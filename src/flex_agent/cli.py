from __future__ import annotations

import argparse
import asyncio

from flex_agent.i18n import get_bundle, set_language
from flex_agent.ui.plain_cli import run_plain_cli


def build_parser() -> argparse.ArgumentParser:
    set_language(None)
    cli_text = get_bundle().cli
    parser = argparse.ArgumentParser(description=cli_text.parser_description)
    parser.add_argument(
        "-w", "--workspace",
        default="baseline",
        help=cli_text.workspace_help,
    )
    parser.add_argument(
        "-p", "--prompts-dir",
        default=None,
        dest="prompts_dir",
        help=cli_text.prompts_dir_help,
    )
    parser.add_argument(
        "-l", "--language",
        choices=("zh", "en"),
        default=None,
        help=cli_text.language_help,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(
        run_plain_cli(
            workspace_spec=args.workspace,
            prompts_dir_spec=args.prompts_dir,
            language_spec=args.language,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
