from __future__ import annotations

import asyncio
import platform
import sys
from pathlib import Path
from time import strftime
from typing import Any

from langchain_core.messages import HumanMessage

from flex_agent.orchestration import create_flex_agent
from flex_agent.config import (
    PROJECT_ROOT,
    load_env_file,
    load_recursion_limit,
    merge_invoke_config,
    path_label,
    set_prompts_dir,
    set_workspace_dir,
    trace_invoke_config,
    warn_langsmith_tracing,
)
from flex_agent.debug_log import agent_debug_log, configure_debug_logging
from flex_agent.i18n import get_bundle, set_language
from flex_agent.models import SessionMeta
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


def _chunk_debug_summary(chunk: dict[str, Any]) -> dict[str, Any]:
    messages = chunk.get("messages", [])
    last = messages[-1] if messages else None
    tool_calls = getattr(last, "tool_calls", None) or []
    return {
        "message_count": len(messages) if isinstance(messages, list) else None,
        "last_message_type": last.__class__.__name__ if last is not None else None,
        "last_tool_calls": [
            {
                "name": str(call.get("name") or "unknown"),
                "id": str(call.get("id") or ""),
            }
            for call in tool_calls
            if isinstance(call, dict)
        ],
        "todos_count": len(chunk.get("todos") or []) if isinstance(chunk.get("todos"), list) else None,
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
        cli_text = get_bundle().cli
        label = cli_text.activity_labels.get(mode, cli_text.running)
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
    # region agent log
    agent_debug_log(
        hypothesis_id="H1,H2,H3,H4,H5",
        location="src/flex_agent/ui/plain_cli.py:_stream_agent_turn:start",
        message="agent turn start",
        data={
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "cwd": str(Path.cwd()),
            "workspace_root": str(workspace.root.resolve()),
            "recursion_limit": config.get("recursion_limit"),
            "thread_id": (config.get("configurable") or {}).get("thread_id")
            if isinstance(config.get("configurable"), dict)
            else None,
            "user_text_length": len(user_text),
            "watcher_enabled": watcher.enabled,
        },
    )
    # endregion

    async def _consume() -> None:
        chunk_index = 0
        async for chunk in agent.astream(inputs, config=config, stream_mode="values"):
            chunk_index += 1
            # region agent log
            agent_debug_log(
                hypothesis_id="H2,H3",
                location="src/flex_agent/ui/plain_cli.py:_stream_agent_turn:chunk",
                message="graph stream chunk",
                data={
                    "chunk_index": chunk_index,
                    **_chunk_debug_summary(chunk),
                },
            )
            # endregion
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
        cli_text = get_bundle().cli
        update = parser.mark_interrupted()
        renderer.render_update(update, parser=parser, workspace=workspace)
        for step in update.steps.values():
            if step.status == StepStatus.ERROR and step.result_preview == "interrupted":
                renderer.render_step(step)
        print(style(cli_text.interrupted, TermStyle.YELLOW), flush=True)
        renderer.render_workspace_status(workspace)
        return False

    final = parser.flush_assistant_text()
    renderer.render_update(final, parser=parser, workspace=workspace)
    renderer.render_workspace_status(workspace)
    return True


async def run_plain_cli(
    *,
    workspace_spec: str = "baseline",
    prompts_dir_spec: str | None = None,
    language_spec: str | None = None,
    debug: bool = False,
) -> int:
    load_env_file(PROJECT_ROOT / ".env")
    log_path = configure_debug_logging(enabled=debug)
    warn_langsmith_tracing()
    active_language = set_language(language_spec)
    prompts_dir = set_prompts_dir(prompts_dir_spec, language=active_language)
    workspace_dir = set_workspace_dir(workspace_spec)
    cli_text = get_bundle(active_language).cli
    workspace = Workspace(workspace_dir)
    workspace.ensure_layout()
    workspace.bootstrap_seed_files()
    workspace.save_session_meta(
        SessionMeta(
            prompts_dir=path_label(prompts_dir),
            workspace_dir=path_label(workspace_dir),
            prompts_resolved=str(prompts_dir.resolve()),
            workspace_resolved=str(workspace.root.resolve()),
            language=active_language,
        )
    )
    agent = create_flex_agent(workspace, prompts_dir=prompts_dir, language=active_language)
    parser = StreamEventParser()
    renderer = PlainCliRenderer()

    thread_id = f"flex_agent_{strftime('%Y%m%d_%H%M%S')}"
    config = merge_invoke_config(
        {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": load_recursion_limit(),
        },
        trace_invoke_config("orchestrator"),
    )

    renderer.render_banner(workspace)
    if debug:
        print(f"Debug logging enabled: {log_path}", file=sys.stderr, flush=True)

    while True:
        try:
            prompt = style("> ", TermStyle.BOLD, TermStyle.CYAN) if use_color() else "> "
            user_text = input(f"\n{prompt}").strip()
        except KeyboardInterrupt:
            print(flush=True)
            continue
        except EOFError:
            print(f"\n{cli_text.bye}", flush=True)
            return 0

        if not user_text:
            continue
        if user_text.lower() in {"exit", "quit", "/exit", "/quit"}:
            print(cli_text.bye, flush=True)
            return 0

        handled, output = handle_slash_command(workspace, user_text)
        if handled:
            if output:
                cmd = user_text.strip().lower().split()[0]
                if cmd == "/status":
                    renderer.render_workspace_status(workspace)
                    print(output, flush=True)
                elif cmd in {"/help", "/eval:open", "/eval:axial"}:
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
            print(style(f"\n{cli_text.interrupted}", TermStyle.YELLOW), flush=True)
            renderer.render_workspace_status(workspace)
        except Exception as exc:
            update = parser.mark_error(exc)
            # region agent log
            agent_debug_log(
                hypothesis_id="H2,H3,H4",
                location="src/flex_agent/ui/plain_cli.py:run_plain_cli:error",
                message="agent turn error",
                data={
                    "error_type": type(exc).__name__,
                    "error": repr(exc),
                    "running_steps": [
                        {"tool_name": step.tool_name, "summary": step.summary}
                        for step in parser.steps.values()
                        if step.status == StepStatus.RUNNING
                    ],
                },
            )
            # endregion
            renderer.render_update(update, parser=parser, workspace=workspace)
            for step in update.steps.values():
                if step.status == StepStatus.ERROR:
                    renderer.render_step(step)

    return 0
