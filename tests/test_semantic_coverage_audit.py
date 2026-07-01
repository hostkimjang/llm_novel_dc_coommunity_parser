from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


def load_audit_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "build_semantic_coverage_audit.py"
    spec = importlib.util.spec_from_file_location("build_semantic_coverage_audit", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SemanticCoverageAuditTest(unittest.TestCase):
    def test_list_result_rows_are_audited(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718082,
                    "image_count": 1,
                    "comments": ["표지에 제목 보임"],
                    "comment_metadata": [{"comment_id": "c1", "speaker": "user1"}],
                    "comment_dialogue_context_lines": ["#1 speaker=user1 text=표지에 제목 보임"],
                    "analysis_result": {
                        "identity": {
                            "context_sources": ["image"],
                            "image_evidence_catalog": [{"source": "vlm", "text": "제목"}],
                            "_final_semantic_reread": {"decision": "ACCEPT"},
                        }
                    },
                },
                {
                    "post_id": 11718080,
                    "comments": [],
                    "analysis_result": {"identity": {"reason": "작품 고유 앵커 없음"}},
                },
            ]
        )

        self.assertEqual(audit["coverage"]["total_rows"], 2)
        self.assertEqual(audit["coverage"]["image_post_count"], 1)
        self.assertEqual(audit["coverage"]["image_evidence_catalog_present"], 1)
        self.assertEqual(audit["coverage"]["comment_metadata_present"], 1)
        self.assertEqual(audit["coverage"]["browser_visual_available"], 0)
        self.assertEqual(audit["coverage"]["browser_visual_missing"], 1)

    def test_dict_result_rows_are_audited(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            {
                "results": [
                    {
                        "post_id": "11718091",
                        "comments": ["댓글"],
                        "comment_metadata": [{"comment_id": "c1"}],
                        "comment_dialogue_context_lines": ["#1 speaker=user1 text=댓글"],
                    }
                ]
            }
        )

        self.assertEqual(audit["coverage"]["total_rows"], 1)
        self.assertEqual(audit["rows_source"], "$.results")
        self.assertEqual(audit["coverage"]["comment_row_count"], 1)
        self.assertEqual(audit["coverage"]["comment_dialogue_context_present"], 1)

    def test_image_row_missing_image_evidence_catalog_creates_issue(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718082,
                    "image_urls": ["https://dcimg.example/cover.jpg"],
                    "analysis_result": {"identity": {"context_sources": ["image"]}},
                }
            ]
        )

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["gate"], "REVIEW-LOCKED")
        self.assertIn("image_evidence_catalog_missing", codes)
        self.assertIn("image_context_without_vlm_catalog", codes)
        self.assertIn("browser_visual_or_direct_evidence_missing", codes)

    def test_external_browser_artifact_manifest_can_satisfy_visual_gate(self):
        mod = load_audit_module()
        row = {
            "post_id": 11718082,
            "image_urls": ["https://dcimg.example/cover.jpg"],
            "analysis_result": {
                "identity": {
                    "context_sources": ["image"],
                    "image_evidence_catalog": [{"source": "vlm", "text": "제목"}],
                }
            },
        }
        without_external = mod.audit_data([row])
        self.assertEqual(without_external["coverage"]["browser_visual_missing"], 1)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            screenshot = root / "shot.png"
            screenshot.write_bytes(b"fake")
            manifest = root / "browser_manifest.json"
            manifest.write_text(
                """
                {
                  "rows": [
                    {
                      "post_id": 11718082,
                      "screenshot": "shot.png",
                      "visible_signals": ["article_image_loaded"],
                      "article_image_count": 1,
                      "article_loaded_count": 1,
                      "article_incomplete_count": 0,
                      "article_broken_count": 0,
                      "article_lazy_pending_count": 0,
                      "placeholder_current_src_count": 0
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )
            browser_artifacts = mod.load_browser_artifacts(manifest)
            audit = mod.audit_data(
                [row],
                browser_artifacts=browser_artifacts,
                browser_artifact_manifest=manifest,
            )

        self.assertEqual(audit["coverage"]["browser_visual_available"], 1)
        self.assertEqual(audit["coverage"]["browser_visual_missing"], 0)
        self.assertEqual(audit["coverage"]["browser_visual_external_artifact_available"], 1)

    def test_fallback_browser_attempt_manifest_can_satisfy_visual_gate(self):
        mod = load_audit_module()
        row = {
            "post_id": 11718049,
            "image_urls": ["https://dcimg.example/reaction.jpg"],
            "analysis_result": {
                "identity": {
                    "context_sources": ["image"],
                    "image_evidence_catalog": [
                        {"source": "vlm", "source_url": "https://dcimg.example/reaction.jpg", "text": "본문 이미지"}
                    ],
                    "image_fetch_success": 1,
                    "vlm_chunks_sent": 1,
                }
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            screenshot = root / "shot.png"
            screenshot.write_bytes(b"fake")
            manifest = root / "attempt_manifest.json"
            manifest.write_text(
                """
                {
                  "fallback_browser": {
                    "used": true,
                    "post_id": 11718049,
                    "screenshot_path": "shot.png",
                    "evidence_grade": "Medium",
                    "visible_observation": "본문 이미지 표시",
                    "article_image_count": 1,
                    "article_loaded_count": 1,
                    "article_incomplete_count": 0,
                    "article_broken_count": 0,
                    "article_lazy_pending_count": 0,
                    "placeholder_current_src_count": 0
                  }
                }
                """,
                encoding="utf-8",
            )
            audit = mod.audit_data(
                [row],
                browser_artifacts=mod.load_browser_artifacts(manifest),
                browser_artifact_manifest=manifest,
            )

        self.assertEqual(audit["coverage"]["browser_visual_available"], 1)
        self.assertEqual(audit["coverage"]["browser_visual_missing"], 0)
        self.assertEqual(audit["coverage"]["browser_visual_external_artifact_available"], 1)

    def test_external_browser_artifact_grade_without_loading_counters_does_not_satisfy_visual_gate(self):
        mod = load_audit_module()
        row = {
            "post_id": 11718068,
            "image_urls": ["https://dcimg.example/screenshot.jpg"],
            "analysis_result": {
                "identity": {
                    "context_sources": ["image"],
                    "image_evidence_catalog": [{"source": "vlm", "text": "image text"}],
                }
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            screenshot = root / "medium-but-no-counters.png"
            screenshot.write_bytes(b"fake")
            manifest = root / "browser_manifest.json"
            manifest.write_text(
                """
                {
                  "rows": [
                    {
                      "post_id": 11718068,
                      "screenshot": "medium-but-no-counters.png",
                      "visual_evidence_grade": "Medium"
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )
            browser_artifacts = mod.load_browser_artifacts(manifest)
            audit = mod.audit_data(
                [row],
                browser_artifacts=browser_artifacts,
                browser_artifact_manifest=manifest,
            )

        self.assertEqual(browser_artifacts, {})
        self.assertEqual(audit["coverage"]["browser_visual_available"], 0)
        self.assertEqual(audit["coverage"]["browser_visual_missing"], 1)
        self.assertEqual(audit["coverage"]["browser_visual_external_artifact_available"], 0)

    def test_external_browser_artifact_weak_grade_does_not_satisfy_visual_gate(self):
        mod = load_audit_module()
        row = {
            "post_id": 11718049,
            "image_urls": ["https://dcimg.example/reaction.jpg"],
            "analysis_result": {
                "identity": {
                    "context_sources": ["image"],
                    "image_evidence_catalog": [{"source": "vlm", "text": "character visual only"}],
                }
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            screenshot = root / "weak.png"
            screenshot.write_bytes(b"fake")
            reviews = root / "reviews.jsonl"
            reviews.write_text(
                (
                    '{"post_id":11718049,'
                    '"screenshot_path":"weak.png",'
                    '"visual_evidence_grade":"Weak",'
                    '"article_image_count":0,'
                    '"article_loaded_count":0}\n'
                ),
                encoding="utf-8",
            )
            manifest = root / "browser_manifest.json"
            manifest.write_text(
                '{"output_path":"reviews.jsonl"}\n',
                encoding="utf-8",
            )
            browser_artifacts = mod.load_browser_artifacts(manifest)
            audit = mod.audit_data(
                [row],
                browser_artifacts=browser_artifacts,
                browser_artifact_manifest=manifest,
            )

        self.assertEqual(browser_artifacts, {})
        self.assertEqual(audit["coverage"]["browser_visual_available"], 0)
        self.assertEqual(audit["coverage"]["browser_visual_missing"], 1)
        self.assertEqual(audit["coverage"]["browser_visual_external_artifact_available"], 0)

    def test_external_browser_artifact_strong_grade_with_failed_loading_does_not_satisfy_visual_gate(self):
        mod = load_audit_module()
        row = {
            "post_id": 11718082,
            "image_urls": ["https://dcimg.example/screenshot.jpg"],
            "analysis_result": {
                "identity": {
                    "context_sources": ["image"],
                    "image_evidence_catalog": [{"source": "vlm", "text": "image text"}],
                }
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            screenshot = root / "strong-but-not-loaded.png"
            screenshot.write_bytes(b"fake")
            manifest = root / "browser_manifest.json"
            manifest.write_text(
                """
                {
                  "rows": [
                    {
                      "post_id": 11718082,
                      "screenshot": "strong-but-not-loaded.png",
                      "visual_evidence_grade": "Strong",
                      "article_image_count": 2,
                      "article_loaded_count": 1
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )
            browser_artifacts = mod.load_browser_artifacts(manifest)
            audit = mod.audit_data(
                [row],
                browser_artifacts=browser_artifacts,
                browser_artifact_manifest=manifest,
            )

        self.assertEqual(browser_artifacts, {})
        self.assertEqual(audit["coverage"]["browser_visual_available"], 0)
        self.assertEqual(audit["coverage"]["browser_visual_missing"], 1)
        self.assertEqual(audit["coverage"]["browser_visual_external_artifact_available"], 0)

    def test_image_context_with_vlm_chunk_counter_is_not_context_without_catalog(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718082,
                    "analysis_result": {
                        "identity": {
                            "context_sources": ["image"],
                            "browser_visual_verified": True,
                        }
                    },
                },
                {
                    "post_id": 11718083,
                    "analysis_result": {
                        "identity": {
                            "anchor_type": "image",
                            "browser_visual_verified": True,
                        }
                    },
                },
                {
                    "post_id": 11718084,
                    "analysis_result": {
                        "identity": {
                            "context_sources": ["image"],
                            "image_fetch_success": 1,
                            "vlm_chunks_sent": 1,
                            "vlm_chunk_count": 1,
                            "browser_visual_verified": True,
                        }
                    },
                },
            ]
        )

        codes = {item["code"] for item in audit["issues"]}
        issue = next(item for item in audit["issues"] if item["code"] == "image_context_without_vlm_catalog")
        self.assertEqual(audit["coverage"]["image_context_without_vlm_catalog"], 2)
        self.assertEqual(issue["sample_post_ids"], ["11718082", "11718083"])
        self.assertIn("image_context_without_vlm_catalog", codes)
        self.assertIn("image_evidence_catalog_missing", codes)

    def test_failed_vlm_status_strings_do_not_count_as_chunk_evidence(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718085,
                    "analysis_result": {
                        "identity": {
                            "context_sources": ["image"],
                            "vlm_chunk_count": "failed",
                            "image_fetch_success": "timeout",
                            "vlm": {"status": "pending"},
                            "browser_visual_verified": True,
                        }
                    },
                }
            ]
        )

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["coverage"]["image_context_without_vlm_catalog"], 1)
        self.assertIn("image_context_without_vlm_catalog", codes)

    def test_image_catalog_without_vlm_fetch_chunk_counter_creates_issue(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718082,
                    "image_urls": ["https://dcimg.example/cover.jpg"],
                    "analysis_result": {
                        "identity": {
                            "context_sources": ["image"],
                            "image_evidence_catalog": [
                                {
                                    "source": "vlm",
                                    "source_url": "https://dcimg.example/cover.jpg",
                                    "ocr_text": "재벌가 차녀의 2회차 걸그룹",
                                }
                            ],
                            "browser_visual_verified": True,
                        }
                    },
                }
            ]
        )

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["gate"], "REVIEW-LOCKED")
        self.assertEqual(audit["coverage"]["image_catalog_present_but_vlm_counter_missing"], 1)
        self.assertIn("image_catalog_present_but_vlm_counter_missing", codes)

    def test_image_catalog_with_vlm_fetch_chunk_counter_is_reviewable(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718082,
                    "image_urls": ["https://dcimg.example/cover.jpg"],
                    "analysis_result": {
                        "identity": {
                            "context_sources": ["image"],
                            "image_evidence_catalog": [
                                {
                                    "source": "vlm",
                                    "source_url": "https://dcimg.example/cover.jpg",
                                    "ocr_text": "재벌가 차녀의 2회차 걸그룹",
                                }
                            ],
                            "image_fetch_count": 1,
                            "image_fetch_success": 1,
                            "vlm_chunks_sent": 1,
                            "vlm_total_bytes": 77821,
                            "browser_visual_verified": True,
                        }
                    },
                }
            ]
        )

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["gate"], "GO")
        self.assertEqual(audit["coverage"]["image_catalog_present_but_vlm_counter_missing"], 0)
        self.assertNotIn("image_catalog_present_but_vlm_counter_missing", codes)

    def test_image_ocr_reason_without_public_vlm_counter_creates_issue(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718082,
                    "image_urls": ["https://dcimg.example/cover.jpg"],
                    "analysis_result": {
                        "identity": {
                            "context_sources": ["image"],
                            "reason": "[이미지 OCR] 표지가 재벌가 차녀의 2회차 걸그룹을 직접 표기함",
                            "image_evidence_catalog": [
                                {
                                    "source": "ocr",
                                    "source_url": "https://dcimg.example/cover.jpg",
                                    "ocr_text": "재벌가 차녀의 2회차 걸그룹",
                                }
                            ],
                            "browser_visual_verified": True,
                        }
                    },
                }
            ]
        )

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["gate"], "REVIEW-LOCKED")
        self.assertEqual(audit["coverage"]["image_ocr_reason_without_public_vlm_counter"], 1)
        self.assertIn("image_ocr_reason_without_public_vlm_counter", codes)

    def test_image_evidence_catalog_without_source_or_snippet_creates_unreviewable_issue(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718082,
                    "image_urls": ["https://dcimg.example/cover.jpg"],
                    "analysis_result": {
                        "identity": {
                            "context_sources": ["image"],
                            "image_evidence_catalog": [{"text": "재벌가 차녀의 2회차 걸그룹"}],
                            "image_fetch_success": 1,
                            "vlm_chunks_sent": 1,
                            "browser_visual_verified": True,
                        }
                    },
                }
            ]
        )

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["gate"], "REVIEW")
        self.assertEqual(audit["coverage"]["image_evidence_catalog_unreviewable"], 1)
        self.assertIn("image_evidence_catalog_unreviewable", codes)

    def test_semantic_seed_review_without_final_reread_creates_issue(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718091,
                    "is_relevant": True,
                    "analysis_result": {
                        "identity": {
                            "official_title": "검색으로 되살아난 후보",
                            "title_resolution_state": "resolved",
                            "work_resolution": "resolved",
                            "reason": "semantic_seed_review가 작품 seed를 자연어 문맥으로 낮췄지만 검색 후보가 다시 확정됨",
                            "consistency_flags": ["semantic_seed_review_specific_work_denied"],
                        }
                    },
                }
            ]
        )

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["coverage"]["final_semantic_reread_required"], 1)
        self.assertEqual(audit["coverage"]["final_semantic_reread_required_missing"], 1)
        self.assertEqual(
            audit["coverage"]["semantic_seed_review_present_final_semantic_reread_missing"],
            1,
        )
        self.assertIn("semantic_seed_review_without_final_semantic_reread", codes)
        self.assertIn("final_semantic_reread_coverage_missing", codes)

    def test_non_resolved_semantic_seed_review_does_not_require_final_reread(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718085,
                    "is_relevant": False,
                    "analysis_result": {
                        "identity": {
                            "title_resolution_state": "context_only",
                            "work_resolution": "none",
                            "reason": "semantic_seed_review가 작품 seed를 자연어 문맥으로 낮춤",
                            "consistency_flags": ["semantic_seed_review_specific_work_denied"],
                        }
                    },
                }
            ]
        )

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["coverage"]["semantic_seed_review_present"], 1)
        self.assertEqual(audit["coverage"]["final_semantic_reread_required"], 0)
        self.assertEqual(
            audit["coverage"]["semantic_seed_review_present_final_semantic_reread_missing"],
            0,
        )
        self.assertNotIn("semantic_seed_review_without_final_semantic_reread", codes)
        self.assertNotIn("final_semantic_reread_coverage_missing", codes)

    def test_comment_context_resolution_without_attribution_creates_issue(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718089,
                    "is_relevant": True,
                    "comments": ["작품 단서처럼 보이는 댓글"],
                    "analysis_result": {
                        "identity": {
                            "official_title": "댓글로 되살아난 후보",
                            "title_resolution_state": "resolved",
                            "context_sources": ["comments", "search"],
                        }
                    },
                }
            ]
        )

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["coverage"]["comment_context_resolution_row_count"], 1)
        self.assertEqual(audit["coverage"]["comment_context_resolution_without_attribution"], 1)
        self.assertIn("comment_context_resolution_without_attribution", codes)

    def test_comment_author_match_unverified_resolution_creates_issue(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718090,
                    "is_relevant": True,
                    "comments": ["원글 작성자처럼 보이지만 IP 미확인"],
                    "comment_metadata": [
                        {
                            "comment_id": "c1",
                            "speaker": "user1",
                            "post_author_match_unverified": True,
                        }
                    ],
                    "comment_dialogue_context_lines": [
                        "#1 speaker=user1 role=author_match_unverified text=원글 작성자처럼 보이지만 IP 미확인"
                    ],
                    "analysis_result": {
                        "identity": {
                            "official_title": "댓글 발화로 되살아난 후보",
                            "title_resolution_state": "resolved",
                            "context_sources": ["comments"],
                        }
                    },
                }
            ]
        )

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["coverage"]["comment_author_match_unverified_signal"], 1)
        self.assertEqual(audit["coverage"]["comment_author_match_unverified_used_for_resolution"], 1)
        self.assertIn("comment_author_match_unverified_used_for_resolution", codes)

    def test_comment_author_match_unverified_with_title_alias_support_is_review_only(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718097,
                    "is_relevant": True,
                    "comments": ["동일 닉네임 댓글"],
                    "comment_metadata": [
                        {
                            "comment_id": "c1",
                            "speaker": "user1",
                            "post_author_match_unverified": True,
                        }
                    ],
                    "comment_dialogue_context_lines": [
                        "#1 speaker=user1 role=author_match_unverified text=동일 닉네임 댓글"
                    ],
                    "analysis_result": {
                        "identity": {
                            "official_title": "직접 별칭으로 지지되는 후보",
                            "title_resolution_state": "resolved",
                            "context_sources": ["title", "comments", "search"],
                            "anchor_type": "title_exact",
                            "reason": (
                                "title_in_post: true; "
                                "title_lead_alias_search_work_support; "
                                "evidence_type: search_platform_url"
                            ),
                        }
                    },
                }
            ]
        )

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["coverage"]["comment_author_match_unverified_signal"], 1)
        self.assertEqual(audit["coverage"]["comment_author_match_unverified_used_for_resolution"], 0)
        self.assertEqual(audit["coverage"]["comment_author_match_unverified_resolution_review_only"], 1)
        self.assertNotIn("comment_author_match_unverified_used_for_resolution", codes)
        self.assertIn("comment_author_match_unverified_resolution_review_only", codes)

    def test_comment_context_with_attribution_does_not_create_missing_attribution_issue(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718092,
                    "is_relevant": True,
                    "comments": ["제목 직접 언급"],
                    "comment_metadata": [{"comment_id": "c1", "speaker": "user1", "author": "ㅇㅇ"}],
                    "comment_dialogue_context_lines": ["#1 speaker=user1 author=ㅇㅇ text=제목 직접 언급"],
                    "analysis_result": {
                        "identity": {
                            "official_title": "댓글 제목 직접 언급",
                            "title_resolution_state": "resolved",
                            "context_sources": ["comments"],
                        }
                    },
                }
            ]
        )

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["coverage"]["comment_context_resolution_row_count"], 1)
        self.assertEqual(audit["coverage"]["comment_context_resolution_without_attribution"], 0)
        self.assertNotIn("comment_context_resolution_without_attribution", codes)

    def test_search_only_resolved_title_creates_issue(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718080,
                    "analysis_result": {
                        "identity": {
                            "official_title": "검색만으로 되살아난 후보",
                            "title_resolution_state": "resolved",
                            "grounding_anchor": "search_only",
                        }
                    },
                }
            ]
        )

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["coverage"]["search_only_resolved_title"], 1)
        self.assertEqual(audit["coverage"]["search_only_resolved_title_review_only"], 0)
        self.assertIn("search_only_resolved_title", codes)

    def test_search_only_with_title_alias_and_platform_support_is_review_only(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718075,
                    "analysis_result": {
                        "identity": {
                            "official_title": "직접 별칭으로 지지되는 후보",
                            "title_resolution_state": "resolved",
                            "anchor_type": "title_exact",
                            "reason": (
                                "grounding_anchor: search_only; "
                                "title_in_post: true; "
                                "official_title_evidence: true; "
                                "heretic_url_platform"
                            ),
                        }
                    },
                }
            ]
        )

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["coverage"]["search_only_resolved_title"], 0)
        self.assertEqual(audit["coverage"]["search_only_resolved_title_review_only"], 1)
        self.assertNotIn("search_only_resolved_title", codes)
        self.assertIn("search_only_resolved_title_review_only", codes)

    def test_blocked_intent_resolved_title_creates_issue(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718118,
                    "analysis_result": {
                        "identity": {
                            "official_title": "장르/트로프에서 되살아난 후보",
                            "title_resolution_state": "resolved",
                            "discussion_type": "trope_discussion",
                        }
                    },
                }
            ]
        )

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["coverage"]["blocked_intent_resolved_title"], 1)
        self.assertEqual(audit["coverage"]["blocked_intent_resolved_title_review_only"], 0)
        self.assertIn("blocked_intent_resolved_title", codes)

    def test_intent_denied_context_only_with_title_present_creates_issue(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718080,
                    "analysis_result": {
                        "identity": {
                            "official_title": "되살아나면 안 되는 후보",
                            "title_resolution_allowed": False,
                            "title_resolution_state": "context_only",
                            "discussion_type": "trope_discussion",
                            "consistency_flags": [
                                "semantic_seed_review_specific_work_denied",
                                "context_only_no_work_anchor",
                            ],
                            "uncertainty_sources": [
                                "intent_permit_for_title_search=false(semantic_seed_review_not_specific_work)"
                            ],
                        }
                    },
                }
            ]
        )

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["coverage"]["intent_denied_title_present"], 1)
        self.assertIn("intent_denied_title_present", codes)
        self.assertEqual(audit["gate"], "REVIEW-LOCKED")

    def test_intent_denied_without_title_is_not_title_present_issue(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718080,
                    "analysis_result": {
                        "identity": {
                            "official_title": "",
                            "title_resolution_allowed": False,
                            "title_resolution_state": "context_only",
                            "consistency_flags": ["semantic_seed_review_specific_work_denied"],
                        }
                    },
                }
            ]
        )

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["coverage"]["intent_denied_title_present"], 0)
        self.assertNotIn("intent_denied_title_present", codes)

    def test_adjacent_reason_with_non_relevant_post_note_is_review_issue(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718080,
                    "analysis_result": {
                        "identity": {
                            "is_relevant": False,
                            "topicality": "adjacent_relevant",
                            "title_resolution_state": "adjacent",
                            "discussion_type": "trope_discussion",
                            "reason": (
                                "[판정 요약] - 판정: 주변 관련 - discussion_type: trope_discussion "
                                "- 핵심 결론: 특정 작품보다 장르/트로프 일반론입니다. "
                                "[정합성 교정] - 최종 분류는 adjacent_relevant이며 단일 공식 제목은 미확정입니다. "
                                "- 최종 판정은 비관련 포스트(discussion_type=trope_discussion)이며 원문 reason의 작품 확정 결론을 완화함."
                            ),
                        }
                    },
                }
            ]
        )

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["gate"], "REVIEW")
        self.assertEqual(audit["coverage"]["adjacent_reason_non_relevant_wording_conflict"], 1)
        self.assertIn("adjacent_reason_non_relevant_wording_conflict", codes)

    def test_specific_work_hold_with_direct_anchor_is_review_only(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718120,
                    "analysis_result": {
                        "identity": {
                            "official_title": "직접 별칭으로 지지되는 후보",
                            "title_resolution_state": "resolved",
                            "discussion_type": "community_banter",
                            "grounding_anchor": "search_only",
                            "body_alias_anchor": True,
                            "relation_judgment": {
                                "discussion_target": "specific_work",
                                "promotion_decision": "hold",
                            },
                        }
                    },
                }
            ]
        )

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["coverage"]["search_only_resolved_title"], 0)
        self.assertEqual(audit["coverage"]["blocked_intent_resolved_title"], 0)
        self.assertEqual(audit["coverage"]["search_only_resolved_title_review_only"], 1)
        self.assertEqual(audit["coverage"]["blocked_intent_resolved_title_review_only"], 1)
        self.assertNotIn("search_only_resolved_title", codes)
        self.assertNotIn("blocked_intent_resolved_title", codes)
        self.assertIn("search_only_resolved_title_review_only", codes)
        self.assertIn("blocked_intent_resolved_title_review_only", codes)
        self.assertEqual(audit["gate"], "REVIEW")

    def test_browser_loading_counters_count_as_visual_available(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718082,
                    "article_image_count": 1,
                    "article_loaded_count": 1,
                    "placeholder_count": 0,
                    "incomplete_count": 0,
                    "broken_count": 0,
                    "analysis_result": {
                        "identity": {
                            "context_sources": ["image"],
                            "image_evidence_catalog": [{"source": "vlm", "text": "제목"}],
                            "_final_semantic_reread": {"decision": "ACCEPT"},
                        }
                    },
                }
            ]
        )

        self.assertEqual(audit["coverage"]["browser_visual_required"], 1)
        self.assertEqual(audit["coverage"]["browser_visual_available"], 1)
        self.assertNotIn(
            "browser_visual_or_direct_evidence_missing",
            {item["code"] for item in audit["issues"]},
        )

    def test_browser_loading_counters_without_visual_artifact_creates_review_issue(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718082,
                    "article_image_count": 1,
                    "article_loaded_count": 1,
                    "placeholder_count": 0,
                    "incomplete_count": 0,
                    "broken_count": 0,
                    "analysis_result": {
                        "identity": {
                            "context_sources": ["image"],
                            "image_evidence_catalog": [
                                {
                                    "source": "vlm",
                                    "source_url": "https://dcimg.example/cover.jpg",
                                    "ocr_text": "재벌가 차녀의 2회차 걸그룹",
                                }
                            ],
                            "image_fetch_success": 1,
                            "vlm_chunks_sent": 1,
                        }
                    },
                }
            ]
        )

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["coverage"]["browser_visual_available"], 1)
        self.assertEqual(audit["coverage"]["browser_loading_ok_but_visual_artifact_missing"], 1)
        self.assertIn("browser_loading_ok_but_visual_artifact_missing", codes)
        self.assertEqual(audit["gate"], "REVIEW")

    def test_browser_screenshot_path_alone_is_not_visual_available(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718082,
                    "image_count": 1,
                    "browser_screenshot_path": "screenshots/11718082.png",
                    "analysis_result": {
                        "identity": {
                            "context_sources": ["image"],
                            "image_evidence_catalog": [{"source": "vlm", "text": "제목"}],
                        }
                    },
                }
            ]
        )

        self.assertEqual(audit["coverage"]["browser_visual_required"], 1)
        self.assertEqual(audit["coverage"]["browser_visual_available"], 0)
        self.assertEqual(audit["coverage"]["browser_visual_missing"], 1)
        self.assertIn(
            "browser_visual_or_direct_evidence_missing",
            {item["code"] for item in audit["issues"]},
        )

    def test_browser_loading_pending_overrides_visual_verified(self):
        mod = load_audit_module()
        audit = mod.audit_data(
            [
                {
                    "post_id": 11718082,
                    "article_image_count": 2,
                    "article_loaded_count": 1,
                    "article_lazy_pending_count": 1,
                    "placeholder_current_src_count": 1,
                    "browser_visual_verified": True,
                    "analysis_result": {
                        "identity": {
                            "official_title": "재벌가 차녀의 2회차 걸그룹",
                            "context_sources": ["image"],
                            "image_evidence_catalog": [{"source": "vlm", "ocr_text": "재벌가 차녀의 2회차 걸그룹"}],
                        }
                    },
                }
            ]
        )

        self.assertEqual(audit["coverage"]["browser_visual_required"], 1)
        self.assertEqual(audit["coverage"]["browser_visual_available"], 0)
        self.assertEqual(audit["coverage"]["browser_visual_missing"], 1)
        self.assertEqual(audit["coverage"]["browser_loading_failed_or_pending_text_match_used"], 1)
        self.assertIn(
            "image_loading_failed_or_pending_text_match_used",
            {item["code"] for item in audit["issues"]},
        )

    def test_markdown_contains_korean_headings(self):
        mod = load_audit_module()
        audit = mod.audit_data([{"post_id": 1, "comments": []}])
        markdown = mod.build_markdown(audit)

        self.assertIn("## 요약", markdown)
        self.assertIn("## 커버리지", markdown)
        self.assertIn("## 판정 메모", markdown)
        self.assertIn("10만 건 semantic approval이 아니며", markdown)


if __name__ == "__main__":
    unittest.main()
