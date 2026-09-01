from __future__ import annotations

"""Immutable comparison receipts for no-public-write semantic observations.

The authoritative publication WAL remains the only public-decision owner.  A
fresh stochastic execution may legitimately differ from that reference; this
module records the difference without treating the observed decision as a
public commit or an activation authority.
"""

import hashlib
import json
import re
from typing import Any, Mapping


PUBLICATION_SHADOW_OBSERVATION_SCHEMA = "publication_shadow_observation_v1"

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_TOP_LEVEL_FIELDS = {
    "schema_version",
    "publication_scope_id",
    "input_index",
    "post_id",
    "authority",
    "public_apply",
    "authoritative_decision",
    "observed_decision",
    "comparison",
    "receipt_sha256",
}
_DECISION_FIELDS = {
    "decision_id",
    "outcome",
    "publish_allowed",
    "decision_sha256",
    "public_projection_sha256",
    "stable_result_sha256",
}
_COMPARISON_FIELDS = {
    "decision_equivalent",
    "outcome_equal",
    "publish_allowed_equal",
    "decision_payload_equal",
    "public_projection_equal",
    "stable_result_equal",
    "drift_dimensions",
}


class PublicationShadowObservationError(ValueError):
    pass


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            dict(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _receipt_value(receipt: Any, field: str) -> Any:
    if isinstance(receipt, Mapping):
        return receipt.get(field)
    return getattr(receipt, field, None)


def _hex64(value: Any, *, field: str) -> str:
    normalized = str(value or "").strip().lower()
    if _HEX64.fullmatch(normalized) is None:
        raise PublicationShadowObservationError(f"{field} must be lowercase sha256")
    return normalized


def _positive_index(value: Any) -> int:
    if isinstance(value, bool):
        raise PublicationShadowObservationError("input_index must be a positive integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise PublicationShadowObservationError(
            "input_index must be a positive integer"
        ) from exc
    if normalized <= 0:
        raise PublicationShadowObservationError("input_index must be a positive integer")
    return normalized


def _post_id(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        raise PublicationShadowObservationError("post_id is invalid")
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            raise PublicationShadowObservationError("post_id is invalid")
        return normalized
    if isinstance(value, int):
        return value
    normalized = str(value).strip()
    if not normalized:
        raise PublicationShadowObservationError("post_id is invalid")
    return normalized


def _decision_view(receipt: Any, *, label: str) -> dict[str, Any]:
    outcome = str(_receipt_value(receipt, "outcome") or "").strip().upper()
    if outcome not in {"PUBLISH", "HOLD", "ERROR_HOLD"}:
        raise PublicationShadowObservationError(f"{label}.outcome is invalid")
    publish_allowed = _receipt_value(receipt, "publish_allowed")
    if not isinstance(publish_allowed, bool):
        raise PublicationShadowObservationError(
            f"{label}.publish_allowed must be boolean"
        )
    if (outcome == "PUBLISH") != publish_allowed:
        raise PublicationShadowObservationError(
            f"{label}.outcome/publish_allowed mismatch"
        )
    return {
        "decision_id": _hex64(
            _receipt_value(receipt, "decision_id"), field=f"{label}.decision_id"
        ),
        "outcome": outcome,
        "publish_allowed": publish_allowed,
        "decision_sha256": _hex64(
            _receipt_value(receipt, "decision_sha256"),
            field=f"{label}.decision_sha256",
        ),
        "public_projection_sha256": _hex64(
            _receipt_value(receipt, "public_projection_sha256"),
            field=f"{label}.public_projection_sha256",
        ),
        "stable_result_sha256": _hex64(
            _receipt_value(receipt, "stable_result_sha256"),
            field=f"{label}.stable_result_sha256",
        ),
    }


def _comparison(
    authoritative: Mapping[str, Any], observed: Mapping[str, Any]
) -> dict[str, Any]:
    equalities = {
        "decision_equivalent": observed["decision_id"] == authoritative["decision_id"],
        "outcome_equal": observed["outcome"] == authoritative["outcome"],
        "publish_allowed_equal": (
            observed["publish_allowed"] == authoritative["publish_allowed"]
        ),
        "decision_payload_equal": (
            observed["decision_sha256"] == authoritative["decision_sha256"]
        ),
        "public_projection_equal": (
            observed["public_projection_sha256"]
            == authoritative["public_projection_sha256"]
        ),
        "stable_result_equal": (
            observed["stable_result_sha256"]
            == authoritative["stable_result_sha256"]
        ),
    }
    dimensions = {
        "decision_equivalent": "DECISION_ID",
        "outcome_equal": "OUTCOME",
        "publish_allowed_equal": "PUBLISH_ALLOWED",
        "decision_payload_equal": "DECISION_PAYLOAD",
        "public_projection_equal": "PUBLIC_PROJECTION",
        "stable_result_equal": "STABLE_RESULT",
    }
    return {
        **equalities,
        "drift_dimensions": [
            dimensions[key] for key, equal in equalities.items() if not equal
        ],
    }


def build_publication_shadow_observation(
    *,
    observed_receipt: Any,
    authoritative_receipt: Any,
) -> dict[str, Any]:
    """Build a deterministic no-public-write observation receipt."""

    observed_scope = _hex64(
        _receipt_value(observed_receipt, "publication_scope_id"),
        field="observed.publication_scope_id",
    )
    authoritative_scope = _hex64(
        _receipt_value(authoritative_receipt, "publication_scope_id"),
        field="authoritative.publication_scope_id",
    )
    observed_index = _positive_index(_receipt_value(observed_receipt, "input_index"))
    authoritative_index = _positive_index(
        _receipt_value(authoritative_receipt, "input_index")
    )
    observed_post_id = _post_id(_receipt_value(observed_receipt, "post_id"))
    authoritative_post_id = _post_id(
        _receipt_value(authoritative_receipt, "post_id")
    )
    if observed_scope != authoritative_scope:
        raise PublicationShadowObservationError("publication scope mismatch")
    if observed_index != authoritative_index:
        raise PublicationShadowObservationError("input_index mismatch")
    if str(observed_post_id) != str(authoritative_post_id):
        raise PublicationShadowObservationError("post_id mismatch")

    authoritative = _decision_view(authoritative_receipt, label="authoritative")
    observed = _decision_view(observed_receipt, label="observed")
    material = {
        "schema_version": PUBLICATION_SHADOW_OBSERVATION_SCHEMA,
        "publication_scope_id": authoritative_scope,
        "input_index": authoritative_index,
        "post_id": authoritative_post_id,
        "authority": "publication_commit_wal",
        "public_apply": False,
        "authoritative_decision": authoritative,
        "observed_decision": observed,
        "comparison": _comparison(authoritative, observed),
    }
    return {**material, "receipt_sha256": _canonical_sha256(material)}


def validate_publication_shadow_observation(value: Any) -> dict[str, Any]:
    """Strictly validate and normalize a serialized observation receipt."""

    if not isinstance(value, Mapping):
        raise PublicationShadowObservationError("observation receipt must be an object")
    if set(value) != _TOP_LEVEL_FIELDS:
        raise PublicationShadowObservationError("observation receipt fields mismatch")
    if value.get("schema_version") != PUBLICATION_SHADOW_OBSERVATION_SCHEMA:
        raise PublicationShadowObservationError("observation receipt schema mismatch")
    if value.get("authority") != "publication_commit_wal":
        raise PublicationShadowObservationError("observation authority mismatch")
    if value.get("public_apply") is not False:
        raise PublicationShadowObservationError("shadow observation cannot apply publicly")

    authoritative = value.get("authoritative_decision")
    observed = value.get("observed_decision")
    comparison = value.get("comparison")
    if not isinstance(authoritative, Mapping) or set(authoritative) != _DECISION_FIELDS:
        raise PublicationShadowObservationError("authoritative decision fields mismatch")
    if not isinstance(observed, Mapping) or set(observed) != _DECISION_FIELDS:
        raise PublicationShadowObservationError("observed decision fields mismatch")
    if not isinstance(comparison, Mapping) or set(comparison) != _COMPARISON_FIELDS:
        raise PublicationShadowObservationError("comparison fields mismatch")

    scope = _hex64(value.get("publication_scope_id"), field="publication_scope_id")
    index = _positive_index(value.get("input_index"))
    post_id = _post_id(value.get("post_id"))
    normalized_authoritative = _decision_view(
        authoritative, label="authoritative_decision"
    )
    normalized_observed = _decision_view(observed, label="observed_decision")
    expected_comparison = _comparison(normalized_authoritative, normalized_observed)
    if dict(comparison) != expected_comparison:
        raise PublicationShadowObservationError("observation comparison mismatch")
    material = {
        "schema_version": PUBLICATION_SHADOW_OBSERVATION_SCHEMA,
        "publication_scope_id": scope,
        "input_index": index,
        "post_id": post_id,
        "authority": "publication_commit_wal",
        "public_apply": False,
        "authoritative_decision": normalized_authoritative,
        "observed_decision": normalized_observed,
        "comparison": expected_comparison,
    }
    receipt_sha256 = _hex64(value.get("receipt_sha256"), field="receipt_sha256")
    if receipt_sha256 != _canonical_sha256(material):
        raise PublicationShadowObservationError("observation receipt hash mismatch")
    return {**material, "receipt_sha256": receipt_sha256}
