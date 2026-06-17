from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any, Literal

from flex_agent.config import build_llm, load_model_config
from flex_agent.eval.aggregate import aggregate_eval_results
from flex_agent.eval.async_utils import run_async
from flex_agent.eval.batch_semantic import batch_semantic_judge
from flex_agent.eval.core import ALL_HUMAN_DIMENSIONS, extract_agent_items
from flex_agent.eval.judge import judge_keyword
from flex_agent.eval.pairs import load_eval_pairs
from flex_agent.eval.report import format_open_coding_report
from flex_agent.eval.semantic import apply_semantic_alignment, build_dimension_name_alignment
from flex_agent.i18n import get_bundle, get_language
from flex_agent.workspace import Workspace

ProgressCallback = Callable[[str], None]


def _emit_progress(on_progress: ProgressCallback | None, message: str) -> None:
    if on_progress is not None:
        on_progress(message)


def _default_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)

def aggregate_workspace_eval(
    workspace: Workspace,
    *,
    mode: Literal["keyword", "semantic", "both"] = "both",
    save_json: bool = True,
    on_progress: ProgressCallback | None = _default_progress,
) -> str:
    """Recompute CPR from eval/open/{id}.json on disk (no LLM)."""
    language = get_language()
    progress = get_bundle(language).progress
    report_text = get_bundle(language).report
    if not workspace.eval_open_dir.exists():
        raise RuntimeError(progress.eval_no_results)

    agg = aggregate_eval_results(workspace.eval_open_dir)
    item_keyword = agg.get("item_level_keyword")
    item_semantic = agg.get("item_level_semantic")

    if mode == "keyword":
        item_semantic = None
    elif mode == "semantic":
        item_keyword = None

    summary = workspace.load_eval_summary("open") or {}
    coded_count = summary.get("coded_count", len(workspace.list_coded_ids()))
    benchmark_path = summary.get("benchmark_path", str(workspace.human_benchmark_path))

    report = format_open_coding_report(
        item_keyword=item_keyword,
        item_semantic=item_semantic,
        coded_count=coded_count,
        benchmark_path=benchmark_path,
        language=language,
    )

    if save_json:
        payload: dict[str, Any] = {
            "mode": mode,
            "align": summary.get("align", False),
            "status": "complete",
            "coded_count": coded_count,
            "benchmark_path": benchmark_path,
            "language": language,
        }
        if item_keyword is not None:
            payload["item_level_keyword"] = item_keyword
        if item_semantic is not None:
            payload["item_level_semantic"] = item_semantic

        output_path = workspace.save_eval_summary(
            "open",
            payload=payload,
            report=report,
            meta={
                "mode": mode,
                "align": summary.get("align", False),
                "status": "complete",
                "coded_count": coded_count,
                "benchmark_path": benchmark_path,
                "language": language,
                "keyword_complete": agg["keyword_complete"],
                "semantic_complete": agg["semantic_complete"],
            },
        )
        rel_summary = output_path.relative_to(workspace.root).as_posix()
        rel_report = workspace.eval_report_path("open").relative_to(workspace.root).as_posix()
        per_text_count = len(workspace.list_eval_text_ids("open"))
        _emit_progress(on_progress, progress.eval_aggregate_saved.format(path=rel_summary))
        report += "\n" + report_text.summary_saved.format(path=rel_summary)
        report += "\n" + report_text.report_saved.format(path=rel_report)
        report += "\n" + report_text.per_text_aggregated.format(count=per_text_count)

    return report


