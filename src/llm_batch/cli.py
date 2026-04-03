from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, List

from .models import OutputItem
from .llm.client import LLMClient
from .pipeline import load_batch_from_file, load_batch_from_text, run_batch


def _serialize(outputs: List[Any]) -> str:
    return json.dumps([item.model_dump(exclude_none=True) for item in outputs], ensure_ascii=False)


def main() -> None:
    # Windows 콘솔 출력 인코딩 이슈(한글 깨짐) 완화
    if sys.platform.startswith("win"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="LLM novel batch pipeline")
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input", help="Input JSON/JSONL file path")
    input_group.add_argument("--input-text", help="Input JSON/JSONL as a single text string")
    input_group.add_argument(
        "--stdin",
        action="store_true",
        help="Read JSON/JSONL from stdin (pipe or interactive)",
    )
    parser.add_argument("--output", help="Output file path (optional)")
    parser.add_argument(
        "--incremental-output",
        help="Incremental output path: save each item immediately with original post data (pretty JSON)",
    )
    parser.add_argument("--no-search", action="store_true", help="Disable MCP search")
    parser.add_argument("--use-llm", action="store_true", help="Enable LLM refinement for Unknown items")
    parser.add_argument("--trace", action="store_true", help="Print rule/search/LLM trace to stderr")
    parser.add_argument("--limit", type=int, default=None, help="Process only first N posts (debug)")
    parser.add_argument(
        "--output-schema",
        choices=["v1", "v2"],
        default="v1",
        help="Output schema. v1: identity only. v2: identity + analysis (if enabled).",
    )
    parser.add_argument(
        "--analyze-metadata",
        action="store_true",
        help="Enable Stage2 metadata extraction (micro_tags/sentiment/drift/nsfw/user_segment). Requires --use-llm.",
    )
    parser.add_argument(
        "--agentic-search",
        action="store_true",
        help="Let LLM decide when/what to search (LLM -> MCP search -> LLM). Requires MCP enabled.",
    )
    parser.add_argument(
        "--llm-backend",
        choices=["http", "local"],
        default=None,
        help="LLM backend: http (llama.cpp server) or local (llama-cpp-python)",
    )
    parser.add_argument(
        "--server-type",
        choices=["llama", "vllm"],
        default=None,
        help="LLM serving engine: llama (llama-server, default) or vllm (vLLM)",
    )
    parser.add_argument(
        "--llm-endpoint",
        default=None,
        help="LLM endpoint URL for --llm-backend http (e.g. https://llama.kimjang.me)",
    )
    parser.add_argument("--model-path", default=None, help="GGUF model path for --llm-backend local")
    parser.add_argument(
        "--n-ctx",
        type=int,
        default=None,
        help="Local backend context window (sets env LLM_N_CTX). Recommend 16384.",
    )
    parser.add_argument(
        "--n-gpu-layers",
        type=int,
        default=None,
        help="Local backend GPU layers offload (sets env LLM_N_GPU_LAYERS).",
    )
    parser.add_argument("--chat-format", default=None, help="llama-cpp-python chat_format (e.g. chatml)")
    parser.add_argument(
        "--llm-profile",
        choices=["tool", "general"],
        default=None,
        help="Sampling profile. tool: temp=0.7 top_p=1.0 min_p=0.01 repeat_penalty=1.0. general: temp=1.0 top_p=0.95 min_p=0.01 repeat_penalty=1.0",
    )
    parser.add_argument("--temp", type=float, default=None, help="Override temperature")
    parser.add_argument("--top-p", type=float, default=None, help="Override top_p")
    parser.add_argument("--min-p", type=float, default=None, help="Override min_p (llama.cpp default is 0.05)")
    parser.add_argument("--repeat-penalty", type=float, default=None, help="Set repeat_penalty (disable with 1.0)")
    parser.add_argument("--max-tokens", type=int, default=None, help="Max tokens to generate (default 512)")
    parser.add_argument(
        "--llm-stream",
        action="store_true",
        help="Stream LLM output to stderr (local backend only). Final JSON output is still returned normally.",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Use multi-expert staged pipeline (4-stage analysis with specialized personas).",
    )
    args = parser.parse_args()
    if args.n_ctx is not None:
        os.environ["LLM_N_CTX"] = str(int(args.n_ctx))
    if args.n_gpu_layers is not None:
        os.environ["LLM_N_GPU_LAYERS"] = str(int(args.n_gpu_layers))
    if args.server_type is not None:
        os.environ["LLM_SERVER_TYPE"] = args.server_type

    # Staged pipeline mode (multi-expert)
    if args.staged:
        from .staged_pipeline import run_staged_pipeline, StagedPipeline, _ts
        from .pipeline import _load_json_items, _partition_items
        
        if not args.input:
            print("Error: --staged requires --input file", file=sys.stderr)
            sys.exit(1)
        
        input_path = Path(args.input)
        output_path = Path(args.output) if args.output else None
        
        run_staged_pipeline(input_path, output_path, args.limit)
        return

    if args.input:
        batch = load_batch_from_file(Path(args.input))
    elif args.input_text:
        batch = load_batch_from_text(args.input_text)
    else:
        data = sys.stdin.buffer.read()
        # Windows/PowerShell 파이프 인코딩 이슈 대비: UTF-8 우선, 실패 시 CP949 폴백
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("cp949", errors="replace")
        batch = load_batch_from_text(text)
    llm_client = None
    if args.use_llm:
        llm_client = LLMClient(
            backend=args.llm_backend,
            endpoint=args.llm_endpoint,
            model_path=args.model_path,
            chat_format=args.chat_format,
            stream=args.llm_stream,
            profile=args.llm_profile,
            temperature=args.temp,
            top_p=args.top_p,
            min_p=args.min_p,
            repeat_penalty=args.repeat_penalty,
            max_tokens=args.max_tokens,
            server_type=args.server_type,
        )

    incremental_path = Path(args.incremental_output) if args.incremental_output else None

    outputs = run_batch(
        batch,
        use_search=not args.no_search,
        use_llm=args.use_llm,
        trace=args.trace,
        llm_client=llm_client,
        limit=args.limit,
        agentic_search=args.agentic_search,
        output_schema=args.output_schema,
        analyze_metadata=bool(args.analyze_metadata),
        incremental_output_path=incremental_path,
    )
    payload = _serialize(outputs)

    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        print(payload)

