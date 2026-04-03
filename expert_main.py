from __future__ import annotations

"""
Agentic Pipeline (유기적 전문가 시스템) 원클릭 엔트리포인트.

목표:
- tests/inputs/sample.jsonl 같은 커뮤니티 게시글을 Agentic Pipeline으로 분석
- main.py와 동일한 LLM/MCP 환경설정 사용
- 토큰 사용량, 로그, 결과를 main.py처럼 저장
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, Empty
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# 대시보드 비활성화 플래그: --no-dashboard
_NO_DASHBOARD = "--no-dashboard" in sys.argv

# ─── CLI 인자 파싱 ──────────────────────────────────────
def _build_arg_parser(*, add_help: bool) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Agentic Pipeline (유기적 전문가 시스템)",
        add_help=add_help,  # 기존 sys.argv[1] 호환성 유지
    )
    parser.add_argument("input", nargs="?", default=None, help="입력 JSONL 파일 경로")
    parser.add_argument("--input", dest="input_flag", default=None, help="입력 JSONL 파일 경로 (--input 형식)")
    parser.add_argument("--output", "-o", default=None, help="출력 JSON 파일 경로")
    parser.add_argument("--parallel", "-p", type=int, default=1, help="병렬 처리 워커 수 (기본: 1)")
    parser.add_argument("--no-dashboard", action="store_true", help="대시보드 비활성화")
    parser.add_argument(
        "--server-type", "-s",
        choices=["llama", "vllm"],
        default=None,
        help="LLM 서빙 엔진 선택: llama (llama-server, 기본) 또는 vllm",
    )
    parser.add_argument("--llm-endpoint", default=None, help="LLM 서버 엔드포인트 URL (예: http://a100:8000)")
    parser.add_argument("--llm-model", default=None, help="사용할 모델명 (예: Qwen/Qwen3-32B)")
    parser.add_argument("--vlm", choices=["on", "off"], default=None, help="멀티모달/VLM 보강 사용 여부")
    parser.add_argument("--ocr", choices=["on", "off"], default=None, help="VLM 경로에서 OCR 텍스트 추출 여부")
    parser.add_argument("--vlm-fetch-timeout", type=float, default=None, help="이미지 fetch timeout (초)")
    parser.add_argument("--vlm-max-image-bytes", type=int, default=None, help="개별 이미지 최대 바이트")
    parser.add_argument("--vlm-max-total-bytes", type=int, default=None, help="포스트당 이미지 총 바이트 상한")
    parser.add_argument("--vlm-chunk-max-images", type=int, default=None, help="멀티모달 청크당 최대 이미지 수")
    parser.add_argument("--vlm-chunk-max-bytes", type=int, default=None, help="멀티모달 청크당 최대 바이트")
    parser.add_argument("--slang-db", choices=["on", "off"], default=None, help="중앙 slang DB 검토용 저장 사용 여부")
    parser.add_argument("--slang-db-path", default=None, help="중앙 slang DB JSON 경로")
    parser.add_argument("--slang-db-flush-posts", type=int, default=None, help="slang DB flush post 간격")
    parser.add_argument("--slang-db-flush-seconds", type=int, default=None, help="slang DB flush 시간 간격(초)")
    parser.add_argument("--no-auto-up-shards", action="store_true", help="로컬 MCP/WARP shard 자동 기동 비활성화")
    return parser


def _parse_args() -> argparse.Namespace:
    if any(arg in {"-h", "--help"} for arg in sys.argv[1:]):
        _build_arg_parser(add_help=True).print_help(sys.stderr)
        raise SystemExit(0)

    parser = _build_arg_parser(add_help=False)
    # 알 수 없는 인자 무시 (기존 호환성)
    args, _ = parser.parse_known_args()
    return args

_CLI_ARGS = _parse_args()
# --input 플래그가 positional input보다 우선
if _CLI_ARGS.input_flag:
    _CLI_ARGS.input = _CLI_ARGS.input_flag
_PARALLEL = max(1, _CLI_ARGS.parallel)

# ─── 스레드 안전 로그 출력 ──────────────────────────────
_print_lock = threading.Lock()
_results_lock = threading.Lock()

# ─── 병렬 모드: 워커별 로그 파일 라우팅 ─────────────────
_worker_tls = threading.local()  # .log_file, .worker_id 저장
_parallel_mode = False  # _Tee에서 참조
_shutdown_event = threading.Event()  # Ctrl+C 종료 시그널
_main_thread_id = threading.main_thread().ident  # 병렬 모드 콘솔 출력 제어


def _set_env(k: str, v: str) -> None:
    """환경변수 강제 설정"""
    os.environ[k] = v


def _resolve_toggle(value: Optional[str], *, env_key: str, default: str) -> str:
    raw = value if value is not None else os.getenv(env_key, default)
    normalized = str(raw or default).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return "1"
    if normalized in {"0", "false", "no", "off"}:
        return "0"
    return "1" if str(default).strip().lower() in {"1", "true", "yes", "on"} else "0"


def _configure_mcp_endpoints(default_count: int) -> None:
    """MCP shard endpoint를 자동 구성한다.

    우선순위:
    1) MCP_ENDPOINTS 직접 지정
    2) MCP_ENDPOINT 단일 지정
    3) MCP_SHARD_* + parallel 기반 자동 생성
    """
    raw_endpoints = os.getenv("MCP_ENDPOINTS", "").strip()
    raw_endpoint = os.getenv("MCP_ENDPOINT", "").strip()

    if raw_endpoints:
        endpoints = [p.strip().rstrip("/") for p in raw_endpoints.split(",") if p.strip()]
        if endpoints and not raw_endpoint:
            _set_env("MCP_ENDPOINT", endpoints[0])
        _set_env("MCP_ENDPOINTS_AUTOGEN", "0")
        return

    if raw_endpoint:
        _set_env("MCP_ENDPOINTS_AUTOGEN", "0")
        return

    try:
        shard_count = max(1, int(os.getenv("MCP_SHARD_COUNT", str(default_count))))
    except Exception:
        shard_count = max(1, default_count)
    try:
        base_port = int(os.getenv("MCP_SHARD_BASE_PORT", "3333"))
    except Exception:
        base_port = 3333

    scheme = os.getenv("MCP_SHARD_SCHEME", "http").strip() or "http"
    host = os.getenv("MCP_SHARD_HOST", "localhost").strip() or "localhost"

    endpoints = [f"{scheme}://{host}:{base_port + idx}" for idx in range(shard_count)]
    _set_env("MCP_ENDPOINTS", ",".join(endpoints))
    _set_env("MCP_ENDPOINT", endpoints[0])
    _set_env("MCP_ENDPOINTS_AUTOGEN", "1")


def _get_mcp_endpoint_pool() -> List[str]:
    raw_endpoints = os.getenv("MCP_ENDPOINTS", "").strip()
    if raw_endpoints:
        endpoints = [p.strip().rstrip("/") for p in raw_endpoints.split(",") if p.strip()]
        if endpoints:
            return endpoints

    raw_endpoint = os.getenv("MCP_ENDPOINT", "").strip().rstrip("/")
    if raw_endpoint:
        return [raw_endpoint]

    return ["http://localhost:3333"]


def _can_auto_manage_local_shards() -> bool:
    if _CLI_ARGS.no_auto_up_shards:
        return False
    if os.getenv("MCP_ENDPOINTS_AUTOGEN", "0").strip() != "1":
        return False
    host = os.getenv("MCP_SHARD_HOST", "localhost").strip().lower()
    return host in {"localhost", "127.0.0.1"}


def _auto_up_local_shards(repo_root: Path, shard_count: int) -> None:
    if shard_count <= 0 or not _can_auto_manage_local_shards():
        return

    base_port = os.getenv("MCP_SHARD_BASE_PORT", "3333").strip() or "3333"
    tool_path = repo_root / "tools" / "warp_shards.py"
    cmd = [
        sys.executable,
        str(tool_path),
        "up",
        "--count",
        str(shard_count),
        "--mcp-base-port",
        base_port,
    ]
    print(
        f"[expert_main] 로컬 MCP/WARP shard {shard_count}개 자동 기동 중...",
        file=sys.stderr,
        flush=True,
    )
    subprocess.run(cmd, cwd=repo_root, check=True)


def _memo_local_shard_status(repo_root: Path, memo_path: Path) -> None:
    tool_path = repo_root / "tools" / "warp_shards.py"
    cmd = [sys.executable, str(tool_path), "status", "--json"]
    proc = subprocess.run(
        cmd,
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = proc.stdout.strip()
    if not payload:
        raise RuntimeError("empty shard status payload")

    items = json.loads(payload)
    memo_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[expert_main] WARP shard 메모 저장: {memo_path}", file=sys.stderr, flush=True)
    for item in items:
        service = str(item.get("service") or "?")
        running = bool(item.get("running"))
        trace = item.get("trace") or {}
        if not isinstance(trace, dict):
            trace = {}
        ip = trace.get("ip", "?")
        warp = trace.get("warp", "?")
        loc = trace.get("loc", "?")
        colo = trace.get("colo", "?")
        print(
            f"[expert_main] {service}: running={'yes' if running else 'no'}, ip={ip}, warp={warp}, loc={loc}, colo={colo}",
            file=sys.stderr,
            flush=True,
        )


def main() -> None:
    repo_root = Path(__file__).resolve().parent

    # PowerShell/Windows 콘솔/리다이렉트 인코딩 이슈 완화
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    # ===== 사용자 환경에 맞게 여기만 수정 =====
    # 명령줄 인자로 입력 파일 지정 가능
    if _CLI_ARGS.input:
        INPUT_PATH = Path(_CLI_ARGS.input)
    else:
        #INPUT_PATH = repo_root / "tests" / "inputs" / "sample.jsonl"
        INPUT_PATH = repo_root / "tests" / "inputs" / "test01.jsonl"
    
    LOG_DIR = repo_root / "logs"
    OUT_DIR = repo_root / "out"
    LIMIT = None  # 디버그 시 숫자 지정, 전체 돌리려면 None

    # ===== LLM 실행 환경 선택 =====
    # "local": 로컬 llama-cpp-python (GPU 필요)
    # "remote": 원격 llama-server 또는 vLLM
    LLM_MODE = "remote"  # "local" or "remote"
    # 서빙 엔진 선택: "llama" (llama-server/llama.cpp) 또는 "vllm" (vLLM)
    #LLM_SERVER_TYPE = _CLI_ARGS.server_type or os.getenv("LLM_SERVER_TYPE", "llama")
    LLM_SERVER_TYPE = _CLI_ARGS.server_type or os.getenv("LLM_SERVER_TYPE", "vllm")

    # MCP(SearchXNG/Crawl4AI shard)
    # 외부에서 MCP_ENDPOINTS를 넘기면 워커별 shard 분산을 그대로 사용한다.
    _configure_mcp_endpoints(_PARALLEL)

    # ===== LLM 공통 설정 (main.py와 동일) =====
    _set_env("LLM_N_CTX", "131072")
    # 컨텍스트 경고/가드 기준을 실제 n_ctx와 맞춘다.  (vLLM --max-model-len 131072 대응)
    _set_env("LLM_CONTEXT_LIMIT_TOKENS", os.environ.get("LLM_N_CTX", "131072"))
    _set_env("LLM_MAX_TOKENS", "65536")
    _set_env("LLM_EXPERT_MAX_TOKENS", os.environ.get("LLM_EXPERT_MAX_TOKENS", "65536"))
    _set_env("LLM_VERIFIER_MAX_TOKENS", os.environ.get("LLM_VERIFIER_MAX_TOKENS", os.environ.get("LLM_EXPERT_MAX_TOKENS", "65536")))
    _set_env("LLM_VERIFIER_COMPACT_MAX_TOKENS", os.environ.get("LLM_VERIFIER_COMPACT_MAX_TOKENS", os.environ.get("LLM_EXPERT_MAX_TOKENS", "65536")))
    _set_env("LLM_RELATION_JUDGE_MAX_TOKENS", os.environ.get("LLM_RELATION_JUDGE_MAX_TOKENS", os.environ.get("LLM_EXPERT_MAX_TOKENS", "65536")))
    _set_env("LLM_REASON_REVIEW_MAX_TOKENS", os.environ.get("LLM_REASON_REVIEW_MAX_TOKENS", os.environ.get("LLM_MAX_TOKENS", "65536")))
    _set_env("LLM_JSON_GRAMMAR", "1")
    _set_env("LLM_PROGRESS_EVERY", "5")
    _set_env("LLM_MAX_SEARCH_ROUNDS", "6")
    # 검색 증강 제한 기본 해제: 커뮤니티 글 recall 확보 우선
    _set_env("LLM_MAX_SEARCH_QUERIES", "200")
    _set_env("LLM_ENABLE_SEARCH_SUPPRESSION", "0")
    _set_env("LLM_FLASH_ATTN", "1")
    _set_env("LLM_CACHE_TYPE_K", "q4_0")
    _set_env("LLM_CACHE_TYPE_V", "q4_0")
    _set_env("LLM_PRINT_TIMINGS", "1")
    _set_env("MCP_TOP_K_RESULTS", "10")  # 검색 결과 상위 10개 사용
    _set_env("MCP_DEFAULT_NUM_RESULTS", "15")  # SearXNG에서 15개 요청
    _set_env("MCP_MAX_CONTENT_CHARS", "0")
    _set_env("PIPELINE_FETCH_CONCURRENCY", os.getenv("PIPELINE_FETCH_CONCURRENCY", "4"))
    _set_env("PIPELINE_SEARCH_CONCURRENCY", os.getenv("PIPELINE_SEARCH_CONCURRENCY", "2"))
    
    # ===== 스트리밍 및 디버그 설정 (main.py와 동일) =====
    _set_env("LLM_DEBUG_DUMP_MESSAGES", os.environ.get("LLM_DEBUG_DUMP_MESSAGES", "0"))
    _set_env("LLM_DEBUG_DUMP_MAX_CHARS", os.environ.get("LLM_DEBUG_DUMP_MAX_CHARS", "0"))
    _set_env("LLM_STREAM", "1")
    _set_env("LLM_VLM", _resolve_toggle(_CLI_ARGS.vlm, env_key="LLM_VLM", default="0"))
    _set_env("LLM_OCR", _resolve_toggle(_CLI_ARGS.ocr, env_key="LLM_OCR", default="1"))
    _set_env(
        "LLM_VLM_FETCH_TIMEOUT",
        str(_CLI_ARGS.vlm_fetch_timeout if _CLI_ARGS.vlm_fetch_timeout is not None else os.getenv("LLM_VLM_FETCH_TIMEOUT", "12")),
    )
    _set_env(
        "LLM_VLM_MAX_IMAGE_BYTES",
        str(_CLI_ARGS.vlm_max_image_bytes if _CLI_ARGS.vlm_max_image_bytes is not None else os.getenv("LLM_VLM_MAX_IMAGE_BYTES", "8388608")),
    )
    _set_env(
        "LLM_VLM_MAX_TOTAL_BYTES",
        str(_CLI_ARGS.vlm_max_total_bytes if _CLI_ARGS.vlm_max_total_bytes is not None else os.getenv("LLM_VLM_MAX_TOTAL_BYTES", "50331648")),
    )
    _set_env(
        "LLM_VLM_CHUNK_MAX_IMAGES",
        str(_CLI_ARGS.vlm_chunk_max_images if _CLI_ARGS.vlm_chunk_max_images is not None else os.getenv("LLM_VLM_CHUNK_MAX_IMAGES", "8")),
    )
    _set_env(
        "LLM_VLM_CHUNK_MAX_BYTES",
        str(_CLI_ARGS.vlm_chunk_max_bytes if _CLI_ARGS.vlm_chunk_max_bytes is not None else os.getenv("LLM_VLM_CHUNK_MAX_BYTES", "12582912")),
    )
    _set_env("LLM_VLM_MAX_TOKENS", os.environ.get("LLM_VLM_MAX_TOKENS", "12288"))
    _set_env("PIPELINE_SLANG_DB", _resolve_toggle(_CLI_ARGS.slang_db, env_key="PIPELINE_SLANG_DB", default="0"))
    _set_env(
        "PIPELINE_SLANG_DB_PATH",
        str(_CLI_ARGS.slang_db_path if _CLI_ARGS.slang_db_path is not None else os.getenv("PIPELINE_SLANG_DB_PATH", "slang_db/slang_db.json")),
    )
    _set_env(
        "PIPELINE_SLANG_DB_FLUSH_POSTS",
        str(_CLI_ARGS.slang_db_flush_posts if _CLI_ARGS.slang_db_flush_posts is not None else os.getenv("PIPELINE_SLANG_DB_FLUSH_POSTS", "5")),
    )
    _set_env(
        "PIPELINE_SLANG_DB_FLUSH_SECONDS",
        str(_CLI_ARGS.slang_db_flush_seconds if _CLI_ARGS.slang_db_flush_seconds is not None else os.getenv("PIPELINE_SLANG_DB_FLUSH_SECONDS", "5")),
    )
    
    # GLM-4.7-Flash reasoning 모드 제어
    _set_env("LLM_ENABLE_THINKING", "0")
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
        # vocab_only probe 비활성화 (컨텍스트 생성 충돌 방지)
        _set_env("LLM_USE_GGUF_JINJA", "0")
    elif LLM_MODE == "remote":
        # ===== Remote: llama-server 또는 vLLM =====
        _set_env("LLM_BACKEND", "http")
        _set_env("LLM_SERVER_TYPE", LLM_SERVER_TYPE)  # "llama" or "vllm"
        
        if LLM_SERVER_TYPE == "vllm":
            # ===== vLLM 서빙 =====
            #_set_env("LLM_ENDPOINT", _CLI_ARGS.llm_endpoint or os.getenv("LLM_ENDPOINT", "http://localhost:20000/"))
            _set_env("LLM_ENDPOINT", _CLI_ARGS.llm_endpoint or os.getenv("LLM_ENDPOINT", "http://a100:10000/"))
            #_set_env("LLM_ENDPOINT", _CLI_ARGS.llm_endpoint or os.getenv("LLM_ENDPOINT", "http://10.20.0.101:8000/"))
            _set_env("LLM_MODEL", _CLI_ARGS.llm_model or os.getenv("LLM_MODEL", "Sehyo/Qwen3.5-35B-A3B-NVFP4"))
            #_set_env("LLM_MODEL", _CLI_ARGS.llm_model or os.getenv("LLM_MODEL", "AxionML/Qwen3.5-35B-A3B-NVFP4"))
            # vLLM 전용 샘플링 기본값
            _set_env("LLM_TEMP", os.getenv("LLM_TEMP", "0.7"))
            _set_env("LLM_TOP_P", os.getenv("LLM_TOP_P", "0.8"))
            _set_env("LLM_MIN_P", os.getenv("LLM_MIN_P", "0.0"))
            _set_env("LLM_REPEAT_PENALTY", os.getenv("LLM_REPEAT_PENALTY", "1.0"))
            _set_env("LLM_VLLM_TOP_K", os.getenv("LLM_VLLM_TOP_K", "20"))
            _set_env("LLM_VLLM_PRESENCE_PENALTY", os.getenv("LLM_VLLM_PRESENCE_PENALTY", "1.5"))
            
            # ===== 전문가별 temperature =====
            # Qwen 공식 권장값 0.7로 통일 (local LLM 최적 샘플링)
            # 환경변수로 오버라이드 가능: LLM_TEMP_{EXPERT} (예: LLM_TEMP_DECODER=0.4)
            _QWEN_TEMP = "0.7"
            _set_env("LLM_TEMP_GATEKEEPER", os.getenv("LLM_TEMP_GATEKEEPER", _QWEN_TEMP))
            _set_env("LLM_TEMP_DISCOURSE", os.getenv("LLM_TEMP_DISCOURSE", _QWEN_TEMP))
            _set_env("LLM_TEMP_DECODER", os.getenv("LLM_TEMP_DECODER", _QWEN_TEMP))
            _set_env("LLM_TEMP_VERIFIER", os.getenv("LLM_TEMP_VERIFIER", _QWEN_TEMP))
            _set_env("LLM_TEMP_CRITIC", os.getenv("LLM_TEMP_CRITIC", _QWEN_TEMP))
            _set_env("LLM_TEMP_SYNTHESIZER", os.getenv("LLM_TEMP_SYNTHESIZER", _QWEN_TEMP))
            _set_env("LLM_TEMP_ARBITER", os.getenv("LLM_TEMP_ARBITER", _QWEN_TEMP))
            _set_env("LLM_TEMP_JURY", os.getenv("LLM_TEMP_JURY", _QWEN_TEMP))
            _set_env("LLM_TEMP_ADVOCATE", os.getenv("LLM_TEMP_ADVOCATE", _QWEN_TEMP))
            _set_env("LLM_TEMP_SKEPTIC", os.getenv("LLM_TEMP_SKEPTIC", _QWEN_TEMP))
            _set_env("LLM_TEMP_JUDGE", os.getenv("LLM_TEMP_JUDGE", _QWEN_TEMP))
        else:
            # ===== llama-server 서빙 (기본) =====
            _set_env("LLM_ENDPOINT", _CLI_ARGS.llm_endpoint or os.getenv("LLM_ENDPOINT", "http://a100:10000/"))
            _set_env("LLM_MODEL", _CLI_ARGS.llm_model or os.getenv("LLM_MODEL", "unsloth/Qwen3.5-35B-A3B-GGUF:UD-IQ3_XXS"))
        #_set_env("LLM_ENDPOINT", "https://llama.kimjang.me")
        #_set_env("LLM_ENDPOINT", "http://127.0.0.1:20000/")
    else:
        raise ValueError(f"Unknown LLM_MODE: {LLM_MODE}. Use 'local' or 'remote'.")

    # 서빙 엔진 로그
    _srv = os.getenv('LLM_SERVER_TYPE', 'llama')
    _ep = os.getenv('LLM_ENDPOINT', '?')
    _mdl = os.getenv('LLM_MODEL', '?')
    print(f"[config] server_type={_srv}, endpoint={_ep}, model={_mdl}", file=sys.stderr, flush=True)
    print(
        "[config] vlm={vlm}, ocr={ocr}, fetch_timeout={timeout}, max_image_bytes={img}, "
        "max_total_bytes={total}, chunk_max_images={chunk_i}, chunk_max_bytes={chunk_b}".format(
            vlm=os.getenv("LLM_VLM", "0"),
            ocr=os.getenv("LLM_OCR", "1"),
            timeout=os.getenv("LLM_VLM_FETCH_TIMEOUT", "12"),
            img=os.getenv("LLM_VLM_MAX_IMAGE_BYTES", "8388608"),
            total=os.getenv("LLM_VLM_MAX_TOTAL_BYTES", "50331648"),
            chunk_i=os.getenv("LLM_VLM_CHUNK_MAX_IMAGES", "8"),
            chunk_b=os.getenv("LLM_VLM_CHUNK_MAX_BYTES", "12582912"),
        ),
        file=sys.stderr,
        flush=True,
    )
    print(f"[config] python={sys.executable}", file=sys.stderr, flush=True)
    print(
        f"[config] virtual_env={os.getenv('VIRTUAL_ENV', '(none)')}",
        file=sys.stderr,
        flush=True,
    )
    print(
        "[config] slang_db={enabled}, path={path}, flush_posts={posts}, flush_seconds={seconds}".format(
            enabled=os.getenv("PIPELINE_SLANG_DB", "0"),
            path=os.getenv("PIPELINE_SLANG_DB_PATH", "slang_db/slang_db.json"),
            posts=os.getenv("PIPELINE_SLANG_DB_FLUSH_POSTS", "5"),
            seconds=os.getenv("PIPELINE_SLANG_DB_FLUSH_SECONDS", "5"),
        ),
        file=sys.stderr,
        flush=True,
    )
    # ===== 아래는 보통 건드릴 필요 없음 =====
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Input not found: {INPUT_PATH}")

    # 디렉토리 생성
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 타임스탬프 기반 파일명
    # 초 단위만 쓰면 같은 초에 두 런이 시작될 때 로그/결과 파일이 충돌한다.
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    import hashlib
    _prompt_version = os.getenv("PIPELINE_PROMPT_VERSION", "2026-03-30-semantic-contract-v1").strip() or "unknown"
    _run_config_payload = {
        "llm_mode": LLM_MODE,
        "server_type": LLM_SERVER_TYPE,
        "llm_endpoint": os.getenv("LLM_ENDPOINT", ""),
        "llm_model": os.getenv("LLM_MODEL", ""),
        "parallel": _PARALLEL,
        "mcp_endpoints": os.getenv("MCP_ENDPOINTS", os.getenv("MCP_ENDPOINT", "")),
        "slang_db": os.getenv("PIPELINE_SLANG_DB", "0"),
        "reason_full_mode": os.getenv("PIPELINE_REASON_FULL_MODE", os.getenv("REASON_FULL_MODE", "1")),
        "prompt_version": _prompt_version,
    }
    _config_hash = hashlib.sha256(
        json.dumps(_run_config_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    log_path = LOG_DIR / f"expert_run_{ts}.log"
    if _CLI_ARGS.output:
        out_result_path = Path(_CLI_ARGS.output)
        out_result_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        out_result_path = OUT_DIR / f"expert_result_{ts}.json"

    _orig_out = sys.stdout
    _orig_err = sys.stderr

    for _stream_name, _stream in (("stdout", _orig_out), ("stderr", _orig_err)):
        if hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

    class _Tee:
        """stdout/stderr를 파일과 콘솔 동시 출력 + 대시보드 로그 포워딩
        
        병렬 모드:
          - 워커 스레드 출력 → 워커별 로그 파일 + 통합 로그 (콘솔 억제)
          - 메인 스레드 출력 → 콘솔 + 통합 로그 (기존 동작)
        """
        def __init__(self, console_stream, file_stream):
            self._console = console_stream  # _orig_err
            self._file = file_stream        # 통합 로그 파일
            self._monitor = None
            self._log_buf = ""  # 라인 버퍼 (줄바꿈 단위로 flush)
            self._worker_bufs = {}  # thread_id → buf (워커별 버퍼)
            if not _NO_DASHBOARD:
                try:
                    from llm_batch.monitor.event_bus import monitor as _mon
                    self._monitor = _mon
                except Exception:
                    pass

        def write(self, s):
            if not s:
                return 0
            wrote = len(s) if isinstance(s, str) else 0

            # 통합 로그 파일에는 항상 기록
            try:
                self._file.write(s)
            except Exception:
                pass

            # 병렬 모드: 메인 스레드만 콘솔 출력 (워커 + 서브스레드 모두 억제)
            _is_main = threading.get_ident() == _main_thread_id
            if _parallel_mode and not _is_main:
                # 비-메인 스레드 (워커 및 jury 서브스레드): 콘솔 억제
                worker_log = getattr(_worker_tls, 'log_file', None)
                if worker_log is not None:
                    try:
                        worker_log.write(s)
                    except Exception:
                        pass
                # 통합 로그에는 이미 기록됨, 콘솔 생략
            else:
                # 메인 스레드 또는 순차 모드: 콘솔에 출력
                try:
                    self._console.write(s)
                except Exception:
                    pass

            # 초기 import 타이밍 이슈로 monitor가 비어있을 수 있으므로 lazy attach
            if self._monitor is None and not _NO_DASHBOARD:
                try:
                    from llm_batch.monitor.event_bus import monitor as _mon
                    self._monitor = _mon
                except Exception:
                    pass

            # 대시보드 로그 포워딩 — 줄바꿈 단위로 버퍼링
            if self._monitor:
                try:
                    tid = threading.get_ident()
                    buf = self._worker_bufs.get(tid, "")
                    buf += s
                    wid = getattr(_worker_tls, 'worker_id', -1)
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        if line.strip():
                            self._monitor.add_log(line, worker_id=wid)
                    self._worker_bufs[tid] = buf
                except Exception:
                    pass
            return wrote

        def flush(self):
            try:
                self._file.flush()
            except Exception:
                pass
            worker_log = getattr(_worker_tls, 'log_file', None)
            if worker_log:
                try:
                    worker_log.flush()
                except Exception:
                    pass
            _is_main = threading.get_ident() == _main_thread_id
            if not (_parallel_mode and not _is_main):
                try:
                    self._console.flush()
                except Exception:
                    pass

        def isatty(self):
            try:
                return self._console.isatty()
            except Exception:
                return False

        @property
        def encoding(self):
            enc = getattr(self._console, "encoding", None)
            return enc or "utf-8"

        def reconfigure(self, **kwargs):
            for st in [self._console, self._file]:
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

        try:
            # 대시보드 서버 기동
            if not _NO_DASHBOARD:
                try:
                    sys.path.insert(0, str(repo_root / "src"))
                    from llm_batch.monitor.server import start_dashboard
                    from llm_batch.monitor.event_bus import monitor as _monitor
                    _dash_port = int(os.environ.get("DASHBOARD_PORT", "8080"))
                    _dash_thread = start_dashboard(port=_dash_port)
                    _dash_actual_port = int(getattr(_dash_thread, "dashboard_port", _dash_port))
                    # _Tee가 초기에 monitor import를 놓쳐도 즉시 연결되도록 재주입
                    for _tee_stream in (sys.stdout, sys.stderr):
                        try:
                            if hasattr(_tee_stream, "_monitor"):
                                setattr(_tee_stream, "_monitor", _monitor)
                        except Exception:
                            pass
                    # sys.stderr(_Tee)로 출력해 콘솔+로그 파일 모두에 남긴다.
                    print(
                        f"[expert_main] 📊 Dashboard: http://127.0.0.1:{_dash_actual_port} (bind=0.0.0.0)",
                        file=sys.stderr,
                        flush=True,
                    )
                except Exception as _e:
                    # 실패 원인도 로그 파일에 남겨 실행 중 추적 가능하게 한다.
                    print(f"[expert_main] ⚠️ 대시보드 기동 실패: {_e}", file=sys.stderr, flush=True)
                    _monitor = None
            else:
                _monitor = None

            print(f"[expert_main] 로그 저장: {log_path}", file=sys.stderr, flush=True)
            print(f"[expert_main] 결과 저장: {out_result_path}", file=sys.stderr, flush=True)
            print(f"[expert_main] LLM_MODE: {LLM_MODE}", file=sys.stderr, flush=True)
            print(f"[expert_main] 입력: {INPUT_PATH}", file=sys.stderr, flush=True)
            print(
                f"[expert_main] MCP shards: {os.getenv('MCP_ENDPOINTS', os.getenv('MCP_ENDPOINT', 'http://localhost:3333'))}",
                file=sys.stderr,
                flush=True,
            )

            # 프로젝트 src를 path에 추가
            sys.path.insert(0, str(repo_root / "src"))

            from llm_batch.agentic_pipeline import AgenticPipeline
            from llm_batch.llm.client import LLMClient
            from llm_batch.search.client import MCPClient
            from llm_batch.models import PostInput, ContentBlock
            from llm_batch.batch_context import BatchContextMemory
            from llm_batch.slang_db import SlangDBManager

            # 입력 로드
            posts = load_jsonl_posts(INPUT_PATH)
            if LIMIT:
                posts = posts[:LIMIT]

            print(f"\n{'='*70}", file=sys.stderr, flush=True)
            print(f"🤖 Agentic Pipeline (유기적 전문가 시스템)", file=sys.stderr, flush=True)
            print(f"{'='*70}", file=sys.stderr, flush=True)
            print(f"📂 입력: {INPUT_PATH} ({len(posts)}개 포스트)", file=sys.stderr, flush=True)

            # ─── 검색 서버 헬스체크 ──────────────────────────
            print(f"\n🔍 검색 서버 연결 확인 중...", file=sys.stderr, flush=True)
            _mcp_endpoint_pool = _get_mcp_endpoint_pool()
            if _can_auto_manage_local_shards():
                try:
                    _auto_up_local_shards(repo_root, len(_mcp_endpoint_pool))
                except Exception as exc:
                    print(f"[expert_main] ⚠️ shard 자동 기동 실패: {exc}", file=sys.stderr, flush=True)

            _health_failures = []
            _health_ok = {}
            _health_attempts = 6 if _can_auto_manage_local_shards() else 1
            for _attempt in range(_health_attempts):
                _health_failures = []
                _health_ok = {}
                for _idx, _endpoint in enumerate(_mcp_endpoint_pool):
                    _hc_mcp = MCPClient(endpoint=_endpoint)
                    _hc = _hc_mcp.health_check(timeout=30.0)
                    if _hc["ok"]:
                        _health_ok[_endpoint] = _hc
                    else:
                        _health_failures.append((_endpoint, _hc.get("error") or "unknown error"))
                if not _health_failures:
                    break
                if _attempt + 1 < _health_attempts:
                    print(
                        f"[expert_main] shard 초기화 대기 중... ({_attempt + 1}/{_health_attempts - 1})",
                        file=sys.stderr,
                        flush=True,
                    )
                    time.sleep(5)

            for _idx, _endpoint in enumerate(_mcp_endpoint_pool):
                _hc = _health_ok.get(_endpoint)
                if _hc:
                    print(
                        f"✅ 검색 서버 정상 [shard {_idx}] {_endpoint}: Bridge {_hc['latency_ms']:.0f}ms, Search {_hc.get('search_latency_ms', 0):.0f}ms",
                        file=sys.stderr,
                        flush=True,
                    )

            if _can_auto_manage_local_shards():
                try:
                    _memo_local_shard_status(repo_root, LOG_DIR / f"warp_shards_status_{ts}.json")
                except Exception as exc:
                    print(f"[expert_main] ⚠️ WARP shard 메모 저장 실패: {exc}", file=sys.stderr, flush=True)

            if _health_failures:
                print(f"\n{'❌'*30}", file=sys.stderr, flush=True)
                print(f"❌ 일부 검색 서버 연결 실패!", file=sys.stderr, flush=True)
                for _endpoint, _err in _health_failures:
                    print(f"   - {_endpoint} -> {_err}", file=sys.stderr, flush=True)
                print(f"", file=sys.stderr, flush=True)
                print(f"   💡 해결 방법:", file=sys.stderr, flush=True)
                print(f"      {sys.executable} tools/warp_shards.py up --count {_PARALLEL}", file=sys.stderr, flush=True)
                print(f"      docker ps  # 컨테이너 상태 확인", file=sys.stderr, flush=True)
                print(f"{'❌'*30}\n", file=sys.stderr, flush=True)
                print(f"검색 없이 계속 진행하시겠습니까? (y/N): ", end="", file=_orig_err, flush=True)
                try:
                    _ans = input().strip().lower()
                except (EOFError, KeyboardInterrupt):
                    _ans = "n"
                if _ans != "y":
                    print(f"🛑 검색 서버 미연결 — 파이프라인 중단", file=sys.stderr, flush=True)
                    sys.stdout = _orig_out
                    sys.stderr = _orig_err
                    return
                print(f"⚠️  검색 없이 진행합니다. 결과 품질이 저하될 수 있습니다.", file=sys.stderr, flush=True)

            # ─── 배치 컨텍스트 메모리 (포스트 간 지식 공유) ──
            _batch_context = BatchContextMemory(enabled=True)
            print(f"🧠 BatchContextMemory 활성화 (포스트 간 약칭/작가/캐릭터 공유)", file=sys.stderr, flush=True)
            _recent_post_index = AgenticPipeline.build_recent_post_index(posts)
            print(
                f"🪟 RecentPostIndex 구성 완료 ({len(_recent_post_index)}건, ±30분/20post)",
                file=sys.stderr,
                flush=True,
            )
            _slang_db_enabled = os.getenv("PIPELINE_SLANG_DB", "0").strip() == "1"
            _slang_db_path_raw = os.getenv("PIPELINE_SLANG_DB_PATH", "slang_db/slang_db.json").strip() or "slang_db/slang_db.json"
            _slang_db_path = Path(_slang_db_path_raw)
            if not _slang_db_path.is_absolute():
                _slang_db_path = repo_root / _slang_db_path
            _slang_db_manager = SlangDBManager(
                path=_slang_db_path,
                run_id=ts,
                enabled=_slang_db_enabled,
                flush_posts=int(os.getenv("PIPELINE_SLANG_DB_FLUSH_POSTS", "5") or 5),
                flush_seconds=int(os.getenv("PIPELINE_SLANG_DB_FLUSH_SECONDS", "5") or 5),
                log_fn=lambda msg: print(msg, file=sys.stderr, flush=True),
            )
            if _slang_db_enabled:
                print(f"🗂️ Slang DB 저장 활성화: {_slang_db_path}", file=sys.stderr, flush=True)

            # ─── 워커 팩토리 ──────────────────────────────
            def _create_pipeline(worker_id: int = 0) -> AgenticPipeline:
                """워커별 독립 LLMClient/MCPClient/Pipeline 인스턴스 생성"""
                _llm = LLMClient()
                _endpoint = _mcp_endpoint_pool[worker_id % len(_mcp_endpoint_pool)]
                _mcp = MCPClient(endpoint=_endpoint)
                _pipe = AgenticPipeline(
                    llm=_llm,
                    mcp=_mcp,
                    output_dir=OUT_DIR,
                    max_iterations=15,
                    worker_id=worker_id,
                    parallel_count=_PARALLEL,
                    batch_context=_batch_context,
                    recent_post_index=_recent_post_index,
                )
                print(f"[expert_main] worker W{worker_id} -> MCP shard {_endpoint}", file=sys.stderr, flush=True)
                return _pipe

            # ─── 단일 포스트 처리 함수 ────────────────────
            def _process_one(
                post, index: int, total: int,
                pipeline: AgenticPipeline,
                worker_id: int,
            ) -> Dict[str, Any]:
                """한 포스트를 처리하고 full_result dict 반환"""
                w_tag = f"W{worker_id}" if _PARALLEL > 1 else ""
                
                # 원본 데이터 추출
                content_texts = []
                for block in post.content_blocks:
                    if hasattr(block, "text") and block.text:
                        content_texts.append(block.text)
                    elif isinstance(block, str):
                        content_texts.append(block)
                
                comment_texts = []
                for c in (post.comments or []):
                    if isinstance(c, dict):
                        comment_texts.append(c.get("content", c.get("text", "")))
                    elif hasattr(c, "content"):
                        comment_texts.append(c.content)
                    else:
                        comment_texts.append(str(c))
                
                # 📊 대시보드: post_start — 배너 출력 전에 emit하여
                # 인메모리 포스트별 로그에 배너 라인도 포함되도록 함
                _post_start_t = time.time()
                if _monitor:
                    _monitor.emit("post_start", {
                        "index": index,
                        "total": total,
                        "post_id": post.post_id,
                        "title": post.title,
                        "worker_id": worker_id,
                    })

                # Pretty print post info (스레드 안전 출력)
                with _print_lock:
                    print(f"\n{'='*70}", file=sys.stderr, flush=True)
                    print(f"🤖 [{w_tag}][{index}/{total}] Agentic Pipeline 시작", file=sys.stderr, flush=True)
                    print(f"{'='*70}", file=sys.stderr, flush=True)
                    print(f"📌 Post ID: {post.post_id}", file=sys.stderr, flush=True)
                    print(f"📝 제목: {post.title}", file=sys.stderr, flush=True)
                    print(f"👤 작성자: {post.author}", file=sys.stderr, flush=True)
                    print(f"🔗 URL: {post.url}", file=sys.stderr, flush=True)
                    print(f"📅 작성일: {post.created_at}", file=sys.stderr, flush=True)
                    print(f"\n📄 내용:", file=sys.stderr, flush=True)
                    for j, line in enumerate(content_texts[:10], 1):
                        print(f"   {j}. {line[:100]}{'...' if len(line) > 100 else ''}", file=sys.stderr, flush=True)
                    if len(content_texts) > 10:
                        print(f"   ... ({len(content_texts) - 10}줄 더)", file=sys.stderr, flush=True)
                    print(f"\n💬 댓글 ({len(comment_texts)}개):", file=sys.stderr, flush=True)
                    for j, cmt in enumerate(comment_texts[:5], 1):
                        print(f"   {j}. {cmt[:80]}{'...' if len(cmt) > 80 else ''}", file=sys.stderr, flush=True)
                    if len(comment_texts) > 5:
                        print(f"   ... ({len(comment_texts) - 5}개 더)", file=sys.stderr, flush=True)
                    print(f"{'─'*70}", file=sys.stderr, flush=True)

                result = pipeline.process_post(post)
                result_dict = result.model_dump() if hasattr(result, "model_dump") else dict(result)
                
                full_result = {
                    "post_id": post.post_id,
                    "title": post.title,
                    "author": post.author,
                    "created_at": post.created_at,
                    "url": post.url,
                    "content": content_texts,
                    "comments": comment_texts,
                    "analysis_result": result_dict,
                    "run_meta": {
                        "run_id": ts,
                        "model": os.getenv("LLM_MODEL", ""),
                        "llm_mode": LLM_MODE,
                        "prompt_version": _prompt_version,
                        "config_hash": _config_hash,
                    },
                }

                # 결과 요약 (스레드 안전 출력)
                with _print_lock:
                    print(f"\n📋 [{w_tag}] Result (post_id={post.post_id}):", file=sys.stderr, flush=True)
                    identity = result_dict.get("identity", {})
                    print(f"   is_relevant: {identity.get('is_relevant')}", file=sys.stderr, flush=True)
                    novel_id = identity.get("novel_identity")
                    if novel_id:
                        print(f"   title: {novel_id.get('official_title')}", file=sys.stderr, flush=True)
                        print(f"   confidence: {novel_id.get('confidence')}", file=sys.stderr, flush=True)
                    print(f"   reason: {identity.get('reason') or ''}", file=sys.stderr, flush=True)

                # 📊 대시보드: post_complete
                if _monitor:
                    _post_elapsed = time.time() - _post_start_t
                    _identity = result_dict.get("identity", {})
                    _novel_id = _identity.get("novel_identity") or {}
                    _ctx_token = {}
                    try:
                        _last_ctx = pipeline.orchestrator._last_ctx
                        if _last_ctx and hasattr(_last_ctx, 'token_usage'):
                            _ctx_token = dict(_last_ctx.token_usage)
                    except Exception:
                        pass
                    _monitor.emit("post_complete", {
                        "post_id": post.post_id,
                        "title": post.title,
                        "author": post.author,
                        "created_at": post.created_at,
                        "url": post.url,
                        "content": content_texts[:20],
                        "comments": comment_texts[:30],
                        "is_relevant": _identity.get("is_relevant"),
                        "official_title": _novel_id.get("official_title"),
                        "confidence": _novel_id.get("confidence"),
                        "discussion_type": _identity.get("discussion_type"),
                        "topicality": _identity.get("topicality"),
                        "subtype": _identity.get("subtype"),
                        "work_resolution": _identity.get("work_resolution"),
                        "anchor_type": _identity.get("anchor_type"),
                        "anchor_strength": _identity.get("anchor_strength"),
                        "context_sources": _identity.get("context_sources"),
                        "consistency_flags": _identity.get("consistency_flags"),
                        "reason": _identity.get("reason", ""),
                        "reason_lines": _identity.get("reason_lines"),
                        "slang_insight": _identity.get("slang_insight"),
                        "analysis_notes": (result_dict.get("analysis") or {}).get("notes"),
                        "analysis": result_dict.get("analysis"),
                        "novel_identity": _novel_id,
                        "primary_work": _identity.get("primary_work"),
                        "title_candidates": _identity.get("title_candidates"),
                        "mentioned_works": _identity.get("mentioned_works"),
                        "comparison_target": _identity.get("comparison_target"),
                        "recommendation_candidates": _identity.get("recommendation_candidates"),
                        "relevance_scope": _identity.get("relevance_scope"),
                        "elapsed": round(_post_elapsed, 1),
                        "token_usage": _ctx_token,
                        "worker_id": worker_id,
                    })
                    _monitor.emit("search_stats", {
                        "hits": getattr(pipeline, '_search_cache_hits', 0),
                        "misses": getattr(pipeline, '_search_cache_misses', 0),
                    })

                return full_result

            # ─── 메인 처리 루프 ───────────────────────────
            results = []
            total_start = time.time()

            # 📊 대시보드: batch_start
            if _monitor:
                _monitor.emit("batch_start", {
                    "total": len(posts),
                    "input_file": str(INPUT_PATH.name),
                    "output_file": str(out_result_path.name),
                    "parallel_count": _PARALLEL,
                })

            # ─── 병렬 모드: 컴팩트 CLI 진행 표시 ───────────
            def _cli_progress(msg: str) -> None:
                """병렬 모드에서 콘솔에 간결한 진행 상황만 표시"""
                with _print_lock:
                    _orig_err.write(msg + "\n")
                    _orig_err.flush()

            if _PARALLEL <= 1:
                # ===== 순차 모드 (기존 동작 유지) =====
                pipeline = _create_pipeline(worker_id=0)
                try:
                    for i, post in enumerate(posts, 1):
                        if _shutdown_event.is_set():
                            break
                        full_result = _process_one(post, i, len(posts), pipeline, worker_id=0)
                        results.append(full_result)
                        _slang_db_manager.record_result(full_result)
                        # 점진적 저장
                        out_result_path.write_text(
                            json.dumps(results, ensure_ascii=False, indent=2),
                            encoding="utf-8"
                        )
                except KeyboardInterrupt:
                    _shutdown_event.set()
                    print("\n⚠️  Ctrl+C 감지 — 종료 중...", file=sys.stderr, flush=True)
                    if results:
                        out_result_path.write_text(
                            json.dumps(results, ensure_ascii=False, indent=2),
                            encoding="utf-8"
                        )
                        _slang_db_manager.finalize()
                        print(f"💾 중단 시점까지 {len(results)}건 저장됨: {out_result_path}", file=sys.stderr, flush=True)
                    sys.stdout = _orig_out
                    sys.stderr = _orig_err
                    print("\n🛑 사용자 중단 (Ctrl+C) — 프로세스 종료", file=sys.stderr, flush=True)
                    return
            else:
                # ===== 병렬 모드 =====
                global _parallel_mode
                _parallel_mode = True
                
                print(f"\n🚀 병렬 모드 활성화: {_PARALLEL} 워커", file=sys.stderr, flush=True)
                
                # 워커별 로그 파일 생성
                _worker_log_files = []
                for wid in range(_PARALLEL):
                    wlog_path = LOG_DIR / f"expert_run_{ts}_W{wid}.log"
                    wlog_f = wlog_path.open("w", encoding="utf-8-sig", buffering=1, newline="")
                    _worker_log_files.append(wlog_f)
                    print(f"   📝 W{wid} 로그: {wlog_path}", file=sys.stderr, flush=True)
                
                print(f"   📝 통합 로그: {log_path}", file=sys.stderr, flush=True)
                print(f"   ℹ️  CLI에는 진행 요약만 표시됩니다. 상세 로그는 워커별 파일을 참조하세요.", file=sys.stderr, flush=True)
                print(f"{'─'*70}", file=sys.stderr, flush=True)
                
                # 워커별 파이프라인 미리 생성
                pipelines = [_create_pipeline(worker_id=wid) for wid in range(_PARALLEL)]
                
                def _parallel_process_one(post, global_idx, total, pipeline, worker_id):
                    """병렬 모드 래퍼: 워커별 로그 파일을 thread-local에 설정"""
                    if _shutdown_event.is_set():
                        raise SystemExit("shutdown")
                    _worker_tls.log_file = _worker_log_files[worker_id]
                    _worker_tls.worker_id = worker_id
                    
                    # CLI에 간결한 시작 알림
                    _cli_progress(f"  🔄 [W{worker_id}][{global_idx}/{total}] 시작: #{post.post_id} — {(post.title or '')[:40]}")
                    
                    try:
                        result = _process_one(post, global_idx, total, pipeline, worker_id)
                        
                        # CLI에 간결한 완료 알림
                        identity = result.get("analysis_result", {}).get("identity", {})
                        is_rel = identity.get("is_relevant")
                        novel = (identity.get("novel_identity") or {}).get("official_title", "")
                        tag = "✅" if is_rel else "⛔"
                        info = f" → {novel}" if novel else ""
                        _cli_progress(f"  {tag} [W{worker_id}][{global_idx}/{total}] 완료: #{post.post_id}{info}")
                        return result
                    except Exception as e:
                        _cli_progress(f"  ❌ [W{worker_id}][{global_idx}/{total}] 오류: #{post.post_id} — {e}")
                        raise
                
                # 슬라이딩 윈도우 병렬 처리
                # — 하나 끝나면 즉시 다음 포스트 투입 (빈 워커 재활용)
                _worker_pool = Queue()  # 사용 가능한 워커 ID 큐
                for wid in range(_PARALLEL):
                    _worker_pool.put(wid)

                # 결과를 순서대로 저장하기 위한 dict
                _pending_results: Dict[int, Any] = {}
                _next_save_idx = 1  # 다음으로 results에 추가할 global_idx

                def _flush_ordered():
                    """순서가 맞는 결과를 results에 flush하고 점진 저장"""
                    nonlocal _next_save_idx
                    flushed = False
                    while _next_save_idx in _pending_results:
                        _result_item = _pending_results.pop(_next_save_idx)
                        results.append(_result_item)
                        _slang_db_manager.record_result(_result_item)
                        _next_save_idx += 1
                        flushed = True
                    if flushed:
                        with _results_lock:
                            out_result_path.write_text(
                                json.dumps(results, ensure_ascii=False, indent=2),
                                encoding="utf-8"
                            )

                _executor_ref = None  # Ctrl+C에서 접근용

                def _collect_done(futures_dict):
                    """완료된 future들을 수거하고 워커 반환"""
                    done_list = [f for f in futures_dict if f.done()]
                    for fut in done_list:
                        gidx, pid, wid_done = futures_dict.pop(fut)
                        try:
                            full_result = fut.result()
                            _pending_results[gidx] = full_result
                        except (SystemExit, KeyboardInterrupt):
                            pass  # 셧다운 중 — 무시
                        except Exception as e:
                            _pending_results[gidx] = {
                                "post_id": pid,
                                "title": "",
                                "error": str(e),
                                "analysis_result": {
                                    "identity": {"is_relevant": False, "reason": f"처리 오류: {e}"},
                                },
                            }
                        _worker_pool.put(wid_done)
                    if done_list:
                        _flush_ordered()

                try:
                    executor = ThreadPoolExecutor(max_workers=_PARALLEL)
                    _executor_ref = executor
                    futures = {}

                    for i, post in enumerate(posts, 1):
                        if _shutdown_event.is_set():
                            break

                        # 빈 워커가 생길 때까지 대기 (완료된 future 수거)
                        while not _shutdown_event.is_set():
                            _collect_done(futures)
                            try:
                                wid = _worker_pool.get(timeout=0.2)
                                break
                            except Empty:
                                continue
                        else:
                            break  # shutdown

                        fut = executor.submit(
                            _parallel_process_one,
                            post, i, len(posts),
                            pipelines[wid], worker_id=wid,
                        )
                        futures[fut] = (i, post.post_id, wid)

                    # 남은 future 전부 수거
                    while futures and not _shutdown_event.is_set():
                        _collect_done(futures)
                        if futures:
                            time.sleep(0.2)

                    # 혹시 남은 것 마저 수거
                    _collect_done(futures)
                    executor.shutdown(wait=False)

                except KeyboardInterrupt:
                    _cli_progress("\n⚠️  Ctrl+C 감지 — 종료 중...")
                    _shutdown_event.set()
                    # 진행 중인 future 취소
                    for fut in list(futures.keys()):
                        fut.cancel()
                    _collect_done(futures)
                    executor.shutdown(wait=False)

                finally:
                    # 워커 로그 파일 닫기
                    for wf in _worker_log_files:
                        try:
                            wf.close()
                        except Exception:
                            pass
                    _parallel_mode = False

                # 셧다운 시 결과 저장 후 즉시 종료 (httpx 스레드 강제 종료)
                if _shutdown_event.is_set():
                    if results:
                        with _results_lock:
                            out_result_path.write_text(
                                json.dumps(results, ensure_ascii=False, indent=2),
                                encoding="utf-8"
                            )
                        _slang_db_manager.finalize()
                        _cli_progress(f"💾 중단 시점까지 {len(results)}건 저장됨: {out_result_path}")
                    sys.stdout = _orig_out
                    sys.stderr = _orig_err
                    print("\n🛑 사용자 중단 (Ctrl+C) — 프로세스 종료", file=sys.stderr, flush=True)
                    return

            # 🔥 배치 검색 캐시 통계 출력
            if _PARALLEL <= 1:
                _all_pipelines = [pipeline]
            else:
                _all_pipelines = pipelines
            cache_hits = sum(getattr(p, '_search_cache_hits', 0) for p in _all_pipelines)
            cache_misses = sum(getattr(p, '_search_cache_misses', 0) for p in _all_pipelines)
            cache_total = cache_hits + cache_misses
            cache_entries = sum(len(getattr(p, '_search_cache', {})) for p in _all_pipelines)
            if cache_total > 0:
                print(f"\n{'='*70}", file=sys.stderr, flush=True)
                print(f"🔎 배치 검색 캐시 통계 ({'워커별 독립 캐시' if _PARALLEL > 1 else '단일 캐시'}):", file=sys.stderr, flush=True)
                print(f"   총 검색 요청: {cache_total}건", file=sys.stderr, flush=True)
                print(f"   캐시 히트:    {cache_hits}건 ({cache_hits/cache_total*100:.1f}%)", file=sys.stderr, flush=True)
                print(f"   실제 검색:    {cache_misses}건 ({cache_misses/cache_total*100:.1f}%)", file=sys.stderr, flush=True)
                print(f"   캐시 엔트리:  {cache_entries}개", file=sys.stderr, flush=True)
                if _PARALLEL > 1:
                    print(f"   워커 수:      {_PARALLEL}개 (독립 캐시)", file=sys.stderr, flush=True)
                print(f"{'='*70}", file=sys.stderr, flush=True)
            
            # 전체 완료
            _slang_db_manager.finalize()
            total_elapsed = time.time() - total_start
            print(f"\n{'='*70}", file=sys.stderr, flush=True)
            print(f"✅ 처리 완료!", file=sys.stderr, flush=True)
            print(f"{'='*70}", file=sys.stderr, flush=True)

            # 요약 통계
            relevant = sum(
                1 for r in results 
                if r.get("analysis_result", {}).get("identity", {}).get("is_relevant")
            )
            identified = sum(
                1 for r in results
                if (r.get("analysis_result", {}).get("identity", {}).get("novel_identity") or {}).get("official_title")
            )

            print(f"\n📊 Summary:", file=sys.stderr, flush=True)
            print(f"   Total Posts: {len(results)}", file=sys.stderr, flush=True)
            print(f"   Relevant: {relevant}", file=sys.stderr, flush=True)
            print(f"   Identified (with title): {identified}", file=sys.stderr, flush=True)
            print(f"   Total Time: {total_elapsed:.1f}s", file=sys.stderr, flush=True)
            if len(results) > 0:
                print(f"   Avg Time/Post: {total_elapsed/len(results):.1f}s", file=sys.stderr, flush=True)
            
            # 전체 배치 토큰 통계는 각 포스트 처리 중 출력됨
            # 여기서는 요약만 표시
            print(f"\n💡 참고: 각 전문가별 토큰 사용량은 위 로그 참조", file=sys.stderr, flush=True)

            print(f"\n💾 결과 파일:", file=sys.stderr, flush=True)
            print(f"   - 통합 로그: {log_path}", file=sys.stderr, flush=True)
            if _PARALLEL > 1:
                for wid in range(_PARALLEL):
                    wlog_p = LOG_DIR / f"expert_run_{ts}_W{wid}.log"
                    print(f"   - W{wid} 로그: {wlog_p}", file=sys.stderr, flush=True)
            print(f"   - 결과: {out_result_path}", file=sys.stderr, flush=True)

            # 📊 대시보드: batch_complete
            if _monitor:
                _monitor.emit("batch_complete", {
                    "total": len(results),
                    "relevant": relevant,
                    "identified": identified,
                    "elapsed": round(total_elapsed, 1),
                })

        finally:
            sys.stdout = _orig_out
            sys.stderr = _orig_err


def load_jsonl_posts(path: Path) -> List:
    """JSONL 파일에서 포스트만 로드 (댓글 제외)"""
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    from llm_batch.models import PostInput, ContentBlock

    posts = []
    post_map: Dict[int, Dict[str, Any]] = {}
    comments_map: Dict[int, List[Dict[str, Any]]] = {}

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue

            # 댓글인지 포스트인지 구분
            if "comment_id" in item:
                # 댓글
                pid = item.get("post_id")
                if pid:
                    if pid not in comments_map:
                        comments_map[pid] = []
                    comments_map[pid].append(item)
            elif "post_id" in item:
                # 포스트
                pid = item["post_id"]
                post_map[pid] = item

    # PostInput으로 변환
    for pid, data in post_map.items():
        content_blocks = []
        for block in data.get("content_blocks", []):
            if isinstance(block, dict):
                content_blocks.append(ContentBlock(
                    type=block.get("type", "text"),
                    text=block.get("text"),
                    url=block.get("url"),
                ))
            else:
                content_blocks.append(ContentBlock(type="text", text=str(block)))

        # 댓글 연결
        comments = comments_map.get(pid, [])

        posts.append(PostInput(
            post_id=pid,
            title=data.get("title", ""),
            author=data.get("author", ""),
            content_blocks=content_blocks,
            gallery_id=data.get("gallery_id", ""),
            url=data.get("url", ""),
            created_at=data.get("created_at", ""),
            comments=comments,
        ))

    return posts


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        _shutdown_event.set()
        print("\n🛑 사용자 중단 (Ctrl+C)", file=sys.stderr, flush=True)
        # 결과가 있으면 저장
        raise SystemExit(1)
