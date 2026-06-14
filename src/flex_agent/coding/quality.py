from __future__ import annotations

import copy
import html
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from flex_agent.models import DimensionDetail, FinishedItemDetail, FinishedTextItem


POLARITY_RE = re.compile(r"^\s*([^:：]+?)\s*[:：]\s*([+-]1)\s*$")
SPAN_LABEL_RE = re.compile(
    r"<span[^>]*title=[\"']([^\"']+)[\"'][^>]*>(.*?)</span>",
    flags=re.IGNORECASE | re.DOTALL,
)
@dataclass
class QualityWarnings:
    invalid_markup: int = 0
    english_labels: int = 0
    neutral_labels: int = 0
    malformed_labels: int = 0
    duplicate_items: int = 0
    empty_evidence: int = 0
    dropped_labels: int = 0
    normalized_labels: int = 0
    notes: list[str] = field(default_factory=list)

    def add(self, other: "QualityWarnings") -> None:
        self.invalid_markup += other.invalid_markup
        self.english_labels += other.english_labels
        self.neutral_labels += other.neutral_labels
        self.malformed_labels += other.malformed_labels
        self.duplicate_items += other.duplicate_items
        self.empty_evidence += other.empty_evidence
        self.dropped_labels += other.dropped_labels
        self.normalized_labels += other.normalized_labels
        self.notes.extend(other.notes)

    def as_dict(self) -> dict:
        return {
            "invalid_markup": self.invalid_markup,
            "english_labels": self.english_labels,
            "neutral_labels": self.neutral_labels,
            "malformed_labels": self.malformed_labels,
            "duplicate_items": self.duplicate_items,
            "empty_evidence": self.empty_evidence,
            "dropped_labels": self.dropped_labels,
            "normalized_labels": self.normalized_labels,
            "notes": self.notes,
        }


COMMON_LABEL_ALIASES = {
    "员工态度": "态度",
    "服务态度": "态度",
    "工作人员态度": "态度",
    "员工服务": "态度",
    "服务质量": "态度",
    "员工指导": "专业度",
    "耐心指导": "专业度",
    "员工专业度": "专业度",
    "拍照服务": "增值服务",
    "地理位置": "位置",
    "位置便利": "位置",
    "交通便利": "位置",
    "环境": "环境",
    "坏境": "环境",
    "场地环境": "环境",
    "场地空间": "充裕度",
    "空间": "充裕度",
    "空间大小": "充裕度",
    "身体舒适度": "物理舒适度",
    "身体疲劳": "物理舒适度",
    "眩晕": "生理舒适度",
    "晕眩": "生理舒适度",
    "视觉": "画面",
    "视觉效果": "画面",
    "声音效果": "声音",
    "音效": "声音",
    "游戏种类": "选择多样",
    "内容多样性": "选择多样",
    "游戏丰富度": "丰富度",
    "新鲜感": "创新性",
    "社交": "熟人社交",
    "朋友社交": "熟人社交",
    "亲子社交": "熟人社交",
    "性价比": "价格",
    "性价比感知": "价格",
    "重游意愿": "二刷意愿",
    "再访意愿": "二刷意愿",
    "再次体验意愿": "二刷意愿",
    "推荐": "推荐意愿",
}


ENGLISH_LABEL_TRANSLATIONS = {
    "staff_attitude": "态度",
    "staff_service_attitude": "态度",
    "staff_service_quality": "态度",
    "service_quality": "态度",
    "staff_patience": "专业度",
    "staff_guidance": "专业度",
    "staff_professionalism": "专业度",
    "staff_expertise": "专业度",
    "service_flexibility": "增值服务",
    "service_accommodation": "增值服务",
    "location_convenience": "位置",
    "geographic_accessibility": "位置",
    "location_findability": "位置",
    "environment_ambiance": "环境",
    "environmental_aesthetics": "环境",
    "physical_comfort": "物理舒适度",
    "equipment_weight": "物理舒适度",
    "usability": "上手难易",
    "ease_of_learning": "上手难易",
    "visual_quality": "画面",
    "immersive_realism": "画面",
    "audio_quality": "声音",
    "content_variety": "选择多样",
    "game_variety": "选择多样",
    "content_diversity": "选择多样",
    "gameplay_fun": "趣味性",
    "game_enjoyment": "趣味性",
    "playfulness": "趣味性",
    "novelty": "创新性",
    "novelty_experience": "创新性",
    "price_value": "价格",
    "value_for_money": "价格",
    "social_value": "熟人社交",
    "social_interaction": "熟人社交",
    "revisit_intention": "二刷意愿",
    "revist_intention": "二刷意愿",
    "recommendation_intention": "推荐意愿",
}


