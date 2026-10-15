from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.llm_batch.grounding.candidate_set_calibration_shadow import (
    CALIBRATED_BOUND_STATUS,
    CALIBRATION_POLICY_SCHEMA_V4,
    CALIBRATION_SHADOW_SCHEMA,
    CALIBRATION_UNAVAILABLE_SCHEMA,
    CalibrationArtifact,
    CalibrationEvaluationPolicy,
    CalibrationFitReceipt,
    CalibrationSplitAssignment,
    CalibrationSplitManifest,
    EventScoreVector,
    FrozenActualEvidenceReceipt,
    _actual_interval_gate_checks,
    _clopper_pearson_interval,
    build_calibration_shadow,
    calibration_shadow_from_dict,
    evaluate_frozen_holdout,
)
from src.llm_batch.grounding.candidate_set_shadow import (
    NIL_LABEL,
    PROBABILITY_STATUS,
    build_uncalibrated_selective_shadow,
)
from src.llm_batch.promotion_gate import (
    EvidenceRecord,
    GroundingState,
    RetrievalState,
    can_publish_title,
)
from src.llm_batch.grounding.calibration_actual_readback import build_readback_manifest, canonical_bytes, expected_universe_readback, prediction_payload_readback, producer_coverage_receipt, sha256_bytes, snapshot_artifact


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
SHA_E = "e" * 64
SHA_F = "f" * 64


