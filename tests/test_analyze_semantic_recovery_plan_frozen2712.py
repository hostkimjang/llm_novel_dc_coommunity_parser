from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.llm_batch.ledger.publication_commit import compute_publication_decision_commit
import tools.analyze_semantic_recovery_plan_frozen2712 as analysis
from tools.analyze_semantic_recovery_plan_frozen2712 import (
    _atomic_write,
    build_recovery_plan_replay_report,
)


def _candidate(post_id: int) -> dict:
    return {
        "official_title": f"Work {post_id}",
        "heretic_url": f"https://novelpia.com/novel/{post_id}",
        "reference_role": "primary",
        "source_tier": "official_detail",
        "page_type": "novel_page",
        "content_status": "active",
    }


def _result(post_id: int, *, candidate: bool = False, not_applicable: bool = False) -> dict:
    work_resolution = "none" if not_applicable else "unresolved"
    candidates = [_candidate(post_id)] if candidate else []
    return {
        "post_id": post_id,
        "title": "test",
        "content": [],
        "comments": [],
        "image_count": 0,
        "error": "test error hold",
        "analysis_result": {
            "identity": {
                "is_relevant": False,
                "work_resolution": work_resolution,
                "promotion_decision": {
                    "publish_allowed": False,
                    "official_title": None,
                    "reason_codes": ["official_url_evidence_missing"] if candidate else [],
                    "scope": {"confidence": "low"},
                    "bypassed_gate": False,
                    "status": "candidate_only",
                },
                "promotion_gate_state": {
                    "work_resolution": work_resolution,
                    "semantic_publication": None,
                },
                "title_candidates": candidates,
                "primary_work": None,
                "mentioned_works": None,
                "secondary_reference_works": [],
                "comparison_target": None,
                "image_evidence_catalog": None,
                "search_health": {"status": "HEALTHY"},
            }
        },
        "run_meta": {},
    }


def _checkpoint(
    post_id: int, *, candidate: bool = False, not_applicable: bool = False
) -> dict:
    result = _result(post_id, candidate=candidate, not_applicable=not_applicable)
    commit = compute_publication_decision_commit(
        result,
        publication_scope_id="a" * 64,
        attempt_run_id="analysis-attempt",
        input_index=post_id,
        post_id=post_id,
    )
    return {
        "global_idx": post_id,
        "post_id": post_id,
        "status": "completed",
        "result": result,
        "publication_commit": commit.to_dict(),
    }


def _ledger(post_id: int, verdict: str, action: str) -> dict:
    return {
        "post_id": str(post_id),
        "pipeline": {"publish_allowed": False, "official_title": None},
        "source_evidence": {
            "image_count": 0,
            "comments_count": 0,
            "explicit_ocr_titles": [],
            "title_candidates": [],
        },
        "independent_semantic_verdict": {
            "review_verdict": verdict,
            "dashboard_action": action,
        },
    }


class AnalyzeSemanticRecoveryPlanFrozen2712Test(unittest.TestCase):
    def _fixture(self):
        checkpoint = [
            _checkpoint(1, candidate=True),
            _checkpoint(2, not_applicable=True),
            _checkpoint(3, candidate=True),
            _checkpoint(99, not_applicable=True),
        ]
        ledger = [
            _ledger(1, "FN_TITLE_MISSING", "CORRECT"),
            _ledger(2, "PASS", "KEEP"),
            _ledger(3, "NOISE_CORRECT", "NOT_APPLICABLE"),
        ]
        return checkpoint, ledger

    def test_replay_coverage_breakdowns_and_noninterference(self) -> None:
        checkpoint, ledger = self._fixture()
        rows, summary = build_recovery_plan_replay_report(
            checkpoint_rows=checkpoint, ledger_rows=ledger
        )
        self.assertEqual(len(rows), 3)
        self.assertEqual(summary["coverage"]["raw_extra_rows"], 1)
        self.assertEqual(summary["coverage"]["receipt_covered_rows"], 3)
        self.assertEqual(summary["noninterference"]["decision_id_drift_rows"], 0)
        self.assertEqual(summary["plan"]["search_calls_executed"], 0)
        self.assertEqual(summary["plan"]["network_calls_executed"], 0)
        self.assertEqual(summary["plan"]["public_apply_true_rows"], 0)
        self.assertGreater(summary["plan"]["canonical_binding_rows"], 0)
        self.assertEqual(
            summary["offline_evaluation_only"]["verdict"]["FN_TITLE_MISSING"][
                "denominator"
            ],
            1,
        )
        self.assertEqual(
            summary["offline_evaluation_only"]["cohort"]["high_risk_union"][
                "denominator"
            ],
            1,
        )
        self.assertEqual(
            summary["offline_evaluation_only"]["cohort"]["safe_no_title"][
                "denominator"
            ],
            1,
        )
        self.assertEqual(summary["gates"]["integrity_gate"], "GO")
        self.assertEqual(summary["gates"]["semantic_effectiveness_gate"], "NO_GO")

    def test_duplicate_and_missing_fail_closed(self) -> None:
        checkpoint, ledger = self._fixture()
        with self.assertRaisesRegex(ValueError, "duplicate post_id"):
            build_recovery_plan_replay_report(
                checkpoint_rows=checkpoint + [checkpoint[0]], ledger_rows=ledger
            )
        with self.assertRaisesRegex(ValueError, "missing ledger post_id"):
            build_recovery_plan_replay_report(
                checkpoint_rows=checkpoint[1:], ledger_rows=ledger
            )

    def test_label_injection_changes_only_offline_breakdown(self) -> None:
        checkpoint, ledger = self._fixture()
        first_rows, _ = build_recovery_plan_replay_report(
            checkpoint_rows=checkpoint, ledger_rows=ledger
        )
        injected = deepcopy(ledger)
        injected[0]["manual_semantic_review_required"] = False
        injected[0]["independent_semantic_verdict"]["review_verdict"] = (
            "EVIDENCE_CONFLICT"
        )
        injected[0]["independent_semantic_verdict"]["dashboard_action"] = "HOLD"
        second_rows, _ = build_recovery_plan_replay_report(
            checkpoint_rows=checkpoint, ledger_rows=injected
        )
        self.assertEqual(first_rows[0]["plan_receipt"], second_rows[0]["plan_receipt"])
        self.assertEqual(first_rows[0]["noninterference"], second_rows[0]["noninterference"])
        self.assertNotEqual(
            first_rows[0]["offline_evaluation"],
            second_rows[0]["offline_evaluation"],
        )

    def test_drift_forces_integrity_no_go(self) -> None:
        checkpoint, ledger = self._fixture()
        original = analysis.compute_publication_decision_commit

        def drift_after_attach(result, **kwargs):
            computed = original(result, **kwargs)
            if "semantic_recovery_plan_receipt" in result.get("run_meta", {}):
                return replace(computed, stable_result_sha256="0" * 64)
            return computed

        with patch.object(
            analysis,
            "compute_publication_decision_commit",
            side_effect=drift_after_attach,
        ):
            _, summary = build_recovery_plan_replay_report(
                checkpoint_rows=checkpoint, ledger_rows=ledger
            )
        self.assertGreater(
            summary["noninterference"]["stable_result_sha256_drift_rows"], 0
        )
        self.assertEqual(summary["gates"]["integrity_gate"], "NO_GO")

    def test_atomic_writer_replaces_complete_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "summary.json"
            _atomic_write(path, "first\n")
            _atomic_write(path, "second\n")
            self.assertEqual(path.read_text(encoding="utf-8"), "second\n")
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
