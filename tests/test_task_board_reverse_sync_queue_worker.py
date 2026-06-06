from __future__ import annotations

import sys
import unittest
from pathlib import Path


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
