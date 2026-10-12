from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import meta_todo_task_board_agent as agent  # noqa: E402


class AgentLockOwnershipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.lock = self.root / "agent.lock"
        self.state = self.root / "state.json"
        self.tasks = self.root / "site-public" / "tasks.json"
        self.tasks.parent.mkdir()
        self.tasks.write_text(json.dumps([{
            "id": "fixture-task", "title": "Fixture", "status": "todo",
            "priority": "B", "assignee": "Me",
        }]))
        # Keep every filesystem path local and prevent all subprocess/network work.
        values = {
            "ROOT": self.root,
            "GENERATOR": self.root / "scripts" / "generator.py",
            "TASKS_JSON": self.tasks,
            "STATE_PATH": self.state,
            "LOCK_PATH": self.lock,
            "AGENT_HOME": self.root / "agent-home",
        }
        self.enterContext(patch.multiple(agent, **values))
        self.runner = self.enterContext(patch.object(
            agent, "run", return_value=subprocess.CompletedProcess([], 0, "fixture generated", ""),
        ))
        self.pull = self.enterContext(patch.object(agent, "git_pull_if_configured"))
        self.enterContext(patch.object(agent, "prepare_meta_todo_source", return_value=None))
        self.enterContext(patch.object(agent, "git_changed", return_value=False))
        self.verify = self.enterContext(patch.object(
            agent, "verify_public", return_value={"ok": True, "count": 1, "done": 0},
        ))
        self.deploy = self.enterContext(patch.object(agent, "deploy"))
        self.push = self.enterContext(patch.object(agent, "git_commit_push"))
        self.enterContext(patch.object(sys, "argv", ["agent"]))

    def invoke(self) -> int:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return agent.main()

    def test_contention_preserves_other_owner_lock_and_state(self) -> None:
        self.lock.write_bytes(b"another-owner-pid\n")
        self.state.write_bytes(b'{"status":"publishing","owner":"another invocation"}\n')
        lock_before = self.lock.read_bytes()
        state_before = self.state.read_bytes()
        inode_before = self.lock.stat().st_ino

        self.assertEqual(self.invoke(), 1)

        self.assertEqual(self.lock.read_bytes(), lock_before)
        self.assertEqual(self.lock.stat().st_ino, inode_before)
        self.assertEqual(self.state.read_bytes(), state_before)
        self.pull.assert_not_called()
        self.runner.assert_not_called()
        self.verify.assert_not_called()
        self.deploy.assert_not_called()
        self.push.assert_not_called()

    def test_success_releases_own_lock_and_records_verified_state(self) -> None:
        def check_lock_during_generation(*_args, **_kwargs):
            self.assertTrue(self.lock.exists())
            return subprocess.CompletedProcess([], 0, "fixture generated", "")

        self.runner.side_effect = check_lock_during_generation
        self.assertEqual(self.invoke(), 0)
        self.assertFalse(self.lock.exists())
        state = json.loads(self.state.read_text())
        self.assertEqual(state["status"], "no_change")
        self.assertTrue(state["public_verify"]["ok"])
        self.deploy.assert_not_called()
        self.push.assert_not_called()

    def test_failure_after_acquisition_releases_own_lock_and_records_error(self) -> None:
        def fail_after_lock():
            self.assertTrue(self.lock.exists())
            raise RuntimeError("isolated pull failure")

        self.pull.side_effect = fail_after_lock
        self.assertEqual(self.invoke(), 1)
        self.assertFalse(self.lock.exists())
        state = json.loads(self.state.read_text())
        self.assertEqual(state["status"], "error")
        self.assertEqual(state["error"], "isolated pull failure")
        self.runner.assert_not_called()
        self.verify.assert_not_called()
        self.deploy.assert_not_called()
        self.push.assert_not_called()

    def test_privacy_block_releases_own_lock_without_publication(self) -> None:
        self.tasks.write_text(json.dumps([{
            "id": "fixture-task", "title": "private@example.invalid", "status": "todo",
            "priority": "B", "assignee": "Me",
        }]))
        self.assertEqual(self.invoke(), 2)
        self.assertFalse(self.lock.exists())
        self.assertEqual(json.loads(self.state.read_text())["status"], "blocked_privacy")
        self.verify.assert_not_called()
        self.deploy.assert_not_called()
        self.push.assert_not_called()


if __name__ == "__main__":
    unittest.main()
