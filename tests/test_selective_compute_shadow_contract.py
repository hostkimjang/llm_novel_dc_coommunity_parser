from __future__ import annotations

from dataclasses import replace
import unittest

from src.llm_batch.selective_compute_shadow import (
    ACTION_ASSERT_NIL,
    ACTION_NONE,
    COST_STATUS_PARTIAL_LOG,
    COST_STATUS_PARTIAL_RUNTIME,
    COST_STATUS_STRUCTURED,
    COST_STATUS_SYNTHETIC,
    EVIDENCE_SCOPE_FROZEN_ACTUAL,
    EVIDENCE_SCOPE_SAVED,
    EVIDENCE_SCOPE_SYNTHETIC,
    LANE_CHEAP_RULE,
    LANE_FULL_EXPERT,
    NIL_LABEL,
    REQUIRED_BINDING_NAMES,
    DecisionCostTrace,
    SelectiveComputeObservation,
    SelectiveComputePolicy,
    build_selective_compute_routing,
    canonical_hash,
    decision_cost_trace_from_dict,
    evaluate_selective_compute_receipts,
    normalize_optional_nonnegative_count,
    selective_compute_observation_from_dict,
    selective_compute_policy_from_dict,
    selective_compute_routing_receipt_from_dict,
)


def _sha(label: str) -> str:
    return canonical_hash({"fixture": label})


def _bindings(seed: str = "safe") -> dict[str, str]:
    return {name: _sha(f"{seed}:{name}") for name in REQUIRED_BINDING_NAMES}


def _safe_observation(
    *,
    post_id: str = "p-safe",
    input_index: int = 0,
    action: str = ACTION_ASSERT_NIL,
    label: str = NIL_LABEL,
) -> SelectiveComputeObservation:
    return SelectiveComputeObservation.create(
        evidence_scope=EVIDENCE_SCOPE_SYNTHETIC,
        publication_scope_id="scope-synthetic",
        attempt_run_id="run-synthetic",
        input_index=input_index,
        post_id=post_id,
        binding_digests=_bindings(post_id),
        publication_input_fingerprint=_sha(f"{post_id}:publication-input"),
        baseline_decision_fingerprint=_sha(f"{post_id}:decision"),
        baseline_publication_before_fingerprint=_sha(f"{post_id}:public"),
        baseline_publication_after_fingerprint=_sha(f"{post_id}:public"),
        candidate_set_before_fingerprint=_sha(f"{post_id}:candidates"),
        candidate_set_after_fingerprint=_sha(f"{post_id}:candidates"),
        source_binding_status="VALID",
        search_requirement_status="REQUIRED",
        search_health_status="HEALTHY",
        producer_proof_status="COMPLETE",
        candidate_generation_status="COMPLETE",
        candidate_conflict_status="NONE",
        vlm_ocr_requirement_status="NOT_REQUIRED",
        vlm_ocr_status="NOT_APPLICABLE",
        publication_status="CLEAN",
        judge_coverage_status="COMPLETE",
        scope_status="CURRENT_WORK",
        calibration_status="SYNTHETIC_BOUND",
        budget_binding_status="VALID",
        cheap_terminal_status=(
            "VERIFIED_DETERMINISTIC_NIL"
            if action == ACTION_ASSERT_NIL
            else "VERIFIED_DETERMINISTIC_RESOLVE"
        ),
        proposed_terminal_action=action,
        proposed_selected_label=label,
        cost_evidence_status=COST_STATUS_SYNTHETIC,
        cost_evidence_digest=_sha(f"{post_id}:cost"),
        baseline_expert_calls=4,
        baseline_total_tokens=400,
        baseline_wall_ms=4_000,
    )


def _replace_observation(
    observation: SelectiveComputeObservation,
    **changes,
) -> SelectiveComputeObservation:
    payload = observation.payload_without_observation_fingerprint()
    payload["binding_digests"] = observation.binding_digests
    payload.update(changes)
    return SelectiveComputeObservation.create(**payload)


