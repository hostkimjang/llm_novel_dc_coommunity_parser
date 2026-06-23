import json
import tempfile
import unittest
from pathlib import Path

from tools.compare_completed779_improvement import build_reimprovement_queue, compare, write_queue_markdown


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


class Completed779CompareTest(unittest.TestCase):
    def test_precision_title_match_with_wrong_url_remains_reimprovement_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed.jsonl"
            after = root / "after.json"
            write_jsonl(
                seed,
                [
                    {
                        "post_id": 11697267,
                        "seed_bucket": "precision_identity_high",
                        "disagreement_type": "reason_evidence_mismatch",
                        "recommended_action": "source_upgrade",
                        "independent_official_title": "아카데미 생존 갤러리",
                        "independent_url": "https://novelpia.com/novel/380218",
                        "pipeline_official_title": "아카데미 생존 갤러리",
                        "pipeline_url": "https://novelpia.com/novel/415486",
                    }
                ],
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11697267,
                            "analysis_result": {
                                "identity": {
                                    "novel_identity": {
                                        "official_title": "아카데미 생존 갤러리",
                                        "heretic_url": "https://novelpia.com/novel/415486",
                                    },
                                    "title_resolution_state": "resolved",
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)
            queue = build_reimprovement_queue(report, canary_kind="text_url_comment")

            self.assertEqual(report["total_seed_rows"], 1)
            self.assertEqual(report["after_rows_matched"], 1)
            self.assertEqual(report["rows"][0]["movement_status"], "title_match_url_still_mismatched")
            self.assertEqual(queue["rows"][0]["acceptance_status"], "still_bad")
            self.assertEqual(queue["rows"][0]["expected_url"], "https://novelpia.com/novel/380218")

    def test_only_after_posts_scopes_split_canary_seed_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed.jsonl"
            after = root / "after.json"
            write_jsonl(
                seed,
                [
                    {"post_id": 1, "seed_bucket": "recall_relevance_representative"},
                    {"post_id": 2, "seed_bucket": "recall_relevance_representative"},
                ],
            )
            after.write_text(
                json.dumps([{"post_id": 1, "analysis_result": {"identity": {}}}]),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)

            self.assertEqual(report["total_seed_rows"], 1)
            self.assertEqual(report["after_rows_matched"], 1)
            self.assertEqual(report["rows"][0]["post_id"], 1)

    def test_completed_wrapper_result_row_is_unwrapped_for_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed.jsonl"
            after = root / "after.json"
            write_jsonl(
                seed,
                [
                    {
                        "post_id": 11700473,
                        "seed_bucket": "source_url_hygiene",
                        "expected_title": "로판 속 주인공이 나만 좋아함",
                        "expected_url": "https://novelpia.com/novel/347085",
                    }
                ],
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "global_idx": 1,
                            "post_id": 11700473,
                            "status": "completed",
                            "result": {
                                "post_id": 11700473,
                                "analysis_result": {
                                    "identity": {
                                        "novel_identity": {
                                            "official_title": "로판 속 주인공이 나만 좋아함",
                                            "heretic_url": "https://novelpia.com/novel/347085",
                                        },
                                        "title_resolution_state": "resolved",
                                    }
                                },
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)

            self.assertEqual(report["after_rows_matched"], 1)
            self.assertEqual(report["rows"][0]["after_identity"]["official_title"], "로판 속 주인공이 나만 좋아함")
            self.assertEqual(report["rows"][0]["movement_status"], "resolved_expected_title_and_url")

    def test_loop7_queue_metadata_is_preserved_for_compare_requeue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed.jsonl"
            after = root / "after.json"
            write_jsonl(
                seed,
                [
                    {
                        "post_id": 11702060,
                        "queue_role": "main",
                        "selection_bucket": "loop7_wrong_relevance",
                        "selection_reason": "main:loop7_wrong_relevance",
                        "seed_bucket": "recall_relevance_representative",
                        "disagreement_type": "wrong_relevance",
                    }
                ],
            )
            after.write_text(
                json.dumps([{"post_id": 11702060, "analysis_result": {"identity": {}}}]),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)
            queue = build_reimprovement_queue(report, canary_kind="hermes_loop7")

            self.assertEqual(report["rows"][0]["queue_role"], "main")
            self.assertEqual(report["rows"][0]["selection_bucket"], "loop7_wrong_relevance")
            self.assertEqual(queue["rows"][0]["queue_role"], "main")
            self.assertEqual(queue["rows"][0]["selection_bucket"], "loop7_wrong_relevance")

    def test_queue_markdown_uses_custom_title_and_role_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.md"
            write_queue_markdown(
                path,
                {
                    "canary_kind": "hermes_loop7",
                    "rows": [
                        {
                            "post_id": 1,
                            "queue_role": "control",
                            "selection_bucket": "loop7_operational_residual_review",
                            "seed_bucket": "source_url_hygiene",
                            "movement_status": "title_or_url_still_mismatched",
                        }
                    ],
                },
                title="completed779 Hermes Loop 7 Remaining Queue",
            )

            text = path.read_text(encoding="utf-8")
            self.assertIn("# completed779 Hermes Loop 7 Remaining Queue", text)
            self.assertIn("| post_id | role | selection | bucket | issue |", text)
            self.assertNotIn("Loop 2 Remaining Queue", text)

    def test_precision_title_match_with_missing_expected_url_is_not_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed.jsonl"
            after = root / "after.json"
            write_jsonl(
                seed,
                [
                    {
                        "post_id": 11697267,
                        "seed_bucket": "precision_identity_high",
                        "disagreement_type": "reason_evidence_mismatch",
                        "independent_official_title": "아카데미 생존 갤러리",
                        "independent_url": "https://novelpia.com/novel/380218",
                    }
                ],
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11697267,
                            "analysis_result": {
                                "identity": {
                                    "novel_identity": {
                                        "official_title": "아카데미 생존 갤러리",
                                        "heretic_url": None,
                                    }
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)

            self.assertEqual(report["rows"][0]["movement_status"], "title_match_url_still_mismatched")

    def test_garbage_snippet_title_is_reimprovement_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed.jsonl"
            after = root / "after.json"
            write_jsonl(
                seed,
                [
                    {
                        "post_id": 11716482,
                        "seed_bucket": "candidate_comment_multi",
                        "disagreement_type": "conflicting_or_multi_candidate",
                    }
                ],
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11716482,
                            "analysis_result": {
                                "identity": {
                                    "novel_identity": {
                                        "official_title": (
                                            "개요 정신 질환자란 망상, 환각, 사고나 기분의 장애 등으로 "
                                            "일상생활에 중대한 제약이 있는 사람을 말한다."
                                        ),
                                        "heretic_url": "https://ridibooks.com/books/120104954",
                                    },
                                    "title_resolution_state": "resolved",
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)
            queue = build_reimprovement_queue(report, canary_kind="image_ocr")

            self.assertEqual(report["rows"][0]["movement_status"], "garbage_title_after")
            self.assertEqual(queue["rows"][0]["acceptance_status"], "still_bad")

    def test_url_or_domain_title_is_pollution_not_url_upgrade(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed.jsonl"
            after = root / "after.json"
            write_jsonl(
                seed,
                [
                    {
                        "post_id": 11700001,
                        "seed_bucket": "source_url_hygiene",
                        "disagreement_type": "title_correct_url_mismatch",
                        "recommended_action": "source_upgrade",
                        "independent_official_title": "판초우의의 마법사",
                        "independent_url": "https://novel.munpia.com/530500",
                        "pipeline_url": None,
                    }
                ],
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11700001,
                            "analysis_result": {
                                "identity": {
                                    "novel_identity": {
                                        "official_title": "https://novel.munpia.com/530500",
                                        "heretic_url": "https://novel.munpia.com/530500",
                                    },
                                    "title_resolution_state": "resolved",
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)
            queue = build_reimprovement_queue(report, canary_kind="text_url_comment")

            self.assertEqual(report["rows"][0]["movement_status"], "garbage_title_after")
            self.assertEqual(queue["rows"][0]["acceptance_status"], "still_bad")

    def test_queue_shaped_source_url_hygiene_row_is_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "queue.json"
            after = root / "after.json"
            seed.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "post_id": 11711631,
                                "seed_bucket": "source_url_hygiene",
                                "disagreement_type": "title_correct_url_mismatch",
                                "recommended_action": "source_upgrade",
                                "before_title": "하남자의 탑 공략법",
                                "before_url": "https://example.com/community/11711631",
                                "expected_title": "하남자의 탑 공략법",
                                "expected_url": "https://novelpia.com/novel/123456",
                                "movement_status": "title_or_url_still_mismatched",
                                "observed_problem": "Loop1 kept a community URL.",
                                "suspected_code_hook": "official_url_upgrade",
                                "proposed_next_fix": "prefer official detail URL",
                                "required_test": "source_url_hygiene_upgrade",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11711631,
                            "analysis_result": {
                                "identity": {
                                    "novel_identity": {
                                        "official_title": "하남자의 탑 공략법",
                                        "heretic_url": "https://example.com/community/11711631",
                                    }
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)
            queue = build_reimprovement_queue(report, canary_kind="loop2")

            self.assertEqual(report["total_seed_rows"], 1)
            self.assertEqual(report["rows"][0]["expected_independent_url"], "https://novelpia.com/novel/123456")
            self.assertEqual(report["rows"][0]["baseline_pipeline_url"], "https://example.com/community/11711631")
            self.assertEqual(report["rows"][0]["movement_status"], "title_or_url_still_mismatched")
            self.assertEqual(queue["rows"][0]["source_queue_movement_status"], "title_or_url_still_mismatched")
            self.assertEqual(queue["rows"][0]["observed_problem"], "Loop1 kept a community URL.")
            self.assertEqual(queue["rows"][0]["suspected_code_hook"], "official_url_upgrade")
            self.assertEqual(queue["rows"][0]["required_test"], "source_url_hygiene_upgrade")

    def test_queue_shaped_candidate_row_can_close_as_candidate_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "queue.json"
            after = root / "after.json"
            seed.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "post_id": 11716482,
                                "seed_bucket": "candidate_comment_multi",
                                "disagreement_type": "conflicting_or_multi_candidate",
                                "before_title": None,
                                "before_url": None,
                                "expected_title": "판초우의의 마법사",
                                "expected_url": "https://novelpia.com/novel/999999",
                                "movement_status": "still_under_resolved_or_noise",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11716482,
                            "analysis_result": {
                                "identity": {
                                    "title_resolution_state": "hold",
                                    "candidate_ledger": {"candidate_count": 2},
                                    "title_candidates": [
                                        {
                                            "official_title": "판초우의의 마법사",
                                            "heretic_url": "https://novelpia.com/novel/999999",
                                        }
                                    ],
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)

            self.assertEqual(report["rows"][0]["movement_status"], "candidate_or_human_review_preserved")
            self.assertTrue(report["rows"][0]["evidence_flags"]["expected_title_in_candidates"])
            self.assertEqual(report["movement_status_counts"], {"candidate_or_human_review_preserved": 1})

    def test_recall_relevance_wrong_final_title_stays_reimprovement_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "queue.json"
            after = root / "after.json"
            seed.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "post_id": 11716462,
                                "seed_bucket": "recall_relevance_representative",
                                "disagreement_type": "under_resolved_false_negative",
                                "expected_title": "니들 생각 다 들린다",
                                "expected_url": "https://novelpia.com/novel/375702",
                                "movement_status": "still_under_resolved_or_noise",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11716462,
                            "analysis_result": {
                                "identity": {
                                    "novel_identity": {
                                        "official_title": "분양받은 히로인을 유기하지 말아 주새오",
                                        "heretic_url": "https://novelpia.com/novel/219258",
                                    },
                                    "title_resolution_state": "resolved",
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)
            queue = build_reimprovement_queue(report, canary_kind="hermes_loop8")

            self.assertEqual(report["rows"][0]["movement_status"], "title_or_url_still_mismatched")
            self.assertEqual(queue["rows"][0]["acceptance_status"], "still_bad")

    def test_source_url_hygiene_lint_or_hold_is_safe_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "queue.json"
            after = root / "after.json"
            seed.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "post_id": 11702055,
                                "seed_bucket": "source_url_hygiene",
                                "expected_title": "즉사기 들고 무림에 떨어지다",
                                "expected_url": "https://novelpia.com/novel/102155",
                                "before_title": "즉사기 들고 무림에 떨어지다",
                                "before_url": "https://namu.wiki/w/example-character",
                                "movement_status": "title_or_url_still_mismatched",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11702055,
                            "analysis_result": {
                                "identity": {
                                    "novel_identity": {
                                        "official_title": "즉사기 들고 무림에 떨어지다",
                                        "heretic_url": "https://namu.wiki/w/example-character",
                                    },
                                    "title_resolution_state": "hold",
                                    "identity_consistency_lint": {
                                        "status": "url_mismatch",
                                        "reason": "wiki/person URL is not an official detail page.",
                                    },
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)
            queue = build_reimprovement_queue(report, canary_kind="loop2")

            self.assertEqual(report["rows"][0]["movement_status"], "url_lint_preserved")
            self.assertEqual(queue["rows"], [])

    def test_precision_wrong_work_control_closes_when_expected_candidate_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "queue.json"
            after = root / "after.json"
            seed.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "post_id": 11694064,
                                "seed_bucket": "precision_wrong_work_control",
                                "disagreement_type": "wrong_work",
                                "expected_title": "판초우의의 마법사",
                                "expected_url": "https://novel.munpia.com/530500",
                                "before_title": "무협 게임에 빙의했다. 문제는 나는 스토리를 보지 않는 스킵충이다",
                                "before_url": "https://novelpia.com/novel/416507",
                                "movement_status": "review",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11694064,
                            "analysis_result": {
                                "identity": {
                                    "title_resolution_state": "unresolved_matchable",
                                    "title_resolution_allowed": False,
                                    "novel_identity": {
                                        "official_title": None,
                                        "heretic_url": None,
                                    },
                                    "primary_work": {
                                        "official_title": "판초우의의 마법사",
                                        "heretic_url": "https://novel.munpia.com/530500",
                                    },
                                    "title_candidates": [
                                        {
                                            "official_title": "판초우의의 마법사",
                                            "heretic_url": "https://novel.munpia.com/530500",
                                        }
                                    ],
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)
            queue = build_reimprovement_queue(report, canary_kind="hermes_loop8")

            self.assertEqual(report["rows"][0]["movement_status"], "blocked_or_candidate_preserved")
            self.assertTrue(report["rows"][0]["evidence_flags"]["expected_title_in_candidates"])
            self.assertTrue(report["rows"][0]["evidence_flags"]["expected_url_in_candidates"])
            self.assertEqual(report["rows"][0]["after_identity"]["candidate_titles"], ["판초우의의 마법사"])
            self.assertEqual(queue["rows"], [])

    def test_precision_wrong_work_control_without_expected_candidate_stays_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "queue.json"
            after = root / "after.json"
            seed.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "post_id": 11703631,
                                "seed_bucket": "precision_wrong_work_control",
                                "disagreement_type": "wrong_work",
                                "expected_title": "나의 악당들",
                                "expected_url": "https://page.kakao.com/content/55826557",
                                "before_title": "7인의 피카레스크",
                                "before_url": "https://novelpia.com/novel/396754",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11703631,
                            "analysis_result": {
                                "identity": {
                                    "title_resolution_state": "unresolved_matchable",
                                    "candidate_ledger": {"candidate_count": 1},
                                    "title_candidates": [
                                        {
                                            "official_title": "7인의 피카레스크",
                                            "heretic_url": "https://novelpia.com/novel/396754",
                                        }
                                    ],
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)
            queue = build_reimprovement_queue(report, canary_kind="hermes_loop10")

            self.assertEqual(report["rows"][0]["movement_status"], "still_needs_precision_review")
            self.assertFalse(report["rows"][0]["evidence_flags"]["expected_title_preserved"])
            self.assertEqual(queue["rows"][0]["post_id"], 11703631)

    def test_expected_candidate_with_benign_prune_lint_closes_as_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "queue.json"
            after = root / "after.json"
            seed.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "post_id": 11718051,
                                "seed_bucket": "recall_relevance_representative",
                                "disagreement_type": "under_resolved_false_negative",
                                "expected_title": "몰락민족의 천재 기사",
                                "expected_url": "https://series.naver.com/novel/detail.series?productNo=13683859",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11718051,
                            "analysis_result": {
                                "identity": {
                                    "title_resolution_state": "unresolved_matchable",
                                    "candidate_audit_lint": ["llm_only_sentence_candidate_pruned"],
                                    "candidate_pruned_llm_only_surfaces": ["아무튼 재밌게 봄"],
                                    "title_candidates": [
                                        {
                                            "official_title": "몰락민족의 천재 기사",
                                            "heretic_url": "https://series.naver.com/novel/detail.series?productNo=13683859",
                                        }
                                    ],
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)
            queue = build_reimprovement_queue(report, canary_kind="hermes_loop10")

            self.assertEqual(report["rows"][0]["movement_status"], "candidate_preserved_with_benign_prune")
            self.assertTrue(report["rows"][0]["evidence_flags"]["prune_fired"])
            self.assertTrue(report["rows"][0]["evidence_flags"]["benign_prune"])
            self.assertEqual(queue["rows"], [])

    def test_expected_candidate_with_pruned_expected_surface_stays_reviewable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "queue.json"
            after = root / "after.json"
            seed.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "post_id": 11718051,
                                "seed_bucket": "recall_relevance_representative",
                                "disagreement_type": "under_resolved_false_negative",
                                "expected_title": "몰락민족의 천재 기사",
                                "expected_url": "https://series.naver.com/novel/detail.series?productNo=13683859",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11718051,
                            "analysis_result": {
                                "identity": {
                                    "title_resolution_state": "unresolved_matchable",
                                    "candidate_audit_lint": ["llm_only_sentence_candidate_pruned"],
                                    "candidate_pruned_llm_only_surfaces": ["몰락민족의 천재 기사 외전"],
                                    "title_candidates": [
                                        {
                                            "official_title": "몰락민족의 천재 기사",
                                            "heretic_url": "https://series.naver.com/novel/detail.series?productNo=13683859",
                                        }
                                    ],
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)
            queue = build_reimprovement_queue(report, canary_kind="hermes_loop10")

            self.assertEqual(report["rows"][0]["movement_status"], "candidate_preserved_with_prune_review")
            self.assertTrue(report["rows"][0]["evidence_flags"]["prune_fired"])
            self.assertFalse(report["rows"][0]["evidence_flags"]["benign_prune"])
            self.assertEqual(queue["rows"][0]["post_id"], 11718051)

    def test_expected_candidate_with_pruned_author_comment_wrapper_closes_as_benign(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "queue.json"
            after = root / "after.json"
            seed.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "post_id": 11703621,
                                "seed_bucket": "recall_relevance_representative",
                                "disagreement_type": "under_resolved",
                                "expected_title": "시체공양으로 데미갓",
                                "expected_url": "https://m.munpia.com/novel/detail/327873",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11703621,
                            "analysis_result": {
                                "identity": {
                                    "title_resolution_state": "author_new_work_context",
                                    "candidate_audit_lint": ["llm_only_sentence_candidate_pruned"],
                                    "candidate_pruned_llm_only_surfaces": [
                                        "시체공양으로 데미갓 작가 씨발아 돌아오라고"
                                    ],
                                    "title_candidates": [
                                        {
                                            "official_title": "시체공양으로 데미갓",
                                            "heretic_url": "https://m.munpia.com/novel/detail/327873",
                                        }
                                    ],
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)
            queue = build_reimprovement_queue(report, canary_kind="hermes_loop13")

            self.assertEqual(report["rows"][0]["movement_status"], "candidate_preserved_with_benign_prune")
            self.assertTrue(report["rows"][0]["evidence_flags"]["prune_fired"])
            self.assertTrue(report["rows"][0]["evidence_flags"]["benign_prune"])
            self.assertEqual(queue["rows"], [])

    def test_expected_url_evidence_strength_is_reported_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "queue.json"
            after = root / "after.json"
            seed.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "post_id": 11708478,
                                "seed_bucket": "candidate_comment_multi",
                                "disagreement_type": "comment_explicit_title_missed",
                                "expected_title": "사연 있는 악역으로 착각 당한다",
                                "expected_url": "https://novelpia.com/novel/396159",
                            },
                            {
                                "post_id": 11710025,
                                "seed_bucket": "recall_relevance_representative",
                                "disagreement_type": "under_resolved_false_negative",
                                "expected_title": "망할 놈의 아카데미",
                                "expected_url": "https://novelpia.com/novel/110488",
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11708478,
                            "analysis_result": {
                                "identity": {
                                    "title_resolution_state": "unresolved_matchable",
                                    "title_candidates": [
                                        {
                                            "official_title": "사연 있는 악역으로 착각 당한다",
                                            "heretic_url": "https://novelpia.com/novel/396159",
                                            "source_tier": "official_detail",
                                            "page_type": "novel_page",
                                            "content_status": "unavailable",
                                            "negative_evidence": ["url_deleted_or_unavailable"],
                                        }
                                    ],
                                }
                            },
                        },
                        {
                            "post_id": 11710025,
                            "analysis_result": {
                                "identity": {
                                    "title_resolution_state": "adjacent",
                                    "title_candidates": [
                                        {
                                            "official_title": "망할 놈의 아카데미",
                                            "heretic_url": "https://novelpia.com/novel/110488",
                                            "source_tier": "judge_seed_expected",
                                        }
                                    ],
                                }
                            },
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)
            by_id = {row["post_id"]: row for row in report["rows"]}

            self.assertEqual(
                by_id[11708478]["evidence_flags"]["expected_url_evidence_strength"],
                "unavailable_official_detail",
            )
            self.assertEqual(
                by_id[11710025]["evidence_flags"]["expected_url_evidence_strength"],
                "judge_seed_expected",
            )

    def test_source_url_hygiene_wrong_title_is_not_hidden_by_lint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "queue.json"
            after = root / "after.json"
            seed.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "post_id": 11698880,
                                "seed_bucket": "source_url_hygiene",
                                "expected_title": "아카데미 생존 갤러리",
                                "expected_url": "https://novelpia.com/novel/380218",
                                "before_title": "아카데미 생존 갤러리",
                                "before_url": "https://novelpia.com/novel/415486",
                                "movement_status": "url_lint_preserved",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11698880,
                            "analysis_result": {
                                "identity": {
                                    "novel_identity": {
                                        "official_title": "가챠 중독자의 퓨전펑크 생활",
                                        "heretic_url": "https://novelpia.com/novel/387014",
                                    },
                                    "title_resolution_state": "resolved",
                                    "output_consistency_lint": ["judge_hygiene_seed_title_correct_url_mismatch"],
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)
            queue = build_reimprovement_queue(report, canary_kind="loop5_postfix")

            self.assertEqual(report["rows"][0]["movement_status"], "title_or_url_still_mismatched")
            self.assertEqual(queue["rows"][0]["acceptance_status"], "still_bad")

    def test_source_url_hygiene_missing_expected_title_is_not_hidden_by_lint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "queue.json"
            after = root / "after.json"
            seed.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "post_id": 11702055,
                                "seed_bucket": "source_url_hygiene",
                                "expected_title": "괴담 호텔 탈출기",
                                "expected_url": "https://novelpia.com/novel/102155",
                                "before_title": None,
                                "before_url": None,
                                "movement_status": "url_lint_preserved",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11702055,
                            "analysis_result": {
                                "identity": {
                                    "novel_identity": {"official_title": None, "heretic_url": None},
                                    "title_resolution_state": "hold",
                                    "candidate_ledger": {"candidate_count": 0},
                                    "candidate_ledger_status": "hold_without_candidates",
                                    "output_consistency_lint": ["judge_hygiene_seed_heretic_url_null"],
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)
            queue = build_reimprovement_queue(report, canary_kind="loop5_postfix")

            self.assertEqual(report["rows"][0]["movement_status"], "title_or_url_still_mismatched")
            self.assertEqual(queue["rows"][0]["acceptance_status"], "still_bad")

    def test_source_url_hygiene_ocr_close_variant_keeps_url_lint_bucket(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "queue.json"
            after = root / "after.json"
            seed.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "post_id": 11716480,
                                "seed_bucket": "source_url_hygiene",
                                "expected_title": "여대학생 가랑이 사이 무릎 꿇은 엄마들",
                                "expected_url": None,
                                "before_title": "여대학생 가랑이 사이 무릎 꿇은 엄마들",
                                "before_url": None,
                                "movement_status": "url_lint_preserved",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11716480,
                            "analysis_result": {
                                "identity": {
                                    "novel_identity": {
                                        "official_title": "여대생 가랑이 사이 무릎 꿇은 엄마들",
                                        "heretic_url": None,
                                    },
                                    "title_resolution_state": "resolved",
                                    "output_consistency_lint": ["judge_hygiene_seed_heretic_url_null"],
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)
            queue = build_reimprovement_queue(report, canary_kind="loop5_postfix")

            self.assertEqual(report["rows"][0]["movement_status"], "url_lint_preserved")
            self.assertEqual(queue["rows"], [])

    def test_input_row_embedded_judge_seed_is_unwrapped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "input.jsonl"
            after = root / "after.json"
            write_jsonl(
                seed,
                [
                    {
                        "post_id": 11698880,
                        "title": "아생갤 개 존나게 재밌군 ㅇㅇ",
                        "_judge_seed": {
                            "post_id": 11698880,
                            "seed_bucket": "source_url_hygiene",
                            "disagreement_type": "reason_evidence_mismatch",
                            "independent_official_title": "아카데미 생존 갤러리",
                            "independent_url": "https://novelpia.com/novel/380218",
                            "pipeline_official_title": "아카데미 생존 갤러리",
                            "pipeline_url": "https://novelpia.com/novel/415486",
                            "source_identity": {
                                "official_title": "아카데미 생존 갤러리",
                                "heretic_url": "https://novelpia.com/novel/415486",
                            },
                        },
                    }
                ],
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11698880,
                            "analysis_result": {
                                "identity": {
                                    "novel_identity": {
                                        "official_title": None,
                                        "heretic_url": None,
                                    },
                                    "title_resolution_state": "unresolved_matchable",
                                    "output_consistency_lint": [
                                        "judge_hygiene_seed_expected_title_conflict_reason_evidence_mismatch"
                                    ],
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)

            self.assertEqual(report["rows"][0]["seed_bucket"], "source_url_hygiene")
            self.assertEqual(report["rows"][0]["expected_independent_title"], "아카데미 생존 갤러리")
            self.assertEqual(report["rows"][0]["movement_status"], "title_or_url_still_mismatched")

    def test_unresolved_matchable_without_candidates_stays_under_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "queue.json"
            after = root / "after.json"
            seed.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "post_id": 11697256,
                                "seed_bucket": "recall_relevance_representative",
                                "expected_title": "판초우의의 마법사",
                                "movement_status": "still_under_resolved_or_noise",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11697256,
                            "analysis_result": {
                                "identity": {
                                    "title_resolution_state": "unresolved_matchable",
                                    "candidate_ledger": {"candidate_count": 0},
                                    "candidate_ledger_status": "hold_without_candidates",
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)

            self.assertEqual(report["rows"][0]["movement_status"], "still_under_resolved_or_noise")
            self.assertTrue(report["rows"][0]["evidence_flags"]["hold_without_candidates"])

    def test_context_only_hold_without_candidates_stays_under_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "queue.json"
            after = root / "after.json"
            seed.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "post_id": 11697257,
                                "seed_bucket": "recall_relevance_representative",
                                "expected_title": "판초우의의 마법사",
                                "movement_status": "still_under_resolved_or_noise",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11697257,
                            "analysis_result": {
                                "identity": {
                                    "title_resolution_state": "context_only",
                                    "candidate_ledger": {"candidate_count": 0},
                                    "candidate_ledger_status": "hold_without_candidates",
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)

            self.assertEqual(report["rows"][0]["movement_status"], "still_under_resolved_or_noise")

    def test_wrong_relevance_boundary_hold_without_expected_title_closes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "queue.json"
            after = root / "after.json"
            seed.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "post_id": 11697229,
                                "seed_bucket": "recall_relevance_representative",
                                "disagreement_type": "wrong_relevance",
                                "expected_title": None,
                                "movement_status": "still_under_resolved_or_noise",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11697229,
                            "analysis_result": {
                                "identity": {
                                    "is_novel_related": True,
                                    "is_resolved_work_discussion": False,
                                    "title_resolution_state": "adjacent",
                                    "title_resolution_allowed": False,
                                    "candidate_ledger": {"candidate_count": 0},
                                    "candidate_ledger_status": "hold_without_candidates",
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)
            queue = build_reimprovement_queue(report, canary_kind="hermes_loop13")

            self.assertEqual(report["rows"][0]["movement_status"], "boundary_hold_preserved")
            self.assertEqual(queue["rows"], [])

    def test_trope_boundary_expected_title_resolution_requeues_as_overpromotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed.jsonl"
            after = root / "after.json"
            write_jsonl(
                seed,
                [
                    {
                        "post_id": 11710037,
                        "seed_bucket": "recall_relevance_representative",
                        "disagreement_type": "trope_or_author_talk_risk",
                        "recommended_action": "human_review",
                        "independent_official_title": "괴담 호텔 탈출기",
                        "independent_url": "https://novelpia.com/novel/102155",
                    }
                ],
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11710037,
                            "analysis_result": {
                                "identity": {
                                    "novel_identity": {
                                        "official_title": "괴담 호텔 탈출기",
                                        "heretic_url": "https://novelpia.com/novel/102155",
                                    },
                                    "title_resolution_state": "resolved",
                                    "candidate_ledger_status": "safe_resolved",
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)
            queue = build_reimprovement_queue(report, canary_kind="loop15_text")

            self.assertEqual(report["rows"][0]["movement_status"], "boundary_title_over_promoted")
            self.assertEqual(queue["rows"][0]["acceptance_status"], "still_bad")

    def test_recall_expected_title_with_wrong_url_stays_reimprovement_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed.jsonl"
            after = root / "after.json"
            write_jsonl(
                seed,
                [
                    {
                        "post_id": 11718077,
                        "seed_bucket": "recall_relevance_representative",
                        "disagreement_type": "under_resolved",
                        "independent_official_title": "즉사기 들고 무림에 떨어지다",
                        "independent_url": "https://series.naver.com/novel/detail.series?productNo=14041321",
                    }
                ],
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11718077,
                            "analysis_result": {
                                "identity": {
                                    "novel_identity": {
                                        "official_title": "즉사기 들고 무림에 떨어지다",
                                        "heretic_url": "https://novelpia.com/novel/380823",
                                    },
                                    "title_resolution_state": "resolved",
                                    "candidate_ledger_status": "safe_resolved",
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)
            queue = build_reimprovement_queue(report, canary_kind="loop16_url_guard")

            self.assertEqual(report["rows"][0]["movement_status"], "title_match_url_still_mismatched")
            self.assertEqual(queue["rows"][0]["acceptance_status"], "still_bad")
            self.assertEqual(
                queue["rows"][0]["expected_url"],
                "https://series.naver.com/novel/detail.series?productNo=14041321",
            )

    def test_expected_null_row_with_unexpected_resolved_title_requeues(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "queue.json"
            after = root / "after.json"
            seed.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "post_id": 11710045,
                                "seed_bucket": "recall_relevance_representative",
                                "disagreement_type": "under_resolved_false_negative",
                                "expected_title": None,
                                "expected_url": None,
                                "before_title": None,
                                "before_url": None,
                                "movement_status": "candidate_or_human_review_preserved",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            after.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11710045,
                            "analysis_result": {
                                "identity": {
                                    "novel_identity": {
                                        "official_title": "넣어 키운 걸그룹",
                                        "heretic_url": "https://ridibooks.com/books/3586035935",
                                    },
                                    "is_novel_related": True,
                                    "is_resolved_work_discussion": True,
                                    "title_resolution_state": "resolved",
                                    "title_resolution_allowed": True,
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = compare(seed, after, only_after_posts=True)
            queue = build_reimprovement_queue(report, canary_kind="loop14")

            self.assertEqual(report["rows"][0]["movement_status"], "unexpected_resolved_title")
            self.assertTrue(report["rows"][0]["evidence_flags"]["unexpected_resolved_title"])
            self.assertEqual(queue["rows"][0]["acceptance_status"], "still_bad")

    def test_write_queue_markdown_records_remaining_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.md"
            queue = {
                "canary_kind": "loop2",
                "semantic_quality": "REVIEW-LOCKED",
                "full_scan_approval": False,
                "rows": [
                    {
                        "post_id": 11702055,
                        "seed_bucket": "source_url_hygiene",
                        "disagreement_type": "title_url_mismatch",
                        "before_title": "즉사기 들고 무림에 떨어지다",
                        "before_url": "https://namu.wiki/w/example",
                        "after_title": "즉사기 들고 무림에 떨어지다",
                        "after_url": "https://namu.wiki/w/example",
                        "expected_title": "즉사기 들고 무림에 떨어지다",
                        "expected_url": "https://novelpia.com/novel/102155",
                        "movement_status": "title_or_url_still_mismatched",
                        "source_queue_observed_problem": "wiki/person URL should remain lint/HOLD.",
                    }
                ],
            }

            write_queue_markdown(path, queue)

            text = path.read_text(encoding="utf-8")
            self.assertIn("completed779 Reimprovement Loop 2 Remaining Queue", text)
            self.assertIn("11702055", text)
            self.assertIn("title_or_url_still_mismatched", text)


if __name__ == "__main__":
    unittest.main()
