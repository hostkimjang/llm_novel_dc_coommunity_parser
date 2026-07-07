from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_B1_LANES = {
    "B1_different_candidate_alignment_review",
    "B1_related_candidate_alignment_review",
    "B1_missing_candidate_alignment_review",
}

CANONICAL_RELEASE_GATE = "BLOCKED_UNTIL_CANONICAL_CANDIDATE_RECHECK"
CANONICAL_RECHECK_ACTION = "current_projection_candidate_recheck_required"
MISSING_CANDIDATE_LANE = "B1_missing_candidate_alignment_review"

VERDICT_OPTIONS = [
    "EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED",
    "CURRENT_PROJECTION_CANDIDATE_CONFIRMED",
    "RELATED_CANONICAL_VARIANT_CONFIRMED",
    "WRONG_OR_UNRELATED_CANDIDATE",
    "INSUFFICIENT_EVIDENCE_HOLD",
]

MISSING_CANDIDATE_VERDICT_OPTIONS = [
    "EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED",
    "INSUFFICIENT_EVIDENCE_HOLD",
]


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, raw_line in enumerate(f, start=1):
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            payload = json.loads(raw_line)
            if not isinstance(payload, dict):
                raise ValueError(f"Expected JSON object at {path}:{line_no}")
            rows.append(payload)
    return rows


