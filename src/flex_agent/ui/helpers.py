from __future__ import annotations

import json
import sys
from typing import Callable

from flex_agent.coding.export import export_open_coding_result
from flex_agent.eval import evaluate_workspace
from flex_agent.config import (
    get_prompts_dir,
    get_workspace_dir,
    path_label,
)
from flex_agent.models import DimensionDetail, SessionMeta
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
            "  /status      - show workspace counters",
            "  /tree        - print codebook tree",
            "  /export      - export open coding JSON",
            "  /eval:open   - evaluate open coding vs human benchmark (default: both)",
            "  /eval:open keyword|semantic|both|metrics",
            "               metrics = re-aggregate CPR from eval/open/*.json (no LLM)",
            "  /clear       - remove coding/codebook/meta/quality/exports (keep corpus/ & private/)",
            "  /help        - show this help",
            "  Esc      - interrupt the current agent turn",
            "  exit     - quit",
        ]
    )


def handle_slash_command(workspace: Workspace, command: str) -> tuple[bool, str | None]:
    parts = command.strip().split()
    if not parts:
        return False, None
    cmd = parts[0].lower()
    if cmd in {"/help", "help"}:
        return True, format_help()
    if cmd == "/status":
        return True, json.dumps(workspace.status(), ensure_ascii=False, indent=2)
    if cmd == "/tree":
        return True, format_codebook_tree(workspace.load_dimensions())
    if cmd == "/export":
        path = export_open_coding_result(workspace)
        return True, f"Exported to {path}"
    if cmd == "/eval:open":
        mode = parts[1].lower() if len(parts) > 1 and not parts[1].startswith("--") else "both"
        if mode not in {"keyword", "semantic", "both", "metrics"}:
            return True, f"未知评测模式: {mode}（可选 keyword / semantic / both / metrics）"
        align = "--align" in parts
        try:
            report = evaluate_workspace(
                workspace,
                mode=mode,  # type: ignore[arg-type]
                align=align,
                on_progress=lambda msg: print(msg, file=sys.stderr, flush=True),
            )
        except RuntimeError as exc:
            return True, str(exc)
        except Exception as exc:
            return True, f"评测失败: {exc!r}"
        return True, report
    if cmd == "/clear":
        workspace.clear_artifacts()
        prompts_dir = get_prompts_dir()
        workspace_dir = get_workspace_dir()
        workspace.save_session_meta(
            SessionMeta(
                prompts_dir=path_label(prompts_dir),
                workspace_dir=path_label(workspace_dir),
                prompts_resolved=str(prompts_dir.resolve()),
                workspace_resolved=str(workspace.root.resolve()),
            )
        )
        return True, "Cleared workspace (corpus/ and private/ preserved)."
    return False, None
