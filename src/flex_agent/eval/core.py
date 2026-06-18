"""Shared evaluation utilities for open coding quality assessment."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flex_agent.coding.quality import COMMON_LABEL_ALIASES, ENGLISH_LABEL_TRANSLATIONS

ALL_HUMAN_DIMENSIONS = sorted(
    {
        "位置", "环境", "私密性", "充裕度",
        "态度", "专业度", "增值服务",
        "上手难易", "物理舒适度", "生理舒适度", "维护情况", "可靠性", "流畅度",
        "声音", "画面", "其他感官",
        "选择多样", "趣味性", "创新性", "丰富度",
        "价格", "时长/次数", "熟人社交", "陌生社交", "愉悦身心", "体验探索",
        "二刷意愿", "推荐意愿",
    }
)

P_TAG_RE = re.compile(r"</?p>", flags=re.IGNORECASE)


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


def micro_from_counts(
    nums_both: int,
    nums_llm_only: int,
    nums_human_only: int,
) -> EvalMetrics:
    """Compute pooled (micro) CPR metrics from aggregate item counts."""
    n_agent = nums_both + nums_llm_only
    n_human = nums_both + nums_human_only
    n_union = nums_both + nums_llm_only + nums_human_only
    return EvalMetrics(
        consistency=nums_both / n_union if n_union else 0.0,
        precision=nums_both / n_agent if n_agent else 0.0,
        recall=nums_both / n_human if n_human else 0.0,
        n_human=n_human,
        n_agent=n_agent,
        n_intersection=nums_both,
        n_union=n_union,
    )


def normalize_dimension(dim: str) -> str:
    """Normalize a dimension name through alias tables."""
    dim = dim.strip()
    if dim in COMMON_LABEL_ALIASES:
        return COMMON_LABEL_ALIASES[dim]
    lowered = dim.lower().replace("-", "_").replace(" ", "_")
    if lowered in ENGLISH_LABEL_TRANSLATIONS:
        return ENGLISH_LABEL_TRANSLATIONS[lowered]
    return dim


def normalize_content_key(content: str) -> str:
    """Normalize text content for matching benchmark rows to agent results."""
    without_tags = P_TAG_RE.sub("", str(content or ""))
    return "".join(without_tags.split())


def human_items_from_record(record: dict[str, Any]) -> dict[str, int]:
    """Extract normalized non-zero human dimensions from benchmark record."""
    items: dict[str, int] = {}
    if isinstance(record.get("human_items"), list):
        for item in record.get("human_items", []):
            value = item.get("value", 1)
            if value == 0:
                continue
            dim = normalize_dimension(str(item.get("dimension", "")).strip())
            if dim:
                items[dim] = int(value)
        return items

    for code_val in record.get("codes", {}).values():
        value = code_val.get("value", 0)
        if value != 0:
            dim = normalize_dimension(str(code_val.get("dimension", "")).strip())
            if dim:
                items[dim] = int(value)
    return items


def make_item_set(items: dict[str, int]) -> set[str]:
    """Convert {dim: polarity} to a set of 'dim:+1' / 'dim:-1' strings."""
    return {f"{dim}:{'+' if pol > 0 else '-'}1" for dim, pol in items.items()}


def load_human_benchmark(jsonl_path: Path) -> dict[int, dict[str, int]]:
    """Load human-coded benchmark keyed by 1-indexed file order."""
    human_items: dict[int, dict[str, int]] = {}
    with open(jsonl_path, encoding="utf-8") as handle:
        for idx, line in enumerate(handle, start=1):
            record = json.loads(line.strip())
            items = human_items_from_record(record)
            if items:
                human_items[idx] = items
    return human_items


def load_human_benchmark_by_content(jsonl_path: Path) -> dict[str, dict[str, int]]:
    """Load human-coded benchmark keyed by normalized comment content."""
    human_items_by_content: dict[str, dict[str, int]] = {}
    with open(jsonl_path, encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line.strip())
            comment = str(record.get("comments", "")).strip()
            if not comment:
                continue
            normalized_comment = normalize_content_key(comment)
            items = human_items_from_record(record)
            if items:
                human_items_by_content[normalized_comment] = items
    return human_items_by_content


def load_human_records_by_content(jsonl_path: Path) -> dict[str, dict[str, Any]]:
    """Load full human benchmark records keyed by normalized comment content."""
    records: dict[str, dict[str, Any]] = {}
    with open(jsonl_path, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            comment = str(record.get("comments", "")).strip()
            if not comment:
                continue
            record = dict(record)
            record["items_by_dimension"] = human_items_from_record(record)
            records[normalize_content_key(comment)] = record
    return records


def extract_agent_items(finished_texts: list[dict]) -> dict[int, dict[str, int]]:
    """Extract per-text items from finished_texts; ignores polarity for matching."""
    agent_items: dict[int, dict[str, int]] = {}
    for ft in finished_texts:
        text_id = ft["id"]
        items: dict[str, int] = {}
        for item in ft.get("items", []):
            normalized = str(item.get("normalized_label") or "").strip()
            if normalized:
                dim = normalize_dimension(re.split(r"[:：]", normalized, maxsplit=1)[0].strip())
                if dim and dim not in items:
                    items[dim] = 1
                continue

            labels_str = item.get("labels", "") or ""
            for label in labels_str.split(";"):
                label = label.strip()
                if not label or (":" not in label and "：" not in label):
                    continue
                parts = re.split(r"[:：]", label, maxsplit=1)
                if len(parts) != 2:
                    continue
                dim_raw, pol_str = parts
                dim = normalize_dimension(dim_raw)
                try:
                    pol = int(pol_str)
                except ValueError:
                    continue
                if pol not in (-1, 1):
                    continue
                if dim not in items:
                    items[dim] = pol
        if items:
            agent_items[text_id] = items
    return agent_items


def extract_agent_items_raw(finished_texts: list[dict]) -> dict[int, list[dict]]:
    """Extract raw agent items per text (with evidence/reason intact)."""
    raw_items: dict[int, list[dict]] = {}
    for ft in finished_texts:
        text_id = ft["id"]
        items = ft.get("items", [])
        if items:
            raw_items[text_id] = items
    return raw_items
