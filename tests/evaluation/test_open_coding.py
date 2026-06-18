from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flex_agent.eval.core import (
    extract_agent_items,
    extract_agent_items_raw,
    load_human_benchmark,
    make_item_set,
    normalize_dimension,
)
from flex_agent.eval.metrics import compute_item_metrics_simple
from flex_agent.eval.prompts import dimension_name_alignment_prompt, text_alignment_prompt
from flex_agent.eval.semantic import apply_semantic_alignment
from flex_agent.eval.text_alignment import BatchSemanticAlignment, build_semantic_alignment_for_texts
from flex_agent.models import FinishedItemDetail, FinishedTextItem
from flex_agent.workspace import Workspace


class NormalizeDimensionTests(unittest.TestCase):
    def test_alias_normalization(self) -> None:
        self.assertEqual(normalize_dimension("服务态度"), "态度")
        self.assertEqual(normalize_dimension("地理位置"), "位置")
        self.assertEqual(normalize_dimension("性价比"), "价格")
        self.assertEqual(normalize_dimension("坏境"), "环境")

    def test_english_translation(self) -> None:
        self.assertEqual(normalize_dimension("staff_patience"), "专业度")
        self.assertEqual(normalize_dimension("visual_quality"), "画面")
        self.assertEqual(normalize_dimension("revisit_intention"), "二刷意愿")


class MakeItemSetTests(unittest.TestCase):
    def test_converts_to_labeled_set(self) -> None:
        items = {"画面": 1, "态度": -1, "价格": 1}
        result = make_item_set(items)
        self.assertEqual(result, {"画面:+1", "态度:-1", "价格:+1"})


class LoadHumanBenchmarkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8")
        records = [
            {"comments": "画面好", "codes": {"4.2": {"dimension": "画面", "value": 1}}},
            {"comments": "态度差", "codes": {"2.1": {"dimension": "态度", "value": -1}}},
        ]
        for record in records:
            self.tmp.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.tmp.close()

    def tearDown(self) -> None:
        Path(self.tmp.name).unlink(missing_ok=True)

    def test_loads_nonzero_codes_only(self) -> None:
        result = load_human_benchmark(Path(self.tmp.name))
        self.assertEqual(len(result), 2)
        self.assertEqual(result[1], {"画面": 1})
        self.assertEqual(result[2], {"态度": -1})


class ComputeItemMetricsSimpleTests(unittest.TestCase):
    def test_perfect_match(self) -> None:
        human = {1: {"画面": 1, "态度": 1}}
        agent = {1: {"画面": 1, "态度": 1}}
        result = compute_item_metrics_simple(human, agent)
        self.assertEqual(result["macro"]["consistency"], 1.0)

    def test_partial_overlap(self) -> None:
        human = {1: {"画面": 1, "态度": 1, "趣味性": 1}}
        agent = {1: {"画面": 1, "价格": 1}}
        result = compute_item_metrics_simple(human, agent)
        self.assertEqual(result["macro"]["n_intersection"], 1)
        self.assertEqual(result["macro"]["consistency"], 0.25)
        self.assertEqual(result["micro"]["precision"], 0.5)
        self.assertAlmostEqual(result["micro"]["recall"], 1 / 3, places=4)

    def test_macro_vs_micro_across_texts(self) -> None:
        human = {
            1: {"画面": 1},
            2: {"画面": 1, "态度": 1, "趣味性": 1},
        }
        agent = {
            1: {"画面": 1},
            2: {"画面": 1, "价格": 1},
        }
        result = compute_item_metrics_simple(human, agent)
        self.assertEqual(result["macro"]["precision"], 0.75)
        self.assertAlmostEqual(result["micro"]["precision"], 2 / 3, places=4)


