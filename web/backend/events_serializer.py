from __future__ import annotations

from typing import Any

from flex_agent.i18n import get_bundle
from flex_agent.ui.events import (
    StepRecord,
    StepStatus,
    TimelineEntry,
    TodoItem,
    UIUpdate,
)
from flex_agent.workspace import Workspace


def workspace_summary(workspace: Workspace) -> str:
    status = workspace.status()
    parts = [
        f"texts={status.get('texts_total', 0)}",
        f"coded={status.get('coded_count', 0)}",
        f"queue={status.get('queue_remaining', 0)}",
        f"dimensions={status.get('dimensions_count', 0)}",
    ]
    run = status.get("run")
    if run and run.get("max_nums") is not None:
        parts.append(f"max={run['max_nums']}")
    return " · ".join(parts)


def i18n_payload(language: str | None = None) -> dict[str, Any]:
    bundle = get_bundle(language)
    cli = bundle.cli
    return {
        "banner_hint": cli.banner_hint,
        "plan_title": cli.plan_title,
        "workspace_prefix": cli.workspace_prefix,
        "activity_labels": dict(cli.activity_labels),
        "interrupted": cli.interrupted,
        "recursion_limit_reached": cli.recursion_limit_reached,
        "bye": cli.bye,
        "running": cli.running,
    }


def banner_payload(workspace: Workspace, language: str | None = None) -> dict[str, Any]:
    return {
        "title": "flex-agent",
        "workspace_root": str(workspace.root),
        "workspace_summary": workspace_summary(workspace),
        "i18n": i18n_payload(language),
    }


def _serialize_timeline_entry(entry: TimelineEntry) -> dict[str, Any]:
    return {
        "kind": entry.kind,
        "text": entry.text,
        "step_id": entry.step_id,
    }


def _serialize_step(step: StepRecord) -> dict[str, Any]:
    return {
        "step_id": step.step_id,
        "tool_name": step.tool_name,
        "label": step.label,
        "summary": step.summary,
        "status": step.status.value,
        "result_preview": step.result_preview,
    }


def _serialize_todo(item: TodoItem) -> dict[str, Any]:
    return {
        "content": item.content,
        "status": item.status,
    }


def serialize_ui_update(
    update: UIUpdate,
    *,
    workspace: Workspace | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "update",
        "timeline": [_serialize_timeline_entry(e) for e in update.timeline],
        "steps": {k: _serialize_step(v) for k, v in update.steps.items()},
        "todos": [_serialize_todo(t) for t in update.todos],
        "streaming_assistant": update.streaming_assistant,
        "activity_mode": update.activity_mode,
    }
    if update.refresh_workspace and workspace is not None:
        bundle = get_bundle(language)
        payload["workspace_summary"] = workspace_summary(workspace)
        payload["workspace_prefix"] = bundle.cli.workspace_prefix
    return payload


def serialize_system_message(text: str) -> dict[str, Any]:
    return {
        "type": "update",
        "timeline": [{"kind": "system", "text": text, "step_id": None}],
        "steps": {},
        "todos": [],
        "streaming_assistant": None,
        "activity_mode": "idle",
    }


def serialize_progress_message(text: str) -> dict[str, Any]:
    return {
        "type": "update",
        "timeline": [{"kind": "progress", "text": text, "step_id": None}],
        "steps": {},
        "todos": [],
        "streaming_assistant": None,
        "activity_mode": None,
    }


def serialize_user_echo(text: str) -> dict[str, Any]:
    return {
        "type": "update",
        "timeline": [{"kind": "user", "text": text, "step_id": None}],
        "steps": {},
        "todos": [],
        "streaming_assistant": None,
        "activity_mode": None,
    }


def serialize_error_message(text: str) -> dict[str, Any]:
    return {
        "type": "update",
        "timeline": [{"kind": "error", "text": text, "step_id": None}],
        "steps": {},
        "todos": [],
        "streaming_assistant": "",
        "activity_mode": "idle",
    }


def serialize_idle() -> dict[str, Any]:
    return {
        "type": "update",
        "timeline": [],
        "steps": {},
        "todos": [],
        "streaming_assistant": "",
        "activity_mode": "idle",
    }


def serialize_banner_event(workspace: Workspace, language: str | None = None) -> dict[str, Any]:
    return {
        "type": "banner",
        **banner_payload(workspace, language),
    }


def serialize_step_status(step: StepRecord) -> dict[str, Any]:
    return {
        "type": "step_refresh",
        "step": _serialize_step(step),
    }
