#!/usr/bin/env python3
"""Deterministic sync agent for Meta TODO -> public task board."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(os.environ.get("TASK_BOARD_ROOT", Path(__file__).resolve().parents[1]))
GENERATOR = ROOT / "scripts" / "meta_todo_to_tasks_json.py"
TASKS_JSON = ROOT / "site-public" / "tasks.json"
STATE_PATH = Path("/Users/michito/.openclaw/state/meta_todo_task_board_agent.json")
LOCK_PATH = Path("/tmp/ai.openclaw.metatodo-taskboard-agent.lock")
AGENT_HOME = Path("/Users/michito/.openclaw/metatodo-taskboard-agent")
OBSIDIAN_BIN = os.environ.get("OBSIDIAN_BIN", "/opt/homebrew/bin/obsidian")
OBSIDIAN_VAULT_NAME = os.environ.get("OBSIDIAN_VAULT_NAME", "Hamada_Obsidian")
OBSIDIAN_SOURCE_REL = os.environ.get("OBSIDIAN_SOURCE_REL", "Meta TODO.md")
PUBLIC_URL = "https://site-public.vercel.app/tasks.json"
VERCEL_SCOPE = "miiichiiis-projects"

PRIVATE_PATTERNS = [
    re.compile(r"/Users/michito"),
    re.compile(r"Library/Mobile Documents"),
    re.compile(r"90_Processed"),
    re.compile(r"Source PDF", re.IGNORECASE),
    re.compile(r"\bid:[A-Za-z0-9_-]+"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"hamamichi", re.IGNORECASE),
    re.compile(r"md\.tsukuba", re.IGNORECASE),
]


def run(
    cmd: list[str],
    *,
    check: bool = True,
    capture: bool = True,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:" + env.get("PATH", "")
    return subprocess.run(
        cmd,
        cwd=cwd or ROOT,
        text=True,
        capture_output=capture,
        check=check,
        env=env,
    )


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_tasks() -> list[dict[str, object]]:
    data = json.loads(TASKS_JSON.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise RuntimeError("tasks.json must contain a JSON array")
    if not data:
        raise RuntimeError("refusing to publish 0 tasks from Meta TODO")
    for index, task in enumerate(data):
        if not isinstance(task, dict):
            raise RuntimeError(f"task #{index + 1} is not an object")
        for key in ("id", "title", "status", "priority", "assignee"):
            if key not in task:
                raise RuntimeError(f"task #{index + 1} is missing {key}")
    return data


def prepare_meta_todo_source() -> Path | None:
    if os.environ.get("METATODO_USE_OBSIDIAN_CLI") != "1":
        return None
    AGENT_HOME.mkdir(parents=True, exist_ok=True)
    source_copy = AGENT_HOME / "meta_todo_source.md"
    result = run(
        [
            OBSIDIAN_BIN,
            "read",
            f"path={OBSIDIAN_SOURCE_REL}",
            f"vault={OBSIDIAN_VAULT_NAME}",
        ]
    )
    source_copy.write_text(result.stdout, encoding="utf-8")
    return source_copy


def privacy_scan(tasks: list[dict[str, object]]) -> list[str]:
    findings: list[str] = []
    for task in tasks:
        haystack = " ".join(str(task.get(key, "")) for key in ("id", "title", "assignee"))
        for pattern in PRIVATE_PATTERNS:
            if pattern.search(haystack):
                findings.append(f"{task.get('id', '<no-id>')}: matched {pattern.pattern}")
                break
    return findings


def git_changed() -> bool:
    result = run(["git", "diff", "--quiet", "--", str(TASKS_JSON.relative_to(ROOT))], check=False)
    return result.returncode == 1


def git_pull_if_configured() -> None:
    if os.environ.get("METATODO_AGENT_GIT_PULL") != "1":
        return
    status = run(["git", "status", "--porcelain"], check=True)
    if status.stdout.strip():
        raise RuntimeError("agent worktree is dirty before pull")
    run(["git", "pull", "--ff-only", "origin", "main"])


def git_commit_push(message: str) -> str:
    run(["git", "add", str(TASKS_JSON.relative_to(ROOT))])
    commit = run(["git", "commit", "-m", message])
    run(["git", "push", "origin", "main"])
    return commit.stdout.strip()


def deploy() -> str:
    result = run(
        [
            "npx",
            "--yes",
            "vercel@latest",
            "deploy",
            "--prod",
            "--yes",
            "--scope",
            VERCEL_SCOPE,
        ],
        cwd=ROOT / "site-public",
    )
    return result.stdout.strip()


def verify_public(timeout_seconds: int = 45) -> dict[str, object]:
    deadline = time.time() + timeout_seconds
    local_hash = sha256(TASKS_JSON)
    last_error = ""
    while time.time() < deadline:
        result = run(["curl", "-L", "-sS", "--max-time", "15", PUBLIC_URL], check=False)
        if result.returncode == 0 and result.stdout.strip():
            remote_bytes = result.stdout.encode("utf-8")
            remote_hash = hashlib.sha256(remote_bytes).hexdigest()
            if remote_hash == local_hash:
                remote_tasks = json.loads(result.stdout)
                return {
                    "ok": True,
                    "count": len(remote_tasks),
                    "done": sum(1 for task in remote_tasks if task.get("status") == "done"),
                    "hash": remote_hash,
                }
            last_error = f"hash mismatch remote={remote_hash} local={local_hash}"
        else:
            last_error = result.stderr.strip() or f"curl exit {result.returncode}"
        time.sleep(5)
    return {"ok": False, "error": last_error, "local_hash": local_hash}


def write_state(payload: dict[str, object]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def acquire_lock() -> None:
    try:
        fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RuntimeError(f"lock exists: {LOCK_PATH}") from exc
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(f"{os.getpid()}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-deploy", action="store_true", help="Commit/push changes but skip Vercel deploy")
    parser.add_argument("--dry-run", action="store_true", help="Generate and validate, but do not commit/push/deploy")
    parser.add_argument("--commit-message", default="Sync task board from Meta TODO")
    args = parser.parse_args()

    started = datetime.now(timezone.utc).isoformat()
    state: dict[str, object] = {"started_at": started, "root": str(ROOT)}

    try:
        acquire_lock()
        git_pull_if_configured()
        before_hash = sha256(TASKS_JSON)
        meta_todo_source = prepare_meta_todo_source()
        generator_cmd = ["python3", str(GENERATOR.relative_to(ROOT))]
        if meta_todo_source is not None:
            generator_cmd.extend(["--meta-todo", str(meta_todo_source)])
        generator = run(generator_cmd)
        state["generator"] = generator.stdout.strip()

        tasks = load_tasks()
        findings = privacy_scan(tasks)
        if findings:
            state.update({"status": "blocked_privacy", "findings": findings})
            write_state(state)
            for finding in findings:
                print(f"privacy block: {finding}", file=sys.stderr)
            return 2

        changed = git_changed()
        state.update(
            {
                "status": "changed" if changed else "no_change",
                "before_hash": before_hash,
                "after_hash": sha256(TASKS_JSON),
                "count": len(tasks),
                "done": sum(1 for task in tasks if task.get("status") == "done"),
                "dry_run": args.dry_run,
            }
        )

        if not changed:
            public_verify = verify_public(timeout_seconds=15)
            state["public_verify"] = public_verify
            if not public_verify.get("ok") and not args.dry_run and not args.no_deploy:
                state["deploy"] = deploy()
                state["public_verify"] = verify_public()
                state["status"] = "redeployed_drift" if state["public_verify"].get("ok") else "deploy_unverified"
                state["finished_at"] = datetime.now(timezone.utc).isoformat()
                write_state(state)
                print(json.dumps(state, ensure_ascii=False, indent=2))
                return 0
            write_state(state)
            print(f"no change ({len(tasks)} tasks, {state['done']} done)")
            return 0

        if args.dry_run:
            write_state(state)
            print(f"dry run: tasks.json changed ({len(tasks)} tasks)")
            return 0

        state["commit"] = git_commit_push(args.commit_message)

        if args.no_deploy:
            state["deploy"] = "skipped"
        else:
            state["deploy"] = deploy()
            state["public_verify"] = verify_public()

        state["status"] = "ok"
        state["finished_at"] = datetime.now(timezone.utc).isoformat()
        write_state(state)
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        state.update({"status": "error", "error": str(exc), "finished_at": datetime.now(timezone.utc).isoformat()})
        write_state(state)
        print(f"MetaTODO Task Board Agent failed: {exc}", file=sys.stderr)
        return 1
    finally:
        try:
            LOCK_PATH.unlink()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
