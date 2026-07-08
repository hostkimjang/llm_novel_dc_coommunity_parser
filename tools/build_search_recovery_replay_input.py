from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_DEFERRED_STATUSES = {"SEARCH_DEGRADED", "SEARCH_DEGRADED_RECOVERED"}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"Expected object at {path}:{line_no}")
            rows.append(payload)
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _post_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _source_index(source_result: Any) -> dict[str, dict[str, Any]]:
    if isinstance(source_result, dict):
        raw_rows = source_result.get("rows") or source_result.get("results") or source_result.get("items")
    else:
        raw_rows = source_result
    if not isinstance(raw_rows, list):
        raise ValueError("source result must be a list or object with rows/results/items")

    index: dict[str, dict[str, Any]] = {}
    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        pid = _post_id(row.get("post_id"))
        if pid is not None and pid not in index:
            index[pid] = row
    return index


def _runtime_row(source: dict[str, Any], deferred: dict[str, Any], batch_id: str) -> dict[str, Any]:
    row = {key: value for key, value in source.items() if key not in {"analysis_result", "run_meta"}}
    row["_search_recovery_replay"] = {
        "batch_id": batch_id,
        "post_id": deferred.get("post_id"),
        "loop609_primary_action": deferred.get("primary_action"),
        "loop609_status": deferred.get("status"),
        "loop609_search_status": deferred.get("search_status"),
        "loop609_search_queries": deferred.get("search_queries"),
        "loop609_search_degraded": deferred.get("search_degraded"),
        "loop609_search_degraded_recovered": deferred.get("search_degraded_recovered"),
        "loop609_search_unrecovered_degraded": deferred.get("search_unrecovered_degraded"),
        "survey_failure_class": deferred.get("survey_failure_class"),
        "survey_disagreement_type": deferred.get("survey_disagreement_type"),
        "survey_correct_hypothesis": deferred.get("survey_correct_hypothesis"),
        "before_title": deferred.get("before_title"),
        "after_title": deferred.get("after_title"),
        "approval_state": "search_recovery_replay_required_not_approval",
        "close_condition": (
            "runtime complete with query-level search health ok, then recompare only these deferred rows"
        ),
    }
    return row


