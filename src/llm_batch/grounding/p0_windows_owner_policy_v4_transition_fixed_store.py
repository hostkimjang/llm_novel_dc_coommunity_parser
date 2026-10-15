"""Zero-input, read-only live V3 -> V4 fixed-store transition observer.

All eight V3 roles and thirteen V4 roles are opened before the first member
byte is read.  Three directory watches remain armed for the entire held-handle
interval.  Success is component-only and cannot grant owner authority.
"""

from __future__ import annotations

from contextlib import ExitStack
import hashlib
import hmac
import inspect
import os
from typing import Any, Mapping

from . import p0_windows_binary_acl_projection as acl
from . import p0_windows_directory_change_watch as watch_module
from . import p0_windows_fixed_directory_identity as fixed
from . import p0_windows_fixed_owner_policy_store_candidate as v3_store
from . import p0_windows_owner_policy_contract as v3_contract
from . import p0_windows_owner_policy_v4_epoch2_fixed_store as v4_store
from . import p0_windows_owner_policy_v4_epoch2_fixed_store_parent_validator as v4_parent
from . import p0_windows_owner_policy_v4_packet_v2_profile_contract as v4_contract
from . import p0_windows_owner_policy_v4_transition_parent_validator as transition_parent


RECEIPT_SCHEMA = "p0_windows_owner_policy_v4_transition_fixed_store_receipt_v1"
GATE_STATUS = "NO_GO_OWNER_POLICY_V3_V4_TRANSITION_COMPONENT_ONLY"
OPERATIONAL_EFFECT = "NONE_READ_ONLY_COMPONENT_OBSERVATION"
ROLE_SEQUENCE = tuple(
    [f"v3:{role}" for role in v3_contract.OBJECT_ROLES]
    + [f"v4:{role}" for role in v4_store.ALL_ROLES]
)
FILE_ROLE_SEQUENCE = tuple(
    [f"v3:{role}" for role in v3_contract.OBJECT_ROLES[5:]]
    + [f"v4:{role}" for role in v4_store.FILE_ROLES]
)
DIRECTORY_ROLE_SEQUENCE = tuple(role for role in ROLE_SEQUENCE if role not in FILE_ROLE_SEQUENCE)
WATCH_SCOPE_SEQUENCE = ("common_parent", "v3_store", "v4_store")
_CAPS = {
    "v3:policy_body_file": 256_000,
    "v3:policy_signature_file": 64_000,
    "v3:public_key_pin_file": 64_000,
    **{f"v4:{row[0]}": row[4] for row in v4_store.FIXED_MEMBER_CONTRACT},
}
AGGREGATE_CAP_BYTES = sum(_CAPS.values())
_TRUE_FIELDS = (
    "zero_input_known_folder_path_selected",
    "three_directory_watches_armed_before_role_open",
    "all_twenty_one_role_handles_open_before_first_read",
    "all_role_handles_held_across_both_policy_validations",
    "all_handles_non_inheritable_observed",
    "same_volume_unique_object_identity_verified",
    "all_nine_member_sizes_bounded_before_first_read",
    "raw_transition_bundle_read_under_one_held_interval",
    "live_v3_embedded_predecessor_bytes_exactly_equal",
    "v3_signed_object_identity_exact_match_verified",
    "v4_contract_producer_executed_once",
    "v4_parent_replay_cross_checked_by_transition_parent",
    "transition_parent_strict_replay_verified",
    "presented_spki_v3_v4_signature_mathematics_verified",
    "epoch_one_to_two_transition_verified",
    "role_pre_post_and_reopen_stable",
    "inventory_pre_post_stable",
    "binary_acl_pre_post_stable",
    "directory_change_interval_clean",
    "three_watch_intersection_counter_verified",
    "v3_signed_acl_exact_match_verified",
    "common_parent_required_store_entries_bound",
    "ancestor_pre_post_and_reopen_stable",
)
_FALSE_FIELDS = (
    "serialized_receipt_authoritative", "external_root_identity_pin_verified",
    "bootstrap_public_key_independently_pinned",
    "external_public_key_pin_provisioning_verified", "external_root_authority_verified",
    "external_code_authority_verified", "trusted_time_verified",
    "revocation_high_watermark_verified", "durable_nonce_state_verified",
    "os_write_deny_verified", "signed_native_runtime_witness_verified",
    "runtime_noninterference_verified", "actual_semantic_evidence_verified",
    "owner_authority_verified", "actual_authority_granted", "public_apply_allowed",
    "wal_write_allowed", "central_slang_db_write_allowed", "production_approval",
    "full_scan_approval", "p0_phase_exit", "action_applied",
    "protected_pipeline_state_mutated",
)
_BLOCKERS = (
    "V3_V4_TRANSITION_FIXED_STORE_NOT_VERIFIED",
    "TWENTY_ONE_HELD_ROLE_INTERVAL_NOT_VERIFIED",
    "THREE_WATCH_INTERSECTION_NOT_VERIFIED",
    "LIVE_EMBEDDED_PREDECESSOR_CONTINUITY_NOT_VERIFIED",
    "PRESENTED_SPKI_DUAL_SIGNATURE_MATH_NOT_VERIFIED",
    "V3_SIGNED_ACL_NOT_VERIFIED",
    "COMMON_PARENT_STORE_BINDING_NOT_VERIFIED",
    "PRE_POST_REOPEN_STABILITY_NOT_VERIFIED",
    "TRANSITION_PARENT_STRICT_REPLAY_NOT_VERIFIED",
    "BOOTSTRAP_PUBLIC_KEY_INDEPENDENT_PIN_NOT_VERIFIED",
    "EXTERNAL_PUBLIC_KEY_PIN_PROVISIONING_NOT_VERIFIED",
    "TRUSTED_TIME_NOT_VERIFIED", "REVOCATION_HIGH_WATERMARK_NOT_VERIFIED",
    "DURABLE_NONCE_STATE_NOT_VERIFIED", "EXTERNAL_ROOT_AUTHORITY_NOT_VERIFIED",
    "EXTERNAL_CODE_AUTHORITY_NOT_VERIFIED", "OS_WRITE_DENY_NOT_VERIFIED",
    "SIGNED_NATIVE_RUNTIME_WITNESS_NOT_VERIFIED",
    "RUNTIME_NONINTERFERENCE_NOT_VERIFIED", "ACTUAL_SEMANTIC_EVIDENCE_NOT_VERIFIED",
)
_EVIDENCE_FIELDS = (
    "role_handle_count", "file_handle_count", "ancestor_handle_count",
    "total_member_bytes", "raw_sha256_by_role",
    "role_identity_projection_sha256", "inventory_projection_sha256",
    "binary_acl_projection_set_sha256", "v3_contract_receipt_declared_sha256",
    "v4_child_receipt_declared_sha256", "v4_parent_receipt_declared_sha256",
    "transition_parent_receipt", "transition_parent_receipt_declared_sha256",
    "transition_parent_receipt_full_canonical_sha256",
)
_RECEIPT_FIELDS = (
    "schema_version", "gate_status", "decision", "failure_stage", "blocker_codes",
    "role_sequence", "file_role_sequence", "watch_scope_sequence", *_EVIDENCE_FIELDS,
    "directory_change_watches", *_TRUE_FIELDS, *_FALSE_FIELDS,
    "credited_actual_source_claim_count", "credited_actual_a_context_review_count",
    "operational_effect", "receipt_sha256",
)


