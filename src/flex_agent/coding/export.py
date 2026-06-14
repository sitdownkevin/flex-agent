from __future__ import annotations

from pathlib import Path
from time import strftime

from flex_agent.models import WorkspaceSnapshot
from flex_agent.workspace import Workspace


def export_open_coding_result(workspace: Workspace) -> Path:
    meta = workspace.load_run_meta()
    if meta is None:
        raise RuntimeError("Run metadata missing; initialize workspace first.")

    texts = workspace.load_texts()
    coded_ids = set(workspace.list_coded_ids())
    finished = workspace.load_finished_texts()
    dimensions = workspace.load_dimensions()
    warnings = workspace.load_warnings()

    snapshot = WorkspaceSnapshot(
        unfinished_texts=[text for text in texts if text.id not in coded_ids],
        finished_texts=finished,
        dimensions=dimensions,
        quality_warnings=warnings,
    )

    workspace.exports_dir.mkdir(parents=True, exist_ok=True)
    output_path = workspace.exports_dir / f"open_coding_result_{strftime('%Y%m%d_%H%M%S')}.json"
    payload = {
        "meta": {
            "max_nums": meta.max_nums,
            "codebook_nums": meta.codebook_nums,
            "kevin_batch_size": meta.kevin_batch_size,
            "open_mode": meta.open_mode,
            "sample_mode": meta.sample_mode,
            "random_seed": meta.random_seed,
            "prompts_dir": meta.prompts_dir,
            "workspace_dir": meta.workspace_dir,
            "debug_dir": None,
            "finished_texts": len(finished),
            "dimensions": len(dimensions),
            "quality_warnings": warnings,
        },
        "state": snapshot.model_dump(),
    }
    output_path.write_text(
        __import__("json").dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path
