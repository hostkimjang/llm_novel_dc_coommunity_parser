from __future__ import annotations

from copy import deepcopy
import socket
import unittest
from unittest.mock import patch

from src.llm_batch.ledger.publication_commit import compute_publication_decision_commit
from src.llm_batch.measurement.semantic_recovery_plan import (
    PLAN_HOLD,
    PLAN_NOT_APPLICABLE,
    PLAN_UNKNOWN,
    SemanticRecoveryPlanError,
    build_semantic_recovery_plan_receipt,
    validate_semantic_recovery_plan_receipt,
)


def _candidate(
    title: str,
    url: str,
    *,
    role: str = "primary",
    source_tier: str = "official_detail",
    page_type: str = "novel_page",
    content_status: str = "active",
) -> dict:
    return {
        "official_title": title,
        "heretic_url": url,
        "reference_role": role,
        "source_tier": source_tier,
        "page_type": page_type,
        "content_status": content_status,
    }


def _result(
    *,
    candidates: list[dict] | None = None,
    search: str | None = "HEALTHY",
    semantic: dict | None = None,
    not_applicable: bool = False,
    image_evidence: list[dict] | None = None,
) -> dict:
    candidates = candidates if candidates is not None else []
    work_resolution = "none" if not_applicable else "unresolved"
    identity = {
        "is_relevant": False,
        "work_resolution": work_resolution,
        "promotion_decision": {
            "publish_allowed": False,
            "official_title": None,
            "reason_codes": ["official_url_evidence_missing"] if candidates else [],
            "scope": {"confidence": "low"},
            "bypassed_gate": False,
            "status": "candidate_only",
        },
        "promotion_gate_state": {
            "work_resolution": work_resolution,
            "semantic_publication": semantic,
        },
        "title_candidates": candidates,
        "primary_work": None,
        "mentioned_works": None,
        "secondary_reference_works": [],
        "comparison_target": None,
        "image_evidence_catalog": image_evidence,
        "search_health": {"status": search} if search is not None else None,
    }
    return {
        "post_id": 101,
        "title": "plan test",
        "content": [],
        "comments": [],
        "image_count": 0,
        "error": "test error hold",
        "analysis_result": {"identity": identity},
        "run_meta": {},
    }


def _commit(result: dict):
    return compute_publication_decision_commit(
        result,
        publication_scope_id="a" * 64,
        attempt_run_id="plan-attempt",
        input_index=1,
        post_id=101,
    )


def _receipt(result: dict):
    commit = _commit(result)
    receipt = build_semantic_recovery_plan_receipt(
        result, commit, attempt_run_id="plan-attempt"
    )
    return commit, receipt


