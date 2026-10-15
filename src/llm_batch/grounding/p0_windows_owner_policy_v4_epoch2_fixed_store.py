"""Zero-input Windows fixed-store observer for owner policy V4 epoch 2.

This additive component deliberately does not extend or mutate the V1--V3
genesis store.  It owns a distinct, compiled ProgramData layout, opens every
directory and file by Win32 handle before reading the first byte, and replays
the presented V4 validator once while all handles and directory-change
watches remain live.  A successful observation is still component-only:
external root/key/code authority, trusted time, revocation, durable nonce,
write denial, runtime non-interference, semantic evidence and every production
gate remain false.
"""

from __future__ import annotations

from contextlib import ExitStack
import ctypes
import hashlib
import hmac
import inspect
import json
import marshal
import os
from typing import Any, Mapping

from llm_batch.grounding import p0_presented_a_context_annotation_packet_v2_windows_fixed_directory as fixed_win
from llm_batch.grounding import p0_windows_binary_acl_projection as binary_acl
from llm_batch.grounding import p0_windows_directory_change_watch as directory_watch
from llm_batch.grounding import p0_windows_fixed_owner_policy_store_candidate as legacy_store
from llm_batch.grounding import p0_windows_owner_policy_v4_packet_v2_profile_contract as v4
from llm_batch.grounding import p0_windows_owner_policy_v4_epoch2_fixed_store_parent_validator as parent_replay


RECEIPT_SCHEMA = "p0_windows_owner_policy_v4_epoch2_fixed_store_receipt_v1"
GATE_STATUS = "NO_GO_OWNER_POLICY_V4_EPOCH2_FIXED_STORE_COMPONENT_ONLY"
OPERATIONAL_EFFECT = "NONE_READ_ONLY_COMPONENT_OBSERVATION"
KNOWN_FOLDER_ID = "{62ab5d82-fdc1-4dc3-a9dd-070d1d495d97}"
KNOWN_FOLDER_FLAGS = 0
COMPILED_POLICY_EPOCH = 2
GENERATION_COMPONENT = f"{COMPILED_POLICY_EPOCH:020d}"
FIXED_STORE_SUFFIX = (
    "llm-novel-dc",
    "p0-owner-policy-v4-packet-v2",
)

FIXED_MEMBER_CONTRACT = (
    (
        "predecessor_policy_v3_body",
        "predecessor",
        "policy_v3_body.json",
        "application/json",
        256_000,
    ),
    (
        "predecessor_policy_v3_signature",
        "predecessor",
        "policy_v3_signature.json",
        "application/json",
        64_000,
    ),
    (
        "packet_v2_public_key_pin",
        "packet_v2",
        "p0_actual_owner_root_public_key_pin_v2.json",
        "application/json",
        64_000,
    ),
    (
        "policy_v4_body",
        "policy_v4",
        "body.json",
        "application/json",
        256_000,
    ),
    (
        "policy_v4_signature",
        "policy_v4",
        "signature.json",
        "application/json",
        64_000,
    ),
    (
        "bootstrap_public_key_spki",
        "bootstrap",
        "bootstrap_public_key_p256_spki.der",
        "application/pkix-key",
        1_024,
    ),
)
AGGREGATE_MEMBER_CAP_BYTES = sum(row[4] for row in FIXED_MEMBER_CONTRACT)

DIRECTORY_ROLES = (
    "policy_store",
    "generations_directory",
    "generation_directory",
    "predecessor_directory",
    "packet_v2_directory",
    "policy_v4_directory",
    "bootstrap_directory",
)
FILE_ROLES = tuple(row[0] for row in FIXED_MEMBER_CONTRACT)
ALL_ROLES = (*DIRECTORY_ROLES, *FILE_ROLES)

_PARENT_BY_ROLE = {
    "policy_store": None,
    "generations_directory": "policy_store",
    "generation_directory": "generations_directory",
    "predecessor_directory": "generation_directory",
    "packet_v2_directory": "generation_directory",
    "policy_v4_directory": "generation_directory",
    "bootstrap_directory": "generation_directory",
    "predecessor_policy_v3_body": "predecessor_directory",
    "predecessor_policy_v3_signature": "predecessor_directory",
    "packet_v2_public_key_pin": "packet_v2_directory",
    "policy_v4_body": "policy_v4_directory",
    "policy_v4_signature": "policy_v4_directory",
    "bootstrap_public_key_spki": "bootstrap_directory",
}
_NAME_BY_ROLE = {
    "policy_store": FIXED_STORE_SUFFIX[-1],
    "generations_directory": "generations",
    "generation_directory": GENERATION_COMPONENT,
    "predecessor_directory": "predecessor",
    "packet_v2_directory": "packet_v2",
    "policy_v4_directory": "policy_v4",
    "bootstrap_directory": "bootstrap",
    **{role: filename for role, _directory, filename, _media, _cap in FIXED_MEMBER_CONTRACT},
}
_DIRECTORY_INVENTORIES: Mapping[str, Mapping[str, bool]] = {
    "policy_store": {"generations": True},
    "generations_directory": {GENERATION_COMPONENT: True},
    "generation_directory": {
        "predecessor": True,
        "packet_v2": True,
        "policy_v4": True,
        "bootstrap": True,
    },
    "predecessor_directory": {
        "policy_v3_body.json": False,
        "policy_v3_signature.json": False,
    },
    "packet_v2_directory": {
        "p0_actual_owner_root_public_key_pin_v2.json": False,
    },
    "policy_v4_directory": {"body.json": False, "signature.json": False},
    "bootstrap_directory": {"bootstrap_public_key_p256_spki.der": False},
}

_WATCH_FILTER = (
    directory_watch.FILE_NOTIFY_CHANGE_FILE_NAME
    | directory_watch.FILE_NOTIFY_CHANGE_DIR_NAME
    | directory_watch.FILE_NOTIFY_CHANGE_ATTRIBUTES
    | directory_watch.FILE_NOTIFY_CHANGE_SIZE
    | directory_watch.FILE_NOTIFY_CHANGE_LAST_WRITE
    | directory_watch.FILE_NOTIFY_CHANGE_CREATION
    | directory_watch.FILE_NOTIFY_CHANGE_SECURITY
)
_READ_CONTROL = 0x00020000

_STRUCTURAL_TRUE_FIELDS = (
    "zero_input_known_folder_path_selected",
    "exact_epoch2_layout_verified",
    "all_ancestor_handles_held",
    "all_role_handles_open_before_first_read",
    "all_handles_non_inheritable_observed",
    "same_volume_unique_object_identity_verified",
    "directory_entry_handle_identity_verified",
    "single_link_non_reparse_unnamed_stream_verified",
    "raw_bundle_read_under_one_held_handle_interval",
    "v4_parent_first_validation_verified",
    "v4_parent_independent_replay_verified",
    "v4_child_receipt_second_strict_revalidation_verified",
    "member_pre_post_reopen_stable",
    "ancestor_pre_post_reopen_stable",
    "inventory_pre_post_stable",
    "binary_acl_pre_post_stable",
    "directory_change_interval_clean",
)
_AUTHORITY_FALSE_FIELDS = (
    "serialized_receipt_authoritative",
    "external_root_identity_pin_verified",
    "bootstrap_public_key_independently_pinned",
    "external_public_key_pin_provisioning_verified",
    "trusted_time_verified",
    "revocation_high_watermark_verified",
    "durable_nonce_state_verified",
    "external_root_authority_verified",
    "external_code_authority_verified",
    "os_write_deny_verified",
    "signed_native_runtime_witness_verified",
    "live_v3_fixed_store_predecessor_continuity_verified",
    "predecessor_bootstrap_signature_mathematics_verified",
    "runtime_noninterference_verified",
    "actual_semantic_evidence_verified",
    "owner_authority_verified",
    "actual_authority_granted",
    "public_apply_allowed",
    "wal_write_allowed",
    "central_slang_db_write_allowed",
    "production_approval",
    "full_scan_approval",
    "p0_phase_exit",
    "action_applied",
    "protected_pipeline_state_mutated",
)
_BLOCKER_ORDER = (
    "FIXED_V4_EPOCH2_STORE_NOT_VERIFIED",
    "V4_RAW_BUNDLE_NOT_VERIFIED",
    "V4_PARENT_REPLAY_NOT_VERIFIED",
    "BINARY_ACL_STABILITY_NOT_VERIFIED",
    "DIRECTORY_CHANGE_INTERVAL_NOT_VERIFIED",
    "LIVE_V3_FIXED_STORE_PREDECESSOR_CONTINUITY_NOT_VERIFIED",
    "PREDECESSOR_BOOTSTRAP_SIGNATURE_MATHEMATICS_NOT_VERIFIED",
    "EXTERNAL_PUBLIC_KEY_PIN_PROVISIONING_NOT_VERIFIED",
    "TRUSTED_TIME_NOT_VERIFIED",
    "REVOCATION_HIGH_WATERMARK_NOT_VERIFIED",
    "DURABLE_NONCE_STATE_NOT_VERIFIED",
    "EXTERNAL_ROOT_AUTHORITY_NOT_VERIFIED",
    "EXTERNAL_CODE_AUTHORITY_NOT_VERIFIED",
    "OS_WRITE_DENY_NOT_VERIFIED",
    "SIGNED_NATIVE_RUNTIME_WITNESS_NOT_VERIFIED",
    "RUNTIME_NONINTERFERENCE_NOT_VERIFIED",
    "ACTUAL_SEMANTIC_EVIDENCE_NOT_VERIFIED",
)

