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

from fastapi import Body, FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .event_bus import monitor
from .run_index import RunIndex, bound_manifest, bound_manifest_rows, inside, row_meta
from .recovery_view import bind_recovery_view_row, read_recovery_view
from .recovery_provider_view import bind_recovery_provider_view_row, read_recovery_provider_view
from .recovery_native_view import bind_recovery_native_view_row, read_recovery_native_view

_run_index = RunIndex()

# ─── FastAPI 앱 ────────────────────────────────────────────

app = FastAPI(title="Expert Pipeline Monitor", docs_url=None, redoc_url=None)

# 프로젝트 루트 (expert_main.py 위치)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_OUT_DIR = _REPO_ROOT / "out"
_LOG_DIR = _REPO_ROOT / "logs"
_STATIC_DIR = Path(__file__).resolve().parent / "static"
_SLANG_DB_PATH = _REPO_ROOT / "slang_db" / "slang_db.json"

# 프런트엔드 자산만 제공한다. 결과·로그 등 저장소의 다른 파일은 포함하지 않는다.
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="dashboard-static")

# 감지 핸드셰이크 마커 — expert_main이 같은 포트의 무관한 앱을 오인하지 않게 한다.
_HEALTH_SERVICE_MARKER = "expert-pipeline-monitor"


def _is_standalone_mode() -> bool:
    """tools/dashboard_server.py 로 뜬 standalone 프로세스 여부."""
    return os.environ.get("DASHBOARD_STANDALONE", "0").strip() == "1"


# standalone 모드에서 웹 UI의 resume 요청을 expert_main forwarder에 전달하기 위한
# piggyback 플래그 (ingest 응답에 실어 보낸다).
_pending_resume_lock = threading.Lock()
_pending_resume_requested = False

