import unittest

from tools.apply_candidate_set_projection_contract import apply_candidate_set_projection_contract
from tools.audit_post_verdict_promotion_gate_release_contract import build_audit
from tools.audit_publication_contract_convergence import audit_rows


def _publish_plan(post_id=1):
    scope = {"scope_kind": "current_work", "confidence": "high", "direct_bridge_sources": ["unit"]}
    return {
        "post_id": post_id,
        "contract_action": "candidate_set_expected_restore_contract_case",
        "target_title": "Expected Work",
        "target_url": "https://example.test/expected",
        "promotion_decision": {
            "status": "publish",
            "publish_allowed": True,
            "official_title": "Expected Work",
            "official_url": "https://example.test/expected",
            "candidate_preserved": False,
            "reason_codes": [
                "official_title_exists",
                "row_discusses_work_as_work",
                "scope_current_work",
                "candidate_set_source_native_contract_case",
            ],
            "bypassed_gate": False,
            "scope": scope,
        },
        "promotion_gate_state": {"scope": scope},
    }


def _rebuild_hold_plan(post_id=2):
    scope = {
        "scope_kind": "unknown",
        "confidence": "high",
        "direct_bridge_sources": ["unit"],
        "conflict_reason_codes": ["candidate_set_rebuild_required"],
    }
    return {
        "post_id": post_id,
        "contract_action": "candidate_set_rebuild_required_before_publish",
        "target_title": None,
        "target_url": None,
        "promotion_decision": {
            "status": "reject",
            "publish_allowed": False,
            "official_title": None,
            "official_url": None,
            "candidate_preserved": False,
            "reason_codes": [
                "no_candidate_title",
                "row_discussion_missing",
                "scope_unknown",
                "scope_not_current_work",
                "candidate_set_rebuild_required",
            ],
            "bypassed_gate": False,
            "scope": scope,
        },
        "promotion_gate_state": {"scope": scope},
    }


def _intent_hold_plan(post_id=4):
    scope = {
        "scope_kind": "platform_meta_nonwork",
        "confidence": "high",
        "direct_bridge_sources": ["unit"],
        "conflict_reason_codes": ["intent_guard_no_webnovel_promotion"],
    }
    return {
        "post_id": post_id,
        "contract_action": "no_publish_intent_guard_contract_case",
        "target_title": "Classic Surface",
        "target_url": None,
        "promotion_decision": {
            "status": "candidate_only",
            "publish_allowed": False,
            "official_title": None,
            "official_url": None,
            "candidate_preserved": True,
            "reason_codes": [
                "row_discussion_missing",
                "nonwork",
                "scope_platform_meta_nonwork",
                "scope_not_current_work",
                "intent_guard_no_webnovel_promotion",
            ],
            "bypassed_gate": False,
            "scope": scope,
        },
        "promotion_gate_state": {"scope": scope},
    }


def _public_projection(post_id, title, url="https://example.test/wrong"):
    decision = {
        "status": "publish",
        "publish_allowed": True,
        "official_title": title,
        "official_url": url,
        "candidate_preserved": False,
        "reason_codes": ["scope_current_work", "row_discusses_work_as_work"],
        "bypassed_gate": False,
        "scope": {"scope_kind": "current_work", "confidence": "medium"},
    }
    return {
        "post_id": post_id,
        "actual_title": title,
        "actual_url": url,
        "analysis_result": {
            "identity": {
                "candidate_ledger_status": "safe_resolved",
                "novel_identity": {"official_title": title, "heretic_url": url},
                "promotion_decision": decision,
                "candidate_ledger": {"promotion_decision": decision},
            }
        },
    }


def _blocked_projection(post_id=3):
    return {
        "post_id": post_id,
        "analysis_result": {
            "identity": {
                "candidate_ledger_status": "promotion_blocked",
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "blocked_official_title": "Blocked Candidate",
                "blocked_official_title_url": "https://example.test/blocked",
                "novel_identity": {"official_title": None, "heretic_url": None},
                "candidate_ledger": {
                    "candidate_ledger_status": "promotion_blocked",
                    "blocked_official_title": "Blocked Candidate",
                    "blocked_official_title_url": "https://example.test/blocked",
                },
            }
        },
    }


class ApplyCandidateSetProjectionContractTest(unittest.TestCase):
    def test_candidate_set_restore_and_holds_converge(self):
        plan = {
            "plan_id": "unit",
            "gate": "REVIEW-LOCKED",
            "full_scan_approval": False,
            "rows": [
                _publish_plan(1),
                _rebuild_hold_plan(2),
                _rebuild_hold_plan(3),
                _intent_hold_plan(4),
            ],
        }
        projection, report = apply_candidate_set_projection_contract(
            contract_plan=plan,
            projection_payload=[
                _public_projection(1, "Wrong Publish"),
                _public_projection(2, "Wrong Candidate"),
                _blocked_projection(3),
                _public_projection(4, "Wrong Same Surface Novel"),
            ],
            projection_id="unit",
        )

        self.assertEqual(report["gate"], "REVIEW-LOCKED")
        self.assertEqual(report["summary"]["applied_restore_rows"], 1)
        self.assertEqual(report["summary"]["applied_hold_rows"], 3)
        self.assertEqual(
            report["summary"]["completion_gate"],
            "adjusted full375 collateral GO + full_scan path",
        )
        self.assertEqual(report["summary"]["scrubbed_public_identity_rows"], 2)
        self.assertEqual(report["summary"]["already_blocked_hold_rows"], 1)

        by_post = {row["post_id"]: row for row in projection}
        restored = by_post[1]["analysis_result"]["identity"]
        self.assertEqual(restored["novel_identity"]["official_title"], "Expected Work")
        self.assertTrue(restored["promotion_decision"]["publish_allowed"])
        self.assertEqual(
            restored["publish_contract_trace"]["superseded_projection_candidate"]["official_title"],
            "Wrong Publish",
        )

        scrubbed = by_post[2]["analysis_result"]["identity"]
        self.assertIsNone(scrubbed["novel_identity"]["official_title"])
        self.assertFalse(scrubbed["promotion_decision"]["publish_allowed"])
        self.assertTrue(scrubbed["promotion_decision"]["candidate_preserved"])
        self.assertEqual(scrubbed["blocked_official_title"], "Wrong Candidate")
        self.assertIn("serialized_public_identity_scrubbed", scrubbed["promotion_decision"]["reason_codes"])

        release = build_audit(contract_plan=plan, projection_rows=projection, audit_id="unit_release")
        self.assertEqual(release["summary"]["violation_row_count"], 0)
        self.assertEqual(release["summary"]["pending_contract_rows"], 0)
        self.assertEqual(release["summary"]["release_candidate_after_contract_rows"], 1)
        self.assertEqual(release["summary"]["satisfied_no_release_rows"], 3)
        self.assertEqual(audit_rows(projection)["gate"], "GO")


if __name__ == "__main__":
    unittest.main()
