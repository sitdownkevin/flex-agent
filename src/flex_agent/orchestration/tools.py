from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from flex_agent.coding.agents import PromptContext, arun_alice, arun_bob, arun_kevin
from flex_agent.coding.export import export_open_coding_result
from flex_agent.coding.quality import (
    QualityWarnings,
    extract_item_details,
    extract_item_pool,
    normalize_finished_text,
    review_dimensions,
)
from flex_agent.config import build_llm, get_prompts_dir, load_model_config, path_label
from flex_agent.i18n import Language, get_bundle, get_language, resolve_language
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


@dataclass(frozen=True)
class ToolInputSchemas:
    init_run: type[BaseModel]
    batch_bob: type[BaseModel]
    kevin_batch: type[BaseModel]


def _tool_input_schemas(language: str | None = None) -> ToolInputSchemas:
    descriptions = get_bundle(language).llm.tool_arg_descriptions
    suffix = "Zh" if (resolve_language(language) if language is not None else get_language()) == "zh" else "En"
    init_run = create_model(
        f"InitRunInput{suffix}",
        data_path=(str, Field(description=descriptions["data_path"])),
        max_nums=(int, Field(default=10, description=descriptions["max_nums"])),
        codebook_nums=(int, Field(default=5, description=descriptions["codebook_nums"])),
        kevin_batch_size=(int, Field(default=5, description=descriptions["kevin_batch_size"])),
        sample_mode=(str, Field(default="sequential", description=descriptions["sample_mode"])),
        random_seed=(int | None, Field(default=None, description=descriptions["random_seed"])),
        open_mode=(str, Field(default="pure", description=descriptions["open_mode"])),
    )
    batch_bob = create_model(
        f"BatchBobInput{suffix}",
        text_ids=(list[int] | None, Field(default=None, description=descriptions["text_ids"])),
        concurrency_limit=(int, Field(default=10, description=descriptions["concurrency_limit"])),
    )
    kevin_batch = create_model(
        f"KevinBatchInput{suffix}",
        batch_index=(int | None, Field(default=None, description=descriptions["batch_index"])),
    )
    return ToolInputSchemas(init_run=init_run, batch_bob=batch_bob, kevin_batch=kevin_batch)


ProgressCallback = Callable[[str], None]


def _default_bob_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


@dataclass
class CodingToolContext:
    workspace: Workspace
    llm: BaseChatModel
    llm_pro: BaseChatModel
    prompt_ctx: PromptContext
    prompts_dir_label: str
    workspace_dir_label: str
    language: Language = "zh"
    on_progress: ProgressCallback | None = _default_bob_progress


def _chunked(ids: list[int], size: int) -> list[list[int]]:
    chunk_size = max(1, size)
    return [ids[idx : idx + chunk_size] for idx in range(0, len(ids), chunk_size)]


def _tool_error(tool_name: str, exc: BaseException) -> str:
    return f"{tool_name} failed: {type(exc).__name__}: {exc}"


