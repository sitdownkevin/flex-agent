from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from flex_agent.config import build_llm, load_model_config
from flex_agent.eval.axial_aggregate import (
    AXIAL_GLOBAL_RESULT_NAME,
    aggregate_axial_global_payload,
    axial_global_result_path,
    load_axial_global_payload,
)
from flex_agent.eval.axial_core import HUMAN_CATEGORIES, human_category_taxonomy
from flex_agent.eval.axial_judge import (
    apply_axial_alignment_to_dims,
    judge_axial_global_keyword,
    judge_axial_global_semantic,
)
from flex_agent.eval.axial_pairs import load_axial_global_eval
from flex_agent.eval.report import format_axial_coding_report
from flex_agent.eval.semantic import build_dimension_name_alignment
from flex_agent.i18n import get_bundle, get_language
from flex_agent.workspace import Workspace

ProgressCallback = Callable[[str], None]


def _emit_progress(on_progress: ProgressCallback | None, message: str) -> None:
    if on_progress is not None:
        on_progress(message)


def _default_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _write_axial_global_result(eval_dir: Path, payload: dict[str, Any]) -> Path:
    eval_dir.mkdir(parents=True, exist_ok=True)
    for path in eval_dir.glob("*.json"):
        if path.name in {AXIAL_GLOBAL_RESULT_NAME, "summary.json"}:
            continue
        try:
            int(path.stem)
        except ValueError:
            continue
        path.unlink(missing_ok=True)
    output_path = axial_global_result_path(eval_dir)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def aggregate_axial_workspace_eval(
    workspace: Workspace,
    *,
    mode: Literal["keyword", "semantic", "both"] = "both",
    save_json: bool = True,
    on_progress: ProgressCallback | None = _default_progress,
) -> str:
    """Recompute CPR from eval/axial/global.json on disk (no LLM)."""
    language = get_language()
    progress = get_bundle(language).progress
    report_text = get_bundle(language).report
    global_payload = load_axial_global_payload(workspace.eval_axial_dir)
    if global_payload is None:
        raise RuntimeError(progress.axial_no_results)

    agg = aggregate_axial_global_payload(global_payload)
    item_keyword = agg.get("item_level_keyword")
    item_semantic = agg.get("item_level_semantic")

    if mode == "keyword":
        item_semantic = None
    elif mode == "semantic":
        item_keyword = None

    summary = workspace.load_eval_summary("axial") or {}
    coded_count = summary.get("coded_count", len(workspace.list_coded_ids()))
    benchmark_path = summary.get("benchmark_path", str(workspace.human_benchmark_path))
    codebook_dimensions_count = summary.get(
        "codebook_dimensions_count",
        len(workspace.load_dimensions()),
    )

    report = format_axial_coding_report(
        item_keyword=item_keyword,
        item_semantic=item_semantic,
        coded_count=coded_count,
        benchmark_path=benchmark_path,
        codebook_dimensions_count=codebook_dimensions_count,
        human_category_count=len(human_category_taxonomy()),
        language=language,
    )

    if save_json:
        payload: dict[str, Any] = {
            "eval_kind": "axial",
            "scope": "workspace",
            "mode": mode,
            "align": summary.get("align", False),
            "status": "complete",
            "coded_count": coded_count,
            "benchmark_path": benchmark_path,
            "codebook_dimensions_count": codebook_dimensions_count,
            "human_category_taxonomy": list(HUMAN_CATEGORIES),
            "language": language,
        }
        if item_keyword is not None:
            payload["item_level_keyword"] = item_keyword
        if item_semantic is not None:
            payload["item_level_semantic"] = item_semantic

        output_path = workspace.save_eval_summary(
            "axial",
            payload=payload,
            report=report,
            meta={
                "eval_kind": "axial",
                "scope": "workspace",
                "mode": mode,
                "align": summary.get("align", False),
                "status": "complete",
                "coded_count": coded_count,
                "benchmark_path": benchmark_path,
                "codebook_dimensions_count": codebook_dimensions_count,
                "language": language,
                "keyword_complete": agg["keyword_complete"],
                "semantic_complete": agg["semantic_complete"],
            },
        )
        rel_summary = output_path.relative_to(workspace.root).as_posix()
        rel_report = workspace.eval_report_path("axial").relative_to(workspace.root).as_posix()
        _emit_progress(on_progress, progress.axial_aggregate_saved.format(path=rel_summary))
        report += "\n" + report_text.summary_saved.format(path=rel_summary)
        report += "\n" + report_text.report_saved.format(path=rel_report)
        report += "\n" + report_text.axial_global_result.format(name=AXIAL_GLOBAL_RESULT_NAME)

    return report


