"""Workspace-level keyword and semantic judging for axial coding evaluation."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from flex_agent.eval.axial_aggregate import AXIAL_GLOBAL_TEXT_ID
from flex_agent.eval.axial_alignment import build_axial_semantic_alignment_for_texts
from flex_agent.eval.axial_core import enforce_one_to_one_alignment, keyword_alignment, normalize_category
from flex_agent.eval.axial_pairs import AxialGlobalEvalContext
from flex_agent.eval.judge import _counts_to_row
from flex_agent.eval.semantic_metrics import (
    apply_heuristic_semantic_alignment,
    build_semantic_row,
    merge_semantic_alignments,
    prefetch_semantic_alignment,
)
from flex_agent.i18n import get_language

GLOBAL_EVAL_CONTENT = "（workspace 级 codebook 主轴维度评测）"


def _global_eval_content() -> str:
    return (
        "(workspace-level codebook axial-dimension evaluation)"
        if get_language() == "en"
        else GLOBAL_EVAL_CONTENT
    )


def apply_axial_alignment_to_dims(
    agent_dims: set[str],
    alignment: dict[str, str | None],
    *,
    human_categories: set[str] | None = None,
) -> set[str]:
    """Rewrite agent dims to human categories with strict one-to-one mapping."""
    if not alignment:
        return set(agent_dims)
    category_pool = human_categories or {
        normalize_category(value) for value in alignment.values() if value
    }
    strict = enforce_one_to_one_alignment(
        {dim: alignment.get(dim) for dim in agent_dims},
        agent_dims=agent_dims,
        human_categories=category_pool,
    )
    mapped: set[str] = set()
    for dim in agent_dims:
        target = strict.get(dim)
        if target is not None:
            mapped.add(target)
        elif dim not in alignment:
            mapped.add(dim)
    return mapped


def judge_axial_global_keyword(
    ctx: AxialGlobalEvalContext,
    *,
    agent_dims: set[str] | None = None,
) -> dict[str, Any]:
    """Keyword-match full codebook dimensions against human category taxonomy."""
    human_categories = {normalize_category(c) for c in ctx.human_categories}
    agent_axial_dims = agent_dims if agent_dims is not None else set(ctx.agent_axial_dims)
    matched_agent, matched_human = keyword_alignment(agent_axial_dims, human_categories)
    return _counts_to_row(
        AXIAL_GLOBAL_TEXT_ID,
        human_categories,
        agent_axial_dims,
        matched_agent,
        matched_human,
    )


def judge_axial_global_semantic(
    ctx: AxialGlobalEvalContext,
    llm: BaseChatModel,
    *,
    agent_dims: set[str] | None = None,
) -> dict[str, Any]:
    """Semantic-align full codebook dimensions against human category taxonomy (one LLM call)."""
    human_categories = {normalize_category(c) for c in ctx.human_categories}
    resolved_agent_dims = agent_dims if agent_dims is not None else set(ctx.agent_axial_dims)
    alignment = prefetch_semantic_alignment(resolved_agent_dims, human_categories)

    pending_agent = {agent for agent, category in alignment.items() if category is None}
    if pending_agent and ctx.agent_dimensions_detail:
        entry = {
            "text_id": AXIAL_GLOBAL_TEXT_ID,
            "content": _global_eval_content(),
            "human_categories": sorted(human_categories),
            "agent_dimensions": ctx.agent_dimensions_detail,
        }
        try:
            llm_alignment = build_axial_semantic_alignment_for_texts([entry], llm)
            alignment = merge_semantic_alignments(
                alignment,
                llm_alignment.get(AXIAL_GLOBAL_TEXT_ID, {}),
            )
            alignment = enforce_one_to_one_alignment(
                alignment,
                agent_dims=resolved_agent_dims,
                human_categories=human_categories,
            )
        except Exception as exc:
            alignment = apply_heuristic_semantic_alignment(
                resolved_agent_dims, human_categories, alignment
            )
            alignment = enforce_one_to_one_alignment(
                alignment,
                agent_dims=resolved_agent_dims,
                human_categories=human_categories,
            )
            if any(alignment.values()):
                return build_semantic_row(
                    AXIAL_GLOBAL_TEXT_ID,
                    human_categories,
                    resolved_agent_dims,
                    alignment,
                )
            return build_semantic_row(
                AXIAL_GLOBAL_TEXT_ID,
                human_categories,
                resolved_agent_dims,
                alignment,
                status="failed",
                error=repr(exc),
            )

    alignment = apply_heuristic_semantic_alignment(
        resolved_agent_dims, human_categories, alignment
    )
    alignment = enforce_one_to_one_alignment(
        alignment,
        agent_dims=resolved_agent_dims,
        human_categories=human_categories,
    )
    return build_semantic_row(
        AXIAL_GLOBAL_TEXT_ID,
        human_categories,
        resolved_agent_dims,
        alignment,
    )
