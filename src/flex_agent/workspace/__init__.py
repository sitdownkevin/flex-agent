from __future__ import annotations

import json
import random
import shutil
from pathlib import Path

from flex_agent.models import (
    DimensionDetail,
    FinishedTextItem,
    PartitionMeta,
    RunMeta,
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

    def ensure_layout(self) -> None:
        for path in (
            self.meta_dir,
            self.corpus_dir,
            self.coding_dir,
            self.codebook_dir,
            self.codebook_batches_dir,
            self.quality_dir,
            self.exports_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def clear_artifacts(self) -> None:
        """Remove all workspace state except files under corpus/."""
        for path in (
            self.meta_dir,
            self.coding_dir,
            self.codebook_dir,
            self.quality_dir,
            self.exports_dir,
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
        )
        self.save_run_meta(meta)
        self.save_partition(
            PartitionMeta(codebook_text_ids=codebook_ids, kevin_text_ids=kevin_ids)
        )
        self.save_queue([text.id for text in texts])
        self.save_dimensions([])
        self._write_json(self.quality_dir / "warnings.json", {})
        return meta

    def status(self) -> dict:
        meta = self.load_run_meta()
        partition = self.load_partition()
        coded_ids = self.list_coded_ids()
        dimensions = self.load_dimensions()
        return {
            "workspace": str(self.root),
            "run": meta.model_dump() if meta else None,
            "texts_total": len(self.load_texts()),
            "coded_count": len(coded_ids),
            "queue_remaining": len(self.load_queue()),
            "codebook_text_ids": partition.codebook_text_ids,
            "kevin_text_ids": partition.kevin_text_ids,
            "dimensions_count": len(dimensions),
            "warnings": self.load_warnings(),
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
