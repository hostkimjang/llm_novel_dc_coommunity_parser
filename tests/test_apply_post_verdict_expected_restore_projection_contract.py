import unittest

from tools.apply_post_verdict_expected_restore_projection_contract import apply_expected_restore_contract
from tools.audit_post_verdict_promotion_gate_release_contract import build_audit
from tools.audit_publication_contract_convergence import audit_rows


def _restore_plan_row(post_id=1):
    scope = {"scope_kind": "current_work", "confidence": "high", "direct_bridge_sources": ["unit"]}
    return {
        "post_id": post_id,
        "contract_action": "expected_title_restore_contract_case",
        "target_title": "Expected Work",
        "target_url": None,
        "current_projection_candidate_title": "Wrong Candidate",
        "current_projection_candidate_url": "https://example.test/wrong",
        "promotion_decision": {
            "status": "publish",
            "publish_allowed": True,
            "official_title": "Expected Work",
            "official_url": None,
            "candidate_preserved": False,
            "reason_codes": [
                "official_title_exists",
                "row_discusses_work_as_work",
                "scope_current_work",
            ],
            "bypassed_gate": False,
            "scope": scope,
        },
    }


def _blocked_projection_row(post_id=1):
    decision = {
        "status": "candidate_only",
        "publish_allowed": False,
        "official_title": None,
        "official_url": None,
        "candidate_preserved": True,
        "reason_codes": ["scope_context_only", "scope_not_current_work", "serialized_public_identity_scrubbed"],
        "bypassed_gate": False,
        "scope": {"scope_kind": "context_only", "confidence": "medium"},
    }
    trace = {
        "pre_gate_candidate": {
            "official_title": "Wrong Candidate",
            "official_url": "https://example.test/wrong",
            "source": "unit",
        },
        "gate_decision": decision,
        "scope_state": decision["scope"],
        "post_gate_identity": {
            "official_title": None,
            "official_url": None,
            "candidate_ledger_status": "promotion_blocked",
        },
        "reason_codes": decision["reason_codes"],
        "bypassed_gate": False,
    }
    ledger = {
        "candidate_preservation": trace["pre_gate_candidate"],
        "public_publish": trace["post_gate_identity"],
        "gate_decision": decision,
    }
    return {
        "post_id": post_id,
        "analysis_result": {
            "identity": {
                "candidate_ledger_status": "promotion_blocked",
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "novel_identity": {"official_title": None, "heretic_url": None},
                "title_candidates": [
                    {"official_title": "Wrong Candidate", "heretic_url": "https://example.test/wrong"}
                ],
                "promotion_decision": decision,
                "publish_contract_trace": trace,
                "publish_ledger": ledger,
                "candidate_ledger": {
                    "candidate_ledger_status": "promotion_blocked",
                    "promotion_decision": decision,
                    "publish_contract_trace": trace,
                    "publish_ledger": ledger,
                },
            }
        },
    }


class ApplyPostVerdictExpectedRestoreProjectionContractTest(unittest.TestCase):
    def test_restore_publish_decision_is_serialized_without_wrong_candidate_leak(self):
        plan = {"plan_id": "unit_plan", "rows": [_restore_plan_row()]}
        projection, report = apply_expected_restore_contract(
            contract_plan=plan,
            projection_payload=[_blocked_projection_row()],
            projection_id="unit_projection",
        )

        self.assertEqual(report["gate"], "REVIEW-LOCKED")
        self.assertEqual(report["summary"]["applied_restore_rows"], 1)
        identity = projection[0]["analysis_result"]["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "safe_resolved")
        self.assertEqual(identity["novel_identity"]["official_title"], "Expected Work")
        self.assertTrue(identity["promotion_decision"]["publish_allowed"])
        self.assertEqual(identity["publish_contract_trace"]["post_gate_identity"]["official_title"], "Expected Work")
        self.assertEqual(
            identity["publish_contract_trace"]["superseded_projection_candidate"]["official_title"],
            "Wrong Candidate",
        )
        self.assertEqual(audit_rows(projection)["gate"], "GO")

        release = build_audit(
            contract_plan=plan,
            projection_rows=projection,
            audit_id="unit_release",
        )
        self.assertEqual(release["summary"]["pending_contract_rows"], 0)
        self.assertEqual(release["summary"]["release_candidate_after_contract_rows"], 1)
        self.assertEqual(release["summary"]["violation_row_count"], 0)

    def test_non_restore_actions_are_not_changed(self):
        plan = {
            "plan_id": "unit_plan",
            "rows": [
                {
                    "post_id": 2,
                    "contract_action": "candidate_scrub_no_publish_contract_case",
                }
            ],
        }
        projection, report = apply_expected_restore_contract(
            contract_plan=plan,
            projection_payload=[_blocked_projection_row(post_id=2)],
            projection_id="unit_projection",
        )

        self.assertEqual(report["summary"]["applied_restore_rows"], 0)
        self.assertEqual(
            projection[0]["analysis_result"]["identity"]["candidate_ledger_status"],
            "promotion_blocked",
        )

    def test_missing_projection_row_is_validation_issue(self):
        plan = {"plan_id": "unit_plan", "rows": [_restore_plan_row(post_id=3)]}
        _projection, report = apply_expected_restore_contract(
            contract_plan=plan,
            projection_payload=[],
            projection_id="unit_projection",
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["validation_issues"][0]["issue"], "projection_row_missing")


if __name__ == "__main__":
    unittest.main()
