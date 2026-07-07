from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.audit_post_verdict_promotion_gate_release_contract import build_audit, write_markdown


def _plan_row(post_id, action, target="Expected", candidate="Wrong"):
    return {
        "post_id": post_id,
        "contract_batch_lane": "lane",
        "contract_action": action,
        "target_title": target,
        "target_url": None,
        "current_projection_candidate_title": candidate,
        "current_projection_candidate_url": None,
    }


def _projection(post_id, title=None, status="promotion_blocked", publish=False):
    return {
        "post_id": post_id,
        "analysis_result": {
            "identity": {
                "novel_identity": {"official_title": title, "heretic_url": None},
                "candidate_ledger_status": status,
                "publish_allowed": publish,
            }
        },
    }


class AuditPostVerdictPromotionGateReleaseContractTest(unittest.TestCase):
    def test_restore_plan_stays_pending_when_projection_is_not_restored(self):
        audit = build_audit(
            contract_plan={
                "plan_id": "unit",
                "gate": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [_plan_row(1, "expected_title_restore_contract_case")],
            },
            projection_rows=[_projection(1)],
            audit_id="unit",
        )

        self.assertEqual(audit["gate"], "REVIEW-LOCKED")
        self.assertEqual(audit["summary"]["pending_contract_rows"], 1)
        self.assertEqual(audit["summary"]["release_candidate_after_contract_rows"], 0)
        self.assertEqual(audit["summary"]["runtime_replay_allowed_rows"], 0)
        self.assertEqual(audit["rows"][0]["release_gate_state"], "expected_restore_contract_pending_projection_not_restored")

    def test_restore_plan_candidate_leak_is_violation(self):
        audit = build_audit(
            contract_plan={
                "plan_id": "unit",
                "gate": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [_plan_row(1, "expected_title_restore_contract_case")],
            },
            projection_rows=[_projection(1, title="Wrong", status="safe_resolved", publish=True)],
            audit_id="unit",
        )

        self.assertEqual(audit["gate"], "NO-GO")
        self.assertEqual(audit["rows"][0]["violation_code"], "current_candidate_leaked_after_expected_restore_plan")

    def test_restore_plan_target_publish_is_release_candidate_not_runtime_replay(self):
        audit = build_audit(
            contract_plan={
                "plan_id": "unit",
                "gate": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [_plan_row(1, "expected_title_restore_contract_case")],
            },
            projection_rows=[_projection(1, title="Expected", status="safe_resolved", publish=True)],
            audit_id="unit",
        )

        self.assertEqual(audit["gate"], "REVIEW-LOCKED")
        self.assertEqual(audit["summary"]["release_candidate_after_contract_rows"], 1)
        self.assertEqual(audit["summary"]["runtime_replay_allowed_rows"], 0)
        self.assertEqual(audit["rows"][0]["release_gate_state"], "expected_restore_contract_satisfied_release_candidate")

    def test_restore_plan_same_candidate_title_as_target_is_not_leak(self):
        audit = build_audit(
            contract_plan={
                "plan_id": "unit",
                "gate": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [
                    _plan_row(
                        1,
                        "expected_title_restore_contract_case",
                        target="Same Work",
                        candidate="Same Work",
                    )
                ],
            },
            projection_rows=[_projection(1, title="Same Work", status="safe_resolved", publish=True)],
            audit_id="unit",
        )

        self.assertEqual(audit["gate"], "REVIEW-LOCKED")
        self.assertEqual(audit["summary"]["violation_row_count"], 0)
        self.assertEqual(audit["summary"]["release_candidate_after_contract_rows"], 1)
        self.assertEqual(audit["rows"][0]["release_gate_state"], "expected_restore_contract_satisfied_release_candidate")
        self.assertTrue(audit["rows"][0]["publish_allowed"])

    def test_runtime_mismatch_plan_requires_no_public_identity(self):
        audit = build_audit(
            contract_plan={
                "plan_id": "unit",
                "gate": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [_plan_row(1, "restore_target_runtime_mismatch_review_required")],
            },
            projection_rows=[_projection(1, title="Unexpected Public", status="safe_resolved", publish=True)],
            audit_id="unit",
        )

        self.assertEqual(audit["gate"], "NO-GO")
        self.assertEqual(audit["summary"]["violation_row_count"], 1)
        self.assertEqual(audit["rows"][0]["release_gate_state"], "restore_target_mismatch_public_identity_violation")
        self.assertEqual(
            audit["rows"][0]["violation_code"],
            "mismatch_review_published_before_source_native_verdict",
        )

    def test_runtime_mismatch_plan_preserves_no_release_when_blocked(self):
        audit = build_audit(
            contract_plan={
                "plan_id": "unit",
                "gate": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [_plan_row(1, "restore_target_runtime_mismatch_review_required")],
            },
            projection_rows=[_projection(1)],
            audit_id="unit",
        )

        self.assertEqual(audit["gate"], "REVIEW-LOCKED")
        self.assertEqual(audit["summary"]["satisfied_no_release_rows"], 1)
        self.assertEqual(audit["rows"][0]["release_gate_state"], "restore_target_mismatch_preserved_no_release")

    def test_official_support_missing_hold_preserves_no_release_when_blocked(self):
        audit = build_audit(
            contract_plan={
                "plan_id": "unit",
                "gate": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [_plan_row(1, "official_support_missing_restore_hold_contract_case")],
            },
            projection_rows=[_projection(1)],
            audit_id="unit",
        )

        self.assertEqual(audit["gate"], "REVIEW-LOCKED")
        self.assertEqual(audit["summary"]["satisfied_no_release_rows"], 1)
        self.assertEqual(audit["summary"]["release_candidate_after_contract_rows"], 0)
        self.assertEqual(
            audit["rows"][0]["release_gate_state"],
            "official_support_missing_restore_hold_preserved_no_release",
        )

    def test_official_support_missing_hold_blocks_public_identity(self):
        audit = build_audit(
            contract_plan={
                "plan_id": "unit",
                "gate": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [_plan_row(1, "official_support_missing_restore_hold_contract_case")],
            },
            projection_rows=[_projection(1, title="Expected", status="safe_resolved", publish=True)],
            audit_id="unit",
        )

        self.assertEqual(audit["gate"], "NO-GO")
        self.assertEqual(
            audit["rows"][0]["violation_code"],
            "official_support_missing_hold_published_before_official_detail_url",
        )

    def test_markdown_gate_interpretation_uses_summary_counts(self):
        audit = build_audit(
            contract_plan={
                "plan_id": "unit",
                "gate": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [_plan_row(1, "expected_title_restore_contract_case")],
            },
            projection_rows=[_projection(1, title="Expected", status="safe_resolved", publish=True)],
            audit_id="unit",
        )

        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "audit.md"
            write_markdown(output_path, audit)
            markdown = output_path.read_text(encoding="utf-8")

        self.assertIn("pending contract는 `0`건", markdown)
        self.assertIn("release candidate는 `1`건", markdown)
        self.assertNotIn("release candidate는 `0`건", markdown)

    def test_scrub_plan_no_public_identity_is_satisfied_no_release(self):
        audit = build_audit(
            contract_plan={
                "plan_id": "unit",
                "gate": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [_plan_row(1, "candidate_scrub_no_publish_contract_case")],
            },
            projection_rows=[_projection(1)],
            audit_id="unit",
        )

        self.assertEqual(audit["summary"]["satisfied_no_release_rows"], 1)
        self.assertEqual(audit["rows"][0]["release_gate_state"], "scrub_contract_satisfied_no_release")

    def test_variant_hold_blocks_public_identity(self):
        audit = build_audit(
            contract_plan={
                "plan_id": "unit",
                "gate": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [_plan_row(2, "canonical_variant_policy_hold_contract_case")],
            },
            projection_rows=[_projection(2, title="Expected", status="safe_resolved", publish=True)],
            audit_id="unit",
        )

        self.assertEqual(audit["gate"], "NO-GO")
        self.assertEqual(audit["rows"][0]["violation_code"], "variant_published_before_policy_contract")

    def test_stronger_evidence_hold_preserves_no_release(self):
        audit = build_audit(
            contract_plan={
                "plan_id": "unit",
                "gate": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [_plan_row(3, "stronger_evidence_hard_hold_contract_case")],
            },
            projection_rows=[_projection(3)],
            audit_id="unit",
        )

        self.assertEqual(audit["summary"]["satisfied_no_release_rows"], 1)
        self.assertEqual(audit["rows"][0]["release_gate_state"], "stronger_evidence_hold_preserved_no_release")

    def test_expected_audit_update_release_candidate_when_actual_title_published(self):
        audit = build_audit(
            contract_plan={
                "plan_id": "unit",
                "gate": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [
                    {
                        "post_id": 4,
                        "contract_action": "expected_audit_update_exclusion_contract_case",
                        "target_title": "Actual Work",
                        "expected_title": "Actual Work 질문 표면",
                    }
                ],
            },
            projection_rows=[_projection(4, title="Actual Work", status="safe_resolved", publish=True)],
            audit_id="unit",
        )

        self.assertEqual(audit["summary"]["release_candidate_after_contract_rows"], 1)
        self.assertEqual(
            audit["rows"][0]["release_gate_state"],
            "expected_audit_update_contract_satisfied_release_candidate",
        )

    def test_expected_audit_update_old_expected_leak_is_violation(self):
        audit = build_audit(
            contract_plan={
                "plan_id": "unit",
                "gate": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [
                    {
                        "post_id": 5,
                        "contract_action": "expected_audit_update_exclusion_contract_case",
                        "target_title": "Actual Work",
                        "expected_title": "Actual Work 질문 표면",
                    }
                ],
            },
            projection_rows=[_projection(5, title="Actual Work 질문 표면", status="safe_resolved", publish=True)],
            audit_id="unit",
        )

        self.assertEqual(audit["gate"], "NO-GO")
        self.assertEqual(
            audit["rows"][0]["violation_code"],
            "old_expected_title_leaked_after_expected_audit_update_plan",
        )

    def test_native_web_hold_preserves_no_release(self):
        audit = build_audit(
            contract_plan={
                "plan_id": "unit",
                "gate": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [_plan_row(6, "native_web_disambiguation_hold_contract_case")],
            },
            projection_rows=[_projection(6)],
            audit_id="unit",
        )

        self.assertEqual(audit["summary"]["satisfied_no_release_rows"], 1)
        self.assertEqual(
            audit["rows"][0]["release_gate_state"],
            "native_web_disambiguation_hold_preserved_no_release",
        )

    def test_non_webnovel_ebook_policy_hold_preserves_no_release(self):
        audit = build_audit(
            contract_plan={
                "plan_id": "unit",
                "gate": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [_plan_row(7, "non_webnovel_ebook_policy_hold_contract_case")],
            },
            projection_rows=[_projection(7)],
            audit_id="unit",
        )

        self.assertEqual(audit["gate"], "REVIEW-LOCKED")
        self.assertEqual(audit["summary"]["satisfied_no_release_rows"], 1)
        self.assertEqual(
            audit["rows"][0]["release_gate_state"],
            "non_webnovel_ebook_policy_hold_preserved_no_release",
        )

    def test_non_webnovel_ebook_policy_hold_flags_public_identity(self):
        audit = build_audit(
            contract_plan={
                "plan_id": "unit",
                "gate": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [_plan_row(7, "non_webnovel_ebook_policy_hold_contract_case")],
            },
            projection_rows=[_projection(7, title="인간실격", status="safe_resolved", publish=True)],
            audit_id="unit",
        )

        self.assertEqual(audit["gate"], "NO-GO")
        self.assertEqual(
            audit["rows"][0]["violation_code"],
            "non_webnovel_ebook_policy_published_before_policy_contract",
        )

    def test_canonical_cleanup_contaminated_actual_leak_is_violation(self):
        audit = build_audit(
            contract_plan={
                "plan_id": "unit",
                "gate": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [
                    {
                        "post_id": 7,
                        "contract_action": "canonical_cleanup_or_url_correction_contract_case",
                        "target_title": "Clean Canonical",
                        "actual_title": "Contaminated Candidate",
                    }
                ],
            },
            projection_rows=[_projection(7, title="Contaminated Candidate", status="safe_resolved", publish=True)],
            audit_id="unit",
        )

        self.assertEqual(audit["gate"], "NO-GO")
        self.assertEqual(
            audit["rows"][0]["violation_code"],
            "contaminated_candidate_leaked_before_canonical_cleanup",
        )

    def test_canonical_cleanup_target_publish_is_release_candidate(self):
        audit = build_audit(
            contract_plan={
                "plan_id": "unit",
                "gate": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [
                    {
                        "post_id": 8,
                        "contract_action": "canonical_cleanup_or_url_correction_contract_case",
                        "target_title": "Clean Canonical",
                        "actual_title": "Contaminated Candidate",
                    }
                ],
            },
            projection_rows=[_projection(8, title="Clean Canonical", status="safe_resolved", publish=True)],
            audit_id="unit",
        )

        self.assertEqual(audit["summary"]["release_candidate_after_contract_rows"], 1)
        self.assertEqual(
            audit["rows"][0]["release_gate_state"],
            "canonical_cleanup_contract_satisfied_release_candidate",
        )

    def test_candidate_set_restore_target_publish_is_release_candidate(self):
        audit = build_audit(
            contract_plan={
                "plan_id": "unit",
                "gate": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [_plan_row(9, "candidate_set_expected_restore_contract_case")],
            },
            projection_rows=[_projection(9, title="Expected", status="safe_resolved", publish=True)],
            audit_id="unit",
        )

        self.assertEqual(audit["gate"], "REVIEW-LOCKED")
        self.assertEqual(audit["summary"]["release_candidate_after_contract_rows"], 1)
        self.assertEqual(
            audit["rows"][0]["release_gate_state"],
            "candidate_set_expected_restore_contract_satisfied_release_candidate",
        )

    def test_candidate_set_rebuild_hold_blocks_public_identity(self):
        audit = build_audit(
            contract_plan={
                "plan_id": "unit",
                "gate": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [_plan_row(10, "candidate_set_rebuild_required_before_publish")],
            },
            projection_rows=[_projection(10, title="Wrong", status="safe_resolved", publish=True)],
            audit_id="unit",
        )

        self.assertEqual(audit["gate"], "NO-GO")
        self.assertEqual(
            audit["rows"][0]["violation_code"],
            "candidate_set_rebuild_published_before_candidate_rebuild",
        )

    def test_candidate_set_rebuild_hold_preserves_no_release_when_blocked(self):
        audit = build_audit(
            contract_plan={
                "plan_id": "unit",
                "gate": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [_plan_row(11, "candidate_set_rebuild_required_before_publish")],
            },
            projection_rows=[_projection(11)],
            audit_id="unit",
        )

        self.assertEqual(audit["summary"]["satisfied_no_release_rows"], 1)
        self.assertEqual(audit["rows"][0]["release_gate_state"], "candidate_set_rebuild_preserved_no_release")

    def test_no_publish_intent_guard_blocks_public_identity(self):
        audit = build_audit(
            contract_plan={
                "plan_id": "unit",
                "gate": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [_plan_row(12, "no_publish_intent_guard_contract_case")],
            },
            projection_rows=[_projection(12, title="Same Surface Webnovel", status="safe_resolved", publish=True)],
            audit_id="unit",
        )

        self.assertEqual(audit["gate"], "NO-GO")
        self.assertEqual(
            audit["rows"][0]["violation_code"],
            "intent_guard_published_before_no_publish_contract",
        )

    def test_no_publish_intent_guard_preserves_no_release_when_blocked(self):
        audit = build_audit(
            contract_plan={
                "plan_id": "unit",
                "gate": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [_plan_row(13, "no_publish_intent_guard_contract_case")],
            },
            projection_rows=[_projection(13)],
            audit_id="unit",
        )

        self.assertEqual(audit["summary"]["satisfied_no_release_rows"], 1)
        self.assertEqual(audit["rows"][0]["release_gate_state"], "no_publish_intent_guard_preserved_no_release")


if __name__ == "__main__":
    unittest.main()