def clean_content_markup(content_with_labels: str) -> tuple[str, QualityWarnings]:
    warnings = QualityWarnings()
    cleaned = content_with_labels or ""

    if "<e>" in cleaned or "</e>" in cleaned:
        warnings.invalid_markup += cleaned.count("<e>") + cleaned.count("</e>")
        cleaned = cleaned.replace("<e>", "<p>").replace("</e>", "</p>")

    def replace_span(match: re.Match[str]) -> str:
        warnings.invalid_markup += 1
        return f"<p>{match.group(2)}</p>"

    cleaned = SPAN_LABEL_RE.sub(replace_span, cleaned)
    cleaned = re.sub(r"</?strong>|</?em>|</?b>|</?i>", "", cleaned, flags=re.IGNORECASE)
    return cleaned, warnings


def _wrap_missing_evidence(content_with_labels: str, evidence: str) -> tuple[str, bool]:
    evidence = evidence.strip()
    if not evidence or f"<p>{evidence}</p>" in content_with_labels:
        return content_with_labels, False
    if evidence not in content_with_labels:
        return content_with_labels, False
    return content_with_labels.replace(evidence, f"<p>{evidence}</p>", 1), True


def normalize_label_dimension(raw_dimension: str, warnings: QualityWarnings) -> str | None:
    dimension = html.unescape(raw_dimension).strip()
    dimension = re.sub(r"\s+", "", dimension)
    if not dimension:
        warnings.malformed_labels += 1
        return None

    lowered = dimension.lower().replace("-", "_").replace(" ", "_")
    if lowered in {"neutral", "none", "n/a", "na"}:
        warnings.neutral_labels += 1
        warnings.dropped_labels += 1
        return None

    if re.fullmatch(r"[A-Za-z0-9_ /-]+", dimension):
        warnings.english_labels += 1
        translated = ENGLISH_LABEL_TRANSLATIONS.get(lowered)
        if translated is None:
            warnings.dropped_labels += 1
            return None
        warnings.normalized_labels += 1
        return translated

    normalized = COMMON_LABEL_ALIASES.get(dimension, dimension)
    if normalized != dimension:
        warnings.normalized_labels += 1
    return normalized


def item_dimension(item: FinishedItemDetail, warnings: QualityWarnings | None = None) -> str | None:
    active_warnings = warnings if warnings is not None else QualityWarnings()

    raw = (item.normalized_label or "").strip()
    if raw:
        match = POLARITY_RE.match(raw)
        if match:
            raw = match.group(1)
        return normalize_label_dimension(raw, active_warnings)

    if item.labels:
        parsed = parse_labels(item.labels, active_warnings)
        if parsed:
            return parsed[0].split(":", maxsplit=1)[0]

    if item.name:
        return normalize_label_dimension(item.name.strip(), active_warnings)

    return None


def item_dimensions(item: FinishedItemDetail, warnings: QualityWarnings | None = None) -> list[str]:
    if (item.normalized_label or "").strip():
        dimension = item_dimension(item, warnings)
        return [dimension] if dimension else []
    if item.labels:
        return [label.split(":", maxsplit=1)[0] for label in parse_labels(item.labels, warnings)]
    dimension = item_dimension(item, warnings)
    return [dimension] if dimension else []


def parse_labels(labels: str, warnings: QualityWarnings | None = None) -> list[str]:
    active_warnings = warnings if warnings is not None else QualityWarnings()
    parsed: list[str] = []
    seen: set[str] = set()
    for raw_label in re.split(r"[;；]", labels or ""):
        label = raw_label.strip()
        if not label:
            continue
        if "neutral" in label.lower():
            active_warnings.neutral_labels += 1
            active_warnings.dropped_labels += 1
            continue
        match = POLARITY_RE.match(label)
        if not match:
            active_warnings.malformed_labels += 1
            active_warnings.dropped_labels += 1
            continue
        dimension = normalize_label_dimension(match.group(1), active_warnings)
        if dimension is None:
            continue
        normalized_label = f"{dimension}:{match.group(2)}"
        if normalized_label not in seen:
            parsed.append(normalized_label)
            seen.add(normalized_label)
    return parsed


