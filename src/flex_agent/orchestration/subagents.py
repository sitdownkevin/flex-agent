from __future__ import annotations

from deepagents.middleware.filesystem import FilesystemPermission

from flex_agent.coding.agents import PromptContext
from flex_agent.i18n import get_bundle

SUBAGENT_DENY_PRIVATE = [
    FilesystemPermission(
        operations=["read", "write"],
        paths=["/private/**", "/eval/**"],
        mode="deny",
    ),
]

PRIVATE_ACCESS_NOTE = get_bundle("zh").llm.private_access_note
BOB_WORKSPACE_SCHEMA_NOTE = get_bundle("zh").llm.bob_workspace_schema_note
CODEBOOK_WORKSPACE_SCHEMA_NOTE = get_bundle("zh").llm.codebook_workspace_schema_note


def build_subagents(prompt_ctx: PromptContext | None = None, *, language: str | None = None) -> list[dict]:
    ctx = prompt_ctx or PromptContext.load()
    bundle = get_bundle(language or ctx.language).llm
    return [
        {
            "name": "bob-coder",
            "description": bundle.subagent_descriptions["bob-coder"],
            "system_prompt": (
                ctx.bob_template
                + bundle.subagent_addenda["bob-coder"]
                + bundle.bob_workspace_schema_note
                + bundle.private_access_note
            ),
            "permissions": SUBAGENT_DENY_PRIVATE,
        },
        {
            "name": "alice-codebook",
            "description": bundle.subagent_descriptions["alice-codebook"],
            "system_prompt": (
                ctx.alice_template
                + bundle.subagent_addenda["alice-codebook"]
                + bundle.codebook_workspace_schema_note
                + bundle.private_access_note
            ),
            "permissions": SUBAGENT_DENY_PRIVATE,
        },
        {
            "name": "kevin-updater",
            "description": bundle.subagent_descriptions["kevin-updater"],
            "system_prompt": (
                ctx.kevin_template
                + bundle.subagent_addenda["kevin-updater"]
                + bundle.codebook_workspace_schema_note
                + bundle.private_access_note
            ),
            "permissions": SUBAGENT_DENY_PRIVATE,
        },
    ]