def evaluate_workspace(
    workspace: Workspace,
    *,
    mode: Literal["keyword", "semantic", "both", "metrics"] = "both",
    align: bool = False,
    concurrency_limit: int = 10,
    resume: bool = True,
    save_json: bool = True,
    on_progress: ProgressCallback | None = _default_progress,
) -> str:
    """Evaluate workspace open coding: align → judge per-text → aggregate CPR."""
    language = get_language()
    progress = get_bundle(language).progress
    report_text = get_bundle(language).report
    if mode == "metrics":
        return aggregate_workspace_eval(
            workspace,
            mode="both",
            save_json=save_json,
            on_progress=on_progress,
        )

    if not workspace.benchmark_ready():
        raise RuntimeError(progress.eval_benchmark_missing)

    coded_count = len(workspace.list_coded_ids())
    if coded_count == 0:
        raise RuntimeError(progress.eval_no_coded_texts)

    _emit_progress(on_progress, progress.eval_start.format(mode=mode, coded_count=coded_count))

    benchmark_path = workspace.human_benchmark_path
    _emit_progress(on_progress, progress.eval_load_benchmark.format(path=benchmark_path))
    pairs, agent_only = load_eval_pairs(workspace, benchmark_path=benchmark_path)
    _emit_progress(
        on_progress,
        progress.eval_aligned_pairs.format(
            pairs=len(pairs),
            coded_count=coded_count,
            human_count=len(pairs),
            agent_only=agent_only,
        ),
    )

    if not pairs:
        raise RuntimeError(progress.eval_no_pairs)

    agent_items = extract_agent_items([
        {"id": pair.text_id, "items": pair.agent_items_raw} for pair in pairs
    ])

    if align:
        all_agent_dims = sorted({dim for items in agent_items.values() for dim in items})
        unmatched = [d for d in all_agent_dims if d not in ALL_HUMAN_DIMENSIONS]
        if unmatched:
            _emit_progress(
                on_progress,
                progress.eval_dimension_mapping.format(count=len(unmatched)),
            )
            model_cfg = load_model_config()
            llm = build_llm(
                model_cfg.default_model,
                timeout=120.0,
                max_retries=model_cfg.max_retries,
                seed=model_cfg.seed,
            )
            alignment = build_dimension_name_alignment(unmatched, ALL_HUMAN_DIMENSIONS, llm)
            agent_items = apply_semantic_alignment(agent_items, alignment)

    workspace.eval_open_dir.mkdir(parents=True, exist_ok=True)

    if mode in {"keyword", "both"}:
        _emit_progress(on_progress, progress.eval_keyword_running)
        for pair in pairs:
            keyword = judge_keyword(pair, agent_items=agent_items.get(pair.text_id))
            existing = workspace.load_eval_text("open", pair.text_id) or {"text_id": pair.text_id}
            existing["keyword"] = keyword
            workspace.save_eval_text("open", pair.text_id, existing)
        _emit_progress(
            on_progress,
            progress.eval_keyword_written.format(count=len(pairs)),
        )
        agg = aggregate_eval_results(workspace.eval_open_dir)
        if agg.get("item_level_keyword"):
            macro = agg["item_level_keyword"]["macro"]
            _emit_progress(
                on_progress,
                progress.eval_keyword_macro.format(
                    consistency=macro["consistency"],
                    precision=macro["precision"],
                    recall=macro["recall"],
                ),
            )

    if mode in {"semantic", "both"}:
        model_cfg = load_model_config()
        align_llm = build_llm(
            model_cfg.default_model,
            timeout=180.0,
            max_retries=model_cfg.max_retries,
            seed=model_cfg.seed,
        )
        run_async(
            batch_semantic_judge(
                workspace,
                pairs,
                align_llm,
                resume=resume,
                concurrency_limit=concurrency_limit,
                on_progress=lambda msg: _emit_progress(on_progress, msg),
            )
        )
        agg = aggregate_eval_results(workspace.eval_open_dir)
        if agg.get("item_level_semantic"):
            macro = agg["item_level_semantic"]["macro"]
            _emit_progress(
                on_progress,
                progress.eval_semantic_macro.format(
                    consistency=macro["consistency"],
                    precision=macro["precision"],
                    recall=macro["recall"],
                    complete=agg["semantic_complete"],
                    total=len(pairs),
                ),
            )

    _emit_progress(on_progress, progress.eval_generating_report)
    agg = aggregate_eval_results(workspace.eval_open_dir)
    item_keyword = agg.get("item_level_keyword") if mode in {"keyword", "both"} else None
    item_semantic = agg.get("item_level_semantic") if mode in {"semantic", "both"} else None

    report = format_open_coding_report(
        item_keyword=item_keyword,
        item_semantic=item_semantic,
        coded_count=coded_count,
        benchmark_path=str(benchmark_path),
        language=language,
    )

    if save_json:
        payload: dict[str, Any] = {
            "mode": mode,
            "align": align,
            "status": "complete",
            "coded_count": coded_count,
            "benchmark_path": str(benchmark_path),
            "language": language,
        }
        if item_keyword is not None:
            payload["item_level_keyword"] = item_keyword
        if item_semantic is not None:
            payload["item_level_semantic"] = item_semantic

        output_path = workspace.save_eval_summary(
            "open",
            payload=payload,
            report=report,
            meta={
                "mode": mode,
                "align": align,
                "status": "complete",
                "coded_count": coded_count,
                "benchmark_path": str(benchmark_path),
                "language": language,
                "keyword_complete": agg["keyword_complete"],
                "semantic_complete": agg["semantic_complete"],
            },
        )
        rel_summary = output_path.relative_to(workspace.root).as_posix()
        rel_report = workspace.eval_report_path("open").relative_to(workspace.root).as_posix()
        per_text_count = len(workspace.list_eval_text_ids("open"))
        _emit_progress(on_progress, progress.eval_saved.format(path=rel_summary))
        report += "\n" + report_text.summary_saved.format(path=rel_summary)
        report += "\n" + report_text.report_saved.format(path=rel_report)
        report += "\n" + report_text.per_text_written.format(count=per_text_count)

    _emit_progress(on_progress, progress.eval_complete)
    return report