def _semantic_contract_projection() -> dict[str, Any]:
    return {
        "schema": RECEIPT_SCHEMA, "gate_status": GATE_STATUS,
        "operational_effect": OPERATIONAL_EFFECT,
        "roles": list(ROLE_SEQUENCE), "file_roles": list(FILE_ROLE_SEQUENCE),
        "watch_scopes": list(WATCH_SCOPE_SEQUENCE), "caps": dict(_CAPS),
        "aggregate_cap": AGGREGATE_CAP_BYTES, "true_fields": list(_TRUE_FIELDS),
        "false_fields": list(_FALSE_FIELDS), "blockers": list(_BLOCKERS),
        "receipt_fields": list(_RECEIPT_FIELDS),
        "transition_parent_manifest": transition_parent.EXPECTED_COMPONENT_MANIFEST_SHA256,
    }


SEMANTIC_CONTRACT_SHA256 = "365e91b353e8db275750507c96af1670fedcff4609aecfea705d514044fc24b5"
EXPECTED_SEMANTIC_CONTRACT_SHA256 = "365e91b353e8db275750507c96af1670fedcff4609aecfea705d514044fc24b5"
COMPONENT_MANIFEST = {
    "component": "p0_windows_owner_policy_v4_transition_fixed_store",
    "receipt_schema": RECEIPT_SCHEMA,
    "semantic_contract_sha256": SEMANTIC_CONTRACT_SHA256,
    "role_handle_count": 21, "file_handle_count": 9, "watch_count": 3,
    "transition_parent_component_manifest_sha256": transition_parent.EXPECTED_COMPONENT_MANIFEST_SHA256,
    "authority_boundary": GATE_STATUS,
}
COMPONENT_MANIFEST_SHA256 = "58b7c10801e95a11c322457e3286a228435f50128336eb75dc2e143251420ae2"
EXPECTED_COMPONENT_MANIFEST_SHA256 = "58b7c10801e95a11c322457e3286a228435f50128336eb75dc2e143251420ae2"


class P0WindowsOwnerPolicyV4TransitionFixedStoreError(RuntimeError):
    """The transition observation could not fail closed."""


def canonical_bytes(value: Any) -> bytes:
    return transition_parent.canonical_bytes(value)


def canonical_sha256(value: Any) -> str:
    return transition_parent.canonical_sha256(value)


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


