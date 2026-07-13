from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.run_selective_compute_shadow_harness import (
    DEFAULT_P1_COMPARISON,
    DEFAULT_P1_RUN_SPEC,
    DEFAULT_P2_COMPARISON,
    DEFAULT_P2_RUN_SPEC,
    DEFAULT_P3_COMPARISON,
    DEFAULT_P3_RUN_SPEC,
    DEFAULT_OUTPUT_DIR,
    LANE_FULL_EXPERT,
    _implementation_contract,
    _read_json,
    _run_attack_suite,
    _run_spec_self_hash,
    _validate_p3_parent_chain,
    _validate_parent_comparison_semantics,
    build_comparison,
    create_run_spec,
    parse_sidecar_cost_logs,
    render_markdown,
    validate_comparison,
    validate_run_spec_dict,
    write_bundle,
)
from src.llm_batch.selective_compute_shadow import canonical_hash


ROOT = Path(__file__).resolve().parents[1]


class SelectiveComputeShadowHarnessUnitTests(unittest.TestCase):
    def test_canonical_defaults_point_to_v19_chain(self) -> None:
        self.assertEqual("v8", DEFAULT_P2_RUN_SPEC.parent.name)
        self.assertEqual("v18", DEFAULT_P3_RUN_SPEC.parent.name)
        self.assertEqual("v18", DEFAULT_P3_COMPARISON.parent.name)
        self.assertEqual("v19", DEFAULT_OUTPUT_DIR.name)

    def test_implementation_contract_is_materialized_without_parent_chain(self) -> None:
        implementation = _implementation_contract()
        self.assertIsInstance(implementation, dict)
        self.assertEqual(set(implementation), {"artifacts", "sha256"})
        self.assertIn("routing_contract", implementation["artifacts"])
        self.assertIn("future_runtime_instrumentation", implementation["artifacts"])
        for name in (
            "physical_call_ledger_contract",
            "physical_call_independent_reader",
            "physical_call_wrapper",
            "after_source_only_router",
            "paired_measurement_reader",
            "paired_measurement_cli",
            "physical_retry_observer",
            "publication_cost_noninterference",
            "publication_call_integration_tests",
            "runtime_binding_tests",
            "recovery_tool",
            "ledger_independent_reader_tests",
            "early_route_contract_tests",
            "early_route_runtime_tests",
            "paired_measurement_reader_tests",
            "fresh_measurement_recovery_tests",
        ):
            self.assertIn(name, implementation["artifacts"])

    def test_false_cheap_attack_suite_runs_without_parent_chain(self) -> None:
        attacks = _run_attack_suite()
        self.assertEqual(attacks["attack_count"], 20)
        self.assertEqual(attacks["blocked_or_rejected"], 20)
        self.assertEqual(attacks["false_cheap_count"], 0)

    def test_future_runtime_trace_hook_exists_without_parent_chain(self) -> None:
        source = (ROOT / "expert_main.py").read_text(encoding="utf-8")
        self.assertIn("DecisionCostTrace.create(", source)
        self.assertIn("publication_scope_id=publication_scope_id", source)
        self.assertIn("input_index=index", source)
        self.assertIn("expert_calls=None", source)
        self.assertIn('"decision_cost_trace": _decision_cost_trace.to_dict()', source)
        self.assertIn("DecisionTracingLLMClient(", source)
        self.assertIn(".begin_row_attempt(", source)
        self.assertIn(".seal_row_attempt()", source)
        self.assertIn("decision_call_ledger_registry.link_publication(", source)
        self.assertIn('"decision_call_ledger_production_enable_allowed": False', source)

    def test_parser_missing_and_duplicate_evidence_fail_closed_without_parent_chain(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "W0.log"
            second = Path(temp_dir) / "W1.log"
            first.write_text(
                "\n".join(
                    [
                        "[01:00:00.000|W0] Orchestrator 시작: post_id=9001",
                        "[01:00:01.000|W0] 📊 Post 9001 token usage",
                        "  prompt_tokens: 9",
                        "  completion_tokens: 1",
                        "  total_tokens: 10",
                        "[01:00:02.000|W0] ✅ Post 9001 완료 (2.0s, 0 iterations)",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            rows = parse_sidecar_cost_logs([first])
            self.assertNotIn("expert_prompt_calls_observed", rows["9001"])
            second.write_text(
                "[01:00:00.000|W1] 🖼️ VLM chunk request: post_id=9001 chunk=1/1\n",
                encoding="utf-8",
            )
            duplicated = parse_sidecar_cost_logs([first, second])
            self.assertEqual(duplicated["9001"]["attribution_status"], "AMBIGUOUS_MULTI_LOG")

    def test_forged_parent_comparison_is_rejected_without_full_chain_setup(self) -> None:
        forged = _read_json(DEFAULT_P1_COMPARISON)
        forged["gates"]["probability"] = "FORGED_GO"
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "forged-p1-comparison.json"
            path.write_text(json.dumps(forged, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "semantic replay mismatch"):
                _validate_parent_comparison_semantics(
                    stage="P1",
                    run_spec_path=DEFAULT_P1_RUN_SPEC,
                    comparison_path=path,
                )

    def test_p3_parent_chain_and_label_ledger_are_exactly_bound(self) -> None:
        p1_spec = _read_json(DEFAULT_P1_RUN_SPEC)
        p2_spec = _read_json(DEFAULT_P2_RUN_SPEC)
        p3_spec = _read_json(DEFAULT_P3_RUN_SPEC)
        label_ref = _validate_p3_parent_chain(
            p1_spec=p1_spec,
            p2_spec=p2_spec,
            p3_spec=p3_spec,
            p1_run_spec_path=DEFAULT_P1_RUN_SPEC,
            p1_comparison_path=DEFAULT_P1_COMPARISON,
            p2_run_spec_path=DEFAULT_P2_RUN_SPEC,
            p2_comparison_path=DEFAULT_P2_COMPARISON,
        )
        self.assertEqual(p3_spec["artifacts"]["label_ledger"], label_ref)

        wrong_parent = copy.deepcopy(p3_spec)
        wrong_parent["parent_contract"]["p1_run_spec_self_hash"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "parent chain self-hash"):
            _validate_p3_parent_chain(
                p1_spec=p1_spec,
                p2_spec=p2_spec,
                p3_spec=wrong_parent,
                p1_run_spec_path=DEFAULT_P1_RUN_SPEC,
                p1_comparison_path=DEFAULT_P1_COMPARISON,
                p2_run_spec_path=DEFAULT_P2_RUN_SPEC,
                p2_comparison_path=DEFAULT_P2_COMPARISON,
            )

        wrong_ledger = copy.deepcopy(p3_spec)
        wrong_ledger["artifacts"]["label_ledger"] = copy.deepcopy(
            p3_spec["artifacts"]["dataset_readiness"]
        )
        with self.assertRaisesRegex(ValueError, "label ledger lineage"):
            _validate_p3_parent_chain(
                p1_spec=p1_spec,
                p2_spec=p2_spec,
                p3_spec=wrong_ledger,
                p1_run_spec_path=DEFAULT_P1_RUN_SPEC,
                p1_comparison_path=DEFAULT_P1_COMPARISON,
                p2_run_spec_path=DEFAULT_P2_RUN_SPEC,
                p2_comparison_path=DEFAULT_P2_COMPARISON,
            )


class SelectiveComputeShadowHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.spec = create_run_spec(
            parent_p1_run_spec_path=DEFAULT_P1_RUN_SPEC,
            parent_p1_comparison_path=DEFAULT_P1_COMPARISON,
            parent_p2_run_spec_path=DEFAULT_P2_RUN_SPEC,
            parent_p2_comparison_path=DEFAULT_P2_COMPARISON,
            parent_p3_run_spec_path=DEFAULT_P3_RUN_SPEC,
            parent_p3_comparison_path=DEFAULT_P3_COMPARISON,
        )
        cls.comparison = build_comparison(cls.spec)

    def test_run_spec_and_parent_cost_evidence_validate(self) -> None:
        implementation = _implementation_contract()
        self.assertIsInstance(implementation, dict)
        self.assertIn("artifacts", implementation)
        self.assertIn("sha256", implementation)
        context = validate_run_spec_dict(self.spec)
        self.assertEqual(18, len(context["label_ledger_rows"]))
        self.assertEqual(
            self.spec["artifacts"]["p3_label_ledger"]["sha256"],
            self.spec["parent_contract"]["p3_label_ledger_sha256"],
        )
        cost = context["cost_diagnostics"]
        self.assertEqual(cost["status"], "PARTIAL_SIDECAR_LOG")
        self.assertEqual(cost["row_count"], 18)
        self.assertEqual(cost["post_id_log_coverage"], 18)
        self.assertEqual(cost["token_aggregate_coverage"], 18)
        self.assertEqual(cost["wall_time_coverage"], 18)
        self.assertFalse(cost["canonical_per_post_cost_receipt"])
        self.assertFalse(self.spec["full_scan_approval"])

    def test_p4_explicit_p3_label_ledger_binding_rejects_substitution(self) -> None:
        forged = copy.deepcopy(self.spec)
        forged["artifacts"]["p3_label_ledger"] = copy.deepcopy(
            forged["artifacts"]["baseline_result"]
        )
        forged["run_spec_sha256"] = _run_spec_self_hash(forged)
        with self.assertRaisesRegex(ValueError, "P3 label ledger binding"):
            validate_run_spec_dict(forged)

    def test_log_parser_reconstructs_diagnostics_but_not_receipts(self) -> None:
        paths = [ref["path"] for ref in self.spec["artifacts"]["worker_logs"]]
        rows = parse_sidecar_cost_logs(paths)
        self.assertEqual(len(rows), 18)
        self.assertTrue(all(row.get("wall_ms_observed", 0) > 0 for row in rows.values()))
        self.assertTrue(all(row.get("total_tokens_observed", 0) >= 0 for row in rows.values()))
        self.assertTrue(any(row.get("expert_prompt_calls_observed", 0) > 1 for row in rows.values()))

    def test_log_parser_does_not_launder_missing_calls_or_duplicate_attribution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "W0.log"
            second = Path(temp_dir) / "W1.log"
            first.write_text(
                "\n".join(
                    [
                        "[01:00:00.000|W0] Orchestrator 시작: post_id=9001",
                        "[01:00:01.000|W0] 📊 Post 9001 token usage",
                        "  prompt_tokens: 9",
                        "  completion_tokens: 1",
                        "  total_tokens: 10",
                        "[01:00:02.000|W0] ✅ Post 9001 완료 (2.0s, 0 iterations)",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            rows = parse_sidecar_cost_logs([first])
            self.assertEqual(rows["9001"]["attribution_status"], "COMPLETE_SINGLE_ATTEMPT")
            self.assertNotIn("expert_prompt_calls_observed", rows["9001"])
            second.write_text(
                "[01:00:00.000|W1] 🖼️ VLM chunk request: post_id=9001 chunk=1/1\n",
                encoding="utf-8",
            )
            duplicated = parse_sidecar_cost_logs([first, second])
            self.assertEqual(duplicated["9001"]["attribution_status"], "AMBIGUOUS_MULTI_LOG")
            self.assertEqual(len(duplicated["9001"]["source_logs"]), 2)

    def test_future_runtime_row_persists_typed_partial_trace(self) -> None:
        source = (ROOT / "expert_main.py").read_text(encoding="utf-8")
        self.assertIn("DecisionCostTrace.create(", source)
        self.assertIn("publication_scope_id=publication_scope_id", source)
        self.assertIn("input_index=index", source)
        self.assertIn("expert_calls=None", source)
        self.assertIn('measurement_status=COST_STATUS_PARTIAL_RUNTIME', source)
        self.assertIn('"decision_cost_trace": _decision_cost_trace.to_dict()', source)

    def test_saved_golden_fails_closed_and_actual_metrics_stay_null(self) -> None:
        validate_comparison(self.comparison, self.spec)
        actual = self.comparison["actual_saved_golden"]
        evaluation = actual["evaluation"]
        self.assertEqual(evaluation["lane_counts"][LANE_FULL_EXPERT], 18)
        self.assertEqual(actual["before_after"]["public_contract_unchanged_rows"], 18)
        self.assertIsNone(actual["before_after"]["actual_cost_delta"])
        self.assertEqual(
            "IMPLEMENTED_FOUNDATION_NO_ACTUAL_PAIR",
            self.comparison["gates"]["actual_source_readback"],
        )
        self.assertEqual(
            "IMPLEMENTED_READER_ROUTER_PAIRED_HARNESS_NOT_RUNTIME_EXECUTED",
            self.comparison["gates"]["future_runtime_instrumentation"],
        )
        for name, metric in evaluation["primary_metrics"].items():
            if name != "expert_escalation_rate":
                self.assertIsNone(metric["value"], name)
        self.assertEqual(evaluation["gate"], "NO_GO_ACTUAL_EVIDENCE_NOT_AVAILABLE")

    def test_synthetic_math_and_twenty_attacks_are_scoped(self) -> None:
        synthetic = self.comparison["synthetic_contract"]
        self.assertFalse(synthetic["actual_performance_claim_allowed"])
        self.assertEqual(
            synthetic["evaluation"]["primary_metrics"]["expert_escalation_rate"]["status"],
            "SYNTHETIC_CONTRACT_ONLY",
        )
        self.assertEqual(
            synthetic["before_after_fixture_math"]["status"],
            "SYNTHETIC_CONTRACT_ONLY_NOT_ACTUAL_SAVINGS",
        )
        attacks = _run_attack_suite()
        self.assertEqual(attacks["attack_count"], 20)
        self.assertEqual(attacks["blocked_or_rejected"], 20)
        self.assertEqual(attacks["false_cheap_count"], 0)

    def test_korean_report_explains_features_and_approval_boundary(self) -> None:
        markdown = render_markdown(self.comparison, self.spec)
        for phrase in (
            "기능을 쉽게 읽는 표",
            "저장된 Golden18",
            "합성 4행",
            "실제 파이프라인 절감률이 아니다",
            "false-cheap 적대 테스트",
            "sibling typed call ledger",
            "paired source replay",
            "reference-copy 0-call",
            "18/59 bounded 검증 전용",
            "runtime_validation=NOT_RUN",
            "full_scan_approval=false",
        ):
            self.assertIn(phrase, markdown)
        self.assertNotIn("full_scan_approval=true", markdown)

    def test_forged_actual_metric_and_approval_are_rejected(self) -> None:
        forged_metric = copy.deepcopy(self.comparison)
        forged_metric["actual_saved_golden"]["evaluation"]["primary_metrics"][
            "expert_calls_per_post"
        ]["value"] = 1.0
        with self.assertRaisesRegex(ValueError, "replay mismatch"):
            validate_comparison(forged_metric, self.spec)
        forged_approval = copy.deepcopy(self.comparison)
        forged_approval["full_scan_approval"] = True
        with self.assertRaisesRegex(ValueError, "approval boundary"):
            validate_comparison(forged_approval, self.spec)

    def test_immutable_bundle_readback_and_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "p4"
            paths = write_bundle(self.spec, self.comparison, output)
            first = {name: path.read_bytes() for name, path in paths.items()}
            replay = write_bundle(self.spec, self.comparison, output)
            self.assertEqual(
                {name: path.read_bytes() for name, path in replay.items()},
                first,
            )
            tampered = copy.deepcopy(self.comparison)
            tampered["generated_at"] = "2099-01-01T00:00:00+09:00"
            with self.assertRaisesRegex(ValueError, "immutable artifact conflict"):
                write_bundle(self.spec, tampered, output)
            self.assertEqual(
                {name: path.read_bytes() for name, path in paths.items()},
                first,
            )

    def test_bundle_snapshots_mutable_inputs_before_validation(self) -> None:
        mutable_comparison = copy.deepcopy(self.comparison)
        from tools import run_selective_compute_shadow_harness as harness

        real_validate = harness.validate_run_spec_dict

        def mutate_original_after_snapshot(value):
            mutable_comparison["full_scan_approval"] = True
            return real_validate(value)

        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            harness,
            "validate_run_spec_dict",
            side_effect=mutate_original_after_snapshot,
        ):
            paths = harness.write_bundle(
                self.spec,
                mutable_comparison,
                Path(temp_dir) / "snapshot-safe",
            )
            stored = json.loads(paths["comparison_json"].read_text(encoding="utf-8"))
            self.assertFalse(stored["full_scan_approval"])

    def test_corrupt_staging_bundle_is_never_exposed(self) -> None:
        from tools import run_selective_compute_shadow_harness as harness

        real_write = harness._exclusive_write

        def corrupt_comparison(path, payload):
            real_write(path, payload)
            if path.name == "comparison.json":
                path.write_text("{}\n", encoding="utf-8")

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "corrupt-staging"
            with patch.object(
                harness,
                "_exclusive_write",
                side_effect=corrupt_comparison,
            ), self.assertRaises(ValueError):
                harness.write_bundle(self.spec, self.comparison, target)
            self.assertFalse(target.exists())

    def test_run_spec_live_hash_tampering_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.spec)
        tampered["cost_baseline"]["post_id_log_coverage"] = 17
        with self.assertRaisesRegex(ValueError, "self hash"):
            validate_run_spec_dict(tampered)

    def test_self_consistent_implementation_set_reduction_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.spec)
        artifacts = tampered["implementation_contract"]["artifacts"]
        artifacts.pop("physical_call_ledger_contract")
        tampered["implementation_contract"]["sha256"] = canonical_hash(
            {
                name: ref["sha256"]
                for name, ref in sorted(artifacts.items())
            }
        )
        tampered["run_spec_sha256"] = _run_spec_self_hash(tampered)
        with self.assertRaisesRegex(ValueError, "implementation contract mismatch"):
            validate_run_spec_dict(tampered)


if __name__ == "__main__":
    unittest.main()
