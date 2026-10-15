"""Caller-injection-free Windows fixed owner-policy store candidate.

The public function has no inputs.  It discovers ``FOLDERID_ProgramData`` via
``SHGetKnownFolderPath`` and observes one compiled genesis layout below a
compiled lowercase suffix.  All lexical ancestors and the eight policy roles
remain held while exact inventories, bytes, object identities, binary ACLs,
and namespace reopens are checked.

This is deliberately not an authority verifier.  A compiled public-key
candidate verifies the policy signature mathematics, but that candidate is
not independently provisioned authority, the fixed name is not proof of
external provisioning, and no rollback-resistant high-watermark exists.
Every authority, P0-exit, and production field therefore remains false.
"""

from __future__ import annotations

from contextlib import ExitStack
import ctypes
from ctypes import wintypes
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any, Mapping

from . import p0_external_owner_asymmetric_signature as asymmetric
from . import p0_windows_binary_acl_projection as binary_acl
from . import p0_windows_bootstrap_policy_signature_candidate as bootstrap
from . import p0_windows_directory_change_watch as directory_watch
from . import p0_windows_fixed_directory_identity as fixed
from . import p0_windows_owner_policy_contract as policy


CANDIDATE_RECEIPT_SCHEMA = (
    "p0_windows_fixed_owner_policy_store_candidate_receipt_v1"
)
GATE_STATUS = "OWNER_POLICY_FIXED_STORE_CANDIDATE_PASS_AUTHORITY_NO_GO"
KNOWN_FOLDER_ID = "{62ab5d82-fdc1-4dc3-a9dd-070d1d495d97}"
KNOWN_FOLDER_FLAGS = 0
COMPILED_POLICY_EPOCH = 1
GENERATION_COMPONENT = f"{COMPILED_POLICY_EPOCH:020d}"
POLICY_BODY_FILENAME = "body.json"
POLICY_SIGNATURE_FILENAME = "signature.json"
PUBLIC_KEY_PIN_FILENAME = "p0_external_owner_public_key_pin_v1.json"

_IS_WINDOWS = os.name == "nt"
_FILE_ATTRIBUTE_DIRECTORY = 0x00000010
_FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
_HANDLE_FLAG_INHERIT = 0x00000001
_WATCH_FILTER = (
    directory_watch.FILE_NOTIFY_CHANGE_FILE_NAME
    | directory_watch.FILE_NOTIFY_CHANGE_DIR_NAME
    | directory_watch.FILE_NOTIFY_CHANGE_ATTRIBUTES
    | directory_watch.FILE_NOTIFY_CHANGE_SIZE
    | directory_watch.FILE_NOTIFY_CHANGE_LAST_WRITE
    | directory_watch.FILE_NOTIFY_CHANGE_CREATION
    | directory_watch.FILE_NOTIFY_CHANGE_SECURITY
)

_DIRECTORY_INVENTORIES: Mapping[str, Mapping[str, bool]] = {
    "policy_store": {"generations": True},
    "generations_directory": {GENERATION_COMPONENT: True},
    "generation_directory": {"policy": True, "pin": True},
    "policy_directory": {
        POLICY_BODY_FILENAME: False,
        POLICY_SIGNATURE_FILENAME: False,
    },
    "pin_directory": {PUBLIC_KEY_PIN_FILENAME: False},
}

_FALSE_FIELDS = (
    "serialized_receipt_authoritative",
    "execution_trace_transferable_by_receipt",
    "bootstrap_public_key_independently_pinned",
    "trusted_verifier_code_identity_verified",
    "trusted_cng_provider_provenance_verified",
    "fixed_policy_store_discovery_verified",
    "live_windows_binary_acl_verified",
    "effective_verifier_token_verified",
    "linked_elevated_token_absence_verified",
    "independent_owner_policy_state_verified",
    "external_owner_policy_provisioning_verified",
    "external_public_key_pin_provisioning_verified",
    "trusted_time_verified",
    "revocation_current_verified",
    "rollback_resistant_policy_epoch_verified",
    "rollback_resistant_key_epoch_verified",
    "durable_nonce_state_verified",
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


class P0WindowsFixedOwnerPolicyStoreCandidateError(RuntimeError):
    """The fixed-store candidate could not preserve fail-closed semantics."""


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


_FOLDERID_PROGRAM_DATA = _GUID(
    0x62AB5D82,
    0xFDC1,
    0x4DC3,
    (ctypes.c_ubyte * 8)(0xA9, 0xDD, 0x07, 0x0D, 0x1D, 0x49, 0x5D, 0x97),
)


class _KnownFolderApi:
    def __init__(self) -> None:
        if not _IS_WINDOWS:
            raise P0WindowsFixedOwnerPolicyStoreCandidateError(
                "fixed owner-policy store discovery is Windows-only"
            )
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        ole32 = ctypes.WinDLL("ole32", use_last_error=True)
        self.SHGetKnownFolderPath = shell32.SHGetKnownFolderPath
        self.SHGetKnownFolderPath.argtypes = [
            ctypes.POINTER(_GUID),
            wintypes.DWORD,
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.LPWSTR),
        ]
        self.SHGetKnownFolderPath.restype = ctypes.c_long
        self.CoTaskMemFree = ole32.CoTaskMemFree
        self.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        self.CoTaskMemFree.restype = None


