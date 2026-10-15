"""Combined direct local supervisor for the actual-P0 packet/authority bridge.

The public executor accepts source bytes, roots, pins, and a caller-presented
key.  It never accepts serialized child validator receipts or private states.
Every child validator is invoked in the same call and only its in-process
result is passed to the final bridge.  This is still an untrusted local
observation: external owner/code/root trust, replay protection, OS write deny,
runtime noninterference, credit, and every operational gate remain false.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import marshal
from pathlib import Path
import re
from types import ModuleType
from typing import Any, Mapping

from llm_batch.grounding import p0_actual_authority_bridge_contract as bridge
from llm_batch.grounding import p0_actual_authority_contract as authority
from llm_batch.grounding import p0_actual_authority_raw_execution as authority_raw
from llm_batch.grounding import p0_actual_owner_root_preauthorization as preauth
from llm_batch.grounding import p0_actual_packet_contract as packet
from llm_batch.grounding import p0_actual_supervisor_execution_contract as packet_supervisor


COMBINED_EXECUTION_SCHEMA = "p0_actual_authority_supervisor_execution_receipt_v1"
PRESENTED_VALIDATION_SCHEMA = (
    "p0_actual_authority_supervisor_presented_validation_v1"
)
MEASUREMENT_MANIFEST_SCHEMA = (
    "p0_actual_authority_supervisor_validator_measurement_manifest_v1"
)
EXECUTION_SCOPE = "DIRECT_PACKET_AND_AUTHORITY_VALIDATOR_INVOCATIONS_ONLY"
GATE_STATUS = "DIRECT_LOCAL_AUTHORITY_BRIDGE_PASS_EXTERNAL_TRUST_NO_GO"
PRESENTED_GATE_STATUS = "PRESENTED_COMBINED_RECEIPT_ONLY_EXTERNAL_TRUST_NO_GO"
NONCE_COMMITMENT_DOMAIN = "p0-actual-owner-root-preauthorization-nonce-v1"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")
_FILE_ID = re.compile(r"^[0-9a-f]{32}$")

_FALSE_FIELDS = (
    "underlying_validator_execution_verified",
    "external_code_authority_verified",
    "supervisor_runtime_trust_verified",
    "external_owner_trust_verified",
    "trusted_time_verified",
    "external_trust_store_verified",
    "revocation_current_verified",
    "external_root_identity_pin_verified",
    "filesystem_handle_binding_verified",
    "filesystem_handle_trust_verified",
    "windows_handle_capture_execution_provenance_verified",
    "handles_held_across_validator_execution",
    "nonce_uniqueness_verified",
    "single_use_replay_consumed",
    "os_write_deny_verified",
    "continuous_watch_verified",
    "authority_journal_watch_bundle_verified",
    "runtime_noninterference_verified",
    "parser_runtime_execution_verified",
    "durable_predecessor_verified",
    "annotation_append_only_verified",
    "actual_semantic_evidence_verified",
    "owner_authority_verified",
    "actual_authority_granted",
    "production_approval",
    "full_scan_approval",
    "p0_phase_exit",
    "action_applied",
)

_FIXED_STEP_ORDER = (
    "VALIDATE_OWNER_ROOT_PREAUTHORIZATION_RAW",
    "EXECUTE_PACKET_SUPERVISOR_PRIVATE_STATE",
    "EXECUTE_AUTHORITY_RAW_PRIVATE_STATE",
    "VERIFY_PARSER_RECEIPT_BYTE_AND_SEMANTIC_BINDING",
    "VALIDATE_PARSER_PROVENANCE_RAW",
    "VALIDATE_TERMINAL_BRIDGE_ATTESTATION_RAW",
    "EXECUTE_FINAL_AUTHORITY_BRIDGE",
)


class P0ActualAuthoritySupervisorError(ValueError):
    """Raised when the combined local execution cannot remain fail-closed."""


def _json_plain(value: Any) -> Any:
    """Detach immutable private state into ordinary JSON-compatible values."""

    if isinstance(value, Mapping):
        return {key: _json_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_plain(item) for item in value]
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _json_plain(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def json_file_bytes(value: Any) -> bytes:
    return canonical_bytes(value) + b"\n"


def nonce_commitment_sha256(nonce: str) -> str:
    if not isinstance(nonce, str) or not nonce or nonce != nonce.strip():
        raise P0ActualAuthoritySupervisorError("preauthorization nonce is invalid")
    return canonical_sha256(
        {"domain": NONCE_COMMITMENT_DOMAIN, "nonce": nonce}
    )


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise P0ActualAuthoritySupervisorError(f"{field} must be lowercase sha256")
    return value


def _identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise P0ActualAuthoritySupervisorError(f"{field} is invalid")
    return value


def _duplicate_rejecting_object(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P0ActualAuthoritySupervisorError(
                f"duplicate JSON key is forbidden: {key}"
            )
        result[key] = value
    return result


def _reject_nonfinite(token: str) -> None:
    raise P0ActualAuthoritySupervisorError(
        f"non-finite JSON constant is forbidden: {token}"
    )


def _parse_canonical_json_object(raw: Any, label: str) -> dict[str, Any]:
    if type(raw) is not bytes:
        raise P0ActualAuthoritySupervisorError(f"{label} must be exact bytes")
    if not raw or raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise P0ActualAuthoritySupervisorError(f"{label} framing is invalid")
    if not raw.endswith(b"\n"):
        raise P0ActualAuthoritySupervisorError(f"{label} requires final LF")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=_reject_nonfinite,
        )
    except P0ActualAuthoritySupervisorError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise P0ActualAuthoritySupervisorError(
            f"{label} must be strict UTF-8 JSON"
        ) from exc
    if not isinstance(value, dict):
        raise P0ActualAuthoritySupervisorError(f"{label} must be an object")
    try:
        expected = json_file_bytes(value)
    except (TypeError, ValueError) as exc:
        raise P0ActualAuthoritySupervisorError(
            f"{label} cannot be canonicalized"
        ) from exc
    if raw != expected:
        raise P0ActualAuthoritySupervisorError(
            f"{label} must use canonical JSON bytes"
        )
    return value


def _module_source_sha256(module: ModuleType) -> str:
    source = getattr(module, "__file__", None)
    if not isinstance(source, str):
        raise P0ActualAuthoritySupervisorError("validator module lacks source path")
    return hashlib.sha256(Path(source).read_bytes()).hexdigest()


def _callable_code_sha256(value: Any, label: str) -> str:
    code = getattr(value, "__code__", None)
    if code is None:
        raise P0ActualAuthoritySupervisorError(f"callable lacks code object: {label}")
    return canonical_sha256(
        {
            "code_marshaled_sha256": hashlib.sha256(marshal.dumps(code)).hexdigest(),
            "defaults_sha256": canonical_sha256(repr(getattr(value, "__defaults__", None))),
            "kwdefaults_sha256": canonical_sha256(
                repr(getattr(value, "__kwdefaults__", None))
            ),
        }
    )


def _measurement_specs() -> tuple[tuple[str, ModuleType, str], ...]:
    return (
        (_FIXED_STEP_ORDER[0], preauth, "validate_owner_root_preauthorization"),
        (_FIXED_STEP_ORDER[1], packet_supervisor, "_execute_packet_supervisor_state"),
        (_FIXED_STEP_ORDER[2], authority_raw, "_execute_authority_raw_validation_state"),
        (_FIXED_STEP_ORDER[3], __import__(__name__, fromlist=["x"]), "_verify_parser_binding"),
        (_FIXED_STEP_ORDER[4], bridge, "validate_parser_provenance_authorization"),
        (_FIXED_STEP_ORDER[5], bridge, "validate_terminal_bridge_attestation"),
        (_FIXED_STEP_ORDER[6], bridge, "validate_authority_bridge_bundle"),
    )


def _measurement(index: int) -> dict[str, Any]:
    step_name, module, callable_name = _measurement_specs()[index]
    target = getattr(module, callable_name, None)
    if not callable(target):
        raise P0ActualAuthoritySupervisorError(
            f"validator callable unavailable: {module.__name__}.{callable_name}"
        )
    return {
        "step_index": index,
        "step_name": step_name,
        "module_name": module.__name__,
        "callable_name": callable_name,
        "module_source_sha256": _module_source_sha256(module),
        "callable_code_sha256": _callable_code_sha256(target, callable_name),
    }


def build_local_authority_supervisor_measurement_manifest() -> dict[str, Any]:
    rows = [_measurement(index) for index in range(len(_FIXED_STEP_ORDER))]
    material = {
        "schema_version": MEASUREMENT_MANIFEST_SCHEMA,
        "measurement_scope": "LOCAL_SELF_MEASUREMENT_NOT_EXTERNAL_AUTHORITY",
        "measurements": rows,
        "external_code_authority_verified": False,
        "supervisor_runtime_trust_verified": False,
    }
    return {**material, "artifact_sha256": canonical_sha256(material)}


def _validate_measurement_manifest(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise P0ActualAuthoritySupervisorError("measurement manifest must be object")
    row = dict(value)
    fields = {
        "schema_version",
        "measurement_scope",
        "measurements",
        "external_code_authority_verified",
        "supervisor_runtime_trust_verified",
        "artifact_sha256",
    }
    if set(row) != fields or row["schema_version"] != MEASUREMENT_MANIFEST_SCHEMA:
        raise P0ActualAuthoritySupervisorError("measurement manifest shape mismatch")
    if row["measurement_scope"] != "LOCAL_SELF_MEASUREMENT_NOT_EXTERNAL_AUTHORITY":
        raise P0ActualAuthoritySupervisorError("measurement scope mismatch")
    if row["external_code_authority_verified"] is not False or row[
        "supervisor_runtime_trust_verified"
    ] is not False:
        raise P0ActualAuthoritySupervisorError("measurement trust overclaim")
    stored = _sha(row["artifact_sha256"], "measurement artifact_sha256")
    if stored != canonical_sha256(
        {key: item for key, item in row.items() if key != "artifact_sha256"}
    ):
        raise P0ActualAuthoritySupervisorError("measurement self-hash mismatch")
    values = row["measurements"]
    if not isinstance(values, list) or len(values) != len(_FIXED_STEP_ORDER):
        raise P0ActualAuthoritySupervisorError("measurement count mismatch")
    for index, item in enumerate(values):
        if item != _measurement(index):
            raise P0ActualAuthoritySupervisorError(
                f"caller-pinned combined validator measurement mismatch at step {index}"
            )
    return json.loads(canonical_bytes(row))


def _measure_and_match(manifest: Mapping[str, Any], index: int) -> dict[str, Any]:
    measured = _measurement(index)
    if measured != manifest["measurements"][index]:
        raise P0ActualAuthoritySupervisorError(
            f"combined validator measurement changed at step {index}"
        )
    return measured


def _receipt_binding(value: Mapping[str, Any], label: str) -> dict[str, Any]:
    row = _json_plain(value)
    stored = _sha(row.get("receipt_sha256"), f"{label}.receipt_sha256")
    if stored != canonical_sha256(
        {key: item for key, item in row.items() if key != "receipt_sha256"}
    ):
        raise P0ActualAuthoritySupervisorError(f"{label} self-hash mismatch")
    return {
        "schema_version": row.get("schema_version"),
        "declared_receipt_sha256": stored,
        "full_canonical_sha256": canonical_sha256(row),
    }


def _artifact_binding(value: Mapping[str, Any], label: str) -> dict[str, Any]:
    row = _json_plain(value)
    stored = _sha(row.get("artifact_sha256"), f"{label}.artifact_sha256")
    if stored != canonical_sha256(
        {key: item for key, item in row.items() if key != "artifact_sha256"}
    ):
        raise P0ActualAuthoritySupervisorError(f"{label} self-hash mismatch")
    return {
        "schema_version": row.get("schema_version"),
        "artifact_sha256": stored,
        "full_canonical_sha256": canonical_sha256(row),
    }


def _reject_child_overclaim(value: Any, label: str) -> None:
    """Reject authority truth hidden anywhere in a direct child result."""

    forbidden_true = {
        "underlying_validator_execution_verified",
        "external_code_authority_verified",
        "supervisor_runtime_trust_verified",
        "external_owner_trust_verified",
        "external_owner_authority_verified",
        "trusted_time_verified",
        "external_trust_store_verified",
        "revocation_current_verified",
        "external_root_identity_pin_verified",
        "filesystem_handle_trust_verified",
        "windows_handle_capture_execution_provenance_verified",
        "handles_held_across_validator_execution",
        "nonce_uniqueness_verified",
        "single_use_replay_consumed",
        "os_write_deny_verified",
        "continuous_watch_verified",
        "authority_journal_watch_bundle_verified",
        "runtime_noninterference_verified",
        "parser_runtime_execution_verified",
        "durable_predecessor_verified",
        "annotation_append_only_verified",
        "actual_semantic_evidence_verified",
        "owner_authority_verified",
        "actual_authority_granted",
        "production_approval",
        "full_scan_approval",
        "p0_phase_exit",
        "action_applied",
    }

    def walk(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                if key in forbidden_true and child is True:
                    raise P0ActualAuthoritySupervisorError(
                        f"{label} nested authority overclaim: {key}"
                    )
                if key == "credited_counts" and child != {
                    "actual_source_claim_count": 0,
                    "actual_a_context_review_count": 0,
                }:
                    raise P0ActualAuthoritySupervisorError(
                        f"{label} nested credit overclaim"
                    )
                if key in {
                    "credited_actual_source_claim_count",
                    "credited_actual_a_context_review_count",
                } and child != 0:
                    raise P0ActualAuthoritySupervisorError(
                        f"{label} nested credit overclaim: {key}"
                    )
                if key == "gate_status" and isinstance(child, str) and child.startswith(
                    "GO"
                ):
                    raise P0ActualAuthoritySupervisorError(
                        f"{label} nested GO overclaim"
                    )
                walk(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                walk(child)

    walk(value)


def _packet_json(state: Any, filename: str, label: str) -> dict[str, Any]:
    try:
        raw = state.raw_by_name[filename]
    except (KeyError, TypeError) as exc:
        raise P0ActualAuthoritySupervisorError(
            f"packet private state lacks {label} raw bytes"
        ) from exc
    return _parse_canonical_json_object(raw, label)


def _verify_parser_binding(
    *,
    packet_state: Any,
    authority_state: Any,
) -> dict[str, Any]:
    packet_name = "parser_receipt.json"
    authority_name = authority.AUTHORITY_EXAMPLE_FILES_V2["parser_receipt"]
    packet_raw = packet_state.raw_by_name[packet_name]
    authority_raw_bytes = authority_state.raw_by_filename[authority_name]
    if type(packet_raw) is not bytes or type(authority_raw_bytes) is not bytes:
        raise P0ActualAuthoritySupervisorError("parser receipt inputs must be bytes")
    packet_sha = hashlib.sha256(packet_raw).hexdigest()
    authority_sha = hashlib.sha256(authority_raw_bytes).hexdigest()
    packet_row = _parse_canonical_json_object(packet_raw, "packet parser receipt")
    authority_row = dict(authority_state.parsed_rows["parser_receipt"])
    if packet_raw != authority_raw_bytes or packet_sha != authority_sha:
        raise P0ActualAuthoritySupervisorError(
            "packet/authority parser receipt byte-exact binding mismatch"
        )
    if packet_row != authority_row:
        raise P0ActualAuthoritySupervisorError(
            "packet/authority parser receipt semantic binding mismatch"
        )
    artifact_sha = _sha(packet_row.get("artifact_sha256"), "parser artifact_sha256")
    if artifact_sha != authority_row.get("artifact_sha256") or artifact_sha != packet_state.packet_receipt.get(
        "parser_receipt_sha256"
    ):
        raise P0ActualAuthoritySupervisorError(
            "parser receipt artifact projection mismatch"
        )
    return {
        "packet_parser_receipt_raw_sha256": packet_sha,
        "authority_parser_receipt_raw_sha256": authority_sha,
        "parser_receipt_artifact_sha256": artifact_sha,
        "parser_receipt_byte_exact_cross_binding_verified": True,
        "parser_receipt_semantic_cross_binding_verified": True,
    }


def _trace_row(
    *,
    index: int,
    previous: str,
    measurement: Mapping[str, Any],
    input_binding: Any,
    output_binding: Mapping[str, Any],
) -> dict[str, Any]:
    material = {
        "step_index": index,
        "step_name": _FIXED_STEP_ORDER[index],
        "previous_step_sha256": previous,
        "measurement_sha256": canonical_sha256(measurement),
        "input_binding_sha256": canonical_sha256(input_binding),
        "output_binding": dict(output_binding),
        "output_binding_sha256": canonical_sha256(output_binding),
    }
    return {**material, "step_sha256": canonical_sha256(material)}


def _reject_bridge_overclaim(value: Mapping[str, Any]) -> None:
    if value.get("schema_version") != bridge.BRIDGE_RECEIPT_SCHEMA:
        raise P0ActualAuthoritySupervisorError("bridge result schema mismatch")
    _receipt_binding(value, "bridge result")
    required_false = (
        "underlying_validator_execution_verified",
        "external_anchor_trust_verified",
        "external_root_identity_pin_verified",
        "filesystem_handle_trust_verified",
        "os_write_deny_verified",
        "runtime_noninterference_verified",
        "owner_authority_verified",
        "actual_authority_granted",
        "production_approval",
        "full_scan_approval",
        "p0_phase_exit",
        "action_applied",
    )
    if any(value.get(field) is not False for field in required_false):
        raise P0ActualAuthoritySupervisorError("bridge result authority overclaim")
    if value.get("credited_counts") != {
        "actual_source_claim_count": 0,
        "actual_a_context_review_count": 0,
    } or value.get("gate_status") != "NO_GO_ACTUAL_P0_AUTHORITY_NOT_VERIFIED":
        raise P0ActualAuthoritySupervisorError("bridge result gate/credit overclaim")


def execute_authority_supervisor_trace(
    *,
    packet_dir: Path | str,
    expected_packet_root_final_path: str,
    expected_packet_root_volume_serial: int,
    expected_packet_root_file_id: str,
    expected_packet_manifest_sha256: str,
    authority_raw_by_filename: Mapping[str, bytes],
    annotation_event_bytes: bytes,
    owner_root_preauthorization_bytes: bytes,
    parser_provenance_authorization_bytes: bytes,
    terminal_bridge_attestation_bytes: bytes,
    expected_authority_origin: str,
    expected_packet_origin: str,
    expected_event_origin: str,
    foundation_manifest_sha256: str,
    foundation_receipt_sha256: str,
    session_id: str,
    run_id: str,
    nonce_commitment_sha256: str,
    expected_packet_validator_measurement_manifest: Mapping[str, Any],
    expected_combined_validator_measurement_manifest: Mapping[str, Any],
    key: bytes | None = None,
) -> dict[str, Any]:
    """Run every packet/authority/bridge validator in one local call."""

    session = _identifier(session_id, "session_id")
    run = _identifier(run_id, "run_id")
    nonce_pin = _sha(nonce_commitment_sha256, "nonce_commitment_sha256")
    manifest_pin = _sha(expected_packet_manifest_sha256, "expected_packet_manifest_sha256")
    foundation_manifest_pin = _sha(foundation_manifest_sha256, "foundation_manifest_sha256")
    foundation_receipt_pin = _sha(foundation_receipt_sha256, "foundation_receipt_sha256")
    if type(key) is not bytes or len(key) < 32:
        raise P0ActualAuthoritySupervisorError("combined actual executor requires key bytes")
    if not isinstance(authority_raw_by_filename, Mapping):
        raise P0ActualAuthoritySupervisorError("authority raw inventory must be mapping")
    raw_snapshot = dict(authority_raw_by_filename)
    for label, raw in (
        ("owner root preauthorization", owner_root_preauthorization_bytes),
        ("parser provenance authorization", parser_provenance_authorization_bytes),
        ("terminal bridge attestation", terminal_bridge_attestation_bytes),
    ):
        if type(raw) is not bytes:
            raise P0ActualAuthoritySupervisorError(f"{label} must be exact bytes")
    combined_measurements = _validate_measurement_manifest(
        expected_combined_validator_measurement_manifest
    )

    authority_projection = [
        {
            "role": role,
            "path": path,
            "bytes": len(raw_snapshot[path]),
            "sha256": hashlib.sha256(raw_snapshot[path]).hexdigest(),
        }
        for role, path in authority_raw.AUTHORITY_FILE_ROLES
        if path in raw_snapshot and type(raw_snapshot[path]) is bytes
    ]
    if len(authority_projection) != authority_raw.AUTHORITY_FILE_COUNT or set(
        raw_snapshot
    ) != {path for _, path in authority_raw.AUTHORITY_FILE_ROLES}:
        raise P0ActualAuthoritySupervisorError("authority raw inventory mismatch")
    supplemental_projection = {
        "owner_root_preauthorization_bytes_sha256": hashlib.sha256(
            owner_root_preauthorization_bytes
        ).hexdigest(),
        "parser_provenance_authorization_bytes_sha256": hashlib.sha256(
            parser_provenance_authorization_bytes
        ).hexdigest(),
        "terminal_bridge_attestation_bytes_sha256": hashlib.sha256(
            terminal_bridge_attestation_bytes
        ).hexdigest(),
        "annotation_event_bytes_sha256": hashlib.sha256(annotation_event_bytes).hexdigest(),
    }
    genesis = {
        "session_id": session,
        "run_id": run,
        "nonce_commitment_sha256": nonce_pin,
        "expected_packet_manifest_sha256": manifest_pin,
        "expected_packet_root_identity": {
            "final_path": expected_packet_root_final_path,
            "volume_serial": str(expected_packet_root_volume_serial),
            "file_id": expected_packet_root_file_id,
        },
        "expected_authority_origin": expected_authority_origin,
        "expected_packet_origin": expected_packet_origin,
        "expected_event_origin": expected_event_origin,
        "foundation_manifest_sha256": foundation_manifest_pin,
        "foundation_receipt_sha256": foundation_receipt_pin,
        "authority_raw_projection_sha256": canonical_sha256(authority_projection),
        "supplemental_raw_projection": supplemental_projection,
        "packet_validator_measurement_manifest_sha256": _sha(
            expected_packet_validator_measurement_manifest.get("artifact_sha256"),
            "packet measurement artifact_sha256",
        ),
        "combined_validator_measurement_manifest_sha256": combined_measurements[
            "artifact_sha256"
        ],
    }
    genesis_sha = canonical_sha256(genesis)
    trace: list[dict[str, Any]] = []
    result_bindings: list[dict[str, Any]] = []
    previous = "0" * 64

    preauth_row = _parse_canonical_json_object(
        owner_root_preauthorization_bytes, "owner root preauthorization"
    )
    before = _measure_and_match(combined_measurements, 0)
    preauth_receipt = preauth.validate_owner_root_preauthorization(
        preauth_row,
        expected_authority_origin,
        key=key,
        expected_owner_anchor_sha256=preauth_row.get("owner_anchor_sha256"),
        observed_at=preauth_row.get("not_before"),
    )
    after = _measure_and_match(combined_measurements, 0)
    if before != after:
        raise P0ActualAuthoritySupervisorError("preauth validator changed during call")
    preauth_binding = _receipt_binding(preauth_receipt, "preauthorization")
    _reject_child_overclaim(preauth_receipt, "preauthorization result")
    trace.append(_trace_row(index=0, previous=previous, measurement=after, input_binding={"genesis_sha256": genesis_sha, "raw_sha256": supplemental_projection["owner_root_preauthorization_bytes_sha256"]}, output_binding=preauth_binding))
    previous = trace[-1]["step_sha256"]
    result_bindings.append({"step_index": 0, **preauth_binding})

    before = _measure_and_match(combined_measurements, 1)
    packet_state = packet_supervisor._execute_packet_supervisor_state(
        packet_dir=packet_dir,
        expected_root_final_path=expected_packet_root_final_path,
        expected_root_volume_serial=expected_packet_root_volume_serial,
        expected_root_file_id=expected_packet_root_file_id,
        expected_manifest_sha256=manifest_pin,
        expected_origin=expected_packet_origin,
        session_id=session,
        run_id=run,
        nonce_commitment_sha256=nonce_pin,
        expected_validator_measurement_manifest=expected_packet_validator_measurement_manifest,
    )
    after = _measure_and_match(combined_measurements, 1)
    if before != after:
        raise P0ActualAuthoritySupervisorError("packet executor changed during call")
    packet_binding = _receipt_binding(packet_state.public_receipt, "packet supervisor")
    _reject_child_overclaim(packet_state.public_receipt, "packet supervisor result")
    trace.append(_trace_row(index=1, previous=previous, measurement=after, input_binding={"genesis_sha256": genesis_sha, "manifest_sha256": manifest_pin}, output_binding=packet_binding))
    previous = trace[-1]["step_sha256"]
    result_bindings.append({"step_index": 1, **packet_binding})

    authority_rows_preview = {
        role: _parse_canonical_json_object(raw_snapshot[path], f"authority {role}")
        for role, path in authority_raw.AUTHORITY_FILE_ROLES
    }
    capture_observed_at = authority_rows_preview["launch"].get("capture_started_at")
    expected_anchor = authority_rows_preview["owner_anchor"].get("artifact_sha256")
    before = _measure_and_match(combined_measurements, 2)
    authority_state = authority_raw._execute_authority_raw_validation_state(
        authority_raw_by_filename=raw_snapshot,
        annotation_event_bytes=annotation_event_bytes,
        expected_authority_origin=expected_authority_origin,
        expected_event_origin=expected_event_origin,
        foundation_manifest_sha256=foundation_manifest_pin,
        foundation_receipt_sha256=foundation_receipt_pin,
        key=key,
        expected_external_anchor_sha256=expected_anchor,
        observed_at=capture_observed_at,
    )
    after = _measure_and_match(combined_measurements, 2)
    if before != after:
        raise P0ActualAuthoritySupervisorError("authority raw executor changed during call")
    authority_binding = _receipt_binding(authority_state.public_receipt, "authority raw")
    _reject_child_overclaim(authority_state.public_receipt, "authority raw result")
    trace.append(_trace_row(index=2, previous=previous, measurement=after, input_binding={"authority_raw_projection_sha256": genesis["authority_raw_projection_sha256"], "event_sha256": supplemental_projection["annotation_event_bytes_sha256"]}, output_binding=authority_binding))
    previous = trace[-1]["step_sha256"]
    result_bindings.append({"step_index": 2, **authority_binding})

    before = _measure_and_match(combined_measurements, 3)
    parser_binding = _verify_parser_binding(
        packet_state=packet_state, authority_state=authority_state
    )
    after = _measure_and_match(combined_measurements, 3)
    if before != after:
        raise P0ActualAuthoritySupervisorError("parser binding validator changed")
    trace.append(_trace_row(index=3, previous=previous, measurement=after, input_binding={"packet_raw_projection_sha256": packet_state.public_receipt["raw_member_projection_sha256"], "authority_raw_projection_sha256": genesis["authority_raw_projection_sha256"]}, output_binding=parser_binding))
    previous = trace[-1]["step_sha256"]
    result_bindings.append({"step_index": 3, **parser_binding})

    parser_row = dict(authority_state.parsed_rows["parser_receipt"])
    route_row = _packet_json(packet_state, "route_receipt.json", "route receipt")
    manifest_row = _packet_json(packet_state, packet.PACKET_MANIFEST_FILENAME, "packet manifest")
    provenance_row = _parse_canonical_json_object(
        parser_provenance_authorization_bytes, "parser provenance authorization"
    )
    before = _measure_and_match(combined_measurements, 4)
    provenance, provenance_math = bridge.validate_parser_provenance_authorization(
        provenance_row,
        expected_authority_origin,
        key=key,
        expected_external_anchor_sha256=expected_anchor,
    )
    after = _measure_and_match(combined_measurements, 4)
    if before != after:
        raise P0ActualAuthoritySupervisorError("provenance validator changed")
    provenance_binding = _artifact_binding(provenance, "parser provenance")
    _reject_child_overclaim(provenance, "parser provenance result")
    expected_provenance = preauth_row.get("expected_provenance")
    expected_map = {
        "parser_receipt_schema": provenance["expected_parser_receipt_schema"],
        "parser_manifest_sha256": provenance["expected_parser_manifest_sha256"],
        "parser_version": provenance["expected_parser_version"],
        "capture_manifest_sha256": provenance["expected_capture_manifest_sha256"],
        "input_registry_sha256": provenance["expected_input_registry_sha256"],
        "source_input_plan_sha256": route_row["source_input_plan_sha256"],
        "sampling_frame_sha256": route_row["sampling_frame_sha256"],
        "packet_manifest_schema": packet.PACKET_MANIFEST_SCHEMA,
        "packet_fixed_member_contract_sha256": preauth.FIXED_MEMBER_CONTRACT_SHA256,
    }
    if expected_provenance != expected_map:
        raise P0ActualAuthoritySupervisorError("preauthorization/provenance mismatch")
    root = preauth_row.get("allowed_packet_root")
    if not isinstance(root, Mapping) or (
        root.get("final_volume_guid_path") != expected_packet_root_final_path
        or root.get("volume_serial_decimal") != str(expected_packet_root_volume_serial)
        or root.get("file_id_128_hex") != expected_packet_root_file_id
    ):
        raise P0ActualAuthoritySupervisorError("preauthorization packet root mismatch")
    if (
        preauth_row.get("run_id") != run
        or preauth_row.get("parser_run_id") != parser_row.get("parser_run_id")
        or nonce_commitment_sha256_fn(preauth_row.get("nonce")) != nonce_pin
        or preauth_row.get("launch_sha256") != authority_state.parsed_rows["launch"]["artifact_sha256"]
        or preauth_row.get("owner_authorization_sha256") != authority_state.parsed_rows["owner_authorization"]["artifact_sha256"]
        or preauth_row.get("watch_spec_sha256") != authority_state.parsed_rows["watch_spec"]["artifact_sha256"]
        or provenance["launch_sha256"] != parser_row["launch_sha256"]
        or provenance["expected_parser_manifest_sha256"] != route_row["parser_manifest_sha256"]
        or provenance["expected_parser_version"] != route_row["parser_version"]
        or provenance["expected_capture_manifest_sha256"] != parser_row["capture_manifest_sha256"]
        or provenance["expected_input_registry_sha256"] != parser_row["input_registry_sha256"]
    ):
        raise P0ActualAuthoritySupervisorError("run/nonce/parser provenance binding mismatch")
    trace.append(_trace_row(index=4, previous=previous, measurement=after, input_binding={"raw_sha256": supplemental_projection["parser_provenance_authorization_bytes_sha256"], "parser_binding_sha256": canonical_sha256(parser_binding)}, output_binding={**provenance_binding, "signature_math_valid": provenance_math}))
    previous = trace[-1]["step_sha256"]
    result_bindings.append({"step_index": 4, **provenance_binding, "signature_math_valid": provenance_math})

    terminal_row = _parse_canonical_json_object(
        terminal_bridge_attestation_bytes, "terminal bridge attestation"
    )
    before = _measure_and_match(combined_measurements, 5)
    terminal, terminal_math = bridge.validate_terminal_bridge_attestation(
        terminal_row,
        expected_authority_origin,
        key=key,
        expected_external_anchor_sha256=expected_anchor,
    )
    after = _measure_and_match(combined_measurements, 5)
    if before != after:
        raise P0ActualAuthoritySupervisorError("terminal validator changed")
    terminal_binding = _artifact_binding(terminal, "terminal bridge")
    _reject_child_overclaim(terminal, "terminal bridge result")
    trace.append(_trace_row(index=5, previous=previous, measurement=after, input_binding={"raw_sha256": supplemental_projection["terminal_bridge_attestation_bytes_sha256"], "prior_result_bindings_sha256": canonical_sha256(result_bindings)}, output_binding={**terminal_binding, "signature_math_valid": terminal_math}))
    previous = trace[-1]["step_sha256"]
    result_bindings.append({"step_index": 5, **terminal_binding, "signature_math_valid": terminal_math})

    before = _measure_and_match(combined_measurements, 6)
    bridge_result = bridge.validate_authority_bridge_bundle(
        parser_provenance_authorization=provenance,
        terminal_bridge_attestation=terminal,
        owner_anchor=_json_plain(authority_state.parsed_rows["owner_anchor"]),
        owner_authorization=_json_plain(
            authority_state.parsed_rows["owner_authorization"]
        ),
        launch=_json_plain(authority_state.parsed_rows["launch"]),
        parser_receipt=parser_row,
        route_receipt=route_row,
        keyless_manifest=manifest_row,
        packet_receipt=_json_plain(packet_state.packet_receipt),
        authority_manifest=_json_plain(authority_state.parsed_rows["manifest"]),
        authority_final_attestation=_json_plain(
            authority_state.parsed_rows["final_attestation"]
        ),
        authority_foundation_receipt=_json_plain(authority_state.foundation_result),
        event_bytes_receipt=_json_plain(authority_state.event_result),
        a_event_bytes_receipt=_json_plain(packet_state.a_event_receipt),
        windows_packet_validation_receipt=_json_plain(
            packet_state.windows_packet_receipt
        ),
        expected_authority_origin=expected_authority_origin,
        expected_packet_origin=expected_packet_origin,
        key=key,
        expected_external_anchor_sha256=expected_anchor,
    )
    after = _measure_and_match(combined_measurements, 6)
    if before != after:
        raise P0ActualAuthoritySupervisorError("bridge validator changed")
    _reject_bridge_overclaim(bridge_result)
    bridge_binding = _receipt_binding(bridge_result, "authority bridge")
    trace.append(_trace_row(index=6, previous=previous, measurement=after, input_binding={"prior_result_bindings_sha256": canonical_sha256(result_bindings), "terminal_artifact_sha256": terminal["artifact_sha256"]}, output_binding=bridge_binding))
    previous = trace[-1]["step_sha256"]
    result_bindings.append({"step_index": 6, **bridge_binding})

    material = {
        "schema_version": COMBINED_EXECUTION_SCHEMA,
        "execution_scope": EXECUTION_SCOPE,
        "session_id": session,
        "run_id": run,
        "nonce_commitment_sha256": nonce_pin,
        "execution_genesis": genesis,
        "execution_genesis_sha256": genesis_sha,
        "fixed_step_order": list(_FIXED_STEP_ORDER),
        "step_trace": trace,
        "trace_head_sha256": previous,
        "result_bindings": result_bindings,
        "result_bindings_sha256": canonical_sha256(result_bindings),
        "authority_raw_projection": authority_projection,
        "authority_raw_projection_sha256": canonical_sha256(authority_projection),
        "supplemental_raw_projection": supplemental_projection,
        "supplemental_raw_projection_sha256": canonical_sha256(supplemental_projection),
        "parser_binding": parser_binding,
        "parser_binding_sha256": canonical_sha256(parser_binding),
        "preauthorization_signature_math_valid": preauth_receipt["signature_math_valid"],
        "provenance_signature_math_valid": provenance_math,
        "terminal_signature_math_valid": terminal_math,
        "foundation_signature_math_valid": authority_state.foundation_result["detached_hmac_math_valid"],
        "final_attestation_signature_math_valid": authority_state.foundation_result["final_attestation_math_valid"],
        "packet_side_direct_invocations_observed": True,
        "authority_side_direct_invocations_observed": True,
        "bridge_direct_invocation_observed": True,
        "direct_local_validator_invocations_observed": True,
        "serialized_child_receipt_inputs_accepted": False,
        "untrusted_local_execution_observation": True,
        **{field: False for field in _FALSE_FIELDS},
        "credited_counts": {
            "actual_source_claim_count": 0,
            "actual_a_context_review_count": 0,
        },
        "operational_effect": "NONE_SHADOW_ONLY",
        "gate_status": GATE_STATUS,
    }
    return {**material, "receipt_sha256": canonical_sha256(material)}


# Keep the public helper name distinct from the nonce parameter used by the executor.
nonce_commitment_sha256_fn = nonce_commitment_sha256


def validate_presented_authority_supervisor_receipt(value: Any) -> dict[str, Any]:
    """Validate receipt structure only and explicitly discard execution truth."""

    if not isinstance(value, Mapping):
        raise P0ActualAuthoritySupervisorError("presented combined receipt must be object")
    row = _json_plain(value)
    local_true_fields = {
        "packet_side_direct_invocations_observed",
        "authority_side_direct_invocations_observed",
        "bridge_direct_invocation_observed",
        "direct_local_validator_invocations_observed",
        "untrusted_local_execution_observation",
    }
    math_fields = {
        "preauthorization_signature_math_valid",
        "provenance_signature_math_valid",
        "terminal_signature_math_valid",
        "foundation_signature_math_valid",
        "final_attestation_signature_math_valid",
    }
    required_fields = {
        "schema_version",
        "execution_scope",
        "session_id",
        "run_id",
        "nonce_commitment_sha256",
        "execution_genesis",
        "execution_genesis_sha256",
        "fixed_step_order",
        "step_trace",
        "trace_head_sha256",
        "result_bindings",
        "result_bindings_sha256",
        "authority_raw_projection",
        "authority_raw_projection_sha256",
        "supplemental_raw_projection",
        "supplemental_raw_projection_sha256",
        "parser_binding",
        "parser_binding_sha256",
        "serialized_child_receipt_inputs_accepted",
        "credited_counts",
        "operational_effect",
        "gate_status",
        "receipt_sha256",
        *local_true_fields,
        *math_fields,
        *_FALSE_FIELDS,
    }
    if set(row) != required_fields:
        raise P0ActualAuthoritySupervisorError(
            "presented combined top-level fields mismatch"
        )
    if row.get("schema_version") != COMBINED_EXECUTION_SCHEMA or row.get(
        "execution_scope"
    ) != EXECUTION_SCOPE:
        raise P0ActualAuthoritySupervisorError("presented combined schema/scope mismatch")
    stored = _sha(row.get("receipt_sha256"), "receipt_sha256")
    if stored != canonical_sha256(
        {key: item for key, item in row.items() if key != "receipt_sha256"}
    ):
        raise P0ActualAuthoritySupervisorError("presented combined self-hash mismatch")
    if row.get("fixed_step_order") != list(_FIXED_STEP_ORDER):
        raise P0ActualAuthoritySupervisorError("presented combined step order mismatch")
    session = _identifier(row.get("session_id"), "session_id")
    run = _identifier(row.get("run_id"), "run_id")
    nonce_pin = _sha(row.get("nonce_commitment_sha256"), "nonce_commitment_sha256")
    genesis = row.get("execution_genesis")
    genesis_fields = {
        "session_id",
        "run_id",
        "nonce_commitment_sha256",
        "expected_packet_manifest_sha256",
        "expected_packet_root_identity",
        "expected_authority_origin",
        "expected_packet_origin",
        "expected_event_origin",
        "foundation_manifest_sha256",
        "foundation_receipt_sha256",
        "authority_raw_projection_sha256",
        "supplemental_raw_projection",
        "packet_validator_measurement_manifest_sha256",
        "combined_validator_measurement_manifest_sha256",
    }
    if not isinstance(genesis, Mapping) or set(genesis) != genesis_fields:
        raise P0ActualAuthoritySupervisorError("presented execution genesis malformed")
    if (
        genesis.get("session_id") != session
        or genesis.get("run_id") != run
        or genesis.get("nonce_commitment_sha256") != nonce_pin
    ):
        raise P0ActualAuthoritySupervisorError("presented genesis identity mismatch")
    for field in (
        "expected_packet_manifest_sha256",
        "foundation_manifest_sha256",
        "foundation_receipt_sha256",
        "authority_raw_projection_sha256",
        "packet_validator_measurement_manifest_sha256",
        "combined_validator_measurement_manifest_sha256",
    ):
        _sha(genesis.get(field), f"execution_genesis.{field}")
    root = genesis.get("expected_packet_root_identity")
    if (
        not isinstance(root, Mapping)
        or set(root) != {"final_path", "volume_serial", "file_id"}
        or not isinstance(root.get("final_path"), str)
        or not root.get("final_path")
        or not isinstance(root.get("volume_serial"), str)
        or not root.get("volume_serial").isdigit()
        or not isinstance(root.get("file_id"), str)
        or _FILE_ID.fullmatch(root.get("file_id")) is None
    ):
        raise P0ActualAuthoritySupervisorError("presented genesis root malformed")
    for field in (
        "expected_authority_origin",
        "expected_packet_origin",
        "expected_event_origin",
    ):
        if not isinstance(genesis.get(field), str) or not genesis[field]:
            raise P0ActualAuthoritySupervisorError(
                f"presented genesis {field} malformed"
            )
    genesis_sha = _sha(row.get("execution_genesis_sha256"), "execution_genesis_sha256")
    if genesis_sha != canonical_sha256(genesis):
        raise P0ActualAuthoritySupervisorError("presented genesis self-hash mismatch")

    trace = row.get("step_trace")
    if not isinstance(trace, list) or len(trace) != len(_FIXED_STEP_ORDER):
        raise P0ActualAuthoritySupervisorError("presented combined trace count mismatch")
    previous = "0" * 64
    for index, step in enumerate(trace):
        if not isinstance(step, Mapping):
            raise P0ActualAuthoritySupervisorError("presented trace row malformed")
        material = dict(step)
        if set(material) != {
            "step_index",
            "step_name",
            "previous_step_sha256",
            "measurement_sha256",
            "input_binding_sha256",
            "output_binding",
            "output_binding_sha256",
            "step_sha256",
        }:
            raise P0ActualAuthoritySupervisorError(
                "presented trace fields mismatch"
            )
        step_sha = _sha(material.pop("step_sha256", None), "step_sha256")
        measurement_sha = _sha(
            material.get("measurement_sha256"), "measurement_sha256"
        )
        input_sha = _sha(
            material.get("input_binding_sha256"), "input_binding_sha256"
        )
        del measurement_sha, input_sha
        output_binding = material.get("output_binding")
        output_sha = _sha(
            material.get("output_binding_sha256"), "output_binding_sha256"
        )
        if (
            material.get("step_index") != index
            or material.get("step_name") != _FIXED_STEP_ORDER[index]
            or material.get("previous_step_sha256") != previous
            or not isinstance(output_binding, Mapping)
            or output_sha != canonical_sha256(output_binding)
            or step_sha != canonical_sha256(material)
        ):
            raise P0ActualAuthoritySupervisorError("presented trace chain mismatch")
        previous = step_sha
    if previous != row.get("trace_head_sha256"):
        raise P0ActualAuthoritySupervisorError("presented trace head mismatch")

    parser_binding_fields = {
        "packet_parser_receipt_raw_sha256",
        "authority_parser_receipt_raw_sha256",
        "parser_receipt_artifact_sha256",
        "parser_receipt_byte_exact_cross_binding_verified",
        "parser_receipt_semantic_cross_binding_verified",
    }
    result_bindings = row.get("result_bindings")
    if not isinstance(result_bindings, list) or len(result_bindings) != len(trace):
        raise P0ActualAuthoritySupervisorError("presented result bindings malformed")
    receipt_binding_steps = {
        0: preauth.PREAUTHORIZATION_RECEIPT_SCHEMA,
        1: packet_supervisor.SUPERVISOR_EXECUTION_RECEIPT_SCHEMA,
        2: authority_raw.AUTHORITY_RAW_EXECUTION_SCHEMA,
        6: bridge.BRIDGE_RECEIPT_SCHEMA,
    }
    artifact_binding_steps = {
        4: bridge.PARSER_PROVENANCE_AUTHORIZATION_SCHEMA,
        5: bridge.TERMINAL_BRIDGE_ATTESTATION_SCHEMA,
    }
    for index, binding in enumerate(result_bindings):
        if not isinstance(binding, Mapping) or dict(binding) != {
            "step_index": index,
            **dict(trace[index]["output_binding"]),
        }:
            raise P0ActualAuthoritySupervisorError(
                "presented result/trace binding mismatch"
            )
        binding_fields = set(binding)
        if index in receipt_binding_steps:
            if (
                binding_fields
                != {
                    "step_index",
                    "schema_version",
                    "declared_receipt_sha256",
                    "full_canonical_sha256",
                }
                or binding.get("schema_version") != receipt_binding_steps[index]
            ):
                raise P0ActualAuthoritySupervisorError(
                    "presented receipt result binding shape mismatch"
                )
            _sha(
                binding.get("declared_receipt_sha256"),
                "declared_receipt_sha256",
            )
            _sha(binding.get("full_canonical_sha256"), "full_canonical_sha256")
        elif index in artifact_binding_steps:
            if (
                binding_fields
                != {
                    "step_index",
                    "schema_version",
                    "artifact_sha256",
                    "full_canonical_sha256",
                    "signature_math_valid",
                }
                or binding.get("schema_version") != artifact_binding_steps[index]
                or type(binding.get("signature_math_valid")) is not bool
            ):
                raise P0ActualAuthoritySupervisorError(
                    "presented artifact result binding shape mismatch"
                )
            _sha(binding.get("artifact_sha256"), "artifact_sha256")
            _sha(binding.get("full_canonical_sha256"), "full_canonical_sha256")
        elif index == 3:
            if binding_fields != {"step_index", *parser_binding_fields}:
                raise P0ActualAuthoritySupervisorError(
                    "presented parser result binding shape mismatch"
                )
    result_sha = _sha(row.get("result_bindings_sha256"), "result_bindings_sha256")
    if result_sha != canonical_sha256(result_bindings):
        raise P0ActualAuthoritySupervisorError(
            "presented result bindings self-hash mismatch"
        )

    authority_projection = row.get("authority_raw_projection")
    if not isinstance(authority_projection, list) or len(authority_projection) != len(
        authority_raw.AUTHORITY_FILE_ROLES
    ):
        raise P0ActualAuthoritySupervisorError(
            "presented authority raw projection malformed"
        )
    for item, (role, path) in zip(
        authority_projection, authority_raw.AUTHORITY_FILE_ROLES, strict=True
    ):
        if (
            not isinstance(item, Mapping)
            or set(item) != {"role", "path", "bytes", "sha256"}
            or item.get("role") != role
            or item.get("path") != path
            or not isinstance(item.get("bytes"), int)
            or isinstance(item.get("bytes"), bool)
            or item.get("bytes") <= 0
        ):
            raise P0ActualAuthoritySupervisorError(
                "presented authority raw projection row malformed"
            )
        _sha(item.get("sha256"), f"authority_raw_projection.{role}.sha256")
    authority_projection_sha = _sha(
        row.get("authority_raw_projection_sha256"),
        "authority_raw_projection_sha256",
    )
    if (
        authority_projection_sha != canonical_sha256(authority_projection)
        or genesis.get("authority_raw_projection_sha256") != authority_projection_sha
    ):
        raise P0ActualAuthoritySupervisorError(
            "presented authority raw projection binding mismatch"
        )

    supplemental = row.get("supplemental_raw_projection")
    supplemental_fields = {
        "owner_root_preauthorization_bytes_sha256",
        "parser_provenance_authorization_bytes_sha256",
        "terminal_bridge_attestation_bytes_sha256",
        "annotation_event_bytes_sha256",
    }
    if not isinstance(supplemental, Mapping) or set(supplemental) != supplemental_fields:
        raise P0ActualAuthoritySupervisorError(
            "presented supplemental raw projection malformed"
        )
    for field in supplemental_fields:
        _sha(supplemental.get(field), f"supplemental_raw_projection.{field}")
    supplemental_sha = _sha(
        row.get("supplemental_raw_projection_sha256"),
        "supplemental_raw_projection_sha256",
    )
    if (
        supplemental_sha != canonical_sha256(supplemental)
        or genesis.get("supplemental_raw_projection") != supplemental
    ):
        raise P0ActualAuthoritySupervisorError(
            "presented supplemental raw projection binding mismatch"
        )

    parser_binding = row.get("parser_binding")
    if not isinstance(parser_binding, Mapping) or set(parser_binding) != parser_binding_fields:
        raise P0ActualAuthoritySupervisorError("presented parser binding malformed")
    packet_parser_sha = _sha(
        parser_binding.get("packet_parser_receipt_raw_sha256"),
        "packet parser raw sha256",
    )
    authority_parser_sha = _sha(
        parser_binding.get("authority_parser_receipt_raw_sha256"),
        "authority parser raw sha256",
    )
    _sha(
        parser_binding.get("parser_receipt_artifact_sha256"),
        "parser receipt artifact sha256",
    )
    if (
        packet_parser_sha != authority_parser_sha
        or parser_binding.get("parser_receipt_byte_exact_cross_binding_verified")
        is not True
        or parser_binding.get("parser_receipt_semantic_cross_binding_verified")
        is not True
        or _sha(row.get("parser_binding_sha256"), "parser_binding_sha256")
        != canonical_sha256(parser_binding)
    ):
        raise P0ActualAuthoritySupervisorError(
            "presented parser cross-binding mismatch"
        )

    if any(row.get(field) is not True for field in local_true_fields):
        raise P0ActualAuthoritySupervisorError(
            "presented local observation flags mismatch"
        )
    if any(type(row.get(field)) is not bool for field in math_fields):
        raise P0ActualAuthoritySupervisorError(
            "presented signature math fields malformed"
        )
    if any(row.get(field) is not False for field in _FALSE_FIELDS) or row.get(
        "credited_counts"
    ) != {"actual_source_claim_count": 0, "actual_a_context_review_count": 0}:
        raise P0ActualAuthoritySupervisorError("presented authority/credit overclaim")
    if (
        row.get("serialized_child_receipt_inputs_accepted") is not False
        or row.get("operational_effect") != "NONE_SHADOW_ONLY"
        or row.get("gate_status") != GATE_STATUS
        or row.get("action_applied") is not False
    ):
        raise P0ActualAuthoritySupervisorError("presented combined gate overclaim")
    material = {
        "schema_version": PRESENTED_VALIDATION_SCHEMA,
        "validation_scope": "PRESENTED_COMBINED_RECEIPT_STRUCTURE_ONLY",
        "presented_combined_receipt_sha256": stored,
        "presented_receipt_structurally_verified": True,
        "direct_local_validator_invocations_observed": False,
        "packet_side_direct_invocations_observed": False,
        "authority_side_direct_invocations_observed": False,
        "bridge_direct_invocation_observed": False,
        "underlying_validator_execution_verified": False,
        "untrusted_local_execution_observation": True,
        **{field: False for field in _FALSE_FIELDS if field != "underlying_validator_execution_verified"},
        "credited_counts": {
            "actual_source_claim_count": 0,
            "actual_a_context_review_count": 0,
        },
        "operational_effect": "NONE_SHADOW_ONLY",
        "gate_status": PRESENTED_GATE_STATUS,
    }
    return {**material, "receipt_sha256": canonical_sha256(material)}


__all__ = [
    "COMBINED_EXECUTION_SCHEMA",
    "GATE_STATUS",
    "MEASUREMENT_MANIFEST_SCHEMA",
    "P0ActualAuthoritySupervisorError",
    "PRESENTED_VALIDATION_SCHEMA",
    "build_local_authority_supervisor_measurement_manifest",
    "execute_authority_supervisor_trace",
    "nonce_commitment_sha256",
    "validate_presented_authority_supervisor_receipt",
]
