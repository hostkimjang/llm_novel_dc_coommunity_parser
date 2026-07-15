from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_adjusted_collateral_adjudication import DERIVATION_VERSION
from tools.build_adjusted_collateral_blind_packet import (
    PRODUCTION_GOLDEN_ROWS,
    PRODUCTION_PANEL_ROWS,
)
from tools.validate_adjusted_collateral_adjudication import (
    VALIDATION_REPORT_TYPE,
    VALIDATOR_VERSION,
    current_validator_code_sha256,
    validate_adjudication,
    validation_receipt_payload,
    validation_receipt_digest,
)
from tools.compare_completed779_improvement import load_json_or_jsonl


PRODUCTION_GATE_CODE_PINS = {
    "tools/build_adjusted_collateral_adjudication.py": (
        "18aa9fa79243e0d73ff4348e15f5be5c8023ecfebef02fac1d1c3d0bb52afff2"
    ),
    "tools/build_adjusted_collateral_blind_packet.py": (
        "22ffb968a56c2dc442e299562f01e579b74d48f6b670901ce8c2c8ea80a3d199"
    ),
    "tools/validate_adjusted_collateral_adjudication.py": (
        "905c23802c3c2089c4cce0f1c4079cacc84fe7b5419a2d5c47c076548ca3d48c"
    ),
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _is_sha256(value: Any) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(value or "")))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _adjudication_binding_issues(
    *,
    adjudication: dict[str, Any],
    collateral: dict[str, Any],
    golden_audit: dict[str, Any],
    expected_scope_rows: int,
    expected_golden_rows: int,
) -> list[str]:
    issues: list[str] = []
    for relative_path, expected_sha256 in PRODUCTION_GATE_CODE_PINS.items():
        source_path = (ROOT / relative_path).resolve()
        if not source_path.is_file() or _file_sha256(source_path) != expected_sha256:
            issues.append(f"production_gate_code_pin_mismatch:{relative_path}")
    collateral_digest = _canonical_digest(collateral)
    changed_count = _safe_int(collateral.get("changed_post_count"))
    if adjudication.get("report_type") != VALIDATION_REPORT_TYPE:
        issues.append("validation_report_type_mismatch")
    if adjudication.get("validator_version") != VALIDATOR_VERSION:
        issues.append("validator_version_mismatch")
    if adjudication.get("derivation_version") != DERIVATION_VERSION:
        issues.append("derivation_version_mismatch")
    if adjudication.get("validator_code_sha256") != current_validator_code_sha256():
        issues.append("validator_code_sha256_mismatch")
    if adjudication.get("source_compare_digest") != collateral_digest:
        issues.append("source_compare_digest_mismatch")
    if adjudication.get("authoritative_trust_gate") != "GO":
        issues.append("authoritative_trust_gate_not_go")
    for field in (
        "trust_root_digest",
        "bound_after_payload_sha256",
        "raw_judge_receipt_sha256",
    ):
        if not _is_sha256(adjudication.get(field)):
            issues.append(f"{field}_missing")
    if _safe_int(adjudication.get("source_changed_count")) != changed_count:
        issues.append("source_changed_count_mismatch")
    if _safe_int(adjudication.get("drift_union_count")) != changed_count:
        issues.append("drift_union_count_mismatch")
    if _safe_int(adjudication.get("expected_scope_rows")) != expected_scope_rows:
        issues.append("expected_scope_rows_mismatch")
    if _safe_int(adjudication.get("expected_golden_rows")) != expected_golden_rows:
        issues.append("expected_golden_rows_mismatch")
    if not _is_sha256(adjudication.get("validated_payload_digest")):
        issues.append("validated_payload_digest_missing")
    if not _is_sha256(adjudication.get("collateral_binding_digest")):
        issues.append("collateral_binding_digest_missing")
    source_digests = adjudication.get("source_value_digests")
    if not isinstance(source_digests, dict):
        issues.append("source_value_digests_missing")
    elif source_digests.get("collateral_compare") != collateral_digest:
        issues.append("source_value_compare_digest_mismatch")
    if isinstance(source_digests, dict) and source_digests.get("golden_audit") != _canonical_digest(
        golden_audit
    ):
        issues.append("source_value_golden_audit_digest_mismatch")
    if isinstance(source_digests, dict) and adjudication.get(
        "bound_after_payload_sha256"
    ) != source_digests.get("after_result"):
        issues.append("bound_after_payload_digest_mismatch")
    artifact_hashes = adjudication.get("source_artifact_hashes")
    artifact_paths = adjudication.get("source_artifact_paths")
    path_to_hash_field = {
        "collateral_compare": "collateral_compare_sha256",
        "baseline_result": "baseline_result_sha256",
        "source_input": "source_input_sha256",
        "after_result": "after_result_sha256",
        "golden_manifest": "golden_manifest_sha256",
        "blind_packet_jsonl": "blind_packet_jsonl_sha256",
        "blind_map_json": "blind_map_json_sha256",
        "verdicts_jsonl": "verdicts_jsonl_sha256",
        "baseline_manifest": "baseline_manifest_sha256",
        "merged_manifest": "merged_manifest_sha256",
        "merged_checkpoint": "merged_checkpoint_sha256",
        "merged_pending": "merged_pending_sha256",
        "merge_binding_receipt": "merge_binding_receipt_sha256",
        "runtime_trust_anchor": "runtime_trust_anchor_sha256",
        "golden_audit": "golden_audit_sha256",
        "raw_judge_receipt": "raw_judge_receipt_sha256",
        "adjudication_report": "adjudication_report_sha256",
    }
    if isinstance(artifact_paths, dict) and artifact_paths.get("merge_integrity"):
        path_to_hash_field["merge_integrity"] = "merge_integrity_sha256"
    if isinstance(artifact_paths, dict) and artifact_paths.get("thread_readback_receipt"):
        path_to_hash_field["thread_readback_receipt"] = (
            "thread_readback_receipt_sha256"
        )
    elif changed_count:
        issues.append("thread_readback_receipt_missing_for_nonzero_drift")
    if not isinstance(artifact_hashes, dict) or not artifact_hashes:
        issues.append("source_artifact_hashes_missing")
    elif any(not _is_sha256(value) for value in artifact_hashes.values()):
        issues.append("source_artifact_hash_invalid")
    if not isinstance(artifact_paths, dict) or set(artifact_paths) != set(path_to_hash_field):
        issues.append("source_artifact_paths_incomplete")
    elif isinstance(artifact_hashes, dict):
        trust_anchors = adjudication.get("trust_anchors")
        if not isinstance(trust_anchors, dict):
            issues.append("trust_anchors_missing")
        else:
            if trust_anchors.get("runtime_trust_anchor_sha256") != artifact_hashes.get(
                "runtime_trust_anchor_sha256"
            ):
                issues.append("runtime_trust_anchor_receipt_hash_mismatch")
            if adjudication.get("raw_judge_receipt_sha256") != artifact_hashes.get(
                "raw_judge_receipt_sha256"
            ):
                issues.append("raw_judge_receipt_receipt_hash_mismatch")
        for path_field, hash_field in path_to_hash_field.items():
            path = Path(str(artifact_paths[path_field]))
            if not path.is_file():
                issues.append(f"source_artifact_missing:{path_field}")
                continue
            try:
                actual_hash = _file_sha256(path)
            except OSError:
                issues.append(f"source_artifact_unreadable:{path_field}")
                continue
            if actual_hash != artifact_hashes.get(hash_field):
                issues.append(f"source_artifact_hash_mismatch:{path_field}")
        compare_path = Path(str(artifact_paths["collateral_compare"]))
        if compare_path.is_file():
            try:
                compare_payload = json.loads(compare_path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                issues.append("source_compare_artifact_unreadable")
            else:
                if _canonical_digest(compare_payload) != collateral_digest:
                    issues.append("source_compare_artifact_payload_mismatch")
        value_digest_fields = {
            "baseline_result": "baseline_result",
            "source_input": "source_input",
            "after_result": "after_result",
            "golden_manifest": "golden_manifest",
            "blind_packet_jsonl": "blind_packet",
            "blind_map_json": "blind_private_map",
            "verdicts_jsonl": "verdict_rows",
            "baseline_manifest": "baseline_manifest",
            "merged_manifest": "merged_manifest",
            "merged_checkpoint": "merged_checkpoint",
            "merged_pending": "merged_pending",
            "merge_binding_receipt": "merge_binding_receipt",
            "runtime_trust_anchor": "runtime_trust_anchor",
            "golden_audit": "golden_audit",
            "raw_judge_receipt": "raw_judge_receipt",
        }
        if "merge_integrity" in path_to_hash_field:
            value_digest_fields["merge_integrity"] = "merge_integrity"
        if "thread_readback_receipt" in path_to_hash_field:
            value_digest_fields["thread_readback_receipt"] = (
                "thread_readback_receipt"
            )
        row_artifacts = {
            "baseline_result",
            "source_input",
            "after_result",
            "blind_packet_jsonl",
            "verdicts_jsonl",
            "merged_checkpoint",
        }
        if isinstance(source_digests, dict):
            for path_field, digest_field in value_digest_fields.items():
                path = Path(str(artifact_paths[path_field]))
                if not path.is_file():
                    continue
                try:
                    value = (
                        load_json_or_jsonl(path)
                        if path_field in row_artifacts
                        else json.loads(path.read_text(encoding="utf-8-sig"))
                    )
                except (OSError, ValueError, json.JSONDecodeError):
                    issues.append(f"source_artifact_payload_unreadable:{path_field}")
                    continue
                if _canonical_digest(value) != source_digests.get(digest_field):
                    issues.append(f"source_artifact_value_digest_mismatch:{path_field}")
        if all(Path(str(artifact_paths[key])).is_file() for key in path_to_hash_field):
            try:
                source_hashes = {
                    hash_field: _file_sha256(Path(str(artifact_paths[path_field])))
                    for path_field, hash_field in path_to_hash_field.items()
                    if path_field != "adjudication_report"
                }
                recomputed_validation = validate_adjudication(
                    report=json.loads(
                        Path(str(artifact_paths["adjudication_report"])).read_text(
                            encoding="utf-8-sig"
                        )
                    ),
                    compare=json.loads(
                        Path(str(artifact_paths["collateral_compare"])).read_text(
                            encoding="utf-8-sig"
                        )
                    ),
                    verdict_rows=load_json_or_jsonl(Path(str(artifact_paths["verdicts_jsonl"]))),
                    baseline_rows=load_json_or_jsonl(Path(str(artifact_paths["baseline_result"]))),
                    source_rows=load_json_or_jsonl(Path(str(artifact_paths["source_input"]))),
                    after_rows=load_json_or_jsonl(Path(str(artifact_paths["after_result"]))),
                    golden_manifest=json.loads(
                        Path(str(artifact_paths["golden_manifest"])).read_text(
                            encoding="utf-8-sig"
                        )
                    ),
                    blind_packet_rows=load_json_or_jsonl(
                        Path(str(artifact_paths["blind_packet_jsonl"]))
                    ),
                    blind_map=json.loads(
                        Path(str(artifact_paths["blind_map_json"])).read_text(
                            encoding="utf-8-sig"
                        )
                    ),
                    expected_scope_rows=expected_scope_rows,
                    expected_golden_rows=expected_golden_rows,
                    trust_bundle={
                        "artifact_paths": {
                            key: Path(str(artifact_paths[key]))
                            for key in (
                                "baseline_result",
                                "baseline_manifest",
                                "source_input",
                                "after_result",
                                "merged_manifest",
                                "merged_checkpoint",
                                "merged_pending",
                                "merge_binding_receipt",
                                "merge_integrity",
                                "runtime_trust_anchor",
                                "golden_manifest",
                                "golden_audit",
                                "raw_judge_receipt",
                                "thread_readback_receipt",
                                "blind_packet_jsonl",
                                "verdicts_jsonl",
                            )
                            if key in artifact_paths
                        },
                        "anchors": adjudication.get("trust_anchors") or {},
                    },
                    artifact_hashes=source_hashes,
                    adjudication_report_path=Path(str(artifact_paths["adjudication_report"])),
                )
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                issues.append("validator_source_recompute_failed")
            else:
                if validation_receipt_payload(recomputed_validation) != validation_receipt_payload(
                    adjudication
                ):
                    issues.append("validator_source_recompute_mismatch")
    if adjudication.get("mismatched_fields") not in ([], None):
        issues.append("validator_mismatched_fields_nonempty")
    if adjudication.get("artifact_hash_mismatches") not in ([], None):
        issues.append("validator_artifact_hash_mismatches_nonempty")
    if adjudication.get("independent_source_validation_issues") not in ([], None):
        issues.append("independent_source_validation_issues_nonempty")
    if adjudication.get("validation_issues") not in ([], None):
        issues.append("validator_validation_issues_nonempty")
    boundary = adjudication.get("approval_boundary")
    if not isinstance(boundary, dict) or boundary.get("validator_recomputed_from_source_artifacts") is not True:
        issues.append("validator_source_recompute_boundary_missing")
    if not isinstance(boundary, dict) or boundary.get("validator_rebuilt_blind_packet_and_private_map") is not True:
        issues.append("validator_blind_material_boundary_missing")
    supplied_receipt = adjudication.get("validation_receipt_digest")
    if not _is_sha256(supplied_receipt) or supplied_receipt != validation_receipt_digest(adjudication):
        issues.append("validation_receipt_digest_mismatch")
    return issues


def _raw_regression_post_ids(collateral: dict[str, Any]) -> set[int] | None:
    rows = collateral.get("rows")
    if not isinstance(rows, list):
        return None
    post_ids: set[int] = set()
    saw_regression_row = False
    for row in rows:
        if not isinstance(row, dict) or not row.get("is_regression"):
            continue
        saw_regression_row = True
        post_id = row.get("post_id")
        if isinstance(post_id, int):
            post_ids.add(post_id)
    return post_ids if saw_regression_row else None


def _review_post_ids(collateral_review: dict[str, Any]) -> set[int] | None:
    rows = collateral_review.get("rows")
    if not isinstance(rows, list):
        return None
    post_ids = {row.get("post_id") for row in rows if isinstance(row, dict)}
    return {post_id for post_id in post_ids if isinstance(post_id, int)}


def _exclusion_post_ids(collateral_review: dict[str, Any]) -> set[int] | None:
    rows = collateral_review.get("rows")
    if not isinstance(rows, list):
        return None
    post_ids: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if "exclude_from_regression_count_after_gate_wiring" not in (row.get("action") or []):
            continue
        post_id = row.get("post_id")
        if isinstance(post_id, int):
            post_ids.add(post_id)
    return post_ids


def _contract_accounted_post_ids(contract_accounting: dict[str, Any]) -> set[int] | None:
    rows = contract_accounting.get("rows")
    if not isinstance(rows, list):
        return None
    post_ids: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("ordinary_residual_unprocessed"):
            continue
        if not (row.get("contract_processed") or row.get("source_native_processed")):
            continue
        post_id = row.get("post_id")
        if isinstance(post_id, int):
            post_ids.add(post_id)
    return post_ids


def golden_gate(golden: dict[str, Any], expected_rows: int) -> dict[str, Any]:
    row_count = _safe_int(golden.get("row_count"))
    passed_count = _safe_int(golden.get("passed_count"))
    failed_count = _safe_int(golden.get("failed_count"))
    semantic_gate = str(golden.get("canary_semantic_gate") or "").strip()
    runtime = golden.get("runtime") if isinstance(golden.get("runtime"), dict) else {}
    runtime_completed = _safe_int(runtime.get("completed_count"))
    runtime_pending = _safe_int(runtime.get("pending_count"))
    runtime_failed = _safe_int(runtime.get("failed_count"))
    runtime_complete = (
        runtime_completed is not None
        and runtime_completed >= expected_rows
        and runtime_pending == 0
        and runtime_failed == 0
    )
    passed = (
        row_count == expected_rows
        and passed_count == expected_rows
        and failed_count == 0
        and semantic_gate in {"PASS", "GO"}
        and runtime_complete
    )
    blockers: list[str] = []
    if row_count != expected_rows:
        blockers.append("golden_row_count_mismatch")
    if passed_count != expected_rows or failed_count != 0:
        blockers.append("golden_expected_answer_failures")
    if semantic_gate not in {"PASS", "GO"}:
        blockers.append("golden_semantic_gate_not_pass")
    if not runtime_complete:
        blockers.append("golden_runtime_not_complete")
    return {
        "gate": "GO" if passed else "NO-GO",
        "expected_rows": expected_rows,
        "row_count": row_count,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "canary_semantic_gate": semantic_gate,
        "runtime_complete": runtime_complete,
        "blockers": blockers,
    }


def _collateral_review_adjustment(
    *,
    collateral_review: dict[str, Any] | None,
    contract_accounting: dict[str, Any] | None = None,
    raw_regression_count: int | None,
    raw_regression_post_ids: set[int] | None = None,
) -> dict[str, Any]:
    if not collateral_review:
        return {
            "provided": False,
            "applied": False,
            "exclusion_candidate_rows": 0,
            "review_adjusted_regression_count": raw_regression_count,
            "blockers": [],
        }

    summary = collateral_review.get("summary") if isinstance(collateral_review.get("summary"), dict) else {}
    transition = (
        summary.get("queue_transition")
        if isinstance(summary.get("queue_transition"), dict)
        else {}
    )
    action_counts = summary.get("action_counts") if isinstance(summary.get("action_counts"), dict) else {}
    review_gate = str(collateral_review.get("gate") or "").strip()
    batch_review_rows = _safe_int(summary.get("batch_review_rows"))
    reviewed_rows = _safe_int(summary.get("reviewed_rows"))
    source_native_decision_rows = _safe_int(summary.get("source_native_decision_rows"))
    info_missing_rows = _safe_int(summary.get("info_missing_rows"))
    unreviewed_batch_rows = _safe_int(summary.get("unreviewed_batch_rows"))
    unreviewed_or_info_missing_batch_rows = _safe_int(summary.get("unreviewed_or_info_missing_batch_rows"))
    validation_issue_count = _safe_int(summary.get("validation_issue_count"))
    exclusion_candidate_rows = _safe_int(transition.get("exclusion_candidate_rows"))
    if exclusion_candidate_rows is None:
        exclusion_candidate_rows = _safe_int(
            action_counts.get("exclude_from_regression_count_after_gate_wiring")
        )
    if exclusion_candidate_rows is None:
        exclusion_candidate_rows = 0
    reviewed_raw_regression_rows: int | None = None
    reviewed_non_regression_rows: int | None = None
    unreviewed_regression_post_ids: list[int] | None = None
    review_post_ids = _review_post_ids(collateral_review)
    exclusion_post_ids = _exclusion_post_ids(collateral_review)
    if raw_regression_post_ids is not None and review_post_ids is not None:
        reviewed_raw_regression_rows = len(raw_regression_post_ids & review_post_ids)
        reviewed_non_regression_rows = len(review_post_ids - raw_regression_post_ids)
        unreviewed_regression_post_ids = sorted(raw_regression_post_ids - review_post_ids)
        if exclusion_post_ids is not None:
            exclusion_candidate_rows = len(exclusion_post_ids & raw_regression_post_ids)

    blockers: list[str] = []
    if review_gate != "REVIEW-LOCKED":
        blockers.append("collateral_review_gate_not_review_locked")
    if validation_issue_count != 0:
        blockers.append("collateral_review_validation_issues_nonzero")
    if batch_review_rows is None or reviewed_rows is None:
        blockers.append("collateral_review_counts_missing")
    elif reviewed_rows != batch_review_rows:
        blockers.append("collateral_review_not_fully_reviewed")
    if (unreviewed_batch_rows or 0) != 0:
        blockers.append("collateral_review_unreviewed_rows_nonzero")
    full_review_by_post_id = False
    if (
        raw_regression_post_ids is not None
        and review_post_ids is not None
        and raw_regression_count is not None
    ):
        full_review_by_post_id = raw_regression_post_ids.issubset(review_post_ids)

    if raw_regression_count is None:
        blockers.append("collateral_raw_regression_count_missing")
    else:
        scoped_rows = _safe_int(transition.get("original_p0_rows"))
        full_review = batch_review_rows == raw_regression_count
        scoped_p0_review = (
            batch_review_rows is not None
            and batch_review_rows < raw_regression_count
            and scoped_rows == batch_review_rows
        )
        if not (full_review or full_review_by_post_id or scoped_p0_review):
            blockers.append("collateral_review_batch_count_mismatch")
    if raw_regression_count is not None and exclusion_candidate_rows > raw_regression_count:
        blockers.append("collateral_review_exclusion_exceeds_regression_count")
    if batch_review_rows is not None and exclusion_candidate_rows > batch_review_rows:
        blockers.append("collateral_review_exclusion_exceeds_batch_count")

    contract_accounting_details: dict[str, Any] = {
        "provided": contract_accounting is not None,
        "applied": False,
        "accounting_id": contract_accounting.get("accounting_id") if contract_accounting else None,
        "contract_accounted_raw_regression_rows": 0,
        "contract_accounted_additional_rows": 0,
        "ordinary_residual_unprocessed_rows": None,
        "validation_issue_count": None,
        "blockers": [],
    }
    contract_accounted_raw_ids: set[int] = set()
    if contract_accounting is not None:
        accounting_summary = (
            contract_accounting.get("summary")
            if isinstance(contract_accounting.get("summary"), dict)
            else {}
        )
        accounting_gate = str(contract_accounting.get("gate") or "").strip()
        accounting_validation_issues = _safe_int(accounting_summary.get("validation_issue_count"))
        ordinary_residual_rows = _safe_int(accounting_summary.get("ordinary_residual_unprocessed_rows"))
        accounted_post_ids = _contract_accounted_post_ids(contract_accounting)
        accounting_blockers: list[str] = []
        if accounting_gate != "REVIEW-LOCKED":
            accounting_blockers.append("contract_accounting_gate_not_review_locked")
        if accounting_validation_issues != 0:
            accounting_blockers.append("contract_accounting_validation_issues_nonzero")
        if accounted_post_ids is None:
            accounting_blockers.append("contract_accounting_rows_missing")
        if raw_regression_post_ids is None:
            accounting_blockers.append("contract_accounting_requires_row_level_collateral")
        if not accounting_blockers and accounted_post_ids is not None and raw_regression_post_ids is not None:
            exclusion_ids = exclusion_post_ids or set()
            contract_accounted_raw_ids = raw_regression_post_ids & accounted_post_ids
            contract_accounting_details["applied"] = True
            contract_accounting_details["contract_accounted_raw_regression_rows"] = len(contract_accounted_raw_ids)
            contract_accounting_details["contract_accounted_additional_rows"] = len(
                contract_accounted_raw_ids - (exclusion_ids & raw_regression_post_ids)
            )
        contract_accounting_details.update(
            {
                "gate": accounting_gate,
                "ordinary_residual_unprocessed_rows": ordinary_residual_rows,
                "validation_issue_count": accounting_validation_issues,
                "contract_processed_rows": accounting_summary.get("contract_processed_rows"),
                "source_native_processed_rows": accounting_summary.get("source_native_processed_rows"),
                "processed_or_excluded_rows": accounting_summary.get("processed_or_excluded_rows"),
                "contract_accounting_state_counts": accounting_summary.get("contract_accounting_state_counts") or {},
                "blockers": accounting_blockers,
            }
        )
        blockers.extend(accounting_blockers)

    applied = not blockers
    if applied and raw_regression_count is not None:
        if raw_regression_post_ids is not None:
            exclusion_ids = (exclusion_post_ids or set()) & raw_regression_post_ids
            adjusted_post_ids = raw_regression_post_ids - exclusion_ids - contract_accounted_raw_ids
            adjusted = len(adjusted_post_ids)
        else:
            adjusted = max(raw_regression_count - exclusion_candidate_rows, 0)
    else:
        adjusted = raw_regression_count
    if raw_regression_count is not None and reviewed_raw_regression_rows is not None:
        unreviewed_regression_rows = max(raw_regression_count - reviewed_raw_regression_rows, 0)
    elif raw_regression_count is not None and batch_review_rows is not None:
        unreviewed_regression_rows = max(raw_regression_count - batch_review_rows, 0)
    else:
        unreviewed_regression_rows = None
    return {
        "provided": True,
        "applied": applied,
        "review_id": collateral_review.get("review_id"),
        "review_gate": review_gate,
        "review_scope": (
            "full_regression"
            if raw_regression_count is not None and batch_review_rows == raw_regression_count
            else "full_regression_post_id_overlap"
            if full_review_by_post_id
            else "p0_scoped"
            if applied and (unreviewed_regression_rows or 0) > 0
            else "unknown"
        ),
        "batch_review_rows": batch_review_rows,
        "reviewed_rows": reviewed_rows,
        "source_native_decision_rows": source_native_decision_rows,
        "info_missing_rows": info_missing_rows,
        "unreviewed_batch_rows": unreviewed_batch_rows,
        "unreviewed_or_info_missing_batch_rows": unreviewed_or_info_missing_batch_rows,
        "unreviewed_regression_rows": unreviewed_regression_rows,
        "reviewed_raw_regression_rows": reviewed_raw_regression_rows,
        "reviewed_non_regression_rows": reviewed_non_regression_rows,
        "unreviewed_regression_post_ids": unreviewed_regression_post_ids,
        "validation_issue_count": validation_issue_count,
        "exclusion_candidate_rows": exclusion_candidate_rows,
        "contract_accounting": contract_accounting_details,
        "label_counts": summary.get("label_counts") or {},
        "action_counts": action_counts,
        "review_adjusted_regression_count": adjusted,
        "blockers": blockers,
    }


def collateral_gate(
    collateral: dict[str, Any],
    expected_shared_posts: int,
    collateral_review: dict[str, Any] | None = None,
    contract_accounting: dict[str, Any] | None = None,
    adjudication_validation: dict[str, Any] | None = None,
    golden_audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    shared = _safe_int(collateral.get("shared_post_count"))
    changed = _safe_int(collateral.get("changed_post_count"))
    regression_count = _safe_int(collateral.get("collateral_regression_count"))
    baseline_mode = str(collateral.get("baseline_mode") or "bootstrap_20260626").strip()
    collateral_measure = str(collateral.get("collateral_measure") or "").strip()
    adjusted_drift_count = _safe_int(collateral.get("adjusted_drift_count"))
    uses_adjudicated_drift = (
        baseline_mode == "adjudicated_rebaseline"
        or collateral_measure == "adjusted_drift"
    )
    runtime_completed = _safe_int(collateral.get("runtime_completed_count"))
    runtime_flushed = _safe_int(collateral.get("runtime_flushed_count"))
    runtime_pending = _safe_int(collateral.get("runtime_pending_count"))
    runtime_failed = _safe_int(collateral.get("runtime_failed_count"))
    runtime_complete = (
        runtime_completed == expected_shared_posts
        and runtime_flushed == expected_shared_posts
        and runtime_pending == 0
        and runtime_failed == 0
    )
    review_adjustment = _collateral_review_adjustment(
        collateral_review=collateral_review,
        contract_accounting=contract_accounting,
        raw_regression_count=regression_count,
        raw_regression_post_ids=_raw_regression_post_ids(collateral),
    )
    adjusted_regression_count = review_adjustment.get("review_adjusted_regression_count")
    adjudication = adjudication_validation if isinstance(adjudication_validation, dict) else None
    adjudication_validator_gate = str((adjudication or {}).get("validator_gate") or "").strip()
    adjudication_semantic_gate = str((adjudication or {}).get("semantic_gate") or "").strip()
    unreviewed_adjusted_rows = _safe_int((adjudication or {}).get("unreviewed_adjusted_rows"))
    true_semantic_regression_count = _safe_int(
        (adjudication or {}).get("true_semantic_regression_count")
    )
    actionable_unfixed_count = _safe_int((adjudication or {}).get("actionable_unfixed_count"))
    adjudication_binding_issues = (
        _adjudication_binding_issues(
            adjudication=adjudication,
            collateral=collateral,
            golden_audit=golden_audit or {},
            expected_scope_rows=expected_shared_posts,
            expected_golden_rows=PRODUCTION_GOLDEN_ROWS,
        )
        if adjudication is not None
        else []
    )
    adjudication_ok = (
        adjudication is not None
        and adjudication_validator_gate == "GO"
        and adjudication_semantic_gate == "GO"
        and unreviewed_adjusted_rows == 0
        and true_semantic_regression_count == 0
        and actionable_unfixed_count == 0
        and not adjudication_binding_issues
    )
    gate_regression_count = (
        true_semantic_regression_count
        if uses_adjudicated_drift
        else adjusted_regression_count
    )
    gate_metric = (
        "adjudicated_semantic_gate"
        if uses_adjudicated_drift
        else "review_adjusted_regression_count"
        if review_adjustment.get("applied")
        else "collateral_regression_count"
    )
    metric_blockers: list[str] = []
    if uses_adjudicated_drift:
        if adjudication is None:
            metric_blockers.append("collateral_adjudication_validation_missing")
        else:
            if adjudication_binding_issues:
                metric_blockers.append("collateral_adjudication_validation_unbound")
            if adjudication_validator_gate != "GO":
                metric_blockers.append("collateral_adjudication_validator_not_go")
            if adjudication_semantic_gate != "GO":
                metric_blockers.append("collateral_adjudication_semantic_not_go")
            if unreviewed_adjusted_rows != 0:
                metric_blockers.append("collateral_unreviewed_adjusted_rows_nonzero")
            if true_semantic_regression_count != 0:
                metric_blockers.append("collateral_true_semantic_regression_nonzero")
            if actionable_unfixed_count != 0:
                metric_blockers.append("collateral_actionable_unfixed_nonzero")
    passed = (
        shared == expected_shared_posts
        and (adjudication_ok if uses_adjudicated_drift else (gate_regression_count or 0) == 0)
        and (uses_adjudicated_drift or not review_adjustment.get("blockers"))
        and not metric_blockers
        and runtime_complete
    )
    blockers: list[str] = []
    if shared != expected_shared_posts:
        blockers.append("collateral_shared_post_count_mismatch")
    blockers.extend(metric_blockers)
    if not uses_adjudicated_drift:
        blockers.extend(review_adjustment.get("blockers") or [])
    if not uses_adjudicated_drift and (gate_regression_count or 0) != 0:
        blockers.append(
            "collateral_review_adjusted_regression_count_nonzero"
            if review_adjustment.get("applied")
            else "collateral_regression_count_nonzero"
        )
    if (
        review_adjustment.get("applied")
        and (review_adjustment.get("unreviewed_regression_rows") or 0) != 0
    ):
        blockers.append("collateral_review_unreviewed_regression_rows_nonzero")
    if any(value is None for value in (runtime_completed, runtime_flushed, runtime_pending, runtime_failed)):
        blockers.append("collateral_runtime_counts_missing")
    elif not runtime_complete:
        blockers.append("collateral_runtime_not_complete")
    return {
        "gate": "GO" if passed else "NO-GO",
        "expected_shared_posts": expected_shared_posts,
        "shared_post_count": shared,
        "changed_post_count": changed,
        "baseline_mode": baseline_mode,
        "collateral_measure": collateral_measure or (
            "adjusted_drift" if uses_adjudicated_drift else "historical_raw_vs_20260626"
        ),
        "collateral_regression_count": regression_count,
        "historical_raw_collateral_regression_count": _safe_int(
            collateral.get("historical_raw_collateral_regression_count")
        ),
        "adjusted_drift_count": adjusted_drift_count,
        "diagnostic_adjusted_drift_count": adjusted_drift_count,
        "adjudication_validation": adjudication,
        "adjudication_validator_gate": adjudication_validator_gate or None,
        "adjudication_semantic_gate": adjudication_semantic_gate or None,
        "adjudication_binding_issues": adjudication_binding_issues,
        "unreviewed_adjusted_rows": unreviewed_adjusted_rows,
        "true_semantic_regression_count": true_semantic_regression_count,
        "actionable_unfixed_count": actionable_unfixed_count,
        "review_adjusted_regression_count": adjusted_regression_count,
        "gate_metric": gate_metric,
        "gate_regression_count": gate_regression_count,
        "review_adjustment": review_adjustment,
        "runtime_complete": runtime_complete,
        "runtime_completed_count": runtime_completed,
        "runtime_flushed_count": runtime_flushed,
        "runtime_pending_count": runtime_pending,
        "runtime_failed_count": runtime_failed,
        "blockers": blockers,
    }


def evaluate_gates(
    *,
    golden: dict[str, Any],
    collateral: dict[str, Any],
    collateral_review: dict[str, Any] | None = None,
    contract_accounting: dict[str, Any] | None = None,
    adjudication_validation: dict[str, Any] | None = None,
    expected_golden_rows: int = 18,
    expected_collateral_shared_posts: int = 375,
) -> dict[str, Any]:
    golden_result = golden_gate(golden, expected_golden_rows)
    collateral_result = collateral_gate(
        collateral,
        expected_collateral_shared_posts,
        collateral_review=collateral_review,
        contract_accounting=contract_accounting,
        adjudication_validation=adjudication_validation,
        golden_audit=golden,
    )
    uses_adjudicated_rebaseline = (
        collateral_result.get("baseline_mode") == "adjudicated_rebaseline"
        or collateral_result.get("collateral_measure") == "adjusted_drift"
    )
    component_gate = (
        "GO" if golden_result["gate"] == "GO" and collateral_result["gate"] == "GO" else "NO-GO"
    )
    gate = "GO" if component_gate == "GO" and uses_adjudicated_rebaseline else "NO-GO"
    completion_gate_metric = (
        "adjudicated_semantic_gate"
        if uses_adjudicated_rebaseline
        else "not_open_until_adjudicated_rebaseline"
    )
    return {
        "report_type": "always_on_regression_gates",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "gate": gate,
        "component_gate": component_gate,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "completion_gate": "adjusted full375 collateral GO + full_scan path",
        "completion_gate_metric": completion_gate_metric,
        "current_collateral_gate_metric": collateral_result.get("gate_metric"),
        "raw_20260626_baseline_is_completion_gate": False,
        "raw_20260626_baseline_role": "diagnostic historical compare only",
        "rebaseline_status": "APPLIED" if uses_adjudicated_rebaseline else "NOT_APPLIED",
        "policy": {
            "golden_expected_rows": expected_golden_rows,
            "full_375_collateral_required": True,
            "golden_pass_alone_is_not_approval": True,
            "collateral_runtime_pass_alone_is_not_approval": True,
            "collateral_source_native_exclusion_requires_clean_review_summary": True,
            "collateral_contract_accounting_is_not_full_scan_approval": True,
            "completion_gate_uses_adjusted_metric_after_adjudication": True,
            "adjusted_drift_count_is_diagnostic": True,
            "adjudicated_gate_requires_validator_go": True,
            "adjudicated_gate_requires_source_bound_validator_receipt": True,
            "adjudicated_gate_requires_unreviewed_and_true_regression_zero": True,
            "collateral_runtime_requires_completed_flushed_pending_failed_375_375_0_0": True,
            "historical_raw_vs_20260626_is_not_completion_gate": True,
        },
        "golden": golden_result,
        "collateral": collateral_result,
        "blockers": [
            *[f"golden:{code}" for code in golden_result["blockers"]],
            *[f"collateral:{code}" for code in collateral_result["blockers"]],
            *(
                ["collateral:adjudicated_rebaseline_required_for_completion"]
                if not uses_adjudicated_rebaseline
                else []
            ),
        ],
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    def display(value: Any) -> str:
        return "null" if value is None else str(value)

    lines = [
        "# 상시 회귀 게이트",
        "",
        f"- gate: `{report['gate']}`",
        f"- semantic_quality: `{report['semantic_quality']}`",
        f"- full_scan_approval: `{str(report['full_scan_approval']).lower()}`",
        f"- completion_gate: `{report.get('completion_gate')}`",
        f"- completion_gate_metric: `{report.get('completion_gate_metric')}`",
        f"- current_collateral_gate_metric: `{report.get('current_collateral_gate_metric')}`",
        f"- rebaseline_status: `{report.get('rebaseline_status')}`",
        (
            "- raw_20260626_baseline_is_completion_gate: "
            f"`{str(report.get('raw_20260626_baseline_is_completion_gate')).lower()}`"
        ),
        f"- 정책: golden-{report['golden']['expected_rows']}과 full 375 collateral diff를 항상 함께 요구한다.",
        "",
        "## Golden 게이트",
        "",
        f"- gate: `{report['golden']['gate']}`",
        f"- rows: `{report['golden']['row_count']}/{report['golden']['expected_rows']}`",
        f"- passed: `{display(report['golden']['passed_count'])}`",
        f"- failed: `{display(report['golden']['failed_count'])}`",
        f"- runtime_complete: `{report['golden']['runtime_complete']}`",
        "",
        "## Collateral 게이트",
        "",
        f"- gate: `{report['collateral']['gate']}`",
        (
            "- shared posts: "
            f"`{report['collateral']['shared_post_count']}/{report['collateral']['expected_shared_posts']}`"
        ),
        f"- baseline_mode: `{report['collateral'].get('baseline_mode')}`",
        f"- collateral_measure: `{report['collateral'].get('collateral_measure')}`",
        f"- changed posts: `{report['collateral']['changed_post_count']}`",
        f"- raw collateral_regression_count: `{report['collateral']['collateral_regression_count']}`",
        (
            "- historical_raw_collateral_regression_count: "
            f"`{display(report['collateral'].get('historical_raw_collateral_regression_count'))}`"
        ),
        f"- adjusted_drift_count: `{display(report['collateral'].get('adjusted_drift_count'))}`",
        f"- adjudication_validator_gate: `{display(report['collateral'].get('adjudication_validator_gate'))}`",
        f"- adjudication_semantic_gate: `{display(report['collateral'].get('adjudication_semantic_gate'))}`",
        f"- unreviewed_adjusted_rows: `{display(report['collateral'].get('unreviewed_adjusted_rows'))}`",
        f"- true_semantic_regression_count: `{display(report['collateral'].get('true_semantic_regression_count'))}`",
        f"- actionable_unfixed_count: `{display(report['collateral'].get('actionable_unfixed_count'))}`",
        (
            "- review exclusion candidates: "
            f"`{report['collateral']['review_adjustment'].get('exclusion_candidate_rows')}`"
        ),
        (
            "- review adjustment applied: "
            f"`{report['collateral']['review_adjustment'].get('applied')}`"
        ),
        (
            "- review scope: "
            f"`{report['collateral']['review_adjustment'].get('review_scope')}`"
        ),
        (
            "- source-native decision rows: "
            f"`{display(report['collateral']['review_adjustment'].get('source_native_decision_rows'))}`"
        ),
        (
            "- info missing rows: "
            f"`{display(report['collateral']['review_adjustment'].get('info_missing_rows'))}`"
        ),
        (
            "- unreviewed or info-missing rows: "
            f"`{display(report['collateral']['review_adjustment'].get('unreviewed_or_info_missing_batch_rows'))}`"
        ),
        (
            "- unreviewed regression rows: "
            f"`{report['collateral']['review_adjustment'].get('unreviewed_regression_rows')}`"
        ),
        (
            "- reviewed raw regression rows: "
            f"`{display(report['collateral']['review_adjustment'].get('reviewed_raw_regression_rows'))}`"
        ),
        (
            "- reviewed non-regression rows: "
            f"`{display(report['collateral']['review_adjustment'].get('reviewed_non_regression_rows'))}`"
        ),
        (
            "- review_adjusted_regression_count: "
            f"`{report['collateral']['review_adjusted_regression_count']}`"
        ),
        f"- gate_metric: `{report['collateral'].get('gate_metric')}`",
        f"- gate_regression_count: `{display(report['collateral'].get('gate_regression_count'))}`",
        f"- runtime_complete: `{report['collateral']['runtime_complete']}`",
        "",
        "## 완료 Gate 해석",
        "",
    ]
    if report.get("completion_gate_metric") == "adjudicated_semantic_gate":
        lines.append(
            "판결 baseline이 적용된 상태이므로 완료 gate는 validator가 재계산한 "
            "`unreviewed_adjusted_rows=0`, `true_semantic_regression_count=0`, "
            "`actionable_unfixed_count=0`을 본다. adjusted drift와 2026-06-26 raw diff는 diagnostic이다."
        )
    else:
        lines.append(
            "아직 adjudicated re-baseline이 적용되지 않았으므로 completion gate는 열리지 않는다. "
            "현재 bootstrap raw diff는 진단용이며, 완료 기준은 전 행 판결 후 adjusted full375 collateral GO와 full_scan path다."
        )
    lines.extend(
        [
            "",
            "## Contract 회계 조정",
            "",
        ]
    )
    contract_accounting = report["collateral"]["review_adjustment"].get("contract_accounting") or {}
    if contract_accounting.get("provided"):
        lines.extend(
            [
                f"- applied: `{contract_accounting.get('applied')}`",
                f"- accounting_id: `{contract_accounting.get('accounting_id')}`",
                f"- processed_or_excluded_rows: `{display(contract_accounting.get('processed_or_excluded_rows'))}`",
                f"- ordinary_residual_unprocessed_rows: `{display(contract_accounting.get('ordinary_residual_unprocessed_rows'))}`",
                f"- contract_accounted_raw_regression_rows: `{contract_accounting.get('contract_accounted_raw_regression_rows')}`",
                f"- contract_accounted_additional_rows: `{contract_accounting.get('contract_accounted_additional_rows')}`",
                f"- validation_issue_count: `{display(contract_accounting.get('validation_issue_count'))}`",
                "",
            ]
        )
    else:
        lines.extend(["- provided: `false`", ""])
    lines.extend(
        [
            "## 차단 항목",
            "",
        ]
    )
    if report["blockers"]:
        for blocker in report["blockers"]:
            lines.append(f"- `{blocker}`")
    else:
        lines.append("- 없음")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate golden plus full 375 collateral as always-on gates.")
    parser.add_argument("--golden-audit", required=True, type=Path)
    parser.add_argument("--collateral-compare", required=True, type=Path)
    parser.add_argument("--collateral-review-summary", type=Path, default=None)
    parser.add_argument("--contract-accounting", type=Path, default=None)
    parser.add_argument("--collateral-adjudication-validation", type=Path, default=None)
    parser.add_argument("--expected-golden-rows", type=int, default=18)
    parser.add_argument("--expected-collateral-shared-posts", type=int, default=375)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-no-go", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.expected_golden_rows != PRODUCTION_GOLDEN_ROWS:
        raise SystemExit(
            f"production golden scope is fixed at {PRODUCTION_GOLDEN_ROWS}; "
            f"got {args.expected_golden_rows}"
        )
    if args.expected_collateral_shared_posts != PRODUCTION_PANEL_ROWS:
        raise SystemExit(
            f"production collateral scope is fixed at {PRODUCTION_PANEL_ROWS}; "
            f"got {args.expected_collateral_shared_posts}"
        )
    report = evaluate_gates(
        golden=load_json(args.golden_audit),
        collateral=load_json(args.collateral_compare),
        collateral_review=(
            load_json(args.collateral_review_summary)
            if args.collateral_review_summary
            else None
        ),
        contract_accounting=(
            load_json(args.contract_accounting)
            if args.contract_accounting
            else None
        ),
        adjudication_validation=(
            load_json(args.collateral_adjudication_validation)
            if args.collateral_adjudication_validation
            else None
        ),
        expected_golden_rows=args.expected_golden_rows,
        expected_collateral_shared_posts=args.expected_collateral_shared_posts,
    )
    write_json(args.output_json, report)
    write_markdown(report, args.output_md)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.fail_on_no_go and report["gate"] != "GO":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