def build_replay_input(
    source_result: Any,
    deferred_rows: list[dict[str, Any]],
    *,
    batch_id: str,
    deferred_statuses: set[str] | None = None,
    limit: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    deferred_statuses = deferred_statuses or DEFAULT_DEFERRED_STATUSES
    source_by_id = _source_index(source_result)
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    missing: list[Any] = []
    seen: set[str] = set()

    for deferred in deferred_rows:
        pid = _post_id(deferred.get("post_id"))
        status = str(deferred.get("search_status") or "").strip()
        if pid is None:
            skipped.append({"post_id": None, "reason": "missing_post_id"})
            continue
        if status not in deferred_statuses:
            skipped.append({"post_id": deferred.get("post_id"), "reason": "search_status_not_deferred", "status": status})
            continue
        if pid in seen:
            skipped.append({"post_id": deferred.get("post_id"), "reason": "duplicate_post_id"})
            continue
        source = source_by_id.get(pid)
        if source is None:
            missing.append(deferred.get("post_id"))
            continue
        selected.append(_runtime_row(source, deferred, batch_id))
        seen.add(pid)
        if limit is not None and len(selected) >= limit:
            break

    replay_meta = [row.get("_search_recovery_replay") or {} for row in selected]
    status_counts = Counter(str(item.get("loop609_search_status") or "") for item in replay_meta)
    action_counts = Counter(str(item.get("loop609_primary_action") or "") for item in replay_meta)
    survey_counts = Counter(str(item.get("survey_failure_class") or "None") for item in replay_meta)
    manifest = {
        "report_type": "search_recovery_replay_input_manifest",
        "batch_id": batch_id,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "gate": "GO" if not missing else "NO-GO",
        "summary": {
            "deferred_source_rows": len(deferred_rows),
            "runtime_input_rows": len(selected),
            "missing_post_ids": missing,
            "skipped_rows": len(skipped),
            "loop609_search_status_counts": dict(sorted(status_counts.items())),
            "loop609_primary_action_counts": dict(sorted(action_counts.items())),
            "survey_failure_class_counts": dict(sorted(survey_counts.items())),
            "post_ids": [row.get("post_id") for row in selected],
        },
        "execution_contract": {
            "requested_parallel": 16,
            "dashboard_required": True,
            "forbidden_flags": ["--no-dashboard"],
            "required_env": {
                "MCP_HEALTH_INCLUDE_SEARCH": "1",
                "MCP_HEALTH_LIGHT_MODE": "0",
                "DASHBOARD_URL": "http://127.0.0.1:8080",
                "DASHBOARD_PORT": "8080",
                "EXPERT_DASHBOARD_FORWARD": "1",
            },
            "approval_boundary": "input generation is not runtime/search approval",
        },
        "missing_post_ids": missing,
        "skipped": skipped,
    }
    return selected, manifest


def write_report(manifest: dict[str, Any], path: Path) -> None:
    summary = manifest.get("summary") or {}
    contract = manifest.get("execution_contract") or {}
    lines = [
        f"# {manifest.get('batch_id')} search recovery replay input",
        "",
        "## 요약",
        "",
        f"- gate: `{manifest.get('gate')}`",
        f"- runtime_input_rows: `{summary.get('runtime_input_rows')}`",
        f"- missing_post_ids: `{summary.get('missing_post_ids')}`",
        f"- skipped_rows: `{summary.get('skipped_rows')}`",
        f"- loop609_search_status_counts: `{summary.get('loop609_search_status_counts')}`",
        f"- primary_action_counts: `{summary.get('loop609_primary_action_counts')}`",
        f"- survey_failure_class_counts: `{summary.get('survey_failure_class_counts')}`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "- full_scan_approval: `false`",
        "",
        "## 실행 계약",
        "",
        f"- requested_parallel: `{contract.get('requested_parallel')}`",
        f"- dashboard_required: `{contract.get('dashboard_required')}`",
        f"- forbidden_flags: `{contract.get('forbidden_flags')}`",
        f"- required_env: `{contract.get('required_env')}`",
        "- 이 입력 생성은 approval이 아니다. 재실행 후 row-level search health가 `ok`인지 별도 감사해야 한다.",
        "- full375 재실행은 이 보류 행 재실행과 검색 복구 판정 이후에만 연다.",
        "",
        "## Post IDs",
        "",
        ", ".join(str(post_id) for post_id in summary.get("post_ids") or []),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")


def _parse_statuses(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a runtime replay input for search-degraded deferred rows.")
    parser.add_argument("--source-result", required=True, type=Path)
    parser.add_argument("--deferred-jsonl", required=True, type=Path)
    parser.add_argument("--batch-id", default="search_recovery_replay")
    parser.add_argument("--deferred-statuses", default=",".join(sorted(DEFAULT_DEFERRED_STATUSES)))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--output-jsonl", required=True, type=Path)
    parser.add_argument("--manifest-json", required=True, type=Path)
    parser.add_argument("--report-md", required=True, type=Path)
    parser.add_argument("--fail-on-missing", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows, manifest = build_replay_input(
        _load_json(args.source_result),
        _load_jsonl(args.deferred_jsonl),
        batch_id=args.batch_id,
        deferred_statuses=_parse_statuses(args.deferred_statuses),
        limit=args.limit if args.limit > 0 else None,
    )
    manifest["source_result"] = args.source_result.as_posix()
    manifest["deferred_jsonl"] = args.deferred_jsonl.as_posix()
    manifest["output_jsonl"] = args.output_jsonl.as_posix()
    _write_jsonl(args.output_jsonl, rows)
    _write_json(args.manifest_json, manifest)
    write_report(manifest, args.report_md)
    if args.fail_on_missing and manifest.get("missing_post_ids"):
        return 1
    print(f"WROTE {args.output_jsonl} rows={len(rows)} gate={manifest.get('gate')}")
    print(f"WROTE {args.manifest_json}")
    print(f"WROTE {args.report_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
