"""Regression guard for the typed search fail-close publish contract (P0).

Covers the improvement described in
``docs/devs/LLM_PIPELINE_ARCHITECTURE_RESEARCH_20260711.md`` step 1: a row that
requires external-source search grounding must not publish a public title when
that grounding was attempted but not recovered, and this must hold on typed
``RetrievalState`` input alone -- without depending on an upstream stage
emitting a free-form ``search_evidence_missing`` reason code.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm_batch.promotion_gate import (  # noqa: E402
    EvidenceRecord,
    GroundingState,
    RetrievalState,
    ScopeState,
    can_publish_title,
    grounding_state_from_dict,
    publish_input_fingerprint,
)
from tools.search_fail_close_probe import build_report  # noqa: E402


def _publishable_evidence(title: str) -> list[EvidenceRecord]:
    return [
        EvidenceRecord(
            kind="alias_bridge",
            strength="strong",
            source_path_or_snippet=title,
            supports_publish=True,
            reason_code="alias_bridge",
            candidate_title=title,
        )
    ]


def _state(title: str, retrieval):
    return GroundingState(
        post_id=1,
        candidate_title=title,
        candidate_url="",
        official_title_exists=True,
        row_discusses_work_as_work=True,
        scope=ScopeState(
            scope_kind="current_work",
            confidence="high",
            direct_bridge_sources=["explicit_alias_relation"],
        ),
        retrieval=retrieval,
    )


class RetrievalStateFailCloseTest(unittest.TestCase):
    def test_baseline_gap_publishes_without_typed_retrieval(self):
        title = "아카데미 생존 갤러리"
        decision = can_publish_title(_state(title, None), _publishable_evidence(title))
        # Pre-improvement behaviour: with no typed search input and no search
        # reason code, the row publishes. This documents the limitation.
        self.assertEqual(decision.status, "publish")
        self.assertTrue(decision.publish_allowed)

    def test_required_unrecovered_search_fails_close(self):
        title = "아카데미 생존 갤러리"
        retrieval = RetrievalState(required=True, attempted=True, recovered=False)
        decision = can_publish_title(_state(title, retrieval), _publishable_evidence(title))
        self.assertFalse(decision.publish_allowed)
        self.assertEqual(decision.status, "candidate_only")
        self.assertIn("search_evidence_missing", decision.reason_codes)
        self.assertTrue(decision.candidate_preserved)
        self.assertIsNone(decision.official_title)

    def test_hard_blocked_search_fails_close(self):
        title = "던전 리셋"
        retrieval = RetrievalState(required=True, attempted=True, recovered=False, hard_blocked=True)
        decision = can_publish_title(_state(title, retrieval), _publishable_evidence(title))
        self.assertFalse(decision.publish_allowed)
        self.assertIn("search_blind_condition", decision.reason_codes)

    def test_recovered_search_still_publishes(self):
        title = "화산귀환"
        retrieval = RetrievalState(required=True, attempted=True, recovered=True)
        decision = can_publish_title(_state(title, retrieval), _publishable_evidence(title))
        self.assertTrue(decision.publish_allowed)
        self.assertEqual(decision.status, "publish")

    def test_search_not_required_still_publishes(self):
        title = "나 혼자만 레벨업"
        retrieval = RetrievalState(required=False, attempted=False, recovered=False)
        decision = can_publish_title(_state(title, retrieval), _publishable_evidence(title))
        self.assertTrue(decision.publish_allowed)

    def test_default_retrieval_preserves_v2_fingerprint(self):
        title = "아카데미 생존 갤러리"
        ev = _publishable_evidence(title)
        fp_none = publish_input_fingerprint(_state(title, None), ev)
        fp_default = publish_input_fingerprint(_state(title, RetrievalState()), ev)
        self.assertEqual(fp_none, fp_default)
        self.assertEqual(len(fp_none), 64)

    def test_populated_retrieval_changes_fingerprint(self):
        title = "아카데미 생존 갤러리"
        ev = _publishable_evidence(title)
        fp_none = publish_input_fingerprint(_state(title, None), ev)
        fp_populated = publish_input_fingerprint(
            _state(title, RetrievalState(required=True, attempted=True)), ev
        )
        self.assertNotEqual(fp_none, fp_populated)

    def test_populated_retrieval_survives_serialized_roundtrip(self):
        retrieval = RetrievalState(
            required=True,
            attempted=True,
            recovered=False,
            hard_blocked=True,
            reason_codes=("provider_timeout",),
        )
        state = _state("아카데미 생존 갤러리", retrieval)
        restored = grounding_state_from_dict(state.to_dict())
        self.assertIsNotNone(restored.retrieval)
        self.assertEqual(retrieval, restored.retrieval)
        decision = can_publish_title(restored, _publishable_evidence(state.candidate_title))
        self.assertFalse(decision.publish_allowed)
        self.assertIn("search_blind_condition", decision.reason_codes)
        self.assertIn("provider_timeout", decision.reason_codes)

    def test_retrieval_boolean_fields_are_strict(self):
        with self.assertRaisesRegex(ValueError, "required must be a bool"):
            RetrievalState(required="false")
        state = _state("아카데미 생존 갤러리", None).to_dict()
        state["retrieval"] = {"required": 1}
        with self.assertRaisesRegex(ValueError, "retrieval.required must be a bool"):
            grounding_state_from_dict(state)

    def test_probe_reports_zero_unsafe_after(self):
        report = build_report()
        repeated = build_report()
        self.assertEqual(report["before"]["unsafe_publish_count"], 5)
        self.assertEqual(report["after"]["unsafe_publish_count"], 0)
        self.assertEqual(report["improvement"]["unsafe_publish_reduced_by"], 5)
        self.assertTrue(report["improvement"]["correct_publish_preserved"])
        self.assertTrue(report["improvement"]["no_correct_publish_lost"])
        self.assertEqual(64, len(report["scenario_set_sha256"]))
        self.assertEqual(report, repeated)


if __name__ == "__main__":
    unittest.main()
