from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from .constants import HUMAN_CATEGORIES
from .inference import run_direct_batches
from .io import load_human_records, write_json, write_predictions_jsonl
from .llm import LLMClient, OpenAIChatClient, load_env_file
from .metrics import evaluate_axial, evaluate_open
from .report import format_axial_report, format_open_report
from flex_agent.i18n import set_language

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROMPT_PATH = PROJECT_ROOT / "direct_inference_eval" / "prompts" / "direct_batch.md"
DEFAULT_PROMPT_PATHS = {
    "zh": DEFAULT_PROMPT_PATH,
    "en": PROJECT_ROOT / "direct_inference_eval" / "prompts" / "direct_batch_en.md",
}


def run_experiment(
    *,
    input_path: Path,
    output_dir: Path,
    batch_size: int = 50,
    mode: Literal["open", "axial", "both"] = "both",
    limit: int | None = None,
    model: str | None = None,
    resume: bool = False,
    run_llm_semantic: bool = True,
    direct_client: LLMClient | None = None,
    semantic_client: LLMClient | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    load_env_file(PROJECT_ROOT / ".env")
    active_language = set_language(language)
    records = load_human_records(input_path, limit=limit)
    prompt_template = DEFAULT_PROMPT_PATHS[active_language].read_text(encoding="utf-8")
    client = direct_client or OpenAIChatClient(model=model)
    semantic = None
    if run_llm_semantic:
        semantic = semantic_client or direct_client or OpenAIChatClient(model=model)

    predictions, batch_reports = run_direct_batches(
        records,
        output_dir=output_dir,
        prompt_template=prompt_template,
        client=client,
        batch_size=batch_size,
        resume=resume,
    )
    records_path = output_dir / "predictions" / "records.jsonl"
    write_predictions_jsonl(records_path, predictions)
    write_json(
        output_dir / "predictions" / "batches_summary.json",
        {
            "input_path": str(input_path),
            "limit": limit,
            "batch_size": batch_size,
            "language": active_language,
            "batches": batch_reports,
            "predicted_texts": len(predictions),
        },
    )

    reports: list[Path] = []
    if mode in {"open", "both"}:
        open_payload = evaluate_open(records, predictions, semantic_client=semantic)
        open_dir = output_dir / "eval" / "open"
        _write_open_eval(open_dir, open_payload)
        open_summary = {
            "eval_kind": "open",
            "mode": "direct_inference",
            "status": "complete",
            "input_path": str(input_path),
            "predicted_count": len(predictions),
            "batch_size": batch_size,
            "language": active_language,
            "item_level_keyword": open_payload.get("item_level_keyword"),
        }
        if open_payload.get("item_level_semantic") is not None:
            open_summary["item_level_semantic"] = open_payload["item_level_semantic"]
        write_json(open_dir / "summary.json", open_summary)
        report = format_open_report(
            item_keyword=open_payload.get("item_level_keyword"),
            item_semantic=open_payload.get("item_level_semantic"),
            input_path=str(input_path),
            predicted_count=len(predictions),
            language=active_language,
        )
        report_path = open_dir / "report.txt"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        reports.append(report_path)

    if mode in {"axial", "both"}:
        axial_payload = evaluate_axial(predictions, semantic_client=semantic)
        axial_dir = output_dir / "eval" / "axial"
        global_payload = {"scope": "workspace", **axial_payload.get("global", {})}
        write_json(axial_dir / "global.json", global_payload)
        axial_summary = {
            "eval_kind": "axial",
            "mode": "direct_inference",
            "scope": "workspace",
            "status": "complete",
            "input_path": str(input_path),
            "predicted_count": len(predictions),
            "agent_category_count": axial_payload.get("agent_category_count", 0),
            "human_category_taxonomy": list(HUMAN_CATEGORIES),
            "language": active_language,
            "item_level_keyword": axial_payload.get("item_level_keyword"),
        }
        if axial_payload.get("item_level_semantic") is not None:
            axial_summary["item_level_semantic"] = axial_payload["item_level_semantic"]
        write_json(axial_dir / "summary.json", axial_summary)
        report = format_axial_report(
            item_keyword=axial_payload.get("item_level_keyword"),
            item_semantic=axial_payload.get("item_level_semantic"),
            input_path=str(input_path),
            predicted_count=len(predictions),
            human_category_count=len(HUMAN_CATEGORIES),
            agent_category_count=axial_payload.get("agent_category_count", 0),
            language=active_language,
        )
        report_path = axial_dir / "report.txt"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        reports.append(report_path)

    return {
        "records_path": records_path,
        "reports": reports,
        "predicted_count": len(predictions),
    }


def _write_open_eval(open_dir: Path, payload: dict[str, Any]) -> None:
    keyword_rows = {
        int(row["text_id"]): row
        for row in payload.get("item_level_keyword", {}).get("per_text", [])
    }
    semantic_rows = {
        int(row["text_id"]): row
        for row in payload.get("item_level_semantic", {}).get("per_text", [])
    }
    text_ids = sorted(set(keyword_rows) | set(semantic_rows))
    for text_id in text_ids:
        row_payload: dict[str, Any] = {"text_id": text_id}
        if text_id in keyword_rows:
            row_payload["keyword"] = keyword_rows[text_id]
        if text_id in semantic_rows:
            row_payload["semantic"] = semantic_rows[text_id]
        write_json(open_dir / f"{text_id}.json", row_payload)