class EvalPromptTests(unittest.TestCase):
    def test_text_alignment_prompt_has_placeholder(self) -> None:
        prompt = text_alignment_prompt()
        self.assertIn("{texts_json}", prompt)
        self.assertNotIn("ReAct", prompt)
        self.assertIn("允许多对一", prompt)
        self.assertIn("只输出 JSON", prompt)
        self.assertNotIn("游戏趣味性", prompt)
        self.assertNotIn("例如", prompt)

    def test_dimension_name_alignment_prompt_formats_lists(self) -> None:
        prompt = dimension_name_alignment_prompt(human_list="- 画面", agent_list="- 视觉质量")
        self.assertIn("- 画面", prompt)
        self.assertIn("- 视觉质量", prompt)
        self.assertNotIn("ReAct", prompt)
        self.assertIn("允许多对一", prompt)
        self.assertIn("只输出 JSON", prompt)
        self.assertNotIn("例如", prompt)

    def test_semantic_alignment_schema_does_not_reference_react(self) -> None:
        schema_text = json.dumps(BatchSemanticAlignment.model_json_schema(), ensure_ascii=False)
        self.assertNotIn("ReAct", schema_text)
        self.assertIn("可选的简短判断依据", schema_text)
        self.assertIn("可选的简短匹配结果标记", schema_text)


class SemanticAlignmentTests(unittest.TestCase):
    def test_remaps_agent_dimensions(self) -> None:
        agent_items = {1: {"视觉质量": 1, "趣味性": -1}}
        alignment = {"视觉质量": "画面"}
        result = apply_semantic_alignment(agent_items, alignment)
        self.assertEqual(result[1], {"画面": 1, "趣味性": -1})


class SemanticAlignmentLLMTests(unittest.TestCase):
    def test_validates_fake_llm_structured_output(self) -> None:
        class FakeChain:
            def invoke(self, payload):
                from flex_agent.eval.text_alignment import (
                    BatchSemanticAlignment,
                    SemanticMatch,
                    TextSemanticAlignment,
                )

                return BatchSemanticAlignment(
                    texts=[
                        TextSemanticAlignment(
                            text_id="1",
                            matches=[
                                SemanticMatch(agent_dimension="视觉质量", matched_human_dimension="画面"),
                                SemanticMatch(agent_dimension="价格", matched_human_dimension="不存在"),
                            ],
                        )
                    ]
                )

        class FakePrompt:
            def __or__(self, other):
                return FakeChain()

        class FakeLLM:
            def with_structured_output(self, schema, method="json_schema"):
                return self

        entries = [
            {
                "text_id": 1,
                "content": "画面很好",
                "human_items": [{"dimension": "画面", "evidences": ["画面很好"]}],
                "agent_items": [
                    {"dimension": "视觉质量", "evidences": ["画面很好"]},
                    {"dimension": "价格", "evidences": ["便宜"]},
                ],
            }
        ]
        with patch(
            "flex_agent.eval.text_alignment.ChatPromptTemplate.from_messages",
            return_value=FakePrompt(),
        ):
            result = build_semantic_alignment_for_texts(entries, FakeLLM())
        self.assertEqual(result[1]["视觉质量"], "画面")
        self.assertIsNone(result[1]["价格"])


class PartialSemanticMetricsTests(unittest.TestCase):
    def test_aggregate_partial_metrics(self) -> None:
        from flex_agent.eval.text_alignment import _aggregate_semantic_metrics

        entries = [
            {
                "text_id": 1,
                "human_items": [{"dimension": "画面"}],
                "agent_items": [{"dimension": "画面"}, {"dimension": "价格"}],
            },
            {
                "text_id": 2,
                "human_items": [{"dimension": "态度"}],
                "agent_items": [{"dimension": "态度"}, {"dimension": "环境"}],
            },
        ]
        alignments = {
            1: {"画面": "画面", "价格": None},
            2: {"态度": "态度", "环境": None},
        }
        partial = _aggregate_semantic_metrics(entries[:1], {1: alignments[1]})
        self.assertEqual(partial["common_texts"], 1)
        self.assertEqual(partial["macro"]["n_intersection"], 1)

        missing = _aggregate_semantic_metrics(entries[:1], {})
        self.assertEqual(missing["macro"]["n_intersection"], 0)

        full = _aggregate_semantic_metrics(entries, alignments)
        self.assertEqual(full["common_texts"], 2)
        self.assertEqual(full["macro"]["n_intersection"], 2)


