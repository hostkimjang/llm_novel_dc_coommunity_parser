from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


RUNTIME_REPAIR_ACTION = "shared_gate_runtime_block_repair_required"
SEARCH_REPLAY_ACTION = "search_degraded_or_timeout_replay_required"
TRACE_REVIEW_ACTION = "blocked_expected_title_trace_review_required"


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _actions(row: dict[str, Any]) -> list[str]:
    value = row.get("actions") or row.get("action") or []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return []


def _post_id(row: dict[str, Any]) -> int | None:
    value = row.get("post_id")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _counter_to_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _runtime_rows(batch: dict[str, Any]) -> list[dict[str, Any]]:
    rows = batch.get("rows") or []
    if not isinstance(rows, list):
        raise ValueError("batch.rows must be a list")
    return [
        row
        for row in rows
        if isinstance(row, dict)
        and row.get("runtime_input_eligible") is True
        and str(row.get("review_label")) == "REPROCESS"
        and RUNTIME_REPAIR_ACTION in _actions(row)
    ]


def _verdict_rows(verdict: dict[str, Any]) -> list[dict[str, Any]]:
    rows = verdict.get("rows") or []
    if not isinstance(rows, list):
        raise ValueError("verdict.rows must be a list")
    return [row for row in rows if isinstance(row, dict)]


def classify_runtime_row(row: dict[str, Any]) -> tuple[str, list[str]]:
    actions = set(_actions(row))
    unrecovered = _int_value(row.get("search_unrecovered_degraded"))
    search_status = str(row.get("search_status") or "")
    if SEARCH_REPLAY_ACTION in actions or unrecovered > 0 or "DEGRADED" in search_status:
        if unrecovered > 0 or SEARCH_REPLAY_ACTION in actions:
            return (
                "search_blind_or_recovered_preflight_before_replay",
                ["search_degraded_or_timeout_not_recovered"],
            )
    if TRACE_REVIEW_ACTION in actions and row.get("exact_title_match") is True:
        return (
            "publish_contract_trace_repair_before_replay",
            ["exact_title_blocked_by_publish_contract_trace"],
        )
    return (
        "shared_gate_contract_repair_before_replay",
        ["shared_gate_runtime_block_unrepaired"],
    )


def classify_verdict_row(row: dict[str, Any]) -> tuple[str, list[str]]:
    label = str(row.get("review_label") or "")
    if label == "ACCEPT":
        return (
            "variant_policy_before_regression_exclusion",
            ["variant_accept_requires_gate_policy"],
        )
    if label == "REPROCESS":
        return (
            "canonical_repair_before_runtime_replay",
            ["canonical_title_or_url_repair_required"],
        )
    if label == "HOLD":
        return (
            "hard_hold_policy_or_native_review",
            ["hard_hold_not_relaxed"],
        )
    return ("manual_review", ["unknown_verdict_label"])


