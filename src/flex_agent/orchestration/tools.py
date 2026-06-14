from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from flex_agent.coding.agents import PromptContext, arun_alice, arun_bob, arun_kevin
from flex_agent.coding.export import export_open_coding_result
from flex_agent.coding.quality import (
    QualityWarnings,
    extract_item_details,
    extract_item_pool,
    normalize_finished_text,
    review_dimensions,
)
from flex_agent.config import build_llm, load_model_config
from flex_agent.models import DimensionDetail, FinishedItemDetail, FinishedTextItem
from flex_agent.workspace import Workspace


class InitRunInput(BaseModel):
    data_path: str = Field(
        description=(
            "Path to source jsonl with a comments/content field per line "
            "(e.g. /corpus/codebook_done.jsonl). Do not pass corpus/raw.jsonl."
        ),
    )
    max_nums: int = Field(default=10, description="Maximum number of texts to process.")
    codebook_nums: int = Field(default=5, description="Number of texts for Alice codebook sample.")
    kevin_batch_size: int = Field(default=5, description="Kevin batch size.")
    sample_mode: str = Field(default="sequential", description="sequential or random sampling.")
    random_seed: int | None = Field(default=None, description="Random seed for sampling/partition.")
    open_mode: str = Field(default="pure", description="Open coding mode label for export metadata.")


class BatchBobInput(BaseModel):
    text_ids: list[int] | None = Field(
        default=None,
        description="Optional explicit text ids. Defaults to all texts in queue.",
    )
    concurrency_limit: int = Field(default=10, description="Max concurrent Bob calls.")


class KevinBatchInput(BaseModel):
    batch_index: int | None = Field(
        default=None,
        description="1-based Kevin batch index. If omitted, runs all Kevin batches sequentially.",
    )


class ExportInput(BaseModel):
    pass


@dataclass
class CodingToolContext:
    workspace: Workspace
    llm: BaseChatModel
    llm_pro: BaseChatModel
    prompt_ctx: PromptContext = field(default_factory=PromptContext.load)


def _chunked(ids: list[int], size: int) -> list[list[int]]:
    chunk_size = max(1, size)
    return [ids[idx : idx + chunk_size] for idx in range(0, len(ids), chunk_size)]


def _tool_error(tool_name: str, exc: BaseException) -> str:
    return f"{tool_name} failed: {type(exc).__name__}: {exc}"


