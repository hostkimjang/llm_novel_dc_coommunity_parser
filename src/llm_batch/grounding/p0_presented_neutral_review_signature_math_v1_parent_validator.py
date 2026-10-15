"""Independent parent replay for presented neutral-review signature math v1.

This module intentionally does not import the producer contract.  It reparses
all four raw artifacts, reconstructs every projection and receipt field, and
re-executes the provider-fixed Windows CNG verification.  Its successful result
remains a component-only replay, not external review authority.
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
from typing import Any, Mapping

from . import p0_windows_cng_ecdsa_p256 as cng_p256


COMPONENT_VERSION = "presented-neutral-review-signature-math-v1"
PUBLIC_KEY_PIN_SCHEMA = "p0_presented_neutral_review_signature_key_pin_v1"
SUBJECT_SCHEMA = "p0_presented_neutral_review_signature_subject_v1"
SIGNATURE_ENVELOPE_SCHEMA = "p0_presented_neutral_review_signature_envelope_v1"
VALIDATION_RECEIPT_SCHEMA = "p0_presented_neutral_review_signature_math_receipt_v1"
PARENT_RECEIPT_SCHEMA = "p0_presented_neutral_review_signature_math_parent_receipt_v1"

RECORD_ORIGIN = "ACTUAL_SCHEMA_CONTRACT_EXAMPLE_ONLY"
PRESENTED_PIN_ORIGIN = "PRESENTED_NEUTRAL_REVIEW_SIGNATURE_PIN_CANDIDATE"
PRESENTED_SUBJECT_ORIGIN = "PRESENTED_NEUTRAL_REVIEW_SIGNATURE_SUBJECT_CANDIDATE"
PRESENTED_SIGNATURE_ORIGIN = "PRESENTED_NEUTRAL_REVIEW_SIGNATURE_CANDIDATE"
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
ALGORITHM = "ECDSA_P256_SHA256_CNG_V1"
CURVE = "NIST_P256"
CNG_PROVIDER = "Microsoft Primitive Provider"
COORDINATE_ENCODING = "P256_XY32_BIG_ENDIAN_BASE64_V1"
FINGERPRINT_ENCODING = "RFC5480_DER_SPKI_SHA256_V1"
GATE_STATUS = (
    "NO_GO_EXTERNAL_REVIEW_AUTHORITY_SIGNATURE_MATH_AND_RAW_BINDING_ONLY"
)

_PROFILES: dict[str, tuple[str, str, str]] = {
    "CAMPAIGN_POLICY_PREAUTHORIZATION": (
        "REVIEW_POLICY_PREAUTH_SIGNING_ONLY",
        "P0_NEUTRAL_REVIEW_CAMPAIGN_POLICY_PREAUTHORIZATION",
        "llm-novel-dc-community-parser/p0-neutral-review-policy-preauth-signature/v1",
    ),
    "REVIEW_LEASE": (
        "REVIEW_LEASE_SIGNING_ONLY",
        "P0_NEUTRAL_REVIEW_LEASE",
        "llm-novel-dc-community-parser/p0-neutral-review-lease-signature/v1",
    ),
    "HUMAN_REVIEW_RESULT": (
        "HUMAN_REVIEW_RESULT_SIGNING_ONLY",
        "P0_NEUTRAL_HUMAN_REVIEW_RESULT",
        "llm-novel-dc-community-parser/p0-neutral-human-review-result-signature/v1",
    ),
    "FINAL_REVIEW_ATTESTATION": (
        "REVIEW_FINAL_ATTESTATION_SIGNING_ONLY",
        "P0_NEUTRAL_REVIEW_FINAL_ATTESTATION",
        "llm-novel-dc-community-parser/p0-neutral-review-final-attestation-signature/v1",
    ),
}
_FALSE_FIELDS = (
    "external_key_provisioning_verified",
    "external_authority_anchor_verified",
    "signer_identity_verified",
    "reviewer_identity_verified",
    "reviewer_independence_verified",
    "reviewer_blinding_verified",
    "human_judgment_factuality_verified",
    "payload_semantics_verified",
    "trusted_time_verified",
    "revocation_state_verified",
    "durable_replay_prevention_verified",
    "code_identity_verified",
    "dependency_closure_verified",
    "trusted_cng_provider_provenance_verified",
    "process_isolation_verified",
    "runtime_execution_authority_verified",
    "serialized_receipt_authoritative",
    "execution_trace_transferable_by_receipt",
    "actual_human_review_verified",
    "actual_source_evidence_verified",
    "metric_eligibility_verified",
    "single_signature_is_review_evidence",
    "cross_role_cryptographic_key_separation_verified",
    "cross_role_key_separation_verified",
    "review_chain_verified",
    "workflow_lineage_verified",
    "review_accounting_binding_verified",
    "dual_blind_primary_pair_verified",
    "dual_blind_quorum_verified",
    "adjudication_verified",
    "disagreement_adjudication_verified",
    "retrospective_actualization_allowed",
    "presented_accounting_receipt_upgrade_permitted",
    "descriptive_metrics_allowed",
    "descriptive_quality_metrics_allowed",
    "inferential_metrics_allowed",
    "complete_case_metrics_allowed",
    "semantic_metrics_allowed",
    "actual_authority_granted",
    "p0_phase_exit",
    "production_approval",
    "full_scan_approval",
)
_PIN_FIELDS = frozenset(
    {
        "schema_version", "record_origin", "component_version", "signature_kind",
        "trust_domain", "project_id", "environment", "purpose", "key_role",
        "key_id", "key_epoch", "algorithm", "curve", "cng_provider",
        "coordinate_encoding", "fingerprint_encoding", "public_key_x_base64",
        "public_key_y_base64", "public_key_fingerprint_sha256",
        "signer_principal_commitment_sha256", "authority_anchor_sha256",
        "allowed_signature_domains", "presented_revocation_snapshot_raw_sha256",
        "artifact_sha256",
    }
)
_SUBJECT_FIELDS = frozenset(
    {
        "schema_version", "record_origin", "component_version", "signature_kind",
        "domain", "trust_domain", "project_id", "environment", "purpose",
        "key_role", "campaign_id", "run_id", "subject_id", "presented_issued_at",
        "nonce_commitment_sha256", "payload_schema", "payload_bytes",
        "payload_raw_sha256", "payload_artifact_sha256",
        "predecessor_subject_raw_sha256", "caller_presented_subject_only",
        "external_authority_claimed", "actual_human_review_claimed",
        "semantic_promotion_claimed", "action_applied", "operational_effect",
        "artifact_sha256",
    }
)
_ENVELOPE_FIELDS = frozenset(
    {
        "schema_version", "record_origin", "component_version", "signature_kind",
        "domain", "trust_domain", "project_id", "environment", "purpose",
        "key_role", "campaign_id", "run_id", "subject_id", "key_id", "key_epoch",
        "algorithm", "public_key_fingerprint_sha256",
        "signer_principal_commitment_sha256", "public_key_pin_raw_sha256",
        "public_key_pin_artifact_sha256", "subject_schema", "subject_bytes",
        "subject_raw_sha256", "subject_artifact_sha256", "payload_raw_sha256",
        "signature_rs_base64", "artifact_sha256",
    }
)

_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_MAX_BYTES = 1024 * 1024
_P256_ORDER = int(
    "ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551",
    16,
)
_SPKI_PREFIX = bytes.fromhex(
    "3059301306072a8648ce3d020106082a8648ce3d03010703420004"
)
_FORBIDDEN_PAYLOAD_FIELDS = frozenset(
    {
        "target_work_id", "target_sense_id", "work_id", "sense_id",
        "alias_relation", "nil_status", "retrieval_query", "route_class",
        "route_decision", "packet_credit", "ledger_credit", "publication_decision",
        "production_approval", "full_scan_approval", "p0_phase_exit",
        "actual_authority_granted", "actual_human_review_verified",
        "actual_source_evidence_verified", "metric_eligibility_verified",
        "semantic_promotion_claimed", "source_credit_count", "actual_human_review_count",
        "actual_context_credit_count", "actual_human_unreviewed_input_count",
        "actual_primary_review_event_count", "actual_pair_complete_input_count",
        "actual_adjudicated_input_count", "actual_judged_input_count",
        "statistical_denominator_contribution", "successor_campaign_new_precommit_required",
        "metric_gate_status", "gate_status", *_FALSE_FIELDS,
    }
)


class P0PresentedNeutralReviewSignatureMathV1ParentError(ValueError):
    """Independent parent replay rejected the presented bundle."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise P0PresentedNeutralReviewSignatureMathV1ParentError(
            "value is not canonical JSON data"
        ) from exc


