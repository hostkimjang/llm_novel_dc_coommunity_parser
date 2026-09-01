from __future__ import annotations

from copy import deepcopy
import unittest

from src.llm_batch.ledger.publication_commit import compute_publication_decision_commit
from src.llm_batch.measurement.semantic_review_router import (
    NO_REVIEW,
    NOT_APPLICABLE,
    REVIEW_REQUIRED,
    UNKNOWN,
    SemanticReviewRouterError,
    build_semantic_review_router_receipt,
    validate_semantic_review_router_receipt,
)


def _result(*, kind: str = "review") -> dict:
    identity = {
        "is_relevant": False,
        "work_resolution": "unresolved",
        "promotion_decision": {
            "publish_allowed": False,
            "official_title": None,
            "reason_codes": [],
            "scope": {"confidence": "low"},
            "bypassed_gate": False,
            "status": "candidate_only",
        },
        "promotion_gate_state": {"work_resolution": "unresolved"},
        "consistency_flags": ["ocr_explicit_title_unresolved"],
        "output_consistency_lint": [],
        "title_candidates": [],
        "candidate_preservation_sources": [],
    }
    result = {
        "post_id": 101,
        "title": "router test",
        "content": [],
        "comments": [],
        "image_count": 1,
        "error": "test-only error hold",
        "analysis_result": {"identity": identity},
        "run_meta": {},
    }
    if kind == "no_review":
        identity["consistency_flags"] = []
        result["image_count"] = 1
    elif kind == "not_applicable":
        identity.update({"is_relevant": False, "work_resolution": "none"})
        identity["promotion_gate_state"] = {"work_resolution": "none"}
        identity["consistency_flags"] = []
        identity["title_candidates"] = None
        identity["candidate_preservation_sources"] = None
        result["image_count"] = 0
    elif kind == "unknown":
        identity.pop("promotion_gate_state")
    return result


def _commit(result: dict):
    return compute_publication_decision_commit(
        result,
        publication_scope_id="a" * 64,
        attempt_run_id="router-attempt",
        input_index=1,
        post_id=101,
    )


class SemanticReviewRouterTest(unittest.TestCase):
    def _receipt(self, *, kind: str = "review"):
        result = _result(kind=kind)
        commit = _commit(result)
        receipt = build_semantic_review_router_receipt(
            result, commit, attempt_run_id="router-attempt"
        )
        return result, commit, receipt

    def test_review_receipt_is_self_hashed_and_bound(self) -> None:
        result, commit, receipt = self._receipt()
        self.assertEqual(receipt["state"], REVIEW_REQUIRED)
        self.assertEqual(receipt["trigger_codes"], ["OCR_TITLE_UNRESOLVED"])
        self.assertFalse(receipt["public_apply"])
        self.assertEqual(
            validate_semantic_review_router_receipt(
                receipt,
                result=result,
                expected_publication_receipt=commit,
                expected_scope_id="a" * 64,
                expected_input_index=1,
                expected_post_id=101,
                expected_attempt_run_id="router-attempt",
            ),
            receipt,
        )

    def test_no_review_not_applicable_and_unknown_are_explicit(self) -> None:
        self.assertEqual(self._receipt(kind="no_review")[2]["state"], NO_REVIEW)
        self.assertEqual(self._receipt(kind="not_applicable")[2]["state"], NOT_APPLICABLE)
        unknown = self._receipt(kind="unknown")[2]
        self.assertEqual(unknown["state"], UNKNOWN)
        self.assertEqual(unknown["trigger_codes"], [])
        self.assertIn("MISSING_PROMOTION_GATE_STATE", unknown["unknown_reason_codes"])

    def test_tamper_extra_field_and_coordinate_mismatch_fail_closed(self) -> None:
        result, commit, receipt = self._receipt()
        forged = deepcopy(receipt)
        forged["receipt_sha256"] = "0" * 64
        with self.assertRaisesRegex(SemanticReviewRouterError, "receipt hash mismatch"):
            validate_semantic_review_router_receipt(forged)
        forged_source = deepcopy(receipt)
        forged_source["source_view"]["work_resolution"] = "none"
        with self.assertRaisesRegex(
            SemanticReviewRouterError, "source_view hash mismatch"
        ):
            validate_semantic_review_router_receipt(forged_source)
        extra = dict(receipt)
        extra["unexpected"] = True
        with self.assertRaisesRegex(SemanticReviewRouterError, "fields mismatch"):
            validate_semantic_review_router_receipt(extra)
        with self.assertRaisesRegex(SemanticReviewRouterError, "input_index mismatch"):
            validate_semantic_review_router_receipt(
                receipt, result=result, expected_input_index=2
            )
        with self.assertRaisesRegex(SemanticReviewRouterError, "publication receipt input_index mismatch"):
            other = deepcopy(commit.to_dict())
            other["input_index"] = 2
            validate_semantic_review_router_receipt(
                receipt, expected_publication_receipt=other
            )

    def test_unrelated_label_like_input_is_not_consumed(self) -> None:
        result, commit, first = self._receipt(kind="no_review")
        injected = deepcopy(result)
        injected["analysis_result"]["identity"]["independent_semantic_verdict"] = {
            "review_verdict": "FORCE_REVIEW",
            "dashboard_action": "CORRECT",
        }
        injected["analysis_result"]["identity"]["manual_semantic_review_required"] = True
        second = build_semantic_review_router_receipt(
            injected, commit, attempt_run_id="router-attempt"
        )
        self.assertEqual(first, second)

    def test_attempt_local_receipt_does_not_change_stable_hash_or_decision(self) -> None:
        result, commit, receipt = self._receipt()
        result["run_meta"]["semantic_review_router_receipt"] = receipt
        after = _commit(result)
        self.assertEqual(after.stable_result_sha256, commit.stable_result_sha256)
        self.assertEqual(after.decision_id, commit.decision_id)
        self.assertNotEqual(after.result_sha256, commit.result_sha256)


if __name__ == "__main__":
    unittest.main()