# ─── REST API ──────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def index():
    """대시보드 메인 페이지"""
    html_file = _STATIC_DIR / "index.html"
    if html_file.exists():
        return HTMLResponse(html_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Dashboard index.html not found</h1>", status_code=404)


@app.get("/api/health")
async def api_health():
    """감지/핸드셰이크용 식별 응답.

    내장 대시보드도 같은 app이라 이 엔드포인트를 갖지만 standalone=False라서
    expert_main의 양보 대상이 되지 않는다.
    """
    return JSONResponse({
        "ok": True,
        "service": _HEALTH_SERVICE_MARKER,
        "standalone": _is_standalone_mode(),
        "pid": os.getpid(),
    })


def _ingest_token_ok(request: Request) -> bool:
    expected = os.environ.get("DASHBOARD_INGEST_TOKEN", "").strip()
    if not expected:
        return True
    return request.headers.get("X-Ingest-Token", "") == expected


def _verified_failed_runner_binding(data):
    """Legacy output-only UI needs actual local receipt/plan/manifest readback."""
    try:
        from tools.attach_manifest_dashboard import _failure_item
        ref, manifest_ref = data["receipt_ref"], data["manifest_ref"]
        rebuilt = _failure_item(Path(manifest_ref["path"]), Path(ref["path"]),
                                expected_run_id=data["run_id"], started_at=(data["started_at_epoch"]
                                    if data.get("start_time_source") == "RUNNER_EPOCH" else None))
        return rebuilt["data"] == data
    except Exception:
        return False


@app.post("/api/ingest")
def api_ingest(request: Request, payload: Dict[str, Any] = Body(...)):
    """expert_main forwarder가 보내는 이벤트/로그/스냅샷 배치를 주입한다.

    의도적으로 sync 핸들러(def) — FastAPI threadpool에서 실행되므로
    monitor 주입 경로가 expert_main 워커 스레드의 emit과 동일한
    (비-이벤트루프 스레드 → call_soon_threadsafe) 검증된 패턴을 탄다.
    """
    # 내장 모드 프로세스는 외부 ingest를 받지 않는다 — standalone이 죽은 사이
    # 같은 포트를 다른 expert_main의 내장 대시보드가 차지했을 때 런 간
    # 교차 주입(상태 오염)을 수신 측에서 차단한다.
    if not _is_standalone_mode():
        return JSONResponse(
            {"ok": False, "error": "ingest is only accepted in standalone mode"},
            status_code=403,
        )
    if not _ingest_token_ok(request):
        return JSONResponse({"ok": False, "error": "invalid ingest token"}, status_code=403)

    items = payload.get("items") or []
    accepted = 0
    for item in items:
        try:
            kind = item.get("kind")
            if kind == "event":
                event_type = str(item.get("type") or "")
                event_data = item.get("data") or {}
                if event_type == "batch_failed":
                    verified = _verified_failed_runner_binding(event_data)
                    core_notice = (event_data.get("failure_origin") == "CORE_EXCEPTION"
                                   and event_data.get("reason_code") == "CORE_EXCEPTION"
                                   and event_data.get("process_exited") is False
                                   and event_data.get("exit_code") is None)
                    if not core_notice and not verified:
                        continue
                    applied = monitor.ingest_failure(event_data, legacy_receipt_bound=verified)
                else:
                    applied = monitor.ingest_event(event_type, event_data, ts=item.get("ts"))
                if applied is not False:
                    accepted += 1
            elif kind == "log":
                raw_worker_id = item.get("worker_id")
                monitor.ingest_log(
                    str(item.get("line") or ""),
                    worker_id=-1 if raw_worker_id is None else int(raw_worker_id),
                )
                accepted += 1
            elif kind == "status_snapshot":
                if monitor.load_status_snapshot(item.get("data") or {}) is not False:
                    accepted += 1
        except Exception:
            continue

    global _pending_resume_requested
    with _pending_resume_lock:
        resume_requested = _pending_resume_requested
        _pending_resume_requested = False

    return JSONResponse({
        "ok": True,
        "received": len(items),
        "accepted": accepted,
        "resume_requested": resume_requested,
    })


@app.get("/api/status")
async def api_status():
    """현재 배치 실행 상태"""
    return JSONResponse(monitor.get_status())


@app.post("/api/llm/resume")
async def api_llm_resume(
    source: str = Query("web_dashboard", pattern="^[a-z_]{1,32}$"),
):
    """대시보드에서 LLM suspend 상태를 재개합니다."""
    # standalone 모드: suspend 컨트롤러는 expert_main 프로세스에 있으므로
    # 직접 호출 대신 ingest 응답에 piggyback할 플래그만 세운다.
    if _is_standalone_mode():
        if not monitor.llm_suspended:
            return JSONResponse(
                {"ok": False, "error": "llm suspend 상태가 아닙니다.", "source": source},
                status_code=409,
            )
        global _pending_resume_requested
        with _pending_resume_lock:
            _pending_resume_requested = True
        return JSONResponse({"ok": True, "source": source, "forwarded": True})

    try:
        from llm_batch.llm.client import request_llm_server_resume

        ok = request_llm_server_resume(source=source)
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
            status_code=500,
        )

    if not ok:
        return JSONResponse(
            {"ok": False, "error": "llm suspend 상태가 아닙니다.", "source": source},
            status_code=409,
        )

    return JSONResponse({"ok": True, "source": source})


@app.get("/api/results")
async def api_results(
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    q: str = Query("", max_length=200),
    relevance: str = Query("all", pattern="^(all|relevant|noise)$"),
):
    """현재 실행의 포스트별 결과 요약 (페이지 단위 + 검색/필터)"""
    return JSONResponse(
        _build_live_results_payload(offset=offset, limit=limit, order=order, q=q, relevance=relevance)
    )


