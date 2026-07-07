from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


REPAIR_ACTIONS = {
    "prior_runtime_promotion_block_repair_required",
    "shared_gate_runtime_block_repair_required",
}

SCOPE_OR_NONWORK_MARKERS = {
    "context_only",
    "scope_context_only",
    "scope_not_current_work",
    "scope_unknown",
    "scope_unclassified",
    "row_discussion_missing",
    "nonwork",
    "nonwork_or_noise_context",
    "community_banter",
    "scope_platform_meta_nonwork",
    "non_novel_discourse",
    "exact_alias_candidate_preserved_without_work_discussion",
    "image_ocr_without_title_anchor",
    "unresolved_body_character_work_anchor",
    "missing_body_work_bridge",
}

CANDIDATE_PRESERVATION_MARKERS = {
    "blocked_candidate_scope_inferred_from_final_contract",
    "blocked_candidate_scope_inferred_from_search_evidence",
    "llm_only_sentence_candidate_pruned",
    "missing_direct_candidate_title",
    "official_url_recall_candidate_preserved",
    "official_url_recall_candidate_source_preserved",
    "serialized_public_identity_scrubbed",
    "serialized_public_identity_shared_gate_restored",
}

IMAGE_OR_ALIAS_MARKERS = {
    "alias_bridge",
    "batch_alias_public_title_bridge",
    "direct_image_work_surface_bridge",
    "ocr_catalog_official_title",
    "title_acceptance_accept",
    "title_led_consumption_bridge",
    "unverified_promoted_image_work_title_without_official_support",
    "verified_alias_title_only_publication",
}

TITLE_URL_OR_VARIANT_MARKERS = {
    "body_verified_character_work_competes_with_resolved_public_title",
    "character_bridge_variance_hold",
    "character_title_collision",
    "competing_candidate_present",
    "official_detail_url_title_mismatch_publish_blocked",
    "official_url_withheld_by_title_mismatch",
    "promoted_image_work_title_conflicts_with_public_title",
    "title_led_alias_contextual_official_detail_competes",
    "url_title_mismatch",
}

OFFICIAL_SUPPORT_MARKERS = {
    "official_detail_url",
    "official_detail_url_recovered_from_search_evidence",
    "official_title_exists",
}

PROJECTED_CURRENT_WORK_MARKERS = {
    "source_native_review_current_work",
    "scope_current_work",
    "row_discusses_work_as_work",
}

RUNTIME_CURRENT_WORK_MARKERS = {
    "scope_current_work",
    "row_discusses_work_as_work",
}

