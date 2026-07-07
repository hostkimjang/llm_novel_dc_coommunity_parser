from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from tools.test_run_dashboard_policy import test_run_execution_contract
except ModuleNotFoundError:  # direct script execution: python tools/build_residual_p0_contract_queue.py
    from test_run_dashboard_policy import test_run_execution_contract


SHARED_GATE_LANE = "shared_gate_restore_contract_review"
CANDIDATE_SET_LANE = "candidate_set_rebuild_review"
SOURCE_NATIVE_LANE = "source_native_or_blind_review"
NATIVE_WEB_LANE = "native_web_image_evidence_review"
NO_PUBLISH_LANE = "no_publish_guard_review"
SOURCE_NATIVE_REVIEW_ACTION = "source_native_or_blind_review_required"
SHARED_GATE_ACTION = "shared_promotion_gate_wiring_required"
SAFE_LOSS_RESTORE_ACTION = "repair_safe_loss_restore_supported_title"
OFFICIAL_REF_MARKERS = (
    "novelpia.com/novel/",
    "novel.munpia.com/",
    "m.munpia.com/novel/detail/",
    "mm.munpia.com/novel/detail/",
    "page.kakao.com/content/",
    "ridibooks.com/books/",
    "series.naver.com/novel/detail.series",
)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value or "").strip()


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("input batch must contain rows list")
    return [row for row in rows if isinstance(row, dict)]


def _actions(row: dict[str, Any]) -> set[str]:
    return {_string(item) for item in _as_list(row.get("actions")) if _string(item)}


def _batch_lanes(row: dict[str, Any]) -> set[str]:
    lanes = {_string(item) for item in _as_list(row.get("batch_lanes")) if _string(item)}
    dispatch_lane = _string(row.get("dispatch_lane"))
    if dispatch_lane:
        lanes.add(dispatch_lane)
    return lanes


