from __future__ import annotations

import argparse
from pathlib import Path

from .gpt_runner import GPTFullAuditConfig, GPTFullAuditRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run GPT direct full audit for an expert result run.")
    parser.add_argument("--result", required=True, help="Result JSON path")
    parser.add_argument("--log-prefix", required=True, help="Log prefix path without worker suffix")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--input", dest="input_path", default=None, help="Input JSONL path")
    parser.add_argument("--queue", dest="queue_path", default=None, help="Active learning queue CSV path")
    parser.add_argument("--openai-model", required=True, help="GPT model name to use for blind/adjudication passes")
    parser.add_argument("--openai-base-url", default=None, help="Override OpenAI API base URL")
    parser.add_argument("--workers", type=int, default=1, help="Worker count for both blind and adjudication passes")
    parser.add_argument("--timeout-s", type=float, default=300.0, help="HTTP timeout for GPT calls")
    parser.add_argument("--max-casebook-per-class", type=int, default=3, help="Cases per error class in casebook")
    parser.add_argument("--no-resume", action="store_true", help="Do not reuse existing intermediate JSONL outputs")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    runner = GPTFullAuditRunner(
        GPTFullAuditConfig(
            result_path=Path(args.result),
            log_prefix=Path(args.log_prefix),
            output_dir=Path(args.output),
            input_path=Path(args.input_path) if args.input_path else None,
            queue_path=Path(args.queue_path) if args.queue_path else None,
            openai_model=args.openai_model,
            openai_base_url=args.openai_base_url,
            workers=max(1, args.workers),
            timeout_s=max(1.0, args.timeout_s),
            resume=not args.no_resume,
            max_casebook_per_class=max(1, args.max_casebook_per_class),
        )
    )
    outputs = runner.run()
    for key, value in outputs.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
