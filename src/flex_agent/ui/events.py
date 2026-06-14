from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from flex_agent.ui.labels import summarize_tool_args, tool_label


class StepStatus(str, Enum):
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


@dataclass
class TodoItem:
    content: str
    status: Literal["pending", "in_progress", "completed"] = "pending"


@dataclass
class TimelineEntry:
    kind: Literal["user", "assistant", "step", "system", "error"]
    text: str
    step_id: str | None = None


@dataclass
class StepRecord:
    step_id: str
    tool_name: str
    label: str
    summary: str
    status: StepStatus = StepStatus.RUNNING
    result_preview: str = ""


@dataclass
class UIUpdate:
    timeline: list[TimelineEntry] = field(default_factory=list)
    steps: dict[str, StepRecord] = field(default_factory=dict)
    todos: list[TodoItem] = field(default_factory=list)
    refresh_workspace: bool = False
    streaming_assistant: str | None = None
    activity_mode: Literal["idle", "thinking", "streaming", "tool"] | None = None


def _message_key(message: BaseMessage, index: int) -> str:
    message_id = getattr(message, "id", None)
    if message_id:
        return str(message_id)
    return f"{message.__class__.__name__}:{index}:{id(message)}"


def _extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if text:
                    parts.append(str(text))
        return "".join(parts).strip()
    if content is None:
        return ""
    return str(content).strip()


