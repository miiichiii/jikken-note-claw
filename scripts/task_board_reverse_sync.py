#!/usr/bin/env python3
"""Safe reverse-sync for task-board checkbox updates back to Meta TODO."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_META_TODO = Path(
    os.environ.get(
        "METATODO_PATH",
        "/Users/michito/Library/Mobile Documents/iCloud~md~obsidian/Documents/"
        "Hamada_Obsidian/Meta TODO.md",
    )
)
DEFAULT_TASKS_JSON = Path(os.environ.get("TASK_BOARD_TASKS_JSON", ROOT / "site-public" / "tasks.json"))
DEFAULT_STATE_PATH = Path(
    os.environ.get("TASK_BOARD_REVERSE_SYNC_STATE", "/Users/michito/.openclaw/state/task_board_reverse_sync_state.json")
)
DEFAULT_TOKEN_PATH = Path(
    os.environ.get("TASK_BOARD_REVERSE_SYNC_TOKEN", "/Users/michito/.openclaw/state/task_board_reverse_sync_token.txt")
)
DEFAULT_BACKUP_DIR = Path(
    os.environ.get("TASK_BOARD_REVERSE_SYNC_BACKUP_DIR", "/Users/michito/.openclaw/state/task_board_reverse_sync_backups")
)
LOCK_PATH = Path(os.environ.get("TASK_BOARD_REVERSE_SYNC_LOCK", "/tmp/ai.openclaw.metatodo-taskboard-reverse-sync.lock"))
AGENT = ROOT / "scripts" / "meta_todo_task_board_agent.py"
OBSIDIAN_VAULT = Path(
    os.environ.get(
        "OBSIDIAN_VAULT",
        "/Users/michito/Library/Mobile Documents/iCloud~md~obsidian/Documents/Hamada_Obsidian",
    )
)
OBSIDIAN_VAULT_NAME = os.environ.get("OBSIDIAN_VAULT_NAME", "Hamada_Obsidian")
OBSIDIAN_BIN = os.environ.get("OBSIDIAN_BIN", "/opt/homebrew/bin/obsidian")
CLI_MODE = os.environ.get("METATODO_USE_OBSIDIAN_CLI") == "1"

TASK_LINE_RE = re.compile(
    r"^(?P<prefix>\s*[-*]\s+\[)(?P<mark>[ xX])(?P<suffix>\]\s+.*?)(?:\s*<!--\s*mtodo:(?P<id>[^>\s]+)\s*-->)?\s*$"
)


@dataclass
class SourceTask:
    task_id: str
    line_index: int
    status: str
    line: str


class ReverseSyncError(RuntimeError):
    def __init__(self, message: str, *, code: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:" + env.get("PATH", "")
    return subprocess.run(
        cmd,
        cwd=cwd or ROOT,
        text=True,
        capture_output=True,
        check=check,
        env=env,
    )


def obsidian_cmd(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run([OBSIDIAN_BIN, *args, f"vault={OBSIDIAN_VAULT_NAME}"], check=check)


def _vault_rel(path: Path) -> str | None:
    try:
        return str(path.resolve().relative_to(OBSIDIAN_VAULT.resolve()))
    except ValueError:
        return None


def read_text(path: Path) -> str:
    rel = _vault_rel(path)
    if CLI_MODE and rel is not None:
        return obsidian_cmd("read", f"path={rel}").stdout
    return path.read_text(encoding="utf-8")


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def write_text(path: Path, text: str) -> None:
    rel = _vault_rel(path)
    if CLI_MODE and rel is not None:
        code = f"app.vault.adapter.write({json.dumps(rel)}, {json.dumps(text)})"
        obsidian_cmd("eval", f"code={code}")
        return
    atomic_write_text(path, text)


def parse_source_tasks(text: str) -> tuple[dict[str, SourceTask], set[str]]:
    tasks: dict[str, SourceTask] = {}
    duplicates: set[str] = set()
    for index, line in enumerate(text.splitlines()):
        match = TASK_LINE_RE.match(line)
        if not match or not match.group("id"):
            continue
        task_id = match.group("id")
        status = "done" if match.group("mark").lower() == "x" else "todo"
        if task_id in tasks:
            duplicates.add(task_id)
            continue
        tasks[task_id] = SourceTask(task_id=task_id, line_index=index, status=status, line=line)
    return tasks, duplicates


def replace_checkbox(line: str, desired_status: str) -> str:
    wanted_mark = "x" if desired_status == "done" else " "
    return re.sub(r"^(\s*[-*]\s+\[)[ xX](\].*)$", rf"\1{wanted_mark}\2", line, count=1)


def backup_source(path: Path, *, backup_dir: Path = DEFAULT_BACKUP_DIR, task_id: str) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"{stamp}-{task_id}-{path.name}"
    shutil.copy2(path, backup_path)
    return backup_path


def acquire_lock() -> None:
    try:
        fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ReverseSyncError(
            f"reverse sync lock exists: {LOCK_PATH}",
            code="busy",
            status_code=409,
        ) from exc
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(f"{os.getpid()}\n")


def write_state(payload: dict[str, object], *, state_path: Path = DEFAULT_STATE_PATH) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(state_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def validate_status(status: str) -> str:
    if status not in {"todo", "done"}:
        raise ReverseSyncError(
            f"desired status must be todo or done, got {status!r}",
            code="invalid_status",
            status_code=400,
        )
    return status


def load_tasks_json_status(tasks_json: Path) -> dict[str, str]:
    if not tasks_json.exists():
        return {}
    data = json.loads(tasks_json.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ReverseSyncError("tasks.json must be a JSON array", code="tasks_json_invalid", status_code=500)
    statuses: dict[str, str] = {}
    duplicates: set[str] = set()
    for task in data:
        if not isinstance(task, dict):
            continue
        task_id = str(task.get("id", ""))
        if not task_id:
            continue
        if task_id in statuses:
            duplicates.add(task_id)
            continue
        statuses[task_id] = str(task.get("status") or "todo")
    if duplicates:
        dupes = ", ".join(sorted(duplicates)[:5])
        raise ReverseSyncError(
            f"duplicate task ids in tasks.json: {dupes}",
            code="tasks_json_duplicate_id",
            status_code=500,
        )
    return statuses


def run_agent(commit_message: str) -> subprocess.CompletedProcess[str]:
    return run(["python3", str(AGENT), "--commit-message", commit_message], cwd=ROOT, check=True)


def verify_tasks_json_status(tasks_json: Path, task_id: str, desired_status: str) -> None:
    statuses = load_tasks_json_status(tasks_json)
    actual = statuses.get(task_id)
    if actual != desired_status:
        raise ReverseSyncError(
            f"tasks.json status for {task_id} is {actual!r}, expected {desired_status!r}",
            code="verify_failed",
            status_code=502,
        )


def reverse_sync_task(
    *,
    task_id: str,
    desired_status: str,
    expected_current_status: str,
    meta_todo_path: Path = DEFAULT_META_TODO,
    tasks_json_path: Path = DEFAULT_TASKS_JSON,
    backup_dir: Path = DEFAULT_BACKUP_DIR,
    agent_runner: Callable[[str], subprocess.CompletedProcess[str]] = run_agent,
) -> dict[str, object]:
    desired_status = validate_status(desired_status)
    expected_current_status = validate_status(expected_current_status)
    started_at = now_iso()
    state: dict[str, object] = {
        "task_id": task_id,
        "desired_status": desired_status,
        "expected_current_status": expected_current_status,
        "started_at": started_at,
        "meta_todo_path": str(meta_todo_path),
        "tasks_json_path": str(tasks_json_path),
    }

    acquire_lock()
    try:
        source_before = read_text(meta_todo_path)
        tasks, duplicates = parse_source_tasks(source_before)
        if duplicates:
            dupes = ", ".join(sorted(duplicates)[:5])
            raise ReverseSyncError(
                f"duplicate task ids in Meta TODO: {dupes}",
                code="duplicate_id",
                status_code=409,
            )

        task = tasks.get(task_id)
        if task is None:
            raise ReverseSyncError(
                f"task id not found in Meta TODO: {task_id}",
                code="task_not_found",
                status_code=404,
            )
        if task.status != expected_current_status:
            raise ReverseSyncError(
                f"current status is {task.status}, expected {expected_current_status}",
                code="stale_status",
                status_code=409,
            )

        line_number = task.line_index + 1
        state["line_number"] = line_number
        if task.status == desired_status:
            state.update(
                {
                    "status": "noop",
                    "source_updated": False,
                    "published": False,
                    "finished_at": now_iso(),
                }
            )
            write_state(state)
            return state

        raw_lines = source_before.splitlines(keepends=True)
        old_line_with_newline = raw_lines[task.line_index]
        if old_line_with_newline.endswith("\r\n"):
            newline = "\r\n"
            old_line = old_line_with_newline[:-2]
        elif old_line_with_newline.endswith("\n"):
            newline = "\n"
            old_line = old_line_with_newline[:-1]
        else:
            newline = ""
            old_line = old_line_with_newline
        new_line = replace_checkbox(old_line, desired_status)
        if new_line == old_line:
            raise ReverseSyncError(
                f"could not update checkbox on line {line_number}",
                code="checkbox_replace_failed",
                status_code=500,
            )
        latest_before_write = read_text(meta_todo_path)
        if latest_before_write != source_before:
            raise ReverseSyncError(
                "Meta TODO changed during sync; reload and retry",
                code="source_changed",
                status_code=409,
            )
        raw_lines[task.line_index] = new_line + newline
        source_after = "".join(raw_lines)

        backup_path = backup_source(meta_todo_path, backup_dir=backup_dir, task_id=task_id)
        write_text(meta_todo_path, source_after)

        reread = read_text(meta_todo_path)
        new_tasks, new_duplicates = parse_source_tasks(reread)
        if new_duplicates:
            raise ReverseSyncError(
                "duplicate ids detected after write",
                code="duplicate_id_after_write",
                status_code=500,
            )
        updated = new_tasks.get(task_id)
        if updated is None or updated.status != desired_status:
            raise ReverseSyncError(
                f"post-write status verification failed for {task_id}",
                code="post_write_verify_failed",
                status_code=500,
            )

        state.update(
            {
                "backup_path": str(backup_path),
                "line_number": line_number,
                "before_status": task.status,
                "after_status": desired_status,
                "source_updated": True,
                "before_hash": hashlib.sha256(source_before.encode("utf-8")).hexdigest(),
                "after_hash": hashlib.sha256(source_after.encode("utf-8")).hexdigest(),
            }
        )

        commit_message = f"Reverse sync task board checkbox: {task_id} -> {desired_status}"
        try:
            agent = agent_runner(commit_message)
            state["agent_stdout"] = agent.stdout.strip()
            state["agent_stderr"] = agent.stderr.strip()
            verify_tasks_json_status(tasks_json_path, task_id, desired_status)
            state["published"] = True
            state["status"] = "ok"
        except (subprocess.CalledProcessError, ReverseSyncError) as exc:
            state["published"] = False
            state["status"] = "source_updated_public_sync_failed"
            state["warning"] = str(exc)
            if isinstance(exc, subprocess.CalledProcessError):
                state["agent_stdout"] = exc.stdout.strip()
                state["agent_stderr"] = exc.stderr.strip()
            else:
                state["agent_stderr"] = str(exc)

        state["finished_at"] = now_iso()
        write_state(state)
        return state
    finally:
        try:
            LOCK_PATH.unlink()
        except FileNotFoundError:
            pass


def load_or_create_token(token_path: Path = DEFAULT_TOKEN_PATH, *, rotate: bool = False) -> str:
    if rotate or not token_path.exists():
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token = secrets.token_urlsafe(24)
        atomic_write_text(token_path, token + "\n")
        return token
    return token_path.read_text(encoding="utf-8").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    token_parser = subparsers.add_parser("token", help="Print or rotate the local task-board sync token")
    token_parser.add_argument("--rotate", action="store_true")
    token_parser.add_argument("--token-path", type=Path, default=DEFAULT_TOKEN_PATH)

    apply_parser = subparsers.add_parser("apply", help="Apply one reverse-sync checkbox update")
    apply_parser.add_argument("--task-id", required=True)
    apply_parser.add_argument("--desired-status", required=True, choices=("todo", "done"))
    apply_parser.add_argument("--expected-current-status", required=True, choices=("todo", "done"))
    apply_parser.add_argument("--meta-todo", type=Path, default=DEFAULT_META_TODO)
    apply_parser.add_argument("--tasks-json", type=Path, default=DEFAULT_TASKS_JSON)
    apply_parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)

    args = parser.parse_args()

    if args.command == "token":
        print(load_or_create_token(args.token_path, rotate=args.rotate))
        return 0

    try:
        result = reverse_sync_task(
            task_id=args.task_id,
            desired_status=args.desired_status,
            expected_current_status=args.expected_current_status,
            meta_todo_path=args.meta_todo,
            tasks_json_path=args.tasks_json,
            backup_dir=args.backup_dir,
        )
    except ReverseSyncError as exc:
        print(json.dumps({"status": "error", "code": exc.code, "message": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
