from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from tools.test_run_dashboard_policy import (
        dashboard_contract,
        expected_effective_parallel,
        requested_parallel_for_test_run,
    )
except ModuleNotFoundError:
    from test_run_dashboard_policy import (  # type: ignore[no-redef]
        dashboard_contract,
        expected_effective_parallel,
        requested_parallel_for_test_run,
    )


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _counter_to_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _reason_set(row: dict[str, Any]) -> set[str]:
    reasons = row.get("projected_reasons") or []
    if not isinstance(reasons, list):
        reasons = [reasons]
    return {str(reason or "").strip() for reason in reasons if str(reason or "").strip()}


def _projected_status(row: dict[str, Any]) -> str:
    return str(row.get("projected_status") or "").strip()


def _post_id_key(value: Any) -> str:
    return str(value or "").strip()


def _prior_audit_rows(prior_runtime_expected_audit: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not prior_runtime_expected_audit:
        return {}
    rows = prior_runtime_expected_audit.get("rows") or []
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        post_id = _post_id_key(item.get("post_id"))
        if post_id:
            out[post_id] = item
    return out


def _prior_status(prior_runtime_audit: dict[str, Any] | None) -> str:
    if not prior_runtime_audit:
        return ""
    return str(prior_runtime_audit.get("audit_status") or "").strip()


def classify_projection_row(
    row: dict[str, Any],
    *,
    prior_runtime_audit: dict[str, Any] | None = None,
    prior_audit_enabled: bool = False,
) -> dict[str, Any]:
    status = _projected_status(row)
    reasons = _reason_set(row)
    exact_match = row.get("matches_source_native_title") is True
    selected_title = row.get("selected_title")
    projected_title = row.get("projected_title")
    prior_status = _prior_status(prior_runtime_audit)

    if status == "safe_resolved" and exact_match:
        if prior_status == "FAIL_RUNTIME_PROMOTION_BLOCKED":
            if row.get("projected_url"):
                return {
                    "review_label": "REPROCESS",
                    "priority": "P0",
                    "owner_mode": "RUNTIME_REPLAY_WITH_SHARED_GATE_SEED",
                    "actions": [
                        "runtime_replay_with_projection_followup_seed_required",
                        "full375_collateral_recheck_after_runtime",
                    ],
                    "rationale_ko": (
                        "Projection은 safe_resolved exact이고 official URL을 가진 shared-gate seed를 포함한다. "
                        "과거 runtime promotion_blocked 반복을 피하기 위해 projection seed를 runtime input에 보존한 뒤 replay한다."
                    ),
                    "close_condition": "projection follow-up seed가 runtime publish_contract_trace에 반영되고 같은 title/url safe_resolved를 내야 한다.",
                }
            return {
                "review_label": "REPROCESS",
                "priority": "P0",
                "owner_mode": "CODE_OR_RUNTIME_CONTRACT_REPAIR",
                "actions": [
                    "prior_runtime_promotion_block_repair_required",
                    "projection_followup_official_url_repair_required",
                    "shared_gate_runtime_block_repair_required",
                    "full375_collateral_recheck_after_repair",
                ],
                "rationale_ko": (
                    "Projection은 safe_resolved exact지만 과거 동일 계열 runtime expected-audit에서 "
                    "promotion_blocked로 실패했고 projection official URL이 없다. 같은 입력을 반복 실행하기 전에 "
                    "official URL 보강, prior reason_codes, publish_contract_trace / candidate preservation / search-blind 조건을 수리해야 한다."
                ),
                "close_condition": "prior runtime promotion_blocked 원인을 수리한 뒤 runtime replay와 full375 collateral을 다시 확인한다.",
            }
        if prior_status in {"FAIL_SAFE_RESOLVED_TITLE_MISMATCH", "FAIL_VARIANT_COMPACT_MATCH_ONLY"}:
            return {
                "review_label": "HOLD",
                "priority": "P0",
                "owner_mode": "SOURCE_NATIVE_OR_CANONICAL_REVIEW",
                "actions": [
                    "prior_runtime_title_mismatch_review_required",
                    "source_native_canonical_variant_review_required",
                    "runtime_replay_after_variant_review",
                ],
                "rationale_ko": (
                    "Projection은 safe_resolved exact지만 과거 runtime은 다른 title 또는 compact variant로 "
                    "수렴했다. 정당 variant인지 wrong-work인지 source-native/blind review로 먼저 확정한다."
                ),
                "close_condition": "variant/wrong-work 판정을 닫은 뒤에만 runtime replay 후보로 되돌린다.",
            }
        if prior_audit_enabled and prior_runtime_audit is None:
            return {
                "review_label": "HOLD",
                "priority": "P1",
                "owner_mode": "RUNTIME_AUDIT_GAP_REVIEW",
                "actions": [
                    "prior_runtime_expected_audit_missing_review_required",
                    "runtime_replay_projected_safe_resolved_exact_required",
                    "full375_collateral_recheck_after_runtime",
                ],
                "rationale_ko": (
                    "Projection은 safe_resolved exact지만 비교할 prior runtime expected-audit가 없다. "
                    "신규 runtime replay 후보로 남기되, audit gap을 명시한다."
                ),
                "close_condition": "runtime replay가 같은 title/url safe_resolved를 내고 publication contract violation이 0이어야 한다.",
            }
        return {
            "review_label": "REPROCESS",
            "priority": "P1" if prior_status == "PASS_EXACT_SAFE_RESOLVED" else "P0",
            "owner_mode": "RUNTIME_REPLAY",
            "actions": [
                "runtime_replay_projected_safe_resolved_exact_required",
                "full375_collateral_recheck_after_runtime",
            ],
            "rationale_ko": (
                "Projection은 source-native selected title과 같은 safe_resolved로 수렴했다. "
                "같은 입력 runtime replay에서 실제 publish 계약과 row 생산성을 확인해야 한다."
            ),
            "close_condition": "runtime replay가 같은 title/url safe_resolved를 내고 publication contract violation이 0이어야 한다.",
        }

    if status == "safe_resolved":
        return {
            "review_label": "HOLD",
            "priority": "P1",
            "owner_mode": "SOURCE_NATIVE_OR_CANONICAL_REVIEW",
            "actions": [
                "source_native_canonical_variant_review_required",
                "runtime_replay_after_variant_review",
            ],
            "rationale_ko": (
                f"Projection은 safe_resolved지만 source-native selected title `{selected_title}`와 "
                f"projected title `{projected_title}`가 정확히 일치하지 않는다. canonical variant인지 "
                "wrong-work인지 먼저 확인해야 한다."
            ),
            "close_condition": "source-native 또는 blind review가 title variant를 정당 해소로 확정한 뒤 runtime replay를 실행한다.",
        }

    if status == "output_consistency_lint":
        return {
            "review_label": "REPROCESS",
            "priority": "P0",
            "owner_mode": "CODE_CONTRACT_OR_LINT_REVIEW",
            "actions": [
                "output_consistency_lint_contract_followup_required",
                "publication_trace_lint_review_required",
            ],
            "rationale_ko": (
                "Projection 후에도 output_consistency_lint가 남았다. public ledger, "
                "candidate ledger, publish_contract_trace consistency를 먼저 맞춰야 한다."
            ),
            "close_condition": "lint reason이 제거되고 blocked/publish trace가 동일한 decision으로 수렴해야 한다.",
        }

    scope_or_nonwork_markers = {
        "scope_not_current_work",
        "scope_context_only",
        "row_discussion_missing",
        "nonwork",
        "nonwork_or_noise_context",
        "community_banter",
        "scope_platform_meta_nonwork",
        "non_novel_discourse",
        "missing_body_work_bridge",
        "unresolved_body_character_work_anchor",
    }
    if status == "promotion_blocked" and reasons & scope_or_nonwork_markers:
        return {
            "review_label": "HOLD",
            "priority": "P2",
            "owner_mode": "POLICY_OR_SOURCE_NATIVE_REVIEW",
            "actions": ["scope_or_nonwork_hard_hold_review_required"],
            "rationale_ko": (
                "Projection 후에도 current-work scope가 닫히지 않거나 nonwork/context-only 근거가 남았다. "
                "무리한 promotion 완화가 아니라 source-native 또는 policy review가 필요하다."
            ),
            "close_condition": "current-work direct bridge가 source-native로 확인되기 전까지 public publish를 열지 않는다.",
        }

    support_gap_markers = {
        "verified_alias_title_only_counterevidence_blocked",
        "official_url_withheld_by_title_mismatch",
        "serialized_public_identity_shared_gate_restored",
        "llm_only_sentence_candidate_pruned",
        "precision_seed_official_title_requires_review",
        "exact_alias_candidate_preserved_without_work_discussion",
        "candidate_set_rebuild_required",
        "no_candidate_title",
        "source_native_support_not_sufficient",
    }
    if status == "promotion_blocked" and reasons & support_gap_markers:
        return {
            "review_label": "REPROCESS",
            "priority": "P1",
            "owner_mode": "CODE_OR_CANDIDATE_REPAIR",
            "actions": ["shared_gate_support_gap_repair_required"],
            "rationale_ko": (
                "Projection 후에도 shared gate support gap 또는 candidate pruning/counterevidence가 남았다. "
                "direct source support, official detail support, candidate preservation을 다시 점검한다."
            ),
            "close_condition": "supported current-work candidate만 publish되고 hard negative evidence가 있으면 계속 candidate_only여야 한다.",
        }

    return {
        "review_label": "HOLD",
        "priority": "P2",
        "owner_mode": "MANUAL_REVIEW",
        "actions": ["blocked_projection_manual_review_required"],
        "rationale_ko": "Projection 후에도 promotion_blocked가 남았지만 자동 분류 marker가 부족하다. 수동 review가 필요하다.",
        "close_condition": "source-native/blind review가 publish, candidate_only, lint 중 하나로 확정해야 한다.",
    }


def build_followup_queue(
    projection: dict[str, Any],
    *,
    generated_at: str | None = None,
    queue_id: str = "projection_followup_action_queue",
    prior_runtime_expected_audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = projection.get("rows") or []
    if not isinstance(rows, list):
        raise ValueError("projection.rows must be a list")

    out_rows: list[dict[str, Any]] = []
    label_counts: Counter[str] = Counter()
    priority_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    owner_counts: Counter[str] = Counter()
    exact_counts: Counter[str] = Counter()
    prior_audit_counts: Counter[str] = Counter()
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    validation_issues: list[dict[str, Any]] = []
    prior_audit_enabled = prior_runtime_expected_audit is not None
    prior_by_post_id = _prior_audit_rows(prior_runtime_expected_audit)

    for row in rows:
        if not isinstance(row, dict):
            validation_issues.append({"code": "non_object_projection_row"})
            continue
        prior_runtime_audit = prior_by_post_id.get(_post_id_key(row.get("post_id")))
        prior_status = _prior_status(prior_runtime_audit) or "NO_PRIOR_AUDIT"
        if prior_audit_enabled:
            prior_audit_counts[prior_status] += 1
        classification = classify_projection_row(
            row,
            prior_runtime_audit=prior_runtime_audit,
            prior_audit_enabled=prior_audit_enabled,
        )
        status = _projected_status(row)
        exact_key = "match" if row.get("matches_source_native_title") is True else "mismatch"
        actions = classification["actions"]
        entry = {
            "post_id": row.get("post_id"),
            "projected_status": status,
            "review_label": classification["review_label"],
            "priority": classification["priority"],
            "owner_mode": classification["owner_mode"],
            "actions": actions,
            "selected_title": row.get("selected_title"),
            "selected_option_id": row.get("selected_option_id"),
            "source_native_verdict": row.get("source_native_verdict"),
            "projected_title": row.get("projected_title"),
            "projected_url": row.get("projected_url"),
            "before_status": row.get("before_status"),
            "before_title": row.get("before_title"),
            "before_url": row.get("before_url"),
            "prior_runtime_audit_status": None if prior_status == "NO_PRIOR_AUDIT" else prior_status,
            "prior_runtime_expected_title": (prior_runtime_audit or {}).get("expected_title"),
            "prior_runtime_actual_title": (prior_runtime_audit or {}).get("actual_title"),
            "prior_runtime_reason_codes": (prior_runtime_audit or {}).get("reason_codes") or [],
            "prior_runtime_search_status": (prior_runtime_audit or {}).get("search_status"),
            "matches_source_native_title": row.get("matches_source_native_title") is True,
            "projected_reasons": sorted(_reason_set(row)),
            "promotion_decision": row.get("promotion_decision"),
            "promotion_gate_state": row.get("promotion_gate_state"),
            "promotion_gate_evidence": row.get("promotion_gate_evidence") or [],
            "publish_contract_trace": row.get("publish_contract_trace"),
            "publish_ledger": row.get("publish_ledger"),
            "rationale_ko": classification["rationale_ko"],
            "close_condition": classification["close_condition"],
            "evidence_refs": [
                f"{projection.get('projection_id') or queue_id}#post_id={row.get('post_id')}"
            ],
        }
        out_rows.append(entry)
        label_counts[entry["review_label"]] += 1
        priority_counts[entry["priority"]] += 1
        status_counts[status] += 1
        owner_counts[entry["owner_mode"]] += 1
        exact_counts[exact_key] += 1
        for action in actions:
            action_counts[action] += 1
            groups[action].append(entry)

    action_groups: list[dict[str, Any]] = []
    for action in sorted(groups):
        group_rows = groups[action]
        action_groups.append(
            {
                "action": action,
                "row_count": len(group_rows),
                "priority_counts": _counter_to_dict(Counter(str(item["priority"]) for item in group_rows)),
                "label_counts": _counter_to_dict(Counter(str(item["review_label"]) for item in group_rows)),
                "projected_status_counts": _counter_to_dict(Counter(str(item["projected_status"]) for item in group_rows)),
                "owner_modes": _counter_to_dict(Counter(str(item["owner_mode"]) for item in group_rows)),
                "post_ids": [item["post_id"] for item in group_rows],
                "sample_rows": group_rows[:8],
            }
        )

    if projection.get("input_rows") is not None and int(projection.get("input_rows")) != len(rows):
        validation_issues.append(
            {
                "code": "projection_input_rows_mismatch",
                "expected": projection.get("input_rows"),
                "actual": len(rows),
            }
        )

    return {
        "report_type": "projection_followup_action_queue",
        "queue_id": queue_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_projection_id": projection.get("projection_id"),
        "source_projection_path": projection.get("source_projection_path"),
        "source_queue": projection.get("source_queue"),
        "source_full375_result": projection.get("source_full375_result"),
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "summary": {
            "source_rows": len(rows),
            "followup_action_queue_rows": len(out_rows),
            "label_counts": _counter_to_dict(label_counts),
            "priority_counts": _counter_to_dict(priority_counts),
            "projected_status_counts": _counter_to_dict(status_counts),
            "exact_match_counts": _counter_to_dict(exact_counts),
            "prior_runtime_audit_status_counts": _counter_to_dict(prior_audit_counts),
            "owner_mode_counts": _counter_to_dict(owner_counts),
            "action_counts": _counter_to_dict(action_counts),
            "action_group_count": len(action_groups),
            "runtime_replay_candidate_rows": action_counts.get("runtime_replay_projected_safe_resolved_exact_required", 0),
            "runtime_seed_replay_candidate_rows": action_counts.get("runtime_replay_with_projection_followup_seed_required", 0),
            "variant_review_rows": action_counts.get("source_native_canonical_variant_review_required", 0),
            "lint_followup_rows": action_counts.get("output_consistency_lint_contract_followup_required", 0),
            "still_blocked_rows": status_counts.get("promotion_blocked", 0),
            "validation_issue_count": len(validation_issues),
        },
        "validation_issues": validation_issues,
        "action_groups": action_groups,
        "rows": out_rows,
        "approval_boundary": {
            "projection_queue_is_not_approval": True,
            "runtime_replay_required_for_projected_safe_resolved": True,
            "full375_collateral_remains_no_go_until_replayed": True,
            "completion_gate": "full375 collateral GO + full_scan path",
        },
    }


def _source_input_row(source: dict[str, Any], queue_row: dict[str, Any], queue_id: str) -> dict[str, Any]:
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
    out["_loop_projection_followup"] = {
        "queue_id": queue_id,
        "post_id": queue_row.get("post_id"),
        "selected_title": queue_row.get("selected_title"),
        "projected_title": queue_row.get("projected_title"),
        "projected_url": queue_row.get("projected_url"),
        "source_native_verdict": queue_row.get("source_native_verdict"),
        "actions": queue_row.get("actions") or [],
        "close_condition": queue_row.get("close_condition"),
        "approval_state": "runtime_replay_required_not_approval",
        "projected_status": queue_row.get("projected_status"),
        "matches_source_native_title": queue_row.get("matches_source_native_title") is True,
        "promotion_decision": queue_row.get("promotion_decision"),
        "promotion_gate_state": queue_row.get("promotion_gate_state"),
        "promotion_gate_evidence": queue_row.get("promotion_gate_evidence") or [],
        "publish_contract_trace": queue_row.get("publish_contract_trace"),
        "publish_ledger": queue_row.get("publish_ledger"),
        "prior_runtime_audit_status": queue_row.get("prior_runtime_audit_status"),
    }
    return out


def build_runtime_replay_input(
    queue: dict[str, Any],
    source_rows: list[dict[str, Any]],
    *,
    source_result_path: Path,
    output_jsonl: Path | None = None,
    runtime_manifest_json: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_index = {str(row.get("post_id")): row for row in source_rows if row.get("post_id") is not None}
    runtime_rows = [
        row
        for row in queue.get("rows") or []
        if isinstance(row, dict)
        and (
            "runtime_replay_projected_safe_resolved_exact_required" in (row.get("actions") or [])
            or "runtime_replay_with_projection_followup_seed_required" in (row.get("actions") or [])
        )
    ]
    missing_post_ids: list[Any] = []
    input_rows: list[dict[str, Any]] = []
    for row in runtime_rows:
        source = source_index.get(str(row.get("post_id")))
        if source is None:
            missing_post_ids.append(row.get("post_id"))
            continue
        input_rows.append(_source_input_row(source, row, str(queue.get("queue_id") or "")))

    manifest = {
        "queue_id": queue.get("queue_id"),
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "source_result_path": source_result_path.as_posix(),
        "runtime_replay_candidate_rows": len(runtime_rows),
        "runtime_input_rows": len(input_rows),
        "runtime_input_manifest_path": runtime_manifest_json.as_posix() if runtime_manifest_json else None,
        "requested_parallel": requested_parallel_for_test_run(len(input_rows)),
        "expected_effective_parallel": expected_effective_parallel(len(input_rows)),
        "dashboard_contract": dashboard_contract(),
        "dashboard_attach_boundary": (
            "Attach the expert_main result manifest after runtime starts or completes; "
            "do not attach this input-generation manifest."
        ),
        "missing_post_ids": missing_post_ids,
        "post_ids": [row.get("post_id") for row in input_rows],
        "expected_titles": [
            (row.get("_loop_projection_followup") or {}).get("projected_title")
            for row in input_rows
        ],
        "output_jsonl": output_jsonl.as_posix() if output_jsonl else None,
        "gate": {
            "runtime_input_generation": "GO" if not missing_post_ids else "NO-GO",
            "semantic_quality": "REVIEW-LOCKED",
            "full_scan_approval": False,
            "approval_boundary": "input generation is not runtime approval",
            "projection_followup_seed_is_not_approval": True,
        },
    }
    return input_rows, manifest


def write_markdown(queue: dict[str, Any], path: Path) -> None:
    summary = queue["summary"]
    lines = [
        f"# {queue.get('queue_id')}",
        "",
        "## 요약",
        "",
        f"- source_projection_id: `{queue.get('source_projection_id')}`",
        f"- gate: `{queue.get('gate')}`",
        f"- followup_action_queue_rows: `{summary.get('followup_action_queue_rows')}`",
        f"- label_counts: `{summary.get('label_counts')}`",
        f"- priority_counts: `{summary.get('priority_counts')}`",
        f"- projected_status_counts: `{summary.get('projected_status_counts')}`",
        f"- exact_match_counts: `{summary.get('exact_match_counts')}`",
        f"- prior_runtime_audit_status_counts: `{summary.get('prior_runtime_audit_status_counts')}`",
        f"- runtime_replay_candidate_rows: `{summary.get('runtime_replay_candidate_rows')}`",
        f"- runtime_seed_replay_candidate_rows: `{summary.get('runtime_seed_replay_candidate_rows')}`",
        f"- variant_review_rows: `{summary.get('variant_review_rows')}`",
        f"- lint_followup_rows: `{summary.get('lint_followup_rows')}`",
        f"- still_blocked_rows: `{summary.get('still_blocked_rows')}`",
        f"- validation_issue_count: `{summary.get('validation_issue_count')}`",
        "- approval: `false`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "",
        "## 승인 경계",
        "",
        "- 이 큐는 source projection의 후속 실행 단위이며 approval이 아니다.",
        "- `safe_resolved` projection도 runtime replay와 publication contract audit 전에는 해소 처리하지 않는다.",
        "- prior runtime expected-audit 실패 행은 같은 입력 반복 실행 전에 repair/source-native review lane으로 보낸다.",
        "- source-native exact title mismatch는 canonical variant 또는 wrong-work review 전까지 publish 근거가 아니다.",
        "- 완료 기준은 여전히 `full375 collateral GO + full_scan 경로 정의`다.",
        "",
        "## Action groups",
        "",
    ]
    for group in queue.get("action_groups") or []:
        sample = ", ".join(str(post_id) for post_id in group.get("post_ids", [])[:12])
        lines.extend(
            [
                f"### {group.get('action')}",
                "",
                f"- row_count: `{group.get('row_count')}`",
                f"- priority_counts: `{group.get('priority_counts')}`",
                f"- label_counts: `{group.get('label_counts')}`",
                f"- projected_status_counts: `{group.get('projected_status_counts')}`",
                f"- owner_modes: `{group.get('owner_modes')}`",
                f"- sample_post_ids: `{sample}`",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    while lines and lines[-1] == "":
        lines.pop()
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build follow-up action queue from a projection artifact.")
    parser.add_argument("--projection", required=True, type=Path)
    parser.add_argument("--queue-id", default="projection_followup_action_queue")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--prior-runtime-expected-audit", type=Path, default=None)
    parser.add_argument("--source-result", type=Path, default=None)
    parser.add_argument("--runtime-input-jsonl", type=Path, default=None)
    parser.add_argument("--runtime-manifest-json", type=Path, default=None)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    projection = load_json(args.projection)
    projection.setdefault("source_projection_path", args.projection.as_posix())
    prior_runtime_expected_audit = (
        load_json(args.prior_runtime_expected_audit)
        if args.prior_runtime_expected_audit
        else None
    )
    queue = build_followup_queue(
        projection,
        queue_id=args.queue_id,
        prior_runtime_expected_audit=prior_runtime_expected_audit,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    write_markdown(queue, args.output_md)
    if args.source_result or args.runtime_input_jsonl or args.runtime_manifest_json:
        if not (args.source_result and args.runtime_input_jsonl and args.runtime_manifest_json):
            raise ValueError("--source-result, --runtime-input-jsonl, and --runtime-manifest-json must be passed together")
        runtime_rows, manifest = build_runtime_replay_input(
            queue,
            load_result_rows(args.source_result),
            source_result_path=args.source_result,
            output_jsonl=args.runtime_input_jsonl,
            runtime_manifest_json=args.runtime_manifest_json,
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
    if args.fail_on_validation_issue and queue["summary"]["validation_issue_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
