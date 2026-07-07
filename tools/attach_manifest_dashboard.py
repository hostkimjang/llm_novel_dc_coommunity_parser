"""Attach an existing manifest/checkpoint based expert run to the web dashboard.

This is a narrow bridge for runs that were started with ``--no-dashboard``.
It periodically reads an expert_main manifest and POSTs a status snapshot to a
standalone dashboard server (``tools/dashboard_server.py``).
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_json_when_ready(path: Path, *, wait_sec: float = 0.0, retry_sec: float = 0.5) -> Any:
    deadline = time.time() + max(0.0, wait_sec)
    while True:
        try:
            return _load_json(path)
        except (FileNotFoundError, JSONDecodeError, OSError) as exc:
            if time.time() >= deadline:
                raise
            time.sleep(max(0.1, retry_sec))


def _read_json_array(path: Path, *, limit: int = 500) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = _load_json(path)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    rows = [item for item in data if isinstance(item, dict)]
    return rows[-limit:]


def _iter_checkpoint_tail(path: Path, *, limit: int = 500) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    rows: List[Dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _identity(item: Dict[str, Any]) -> Dict[str, Any]:
    return ((item.get("analysis_result") or {}).get("identity") or {})


def _novel(identity: Dict[str, Any]) -> Dict[str, Any]:
    value = identity.get("novel_identity") or {}
    return value if isinstance(value, dict) else {}


def _summary_from_result(item: Dict[str, Any]) -> Dict[str, Any]:
    identity = _identity(item)
    novel = _novel(identity)
    return {
        "post_id": item.get("post_id"),
        "title": item.get("title", ""),
        "author": item.get("author") or item.get("post_author"),
        "created_at": item.get("created_at"),
        "url": item.get("url"),
        "is_relevant": identity.get("is_relevant"),
        "official_title": novel.get("official_title"),
        "confidence": novel.get("confidence"),
        "discussion_type": identity.get("discussion_type"),
        "topicality": identity.get("topicality"),
        "subtype": identity.get("subtype"),
        "work_resolution": identity.get("work_resolution"),
        "relevance_scope": identity.get("relevance_scope"),
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
    }


def _build_post_summaries(manifest: Dict[str, Any], *, limit: int = 500) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    result_path = Path(str(manifest.get("output_file") or ""))
    for item in _read_json_array(result_path, limit=limit):
        rows.append(_summary_from_result(item))

    checkpoint_path = Path(str(manifest.get("checkpoint_jsonl") or ""))
    seen = {row.get("post_id") for row in rows}
    for checkpoint_item in _iter_checkpoint_tail(checkpoint_path, limit=limit):
        result = checkpoint_item.get("result")
        if not isinstance(result, dict):
            continue
        post_id = result.get("post_id")
        if post_id in seen:
            continue
        seen.add(post_id)
        rows.append(_summary_from_result(result))

    return rows[-limit:]


def _snapshot(manifest: Dict[str, Any], *, started_at: float, summary_limit: int) -> Dict[str, Any]:
    total = int(manifest.get("input_post_count") or 0)
    completed = int(manifest.get("completed_count") or 0)
    failed = int(manifest.get("failed_count") or 0)
    parallel = int(manifest.get("parallel_count") or manifest.get("effective_parallel") or 1)
    return {
        "batch_running": not bool(manifest.get("large_run_complete")),
        "total_posts": total,
        "current_index": completed,
        "input_file": manifest.get("input_file") or "",
        "output_file": manifest.get("output_file") or "",
        "parallel_count": parallel,
        "batch_start_time": started_at,
        "done_count": completed,
        "relevant_count": 0,
        "noise_count": 0,
        "search_hits": int(manifest.get("mcp_health_ok_count") or 0),
        "search_misses": int(manifest.get("mcp_health_failure_count") or 0),
        "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "post_summaries": _build_post_summaries(manifest, limit=summary_limit),
        "active_posts": {},
        "llm_suspended": False,
        "attach_manifest": {
            "run_id": manifest.get("run_id"),
            "completed_count": completed,
            "flushed_count": manifest.get("flushed_count"),
            "pending_count": manifest.get("pending_count"),
            "failed_count": failed,
            "large_run_complete": manifest.get("large_run_complete"),
            "ordered_flush_blocked": manifest.get("ordered_flush_blocked"),
            "partial_flush_gap": manifest.get("partial_flush_gap"),
        },
    }


def _post_items(url: str, items: List[Dict[str, Any]], *, token: str = "") -> Dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Ingest-Token"] = token
    body = json.dumps({"items": items}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{url.rstrip('/')}/api/ingest", data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=5) as resp:
        payload = resp.read().decode("utf-8")
    return json.loads(payload or "{}")


def _started_at_from_manifest(manifest: Dict[str, Any]) -> float:
    run_id = str(manifest.get("run_id") or "").strip()
    parts = run_id.split("_")
    if len(parts) >= 2:
        raw = f"{parts[0]}_{parts[1]}"
        try:
            return time.mktime(datetime.strptime(raw, "%Y%m%d_%H%M%S").timetuple())
        except ValueError:
            pass
    return time.time()


def main() -> int:
    parser = argparse.ArgumentParser(description="Attach manifest progress to standalone dashboard")
    parser.add_argument("--manifest", required=True, help="expert_main manifest JSON path")
    parser.add_argument("--dashboard-url", default="http://127.0.0.1:8080", help="standalone dashboard base URL")
    parser.add_argument("--interval-sec", type=float, default=5.0, help="snapshot push interval")
    parser.add_argument("--summary-limit", type=int, default=500, help="max live result summaries to push")
    parser.add_argument("--once", action="store_true", help="push one snapshot and exit")
    parser.add_argument("--token", default="", help="DASHBOARD_INGEST_TOKEN if configured")
    parser.add_argument(
        "--wait-for-manifest-sec",
        type=float,
        default=0.0,
        help="wait this long for a manifest that is being created by a just-started run",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    started_at: Optional[float] = None
    last_completed: Optional[int] = None
    first_load = True

    while True:
        try:
            manifest = _load_json_when_ready(
                manifest_path,
                wait_sec=args.wait_for_manifest_sec if first_load else min(args.interval_sec, 2.0),
            )
        except (FileNotFoundError, JSONDecodeError, OSError) as exc:
            print(
                f"[attach_manifest_dashboard] manifest not ready: {manifest_path} ({exc})",
                flush=True,
            )
            return 2
        first_load = False
        if started_at is None:
            started_at = _started_at_from_manifest(manifest)
        completed = int(manifest.get("completed_count") or 0)
        snap = _snapshot(manifest, started_at=started_at, summary_limit=args.summary_limit)
        items = [
            {
                "kind": "status_snapshot",
                "data": snap,
            },
        ]
        if completed != last_completed:
            items.append(
                {
                    "kind": "log",
                    "worker_id": -1,
                    "line": (
                        "[manifest-attach] "
                        f"run_id={manifest.get('run_id')} "
                        f"completed={completed}/{manifest.get('input_post_count')} "
                        f"flushed={manifest.get('flushed_count')} "
                        f"pending={manifest.get('pending_count')} "
                        f"failed={manifest.get('failed_count')}"
                    ),
                }
            )
            last_completed = completed
        try:
            _post_items(args.dashboard_url, items, token=args.token)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"[attach_manifest_dashboard] dashboard post failed: {exc}", flush=True)
        if args.once or bool(manifest.get("large_run_complete")):
            break
        time.sleep(max(1.0, args.interval_sec))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
