from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from tools.test_run_dashboard_policy import test_run_execution_contract
except ModuleNotFoundError:  # direct script execution: python tools/build_action_queue_batch.py
    from test_run_dashboard_policy import test_run_execution_contract


RUNTIME_REPROCESS_ACTION = "shared_gate_runtime_block_repair_required"
SEARCH_REPLAY_ACTION = "search_degraded_or_timeout_replay_required"
CANONICAL_REVIEW_ACTION = "canonical_variant_or_wrong_work_review_required"
VARIANT_POLICY_ACTION = "spacing_or_canonical_variant_policy_review_required"
SOURCE_NATIVE_REVIEW_ACTION = "source_native_or_blind_review_required"


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"Expected JSON object at {path}:{line_no}")
            rows.append(payload)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _counter_to_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _split_csv(value: str | None) -> set[str] | None:
    if value is None:
        return None
    parts = {part.strip() for part in value.split(",") if part.strip()}
    return parts or None


def _actions(row: dict[str, Any]) -> list[str]:
    value = row.get("actions") or []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _row_matches(
    row: dict[str, Any],
    *,
    priorities: set[str] | None,
    labels: set[str] | None,
    actions: set[str] | None,
) -> bool:
    if priorities is not None and str(row.get("priority")) not in priorities:
        return False
    if labels is not None and str(row.get("review_label")) not in labels:
        return False
    if actions is not None and not actions.intersection(_actions(row)):
        return False
    return True


def _lanes_for(row: dict[str, Any]) -> list[str]:
    actions = set(_actions(row))
    label = str(row.get("review_label") or "")
    lanes: list[str] = []
    if SOURCE_NATIVE_REVIEW_ACTION in actions:
        lanes.append("source_native_or_blind_review")
    if label == "REPROCESS" and RUNTIME_REPROCESS_ACTION in actions:
        lanes.append("runtime_repair_replay")
    if SEARCH_REPLAY_ACTION in actions:
        lanes.append("search_replay_required")
    if CANONICAL_REVIEW_ACTION in actions:
        lanes.append("source_native_or_blind_canonical_review")
    if VARIANT_POLICY_ACTION in actions:
        lanes.append("canonical_variant_policy_review")
    if not lanes:
        lanes.append("manual_review")
    return lanes


def _dispatch_lane(row: dict[str, Any]) -> str:
    label = str(row.get("review_label") or "")
    lanes = _lanes_for(row)
    if "source_native_or_blind_review" in lanes:
        return "source_native_or_blind_review"
    if label == "HOLD" and "canonical_variant_policy_review" in lanes:
        return "canonical_variant_policy_review"
    if label == "HOLD":
        return "source_native_or_blind_review"
    if label == "REPROCESS" and "search_replay_required" in lanes:
        return "runtime_repair_with_search_replay"
    if label == "REPROCESS":
        return "runtime_repair_without_search_replay"
    return "manual_review"


def _source_input_row(source: dict[str, Any], queue_row: dict[str, Any], batch_id: str) -> dict[str, Any]:
    keep_keys = [
        "post_id",
        "url",
        "gallery_id",
        "title",
        "content",
        "content_blocks",
        "image_urls",
        "image_count",
        "comments",
        "comments_raw",
        "comment_metadata",
        "comment_context_lines",
        "comment_dialogue_context_lines",
        "author",
        "post_author",
        "ip",
        "author_ip",
        "post_ip",
        "created_at",
    ]
    out = {key: source.get(key) for key in keep_keys if key in source}
    out["_loop_action_batch"] = {
        "batch_id": batch_id,
        "post_id": queue_row.get("post_id"),
        "expected_title": queue_row.get("expected_title"),
        "actual_title_before_batch": queue_row.get("actual_title"),
        "actions": _actions(queue_row),
        "priority": queue_row.get("priority"),
        "review_label": queue_row.get("review_label"),
        "dispatch_lane": queue_row.get("dispatch_lane"),
        "approval_state": "runtime_replay_required_not_approval",
        "close_condition": queue_row.get("close_condition"),
    }
    return out


