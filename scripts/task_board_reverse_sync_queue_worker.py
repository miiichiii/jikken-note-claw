#!/usr/bin/env python3
"""Consume authenticated task-board reverse-sync requests from GitHub issues."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import task_board_reverse_sync as reverse_sync


QUEUE_LABEL = "task-board-reverse-sync"
PROCESSING_LABEL = "task-board-reverse-sync-processing"
SUCCESS_LABEL = "task-board-reverse-sync-synced"
PARTIAL_LABEL = "task-board-reverse-sync-partial"
FAILED_LABEL = "task-board-reverse-sync-failed"
CONFLICT_LABEL = "task-board-reverse-sync-conflict"
RESULT_MARKER = "<!-- task-board-reverse-sync-result -->"
REQUEST_MARKER = "<!-- task-board-reverse-sync-request -->"
TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,160}$")
CLIENT_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,120}$")

DEFAULT_REPO = os.environ.get("TASK_BOARD_SYNC_QUEUE_REPO", "miiichiii/jikken-note-claw")
DEFAULT_STATE_PATH = Path(
    os.environ.get("TASK_BOARD_SYNC_QUEUE_STATE", "/Users/michito/.openclaw/state/task_board_reverse_sync_queue_worker.json")
)
DEFAULT_LOCK_PATH = Path(
    os.environ.get("TASK_BOARD_SYNC_QUEUE_LOCK", "/tmp/ai.openclaw.task-board-reverse-sync-queue-worker.lock")
)


class QueueWorkerError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(text, encoding="utf-8")
    os.replace(temp_path, path)


def write_state(payload: dict[str, object], *, state_path: Path = DEFAULT_STATE_PATH) -> None:
    atomic_write_text(state_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def load_marked_json(text: str, marker: str) -> dict[str, object]:
    marker_index = text.find(marker)
    if marker_index == -1:
        raise QueueWorkerError(f"marker not found: {marker}")
    start = text.find("```json", marker_index)
    end = text.find("```", start + 7)
    if start == -1 or end == -1:
        raise QueueWorkerError(f"JSON code fence missing for {marker}")
    payload = json.loads(text[start + 7 : end].strip())
    if not isinstance(payload, dict):
        raise QueueWorkerError(f"payload for {marker} must be an object")
    return payload


def format_result_comment(payload: dict[str, object]) -> str:
    return "\n".join([RESULT_MARKER, "```json", json.dumps(payload, ensure_ascii=False, indent=2), "```"])


def validate_request_payload(payload: dict[str, object]) -> dict[str, str]:
    task_id = str(payload.get("taskId") or "").strip()
    desired_status = str(payload.get("desiredStatus") or "").strip()
    expected_current_status = str(payload.get("expectedCurrentStatus") or "").strip()
    client_request_id = str(payload.get("clientRequestId") or "").strip()
    if not TASK_ID_RE.match(task_id):
        raise QueueWorkerError("invalid taskId in queue request")
    if desired_status not in {"todo", "done"}:
        raise QueueWorkerError("invalid desiredStatus in queue request")
    if expected_current_status not in {"todo", "done"}:
        raise QueueWorkerError("invalid expectedCurrentStatus in queue request")
    if not CLIENT_REQUEST_ID_RE.match(client_request_id):
        raise QueueWorkerError("invalid clientRequestId in queue request")
    return {
        "taskId": task_id,
        "desiredStatus": desired_status,
        "expectedCurrentStatus": expected_current_status,
        "clientRequestId": client_request_id,
    }


def resolve_github_token() -> str:
    token = os.environ.get("TASK_BOARD_SYNC_QUEUE_GITHUB_TOKEN", "").strip()
    if token:
        return token
    result = subprocess.run(
        ["gh", "auth", "token"],
        text=True,
        capture_output=True,
        check=False,
        env=os.environ.copy(),
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise QueueWorkerError("GitHub token unavailable; set TASK_BOARD_SYNC_QUEUE_GITHUB_TOKEN or authenticate gh")
    return result.stdout.strip()


@dataclass
class GitHubIssueQueueClient:
    repo: str
    token: str

    def _api(
        self,
        path: str,
        *,
        method: str = "GET",
        body: dict[str, object] | list[object] | None = None,
    ) -> object:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            url=f"https://api.github.com{path}",
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "task-board-reverse-sync-worker",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise QueueWorkerError(f"GitHub API {exc.code}: {detail}") from exc
        return None if not raw else json.loads(raw)

    @property
    def owner(self) -> str:
        return self.repo.split("/", 1)[0]

    @property
    def repo_name(self) -> str:
        return self.repo.split("/", 1)[1]

    def list_open_requests(self) -> list[dict[str, object]]:
        encoded_label = urllib.parse.quote(QUEUE_LABEL, safe="")
        data = self._api(
            f"/repos/{self.owner}/{self.repo_name}/issues"
            f"?state=open&labels={encoded_label}&per_page=100&sort=created&direction=asc"
        )
        if not isinstance(data, list):
            raise QueueWorkerError("GitHub issue list response must be an array")
        return [issue for issue in data if isinstance(issue, dict) and "pull_request" not in issue]

    def issue_labels(self, issue: dict[str, object]) -> list[str]:
        labels = issue.get("labels") or []
        return [str(label.get("name")) for label in labels if isinstance(label, dict)]

    def update_issue(self, issue_number: int, *, state: str | None = None, labels: list[str] | None = None) -> dict[str, object]:
        payload: dict[str, object] = {}
        if state is not None:
            payload["state"] = state
        if labels is not None:
            payload["labels"] = labels
        data = self._api(f"/repos/{self.owner}/{self.repo_name}/issues/{issue_number}", method="PATCH", body=payload)
        if not isinstance(data, dict):
            raise QueueWorkerError("GitHub issue update response must be an object")
        return data

    def add_comment(self, issue_number: int, body: str) -> dict[str, object]:
        data = self._api(
            f"/repos/{self.owner}/{self.repo_name}/issues/{issue_number}/comments",
            method="POST",
            body={"body": body},
        )
        if not isinstance(data, dict):
            raise QueueWorkerError("GitHub comment response must be an object")
        return data


def normalize_result(
    issue_number: int,
    request_payload: dict[str, object],
    result: dict[str, object] | None = None,
    *,
    error: Exception | None = None,
) -> tuple[list[str], dict[str, object]]:
    if error is None:
        assert result is not None
        sync_status = str(result.get("status") or "ok")
        if sync_status in {"ok", "noop"}:
            labels = [QUEUE_LABEL, SUCCESS_LABEL]
            state = "synced"
        elif sync_status == "source_updated_public_sync_failed":
            labels = [QUEUE_LABEL, PARTIAL_LABEL]
            state = "partial"
        else:
            labels = [QUEUE_LABEL, FAILED_LABEL]
            state = "failed"
        payload = {
            "requestId": issue_number,
            "taskId": request_payload["taskId"],
            "syncState": state,
            "result": result,
            "finishedAt": now_iso(),
        }
        return labels, payload

    if isinstance(error, reverse_sync.ReverseSyncError) and error.code == "stale_status":
        labels = [QUEUE_LABEL, CONFLICT_LABEL]
        state = "failed_conflict"
        code = error.code
    else:
        labels = [QUEUE_LABEL, FAILED_LABEL]
        state = "failed"
        code = getattr(error, "code", error.__class__.__name__)

    payload = {
        "requestId": issue_number,
        "taskId": request_payload.get("taskId", ""),
        "syncState": state,
        "error": {"code": code, "message": str(error)},
        "finishedAt": now_iso(),
    }
    return labels, payload


def process_issue(
    issue: dict[str, object],
    *,
    github: GitHubIssueQueueClient,
    reverse_sync_runner: Callable[..., dict[str, object]] = reverse_sync.reverse_sync_task,
) -> dict[str, object]:
    issue_number = int(issue["number"])
    request_payload = validate_request_payload(load_marked_json(str(issue.get("body") or ""), REQUEST_MARKER))
    current_labels = github.issue_labels(issue)
    processing_labels = [label for label in current_labels if label not in {SUCCESS_LABEL, PARTIAL_LABEL, FAILED_LABEL, CONFLICT_LABEL, PROCESSING_LABEL}]
    if QUEUE_LABEL not in processing_labels:
        processing_labels.append(QUEUE_LABEL)
    processing_labels.append(PROCESSING_LABEL)
    github.update_issue(issue_number, labels=processing_labels)

    try:
        result = reverse_sync_runner(
            task_id=str(request_payload["taskId"]),
            desired_status=str(request_payload["desiredStatus"]),
            expected_current_status=str(request_payload["expectedCurrentStatus"]),
        )
        labels, result_payload = normalize_result(issue_number, request_payload, result=result)
    except Exception as exc:
        labels, result_payload = normalize_result(issue_number, request_payload, error=exc)

    github.add_comment(issue_number, format_result_comment(result_payload))
    github.update_issue(issue_number, state="closed", labels=labels)
    return result_payload


def acquire_lock(lock_path: Path = DEFAULT_LOCK_PATH) -> None:
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise QueueWorkerError(f"worker lock exists: {lock_path}") from exc
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(f"{os.getpid()}\n")


def release_lock(lock_path: Path = DEFAULT_LOCK_PATH) -> None:
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def run_once(
    *,
    repo: str = DEFAULT_REPO,
    reverse_sync_runner: Callable[..., dict[str, object]] = reverse_sync.reverse_sync_task,
) -> dict[str, object]:
    github = GitHubIssueQueueClient(repo=repo, token=resolve_github_token())
    issues = github.list_open_requests()
    if not issues:
        summary = {"status": "idle", "repo": repo, "checked_at": now_iso()}
        write_state(summary)
        return summary
    result = process_issue(issues[0], github=github, reverse_sync_runner=reverse_sync_runner)
    summary = {"status": "processed", "repo": repo, "result": result, "checked_at": now_iso()}
    write_state(summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--poll-interval", type=float, default=15.0)
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()

    acquire_lock()
    try:
        if not args.loop:
            result = run_once(repo=args.repo)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        while True:
            try:
                result = run_once(repo=args.repo)
                print(json.dumps(result, ensure_ascii=False), flush=True)
            except Exception as exc:
                error_state = {"status": "error", "message": str(exc), "checked_at": now_iso()}
                write_state(error_state)
                print(json.dumps(error_state, ensure_ascii=False), file=sys.stderr, flush=True)
            time.sleep(args.poll_interval)
    finally:
        release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
