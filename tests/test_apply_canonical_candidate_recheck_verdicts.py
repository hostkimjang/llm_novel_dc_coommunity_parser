import unittest
from pathlib import Path

from tools.apply_canonical_candidate_recheck_verdicts import (
    build_application_summary,
    build_verdict_template,
)


def _batch_row() -> dict:
    return {
        "post_id": 11660271,
        "review_lane": "B1_different_candidate_alignment_review",
        "expected_or_source_native_title": "월야의 여인들",
        "current_projection_candidate_title": "경멸하는 여자를 굴복시키는 법",
        "current_projection_candidate_url": "https://novelpia.com/novel/121059",
        "candidate_support_state": "official_url_candidate_support",
        "search_gate": "SEARCH_RECOVERED_CONDITIONAL",
        "primary_repair_lane": "scope_or_nonwork_monotonicity_repair",
        "allowed_verdicts": [
            "EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED",
            "CURRENT_PROJECTION_CANDIDATE_CONFIRMED",
            "RELATED_CANONICAL_VARIANT_CONFIRMED",
            "WRONG_OR_UNRELATED_CANDIDATE",
            "INSUFFICIENT_EVIDENCE_HOLD",
        ],
        "after_verdict_contract": {
            "EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED": {
                "next_state": "candidate_scrub_or_expected_title_restore_contract_required",
                "runtime_release": "blocked_until_contract_tests_pass",
            },
            "CURRENT_PROJECTION_CANDIDATE_CONFIRMED": {
                "next_state": "source_native_expectation_update_or_blind_acceptance_required",
                "runtime_release": "blocked_until_expected_contract_updated",
            },
            "RELATED_CANONICAL_VARIANT_CONFIRMED": {
                "next_state": "canonical_variant_policy_contract_required",
                "runtime_release": "blocked_until_variant_policy_tests_pass",
            },
            "WRONG_OR_UNRELATED_CANDIDATE": {
                "next_state": "current_projection_candidate_scrub_required",
                "runtime_release": "blocked_until_candidate_scrub_tests_pass",
            },
            "INSUFFICIENT_EVIDENCE_HOLD": {
                "next_state": "hard_hold_or_native_web_review_required",
                "runtime_release": "blocked_until_stronger_evidence",
            },
            "current_runtime_release_gate": "BLOCKED_UNTIL_CANONICAL_CANDIDATE_RECHECK",
            "runtime_replay_allowed_before_verdict": False,
        },
    }


class ApplyCanonicalCandidateRecheckVerdictsTest(unittest.TestCase):
    def test_expected_source_native_verdict_maps_to_contract_block(self):
        batch = {"rows": [_batch_row()]}
        verdicts = {
            "rows": [
                {
                    "post_id": 11660271,
                    "canonical_verdict": "EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED",
                    "evidence_grade": "Strong",
                    "rationale_ko": "원문과 source-native 근거는 expected title을 지지한다.",
                    "evidence_refs": ["unit://source"],
                }
            ]
        }

        summary = build_application_summary(
            batch=batch,
            batch_path=Path("batch.json"),
            verdicts=verdicts,
            verdict_path=Path("verdicts.json"),
            generated_at="2026-07-07T00:00:00",
        )

        self.assertEqual(summary["gate"], "REVIEW-LOCKED")
        self.assertEqual(summary["summary"]["accepted_verdict_rows"], 1)
        self.assertEqual(summary["summary"]["runtime_replay_allowed_rows"], 0)
        self.assertFalse(summary["full_scan_approval"])
        row = summary["rows"][0]
        self.assertEqual(row["canonical_title"], "월야의 여인들")
        self.assertEqual(
            row["post_verdict_next_state"],
            "candidate_scrub_or_expected_title_restore_contract_required",
        )
        self.assertEqual(row["runtime_release_condition"], "blocked_until_contract_tests_pass")
        self.assertFalse(row["runtime_replay_allowed_after_verdict"])

    def test_invalid_verdict_keeps_no_go(self):
        batch = {"rows": [_batch_row()]}
        verdicts = {
            "rows": [
                {
                    "post_id": 11660271,
                    "canonical_verdict": "UNLISTED_VERDICT",
                    "evidence_grade": "Strong",
                    "rationale_ko": "허용되지 않은 verdict다.",
                    "evidence_refs": ["unit://source"],
                }
            ]
        }

        summary = build_application_summary(
            batch=batch,
            batch_path=Path("batch.json"),
            verdicts=verdicts,
            generated_at="2026-07-07T00:00:00",
        )

        self.assertEqual(summary["gate"], "NO-GO")
        self.assertEqual(summary["summary"]["validation_issue_count"], 1)
        self.assertEqual(
            summary["validation_issues"][0]["issues"],
            ["canonical_verdict_not_allowed_for_batch_row"],
        )

    def test_related_variant_requires_canonical_title(self):
        batch = {"rows": [_batch_row()]}
        verdicts = {
            "rows": [
                {
                    "post_id": 11660271,
                    "canonical_verdict": "RELATED_CANONICAL_VARIANT_CONFIRMED",
                    "evidence_grade": "Medium",
                    "rationale_ko": "variant 관계라고 주장하지만 canonical title이 빠졌다.",
                    "evidence_refs": ["unit://source"],
                }
            ]
        }

        summary = build_application_summary(
            batch=batch,
            batch_path=Path("batch.json"),
            verdicts=verdicts,
            generated_at="2026-07-07T00:00:00",
        )

        self.assertEqual(summary["gate"], "NO-GO")
        self.assertIn(
            "missing_canonical_title_for_related_variant",
            summary["validation_issues"][0]["issues"],
        )

    def test_empty_verdicts_report_unreviewed_and_template(self):
        batch = {"rows": [_batch_row()]}

        summary = build_application_summary(
            batch=batch,
            batch_path=Path("batch.json"),
            verdicts=None,
            generated_at="2026-07-07T00:00:00",
        )
        template = build_verdict_template(
            batch=batch,
            batch_path=Path("batch.json"),
            review_id="unit_template",
            scope="unit template",
            generated_at="2026-07-07T00:00:00",
        )

        self.assertEqual(summary["gate"], "REVIEW-LOCKED")
        self.assertEqual(summary["summary"]["verdict_rows"], 0)
        self.assertEqual(summary["summary"]["unreviewed_batch_rows"], 1)
        self.assertEqual(summary["unreviewed_post_ids"], [11660271])
        self.assertEqual(template["summary"]["template_rows"], 1)
        self.assertEqual(template["rows"][0]["canonical_verdict"], "")
        self.assertIn("EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED", template["rows"][0]["allowed_verdicts"])


if __name__ == "__main__":
    unittest.main()