def _canonical_sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _raw_sha(raw: bytes) -> str:
    if type(raw) is not bytes:
        raise P0PresentedNeutralReviewSignatureMathV1ParentError("raw value must be bytes")
    return hashlib.sha256(raw).hexdigest()


def _duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise P0PresentedNeutralReviewSignatureMathV1ParentError(
                f"duplicate JSON key is forbidden: {key}"
            )
        output[key] = value
    return output


def _nonfinite(token: str) -> None:
    raise P0PresentedNeutralReviewSignatureMathV1ParentError(
        f"non-finite JSON constant is forbidden: {token}"
    )


def _parse(raw: bytes, label: str) -> dict[str, Any]:
    if (
        type(raw) is not bytes or not raw or len(raw) > _MAX_BYTES
        or raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or not raw.endswith(b"\n")
    ):
        raise P0PresentedNeutralReviewSignatureMathV1ParentError(f"{label} framing is invalid")
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_duplicates, parse_constant=_nonfinite
        )
    except P0PresentedNeutralReviewSignatureMathV1ParentError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise P0PresentedNeutralReviewSignatureMathV1ParentError(
            f"{label} must be strict UTF-8 JSON"
        ) from exc
    if not isinstance(value, dict) or raw != _canonical(value) + b"\n":
        raise P0PresentedNeutralReviewSignatureMathV1ParentError(
            f"{label} must be canonical JSON plus LF"
        )
    return value


