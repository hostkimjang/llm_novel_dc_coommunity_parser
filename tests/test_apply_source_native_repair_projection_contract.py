import unittest

from expert_main import _canonical_official_detail_url

from tools.apply_source_native_repair_projection_contract import apply_contract


class ApplySourceNativeRepairProjectionContractTest(unittest.TestCase):
    def test_canonical_official_detail_url_accepts_mobile_munpia_and_ridi_detail(self):
        self.assertEqual(
            _canonical_official_detail_url("https://m.munpia.com/novel/detail/567990"),
            "https://novel.munpia.com/567990",
        )
        self.assertEqual(
            _canonical_official_detail_url("https://ridibooks.com/books/425439440"),
            "https://ridibooks.com/books/425439440",
        )

    def test_applies_source_native_selected_title_through_shared_seed(self):
        projection = [
            {
                "post_id": 1,
                "title": "마줍 얘기",
                "content": ["마줍에 나오는 투명 우주 흡혈귀 얘기"],
                "comments": ["작품 설정 얘기"],
                "analysis_result": {
                    "identity": {
                        "candidate_ledger_status": "promotion_blocked",
                        "title_resolution_allowed": False,
                        "title_resolution_state": "unresolved_matchable",
                        "work_resolution": "unresolved",
                        "novel_identity": None,
                        "candidate_ledger": {},
                    }
                },
            }
        ]
        verdicts = {
            "rows": [
                {
                    "post_id": 1,
                    "review_label": "REPROCESS",
                    "selected_title": "마도서를 줍다 마법사가 되다",
                    "selected_url": "https://novelpia.com/novel/414963",
                    "source_native_verdict": "supported_safe_title_lost_to_null",
                    "evidence_grade": "Strong",
                    "action": [
                        "repair_safe_loss_restore_supported_title",
                        "shared_promotion_gate_wiring_required",
                    ],
                    "rationale_ko": "본문이 후보 작품 약칭과 설정 대상을 직접 연결한다.",
                }
            ]
        }

        result_rows, application = apply_contract(projection, verdicts, application_id="unit")

        identity = result_rows[0]["analysis_result"]["identity"]
        self.assertEqual(application["gate"], "REVIEW-LOCKED")
        self.assertFalse(application["full_scan_approval"])
        self.assertEqual(application["summary"]["applied_publish_rows"], 1)
        self.assertEqual(application["rows"][0]["outcome"], "applied_shared_gate_publish")
        self.assertEqual(identity["candidate_ledger_status"], "safe_resolved")
        self.assertTrue(identity["title_resolution_allowed"])
        self.assertEqual(identity["novel_identity"]["official_title"], "마도서를 줍다 마법사가 되다")
        self.assertIn(
            "projection_followup_shared_gate_seed_applied",
            identity["promotion_decision"]["reason_codes"],
        )
        self.assertEqual(identity["publish_contract_trace"]["gate_decision"], identity["promotion_decision"])

    def test_applies_wrong_work_restore_action_through_shared_seed(self):
        projection = [
            {
                "post_id": 12,
                "title": "무친년은 노맨스여서 별로임",
                "content": ["거의 1000회찬데 로맨스 없는게"],
                "comments": ["착즙각은 주시자나"],
                "analysis_result": {
                    "identity": {
                        "candidate_ledger_status": "safe_resolved",
                        "title_resolution_allowed": True,
                        "title_resolution_state": "resolved",
                        "work_resolution": "resolved",
                        "novel_identity": {
                            "official_title": "[무친년]이 무림의 미친놈",
                            "heretic_url": None,
                            "confidence": "High",
                        },
                        "candidate_ledger": {
                            "candidate_preservation_sources": [
                                {
                                    "official_title": "이 무림의 미친년은 나야",
                                    "heretic_url": "https://novelpia.com/novel/217943",
                                    "source_tier": "official_detail",
                                }
                            ]
                        },
                    }
                },
            }
        ]
        verdicts = {
            "rows": [
                {
                    "post_id": 12,
                    "review_label": "REPROCESS",
                    "selected_title": "이 무림의 미친년은 나야",
                    "selected_url": None,
                    "source_native_verdict": "source_alias_supports_official_title_after_variant_wrong_work",
                    "evidence_grade": "Strong",
                    "action": [
                        "repair_after_wrong_work",
                        "shared_promotion_gate_wiring_required",
                    ],
                    "rationale_ko": "`무친년`은 원문 작품 별칭이고 C1은 title variant/wrong work다.",
                }
            ]
        }

        result_rows, application = apply_contract(projection, verdicts, application_id="unit")

        identity = result_rows[0]["analysis_result"]["identity"]
        self.assertEqual(application["summary"]["eligible_restore_rows"], 1)
        self.assertEqual(application["summary"]["eligible_safe_loss_rows"], 0)
        self.assertEqual(application["summary"]["eligible_wrong_work_repair_rows"], 1)
        self.assertEqual(application["summary"]["applied_publish_rows"], 1)
        self.assertEqual(application["rows"][0]["outcome"], "applied_shared_gate_publish")
        self.assertIn("repair_after_wrong_work", application["rows"][0]["actions"])
        self.assertEqual(identity["candidate_ledger_status"], "safe_resolved")
        self.assertEqual(identity["novel_identity"]["official_title"], "이 무림의 미친년은 나야")
        self.assertEqual(identity["novel_identity"]["heretic_url"], "https://novelpia.com/novel/217943")

    def test_missing_official_url_stays_unpublished(self):
        projection = [
            {
                "post_id": 2,
                "title": "화산파 얘기",
                "content": ["화귀 댓글"],
                "comments": [],
                "analysis_result": {
                    "identity": {
                        "candidate_ledger_status": "promotion_blocked",
                        "title_resolution_allowed": False,
                        "novel_identity": None,
                        "candidate_ledger": {},
                    }
                },
            }
        ]
        verdicts = {
            "rows": [
                {
                    "post_id": 2,
                    "review_label": "REPROCESS",
                    "selected_title": "화산파(화산귀환)",
                    "selected_url": None,
                    "source_native_verdict": "supported_safe_title_lost_to_null",
                    "evidence_grade": "Strong",
                    "action": [
                        "repair_safe_loss_restore_supported_title",
                        "shared_promotion_gate_wiring_required",
                    ],
                }
            ]
        }

        result_rows, application = apply_contract(projection, verdicts, application_id="unit")

        identity = result_rows[0]["analysis_result"]["identity"]
        self.assertEqual(application["summary"]["applied_publish_rows"], 0)
        self.assertEqual(application["rows"][0]["outcome"], "skipped_missing_official_detail_url")
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertFalse(identity["title_resolution_allowed"])

    def test_recovers_matching_preserved_official_url_from_projection_row(self):
        projection = [
            {
                "post_id": 22,
                "title": "무마 웹툰 보는데",
                "content": ["무마랑 시로네 얘기"],
                "comments": [],
                "analysis_result": {
                    "identity": {
                        "candidate_ledger_status": "promotion_blocked",
                        "title_resolution_allowed": False,
                        "title_resolution_state": "unresolved_matchable",
                        "work_resolution": "unresolved",
                        "novel_identity": None,
                        "candidate_ledger": {
                            "candidate_preservation_sources": [
                                {
                                    "official_title": "무한의 마법사",
                                    "heretic_url": "https://novel.munpia.com/490453",
                                    "source_tier": "official_detail",
                                }
                            ]
                        },
                    }
                },
            }
        ]
        verdicts = {
            "rows": [
                {
                    "post_id": 22,
                    "review_label": "REPROCESS",
                    "selected_title": "무한의 마법사",
                    "selected_url": None,
                    "source_native_verdict": "direct_abbreviation_supports_safe_title_lost_to_null",
                    "evidence_grade": "Strong",
                    "action": [
                        "repair_safe_loss_restore_supported_title",
                        "shared_promotion_gate_wiring_required",
                    ],
                    "rationale_ko": "원문 약칭과 캐릭터 맥락이 같은 작품을 직접 지지한다.",
                }
            ]
        }

        result_rows, application = apply_contract(projection, verdicts, application_id="unit")

        identity = result_rows[0]["analysis_result"]["identity"]
        self.assertEqual(application["summary"]["applied_publish_rows"], 1)
        self.assertEqual(application["rows"][0]["selected_url"], "https://novel.munpia.com/490453")
        self.assertEqual(identity["candidate_ledger_status"], "safe_resolved")
        self.assertEqual(identity["novel_identity"]["official_title"], "무한의 마법사")

    def test_does_not_recover_preserved_url_from_different_candidate_title(self):
        projection = [
            {
                "post_id": 23,
                "title": "랫따싶 풀네임",
                "content": ["랫따싶이 뭔데"],
                "comments": [],
                "analysis_result": {
                    "identity": {
                        "candidate_ledger_status": "promotion_blocked",
                        "title_resolution_allowed": False,
                        "novel_identity": None,
                        "candidate_ledger": {
                            "candidate_preservation_sources": [
                                {
                                    "official_title": "다른 림월드 팬픽",
                                    "heretic_url": "https://novelpia.com/novel/409182",
                                    "source_tier": "official_detail",
                                }
                            ]
                        },
                    }
                },
            }
        ]
        verdicts = {
            "rows": [
                {
                    "post_id": 23,
                    "review_label": "REPROCESS",
                    "selected_title": "[림월드]변방계에서 회귀자로 살아남기",
                    "selected_url": None,
                    "source_native_verdict": "direct_alias_and_comment_context_support_safe_title_lost_to_null",
                    "evidence_grade": "Strong",
                    "action": [
                        "repair_safe_loss_restore_supported_title",
                        "shared_promotion_gate_wiring_required",
                    ],
                }
            ]
        }

        result_rows, application = apply_contract(projection, verdicts, application_id="unit")

        identity = result_rows[0]["analysis_result"]["identity"]
        self.assertEqual(application["summary"]["applied_publish_rows"], 0)
        self.assertEqual(application["rows"][0]["outcome"], "skipped_missing_official_detail_url")
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")

    def test_strong_source_native_verdict_overrides_reviewed_stale_context_hold(self):
        projection = [
            {
                "post_id": 3,
                "title": "별품소 얘기",
                "content": ["별품소 최신화 얘기"],
                "comments": [],
                "analysis_result": {
                    "identity": {
                        "candidate_ledger_status": "promotion_blocked",
                        "title_resolution_allowed": False,
                        "title_resolution_state": "context_only",
                        "work_resolution": "unresolved",
                        "consistency_flags": [
                            "recommendation_context_only_no_work_anchor",
                            "batch_memory_alias_rescue_blocked_nonwork_context",
                        ],
                        "novel_identity": None,
                        "candidate_ledger": {},
                    }
                },
            }
        ]
        verdicts = {
            "rows": [
                {
                    "post_id": 3,
                    "review_label": "REPROCESS",
                    "selected_title": "별을 품은 소드마스터",
                    "selected_url": "https://novel.munpia.com/254718",
                    "source_native_verdict": "direct_abbreviation_supports_safe_title_lost_to_null",
                    "evidence_grade": "Strong",
                    "action": [
                        "repair_safe_loss_restore_supported_title",
                        "shared_promotion_gate_wiring_required",
                    ],
                    "rationale_ko": "본문이 약칭과 작품 소비 맥락을 직접 연결한다.",
                }
            ]
        }

        result_rows, application = apply_contract(projection, verdicts, application_id="unit")

        identity = result_rows[0]["analysis_result"]["identity"]
        self.assertEqual(application["summary"]["applied_publish_rows"], 1)
        self.assertEqual(application["rows"][0]["outcome"], "applied_shared_gate_publish")
        self.assertEqual(identity["candidate_ledger_status"], "safe_resolved")
        self.assertEqual(identity["novel_identity"]["official_title"], "별을 품은 소드마스터")
        self.assertIn(
            "source_native_review_overrode_stale_context_hard_hold",
            identity["promotion_decision"]["reason_codes"],
        )

    def test_medium_source_native_verdict_keeps_stale_context_hold(self):
        projection = [
            {
                "post_id": 4,
                "title": "설정값 얘기",
                "content": ["추천 맥락이 섞여 있음"],
                "comments": [],
                "analysis_result": {
                    "identity": {
                        "candidate_ledger_status": "promotion_blocked",
                        "title_resolution_allowed": False,
                        "title_resolution_state": "context_only",
                        "work_resolution": "unresolved",
                        "consistency_flags": ["recommendation_context_only_no_work_anchor"],
                        "novel_identity": None,
                        "candidate_ledger": {},
                    }
                },
            }
        ]
        verdicts = {
            "rows": [
                {
                    "post_id": 4,
                    "review_label": "REPROCESS",
                    "selected_title": "설정값 딸깍으로 판타지 시스템 정상화",
                    "selected_url": "https://novelpia.com/novel/383584",
                    "source_native_verdict": "title_phrase_and_plot_context_support_safe_title_lost_to_null",
                    "evidence_grade": "Medium",
                    "action": [
                        "repair_safe_loss_restore_supported_title",
                        "shared_promotion_gate_wiring_required",
                    ],
                }
            ]
        }

        result_rows, application = apply_contract(projection, verdicts, application_id="unit")

        identity = result_rows[0]["analysis_result"]["identity"]
        self.assertEqual(application["summary"]["applied_publish_rows"], 0)
        self.assertEqual(application["rows"][0]["outcome"], "skipped_by_shared_gate")
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")


if __name__ == "__main__":
    unittest.main()
