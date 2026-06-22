from __future__ import annotations

from pathlib import Path

from deepagents import GeneralPurposeSubagentProfile, HarnessProfile, create_deep_agent, register_harness_profile
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from langgraph.checkpoint.memory import MemorySaver

from flex_agent.config import build_llm, load_model_config
from flex_agent.debug_log import agent_debug_log
from flex_agent.i18n import get_language, resolve_language
from flex_agent.orchestration.prompt import orchestrator_prompt
from flex_agent.orchestration.subagents import build_subagents
from flex_agent.orchestration.tools import CodingToolContext, build_coding_tools, create_coding_tool_context
from flex_agent.workspace import Workspace

_HARNESS_REGISTERED = False
_CHECKPOINTER = MemorySaver()


def _ensure_flex_harness_profile() -> None:
    global _HARNESS_REGISTERED
    if _HARNESS_REGISTERED:
        return
    register_harness_profile(
        "openai",
        HarnessProfile(
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
        ),
    )
    _HARNESS_REGISTERED = True


def build_backend(workspace: Workspace) -> CompositeBackend:
    root = workspace.root.resolve()
    return CompositeBackend(
        default=FilesystemBackend(root_dir=root, virtual_mode=True),
        routes={"/agent/": StateBackend()},
    )


def create_flex_agent(
    workspace: Workspace,
    *,
    prompts_dir: Path | None = None,
    tool_ctx: CodingToolContext | None = None,
    language: str | None = None,
):
    _ensure_flex_harness_profile()
    active_language = resolve_language(language) if language is not None else get_language()
    ctx = tool_ctx or create_coding_tool_context(
        workspace,
        prompts_dir=prompts_dir,
        language=active_language,
    )
    model_cfg = load_model_config()
    model = build_llm(
        model_cfg.pro_model,
        timeout=model_cfg.timeout,
        max_retries=model_cfg.max_retries,
        seed=model_cfg.seed,
    )
    workspace.ensure_layout()
    workspace.bootstrap_seed_files()
    # region agent log
    agent_debug_log(
        hypothesis_id="H3,H5",
        location="src/flex_agent/orchestration/factory.py:create_flex_agent",
        message="creating deep agent",
        data={
            "language": ctx.language,
            "workspace_root": str(workspace.root.resolve()),
            "prompts_dir": ctx.prompts_dir_label,
            "default_model": model_cfg.default_model,
            "pro_model": model_cfg.pro_model,
            "seed": model_cfg.seed,
            "checkpointer_id": id(_CHECKPOINTER),
        },
    )
    # endregion
    return create_deep_agent(
        model=model,
        tools=build_coding_tools(ctx),
        system_prompt=orchestrator_prompt(ctx.language),
        subagents=build_subagents(ctx.prompt_ctx, language=ctx.language),
        backend=build_backend(workspace),
        checkpointer=_CHECKPOINTER,
        name="code-orchestrator",
    )
