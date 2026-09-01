from __future__ import annotations

import unittest

from tools.analyze_frozen_2712_repeat_consensus import build_repeat_consensus_report


def ledger(post_id: int = 1, verdict: str = "PASS", action: str = "KEEP", title: str | None = "Expected") -> dict:
    return {
        "post_id": post_id,
        "cohorts": ["control"],
        "independent_semantic_verdict": {
            "review_verdict": verdict,
            "dashboard_action": action,
            "recommended_title": title,
            "dashboard_title_expected": title,
        },
    }


def run(post_id: int = 1, publish: bool = True, title: str | None = "Expected") -> dict:
    return {
        "post_id": post_id,
        "analysis_result": {"identity": {"identity_state": "resolved_title", "system_state": "clean", "promotion_decision": {"publish_allowed": publish, "official_title": title}, "search_health": {"status": "HEALTHY", "queries_issued": 1}}},
        "run_meta": {"decision_cost_trace": {"expert_calls": 1, "search_calls": 1, "prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5, "wall_ms": 7}},
    }


def run_with_search_health(post_id: int = 1, **health: object) -> dict:
    row = run(post_id)
    row["analysis_result"]["identity"]["search_health"] = health
    return row


def manifest(model: str = "model-a", snapshot: str = "snapshot-a") -> dict:
    return {
        "input_post_count": 1,
        "completed_count": 1,
        "flushed_count": 1,
        "pending_count": 0,
        "failed_count": 0,
        "terminal_artifacts_finalized": True,
        "runtime_completion_gate": {"status": "GO"},
        "requested_parallel": 16,
        "effective_parallel": 1,
        "dashboard_enabled": True,
        "llm_model": model,
        "input_snapshot_hash": snapshot,
    }


def production_manifest(model: str = "model-a", snapshot: str = "snapshot-a") -> dict:
    value = manifest(model=model, snapshot=snapshot)
    value["publication_input_snapshot_sha256"] = value.pop("input_snapshot_hash")
    return value


class FrozenRepeatConsensusTest(unittest.TestCase):
    def test_production_publication_snapshot_key_is_accepted(self) -> None:
        rows, summary = build_repeat_consensus_report(
            [ledger()],
            [[run()] for _ in range(3)],
            [[run()] for _ in range(3)],
            before_manifests=[production_manifest() for _ in range(3)],
            after_manifests=[production_manifest() for _ in range(3)],
        )
        self.assertEqual(1, len(rows))
        self.assertEqual("GO", summary["manifest_comparability"]["status"])

    def test_numeric_search_health_counts_and_bool_flags_are_explicit(self) -> None:
        health = {
            "status": "SEARCH_DEGRADED",
            "queries_issued": 2,
            "degraded": 2,
            "unrecovered_degraded": 1,
        }
        rows, summary = build_repeat_consensus_report(
            [ledger()],
            [[run_with_search_health(**health)] for _ in range(3)],
            [[run_with_search_health(**health)] for _ in range(3)],
        )
        search = summary["metrics"]["observability"]["before"]["search_health"]
        self.assertEqual(6, search["counts"]["degraded_count"]["value"])
        self.assertEqual(search["counts"]["degraded_count"], search["degraded_count"])
        self.assertEqual("MEASURED", search["counts"]["degraded_count"]["status"])
        self.assertEqual(3, search["is_flags"]["is_degraded"]["true"])
        self.assertEqual(search["is_flags"]["is_degraded"], search["is_degraded"])
        self.assertEqual(3, search["is_flags"]["is_unrecovered_degraded"]["true"])
        # Existing consumers retain the old bool-only key path; the additive
        # `is_flags` path exposes normalized bools for numeric rows.
        self.assertEqual("NOT_ESTIMABLE", search["booleans"]["degraded"]["status"])
        self.assertEqual(3, search["status_counts"]["SEARCH_DEGRADED"])

    def test_exact_post_id_set_failure(self) -> None:
        with self.assertRaisesRegex(ValueError, "post_id set mismatch"):
            build_repeat_consensus_report(
                [ledger()],
                [[run()], [run(2)], [run()]],
                [[run()], [run()], [run()]],
            )

    def test_one_of_three_wobble_is_not_two_of_three_consensus(self) -> None:
        rows, summary = build_repeat_consensus_report(
            [ledger()],
            [[run()], [run()], [run()]],
            [[run(publish=True, title="Wrong")], [run()], [run()]],
        )
        after = rows[0]["after"]
        self.assertEqual("TWO_OF_THREE", after["public_consensus"]["fraction_label"])
        self.assertEqual("COMPLIANT", after["adjudication_consensus"]["label"])
        self.assertEqual(2, after["exact_adjudicated_compliance_count"])
        self.assertEqual(1, after["public_projection_distribution"][1]["count"])
        self.assertEqual(0, summary["metrics"]["systematic_regressions"])

        rows, summary = build_repeat_consensus_report(
            [ledger()],
            [[run()], [run()], [run()]],
            [[run(publish=True, title="Wrong")], [run(publish=True, title="Wrong")], [run()]],
        )
        self.assertEqual("TWO_OF_THREE", rows[0]["after"]["adjudication_consensus"]["fraction_label"])
        self.assertEqual("NONCOMPLIANT", rows[0]["after"]["adjudication_consensus"]["label"])
        self.assertEqual(1, summary["metrics"]["systematic_regressions"])
        self.assertEqual({"TWO_OF_THREE": 1}, summary["metrics"]["normal_to_abnormal_concentration"])

    def test_new_any_run_unsafe_publish_requires_review_but_is_not_hard_failure(self) -> None:
        rows, summary = build_repeat_consensus_report(
            [ledger()],
            [[run()], [run()], [run()]],
            [[run(publish=True, title="Wrong")], [run()], [run()]],
        )
        self.assertTrue(rows[0]["transition"]["after_unsafe_publish_any_run"])
        self.assertEqual(1, summary["metrics"]["after_unsafe_publish_any_run"])
        self.assertEqual(1, summary["metrics"]["unsafe_publish_transition"]["introduced_any_run"])
        self.assertEqual("REVIEW_REQUIRED_NEW_UNSAFE_PUBLICATION", summary["gate"])

    def test_persistent_unsafe_publish_is_separated_from_new_regression(self) -> None:
        rows, summary = build_repeat_consensus_report(
            [ledger()],
            [[run(publish=True, title="Wrong")], [run()], [run()]],
            [[run(publish=True, title="Wrong")], [run()], [run()]],
        )
        self.assertEqual(1, len(rows))
        self.assertEqual(0, summary["metrics"]["unsafe_publish_transition"]["introduced_any_run"])
        self.assertEqual(1, summary["metrics"]["unsafe_publish_transition"]["persistent_any_run"])
        self.assertNotEqual("HARD_SAFETY_EVENT", summary["gate"])

    def test_manifest_comparability_rejects_model_or_snapshot_difference(self) -> None:
        _, report = build_repeat_consensus_report(
            [ledger()], [[run()], [run()], [run()]], [[run()], [run()], [run()]],
            before_manifests=[manifest(), manifest(), manifest()],
            after_manifests=[manifest(), manifest(), manifest()],
        )
        self.assertEqual("GO", report["manifest_comparability"]["status"])
        self.assertEqual(6, len(report["manifest_comparability"]["records"]))
        with self.assertRaisesRegex(ValueError, "model differs"):
            build_repeat_consensus_report(
                [ledger()], [[run()], [run()], [run()]], [[run()], [run()], [run()]],
                before_manifests=[manifest(), manifest(), manifest()],
                after_manifests=[manifest(), manifest(model="model-b"), manifest()],
            )
        with self.assertRaisesRegex(ValueError, "input_snapshot_hash differs"):
            build_repeat_consensus_report(
                [ledger()], [[run()], [run()], [run()]], [[run()], [run()], [run()]],
                before_manifests=[manifest(), manifest(), manifest()],
                after_manifests=[manifest(), manifest(snapshot="snapshot-b"), manifest()],
            )


if __name__ == "__main__":
    unittest.main()