_RECEIPT_FIELDS = (
    "schema_version",
    "component_manifest_sha256",
    "fixed_member_contract_sha256",
    "gate_status",
    "decision",
    "known_folder_id",
    "known_folder_flags",
    "fixed_store_suffix",
    "selected_generation_component",
    "selected_policy_epoch",
    "member_sequence",
    "aggregate_member_cap_bytes",
    "failure_stage",
    "blocker_codes",
    "store_observation_succeeded",
    "root_final_path",
    "root_volume_serial_decimal",
    "root_file_id_128_hex",
    "ancestor_handle_count",
    "role_handle_count",
    "total_member_bytes",
    "member_raw_sha256_by_role",
    "member_evidence_sha256",
    "role_identity_projection_sha256",
    "inventory_projection_sha256",
    "binary_acl_projection_sha256_by_role",
    "binary_acl_projection_set_sha256",
    "directory_change_watches",
    "v4_contract_receipt",
    "v4_contract_receipt_declared_sha256",
    "v4_contract_receipt_full_canonical_sha256",
    "v4_parent_execution_count",
    "parent_replay_component_manifest_sha256",
    "parent_replay_receipt",
    "parent_replay_receipt_declared_sha256",
    "parent_replay_receipt_full_canonical_sha256",
    *_STRUCTURAL_TRUE_FIELDS,
    "caller_supplied_path_absent",
    "caller_supplied_environment_absent",
    "caller_supplied_epoch_absent",
    "caller_supplied_key_absent",
    "caller_supplied_time_absent",
    "caller_supplied_revocation_absent",
    "caller_supplied_nonce_absent",
    "caller_supplied_callback_absent",
    *_AUTHORITY_FALSE_FIELDS,
    "credited_actual_source_claim_count",
    "credited_actual_a_context_review_count",
    "operational_effect",
    "receipt_hash_scope",
    "receipt_sha256",
)


