from __future__ import annotations

from typing import Any

from flex_agent.i18n import get_bundle


def _pct(val: float) -> str:
    return f"{val * 100:.1f}%"


def _format_metric_rows(item_result: dict[str, Any]) -> list[str]:
    macro = item_result["macro"]
    micro = item_result.get("micro", macro)
    return [
        f"Consistency    {_pct(macro['consistency']):>10} {_pct(micro['consistency']):>10}",
        f"Precision      {_pct(macro['precision']):>10} {_pct(micro['precision']):>10}",
        f"Recall         {_pct(macro['recall']):>10} {_pct(micro['recall']):>10}",
    ]


def _format_item_section(title: str, item_result: dict[str, Any], *, language: str | None = None) -> list[str]:
    text = get_bundle(language).report
    macro = item_result["macro"]
    lines = [
        title,
        "-" * 60,
        text.common_texts.format(common_texts=item_result["common_texts"]),
        text.human_agent_only.format(
            human_only=item_result.get("skipped_human_only", 0),
            agent_only=item_result.get("skipped_agent_only", 0),
        ),
        "",
        text.metric_header,
        *_format_metric_rows(item_result),
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


def format_open_coding_report(
    *,
    item_keyword: dict[str, Any] | None,
    item_semantic: dict[str, Any] | None,
    coded_count: int,
    benchmark_path: str,
    language: str | None = None,
) -> str:
    text = get_bundle(language).report
    sep = "=" * 72
    lines = [
        sep,
        text.open_title,
        text.metrics_line,
        text.coded_and_benchmark.format(coded_count=coded_count, benchmark_path=benchmark_path),
        sep,
    ]

    if item_keyword is not None:
        lines.extend(_format_item_section(text.open_keyword_section, item_keyword, language=language))
        lines.append("")

    if item_semantic is not None:
        lines.extend(_format_item_section(text.open_semantic_section, item_semantic, language=language))
        lines.append("")

    if item_keyword is None and item_semantic is None:
        lines.append(text.no_results)

    lines.append(sep)
    return "\n".join(lines)


def _format_axial_section(title: str, item_result: dict[str, Any], *, language: str | None = None) -> list[str]:
    text = get_bundle(language).report
    macro = item_result["macro"]
    lines = [
        title,
        "-" * 60,
        text.axial_granularity,
        "",
        text.metric_header,
        *_format_metric_rows(item_result),
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


def format_axial_coding_report(
    *,
    item_keyword: dict[str, Any] | None,
    item_semantic: dict[str, Any] | None,
    coded_count: int,
    benchmark_path: str,
    codebook_dimensions_count: int,
    human_category_count: int = 7,
    language: str | None = None,
) -> str:
    text = get_bundle(language).report
    sep = "=" * 72
    lines = [
        sep,
        text.axial_title,
        text.metrics_line,
        text.axial_header_granularity.format(
            codebook_dimensions_count=codebook_dimensions_count,
            human_category_count=human_category_count,
        ),
        text.coded_and_benchmark.format(coded_count=coded_count, benchmark_path=benchmark_path),
        sep,
    ]

    if item_keyword is not None:
        lines.extend(_format_axial_section(text.axial_keyword_section, item_keyword, language=language))
        lines.append("")

    if item_semantic is not None:
        lines.extend(_format_axial_section(text.axial_semantic_section, item_semantic, language=language))
        lines.append("")

    if item_keyword is None and item_semantic is None:
        lines.append(text.no_results)

    lines.append(sep)
    return "\n".join(lines)
