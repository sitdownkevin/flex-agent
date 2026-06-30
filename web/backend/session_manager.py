from __future__ import annotations

import asyncio
import json
import random
import shutil
import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from time import strftime
from typing import Any

from flex_agent.config import (
    PROMPTS_ROOT,
    WORKSPACES_ROOT,
    load_recursion_limit,
    merge_invoke_config,
    path_label,
    resolve_workspace_dir,
    set_prompts_dir,
    set_workspace_dir,
    trace_invoke_config,
)
from flex_agent.i18n import Language, set_language
from flex_agent.models import SessionMeta
from flex_agent.orchestration import create_flex_agent
from flex_agent.orchestration.tools import create_coding_tool_context
from flex_agent.ui.events import StreamEventParser
from flex_agent.workspace import Workspace

from web.backend.env_runtime import (
    apply_workspace_env,
    clear_llm_cache,
    infer_prompt_set,
    load_env_json,
    restore_env,
    save_env_json,
    task_background_path,
    validate_create_params,
    workspace_prompts_dir,
)
from web.backend.events_serializer import (
    banner_payload,
    serialize_progress_message,
    workspace_summary,
)

SendFn = Callable[[dict[str, Any]], Awaitable[None]]


agent_turn_lock = asyncio.Lock()
_runtime_build_lock = threading.Lock()


def _generate_session_id() -> str:
    suffix = f"{random.randint(0, 999999):06d}"
    return f"sess_{strftime('%Y%m%d_%H%M%S')}_{suffix}"


def _is_valid_session_id(session_id: str) -> bool:
    if not session_id or ".." in session_id or "/" in session_id or "\\" in session_id:
        return False
    return True


def _language_for_prompt_set(prompt_set: str, language: str | None = None) -> Language:
    if language in {"zh", "en"}:
        return language  # type: ignore[return-value]
    return "en" if prompt_set == "baseline_en" else "zh"


def _copy_prompt_set(workspace: Workspace, prompt_set: str) -> Path:
    source = (PROMPTS_ROOT / prompt_set).resolve()
    if not source.is_dir():
        raise ValueError(f"Prompt set not found: {prompt_set}")

    dest = workspace_prompts_dir(workspace)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest)
    (dest / ".prompt_set").write_text(prompt_set, encoding="utf-8")
    return dest


def _web_agent_json_path(workspace: Workspace) -> Path:
    return workspace.meta_dir / "web_agent.json"


def _migrate_legacy_thread_run_json(workspace: Workspace) -> None:
    """Move mistaken thread_id-only meta/run.json to meta/web_agent.json."""
    legacy = workspace.meta_dir / "run.json"
    if not legacy.exists():
        return
    try:
        data = json.loads(legacy.read_text(encoding="utf-8"))
        if not (isinstance(data, dict) and data.get("thread_id") and "data_path" not in data):
            return
        thread_id = str(data["thread_id"])
        if not _web_agent_json_path(workspace).exists():
            _save_thread_id(workspace, thread_id)
        legacy.unlink()
    except (json.JSONDecodeError, OSError, TypeError):
        return


def _load_thread_id(workspace: Workspace) -> str | None:
    _migrate_legacy_thread_run_json(workspace)
    path = _web_agent_json_path(workspace)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        thread_id = data.get("thread_id")
        return str(thread_id) if thread_id else None
    except (json.JSONDecodeError, OSError, TypeError):
        return None