class P0WindowsOwnerPolicyV4Epoch2FixedStoreError(RuntimeError):
    """The V4 epoch2 fixed-store observation could not fail closed."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _semantic_contract_projection() -> dict[str, Any]:
    return {
        "schema": RECEIPT_SCHEMA,
        "gate_status": GATE_STATUS,
        "operational_effect": OPERATIONAL_EFFECT,
        "known_folder": [KNOWN_FOLDER_ID, KNOWN_FOLDER_FLAGS],
        "compiled_policy_epoch": COMPILED_POLICY_EPOCH,
        "generation_component": GENERATION_COMPONENT,
        "fixed_store_suffix": list(FIXED_STORE_SUFFIX),
        "fixed_member_contract": [list(row) for row in FIXED_MEMBER_CONTRACT],
        "aggregate_member_cap_bytes": AGGREGATE_MEMBER_CAP_BYTES,
        "directory_roles": list(DIRECTORY_ROLES),
        "file_roles": list(FILE_ROLES),
        "all_roles": list(ALL_ROLES),
        "parent_by_role": [
            [role, _PARENT_BY_ROLE[role]] for role in ALL_ROLES
        ],
        "name_by_role": [[role, _NAME_BY_ROLE[role]] for role in ALL_ROLES],
        "directory_inventories": [
            [role, [[name, is_directory] for name, is_directory in inventory.items()]]
            for role, inventory in _DIRECTORY_INVENTORIES.items()
        ],
        "watch_filter": _WATCH_FILTER,
        "read_control": _READ_CONTROL,
        "receipt_fields": list(_RECEIPT_FIELDS),
        "structural_true_fields": list(_STRUCTURAL_TRUE_FIELDS),
        "authority_false_fields": list(_AUTHORITY_FALSE_FIELDS),
        "blocker_order": list(_BLOCKER_ORDER),
        "v4_receipt_fields": list(v4._RECEIPT_FIELDS),
        "v4_true_fields": list(v4._RECEIPT_TRUE_FIELDS),
        "v4_false_fields": list(v4._RECEIPT_FALSE_FIELDS),
        "parent_raw_roles": list(parent_replay.RAW_ROLES),
        "parent_epochs": [
            parent_replay.EXPECTED_PREDECESSOR_EPOCH,
            parent_replay.EXPECTED_POLICY_EPOCH,
        ],
        "parent_semantic_contract_sha256": (
            parent_replay.EXPECTED_SEMANTIC_CONTRACT_SHA256
        ),
        "parent_manifest_sha256": parent_replay.EXPECTED_COMPONENT_MANIFEST_SHA256,
        "public_apis": ["observe_fixed_windows_owner_policy_v4_epoch2_store"],
    }


FIXED_MEMBER_CONTRACT_SHA256 = canonical_sha256(FIXED_MEMBER_CONTRACT)
EXPECTED_FIXED_MEMBER_CONTRACT_SHA256 = (
    "74909707f5ae5abc44c4d537f9355802f9104a607c585a46dd657e79094142a0"
)

SEMANTIC_CONTRACT_SHA256 = canonical_sha256(_semantic_contract_projection())
EXPECTED_SEMANTIC_CONTRACT_SHA256 = (
    "a0d9494c10b6519f6383e4ecab98d8f9a6650869b6cb11ced06b5f58c2aa51b7"
)

COMPONENT_MANIFEST = {
    "component": "p0_windows_owner_policy_v4_epoch2_fixed_store",
    "schemas": {"receipt": RECEIPT_SCHEMA},
    "known_folder_id": KNOWN_FOLDER_ID,
    "known_folder_flags": KNOWN_FOLDER_FLAGS,
    "fixed_store_suffix": FIXED_STORE_SUFFIX,
    "selected_policy_epoch": COMPILED_POLICY_EPOCH,
    "generation_component": GENERATION_COMPONENT,
    "fixed_member_contract_sha256": FIXED_MEMBER_CONTRACT_SHA256,
    "aggregate_member_cap_bytes": AGGREGATE_MEMBER_CAP_BYTES,
    "semantic_contract_sha256": SEMANTIC_CONTRACT_SHA256,
    "v4_component_manifest_sha256": v4.EXPECTED_COMPONENT_MANIFEST_SHA256,
    "parent_replay_component_manifest_sha256": (
        parent_replay.EXPECTED_COMPONENT_MANIFEST_SHA256
    ),
    "validation_architecture": (
        "ZERO_INPUT_KNOWN_FOLDER_HELD_ANCESTOR_AND_ROLE_HANDLES_"
        "ALL_FILES_OPEN_BEFORE_READ_V4_VALIDATE_ONCE_THEN_LOCAL_RECEIPT_REPLAY_"
        "PRE_POST_REOPEN_ACL_AND_WATCH"
    ),
    "public_apis": ("observe_fixed_windows_owner_policy_v4_epoch2_store",),
    "authority_boundary": GATE_STATUS,
}
COMPONENT_MANIFEST_SHA256 = canonical_sha256(COMPONENT_MANIFEST)
EXPECTED_COMPONENT_MANIFEST_SHA256 = (
    "6bfe0e80c26c707db3e0634700ad9d60574670179b33b610a10695e186ca0697"
)


_FIXED_WIN_MODULE = fixed_win
_BINARY_ACL_MODULE = binary_acl
_WATCH_MODULE = directory_watch
_LEGACY_STORE_MODULE = legacy_store
_V4_MODULE = v4
_PARENT_REPLAY_MODULE = parent_replay
_V4_VALIDATOR = v4.validate_presented_windows_owner_policy_v4_packet_v2_profile
_V4_VALIDATOR_PIN = _V4_VALIDATOR
_V4_RECEIPT_FIELDS_PIN = v4._RECEIPT_FIELDS
_V4_TRUE_FIELDS_PIN = v4._RECEIPT_TRUE_FIELDS
_V4_FALSE_FIELDS_PIN = v4._RECEIPT_FALSE_FIELDS
_V4_FUNCTION_SNAPSHOT = tuple(
    (
        name,
        value,
        value.__code__,
        value.__defaults__,
        value.__kwdefaults__,
        dict(value.__kwdefaults__) if value.__kwdefaults__ is not None else None,
    )
    for name, value in inspect.getmembers(v4, inspect.isfunction)
    if value.__module__ == v4.__name__
)


def _constant_snapshot_eligible(value: Any) -> bool:
    if type(value) in {str, int, bool, type(None)}:
        return True
    return type(value) is tuple and all(
        _constant_snapshot_eligible(item) for item in value
    )


_V4_CONSTANT_SNAPSHOT = tuple(
    (name, value, type(value))
    for name, value in vars(v4).items()
    if name.isupper() and _constant_snapshot_eligible(value)
)
_PARENT_REPLAY_VALIDATOR = parent_replay.validate_v4_epoch2_fixed_store_parent_replay
_PARENT_REPLAY_VALIDATOR_PIN = _PARENT_REPLAY_VALIDATOR


def _callable_code_sha256(value: Any) -> str:
    code = getattr(value, "__code__", None)
    if code is None:
        return ""
    material = (
        marshal.dumps(code)
        + repr(getattr(value, "__defaults__", None)).encode("utf-8")
        + repr(getattr(value, "__kwdefaults__", None)).encode("utf-8")
    )
    return hashlib.sha256(material).hexdigest()


_PARENT_HELPER_PINS = {
    name: (getattr(parent_replay, name), _callable_code_sha256(getattr(parent_replay, name)))
    for name in (
        "canonical_bytes",
        "canonical_sha256",
        "_semantic_contract_projection",
        "_duplicate_rejecting_object",
        "_reject_constant",
        "_parse_canonical",
        "_artifact_self_hash",
        "_lower_sha256",
        "_strict_child",
        "_expected_predecessor_receipt_sha256",
        "_verify_v4_signature_math",
        "_validate",
        "_code_sha256",
        "_assert_parent_integrity",
        "validate_v4_epoch2_fixed_store_parent_replay",
    )
}
_HASHLIB_SHA256_PIN = hashlib.sha256
_JSON_DUMPS_PIN = json.dumps
_PARENT_JSON_LOADS_PIN = parent_replay.json.loads
_PARENT_HMAC_COMPARE_DIGEST_PIN = parent_replay.hmac.compare_digest
_DEPENDENCY_CALLABLES = {
    "open_handle": fixed_win._open_handle,
    "query_snapshot": fixed_win._query_snapshot,
    "enumerate_directory": fixed_win._enumerate_directory,
    "read_handle_exact": fixed_win._read_handle_exact,
    "assert_directory": fixed_win._assert_directory,
    "assert_regular_single_link": fixed_win._assert_regular_single_link,
    "assert_not_case_sensitive_directory": fixed_win._assert_not_case_sensitive_directory,
    "assert_entry_matches_snapshot": fixed_win._assert_entry_matches_snapshot,
    "assert_direct_descendant": fixed_win._assert_direct_final_path_descendant,
    "lexical_ancestor_paths": fixed_win._lexical_ancestor_paths,
    "snapshot_stable": fixed_win._snapshot_stable,
    "snapshot_projection": fixed_win._snapshot_stable_projection,
    "ancestor_projection": fixed_win._ancestor_namespace_projection,
    "inventory_projection": fixed_win._inventory_projection,
    "observe_acl": binary_acl.observe_windows_binary_acl_projection,
    "program_data_path": legacy_store._program_data_path,
    "assert_non_inheritable": legacy_store._assert_non_inheritable,
}
_DEPENDENCY_CALLABLE_PINS = {
    name: (
        value,
        value.__code__,
        value.__defaults__,
        value.__kwdefaults__,
        dict(value.__kwdefaults__) if value.__kwdefaults__ is not None else None,
    )
    for name, value in _DEPENDENCY_CALLABLES.items()
}
_WATCH_CLASS = directory_watch.WindowsDirectoryChangeWatch
_OWNED_HANDLE_CLASS = fixed_win._OwnedHandle
_WIN32_CLASS_PIN = fixed_win._Win32
_HANDLE_FLAGS_CLASS_PIN = legacy_store._HandleFlagsApi
_WATCH_START_STATIC = inspect.getattr_static(_WATCH_CLASS, "start")
_WATCH_BARRIER_STATIC = inspect.getattr_static(_WATCH_CLASS, "barrier")
_WATCH_FINALIZE_STATIC = inspect.getattr_static(_WATCH_CLASS, "finalize")


def _descriptor_function(value: Any) -> Any:
    return value.__func__ if isinstance(value, (classmethod, staticmethod)) else value


_WATCH_METHOD_PINS = tuple(
    (
        name,
        value,
        _descriptor_function(value),
        _descriptor_function(value).__code__,
        _descriptor_function(value).__defaults__,
        _descriptor_function(value).__kwdefaults__,
        (
            dict(_descriptor_function(value).__kwdefaults__)
            if _descriptor_function(value).__kwdefaults__ is not None
            else None
        ),
    )
    for name, value in (
        ("start", _WATCH_START_STATIC),
        ("barrier", _WATCH_BARRIER_STATIC),
        ("finalize", _WATCH_FINALIZE_STATIC),
    )
)


def _assert_component_and_dependency_integrity() -> Any:
    if (
        FIXED_MEMBER_CONTRACT_SHA256
        != EXPECTED_FIXED_MEMBER_CONTRACT_SHA256
        or canonical_sha256(FIXED_MEMBER_CONTRACT)
        != EXPECTED_FIXED_MEMBER_CONTRACT_SHA256
        or SEMANTIC_CONTRACT_SHA256 != EXPECTED_SEMANTIC_CONTRACT_SHA256
        or canonical_sha256(_semantic_contract_projection())
        != EXPECTED_SEMANTIC_CONTRACT_SHA256
        or COMPONENT_MANIFEST_SHA256 != EXPECTED_COMPONENT_MANIFEST_SHA256
        or canonical_sha256(COMPONENT_MANIFEST)
        != EXPECTED_COMPONENT_MANIFEST_SHA256
        or fixed_win is not _FIXED_WIN_MODULE
        or binary_acl is not _BINARY_ACL_MODULE
        or directory_watch is not _WATCH_MODULE
        or legacy_store is not _LEGACY_STORE_MODULE
        or v4 is not _V4_MODULE
        or parent_replay is not _PARENT_REPLAY_MODULE
        or _V4_VALIDATOR is not _V4_VALIDATOR_PIN
        or v4.validate_presented_windows_owner_policy_v4_packet_v2_profile
        is not _V4_VALIDATOR_PIN
        or v4._RECEIPT_FIELDS != _V4_RECEIPT_FIELDS_PIN
        or v4._RECEIPT_TRUE_FIELDS != _V4_TRUE_FIELDS_PIN
        or v4._RECEIPT_FALSE_FIELDS != _V4_FALSE_FIELDS_PIN
        or v4.COMPONENT_MANIFEST_SHA256
        != v4.EXPECTED_COMPONENT_MANIFEST_SHA256
        or canonical_sha256(v4.COMPONENT_MANIFEST)
        != v4.EXPECTED_COMPONENT_MANIFEST_SHA256
        or v4.EXPECTED_COMPONENT_MANIFEST_SHA256
        != "9224e3c69c2748a882b81d5ccd29d02f3a9ad689e29a20ea6de6f100edbb9fc7"
        or _PARENT_REPLAY_VALIDATOR is not _PARENT_REPLAY_VALIDATOR_PIN
        or parent_replay.validate_v4_epoch2_fixed_store_parent_replay
        is not _PARENT_REPLAY_VALIDATOR_PIN
        or parent_replay.COMPONENT_MANIFEST_SHA256
        != parent_replay.EXPECTED_COMPONENT_MANIFEST_SHA256
        or canonical_sha256(parent_replay.COMPONENT_MANIFEST)
        != parent_replay.EXPECTED_COMPONENT_MANIFEST_SHA256
        or parent_replay.SEMANTIC_CONTRACT_SHA256
        != parent_replay.EXPECTED_SEMANTIC_CONTRACT_SHA256
        or canonical_sha256(parent_replay._semantic_contract_projection())
        != parent_replay.EXPECTED_SEMANTIC_CONTRACT_SHA256
        or parent_replay.EXPECTED_COMPONENT_MANIFEST_SHA256
        != "36eec436b81138357b87d5368029754ac846c901db75e640a0889adaadc209e8"
        or fixed_win._OwnedHandle is not _OWNED_HANDLE_CLASS
        or fixed_win._Win32 is not _WIN32_CLASS_PIN
        or legacy_store._HandleFlagsApi is not _HANDLE_FLAGS_CLASS_PIN
        or hashlib.sha256 is not _HASHLIB_SHA256_PIN
        or json.dumps is not _JSON_DUMPS_PIN
        or parent_replay.json.loads is not _PARENT_JSON_LOADS_PIN
        or parent_replay.hmac.compare_digest
        is not _PARENT_HMAC_COMPARE_DIGEST_PIN
    ):
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
            "V4 epoch2 fixed-store component/dependency pin drift"
        )
    for (
        name, expected, expected_code, expected_defaults,
        expected_kwdefaults, expected_kwdefaults_value,
    ) in _V4_FUNCTION_SNAPSHOT:
        live = getattr(v4, name, None)
        if (
            live is not expected
            or live.__code__ is not expected_code
            or live.__defaults__ is not expected_defaults
            or live.__kwdefaults__ is not expected_kwdefaults
            or live.__kwdefaults__ != expected_kwdefaults_value
        ):
            raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                f"V4 validation graph function drift: {name}"
            )
    for name, expected, expected_type in _V4_CONSTANT_SNAPSHOT:
        live = getattr(v4, name, None)
        if type(live) is not expected_type or live != expected:
            raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                f"V4 validation graph constant drift: {name}"
            )
    for name, (expected, expected_code_sha) in _PARENT_HELPER_PINS.items():
        live = getattr(parent_replay, name, None)
        if (
            live is not expected
            or _callable_code_sha256(live) != expected_code_sha
        ):
            raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                f"V4 parent replay helper drift: {name}"
            )
    for name, expected in _DEPENDENCY_CALLABLES.items():
        special = {
            "observe_acl": (binary_acl, "observe_windows_binary_acl_projection"),
            "program_data_path": (legacy_store, "_program_data_path"),
            "assert_non_inheritable": (legacy_store, "_assert_non_inheritable"),
        }
        fixed_attributes = {
            "open_handle": "_open_handle",
            "query_snapshot": "_query_snapshot",
            "enumerate_directory": "_enumerate_directory",
            "read_handle_exact": "_read_handle_exact",
            "assert_directory": "_assert_directory",
            "assert_regular_single_link": "_assert_regular_single_link",
            "assert_not_case_sensitive_directory": "_assert_not_case_sensitive_directory",
            "assert_entry_matches_snapshot": "_assert_entry_matches_snapshot",
            "assert_direct_descendant": "_assert_direct_final_path_descendant",
            "lexical_ancestor_paths": "_lexical_ancestor_paths",
            "snapshot_stable": "_snapshot_stable",
            "snapshot_projection": "_snapshot_stable_projection",
            "ancestor_projection": "_ancestor_namespace_projection",
            "inventory_projection": "_inventory_projection",
        }
        module, attribute = (
            special[name]
            if name in special
            else (fixed_win, fixed_attributes[name])
        )
        live = getattr(module, attribute)
        (
            _expected_object,
            expected_code,
            expected_defaults,
            expected_kwdefaults,
            expected_kwdefaults_value,
        ) = _DEPENDENCY_CALLABLE_PINS[name]
        if (
            live is not expected
            or live.__code__ is not expected_code
            or live.__defaults__ is not expected_defaults
            or live.__kwdefaults__ is not expected_kwdefaults
            or live.__kwdefaults__ != expected_kwdefaults_value
        ):
            raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                f"V4 epoch2 fixed-store dependency drift: {name}"
            )
    if (
        directory_watch.WindowsDirectoryChangeWatch is not _WATCH_CLASS
        or inspect.getattr_static(_WATCH_CLASS, "start") is not _WATCH_START_STATIC
        or inspect.getattr_static(_WATCH_CLASS, "barrier")
        is not _WATCH_BARRIER_STATIC
        or inspect.getattr_static(_WATCH_CLASS, "finalize")
        is not _WATCH_FINALIZE_STATIC
    ):
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
            "V4 epoch2 directory-watch dependency drift"
        )
    for (
        name, expected, expected_function, expected_code, expected_defaults,
        expected_kwdefaults, expected_kwdefaults_value,
    ) in _WATCH_METHOD_PINS:
        live = inspect.getattr_static(_WATCH_CLASS, name)
        live_function = _descriptor_function(live)
        if (
            live is not expected
            or live_function is not expected_function
            or live_function.__code__ is not expected_code
            or live_function.__defaults__ is not expected_defaults
            or live_function.__kwdefaults__ is not expected_kwdefaults
            or live_function.__kwdefaults__ != expected_kwdefaults_value
        ):
            raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                f"V4 epoch2 directory-watch method code drift: {name}"
            )
    helper_pins = globals().get("_SELF_HELPER_PINS")
    if helper_pins is not None:
        for name, expected, expected_code in helper_pins:
            live = globals().get(name)
            if live is not expected or _callable_code_sha256(live) != expected_code:
                raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                    f"V4 fixed-store private helper drift: {name}"
                )
    return _V4_VALIDATOR_PIN


def _paths(program_data_path: str) -> dict[str, str]:
    store = os.path.join(program_data_path, *FIXED_STORE_SUFFIX)
    generations = os.path.join(store, "generations")
    generation = os.path.join(generations, GENERATION_COMPONENT)
    paths = {
        "policy_store": store,
        "generations_directory": generations,
        "generation_directory": generation,
        "predecessor_directory": os.path.join(generation, "predecessor"),
        "packet_v2_directory": os.path.join(generation, "packet_v2"),
        "policy_v4_directory": os.path.join(generation, "policy_v4"),
        "bootstrap_directory": os.path.join(generation, "bootstrap"),
    }
    for role, directory, filename, _media, _cap in FIXED_MEMBER_CONTRACT:
        paths[role] = os.path.join(paths[f"{directory}_directory"], filename)
    return paths


def _open_role_handle(
    api: Any, path: str, *, directory: bool
) -> Any:
    if not directory:
        return fixed_win._open_handle(
            api, path, directory=False, read_data=True
        )
    desired = (
        fixed_win._FILE_READ_ATTRIBUTES
        | fixed_win._FILE_LIST_DIRECTORY
        | _READ_CONTROL
    )
    value = api.CreateFileW(
        path,
        desired,
        fixed_win._FILE_SHARE_READ,
        None,
        fixed_win._OPEN_EXISTING,
        fixed_win._FILE_FLAG_OPEN_REPARSE_POINT
        | fixed_win._FILE_FLAG_BACKUP_SEMANTICS,
        None,
    )
    if value == fixed_win._INVALID_HANDLE_VALUE:
        error = ctypes.get_last_error()
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
            f"open V4 ACL-readable directory failed with Windows error {error}"
        )
    return _OWNED_HANDLE_CLASS(api, value, path)


def _validate_inventory(
    values: Mapping[str, Any], expected: Mapping[str, bool], label: str
) -> None:
    if set(values) != set(expected):
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
            f"exact V4 epoch2 inventory mismatch: {label}"
        )
    for name, is_directory in expected.items():
        entry = values[name]
        observed_directory = bool(entry.attributes & fixed_win._FILE_ATTRIBUTE_DIRECTORY)
        if (
            observed_directory is not is_directory
            or bool(entry.attributes & fixed_win._FILE_ATTRIBUTE_REPARSE_POINT)
            or entry.reparse_tag != 0
        ):
            raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                f"V4 epoch2 inventory kind/reparse mismatch: {label}/{name}"
            )


def _assert_inventory_entry_matches_snapshot(
    entry: Any, snapshot: Any, *, directory: bool, label: str
) -> None:
    if not directory:
        fixed_win._assert_entry_matches_snapshot(entry, snapshot, label)
        return
    expected = (
        entry.file_id,
        entry.creation_time,
        entry.last_write_time,
        entry.change_time,
        entry.attributes,
        entry.reparse_tag,
    )
    observed = (
        snapshot.file_id,
        snapshot.basic[0],
        snapshot.basic[2],
        snapshot.basic[3],
        snapshot.basic[4],
        snapshot.reparse_tag,
    )
    if expected != observed:
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
            f"V4 directory-entry/handle identity mismatch: {label}"
        )


def _snapshot_stable(before: Any, after: Any) -> bool:
    return fixed_win._snapshot_stable(before, after)


def _identity_projection(snapshot: Any) -> dict[str, Any]:
    return {
        "final_path": snapshot.final_path,
        "volume_serial_decimal": str(snapshot.volume_serial),
        "file_id_128_hex": snapshot.file_id,
        "stable_projection_sha256": canonical_sha256(
            fixed_win._snapshot_stable_projection(snapshot)
        ),
    }


def _validate_v4_receipt(
    receipt: Any, *, raws: Mapping[str, bytes]
) -> dict[str, Any]:
    try:
        parent_replay._strict_child(receipt)
    except parent_replay.P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError as exc:
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
            "V4 parent receipt full exact-field replay mismatch"
        ) from exc
    if (
        type(receipt) is not dict
        or tuple(receipt) != _V4_RECEIPT_FIELDS_PIN
        or receipt.get("schema_version") != v4.RECEIPT_SCHEMA
        or receipt.get("gate_status") != v4.GATE_STATUS
        or any(receipt.get(field) is not True for field in _V4_TRUE_FIELDS_PIN)
        or any(receipt.get(field) is not False for field in _V4_FALSE_FIELDS_PIN)
        or type(receipt.get("credited_actual_source_claim_count")) is not int
        or receipt.get("credited_actual_source_claim_count") != 0
        or type(receipt.get("credited_actual_a_context_review_count")) is not int
        or receipt.get("credited_actual_a_context_review_count") != 0
    ):
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
            "V4 parent receipt structural replay mismatch"
        )
    expected_raw_bindings = {
        "predecessor_policy_v3_bytes_sha256": hashlib.sha256(
            raws["predecessor_policy_v3_body"]
        ).hexdigest(),
        "predecessor_policy_v3_signature_bytes_sha256": hashlib.sha256(
            raws["predecessor_policy_v3_signature"]
        ).hexdigest(),
        "packet_v2_public_key_pin_bytes_sha256": hashlib.sha256(
            raws["packet_v2_public_key_pin"]
        ).hexdigest(),
        "policy_v4_body_bytes_sha256": hashlib.sha256(
            raws["policy_v4_body"]
        ).hexdigest(),
        "policy_v4_signature_bytes_sha256": hashlib.sha256(
            raws["policy_v4_signature"]
        ).hexdigest(),
    }
    if any(
        receipt.get(field) != expected
        for field, expected in expected_raw_bindings.items()
    ):
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
            "V4 parent receipt/raw byte binding mismatch"
        )
    material = dict(receipt)
    declared = material.pop("receipt_sha256", None)
    if (
        type(declared) is not str
        or not hmac.compare_digest(declared, v4.canonical_sha256(material))
    ):
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
            "V4 parent receipt self-hash mismatch"
        )
    return receipt


def _run_v4_parent(
    raws: Mapping[str, bytes], *, checked_validator: Any
) -> dict[str, Any]:
    if checked_validator is not _V4_VALIDATOR_PIN:
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
            "unchecked V4 validator object"
        )
    return _validate_v4_receipt(checked_validator(
        predecessor_policy_v3_body_bytes=raws["predecessor_policy_v3_body"],
        predecessor_policy_v3_signature_bytes=raws[
            "predecessor_policy_v3_signature"
        ],
        packet_v2_public_key_pin_bytes=raws["packet_v2_public_key_pin"],
        policy_v4_body_bytes=raws["policy_v4_body"],
        policy_v4_signature_bytes=raws["policy_v4_signature"],
        bootstrap_public_key_spki_der=raws["bootstrap_public_key_spki"],
    ), raws=raws)


def _watch_projection(outcome: Any) -> dict[str, Any]:
    return {
        "schema_version": outcome.schema_version,
        "requested_path": outcome.requested_path,
        "identity": {
            "final_path": outcome.identity.final_path,
            "volume_serial_decimal": str(outcome.identity.volume_serial),
            "file_id_128_hex": outcome.identity.file_id,
        },
        "watch_subtree": outcome.watch_subtree,
        "notify_filter": outcome.notify_filter,
        "completion_status": outcome.completion_status,
        "pending_request_until_interval_end_observed": (
            outcome.pending_request_until_interval_end_observed
        ),
        "completion_drained_observed": outcome.completion_drained_observed,
        "watch_handles_non_inheritable_verified": (
            outcome.watch_handles_non_inheritable_verified
        ),
        "watch_handles_closed_observed": outcome.watch_handles_closed_observed,
        "directory_change_notification_delivered_observed": (
            outcome.directory_change_notification_delivered_observed
        ),
        "overflow_observed": outcome.overflow_observed,
        "observation_gap_observed": outcome.observation_gap_observed,
        "bounded_observation_verified": (
            outcome.project_source_directory_change_watch_observation_verified
        ),
    }


def _assert_watch_clean(outcome: Any) -> None:
    if (
        not outcome.project_source_directory_change_watch_observation_verified
        or outcome.directory_change_notification_delivered_observed
        or outcome.overflow_observed
        or outcome.observation_gap_observed
        or not outcome.pending_request_until_interval_end_observed
        or not outcome.completion_drained_observed
        or not outcome.watch_handles_non_inheritable_verified
        or not outcome.watch_handles_closed_observed
    ):
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
            "V4 epoch2 directory-change observation is not clean"
        )


def _observe_with_held_handles(
    program_data_path: str,
    paths: Mapping[str, str],
    watches: list[Any],
) -> dict[str, Any]:
    _assert_component_and_dependency_integrity()
    api = fixed_win._Win32()
    flags_api = legacy_store._HandleFlagsApi()
    store_path, ancestor_paths = fixed_win._lexical_ancestor_paths(
        paths["policy_store"]
    )
    if store_path != paths["policy_store"]:
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
            "V4 epoch2 store lexical normalization mismatch"
        )

    with ExitStack() as stack:
        ancestors: list[tuple[str, Any, Any]] = []
        for index, lexical_path in enumerate(ancestor_paths):
            handle = stack.enter_context(
                fixed_win._open_handle(
                    api, lexical_path, directory=True, read_data=False
                )
            )
            legacy_store._assert_non_inheritable(
                flags_api, handle.value, f"V4 ancestor {index}"
            )
            snapshot = fixed_win._query_snapshot(
                api, handle.value, include_streams=False
            )
            fixed_win._assert_directory(snapshot, f"V4 ancestor {index}")
            fixed_win._assert_not_case_sensitive_directory(
                api, handle.value, f"V4 ancestor {index}"
            )
            if ancestors:
                parent = ancestors[-1][2]
                if snapshot.volume_serial != parent.volume_serial:
                    raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                        "V4 ancestor chain crosses a volume"
                    )
                fixed_win._assert_direct_final_path_descendant(
                    parent.final_path, snapshot.final_path, f"V4 ancestor {index}"
                )
            ancestors.append((lexical_path, handle, snapshot))
        if not ancestors:
            raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                "V4 store requires held lexical ancestors"
            )

        held: dict[str, tuple[Any, Any]] = {}
        for role in ALL_ROLES:
            is_directory = role in DIRECTORY_ROLES
            handle = stack.enter_context(
                _open_role_handle(api, paths[role], directory=is_directory)
            )
            legacy_store._assert_non_inheritable(flags_api, handle.value, role)
            snapshot = fixed_win._query_snapshot(
                api, handle.value, include_streams=not is_directory
            )
            if is_directory:
                fixed_win._assert_directory(snapshot, role)
                fixed_win._assert_not_case_sensitive_directory(
                    api, handle.value, role
                )
            else:
                fixed_win._assert_regular_single_link(snapshot, role)
            held[role] = (handle, snapshot)

        seen: set[tuple[int, str]] = set()
        store_volume = held["policy_store"][1].volume_serial
        for role in ALL_ROLES:
            snapshot = held[role][1]
            if snapshot.volume_serial != store_volume:
                raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                    f"V4 epoch2 role crosses volume: {role}"
                )
            identity = (snapshot.volume_serial, snapshot.file_id)
            if identity in seen:
                raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                    "V4 epoch2 roles require unique object identities"
                )
            seen.add(identity)
            parent_role = _PARENT_BY_ROLE[role]
            parent = ancestors[-1][2] if parent_role is None else held[parent_role][1]
            expected_final = parent.final_path + "\\" + _NAME_BY_ROLE[role]
            if snapshot.final_path != expected_final:
                raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                    f"V4 epoch2 final path/casing mismatch: {role}"
                )
            fixed_win._assert_direct_final_path_descendant(
                parent.final_path, snapshot.final_path, role
            )

        expected_watch_snapshots = (ancestors[-1][2], held["policy_store"][1])
        for watch, expected in zip(watches, expected_watch_snapshots, strict=True):
            if (
                watch.identity.final_path != expected.final_path
                or watch.identity.volume_serial != expected.volume_serial
                or watch.identity.file_id != expected.file_id
            ):
                raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                    "V4 directory-watch identity/held handle mismatch"
                )

        inventory_before: dict[str, Mapping[str, Any]] = {}
        for role, expected in _DIRECTORY_INVENTORIES.items():
            inventory = fixed_win._enumerate_directory(api, held[role][0].value)
            _validate_inventory(inventory, expected, role)
            inventory_before[role] = inventory
            for child_role, parent_role in _PARENT_BY_ROLE.items():
                if parent_role == role:
                    _assert_inventory_entry_matches_snapshot(
                        inventory[_NAME_BY_ROLE[child_role]],
                        held[child_role][1],
                        directory=child_role in DIRECTORY_ROLES,
                        label=_NAME_BY_ROLE[child_role],
                    )

        # All six file handles are open and every individual/aggregate size is
        # bounded before this first read.
        raws: dict[str, bytes] = {}
        member_evidence: list[dict[str, Any]] = []
        total = 0
        cap_by_role = {row[0]: row[4] for row in FIXED_MEMBER_CONTRACT}
        media_by_role = {row[0]: row[3] for row in FIXED_MEMBER_CONTRACT}
        preflight_total = 0
        for role in FILE_ROLES:
            size = held[role][1].standard[1]
            if type(size) is not int or not 0 <= size <= cap_by_role[role]:
                raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                    f"V4 epoch2 member exceeds cap: {role}"
                )
            preflight_total += size
        if preflight_total > AGGREGATE_MEMBER_CAP_BYTES:
            raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                "V4 epoch2 aggregate member cap exceeded before first read"
            )
        for role in FILE_ROLES:
            handle, before = held[role]
            size = before.standard[1]
            raw = fixed_win._read_handle_exact(api, handle.value, size, role)
            after_read = fixed_win._query_snapshot(
                api, handle.value, include_streams=True
            )
            if not _snapshot_stable(before, after_read):
                raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                    f"V4 epoch2 member changed while read: {role}"
                )
            raws[role] = raw
            total += len(raw)
            member_evidence.append({
                "role": role,
                "path": paths[role],
                "media_type": media_by_role[role],
                "max_bytes": cap_by_role[role],
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                **_identity_projection(before),
            })
        if total > AGGREGATE_MEMBER_CAP_BYTES:
            raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                "V4 epoch2 aggregate member cap exceeded"
            )

        checked_validator = _assert_component_and_dependency_integrity()
        first_parent = _run_v4_parent(
            raws, checked_validator=checked_validator
        )
        _assert_component_and_dependency_integrity()
        independent_parent = _PARENT_REPLAY_VALIDATOR(
            raw_bundle=raws,
            child_receipt=first_parent,
        )
        _assert_component_and_dependency_integrity()

        acl_before: dict[str, Any] = {}
        acl_hashes: dict[str, str] = {}
        for role in ALL_ROLES:
            projection = binary_acl.observe_windows_binary_acl_projection(
                handle=held[role][0].value
            )
            acl_before[role] = projection
            acl_hashes[role] = canonical_sha256(projection)

        for watch in watches:
            barrier = watch.barrier()
            if not barrier.observation_acceptable:
                raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                    "V4 directory watch completed before interval end: "
                    f"{barrier.completion_status}"
                )

        inventory_after: dict[str, Mapping[str, Any]] = {}
        for role, expected in _DIRECTORY_INVENTORIES.items():
            inventory = fixed_win._enumerate_directory(api, held[role][0].value)
            _validate_inventory(inventory, expected, role)
            inventory_after[role] = inventory
            if fixed_win._inventory_projection(inventory_before[role]) != (
                fixed_win._inventory_projection(inventory)
            ):
                raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                    f"V4 epoch2 directory inventory changed: {role}"
                )

        role_after: dict[str, Any] = {}
        for role in ALL_ROLES:
            is_directory = role in DIRECTORY_ROLES
            handle, before = held[role]
            after = fixed_win._query_snapshot(
                api, handle.value, include_streams=not is_directory
            )
            if not _snapshot_stable(before, after):
                raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                    f"V4 epoch2 role changed: {role}"
                )
            role_after[role] = after
            projection = binary_acl.observe_windows_binary_acl_projection(
                handle=handle.value
            )
            if canonical_sha256(projection) != acl_hashes[role]:
                raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                    f"V4 epoch2 binary ACL changed: {role}"
                )

        for role in ALL_ROLES:
            is_directory = role in DIRECTORY_ROLES
            with fixed_win._open_handle(
                api, paths[role], directory=is_directory, read_data=False
            ) as reopened:
                legacy_store._assert_non_inheritable(
                    flags_api, reopened.value, f"reopened {role}"
                )
                reopened_snapshot = fixed_win._query_snapshot(
                    api, reopened.value, include_streams=not is_directory
                )
                if not _snapshot_stable(role_after[role], reopened_snapshot):
                    raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                        f"V4 epoch2 reopen mismatch: {role}"
                    )

        for index, (path, handle, before) in enumerate(ancestors):
            after = fixed_win._query_snapshot(
                api, handle.value, include_streams=False
            )
            if fixed_win._ancestor_namespace_projection(before) != (
                fixed_win._ancestor_namespace_projection(after)
            ):
                raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                    f"V4 ancestor changed: {index}"
                )
            with fixed_win._open_handle(
                api, path, directory=True, read_data=False
            ) as reopened:
                legacy_store._assert_non_inheritable(
                    flags_api, reopened.value, f"reopened ancestor {index}"
                )
                snapshot = fixed_win._query_snapshot(
                    api, reopened.value, include_streams=False
                )
                if fixed_win._ancestor_namespace_projection(after) != (
                    fixed_win._ancestor_namespace_projection(snapshot)
                ):
                    raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                        f"V4 ancestor reopen mismatch: {index}"
                    )

        # Recheck the child receipt locally without invoking its producer a
        # second time; the distinct parent module above owns the independent
        # raw/schema/epoch/scope replay.
        _assert_component_and_dependency_integrity()
        replay_parent = _validate_v4_receipt(first_parent, raws=raws)
        _assert_component_and_dependency_integrity()
        if replay_parent != first_parent:
            raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
                "V4 parent first/replay receipts differ"
            )

        role_projection = {
            role: _identity_projection(held[role][1]) for role in ALL_ROLES
        }
        inventory_projection = {
            role: fixed_win._inventory_projection(inventory_before[role])
            for role in _DIRECTORY_INVENTORIES
        }
        raw_hashes = {
            role: hashlib.sha256(raws[role]).hexdigest() for role in FILE_ROLES
        }
        return {
            "root_final_path": held["policy_store"][1].final_path,
            "root_volume_serial_decimal": str(store_volume),
            "root_file_id_128_hex": held["policy_store"][1].file_id,
            "ancestor_handle_count": len(ancestors),
            "role_handle_count": len(held),
            "total_member_bytes": total,
            "member_raw_sha256_by_role": raw_hashes,
            "member_evidence_sha256": canonical_sha256(member_evidence),
            "role_identity_projection_sha256": canonical_sha256(role_projection),
            "inventory_projection_sha256": canonical_sha256(inventory_projection),
            "binary_acl_projection_sha256_by_role": acl_hashes,
            "binary_acl_projection_set_sha256": canonical_sha256(acl_hashes),
            "v4_contract_receipt": first_parent,
            "v4_contract_receipt_declared_sha256": first_parent["receipt_sha256"],
            "v4_contract_receipt_full_canonical_sha256": canonical_sha256(
                first_parent
            ),
            "parent_replay_component_manifest_sha256": (
                parent_replay.COMPONENT_MANIFEST_SHA256
            ),
            "parent_replay_receipt": independent_parent,
            "parent_replay_receipt_declared_sha256": independent_parent[
                "receipt_sha256"
            ],
            "parent_replay_receipt_full_canonical_sha256": canonical_sha256(
                independent_parent
            ),
        }


def _observe_at_program_data(program_data_path: str) -> dict[str, Any]:
    _assert_component_and_dependency_integrity()
    paths = _paths(program_data_path)
    watch_paths = (
        os.path.join(program_data_path, FIXED_STORE_SUFFIX[0]),
        paths["policy_store"],
    )
    watches: list[Any] = []
    outcomes: list[Any] = []
    primary: BaseException | None = None
    evidence: dict[str, Any] | None = None
    try:
        for path in watch_paths:
            watches.append(directory_watch.WindowsDirectoryChangeWatch.start(
                path, watch_subtree=True, notify_filter=_WATCH_FILTER
            ))
        evidence = _observe_with_held_handles(program_data_path, paths, watches)
    except BaseException as exc:
        primary = exc
    finally:
        for watch in reversed(watches):
            try:
                outcomes.append(watch.finalize())
            except BaseException as cleanup_error:
                if primary is None:
                    primary = cleanup_error
    if primary is not None:
        if isinstance(primary, (KeyboardInterrupt, SystemExit)):
            raise primary
        if isinstance(primary, P0WindowsOwnerPolicyV4Epoch2FixedStoreError):
            raise primary
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
            "V4 epoch2 fixed-store observation failed closed"
        ) from primary
    assert evidence is not None
    outcomes.reverse()
    for outcome in outcomes:
        _assert_watch_clean(outcome)
    _assert_component_and_dependency_integrity()
    return _success_receipt(
        evidence=evidence,
        watch_projection=[_watch_projection(value) for value in outcomes],
    )


def _base_material() -> dict[str, Any]:
    return {
        "schema_version": RECEIPT_SCHEMA,
        "component_manifest_sha256": COMPONENT_MANIFEST_SHA256,
        "fixed_member_contract_sha256": FIXED_MEMBER_CONTRACT_SHA256,
        "gate_status": GATE_STATUS,
        "decision": "NO_GO",
        "known_folder_id": KNOWN_FOLDER_ID,
        "known_folder_flags": KNOWN_FOLDER_FLAGS,
        "fixed_store_suffix": list(FIXED_STORE_SUFFIX),
        "selected_generation_component": GENERATION_COMPONENT,
        "selected_policy_epoch": COMPILED_POLICY_EPOCH,
        "member_sequence": list(FILE_ROLES),
        "aggregate_member_cap_bytes": AGGREGATE_MEMBER_CAP_BYTES,
    }


def _seal(material: Mapping[str, Any]) -> dict[str, Any]:
    actual_fields = tuple(material) + ("receipt_sha256",)
    if actual_fields != _RECEIPT_FIELDS:
        first_drift = next(
            (
                (index, actual, expected)
                for index, (actual, expected) in enumerate(
                    zip(actual_fields, _RECEIPT_FIELDS, strict=False)
                )
                if actual != expected
            ),
            None,
        )
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
            f"V4 epoch2 receipt exact field drift: {first_drift}"
        )
    return {**material, "receipt_sha256": canonical_sha256(material)}


def _success_receipt(
    *, evidence: Mapping[str, Any], watch_projection: list[dict[str, Any]]
) -> dict[str, Any]:
    material = {
        **_base_material(),
        "failure_stage": "EXTERNAL_STATE",
        "blocker_codes": list(_BLOCKER_ORDER[5:]),
        "store_observation_succeeded": True,
        "root_final_path": evidence["root_final_path"],
        "root_volume_serial_decimal": evidence["root_volume_serial_decimal"],
        "root_file_id_128_hex": evidence["root_file_id_128_hex"],
        "ancestor_handle_count": evidence["ancestor_handle_count"],
        "role_handle_count": evidence["role_handle_count"],
        "total_member_bytes": evidence["total_member_bytes"],
        "member_raw_sha256_by_role": evidence["member_raw_sha256_by_role"],
        "member_evidence_sha256": evidence["member_evidence_sha256"],
        "role_identity_projection_sha256": evidence[
            "role_identity_projection_sha256"
        ],
        "inventory_projection_sha256": evidence["inventory_projection_sha256"],
        "binary_acl_projection_sha256_by_role": evidence[
            "binary_acl_projection_sha256_by_role"
        ],
        "binary_acl_projection_set_sha256": evidence[
            "binary_acl_projection_set_sha256"
        ],
        "directory_change_watches": watch_projection,
        "v4_contract_receipt": evidence["v4_contract_receipt"],
        "v4_contract_receipt_declared_sha256": evidence[
            "v4_contract_receipt_declared_sha256"
        ],
        "v4_contract_receipt_full_canonical_sha256": evidence[
            "v4_contract_receipt_full_canonical_sha256"
        ],
        "v4_parent_execution_count": 1,
        "parent_replay_component_manifest_sha256": evidence[
            "parent_replay_component_manifest_sha256"
        ],
        "parent_replay_receipt": evidence["parent_replay_receipt"],
        "parent_replay_receipt_declared_sha256": evidence[
            "parent_replay_receipt_declared_sha256"
        ],
        "parent_replay_receipt_full_canonical_sha256": evidence[
            "parent_replay_receipt_full_canonical_sha256"
        ],
        **{field: True for field in _STRUCTURAL_TRUE_FIELDS},
        "caller_supplied_path_absent": True,
        "caller_supplied_environment_absent": True,
        "caller_supplied_epoch_absent": True,
        "caller_supplied_key_absent": True,
        "caller_supplied_time_absent": True,
        "caller_supplied_revocation_absent": True,
        "caller_supplied_nonce_absent": True,
        "caller_supplied_callback_absent": True,
        **{field: False for field in _AUTHORITY_FALSE_FIELDS},
        "credited_actual_source_claim_count": 0,
        "credited_actual_a_context_review_count": 0,
        "operational_effect": OPERATIONAL_EFFECT,
        "receipt_hash_scope": "CANONICAL_MATERIAL_EXCLUDING_RECEIPT_SHA256",
    }
    return _seal(material)


def _failure_receipt(*, stage: str) -> dict[str, Any]:
    material = {
        **_base_material(),
        "failure_stage": stage,
        "blocker_codes": list(_BLOCKER_ORDER),
        "store_observation_succeeded": False,
        "root_final_path": "",
        "root_volume_serial_decimal": "",
        "root_file_id_128_hex": "",
        "ancestor_handle_count": 0,
        "role_handle_count": 0,
        "total_member_bytes": 0,
        "member_raw_sha256_by_role": {},
        "member_evidence_sha256": "",
        "role_identity_projection_sha256": "",
        "inventory_projection_sha256": "",
        "binary_acl_projection_sha256_by_role": {},
        "binary_acl_projection_set_sha256": "",
        "directory_change_watches": [],
        "v4_contract_receipt": {},
        "v4_contract_receipt_declared_sha256": "",
        "v4_contract_receipt_full_canonical_sha256": "",
        "v4_parent_execution_count": 0,
        "parent_replay_component_manifest_sha256": (
            parent_replay.COMPONENT_MANIFEST_SHA256
        ),
        "parent_replay_receipt": {},
        "parent_replay_receipt_declared_sha256": "",
        "parent_replay_receipt_full_canonical_sha256": "",
        **{field: False for field in _STRUCTURAL_TRUE_FIELDS},
        "caller_supplied_path_absent": True,
        "caller_supplied_environment_absent": True,
        "caller_supplied_epoch_absent": True,
        "caller_supplied_key_absent": True,
        "caller_supplied_time_absent": True,
        "caller_supplied_revocation_absent": True,
        "caller_supplied_nonce_absent": True,
        "caller_supplied_callback_absent": True,
        **{field: False for field in _AUTHORITY_FALSE_FIELDS},
        "credited_actual_source_claim_count": 0,
        "credited_actual_a_context_review_count": 0,
        "operational_effect": OPERATIONAL_EFFECT,
        "receipt_hash_scope": "CANONICAL_MATERIAL_EXCLUDING_RECEIPT_SHA256",
    }
    return _seal(material)


def _validate_final_receipt(
    receipt: Any, *, expected_stage: str, expected_success: bool
) -> dict[str, Any]:
    caller_absence_fields = (
        "caller_supplied_path_absent",
        "caller_supplied_environment_absent",
        "caller_supplied_epoch_absent",
        "caller_supplied_key_absent",
        "caller_supplied_time_absent",
        "caller_supplied_revocation_absent",
        "caller_supplied_nonce_absent",
        "caller_supplied_callback_absent",
    )
    if (
        type(receipt) is not dict
        or tuple(receipt) != _RECEIPT_FIELDS
        or receipt.get("schema_version") != RECEIPT_SCHEMA
        or receipt.get("component_manifest_sha256") != COMPONENT_MANIFEST_SHA256
        or receipt.get("fixed_member_contract_sha256")
        != FIXED_MEMBER_CONTRACT_SHA256
        or receipt.get("gate_status") != GATE_STATUS
        or receipt.get("decision") != "NO_GO"
        or receipt.get("failure_stage") != expected_stage
        or receipt.get("store_observation_succeeded") is not expected_success
        or receipt.get("operational_effect") != OPERATIONAL_EFFECT
        or receipt.get("receipt_hash_scope")
        != "CANONICAL_MATERIAL_EXCLUDING_RECEIPT_SHA256"
        or any(receipt.get(field) is not True for field in caller_absence_fields)
        or any(receipt.get(field) is not False for field in _AUTHORITY_FALSE_FIELDS)
        or type(receipt.get("credited_actual_source_claim_count")) is not int
        or receipt.get("credited_actual_source_claim_count") != 0
        or type(receipt.get("credited_actual_a_context_review_count")) is not int
        or receipt.get("credited_actual_a_context_review_count") != 0
        or any(
            receipt.get(field) is not expected_success
            for field in _STRUCTURAL_TRUE_FIELDS
        )
        or type(receipt.get("v4_parent_execution_count")) is not int
        or receipt.get("v4_parent_execution_count") != (1 if expected_success else 0)
    ):
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
            "V4 epoch2 final receipt exact denial/truth-table mismatch"
        )
    material = dict(receipt)
    declared = material.pop("receipt_sha256", None)
    if (
        type(declared) is not str
        or len(declared) != 64
        or not hmac.compare_digest(declared, canonical_sha256(material))
    ):
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreError(
            "V4 epoch2 final receipt self-hash mismatch"
        )
    return receipt


def _checked_failure_receipt(stage: str) -> dict[str, Any]:
    _assert_component_and_dependency_integrity()
    candidate = _failure_receipt(stage=stage)
    _assert_component_and_dependency_integrity()
    return _validate_final_receipt(
        candidate, expected_stage=stage, expected_success=False
    )


_SELF_HELPER_PINS = tuple(
    (name, value, _callable_code_sha256(value))
    for name, value in (
        ("canonical_bytes", canonical_bytes),
        ("canonical_sha256", canonical_sha256),
        ("_semantic_contract_projection", _semantic_contract_projection),
        ("_descriptor_function", _descriptor_function),
        ("_constant_snapshot_eligible", _constant_snapshot_eligible),
        ("_assert_component_and_dependency_integrity", _assert_component_and_dependency_integrity),
        ("_paths", _paths),
        ("_open_role_handle", _open_role_handle),
        ("_validate_inventory", _validate_inventory),
        ("_assert_inventory_entry_matches_snapshot", _assert_inventory_entry_matches_snapshot),
        ("_snapshot_stable", _snapshot_stable),
        ("_identity_projection", _identity_projection),
        ("_validate_v4_receipt", _validate_v4_receipt),
        ("_run_v4_parent", _run_v4_parent),
        ("_watch_projection", _watch_projection),
        ("_assert_watch_clean", _assert_watch_clean),
        ("_observe_with_held_handles", _observe_with_held_handles),
        ("_observe_at_program_data", _observe_at_program_data),
        ("_base_material", _base_material),
        ("_seal", _seal),
        ("_success_receipt", _success_receipt),
        ("_failure_receipt", _failure_receipt),
        ("_validate_final_receipt", _validate_final_receipt),
        ("_checked_failure_receipt", _checked_failure_receipt),
    )
)


def observe_fixed_windows_owner_policy_v4_epoch2_store() -> dict[str, Any]:
    """Observe the compiled ProgramData V4 epoch2 layout without caller inputs."""

    # Integrity failure propagates.  Calling any module-global receipt builder
    # after integrity has failed would let the compromised helper choose the
    # returned truth table.
    _assert_component_and_dependency_integrity()
    if os.name != "nt":
        return _checked_failure_receipt("PLATFORM")
    try:
        program_data_path = legacy_store._program_data_path(
            legacy_store._KnownFolderApi()
        )
        if not os.path.isdir(_paths(program_data_path)["policy_store"]):
            return _checked_failure_receipt("FIXED_STORE")
        receipt = _observe_at_program_data(program_data_path)
        _assert_component_and_dependency_integrity()
        return _validate_final_receipt(
            receipt, expected_stage="EXTERNAL_STATE", expected_success=True
        )
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        return _checked_failure_receipt("VALIDATION")


__all__ = [
    "AGGREGATE_MEMBER_CAP_BYTES",
    "ALL_ROLES",
    "COMPILED_POLICY_EPOCH",
    "COMPONENT_MANIFEST",
    "COMPONENT_MANIFEST_SHA256",
    "DIRECTORY_ROLES",
    "EXPECTED_COMPONENT_MANIFEST_SHA256",
    "EXPECTED_FIXED_MEMBER_CONTRACT_SHA256",
    "FILE_ROLES",
    "FIXED_MEMBER_CONTRACT",
    "FIXED_MEMBER_CONTRACT_SHA256",
    "FIXED_STORE_SUFFIX",
    "GATE_STATUS",
    "GENERATION_COMPONENT",
    "KNOWN_FOLDER_ID",
    "P0WindowsOwnerPolicyV4Epoch2FixedStoreError",
    "RECEIPT_SCHEMA",
    "observe_fixed_windows_owner_policy_v4_epoch2_store",
]