def build_action_batch(
    queue: dict[str, Any],
    *,
    generated_at: str | None = None,
    batch_id: str = "action_queue_batch",
    priorities: set[str] | None = None,
    labels: set[str] | None = None,
    actions: set[str] | None = None,
) -> dict[str, Any]:
    rows = queue.get("rows") or []
    if not isinstance(rows, list):
        raise ValueError("queue.rows must be a list")

    selected: list[dict[str, Any]] = []
    validation_issues: list[dict[str, Any]] = []
    label_counts: Counter[str] = Counter()
    priority_counts: Counter[str] = Counter()
    owner_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    lane_counts: Counter[str] = Counter()
    dispatch_counts: Counter[str] = Counter()
    audit_counts: Counter[str] = Counter()
    lane_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        if not isinstance(row, dict):
            validation_issues.append({"code": "non_object_queue_row"})
            continue
        if not _row_matches(row, priorities=priorities, labels=labels, actions=actions):
            continue
        lanes = _lanes_for(row)
        dispatch_lane = _dispatch_lane(row)
        entry = {
            **row,
            "batch_lanes": lanes,
            "dispatch_lane": dispatch_lane,
            "runtime_input_eligible": (
                str(row.get("review_label")) == "REPROCESS"
                and RUNTIME_REPROCESS_ACTION in _actions(row)
            ),
            "source_native_review_required": SOURCE_NATIVE_REVIEW_ACTION in _actions(row)
            or str(row.get("review_label")) == "HOLD",
        }
        selected.append(entry)
        label_counts[str(entry.get("review_label"))] += 1
        priority_counts[str(entry.get("priority"))] += 1
        owner_counts[str(entry.get("owner_mode"))] += 1
        audit_counts[str(entry.get("audit_status"))] += 1
        dispatch_counts[dispatch_lane] += 1
        for action in _actions(entry):
            action_counts[action] += 1
        for lane in lanes:
            lane_counts[lane] += 1
            lane_groups[lane].append(entry)

    action_groups: list[dict[str, Any]] = []
    for lane in sorted(lane_groups):
        group_rows = lane_groups[lane]
        action_groups.append(
            {
                "lane": lane,
                "row_count": len(group_rows),
                "label_counts": _counter_to_dict(Counter(str(item.get("review_label")) for item in group_rows)),
                "priority_counts": _counter_to_dict(Counter(str(item.get("priority")) for item in group_rows)),
                "dispatch_lane_counts": _counter_to_dict(Counter(str(item.get("dispatch_lane")) for item in group_rows)),
                "post_ids": [item.get("post_id") for item in group_rows],
                "sample_rows": group_rows[:8],
            }
        )

    source_summary = queue.get("summary") or {}
    return {
        "report_type": "action_queue_batch",
        "batch_id": batch_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_queue_id": queue.get("queue_id"),
        "filter": {
            "priorities": sorted(priorities) if priorities else None,
            "labels": sorted(labels) if labels else None,
            "actions": sorted(actions) if actions else None,
        },
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "summary": {
            "source_queue_rows": source_summary.get("action_queue_rows", len(rows)),
            "selected_rows": len(selected),
            "runtime_input_candidate_rows": sum(1 for row in selected if row.get("runtime_input_eligible") is True),
            "source_native_review_rows": sum(1 for row in selected if row.get("source_native_review_required") is True),
            "search_replay_required_rows": lane_counts.get("search_replay_required", 0),
            "label_counts": _counter_to_dict(label_counts),
            "priority_counts": _counter_to_dict(priority_counts),
            "owner_mode_counts": _counter_to_dict(owner_counts),
            "audit_status_counts": _counter_to_dict(audit_counts),
            "action_counts": _counter_to_dict(action_counts),
            "lane_counts": _counter_to_dict(lane_counts),
            "dispatch_lane_counts": _counter_to_dict(dispatch_counts),
            "validation_issue_count": len(validation_issues),
        },
        "validation_issues": validation_issues,
        "action_groups": action_groups,
        "execution_contract": test_run_execution_contract(len(selected)),
        "rows": selected,
        "approval_boundary": {
            "batch_generation_is_not_approval": True,
            "runtime_input_generation_is_not_runtime_approval": True,
            "source_native_packet_generation_is_not_review_completion": True,
            "completion_gate": "full375 collateral GO + full_scan path",
        },
    }