class SemanticRecoveryPlanTest(unittest.TestCase):
    def test_four_relation_roles_and_secondary_never_becomes_primary(self) -> None:
        candidates = [
            _candidate("Primary", "https://novelpia.com/novel/101", role="primary"),
            _candidate("Previous", "https://novelpia.com/novel/102", role="previous"),
            _candidate("Mentioned", "https://page.kakao.com/content/103", role="mentioned"),
            _candidate("Compared", "https://series.naver.com/novel/detail.series?productNo=104", role="comparison"),
            _candidate("Secondary", "https://novelpia.com/novel/105", role="secondary"),
        ]
        _, receipt = _receipt(_result(candidates=candidates))
        counts = receipt["plan"]["relationship_counts"]
        self.assertEqual(counts, {"comparison": 1, "mentioned": 2, "previous": 1, "primary": 1})
        secondary_binding = next(
            item for item in receipt["plan"]["canonical_bindings"] if item["canonical_work_id"] == "novelpia:105"
        )
        self.assertEqual(secondary_binding["relation_role"], "mentioned")

    def test_multiple_primary_is_ambiguous_hold(self) -> None:
        candidates = [
            _candidate("First", "https://novelpia.com/novel/201"),
            _candidate("Second", "https://novelpia.com/novel/202"),
        ]
        _, receipt = _receipt(_result(candidates=candidates))
        self.assertEqual(receipt["plan"]["state"], PLAN_HOLD)
        self.assertIn("MULTIPLE_PRIMARY", receipt["plan"]["blocker_codes"])
        self.assertEqual(receipt["plan"]["primary_identity_count"], 2)

    def test_missing_primary_is_hold_and_secondary_stays_non_primary(self) -> None:
        secondary = _candidate(
            "Reference", "https://novelpia.com/novel/203", role="secondary"
        )
        _, receipt = _receipt(_result(candidates=[secondary]))
        self.assertEqual(receipt["plan"]["state"], PLAN_HOLD)
        self.assertIn("MISSING_PRIMARY", receipt["plan"]["blocker_codes"])
        self.assertEqual(receipt["plan"]["primary_identity_count"], 0)
        self.assertEqual(receipt["plan"]["relationship_counts"]["primary"], 0)

    def test_typed_non_novel_quarantine_and_cross_media_hold(self) -> None:
        non_novel = _candidate(
            "Typed Media", "https://novelpia.com/novel/301", page_type="news_page"
        )
        _, receipt = _receipt(_result(candidates=[non_novel]))
        self.assertEqual(receipt["plan"]["media_action"], "QUARANTINE_NON_NOVEL")
        self.assertIn("TYPED_NON_NOVEL_MEDIA", receipt["plan"]["blocker_codes"])
        _, title_only = _receipt(
            _result(
                candidates=[
                    _candidate(
                        "News-Like Surface",
                        "https://novelpia.com/novel/303",
                        page_type="novel_page",
                    )
                ]
            )
        )
        self.assertEqual(title_only["plan"]["media_action"], "NO_MEDIA_ACTION")
        _, cross = _receipt(
            _result(
                candidates=[_candidate("Cross", "https://novelpia.com/novel/302")],
                semantic={
                    "evidence_status": "sufficient",
                    "media_domain_class": "cross_media_unresolved",
                    "primary_work_status": "unique",
                },
            )
        )
        self.assertEqual(cross["plan"]["media_action"], "HOLD_CROSS_MEDIA")
        self.assertIn("CROSS_MEDIA_CONFLICT", cross["plan"]["blocker_codes"])

    def test_stable_platform_bindings_and_malformed_or_listing_reject(self) -> None:
        cases = (
            ("https://page.kakao.com/content/401", "kakao:401"),
            ("https://series.naver.com/novel/detail.series?productNo=402", "naver:402"),
            ("https://novelpia.com/novel/403", "novelpia:403"),
        )
        for url, expected_id in cases:
            with self.subTest(url=url):
                _, receipt = _receipt(_result(candidates=[_candidate("Official", url)]))
                self.assertEqual(receipt["plan"]["canonical_bindings"][0]["canonical_work_id"], expected_id)
        rejected = (
            "https://novelpia.com/novel/all",
            "https://novelpia.com/novel/title-slug",
            "https://page.kakao.com/content/hash-value",
            "https://series.naver.com/novel/home.series",
        )
        for url in rejected:
            with self.subTest(url=url):
                _, receipt = _receipt(_result(candidates=[_candidate("Rejected", url)]))
                self.assertEqual(receipt["plan"]["canonical_bindings"], [])
                self.assertIn("OFFICIAL_DETAIL_ID_UNAVAILABLE", receipt["plan"]["blocker_codes"])
        listing = _candidate(
            "Listing",
            "https://novelpia.com/novel/404",
            page_type="search_result",
        )
        deleted = _candidate(
            "Deleted",
            "https://novelpia.com/novel/405",
            content_status="deleted",
        )
        for candidate in (listing, deleted):
            _, receipt = _receipt(_result(candidates=[candidate]))
            self.assertEqual(receipt["plan"]["canonical_bindings"], [])
            self.assertIn("OFFICIAL_DETAIL_ID_UNAVAILABLE", receipt["plan"]["blocker_codes"])

    def test_canonical_collisions_hold(self) -> None:
        one_id_two_displays = [
            _candidate("Display One", "https://novelpia.com/novel/501"),
            _candidate("Display Two", "https://novelpia.com/novel/501"),
        ]
        _, first = _receipt(_result(candidates=one_id_two_displays))
        self.assertIn("CANONICAL_ID_DISPLAY_COLLISION", first["plan"]["blocker_codes"])
        one_display_two_ids = [
            _candidate("Same Display", "https://novelpia.com/novel/502"),
            _candidate("Same Display", "https://novelpia.com/novel/503"),
        ]
        _, second = _receipt(_result(candidates=one_display_two_ids))
        self.assertIn("CANONICAL_ID_DISPLAY_COLLISION", second["plan"]["blocker_codes"])

    def test_raw_ocr_title_is_counted_but_never_rendered(self) -> None:
        image = {
            "evidence_type": "explicit_text",
            "title_role": "work_title",
            "explicit_work_title": "Raw OCR Only",
        }
        ocr_candidate = _candidate(
            "Raw OCR Only",
            "https://novelpia.com/novel/601",
            source_tier="ocr",
        )
        _, receipt = _receipt(_result(candidates=[ocr_candidate], image_evidence=[image]))
        self.assertEqual(receipt["plan"]["raw_ocr_evidence_count"], 1)
        self.assertEqual(receipt["plan"]["canonical_bindings"], [])
        self.assertNotIn("Raw OCR Only", json_text(receipt["plan"]["canonical_bindings"]))

    def test_degraded_unknown_not_applicable_and_healthy_hold_query_plan(self) -> None:
        candidate = _candidate("Needs Check", "https://novelpia.com/novel/not-a-number")
        for status in ("SEARCH_DEGRADED", None):
            with self.subTest(status=status):
                _, receipt = _receipt(_result(candidates=[candidate], search=status))
                query = receipt["plan"]["query_plan"]
                self.assertFalse(query["query_execution_allowed"])
                self.assertEqual(query["max_queries"], 0)
        _, healthy = _receipt(_result(candidates=[candidate], search="HEALTHY"))
        self.assertTrue(healthy["plan"]["query_plan"]["query_execution_allowed"])
        self.assertGreater(healthy["plan"]["query_plan"]["max_queries"], 0)
        _, not_applicable = _receipt(_result(not_applicable=True, search=None))
        self.assertEqual(not_applicable["plan"]["state"], PLAN_NOT_APPLICABLE)
        self.assertEqual(not_applicable["plan"]["query_plan"]["max_queries"], 0)

    def test_plan_build_has_no_search_or_network_calls(self) -> None:
        result = _result(candidates=[_candidate("No Calls", "https://novelpia.com/novel/701")])
        commit = _commit(result)
        with patch.object(socket, "create_connection", side_effect=AssertionError("network call")) as network:
            receipt = build_semantic_recovery_plan_receipt(
                result, commit, attempt_run_id="plan-attempt"
            )
        network.assert_not_called()
        self.assertEqual(receipt["plan"]["search_calls_executed"], 0)
        self.assertEqual(receipt["plan"]["network_calls_executed"], 0)

    def test_missing_typed_input_is_unknown(self) -> None:
        result = _result()
        result["analysis_result"]["identity"].pop("promotion_gate_state")
        commit = _commit(result)
        receipt = build_semantic_recovery_plan_receipt(
            result, commit, attempt_run_id="plan-attempt"
        )
        self.assertEqual(receipt["plan"]["state"], PLAN_UNKNOWN)

    def test_label_and_judge_seed_injection_do_not_change_source_or_plan(self) -> None:
        result = _result(candidates=[_candidate("Stable", "https://novelpia.com/novel/801")])
        _, first = _receipt(result)
        injected = deepcopy(result)
        injected["analysis_result"]["identity"]["manual_semantic_review_required"] = True
        injected["judge_seed"] = {"expected_title": "Injected"}
        injected_commit = _commit(injected)
        second = build_semantic_recovery_plan_receipt(
            injected, injected_commit, attempt_run_id="plan-attempt"
        )
        self.assertEqual(first["source_view"], second["source_view"])
        self.assertEqual(first["plan"], second["plan"])

    def test_tamper_binding_and_stable_noninterference(self) -> None:
        result = _result(candidates=[_candidate("Bound", "https://novelpia.com/novel/901")])
        commit, receipt = _receipt(result)
        self.assertEqual(
            validate_semantic_recovery_plan_receipt(
                receipt,
                result=result,
                expected_publication_receipt=commit,
                expected_scope_id="a" * 64,
                expected_input_index=1,
                expected_post_id=101,
                expected_attempt_run_id="plan-attempt",
            ),
            receipt,
        )
        forged = deepcopy(receipt)
        forged["plan"]["state"] = PLAN_NOT_APPLICABLE
        with self.assertRaisesRegex(SemanticRecoveryPlanError, "plan hash mismatch"):
            validate_semantic_recovery_plan_receipt(forged)
        extra = dict(receipt)
        extra["unexpected"] = True
        with self.assertRaisesRegex(SemanticRecoveryPlanError, "fields mismatch"):
            validate_semantic_recovery_plan_receipt(extra)
        with self.assertRaisesRegex(SemanticRecoveryPlanError, "input_index mismatch"):
            validate_semantic_recovery_plan_receipt(receipt, expected_input_index=2)
        wrong_binding = compute_publication_decision_commit(
            result,
            publication_scope_id="a" * 64,
            attempt_run_id="plan-attempt",
            input_index=2,
            post_id=101,
        )
        with self.assertRaisesRegex(
            SemanticRecoveryPlanError, "publication receipt input_index mismatch"
        ):
            validate_semantic_recovery_plan_receipt(
                receipt, expected_publication_receipt=wrong_binding
            )
        result["run_meta"]["semantic_recovery_plan_receipt"] = receipt
        after = _commit(result)
        self.assertEqual(after.stable_result_sha256, commit.stable_result_sha256)
        self.assertEqual(after.decision_id, commit.decision_id)
        self.assertEqual(after.public_projection_sha256, commit.public_projection_sha256)
        self.assertNotEqual(after.result_sha256, commit.result_sha256)


def json_text(value: object) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True)


if __name__ == "__main__":
    unittest.main()
