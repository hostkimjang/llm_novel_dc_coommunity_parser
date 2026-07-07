import unittest

from tools.apply_source_native_hold_projection_contract import apply_contract


class ApplySourceNativeHoldProjectionContractTest(unittest.TestCase):
    def test_applies_source_native_hold_to_unsafe_promotion(self):
        projection = [
            {
                "post_id": 1,
                "title": "베지테리언 아이디어",
                "content": ["정육점 사장이 됐다 같은 소설 아이디어"],
                "comments": [],
                "analysis_result": {
                    "identity": {
                        "candidate_ledger_status": "safe_resolved",
                        "title_resolution_allowed": True,
                        "title_resolution_state": "resolved",
                        "work_resolution": "resolved",
                        "is_resolved_work_discussion": True,
                        "novel_identity": {
                            "official_title": "사이버펑크 베지테리언 매드니스",
                            "heretic_url": "https://novelpia.com/novel/31737",
                            "confidence": "High",
                        },
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
                    "selected_option_id": "HOLD",
                    "selected_title": None,
                    "source_native_verdict": "generic_idea_prompt_not_candidate_work_discussion",
                    "evidence_grade": "Strong",
                    "actions": ["repair_unsafe_promotion", "intent_guard_review"],
                }
            ]
        }

        result_rows, application = apply_contract(projection, verdicts, application_id="unit")

        identity = result_rows[0]["analysis_result"]["identity"]
        self.assertEqual(application["gate"], "REVIEW-LOCKED")
        self.assertFalse(application["full_scan_approval"])
        self.assertEqual(application["summary"]["applied_hold_rows"], 1)
        self.assertEqual(application["rows"][0]["outcome"], "applied_source_native_hold")
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(identity["blocked_official_title"], "사이버펑크 베지테리언 매드니스")
        self.assertEqual(
            identity["publish_contract_trace"]["pre_gate_candidate"]["official_title"],
            "사이버펑크 베지테리언 매드니스",
        )
        self.assertFalse(identity["publish_contract_trace"]["gate_decision"]["publish_allowed"])
        self.assertEqual(identity["publish_contract_trace"]["gate_decision"], identity["promotion_decision"])

    def test_ignores_publish_repair_rows(self):
        projection = [
            {
                "post_id": 2,
                "analysis_result": {
                    "identity": {
                        "candidate_ledger_status": "promotion_blocked",
                        "title_resolution_allowed": False,
                        "novel_identity": None,
                    }
                },
            }
        ]
        verdicts = {
            "rows": [
                {
                    "post_id": 2,
                    "review_label": "REPROCESS",
                    "selected_option_id": "C1",
                    "selected_title": "전지적 1인칭 시점",
                    "source_native_verdict": "direct_abbreviation_supports_safe_title_lost_to_null",
                    "evidence_grade": "Strong",
                    "actions": [
                        "repair_safe_loss_restore_supported_title",
                        "shared_promotion_gate_wiring_required",
                    ],
                }
            ]
        }

        result_rows, application = apply_contract(projection, verdicts, application_id="unit")

        identity = result_rows[0]["analysis_result"]["identity"]
        self.assertEqual(application["summary"]["eligible_unsafe_promotion_rows"], 0)
        self.assertEqual(application["summary"]["applied_hold_rows"], 0)
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")


if __name__ == "__main__":
    unittest.main()