_DEPENDENCY_PINS = {
    "transition_parent": transition_parent.validate_windows_owner_policy_v4_transition_parent,
    "v4_child": v4_contract.validate_presented_windows_owner_policy_v4_packet_v2_profile,
    "v4_parent": v4_parent.validate_v4_epoch2_fixed_store_parent_replay,
    "v3_acl": (
        v3_contract.compare_exact_security_projection,
        _stable_code_digest(v3_contract.compare_exact_security_projection),
    ),
    "common_entry": (
        v4_store._assert_inventory_entry_matches_snapshot,
        _stable_code_digest(v4_store._assert_inventory_entry_matches_snapshot),
    ),
    "open_handle": fixed._open_handle, "query_snapshot": fixed._query_snapshot,
    "enumerate_directory": fixed._enumerate_directory,
    "read_exact": fixed._read_handle_exact,
    "observe_acl": acl.observe_windows_binary_acl_projection,
    "known_folder_api": v3_store._KnownFolderApi,
    "handle_flags_api": v3_store._HandleFlagsApi,
    "fixed_win32": fixed._Win32,
    "program_data_path": v3_store._program_data_path,
    "v3_role_paths": v3_store._role_paths,
    "v3_non_inheritable": v3_store._assert_non_inheritable,
    "v3_inventory": v3_store._validate_exact_inventory,
    "v4_paths": v4_store._paths,
    "v4_open_role": v4_store._open_role_handle,
    "v4_inventory": v4_store._validate_inventory,
    "assert_directory": fixed._assert_directory,
    "assert_regular": fixed._assert_regular_single_link,
    "snapshot_stable": fixed._snapshot_stable,
    "ancestor_projection": fixed._ancestor_namespace_projection,
    "inventory_projection": fixed._inventory_projection,
    "lexical_ancestors": fixed._lexical_ancestor_paths,
    "watch_start": inspect.getattr_static(watch_module.WindowsDirectoryChangeWatch, "start"),
    "watch_barrier": inspect.getattr_static(watch_module.WindowsDirectoryChangeWatch, "barrier"),
    "watch_finalize": inspect.getattr_static(watch_module.WindowsDirectoryChangeWatch, "finalize"),
    "path_join": os.path.join,
    "path_isabs": os.path.isabs,
    "path_basename": os.path.basename,
    "path_dirname": os.path.dirname,
}
_EXTERNAL_CODE_PINS = tuple(
    (
        label, value,
        _stable_code_digest(value),
        value.__defaults__,
        dict(value.__kwdefaults__) if value.__kwdefaults__ is not None else None,
    )
    for label, value in (
        ("transition_parent", transition_parent.validate_windows_owner_policy_v4_transition_parent),
        ("v4_child", v4_contract.validate_presented_windows_owner_policy_v4_packet_v2_profile),
        ("v4_parent", v4_parent.validate_v4_epoch2_fixed_store_parent_replay),
        ("v3_acl", v3_contract.compare_exact_security_projection),
        ("common_entry", v4_store._assert_inventory_entry_matches_snapshot),
        ("open_handle", fixed._open_handle), ("query_snapshot", fixed._query_snapshot),
        ("enumerate_directory", fixed._enumerate_directory),
        ("read_exact", fixed._read_handle_exact),
        ("observe_acl", acl.observe_windows_binary_acl_projection),
        ("program_data_path", v3_store._program_data_path),
        ("v3_role_paths", v3_store._role_paths),
        ("v3_non_inheritable", v3_store._assert_non_inheritable),
        ("v3_inventory", v3_store._validate_exact_inventory),
        ("v4_paths", v4_store._paths),
        ("v4_open_role", v4_store._open_role_handle),
        ("v4_inventory", v4_store._validate_inventory),
        ("assert_directory", fixed._assert_directory),
        ("assert_regular", fixed._assert_regular_single_link),
        ("snapshot_stable", fixed._snapshot_stable),
        ("ancestor_projection", fixed._ancestor_namespace_projection),
        ("inventory_projection", fixed._inventory_projection),
        ("lexical_ancestors", fixed._lexical_ancestor_paths),
        ("path_join", os.path.join), ("path_isabs", os.path.isabs),
        ("path_basename", os.path.basename), ("path_dirname", os.path.dirname),
    )
)
_CLASS_DESCRIPTOR_PINS = tuple(
    (
        label,
        value,
        tuple(value.__dict__),
        inspect.getattr_static(value, "__init__"),
        _stable_code_digest(inspect.getattr_static(value, "__init__")),
        inspect.getattr_static(value, "__init__").__defaults__,
        (
            dict(inspect.getattr_static(value, "__init__").__kwdefaults__)
            if inspect.getattr_static(value, "__init__").__kwdefaults__ is not None
            else None
        ),
    )
    for label, value in (
        ("known_folder_api", v3_store._KnownFolderApi),
        ("handle_flags_api", v3_store._HandleFlagsApi),
        ("fixed_win32", fixed._Win32),
    )
)
_FIXED_PRIMITIVE_CONSTANT_PINS = tuple(
    (name, type(value), value)
    for name, value in vars(fixed).items()
    if (
        name.startswith("_")
        and name[1:].isupper()
        and type(value) in (bool, int, str, bytes, tuple, frozenset)
    )
)
_V3_DIRECTORY_INVENTORIES_REPR_SHA256 = hashlib.sha256(
    repr(v3_store._DIRECTORY_INVENTORIES).encode("utf-8")
).hexdigest()
_V4_DIRECTORY_INVENTORIES_REPR_SHA256 = hashlib.sha256(
    repr(v4_store._DIRECTORY_INVENTORIES).encode("utf-8")
).hexdigest()
_V3_FIXED_SUFFIX_PIN = v3_contract.FIXED_POLICY_STORE_SUFFIX
_V4_FIXED_SUFFIX_PIN = v4_store.FIXED_STORE_SUFFIX
_V4_WATCH_FILTER_PIN = v4_store._WATCH_FILTER
_HASHLIB_SHA256_PIN = hashlib.sha256
_STABLE_CODE_DIGEST_PIN = _stable_code_digest
_STABLE_CODE_OBJECT_PIN = _stable_code_digest.__code__


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
        or transition_parent.validate_windows_owner_policy_v4_transition_parent is not _DEPENDENCY_PINS["transition_parent"]
        or v4_contract.validate_presented_windows_owner_policy_v4_packet_v2_profile is not _DEPENDENCY_PINS["v4_child"]
        or v4_parent.validate_v4_epoch2_fixed_store_parent_replay is not _DEPENDENCY_PINS["v4_parent"]
        or v3_contract.compare_exact_security_projection is not _DEPENDENCY_PINS["v3_acl"][0]
        or _stable_code_digest(v3_contract.compare_exact_security_projection) != _DEPENDENCY_PINS["v3_acl"][1]
        or v4_store._assert_inventory_entry_matches_snapshot is not _DEPENDENCY_PINS["common_entry"][0]
        or _stable_code_digest(v4_store._assert_inventory_entry_matches_snapshot) != _DEPENDENCY_PINS["common_entry"][1]
        or fixed._open_handle is not _DEPENDENCY_PINS["open_handle"]
        or fixed._query_snapshot is not _DEPENDENCY_PINS["query_snapshot"]
        or fixed._enumerate_directory is not _DEPENDENCY_PINS["enumerate_directory"]
        or fixed._read_handle_exact is not _DEPENDENCY_PINS["read_exact"]
        or acl.observe_windows_binary_acl_projection is not _DEPENDENCY_PINS["observe_acl"]
        or v3_store._KnownFolderApi is not _DEPENDENCY_PINS["known_folder_api"]
        or v3_store._HandleFlagsApi is not _DEPENDENCY_PINS["handle_flags_api"]
        or fixed._Win32 is not _DEPENDENCY_PINS["fixed_win32"]
        or v3_store._program_data_path is not _DEPENDENCY_PINS["program_data_path"]
        or v3_store._role_paths is not _DEPENDENCY_PINS["v3_role_paths"]
        or v3_store._assert_non_inheritable is not _DEPENDENCY_PINS["v3_non_inheritable"]
        or v3_store._validate_exact_inventory is not _DEPENDENCY_PINS["v3_inventory"]
        or v4_store._paths is not _DEPENDENCY_PINS["v4_paths"]
        or v4_store._open_role_handle is not _DEPENDENCY_PINS["v4_open_role"]
        or v4_store._validate_inventory is not _DEPENDENCY_PINS["v4_inventory"]
        or fixed._assert_directory is not _DEPENDENCY_PINS["assert_directory"]
        or fixed._assert_regular_single_link is not _DEPENDENCY_PINS["assert_regular"]
        or fixed._snapshot_stable is not _DEPENDENCY_PINS["snapshot_stable"]
        or fixed._ancestor_namespace_projection is not _DEPENDENCY_PINS["ancestor_projection"]
        or fixed._inventory_projection is not _DEPENDENCY_PINS["inventory_projection"]
        or fixed._lexical_ancestor_paths is not _DEPENDENCY_PINS["lexical_ancestors"]
        or hashlib.sha256(repr(v3_store._DIRECTORY_INVENTORIES).encode("utf-8")).hexdigest()
        != _V3_DIRECTORY_INVENTORIES_REPR_SHA256
        or hashlib.sha256(repr(v4_store._DIRECTORY_INVENTORIES).encode("utf-8")).hexdigest()
        != _V4_DIRECTORY_INVENTORIES_REPR_SHA256
        or v3_contract.FIXED_POLICY_STORE_SUFFIX != _V3_FIXED_SUFFIX_PIN
        or v4_store.FIXED_STORE_SUFFIX != _V4_FIXED_SUFFIX_PIN
        or v4_store._WATCH_FILTER != _V4_WATCH_FILTER_PIN
        or inspect.getattr_static(watch_module.WindowsDirectoryChangeWatch, "start") is not _DEPENDENCY_PINS["watch_start"]
        or inspect.getattr_static(watch_module.WindowsDirectoryChangeWatch, "barrier") is not _DEPENDENCY_PINS["watch_barrier"]
        or inspect.getattr_static(watch_module.WindowsDirectoryChangeWatch, "finalize") is not _DEPENDENCY_PINS["watch_finalize"]
        or os.path.join is not _DEPENDENCY_PINS["path_join"]
        or os.path.isabs is not _DEPENDENCY_PINS["path_isabs"]
        or os.path.basename is not _DEPENDENCY_PINS["path_basename"]
        or os.path.dirname is not _DEPENDENCY_PINS["path_dirname"]
    ):
        raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
            "transition fixed-store component/dependency integrity drift"
        )
    transition_parent._assert_integrity()
    v4_store._assert_component_and_dependency_integrity()
    for label, live, code_sha, defaults, kwdefaults in _EXTERNAL_CODE_PINS:
        if (
            _stable_code_digest(live) != code_sha
            or live.__defaults__ != defaults
            or live.__kwdefaults__ != kwdefaults
        ):
            raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
                f"transition fixed-store dependency code drift: {label}"
            )
    for label, live_class, class_fields, init, code_sha, defaults, kwdefaults in _CLASS_DESCRIPTOR_PINS:
        live_init = inspect.getattr_static(live_class, "__init__")
        if (
            tuple(live_class.__dict__) != class_fields
            or live_init is not init
            or _stable_code_digest(live_init) != code_sha
            or live_init.__defaults__ != defaults
            or live_init.__kwdefaults__ != kwdefaults
        ):
            raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
                f"transition fixed-store class descriptor drift: {label}"
            )
    for name, expected_type, expected_value in _FIXED_PRIMITIVE_CONSTANT_PINS:
        live = getattr(fixed, name, None)
        if type(live) is not expected_type or live != expected_value:
            raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
                f"transition fixed-store Win32 constant drift: {name}"
            )
    pins = globals().get("_SELF_HELPER_PINS")
    if pins is not None:
        for name, expected, code_sha, defaults, kwdefaults in pins:
            live = globals().get(name)
            if (
                live is not expected
                or _callable_code_sha256(live) != code_sha
                or getattr(live, "__defaults__", None) != defaults
                or getattr(live, "__kwdefaults__", None) != kwdefaults
            ):
                raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
                    f"transition fixed-store private helper drift: {name}"
                )


