from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def load_round2_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "build_qualitative_round2_review.py"
    spec = importlib.util.spec_from_file_location("build_qualitative_round2_review", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_round3_after_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "build_qualitative_round3_after_review.py"
    spec = importlib.util.spec_from_file_location("build_qualitative_round3_after_review", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_current_remaining_action_inputs_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "build_current_remaining_action_inputs.py"
    spec = importlib.util.spec_from_file_location("build_current_remaining_action_inputs", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_v78_vlm_relabel_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "build_v78_vlm_browser_semantic_relabel.py"
    spec = importlib.util.spec_from_file_location("build_v78_vlm_browser_semantic_relabel", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_capture_vlm_browser_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "capture_vlm_ocr_browser_review_cli.py"
    spec = importlib.util.spec_from_file_location("capture_vlm_ocr_browser_review_cli", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_slang_status_review_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "build_slang_db_status_review.py"
    spec = importlib.util.spec_from_file_location("build_slang_db_status_review", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_large_scale_preflight_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "preflight_qualitative_large_scale_review.py"
    spec = importlib.util.spec_from_file_location("preflight_qualitative_large_scale_review", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_reason_hygiene_scan_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "scan_reason_hygiene.py"
    spec = importlib.util.spec_from_file_location("scan_reason_hygiene", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_llm_judgment_review_packet_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "build_llm_judgment_review_packet.py"
    spec = importlib.util.spec_from_file_location("build_llm_judgment_review_packet", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QualitativeReviewPacketToolsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.round2 = load_round2_module()
        cls.round3_after = load_round3_after_module()
        cls.current_remaining = load_current_remaining_action_inputs_module()
        cls.v78_vlm_relabel = load_v78_vlm_relabel_module()
        cls.capture_vlm_browser = load_capture_vlm_browser_module()
        cls.slang_status_review = load_slang_status_review_module()
        cls.large_scale_preflight = load_large_scale_preflight_module()
        cls.reason_hygiene_scan = load_reason_hygiene_scan_module()
        cls.llm_judgment_packet = load_llm_judgment_review_packet_module()

    def test_final_decision_fields_preserves_alias_resolution_sources(self) -> None:
        alias_sources = [
            {
                "alias": "담텔기",
                "canonical_title": "괴담 호텔 탈출기",
                "alias_resolution_source": "known_title_abbreviation",
                "source_registry": "KNOWN_TITLE_ABBREVIATIONS",
                "matched_surface_kind": "post_title",
            }
        ]

        fields = self.round2.final_decision_fields(
            {
                "novel_identity": {
                    "official_title": "괴담 호텔 탈출기",
                    "confidence": "High",
                    "alias_resolution_sources": alias_sources,
                }
            }
        )

        self.assertEqual(fields["alias_resolution_sources"], alias_sources)

    def test_registry_anchor_only_alias_resolution_labels_hold_for_weak_resolved(self) -> None:
        row = {
            "post_id": 11718120,
            "title": "담텔기 작가의 말 스포",
            "content": ["305호 끝나면 휴재 얘기"],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "괴담 호텔 탈출기",
                        "confidence": "Medium",
                        "alias_resolution_sources": [
                            {
                                "alias": "담텔기",
                                "canonical_title": "괴담 호텔 탈출기",
                                "source_registry": "KNOWN_TITLE_ABBREVIATIONS",
                                "promotion_evidence_tier": "registry_anchor_only",
                                "promotion_confidence": "Medium",
                                "confidence_demoted_without_hard_evidence": True,
                            }
                        ],
                    },
                    "work_resolution": "resolved",
                    "reason": (
                        "[근거 요약]\n"
                        "- official_title_evidence: false\n"
                        "- evidence_bucket: post_spans=0, search_snippets=0, official_urls=0\n"
                        "- alias_promotion_evidence_tier: registry_anchor_only\n"
                    ),
                }
            },
            "run_meta": {"run_id": "run-alias"},
        }

        facts = self.round2.extract_facts(1, row)
        packet = self.round2.build_packet("R2-ALIAS", "weak_evidence_but_strong_resolution", facts, Path("result.json"))
        label = self.round2.review_label(packet, facts)

        self.assertTrue(facts["registry_anchor_only_alias_resolution"])
        self.assertEqual(label["label"], "HOLD")
        self.assertEqual(label["action"], "re_judge")
        self.assertIn("registry_anchor_only_alias_resolution", label["boundary_risk"])

    def test_llm_judgment_packet_preserves_alias_resolution_sources(self) -> None:
        alias_sources = [
            {
                "alias": "담텔기",
                "canonical_title": "괴담 호텔 탈출기",
                "promotion_evidence_tier": "registry_anchor_only",
            }
        ]
        row = {
            "status": "completed",
            "result": {
                "post_id": 1,
                "title": "담텔기 후기",
                "analysis_result": {
                    "identity": {
                        "is_relevant": True,
                        "novel_identity": {
                            "official_title": "괴담 호텔 탈출기",
                            "confidence": "Medium",
                            "alias_resolution_sources": alias_sources,
                        },
                    }
                },
            },
        }

        item = self.llm_judgment_packet._review_item(row, audit={}, slang_db={})

        self.assertEqual(item["model_judgment"]["alias_resolution_sources"], alias_sources)

    def test_reason_hygiene_raw_scan_separates_historical_repro_and_clean_canary(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            dirty = root / "v371_dirty_result.json"
            clean = root / "v372_clean_result.json"
            manifest = root / "v372_clean_result_manifest.json"
            tool_report = root / "v374_scan_tool_report.json"
            unversioned = root / "action_queue.json"
            dirty.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 1,
                            "analysis_result": {
                                "identity": {
                                    "reason": (
                                        "\uc7a5\ub974 \uac10\uc0c1\\n"
                                        "- \uc791\ud488 seed \uc81c\uc678: \uc7a5\ub974\ud45c\uba74"
                                    )
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            clean.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 2,
                            "analysis_result": {
                                "identity": {
                                    "reason": (
                                        "\ud45c\ud604 \uc624\ud0c0/\ucd95\uc57d "
                                        "\ud328\ud134(\ubc94\uc6a9 \uc7ac\ud574\ub3c5 \ud6c4\ubcf4)"
                                    )
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            manifest.write_text('{"ignored": true}', encoding="utf-8")
            tool_report.write_text(
                json.dumps({"patterns": ["\uc791\ud488 seed \uc81c\uc678"]}, ensure_ascii=False),
                encoding="utf-8",
            )
            unversioned.write_text(
                json.dumps({"reason": "\uc791\ud488 seed \uc81c\uc678: ignored"}, ensure_ascii=False),
                encoding="utf-8",
            )

            report = self.reason_hygiene_scan.build_scan_report([root], min_version=360)

        self.assertEqual(report["files_scanned"], 2)
        self.assertEqual(report["hit_files"], 1)
        self.assertEqual(report["hit_type_counts"], {"seed_excluded": 1})
        dirty_result = next(item for item in report["results"] if item["name"] == "v371_dirty_result.json")
        clean_result = next(item for item in report["results"] if item["name"] == "v372_clean_result.json")
        self.assertEqual(dirty_result["hits"], ["seed_excluded"])
        self.assertEqual(clean_result["hits"], [])

    def test_reason_hygiene_scan_flags_reread_wording_drift(self) -> None:
        legacy_reread_label = "\ubc94\uc6a9 \uc7ac\ud574\ub3c5 \ud6c4\ubcf4"
        legacy_possibility_label = "\ud45c\ud604 \uc624\ud0c0/\ucd95\uc57d \uac00\ub2a5\uc131"
        legacy_spacing_label = "\ud45c\ud604 \uc624\ud0c0/\ucd95\uc57d/\ub744\uc5b4\uc4f0\uae30 \uac00\ub2a5\uc131"
        result = self.reason_hygiene_scan.scan_text(
            f"reason: {legacy_possibility_label}은 {legacy_reread_label}이며 "
            f"{legacy_spacing_label}({legacy_reread_label})을 공개함."
        )

        self.assertIn("reread_wording_drift", result["hits"])
        self.assertEqual(result["hit_counts"]["reread_wording_drift"], 2)

    def test_reason_hygiene_scan_flags_surface_reread_label_colon_payload(self) -> None:
        result = self.reason_hygiene_scan.scan_text(
            "reason: 표현 오타/축약 패턴(범용): 표면값A; 표면값B"
        )

        self.assertIn("surface_reread_label_colon_payload", result["hits"])

    def test_reason_hygiene_scan_flags_difficult_to_determine_suffix_drift(self) -> None:
        result = self.reason_hygiene_scan.scan_text(
            "특정 작품으로 단정하기 어려움할 수 없어 비관련으로 둔다."
        )

        self.assertIn("bad_phrase", result["hits"])

    def test_evidence_catalog_merges_candidate_metadata_without_fake_snippet(self) -> None:
        row = {
            "analysis_result": {
                "analysis": {
                    "detected_titles": [
                        {
                            "official_title": "성녀의 속마음이 들린다",
                            "heretic_url": "https://novelpia.com/novel/314965",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "reference_role": "primary",
                        }
                    ]
                },
                "identity": {
                    "novel_identity": {
                        "official_title": "성녀의 속마음이 들린다",
                        "heretic_url": "https://novelpia.com/novel/314965",
                        "confidence": "High",
                    },
                    "primary_work": {
                        "official_title": "성녀의 속마음이 들린다",
                        "heretic_url": "https://novelpia.com/novel/314965",
                        "source_tier": "official_detail",
                        "page_type": "novel_page",
                        "reference_role": "primary",
                    },
                    "title_candidates": [
                        {
                            "official_title": "성녀의 속마음이 들린다",
                            "heretic_url": "https://novelpia.com/novel/314965",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "reference_role": "primary",
                        }
                    ],
                    "entity_mentions": [
                        {
                            "text": "성녀 속마음",
                            "entity_type": "work",
                            "canonical_value": "성녀의 속마음이 들린다",
                            "source": "title_candidates",
                            "role": "primary",
                            "confidence": "High",
                        }
                    ],
                    "search_evidence_catalog": [
                        {
                            "eid": "E0001",
                            "title": "성녀의 속마음이 들린다",
                            "url": "https://novelpia.com/novel/314965",
                            "snippet": "성녀의 속마음이 들린다 작품 상세",
                            "query": "성녀 속마음 노벨피아",
                            "source_tier": "novel_platform",
                        }
                    ],
                },
            }
        }
        idn = row["analysis_result"]["identity"]

        catalog = self.round2.evidence_catalog(row, idn)
        urls = self.round2.evidence_urls(idn)

        url_items = [item for item in catalog if item.get("url") == "https://novelpia.com/novel/314965"]
        self.assertGreaterEqual(len(url_items), 1)
        self.assertIn("https://novelpia.com/novel/314965", urls)
        merged_candidate = next(item for item in catalog if "identity.primary_work" in item["source_sections"])
        self.assertIn("identity.title_candidates", merged_candidate["source_sections"])
        self.assertIn("analysis.detected_titles", merged_candidate["source_sections"])
        search_item = next(item for item in catalog if "identity.search_evidence_catalog" in item["source_sections"])
        self.assertEqual(search_item["query"], "성녀 속마음 노벨피아")
        self.assertIn("작품 상세", search_item["snippet"])
        entity_items = [item for item in catalog if item.get("entity_type") == "work"]
        self.assertEqual(entity_items[0]["alias_or_mention"], "성녀 속마음")
        self.assertIsNone(entity_items[0]["snippet"])

    def test_structured_search_catalog_overrides_stale_zero_official_url_reason_counter(self) -> None:
        row = {
            "post_id": 9803986,
            "title": "k문제 질질 끄는 거 같네...",
            "content": [
                "결국 오늘 내용 요약하면",
                "니폰바이가 잘못된 선택을 내렸고",
                "그걸로 도하와 친구들이 니폰바이 뜯어먹을 거라는 소리...?",
            ],
            "comments": [],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "K-문화의 제왕",
                        "confidence": "High",
                    },
                    "discussion_type": "character_talk",
                    "topicality": "core_relevant",
                    "work_resolution": "resolved",
                    "anchor_type": "title_alias",
                    "anchor_strength": "medium",
                    "primary_work": {
                        "official_title": "K-문화의 제왕",
                        "confidence": "High",
                        "source_tier": "mixed",
                        "reference_role": "primary",
                    },
                    "reason": (
                        "[근거 요약] - official_title_evidence: true - title_in_post: true "
                        "- evidence_bucket: post_spans=2, search_snippets=0, official_urls=0 "
                        "[최종 종합] 제목/본문 앵커와 검색 근거를 종합하여 K-문화의 제왕 관련 작품 토론으로 판정"
                    ),
                    "search_evidence_catalog": [
                        {
                            "eid": "E002",
                            "title": "K-문화의 제왕 - 문피아 웹소설",
                            "url": "https://mm.munpia.com/?menu=novel&id=433967",
                            "snippet": "K-문화의 제왕. 고별 - 1998년으로 돌아왔다.",
                            "query": "k문제",
                            "source_tier": "novel_platform",
                        }
                    ],
                }
            },
        }

        facts = self.round2.extract_facts(1, row)
        packet = self.round2.build_packet("R2-TEST", "alias_recall_loss_false_negative", facts, Path("result.json"))
        label = self.round2.review_label(packet, facts)

        self.assertEqual(facts["catalog_official_urls"], 1)
        self.assertEqual(facts["catalog_search_snippets"], 1)
        self.assertEqual(facts["official_urls"], 1)
        self.assertEqual(facts["search_snippets"], 1)
        self.assertFalse(facts["weak_evidence"])
        self.assertEqual(packet["evidence_counts"]["official_urls"], 1)
        self.assertEqual(label["label"], "ACCEPT")
        self.assertEqual(label["action"], "no_action")

    def test_round2_flags_missing_final_semantic_reread_for_context_only_rescue(self) -> None:
        row = {
            "post_id": 11718091,
            "title": "소신발언)) 은영이 23센줄 몰랐음",
            "content": ["묘사만 보면 한 16살인줄???"],
            "comments": [],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "검색으로 올라온 후보작",
                        "confidence": "High",
                    },
                    "discussion_type": "general",
                    "work_resolution": "resolved",
                    "primary_work": {
                        "official_title": "검색으로 올라온 후보작",
                        "confidence": "High",
                        "source_tier": "llm_only",
                    },
                    "consistency_flags": ["surface_paraphrase_non_title_terms_removed"],
                    "reason": (
                        "[원문 해석] 표현 오타/축약 패턴(범용); "
                        "작품 seed 제외: 은영이 "
                        "[근거 요약] - official_title_evidence: false - title_in_post: false "
                        "- evidence_bucket: post_spans=0, search_snippets=1, official_urls=0"
                    ),
                }
            },
        }

        facts = self.round2.extract_facts(1, row)
        packet = self.round2.build_packet(
            "R2-TEST",
            "final_semantic_reread_missing_for_semantic_seed",
            facts,
            Path("result.json"),
        )
        label = self.round2.review_label(packet, facts)

        self.assertIn("final_semantic_reread_missing_for_semantic_seed", facts["bucket_reasons"])
        self.assertTrue(facts["semantic_seed_or_context_only_risk"])
        self.assertFalse(facts["final_semantic_reread_reviewed"])
        self.assertEqual(label["label"], "REJECT")
        self.assertEqual(label["action"], "re_judge")
        self.assertIn("final_semantic_reread_missing", label["boundary_risk"])

    def test_round2_accepts_repaired_official_url_when_same_url_search_title_supports_work(self) -> None:
        url = "https://m.munpia.com/novel/detail/328421"
        row = {
            "post_id": 11718097,
            "title": "망겜힐은 오행복 박태양이 빌런이였어야돼",
            "content": ["오행복과 박태양 서사 이야기"],
            "comments": [],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "망겜의 힐러",
                        "heretic_url": url,
                        "confidence": "Medium",
                    },
                    "discussion_type": "character_talk",
                    "work_resolution": "resolved",
                    "primary_work": {
                        "official_title": "망겜의 힐러",
                        "heretic_url": url,
                        "confidence": "Medium",
                        "source_tier": "official_detail",
                    },
                    "consistency_flags": ["official_detail_url_repaired_from_search"],
                    "reason": (
                        "[근거 요약] - official_title_evidence: true - title_in_post: true "
                        "- evidence_bucket: post_spans=2, search_snippets=1, official_urls=1 "
                        "이미지는 캐릭터/장면 보조 정보만 제공하여 최종 제목 확정 근거로 사용하지 않았습니다."
                    ),
                    "search_evidence_catalog": [
                        {
                            "eid": "E019",
                            "title": "망겜의 힐러 - 문피아 웹소설 - Munpia",
                            "url": url,
                            "snippet": "망겜의 힐러. 검미성 - 한 소방관이 눈을 떴을 때...",
                            "source_tier": "novel_platform",
                        }
                    ],
                }
            },
        }

        facts = self.round2.extract_facts(1, row)
        packet = self.round2.build_packet(
            "R2-TEST",
            "official_url_synopsis_or_branding_mismatch",
            facts,
            Path("result.json"),
        )
        label = self.round2.review_label(packet, facts)

        self.assertIn("official_url_synopsis_or_branding_mismatch", facts["bucket_reasons"])
        self.assertEqual(facts["final_heretic_url"], url)
        self.assertEqual(facts["catalog_official_urls"], 1)
        self.assertEqual(label["label"], "ACCEPT")
        self.assertEqual(label["action"], "no_action")
        self.assertIn("official_url_synopsis_or_branding_mismatch", label["boundary_risk"])

    def test_round2_packet_preserves_comment_author_context(self) -> None:
        row = {
            "post_id": 1,
            "gallery_id": "genrenovel",
            "title": "known alias discussion",
            "author": "writer",
            "post_author": "writer",
            "content": ["body"],
            "comments": ["same author reply"],
            "comment_metadata": [
                {
                    "index": 0,
                    "comment_id": "c1",
                    "author": "writer",
                    "ip": "1.2.3.4",
                    "speaker": "post_author",
                    "is_post_author": True,
                    "reply_level": 1,
                    "reply_to_comment_id": "c0",
                }
            ],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "Known Work",
                        "confidence": "High",
                    },
                    "work_resolution": "resolved",
                    "reason": (
                        "official_title_evidence: true; title_in_post: true; "
                        "evidence_bucket: post_spans=1, search_snippets=1, official_urls=1"
                    ),
                }
            },
            "run_meta": {"run_id": "run-comment"},
        }

        facts = self.round2.extract_facts(1, row)
        packet = self.round2.build_packet("R2-COMMENT", "weak_evidence_but_strong_resolution", facts, Path("result.json"))

        self.assertEqual(facts["comment_metadata_count"], 1)
        self.assertEqual(facts["comment_context_line_count"], 1)
        self.assertEqual(facts["comment_dialogue_context_line_count"], 1)
        self.assertEqual(facts["comment_context_source"], "reconstructed_from_comment_metadata")
        self.assertEqual(
            facts["comment_dialogue_context_source"],
            "reconstructed_from_comment_metadata_and_comments",
        )
        self.assertNotIn("comments_without_author_metadata", facts["bucket_reasons"])
        self.assertNotIn("comment_speaker_context_unavailable", facts["bucket_reasons"])
        self.assertEqual(packet["gallery_id"], "genrenovel")
        self.assertEqual(packet["post_author"], "writer")
        self.assertEqual(packet["comment_metadata"][0]["comment_id"], "c1")
        self.assertIn("author=writer", packet["comment_context_lines"][0])
        self.assertIn("role=post_author", packet["comment_context_lines"][0])
        self.assertIn("reply_to=c0", packet["comment_context_lines"][0])
        self.assertIn("text=same author reply", packet["comment_dialogue_context_lines"][0])
        self.assertEqual(packet["evidence_counts"]["comment_context_source"], "reconstructed_from_comment_metadata")
        self.assertEqual(
            packet["evidence_counts"]["comment_dialogue_context_source"],
            "reconstructed_from_comment_metadata_and_comments",
        )
        self.assertEqual(packet["prompt_public_fields"]["comment_metadata"][0]["ip"], "1.2.3.4")
        self.assertIn("comment_dialogue_context_lines", packet["prompt_public_fields"])

    def test_round2_flags_anonymous_author_ip_mismatch_dialogue_bucket(self) -> None:
        row = {
            "post_id": 2,
            "gallery_id": "genrenovel",
            "title": "댓글 화자 확인",
            "author": "ㅇㅇ",
            "post_ip": "123.248",
            "content": ["본문"],
            "comments": ["다른 유동 댓글"],
            "comment_metadata": [
                {
                    "index": 0,
                    "comment_id": "c1",
                    "author": "ㅇㅇ",
                    "ip": "211.36",
                    "speaker": "post_author",
                    "is_post_author": True,
                }
            ],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "댓글 후보작",
                        "confidence": "High",
                    },
                    "work_resolution": "resolved",
                    "reason": (
                        "official_title_evidence: true; title_in_post: false; "
                        "evidence_bucket: post_spans=0, search_snippets=1, official_urls=1"
                    ),
                }
            },
            "run_meta": {"run_id": "run-comment-ip"},
        }

        facts = self.round2.extract_facts(1, row)
        packet = self.round2.build_packet("R2-COMMENT-IP", "comment_author_ip_mismatch_dialogue", facts, Path("result.json"))
        label = self.round2.review_label(packet, facts)

        self.assertEqual(facts["post_ip"], "123.248")
        self.assertEqual(facts["comment_author_ip_mismatch_count"], 1)
        self.assertEqual(facts["suspicious_post_author_role_count"], 1)
        self.assertIn("comment_author_ip_mismatch_dialogue", facts["bucket_reasons"])
        self.assertIn("comment_author_ip_mismatch_dialogue", packet["risk_tags"])
        self.assertEqual(packet["post_ip"], "123.248")
        self.assertEqual(packet["evidence_counts"]["comment_author_ip_mismatch_count"], 1)
        self.assertEqual(packet["prompt_public_fields"]["post_ip"], "123.248")
        self.assertEqual(packet["result_public_fields"]["comment_author_ip_mismatch_count"], 1)
        self.assertEqual(label["label"], "HOLD")
        self.assertEqual(label["action"], "human_review")
        self.assertIn("comment_author_ip_mismatch", label["boundary_risk"])

    def test_round2_flags_anonymous_author_match_unverified_bucket(self) -> None:
        row = {
            "post_id": 3,
            "gallery_id": "genrenovel",
            "title": "댓글 화자 미확정",
            "author": "ㅇㅇ",
            "content": ["본문"],
            "comments": ["같은 닉이지만 IP 확인 없음"],
            "comment_metadata": [
                {
                    "index": 0,
                    "comment_id": "c1",
                    "author": "ㅇㅇ",
                    "speaker": "user1",
                    "is_post_author": False,
                    "post_author_match_unverified": True,
                }
            ],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "댓글 후보작",
                        "confidence": "High",
                    },
                    "work_resolution": "resolved",
                    "reason": (
                        "official_title_evidence: true; title_in_post: false; "
                        "evidence_bucket: post_spans=0, search_snippets=1, official_urls=1"
                    ),
                }
            },
            "run_meta": {"run_id": "run-comment-unverified"},
        }

        facts = self.round2.extract_facts(1, row)
        packet = self.round2.build_packet(
            "R2-COMMENT-UNVERIFIED",
            "comment_author_match_unverified_dialogue",
            facts,
            Path("result.json"),
        )
        label = self.round2.review_label(packet, facts)

        self.assertEqual(facts["comment_author_match_unverified_count"], 1)
        self.assertIn("comment_author_match_unverified_dialogue", facts["bucket_reasons"])
        self.assertIn("comment_author_match_unverified_dialogue", packet["risk_tags"])
        self.assertIn("role=author_match_unverified", packet["comment_context_lines"][0])
        self.assertEqual(packet["evidence_counts"]["comment_author_match_unverified_count"], 1)
        self.assertEqual(packet["result_public_fields"]["comment_author_match_unverified_count"], 1)
        self.assertEqual(label["label"], "HOLD")
        self.assertEqual(label["action"], "human_review")
        self.assertIn("comment_author_match_unverified", label["boundary_risk"])

    def test_round2_flags_batch_memory_rescue_without_anchor_buckets(self) -> None:
        row = {
            "post_id": 11718083,
            "title": "너에겐 네가 위기에 처했을때",
            "content": ["옛날에 무슨 소설에서 본 대사였는데 기억이 안남"],
            "comments": [],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "네이버",
                        "confidence": "High",
                    },
                    "work_resolution": "resolved",
                    "identity_state": "resolved_title",
                    "consistency_flags": [
                        "notes_demoted_for_unresolved",
                        "batch_memory_exact_alias_rescued",
                    ],
                    "reason": (
                        "grounding_anchor: none; official_title_evidence: false; "
                        "evidence_bucket: post_spans=0, search_snippets=0, official_urls=0; "
                        "작품 고유 근거 부족; 검증 반론(참고): memory query (critical)"
                    ),
                }
            },
        }

        facts = self.round2.extract_facts(1, row)
        packet = self.round2.build_packet("R2-BATCH-NO-ANCHOR", "batch_memory_exact_alias_rescued_no_anchor", facts, Path("result.json"))
        label = self.round2.review_label(packet, facts)

        self.assertIn("batch_memory_exact_alias_rescued_no_anchor", facts["bucket_reasons"])
        self.assertIn("critical_counter_but_resolved", facts["bucket_reasons"])
        self.assertIn("notes_demoted_then_resolved", facts["bucket_reasons"])
        self.assertIn("official_url_missing_for_resolved", facts["bucket_reasons"])
        self.assertIn("reason_says_no_anchor_but_resolved", facts["bucket_reasons"])
        self.assertTrue(packet["evidence_counts"]["batch_memory_exact_alias_rescued"])
        self.assertTrue(packet["evidence_counts"]["no_or_search_only_anchor"])
        self.assertTrue(packet["evidence_counts"]["official_url_missing_for_resolved"])
        self.assertEqual(label["label"], "REJECT")
        self.assertEqual(label["action"], "slang_db_review")
        self.assertIn("batch_memory_alias_overreach", label["boundary_risk"])

    def test_round2_flags_memory_query_official_candidate_without_quote_alignment(self) -> None:
        row = {
            "post_id": 11718083,
            "title": "너에겐 네가 위기에 처했을때",
            "content": ["옛날에 무슨 소설에서 본 대사였는데 기억이 안남"],
            "comments": [],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "하차 이후의 소설 속",
                        "heretic_url": "https://series.naver.com/novel/detail.series?productNo=8830908",
                        "confidence": "High",
                    },
                    "primary_work": {
                        "official_title": "하차 이후의 소설 속",
                        "heretic_url": "https://series.naver.com/novel/detail.series?productNo=8830908",
                        "source_tier": "official_detail",
                    },
                    "work_resolution": "resolved",
                    "identity_state": "resolved_title",
                    "reason": (
                        "official_title_evidence: true; title_in_post: false; "
                        "evidence_bucket: post_spans=0, search_snippets=1, official_urls=1; "
                        "후보 공식 작품 페이지를 확인했다."
                    ),
                    "search_evidence_catalog": [
                        {
                            "title": "하차 이후의 소설 속 - 네이버 시리즈",
                            "url": "https://series.naver.com/novel/detail.series?productNo=8830908",
                            "snippet": "하차 이후의 소설 속 작품 소개와 회차 정보",
                            "query": "\"너에겐 네가 위기에 처했을때\"",
                            "source_tier": "novel_platform",
                        }
                    ],
                }
            },
        }

        facts = self.round2.extract_facts(1, row)
        packet = self.round2.build_packet(
            "R2-QUOTE-MISSING",
            "quote_alignment_missing_for_memory_query",
            facts,
            Path("result.json"),
        )
        label = self.round2.review_label(packet, facts)

        self.assertTrue(facts["memory_query_resolved"])
        self.assertIn("너에겐 네가 위기에 처했을때", facts["memory_query_quote_terms"])
        self.assertEqual(facts["candidate_official_page_hits"], 1)
        self.assertEqual(facts["quote_alignment_support_count"], 0)
        self.assertTrue(facts["quote_alignment_missing_for_memory_query"])
        self.assertIn("quote_alignment_missing_for_memory_query", facts["bucket_reasons"])
        self.assertIn("quote_alignment_missing_for_memory_query", packet["risk_tags"])
        self.assertEqual(packet["evidence_counts"]["quote_alignment_support_count"], 0)
        self.assertEqual(packet["evidence_counts"]["candidate_official_page_hits"], 1)
        self.assertTrue(packet["result_public_fields"]["quote_alignment_missing_for_memory_query"])
        self.assertEqual(label["label"], "HOLD")
        self.assertEqual(label["action"], "human_review")
        self.assertIn("quote_alignment_missing", label["boundary_risk"])

    def test_round2_does_not_flag_memory_query_when_quote_alignment_is_direct(self) -> None:
        row = {
            "post_id": 11718083,
            "title": "너에겐 네가 위기에 처했을때",
            "content": ["옛날에 무슨 소설에서 본 대사였는데 기억이 안남"],
            "comments": [],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "후보 작품",
                        "heretic_url": "https://novelpia.com/novel/12345",
                        "confidence": "High",
                    },
                    "primary_work": {
                        "official_title": "후보 작품",
                        "heretic_url": "https://novelpia.com/novel/12345",
                        "source_tier": "official_detail",
                    },
                    "work_resolution": "resolved",
                    "reason": (
                        "official_title_evidence: true; title_in_post: false; "
                        "evidence_bucket: post_spans=0, search_snippets=1, official_urls=1"
                    ),
                    "search_evidence_catalog": [
                        {
                            "title": "후보 작품 - 노벨피아",
                            "url": "https://novelpia.com/novel/12345",
                            "snippet": "너에겐 네가 위기에 처했을때 달려와 줄 친구가 있다는 대사가 등장한다.",
                            "source_tier": "novel_platform",
                        }
                    ],
                }
            },
        }

        facts = self.round2.extract_facts(1, row)

        self.assertTrue(facts["memory_query_resolved"])
        self.assertGreaterEqual(facts["quote_alignment_support_count"], 1)
        self.assertFalse(facts["quote_alignment_missing_for_memory_query"])
        self.assertNotIn("quote_alignment_missing_for_memory_query", facts["bucket_reasons"])

    def test_round2_does_not_flag_no_anchor_when_title_alias_has_official_detail(self) -> None:
        row = {
            "post_id": 11718078,
            "title": "즉사무림 그정도 재미임?",
            "content": ["초반부는 재밌는데 후반부 어떰?"],
            "comments": [],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "즉사기 들고 무림에 떨어지다",
                        "confidence": "High",
                        "heretic_url": "https://novel.munpia.com/528383",
                    },
                    "primary_work": {
                        "official_title": "즉사기 들고 무림에 떨어지다",
                        "source_tier": "official_detail",
                        "heretic_url": "https://novel.munpia.com/528383",
                    },
                    "work_resolution": "resolved",
                    "identity_state": "resolved_title",
                    "search_evidence_catalog": [
                        {
                            "title": "즉사기 들고 무림에 떨어지다",
                            "url": "https://novel.munpia.com/528383",
                            "snippet": "문피아 웹소설 즉사기 들고 무림에 떨어지다",
                        }
                    ],
                    "reason": (
                        "grounding_anchor: title_abbrev_mention; official_title_evidence: true; "
                        "title_in_post: true; evidence_bucket: post_spans=1, search_snippets=3, official_urls=1; "
                        "본문에는 캐릭터/줄거리 고유 앵커가 부족하지만 제목 약칭과 공식 상세 URL이 직접 일치한다."
                    ),
                }
            },
        }

        facts = self.round2.extract_facts(1, row)

        self.assertTrue(facts["no_or_search_only_anchor"])
        self.assertTrue(facts["strong_title_alias_or_direct_evidence"])
        self.assertFalse(facts["reason_says_no_anchor_but_resolved"])
        self.assertNotIn("reason_says_no_anchor_but_resolved", facts["bucket_reasons"])

    def test_round2_accepts_platform_non_detail_when_official_detail_and_title_anchor_exist(self) -> None:
        row = {
            "post_id": 11718078,
            "title": "즉사무림 그정도 재미임?",
            "content": ["언급 많네"],
            "comments": [],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "즉사기 들고 무림에 떨어지다",
                        "confidence": "High",
                        "heretic_url": "https://novel.munpia.com/528383",
                    },
                    "primary_work": {
                        "official_title": "즉사기 들고 무림에 떨어지다",
                        "source_tier": "official_detail",
                        "heretic_url": "https://novel.munpia.com/528383",
                    },
                    "discussion_type": "character_talk",
                    "work_resolution": "resolved",
                    "reason": (
                        "grounding_anchor: title_mention; title_in_post: true; "
                        "official_title_evidence: true; evidence_bucket: post_spans=2, "
                        "search_snippets=2, official_urls=1"
                    ),
                    "search_evidence_catalog": [
                        {
                            "title": "즉사기 들고 무림에 떨어지다 - 문피아 웹소설",
                            "url": "https://novel.munpia.com/528383",
                            "snippet": "즉사기 들고 무림에 떨어지다 작품 상세",
                            "source_tier": "novel_platform",
                        },
                        {
                            "title": "즉사기 들고 무림에 떨어지다 검색 결과",
                            "url": "https://www.munpia.com/page/best",
                            "snippet": "즉사기 들고 무림에 떨어지다 관련 목록",
                            "source_tier": "novel_platform",
                        },
                    ],
                }
            },
        }

        facts = self.round2.extract_facts(1, row)
        packet = self.round2.build_packet(
            "R2-PLATFORM-MIXED",
            "platform_non_detail_url_used_near_official_evidence",
            facts,
            Path("result.json"),
        )
        label = self.round2.review_label(packet, facts)

        self.assertIn("platform_non_detail_url_used_near_official_evidence", facts["bucket_reasons"])
        self.assertEqual(facts["catalog_official_urls"], 1)
        self.assertEqual(facts["platform_non_detail_urls"], 1)
        self.assertTrue(facts["strong_title_alias_or_direct_evidence"])
        self.assertEqual(label["label"], "ACCEPT")
        self.assertEqual(label["action"], "no_action")

    def test_round2_accepts_false_negative_recall_when_title_null_trope_boundary_is_closed(self) -> None:
        row = {
            "post_id": 11718080,
            "title": "소설 보는 친구 있으면 좋음...",
            "content": ["밥 먹으면서 TS랑 장르 얘기할 친구 있으면 좋겠다는 잡담"],
            "comments": [],
            "analysis_result": {
                "identity": {
                    "is_relevant": False,
                    "novel_identity": {},
                    "discussion_type": "trope_discussion",
                    "work_resolution": "none",
                    "title_resolution_state": "adjacent",
                    "title_resolution_allowed": False,
                    "reason": (
                        "판정: 주변 관련; 특정 작품보다 장르/트로프 일반론에 가깝습니다. "
                        "공식 제목: 미확정; grounding_anchor: none"
                    ),
                }
            },
        }

        facts = self.round2.extract_facts(1, row)
        packet = self.round2.build_packet("R2-TROPE-NULL", "round2_false_negative_recall", facts, Path("result.json"))
        label = self.round2.review_label(packet, facts)

        self.assertIn("round2_false_negative_recall", facts["bucket_reasons"])
        self.assertEqual(label["label"], "ACCEPT")
        self.assertEqual(label["action"], "no_action")

    def test_round2_accepts_author_match_unverified_when_context_only_no_title_is_closed(self) -> None:
        row = {
            "post_id": 11718091,
            "gallery_id": "genrenovel",
            "title": "소신발언)) 은영이 23센줄 몰랐음",
            "author": "ㅇㅇ",
            "content": ["묘사만 보면 한 16살인줄???"],
            "comments": ["머리도 안올렸잖아 더어린줄"],
            "comment_metadata": [
                {
                    "index": 0,
                    "comment_id": "c1",
                    "author": "ㅇㅇ",
                    "speaker": "user1",
                    "is_post_author": False,
                    "post_author_match_unverified": True,
                }
            ],
            "analysis_result": {
                "identity": {
                    "is_relevant": False,
                    "novel_identity": {},
                    "discussion_type": "noise",
                    "work_resolution": "none",
                    "title_resolution_state": "context_only",
                    "title_resolution_allowed": False,
                    "consistency_flags": [
                        "context_only_no_work_anchor",
                        "comment_author_match_unverified_not_independent_evidence",
                    ],
                    "reason": (
                        "판정: 비관련; 표현 오타/축약 패턴(범용); "
                        "댓글 author_match_unverified는 독립 작품 근거가 아니다."
                    ),
                }
            },
        }

        facts = self.round2.extract_facts(1, row)
        packet = self.round2.build_packet(
            "R2-COMMENT-CONTEXT-CLOSED",
            "comment_author_match_unverified_dialogue",
            facts,
            Path("result.json"),
        )
        label = self.round2.review_label(packet, facts)

        self.assertIn("comment_author_match_unverified_dialogue", facts["bucket_reasons"])
        self.assertEqual(label["label"], "ACCEPT")
        self.assertEqual(label["action"], "no_action")

    def test_minor_alias_counter_with_official_evidence_is_accept(self) -> None:
        row = {
            "post_id": 11718097,
            "title": "망겜힐은 오행복 박태양이 빌런이였어야돼",
            "content": ["오행복과 박태양 서사 이야기"],
            "comments": ["검미성이면 할 수 있는데"],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "망겜의 힐러",
                        "heretic_url": "https://m.munpia.com/novel/detail/328421",
                        "confidence": "High",
                    },
                    "primary_work": {
                        "official_title": "망겜의 힐러",
                        "heretic_url": "https://m.munpia.com/novel/detail/328421",
                        "source_tier": "official_detail",
                    },
                    "work_resolution": "resolved",
                    "identity_state": "resolved_title",
                    "discussion_type": "character_talk",
                    "reason": (
                        "grounding_anchor: title_abbrev_mention; official_title_evidence: true; "
                        "title_in_post: true; evidence_bucket: post_spans=4, search_snippets=48, official_urls=4; "
                        "검증 반론(참고): 제목 '망겜힐'과 정식명 '망겜의 힐러' 불일치(minor)"
                    ),
                }
            },
        }

        facts = self.round2.extract_facts(1, row)
        packet = self.round2.build_packet("R2-MINOR-ALIAS", "critical_counter_but_resolved", facts, Path("result.json"))
        label = self.round2.review_label(packet, facts)

        self.assertIn("critical_counter_but_resolved", facts["bucket_reasons"])
        self.assertTrue(facts["strong_title_alias_or_direct_evidence"])
        self.assertEqual(label["label"], "ACCEPT")
        self.assertEqual(label["action"], "no_action")
        self.assertIn("minor_alias_normalization_counter", label["boundary_risk"])

    def test_round2_flags_search_absent_image_title_bucket(self) -> None:
        row = {
            "post_id": 11718099,
            "title": "빌환 표지변경됨",
            "content": ["[이미지 OCR] MUNPIA 검은 여왕의 혼성명 묵마 퓨전판타지 소설"],
            "comments": [],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "검은 여왕의 혼성명",
                        "confidence": "High",
                    },
                    "work_resolution": "resolved",
                    "context_sources": ["title", "body", "image"],
                    "consistency_flags": ["title_surface_primary_candidate_rescued"],
                    "reason": (
                        "이미지 OCR: MUNPIA 검은 여왕의 혼성명; "
                        "official_title_evidence: false; title_in_post: false; "
                        "evidence_bucket: post_spans=0, search_snippets=0, official_urls=0; "
                        "검증 반론(참고): search_absent_verified_title(critical)"
                    ),
                }
            },
        }

        facts = self.round2.extract_facts(1, row)
        packet = self.round2.build_packet(
            "R2-IMAGE-SEARCH-ABSENT",
            "search_absent_verified_title_direct_image_title",
            facts,
            Path("result.json"),
        )
        label = self.round2.review_label(packet, facts)

        self.assertIn("search_absent_verified_title_direct_image_title", facts["bucket_reasons"])
        self.assertIn("title_surface_primary_candidate_rescued", facts["bucket_reasons"])
        self.assertIn("critical_counter_but_resolved", facts["bucket_reasons"])
        self.assertTrue(packet["evidence_counts"]["search_absent_verified_title"])
        self.assertTrue(packet["evidence_counts"]["direct_image_title"])
        self.assertEqual(label["label"], "REPROCESS")
        self.assertEqual(label["action"], "human_review")
        self.assertIn("visual_ocr_contradiction", label["boundary_risk"])

    def test_round2_packet_includes_image_evidence_catalog(self) -> None:
        row = {
            "post_id": 11718082,
            "title": "이 장면 어디 작품임?",
            "content": ["스크린샷 요약"],
            "content_blocks": [
                {"type": "image", "url": "https://dcimg.example/post11718082.jpg"},
                {"type": "text", "text": "스크린샷 요약"},
            ],
            "image_urls": ["https://dcimg.example/post11718082.jpg"],
            "image_count": 1,
            "comments": [],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "재벌가 차녀의 2회차 걸그룹",
                        "heretic_url": "https://page.kakao.com/content/123456",
                        "confidence": "High",
                    },
                    "work_resolution": "resolved",
                    "discussion_type": "character_talk",
                    "context_sources": ["title", "body", "image"],
                    "reason": (
                        "이미지 OCR 근거. official_title_evidence: true; title_in_post: false; "
                        "evidence_bucket: post_spans=0, search_snippets=1, official_urls=1"
                    ),
                    "image_evidence_catalog": [
                        {
                            "eid": "IMG-1",
                            "rank": 1,
                            "source_url": "https://dcimg.example/post11718082.jpg",
                            "ocr_text": "재벌가 차녀의 2회차 걸그룹 267화 중",
                            "visual_summary": "카카오페이지 문구형 스크린샷",
                            "explicit_work_title": "재벌가 차녀의 2회차 걸그룹",
                            "explicit_author_name": "유은우",
                            "evidence_type": "image_ocr",
                            "title_role": "explicit_work_title",
                            "promotion_eligible": True,
                            "work_cues": ["카카오페이지", "267화"],
                        }
                    ],
                }
            },
        }
        idn = row["analysis_result"]["identity"]

        facts = self.round2.extract_facts(1, row)
        packet = self.round2.build_packet("R2-IMAGE-CATALOG", "VLM_OCR_involved", facts, Path("result.json"))
        catalog = self.round2.evidence_catalog(row, idn)

        image_item = next(item for item in catalog if "identity.image_evidence_catalog" in item["source_sections"])
        self.assertEqual(image_item["url"], "https://dcimg.example/post11718082.jpg")
        self.assertEqual(image_item["explicit_work_title"], "재벌가 차녀의 2회차 걸그룹")
        self.assertIn("267화", image_item["ocr_text"])
        self.assertEqual(packet["image_count"], 1)
        self.assertEqual(packet["image_urls"], ["https://dcimg.example/post11718082.jpg"])
        self.assertFalse(facts["image_evidence_catalog_missing"])
        self.assertNotIn("image_evidence_catalog_missing", facts["bucket_reasons"])
        self.assertEqual(packet["vlm_ocr_fields"]["image_evidence_catalog_count"], 1)
        self.assertEqual(
            packet["vlm_ocr_fields"]["image_evidence_catalog"][0]["explicit_work_title"],
            "재벌가 차녀의 2회차 걸그룹",
        )

    def test_round2_flags_missing_image_evidence_catalog_bucket(self) -> None:
        row = {
            "post_id": 11718082,
            "title": "스크린샷 있음",
            "content": ["[이미지 첨부]"],
            "content_blocks": [{"type": "image", "url": "https://dcimg.example/missing.jpg"}],
            "image_urls": ["https://dcimg.example/missing.jpg"],
            "image_count": 1,
            "comments": [],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "재벌가 차녀의 2회차 걸그룹",
                        "confidence": "High",
                    },
                    "work_resolution": "resolved",
                    "context_sources": ["title", "image"],
                    "reason": (
                        "이미지 OCR로 작품명 후보를 봄. "
                        "official_title_evidence: false; title_in_post: false; "
                        "evidence_bucket: post_spans=0, search_snippets=0, official_urls=0"
                    ),
                }
            },
        }

        facts = self.round2.extract_facts(1, row)
        packet = self.round2.build_packet(
            "R2-IMAGE-MISSING",
            "image_evidence_catalog_missing",
            facts,
            Path("result.json"),
        )
        label = self.round2.review_label(packet, facts)

        self.assertTrue(facts["image_evidence_catalog_missing"])
        self.assertIn("image_evidence_catalog_missing", facts["bucket_reasons"])
        self.assertEqual(packet["vlm_ocr_fields"]["image_evidence_catalog_count"], 0)
        self.assertTrue(packet["vlm_ocr_fields"]["image_evidence_catalog_missing"])
        self.assertEqual(label["label"], "REPROCESS")
        self.assertEqual(label["action"], "re_run")
        self.assertIn("image_evidence_catalog_missing", label["boundary_risk"])

    def test_round2_does_not_dedupe_against_random_control_labels(self) -> None:
        row = {
            "post_id": 11718082,
            "title": "스크린샷 있음",
            "content": ["[이미지 첨부]"],
            "content_blocks": [{"type": "image", "url": "https://dcimg.example/missing.jpg"}],
            "image_urls": ["https://dcimg.example/missing.jpg"],
            "image_count": 1,
            "comments": [],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "재벌가 차녀의 2회차 걸그룹",
                        "confidence": "High",
                    },
                    "work_resolution": "resolved",
                    "context_sources": ["title", "image"],
                    "reason": (
                        "이미지 OCR로 작품명 후보를 봄. "
                        "official_title_evidence: false; title_in_post: false; "
                        "evidence_bucket: post_spans=0, search_snippets=0, official_urls=0"
                    ),
                }
            },
        }
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_path = tmp_path / "result.json"
            result_path.write_text(json.dumps([row], ensure_ascii=False), encoding="utf-8")
            review_dir = tmp_path / "review"
            review_dir.mkdir()
            random_label = {
                "round": "round1_random_control",
                "bucket": "random_control",
                "post_id": 11718082,
                "label": "REPROCESS",
            }
            (review_dir / "review_labels.jsonl").write_text(
                json.dumps(random_label, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            packets, labels, manifest = self.round2.select_round2(result_path, review_dir, 1.0)

        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0]["post_id"], 11718082)
        self.assertEqual(labels[0]["post_id"], 11718082)
        self.assertEqual(manifest["excluded_existing_review_post_ids"], 0)

    def test_random_control_applies_high_risk_bucket_policy(self) -> None:
        row = {
            "post_id": 11718091,
            "title": "소신발언)) 은영이 23센줄 몰랐음",
            "content": ["묘사만 보면 한 16살인줄???"],
            "comments": ["ㄹㅇ 머리도 안올렷잖아 더어린줄"],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "Re:제로부터 시작하는 원신생존기",
                        "confidence": "High",
                    },
                    "work_resolution": "resolved",
                    "identity_state": "resolved_title",
                    "context_sources": ["title", "body", "comments", "search"],
                    "consistency_flags": ["batch_memory_exact_alias_rescued"],
                    "reason": (
                        "official_title_evidence: true; title_in_post: true; "
                        "evidence_bucket: post_spans=1, search_snippets=1, official_urls=0; "
                        "grounding_anchor: none; Verifier critical counter"
                    ),
                }
            },
        }

        facts = self.round2.extract_facts(1, row)
        packet = self.round2.build_packet("RC3-TEST", "random_control", facts, Path("result.json"))
        label = self.round2.review_label(packet, facts)

        self.assertEqual(label["bucket"], "random_control")
        self.assertEqual(label["applied_review_bucket"], "reason_says_no_anchor_but_resolved")
        self.assertEqual(label["label"], "REJECT")
        self.assertEqual(label["action"], "re_judge")
        self.assertIn("no_anchor_resolved", label["boundary_risk"])

    def test_round2_recovered_source_policy_preserves_original_run_id(self) -> None:
        recovered_path = Path(
            "qualitative_review/20260528_141006_620986/v162_run_integrity_recovered_completed_80.json"
        )
        summary = {
            "integrity_classification": "recoverable_pending_flush_gap",
            "recovery_safe_to_use_as_completed_subset": True,
            "large_run_complete": False,
            "final_result_rows": 71,
            "checkpoint_completed_rows": 80,
            "pending_snapshot_rows": 9,
            "recovered_rows": 80,
            "summary_path": "qualitative_review/20260528_141006_620986/v162_run_integrity_recovery_summary.json",
        }

        self.assertEqual(self.round2.infer_run_id(recovered_path), "20260528_141006_620986")
        policy = self.round2.source_review_policy(recovered_path, summary)

        self.assertEqual(policy["source_dataset_kind"], "checkpoint_recovered_completed_subset")
        self.assertEqual(policy["source_integrity_classification"], "recoverable_pending_flush_gap")
        self.assertTrue(policy["recovery_safe_to_use_as_completed_subset"])
        self.assertFalse(policy["large_run_complete"])
        self.assertEqual(policy["counts"]["recovered_rows"], 80)
        self.assertIn("semantic approval 근거로 쓰지 않는다", policy["approval_policy"])

    def test_round2_final_result_source_policy_is_not_reclassified_by_recovery_summary(self) -> None:
        result_path = Path("out/expert_result_20260528_141006_620986.json")
        summary = {
            "integrity_classification": "recoverable_pending_flush_gap",
            "recovery_safe_to_use_as_completed_subset": True,
            "large_run_complete": False,
            "final_result_rows": 71,
            "checkpoint_completed_rows": 80,
            "pending_snapshot_rows": 9,
            "recovered_rows": 80,
            "summary_path": "qualitative_review/20260528_141006_620986/v162_run_integrity_recovery_summary.json",
        }

        policy = self.round2.source_review_policy(result_path, summary)

        self.assertEqual(policy["source_dataset_kind"], "final_result_json")
        self.assertFalse(policy["large_run_complete"])
        self.assertIn("large run incomplete", policy["approval_policy"])

    def test_random_control_manifest_records_sample_shortfall(self) -> None:
        random_tool = __import__("importlib").util.spec_from_file_location(
            "build_qualitative_random_control_review",
            Path(__file__).resolve().parents[1] / "tools" / "build_qualitative_random_control_review.py",
        )
        self.assertIsNotNone(random_tool)
        self.assertIsNotNone(random_tool.loader)
        module = __import__("importlib").util.module_from_spec(random_tool)
        random_tool.loader.exec_module(module)

        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            result_path = tmp / "expert_result_20260528_141006_620986.json"
            rows = [
                {
                    "post_id": 1,
                    "title": "작품 A",
                    "content": ["본문"],
                    "comments": [],
                    "analysis_result": {"identity": {"is_relevant": False, "reason": "noise"}},
                },
                {
                    "post_id": 2,
                    "title": "작품 B",
                    "content": ["본문"],
                    "comments": [],
                    "analysis_result": {
                        "identity": {
                            "is_relevant": True,
                            "novel_identity": {"official_title": "작품 B", "confidence": "High"},
                            "reason": "official_title_evidence: true; evidence_bucket: post_spans=1, search_snippets=1, official_urls=1",
                        }
                    },
                },
            ]
            result_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

            selected, manifest = module.select_random_rows(result_path, tmp, self.round2, 5)

        self.assertEqual(len(selected), 2)
        self.assertEqual(manifest["requested_sample_size"], 5)
        self.assertEqual(manifest["selected_sample_size"], 2)
        self.assertEqual(manifest["sample_shortfall"], 3)
        self.assertFalse(manifest["sample_target_satisfied"])

    def test_large_scale_preflight_blocks_partial_recovered_subset(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            result_path = tmp / "v162_run_integrity_recovered_completed_80.json"
            result_path.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 1,
                            "title": "작품 A",
                            "content": ["본문"],
                            "comments": [],
                            "analysis_result": {"identity": {"is_relevant": False, "reason": "noise"}},
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            manifest_path = tmp / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "input_post_count": 100,
                        "completed_count": 80,
                        "flushed_count": 71,
                        "pending_count": 9,
                        "failed_count": 0,
                    }
                ),
                encoding="utf-8",
            )
            summary_path = tmp / "summary.json"
            summary_path.write_text(
                json.dumps(
                    {
                        "integrity_classification": "recoverable_pending_flush_gap",
                        "recovery_safe_to_use_as_completed_subset": True,
                        "large_run_complete": False,
                        "final_result_rows": 71,
                        "checkpoint_completed_rows": 80,
                        "pending_snapshot_rows": 9,
                        "recovered_rows": 80,
                    }
                ),
                encoding="utf-8",
            )

            preflight = self.large_scale_preflight.build_preflight(
                result_path=result_path,
                manifest_path=manifest_path,
                checkpoint_path=None,
                pending_path=None,
                source_integrity_summary_path=summary_path,
                random_target=1000,
                target_scale=1.0,
            )

        self.assertEqual(preflight["gate"]["overall"], "REVIEW-LOCKED")
        self.assertIn("large_run_completion_not_proven", preflight["gate"]["blockers"])
        self.assertIn("random_baseline_target_not_feasible", preflight["gate"]["blockers"])
        self.assertEqual(preflight["random_baseline"]["shortfall"], 999)
        self.assertFalse(preflight["manifest_completion_state"]["clean_by_counts"])
        self.assertIn("pending_count_gt_zero", preflight["manifest_completion_state"]["partial_signals"])
        self.assertEqual(preflight["source_review_policy"]["source_dataset_kind"], "checkpoint_recovered_completed_subset")
        self.assertFalse(preflight["source_review_policy"]["large_run_complete"])
        self.assertIn("obtain_completed_source", preflight["gate"]["required_next_actions"])
        self.assertIn("keep_current_source_as_regression_seed_only", preflight["gate"]["required_next_actions"])

    def test_large_scale_preflight_classifies_manifest_partial_final_result(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            result_path = tmp / "expert_result_20260528_141006_620986.json"
            result_path.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 1,
                            "title": "작품 A",
                            "content": ["본문"],
                            "comments": [],
                            "analysis_result": {"identity": {"is_relevant": False, "reason": "noise"}},
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            manifest_path = tmp / "expert_result_20260528_141006_620986_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "input_post_count": 104502,
                        "completed_count": 80,
                        "flushed_count": 71,
                        "pending_count": 9,
                        "failed_count": 0,
                    }
                ),
                encoding="utf-8",
            )

            preflight = self.large_scale_preflight.build_preflight(
                result_path=result_path,
                manifest_path=manifest_path,
                checkpoint_path=None,
                pending_path=None,
                source_integrity_summary_path=None,
                random_target=1000,
                target_scale=1.0,
            )

        self.assertEqual(preflight["source_review_policy"]["source_dataset_kind"], "partial_final_result_json")
        self.assertEqual(preflight["source_review_policy"]["source_integrity_classification"], "manifest_partial_run")
        self.assertFalse(preflight["source_review_policy"]["large_run_complete"])
        self.assertIn("regression seed", preflight["source_review_policy"]["approval_policy"])
        self.assertEqual(preflight["source_review_policy"]["counts"]["final_result_rows"], 1)
        self.assertIn("obtain_completed_source", preflight["gate"]["required_next_actions"])
        self.assertIn("keep_current_source_as_regression_seed_only", preflight["gate"]["required_next_actions"])

    def test_large_scale_preflight_fail_on_locked_exit_code(self) -> None:
        locked = {"gate": {"overall": "REVIEW-LOCKED"}}
        unlocked = {"gate": {"overall": "REVIEW"}}

        self.assertEqual(
            self.large_scale_preflight.exit_code_for_gate(locked, fail_on_locked=False),
            0,
        )
        self.assertEqual(
            self.large_scale_preflight.exit_code_for_gate(locked, fail_on_locked=True),
            2,
        )
        self.assertEqual(
            self.large_scale_preflight.exit_code_for_gate(unlocked, fail_on_locked=True),
            0,
        )

    def test_review_builders_block_locked_or_mismatched_preflight_source(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result_path = (root / "expert_result_20260528_141006_620986.json").resolve()
            other_result = (root / "other_result.json").resolve()

            missing = self.round2.preflight_source_gate_status(
                None,
                result_path=result_path,
                fail_on_locked_source=True,
            )
            locked = self.round2.preflight_source_gate_status(
                {
                    "source_result_path": result_path.as_posix(),
                    "gate": {
                        "overall": "REVIEW-LOCKED",
                        "required_next_actions": ["obtain_completed_source"],
                    },
                },
                result_path=result_path,
                fail_on_locked_source=True,
            )
            mismatch = self.round2.preflight_source_gate_status(
                {
                    "source_result_path": other_result.as_posix(),
                    "gate": {"overall": "GO"},
                },
                result_path=result_path,
                fail_on_locked_source=True,
            )
            allowed = self.round2.preflight_source_gate_status(
                {
                    "source_result_path": result_path.as_posix(),
                    "gate": {"overall": "GO"},
                },
                result_path=result_path,
                fail_on_locked_source=True,
            )
            not_requested = self.round2.preflight_source_gate_status(
                None,
                result_path=result_path,
                fail_on_locked_source=False,
            )

        self.assertEqual(missing["exit_code"], 2)
        self.assertEqual(missing["reason"], "preflight_missing")
        self.assertEqual(locked["exit_code"], 2)
        self.assertEqual(locked["reason"], "preflight_review_locked")
        self.assertIn("obtain_completed_source", locked["required_next_actions"])
        self.assertEqual(mismatch["exit_code"], 2)
        self.assertEqual(mismatch["reason"], "preflight_source_mismatch")
        self.assertEqual(allowed["exit_code"], 0)
        self.assertFalse(allowed["blocked"])
        self.assertEqual(not_requested["exit_code"], 0)

    def test_large_scale_preflight_markdown_uses_korean_review_headings(self) -> None:
        with TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "preflight_ko.md"
            preflight = {
                "run_id": "test_run",
                "generated_at": "2026-05-31T00:00:00",
                "source_result_path": "out/result.json",
                "result_rows": 71,
                "source_review_policy": {
                    "source_dataset_kind": "final_result_json",
                    "source_integrity_classification": None,
                    "large_run_complete": False,
                    "approval_policy": "semantic review 근거로 쓰기 전 정합성을 확인한다.",
                },
                "manifest_completion_state": {
                    "input_post_count": 100,
                    "completed_count": 80,
                    "flushed_count": 71,
                    "pending_count": 9,
                    "failed_count": 0,
                    "partial_signals": ["pending_count_gt_zero"],
                },
                "checkpoint_completed_rows": 80,
                "pending_snapshot_rows": 9,
                "random_baseline": {
                    "requested_sample_size": 1000,
                    "available_rows": 71,
                    "feasible": False,
                    "shortfall": 929,
                },
                "high_risk": {"target_total": 660},
                "gate": {
                    "run_integrity": "REVIEW",
                    "semantic_preflight": "REVIEW-LOCKED",
                    "overall": "REVIEW-LOCKED",
                    "blockers": ["random_baseline_target_not_feasible"],
                    "required_next_actions": ["obtain_completed_source"],
                },
            }

            self.large_scale_preflight.write_markdown(out, preflight)
            text = out.read_text(encoding="utf-8")

        self.assertIn("# 대규모 정성 리뷰 사전 점검 - test_run", text)
        self.assertIn("## Source 정책", text)
        self.assertIn("## 표본 추출 가능성", text)
        self.assertIn("- 원본 source:", text)
        self.assertIn("- 다음 필수 액션:", text)
        self.assertNotIn("# Large-Scale Qualitative Review Preflight", text)
        self.assertNotIn("## Sampling Feasibility", text)

    def test_round2_missing_comment_author_context_is_info_missing(self) -> None:
        row = {
            "post_id": 2,
            "title": "comment-dependent discussion",
            "author": "writer",
            "content": ["body"],
            "comments": ["reply without public author metadata"],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "Weak Work",
                        "confidence": "High",
                    },
                    "work_resolution": "resolved",
                    "reason": (
                        "official_title_evidence: false; title_in_post: false; "
                        "evidence_bucket: post_spans=0, search_snippets=0, official_urls=0"
                    ),
                }
            },
            "run_meta": {"run_id": "run-comment"},
        }

        facts = self.round2.extract_facts(1, row)
        packet = self.round2.build_packet("R2-MISSING", "comments_without_author_metadata", facts, Path("result.json"))
        label = self.round2.review_label(packet, facts)

        self.assertIn("comments_without_author_metadata", facts["bucket_reasons"])
        self.assertIn("comment_speaker_context_unavailable", facts["bucket_reasons"])
        self.assertEqual(packet["comment_metadata"], [])
        self.assertEqual(packet["comment_context_lines"], [])
        self.assertEqual(packet["comment_context_source"], "missing")
        self.assertEqual(packet["comment_dialogue_context_source"], "reconstructed_from_comments_only")
        self.assertEqual(label["label"], "INFO_MISSING")
        self.assertEqual(label["action"], "human_review")
        self.assertEqual(label["evidence_grade"], "Missing")

    def test_weak_unresolved_character_virtual_battle_is_hold(self) -> None:
        row = {
            "post_id": 11663540,
            "title": "TS) 주서연 전차랑 줄다리기 하면 이길까?",
            "content": ["내가 봤을땐 이 고릴라년이 가볍게 이길것 같은데"],
            "comments": ["전차 주제에 주서연이랑 비비려하네"],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": None,
                    "discussion_type": "character_talk",
                    "topicality": "core_relevant",
                    "work_resolution": "unresolved",
                    "identity_state": "unresolved_title",
                    "anchor_type": "none",
                    "anchor_strength": "none",
                    "reason": (
                        "[판정 요약] - 판정: 관련(정식 제목 미확정) "
                        "[근거 요약] - grounding_anchor: none - "
                        "evidence_bucket: post_spans=1, search_snippets=0, official_urls=0 "
                        "[근거 스코어] - executed_queries: 14 - degraded_queries: 14"
                    ),
                    "context_sources": ["title", "body", "comments", "search"],
                }
            },
            "run_meta": {"run_id": "test", "worker_id": 2},
        }

        facts = self.round2.extract_facts(1, row)
        with TemporaryDirectory() as tmp:
            packet = self.round2.build_packet("T-0001", "round3_targeted_after", facts, Path(tmp) / "result.json")
        label = self.round2.review_label(packet, facts)

        self.assertEqual(label["label"], "HOLD")
        self.assertEqual(label["action"], "re_judge")
        self.assertEqual(label["evidence_grade"], "Weak")
        self.assertIn("weak_unresolved_boundary", label["boundary_risk"])
        self.assertIn("character_virtual_battle", label["boundary_risk"])

    def test_generic_bridge_non_relevant_title_null_is_accept(self) -> None:
        row = {
            "post_id": 8531521,
            "title": "강연금 알렉형제는 강한편이긴 한데",
            "content": ["상대적으로 좆밥같아보임"],
            "comments": ["요즘 이타도리보단 낫지"],
            "analysis_result": {
                "identity": {
                    "is_relevant": False,
                    "novel_identity": None,
                    "discussion_type": "noise",
                    "topicality": "unrelated",
                    "work_resolution": "none",
                    "identity_state": "none",
                    "reason": (
                        "[판정 요약] - 판정: 비관련 "
                        "[근거 요약] - evidence_bucket: post_spans=0, search_snippets=0, official_urls=0"
                    ),
                    "context_sources": ["title", "body", "comments", "search"],
                }
            },
            "run_meta": {"run_id": "test", "worker_id": 4},
        }

        facts = self.round2.extract_facts(1, row)
        with TemporaryDirectory() as tmp:
            packet = self.round2.build_packet("T-0002", "generic_parenthetical_bridge", facts, Path(tmp) / "result.json")
        label = self.round2.review_label(packet, facts)

        self.assertEqual(label["label"], "ACCEPT")
        self.assertEqual(label["action"], "no_action")
        self.assertIn("generic_term", label["boundary_risk"])

    def test_generic_bridge_with_direct_official_evidence_is_accept(self) -> None:
        row = {
            "post_id": 11113480,
            "title": "카드아카 190화까지 보고 왔다",
            "content": ["이우주랑 전익현 이야기"],
            "comments": ["작품 감상"],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "카드 아카데미 1타강사",
                        "heretic_url": "https://page.kakao.com/content/58517213?tab_type=about",
                        "confidence": "High",
                    },
                    "primary_work": {
                        "official_title": "카드 아카데미 1타강사",
                        "heretic_url": "https://page.kakao.com/content/58517213?tab_type=about",
                        "source_tier": "official_detail",
                    },
                    "discussion_type": "character_talk",
                    "topicality": "core_relevant",
                    "work_resolution": "resolved",
                    "identity_state": "resolved_title",
                    "reason": (
                        "[근거 요약] - official_title_evidence: true - title_in_post: true "
                        "- evidence_bucket: post_spans=2, search_snippets=4, official_urls=1 "
                        "[근거 스코어] - executed_queries: 4 - degraded_queries: 0"
                    ),
                    "context_sources": ["title", "body", "comments", "search"],
                }
            },
            "run_meta": {"run_id": "test", "worker_id": 1},
        }

        facts = self.round2.extract_facts(1, row)
        with TemporaryDirectory() as tmp:
            packet = self.round2.build_packet("T-0003", "generic_parenthetical_bridge", facts, Path(tmp) / "result.json")
        label = self.round2.review_label(packet, facts)

        self.assertEqual(label["label"], "ACCEPT")
        self.assertEqual(label["action"], "no_action")
        self.assertEqual(label["evidence_grade"], "Strong")

    def test_generic_bridge_ignores_explanatory_reason_parentheses(self) -> None:
        row = {
            "post_id": 11718099,
            "title": "빌환 표지변경됨",
            "content": ["시엘이랑 세냐 빼고 아니스티나랑 매르만 있어도 된다는 말은 ㄴㄴ"],
            "comments": [],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "빌어먹을 환생",
                        "heretic_url": "https://novel.munpia.com/222360",
                        "confidence": "High",
                    },
                    "primary_work": {
                        "official_title": "빌어먹을 환생",
                        "heretic_url": "https://novel.munpia.com/222360",
                        "source_tier": "official_detail",
                    },
                    "slang_insight": {
                        "detected_term": "빌환",
                        "decoded_term": "빌어먹을 환생",
                        "alias_scope": "pure_work_alias",
                        "store_reason": "pure_work_alias",
                    },
                    "discussion_type": "character_talk",
                    "topicality": "core_relevant",
                    "work_resolution": "resolved",
                    "identity_state": "resolved_title",
                    "reason": (
                        "[근거 요약] - grounding_anchor: title_abbrev_mention "
                        "- official_title_evidence: true - title_in_post: false "
                        "- evidence_bucket: post_spans=0, search_snippets=27, official_urls=3 "
                        "- 검증 반론(참고): 본문 내용(이미지 요약)은 작품의 설정(캐릭터 구성, 장르)을 담고 있으나 "
                        "최종 제목 근거로 사용하지 않음. "
                        "[근거 스코어] - executed_queries: 6 - degraded_queries: 0"
                    ),
                    "context_sources": ["title", "body", "search", "image"],
                }
            },
            "run_meta": {"run_id": "test", "worker_id": 1},
        }

        facts = self.round2.extract_facts(1, row)

        self.assertFalse(facts["generic_bridge"])
        self.assertNotIn("generic_parenthetical_bridge", facts["bucket_reasons"])
        self.assertTrue(facts["strong_title_alias_or_direct_evidence"])

    def test_round2_accepts_blocked_ocr_surface_when_official_detail_resolves_title(self) -> None:
        row = {
            "post_id": 11718082,
            "title": "이게 백합 소설이 아니라니...",
            "content": ["이미지 OCR: 재벌가 차녀의 2회차 결그룹 유은우 267화 KAKAO PAGE"],
            "comments": [],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "재벌가 차녀의 2회차 걸그룹",
                        "heretic_url": "https://page.kakao.com/content/66692543",
                        "confidence": "High",
                    },
                    "primary_work": {
                        "official_title": "재벌가 차녀의 2회차 걸그룹",
                        "heretic_url": "https://page.kakao.com/content/66692543",
                        "source_tier": "official_detail",
                        "locked": True,
                    },
                    "slang_insight": {
                        "detected_term": "재벌가 차녀의 2회차 결그룹",
                        "decoded_term": "재벌가 차녀의 2회차 걸그룹",
                        "alias_scope": "work_plus_character",
                        "store_in_slang_db": False,
                        "store_reason": "character_attached_composite",
                    },
                    "image_evidence_catalog": [
                        {
                            "explicit_work_title": "재벌가 차녀의 2회차 결그룹",
                            "explicit_author_name": "유은우",
                            "promotion_eligible": True,
                            "source_url": "https://dcimg7.dcinside.co.kr/viewimage.php?id=x",
                        }
                    ],
                    "discussion_type": "character_talk",
                    "topicality": "core_relevant",
                    "work_resolution": "resolved",
                    "identity_state": "resolved_title",
                    "consistency_flags": [
                        "official_detail_title_preferred_over_surface_form",
                        "surface_form_duplicate_reference_pruned",
                    ],
                    "reason": (
                        "[근거 요약] - official_title_evidence: true - title_in_post: true "
                        "- evidence_bucket: post_spans=2, search_snippets=8, official_urls=1 "
                        "이미지 OCR/표지 후보가 최종 제목과 일치하지 않아 보조 제목 근거로 사용하지 않습니다."
                    ),
                    "context_sources": ["title", "body", "search", "image"],
                }
            },
            "run_meta": {"run_id": "test", "worker_id": 1},
        }

        facts = self.round2.extract_facts(1, row)
        packet = self.round2.build_packet("R2-SLANG-OCR-CLOSED", "slang_db_store_block_pending_family_noise", facts, Path("result.json"))
        label = self.round2.review_label(packet, facts)

        self.assertIn("slang_db_store_block_pending_family_noise", facts["bucket_reasons"])
        self.assertEqual(label["label"], "ACCEPT")
        self.assertEqual(label["action"], "no_action")
        self.assertIn("slang_db_subtype_closed", label["boundary_risk"])
        self.assertNotIn("slang_db_subtype", label["boundary_risk"])

    def test_degraded_queries_zero_does_not_mark_search_degraded(self) -> None:
        row = {
            "post_id": 11113480,
            "title": "카드아카 190화까지 보고 왔다",
            "content": ["이우주랑 전익현 이야기"],
            "comments": ["작품 감상"],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "카드 아카데미 1타강사",
                        "heretic_url": "https://page.kakao.com/content/58517213?tab_type=about",
                        "confidence": "High",
                    },
                    "primary_work": {
                        "official_title": "카드 아카데미 1타강사",
                        "heretic_url": "https://page.kakao.com/content/58517213?tab_type=about",
                        "source_tier": "official_detail",
                    },
                    "discussion_type": "character_talk",
                    "topicality": "core_relevant",
                    "work_resolution": "resolved",
                    "identity_state": "resolved_title",
                    "reason": (
                        "[근거 요약] - official_title_evidence: true - title_in_post: true "
                        "- evidence_bucket: post_spans=2, search_snippets=4, official_urls=1 "
                        "[근거 스코어] - executed_queries: 4 - degraded_queries: 0"
                    ),
                    "context_sources": ["title", "body", "comments", "search"],
                }
            },
            "run_meta": {"run_id": "test", "worker_id": 1},
        }

        facts = self.round2.extract_facts(1, row)

        self.assertFalse(facts["search_degraded"])
        self.assertFalse(facts["degraded_majority"])

    def test_round3_after_target_map_falls_back_to_base_packet_and_pattern_bucket(self) -> None:
        with TemporaryDirectory() as tmp:
            target_path = Path(tmp) / "target.jsonl"
            target_path.write_text(
                (
                    '{"post_id": 10365476, "title": "generic target", '
                    '"content": ["body"], "comments": ["comment"], '
                    '"_round3_target": {'
                    '"base_packet_id": "R3A-0101", '
                    '"primary_pattern": "generic_common_surface", '
                    '"patterns": ["generic_common_surface"], '
                    '"label": "HOLD", "action": "re_judge"'
                    "}}\n"
                ),
                encoding="utf-8",
            )

            targets = self.round3_after.target_map(target_path)

        target = targets["10365476"]
        self.assertEqual(target["packet_id"], "R3A-0101")
        self.assertEqual(target["bucket"], "generic_common_surface")
        self.assertEqual(target["primary_pattern"], "generic_common_surface")

    def test_current_remaining_action_inputs_split_rerun_review_and_browser_targets(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            review_dir = root / "review"
            review_dir.mkdir()
            source_path = root / "result.json"
            remaining_path = review_dir / "remaining.jsonl"
            source_path.write_text(
                (
                    '[{"post_id": 1, "url": "u1", "title": "t1", "content": ["b1"], "comments": []}, '
                    '{"post_id": 2, "url": "u2", "title": "t2", "content": [], "comments": ["c2"]}, '
                    '{"post_id": 3, "url": "u3", "title": "t3", "content": [], "comments": []}]'
                ),
                encoding="utf-8",
            )
            remaining_path.write_text(
                "\n".join(
                    [
                        '{"post_id": 1, "final_action": "re_search", "final_label": "HOLD", "primary_pattern": "worker_shard_degraded_window"}',
                        '{"post_id": 2, "final_action": "slang_db_review", "final_label": "HOLD", "primary_pattern": "slang_db_alias_subtype"}',
                        '{"post_id": 3, "final_action": "re_run", "final_label": "REPROCESS", "primary_pattern": "vlm_ocr_evidence_gap"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            manifest = self.current_remaining.build_action_inputs(
                review_dir,
                remaining_path,
                source_path,
                "current",
            )

            self.assertEqual(manifest["remaining_rows"], 3)
            self.assertEqual(manifest["rerun_input_counts"]["re_search"], 1)
            self.assertEqual(manifest["rerun_input_counts"]["re_run"], 1)
            self.assertEqual(manifest["review_packet_counts"]["slang_db_review"], 1)
            self.assertEqual(manifest["browser_target_rows"], 1)
            self.assertEqual(manifest["rerun_combined_rows"], 2)
            self.assertFalse(manifest["missing_post_ids"])

    def test_current_remaining_action_inputs_outputs_docs_issue_and_slang_fields(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            review_dir = root / "review"
            review_dir.mkdir()
            source_path = root / "result.json"
            remaining_path = review_dir / "remaining.jsonl"
            source_path.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 10,
                            "url": "u10",
                            "title": "slang candidate",
                            "content": ["body"],
                            "comments": [],
                            "analysis_result": {
                                "identity": {
                                    "is_relevant": True,
                                    "reason": "alias candidate",
                                    "work_resolution": "resolved",
                                    "identity_state": "resolved_title",
                                    "novel_identity": {"official_title": "Work A"},
                                    "slang_insight": {
                                        "detected_term": "alias-a",
                                        "decoded_term": "alias-a",
                                        "store_in_slang_db": False,
                                    },
                                }
                            },
                        },
                        {
                            "post_id": 11,
                            "url": "u11",
                            "title": "missing slang fields",
                            "content": ["body"],
                            "comments": [],
                            "analysis_result": {"identity": {"is_relevant": True}},
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            remaining_path.write_text(
                "\n".join(
                    [
                        '{"post_id": 10, "final_action": "slang_db_review", "final_label": "HOLD", "primary_pattern": "slang_db_alias_subtype"}',
                        '{"post_id": 11, "final_action": "docs_issue", "final_label": "INFO_MISSING", "primary_pattern": "slang_db_alias_subtype"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            manifest = self.current_remaining.build_action_inputs(
                review_dir,
                remaining_path,
                source_path,
                "current",
            )
            slang_packets = self.current_remaining.load_jsonl(review_dir / "current_slang_db_review_packets.jsonl")
            docs_packets = self.current_remaining.load_jsonl(review_dir / "current_docs_issue_packets.jsonl")

            self.assertEqual(manifest["review_packet_counts"]["slang_db_review"], 1)
            self.assertEqual(manifest["review_packet_counts"]["docs_issue"], 1)
            self.assertEqual(slang_packets[0]["slang_db_fields"]["detected_term"], "alias-a")
            self.assertFalse(slang_packets[0]["slang_db_fields"]["store_in_slang_db"])
            self.assertEqual(slang_packets[0]["final_decision_fields"]["official_title"], "Work A")
            self.assertEqual(slang_packets[0]["reason"], "alias candidate")
            self.assertEqual(docs_packets[0]["final_action"], "docs_issue")

    def test_current_remaining_action_inputs_accepts_round2_action_queue_json(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            review_dir = root / "review"
            review_dir.mkdir()
            source_path = root / "result.json"
            queue_path = review_dir / "action_queue.json"
            source_path.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11718082,
                            "url": "u-image",
                            "title": "image post",
                            "content": ["body"],
                            "content_blocks": [{"type": "image", "url": "https://dcimg.example/a.jpg"}],
                            "image_urls": ["https://dcimg.example/a.jpg"],
                            "image_count": 1,
                            "comments": [],
                        },
                        {
                            "post_id": 11718080,
                            "url": "u-rejudge",
                            "title": "소설 보는 친구 있으면 좋음",
                            "content": ["밥 먹는데 소설 얘기할 친구가 있으면 좋겠다는 한탄"],
                            "comments": [],
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (review_dir / "review_packets.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "packet_id": "RC3-0001",
                                "post_id": 11718082,
                                "bucket": "random_control",
                                "risk_tags": ["image_evidence_catalog_missing"],
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "packet_id": "RC3-0002",
                                "post_id": 11718080,
                                "bucket": "random_control",
                                "risk_tags": ["reason_says_no_anchor_but_resolved"],
                                "resolved_title": "소보로설",
                                "relevance": True,
                            },
                            ensure_ascii=False,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (review_dir / "review_labels.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "packet_id": "RC3-0001",
                                "bucket": "random_control",
                                "applied_review_bucket": "image_evidence_catalog_missing",
                                "boundary_risk": ["image_evidence_catalog_missing"],
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "packet_id": "RC3-0002",
                                "bucket": "random_control",
                                "applied_review_bucket": "reason_says_no_anchor_but_resolved",
                                "boundary_risk": ["no_anchor_resolved"],
                            },
                            ensure_ascii=False,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            queue_path.write_text(
                json.dumps(
                    [
                        {
                            "priority": "P1",
                            "packet_id": "RC3-0001",
                            "post_id": 11718082,
                            "bucket": "random_control",
                            "label": "REPROCESS",
                            "action": "human_review",
                            "evidence_grade": "Weak",
                            "rationale": "이미지 근거 누락",
                        },
                        {
                            "priority": "P0/P1",
                            "packet_id": "RC3-0002",
                            "post_id": 11718080,
                            "bucket": "random_control",
                            "label": "REJECT",
                            "action": "re_judge",
                            "evidence_grade": "Weak",
                            "rationale": "no-anchor resolved",
                        },
                        {
                            "priority": "P0/P1",
                            "packet_id": "R2-0002",
                            "post_id": 11718080,
                            "bucket": "batch_memory_exact_alias_rescued_no_anchor",
                            "label": "REJECT",
                            "action": "slang_db_review",
                            "evidence_grade": "Weak",
                            "rationale": "batch memory alias review",
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            manifest = self.current_remaining.build_action_inputs(
                review_dir,
                queue_path,
                source_path,
                "v263",
            )
            browser_targets = self.current_remaining.load_jsonl(review_dir / "v263_browser_targets.jsonl")
            rejudge_inputs = self.current_remaining.load_jsonl(review_dir / "v263_re_judge_input.jsonl")

        self.assertEqual(manifest["remaining_rows"], 3)
        self.assertEqual(manifest["unique_remaining_rows"], 2)
        self.assertEqual(manifest["rerun_input_counts"]["re_judge"], 1)
        self.assertEqual(manifest["review_packet_counts"]["slang_db_review"], 1)
        self.assertEqual(manifest["browser_target_rows"], 1)
        self.assertEqual(manifest["duplicate_post_ids_removed"], ["11718080"])
        self.assertFalse(manifest["image_source_missing_post_ids"])
        self.assertEqual(browser_targets[0]["post_id"], 11718082)
        self.assertEqual(browser_targets[0]["image_urls"], ["https://dcimg.example/a.jpg"])
        self.assertEqual(rejudge_inputs[0]["_round3_target"]["primary_pattern"], "reason_says_no_anchor_but_resolved")
        self.assertEqual(rejudge_inputs[0]["_issue_regression"]["previous_resolved_title"], "소보로설")
        self.assertEqual(manifest["execution_contract"]["current_rerun_input_count"], 1)
        self.assertEqual(manifest["execution_contract"]["recommended_parallel_for_current_inputs"], 16)
        self.assertEqual(manifest["execution_contract"]["expected_effective_parallel_for_current_inputs"], 1)
        self.assertIn("--parallel 16", manifest["execution_contract"]["required_flags"])
        self.assertNotIn("--no-dashboard", manifest["execution_contract"]["required_flags"])
        self.assertEqual(
            manifest["execution_contract"]["dashboard_contract"]["dashboard_policy"],
            "WEB_DASHBOARD_REQUIRED_FOR_TEST_RUNS",
        )
        self.assertNotIn("MCP_SHARD_COUNT", manifest["execution_contract"])

    def test_current_remaining_action_inputs_locks_requested_parallel_at_16(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            review_dir = root / "review"
            review_dir.mkdir()
            source_path = root / "source.json"
            queue_path = review_dir / "action_queue.json"
            source_rows = [
                {
                    "post_id": 20000000 + idx,
                    "title": f"대량 재판정 후보 {idx}",
                    "content": [f"본문 {idx}"],
                    "analysis_result": {"identity": {"is_relevant": False}},
                }
                for idx in range(37)
            ]
            queue_rows = [
                {
                    "packet_id": f"RC3-{idx:04d}",
                    "post_id": 20000000 + idx,
                    "label": "HOLD",
                    "action": "re_judge",
                    "evidence_grade": "Weak",
                    "rationale": "대량 boundary cap 회귀",
                }
                for idx in range(37)
            ]
            source_path.write_text(json.dumps(source_rows, ensure_ascii=False), encoding="utf-8")
            queue_path.write_text(json.dumps(queue_rows, ensure_ascii=False), encoding="utf-8")

            manifest = self.current_remaining.build_action_inputs(
                review_dir,
                queue_path,
                source_path,
                "v264",
            )

        self.assertEqual(manifest["rerun_combined_rows"], 37)
        self.assertEqual(manifest["execution_contract"]["current_rerun_input_count"], 37)
        self.assertEqual(manifest["execution_contract"]["expert_main_parallel_max"], 36)
        self.assertEqual(manifest["execution_contract"]["recommended_parallel_for_current_inputs"], 16)
        self.assertEqual(manifest["execution_contract"]["expected_effective_parallel_for_current_inputs"], 16)
        self.assertIn("--parallel 16", manifest["execution_contract"]["required_flags"])
        self.assertNotIn("--no-dashboard", manifest["execution_contract"]["required_flags"])

    def test_current_remaining_action_inputs_loads_jsonl_source_with_comments_and_images(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            review_dir = root / "review"
            review_dir.mkdir()
            source_path = root / "input.jsonl"
            queue_path = review_dir / "action_queue.json"
            source_rows = [
                {
                    "post_id": 11718082,
                    "url": "u-image",
                    "title": "image post",
                    "content_blocks": [{"type": "image", "url": "https://dcimg.example/a.jpg"}],
                    "comments": [],
                },
                {
                    "comment_id": "c1",
                    "post_id": 11718082,
                    "author": "ㅇㅇ",
                    "ip": "1.2",
                    "content": "댓글 맥락",
                },
            ]
            source_path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in source_rows) + "\n",
                encoding="utf-8",
            )
            queue_path.write_text(
                json.dumps(
                    [
                        {
                            "packet_id": "RC3-0001",
                            "post_id": 11718082,
                            "label": "REPROCESS",
                            "action": "human_review",
                            "evidence_grade": "Weak",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (review_dir / "review_labels.jsonl").write_text(
                json.dumps(
                    {
                        "packet_id": "RC3-0001",
                        "bucket": "random_control",
                        "applied_review_bucket": "image_evidence_catalog_missing",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            manifest = self.current_remaining.build_action_inputs(
                review_dir,
                queue_path,
                source_path,
                "vjsonl",
            )
            browser_targets = self.current_remaining.load_jsonl(review_dir / "vjsonl_browser_targets.jsonl")

        self.assertEqual(manifest["browser_target_rows"], 1)
        self.assertFalse(manifest["image_source_missing_post_ids"])
        self.assertEqual(browser_targets[0]["image_urls"], [])
        self.assertEqual(browser_targets[0]["content_blocks"], [{"type": "image", "url": "https://dcimg.example/a.jpg"}])
        self.assertIn("댓글 맥락", browser_targets[0]["comment_excerpt"])

    def test_slang_status_review_splits_followup_actions(self) -> None:
        with TemporaryDirectory() as tmp:
            review_dir = Path(tmp)
            manual_path = review_dir / "manual.jsonl"
            packet_path = review_dir / "packets.jsonl"
            manual_path.write_text(
                "\n".join(
                    json.dumps(row, ensure_ascii=False)
                    for row in [
                        {
                            "post_id": 1,
                            "closure_action": "slang_db_review",
                            "current_label": "HOLD",
                            "current_evidence_grade": "Weak",
                            "primary_pattern": "slang_db_alias_subtype",
                            "title": "blocked",
                            "slang_db_review": {
                                "status": "blocked_by_result_contract",
                                "terms": ["정식제목"],
                                "store_in_slang_db": False,
                                "store_reason": "exact_title_not_alias",
                                "term_states": {"정식제목": "repo:title_key"},
                            },
                        },
                        {
                            "post_id": 2,
                            "closure_action": "slang_db_review",
                            "current_label": "HOLD",
                            "current_evidence_grade": "Weak",
                            "primary_pattern": "slang_db_alias_subtype",
                            "title": "gap",
                            "slang_db_review": {
                                "status": "extracted_not_persisted",
                                "terms": ["신규약칭"],
                                "store_in_slang_db": True,
                                "store_reason": "pure_work_alias",
                                "term_states": {"신규약칭": "not_found"},
                            },
                        },
                        {
                            "post_id": 3,
                            "closure_action": "slang_db_review",
                            "current_label": "HOLD",
                            "current_evidence_grade": "Medium",
                            "primary_pattern": "slang_db_alias_subtype",
                            "title": "conflict",
                            "slang_db_review": {
                                "status": "persisted_conflict",
                                "terms": ["conflict-alias"],
                                "store_in_slang_db": True,
                                "store_reason": "pure_work_alias",
                                "term_states": {"conflict-alias": "repo:conflict"},
                            },
                        },
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            packet_path.write_text(
                "\n".join(
                    json.dumps(row, ensure_ascii=False)
                    for row in [
                        {"post_id": 1, "title": "blocked", "slang_db_fields": {"detected_term": "정식제목"}},
                        {"post_id": 2, "title": "gap", "slang_db_fields": {"detected_term": "신규약칭"}},
                        {"post_id": 3, "title": "conflict", "slang_db_fields": {"detected_term": "conflict-alias"}},
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            manifest = self.slang_status_review.build_slang_status_review(
                review_dir,
                manual_path,
                packet_path,
                "status",
            )
            labels = self.slang_status_review.load_jsonl(review_dir / "status_labels.jsonl")
            packets = self.slang_status_review.load_jsonl(review_dir / "status_packets.jsonl")

            self.assertEqual(manifest["total_rows"], 3)
            self.assertEqual(manifest["status_counts"]["blocked_by_result_contract"], 1)
            self.assertEqual(manifest["status_counts"]["extracted_not_persisted"], 1)
            self.assertEqual(manifest["status_counts"]["persisted_conflict"], 1)
            self.assertEqual(
                manifest["followup_action_counts"]["confirm_block_reason_and_recall_impact"],
                1,
            )
            self.assertEqual(manifest["followup_action_counts"]["investigate_persistence_gap"], 1)
            self.assertEqual(manifest["followup_action_counts"]["resolve_conflicting_alias"], 1)
            by_post = {row["post_id"]: row for row in labels}
            self.assertEqual(by_post[1]["label"], "HOLD")
            self.assertEqual(by_post[2]["label"], "REPROCESS")
            self.assertEqual(by_post[3]["label"], "HOLD")
            self.assertEqual(packets[0]["packet_id"], "STATUS-0001")
            self.assertTrue((review_dir / "status_blocked_by_result_contract_packets.jsonl").exists())
            self.assertTrue((review_dir / "status_extracted_not_persisted_packets.jsonl").exists())
            self.assertTrue((review_dir / "status_persisted_conflict_packets.jsonl").exists())

    def test_generic_bridge_with_direct_evidence_but_degraded_search_routes_to_re_search(self) -> None:
        row = {
            "post_id": 11113480,
            "title": "카드아카 190화까지 보고 왔다",
            "content": ["이우주랑 전익현 이야기"],
            "comments": ["작품 감상"],
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "카드 아카데미 1타강사",
                        "heretic_url": "https://page.kakao.com/content/58517213?tab_type=about",
                        "confidence": "High",
                    },
                    "primary_work": {
                        "official_title": "카드 아카데미 1타강사",
                        "heretic_url": "https://page.kakao.com/content/58517213?tab_type=about",
                        "source_tier": "official_detail",
                    },
                    "discussion_type": "character_talk",
                    "topicality": "core_relevant",
                    "work_resolution": "resolved",
                    "identity_state": "resolved_title",
                    "reason": (
                        "[근거 요약] - official_title_evidence: true - title_in_post: true "
                        "- evidence_bucket: post_spans=2, search_snippets=4, official_urls=1 "
                        "[근거 스코어] - executed_queries: 6 - degraded_queries: 4"
                    ),
                    "context_sources": ["title", "body", "comments", "search"],
                }
            },
            "run_meta": {"run_id": "test", "worker_id": 1},
        }

        facts = self.round2.extract_facts(1, row)
        with TemporaryDirectory() as tmp:
            packet = self.round2.build_packet("T-0004", "generic_parenthetical_bridge", facts, Path(tmp) / "result.json")
        label = self.round2.review_label(packet, facts)

        self.assertEqual(label["label"], "HOLD")
        self.assertEqual(label["action"], "re_search")
        self.assertIn("search_degraded", label["boundary_risk"])

    def test_v78_vlm_relabel_keeps_strong_image_gate_as_human_review_until_semantic_review(self) -> None:
        target = {
            "post_id": 9531764,
            "title": "배달음식은 예전에는 많이 먹었는데 요즘은 절대 못먹겠음",
            "body_excerpt": "돈 존나 쭉쭉 빠지더라",
            "final_decision_fields": {"is_relevant": False, "official_title": None},
            "reason": "일상 잡담으로 판정했다.",
            "final_label": "REPROCESS",
            "final_action": "re_run",
            "primary_pattern": "vlm_ocr_evidence_gap",
            "patterns": ["vlm_ocr_evidence_gap"],
        }
        iab = {
            "post_id": 9531764,
            "visual_evidence_grade": "Strong",
            "screenshot_path": "screenshots/9531764.png",
            "image_gate": {"imageGatePass": True, "visual_evidence_grade": "Strong"},
            "final_image_state": {
                "articleImageCount": 1,
                "articleLoadedCount": 1,
                "articlePlaceholderCount": 0,
                "articleIncompleteCount": 0,
                "articleBrokenCount": 0,
            },
        }

        _packet, label = self.v78_vlm_relabel.relabel_target(1, target, iab, None)

        self.assertEqual(label["label"], "HOLD")
        self.assertEqual(label["action"], "human_review")
        self.assertEqual(label["image_gate_grade"], "Strong")
        self.assertEqual(label["transition"], "REPROCESS->HOLD")
        packet, _label = self.v78_vlm_relabel.relabel_target(1, target, iab, None)
        self.assertEqual(packet["final_decision_fields"], {"is_relevant": False, "official_title": None})
        self.assertEqual(packet["reason"], "일상 잡담으로 판정했다.")

    def test_v78_vlm_relabel_does_not_trust_explicit_gate_when_lazy_pending_remains(self) -> None:
        target = {
            "post_id": 11097334,
            "title": "허억 오크노디 초비상!!!!",
            "final_label": "REPROCESS",
            "final_action": "re_run",
            "primary_pattern": "vlm_ocr_evidence_gap",
            "patterns": ["vlm_ocr_evidence_gap"],
        }
        iab = {
            "post_id": 11097334,
            "visual_evidence_grade": "Strong",
            "image_gate": {"imageGatePass": True, "visual_evidence_grade": "Strong"},
            "final_image_state": {
                "articleImageCount": 3,
                "articleLoadedCount": 3,
                "articlePlaceholderCount": 0,
                "articleIncompleteCount": 0,
                "articleBrokenCount": 0,
                "articleLazyPendingCount": 1,
                "dataOriginalPendingCount": 1,
                "placeholderCurrentSrcCount": 1,
                "articleAttachmentFileCount": 1,
                "articleAttachmentLinks": [{"text": "원본.gif", "href": "https://image.example/viewimagePop.php"}],
            },
        }

        packet, label = self.v78_vlm_relabel.relabel_target(1, target, iab, None)

        self.assertEqual(label["label"], "INFO_MISSING")
        self.assertEqual(label["action"], "human_review")
        self.assertEqual(label["evidence_grade"], "Weak")
        self.assertFalse(label["image_gate_pass"])
        self.assertEqual(packet["image_gate"]["article_lazy_pending_count"], 1)
        self.assertEqual(packet["image_gate"]["data_original_pending_count"], 1)
        self.assertEqual(packet["image_gate"]["placeholder_current_src_count"], 1)
        self.assertEqual(packet["image_gate"]["article_attachment_file_count"], 1)
        self.assertEqual(packet["image_gate"]["article_attachment_links"][0]["text"], "원본.gif")

    def test_capture_vlm_browser_grade_treats_data_original_pending_as_weak(self) -> None:
        grade = self.capture_vlm_browser.evidence_grade(
            title="허억 오크노디 초비상!!!!",
            body_text="본문 텍스트",
            target_title="허억 오크노디 초비상!!!!",
            post_id=11097334,
            screenshot_ok=True,
            blocked_signals=[],
            open_return_code=0,
            eval_return_code=0,
            article_image_count=3,
            article_loaded_count=3,
            article_incomplete_count=0,
            article_placeholder_count=0,
            article_broken_count=0,
            article_lazy_pending_count=1,
            data_original_pending_count=1,
            placeholder_current_src_count=1,
        )

        self.assertEqual(grade, "Weak")

    def test_v78_vlm_relabel_allows_manual_browser_review_accept_for_single_row(self) -> None:
        target = {
            "post_id": 9531764,
            "title": "배달음식은 예전에는 많이 먹었는데 요즘은 절대 못먹겠음",
            "final_label": "REPROCESS",
            "final_action": "re_run",
            "primary_pattern": "vlm_ocr_evidence_gap",
            "patterns": ["vlm_ocr_evidence_gap"],
        }
        iab = {
            "post_id": 9531764,
            "visual_evidence_grade": "Strong",
            "image_gate": {"imageGatePass": True, "visual_evidence_grade": "Strong"},
            "final_image_state": {"articleImageCount": 1, "articleLoadedCount": 1},
        }
        manual = {
            "post_id": 9531764,
            "_manual_review_path": "manual.json",
            "visual_evidence": {
                "article_image_loading_grade": "Strong",
                "image_semantic_support_grade": "Weak",
            },
            "semantic_review": {
                "final_review_label": "ACCEPT",
                "action": "no_action",
                "approval_scope": "단건 false/null 판정과 이미지 로딩 상태가 정합적이다.",
            },
        }

        _packet, label = self.v78_vlm_relabel.relabel_target(1, target, iab, manual)

        self.assertEqual(label["label"], "ACCEPT")
        self.assertEqual(label["action"], "no_action")
        self.assertEqual(label["evidence_grade"], "Medium")
        self.assertEqual(label["transition"], "REPROCESS->ACCEPT")


if __name__ == "__main__":
    unittest.main()
