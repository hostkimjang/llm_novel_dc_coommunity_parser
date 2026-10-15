"""외부 trust 실행과 Windows runtime witness를 결합하는 actual-P0 supervisor.

이 계층은 caller key를 받지 않는다. run root 밖 trust store에서 key를 읽고
single-use nonce를 먼저 소비한 뒤, Windows witness가 기존 packet/authority 결합
supervisor 호출 전체를 감싼다. nonce 소비 뒤 하위 실행이 실패하면 nonce 파일을
지우지 않아 replay를 fail-close한다.

trust-store 경로와 wall clock, 보호 root pin, verifier process 자체는 독립적으로
attest되지 않았다. 따라서 store-key 서명 검증·nonce 소비·bounded runtime 관측이
성공해도 owner authority, actual credit, P0 exit, production/full scan은 열지 않는다.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
import re
from typing import Any, Mapping

from llm_batch.grounding import p0_actual_authority_supervisor_execution as combined
from llm_batch.grounding import p0_actual_owner_root_preauthorization as preauth
from llm_batch.grounding import p0_external_owner_trust_execution as external
from llm_batch.grounding import p0_windows_runtime_evidence as runtime


EXECUTION_RECEIPT_SCHEMA = "p0_external_authority_runtime_supervisor_receipt_v1"
PRESENTED_VALIDATION_SCHEMA = (
    "p0_external_authority_runtime_supervisor_presented_validation_v1"
)
EXECUTION_SCOPE = (
    "STORE_KEY_NONCE_CONSUMPTION_AND_BOUNDED_RUNTIME_WRAPPED_LOCAL_VALIDATORS"
)
GATE_STATUS = "EXTERNAL_STORE_AND_RUNTIME_WITNESS_EXECUTED_AUTHORITY_NO_GO"
PRESENTED_GATE_STATUS = "PRESENTED_EXTERNAL_RUNTIME_RECEIPT_ONLY_AUTHORITY_NO_GO"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")

_ALWAYS_FALSE_FIELDS = (
    "external_code_authority_verified",
    "supervisor_runtime_trust_verified",
    "trusted_time_verified",
    "external_trust_store_verified",
    "revocation_current_verified",
    "external_owner_trust_verified",
    "external_root_identity_pin_verified",
    "filesystem_handle_binding_verified",
    "filesystem_handle_trust_verified",
    "windows_handle_capture_execution_provenance_verified",
    "handles_held_across_validator_execution",
    "authority_journal_watch_bundle_verified",
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


class P0ExternalAuthorityRuntimeSupervisorError(ValueError):
    """결합 실행이 신뢰 경계를 보존할 수 없을 때 발생한다."""


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _plain(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise P0ExternalAuthorityRuntimeSupervisorError(f"{label} is invalid")
    return value


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise P0ExternalAuthorityRuntimeSupervisorError(
            f"{label} must be lowercase sha256"
        )
    return value


def _duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P0ExternalAuthorityRuntimeSupervisorError(
                f"duplicate JSON key: {key}"
            )
        result[key] = value
    return result


def _reject_nonfinite(token: str) -> None:
    raise P0ExternalAuthorityRuntimeSupervisorError(
        f"non-finite JSON constant is forbidden: {token}"
    )


def _parse_canonical_object(raw: Any, label: str) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or raw.startswith(b"\xef\xbb\xbf"):
        raise P0ExternalAuthorityRuntimeSupervisorError(
            f"{label} must be exact UTF-8 bytes without BOM"
        )
    try:
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_duplicate_object,
            parse_constant=_reject_nonfinite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise P0ExternalAuthorityRuntimeSupervisorError(
            f"{label} is not strict JSON"
        ) from exc
    if not isinstance(value, dict) or canonical_bytes(value) + b"\n" != raw:
        raise P0ExternalAuthorityRuntimeSupervisorError(
            f"{label} must be one canonical JSON object plus LF"
        )
    return value


def _normalise_windows_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise P0ExternalAuthorityRuntimeSupervisorError(f"{label} is invalid")
    return value.replace("/", "\\").rstrip("\\").casefold()


def _protected_roots(
    value: Mapping[str, Path | str],
) -> dict[str, Path]:
    if not isinstance(value, Mapping) or list(value) != list(
        runtime.REQUIRED_PROTECTED_CATEGORIES
    ):
        raise P0ExternalAuthorityRuntimeSupervisorError(
            "protected_category_roots must contain the exact ordered category set"
        )
    result: dict[str, Path] = {}
    identities: set[tuple[int, int]] = set()
    for category, raw_path in value.items():
        try:
            path = Path(raw_path).resolve(strict=True)
            info = path.stat()
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise P0ExternalAuthorityRuntimeSupervisorError(
                f"protected category root is unavailable: {category}"
            ) from exc
        if not path.is_dir():
            raise P0ExternalAuthorityRuntimeSupervisorError(
                f"protected category root must be directory: {category}"
            )
        identity = (int(info.st_dev), int(info.st_ino))
        if identity in identities:
            raise P0ExternalAuthorityRuntimeSupervisorError(
                "protected category roots must have distinct identities"
            )
        identities.add(identity)
        result[category] = path
    return result


def _expected_effective_roots(preauthorization: Mapping[str, Any]) -> dict[str, str]:
    protected = preauthorization.get("protected_roots")
    categories = preauthorization.get("category_root_map")
    if not isinstance(protected, list) or not isinstance(categories, list):
        raise P0ExternalAuthorityRuntimeSupervisorError(
            "preauthorization protected root projection is invalid"
        )
    root_paths: dict[str, str] = {}
    for row in protected:
        if not isinstance(row, Mapping):
            raise P0ExternalAuthorityRuntimeSupervisorError(
                "preauthorization protected root is invalid"
            )
        root_id = _identifier(row.get("root_id"), "protected root_id")
        root_paths[root_id] = _normalise_windows_path(
            row.get("final_volume_guid_path"), "protected final path"
        )
    expected: dict[str, str] = {}
    if len(categories) != len(runtime.REQUIRED_PROTECTED_CATEGORIES):
        raise P0ExternalAuthorityRuntimeSupervisorError(
            "preauthorization category root count mismatch"
        )
    for index, row in enumerate(categories):
        if not isinstance(row, Mapping):
            raise P0ExternalAuthorityRuntimeSupervisorError(
                "preauthorization category root mapping is invalid"
            )
        category = row.get("category")
        if category != runtime.REQUIRED_PROTECTED_CATEGORIES[index]:
            raise P0ExternalAuthorityRuntimeSupervisorError(
                "preauthorization category order mismatch"
            )
        root_id = row.get("root_id")
        relative = row.get("relative_root")
        if root_id not in root_paths or not isinstance(relative, str) or not relative:
            raise P0ExternalAuthorityRuntimeSupervisorError(
                "preauthorization category root reference is invalid"
            )
        expected[category] = _normalise_windows_path(
            root_paths[root_id] + "\\" + relative,
            "effective protected root",
        )
    return expected


def _runtime_root_binding(
    runtime_receipt: Mapping[str, Any], expected: Mapping[str, str]
) -> tuple[bool, list[dict[str, Any]]]:
    categories = runtime_receipt.get("categories")
    if not isinstance(categories, list) or len(categories) != len(expected):
        raise P0ExternalAuthorityRuntimeSupervisorError(
            "runtime category evidence count mismatch"
        )
    projection: list[dict[str, Any]] = []
    all_bound = True
    for index, row in enumerate(categories):
        category = runtime.REQUIRED_PROTECTED_CATEGORIES[index]
        if not isinstance(row, Mapping) or row.get("category") != category:
            raise P0ExternalAuthorityRuntimeSupervisorError(
                "runtime category evidence order mismatch"
            )
        identity = row.get("pre_identity")
        observed_path = identity.get("final_path") if isinstance(identity, Mapping) else None
        match = bool(
            observed_path is not None
            and _normalise_windows_path(observed_path, "runtime observed root")
            == expected[category]
        )
        all_bound = all_bound and match
        projection.append(
            {
                "category": category,
                "expected_final_path": expected[category],
                "observed_final_path": observed_path,
                "matched": match,
            }
        )
    return all_bound, projection


def _receipt_binding(value: Mapping[str, Any], label: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise P0ExternalAuthorityRuntimeSupervisorError(f"{label} receipt is invalid")
    row = _plain(value)
    schema_fields = [field for field in ("schema_version", "schema") if field in row]
    digest_fields = [
        field for field in ("receipt_sha256", "evidence_sha256") if field in row
    ]
    if len(schema_fields) != 1 or len(digest_fields) != 1:
        raise P0ExternalAuthorityRuntimeSupervisorError(
            f"{label} receipt schema/hash field is ambiguous"
        )
    schema = row[schema_fields[0]]
    digest_field = digest_fields[0]
    digest = _sha(row[digest_field], f"{label} sha256")
    if not isinstance(schema, str) or not schema:
        raise P0ExternalAuthorityRuntimeSupervisorError(f"{label} schema is invalid")
    material = dict(row)
    material.pop(digest_field)
    if not hmac.compare_digest(digest, canonical_sha256(material)):
        raise P0ExternalAuthorityRuntimeSupervisorError(
            f"{label} receipt self-hash mismatch"
        )
    return {"schema": schema, "sha256": digest}


def _reject_trust_overclaim(value: Mapping[str, Any]) -> None:
    required_true = (
        "trust_store_filesystem_execution_observed",
        "signature_verified_with_store_key",
        "single_use_replay_consumed",
        "nonce_atomic_create_exclusive_verified",
        "nonce_record_file_flush_verified",
        "nonce_ledger_action_applied",
    )
    if any(value.get(field) is not True for field in required_true):
        raise P0ExternalAuthorityRuntimeSupervisorError(
            "external trust execution did not consume a verified nonce"
        )
    forbidden_true = (
        "external_trust_store_verified",
        "revocation_current_verified",
        "trusted_time_verified",
        "external_owner_trust_verified",
        "external_root_identity_pin_verified",
        "filesystem_handle_trust_verified",
        "owner_authority_verified",
        "actual_authority_granted",
        "production_approval",
        "full_scan_approval",
        "p0_phase_exit",
        "action_applied",
    )
    if any(value.get(field) is not False for field in forbidden_true):
        raise P0ExternalAuthorityRuntimeSupervisorError(
            "external trust receipt authority overclaim"
        )
    if value.get("gate_status") != "EXTERNAL_STORE_EXECUTED_ACTUAL_P0_AUTHORITY_NO_GO":
        raise P0ExternalAuthorityRuntimeSupervisorError(
            "external trust receipt gate overclaim"
        )


def _reject_runtime_overclaim(value: Mapping[str, Any]) -> None:
    for field in (
        "owner_authority_verified",
        "semantic_quality_verified",
        "p0_exit_authorized",
        "production_authorized",
        "parser_runtime_execution_verified",
    ):
        if value.get(field) is not False:
            raise P0ExternalAuthorityRuntimeSupervisorError(
                "runtime witness receipt authority overclaim"
            )
    if value.get("operation_completed") is not True:
        raise P0ExternalAuthorityRuntimeSupervisorError(
            "runtime-wrapped combined operation did not complete"
        )


def _reject_combined_overclaim(value: Mapping[str, Any]) -> None:
    if not isinstance(value, Mapping):
        raise P0ExternalAuthorityRuntimeSupervisorError(
            "combined supervisor operation result is invalid"
        )
    if value.get("gate_status") != combined.GATE_STATUS:
        raise P0ExternalAuthorityRuntimeSupervisorError(
            "combined supervisor gate overclaim"
        )
    if value.get("credited_counts") != {
        "actual_source_claim_count": 0,
        "actual_a_context_review_count": 0,
    }:
        raise P0ExternalAuthorityRuntimeSupervisorError(
            "combined supervisor credit overclaim"
        )
    if any(value.get(field) is not False for field in combined._FALSE_FIELDS):
        raise P0ExternalAuthorityRuntimeSupervisorError(
            "combined supervisor nested authority overclaim"
        )


def execute_external_authority_runtime_supervisor_trace(
    *,
    trust_store_dir: Path | str,
    run_root: Path | str,
    protected_category_roots: Mapping[str, Path | str],
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
) -> dict[str, Any]:
    """Consume trusted-store nonce and run the local validators under a witness."""

    session = _identifier(session_id, "session_id")
    run = _identifier(run_id, "run_id")
    nonce = _sha(nonce_commitment_sha256, "nonce_commitment_sha256")
    preauthorization = _parse_canonical_object(
        owner_root_preauthorization_bytes, "owner root preauthorization"
    )
    if preauthorization.get("run_id") != run:
        raise P0ExternalAuthorityRuntimeSupervisorError(
            "preauthorization run_id mismatch"
        )
    provenance = preauthorization.get("expected_provenance")
    if not isinstance(provenance, Mapping):
        raise P0ExternalAuthorityRuntimeSupervisorError(
            "preauthorization expected provenance is invalid"
        )
    roots = _protected_roots(protected_category_roots)
    expected_effective_roots = _expected_effective_roots(preauthorization)

    trust_state = external._execute_external_owner_trust_state(
        trust_store_dir=trust_store_dir,
        run_root=run_root,
        packet_root=packet_dir,
        protected_roots=list(roots.values()),
        owner_root_preauthorization_bytes=owner_root_preauthorization_bytes,
        session_id=session,
        run_id=run,
        nonce_commitment_sha256=nonce,
        expected_packet_root_final_path=expected_packet_root_final_path,
        expected_packet_root_volume_serial=expected_packet_root_volume_serial,
        expected_packet_root_file_id=expected_packet_root_file_id,
        expected_parser_provenance=dict(provenance),
    )
    try:
        trust_receipt = _plain(trust_state.public_receipt)
        _reject_trust_overclaim(trust_receipt)
        trusted_key = external._consume_external_owner_trust_state(
            trust_state,
            expected_receipt_sha256=trust_receipt["receipt_sha256"],
            expected_nonce_commitment_sha256=nonce,
        )
    except BaseException:
        # Mint 이후 어떤 invariant가 실패해도 key-bearing registry entry를
        # 남기지 않는다. nonce burn은 의도대로 복구하지 않는다.
        external._discard_external_owner_trust_state(trust_state)
        raise

    def execute_combined() -> dict[str, Any]:
        return combined.execute_authority_supervisor_trace(
            packet_dir=packet_dir,
            expected_packet_root_final_path=expected_packet_root_final_path,
            expected_packet_root_volume_serial=expected_packet_root_volume_serial,
            expected_packet_root_file_id=expected_packet_root_file_id,
            expected_packet_manifest_sha256=expected_packet_manifest_sha256,
            authority_raw_by_filename=authority_raw_by_filename,
            annotation_event_bytes=annotation_event_bytes,
            owner_root_preauthorization_bytes=owner_root_preauthorization_bytes,
            parser_provenance_authorization_bytes=parser_provenance_authorization_bytes,
            terminal_bridge_attestation_bytes=terminal_bridge_attestation_bytes,
            expected_authority_origin=expected_authority_origin,
            expected_packet_origin=expected_packet_origin,
            expected_event_origin=expected_event_origin,
            foundation_manifest_sha256=foundation_manifest_sha256,
            foundation_receipt_sha256=foundation_receipt_sha256,
            session_id=session,
            run_id=run,
            nonce_commitment_sha256=nonce,
            expected_packet_validator_measurement_manifest=(
                expected_packet_validator_measurement_manifest
            ),
            expected_combined_validator_measurement_manifest=(
                expected_combined_validator_measurement_manifest
            ),
            key=trusted_key,
        )

    runtime_state = runtime._execute_windows_runtime_evidence_state(
        roots,
        execute_combined,
        # 이 callback은 parser가 아니라 validator supervisor다. restricted
        # parser token은 write-open probe에만 쓰고 validator 실행 전 복원한다.
        impersonate_operation=False,
    )
    runtime_state = runtime._consume_windows_runtime_evidence_state(runtime_state)
    runtime_receipt = _plain(runtime_state.detached_receipt)
    if runtime_state.operation_exception is not None:
        raise runtime_state.operation_exception.with_traceback(
            runtime_state.operation_traceback
        )
    combined_receipt = _plain(runtime_state.operation_result)
    _reject_runtime_overclaim(runtime_receipt)
    _reject_combined_overclaim(combined_receipt)

    root_binding, root_projection = _runtime_root_binding(
        runtime_receipt, expected_effective_roots
    )
    trust_binding = _receipt_binding(trust_receipt, "external trust")
    runtime_binding = _receipt_binding(runtime_receipt, "runtime witness")
    combined_binding = _receipt_binding(combined_receipt, "combined supervisor")
    if (
        trust_receipt.get("session_id") != session
        or trust_receipt.get("run_id") != run
        or trust_receipt.get("nonce_commitment_sha256") != nonce
        or combined_receipt.get("session_id") != session
        or combined_receipt.get("run_id") != run
        or combined_receipt.get("nonce_commitment_sha256") != nonce
        or trust_receipt.get("preauthorization_bytes_sha256")
        != hashlib.sha256(owner_root_preauthorization_bytes).hexdigest()
    ):
        raise P0ExternalAuthorityRuntimeSupervisorError(
            "trust/combined session, run, nonce, or raw preauthorization mismatch"
        )

    bounded = runtime_receipt.get("bounded_runtime_noninterference_verified") is True
    material = {
        "schema_version": EXECUTION_RECEIPT_SCHEMA,
        "execution_scope": EXECUTION_SCOPE,
        "session_id": session,
        "run_id": run,
        "nonce_commitment_sha256": nonce,
        "owner_root_preauthorization_bytes_sha256": hashlib.sha256(
            owner_root_preauthorization_bytes
        ).hexdigest(),
        "external_trust_binding": trust_binding,
        "runtime_witness_binding": runtime_binding,
        "combined_supervisor_binding": combined_binding,
        "child_bindings_sha256": canonical_sha256(
            [trust_binding, runtime_binding, combined_binding]
        ),
        "protected_category_root_projection": root_projection,
        "protected_category_root_projection_sha256": canonical_sha256(root_projection),
        # 이 값은 signed parent tuple/held handle trust가 아니라 final-path
        # projection 일치만 뜻한다. authority 표현을 사용하지 않는다.
        "protected_category_final_path_projection_match": root_binding,
        "trust_store_filesystem_execution_observed": True,
        "signature_verified_with_store_key": True,
        "single_use_replay_consumed": True,
        "nonce_ledger_action_applied": True,
        "power_loss_durable_replay_verified": bool(
            trust_receipt.get("power_loss_durable_replay_verified")
        ),
        "combined_direct_local_execution_observed": True,
        "runtime_witness_same_process_execution_observed": True,
        "qpc_monotonic_timeline_verified": bool(
            runtime_receipt.get("qpc_monotonic_timeline_verified")
        ),
        "usn_interval_verified": bool(runtime_receipt.get("usn_interval_verified")),
        "continuous_watch_verified": bool(
            runtime_receipt.get("continuous_watch_verified")
        ),
        "os_write_deny_verified": bool(runtime_receipt.get("os_write_deny_verified")),
        "current_thread_restricted_token_write_open_denial_verified": bool(
            runtime_receipt.get(
                "current_thread_restricted_token_write_open_denial_verified"
            )
        ),
        "bounded_runtime_noninterference_verified": bounded,
        "runtime_noninterference_verified": False,
        **{field: False for field in _ALWAYS_FALSE_FIELDS},
        "credited_counts": {
            "actual_source_claim_count": 0,
            "actual_a_context_review_count": 0,
        },
        "security_control_state_mutated": True,
        "protected_pipeline_state_mutated": False,
        "operational_effect": "NONCE_LEDGER_CONSUMED_PIPELINE_SHADOW_ONLY",
        "gate_status": GATE_STATUS,
    }
    return {**material, "receipt_sha256": canonical_sha256(material)}


def validate_presented_external_authority_runtime_receipt(
    value: Any,
) -> dict[str, Any]:
    """Validate a serialized receipt and discard every execution truth."""

    if not isinstance(value, Mapping):
        raise P0ExternalAuthorityRuntimeSupervisorError(
            "presented external runtime receipt must be object"
        )
    row = _plain(value)
    stored = _sha(row.get("receipt_sha256"), "receipt_sha256")
    material = dict(row)
    material.pop("receipt_sha256", None)
    if stored != canonical_sha256(material):
        raise P0ExternalAuthorityRuntimeSupervisorError(
            "presented external runtime receipt hash mismatch"
        )
    expected_fields = {
        "schema_version",
        "execution_scope",
        "session_id",
        "run_id",
        "nonce_commitment_sha256",
        "owner_root_preauthorization_bytes_sha256",
        "external_trust_binding",
        "runtime_witness_binding",
        "combined_supervisor_binding",
        "child_bindings_sha256",
        "protected_category_root_projection",
        "protected_category_root_projection_sha256",
        "protected_category_final_path_projection_match",
        "trust_store_filesystem_execution_observed",
        "signature_verified_with_store_key",
        "single_use_replay_consumed",
        "nonce_ledger_action_applied",
        "power_loss_durable_replay_verified",
        "combined_direct_local_execution_observed",
        "runtime_witness_same_process_execution_observed",
        "qpc_monotonic_timeline_verified",
        "usn_interval_verified",
        "continuous_watch_verified",
        "os_write_deny_verified",
        "current_thread_restricted_token_write_open_denial_verified",
        "bounded_runtime_noninterference_verified",
        "runtime_noninterference_verified",
        "credited_counts",
        "security_control_state_mutated",
        "protected_pipeline_state_mutated",
        "operational_effect",
        "gate_status",
        "receipt_sha256",
        *_ALWAYS_FALSE_FIELDS,
    }
    if set(row) != expected_fields:
        raise P0ExternalAuthorityRuntimeSupervisorError(
            "presented external runtime receipt field inventory mismatch"
        )
    binding_schemas = {
        "external_trust_binding": external.EXECUTION_RECEIPT_SCHEMA,
        "runtime_witness_binding": runtime.RUNTIME_EVIDENCE_SCHEMA,
        "combined_supervisor_binding": combined.COMBINED_EXECUTION_SCHEMA,
    }
    bindings: list[dict[str, str]] = []
    for field, expected_schema in binding_schemas.items():
        child = row[field]
        if (
            not isinstance(child, Mapping)
            or set(child) != {"schema", "sha256"}
            or child.get("schema") != expected_schema
        ):
            raise P0ExternalAuthorityRuntimeSupervisorError(
                f"presented {field} is invalid"
            )
        bindings.append(
            {
                "schema": child["schema"],
                "sha256": _sha(child.get("sha256"), f"{field}.sha256"),
            }
        )
    if row["child_bindings_sha256"] != canonical_sha256(bindings):
        raise P0ExternalAuthorityRuntimeSupervisorError(
            "presented child binding aggregate mismatch"
        )
    projection = row["protected_category_root_projection"]
    if not isinstance(projection, list) or len(projection) != len(
        runtime.REQUIRED_PROTECTED_CATEGORIES
    ):
        raise P0ExternalAuthorityRuntimeSupervisorError(
            "presented protected root projection is invalid"
        )
    projected_matches: list[bool] = []
    for index, item in enumerate(projection):
        if (
            not isinstance(item, Mapping)
            or set(item)
            != {
                "category",
                "expected_final_path",
                "observed_final_path",
                "matched",
            }
            or item.get("category") != runtime.REQUIRED_PROTECTED_CATEGORIES[index]
            or not isinstance(item.get("expected_final_path"), str)
            or not item.get("expected_final_path")
            or (
                item.get("observed_final_path") is not None
                and not isinstance(item.get("observed_final_path"), str)
            )
            or type(item.get("matched")) is not bool
        ):
            raise P0ExternalAuthorityRuntimeSupervisorError(
                "presented protected root projection row is invalid"
            )
        observed_path = item["observed_final_path"]
        calculated_match = bool(
            observed_path is not None
            and _normalise_windows_path(
                observed_path, "presented observed final path"
            )
            == _normalise_windows_path(
                item["expected_final_path"], "presented expected final path"
            )
        )
        if item["matched"] != calculated_match:
            raise P0ExternalAuthorityRuntimeSupervisorError(
                "presented protected root projection match is inconsistent"
            )
        projected_matches.append(item["matched"])
    if (
        row["protected_category_root_projection_sha256"]
        != canonical_sha256(projection)
        or row["protected_category_final_path_projection_match"]
        != all(projected_matches)
    ):
        raise P0ExternalAuthorityRuntimeSupervisorError(
            "presented protected root projection binding mismatch"
        )
    boolean_fields = {
        "protected_category_final_path_projection_match",
        "trust_store_filesystem_execution_observed",
        "signature_verified_with_store_key",
        "single_use_replay_consumed",
        "nonce_ledger_action_applied",
        "power_loss_durable_replay_verified",
        "combined_direct_local_execution_observed",
        "runtime_witness_same_process_execution_observed",
        "qpc_monotonic_timeline_verified",
        "usn_interval_verified",
        "continuous_watch_verified",
        "os_write_deny_verified",
        "current_thread_restricted_token_write_open_denial_verified",
        "bounded_runtime_noninterference_verified",
        "runtime_noninterference_verified",
        "security_control_state_mutated",
        "protected_pipeline_state_mutated",
        *_ALWAYS_FALSE_FIELDS,
    }
    if any(type(row.get(field)) is not bool for field in boolean_fields):
        raise P0ExternalAuthorityRuntimeSupervisorError(
            "presented external runtime receipt boolean type mismatch"
        )
    fixed_true = (
        "trust_store_filesystem_execution_observed",
        "signature_verified_with_store_key",
        "single_use_replay_consumed",
        "nonce_ledger_action_applied",
        "combined_direct_local_execution_observed",
        "runtime_witness_same_process_execution_observed",
        "security_control_state_mutated",
    )
    fixed_false = (
        "power_loss_durable_replay_verified",
        "os_write_deny_verified",
        "bounded_runtime_noninterference_verified",
        "runtime_noninterference_verified",
        "protected_pipeline_state_mutated",
        *_ALWAYS_FALSE_FIELDS,
    )
    if any(row[field] is not True for field in fixed_true) or any(
        row[field] is not False for field in fixed_false
    ):
        raise P0ExternalAuthorityRuntimeSupervisorError(
            "presented external runtime receipt fixed invariant mismatch"
        )
    if (
        row.get("schema_version") != EXECUTION_RECEIPT_SCHEMA
        or row.get("execution_scope") != EXECUTION_SCOPE
        or _identifier(row.get("session_id"), "session_id") != row.get("session_id")
        or _identifier(row.get("run_id"), "run_id") != row.get("run_id")
        or _sha(row.get("nonce_commitment_sha256"), "nonce_commitment_sha256")
        != row.get("nonce_commitment_sha256")
        or _sha(
            row.get("owner_root_preauthorization_bytes_sha256"),
            "owner_root_preauthorization_bytes_sha256",
        )
        != row.get("owner_root_preauthorization_bytes_sha256")
        or row.get("gate_status") != GATE_STATUS
        or row.get("operational_effect")
        != "NONCE_LEDGER_CONSUMED_PIPELINE_SHADOW_ONLY"
        or row.get("credited_counts")
        != {"actual_source_claim_count": 0, "actual_a_context_review_count": 0}
        or any(row.get(field) is not False for field in _ALWAYS_FALSE_FIELDS)
    ):
        raise P0ExternalAuthorityRuntimeSupervisorError(
            "presented external runtime receipt structure/gate overclaim"
        )
    binding = {
        "schema_version": PRESENTED_VALIDATION_SCHEMA,
        "presented_receipt_sha256": stored,
        "presented_structure_verified": True,
        "underlying_execution_verified": False,
        "trust_store_filesystem_execution_observed": False,
        "signature_verified_with_store_key": False,
        "single_use_replay_consumed": False,
        "nonce_ledger_action_applied": False,
        "combined_direct_local_execution_observed": False,
        "runtime_witness_same_process_execution_observed": False,
        "qpc_monotonic_timeline_verified": False,
        "usn_interval_verified": False,
        "continuous_watch_verified": False,
        "os_write_deny_verified": False,
        "current_thread_restricted_token_write_open_denial_verified": False,
        "bounded_runtime_noninterference_verified": False,
        "runtime_noninterference_verified": False,
        **{field: False for field in _ALWAYS_FALSE_FIELDS},
        "credited_counts": {
            "actual_source_claim_count": 0,
            "actual_a_context_review_count": 0,
        },
        "operational_effect": "NONE_PRESENTED_RECEIPT_ONLY",
        "gate_status": PRESENTED_GATE_STATUS,
    }
    return {**binding, "receipt_sha256": canonical_sha256(binding)}


__all__ = [
    "EXECUTION_RECEIPT_SCHEMA",
    "EXECUTION_SCOPE",
    "GATE_STATUS",
    "P0ExternalAuthorityRuntimeSupervisorError",
    "PRESENTED_GATE_STATUS",
    "PRESENTED_VALIDATION_SCHEMA",
    "canonical_bytes",
    "canonical_sha256",
    "execute_external_authority_runtime_supervisor_trace",
    "validate_presented_external_authority_runtime_receipt",
]
