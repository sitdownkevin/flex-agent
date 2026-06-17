from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from direct_inference_eval.direct_eval.inference import run_direct_batches
from direct_inference_eval.direct_eval.metrics import evaluate_axial, evaluate_open
from direct_inference_eval.direct_eval.parser import parse_prediction_response
from direct_inference_eval.direct_eval.pipeline import run_experiment
from direct_inference_eval.direct_eval.schemas import HumanRecord, PredictionItem, PredictionRecord
from flex_agent.i18n import set_language


class FakeClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.responses:
            raise AssertionError("unexpected LLM call")
        return self.responses.pop(0)


class ParsePredictionResponseTests(unittest.TestCase):
    def test_accepts_fenced_json_and_normalizes_items(self) -> None:
        raw = """```json
        {"records":[{"text_id":1,"items":[
          {"evidence":"服务很好","dimension":"服务态度","category":"服务体验","value":1,"reason":"x"},
          {"evidence":"无关","dimension":"噪音","category":"","value":0,"reason":"neutral"}
        ]}]}
        ```"""
        parsed = parse_prediction_response(raw, expected_ids={1})
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].text_id, 1)
        self.assertEqual(len(parsed[0].items), 1)
        self.assertEqual(parsed[0].items[0].dimension, "态度")


class DirectBatchRunnerTests(unittest.TestCase):
    def _record(self, text_id: int) -> HumanRecord:
        return HumanRecord(
            text_id=text_id,
            content=f"评论{text_id}",
            human_dimensions={"画面": 1},
            human_categories={"sensory appeal"},
        )

    def test_failed_batch_is_skipped_and_resume_reuses_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            records = [self._record(1), self._record(2)]
            first = FakeClient([
                '{"records":[{"text_id":1,"items":[{"evidence":"画面好","dimension":"画面","category":"沉浸体验","value":1,"reason":"x"}]}]}',
                'not json',
            ])
            predictions, reports = run_direct_batches(
                records,
                output_dir=output,
                prompt_template="{records_json}",
                client=first,
                batch_size=1,
                resume=False,
            )
            self.assertEqual(sorted(predictions), [1])
            self.assertEqual(reports[1]["status"], "failed")

            second = FakeClient([
                '{"records":[{"text_id":2,"items":[{"evidence":"画面好","dimension":"画面","category":"沉浸体验","value":1,"reason":"x"}]}]}',
            ])
            predictions, reports = run_direct_batches(
                records,
                output_dir=output,
                prompt_template="{records_json}",
                client=second,
                batch_size=1,
                resume=True,
            )
            self.assertEqual(sorted(predictions), [1, 2])
            self.assertEqual(len(second.prompts), 1)
            self.assertTrue(reports[0]["skipped"])


class OpenMetricsTests(unittest.TestCase):
    def test_partial_and_missing_prediction_counts_cpr(self) -> None:
        records = [
            HumanRecord(1, "画面好服务好", {"画面": 1, "态度": 1}, {"sensory appeal"}),
            HumanRecord(2, "价格贵", {"价格": -1}, {"perceived value"}),
        ]
        predictions = {
            1: PredictionRecord(
                1,
                [
                    PredictionItem("画面好", "画面", "沉浸体验", 1, "x"),
                    PredictionItem("价格", "价格", "价格感知", 1, "x"),
                ],
            )
        }
        result = evaluate_open(records, predictions)
        macro = result["item_level_keyword"]["macro"]
        self.assertEqual(macro["n_intersection"], 1)
        self.assertEqual(macro["n_agent"], 2)
        self.assertEqual(macro["n_human"], 3)
        self.assertAlmostEqual(macro["consistency"], 0.1666, places=4)
        self.assertEqual(macro["precision"], 0.25)
        self.assertEqual(macro["recall"], 0.25)

    def test_perfect_match(self) -> None:
        records = [HumanRecord(1, "画面好", {"画面": 1}, {"sensory appeal"})]
        predictions = {1: PredictionRecord(1, [PredictionItem("画面好", "视觉效果", "沉浸体验")])}
        result = evaluate_open(records, predictions)
        self.assertEqual(result["item_level_keyword"]["macro"]["consistency"], 1.0)


