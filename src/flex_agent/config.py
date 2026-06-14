from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from langchain_openai import ChatOpenAI


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_ROOT = PROJECT_ROOT / "prompts"
WORKSPACES_ROOT = PROJECT_ROOT / "workspaces"
DEFAULT_PROMPTS_DIR = PROMPTS_ROOT / "baseline"
DEFAULT_WORKSPACE = WORKSPACES_ROOT / "baseline"

REQUIRED_PROMPT_FILES = (
    "agent_alice.md",
    "agent_bob.md",
    "agent_kevin.md",
    "grounded_theory_background.md",
    "task_background.md",
    "eval_text_alignment.md",
    "eval_dimension_name_alignment.md",
)

_active_prompts_dir: Path = DEFAULT_PROMPTS_DIR
_active_workspace_dir: Path = DEFAULT_WORKSPACE


def path_label(path: Path, *, root: Path = PROJECT_ROOT) -> str:
    resolved = path.resolve()
    root_resolved = root.resolve()
    try:
        return resolved.relative_to(root_resolved).as_posix()
    except ValueError:
        return resolved.as_posix()


def _resolve_under_root(spec: str | Path, *, root: Path, prefix: str) -> Path:
    raw = Path(spec)
    if raw.is_absolute():
        return raw.resolve()

    text = str(spec).strip()
    if not text:
        raise ValueError("Path spec must not be empty.")

    candidate = (PROJECT_ROOT / text).resolve()
    if candidate.exists() or "/" in text or text.startswith(prefix):
        return candidate

    return (root / text).resolve()


def _validate_prompts_dir(path: Path) -> Path:
    if not path.is_dir():
        raise FileNotFoundError(f"Prompts directory not found: {path}")
    missing = [name for name in REQUIRED_PROMPT_FILES if not (path / name).is_file()]
    if missing:
        raise FileNotFoundError(
            f"Prompts directory {path} is missing required files: {', '.join(missing)}"
        )
    return path


def resolve_prompts_dir(spec: str | Path = "baseline") -> Path:
    return _validate_prompts_dir(_resolve_under_root(spec, root=PROMPTS_ROOT, prefix="prompts/"))


def resolve_workspace_dir(spec: str | Path = "baseline") -> Path:
    return _resolve_under_root(spec, root=WORKSPACES_ROOT, prefix="workspaces/")


def set_prompts_dir(spec: str | Path) -> Path:
    global _active_prompts_dir
    _active_prompts_dir = resolve_prompts_dir(spec)
    return _active_prompts_dir


def get_prompts_dir() -> Path:
    return _active_prompts_dir


def set_workspace_dir(spec: str | Path) -> Path:
    global _active_workspace_dir
    _active_workspace_dir = resolve_workspace_dir(spec)
    return _active_workspace_dir


def get_workspace_dir() -> Path:
    return _active_workspace_dir


def load_env_file(path: Path | None = None) -> None:
    env_path = path or PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class ModelConfig:
    default_model: str
    pro_model: str
    timeout: float
    max_retries: int
    seed: int | None


def load_model_config(
    *,
    timeout: float = 300.0,
    max_retries: int = 5,
) -> ModelConfig:
    seed_raw = os.getenv("OPENAI_SEED", "42").strip()
    seed = int(seed_raw) if seed_raw else None
    return ModelConfig(
        default_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        pro_model=os.getenv("OPENAI_MODEL_PRO", "gpt-4o"),
        timeout=timeout,
        max_retries=max_retries,
        seed=seed,
    )


def build_llm(
    model_name: str,
    *,
    timeout: float = 300.0,
    max_retries: int = 5,
    seed: int | None = None,
) -> ChatOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    kwargs: dict = {
        "model": model_name,
        "temperature": 0,
        "top_p": 1,
        "frequency_penalty": 0,
        "presence_penalty": 0,
        "api_key": api_key,
        "timeout": timeout,
        "max_retries": max_retries,
    }
    if seed is not None:
        kwargs["seed"] = seed
    base_url = os.getenv("OPENAI_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)
