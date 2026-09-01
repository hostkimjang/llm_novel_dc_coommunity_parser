from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from src.llm_batch.ledger.publication_commit import compute_publication_decision_commit
import tools.analyze_semantic_review_router_frozen2712 as router_analysis
from tools.analyze_semantic_review_router_frozen2712 import (
    COHORT_FILES,
    build_router_replay_report,
)


def _result(post_id: int, *, review: bool = False, not_applicable: bool = False) -> dict:
    identity = {
        "is_relevant": False,
        "work_resolution": "none" if not_applicable else "unresolved",
        "promotion_decision": {
            "publish_allowed": False,
            "official_title": None,
            "reason_codes": [],
            "scope": {"confidence": "low"},
            "bypassed_gate": False,
            "status": "candidate_only",
        },
        "promotion_gate_state": {"work_resolution": "none" if not_applicable else "unresolved"},
        "consistency_flags": ["ocr_explicit_title_unresolved"] if review else [],
        "output_consistency_lint": [],
        "title_candidates": None,
        "candidate_preservation_sources": None,
    }
    return {
        "post_id": post_id,
        "title": "test",
        "content": [],
        "comments": [],
        "image_count": 0 if not_applicable else 1,
        "error": "test error hold",
        "analysis_result": {"identity": identity},
        "run_meta": {},
    }


def _checkpoint(post_id: int, *, review: bool = False, not_applicable: bool = False) -> dict:
    result = _result(post_id, review=review, not_applicable=not_applicable)
    commit = compute_publication_decision_commit(
        result,
        publication_scope_id="a" * 64,
        attempt_run_id="router-analysis",
        input_index=post_id,
        post_id=post_id,
    )
    return {"global_idx": post_id, "post_id": post_id, "result": result, "publication_commit": commit.to_dict()}


def _ledger(post_id: int, verdict: str, action: str) -> dict:
    return {
        "post_id": str(post_id),
        "pipeline": {"publish_allowed": False, "official_title": None},
        "source_evidence": {"image_count": 0, "comments_count": 0, "explicit_ocr_titles": [], "title_candidates": []},
        "independent_semantic_verdict": {"review_verdict": verdict, "dashboard_action": action},
    }


class AnalyzeSemanticReviewRouterFrozen2712Test(unittest.TestCase):
    def _fixture(self):
        ledger = [_ledger(1, "FN_TITLE_MISSING", "CORRECT"), _ledger(2, "PASS", "KEEP"), _ledger(3, "NOISE_CORRECT", "NOT_APPLICABLE")]
        cohorts = {name: set() for name in COHORT_FILES}
        cohorts["fn_title_missing"] = {"1"}
        cohorts["pass"] = {"2"}
        cohorts["safe_no_title"] = {"3"}
        cohorts["ultra_safe_no_title"] = {"3"}
        return [_checkpoint(1, review=True), _checkpoint(2), _checkpoint(3, not_applicable=True)], ledger, [_result(1), _result(2), _result(3)], cohorts

    def test_replay_is_review_only_and_uses_offline_metrics(self) -> None:
        checkpoint, ledger, raw, cohorts = self._fixture()
        rows, summary = build_router_replay_report(checkpoint_rows=checkpoint, ledger_rows=ledger, raw_rows=raw, cohorts=cohorts)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["router"]["state"], "REVIEW_REQUIRED")
        self.assertEqual(summary["router"]["public_apply_true_rows"], 0)
        self.assertEqual(summary["noninterference"]["decision_id_drift_rows"], 0)
        self.assertEqual(summary["offline_evaluation_only"]["metrics"]["fn_title_missing"], {"routed": 1, "denominator": 1, "rate": 1.0})
        self.assertFalse(summary["gates"]["full_scan_approval"])

    def test_duplicate_missing_and_cohort_extra_fail_closed(self) -> None:
        checkpoint, ledger, raw, cohorts = self._fixture()
        with self.assertRaisesRegex(ValueError, "duplicate post_id"):
            build_router_replay_report(checkpoint_rows=checkpoint + [checkpoint[0]], ledger_rows=ledger, raw_rows=raw, cohorts=cohorts)
        with self.assertRaisesRegex(ValueError, "missing_checkpoint"):
            build_router_replay_report(checkpoint_rows=checkpoint[:2], ledger_rows=ledger, raw_rows=raw, cohorts=cohorts)
        bad = deepcopy(cohorts)
        bad["pass"] = {"99"}
        with self.assertRaisesRegex(ValueError, "post_id not in ledger"):
            build_router_replay_report(checkpoint_rows=checkpoint, ledger_rows=ledger, raw_rows=raw, cohorts=bad)

    def test_label_like_injection_does_not_change_router_receipt_or_state(self) -> None:
        checkpoint, ledger, raw, cohorts = self._fixture()
        first, _ = build_router_replay_report(checkpoint_rows=checkpoint, ledger_rows=ledger, raw_rows=raw, cohorts=cohorts)
        injected = deepcopy(ledger)
        injected[0]["manual_semantic_review_required"] = False
        second, _ = build_router_replay_report(checkpoint_rows=checkpoint, ledger_rows=injected, raw_rows=raw, cohorts=cohorts)
        self.assertEqual(first[0]["router"], second[0]["router"])

    def test_noninterference_drift_fails_closed(self) -> None:
        checkpoint, ledger, raw, cohorts = self._fixture()
        original = router_analysis.compute_publication_decision_commit

        def drift_after_attachment(result, **kwargs):
            computed = original(result, **kwargs)
            if "semantic_review_router_receipt" in result.get("run_meta", {}):
                return replace(computed, decision_id="0" * 64)
            return computed

        with patch.object(router_analysis, "compute_publication_decision_commit", side_effect=drift_after_attachment):
            _, summary = build_router_replay_report(checkpoint_rows=checkpoint, ledger_rows=ledger, raw_rows=raw, cohorts=cohorts)
        self.assertGreater(summary["noninterference"]["decision_id_drift_rows"], 0)
        self.assertEqual(summary["gates"]["integrity_gate"], "NO_GO")

    def test_metric_denominators_are_exact_and_overlaps_not_summed(self) -> None:
        checkpoint, ledger, raw, cohorts = self._fixture()
        cohorts["arbitration"] = {"1", "2"}
        rows, summary = build_router_replay_report(checkpoint_rows=checkpoint, ledger_rows=ledger, raw_rows=raw, cohorts=cohorts)
        metrics = summary["offline_evaluation_only"]["metrics"]
        self.assertEqual(metrics["arbitration"]["denominator"], 2)
        self.assertEqual(metrics["pass"]["denominator"], 1)
        self.assertEqual(metrics["safe_no_title"]["denominator"], 1)
        self.assertIn("중첩", summary["offline_evaluation_only"]["cohort_overlap_caveat_ko"])
        self.assertEqual(rows[0]["offline_evaluation"]["cohorts"], ["arbitration", "fn_title_missing"])


if __name__ == "__main__":
    unittest.main()
