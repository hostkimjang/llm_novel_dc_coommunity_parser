"""
Monitor Dashboard Server — FastAPI + SSE 기반 웹 모니터링 대시보드

별도 스레드에서 uvicorn 으로 실행되며, expert_main.py 프로세스와 함께 동작합니다.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import socket
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
async def api_results(
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    order: str = Query("desc", pattern="^(asc|desc)$"),
):
    """현재 실행의 포스트별 결과 요약 (페이지 단위)"""
    payload = monitor.get_results(offset=offset, limit=limit, order=order)
    items = payload.get("items") or []

    if items and any(_summary_needs_identity_enrichment(item) for item in items):
        for path in _candidate_result_paths():
            if not path.exists():
                continue
            try:
                raw_items = _load_result_file(path)
            except Exception:
                continue
            by_post_id = {item.get("post_id"): item for item in raw_items}
            enriched_items = []
            changed = False
            for summary in items:
                raw_item = by_post_id.get(summary.get("post_id"))
                if raw_item is not None and _summary_needs_identity_enrichment(summary):
                    enriched_items.append(_enrich_summary_from_result(summary, raw_item))
                    changed = True
                else:
                    enriched_items.append(summary)
            if changed:
                payload["items"] = enriched_items
                break

    return JSONResponse(payload)


@app.get("/api/results/{post_id}")
async def api_result_detail(post_id: int):
    """현재 실행 결과에서 특정 post_id의 상세 정보를 반환"""
    summary = monitor.get_result_summary(post_id)

    for path in _candidate_result_paths():
        if not path.exists():
            continue
        item = _find_post_in_result_file(path, post_id)
        if item is not None:
            return JSONResponse(_to_live_detail(item, summary=summary))

    if summary:
        return JSONResponse(summary)
    return JSONResponse({"error": "not found"}, status_code=404)


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


def _load_result_file(filepath: Path) -> List[Dict[str, Any]]:
    data = json.loads(filepath.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("top-level JSON must be an array")
    return data


def _find_post_in_result_file(filepath: Path, post_id: int) -> Optional[Dict[str, Any]]:
    try:
        data = _load_result_file(filepath)
    except Exception:
        return None

    for item in data:
        if item.get("post_id") == post_id:
            return item
    return None


def _candidate_result_paths() -> List[Path]:
    candidate_paths: List[Path] = []
    status = monitor.get_status()
    output_name = status.get("output_file")
    if output_name:
        candidate_paths.append(_OUT_DIR / output_name)
    if _OUT_DIR.exists():
        for path in sorted(_OUT_DIR.glob("expert_result_*.json"), reverse=True):
            if path not in candidate_paths:
                candidate_paths.append(path)
            if len(candidate_paths) >= 4:
                break
    return candidate_paths


def _has_text(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _summary_needs_identity_enrichment(item: Dict[str, Any]) -> bool:
    missing_structure = not any(item.get(key) for key in ("topicality", "subtype", "work_resolution"))
    missing_reason = not (
        _has_text(item.get("reason"))
        or _has_text(item.get("reason_lines"))
        or _has_text(item.get("analysis_notes"))
    )
    return missing_structure or missing_reason


def _enrich_summary_from_result(summary: Dict[str, Any], item: Dict[str, Any]) -> Dict[str, Any]:
    identity = (item.get("analysis_result") or {}).get("identity") or {}
    novel = identity.get("novel_identity") or {}
    enriched = dict(summary)
    enriched.update({
        "is_relevant": identity.get("is_relevant", summary.get("is_relevant")),
        "official_title": novel.get("official_title", summary.get("official_title")),
        "confidence": novel.get("confidence", summary.get("confidence")),
        "discussion_type": identity.get("discussion_type", summary.get("discussion_type")),
        "topicality": identity.get("topicality"),
        "relevance_scope": identity.get("relevance_scope"),
        "subtype": identity.get("subtype"),
        "work_resolution": identity.get("work_resolution"),
        "anchor_type": identity.get("anchor_type"),
        "anchor_strength": identity.get("anchor_strength"),
        "context_sources": identity.get("context_sources"),
        "consistency_flags": identity.get("consistency_flags"),
        "primary_work": identity.get("primary_work"),
        "title_candidates": identity.get("title_candidates"),
        "mentioned_works": identity.get("mentioned_works"),
        "comparison_target": identity.get("comparison_target"),
        "recommendation_candidates": identity.get("recommendation_candidates"),
        "novel_identity": novel,
        "reason": identity.get("reason") or summary.get("reason"),
        "reason_lines": identity.get("reason_lines") or summary.get("reason_lines"),
        "analysis_notes": ((item.get("analysis_result") or {}).get("analysis") or {}).get("notes") or summary.get("analysis_notes"),
    })
    return enriched


def _to_history_summary(item: Dict[str, Any]) -> Dict[str, Any]:
    identity = (item.get("analysis_result") or {}).get("identity") or {}
    novel = identity.get("novel_identity") or {}
    return {
        "post_id": item.get("post_id"),
        "title": item.get("title", ""),
        "is_relevant": identity.get("is_relevant"),
        "official_title": novel.get("official_title"),
        "confidence": novel.get("confidence"),
        "discussion_type": identity.get("discussion_type"),
        "topicality": identity.get("topicality"),
        "relevance_scope": identity.get("relevance_scope"),
        "subtype": identity.get("subtype"),
        "work_resolution": identity.get("work_resolution"),
        "primary_work": identity.get("primary_work"),
        "title_candidates": identity.get("title_candidates"),
        "novel_identity": novel,
    }


def _to_live_detail(item: Dict[str, Any], summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    identity = (item.get("analysis_result") or {}).get("identity") or {}
    novel = identity.get("novel_identity") or {}
    detail = {
        "post_id": item.get("post_id"),
        "title": item.get("title", ""),
        "author": item.get("author"),
        "created_at": item.get("created_at"),
        "url": item.get("url"),
        "content": item.get("content") or [],
        "comments": item.get("comments") or [],
        "is_relevant": identity.get("is_relevant"),
        "official_title": novel.get("official_title"),
        "confidence": novel.get("confidence"),
        "discussion_type": identity.get("discussion_type"),
        "topicality": identity.get("topicality"),
        "relevance_scope": identity.get("relevance_scope"),
        "subtype": identity.get("subtype"),
        "work_resolution": identity.get("work_resolution"),
        "anchor_type": identity.get("anchor_type"),
        "anchor_strength": identity.get("anchor_strength"),
        "context_sources": identity.get("context_sources"),
        "consistency_flags": identity.get("consistency_flags"),
        "reason_lines": identity.get("reason_lines"),
        "title_candidates": identity.get("title_candidates"),
        "primary_work": identity.get("primary_work"),
        "mentioned_works": identity.get("mentioned_works"),
        "future_watch_target": identity.get("future_watch_target"),
        "comparison_target": identity.get("comparison_target"),
        "recommendation_candidates": identity.get("recommendation_candidates"),
        "entity_mentions": identity.get("entity_mentions"),
        "reason": identity.get("reason", ""),
        "analysis_notes": ((item.get("analysis_result") or {}).get("analysis") or {}).get("notes"),
        "slang_insight": identity.get("slang_insight"),
        "analysis": (item.get("analysis_result") or {}).get("analysis"),
        "novel_identity": novel,
    }
    if summary:
        for key in ("elapsed", "token_usage", "flow_log", "worker_id"):
            if key in summary and summary.get(key) is not None:
                detail[key] = summary.get(key)
    return detail


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
async def api_run_detail(
    filename: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    summary: bool = Query(False),
):
    """특정 과거 결과 JSON 반환"""
    # path traversal 방지
    if ".." in filename or "/" in filename or "\\" in filename:
        return JSONResponse({"error": "invalid filename"}, status_code=400)

    filepath = _OUT_DIR / filename
    if not filepath.exists() or not filepath.name.startswith("expert_result_"):
        return JSONResponse({"error": "not found"}, status_code=404)

    try:
        data = _load_result_file(filepath)
        if not summary:
            return JSONResponse(data)

        relevant = sum(
            1
            for item in data
            if ((item.get("analysis_result") or {}).get("identity") or {}).get("is_relevant")
        )
        identified = sum(
            1
            for item in data
            if ((((item.get("analysis_result") or {}).get("identity") or {}).get("novel_identity") or {}).get("official_title"))
        )
        page = data[offset:offset + limit]
        return JSONResponse({
            "items": [_to_history_summary(item) for item in page],
            "total": len(data),
            "offset": offset,
            "limit": limit,
            "has_more": offset + limit < len(data),
            "stats": {
                "relevant": relevant,
                "identified": identified,
                "noise": len(data) - relevant,
            },
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/runs/{filename}/posts/{post_id}")
async def api_run_post_detail(filename: str, post_id: int):
    """특정 과거 실행에서 post_id 상세 결과 반환"""
    if ".." in filename or "/" in filename or "\\" in filename:
        return JSONResponse({"error": "invalid filename"}, status_code=400)

    filepath = _OUT_DIR / filename
    if not filepath.exists() or not filepath.name.startswith("expert_result_"):
        return JSONResponse({"error": "not found"}, status_code=404)

    item = _find_post_in_result_file(filepath, post_id)
    if item is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(item)


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


# ─── 포스트별 로그 추출 ────────────────────────────────────


def _extract_post_log_from_file(filepath: Path, post_id: int) -> Optional[List[str]]:
    """로그 파일에서 특정 post_id의 처리 구간을 추출합니다.
    
    마커:
      시작: '📌 Post ID: {post_id}' (배너 블록의 일부)
      끝:   '✅ Post {post_id} 완료' 이후 몇 줄 더 포함
    
    배너 시작 줄(===…) 부터 완료 마커 이후 구분선(===…)까지 추출합니다.
    """
    try:
        text = filepath.read_text(encoding="utf-8-sig")
    except Exception:
        return None

    lines = text.splitlines()
    total = len(lines)
    post_id_str = str(post_id)
    marker_start = f"📌 Post ID: {post_id_str}"
    marker_end_prefix = f"✅ Post {post_id_str} 완료"

    # 시작 위치 찾기 — "📌 Post ID:" 줄 탐색
    start_idx = None
    for i, line in enumerate(lines):
        if marker_start in line:
            # 배너 시작(===…) 줄로 역추적 (최대 5줄)
            banner_start = i
            for back in range(1, 6):
                if i - back >= 0 and lines[i - back].strip().startswith("=" * 10):
                    banner_start = i - back
                    break
            start_idx = banner_start
            break

    if start_idx is None:
        return None

    # 끝 위치 찾기 — "✅ Post {id} 완료" 줄 이후 구분선까지
    end_idx = total  # 기본값: 파일 끝
    found_end_marker = False
    for i in range(start_idx + 1, total):
        if marker_end_prefix in lines[i]:
            found_end_marker = True
            # 완료 마커 이후 추가 줄 포함 (토큰 요약, 구분선 등)
            end_idx = i + 1
            for j in range(i + 1, min(i + 80, total)):
                end_idx = j + 1
                # 다음 포스트 배너 시작이면 중단
                if "📌 Post ID:" in lines[j] and marker_start not in lines[j]:
                    end_idx = j  # 다음 포스트 배너 전까지
                    break
                if lines[j].strip().startswith("=" * 10) and j > i + 2:
                    # 다음 배너의 === 줄이면 한 줄 더 포함하고 중단
                    # 다음 줄이 "🤖" 로 시작하면 배너이므로 여기서 끊기
                    if j + 1 < total and "🤖" in lines[j + 1]:
                        end_idx = j
                        break
            break

    if not found_end_marker:
        # 완료 마커를 못 찾은 경우 — 다음 포스트 시작 전까지
        for i in range(start_idx + 5, total):
            if "📌 Post ID:" in lines[i] and marker_start not in lines[i]:
                end_idx = i
                for back in range(1, 6):
                    if i - back > start_idx and lines[i - back].strip().startswith("=" * 10):
                        end_idx = i - back
                        break
                break

    return lines[start_idx:end_idx]


@app.get("/api/post_log/{post_id}")
async def api_post_log(post_id: int):
    """특정 post_id의 처리 로그를 추출하여 반환합니다.
    
    검색 순서:
    1. 현재 실행 중인 배치의 로그 (인메모리)
    2. 워커별 로그 파일 (가장 최근 것부터)
    3. 통합 로그 파일 (가장 최근 것부터)
    """
    try:
        # 1) 인메모리 (현재 실행 중인 배치)
        in_memory = monitor.get_post_logs(post_id)
        if in_memory:
            return JSONResponse({
                "post_id": post_id,
                "source": "memory",
                "lines": in_memory,
            })

        # 2) 워커별 로그 파일 탐색 (최신순)
        if _LOG_DIR.exists():
            try:
                worker_logs = sorted(
                    _LOG_DIR.glob("expert_run_*_W*.log"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
            except OSError:
                worker_logs = []

            for wlog in worker_logs[:32]:  # 최근 32개까지만
                extracted = _extract_post_log_from_file(wlog, post_id)
                if extracted:
                    return JSONResponse({
                        "post_id": post_id,
                        "source": wlog.name,
                        "lines": extracted,
                    })

            # 3) 통합 로그 파일 탐색
            try:
                main_logs = sorted(
                    _LOG_DIR.glob("expert_run_*.log"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
            except OSError:
                main_logs = []
            main_logs = [p for p in main_logs if "_W" not in p.name]
            for mlog in main_logs[:5]:
                extracted = _extract_post_log_from_file(mlog, post_id)
                if extracted:
                    return JSONResponse({
                        "post_id": post_id,
                        "source": mlog.name,
                        "lines": extracted,
                    })

        return JSONResponse({"post_id": post_id, "source": None, "lines": []}, status_code=404)
    except Exception as exc:
        return JSONResponse(
            {"post_id": post_id, "error": f"{type(exc).__name__}: {exc}"},
            status_code=500,
        )


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
            results = monitor.get_results(offset=0, limit=200, order="desc")
            if results["items"]:
                yield f"event: restore\ndata: {json.dumps(results['items'], ensure_ascii=False, default=str)}\n\n"

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

    # 포트 충돌 시 자동으로 다음 포트를 탐색한다.
    # (Windows에서 10048 발생 시 대시보드가 조용히 죽는 문제 방지)
    def _is_port_available(bind_host: str, bind_port: int) -> bool:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((bind_host, bind_port))
            return True
        except OSError:
            return False
        finally:
            s.close()

    preferred_port = int(port)
    selected_port = preferred_port
    if not _is_port_available(host, selected_port):
        for candidate in range(preferred_port + 1, preferred_port + 32):
            if _is_port_available(host, candidate):
                selected_port = candidate
                break
        else:
            raise RuntimeError(
                f"Dashboard port unavailable: {host}:{preferred_port} (fallback failed)"
            )

    def _run():
        import uvicorn
        uvicorn.run(
            app,
            host=host,
            port=selected_port,
            log_level="warning",  # uvicorn 자체 로그는 최소화
            access_log=False,
        )

    t = threading.Thread(target=_run, daemon=True, name="dashboard")
    # 호출부에서 실제 바인드 포트를 로깅할 수 있게 노출
    setattr(t, "dashboard_port", selected_port)
    t.start()
    return t
