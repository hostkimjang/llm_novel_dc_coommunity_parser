"""Fail-closed readiness ledger for a future P3 actual calibration dataset.

This module never invents labels or split assignments.  It records which
pre-registered fields are still missing from the supplied saved evidence so a
Golden fixture cannot be silently promoted into DEV/CAL/FROZEN_ACTUAL data.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "candidate_set_calibration_dataset_readiness_v2"
GATE_NOT_READY = "NO_GO_ACTUAL_DATASET_NOT_READY"
GATE_READY = "GO_ACTUAL_DATASET_READY_FOR_SPLIT_FREEZE"
SHA_FIELDS = {
    "content_fingerprint",
    "source_group_fingerprint",
    "label_provenance_sha256",
    "candidate_set_fingerprint",
    "gold_work_fingerprint",
}
ROW_FIELDS = {
    "post_id",
    "truth_kind",
    "expected_title",
    "candidate_title_observed",
    "generation_status",
    "candidate_set_recall_status",
    "candidate_set_fingerprint",
    "split_group_id",
    "content_fingerprint",
    "source_group_fingerprint",
    "label_provenance_sha256",
    "truth_candidate_id",
    "gold_work_fingerprint",
    "binding_status",
    "blockers",
    "ready_for_split_assignment",
    "row_sha256",
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_payload(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _sha(value: Any, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name} must be lowercase sha256")
    return value


def _post_id(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        raise ValueError("invalid post_id")
    text = str(value).strip()
    if not text:
        raise ValueError("invalid post_id")
    return text


def _source_refs(sources: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    required = {"p1_run_spec", "p1_comparison", "label_ledger"}
    if set(sources) != required:
        raise ValueError("dataset readiness source refs mismatch")
    output: dict[str, dict[str, Any]] = {}
    paths: set[str] = set()
    for name in sorted(required):
        ref = sources[name]
        if not isinstance(ref, Mapping) or set(ref) != {"path", "sha256", "bytes"}:
            raise ValueError("invalid dataset readiness source ref")
        path = ref.get("path")
        size = ref.get("bytes")
        if (
            not isinstance(path, str)
            or not path
            or path in paths
            or isinstance(size, bool)
            or not isinstance(size, int)
            or size < 0
        ):
            raise ValueError("invalid dataset readiness source ref value")
        paths.add(path)
        output[name] = {
            "path": path,
            "sha256": _sha(ref.get("sha256"), f"{name} sha256"),
            "bytes": size,
        }
    return output


def _policy_ref(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != {"path", "sha256", "bytes"}:
        raise ValueError("invalid actual evaluation policy ref")
    path = value.get("path")
    size = value.get("bytes")
    if (
        not isinstance(path, str)
        or not path
        or isinstance(size, bool)
        or not isinstance(size, int)
        or size < 0
    ):
        raise ValueError("invalid actual evaluation policy ref value")
    return {
        "path": path,
        "sha256": _sha(value.get("sha256"), "actual evaluation policy file sha256"),
        "bytes": size,
    }


def _optional_sha(row: Mapping[str, Any], field: str) -> str | None:
    value = row.get(field)
    if value is None:
        return None
    return _sha(value, field)


def _expected_blockers(
    row: Mapping[str, Any],
    actual_evaluation_policy_sha256: str | None,
) -> list[str]:
    blockers: list[str] = []
    if row.get("generation_status") != "COMPLETE":
        blockers.append("PRODUCER_GENERATION_NOT_COMPLETE")
    for field, blocker in (
        ("split_group_id", "SPLIT_GROUP_PROVENANCE_MISSING"),
        ("content_fingerprint", "CONTENT_FINGERPRINT_MISSING"),
        ("source_group_fingerprint", "SOURCE_GROUP_FINGERPRINT_MISSING"),
        ("label_provenance_sha256", "PER_ROW_LABEL_PROVENANCE_MISSING"),
    ):
        if not row.get(field):
            blockers.append(blocker)
    if actual_evaluation_policy_sha256 is None:
        blockers.append("ACTUAL_EVALUATION_POLICY_NOT_PREREGISTERED")
    truth_kind = row.get("truth_kind")
    if truth_kind == "UNJUDGED":
        blockers.append("TRUTH_UNJUDGED")
    if truth_kind == "CANDIDATE" and (
        not row.get("truth_candidate_id")
        or row.get("binding_status") != "UNIQUE"
        or not row.get("gold_work_fingerprint")
    ):
        blockers.append("IMMUTABLE_CANDIDATE_ID_BINDING_MISSING")
    if truth_kind == "CANDIDATE" and row.get("candidate_title_observed") is not True:
        blockers.append("EXPECTED_TITLE_NOT_OBSERVED")
    return sorted(set(blockers))


def build_dataset_readiness(
    *,
    p1_comparison: Mapping[str, Any],
    label_ledger: Mapping[str, Any],
    sources: Mapping[str, Mapping[str, Any]],
    actual_evaluation_policy_sha256: str | None = None,
    actual_evaluation_policy_ref: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if p1_comparison.get("schema_version") != "candidate-set-nil-shadow-saved-artifact-v1":
        raise ValueError("unsupported P1 comparison schema")
    if label_ledger.get("schema_version") != "candidate-set-nil-label-ledger-v1":
        raise ValueError("unsupported label ledger schema")
    p1_rows = p1_comparison.get("rows")
    labels = label_ledger.get("rows")
    if not isinstance(p1_rows, list) or not isinstance(labels, list) or not p1_rows:
        raise ValueError("readiness inputs contain no rows")
    label_by_post = {_post_id(row.get("post_id")): row for row in labels if isinstance(row, Mapping)}
    if len(label_by_post) != len(labels):
        raise ValueError("duplicate or malformed label rows")
    p1_by_post = {_post_id(row.get("post_id")): row for row in p1_rows if isinstance(row, Mapping)}
    if len(p1_by_post) != len(p1_rows) or list(p1_by_post) != list(label_by_post):
        raise ValueError("P1/label post order or set mismatch")
    gates = p1_comparison.get("gates")
    if (
        not isinstance(gates, Mapping)
        or gates.get("artifact_integrity") != "GO"
        or gates.get("candidate_set_recall") != "NOT_EVALUABLE"
        or gates.get("semantic_quality") != "REVIEW-LOCKED"
        or gates.get("full_scan_approval") is not False
    ):
        raise ValueError("P1 comparison approval boundary mismatch")
    if actual_evaluation_policy_sha256 is not None:
        _sha(actual_evaluation_policy_sha256, "actual_evaluation_policy_sha256")
    stored_policy_ref = _policy_ref(actual_evaluation_policy_ref)
    if (actual_evaluation_policy_sha256 is None) is not (stored_policy_ref is None):
        raise ValueError("actual evaluation policy hash/ref must be present together")

    readiness_rows: list[dict[str, Any]] = []
    for post_id, p1_row in p1_by_post.items():
        label = label_by_post[post_id]
        if p1_row.get("truth_kind") != label.get("truth_kind"):
            raise ValueError("P1/label truth mismatch")
        candidate_set = p1_row.get("candidate_set")
        label_comparison = p1_row.get("label_comparison")
        if not isinstance(candidate_set, Mapping) or not isinstance(label_comparison, Mapping):
            raise ValueError("P1 readiness row shape mismatch")
        truth_kind = str(label.get("truth_kind") or "")
        if truth_kind not in {"CANDIDATE", "NIL", "UNJUDGED"}:
            raise ValueError("unsupported readiness truth kind")
        generation_status = str(candidate_set.get("generation_status") or "UNKNOWN")
        observed_title = label_comparison.get("candidate_title_observed")
        row_payload = {
            "post_id": post_id,
            "truth_kind": truth_kind,
            "expected_title": label.get("expected_title"),
            "candidate_title_observed": observed_title,
            "generation_status": generation_status,
            "candidate_set_recall_status": candidate_set.get("candidate_set_recall_status"),
            "candidate_set_fingerprint": _sha(
                candidate_set.get("candidate_set_fingerprint"),
                "candidate_set_fingerprint",
            ),
            "split_group_id": label.get("split_group_id"),
            "content_fingerprint": _optional_sha(label, "content_fingerprint"),
            "source_group_fingerprint": _optional_sha(label, "source_group_fingerprint"),
            "label_provenance_sha256": _optional_sha(label, "label_provenance_sha256"),
            "truth_candidate_id": label.get("truth_candidate_id"),
            "gold_work_fingerprint": _optional_sha(label, "gold_work_fingerprint"),
            "binding_status": label.get("binding_status"),
        }
        row_payload["blockers"] = _expected_blockers(
            row_payload,
            actual_evaluation_policy_sha256,
        )
        row_payload["ready_for_split_assignment"] = not row_payload["blockers"]
        row_payload["row_sha256"] = sha256_payload(row_payload)
        readiness_rows.append(row_payload)

    counts = {
        "source_rows": len(readiness_rows),
        "candidate_truth": sum(row["truth_kind"] == "CANDIDATE" for row in readiness_rows),
        "nil_truth": sum(row["truth_kind"] == "NIL" for row in readiness_rows),
        "unjudged": sum(row["truth_kind"] == "UNJUDGED" for row in readiness_rows),
        "generation_complete": sum(row["generation_status"] == "COMPLETE" for row in readiness_rows),
        "ready_rows": sum(row["ready_for_split_assignment"] for row in readiness_rows),
    }
    ready = counts["ready_rows"] == counts["source_rows"] and counts["unjudged"] == 0
    payload = {
        "schema_version": SCHEMA_VERSION,
        "sources": _source_refs(sources),
        "actual_evaluation_policy_sha256": actual_evaluation_policy_sha256,
        "actual_evaluation_policy": stored_policy_ref,
        "counts": counts,
        "rows": readiness_rows,
        "ready_for_split_manifest": ready,
        "split_manifest": None,
        "actual_metrics": None,
        "gate": GATE_READY if ready else GATE_NOT_READY,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
    }
    payload["manifest_sha256"] = sha256_payload(payload)
    validate_dataset_readiness_manifest(payload)
    return payload


def validate_dataset_readiness_manifest(manifest: Mapping[str, Any]) -> None:
    required = {
        "schema_version",
        "sources",
        "actual_evaluation_policy_sha256",
        "actual_evaluation_policy",
        "counts",
        "rows",
        "ready_for_split_manifest",
        "split_manifest",
        "actual_metrics",
        "gate",
        "semantic_quality",
        "full_scan_approval",
        "manifest_sha256",
    }
    if not isinstance(manifest, Mapping) or set(manifest) != required:
        raise ValueError("invalid dataset readiness manifest shape")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported dataset readiness schema")
    _source_refs(manifest["sources"])
    policy_sha = manifest.get("actual_evaluation_policy_sha256")
    if policy_sha is not None:
        _sha(policy_sha, "actual_evaluation_policy_sha256")
    policy_ref = _policy_ref(manifest.get("actual_evaluation_policy"))
    if (policy_sha is None) is not (policy_ref is None):
        raise ValueError("actual evaluation policy hash/ref mismatch")
    rows = manifest.get("rows")
    counts = manifest.get("counts")
    if not isinstance(rows, list) or not rows or not isinstance(counts, Mapping):
        raise ValueError("dataset readiness rows/counts missing")
    expected_count_keys = {
        "source_rows",
        "candidate_truth",
        "nil_truth",
        "unjudged",
        "generation_complete",
        "ready_rows",
    }
    if set(counts) != expected_count_keys:
        raise ValueError("dataset readiness count keys mismatch")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts.values()):
        raise ValueError("invalid dataset readiness count")
    post_ids: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != ROW_FIELDS:
            raise ValueError("invalid dataset readiness row")
        post_ids.append(_post_id(row.get("post_id")))
        truth_kind = row.get("truth_kind")
        if truth_kind not in {"CANDIDATE", "NIL", "UNJUDGED"}:
            raise ValueError("invalid dataset readiness truth kind")
        if row.get("expected_title") is not None and (
            not isinstance(row.get("expected_title"), str)
            or not str(row.get("expected_title")).strip()
        ):
            raise ValueError("invalid dataset readiness expected title")
        if row.get("candidate_title_observed") not in {True, False, None}:
            raise ValueError("invalid candidate title observation")
        if not isinstance(row.get("generation_status"), str) or not row.get("generation_status"):
            raise ValueError("invalid readiness generation status")
        recall_status = row.get("candidate_set_recall_status")
        if recall_status is not None and (
            not isinstance(recall_status, str) or not recall_status
        ):
            raise ValueError("invalid readiness recall status")
        _sha(row.get("candidate_set_fingerprint"), "candidate_set_fingerprint")
        split_group_id = row.get("split_group_id")
        if split_group_id is not None and (
            not isinstance(split_group_id, str) or not split_group_id.strip()
        ):
            raise ValueError("invalid split_group_id")
        for field in SHA_FIELDS - {"candidate_set_fingerprint"}:
            _optional_sha(row, field)
        truth_candidate_id = row.get("truth_candidate_id")
        if truth_candidate_id is not None and (
            not isinstance(truth_candidate_id, str) or not truth_candidate_id.strip()
        ):
            raise ValueError("invalid truth_candidate_id")
        binding_status = row.get("binding_status")
        if binding_status not in {None, "UNIQUE", "MISSING", "AMBIGUOUS", "NOT_APPLICABLE"}:
            raise ValueError("invalid readiness binding_status")
        stored_hash = row.get("row_sha256")
        if _sha(stored_hash, "row_sha256") != sha256_payload(
            {key: value for key, value in row.items() if key != "row_sha256"}
        ):
            raise ValueError("dataset readiness row hash mismatch")
        blockers = row.get("blockers")
        if not isinstance(blockers, list) or blockers != sorted(set(blockers)):
            raise ValueError("dataset readiness blockers must be sorted and unique")
        if blockers != _expected_blockers(row, policy_sha):
            raise ValueError("dataset readiness blockers do not match row evidence")
        if row.get("ready_for_split_assignment") is not (not blockers):
            raise ValueError("dataset readiness row gate mismatch")
    if len(post_ids) != len(set(post_ids)):
        raise ValueError("duplicate dataset readiness post_id")
    recomputed = {
        "source_rows": len(rows),
        "candidate_truth": sum(row.get("truth_kind") == "CANDIDATE" for row in rows),
        "nil_truth": sum(row.get("truth_kind") == "NIL" for row in rows),
        "unjudged": sum(row.get("truth_kind") == "UNJUDGED" for row in rows),
        "generation_complete": sum(row.get("generation_status") == "COMPLETE" for row in rows),
        "ready_rows": sum(row.get("ready_for_split_assignment") is True for row in rows),
    }
    if dict(counts) != recomputed:
        raise ValueError("dataset readiness counts mismatch")
    ready = recomputed["ready_rows"] == recomputed["source_rows"] and recomputed["unjudged"] == 0
    if manifest.get("ready_for_split_manifest") is not ready:
        raise ValueError("dataset readiness overall gate mismatch")
    expected_gate = GATE_READY if ready else GATE_NOT_READY
    if manifest.get("gate") != expected_gate:
        raise ValueError("dataset readiness gate value mismatch")
    if manifest.get("split_manifest") is not None or manifest.get("actual_metrics") is not None:
        raise ValueError("readiness preflight must not synthesize split or metrics")
    if manifest.get("semantic_quality") != "REVIEW-LOCKED" or manifest.get("full_scan_approval") is not False:
        raise ValueError("dataset readiness approval boundary mismatch")
    stored_manifest_hash = manifest.get("manifest_sha256")
    if _sha(stored_manifest_hash, "manifest_sha256") != sha256_payload(
        {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    ):
        raise ValueError("dataset readiness manifest hash mismatch")


def validate_dataset_readiness_against_sources(
    manifest: Mapping[str, Any],
    *,
    p1_comparison: Mapping[str, Any],
    label_ledger: Mapping[str, Any],
    actual_evaluation_policy: Mapping[str, Any] | None = None,
    actual_evaluation_policy_ref: Mapping[str, Any] | None = None,
) -> None:
    """Replay every row from the source artifacts bound by the manifest."""

    validate_dataset_readiness_manifest(manifest)
    policy_sha = manifest["actual_evaluation_policy_sha256"]
    if policy_sha is None:
        if actual_evaluation_policy is not None or actual_evaluation_policy_ref is not None:
            raise ValueError("unexpected actual evaluation policy source")
    else:
        if not isinstance(actual_evaluation_policy, Mapping):
            raise ValueError("actual evaluation policy source is required")
        from src.llm_batch.candidate_set_calibration_shadow import (
            CalibrationEvaluationPolicy,
        )

        try:
            policy = CalibrationEvaluationPolicy(**dict(actual_evaluation_policy))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid actual evaluation policy source: {exc}") from exc
        if (
            policy.policy_scope != "FROZEN_ACTUAL_PRE_REGISTERED"
            or policy.policy_sha256 != policy_sha
        ):
            raise ValueError("actual evaluation policy semantic binding mismatch")
        if _policy_ref(actual_evaluation_policy_ref) != manifest["actual_evaluation_policy"]:
            raise ValueError("actual evaluation policy artifact binding mismatch")
    rebuilt = build_dataset_readiness(
        p1_comparison=p1_comparison,
        label_ledger=label_ledger,
        sources=manifest["sources"],
        actual_evaluation_policy_sha256=policy_sha,
        actual_evaluation_policy_ref=manifest["actual_evaluation_policy"],
    )
    if dict(manifest) != rebuilt:
        raise ValueError("dataset readiness source replay mismatch")
