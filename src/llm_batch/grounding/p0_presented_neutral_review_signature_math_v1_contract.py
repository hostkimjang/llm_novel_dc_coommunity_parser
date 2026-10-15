"""Domain-separated signature-math component for future neutral review evidence.

The caller presents a public-key pin, an exact canonical subject, the subject's
exact canonical payload, and an ECDSA P-256 signature envelope.  This module
checks structural projections, raw-byte bindings, RFC 5480 key fingerprinting,
canonical low-S form, and signature mathematics with the provider-fixed Windows
CNG verifier.

This is deliberately not an authority component.  The pin, revocation digest,
clock text, signer commitment, and all reviewed content are caller-presented.
Success proves neither reviewer identity/independence nor human judgment,
external provisioning, freshness, durable replay prevention, actual evidence,
metric eligibility, P0 exit, or permission to mutate operational state.
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

CAMPAIGN_POLICY_PREAUTHORIZATION = "CAMPAIGN_POLICY_PREAUTHORIZATION"
REVIEW_LEASE = "REVIEW_LEASE"
HUMAN_REVIEW_RESULT = "HUMAN_REVIEW_RESULT"
FINAL_REVIEW_ATTESTATION = "FINAL_REVIEW_ATTESTATION"

SIGNATURE_PROFILE: dict[str, tuple[str, str, str]] = {
    CAMPAIGN_POLICY_PREAUTHORIZATION: (
        "REVIEW_POLICY_PREAUTH_SIGNING_ONLY",
        "P0_NEUTRAL_REVIEW_CAMPAIGN_POLICY_PREAUTHORIZATION",
        "llm-novel-dc-community-parser/p0-neutral-review-policy-preauth-signature/v1",
    ),
    REVIEW_LEASE: (
        "REVIEW_LEASE_SIGNING_ONLY",
        "P0_NEUTRAL_REVIEW_LEASE",
        "llm-novel-dc-community-parser/p0-neutral-review-lease-signature/v1",
    ),
    HUMAN_REVIEW_RESULT: (
        "HUMAN_REVIEW_RESULT_SIGNING_ONLY",
        "P0_NEUTRAL_HUMAN_REVIEW_RESULT",
        "llm-novel-dc-community-parser/p0-neutral-human-review-result-signature/v1",
    ),
    FINAL_REVIEW_ATTESTATION: (
        "REVIEW_FINAL_ATTESTATION_SIGNING_ONLY",
        "P0_NEUTRAL_REVIEW_FINAL_ATTESTATION",
        "llm-novel-dc-community-parser/p0-neutral-review-final-attestation-signature/v1",
    ),
}

_FALSE_TRUTH_FIELDS = (
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
        "schema_version",
        "record_origin",
        "component_version",
        "signature_kind",
        "trust_domain",
        "project_id",
        "environment",
        "purpose",
        "key_role",
        "key_id",
        "key_epoch",
        "algorithm",
        "curve",
        "cng_provider",
        "coordinate_encoding",
        "fingerprint_encoding",
        "public_key_x_base64",
        "public_key_y_base64",
        "public_key_fingerprint_sha256",
        "signer_principal_commitment_sha256",
        "authority_anchor_sha256",
        "allowed_signature_domains",
        "presented_revocation_snapshot_raw_sha256",
        "artifact_sha256",
    }
)
_SUBJECT_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "component_version",
        "signature_kind",
        "domain",
        "trust_domain",
        "project_id",
        "environment",
        "purpose",
        "key_role",
        "campaign_id",
        "run_id",
        "subject_id",
        "presented_issued_at",
        "nonce_commitment_sha256",
        "payload_schema",
        "payload_bytes",
        "payload_raw_sha256",
        "payload_artifact_sha256",
        "predecessor_subject_raw_sha256",
        "caller_presented_subject_only",
        "external_authority_claimed",
        "actual_human_review_claimed",
        "semantic_promotion_claimed",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)
_ENVELOPE_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "component_version",
        "signature_kind",
        "domain",
        "trust_domain",
        "project_id",
        "environment",
        "purpose",
        "key_role",
        "campaign_id",
        "run_id",
        "subject_id",
        "key_id",
        "key_epoch",
        "algorithm",
        "public_key_fingerprint_sha256",
        "signer_principal_commitment_sha256",
        "public_key_pin_raw_sha256",
        "public_key_pin_artifact_sha256",
        "subject_schema",
        "subject_bytes",
        "subject_raw_sha256",
        "subject_artifact_sha256",
        "payload_raw_sha256",
        "signature_rs_base64",
        "artifact_sha256",
    }
)

_MAX_JSON_BYTES = 1024 * 1024
_MAX_PAYLOAD_BYTES = 1024 * 1024
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_P256_ORDER = int(
    "ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551",
    16,
)
_P256_SPKI_PREFIX = bytes.fromhex(
    "3059301306072a8648ce3d020106082a8648ce3d03010703420004"
)
_FORBIDDEN_PAYLOAD_FIELDS = frozenset(
    {
        "target_work_id",
        "target_sense_id",
        "work_id",
        "sense_id",
        "alias_relation",
        "nil_status",
        "retrieval_query",
        "route_class",
        "route_decision",
        "packet_credit",
        "ledger_credit",
        "publication_decision",
        "production_approval",
        "full_scan_approval",
        "p0_phase_exit",
        "actual_authority_granted",
        "actual_human_review_verified",
        "actual_source_evidence_verified",
        "metric_eligibility_verified",
        "semantic_promotion_claimed",
        "source_credit_count",
        "actual_human_review_count",
        "actual_context_credit_count",
        "actual_human_unreviewed_input_count",
        "actual_primary_review_event_count",
        "actual_pair_complete_input_count",
        "actual_adjudicated_input_count",
        "actual_judged_input_count",
        "statistical_denominator_contribution",
        "successor_campaign_new_precommit_required",
        "metric_gate_status",
        "gate_status",
        *_FALSE_TRUTH_FIELDS,
    }
)


class P0PresentedNeutralReviewSignatureMathV1Error(ValueError):
    """Presented review signature evidence failed the component contract."""


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise P0PresentedNeutralReviewSignatureMathV1Error(
            "value is not canonical JSON data"
        ) from exc


def canonical_file_bytes(value: Any) -> bytes:
    return canonical_bytes(value) + b"\n"


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def raw_sha256(raw: bytes) -> str:
    if type(raw) is not bytes:
        raise P0PresentedNeutralReviewSignatureMathV1Error("raw value must be bytes")
    return hashlib.sha256(raw).hexdigest()


def _reject_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P0PresentedNeutralReviewSignatureMathV1Error(
                f"duplicate JSON key is forbidden: {key}"
            )
        result[key] = value
    return result


def _reject_nonfinite(token: str) -> None:
    raise P0PresentedNeutralReviewSignatureMathV1Error(
        f"non-finite JSON constant is forbidden: {token}"
    )


def _parse_canonical_json(raw: bytes, label: str, *, max_bytes: int = _MAX_JSON_BYTES) -> dict[str, Any]:
    if (
        type(raw) is not bytes
        or not raw
        or len(raw) > max_bytes
        or raw.startswith(b"\xef\xbb\xbf")
        or b"\r" in raw
        or not raw.endswith(b"\n")
    ):
        raise P0PresentedNeutralReviewSignatureMathV1Error(f"{label} framing is invalid")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_object,
            parse_constant=_reject_nonfinite,
        )
    except P0PresentedNeutralReviewSignatureMathV1Error:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise P0PresentedNeutralReviewSignatureMathV1Error(
            f"{label} must be strict UTF-8 JSON"
        ) from exc
    if not isinstance(value, dict) or raw != canonical_file_bytes(value):
        raise P0PresentedNeutralReviewSignatureMathV1Error(
            f"{label} must be one canonical JSON object plus one final LF"
        )
    return value


def _strict(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise P0PresentedNeutralReviewSignatureMathV1Error(f"{label} must be an object")
    keys = frozenset(value)
    if keys != fields:
        raise P0PresentedNeutralReviewSignatureMathV1Error(
            f"{label} fields mismatch: missing={sorted(fields - keys)}, extra={sorted(keys - fields)}"
        )
    return dict(value)


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA_RE.fullmatch(value) is None:
        raise P0PresentedNeutralReviewSignatureMathV1Error(
            f"{label} must be lowercase SHA-256"
        )
    return value


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise P0PresentedNeutralReviewSignatureMathV1Error(f"{label} is invalid")
    return value


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise P0PresentedNeutralReviewSignatureMathV1Error(
            f"{label} must be a positive integer"
        )
    return value


def _presented_utc_time(value: Any, label: str) -> str:
    if not isinstance(value, str) or _TIME_RE.fullmatch(value) is None:
        raise P0PresentedNeutralReviewSignatureMathV1Error(f"{label} is invalid")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise P0PresentedNeutralReviewSignatureMathV1Error(
            f"{label} is not a real UTC timestamp"
        ) from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise P0PresentedNeutralReviewSignatureMathV1Error(f"{label} is invalid")
    return value


def _reject_payload_semantic_promotion(value: Any, *, depth: int = 0) -> None:
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
                    raise P0PresentedNeutralReviewSignatureMathV1Error(
                        f"subject payload semantic/operational field is forbidden: {key}"
                    )
            _reject_payload_semantic_promotion(item, depth=depth + 1)
    elif isinstance(value, list):
        for item in value:
            _reject_payload_semantic_promotion(item, depth=depth + 1)


def _decode_base64(value: Any, *, length: int, label: str) -> bytes:
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        raise P0PresentedNeutralReviewSignatureMathV1Error(
            f"{label} must be canonical base64"
        )
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise P0PresentedNeutralReviewSignatureMathV1Error(
            f"{label} must be canonical base64"
        ) from exc
    if len(decoded) != length or base64.b64encode(decoded).decode("ascii") != value:
        raise P0PresentedNeutralReviewSignatureMathV1Error(
            f"{label} must encode exactly {length} bytes"
        )
    return decoded


def _profile(kind: Any) -> tuple[str, str, str]:
    if not isinstance(kind, str) or kind not in SIGNATURE_PROFILE:
        raise P0PresentedNeutralReviewSignatureMathV1Error("signature_kind is invalid")
    return SIGNATURE_PROFILE[kind]


def _validate_self_hash(row: Mapping[str, Any], label: str) -> str:
    stored = _sha(row.get("artifact_sha256"), f"{label}.artifact_sha256")
    material = {key: value for key, value in row.items() if key != "artifact_sha256"}
    if not hmac.compare_digest(stored, canonical_sha256(material)):
        raise P0PresentedNeutralReviewSignatureMathV1Error(f"{label} self-hash mismatch")
    return stored


def _artifact_sha(value: Mapping[str, Any], label: str) -> str:
    artifact = _sha(value.get("artifact_sha256"), f"{label}.artifact_sha256")
    material = {key: item for key, item in value.items() if key != "artifact_sha256"}
    if not hmac.compare_digest(artifact, canonical_sha256(material)):
        raise P0PresentedNeutralReviewSignatureMathV1Error(f"{label} self-hash mismatch")
    return artifact


def public_key_fingerprint_sha256(*, public_key_x_base64: str, public_key_y_base64: str) -> str:
    x = _decode_base64(public_key_x_base64, length=32, label="public_key_x_base64")
    y = _decode_base64(public_key_y_base64, length=32, label="public_key_y_base64")
    return hashlib.sha256(_P256_SPKI_PREFIX + x + y).hexdigest()


def build_presented_review_key_pin_bytes(
    *,
    signature_kind: str,
    trust_domain: str,
    project_id: str,
    environment: str,
    key_id: str,
    key_epoch: int,
    public_key_x_base64: str,
    public_key_y_base64: str,
    signer_principal_commitment_sha256: str,
    authority_anchor_sha256: str,
    presented_revocation_snapshot_raw_sha256: str,
) -> bytes:
    """Build a strictly typed caller-presented pin; it is not provisioning."""

    key_role, purpose, domain = _profile(signature_kind)
    fingerprint = public_key_fingerprint_sha256(
        public_key_x_base64=public_key_x_base64,
        public_key_y_base64=public_key_y_base64,
    )
    material = {
        "schema_version": PUBLIC_KEY_PIN_SCHEMA,
        "record_origin": PRESENTED_PIN_ORIGIN,
        "component_version": COMPONENT_VERSION,
        "signature_kind": signature_kind,
        "trust_domain": trust_domain,
        "project_id": project_id,
        "environment": environment,
        "purpose": purpose,
        "key_role": key_role,
        "key_id": key_id,
        "key_epoch": key_epoch,
        "algorithm": ALGORITHM,
        "curve": CURVE,
        "cng_provider": CNG_PROVIDER,
        "coordinate_encoding": COORDINATE_ENCODING,
        "fingerprint_encoding": FINGERPRINT_ENCODING,
        "public_key_x_base64": public_key_x_base64,
        "public_key_y_base64": public_key_y_base64,
        "public_key_fingerprint_sha256": fingerprint,
        "signer_principal_commitment_sha256": signer_principal_commitment_sha256,
        "authority_anchor_sha256": authority_anchor_sha256,
        "allowed_signature_domains": [domain],
        "presented_revocation_snapshot_raw_sha256": presented_revocation_snapshot_raw_sha256,
    }
    raw = canonical_file_bytes({**material, "artifact_sha256": canonical_sha256(material)})
    _validate_pin(_parse_canonical_json(raw, "public-key pin"))
    return raw


def build_presented_review_subject_bytes(
    *,
    signature_kind: str,
    trust_domain: str,
    project_id: str,
    environment: str,
    campaign_id: str,
    run_id: str,
    subject_id: str,
    presented_issued_at: str,
    nonce_commitment_sha256: str,
    payload_raw: bytes,
    predecessor_subject_raw_sha256: str | None,
) -> bytes:
    """Bind one exact canonical payload into a non-authoritative subject."""

    key_role, purpose, domain = _profile(signature_kind)
    payload = _parse_canonical_json(payload_raw, "subject payload", max_bytes=_MAX_PAYLOAD_BYTES)
    payload_schema = _identifier(payload.get("schema_version"), "subject payload.schema_version")
    payload_artifact_sha = _artifact_sha(payload, "subject payload")
    _reject_payload_semantic_promotion(payload)
    if (
        payload.get("record_origin") != RECORD_ORIGIN
        or payload.get("action_applied") is not False
        or payload.get("operational_effect") != OPERATIONAL_EFFECT
    ):
        raise P0PresentedNeutralReviewSignatureMathV1Error(
            "subject payload must remain a no-effect presented contract artifact"
        )
    if predecessor_subject_raw_sha256 is not None:
        _sha(predecessor_subject_raw_sha256, "predecessor_subject_raw_sha256")
    material = {
        "schema_version": SUBJECT_SCHEMA,
        "record_origin": PRESENTED_SUBJECT_ORIGIN,
        "component_version": COMPONENT_VERSION,
        "signature_kind": signature_kind,
        "domain": domain,
        "trust_domain": trust_domain,
        "project_id": project_id,
        "environment": environment,
        "purpose": purpose,
        "key_role": key_role,
        "campaign_id": campaign_id,
        "run_id": run_id,
        "subject_id": subject_id,
        "presented_issued_at": presented_issued_at,
        "nonce_commitment_sha256": nonce_commitment_sha256,
        "payload_schema": payload_schema,
        "payload_bytes": len(payload_raw),
        "payload_raw_sha256": raw_sha256(payload_raw),
        "payload_artifact_sha256": payload_artifact_sha,
        "predecessor_subject_raw_sha256": predecessor_subject_raw_sha256,
        "caller_presented_subject_only": True,
        "external_authority_claimed": False,
        "actual_human_review_claimed": False,
        "semantic_promotion_claimed": False,
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    raw = canonical_file_bytes({**material, "artifact_sha256": canonical_sha256(material)})
    _validate_subject(_parse_canonical_json(raw, "signature subject"), payload_raw=payload_raw)
    return raw


def build_presented_review_signature_envelope_material(
    *, public_key_pin_raw: bytes, subject_raw: bytes, payload_raw: bytes
) -> dict[str, Any]:
    """Return exact domain-separated material for an external test/owner signer."""

    pin = _validate_pin(_parse_canonical_json(public_key_pin_raw, "public-key pin"))[0]
    subject = _validate_subject(
        _parse_canonical_json(subject_raw, "signature subject"), payload_raw=payload_raw
    )
    _require_projection(pin, subject, label="pin/subject")
    return {
        "schema_version": SIGNATURE_ENVELOPE_SCHEMA,
        "record_origin": PRESENTED_SIGNATURE_ORIGIN,
        "component_version": COMPONENT_VERSION,
        "signature_kind": subject["signature_kind"],
        "domain": subject["domain"],
        "trust_domain": subject["trust_domain"],
        "project_id": subject["project_id"],
        "environment": subject["environment"],
        "purpose": subject["purpose"],
        "key_role": subject["key_role"],
        "campaign_id": subject["campaign_id"],
        "run_id": subject["run_id"],
        "subject_id": subject["subject_id"],
        "key_id": pin["key_id"],
        "key_epoch": pin["key_epoch"],
        "algorithm": ALGORITHM,
        "public_key_fingerprint_sha256": pin["public_key_fingerprint_sha256"],
        "signer_principal_commitment_sha256": pin["signer_principal_commitment_sha256"],
        "public_key_pin_raw_sha256": raw_sha256(public_key_pin_raw),
        "public_key_pin_artifact_sha256": pin["artifact_sha256"],
        "subject_schema": SUBJECT_SCHEMA,
        "subject_bytes": len(subject_raw),
        "subject_raw_sha256": raw_sha256(subject_raw),
        "subject_artifact_sha256": subject["artifact_sha256"],
        "payload_raw_sha256": subject["payload_raw_sha256"],
    }


def seal_presented_review_signature_envelope_bytes(
    *, unsigned_material: Mapping[str, Any], signature_rs_base64: str
) -> bytes:
    """Attach an externally produced signature; no private-key API exists here."""

    material_fields = _ENVELOPE_FIELDS.difference({"signature_rs_base64", "artifact_sha256"})
    material = _strict(unsigned_material, material_fields, "unsigned signature envelope")
    row_without_hash = {**material, "signature_rs_base64": signature_rs_base64}
    raw = canonical_file_bytes(
        {**row_without_hash, "artifact_sha256": canonical_sha256(row_without_hash)}
    )
    _validate_envelope(_parse_canonical_json(raw, "signature envelope"))
    return raw


def presented_review_signature_material(envelope: Mapping[str, Any]) -> dict[str, Any]:
    row = _strict(envelope, _ENVELOPE_FIELDS, "signature envelope")
    return {
        key: value
        for key, value in row.items()
        if key not in {"signature_rs_base64", "artifact_sha256"}
    }


def _validate_pin(value: Any) -> tuple[dict[str, Any], bytes, bytes]:
    row = _strict(value, _PIN_FIELDS, "public-key pin")
    key_role, purpose, domain = _profile(row["signature_kind"])
    if (
        row["schema_version"] != PUBLIC_KEY_PIN_SCHEMA
        or row["record_origin"] != PRESENTED_PIN_ORIGIN
        or row["component_version"] != COMPONENT_VERSION
        or row["purpose"] != purpose
        or row["key_role"] != key_role
        or row["algorithm"] != ALGORITHM
        or row["curve"] != CURVE
        or row["cng_provider"] != CNG_PROVIDER
        or row["coordinate_encoding"] != COORDINATE_ENCODING
        or row["fingerprint_encoding"] != FINGERPRINT_ENCODING
        or row["allowed_signature_domains"] != [domain]
    ):
        raise P0PresentedNeutralReviewSignatureMathV1Error(
            "public-key pin schema/profile/provider mismatch"
        )
    for field in ("trust_domain", "project_id", "environment", "key_id"):
        _identifier(row[field], f"public-key pin.{field}")
    _positive_int(row["key_epoch"], "public-key pin.key_epoch")
    x = _decode_base64(row["public_key_x_base64"], length=32, label="public-key pin.public_key_x_base64")
    y = _decode_base64(row["public_key_y_base64"], length=32, label="public-key pin.public_key_y_base64")
    expected_fingerprint = hashlib.sha256(_P256_SPKI_PREFIX + x + y).hexdigest()
    if not hmac.compare_digest(
        _sha(row["public_key_fingerprint_sha256"], "public-key pin.public_key_fingerprint_sha256"),
        expected_fingerprint,
    ):
        raise P0PresentedNeutralReviewSignatureMathV1Error("public-key pin fingerprint mismatch")
    for field in (
        "signer_principal_commitment_sha256",
        "authority_anchor_sha256",
        "presented_revocation_snapshot_raw_sha256",
    ):
        _sha(row[field], f"public-key pin.{field}")
    _validate_self_hash(row, "public-key pin")
    return row, x, y


def _validate_subject(value: Any, *, payload_raw: bytes) -> dict[str, Any]:
    row = _strict(value, _SUBJECT_FIELDS, "signature subject")
    key_role, purpose, domain = _profile(row["signature_kind"])
    if (
        row["schema_version"] != SUBJECT_SCHEMA
        or row["record_origin"] != PRESENTED_SUBJECT_ORIGIN
        or row["component_version"] != COMPONENT_VERSION
        or row["domain"] != domain
        or row["purpose"] != purpose
        or row["key_role"] != key_role
        or row["caller_presented_subject_only"] is not True
        or row["external_authority_claimed"] is not False
        or row["actual_human_review_claimed"] is not False
        or row["semantic_promotion_claimed"] is not False
        or row["action_applied"] is not False
        or row["operational_effect"] != OPERATIONAL_EFFECT
    ):
        raise P0PresentedNeutralReviewSignatureMathV1Error("signature subject profile mismatch")
    for field in ("trust_domain", "project_id", "environment", "campaign_id", "run_id", "subject_id", "payload_schema"):
        _identifier(row[field], f"signature subject.{field}")
    _presented_utc_time(row["presented_issued_at"], "signature subject.presented_issued_at")
    _sha(row["nonce_commitment_sha256"], "signature subject.nonce_commitment_sha256")
    if row["predecessor_subject_raw_sha256"] is not None:
        _sha(row["predecessor_subject_raw_sha256"], "signature subject.predecessor_subject_raw_sha256")
    payload = _parse_canonical_json(payload_raw, "subject payload", max_bytes=_MAX_PAYLOAD_BYTES)
    _reject_payload_semantic_promotion(payload)
    if (
        payload.get("record_origin") != RECORD_ORIGIN
        or payload.get("action_applied") is not False
        or payload.get("operational_effect") != OPERATIONAL_EFFECT
    ):
        raise P0PresentedNeutralReviewSignatureMathV1Error(
            "subject payload must remain a no-effect presented contract artifact"
        )
    payload_raw_sha = _sha(row["payload_raw_sha256"], "signature subject.payload_raw_sha256")
    payload_artifact_sha = _sha(
        row["payload_artifact_sha256"], "signature subject.payload_artifact_sha256"
    )
    if (
        row["payload_bytes"] != len(payload_raw)
        or not hmac.compare_digest(payload_raw_sha, raw_sha256(payload_raw))
        or row["payload_schema"] != payload.get("schema_version")
        or not hmac.compare_digest(payload_artifact_sha, _artifact_sha(payload, "subject payload"))
    ):
        raise P0PresentedNeutralReviewSignatureMathV1Error("signature subject payload binding mismatch")
    _positive_int(row["payload_bytes"], "signature subject.payload_bytes")
    _validate_self_hash(row, "signature subject")
    return row


def _validate_envelope(value: Any) -> tuple[dict[str, Any], bytes, bytes]:
    row = _strict(value, _ENVELOPE_FIELDS, "signature envelope")
    key_role, purpose, domain = _profile(row["signature_kind"])
    if (
        row["schema_version"] != SIGNATURE_ENVELOPE_SCHEMA
        or row["record_origin"] != PRESENTED_SIGNATURE_ORIGIN
        or row["component_version"] != COMPONENT_VERSION
        or row["domain"] != domain
        or row["purpose"] != purpose
        or row["key_role"] != key_role
        or row["algorithm"] != ALGORITHM
        or row["subject_schema"] != SUBJECT_SCHEMA
    ):
        raise P0PresentedNeutralReviewSignatureMathV1Error("signature envelope profile mismatch")
    for field in ("trust_domain", "project_id", "environment", "campaign_id", "run_id", "subject_id", "key_id"):
        _identifier(row[field], f"signature envelope.{field}")
    _positive_int(row["key_epoch"], "signature envelope.key_epoch")
    _positive_int(row["subject_bytes"], "signature envelope.subject_bytes")
    for field in (
        "public_key_fingerprint_sha256",
        "signer_principal_commitment_sha256",
        "public_key_pin_raw_sha256",
        "public_key_pin_artifact_sha256",
        "subject_raw_sha256",
        "subject_artifact_sha256",
        "payload_raw_sha256",
    ):
        _sha(row[field], f"signature envelope.{field}")
    signature = _decode_base64(row["signature_rs_base64"], length=64, label="signature envelope.signature_rs_base64")
    r = int.from_bytes(signature[:32], "big")
    s = int.from_bytes(signature[32:], "big")
    if not 0 < r < _P256_ORDER or not 0 < s <= _P256_ORDER // 2:
        raise P0PresentedNeutralReviewSignatureMathV1Error(
            "signature must use canonical nonzero low-S P-256 r||s"
        )
    _validate_self_hash(row, "signature envelope")
    return row, signature, canonical_bytes(presented_review_signature_material(row))


def _require_projection(left: Mapping[str, Any], right: Mapping[str, Any], *, label: str) -> None:
    for field in (
        "signature_kind",
        "trust_domain",
        "project_id",
        "environment",
        "purpose",
        "key_role",
    ):
        if left[field] != right[field]:
            raise P0PresentedNeutralReviewSignatureMathV1Error(
                f"{label} projection mismatch: {field}"
            )


def validate_presented_neutral_review_signature_math(
    *,
    public_key_pin_raw: bytes,
    subject_raw: bytes,
    payload_raw: bytes,
    signature_envelope_raw: bytes,
    expected_signature_kind: str,
    expected_public_key_pin_raw_sha256: str,
    expected_subject_raw_sha256: str,
) -> dict[str, Any]:
    """Verify one presented signature and return a non-authoritative receipt."""

    _profile(expected_signature_kind)
    _sha(expected_public_key_pin_raw_sha256, "expected_public_key_pin_raw_sha256")
    _sha(expected_subject_raw_sha256, "expected_subject_raw_sha256")
    pin_raw_sha = raw_sha256(public_key_pin_raw)
    subject_raw_sha = raw_sha256(subject_raw)
    if not hmac.compare_digest(pin_raw_sha, expected_public_key_pin_raw_sha256):
        raise P0PresentedNeutralReviewSignatureMathV1Error("presented public-key pin expectation mismatch")
    if not hmac.compare_digest(subject_raw_sha, expected_subject_raw_sha256):
        raise P0PresentedNeutralReviewSignatureMathV1Error("presented subject expectation mismatch")
    pin, x, y = _validate_pin(_parse_canonical_json(public_key_pin_raw, "public-key pin"))
    subject = _validate_subject(
        _parse_canonical_json(subject_raw, "signature subject"), payload_raw=payload_raw
    )
    envelope, signature, signature_input = _validate_envelope(
        _parse_canonical_json(signature_envelope_raw, "signature envelope")
    )
    if pin["signature_kind"] != expected_signature_kind or subject["signature_kind"] != expected_signature_kind:
        raise P0PresentedNeutralReviewSignatureMathV1Error("expected signature kind mismatch")
    _require_projection(pin, subject, label="pin/subject")
    _require_projection(pin, envelope, label="pin/envelope")
    _require_projection(subject, envelope, label="subject/envelope")
    exact = {
        "campaign_id": subject["campaign_id"],
        "run_id": subject["run_id"],
        "subject_id": subject["subject_id"],
        "key_id": pin["key_id"],
        "key_epoch": pin["key_epoch"],
        "public_key_fingerprint_sha256": pin["public_key_fingerprint_sha256"],
        "signer_principal_commitment_sha256": pin["signer_principal_commitment_sha256"],
        "public_key_pin_raw_sha256": pin_raw_sha,
        "public_key_pin_artifact_sha256": pin["artifact_sha256"],
        "subject_bytes": len(subject_raw),
        "subject_raw_sha256": subject_raw_sha,
        "subject_artifact_sha256": subject["artifact_sha256"],
        "payload_raw_sha256": subject["payload_raw_sha256"],
    }
    for field, expected in exact.items():
        if envelope[field] != expected:
            raise P0PresentedNeutralReviewSignatureMathV1Error(
                f"signature envelope exact binding mismatch: {field}"
            )
    try:
        cng_p256.verify_p256_sha256(
            public_key_x=x,
            public_key_y=y,
            digest=hashlib.sha256(signature_input).digest(),
            signature=signature,
        )
    except cng_p256.P0WindowsCngEcdsaP256Error as exc:
        raise P0PresentedNeutralReviewSignatureMathV1Error(str(exc)) from exc
    material: dict[str, Any] = {
        "schema_version": VALIDATION_RECEIPT_SCHEMA,
        "record_origin": RECORD_ORIGIN,
        "component_version": COMPONENT_VERSION,
        "signature_kind": subject["signature_kind"],
        "domain": subject["domain"],
        "purpose": subject["purpose"],
        "key_role": subject["key_role"],
        "trust_domain": subject["trust_domain"],
        "project_id": subject["project_id"],
        "environment": subject["environment"],
        "campaign_id": subject["campaign_id"],
        "run_id": subject["run_id"],
        "subject_id": subject["subject_id"],
        "key_id": pin["key_id"],
        "key_epoch": pin["key_epoch"],
        "public_key_fingerprint_sha256": pin["public_key_fingerprint_sha256"],
        "signer_principal_commitment_sha256": pin["signer_principal_commitment_sha256"],
        "authority_anchor_sha256": pin["authority_anchor_sha256"],
        "presented_revocation_snapshot_raw_sha256": pin["presented_revocation_snapshot_raw_sha256"],
        "public_key_pin_bytes": len(public_key_pin_raw),
        "public_key_pin_raw_sha256": pin_raw_sha,
        "public_key_pin_artifact_sha256": pin["artifact_sha256"],
        "subject_bytes": len(subject_raw),
        "subject_raw_sha256": subject_raw_sha,
        "subject_artifact_sha256": subject["artifact_sha256"],
        "payload_bytes": len(payload_raw),
        "payload_raw_sha256": subject["payload_raw_sha256"],
        "payload_artifact_sha256": subject["payload_artifact_sha256"],
        "signature_envelope_bytes": len(signature_envelope_raw),
        "signature_envelope_raw_sha256": raw_sha256(signature_envelope_raw),
        "signature_envelope_artifact_sha256": envelope["artifact_sha256"],
        "signature_input_sha256": hashlib.sha256(signature_input).hexdigest(),
        "algorithm": ALGORITHM,
        "curve": CURVE,
        "cng_provider": CNG_PROVIDER,
        "caller_presented_pin_only": True,
        "caller_presented_revocation_only": True,
        "expected_pin_and_subject_are_caller_arguments": True,
        "signature_kind_role_domain_exactly_mapped": True,
        "payload_forbidden_semantic_promotion_fields_absent": True,
        "canonical_raw_binding_verified": True,
        "rfc5480_public_key_fingerprint_verified": True,
        "canonical_low_s_signature_verified": True,
        "asymmetric_signature_math_verified": True,
        **{field: False for field in _FALSE_TRUTH_FIELDS},
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
    return {**material, "receipt_sha256": canonical_sha256(material)}


__all__ = [
    "ALGORITHM",
    "CAMPAIGN_POLICY_PREAUTHORIZATION",
    "COMPONENT_VERSION",
    "FINAL_REVIEW_ATTESTATION",
    "GATE_STATUS",
    "HUMAN_REVIEW_RESULT",
    "P0PresentedNeutralReviewSignatureMathV1Error",
    "PUBLIC_KEY_PIN_SCHEMA",
    "REVIEW_LEASE",
    "SIGNATURE_ENVELOPE_SCHEMA",
    "SIGNATURE_PROFILE",
    "SUBJECT_SCHEMA",
    "VALIDATION_RECEIPT_SCHEMA",
    "build_presented_review_key_pin_bytes",
    "build_presented_review_signature_envelope_material",
    "build_presented_review_subject_bytes",
    "canonical_bytes",
    "canonical_file_bytes",
    "canonical_sha256",
    "presented_review_signature_material",
    "public_key_fingerprint_sha256",
    "raw_sha256",
    "seal_presented_review_signature_envelope_bytes",
    "validate_presented_neutral_review_signature_math",
]
