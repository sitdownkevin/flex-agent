from __future__ import annotations

from pathlib import Path

from flex_agent.config import get_prompts_dir


def read_prompt_file(filename: str, *, prompts_dir: Path | None = None) -> str:
    base = (prompts_dir or get_prompts_dir()).resolve()
    return (base / filename).read_text(encoding="utf-8")
