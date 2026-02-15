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
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Agentic Pipeline (유기적 전문가 시스템)",
        add_help=False,  # 기존 sys.argv[1] 호환성 유지
    )
    parser.add_argument("input", nargs="?", default=None, help="입력 JSONL 파일 경로")
    parser.add_argument("--parallel", "-p", type=int, default=1, help="병렬 처리 워커 수 (기본: 1)")
    parser.add_argument("--no-dashboard", action="store_true", help="대시보드 비활성화")
    # 알 수 없는 인자 무시 (기존 호환성)
    args, _ = parser.parse_known_args()
    return args

_CLI_ARGS = _parse_args()
_PARALLEL = max(1, _CLI_ARGS.parallel)

# ─── 스레드 안전 로그 출력 ──────────────────────────────
_print_lock = threading.Lock()
_results_lock = threading.Lock()

# ─── 병렬 모드: 워커별 로그 파일 라우팅 ─────────────────
_worker_tls = threading.local()  # .log_file, .worker_id 저장
_parallel_mode = False  # _Tee에서 참조
_shutdown_event = threading.Event()  # Ctrl+C 종료 시그널


def _set_env(k: str, v: str) -> None:
    """환경변수 강제 설정"""
    os.environ[k] = v


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
    # "remote": 원격 llama-server (https://llama.kimjang.me/)
    LLM_MODE = "remote"  # "local" or "remote"

    # MCP(SearchXNG)
    _set_env("MCP_ENDPOINT", "http://localhost:3333")

    # ===== LLM 공통 설정 (main.py와 동일) =====
    _set_env("LLM_N_CTX", "65536")
    _set_env("LLM_MAX_TOKENS", "16384")
    _set_env("LLM_JSON_GRAMMAR", "1")
    _set_env("LLM_PROGRESS_EVERY", "5")
    _set_env("LLM_MAX_SEARCH_ROUNDS", "2")
    _set_env("LLM_MAX_SEARCH_QUERIES", "2")
    _set_env("LLM_FLASH_ATTN", "1")
    _set_env("LLM_CACHE_TYPE_K", "q8_0")
    _set_env("LLM_CACHE_TYPE_V", "q8_0")
    _set_env("LLM_PRINT_TIMINGS", "1")
    _set_env("MCP_TOP_K_RESULTS", "10")  # 검색 결과 상위 10개 사용
    _set_env("MCP_DEFAULT_NUM_RESULTS", "15")  # SearXNG에서 15개 요청
    _set_env("MCP_MAX_CONTENT_CHARS", "400")
    
    # ===== 스트리밍 및 디버그 설정 (main.py와 동일) =====
    _set_env("LLM_DEBUG_DUMP_MESSAGES", "0")
    _set_env("LLM_DEBUG_DUMP_MAX_CHARS", "0")
    _set_env("LLM_STREAM", "1")
    
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
        # ===== Remote: llama-server (https://llama.kimjang.me/) =====
        _set_env("LLM_BACKEND", "http")
        _set_env("LLM_ENDPOINT", "http://a100:10000/")
        #_set_env("LLM_ENDPOINT", "https://llama.kimjang.me")
        #_set_env("LLM_ENDPOINT", "http://127.0.0.1:8080/")
        _set_env("LLM_MODEL", "unsloth/GLM-4.7-Flash-GGUF:IQ3_XXS")
    else:
        raise ValueError(f"Unknown LLM_MODE: {LLM_MODE}. Use 'local' or 'remote'.")

    # ===== 아래는 보통 건드릴 필요 없음 =====
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Input not found: {INPUT_PATH}")

    # 디렉토리 생성
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 타임스탬프 기반 파일명
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"expert_run_{ts}.log"
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

            # 병렬 모드: 워커 스레드인지 확인
            worker_log = getattr(_worker_tls, 'log_file', None)
            if _parallel_mode and worker_log is not None:
                # 워커 스레드: 워커별 로그 파일에만 기록 (콘솔 억제)
                try:
                    worker_log.write(s)
                except Exception:
                    pass
            else:
                # 메인 스레드 또는 순차 모드: 콘솔에 출력
                try:
                    self._console.write(s)
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
            if not (_parallel_mode and worker_log is not None):
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
                    start_dashboard(port=_dash_port)
                    print(f"[expert_main] 📊 Dashboard: http://0.0.0.0:{_dash_port}", file=_orig_err, flush=True)
                except Exception as _e:
                    print(f"[expert_main] ⚠️ 대시보드 기동 실패: {_e}", file=_orig_err, flush=True)
                    _monitor = None
            else:
                _monitor = None

            print(f"[expert_main] 로그 저장: {log_path}", file=sys.stderr, flush=True)
            print(f"[expert_main] 결과 저장: {out_result_path}", file=sys.stderr, flush=True)
            print(f"[expert_main] LLM_MODE: {LLM_MODE}", file=sys.stderr, flush=True)
            print(f"[expert_main] 입력: {INPUT_PATH}", file=sys.stderr, flush=True)

            # 프로젝트 src를 path에 추가
            sys.path.insert(0, str(repo_root / "src"))

            from llm_batch.agentic_pipeline import AgenticPipeline
            from llm_batch.llm.client import LLMClient
            from llm_batch.search.client import MCPClient
            from llm_batch.models import PostInput, ContentBlock

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
            _hc_mcp = MCPClient(endpoint=os.environ.get("MCP_ENDPOINT", "http://localhost:3333"))
            _hc = _hc_mcp.health_check(timeout=10.0)
            if _hc["ok"]:
                print(f"✅ 검색 서버 정상: Bridge {_hc['latency_ms']:.0f}ms, Search {_hc.get('search_latency_ms', 0):.0f}ms", file=sys.stderr, flush=True)
            else:
                print(f"\n{'❌'*30}", file=sys.stderr, flush=True)
                print(f"❌ 검색 서버 연결 실패!", file=sys.stderr, flush=True)
                print(f"   오류: {_hc['error']}", file=sys.stderr, flush=True)
                print(f"   엔드포인트: {_hc_mcp.endpoint}", file=sys.stderr, flush=True)
                print(f"", file=sys.stderr, flush=True)
                print(f"   💡 해결 방법:", file=sys.stderr, flush=True)
                print(f"      docker compose up -d", file=sys.stderr, flush=True)
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

            # ─── 워커 팩토리 ──────────────────────────────
            def _create_pipeline(worker_id: int = 0) -> AgenticPipeline:
                """워커별 독립 LLMClient/MCPClient/Pipeline 인스턴스 생성"""
                _llm = LLMClient()
                _mcp = MCPClient(endpoint=os.environ.get("MCP_ENDPOINT", "http://localhost:3333"))
                _pipe = AgenticPipeline(
                    llm=_llm,
                    mcp=_mcp,
                    output_dir=OUT_DIR,
                    max_iterations=15,
                    worker_id=worker_id,
                    parallel_count=_PARALLEL,
                )
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

                # 📊 대시보드: post_start
                _post_start_t = time.time()
                if _monitor:
                    _monitor.emit("post_start", {
                        "index": index,
                        "total": total,
                        "post_id": post.post_id,
                        "title": post.title,
                        "worker_id": worker_id,
                    })

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
                        "reason": _identity.get("reason", ""),
                        "slang_insight": _identity.get("slang_insight"),
                        "analysis": result_dict.get("analysis"),
                        "novel_identity": _novel_id,
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
                        results.append(_pending_results.pop(_next_save_idx))
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
