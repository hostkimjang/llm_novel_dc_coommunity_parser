"""Attach an existing manifest/checkpoint based expert run to the web dashboard.

This is a narrow bridge for runs that were started with ``--no-dashboard``.
It periodically reads an expert_main manifest and POSTs a status snapshot to a
standalone dashboard server (``tools/dashboard_server.py``).
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import math
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


def _manifest_failure(manifest: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """A stored core failure may restore display state, never a completed run."""
    failure = manifest.get("batch_failure")
    declared = manifest.get("batch_status") == "FAILED" or manifest.get("terminal_status") == "FAILED"
    if failure is None and not declared:
        return None
    if (not declared or type(failure) is not dict
            or failure.get("schema_version") not in {"dashboard_run_failure_v1", "expert_batch_failure_v1"}
            or failure.get("failure_origin") != "CORE_EXCEPTION" or failure.get("reason_code") != "CORE_EXCEPTION"
            or failure.get("process_exited") is not False or failure.get("exit_code") is not None
            or failure.get("shutdown_status") not in {"NOT_STARTED", "DRAINING", "DRAINED", "CLEANUP_ERROR"}
            or manifest.get("large_run_complete") is True or manifest.get("terminal_artifacts_finalized") is True):
        raise ValueError("manifest failed state lacks consistent core failure")
    if (type(manifest.get("run_id")) is not str or not manifest["run_id"]
            or failure.get("run_id") != manifest["run_id"]
            or "publication_scope_id" not in manifest or "publication_scope_id" not in failure
            or failure["publication_scope_id"] != manifest["publication_scope_id"]
            or type(failure.get("output_file")) is not str or not Path(failure["output_file"]).is_absolute()
            or type(manifest.get("output_file")) is not str or not Path(manifest["output_file"]).is_absolute()
            or Path(failure["output_file"]).resolve() != Path(manifest["output_file"]).resolve()):
        raise ValueError("manifest failure run/output/scope mismatch")
    keys = ("input_post_count", "completed_count", "flushed_count", "pending_count", "failed_count")
    counts = failure.get("manifest_counts")
    if (type(counts) is not dict or set(counts) != set(keys)
            or any(type(counts[k]) is not int or type(manifest.get(k)) is not int
                   or counts[k] != manifest[k] or counts[k] < 0 for k in keys)
            or any(v > counts["input_post_count"] for v in counts.values())):
        raise ValueError("manifest failure counts mismatch")
    parallel = failure.get("parallel_count")
    if (type(parallel) is not int or parallel < 1
            or any(k in manifest and (type(manifest[k]) is not int or manifest[k] != parallel)
                   for k in ("effective_parallel", "parallel_count"))):
        raise ValueError("manifest failure parallel mismatch")
    start, end = _epoch(failure.get("started_at_epoch")), _epoch(failure.get("ended_at_epoch"))
    if end < start:
        raise ValueError("manifest failure time order mismatch")
    return deepcopy(failure)


def _snapshot(manifest: Dict[str, Any], *, started_at: float, summary_limit: int, start_time_source: str = "UNSPECIFIED") -> Dict[str, Any]:
    total = int(manifest.get("input_post_count") or 0)
    completed = int(manifest.get("completed_count") or 0)
    failed = int(manifest.get("failed_count") or 0)
    failure = _manifest_failure(manifest)
    parallel = (failure["parallel_count"] if failure is not None else
                int(manifest.get("parallel_count") or manifest.get("effective_parallel") or 1))
    snapshot = {
        "batch_running": not bool(manifest.get("large_run_complete")),
        "batch_status": "COMPLETED" if manifest.get("large_run_complete") else "RUNNING",
        "run_id": manifest.get("run_id"),
        "publication_scope_id": manifest.get("publication_scope_id"),
        "total_posts": total,
        "current_index": completed,
        "input_file": manifest.get("input_file") or "",
        "output_file": manifest.get("output_file") or "",
        "parallel_count": parallel,
        "batch_start_time": started_at,
        "batch_start_time_source": start_time_source,
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
    if failure is not None:
        snapshot.update(batch_running=False, batch_status="FAILED", batch_failure=failure,
                        batch_start_time=failure["started_at_epoch"], batch_start_time_source="CORE_EPOCH")
    return snapshot


def _post_items(url: str, items: List[Dict[str, Any]], *, token: str = "") -> Dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Ingest-Token"] = token
    body = json.dumps({"items": items}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{url.rstrip('/')}/api/ingest", data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=5) as resp:
        payload = resp.read().decode("utf-8")
    return json.loads(payload or "{}")


def _epoch(value: Any) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError("dashboard start/end epoch must be finite and positive")
    return float(value)


def _started_at_from_manifest(manifest: Dict[str, Any], explicit: Optional[float] = None) -> float:
    # Runner epoch takes precedence. A paired START has an explicit UTC offset;
    # a run ID is an identifier, not a timezone-aware process start timestamp.
    if explicit is not None:
        return _epoch(explicit)
    observed = ((manifest.get("paired_execution_observation") or {}).get("start") or {}).get("observed_at")
    if isinstance(observed, str):
        try:
            stamp = datetime.fromisoformat(observed.replace("Z", "+00:00"))
            if stamp.tzinfo is not None:
                return _epoch(stamp.timestamp())
        except ValueError:
            pass
    # Legacy CLI compatibility only; no UTC inference from an old run ID.
    run_id = str(manifest.get("run_id") or "").strip()
    parts = run_id.split("_")
    if len(parts) >= 2:
        raw = f"{parts[0]}_{parts[1]}"
        try:
            return time.mktime(datetime.strptime(raw, "%Y%m%d_%H%M%S").timetuple())
        except ValueError:
            pass
    return time.time()


def _start_time_source(manifest: Dict[str, Any], explicit: Optional[float] = None) -> str:
    if explicit is not None:
        return "RUNNER_EPOCH"
    observed = ((manifest.get("paired_execution_observation") or {}).get("start") or {}).get("observed_at")
    try:
        if isinstance(observed, str) and datetime.fromisoformat(observed.replace("Z", "+00:00")).tzinfo is not None:
            return "PAIRED_START_OBSERVATION"
    except ValueError:
        pass
    return "LEGACY_INFERRED_OR_ATTACH_TIME"


def _failure_item(manifest_path: Path, receipt_path: Path, *,
                  expected_run_id: str, started_at: Optional[float] = None) -> Dict[str, Any]:
    """Read-only binding of a failed runner receipt to exactly one dashboard run."""
    receipt_bytes = receipt_path.read_bytes()
    receipt = json.loads(receipt_bytes)
    if (receipt.get("receipt_type") != "independent_plan_execution_receipt"
            or receipt.get("gate") not in {"FAILED", "FAILED_RUNTIME_ARTIFACT_VALIDATION"}
            or type(receipt.get("exit_code")) is not int or receipt["exit_code"] == 0):
        raise ValueError("not an explicit failed runner receipt")
    plan_path = Path(receipt["plan"])
    plan_bytes = plan_path.read_bytes()
    if hashlib.sha256(plan_bytes).hexdigest() != receipt.get("plan_sha256"):
        raise ValueError("failure receipt plan SHA mismatch")
    runs = json.loads(plan_bytes)["planned_runs"]
    index = receipt.get("failed_run_index")
    if type(index) is not int or not 1 <= index <= len(runs):
        raise ValueError("failure receipt run index invalid")
    run = runs[index - 1]
    output = Path(run["output_json"]).resolve()
    planned_manifest = Path(run.get("manifest_json") or output.with_name(output.stem + "_manifest.json"))
    if planned_manifest.resolve() != manifest_path.resolve():
        raise ValueError("failure receipt manifest path mismatch")
    manifest = _load_json(manifest_path)
    if "batch_completion_contract" in run:
        contract = run["batch_completion_contract"]
        if (type(contract) is not dict or type(contract.get("planned_run_id")) is not str
                or not contract["planned_run_id"] or contract["planned_run_id"] != expected_run_id):
            raise ValueError("failure planned run ID mismatch")
    if (not expected_run_id or manifest.get("run_id") != expected_run_id
            or Path(str(manifest.get("output_file") or "")).resolve() != output):
        raise ValueError("failure run/output binding mismatch")
    claim_path = run.get("output_attempt_claim_json")
    if claim_path:
        claim = _load_json(Path(claim_path))
        if (claim.get("run_id") != expected_run_id
                or Path(str(claim.get("output_file") or "")).resolve() != output):
            raise ValueError("failure attempt claim mismatch")
    counts = {key: manifest.get(key, 0) for key in
              ("input_post_count", "completed_count", "flushed_count", "pending_count", "failed_count")}
    if any(type(v) is not int or v < 0 for v in counts.values()):
        raise ValueError("failure manifest counts invalid")
    total = counts["input_post_count"]
    if any(v > total for k, v in counts.items() if k != "input_post_count"):
        raise ValueError("failure manifest count exceeds denominator")
    parallel = manifest.get("effective_parallel") or manifest.get("parallel_count") or 1
    if type(parallel) is not int or parallel < 1:
        raise ValueError("failure manifest parallel invalid")
    start = _started_at_from_manifest(manifest, started_at)
    # New runner receipts carry aware UTC. Legacy receipts used local ISO time.
    end = _epoch(datetime.fromisoformat(receipt["completed_at"].replace("Z", "+00:00")).timestamp())
    if end < start:
        raise ValueError("failure receipt precedes observed start")
    reason = "CHILD_EXIT_NONZERO" if receipt["gate"] == "FAILED" else "ARTIFACT_VALIDATION_FAILED"
    message = f"child exit {receipt['exit_code']}" if reason == "CHILD_EXIT_NONZERO" else str(receipt.get("error") or "runtime artifact validation failed")
    data = {"schema_version": "dashboard_run_failure_v1", "run_id": expected_run_id,
            "output_file": str(output), "publication_scope_id": manifest.get("publication_scope_id"),
            "parallel_count": parallel,
            "failure_origin": "RUNNER_RECEIPT", "reason_code": reason, "message": message[:1000], "exit_code": receipt["exit_code"] if reason == "CHILD_EXIT_NONZERO" else 0,
            "invocation_exit_code": receipt["exit_code"], "process_exited": True,
            "start_time_source": _start_time_source(manifest, started_at),
            "started_at_epoch": start, "ended_at_epoch": end, "manifest_counts": counts,
            "manifest_ref": {"path": str(manifest_path.resolve()), "sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()},
            "receipt_ref": {"path": str(receipt_path.resolve()), "sha256": hashlib.sha256(receipt_bytes).hexdigest()},
            "terminal_artifacts_finalized": manifest.get("terminal_artifacts_finalized") is True}
    return {"kind": "event", "type": "batch_failed", "data": data}


def main() -> int:
    parser = argparse.ArgumentParser(description="Attach manifest progress to standalone dashboard")
    parser.add_argument("--manifest", required=True, help="expert_main manifest JSON path")
    parser.add_argument("--dashboard-url", default="http://127.0.0.1:8080", help="standalone dashboard base URL")
    parser.add_argument("--interval-sec", type=float, default=5.0, help="snapshot push interval")
    parser.add_argument("--summary-limit", type=int, default=500, help="max live result summaries to push")
    parser.add_argument("--once", action="store_true", help="push one snapshot and exit")
    parser.add_argument("--started-at-epoch", type=float, default=None, help="actual runner start epoch; never inferred from run ID")
    parser.add_argument("--failure-receipt", help="report an explicit failed runner receipt once; do not change manifest/WAL")
    parser.add_argument("--expected-run-id", help="required exact run binding for --failure-receipt")
    parser.add_argument("--token", default="", help="DASHBOARD_INGEST_TOKEN if configured")
    parser.add_argument(
        "--wait-for-manifest-sec",
        type=float,
        default=0.0,
        help="wait this long for a manifest that is being created by a just-started run",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if args.failure_receipt:
        try:
            item = _failure_item(manifest_path, Path(args.failure_receipt),
                                 expected_run_id=args.expected_run_id or "", started_at=args.started_at_epoch)
            reply = _post_items(args.dashboard_url, [item], token=args.token)
            if reply.get("accepted") != 1:
                raise ValueError("dashboard rejected failure binding")
        except (ValueError, KeyError, OSError, urllib.error.URLError) as exc:
            print(f"[attach_manifest_dashboard] failure not applied: {exc}", flush=True)
            return 2
        return 0
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
            started_at = _started_at_from_manifest(manifest, args.started_at_epoch)
        completed = int(manifest.get("completed_count") or 0)
        try:
            snap = _snapshot(manifest, started_at=started_at, summary_limit=args.summary_limit,
                             start_time_source=_start_time_source(manifest, args.started_at_epoch))
        except ValueError as exc:
            print(f"[attach_manifest_dashboard] snapshot not applied: {exc}", flush=True)
            return 2
        items = [
            {
                "kind": "status_snapshot",
                "data": snap,
            },
        ]
        if completed != last_completed and snap.get("batch_failure") is None:
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
            reply = _post_items(args.dashboard_url, items, token=args.token)
            if snap.get("batch_failure") is not None and reply.get("accepted") != 1:
                print("[attach_manifest_dashboard] failure snapshot binding rejected", flush=True)
                return 2
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"[attach_manifest_dashboard] dashboard post failed: {exc}", flush=True)
            if snap.get("batch_failure") is not None:
                return 2
        if args.once or bool(manifest.get("large_run_complete")):
            break
        time.sleep(max(1.0, args.interval_sec))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
