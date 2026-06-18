from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .constants import (
    CATEGORY_KEYWORD_ALIASES,
    HUMAN_CATEGORIES,
    normalize_category,
    normalize_dimension,
)
from .llm import LLMClient
from .parser import extract_json_payload
from .schemas import HumanRecord, PredictionRecord
from flex_agent.i18n import get_bundle
from flex_agent.eval.core import micro_from_counts

GLOBAL_AXIAL_TEXT_ID = 0


@dataclass
class EvalMetrics:
    consistency: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    n_human: int = 0
    n_agent: int = 0
    n_intersection: int = 0
    n_union: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "consistency": round(self.consistency, 4),
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "n_human": self.n_human,
            "n_agent": self.n_agent,
            "n_intersection": self.n_intersection,
            "n_union": self.n_union,
        }


def prediction_dimensions(prediction: PredictionRecord | None) -> set[str]:
    if prediction is None:
        return set()
    return {
        normalize_dimension(item.dimension)
        for item in prediction.items
        if item.value != 0 and normalize_dimension(item.dimension)
    }


def prediction_categories(prediction: PredictionRecord | None) -> set[str]:
    if prediction is None:
        return set()
    return {
        normalize_category(item.category)
        for item in prediction.items
        if item.value != 0 and normalize_category(item.category)
    }


