"""Compile zero-input Actual-P0 blockers without granting execution authority.

The result is a diagnostic receipt only.  It invokes the existing Windows
owner-provisioning preflight once, validates that candidate receipt, and
compares two point-in-time projections of the fixed local Slang/publication
endpoints.  Neither a Python checksum nor equal pre/post projections is a
signed native observation, continuous watch, transient-write exclusion,
runtime noninterference proof, or permission to capture the actual 40+20 pilot.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
import re
from typing import Any, Mapping

from . import p0_windows_owner_provisioning_preflight_candidate as preflight


RECEIPT_SCHEMA = "p0_actual_readiness_blocker_compilation_receipt_v1"
GATE_STATUS = "ACTUAL_READINESS_BLOCKERS_COMPILED_AUTHORITY_NO_GO"
OPERATIONAL_EFFECT = "NONE_BLOCKER_COMPILATION_ONLY"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CENTRAL_SLANG_DB = _REPO_ROOT / "slang_db" / "slang_db.json"
_PUBLICATION_JOURNAL_DIRECTORY = (
    _REPO_ROOT / "out" / "publication_commit_journals"
)

_EXPECTED_SOURCE_PROFILES = (
    "OFFICIAL_STRUCTURED",
    "COMMUNITY_STRUCTURED",
    "MEDIA_OCR",
    "GENERIC_FALLBACK",
)
_EXPECTED_PER_PROFILE_QUOTA = 10
_EXPECTED_SOURCE_CLAIMS = 40
_EXPECTED_A_CONTEXT_REVIEWS = 20
_REQUIRED_ACTUAL_WATCH_CATEGORIES = (
    "CENTRAL_SLANG_DB",
    "CHECKPOINT",
    "DECISION_LEDGER",
    "PUBLICATION_JOURNAL",
    "RECOVERY",
    "RESULT",
)

_PREFLIGHT_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "gate_status",
        "decision",
        "failure_stage",
        "blocker_codes",
        "candidate_only",
        "zero_input_public_api_verified",
        "caller_supplied_selector_absent",
        "fixed_policy_store_candidate_observed",
        "owner_policy_v2_contract_verified",
        "v1_future_authority_hard_rejected",
        "bootstrap_signature_mathematics_verified",
        "deployment_projection_cross_binding_verified",
        "service_configuration_candidate_verified",
        "service_image_identity_candidate_verified",
        "service_configuration_projection",
        "service_image_identity_projection",
        "service_process_token_verified",
        "embedded_bootstrap_resource_verified",
        "trusted_verifier_code_identity_verified",
        "wdac_umci_enforced_verified",
        "wdac_policy_identity_hash_verified",
        "loaded_cng_provider_identity_verified",
        "trusted_cng_provider_provenance_verified",
        "trusted_time_verified",
        "revocation_current_verified",
        "signed_native_observer_receipt_verified",
        "single_interval_store_host_cross_binding_verified",
        "serialized_receipt_authoritative",
        "external_owner_policy_provisioning_verified",
        "external_code_authority_verified",
        "owner_authority_verified",
        "actual_authority_granted",
        "actual_semantic_evidence_verified",
        "production_approval",
        "full_scan_approval",
        "p0_phase_exit",
        "action_applied",
        "protected_pipeline_state_mutated",
        "credited_actual_source_claim_count",
        "credited_actual_a_context_review_count",
        "operational_effect",
        "receipt_sha256",
    }
)
_PREFLIGHT_OBSERVATION_FIELDS = (
    "fixed_policy_store_candidate_observed",
    "owner_policy_v2_contract_verified",
    "v1_future_authority_hard_rejected",
    "bootstrap_signature_mathematics_verified",
    "deployment_projection_cross_binding_verified",
    "service_configuration_candidate_verified",
    "service_image_identity_candidate_verified",
)
_PREFLIGHT_ALWAYS_FALSE_FIELDS = (
    "service_process_token_verified",
    "embedded_bootstrap_resource_verified",
    "trusted_verifier_code_identity_verified",
    "wdac_umci_enforced_verified",
    "wdac_policy_identity_hash_verified",
    "loaded_cng_provider_identity_verified",
    "trusted_cng_provider_provenance_verified",
    "trusted_time_verified",
    "revocation_current_verified",
    "signed_native_observer_receipt_verified",
    "single_interval_store_host_cross_binding_verified",
    "serialized_receipt_authoritative",
    "external_owner_policy_provisioning_verified",
    "external_code_authority_verified",
    "owner_authority_verified",
    "actual_authority_granted",
    "actual_semantic_evidence_verified",
    "production_approval",
    "full_scan_approval",
    "p0_phase_exit",
    "action_applied",
    "protected_pipeline_state_mutated",
)
_PREFLIGHT_BLOCKER_ORDER = (
    "FIXED_OWNER_POLICY_STORE_NOT_VERIFIED",
    "OWNER_POLICY_V2_NOT_VERIFIED",
    "SERVICE_CONFIGURATION_NOT_VERIFIED",
    "SERVICE_IMAGE_IDENTITY_NOT_VERIFIED",
    "SERVICE_PROCESS_TOKEN_NOT_VERIFIED",
    "EMBEDDED_BOOTSTRAP_RESOURCE_NOT_VERIFIED",
    "AUTHENTICODE_NOT_VERIFIED",
    "WDAC_UMCI_NOT_VERIFIED",
    "LOADED_CNG_PROVIDER_NOT_VERIFIED",
    "TRUSTED_TIME_REVOCATION_NOT_VERIFIED",
    "SIGNED_NATIVE_OBSERVER_NOT_VERIFIED",
    "SINGLE_INTERVAL_STORE_HOST_BINDING_NOT_VERIFIED",
    "EXTERNAL_OWNER_PROVISIONING_NOT_VERIFIED",
)
_PREFLIGHT_DOWNSTREAM_BLOCKERS = frozenset(_PREFLIGHT_BLOCKER_ORDER[4:])
_PREFLIGHT_STAGE_STATES = {
    "FIXED_STORE": ((False, False, False, False, False, False, False),),
    "OWNER_POLICY_V2": (
        (True, False, False, False, False, False, False),
        (True, False, True, False, False, False, False),
    ),
    "SERVICE_CONFIGURATION": ((True, True, True, True, True, False, False),),
    "SERVICE_IMAGE": ((True, True, True, True, True, True, False),),
    "NATIVE_EXTERNAL_EVIDENCE": ((True, True, True, True, True, True, True),),
}

_BASE_BLOCKER_ORDER = (
    "OWNER_PROVISIONING_PREFLIGHT_NO_GO",
    "SIGNED_NATIVE_OBSERVER_NOT_VERIFIED",
    "EXTERNAL_OWNER_TRUST_NOT_VERIFIED",
    "TRUSTED_TIME_NOT_VERIFIED",
    "REVOCATION_CURRENT_NOT_VERIFIED",
    "DURABLE_CROSS_PROCESS_NONCE_NOT_VERIFIED",
    "PROTECTED_ROOT_OWNER_PINS_NOT_VERIFIED",
    "PROTECTED_WATCH_6_CATEGORY_COVERAGE_NOT_VERIFIED",
    "PROCESS_WIDE_WRITE_DENY_NOT_VERIFIED",
    "AUTHORITY_JOURNAL_WATCH_BUNDLE_NOT_VERIFIED",
    "RUNTIME_NONINTERFERENCE_NOT_VERIFIED",
    "PARSER_RUNTIME_NOT_RUN",
    "ACTUAL_POLICY_AUTHORITY_NOT_VERIFIED",
    "ACTUAL_CAPTURE_RIGHTS_POLICY_NOT_AUTHORIZED",
    "ACTUAL_SAMPLING_PLAN_NOT_AUTHORIZED",
    "ACTUAL_ANNOTATION_GUIDELINE_NOT_AUTHORIZED",
    "ACTUAL_REVIEWER_ASSIGNMENT_NOT_AUTHORIZED",
    "ACTUAL_ANNOTATION_DURABLE_PREDECESSOR_NOT_VERIFIED",
    "ACTUAL_ANNOTATION_APPEND_ONLY_NOT_VERIFIED",
    "ACTUAL_SOURCE_CLAIMS_CREDITED_0_OF_40",
    "ACTUAL_A_CONTEXT_REVIEWS_CREDITED_0_OF_20",
    "ACTUAL_SEMANTIC_EVIDENCE_NOT_VERIFIED",
    "P1_RETRIEVAL_RERANKER_NIL_SHADOW_BLOCKED_BY_P0",
    "BLOCKER_ONLY_COMPILER_NOT_AUTHORITY",
)
_FALSE_OUTPUT_FIELDS = (
    "capture_execution_authorized",
    "runtime_execution_entrypoint_invoked",
    "process_spawned",
    "service_started",
    "nonce_consumption_invoked",
    "publication_wal_write_invoked_by_compiler",
    "central_slang_db_write_invoked_by_compiler",
    "action_applied",
    "protected_pipeline_state_mutated",
    "host_preflight_freshness_verified",
    "signed_native_observer_receipt_verified",
    "external_owner_trust_verified",
    "trusted_time_verified",
    "revocation_current_verified",
    "durable_cross_process_nonce_verified",
    "protected_root_owner_pins_verified",
    "protected_watch_six_category_coverage_verified",
    "process_wide_write_deny_verified",
    "authority_journal_watch_bundle_verified",
    "continuous_runtime_noninterference_verified",
    "transient_write_absence_verified",
    "runtime_noninterference_verified",
    "parser_runtime_verified",
    "actual_policy_authority_verified",
    "actual_annotation_durable_predecessor_verified",
    "actual_annotation_append_only_verified",
    "actual_authority_granted",
    "actual_semantic_evidence_verified",
    "p0_phase_exit",
    "production_approval",
    "full_scan_approval",
    "serialized_receipt_authoritative",
)

_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_HEX_32 = re.compile(r"^[0-9a-f]{32}$")


class _InvalidPreflightReceipt(ValueError):
    pass


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_projection(path: Path, kind: str) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    try:
        relative = resolved.relative_to(_REPO_ROOT.resolve(strict=True))
    except ValueError as exc:
        raise ValueError("fixed endpoint escaped repository root") from exc
    before = resolved.stat()
    digest = hashlib.sha256()
    with resolved.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    after = resolved.stat()
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
    ):
        raise ValueError("fixed endpoint changed during snapshot")
    return {
        "kind": kind,
        "path": relative.as_posix(),
        "bytes": after.st_size,
        "mtime_ns": after.st_mtime_ns,
        "sha256": digest.hexdigest(),
    }


def _snapshot_fixed_local_endpoints() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    slang_present = _CENTRAL_SLANG_DB.is_file()
    if slang_present:
        rows.append(_file_projection(_CENTRAL_SLANG_DB, "CENTRAL_SLANG_DB"))
    journals: list[Path] = []
    if _PUBLICATION_JOURNAL_DIRECTORY.is_dir():
        journals = sorted(
            (
                path
                for path in _PUBLICATION_JOURNAL_DIRECTORY.iterdir()
                if path.is_file() and path.suffix.casefold() == ".jsonl"
            ),
            key=lambda path: path.name.casefold(),
        )
    rows.extend(
        _file_projection(path, "PUBLICATION_JOURNAL") for path in journals
    )
    required_present = slang_present and bool(journals)
    return {
        "snapshot_succeeded": True,
        "required_local_endpoint_kinds_present": required_present,
        "projection": rows,
        "projection_sha256": _canonical_sha256(rows),
    }


def _safe_snapshot_fixed_local_endpoints() -> dict[str, Any]:
    try:
        return _snapshot_fixed_local_endpoints()
    except Exception:
        empty: list[dict[str, Any]] = []
        return {
            "snapshot_succeeded": False,
            "required_local_endpoint_kinds_present": False,
            "projection": empty,
            "projection_sha256": _canonical_sha256(empty),
        }


def _expected_preflight_blockers(state: tuple[bool, ...]) -> list[str]:
    structural_verified = {
        "FIXED_OWNER_POLICY_STORE_NOT_VERIFIED": state[0],
        "OWNER_POLICY_V2_NOT_VERIFIED": state[1],
        "SERVICE_CONFIGURATION_NOT_VERIFIED": state[5],
        "SERVICE_IMAGE_IDENTITY_NOT_VERIFIED": state[6],
    }
    return [
        blocker
        for blocker in _PREFLIGHT_BLOCKER_ORDER
        if (
            blocker in _PREFLIGHT_DOWNSTREAM_BLOCKERS
            or structural_verified.get(blocker) is False
        )
    ]


def _validate_service_projection(value: Any) -> bool:
    if type(value) is not dict or set(value) != {
        "service_name",
        "service_type",
        "service_start_type",
        "service_error_control",
        "service_sid_type",
        "service_start_account_sid",
        "service_binary_path_argv_policy",
        "raw_binary_path_sha256",
    }:
        return False
    return (
        value["service_name"] == "llm-novel-dc-p0-owner-verifier-v2"
        and value["service_type"] == "SERVICE_WIN32_OWN_PROCESS"
        and value["service_start_type"] == "SERVICE_DEMAND_START"
        and value["service_error_control"] == "SERVICE_ERROR_NORMAL"
        and value["service_sid_type"] == "SERVICE_SID_TYPE_RESTRICTED"
        and value["service_start_account_sid"] == "S-1-5-18"
        and value["service_binary_path_argv_policy"]
        == "EXACT_QUOTED_IMAGE_PATH_NO_ARGUMENTS"
        and type(value["raw_binary_path_sha256"]) is str
        and _HEX_64.fullmatch(value["raw_binary_path_sha256"]) is not None
    )


def _validate_image_projection(value: Any) -> bool:
    if type(value) is not dict or set(value) != {
        "final_volume_guid_path",
        "volume_serial_decimal",
        "file_id_128_hex",
        "image_sha256",
        "held_handle_pre_post_stable",
        "single_link_non_reparse_unnamed_stream_verified",
        "handle_non_inheritable_verified",
    }:
        return False
    return (
        type(value["final_volume_guid_path"]) is str
        and value["final_volume_guid_path"].startswith("\\\\?\\Volume{")
        and type(value["volume_serial_decimal"]) is str
        and value["volume_serial_decimal"].isdigit()
        and type(value["file_id_128_hex"]) is str
        and _HEX_32.fullmatch(value["file_id_128_hex"]) is not None
        and type(value["image_sha256"]) is str
        and _HEX_64.fullmatch(value["image_sha256"]) is not None
        and value["held_handle_pre_post_stable"] is True
        and value["single_link_non_reparse_unnamed_stream_verified"] is True
        and value["handle_non_inheritable_verified"] is True
    )


def _validate_same_call_preflight_receipt(receipt: Any) -> dict[str, Any]:
    if type(receipt) is not dict or set(receipt) != _PREFLIGHT_RECEIPT_FIELDS:
        raise _InvalidPreflightReceipt("field inventory mismatch")
    if (
        receipt["schema_version"]
        != "p0_windows_owner_provisioning_preflight_candidate_receipt_v1"
        or receipt["gate_status"]
        != "WINDOWS_OWNER_PROVISIONING_PREFLIGHT_CANDIDATE_EXECUTED_HOST_AND_EXTERNAL_PROVISIONING_NO_GO"
        or receipt["decision"] != "NO_GO"
        or receipt["candidate_only"] is not True
        or receipt["zero_input_public_api_verified"] is not True
        or receipt["caller_supplied_selector_absent"] is not True
        or receipt["operational_effect"] != "NONE_SHADOW_ONLY"
        or any(receipt[field] is not False for field in _PREFLIGHT_ALWAYS_FALSE_FIELDS)
        or type(receipt["credited_actual_source_claim_count"]) is not int
        or receipt["credited_actual_source_claim_count"] != 0
        or type(receipt["credited_actual_a_context_review_count"]) is not int
        or receipt["credited_actual_a_context_review_count"] != 0
    ):
        raise _InvalidPreflightReceipt("fixed candidate contract mismatch")
    stage = receipt["failure_stage"]
    if type(stage) is not str or stage not in _PREFLIGHT_STAGE_STATES:
        raise _InvalidPreflightReceipt("failure stage mismatch")
    observed_state = tuple(
        receipt[field] for field in _PREFLIGHT_OBSERVATION_FIELDS
    )
    if observed_state not in _PREFLIGHT_STAGE_STATES[stage]:
        raise _InvalidPreflightReceipt("stage observation truth table mismatch")
    state = observed_state
    blockers = receipt["blocker_codes"]
    if type(blockers) is not list or blockers != _expected_preflight_blockers(state):
        raise _InvalidPreflightReceipt("blocker order mismatch")
    service_projection = receipt["service_configuration_projection"]
    image_projection = receipt["service_image_identity_projection"]
    if state[5]:
        if not _validate_service_projection(service_projection):
            raise _InvalidPreflightReceipt("service projection mismatch")
    elif type(service_projection) is not dict or service_projection:
        raise _InvalidPreflightReceipt("unexpected service projection")
    if state[6]:
        if not _validate_image_projection(image_projection):
            raise _InvalidPreflightReceipt("image projection mismatch")
        expected_raw_path_hash = hashlib.sha256(
            f'"{image_projection["final_volume_guid_path"]}"'.encode("utf-16-le")
        ).hexdigest()
        if not hmac.compare_digest(
            expected_raw_path_hash,
            service_projection["raw_binary_path_sha256"],
        ):
            raise _InvalidPreflightReceipt("service image path mismatch")
    elif type(image_projection) is not dict or image_projection:
        raise _InvalidPreflightReceipt("unexpected image projection")
    declared = receipt["receipt_sha256"]
    if type(declared) is not str or _HEX_64.fullmatch(declared) is None:
        raise _InvalidPreflightReceipt("receipt hash shape mismatch")
    material = dict(receipt)
    material.pop("receipt_sha256")
    if not hmac.compare_digest(declared, _canonical_sha256(material)):
        raise _InvalidPreflightReceipt("receipt hash mismatch")
    return {
        "schema_version": receipt["schema_version"],
        "declared_receipt_sha256": declared,
        "full_canonical_sha256": _canonical_sha256(receipt),
        "failure_stage": stage,
        "blocker_codes": list(blockers),
    }


def _endpoint_comparison(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> tuple[bool, bool, bool, bool]:
    before_rows = before["projection"]
    after_rows = after["projection"]
    snapshots_usable = (
        before["snapshot_succeeded"] is True
        and after["snapshot_succeeded"] is True
        and before["required_local_endpoint_kinds_present"] is True
        and after["required_local_endpoint_kinds_present"] is True
    )
    before_inventory = [
        (row["kind"], row["path"]) for row in before_rows
    ]
    after_inventory = [
        (row["kind"], row["path"]) for row in after_rows
    ]
    inventory_stable = snapshots_usable and before_inventory == after_inventory
    before_content = [
        (row["kind"], row["path"], row["bytes"], row["sha256"])
        for row in before_rows
    ]
    after_content = [
        (row["kind"], row["path"], row["bytes"], row["sha256"])
        for row in after_rows
    ]
    bytes_sha_stable = inventory_stable and before_content == after_content
    before_mtimes = [
        (row["kind"], row["path"], row["mtime_ns"])
        for row in before_rows
    ]
    after_mtimes = [
        (row["kind"], row["path"], row["mtime_ns"])
        for row in after_rows
    ]
    mtime_stable = inventory_stable and before_mtimes == after_mtimes
    pre_post_match = (
        snapshots_usable
        and inventory_stable
        and bytes_sha_stable
        and mtime_stable
    )
    return inventory_stable, bytes_sha_stable, mtime_stable, pre_post_match


def compile_fixed_p0_actual_readiness_blockers() -> dict[str, Any]:
    """Return a zero-input, read-only, permanently non-authoritative receipt."""

    before = _safe_snapshot_fixed_local_endpoints()
    child_executed = False
    child_validated = False
    child_status = "EXECUTION_FAILED"
    child_stage = "UNAVAILABLE"
    child_blockers = ["HOST_PREFLIGHT_EXECUTION_FAILED"]
    child_binding = {
        "schema_version": "",
        "declared_receipt_sha256": "",
        "full_canonical_sha256": "",
    }
    try:
        child = preflight.observe_fixed_windows_owner_provisioning_preflight_candidate()
        child_executed = True
        try:
            validated = _validate_same_call_preflight_receipt(child)
        except _InvalidPreflightReceipt:
            child_status = "INVALID_RECEIPT"
            child_stage = "RECEIPT_INVALID"
            child_blockers = ["HOST_PREFLIGHT_RECEIPT_NOT_VERIFIED"]
        else:
            child_validated = True
            child_status = "VALID_CANDIDATE_NO_GO"
            child_stage = validated["failure_stage"]
            child_blockers = validated["blocker_codes"]
            child_binding = {
                "schema_version": validated["schema_version"],
                "declared_receipt_sha256": validated[
                    "declared_receipt_sha256"
                ],
                "full_canonical_sha256": validated[
                    "full_canonical_sha256"
                ],
            }
    except Exception:
        pass
    after = _safe_snapshot_fixed_local_endpoints()
    (
        inventory_stable,
        bytes_sha_stable,
        mtime_stable,
        pre_post_match,
    ) = _endpoint_comparison(before, after)
    dynamic_blockers: list[str] = []
    snapshots_usable = (
        before["snapshot_succeeded"] is True
        and after["snapshot_succeeded"] is True
        and before["required_local_endpoint_kinds_present"] is True
        and after["required_local_endpoint_kinds_present"] is True
    )
    if not snapshots_usable:
        dynamic_blockers.append("LOCAL_ENDPOINT_SNAPSHOT_NOT_VERIFIED")
    elif not inventory_stable or not bytes_sha_stable or not mtime_stable:
        dynamic_blockers.append("LOCAL_ENDPOINT_CHANGED_DURING_COMPILATION")
    if child_status == "INVALID_RECEIPT":
        dynamic_blockers.append("HOST_PREFLIGHT_RECEIPT_NOT_VERIFIED")
    elif child_status == "EXECUTION_FAILED":
        dynamic_blockers.append("HOST_PREFLIGHT_EXECUTION_FAILED")
    material: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA,
        "gate_status": GATE_STATUS,
        "scope": "ZERO_INPUT_READ_ONLY_BLOCKER_COMPILATION_ONLY",
        "phase": "PRE_CAPTURE",
        "decision": "NO_GO",
        "blocker_only": True,
        "zero_input_public_api_verified": True,
        "caller_supplied_selector_absent": True,
        "blocker_codes": [*_BASE_BLOCKER_ORDER[:-1], *dynamic_blockers, _BASE_BLOCKER_ORDER[-1]],
        "host_preflight_status": child_status,
        "host_preflight_candidate_executed": child_executed,
        "host_preflight_receipt_validated": child_validated,
        "host_preflight_failure_stage": child_stage,
        "host_preflight_blocker_codes": child_blockers,
        "host_preflight_receipt_binding": child_binding,
        "child_self_hash_only_not_authority": True,
        "required_source_profiles": list(_EXPECTED_SOURCE_PROFILES),
        "required_per_profile_quota": _EXPECTED_PER_PROFILE_QUOTA,
        "required_actual_selected_source_claim_unit_count": (
            _EXPECTED_SOURCE_CLAIMS
        ),
        "required_actual_a_sampling_unit_count": _EXPECTED_A_CONTEXT_REVIEWS,
        "observed_actual_selected_source_claim_unit_count": 0,
        "observed_actual_source_claim_row_count": 0,
        "observed_actual_a_sampling_unit_count": 0,
        "observed_actual_a_annotation_event_count": 0,
        "credited_actual_selected_source_claim_unit_count": 0,
        "credited_actual_a_sampling_unit_count": 0,
        "source_credit_unit_definition": (
            "LABEL_BLIND_UNIQUE_SELECTED_CLAIM_UNIT_SOURCE_SNAPSHOT_PROFILE_10X4"
        ),
        "a_context_credit_unit_definition": (
            "UNIQUE_SAMPLING_UNIT_WITH_BOUND_PRIMARY_HUMAN_JOURNAL"
        ),
        "selected_a_context_denominator_includes_statuses": [
            "JUDGED",
            "UNJUDGED",
            "UNAVAILABLE",
        ],
        "observed_a_annotation_status_counts": {
            "JUDGED": 0,
            "UNJUDGED": 0,
            "UNAVAILABLE": 0,
        },
        "annotation_coverage_numerator_judged": 0,
        "annotation_coverage_denominator": (
            "ALL_SELECTED_20_INCLUDING_UNJUDGED_UNAVAILABLE"
        ),
        "terminal_accuracy_denominator": "JUDGED_ONLY",
        "worst_case_denominator": "ALL_SELECTED_20",
        "one_to_many_claim_rows_increase_selected_unit_credit": False,
        "recheck_events_increase_a_sampling_unit_credit": False,
        "synthetic_or_structural_evidence_creditable": False,
        "required_actual_watch_categories": list(
            _REQUIRED_ACTUAL_WATCH_CATEGORIES
        ),
        "local_endpoint_snapshot_before_succeeded": before[
            "snapshot_succeeded"
        ],
        "local_endpoint_snapshot_after_succeeded": after[
            "snapshot_succeeded"
        ],
        "required_local_endpoint_kinds_present_before": before[
            "required_local_endpoint_kinds_present"
        ],
        "required_local_endpoint_kinds_present_after": after[
            "required_local_endpoint_kinds_present"
        ],
        "local_endpoint_projection_before": before["projection"],
        "local_endpoint_projection_after": after["projection"],
        "local_endpoint_projection_before_sha256": before[
            "projection_sha256"
        ],
        "local_endpoint_projection_after_sha256": after[
            "projection_sha256"
        ],
        "local_endpoint_inventory_stable": inventory_stable,
        "local_endpoint_bytes_sha_stable": bytes_sha_stable,
        "local_endpoint_mtime_stable": mtime_stable,
        "compiler_pre_post_endpoint_projection_match_observed": (
            pre_post_match
        ),
        "endpoint_observation_scope": "POINT_IN_TIME_PRE_POST_ONLY",
        "policy_authority_status": (
            "TEMPLATE_AND_CONTRACT_ONLY_EXTERNAL_PROVISIONING_NOT_VERIFIED"
        ),
        "annotation_authority_status": (
            "SCHEMA_ONLY_NO_OWNER_GUIDELINE_REVIEWER_APPEND_ONLY_AUTHORITY"
        ),
        "next_phase": "EXTERNAL_OWNER_PROVISIONING_REQUIRED",
        **{field: False for field in _FALSE_OUTPUT_FIELDS},
        "operational_effect": OPERATIONAL_EFFECT,
    }
    return {**material, "receipt_sha256": _canonical_sha256(material)}


__all__ = [
    "GATE_STATUS",
    "OPERATIONAL_EFFECT",
    "RECEIPT_SCHEMA",
    "compile_fixed_p0_actual_readiness_blockers",
]
