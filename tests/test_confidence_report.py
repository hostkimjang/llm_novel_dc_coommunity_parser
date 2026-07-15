from __future__ import annotations

from dataclasses import replace
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.llm_batch.grounding.calibration_actual_readback import snapshot_artifact
from src.llm_batch.grounding.candidate_set_shadow import LabelProbability, build_candidate_set
from src.llm_batch.grounding.confidence_report import (
    ConfidenceEvaluationRow,
    TypedConfidenceReport,
    read_jsonl_rows,
    read_policy_independent_metrics,
)
from src.llm_batch.promotion_gate import GroundingState


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_LESS_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "typed_confidence_source_less_contract_v1.jsonl"


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


class TypedConfidenceReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.candidate_set = build_candidate_set(
            GroundingState(post_id=1, candidate_title="작품 A"),
            (),
            generation_status="COMPLETE",
        )
        self.work_id = self.candidate_set.candidates[0].candidate_id
        self.fingerprint = self.candidate_set.candidate_set_fingerprint
        payloads = {
            "candidate_set": self.candidate_set.to_dict(),
            "source": {"post_id": "source-row", "body_sha256": "b" * 64},
            "label": {"label_contract": "source-backed"},
            "calibration": {"calibration_contract": "frozen"},
            "prediction": {"prediction_contract": "frozen"},
        }
        refs = []
        for logical_name, payload in payloads.items():
            relative_path = f"{logical_name}.json"
            _write_json(self.root / relative_path, payload)
            refs.append(snapshot_artifact(self.root, logical_name, relative_path))
        self.refs = tuple(refs)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def report(
        self,
        *,
        post_id: str = "1",
        evidence_mode: str = "FROZEN_ACTUAL",
        generation_status: str = "COMPLETE",
        probabilities: tuple[float, float] | None = (0.8, 0.2),
        selected: str | None = None,
        action: str = "SHADOW_SELECT",
        refs=None,
    ) -> TypedConfidenceReport:
        available = probabilities is not None
        if selected is None and available:
            selected = self.work_id
        probability_values = probabilities if probabilities is not None else (None, None)
        selected_probability = None
        if available and selected is not None:
            selected_probability = {
                self.work_id: probability_values[0],
                "__NIL__": probability_values[1],
            }[selected]
        if refs is None:
            refs = self.refs if evidence_mode == "FROZEN_ACTUAL" else ()
        return TypedConfidenceReport(
            post_id=post_id,
            candidate_set_fingerprint=self.fingerprint,
            producer_generation_status=generation_status,
            candidate_set_recall_status=(
                "READY_FOR_GOLD_EVALUATION"
                if generation_status == "COMPLETE"
                else f"NOT_EVALUABLE_GENERATION_{generation_status}"
            ),
            event_probabilities=(
                LabelProbability(self.work_id, probability_values[0]),
                LabelProbability("__NIL__", probability_values[1]),
            ),
            probability_status=(
                "CALIBRATED_FROZEN_ACTUAL"
                if available and evidence_mode == "FROZEN_ACTUAL"
                else "CALIBRATED_SHADOW"
                if available
                else "UNCALIBRATED"
            ),
            selected_label=selected if available else None,
            selected_probability=selected_probability,
            confidence_percentage=selected_probability * 100 if selected_probability is not None else None,
            shadow_action=action,
            action_applied=False,
            operational_effect="NONE_SHADOW_ONLY",
            evidence_mode=evidence_mode,
            evidence_artifacts=tuple(refs),
        )

    def metrics(self, rows, *, ece_bins: int = 10):
        bound = self.bind_rows(tuple(rows))
        return read_policy_independent_metrics(
            bound, ece_bins=ece_bins, artifact_root=self.root
        )

    def bind_rows(self, rows):
        candidate_path = self.root / "bound_candidate_set.json"
        _write_json(candidate_path, self.candidate_set.to_dict())
        candidate_ref = snapshot_artifact(
            self.root, "candidate_set", candidate_path.name
        )
        source_path = self.root / "bound_source.jsonl"
        _write_jsonl(
            source_path,
            [{"post_id": row.report.post_id} for row in rows],
        )
        source_ref = snapshot_artifact(
            self.root, "source", source_path.name, jsonl=True
        )
        label_path = self.root / "bound_label.jsonl"
        _write_jsonl(
            label_path,
            [
                {
                    "post_id": row.report.post_id,
                    "gold_label": row.gold_label,
                    "candidate_set_fingerprint": row.report.candidate_set_fingerprint,
                    "source_artifact_sha256": source_ref.sha256,
                }
                for row in rows
            ],
        )
        label_ref = snapshot_artifact(
            self.root, "label", label_path.name, jsonl=True
        )
        calibration_path = self.root / "bound_calibration.json"
        calibration_fingerprint = "c" * 64
        _write_json(
            calibration_path,
            {
                "calibration_fingerprint": calibration_fingerprint,
                "candidate_set_artifact_sha256": candidate_ref.sha256,
            },
        )
        calibration_ref = snapshot_artifact(
            self.root, "calibration", calibration_path.name
        )
        prediction_path = self.root / "bound_prediction.jsonl"
        _write_jsonl(
            prediction_path,
            [
                {
                    "post_id": row.report.post_id,
                    "candidate_set_fingerprint": row.report.candidate_set_fingerprint,
                    "source_artifact_sha256": source_ref.sha256,
                    "label_artifact_sha256": label_ref.sha256,
                    "calibration_artifact_sha256": calibration_ref.sha256,
                    "calibration_fingerprint": calibration_fingerprint,
                    "event_probabilities": [
                        item.to_dict() for item in row.report.event_probabilities
                    ],
                    "selected_label": row.report.selected_label,
                    "selected_probability": row.report.selected_probability,
                    "confidence_percentage": row.report.confidence_percentage,
                }
                for row in rows
            ],
        )
        prediction_ref = snapshot_artifact(
            self.root, "prediction", prediction_path.name, jsonl=True
        )
        refs = (
            candidate_ref,
            source_ref,
            label_ref,
            calibration_ref,
            prediction_ref,
        )
        return tuple(
            ConfidenceEvaluationRow(
                replace(row.report, evidence_artifacts=refs), row.gold_label
            )
            for row in rows
        )

    def test_uncalibrated_report_cannot_claim_a_percentage(self):
        value = self.report(
            evidence_mode="NO_EXTERNAL_EVIDENCE",
            probabilities=None,
            selected=None,
            action="ABSTAIN",
        )
        self.assertEqual("UNCALIBRATED", value.probability_status)
        self.assertIsNone(value.confidence_percentage)
        self.assertEqual("ABSTAIN", value.shadow_action)
        self.assertFalse(value.action_applied)

    def test_percentage_is_selected_probability_not_accuracy_and_rejects_strings(self):
        value = self.report()
        payload = value.to_dict()
        self.assertEqual(80.0, payload["confidence_percentage"])
        self.assertEqual("PER_ROW_CALIBRATED_PROBABILITY_NOT_ACCURACY", payload["percentage_semantics"])
        with self.assertRaisesRegex(ValueError, "confidence_percentage"):
            TypedConfidenceReport(**{**value.__dict__, "confidence_percentage": 50.0})
        with self.assertRaisesRegex(ValueError, "must be a number"):
            TypedConfidenceReport(**{**value.__dict__, "confidence_percentage": "80"})

    def test_from_candidate_set_binds_exact_event_eligible_labels_and_nil(self):
        candidate_set = self.candidate_set
        probabilities = (LabelProbability(self.work_id, 0.8), LabelProbability("__NIL__", 0.2))
        value = TypedConfidenceReport.from_candidate_set(
            candidate_set,
            post_id="1",
            event_probabilities=probabilities,
            probability_status="CALIBRATED_SHADOW",
            selected_label=self.work_id,
            selected_probability=0.8,
            confidence_percentage=80.0,
            shadow_action="SHADOW_SELECT",
            evidence_mode="SYNTHETIC_CONTRACT_ONLY",
        )
        self.assertEqual([self.work_id, "__NIL__"], [item.label for item in value.event_probabilities])
        with self.assertRaisesRegex(ValueError, "exactly match"):
            TypedConfidenceReport.from_candidate_set(
                candidate_set,
                post_id="1",
                event_probabilities=(LabelProbability("forged", 0.8), LabelProbability("__NIL__", 0.2)),
                probability_status="CALIBRATED_SHADOW",
                selected_label="forged",
                selected_probability=0.8,
                confidence_percentage=80.0,
                shadow_action="SHADOW_SELECT",
                evidence_mode="SYNTHETIC_CONTRACT_ONLY",
            )

    def test_unknown_and_truncated_producers_require_null_probabilities_and_abstain(self):
        for generation_status in ("UNKNOWN", "TRUNCATED"):
            safe = self.report(
                evidence_mode="NO_EXTERNAL_EVIDENCE",
                generation_status=generation_status,
                probabilities=None,
                selected=None,
                action="ABSTAIN",
            )
            self.assertEqual("UNCALIBRATED", safe.probability_status)
            with self.assertRaisesRegex(ValueError, "incomplete producer"):
                TypedConfidenceReport(
                    **{
                        **safe.__dict__,
                        "event_probabilities": (
                            LabelProbability(self.work_id, 0.8),
                            LabelProbability("__NIL__", 0.2),
                        ),
                        "probability_status": "CALIBRATED_SHADOW",
                        "selected_label": self.work_id,
                        "selected_probability": 0.8,
                        "confidence_percentage": 80.0,
                        "shadow_action": "SHADOW_SELECT",
                    }
                )

    def test_frozen_actual_requires_exact_refs_and_explicit_verified_root(self):
        with self.assertRaisesRegex(ValueError, "requires exact"):
            self.report(refs=())
        row = ConfidenceEvaluationRow(self.report(), self.work_id)
        no_root = read_policy_independent_metrics((row,))
        self.assertEqual("NOT_ESTIMABLE_ARTIFACT_ROOT_REQUIRED", no_root["status"])
        bound = self.bind_rows((row,))
        self.assertEqual(
            "ESTIMABLE",
            read_policy_independent_metrics(bound, artifact_root=self.root)["status"],
        )
        (self.root / "bound_prediction.jsonl").write_text(
            '{"tampered":true}\n', encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "snapshot mismatch"):
            read_policy_independent_metrics(bound, artifact_root=self.root)

    def test_bound_candidate_set_artifact_must_match_report_labels(self):
        _write_json(
            self.root / "candidate_set.json",
            {**self.candidate_set.to_dict(), "candidate_set_fingerprint": "a" * 64},
        )
        changed_refs = list(self.refs)
        changed_refs[0] = snapshot_artifact(self.root, "candidate_set", "candidate_set.json")
        row = ConfidenceEvaluationRow(self.report(refs=tuple(changed_refs)), self.work_id)
        with self.assertRaisesRegex(ValueError, "candidate_set artifact contract invalid"):
            read_policy_independent_metrics((row,), artifact_root=self.root)

    def test_current_refs_cannot_bind_unrelated_label_calibration_or_prediction(self):
        original = ConfidenceEvaluationRow(self.report(), self.work_id)

        bound = self.bind_rows((original,))[0]
        _write_jsonl(
            self.root / "bound_label.jsonl",
            [
                {
                    "post_id": bound.report.post_id,
                    "gold_label": "__NIL__",
                    "candidate_set_fingerprint": bound.report.candidate_set_fingerprint,
                    "source_artifact_sha256": bound.report.evidence_artifacts[1].sha256,
                }
            ],
        )
        refs = list(bound.report.evidence_artifacts)
        refs[2] = snapshot_artifact(
            self.root, "label", "bound_label.jsonl", jsonl=True
        )
        wrong_label = ConfidenceEvaluationRow(
            replace(bound.report, evidence_artifacts=tuple(refs)), bound.gold_label
        )
        with self.assertRaisesRegex(ValueError, "label artifact semantic binding mismatch"):
            read_policy_independent_metrics((wrong_label,), artifact_root=self.root)

        bound = self.bind_rows((original,))[0]
        _write_json(
            self.root / "bound_calibration.json",
            {
                "calibration_fingerprint": "d" * 64,
                "candidate_set_artifact_sha256": bound.report.evidence_artifacts[0].sha256,
            },
        )
        refs = list(bound.report.evidence_artifacts)
        refs[3] = snapshot_artifact(
            self.root, "calibration", "bound_calibration.json"
        )
        wrong_calibration = ConfidenceEvaluationRow(
            replace(bound.report, evidence_artifacts=tuple(refs)), bound.gold_label
        )
        with self.assertRaisesRegex(ValueError, "prediction artifact semantic binding mismatch"):
            read_policy_independent_metrics((wrong_calibration,), artifact_root=self.root)

        bound = self.bind_rows((original,))[0]
        prediction = json.loads(
            (self.root / "bound_prediction.jsonl").read_text(encoding="utf-8")
        )
        prediction["selected_probability"] = 0.1
        _write_jsonl(self.root / "bound_prediction.jsonl", [prediction])
        refs = list(bound.report.evidence_artifacts)
        refs[4] = snapshot_artifact(
            self.root, "prediction", "bound_prediction.jsonl", jsonl=True
        )
        wrong_prediction = ConfidenceEvaluationRow(
            replace(bound.report, evidence_artifacts=tuple(refs)), bound.gold_label
        )
        with self.assertRaisesRegex(ValueError, "prediction artifact semantic binding mismatch"):
            read_policy_independent_metrics((wrong_prediction,), artifact_root=self.root)

    def test_gold_outside_candidate_set_is_a_recall_miss(self):
        row = ConfidenceEvaluationRow(self.report(), "work-b")
        result = self.metrics((row,))
        self.assertEqual("ESTIMABLE", result["status"])
        self.assertEqual(0.0, result["metrics"]["candidate_set_recall"])
        self.assertEqual(0.0, result["metrics"]["top_label_accuracy"])
        self.assertEqual(1, result["metric_denominators"]["candidate_set_recall_non_nil_gold_rows"])
        self.assertTrue(math.isfinite(result["metrics"]["log_loss"]))

    def test_selected_label_must_be_deterministic_argmax(self):
        with self.assertRaisesRegex(ValueError, "deterministic argmax"):
            self.report(probabilities=(0.3, 0.7), selected=self.work_id)
        tie = self.report(probabilities=(0.5, 0.5), selected="__NIL__")
        self.assertEqual("__NIL__", tie.selected_label)

    def test_metrics_have_exact_meaning_without_policy_thresholds(self):
        rows = (
            ConfidenceEvaluationRow(self.report(post_id="1", probabilities=(0.8, 0.2)), self.work_id),
            ConfidenceEvaluationRow(self.report(post_id="2", probabilities=(0.7, 0.3)), "__NIL__"),
        )
        result = self.metrics(rows, ece_bins=2)
        self.assertEqual("NONE_DESCRIPTIVE_ONLY", result["reader_policy"])
        self.assertAlmostEqual(0.5, result["metrics"]["top_label_accuracy"])
        self.assertAlmostEqual(1.0, result["metrics"]["candidate_set_recall"])
        self.assertAlmostEqual(0.53, result["metrics"]["brier"])
        self.assertAlmostEqual((-math.log(0.8) - math.log(0.3)) / 2.0, result["metrics"]["log_loss"])
        self.assertAlmostEqual(0.25, result["metrics"]["ece"])
        self.assertAlmostEqual(0.5, result["metrics"]["selective_risk"])
        self.assertAlmostEqual(0.25, result["metrics"]["aurc"])
        self.assertAlmostEqual(1.0, result["metrics"]["coverage"])

    def test_calibrated_abstain_produces_nontrivial_coverage_and_selective_risk(self):
        rows = (
            ConfidenceEvaluationRow(self.report(post_id="1"), self.work_id),
            ConfidenceEvaluationRow(self.report(post_id="2", action="ABSTAIN"), "__NIL__"),
        )
        result = self.metrics(rows)
        self.assertEqual(0.5, result["metrics"]["coverage"])
        self.assertEqual(0.0, result["metrics"]["selective_risk"])
        self.assertEqual(1, result["metric_denominators"]["selective_covered_rows"])

    def test_aurc_ties_are_input_order_invariant(self):
        correct = ConfidenceEvaluationRow(self.report(post_id="a"), self.work_id)
        incorrect = ConfidenceEvaluationRow(self.report(post_id="b"), "__NIL__")
        forward = self.metrics((correct, incorrect))["metrics"]["aurc"]
        reverse = self.metrics((incorrect, correct))["metrics"]["aurc"]
        self.assertEqual(0.5, forward)
        self.assertEqual(forward, reverse)

    def test_nil_only_complete_dataset_is_estimable(self):
        row = ConfidenceEvaluationRow(
            self.report(probabilities=(0.2, 0.8), selected="__NIL__"),
            "__NIL__",
        )
        result = self.metrics((row,))
        self.assertEqual("ESTIMABLE", result["status"])
        self.assertIsNone(result["metrics"]["candidate_set_recall"])
        self.assertEqual(0, result["metric_denominators"]["candidate_set_recall_non_nil_gold_rows"])
        self.assertEqual(1.0, result["metrics"]["top_label_accuracy"])

    def test_source_less_contract_fixture_never_becomes_actual_metrics(self):
        rows = read_jsonl_rows(str(SOURCE_LESS_FIXTURE))
        result = read_policy_independent_metrics(rows)
        self.assertEqual("NOT_ESTIMABLE_NOT_FROZEN_ACTUAL", result["status"])
        self.assertTrue(all(value is None for value in result["metrics"].values()))

    def test_reader_rejects_duplicate_json_keys(self):
        duplicate = self.root / "duplicate.jsonl"
        duplicate.write_text('{"post_id":"1","post_id":"2"}\n', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            read_jsonl_rows(str(duplicate))

    def test_cli_source_less_fixture_is_no_write_and_not_estimable(self):
        before = SOURCE_LESS_FIXTURE.read_bytes()
        completed = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "tools" / "read_typed_confidence_metrics.py"),
                "--input",
                str(SOURCE_LESS_FIXTURE),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual("NOT_ESTIMABLE_NOT_FROZEN_ACTUAL", payload["status"])
        self.assertFalse(payload["runtime_started"])
        self.assertFalse(payload["writes_performed"])
        self.assertFalse(payload["public_result_interference"])
        self.assertEqual(before, SOURCE_LESS_FIXTURE.read_bytes())

    def test_cli_frozen_actual_rechecks_artifacts_without_writing(self):
        evaluation = self.root / "evaluation.jsonl"
        bound_row = self.bind_rows(
            (ConfidenceEvaluationRow(self.report(), self.work_id),)
        )[0]
        payload = bound_row.report.to_dict()
        payload["gold_label"] = bound_row.gold_label
        evaluation.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        tracked_paths = [
            evaluation,
            *(self.root / ref.relative_path for ref in bound_row.report.evidence_artifacts),
        ]
        before = {path: path.read_bytes() for path in tracked_paths}
        completed = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "tools" / "read_typed_confidence_metrics.py"),
                "--input",
                str(evaluation),
                "--artifact-root",
                str(self.root),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual("ESTIMABLE", result["status"])
        self.assertFalse(result["runtime_started"])
        self.assertFalse(result["writes_performed"])
        self.assertFalse(result["public_result_interference"])
        self.assertEqual(before, {path: path.read_bytes() for path in tracked_paths})


if __name__ == "__main__":
    unittest.main()