def evaluate_axial_workspace(
    workspace: Workspace,
    *,
    mode: Literal["keyword", "semantic", "both", "metrics"] = "both",
    align: bool = False,
    concurrency_limit: int = 10,
    resume: bool = True,
    save_json: bool = True,
    on_progress: ProgressCallback | None = _default_progress,
) -> str:
    """Evaluate workspace axial coding once: codebook dimensions vs human categories."""
    del concurrency_limit  # global eval uses a single semantic LLM call
    language = get_language()
    progress = get_bundle(language).progress
    report_text = get_bundle(language).report

    if mode == "metrics":
        return aggregate_axial_workspace_eval(
            workspace,
            mode="both",
            save_json=save_json,
            on_progress=on_progress,
        )

    if not workspace.benchmark_ready():
        raise RuntimeError(progress.eval_benchmark_missing)

    dimensions = workspace.load_dimensions()
    if not dimensions:
        raise RuntimeError(progress.axial_no_dimensions)

    ctx = load_axial_global_eval(workspace)
    if not ctx.agent_axial_dims:
        raise RuntimeError(progress.axial_no_valid_dimensions)

    coded_count = len(workspace.list_coded_ids())
    benchmark_path = workspace.human_benchmark_path
    human_categories = sorted(ctx.human_categories)
    agent_dims = set(ctx.agent_axial_dims)

    _emit_progress(
        on_progress,
        progress.axial_start.format(
            mode=mode,
            agent_count=len(agent_dims),
            human_count=len(human_categories),
        ),
    )

    if align:
        sorted_agent = sorted(agent_dims)
        if sorted_agent:
            _emit_progress(
                on_progress,
                progress.axial_category_mapping.format(count=len(sorted_agent)),
            )
            model_cfg = load_model_config()
            llm = build_llm(
                model_cfg.default_model,
                timeout=120.0,
                max_retries=model_cfg.max_retries,
                seed=model_cfg.seed,
            )
            alignment = build_dimension_name_alignment(sorted_agent, human_categories, llm)
            agent_dims = apply_axial_alignment_to_dims(
                agent_dims,
                alignment,
                human_categories=set(human_categories),
            )

    workspace.eval_axial_dir.mkdir(parents=True, exist_ok=True)
    global_payload: dict[str, Any] = {"scope": "workspace"}

    existing = load_axial_global_payload(workspace.eval_axial_dir) or {}

    if mode in {"keyword", "both"}:
        _emit_progress(on_progress, progress.axial_keyword_running)
        keyword = judge_axial_global_keyword(ctx, agent_dims=agent_dims)
        global_payload["keyword"] = keyword
        metrics = keyword
        _emit_progress(
            on_progress,
            progress.axial_keyword_macro.format(
                consistency=metrics["consistency"],
                precision=metrics["precision"],
                recall=metrics["recall"],
            ),
        )
    elif resume and existing.get("keyword"):
        global_payload["keyword"] = existing["keyword"]

    if mode in {"semantic", "both"}:
        if resume and existing.get("semantic", {}).get("status") == "complete":
            _emit_progress(on_progress, progress.axial_semantic_skip_complete)
            global_payload["semantic"] = existing["semantic"]
        else:
            _emit_progress(on_progress, progress.axial_semantic_running)
            model_cfg = load_model_config()
            align_llm = build_llm(
                model_cfg.default_model,
                timeout=180.0,
                max_retries=model_cfg.max_retries,
                seed=model_cfg.seed,
            )
            semantic = judge_axial_global_semantic(ctx, align_llm)
            global_payload["semantic"] = semantic
            _emit_progress(
                on_progress,
                progress.axial_semantic_macro.format(
                    consistency=semantic["consistency"],
                    precision=semantic["precision"],
                    recall=semantic["recall"],
                ),
            )
    elif resume and existing.get("semantic"):
        global_payload["semantic"] = existing["semantic"]

    _write_axial_global_result(workspace.eval_axial_dir, global_payload)

    _emit_progress(on_progress, progress.axial_generating_report)
    agg = aggregate_axial_global_payload(global_payload)
    item_keyword = agg.get("item_level_keyword") if mode in {"keyword", "both"} else None
    item_semantic = agg.get("item_level_semantic") if mode in {"semantic", "both"} else None

    report = format_axial_coding_report(
        item_keyword=item_keyword,
        item_semantic=item_semantic,
        coded_count=coded_count,
        benchmark_path=str(benchmark_path),
        codebook_dimensions_count=len(dimensions),
        human_category_count=len(human_categories),
        language=language,
    )

    if save_json:
        payload: dict[str, Any] = {
            "eval_kind": "axial",
            "scope": "workspace",
            "mode": mode,
            "align": align,
            "status": "complete",
            "coded_count": coded_count,
            "benchmark_path": str(benchmark_path),
            "codebook_dimensions_count": len(dimensions),
            "human_category_taxonomy": list(HUMAN_CATEGORIES),
            "language": language,
        }
        if item_keyword is not None:
            payload["item_level_keyword"] = item_keyword
        if item_semantic is not None:
            payload["item_level_semantic"] = item_semantic

        output_path = workspace.save_eval_summary(
            "axial",
            payload=payload,
            report=report,
            meta={
                "eval_kind": "axial",
                "scope": "workspace",
                "mode": mode,
                "align": align,
                "status": "complete",
                "coded_count": coded_count,
                "benchmark_path": str(benchmark_path),
                "codebook_dimensions_count": len(dimensions),
                "language": language,
                "keyword_complete": agg["keyword_complete"],
                "semantic_complete": agg["semantic_complete"],
            },
        )
        rel_summary = output_path.relative_to(workspace.root).as_posix()
        rel_report = workspace.eval_report_path("axial").relative_to(workspace.root).as_posix()
        _emit_progress(on_progress, progress.axial_saved.format(path=rel_summary))
        report += "\n" + report_text.summary_saved.format(path=rel_summary)
        report += "\n" + report_text.report_saved.format(path=rel_report)
        report += "\n" + report_text.axial_global_result.format(name=AXIAL_GLOBAL_RESULT_NAME)

    _emit_progress(on_progress, progress.axial_complete)
    return report
