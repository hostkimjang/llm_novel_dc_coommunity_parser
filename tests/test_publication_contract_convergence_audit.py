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


def _converged_scrubbed_candidate_row():
    scope = {
        "scope_kind": "context_only",
        "confidence": "medium",
        "conflict_reason_codes": ["scope_contract_unit"],
    }
    decision = {
        "status": "candidate_only",
        "publish_allowed": False,
        "official_title": None,
        "official_url": None,
        "candidate_preserved": True,
        "reason_codes": [
            "scope_context_only",
            "scope_not_current_work",
            "serialized_public_identity_scrubbed",
        ],
        "bypassed_gate": False,
        "scope": scope,
    }
    pre_gate = {
        "official_title": "아카데미 생존 갤러리",
        "official_url": "https://novelpia.com/novel/380218",
        "source": "serialized_public_identity",
    }
    post_gate = {
        "official_title": None,
        "official_url": None,
        "candidate_ledger_status": "promotion_blocked",
    }
    trace = {
        "pre_gate_candidate": pre_gate,
        "gate_decision": decision,
        "scope_state": scope,
        "post_gate_identity": post_gate,
        "reason_codes": decision["reason_codes"],
        "bypassed_gate": False,
    }
    publish_ledger = {
        "candidate_preservation": pre_gate,
        "public_publish": post_gate,
        "gate_decision": decision,
    }
    return {
        "post_id": 11698880,
        "analysis_result": {
            "identity": {
                "candidate_ledger_status": "promotion_blocked",
                "blocked_official_title": "아카데미 생존 갤러리",
                "blocked_official_title_url": "https://novelpia.com/novel/380218",
                "promotion_decision": decision,
                "publish_contract_trace": trace,
                "publish_ledger": publish_ledger,
                "candidate_ledger": {
                    "candidate_ledger_status": "promotion_blocked",
                    "blocked_official_title": "아카데미 생존 갤러리",
                    "blocked_official_title_url": "https://novelpia.com/novel/380218",
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

    def test_scrubbed_blocked_candidate_preservation_contract_is_go(self):
        report = audit_rows([_converged_scrubbed_candidate_row()])

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

    def test_scrubbed_blocked_decision_requires_candidate_preservation(self):
        decision = {
            "status": "candidate_only",
            "publish_allowed": False,
            "official_title": None,
            "official_url": None,
            "candidate_preserved": True,
            "reason_codes": ["serialized_public_identity_scrubbed"],
            "bypassed_gate": False,
        }
        trace = {
            "gate_decision": decision,
            "post_gate_identity": {"official_title": None, "official_url": None},
            "reason_codes": decision["reason_codes"],
            "bypassed_gate": False,
        }
        publish_ledger = {
            "public_publish": trace["post_gate_identity"],
            "gate_decision": decision,
        }
        report = audit_rows(
            [
                {
                    "post_id": 11660271,
                    "analysis_result": {
                        "identity": {
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
            ]
        )

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row in report["violations"]
            for violation in row["violations"]
        }
        self.assertIn("blocked_candidate_preservation_missing", codes)

    def test_scrubbed_hold_without_candidates_is_converged_without_candidate_payload(self):
        decision = {
            "status": "candidate_only",
            "publish_allowed": False,
            "official_title": None,
            "official_url": None,
            "candidate_preserved": False,
            "reason_codes": ["hold_without_candidates", "serialized_public_identity_scrubbed"],
            "bypassed_gate": False,
        }
        pre_gate = {
            "official_title": None,
            "official_url": None,
            "source": "candidate_ledger_or_serialized_identity",
        }
        post_gate = {"official_title": None, "official_url": None}
        trace = {
            "pre_gate_candidate": pre_gate,
            "gate_decision": decision,
            "post_gate_identity": post_gate,
            "reason_codes": decision["reason_codes"],
            "bypassed_gate": False,
        }
        publish_ledger = {
            "candidate_preservation": pre_gate,
            "public_publish": post_gate,
            "gate_decision": decision,
        }
        report = audit_rows(
            [
                {
                    "post_id": 11665122,
                    "analysis_result": {
                        "identity": {
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
            ]
        )

        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["summary"]["violation_row_count"], 0)

    def test_scrubbed_decision_must_mark_candidate_preserved(self):
        row = _converged_scrubbed_candidate_row()
        identity = row["analysis_result"]["identity"]
        decision = dict(identity["promotion_decision"])
        decision["candidate_preserved"] = False
        identity["promotion_decision"] = decision
        identity["publish_contract_trace"] = {
            **identity["publish_contract_trace"],
            "gate_decision": decision,
        }
        identity["publish_ledger"] = {
            **identity["publish_ledger"],
            "gate_decision": decision,
        }
        identity["candidate_ledger"] = {
            **identity["candidate_ledger"],
            "promotion_decision": decision,
            "publish_contract_trace": identity["publish_contract_trace"],
            "publish_ledger": identity["publish_ledger"],
        }

        report = audit_rows([row])

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }
        self.assertIn("scrubbed_decision_not_candidate_preserved", codes)

    def test_candidate_preservation_trace_and_ledger_must_match(self):
        row = _converged_scrubbed_candidate_row()
        identity = row["analysis_result"]["identity"]
        publish_ledger = dict(identity["publish_ledger"])
        publish_ledger["candidate_preservation"] = {
            "official_title": "다른 후보",
            "official_url": "https://example.test/other",
        }
        identity["publish_ledger"] = publish_ledger
        identity["candidate_ledger"] = {
            **identity["candidate_ledger"],
            "publish_ledger": publish_ledger,
        }

        report = audit_rows([row])

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }
        self.assertIn("candidate_preservation_trace_ledger_mismatch", codes)

    def test_scope_state_must_match_promotion_decision_scope(self):
        row = _converged_scrubbed_candidate_row()
        identity = row["analysis_result"]["identity"]
        identity["publish_contract_trace"] = {
            **identity["publish_contract_trace"],
            "scope_state": {
                "scope_kind": "current_work",
                "confidence": "high",
            },
        }
        identity["candidate_ledger"] = {
            **identity["candidate_ledger"],
            "publish_contract_trace": identity["publish_contract_trace"],
        }

        report = audit_rows([row])

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }
        self.assertIn("publish_contract_trace_scope_state_mismatch", codes)

    def test_scope_kind_requires_matching_reason_code(self):
        row = _converged_scrubbed_candidate_row()
        identity = row["analysis_result"]["identity"]
        decision = dict(identity["promotion_decision"])
        decision["reason_codes"] = [
            "scope_not_current_work",
            "serialized_public_identity_scrubbed",
        ]
        identity["promotion_decision"] = decision
        identity["publish_contract_trace"] = {
            **identity["publish_contract_trace"],
            "gate_decision": decision,
            "reason_codes": decision["reason_codes"],
        }
        identity["publish_ledger"] = {
            **identity["publish_ledger"],
            "gate_decision": decision,
        }
        identity["candidate_ledger"] = {
            **identity["candidate_ledger"],
            "promotion_decision": decision,
            "publish_contract_trace": identity["publish_contract_trace"],
            "publish_ledger": identity["publish_ledger"],
        }

        report = audit_rows([row])

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }
        self.assertIn("promotion_decision_scope_reason_missing", codes)

    def test_non_current_scope_cannot_carry_current_work_reason(self):
        row = _converged_scrubbed_candidate_row()
        identity = row["analysis_result"]["identity"]
        decision = dict(identity["promotion_decision"])
        decision["reason_codes"] = [
            "scope_context_only",
            "scope_current_work",
            "serialized_public_identity_scrubbed",
            "serialized_public_identity_published",
        ]
        identity["promotion_decision"] = decision
        identity["publish_contract_trace"] = {
            **identity["publish_contract_trace"],
            "gate_decision": decision,
            "reason_codes": decision["reason_codes"],
        }
        identity["publish_ledger"] = {
            **identity["publish_ledger"],
            "gate_decision": decision,
        }
        identity["candidate_ledger"] = {
            **identity["candidate_ledger"],
            "promotion_decision": decision,
            "publish_contract_trace": identity["publish_contract_trace"],
            "publish_ledger": identity["publish_ledger"],
        }

        report = audit_rows([row])

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }
        self.assertIn("scope_non_current_conflicts_with_current_reason", codes)
        self.assertIn("blocked_non_current_scope_missing_not_current_reason", codes)
        self.assertIn("blocked_decision_has_publish_only_reason", codes)
        self.assertIn("published_and_scrubbed_reason_conflict", codes)

    def test_publish_allowed_requires_current_work_scope(self):
        row = _converged_publish_row()
        identity = row["analysis_result"]["identity"]
        scope = {"scope_kind": "context_only", "confidence": "medium"}
        decision = {
            **identity["promotion_decision"],
            "scope": scope,
            "reason_codes": ["scope_context_only", "row_discusses_work_as_work"],
        }
        identity["promotion_decision"] = decision
        identity["publish_contract_trace"] = {
            **identity["publish_contract_trace"],
            "gate_decision": decision,
            "scope_state": scope,
            "reason_codes": decision["reason_codes"],
        }
        identity["publish_ledger"] = {
            **identity["publish_ledger"],
            "gate_decision": decision,
        }
        identity["candidate_ledger"] = {
            **identity["candidate_ledger"],
            "promotion_decision": decision,
            "publish_contract_trace": identity["publish_contract_trace"],
            "publish_ledger": identity["publish_ledger"],
        }

        report = audit_rows([row])

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }
        self.assertIn("publish_allowed_non_current_scope", codes)

    def test_official_url_withheld_reason_allows_title_only_publication(self):
        row = _converged_publish_row()
        identity = row["analysis_result"]["identity"]
        decision = dict(identity["promotion_decision"])
        decision["official_url"] = None
        decision["reason_codes"] = [
            *decision["reason_codes"],
            "official_url_withheld_by_title_mismatch",
        ]
        trace = {
            **identity["publish_contract_trace"],
            "gate_decision": decision,
            "post_gate_identity": {
                **identity["publish_contract_trace"]["post_gate_identity"],
                "official_url": None,
            },
            "reason_codes": decision["reason_codes"],
        }
        publish_ledger = {
            **identity["publish_ledger"],
            "public_publish": trace["post_gate_identity"],
            "gate_decision": decision,
        }
        identity["novel_identity"]["heretic_url"] = None
        identity["promotion_decision"] = decision
        identity["publish_contract_trace"] = trace
        identity["publish_ledger"] = publish_ledger
        identity["candidate_ledger"] = {
            **identity["candidate_ledger"],
            "promotion_decision": decision,
            "publish_contract_trace": trace,
            "publish_ledger": publish_ledger,
        }

        report = audit_rows([row])

        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["summary"]["violation_row_count"], 0)

    def test_official_url_withheld_reason_must_not_publish_url(self):
        row = _converged_publish_row()
        identity = row["analysis_result"]["identity"]
        decision = dict(identity["promotion_decision"])
        decision["reason_codes"] = [
            *decision["reason_codes"],
            "official_url_withheld_by_title_mismatch",
        ]
        identity["promotion_decision"] = decision
        identity["publish_contract_trace"] = {
            **identity["publish_contract_trace"],
            "gate_decision": decision,
            "reason_codes": decision["reason_codes"],
        }
        identity["publish_ledger"] = {
            **identity["publish_ledger"],
            "gate_decision": decision,
        }
        identity["candidate_ledger"] = {
            **identity["candidate_ledger"],
            "promotion_decision": decision,
            "publish_contract_trace": identity["publish_contract_trace"],
            "publish_ledger": identity["publish_ledger"],
        }

        report = audit_rows([row])

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }
        self.assertIn("official_url_withheld_reason_has_decision_url", codes)
        self.assertIn("official_url_withheld_reason_publishes_trace_url", codes)
        self.assertIn("official_url_withheld_reason_publishes_ledger_url", codes)
        self.assertIn("official_url_withheld_reason_serialized_url_leak", codes)

    def test_url_title_mismatch_block_reason_must_block_and_preserve_candidate_url(self):
        row = _converged_publish_row()
        identity = row["analysis_result"]["identity"]
        decision = {
            **identity["promotion_decision"],
            "reason_codes": [
                *identity["promotion_decision"]["reason_codes"],
                "url_title_mismatch",
                "official_detail_url_title_mismatch_publish_blocked",
            ],
        }
        identity["promotion_decision"] = decision
        identity["publish_contract_trace"] = {
            **identity["publish_contract_trace"],
            "gate_decision": decision,
            "reason_codes": decision["reason_codes"],
        }
        identity["publish_ledger"] = {
            **identity["publish_ledger"],
            "gate_decision": decision,
        }
        identity["candidate_ledger"] = {
            **identity["candidate_ledger"],
            "promotion_decision": decision,
            "publish_contract_trace": identity["publish_contract_trace"],
            "publish_ledger": identity["publish_ledger"],
        }

        report = audit_rows([row])

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }
        self.assertIn("url_title_mismatch_block_reason_allows_publish", codes)
        self.assertIn("url_title_mismatch_block_reason_has_decision_url", codes)

    def test_url_title_mismatch_block_reason_requires_candidate_url_preservation(self):
        row = _converged_scrubbed_candidate_row()
        identity = row["analysis_result"]["identity"]
        decision = {
            **identity["promotion_decision"],
            "reason_codes": [
                *identity["promotion_decision"]["reason_codes"],
                "url_title_mismatch",
                "official_detail_url_title_mismatch_publish_blocked",
            ],
        }
        trace = {
            **identity["publish_contract_trace"],
            "pre_gate_candidate": {
                "official_title": "아카데미 생존 갤러리",
                "official_url": None,
                "source": "candidate_ledger_or_serialized_identity",
            },
            "gate_decision": decision,
            "reason_codes": decision["reason_codes"],
        }
        publish_ledger = {
            **identity["publish_ledger"],
            "candidate_preservation": trace["pre_gate_candidate"],
            "gate_decision": decision,
        }
        identity["blocked_official_title_url"] = None
        identity["candidate_ledger"]["blocked_official_title_url"] = None
        identity["promotion_decision"] = decision
        identity["publish_contract_trace"] = trace
        identity["publish_ledger"] = publish_ledger
        identity["candidate_ledger"] = {
            **identity["candidate_ledger"],
            "promotion_decision": decision,
            "publish_contract_trace": trace,
            "publish_ledger": publish_ledger,
        }

        report = audit_rows([row])

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }
        self.assertIn("url_title_mismatch_candidate_url_not_preserved", codes)


if __name__ == "__main__":
    unittest.main()
