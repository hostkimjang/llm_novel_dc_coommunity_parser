"""Bounded supervisor receipt for direct packet-side validator execution.

The executor in this module accepts roots and caller pins, not serialized
child receipts.  It captures the Windows packet once and invokes the packet
validators over that single in-memory observation in a fixed order.  Local
source/code measurements make the invocation trace reproducible, but are not
an external code authority or a trusted supervisor runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import marshal
from pathlib import Path
import re
from types import MappingProxyType, ModuleType
from typing import Any, Callable, Mapping

from llm_batch.grounding import p0_actual_a_event_bytes as a_event_bytes
from llm_batch.grounding import p0_actual_packet_contract as packet_contract
from llm_batch.grounding import p0_windows_fixed_directory_identity as windows_identity


SUPERVISOR_EXECUTION_RECEIPT_SCHEMA = (
    "p0_actual_packet_supervisor_execution_receipt_v1"
)
VALIDATOR_MEASUREMENT_MANIFEST_SCHEMA = (
    "p0_actual_packet_validator_measurement_manifest_v1"
)
PRESENTED_RECEIPT_VALIDATION_SCHEMA = (
    "p0_actual_presented_packet_supervisor_receipt_validation_v1"
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")
_FILE_ID = re.compile(r"^[0-9a-f]{32}$")

_STEP_SPECS = (
    (
        0,
        "READ_WINDOWS_FIXED_PACKET_DIRECTORY",
        windows_identity,
        "read_windows_fixed_p0_packet_directory",
        windows_identity.WINDOWS_HANDLE_RECEIPT_SCHEMA,
    ),
    (
        1,
        "VALIDATE_PACKET_BYTES",
        packet_contract,
        "validate_packet_bytes",
        packet_contract.PACKET_RECEIPT_SCHEMA,
    ),
    (
        2,
        "BIND_WINDOWS_FIXED_PACKET_OBSERVATION",
        windows_identity,
        "bind_windows_fixed_packet_observation",
        windows_identity.WINDOWS_PACKET_VALIDATION_RECEIPT_SCHEMA,
    ),
    (
        3,
        "VERIFY_A_EVENT_BYTES",
        a_event_bytes,
        "verify_a_event_bytes",
        a_event_bytes.A_EVENT_BYTES_RECEIPT_SCHEMA,
    ),
)

_FALSE_AUTHORITY_FIELDS = (
    "authority_side_execution_trace_verified",
    "external_code_authority_verified",
    "supervisor_runtime_trust_verified",
    "nonce_uniqueness_verified",
    "filesystem_handle_trust_verified",
    "external_root_identity_pin_verified",
    "owner_authority_verified",
    "external_owner_authority_verified",
    "os_write_deny_verified",
    "runtime_noninterference_verified",
    "authority_journal_watch_bundle_verified",
    "actual_authority_granted",
    "production_approval",
    "full_scan_approval",
    "p0_phase_exit",
    "action_applied",
)

_NESTED_FORBIDDEN_TRUE_FIELDS = frozenset(
    {
        "external_root_identity_pin_verified",
        "filesystem_handle_trust_verified",
        "durable_predecessor_verified",
        "annotation_append_only_verified",
        "owner_authority_verified",
        "external_owner_authority_verified",
        "os_write_deny_verified",
        "runtime_noninterference_verified",
        "authority_journal_watch_bundle_verified",
        "external_code_authority_verified",
        "supervisor_runtime_trust_verified",
        "nonce_uniqueness_verified",
        "actual_authority_granted",
        "production_approval",
        "full_scan_approval",
        "p0_phase_exit",
        "action_applied",
    }
)


class P0ActualSupervisorExecutionError(ValueError):
    """Raised when the bounded direct-execution contract fails closed."""


@dataclass(frozen=True)
class _PacketSupervisorState:
    """Private immutable hand-off for same-process authority integration.

    This state is created only by the direct executor.  It is deliberately
    absent from ``__all__`` and is never accepted as a public input, so a
    caller-presented serialized receipt cannot stand in for the captured raw
    bytes or the in-process validator results.
    """

    raw_by_name: Mapping[str, bytes]
    raw_member_projection: tuple[Mapping[str, Any], ...]
    handle_receipt: Mapping[str, Any]
    packet_receipt: Mapping[str, Any]
    windows_packet_receipt: Mapping[str, Any]
    a_event_receipt: Mapping[str, Any]
    public_receipt: Mapping[str, Any]


def _freeze_snapshot(value: Any) -> Any:
    """Recursively freeze JSON-like execution state without serializing it."""

    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze_snapshot(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_snapshot(item) for item in value)
    if isinstance(value, bytes):
        return bytes(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise P0ActualSupervisorExecutionError(
        f"execution snapshot contains unsupported value: {type(value).__name__}"
    )


def _thaw_snapshot(value: Any) -> Any:
    """Return a fresh ordinary JSON-like copy of a private frozen snapshot."""

    if isinstance(value, Mapping):
        return {key: _thaw_snapshot(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_snapshot(item) for item in value]
    if isinstance(value, bytes):
        return bytes(value)
    return value


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


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise P0ActualSupervisorExecutionError(
            f"{field} must be 64 lowercase hexadecimal characters"
        )
    return value


def _identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise P0ActualSupervisorExecutionError(f"{field} is invalid")
    return value


def _module_source_sha256(module: ModuleType) -> str:
    source_path = getattr(module, "__file__", None)
    if not isinstance(source_path, str):
        raise P0ActualSupervisorExecutionError("validator module has no source path")
    path = Path(source_path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise P0ActualSupervisorExecutionError(
            f"cannot measure validator module source: {module.__name__}"
        ) from exc
    return hashlib.sha256(raw).hexdigest()


def _callable_code_sha256(value: Any, label: str) -> str:
    code = getattr(value, "__code__", None)
    if code is None:
        raise P0ActualSupervisorExecutionError(
            f"validator callable has no Python code object: {label}"
        )
    material = {
        "code_marshaled_sha256": hashlib.sha256(marshal.dumps(code)).hexdigest(),
        "defaults_sha256": canonical_sha256(repr(getattr(value, "__defaults__", None))),
        "kwdefaults_sha256": canonical_sha256(
            repr(getattr(value, "__kwdefaults__", None))
        ),
    }
    return canonical_sha256(material)


def _measurement(
    step_index: int,
    step_name: str,
    module: ModuleType,
    callable_name: str,
) -> dict[str, Any]:
    target = getattr(module, callable_name, None)
    if not callable(target):
        raise P0ActualSupervisorExecutionError(
            f"validator callable is unavailable: {module.__name__}.{callable_name}"
        )
    return {
        "step_index": step_index,
        "step_name": step_name,
        "module_name": module.__name__,
        "callable_name": callable_name,
        "module_source_sha256": _module_source_sha256(module),
        "callable_code_sha256": _callable_code_sha256(
            target, f"{module.__name__}.{callable_name}"
        ),
    }


def build_local_packet_validator_measurement_manifest() -> dict[str, Any]:
    """Measure the local validators; this helper confers no external trust."""

    measurements = [
        _measurement(index, name, module, callable_name)
        for index, name, module, callable_name, _ in _STEP_SPECS
    ]
    material = {
        "schema_version": VALIDATOR_MEASUREMENT_MANIFEST_SCHEMA,
        "measurement_scope": "LOCAL_SELF_MEASUREMENT_NOT_EXTERNAL_AUTHORITY",
        "measurements": measurements,
        "external_code_authority_verified": False,
        "supervisor_runtime_trust_verified": False,
    }
    return {**material, "artifact_sha256": canonical_sha256(material)}


def _validate_measurement_manifest(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise P0ActualSupervisorExecutionError("measurement manifest must be an object")
    expected_fields = {
        "schema_version",
        "measurement_scope",
        "measurements",
        "external_code_authority_verified",
        "supervisor_runtime_trust_verified",
        "artifact_sha256",
    }
    if set(value) != expected_fields:
        raise P0ActualSupervisorExecutionError("measurement manifest fields mismatch")
    row = dict(value)
    if row["schema_version"] != VALIDATOR_MEASUREMENT_MANIFEST_SCHEMA:
        raise P0ActualSupervisorExecutionError("measurement manifest schema mismatch")
    if row["measurement_scope"] != "LOCAL_SELF_MEASUREMENT_NOT_EXTERNAL_AUTHORITY":
        raise P0ActualSupervisorExecutionError("measurement scope mismatch")
    if row["external_code_authority_verified"] is not False or row[
        "supervisor_runtime_trust_verified"
    ] is not False:
        raise P0ActualSupervisorExecutionError(
            "local measurement cannot assert external/runtime trust"
        )
    stored = _sha(row["artifact_sha256"], "measurement artifact_sha256")
    material = {key: item for key, item in row.items() if key != "artifact_sha256"}
    if stored != canonical_sha256(material):
        raise P0ActualSupervisorExecutionError("measurement manifest self-hash mismatch")
    values = row["measurements"]
    if not isinstance(values, list) or len(values) != len(_STEP_SPECS):
        raise P0ActualSupervisorExecutionError("measurement row count mismatch")
    measurement_fields = {
        "step_index",
        "step_name",
        "module_name",
        "callable_name",
        "module_source_sha256",
        "callable_code_sha256",
    }
    for measured, (index, name, module, callable_name, _) in zip(values, _STEP_SPECS):
        if not isinstance(measured, Mapping) or set(measured) != measurement_fields:
            raise P0ActualSupervisorExecutionError("measurement row fields mismatch")
        if (
            measured["step_index"] != index
            or measured["step_name"] != name
            or measured["module_name"] != module.__name__
            or measured["callable_name"] != callable_name
        ):
            raise P0ActualSupervisorExecutionError("measurement row identity/order mismatch")
        _sha(measured["module_source_sha256"], "module_source_sha256")
        _sha(measured["callable_code_sha256"], "callable_code_sha256")
    return json.loads(canonical_bytes(row))


def _measure_and_match(expected: Mapping[str, Any], step_index: int) -> dict[str, Any]:
    index, name, module, callable_name, _ = _STEP_SPECS[step_index]
    measured = _measurement(index, name, module, callable_name)
    if measured != expected["measurements"][step_index]:
        raise P0ActualSupervisorExecutionError(
            f"caller-pinned validator measurement mismatch at step {step_index}"
        )
    return measured


def _verify_declared_receipt(
    value: Any,
    *,
    expected_schema: str,
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise P0ActualSupervisorExecutionError(f"{label} result must be an object")
    row = dict(value)
    if row.get("schema_version") != expected_schema:
        raise P0ActualSupervisorExecutionError(f"{label} result schema mismatch")
    stored = _sha(row.get("receipt_sha256"), f"{label} receipt_sha256")
    material = {key: item for key, item in row.items() if key != "receipt_sha256"}
    if stored != canonical_sha256(material):
        raise P0ActualSupervisorExecutionError(f"{label} result self-hash mismatch")
    overclaimed: list[str] = []

    def inspect_nested(item: Any, path: str) -> None:
        if isinstance(item, Mapping):
            for key, nested in item.items():
                nested_path = f"{path}.{key}" if path else str(key)
                if key in _NESTED_FORBIDDEN_TRUE_FIELDS and nested is True:
                    overclaimed.append(nested_path)
                inspect_nested(nested, nested_path)
        elif isinstance(item, list):
            for index, nested in enumerate(item):
                inspect_nested(nested, f"{path}[{index}]")

    inspect_nested(row, label)
    if overclaimed:
        raise P0ActualSupervisorExecutionError(
            f"{label} result overclaims forbidden capability/trust fields: {overclaimed}"
        )
    return {
        "schema_version": expected_schema,
        "declared_receipt_sha256": stored,
        "full_canonical_sha256": canonical_sha256(row),
    }


def _raw_member_projection(raw_by_name: Mapping[str, bytes]) -> list[dict[str, Any]]:
    expected_names = {
        packet_contract.PACKET_MANIFEST_FILENAME,
        *(path for _, path, _ in packet_contract.CHILD_FILES),
    }
    if set(raw_by_name) != expected_names:
        raise P0ActualSupervisorExecutionError("captured raw member inventory mismatch")
    role_by_path = {path: role for role, path, _ in packet_contract.CHILD_FILES}
    ordered_names = [packet_contract.PACKET_MANIFEST_FILENAME] + [
        path for _, path, _ in packet_contract.CHILD_FILES
    ]
    result: list[dict[str, Any]] = []
    for index, name in enumerate(ordered_names):
        raw = raw_by_name[name]
        if not isinstance(raw, bytes):
            raise P0ActualSupervisorExecutionError("captured raw member must be bytes")
        result.append(
            {
                "index": index,
                "role": "packet_manifest" if index == 0 else role_by_path[name],
                "path": name,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    expected_count = 1 + len(packet_contract.CHILD_FILES)
    if len(result) != expected_count:
        raise P0ActualSupervisorExecutionError(
            "packet supervisor raw inventory differs from the fixed packet contract"
        )
    return result


def _verify_handle_receipt_cross_binding(
    receipt: Mapping[str, Any],
    raw_by_name: Mapping[str, bytes],
    *,
    expected_root_final_path: str,
    expected_root_volume_serial: int,
    expected_root_file_id: str,
) -> None:
    root_path = receipt.get("root_final_path")
    if (
        not isinstance(root_path, str)
        or root_path.casefold() != expected_root_final_path.casefold()
        or receipt.get("root_volume_serial") != str(expected_root_volume_serial)
        or receipt.get("root_file_id") != expected_root_file_id
    ):
        raise P0ActualSupervisorExecutionError(
            "Windows handle receipt/root identity cross-binding mismatch"
        )
    members = receipt.get("members")
    if not isinstance(members, list) or len(members) != 1 + len(
        packet_contract.CHILD_FILES
    ):
        raise P0ActualSupervisorExecutionError(
            "Windows handle receipt member inventory count mismatch"
        )
    by_name: dict[str, Mapping[str, Any]] = {}
    for member in members:
        if not isinstance(member, Mapping) or not isinstance(member.get("name"), str):
            raise P0ActualSupervisorExecutionError(
                "Windows handle receipt member is malformed"
            )
        name = member["name"]
        if name in by_name:
            raise P0ActualSupervisorExecutionError(
                "Windows handle receipt member names are not unique"
            )
        by_name[name] = member
    if set(by_name) != set(raw_by_name):
        raise P0ActualSupervisorExecutionError(
            "Windows handle receipt/raw inventory names mismatch"
        )
    for name, raw in raw_by_name.items():
        member = by_name[name]
        if member.get("bytes") != len(raw) or member.get("sha256") != hashlib.sha256(
            raw
        ).hexdigest():
            raise P0ActualSupervisorExecutionError(
                f"Windows handle receipt/raw member cross-binding mismatch: {name}"
            )


def _verify_a_receipt_cross_binding(
    receipt: Mapping[str, Any],
    role_raw: Mapping[str, bytes],
    derived_a_source_claim_bytes: bytes,
    derivation: Mapping[str, Any],
    *,
    expected_origin: str,
) -> None:
    context_rows = _strict_jsonl_rows(role_raw["a_contexts"], "A context JSONL")
    event_rows = _strict_jsonl_rows(
        role_raw["a_annotation_events"], "A event JSONL"
    )
    expected = {
        "record_origin": expected_origin,
        "source_claim_file_sha256": hashlib.sha256(
            derived_a_source_claim_bytes
        ).hexdigest(),
        "source_claim_row_count": derivation["derived_a_source_claim_row_count"],
        "a_context_file_sha256": hashlib.sha256(role_raw["a_contexts"]).hexdigest(),
        "a_context_row_count": len(context_rows),
        "a_event_file_sha256": hashlib.sha256(
            role_raw["a_annotation_events"]
        ).hexdigest(),
        "a_event_row_count": len(event_rows),
        "a_subject_selection_seal_file_sha256": hashlib.sha256(
            role_raw["a_subject_selection_seal"]
        ).hexdigest(),
        "a_subject_selection_seal_row_count": 1,
    }
    mismatched = sorted(
        field for field, value in expected.items() if receipt.get(field) != value
    )
    if mismatched:
        raise P0ActualSupervisorExecutionError(
            f"A event receipt/raw input cross-binding mismatch: {mismatched}"
        )


def _strict_jsonl_rows(raw: bytes, label: str) -> list[dict[str, Any]]:
    if not isinstance(raw, bytes) or raw.startswith(b"\xef\xbb\xbf"):
        raise P0ActualSupervisorExecutionError(f"{label} must be BOM-free bytes")
    if not raw or not raw.endswith(b"\n") or b"\r" in raw:
        raise P0ActualSupervisorExecutionError(
            f"{label} must use LF and end with exactly one record newline"
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise P0ActualSupervisorExecutionError(f"{label} is not UTF-8") from exc

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise P0ActualSupervisorExecutionError(
                    f"{label} contains a duplicate JSON key"
                )
            result[key] = value
        return result

    rows: list[dict[str, Any]] = []
    raw_lines = raw.splitlines(keepends=True)
    for index, raw_line in enumerate(raw_lines):
        if raw_line == b"\n":
            raise P0ActualSupervisorExecutionError(f"{label} contains a blank row")
        try:
            value = json.loads(
                raw_line.decode("utf-8"),
                object_pairs_hook=unique_object,
                parse_constant=lambda token: (_ for _ in ()).throw(
                    P0ActualSupervisorExecutionError(
                        f"{label} contains non-finite JSON: {token}"
                    )
                ),
            )
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise P0ActualSupervisorExecutionError(
                f"{label} row {index} is invalid JSON"
            ) from exc
        if not isinstance(value, dict):
            raise P0ActualSupervisorExecutionError(
                f"{label} row {index} must be an object"
            )
        if packet_contract.jsonl_bytes([value]) != raw_line:
            raise P0ActualSupervisorExecutionError(
                f"{label} row {index} is not canonical JSONL"
            )
        rows.append(value)
    return rows


def _derive_a_source_claim_subset(
    source_claim_raw: bytes,
    a_context_raw: bytes,
) -> tuple[bytes, dict[str, Any]]:
    """Derive the exact TRACK-A claim subset from two handle-captured members."""

    claims = _strict_jsonl_rows(source_claim_raw, "source claim JSONL")
    contexts = _strict_jsonl_rows(a_context_raw, "A context JSONL")
    claims_by_id: dict[str, dict[str, Any]] = {}
    for claim in claims:
        claim_id = claim.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            raise P0ActualSupervisorExecutionError("source claim ID is invalid")
        if claim_id in claims_by_id:
            raise P0ActualSupervisorExecutionError("source claim IDs are not unique")
        claims_by_id[claim_id] = claim
    selected_ids: set[str] = set()
    for context in contexts:
        source_claim_ids = context.get("source_claim_ids")
        if (
            not isinstance(source_claim_ids, list)
            or not source_claim_ids
            or any(not isinstance(value, str) for value in source_claim_ids)
            or source_claim_ids != sorted(set(source_claim_ids))
        ):
            raise P0ActualSupervisorExecutionError(
                "A context source claim selection is invalid"
            )
        selected_ids.update(source_claim_ids)
    missing = sorted(selected_ids - set(claims_by_id))
    if missing:
        raise P0ActualSupervisorExecutionError(
            "A context selection references a missing source claim"
        )
    non_track_a_selected = sorted(
        claim_id for claim_id in selected_ids if claims_by_id[claim_id].get("track") != "A"
    )
    if non_track_a_selected:
        raise P0ActualSupervisorExecutionError(
            "A-context selection may derive TRACK-A source claims only"
        )
    ordered_ids = sorted(selected_ids)
    ordered_rows = [claims_by_id[claim_id] for claim_id in ordered_ids]
    unselected_track_a_ids = sorted(
        claim_id
        for claim_id, row in claims_by_id.items()
        if row.get("track") == "A" and claim_id not in selected_ids
    )
    derived = packet_contract.jsonl_bytes(ordered_rows)
    projection = {
        "handle_captured_full_source_claim_file_sha256": hashlib.sha256(
            source_claim_raw
        ).hexdigest(),
        "handle_captured_full_source_claim_row_count": len(claims),
        "handle_captured_total_track_a_claim_count": sum(
            row.get("track") == "A" for row in claims
        ),
        "selected_source_claim_ids": ordered_ids,
        "selected_source_claim_ids_sha256": canonical_sha256(ordered_ids),
        "selected_source_claim_id_count": len(ordered_ids),
        "unselected_packet_track_a_claim_count": len(unselected_track_a_ids),
        "unselected_packet_track_a_claim_ids_sha256": canonical_sha256(
            unselected_track_a_ids
        ),
        "derived_a_source_claim_row_count": len(ordered_rows),
        "derived_a_source_claim_jsonl_sha256": hashlib.sha256(derived).hexdigest(),
        "selection_rule": "A_CONTEXT_SOURCE_CLAIM_ID_UNION_EXACT_TRACK_A",
        "full_source_claim_rows_canonical_json_verified": True,
        "derived_subset_duplicate_missing_non_track_a_or_unreferenced_rows_rejected": True,
    }
    return derived, projection


def _trace_row(
    *,
    step_index: int,
    previous_step_sha256: str,
    expected_measurement: Mapping[str, Any],
    before_measurement: Mapping[str, Any],
    after_measurement: Mapping[str, Any],
    input_binding: Any,
    result_binding: Mapping[str, Any],
) -> dict[str, Any]:
    _, step_name, _, _, _ = _STEP_SPECS[step_index]
    material = {
        "step_index": step_index,
        "step_name": step_name,
        "previous_step_sha256": previous_step_sha256,
        "expected_measurement_sha256": canonical_sha256(expected_measurement),
        "before_measurement_sha256": canonical_sha256(before_measurement),
        "after_measurement_sha256": canonical_sha256(after_measurement),
        "input_binding_sha256": canonical_sha256(input_binding),
        "output_schema_version": result_binding["schema_version"],
        "output_declared_receipt_sha256": result_binding[
            "declared_receipt_sha256"
        ],
        "output_full_canonical_sha256": result_binding["full_canonical_sha256"],
        "output_binding_sha256": canonical_sha256(result_binding),
    }
    return {**material, "step_sha256": canonical_sha256(material)}


def _execute_packet_supervisor_state(
    *,
    packet_dir: Path | str,
    expected_root_final_path: str,
    expected_root_volume_serial: int,
    expected_root_file_id: str,
    expected_manifest_sha256: str,
    expected_origin: str,
    session_id: str,
    run_id: str,
    nonce_commitment_sha256: str,
    expected_validator_measurement_manifest: Mapping[str, Any],
) -> _PacketSupervisorState:
    """Directly invoke validators and retain their immutable in-process state.

    No serialized observation or child receipt is accepted.  Any exception or
    mismatch aborts the function, so a state is never produced for a partially
    executed sequence.
    """

    session = _identifier(session_id, "session_id")
    run = _identifier(run_id, "run_id")
    nonce = _sha(nonce_commitment_sha256, "nonce_commitment_sha256")
    manifest_pin = _sha(expected_manifest_sha256, "expected_manifest_sha256")
    if expected_origin not in {
        packet_contract.ACTUAL_ORIGIN,
        packet_contract.EXAMPLE_ORIGIN,
    }:
        raise P0ActualSupervisorExecutionError("expected_origin is unsupported")
    if not isinstance(expected_root_final_path, str) or not expected_root_final_path:
        raise P0ActualSupervisorExecutionError("expected root final path is invalid")
    if not isinstance(expected_root_volume_serial, int) or isinstance(
        expected_root_volume_serial, bool
    ) or not 0 <= expected_root_volume_serial <= (2**64 - 1):
        raise P0ActualSupervisorExecutionError("expected root volume serial is invalid")
    if not isinstance(expected_root_file_id, str) or not _FILE_ID.fullmatch(
        expected_root_file_id
    ):
        raise P0ActualSupervisorExecutionError("expected root file ID is invalid")
    expected_measurements = _validate_measurement_manifest(
        expected_validator_measurement_manifest
    )

    # Preflight every caller pin before touching the packet directory.
    for step_index in range(len(_STEP_SPECS)):
        _measure_and_match(expected_measurements, step_index)

    trace: list[dict[str, Any]] = []
    execution_measurements: list[dict[str, Any]] = []
    result_bindings: list[dict[str, Any]] = []
    previous_step_sha = "0" * 64
    caller_pinned_root_identity = {
        "final_path": expected_root_final_path,
        "volume_serial": str(expected_root_volume_serial),
        "file_id": expected_root_file_id,
    }
    execution_genesis = {
        "session_id": session,
        "run_id": run,
        "nonce_commitment_sha256": nonce,
        "expected_manifest_sha256": manifest_pin,
        "expected_origin": expected_origin,
        "caller_pinned_root_identity": caller_pinned_root_identity,
    }
    execution_genesis_sha256 = canonical_sha256(execution_genesis)

    before = _measure_and_match(expected_measurements, 0)
    observation = windows_identity.read_windows_fixed_p0_packet_directory(
        packet_dir,
        expected_root_final_path=expected_root_final_path,
        expected_root_volume_serial=expected_root_volume_serial,
        expected_root_file_id=expected_root_file_id,
    )
    after = _measure_and_match(expected_measurements, 0)
    raw_projection = _raw_member_projection(observation.raw_by_name)
    handle_binding = _verify_declared_receipt(
        observation.receipt,
        expected_schema=windows_identity.WINDOWS_HANDLE_RECEIPT_SCHEMA,
        label="Windows handle",
    )
    if observation.receipt.get("filesystem_handle_binding_verified") is not True or (
        observation.receipt.get("filesystem_handle_trust_verified") is not False
    ):
        raise P0ActualSupervisorExecutionError("Windows handle result scope mismatch")
    _verify_handle_receipt_cross_binding(
        observation.receipt,
        observation.raw_by_name,
        expected_root_final_path=expected_root_final_path,
        expected_root_volume_serial=expected_root_volume_serial,
        expected_root_file_id=expected_root_file_id,
    )
    step = _trace_row(
        step_index=0,
        previous_step_sha256=previous_step_sha,
        expected_measurement=expected_measurements["measurements"][0],
        before_measurement=before,
        after_measurement=after,
        input_binding=execution_genesis,
        result_binding=handle_binding,
    )
    trace.append(step)
    previous_step_sha = step["step_sha256"]
    execution_measurements.append(
        {"step_index": 0, "before": before, "after": after, "pinned_match": True}
    )
    result_bindings.append({"step_index": 0, **handle_binding})

    before = _measure_and_match(expected_measurements, 1)
    packet_receipt = packet_contract.validate_packet_bytes(
        observation.manifest_bytes,
        observation.child_bytes,
        expected_manifest_sha256=manifest_pin,
        expected_origin=expected_origin,
    )
    after = _measure_and_match(expected_measurements, 1)
    packet_binding = _verify_declared_receipt(
        packet_receipt,
        expected_schema=packet_contract.PACKET_RECEIPT_SCHEMA,
        label="packet",
    )
    step = _trace_row(
        step_index=1,
        previous_step_sha256=previous_step_sha,
        expected_measurement=expected_measurements["measurements"][1],
        before_measurement=before,
        after_measurement=after,
        input_binding={
            "raw_member_projection_sha256": canonical_sha256(raw_projection),
            "expected_manifest_sha256": manifest_pin,
            "expected_origin": expected_origin,
        },
        result_binding=packet_binding,
    )
    trace.append(step)
    previous_step_sha = step["step_sha256"]
    execution_measurements.append(
        {"step_index": 1, "before": before, "after": after, "pinned_match": True}
    )
    result_bindings.append({"step_index": 1, **packet_binding})

    before = _measure_and_match(expected_measurements, 2)
    composite_receipt = windows_identity.bind_windows_fixed_packet_observation(
        observation,
        expected_manifest_sha256=manifest_pin,
        expected_origin=expected_origin,
    )
    after = _measure_and_match(expected_measurements, 2)
    composite_binding = _verify_declared_receipt(
        composite_receipt,
        expected_schema=windows_identity.WINDOWS_PACKET_VALIDATION_RECEIPT_SCHEMA,
        label="Windows packet binding",
    )
    if composite_receipt.get("filesystem_handle_binding_verified") is not True or (
        composite_receipt.get("filesystem_handle_trust_verified") is not False
    ):
        raise P0ActualSupervisorExecutionError("Windows packet binding scope mismatch")
    if composite_receipt.get("packet_receipt_full_canonical_sha256") != packet_binding[
        "full_canonical_sha256"
    ]:
        raise P0ActualSupervisorExecutionError(
            "direct packet and composite packet results differ"
        )
    step = _trace_row(
        step_index=2,
        previous_step_sha256=previous_step_sha,
        expected_measurement=expected_measurements["measurements"][2],
        before_measurement=before,
        after_measurement=after,
        input_binding={
            "raw_member_projection_sha256": canonical_sha256(raw_projection),
            "handle_result_full_canonical_sha256": handle_binding[
                "full_canonical_sha256"
            ],
            "packet_result_full_canonical_sha256": packet_binding[
                "full_canonical_sha256"
            ],
        },
        result_binding=composite_binding,
    )
    trace.append(step)
    previous_step_sha = step["step_sha256"]
    execution_measurements.append(
        {"step_index": 2, "before": before, "after": after, "pinned_match": True}
    )
    result_bindings.append({"step_index": 2, **composite_binding})

    role_raw = {
        role: observation.raw_by_name[path]
        for role, path, _ in packet_contract.CHILD_FILES
    }
    derived_a_source_claim_bytes, a_claim_derivation = _derive_a_source_claim_subset(
        role_raw["source_claims"], role_raw["a_contexts"]
    )
    before = _measure_and_match(expected_measurements, 3)
    a_receipt = a_event_bytes.verify_a_event_bytes(
        source_claim_bytes=derived_a_source_claim_bytes,
        a_context_bytes=role_raw["a_contexts"],
        a_event_bytes=role_raw["a_annotation_events"],
        a_subject_selection_seal_bytes=role_raw["a_subject_selection_seal"],
        expected_origin=expected_origin,
    )
    after = _measure_and_match(expected_measurements, 3)
    a_binding = _verify_declared_receipt(
        a_receipt,
        expected_schema=a_event_bytes.A_EVENT_BYTES_RECEIPT_SCHEMA,
        label="A event bytes",
    )
    _verify_a_receipt_cross_binding(
        a_receipt,
        role_raw,
        derived_a_source_claim_bytes,
        a_claim_derivation,
        expected_origin=expected_origin,
    )
    a_input_projection = [
        member
        for member in raw_projection
        if member["role"]
        in {
            "source_claims",
            "a_contexts",
            "a_annotation_events",
            "a_subject_selection_seal",
        }
    ]
    step = _trace_row(
        step_index=3,
        previous_step_sha256=previous_step_sha,
        expected_measurement=expected_measurements["measurements"][3],
        before_measurement=before,
        after_measurement=after,
        input_binding={
            "a_handle_captured_raw_member_projection": a_input_projection,
            "a_source_claim_subset_derivation": a_claim_derivation,
        },
        result_binding=a_binding,
    )
    trace.append(step)
    previous_step_sha = step["step_sha256"]
    execution_measurements.append(
        {"step_index": 3, "before": before, "after": after, "pinned_match": True}
    )
    result_bindings.append({"step_index": 3, **a_binding})

    material = {
        "schema_version": SUPERVISOR_EXECUTION_RECEIPT_SCHEMA,
        "execution_scope": "DIRECT_PACKET_VALIDATOR_INVOCATIONS_ONLY",
        "session_id": session,
        "run_id": run,
        "nonce_commitment_sha256": nonce,
        "expected_manifest_sha256": manifest_pin,
        "expected_origin": expected_origin,
        "caller_pinned_root_identity": caller_pinned_root_identity,
        "execution_genesis": execution_genesis,
        "execution_genesis_sha256": execution_genesis_sha256,
        "expected_validator_measurement_manifest_artifact_sha256": expected_measurements[
            "artifact_sha256"
        ],
        "expected_validator_measurement_manifest_full_canonical_sha256": canonical_sha256(
            expected_measurements
        ),
        "execution_measurements": execution_measurements,
        "fixed_step_order": [name for _, name, _, _, _ in _STEP_SPECS],
        "step_trace": trace,
        "trace_head_sha256": previous_step_sha,
        "raw_member_count": len(raw_projection),
        "raw_member_projection": raw_projection,
        "raw_member_projection_sha256": canonical_sha256(raw_projection),
        "a_claim_subset_derivation": a_claim_derivation,
        "a_claim_subset_derivation_sha256": canonical_sha256(a_claim_derivation),
        "result_bindings": result_bindings,
        "result_bindings_sha256": canonical_sha256(result_bindings),
        "direct_packet_validator_invocations_completed": True,
        "presented_receipt_inputs_accepted": False,
        "packet_side_execution_trace_verified": True,
        "same_handle_captured_packet_inputs_with_derived_a_claim_subset_verified": True,
        "untrusted_local_execution_observation": True,
        "caller_self_measurement_only": True,
        "windows_handle_capture_execution_provenance_verified": False,
        "handles_held_across_validator_execution": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
        "credited_counts": {
            "actual_source_claim_count": 0,
            "actual_a_context_review_count": 0,
        },
        "operational_effect": "NONE_SHADOW_ONLY",
        "gate_status": "DIRECT_PACKET_EXECUTION_TRACE_PASS_EXTERNAL_TRUST_NO_GO",
        "receipt_hash_scope": "CANONICAL_MATERIAL_EXCLUDING_RECEIPT_SHA256",
    }
    public_receipt = {**material, "receipt_sha256": canonical_sha256(material)}
    frozen_projection = _freeze_snapshot(raw_projection)
    if not isinstance(frozen_projection, tuple):
        raise P0ActualSupervisorExecutionError(
            "internal raw member projection freeze failed"
        )
    return _PacketSupervisorState(
        raw_by_name=MappingProxyType(
            {name: bytes(raw) for name, raw in observation.raw_by_name.items()}
        ),
        raw_member_projection=frozen_projection,
        handle_receipt=_freeze_snapshot(observation.receipt),
        packet_receipt=_freeze_snapshot(packet_receipt),
        windows_packet_receipt=_freeze_snapshot(composite_receipt),
        a_event_receipt=_freeze_snapshot(a_receipt),
        public_receipt=_freeze_snapshot(public_receipt),
    )


def execute_packet_supervisor_trace(
    *,
    packet_dir: Path | str,
    expected_root_final_path: str,
    expected_root_volume_serial: int,
    expected_root_file_id: str,
    expected_manifest_sha256: str,
    expected_origin: str,
    session_id: str,
    run_id: str,
    nonce_commitment_sha256: str,
    expected_validator_measurement_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Directly execute packet validators and return a fresh ordinary receipt.

    The immutable raw/result state remains private for same-process authority
    integration.  Public callers receive only a deep, mutable copy of the
    unchanged v1 receipt and cannot inject a state or child receipt.
    """

    state = _execute_packet_supervisor_state(
        packet_dir=packet_dir,
        expected_root_final_path=expected_root_final_path,
        expected_root_volume_serial=expected_root_volume_serial,
        expected_root_file_id=expected_root_file_id,
        expected_manifest_sha256=expected_manifest_sha256,
        expected_origin=expected_origin,
        session_id=session_id,
        run_id=run_id,
        nonce_commitment_sha256=nonce_commitment_sha256,
        expected_validator_measurement_manifest=(
            expected_validator_measurement_manifest
        ),
    )
    receipt = _thaw_snapshot(state.public_receipt)
    if not isinstance(receipt, dict):
        raise P0ActualSupervisorExecutionError(
            "internal public receipt thaw failed"
        )
    return receipt


