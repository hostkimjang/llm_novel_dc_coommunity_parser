from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from src.llm_batch.ledger.publication_commit import compute_publication_decision_commit
from src.llm_batch.measurement.publication_shadow_observation import build_publication_shadow_observation
from tests.test_publication_decision_commit import _scope_id, _valid_result
from tools.analyze_recovery_sidecar_grouped_ab import (
    _measurement_status_with_readback,
    build_report,
)


class GroupedRecoveryAnalyzerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "runs"
        self.scope = _scope_id(tuple(range(1, 33)))
        self._write_fixture()

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def _dump(path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _jsonl(path: Path, values: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values), encoding="utf-8")

    def _result(self, post_id: int, title: str = "Expected", publish: bool = True, router_unknown: bool = False, raw_identity_conflict: bool = False, search_status: str = "HEALTHY") -> dict:
        result = _valid_result(post_id=post_id, candidate_title=title, publish=publish)
        identity = result["analysis_result"]["identity"]
        identity["system_state"] = "clean"
        if not router_unknown:
            identity["semantic_review_required"] = False
        if raw_identity_conflict:
            # This is deliberately a CLI/raw identity-shaped hint, not the
            # typed publication decision that the commit and shadow receipt bind.
            identity["raw_cli_identity"] = {"publish_allowed": False, "official_title": "Raw Identity Wrong"}
        identity["search_health"] = {"status": search_status, "queries_issued": 0, "degraded": 0, "unrecovered_degraded": 0}
        result["run_meta"] = {"decision_cost_trace": {"expert_calls": 1, "search_calls": 1, "prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5, "wall_ms": 7}}
        return result

    def _commit(self, result: dict, index: int) -> dict:
        return compute_publication_decision_commit(result, publication_scope_id=self.scope, attempt_run_id="synthetic", input_index=index, post_id=index).to_dict()

    def _manifest(self, arm: str, measurement: str = "GO") -> dict:
        return {"input_post_count": 32, "completed_count": 32, "flushed_count": 32, "pending_count": 0, "failed_count": 0,
                "requested_parallel": 16, "effective_parallel": 16, "dashboard_enabled": True, "terminal_artifacts_finalized": True,
                "publication_execution_mode": "FRESH_SHADOW_OBSERVATION_NO_PUBLIC_WRITE", "recovery_activation_status": "SKIPPED_FRESH_MEASUREMENT",
                "recovery_activation_requested_mode": "OFF" if arm == "before" else "AUDIT_ONLY",
                "runtime_completion_gate": {"status": "GO"}, "measurement_gate": {"status": measurement, "reason_codes": [] if measurement == "GO" else ["SYNTHETIC_NO_GO"]},
                "decision_call_ledger_summary": {
                    "ledger_status": "COMPLETE" if measurement == "GO" else "PARTIAL",
                    "actual_kpi_status": "MEASURED" if measurement == "GO" else "NOT_ESTIMABLE",
                    "reason_codes": [] if measurement == "GO" else ["SYNTHETIC_NO_GO"],
                    "derived_observation": {"expert_calls": 32},
                },
                "publication_noninterference_gate": {"status": "GO", "public_write_allowed": False, "start_wal_sha256": self.wal_sha, "current_wal_sha256": self.wal_sha, "start_wal_event_count": 32, "current_wal_event_count": 32},
                "publication_shadow_observation": {"status": "GO", "public_apply": False, "observed_observation_count": 32}}

    def _write_fixture(self, *, after_wrong_repeats: set[int] = set(), after_hold_repeats: set[int] = set(), measurement: str = "GO", tamper: bool = False, router_unknown: bool = False, raw_identity_conflict: bool = False, search_status: str = "HEALTHY") -> Path:
        source_rows, ledger_rows = [], []
        authorities = {}
        for index in range(1, 33):
            result, commit = self._result(index, search_status=search_status), self._commit(self._result(index, search_status=search_status), index)
            # Commit must match exactly the stored result; generate it from that row.
            commit = self._commit(result, index)
            source_rows.append({"global_idx": index, "post_id": index, "publication_commit": commit, "result": result})
            authorities[index] = commit
            ledger_rows.append({"post_id": index, "independent_semantic_verdict": {"review_verdict": "PASS", "dashboard_action": "KEEP", "recommended_title": "Expected", "dashboard_title_expected": "Expected"}})
        self._jsonl(self.root / "source_owner_checkpoint.jsonl", source_rows)
        wal = self.root.parent / "publication_wal.jsonl"
        self._jsonl(wal, [{"sequence": index} for index in range(1, 33)])
        self.wal_sha = hashlib.sha256(wal.read_bytes()).hexdigest()
        self._dump(self.root / "source_owner_manifest.json", {"runtime_completion_gate": {"status": "GO"}, "publication_commit_journal": str(wal)})
        ledger = self.root.parent / "ledger.jsonl"; self._jsonl(ledger, ledger_rows)
        for repeat in range(1, 4):
            for arm in ("before", "after"):
                self._dump(self.root / f"repeat_{repeat}" / f"{arm}_manifest.json", self._manifest(arm, measurement))
                rows = []
                for index in range(1, 33):
                    wrong = arm == "after" and repeat in after_wrong_repeats and index == 1
                    hold = arm == "after" and repeat in after_hold_repeats and index == 1
                    result = self._result(index, "Wrong" if wrong else "Expected", publish=not hold, router_unknown=router_unknown, raw_identity_conflict=raw_identity_conflict, search_status=search_status)
                    preview = self._commit(result, index)
                    observation = build_publication_shadow_observation(observed_receipt=preview, authoritative_receipt=authorities[index])
                    if tamper and arm == "before" and repeat == 1 and index == 1:
                        observation["public_apply"] = True
                    result["run_meta"]["publication_shadow_observation"] = observation
                    # Commit storage includes the final serialized result, whereas the
                    # observation uses its stable decision view before receipt insertion.
                    final = self._commit(result, index)
                    rows.append({"global_idx": index, "post_id": index, "publication_commit": final, "result": result})
                self._jsonl(self.root / f"repeat_{repeat}" / f"{arm}_checkpoint.jsonl", rows)
        return ledger

    def test_receipt_validation_and_three_repeat_consensus(self) -> None:
        ledger = self._write_fixture(after_wrong_repeats={1, 2})
        rows, summary = build_report(self.root, ledger)
        self.assertEqual(32, len(rows))
        self.assertEqual("TWO_OF_THREE", rows[0]["after"]["modal_projection"]["fraction_label"])
        self.assertTrue(rows[0]["transition"]["source_recurrent_regression"]["after"])
        self.assertEqual("NO_GO", summary["semantic_auto_activation_gate"])

    def test_exact_set_mismatch_fails(self) -> None:
        ledger = self._write_fixture()
        path = self.root / "repeat_2" / "after_checkpoint.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        rows[-1]["post_id"] = 99
        self._jsonl(path, rows)
        with self.assertRaisesRegex(ValueError, "exact set mismatch"):
            build_report(self.root, ledger)

    def test_invalid_shadow_receipt_fails_closed(self) -> None:
        ledger = self._write_fixture(tamper=True)
        with self.assertRaisesRegex(ValueError, "shadow observation"):
            build_report(self.root, ledger)

    def test_actual_publication_wal_tamper_fails_closed(self) -> None:
        ledger = self._write_fixture()
        wal = self.root.parent / "publication_wal.jsonl"
        wal.write_text(
            wal.read_text(encoding="utf-8") + '{"sequence":33}\n',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "actual publication WAL SHA"):
            build_report(self.root, ledger)

    def test_measurement_not_estimable_and_causal_warning(self) -> None:
        ledger = self._write_fixture(measurement="NO_GO")
        _, summary = build_report(self.root, ledger)
        self.assertEqual("NOT_ESTIMABLE", summary["metrics"]["decision_calls_tokens_cost"]["total_tokens"]["status"])
        self.assertIn("does not establish a sidecar causal effect", summary["causal_warning"])
        self.assertEqual("NO_GO", summary["semantic_auto_activation_gate"])

    def test_hold_is_not_wrong_title_publish_and_router_unknown_is_not_green(self) -> None:
        ledger = self._write_fixture(after_hold_repeats={1, 2}, router_unknown=True)
        rows, summary = build_report(self.root, ledger)
        self.assertFalse(rows[0]["after"]["quality"]["wrong_title_publish"]["any_run"])
        self.assertEqual(0, summary["metrics"]["quality"]["wrong_title_publish"]["after"]["any_run_posts"])
        self.assertFalse(summary["metrics"]["router"]["before"]["green"])

    def test_validated_commit_authority_beats_conflicting_raw_identity_title(self) -> None:
        ledger = self._write_fixture(raw_identity_conflict=True)
        rows, _ = build_report(self.root, ledger)
        self.assertEqual("Expected", rows[0]["before"]["observed_projections"][0]["official_title"])

    def test_not_applicable_search_health_is_green_like_with_separate_coverage(self) -> None:
        ledger = self._write_fixture(search_status="NOT_APPLICABLE")
        _, summary = build_report(self.root, ledger)
        self.assertTrue(summary["metrics"]["search"]["before"]["green"])
        self.assertEqual(32 * 3, summary["metrics"]["search"]["before"]["not_applicable_rows"])

    def test_measurement_blind_replacement_override_preserves_original(self) -> None:
        ledger = self._write_fixture()
        original_manifest_path = self.root / "repeat_3" / "after_manifest.json"
        original_manifest = self._manifest("after", "NO_GO")
        original_manifest["run_id"] = "20260723_010000_000000"
        self._dump(original_manifest_path, original_manifest)

        replacement = self.root / "replacement" / "after.json"
        replacement_manifest = self._manifest("after", "GO")
        replacement_manifest["run_id"] = "20260723_020000_000000"
        self._dump(replacement.with_name("after_manifest.json"), replacement_manifest)
        original_checkpoint = self.root / "repeat_3" / "after_checkpoint.jsonl"
        replacement.with_name("after_checkpoint.jsonl").parent.mkdir(parents=True, exist_ok=True)
        replacement.with_name("after_checkpoint.jsonl").write_bytes(original_checkpoint.read_bytes())
        self._dump(replacement, [])

        policy = self.root / "replacement" / "retry_policy.json"
        self._dump(
            policy,
            {
                "schema_version": "measurement_incomplete_arm_replacement_policy_v1",
                "created_at_kst": "2026-07-23T01:30:00+09:00",
                "source_series_root": str(self.root.resolve()),
                "selection_policy": {
                    "semantic_result_blind": True,
                    "accept_first_terminal_attempt_matching_all_gates": True,
                    "original_or_prior_attempt_overwrite_allowed": False,
                },
            },
        )
        _, summary = build_report(
            self.root,
            ledger,
            attempt_overrides={(3, "after"): replacement},
            replacement_policy_path=policy,
        )
        self.assertEqual("GO", summary["measurement_gate"])
        self.assertEqual(
            "GO_MEASUREMENT_BLIND_REPLACEMENT_QUALIFIED",
            summary["attempt_selection"]["status"],
        )
        self.assertEqual("NO_GO", json.loads(original_manifest_path.read_text())["measurement_gate"]["status"])

    def test_override_without_policy_fails_closed(self) -> None:
        ledger = self._write_fixture()
        replacement = self.root / "repeat_3" / "after.json"
        with self.assertRaisesRegex(ValueError, "precommitted replacement policy"):
            build_report(
                self.root,
                ledger,
                attempt_overrides={(3, "after"): replacement},
            )

    def test_exact_independent_readback_promotes_pending_manifest_measurement(self) -> None:
        manifest = self._manifest("after", "GO")
        manifest["decision_call_ledger_summary"]["actual_kpi_status"] = (
            "PENDING_INDEPENDENT_READBACK"
        )
        status, reasons = _measurement_status_with_readback(
            manifest,
            {
                "gate_status": "GO",
                "aggregate_status": "EXACT",
                "actual_kpi_status": "EXACT",
                "measurement_completion_status": "EXACT",
                "usage": {"aggregate_exact": True},
                "reason_codes": [],
            },
        )
        self.assertEqual("GO", status)
        self.assertEqual([], reasons)

    def test_nonexact_independent_readback_fails_closed(self) -> None:
        manifest = self._manifest("after", "GO")
        status, reasons = _measurement_status_with_readback(
            manifest,
            {
                "gate_status": "NO-GO",
                "aggregate_status": "NOT_ESTIMABLE",
                "actual_kpi_status": "NOT_ESTIMABLE",
                "measurement_completion_status": "NOT_ESTIMABLE",
                "usage": {"aggregate_exact": False},
                "reason_codes": ["USAGE_ESTIMATED"],
            },
        )
        self.assertEqual("NO_GO", status)
        self.assertEqual(["USAGE_ESTIMATED"], reasons)


if __name__ == "__main__":
    unittest.main()
