from __future__ import annotations

"""
개발/로컬 실행용 원클릭 엔트리포인트.

목표:
- 매번 `llm-batch ...` 옵션/환경변수 치기 귀찮을 때
- 여기 설정만 바꾸고 `python main.py` 로 실행
"""

import os
import sys
from datetime import datetime
from pathlib import Path


def _set_env(k: str, v: str) -> None:
    # "설정 다 때려박기" 용도이므로 기본적으로 강제 override 한다.
    os.environ[k] = v


def main() -> None:
    repo_root = Path(__file__).resolve().parent

    # PowerShell/Windows 콘솔/리다이렉트 인코딩 이슈 완화
    # - 파일 로그는 우리가 UTF-8-SIG로 직접 쓰므로, 터미널/리다이렉트에 덜 의존하게 된다.
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    # ===== 사용자 환경에 맞게 여기만 수정 =====
    INPUT_PATH = repo_root / "tests" / "inputs" / "sample.jsonl"
    OUTPUT_PATH = repo_root / "_last_run.json"
    LOG_DIR = repo_root / "logs"
    OUT_DIR = repo_root / "out"  # 처리 결과 JSON 저장 디렉토리
    USE_LLM = True
    TRACE = True
    DEBUG_LLM_MESSAGES = True  # LLM이 받는 messages(system/user)를 stderr로 덤프
    STREAM_LLM_TOKENS = True  # 실제 생성 토큰을 stderr로 실시간 출력(--llm-stream)
    NO_SEARCH = False
    AGENTIC_SEARCH = True
    LIMIT = None  # 디버그 시 빠르게. 전체 돌리려면 None 으로
    OUTPUT_SCHEMA = "v2"  # "v1" or "v2"
    ANALYZE_METADATA = True  # V2: micro_tags/sentiment/drift/nsfw/user_segment

    # ===== LLM 실행 환경 선택 =====
    # "local": 로컬 llama-cpp-python (GPU 필요)
    # "remote": 원격 llama-server (https://llama.kimjang.me/)
    LLM_MODE = "remote"  # "local" or "remote"

    # MCP(SearchXNG)
    _set_env("MCP_ENDPOINT", "http://localhost:3333")

    # ===== LLM 공통 설정 =====
    _set_env("LLM_N_CTX", "16384")
    _set_env("LLM_MAX_TOKENS", "16384")
    _set_env("LLM_JSON_GRAMMAR", "1")
    _set_env("LLM_PROGRESS_EVERY", "5")
    _set_env("LLM_MAX_SEARCH_ROUNDS", "2")
    _set_env("LLM_MAX_SEARCH_QUERIES", "2")
    _set_env("LLM_CACHE_TYPE_K", "f16")
    _set_env("LLM_CACHE_TYPE_V", "f16")
    _set_env("LLM_PRINT_TIMINGS", "1")
    _set_env("MCP_TOP_K_RESULTS", "5")
    _set_env("MCP_MAX_CONTENT_CHARS", "400")
    if DEBUG_LLM_MESSAGES:
        _set_env("LLM_DEBUG_DUMP_MESSAGES", "0")
        _set_env("LLM_DEBUG_DUMP_MAX_CHARS", "0")
    if STREAM_LLM_TOKENS:
        _set_env("LLM_STREAM", "1")
    # GLM-4.7-Flash reasoning 모드 제어
    _set_env("LLM_ENABLE_THINKING", "1")
    _set_env("LLM_THINK_STREAM", "1")

    if LLM_MODE == "local":
        # ===== Local: llama-cpp-python =====
        _set_env("LLM_BACKEND", "local")
        _set_env(
            "LLM_MODEL_PATH",
            r"C:\Users\kimjang\AppData\Local\llama.cpp\unsloth_GLM-4.7-Flash-GGUF_GLM-4.7-Flash-UD-IQ3_XXS.gguf",
        )
        _set_env("LLM_N_GPU_LAYERS", "60")
        _set_env("LLM_PRINT_SYSTEM_INFO", "1")
    elif LLM_MODE == "remote":
        # ===== Remote: llama-server (https://llama.kimjang.me/) =====
        # 서버 설정:
        # ./llama-server -hf unsloth/GLM-4.7-Flash-GGUF:IQ3_XXS \
        #   --host 0.0.0.0 --port 10000 -sm none -mg 1 -ngl 60 \
        #   -c 16384 -n 16384 -fa off -ctk f16 -ctv f16 --jinja
        _set_env("LLM_BACKEND", "http")
        _set_env("LLM_ENDPOINT", "https://llama.kimjang.me")
        _set_env("LLM_MODEL", "unsloth/GLM-4.7-Flash-GGUF:IQ3_XXS")
    else:
        raise ValueError(f"Unknown LLM_MODE: {LLM_MODE}. Use 'local' or 'remote'.")

    # ===== 아래는 보통 건드릴 필요 없음 =====
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Input not found: {INPUT_PATH}")

    # 콘솔 출력 로그를 logs/ 아래에 저장(터미널 truncate 방지)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)  # 결과 저장 디렉토리 생성
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"run_{ts}.log"
    # 처리 결과를 out/ 디렉토리에도 타임스탬프 포함하여 저장
    out_result_path = OUT_DIR / f"result_{ts}.json"
    _orig_out = sys.stdout
    _orig_err = sys.stderr

    class _Tee:
        def __init__(self, *streams):
            self._streams = streams

        def write(self, s):
            wrote = 0
            for st in self._streams:
                try:
                    st.write(s)
                    wrote = max(wrote, len(s) if isinstance(s, str) else 0)
                except Exception:
                    pass
            return wrote

        def flush(self):
            for st in self._streams:
                try:
                    st.flush()
                except Exception:
                    pass

        def isatty(self):
            try:
                return any(getattr(st, "isatty", lambda: False)() for st in self._streams)
            except Exception:
                return False

        @property
        def encoding(self):
            # best effort
            for st in self._streams:
                enc = getattr(st, "encoding", None)
                if enc:
                    return enc
            return "utf-8"

        def reconfigure(self, **kwargs):
            # allow llm_batch.cli to call sys.stdout/sys.stderr.reconfigure on Windows
            for st in self._streams:
                try:
                    rc = getattr(st, "reconfigure", None)
                    if callable(rc):
                        rc(**kwargs)
                except Exception:
                    pass

    # UTF-8-SIG(BOM)로 저장하면 Windows 메모장에서도 한글이 안 깨짐
    with log_path.open("w", encoding="utf-8-sig", buffering=1, newline="") as f:
        sys.stdout = _Tee(_orig_out, f)
        sys.stderr = _Tee(_orig_err, f)

        print(f"[main] 로그 저장: {log_path}", file=sys.stderr, flush=True)
        print(f"[main] 결과 저장: {out_result_path}", file=sys.stderr, flush=True)
        print(f"[main] LLM_MODE: {LLM_MODE}", file=sys.stderr, flush=True)
        print(f"[main] args will be set for llm-batch", file=sys.stderr, flush=True)

        from llm_batch.cli import main as cli_main

        argv = ["llm-batch", "--input", str(INPUT_PATH)]
        # 항상 결과를 파일로 남겨, 터미널 출력이 truncate 되어도 재현/분석 가능하게 한다.
        argv += ["--output", str(OUTPUT_PATH)]
        # Incremental 저장: 원본 데이터 + 분석 결과를 예쁘게 저장
        argv += ["--incremental-output", str(out_result_path)]
        if NO_SEARCH:
            argv.append("--no-search")
        if USE_LLM:
            argv.append("--use-llm")
        if TRACE:
            argv.append("--trace")
        if AGENTIC_SEARCH:
            argv.append("--agentic-search")
        if STREAM_LLM_TOKENS:
            argv.append("--llm-stream")
        if LIMIT is not None:
            argv += ["--limit", str(int(LIMIT))]

        # LLM 백엔드 설정 (local vs remote)
        if LLM_MODE == "local":
            argv += ["--llm-backend", "local", "--model-path", os.environ["LLM_MODEL_PATH"]]
        elif LLM_MODE == "remote":
            argv += ["--llm-backend", "http", "--llm-endpoint", os.environ["LLM_ENDPOINT"]]

        argv += ["--output-schema", OUTPUT_SCHEMA]
        if ANALYZE_METADATA:
            argv.append("--analyze-metadata")

        sys.argv = argv
        try:
            cli_main()
            # 처리 완료 메시지 (incremental 저장은 파이프라인에서 자동으로 처리됨)
            print(f"\n[main] ✅ 처리 완료!", file=sys.stderr, flush=True)
            print(f"  - 분석 결과 (slim): {OUTPUT_PATH}", file=sys.stderr, flush=True)
            print(f"  - 전체 결과 (원본+분석): {out_result_path}", file=sys.stderr, flush=True)
        finally:
            sys.stdout = _orig_out
            sys.stderr = _orig_err


if __name__ == "__main__":
    main()