def normalize_item(item: FinishedItemDetail) -> tuple[list[FinishedItemDetail], QualityWarnings]:
    warnings = QualityWarnings()
    evidence = (item.evidence or item.name or "").strip()
    if not evidence:
        warnings.empty_evidence += 1

    if (item.normalized_label or "").strip():
        dimension = item_dimension(item, warnings)
        if dimension is None:
            return [], warnings
        return [
            FinishedItemDetail(
                name=(item.name or evidence or dimension).strip(),
                evidence=evidence or None,
                normalized_label=dimension,
                reason=item.reason,
            )
        ], warnings

    if item.labels:
        parsed_labels = parse_labels(item.labels, warnings)
        normalized_items: list[FinishedItemDetail] = []
        for label in parsed_labels:
            dimension = label.split(":", maxsplit=1)[0]
            normalized_items.append(
                FinishedItemDetail(
                    name=(item.name or evidence or dimension).strip(),
                    evidence=evidence or None,
                    normalized_label=dimension,
                    reason=item.reason,
                )
            )
        return normalized_items, warnings

    dimension = item_dimension(item, warnings)
    if dimension is None:
        return [], warnings

    return [
        FinishedItemDetail(
            name=(item.name or evidence or dimension).strip(),
            evidence=evidence or None,
            normalized_label=dimension,
            reason=item.reason,
        )
    ], warnings


def normalize_finished_text(finished: FinishedTextItem) -> tuple[FinishedTextItem, QualityWarnings]:
    warnings = QualityWarnings()
    content_with_labels, markup_warnings = clean_content_markup(finished.content_with_labels)
    warnings.add(markup_warnings)

    normalized_items: list[FinishedItemDetail] = []
    seen_items: set[tuple[str, str]] = set()
    for item in finished.items:
        item_outputs, item_warnings = normalize_item(item)
        warnings.add(item_warnings)
        for normalized_item in item_outputs:
            key = (normalized_item.name, normalized_item.normalized_label or "")
            if key in seen_items:
                warnings.duplicate_items += 1
                continue
            normalized_items.append(normalized_item)
            seen_items.add(key)

    for normalized_item in normalized_items:
        if normalized_item.evidence:
            content_with_labels, wrapped = _wrap_missing_evidence(
                content_with_labels,
                normalized_item.evidence,
            )
            if wrapped:
                warnings.invalid_markup += 1

    return (
        FinishedTextItem(
            id=finished.id,
            content=finished.content,
            content_with_labels=content_with_labels,
            items=normalized_items,
        ),
        warnings,
    )


def normalize_finished_texts(
    finished_texts: Sequence[FinishedTextItem],
) -> tuple[list[FinishedTextItem], QualityWarnings]:
    warnings = QualityWarnings()
    normalized: list[FinishedTextItem] = []
    for finished in finished_texts:
        normalized_finished, item_warnings = normalize_finished_text(finished)
        warnings.add(item_warnings)
        normalized.append(normalized_finished)
    return normalized, warnings


def extract_item_pool(finished_texts: Iterable[FinishedTextItem]) -> list[str]:
    item_names: set[str] = set()
    for finished in finished_texts:
        for item in finished.items:
            item_names.update(item_dimensions(item))
    return sorted(item_names)