class _HandleFlagsApi:
    def __init__(self) -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.GetHandleInformation = kernel32.GetHandleInformation
        self.GetHandleInformation.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.GetHandleInformation.restype = wintypes.BOOL


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


_BOOTSTRAP_RECEIPT_TRUE_FIELDS = (
    "compiled_bootstrap_key_candidate_selected",
    "signature_bootstrap_identity_matches_compiled_candidate",
    "strict_policy_contract_revalidated",
    "signature_domain_separation_material_verified",
    "exact_policy_body_bytes_hash_bound_verified",
    "canonical_low_s_signature_verified",
    "cng_public_key_import_verified",
    "bootstrap_signature_mathematics_verified",
)
_BOOTSTRAP_RECEIPT_FALSE_FIELDS = (
    "serialized_receipt_authoritative",
    "execution_trace_transferable_by_receipt",
    *bootstrap._FALSE_FIELDS,
)


def _validate_same_call_bootstrap_receipt(
    *,
    receipt: Any,
    policy_body_bytes: bytes,
    policy_signature_bytes: bytes,
    contract_receipt: Mapping[str, Any],
    body: Mapping[str, Any],
) -> None:
    if type(receipt) is not dict:
        raise P0WindowsFixedOwnerPolicyStoreCandidateError(
            "bootstrap signature verifier returned a non-dict receipt"
        )
    material = dict(receipt)
    declared = material.pop("receipt_sha256", None)
    if (
        type(declared) is not str
        or len(declared) != 64
        or not hmac.compare_digest(declared, canonical_sha256(material))
    ):
        raise P0WindowsFixedOwnerPolicyStoreCandidateError(
            "bootstrap signature receipt self-hash mismatch"
        )
    if (
        receipt.get("schema_version") != bootstrap.RECEIPT_SCHEMA
        or receipt.get("gate_status") != bootstrap.GATE_STATUS
        or receipt.get("candidate_only") is not True
        or receipt.get("signature_material_contract")
        != bootstrap.SIGNATURE_MATERIAL_CONTRACT
        or receipt.get("compiled_bootstrap_key_candidate_provenance")
        != bootstrap.COMPILED_BOOTSTRAP_KEY_CANDIDATE_PROVENANCE
        or receipt.get("algorithm") != policy.BOOTSTRAP_SIGNATURE_ALGORITHM
        or receipt.get("curve") != asymmetric.CURVE
        or receipt.get("cng_provider_name") != asymmetric.CNG_PROVIDER
    ):
        raise P0WindowsFixedOwnerPolicyStoreCandidateError(
            "bootstrap signature receipt contract mismatch"
        )
    if any(
        receipt.get(field) is not True
        for field in _BOOTSTRAP_RECEIPT_TRUE_FIELDS
    ):
        raise P0WindowsFixedOwnerPolicyStoreCandidateError(
            "bootstrap signature receipt success proof is incomplete"
        )
    if any(
        receipt.get(field) is not False
        for field in _BOOTSTRAP_RECEIPT_FALSE_FIELDS
    ):
        raise P0WindowsFixedOwnerPolicyStoreCandidateError(
            "bootstrap signature receipt authority truth table mismatch"
        )
    if (
        receipt.get("policy_body_bytes_sha256")
        != hashlib.sha256(policy_body_bytes).hexdigest()
        or receipt.get("policy_signature_bytes_sha256")
        != hashlib.sha256(policy_signature_bytes).hexdigest()
        or receipt.get("owner_policy_contract_receipt")
        != contract_receipt
        or receipt.get("owner_policy_contract_receipt_declared_sha256")
        != contract_receipt.get("receipt_sha256")
        or receipt.get("compiled_bootstrap_key_id")
        != body.get("bootstrap_key_id")
        or receipt.get("compiled_bootstrap_public_key_fingerprint_sha256")
        != body.get("bootstrap_public_key_fingerprint_sha256")
    ):
        raise P0WindowsFixedOwnerPolicyStoreCandidateError(
            "bootstrap signature receipt/raw-byte binding mismatch"
        )


