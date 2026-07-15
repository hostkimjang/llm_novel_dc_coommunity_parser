from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from llm_batch.promotion_gate import (
        PUBLISH_CONTRACT_VERSION,
        candidate_inventory_evidence_from_sources,
        candidate_inventory_pairs,
        candidate_inventory_records,
        build_publish_ledger,
        evaluate_publish_contract,
        evidence_records_from_payload,
        grounding_state_from_dict,
    )
except ModuleNotFoundError:
    from src.llm_batch.promotion_gate import (
        PUBLISH_CONTRACT_VERSION,
        candidate_inventory_evidence_from_sources,
        candidate_inventory_pairs,
        candidate_inventory_records,
        build_publish_ledger,
        evaluate_publish_contract,
        evidence_records_from_payload,
        grounding_state_from_dict,
    )


PUBLIC_TITLE_KEYS = ("official_title", "official_novel_title", "resolved_title")
PUBLIC_URL_KEYS = ("heretic_url", "official_url", "resolved_url")
NO_CANDIDATE_REASON_CODES = {
    "hold_without_candidates",
    "no_candidate_title",
    "missing_candidate_title",
    "no_public_candidate",
}
PUBLISH_ONLY_REASON_CODES = {
    "serialized_public_identity_published",
}
URL_TITLE_MISMATCH_BLOCK_REASON_CODES = {
    "url_title_mismatch",
    "official_detail_url_title_mismatch_publish_blocked",
}
URL_WITHHELD_REASON_CODE = "official_url_withheld_by_title_mismatch"
IMAGE_DIRECT_WORK_REASON_CODES = {
    "direct_image_work_surface_bridge",
    "direct_image_work_surface_lock",
    "structured_direct_image_work_surface",
    "ocr_catalog_official_title",
    "image_ocr_work_title",
}
IMAGE_TITLE_ONLY_PUBLISH_REASON_CODE = "verified_image_ocr_work_title_publication"
IMAGE_HARD_HOLD_REASON_CODES = {
    "image_ocr_without_title_anchor",
    "platform_meta_image_title_hard_hold",
    "image_scene_cues_unverified_public_title_bridge",
    "precision_seed_weak_source_title_without_official_support",
}
IMAGE_UNVERIFIED_REASON_CODE = "unverified_promoted_image_work_title_without_official_support"
SCOPE_CURRENT_WORK_REASON_MARKERS = {
    "scope_current_work",
    "row_discusses_work_as_work",
}
SCOPE_NONCURRENT_REASON_MARKERS = {
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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not raw_line.strip():
            continue
        row = json.loads(raw_line)
        if not isinstance(row, dict):
            raise ValueError(f"Expected JSON object at {path}:{line_no}")
        rows.append(row)
    return rows


def load_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        return load_jsonl(path)
    payload = load_json(path)
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("results", "rows", "items", "data"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    raise ValueError(f"Unsupported row payload: {path}")


def build_result_artifact_binding(
    path: Path,
    *,
    row_count: int,
) -> dict[str, Any]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(path),
        "sha256": digest.hexdigest(),
        "size_bytes": path.stat().st_size,
        "row_count": row_count,
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def unwrap_result_row(row: dict[str, Any]) -> dict[str, Any]:
    nested = row.get("result")
    if isinstance(nested, dict):
        return nested
    return row


def row_identity(row: dict[str, Any]) -> dict[str, Any]:
    row = unwrap_result_row(row)
    analysis = row.get("analysis_result")
    if isinstance(analysis, dict) and isinstance(analysis.get("identity"), dict):
        return analysis["identity"]
    identity = row.get("identity")
    return identity if isinstance(identity, dict) else {}


def row_post_id(row: dict[str, Any]) -> str:
    row = unwrap_result_row(row)
    for source in (
        row,
        row.get("analysis_result") if isinstance(row.get("analysis_result"), dict) else {},
        row_identity(row),
    ):
        if isinstance(source, dict) and source.get("post_id") not in (None, ""):
            return str(source.get("post_id")).strip()
    return ""


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_or_none(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _first_public_value(identity: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    novel = _dict_or_empty(identity.get("novel_identity"))
    for source in (novel, identity):
        for key in keys:
            value = _string_or_none(source.get(key))
            if value:
                return value
    return None


def _public_identity(identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "official_title": _first_public_value(identity, PUBLIC_TITLE_KEYS),
        "official_url": _first_public_value(identity, PUBLIC_URL_KEYS),
    }


def _same_dict(left: Any, right: Any) -> bool:
    return isinstance(left, dict) and isinstance(right, dict) and left == right


def _candidate_title_url(value: Any) -> dict[str, str | None]:
    payload = _dict_or_empty(value)
    return {
        "official_title": _string_or_none(payload.get("official_title")),
        "official_url": _string_or_none(payload.get("official_url")),
    }


def _has_candidate_payload(value: Any) -> bool:
    candidate = _candidate_title_url(value)
    return bool(candidate["official_title"] or candidate["official_url"])


def _scope_kind(value: Any) -> str:
    return str(_dict_or_empty(value).get("scope_kind") or "").strip()


def _reason_code_set(value: Any) -> set[str]:
    if isinstance(value, dict):
        value = value.get("reason_codes")
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return set()
    return {str(code or "").strip() for code in value if str(code or "").strip()}


def _title_key(value: Any) -> str:
    import re

    return re.sub(r"[^0-9A-Za-z가-힣]+", "", str(value or "")).lower()


def _near_title_match(left: Any, right: Any) -> bool:
    left_key = _title_key(left)
    right_key = _title_key(right)
    if not left_key or not right_key:
        return False
    return bool(left_key == right_key or left_key in right_key or right_key in left_key)


def _iter_dict_list(container: Any, key: str) -> list[dict[str, Any]]:
    if not isinstance(container, dict):
        return []
    values = container.get(key)
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, dict)]


def _direct_bridge_sources(*scopes: Any) -> set[str]:
    out: set[str] = set()
    for scope in scopes:
        payload = _dict_or_empty(scope)
        values = payload.get("direct_bridge_sources")
        if isinstance(values, list):
            out.update(str(value or "").strip() for value in values if str(value or "").strip())
    return out


def _matching_verified_image_work_title(identity: dict[str, Any], ledger: dict[str, Any], title: Any) -> bool:
    candidate_title = str(title or "").strip()
    if not candidate_title:
        return False
    for source in (identity, ledger):
        for item in (
            _iter_dict_list(source, "image_evidence_catalog")
            + _iter_dict_list(source, "image_enrichment")
        ):
            if item.get("promotion_eligible") is not True:
                continue
            role = str(item.get("title_role") or "").strip().lower()
            evidence_type = str(item.get("evidence_type") or "").strip().lower()
            if role not in {"title", "cover_title", "explicit_title", "work_title"} and evidence_type not in {
                "ocr_title",
                "explicit_title",
                "work_title",
                "explicit_text",
            }:
                continue
            if any(
                _near_title_match(item.get(key), candidate_title)
                for key in ("explicit_work_title", "detected_title", "work_title", "official_title")
            ):
                return True
    return False


def _candidate_title_from_sources(*values: Any) -> str | None:
    for value in values:
        candidate = _candidate_title_url(value)
        if candidate["official_title"]:
            return candidate["official_title"]
    return None


def _append_violation(violations: list[dict[str, Any]], code: str, detail: str) -> None:
    violations.append({"code": code, "detail": detail})


def audit_row(row: dict[str, Any], *, index: int) -> dict[str, Any]:
    identity = row_identity(row)
    post_id = row_post_id(row)
    public_identity = _public_identity(identity)
    violations: list[dict[str, Any]] = []
    if not identity:
        _append_violation(violations, "missing_identity", "row has no identity payload")
        return {
            "index": index,
            "post_id": post_id,
            "gate": "NO-GO",
            "public_identity": public_identity,
            "violations": violations,
        }

    ledger = _dict_or_empty(identity.get("candidate_ledger"))
    identity_integrity_error = identity.get("publish_contract_integrity_error")
    ledger_integrity_error = ledger.get("publish_contract_integrity_error")
    if identity_integrity_error is not None or ledger_integrity_error is not None:
        _append_violation(
            violations,
            "publish_contract_integrity_error",
            "serializer recorded an authoritative typed-contract integrity failure",
        )
        if identity_integrity_error != ledger_integrity_error:
            _append_violation(
                violations,
                "candidate_ledger_publish_contract_integrity_error_mismatch",
                "candidate_ledger integrity error differs from identity integrity error",
            )
    identity_decision = identity.get("promotion_decision")
    decision = identity_decision
    if not isinstance(decision, dict):
        decision = ledger.get("promotion_decision")
    identity_trace = identity.get("publish_contract_trace")
    trace = identity_trace
    if not isinstance(trace, dict):
        trace = ledger.get("publish_contract_trace")
    identity_publish_ledger = identity.get("publish_ledger")
    publish_ledger = identity_publish_ledger
    if not isinstance(publish_ledger, dict):
        publish_ledger = ledger.get("publish_ledger")
    identity_gate_state = identity.get("promotion_gate_state")
    ledger_gate_state = ledger.get("promotion_gate_state")
    promotion_gate_state = (
        identity_gate_state
        if isinstance(identity_gate_state, dict)
        else ledger_gate_state if isinstance(ledger_gate_state, dict) else {}
    )
    # The serialized row identity is the outer contract key.  When typed
    # state carries a post_id, it must agree with that key; otherwise a
    # converged-looking row could be attributed to the wrong post.
    typed_state_post_id = _string_or_none(promotion_gate_state.get("post_id"))
    if typed_state_post_id and post_id and typed_state_post_id != post_id:
        _append_violation(
            violations,
            "typed_state_post_id_mismatch",
            f"typed promotion_gate_state.post_id={typed_state_post_id} differs from row post_id={post_id}",
        )
    identity_gate_evidence = identity.get("promotion_gate_evidence")
    ledger_gate_evidence = ledger.get("promotion_gate_evidence")
    promotion_gate_evidence = (
        identity_gate_evidence
        if isinstance(identity_gate_evidence, list)
        else ledger_gate_evidence if isinstance(ledger_gate_evidence, list) else []
    )
    candidate_decision = ledger.get("promotion_decision")
    identity_contract_version = str(identity.get("publish_contract_version") or "").strip()
    ledger_contract_version = str(ledger.get("publish_contract_version") or "").strip()
    identity_fingerprint = str(
        identity.get("publish_contract_input_fingerprint") or ""
    ).strip()
    ledger_fingerprint_marker = str(
        ledger.get("publish_contract_input_fingerprint") or ""
    ).strip()
    decision_contract_version = str(
        decision.get("contract_version") if isinstance(decision, dict) else ""
    ).strip()
    identity_ledger_gate_decision = _dict_or_empty(
        identity_publish_ledger.get("gate_decision")
        if isinstance(identity_publish_ledger, dict)
        else None
    )
    candidate_ledger_publish_ledger = ledger.get("publish_ledger")
    candidate_ledger_gate_decision = _dict_or_empty(
        candidate_ledger_publish_ledger.get("gate_decision")
        if isinstance(candidate_ledger_publish_ledger, dict)
        else None
    )
    v2_marker = bool(
        identity_contract_version == PUBLISH_CONTRACT_VERSION
        or ledger_contract_version == PUBLISH_CONTRACT_VERSION
        or decision_contract_version == PUBLISH_CONTRACT_VERSION
        or (
            isinstance(identity_gate_state, dict)
            and isinstance(identity_gate_evidence, list)
        )
        or (
            isinstance(ledger_gate_state, dict)
            and isinstance(ledger_gate_evidence, list)
        )
        or bool(identity_fingerprint)
        or bool(ledger_fingerprint_marker)
        or str(identity_ledger_gate_decision.get("contract_version") or "").strip()
        == PUBLISH_CONTRACT_VERSION
        or str(candidate_ledger_gate_decision.get("contract_version") or "").strip()
        == PUBLISH_CONTRACT_VERSION
    )
    if v2_marker and not isinstance(identity_decision, dict):
        _append_violation(
            violations,
            "identity_promotion_decision_missing",
            "v2 authoritative identity must contain promotion_decision; candidate_ledger is mirror-only",
        )
    if v2_marker and not isinstance(candidate_decision, dict):
        _append_violation(
            violations,
            "candidate_ledger_promotion_decision_missing",
            "v2 candidate_ledger must mirror the authoritative promotion_decision",
        )
    if v2_marker and not isinstance(identity_trace, dict):
        _append_violation(
            violations,
            "identity_publish_contract_trace_missing",
            "v2 authoritative identity must contain publish_contract_trace; candidate_ledger is mirror-only",
        )
    if v2_marker and not isinstance(identity_publish_ledger, dict):
        _append_violation(
            violations,
            "identity_publish_ledger_missing",
            "v2 authoritative identity must contain publish_ledger; candidate_ledger is mirror-only",
        )

    has_public_title = bool(public_identity["official_title"])
    if has_public_title and not isinstance(decision, dict):
        _append_violation(
            violations,
            "missing_publication_decision_for_public_identity",
            "serialized public title exists without PromotionDecision",
        )
    if isinstance(decision, dict) and not isinstance(trace, dict):
        _append_violation(violations, "missing_publish_contract_trace", "PromotionDecision exists without trace")
    if isinstance(decision, dict) and not isinstance(publish_ledger, dict):
        _append_violation(violations, "missing_publish_ledger", "PromotionDecision exists without publish ledger")

    if not isinstance(decision, dict):
        _append_violation(
            violations,
            "missing_authoritative_promotion_decision",
            "publication contract convergence requires a typed PromotionDecision for every row",
        )
        return {
            "index": index,
            "post_id": post_id,
            "gate": "NO-GO",
            "public_identity": public_identity,
            "violations": violations,
        }

    gate_decision = _dict_or_empty(trace.get("gate_decision")) if isinstance(trace, dict) else {}
    ledger_gate_decision = _dict_or_empty(publish_ledger.get("gate_decision")) if isinstance(publish_ledger, dict) else {}
    pre_gate_candidate = trace.get("pre_gate_candidate") if isinstance(trace, dict) else {}
    ledger_candidate_preservation = (
        publish_ledger.get("candidate_preservation") if isinstance(publish_ledger, dict) else {}
    )
    candidate_trace = ledger.get("publish_contract_trace")
    candidate_publish_ledger = ledger.get("publish_ledger")

    serialized_fingerprint = identity_fingerprint
    ledger_fingerprint = str(ledger.get("publish_contract_input_fingerprint") or "").strip()
    if identity_contract_version != PUBLISH_CONTRACT_VERSION:
        _append_violation(
            violations,
            "authoritative_publish_contract_missing",
            f"expected {PUBLISH_CONTRACT_VERSION}, got {identity_contract_version or 'missing'}",
        )
    if ledger_contract_version != identity_contract_version:
        _append_violation(
            violations,
            "candidate_ledger_publish_contract_version_mismatch",
            "candidate_ledger contract version differs from identity contract version",
        )
    if decision_contract_version != identity_contract_version:
        _append_violation(
            violations,
            "promotion_decision_publish_contract_version_mismatch",
            "PromotionDecision contract version differs from identity contract version",
        )
    if not isinstance(identity_gate_state, dict):
        _append_violation(
            violations,
            "promotion_gate_state_missing_for_shadow_recompute",
            "typed state is required for fail-closed shadow recompute",
        )
    if not isinstance(ledger_gate_state, dict):
        _append_violation(
            violations,
            "candidate_ledger_promotion_gate_state_missing",
            "candidate_ledger must mirror the authoritative typed state",
        )
    elif isinstance(identity_gate_state, dict) and ledger_gate_state != identity_gate_state:
        _append_violation(
            violations,
            "candidate_ledger_promotion_gate_state_mismatch",
            "candidate_ledger typed state differs from identity typed state",
        )
    if not isinstance(identity_gate_evidence, list):
        _append_violation(
            violations,
            "promotion_gate_evidence_missing_for_shadow_recompute",
            "typed evidence is required for fail-closed shadow recompute",
        )
    if not isinstance(ledger_gate_evidence, list):
        _append_violation(
            violations,
            "candidate_ledger_promotion_gate_evidence_missing",
            "candidate_ledger must mirror the authoritative typed evidence",
        )
    elif isinstance(identity_gate_evidence, list) and ledger_gate_evidence != identity_gate_evidence:
        _append_violation(
            violations,
            "candidate_ledger_promotion_gate_evidence_mismatch",
            "candidate_ledger typed evidence differs from identity typed evidence",
        )
    if ledger_fingerprint != serialized_fingerprint:
        _append_violation(
            violations,
            "candidate_ledger_publish_contract_input_fingerprint_mismatch",
            "candidate_ledger input fingerprint differs from identity input fingerprint",
        )
    shadow_post_gate: dict[str, Any] = {}
    if promotion_gate_state:
        try:
            shadow_state = grounding_state_from_dict(promotion_gate_state)
            shadow_evidence = evidence_records_from_payload(promotion_gate_evidence)
            # Trace and ledger are serialized outputs, never shadow-recompute
            # inputs.  Using them here would let a forged trace validate itself.
            shadow_contract = evaluate_publish_contract(shadow_state, shadow_evidence)
        except (TypeError, ValueError) as exc:
            detail = str(exc)
            _append_violation(
                violations,
                (
                    "candidate_inventory_count_invalid_type"
                    if "candidate_inventory_count" in detail
                    else "promotion_gate_state_invalid_for_shadow_recompute"
                ),
                detail,
            )
        else:
            shadow_post_gate = _dict_or_empty(
                shadow_contract.trace.to_dict().get("post_gate_identity")
            )
            shadow_decision = shadow_contract.decision.to_dict()
            shadow_trace = shadow_contract.trace.to_dict()
            shadow_publish_ledger = build_publish_ledger(shadow_trace)
            if shadow_decision != decision:
                _append_violation(
                    violations,
                    "promotion_decision_shadow_recompute_mismatch",
                    "serialized PromotionDecision differs from state/evidence recomputation",
                )
            if not serialized_fingerprint:
                _append_violation(
                    violations,
                    "publish_contract_input_fingerprint_missing",
                    "authoritative contract lacks an input fingerprint",
                )
            elif serialized_fingerprint != shadow_contract.input_fingerprint:
                _append_violation(
                    violations,
                    "publish_contract_input_fingerprint_mismatch",
                    "serialized input fingerprint differs from state/evidence recomputation",
                )
            trace_fingerprint = str(_dict_or_empty(trace).get("input_fingerprint") or "").strip()
            if trace_fingerprint != shadow_contract.input_fingerprint:
                _append_violation(
                    violations,
                    "publish_contract_trace_input_fingerprint_mismatch",
                    "trace fingerprint differs from state/evidence recomputation",
                )
            if trace != shadow_trace:
                _append_violation(
                    violations,
                    "publish_contract_trace_shadow_recompute_mismatch",
                    "serialized publish_contract_trace differs from state/evidence recomputation",
                )
            if publish_ledger != shadow_publish_ledger:
                _append_violation(
                    violations,
                    "publish_ledger_shadow_recompute_mismatch",
                    "serialized publish_ledger differs from deterministic shadow trace",
                )

    if decision.get("bypassed_gate") is True:
        _append_violation(violations, "promotion_decision_bypassed_gate", "PromotionDecision bypassed_gate=true")
    if not _same_dict(candidate_decision, decision):
        _append_violation(
            violations,
            "candidate_ledger_promotion_decision_mismatch",
            "candidate_ledger.promotion_decision differs from identity.promotion_decision",
        )
    if isinstance(trace, dict) and not _same_dict(gate_decision, decision):
        _append_violation(
            violations,
            "publish_contract_trace_gate_decision_mismatch",
            "publish_contract_trace.gate_decision differs from PromotionDecision",
        )
    if isinstance(publish_ledger, dict) and not _same_dict(ledger_gate_decision, decision):
        _append_violation(
            violations,
            "publish_ledger_gate_decision_mismatch",
            "publish_ledger.gate_decision differs from PromotionDecision",
        )
    if isinstance(trace, dict) and not _same_dict(candidate_trace, trace):
        _append_violation(
            violations,
            "candidate_ledger_publish_contract_trace_mismatch",
            "candidate_ledger.publish_contract_trace differs from identity.publish_contract_trace",
        )
    if isinstance(publish_ledger, dict) and not _same_dict(candidate_publish_ledger, publish_ledger):
        _append_violation(
            violations,
            "candidate_ledger_publish_ledger_mismatch",
            "candidate_ledger.publish_ledger differs from identity.publish_ledger",
        )

    publish_allowed = decision.get("publish_allowed") is True
    status = str(decision.get("status") or "").strip()
    reason_codes = _reason_code_set(decision)
    reason_code_sources = [
        ("PromotionDecision.reason_codes", reason_codes),
        ("publish_contract_trace.reason_codes", _reason_code_set(trace) if isinstance(trace, dict) else set()),
        (
            "publish_contract_trace.gate_decision.reason_codes",
            _reason_code_set(gate_decision) if isinstance(gate_decision, dict) else set(),
        ),
        (
            "publish_ledger.gate_decision.reason_codes",
            _reason_code_set(ledger_gate_decision) if isinstance(ledger_gate_decision, dict) else set(),
        ),
        (
            "candidate_ledger.promotion_decision.reason_codes",
            _reason_code_set(candidate_decision) if isinstance(candidate_decision, dict) else set(),
        ),
        (
            "candidate_ledger.publish_contract_trace.reason_codes",
            _reason_code_set(candidate_trace) if isinstance(candidate_trace, dict) else set(),
        ),
    ]
    combined_scope_reason_codes: set[str] = set()
    mixed_sources: list[str] = []
    for source_name, source_codes in reason_code_sources:
        combined_scope_reason_codes.update(source_codes)
        if (
            source_codes & SCOPE_CURRENT_WORK_REASON_MARKERS
            and source_codes & SCOPE_NONCURRENT_REASON_MARKERS
        ):
            mixed_sources.append(source_name)
    current_scope_markers = sorted(combined_scope_reason_codes & SCOPE_CURRENT_WORK_REASON_MARKERS)
    noncurrent_scope_markers = sorted(combined_scope_reason_codes & SCOPE_NONCURRENT_REASON_MARKERS)
    if current_scope_markers and noncurrent_scope_markers:
        source_detail = f" sources={mixed_sources}" if mixed_sources else " sources=cross-source"
        _append_violation(
            violations,
            "mixed_current_noncurrent_scope_reason_codes",
            (
                "scope reason codes mix current-work markers "
                f"{current_scope_markers} with non-current markers {noncurrent_scope_markers};"
                f"{source_detail}"
            ),
        )
    decision_scope = _dict_or_empty(decision.get("scope"))
    trace_scope = _dict_or_empty(trace.get("scope_state")) if isinstance(trace, dict) else {}
    scope_kind = _scope_kind(decision_scope)
    if publish_allowed and status != "publish":
        _append_violation(violations, "publish_allowed_status_mismatch", "publish_allowed=true but status is not publish")
    if not publish_allowed and status == "publish":
        _append_violation(violations, "blocked_decision_status_publish", "publish_allowed=false but status=publish")
    if publish_allowed and decision.get("candidate_preserved") is True:
        _append_violation(
            violations,
            "publish_allowed_candidate_preserved_true",
            "publish_allowed=true but candidate_preserved=true",
        )
    if decision_scope and isinstance(trace, dict) and not _same_dict(trace_scope, decision_scope):
        _append_violation(
            violations,
            "publish_contract_trace_scope_state_mismatch",
            "publish_contract_trace.scope_state differs from PromotionDecision.scope",
        )
    if scope_kind:
        expected_scope_code = f"scope_{scope_kind}"
        if expected_scope_code not in reason_codes:
            _append_violation(
                violations,
                "promotion_decision_scope_reason_missing",
                f"PromotionDecision.scope.scope_kind={scope_kind} lacks reason code {expected_scope_code}",
            )
        if scope_kind == "current_work":
            if "scope_not_current_work" in reason_codes:
                _append_violation(
                    violations,
                    "scope_current_work_conflicts_with_not_current_reason",
                    "scope_kind=current_work conflicts with scope_not_current_work reason",
                )
        else:
            if "scope_current_work" in reason_codes:
                _append_violation(
                    violations,
                    "scope_non_current_conflicts_with_current_reason",
                    "non-current scope_kind conflicts with scope_current_work reason",
                )
            if not publish_allowed and "scope_not_current_work" not in reason_codes:
                _append_violation(
                    violations,
                    "blocked_non_current_scope_missing_not_current_reason",
                    "blocked non-current scope lacks scope_not_current_work reason",
                )
            if publish_allowed:
                _append_violation(
                    violations,
                    "publish_allowed_non_current_scope",
                    "publish_allowed=true with non-current PromotionDecision.scope",
                )
    if not publish_allowed and reason_codes & PUBLISH_ONLY_REASON_CODES:
        _append_violation(
            violations,
            "blocked_decision_has_publish_only_reason",
            "blocked decision still carries publish-only reason code",
        )
    if publish_allowed and "serialized_public_identity_scrubbed" in reason_codes:
        _append_violation(
            violations,
            "publish_allowed_has_scrubbed_reason",
            "publish_allowed=true still carries serialized_public_identity_scrubbed reason",
        )
    if "serialized_public_identity_published" in reason_codes and "serialized_public_identity_scrubbed" in reason_codes:
        _append_violation(
            violations,
            "published_and_scrubbed_reason_conflict",
            "decision carries both serialized_public_identity_published and serialized_public_identity_scrubbed",
        )

    post_gate = _dict_or_empty(trace.get("post_gate_identity")) if isinstance(trace, dict) else {}
    public_publish = _dict_or_empty(publish_ledger.get("public_publish")) if isinstance(publish_ledger, dict) else {}
    if shadow_post_gate:
        resolution_fields = (
            "title_resolution_allowed",
            "title_resolution_state",
            "work_resolution",
            "candidate_ledger_status",
        )
        for field in resolution_fields:
            expected_value = shadow_post_gate.get(field)
            if post_gate.get(field) != expected_value:
                _append_violation(
                    violations,
                    f"post_gate_identity_{field}_shadow_mismatch",
                    f"post_gate_identity.{field} differs from deterministic state/evidence recomputation",
                )
            if public_publish.get(field) != expected_value:
                _append_violation(
                    violations,
                    f"publish_ledger_{field}_shadow_mismatch",
                    f"publish_ledger.public_publish.{field} differs from deterministic state/evidence recomputation",
                )
            if identity.get(field) != expected_value:
                _append_violation(
                    violations,
                    f"serialized_identity_{field}_shadow_mismatch",
                    f"identity.{field} differs from deterministic state/evidence recomputation",
                )
            if ledger.get(field) != expected_value:
                _append_violation(
                    violations,
                    f"candidate_ledger_{field}_shadow_mismatch",
                    f"candidate_ledger.{field} differs from deterministic state/evidence recomputation",
                )
    expected_title = _string_or_none(decision.get("official_title"))
    expected_url = _string_or_none(decision.get("official_url"))
    gate_scope = _dict_or_empty(promotion_gate_state.get("scope"))
    image_direct_sources = _direct_bridge_sources(decision_scope, trace_scope, gate_scope)
    image_anchor_context = bool(
        reason_codes & IMAGE_DIRECT_WORK_REASON_CODES
        or image_direct_sources & IMAGE_DIRECT_WORK_REASON_CODES
    )
    if publish_allowed and IMAGE_UNVERIFIED_REASON_CODE in reason_codes:
        _append_violation(
            violations,
            "image_unverified_reason_allows_publish",
            "unverified image/OCR public-title reason must not allow public publication",
        )
    if (
        publish_allowed
        and image_anchor_context
        and not expected_url
        and IMAGE_TITLE_ONLY_PUBLISH_REASON_CODE in reason_codes
        and not _matching_verified_image_work_title(identity, ledger, expected_title)
    ):
        _append_violation(
            violations,
            "verified_image_ocr_publication_missing_verified_evidence",
            "verified image/OCR title-only publication lacks a matching promotion_eligible work-title evidence item",
        )
    url_title_mismatch_block = bool(reason_codes & URL_TITLE_MISMATCH_BLOCK_REASON_CODES)
    if url_title_mismatch_block:
        preserved_url_sources = [
            pre_gate_candidate,
            ledger_candidate_preservation,
            {
                "official_title": identity.get("blocked_official_title"),
                "official_url": identity.get("blocked_official_title_url"),
            },
            {
                "official_title": ledger.get("blocked_official_title"),
                "official_url": ledger.get("blocked_official_title_url"),
            },
        ]
        if publish_allowed:
            _append_violation(
                violations,
                "url_title_mismatch_block_reason_allows_publish",
                "url-title mismatch block reason must not allow public title publication",
            )
        if expected_url:
            _append_violation(
                violations,
                "url_title_mismatch_block_reason_has_decision_url",
                "url-title mismatch block reason must keep the URL only as a preserved candidate",
            )
        if not any(_string_or_none(_dict_or_empty(source).get("official_url")) for source in preserved_url_sources):
            _append_violation(
                violations,
                "url_title_mismatch_candidate_url_not_preserved",
                "url-title mismatch block reason must preserve the blocked candidate URL in trace, ledger, or blocked fields",
            )
    if URL_WITHHELD_REASON_CODE in reason_codes:
        if expected_url:
            _append_violation(
                violations,
                "official_url_withheld_reason_has_decision_url",
                "official_url_withheld_by_title_mismatch must keep official_url out of PromotionDecision",
            )
        if _string_or_none(post_gate.get("official_url")):
            _append_violation(
                violations,
                "official_url_withheld_reason_publishes_trace_url",
                "official_url_withheld_by_title_mismatch must keep official_url out of publish_contract_trace.post_gate_identity",
            )
        if _string_or_none(public_publish.get("official_url")):
            _append_violation(
                violations,
                "official_url_withheld_reason_publishes_ledger_url",
                "official_url_withheld_by_title_mismatch must keep official_url out of publish_ledger.public_publish",
            )
        if public_identity["official_url"]:
            _append_violation(
                violations,
                "official_url_withheld_reason_serialized_url_leak",
                "official_url_withheld_by_title_mismatch must keep official_url out of serialized public identity",
            )
    if publish_allowed:
        if not expected_title:
            _append_violation(violations, "publish_allowed_missing_official_title", "allowed decision lacks official_title")
        if _string_or_none(post_gate.get("official_title")) != expected_title:
            _append_violation(
                violations,
                "post_gate_identity_title_mismatch",
                "post_gate_identity.official_title does not match allowed decision",
            )
        if _string_or_none(post_gate.get("official_url")) != expected_url:
            _append_violation(
                violations,
                "post_gate_identity_url_mismatch",
                "post_gate_identity.official_url does not match allowed decision",
            )
        if _string_or_none(public_publish.get("official_title")) != expected_title:
            _append_violation(
                violations,
                "publish_ledger_public_title_mismatch",
                "publish_ledger.public_publish.official_title does not match allowed decision",
            )
        if public_identity["official_title"] != expected_title:
            _append_violation(
                violations,
                "serialized_public_title_mismatch",
                "serialized official_title does not match allowed decision",
            )
    else:
        blocked_candidate_title = _candidate_title_from_sources(
            pre_gate_candidate,
            ledger_candidate_preservation,
            {
                "official_title": identity.get("blocked_official_title"),
                "official_url": identity.get("blocked_official_title_url"),
            },
            {
                "official_title": ledger.get("blocked_official_title"),
                "official_url": ledger.get("blocked_official_title_url"),
            },
        )
        blocked_current_work = bool(scope_kind == "current_work" or "scope_current_work" in reason_codes)
        blocked_row_discusses = bool("row_discusses_work_as_work" in reason_codes)
        blocked_official_exists = bool("official_title_exists" in reason_codes)
        if (
            image_anchor_context
            and blocked_candidate_title
            and blocked_current_work
            and blocked_row_discusses
            and blocked_official_exists
            and not (reason_codes & IMAGE_HARD_HOLD_REASON_CODES)
            and _matching_verified_image_work_title(identity, ledger, blocked_candidate_title)
        ):
            _append_violation(
                violations,
                "verified_image_ocr_work_title_blocked_by_precision_review",
                "promotion_eligible image/OCR work-title current-work candidate is still blocked instead of title-only publication",
            )
        no_candidate_hold = bool(reason_codes & NO_CANDIDATE_REASON_CODES)
        candidate_preservation_expected = (
            decision.get("candidate_preserved") is True
            or ("serialized_public_identity_scrubbed" in reason_codes and not no_candidate_hold)
        )
        candidate_preservation_sources = [
            pre_gate_candidate,
            ledger_candidate_preservation,
            {
                "official_title": identity.get("blocked_official_title"),
                "official_url": identity.get("blocked_official_title_url"),
            },
            {
                "official_title": ledger.get("blocked_official_title"),
                "official_url": ledger.get("blocked_official_title_url"),
            },
        ]
        inventory_mirrors = {}
        if "title_candidates" in identity or "candidate_preservation_sources" in identity:
            inventory_mirrors["identity"] = (
                identity.get("title_candidates"),
                identity.get("candidate_preservation_sources"),
            )
        if "title_candidates" in ledger or "candidate_preservation_sources" in ledger:
            inventory_mirrors["candidate_ledger"] = (
                ledger.get("title_candidates"),
                ledger.get("candidate_preservation_sources"),
            )
        actual_inventory = candidate_inventory_evidence_from_sources(
            *(
                payload
                for mirror_payloads in inventory_mirrors.values()
                for payload in mirror_payloads
            )
        )
        typed_inventory = candidate_inventory_records(
            evidence_records_from_payload(promotion_gate_evidence)
        )
        raw_inventory_count = promotion_gate_state.get("candidate_inventory_count", 0)
        typed_inventory_count = (
            raw_inventory_count
            if isinstance(raw_inventory_count, int)
            and not isinstance(raw_inventory_count, bool)
            and raw_inventory_count >= 0
            else -1
        )
        actual_inventory_pairs = candidate_inventory_pairs(actual_inventory)
        typed_inventory_pairs = candidate_inventory_pairs(typed_inventory)
        # A URL-only pre-gate payload is still an unselected inventory when
        # typed state has no candidate title.  Treating the URL as a selected
        # candidate skipped payload validation and undercounted mismatches.
        inventory_only_contract = bool(
            not str(promotion_gate_state.get("candidate_title") or "").strip()
            and (
                typed_inventory_count > 0
                or bool(typed_inventory)
                or bool(actual_inventory)
                or bool(str(promotion_gate_state.get("candidate_url") or "").strip())
            )
        )
        if inventory_only_contract and typed_inventory_count != len(typed_inventory):
            _append_violation(
                violations,
                "candidate_inventory_count_evidence_mismatch",
                "typed candidate_inventory_count differs from preservation evidence count",
            )
        if inventory_only_contract and actual_inventory_pairs != typed_inventory_pairs:
            _append_violation(
                violations,
                "candidate_inventory_payload_mismatch",
                "typed preservation evidence differs from identity/candidate-ledger inventory",
            )
        if inventory_only_contract:
            for mirror_name, mirror_payloads in inventory_mirrors.items():
                mirror_pairs = candidate_inventory_pairs(
                    candidate_inventory_evidence_from_sources(*mirror_payloads)
                )
                if mirror_pairs != typed_inventory_pairs:
                    _append_violation(
                        violations,
                        "candidate_inventory_mirror_payload_mismatch",
                        f"{mirror_name} differs from typed preservation evidence",
                    )
        titleless_payload_present = bool(
            actual_inventory
            or str(promotion_gate_state.get("candidate_url") or "").strip()
        )
        if inventory_only_contract and titleless_payload_present and decision.get("candidate_preserved") is not True:
            _append_violation(
                violations,
                "candidate_inventory_not_marked_preserved",
                "candidate inventory exists but PromotionDecision.candidate_preserved is not true",
            )
        if inventory_only_contract and titleless_payload_present and status != "candidate_only":
            _append_violation(
                violations,
                "candidate_inventory_status_mismatch",
                "unselected candidate inventory must use status=candidate_only",
            )
        if (
            inventory_only_contract
            and titleless_payload_present
            and post_gate.get("candidate_ledger_status") != "promotion_blocked"
        ):
            _append_violation(
                violations,
                "candidate_inventory_ledger_status_mismatch",
                "unselected candidate inventory must serialize candidate_ledger_status=promotion_blocked",
            )
        candidate_preserved_payload_present = any(
            _has_candidate_payload(source) for source in candidate_preservation_sources
        ) or bool(inventory_only_contract and actual_inventory)
        if (
            "serialized_public_identity_scrubbed" in reason_codes
            and not no_candidate_hold
            and decision.get("candidate_preserved") is not True
        ):
            _append_violation(
                violations,
                "scrubbed_decision_not_candidate_preserved",
                "serialized_public_identity_scrubbed decision with a candidate must mark candidate_preserved=true",
            )
        if candidate_preservation_expected and not candidate_preserved_payload_present:
            _append_violation(
                violations,
                "blocked_candidate_preservation_missing",
                "blocked/scrubbed decision does not preserve the candidate in trace, ledger, or blocked title fields",
            )
        if (
            isinstance(trace, dict)
            and isinstance(publish_ledger, dict)
            and _has_candidate_payload(pre_gate_candidate)
            and _has_candidate_payload(ledger_candidate_preservation)
            and _candidate_title_url(pre_gate_candidate) != _candidate_title_url(ledger_candidate_preservation)
        ):
            _append_violation(
                violations,
                "candidate_preservation_trace_ledger_mismatch",
                "publish_ledger.candidate_preservation differs from publish_contract_trace.pre_gate_candidate",
            )
        if _string_or_none(post_gate.get("official_title")):
            _append_violation(violations, "blocked_trace_publishes_title", "blocked trace still publishes title")
        if _string_or_none(post_gate.get("official_url")):
            _append_violation(violations, "blocked_trace_publishes_url", "blocked trace still publishes url")
        if _string_or_none(public_publish.get("official_title")):
            _append_violation(violations, "blocked_ledger_publishes_title", "blocked publish ledger still publishes title")
        if _string_or_none(public_publish.get("official_url")):
            _append_violation(violations, "blocked_ledger_publishes_url", "blocked publish ledger still publishes url")
        if public_identity["official_title"]:
            _append_violation(
                violations,
                "blocked_serialized_public_title_leak",
                "blocked decision still has serialized public official_title",
            )
        if public_identity["official_url"]:
            _append_violation(
                violations,
                "blocked_serialized_public_url_leak",
                "blocked decision still has serialized public official_url",
            )

    return {
        "index": index,
        "post_id": post_id,
        "gate": "NO-GO" if violations else "GO",
        "public_identity": public_identity,
        "decision": {
            "status": status,
            "publish_allowed": publish_allowed,
            "official_title": expected_title,
            "official_url": expected_url,
        },
        "violations": violations,
    }


def _input_post_ids(values: Any) -> list[str]:
    """Extract post ids from legacy scalar/list/object panel inputs."""
    if isinstance(values, dict):
        for key in ("post_ids", "expected_post_ids", "rows", "items", "data", "results"):
            if key in values:
                return _input_post_ids(values[key])
        value = values.get("post_id")
        return [str(value).strip()] if value not in (None, "") else []
    if isinstance(values, (list, tuple, set)):
        result: list[str] = []
        for item in values:
            result.extend(_input_post_ids(item))
        return result
    if values not in (None, ""):
        return [str(values).strip()]
    return []


def audit_rows(
    rows: list[dict[str, Any]],
    *,
    expected_post_ids: Any = None,
    panel_rows: Any = None,
) -> dict[str, Any]:
    row_reports = [audit_row(row, index=index) for index, row in enumerate(rows, start=1)]
    # Exact-once is fail-closed from the result rows alone.  Duplicate
    # non-empty ids are always a publication-contract violation (never GO).
    seen: dict[str, int] = {}
    duplicate_post_ids: list[str] = []
    for index, row in enumerate(rows, start=1):
        post_id = row_post_id(row)
        if not post_id:
            continue
        if post_id in seen:
            duplicate_post_ids.append(post_id)
            row_reports[index - 1]["violations"].append(
                {"code": "duplicate_post_id", "detail": f"post_id {post_id} also appears at row {seen[post_id]}"}
            )
        else:
            seen[post_id] = index

    expected_ids = _input_post_ids(expected_post_ids)
    panel_ids = _input_post_ids(panel_rows) if panel_rows is not None else []
    coverage_violations: list[dict[str, Any]] = []
    if expected_ids or panel_rows is not None:
        expected_set = set(expected_ids or panel_ids)
        actual_set = set(seen)
        missing = sorted(expected_set - actual_set)
        orphan = sorted(actual_set - expected_set)
        expected_dupes = sorted({pid for pid in expected_ids if expected_ids.count(pid) > 1})
        panel_dupes = sorted({pid for pid in panel_ids if panel_ids.count(pid) > 1})
        if missing:
            coverage_violations.append({"code": "expected_post_id_missing", "detail": f"missing post_ids: {missing}"})
        if orphan:
            coverage_violations.append({"code": "orphan_post_id", "detail": f"rows outside expected/panel scope: {orphan}"})
        if expected_dupes or panel_dupes:
            coverage_violations.append({"code": "expected_post_id_duplicate", "detail": f"duplicate expected/panel ids: {sorted(set(expected_dupes + panel_dupes))}"})
    if coverage_violations:
        row_reports.append({"index": 0, "post_id": "", "gate": "NO-GO", "public_identity": {}, "violations": coverage_violations})
    violations = [item for item in row_reports if item["violations"]]
    counts = Counter(
        violation["code"]
        for item in row_reports
        for violation in item["violations"]
    )
    return {
        "report_type": "publication_contract_convergence_audit",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "gate": "GO" if not violations else "NO-GO",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "exact_once": {
            "status": "NOT_PROVABLE",
            "reason": "no verified durable receipt/sidecar audit supplied; semantic convergence is not exact-once proof",
            "duplicate_post_ids": sorted(set(duplicate_post_ids)),
        },
        "policy": {
            "typed_promotion_decision_required_for_every_row": True,
            "promotion_decision_trace_ledger_serialized_identity_must_converge": True,
            "trace_and_publish_ledger_must_equal_state_evidence_shadow": True,
            "each_present_candidate_inventory_mirror_group_must_equal_typed_inventory": True,
            "blocked_decision_must_not_publish_serialized_public_identity": True,
            "allowed_decision_must_match_serialized_public_identity": True,
            "scrubbed_candidate_must_be_preserved_or_marked_no_candidate": True,
            "promotion_decision_scope_must_match_trace_and_reason_codes": True,
            "blocked_decision_must_not_carry_publish_only_reason_codes": True,
            "url_title_mismatch_block_must_preserve_candidate_url_without_publication": True,
            "official_url_withheld_reason_must_not_publish_url": True,
            "verified_image_ocr_work_title_current_work_candidate_must_not_remain_precision_blocked": True,
            "mixed_current_and_noncurrent_scope_reason_codes_must_be_normalized": True,
            "non_empty_post_ids_must_be_unique": True,
            "typed_state_post_id_must_match_row_post_id_when_present": True,
            "exact_once_requires_verified_sidecar_audit": True,
        },
        "summary": {
            "row_count": len(row_reports),
            "violation_row_count": len(violations),
            "violation_counts": dict(counts.most_common()),
        },
        "violations": violations[:100],
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Publication contract convergence 감사",
        "",
        f"- gate: `{report['gate']}`",
        f"- semantic_quality: `{report['semantic_quality']}`",
        f"- full_scan_approval: `{str(report['full_scan_approval']).lower()}`",
        "- 정책: `PromotionDecision`, `publish_contract_trace`, `publish_ledger`, serialized public identity는 같은 publish/block 결론으로 수렴해야 한다.",
        "- 정책: 모든 행에 typed `PromotionDecision`이 있어야 하며, trace/ledger는 state+evidence shadow와 정확히 일치해야 한다.",
        "- 정책: 존재하는 top-level/candidate-ledger 후보 inventory 묶음은 각각 typed inventory와 같아야 한다.",
        "- 정책: `serialized_public_identity_scrubbed`는 후보가 있으면 candidate ledger/trace에 보존하고, 후보가 없으면 `hold_without_candidates` 같은 no-candidate reason을 남겨야 한다.",
        "- 정책: `PromotionDecision.scope`는 `publish_contract_trace.scope_state`와 일치해야 하며, scope reason code와 publish/block reason code가 충돌하면 안 된다.",
        "- 정책: current-work marker와 non-current/context marker가 reason source 안이나 source 사이에 함께 남으면 mixed trace로 보고 정규화해야 한다.",
        "- 정책: URL/title mismatch block은 후보 URL을 보존하되 public decision/trace/ledger/serialized identity로 URL을 publish하지 않아야 한다.",
        "- 정책: `official_url_withheld_by_title_mismatch`는 제목 publish만 허용하고 URL은 pre-gate 후보로만 남겨야 한다.",
        "- 정책: `promotion_eligible=true`인 이미지/OCR work-title 후보가 current-work shared gate를 충족하면 title-only publish로 수렴해야 하며, 직접 제목 앵커가 없는 이미지는 candidate_only로 남아야 한다.",
        "",
        "## 요약",
        "",
        f"- row_count: `{report['summary']['row_count']}`",
        f"- violation_row_count: `{report['summary']['violation_row_count']}`",
        f"- violation_counts: `{report['summary']['violation_counts']}`",
        "",
    ]
    result_artifacts = report.get("result_artifacts")
    if isinstance(result_artifacts, list) and result_artifacts:
        lines.extend(["## 입력 artifact binding", ""])
        for artifact in result_artifacts:
            lines.extend(
                [
                    f"- path: `{artifact.get('path')}`",
                    f"  - sha256: `{artifact.get('sha256')}`",
                    f"  - size_bytes: `{artifact.get('size_bytes')}`",
                    f"  - row_count: `{artifact.get('row_count')}`",
                ]
            )
        lines.append("")
    if report["violations"]:
        lines.extend(["## 위반 샘플", ""])
        for item in report["violations"][:20]:
            lines.extend(
                [
                    f"### row {item['index']} post_id `{item['post_id']}`",
                    "",
                    f"- public_identity: `{item['public_identity']}`",
                    f"- decision: `{item.get('decision')}`",
                    "- violations:",
                ]
            )
            for violation in item["violations"]:
                lines.append(f"  - `{violation['code']}`: {violation['detail']}")
            lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit publication contract convergence in result rows.")
    parser.add_argument("--result", required=True, type=Path, action="append")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-no-go", action="store_true")
    # Optional legacy-compatible scope inputs.  They are only coverage
    # references; they do not claim durable receipt/exact-once proof.
    parser.add_argument("--expected-post-ids", type=Path)
    parser.add_argument("--panel-input", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    loaded_results = [
        (result_path, load_rows(result_path))
        for result_path in args.result
    ]
    rows = [row for _, result_rows in loaded_results for row in result_rows]
    expected_post_ids = load_json(args.expected_post_ids) if args.expected_post_ids else None
    panel_rows = load_rows(args.panel_input) if args.panel_input else None
    report = audit_rows(rows, expected_post_ids=expected_post_ids, panel_rows=panel_rows)
    report["result_paths"] = [str(path) for path in args.result]
    report["result_artifacts"] = [
        build_result_artifact_binding(result_path, row_count=len(result_rows))
        for result_path, result_rows in loaded_results
    ]
    write_json(args.output_json, report)
    write_markdown(report, args.output_md)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.fail_on_no_go and report["gate"] != "GO":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