_ASSERT_INTEGRITY_FUNCTION_PIN = _assert_integrity
_ASSERT_INTEGRITY_CODE_OBJECT_PIN = _assert_integrity.__code__


def _all_paths(program_data: str) -> tuple[dict[str, str], dict[str, str]]:
    return v3_store._role_paths(program_data), v4_store._paths(program_data)


def _role_path(role: str, v3_paths: Mapping[str, str], v4_paths: Mapping[str, str]) -> str:
    prefix, name = role.split(":", 1)
    return (v3_paths if prefix == "v3" else v4_paths)[name]


def _open_role(stack: ExitStack, api: Any, flags_api: Any, role: str, path: str) -> tuple[Any, Any]:
    directory = role in DIRECTORY_ROLE_SEQUENCE
    if role.startswith("v4:"):
        handle = stack.enter_context(v4_store._open_role_handle(api, path, directory=directory))
    else:
        handle = stack.enter_context(
            fixed._open_handle(api, path, directory=directory, read_data=not directory)
        )
    v3_store._assert_non_inheritable(flags_api, handle.value, role)
    snapshot = fixed._query_snapshot(api, handle.value, include_streams=not directory)
    if directory:
        fixed._assert_directory(snapshot, role)
    else:
        fixed._assert_regular_single_link(snapshot, role)
    return handle, snapshot


