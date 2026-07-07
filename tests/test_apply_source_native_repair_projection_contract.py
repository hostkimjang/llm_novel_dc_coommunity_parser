import unittest

from tools.apply_source_native_repair_projection_contract import apply_contract


class ApplySourceNativeRepairProjectionContractTest(unittest.TestCase):
    def test_applies_source_native_selected_title_through_shared_seed(self):
        projection = [
            {
                "post_id": 1,
                "title": "마줍 얘기",
                "content": ["마줍에 나오는 투명 우주 흡혈귀 얘기"],
                "comments": ["작품 설정 얘기"],
                "analysis_result": {
                    "identity": {
                        "candidate_ledger_status": "promotion_blocked",
                        "title_resolution_allowed": False,
                        "title_resolution_state": "unresolved_matchable",
                        "work_resolution": "unresolved",
                        "novel_identity": None,
                        "candidate_ledger": {},
                    }
                },
            }
        ]
        verdicts = {
            "rows": [
                {
                    "post_id": 1,
                    "review_label": "REPROCESS",
                    "selected_title": "마도서를 줍다 마법사가 되다",
                    "selected_url": "https://novelpia.com/novel/414963",
                    "source_native_verdict": "supported_safe_title_lost_to_null",
                    "evidence_grade": "Strong",
                    "action": [
                        "repair_safe_loss_restore_supported_title",
                        "shared_promotion_gate_wiring_required",
                    ],
                    "rationale_ko": "본문이 후보 작품 약칭과 설정 대상을 직접 연결한다.",
                }
            ]
        }

        result_rows, application = apply_contract(projection, verdicts, application_id="unit")

        identity = result_rows[0]["analysis_result"]["identity"]
        self.assertEqual(application["gate"], "REVIEW-LOCKED")
        self.assertFalse(application["full_scan_approval"])
        self.assertEqual(application["summary"]["applied_publish_rows"], 1)
        self.assertEqual(application["rows"][0]["outcome"], "applied_shared_gate_publish")
        self.assertEqual(identity["candidate_ledger_status"], "safe_resolved")
        self.assertTrue(identity["title_resolution_allowed"])
        self.assertEqual(identity["novel_identity"]["official_title"], "마도서를 줍다 마법사가 되다")
        self.assertIn(
            "projection_followup_shared_gate_seed_applied",
            identity["promotion_decision"]["reason_codes"],
        )
        self.assertEqual(identity["publish_contract_trace"]["gate_decision"], identity["promotion_decision"])

    def test_missing_official_url_stays_unpublished(self):
        projection = [
            {
                "post_id": 2,
                "title": "화산파 얘기",
                "content": ["화귀 댓글"],
                "comments": [],
                "analysis_result": {
                    "identity": {
                        "candidate_ledger_status": "promotion_blocked",
                        "title_resolution_allowed": False,
                        "novel_identity": None,
                        "candidate_ledger": {},
                    }
                },
            }
        ]
        verdicts = {
            "rows": [
                {
                    "post_id": 2,
                    "review_label": "REPROCESS",
                    "selected_title": "화산파(화산귀환)",
                    "selected_url": None,
                    "source_native_verdict": "supported_safe_title_lost_to_null",
                    "evidence_grade": "Strong",
                    "action": [
                        "repair_safe_loss_restore_supported_title",
                        "shared_promotion_gate_wiring_required",
                    ],
                }
            ]
        }

        result_rows, application = apply_contract(projection, verdicts, application_id="unit")

        identity = result_rows[0]["analysis_result"]["identity"]
        self.assertEqual(application["summary"]["applied_publish_rows"], 0)
        self.assertEqual(application["rows"][0]["outcome"], "skipped_missing_official_detail_url")
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertFalse(identity["title_resolution_allowed"])


if __name__ == "__main__":
    unittest.main()