def _program_data_path(api: _KnownFolderApi) -> str:
    allocated = wintypes.LPWSTR()
    result: str | None = None
    primary_error: BaseException | None = None
    try:
        status = api.SHGetKnownFolderPath(
            ctypes.byref(_FOLDERID_PROGRAM_DATA),
            KNOWN_FOLDER_FLAGS,
            None,
            ctypes.byref(allocated),
        )
        if status != 0:
            raise P0WindowsFixedOwnerPolicyStoreCandidateError(
                "SHGetKnownFolderPath(ProgramData) failed with HRESULT "
                f"0x{status & 0xffffffff:08x}"
            )
        result = allocated.value
        if not result:
            raise P0WindowsFixedOwnerPolicyStoreCandidateError(
                "SHGetKnownFolderPath(ProgramData) returned no path"
            )
    except BaseException as exc:
        primary_error = exc
    finally:
        pointer = ctypes.cast(allocated, ctypes.c_void_p).value
        if pointer:
            try:
                api.CoTaskMemFree(ctypes.c_void_p(pointer))
            except BaseException as cleanup_error:
                if primary_error is None:
                    primary_error = P0WindowsFixedOwnerPolicyStoreCandidateError(
                        "CoTaskMemFree(ProgramData) failed"
                    )
                    primary_error.__cause__ = cleanup_error
    if primary_error is not None:
        raise primary_error
    assert result is not None
    try:
        root_path, _ancestors = fixed._lexical_ancestor_paths(result)
    except fixed.P0WindowsFixedDirectoryError as exc:
        raise P0WindowsFixedOwnerPolicyStoreCandidateError(
            "ProgramData known-folder path is not one strict local path"
        ) from exc
    if root_path != os.path.abspath(result):
        raise P0WindowsFixedOwnerPolicyStoreCandidateError(
            "ProgramData known-folder path is not lexically canonical"
        )
    return root_path


def _role_paths(program_data_path: str) -> dict[str, str]:
    store = os.path.join(program_data_path, *policy.FIXED_POLICY_STORE_SUFFIX)
    generations = os.path.join(store, "generations")
    generation = os.path.join(generations, GENERATION_COMPONENT)
    policy_directory = os.path.join(generation, "policy")
    pin_directory = os.path.join(generation, "pin")
    return {
        "policy_store": store,
        "generations_directory": generations,
        "generation_directory": generation,
        "policy_directory": policy_directory,
        "pin_directory": pin_directory,
        "policy_body_file": os.path.join(
            policy_directory, POLICY_BODY_FILENAME
        ),
        "policy_signature_file": os.path.join(
            policy_directory, POLICY_SIGNATURE_FILENAME
        ),
        "public_key_pin_file": os.path.join(
            pin_directory, PUBLIC_KEY_PIN_FILENAME
        ),
    }


def _identity_projection(snapshot: Any) -> dict[str, str]:
    return {
        "final_path": snapshot.final_path,
        "volume_serial_decimal": str(snapshot.volume_serial),
        "file_id_128_hex": snapshot.file_id,
    }


def _snapshot_exact_stable(before: Any, after: Any) -> bool:
    return (
        before.final_path == after.final_path
        and fixed._snapshot_stable(before, after)
    )


def _validate_exact_inventory(
    inventory: Mapping[str, Any], expected: Mapping[str, bool], label: str
) -> None:
    if set(inventory) != set(expected):
        raise P0WindowsFixedOwnerPolicyStoreCandidateError(
            f"{label} exact inventory mismatch"
        )
    for name, should_be_directory in expected.items():
        entry = inventory[name]
        is_directory = bool(entry.attributes & _FILE_ATTRIBUTE_DIRECTORY)
        if (
            is_directory is not should_be_directory
            or entry.attributes & _FILE_ATTRIBUTE_REPARSE_POINT
            or entry.reparse_tag
        ):
            raise P0WindowsFixedOwnerPolicyStoreCandidateError(
                f"{label} inventory member kind/reparse mismatch: {name}"
            )


def _assert_non_inheritable(api: _HandleFlagsApi, handle: int, label: str) -> None:
    flags = wintypes.DWORD()
    if not api.GetHandleInformation(handle, ctypes.byref(flags)):
        raise P0WindowsFixedOwnerPolicyStoreCandidateError(
            f"GetHandleInformation failed for {label}"
        )
    if flags.value & _HANDLE_FLAG_INHERIT:
        raise P0WindowsFixedOwnerPolicyStoreCandidateError(
            f"held handle is inheritable: {label}"
        )


