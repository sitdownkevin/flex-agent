from __future__ import annotations

import json
from typing import Any

from flex_agent.i18n import get_bundle

TOOL_LABELS: dict[str, str] = dict(get_bundle("zh").cli.tool_labels)


def tool_label(name: str) -> str:
    return get_bundle().cli.tool_labels.get(name, name)


def summarize_tool_args(name: str, args: Any) -> str:
    if not isinstance(args, dict):
        if args in (None, "", {}):
            return ""
        return str(args)

    if name == "task":
        subagent = args.get("subagent_type") or args.get("name") or args.get("agent")
        description = args.get("description") or args.get("prompt") or args.get("task")
        parts = [part for part in (subagent, _short_text(description)) if part]
        return " → ".join(parts) if parts else json.dumps(args, ensure_ascii=False)

    if name in {"read_file", "write_file", "edit_file"}:
        path = args.get("file_path") or args.get("path") or args.get("target_file")
        return str(path) if path else _compact_json(args)

    if name == "write_todos":
        todos = args.get("todos") or []
        return get_bundle().cli.todo_count.format(count=len(todos))

    if name == "batch_bob_code":
        ids = args.get("text_ids")
        if ids:
            return get_bundle().cli.text_count.format(count=len(ids))
        concurrency = args.get("concurrency_limit")
        return f"concurrency={concurrency}" if concurrency else ""

    if name == "init_open_coding_run":
        parts = []
        if args.get("data_path"):
            parts.append(str(args["data_path"]))
        if args.get("max_nums") is not None:
            parts.append(f"max={args['max_nums']}")
        return ", ".join(parts)

    return _compact_json(args)


def _short_text(value: Any, limit: int = 80) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _compact_json(args: dict[str, Any], limit: int = 120) -> str:
    payload = json.dumps(args, ensure_ascii=False)
    if len(payload) <= limit:
        return payload
    return payload[: limit - 3] + "..."
