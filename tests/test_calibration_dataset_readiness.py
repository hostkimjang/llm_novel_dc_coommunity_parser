from __future__ import annotations

import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.llm_batch.grounding.calibration_dataset_readiness import (
    GATE_NOT_READY,
    GATE_READY,
    sha256_payload,
    validate_dataset_readiness_against_sources,
    validate_dataset_readiness_manifest,
)
from src.llm_batch.grounding.candidate_set_calibration_shadow import CalibrationEvaluationPolicy
from tools.run_calibration_dataset_readiness import (
    build_current_readiness,
    render_markdown,
    write_outputs,
)


ROOT = Path(__file__).resolve().parents[1]
P1_RUN_SPEC = ROOT / "out/candidate_set_nil_shadow_harness_20260711/v8/run_spec.json"
P1_COMPARISON = ROOT / "out/candidate_set_nil_shadow_harness_20260711/v8/comparison.json"
LABEL_LEDGER = ROOT / "docs/devs/p1_candidate_set_nil_golden18_label_ledger_20260711.json"


class CalibrationDatasetReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = build_current_readiness(
            p1_run_spec_path=P1_RUN_SPEC,
            p1_comparison_path=P1_COMPARISON,
            label_ledger_path=LABEL_LEDGER,
        )

    def test_current_golden18_is_explicitly_not_actual_ready(self):
        manifest = self.manifest
        self.assertEqual(GATE_NOT_READY, manifest["gate"])
        self.assertFalse(manifest["ready_for_split_manifest"])
        self.assertIsNone(manifest["split_manifest"])
        self.assertIsNone(manifest["actual_metrics"])
        self.assertEqual(
            {
                "source_rows": 18,
                "candidate_truth": 9,
                "nil_truth": 6,
                "unjudged": 3,
                "generation_complete": 0,
                "ready_rows": 0,
            },
            manifest["counts"],
        )
        self.assertEqual("REVIEW-LOCKED", manifest["semantic_quality"])
        self.assertFalse(manifest["full_scan_approval"])

    def test_unknown_and_unjudged_cannot_be_promoted(self):
        rows = self.manifest["rows"]
        self.assertTrue(all("PRODUCER_GENERATION_NOT_COMPLETE" in row["blockers"] for row in rows))
        unjudged = [row for row in rows if row["truth_kind"] == "UNJUDGED"]
        self.assertEqual(3, len(unjudged))
        self.assertTrue(all("TRUTH_UNJUDGED" in row["blockers"] for row in unjudged))
        candidates = [row for row in rows if row["truth_kind"] == "CANDIDATE"]
        self.assertEqual(9, len(candidates))
        self.assertTrue(all(row["candidate_title_observed"] is True for row in candidates))
        self.assertTrue(all("IMMUTABLE_CANDIDATE_ID_BINDING_MISSING" in row["blockers"] for row in candidates))

    def test_self_rehashed_gate_or_row_tamper_is_rejected(self):
        forged = copy.deepcopy(self.manifest)
        forged["rows"][0]["blockers"] = []
        forged["rows"][0]["ready_for_split_assignment"] = True
        forged["rows"][0]["row_sha256"] = sha256_payload(
            {key: value for key, value in forged["rows"][0].items() if key != "row_sha256"}
        )
        forged["manifest_sha256"] = sha256_payload(
            {key: value for key, value in forged.items() if key != "manifest_sha256"}
        )
        with self.assertRaises(ValueError):
            validate_dataset_readiness_manifest(forged)
        forged = copy.deepcopy(self.manifest)
        forged["ready_for_split_manifest"] = True
        with self.assertRaises(ValueError):
            validate_dataset_readiness_manifest(forged)

    def test_fully_self_rehashed_ready_forgery_fails_source_replay(self):
        forged = copy.deepcopy(self.manifest)
        policy = self._actual_policy()
        forged["actual_evaluation_policy_sha256"] = policy.policy_sha256
        forged["actual_evaluation_policy"] = {
            "path": "forged-actual-policy.json",
            "sha256": "a" * 64,
            "bytes": 1,
        }
        for index, row in enumerate(forged["rows"]):
            if row["truth_kind"] == "UNJUDGED":
                row["truth_kind"] = "NIL"
            row["generation_status"] = "COMPLETE"
            row["split_group_id"] = f"group-{index}"
            row["content_fingerprint"] = f"{index + 1:064x}"
            row["source_group_fingerprint"] = f"{index + 101:064x}"
            row["label_provenance_sha256"] = f"{index + 201:064x}"
            if row["truth_kind"] == "CANDIDATE":
                row["truth_candidate_id"] = f"candidate-{index}"
                row["gold_work_fingerprint"] = f"{index + 301:064x}"
                row["binding_status"] = "UNIQUE"
                row["candidate_title_observed"] = True
            else:
                row["truth_candidate_id"] = None
                row["gold_work_fingerprint"] = None
                row["binding_status"] = "NOT_APPLICABLE"
            row["blockers"] = []
            row["ready_for_split_assignment"] = True
            row["row_sha256"] = sha256_payload(
                {key: value for key, value in row.items() if key != "row_sha256"}
            )
        forged["counts"] = {
            "source_rows": len(forged["rows"]),
            "candidate_truth": sum(row["truth_kind"] == "CANDIDATE" for row in forged["rows"]),
            "nil_truth": sum(row["truth_kind"] == "NIL" for row in forged["rows"]),
            "unjudged": 0,
            "generation_complete": len(forged["rows"]),
            "ready_rows": len(forged["rows"]),
        }
        forged["ready_for_split_manifest"] = True
        forged["gate"] = GATE_READY
        forged["manifest_sha256"] = sha256_payload(
            {key: value for key, value in forged.items() if key != "manifest_sha256"}
        )
        validate_dataset_readiness_manifest(forged)
        p1_comparison = json.loads(P1_COMPARISON.read_text(encoding="utf-8"))
        label_ledger = json.loads(LABEL_LEDGER.read_text(encoding="utf-8"))
        with self.assertRaisesRegex(ValueError, "source replay mismatch"):
            validate_dataset_readiness_against_sources(
                forged,
                p1_comparison=p1_comparison,
                label_ledger=label_ledger,
                actual_evaluation_policy=policy.to_dict(),
                actual_evaluation_policy_ref=forged["actual_evaluation_policy"],
            )

    def test_outputs_are_korean_and_exclusive(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            json_path, markdown_path = write_outputs(
                self.manifest,
                output_json=root / "readiness.json",
                output_markdown=root / "readiness.md",
            )
            self.assertTrue(json_path.is_file())
            self.assertIn("실제 보정 자료 준비도", markdown_path.read_text(encoding="utf-8"))
            self.assertIn("NO_GO_ACTUAL_DATASET_NOT_READY", render_markdown(self.manifest))
            with self.assertRaisesRegex(ValueError, "new files"):
                write_outputs(
                    self.manifest,
                    output_json=json_path,
                    output_markdown=markdown_path,
                )

    @staticmethod
    def _actual_policy() -> CalibrationEvaluationPolicy:
        return CalibrationEvaluationPolicy.create(
            fixed_bin_edges=(0.0, 0.5, 1.0),
            selector_max_error_probability=0.2,
            nil_min_probability=0.8,
            alpha=0.05,
            min_dev_rows=2,
            min_dev_per_truth_class=1,
            min_calibration_rows=2,
            min_calibration_per_truth_class=1,
            min_frozen_rows=2,
            min_per_truth_class=1,
            min_occupied_bin_rows=1,
            target_coverage=0.5,
            max_selective_risk_upper_bound=0.5,
            baseline_noninferiority_margin=0.1,
            min_candidate_recall_lower_bound=0.1,
            min_nil_prediction_count=1,
            min_nil_precision_lower_bound=0.1,
            min_nil_recall_lower_bound=0.1,
            paired_delta_ci_bounds={
                "top_label_accuracy": -0.1,
                "brier": 0.1,
                "log_loss": 0.1,
                "ece": 0.1,
                "selective_risk": 0.1,
                "aurc": 0.1,
            },
            policy_scope="FROZEN_ACTUAL_PRE_REGISTERED",
            policy_origin="PRE_REGISTERED_DEV_CALIBRATION",
        )

    def test_actual_policy_is_read_from_file_and_removes_only_policy_blocker(self):
        with TemporaryDirectory() as directory:
            policy_path = Path(directory) / "policy.json"
            policy = self._actual_policy()
            policy_path.write_text(
                json.dumps(policy.to_dict(), ensure_ascii=False),
                encoding="utf-8",
            )
            manifest = build_current_readiness(
                p1_run_spec_path=P1_RUN_SPEC,
                p1_comparison_path=P1_COMPARISON,
                label_ledger_path=LABEL_LEDGER,
                actual_evaluation_policy_path=policy_path,
            )
            self.assertEqual(policy.policy_sha256, manifest["actual_evaluation_policy_sha256"])
            self.assertEqual(GATE_NOT_READY, manifest["gate"])
            self.assertEqual(0, manifest["counts"]["ready_rows"])
            self.assertTrue(
                all(
                    "ACTUAL_EVALUATION_POLICY_NOT_PREREGISTERED" not in row["blockers"]
                    for row in manifest["rows"]
                )
            )

    def test_actual_policy_v3_hash_binds_top_label_accuracy_denominator(self):
        policy = self._actual_policy()
        payload = policy.to_dict()
        self.assertEqual("candidate_set_calibration_policy_v3", payload["schema_version"])
        self.assertEqual("ALL_FROZEN_ROWS", payload["top_label_accuracy_denominator"])
        payload["top_label_accuracy_denominator"] = "NON_ABSTAIN_ROWS"
        with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
            CalibrationEvaluationPolicy(**payload)
        legacy = {
            key: value
            for key, value in policy.to_dict().items()
            if key not in {"policy_sha256", "top_label_accuracy_denominator"}
        }
        legacy["schema_version"] = "candidate_set_calibration_policy_v2"
        with self.assertRaisesRegex(ValueError, "requires explicit v3"):
            CalibrationEvaluationPolicy.create(**legacy)

    def test_synthetic_or_duplicate_key_policy_is_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            synthetic = self._actual_policy().to_dict()
            synthetic["policy_scope"] = "SYNTHETIC_CONTRACT_ONLY"
            synthetic.pop("policy_sha256")
            synthetic_policy = CalibrationEvaluationPolicy.create(
                **{key: value for key, value in synthetic.items() if key != "schema_version"}
            )
            synthetic_path = root / "synthetic.json"
            synthetic_path.write_text(json.dumps(synthetic_policy.to_dict()), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "FROZEN_ACTUAL_PRE_REGISTERED"):
                build_current_readiness(
                    p1_run_spec_path=P1_RUN_SPEC,
                    p1_comparison_path=P1_COMPARISON,
                    label_ledger_path=LABEL_LEDGER,
                    actual_evaluation_policy_path=synthetic_path,
                )
            duplicate_path = root / "duplicate.json"
            duplicate_path.write_text(
                '{"schema_version":"candidate_set_calibration_policy_v2",'
                '"policy_scope":"FROZEN_ACTUAL_PRE_REGISTERED",'
                '"policy_scope":"SYNTHETIC_CONTRACT_ONLY"}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                build_current_readiness(
                    p1_run_spec_path=P1_RUN_SPEC,
                    p1_comparison_path=P1_COMPARISON,
                    label_ledger_path=LABEL_LEDGER,
                    actual_evaluation_policy_path=duplicate_path,
                )


if __name__ == "__main__":
    unittest.main()