def build_coding_tools(ctx: CodingToolContext) -> list[StructuredTool]:
    bundle = get_bundle(ctx.language)
    progress = bundle.progress

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
                prompts_dir=ctx.prompts_dir_label,
                workspace_dir=ctx.workspace_dir_label,
                language=ctx.language,
            )
            partition = ctx.workspace.load_partition()
            return progress.initialized_run.format(
                max_nums=meta.max_nums,
                codebook=len(partition.codebook_text_ids),
                kevin=len(partition.kevin_text_ids),
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
            return progress.no_texts_to_code

        total = len(target_ids)
        limit = max(1, concurrency_limit)
        sem = asyncio.Semaphore(limit)
        lock = asyncio.Lock()
        warnings = QualityWarnings()
        coded = 0
        skipped: list[int] = []

        def _emit(message: str) -> None:
            if ctx.on_progress is not None:
                ctx.on_progress(message)

        _emit(progress.bob_start.format(total=total, limit=limit))

        async def _record_skip(text_id: int, *, note: str | None = None) -> None:
            async with lock:
                skipped.append(text_id)
                if note is not None:
                    warnings.notes.append(note)
                done = coded + len(skipped)
                _emit(progress.bob_skip.format(text_id=text_id, done=done, total=total))

        async def _code_one(text_id: int) -> None:
            nonlocal coded
            text = texts.get(text_id)
            if text is None:
                await _record_skip(text_id)
                return
            async with sem:
                try:
                    output = await arun_bob(ctx.llm, ctx.prompt_ctx, text)
                except Exception as exc:
                    await _record_skip(
                        text_id,
                        note=f"bob skipped text_id={text_id}: {exc!r}",
                    )
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
            async with lock:
                coded += 1
                done = coded + len(skipped)
                _emit(
                    progress.bob_done.format(
                        text_id=text_id,
                        done=done,
                        total=total,
                        items=len(output.items),
                    )
                )

        await asyncio.gather(*(_code_one(text_id) for text_id in target_ids))
        remaining = [text_id for text_id in ctx.workspace.load_queue() if text_id not in ctx.workspace.list_coded_ids()]
        ctx.workspace.save_queue(remaining)
        ctx.workspace.merge_warnings(warnings.as_dict())
        return progress.bob_summary.format(
            coded=coded,
            total=len(target_ids),
            skipped=skipped,
            remaining=len(remaining),
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
            return progress.alice_empty_pool

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
        return progress.alice_written.format(count=len(reviewed))

    async def run_kevin_batches(batch_index: int | None = None) -> str:
        meta = ctx.workspace.load_run_meta()
        if meta is None:
            return progress.run_not_initialized

        partition = ctx.workspace.load_partition()
        id_to_finished = {item.id: item for item in ctx.workspace.load_finished_texts()}
        kevin_source_ids = [
            text_id for text_id in partition.kevin_text_ids if text_id in id_to_finished
        ]
        batches = _chunked(kevin_source_ids, meta.kevin_batch_size)
        if not batches:
            return progress.no_kevin_batches

        if batch_index is not None:
            if batch_index < 1 or batch_index > len(batches):
                return progress.invalid_batch_index.format(
                    batch_index=batch_index,
                    total=len(batches),
                )
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
        return progress.kevin_summary.format(processed=processed, dimensions=len(final_reviewed))

    async def export_result() -> str:
        meta = ctx.workspace.load_run_meta()
        if meta is None:
            return progress.export_missing_run
        output_path = export_open_coding_result(ctx.workspace)
        return progress.export_result.format(path=output_path)

    async def workspace_status() -> str:
        import json

        return json.dumps(ctx.workspace.status(), ensure_ascii=False, indent=2)

    schemas = _tool_input_schemas(ctx.language)
    descriptions = bundle.llm.tool_descriptions
    return [
        StructuredTool.from_function(
            coroutine=init_open_coding_run,
            name="init_open_coding_run",
            description=descriptions["init_open_coding_run"],
            args_schema=schemas.init_run,
        ),
        StructuredTool.from_function(
            coroutine=batch_bob_code,
            name="batch_bob_code",
            description=descriptions["batch_bob_code"],
            args_schema=schemas.batch_bob,
        ),
        StructuredTool.from_function(
            coroutine=run_alice_codebook,
            name="run_alice_codebook",
            description=descriptions["run_alice_codebook"],
        ),
        StructuredTool.from_function(
            coroutine=run_kevin_batches,
            name="run_kevin_batches",
            description=descriptions["run_kevin_batches"],
            args_schema=schemas.kevin_batch,
        ),
        StructuredTool.from_function(
            coroutine=export_result,
            name="export_result",
            description=descriptions["export_result"],
            args_schema=ExportInput,
        ),
        StructuredTool.from_function(
            coroutine=workspace_status,
            name="workspace_status",
            description=descriptions["workspace_status"],
        ),
    ]


def create_coding_tool_context(
    workspace: Workspace,
    *,
    prompts_dir: Path | None = None,
    language: str | None = None,
) -> CodingToolContext:
    active_language = resolve_language(language) if language is not None else get_language()
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
    resolved_prompts = (prompts_dir or get_prompts_dir()).resolve()
    return CodingToolContext(
        workspace=workspace,
        llm=llm,
        llm_pro=llm_pro,
        prompt_ctx=PromptContext.load(resolved_prompts, language=active_language),
        prompts_dir_label=path_label(resolved_prompts),
        workspace_dir_label=path_label(workspace.root),
        language=active_language,
        on_progress=_default_bob_progress,
    )