def _strict(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or frozenset(value) != fields:
        raise P0PresentedNeutralReviewSignatureMathV1ParentError(f"{label} fields mismatch")
    return dict(value)


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA_RE.fullmatch(value) is None:
        raise P0PresentedNeutralReviewSignatureMathV1ParentError(f"{label} is not SHA-256")
    return value


def _ident(value: Any, label: str) -> str:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise P0PresentedNeutralReviewSignatureMathV1ParentError(f"{label} is invalid")
    return value


def _pos(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise P0PresentedNeutralReviewSignatureMathV1ParentError(f"{label} is invalid")
    return value


def _utc(value: Any, label: str) -> str:
    if not isinstance(value, str) or _TIME_RE.fullmatch(value) is None:
        raise P0PresentedNeutralReviewSignatureMathV1ParentError(f"{label} is invalid")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise P0PresentedNeutralReviewSignatureMathV1ParentError(
            f"{label} is not a real UTC timestamp"
        ) from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise P0PresentedNeutralReviewSignatureMathV1ParentError(f"{label} is invalid")
    return value


def _reject_payload_promotion(value: Any, *, depth: int = 0) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if isinstance(key, str):
                lowered = key.lower()
                if (
                    lowered in _FORBIDDEN_PAYLOAD_FIELDS
                    or lowered.endswith("_verified")
                    or lowered.endswith("_approval")
                    or lowered.endswith("_allowed")
                    or lowered.startswith("actual_")
                    or (depth > 0 and lowered in {"action_applied", "operational_effect"})
                ):
                    raise P0PresentedNeutralReviewSignatureMathV1ParentError(
                        f"payload semantic/operational field is forbidden: {key}"
                    )
            _reject_payload_promotion(item, depth=depth + 1)
    elif isinstance(value, list):
        for item in value:
            _reject_payload_promotion(item, depth=depth + 1)


def _profile(kind: Any) -> tuple[str, str, str]:
    if not isinstance(kind, str) or kind not in _PROFILES:
        raise P0PresentedNeutralReviewSignatureMathV1ParentError("signature kind is invalid")
    return _PROFILES[kind]


def _self_hash(row: Mapping[str, Any], label: str) -> str:
    stored = _sha(row.get("artifact_sha256"), f"{label}.artifact_sha256")
    material = {key: value for key, value in row.items() if key != "artifact_sha256"}
    if not hmac.compare_digest(stored, _canonical_sha(material)):
        raise P0PresentedNeutralReviewSignatureMathV1ParentError(f"{label} self-hash mismatch")
    return stored


def _b64(value: Any, length: int, label: str) -> bytes:
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        raise P0PresentedNeutralReviewSignatureMathV1ParentError(f"{label} base64 is invalid")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise P0PresentedNeutralReviewSignatureMathV1ParentError(
            f"{label} base64 is invalid"
        ) from exc
    if len(decoded) != length or base64.b64encode(decoded).decode("ascii") != value:
        raise P0PresentedNeutralReviewSignatureMathV1ParentError(f"{label} width is invalid")
    return decoded


def _projection(left: Mapping[str, Any], right: Mapping[str, Any], label: str) -> None:
    for field in ("signature_kind", "trust_domain", "project_id", "environment", "purpose", "key_role"):
        if left[field] != right[field]:
            raise P0PresentedNeutralReviewSignatureMathV1ParentError(
                f"{label} projection mismatch: {field}"
            )


def _validate_pin(row: dict[str, Any]) -> tuple[dict[str, Any], bytes, bytes]:
    row = _strict(row, _PIN_FIELDS, "pin")
    role, purpose, domain = _profile(row["signature_kind"])
    fixed = (
        row["schema_version"] == PUBLIC_KEY_PIN_SCHEMA
        and row["record_origin"] == PRESENTED_PIN_ORIGIN
        and row["component_version"] == COMPONENT_VERSION
        and row["purpose"] == purpose and row["key_role"] == role
        and row["algorithm"] == ALGORITHM and row["curve"] == CURVE
        and row["cng_provider"] == CNG_PROVIDER
        and row["coordinate_encoding"] == COORDINATE_ENCODING
        and row["fingerprint_encoding"] == FINGERPRINT_ENCODING
        and row["allowed_signature_domains"] == [domain]
    )
    if not fixed:
        raise P0PresentedNeutralReviewSignatureMathV1ParentError("pin profile mismatch")
    for field in ("trust_domain", "project_id", "environment", "key_id"):
        _ident(row[field], f"pin.{field}")
    _pos(row["key_epoch"], "pin.key_epoch")
    x = _b64(row["public_key_x_base64"], 32, "pin.x")
    y = _b64(row["public_key_y_base64"], 32, "pin.y")
    fingerprint = hashlib.sha256(_SPKI_PREFIX + x + y).hexdigest()
    if not hmac.compare_digest(
        _sha(row["public_key_fingerprint_sha256"], "pin.fingerprint"), fingerprint
    ):
        raise P0PresentedNeutralReviewSignatureMathV1ParentError("pin fingerprint mismatch")
    for field in (
        "signer_principal_commitment_sha256", "authority_anchor_sha256",
        "presented_revocation_snapshot_raw_sha256",
    ):
        _sha(row[field], f"pin.{field}")
    _self_hash(row, "pin")
    return row, x, y


def _validate_subject(row: dict[str, Any], payload_raw: bytes) -> dict[str, Any]:
    row = _strict(row, _SUBJECT_FIELDS, "subject")
    role, purpose, domain = _profile(row["signature_kind"])
    fixed = (
        row["schema_version"] == SUBJECT_SCHEMA
        and row["record_origin"] == PRESENTED_SUBJECT_ORIGIN
        and row["component_version"] == COMPONENT_VERSION
        and row["domain"] == domain and row["purpose"] == purpose and row["key_role"] == role
        and row["caller_presented_subject_only"] is True
        and row["external_authority_claimed"] is False
        and row["actual_human_review_claimed"] is False
        and row["semantic_promotion_claimed"] is False
        and row["action_applied"] is False and row["operational_effect"] == OPERATIONAL_EFFECT
    )
    if not fixed:
        raise P0PresentedNeutralReviewSignatureMathV1ParentError("subject profile mismatch")
    for field in ("trust_domain", "project_id", "environment", "campaign_id", "run_id", "subject_id", "payload_schema"):
        _ident(row[field], f"subject.{field}")
    _utc(row["presented_issued_at"], "subject.presented_issued_at")
    _sha(row["nonce_commitment_sha256"], "subject.nonce")
    if row["predecessor_subject_raw_sha256"] is not None:
        _sha(row["predecessor_subject_raw_sha256"], "subject.predecessor")
    payload = _parse(payload_raw, "payload")
    _reject_payload_promotion(payload)
    if (
        payload.get("record_origin") != RECORD_ORIGIN
        or payload.get("action_applied") is not False
        or payload.get("operational_effect") != OPERATIONAL_EFFECT
    ):
        raise P0PresentedNeutralReviewSignatureMathV1ParentError(
            "payload is not a no-effect presented contract artifact"
        )
    payload_artifact = _self_hash(payload, "payload")
    _pos(row["payload_bytes"], "subject.payload_bytes")
    for field in ("payload_raw_sha256", "payload_artifact_sha256"):
        _sha(row[field], f"subject.{field}")
    if (
        row["payload_schema"] != payload.get("schema_version")
        or row["payload_bytes"] != len(payload_raw)
        or row["payload_raw_sha256"] != _raw_sha(payload_raw)
        or row["payload_artifact_sha256"] != payload_artifact
    ):
        raise P0PresentedNeutralReviewSignatureMathV1ParentError("subject payload binding mismatch")
    _self_hash(row, "subject")
    return row


def _validate_envelope(row: dict[str, Any]) -> tuple[dict[str, Any], bytes, bytes]:
    row = _strict(row, _ENVELOPE_FIELDS, "envelope")
    role, purpose, domain = _profile(row["signature_kind"])
    if not (
        row["schema_version"] == SIGNATURE_ENVELOPE_SCHEMA
        and row["record_origin"] == PRESENTED_SIGNATURE_ORIGIN
        and row["component_version"] == COMPONENT_VERSION
        and row["domain"] == domain and row["purpose"] == purpose and row["key_role"] == role
        and row["algorithm"] == ALGORITHM and row["subject_schema"] == SUBJECT_SCHEMA
    ):
        raise P0PresentedNeutralReviewSignatureMathV1ParentError("envelope profile mismatch")
    for field in ("trust_domain", "project_id", "environment", "campaign_id", "run_id", "subject_id", "key_id"):
        _ident(row[field], f"envelope.{field}")
    _pos(row["key_epoch"], "envelope.key_epoch")
    _pos(row["subject_bytes"], "envelope.subject_bytes")
    for field in (
        "public_key_fingerprint_sha256", "signer_principal_commitment_sha256",
        "public_key_pin_raw_sha256", "public_key_pin_artifact_sha256",
        "subject_raw_sha256", "subject_artifact_sha256", "payload_raw_sha256",
    ):
        _sha(row[field], f"envelope.{field}")
    signature = _b64(row["signature_rs_base64"], 64, "envelope.signature")
    r = int.from_bytes(signature[:32], "big")
    s = int.from_bytes(signature[32:], "big")
    if not 0 < r < _P256_ORDER or not 0 < s <= _P256_ORDER // 2:
        raise P0PresentedNeutralReviewSignatureMathV1ParentError("signature is not canonical low-S")
    _self_hash(row, "envelope")
    material = {
        key: value for key, value in row.items()
        if key not in {"signature_rs_base64", "artifact_sha256"}
    }
    return row, signature, _canonical(material)


def validate_presented_neutral_review_signature_math_against_raw_inputs(
    *,
    public_key_pin_raw: bytes,
    subject_raw: bytes,
    payload_raw: bytes,
    signature_envelope_raw: bytes,
    component_receipt_raw: bytes,
    expected_signature_kind: str,
    expected_public_key_pin_raw_sha256: str,
    expected_subject_raw_sha256: str,
) -> dict[str, Any]:
    """Independently replay the raw bundle and exact child receipt."""

    _profile(expected_signature_kind)
    _sha(expected_public_key_pin_raw_sha256, "expected pin sha")
    _sha(expected_subject_raw_sha256, "expected subject sha")
    pin_raw_sha = _raw_sha(public_key_pin_raw)
    subject_raw_sha = _raw_sha(subject_raw)
    if pin_raw_sha != expected_public_key_pin_raw_sha256 or subject_raw_sha != expected_subject_raw_sha256:
        raise P0PresentedNeutralReviewSignatureMathV1ParentError("caller expectation mismatch")
    pin, x, y = _validate_pin(_parse(public_key_pin_raw, "pin"))
    subject = _validate_subject(_parse(subject_raw, "subject"), payload_raw)
    envelope, signature, signature_input = _validate_envelope(
        _parse(signature_envelope_raw, "envelope")
    )
    child = _parse(component_receipt_raw, "component receipt")
    if pin["signature_kind"] != expected_signature_kind or subject["signature_kind"] != expected_signature_kind:
        raise P0PresentedNeutralReviewSignatureMathV1ParentError("expected kind mismatch")
    _projection(pin, subject, "pin/subject")
    _projection(pin, envelope, "pin/envelope")
    _projection(subject, envelope, "subject/envelope")
    exact = {
        "campaign_id": subject["campaign_id"], "run_id": subject["run_id"],
        "subject_id": subject["subject_id"], "key_id": pin["key_id"],
        "key_epoch": pin["key_epoch"],
        "public_key_fingerprint_sha256": pin["public_key_fingerprint_sha256"],
        "signer_principal_commitment_sha256": pin["signer_principal_commitment_sha256"],
        "public_key_pin_raw_sha256": pin_raw_sha,
        "public_key_pin_artifact_sha256": pin["artifact_sha256"],
        "subject_bytes": len(subject_raw), "subject_raw_sha256": subject_raw_sha,
        "subject_artifact_sha256": subject["artifact_sha256"],
        "payload_raw_sha256": subject["payload_raw_sha256"],
    }
    for field, expected in exact.items():
        if envelope[field] != expected:
            raise P0PresentedNeutralReviewSignatureMathV1ParentError(
                f"envelope exact binding mismatch: {field}"
            )
    try:
        cng_p256.verify_p256_sha256(
            public_key_x=x, public_key_y=y,
            digest=hashlib.sha256(signature_input).digest(), signature=signature,
        )
    except cng_p256.P0WindowsCngEcdsaP256Error as exc:
        raise P0PresentedNeutralReviewSignatureMathV1ParentError(str(exc)) from exc
    expected_material: dict[str, Any] = {
        "schema_version": VALIDATION_RECEIPT_SCHEMA,
        "record_origin": RECORD_ORIGIN,
        "component_version": COMPONENT_VERSION,
        "signature_kind": subject["signature_kind"], "domain": subject["domain"],
        "purpose": subject["purpose"], "key_role": subject["key_role"],
        "trust_domain": subject["trust_domain"], "project_id": subject["project_id"],
        "environment": subject["environment"], "campaign_id": subject["campaign_id"],
        "run_id": subject["run_id"], "subject_id": subject["subject_id"],
        "key_id": pin["key_id"], "key_epoch": pin["key_epoch"],
        "public_key_fingerprint_sha256": pin["public_key_fingerprint_sha256"],
        "signer_principal_commitment_sha256": pin["signer_principal_commitment_sha256"],
        "authority_anchor_sha256": pin["authority_anchor_sha256"],
        "presented_revocation_snapshot_raw_sha256": pin["presented_revocation_snapshot_raw_sha256"],
        "public_key_pin_bytes": len(public_key_pin_raw), "public_key_pin_raw_sha256": pin_raw_sha,
        "public_key_pin_artifact_sha256": pin["artifact_sha256"],
        "subject_bytes": len(subject_raw), "subject_raw_sha256": subject_raw_sha,
        "subject_artifact_sha256": subject["artifact_sha256"],
        "payload_bytes": len(payload_raw), "payload_raw_sha256": subject["payload_raw_sha256"],
        "payload_artifact_sha256": subject["payload_artifact_sha256"],
        "signature_envelope_bytes": len(signature_envelope_raw),
        "signature_envelope_raw_sha256": _raw_sha(signature_envelope_raw),
        "signature_envelope_artifact_sha256": envelope["artifact_sha256"],
        "signature_input_sha256": hashlib.sha256(signature_input).hexdigest(),
        "algorithm": ALGORITHM, "curve": CURVE, "cng_provider": CNG_PROVIDER,
        "caller_presented_pin_only": True, "caller_presented_revocation_only": True,
        "expected_pin_and_subject_are_caller_arguments": True,
        "signature_kind_role_domain_exactly_mapped": True,
        "payload_forbidden_semantic_promotion_fields_absent": True,
        "canonical_raw_binding_verified": True,
        "rfc5480_public_key_fingerprint_verified": True,
        "canonical_low_s_signature_verified": True,
        "asymmetric_signature_math_verified": True,
        **{field: False for field in _FALSE_FIELDS},
        "successor_campaign_new_precommit_required": True,
        "statistical_denominator_contribution": "NONE",
        "actual_human_review_count": 0, "actual_context_credit_count": 0,
        "actual_human_unreviewed_input_count": 40,
        "actual_primary_review_event_count": 0,
        "actual_pair_complete_input_count": 0,
        "actual_adjudicated_input_count": 0,
        "actual_judged_input_count": 0,
        "actual_source_credit_count": 0,
        "metric_gate_status": "NOT_ESTIMABLE_ACTUAL_REVIEW_AUTHORITY_ABSENT",
        "gate_status": GATE_STATUS, "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    expected_child = {**expected_material, "receipt_sha256": _canonical_sha(expected_material)}
    if child != expected_child:
        raise P0PresentedNeutralReviewSignatureMathV1ParentError(
            "component receipt differs from independent reconstruction"
        )
    parent_material = {
        "schema_version": PARENT_RECEIPT_SCHEMA,
        "record_origin": RECORD_ORIGIN,
        "component_version": COMPONENT_VERSION,
        "component_receipt_raw_sha256": _raw_sha(component_receipt_raw),
        "component_receipt_sha256": child["receipt_sha256"],
        "signature_kind": subject["signature_kind"],
        "signature_input_sha256": hashlib.sha256(signature_input).hexdigest(),
        "parent_separate_implementation_raw_replay_verified": True,
        "parent_reexecuted_windows_cng_signature_math": True,
        "parent_imports_producer_contract": False,
        **{field: False for field in _FALSE_FIELDS},
        "successor_campaign_new_precommit_required": True,
        "statistical_denominator_contribution": "NONE",
        "actual_human_review_count": 0,
        "actual_context_credit_count": 0,
        "actual_human_unreviewed_input_count": 40,
        "actual_primary_review_event_count": 0,
        "actual_pair_complete_input_count": 0,
        "actual_adjudicated_input_count": 0,
        "actual_judged_input_count": 0,
        "actual_source_credit_count": 0,
        "metric_gate_status": "NOT_ESTIMABLE_ACTUAL_REVIEW_AUTHORITY_ABSENT",
        "gate_status": GATE_STATUS,
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    return {**parent_material, "receipt_sha256": _canonical_sha(parent_material)}


__all__ = [
    "P0PresentedNeutralReviewSignatureMathV1ParentError",
    "PARENT_RECEIPT_SCHEMA",
    "validate_presented_neutral_review_signature_math_against_raw_inputs",
]