def build_readiness_queue(
    batch: dict[str, Any],
    verdict: dict[str, Any],
    *,
    queue_id: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    runtime_rows = _runtime_rows(batch)
    verdict_rows = _verdict_rows(verdict)
    validation_issues: list[dict[str, Any]] = []
    output_rows: list[dict[str, Any]] = []
    runtime_lane_counts: Counter[str] = Counter()
    verdict_lane_counts: Counter[str] = Counter()
    blocker_counts: Counter[str] = Counter()

    seen: set[int] = set()
    for row in runtime_rows:
        post_id = _post_id(row)
        if post_id is None:
            validation_issues.append({"code": "runtime_row_missing_post_id", "row": row})
            continue
        seen.add(post_id)
        lane, blockers = classify_runtime_row(row)
        runtime_lane_counts[lane] += 1
        for blocker in blockers:
            blocker_counts[blocker] += 1
        output_rows.append(
            {
                "post_id": post_id,
                "source": "loop491_runtime_reprocess",
                "review_label": row.get("review_label"),
                "lane": lane,
                "ready_for_runtime_replay": False,
                "blockers": blockers,
                "expected_title": row.get("expected_title"),
                "actual_title": row.get("actual_title"),
                "actual_url": row.get("actual_url"),
                "search_status": row.get("search_status"),
                "search_unrecovered_degraded": _int_value(row.get("search_unrecovered_degraded")),
                "exact_title_match": row.get("exact_title_match"),
                "compact_title_match": row.get("compact_title_match"),
                "candidate_ledger_status": row.get("candidate_ledger_status"),
                "promotion_status": row.get("promotion_status"),
                "title_resolution_state": row.get("title_resolution_state"),
                "work_resolution": row.get("work_resolution"),
                "discussion_type": row.get("discussion_type"),
                "actions": _actions(row),
                "reason_codes": row.get("reason_codes") or [],
                "close_condition": row.get("close_condition"),
            }
        )

    for row in verdict_rows:
        post_id = _post_id(row)
        if post_id is None:
            validation_issues.append({"code": "verdict_row_missing_post_id", "row": row})
            continue
        if post_id in seen:
            validation_issues.append({"code": "post_id_in_runtime_and_verdict_rows", "post_id": post_id})
        lane, blockers = classify_verdict_row(row)
        verdict_lane_counts[lane] += 1
        for blocker in blockers:
            blocker_counts[blocker] += 1
        output_rows.append(
            {
                "post_id": post_id,
                "source": "loop492_hold_verdict",
                "review_label": row.get("review_label"),
                "lane": lane,
                "ready_for_runtime_replay": False,
                "blockers": blockers,
                "expected_title": row.get("expected_title"),
                "actual_title": row.get("actual_title"),
                "actual_url": row.get("actual_url"),
                "selected_title": row.get("selected_title"),
                "selected_url": row.get("selected_url"),
                "source_native_verdict": row.get("source_native_verdict"),
                "evidence_grade": row.get("evidence_grade"),
                "native_web_checked": row.get("native_web_checked"),
                "actions": _actions(row),
                "rationale_ko": row.get("rationale_ko"),
            }
        )

    ready_count = sum(1 for row in output_rows if row.get("ready_for_runtime_replay") is True)
    blocked_count = len(output_rows) - ready_count
    return {
        "report_type": "runtime_replay_readiness_queue",
        "queue_id": queue_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_batch": batch.get("batch_id"),
        "source_verdict": verdict.get("review_id"),
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "summary": {
            "loop491_selected_p0_rows": (batch.get("summary") or {}).get("selected_rows"),
            "loop491_runtime_reprocess_rows": len(runtime_rows),
            "loop492_verdict_rows": len(verdict_rows),
            "ready_for_runtime_replay_rows": ready_count,
            "blocked_before_runtime_replay_rows": blocked_count,
            "runtime_lane_counts": _counter_to_dict(runtime_lane_counts),
            "verdict_lane_counts": _counter_to_dict(verdict_lane_counts),
            "blocker_counts": _counter_to_dict(blocker_counts),
            "validation_issue_count": len(validation_issues),
        },
        "runtime_replay_gate": {
            "status": "BLOCKED_BEFORE_REPAIR",
            "reason": "Loop491 warned that REPROCESS 14 would be a repeat unless shared-gate repair or search-blind tagging happens first.",
            "prepared_input": "out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop491_p0_reprocess14_runtime_replay_input.jsonl",
            "dispatch_rule": "Do not run the prepared input until ready_for_runtime_replay_rows is nonzero after code/contract repair or search preflight tagging.",
        },
        "stop_condition": {
            "actionable_queue_must_decrease": True,
            "same_packet_safe_resolved_must_be_monotonic_non_decreasing": True,
            "round_count_is_not_a_stop_condition": True,
        },
        "validation_issues": validation_issues,
        "rows": output_rows,
        "approval_boundary": {
            "readiness_queue_is_not_runtime_approval": True,
            "full375_collateral_remains_no_go": True,
            "full_scan_approval": False,
        },
    }


def write_markdown(path: Path, queue: dict[str, Any]) -> None:
    summary = queue["summary"]
    lines = [
        f"# {queue['queue_id']}",
        "",
        "## 요약",
        "",
        f"- source_batch: `{queue.get('source_batch')}`",
        f"- source_verdict: `{queue.get('source_verdict')}`",
        f"- Loop491 runtime REPROCESS rows: `{summary['loop491_runtime_reprocess_rows']}`",
        f"- Loop492 verdict rows: `{summary['loop492_verdict_rows']}`",
        f"- ready_for_runtime_replay rows: `{summary['ready_for_runtime_replay_rows']}`",
        f"- blocked_before_runtime_replay rows: `{summary['blocked_before_runtime_replay_rows']}`",
        f"- runtime lanes: `{summary['runtime_lane_counts']}`",
        f"- verdict lanes: `{summary['verdict_lane_counts']}`",
        f"- gate: `{queue['gate']}`",
        f"- semantic_quality: `{queue['semantic_quality']}`",
        f"- full_scan_approval: `{str(queue['full_scan_approval']).lower()}`",
        "",
        "## Runtime replay gate",
        "",
        f"- status: `{queue['runtime_replay_gate']['status']}`",
        f"- reason: {queue['runtime_replay_gate']['reason']}",
        f"- prepared input: `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop491_p0_reprocess14_runtime_replay_input.jsonl`",
        "- stop condition: actionable queue 감소 + 동일 packet safe_resolved 단조 비감소",
        "",
        "## Lanes",
        "",
    ]
    for lane, count in summary["runtime_lane_counts"].items():
        ids = [row["post_id"] for row in queue["rows"] if row.get("source") == "loop491_runtime_reprocess" and row.get("lane") == lane]
        lines.append(f"- `{lane}`: `{count}` rows / post_ids `{ids}`")
    for lane, count in summary["verdict_lane_counts"].items():
        ids = [row["post_id"] for row in queue["rows"] if row.get("source") == "loop492_hold_verdict" and row.get("lane") == lane]
        lines.append(f"- `{lane}`: `{count}` rows / post_ids `{ids}`")
    lines.extend(
        [
            "",
            "## Approval boundary",
            "",
            "- 이 readiness queue는 replay 승인이나 full375 GO가 아니다.",
            "- `ready_for_runtime_replay_rows=0`이므로 prepared 14건 입력을 즉시 실행하지 않는다.",
            "- 완료 기준은 계속 `adjusted full375 collateral GO + full_scan 경로 정의`다.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-queue", required=True)
    parser.add_argument("--verdicts", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--queue-id", default="runtime_replay_readiness_queue")
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    queue = build_readiness_queue(
        load_json(Path(args.batch_queue)),
        load_json(Path(args.verdicts)),
        queue_id=args.queue_id,
    )
    write_json(Path(args.output_json), queue)
    write_markdown(Path(args.output_md), queue)
    if args.fail_on_validation_issue and queue["validation_issues"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
