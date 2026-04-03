from __future__ import annotations

import argparse
from pathlib import Path

from .runner import AuditConfig, AuditRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run exhaustive audit for an expert result run.")
    parser.add_argument("--result", required=True, help="Result JSON path")
    parser.add_argument("--log-prefix", required=True, help="Log prefix path without worker suffix")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--input", dest="input_path", default=None, help="Input JSONL path")
    parser.add_argument("--queue", dest="queue_path", default=None, help="Active learning queue CSV path")
    parser.add_argument("--skip-blind-reread", action="store_true", help="Skip blind LLM reread")
    parser.add_argument("--skip-targeted-explanations", action="store_true", help="Skip targeted explanation pass")
    parser.add_argument("--blind-workers", type=int, default=1, help="Blind reread worker count")
    parser.add_argument("--explanation-workers", type=int, default=1, help="Targeted explanation worker count")
    parser.add_argument("--max-dossiers-per-label", type=int, default=3, help="Cases per risk label in dossier")
    parser.add_argument("--max-explanations", type=int, default=0, help="Limit targeted explanations; 0 means all flagged rows")
    parser.add_argument("--no-resume", action="store_true", help="Do not reuse existing JSONL outputs")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    runner = AuditRunner(
        AuditConfig(
            result_path=Path(args.result),
            log_prefix=Path(args.log_prefix),
            output_dir=Path(args.output),
            input_path=Path(args.input_path) if args.input_path else None,
            queue_path=Path(args.queue_path) if args.queue_path else None,
            enable_blind_reread=not args.skip_blind_reread,
            enable_targeted_explanations=not args.skip_targeted_explanations,
            blind_workers=max(1, args.blind_workers),
            explanation_workers=max(1, args.explanation_workers),
            resume=not args.no_resume,
            max_dossiers_per_label=max(1, args.max_dossiers_per_label),
            max_explanations=max(0, args.max_explanations),
        )
    )
    outputs = runner.run()
    for key, value in outputs.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