class AxialMetricsTests(unittest.TestCase):
    def test_global_keyword_alignment_is_one_to_one(self) -> None:
        predictions = {
            1: PredictionRecord(
                1,
                [
                    PredictionItem("服务好", "态度", "服务体验"),
                    PredictionItem("耐心", "专业度", "态度"),
                    PredictionItem("画面", "画面", "沉浸体验"),
                ],
            )
        }
        result = evaluate_axial(predictions)
        macro = result["item_level_keyword"]["macro"]
        self.assertEqual(macro["n_intersection"], 2)
        self.assertEqual(macro["n_agent"], 3)
        self.assertEqual(macro["n_human"], 7)


class PipelineOutputTests(unittest.TestCase):
    def test_run_experiment_writes_records_and_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_path = root / "fixture.jsonl"
            rows = [
                {
                    "id": 1,
                    "comments": "画面很好，服务也好",
                    "human_items": [
                        {"dimension": "画面", "category": "sensory appeal", "value": 1},
                        {"dimension": "态度", "category": "interactive service", "value": 1},
                    ],
                },
                {
                    "id": 2,
                    "comments": "价格有点贵",
                    "human_items": [
                        {"dimension": "价格", "category": "perceived value", "value": -1},
                    ],
                },
            ]
            input_path.write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                encoding="utf-8",
            )
            client = FakeClient([
                json.dumps(
                    {
                        "records": [
                            {
                                "text_id": 1,
                                "items": [
                                    {"evidence": "画面很好", "dimension": "画面", "category": "沉浸体验", "value": 1},
                                    {"evidence": "服务也好", "dimension": "服务态度", "category": "服务体验", "value": 1},
                                ],
                            },
                            {
                                "text_id": 2,
                                "items": [
                                    {"evidence": "价格有点贵", "dimension": "价格", "category": "价格感知", "value": -1},
                                ],
                            },
                        ]
                    },
                    ensure_ascii=False,
                )
            ])
            result = run_experiment(
                input_path=input_path,
                output_dir=root / "run",
                batch_size=2,
                mode="both",
                resume=False,
                run_llm_semantic=False,
                direct_client=client,
            )
            self.assertTrue(result["records_path"].exists())
            open_summary = json.loads((root / "run" / "eval" / "open" / "summary.json").read_text(encoding="utf-8"))
            axial_global = json.loads((root / "run" / "eval" / "axial" / "global.json").read_text(encoding="utf-8"))
            self.assertEqual(open_summary["eval_kind"], "open")
            self.assertEqual(open_summary["language"], "zh")
            self.assertEqual(open_summary["item_level_keyword"]["macro"]["precision"], 1.0)
            self.assertIn("keyword", axial_global)

    def test_run_experiment_english_language_uses_english_prompt_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_path = root / "fixture.jsonl"
            input_path.write_text(
                json.dumps(
                    {
                        "id": 1,
                        "comments": "画面很好",
                        "human_items": [{"dimension": "画面", "category": "sensory appeal", "value": 1}],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            client = FakeClient([
                json.dumps(
                    {
                        "records": [
                            {
                                "text_id": 1,
                                "items": [
                                    {
                                        "evidence": "画面很好",
                                        "dimension": "visual quality",
                                        "category": "sensory appeal",
                                        "value": 1,
                                    }
                                ],
                            }
                        ]
                    }
                )
            ])

            try:
                run_experiment(
                    input_path=input_path,
                    output_dir=root / "run-en",
                    batch_size=1,
                    mode="open",
                    resume=False,
                    run_llm_semantic=False,
                    direct_client=client,
                    language="en",
                )

                self.assertIn("concise English dimension", client.prompts[0])
                self.assertNotIn("简洁中文维度", client.prompts[0])
                summary = json.loads((root / "run-en" / "eval" / "open" / "summary.json").read_text(encoding="utf-8"))
                report = (root / "run-en" / "eval" / "open" / "report.txt").read_text(encoding="utf-8")
                self.assertEqual(summary["language"], "en")
                self.assertIn("Direct Inference Open Coding Quality Evaluation", report)
                self.assertNotIn("质量评估", report)
            finally:
                set_language("zh")


if __name__ == "__main__":
    unittest.main()
