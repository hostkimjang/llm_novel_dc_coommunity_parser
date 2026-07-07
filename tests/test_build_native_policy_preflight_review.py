import unittest

from tools.build_native_policy_preflight_review import build_review


class BuildNativePolicyPreflightReviewTest(unittest.TestCase):
    def _contract_queue(self):
        return {
            "queue_id": "unit_contract_queue",
            "rows": [
                {
                    "post_id": 1,
                    "dispatch_lane": "native_web_image_evidence_review",
                    "batch_lanes": ["native_web_image_evidence_review", "shared_gate_restore_contract_review"],
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "REPROCESS",
                    "target_title": "귤부인 대롱대롱",
                    "evidence_grade": "Medium",
                    "source_native_verdict": "direct_title_surface_and_scene_reaction_support_safe_title",
                    "actions": [
                        "repair_safe_loss_restore_supported_title",
                        "shared_promotion_gate_wiring_required",
                        "native_web_review_required",
                    ],
                    "rationale_ko": "원문 제목이 귤부인 대롱대롱을 직접 말한다.",
                    "evidence_refs": ["docs/devs/source.json#post_id=1"],
                },
                {
                    "post_id": 2,
                    "dispatch_lane": "no_publish_guard_review",
                    "batch_lanes": ["no_publish_guard_review", "shared_gate_restore_contract_review"],
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "REPROCESS",
                    "target_title": "니들 생각 다 들린다",
                    "evidence_grade": "Strong",
                    "source_native_verdict": "work_specific_emoticon_purchase_supports_safe_title",
                    "actions": [
                        "repair_safe_loss_restore_supported_title",
                        "shared_promotion_gate_wiring_required",
                        "merchandise_or_emoticon_work_context_guard",
                    ],
                    "rationale_ko": "원문과 OCR이 작품별 이모티콘 구매 맥락을 직접 지지한다.",
                    "evidence_refs": ["docs/devs/source.json#post_id=2"],
                },
                {
                    "post_id": 3,
                    "dispatch_lane": "candidate_set_rebuild_review",
                    "batch_lanes": ["candidate_set_rebuild_review", "native_web_image_evidence_review"],
                    "target_title": "Other",
                },
            ],
        }

    def _reviewed_refs(self):
        return {
            "review_id": "unit_native_review",
            "rows": [
                {
                    "post_id": 1,
                    "native_policy_state": "native_web_exact_title_not_found_context_only",
                    "official_title": "친아들이 내게 집착한다",
                    "official_url": "https://novelpia.com/novel/197558",
                    "accepted_by_native_policy_contract": False,
                    "review_action": "native_web_context_only_hold",
                    "source_urls": ["https://novelpia.com/novel/197558"],
                    "source_evidence_ko": "노벨피아 공식 상세는 #귤부인 태그를 보이지만 target title과 일치하지 않는다.",
                    "hold_reason_ko": "exact official title이 없어 publish하지 않는다.",
                },
                {
                    "post_id": 2,
                    "native_policy_state": "official_detail_and_store_context_confirmed",
                    "official_title": "니들 생각 다 들린다",
                    "official_url": "https://novelpia.com/novel/384318",
                    "store_url": "https://novelpia.com/openstore_v2_detail/1696",
                    "store_context_confirmed": True,
                    "accepted_by_native_policy_contract": True,
                    "source_urls": [
                        "https://novelpia.com/novel/384318",
                        "https://novelpia.com/openstore_v2_detail/1696",
                    ],
                    "source_evidence_ko": "공식 작품 상세와 노벨티콘 스토어가 같은 작품명을 지지한다.",
                },
            ],
        }

    def test_only_confirmed_official_detail_and_store_context_dispatches(self):
        report, dispatch = build_review(
            contract_queue=self._contract_queue(),
            reviewed_refs=self._reviewed_refs(),
            review_id="unit_native_review",
        )

        self.assertEqual(report["gate"], "REVIEW-LOCKED")
        self.assertEqual(report["summary"]["source_preflight_rows"], 2)
        self.assertEqual(report["summary"]["restore_dispatch_rows"], 1)
        self.assertEqual(report["summary"]["hold_rows"], 1)
        rows = {row["post_id"]: row for row in report["rows"]}
        self.assertEqual(rows[1]["review_action"], "native_web_context_only_hold")
        self.assertFalse(rows[1]["restore_dispatch_row"])
        self.assertEqual(rows[2]["review_action"], "native_policy_restore_dispatch")
        self.assertTrue(rows[2]["restore_dispatch_row"])

        self.assertEqual(len(dispatch["rows"]), 1)
        self.assertEqual(dispatch["rows"][0]["post_id"], 2)
        self.assertEqual(dispatch["rows"][0]["dispatch_lane"], "shared_gate_restore_contract_review")
        self.assertEqual(dispatch["rows"][0]["selected_title"], "니들 생각 다 들린다")
        self.assertEqual(dispatch["rows"][0]["selected_url"], "https://novelpia.com/novel/384318")
        self.assertIn("work_specific_store_context_confirmed", dispatch["rows"][0]["actions"])
        self.assertFalse(dispatch["rows"][0]["runtime_replay_allowed"])

    def test_store_context_is_required_for_merchandise_guard(self):
        refs = self._reviewed_refs()
        refs["rows"][1]["store_context_confirmed"] = False

        report, dispatch = build_review(
            contract_queue=self._contract_queue(),
            reviewed_refs=refs,
            review_id="unit_native_review",
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["summary"]["validation_issue_count"], 1)
        self.assertEqual(report["validation_issues"][0]["issues"], ["native_policy_dispatch_contract_not_satisfied"])
        self.assertEqual(dispatch["summary"]["restore_dispatch_rows"], 0)

    def test_dispatch_execution_contract_keeps_parallel_16_and_dashboard(self):
        _, dispatch = build_review(
            contract_queue=self._contract_queue(),
            reviewed_refs=self._reviewed_refs(),
            review_id="unit_native_review",
        )

        self.assertEqual(dispatch["execution_contract"]["requested_parallel"], 16)
        self.assertEqual(dispatch["execution_contract"]["expected_effective_parallel"], 1)
        self.assertIn("--no-dashboard", dispatch["execution_contract"]["forbidden_flags"])
        self.assertEqual(
            dispatch["execution_contract"]["dashboard_contract"]["dashboard_policy"],
            "WEB_DASHBOARD_REQUIRED_FOR_TEST_RUNS",
        )

    def test_auxiliary_native_web_batch_lane_does_not_enter_preflight_review(self):
        report, dispatch = build_review(
            contract_queue=self._contract_queue(),
            reviewed_refs=self._reviewed_refs(),
            review_id="unit_native_review",
        )

        self.assertEqual(report["summary"]["source_preflight_rows"], 2)
        self.assertNotIn(3, {row["post_id"] for row in report["rows"]})
        self.assertNotIn(3, {row["post_id"] for row in dispatch["rows"]})


if __name__ == "__main__":
    unittest.main()
