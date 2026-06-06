#!/usr/bin/env python3
"""Local authenticated HTTP bridge for task-board reverse sync."""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import task_board_reverse_sync as reverse_sync


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
ALLOWED_ORIGINS = {
    "https://site-public.vercel.app",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
}


class ReverseSyncHandler(BaseHTTPRequestHandler):
    server_version = "TaskBoardReverseSync/1.0"

    def _origin_allowed(self) -> str | None:
        origin = self.headers.get("Origin")
        if not origin:
            return None
        return origin if origin in ALLOWED_ORIGINS else None

    def _cors_headers(self) -> dict[str, str]:
        origin = self._origin_allowed()
        headers = {
            "Cache-Control": "no-store",
            "Content-Type": "application/json; charset=utf-8",
        }
        if origin:
            headers["Access-Control-Allow-Origin"] = origin
            headers["Vary"] = "Origin"
        return headers

    def _write_json(self, payload: dict[str, object], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        for key, value in self._cors_headers().items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict[str, object]:
        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length or "0")
        except ValueError as exc:
            raise reverse_sync.ReverseSyncError("invalid content-length", code="invalid_length", status_code=400) from exc
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError as exc:
            raise reverse_sync.ReverseSyncError("request body must be valid JSON", code="invalid_json", status_code=400) from exc
        if not isinstance(data, dict):
            raise reverse_sync.ReverseSyncError("request body must be a JSON object", code="invalid_json", status_code=400)
        return data

    def _authorize(self) -> None:
        header = self.headers.get("Authorization") or ""
        token = getattr(self.server, "sync_token", "")
        if not header.startswith("Bearer ") or header[7:].strip() != token:
            raise reverse_sync.ReverseSyncError("invalid bearer token", code="unauthorized", status_code=401)

    def do_OPTIONS(self) -> None:  # noqa: N802
        origin = self._origin_allowed()
        if not origin:
            self.send_response(HTTPStatus.FORBIDDEN)
            self.end_headers()
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Vary", "Origin")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/v1/task-board/status":
            self._write_json({"status": "not_found"}, status=404)
            return
        self._write_json(
            {
                "status": "ok",
                "bridge": "task-board-reverse-sync",
                "tokenConfigured": True,
                "metaTodoPath": str(getattr(self.server, "meta_todo_path")),
                "tasksJsonPath": str(getattr(self.server, "tasks_json_path")),
            }
        )

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/task-board/reverse-sync":
            self._write_json({"status": "not_found"}, status=404)
            return
        try:
            self._authorize()
            payload = self._read_json_body()
            task_id = str(payload.get("taskId") or "")
            desired_status = str(payload.get("desiredStatus") or "")
            expected_current_status = str(payload.get("expectedCurrentStatus") or "")
            if not task_id:
                raise reverse_sync.ReverseSyncError("taskId is required", code="task_id_required", status_code=400)
            result = reverse_sync.reverse_sync_task(
                task_id=task_id,
                desired_status=desired_status,
                expected_current_status=expected_current_status,
                meta_todo_path=getattr(self.server, "meta_todo_path"),
                tasks_json_path=getattr(self.server, "tasks_json_path"),
                backup_dir=getattr(self.server, "backup_dir"),
            )
            status_code = 200 if result.get("status") in {"ok", "noop"} else 202
            self._write_json(result, status=status_code)
        except reverse_sync.ReverseSyncError as exc:
            self._write_json(
                {"status": "error", "code": exc.code, "message": str(exc)},
                status=exc.status_code,
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--meta-todo", type=Path, default=reverse_sync.DEFAULT_META_TODO)
    parser.add_argument("--tasks-json", type=Path, default=reverse_sync.DEFAULT_TASKS_JSON)
    parser.add_argument("--backup-dir", type=Path, default=reverse_sync.DEFAULT_BACKUP_DIR)
    parser.add_argument("--token-path", type=Path, default=reverse_sync.DEFAULT_TOKEN_PATH)
    parser.add_argument("--rotate-token", action="store_true")
    args = parser.parse_args()

    sync_token = reverse_sync.load_or_create_token(args.token_path, rotate=args.rotate_token)
    server = ThreadingHTTPServer((args.host, args.port), ReverseSyncHandler)
    server.sync_token = sync_token
    server.meta_todo_path = args.meta_todo
    server.tasks_json_path = args.tasks_json
    server.backup_dir = args.backup_dir

    print(
        json.dumps(
            {
                "status": "listening",
                "host": args.host,
                "port": args.port,
                "meta_todo_path": str(args.meta_todo),
                "tasks_json_path": str(args.tasks_json),
                "token_path": str(args.token_path),
            },
            ensure_ascii=False,
        )
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