class SelectiveComputeShadowContractTests(unittest.TestCase):
    def test_policy_and_observation_round_trip_are_strict(self) -> None:
        policy = SelectiveComputePolicy.create(EVIDENCE_SCOPE_SYNTHETIC)
        observation = _safe_observation()
        self.assertEqual(
            selective_compute_policy_from_dict(policy.to_dict()).to_dict(),
            policy.to_dict(),
        )
        self.assertEqual(
            selective_compute_observation_from_dict(observation.to_dict()).to_dict(),
            observation.to_dict(),
        )
        forged = observation.to_dict()
        forged["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "shape mismatch"):
            selective_compute_observation_from_dict(forged)

    def test_safe_synthetic_row_selects_cheap_lane_without_effect(self) -> None:
        policy = SelectiveComputePolicy.create(EVIDENCE_SCOPE_SYNTHETIC)
        receipt = build_selective_compute_routing(_safe_observation(), policy)
        self.assertEqual(receipt.selected_compute_lane, LANE_CHEAP_RULE)
        self.assertEqual(receipt.hard_risk_codes, ())
        self.assertEqual(receipt.expert_call_units_avoided, 4)
        self.assertFalse(receipt.route_applied)
        self.assertFalse(receipt.action_applied)
        self.assertFalse(receipt.public_decision_changed)
        self.assertFalse(receipt.candidate_set_changed)
        self.assertEqual(
            selective_compute_routing_receipt_from_dict(receipt.to_dict()).to_dict(),
            receipt.to_dict(),
        )

    def test_each_false_cheap_signal_fails_closed(self) -> None:
        policy = SelectiveComputePolicy.create(EVIDENCE_SCOPE_SYNTHETIC)
        safe = _safe_observation()
        cases = {
            "source_binding": (
                {"source_binding_status": "INVALID"},
                "SOURCE_BINDING_INVALID",
            ),
            "search_unknown": (
                {"search_requirement_status": "UNKNOWN", "search_health_status": "UNKNOWN"},
                "SEARCH_REQUIRED_OR_UNKNOWN",
            ),
            "search_not_required_laundering": (
                {
                    "search_requirement_status": "NOT_REQUIRED",
                    "search_health_status": "DEGRADED",
                },
                "SEARCH_DEGRADED_OR_BLOCKED",
            ),
            "producer": (
                {"producer_proof_status": "INCOMPLETE"},
                "PRODUCER_PROOF_NOT_COMPLETE",
            ),
            "generation_unknown": (
                {"candidate_generation_status": "UNKNOWN"},
                "CANDIDATE_GENERATION_UNKNOWN",
            ),
            "generation_truncated": (
                {"candidate_generation_status": "TRUNCATED"},
                "CANDIDATE_GENERATION_TRUNCATED",
            ),
            "multi_work": (
                {"candidate_conflict_status": "MULTI_WORK"},
                "MULTI_WORK_OR_IDENTITY_CONFLICT",
            ),
            "vlm_missing": (
                {
                    "vlm_ocr_requirement_status": "REQUIRED",
                    "vlm_ocr_status": "INCOMPLETE",
                },
                "VLM_OCR_REQUIRED_NOT_COMPLETE",
            ),
            "vlm_conflict": (
                {
                    "vlm_ocr_requirement_status": "REQUIRED",
                    "vlm_ocr_status": "CONFLICT",
                },
                "VLM_OCR_TITLE_CONFLICT",
            ),
            "publication_hold": (
                {"publication_status": "HOLD"},
                "PUBLICATION_HOLD_OR_QUARANTINE",
            ),
            "unjudged": (
                {"judge_coverage_status": "UNJUDGED"},
                "UNJUDGED_OR_INVALID_VERDICT",
            ),
            "scope": (
                {"scope_status": "UNKNOWN"},
                "SCOPE_UNKNOWN_OR_NOT_CURRENT_WORK",
            ),
            "calibration": (
                {"calibration_status": "NOT_AVAILABLE"},
                "CALIBRATION_ACTUAL_NOT_BOUND",
            ),
            "budget": (
                {"budget_binding_status": "INVALID"},
                "BUDGET_SCOPE_INVALID",
            ),
            "terminal": (
                {
                    "cheap_terminal_status": "NOT_VERIFIED",
                    "proposed_terminal_action": ACTION_NONE,
                    "proposed_selected_label": None,
                },
                "CHEAP_TERMINAL_NOT_VERIFIED",
            ),
        }
        for name, (changes, expected_code) in cases.items():
            with self.subTest(name=name):
                receipt = build_selective_compute_routing(
                    _replace_observation(safe, **changes),
                    policy,
                )
                self.assertEqual(receipt.selected_compute_lane, LANE_FULL_EXPERT)
                self.assertIn(expected_code, receipt.hard_risk_codes)
                self.assertEqual(receipt.proposed_terminal_action, ACTION_NONE)
                self.assertIsNone(receipt.proposed_selected_label)

    def test_public_or_candidate_mutation_is_rejected_before_routing(self) -> None:
        safe = _safe_observation()
        with self.assertRaisesRegex(ValueError, "public decision fingerprint"):
            _replace_observation(
                safe,
                baseline_publication_after_fingerprint=_sha("different-public"),
            )
        with self.assertRaisesRegex(ValueError, "candidate-set fingerprint"):
            _replace_observation(
                safe,
                candidate_set_after_fingerprint=_sha("different-candidates"),
            )

    def test_runtime_cost_trace_is_typed_and_bound(self) -> None:
        trace = DecisionCostTrace.create(
            publication_scope_id="scope-synthetic",
            run_id="run-actual",
            input_index=0,
            post_id="p-actual",
            model_tier="single-shared-model",
            processing_started_at="2026-07-12T01:00:00+09:00",
            processing_finished_at="2026-07-12T01:00:01+09:00",
            wall_ms=1_000,
            prompt_tokens=90,
            completion_tokens=10,
            total_tokens=100,
            expert_calls=2,
            search_calls=1,
            retry_count=0,
            vlm_chunks=0,
            measurement_status=COST_STATUS_STRUCTURED,
        )
        self.assertEqual(decision_cost_trace_from_dict(trace.to_dict()).to_dict(), trace.to_dict())
        actual = _replace_observation(
            _safe_observation(post_id="p-actual"),
            evidence_scope=EVIDENCE_SCOPE_FROZEN_ACTUAL,
            attempt_run_id="run-actual",
            calibration_status="FROZEN_ACTUAL_BOUND",
            cost_evidence_status=COST_STATUS_STRUCTURED,
            cost_evidence_digest=trace.trace_sha256,
            baseline_expert_calls=2,
            baseline_total_tokens=100,
            baseline_wall_ms=1_000,
        )
        policy = SelectiveComputePolicy.create(EVIDENCE_SCOPE_FROZEN_ACTUAL)
        receipt = build_selective_compute_routing(
            actual,
            policy,
            decision_cost_trace=trace,
        )
        self.assertEqual(receipt.selected_compute_lane, LANE_FULL_EXPERT)
        self.assertIn("ACTUAL_SOURCE_READBACK_NOT_IMPLEMENTED", receipt.hard_risk_codes)
        self.assertEqual(receipt.cost_metric_status, "NOT_ESTIMABLE")
        self.assertIsNone(receipt.expert_call_units_avoided)
        with self.assertRaisesRegex(ValueError, "cost trace digest"):
            build_selective_compute_routing(
                _replace_observation(actual, cost_evidence_digest=_sha("wrong-cost")),
                policy,
                decision_cost_trace=trace,
            )

    def test_partial_runtime_trace_keeps_headline_cost_null(self) -> None:
        trace = DecisionCostTrace.create(
            publication_scope_id="scope-synthetic",
            run_id="run-partial",
            input_index=0,
            post_id="p-partial",
            model_tier="single-shared-model",
            processing_started_at="2026-07-12T01:00:00+09:00",
            processing_finished_at="2026-07-12T01:00:02+09:00",
            wall_ms=2_000,
            prompt_tokens=90,
            completion_tokens=10,
            total_tokens=100,
            expert_calls=None,
            search_calls=1,
            retry_count=0,
            vlm_chunks=0,
            measurement_status=COST_STATUS_PARTIAL_RUNTIME,
        )
        observation = _replace_observation(
            _safe_observation(post_id="p-partial"),
            evidence_scope=EVIDENCE_SCOPE_FROZEN_ACTUAL,
            attempt_run_id="run-partial",
            calibration_status="FROZEN_ACTUAL_BOUND",
            cost_evidence_status=COST_STATUS_PARTIAL_RUNTIME,
            cost_evidence_digest=trace.trace_sha256,
            baseline_expert_calls=None,
            baseline_total_tokens=100,
            baseline_wall_ms=2_000,
        )
        receipt = build_selective_compute_routing(
            observation,
            SelectiveComputePolicy.create(EVIDENCE_SCOPE_FROZEN_ACTUAL),
            decision_cost_trace=trace,
        )
        self.assertEqual(receipt.selected_compute_lane, LANE_FULL_EXPERT)
        self.assertIn("ACTUAL_SOURCE_READBACK_NOT_IMPLEMENTED", receipt.hard_risk_codes)
        self.assertEqual(receipt.cost_metric_status, "NOT_ESTIMABLE")
        self.assertIsNone(receipt.expert_call_units_avoided)
        missing_aggregate = DecisionCostTrace.create(
            publication_scope_id="scope-synthetic",
            run_id="run-missing",
            input_index=2,
            post_id="p-missing",
            model_tier="single-shared-model",
            processing_started_at="2026-07-12T01:00:00+09:00",
            processing_finished_at="2026-07-12T01:00:03+09:00",
            wall_ms=3_000,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            expert_calls=None,
            search_calls=None,
            retry_count=None,
            vlm_chunks=None,
            measurement_status=COST_STATUS_PARTIAL_RUNTIME,
        )
        self.assertIsNone(missing_aggregate.total_tokens)
        self.assertIsNone(missing_aggregate.search_calls)

    def test_actual_scope_cannot_launder_synthetic_cost_or_boolean_readback(self) -> None:
        synthetic = _safe_observation(post_id="p-launder")
        with self.assertRaisesRegex(ValueError, "synthetic cost evidence"):
            _replace_observation(
                synthetic,
                evidence_scope=EVIDENCE_SCOPE_FROZEN_ACTUAL,
                calibration_status="FROZEN_ACTUAL_BOUND",
            )
        trace = DecisionCostTrace.create(
            publication_scope_id="scope-synthetic",
            run_id="run-actual-readback",
            input_index=0,
            post_id="p-actual-readback",
            model_tier="single-shared-model",
            processing_started_at="2026-07-12T01:00:00+09:00",
            processing_finished_at="2026-07-12T01:00:01+09:00",
            wall_ms=1_000,
            prompt_tokens=90,
            completion_tokens=10,
            total_tokens=100,
            expert_calls=2,
            search_calls=1,
            retry_count=0,
            vlm_chunks=0,
            measurement_status=COST_STATUS_STRUCTURED,
        )
        actual = _replace_observation(
            _safe_observation(post_id="p-actual-readback"),
            evidence_scope=EVIDENCE_SCOPE_FROZEN_ACTUAL,
            attempt_run_id="run-actual-readback",
            calibration_status="FROZEN_ACTUAL_BOUND",
            cost_evidence_status=COST_STATUS_STRUCTURED,
            cost_evidence_digest=trace.trace_sha256,
            baseline_expert_calls=2,
            baseline_total_tokens=100,
            baseline_wall_ms=1_000,
        )
        policy = SelectiveComputePolicy.create(EVIDENCE_SCOPE_FROZEN_ACTUAL)
        receipt = build_selective_compute_routing(actual, policy, decision_cost_trace=trace)
        evaluation = evaluate_selective_compute_receipts(
            [receipt],
            [actual],
            policy,
            truth_labels={actual.post_id: NIL_LABEL},
            actual_evidence_readback=True,
            decision_cost_traces={actual.post_id: trace},
        )
        self.assertEqual(evaluation["gate"], "NO_GO_ACTUAL_ARTIFACT_READBACK_NOT_IMPLEMENTED")
        self.assertIsNone(evaluation["primary_metrics"]["safe_auto_coverage"]["value"])
        self.assertIsNone(evaluation["primary_metrics"]["expert_calls_per_post"]["value"])
        with self.assertRaisesRegex(ValueError, "must be bool"):
            evaluate_selective_compute_receipts(
                [receipt],
                [actual],
                policy,
                truth_labels={actual.post_id: NIL_LABEL},
                actual_evidence_readback=1,  # type: ignore[arg-type]
                decision_cost_traces={actual.post_id: trace},
            )

    def test_optional_count_normalizer_never_turns_invalid_values_into_zero(self) -> None:
        self.assertEqual(normalize_optional_nonnegative_count(0), 0)
        self.assertEqual(normalize_optional_nonnegative_count("12"), 12)
        for value in (None, "", " ", False, True, -1, "-1", 1.5, "1.5", object()):
            with self.subTest(value=repr(value)):
                self.assertIsNone(normalize_optional_nonnegative_count(value))

    def test_synthetic_evaluation_computes_only_fixture_math(self) -> None:
        policy = SelectiveComputePolicy.create(EVIDENCE_SCOPE_SYNTHETIC)
        cheap = _safe_observation(post_id="p-cheap", input_index=0)
        full = _replace_observation(
            _safe_observation(
                post_id="p-full",
                input_index=1,
                action="RESOLVE",
                label="cand_full",
            ),
            search_health_status="BLOCKED",
        )
        receipts = [
            build_selective_compute_routing(cheap, policy),
            build_selective_compute_routing(full, policy),
        ]
        evaluation = evaluate_selective_compute_receipts(
            receipts,
            [cheap, full],
            policy,
            truth_labels={"p-cheap": NIL_LABEL, "p-full": "cand_full"},
        )
        self.assertEqual(evaluation["gate"], "GO_SYNTHETIC_CONTRACT_ONLY")
        self.assertEqual(evaluation["primary_metrics"]["safe_auto_coverage"]["value"], 0.5)
        self.assertEqual(evaluation["primary_metrics"]["expert_escalation_rate"]["value"], 0.5)
        self.assertEqual(
            evaluation["primary_metrics"]["expert_escalation_rate"]["status"],
            "SYNTHETIC_CONTRACT_ONLY",
        )
        self.assertEqual(evaluation["primary_metrics"]["expert_calls_per_post"]["value"], 2.0)
        self.assertEqual(evaluation["primary_metrics"]["expert_call_avoidance_rate"]["value"], 0.5)
        self.assertFalse(evaluation["full_scan_approval"])

    def test_saved_artifact_evaluation_refuses_actual_cost_percentages(self) -> None:
        saved = _replace_observation(
            _safe_observation(post_id="p-saved"),
            evidence_scope=EVIDENCE_SCOPE_SAVED,
            calibration_status="NOT_AVAILABLE",
            cost_evidence_status=COST_STATUS_PARTIAL_LOG,
            cost_evidence_digest=_sha("sidecar-logs"),
            baseline_expert_calls=3,
            baseline_total_tokens=300,
            baseline_wall_ms=3_000,
        )
        policy = SelectiveComputePolicy.create(EVIDENCE_SCOPE_SAVED)
        receipt = build_selective_compute_routing(saved, policy)
        evaluation = evaluate_selective_compute_receipts(
            [receipt],
            [saved],
            policy,
            truth_labels={"p-saved": NIL_LABEL},
        )
        self.assertEqual(receipt.selected_compute_lane, LANE_FULL_EXPERT)
        self.assertIsNone(evaluation["primary_metrics"]["safe_auto_coverage"]["value"])
        self.assertIsNone(evaluation["primary_metrics"]["expert_calls_per_post"]["value"])
        self.assertEqual(evaluation["primary_metrics"]["expert_escalation_rate"]["value"], 1.0)
        self.assertEqual(
            evaluation["primary_metrics"]["expert_escalation_rate"]["status"],
            "OBSERVED_SHADOW_ROUTE_DISTRIBUTION",
        )
        self.assertEqual(evaluation["gate"], "NO_GO_ACTUAL_EVIDENCE_NOT_AVAILABLE")

    def test_forged_receipt_and_duplicate_identity_are_rejected(self) -> None:
        policy = SelectiveComputePolicy.create(EVIDENCE_SCOPE_SYNTHETIC)
        observation = _safe_observation()
        receipt = build_selective_compute_routing(observation, policy)
        forged = receipt.to_dict()
        forged["action_applied"] = True
        forged["receipt_sha256"] = canonical_hash(
            {key: value for key, value in forged.items() if key != "receipt_sha256"}
        )
        with self.assertRaisesRegex(ValueError, "must not apply"):
            selective_compute_routing_receipt_from_dict(forged)
        duplicate_identity_observation = _replace_observation(
            observation,
            cost_evidence_digest=_sha("duplicate-identity-cost"),
        )
        duplicate_identity_receipt = build_selective_compute_routing(
            duplicate_identity_observation,
            policy,
        )
        with self.assertRaisesRegex(ValueError, "post_id values must be unique"):
            evaluate_selective_compute_receipts(
                [receipt, duplicate_identity_receipt],
                [observation, duplicate_identity_observation],
                policy,
                truth_labels={observation.post_id: NIL_LABEL},
            )
        other_scope = _replace_observation(
            _safe_observation(post_id="p-other-scope", input_index=1),
            publication_scope_id="scope-other",
        )
        with self.assertRaisesRegex(ValueError, "mix publication scopes"):
            evaluate_selective_compute_receipts(
                [receipt, build_selective_compute_routing(other_scope, policy)],
                [observation, other_scope],
                policy,
                truth_labels={observation.post_id: NIL_LABEL, other_scope.post_id: NIL_LABEL},
            )

    def test_mapping_values_are_snapshotted_before_evaluation(self) -> None:
        class OneShotMapping(dict):
            def __iter__(self):
                return super().__iter__()

        policy = SelectiveComputePolicy.create(EVIDENCE_SCOPE_SYNTHETIC)
        observation = _safe_observation()
        receipt = build_selective_compute_routing(observation, policy)
        truth = OneShotMapping({observation.post_id: NIL_LABEL})
        result = evaluate_selective_compute_receipts(
            [receipt],
            [observation],
            policy,
            truth_labels=truth,
        )
        truth[observation.post_id] = "tampered-after-call"
        self.assertEqual(result["primary_metrics"]["safe_auto_coverage"]["value"], 1.0)


if __name__ == "__main__":
    unittest.main()