@app.get("/api/results/{post_id}")
async def api_result_detail(post_id: int):
    """현재 실행 결과에서 특정 post_id의 상세 정보를 반환"""
    summary = monitor.get_result_summary(post_id)

    for path in _candidate_result_paths():
        if not path.exists():
            continue
        item = _find_post_in_result_file(path, post_id)
        if item is not None:
            output, _ = _current_output_binding()
            return JSONResponse(await asyncio.to_thread(_to_live_detail, item, summary=summary, output_path=output or path))

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


@app.get("/api/slang-db")
async def api_slang_db(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """slang_db titles 버킷을 페이지 단위로 반환"""
    return JSONResponse(_build_slang_db_payload(offset=offset, limit=limit))


# ─── 과거 실행 이력 ──────────────────────────────────────


_TS_RE = re.compile(r"(\d{8}_\d{6})")
_FINAL_RESULT_RE = re.compile(r"^expert_result_(\d{8}_\d{6}_\d+)\.json$")
_FULL_RUN_ID_RE = re.compile(r"^\d{8}_\d{6}_\d+$")


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
    return _run_index.load_result(filepath, _OUT_DIR)


def _unwrap_result_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """중간 스냅샷 항목이면 실제 result payload를 꺼낸다."""
    if not isinstance(item, dict):
        return {}
    nested = item.get("result")
    if isinstance(nested, dict):
        return nested
    return item


def _find_post_in_result_file(filepath: Path, post_id: int) -> Optional[Dict[str, Any]]:
    try:
        data = _load_result_file(filepath)
    except Exception:
        return None

    for raw_item in data:
        item = _unwrap_result_item(raw_item)
        if item.get("post_id") == post_id:
            return item
    return None


def _is_final_result_file(path_or_name: Any) -> bool:
    name = Path(str(path_or_name or "")).name
    return bool(_FINAL_RESULT_RE.fullmatch(name))


def _current_output_binding() -> tuple[Optional[Path], bool]:
    """Return the repository-local current output and whether a scope was declared.

    A declared current output is authoritative even while its final JSON is not
    present yet.  Returning ``(None, True)`` for an unsafe binding prevents the
    live API from silently reading an unrelated historical result.
    """

    status = monitor.get_status()
    output_name = str(status.get("output_file") or "").strip()
    if not output_name:
        return None, False

    output_path = Path(output_name)
    if not output_path.is_absolute():
        output_path = _OUT_DIR / output_path
    try:
        output_path = output_path.resolve()
        output_path.relative_to(_OUT_DIR.resolve())
    except (OSError, ValueError):
        return None, True
    if output_path.suffix.lower() != ".json":
        return None, True
    return output_path, True


def _run_id_from_current_output(output_path: Path) -> Optional[str]:
    """Resolve the exact run id without borrowing a timestamp from history."""
    match = _FINAL_RESULT_RE.fullmatch(output_path.name)
    binding = bound_manifest(output_path, _OUT_DIR)
    if binding["binding_status"] == "MISMATCH":
        return None
    run_id = binding["summary"].get("run_id") or (match.group(1) if match else "")
    if not isinstance(run_id, str) or not _FULL_RUN_ID_RE.fullmatch(run_id):
        return None
    if output_path.exists():
        try:
            rows = _load_result_file(output_path)
            for item in rows:
                item = _unwrap_result_item(item)
                if row_meta(item).get("run_id") not in (None, "", run_id):
                    return None
            if binding["summary"] and bound_manifest_rows(output_path, _OUT_DIR, rows)["binding_status"] == "MISMATCH":
                return None
        except (OSError, ValueError, UnicodeError):
            return None
    return run_id


def _recent_final_result_paths() -> List[Path]:
    if not _OUT_DIR.exists():
        return []
    return [
        path
        for path in sorted(_OUT_DIR.glob("expert_result_*.json"), reverse=True)
        if _is_final_result_file(path)
    ]


def _candidate_result_paths() -> List[Path]:
    candidate_paths: List[Path] = []
    output_path, current_scope_declared = _current_output_binding()
    if current_scope_declared:
        if output_path is None:
            return []
        candidate_paths.append(output_path)

        # 실행 중에는 final JSON이 아직 flush 중일 수 있으므로 같은 디렉터리의
        # current-run snapshot만 폴백으로 둔다. current scope가 선언된 동안에는
        # post_id가 같은 과거 실행으로 넘어가지 않는다.
        pending_snapshot = output_path.with_name(f"{output_path.stem}_pending_snapshot.json")
        if pending_snapshot not in candidate_paths:
            candidate_paths.append(pending_snapshot)
        return candidate_paths

    for path in _recent_final_result_paths():
        if path not in candidate_paths:
            candidate_paths.append(path)
        if len(candidate_paths) >= 4:
            break
    return candidate_paths


def _load_slang_db_file() -> Dict[str, Any]:
    if not _SLANG_DB_PATH.exists():
        return {"updated_at": None, "titles": {}, "family_aliases": {}}

    try:
        payload = json.loads(_SLANG_DB_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"updated_at": None, "titles": {}, "family_aliases": {}}

    if not isinstance(payload, dict):
        return {"updated_at": None, "titles": {}, "family_aliases": {}}

    titles = payload.get("titles")
    if not isinstance(titles, dict):
        titles = {}
    family_aliases = payload.get("family_aliases")
    if not isinstance(family_aliases, dict):
        family_aliases = {}

    return {
        "updated_at": payload.get("updated_at"),
        "titles": titles,
        "family_aliases": family_aliases,
    }


def _extract_term_list(bucket: Any, key: str) -> List[str]:
    if not isinstance(bucket, dict):
        return []

    terms: List[str] = []
    seen: set[str] = set()
    for entry in bucket.get(key) or []:
        raw_term = entry.get("term") if isinstance(entry, dict) else entry
        term = str(raw_term or "").strip()
        if not term or term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms


def _extract_slang_terms(bucket: Any) -> List[str]:
    return _extract_term_list(bucket, "slang")


def _extract_pending_terms(bucket: Any) -> List[str]:
    return _extract_term_list(bucket, "pending")


def _extract_conflict_terms(bucket: Any) -> List[str]:
    return _extract_term_list(bucket, "conflicts")


def _build_pending_kind_counts(bucket: Any) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    if not isinstance(bucket, dict):
        return counts
    for entry in bucket.get("pending") or []:
        if not isinstance(entry, dict):
            continue
        kind = str(entry.get("pending_kind") or "unknown").strip()
        if not kind:
            kind = "unknown"
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def _extract_example_preview(bucket: Any, *, limit: int = 3) -> List[Dict[str, Any]]:
    preview: List[Dict[str, Any]] = []
    if not isinstance(bucket, dict):
        return preview
    for example in (bucket.get("examples") or [])[:limit]:
        if not isinstance(example, dict):
            continue
        preview.append(
            {
                "post_id": example.get("post_id"),
                "alias": example.get("alias"),
                "bucket": example.get("bucket"),
                "source_role": example.get("source_role"),
                "discussion_type": example.get("discussion_type"),
                "work_resolution": example.get("work_resolution"),
                "pending_kind": example.get("pending_kind"),
                "classification_confidence": example.get("classification_confidence"),
                "created_at": example.get("created_at"),
            }
        )
    return preview


def _extract_family_alias_terms(payload: Dict[str, Any], title: str) -> List[str]:
    terms: List[str] = []
    seen: set[str] = set()
    for key, bucket in (payload.get("family_aliases") or {}).items():
        if not isinstance(bucket, dict):
            continue
        titles = [str(x).strip() for x in (bucket.get("titles") or []) if str(x).strip()]
        if str(title or "").strip() not in titles:
            continue
        term = str(bucket.get("term") or key or "").strip()
        if not term or term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms


def _build_slang_db_payload(offset: int = 0, limit: int = 100) -> Dict[str, Any]:
    payload = _load_slang_db_file()
    rows: List[Dict[str, Any]] = []
    summary = {
        "titles_with_slang": 0,
        "titles_with_pending": 0,
        "titles_with_conflicts": 0,
        "titles_with_family_aliases": 0,
    }

    for title, bucket in sorted((payload.get("titles") or {}).items(), key=lambda item: str(item[0])):
        title_text = str(title or "").strip()
        slang_terms = _extract_slang_terms(bucket)
        pending_terms = _extract_pending_terms(bucket)
        conflict_terms = _extract_conflict_terms(bucket)
        family_alias_terms = _extract_family_alias_terms(payload, title_text)
        example_preview = _extract_example_preview(bucket)
        pending_kind_counts = _build_pending_kind_counts(bucket)
        if slang_terms:
            summary["titles_with_slang"] += 1
        if pending_terms:
            summary["titles_with_pending"] += 1
        if conflict_terms:
            summary["titles_with_conflicts"] += 1
        if family_alias_terms:
            summary["titles_with_family_aliases"] += 1
        rows.append({
            "title": title_text,
            "slang_terms": slang_terms,
            "slang_count": len(slang_terms),
            "pending_terms": pending_terms,
            "pending_count": len(pending_terms),
            "pending_kind_counts": pending_kind_counts,
            "conflict_terms": conflict_terms,
            "conflict_count": len(conflict_terms),
            "family_alias_terms": family_alias_terms,
            "family_alias_count": len(family_alias_terms),
            "example_preview": example_preview,
            "example_count": len(bucket.get("examples") or []),
        })

    total = len(rows)
    page = rows[offset:offset + limit]
    return {
        "items": page,
        "total": total,
        "offset": offset,
        "limit": limit,
        "updated_at": payload.get("updated_at"),
        "summary": summary,
    }


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
    missing_scope = not all(key in item for key in (
        "identity_state",
        "is_novel_related",
        "is_resolved_work_discussion",
        "title_resolution_state",
        "title_resolution_allowed",
        "primary_subject_type",
        "primary_subject_text",
    ))
    missing_reason = not (
        _has_text(item.get("reason"))
        or _has_text(item.get("reason_lines"))
        or _has_text(item.get("analysis_notes"))
    )
    return missing_structure or missing_scope or missing_reason


def _build_live_results_payload(
    offset: int = 0,
    limit: int = 200,
    order: str = "desc",
    q: str = "",
    relevance: str = "all",
) -> Dict[str, Any]:
    payload = monitor.get_results(offset=offset, limit=limit, order=order, q=q, relevance=relevance)
    items = payload.get("items") or []

    if not items or not any(_summary_needs_identity_enrichment(item) for item in items):
        return payload

    for path in _candidate_result_paths():
        if not path.exists():
            continue
        try:
            raw_items = _load_result_file(path)
        except Exception:
            continue
        by_post_id = {}
        for raw_item in raw_items:
            item = _unwrap_result_item(raw_item)
            post_id = item.get("post_id")
            if post_id is not None:
                by_post_id[post_id] = raw_item
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

    return payload


def _enrich_summary_from_result(summary: Dict[str, Any], item: Dict[str, Any]) -> Dict[str, Any]:
    item = _unwrap_result_item(item)
    identity = (item.get("analysis_result") or {}).get("identity") or {}
    novel = identity.get("novel_identity") or {}
    enriched = dict(summary)
    enriched.update({
        "is_relevant": identity.get("is_relevant", summary.get("is_relevant")),
        "identity_state": identity.get("identity_state", summary.get("identity_state")),
        "is_novel_related": identity.get("is_novel_related", summary.get("is_novel_related")),
        "is_resolved_work_discussion": identity.get("is_resolved_work_discussion", summary.get("is_resolved_work_discussion")),
        "title_resolution_state": identity.get("title_resolution_state", summary.get("title_resolution_state")),
        "title_resolution_allowed": identity.get("title_resolution_allowed", summary.get("title_resolution_allowed")),
        "primary_subject_type": identity.get("primary_subject_type", summary.get("primary_subject_type")),
        "primary_subject_text": identity.get("primary_subject_text", summary.get("primary_subject_text")),
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
    item = _unwrap_result_item(item)
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


def _to_live_detail(item: Dict[str, Any], summary: Optional[Dict[str, Any]] = None,
                    *, output_path: Optional[Path] = None) -> Dict[str, Any]:
    item = _unwrap_result_item(item)
    identity = (item.get("analysis_result") or {}).get("identity") or {}
    novel = identity.get("novel_identity") or {}
    detail = {
        # 상세 화면은 현재 identity 계약 전체를 받는다. 목록/SSE의 크기는 유지한다.
        **identity,
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
        "run_meta": row_meta(item),
    }
    if output_path is not None:
        detail["run_manifest"] = bound_manifest(output_path, _OUT_DIR, item=item)
        detail["recovery_execution"] = read_recovery_view(output_path, _OUT_DIR, item=item)
        detail["recovery_provider_execution"] = read_recovery_provider_view(output_path, _OUT_DIR, item=item)
        detail["recovery_native_execution"] = read_recovery_native_view(output_path, _OUT_DIR, item=item)
        # WAL 재생 행의 원래 run_id와 현재 export를 합치지 않는다.
        detail["recovery_native_export_manifest"] = bound_manifest(output_path, _OUT_DIR)
    if summary:
        for key in ("elapsed", "token_usage", "flow_log", "flow_dropped", "worker_id"):
            if key in summary and summary.get(key) is not None:
                detail[key] = summary.get(key)
    return detail


@app.get("/api/runs")
async def api_runs():
    """기존 최상위 결과와 검증된 중첩 sidecar를 제한된 캐시로 조회한다."""
    current_output, _ = _current_output_binding()
    records = await asyncio.to_thread(_run_index.records, _OUT_DIR, current_output=current_output)
    runs = [_run_public(record) for record in records.values()]
    return JSONResponse(runs, headers={"X-Run-Index-Truncated": str(_run_index.truncated).lower()})


def _run_public(record):
    public = dict(record.public)
    public["timestamp"] = _parse_run_ts(public.get("run_id") or public["filename"])
    run_id = public.get("run_id")
    if run_id:
        log = inside(_LOG_DIR / f"expert_run_{run_id}.log", _LOG_DIR)
        if log is not None and log.is_file():
            public["log_file"] = log.name
    return public


def _history_record(filename):
    if ".." in filename or "/" in filename or "\\" in filename:
        return None, JSONResponse({"error": "invalid run key"}, status_code=400)
    current_output, _ = _current_output_binding()
    record = _run_index.resolve(filename, _OUT_DIR, current_output=current_output)
    if record is None:
        return None, JSONResponse({"error": "not found"}, status_code=404)
    return record, None


def _history_item(item, record, recovery_view=None, provider_view=None, native_view=None):
    result = dict(_unwrap_result_item(item))
    recovery = (read_recovery_view(record.path, _OUT_DIR, item=result) if recovery_view is None
                else bind_recovery_view_row(recovery_view, result))
    provider = (read_recovery_provider_view(record.path, _OUT_DIR, item=result) if provider_view is None
                else bind_recovery_provider_view_row(provider_view, result))
    native = (read_recovery_native_view(record.path, _OUT_DIR, item=result) if native_view is None
              else bind_recovery_native_view_row(native_view, result))
    result["run_meta"] = row_meta(result)
    result["run_manifest"] = bound_manifest(record.path, _OUT_DIR, item=result, manifest_path=record.manifest)
    result["recovery_execution"] = recovery
    result["recovery_provider_execution"] = provider
    result["recovery_native_execution"] = native
    result["recovery_native_export_manifest"] = bound_manifest(record.path, _OUT_DIR, manifest_path=record.manifest)
    return result


def _history_detail(filename, offset, limit, summary):
    record, error = _history_record(filename)
    if error is not None:
        return error
    try:
        data = _load_result_file(record.path)
        if not summary:
            recovery = read_recovery_view(record.path, _OUT_DIR)
            provider = read_recovery_provider_view(record.path, _OUT_DIR)
            native = read_recovery_native_view(record.path, _OUT_DIR)
            return JSONResponse([_history_item(item, record, recovery, provider, native) for item in data])
        data = [_unwrap_result_item(item) for item in data]
        relevant = sum(1 for item in data if ((item.get("analysis_result") or {}).get("identity") or {}).get("is_relevant"))
        identified = sum(1 for item in data if ((((item.get("analysis_result") or {}).get("identity") or {}).get("novel_identity") or {}).get("official_title")))
        return JSONResponse({
            "items": [_to_history_summary(item) for item in data[offset:offset + limit]],
            "total": len(data), "offset": offset, "limit": limit,
            "has_more": offset + limit < len(data),
            "stats": {"relevant": relevant, "identified": identified, "noise": len(data) - relevant},
            "run": _run_public(record),
            "run_manifest": bound_manifest_rows(record.path, _OUT_DIR, data, manifest_path=record.manifest),
            "recovery_native_execution": read_recovery_native_view(record.path, _OUT_DIR),
            "recovery_native_export_manifest": bound_manifest(record.path, _OUT_DIR, manifest_path=record.manifest),
        })
    except (OSError, ValueError, UnicodeError):
        return JSONResponse({"error": "result unavailable or invalid"}, status_code=422)


@app.get("/api/runs/{filename}")
async def api_run_detail(
    filename: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    summary: bool = Query(False),
):
    """불투명 실행 키와 기존 최상위 filename을 모두 지원한다."""
    return await asyncio.to_thread(_history_detail, filename, offset, limit, summary)


@app.get("/api/runs/{filename}/posts/{post_id}")
async def api_run_post_detail(filename: str, post_id: int):
    """특정 과거 실행에서 post_id 상세 결과 반환"""
    record, error = await asyncio.to_thread(_history_record, filename)
    if error is not None:
        return error
    item = await asyncio.to_thread(_find_post_in_result_file, record.path, post_id)
    if item is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(await asyncio.to_thread(_history_item, item, record))


@app.get("/api/runs/{filename}/log")
def api_run_log(filename: str, tail: int = Query(300, ge=1, le=5000)):
    """선택한 실행 ID의 로그만 읽고 큰 로그는 마지막 2 MiB로 제한한다."""
    record, error = _history_record(filename)
    if error is not None:
        return error
    run_id = _run_id_from_current_output(record.path)
    if not run_id:
        return JSONResponse({"lines": [], "source": None, "run_id": None}, status_code=404)
    path = inside(_LOG_DIR / f"expert_run_{run_id}.log", _LOG_DIR)
    if path is None or not path.is_file():
        return JSONResponse({"lines": [], "source": None, "run_id": run_id}, status_code=404)
    try:
        with path.open("rb") as stream:
            size = stream.seek(0, 2)
            start = max(0, size - 2 * 1024 * 1024)
            stream.seek(start)
            raw = stream.read(2 * 1024 * 1024)
        lines = raw.decode("utf-8-sig", errors="replace").splitlines()
        if start and lines:
            lines = lines[1:]
        return JSONResponse({"lines": lines[-tail:], "source": path.name, "run_id": run_id, "truncated": bool(start)})
    except OSError:
        return JSONResponse({"lines": [], "source": None, "run_id": run_id}, status_code=404)


@app.get("/api/logs/{filename}")
async def api_log_detail(filename: str, tail: int = Query(300, ge=1, le=5000)):
    """특정 로그 파일의 마지막 n줄"""
    if ".." in filename or "/" in filename or "\\" in filename:
        return JSONResponse({"error": "invalid filename"}, status_code=400)

    filepath = inside(_LOG_DIR / filename, _LOG_DIR)
    if filepath is None or not filepath.exists() or not filepath.name.startswith("expert_run_"):
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
    filepath = inside(filepath, _LOG_DIR)
    if filepath is None:
        return None
    try:
        # GB급 통합 로그를 통째로 read하면 메모리 스파이크(파일 크기의 2-3배)가
        # 발생한다 — 상한 초과 파일은 건너뛴다 (워커별 로그가 1차 탐색 대상이라
        # 대부분 거기서 찾는다). DASHBOARD_POST_LOG_MAX_FILE_MB로 조정 가능.
        try:
            max_mb = float(os.environ.get("DASHBOARD_POST_LOG_MAX_FILE_MB", "200"))
        except Exception:
            max_mb = 200.0
        if max_mb > 0 and filepath.stat().st_size > max_mb * 1024 * 1024:
            return None
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
def api_post_log(post_id: int, source: str = Query("auto", pattern="^(auto|file)$")):
    """특정 post_id의 처리 로그를 추출하여 반환합니다.

    의도적으로 sync 핸들러(def) — 로그 파일 추출이 대형 파일(수십 MB~GB)
    전체 read라 async로 두면 uvicorn 이벤트 루프가 블로킹되어 SSE/상태 API가
    전부 멈춘다. FastAPI threadpool에서 실행되면 루프는 계속 돈다.

    검색 순서:
    1. 현재 실행 중인 배치의 로그 (인메모리) — source=file이면 건너뜀
    2. 워커별 로그 파일 (가장 최근 것부터)
    3. 통합 로그 파일 (가장 최근 것부터)

    인메모리 로그는 post_start 이후 워커 라인만 수집되어 시작 배너 등
    앞부분이 빠질 수 있다. 전체 구간이 필요하면 source=file로 호출하면
    로그 파일에서 배너~완료 요약까지 추출해 반환한다.
    """
    try:
        # 1) 인메모리 (현재 실행 중인 배치)
        if source != "file":
            in_memory = monitor.get_post_logs(post_id)
            if in_memory:
                return JSONResponse({
                    "post_id": post_id,
                    "source": "memory",
                    "lines": in_memory,
                })

        output_path, current_scope_declared = _current_output_binding()
        current_run_id = (
            _run_id_from_current_output(output_path)
            if output_path is not None
            else None
        )

        # 2) 워커별 로그 파일 탐색. current output이 선언된 경우 동일 run id로만
        # 범위를 고정하며, 결속 정보가 없다고 과거 실행으로 넘어가지 않는다.
        if _LOG_DIR.exists():
            try:
                worker_pattern = (
                    f"expert_run_{current_run_id}_W*.log"
                    if current_scope_declared and current_run_id
                    else "expert_run_*_W*.log"
                )
                worker_logs = (
                    sorted(
                        _LOG_DIR.glob(worker_pattern),
                        key=lambda p: p.stat().st_mtime,
                        reverse=True,
                    )
                    if (not current_scope_declared or current_run_id)
                    else []
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
                if current_scope_declared:
                    main_logs = (
                        [_LOG_DIR / f"expert_run_{current_run_id}.log"]
                        if current_run_id
                        else []
                    )
                    main_logs = [path for path in main_logs if path.exists()]
                else:
                    main_logs = sorted(
                        _LOG_DIR.glob("expert_run_*.log"),
                        key=lambda p: p.stat().st_mtime,
                        reverse=True,
                    )
                    main_logs = [p for p in main_logs if "_W" not in p.name]
            except OSError:
                main_logs = []
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
            # limit 200이면 초기 페이로드가 ~240KB에 달해 접속/재연결마다 부담 —
            # 50건이면 첫 화면 채우기에 충분하고 나머지는 /api/results 페이지로.
            results = _build_live_results_payload(offset=0, limit=50, order="desc")
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