RUNTIME_NONCURRENT_MARKERS = {
    "context_only",
    "scope_context_only",
    "scope_not_current_work",
    "scope_unknown",
    "scope_unclassified",
    "row_discussion_missing",
    "nonwork",
    "nonwork_or_noise_context",
    "community_banter",
    "scope_platform_meta_nonwork",
    "non_novel_discourse",
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _iter_payload_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("rows", "results", "items", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def _unwrap_result_row(row: dict[str, Any]) -> dict[str, Any]:
    result = row.get("result")
    if isinstance(result, dict):
        return result
    return row


def _surface_key(value: Any) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def _near_surface_match(left: Any, right: Any) -> bool:
    left_key = _surface_key(left)
    right_key = _surface_key(right)
    if not left_key or not right_key:
        return False
    return left_key == right_key or left_key in right_key or right_key in left_key


def _candidate_metadata(identity: dict[str, Any], ledger: dict[str, Any], candidate_title: Any) -> dict[str, Any]:
    negative_evidence: set[str] = set()
    source_tiers: set[str] = set()
    source_roles: set[str] = set()
    matched_source_count = 0
    for container in (identity, ledger):
        if not isinstance(container, dict):
            continue
        for key in ("candidate_preservation_sources", "title_candidates"):
            values = container.get(key)
            if not isinstance(values, list):
                continue
            for item in values:
                if not isinstance(item, dict):
                    continue
                item_title = item.get("official_title") or item.get("title") or item.get("resolved_title")
                if candidate_title and item_title and not _near_surface_match(candidate_title, item_title):
                    continue
                if candidate_title and not item_title:
                    continue
                matched_source_count += 1
                raw_negative = item.get("negative_evidence") or []
                if isinstance(raw_negative, str):
                    raw_negative = [raw_negative]
                if isinstance(raw_negative, list):
                    negative_evidence.update(
                        str(value or "").strip()
                        for value in raw_negative
                        if str(value or "").strip()
                    )
                for field in ("source_tier", "reference_role", "preservation_role"):
                    value = str(item.get(field) or "").strip()
                    if not value:
                        continue
                    if field == "source_tier":
                        source_tiers.add(value)
                    else:
                        source_roles.add(value)

    image_title_match = False
    for container in (identity, ledger):
        if not isinstance(container, dict):
            continue
        for key in ("image_evidence_catalog", "image_enrichment"):
            values = container.get(key)
            if not isinstance(values, list):
                continue
            for item in values:
                if not isinstance(item, dict) or item.get("promotion_eligible") is not True:
                    continue
                for field in ("explicit_work_title", "detected_title", "work_title", "official_title"):
                    if _near_surface_match(candidate_title, item.get(field)):
                        image_title_match = True
                        break
                if image_title_match:
                    break
            if image_title_match:
                break
        if image_title_match:
            break

    return {
        "candidate_negative_evidence": sorted(negative_evidence),
        "candidate_source_tiers": sorted(source_tiers),
        "candidate_source_roles": sorted(source_roles),
        "candidate_metadata_source_count": matched_source_count,
        "candidate_image_title_match": image_title_match,
    }


def load_projection_candidate_map(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    candidates: dict[str, dict[str, Any]] = {}
    for raw_row in _iter_payload_rows(payload):
        row = _unwrap_result_row(raw_row)
        post_id = str(row.get("post_id") or "").strip()
        if not post_id:
            continue
        identity = ((row.get("analysis_result") or {}).get("identity") or row.get("identity") or {})
        if not isinstance(identity, dict):
            identity = {}
        ledger = identity.get("candidate_ledger") or {}
        if not isinstance(ledger, dict):
            ledger = {}
        trace = identity.get("publish_contract_trace") or ledger.get("publish_contract_trace") or {}
        if not isinstance(trace, dict):
            trace = {}
        pre_gate = trace.get("pre_gate_candidate") or {}
        if not isinstance(pre_gate, dict):
            pre_gate = {}
        blocked_reasons = trace.get("blocked_reason_codes") or trace.get("reason_codes") or []
        if not isinstance(blocked_reasons, list):
            blocked_reasons = [blocked_reasons]
        blocked_official_title = ledger.get("blocked_official_title") or identity.get("blocked_official_title")
        blocked_official_url = (
            ledger.get("blocked_official_title_url")
            or ledger.get("blocked_official_url")
            or identity.get("blocked_official_title_url")
            or identity.get("blocked_official_url")
        )
        candidate_title = pre_gate.get("official_title") or blocked_official_title
        candidates[post_id] = {
            "official_title": candidate_title,
            "official_url": pre_gate.get("official_url") or blocked_official_url,
            "source": pre_gate.get("source"),
            "decision": trace.get("decision"),
            "reason_codes": [str(item) for item in blocked_reasons if str(item or "").strip()],
            "blocked_official_title": blocked_official_title,
            "blocked_official_url": blocked_official_url,
            **_candidate_metadata(identity, ledger, candidate_title),
        }
    return candidates


def _counter_to_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _title_key(value: Any) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def _title_alignment_state(expected_title: Any, current_title: Any) -> str:
    expected = _title_key(expected_title)
    current = _title_key(current_title)
    if not expected or not current:
        return "missing_current_projection_candidate"
    if expected == current:
        return "same_title_surface"

    shorter, longer = (expected, current) if len(expected) <= len(current) else (current, expected)
    if len(shorter) >= 2 and shorter in longer:
        return "related_title_surface_review"

    shorter_chars = set(shorter)
    if shorter_chars:
        overlap = len(shorter_chars & set(longer)) / len(shorter_chars)
        if len(shorter) <= 4 and overlap >= 0.75:
            return "related_title_surface_review"
        if len(shorter) > 4 and overlap >= 0.55:
            return "related_title_surface_review"
    return "different_title_candidate_review"


def _candidate_alignment_requires_review(state: str) -> bool:
    return state in {
        "missing_current_projection_candidate",
        "related_title_surface_review",
        "different_title_candidate_review",
    }


PRESERVATION_ONLY_SUPPORT_STATES = {
    "candidate_preservation_only_no_official_detail",
    "unverified_image_candidate_preservation_only",
    "image_ocr_preservation_pending_official_url",
    "non_official_candidate_preservation_only",
}


def _candidate_support_state(projection_candidate: dict[str, Any] | None) -> str:
    if projection_candidate is None:
        return "projection_alignment_not_checked"
    if not projection_candidate:
        return "missing_current_projection_candidate_support"
    if projection_candidate.get("official_url"):
        return "official_url_candidate_support"
    title = str(projection_candidate.get("official_title") or "").strip()
    if not title:
        return "missing_current_projection_candidate_support"
    negative_evidence = {
        str(value or "").strip()
        for value in projection_candidate.get("candidate_negative_evidence") or []
        if str(value or "").strip()
    }
    reason_codes = {
        str(value or "").strip()
        for value in projection_candidate.get("reason_codes") or []
        if str(value or "").strip()
    }
    source_tiers = {
        str(value or "").strip()
        for value in projection_candidate.get("candidate_source_tiers") or []
        if str(value or "").strip()
    }
    if "missing_official_url_for_official_detail" in negative_evidence:
        return "candidate_preservation_only_no_official_detail"
    if (
        "unverified_promoted_image_work_title_without_official_support" in negative_evidence
        or "unverified_promoted_image_work_title_without_official_support" in reason_codes
    ):
        return "unverified_image_candidate_preservation_only"
    if projection_candidate.get("candidate_image_title_match") is True:
        return "image_ocr_preservation_pending_official_url"
    if "official_detail_url" in reason_codes:
        return "official_detail_trace_missing_url_review"
    if source_tiers and "official_detail" not in source_tiers:
        return "non_official_candidate_preservation_only"
    return "candidate_support_review_required"


def _repair_readiness_state(*, alignment_state: str, search_gate: str, candidate_support_state: str) -> str:
    if alignment_state == "not_checked":
        return "projection_alignment_not_checked"
    if _candidate_alignment_requires_review(alignment_state):
        return "candidate_alignment_review_required"
    if search_gate in {"SEARCH_BLIND_BLOCKER", "SEARCH_EVIDENCE_MISSING"}:
        return "same_title_search_preflight_required"
    if candidate_support_state in PRESERVATION_ONLY_SUPPORT_STATES:
        return "same_title_preservation_only_contract_repair_candidate"
    if search_gate == "SEARCH_RECOVERED_CONDITIONAL":
        return "same_title_search_recovered_contract_candidate"
    if search_gate == "SEARCH_OK":
        return "same_title_contract_candidate"
    return "manual_review_required"


def _actions(row: dict[str, Any]) -> list[str]:
    value = row.get("actions") or []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return []


def _reason_set(row: dict[str, Any]) -> set[str]:
    value = row.get("prior_runtime_reason_codes") or row.get("reason_codes") or []
    if not isinstance(value, list):
        value = [value]
    return {str(item or "").strip() for item in value if str(item or "").strip()}


def _runtime_audit_status(row: dict[str, Any]) -> str:
    return str(row.get("prior_runtime_audit_status") or row.get("audit_status") or "").strip()


def _runtime_search_status(row: dict[str, Any]) -> str:
    return str(row.get("prior_runtime_search_status") or row.get("search_status") or "None").strip()


def _projected_reason_set(row: dict[str, Any]) -> set[str]:
    value = row.get("projected_reasons") or []
    if not isinstance(value, list):
        value = [value]
    return {str(item or "").strip() for item in value if str(item or "").strip()}


def _repair_rows(queue: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = queue.get("rows") or []
    if not isinstance(rows, list):
        raise ValueError("queue.rows must be a list")
    selected: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            issues.append({"code": "non_object_queue_row", "index": idx})
            continue
        action_set = set(_actions(row))
        if not action_set.intersection(REPAIR_ACTIONS):
            continue
        audit_status = _runtime_audit_status(row)
        if audit_status != "FAIL_RUNTIME_PROMOTION_BLOCKED":
            issues.append(
                {
                    "code": "repair_action_without_prior_promotion_block",
                    "post_id": row.get("post_id"),
                    "prior_runtime_audit_status": audit_status or None,
                }
            )
        selected.append(row)
    return selected, issues


def _search_gate(row: dict[str, Any]) -> str:
    text = _runtime_search_status(row)
    if text == "ok":
        return "SEARCH_OK"
    if text == "SEARCH_DEGRADED_RECOVERED":
        return "SEARCH_RECOVERED_CONDITIONAL"
    if text == "SEARCH_DEGRADED":
        return "SEARCH_BLIND_BLOCKER"
    return "SEARCH_EVIDENCE_MISSING"


def _facets_for(reasons: set[str], search_gate: str) -> list[str]:
    facets: list[str] = ["public_identity_serialization_trace"]
    if reasons & SCOPE_OR_NONWORK_MARKERS:
        facets.append("scope_or_nonwork_monotonicity")
    if reasons & CANDIDATE_PRESERVATION_MARKERS:
        facets.append("candidate_preservation_or_scrub")
    if reasons & IMAGE_OR_ALIAS_MARKERS:
        facets.append("image_or_alias_anchor_contract")
    if reasons & TITLE_URL_OR_VARIANT_MARKERS:
        facets.append("title_url_or_variant_trace")
    if reasons & OFFICIAL_SUPPORT_MARKERS:
        facets.append("official_support_reconciliation")
    if search_gate != "SEARCH_OK":
        facets.append("search_blind_or_missing_preflight")
    return facets


def _scope_claim(reasons: set[str], *, projected: bool = False) -> str:
    if projected:
        if reasons & PROJECTED_CURRENT_WORK_MARKERS:
            return "PROJECTED_CURRENT_WORK"
        return "PROJECTED_SCOPE_UNSPECIFIED"
    has_current = bool(reasons & RUNTIME_CURRENT_WORK_MARKERS)
    has_noncurrent = bool(reasons & RUNTIME_NONCURRENT_MARKERS)
    if has_current and has_noncurrent:
        return "RUNTIME_MIXED_CURRENT_AND_NONCURRENT"
    if has_noncurrent:
        return "RUNTIME_NONCURRENT_OR_CONTEXT_ONLY"
    if has_current:
        return "RUNTIME_CURRENT_WORK"
    return "RUNTIME_SCOPE_UNSPECIFIED"


def _projection_runtime_scope_conflict_kind(projected_reasons: set[str], runtime_reasons: set[str]) -> str:
    if not projected_reasons & PROJECTED_CURRENT_WORK_MARKERS:
        return "none"
    has_current = bool(runtime_reasons & RUNTIME_CURRENT_WORK_MARKERS)
    has_noncurrent = bool(runtime_reasons & RUNTIME_NONCURRENT_MARKERS)
    if has_current and has_noncurrent:
        return "mixed_trace"
    if has_noncurrent:
        return "hard_noncurrent"
    return "none"


def _primary_lane(reasons: set[str]) -> str:
    if reasons & TITLE_URL_OR_VARIANT_MARKERS:
        return "title_url_or_variant_trace_repair"
    if reasons & IMAGE_OR_ALIAS_MARKERS:
        return "image_or_alias_anchor_contract_repair"
    if reasons & SCOPE_OR_NONWORK_MARKERS:
        return "scope_or_nonwork_monotonicity_repair"
    if reasons & CANDIDATE_PRESERVATION_MARKERS:
        return "candidate_preservation_or_scrub_repair"
    if "promotion_blocked" in reasons:
        return "promotion_trace_introspection_required"
    return "manual_shared_gate_repair_review"


def _lane_action(lane: str) -> str:
    return f"{lane}_required" if not lane.endswith("_required") else lane


def _close_condition(lane: str) -> str:
    if lane == "title_url_or_variant_trace_repair":
        return "title/url mismatch, competing candidate, variant reason이 publish_contract_trace와 can_publish_title에서 같은 결정으로 수렴해야 한다."
    if lane == "image_or_alias_anchor_contract_repair":
        return "이미지/OCR/별칭 앵커가 direct work anchor인지 검증하고, 미검증 앵커는 candidate_only로 보존해야 한다."
    if lane == "scope_or_nonwork_monotonicity_repair":
        return "current-work 직접 브리지가 확인되기 전에는 hard-hold를 완화하지 않고, 확인된 경우 _post_discusses_work_as_work 경유로만 publish를 연다."
    if lane == "candidate_preservation_or_scrub_repair":
        return "supported candidate가 serialized public identity에서 사라지지 않고 candidate ledger와 publish trace에 보존되어야 한다."
    if lane == "promotion_trace_introspection_required":
        return "promotion_blocked reason이 publish_contract_trace에 충분히 노출되어 다음 repair lane으로 재분류되어야 한다."
    return "수동 review가 publish, candidate_only, repair 중 하나를 확정해야 한다."


def _contract_tests(lane: str) -> list[str]:
    common = [
        "runtime replay는 수리 전 금지한다.",
        "수리 후 같은 packet safe_resolved는 단조 비감소해야 한다.",
        "full375 collateral 재확인 전 approval을 열지 않는다.",
    ]
    lane_tests = {
        "title_url_or_variant_trace_repair": [
            "publish_contract_trace와 can_publish_title이 title/url mismatch를 같은 reason code로 노출한다.",
            "공식 URL과 public title이 불일치하면 safe_resolved가 아니라 candidate_only로 보존한다.",
        ],
        "image_or_alias_anchor_contract_repair": [
            "검증된 이미지/OCR/별칭 앵커만 _post_discusses_work_as_work 경유로 current-work bridge를 연다.",
            "image_ocr_without_title_anchor 계열은 직접 제목 앵커 없이는 publish를 열지 않는다.",
        ],
        "scope_or_nonwork_monotonicity_repair": [
            "_has_verified_contextual_alias_work_bridge는 _post_discusses_work_as_work를 경유한다.",
            "scope_not_current_work/context_only/nonwork reason은 direct work bridge 없이는 monotonic hard-hold를 유지한다.",
        ],
        "candidate_preservation_or_scrub_repair": [
            "llm-only sentence pruning 뒤에도 source-native supported candidate는 candidate ledger에 보존된다.",
            "serialized_public_identity_scrubbed reason은 public identity와 candidate ledger의 불일치로 audit 가능해야 한다.",
        ],
        "promotion_trace_introspection_required": [
            "promotion_blocked 단독 reason은 다음 repair lane으로 재분류할 수 있을 만큼 trace detail을 남긴다.",
        ],
    }
    return lane_tests.get(lane, ["manual review packet이 next action을 확정한다."]) + common


def classify_repair_row(
    row: dict[str, Any],
    *,
    projection_candidates_by_post_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    reasons = _reason_set(row)
    projected_reasons = _projected_reason_set(row)
    search_gate = _search_gate(row)
    lane = _primary_lane(reasons)
    facets = _facets_for(reasons, search_gate)
    scope_conflict_kind = _projection_runtime_scope_conflict_kind(projected_reasons, reasons)
    scope_conflict = scope_conflict_kind != "none"
    if scope_conflict:
        facets.append("projection_runtime_scope_conflict")
    if scope_conflict_kind == "mixed_trace":
        facets.append("projection_runtime_scope_mixed_trace")
    actions = [
        _lane_action(lane),
        "publish_contract_trace_contract_test_required",
        "runtime_replay_after_contract_repair",
        "full375_collateral_recheck_after_repair",
    ]
    if scope_conflict_kind == "hard_noncurrent":
        actions.insert(1, "projection_runtime_scope_reconciliation_required")
    elif scope_conflict_kind == "mixed_trace":
        actions.insert(1, "projection_runtime_scope_trace_normalization_required")
    if search_gate in {"SEARCH_BLIND_BLOCKER", "SEARCH_EVIDENCE_MISSING"}:
        actions.insert(1, "search_blind_preflight_required")
    elif search_gate == "SEARCH_RECOVERED_CONDITIONAL":
        actions.insert(1, "search_recovered_conditional_tag_required")

    selected_title = row.get("selected_title") or row.get("expected_title")
    projected_title = row.get("projected_title") or row.get("expected_title")
    expected_title_for_alignment = selected_title or projected_title
    projection_candidate: dict[str, Any] | None = None
    alignment_state = "not_checked"
    if projection_candidates_by_post_id is not None:
        projection_candidate = projection_candidates_by_post_id.get(str(row.get("post_id") or "").strip())
        if projection_candidate is None:
            alignment_state = "missing_current_projection_candidate"
            projection_candidate = {}
        else:
            alignment_state = _title_alignment_state(
                expected_title_for_alignment,
                projection_candidate.get("official_title"),
            )
    candidate_support_state = _candidate_support_state(projection_candidate)
    alignment_requires_review = _candidate_alignment_requires_review(alignment_state)
    if alignment_requires_review:
        facets.append("current_projection_candidate_alignment_review")
        actions.insert(1, "current_projection_candidate_recheck_required")
    readiness_state = _repair_readiness_state(
        alignment_state=alignment_state,
        search_gate=search_gate,
        candidate_support_state=candidate_support_state,
    )
    if readiness_state == "same_title_search_recovered_contract_candidate":
        actions.insert(1, "same_title_search_recovered_contract_repair_candidate")
    elif readiness_state == "same_title_preservation_only_contract_repair_candidate":
        actions.insert(1, "same_title_preservation_only_contract_repair_candidate")
        actions.insert(2, "candidate_preservation_only_no_publish_required")
    elif readiness_state == "same_title_contract_candidate":
        actions.insert(1, "same_title_surface_contract_repair_candidate")
    elif readiness_state == "same_title_search_preflight_required":
        actions.insert(1, "same_title_surface_search_preflight_required")

    contract_tests = _contract_tests(lane)
    if alignment_requires_review:
        contract_tests = contract_tests + [
            "current projection pre_gate_candidate가 expected/source-native title과 다르면 shared gate 완화 전 source-native/blind canonicality를 재확인한다.",
        ]
    evidence_refs = list(row.get("evidence_refs") or []) + [
        f"prior_runtime_expected_audit#post_id={row.get('post_id')}"
    ]
    if projection_candidates_by_post_id is not None:
        evidence_refs.append(f"current_projection_result#post_id={row.get('post_id')}")

    return {
        "post_id": row.get("post_id"),
        "selected_title": selected_title,
        "projected_title": projected_title,
        "current_projection_candidate": projection_candidate,
        "current_projection_candidate_alignment_state": alignment_state,
        "current_projection_candidate_alignment_requires_review": alignment_requires_review,
        "candidate_support_state": candidate_support_state,
        "repair_readiness_state": readiness_state,
        "source_native_verdict": row.get("source_native_verdict"),
        "prior_runtime_audit_status": _runtime_audit_status(row) or None,
        "prior_runtime_search_status": _runtime_search_status(row),
        "search_gate": search_gate,
        "projected_scope_claim": _scope_claim(projected_reasons, projected=True),
        "runtime_scope_claim": _scope_claim(reasons),
        "projection_runtime_scope_conflict": scope_conflict,
        "projection_runtime_scope_conflict_kind": scope_conflict_kind,
        "primary_repair_lane": lane,
        "repair_facets": facets,
        "reason_codes": sorted(reasons),
        "projected_reasons": sorted(projected_reasons),
        "runtime_replay_allowed": False,
        "runtime_replay_blocker": "contract_repair_required_before_replay",
        "actions": actions,
        "close_condition": _close_condition(lane),
        "required_contract_tests": contract_tests,
        "evidence_refs": evidence_refs,
    }


def build_repair_queue(
    source_queue: dict[str, Any],
    *,
    queue_id: str,
    generated_at: str | None = None,
    projection_candidates_by_post_id: dict[str, dict[str, Any]] | None = None,
    projection_result_path: str | Path | None = None,
) -> dict[str, Any]:
    rows, validation_issues = _repair_rows(source_queue)
    out_rows = [
        classify_repair_row(row, projection_candidates_by_post_id=projection_candidates_by_post_id)
        for row in rows
    ]
    primary_counts = Counter(str(row["primary_repair_lane"]) for row in out_rows)
    facet_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    search_counts = Counter(str(row["search_gate"]) for row in out_rows)
    action_counts: Counter[str] = Counter()
    scope_conflict_counts = Counter(
        "conflict" if row.get("projection_runtime_scope_conflict") else "no_conflict" for row in out_rows
    )
    scope_conflict_kind_counts = Counter(str(row.get("projection_runtime_scope_conflict_kind") or "none") for row in out_rows)
    alignment_counts = Counter(str(row.get("current_projection_candidate_alignment_state") or "not_checked") for row in out_rows)
    candidate_support_counts = Counter(str(row.get("candidate_support_state") or "candidate_support_review_required") for row in out_rows)
    readiness_counts = Counter(str(row.get("repair_readiness_state") or "manual_review_required") for row in out_rows)
    lane_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in out_rows:
        lane_groups[str(row["primary_repair_lane"])].append(row)
        for facet in row["repair_facets"]:
            facet_counts[str(facet)] += 1
        for reason in row["reason_codes"]:
            reason_counts[str(reason)] += 1
        for action in row["actions"]:
            action_counts[str(action)] += 1

    action_groups: list[dict[str, Any]] = []
    for lane in sorted(lane_groups):
        group_rows = lane_groups[lane]
        action_groups.append(
            {
                "primary_repair_lane": lane,
                "row_count": len(group_rows),
                "search_gate_counts": _counter_to_dict(Counter(str(row["search_gate"]) for row in group_rows)),
                "facet_counts": _counter_to_dict(
                    Counter(facet for row in group_rows for facet in row["repair_facets"])
                ),
                "projection_runtime_scope_conflict_rows": sum(
                    1 for row in group_rows if row.get("projection_runtime_scope_conflict")
                ),
                "projection_runtime_scope_conflict_kind_counts": _counter_to_dict(
                    Counter(str(row.get("projection_runtime_scope_conflict_kind") or "none") for row in group_rows)
                ),
                "current_projection_candidate_alignment_counts": _counter_to_dict(
                    Counter(
                        str(row.get("current_projection_candidate_alignment_state") or "not_checked")
                        for row in group_rows
                    )
                ),
                "current_projection_candidate_review_rows": sum(
                    1 for row in group_rows if row.get("current_projection_candidate_alignment_requires_review")
                ),
                "candidate_support_state_counts": _counter_to_dict(
                    Counter(str(row.get("candidate_support_state") or "candidate_support_review_required") for row in group_rows)
                ),
                "repair_readiness_counts": _counter_to_dict(
                    Counter(str(row.get("repair_readiness_state") or "manual_review_required") for row in group_rows)
                ),
                "post_ids": [row.get("post_id") for row in group_rows],
                "sample_rows": group_rows[:8],
            }
        )

    return {
        "report_type": "shared_gate_runtime_block_repair_queue",
        "queue_id": queue_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_queue_id": source_queue.get("queue_id"),
        "source_queue_path": source_queue.get("source_projection_path") or "",
        "projection_result_path": str(projection_result_path or ""),
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "summary": {
            "source_queue_rows": len(source_queue.get("rows") or []),
            "repair_rows": len(out_rows),
            "runtime_replay_allowed_rows": sum(1 for row in out_rows if row.get("runtime_replay_allowed") is True),
            "primary_repair_lane_counts": _counter_to_dict(primary_counts),
            "repair_facet_counts": _counter_to_dict(facet_counts),
            "search_gate_counts": _counter_to_dict(search_counts),
            "reason_counts": _counter_to_dict(reason_counts),
            "action_counts": _counter_to_dict(action_counts),
            "projection_runtime_scope_conflict_counts": _counter_to_dict(scope_conflict_counts),
            "projection_runtime_scope_conflict_kind_counts": _counter_to_dict(scope_conflict_kind_counts),
            "current_projection_candidate_alignment_counts": _counter_to_dict(alignment_counts),
            "current_projection_candidate_review_rows": sum(
                1 for row in out_rows if row.get("current_projection_candidate_alignment_requires_review")
            ),
            "candidate_support_state_counts": _counter_to_dict(candidate_support_counts),
            "repair_readiness_counts": _counter_to_dict(readiness_counts),
            "validation_issue_count": len(validation_issues),
        },
        "stop_condition": {
            "actionable_queue_must_decrease": True,
            "same_packet_safe_resolved_must_be_monotonic_non_decreasing": True,
            "round_count_is_not_a_stop_condition": True,
        },
        "approval_boundary": {
            "repair_queue_is_not_approval": True,
            "runtime_replay_before_contract_repair_forbidden": True,
            "full375_collateral_remains_no_go": True,
            "completion_gate": "full375 collateral GO + full_scan path",
        },
        "validation_issues": validation_issues,
        "action_groups": action_groups,
        "rows": out_rows,
    }


def write_markdown(queue: dict[str, Any], path: Path) -> None:
    summary = queue["summary"]
    lines = [
        f"# {queue['queue_id']}",
        "",
        "## 요약",
        "",
        f"- source_queue_id: `{queue.get('source_queue_id')}`",
        f"- gate: `{queue.get('gate')}`",
        f"- repair_rows: `{summary.get('repair_rows')}`",
        f"- runtime_replay_allowed_rows: `{summary.get('runtime_replay_allowed_rows')}`",
        f"- primary_repair_lane_counts: `{summary.get('primary_repair_lane_counts')}`",
        f"- repair_facet_counts: `{summary.get('repair_facet_counts')}`",
        f"- search_gate_counts: `{summary.get('search_gate_counts')}`",
        f"- projection_runtime_scope_conflict_counts: `{summary.get('projection_runtime_scope_conflict_counts')}`",
        f"- projection_runtime_scope_conflict_kind_counts: `{summary.get('projection_runtime_scope_conflict_kind_counts')}`",
        f"- current_projection_candidate_alignment_counts: `{summary.get('current_projection_candidate_alignment_counts')}`",
        f"- current_projection_candidate_review_rows: `{summary.get('current_projection_candidate_review_rows')}`",
        f"- candidate_support_state_counts: `{summary.get('candidate_support_state_counts')}`",
        f"- repair_readiness_counts: `{summary.get('repair_readiness_counts')}`",
        f"- validation_issue_count: `{summary.get('validation_issue_count')}`",
        "- approval: `false`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "",
        "## 승인 경계",
        "",
        "- 이 repair queue는 runtime replay 입력이 아니다.",
        "- 수리 전 동일 packet 반복 실행을 금지한다.",
        "- search degraded 또는 missing 행은 `search-blind 조건부`를 보존한다.",
        "- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.",
        "",
        "## Repair lanes",
        "",
    ]
    for group in queue.get("action_groups") or []:
        sample = ", ".join(str(post_id) for post_id in group.get("post_ids", [])[:12])
        lines.extend(
            [
                f"### {group.get('primary_repair_lane')}",
                "",
                f"- row_count: `{group.get('row_count')}`",
                f"- search_gate_counts: `{group.get('search_gate_counts')}`",
                f"- facet_counts: `{group.get('facet_counts')}`",
                f"- projection_runtime_scope_conflict_rows: `{group.get('projection_runtime_scope_conflict_rows')}`",
                f"- projection_runtime_scope_conflict_kind_counts: `{group.get('projection_runtime_scope_conflict_kind_counts')}`",
                f"- current_projection_candidate_alignment_counts: `{group.get('current_projection_candidate_alignment_counts')}`",
                f"- current_projection_candidate_review_rows: `{group.get('current_projection_candidate_review_rows')}`",
                f"- candidate_support_state_counts: `{group.get('candidate_support_state_counts')}`",
                f"- repair_readiness_counts: `{group.get('repair_readiness_counts')}`",
                f"- sample_post_ids: `{sample}`",
                "",
            ]
        )
    lines.extend(["## 다음 조건", "", "- contract repair 뒤에만 runtime replay 후보로 되돌린다.", "- replay 뒤에는 full375 collateral을 다시 확인한다."])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a repair queue for shared gate runtime promotion-block rows.")
    parser.add_argument("--queue", required=True, type=Path)
    parser.add_argument("--queue-id", default="shared_gate_runtime_block_repair_queue")
    parser.add_argument("--projection-result", type=Path, default=None)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    projection_candidates = None
    if args.projection_result is not None:
        projection_candidates = load_projection_candidate_map(args.projection_result)
    queue = build_repair_queue(
        load_json(args.queue),
        queue_id=args.queue_id,
        projection_candidates_by_post_id=projection_candidates,
        projection_result_path=args.projection_result,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    write_markdown(queue, args.output_md)
    if args.fail_on_validation_issue and queue["summary"]["validation_issue_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
