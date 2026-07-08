from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


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


def _post_id(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _source_index(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    index: dict[int, dict[str, Any]] = {}
    for row in rows:
        pid = _post_id(row.get("post_id"))
        if pid is not None and pid not in index:
            index[pid] = row
    return index


def _audit_blocker_rows(audit: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for row in audit.get("rows") or []:
        if not isinstance(row, dict):
            continue
        reason = str(row.get("search_blocker_reason") or "").strip()
        pid = _post_id(row.get("post_id"))
        if pid is None or not reason:
            continue
        blockers.append(row)
    return blockers


def build_blocker_replay_input(
    *,
    source_rows: list[dict[str, Any]],
    audit: dict[str, Any],
    batch_id: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_by_id = _source_index(source_rows)
    selected: list[dict[str, Any]] = []
    missing: list[int] = []
    blocker_rows = _audit_blocker_rows(audit)

    for audit_row in blocker_rows:
        pid = _post_id(audit_row.get("post_id"))
        if pid is None:
            continue
        source = source_by_id.get(pid)
        if source is None:
            missing.append(pid)
            continue
        row = dict(source)
        row["_search_recovery_blocker_replay"] = {
            "batch_id": batch_id,
            "post_id": pid,
            "source_audit_id": audit.get("audit_id"),
            "loop615_search_status": audit_row.get("search_status"),
            "loop615_search_blocker_reason": audit_row.get("search_blocker_reason"),
            "loop615_queries_issued": audit_row.get("queries_issued"),
            "loop615_degraded": audit_row.get("degraded"),
            "loop615_degraded_recovered": audit_row.get("degraded_recovered"),
            "loop615_unrecovered_degraded": audit_row.get("unrecovered_degraded"),
            "approval_state": "search_blocker_replay_required_not_approval",
            "close_condition": "runtime complete and row-level hard search blockers reduced to zero",
        }
        selected.append(row)

    reason_counts = Counter(
        str((row.get("_search_recovery_blocker_replay") or {}).get("loop615_search_blocker_reason") or "")
        for row in selected
    )
    status_counts = Counter(
        str((row.get("_search_recovery_blocker_replay") or {}).get("loop615_search_status") or "")
        for row in selected
    )
    manifest = {
        "report_type": "search_recovery_blocker_replay_input_manifest",
        "batch_id": batch_id,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "gate": "GO" if not missing else "NO-GO",
        "summary": {
            "source_input_rows": len(source_rows),
            "audit_blocker_rows": len(blocker_rows),
            "runtime_input_rows": len(selected),
            "missing_post_ids": missing,
            "blocker_reason_counts": dict(sorted(reason_counts.items())),
            "loop615_search_status_counts": dict(sorted(status_counts.items())),
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
            "approval_boundary": "blocker input generation is not runtime/search approval",
        },
        "missing_post_ids": missing,
    }
    return selected, manifest


def write_report(manifest: dict[str, Any], path: Path) -> None:
    summary = manifest.get("summary") or {}
    contract = manifest.get("execution_contract") or {}
    lines = [
        f"# {manifest.get('batch_id')} 검색 blocker 재실행 입력",
        "",
        "## 요약",
        "",
        f"- gate: `{manifest.get('gate')}`",
        f"- source_input_rows: `{summary.get('source_input_rows')}`",
        f"- audit_blocker_rows: `{summary.get('audit_blocker_rows')}`",
        f"- runtime_input_rows: `{summary.get('runtime_input_rows')}`",
        f"- missing_post_ids: `{summary.get('missing_post_ids')}`",
        f"- blocker_reason_counts: `{summary.get('blocker_reason_counts')}`",
        f"- loop615_search_status_counts: `{summary.get('loop615_search_status_counts')}`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "- full_scan_approval: `false`",
        "",
        "## 실행 계약",
        "",
        f"- requested_parallel: `{contract.get('requested_parallel')}`",
        f"- dashboard_required: `{contract.get('dashboard_required')}`",
        f"- forbidden_flags: `{contract.get('forbidden_flags')}`",
        f"- required_env: `{contract.get('required_env')}`",
        "- 이 입력 생성은 approval이 아니다. 재실행 후 row-level hard search blocker가 `0`인지 다시 감사한다.",
        "- full375 재실행은 이 blocker replay가 조용해진 뒤에만 연다.",
        "",
        "## Post ID 목록",
        "",
        ", ".join(str(post_id) for post_id in summary.get("post_ids") or []),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a replay input for rows with hard search blockers.")
    parser.add_argument("--source-input-jsonl", required=True, type=Path)
    parser.add_argument("--search-audit-json", required=True, type=Path)
    parser.add_argument("--batch-id", default="search_recovery_blocker_replay")
    parser.add_argument("--output-jsonl", required=True, type=Path)
    parser.add_argument("--manifest-json", required=True, type=Path)
    parser.add_argument("--report-md", required=True, type=Path)
    parser.add_argument("--fail-on-missing", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows, manifest = build_blocker_replay_input(
        source_rows=_load_jsonl(args.source_input_jsonl),
        audit=_load_json(args.search_audit_json),
        batch_id=args.batch_id,
    )
    manifest["source_input_jsonl"] = args.source_input_jsonl.as_posix()
    manifest["search_audit_json"] = args.search_audit_json.as_posix()
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
