from __future__ import annotations

from pathlib import Path
import unittest

from tools.build_remaining_native_hold_contract_plan import (
    NATIVE_WEB_HOLD,
    apply_hold_contracts,
    build_plan,
)


class BuildRemainingNativeHoldContractPlanTest(unittest.TestCase):
    def test_builds_image_hold_contract_with_candidate_only_decision(self) -> None:
        dispatch = {
            "dispatch_id": "remaining4",
            "rows": [
                {
                    "post_id": 1,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "source_native_verdict": "image_or_context_required_for_safe_title",
                    "actions": ["image_native_review_required", "native_web_review_required"],
                }
            ],
        }
        result_rows = [
            {
                "post_id": 1,
                "analysis_result": {
                    "identity": {
                        "image_evidence_catalog": [
                            {
                                "explicit_work_title": "Image Candidate",
                                "title_role": "unknown",
                                "promotion_eligible": False,
                            }
                        ]
                    },
                    "analysis": {"detected_titles": []},
                },
            }
        ]

        plan = build_plan(
            dispatch=dispatch,
            result_rows=result_rows,
            plan_id="unit",
            result_path=Path("result.json"),
        )

        self.assertEqual(plan["summary"]["contract_plan_rows"], 1)
        row = plan["rows"][0]
        self.assertEqual(row["contract_action"], NATIVE_WEB_HOLD)
        self.assertEqual(row["current_projection_candidate_title"], "Image Candidate")
        self.assertEqual(row["promotion_decision"]["status"], "candidate_only")
        self.assertFalse(row["promotion_decision"]["publish_allowed"])

    def test_application_scrubs_public_identity_and_preserves_candidate(self) -> None:
        plan = {
            "plan_id": "unit",
            "rows": [
                {
                    "post_id": 2,
                    "contract_action": NATIVE_WEB_HOLD,
                    "contract_origin": "unit",
                    "current_projection_candidate_title": "Unsafe Public",
                    "current_projection_candidate_url": "https://example.test/work",
                    "promotion_decision": {
                        "status": "candidate_only",
                        "publish_allowed": False,
                        "candidate_preserved": True,
                        "reason_codes": ["scope_not_current_work"],
                    },
                    "scope_state": {"scope_kind": "unknown", "confidence": "medium"},
                    "rationale_ko": "hold",
                }
            ],
        }
        projection_rows = [
            {
                "post_id": 2,
                "actual_title": "Unsafe Public",
                "actual_url": "https://example.test/work",
                "analysis_result": {
                    "identity": {
                        "novel_identity": {
                            "official_title": "Unsafe Public",
                            "heretic_url": "https://example.test/work",
                            "confidence": "High",
                        },
                        "heretic_url": "https://example.test/work",
                        "official_url": "https://example.test/work",
                        "resolved_url": "https://example.test/work",
                        "title_resolution_allowed": True,
                        "safe_resolved": True,
                    }
                },
            }
        ]

        updated, application = apply_hold_contracts(
            projection_rows=projection_rows,
            plan=plan,
            projection_id="unit_application",
        )

        identity = updated[0]["analysis_result"]["identity"]
        self.assertIsNone(updated[0]["actual_title"])
        self.assertIsNone(updated[0]["actual_url"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertIsNone(identity["novel_identity"]["heretic_url"])
        self.assertIsNone(identity["heretic_url"])
        self.assertIsNone(identity["official_url"])
        self.assertIsNone(identity["resolved_url"])
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertEqual(identity["candidate_ledger"]["status"], "candidate_only")
        self.assertEqual(identity["blocked_official_title"], "Unsafe Public")
        self.assertIn("serialized_public_identity_scrubbed", identity["promotion_decision"]["reason_codes"])
        self.assertEqual(application["summary"]["applied_scrubbed_public_identity_rows"], 1)


if __name__ == "__main__":
    unittest.main()