def _inventory_projection(api: Any, held: Mapping[str, tuple[Any, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, expected in v3_store._DIRECTORY_INVENTORIES.items():
        role = f"v3:{name}"
        value = fixed._enumerate_directory(api, held[role][0].value)
        v3_store._validate_exact_inventory(value, expected, role)
        result[role] = fixed._inventory_projection(value)
    for name, expected in v4_store._DIRECTORY_INVENTORIES.items():
        role = f"v4:{name}"
        value = fixed._enumerate_directory(api, held[role][0].value)
        v4_store._validate_inventory(value, expected, role)
        result[role] = fixed._inventory_projection(value)
    return result


def _watch_clean(outcome: Any) -> bool:
    return bool(
        outcome.project_source_directory_change_watch_observation_verified
        and not outcome.directory_change_notification_delivered_observed
        and not outcome.overflow_observed
        and not outcome.observation_gap_observed
        and outcome.pending_request_until_interval_end_observed
        and outcome.completion_drained_observed
        and outcome.watch_handles_non_inheritable_verified
        and outcome.watch_handles_closed_observed
    )


def _observe_held(
    *, program_data: str, watches: list[Any], v3_paths: Mapping[str, str],
    v4_paths: Mapping[str, str],
) -> dict[str, Any]:
    _assert_integrity()
    api = fixed._Win32()
    flags_api = v3_store._HandleFlagsApi()
    common_path = os.path.join(program_data, v3_contract.FIXED_POLICY_STORE_SUFFIX[0])
    normalized, ancestor_paths = fixed._lexical_ancestor_paths(common_path)
    if normalized != common_path:
        raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
            "common parent lexical normalization mismatch"
        )
    with ExitStack() as stack:
        ancestors: list[tuple[str, Any, Any]] = []
        for index, path in enumerate(ancestor_paths):
            handle = stack.enter_context(fixed._open_handle(api, path, directory=True, read_data=False))
            v3_store._assert_non_inheritable(flags_api, handle.value, f"ancestor:{index}")
            snapshot = fixed._query_snapshot(api, handle.value, include_streams=False)
            fixed._assert_directory(snapshot, f"ancestor:{index}")
            ancestors.append((path, handle, snapshot))
        common = stack.enter_context(fixed._open_handle(api, common_path, directory=True, read_data=False))
        v3_store._assert_non_inheritable(flags_api, common.value, "common_parent")
        common_snapshot = fixed._query_snapshot(api, common.value, include_streams=False)
        fixed._assert_directory(common_snapshot, "common_parent")

        held: dict[str, tuple[Any, Any]] = {}
        for role in ROLE_SEQUENCE:
            held[role] = _open_role(
                stack, api, flags_api, role, _role_path(role, v3_paths, v4_paths)
            )
        if len(held) != 21:
            raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
                "exactly twenty-one role handles are required"
            )
        identities = [
            (snapshot.volume_serial, snapshot.file_id)
            for _handle, snapshot in held.values()
        ]
        if len(set(identities)) != 21 or len({value[0] for value in identities}) != 1:
            raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
                "transition roles must be unique objects on one volume"
            )
        expected_watch = (
            common_snapshot, held["v3:policy_store"][1], held["v4:policy_store"][1]
        )
        for watch, expected in zip(watches, expected_watch, strict=True):
            if (
                watch.identity.final_path != expected.final_path
                or watch.identity.volume_serial != expected.volume_serial
                or watch.identity.file_id != expected.file_id
            ):
                raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
                    "watch/held-handle identity mismatch"
                )
        common_inventory = fixed._enumerate_directory(api, common.value)
        required_common = {
            v3_contract.FIXED_POLICY_STORE_SUFFIX[-1]: held["v3:policy_store"][1],
            v4_store.FIXED_STORE_SUFFIX[-1]: held["v4:policy_store"][1],
        }
        if any(name not in common_inventory for name in required_common):
            raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
                "common parent is missing a required policy store"
            )
        for name, snapshot in required_common.items():
            v4_store._assert_inventory_entry_matches_snapshot(
                common_inventory[name], snapshot, directory=True, label=name
            )
        inventory_before = _inventory_projection(api, held)
        sizes = {role: held[role][1].standard[1] for role in FILE_ROLE_SEQUENCE}
        if (
            any(type(size) is not int or not 0 <= size <= _CAPS[role] for role, size in sizes.items())
            or sum(sizes.values()) > AGGREGATE_CAP_BYTES
        ):
            raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
                "transition member size cap exceeded before first read"
            )
        raws: dict[str, bytes] = {}
        for role in FILE_ROLE_SEQUENCE:
            handle, before = held[role]
            raw = fixed._read_handle_exact(api, handle.value, sizes[role], role)
            after = fixed._query_snapshot(api, handle.value, include_streams=True)
            if not fixed._snapshot_stable(before, after):
                raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
                    f"member changed during read: {role}"
                )
            raws[role] = raw
        if not hmac.compare_digest(raws["v3:policy_body_file"], raws["v4:predecessor_policy_v3_body"]):
            raise P0WindowsOwnerPolicyV4TransitionFixedStoreError("live/embedded V3 body mismatch")
        if not hmac.compare_digest(raws["v3:policy_signature_file"], raws["v4:predecessor_policy_v3_signature"]):
            raise P0WindowsOwnerPolicyV4TransitionFixedStoreError("live/embedded V3 signature mismatch")

        # Every validation and cross-check runs while all handles remain live.
        v4_raws = {
            role: raws[f"v4:{role}"] for role in v4_parent.RAW_ROLES
        }
        v4_child = v4_contract.validate_presented_windows_owner_policy_v4_packet_v2_profile(
            predecessor_policy_v3_body_bytes=v4_raws["predecessor_policy_v3_body"],
            predecessor_policy_v3_signature_bytes=v4_raws["predecessor_policy_v3_signature"],
            packet_v2_public_key_pin_bytes=v4_raws["packet_v2_public_key_pin"],
            policy_v4_body_bytes=v4_raws["policy_v4_body"],
            policy_v4_signature_bytes=v4_raws["policy_v4_signature"],
            bootstrap_public_key_spki_der=v4_raws["bootstrap_public_key_spki"],
        )
        parent_receipt = v4_parent.validate_v4_epoch2_fixed_store_parent_replay(
            raw_bundle=v4_raws, child_receipt=v4_child
        )
        transition_raws = {
            "live_v3_policy_body": raws["v3:policy_body_file"],
            "live_v3_policy_signature": raws["v3:policy_signature_file"],
            "live_v3_operational_pin": raws["v3:public_key_pin_file"],
            **v4_raws,
        }
        transition_receipt = transition_parent.validate_windows_owner_policy_v4_transition_parent(
            raw_bundle=transition_raws, v4_child_receipt=v4_child,
            v4_parent_receipt=parent_receipt,
        )
        _assert_integrity()
        v3_body = transition_parent._parse(
            raws["v3:policy_body_file"], "held live V3 policy body"
        )
        signed_v3_objects = {
            row["role"]: row for row in v3_body["object_policies"]
        }
        for role in v3_contract.OBJECT_ROLES:
            observed = held[f"v3:{role}"][1]
            expected = signed_v3_objects[role]
            if (
                observed.final_path != expected["final_volume_guid_path"]
                or str(observed.volume_serial) != expected["volume_serial_decimal"]
                or observed.file_id != expected["file_id_128_hex"]
            ):
                raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
                    f"signed/live V3 object identity mismatch: {role}"
                )
        acl_before: dict[str, str] = {}
        for role, (handle, _snapshot) in held.items():
            projection = acl.observe_windows_binary_acl_projection(handle=handle.value)
            if role.startswith("v3:"):
                v3_contract.compare_exact_security_projection(
                    validated_policy_body_bytes=raws["v3:policy_body_file"],
                    role=role.split(":", 1)[1], observed_security_projection=projection,
                )
            acl_before[role] = canonical_sha256(projection)
        if inventory_before != _inventory_projection(api, held):
            raise P0WindowsOwnerPolicyV4TransitionFixedStoreError("directory inventory changed")
        for role, (handle, before) in held.items():
            after = fixed._query_snapshot(api, handle.value, include_streams=role in FILE_ROLE_SEQUENCE)
            if not fixed._snapshot_stable(before, after):
                raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(f"role changed: {role}")
            if canonical_sha256(acl.observe_windows_binary_acl_projection(handle=handle.value)) != acl_before[role]:
                raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(f"ACL changed: {role}")
            directory = role in DIRECTORY_ROLE_SEQUENCE
            path = _role_path(role, v3_paths, v4_paths)
            with fixed._open_handle(api, path, directory=directory, read_data=False) as reopened:
                v3_store._assert_non_inheritable(flags_api, reopened.value, f"reopen:{role}")
                reopened_snapshot = fixed._query_snapshot(api, reopened.value, include_streams=not directory)
                if not fixed._snapshot_stable(after, reopened_snapshot):
                    raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(f"reopen mismatch: {role}")
        for index, (path, handle, before) in enumerate(ancestors):
            after = fixed._query_snapshot(api, handle.value, include_streams=False)
            if fixed._ancestor_namespace_projection(before) != fixed._ancestor_namespace_projection(after):
                raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
                    f"ancestor changed: {index}"
                )
            with fixed._open_handle(api, path, directory=True, read_data=False) as reopened:
                reopened_snapshot = fixed._query_snapshot(api, reopened.value, include_streams=False)
                if fixed._ancestor_namespace_projection(after) != fixed._ancestor_namespace_projection(reopened_snapshot):
                    raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
                        f"ancestor reopen mismatch: {index}"
                    )
        barriers = [watch.barrier() for watch in watches]
        if any(not barrier.observation_acceptable for barrier in barriers):
            raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
                "watch completed before interval end"
            )
        armed = [watch._armed_counter_ns for watch in watches]
        ended = [barrier.counter_ns for barrier in barriers]
        if not max(armed) < min(ended):
            raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
                "three watch intervals do not intersect"
            )
        return {
            "role_handle_count": 21,
            "file_handle_count": 9,
            "ancestor_handle_count": len(ancestors) + 1,
            "total_member_bytes": sum(len(value) for value in raws.values()),
            "raw_sha256_by_role": {role: hashlib.sha256(raws[role]).hexdigest() for role in FILE_ROLE_SEQUENCE},
            "role_identity_projection_sha256": canonical_sha256({
                role: [snapshot.final_path, str(snapshot.volume_serial), snapshot.file_id]
                for role, (_handle, snapshot) in held.items()
            }),
            "inventory_projection_sha256": canonical_sha256(inventory_before),
            "binary_acl_projection_set_sha256": canonical_sha256(acl_before),
            "v3_contract_receipt_declared_sha256": transition_receipt[
                "predecessor_contract_receipt_sha256"
            ],
            "v4_child_receipt_declared_sha256": v4_child["receipt_sha256"],
            "v4_parent_receipt_declared_sha256": parent_receipt["receipt_sha256"],
            "transition_parent_receipt": transition_receipt,
            "transition_parent_receipt_declared_sha256": transition_receipt["receipt_sha256"],
            "transition_parent_receipt_full_canonical_sha256": canonical_sha256(transition_receipt),
        }