def _canonical_hash(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class _FlipAfterFirstSnapshot(Mapping):
    def __init__(self, first, second):
        self._first = dict(first)
        self._second = dict(second)
        self._reads = 0

    def __iter__(self):
        return iter(self._first)

    def __len__(self):
        return len(self._first)

    def __getitem__(self, key):
        source = self._first if self._reads < len(self._first) else self._second
        self._reads += 1
        return source[key]


def _base_shadow(*, generation_status: str = "COMPLETE", retrieval_blocked: bool = False):
    state = GroundingState(
        post_id=101,
        candidate_title="작품 A",
        candidate_url="https://example.test/a",
        retrieval=(
            RetrievalState(required=True, attempted=True, recovered=False)
            if retrieval_blocked
            else None
        ),
    )
    evidence = [
        EvidenceRecord(
            kind="candidate_preservation",
            candidate_title="작품 A",
            candidate_url="https://example.test/a",
            supports_publish=True,
        )
    ]
    decision = can_publish_title(state, evidence)
    return build_uncalibrated_selective_shadow(
        state,
        evidence,
        decision,
        generation_status=generation_status,
    )


def _policy(**overrides):
    values = {
        "fixed_bin_edges": (0.0, 0.5, 1.0),
        "selector_max_error_probability": 0.40,
        "nil_min_probability": 0.60,
        "alpha": 0.05,
        "min_dev_rows": 2,
        "min_dev_per_truth_class": 1,
        "min_calibration_rows": 2,
        "min_calibration_per_truth_class": 1,
        "min_frozen_rows": 2,
        "min_per_truth_class": 1,
        "min_occupied_bin_rows": 1,
        "target_coverage": 0.50,
        "max_selective_risk_upper_bound": 1.0,
        "baseline_noninferiority_margin": 1.0,
        "min_candidate_recall_lower_bound": 0.0,
        "min_nil_prediction_count": 1,
        "min_nil_precision_lower_bound": 0.0,
        "min_nil_recall_lower_bound": 0.0,
        "paired_delta_ci_bounds": {
            "top_label_accuracy": -1.0,
            "brier": 2.0,
            "log_loss": 100.0,
            "ece": 1.0,
            "selective_risk": 1.0,
            "aurc": 1.0,
        },
        "policy_scope": "SYNTHETIC_CONTRACT_ONLY",
        "policy_origin": "PRE_REGISTERED_DEV_CALIBRATION",
    }
    values.update(overrides)
    return CalibrationEvaluationPolicy.create(**values)


def _split_manifest(candidate_label: str, candidate_set_fingerprint: str) -> CalibrationSplitManifest:
    def _binding(truth_kind: str, truth_label: str, split: str):
        split_fingerprint = {
            "DEV": SHA_D,
            "CALIBRATION": SHA_E,
            "FROZEN_HOLDOUT": candidate_set_fingerprint,
        }[split]
        return {
            "candidate_set_fingerprint": split_fingerprint,
            "gold_work_fingerprint": {
                "DEV": "1" * 64,
                "CALIBRATION": "2" * 64,
                "FROZEN_HOLDOUT": "3" * 64,
            }[split]
            if truth_kind == "CANDIDATE"
            else None,
            "binding_status": "UNIQUE" if truth_kind == "CANDIDATE" else "NOT_APPLICABLE",
            "matched_candidate_ids": (truth_label,) if truth_kind == "CANDIDATE" else (),
        }

    rows = (
        CalibrationSplitAssignment(
            example_id="dev-candidate",
            post_id="1",
            split_group_id="group-dev-candidate",
            content_fingerprint="1" * 64,
            source_group_fingerprint="2" * 64,
            split="DEV",
            truth_kind="CANDIDATE",
            truth_label="cand_dev",
            label_provenance_sha256=SHA_A,
            **_binding("CANDIDATE", "cand_dev", "DEV"),
        ),
        CalibrationSplitAssignment(
            example_id="dev-nil",
            post_id="2",
            split_group_id="group-dev-nil",
            content_fingerprint="3" * 64,
            source_group_fingerprint="4" * 64,
            split="DEV",
            truth_kind="NIL",
            truth_label=NIL_LABEL,
            label_provenance_sha256=SHA_A,
            **_binding("NIL", NIL_LABEL, "DEV"),
        ),
        CalibrationSplitAssignment(
            example_id="cal-candidate",
            post_id="3",
            split_group_id="group-cal-candidate",
            content_fingerprint="5" * 64,
            source_group_fingerprint="6" * 64,
            split="CALIBRATION",
            truth_kind="CANDIDATE",
            truth_label="cand_calibration",
            label_provenance_sha256=SHA_B,
            **_binding("CANDIDATE", "cand_calibration", "CALIBRATION"),
        ),
        CalibrationSplitAssignment(
            example_id="cal-nil",
            post_id="4",
            split_group_id="group-cal-nil",
            content_fingerprint="7" * 64,
            source_group_fingerprint="8" * 64,
            split="CALIBRATION",
            truth_kind="NIL",
            truth_label=NIL_LABEL,
            label_provenance_sha256=SHA_B,
            **_binding("NIL", NIL_LABEL, "CALIBRATION"),
        ),
        CalibrationSplitAssignment(
            example_id="frozen-candidate",
            post_id="5",
            split_group_id="group-frozen-candidate",
            content_fingerprint="9" * 64,
            source_group_fingerprint="0" * 64,
            split="FROZEN_HOLDOUT",
            truth_kind="CANDIDATE",
            truth_label=candidate_label,
            label_provenance_sha256=SHA_C,
            **_binding("CANDIDATE", candidate_label, "FROZEN_HOLDOUT"),
        ),
        CalibrationSplitAssignment(
            example_id="frozen-nil",
            post_id="6",
            split_group_id="group-frozen-nil",
            content_fingerprint="a" * 64,
            source_group_fingerprint="b" * 64,
            split="FROZEN_HOLDOUT",
            truth_kind="NIL",
            truth_label=NIL_LABEL,
            label_provenance_sha256=SHA_C,
            **_binding("NIL", NIL_LABEL, "FROZEN_HOLDOUT"),
        ),
    )
    return CalibrationSplitManifest.create(
        assignments=rows,
        source_label_ledger_sha256=SHA_D,
        assignment_seed_sha256=SHA_E,
    )


def _artifact(
    manifest,
    policy,
    *,
    temperature: float = 1.0,
    scorer_fingerprint: str = SHA_F,
):
    calibration_rows = [
        item for item in manifest.assignments if item.split == "CALIBRATION"
    ]
    fit_receipt = CalibrationFitReceipt.create(
        split_manifest_sha256=manifest.manifest_sha256,
        calibration_split_fingerprint=manifest.split_fingerprints["CALIBRATION"],
        scorer_fingerprint=scorer_fingerprint,
        fit_row_count=len(calibration_rows),
        candidate_truth_count=sum(item.truth_kind == "CANDIDATE" for item in calibration_rows),
        resolved_candidate_count=sum(
            item.truth_kind == "CANDIDATE" and item.binding_status == "UNIQUE"
            for item in calibration_rows
        ),
        unresolved_candidate_count=sum(
            item.truth_kind == "CANDIDATE" and item.binding_status != "UNIQUE"
            for item in calibration_rows
        ),
        nil_truth_count=sum(item.truth_kind == "NIL" for item in calibration_rows),
        unjudged_count=sum(item.truth_kind == "UNJUDGED" for item in calibration_rows),
        method="TEMPERATURE_SCALING",
        temperature=temperature,
    )
    return CalibrationArtifact.create(
        split_manifest_sha256=manifest.manifest_sha256,
        calibration_split_fingerprint=manifest.split_fingerprints["CALIBRATION"],
        frozen_holdout_fingerprint=manifest.split_fingerprints["FROZEN_HOLDOUT"],
        scorer_fingerprint=scorer_fingerprint,
        policy_sha256=policy.policy_sha256,
        method="TEMPERATURE_SCALING",
        temperature=temperature,
        fit_receipt=fit_receipt,
    )


def _score(base, artifact, *, example_id: str, post_id: str, raw_scores):
    return EventScoreVector.create(
        example_id=example_id,
        post_id=post_id,
        split="FROZEN_HOLDOUT",
        base_shadow=base,
        raw_scores=tuple(raw_scores),
        scorer_fingerprint=artifact.scorer_fingerprint,
        split_manifest_sha256=artifact.split_manifest_sha256,
        generation_proof_fingerprint=SHA_A,
        retrieval_state_fingerprint=SHA_B,
        feature_schema_version="candidate_probability_features_v1",
        feature_fingerprint=SHA_C,
    )


def _build_bound(base, score, artifact, policy, manifest):
    assignment = next(
        item for item in manifest.assignments if item.example_id == score.example_id
    )
    return build_calibration_shadow(
        base,
        score,
        artifact,
        policy,
        split_manifest=manifest,
        assignment=assignment,
    )


def _two_row_predictions(base, manifest, artifact, policy, *, candidate_scores, nil_scores):
    scores = {
        "frozen-candidate": _score(
            base,
            artifact,
            example_id="frozen-candidate",
            post_id="5",
            raw_scores=candidate_scores,
        ),
        "frozen-nil": _score(
            base,
            artifact,
            example_id="frozen-nil",
            post_id="6",
            raw_scores=nil_scores,
        ),
    }
    shadows = {
        example_id: _build_bound(base, score, artifact, policy, manifest)
        for example_id, score in scores.items()
    }
    bases = {example_id: base for example_id in scores}
    return bases, scores, shadows


class CandidateSetCalibrationShadowContractTests(unittest.TestCase):
    def test_actual_policy_v4_binds_interval_protocol(self):
        policy = _policy(
            policy_scope="FROZEN_ACTUAL_PRE_REGISTERED",
            min_candidate_recall_lower_bound=0.01,
            min_nil_precision_lower_bound=0.01,
            min_nil_recall_lower_bound=0.01,
        )
        payload = policy.to_dict()
        self.assertEqual(CALIBRATION_POLICY_SCHEMA_V4, payload["schema_version"])
        self.assertEqual(30, payload["min_bootstrap_groups"])
        self.assertEqual(2_000, payload["min_bootstrap_replicates"])
        self.assertEqual(
            "CLUSTER_BOOTSTRAP_PERCENTILE",
            payload["cluster_interval_method"],
        )
        for field_name, replacement in (
            ("top_label_accuracy_denominator", "NON_ABSTAIN_ROWS"),
            ("min_bootstrap_groups", 31),
            ("min_bootstrap_replicates", 2_001),
        ):
            forged = dict(payload)
            forged[field_name] = replacement
            with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
                CalibrationEvaluationPolicy(**forged)

        legacy_values = {
            key: value
            for key, value in payload.items()
            if key
            not in {
                "policy_sha256",
                "min_bootstrap_groups",
                "min_bootstrap_replicates",
                "cluster_interval_method",
            }
        }
        legacy_values["schema_version"] = "candidate_set_calibration_policy_v3"
        legacy = CalibrationEvaluationPolicy.create(**legacy_values)
        self.assertEqual("candidate_set_calibration_policy_v3", legacy.schema_version)

    def test_legacy_v2_v3_policy_hashes_remain_stable(self):
        synthetic_v2 = _policy()
        self.assertEqual(
            "9d8ade20391e693c47c591b14c0d9a22c5276846cd91a2438c48303326b1c1b3",
            synthetic_v2.policy_sha256,
        )
        self.assertEqual(
            synthetic_v2.to_dict(),
            CalibrationEvaluationPolicy(**synthetic_v2.to_dict()).to_dict(),
        )
        actual_v3 = _policy(
            policy_scope="FROZEN_ACTUAL_PRE_REGISTERED",
            schema_version="candidate_set_calibration_policy_v3",
            min_candidate_recall_lower_bound=0.01,
            min_nil_precision_lower_bound=0.01,
            min_nil_recall_lower_bound=0.01,
        )
        self.assertEqual(
            "e0fdd130deb7beb6e058fb0eceb6996727c621241f2087bb030d019e2dc8ed9a",
            actual_v3.policy_sha256,
        )
        self.assertEqual(
            actual_v3.to_dict(),
            CalibrationEvaluationPolicy(**actual_v3.to_dict()).to_dict(),
        )

    def test_complete_bound_shadow_uses_candidate_nil_simplex_without_public_effect(self):
        base = _base_shadow()
        candidate_label = base.event_probabilities[0].label
        policy = _policy()
        manifest = _split_manifest(candidate_label, base.candidate_set.candidate_set_fingerprint)
        artifact = _artifact(manifest, policy)
        score = _score(
            base,
            artifact,
            example_id="frozen-candidate",
            post_id="5",
            raw_scores=(3.0, 0.0),
        )

        shadow = _build_bound(base, score, artifact, policy, manifest)

        self.assertEqual(CALIBRATION_SHADOW_SCHEMA, shadow.schema_version)
        self.assertEqual(CALIBRATED_BOUND_STATUS, shadow.probability_status)
        self.assertEqual([candidate_label, NIL_LABEL], [item.label for item in shadow.event_probabilities])
        self.assertAlmostEqual(1.0, sum(item.probability for item in shadow.event_probabilities))
        self.assertEqual(candidate_label, shadow.selected_label)
        self.assertEqual("RESOLVE", shadow.action)
        self.assertFalse(shadow.action_applied)
        self.assertEqual("NONE_SHADOW_ONLY", shadow.operational_effect)
        self.assertEqual(shadow.to_dict(), calibration_shadow_from_dict(shadow.to_dict()).to_dict())

    def test_unknown_generation_fails_closed_with_all_null_probabilities(self):
        base = _base_shadow(generation_status="UNKNOWN")
        candidate_label = base.event_probabilities[0].label
        policy = _policy()
        manifest = _split_manifest(candidate_label, base.candidate_set.candidate_set_fingerprint)
        artifact = _artifact(manifest, policy)
        score = _score(base, artifact, example_id="frozen-candidate", post_id="5", raw_scores=(3.0, 0.0))

        shadow = build_calibration_shadow(base, score, artifact, policy)

        self.assertEqual(CALIBRATION_UNAVAILABLE_SCHEMA, shadow.schema_version)
        self.assertEqual(PROBABILITY_STATUS, shadow.probability_status)
        self.assertTrue(all(item.probability is None for item in shadow.event_probabilities))
        self.assertIsNone(shadow.selected_label)
        self.assertIn("candidate_set_generation_not_complete", shadow.reason_codes)

    def test_missing_artifact_never_creates_probabilities(self):
        base = _base_shadow()
        shadow = build_calibration_shadow(base, None, None, _policy())
        self.assertEqual(CALIBRATION_UNAVAILABLE_SCHEMA, shadow.schema_version)
        self.assertTrue(all(item.probability is None for item in shadow.event_probabilities))
        self.assertIn("calibration_artifact_missing", shadow.reason_codes)

    def test_score_label_or_fingerprint_mismatch_is_rejected(self):
        base = _base_shadow()
        candidate_label = base.event_probabilities[0].label
        policy = _policy()
        manifest = _split_manifest(candidate_label, base.candidate_set.candidate_set_fingerprint)
        artifact = _artifact(manifest, policy)
        score = _score(base, artifact, example_id="frozen-candidate", post_id="5", raw_scores=(3.0, 0.0))

        with self.assertRaisesRegex(ValueError, "labels do not match|labels must be unique"):
            build_calibration_shadow(
                base,
                replace(score, labels=tuple(reversed(score.labels))),
                artifact,
                policy,
                split_manifest=manifest,
                assignment=next(item for item in manifest.assignments if item.example_id == score.example_id),
            )
        with self.assertRaisesRegex(ValueError, "candidate-set fingerprint"):
            build_calibration_shadow(
                base,
                replace(score, candidate_set_fingerprint=SHA_A),
                artifact,
                policy,
                split_manifest=manifest,
                assignment=next(item for item in manifest.assignments if item.example_id == score.example_id),
            )

    def test_artifact_policy_or_split_binding_mismatch_is_rejected(self):
        base = _base_shadow()
        candidate_label = base.event_probabilities[0].label
        policy = _policy()
        manifest = _split_manifest(candidate_label, base.candidate_set.candidate_set_fingerprint)
        artifact = _artifact(manifest, policy)
        score = _score(base, artifact, example_id="frozen-candidate", post_id="5", raw_scores=(3.0, 0.0))

        with self.assertRaisesRegex(ValueError, "policy"):
            _build_bound(base, score, replace(artifact, policy_sha256=SHA_A), policy, manifest)
        with self.assertRaisesRegex(ValueError, "split manifest"):
            build_calibration_shadow(
                base,
                replace(score, split_manifest_sha256=SHA_A),
                artifact,
                policy,
                split_manifest=manifest,
                assignment=next(item for item in manifest.assignments if item.example_id == score.example_id),
            )

    def test_retrieval_failclose_remains_abstain_even_with_high_score(self):
        base = _base_shadow(retrieval_blocked=True)
        candidate_label = base.event_probabilities[0].label
        policy = _policy()
        manifest = _split_manifest(candidate_label, base.candidate_set.candidate_set_fingerprint)
        artifact = _artifact(manifest, policy)
        score = _score(base, artifact, example_id="frozen-candidate", post_id="5", raw_scores=(9.0, 0.0))

        shadow = _build_bound(base, score, artifact, policy, manifest)

        self.assertEqual("ABSTAIN", shadow.action)
        self.assertIn("retrieval_failclose_requires_abstain", shadow.reason_codes)

        bases, scores, shadows = _two_row_predictions(
            base,
            manifest,
            artifact,
            policy,
            candidate_scores=(9.0, 0.0),
            nil_scores=(0.0, 9.0),
        )
        report = evaluate_frozen_holdout(
            split_manifest=manifest,
            shadows=shadows,
            policy=policy,
            evidence_mode="SYNTHETIC_CONTRACT_ONLY",
            base_shadows=bases,
            score_vectors=scores,
            calibration_artifact=artifact,
        )
        self.assertEqual("NOT_EVALUABLE_RETRIEVAL_BLOCKED", report["status"])
        self.assertTrue(all(value is None for value in report["metrics"].values()))

    def test_split_manifest_rejects_group_or_content_leakage(self):
        base = _base_shadow()
        candidate_label = base.event_probabilities[0].label
        manifest = _split_manifest(candidate_label, base.candidate_set.candidate_set_fingerprint)
        rows = list(manifest.assignments)
        rows[4] = replace(rows[4], split_group_id=rows[0].split_group_id)
        with self.assertRaisesRegex(ValueError, "split-group leakage"):
            CalibrationSplitManifest.create(
                assignments=tuple(rows),
                source_label_ledger_sha256=SHA_D,
                assignment_seed_sha256=SHA_E,
            )
        rows = list(manifest.assignments)
        rows[4] = replace(rows[4], content_fingerprint=rows[0].content_fingerprint)
        with self.assertRaisesRegex(ValueError, "content leakage"):
            CalibrationSplitManifest.create(
                assignments=tuple(rows),
                source_label_ledger_sha256=SHA_D,
                assignment_seed_sha256=SHA_E,
            )
        rows = list(manifest.assignments)
        rows[4] = replace(
            rows[4],
            source_group_fingerprint=rows[0].source_group_fingerprint,
        )
        with self.assertRaisesRegex(ValueError, "source-group leakage"):
            CalibrationSplitManifest.create(
                assignments=tuple(rows),
                source_label_ledger_sha256=SHA_D,
                assignment_seed_sha256=SHA_E,
            )
        rows = list(manifest.assignments)
        rows[4] = replace(
            rows[4],
            candidate_set_fingerprint=rows[0].candidate_set_fingerprint,
        )
        with self.assertRaisesRegex(ValueError, "candidate-set leakage"):
            CalibrationSplitManifest.create(
                assignments=tuple(rows),
                source_label_ledger_sha256=SHA_D,
                assignment_seed_sha256=SHA_E,
            )
        rows = list(manifest.assignments)
        rows[4] = replace(
            rows[4],
            gold_work_fingerprint=rows[0].gold_work_fingerprint,
        )
        with self.assertRaisesRegex(ValueError, "candidate/work leakage"):
            CalibrationSplitManifest.create(
                assignments=tuple(rows),
                source_label_ledger_sha256=SHA_D,
                assignment_seed_sha256=SHA_E,
            )

    def test_synthetic_metric_contract_computes_but_never_allows_conversion(self):
        base = _base_shadow()
        candidate_label = base.event_probabilities[0].label
        policy = _policy()
        manifest = _split_manifest(candidate_label, base.candidate_set.candidate_set_fingerprint)
        artifact = _artifact(manifest, policy)
        bases, scores, after = _two_row_predictions(
            base,
            manifest,
            artifact,
            policy,
            candidate_scores=(3.0, 0.0),
            nil_scores=(0.0, 3.0),
        )

        report = evaluate_frozen_holdout(
            split_manifest=manifest,
            shadows=after,
            policy=policy,
            evidence_mode="SYNTHETIC_CONTRACT_ONLY",
            base_shadows=bases,
            score_vectors=scores,
            calibration_artifact=artifact,
        )

        self.assertEqual("GO_SYNTHETIC_METRIC_CONTRACT_ONLY", report["status"])
        self.assertEqual(1.0, report["candidate_set_recall"]["value"])
        self.assertEqual(1.0, report["metrics"]["top_label_accuracy"])
        self.assertLess(report["metrics"]["multiclass_brier"], 0.01)
        self.assertFalse(report["conversion_allowed"])
        self.assertEqual("SYNTHETIC_EVIDENCE_NEVER_DEPLOYMENT", report["conversion_reason"])

    def test_rehashed_shadow_and_score_tamper_cannot_bypass_source_replay(self):
        base = _base_shadow()
        candidate_label = base.event_probabilities[0].label
        policy = _policy()
        manifest = _split_manifest(candidate_label, base.candidate_set.candidate_set_fingerprint)
        artifact = _artifact(manifest, policy)
        bases, scores, shadows = _two_row_predictions(
            base,
            manifest,
            artifact,
            policy,
            candidate_scores=(3.0, 0.0),
            nil_scores=(0.0, 3.0),
        )

        action_forged = shadows["frozen-candidate"].to_dict()
        action_forged["action"] = "ASSERT_NIL"
        action_forged["shadow_fingerprint"] = _canonical_hash(
            {key: value for key, value in action_forged.items() if key != "shadow_fingerprint"}
        )
        with self.assertRaisesRegex(ValueError, "ASSERT_NIL"):
            calibration_shadow_from_dict(action_forged)

        mass_forged = shadows["frozen-candidate"].to_dict()
        mass_forged["event_probabilities"][0]["probability_mass"] -= 1
        mass_forged["event_probabilities"][1]["probability_mass"] += 1
        mass_forged["selected_error_probability_mass"] += 1
        mass_forged["shadow_fingerprint"] = _canonical_hash(
            {key: value for key, value in mass_forged.items() if key != "shadow_fingerprint"}
        )
        parsed_forgery = calibration_shadow_from_dict(mass_forged)
        forged_shadows = dict(shadows)
        forged_shadows["frozen-candidate"] = parsed_forgery
        report = evaluate_frozen_holdout(
            split_manifest=manifest,
            shadows=forged_shadows,
            policy=policy,
            evidence_mode="SYNTHETIC_CONTRACT_ONLY",
            base_shadows=bases,
            score_vectors=scores,
            calibration_artifact=artifact,
        )
        self.assertEqual("NOT_EVALUABLE_SOURCE_BINDING_INVALID", report["status"])
        self.assertTrue(all(value is None for value in report["metrics"].values()))

        score_payload = scores["frozen-candidate"].payload_without_score_vector_sha256()
        score_payload["publication_input_fingerprint"] = SHA_D
        forged_score = EventScoreVector(
            **score_payload,
            score_vector_sha256=_canonical_hash(score_payload),
        )
        with self.assertRaisesRegex(ValueError, "publication-input fingerprint"):
            _build_bound(base, forged_score, artifact, policy, manifest)

    def test_time_varying_mapping_is_snapshotted_before_source_replay(self):
        base = _base_shadow()
        candidate_label = base.event_probabilities[0].label
        policy = _policy()
        manifest = _split_manifest(candidate_label, base.candidate_set.candidate_set_fingerprint)
        artifact = _artifact(manifest, policy)
        bases, wrong_scores, wrong_shadows = _two_row_predictions(
            base,
            manifest,
            artifact,
            policy,
            candidate_scores=(0.0, 3.0),
            nil_scores=(3.0, 0.0),
        )
        _, _, correct_shadows = _two_row_predictions(
            base,
            manifest,
            artifact,
            policy,
            candidate_scores=(3.0, 0.0),
            nil_scores=(0.0, 3.0),
        )
        report = evaluate_frozen_holdout(
            split_manifest=manifest,
            shadows=_FlipAfterFirstSnapshot(wrong_shadows, correct_shadows),
            policy=policy,
            evidence_mode="SYNTHETIC_CONTRACT_ONLY",
            base_shadows=bases,
            score_vectors=wrong_scores,
            calibration_artifact=artifact,
        )
        self.assertEqual("GO_SYNTHETIC_METRIC_CONTRACT_ONLY", report["status"])
        self.assertEqual(0.0, report["metrics"]["top_label_accuracy"])

        blocked_base = _base_shadow(retrieval_blocked=True)
        blocked_manifest = _split_manifest(
            blocked_base.event_probabilities[0].label,
            blocked_base.candidate_set.candidate_set_fingerprint,
        )
        blocked_artifact = _artifact(blocked_manifest, policy)
        blocked_bases, blocked_scores, blocked_shadows = _two_row_predictions(
            blocked_base,
            blocked_manifest,
            blocked_artifact,
            policy,
            candidate_scores=(3.0, 0.0),
            nil_scores=(0.0, 3.0),
        )
        report = evaluate_frozen_holdout(
            split_manifest=blocked_manifest,
            shadows=_FlipAfterFirstSnapshot(blocked_shadows, correct_shadows),
            policy=policy,
            evidence_mode="SYNTHETIC_CONTRACT_ONLY",
            base_shadows=blocked_bases,
            score_vectors=blocked_scores,
            calibration_artifact=blocked_artifact,
        )
        self.assertEqual("NOT_EVALUABLE_RETRIEVAL_BLOCKED", report["status"])
        self.assertTrue(all(value is None for value in report["metrics"].values()))

    def test_clopper_pearson_and_policy_boundaries_are_explicit(self):
        self.assertEqual((None, None), _clopper_pearson_interval(0, 0, 0.05))
        lower, upper = _clopper_pearson_interval(0, 10, 0.05)
        self.assertEqual(0.0, lower)
        self.assertAlmostEqual(0.3084971078187607, upper, places=12)
        lower, upper = _clopper_pearson_interval(10, 10, 0.05, one_sided=True)
        self.assertAlmostEqual(0.7411344491069476, lower, places=12)
        self.assertEqual(1.0, upper)
        lower, upper = _clopper_pearson_interval(5, 10, 0.05)
        self.assertAlmostEqual(0.18708602844739863, lower, places=12)
        self.assertAlmostEqual(0.8129139715526013, upper, places=12)
        with self.assertRaisesRegex(ValueError, "target_coverage"):
            _policy(target_coverage=0.0)

    def test_actual_interval_gate_uses_paired_selective_risk_upper_bound(self):
        policy = _policy(
            baseline_noninferiority_margin=0.05,
            paired_delta_ci_bounds={
                "top_label_accuracy": -1.0,
                "brier": 2.0,
                "log_loss": 100.0,
                "ece": 1.0,
                "selective_risk": 0.05,
                "aurc": 1.0,
            },
        )
        def bootstrap(selective_upper):
            paired = {
                metric: {
                    "lower": 0.0,
                    "upper": 0.0,
                    "estimable": True,
                }
                for metric in policy.paired_delta_ci_bounds
            }
            paired["selective_risk"]["upper"] = selective_upper
            return {"paired_deltas": paired}

        passed = _actual_interval_gate_checks(bootstrap(0.05), policy)
        failed = _actual_interval_gate_checks(bootstrap(0.051), policy)
        missing = _actual_interval_gate_checks({"paired_deltas": {}}, policy)
        self.assertTrue(all(passed.values()))
        self.assertFalse(failed["paired_selective_risk_upper_bound"])
        self.assertFalse(any(missing.values()))

    def test_dev_unresolved_labels_cannot_satisfy_fit_minimum(self):
        base = _base_shadow()
        candidate_label = base.event_probabilities[0].label
        policy = _policy()
        manifest = _split_manifest(candidate_label, base.candidate_set.candidate_set_fingerprint)
        rows = list(manifest.assignments)
        rows[0] = replace(
            rows[0],
            truth_label=None,
            binding_status="MISSING",
            matched_candidate_ids=(),
        )
        unresolved_manifest = CalibrationSplitManifest.create(
            assignments=tuple(rows),
            source_label_ledger_sha256=SHA_D,
            assignment_seed_sha256=SHA_E,
        )
        artifact = _artifact(unresolved_manifest, policy)
        with self.assertRaisesRegex(ValueError, "DEV policy split"):
            artifact.validate_against(unresolved_manifest, policy)

    def test_frozen_actual_requires_bound_baseline_and_never_claims_conversion_without_full_ci(self):
        base = _base_shadow()
        candidate_label = base.event_probabilities[0].label
        policy = _policy(
            policy_scope="FROZEN_ACTUAL_PRE_REGISTERED",
            min_candidate_recall_lower_bound=0.01,
            min_nil_precision_lower_bound=0.01,
            min_nil_recall_lower_bound=0.01,
        )
        manifest = _split_manifest(candidate_label, base.candidate_set.candidate_set_fingerprint)
        artifact = _artifact(manifest, policy)
        baseline_artifact = _artifact(
            manifest,
            policy,
            scorer_fingerprint="9" * 64,
        )
        bases, scores, after = _two_row_predictions(
            base,
            manifest,
            artifact,
            policy,
            candidate_scores=(3.0, 0.0),
            nil_scores=(0.0, 3.0),
        )
        baseline_bases, baseline_scores, baseline = _two_row_predictions(
            base,
            manifest,
            baseline_artifact,
            policy,
            candidate_scores=(1.0, 0.0),
            nil_scores=(0.0, 1.0),
        )
        expected = [{"example_id": item.example_id, "post_id": item.post_id} for item in manifest.assignments if item.split == "FROZEN_HOLDOUT"]
        producer_rows = []
        prediction_rows = []
        for item in manifest.assignments:
            if item.split != "FROZEN_HOLDOUT":
                continue
            shadow = after[item.example_id]
            source_sha = "8" * 64
            producer_rows.append({**{"example_id": item.example_id, "post_id": item.post_id}, "generation_status": "COMPLETE", "candidate_set_fingerprint": shadow.candidate_set_fingerprint, "generation_proof_fingerprint": shadow.generation_proof_fingerprint, "source_digest_sha256": source_sha})
            prediction_rows.append({"example_id": item.example_id, "post_id": item.post_id, "group": item.split_group_id, "probabilities": {p.label: p.probability_mass for p in shadow.event_probabilities}, "shadow_fingerprint": shadow.shadow_fingerprint, "score_vector_sha256": shadow.score_vector_sha256, "candidate_set_fingerprint": shadow.candidate_set_fingerprint, "generation_proof_fingerprint": shadow.generation_proof_fingerprint, "source_digest_sha256": source_sha})
        baseline_rows = []
        for item in manifest.assignments:
            if item.split == "FROZEN_HOLDOUT":
                shadow = baseline[item.example_id]
                baseline_rows.append({"example_id": item.example_id, "post_id": item.post_id, "group": item.split_group_id, "probabilities": {p.label: p.probability_mass for p in shadow.event_probabilities}, "shadow_fingerprint": shadow.shadow_fingerprint, "score_vector_sha256": shadow.score_vector_sha256, "candidate_set_fingerprint": shadow.candidate_set_fingerprint, "generation_proof_fingerprint": shadow.generation_proof_fingerprint, "source_digest_sha256": "8" * 64})
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); root = Path(temp.name)
        for name, rows in (("expected", expected), ("producer", producer_rows), ("prediction", prediction_rows), ("baseline", baseline_rows)):
            (root / f"{name}.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
        refs = {
            "expected_universe": snapshot_artifact(root, "expected_universe", "expected.jsonl", jsonl=True),
            "prediction": snapshot_artifact(root, "prediction", "prediction.jsonl", jsonl=True),
            "baseline_prediction": snapshot_artifact(root, "baseline_prediction", "baseline.jsonl", jsonl=True),
            "producer": snapshot_artifact(root, "producer", "producer.jsonl", jsonl=True),
        }
        readback = build_readback_manifest(
            run_spec_sha256=SHA_A,
            artifacts=refs,
            expected_universe=expected_universe_readback(expected),
            producer_coverage=producer_coverage_receipt(expected, producer_rows),
            prediction=prediction_payload_readback(expected, prediction_rows),
            baseline_prediction=prediction_payload_readback(expected, baseline_rows),
            source_digest_sha256="8" * 64,
            metric_protocol_sha256=policy.policy_sha256,
            bootstrap_seed=7,
            bootstrap_replicates=100,
        )
        receipt = FrozenActualEvidenceReceipt.create(
            run_spec_sha256=SHA_A,
            split_manifest_sha256=manifest.manifest_sha256,
            source_label_ledger_sha256=manifest.source_label_ledger_sha256,
            expected_universe_artifact_sha256=refs["expected_universe"].sha256,
            prediction_artifact_sha256=refs["prediction"].sha256,
            baseline_prediction_artifact_sha256=refs["baseline_prediction"].sha256,
            producer_receipt_artifact_sha256=refs["producer"].sha256,
            readback_manifest_sha256=readback["manifest_sha256"],
            evaluation_plan_sha256=readback["evaluation_plan_sha256"],
            calibrator_fit_receipt_sha256=artifact.calibrator_fit_receipt_sha256,
            baseline_calibrator_fit_receipt_sha256=baseline_artifact.calibrator_fit_receipt_sha256,
            generation_proof_set_sha256=_canonical_hash(
                sorted(score.generation_proof_fingerprint for score in scores.values())
            ),
            metric_protocol_sha256=policy.policy_sha256,
        )

        report = evaluate_frozen_holdout(
            split_manifest=manifest,
            shadows=after,
            base_shadows=bases,
            score_vectors=scores,
            calibration_artifact=artifact,
            baseline_shadows=baseline,
            baseline_base_shadows=baseline_bases,
            baseline_score_vectors=baseline_scores,
            baseline_calibration_artifact=baseline_artifact,
            policy=policy,
            evidence_mode="FROZEN_ACTUAL",
            actual_evidence_receipt=receipt,
            prediction_artifact_sha256=refs["prediction"].sha256,
            baseline_prediction_artifact_sha256=refs["baseline_prediction"].sha256,
            run_spec_sha256=SHA_A,
            producer_receipt_artifact_sha256=refs["producer"].sha256,
            actual_readback_manifest=readback,
            actual_readback_root=str(root),
            actual_bootstrap_seed=7,
            actual_bootstrap_replicates=100,
        )
        self.assertEqual("NOT_ESTIMABLE_ACTUAL_INTERVAL_PROTOCOL", report["status"])
        self.assertIn("at least 2000 integer bootstrap replicates", report["reason"])
        self.assertFalse(report["conversion_allowed"])
        repeated = evaluate_frozen_holdout(
            split_manifest=manifest, shadows=after, base_shadows=bases, score_vectors=scores,
            calibration_artifact=artifact, baseline_shadows=baseline,
            baseline_base_shadows=baseline_bases, baseline_score_vectors=baseline_scores,
            baseline_calibration_artifact=baseline_artifact, policy=policy,
            evidence_mode="FROZEN_ACTUAL", actual_evidence_receipt=receipt,
            prediction_artifact_sha256=refs["prediction"].sha256, baseline_prediction_artifact_sha256=refs["baseline_prediction"].sha256,
            run_spec_sha256=SHA_A, producer_receipt_artifact_sha256=refs["producer"].sha256,
            actual_readback_manifest=readback, actual_bootstrap_seed=7,
            actual_bootstrap_replicates=100, actual_readback_root=str(root),
        )
        self.assertEqual(report, repeated)
        missing = evaluate_frozen_holdout(
            split_manifest=manifest, shadows=after, base_shadows=bases, score_vectors=scores,
            calibration_artifact=artifact, policy=policy, evidence_mode="FROZEN_ACTUAL",
            actual_evidence_receipt=receipt, prediction_artifact_sha256=refs["prediction"].sha256,
            baseline_prediction_artifact_sha256=refs["baseline_prediction"].sha256, run_spec_sha256=SHA_A,
            producer_receipt_artifact_sha256=refs["producer"].sha256,
        )
        self.assertTrue(missing["status"].startswith("NOT_ESTIMABLE"))
        forged = json.loads(json.dumps(readback))
        forged["prediction"]["per_row"][0]["candidate_set_fingerprint"] = "7" * 64
        forged["prediction"]["payload_sha256"] = sha256_bytes(canonical_bytes(forged["prediction"]["per_row"]))
        forged["manifest_sha256"] = sha256_bytes(canonical_bytes({k: v for k, v in forged.items() if k != "manifest_sha256"}))
        forged_report = evaluate_frozen_holdout(
            split_manifest=manifest, shadows=after, base_shadows=bases, score_vectors=scores,
            calibration_artifact=artifact, baseline_shadows=baseline,
            baseline_base_shadows=baseline_bases, baseline_score_vectors=baseline_scores,
            baseline_calibration_artifact=baseline_artifact, policy=policy,
            evidence_mode="FROZEN_ACTUAL", actual_evidence_receipt=receipt,
            prediction_artifact_sha256=refs["prediction"].sha256, baseline_prediction_artifact_sha256=refs["baseline_prediction"].sha256,
            run_spec_sha256=SHA_A, producer_receipt_artifact_sha256=refs["producer"].sha256,
            actual_readback_manifest=forged, actual_bootstrap_seed=7,
            actual_bootstrap_replicates=100, actual_readback_root=str(root),
        )
        self.assertEqual("NOT_ESTIMABLE_ACTUAL_READBACK_INVALID", forged_report["status"])
        wrong_rows = json.loads(json.dumps(prediction_rows))
        wrong_rows[0]["shadow_fingerprint"] = "6" * 64
        (root / "prediction.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in wrong_rows) + "\n", encoding="utf-8")
        wrong_refs = dict(refs); wrong_refs["prediction"] = snapshot_artifact(root, "prediction", "prediction.jsonl", jsonl=True)
        wrong_readback = build_readback_manifest(
            run_spec_sha256=SHA_A,
            artifacts=wrong_refs,
            expected_universe=expected_universe_readback(expected),
            producer_coverage=producer_coverage_receipt(expected, producer_rows),
            prediction=prediction_payload_readback(expected, wrong_rows),
            baseline_prediction=prediction_payload_readback(expected, baseline_rows),
            source_digest_sha256="8" * 64,
            metric_protocol_sha256=policy.policy_sha256,
            bootstrap_seed=7,
            bootstrap_replicates=100,
        )
        wrong_receipt_payload = receipt.payload_without_receipt_sha256()
        wrong_receipt_payload["prediction_artifact_sha256"] = wrong_refs["prediction"].sha256
        wrong_receipt_payload["readback_manifest_sha256"] = wrong_readback["manifest_sha256"]
        wrong_receipt_payload["evaluation_plan_sha256"] = wrong_readback["evaluation_plan_sha256"]
        wrong_receipt = FrozenActualEvidenceReceipt.create(**wrong_receipt_payload)
        wrong_report = evaluate_frozen_holdout(
            split_manifest=manifest, shadows=after, base_shadows=bases, score_vectors=scores,
            calibration_artifact=artifact, baseline_shadows=baseline,
            baseline_base_shadows=baseline_bases, baseline_score_vectors=baseline_scores,
            baseline_calibration_artifact=baseline_artifact, policy=policy,
            evidence_mode="FROZEN_ACTUAL", actual_evidence_receipt=wrong_receipt,
            prediction_artifact_sha256=wrong_refs["prediction"].sha256,
            baseline_prediction_artifact_sha256=refs["baseline_prediction"].sha256,
            run_spec_sha256=SHA_A, producer_receipt_artifact_sha256=refs["producer"].sha256,
            actual_readback_manifest=wrong_readback, actual_readback_root=str(root),
            actual_bootstrap_seed=7, actual_bootstrap_replicates=100,
        )
        self.assertEqual("NOT_ESTIMABLE_ACTUAL_READBACK_INVALID", wrong_report["status"])

        (root / "prediction.jsonl").write_text(
            "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in prediction_rows) + "\n",
            encoding="utf-8",
        )
        wrong_baseline_rows = json.loads(json.dumps(baseline_rows))
        wrong_baseline_rows[0]["shadow_fingerprint"] = "5" * 64
        (root / "baseline.jsonl").write_text(
            "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in wrong_baseline_rows) + "\n",
            encoding="utf-8",
        )
        wrong_baseline_refs = dict(refs)
        wrong_baseline_refs["prediction"] = snapshot_artifact(root, "prediction", "prediction.jsonl", jsonl=True)
        wrong_baseline_refs["baseline_prediction"] = snapshot_artifact(root, "baseline_prediction", "baseline.jsonl", jsonl=True)
        wrong_baseline_readback = build_readback_manifest(
            run_spec_sha256=SHA_A,
            artifacts=wrong_baseline_refs,
            expected_universe=expected_universe_readback(expected),
            producer_coverage=producer_coverage_receipt(expected, producer_rows),
            prediction=prediction_payload_readback(expected, prediction_rows),
            baseline_prediction=prediction_payload_readback(expected, wrong_baseline_rows),
            source_digest_sha256="8" * 64,
            metric_protocol_sha256=policy.policy_sha256,
            bootstrap_seed=7,
            bootstrap_replicates=100,
        )
        wrong_baseline_receipt_payload = receipt.payload_without_receipt_sha256()
        wrong_baseline_receipt_payload["baseline_prediction_artifact_sha256"] = wrong_baseline_refs["baseline_prediction"].sha256
        wrong_baseline_receipt_payload["readback_manifest_sha256"] = wrong_baseline_readback["manifest_sha256"]
        wrong_baseline_receipt_payload["evaluation_plan_sha256"] = wrong_baseline_readback["evaluation_plan_sha256"]
        wrong_baseline_receipt = FrozenActualEvidenceReceipt.create(**wrong_baseline_receipt_payload)
        wrong_baseline_report = evaluate_frozen_holdout(
            split_manifest=manifest, shadows=after, base_shadows=bases, score_vectors=scores,
            calibration_artifact=artifact, baseline_shadows=baseline,
            baseline_base_shadows=baseline_bases, baseline_score_vectors=baseline_scores,
            baseline_calibration_artifact=baseline_artifact, policy=policy,
            evidence_mode="FROZEN_ACTUAL", actual_evidence_receipt=wrong_baseline_receipt,
            prediction_artifact_sha256=wrong_baseline_refs["prediction"].sha256,
            baseline_prediction_artifact_sha256=wrong_baseline_refs["baseline_prediction"].sha256,
            run_spec_sha256=SHA_A, producer_receipt_artifact_sha256=refs["producer"].sha256,
            actual_readback_manifest=wrong_baseline_readback, actual_readback_root=str(root),
            actual_bootstrap_seed=7, actual_bootstrap_replicates=100,
        )
        self.assertEqual("NOT_ESTIMABLE_ACTUAL_READBACK_INVALID", wrong_baseline_report["status"])

    def test_frozen_actual_v4_success_keeps_selected_point_ci_and_paired_gates_aligned(self):
        base = _base_shadow()
        candidate_label = base.event_probabilities[0].label
        for denominator in ("ALL_FROZEN_ROWS", "NON_ABSTAIN_ROWS"):
            with self.subTest(denominator=denominator), tempfile.TemporaryDirectory() as directory:
                policy = _policy(
                    policy_scope="FROZEN_ACTUAL_PRE_REGISTERED",
                    top_label_accuracy_denominator=denominator,
                    min_candidate_recall_lower_bound=0.01,
                    min_nil_precision_lower_bound=0.01,
                    min_nil_recall_lower_bound=0.01,
                )
                seed_manifest = _split_manifest(
                    candidate_label,
                    base.candidate_set.candidate_set_fingerprint,
                )
                assignments = [
                    item
                    for item in seed_manifest.assignments
                    if item.split != "FROZEN_HOLDOUT"
                ]
                for index in range(30):
                    truth_kind = "CANDIDATE" if index % 2 == 0 else "NIL"
                    truth_label = candidate_label if truth_kind == "CANDIDATE" else NIL_LABEL
                    assignments.append(
                        CalibrationSplitAssignment(
                            example_id=f"actual-{index:02d}",
                            post_id=str(1_000 + index),
                            split_group_id=f"independent-group-{index:02d}",
                            content_fingerprint=_canonical_hash({"content": index}),
                            source_group_fingerprint=_canonical_hash({"source": index}),
                            split="FROZEN_HOLDOUT",
                            truth_kind=truth_kind,
                            truth_label=truth_label,
                            label_provenance_sha256=SHA_C,
                            candidate_set_fingerprint=base.candidate_set.candidate_set_fingerprint,
                            gold_work_fingerprint=("3" * 64 if truth_kind == "CANDIDATE" else None),
                            binding_status=("UNIQUE" if truth_kind == "CANDIDATE" else "NOT_APPLICABLE"),
                            matched_candidate_ids=((candidate_label,) if truth_kind == "CANDIDATE" else ()),
                        )
                    )
                manifest = CalibrationSplitManifest.create(
                    assignments=tuple(assignments),
                    source_label_ledger_sha256=SHA_D,
                    assignment_seed_sha256=SHA_E,
                )
                artifact = _artifact(manifest, policy)
                baseline_artifact = _artifact(
                    manifest,
                    policy,
                    scorer_fingerprint="9" * 64,
                )
                frozen = [
                    item for item in manifest.assignments if item.split == "FROZEN_HOLDOUT"
                ]
                bases = {}
                scores = {}
                after = {}
                baseline_bases = {}
                baseline_scores = {}
                baseline = {}
                for index, assignment in enumerate(frozen):
                    abstain = index >= 20
                    if abstain:
                        raw_scores = (0.0, 0.0)
                    elif assignment.truth_kind == "CANDIDATE":
                        raw_scores = (3.0, 0.0)
                    else:
                        raw_scores = (0.0, 3.0)
                    score = _score(
                        base,
                        artifact,
                        example_id=assignment.example_id,
                        post_id=assignment.post_id,
                        raw_scores=raw_scores,
                    )
                    baseline_score = _score(
                        base,
                        baseline_artifact,
                        example_id=assignment.example_id,
                        post_id=assignment.post_id,
                        raw_scores=raw_scores,
                    )
                    bases[assignment.example_id] = base
                    scores[assignment.example_id] = score
                    after[assignment.example_id] = _build_bound(
                        base, score, artifact, policy, manifest
                    )
                    baseline_bases[assignment.example_id] = base
                    baseline_scores[assignment.example_id] = baseline_score
                    baseline[assignment.example_id] = _build_bound(
                        base, baseline_score, baseline_artifact, policy, manifest
                    )

                root = Path(directory)
                expected = [
                    {"example_id": item.example_id, "post_id": item.post_id}
                    for item in frozen
                ]
                producer_rows = []
                prediction_rows = []
                baseline_rows = []
                for item in frozen:
                    shadow = after[item.example_id]
                    before_shadow = baseline[item.example_id]
                    source_sha = "8" * 64
                    producer_rows.append(
                        {
                            "example_id": item.example_id,
                            "post_id": item.post_id,
                            "generation_status": "COMPLETE",
                            "candidate_set_fingerprint": shadow.candidate_set_fingerprint,
                            "generation_proof_fingerprint": shadow.generation_proof_fingerprint,
                            "source_digest_sha256": source_sha,
                        }
                    )
                    for target, value in (
                        (prediction_rows, shadow),
                        (baseline_rows, before_shadow),
                    ):
                        target.append(
                            {
                                "example_id": item.example_id,
                                "post_id": item.post_id,
                                "group": item.split_group_id,
                                "probabilities": {
                                    probability.label: probability.probability_mass
                                    for probability in value.event_probabilities
                                },
                                "shadow_fingerprint": value.shadow_fingerprint,
                                "score_vector_sha256": value.score_vector_sha256,
                                "candidate_set_fingerprint": value.candidate_set_fingerprint,
                                "generation_proof_fingerprint": value.generation_proof_fingerprint,
                                "source_digest_sha256": source_sha,
                            }
                        )
                for name, rows in (
                    ("expected", expected),
                    ("producer", producer_rows),
                    ("prediction", prediction_rows),
                    ("baseline", baseline_rows),
                ):
                    (root / f"{name}.jsonl").write_text(
                        "\n".join(
                            json.dumps(row, ensure_ascii=False, sort_keys=True)
                            for row in rows
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                refs = {
                    "expected_universe": snapshot_artifact(
                        root, "expected_universe", "expected.jsonl", jsonl=True
                    ),
                    "producer": snapshot_artifact(
                        root, "producer", "producer.jsonl", jsonl=True
                    ),
                    "prediction": snapshot_artifact(
                        root, "prediction", "prediction.jsonl", jsonl=True
                    ),
                    "baseline_prediction": snapshot_artifact(
                        root, "baseline_prediction", "baseline.jsonl", jsonl=True
                    ),
                }
                readback = build_readback_manifest(
                    run_spec_sha256=SHA_A,
                    artifacts=refs,
                    expected_universe=expected_universe_readback(expected),
                    producer_coverage=producer_coverage_receipt(expected, producer_rows),
                    prediction=prediction_payload_readback(expected, prediction_rows),
                    baseline_prediction=prediction_payload_readback(expected, baseline_rows),
                    source_digest_sha256="8" * 64,
                    metric_protocol_sha256=policy.policy_sha256,
                    bootstrap_seed=7,
                    bootstrap_replicates=2_000,
                )
                receipt = FrozenActualEvidenceReceipt.create(
                    run_spec_sha256=SHA_A,
                    split_manifest_sha256=manifest.manifest_sha256,
                    source_label_ledger_sha256=manifest.source_label_ledger_sha256,
                    expected_universe_artifact_sha256=refs["expected_universe"].sha256,
                    prediction_artifact_sha256=refs["prediction"].sha256,
                    baseline_prediction_artifact_sha256=refs["baseline_prediction"].sha256,
                    producer_receipt_artifact_sha256=refs["producer"].sha256,
                    readback_manifest_sha256=readback["manifest_sha256"],
                    evaluation_plan_sha256=readback["evaluation_plan_sha256"],
                    calibrator_fit_receipt_sha256=artifact.calibrator_fit_receipt_sha256,
                    baseline_calibrator_fit_receipt_sha256=baseline_artifact.calibrator_fit_receipt_sha256,
                    generation_proof_set_sha256=_canonical_hash(
                        sorted(
                            score.generation_proof_fingerprint
                            for score in scores.values()
                        )
                    ),
                    metric_protocol_sha256=policy.policy_sha256,
                )
                report = evaluate_frozen_holdout(
                    split_manifest=manifest,
                    shadows=after,
                    base_shadows=bases,
                    score_vectors=scores,
                    calibration_artifact=artifact,
                    baseline_shadows=baseline,
                    baseline_base_shadows=baseline_bases,
                    baseline_score_vectors=baseline_scores,
                    baseline_calibration_artifact=baseline_artifact,
                    policy=policy,
                    evidence_mode="FROZEN_ACTUAL",
                    actual_evidence_receipt=receipt,
                    prediction_artifact_sha256=refs["prediction"].sha256,
                    baseline_prediction_artifact_sha256=refs["baseline_prediction"].sha256,
                    run_spec_sha256=SHA_A,
                    producer_receipt_artifact_sha256=refs["producer"].sha256,
                    actual_readback_manifest=readback,
                    actual_readback_root=str(root),
                    actual_bootstrap_seed=7,
                    actual_bootstrap_replicates=2_000,
                )
                self.assertEqual("GO_FROZEN_ACTUAL_SHADOW_ONLY", report["status"])
                self.assertTrue(report["interval_metric_checks_passed"])
                self.assertFalse(report["conversion_allowed"])
                selected = report["top_label_accuracy_receipt"]
                dual = report["top_label_accuracy_receipts"][denominator]
                self.assertEqual(denominator, selected["denominator_policy"])
                self.assertEqual(report["metrics"]["top_label_accuracy"], selected["value"])
                self.assertEqual(
                    report["cluster_bootstrap"]["point_estimate"]["top_label_accuracy"],
                    selected["value"],
                )
                self.assertEqual(selected["cluster_ci"], dual["cluster_ci"])
                self.assertEqual(policy.policy_sha256, dual["interval_protocol"]["policy_sha256"])
                self.assertEqual(
                    {
                        "top_label_accuracy",
                        "brier",
                        "log_loss",
                        "ece",
                        "selective_risk",
                        "aurc",
                    },
                    set(policy.paired_delta_ci_bounds),
                )

    def test_small_sample_and_missing_truth_candidate_keep_all_headline_metrics_null(self):
        base = _base_shadow()
        candidate_label = base.event_probabilities[0].label
        strict_policy = _policy(min_frozen_rows=3)
        manifest = _split_manifest(candidate_label, base.candidate_set.candidate_set_fingerprint)
        artifact = _artifact(manifest, strict_policy)
        bases, scores, shadows = _two_row_predictions(
            base,
            manifest,
            artifact,
            strict_policy,
            candidate_scores=(3.0, 0.0),
            nil_scores=(0.0, 3.0),
        )
        report = evaluate_frozen_holdout(
            split_manifest=manifest,
            shadows=shadows,
            policy=strict_policy,
            evidence_mode="SYNTHETIC_CONTRACT_ONLY",
            base_shadows=bases,
            score_vectors=scores,
            calibration_artifact=artifact,
        )
        self.assertEqual("NOT_ESTIMABLE_SMALL_SAMPLE", report["status"])
        self.assertTrue(all(value is None for value in report["metrics"].values()))

        bad_rows = list(manifest.assignments)
        bad_rows[4] = replace(
            bad_rows[4],
            truth_label=None,
            binding_status="MISSING",
            matched_candidate_ids=(),
        )
        bad_manifest = CalibrationSplitManifest.create(
            assignments=tuple(bad_rows),
            source_label_ledger_sha256=SHA_D,
            assignment_seed_sha256=SHA_E,
        )
        bad_artifact = _artifact(bad_manifest, strict_policy)
        bad_bases, bad_scores, bad_shadows = _two_row_predictions(
            base,
            bad_manifest,
            bad_artifact,
            strict_policy,
            candidate_scores=(3.0, 0.0),
            nil_scores=(0.0, 3.0),
        )
        report = evaluate_frozen_holdout(
            split_manifest=bad_manifest,
            shadows=bad_shadows,
            policy=strict_policy,
            evidence_mode="SYNTHETIC_CONTRACT_ONLY",
            base_shadows=bad_bases,
            score_vectors=bad_scores,
            calibration_artifact=bad_artifact,
        )
        self.assertEqual("NOT_EVALUABLE_CANDIDATE_SET_INCOMPLETE", report["status"])
        self.assertTrue(all(value is None for value in report["metrics"].values()))

    def test_policy_cannot_be_claimed_as_frozen_tuned(self):
        with self.assertRaisesRegex(ValueError, "policy_origin"):
            _policy(policy_origin="TUNED_ON_FROZEN_HOLDOUT")


if __name__ == "__main__":
    unittest.main()