def _pin_cross_binding(
    body: Mapping[str, Any], pin: Mapping[str, Any], pin_raw: bytes
) -> dict[str, Any]:
    operational_key = body["operational_key"]
    expected = {
        "trust_domain": body["trust_domain"],
        "project_id": body["project_id"],
        "environment": body["environment"],
        "key_id": operational_key["key_id"],
        "key_epoch": operational_key["key_epoch"],
        "algorithm": operational_key["algorithm"],
        "public_key_fingerprint_sha256": operational_key[
            "public_key_fingerprint_sha256"
        ],
        "owner_principal_sha256": body["owner_principal_sha256"],
        "owner_anchor_sha256": body["owner_anchor_sha256"],
        "allowed_signature_domains": operational_key[
            "allowed_signature_domains"
        ],
    }
    for field, value in expected.items():
        if pin.get(field) != value:
            raise P0WindowsFixedOwnerPolicyStoreCandidateError(
                f"public-key pin/policy cross-binding mismatch: {field}"
            )
    pin_bytes_sha = hashlib.sha256(pin_raw).hexdigest()
    if not hmac.compare_digest(
        pin_bytes_sha, operational_key["pin_bytes_sha256"]
    ) or not hmac.compare_digest(
        pin["artifact_sha256"], operational_key["pin_artifact_sha256"]
    ):
        raise P0WindowsFixedOwnerPolicyStoreCandidateError(
            "public-key pin byte/artifact hash mismatch"
        )
    return {
        "public_key_pin_bytes_sha256": pin_bytes_sha,
        "public_key_pin_artifact_sha256": pin["artifact_sha256"],
        "public_key_fingerprint_sha256": pin[
            "public_key_fingerprint_sha256"
        ],
        "public_key_id": pin["key_id"],
        "public_key_epoch": pin["key_epoch"],
    }


def _watch_projection(outcome: Any) -> dict[str, Any]:
    return {
        "requested_path": outcome.requested_path,
        "identity": outcome.identity.as_dict(),
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
        "watch_handles_closed_observed": (
            outcome.watch_handles_closed_observed
        ),
        "directory_change_notification_delivered_observed": (
            outcome.directory_change_notification_delivered_observed
        ),
        "overflow_observed": outcome.overflow_observed,
        "observation_gap_observed": outcome.observation_gap_observed,
        "bounded_watch_observation_verified": (
            outcome.project_source_directory_change_watch_observation_verified
        ),
    }


def _assert_watch_clean(outcome: Any, label: str) -> None:
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
        raise P0WindowsFixedOwnerPolicyStoreCandidateError(
            f"{label} directory-change interval is not clean"
        )


