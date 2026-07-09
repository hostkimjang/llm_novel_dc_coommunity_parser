import unittest

from tools.build_official_support_enrichment_review import build_review


class BuildOfficialSupportEnrichmentReviewTest(unittest.TestCase):
    def _contract_plan(self):
        return {
            "plan_id": "unit_restore_plan",
            "rows": [
                {
                    "post_id": 1,
                    "contract_action": "official_support_missing_restore_hold_contract_case",
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "REPROCESS",
                    "target_title": "Expected Work",
                    "evidence_grade": "Strong",
                    "source_native_verdict": "supported_safe_title_lost_to_null",
                    "rationale_ko": "원문이 Expected Work를 직접 지지한다.",
                    "evidence_refs": ["docs/devs/source.json#post_id=1"],
                },
                {
                    "post_id": 2,
                    "contract_action": "official_support_missing_restore_hold_contract_case",
                    "target_title": "화산파(화산귀환)",
                    "evidence_grade": "Strong",
                    "rationale_ko": "화귀 댓글 맥락.",
                    "evidence_refs": [],
                },
                {
                    "post_id": 3,
                    "contract_action": "official_support_missing_restore_hold_contract_case",
                    "target_title": "인간실격",
                    "evidence_grade": "Strong",
                    "rationale_ko": "고전 문학 맥락.",
                    "evidence_refs": [],
                },
                {
                    "post_id": 4,
                    "contract_action": "expected_title_restore_contract_case",
                    "target_title": "Already Ready",
                },
            ],
        }

    def _reviewed_refs(self):
        return {
            "review_id": "unit_review",
            "rows": [
                {
                    "post_id": 1,
                    "official_support_state": "official_detail_exact_title_found",
                    "official_title": "Expected Work",
                    "official_url": "https://novelpia.com/novel/123",
                    "accepted_by_shared_official_detail_contract": True,
                    "source_urls": ["https://novelpia.com/novel/123"],
                    "source_evidence_ko": "공식 detail이 target title과 일치한다.",
                },
                {
                    "post_id": 2,
                    "official_support_state": "official_detail_found_target_title_mismatch",
                    "official_title": "화산귀환",
                    "official_url": "https://series.naver.com/novel/detail.series?productNo=4130558",
                    "accepted_by_shared_official_detail_contract": False,
                    "hold_reason_ko": "target title과 공식 title이 다르다.",
                },
                {
                    "post_id": 3,
                    "official_support_state": "ebook_or_classic_policy_review_required",
                    "official_title": "인간실격",
                    "official_url": "https://series.naver.com/ebook/detail.series?productNo=8927664",
                    "accepted_by_shared_official_detail_contract": False,
                    "hold_reason_ko": "eBook/classic 정책 검토 대상이다.",
                },
            ],
        }

    def test_exact_official_detail_rows_become_enriched_dispatch_only(self):
        report, dispatch = build_review(
            contract_plan=self._contract_plan(),
            reviewed_refs=self._reviewed_refs(),
            review_id="unit_review",
        )

        self.assertEqual(report["gate"], "REVIEW-LOCKED")
        self.assertEqual(report["summary"]["source_official_missing_hold_rows"], 3)
        self.assertEqual(report["summary"]["enriched_restore_dispatch_rows"], 1)
        self.assertEqual(report["summary"]["hold_rows"], 2)
        self.assertEqual(report["summary"]["runtime_replay_allowed_rows"], 0)
        self.assertEqual(dispatch["summary"]["enriched_restore_dispatch_rows"], 1)
        self.assertEqual(dispatch["rows"][0]["post_id"], 1)
        self.assertEqual(dispatch["rows"][0]["dispatch_lane"], "shared_gate_restore_contract_review")
        self.assertEqual(dispatch["rows"][0]["selected_title"], "Expected Work")
        self.assertEqual(dispatch["rows"][0]["selected_url"], "https://novelpia.com/novel/123")
        self.assertEqual(dispatch["rows"][0]["evidence_refs"][0], "https://novelpia.com/novel/123")
        self.assertFalse(dispatch["rows"][0]["runtime_replay_allowed"])

    def test_title_mismatch_and_ebook_policy_hold_do_not_dispatch(self):
        report, dispatch = build_review(
            contract_plan=self._contract_plan(),
            reviewed_refs=self._reviewed_refs(),
            review_id="unit_review",
        )
        rows = {row["post_id"]: row for row in report["rows"]}

        self.assertEqual(rows[2]["review_action"], "canonical_title_rewrite_review_required")
        self.assertFalse(rows[2]["enriched_restore_dispatch_row"])
        self.assertEqual(rows[3]["review_action"], "non_webnovel_ebook_policy_hold")
        self.assertFalse(rows[3]["webnovel_detail_url_supported"])
        self.assertFalse(rows[3]["enriched_restore_dispatch_row"])
        self.assertEqual([row["post_id"] for row in dispatch["rows"]], [1])

    def test_canonical_rewrite_allowed_title_mismatch_becomes_dispatch(self):
        refs = self._reviewed_refs()
        refs["rows"][1].update(
            {
                "canonical_rewrite_allowed": True,
                "canonical_rewrite_title": "화산귀환",
                "source_native_rewrite_support": True,
                "alias_relation_supported": True,
                "rewrite_reason_ko": "화귀/해남편 근거는 화산귀환을 가리키며 화산파는 작품 공식 title이 아니다.",
            }
        )

        report, dispatch = build_review(
            contract_plan=self._contract_plan(),
            reviewed_refs=refs,
            review_id="unit_review",
        )
        rows = {row["post_id"]: row for row in report["rows"]}

        self.assertEqual(rows[2]["review_action"], "rewrite_target_to_official_restore_dispatch")
        self.assertTrue(rows[2]["canonical_rewrite_dispatch_row"])
        self.assertTrue(rows[2]["enriched_restore_dispatch_row"])
        self.assertEqual(report["summary"]["enriched_restore_dispatch_rows"], 2)
        self.assertEqual(report["summary"]["canonical_rewrite_dispatch_rows"], 1)
        self.assertEqual(report["summary"]["hold_rows"], 1)
        dispatch_by_id = {row["post_id"]: row for row in dispatch["rows"]}
        self.assertEqual(sorted(dispatch_by_id), [1, 2])
        self.assertEqual(dispatch_by_id[2]["selected_title"], "화산귀환")
        self.assertEqual(
            dispatch_by_id[2]["selected_url"],
            "https://series.naver.com/novel/detail.series?productNo=4130558",
        )
        self.assertEqual(
            dispatch_by_id[2]["evidence_refs"][0],
            "https://series.naver.com/novel/detail.series?productNo=4130558",
        )
        self.assertFalse(dispatch_by_id[2]["runtime_replay_allowed"])

    def test_candidate_missing_plan_dispatches_back_to_candidate_set_lane(self):
        plan = self._contract_plan()
        plan["rows"][0]["contract_action"] = "official_support_missing_candidate_hold_contract_case"
        plan["rows"] = plan["rows"][:1]
        refs = self._reviewed_refs()
        refs["rows"] = refs["rows"][:1]

        report, dispatch = build_review(
            contract_plan=plan,
            reviewed_refs=refs,
            review_id="unit_candidate_review",
        )

        self.assertEqual(report["summary"]["source_official_missing_hold_rows"], 1)
        self.assertEqual(report["summary"]["enriched_restore_dispatch_rows"], 1)
        self.assertEqual(dispatch["rows"][0]["dispatch_lane"], "candidate_set_rebuild_review")
        self.assertEqual(dispatch["rows"][0]["selected_title"], "Expected Work")

    def test_missing_review_row_is_validation_issue(self):
        refs = self._reviewed_refs()
        refs["rows"] = refs["rows"][:1]

        report, dispatch = build_review(
            contract_plan=self._contract_plan(),
            reviewed_refs=refs,
            review_id="unit_review",
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["summary"]["validation_issue_count"], 2)
        self.assertEqual(dispatch["summary"]["enriched_restore_dispatch_rows"], 1)

    def test_dispatch_execution_contract_keeps_parallel_16_and_dashboard(self):
        _, dispatch = build_review(
            contract_plan=self._contract_plan(),
            reviewed_refs=self._reviewed_refs(),
            review_id="unit_review",
        )

        self.assertEqual(dispatch["execution_contract"]["requested_parallel"], 16)
        self.assertEqual(
            dispatch["execution_contract"]["dashboard_contract"]["dashboard_policy"],
            "WEB_DASHBOARD_REQUIRED_FOR_TEST_RUNS",
        )
        self.assertIn("--no-dashboard", dispatch["execution_contract"]["forbidden_flags"])


if __name__ == "__main__":
    unittest.main()
