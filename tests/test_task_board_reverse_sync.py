from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import task_board_reverse_sync as reverse_sync  # noqa: E402


REAL_META_TODO = Path(
    "/Users/michito/Library/Mobile Documents/iCloud~md~obsidian/Documents/"
    "Hamada_Obsidian/Meta TODO.md"
)


class ReverseSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.tempdir.name)
        self.meta_todo = self.temp_path / "Meta TODO.md"
        self.tasks_json = self.temp_path / "tasks.json"
        self.backups = self.temp_path / "backups"
        self.state_path = self.temp_path / "state.json"
        self.agent_state_path = self.temp_path / "agent-state.json"
        original_write_state = reverse_sync.write_state
        self.patches = [
            patch.object(reverse_sync, "LOCK_PATH", self.temp_path / "sync.lock"),
            patch.object(reverse_sync, "AGENT_STATE_PATH", self.agent_state_path),
            patch.object(
                reverse_sync, "write_state",
                side_effect=lambda payload: original_write_state(payload, state_path=self.state_path),
            ),
        ]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        self.tempdir.cleanup()

    def agent_runner(self, _commit_message: str):
        text = self.meta_todo.read_text(encoding="utf-8")
        tasks, duplicates = reverse_sync.parse_source_tasks(text)
        self.assertFalse(duplicates)
        payload = [
            {
                "id": task.task_id,
                "title": f"Task {task.task_id}",
                "status": task.status,
                "priority": "B",
                "assignee": "Me",
                "category": "Test",
                "parentCategory": "Test",
                "section": "Test",
                "syncable": True,
            }
            for task in tasks.values()
        ]
        self.tasks_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        class Result:
            stdout = "ok"
            stderr = ""

        return Result()

    def apply_sample(self, **kwargs):
        self.meta_todo.write_text("- [ ] Task <!-- mtodo:mtodo-sample-1 -->\n", encoding="utf-8")
        return reverse_sync.reverse_sync_task(
            task_id="mtodo-sample-1", desired_status="done", expected_current_status="todo",
            meta_todo_path=self.meta_todo, tasks_json_path=self.tasks_json,
            backup_dir=self.backups, **kwargs,
        )

    def simulated_agent_process(self, verification: str):
        """Emulate exit-zero and generated local bytes; never launch the live agent."""
        def process(_cmd, **_kwargs):
            self.agent_runner("fixture generation")
            current_hash = hashlib.sha256(self.tasks_json.read_bytes()).hexdigest()
            state = {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "status": "no_change",  # Real no-change state has no finished_at.
                "after_hash": current_hash,
                "public_verify": {"ok": True, "hash": current_hash},
            }
            if verification == "false":
                state["public_verify"]["ok"] = False
            elif verification == "stale":
                state["started_at"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            elif verification == "future":
                state["started_at"] = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
            elif verification == "naive":
                state["started_at"] = datetime.now().isoformat()
            elif verification == "public_hash_mismatch":
                state["public_verify"]["hash"] = "0" * 64
            elif verification == "generated_hash_mismatch":
                state["after_hash"] = "0" * 64
            elif verification == "missing_public":
                del state["public_verify"]
            elif verification == "truthy_ok":
                state["public_verify"]["ok"] = "true"
            if verification == "missing_state":
                self.agent_state_path.unlink(missing_ok=True)
            else:
                self.agent_state_path.write_text(
                    "{invalid" if verification == "malformed_state" else json.dumps(state),
                    encoding="utf-8",
                )
            return subprocess.CompletedProcess(_cmd, 0, stdout="agent exited zero", stderr="")
        return process

    def test_default_agent_accepts_fresh_matching_public_verification(self) -> None:
        with patch.object(reverse_sync, "run", side_effect=self.simulated_agent_process("fresh")):
            result = self.apply_sample()
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["source_updated"])
        self.assertTrue(result["published"])

    def test_exit_zero_without_current_public_proof_preserves_canonical_save(self) -> None:
        for verification in (
            "false", "stale", "future", "naive", "public_hash_mismatch",
            "generated_hash_mismatch", "missing_public", "truthy_ok",
            "missing_state", "malformed_state",
        ):
            with self.subTest(verification=verification):
                with patch.object(reverse_sync, "run", side_effect=self.simulated_agent_process(verification)):
                    result = self.apply_sample()
                self.assertEqual(result["status"], "source_updated_public_sync_failed")
                self.assertTrue(result["source_updated"])
                self.assertFalse(result["published"])
                self.assertIn("freshly verify", result["warning"])
                self.assertEqual(
                    self.meta_todo.read_text(encoding="utf-8"),
                    "- [x] Task <!-- mtodo:mtodo-sample-1 -->\n",
                )
                self.assertEqual(json.loads(self.state_path.read_text())["published"], False)

    def test_reverse_sync_updates_only_checkbox_in_sample(self) -> None:
        source = (
            "## Sample\n"
            "- [ ] First task <!-- mtodo:mtodo-sample-1 -->\n"
            "- [x] Second task <!-- mtodo:mtodo-sample-2 -->\n"
            "plain line\n"
        )
        self.meta_todo.write_text(source, encoding="utf-8")
        before_lines = self.meta_todo.read_text(encoding="utf-8").splitlines()

        result = reverse_sync.reverse_sync_task(
            task_id="mtodo-sample-1",
            desired_status="done",
            expected_current_status="todo",
            meta_todo_path=self.meta_todo,
            tasks_json_path=self.tasks_json,
            backup_dir=self.backups,
            agent_runner=self.agent_runner,
        )

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["published"])

        after_lines = self.meta_todo.read_text(encoding="utf-8").splitlines()
        changed_indexes = [index for index, (before, after) in enumerate(zip(before_lines, after_lines)) if before != after]
        self.assertEqual(changed_indexes, [1])
        self.assertEqual(after_lines[1], "- [x] First task <!-- mtodo:mtodo-sample-1 -->")
        self.assertEqual(after_lines[2], before_lines[2])
        self.assertEqual(after_lines[3], before_lines[3])

    def test_reverse_sync_rejects_stale_status(self) -> None:
        self.meta_todo.write_text("- [x] Done task <!-- mtodo:mtodo-sample-1 -->\n", encoding="utf-8")

        with self.assertRaises(reverse_sync.ReverseSyncError) as ctx:
            reverse_sync.reverse_sync_task(
                task_id="mtodo-sample-1",
                desired_status="todo",
                expected_current_status="todo",
                meta_todo_path=self.meta_todo,
                tasks_json_path=self.tasks_json,
                backup_dir=self.backups,
                agent_runner=self.agent_runner,
            )

        self.assertEqual(ctx.exception.code, "stale_status")

    def test_reverse_sync_rejects_duplicate_ids(self) -> None:
        self.meta_todo.write_text(
            "- [ ] One <!-- mtodo:mtodo-dup -->\n"
            "- [x] Two <!-- mtodo:mtodo-dup -->\n",
            encoding="utf-8",
        )

        with self.assertRaises(reverse_sync.ReverseSyncError) as ctx:
            reverse_sync.reverse_sync_task(
                task_id="mtodo-dup",
                desired_status="done",
                expected_current_status="todo",
                meta_todo_path=self.meta_todo,
                tasks_json_path=self.tasks_json,
                backup_dir=self.backups,
                agent_runner=self.agent_runner,
            )

        self.assertEqual(ctx.exception.code, "duplicate_id")

    def test_real_meta_todo_copy_changes_only_target_checkbox(self) -> None:
        source = REAL_META_TODO.read_text(encoding="utf-8")
        self.meta_todo.write_text(source, encoding="utf-8")
        tasks, duplicates = reverse_sync.parse_source_tasks(source)
        self.assertFalse(duplicates)
        target = next(task for task in tasks.values() if task.status == "todo")
        before_lines = source.splitlines()

        result = reverse_sync.reverse_sync_task(
            task_id=target.task_id,
            desired_status="done",
            expected_current_status="todo",
            meta_todo_path=self.meta_todo,
            tasks_json_path=self.tasks_json,
            backup_dir=self.backups,
            agent_runner=self.agent_runner,
        )

        self.assertEqual(result["status"], "ok")
        after_lines = self.meta_todo.read_text(encoding="utf-8").splitlines()
        changed_indexes = [index for index, (before, after) in enumerate(zip(before_lines, after_lines)) if before != after]
        self.assertEqual(changed_indexes, [target.line_index])
        self.assertTrue(after_lines[target.line_index].startswith("- [x]"))
        for index in (0, target.line_index - 1, min(len(after_lines) - 1, target.line_index + 1)):
            if index == target.line_index:
                continue
            self.assertEqual(after_lines[index], before_lines[index])


if __name__ == "__main__":
    unittest.main()
