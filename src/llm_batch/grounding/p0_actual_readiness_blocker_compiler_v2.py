"""Read-only actual-readiness blocker compiler consuming transition V1 once."""

from __future__ import annotations

import hashlib
import hmac
import inspect
import json
from typing import Any, Mapping

from . import p0_actual_readiness_blocker_compiler as compiler_v1
from . import p0_windows_owner_policy_v4_transition_fixed_store as transition


RECEIPT_SCHEMA = "p0_actual_readiness_blocker_compilation_receipt_v2"
GATE_STATUS = "ACTUAL_READINESS_V3_V4_TRANSITION_COMPILED_AUTHORITY_NO_GO"
OPERATIONAL_EFFECT = "NONE_BLOCKER_COMPILATION_ONLY"
_CENTRAL_SLANG_DB_RELATIVE_PATH = "slang_db/slang_db.json"
_PUBLICATION_JOURNAL_RELATIVE_PREFIX = "out/publication_commit_journals/"
_BASE_BLOCKERS = (
    "V3_V4_TRANSITION_OBSERVER_NO_GO",
    "BOOTSTRAP_PUBLIC_KEY_INDEPENDENT_PIN_NOT_VERIFIED",
    "EXTERNAL_PUBLIC_KEY_PIN_PROVISIONING_NOT_VERIFIED",
    "TRUSTED_TIME_NOT_VERIFIED", "REVOCATION_HIGH_WATERMARK_NOT_VERIFIED",
    "DURABLE_NONCE_STATE_NOT_VERIFIED", "EXTERNAL_ROOT_AUTHORITY_NOT_VERIFIED",
    "EXTERNAL_CODE_AUTHORITY_NOT_VERIFIED", "OS_WRITE_DENY_NOT_VERIFIED",
    "SIGNED_NATIVE_RUNTIME_WITNESS_NOT_VERIFIED",
    "RUNTIME_NONINTERFERENCE_NOT_VERIFIED", "PARSER_RUNTIME_NOT_RUN",
    "ACTUAL_POLICY_AUTHORITY_NOT_VERIFIED", "ACTUAL_CAPTURE_RIGHTS_POLICY_NOT_AUTHORIZED",
    "ACTUAL_SAMPLING_PLAN_NOT_AUTHORIZED", "ACTUAL_ANNOTATION_GUIDELINE_NOT_AUTHORIZED",
    "ACTUAL_REVIEWER_ASSIGNMENT_NOT_AUTHORIZED",
    "ACTUAL_ANNOTATION_DURABLE_PREDECESSOR_NOT_VERIFIED",
    "ACTUAL_ANNOTATION_APPEND_ONLY_NOT_VERIFIED",
    "ACTUAL_SOURCE_CLAIMS_CREDITED_0_OF_40",
    "ACTUAL_A_CONTEXT_REVIEWS_CREDITED_0_OF_20",
    "ACTUAL_SEMANTIC_EVIDENCE_NOT_VERIFIED",
    "P1_RETRIEVAL_RERANKER_NIL_SHADOW_BLOCKED_BY_P0",
    "BLOCKER_ONLY_COMPILER_NOT_AUTHORITY",
)
_FALSE_FIELDS = (
    "capture_execution_authorized", "runtime_execution_entrypoint_invoked",
    "process_spawned", "service_started", "publication_wal_write_invoked_by_compiler",
    "central_slang_db_write_invoked_by_compiler", "action_applied",
    "protected_pipeline_state_mutated", "external_root_identity_pin_verified",
    "bootstrap_public_key_independently_pinned",
    "external_public_key_pin_provisioning_verified",
    "trusted_time_verified", "revocation_high_watermark_verified",
    "durable_nonce_state_verified", "external_root_authority_verified",
    "external_code_authority_verified", "os_write_deny_verified",
    "signed_native_runtime_witness_verified", "runtime_noninterference_verified",
    "parser_runtime_verified", "actual_policy_authority_verified",
    "actual_capture_rights_policy_authorized", "actual_sampling_plan_authorized",
    "actual_annotation_guideline_authorized", "actual_reviewer_assignment_authorized",
    "actual_annotation_durable_predecessor_verified",
    "actual_annotation_append_only_verified", "actual_authority_granted",
    "actual_semantic_evidence_verified", "p0_phase_exit", "production_approval",
    "full_scan_approval", "serialized_receipt_authoritative",
)
_RECEIPT_FIELDS = (
    "schema_version", "gate_status", "scope", "phase", "decision", "blocker_only",
    "zero_input_public_api_verified", "caller_supplied_selector_absent", "blocker_codes",
    "transition_observer_executed_once", "transition_receipt_strictly_validated",
    "transition_status",
    "transition_failure_stage", "transition_blocker_codes",
    "transition_receipt_declared_sha256", "transition_receipt_full_canonical_sha256",
    "transition_component_manifest_sha256", "child_self_hash_only_not_authority",
    "required_actual_selected_source_claim_unit_count",
    "required_actual_a_sampling_unit_count", "observed_actual_selected_source_claim_unit_count",
    "observed_actual_a_sampling_unit_count", "credited_actual_selected_source_claim_unit_count",
    "credited_actual_a_sampling_unit_count", "local_endpoint_snapshot_before_succeeded",
    "local_endpoint_snapshot_after_succeeded", "required_local_endpoint_kinds_present_before",
    "required_local_endpoint_kinds_present_after", "local_endpoint_projection_before",
    "local_endpoint_projection_after", "local_endpoint_projection_before_sha256",
    "local_endpoint_projection_after_sha256", "local_endpoint_inventory_stable",
    "local_endpoint_bytes_sha_stable", "local_endpoint_mtime_stable",
    "compiler_pre_post_endpoint_projection_match_observed", "endpoint_observation_scope",
    "policy_authority_status", "annotation_authority_status", "next_phase",
    *_FALSE_FIELDS, "operational_effect", "receipt_sha256",
)


