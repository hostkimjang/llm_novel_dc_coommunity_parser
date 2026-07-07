from __future__ import annotations

from pathlib import Path
import unittest

from tools.build_remaining_native_evidence_contract_plan import (
    NO_PUBLISH,
    PUBLISH_RESTORE,
    build_plan,
)


class BuildRemainingNativeEvidenceContractPlanTest(unittest.TestCase):
    def test_direct_image_work_title_becomes_release_candidate(self) -> None:
        dispatch = {
            "dispatch_id": "remaining",
            "rows": [
                {
                    "post_id": 1,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "source_native_verdict": "image_required",
                    "actions": ["image_native_review_required"],
                }
            ],
        }
        result_rows = [
            {
                "post_id": 1,
                "analysis_result": {
                    "identity": {
                        "is_resolved_work_discussion": True,
                        "title_resolution_allowed": True,
                        "image_evidence_catalog": [
                            {
                                "explicit_work_title": "Image Work",
                                "explicit_author_name": "Author",
                                "title_role": "work_title",
                                "promotion_eligible": True,
                            }
                        ],
                    },
                    "analysis": {"detected_titles": []},
                },
            }
        ]

        plan = build_plan(
            residual_dispatch=dispatch,
            result_rows=result_rows,
            result_path=Path("result.json"),
            plan_id="unit",
        )

        self.assertEqual(plan["summary"]["contract_plan_rows"], 1)
        row = plan["rows"][0]
        self.assertEqual(row["contract_action"], PUBLISH_RESTORE)
        self.assertEqual(row["target_title"], "Image Work")
        self.assertEqual(row["promotion_decision"]["status"], "publish")
        self.assertFalse(row["runtime_replay_allowed"])

    def test_nonwork_without_image_becomes_no_publish_contract(self) -> None:
        dispatch = {
            "dispatch_id": "remaining",
            "rows": [
                {
                    "post_id": 2,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "source_native_verdict": "image_required",
                    "actions": ["native_web_review_required"],
                }
            ],
        }
        result_rows = [
            {
                "post_id": 2,
                "analysis_result": {
                    "identity": {
                        "is_relevant": False,
                        "is_resolved_work_discussion": False,
                        "title_resolution_allowed": False,
                        "discussion_type": "noise",
                    },
                    "analysis": {"detected_titles": []},
                },
            }
        ]

        plan = build_plan(
            residual_dispatch=dispatch,
            result_rows=result_rows,
            result_path=Path("result.json"),
            plan_id="unit",
        )

        self.assertEqual(plan["summary"]["no_publish_contract_rows"], 1)
        row = plan["rows"][0]
        self.assertEqual(row["contract_action"], NO_PUBLISH)
        self.assertEqual(row["promotion_decision"]["status"], "reject")
        self.assertFalse(row["release_candidate_not_approval"])

    def test_title_surface_specificity_keeps_row_on_hold(self) -> None:
        dispatch = {
            "dispatch_id": "remaining",
            "rows": [
                {
                    "post_id": 3,
                    "source_native_verdict": "generic_surface",
                    "actions": ["title_surface_specificity_review_required"],
                }
            ],
        }
        result_rows = [
            {
                "post_id": 3,
                "analysis_result": {
                    "identity": {
                        "is_resolved_work_discussion": True,
                        "title_resolution_allowed": True,
                        "novel_identity": {
                            "official_title": "Official Work",
                            "heretic_url": "https://novel.munpia.com/1",
                        },
                    },
                    "analysis": {
                        "detected_titles": [
                            {
                                "official_title": "Official Work",
                                "heretic_url": "https://novel.munpia.com/1",
                                "source_tier": "official_detail",
                                "reference_role": "primary",
                            }
                        ]
                    },
                },
            }
        ]

        plan = build_plan(
            residual_dispatch=dispatch,
            result_rows=result_rows,
            result_path=Path("result.json"),
            plan_id="unit",
        )

        self.assertEqual(plan["summary"]["contract_plan_rows"], 0)
        self.assertEqual(plan["summary"]["hold_rows"], 1)
        self.assertEqual(plan["review_rows"][0]["contract_disposition"], "hold_for_native_web_or_image_review")


if __name__ == "__main__":
    unittest.main()
