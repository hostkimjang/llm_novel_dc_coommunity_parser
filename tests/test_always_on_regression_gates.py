import copy
import hashlib
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.audit_regression_safe_golden import (
    build_audit as build_golden_audit,
    expected_is_hypothesis,
    expected_title_matches,
)
from tools.build_adjusted_collateral_adjudication import (
    DERIVATION_VERSION,
    PRODUCTION_CODEX_CLI_TRUST_ANCHOR_SHA256,
    REVIEWED_PREDECESSOR_SECURITY_DEPENDENCY_SNAPSHOTS,
    RAW_JUDGE_REPORT_TYPE,
    RAW_JUDGE_VERSION,
    _validate_primary_command_vector,
    _validate_readback_command_vector,
    _require_exact_primary_binding,
    blind_receipt_digest,
    build_adjudication,
    preflight_raw_codex_judge_receipt_for_readback,
)
from tools.build_adjusted_collateral_blind_packet import (
    PRODUCTION_GOAL_ID,
    PRODUCTION_BASELINE_MANIFEST_PATH,
    PRODUCTION_BASELINE_MANIFEST_SHA256,
    PRODUCTION_BASELINE_RESULT_PATH,
    PRODUCTION_GOLDEN_MANIFEST_PATH,
    PRODUCTION_GOLDEN_MANIFEST_SHA256,
    PRODUCTION_PANEL_SOURCE_PATH,
    PRODUCTION_PANEL_SOURCE_SHA256,
    RUNTIME_TRUST_ANCHOR_VERSION,
    build_blind_packet,
    canonical_digest,
    file_sha256,
)
from tools.run_codex_blind_adjudication import (
    CONTINUATION_SOURCE_SESSION,
    PRODUCTION_REASONING_EFFORT,
    RUNNER_VERSION,
    RECEIPT_DIGEST_CONTRACT,
    RUNNER_SECURITY_DEPENDENCY_PATHS,
    _build_session_bundle_stage,
    build_security_dependency_manifest,
    enumerate_allowed_evidence_refs,
    _validate_model_response,
    build_output_schema,
    build_prompt,
    capture_security_dependency_snapshot,
)
from tools.verify_codex_blind_judge_thread import (
    RECEIPT_VERSION as READBACK_RECEIPT_VERSION,
    REPORT_TYPE as READBACK_REPORT_TYPE,
    TRUST_BOUNDARY as READBACK_TRUST_BOUNDARY,
    VERIFIER_VERSION as READBACK_VERIFIER_VERSION,
    VERIFIER_SECURITY_DEPENDENCY_PATHS,
    build_readback_prompt,
    build_readback_schema,
)
from tools.compare_completed779_improvement import analysis_identity, load_json_or_jsonl
from tools.build_codex_cli_trust_anchor import validate_trust_anchor
from tools.evaluate_always_on_regression_gates import _canonical_digest, evaluate_gates
from tools.merge_interrupted_run_results import finalize_merge_binding_receipt
from tools.validate_adjusted_collateral_adjudication import (
    VALIDATION_REPORT_TYPE,
    VALIDATOR_VERSION,
    finalize_validation_receipt,
    validate_adjudication,
)
from tests.test_adjusted_collateral_adjudication import (
    compare_payload as _real_compare_payload,
    runtime_row as _real_runtime_row,
    source_row as _real_source_row,
    verdict_for as _real_verdict_for,
)


RUNTIME_TRUST_ANCHOR_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs/devs/loop641_premerge_runtime_trust_anchor_v2.json"
)
CODEX_CLI_TRUST_ANCHOR_PATH = (
    PRODUCTION_BASELINE_RESULT_PATH.parent.parent
    / "review/loop641_codex_cli_native_trust_anchor_v2.json"
)
PRODUCTION_REVIEW_DIR = PRODUCTION_BASELINE_RESULT_PATH.parent.parent / "review"
PRODUCTION_CANONICAL_HASHES = {
    PRODUCTION_BASELINE_RESULT_PATH: "958b5c547e03df3931d25606b4e8204fcb85a58a6642d70443478adad91c74cb",
    PRODUCTION_BASELINE_MANIFEST_PATH: PRODUCTION_BASELINE_MANIFEST_SHA256,
    PRODUCTION_PANEL_SOURCE_PATH: PRODUCTION_PANEL_SOURCE_SHA256,
    PRODUCTION_GOLDEN_MANIFEST_PATH: PRODUCTION_GOLDEN_MANIFEST_SHA256,
    RUNTIME_TRUST_ANCHOR_PATH: "8a7487cff066d162c556678b3f76971436b4a4cba0aad1963b0312af0d2956b8",
    CODEX_CLI_TRUST_ANCHOR_PATH: "b017035b778fc71b31621306c51cb90114b19d1768253009dc3ba91ea288cfb0",
}


def _golden(**overrides):
    payload = {
        "row_count": 18,
        "passed_count": 18,
        "failed_count": 0,
        "canary_semantic_gate": "PASS",
        "runtime": {
            "completed_count": 18,
            "pending_count": 0,
            "failed_count": 0,
        },
    }
    payload.update(overrides)
    return payload


def _collateral(**overrides):
    payload = {
        "shared_post_count": 375,
        "changed_post_count": 0,
        "collateral_regression_count": 0,
        "runtime_completed_count": 375,
        "runtime_flushed_count": 375,
        "runtime_pending_count": 0,
        "runtime_failed_count": 0,
    }
    payload.update(overrides)
    return payload


def _collateral_review(**overrides):
    payload = {
        "review_id": "unit_collateral_review",
        "gate": "REVIEW-LOCKED",
        "summary": {
            "batch_review_rows": 183,
            "reviewed_rows": 183,
            "unreviewed_batch_rows": 0,
            "validation_issue_count": 0,
            "label_counts": {"ACCEPT": 57, "REPROCESS": 95, "HOLD": 31},
            "action_counts": {
                "exclude_from_regression_count_after_gate_wiring": 57,
                "repair_safe_loss": 76,
            },
            "queue_transition": {
                "exclusion_candidate_rows": 57,
                "residual_action_queue_rows": 126,
            },
        },
    }
    payload.update(overrides)
    return payload


def _adjudication_validation(*, collateral=None, artifact_dir=None, **overrides):
    bound_collateral = collateral or _collateral(
        changed_post_count=141,
        collateral_regression_count=141,
        historical_raw_collateral_regression_count=141,
        baseline_mode="adjudicated_rebaseline",
        collateral_measure="adjusted_drift",
        adjusted_drift_count=141,
    )
    compare_digest = _canonical_digest(bound_collateral)
    changed_count = bound_collateral["changed_post_count"]
    artifact_values = {
        "collateral_compare": bound_collateral,
        "baseline_result": [{"post_id": 1, "kind": "baseline"}],
        "source_input": [{"post_id": 1, "kind": "source"}],
        "after_result": [{"post_id": 1, "kind": "after"}],
        "golden_manifest": {"rows": [{"post_id": 1, "kind": "golden"}]},
        "blind_packet_jsonl": [{"post_id": 1, "kind": "packet"}],
        "blind_map_json": {"rows": [{"post_id": 1, "kind": "map"}]},
        "verdicts_jsonl": [{"post_id": 1, "kind": "verdict"}],
    }
    source_value_digests = {
        "collateral_compare": compare_digest,
        "baseline_result": _canonical_digest(artifact_values["baseline_result"]),
        "source_input": _canonical_digest(artifact_values["source_input"]),
        "after_result": _canonical_digest(artifact_values["after_result"]),
        "golden_manifest": _canonical_digest(artifact_values["golden_manifest"]),
        "blind_packet": _canonical_digest(artifact_values["blind_packet_jsonl"]),
        "blind_private_map": _canonical_digest(artifact_values["blind_map_json"]),
        "verdict_rows": _canonical_digest(artifact_values["verdicts_jsonl"]),
    }
    artifact_paths = {}
    artifact_hashes = {}
    if artifact_dir is not None:
        root = Path(artifact_dir)
        path_names = {
            "collateral_compare": "collateral.json",
            "baseline_result": "baseline.json",
            "source_input": "source.jsonl",
            "after_result": "after.json",
            "golden_manifest": "golden.json",
            "blind_packet_jsonl": "packet.jsonl",
            "blind_map_json": "map.json",
            "verdicts_jsonl": "verdicts.jsonl",
        }
        hash_names = {
            "collateral_compare": "collateral_compare_sha256",
            "baseline_result": "baseline_result_sha256",
            "source_input": "source_input_sha256",
            "after_result": "after_result_sha256",
            "golden_manifest": "golden_manifest_sha256",
            "blind_packet_jsonl": "blind_packet_jsonl_sha256",
            "blind_map_json": "blind_map_json_sha256",
            "verdicts_jsonl": "verdicts_jsonl_sha256",
        }
        for key, name in path_names.items():
            path = root / name
            value = artifact_values[key]
            if path.suffix == ".jsonl":
                payload = "".join(json.dumps(row) + "\n" for row in value)
            else:
                payload = json.dumps(value)
            path.write_text(payload, encoding="utf-8")
            artifact_paths[key] = str(path)
            artifact_hashes[hash_names[key]] = file_sha256(path)
    payload = {
        "report_type": VALIDATION_REPORT_TYPE,
        "validator_version": VALIDATOR_VERSION,
        "derivation_version": DERIVATION_VERSION,
        "validator_gate": "GO",
        "semantic_gate": "GO",
        "gate": "GO",
        "expected_scope_rows": 375,
        "expected_golden_rows": 18,
        "source_compare_digest": compare_digest,
        "source_changed_count": changed_count,
        "drift_union_count": changed_count,
        "unreviewed_adjusted_rows": 0,
        "true_semantic_regression_count": 0,
        "actionable_unfixed_count": 0,
        "validated_payload_digest": "b" * 64,
        "collateral_binding_digest": "c" * 64,
        "source_value_digests": source_value_digests,
        "source_artifact_paths": artifact_paths,
        "source_artifact_hashes": artifact_hashes,
        "mismatched_fields": [],
        "artifact_hash_mismatches": [],
        "independent_source_validation_issues": [],
        "validation_issues": [],
        "approval_boundary": {
            "validator_recomputed_from_source_artifacts": True,
            "validator_rebuilt_blind_packet_and_private_map": True,
        },
    }
    payload.update(overrides)
    return finalize_validation_receipt(payload)


