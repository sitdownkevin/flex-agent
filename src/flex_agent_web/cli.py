from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _ensure_project_root() -> Path:
    project_root = Path(__file__).resolve().parents[2]
    root_str = str(project_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return project_root


def main() -> int:
    _ensure_project_root()
    parser = argparse.ArgumentParser(description="CODE: COnstructDevelopmentEngine Web TUI server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9876)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(
        "web.backend.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
