from __future__ import annotations

import json
import random
import shutil
from pathlib import Path
from typing import Any, Literal

from flex_agent.config import PROJECT_ROOT
from flex_agent.models import (
    DimensionDetail,
    FinishedTextItem,
    PartitionMeta,
    RunMeta,
    SessionMeta,
    TextItem,
    merge_quality_warnings,
)


class Workspace:
    """File-backed workspace for open coding state."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.meta_dir = self.root / "meta"
        self.corpus_dir = self.root / "corpus"
        self.coding_dir = self.root / "coding"
        self.codebook_dir = self.root / "codebook"
        self.codebook_batches_dir = self.codebook_dir / "batches"
        self.quality_dir = self.root / "quality"
        self.exports_dir = self.root / "exports"
        self.private_dir = self.root / "private"
        self.eval_dir = self.root / "eval"
        self.eval_open_dir = self.eval_dir / "open"
        self.eval_axial_dir = self.eval_dir / "axial"

    def eval_kind_dir(self, kind: Literal["open", "axial"]) -> Path:
        if kind == "open":
            return self.eval_open_dir
        return self.eval_axial_dir

    @property
    def corpus_seed_path(self) -> Path:
        return self.corpus_dir / "codebook_done.jsonl"

    @property
    def human_benchmark_path(self) -> Path:
        return self.private_dir / "codebook_done_human.jsonl"

    def ensure_layout(self) -> None:
        for path in (
            self.meta_dir,
            self.corpus_dir,
            self.private_dir,
            self.coding_dir,
            self.codebook_dir,
            self.codebook_batches_dir,
            self.quality_dir,
            self.exports_dir,
            self.eval_open_dir,
            self.eval_axial_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def bootstrap_seed_files(self) -> dict[str, str]:
        """Copy packaged seed JSONL files into workspace if missing or stale."""
        self.ensure_layout()
        seeds = {
            str(self.corpus_seed_path): PROJECT_ROOT / "data" / "codebook_done.jsonl",
            str(self.human_benchmark_path): PROJECT_ROOT / "data" / "codebook_done_human.jsonl",
        }
        actions: dict[str, str] = {}
        for dest, source in seeds.items():
            dest_path = Path(dest)
            if not source.exists():
                actions[str(dest_path)] = "missing_source"
                continue
            if not dest_path.exists() or source.stat().st_mtime > dest_path.stat().st_mtime:
                shutil.copy2(source, dest_path)
                actions[str(dest_path)] = "copied"
            else:
                actions[str(dest_path)] = "kept"
        return actions

    def benchmark_ready(self) -> bool:
        return self.corpus_seed_path.exists() and self.human_benchmark_path.exists()

    def clear_artifacts(self) -> None:
        """Remove run artifacts; preserve corpus/ and private/ seed files."""
        for path in (
            self.meta_dir,
            self.coding_dir,
            self.codebook_dir,
            self.quality_dir,
            self.exports_dir,
            self.eval_dir,
        ):
            if path.exists():
                shutil.rmtree(path)
        self.ensure_layout()

    def resolve_data_path(self, data_path: str | Path) -> Path:
        """Map agent virtual paths (e.g. /corpus/foo.jsonl) to workspace files."""
        raw = Path(data_path)
        if raw.is_absolute():
            if raw.exists():
                return raw.resolve()
            virtual = (self.root / raw.as_posix().lstrip("/")).resolve()
            if virtual.exists():
                return virtual
            return raw
        workspace_relative = (self.root / raw).resolve()
        if workspace_relative.exists():
            return workspace_relative
        return raw.resolve()

    def _read_json(self, path: Path, default):
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return default

    def _write_json(self, path: Path, payload) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_run_meta(self) -> RunMeta | None:
        raw = self._read_json(self.meta_dir / "run.json", None)
        return RunMeta.model_validate(raw) if raw else None

    def save_run_meta(self, meta: RunMeta) -> None:
        self._write_json(self.meta_dir / "run.json", meta.model_dump())

    def load_session_meta(self) -> SessionMeta | None:
        raw = self._read_json(self.meta_dir / "session.json", None)
        return SessionMeta.model_validate(raw) if raw else None

    def save_session_meta(self, meta: SessionMeta) -> None:
        self.ensure_layout()
        self._write_json(self.meta_dir / "session.json", meta.model_dump())

    def load_partition(self) -> PartitionMeta:
        raw = self._read_json(self.corpus_dir / "partition.json", {})
        return PartitionMeta.model_validate(raw)

    def save_partition(self, partition: PartitionMeta) -> None:
        self._write_json(self.corpus_dir / "partition.json", partition.model_dump())

    def load_queue(self) -> list[int]:
        return list(self._read_json(self.corpus_dir / "queue.json", []))

    def save_queue(self, queue: list[int]) -> None:
        self._write_json(self.corpus_dir / "queue.json", queue)

    def load_texts(self) -> list[TextItem]:
        path = self.corpus_dir / "raw.jsonl"
        if not path.exists():
            return []
        texts: list[TextItem] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            texts.append(TextItem.model_validate(json.loads(line)))
        return texts

    def save_texts(self, texts: list[TextItem]) -> None:
        path = self.corpus_dir / "raw.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for text in texts:
                handle.write(json.dumps(text.model_dump(), ensure_ascii=False) + "\n")

    def coding_path(self, text_id: int) -> Path:
        return self.coding_dir / f"{text_id}.json"

    def load_coding(self, text_id: int) -> FinishedTextItem | None:
        path = self.coding_path(text_id)
        if not path.exists():
            return None
        return FinishedTextItem.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def save_coding(self, finished: FinishedTextItem) -> None:
        self._write_json(self.coding_path(finished.id), finished.model_dump())

    def list_coded_ids(self) -> list[int]:
        ids: list[int] = []
        for path in self.coding_dir.glob("*.json"):
            try:
                ids.append(int(path.stem))
            except ValueError:
                continue
        return sorted(ids)

    def load_finished_texts(self) -> list[FinishedTextItem]:
        finished: list[FinishedTextItem] = []
        for text_id in self.list_coded_ids():
            item = self.load_coding(text_id)
            if item is not None:
                finished.append(item)
        return finished

    def load_dimensions(self) -> list[DimensionDetail]:
        dimensions_path = self.codebook_dir / "dimensions.json"
        legacy_path = self.codebook_dir / "constructs.json"
        path = dimensions_path if dimensions_path.exists() else legacy_path
        raw = self._read_json(path, [])
        return [DimensionDetail.model_validate(item) for item in raw]

    def save_dimensions(self, dimensions: list[DimensionDetail]) -> None:
        self._write_json(
            self.codebook_dir / "dimensions.json",
            [item.model_dump() for item in dimensions],
        )

    def save_codebook_batch(self, batch_index: int, dimensions: list[DimensionDetail]) -> None:
        self._write_json(
            self.codebook_batches_dir / f"{batch_index}.json",
            [item.model_dump() for item in dimensions],
        )

    def load_warnings(self) -> dict:
        return dict(self._read_json(self.quality_dir / "warnings.json", {}))

    def merge_warnings(self, update: dict) -> dict:
        merged = merge_quality_warnings(self.load_warnings(), update)
        self._write_json(self.quality_dir / "warnings.json", merged)
        return merged

    def init_run(
        self,
        *,
        data_path: Path,
        max_nums: int,
        codebook_nums: int,
        kevin_batch_size: int,
        open_mode: str = "pure",
        sample_mode: str = "sequential",
        random_seed: int | None = None,
        prompts_dir: str | None = None,
        workspace_dir: str | None = None,
    ) -> RunMeta:
        self.ensure_layout()
        data_path = self.resolve_data_path(data_path)
        comments = load_comments_from_jsonl(data_path)
        if not comments:
            raise RuntimeError(f"No valid comments found in {data_path}")

        if sample_mode == "random":
            rng = random.Random(random_seed)
            comments = list(comments)
            rng.shuffle(comments)

        selected = comments[: max(1, min(max_nums, len(comments)))]
        texts = [TextItem(id=idx + 1, content=content) for idx, content in enumerate(selected)]
        self.save_texts(texts)

        codebook_count = min(max(0, codebook_nums), len(texts))
        rng = random.Random(random_seed)
        codebook_ids = sorted(item.id for item in rng.sample(texts, k=codebook_count)) if codebook_count else []
        kevin_ids = [text.id for text in texts if text.id not in set(codebook_ids)]

        meta = RunMeta(
            data_path=str(data_path),
            max_nums=len(texts),
            codebook_nums=len(codebook_ids),
            kevin_batch_size=kevin_batch_size,
            open_mode=open_mode,
            sample_mode=sample_mode,
            random_seed=random_seed,
            prompts_dir=prompts_dir,
            workspace_dir=workspace_dir,
        )
        self.save_run_meta(meta)
        self.save_partition(
            PartitionMeta(codebook_text_ids=codebook_ids, kevin_text_ids=kevin_ids)
        )
        self.save_queue([text.id for text in texts])
        self.save_dimensions([])
        self._write_json(self.quality_dir / "warnings.json", {})
        return meta

    def eval_summary_path(self, kind: Literal["open", "axial"]) -> Path:
        return self.eval_kind_dir(kind) / "summary.json"

    def eval_report_path(self, kind: Literal["open", "axial"]) -> Path:
        return self.eval_kind_dir(kind) / "report.txt"

    def eval_text_path(self, kind: Literal["open", "axial"], text_id: int) -> Path:
        return self.eval_kind_dir(kind) / f"{text_id}.json"

    @staticmethod
    def _strip_eval_per_text(section: dict[str, Any] | None) -> dict[str, Any] | None:
        if section is None:
            return None
        return {key: value for key, value in section.items() if key != "per_text"}

    @staticmethod
    def _merge_eval_per_text(payload: dict[str, Any]) -> dict[int, dict[str, Any]]:
        by_id: dict[int, dict[str, Any]] = {}
        keyword = payload.get("item_level_keyword")
        semantic = payload.get("item_level_semantic")
        if isinstance(keyword, dict):
            for row in keyword.get("per_text", []):
                text_id = int(row["text_id"])
                by_id[text_id] = {"text_id": text_id, "keyword": row, "semantic": None}
        if isinstance(semantic, dict):
            for row in semantic.get("per_text", []):
                text_id = int(row["text_id"])
                if text_id in by_id:
                    by_id[text_id]["semantic"] = row
                else:
                    by_id[text_id] = {"text_id": text_id, "keyword": None, "semantic": row}
        return by_id

    def save_eval_result(
        self,
        kind: Literal["open", "axial"],
        *,
        payload: dict[str, Any],
        report: str,
        meta: dict[str, Any],
    ) -> Path:
        """Persist eval summary, report, and per-text results under eval/{kind}/."""
        kind_dir = self.eval_kind_dir(kind)
        kind_dir.mkdir(parents=True, exist_ok=True)

        per_text_by_id = self._merge_eval_per_text(payload)
        for text_id, text_payload in sorted(per_text_by_id.items()):
            self._write_json(self.eval_text_path(kind, text_id), text_payload)

        summary = {
            key: value
            for key, value in payload.items()
            if key not in {"item_level_keyword", "item_level_semantic"}
        }
        summary["item_level_keyword"] = self._strip_eval_per_text(
            payload.get("item_level_keyword")
        )
        summary["item_level_semantic"] = self._strip_eval_per_text(
            payload.get("item_level_semantic")
        )
        summary.update(meta)
        summary_path = self.eval_summary_path(kind)
        self._write_json(summary_path, summary)
        self.eval_report_path(kind).write_text(report, encoding="utf-8")

        current_ids = set(per_text_by_id)
        for path in kind_dir.glob("*.json"):
            if path.name == "summary.json":
                continue
            try:
                text_id = int(path.stem)
            except ValueError:
                path.unlink(missing_ok=True)
                continue
            if text_id not in current_ids:
                path.unlink()
        return summary_path

    def list_eval_text_ids(self, kind: Literal["open", "axial"]) -> list[int]:
        kind_dir = self.eval_kind_dir(kind)
        if not kind_dir.exists():
            return []
        ids: list[int] = []
        for path in kind_dir.glob("*.json"):
            if path.name == "summary.json":
                continue
            try:
                ids.append(int(path.stem))
            except ValueError:
                continue
        return sorted(ids)

    def load_eval_summary(self, kind: Literal["open", "axial"]) -> dict[str, Any] | None:
        raw = self._read_json(self.eval_summary_path(kind), None)
        return dict(raw) if raw else None

    def load_eval_text(self, kind: Literal["open", "axial"], text_id: int) -> dict[str, Any] | None:
        raw = self._read_json(self.eval_text_path(kind, text_id), None)
        return dict(raw) if raw else None

    def save_eval_text(
        self,
        kind: Literal["open", "axial"],
        text_id: int,
        payload: dict[str, Any],
    ) -> None:
        """Write or merge a single eval/{kind}/{id}.json result."""
        self.eval_kind_dir(kind).mkdir(parents=True, exist_ok=True)
        merged = dict(self.load_eval_text(kind, text_id) or {"text_id": text_id})
        merged.update(payload)
        merged["text_id"] = text_id
        self._write_json(self.eval_text_path(kind, text_id), merged)

    def save_eval_summary(
        self,
        kind: Literal["open", "axial"],
        *,
        payload: dict[str, Any],
        report: str,
        meta: dict[str, Any],
    ) -> Path:
        """Persist eval summary and report without rewriting per-text files."""
        self.eval_kind_dir(kind).mkdir(parents=True, exist_ok=True)
        summary = {
            key: value
            for key, value in payload.items()
            if key not in {"item_level_keyword", "item_level_semantic"}
        }
        summary["item_level_keyword"] = self._strip_eval_per_text(
            payload.get("item_level_keyword")
        )
        summary["item_level_semantic"] = self._strip_eval_per_text(
            payload.get("item_level_semantic")
        )
        summary.update(meta)
        summary_path = self.eval_summary_path(kind)
        self._write_json(summary_path, summary)
        self.eval_report_path(kind).write_text(report, encoding="utf-8")
        return summary_path

    def status(self) -> dict:
        meta = self.load_run_meta()
        session = self.load_session_meta()
        partition = self.load_partition()
        coded_ids = self.list_coded_ids()
        dimensions = self.load_dimensions()
        return {
            "workspace": str(self.root),
            "session": session.model_dump() if session else None,
            "run": meta.model_dump() if meta else None,
            "benchmark_ready": self.benchmark_ready(),
            "corpus_seed": str(self.corpus_seed_path),
            "human_benchmark": str(self.human_benchmark_path),
            "texts_total": len(self.load_texts()),
            "coded_count": len(coded_ids),
            "queue_remaining": len(self.load_queue()),
            "codebook_text_ids": partition.codebook_text_ids,
            "kevin_text_ids": partition.kevin_text_ids,
            "dimensions_count": len(dimensions),
            "warnings": self.load_warnings(),
            "eval_open_count": len(self.list_eval_text_ids("open")),
            "eval_axial_count": len(self.list_eval_text_ids("axial")),
            "latest_eval_open": self.load_eval_summary("open"),
        }


def load_comments_from_jsonl(path: Path) -> list[str]:
    comments: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            record = json.loads(line)
            comment = str(
                record.get("comments") or record.get("content") or record.get("text") or ""
            ).strip()
            if comment:
                comments.append(comment)
    return comments