def _watch_projection(outcome: Any) -> dict[str, Any]:
    return {
        "requested_path": outcome.requested_path,
        "final_path": outcome.identity.final_path,
        "volume_serial_decimal": str(outcome.identity.volume_serial),
        "file_id_128_hex": outcome.identity.file_id,
        "notify_filter": outcome.notify_filter,
        "completion_status": outcome.completion_status,
        "clean": _watch_clean(outcome),
    }


def _observe_at_program_data(program_data: str) -> dict[str, Any]:
    _assert_integrity()
    v3_paths, v4_paths = _all_paths(program_data)
    common_path = os.path.join(program_data, v3_contract.FIXED_POLICY_STORE_SUFFIX[0])
    watch_paths = (common_path, v3_paths["policy_store"], v4_paths["policy_store"])
    watches: list[Any] = []
    outcomes: list[Any] = []
    evidence: dict[str, Any] | None = None
    primary: BaseException | None = None
    try:
        for path in watch_paths:
            watches.append(watch_module.WindowsDirectoryChangeWatch.start(
                path, watch_subtree=True, notify_filter=v4_store._WATCH_FILTER
            ))
        evidence = _observe_held(
            program_data=program_data, watches=watches,
            v3_paths=v3_paths, v4_paths=v4_paths,
        )
    except BaseException as exc:
        primary = exc
    finally:
        for watch in reversed(watches):
            try:
                outcomes.append(watch.finalize())
            except BaseException as exc:
                if primary is None:
                    primary = exc
    if primary is not None:
        if isinstance(primary, (KeyboardInterrupt, SystemExit)):
            raise primary
        raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
            "transition held interval failed closed"
        ) from primary
    assert evidence is not None
    outcomes.reverse()
    if len(outcomes) != 3 or any(not _watch_clean(outcome) for outcome in outcomes):
        raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
            "three-watch interval did not finalize cleanly"
        )
    material: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA, "gate_status": GATE_STATUS,
        "decision": "NO_GO", "failure_stage": "EXTERNAL_STATE",
        "blocker_codes": list(_BLOCKERS[9:]), "role_sequence": list(ROLE_SEQUENCE),
        "file_role_sequence": list(FILE_ROLE_SEQUENCE),
        "watch_scope_sequence": list(WATCH_SCOPE_SEQUENCE),
        **evidence,
        "directory_change_watches": [_watch_projection(outcome) for outcome in outcomes],
        **{field: True for field in _TRUE_FIELDS},
        **{field: False for field in _FALSE_FIELDS},
        "credited_actual_source_claim_count": 0,
        "credited_actual_a_context_review_count": 0,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    return {**material, "receipt_sha256": canonical_sha256(material)}