def _observe_with_held_handles(
    program_data_path: str,
    paths: Mapping[str, str],
    watches: list[Any],
) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    api = fixed._Win32()
    flags_api = _HandleFlagsApi()
    store_path, ancestor_paths = fixed._lexical_ancestor_paths(
        paths["policy_store"]
    )
    if store_path != paths["policy_store"]:
        raise P0WindowsFixedOwnerPolicyStoreCandidateError(
            "fixed policy store path normalization mismatch"
        )

    with ExitStack() as stack:
        ancestors: list[tuple[str, Any, Any]] = []
        for index, lexical_path in enumerate(ancestor_paths):
            handle = stack.enter_context(
                fixed._open_handle(
                    api, lexical_path, directory=True, read_data=False
                )
            )
            _assert_non_inheritable(flags_api, handle.value, f"ancestor {index}")
            snapshot = fixed._query_snapshot(
                api, handle.value, include_streams=False
            )
            fixed._assert_directory(snapshot, f"ancestor {index}")
            if ancestors:
                parent = ancestors[-1][2]
                if snapshot.volume_serial != parent.volume_serial:
                    raise P0WindowsFixedOwnerPolicyStoreCandidateError(
                        "fixed-store ancestor chain crosses a volume"
                    )
                fixed._assert_direct_final_path_descendant(
                    parent.final_path, snapshot.final_path, f"ancestor {index}"
                )
            ancestors.append((lexical_path, handle, snapshot))
        if not ancestors:
            raise P0WindowsFixedOwnerPolicyStoreCandidateError(
                "fixed store requires held lexical ancestors"
            )

        held: dict[str, tuple[Any, Any]] = {}
        for role in policy.OBJECT_ROLES:
            is_directory = role in policy.OBJECT_ROLES[:5]
            handle = stack.enter_context(
                fixed._open_handle(
                    api,
                    paths[role],
                    directory=is_directory,
                    read_data=not is_directory,
                )
            )
            _assert_non_inheritable(flags_api, handle.value, role)
            snapshot = fixed._query_snapshot(
                api, handle.value, include_streams=not is_directory
            )
            if is_directory:
                fixed._assert_directory(snapshot, role)
            else:
                fixed._assert_regular_single_link(snapshot, role)
            held[role] = (handle, snapshot)

        parent_by_role = {
            "policy_store": None,
            "generations_directory": "policy_store",
            "generation_directory": "generations_directory",
            "policy_directory": "generation_directory",
            "pin_directory": "generation_directory",
            "policy_body_file": "policy_directory",
            "policy_signature_file": "policy_directory",
            "public_key_pin_file": "pin_directory",
        }
        names_by_role = {
            "policy_store": policy.FIXED_POLICY_STORE_SUFFIX[-1],
            "generations_directory": "generations",
            "generation_directory": GENERATION_COMPONENT,
            "policy_directory": "policy",
            "pin_directory": "pin",
            "policy_body_file": POLICY_BODY_FILENAME,
            "policy_signature_file": POLICY_SIGNATURE_FILENAME,
            "public_key_pin_file": PUBLIC_KEY_PIN_FILENAME,
        }
        seen_ids: set[tuple[int, str]] = set()
        store_volume = held["policy_store"][1].volume_serial
        for role in policy.OBJECT_ROLES:
            snapshot = held[role][1]
            if snapshot.volume_serial != store_volume:
                raise P0WindowsFixedOwnerPolicyStoreCandidateError(
                    f"fixed policy role crosses a volume: {role}"
                )
            identity = (snapshot.volume_serial, snapshot.file_id)
            if identity in seen_ids:
                raise P0WindowsFixedOwnerPolicyStoreCandidateError(
                    "fixed policy roles must have unique object identities"
                )
            seen_ids.add(identity)
            parent_role = parent_by_role[role]
            parent_snapshot = (
                ancestors[-1][2]
                if parent_role is None
                else held[parent_role][1]
            )
            expected_final_path = (
                parent_snapshot.final_path + "\\" + names_by_role[role]
            )
            if snapshot.final_path != expected_final_path:
                raise P0WindowsFixedOwnerPolicyStoreCandidateError(
                    f"fixed role final path/casing mismatch: {role}"
                )
            fixed._assert_direct_final_path_descendant(
                parent_snapshot.final_path, snapshot.final_path, role
            )

        program_data_snapshot = next(
            (
                snapshot
                for lexical_path, _handle, snapshot in ancestors
                if os.path.abspath(lexical_path) == program_data_path
            ),
            None,
        )
        if program_data_snapshot is None:
            raise P0WindowsFixedOwnerPolicyStoreCandidateError(
                "ProgramData handle is absent from the held ancestor chain"
            )

        watch_expected = (
            ancestors[-1][2],
            held["policy_store"][1],
        )
        for watch, expected in zip(watches, watch_expected, strict=True):
            observed = watch.identity
            if (
                observed.final_path != expected.final_path
                or observed.volume_serial != expected.volume_serial
                or observed.file_id != expected.file_id
            ):
                raise P0WindowsFixedOwnerPolicyStoreCandidateError(
                    "directory-watch identity does not match held handle"
                )

        inventories_before: dict[str, Mapping[str, Any]] = {}
        for role, expected in _DIRECTORY_INVENTORIES.items():
            inventory = fixed._enumerate_directory(api, held[role][0].value)
            _validate_exact_inventory(inventory, expected, role)
            inventories_before[role] = inventory
            for name in expected:
                child_role = next(
                    candidate_role
                    for candidate_role, candidate_name in names_by_role.items()
                    if candidate_name == name
                    and parent_by_role[candidate_role] == role
                )
                fixed._assert_entry_matches_snapshot(
                    inventory[name], held[child_role][1], name
                )

        raw_by_role: dict[str, bytes] = {}
        for role in policy.OBJECT_ROLES[5:]:
            handle, before = held[role]
            raw_by_role[role] = fixed._read_handle_exact(
                api, handle.value, before.standard[1], role
            )
            after_read = fixed._query_snapshot(
                api, handle.value, include_streams=True
            )
            if not _snapshot_exact_stable(before, after_read):
                raise P0WindowsFixedOwnerPolicyStoreCandidateError(
                    f"fixed policy file changed while read: {role}"
                )

        body_raw = raw_by_role["policy_body_file"]
        signature_raw = raw_by_role["policy_signature_file"]
        pin_raw = raw_by_role["public_key_pin_file"]
        contract_receipt = policy.validate_presented_windows_owner_policy_contract(
            policy_body_bytes=body_raw,
            policy_signature_bytes=signature_raw,
        )
        bootstrap_receipt = (
            bootstrap.verify_presented_windows_owner_policy_bootstrap_signature_candidate(
                policy_body_bytes=body_raw,
                policy_signature_bytes=signature_raw,
            )
        )
        body = json.loads(body_raw.decode("utf-8"))
        _validate_same_call_bootstrap_receipt(
            receipt=bootstrap_receipt,
            policy_body_bytes=body_raw,
            policy_signature_bytes=signature_raw,
            contract_receipt=contract_receipt,
            body=body,
        )
        if body["policy_epoch"] != COMPILED_POLICY_EPOCH:
            raise P0WindowsFixedOwnerPolicyStoreCandidateError(
                "policy epoch does not match the compiled genesis directory"
            )
        object_rows = {row["role"]: row for row in body["object_policies"]}
        for role in policy.OBJECT_ROLES:
            observed = _identity_projection(held[role][1])
            expected = {
                "final_path": object_rows[role]["final_volume_guid_path"],
                "volume_serial_decimal": object_rows[role][
                    "volume_serial_decimal"
                ],
                "file_id_128_hex": object_rows[role]["file_id_128_hex"],
            }
            if observed != expected:
                raise P0WindowsFixedOwnerPolicyStoreCandidateError(
                    f"signed/live object identity mismatch: {role}"
                )

        try:
            pin_value = asymmetric._parse_canonical_json(
                pin_raw, "fixed-store public-key pin"
            )
            pin, _x, _y = asymmetric._validate_pin(pin_value)
        except asymmetric.P0ExternalOwnerAsymmetricSignatureError as exc:
            raise P0WindowsFixedOwnerPolicyStoreCandidateError(
                "fixed-store public-key pin is invalid"
            ) from exc
        pin_projection = _pin_cross_binding(body, pin, pin_raw)

        acl_hashes: dict[str, str] = {}
        acl_before: dict[str, Mapping[str, Any]] = {}
        for role in policy.OBJECT_ROLES:
            projection = binary_acl.observe_windows_binary_acl_projection(
                handle=held[role][0].value
            )
            policy.compare_exact_security_projection(
                validated_policy_body_bytes=body_raw,
                role=role,
                observed_security_projection=projection,
            )
            acl_before[role] = projection
            acl_hashes[role] = canonical_sha256(projection)

        for index, watch in enumerate(watches):
            barrier = watch.barrier()
            if not barrier.observation_acceptable:
                raise P0WindowsFixedOwnerPolicyStoreCandidateError(
                    f"directory watch completed before interval end: {index}"
                )

        inventories_after: dict[str, Mapping[str, Any]] = {}
        for role, expected in _DIRECTORY_INVENTORIES.items():
            inventory = fixed._enumerate_directory(api, held[role][0].value)
            _validate_exact_inventory(inventory, expected, role)
            inventories_after[role] = inventory
            if fixed._inventory_projection(inventories_before[role]) != (
                fixed._inventory_projection(inventory)
            ):
                raise P0WindowsFixedOwnerPolicyStoreCandidateError(
                    f"fixed directory inventory changed: {role}"
                )

        role_after: dict[str, Any] = {}
        for role in policy.OBJECT_ROLES:
            handle, before = held[role]
            after = fixed._query_snapshot(
                api,
                handle.value,
                include_streams=role not in policy.OBJECT_ROLES[:5],
            )
            if not _snapshot_exact_stable(before, after):
                raise P0WindowsFixedOwnerPolicyStoreCandidateError(
                    f"fixed role identity/metadata changed: {role}"
                )
            role_after[role] = after
            projection = binary_acl.observe_windows_binary_acl_projection(
                handle=handle.value
            )
            if canonical_sha256(projection) != acl_hashes[role]:
                raise P0WindowsFixedOwnerPolicyStoreCandidateError(
                    f"fixed role binary ACL changed: {role}"
                )

        for role in policy.OBJECT_ROLES:
            is_directory = role in policy.OBJECT_ROLES[:5]
            with fixed._open_handle(
                api,
                paths[role],
                directory=is_directory,
                read_data=False,
            ) as reopened:
                _assert_non_inheritable(
                    flags_api, reopened.value, f"reopened {role}"
                )
                snapshot = fixed._query_snapshot(
                    api,
                    reopened.value,
                    include_streams=not is_directory,
                )
                if not _snapshot_exact_stable(role_after[role], snapshot):
                    raise P0WindowsFixedOwnerPolicyStoreCandidateError(
                        f"lexical reopen identity mismatch: {role}"
                    )

        for index, (lexical_path, _handle, before) in enumerate(ancestors):
            after = fixed._query_snapshot(
                api, ancestors[index][1].value, include_streams=False
            )
            if (
                before.final_path != after.final_path
                or fixed._ancestor_namespace_projection(before)
                != fixed._ancestor_namespace_projection(after)
            ):
                raise P0WindowsFixedOwnerPolicyStoreCandidateError(
                    f"ancestor namespace identity changed: {index}"
                )
            with fixed._open_handle(
                api, lexical_path, directory=True, read_data=False
            ) as reopened:
                _assert_non_inheritable(
                    flags_api, reopened.value, f"reopened ancestor {index}"
                )
                reopened_snapshot = fixed._query_snapshot(
                    api, reopened.value, include_streams=False
                )
                if (
                    after.final_path != reopened_snapshot.final_path
                    or fixed._ancestor_namespace_projection(after)
                    != fixed._ancestor_namespace_projection(reopened_snapshot)
                ):
                    raise P0WindowsFixedOwnerPolicyStoreCandidateError(
                        f"ancestor lexical reopen identity mismatch: {index}"
                    )

        ancestor_projection = [
            {
                "lexical_path": lexical_path,
                **_identity_projection(snapshot),
            }
            for lexical_path, _handle, snapshot in ancestors
        ]
        role_projection = {
            role: _identity_projection(held[role][1])
            for role in policy.OBJECT_ROLES
        }
        inventory_projection = {
            role: fixed._inventory_projection(inventories_before[role])
            for role in _DIRECTORY_INVENTORIES
        }
        public_base = {
            "known_folder_id": KNOWN_FOLDER_ID,
            "known_folder_flags": KNOWN_FOLDER_FLAGS,
            "known_folder_token_is_null": True,
            "known_folder_api_succeeded": True,
            "known_folder_free_call_completed_observed": True,
            "program_data_held_identity": _identity_projection(
                program_data_snapshot
            ),
            "program_data_held_identity_verified": True,
            "program_data_no_reparse_verified": True,
            "fixed_relative_store_components": list(
                policy.FIXED_POLICY_STORE_SUFFIX
            ),
            "selected_generation_component": GENERATION_COMPONENT,
            "selected_policy_epoch": COMPILED_POLICY_EPOCH,
            "compiled_genesis_inventory_verified": True,
            "lexical_ancestor_handle_count": len(ancestors),
            "lexical_ancestor_identity_projection": ancestor_projection,
            "lexical_ancestor_identity_projection_sha256": canonical_sha256(
                ancestor_projection
            ),
            "role_handle_count": len(held),
            "role_identity_projection_by_role": role_projection,
            "role_identity_projection_sha256": canonical_sha256(
                role_projection
            ),
            "inventory_projection_by_directory": inventory_projection,
            "inventory_projection_sha256": canonical_sha256(
                inventory_projection
            ),
            "policy_body_bytes_length": len(body_raw),
            "policy_body_bytes_sha256": hashlib.sha256(body_raw).hexdigest(),
            "policy_signature_bytes_length": len(signature_raw),
            "policy_signature_bytes_sha256": hashlib.sha256(
                signature_raw
            ).hexdigest(),
            "public_key_pin_bytes_length": len(pin_raw),
            **pin_projection,
            "owner_policy_contract_receipt": contract_receipt,
            "owner_policy_contract_receipt_declared_sha256": (
                contract_receipt["receipt_sha256"]
            ),
            "owner_policy_contract_receipt_full_canonical_sha256": (
                canonical_sha256(contract_receipt)
            ),
            "bootstrap_policy_signature_candidate_receipt": bootstrap_receipt,
            "bootstrap_policy_signature_candidate_receipt_declared_sha256": (
                bootstrap_receipt["receipt_sha256"]
            ),
            "bootstrap_signature_input_sha256": bootstrap_receipt[
                "signature_material_bytes_sha256"
            ],
            "compiled_bootstrap_key_id": bootstrap_receipt[
                "compiled_bootstrap_key_id"
            ],
            "compiled_bootstrap_public_key_fingerprint_sha256": (
                bootstrap_receipt[
                    "compiled_bootstrap_public_key_fingerprint_sha256"
                ]
            ),
            "compiled_bootstrap_key_candidate_selected": bootstrap_receipt[
                "compiled_bootstrap_key_candidate_selected"
            ],
            "bootstrap_signature_mathematics_verified": bootstrap_receipt[
                "bootstrap_signature_mathematics_verified"
            ],
            "acl_projection_sha256_by_role": acl_hashes,
            "policy_epoch_directory_exact_match_observed": True,
            "fixed_generation_layout_handle_binding_observed": True,
            "policy_object_identity_live_handle_exact_match_observed": True,
            "pin_bytes_operational_key_cross_binding_observed": True,
            "held_role_acl_projection_matches_presented_template_observed": True,
            "all_lexical_ancestor_handles_held": True,
            "ancestor_namespace_pre_post_and_reopen_stable": True,
            "all_role_handles_held_across_validation": True,
            "all_handles_non_inheritable_observed": True,
            "single_link_non_reparse_unnamed_stream_observed": True,
            "same_volume_role_set_observed": True,
            "role_pre_post_identity_inventory_acl_stable": True,
            "path_reopen_identity_stable": True,
        }
        return public_base, body, signature_raw