def counts_to_row(
    text_id: int,
    human_items: set[str],
    agent_items: set[str],
    matched_agent: set[str],
    matched_human: set[str],
    *,
    status: str = "complete",
    alignment: dict[str, str | None] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    llm_only = agent_items - matched_agent
    human_only = human_items - matched_human
    nums_both = len(matched_agent)
    nums_llm_only = len(llm_only)
    nums_human_only = len(human_only)
    union_count = nums_both + nums_llm_only + nums_human_only
    metrics = EvalMetrics(
        consistency=nums_both / union_count if union_count else 0.0,
        precision=nums_both / (nums_both + nums_llm_only) if (nums_both + nums_llm_only) else 0.0,
        recall=nums_both / (nums_both + nums_human_only) if (nums_both + nums_human_only) else 0.0,
        n_human=nums_both + nums_human_only,
        n_agent=nums_both + nums_llm_only,
        n_intersection=nums_both,
        n_union=union_count,
    )
    row = {
        "text_id": text_id,
        "human_items": sorted(human_items),
        "agent_items": sorted(agent_items),
        "both": sorted(matched_agent),
        "llm_only": sorted(llm_only),
        "human_only": sorted(human_only),
        "nums_both": nums_both,
        "nums_llm_only": nums_llm_only,
        "nums_human_only": nums_human_only,
        "status": status,
        **metrics.as_dict(),
    }
    if alignment is not None:
        row["alignment"] = alignment
    if error:
        row["error"] = error
    return row


def aggregate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
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


def evaluate_open(
    records: list[HumanRecord],
    predictions: dict[int, PredictionRecord],
    *,
    semantic_client: LLMClient | None = None,
) -> dict[str, Any]:
    eval_records = [record for record in records if record.human_dimensions]
    keyword_rows: list[dict[str, Any]] = []
    semantic_rows: list[dict[str, Any]] = []

    for record in eval_records:
        human_dims = {normalize_dimension(dim) for dim in record.human_dimensions}
        agent_dims = prediction_dimensions(predictions.get(record.text_id))
        matched = human_dims & agent_dims
        keyword_rows.append(counts_to_row(record.text_id, human_dims, agent_dims, matched, matched))

        if semantic_client is not None:
            semantic_rows.append(
                semantic_open_row(record, predictions.get(record.text_id), semantic_client)
            )

    payload: dict[str, Any] = {
        "item_level_keyword": aggregate_rows(keyword_rows),
        "keyword_complete": len(keyword_rows),
        "evaluated_texts": len(eval_records),
        "predicted_texts": len(predictions),
        "skipped_agent_only": len(set(predictions) - {record.text_id for record in eval_records}),
    }
    if semantic_client is not None:
        complete_semantic = [row for row in semantic_rows if row.get("status") == "complete"]
        payload["item_level_semantic"] = aggregate_rows(complete_semantic)
        payload["semantic_complete"] = len(complete_semantic)
    return payload


def semantic_open_row(
    record: HumanRecord,
    prediction: PredictionRecord | None,
    semantic_client: LLMClient,
) -> dict[str, Any]:
    human_dims = {normalize_dimension(dim) for dim in record.human_dimensions}
    agent_dims = prediction_dimensions(prediction)
    alignment = apply_heuristic_semantic_alignment(agent_dims, human_dims, {})
    pending = {agent for agent, human in alignment.items() if human is None}
    if pending:
        try:
            llm_alignment = semantic_dimension_alignment(
                semantic_client,
                content=record.content,
                human_items=sorted(human_dims),
                agent_items=sorted(agent_dims),
            )
            alignment = merge_semantic_alignments(alignment, llm_alignment)
        except Exception as exc:
            if not any(alignment.values()):
                return build_semantic_row(
                    record.text_id,
                    human_dims,
                    agent_dims,
                    alignment,
                    status="failed",
                    error=repr(exc),
                )
    alignment = apply_heuristic_semantic_alignment(agent_dims, human_dims, alignment)
    return build_semantic_row(record.text_id, human_dims, agent_dims, alignment)


def build_semantic_row(
    text_id: int,
    human_dims: set[str],
    agent_dims: set[str],
    alignment: dict[str, str | None],
    *,
    status: str = "complete",
    error: str | None = None,
) -> dict[str, Any]:
    matched_agent = {agent for agent, human in alignment.items() if human}
    matched_human = {human for human in alignment.values() if human}
    return counts_to_row(
        text_id,
        human_dims,
        agent_dims,
        matched_agent,
        matched_human,
        status=status,
        alignment=alignment,
        error=error,
    )


def semantic_dimension_alignment(
    client: LLMClient,
    *,
    content: str,
    human_items: list[str],
    agent_items: list[str],
) -> dict[str, str | None]:
    prompt = get_bundle().llm.direct_dimension_alignment_prompt.format(
        content=content,
        human_items=json.dumps(human_items, ensure_ascii=False),
        agent_items=json.dumps(agent_items, ensure_ascii=False),
    )
    payload = extract_json_payload(client.complete(prompt))
    mapping = payload.get("mapping") if isinstance(payload, dict) else None
    if not isinstance(mapping, dict):
        return {}
    human_set = set(human_items)
    agent_set = set(agent_items)
    result: dict[str, str | None] = {}
    for agent, human in mapping.items():
        agent_dim = normalize_dimension(str(agent))
        if agent_dim not in agent_set:
            continue
        human_dim = normalize_dimension(str(human)) if human else None
        result[agent_dim] = human_dim if human_dim in human_set else None
    return result


def evaluate_axial(
    predictions: dict[int, PredictionRecord],
    *,
    semantic_client: LLMClient | None = None,
) -> dict[str, Any]:
    agent_categories = {
        category
        for prediction in predictions.values()
        for category in prediction_categories(prediction)
        if category
    }
    human_categories = {normalize_category(category) for category in HUMAN_CATEGORIES}
    matched_agent, matched_human = keyword_alignment(agent_categories, human_categories)
    keyword = counts_to_row(
        GLOBAL_AXIAL_TEXT_ID,
        human_categories,
        agent_categories,
        matched_agent,
        matched_human,
    )
    payload: dict[str, Any] = {
        "item_level_keyword": aggregate_rows([keyword]),
        "keyword_complete": 1,
        "global": {"keyword": keyword},
        "agent_category_count": len(agent_categories),
        "human_category_count": len(human_categories),
    }
    if semantic_client is not None:
        semantic = semantic_axial_row(agent_categories, human_categories, semantic_client)
        payload["global"]["semantic"] = semantic
        if semantic.get("status") == "complete":
            payload["item_level_semantic"] = aggregate_rows([semantic])
            payload["semantic_complete"] = 1
        else:
            payload["item_level_semantic"] = None
            payload["semantic_complete"] = 0
    return payload


def semantic_axial_row(
    agent_categories: set[str],
    human_categories: set[str],
    semantic_client: LLMClient,
) -> dict[str, Any]:
    alignment = apply_heuristic_semantic_alignment(agent_categories, human_categories, {})
    pending = {agent for agent, human in alignment.items() if human is None}
    if pending:
        try:
            llm_alignment = semantic_category_alignment(semantic_client, agent_categories, human_categories)
            alignment = merge_semantic_alignments(alignment, llm_alignment)
        except Exception as exc:
            alignment = enforce_one_to_one_alignment(
                alignment,
                agent_items=agent_categories,
                human_items=human_categories,
            )
            if not any(alignment.values()):
                return build_semantic_row(
                    GLOBAL_AXIAL_TEXT_ID,
                    human_categories,
                    agent_categories,
                    alignment,
                    status="failed",
                    error=repr(exc),
                )
    alignment = apply_heuristic_semantic_alignment(agent_categories, human_categories, alignment)
    alignment = enforce_one_to_one_alignment(
        alignment,
        agent_items=agent_categories,
        human_items=human_categories,
    )
    return build_semantic_row(GLOBAL_AXIAL_TEXT_ID, human_categories, agent_categories, alignment)


def semantic_category_alignment(
    client: LLMClient,
    agent_categories: set[str],
    human_categories: set[str],
) -> dict[str, str | None]:
    prompt = get_bundle().llm.direct_category_alignment_prompt.format(
        human_categories=json.dumps(sorted(human_categories), ensure_ascii=False),
        agent_categories=json.dumps(sorted(agent_categories), ensure_ascii=False),
    )
    payload = extract_json_payload(client.complete(prompt))
    mapping = payload.get("mapping") if isinstance(payload, dict) else None
    if not isinstance(mapping, dict):
        return {}
    return {
        normalize_category(str(agent)): (
            normalize_category(str(human))
            if human and normalize_category(str(human)) in human_categories
            else None
        )
        for agent, human in mapping.items()
        if normalize_category(str(agent)) in agent_categories
    }


def keyword_match_score(agent_item: str, human_item: str) -> int:
    category = normalize_category(human_item)
    if agent_item == category:
        return 1000 + len(agent_item)
    aliases = CATEGORY_KEYWORD_ALIASES.get(category, set())
    if agent_item in aliases:
        return 900 + len(agent_item)
    best = 0
    for alias in aliases:
        if len(alias) >= 2 and alias in agent_item:
            best = max(best, 500 + len(alias))
        if len(alias) >= 2 and agent_item in alias:
            best = max(best, 400 + len(agent_item))
    return best


def keyword_alignment(agent_items: set[str], human_items: set[str]) -> tuple[set[str], set[str]]:
    candidates: list[tuple[int, str, str]] = []
    for agent in agent_items:
        for human in human_items:
            score = keyword_match_score(agent, human)
            if score > 0:
                candidates.append((score, agent, normalize_category(human)))
    candidates.sort(key=lambda row: (-row[0], row[1], row[2]))
    matched_agent: set[str] = set()
    matched_human: set[str] = set()
    for _score, agent, human in candidates:
        if agent in matched_agent or human in matched_human:
            continue
        matched_agent.add(agent)
        matched_human.add(human)
    return matched_agent, matched_human


def enforce_one_to_one_alignment(
    alignment: dict[str, str | None],
    *,
    agent_items: set[str],
    human_items: set[str],
) -> dict[str, str | None]:
    normalized_human = {normalize_category(human) for human in human_items}
    candidates: list[tuple[int, str, str]] = []
    for agent in agent_items:
        human = alignment.get(agent)
        if not human:
            continue
        category = normalize_category(human)
        if category not in normalized_human:
            continue
        candidates.append((keyword_match_score(agent, category), agent, category))
    candidates.sort(key=lambda row: (-row[0], row[1], row[2]))
    strict: dict[str, str | None] = {agent: None for agent in agent_items}
    used_human: set[str] = set()
    for _score, agent, human in candidates:
        if human in used_human:
            continue
        strict[agent] = human
        used_human.add(human)
    return strict


def merge_semantic_alignments(
    base: dict[str, str | None],
    override: dict[str, str | None],
) -> dict[str, str | None]:
    merged = dict(base)
    for agent_dim, human_dim in override.items():
        if merged.get(agent_dim):
            continue
        merged[agent_dim] = human_dim
    return merged


def apply_heuristic_semantic_alignment(
    agent_dims: set[str],
    human_dims: set[str],
    base: dict[str, str | None] | None = None,
) -> dict[str, str | None]:
    merged: dict[str, str | None] = {agent: None for agent in agent_dims}
    if base:
        merged.update(base)
    for agent_dim in sorted(agent_dims):
        if merged.get(agent_dim):
            continue
        merged[agent_dim] = _heuristic_human_match(agent_dim, human_dims)
    return merged


def _heuristic_human_match(agent_dim: str, human_dims: set[str]) -> str | None:
    best_score = 0
    best_human: str | None = None
    for human_dim in human_dims:
        score = _semantic_proximity_score(agent_dim, human_dim)
        if score > best_score:
            best_score = score
            best_human = human_dim
    return best_human


def _semantic_proximity_score(agent_dim: str, human_dim: str) -> int:
    canonical = normalize_dimension(agent_dim)
    if normalize_category(agent_dim) == normalize_category(human_dim):
        return 120 + len(human_dim)
    if canonical == human_dim:
        return 100 + len(human_dim)
    if len(human_dim) >= 2 and human_dim in agent_dim:
        return 90 + len(human_dim)
    if len(human_dim) >= 2 and human_dim in canonical:
        return 85 + len(human_dim)
    if len(canonical) >= 2 and canonical in human_dim:
        return 80 + len(canonical)
    if len(agent_dim) >= 2 and agent_dim in human_dim:
        return 75 + len(agent_dim)
    if _bigrams(agent_dim) & _bigrams(human_dim):
        overlap = _char_overlap_ratio(agent_dim, human_dim)
        if overlap >= 0.34:
            return 50 + int(overlap * 20) + min(len(human_dim), len(agent_dim))
    if _bigrams(canonical) & _bigrams(human_dim):
        overlap = _char_overlap_ratio(canonical, human_dim)
        if overlap >= 0.34:
            return 40 + int(overlap * 20) + min(len(human_dim), len(canonical))
    return 0


def _bigrams(text: str) -> set[str]:
    if len(text) < 2:
        return set()
    return {text[index : index + 2] for index in range(len(text) - 1)}


def _char_overlap_ratio(left: str, right: str) -> float:
    left_chars = set(left)
    right_chars = set(right)
    if not left_chars or not right_chars:
        return 0.0
    return len(left_chars & right_chars) / min(len(left_chars), len(right_chars))
