from __future__ import annotations

from typing import Any

from flex_agent.i18n import get_bundle


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def format_open_report(
    *,
    item_keyword: dict[str, Any] | None,
    item_semantic: dict[str, Any] | None,
    input_path: str,
    predicted_count: int,
    language: str | None = None,
) -> str:
    text = get_bundle(language).report
    sep = "=" * 72
    lines = [
        sep,
        text.direct_open_title,
        text.metrics_line,
        text.direct_input_line.format(input_path=input_path, predicted_count=predicted_count),
        sep,
    ]
    if item_keyword is not None:
        lines.extend(_format_section(text.open_keyword_section, item_keyword, language=language))
        lines.append("")
    if item_semantic is not None:
        lines.extend(_format_section(text.open_semantic_section, item_semantic, language=language))
        lines.append("")
    if item_keyword is None and item_semantic is None:
        lines.append(text.no_results)
    lines.append(sep)
    return "\n".join(lines)


def format_axial_report(
    *,
    item_keyword: dict[str, Any] | None,
    item_semantic: dict[str, Any] | None,
    input_path: str,
    predicted_count: int,
    human_category_count: int,
    agent_category_count: int,
    language: str | None = None,
) -> str:
    text = get_bundle(language).report
    sep = "=" * 72
    lines = [
        sep,
        text.direct_axial_title,
        text.metrics_line,
        text.direct_axial_granularity.format(
            agent_category_count=agent_category_count,
            human_category_count=human_category_count,
        ),
        text.direct_input_line.format(input_path=input_path, predicted_count=predicted_count),
        sep,
    ]
    if item_keyword is not None:
        lines.extend(_format_section(text.axial_keyword_section, item_keyword, language=language))
        lines.append("")
    if item_semantic is not None:
        lines.extend(_format_section(text.axial_semantic_section, item_semantic, language=language))
        lines.append("")
    if item_keyword is None and item_semantic is None:
        lines.append(text.no_results)
    lines.append(sep)
    return "\n".join(lines)


def _format_section(title: str, item_result: dict[str, Any], *, language: str | None = None) -> list[str]:
    text = get_bundle(language).report
    macro = item_result["macro"]
    lines = [
        title,
        "-" * 60,
        text.common_texts.format(common_texts=item_result["common_texts"]),
        "",
        text.metric_header,
        f"Consistency    {pct(macro['consistency']):>10}",
        f"Precision      {pct(macro['precision']):>10}",
        f"Recall         {pct(macro['recall']):>10}",
        "",
        text.counts.format(
            n_human=macro["n_human"],
            n_agent=macro["n_agent"],
            n_intersection=macro["n_intersection"],
            n_union=macro["n_union"],
        ),
    ]
    if "nums_both" in item_result:
        lines.append(
            text.three_way.format(
                both=item_result["nums_both"],
                llm_only=item_result["nums_llm_only"],
                human_only=item_result["nums_human_only"],
            )
        )
    return lines
