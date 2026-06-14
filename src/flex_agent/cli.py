from __future__ import annotations

import argparse
import asyncio

from flex_agent.ui.plain_cli import run_plain_cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="flex-agent interactive open coding CLI")
    parser.add_argument(
        "--workspace",
        default="baseline",
        help="Workspace category or path (default: baseline -> workspaces/baseline).",
    )
    parser.add_argument(
        "--prompts-dir",
        default="baseline",
        dest="prompts_dir",
        help="Prompt set name or path (default: baseline -> prompts/baseline).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(
        run_plain_cli(
            workspace_spec=args.workspace,
            prompts_dir_spec=args.prompts_dir,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
