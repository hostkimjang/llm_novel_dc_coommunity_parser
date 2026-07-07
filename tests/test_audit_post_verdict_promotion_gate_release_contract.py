import unittest

from tools.audit_post_verdict_promotion_gate_release_contract import build_audit


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


if __name__ == "__main__":
    unittest.main()