def _failure_receipt(stage: str) -> dict[str, Any]:
    material: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA, "gate_status": GATE_STATUS,
        "decision": "NO_GO", "failure_stage": stage,
        "blocker_codes": list(_BLOCKERS), "role_sequence": list(ROLE_SEQUENCE),
        "file_role_sequence": list(FILE_ROLE_SEQUENCE),
        "watch_scope_sequence": list(WATCH_SCOPE_SEQUENCE),
        "role_handle_count": 0, "file_handle_count": 0, "ancestor_handle_count": 0,
        "total_member_bytes": 0, "raw_sha256_by_role": {},
        "role_identity_projection_sha256": "", "inventory_projection_sha256": "",
        "binary_acl_projection_set_sha256": "",
        "v3_contract_receipt_declared_sha256": "",
        "v4_child_receipt_declared_sha256": "",
        "v4_parent_receipt_declared_sha256": "",
        "transition_parent_receipt": {},
        "transition_parent_receipt_declared_sha256": "",
        "transition_parent_receipt_full_canonical_sha256": "",
        "directory_change_watches": [],
        **{field: False for field in _TRUE_FIELDS},
        **{field: False for field in _FALSE_FIELDS},
        "credited_actual_source_claim_count": 0,
        "credited_actual_a_context_review_count": 0,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    return {**material, "receipt_sha256": canonical_sha256(material)}


def _watch_rows_strict(value: Any) -> bool:
    if type(value) is not list or len(value) != 3:
        return False
    try:
        program_data = v3_store._program_data_path(v3_store._KnownFolderApi())
        expected_v3, expected_v4 = _all_paths(program_data)
        expected_requested_paths = (
            os.path.join(program_data, v3_contract.FIXED_POLICY_STORE_SUFFIX[0]),
            expected_v3["policy_store"],
            expected_v4["policy_store"],
        )
    except Exception:
        return False
    expected_leaf_names = (
        v3_contract.FIXED_POLICY_STORE_SUFFIX[0],
        v3_contract.FIXED_POLICY_STORE_SUFFIX[-1],
        v4_store.FIXED_STORE_SUFFIX[-1],
    )
    for row, leaf_name, requested_path in zip(
        value, expected_leaf_names, expected_requested_paths, strict=True
    ):
        if (
            type(row) is not dict
            or tuple(row) != (
                "requested_path", "final_path", "volume_serial_decimal",
                "file_id_128_hex", "notify_filter", "completion_status", "clean",
            )
            or type(row.get("requested_path")) is not str
            or not os.path.isabs(row["requested_path"])
            or row["requested_path"].casefold() != requested_path.casefold()
            or os.path.basename(row["requested_path"]) != leaf_name
            or type(row.get("final_path")) is not str
            or not row["final_path"].startswith("\\\\?\\Volume{")
            or os.path.basename(row["final_path"].rstrip("\\/")) != leaf_name
            or type(row.get("volume_serial_decimal")) is not str
            or not row["volume_serial_decimal"].isdigit()
            or type(row.get("file_id_128_hex")) is not str
            or len(row["file_id_128_hex"]) != 32
            or any(character not in "0123456789abcdef" for character in row["file_id_128_hex"])
            or type(row.get("notify_filter")) is not int
            or row["notify_filter"] != _V4_WATCH_FILTER_PIN
            or row.get("completion_status") != "CANCELED_PENDING_AT_END"
            or row.get("clean") is not True
        ):
            return False
    if (
        os.path.dirname(value[1]["requested_path"]).casefold()
        != value[0]["requested_path"].casefold()
        or os.path.dirname(value[2]["requested_path"]).casefold()
        != value[0]["requested_path"].casefold()
        or len({row["requested_path"].casefold() for row in value}) != 3
        or os.path.dirname(value[1]["final_path"]).casefold()
        != value[0]["final_path"].casefold()
        or os.path.dirname(value[2]["final_path"]).casefold()
        != value[0]["final_path"].casefold()
        or len({
            (row["final_path"].casefold(), row["volume_serial_decimal"], row["file_id_128_hex"])
            for row in value
        }) != 3
    ):
        return False
    return True


