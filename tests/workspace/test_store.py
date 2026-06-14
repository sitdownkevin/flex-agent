from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from flex_agent.coding.export import export_open_coding_result
from flex_agent.coding.quality import normalize_finished_text
from flex_agent.models import DimensionDetail, FinishedItemDetail, FinishedTextItem, RunMeta
from flex_agent.workspace import Workspace, load_comments_from_jsonl


class WorkspaceTests(unittest.TestCase):
    def test_init_run_writes_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "data.jsonl"
            data_path.write_text(
                "\n".join(
                    json.dumps({"comments": f"comment {idx}"}, ensure_ascii=False)
                    for idx in range(1, 6)
                ),
                encoding="utf-8",
            )
            ws = Workspace(root / "workspace")
            meta = ws.init_run(
                data_path=data_path,
                max_nums=3,
                codebook_nums=1,
                kevin_batch_size=2,
                random_seed=7,
            )
            self.assertEqual(meta.max_nums, 3)
            self.assertEqual(len(ws.load_texts()), 3)
            self.assertTrue((ws.corpus_dir / "raw.jsonl").exists())
            self.assertTrue((ws.corpus_dir / "queue.json").exists())
            self.assertTrue((ws.corpus_dir / "partition.json").exists())
            partition = ws.load_partition()
            self.assertEqual(len(partition.codebook_text_ids), 1)
            self.assertEqual(len(partition.kevin_text_ids), 2)

    def test_init_run_accepts_content_field_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "data.jsonl"
            data_path.write_text(
                "\n".join(
                    json.dumps({"id": idx, "content": f"comment {idx}"}, ensure_ascii=False)
                    for idx in range(1, 6)
                ),
                encoding="utf-8",
            )
            ws = Workspace(root / "workspace")
            meta = ws.init_run(
                data_path=data_path,
                max_nums=3,
                codebook_nums=1,
                kevin_batch_size=2,
            )
            self.assertEqual(meta.max_nums, 3)
            self.assertEqual(len(ws.load_texts()), 3)

    def test_load_comments_from_jsonl_accepts_content_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.jsonl"
            path.write_text(
                json.dumps({"content": "hello"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(load_comments_from_jsonl(path), ["hello"])

    def test_load_partition_falls_back_on_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Workspace(Path(tmp))
            ws.ensure_layout()
            (ws.corpus_dir / "partition.json").write_text("{ broken", encoding="utf-8")
            partition = ws.load_partition()
            self.assertEqual(partition.codebook_text_ids, [])
            self.assertEqual(partition.kevin_text_ids, [])

    def test_clear_artifacts_preserves_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "data.jsonl"
            data_path.write_text(
                json.dumps({"comments": "sample"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            ws = Workspace(root / "workspace")
            ws.init_run(
                data_path=data_path,
                max_nums=1,
                codebook_nums=1,
                kevin_batch_size=1,
            )
            ws.save_coding(
                FinishedTextItem(
                    id=1,
                    content="很好玩",
                    content_with_labels="<p>很好玩</p>",
                    items=[],
                )
            )
            extra_corpus = ws.corpus_dir / "codebook_done.jsonl"
            extra_corpus.write_text(
                json.dumps({"comments": "kept"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            ws.clear_artifacts()

            self.assertTrue((ws.corpus_dir / "raw.jsonl").exists())
            self.assertTrue((ws.corpus_dir / "queue.json").exists())
            self.assertTrue((ws.corpus_dir / "partition.json").exists())
            self.assertTrue(extra_corpus.exists())
            self.assertFalse((ws.meta_dir / "run.json").exists())
            self.assertEqual(ws.list_coded_ids(), [])
            self.assertEqual(ws.load_dimensions(), [])
            self.assertEqual(ws.load_warnings(), {})
            self.assertFalse(any(ws.exports_dir.glob("*.json")))
            ws.ensure_layout()
            self.assertTrue(ws.coding_dir.is_dir())
            self.assertTrue(ws.codebook_dir.is_dir())

    def test_resolve_data_path_virtual(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ws = Workspace(root / "workspace")
            ws.ensure_layout()
            corpus_file = ws.corpus_dir / "codebook_done.jsonl"
            corpus_file.write_text(
                json.dumps({"comments": "sample"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            resolved = ws.resolve_data_path("/corpus/codebook_done.jsonl")
            self.assertEqual(resolved, corpus_file.resolve())
            meta = ws.init_run(
                data_path="/corpus/codebook_done.jsonl",
                max_nums=1,
                codebook_nums=1,
                kevin_batch_size=1,
            )
            self.assertEqual(meta.max_nums, 1)
            self.assertEqual(len(ws.load_texts()), 1)

    def test_load_dimensions_falls_back_to_legacy_constructs_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Workspace(Path(tmp))
            ws.ensure_layout()
            legacy = ws.codebook_dir / "constructs.json"
            legacy.write_text(
                json.dumps(
                    [{"name": "体验", "items": ["趣味性"], "definition": "游戏乐趣"}],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            loaded = ws.load_dimensions()
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].name, "体验")

    def test_save_and_load_coding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Workspace(Path(tmp))
            ws.ensure_layout()
            finished = FinishedTextItem(
                id=1,
                content="很好玩",
                content_with_labels="<p>很好玩</p>",
                items=[
                    FinishedItemDetail(
                        name="很好玩",
                        normalized_label="趣味性",
                        evidence="很好玩",
                    )
                ],
            )
            ws.save_coding(finished)
            loaded = ws.load_coding(1)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.items[0].normalized_label, "趣味性")


class ExportTests(unittest.TestCase):
    def test_export_matches_gt_agent_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Workspace(Path(tmp))
            ws.ensure_layout()
            ws.save_run_meta(
                RunMeta(
                    data_path="data.jsonl",
                    max_nums=1,
                    codebook_nums=1,
                    kevin_batch_size=1,
                )
            )
            ws.save_coding(
                FinishedTextItem(
                    id=1,
                    content="很好玩",
                    content_with_labels="<p>很好玩</p>",
                    items=[
                        FinishedItemDetail(
                            name="很好玩",
                            normalized_label="趣味性",
                            evidence="很好玩",
                        )
                    ],
                )
            )
            ws.save_dimensions(
                [DimensionDetail(name="体验", items=["趣味性"], definition="游戏乐趣")]
            )
            output = export_open_coding_result(ws)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertIn("meta", payload)
            self.assertIn("state", payload)
            self.assertEqual(payload["meta"]["finished_texts"], 1)
            self.assertEqual(payload["meta"]["dimensions"], 1)
            self.assertEqual(len(payload["state"]["finished_texts"]), 1)
            self.assertEqual(len(payload["state"]["dimensions"]), 1)


class QualitySmokeTests(unittest.TestCase):
    def test_normalize_finished_text(self) -> None:
        finished = FinishedTextItem(
            id=1,
            content="游戏好玩",
            content_with_labels="<p>游戏好玩</p>",
            items=[
                FinishedItemDetail(
                    name="游戏好玩",
                    normalized_label="playfulness",
                    evidence="游戏好玩",
                )
            ],
        )
        normalized, _ = normalize_finished_text(finished)
        self.assertEqual(normalized.items[0].normalized_label, "趣味性")


if __name__ == "__main__":
    unittest.main()