def merge_new_items_into_dimensions(
    dimensions: Sequence[DimensionDetail],
    new_items: Sequence[str],
    new_dimensions: Sequence[DimensionDetail] | None = None,
) -> tuple[list[DimensionDetail], QualityWarnings]:
    max_new_dimensions_per_merge = 1
    min_items_for_new_dimension = 2
    warnings = QualityWarnings()
    merged = copy.deepcopy(list(dimensions))
    if not merged:
        warnings.notes.append("merge skipped because there are no existing dimensions")

    index: dict[str, DimensionDetail] = {}
    for dimension in merged:
        unique_items: list[str] = []
        for item in dimension.items:
            normalized = COMMON_LABEL_ALIASES.get(item.strip(), item.strip())
            if not normalized:
                continue
            if normalized in index:
                warnings.duplicate_items += 1
                continue
            unique_items.append(normalized)
            index[normalized] = dimension
        dimension.items = unique_items

    dimension_name_index = {dimension.name.strip(): dimension for dimension in merged if dimension.name.strip()}
    created_new_dimensions = 0
    if new_dimensions:
        for proposal in new_dimensions:
            proposal_name = proposal.name.strip()
            if not proposal_name:
                continue
            target_dimension = dimension_name_index.get(proposal_name)
            if target_dimension is None:
                proposed_items = [
                    COMMON_LABEL_ALIASES.get(raw_item.strip(), raw_item.strip())
                    for raw_item in proposal.items
                    if COMMON_LABEL_ALIASES.get(raw_item.strip(), raw_item.strip())
                ]
                unique_proposed_items = list(dict.fromkeys(proposed_items))
                if len(unique_proposed_items) < min_items_for_new_dimension:
                    warnings.notes.append(
                        "skip sparse new dimension proposal with fewer than 2 unique items"
                    )
                    new_items = list(new_items) + unique_proposed_items
                    continue
                if created_new_dimensions >= max_new_dimensions_per_merge:
                    warnings.notes.append(
                        "skip new dimension proposals above max_new_dimensions_per_merge=1"
                    )
                    new_items = list(new_items) + unique_proposed_items
                    continue
                target_dimension = DimensionDetail(
                    name=proposal_name,
                    items=[],
                    definition=proposal.definition,
                )
                merged.append(target_dimension)
                dimension_name_index[proposal_name] = target_dimension
                created_new_dimensions += 1
            elif not target_dimension.definition and proposal.definition:
                target_dimension.definition = proposal.definition

            for raw_item in proposal.items:
                item_label = COMMON_LABEL_ALIASES.get(raw_item.strip(), raw_item.strip())
                if not item_label:
                    continue
                if item_label in index:
                    continue
                target_dimension.items.append(item_label)
                index[item_label] = target_dimension

    skipped_items: list[str] = []
    for raw_item in new_items:
        item_label = COMMON_LABEL_ALIASES.get(raw_item.strip(), raw_item.strip())
        if not item_label:
            continue
        if item_label in index:
            continue
        skipped_items.append(item_label)

    if skipped_items:
        unique_skipped_items = list(dict.fromkeys(skipped_items))
        warnings.notes.append(
            "unassigned items skipped instead of adding fallback dimension: "
            + ", ".join(unique_skipped_items)
        )

    return merged, warnings


def review_dimensions(
    dimensions: Sequence[DimensionDetail],
    finished_texts: Sequence[FinishedTextItem] | None = None,
) -> tuple[list[DimensionDetail], QualityWarnings]:
    warnings = QualityWarnings()
    reviewed: list[DimensionDetail] = []
    used_items: set[str] = set()
    used_names: Counter[str] = Counter()

    for dimension in dimensions:
        name = dimension.name.strip()
        if not name:
            continue
        used_names[name] += 1
        if used_names[name] > 1:
            warnings.duplicate_items += 1
            name = f"{name}{used_names[name]}"

        unique_items: list[str] = []
        for raw_item in dimension.items:
            item = COMMON_LABEL_ALIASES.get(raw_item.strip(), raw_item.strip())
            if not item:
                continue
            if item in used_items:
                warnings.duplicate_items += 1
                continue
            used_items.add(item)
            unique_items.append(item)
        if unique_items:
            reviewed.append(
                DimensionDetail(
                    name=name,
                    items=unique_items,
                    definition=dimension.definition,
                )
            )

    if finished_texts is not None:
        missing_items = [item for item in extract_item_pool(finished_texts) if item not in used_items]
        if missing_items:
            warnings.notes.append(
                "dimension review found uncovered items: " + ", ".join(missing_items)
            )

    return reviewed, warnings


def extract_item_details(finished_texts: Iterable[FinishedTextItem], max_examples: int = 3) -> list[dict[str, Any]]:
    details: dict[str, list[str]] = {}
    for finished in finished_texts:
        for item in finished.items:
            for dimension in item_dimensions(item):
                if dimension not in details:
                    details[dimension] = []
                if item.reason and item.reason.strip():
                    reason = item.reason.strip()
                    if reason not in details[dimension]:
                        details[dimension].append(reason)

    return [
        {
            "label": dimension,
            "reasons": reasons[:max_examples],
        }
        for dimension, reasons in sorted(details.items())
    ]