class P0ActualReadinessBlockerCompilerV2Error(RuntimeError):
    """The blocker compiler could not fail closed."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _stable_code_digest(value: Any) -> str:
    code = getattr(value, "__code__", None)
    if code is None:
        return ""
    projection = (
        code.co_code.hex(), repr(code.co_consts), code.co_names, code.co_varnames,
        code.co_freevars, code.co_cellvars, code.co_argcount,
        code.co_posonlyargcount, code.co_kwonlyargcount, code.co_flags,
    )
    return hashlib.sha256(repr(projection).encode("utf-8")).hexdigest()


def _validate_transition_receipt(receipt: Any) -> dict[str, Any]:
    try:
        transition._validate_receipt(receipt)
    except transition.P0WindowsOwnerPolicyV4TransitionFixedStoreError as exc:
        raise P0ActualReadinessBlockerCompilerV2Error(
            "transition child receipt is invalid"
        ) from exc
    if (
        type(receipt) is not dict
        or tuple(receipt) != transition._RECEIPT_FIELDS
        or receipt["decision"] != "NO_GO"
        or receipt["credited_actual_source_claim_count"] != 0
        or receipt["credited_actual_a_context_review_count"] != 0
        or any(receipt[field] is not False for field in transition._FALSE_FIELDS)
    ):
        raise P0ActualReadinessBlockerCompilerV2Error(
            "transition child exact schema/truth mismatch"
        )
    if receipt["failure_stage"] == "EXTERNAL_STATE":
        nested = receipt["transition_parent_receipt"]
        if (
            type(receipt["role_handle_count"]) is not int
            or receipt["role_handle_count"] != 21
            or type(receipt["file_handle_count"]) is not int
            or receipt["file_handle_count"] != 9
            or len(receipt["directory_change_watches"]) != 3
            or type(nested) is not dict
            or tuple(nested) != transition.transition_parent._RECEIPT_FIELDS
            or nested.get("receipt_sha256")
            != receipt["transition_parent_receipt_declared_sha256"]
            or canonical_sha256(nested)
            != receipt["transition_parent_receipt_full_canonical_sha256"]
        ):
            raise P0ActualReadinessBlockerCompilerV2Error(
                "transition child success evidence binding mismatch"
            )
    return {
        "failure_stage": receipt["failure_stage"],
        "blocker_codes": list(receipt["blocker_codes"]),
        "declared_sha256": receipt["receipt_sha256"],
        "full_sha256": canonical_sha256(receipt),
    }


def _execute_transition_once(observer: Any) -> dict[str, Any]:
    try:
        child = observer()
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        return {
            "executed": False, "validated": False,
            "status": "TRANSITION_EXECUTION_FAILED", "stage": "UNAVAILABLE",
            "blockers": ["V3_V4_TRANSITION_EXECUTION_FAILED"],
            "declared": "", "full": "",
            "dynamic": ["V3_V4_TRANSITION_EXECUTION_FAILED"],
        }
    try:
        binding = _validate_transition_receipt(child)
    except P0ActualReadinessBlockerCompilerV2Error:
        return {
            "executed": True, "validated": False,
            "status": "INVALID_TRANSITION_RECEIPT", "stage": "RECEIPT_INVALID",
            "blockers": ["V3_V4_TRANSITION_RECEIPT_NOT_VERIFIED"],
            "declared": "", "full": "",
            "dynamic": ["V3_V4_TRANSITION_RECEIPT_NOT_VERIFIED"],
        }
    return {
        "executed": True, "validated": True, "status": "VALID_COMPONENT_NO_GO",
        "stage": binding["failure_stage"], "blockers": binding["blocker_codes"],
        "declared": binding["declared_sha256"], "full": binding["full_sha256"],
        "dynamic": [],
    }


def compile_fixed_p0_actual_readiness_blockers_v2() -> dict[str, Any]:
    """Execute the zero-input transition observer exactly once and compile blockers."""

    _assert_integrity()
    before = compiler_v1._safe_snapshot_fixed_local_endpoints()
    child_result = _execute_transition_once(
        transition.observe_fixed_windows_owner_policy_v4_transition_store
    )
    executed = child_result["executed"]
    validated = child_result["validated"]
    status = child_result["status"]
    child_stage = child_result["stage"]
    child_blockers = child_result["blockers"]
    declared, full = child_result["declared"], child_result["full"]
    dynamic: list[str] = list(child_result["dynamic"])
    after = compiler_v1._safe_snapshot_fixed_local_endpoints()
    inventory, bytes_stable, mtime, match = compiler_v1._endpoint_comparison(before, after)
    snapshots_usable = bool(
        before["snapshot_succeeded"] and after["snapshot_succeeded"]
        and before["required_local_endpoint_kinds_present"]
        and after["required_local_endpoint_kinds_present"]
    )
    if not snapshots_usable:
        dynamic.append("LOCAL_ENDPOINT_SNAPSHOT_NOT_VERIFIED")
    elif not match:
        dynamic.append("LOCAL_ENDPOINT_CHANGED_DURING_COMPILATION")
    material: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA, "gate_status": GATE_STATUS,
        "scope": "ZERO_INPUT_READ_ONLY_TRANSITION_BLOCKER_COMPILATION_ONLY",
        "phase": "PRE_CAPTURE", "decision": "NO_GO", "blocker_only": True,
        "zero_input_public_api_verified": True, "caller_supplied_selector_absent": True,
        "blocker_codes": [*_BASE_BLOCKERS[:-1], *dynamic, _BASE_BLOCKERS[-1]],
        "transition_observer_executed_once": executed,
        "transition_receipt_strictly_validated": validated,
        "transition_status": status,
        "transition_failure_stage": child_stage,
        "transition_blocker_codes": child_blockers,
        "transition_receipt_declared_sha256": declared,
        "transition_receipt_full_canonical_sha256": full,
        "transition_component_manifest_sha256": transition.EXPECTED_COMPONENT_MANIFEST_SHA256,
        "child_self_hash_only_not_authority": True,
        "required_actual_selected_source_claim_unit_count": 40,
        "required_actual_a_sampling_unit_count": 20,
        "observed_actual_selected_source_claim_unit_count": 0,
        "observed_actual_a_sampling_unit_count": 0,
        "credited_actual_selected_source_claim_unit_count": 0,
        "credited_actual_a_sampling_unit_count": 0,
        "local_endpoint_snapshot_before_succeeded": before["snapshot_succeeded"],
        "local_endpoint_snapshot_after_succeeded": after["snapshot_succeeded"],
        "required_local_endpoint_kinds_present_before": before["required_local_endpoint_kinds_present"],
        "required_local_endpoint_kinds_present_after": after["required_local_endpoint_kinds_present"],
        "local_endpoint_projection_before": before["projection"],
        "local_endpoint_projection_after": after["projection"],
        "local_endpoint_projection_before_sha256": before["projection_sha256"],
        "local_endpoint_projection_after_sha256": after["projection_sha256"],
        "local_endpoint_inventory_stable": inventory,
        "local_endpoint_bytes_sha_stable": bytes_stable,
        "local_endpoint_mtime_stable": mtime,
        "compiler_pre_post_endpoint_projection_match_observed": match,
        "endpoint_observation_scope": "POINT_IN_TIME_PRE_POST_ONLY",
        "policy_authority_status": "TRANSITION_COMPONENT_ONLY_EXTERNAL_PROVISIONING_NOT_VERIFIED",
        "annotation_authority_status": "SCHEMA_ONLY_NO_OWNER_GUIDELINE_REVIEWER_APPEND_ONLY_AUTHORITY",
        "next_phase": (
            "EXTERNAL_NATIVE_OWNER_AUTHORITY_REQUIRED"
            if validated and child_stage == "EXTERNAL_STATE"
            else "V4_TRANSITION_STORE_PROVISIONING_REQUIRED"
        ),
        **{field: False for field in _FALSE_FIELDS},
        "operational_effect": OPERATIONAL_EFFECT,
    }
    receipt = {**material, "receipt_sha256": canonical_sha256(material)}
    _assert_integrity()
    return _validate_output(receipt)


def _validate_output(receipt: Any) -> dict[str, Any]:
    status = receipt.get("transition_status") if type(receipt) is dict else None
    expected_state = {
        "VALID_COMPONENT_NO_GO": (True, True),
        "INVALID_TRANSITION_RECEIPT": (True, False),
        "TRANSITION_EXECUTION_FAILED": (False, False),
    }.get(status)
    if (
        type(receipt) is not dict or tuple(receipt) != _RECEIPT_FIELDS
        or receipt.get("schema_version") != RECEIPT_SCHEMA
        or receipt.get("gate_status") != GATE_STATUS
        or receipt.get("scope") != "ZERO_INPUT_READ_ONLY_TRANSITION_BLOCKER_COMPILATION_ONLY"
        or receipt.get("phase") != "PRE_CAPTURE"
        or receipt.get("decision") != "NO_GO"
        or receipt.get("blocker_only") is not True
        or receipt.get("zero_input_public_api_verified") is not True
        or receipt.get("caller_supplied_selector_absent") is not True
        or receipt.get("child_self_hash_only_not_authority") is not True
        or receipt.get("transition_component_manifest_sha256")
        != transition.EXPECTED_COMPONENT_MANIFEST_SHA256
        or receipt.get("endpoint_observation_scope") != "POINT_IN_TIME_PRE_POST_ONLY"
        or receipt.get("policy_authority_status")
        != "TRANSITION_COMPONENT_ONLY_EXTERNAL_PROVISIONING_NOT_VERIFIED"
        or receipt.get("annotation_authority_status")
        != "SCHEMA_ONLY_NO_OWNER_GUIDELINE_REVIEWER_APPEND_ONLY_AUTHORITY"
        or receipt.get("operational_effect") != OPERATIONAL_EFFECT
        or receipt.get("transition_status") not in {
            "VALID_COMPONENT_NO_GO", "INVALID_TRANSITION_RECEIPT",
            "TRANSITION_EXECUTION_FAILED",
        }
        or type(receipt.get("transition_observer_executed_once")) is not bool
        or type(receipt.get("transition_receipt_strictly_validated")) is not bool
        or any(
            type(receipt.get(field)) is not int
            for field in (
                "required_actual_selected_source_claim_unit_count",
                "required_actual_a_sampling_unit_count",
                "observed_actual_selected_source_claim_unit_count",
                "observed_actual_a_sampling_unit_count",
                "credited_actual_selected_source_claim_unit_count",
                "credited_actual_a_sampling_unit_count",
            )
        )
        or receipt.get("required_actual_selected_source_claim_unit_count") != 40
        or receipt.get("required_actual_a_sampling_unit_count") != 20
        or receipt.get("observed_actual_selected_source_claim_unit_count") != 0
        or receipt.get("observed_actual_a_sampling_unit_count") != 0
        or receipt.get("credited_actual_selected_source_claim_unit_count") != 0
        or receipt.get("credited_actual_a_sampling_unit_count") != 0
        or receipt.get("next_phase") not in {
            "V4_TRANSITION_STORE_PROVISIONING_REQUIRED",
            "EXTERNAL_NATIVE_OWNER_AUTHORITY_REQUIRED",
        }
        or expected_state is None
        or (
            receipt.get("transition_observer_executed_once"),
            receipt.get("transition_receipt_strictly_validated"),
        ) != expected_state
        or any(
            type(receipt.get(field)) is not bool
            for field in (
                "local_endpoint_snapshot_before_succeeded",
                "local_endpoint_snapshot_after_succeeded",
                "required_local_endpoint_kinds_present_before",
                "required_local_endpoint_kinds_present_after",
                "local_endpoint_inventory_stable", "local_endpoint_bytes_sha_stable",
                "local_endpoint_mtime_stable",
                "compiler_pre_post_endpoint_projection_match_observed",
            )
        )
        or any(receipt.get(field) is not False for field in _FALSE_FIELDS)
    ):
        raise P0ActualReadinessBlockerCompilerV2Error("compiler output schema/truth mismatch")
    def lower_sha(value: Any) -> bool:
        return type(value) is str and len(value) == 64 and all(
            character in "0123456789abcdef" for character in value
        )
    stage = receipt["transition_failure_stage"]
    child_blockers = receipt["transition_blocker_codes"]
    declared = receipt["transition_receipt_declared_sha256"]
    full = receipt["transition_receipt_full_canonical_sha256"]
    if status == "VALID_COMPONENT_NO_GO":
        expected_child_blockers = (
            list(transition._BLOCKERS[9:])
            if stage == "EXTERNAL_STATE"
            else list(transition._BLOCKERS)
            if stage == "FIXED_STORE"
            else None
        )
        if (
            expected_child_blockers is None
            or child_blockers != expected_child_blockers
            or not lower_sha(declared)
            or not lower_sha(full)
        ):
            raise P0ActualReadinessBlockerCompilerV2Error(
                "compiler valid-child state binding mismatch"
            )
    else:
        expected_stage = (
            "RECEIPT_INVALID" if status == "INVALID_TRANSITION_RECEIPT" else "UNAVAILABLE"
        )
        expected_child_blockers = [
            "V3_V4_TRANSITION_RECEIPT_NOT_VERIFIED"
            if status == "INVALID_TRANSITION_RECEIPT"
            else "V3_V4_TRANSITION_EXECUTION_FAILED"
        ]
        if (
            stage != expected_stage
            or child_blockers != expected_child_blockers
            or declared != ""
            or full != ""
        ):
            raise P0ActualReadinessBlockerCompilerV2Error(
                "compiler invalid/failed-child state binding mismatch"
            )
    before_projection = receipt["local_endpoint_projection_before"]
    after_projection = receipt["local_endpoint_projection_after"]
    def projection_valid(value: Any, snapshot_succeeded: bool, required_present: bool) -> bool:
        if type(value) is not list or (not snapshot_succeeded and value != []):
            return False
        for row in value:
            kind = row.get("kind") if type(row) is dict else None
            path = row.get("path") if type(row) is dict else None
            if (
                type(row) is not dict
                or tuple(row) != ("kind", "path", "bytes", "mtime_ns", "sha256")
                or row.get("kind") not in {"CENTRAL_SLANG_DB", "PUBLICATION_JOURNAL"}
                or type(row.get("path")) is not str
                or not row["path"]
                or row["path"].startswith(("/", "\\"))
                or "\\" in row["path"]
                or ".." in row["path"].split("/")
                or (
                    kind == "CENTRAL_SLANG_DB"
                    and path != _CENTRAL_SLANG_DB_RELATIVE_PATH
                )
                or (
                    kind == "PUBLICATION_JOURNAL"
                    and (
                        not path.startswith(_PUBLICATION_JOURNAL_RELATIVE_PREFIX)
                        or "/" in path[len(_PUBLICATION_JOURNAL_RELATIVE_PREFIX):]
                        or not path[len(_PUBLICATION_JOURNAL_RELATIVE_PREFIX):].casefold().endswith(".jsonl")
                        or path[len(_PUBLICATION_JOURNAL_RELATIVE_PREFIX):] == ".jsonl"
                    )
                )
                or type(row.get("bytes")) is not int
                or row["bytes"] < 0
                or type(row.get("mtime_ns")) is not int
                or row["mtime_ns"] < 0
                or not lower_sha(row.get("sha256"))
            ):
                return False
        kinds = [row["kind"] for row in value]
        if kinds.count("CENTRAL_SLANG_DB") > 1:
            return False
        if required_present and not (
            "CENTRAL_SLANG_DB" in kinds and "PUBLICATION_JOURNAL" in kinds
        ):
            return False
        return value == sorted(
            value,
            key=lambda row: (0 if row["kind"] == "CENTRAL_SLANG_DB" else 1, row["path"]),
        )
    if (
        not projection_valid(
            before_projection,
            receipt["local_endpoint_snapshot_before_succeeded"],
            receipt["required_local_endpoint_kinds_present_before"],
        )
        or not projection_valid(
            after_projection,
            receipt["local_endpoint_snapshot_after_succeeded"],
            receipt["required_local_endpoint_kinds_present_after"],
        )
        or not lower_sha(receipt["local_endpoint_projection_before_sha256"])
        or not lower_sha(receipt["local_endpoint_projection_after_sha256"])
        or receipt["local_endpoint_projection_before_sha256"]
        != canonical_sha256(before_projection)
        or receipt["local_endpoint_projection_after_sha256"]
        != canonical_sha256(after_projection)
    ):
        raise P0ActualReadinessBlockerCompilerV2Error(
            "compiler endpoint projection binding mismatch"
        )
    recomputed_endpoint_state = compiler_v1._endpoint_comparison(
        {
            "snapshot_succeeded": receipt["local_endpoint_snapshot_before_succeeded"],
            "required_local_endpoint_kinds_present": receipt[
                "required_local_endpoint_kinds_present_before"
            ],
            "projection": before_projection,
        },
        {
            "snapshot_succeeded": receipt["local_endpoint_snapshot_after_succeeded"],
            "required_local_endpoint_kinds_present": receipt[
                "required_local_endpoint_kinds_present_after"
            ],
            "projection": after_projection,
        },
    )
    if recomputed_endpoint_state != (
        receipt["local_endpoint_inventory_stable"],
        receipt["local_endpoint_bytes_sha_stable"],
        receipt["local_endpoint_mtime_stable"],
        receipt["compiler_pre_post_endpoint_projection_match_observed"],
    ):
        raise P0ActualReadinessBlockerCompilerV2Error(
            "compiler endpoint comparison replay mismatch"
        )
    expected_dynamic: list[str] = []
    if status == "INVALID_TRANSITION_RECEIPT":
        expected_dynamic.append("V3_V4_TRANSITION_RECEIPT_NOT_VERIFIED")
    elif status == "TRANSITION_EXECUTION_FAILED":
        expected_dynamic.append("V3_V4_TRANSITION_EXECUTION_FAILED")
    usable = (
        receipt["local_endpoint_snapshot_before_succeeded"]
        and receipt["local_endpoint_snapshot_after_succeeded"]
        and receipt["required_local_endpoint_kinds_present_before"]
        and receipt["required_local_endpoint_kinds_present_after"]
    )
    if not usable:
        expected_dynamic.append("LOCAL_ENDPOINT_SNAPSHOT_NOT_VERIFIED")
    elif not receipt["compiler_pre_post_endpoint_projection_match_observed"]:
        expected_dynamic.append("LOCAL_ENDPOINT_CHANGED_DURING_COMPILATION")
    if receipt.get("blocker_codes") != [*_BASE_BLOCKERS[:-1], *expected_dynamic, _BASE_BLOCKERS[-1]]:
        raise P0ActualReadinessBlockerCompilerV2Error("compiler blocker order mismatch")
    expected_next = (
        "EXTERNAL_NATIVE_OWNER_AUTHORITY_REQUIRED"
        if status == "VALID_COMPONENT_NO_GO" and receipt.get("transition_failure_stage") == "EXTERNAL_STATE"
        else "V4_TRANSITION_STORE_PROVISIONING_REQUIRED"
    )
    if receipt.get("next_phase") != expected_next:
        raise P0ActualReadinessBlockerCompilerV2Error("compiler next-phase mismatch")
    if (
        (not usable and any(receipt[field] for field in (
            "local_endpoint_inventory_stable", "local_endpoint_bytes_sha_stable",
            "local_endpoint_mtime_stable",
            "compiler_pre_post_endpoint_projection_match_observed",
        )))
        or (
            receipt["compiler_pre_post_endpoint_projection_match_observed"]
            and not all(receipt[field] for field in (
                "local_endpoint_inventory_stable", "local_endpoint_bytes_sha_stable",
                "local_endpoint_mtime_stable",
            ))
        )
    ):
        raise P0ActualReadinessBlockerCompilerV2Error(
            "compiler endpoint truth-table mismatch"
        )
    material = dict(receipt)
    declared = material.pop("receipt_sha256", None)
    if type(declared) is not str or not hmac.compare_digest(declared, canonical_sha256(material)):
        raise P0ActualReadinessBlockerCompilerV2Error("compiler output self-hash mismatch")
    return receipt


def _semantic_contract_projection() -> dict[str, Any]:
    return {
        "schema": RECEIPT_SCHEMA, "gate": GATE_STATUS, "effect": OPERATIONAL_EFFECT,
        "blockers": list(_BASE_BLOCKERS), "false_fields": list(_FALSE_FIELDS),
        "receipt_fields": list(_RECEIPT_FIELDS),
        "central_slang_db_relative_path": _CENTRAL_SLANG_DB_RELATIVE_PATH,
        "publication_journal_relative_prefix": _PUBLICATION_JOURNAL_RELATIVE_PREFIX,
        "transition_manifest": transition.EXPECTED_COMPONENT_MANIFEST_SHA256,
    }


SEMANTIC_CONTRACT_SHA256 = "28ab9196ad9c2700a9937d43f9866e3be6535c6ec2948c843578a99b691e8c16"
EXPECTED_SEMANTIC_CONTRACT_SHA256 = "28ab9196ad9c2700a9937d43f9866e3be6535c6ec2948c843578a99b691e8c16"
COMPONENT_MANIFEST = {
    "component": "p0_actual_readiness_blocker_compiler_v2",
    "receipt_schema": RECEIPT_SCHEMA, "semantic_contract_sha256": SEMANTIC_CONTRACT_SHA256,
    "transition_component_manifest_sha256": transition.EXPECTED_COMPONENT_MANIFEST_SHA256,
    "authority_boundary": GATE_STATUS,
}
COMPONENT_MANIFEST_SHA256 = "0c13c08c46850f6e2288b001b03b448b6460a8b8e9d82e70cd9379a7ce24060e"
EXPECTED_COMPONENT_MANIFEST_SHA256 = "0c13c08c46850f6e2288b001b03b448b6460a8b8e9d82e70cd9379a7ce24060e"


_DEPENDENCY_PINS = {
    "observer": transition.observe_fixed_windows_owner_policy_v4_transition_store,
    "transition_validate": transition._validate_receipt,
    "transition_integrity": transition._assert_integrity,
    "snapshot": compiler_v1._safe_snapshot_fixed_local_endpoints,
    "compare": compiler_v1._endpoint_comparison,
}
_EXTERNAL_CODE_PINS = tuple(
    (
        label, value, _stable_code_digest(value),
        value.__defaults__,
        dict(value.__kwdefaults__) if value.__kwdefaults__ is not None else None,
    )
    for label, value in (
        ("observer", transition.observe_fixed_windows_owner_policy_v4_transition_store),
        ("transition_validate", transition._validate_receipt),
        ("transition_integrity", transition._assert_integrity),
        ("snapshot", compiler_v1._safe_snapshot_fixed_local_endpoints),
        ("compare", compiler_v1._endpoint_comparison),
    )
)
_HASHLIB_SHA256_PIN = hashlib.sha256
_STABLE_CODE_DIGEST_PIN = _stable_code_digest
_STABLE_CODE_OBJECT_PIN = _stable_code_digest.__code__


def _callable_code_sha256(value: Any) -> str:
    return _stable_code_digest(value)


def _assert_integrity() -> None:
    if (
        hashlib.sha256 is not _HASHLIB_SHA256_PIN
        or _stable_code_digest is not _STABLE_CODE_DIGEST_PIN
        or _stable_code_digest.__code__ is not _STABLE_CODE_OBJECT_PIN
        or
        SEMANTIC_CONTRACT_SHA256 != EXPECTED_SEMANTIC_CONTRACT_SHA256
        or canonical_sha256(_semantic_contract_projection()) != EXPECTED_SEMANTIC_CONTRACT_SHA256
        or COMPONENT_MANIFEST_SHA256 != EXPECTED_COMPONENT_MANIFEST_SHA256
        or canonical_sha256(COMPONENT_MANIFEST) != EXPECTED_COMPONENT_MANIFEST_SHA256
        or transition.observe_fixed_windows_owner_policy_v4_transition_store is not _DEPENDENCY_PINS["observer"]
        or transition._validate_receipt is not _DEPENDENCY_PINS["transition_validate"]
        or transition._assert_integrity is not _DEPENDENCY_PINS["transition_integrity"]
        or compiler_v1._safe_snapshot_fixed_local_endpoints is not _DEPENDENCY_PINS["snapshot"]
        or compiler_v1._endpoint_comparison is not _DEPENDENCY_PINS["compare"]
    ):
        raise P0ActualReadinessBlockerCompilerV2Error("compiler V2 integrity drift")
    transition._assert_integrity()
    for label, value, code_sha, defaults, kwdefaults in _EXTERNAL_CODE_PINS:
        if (
            _stable_code_digest(value) != code_sha
            or value.__defaults__ != defaults or value.__kwdefaults__ != kwdefaults
        ):
            raise P0ActualReadinessBlockerCompilerV2Error(
                f"compiler V2 dependency code drift: {label}"
            )
    pins = globals().get("_SELF_HELPER_PINS")
    if pins is not None:
        for name, expected, code_sha, defaults, kwdefaults in pins:
            live = globals().get(name)
            if (
                live is not expected or _callable_code_sha256(live) != code_sha
                or getattr(live, "__defaults__", None) != defaults
                or getattr(live, "__kwdefaults__", None) != kwdefaults
            ):
                raise P0ActualReadinessBlockerCompilerV2Error(
                    f"compiler V2 helper drift: {name}"
                )


_SELF_HELPER_PINS = tuple(
    (
        name, value, _callable_code_sha256(value), value.__defaults__,
        dict(value.__kwdefaults__) if value.__kwdefaults__ is not None else None,
    )
    for name, value in (
        ("canonical_bytes", canonical_bytes), ("canonical_sha256", canonical_sha256),
        ("_stable_code_digest", _stable_code_digest),
        ("_validate_transition_receipt", _validate_transition_receipt),
        ("_execute_transition_once", _execute_transition_once),
        ("compile_fixed_p0_actual_readiness_blockers_v2", compile_fixed_p0_actual_readiness_blockers_v2),
        ("_validate_output", _validate_output), ("_assert_integrity", _assert_integrity),
        ("_callable_code_sha256", _callable_code_sha256),
    )
)


__all__ = [
    "GATE_STATUS", "OPERATIONAL_EFFECT", "P0ActualReadinessBlockerCompilerV2Error",
    "RECEIPT_SCHEMA", "compile_fixed_p0_actual_readiness_blockers_v2",
]
