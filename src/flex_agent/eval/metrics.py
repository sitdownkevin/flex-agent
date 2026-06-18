from __future__ import annotations

from typing import Any

from flex_agent.eval.core import EvalMetrics, micro_from_counts, normalize_dimension


def compute_item_metrics_simple(
    human_items: dict[int, dict[str, int]],
    agent_items: dict[int, dict[str, int]],
) -> dict[str, Any]:
    """Compute item-level metrics by normalized dimension matching, ignoring polarity."""
    common_ids = sorted(set(human_items) & set(agent_items))
    if not common_ids:
        return {
            "common_texts": 0,
            "nums_llm_only": 0,
            "nums_human_only": 0,
            "nums_both": 0,
            "macro": EvalMetrics().as_dict(),
            "micro": EvalMetrics().as_dict(),
            "per_text": [],
        }

    per_text_results: list[dict] = []
    total_llm_only = 0
    total_human_only = 0
    total_both = 0

    for text_id in common_ids:
        h_set = {normalize_dimension(dim) for dim in human_items[text_id]}
        a_set = {normalize_dimension(dim) for dim in agent_items[text_id]}
        both = h_set & a_set
        llm_only = a_set - h_set
        human_only = h_set - a_set

        total_llm_only += len(llm_only)
        total_human_only += len(human_only)
        total_both += len(both)

        union_count = len(both) + len(llm_only) + len(human_only)
        consistency = len(both) / union_count if union_count > 0 else 0.0
        precision = len(both) / (len(both) + len(llm_only)) if (len(both) + len(llm_only)) > 0 else 0.0
        recall = len(both) / (len(both) + len(human_only)) if (len(both) + len(human_only)) > 0 else 0.0

        per_text_results.append({
            "text_id": text_id,
            "human_items": sorted(h_set),
            "agent_items": sorted(a_set),
            "both": sorted(both),
            "llm_only": sorted(llm_only),
            "human_only": sorted(human_only),
            "nums_both": len(both),
            "nums_llm_only": len(llm_only),
            "nums_human_only": len(human_only),
            "consistency": round(consistency, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
        })

    n_texts = len(per_text_results)
    total_agent = total_both + total_llm_only
    total_human = total_both + total_human_only
    total_union = total_both + total_llm_only + total_human_only
    macro = EvalMetrics(
        consistency=sum(r["consistency"] for r in per_text_results) / n_texts,
        precision=sum(r["precision"] for r in per_text_results) / n_texts,
        recall=sum(r["recall"] for r in per_text_results) / n_texts,
        n_human=total_human,
        n_agent=total_agent,
        n_intersection=total_both,
        n_union=total_union,
    )

    return {
        "common_texts": len(common_ids),
        "skipped_human_only": len(set(human_items) - set(agent_items)),
        "skipped_agent_only": len(set(agent_items) - set(human_items)),
        "nums_llm_only": total_llm_only,
        "nums_human_only": total_human_only,
        "nums_both": total_both,
        "macro": macro.as_dict(),
        "micro": micro_from_counts(total_both, total_llm_only, total_human_only).as_dict(),
        "per_text": per_text_results,
    }
