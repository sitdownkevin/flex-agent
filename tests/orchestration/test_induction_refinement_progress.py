from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flex_agent.coding.agents import (
    AxialCodingDimensionDetail,
    AxialCodingOutput,
    InductionDimensionDetail,
    InductionOutput,
    PromptContext,
)
from flex_agent.models import DimensionDetail, FinishedItemDetail, FinishedTextItem
from flex_agent.orchestration.tools import CodingToolContext, build_coding_tools
from flex_agent.workspace import Workspace


def _minimal_prompt_ctx() -> PromptContext:
    return PromptContext(
        grounded_theory_background="gt",
        task_background="task",
        open_coding_template="open-coding",
        induction_template="induction",
        axial_refinement_template="axial-coding",
    )


def _setup_workspace(root: Path, *, count: int = 4, codebook_nums: int = 2, kevin_batch_size: int = 2) -> Workspace:
    data_path = root / "data.jsonl"
    data_path.write_text(
        "\n".join(
            json.dumps({"comments": f"comment {idx}"}, ensure_ascii=False)
            for idx in range(1, count + 1)
        ),
        encoding="utf-8",
    )
    ws = Workspace(root / "workspace")
    ws.init_run(
        data_path=data_path,
        max_nums=count,
        codebook_nums=codebook_nums,
        kevin_batch_size=kevin_batch_size,
    )
    return ws


def _finished(text_id: int) -> FinishedTextItem:
    return FinishedTextItem(
        id=text_id,
        content=f"comment {text_id}",
        content_with_labels=f"comment {text_id}",
        items=[
            FinishedItemDetail(
                name="态度好",
                normalized_label="态度",
                evidence="服务很好",
            )
        ],
    )


def _tool(ctx: CodingToolContext, name: str):
    tools = build_coding_tools(ctx)
    return next(tool for tool in tools if tool.name == name)


class InductionRefinementProgressTests(unittest.TestCase):
    def test_run_construct_induction_emits_start_and_done_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = _setup_workspace(Path(tmp), count=4, codebook_nums=2)
            partition = ws.load_partition()
            for text_id in partition.seed_text_ids:
                ws.save_coding(_finished(text_id))

            messages: list[str] = []
            ctx = CodingToolContext(
                workspace=ws,
                llm=object(),
                llm_pro=object(),
                prompt_ctx=_minimal_prompt_ctx(),
                prompts_dir_label="prompts/test",
                workspace_dir_label="workspaces/test",
                on_progress=messages.append,
            )

            async def mock_arun_induction(_llm, _prompt_ctx, _items_pool, *, items_details=None):
                return InductionOutput(
                    dimensions=[
                        InductionDimensionDetail(
                            name="服务体验",
                            items=["态度"],
                            definition="与服务相关的体验",
                        )
                    ]
                )

            with patch("flex_agent.orchestration.tools.arun_induction", side_effect=mock_arun_induction):
                result = asyncio.run(_tool(ctx, "run_construct_induction").coroutine())

            self.assertIn("Inducing wrote 1 dimensions", result)
            self.assertEqual(messages[0], "[Inducing] 开始归纳 seed pool (1 条目)")
            self.assertEqual(messages[-1], "[Inducing] 完成 · dimensions=1")

    def test_run_axial_coding_emits_batch_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = _setup_workspace(Path(tmp), count=5, codebook_nums=1, kevin_batch_size=2)
            partition = ws.load_partition()
            ws.save_dimensions([DimensionDetail(name="初始维度", items=["态度"], definition="初始")])
            for text_id in partition.update_text_ids:
                ws.save_coding(_finished(text_id))

            messages: list[str] = []
            ctx = CodingToolContext(
                workspace=ws,
                llm=object(),
                llm_pro=object(),
                prompt_ctx=_minimal_prompt_ctx(),
                prompts_dir_label="prompts/test",
                workspace_dir_label="workspaces/test",
                on_progress=messages.append,
            )

            async def mock_arun_axial_coding(_llm, _prompt_ctx, _current, _items_pool, *, items_details=None):
                return AxialCodingOutput(
                    dimensions=[
                        AxialCodingDimensionDetail(
                            name="精炼维度",
                            items=["态度"],
                            definition="精炼后的维度",
                        )
                    ]
                )

            with patch("flex_agent.orchestration.tools.arun_axial_coding", side_effect=mock_arun_axial_coding):
                result = asyncio.run(_tool(ctx, "run_axial_coding").coroutine())

            self.assertIn("AxialCoding processed 2 batch(es)", result)
            self.assertEqual(messages[0], "[Refinement] 开始处理 2 个批次")
            done_lines = [line for line in messages if line.startswith("[Refinement] 完成")]
            self.assertEqual(len(done_lines), 2)
            self.assertIn("batch 1 (1/2)", done_lines[0])
            self.assertIn("batch 2 (2/2)", done_lines[1])


if __name__ == "__main__":
    unittest.main()
