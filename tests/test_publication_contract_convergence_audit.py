import unittest

from tools.audit_publication_contract_convergence import audit_rows


def _converged_publish_row():
    decision = {
        "status": "publish",
        "publish_allowed": True,
        "official_title": "이 무림의 미친년은 나야",
        "official_url": "https://novelpia.com/novel/217943",
        "candidate_preserved": False,
        "reason_codes": ["scope_current_work", "row_discusses_work_as_work"],
        "bypassed_gate": False,
    }
    trace = {
        "pre_gate_candidate": {
            "official_title": "이 무림의 미친년은 나야",
            "official_url": "https://novelpia.com/novel/217943",
        },
        "gate_decision": decision,
        "post_gate_identity": {
            "official_title": "이 무림의 미친년은 나야",
            "official_url": "https://novelpia.com/novel/217943",
        },
        "reason_codes": decision["reason_codes"],
        "bypassed_gate": False,
    }
    publish_ledger = {
        "candidate_preservation": trace["pre_gate_candidate"],
        "public_publish": trace["post_gate_identity"],
        "gate_decision": decision,
    }
    return {
        "post_id": 11674712,
        "analysis_result": {
            "identity": {
                "novel_identity": {
                    "official_title": "이 무림의 미친년은 나야",
                    "heretic_url": "https://novelpia.com/novel/217943",
                },
                "promotion_decision": decision,
                "publish_contract_trace": trace,
                "publish_ledger": publish_ledger,
                "candidate_ledger": {
                    "promotion_decision": decision,
                    "publish_contract_trace": trace,
                    "publish_ledger": publish_ledger,
                },
            }
        },
    }


class PublicationContractConvergenceAuditTest(unittest.TestCase):
    def test_converged_publish_contract_is_go(self):
        report = audit_rows([_converged_publish_row()])

        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["summary"]["violation_row_count"], 0)

    def test_public_title_without_contract_is_no_go(self):
        report = audit_rows(
            [
                {
                    "post_id": 11660237,
                    "analysis_result": {
                        "identity": {
                            "novel_identity": {
                                "official_title": "테라포밍",
                                "heretic_url": "https://novel.munpia.com/416826",
                            }
                        }
                    },
                }
            ]
        )

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row in report["violations"]
            for violation in row["violations"]
        }
        self.assertIn("missing_publication_decision_for_public_identity", codes)

    def test_blocked_decision_with_stale_public_trace_is_no_go(self):
        blocked_decision = {
            "status": "candidate_only",
            "publish_allowed": False,
            "official_title": None,
            "official_url": None,
            "candidate_preserved": True,
            "reason_codes": ["scope_context_only", "scope_not_current_work"],
            "bypassed_gate": False,
        }
        stale_publish_decision = {
            "status": "publish",
            "publish_allowed": True,
            "official_title": "가챠 중독자의 퓨전펑크 생활",
            "official_url": "https://novelpia.com/novel/387014",
            "candidate_preserved": False,
            "reason_codes": ["stale_publish"],
            "bypassed_gate": False,
        }
        stale_trace = {
            "pre_gate_candidate": {
                "official_title": "가챠 중독자의 퓨전펑크 생활",
                "official_url": "https://novelpia.com/novel/387014",
            },
            "gate_decision": stale_publish_decision,
            "post_gate_identity": {
                "official_title": "가챠 중독자의 퓨전펑크 생활",
                "official_url": "https://novelpia.com/novel/387014",
            },
        }
        stale_ledger = {
            "candidate_preservation": stale_trace["pre_gate_candidate"],
            "public_publish": stale_trace["post_gate_identity"],
            "gate_decision": stale_publish_decision,
        }
        report = audit_rows(
            [
                {
                    "post_id": 11698880,
                    "analysis_result": {
                        "identity": {
                            "novel_identity": {
                                "official_title": "가챠 중독자의 퓨전펑크 생활",
                                "heretic_url": "https://novelpia.com/novel/387014",
                            },
                            "promotion_decision": blocked_decision,
                            "publish_contract_trace": stale_trace,
                            "publish_ledger": stale_ledger,
                            "candidate_ledger": {
                                "promotion_decision": blocked_decision,
                                "publish_contract_trace": stale_trace,
                                "publish_ledger": stale_ledger,
                            },
                        }
                    },
                }
            ]
        )

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row in report["violations"]
            for violation in row["violations"]
        }
        self.assertIn("publish_contract_trace_gate_decision_mismatch", codes)
        self.assertIn("publish_ledger_gate_decision_mismatch", codes)
        self.assertIn("blocked_trace_publishes_title", codes)
        self.assertIn("blocked_ledger_publishes_title", codes)
        self.assertIn("blocked_serialized_public_title_leak", codes)


if __name__ == "__main__":
    unittest.main()