def build_coding_tools(ctx: CodingToolContext) -> list[StructuredTool]:
    async def init_open_coding_run(
        data_path: str,
        max_nums: int = 10,
        codebook_nums: int = 5,
        kevin_batch_size: int = 5,
        sample_mode: str = "sequential",
        random_seed: int | None = None,
        open_mode: str = "pure",
    ) -> str:
        try:
            resolved = ctx.workspace.resolve_data_path(data_path)
            meta = ctx.workspace.init_run(
                data_path=resolved,
                max_nums=max_nums,
                codebook_nums=codebook_nums,
                kevin_batch_size=kevin_batch_size,
                sample_mode=sample_mode,
                random_seed=random_seed,
                open_mode=open_mode,
            )
            partition = ctx.workspace.load_partition()
            return (
                f"Initialized run with {meta.max_nums} texts, "
                f"codebook={len(partition.codebook_text_ids)}, "
                f"kevin={len(partition.kevin_text_ids)}."
            )
        except Exception as exc:
            return _tool_error("init_open_coding_run", exc)

    async def batch_bob_code(
        text_ids: list[int] | None = None,
        concurrency_limit: int = 10,
    ) -> str:
        texts = {text.id: text for text in ctx.workspace.load_texts()}
        target_ids = text_ids or ctx.workspace.load_queue()
        if not target_ids:
            return "No texts to code."

        sem = asyncio.Semaphore(max(1, concurrency_limit))
        warnings = QualityWarnings()
        coded = 0
        skipped: list[int] = []

        async def _code_one(text_id: int) -> None:
            nonlocal coded
            text = texts.get(text_id)
            if text is None:
                skipped.append(text_id)
                return
            async with sem:
                try:
                    output = await arun_bob(ctx.llm, ctx.prompt_ctx, text)
                except Exception as exc:
                    skipped.append(text_id)
                    warnings.notes.append(f"bob skipped text_id={text_id}: {exc!r}")
                    return

            finished = FinishedTextItem(
                id=text.id,
                content=text.content,
                content_with_labels=output.content_with_labels,
                items=[
                    FinishedItemDetail(
                        name=item.name,
                        evidence=item.evidence,
                        normalized_label=item.normalized_label,
                        reason=item.reason,
                    )
                    for item in output.items
                ],
            )
            normalized, item_warnings = normalize_finished_text(finished)
            warnings.add(item_warnings)
            ctx.workspace.save_coding(normalized)
            coded += 1

        await asyncio.gather(*(_code_one(text_id) for text_id in target_ids))
        remaining = [text_id for text_id in ctx.workspace.load_queue() if text_id not in ctx.workspace.list_coded_ids()]
        ctx.workspace.save_queue(remaining)
        ctx.workspace.merge_warnings(warnings.as_dict())
        return (
            f"Bob coded {coded}/{len(target_ids)} texts. "
            f"Skipped={skipped}. Remaining queue={len(remaining)}."
        )

    async def run_alice_codebook() -> str:
        partition = ctx.workspace.load_partition()
        finished = [
            item
            for item in ctx.workspace.load_finished_texts()
            if item.id in set(partition.codebook_text_ids)
        ]
        items_pool = extract_item_pool(finished)
        if not items_pool:
            ctx.workspace.save_dimensions([])
            return "Alice skipped: empty item pool."

        items_details = extract_item_details(finished)
        try:
            alice_output = await arun_alice(
                ctx.llm_pro,
                ctx.prompt_ctx,
                items_pool,
                items_details=items_details,
            )
        except Exception as exc:
            return _tool_error("run_alice_codebook", exc)

        candidate = [
            DimensionDetail(name=item.name, items=list(item.items), definition=item.definition)
            for item in alice_output.dimensions
            if item.items
        ]
        if not candidate:
            return _tool_error(
                "run_alice_codebook",
                RuntimeError("Alice returned no non-empty dimensions."),
            )

        reviewed, review_warnings = review_dimensions(candidate, finished)
        ctx.workspace.save_dimensions(reviewed)
        ctx.workspace.merge_warnings(review_warnings.as_dict())
        return f"Alice wrote {len(reviewed)} dimensions to codebook/dimensions.json."

    async def run_kevin_batches(batch_index: int | None = None) -> str:
        meta = ctx.workspace.load_run_meta()
        if meta is None:
            return "Run not initialized."

        partition = ctx.workspace.load_partition()
        id_to_finished = {item.id: item for item in ctx.workspace.load_finished_texts()}
        kevin_source_ids = [
            text_id for text_id in partition.kevin_text_ids if text_id in id_to_finished
        ]
        batches = _chunked(kevin_source_ids, meta.kevin_batch_size)
        if not batches:
            return "No Kevin batches to process."

        if batch_index is not None:
            if batch_index < 1 or batch_index > len(batches):
                return f"Invalid batch_index={batch_index}; valid range 1..{len(batches)}."
            batches = [batches[batch_index - 1]]
            start_idx = batch_index
        else:
            start_idx = 1

        current = ctx.workspace.load_dimensions()
        node_warnings = QualityWarnings()
        processed = 0

        for offset, batch_ids in enumerate(batches, start=start_idx):
            batch_finished = [id_to_finished[text_id] for text_id in batch_ids]
            items_pool = extract_item_pool(batch_finished)
            if not items_pool:
                continue
            items_details = extract_item_details(batch_finished)
            try:
                output = await arun_kevin(
                    ctx.llm_pro,
                    ctx.prompt_ctx,
                    list(current),
                    items_pool,
                    items_details=items_details,
                )
            except Exception as exc:
                node_warnings.notes.append(f"kevin batch {offset} skipped: {exc!r}")
                continue

            candidate = [
                DimensionDetail(name=item.name, items=list(item.items), definition=item.definition)
                for item in output.dimensions
                if item.items
            ]
            reviewed, warnings = review_dimensions(candidate, finished_texts=None)
            node_warnings.add(warnings)
            if reviewed:
                current = reviewed
                ctx.workspace.save_dimensions(current)
                ctx.workspace.save_codebook_batch(offset, current)
                processed += 1

        final_reviewed, final_warnings = review_dimensions(
            current,
            ctx.workspace.load_finished_texts(),
        )
        node_warnings.add(final_warnings)
        ctx.workspace.save_dimensions(final_reviewed)
        ctx.workspace.merge_warnings(node_warnings.as_dict())
        ctx.workspace.save_queue([])
        return f"Kevin processed {processed} batch(es); dimensions={len(final_reviewed)}."

    async def export_result() -> str:
        meta = ctx.workspace.load_run_meta()
        if meta is None:
            return "Run not initialized; nothing to export."
        output_path = export_open_coding_result(ctx.workspace)
        return f"Exported gt-agent compatible result to {output_path}."

    async def workspace_status() -> str:
        import json

        return json.dumps(ctx.workspace.status(), ensure_ascii=False, indent=2)

    return [
        StructuredTool.from_function(
            coroutine=init_open_coding_run,
            name="init_open_coding_run",
            description="Initialize corpus, partition, queue, and empty codebook in workspace files.",
            args_schema=InitRunInput,
        ),
        StructuredTool.from_function(
            coroutine=batch_bob_code,
            name="batch_bob_code",
            description="Concurrently run Bob coding for text ids and write coding/{id}.json files.",
            args_schema=BatchBobInput,
        ),
        StructuredTool.from_function(
            coroutine=run_alice_codebook,
            name="run_alice_codebook",
            description="Build initial dimensions from codebook sample and write codebook/dimensions.json.",
        ),
        StructuredTool.from_function(
            coroutine=run_kevin_batches,
            name="run_kevin_batches",
            description="Incrementally update codebook from Kevin batches and write batch snapshots.",
            args_schema=KevinBatchInput,
        ),
        StructuredTool.from_function(
            coroutine=export_result,
            name="export_result",
            description="Aggregate workspace files into gt-agent compatible exports/open_coding_result_*.json.",
            args_schema=ExportInput,
        ),
        StructuredTool.from_function(
            coroutine=workspace_status,
            name="workspace_status",
            description="Return current workspace counters and run metadata as JSON.",
        ),
    ]


def create_coding_tool_context(workspace: Workspace) -> CodingToolContext:
    model_cfg = load_model_config()
    llm = build_llm(
        model_cfg.default_model,
        timeout=model_cfg.timeout,
        max_retries=model_cfg.max_retries,
        seed=model_cfg.seed,
    )
    llm_pro = build_llm(
        model_cfg.pro_model,
        timeout=model_cfg.timeout,
        max_retries=model_cfg.max_retries,
        seed=model_cfg.seed,
    )
    return CodingToolContext(workspace=workspace, llm=llm, llm_pro=llm_pro)
