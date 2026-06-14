from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from time import strftime
from typing import Any

from langchain_core.messages import HumanMessage

from flex_agent.orchestration import create_flex_agent
from flex_agent.config import DEFAULT_WORKSPACE, PROJECT_ROOT, load_env_file
from flex_agent.ui.events import (
    StreamEventParser,
    StepStatus,
    TimelineEntry,
    UIUpdate,
)
from flex_agent.ui.helpers import handle_slash_command
from flex_agent.ui.interrupt import EscInterruptWatcher
from flex_agent.ui.renderer import PlainCliRenderer, style, TermStyle, use_color
from flex_agent.workspace import Workspace

SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

ACTIVITY_LABELS = {
    "thinking": "Agent 思考中",
    "tool": "执行工具",
    "streaming": "生成回复",
}


def _clear_stderr_line() -> None:
    if use_color():
        print("\r\033[K", end="", file=sys.stderr, flush=True)


def _system_update(text: str, *, refresh_workspace: bool = False) -> UIUpdate:
    return UIUpdate(
        timeline=[TimelineEntry(kind="system", text=text)],
        refresh_workspace=refresh_workspace,
    )


async def _activity_spinner(stop_event: asyncio.Event, mode_holder: list[str]) -> None:
    frame_index = 0
    while not stop_event.is_set():
        mode = mode_holder[0]
        label = ACTIVITY_LABELS.get(mode, "运行中")
        frame = SPINNER_FRAMES[frame_index % len(SPINNER_FRAMES)]
        frame_index += 1
        if use_color():
            print(
                f"\r{TermStyle.GRAY}{frame} {label}...{TermStyle.RESET}",
                end="",
                file=sys.stderr,
                flush=True,
            )
        else:
            print(f"\r{frame} {label}...", end="", file=sys.stderr, flush=True)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=0.12)
        except TimeoutError:
            continue
    _clear_stderr_line()


async def _stream_agent_turn(
    agent,
    user_text: str,
    config: dict[str, Any],
    parser: StreamEventParser,
    workspace: Workspace,
    renderer: PlainCliRenderer,
) -> bool:
    """Run one agent turn. Returns False if interrupted."""
    stop_event = asyncio.Event()
    activity_mode = ["thinking"]
    spinner = asyncio.create_task(_activity_spinner(stop_event, activity_mode))
    inputs = {"messages": [HumanMessage(content=user_text)]}
    watcher = EscInterruptWatcher()
    watcher.start()
    renderer.reset_turn_state()

    async def _consume() -> None:
        async for chunk in agent.astream(inputs, config=config, stream_mode="values"):
            update = parser.consume(chunk)
            if update.activity_mode:
                activity_mode[0] = update.activity_mode
            renderer.render_update(update, parser=parser, workspace=workspace)

    consume_task = asyncio.create_task(_consume())
    interrupted = False

    try:
        if watcher.enabled:
            interrupt_task = asyncio.create_task(watcher.wait())
            done, _pending = await asyncio.wait(
                {consume_task, interrupt_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if interrupt_task in done:
                interrupted = True
                consume_task.cancel()
                try:
                    await consume_task
                except asyncio.CancelledError:
                    pass
            else:
                interrupt_task.cancel()
                try:
                    await interrupt_task
                except asyncio.CancelledError:
                    pass
                await consume_task
        else:
            await consume_task
    except asyncio.CancelledError:
        interrupted = True
        consume_task.cancel()
        try:
            await consume_task
        except asyncio.CancelledError:
            pass
        raise
    finally:
        watcher.stop()
        stop_event.set()
        await spinner

    if interrupted:
        update = parser.mark_interrupted()
        renderer.render_update(update, parser=parser, workspace=workspace)
        for step in update.steps.values():
            if step.status == StepStatus.ERROR and step.result_preview == "interrupted":
                renderer.render_step(step)
        print(style("已中断，可继续输入新指令", TermStyle.YELLOW), flush=True)
        renderer.render_workspace_status(workspace)
        return False

    final = parser.flush_assistant_text()
    renderer.render_update(final, parser=parser, workspace=workspace)
    renderer.render_workspace_status(workspace)
    return True


async def run_plain_cli(
    *,
    workspace_path: str | Path = DEFAULT_WORKSPACE,
) -> int:
    load_env_file(PROJECT_ROOT / ".env")
    workspace = Workspace(Path(workspace_path))
    workspace.ensure_layout()
    agent = create_flex_agent(workspace)
    parser = StreamEventParser()
    renderer = PlainCliRenderer()

    thread_id = f"flex_agent_{strftime('%Y%m%d_%H%M%S')}"
    config = {"configurable": {"thread_id": thread_id}}

    renderer.render_banner(workspace)

    while True:
        try:
            prompt = style("> ", TermStyle.BOLD, TermStyle.CYAN) if use_color() else "> "
            user_text = input(f"\n{prompt}").strip()
        except KeyboardInterrupt:
            print(flush=True)
            continue
        except EOFError:
            print("\nbye", flush=True)
            return 0

        if not user_text:
            continue
        if user_text.lower() in {"exit", "quit", "/exit", "/quit"}:
            print("bye", flush=True)
            return 0

        handled, output = handle_slash_command(workspace, user_text)
        if handled:
            if output:
                cmd = user_text.strip().lower()
                if cmd == "/status":
                    renderer.render_workspace_status(workspace)
                    print(output, flush=True)
                elif cmd == "/help":
                    print(output, flush=True)
                elif cmd == "/clear":
                    renderer.render_update(
                        _system_update(output, refresh_workspace=True),
                        parser=parser,
                        workspace=workspace,
                    )
                else:
                    renderer.render_update(
                        _system_update(output),
                        parser=parser,
                        workspace=workspace,
                    )
            continue

        try:
            parser.note_user_message(user_text, emit=False)
            await _stream_agent_turn(agent, user_text, config, parser, workspace, renderer)
        except KeyboardInterrupt:
            _clear_stderr_line()
            update = parser.mark_interrupted()
            renderer.render_update(update, parser=parser, workspace=workspace)
            print(style("\n已中断，可继续输入新指令", TermStyle.YELLOW), flush=True)
            renderer.render_workspace_status(workspace)
        except Exception as exc:
            update = parser.mark_error(exc)
            renderer.render_update(update, parser=parser, workspace=workspace)
            for step in update.steps.values():
                if step.status == StepStatus.ERROR:
                    renderer.render_step(step)

    return 0
