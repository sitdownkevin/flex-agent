"""Async per-text semantic judging (Bob-style concurrency)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from flex_agent.eval.aggregate import aggregate_eval_results
from flex_agent.eval.judge import judge_semantic
from flex_agent.eval.pairs import EvalPair
from flex_agent.i18n import get_bundle
from flex_agent.workspace import Workspace

ProgressCallback = Callable[[str], None]


def _semantic_status(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    semantic = payload.get("semantic")
    if not isinstance(semantic, dict):
        return None
    return semantic.get("status")


async def batch_semantic_judge(
    workspace: Workspace,
    pairs: list[EvalPair],
    llm: BaseChatModel,
    *,
    resume: bool = True,
    concurrency_limit: int = 10,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Run semantic LLM judge per text with concurrency; skip complete when resuming."""
    pending: list[EvalPair] = []
    skipped = 0
    for pair in pairs:
        if resume:
            existing = workspace.load_eval_text("open", pair.text_id)
            if _semantic_status(existing) == "complete":
                skipped += 1
                continue
        pending.append(pair)

    total_pairs = len(pairs)
    progress = get_bundle().progress
    if on_progress is not None:
        on_progress(
            progress.semantic_pending.format(pending=len(pending))
            + (
                progress.semantic_pending_skipped_suffix.format(skipped=skipped)
                if skipped
                else ""
            )
        )

    if not pending:
        return {"judged": 0, "skipped": skipped, "failed": 0}

    sem = asyncio.Semaphore(max(1, concurrency_limit))
    judged = 0
    failed = 0
    lock = asyncio.Lock()

    async def _judge_one(pair: EvalPair) -> None:
        nonlocal judged, failed
        async with sem:
            existing = workspace.load_eval_text("open", pair.text_id) or {"text_id": pair.text_id}
            try:
                semantic = await asyncio.to_thread(judge_semantic, pair, llm)
            except Exception as exc:
                semantic = {
                    "text_id": pair.text_id,
                    "status": "failed",
                    "error": repr(exc),
                    "both": [],
                    "llm_only": [],
                    "human_only": [],
                    "nums_both": 0,
                    "nums_llm_only": 0,
                    "nums_human_only": 0,
                    "consistency": 0.0,
                    "precision": 0.0,
                    "recall": 0.0,
                    "alignment": {},
                }
                if on_progress is not None:
                    on_progress(progress.semantic_skip.format(text_id=pair.text_id, error=exc))

            existing["semantic"] = semantic
            workspace.save_eval_text("open", pair.text_id, existing)

            async with lock:
                if semantic.get("status") == "complete":
                    judged += 1
                else:
                    failed += 1
                done = judged + failed
                agg = aggregate_eval_results(workspace.eval_open_dir)
                semantic_agg = agg.get("item_level_semantic")
                if on_progress is not None and semantic_agg:
                    micro = semantic_agg["micro"]
                    complete = agg["semantic_complete"]
                    on_progress(
                        progress.semantic_progress.format(
                            done=done,
                            pending=len(pending),
                            complete=complete,
                            total=total_pairs,
                            consistency=micro["consistency"],
                            precision=micro["precision"],
                            recall=micro["recall"],
                        )
                    )

    await asyncio.gather(*(_judge_one(pair) for pair in pending))
    return {"judged": judged, "skipped": skipped, "failed": failed}
