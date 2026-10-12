from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import task_board_reverse_sync as reverse_sync  # noqa: E402
import task_board_reverse_sync_queue_worker as worker  # noqa: E402


def request_issue(task_id: str = "mtodo-sample-1", desired_status: str = "done", expected_status: str = "todo") -> dict[str, object]:
    return {
        "number": 101,
        "body": "\n".join(
            [
                worker.REQUEST_MARKER,
                "```json",
                (
                    "{\n"
                    f'  "taskId": "{task_id}",\n'
                    f'  "desiredStatus": "{desired_status}",\n'
                    f'  "expectedCurrentStatus": "{expected_status}",\n'
                    '  "clientRequestId": "req-12345678"\n'
                    "}"
                ),
                "```",
            ]
        ),
        "labels": [{"name": worker.QUEUE_LABEL}],
    }


class FakeGitHubClient:
    def __init__(self) -> None:
        self.updated: list[tuple[int, str | None, list[str] | None]] = []
        self.comments: list[tuple[int, str]] = []

    def issue_labels(self, issue: dict[str, object]) -> list[str]:
        return [str(item["name"]) for item in issue.get("labels", [])]

    def update_issue(self, issue_number: int, *, state: str | None = None, labels: list[str] | None = None) -> dict[str, object]:
        self.updated.append((issue_number, state, labels))
        return {"number": issue_number, "state": state, "labels": labels or []}

    def add_comment(self, issue_number: int, body: str) -> dict[str, object]:
        self.comments.append((issue_number, body))
        return {"id": 1, "body": body}


class QueueWorkerTests(unittest.TestCase):
    def test_real_reverse_sync_public_proof_controls_partial_or_synced(self) -> None:
        for public_ok, sync_state, label in (
            (False, "partial", worker.PARTIAL_LABEL),
            (True, "synced", worker.SUCCESS_LABEL),
        ):
            with self.subTest(public_ok=public_ok), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                note = root / "Meta TODO.md"
                tasks_json = root / "tasks.json"
                agent_state = root / "agent-state.json"
                note.write_text("- [ ] Task <!-- mtodo:mtodo-sample-1 -->\n", encoding="utf-8")
                original_write_state = reverse_sync.write_state

                def process(cmd, **_kwargs):
                    canonical_tasks, _duplicates = reverse_sync.parse_source_tasks(note.read_text())
                    tasks_json.write_text(json.dumps([
                        {"id": task.task_id, "status": task.status}
                        for task in canonical_tasks.values()
                    ]), encoding="utf-8")
                    current_hash = hashlib.sha256(tasks_json.read_bytes()).hexdigest()
                    agent_state.write_text(json.dumps({
                        "started_at": datetime.now(timezone.utc).isoformat(),
                        "after_hash": current_hash,
                        "public_verify": {"ok": public_ok, "hash": current_hash},
                    }), encoding="utf-8")
                    return subprocess.CompletedProcess(cmd, 0, stdout="exit zero", stderr="")

                def runner(**kwargs):
                    return reverse_sync.reverse_sync_task(
                        **kwargs, meta_todo_path=note, tasks_json_path=tasks_json,
                        backup_dir=root / "backups",
                    )

                github = FakeGitHubClient()
                with (
                    patch.object(reverse_sync, "LOCK_PATH", root / "sync.lock"),
                    patch.object(reverse_sync, "AGENT_STATE_PATH", agent_state),
                    patch.object(reverse_sync, "run", side_effect=process),
                    patch.object(reverse_sync, "write_state", side_effect=lambda payload: original_write_state(
                        payload, state_path=root / "sync-state.json"
                    )),
                ):
                    result = worker.process_issue(
                        request_issue(), github=github, reverse_sync_runner=runner
                    )

                self.assertEqual(result["syncState"], sync_state)
                self.assertEqual(result["result"]["published"], public_ok)
                self.assertTrue(result["result"]["source_updated"])
                self.assertIn("- [x]", note.read_text())
                self.assertEqual(github.updated[-1], (101, "closed", [worker.QUEUE_LABEL, label]))

    def test_validate_request_payload_rejects_bad_client_request_id(self) -> None:
        with self.assertRaises(worker.QueueWorkerError):
            worker.validate_request_payload(
                {
                    "taskId": "mtodo-sample-1",
                    "desiredStatus": "done",
                    "expectedCurrentStatus": "todo",
                    "clientRequestId": "bad",
                }
            )

    def test_process_issue_success_closes_with_synced_label(self) -> None:
        github = FakeGitHubClient()
        issue = request_issue()

        def runner(**kwargs):
            self.assertEqual(kwargs["task_id"], "mtodo-sample-1")
            self.assertEqual(kwargs["desired_status"], "done")
            self.assertEqual(kwargs["expected_current_status"], "todo")
            return {"status": "ok", "published": True}

        result = worker.process_issue(issue, github=github, reverse_sync_runner=runner)

        self.assertEqual(result["syncState"], "synced")
        self.assertEqual(github.updated[0][2], [worker.QUEUE_LABEL, worker.PROCESSING_LABEL])
        self.assertEqual(github.updated[-1][1], "closed")
        self.assertEqual(github.updated[-1][2], [worker.QUEUE_LABEL, worker.SUCCESS_LABEL])
        self.assertIn(worker.RESULT_MARKER, github.comments[0][1])

    def test_process_issue_conflict_maps_to_failed_conflict(self) -> None:
        github = FakeGitHubClient()
        issue = request_issue(expected_status="todo")

        def runner(**_kwargs):
            raise reverse_sync.ReverseSyncError("current status is done, expected todo", code="stale_status", status_code=409)

        result = worker.process_issue(issue, github=github, reverse_sync_runner=runner)

        self.assertEqual(result["syncState"], "failed_conflict")
        self.assertEqual(github.updated[-1][2], [worker.QUEUE_LABEL, worker.CONFLICT_LABEL])
        self.assertIn('"code": "stale_status"', github.comments[0][1])


if __name__ == "__main__":
    unittest.main()