def _observe_at_program_data_with_body_and_signature_bytes(
    program_data_path: str,
) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    paths = _role_paths(program_data_path)
    watch_paths = (
        os.path.join(program_data_path, policy.FIXED_POLICY_STORE_SUFFIX[0]),
        paths["policy_store"],
    )
    watches: list[Any] = []
    primary_error: BaseException | None = None
    base: dict[str, Any] | None = None
    body: dict[str, Any] | None = None
    signature_bytes: bytes | None = None
    outcomes: list[Any] = []
    try:
        for path in watch_paths:
            watches.append(
                directory_watch.WindowsDirectoryChangeWatch.start(
                    path,
                    watch_subtree=True,
                    notify_filter=_WATCH_FILTER,
                )
            )
        base, body, signature_bytes = _observe_with_held_handles(
            program_data_path, paths, watches
        )
    except BaseException as exc:
        primary_error = exc
    finally:
        for watch in reversed(watches):
            try:
                outcomes.append(watch.finalize())
            except BaseException as cleanup_error:
                if primary_error is None:
                    primary_error = cleanup_error

    if primary_error is not None:
        if isinstance(
            primary_error, P0WindowsFixedOwnerPolicyStoreCandidateError
        ):
            raise primary_error
        raise P0WindowsFixedOwnerPolicyStoreCandidateError(
            "fixed owner-policy store observation failed closed"
        ) from primary_error
    assert base is not None and body is not None and signature_bytes is not None
    outcomes.reverse()
    for index, outcome in enumerate(outcomes):
        _assert_watch_clean(outcome, f"fixed-store watch {index}")
    watch_projection = [_watch_projection(outcome) for outcome in outcomes]
    material: dict[str, Any] = {
        "schema_version": CANDIDATE_RECEIPT_SCHEMA,
        "gate_status": GATE_STATUS,
        "candidate_only": True,
        **base,
        "directory_change_watches": watch_projection,
        "bounded_directory_change_interval_observed": True,
        "fixed_policy_store_discovery_candidate_observed": True,
        "caller_supplied_path_absent": True,
        "caller_supplied_environment_absent": True,
        "caller_supplied_epoch_absent": True,
        "caller_supplied_key_absent": True,
        "caller_supplied_sid_absent": True,
        "caller_supplied_expected_identity_absent": True,
        "caller_supplied_receipt_state_callback_absent": True,
        **{field: False for field in _FALSE_FIELDS},
        "credited_actual_source_claim_count": 0,
        "credited_actual_a_context_review_count": 0,
        "operational_effect": "NONE_SHADOW_ONLY",
    }
    receipt = {**material, "receipt_sha256": canonical_sha256(material)}
    return receipt, body, signature_bytes


