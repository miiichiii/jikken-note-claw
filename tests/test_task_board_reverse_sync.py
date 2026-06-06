from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


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
        self.original_state_path = reverse_sync.DEFAULT_STATE_PATH
        reverse_sync.DEFAULT_STATE_PATH = self.state_path

    def tearDown(self) -> None:
        reverse_sync.DEFAULT_STATE_PATH = self.original_state_path
        try:
            reverse_sync.LOCK_PATH.unlink()
        except FileNotFoundError:
            pass
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
