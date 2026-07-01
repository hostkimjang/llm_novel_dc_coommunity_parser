from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


CLOSED_ACTION_STATUSES = {
    "done",
    "closed",
    "complete",
    "completed",
    "hold",
    "human_review",
    "info_missing",
    "unresolved_matchable",
    "quarantine",
    "no_generalizable_fix_left",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        rows: list[dict[str, Any]] = []
        for line_no, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
            if not raw_line.strip():
                continue
            row = json.loads(raw_line)
            if not isinstance(row, dict):
                raise ValueError(f"Expected JSON object at {path}:{line_no}")
            rows.append(row)
        return rows
    payload = load_json(path)
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("results", "rows", "items"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    raise ValueError(f"Unsupported row payload: {path}")


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _first_int(payload: dict[str, Any], paths: list[tuple[str, ...]]) -> tuple[int | None, str | None]:
    for path in paths:
        current: Any = payload
        for key in path:
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(key)
        value = _safe_int(current)
        if value is not None:
            return value, ".".join(path)
    return None, None


def actionable_count(payload: dict[str, Any]) -> tuple[int | None, str]:
    value, source = _first_int(
        payload,
        [
            ("next_actionable_queue",),
            ("summary", "next_actionable_queue"),
            ("summary", "actionable_queue"),
            ("summary", "actionable_count"),
            ("queue", "next_actionable"),
            ("residual_accounting", "next_actionable"),
        ],
    )
    if value is not None:
        return value, source or "explicit_count"

    actions = payload.get("actions")
    if isinstance(actions, list):
        open_items = 0
        for item in actions:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or "open").strip().lower()
            if status in CLOSED_ACTION_STATUSES:
                continue
            open_items += 1
        return open_items, "actions_open_status_count"

    summary_total = _safe_int((payload.get("summary") or {}).get("total_actions"))
    if summary_total is not None:
        return summary_total, "summary.total_actions"
    return None, "missing"


def unwrap_result_row(row: dict[str, Any]) -> dict[str, Any]:
    nested = row.get("result")
    if isinstance(nested, dict):
        return nested
    return row


def row_post_id(row: dict[str, Any]) -> str:
    row = unwrap_result_row(row)
    value = row.get("post_id")
    if value is None:
        value = row.get("id")
    return str(value or "").strip()


def row_identity(row: dict[str, Any]) -> dict[str, Any]:
    row = unwrap_result_row(row)
    analysis = row.get("analysis_result") if isinstance(row.get("analysis_result"), dict) else {}
    identity = analysis.get("identity") if isinstance(analysis, dict) else None
    if isinstance(identity, dict):
        return identity
    identity = row.get("identity")
    return identity if isinstance(identity, dict) else {}


def row_status(row: dict[str, Any]) -> str:
    identity = row_identity(row)
    return str(identity.get("candidate_ledger_status") or row.get("candidate_ledger_status") or "").strip()


def packet_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    post_ids: list[str] = []
    safe_ids: list[str] = []
    status_counts: dict[str, int] = {}
    for row in rows:
        post_id = row_post_id(row)
        if not post_id:
            continue
        post_ids.append(post_id)
        status = row_status(row)
        status_counts[status or "missing"] = status_counts.get(status or "missing", 0) + 1
        if status == "safe_resolved":
            safe_ids.append(post_id)
    return {
        "post_ids": sorted(set(post_ids), key=lambda value: (not value.isdigit(), int(value) if value.isdigit() else value)),
        "row_count": len(post_ids),
        "safe_resolved_count": len(set(safe_ids)),
        "safe_resolved_post_ids": sorted(set(safe_ids), key=lambda value: (not value.isdigit(), int(value) if value.isdigit() else value)),
        "status_counts": dict(sorted(status_counts.items())),
    }


def evaluate_convergence(
    previous_queue: dict[str, Any],
    current_queue: dict[str, Any],
    previous_packet_rows: list[dict[str, Any]],
    current_packet_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    previous_actionable, previous_actionable_source = actionable_count(previous_queue)
    current_actionable, current_actionable_source = actionable_count(current_queue)
    queue_decreased = (
        previous_actionable is not None
        and current_actionable is not None
        and current_actionable < previous_actionable
    )

    previous_packet = packet_summary(previous_packet_rows)
    current_packet = packet_summary(current_packet_rows)
    previous_ids = set(previous_packet["post_ids"])
    current_ids = set(current_packet["post_ids"])
    same_packet = previous_ids == current_ids and bool(previous_ids)
    previous_safe_ids = set(previous_packet["safe_resolved_post_ids"])
    current_safe_ids = set(current_packet["safe_resolved_post_ids"])
    safe_loss_ids = sorted(previous_safe_ids - current_safe_ids) if same_packet else []
    safe_gain_ids = sorted(current_safe_ids - previous_safe_ids) if same_packet else []
    safe_monotonic = (
        same_packet
        and current_packet["safe_resolved_count"] >= previous_packet["safe_resolved_count"]
        and previous_safe_ids.issubset(current_safe_ids)
    )

    blockers: list[dict[str, Any]] = []
    if not queue_decreased:
        blockers.append(
            {
                "code": "actionable_queue_not_decreased",
                "previous_actionable": previous_actionable,
                "current_actionable": current_actionable,
            }
        )
    if not same_packet:
        blockers.append(
            {
                "code": "packet_identity_changed",
                "missing_from_current": sorted(previous_ids - current_ids),
                "extra_in_current": sorted(current_ids - previous_ids),
            }
        )
    if same_packet and not safe_monotonic:
        blockers.append(
            {
                "code": "safe_resolved_not_monotonic",
                "previous_safe_resolved": previous_packet["safe_resolved_count"],
                "current_safe_resolved": current_packet["safe_resolved_count"],
                "safe_loss_post_ids": safe_loss_ids,
            }
        )

    gate = "GO" if queue_decreased and same_packet and safe_monotonic else "NO-GO"
    return {
        "report_type": "goal_convergence_stop_condition",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "gate": gate,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "stop_condition": {
            "loop_count_based_stop": False,
            "requires_actionable_queue_decrease": True,
            "requires_same_packet_safe_resolved_monotonic_nondecrease": True,
        },
        "actionable_queue": {
            "previous": previous_actionable,
            "current": current_actionable,
            "previous_source": previous_actionable_source,
            "current_source": current_actionable_source,
            "decreased": queue_decreased,
        },
        "packet": {
            "same_packet": same_packet,
            "previous": previous_packet,
            "current": current_packet,
            "safe_resolved_monotonic_nondecrease": safe_monotonic,
            "safe_loss_post_ids": safe_loss_ids,
            "safe_gain_post_ids": safe_gain_ids,
            "safe_delta_evaluated": same_packet,
        },
        "blockers": blockers,
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    queue = report["actionable_queue"]
    packet = report["packet"]
    lines = [
        "# Goal 수렴 정지조건 평가",
        "",
        f"- gate: `{report['gate']}`",
        f"- semantic_quality: `{report['semantic_quality']}`",
        f"- full_scan_approval: `{str(report['full_scan_approval']).lower()}`",
        "- 정지조건: 회차 수가 아니라 `actionable queue 감소`와 `동일 packet safe_resolved 단조 비감소`를 동시에 요구한다.",
        "",
        "## Queue",
        "",
        f"- previous actionable: `{queue['previous']}` (`{queue['previous_source']}`)",
        f"- current actionable: `{queue['current']}` (`{queue['current_source']}`)",
        f"- decreased: `{queue['decreased']}`",
        "",
        "## Packet",
        "",
        f"- same_packet: `{packet['same_packet']}`",
        f"- previous safe_resolved: `{packet['previous']['safe_resolved_count']}`",
        f"- current safe_resolved: `{packet['current']['safe_resolved_count']}`",
        f"- safe_delta_evaluated: `{packet['safe_delta_evaluated']}`",
        f"- safe_resolved_monotonic_nondecrease: `{packet['safe_resolved_monotonic_nondecrease']}`",
        f"- safe_loss_post_ids: `{packet['safe_loss_post_ids']}`",
        f"- safe_gain_post_ids: `{packet['safe_gain_post_ids']}`",
        "",
        "## Blockers",
        "",
    ]
    if report["blockers"]:
        for item in report["blockers"]:
            lines.append(f"- `{item['code']}`: `{item}`")
    else:
        lines.append("- 없음")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the architecture goal convergence stop condition.")
    parser.add_argument("--previous-queue", required=True, type=Path)
    parser.add_argument("--current-queue", required=True, type=Path)
    parser.add_argument("--previous-packet-result", required=True, type=Path)
    parser.add_argument("--current-packet-result", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-no-go", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate_convergence(
        load_json(args.previous_queue),
        load_json(args.current_queue),
        load_rows(args.previous_packet_result),
        load_rows(args.current_packet_result),
    )
    write_json(args.output_json, report)
    write_markdown(report, args.output_md)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.fail_on_no_go and report["gate"] != "GO":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
