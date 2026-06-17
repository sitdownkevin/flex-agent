from __future__ import annotations

import argparse
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from direct_eval.pipeline import run_experiment
from flex_agent.i18n import get_bundle, set_language


def build_parser() -> argparse.ArgumentParser:
    set_language(None)
    direct_text = get_bundle().direct
    parser = argparse.ArgumentParser(
        description=direct_text.parser_description,
    )
    parser.add_argument(
        "--input",
        default="data/codebook_done_human.jsonl",
        help=direct_text.input_help,
    )
    parser.add_argument(
        "--output",
        default="direct_inference_eval/runs/default",
        help=direct_text.output_help,
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help=direct_text.batch_size_help,
    )
    parser.add_argument(
        "--mode",
        choices=("open", "axial", "both"),
        default="both",
        help=direct_text.mode_help,
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=direct_text.limit_help,
    )
    parser.add_argument(
        "--model",
        default=None,
        help=direct_text.model_help,
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help=direct_text.resume_help,
    )
    parser.add_argument(
        "--no-llm-semantic",
        action="store_true",
        help=direct_text.no_llm_semantic_help,
    )
    parser.add_argument(
        "--language",
        choices=("zh", "en"),
        default=None,
        help=direct_text.language_help,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    language = set_language(args.language)
    direct_text = get_bundle(language).direct
    result = run_experiment(
        input_path=Path(args.input),
        output_dir=Path(args.output),
        batch_size=args.batch_size,
        mode=args.mode,
        limit=args.limit,
        model=args.model,
        resume=args.resume,
        run_llm_semantic=not args.no_llm_semantic,
        language=language,
    )
    print(direct_text.predictions.format(path=result["records_path"]))
    for report_path in result["reports"]:
        print(direct_text.report.format(path=report_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
