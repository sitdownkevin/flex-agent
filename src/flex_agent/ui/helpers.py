from __future__ import annotations

import json
from typing import Callable

from flex_agent.coding.export import export_open_coding_result
from flex_agent.models import DimensionDetail
from flex_agent.workspace import Workspace

SlashHandler = Callable[[], str | None]


def format_codebook_tree(dimensions: list[DimensionDetail]) -> str:
    if not dimensions:
        return "暂无 codebook 数据"
    lines = ["Codebook"]
    for dimension in dimensions:
        desc = f" ({dimension.definition})" if dimension.definition else ""
        lines.append(f"  [{dimension.name}]{desc} · {len(dimension.items)} items")
        for item in dimension.items:
            lines.append(f"    - {item}")
    return "\n".join(lines)


def format_help() -> str:
    return "\n".join(
        [
            "Slash commands:",
            "  /status  - show workspace counters",
            "  /tree    - print codebook tree",
            "  /export  - export open coding JSON",
            "  /clear   - remove coding/codebook/meta/quality/exports (keep corpus/)",
            "  /help    - show this help",
            "  Esc      - interrupt the current agent turn",
            "  exit     - quit",
        ]
    )


def handle_slash_command(workspace: Workspace, command: str) -> tuple[bool, str | None]:
    cmd = command.strip().lower()
    if cmd in {"/help", "help"}:
        return True, format_help()
    if cmd == "/status":
        return True, json.dumps(workspace.status(), ensure_ascii=False, indent=2)
    if cmd == "/tree":
        return True, format_codebook_tree(workspace.load_dimensions())
    if cmd == "/export":
        path = export_open_coding_result(workspace)
        return True, f"Exported to {path}"
    if cmd == "/clear":
        workspace.clear_artifacts()
        return True, "Cleared workspace (corpus/ preserved)."
    return False, None