class EvaluateWorkspaceTests(unittest.TestCase):
    def test_evaluate_workspace_keyword_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = Workspace(root)
            workspace.ensure_layout()

            human_path = workspace.human_benchmark_path
            human_path.parent.mkdir(parents=True, exist_ok=True)
            human_path.write_text(
                json.dumps(
                    {
                        "comments": "画面很好",
                        "human_items": [{"dimension": "画面", "value": 1, "evidences": []}],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            workspace.corpus_seed_path.write_text(
                json.dumps({"id": 1, "comments": "画面很好"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            workspace.save_coding(
                FinishedTextItem(
                    id=1,
                    content="画面很好",
                    content_with_labels="画面很好",
                    items=[
                        FinishedItemDetail(
                            name="画面清晰",
                            normalized_label="画面",
                            evidence="画面很好",
                        )
                    ],
                )
            )

            from flex_agent.eval.runner import evaluate_workspace

            report = evaluate_workspace(workspace, mode="keyword", save_json=False, on_progress=None)
            self.assertIn("维度名匹配", report)
            self.assertIn("100.0%", report)

    def test_evaluate_workspace_persists_under_eval_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(Path(tmpdir))
            workspace.ensure_layout()
            workspace.human_benchmark_path.parent.mkdir(parents=True, exist_ok=True)
            workspace.human_benchmark_path.write_text(
                json.dumps(
                    {
                        "comments": "画面很好",
                        "human_items": [{"dimension": "画面", "value": 1, "evidences": []}],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            workspace.corpus_seed_path.write_text(
                json.dumps({"id": 1, "comments": "画面很好"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            workspace.save_coding(
                FinishedTextItem(
                    id=1,
                    content="画面很好",
                    content_with_labels="画面很好",
                    items=[FinishedItemDetail(name="画面清晰", normalized_label="画面")],
                )
            )

            from flex_agent.eval.runner import evaluate_workspace

            report = evaluate_workspace(workspace, mode="keyword", save_json=True, on_progress=None)
            self.assertIn("eval/open/summary.json", report)
            self.assertFalse(any(workspace.exports_dir.glob("eval_open_*.json")))
            self.assertTrue(workspace.eval_summary_path("open").exists())
            self.assertEqual(workspace.list_eval_text_ids("open"), [1])
            self.assertIsNotNone(workspace.load_eval_summary("open"))


class AggregateEvalResultsTests(unittest.TestCase):
    def test_aggregate_from_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            eval_dir = Path(tmpdir)
            eval_dir.joinpath("1.json").write_text(
                json.dumps(
                    {
                        "text_id": 1,
                        "keyword": {
                            "text_id": 1,
                            "human_items": ["画面"],
                            "agent_items": ["画面"],
                            "both": ["画面"],
                            "llm_only": [],
                            "human_only": [],
                            "nums_both": 1,
                            "nums_llm_only": 0,
                            "nums_human_only": 0,
                            "consistency": 1.0,
                            "precision": 1.0,
                            "recall": 1.0,
                            "status": "complete",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            from flex_agent.eval.aggregate import aggregate_eval_results

            agg = aggregate_eval_results(eval_dir)
            self.assertEqual(agg["keyword_complete"], 1)
            self.assertEqual(agg["item_level_keyword"]["macro"]["consistency"], 1.0)


class JudgeKeywordTests(unittest.TestCase):
    def test_judge_keyword_perfect_match(self) -> None:
        from flex_agent.eval.judge import judge_keyword
        from flex_agent.eval.pairs import EvalPair

        pair = EvalPair(
            text_id=1,
            content="画面很好",
            human_items={"画面": 1},
            human_record={"human_items": [{"dimension": "画面", "value": 1}]},
            agent_items_raw=[{"normalized_label": "画面", "name": "画面清晰"}],
        )
        result = judge_keyword(pair)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["nums_both"], 1)


class JudgeSemanticFailureTests(unittest.TestCase):
    def test_llm_failure_marks_failed_without_crash(self) -> None:
        from flex_agent.eval.judge import judge_semantic
        from flex_agent.eval.pairs import EvalPair

        pair = EvalPair(
            text_id=1,
            content="画面很好",
            human_items={"画面": 1},
            human_record={"human_items": [{"dimension": "画面", "value": 1}]},
            agent_items_raw=[{"normalized_label": "完全无关", "name": "无关"}],
        )

        class BrokenLLM:
            def with_structured_output(self, schema, method="json_schema"):
                return self

        with patch(
            "flex_agent.eval.judge.build_semantic_alignment_for_texts",
            return_value={},
        ):
            result = judge_semantic(pair, BrokenLLM())
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["nums_both"], 0)


class SemanticMetricsTests(unittest.TestCase):
    def test_human_only_not_inflated_when_aligned(self) -> None:
        from flex_agent.eval.semantic_metrics import build_semantic_row

        row = build_semantic_row(
            36,
            {"体验探索", "生理舒适度"},
            {"晕动症", "游戏趣味性"},
            {"晕动症": "生理舒适度", "游戏趣味性": "体验探索"},
        )
        self.assertEqual(row["human_only"], [])
        self.assertEqual(row["nums_both"], 2)
        self.assertEqual(row["recall"], 1.0)

    def test_prefetch_normalize_alias(self) -> None:
        from flex_agent.eval.semantic_metrics import prefetch_semantic_alignment

        matches = prefetch_semantic_alignment(
            {"服务态度", "画面"},
            {"态度", "画面"},
        )
        self.assertEqual(matches["服务态度"], "态度")
        self.assertEqual(matches["画面"], "画面")

    def test_heuristic_substring_match(self) -> None:
        from flex_agent.eval.semantic_metrics import apply_heuristic_semantic_alignment

        matches = apply_heuristic_semantic_alignment(
            {"游戏趣味性", "价格优惠", "环境"},
            {"趣味性"},
        )
        self.assertEqual(matches["游戏趣味性"], "趣味性")
        self.assertIsNone(matches["环境"])
        self.assertIsNone(matches["价格优惠"])

    def test_heuristic_bigram_overlap_match(self) -> None:
        from flex_agent.eval.semantic_metrics import apply_heuristic_semantic_alignment

        matches = apply_heuristic_semantic_alignment(
            {"沉浸体验"},
            {"体验探索"},
        )
        self.assertEqual(matches["沉浸体验"], "体验探索")

    def test_heuristic_allows_many_to_one(self) -> None:
        from flex_agent.eval.semantic_metrics import apply_heuristic_semantic_alignment

        matches = apply_heuristic_semantic_alignment(
            {"游戏趣味性", "趣味性体验"},
            {"趣味性"},
        )
        self.assertEqual(matches["游戏趣味性"], "趣味性")
        self.assertEqual(matches["趣味性体验"], "趣味性")

    def test_react_action_fallback_parsing(self) -> None:
        from flex_agent.eval.text_alignment import _human_from_react_action

        self.assertEqual(_human_from_react_action("MATCH 趣味性", {"趣味性"}), "趣味性")
        self.assertIsNone(_human_from_react_action("NO_MATCH", {"趣味性"}))

    def test_judge_semantic_falls_back_when_llm_returns_empty(self) -> None:
        from flex_agent.eval.judge import judge_semantic
        from flex_agent.eval.pairs import EvalPair

        pair = EvalPair(
            text_id=1,
            content="很好玩",
            human_items={"趣味性": 1},
            human_record={"human_items": [{"dimension": "趣味性", "value": 1}]},
            agent_items_raw=[
                {"normalized_label": "游戏趣味性", "name": "游戏有趣", "evidence": "很好玩"},
                {"normalized_label": "环境", "name": "环境好"},
            ],
        )

        class EmptyLLM:
            def with_structured_output(self, schema, method="json_schema"):
                return self

        with patch(
            "flex_agent.eval.judge.build_semantic_alignment_for_texts",
            return_value={1: {"游戏趣味性": None, "环境": None}},
        ):
            result = judge_semantic(pair, EmptyLLM())
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["alignment"]["游戏趣味性"], "趣味性")

    def test_aggregate_recomputes_from_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            eval_dir = Path(tmpdir)
            eval_dir.joinpath("1.json").write_text(
                json.dumps(
                    {
                        "text_id": 1,
                        "semantic": {
                            "text_id": 1,
                            "human_items": ["趣味性"],
                            "agent_items": ["游戏趣味性", "环境", "价格优惠"],
                            "both": ["游戏趣味性"],
                            "llm_only": ["环境", "价格优惠"],
                            "human_only": ["趣味性"],
                            "nums_both": 1,
                            "nums_llm_only": 2,
                            "nums_human_only": 1,
                            "status": "complete",
                            "alignment": {
                                "游戏趣味性": "趣味性",
                                "环境": None,
                                "价格优惠": None,
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            from flex_agent.eval.aggregate import aggregate_eval_results

            agg = aggregate_eval_results(eval_dir)
            macro = agg["item_level_semantic"]["macro"]
            self.assertEqual(macro["n_intersection"], 1)
            self.assertEqual(macro["recall"], 1.0)
            self.assertAlmostEqual(macro["consistency"], 1 / 3, places=3)


class MetricsOnlyEvalTests(unittest.TestCase):
    def test_metrics_mode_reaggregates_from_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(Path(tmpdir))
            workspace.ensure_layout()
            workspace.save_eval_text(
                "open",
                1,
                {
                    "text_id": 1,
                    "keyword": {
                        "text_id": 1,
                        "human_items": ["画面"],
                        "agent_items": ["画面"],
                        "both": ["画面"],
                        "llm_only": [],
                        "human_only": [],
                        "nums_both": 1,
                        "nums_llm_only": 0,
                        "nums_human_only": 0,
                        "consistency": 1.0,
                        "precision": 1.0,
                        "recall": 1.0,
                        "status": "complete",
                    },
                },
            )
            workspace.save_eval_summary(
                "open",
                payload={"mode": "keyword", "status": "complete", "coded_count": 1},
                report="stub",
                meta={"coded_count": 1, "benchmark_path": str(workspace.human_benchmark_path)},
            )
            from flex_agent.eval.runner import aggregate_workspace_eval

            report = aggregate_workspace_eval(workspace, mode="keyword", on_progress=None)
            self.assertIn("100.0%", report)


class SemanticResumeTests(unittest.TestCase):
    def test_resume_skips_complete_semantic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(Path(tmpdir))
            workspace.ensure_layout()
            workspace.human_benchmark_path.parent.mkdir(parents=True, exist_ok=True)
            workspace.human_benchmark_path.write_text(
                json.dumps(
                    {
                        "comments": "画面很好",
                        "human_items": [{"dimension": "画面", "value": 1, "evidences": []}],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            workspace.save_coding(
                FinishedTextItem(
                    id=1,
                    content="画面很好",
                    content_with_labels="画面很好",
                    items=[FinishedItemDetail(name="画面清晰", normalized_label="画面")],
                )
            )
            workspace.save_eval_text(
                "open",
                1,
                {
                    "text_id": 1,
                    "semantic": {
                        "text_id": 1,
                        "status": "complete",
                        "both": ["画面"],
                        "human_items": ["画面"],
                        "agent_items": ["画面"],
                        "llm_only": [],
                        "human_only": [],
                        "nums_both": 1,
                        "nums_llm_only": 0,
                        "nums_human_only": 0,
                        "consistency": 1.0,
                        "precision": 1.0,
                        "recall": 1.0,
                        "alignment": {"画面": "画面"},
                    },
                },
            )

            from flex_agent.eval.batch_semantic import batch_semantic_judge
            from flex_agent.eval.pairs import load_eval_pairs

            pairs, _ = load_eval_pairs(workspace)
            call_count = 0

            class SpyLLM:
                def with_structured_output(self, schema, method="json_schema"):
                    nonlocal call_count
                    call_count += 1
                    raise AssertionError("should not call LLM for complete semantic")

            import asyncio

            stats = asyncio.run(
                batch_semantic_judge(workspace, pairs, SpyLLM(), resume=True, on_progress=None)
            )
            self.assertEqual(stats["skipped"], 1)
            self.assertEqual(stats["judged"], 0)
            self.assertEqual(call_count, 0)


class RunAsyncTests(unittest.TestCase):
    def test_run_async_from_running_loop(self) -> None:
        import asyncio

        from flex_agent.eval.async_utils import run_async

        async def _sample() -> str:
            await asyncio.sleep(0)
            return "ok"

        async def _nested() -> str:
            return run_async(_sample())

        result = asyncio.run(_nested())
        self.assertEqual(result, "ok")


if __name__ == "__main__":
    unittest.main()
