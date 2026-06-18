"""Aggregate per-text eval results into macro and micro CPR metrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flex_agent.eval.core import EvalMetrics, micro_from_counts
from flex_agent.eval.semantic_metrics import build_semantic_row


def _aggregate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        empty = EvalMetrics().as_dict()
        return {
            "common_texts": 0,
            "nums_llm_only": 0,
            "nums_human_only": 0,
            "nums_both": 0,
            "macro": empty,
            "micro": empty,
            "per_text": [],
        }

    total_llm_only = sum(row["nums_llm_only"] for row in rows)
    total_human_only = sum(row["nums_human_only"] for row in rows)
    total_both = sum(row["nums_both"] for row in rows)
    total_agent = total_both + total_llm_only
    total_human = total_both + total_human_only
    total_union = total_both + total_llm_only + total_human_only

    macro = EvalMetrics(
        consistency=sum(row["consistency"] for row in rows) / len(rows),
        precision=sum(row["precision"] for row in rows) / len(rows),
        recall=sum(row["recall"] for row in rows) / len(rows),
        n_human=total_human,
        n_agent=total_agent,
        n_intersection=total_both,
        n_union=total_union,
    )
    return {
        "common_texts": len(rows),
        "nums_llm_only": total_llm_only,
        "nums_human_only": total_human_only,
        "nums_both": total_both,
        "macro": macro.as_dict(),
        "micro": micro_from_counts(total_both, total_llm_only, total_human_only).as_dict(),
        "per_text": rows,
    }


def _section_complete(section: dict[str, Any] | None) -> bool:
    if not isinstance(section, dict):
        return False
    status = section.get("status")
    if status is None:
        return "nums_both" in section
    return status == "complete"


def load_eval_text_rows(eval_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load complete keyword/semantic rows from eval/open/{id}.json files."""
    keyword_rows: list[dict[str, Any]] = []
    semantic_rows: list[dict[str, Any]] = []
    if not eval_dir.exists():
        return keyword_rows, semantic_rows

    for path in sorted(eval_dir.glob("*.json"), key=lambda p: p.stem):
        if path.name == "summary.json":
            continue
        try:
            int(path.stem)
        except ValueError:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        keyword = payload.get("keyword")
        semantic = payload.get("semantic")
        if _section_complete(keyword):
            keyword_rows.append(keyword)
        if _section_complete(semantic):
            semantic_rows.append(_normalize_semantic_row(semantic))
    return keyword_rows, semantic_rows


def _normalize_semantic_row(section: dict[str, Any]) -> dict[str, Any]:
    """Recompute counts from alignment so stored rows stay consistent."""
    alignment = section.get("alignment")
    if not isinstance(alignment, dict):
        return section
    human_dims = set(section.get("human_items") or [])
    agent_dims = set(section.get("agent_items") or [])
    if not human_dims or not agent_dims:
        return section
    return build_semantic_row(
        int(section["text_id"]),
        human_dims,
        agent_dims,
        alignment,
        status=str(section.get("status") or "complete"),
        error=section.get("error"),
    )


def aggregate_eval_results(eval_dir: Path) -> dict[str, Any]:
    """Scan eval/open/*.json and compute aggregated keyword/semantic metrics."""
    keyword_rows, semantic_rows = load_eval_text_rows(eval_dir)
    return {
        "item_level_keyword": _aggregate_rows(keyword_rows) if keyword_rows else None,
        "item_level_semantic": _aggregate_rows(semantic_rows) if semantic_rows else None,
        "keyword_complete": len(keyword_rows),
        "semantic_complete": len(semantic_rows),
    }
