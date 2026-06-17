from __future__ import annotations

import json
import sys
from typing import Callable

from flex_agent.coding.export import export_open_coding_result
from flex_agent.eval import evaluate_axial_workspace, evaluate_workspace
from flex_agent.config import (
    get_prompts_dir,
    get_workspace_dir,
    path_label,
)
from flex_agent.i18n import get_bundle, get_language
from flex_agent.models import DimensionDetail, SessionMeta
from flex_agent.workspace import Workspace

SlashHandler = Callable[[], str | None]


def format_codebook_tree(dimensions: list[DimensionDetail]) -> str:
    if not dimensions:
        return get_bundle().cli.no_codebook_data
    lines = ["Codebook"]
    for dimension in dimensions:
        desc = f" ({dimension.definition})" if dimension.definition else ""
        lines.append(f"  [{dimension.name}]{desc} · {len(dimension.items)} items")
        for item in dimension.items:
            lines.append(f"    - {item}")
    return "\n".join(lines)


def format_help() -> str:
    return get_bundle().cli.help_text


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
        return True, get_bundle().progress.export_result.format(path=path)
    if cmd == "/eval:open":
        cli_text = get_bundle().cli
        mode = parts[1].lower() if len(parts) > 1 and not parts[1].startswith("--") else "both"
        if mode not in {"keyword", "semantic", "both", "metrics"}:
            return True, cli_text.invalid_eval_mode.format(mode=mode)
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
            return True, cli_text.eval_failed.format(error=exc)
        return True, report
    if cmd == "/eval:axial":
        cli_text = get_bundle().cli
        mode = parts[1].lower() if len(parts) > 1 and not parts[1].startswith("--") else "both"
        if mode not in {"keyword", "semantic", "both", "metrics"}:
            return True, cli_text.invalid_eval_mode.format(mode=mode)
        align = "--align" in parts
        try:
            report = evaluate_axial_workspace(
                workspace,
                mode=mode,  # type: ignore[arg-type]
                align=align,
                on_progress=lambda msg: print(msg, file=sys.stderr, flush=True),
            )
        except RuntimeError as exc:
            return True, str(exc)
        except Exception as exc:
            return True, cli_text.axial_eval_failed.format(error=exc)
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
                language=get_language(),
            )
        )
        return True, get_bundle().cli.cleared_workspace
    return False, None
