from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_adjusted_collateral_adjudication import (
    DERIVATION_VERSION,
    _load_jsonl,
    build_adjudication,
)
from tools.build_adjusted_collateral_blind_packet import (
    PRODUCTION_GOLDEN_ROWS,
    PRODUCTION_PANEL_ROWS,
    canonical_digest,
    file_sha256,
    prepare_bound_scope,
    validate_blind_material,
)
from tools.compare_completed779_improvement import load_json_or_jsonl


VALIDATOR_VERSION = "adjusted-collateral-adjudication-validator-v2"
VALIDATION_REPORT_TYPE = "adjusted_full375_collateral_adjudication_validation"
VALIDATED_FIELDS = (
    "report_type",
    "derivation_version",
    "baseline_mode",
    "diagnostic_adjusted_drift_count",
    "drift_union_count",
    "verdict_row_count",
    "valid_reviewed_row_count",
    "unreviewed_adjusted_rows",
    "true_semantic_regression_count",
    "actionable_unfixed_count",
    "expected_scope_rows",
    "expected_golden_rows",
    "drift_ids",
    "drift_post_ids",
    "missing_verdict_drift_ids",
    "extra_verdict_drift_ids",
    "duplicate_verdict_drift_ids",
    "invalid_verdict_drift_ids",
    "unreviewed_adjusted_drift_ids",
    "unreviewed_adjusted_post_ids",
    "true_semantic_regression_drift_ids",
    "true_semantic_regression_post_ids",
    "classification_counts",
    "golden_audit_diagnostic",
    "validation_issues",
    "source_binding",
    "reviewed_rows",
    "derivation_digest",
    "gate",
    "adjusted_full375_collateral",
)
VALIDATION_RECEIPT_FIELDS = (
    "report_type",
    "validator_version",
    "validator_code_sha256",
    "derivation_version",
    "validator_gate",
    "semantic_gate",
    "gate",
    "expected_scope_rows",
    "expected_golden_rows",
    "source_compare_digest",
    "source_changed_count",
    "authoritative_trust_gate",
    "trust_root_digest",
    "bound_after_payload_sha256",
    "raw_judge_receipt_sha256",
    "trust_anchors",
    "drift_union_count",
    "unreviewed_adjusted_rows",
    "true_semantic_regression_count",
    "actionable_unfixed_count",
    "validated_payload_digest",
    "collateral_binding_digest",
    "source_value_digests",
    "source_artifact_paths",
    "source_artifact_hashes",
    "mismatched_fields",
    "artifact_hash_mismatches",
    "independent_source_validation_issues",
    "validation_issues",
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def current_validator_code_sha256() -> str:
    return file_sha256(Path(__file__))


def validation_receipt_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {field: payload.get(field) for field in VALIDATION_RECEIPT_FIELDS}


def validation_receipt_digest(payload: dict[str, Any]) -> str:
    return canonical_digest(validation_receipt_payload(payload))


def finalize_validation_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    output = dict(payload)
    output["validator_code_sha256"] = current_validator_code_sha256()
    output["validation_receipt_digest"] = validation_receipt_digest(output)
    return output


def validate_adjudication(
    *,
    report: dict[str, Any],
    compare: dict[str, Any],
    verdict_rows: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    after_rows: list[dict[str, Any]],
    golden_manifest: Any,
    blind_packet_rows: list[dict[str, Any]],
    blind_map: dict[str, Any],
    expected_scope_rows: int = PRODUCTION_PANEL_ROWS,
    expected_golden_rows: int = PRODUCTION_GOLDEN_ROWS,
    allow_multi_variant: bool = False,
    trust_bundle: dict[str, Any] | None = None,
    allow_untrusted_test_scope: bool = False,
    artifact_hashes: dict[str, str] | None = None,
    adjudication_report_path: Path | None = None,
) -> dict[str, Any]:
    # This is deliberately performed before the builder recomputation.  It
    # independently binds the compare, panel order, and blind packet/map to the
    # source artifacts instead of trusting the builder's derived counters.
    scope = prepare_bound_scope(
        compare=compare,
        baseline_rows=baseline_rows,
        source_rows=source_rows,
        after_rows=after_rows,
        golden_manifest=golden_manifest,
        expected_scope_rows=expected_scope_rows,
        expected_golden_rows=expected_golden_rows,
        allow_multi_variant=allow_multi_variant,
        trust_bundle=trust_bundle,
        allow_untrusted_test_scope=allow_untrusted_test_scope,
    )
    independent_source_issues = validate_blind_material(
        scope=scope,
        blind_packet_rows=blind_packet_rows,
        blind_map=blind_map,
    )
    expected = build_adjudication(
        compare=compare,
        verdict_rows=verdict_rows,
        baseline_rows=baseline_rows,
        source_rows=source_rows,
        after_rows=after_rows,
        golden_manifest=golden_manifest,
        blind_packet_rows=blind_packet_rows,
        blind_map=blind_map,
        expected_scope_rows=expected_scope_rows,
        expected_golden_rows=expected_golden_rows,
        allow_multi_variant=allow_multi_variant,
        trust_bundle=trust_bundle,
        allow_untrusted_test_scope=allow_untrusted_test_scope,
        generated_at="validator_recompute",
    )
    mismatched_fields = [field for field in VALIDATED_FIELDS if report.get(field) != expected.get(field)]
    issues: list[str] = []
    if mismatched_fields:
        issues.append("derived_fields_mismatch")
    if independent_source_issues:
        issues.append("independent_source_binding_failed")
    artifacts = report.get("artifacts") if isinstance(report.get("artifacts"), dict) else {}
    artifact_hash_mismatches: list[str] = []
    if artifact_hashes is not None:
        for field, actual_hash in artifact_hashes.items():
            if artifacts.get(field) != actual_hash:
                artifact_hash_mismatches.append(field)
        if artifact_hash_mismatches:
            issues.append("artifact_hash_mismatch")
    approval_boundary = report.get("approval_boundary") if isinstance(report.get("approval_boundary"), dict) else {}
    if approval_boundary.get("gate_is_derived_not_user_supplied") is not True:
        issues.append("derived_gate_boundary_missing")
    if approval_boundary.get("source_compare_is_recomputed_from_bound_artifacts") is not True:
        issues.append("source_recompute_boundary_missing")
    if approval_boundary.get("builder_output_requires_independent_validator") is not True:
        issues.append("independent_validator_boundary_missing")

    validator_gate = "GO" if not issues else "NO-GO"
    semantic_gate = expected.get("gate") if validator_gate == "GO" else "NO-GO"
    source_value_digests = {
        "collateral_compare": canonical_digest(compare),
        "baseline_result": canonical_digest(baseline_rows),
        "source_input": canonical_digest(source_rows),
        "after_result": canonical_digest(after_rows),
        "golden_manifest": canonical_digest(golden_manifest),
        "blind_packet": canonical_digest(blind_packet_rows),
        "blind_private_map": canonical_digest(blind_map),
        "verdict_rows": canonical_digest(verdict_rows),
    }
    if isinstance(trust_bundle, dict) and isinstance(trust_bundle.get("artifact_paths"), dict):
        for key in (
            "baseline_manifest",
            "merged_manifest",
            "merged_checkpoint",
            "merged_pending",
            "merge_binding_receipt",
            "merge_integrity",
            "runtime_trust_anchor",
            "golden_audit",
            "raw_judge_receipt",
            "thread_readback_receipt",
        ):
            path_value = trust_bundle["artifact_paths"].get(key)
            if path_value:
                source_value_digests[key] = canonical_digest(
                    load_json_or_jsonl(Path(str(path_value)))
                    if key == "merged_checkpoint"
                    else json.loads(
                        Path(str(path_value)).read_text(encoding="utf-8-sig")
                    )
                )
    collateral_binding = {
        "source_compare_digest": source_value_digests["collateral_compare"],
        "expected_scope_rows": expected_scope_rows,
        "expected_golden_rows": expected_golden_rows,
        "source_changed_count": compare.get("changed_post_count"),
        "drift_ids": expected.get("drift_ids"),
        "post_id_order_digest": canonical_digest(scope["post_id_order"]),
        "source_value_digests": source_value_digests,
    }
    source_artifact_paths = {
        key: str(Path(str(artifacts.get(key))).resolve())
        for key in (
            "collateral_compare",
            "baseline_result",
            "source_input",
            "after_result",
            "golden_manifest",
            "blind_packet_jsonl",
            "blind_map_json",
            "verdicts_jsonl",
            "baseline_manifest",
            "merged_manifest",
            "merged_checkpoint",
            "merged_pending",
            "merge_binding_receipt",
            "merge_integrity",
            "runtime_trust_anchor",
            "golden_audit",
            "raw_judge_receipt",
            "thread_readback_receipt",
        )
        if artifacts.get(key)
    }
    source_artifact_hashes = dict(sorted((artifact_hashes or {}).items()))
    if adjudication_report_path is not None:
        resolved_report_path = adjudication_report_path.resolve()
        source_artifact_paths["adjudication_report"] = str(resolved_report_path)
        source_artifact_hashes["adjudication_report_sha256"] = file_sha256(resolved_report_path)
    output = {
        "report_type": VALIDATION_REPORT_TYPE,
        "validator_version": VALIDATOR_VERSION,
        "validator_code_sha256": None,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "validator_gate": validator_gate,
        "semantic_gate": semantic_gate,
        "gate": "GO" if validator_gate == "GO" and semantic_gate == "GO" else "NO-GO",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "derivation_version": expected.get("derivation_version"),
        "expected_scope_rows": expected_scope_rows,
        "expected_golden_rows": expected_golden_rows,
        "source_compare_digest": source_value_digests["collateral_compare"],
        "source_changed_count": compare.get("changed_post_count"),
        "authoritative_trust_gate": expected.get("source_binding", {}).get(
            "authoritative_trust", {}
        ).get("gate"),
        "trust_root_digest": expected.get("source_binding", {}).get(
            "authoritative_trust", {}
        ).get("trust_root_digest"),
        "bound_after_payload_sha256": expected.get("source_binding", {}).get(
            "authoritative_trust", {}
        ).get("after_payload_sha256"),
        "raw_judge_receipt_sha256": expected.get("source_binding", {}).get(
            "raw_judge_provenance", {}
        ).get("raw_judge_receipt_sha256"),
        "trust_anchors": dict(
            sorted(
                {
                    **((trust_bundle or {}).get("anchors", {})),
                    **expected.get("source_binding", {})
                    .get("authoritative_trust", {})
                    .get("anchors", {}),
                }.items()
            )
        ),
        "report_derivation_digest": report.get("derivation_digest"),
        "recomputed_derivation_digest": expected.get("derivation_digest"),
        "validated_payload_digest": canonical_digest(
            {field: expected.get(field) for field in VALIDATED_FIELDS}
        ),
        "collateral_binding_digest": canonical_digest(collateral_binding),
        "source_value_digests": source_value_digests,
        "source_artifact_paths": source_artifact_paths,
        "source_artifact_hashes": source_artifact_hashes,
        "mismatched_fields": mismatched_fields,
        "artifact_hash_mismatches": artifact_hash_mismatches,
        "independent_source_validation_issues": independent_source_issues,
        "validation_issues": issues,
        "drift_union_count": expected.get("drift_union_count"),
        "unreviewed_adjusted_rows": expected.get("unreviewed_adjusted_rows"),
        "true_semantic_regression_count": expected.get("true_semantic_regression_count"),
        "actionable_unfixed_count": expected.get("actionable_unfixed_count"),
        "classification_counts": expected.get("classification_counts"),
        "unreviewed_adjusted_drift_ids": expected.get("unreviewed_adjusted_drift_ids"),
        "true_semantic_regression_drift_ids": expected.get("true_semantic_regression_drift_ids"),
        "approval_boundary": {
            "validator_recomputed_from_source_artifacts": True,
            "validator_rebuilt_blind_packet_and_private_map": True,
            "validator_go_is_not_semantic_go": True,
            "semantic_go_requires_unreviewed_and_true_regression_zero": True,
            "receipt_is_bound_to_compare_and_source_value_digests": True,
            "production_full_scan_approval": False,
        },
    }
    return finalize_validation_receipt(output)


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# 판결 기반 full375 collateral validator",
        "",
        f"- validator_gate: `{report['validator_gate']}`",
        f"- semantic_gate: `{report['semantic_gate']}`",
        f"- combined gate: `{report['gate']}`",
        f"- source_compare_digest: `{report['source_compare_digest']}`",
        f"- collateral_binding_digest: `{report['collateral_binding_digest']}`",
        f"- validation_receipt_digest: `{report['validation_receipt_digest']}`",
        f"- drift_union_count: `{report['drift_union_count']}`",
        f"- unreviewed_adjusted_rows: `{report['unreviewed_adjusted_rows']}`",
        f"- true_semantic_regression_count: `{report['true_semantic_regression_count']}`",
        f"- mismatched_fields: `{report['mismatched_fields']}`",
        f"- artifact_hash_mismatches: `{report['artifact_hash_mismatches']}`",
        f"- independent_source_validation_issues: `{report['independent_source_validation_issues']}`",
        f"- validation_issues: `{report['validation_issues']}`",
        "- Validator는 builder GO를 신뢰하지 않고 source artifact에서 scope와 blind material을 먼저 재구성한다.",
        "- combined GO는 현재 validator 코드 hash와 compare/source binding receipt가 일치할 때만 유효하다.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Independently validate source-bound adjusted collateral adjudication.")
    parser.add_argument("--adjudication-report", required=True, type=Path)
    parser.add_argument("--collateral-compare", required=True, type=Path)
    parser.add_argument("--baseline-result", required=True, type=Path)
    parser.add_argument("--baseline-manifest", required=True, type=Path)
    parser.add_argument("--source-input", required=True, type=Path)
    parser.add_argument("--after-result", required=True, type=Path)
    parser.add_argument("--merged-manifest", required=True, type=Path)
    parser.add_argument("--merged-checkpoint", required=True, type=Path)
    parser.add_argument("--merged-pending", required=True, type=Path)
    parser.add_argument("--merge-binding-receipt", required=True, type=Path)
    parser.add_argument("--merge-integrity", type=Path)
    parser.add_argument("--runtime-trust-anchor", required=True, type=Path)
    parser.add_argument("--golden-manifest", required=True, type=Path)
    parser.add_argument("--golden-audit", required=True, type=Path)
    parser.add_argument("--raw-judge-receipt", required=True, type=Path)
    parser.add_argument("--thread-readback-receipt", type=Path)
    parser.add_argument("--trusted-baseline-manifest-sha256", required=True)
    parser.add_argument("--trusted-panel-source-sha256", required=True)
    parser.add_argument("--trusted-golden-manifest-sha256", required=True)
    parser.add_argument("--blind-packet-jsonl", required=True, type=Path)
    parser.add_argument("--blind-map-json", required=True, type=Path)
    parser.add_argument("--verdicts-jsonl", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-no-go", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = _load_json(args.adjudication_report)
    compare = _load_json(args.collateral_compare)
    baseline_rows = load_json_or_jsonl(args.baseline_result)
    source_rows = load_json_or_jsonl(args.source_input)
    after_rows = load_json_or_jsonl(args.after_result)
    golden = _load_json(args.golden_manifest)
    blind_packet_rows = _load_jsonl(args.blind_packet_jsonl)
    blind_map = _load_json(args.blind_map_json)
    verdict_rows = _load_jsonl(args.verdicts_jsonl)
    if verdict_rows and args.thread_readback_receipt is None:
        raise SystemExit("nonzero adjudication requires --thread-readback-receipt")
    trust_bundle = {
        "artifact_paths": {
            "baseline_result": args.baseline_result,
            "baseline_manifest": args.baseline_manifest,
            "source_input": args.source_input,
            "after_result": args.after_result,
            "merged_manifest": args.merged_manifest,
            "merged_checkpoint": args.merged_checkpoint,
            "merged_pending": args.merged_pending,
            "merge_binding_receipt": args.merge_binding_receipt,
            "runtime_trust_anchor": args.runtime_trust_anchor,
            "golden_manifest": args.golden_manifest,
            "golden_audit": args.golden_audit,
            "raw_judge_receipt": args.raw_judge_receipt,
            **(
                {"thread_readback_receipt": args.thread_readback_receipt}
                if args.thread_readback_receipt is not None
                else {}
            ),
            "blind_packet_jsonl": args.blind_packet_jsonl,
            "verdicts_jsonl": args.verdicts_jsonl,
            **(
                {"merge_integrity": args.merge_integrity}
                if args.merge_integrity is not None
                else {}
            ),
        },
        "anchors": {
            "baseline_manifest_sha256": args.trusted_baseline_manifest_sha256,
            "panel_source_sha256": args.trusted_panel_source_sha256,
            "golden_manifest_sha256": args.trusted_golden_manifest_sha256,
        },
    }
    artifact_hashes = {
        "collateral_compare_sha256": file_sha256(args.collateral_compare),
        "baseline_result_sha256": file_sha256(args.baseline_result),
        "baseline_manifest_sha256": file_sha256(args.baseline_manifest),
        "source_input_sha256": file_sha256(args.source_input),
        "after_result_sha256": file_sha256(args.after_result),
        "merged_manifest_sha256": file_sha256(args.merged_manifest),
        "merged_checkpoint_sha256": file_sha256(args.merged_checkpoint),
        "merged_pending_sha256": file_sha256(args.merged_pending),
        "merge_binding_receipt_sha256": file_sha256(args.merge_binding_receipt),
        **(
            {"merge_integrity_sha256": file_sha256(args.merge_integrity)}
            if args.merge_integrity is not None
            else {}
        ),
        "runtime_trust_anchor_sha256": file_sha256(args.runtime_trust_anchor),
        "golden_manifest_sha256": file_sha256(args.golden_manifest),
        "golden_audit_sha256": file_sha256(args.golden_audit),
        "raw_judge_receipt_sha256": file_sha256(args.raw_judge_receipt),
        **(
            {
                "thread_readback_receipt_sha256": file_sha256(
                    args.thread_readback_receipt
                )
            }
            if args.thread_readback_receipt is not None
            else {}
        ),
        "blind_packet_jsonl_sha256": file_sha256(args.blind_packet_jsonl),
        "blind_map_json_sha256": file_sha256(args.blind_map_json),
        "verdicts_jsonl_sha256": file_sha256(args.verdicts_jsonl),
    }
    validation = validate_adjudication(
        report=report,
        compare=compare,
        verdict_rows=verdict_rows,
        baseline_rows=baseline_rows,
        source_rows=source_rows,
        after_rows=after_rows,
        golden_manifest=golden,
        blind_packet_rows=blind_packet_rows,
        blind_map=blind_map,
        expected_scope_rows=PRODUCTION_PANEL_ROWS,
        expected_golden_rows=PRODUCTION_GOLDEN_ROWS,
        trust_bundle=trust_bundle,
        artifact_hashes=artifact_hashes,
        adjudication_report_path=args.adjudication_report,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    with args.output_json.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(validation, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    write_markdown(args.output_md, validation)
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 2 if args.fail_on_no_go and validation["gate"] != "GO" else 0


if __name__ == "__main__":
    raise SystemExit(main())