def build_runtime_input(
    batch: dict[str, Any],
    source_rows: list[dict[str, Any]],
    *,
    source_jsonl: Path,
    output_jsonl: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_index = {str(row.get("post_id")): row for row in source_rows if row.get("post_id") is not None}
    eligible_rows = [
        row
        for row in batch.get("rows") or []
        if isinstance(row, dict) and row.get("runtime_input_eligible") is True
    ]
    missing_post_ids: list[Any] = []
    input_rows: list[dict[str, Any]] = []
    for row in eligible_rows:
        source = source_index.get(str(row.get("post_id")))
        if source is None:
            missing_post_ids.append(row.get("post_id"))
            continue
        input_rows.append(_source_input_row(source, row, str(batch.get("batch_id") or "")))

    manifest = {
        "batch_id": batch.get("batch_id"),
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "source_queue_id": batch.get("source_queue_id"),
        "source_jsonl": source_jsonl.as_posix(),
        "runtime_input_candidate_rows": len(eligible_rows),
        "runtime_input_rows": len(input_rows),
        "missing_post_ids": missing_post_ids,
        "post_ids": [row.get("post_id") for row in input_rows],
        "expected_titles": [
            (row.get("_loop_action_batch") or {}).get("expected_title")
            for row in input_rows
        ],
        "output_jsonl": output_jsonl.as_posix() if output_jsonl else None,
        "execution_contract": test_run_execution_contract(len(input_rows)),
        "gate": {
            "runtime_input_generation": "GO" if not missing_post_ids else "NO-GO",
            "runtime_replay_after_input": "NOT_RUN_AFTER_INPUT",
            "semantic_quality": "REVIEW-LOCKED",
            "full_scan_approval": False,
            "approval_boundary": "input generation is not runtime approval",
        },
    }
    return input_rows, manifest


def build_review_packet(batch: dict[str, Any]) -> dict[str, Any]:
    review_rows = [
        {
            "post_id": row.get("post_id"),
            "priority": row.get("priority"),
            "review_label": row.get("review_label"),
            "dispatch_lane": row.get("dispatch_lane"),
            "audit_status": row.get("audit_status"),
            "expected_title": row.get("expected_title"),
            "actual_title": row.get("actual_title"),
            "actual_url": row.get("actual_url"),
            "actions": row.get("actions") or [],
            "reason_codes": row.get("reason_codes") or [],
            "evidence_refs": row.get("evidence_refs") or [],
            "review_task": (
                "정답 title variant인지 wrong-work인지 source-native 또는 blind judge로 판정한다. "
                "판정 전 promotion hard-hold를 완화하지 않는다."
            ),
        }
        for row in batch.get("rows") or []
        if isinstance(row, dict) and row.get("source_native_review_required") is True
    ]
    return {
        "report_type": "source_native_or_blind_review_packet",
        "packet_id": f"{batch.get('batch_id')}_hold_review_packet",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "source_batch_id": batch.get("batch_id"),
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "review_rows": len(review_rows),
            "priority_counts": _counter_to_dict(Counter(str(row.get("priority")) for row in review_rows)),
            "dispatch_lane_counts": _counter_to_dict(Counter(str(row.get("dispatch_lane")) for row in review_rows)),
            "audit_status_counts": _counter_to_dict(Counter(str(row.get("audit_status")) for row in review_rows)),
        },
        "rows": review_rows,
        "approval_boundary": {
            "packet_generation_is_not_review_completion": True,
            "hard_hold_relaxation_requires_review_verdict": True,
        },
    }


