import unittest

from tools.audit_canonical_post_verdict_projection_contract import build_audit


class AuditCanonicalPostVerdictProjectionContractTest(unittest.TestCase):
    def test_c1_blocks_current_candidate_leak(self):
        queue = {
            "queue_id": "unit",
            "rows": [
                {
                    "post_id": 1,
                    "contract_batch_lane": "C1_expected_restore_or_candidate_scrub_contract",
                    "canonical_verdict": "EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED",
                    "canonical_title": "Expected Work",
                    "current_projection_candidate_title": "Wrong Candidate",
                }
            ],
        }
        projection_rows = [
            {
                "post_id": 1,
                "analysis_result": {
                    "identity": {
                        "novel_identity": {"official_title": "Wrong Candidate"},
                        "candidate_ledger_status": "safe_resolved",
                        "publish_allowed": True,
                    }
                },
            }
        ]

        audit = build_audit(contract_queue=queue, projection_rows=projection_rows, audit_id="unit")

        self.assertEqual(audit["gate"], "NO-GO")
        self.assertEqual(audit["summary"]["violation_counts"], {"current_candidate_leaked_after_expected_verdict": 1})
        self.assertEqual(audit["rows"][0]["outcome"], "current_candidate_leak_violation")

    def test_c1_scrubbed_without_restore_stays_pending_not_released(self):
        queue = {
            "queue_id": "unit",
            "rows": [
                {
                    "post_id": 1,
                    "contract_batch_lane": "C1_expected_restore_or_candidate_scrub_contract",
                    "canonical_verdict": "EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED",
                    "canonical_title": "Expected Work",
                    "current_projection_candidate_title": "Wrong Candidate",
                }
            ],
        }
        projection_rows = [
            {
                "post_id": 1,
                "analysis_result": {
                    "identity": {
                        "novel_identity": {"official_title": None, "heretic_url": None},
                        "candidate_ledger_status": "promotion_blocked",
                    }
                },
            }
        ]

        audit = build_audit(contract_queue=queue, projection_rows=projection_rows, audit_id="unit")

        self.assertEqual(audit["gate"], "REVIEW-LOCKED")
        self.assertEqual(audit["summary"]["pending_contract_rows"], 1)
        self.assertEqual(audit["summary"]["runtime_replay_allowed_rows"], 0)
        self.assertEqual(audit["rows"][0]["outcome"], "candidate_scrub_satisfied_expected_restore_pending")

    def test_c2_publish_before_policy_is_violation(self):
        queue = {
            "queue_id": "unit",
            "rows": [
                {
                    "post_id": 2,
                    "contract_batch_lane": "C2_canonical_variant_policy_contract",
                    "canonical_verdict": "RELATED_CANONICAL_VARIANT_CONFIRMED",
                    "canonical_title": "Canonical",
                    "current_projection_candidate_title": "Variant",
                }
            ],
        }
        projection_rows = [
            {
                "post_id": 2,
                "analysis_result": {
                    "identity": {
                        "novel_identity": {"official_title": "Canonical"},
                        "candidate_ledger_status": "safe_resolved",
                    }
                },
            }
        ]

        audit = build_audit(contract_queue=queue, projection_rows=projection_rows, audit_id="unit")

        self.assertEqual(audit["gate"], "NO-GO")
        self.assertEqual(audit["rows"][0]["violation_code"], "variant_published_before_policy_contract")

    def test_c3_hard_hold_preserved_is_satisfied_but_not_release(self):
        queue = {
            "queue_id": "unit",
            "rows": [
                {
                    "post_id": 3,
                    "contract_batch_lane": "C3_stronger_evidence_or_native_web_hold",
                    "canonical_verdict": "INSUFFICIENT_EVIDENCE_HOLD",
                    "current_projection_candidate_title": "Candidate",
                }
            ],
        }
        projection_rows = [
            {
                "post_id": 3,
                "analysis_result": {
                    "identity": {
                        "novel_identity": {"official_title": None},
                        "candidate_ledger_status": "promotion_blocked",
                    }
                },
            }
        ]

        audit = build_audit(contract_queue=queue, projection_rows=projection_rows, audit_id="unit")

        self.assertEqual(audit["gate"], "REVIEW-LOCKED")
        self.assertEqual(audit["summary"]["satisfied_contract_rows"], 1)
        self.assertEqual(audit["summary"]["runtime_replay_allowed_rows"], 0)
        self.assertEqual(audit["rows"][0]["outcome"], "hard_hold_preserved")


if __name__ == "__main__":
    unittest.main()
