#!/usr/bin/env python3
"""Generate the public task-board JSON from Hamada Obsidian Meta TODO."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path


DEFAULT_META_TODO = Path(
    os.environ.get(
        "METATODO_PATH",
        "/Users/michito/Library/Mobile Documents/iCloud~md~obsidian/Documents/"
        "Hamada_Obsidian/Meta TODO.md",
    )
)
DEFAULT_OUTPUT = Path(os.environ.get("TASK_BOARD_TASKS_JSON", Path(__file__).resolve().parents[1] / "site-public" / "tasks.json"))

CHECKBOX_RE = re.compile(
    r"^(?P<indent>\s*)[-*]\s+\[(?P<mark>[ xX])\]\s+(?P<body>.*?)(?:\s*<!--\s*mtodo:(?P<id>[^>\s]+)\s*-->)?\s*$"
)
HEADING_RE = re.compile(r"^(?P<level>#{2,3})\s+(?P<title>.+?)\s*$")


def clean_title(body: str) -> str:
    body = re.sub(r"\s*<!--.*?-->\s*", " ", body)
    body = re.sub(r"\s*Source PDF:\s*`[^`]+`", " ", body)
    body = re.sub(r"\s*Source:\s*[^（(]+(?:\d{4}-\d{2}-\d{2}[^）)]*)?", " ", body)
    body = re.sub(r"\s*[（(]メール:\s*[^）)]+[）)]", " ", body)
    body = re.sub(r"\s*id:[A-Za-z0-9_-]+", " ", body)
    body = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or Path(m.group(1)).name, body)
    body = re.sub(r"\s+", " ", body)
    return body.strip(" ;、。")


def clean_heading(title: str) -> str:
    title = re.sub(r"^\d+[.．、]\s*", "", title.strip())
    return title.strip(" ;、。")


def priority_for(title: str, status: str) -> str:
    if status == "done":
        return "C"
    urgent_patterns = (
        "至急",
        "重要",
        "今すぐ",
        "本日",
        "今日",
        "明日",
        "締切",
        "まで",
        "〆切",
        "要確認",
    )
    if any(pattern in title for pattern in urgent_patterns):
        return "A"
    date_like = re.search(r"(?:\d{1,2}/\d{1,2}|\d{4}-\d{2}-\d{2})", title)
    return "A" if date_like else "B"


def assignee_for(title: str) -> str:
    bot_patterns = (
        "整理",
        "リスト",
        "メールを書く",
        "依頼文を作る",
        "復旧要否確認",
        "定期見直し",
        "扱いを決める",
        "確認するメール",
    )
    return "Bot" if any(pattern in title for pattern in bot_patterns) else "Me"


def parse_meta_todo(path: Path) -> list[dict[str, str]]:
    tasks: list[dict[str, str | bool]] = []
    seen_ids: set[str] = set()
    current_category = "未分類"
    current_section = ""

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        heading = HEADING_RE.match(line)
        if heading:
            title = clean_heading(heading.group("title"))
            if heading.group("level") == "##":
                current_category = title or "未分類"
                current_section = ""
            else:
                current_section = title
            continue

        match = CHECKBOX_RE.match(line)
        if not match:
            continue

        title = clean_title(match.group("body"))
        if not title:
            continue

        status = "done" if match.group("mark").lower() == "x" else "todo"
        explicit_id = match.group("id")
        task_id = explicit_id or f"meta-todo-line-{line_number}"

        if explicit_id and task_id in seen_ids:
            raise ValueError(f"duplicate mtodo id on line {line_number}: {task_id}")
        if task_id in seen_ids:
            raise ValueError(f"duplicate generated task id on line {line_number}: {task_id}")

        seen_ids.add(task_id)
        tasks.append(
            {
                "id": task_id,
                "title": title,
                "status": status,
                "priority": priority_for(title, status),
                "assignee": assignee_for(title),
                "category": current_section or current_category,
                "parentCategory": current_category,
                "section": current_section,
                "syncable": bool(explicit_id),
            }
        )

    return tasks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--meta-todo", type=Path, default=DEFAULT_META_TODO)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    tasks = parse_meta_todo(args.meta_todo)
    args.output.write_text(
        json.dumps(tasks, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    done = sum(1 for task in tasks if task["status"] == "done")
    print(f"wrote {len(tasks)} tasks to {args.output} ({done} done)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