def write_markdown(batch: dict[str, Any], path: Path) -> None:
    summary = batch["summary"]
    execution_contract = batch.get("execution_contract") or {}
    dashboard_contract = execution_contract.get("dashboard_contract") or {}
    lines = [
        f"# {batch.get('batch_id')}",
        "",
        "## 요약",
        "",
        f"- source_queue_id: `{batch.get('source_queue_id')}`",
        f"- gate: `{batch.get('gate')}`",
        f"- selected_rows: `{summary.get('selected_rows')}`",
        f"- runtime_input_candidate_rows: `{summary.get('runtime_input_candidate_rows')}`",
        f"- source_native_review_rows: `{summary.get('source_native_review_rows')}`",
        f"- search_replay_required_rows: `{summary.get('search_replay_required_rows')}`",
        f"- label_counts: `{summary.get('label_counts')}`",
        f"- priority_counts: `{summary.get('priority_counts')}`",
        f"- dispatch_lane_counts: `{summary.get('dispatch_lane_counts')}`",
        f"- audit_status_counts: `{summary.get('audit_status_counts')}`",
        f"- validation_issue_count: `{summary.get('validation_issue_count')}`",
        "- approval: `false`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "",
        "## 테스트런 실행 계약",
        "",
        f"- policy: `{execution_contract.get('policy')}`",
        f"- row_count: `{execution_contract.get('row_count')}`",
        f"- requested_parallel: `{execution_contract.get('requested_parallel')}`",
        f"- expected_effective_parallel: `{execution_contract.get('expected_effective_parallel')}`",
        f"- required_flags: `{execution_contract.get('required_flags')}`",
        f"- forbidden_flags: `{execution_contract.get('forbidden_flags')}`",
        f"- dashboard_policy: `{dashboard_contract.get('dashboard_policy')}`",
        f"- dashboard_url: `{dashboard_contract.get('dashboard_url')}`",
        f"- dashboard_gate: `{execution_contract.get('dashboard_gate')}`",
        "- Dashboard는 진행 확인 도구이며 semantic/full_scan approval 근거가 아니다.",
        "",
        "## 승인 경계",
        "",
        "- 이 batch는 실행 순서를 정한 산출물이며 approval이 아니다.",
        "- `runtime_input_candidate_rows`는 입력 생성 후보일 뿐 runtime replay 결과가 아니다.",
        "- `HOLD`/`INFO_MISSING` 행은 source-native/blind review 전까지 hard-hold 완화 대상이 아니다.",
        "- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.",
        "",
        "## 처리 lane",
        "",
    ]
    for group in batch.get("action_groups") or []:
        sample = ", ".join(str(post_id) for post_id in group.get("post_ids", [])[:12])
        lines.extend(
            [
                f"### {group.get('lane')}",
                "",
                f"- row_count: `{group.get('row_count')}`",
                f"- label_counts: `{group.get('label_counts')}`",
                f"- priority_counts: `{group.get('priority_counts')}`",
                f"- dispatch_lane_counts: `{group.get('dispatch_lane_counts')}`",
                f"- sample_post_ids: `{sample}`",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    while lines and lines[-1] == "":
        lines.pop()
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_review_packet_markdown(packet: dict[str, Any], path: Path) -> None:
    summary = packet["summary"]
    lines = [
        f"# {packet.get('packet_id')}",
        "",
        "## 요약",
        "",
        f"- source_batch_id: `{packet.get('source_batch_id')}`",
        f"- review_rows: `{summary.get('review_rows')}`",
        f"- priority_counts: `{summary.get('priority_counts')}`",
        f"- dispatch_lane_counts: `{summary.get('dispatch_lane_counts')}`",
        f"- audit_status_counts: `{summary.get('audit_status_counts')}`",
        "- approval: `false`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "",
        "## Review rows",
        "",
    ]
    for row in packet.get("rows") or []:
        lines.extend(
            [
                f"### post_id `{row.get('post_id')}`",
                "",
                f"- priority: `{row.get('priority')}`",
                f"- dispatch_lane: `{row.get('dispatch_lane')}`",
                f"- audit_status: `{row.get('audit_status')}`",
                f"- expected_title: `{row.get('expected_title')}`",
                f"- actual_title: `{row.get('actual_title')}`",
                f"- actions: `{row.get('actions')}`",
                "- review_task: 정답 title variant인지 wrong-work인지 source-native 또는 blind judge로 판정한다.",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    while lines and lines[-1] == "":
        lines.pop()
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a filtered batch from an action queue.")
    parser.add_argument("--queue", required=True, type=Path)
    parser.add_argument("--batch-id", default="action_queue_batch")
    parser.add_argument("--priorities", default=None)
    parser.add_argument("--labels", default=None)
    parser.add_argument("--actions", default=None)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--source-jsonl", type=Path, default=None)
    parser.add_argument("--runtime-input-jsonl", type=Path, default=None)
    parser.add_argument("--runtime-manifest-json", type=Path, default=None)
    parser.add_argument("--review-packet-json", type=Path, default=None)
    parser.add_argument("--review-packet-md", type=Path, default=None)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    batch = build_action_batch(
        load_json(args.queue),
        batch_id=args.batch_id,
        priorities=_split_csv(args.priorities),
        labels=_split_csv(args.labels),
        actions=_split_csv(args.actions),
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(batch, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    write_markdown(batch, args.output_md)

    if args.source_jsonl or args.runtime_input_jsonl or args.runtime_manifest_json:
        if not (args.source_jsonl and args.runtime_input_jsonl and args.runtime_manifest_json):
            raise ValueError("--source-jsonl, --runtime-input-jsonl, and --runtime-manifest-json must be passed together")
        runtime_rows, manifest = build_runtime_input(
            batch,
            load_jsonl(args.source_jsonl),
            source_jsonl=args.source_jsonl,
            output_jsonl=args.runtime_input_jsonl,
        )
        write_jsonl(args.runtime_input_jsonl, runtime_rows)
        args.runtime_manifest_json.parent.mkdir(parents=True, exist_ok=True)
        args.runtime_manifest_json.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        if args.fail_on_validation_issue and manifest["missing_post_ids"]:
            return 1

    if args.review_packet_json or args.review_packet_md:
        if not (args.review_packet_json and args.review_packet_md):
            raise ValueError("--review-packet-json and --review-packet-md must be passed together")
        packet = build_review_packet(batch)
        args.review_packet_json.parent.mkdir(parents=True, exist_ok=True)
        args.review_packet_json.write_text(
            json.dumps(packet, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        write_review_packet_markdown(packet, args.review_packet_md)

    if args.fail_on_validation_issue and batch["summary"]["validation_issue_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