def _real_full375_validation(
    artifact_dir: str,
    *,
    drift_count: int = 141,
    topology_profile: str = "interrupted_merge_75_300",
    return_primary_fixture: bool = False,
    require_golden_pass: bool = True,
):
    root = Path(artifact_dir)
    baseline = load_json_or_jsonl(PRODUCTION_BASELINE_RESULT_PATH)
    source = load_json_or_jsonl(PRODUCTION_PANEL_SOURCE_PATH)
    golden = json.loads(PRODUCTION_GOLDEN_MANIFEST_PATH.read_text(encoding="utf-8-sig"))
    runtime_anchor = json.loads(RUNTIME_TRUST_ANCHOR_PATH.read_text(encoding="utf-8-sig"))
    source_run_id = runtime_anchor["run_ids"]["source"]
    residual_run_id = runtime_anchor["run_ids"]["residual"]
    stable_row = runtime_anchor["stable_projection"]["row"]
    stable_manifest = runtime_anchor["stable_projection"]["manifest"]
    stable_plan = runtime_anchor["stable_projection"]["plan"]
    runtime_anchor_path = RUNTIME_TRUST_ANCHOR_PATH
    if topology_profile == "fresh375":
        fresh_run_id = "20260710_fresh375_unit"
        runtime_anchor = copy.deepcopy(runtime_anchor)
        runtime_anchor["topology"] = {
            "profile": "fresh375",
            "components": ["fresh"],
            "source_rows": 375,
            "fresh_rows": 375,
        }
        runtime_anchor["expected_counts"] = {
            "source_rows": 375,
            "fresh_rows": 375,
            "golden_rows": 18,
        }
        runtime_anchor["run_ids"] = {"fresh": None}
        runtime_anchor["stable_projection"] = {
            "plan": stable_plan,
            "expected_prompt_version": stable_row["prompt_version"],
            "source_panel_sha256": PRODUCTION_PANEL_SOURCE_SHA256,
            "source_post_id_order_sha256": canonical_digest(
                [str(row["post_id"]) for row in source]
            ),
            "runtime_code_tree_sha256": runtime_anchor["runtime_code_tree_sha256"],
        }
        runtime_anchor["stable_runtime_fingerprint_sha256"] = canonical_digest(
            runtime_anchor["stable_projection"]
        )
        runtime_anchor["release_fingerprint_sha256"] = runtime_anchor[
            "stable_runtime_fingerprint_sha256"
        ]
        runtime_anchor["binding_phase"] = "pre_run_release_anchor"
        runtime_anchor["prompt_version_binding"] = {
            "expected": stable_row["prompt_version"],
            "source": "explicit_pre_run_contract",
            "actual_run_start": None,
            "gate": "PENDING_RUN_START_RECEIPT",
        }
        runtime_anchor["configuration_hashes"] = {
            "plan_signature_sha256": canonical_digest(stable_plan),
            "release_fingerprint_sha256": runtime_anchor[
                "stable_runtime_fingerprint_sha256"
            ],
            "runtime_code_tree_sha256": runtime_anchor["runtime_code_tree_sha256"],
        }
        runtime_anchor["component_paths"] = {
            "fresh_plan": runtime_anchor["component_paths"]["source_plan"]
        }
        runtime_anchor["contract"]["parallel"].pop("effective", None)
        runtime_anchor["contract"]["search"].pop("healthy_ok", None)
        runtime_anchor["contract"]["search"].pop("failure_count", None)
        runtime_anchor["contract"]["vlm_ocr"].pop("semantic_review_ready", None)
        runtime_anchor.pop("immutable_components", None)
        runtime_anchor.pop("anchor_payload_sha256", None)
        runtime_anchor["anchor_payload_sha256"] = canonical_digest(runtime_anchor)
        runtime_anchor_path = root / "fresh375_runtime_trust_anchor.json"
        runtime_anchor_path.write_text(
            json.dumps(runtime_anchor, ensure_ascii=False),
            encoding="utf-8",
        )
        source_run_id = fresh_run_id
        residual_run_id = fresh_run_id
    elif topology_profile != "interrupted_merge_75_300":
        raise ValueError(f"unsupported test topology: {topology_profile}")
    golden_by_id = {str(row["post_id"]): row for row in golden["rows"]}
    baseline_by_id = {str(row["post_id"]): row for row in baseline}
    mandatory_golden_results = {}
    for pid, golden_row in golden_by_id.items():
        baseline_row = baseline_by_id[pid]
        expected_title = golden_row.get("expected_title_or_hypothesis")
        actual_title = analysis_identity(baseline_row).get("official_title")
        if (
            expected_title
            and actual_title
            and not expected_is_hypothesis(expected_title)
            and not expected_title_matches(expected_title, actual_title)
        ):
            repaired = _real_runtime_row(
                int(pid),
                str(expected_title),
                blocked_candidate=str(actual_title),
                url_override=golden_row.get("expected_url"),
            )
            mandatory_golden_results[pid] = repaired["analysis_result"]
    if drift_count < len(mandatory_golden_results):
        if require_golden_pass:
            raise AssertionError(
                "requested drift count is smaller than mandatory exact Golden repairs: "
                f"{drift_count} < {len(mandatory_golden_results)}"
            )
        active_mandatory_golden_results = {}
        optional_drift_budget = drift_count
    else:
        active_mandatory_golden_results = mandatory_golden_results
        optional_drift_budget = drift_count - len(mandatory_golden_results)
    after = []
    changed = 0
    optional_changed = 0
    for index, source_row in enumerate(source):
        pid = str(source_row["post_id"])
        baseline_row = baseline_by_id[pid]
        row = copy.deepcopy(source_row)
        row["analysis_result"] = copy.deepcopy(baseline_row.get("analysis_result") or {})
        row["run_meta"] = {
            **copy.deepcopy(stable_row),
            "config_hash": "unit-runtime-config-hash",
            "run_id": (
                source_run_id
                if topology_profile == "fresh375" or index < 75
                else residual_run_id
            ),
        }
        if pid in active_mandatory_golden_results:
            row["analysis_result"] = copy.deepcopy(
                active_mandatory_golden_results[pid]
            )
            changed += 1
        elif pid not in golden_by_id and optional_changed < optional_drift_budget:
            before_title = analysis_identity(baseline_row).get("official_title")
            golden_row = golden_by_id.get(pid)
            if golden_row and golden_row.get("expected_no_public_title") is True:
                target_title = None
            elif golden_row and golden_row.get("expected_title_or_hypothesis"):
                target_title = str(golden_row["expected_title_or_hypothesis"])
            else:
                target_title = None if before_title else f"Recovered {pid}"
            candidate = _real_runtime_row(
                int(pid),
                target_title,
                blocked_candidate=str(before_title or f"Candidate {pid}"),
                url_override=(golden_row or {}).get("expected_url"),
            )
            candidate["run_meta"] = row["run_meta"]
            single_golden = [golden_row] if golden_row else []
            if _real_compare_payload([baseline_row], [candidate], {"rows": single_golden})[
                "changed_post_count"
            ]:
                row["analysis_result"] = candidate["analysis_result"]
                changed += 1
                optional_changed += 1
        after.append(row)
    if changed != drift_count:
        raise AssertionError(f"could not construct requested drift count: {changed} != {drift_count}")
    compare = _real_compare_payload(baseline, after, golden)
    compare.update(
        {
            "historical_raw_collateral_regression_count": drift_count,
            "runtime_completed_count": 375,
            "runtime_flushed_count": 375,
            "runtime_pending_count": 0,
            "runtime_failed_count": 0,
        }
    )
    paths = {
        "collateral_compare": root / "collateral.json",
        "baseline_result": PRODUCTION_BASELINE_RESULT_PATH,
        "baseline_manifest": PRODUCTION_BASELINE_MANIFEST_PATH,
        "source_input": PRODUCTION_PANEL_SOURCE_PATH,
        "after_result": root / "after.json",
        "merged_manifest": root / "merged_manifest.json",
        "merged_checkpoint": root / "merged_checkpoint.jsonl",
        "merged_pending": root / "merged_pending.json",
        "merge_binding_receipt": root / "merge_binding_receipt.json",
        "runtime_trust_anchor": runtime_anchor_path,
        "golden_manifest": PRODUCTION_GOLDEN_MANIFEST_PATH,
        "golden_audit": root / "golden_audit.json",
        "raw_judge_receipt": root / "raw_judge_receipt.json",
        "blind_packet_jsonl": root / "packet.jsonl",
        "blind_map_json": root / "map.json",
        "verdicts_jsonl": root / "verdicts.jsonl",
        "adjudication_report": root / "adjudication.json",
    }
    if topology_profile == "interrupted_merge_75_300":
        paths["merge_integrity"] = root / "merge_integrity.json"
        paths["merge_integrity_md"] = root / "merge_integrity.md"
        paths["residual_component_manifest"] = (
            root / "residual_component_manifest.json"
        )

    def write_json(path: Path, value):
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def write_jsonl(path: Path, rows):
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )

    write_json(paths["after_result"], after)
    merged_checkpoint = [
        {
            "global_idx": index,
            "status": "completed",
            "post_id": row["post_id"],
            "result": row,
        }
        for index, row in enumerate(after, 1)
    ]
    write_jsonl(paths["merged_checkpoint"], merged_checkpoint)
    write_json(paths["merged_pending"], [])
    source_order = [str(row["post_id"]) for row in source]
    after_order = [str(row["post_id"]) for row in after]
    fingerprint = runtime_anchor["stable_runtime_fingerprint_sha256"]
    observed_runtime_fingerprint = canonical_digest(
        {"row": stable_row, "manifest": stable_manifest, "plan": stable_plan}
    )
    anchor_binding = {
        "gate": "GO",
        "path": str(paths["runtime_trust_anchor"].resolve()),
        "sha256": file_sha256(paths["runtime_trust_anchor"]),
        "anchor_version": RUNTIME_TRUST_ANCHOR_VERSION,
        "topology_profile": runtime_anchor["topology"]["profile"],
        "stable_runtime_fingerprint_sha256": fingerprint,
        "release_fingerprint_sha256": runtime_anchor[
            "release_fingerprint_sha256"
        ],
        "runtime_code_tree_sha256": runtime_anchor["runtime_code_tree_sha256"],
    }
    runtime_output_bindings = {
        "result": {
            "path": str(paths["after_result"].resolve()),
            "byte_sha256": file_sha256(paths["after_result"]),
            "canonical_sha256": canonical_digest(after),
            "size_bytes": paths["after_result"].stat().st_size,
            "row_count": len(after),
            "post_id_order_sha256": canonical_digest(after_order),
            "post_id_set_sha256": canonical_digest(sorted(after_order)),
        },
        "checkpoint": {
            "path": str(paths["merged_checkpoint"].resolve()),
            "byte_sha256": file_sha256(paths["merged_checkpoint"]),
            "canonical_sha256": canonical_digest(merged_checkpoint),
            "size_bytes": paths["merged_checkpoint"].stat().st_size,
            "row_count": len(merged_checkpoint),
        },
        "pending": {
            "path": str(paths["merged_pending"].resolve()),
            "byte_sha256": file_sha256(paths["merged_pending"]),
            "canonical_sha256": canonical_digest([]),
            "size_bytes": paths["merged_pending"].stat().st_size,
            "row_count": 0,
        },
    }
    residual_runtime_artifacts = {}
    if topology_profile == "interrupted_merge_75_300":
        residual_component_manifest = {
            **copy.deepcopy(stable_manifest),
            "run_id": residual_run_id,
        }
        write_json(
            paths["residual_component_manifest"],
            residual_component_manifest,
        )
        paths["residual_component_manifest"].chmod(stat.S_IREAD)
        residual_runtime_artifacts = {
            "manifest": {
                "path": str(paths["residual_component_manifest"].resolve()),
                "byte_sha256": file_sha256(paths["residual_component_manifest"]),
                "canonical_sha256": canonical_digest(residual_component_manifest),
                "size_bytes": paths["residual_component_manifest"].stat().st_size,
            }
        }
    merged_manifest = {
        **copy.deepcopy(stable_manifest),
        **(
            {"dashboard_mode": "composite_source_runs"}
            if topology_profile == "interrupted_merge_75_300"
            else {}
        ),
        "run_id": (
            "loop641_recovered75_plus_residual300_merged375"
            if topology_profile == "interrupted_merge_75_300"
            else source_run_id
        ),
        "gate": "GO",
        "output_file": str(paths["after_result"]),
        "checkpoint_jsonl": str(paths["merged_checkpoint"]),
        "pending_snapshot": str(paths["merged_pending"]),
        "input_post_count": 375,
        "completed_count": 375,
        "flushed_count": 375,
        "pending_count": 0,
        "failed_count": 0,
        "large_run_complete": True,
        "result_payload_sha256": canonical_digest(after),
        "input_post_id_order_sha256": canonical_digest(source_order),
        "input_post_id_set_sha256": canonical_digest(sorted(set(source_order))),
        "stable_runtime_fingerprint_sha256": (
            fingerprint
            if topology_profile == "interrupted_merge_75_300"
            else observed_runtime_fingerprint
        ),
        "premerge_trust_anchor": anchor_binding,
        "output_artifacts": runtime_output_bindings,
        "residual_runtime_artifacts": residual_runtime_artifacts,
        **(
            {
                "runtime_composition": {
                    "source_run_id": source_run_id,
                    "source_completed_rows": 75,
                    "residual_run_id": residual_run_id,
                    "residual_completed_rows": 300,
                    "merge_integrity_gate": "GO",
                }
            }
            if topology_profile == "interrupted_merge_75_300"
            else {}
        ),
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
    }
    write_json(paths["merged_manifest"], merged_manifest)
    merge_integrity = {
        "report_type": "interrupted_run_original_order_merge_integrity",
        "gate": "GO",
        "premerge_trust_anchor": anchor_binding,
        "counts": {
            "source_rows": 375,
            "source_unique_post_ids": 375,
            "recovered_rows": 75,
            "recovered_checkpoint_completed_rows": 75,
            "residual_rows": 300,
            "residual_checkpoint_completed_rows": 300,
            "residual_pending_rows": 0,
            "merged_rows": 375,
            "merged_checkpoint_rows": 375,
        },
        "post_id_integrity": {
            "overlap_post_ids": [],
            "missing_post_ids": [],
            "extra_post_ids": [],
            "duplicate_post_ids": [],
            "original_order_preserved": after_order == source_order,
        },
        "runtime_homogeneity": {
            "gate": "GO",
            "stable_runtime_fingerprint_sha256": fingerprint,
            "source_run_id": source_run_id,
            "residual_run_id": residual_run_id,
        },
        "recovery": {
            "integrity_classification": "recoverable_pending_flush_gap",
            "recovery_safe_to_use_as_completed_subset": True,
        },
        "artifacts": {
            "source_jsonl": str(paths["source_input"]),
            "source_jsonl_sha256": file_sha256(paths["source_input"]),
            "output_result": str(paths["after_result"]),
            "output_result_sha256": file_sha256(paths["after_result"]),
            "output_manifest": str(paths["merged_manifest"]),
            "output_manifest_sha256": file_sha256(paths["merged_manifest"]),
            "trust_anchor": str(paths["runtime_trust_anchor"].resolve()),
            "trust_anchor_sha256": file_sha256(paths["runtime_trust_anchor"]),
        },
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
    }
    if topology_profile == "interrupted_merge_75_300":
        write_json(paths["merge_integrity"], merge_integrity)
        paths["merge_integrity_md"].write_text("# synthetic merge integrity\n", encoding="utf-8")
        binding_receipt = finalize_merge_binding_receipt(
            {
                "generated_at": "2026-07-10T00:00:00+09:00",
                "gate": "GO",
                "preflight_paths": {
                    "result": str(paths["after_result"].resolve()),
                    "checkpoint": str(paths["merged_checkpoint"].resolve()),
                    "pending": str(paths["merged_pending"].resolve()),
                    "manifest": str(paths["merged_manifest"].resolve()),
                    "integrity_json": str(paths["merge_integrity"].resolve()),
                    "integrity_md": str(paths["merge_integrity_md"].resolve()),
                    "binding_receipt": str(paths["merge_binding_receipt"].resolve()),
                },
                "trust_anchor": anchor_binding,
                "residual_runtime_artifacts": residual_runtime_artifacts,
                "output_artifacts": runtime_output_bindings,
                "manifest": {
                    "path": str(paths["merged_manifest"].resolve()),
                    "byte_sha256": file_sha256(paths["merged_manifest"]),
                    "canonical_sha256": canonical_digest(merged_manifest),
                    "size_bytes": paths["merged_manifest"].stat().st_size,
                },
                "integrity": {
                    "path": str(paths["merge_integrity"].resolve()),
                    "byte_sha256": file_sha256(paths["merge_integrity"]),
                    "canonical_sha256": canonical_digest(merge_integrity),
                    "size_bytes": paths["merge_integrity"].stat().st_size,
                },
                "integrity_markdown": {
                    "path": str(paths["merge_integrity_md"].resolve()),
                    "byte_sha256": file_sha256(paths["merge_integrity_md"]),
                    "size_bytes": paths["merge_integrity_md"].stat().st_size,
                },
                "approval_boundary": {
                    "detached_receipt_is_binding_evidence_not_semantic_approval": True,
                    "production_full_scan_approval": False,
                },
            }
        )
    else:
        from tools.build_interrupted_merge_trust_anchor import (
            build_fresh375_run_start_binding_receipt,
        )

        partial_rows = after[:16]
        partial_result_path = root / "fresh375_start_partial.json"
        partial_manifest_path = root / "fresh375_start_manifest_snapshot.json"
        write_json(partial_result_path, partial_rows)
        partial_manifest = {
            **copy.deepcopy(stable_manifest),
            "run_id": source_run_id,
            "output_file": str(partial_result_path.resolve()),
            "input_post_count": 375,
            "completed_count": 16,
            "flushed_count": 16,
            "pending_count": 0,
            "failed_count": 0,
            "large_run_complete": False,
            "llm_model": runtime_anchor["contract"]["model"],
            "llm_endpoint": runtime_anchor["contract"]["endpoint"],
        }
        write_json(partial_manifest_path, partial_manifest)
        partial_result_path.chmod(stat.S_IREAD)
        partial_manifest_path.chmod(stat.S_IREAD)
        runtime_anchor_path.chmod(stat.S_IREAD)
        binding_receipt = build_fresh375_run_start_binding_receipt(
            pre_run_anchor=runtime_anchor,
            pre_run_anchor_path=runtime_anchor_path,
            expected_anchor_sha256=file_sha256(runtime_anchor_path),
            run_manifest=partial_manifest,
            run_manifest_path=partial_manifest_path,
            partial_rows=partial_rows,
            partial_result_path=partial_result_path,
            source_rows=source,
            source_jsonl=PRODUCTION_PANEL_SOURCE_PATH,
            runtime_root=Path(__file__).resolve().parents[1],
            allow_untrusted_test_roots=True,
        )
    write_json(paths["merge_binding_receipt"], binding_receipt)
    immutable_runtime_paths = [
        paths["after_result"],
        paths["merged_checkpoint"],
        paths["merged_pending"],
        paths["merged_manifest"],
        paths["merge_binding_receipt"],
    ]
    if topology_profile == "interrupted_merge_75_300":
        immutable_runtime_paths.extend(
            [paths["merge_integrity"], paths["merge_integrity_md"]]
        )
    for immutable_runtime_path in immutable_runtime_paths:
        immutable_runtime_path.chmod(stat.S_IREAD)
    golden_audit = build_golden_audit(
        canary_rows=after,
        golden_rows=golden["rows"],
        run_manifest=merged_manifest,
        canary_result=paths["after_result"].resolve(),
        canary_manifest=paths["merged_manifest"].resolve(),
        golden_manifest=paths["golden_manifest"].resolve(),
    )
    if require_golden_pass and golden_audit["gate"] != "PASS":
        raise AssertionError(f"synthetic full375 golden fixture invalid: {golden_audit['status_counts']}")
    write_json(paths["golden_audit"], golden_audit)
    thread_id = "11111111-1111-4111-8111-111111111111"
    trust_bundle = {
        "artifact_paths": {
            key: paths[key]
            for key in (
                "baseline_result",
                "baseline_manifest",
                "source_input",
                "after_result",
                "merged_manifest",
                "merged_checkpoint",
                "merged_pending",
                "merge_binding_receipt",
                "runtime_trust_anchor",
                "golden_manifest",
                "golden_audit",
                "raw_judge_receipt",
                "blind_packet_jsonl",
                "verdicts_jsonl",
                *(
                    ("merge_integrity",)
                    if topology_profile == "interrupted_merge_75_300"
                    else ()
                ),
            )
        },
        "anchors": {
            "baseline_manifest_sha256": PRODUCTION_BASELINE_MANIFEST_SHA256,
            "panel_source_sha256": PRODUCTION_PANEL_SOURCE_SHA256,
            "golden_manifest_sha256": PRODUCTION_GOLDEN_MANIFEST_SHA256,
        },
    }
    packets, mapping = build_blind_packet(
        compare=compare,
        baseline_rows=baseline,
        source_rows=source,
        after_rows=after,
        golden_manifest=golden,
        packet_id="always-on-real-validator",
        expected_scope_rows=375,
        expected_golden_rows=18,
        trust_bundle=trust_bundle,
    )
    map_by_id = {row["drift_id"]: row for row in mapping["rows"]}
    drift_by_post = {str(row["post_id"]): row for row in compare["rows"]}
    source_by_post = {str(row["post_id"]): row for row in source}
    after_by_post = {str(row["post_id"]): row for row in after}
    verdicts = [
        _real_verdict_for(
            packet,
            map_by_id[packet["drift_id"]],
            source_by_post[str(packet["post_id"])],
            after_by_post[str(packet["post_id"])],
            drift_by_post[str(packet["post_id"])],
            preferred_origin="after",
        )
        for packet in packets
    ]
    write_json(paths["collateral_compare"], compare)
    write_jsonl(paths["blind_packet_jsonl"], packets)
    write_json(paths["blind_map_json"], mapping)

    judge_paths = {
        "prompt": root / "judge.prompt.txt",
        "schema": root / "judge.schema.json",
        "raw_events": root / "judge.raw_events.jsonl",
        "final_response": root / "judge.final_response.json",
        "stderr": root / "judge.stderr.txt",
        "session_bundle": root / "judge.session_bundle.zip",
        "receipt": paths["raw_judge_receipt"],
        "verdicts": paths["verdicts_jsonl"],
    }
    judge_paths["prompt"].write_bytes(build_prompt(packets))
    write_json(judge_paths["schema"], build_output_schema(len(packets)))
    prompt_sha256 = file_sha256(judge_paths["prompt"])
    packet_by_drift_id = {packet["drift_id"]: packet for packet in packets}
    for verdict in verdicts:
        allowed_evidence_refs = enumerate_allowed_evidence_refs(
            packet_by_drift_id[verdict["drift_id"]]
        )
        verdict["evidence_refs"] = [
            next(ref for ref in allowed_evidence_refs if ref.startswith("source.")),
            next(
                ref
                for ref in allowed_evidence_refs
                if ref.startswith("candidate_options[")
            ),
        ]
        verdict["blind_verdict"]["prompt_sha256"] = prompt_sha256
        verdict["blind_verdict"]["receipt_sha256"] = blind_receipt_digest(
            verdict["blind_verdict"]
        )
    write_jsonl(paths["verdicts_jsonl"], verdicts)
    raw_model_rows = [
        {
            "drift_id": verdict["drift_id"],
            "packet_row_sha256": verdict["packet_row_sha256"],
            "preferred_option": verdict["blind_verdict"]["preferred_option"],
            "same_work": verdict["blind_verdict"]["same_work"],
            "relation_to_post": verdict["blind_verdict"]["relation_to_post"],
            "review_label": verdict["review_label"],
            "evidence_grade": verdict["evidence_grade"],
            "row_rationale": verdict["row_rationale"],
            "evidence_refs": verdict["evidence_refs"],
        }
        for verdict in verdicts
    ]
    final_payload = {"verdicts": raw_model_rows}
    validated_model_rows, model_issues = _validate_model_response(final_payload, packets)
    if model_issues or validated_model_rows != raw_model_rows:
        raise AssertionError(f"synthetic raw model receipt invalid: {model_issues}")
    write_json(judge_paths["final_response"], final_payload)
    judge_paths["stderr"].write_bytes(b"")
    raw_events = [
        {"type": "thread.started", "thread_id": thread_id},
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "text": json.dumps(final_payload, ensure_ascii=False),
            },
        },
        {"type": "turn.completed"},
    ]
    write_jsonl(judge_paths["raw_events"], raw_events)
    cli_trust = validate_trust_anchor(CODEX_CLI_TRUST_ANCHOR_PATH, production=True)
    runner_path = (
        Path(__file__).resolve().parents[1] / "tools/run_codex_blind_adjudication.py"
    ).resolve()
    runner_sha256 = file_sha256(runner_path)
    primary_dependency_snapshot = capture_security_dependency_snapshot(
        RUNNER_SECURITY_DEPENDENCY_PATHS
    )
    primary_security_dependency_manifest = build_security_dependency_manifest(
        primary_dependency_snapshot,
        primary_dependency_snapshot,
    )
    isolated_root = root / "judge-runtime"
    isolated_home = isolated_root / "isolated-home"
    isolated_codex_home = isolated_home / ".codex"
    isolated_judge_cwd = isolated_root / "judge-cwd"
    isolated_session = isolated_codex_home / "sessions/2026/07/10/thread.jsonl"
    isolated_session.parent.mkdir(parents=True)
    isolated_judge_cwd.mkdir(parents=True)
    isolated_session.write_text(
        json.dumps({"thread_id": thread_id, "kind": "synthetic-session"}),
        encoding="utf-8",
    )
    session_bundle = {
        **_build_session_bundle_stage(
            isolated_codex_home,
            thread_id,
            judge_paths["session_bundle"],
        ),
        "path": str(judge_paths["session_bundle"].resolve()),
    }
    primary_command = [
        cli_trust["codex_cli"]["executable_path"],
        "exec",
        "-m",
        "gpt-5.6-sol",
        "-c",
        'model_reasoning_effort="high"',
        "--json",
        "--output-schema",
        str(judge_paths["schema"]),
        "-o",
        str(isolated_root / "final-response.json"),
        "--sandbox",
        "read-only",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "-C",
        str(isolated_judge_cwd),
        "-",
    ]
    raw_judge_receipt = {
        "report_type": RAW_JUDGE_REPORT_TYPE,
        "receipt_version": RAW_JUDGE_VERSION,
        "runner_version": RUNNER_VERSION,
        "gate": "GO" if packets else "NOT_REQUIRED",
        "status": "SUCCEEDED" if packets else "NOT_REQUIRED_ZERO_DRIFT",
        "execution_mode": "subprocess_production",
        "cryptographic_service_attestation": False,
        "trust_boundary": "signed_native_codex_cli_plus_required_live_thread_resume",
        "thread_readback_required": True,
        "provider": "codex",
        "model": "gpt-5.6-sol",
        "reasoning_effort": PRODUCTION_REASONING_EFFORT,
        "reviewer_id": "codex-gpt-5.6-sol-blind-judge",
        "runner_run_id": "11111111-1111-4111-8111-222222222222",
        "codex_thread_id": thread_id,
        "goal_id": PRODUCTION_GOAL_ID,
        "continuation_source_session": CONTINUATION_SOURCE_SESSION,
        "judge_run_id": "judge-run-unit",
        "started_at": "2026-07-10T00:00:00+00:00",
        "finished_at": "2026-07-10T00:01:00+00:00",
        "cli_version": cli_trust["codex_cli"]["cli_version"],
        "exit_code": 0,
        "timed_out": False,
        "execution_error": None,
        "command": primary_command,
        "execution_process": {
            "process_id": 9002,
            "parent_process_id": 9001,
            "process_image_path": cli_trust["codex_cli"]["executable_path"],
            "command_sha256": canonical_digest(primary_command),
        },
        "launcher_process": {
            "execution_boundary": "isolated_python_cli_child",
            "pid": 9001,
            "parent_pid": 8999,
            "process_image_path": str(Path(sys.executable).resolve()),
            "process_image_sha256": file_sha256(Path(sys.executable).resolve()),
            "process_image_size": Path(sys.executable).stat().st_size,
            "runner_path": str(runner_path),
            "runner_sha256": runner_sha256,
            "isolated_python": True,
            "argv_sha256": "c" * 64,
            "launcher_challenge_sha256": "d" * 64,
            "imported_production_entrypoint": False,
            "cryptographic_local_process_attestation": False,
        },
        "codex_cli_trust": cli_trust,
        "runner_artifact": {
            "path": str(runner_path),
            "size": runner_path.stat().st_size,
            "sha256_before": runner_sha256,
            "sha256_after": runner_sha256,
            "stable_during_execution": True,
        },
        "security_dependency_manifest": primary_security_dependency_manifest,
        "environment_isolation": {
            "codex_home": str(isolated_codex_home),
            "home": str(isolated_home),
            "inherited_environment_keys": [
                "APPDATA",
                "CODEX_HOME",
                "COMSPEC",
                "HOME",
                "LOCALAPPDATA",
                "SystemRoot",
                "TEMP",
                "TMP",
                "USERPROFILE",
                "WINDIR",
            ],
            "path_inherited": False,
            "global_codex_config_inherited": False,
            "global_agents_inherited": False,
            "authentication_source": "isolated_auth_json_copy",
            "judge_cwd": str(isolated_judge_cwd),
            "relation_contract": {
                "judge_cwd_parent_equals_isolated_home_parent": True,
                "codex_home_parent_equals_isolated_home": True,
            },
            "direct_service_policy": {
                "custom_endpoint_inherited": False,
                "proxy_inherited": False,
                "custom_ca_inherited": False,
                "python_environment_inherited": False,
                "auth_json_network_override_inherited": False,
                "auth_json_schema_allowlist_valid": True,
                "forbidden_environment_keys": [
                    "OPENAI_BASE_URL",
                    "HTTP_PROXY",
                    "HTTPS_PROXY",
                    "ALL_PROXY",
                    "NO_PROXY",
                    "SSL_CERT_FILE",
                    "SSL_CERT_DIR",
                    "PYTHONHOME",
                    "PYTHONPATH",
                    "PYTHONSTARTUP",
                ],
            },
        },
        "prompt_sha256": prompt_sha256,
        "schema_sha256": file_sha256(judge_paths["schema"]),
        "packet_jsonl_path": str(paths["blind_packet_jsonl"].resolve()),
        "packet_jsonl_sha256": file_sha256(paths["blind_packet_jsonl"]),
        "packet_rows_sha256": canonical_digest(packets),
        "packet_id": packets[0]["packet_id"] if packets else None,
        "packet_row_count": len(packets),
        "packet_row_sha256_by_drift_id": {
            packet["drift_id"]: packet["packet_row_sha256"] for packet in packets
        },
        "raw_events_jsonl_path": str(judge_paths["raw_events"].resolve()),
        "raw_events_jsonl_sha256": file_sha256(judge_paths["raw_events"]),
        "raw_event_count": len(raw_events),
        "final_response_path": str(judge_paths["final_response"].resolve()),
        "final_response_sha256": file_sha256(judge_paths["final_response"]),
        "final_response_payload_sha256": canonical_digest(final_payload),
        "raw_event_final_payload_sha256": canonical_digest(final_payload),
        "raw_model_verdict_rows": raw_model_rows,
        "raw_model_verdict_rows_sha256": canonical_digest(raw_model_rows),
        "delivered_verdicts_jsonl_path": str(paths["verdicts_jsonl"].resolve()),
        "delivered_verdicts_jsonl_sha256": file_sha256(paths["verdicts_jsonl"]),
        "delivered_verdict_rows_sha256": canonical_digest(verdicts),
        "delivered_verdict_row_sha256_by_drift_id": {
            verdict["drift_id"]: canonical_digest(verdict) for verdict in verdicts
        },
        "row_count": len(verdicts),
        "rows": [
            {
                "drift_id": verdict["drift_id"],
                "post_id": verdict["post_id"],
                "packet_row_sha256": verdict["packet_row_sha256"],
                "raw_model_verdict": raw_model_rows[index],
                "raw_model_verdict_row_sha256": canonical_digest(raw_model_rows[index]),
                "raw_verdict_row_sha256": canonical_digest(verdict),
                "delivered_verdict_row_sha256": canonical_digest(verdict),
                "raw_verdict": verdict,
            }
            for index, verdict in enumerate(verdicts)
        ],
        "session_bundle": session_bundle,
        "stderr": {
            "raw_sha256": canonical_digest(b"".decode()),
            "raw_byte_count": 0,
            "raw_content_retained": False,
            "retained_redacted_path": str(judge_paths["stderr"].resolve()),
            "retained_redacted_sha256": file_sha256(judge_paths["stderr"]),
            "retained_byte_count": 0,
            "truncated": False,
        },
        "artifacts": {key: str(path.resolve()) for key, path in judge_paths.items()},
        "validation_issues": [],
        "artifact_write_contract": {
            "exclusive_create_no_overwrite": True,
            "read_only_after_create": True,
            "output_prefix_confined_to_repo_out_review": True,
            "retry_requires_new_output_prefix": True,
            "verdict_is_final_commit_marker": True,
        },
        "receipt_digest_contract": RECEIPT_DIGEST_CONTRACT,
    }
    raw_judge_receipt["receipt_payload_sha256"] = canonical_digest(
        raw_judge_receipt
    )
    write_json(paths["raw_judge_receipt"], raw_judge_receipt)
    for immutable_path in (
        paths["blind_packet_jsonl"],
        *judge_paths.values(),
    ):
        immutable_path.chmod(stat.S_IREAD)
    if return_primary_fixture:
        if not packets:
            raise AssertionError("primary preflight fixture requires nonzero drift")
        return {
            "raw_judge_receipt": paths["raw_judge_receipt"],
            "codex_cli_trust_anchor": CODEX_CLI_TRUST_ANCHOR_PATH,
            "raw_events": judge_paths["raw_events"],
            "receipt": raw_judge_receipt,
            "packet_rows": packets,
            "verdict_rows": verdicts,
        }
    if packets:
        paths["thread_readback_receipt"] = root / "readback.receipt.json"
        readback_paths = {
            "prompt": root / "readback.prompt.txt",
            "schema": root / "readback.schema.json",
            "raw_events": root / "readback.raw_events.jsonl",
            "final_response": root / "readback.final_response.json",
            "stderr": root / "readback.stderr.txt",
            "receipt": paths["thread_readback_receipt"],
        }
        challenge = "synthetic-live-thread-resume-challenge-0123456789"
        expected_echo = {
            "thread_id": thread_id,
            "challenge": challenge,
            "primary_receipt_sha256": file_sha256(paths["raw_judge_receipt"]),
            "primary_raw_events_sha256": raw_judge_receipt[
                "raw_events_jsonl_sha256"
            ],
            "primary_final_response_sha256": raw_judge_receipt[
                "final_response_sha256"
            ],
            "primary_verdicts_sha256": raw_judge_receipt[
                "delivered_verdicts_jsonl_sha256"
            ],
        }
        readback_paths["prompt"].write_bytes(build_readback_prompt(expected_echo))
        write_json(readback_paths["schema"], build_readback_schema())
        write_json(readback_paths["final_response"], expected_echo)
        readback_events = [
            {"type": "thread.started", "thread_id": thread_id},
            {"type": "turn.started"},
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": json.dumps(expected_echo, ensure_ascii=False),
                },
            },
            {"type": "turn.completed"},
        ]
        write_jsonl(readback_paths["raw_events"], readback_events)
        readback_paths["stderr"].write_bytes(b"")
        verifier_path = (
            Path(__file__).resolve().parents[1]
            / "tools/verify_codex_blind_judge_thread.py"
        ).resolve()
        verifier_sha256 = file_sha256(verifier_path)
        readback_dependency_snapshot = capture_security_dependency_snapshot(
            VERIFIER_SECURITY_DEPENDENCY_PATHS
        )
        readback_security_dependency_manifest = build_security_dependency_manifest(
            readback_dependency_snapshot,
            readback_dependency_snapshot,
        )
        readback_cwd = root / "readback-runtime/readback-cwd"
        readback_home = root / "readback-runtime/home"
        readback_codex_home = readback_home / ".codex"
        readback_command = [
            cli_trust["codex_cli"]["executable_path"],
            "exec",
            "--sandbox",
            "read-only",
            "resume",
            "-c",
            'model_reasoning_effort="high"',
            "-m",
            "gpt-5.6-sol",
            "--json",
            "--output-schema",
            str(readback_paths["schema"]),
            "-o",
            str(readback_cwd.parent / "final.json"),
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            thread_id,
            "-",
        ]
        primary_binding = {
            "primary_receipt_path": str(paths["raw_judge_receipt"].resolve()),
            "primary_receipt_sha256": file_sha256(paths["raw_judge_receipt"]),
            "thread_id": thread_id,
            "primary_judge_run_id": raw_judge_receipt["judge_run_id"],
            "primary_runner_run_id": raw_judge_receipt["runner_run_id"],
            "primary_process_id": raw_judge_receipt["execution_process"][
                "process_id"
            ],
            "primary_parent_process_id": raw_judge_receipt["execution_process"][
                "parent_process_id"
            ],
            "primary_launcher_process_id": raw_judge_receipt["launcher_process"][
                "pid"
            ],
            "primary_raw_events_sha256": raw_judge_receipt[
                "raw_events_jsonl_sha256"
            ],
            "primary_final_response_sha256": raw_judge_receipt[
                "final_response_sha256"
            ],
            "primary_verdicts_sha256": raw_judge_receipt[
                "delivered_verdicts_jsonl_sha256"
            ],
            "session_bundle_path": session_bundle["path"],
            "session_bundle_sha256": session_bundle["bundle_sha256"],
            "session_files_sha256": session_bundle["files_sha256"],
        }
        readback_receipt = {
            "report_type": READBACK_REPORT_TYPE,
            "receipt_version": READBACK_RECEIPT_VERSION,
            "verifier_version": READBACK_VERIFIER_VERSION,
            "gate": "GO",
            "status": "SUCCEEDED",
            "execution_mode": "subprocess_production",
            "provider": "codex",
            "model": "gpt-5.6-sol",
            "reasoning_effort": "high",
            "goal_id": PRODUCTION_GOAL_ID,
            "continuation_source_session": CONTINUATION_SOURCE_SESSION,
            "codex_thread_id": thread_id,
            "readback_run_id": "codex-thread-readback-unit",
            "started_at": "2026-07-10T00:02:00+00:00",
            "finished_at": "2026-07-10T00:03:00+00:00",
            "exit_code": 0,
            "timed_out": False,
            "execution_error": None,
            "challenge": challenge,
            "challenge_sha256": hashlib.sha256(challenge.encode()).hexdigest(),
            "primary_binding": primary_binding,
            "codex_cli_trust": cli_trust,
            "launcher_process": {
                "execution_boundary": "isolated_python_cli_child",
                "pid": 9101,
                "parent_pid": 9099,
                "process_image_path": str(Path(sys.executable).resolve()),
                "process_image_sha256": file_sha256(Path(sys.executable).resolve()),
                "process_image_size": Path(sys.executable).stat().st_size,
                "verifier_path": str(verifier_path),
                "verifier_sha256": verifier_sha256,
                "isolated_python": True,
                "argv_sha256": "e" * 64,
                "launcher_challenge_sha256": "f" * 64,
                "cryptographic_local_process_attestation": False,
            },
            "execution_process": {
                "process_id": 9102,
                "parent_process_id": 9101,
                "process_image_path": cli_trust["codex_cli"]["executable_path"],
                "command_sha256": canonical_digest(readback_command),
            },
            "verifier_artifact": {
                "path": str(verifier_path),
                "size": verifier_path.stat().st_size,
                "sha256_before": verifier_sha256,
                "sha256_after": verifier_sha256,
                "stable_during_execution": True,
            },
            "runner_dependency_artifact": {
                "path": str(runner_path),
                "size": runner_path.stat().st_size,
                "sha256_before": runner_sha256,
                "sha256_after": runner_sha256,
                "stable_during_execution": True,
            },
            "security_dependency_manifest": readback_security_dependency_manifest,
            "environment_isolation": {
                "codex_home": str(readback_codex_home),
                "home": str(readback_home),
                "judge_cwd": str(readback_cwd),
                "inherited_environment_keys": [
                    "APPDATA",
                    "CODEX_HOME",
                    "COMSPEC",
                    "HOME",
                    "LOCALAPPDATA",
                    "SystemRoot",
                    "TEMP",
                    "TMP",
                    "USERPROFILE",
                    "WINDIR",
                ],
                "path_inherited": False,
                "global_codex_config_inherited": False,
                "global_agents_inherited": False,
                "authentication_source": "isolated_auth_json_copy",
                "relation_contract": {
                    "judge_cwd_parent_equals_isolated_home_parent": True,
                    "codex_home_parent_equals_isolated_home": True,
                },
                "direct_service_policy": {
                    "custom_endpoint_inherited": False,
                    "proxy_inherited": False,
                    "custom_ca_inherited": False,
                    "python_environment_inherited": False,
                    "auth_json_network_override_inherited": False,
                    "auth_json_schema_allowlist_valid": True,
                    "forbidden_environment_keys": [
                        "OPENAI_BASE_URL",
                        "HTTP_PROXY",
                        "HTTPS_PROXY",
                        "ALL_PROXY",
                        "NO_PROXY",
                        "SSL_CERT_FILE",
                        "SSL_CERT_DIR",
                        "PYTHONHOME",
                        "PYTHONPATH",
                        "PYTHONSTARTUP",
                    ],
                },
            },
            "session_restore": {
                "restored_file_count": session_bundle["file_count"],
                "restored_files_sha256": session_bundle["files_sha256"],
                "secrets_restored": False,
            },
            "command": readback_command,
            "prompt_sha256": file_sha256(readback_paths["prompt"]),
            "schema_sha256": file_sha256(readback_paths["schema"]),
            "raw_events_jsonl_sha256": file_sha256(
                readback_paths["raw_events"]
            ),
            "raw_events_byte_count": readback_paths["raw_events"].stat().st_size,
            "raw_event_count": len(readback_events),
            "final_response_sha256": file_sha256(
                readback_paths["final_response"]
            ),
            "final_response_byte_count": readback_paths[
                "final_response"
            ].stat().st_size,
            "final_response_payload_sha256": canonical_digest(expected_echo),
            "artifacts": {
                key: str(path.resolve()) for key, path in readback_paths.items()
            },
            "stderr": {
                "raw_sha256": file_sha256(readback_paths["stderr"]),
                "raw_byte_count": 0,
                "retained_redacted_sha256": file_sha256(
                    readback_paths["stderr"]
                ),
                "truncated": False,
            },
            "validation_issues": [],
            "artifact_write_contract": {
                "exclusive_create_no_overwrite": True,
                "read_only_after_create": True,
                "output_prefix_confined_to_repo_out_review": True,
            },
            "receipt_digest_contract": RECEIPT_DIGEST_CONTRACT,
            "cryptographic_service_attestation": False,
            "trust_boundary": READBACK_TRUST_BOUNDARY,
        }
        readback_receipt["receipt_payload_sha256"] = canonical_digest(
            readback_receipt
        )
        write_json(paths["thread_readback_receipt"], readback_receipt)
        for readback_artifact in readback_paths.values():
            readback_artifact.chmod(stat.S_IREAD)
        trust_bundle["artifact_paths"]["thread_readback_receipt"] = paths[
            "thread_readback_receipt"
        ]
    report = build_adjudication(
        compare=compare,
        verdict_rows=verdicts,
        baseline_rows=baseline,
        source_rows=source,
        after_rows=after,
        golden_manifest=golden,
        blind_packet_rows=packets,
        blind_map=mapping,
        expected_scope_rows=375,
        expected_golden_rows=18,
        trust_bundle=trust_bundle,
    )
    hash_fields = {
        "collateral_compare": "collateral_compare_sha256",
        "baseline_result": "baseline_result_sha256",
        "baseline_manifest": "baseline_manifest_sha256",
        "source_input": "source_input_sha256",
        "after_result": "after_result_sha256",
        "merged_manifest": "merged_manifest_sha256",
        "merged_checkpoint": "merged_checkpoint_sha256",
        "merged_pending": "merged_pending_sha256",
        "merge_binding_receipt": "merge_binding_receipt_sha256",
        "runtime_trust_anchor": "runtime_trust_anchor_sha256",
        "golden_manifest": "golden_manifest_sha256",
        "golden_audit": "golden_audit_sha256",
        "raw_judge_receipt": "raw_judge_receipt_sha256",
        "blind_packet_jsonl": "blind_packet_jsonl_sha256",
        "blind_map_json": "blind_map_json_sha256",
        "verdicts_jsonl": "verdicts_jsonl_sha256",
    }
    if topology_profile == "interrupted_merge_75_300":
        hash_fields["merge_integrity"] = "merge_integrity_sha256"
    if packets:
        hash_fields["thread_readback_receipt"] = (
            "thread_readback_receipt_sha256"
        )
    artifact_hashes = {
        hash_field: file_sha256(paths[path_field])
        for path_field, hash_field in hash_fields.items()
    }
    report["artifacts"] = {
        **{key: str(paths[key]) for key in hash_fields},
        **artifact_hashes,
    }
    write_json(paths["adjudication_report"], report)
    validation = validate_adjudication(
        report=report,
        compare=compare,
        verdict_rows=verdicts,
        baseline_rows=baseline,
        source_rows=source,
        after_rows=after,
        golden_manifest=golden,
        blind_packet_rows=packets,
        blind_map=mapping,
        expected_scope_rows=375,
        expected_golden_rows=18,
        trust_bundle=trust_bundle,
        artifact_hashes=artifact_hashes,
        adjudication_report_path=paths["adjudication_report"],
    )
    return compare, golden_audit, validation