def _save_thread_id(workspace: Workspace, thread_id: str) -> None:
    workspace.ensure_layout()
    _web_agent_json_path(workspace).write_text(
        json.dumps({"thread_id": thread_id}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class ProgressRelay:
    """Bridge synchronous tool progress callbacks to the WebSocket send coroutine."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._send: SendFn | None = None

    def bind(self, loop: asyncio.AbstractEventLoop, send: SendFn) -> None:
        self._loop = loop
        self._send = send

    def unbind(self) -> None:
        self._loop = None
        self._send = None

    def emit(self, message: str) -> None:
        loop = self._loop
        send = self._send
        if loop is None or send is None or loop.is_closed():
            return
        try:
            asyncio.run_coroutine_threadsafe(
                send(serialize_progress_message(message)),
                loop,
            )
        except RuntimeError:
            pass


@dataclass
class AgentRuntime:
    session_id: str
    workspace: Workspace
    language: Language
    prompts_dir: Path
    prompt_set: str
    env_mode: str
    agent: Any
    parser: StreamEventParser
    thread_id: str
    config: dict[str, Any]
    active_turn: asyncio.Task | None = field(default=None, repr=False)
    interrupt_event: asyncio.Event | None = field(default=None, repr=False)
    progress_relay: ProgressRelay = field(default_factory=ProgressRelay, repr=False)


@dataclass
class SessionSummary:
    id: str
    language: str
    created_at: str | None
    status_summary: str
    workspace_root: str
    env_mode: str
    prompt_set: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "language": self.language,
            "created_at": self.created_at,
            "status_summary": self.status_summary,
            "workspace_root": self.workspace_root,
            "env_mode": self.env_mode,
            "prompt_set": self.prompt_set,
        }


class SessionManager:
    def __init__(self) -> None:
        self._runtimes: dict[str, AgentRuntime] = {}

    def activate_session_globals(self, runtime: AgentRuntime) -> None:
        set_language(runtime.language)
        set_prompts_dir(runtime.prompts_dir, language=runtime.language)
        set_workspace_dir(runtime.workspace.root)

    def _session_metadata(self, workspace: Workspace) -> tuple[str, str]:
        env_json = load_env_json(workspace)
        meta = workspace.load_session_meta()
        prompt_set = infer_prompt_set(
            workspace,
            meta.prompts_dir if meta else None,
        )
        return str(env_json.get("mode", "env")), prompt_set

    def list_sessions(self) -> list[SessionSummary]:
        if not WORKSPACES_ROOT.exists():
            return []
        summaries: list[SessionSummary] = []
        for entry in sorted(WORKSPACES_ROOT.iterdir()):
            if not entry.is_dir():
                continue
            meta_path = entry / "meta" / "session.json"
            if not meta_path.exists():
                continue
            session_id = entry.name
            try:
                workspace = Workspace(entry)
                meta = workspace.load_session_meta()
                language = meta.language if meta else "zh"
                env_mode, prompt_set = self._session_metadata(workspace)
                created_at = datetime.fromtimestamp(meta_path.stat().st_mtime).isoformat()
                summaries.append(
                    SessionSummary(
                        id=session_id,
                        language=language,
                        created_at=created_at,
                        status_summary=workspace_summary(workspace),
                        workspace_root=str(workspace.root),
                        env_mode=env_mode,
                        prompt_set=prompt_set,
                    )
                )
            except Exception:
                continue
        summaries.sort(key=lambda item: item.created_at or "", reverse=True)
        return summaries

    def get_workspace(self, session_id: str) -> Workspace:
        if not _is_valid_session_id(session_id):
            raise ValueError(f"Invalid session id: {session_id!r}")
        root = resolve_workspace_dir(session_id)
        if not root.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")
        workspace = Workspace(root)
        _migrate_legacy_thread_run_json(workspace)
        return workspace

    def create_session(
        self,
        *,
        language: str = "zh",
        prompt_set: str = "baseline",
        mode: str = "env",
        overrides: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        cleaned_overrides = {
            k: str(v).strip()
            for k, v in (overrides or {}).items()
            if k and v and str(v).strip()
        }
        validate_create_params(
            prompt_set=prompt_set,
            mode=mode,
            overrides=cleaned_overrides,
        )

        session_id = _generate_session_id()
        while resolve_workspace_dir(session_id).exists():
            session_id = _generate_session_id()

        lang = _language_for_prompt_set(prompt_set, language)
        workspace_dir = resolve_workspace_dir(session_id)
        workspace = Workspace(workspace_dir)
        workspace.ensure_layout()
        workspace.bootstrap_seed_files()
        prompts_dir = _copy_prompt_set(workspace, prompt_set)

        env_json = {"mode": mode, "overrides": cleaned_overrides if mode == "byok" else {}}
        save_env_json(workspace, env_json)

        workspace.save_session_meta(
            SessionMeta(
                prompts_dir=path_label(prompts_dir),
                workspace_dir=path_label(workspace_dir),
                prompts_resolved=str(prompts_dir.resolve()),
                workspace_resolved=str(workspace.root.resolve()),
                language=lang,
            )
        )
        runtime = self._build_runtime(
            session_id,
            workspace,
            lang,
            prompts_dir,
            prompt_set=prompt_set,
            env_mode=mode,
        )
        self._runtimes[session_id] = runtime
        return self._session_payload(session_id, workspace, lang, mode, prompt_set)

    def get_session_info(self, session_id: str) -> dict[str, Any]:
        workspace = self.get_workspace(session_id)
        meta = workspace.load_session_meta()
        language = meta.language if meta else "zh"
        env_mode, prompt_set = self._session_metadata(workspace)
        payload = self._session_payload(session_id, workspace, language, env_mode, prompt_set)
        payload["meta"] = meta.model_dump() if meta else None
        return payload

    def _session_payload(
        self,
        session_id: str,
        workspace: Workspace,
        language: str,
        env_mode: str,
        prompt_set: str,
    ) -> dict[str, Any]:
        return {
            "id": session_id,
            "language": language,
            "env_mode": env_mode,
            "prompt_set": prompt_set,
            "banner": banner_payload(workspace, language),
            "status": workspace.status(),
        }

    def delete_session(self, session_id: str) -> None:
        self.invalidate_runtime(session_id)
        root = resolve_workspace_dir(session_id)
        if not root.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")
        shutil.rmtree(root)

    def invalidate_runtime(self, session_id: str) -> None:
        runtime = self._runtimes.pop(session_id, None)
        if runtime and runtime.active_turn and not runtime.active_turn.done():
            if runtime.interrupt_event:
                runtime.interrupt_event.set()
            runtime.active_turn.cancel()

    def get_or_create_runtime(self, session_id: str) -> AgentRuntime:
        if session_id in self._runtimes:
            return self._runtimes[session_id]

        workspace = self.get_workspace(session_id)
        meta = workspace.load_session_meta()
        if meta is None:
            raise FileNotFoundError(
                f"Session {session_id} has no meta/session.json; create a new session instead."
            )
        language = meta.language  # type: ignore[assignment]
        prompts_dir = Path(meta.prompts_resolved)
        env_mode, prompt_set = self._session_metadata(workspace)
        runtime = self._build_runtime(
            session_id,
            workspace,
            language,
            prompts_dir,
            prompt_set=prompt_set,
            env_mode=env_mode,
        )
        self._runtimes[session_id] = runtime
        return runtime

    def reset_runtime(self, session_id: str) -> AgentRuntime:
        self.invalidate_runtime(session_id)
        workspace = self.get_workspace(session_id)
        meta = workspace.load_session_meta()
        if meta is None:
            raise FileNotFoundError(f"Session not found: {session_id}")
        language = meta.language  # type: ignore[assignment]
        prompts_dir = Path(meta.prompts_resolved)
        env_mode, prompt_set = self._session_metadata(workspace)
        runtime = self._build_runtime(
            session_id,
            workspace,
            language,
            prompts_dir,
            prompt_set=prompt_set,
            env_mode=env_mode,
        )
        self._runtimes[session_id] = runtime
        return runtime

    def get_task_background(self, session_id: str) -> str:
        workspace = self.get_workspace(session_id)
        path = task_background_path(workspace)
        if not path.exists():
            raise FileNotFoundError("task_background.md not found in workspace prompts")
        return path.read_text(encoding="utf-8")

    def save_task_background(self, session_id: str, content: str) -> None:
        cleaned = content.strip()
        if not cleaned:
            raise ValueError("task_background.md must not be empty.")
        workspace = self.get_workspace(session_id)
        path = task_background_path(workspace)
        if not path.parent.exists():
            raise FileNotFoundError("Workspace prompts directory not found.")
        path.write_text(content, encoding="utf-8")
        self.reset_runtime(session_id)

    def _build_runtime(
        self,
        session_id: str,
        workspace: Workspace,
        language: Language,
        prompts_dir: Path,
        *,
        prompt_set: str,
        env_mode: str,
    ) -> AgentRuntime:
        env_json = load_env_json(workspace)
        progress_relay = ProgressRelay()
        with _runtime_build_lock:
            snapshot = apply_workspace_env(env_json)
            try:
                clear_llm_cache()
                self.activate_session_globals_for(language, prompts_dir, workspace)
                tool_ctx = create_coding_tool_context(
                    workspace,
                    prompts_dir=prompts_dir,
                    language=language,
                )
                tool_ctx = replace(tool_ctx, on_progress=progress_relay.emit)
                agent = create_flex_agent(
                    workspace,
                    prompts_dir=prompts_dir,
                    language=language,
                    tool_ctx=tool_ctx,
                )
            finally:
                restore_env(snapshot)

        thread_id = _load_thread_id(workspace)
        if not thread_id:
            thread_id = f"flex_agent_{strftime('%Y%m%d_%H%M%S')}"
            _save_thread_id(workspace, thread_id)
        config = merge_invoke_config(
            {
                "configurable": {"thread_id": thread_id},
                "recursion_limit": load_recursion_limit(),
            },
            trace_invoke_config("orchestrator"),
        )
        return AgentRuntime(
            session_id=session_id,
            workspace=workspace,
            language=language,
            prompts_dir=prompts_dir,
            prompt_set=prompt_set,
            env_mode=env_mode,
            agent=agent,
            parser=StreamEventParser(),
            thread_id=thread_id,
            config=config,
            progress_relay=progress_relay,
        )

    @staticmethod
    def activate_session_globals_for(
        language: Language,
        prompts_dir: Path,
        workspace: Workspace,
    ) -> None:
        set_language(language)
        set_prompts_dir(prompts_dir, language=language)
        set_workspace_dir(workspace.root)


session_manager = SessionManager()