def _counter_to_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _official_refs(row: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for item in _as_list(row.get("evidence_refs")):
        text = _string(item)
        lowered = text.lower()
        if text and any(marker in lowered for marker in OFFICIAL_REF_MARKERS) and text not in seen:
            refs.append(text)
            seen.add(text)
    return refs


def _contract_bucket(row: dict[str, Any], official_refs: list[str]) -> str:
    dispatch_lane = _string(row.get("dispatch_lane"))
    lanes = _batch_lanes(row)
    actions = _actions(row)
    if dispatch_lane == SOURCE_NATIVE_LANE or SOURCE_NATIVE_REVIEW_ACTION in actions or row.get("review_label") == "INFO_MISSING":
        return "source_native_or_blind_info_missing_review"
    if dispatch_lane == CANDIDATE_SET_LANE:
        return "candidate_set_rebuild_required_before_publish"
    if dispatch_lane == NATIVE_WEB_LANE and (SHARED_GATE_LANE in lanes or SHARED_GATE_ACTION in actions):
        return "shared_gate_restore_requires_native_web_review"
    if dispatch_lane == NO_PUBLISH_LANE and (SHARED_GATE_LANE in lanes or SHARED_GATE_ACTION in actions):
        return "shared_gate_restore_requires_no_publish_guard"
    if dispatch_lane == SHARED_GATE_LANE or SAFE_LOSS_RESTORE_ACTION in actions or SHARED_GATE_ACTION in actions:
        if official_refs:
            return "shared_gate_restore_contract_ready_with_official_url"
        return "shared_gate_restore_requires_official_url_enrichment"
    if dispatch_lane == NATIVE_WEB_LANE:
        return "native_web_image_evidence_review"
    if dispatch_lane == NO_PUBLISH_LANE:
        return "no_publish_guard_review"
    return "manual_contract_review"


def _next_action(bucket: str) -> str:
    return {
        "shared_gate_restore_contract_ready_with_official_url": (
            "shared promotion gate contract plan에 통과시킨 뒤 projection과 full375 collateral로 재검증한다."
        ),
        "shared_gate_restore_requires_official_url_enrichment": (
            "공식 detail URL을 후보 ledger에 보존한 뒤에만 shared gate restore contract 후보로 승격한다."
        ),
        "shared_gate_restore_requires_native_web_review": (
            "native web/image 근거를 먼저 확인하고, 이미지/플랫폼 URL 선호가 정리되기 전 publish를 금지한다."
        ),
        "shared_gate_restore_requires_no_publish_guard": (
            "merchandise/emoticon 또는 no-publish guard를 먼저 판정하고, guard가 풀리기 전 publish를 금지한다."
        ),
        "candidate_set_rebuild_required_before_publish": (
            "현재 후보셋이 source-supported title을 담지 못하므로 후보셋 재구성 전 publish와 runtime replay를 금지한다."
        ),
        "source_native_or_blind_info_missing_review": (
            "source-native 또는 blind judge로 정답성을 확정하기 전 hard-hold 완화와 safe-loss 해소 선언을 금지한다."
        ),
        "native_web_image_evidence_review": "native web/image 증거를 먼저 확정한다.",
        "no_publish_guard_review": "no-publish guard를 먼저 확정한다.",
    }.get(bucket, "수동 계약 검토가 필요하다.")


def _queue_row(row: dict[str, Any]) -> dict[str, Any]:
    official_refs = _official_refs(row)
    bucket = _contract_bucket(row, official_refs)
    dispatch_lane = _string(row.get("dispatch_lane"))
    return {
        "post_id": row.get("post_id"),
        "triage_bucket": row.get("triage_bucket"),
        "priority": row.get("priority"),
        "review_label": row.get("review_label"),
        "dispatch_lane": dispatch_lane,
        "batch_lanes": sorted(_batch_lanes(row)),
        "contract_bucket": bucket,
        "next_action_ko": _next_action(bucket),
        "target_title": row.get("selected_title"),
        "selected_option_id": row.get("selected_option_id"),
        "source_native_verdict": row.get("source_native_verdict"),
        "evidence_grade": row.get("evidence_grade"),
        "official_support_refs": official_refs,
        "official_support_ref_count": len(official_refs),
        "actions": row.get("actions") or [],
        "runtime_replay_allowed": False,
        "promotion_hard_hold_relaxation_allowed": False,
        "full375_recheck_required": True,
        "full_scan_approval": False,
        "rationale_ko": row.get("rationale_ko"),
        "evidence_refs": row.get("evidence_refs") or [],
    }


def build_contract_queue(
    batch: dict[str, Any],
    *,
    queue_id: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    rows = [_queue_row(row) for row in _rows(batch)]
    validation_issues: list[dict[str, Any]] = []
    for row in rows:
        if row.get("post_id") in (None, ""):
            validation_issues.append({"issue": "missing_post_id", "row": row})
        if row.get("runtime_replay_allowed"):
            validation_issues.append({"issue": "runtime_replay_allowed_before_contract", "post_id": row.get("post_id")})
        if row.get("contract_bucket") == "shared_gate_restore_contract_ready_with_official_url" and not row.get(
            "official_support_refs"
        ):
            validation_issues.append({"issue": "ready_restore_missing_official_ref", "post_id": row.get("post_id")})

    bucket_counts = Counter(_string(row.get("contract_bucket")) for row in rows)
    dispatch_counts = Counter(_string(row.get("dispatch_lane")) for row in rows)
    label_counts = Counter(_string(row.get("review_label")) for row in rows)
    priority_counts = Counter(_string(row.get("priority")) for row in rows)
    grade_counts = Counter(_string(row.get("evidence_grade")) for row in rows)
    action_counts: Counter[str] = Counter()
    for row in rows:
        for action in _as_list(row.get("actions")):
            action_counts[_string(action)] += 1

    groups: list[dict[str, Any]] = []
    rows_by_bucket: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        rows_by_bucket.setdefault(_string(row.get("contract_bucket")), []).append(row)
    for bucket in sorted(rows_by_bucket):
        group_rows = rows_by_bucket[bucket]
        groups.append(
            {
                "contract_bucket": bucket,
                "row_count": len(group_rows),
                "post_ids": [row.get("post_id") for row in group_rows],
                "dispatch_lane_counts": _counter_to_dict(Counter(_string(row.get("dispatch_lane")) for row in group_rows)),
                "official_support_ref_rows": sum(1 for row in group_rows if row.get("official_support_ref_count")),
                "runtime_replay_allowed_rows": 0,
                "next_action_ko": _next_action(bucket),
            }
        )

    return {
        "report_type": "residual_p0_contract_queue",
        "queue_id": queue_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_batch_id": batch.get("batch_id"),
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "summary": {
            "source_batch_rows": len(_rows(batch)),
            "contract_queue_rows": len(rows),
            "runtime_replay_allowed_rows": 0,
            "shared_gate_restore_clean_lane_rows": dispatch_counts.get(SHARED_GATE_LANE, 0),
            "shared_gate_restore_ready_with_official_url_rows": bucket_counts.get(
                "shared_gate_restore_contract_ready_with_official_url", 0
            ),
            "shared_gate_restore_official_url_enrichment_rows": bucket_counts.get(
                "shared_gate_restore_requires_official_url_enrichment", 0
            ),
            "shared_gate_restore_precondition_review_rows": (
                bucket_counts.get("shared_gate_restore_requires_native_web_review", 0)
                + bucket_counts.get("shared_gate_restore_requires_no_publish_guard", 0)
            ),
            "candidate_set_rebuild_required_rows": bucket_counts.get(
                "candidate_set_rebuild_required_before_publish", 0
            ),
            "source_native_or_blind_info_missing_rows": bucket_counts.get(
                "source_native_or_blind_info_missing_review", 0
            ),
            "validation_issue_count": len(validation_issues),
            "contract_bucket_counts": _counter_to_dict(bucket_counts),
            "dispatch_lane_counts": _counter_to_dict(dispatch_counts),
            "label_counts": _counter_to_dict(label_counts),
            "priority_counts": _counter_to_dict(priority_counts),
            "evidence_grade_counts": _counter_to_dict(grade_counts),
            "action_counts": _counter_to_dict(action_counts),
            "completion_gate": "full375 collateral GO + full_scan path",
        },
        "execution_contract": test_run_execution_contract(len(rows)),
        "validation_issues": validation_issues,
        "contract_groups": groups,
        "rows": rows,
        "approval_boundary": {
            "contract_queue_generation_is_not_approval": True,
            "runtime_replay_allowed": False,
            "dashboard_is_progress_view_not_approval": True,
            "full375_collateral_remains_no_go": True,
            "full_scan_approval": False,
        },
    }


def write_markdown(queue: dict[str, Any], path: Path) -> None:
    summary = queue["summary"]
    execution_contract = queue.get("execution_contract") or {}
    dashboard_contract = execution_contract.get("dashboard_contract") or {}
    lines = [
        f"# {queue.get('queue_id')}",
        "",
        "Loop581 P0 residual 19건을 새 runtime 없이 계약/검토 lane으로 재분해한 산출물이다. "
        "이 문서는 residual 실행 허가나 full_scan approval이 아니다.",
        "",
        "## 요약",
        "",
        f"- source_batch_id: `{queue.get('source_batch_id')}`",
        f"- gate: `{queue.get('gate')}`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "- full_scan_approval: `false`",
        f"- contract_queue_rows: `{summary.get('contract_queue_rows')}`",
        f"- runtime_replay_allowed_rows: `{summary.get('runtime_replay_allowed_rows')}`",
        f"- shared_gate_restore_clean_lane_rows: `{summary.get('shared_gate_restore_clean_lane_rows')}`",
        f"- shared_gate_restore_ready_with_official_url_rows: `{summary.get('shared_gate_restore_ready_with_official_url_rows')}`",
        f"- shared_gate_restore_official_url_enrichment_rows: `{summary.get('shared_gate_restore_official_url_enrichment_rows')}`",
        f"- shared_gate_restore_precondition_review_rows: `{summary.get('shared_gate_restore_precondition_review_rows')}`",
        f"- candidate_set_rebuild_required_rows: `{summary.get('candidate_set_rebuild_required_rows')}`",
        f"- source_native_or_blind_info_missing_rows: `{summary.get('source_native_or_blind_info_missing_rows')}`",
        f"- validation_issue_count: `{summary.get('validation_issue_count')}`",
        f"- contract_bucket_counts: `{summary.get('contract_bucket_counts')}`",
        "",
        "## 테스트런 실행 계약",
        "",
        f"- policy: `{execution_contract.get('policy')}`",
        f"- requested_parallel: `{execution_contract.get('requested_parallel')}`",
        f"- expected_effective_parallel: `{execution_contract.get('expected_effective_parallel')}`",
        f"- forbidden_flags: `{execution_contract.get('forbidden_flags')}`",
        f"- dashboard_policy: `{dashboard_contract.get('dashboard_policy')}`",
        f"- dashboard_url: `{dashboard_contract.get('dashboard_url')}`",
        f"- dashboard_gate: `{execution_contract.get('dashboard_gate')}`",
        "- Dashboard는 진행 확인 도구이며 semantic/full_scan approval 근거가 아니다.",
        "",
        "## 처리 bucket",
        "",
    ]
    for group in queue.get("contract_groups") or []:
        sample = ", ".join(str(post_id) for post_id in group.get("post_ids", [])[:12])
        lines.extend(
            [
                f"### {group.get('contract_bucket')}",
                "",
                f"- row_count: `{group.get('row_count')}`",
                f"- post_ids: `{sample}`",
                f"- dispatch_lane_counts: `{group.get('dispatch_lane_counts')}`",
                f"- official_support_ref_rows: `{group.get('official_support_ref_rows')}`",
                f"- runtime_replay_allowed_rows: `{group.get('runtime_replay_allowed_rows')}`",
                f"- next_action: {group.get('next_action_ko')}",
                "",
            ]
        )
    lines.extend(
        [
            "## 승인 경계",
            "",
            "- 공식 detail URL이 없는 shared-gate restore 행은 publish contract 후보가 아니라 URL 보존/보강 대상이다.",
            "- native web/image 또는 no-publish guard가 붙은 행은 해당 사전 검토가 끝나기 전 shared-gate restore로 승격하지 않는다.",
            "- INFO_MISSING 행은 source-native/blind judge 판정 전 hard-hold 완화 대상이 아니다.",
            "- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a residual P0 contract queue without starting runtime replay.")
    parser.add_argument("--input-batch", required=True, type=Path)
    parser.add_argument("--queue-id", default="loop582_residual_p0_contract_queue")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    queue = build_contract_queue(load_json(args.input_batch), queue_id=args.queue_id)
    write_json(args.output_json, queue)
    write_markdown(queue, args.output_md)
    print(json.dumps({"gate": queue["gate"], "summary": queue["summary"]}, ensure_ascii=False, indent=2))
    if args.fail_on_validation_issue and queue.get("validation_issues"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