def _validate_receipt(receipt: Any) -> dict[str, Any]:
    if (
        type(receipt) is not dict
        or tuple(receipt) != _RECEIPT_FIELDS
        or receipt.get("schema_version") != RECEIPT_SCHEMA
        or receipt.get("gate_status") != GATE_STATUS
        or receipt.get("decision") != "NO_GO"
        or receipt.get("operational_effect") != OPERATIONAL_EFFECT
        or receipt.get("role_sequence") != list(ROLE_SEQUENCE)
        or receipt.get("file_role_sequence") != list(FILE_ROLE_SEQUENCE)
        or receipt.get("watch_scope_sequence") != list(WATCH_SCOPE_SEQUENCE)
        or receipt.get("failure_stage") not in {"FIXED_STORE", "EXTERNAL_STATE"}
        or any(receipt.get(field) is not False for field in _FALSE_FIELDS)
        or type(receipt.get("credited_actual_source_claim_count")) is not int
        or receipt.get("credited_actual_source_claim_count") != 0
        or type(receipt.get("credited_actual_a_context_review_count")) is not int
        or receipt.get("credited_actual_a_context_review_count") != 0
    ):
        raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
            "transition receipt exact schema/type mismatch"
        )
    succeeded = receipt["failure_stage"] == "EXTERNAL_STATE"
    if any(receipt[field] is not succeeded for field in _TRUE_FIELDS):
        raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
            "transition receipt truth table mismatch"
        )
    expected_blockers = list(_BLOCKERS[9:] if succeeded else _BLOCKERS)
    if receipt["blocker_codes"] != expected_blockers:
        raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
            "transition receipt blocker order mismatch"
        )
    def lower_sha(value: Any) -> bool:
        return type(value) is str and len(value) == 64 and all(
            character in "0123456789abcdef" for character in value
        )
    if succeeded:
        nested = receipt["transition_parent_receipt"]
        if (
            type(receipt["role_handle_count"]) is not int
            or receipt["role_handle_count"] != 21
            or type(receipt["file_handle_count"]) is not int
            or receipt["file_handle_count"] != 9
            or type(receipt["ancestor_handle_count"]) is not int
            or receipt["ancestor_handle_count"] <= 0
            or type(receipt["total_member_bytes"]) is not int
            or receipt["total_member_bytes"] <= 0
            or type(receipt["raw_sha256_by_role"]) is not dict
            or tuple(receipt["raw_sha256_by_role"]) != FILE_ROLE_SEQUENCE
            or any(not lower_sha(value) for value in receipt["raw_sha256_by_role"].values())
            or any(not lower_sha(receipt[field]) for field in (
                "role_identity_projection_sha256", "inventory_projection_sha256",
                "binary_acl_projection_set_sha256", "v3_contract_receipt_declared_sha256",
                "v4_child_receipt_declared_sha256", "v4_parent_receipt_declared_sha256",
                "transition_parent_receipt_declared_sha256",
                "transition_parent_receipt_full_canonical_sha256",
            ))
            or not _watch_rows_strict(receipt["directory_change_watches"])
            or type(nested) is not dict
            or tuple(nested) != transition_parent._RECEIPT_FIELDS
            or nested.get("schema_version") != transition_parent.RECEIPT_SCHEMA
            or nested.get("gate_status") != transition_parent.GATE_STATUS
            or nested.get("decision") != "NO_GO"
            or nested.get("operational_effect") != transition_parent.OPERATIONAL_EFFECT
            or nested.get("raw_role_sequence") != list(transition_parent.TRANSITION_RAW_ROLES)
            or type(nested.get("raw_sha256_by_role")) is not dict
            or tuple(nested.get("raw_sha256_by_role", {}))
            != transition_parent.TRANSITION_RAW_ROLES
            or any(not lower_sha(value) for value in nested.get("raw_sha256_by_role", {}).values())
            or nested.get("raw_bundle_projection_sha256")
            != canonical_sha256(nested.get("raw_sha256_by_role"))
            or type(nested.get("policy_id")) is not str
            or not nested.get("policy_id")
            or type(nested.get("predecessor_policy_epoch")) is not int
            or nested.get("predecessor_policy_epoch") != 1
            or type(nested.get("policy_v4_epoch")) is not int
            or nested.get("policy_v4_epoch") != 2
            or any(not lower_sha(nested.get(field)) for field in (
                "predecessor_signature_input_sha256", "predecessor_contract_receipt_sha256",
                "presented_bootstrap_spki_sha256", "v4_parent_declared_sha256",
                "v4_parent_full_canonical_sha256",
            ))
            or any(nested.get(field) is not True for field in transition_parent._TRUE_FIELDS)
            or any(nested.get(field) is not False for field in transition_parent._FALSE_FIELDS)
            or type(nested.get("credited_actual_source_claim_count")) is not int
            or nested.get("credited_actual_source_claim_count") != 0
            or type(nested.get("credited_actual_a_context_review_count")) is not int
            or nested.get("credited_actual_a_context_review_count") != 0
            or nested.get("receipt_sha256") != receipt["transition_parent_receipt_declared_sha256"]
            or canonical_sha256(nested) != receipt["transition_parent_receipt_full_canonical_sha256"]
        ):
            raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
                "transition success evidence/nested receipt mismatch"
            )
        nested_material = dict(nested)
        nested_declared = nested_material.pop("receipt_sha256")
        if not hmac.compare_digest(nested_declared, canonical_sha256(nested_material)):
            raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
                "transition nested parent self-hash mismatch"
            )
    elif (
        type(receipt["role_handle_count"]) is not int
        or receipt["role_handle_count"] != 0
        or type(receipt["file_handle_count"]) is not int
        or receipt["file_handle_count"] != 0
        or type(receipt["ancestor_handle_count"]) is not int
        or receipt["ancestor_handle_count"] != 0
        or type(receipt["total_member_bytes"]) is not int
        or receipt["total_member_bytes"] != 0
        or receipt["raw_sha256_by_role"] != {}
        or any(receipt[field] != "" for field in (
            "role_identity_projection_sha256", "inventory_projection_sha256",
            "binary_acl_projection_set_sha256", "v3_contract_receipt_declared_sha256",
            "v4_child_receipt_declared_sha256", "v4_parent_receipt_declared_sha256",
            "transition_parent_receipt_declared_sha256",
            "transition_parent_receipt_full_canonical_sha256",
        ))
        or receipt["directory_change_watches"] != []
        or receipt["transition_parent_receipt"] != {}
    ):
        raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
            "transition failure receipt carries impossible success evidence"
        )
    material = dict(receipt)
    declared = material.pop("receipt_sha256", None)
    if type(declared) is not str or not hmac.compare_digest(declared, canonical_sha256(material)):
        raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
            "transition receipt self-hash mismatch"
        )
    return receipt


def observe_fixed_windows_owner_policy_v4_transition_store() -> dict[str, Any]:
    """Observe the two compiled stores without caller-supplied selectors."""

    if (
        _assert_integrity is not _ASSERT_INTEGRITY_FUNCTION_PIN
        or _assert_integrity.__code__ is not _ASSERT_INTEGRITY_CODE_OBJECT_PIN
    ):
        raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
            "transition fixed-store integrity checker drift"
        )
    _assert_integrity()
    if os.name != "nt":
        raise P0WindowsOwnerPolicyV4TransitionFixedStoreError(
            "Windows transition observation is Windows-only"
        )
    try:
        program_data = v3_store._program_data_path(v3_store._KnownFolderApi())
        receipt = _observe_at_program_data(program_data)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        receipt = _failure_receipt("FIXED_STORE")
    _assert_integrity()
    return _validate_receipt(receipt)


def _callable_code_sha256(value: Any) -> str:
    return _stable_code_digest(value)


_SELF_HELPER_PINS = tuple(
    (
        name, value, _callable_code_sha256(value), value.__defaults__,
        dict(value.__kwdefaults__) if value.__kwdefaults__ is not None else None,
    )
    for name, value in (
        ("canonical_bytes", canonical_bytes), ("canonical_sha256", canonical_sha256),
        ("_stable_code_digest", _stable_code_digest),
        ("_all_paths", _all_paths),
        ("_role_path", _role_path), ("_open_role", _open_role),
        ("_inventory_projection", _inventory_projection), ("_watch_clean", _watch_clean),
        ("_observe_held", _observe_held), ("_watch_projection", _watch_projection),
        ("_observe_at_program_data", _observe_at_program_data),
        ("_failure_receipt", _failure_receipt), ("_watch_rows_strict", _watch_rows_strict),
        ("_validate_receipt", _validate_receipt),
        ("_assert_integrity", _assert_integrity),
        ("_callable_code_sha256", _callable_code_sha256),
        ("observe_fixed_windows_owner_policy_v4_transition_store", observe_fixed_windows_owner_policy_v4_transition_store),
    )
)


__all__ = [
    "GATE_STATUS", "OPERATIONAL_EFFECT", "P0WindowsOwnerPolicyV4TransitionFixedStoreError",
    "RECEIPT_SCHEMA", "observe_fixed_windows_owner_policy_v4_transition_store",
]
