from __future__ import annotations

from flex_agent.i18n import get_bundle


def orchestrator_prompt(language: str | None = None) -> str:
    return get_bundle(language).llm.orchestrator_prompt


ORCHESTRATOR_PROMPT = orchestrator_prompt("zh")