def _observe_at_program_data_with_body(
    program_data_path: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    receipt, body, _signature_bytes = (
        _observe_at_program_data_with_body_and_signature_bytes(program_data_path)
    )
    return receipt, body


def _observe_at_program_data(program_data_path: str) -> dict[str, Any]:
    receipt, _body = _observe_at_program_data_with_body(program_data_path)
    return receipt


def _observe_fixed_windows_owner_policy_store_candidate_with_body(
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Private same-call handoff for the zero-input host preflight.

    The parsed body is never serialized into the public fixed-store receipt.
    Handles and watches have closed by return, so consumers must not claim a
    single atomic store/host observation interval.
    """

    if not _IS_WINDOWS:
        raise P0WindowsFixedOwnerPolicyStoreCandidateError(
            "fixed owner-policy store observation is Windows-only"
        )
    try:
        program_data_path = _program_data_path(_KnownFolderApi())
        return _observe_at_program_data_with_body(program_data_path)
    except P0WindowsFixedOwnerPolicyStoreCandidateError:
        raise
    except BaseException as exc:
        raise P0WindowsFixedOwnerPolicyStoreCandidateError(
            "fixed owner-policy store observation failed closed"
        ) from exc


def _observe_fixed_windows_owner_policy_store_candidate_with_body_and_signature_bytes(
) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    """Private v3 handoff retaining the exact same-call signature bytes.

    This does not extend the public fixed-store receipt.  The successor can
    independently recompute the detached-signature byte and artifact hashes;
    handles and watches are still closed before return.
    """

    if not _IS_WINDOWS:
        raise P0WindowsFixedOwnerPolicyStoreCandidateError(
            "fixed owner-policy store observation is Windows-only"
        )
    try:
        program_data_path = _program_data_path(_KnownFolderApi())
        return _observe_at_program_data_with_body_and_signature_bytes(
            program_data_path
        )
    except P0WindowsFixedOwnerPolicyStoreCandidateError:
        raise
    except BaseException as exc:
        raise P0WindowsFixedOwnerPolicyStoreCandidateError(
            "fixed owner-policy store observation failed closed"
        ) from exc


def observe_fixed_windows_owner_policy_store_candidate() -> dict[str, Any]:
    """Observe the compiled ProgramData/genesis store without caller inputs."""

    if not _IS_WINDOWS:
        raise P0WindowsFixedOwnerPolicyStoreCandidateError(
            "fixed owner-policy store observation is Windows-only"
        )
    try:
        receipt, _body = (
            _observe_fixed_windows_owner_policy_store_candidate_with_body()
        )
        return receipt
    except P0WindowsFixedOwnerPolicyStoreCandidateError:
        raise
    except BaseException as exc:
        raise P0WindowsFixedOwnerPolicyStoreCandidateError(
            "fixed owner-policy store observation failed closed"
        ) from exc


__all__ = [
    "CANDIDATE_RECEIPT_SCHEMA",
    "COMPILED_POLICY_EPOCH",
    "GATE_STATUS",
    "KNOWN_FOLDER_ID",
    "P0WindowsFixedOwnerPolicyStoreCandidateError",
    "observe_fixed_windows_owner_policy_store_candidate",
]
