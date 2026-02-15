"""
Monitor Dashboard Server — FastAPI + SSE 기반 웹 모니터링 대시보드

별도 스레드에서 uvicorn 으로 실행되며, expert_main.py 프로세스와 함께 동작합니다.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .event_bus import monitor

# ─── FastAPI 앱 ────────────────────────────────────────────

app = FastAPI(title="Expert Pipeline Monitor", docs_url=None, redoc_url=None)

# 프로젝트 루트 (expert_main.py 위치)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_OUT_DIR = _REPO_ROOT / "out"
_LOG_DIR = _REPO_ROOT / "logs"
_STATIC_DIR = Path(__file__).resolve().parent / "static"

# ─── REST API ──────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def index():
    """대시보드 메인 페이지"""
    html_file = _STATIC_DIR / "index.html"
    if html_file.exists():
        return HTMLResponse(html_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Dashboard index.html not found</h1>", status_code=404)


@app.get("/api/status")
async def api_status():
    """현재 배치 실행 상태"""
    return JSONResponse(monitor.get_status())


@app.get("/api/results")
async def api_results():
    """현재 실행의 포스트별 결과 요약"""
    return JSONResponse(monitor.get_results())


@app.get("/api/logs")
async def api_logs(
    n: int = Query(200, ge=1, le=2000),
    worker: int = Query(-1, ge=-1, le=64),
):
    """최근 로그 n줄 (worker=-1: 전체, 0+: 워커별)"""
    return JSONResponse(monitor.get_logs(n, worker_id=worker))


# ─── 과거 실행 이력 ──────────────────────────────────────


_TS_RE = re.compile(r"(\d{8}_\d{6})")


def _parse_run_ts(filename: str) -> Optional[str]:
    """파일명에서 타임스탬프 추출 → 사람이 읽기 쉬운 형태"""
    m = _TS_RE.search(filename)
    if not m:
        return None
    raw = m.group(1)
    try:
        dt = datetime.strptime(raw, "%Y%m%d_%H%M%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return raw


@app.get("/api/runs")
async def api_runs():
    """과거 실행 이력 목록 (out/ 디렉토리 기준)"""
    if not _OUT_DIR.exists():
        return JSONResponse([])

    runs: List[Dict[str, Any]] = []
    for f in sorted(_OUT_DIR.glob("expert_result_*.json"), reverse=True):
        stat = f.stat()
        # 포스트 개수 빠르게 읽기 (JSON 배열 최상위만)
        post_count = 0
        try:
            raw = f.read_text(encoding="utf-8")[:200]
            # 실제 파싱 대신 빠르게 배열 추정
            if raw.strip().startswith("["):
                # "post_id" 키 개수로 대략 추정하면 느릴 수 있으므로
                # 전체 파일을 읽어서 파싱
                data = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    post_count = len(data)
        except Exception:
            pass

        # 매칭되는 로그 파일 탐색
        ts_match = _TS_RE.search(f.name)
        log_name = None
        if ts_match:
            log_candidate = _LOG_DIR / f"expert_run_{ts_match.group(1)}.log"
            if log_candidate.exists():
                log_name = log_candidate.name

        runs.append({
            "filename": f.name,
            "timestamp": _parse_run_ts(f.name),
            "size_kb": round(stat.st_size / 1024, 1),
            "post_count": post_count,
            "log_file": log_name,
        })

    return JSONResponse(runs)


@app.get("/api/runs/{filename}")
async def api_run_detail(filename: str):
    """특정 과거 결과 JSON 반환"""
    # path traversal 방지
    if ".." in filename or "/" in filename or "\\" in filename:
        return JSONResponse({"error": "invalid filename"}, status_code=400)

    filepath = _OUT_DIR / filename
    if not filepath.exists() or not filepath.name.startswith("expert_result_"):
        return JSONResponse({"error": "not found"}, status_code=404)

    try:
        data = json.loads(filepath.read_text(encoding="utf-8"))
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/logs/{filename}")
async def api_log_detail(filename: str, tail: int = Query(300, ge=1, le=5000)):
    """특정 로그 파일의 마지막 n줄"""
    if ".." in filename or "/" in filename or "\\" in filename:
        return JSONResponse({"error": "invalid filename"}, status_code=400)

    filepath = _LOG_DIR / filename
    if not filepath.exists() or not filepath.name.startswith("expert_run_"):
        return JSONResponse({"error": "not found"}, status_code=404)

    try:
        lines = filepath.read_text(encoding="utf-8-sig").splitlines()
        return JSONResponse(lines[-tail:])
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── SSE 스트림 ────────────────────────────────────────────


@app.get("/sse")
async def sse_stream():
    """Server-Sent Events 스트림"""
    queue = monitor.subscribe()

    async def event_generator():
        try:
            # 브라우저 재연결 간격 안내 (2초)
            yield "retry: 2000\n\n"
            # 연결 즉시 현재 상태 전송
            status = monitor.get_status()
            yield f"event: status\ndata: {json.dumps(status, ensure_ascii=False)}\n\n"
            # 현재까지의 결과도 전송 (재연결 시 누락 복구)
            results = monitor.get_results()
            if results:
                yield f"event: restore\ndata: {json.dumps(results, ensure_ascii=False, default=str)}\n\n"

            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=25)
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    # keepalive — 연결 유지 확인
                    yield ": heartbeat\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            monitor.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


# ─── 서버 기동 헬퍼 ────────────────────────────────────────


def start_dashboard(host: str = "0.0.0.0", port: int = 0) -> threading.Thread:
    """
    별도 데몬 스레드에서 대시보드 서버를 기동합니다.
    expert_main.py 에서 호출합니다.
    
    Returns:
        기동된 Thread 객체
    """
    if port == 0:
        port = int(os.environ.get("DASHBOARD_PORT", "8080"))

    def _run():
        import uvicorn
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="warning",  # uvicorn 자체 로그는 최소화
            access_log=False,
        )

    t = threading.Thread(target=_run, daemon=True, name="dashboard")
    t.start()
    return t