class StreamEventParser:
    """Diff LangGraph value chunks into UI-friendly updates."""

    def __init__(self) -> None:
        self.seen_message_keys: set[str] = set()
        self.emitted_user_texts: set[str] = set()
        self.emitted_assistant_texts: set[str] = set()
        self.ai_text_by_key: dict[str, str] = {}
        self.steps: dict[str, StepRecord] = {}
        self.timeline: list[TimelineEntry] = []
        self.todos: list[TodoItem] = []
        self.pending_assistant_text: str = ""

    def note_user_message(self, text: str, *, emit: bool = True) -> UIUpdate:
        cleaned = text.strip()
        if not cleaned or cleaned in self.emitted_user_texts:
            return UIUpdate()
        self.emitted_user_texts.add(cleaned)
        if not emit:
            return UIUpdate()
        entry = TimelineEntry(kind="user", text=cleaned)
        self.timeline.append(entry)
        return UIUpdate(timeline=[entry])

    def flush_assistant_text(self) -> UIUpdate:
        text = self.pending_assistant_text.strip()
        if not text or text in self.emitted_assistant_texts:
            self.pending_assistant_text = ""
            return UIUpdate(streaming_assistant="", activity_mode="idle")
        self.emitted_assistant_texts.add(text)
        entry = TimelineEntry(kind="assistant", text=text)
        self.timeline.append(entry)
        self.pending_assistant_text = ""
        return UIUpdate(
            timeline=[entry],
            streaming_assistant="",
            activity_mode="idle",
        )

    def consume(self, chunk: dict[str, Any]) -> UIUpdate:
        update = UIUpdate(steps=dict(self.steps), todos=list(self.todos))
        messages = chunk.get("messages", [])
        for index, message in enumerate(messages):
            if isinstance(message, AIMessage):
                self._consume_ai_message(message, index, update)
                continue

            key = _message_key(message, index)
            if key in self.seen_message_keys:
                continue
            self.seen_message_keys.add(key)
            self._consume_message(message, update)

        raw_todos = chunk.get("todos")
        if isinstance(raw_todos, list):
            next_todos = [
                TodoItem(
                    content=str(item.get("content", "")),
                    status=item.get("status", "pending"),
                )
                for item in raw_todos
                if isinstance(item, dict) and item.get("content")
            ]
            next_key = tuple((item.content, item.status) for item in next_todos)
            prev_key = tuple((item.content, item.status) for item in self.todos)
            self.todos = next_todos
            if next_key != prev_key:
                update.todos = list(self.todos)

        update.steps = dict(self.steps)
        return update

    def mark_error(self, exc: BaseException) -> UIUpdate:
        flushed = self.flush_assistant_text()
        entry = TimelineEntry(kind="error", text=repr(exc))
        self.timeline.append(entry)
        flushed.timeline.append(entry)
        for step in self.steps.values():
            if step.status == StepStatus.RUNNING:
                step.status = StepStatus.ERROR
                step.result_preview = repr(exc)
        flushed.steps = dict(self.steps)
        flushed.todos = list(self.todos)
        flushed.activity_mode = "idle"
        flushed.streaming_assistant = ""
        return flushed

    def mark_interrupted(self) -> UIUpdate:
        self.pending_assistant_text = ""
        for step in self.steps.values():
            if step.status == StepStatus.RUNNING:
                step.status = StepStatus.ERROR
                step.result_preview = "interrupted"
        return UIUpdate(
            steps=dict(self.steps),
            todos=list(self.todos),
            activity_mode="idle",
            streaming_assistant="",
        )

    def _consume_ai_message(
        self,
        message: AIMessage,
        index: int,
        update: UIUpdate,
    ) -> None:
        ai_key = _message_key(message, index)
        text = _extract_text_content(message.content)
        if text and text != self.ai_text_by_key.get(ai_key, ""):
            self.ai_text_by_key[ai_key] = text
            self.pending_assistant_text = text
            update.streaming_assistant = text
            update.activity_mode = "streaming"

        if message.tool_calls:
            flushed = self.flush_assistant_text()
            if flushed.timeline:
                update.timeline.extend(flushed.timeline)
            if flushed.streaming_assistant == "":
                update.streaming_assistant = ""
            update.activity_mode = "tool"

            for call in message.tool_calls:
                tool_name = str(call.get("name") or "unknown")
                tool_call_id = str(call.get("id") or f"{tool_name}:{len(self.steps)}")
                if tool_call_id in self.steps and self.steps[tool_call_id].status == StepStatus.RUNNING:
                    continue
                args = call.get("args") or {}
                label = tool_label(tool_name)
                summary = summarize_tool_args(tool_name, args)
                step = StepRecord(
                    step_id=tool_call_id,
                    tool_name=tool_name,
                    label=label,
                    summary=summary,
                    status=StepStatus.RUNNING,
                )
                self.steps[tool_call_id] = step
                line = _format_step_line(step)
                entry = TimelineEntry(kind="step", text=line, step_id=tool_call_id)
                self.timeline.append(entry)
                update.timeline.append(entry)

    def _consume_message(self, message: BaseMessage, update: UIUpdate) -> None:
        if isinstance(message, HumanMessage):
            text = _extract_text_content(message.content)
            if text and text not in self.emitted_user_texts:
                self.emitted_user_texts.add(text)
                entry = TimelineEntry(kind="user", text=text)
                self.timeline.append(entry)
                update.timeline.append(entry)
            return

        if isinstance(message, ToolMessage):
            tool_call_id = str(message.tool_call_id)
            preview = _extract_text_content(message.content)
            if len(preview) > 400:
                preview = preview[:400] + "..."

            step = self.steps.get(tool_call_id)
            if step is None:
                tool_name = str(getattr(message, "name", "") or "tool")
                step = StepRecord(
                    step_id=tool_call_id,
                    tool_name=tool_name,
                    label=tool_label(tool_name),
                    summary="",
                    status=StepStatus.DONE,
                    result_preview=preview,
                )
                self.steps[tool_call_id] = step
            else:
                if step.status == StepStatus.DONE:
                    return
                step.status = StepStatus.DONE
                step.result_preview = preview

            line = _format_step_line(step)
            if preview:
                line = f"{line}\n  └ {preview}"
            entry = TimelineEntry(kind="step", text=line, step_id=tool_call_id)
            self.timeline.append(entry)
            update.timeline.append(entry)
            update.refresh_workspace = True
            update.activity_mode = "thinking"


def _format_step_line(step: StepRecord, spinner: str = "") -> str:
    icon = {
        StepStatus.RUNNING: spinner or "⠋",
        StepStatus.DONE: "✓",
        StepStatus.ERROR: "✗",
    }[step.status]
    summary = f" {step.summary}" if step.summary else ""
    return f"{icon} {step.label}{summary}"


def format_step_line(step: StepRecord, spinner: str = "") -> str:
    return _format_step_line(step, spinner=spinner)


def todo_icon(status: str) -> str:
    return {
        "pending": "○",
        "in_progress": "●",
        "completed": "✓",
    }.get(status, "○")
