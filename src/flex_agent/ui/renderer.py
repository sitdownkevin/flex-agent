from __future__ import annotations

import os
import shutil
import sys
from typing import Any

from flex_agent.i18n import get_bundle
from flex_agent.ui.events import (
    StepRecord,
    StepStatus,
    StreamEventParser,
    TimelineEntry,
    TodoItem,
    UIUpdate,
    todo_icon,
)
from flex_agent.workspace import Workspace


class TermStyle:
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    GRAY = "\033[90m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    CLEAR_LINE = "\033[K"
    CURSOR_UP = "\033[A"


def use_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def style(text: str, *codes: str) -> str:
    if not use_color() or not codes:
        return text
    return "".join(codes) + text + TermStyle.RESET


def terminal_width(*, default: int = 80) -> int:
    try:
        return shutil.get_terminal_size(fallback=(default, 24)).columns
    except OSError:
        return default


class PlainCliRenderer:
    """Incremental TUI renderer: stream text, replace step lines, dedupe status."""

    def __init__(self) -> None:
        self._rendered_step_ids: set[str] = set()
        self._step_line_counts: dict[str, int] = {}
        self._last_todos_key: tuple[tuple[str, str], ...] | None = None
        self._last_workspace_summary: str | None = None
        self._streaming_active = False

    def render_banner(self, workspace: Workspace) -> None:
        cli_text = get_bundle().cli
        title = style("flex-agent", TermStyle.BOLD)
        summary = self._workspace_summary(workspace)
        self._last_workspace_summary = summary
        self._print_line(f"{title}  workspace={workspace.root}")
        self._print_line(style(summary, TermStyle.GRAY))
        self._print_line(style(cli_text.banner_hint, TermStyle.GRAY))

    def render_update(
        self,
        update: UIUpdate,
        *,
        parser: StreamEventParser,
        workspace: Workspace,
    ) -> None:
        self._clear_streaming_line()
        for entry in update.timeline:
            self._render_timeline_entry(entry, update.steps)
        if update.streaming_assistant:
            self._render_streaming(update.streaming_assistant)
        if update.todos and self._todos_changed(update.todos):
            self._render_todos(update.todos)
        if update.refresh_workspace:
            self.render_workspace_status(workspace)

    def render_workspace_status(self, workspace: Workspace) -> None:
        try:
            summary = self._workspace_summary(workspace)
        except Exception as exc:
            text = get_bundle().cli.status_unavailable.format(error=exc)
            self._print_line(style(text, TermStyle.YELLOW))
            return
        if summary == self._last_workspace_summary:
            return
        self._last_workspace_summary = summary
        prefix = get_bundle().cli.workspace_prefix
        self._print_line(style(f"{prefix} · {summary}", TermStyle.GRAY))

    def reset_turn_state(self) -> None:
        self._clear_streaming_line()

    def _workspace_summary(self, workspace: Workspace) -> str:
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

    def _todos_changed(self, todos: list[TodoItem]) -> bool:
        key = tuple((item.content, item.status) for item in todos)
        if key == self._last_todos_key:
            return False
        self._last_todos_key = key
        return True

    def _render_timeline_entry(
        self,
        entry: TimelineEntry,
        steps: dict[str, StepRecord],
    ) -> None:
        if entry.kind == "user":
            self._print_line(style(f"> {entry.text}", TermStyle.BOLD, TermStyle.CYAN))
            return
        if entry.kind == "assistant":
            self._print_line(entry.text)
            return
        if entry.kind == "system":
            self._print_line(style(entry.text, TermStyle.GRAY))
            return
        if entry.kind == "error":
            self._print_line(style(f"error: {entry.text}", TermStyle.YELLOW), file=sys.stderr)
            return
        if entry.kind == "step":
            step = steps.get(entry.step_id) if entry.step_id else None
            if step is not None:
                self._render_step(step)
            else:
                self._print_line(entry.text)
            return
        self._print_line(entry.text)

    def render_step(self, step: StepRecord) -> None:
        self._render_step(step)

    def _render_step(self, step: StepRecord) -> None:
        step_id = step.step_id
        if step_id in self._rendered_step_ids:
            self._erase_step_lines(step_id)

        lines = self._format_step_lines(step)
        for line in lines:
            self._print_line(line)

        self._rendered_step_ids.add(step_id)
        self._step_line_counts[step_id] = len(lines)

    def _format_step_lines(self, step: StepRecord) -> list[str]:
        icon = {
            StepStatus.RUNNING: "◐",
            StepStatus.DONE: "✓",
            StepStatus.ERROR: "✗",
        }[step.status]
        summary = f" {step.summary}" if step.summary else ""
        label = f"{icon} {step.label}{summary}"

        if step.status == StepStatus.RUNNING:
            label = style(label, TermStyle.YELLOW)
        elif step.status == StepStatus.DONE:
            label = style(label, TermStyle.GREEN)
        elif step.status == StepStatus.ERROR:
            label = style(label, TermStyle.RED)

        lines = [label]
        preview = step.result_preview.strip()
        if preview and step.status in {StepStatus.DONE, StepStatus.ERROR}:
            preview_line = f"  └ {preview}"
            tone = TermStyle.GRAY if step.status == StepStatus.DONE else TermStyle.YELLOW
            lines.append(style(preview_line, tone))
        return lines

    def _erase_step_lines(self, step_id: str) -> None:
        line_count = self._step_line_counts.get(step_id, 1)
        for _ in range(line_count):
            sys.stdout.write(f"{TermStyle.CURSOR_UP}{TermStyle.CLEAR_LINE}")
        sys.stdout.flush()
        self._rendered_step_ids.discard(step_id)
        self._step_line_counts.pop(step_id, None)

    def _render_todos(self, todos: list[TodoItem]) -> None:
        if not todos:
            return
        self._print_line()
        self._print_line(style(get_bundle().cli.plan_title, TermStyle.BOLD, TermStyle.MAGENTA))
        for item in todos:
            icon = todo_icon(item.status)
            line = f"  {icon} {item.content}"
            if item.status == "in_progress":
                self._print_line(style(line, TermStyle.YELLOW))
            elif item.status == "completed":
                self._print_line(style(line, TermStyle.GREEN))
            else:
                self._print_line(style(line, TermStyle.GRAY))

    def _render_streaming(self, text: str) -> None:
        if not text:
            self._clear_streaming_line()
            return
        width = max(terminal_width() - 1, 20)
        visible = text
        if len(visible) > width:
            visible = "…" + visible[-(width - 1) :]
        if not self._streaming_active:
            sys.stdout.write("\n")
        sys.stdout.write(f"\r{TermStyle.CLEAR_LINE}{visible}")
        sys.stdout.flush()
        self._streaming_active = True

    def _clear_streaming_line(self) -> None:
        if not self._streaming_active:
            return
        sys.stdout.write(f"\r{TermStyle.CLEAR_LINE}")
        sys.stdout.flush()
        self._streaming_active = False

    @staticmethod
    def _print_line(text: str = "", *, file: Any = sys.stdout) -> None:
        print(text, flush=True, file=file)