def load_result_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("results", "rows", "items", "data"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    raise ValueError(f"Expected result row list: {path}")


def _split_csv(value: str | None) -> set[str] | None:
    if value is None:
        return None
    parts = {part.strip() for part in value.split(",") if part.strip()}
    return parts or None


def _counter_to_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _actions(row: dict[str, Any]) -> list[str]:
    value = row.get("actions") or []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return []


def _title_from_row(row: dict[str, Any]) -> Any:
    return row.get("selected_title") or row.get("expected_title") or row.get("projected_title")


def _candidate_title(candidate: Any) -> Any:
    if not isinstance(candidate, dict):
        return None
    return candidate.get("official_title") or candidate.get("blocked_official_title")


def _candidate_url(candidate: Any) -> Any:
    if not isinstance(candidate, dict):
        return None
    return candidate.get("official_url") or candidate.get("blocked_official_url")


def _post_id_key(value: Any) -> str:
    return str(value or "").strip()


def _index_rows(rows: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        result = row.get("result")
        source = result if isinstance(result, dict) else row
        post_id = _post_id_key(source.get("post_id"))
        if post_id and post_id not in indexed:
            indexed[post_id] = source
    return indexed


def _preview_lines(value: Any, *, limit: int = 6, max_chars: int = 240) -> list[str]:
    if value is None:
        return []
    raw_items = value if isinstance(value, list) else [value]
    out: list[str] = []
    for item in raw_items:
        if isinstance(item, dict):
            text = item.get("text") or item.get("content") or item.get("body") or item.get("title")
        else:
            text = item
        text = str(text or "").strip()
        if not text:
            continue
        if len(text) > max_chars:
            text = text[: max_chars - 3].rstrip() + "..."
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _compact_projection_followup(source: dict[str, Any]) -> dict[str, Any] | None:
    followup = source.get("_loop_projection_followup")
    if not isinstance(followup, dict):
        return None
    gate = followup.get("promotion_gate_state")
    trace = followup.get("publish_contract_trace")
    gate_scope = gate.get("scope") if isinstance(gate, dict) and isinstance(gate.get("scope"), dict) else {}
    trace_scope = trace.get("scope_state") if isinstance(trace, dict) and isinstance(trace.get("scope_state"), dict) else {}
    return {
        "queue_id": followup.get("queue_id"),
        "source_native_verdict": followup.get("source_native_verdict"),
        "selected_title": followup.get("selected_title"),
        "projected_title": followup.get("projected_title"),
        "projected_url": followup.get("projected_url"),
        "actions": followup.get("actions") or [],
        "promotion_decision": followup.get("promotion_decision"),
        "promotion_gate_scope": gate_scope,
        "publish_contract_scope": trace_scope,
        "promotion_gate_evidence": followup.get("promotion_gate_evidence") or [],
    }


def _source_context(source: dict[str, Any] | None) -> dict[str, Any] | None:
    if not source:
        return None
    image_urls = source.get("image_urls") if isinstance(source.get("image_urls"), list) else []
    return {
        "post_title": source.get("title"),
        "post_url": source.get("url"),
        "gallery_id": source.get("gallery_id"),
        "created_at": source.get("created_at"),
        "content_preview": _preview_lines(source.get("content") or source.get("content_blocks")),
        "comment_preview": _preview_lines(source.get("comments"), limit=8),
        "comment_context_preview": _preview_lines(source.get("comment_context_lines"), limit=8),
        "comment_dialogue_context_preview": _preview_lines(source.get("comment_dialogue_context_lines"), limit=8),
        "image_count": source.get("image_count"),
        "image_urls": image_urls[:4],
        "projection_followup": _compact_projection_followup(source),
    }


def _runtime_identity(runtime_row: dict[str, Any] | None) -> dict[str, Any]:
    if not runtime_row:
        return {}
    analysis = runtime_row.get("analysis_result")
    if isinstance(analysis, dict) and isinstance(analysis.get("identity"), dict):
        return analysis["identity"]
    identity = runtime_row.get("identity")
    return identity if isinstance(identity, dict) else {}


def _runtime_context(runtime_row: dict[str, Any] | None) -> dict[str, Any] | None:
    identity = _runtime_identity(runtime_row)
    if not identity:
        return None
    promotion = identity.get("promotion_decision") if isinstance(identity.get("promotion_decision"), dict) else {}
    trace = identity.get("publish_contract_trace") if isinstance(identity.get("publish_contract_trace"), dict) else {}
    ledger = identity.get("candidate_ledger") if isinstance(identity.get("candidate_ledger"), dict) else {}
    candidate_sources = ledger.get("candidate_preservation_sources")
    if not isinstance(candidate_sources, list):
        candidate_sources = []
    return {
        "candidate_ledger_status": identity.get("candidate_ledger_status"),
        "blocked_official_title": identity.get("blocked_official_title"),
        "blocked_official_title_url": identity.get("blocked_official_title_url"),
        "title_resolution_state": identity.get("title_resolution_state"),
        "work_resolution": identity.get("work_resolution"),
        "promotion_decision_status": promotion.get("status"),
        "promotion_decision_reason_codes": promotion.get("reason_codes") or [],
        "publish_contract_scope": trace.get("scope_state"),
        "candidate_titles_preview": _preview_lines(ledger.get("title_candidates"), limit=12),
        "candidate_preservation_sources_preview": candidate_sources[:6],
        "reason_preview": _preview_lines(identity.get("reason_lines") or identity.get("reason"), limit=6),
    }


def _row_matches(row: dict[str, Any], lanes: set[str]) -> bool:
    lane = str(row.get("repair_batch_lane") or "")
    return lane in lanes


def _is_missing_candidate_lane(row: dict[str, Any]) -> bool:
    return str(row.get("repair_batch_lane") or "") == MISSING_CANDIDATE_LANE


def _validation_issues(row: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    post_id = row.get("post_id")
    candidate = row.get("current_projection_candidate")
    if row.get("runtime_release_gate") != CANONICAL_RELEASE_GATE:
        issues.append(
            {
                "code": "canonical_batch_row_without_canonical_release_gate",
                "post_id": post_id,
                "runtime_release_gate": row.get("runtime_release_gate"),
            }
        )
    if row.get("runtime_replay_allowed") is True:
        issues.append(
            {
                "code": "canonical_batch_row_runtime_replay_already_allowed",
                "post_id": post_id,
            }
        )
    if row.get("current_projection_candidate_alignment_requires_review") is not True:
        issues.append(
            {
                "code": "canonical_batch_row_not_marked_alignment_review",
                "post_id": post_id,
                "alignment_state": row.get("current_projection_candidate_alignment_state"),
            }
        )
    if CANONICAL_RECHECK_ACTION not in _actions(row):
        issues.append(
            {
                "code": "canonical_batch_row_missing_recheck_action",
                "post_id": post_id,
            }
        )
    if not _title_from_row(row):
        issues.append(
            {
                "code": "canonical_batch_row_missing_expected_source_title",
                "post_id": post_id,
            }
        )
    if not _candidate_title(candidate) and not _is_missing_candidate_lane(row):
        issues.append(
            {
                "code": "canonical_batch_row_missing_current_projection_candidate",
                "post_id": post_id,
            }
        )
    if _is_missing_candidate_lane(row) and row.get("current_projection_candidate_alignment_state") != "missing_current_projection_candidate":
        issues.append(
            {
                "code": "missing_candidate_lane_without_missing_candidate_state",
                "post_id": post_id,
                "alignment_state": row.get("current_projection_candidate_alignment_state"),
            }
        )
    return issues


def _after_verdict_contract(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED": {
            "next_state": "candidate_scrub_or_expected_title_restore_contract_required",
            "runtime_release": "blocked_until_contract_tests_pass",
        },
        "CURRENT_PROJECTION_CANDIDATE_CONFIRMED": {
            "next_state": "source_native_expectation_update_or_blind_acceptance_required",
            "runtime_release": "blocked_until_expected_contract_updated",
        },
        "RELATED_CANONICAL_VARIANT_CONFIRMED": {
            "next_state": "canonical_variant_policy_contract_required",
            "runtime_release": "blocked_until_variant_policy_tests_pass",
        },
        "WRONG_OR_UNRELATED_CANDIDATE": {
            "next_state": "current_projection_candidate_scrub_required",
            "runtime_release": "blocked_until_candidate_scrub_tests_pass",
        },
        "INSUFFICIENT_EVIDENCE_HOLD": {
            "next_state": "hard_hold_or_native_web_review_required",
            "runtime_release": "blocked_until_stronger_evidence",
        },
        "current_runtime_release_gate": row.get("runtime_release_gate"),
        "runtime_replay_allowed_before_verdict": False,
    }


def _review_row(
    row: dict[str, Any],
    *,
    source_row: dict[str, Any] | None = None,
    runtime_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate = row.get("current_projection_candidate")
    if not isinstance(candidate, dict):
        candidate = {}
    missing_candidate_lane = _is_missing_candidate_lane(row)
    out = {
        "post_id": row.get("post_id"),
        "review_lane": row.get("repair_batch_lane"),
        "canonical_review_state": "NEEDS_SOURCE_NATIVE_OR_BLIND_CANONICAL_RECHECK",
        "expected_or_source_native_title": _title_from_row(row),
        "projected_title": row.get("projected_title"),
        "current_projection_candidate_title": _candidate_title(candidate),
        "current_projection_candidate_url": _candidate_url(candidate),
        "current_projection_candidate_alignment_state": row.get("current_projection_candidate_alignment_state"),
        "current_projection_candidate_missing": missing_candidate_lane,
        "candidate_support_state": row.get("candidate_support_state"),
        "search_gate": row.get("search_gate"),
        "prior_runtime_audit_status": row.get("prior_runtime_audit_status"),
        "prior_runtime_search_status": row.get("prior_runtime_search_status"),
        "primary_repair_lane": row.get("primary_repair_lane"),
        "reason_codes": row.get("reason_codes") or [],
        "projected_reasons": row.get("projected_reasons") or [],
        "actions": _actions(row),
        "candidate_evidence_profile": {
            "source_tiers": candidate.get("candidate_source_tiers") or [],
            "source_roles": candidate.get("candidate_source_roles") or [],
            "negative_evidence": candidate.get("candidate_negative_evidence") or [],
            "metadata_source_count": candidate.get("candidate_metadata_source_count"),
            "image_title_match": candidate.get("candidate_image_title_match"),
        },
        "allowed_verdicts": MISSING_CANDIDATE_VERDICT_OPTIONS if missing_candidate_lane else VERDICT_OPTIONS,
        "review_questions": [
            (
                "current projection candidate가 누락된 이유가 후보 재구축 문제인지, expected/source-native title 자체가 "
                "packet-local 작품 근거에 맞는지 확인한다."
                if missing_candidate_lane
                else "expected/source-native title and current projection candidate 중 어느 쪽이 packet-local 작품 근거에 맞는가?"
            ),
            (
                "누락 후보 lane은 expected title 복구, hard hold, 또는 stronger native-web review 중 하나로 판정한다."
                if missing_candidate_lane
                else "둘이 같은 작품의 canonical variant 또는 alias 관계인지, 아니면 다른 작품/비작품 후보인지 확인한다."
            ),
            "official URL, raw post/comment surface, VLM/OCR direct title, verified character-work link를 분리해서 기록한다.",
        ],
        "after_verdict_contract": _after_verdict_contract(row),
        "evidence_refs": row.get("evidence_refs") or [],
        "approval_boundary": {
            "packet_generation_is_not_verdict": True,
            "canonical_recheck_is_required_before_runtime_replay": True,
            "full375_collateral_remains_no_go": True,
        },
    }
    source_context = _source_context(source_row)
    runtime_context = _runtime_context(runtime_row)
    if source_context is not None:
        out["source_context"] = source_context
    if runtime_context is not None:
        out["runtime_context"] = runtime_context
    return out


def build_canonical_recheck_batch(
    queue: dict[str, Any],
    *,
    batch_id: str = "canonical_candidate_recheck_batch",
    lanes: set[str] | None = None,
    generated_at: str | None = None,
    source_rows: list[dict[str, Any]] | None = None,
    runtime_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = queue.get("rows") or []
    if not isinstance(rows, list):
        raise ValueError("queue.rows must be a list")

    selected_lanes = lanes or set(DEFAULT_B1_LANES)
    source_index = _index_rows(source_rows)
    runtime_index = _index_rows(runtime_rows)
    selected: list[dict[str, Any]] = []
    validation_issues: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            validation_issues.append({"code": "non_object_queue_row", "index": idx})
            continue
        if not _row_matches(row, selected_lanes):
            continue
        validation_issues.extend(_validation_issues(row))
        post_id = _post_id_key(row.get("post_id"))
        selected.append(
            _review_row(
                row,
                source_row=source_index.get(post_id),
                runtime_row=runtime_index.get(post_id),
            )
        )

    lane_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in selected:
        lane_groups[str(row.get("review_lane") or "unknown")].append(row)

    groups: list[dict[str, Any]] = []
    for lane in sorted(lane_groups):
        group_rows = lane_groups[lane]
        groups.append(
            {
                "review_lane": lane,
                "row_count": len(group_rows),
                "candidate_support_state_counts": _counter_to_dict(
                    Counter(str(row.get("candidate_support_state") or "missing") for row in group_rows)
                ),
                "search_gate_counts": _counter_to_dict(
                    Counter(str(row.get("search_gate") or "missing") for row in group_rows)
                ),
                "primary_repair_lane_counts": _counter_to_dict(
                    Counter(str(row.get("primary_repair_lane") or "missing") for row in group_rows)
                ),
                "post_ids": [row.get("post_id") for row in group_rows],
                "sample_rows": group_rows[:6],
            }
        )

    source_summary = queue.get("summary") or {}
    return {
        "report_type": "canonical_candidate_recheck_batch",
        "batch_id": batch_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_queue_id": queue.get("queue_id"),
        "source_gate": queue.get("gate"),
        "selected_lanes": sorted(selected_lanes),
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "summary": {
            "source_queue_rows": source_summary.get("repair_rows", len(rows)),
            "selected_rows": len(selected),
            "verdict_required_rows": len(selected),
            "runtime_replay_allowed_rows": 0,
            "review_lane_counts": _counter_to_dict(Counter(str(row.get("review_lane") or "unknown") for row in selected)),
            "alignment_state_counts": _counter_to_dict(
                Counter(str(row.get("current_projection_candidate_alignment_state") or "missing") for row in selected)
            ),
            "candidate_support_state_counts": _counter_to_dict(
                Counter(str(row.get("candidate_support_state") or "missing") for row in selected)
            ),
            "search_gate_counts": _counter_to_dict(Counter(str(row.get("search_gate") or "missing") for row in selected)),
            "primary_repair_lane_counts": _counter_to_dict(
                Counter(str(row.get("primary_repair_lane") or "missing") for row in selected)
            ),
            "source_context_rows": sum(1 for row in selected if isinstance(row.get("source_context"), dict)),
            "runtime_context_rows": sum(1 for row in selected if isinstance(row.get("runtime_context"), dict)),
            "validation_issue_count": len(validation_issues),
        },
        "validation_issues": validation_issues,
        "review_groups": groups,
        "rows": selected,
        "approval_boundary": {
            "batch_generation_is_not_canonical_verdict": True,
            "runtime_replay_before_canonical_verdict_forbidden": True,
            "hard_hold_relaxation_requires_blind_or_source_native_verdict": True,
            "completion_gate": "full375 collateral GO + full_scan path",
        },
    }


def write_markdown(batch: dict[str, Any], path: Path) -> None:
    summary = batch["summary"]
    lines = [
        f"# {batch.get('batch_id')}",
        "",
        "## 요약",
        "",
        f"- source_queue_id: `{batch.get('source_queue_id')}`",
        f"- gate: `{batch.get('gate')}`",
        f"- selected_rows: `{summary.get('selected_rows')}`",
        f"- verdict_required_rows: `{summary.get('verdict_required_rows')}`",
        f"- runtime_replay_allowed_rows: `{summary.get('runtime_replay_allowed_rows')}`",
        f"- review_lane_counts: `{summary.get('review_lane_counts')}`",
        f"- alignment_state_counts: `{summary.get('alignment_state_counts')}`",
        f"- candidate_support_state_counts: `{summary.get('candidate_support_state_counts')}`",
        f"- search_gate_counts: `{summary.get('search_gate_counts')}`",
        f"- primary_repair_lane_counts: `{summary.get('primary_repair_lane_counts')}`",
        f"- source_context_rows: `{summary.get('source_context_rows')}`",
        f"- runtime_context_rows: `{summary.get('runtime_context_rows')}`",
        f"- validation_issue_count: `{summary.get('validation_issue_count')}`",
        "- approval: `false`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "",
        "## 승인 경계",
        "",
        "- 이 batch는 canonical verdict가 아니라 판정 입력이다.",
        "- B1 row는 source-native 또는 blind canonical review 전까지 runtime replay로 넘기지 않는다.",
        "- 판정 뒤에도 contract test와 full375 collateral 확인 전에는 full_scan approval을 열지 않는다.",
        "- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.",
        "",
        "## Review groups",
        "",
    ]
    for group in batch.get("review_groups") or []:
        post_ids = ", ".join(str(post_id) for post_id in group.get("post_ids", [])[:24])
        lines.extend(
            [
                f"### {group.get('review_lane')}",
                "",
                f"- row_count: `{group.get('row_count')}`",
                f"- candidate_support_state_counts: `{group.get('candidate_support_state_counts')}`",
                f"- search_gate_counts: `{group.get('search_gate_counts')}`",
                f"- primary_repair_lane_counts: `{group.get('primary_repair_lane_counts')}`",
                f"- post_ids: `{post_ids}`",
                "",
            ]
        )
    lines.extend(
        [
            "## 판정 옵션",
            "",
            "- `EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED`: expected/source-native title이 맞다. current projection 후보를 scrub/restore 계약으로 정리해야 한다.",
            "- `CURRENT_PROJECTION_CANDIDATE_CONFIRMED`: current projection 후보가 맞다. expected/source-native 기준 자체를 blind 근거로 갱신해야 한다.",
            "- `RELATED_CANONICAL_VARIANT_CONFIRMED`: 같은 작품의 canonical variant다. variant policy 계약 테스트가 필요하다.",
            "- `WRONG_OR_UNRELATED_CANDIDATE`: current projection 후보가 wrong-work 또는 무관 후보다. candidate scrub 계약 테스트가 필요하다.",
            "- `INSUFFICIENT_EVIDENCE_HOLD`: 증거가 부족하다. hard-hold 또는 native-web review로 남긴다.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    while lines and lines[-1] == "":
        lines.pop()
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build B1 canonical candidate recheck batch from a repair queue.")
    parser.add_argument("--queue", required=True, type=Path)
    parser.add_argument("--batch-id", default="canonical_candidate_recheck_batch")
    parser.add_argument("--lanes", default=None)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--source-jsonl", type=Path, default=None)
    parser.add_argument("--runtime-result-json", type=Path, default=None)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    batch = build_canonical_recheck_batch(
        load_json(args.queue),
        batch_id=args.batch_id,
        lanes=_split_csv(args.lanes),
        source_rows=load_jsonl(args.source_jsonl) if args.source_jsonl else None,
        runtime_rows=load_result_rows(args.runtime_result_json) if args.runtime_result_json else None,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(batch, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    write_markdown(batch, args.output_md)
    if args.fail_on_validation_issue and batch["summary"]["validation_issue_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