def _contract_accounting(**overrides):
    payload = {
        "accounting_id": "unit_contract_accounting",
        "gate": "REVIEW-LOCKED",
        "summary": {
            "validation_issue_count": 0,
            "contract_processed_rows": 2,
            "source_native_processed_rows": 0,
            "processed_or_excluded_rows": 2,
            "ordinary_residual_unprocessed_rows": 0,
            "contract_accounting_state_counts": {
                "contract_processed_native_web_disambiguation_hold_no_publish": 2
            },
        },
        "rows": [
            {
                "post_id": 2,
                "contract_processed": True,
                "source_native_processed": False,
                "ordinary_residual_unprocessed": False,
            },
            {
                "post_id": 3,
                "contract_processed": True,
                "source_native_processed": False,
                "ordinary_residual_unprocessed": False,
            },
        ],
    }
    payload.update(overrides)
    return payload


class AlwaysOnRegressionGatesTest(unittest.TestCase):
    @classmethod
    def _start_historical_tree_patch(cls):
        # These integration fixtures intentionally replay the immutable
        # historical Loop641 anchor while the working tree evolves.  Validate
        # the frozen tree record itself here; live-checkout drift rejection is
        # covered by the dedicated runtime-anchor tests.
        def frozen_tree_digest(anchor):
            code_tree = anchor.get("runtime_code_tree") or {}
            files = code_tree.get("files") or []
            digest = canonical_digest(files)
            if (
                code_tree.get("file_count") != len(files)
                or code_tree.get("tree_sha256") != digest
            ):
                raise ValueError("runtime trust anchor code tree digest mismatch")
            return digest

        cls._runtime_tree_patcher = patch(
            "tools.build_adjusted_collateral_blind_packet._runtime_code_tree_digest",
            side_effect=frozen_tree_digest,
        )
        cls._runtime_tree_patcher.start()
        cls.addClassCleanup(cls._runtime_tree_patcher.stop)

    @classmethod
    def _assert_production_canonicals_unchanged(cls):
        for path, expected in PRODUCTION_CANONICAL_HASHES.items():
            actual = file_sha256(path)
            if actual != expected:
                raise AssertionError(f"production canonical changed: {path}: {actual} != {expected}")

    @classmethod
    def setUpClass(cls):
        cls._assert_production_canonicals_unchanged()
        cls._start_historical_tree_patch()

    @classmethod
    def tearDownClass(cls):
        cls._assert_production_canonicals_unchanged()

    def test_primary_and_readback_exact_argv_reject_all_override_attacks(self):
        trusted_executable = str(Path(r"C:\Program Files\Codex\codex.exe"))
        primary_schema = Path(r"C:\review\primary\schema.json")
        primary_final = Path(r"C:\review\primary\final-response.json")
        primary_cwd = Path(r"C:\review\primary\judge-cwd")
        primary_command = [
            trusted_executable,
            "exec",
            "-m",
            "gpt-5.6-sol",
            "-c",
            'model_reasoning_effort="high"',
            "--json",
            "--output-schema",
            str(primary_schema),
            "-o",
            str(primary_final),
            "--sandbox",
            "read-only",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "-C",
            str(primary_cwd),
            "-",
        ]
        readback_schema = Path(r"C:\review\readback\schema.json")
        readback_cwd = Path(r"C:\review\readback\judge-cwd")
        readback_final = readback_cwd.parent / "final.json"
        thread_id = "019f0387-24d0-7313-a6c0-66d09f04bb33"
        readback_command = [
            trusted_executable,
            "exec",
            "--sandbox",
            "read-only",
            "resume",
            "-c",
            'model_reasoning_effort="high"',
            "-m",
            "gpt-5.6-sol",
            "--json",
            "--output-schema",
            str(readback_schema),
            "-o",
            str(readback_final),
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            thread_id,
            "-",
        ]
        _validate_primary_command_vector(
            primary_command,
            trusted_executable=trusted_executable,
            schema_path=primary_schema,
        )
        _validate_readback_command_vector(
            readback_command,
            trusted_executable=trusted_executable,
            schema_path=readback_schema,
            thread_id=thread_id,
            readback_cwd=readback_cwd,
        )

        attacks = {
            "provider": ["--provider", "untrusted"],
            "base_url": ["--base-url", "https://untrusted.invalid/v1"],
            "proxy": ["--proxy", "http://127.0.0.1:4444"],
            "custom_ca": ["--ca-file", r"C:\untrusted\ca.pem"],
            "additional_config": ["-c", 'model_provider="untrusted"'],
            "extra_token": ["--unexpected"],
        }
        for vector_name, command, override_pair_index, override_token_index, validator, kwargs in (
            (
                "primary",
                primary_command,
                2,
                6,
                _validate_primary_command_vector,
                {
                    "trusted_executable": trusted_executable,
                    "schema_path": primary_schema,
                },
            ),
            (
                "readback",
                readback_command,
                7,
                9,
                _validate_readback_command_vector,
                {
                    "trusted_executable": trusted_executable,
                    "schema_path": readback_schema,
                    "thread_id": thread_id,
                    "readback_cwd": readback_cwd,
                },
            ),
        ):
            for attack_name, extra_argv in attacks.items():
                attacked = list(command)
                if len(extra_argv) == 2:
                    attacked[override_pair_index : override_pair_index + 2] = extra_argv
                else:
                    attacked[override_token_index] = extra_argv[0]
                with self.subTest(vector=vector_name, attack=attack_name):
                    with self.assertRaisesRegex(ValueError, "exact reviewed vector"):
                        validator(attacked, **kwargs)

    def test_primary_preflight_rejects_forged_command_process_and_raw_state(self):
        with tempfile.TemporaryDirectory(dir=PRODUCTION_REVIEW_DIR) as artifact_dir:
            fixture = _real_full375_validation(
                artifact_dir,
                drift_count=1,
                return_primary_fixture=True,
            )
            receipt_path = fixture["raw_judge_receipt"]
            anchor_path = fixture["codex_cli_trust_anchor"]
            raw_events_path = fixture["raw_events"]
            original_receipt_bytes = receipt_path.read_bytes()
            original_raw_events_bytes = raw_events_path.read_bytes()

            def restore_fixture() -> None:
                for path, content in (
                    (receipt_path, original_receipt_bytes),
                    (raw_events_path, original_raw_events_bytes),
                ):
                    path.chmod(stat.S_IREAD | stat.S_IWRITE)
                    path.write_bytes(content)
                    path.chmod(stat.S_IREAD)

            def write_receipt(payload: dict) -> None:
                payload.pop("receipt_payload_sha256", None)
                payload["receipt_payload_sha256"] = canonical_digest(payload)
                receipt_path.chmod(stat.S_IREAD | stat.S_IWRITE)
                receipt_path.write_text(
                    json.dumps(payload, ensure_ascii=False),
                    encoding="utf-8",
                )
                receipt_path.chmod(stat.S_IREAD)

            validated = preflight_raw_codex_judge_receipt_for_readback(
                raw_judge_receipt=receipt_path,
                codex_cli_trust_anchor=anchor_path,
            )
            self.assertEqual(validated["thread_id"], validated["binding"]["thread_id"])
            self.assertEqual(validated["packet_rows"], fixture["packet_rows"])
            self.assertEqual(validated["verdict_rows"], fixture["verdict_rows"])
            self.assertEqual(
                validated["security_dependency_validation"]["validation_mode"],
                "current_source_snapshot",
            )

            consumer_relative = "tools/build_adjusted_collateral_adjudication.py"
            predecessor = REVIEWED_PREDECESSOR_SECURITY_DEPENDENCY_SNAPSHOTS[
                consumer_relative
            ]

            def recompute_observed_aggregate(manifest: dict) -> None:
                observed = [
                    {
                        "relative_path": record["relative_path"],
                        "absolute_path": record["absolute_path"],
                        "size": record["size_before"],
                        "sha256": record["sha256_before"],
                    }
                    for record in manifest["dependencies"]
                ]
                aggregate = canonical_digest(observed)
                manifest["aggregate_sha256_before"] = aggregate
                manifest["aggregate_sha256_after"] = aggregate

            def apply_reviewed_predecessor(payload: dict) -> tuple[dict, dict]:
                manifest = payload["security_dependency_manifest"]
                consumer_record = next(
                    record
                    for record in manifest["dependencies"]
                    if record["relative_path"] == consumer_relative
                )
                consumer_record["size_before"] = predecessor["size"]
                consumer_record["size_after"] = predecessor["size"]
                consumer_record["sha256_before"] = predecessor["sha256"]
                consumer_record["sha256_after"] = predecessor["sha256"]
                recompute_observed_aggregate(manifest)
                return manifest, consumer_record

            restore_fixture()
            predecessor_payload = json.loads(
                original_receipt_bytes.decode("utf-8-sig")
            )
            apply_reviewed_predecessor(predecessor_payload)
            write_receipt(predecessor_payload)
            migrated = preflight_raw_codex_judge_receipt_for_readback(
                raw_judge_receipt=receipt_path,
                codex_cli_trust_anchor=anchor_path,
            )
            migration_provenance = migrated["security_dependency_validation"]
            self.assertEqual(
                migration_provenance["validation_mode"],
                "reviewed_predecessor_snapshot_migration",
            )
            self.assertEqual(
                migration_provenance["migration_rows"],
                [
                    {
                        "relative_path": consumer_relative,
                        "receipt_observed_sha256": predecessor["sha256"],
                        "receipt_observed_size": predecessor["size"],
                        "current_sha256": file_sha256(
                            Path(__file__).resolve().parents[1]
                            / consumer_relative
                        ),
                        "current_size": (
                            Path(__file__).resolve().parents[1] / consumer_relative
                        ).stat().st_size,
                        "migration_id": predecessor["migration_id"],
                    }
                ],
            )

            dependency_attacks = (
                (
                    "predecessor_hash",
                    "security dependency bytes changed",
                    lambda manifest, record: (
                        record.__setitem__("sha256_before", "0" * 64),
                        record.__setitem__("sha256_after", "0" * 64),
                        recompute_observed_aggregate(manifest),
                    ),
                ),
                (
                    "predecessor_size",
                    "security dependency bytes changed",
                    lambda manifest, record: (
                        record.__setitem__("size_before", predecessor["size"] + 1),
                        record.__setitem__("size_after", predecessor["size"] + 1),
                        recompute_observed_aggregate(manifest),
                    ),
                ),
                (
                    "observed_aggregate",
                    "security dependency aggregate mismatch",
                    lambda manifest, _record: (
                        manifest.__setitem__("aggregate_sha256_before", "0" * 64),
                        manifest.__setitem__("aggregate_sha256_after", "0" * 64),
                    ),
                ),
                (
                    "other_dependency",
                    "security dependency bytes changed",
                    lambda manifest, _record: (
                        next(
                            row
                            for row in manifest["dependencies"]
                            if row["relative_path"]
                            == "tools/build_adjusted_collateral_blind_packet.py"
                        ).__setitem__("sha256_before", "0" * 64),
                        next(
                            row
                            for row in manifest["dependencies"]
                            if row["relative_path"]
                            == "tools/build_adjusted_collateral_blind_packet.py"
                        ).__setitem__("sha256_after", "0" * 64),
                        recompute_observed_aggregate(manifest),
                    ),
                ),
                (
                    "predecessor_extra_field",
                    "security dependency record schema invalid",
                    lambda _manifest, record: record.__setitem__(
                        "self_authored_allow", True
                    ),
                ),
            )
            for attack_name, expected_error, mutate_dependency in dependency_attacks:
                restore_fixture()
                payload = json.loads(original_receipt_bytes.decode("utf-8-sig"))
                manifest, consumer_record = apply_reviewed_predecessor(payload)
                mutate_dependency(manifest, consumer_record)
                write_receipt(payload)
                with self.subTest(dependency_attack=attack_name):
                    with self.assertRaisesRegex(ValueError, expected_error):
                        preflight_raw_codex_judge_receipt_for_readback(
                            raw_judge_receipt=receipt_path,
                            codex_cli_trust_anchor=anchor_path,
                        )

            mutations = (
                (
                    "command_override",
                    "exact reviewed vector",
                    lambda payload: (
                        payload["command"].__setitem__(2, "--provider"),
                        payload["command"].__setitem__(3, "untrusted"),
                        payload["execution_process"].__setitem__(
                            "command_sha256", canonical_digest(payload["command"])
                        ),
                    ),
                ),
                (
                    "launcher_boundary",
                    "launcher/execution process evidence",
                    lambda payload: payload["launcher_process"].__setitem__(
                        "execution_boundary", "forged"
                    ),
                ),
                (
                    "execution_parent",
                    "launcher/execution process evidence",
                    lambda payload: payload["execution_process"].__setitem__(
                        "parent_process_id",
                        payload["launcher_process"]["pid"] + 1,
                    ),
                ),
                ("raw_event_completion", "no completed turn", None),
            )
            try:
                for mutation_name, expected_error, mutate in mutations:
                    restore_fixture()
                    payload = json.loads(original_receipt_bytes.decode("utf-8-sig"))
                    if mutate is None:
                        raw_rows = [
                            json.loads(line)
                            for line in original_raw_events_bytes.decode(
                                "utf-8-sig"
                            ).splitlines()
                            if line.strip()
                        ]
                        raw_rows = [
                            row
                            for row in raw_rows
                            if row.get("type") != "turn.completed"
                        ]
                        raw_events_path.chmod(stat.S_IREAD | stat.S_IWRITE)
                        raw_events_path.write_text(
                            "".join(
                                json.dumps(row, ensure_ascii=False) + "\n"
                                for row in raw_rows
                            ),
                            encoding="utf-8",
                        )
                        raw_events_path.chmod(stat.S_IREAD)
                        payload["raw_event_count"] = len(raw_rows)
                        payload["raw_events_jsonl_sha256"] = file_sha256(
                            raw_events_path
                        )
                    else:
                        mutate(payload)
                    write_receipt(payload)
                    with self.subTest(mutation=mutation_name):
                        with self.assertRaisesRegex(ValueError, expected_error):
                            preflight_raw_codex_judge_receipt_for_readback(
                                raw_judge_receipt=receipt_path,
                                codex_cli_trust_anchor=anchor_path,
                            )
            finally:
                restore_fixture()

    @unittest.skipUnless(
        PRODUCTION_CODEX_CLI_TRUST_ANCHOR_SHA256.startswith("PENDING_"),
        "production v2 Codex CLI trust anchor is approved",
    )
    def test_nonzero_primary_preflight_is_fail_closed_until_v2_anchor_approved(self):
        with tempfile.TemporaryDirectory(dir=PRODUCTION_REVIEW_DIR) as artifact_dir:
            fixture = _real_full375_validation(
                artifact_dir,
                drift_count=1,
                return_primary_fixture=True,
            )
            with self.assertRaisesRegex(
                ValueError,
                "not the compiled pin|v2 compiled pin mismatch",
            ):
                preflight_raw_codex_judge_receipt_for_readback(
                    raw_judge_receipt=fixture["raw_judge_receipt"],
                    codex_cli_trust_anchor=fixture["codex_cli_trust_anchor"],
                )

    def test_gate_go_requires_golden_and_full_collateral(self):
        report = evaluate_gates(golden=_golden(), collateral=_collateral())

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["component_gate"], "GO")
        self.assertEqual(report["golden"]["gate"], "GO")
        self.assertEqual(report["collateral"]["gate"], "GO")
        self.assertFalse(report["full_scan_approval"])

    def test_golden_runtime_can_come_from_full_panel_audit(self):
        report = evaluate_gates(
            golden=_golden(runtime={"completed_count": 375, "pending_count": 0, "failed_count": 0}),
            collateral=_collateral(),
        )

        self.assertEqual(report["golden"]["gate"], "GO")
        self.assertTrue(report["golden"]["runtime_complete"])

    def test_golden_pass_alone_does_not_approve_without_375_collateral(self):
        report = evaluate_gates(
            golden=_golden(),
            collateral=_collateral(shared_post_count=16, runtime_completed_count=16),
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn("collateral:collateral_shared_post_count_mismatch", report["blockers"])

    def test_collateral_regression_count_blocks_gate(self):
        report = evaluate_gates(
            golden=_golden(),
            collateral=_collateral(changed_post_count=223, collateral_regression_count=183),
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["collateral"]["gate"], "NO-GO")
        self.assertEqual(report["completion_gate"], "adjusted full375 collateral GO + full_scan path")
        self.assertEqual(report["completion_gate_metric"], "not_open_until_adjudicated_rebaseline")
        self.assertFalse(report["raw_20260626_baseline_is_completion_gate"])
        self.assertIn("collateral:collateral_regression_count_nonzero", report["blockers"])

    def test_collateral_review_exclusions_reduce_but_do_not_hide_residual_queue(self):
        report = evaluate_gates(
            golden=_golden(),
            collateral=_collateral(changed_post_count=223, collateral_regression_count=183),
            collateral_review=_collateral_review(),
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["collateral"]["collateral_regression_count"], 183)
        self.assertEqual(report["collateral"]["review_adjusted_regression_count"], 126)
        self.assertTrue(report["collateral"]["review_adjustment"]["applied"])
        self.assertEqual(report["collateral"]["review_adjustment"]["exclusion_candidate_rows"], 57)
        self.assertIn(
            "collateral:collateral_review_adjusted_regression_count_nonzero",
            report["blockers"],
        )

    def test_collateral_review_reports_info_missing_decision_gap(self):
        review = _collateral_review(
            summary={
                "batch_review_rows": 10,
                "reviewed_rows": 10,
                "source_native_decision_rows": 8,
                "info_missing_rows": 2,
                "unreviewed_batch_rows": 0,
                "unreviewed_or_info_missing_batch_rows": 2,
                "validation_issue_count": 0,
                "action_counts": {
                    "exclude_from_regression_count_after_gate_wiring": 3,
                },
                "queue_transition": {
                    "original_p0_rows": 10,
                    "exclusion_candidate_rows": 3,
                    "residual_action_queue_rows": 7,
                },
            }
        )

        report = evaluate_gates(
            golden=_golden(),
            collateral=_collateral(changed_post_count=20, collateral_regression_count=20),
            collateral_review=review,
        )

        adjustment = report["collateral"]["review_adjustment"]
        self.assertTrue(adjustment["applied"])
        self.assertEqual(adjustment["source_native_decision_rows"], 8)
        self.assertEqual(adjustment["info_missing_rows"], 2)
        self.assertEqual(adjustment["unreviewed_or_info_missing_batch_rows"], 2)
        self.assertEqual(report["collateral"]["review_adjusted_regression_count"], 17)

    def test_collateral_review_p0_scope_exclusions_apply_and_leave_unreviewed_p1_visible(self):
        p0_review = _collateral_review(
            summary={
                "batch_review_rows": 138,
                "reviewed_rows": 138,
                "unreviewed_batch_rows": 0,
                "validation_issue_count": 0,
                "label_counts": {"ACCEPT": 34, "REPROCESS": 63, "HOLD": 41},
                "action_counts": {
                    "exclude_from_regression_count_after_gate_wiring": 34,
                    "repair_safe_loss_restore_supported_title": 56,
                },
                "queue_transition": {
                    "original_p0_rows": 138,
                    "exclusion_candidate_rows": 34,
                    "residual_action_queue_rows": 104,
                },
            }
        )

        report = evaluate_gates(
            golden=_golden(),
            collateral=_collateral(changed_post_count=197, collateral_regression_count=139),
            collateral_review=p0_review,
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertTrue(report["collateral"]["review_adjustment"]["applied"])
        self.assertEqual(report["collateral"]["review_adjustment"]["review_scope"], "p0_scoped")
        self.assertEqual(report["collateral"]["review_adjustment"]["exclusion_candidate_rows"], 34)
        self.assertEqual(report["collateral"]["review_adjustment"]["unreviewed_regression_rows"], 1)
        self.assertEqual(report["collateral"]["review_adjusted_regression_count"], 105)
        self.assertIn(
            "collateral:collateral_review_adjusted_regression_count_nonzero",
            report["blockers"],
        )
        self.assertIn(
            "collateral:collateral_review_unreviewed_regression_rows_nonzero",
            report["blockers"],
        )

    def test_collateral_review_uses_post_id_overlap_when_rows_are_available(self):
        review = _collateral_review(
            summary={
                "batch_review_rows": 3,
                "reviewed_rows": 3,
                "unreviewed_batch_rows": 0,
                "validation_issue_count": 0,
                "action_counts": {
                    "exclude_from_regression_count_after_gate_wiring": 2,
                },
                "queue_transition": {
                    "original_p0_rows": 3,
                    "exclusion_candidate_rows": 2,
                    "residual_action_queue_rows": 1,
                },
            },
            rows=[
                {
                    "post_id": 1,
                    "action": ["exclude_from_regression_count_after_gate_wiring"],
                },
                {"post_id": 2, "action": ["repair_after_wrong_work"]},
                {
                    "post_id": 9,
                    "action": ["exclude_from_regression_count_after_gate_wiring"],
                },
            ],
        )
        collateral = _collateral(
            changed_post_count=5,
            collateral_regression_count=4,
            rows=[
                {"post_id": 1, "is_regression": True},
                {"post_id": 2, "is_regression": True},
                {"post_id": 3, "is_regression": True},
                {"post_id": 4, "is_regression": True},
                {"post_id": 9, "is_regression": False},
            ],
        )

        report = evaluate_gates(golden=_golden(), collateral=collateral, collateral_review=review)
        adjustment = report["collateral"]["review_adjustment"]

        self.assertTrue(adjustment["applied"])
        self.assertEqual(adjustment["exclusion_candidate_rows"], 1)
        self.assertEqual(adjustment["reviewed_raw_regression_rows"], 2)
        self.assertEqual(adjustment["reviewed_non_regression_rows"], 1)
        self.assertEqual(adjustment["unreviewed_regression_rows"], 2)
        self.assertEqual(adjustment["unreviewed_regression_post_ids"], [3, 4])
        self.assertEqual(report["collateral"]["review_adjusted_regression_count"], 3)

    def test_collateral_review_allows_extra_non_regression_rows_when_raw_ids_fully_covered(self):
        review = _collateral_review(
            summary={
                "batch_review_rows": 4,
                "reviewed_rows": 4,
                "unreviewed_batch_rows": 0,
                "validation_issue_count": 0,
                "action_counts": {
                    "exclude_from_regression_count_after_gate_wiring": 3,
                },
                "queue_transition": {
                    "original_p0_rows": 4,
                    "exclusion_candidate_rows": 3,
                    "residual_action_queue_rows": 1,
                },
            },
            rows=[
                {
                    "post_id": 1,
                    "action": ["exclude_from_regression_count_after_gate_wiring"],
                },
                {
                    "post_id": 2,
                    "action": ["exclude_from_regression_count_after_gate_wiring"],
                },
                {"post_id": 3, "action": ["repair_after_wrong_work"]},
                {
                    "post_id": 9,
                    "action": ["exclude_from_regression_count_after_gate_wiring"],
                },
            ],
        )
        collateral = _collateral(
            changed_post_count=4,
            collateral_regression_count=3,
            rows=[
                {"post_id": 1, "is_regression": True},
                {"post_id": 2, "is_regression": True},
                {"post_id": 3, "is_regression": True},
                {"post_id": 9, "is_regression": False},
            ],
        )

        report = evaluate_gates(golden=_golden(), collateral=collateral, collateral_review=review)
        adjustment = report["collateral"]["review_adjustment"]

        self.assertTrue(adjustment["applied"])
        self.assertEqual(adjustment["review_scope"], "full_regression_post_id_overlap")
        self.assertEqual(adjustment["reviewed_raw_regression_rows"], 3)
        self.assertEqual(adjustment["reviewed_non_regression_rows"], 1)
        self.assertEqual(adjustment["unreviewed_regression_rows"], 0)
        self.assertEqual(adjustment["unreviewed_regression_post_ids"], [])
        self.assertEqual(adjustment["exclusion_candidate_rows"], 2)
        self.assertEqual(report["collateral"]["review_adjusted_regression_count"], 1)
        self.assertNotIn(
            "collateral:collateral_review_batch_count_mismatch",
            report["blockers"],
        )

    def test_collateral_review_adjustment_requires_clean_full_review_summary(self):
        dirty_review = _collateral_review(
            summary={
                "batch_review_rows": 183,
                "reviewed_rows": 182,
                "unreviewed_batch_rows": 1,
                "validation_issue_count": 1,
                "action_counts": {
                    "exclude_from_regression_count_after_gate_wiring": 57,
                },
                "queue_transition": {"exclusion_candidate_rows": 57},
            }
        )

        report = evaluate_gates(
            golden=_golden(),
            collateral=_collateral(changed_post_count=223, collateral_regression_count=183),
            collateral_review=dirty_review,
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertFalse(report["collateral"]["review_adjustment"]["applied"])
        self.assertEqual(report["collateral"]["review_adjusted_regression_count"], 183)
        self.assertIn("collateral:collateral_review_validation_issues_nonzero", report["blockers"])
        self.assertIn("collateral:collateral_review_not_fully_reviewed", report["blockers"])
        self.assertIn("collateral:collateral_review_unreviewed_rows_nonzero", report["blockers"])

    def test_full_review_exclusion_can_clear_collateral_gate_without_granting_full_scan_approval(self):
        review = _collateral_review(
            summary={
                "batch_review_rows": 183,
                "reviewed_rows": 183,
                "unreviewed_batch_rows": 0,
                "validation_issue_count": 0,
                "action_counts": {
                    "exclude_from_regression_count_after_gate_wiring": 183,
                },
                "queue_transition": {
                    "exclusion_candidate_rows": 183,
                    "residual_action_queue_rows": 0,
                },
            }
        )

        report = evaluate_gates(
            golden=_golden(),
            collateral=_collateral(changed_post_count=223, collateral_regression_count=183),
            collateral_review=review,
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["component_gate"], "GO")
        self.assertEqual(report["collateral"]["gate"], "GO")
        self.assertEqual(report["collateral"]["review_adjusted_regression_count"], 0)
        self.assertFalse(report["full_scan_approval"])

    @unittest.skipIf(
        PRODUCTION_CODEX_CLI_TRUST_ANCHOR_SHA256.startswith("PENDING_"),
        "production v2 Codex CLI trust anchor is intentionally not approved",
    )
    def test_adjudicated_rebaseline_gate_uses_validated_semantics_not_drift_count(self):
        with tempfile.TemporaryDirectory(dir=PRODUCTION_REVIEW_DIR) as artifact_dir:
            collateral, golden_audit, validation = _real_full375_validation(
                artifact_dir, drift_count=141
            )
            readback_receipt = json.loads(
                Path(
                    validation["source_artifact_paths"]["thread_readback_receipt"]
                ).read_text(encoding="utf-8-sig")
            )
            primary_binding = readback_receipt["primary_binding"]
            self.assertEqual(
                set(primary_binding),
                {
                    "primary_receipt_path",
                    "primary_receipt_sha256",
                    "thread_id",
                    "primary_judge_run_id",
                    "primary_runner_run_id",
                    "primary_process_id",
                    "primary_parent_process_id",
                    "primary_launcher_process_id",
                    "primary_raw_events_sha256",
                    "primary_final_response_sha256",
                    "primary_verdicts_sha256",
                    "session_bundle_path",
                    "session_bundle_sha256",
                    "session_files_sha256",
                },
            )
            self.assertEqual(
                primary_binding["primary_parent_process_id"],
                primary_binding["primary_launcher_process_id"],
            )
            _require_exact_primary_binding(primary_binding, dict(primary_binding))
            with self.assertRaisesRegex(ValueError, "primary binding mismatch"):
                _require_exact_primary_binding(
                    {**primary_binding, "self_authored_extra": True},
                    primary_binding,
                )
            report = evaluate_gates(
                golden=golden_audit,
                collateral=collateral,
                adjudication_validation=validation,
            )

        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["completion_gate_metric"], "adjudicated_semantic_gate")
        self.assertFalse(report["raw_20260626_baseline_is_completion_gate"])
        self.assertEqual(report["collateral"]["gate_metric"], "adjudicated_semantic_gate")
        self.assertEqual(report["collateral"]["gate_regression_count"], 0)
        self.assertEqual(report["collateral"]["diagnostic_adjusted_drift_count"], 141)
        self.assertEqual(report["collateral"]["historical_raw_collateral_regression_count"], 141)
        self.assertNotIn("collateral:collateral_regression_count_nonzero", report["blockers"])
        self.assertFalse(report["full_scan_approval"])

    def test_adjudicated_rebaseline_requires_validator_even_when_drift_is_zero(self):
        report = evaluate_gates(
            golden=_golden(),
            collateral=_collateral(
                baseline_mode="adjudicated_rebaseline",
                collateral_measure="adjusted_drift",
                adjusted_drift_count=0,
            ),
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn("collateral:collateral_adjudication_validation_missing", report["blockers"])

    def test_authoritative_zero_drift_receipt_does_not_override_exact_golden_failure(self):
        with tempfile.TemporaryDirectory(dir=PRODUCTION_REVIEW_DIR) as artifact_dir:
            collateral, golden_audit, validation = _real_full375_validation(
                artifact_dir,
                drift_count=0,
                require_golden_pass=False,
            )
            raw_receipt = json.loads(
                Path(validation["source_artifact_paths"]["raw_judge_receipt"]).read_text(
                    encoding="utf-8-sig"
                )
            )
            report = evaluate_gates(
                golden=golden_audit,
                collateral=collateral,
                adjudication_validation=validation,
            )

        self.assertEqual(raw_receipt["status"], "NOT_REQUIRED_ZERO_DRIFT")
        self.assertEqual(validation["drift_union_count"], 0)
        self.assertEqual(validation["unreviewed_adjusted_rows"], 0)
        self.assertEqual(validation["authoritative_trust_gate"], "GO")
        self.assertTrue(
            validation["approval_boundary"][
                "validator_recomputed_from_source_artifacts"
            ]
        )
        self.assertTrue(
            validation["approval_boundary"][
                "validator_rebuilt_blind_packet_and_private_map"
            ]
        )
        self.assertEqual(
            validation["source_value_digests"]["blind_packet"],
            canonical_digest([]),
        )
        self.assertEqual(validation["gate"], "GO")
        self.assertEqual(golden_audit["gate"], "NO-GO")
        self.assertEqual(golden_audit["failed_count"], 1)
        self.assertEqual(report["gate"], "NO-GO")

    def test_fresh375_requires_compiled_anchor_and_nonforgeable_start_binding(self):
        from tools.build_adjusted_collateral_blind_packet import (
            _validate_runtime_trust_anchor,
        )

        fresh_anchor = json.loads(
            RUNTIME_TRUST_ANCHOR_PATH.read_text(encoding="utf-8-sig")
        )
        fresh_anchor["topology"] = {
            "profile": "fresh375",
            "components": ["fresh375"],
            "source_rows": 375,
        }
        fresh_anchor.pop("anchor_payload_sha256", None)
        fresh_anchor["anchor_payload_sha256"] = canonical_digest(fresh_anchor)
        with self.assertRaisesRegex(
            ValueError,
            "fresh375 compiled pre-run anchor path/sha256 pin missing",
        ):
            _validate_runtime_trust_anchor(
                anchor=fresh_anchor,
                anchor_path=RUNTIME_TRUST_ANCHOR_PATH.resolve(),
                anchor_byte_sha256=file_sha256(RUNTIME_TRUST_ANCHOR_PATH),
                resolved={},
                byte_hashes={},
                baseline_rows=[],
                source_rows=[],
                golden_manifest={"rows": []},
                expected_scope_rows=375,
                expected_golden_rows=18,
            )

    def test_adjudicated_rebaseline_rejects_handcrafted_six_field_go(self):
        collateral = _collateral(
            baseline_mode="adjudicated_rebaseline",
            collateral_measure="adjusted_drift",
            adjusted_drift_count=0,
        )
        self_authored = {
            "validator_gate": "GO",
            "semantic_gate": "GO",
            "gate": "GO",
            "unreviewed_adjusted_rows": 0,
            "true_semantic_regression_count": 0,
            "actionable_unfixed_count": 0,
        }

        report = evaluate_gates(
            golden=_golden(),
            collateral=collateral,
            adjudication_validation=self_authored,
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn("collateral:collateral_adjudication_validation_unbound", report["blockers"])
        self.assertIn(
            "validation_report_type_mismatch",
            report["collateral"]["adjudication_binding_issues"],
        )

    def test_adjudicated_rebaseline_rejects_tampered_validator_receipt(self):
        collateral = _collateral(
            changed_post_count=1,
            baseline_mode="adjudicated_rebaseline",
            collateral_measure="adjusted_drift",
            adjusted_drift_count=1,
        )
        validation = _adjudication_validation(collateral=collateral)
        validation["source_changed_count"] = 999

        report = evaluate_gates(
            golden=_golden(),
            collateral=collateral,
            adjudication_validation=validation,
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn("source_changed_count_mismatch", report["collateral"]["adjudication_binding_issues"])
        self.assertIn("validation_receipt_digest_mismatch", report["collateral"]["adjudication_binding_issues"])

    @unittest.skipIf(
        PRODUCTION_CODEX_CLI_TRUST_ANCHOR_SHA256.startswith("PENDING_"),
        "production v2 Codex CLI trust anchor is intentionally not approved",
    )
    def test_authoritative_roots_swaps_and_forged_verdicts_fail_closed(self):
        with tempfile.TemporaryDirectory(dir=PRODUCTION_REVIEW_DIR) as artifact_dir:
            collateral, golden_audit, validation = _real_full375_validation(
                artifact_dir, drift_count=1
            )

            replaced_root = copy.deepcopy(validation)
            replaced_root["trust_anchors"]["panel_source_sha256"] = "0" * 64
            replaced_root = finalize_validation_receipt(replaced_root)
            root_report = evaluate_gates(
                golden=golden_audit,
                collateral=collateral,
                adjudication_validation=replaced_root,
            )

            swapped_after = copy.deepcopy(validation)
            paths = swapped_after["source_artifact_paths"]
            hashes = swapped_after["source_artifact_hashes"]
            digests = swapped_after["source_value_digests"]
            paths["after_result"] = paths["baseline_result"]
            hashes["after_result_sha256"] = hashes["baseline_result_sha256"]
            digests["after_result"] = digests["baseline_result"]
            swapped_after["bound_after_payload_sha256"] = digests["baseline_result"]
            swapped_after = finalize_validation_receipt(swapped_after)
            swap_report = evaluate_gates(
                golden=golden_audit,
                collateral=collateral,
                adjudication_validation=swapped_after,
            )

            forged_anchor = copy.deepcopy(validation)
            original_anchor_path = Path(
                forged_anchor["source_artifact_paths"]["runtime_trust_anchor"]
            )
            forged_anchor_path = Path(artifact_dir) / "forged_runtime_trust_anchor.json"
            forged_anchor_payload = json.loads(
                original_anchor_path.read_text(encoding="utf-8-sig")
            )
            forged_anchor_payload["stable_projection"]["plan"]["runtime_contract"][
                "slang_db"
            ] = "read-only"
            forged_anchor_payload.pop("anchor_payload_sha256", None)
            forged_anchor_payload["anchor_payload_sha256"] = canonical_digest(
                forged_anchor_payload
            )
            forged_anchor_path.write_text(
                json.dumps(forged_anchor_payload, ensure_ascii=False),
                encoding="utf-8",
            )
            forged_anchor["source_artifact_paths"]["runtime_trust_anchor"] = str(
                forged_anchor_path
            )
            forged_anchor_sha = file_sha256(forged_anchor_path)
            forged_anchor["source_artifact_hashes"][
                "runtime_trust_anchor_sha256"
            ] = forged_anchor_sha
            forged_anchor["source_value_digests"]["runtime_trust_anchor"] = canonical_digest(
                forged_anchor_payload
            )
            forged_anchor["trust_anchors"]["runtime_trust_anchor_sha256"] = forged_anchor_sha
            forged_anchor = finalize_validation_receipt(forged_anchor)
            anchor_report = evaluate_gates(
                golden=golden_audit,
                collateral=collateral,
                adjudication_validation=forged_anchor,
            )

            nonzero_marker = copy.deepcopy(validation)
            raw_receipt_path = Path(
                nonzero_marker["source_artifact_paths"]["raw_judge_receipt"]
            )
            original_raw_receipt = raw_receipt_path.read_bytes()
            raw_receipt_path.chmod(stat.S_IREAD | stat.S_IWRITE)
            marker_payload = {
                "report_type": RAW_JUDGE_REPORT_TYPE,
                "receipt_version": RAW_JUDGE_VERSION,
                "gate": "NOT_REQUIRED",
                "status": "NOT_REQUIRED_ZERO_DRIFT",
                "provider": "codex",
                "model": "gpt-5.6-sol",
                "goal_id": PRODUCTION_GOAL_ID,
                "continuation_source_session": CONTINUATION_SOURCE_SESSION,
                "packet_rows_sha256": canonical_digest([]),
                "delivered_verdict_rows_sha256": canonical_digest([]),
                "row_count": 0,
                "rows": [],
                "validation_issues": [],
            }
            raw_receipt_path.write_text(
                json.dumps(marker_payload, ensure_ascii=False),
                encoding="utf-8",
            )
            marker_sha = file_sha256(raw_receipt_path)
            nonzero_marker["source_artifact_hashes"]["raw_judge_receipt_sha256"] = marker_sha
            nonzero_marker["source_value_digests"]["raw_judge_receipt"] = canonical_digest(
                marker_payload
            )
            nonzero_marker["raw_judge_receipt_sha256"] = marker_sha
            nonzero_marker = finalize_validation_receipt(nonzero_marker)
            marker_report = evaluate_gates(
                golden=golden_audit,
                collateral=collateral,
                adjudication_validation=nonzero_marker,
            )
            raw_receipt_path.write_bytes(original_raw_receipt)
            raw_receipt_path.chmod(stat.S_IREAD)

            fake_path_command = copy.deepcopy(validation)
            fake_receipt_payload = json.loads(original_raw_receipt.decode("utf-8-sig"))
            fake_receipt_payload["command"][0] = r"C:\fake-path\codex.cmd"
            raw_receipt_path.chmod(stat.S_IREAD | stat.S_IWRITE)
            raw_receipt_path.write_text(
                json.dumps(fake_receipt_payload, ensure_ascii=False),
                encoding="utf-8",
            )
            raw_receipt_path.chmod(stat.S_IREAD)
            fake_receipt_sha = file_sha256(raw_receipt_path)
            fake_path_command["source_artifact_hashes"][
                "raw_judge_receipt_sha256"
            ] = fake_receipt_sha
            fake_path_command["source_value_digests"]["raw_judge_receipt"] = canonical_digest(
                fake_receipt_payload
            )
            fake_path_command["raw_judge_receipt_sha256"] = fake_receipt_sha
            fake_path_command = finalize_validation_receipt(fake_path_command)
            fake_path_report = evaluate_gates(
                golden=golden_audit,
                collateral=collateral,
                adjudication_validation=fake_path_command,
            )
            raw_receipt_path.chmod(stat.S_IREAD | stat.S_IWRITE)
            raw_receipt_path.write_bytes(original_raw_receipt)
            raw_receipt_path.chmod(stat.S_IREAD)

            omitted_binding = copy.deepcopy(validation)
            omitted_binding["source_artifact_paths"].pop(
                "merge_binding_receipt"
            )
            omitted_binding["source_artifact_hashes"].pop(
                "merge_binding_receipt_sha256"
            )
            omitted_binding["source_value_digests"].pop(
                "merge_binding_receipt"
            )
            omitted_binding = finalize_validation_receipt(omitted_binding)
            omitted_binding_report = evaluate_gates(
                golden=golden_audit,
                collateral=collateral,
                adjudication_validation=omitted_binding,
            )

            swapped_binding = copy.deepcopy(validation)
            swapped_binding["source_artifact_paths"]["merge_binding_receipt"] = (
                swapped_binding["source_artifact_paths"]["merged_manifest"]
            )
            swapped_binding["source_artifact_hashes"][
                "merge_binding_receipt_sha256"
            ] = swapped_binding["source_artifact_hashes"][
                "merged_manifest_sha256"
            ]
            swapped_binding["source_value_digests"]["merge_binding_receipt"] = (
                swapped_binding["source_value_digests"]["merged_manifest"]
            )
            swapped_binding = finalize_validation_receipt(swapped_binding)
            swapped_binding_report = evaluate_gates(
                golden=golden_audit,
                collateral=collateral,
                adjudication_validation=swapped_binding,
            )

            binding_path = Path(
                validation["source_artifact_paths"]["merge_binding_receipt"]
            )
            original_binding_receipt = binding_path.read_bytes()
            binding_path.chmod(stat.S_IREAD | stat.S_IWRITE)
            tampered_binding_payload = json.loads(
                original_binding_receipt.decode("utf-8-sig")
            )
            tampered_binding_payload["finalized"] = False
            binding_path.write_text(
                json.dumps(tampered_binding_payload, ensure_ascii=False),
                encoding="utf-8",
            )
            binding_path.chmod(stat.S_IREAD)
            tampered_binding = copy.deepcopy(validation)
            tampered_binding["source_artifact_hashes"][
                "merge_binding_receipt_sha256"
            ] = file_sha256(binding_path)
            tampered_binding["source_value_digests"]["merge_binding_receipt"] = (
                canonical_digest(tampered_binding_payload)
            )
            tampered_binding = finalize_validation_receipt(tampered_binding)
            tampered_binding_report = evaluate_gates(
                golden=golden_audit,
                collateral=collateral,
                adjudication_validation=tampered_binding,
            )
            binding_path.chmod(stat.S_IREAD | stat.S_IWRITE)
            binding_path.write_bytes(original_binding_receipt)
            binding_path.chmod(stat.S_IREAD)

            forged_verdict = copy.deepcopy(validation)
            verdict_path = Path(forged_verdict["source_artifact_paths"]["verdicts_jsonl"])
            verdict_path.chmod(stat.S_IREAD | stat.S_IWRITE)
            forged_rows = load_json_or_jsonl(verdict_path)
            forged_rows[0]["row_rationale"] = "forged after receipt"
            verdict_path.write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in forged_rows),
                encoding="utf-8",
            )
            forged_verdict["source_artifact_hashes"]["verdicts_jsonl_sha256"] = file_sha256(
                verdict_path
            )
            forged_verdict["source_value_digests"]["verdict_rows"] = canonical_digest(
                forged_rows
            )
            forged_verdict = finalize_validation_receipt(forged_verdict)
            verdict_report = evaluate_gates(
                golden=golden_audit,
                collateral=collateral,
                adjudication_validation=forged_verdict,
            )

        for report in (
            root_report,
            swap_report,
            anchor_report,
            marker_report,
            fake_path_report,
            swapped_binding_report,
            tampered_binding_report,
            verdict_report,
        ):
            self.assertEqual(report["gate"], "NO-GO")
            self.assertIn(
                "validator_source_recompute_failed",
                report["collateral"]["adjudication_binding_issues"],
            )
        self.assertEqual(omitted_binding_report["gate"], "NO-GO")
        self.assertIn(
            "source_artifact_paths_incomplete",
            omitted_binding_report["collateral"]["adjudication_binding_issues"],
        )

    @unittest.skipIf(
        PRODUCTION_CODEX_CLI_TRUST_ANCHOR_SHA256.startswith("PENDING_"),
        "production v2 Codex CLI trust anchor is intentionally not approved",
    )
    def test_adjudicated_rebaseline_rejects_source_artifact_changed_after_validation(self):
        with tempfile.TemporaryDirectory(dir=PRODUCTION_REVIEW_DIR) as artifact_dir:
            collateral, golden_audit, validation = _real_full375_validation(
                artifact_dir, drift_count=18
            )
            after_result_path = Path(
                validation["source_artifact_paths"]["after_result"]
            )
            after_result_path.chmod(stat.S_IREAD | stat.S_IWRITE)
            after_result_path.write_text(
                "[]",
                encoding="utf-8",
            )
            report = evaluate_gates(
                golden=golden_audit,
                collateral=collateral,
                adjudication_validation=validation,
            )
            after_result_path.chmod(stat.S_IREAD)

        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn(
            "source_artifact_hash_mismatch:after_result",
            report["collateral"]["adjudication_binding_issues"],
        )
        self.assertIn(
            "source_artifact_value_digest_mismatch:after_result",
            report["collateral"]["adjudication_binding_issues"],
        )

    def test_adjudicated_rebaseline_blocks_unreviewed_or_true_regression(self):
        collateral = _collateral(
            baseline_mode="adjudicated_rebaseline",
            collateral_measure="adjusted_drift",
            adjusted_drift_count=2,
            changed_post_count=2,
        )
        report = evaluate_gates(
            golden=_golden(),
            collateral=collateral,
            adjudication_validation=_adjudication_validation(
                collateral=collateral,
                semantic_gate="NO-GO",
                gate="NO-GO",
                unreviewed_adjusted_rows=1,
                true_semantic_regression_count=1,
                actionable_unfixed_count=1,
            ),
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn("collateral:collateral_unreviewed_adjusted_rows_nonzero", report["blockers"])
        self.assertIn("collateral:collateral_true_semantic_regression_nonzero", report["blockers"])

    def test_contract_accounting_can_clear_reviewed_actionable_residuals_without_approval(self):
        review = _collateral_review(
            summary={
                "batch_review_rows": 3,
                "reviewed_rows": 3,
                "unreviewed_batch_rows": 0,
                "validation_issue_count": 0,
                "action_counts": {
                    "exclude_from_regression_count_after_gate_wiring": 1,
                },
                "queue_transition": {
                    "original_p0_rows": 3,
                    "exclusion_candidate_rows": 1,
                    "residual_action_queue_rows": 2,
                },
            },
            rows=[
                {
                    "post_id": 1,
                    "action": ["exclude_from_regression_count_after_gate_wiring"],
                },
                {"post_id": 2, "action": ["native_web_or_image_evidence_required"]},
                {"post_id": 3, "action": ["candidate_set_rebuild_required"]},
            ],
        )
        collateral = _collateral(
            changed_post_count=3,
            collateral_regression_count=3,
            rows=[
                {"post_id": 1, "is_regression": True},
                {"post_id": 2, "is_regression": True},
                {"post_id": 3, "is_regression": True},
            ],
        )

        report = evaluate_gates(
            golden=_golden(),
            collateral=collateral,
            collateral_review=review,
            contract_accounting=_contract_accounting(),
        )

        accounting = report["collateral"]["review_adjustment"]["contract_accounting"]
        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["component_gate"], "GO")
        self.assertEqual(report["collateral"]["review_adjusted_regression_count"], 0)
        self.assertTrue(accounting["applied"])
        self.assertEqual(accounting["contract_accounted_raw_regression_rows"], 2)
        self.assertEqual(accounting["contract_accounted_additional_rows"], 2)
        self.assertFalse(report["full_scan_approval"])

    def test_full_collateral_gate_requires_explicit_runtime_counts(self):
        collateral = _collateral()
        collateral.pop("runtime_completed_count")
        collateral.pop("runtime_flushed_count")
        collateral.pop("runtime_pending_count")
        collateral.pop("runtime_failed_count")

        report = evaluate_gates(golden=_golden(), collateral=collateral)

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["collateral"]["gate"], "NO-GO")
        self.assertIn("collateral:collateral_runtime_counts_missing", report["blockers"])

    def test_full_collateral_gate_does_not_coerce_missing_pending_to_zero(self):
        collateral = _collateral()
        collateral.pop("runtime_pending_count")

        report = evaluate_gates(golden=_golden(), collateral=collateral)

        self.assertEqual(report["gate"], "NO-GO")
        self.assertFalse(report["collateral"]["runtime_complete"])
        self.assertIn("collateral:collateral_runtime_counts_missing", report["blockers"])

    def test_full_collateral_gate_requires_flushed_375(self):
        report = evaluate_gates(
            golden=_golden(),
            collateral=_collateral(runtime_flushed_count=374),
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn("collateral:collateral_runtime_not_complete", report["blockers"])

    def test_golden_failure_blocks_even_when_collateral_clean(self):
        report = evaluate_gates(
            golden=_golden(passed_count=15, failed_count=1, canary_semantic_gate="NO-GO"),
            collateral=_collateral(),
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn("golden:golden_expected_answer_failures", report["blockers"])
        self.assertIn("golden:golden_semantic_gate_not_pass", report["blockers"])

    def test_golden_missing_failed_count_is_not_zero(self):
        golden = _golden()
        golden.pop("failed_count")

        report = evaluate_gates(golden=golden, collateral=_collateral())

        self.assertEqual(report["golden"]["gate"], "NO-GO")
        self.assertIn("golden:golden_expected_answer_failures", report["blockers"])


if __name__ == "__main__":
    unittest.main()