def _validate_execution_receipt_structure(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise P0ActualSupervisorExecutionError("supervisor receipt must be an object")
    row = dict(value)
    expected_fields = {
        "schema_version",
        "execution_scope",
        "session_id",
        "run_id",
        "nonce_commitment_sha256",
        "expected_manifest_sha256",
        "expected_origin",
        "caller_pinned_root_identity",
        "execution_genesis",
        "execution_genesis_sha256",
        "expected_validator_measurement_manifest_artifact_sha256",
        "expected_validator_measurement_manifest_full_canonical_sha256",
        "execution_measurements",
        "fixed_step_order",
        "step_trace",
        "trace_head_sha256",
        "raw_member_count",
        "raw_member_projection",
        "raw_member_projection_sha256",
        "a_claim_subset_derivation",
        "a_claim_subset_derivation_sha256",
        "result_bindings",
        "result_bindings_sha256",
        "direct_packet_validator_invocations_completed",
        "presented_receipt_inputs_accepted",
        "packet_side_execution_trace_verified",
        "same_handle_captured_packet_inputs_with_derived_a_claim_subset_verified",
        "untrusted_local_execution_observation",
        "caller_self_measurement_only",
        "windows_handle_capture_execution_provenance_verified",
        "handles_held_across_validator_execution",
        *_FALSE_AUTHORITY_FIELDS,
        "credited_counts",
        "operational_effect",
        "gate_status",
        "receipt_hash_scope",
        "receipt_sha256",
    }
    if set(row) != expected_fields:
        raise P0ActualSupervisorExecutionError("supervisor receipt fields mismatch")
    if row["schema_version"] != SUPERVISOR_EXECUTION_RECEIPT_SCHEMA or row[
        "execution_scope"
    ] != "DIRECT_PACKET_VALIDATOR_INVOCATIONS_ONLY":
        raise P0ActualSupervisorExecutionError("supervisor receipt scope/schema mismatch")
    if row["receipt_hash_scope"] != "CANONICAL_MATERIAL_EXCLUDING_RECEIPT_SHA256":
        raise P0ActualSupervisorExecutionError("supervisor receipt hash scope mismatch")
    stored = _sha(row["receipt_sha256"], "receipt_sha256")
    material = {key: item for key, item in row.items() if key != "receipt_sha256"}
    if stored != canonical_sha256(material):
        raise P0ActualSupervisorExecutionError("supervisor receipt self-hash mismatch")
    _identifier(row["session_id"], "session_id")
    _identifier(row["run_id"], "run_id")
    if row["expected_origin"] not in {
        packet_contract.ACTUAL_ORIGIN,
        packet_contract.EXAMPLE_ORIGIN,
    }:
        raise P0ActualSupervisorExecutionError("supervisor expected origin is invalid")
    root_identity = row["caller_pinned_root_identity"]
    if not isinstance(root_identity, Mapping) or set(root_identity) != {
        "final_path",
        "volume_serial",
        "file_id",
    }:
        raise P0ActualSupervisorExecutionError("caller-pinned root identity is malformed")
    if not isinstance(root_identity["final_path"], str) or not root_identity["final_path"]:
        raise P0ActualSupervisorExecutionError("caller-pinned root final path is invalid")
    if (
        not isinstance(root_identity["volume_serial"], str)
        or not root_identity["volume_serial"].isdigit()
        or not 0 <= int(root_identity["volume_serial"]) <= (2**64 - 1)
        or not isinstance(root_identity["file_id"], str)
        or not _FILE_ID.fullmatch(root_identity["file_id"])
    ):
        raise P0ActualSupervisorExecutionError("caller-pinned root tuple is invalid")
    execution_genesis = row["execution_genesis"]
    expected_genesis = {
        "session_id": row["session_id"],
        "run_id": row["run_id"],
        "nonce_commitment_sha256": row["nonce_commitment_sha256"],
        "expected_manifest_sha256": row["expected_manifest_sha256"],
        "expected_origin": row["expected_origin"],
        "caller_pinned_root_identity": dict(root_identity),
    }
    if (
        not isinstance(execution_genesis, Mapping)
        or set(execution_genesis) != set(expected_genesis)
        or dict(execution_genesis) != expected_genesis
        or canonical_sha256(execution_genesis) != row["execution_genesis_sha256"]
    ):
        raise P0ActualSupervisorExecutionError("execution genesis binding mismatch")
    for field in (
        "nonce_commitment_sha256",
        "expected_manifest_sha256",
        "expected_validator_measurement_manifest_artifact_sha256",
        "expected_validator_measurement_manifest_full_canonical_sha256",
        "trace_head_sha256",
        "raw_member_projection_sha256",
        "a_claim_subset_derivation_sha256",
        "result_bindings_sha256",
        "execution_genesis_sha256",
    ):
        _sha(row[field], field)
    if row["fixed_step_order"] != [name for _, name, _, _, _ in _STEP_SPECS]:
        raise P0ActualSupervisorExecutionError("supervisor step order mismatch")
    if row["direct_packet_validator_invocations_completed"] is not True or row[
        "packet_side_execution_trace_verified"
    ] is not True or row[
        "same_handle_captured_packet_inputs_with_derived_a_claim_subset_verified"
    ] is not True or row["presented_receipt_inputs_accepted"] is not False:
        raise P0ActualSupervisorExecutionError("supervisor execution flags mismatch")
    if (
        row["untrusted_local_execution_observation"] is not True
        or row["caller_self_measurement_only"] is not True
        or row["windows_handle_capture_execution_provenance_verified"] is not False
        or row["handles_held_across_validator_execution"] is not False
    ):
        raise P0ActualSupervisorExecutionError(
            "supervisor local execution trust boundary mismatch"
        )
    if any(row[field] is not False for field in _FALSE_AUTHORITY_FIELDS):
        raise P0ActualSupervisorExecutionError("supervisor authority boundary violated")
    if row["credited_counts"] != {
        "actual_source_claim_count": 0,
        "actual_a_context_review_count": 0,
    }:
        raise P0ActualSupervisorExecutionError("supervisor credited counts must remain zero")
    if row["operational_effect"] != "NONE_SHADOW_ONLY" or row[
        "gate_status"
    ] != "DIRECT_PACKET_EXECUTION_TRACE_PASS_EXTERNAL_TRUST_NO_GO":
        raise P0ActualSupervisorExecutionError("supervisor gate boundary mismatch")

    projection = row["raw_member_projection"]
    if (
        not isinstance(projection, list)
        or len(projection) != row["raw_member_count"]
        or row["raw_member_count"] != 1 + len(packet_contract.CHILD_FILES)
    ):
        raise P0ActualSupervisorExecutionError("supervisor raw member count mismatch")
    expected_projection_identity = [
        (0, "packet_manifest", packet_contract.PACKET_MANIFEST_FILENAME),
        *[
            (index, role, path)
            for index, (role, path, _) in enumerate(
                packet_contract.CHILD_FILES, start=1
            )
        ],
    ]
    projection_fields = {"index", "role", "path", "bytes", "sha256"}
    for member, expected_identity in zip(projection, expected_projection_identity):
        if (
            not isinstance(member, Mapping)
            or set(member) != projection_fields
            or (member["index"], member["role"], member["path"])
            != expected_identity
            or not isinstance(member["bytes"], int)
            or isinstance(member["bytes"], bool)
            or member["bytes"] < 0
        ):
            raise P0ActualSupervisorExecutionError(
                "raw member projection identity/shape mismatch"
            )
        _sha(member["sha256"], "raw member sha256")
    if canonical_sha256(projection) != row["raw_member_projection_sha256"]:
        raise P0ActualSupervisorExecutionError("raw member projection hash mismatch")
    derivation = row["a_claim_subset_derivation"]
    derivation_fields = {
        "handle_captured_full_source_claim_file_sha256",
        "handle_captured_full_source_claim_row_count",
        "handle_captured_total_track_a_claim_count",
        "selected_source_claim_ids",
        "selected_source_claim_ids_sha256",
        "selected_source_claim_id_count",
        "unselected_packet_track_a_claim_count",
        "unselected_packet_track_a_claim_ids_sha256",
        "derived_a_source_claim_row_count",
        "derived_a_source_claim_jsonl_sha256",
        "selection_rule",
        "full_source_claim_rows_canonical_json_verified",
        "derived_subset_duplicate_missing_non_track_a_or_unreferenced_rows_rejected",
    }
    if not isinstance(derivation, Mapping) or set(derivation) != derivation_fields:
        raise P0ActualSupervisorExecutionError("A claim subset derivation shape mismatch")
    for field in (
        "handle_captured_full_source_claim_file_sha256",
        "selected_source_claim_ids_sha256",
        "unselected_packet_track_a_claim_ids_sha256",
        "derived_a_source_claim_jsonl_sha256",
    ):
        _sha(derivation[field], field)
    selected_ids = derivation["selected_source_claim_ids"]
    integer_fields = (
        "handle_captured_full_source_claim_row_count",
        "handle_captured_total_track_a_claim_count",
        "selected_source_claim_id_count",
        "unselected_packet_track_a_claim_count",
        "derived_a_source_claim_row_count",
    )
    if any(
        not isinstance(derivation[field], int)
        or isinstance(derivation[field], bool)
        or derivation[field] < 0
        for field in integer_fields
    ):
        raise P0ActualSupervisorExecutionError("A claim subset counts are invalid")
    if (
        not isinstance(selected_ids, list)
        or selected_ids != sorted(set(selected_ids))
        or any(not isinstance(value, str) or not value for value in selected_ids)
        or len(selected_ids) != derivation["selected_source_claim_id_count"]
        or canonical_sha256(selected_ids)
        != derivation["selected_source_claim_ids_sha256"]
        or derivation["selected_source_claim_id_count"]
        != derivation["derived_a_source_claim_row_count"]
        or derivation["handle_captured_total_track_a_claim_count"]
        != derivation["selected_source_claim_id_count"]
        + derivation["unselected_packet_track_a_claim_count"]
        or derivation["handle_captured_full_source_claim_row_count"]
        < derivation["handle_captured_total_track_a_claim_count"]
        or derivation["selection_rule"]
        != "A_CONTEXT_SOURCE_CLAIM_ID_UNION_EXACT_TRACK_A"
        or derivation["full_source_claim_rows_canonical_json_verified"] is not True
        or derivation[
            "derived_subset_duplicate_missing_non_track_a_or_unreferenced_rows_rejected"
        ]
        is not True
    ):
        raise P0ActualSupervisorExecutionError("A claim subset derivation mismatch")
    if canonical_sha256(derivation) != row["a_claim_subset_derivation_sha256"]:
        raise P0ActualSupervisorExecutionError("A claim subset derivation hash mismatch")
    source_claim_member = next(
        member for member in projection if member["role"] == "source_claims"
    )
    if source_claim_member["sha256"] != derivation[
        "handle_captured_full_source_claim_file_sha256"
    ]:
        raise P0ActualSupervisorExecutionError(
            "A claim derivation/full source member binding mismatch"
        )
    result_bindings = row["result_bindings"]
    if not isinstance(result_bindings, list) or len(result_bindings) != len(_STEP_SPECS):
        raise P0ActualSupervisorExecutionError("result binding count mismatch")
    if canonical_sha256(result_bindings) != row["result_bindings_sha256"]:
        raise P0ActualSupervisorExecutionError("result bindings hash mismatch")

    binding_fields = {
        "step_index",
        "schema_version",
        "declared_receipt_sha256",
        "full_canonical_sha256",
    }
    for index, binding in enumerate(result_bindings):
        if (
            not isinstance(binding, Mapping)
            or set(binding) != binding_fields
            or binding["step_index"] != index
            or binding["schema_version"] != _STEP_SPECS[index][4]
        ):
            raise P0ActualSupervisorExecutionError("result binding shape/schema mismatch")
        _sha(binding["declared_receipt_sha256"], "declared receipt sha256")
        _sha(binding["full_canonical_sha256"], "full receipt sha256")

    execution_measurements = row["execution_measurements"]
    if not isinstance(execution_measurements, list) or len(execution_measurements) != len(
        _STEP_SPECS
    ):
        raise P0ActualSupervisorExecutionError("execution measurement count mismatch")
    measured_rows: list[Mapping[str, Any]] = []
    for index, measurement in enumerate(execution_measurements):
        if (
            not isinstance(measurement, Mapping)
            or set(measurement) != {"step_index", "before", "after", "pinned_match"}
            or measurement["step_index"] != index
            or measurement["pinned_match"] is not True
            or not isinstance(measurement["before"], Mapping)
            or measurement["before"] != measurement["after"]
        ):
            raise P0ActualSupervisorExecutionError("execution measurement shape mismatch")
        measured_rows.append(measurement["before"])
    reconstructed_measurement_material = {
        "schema_version": VALIDATOR_MEASUREMENT_MANIFEST_SCHEMA,
        "measurement_scope": "LOCAL_SELF_MEASUREMENT_NOT_EXTERNAL_AUTHORITY",
        "measurements": measured_rows,
        "external_code_authority_verified": False,
        "supervisor_runtime_trust_verified": False,
    }
    reconstructed_measurement_manifest = {
        **reconstructed_measurement_material,
        "artifact_sha256": canonical_sha256(reconstructed_measurement_material),
    }
    if (
        reconstructed_measurement_manifest["artifact_sha256"]
        != row["expected_validator_measurement_manifest_artifact_sha256"]
        or canonical_sha256(reconstructed_measurement_manifest)
        != row["expected_validator_measurement_manifest_full_canonical_sha256"]
    ):
        raise P0ActualSupervisorExecutionError(
            "execution measurements do not match pinned manifest hashes"
        )
    trace = row["step_trace"]
    if not isinstance(trace, list) or len(trace) != len(_STEP_SPECS):
        raise P0ActualSupervisorExecutionError("step trace count mismatch")
    previous = "0" * 64
    for index, (step, result_binding, measurement) in enumerate(
        zip(trace, result_bindings, execution_measurements)
    ):
        if not isinstance(step, Mapping):
            raise P0ActualSupervisorExecutionError("step trace row must be an object")
        expected_step_fields = {
            "step_index",
            "step_name",
            "previous_step_sha256",
            "expected_measurement_sha256",
            "before_measurement_sha256",
            "after_measurement_sha256",
            "input_binding_sha256",
            "output_schema_version",
            "output_declared_receipt_sha256",
            "output_full_canonical_sha256",
            "output_binding_sha256",
            "step_sha256",
        }
        if set(step) != expected_step_fields:
            raise P0ActualSupervisorExecutionError("step trace row fields mismatch")
        if (
            step["step_index"] != index
            or step["step_name"] != _STEP_SPECS[index][1]
            or step["previous_step_sha256"] != previous
            or result_binding.get("step_index") != index
            or measurement.get("step_index") != index
            or measurement.get("pinned_match") is not True
        ):
            raise P0ActualSupervisorExecutionError("step trace ordering/binding mismatch")
        if index == 0 and step["input_binding_sha256"] != row[
            "execution_genesis_sha256"
        ]:
            raise P0ActualSupervisorExecutionError(
                "step zero/execution genesis binding mismatch"
            )
        if measurement.get("before") != measurement.get("after"):
            raise P0ActualSupervisorExecutionError("validator measurement changed during call")
        if canonical_sha256(measurement["before"]) != step[
            "before_measurement_sha256"
        ] or step["before_measurement_sha256"] != step["after_measurement_sha256"] or (
            step["expected_measurement_sha256"]
            != step["before_measurement_sha256"]
        ):
            raise P0ActualSupervisorExecutionError("step measurement hash mismatch")
        expected_result = {
            key: item for key, item in result_binding.items() if key != "step_index"
        }
        if (
            step["output_schema_version"] != expected_result["schema_version"]
            or step["output_declared_receipt_sha256"]
            != expected_result["declared_receipt_sha256"]
            or step["output_full_canonical_sha256"]
            != expected_result["full_canonical_sha256"]
            or step["output_binding_sha256"] != canonical_sha256(expected_result)
        ):
            raise P0ActualSupervisorExecutionError("step result binding mismatch")
        declared = dict(step)
        step_sha = _sha(declared.pop("step_sha256"), "step_sha256")
        if step_sha != canonical_sha256(declared):
            raise P0ActualSupervisorExecutionError("step hash mismatch")
        previous = step_sha
    if previous != row["trace_head_sha256"]:
        raise P0ActualSupervisorExecutionError("step trace head mismatch")
    return row


def validate_presented_packet_supervisor_receipt(value: Any) -> dict[str, Any]:
    """Validate only a presented receipt's structure, never its execution truth."""

    source = _validate_execution_receipt_structure(value)
    material = {
        "schema_version": PRESENTED_RECEIPT_VALIDATION_SCHEMA,
        "validation_scope": "PRESENTED_SUPERVISOR_RECEIPT_ONLY",
        "presented_supervisor_receipt_declared_sha256": source["receipt_sha256"],
        "presented_supervisor_receipt_full_canonical_sha256": canonical_sha256(source),
        "presented_receipt_structurally_verified": True,
        "direct_packet_validator_invocations_completed": False,
        "packet_side_execution_trace_verified": False,
        "underlying_validator_execution_verified": False,
        "untrusted_local_execution_observation": True,
        "caller_self_measurement_only": True,
        "windows_handle_capture_execution_provenance_verified": False,
        "handles_held_across_validator_execution": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
        "credited_counts": {
            "actual_source_claim_count": 0,
            "actual_a_context_review_count": 0,
        },
        "operational_effect": "NONE_SHADOW_ONLY",
        "gate_status": "PRESENTED_SUPERVISOR_RECEIPT_ONLY_EXTERNAL_TRUST_NO_GO",
    }
    return {**material, "receipt_sha256": canonical_sha256(material)}


__all__ = [
    "P0ActualSupervisorExecutionError",
    "PRESENTED_RECEIPT_VALIDATION_SCHEMA",
    "SUPERVISOR_EXECUTION_RECEIPT_SCHEMA",
    "VALIDATOR_MEASUREMENT_MANIFEST_SCHEMA",
    "build_local_packet_validator_measurement_manifest",
    "execute_packet_supervisor_trace",
    "validate_presented_packet_supervisor_receipt",
]
