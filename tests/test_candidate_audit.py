import json
import tempfile
import unittest
from pathlib import Path

from llm_batch.grounding.candidate_audit import (
    apply_author_angle_official_detail_canonicalization,
    apply_candidate_audit_fields,
    apply_comment_surface_candidate_hints,
    apply_judge_seed_expected_candidate_preservation,
    apply_judge_seed_hygiene_alias_conflict_guard,
    apply_judge_seed_hygiene_expected_title_guard,
    apply_judge_seed_precision_guard,
    apply_judge_seed_title_image_mismatch_guard,
    apply_judge_seed_title_hygiene_guard,
    apply_judge_seed_trope_boundary_hold_guard,
    apply_judge_seed_unverified_ocr_title_guard,
    apply_judge_seed_wrong_relevance_public_title_guard,
    apply_official_title_promotion_guard,
    apply_post_surface_candidate_hints,
    apply_weak_public_title_bridge_guard,
    build_candidate_audit_fields,
    official_url_recoverable,
)
from tools.build_judge3905_source_enriched_canary import build_source_enriched_canary


class CandidateAuditTest(unittest.TestCase):
    def test_official_url_recall_promotes_search_detail_with_direct_title_clue(self):
        identity = {
            "work_resolution": "unresolved",
            "title_resolution_state": "unresolved_matchable",
            "post_side_text": "괴담 호텔 탈출기 최신화 후기",
            "post_core_text": "괴담 호텔 탈출기 최신화 후기",
            "search_evidence_catalog": [
                {
                    "title": "괴담 호텔 탈출기",
                    "url": "https://novelpia.com/novel/102155",
                    "source_tier": "official_detail",
                }
            ],
        }

        recovered = official_url_recoverable(identity)

        self.assertIsNotNone(recovered)
        self.assertEqual(recovered["official_title"], "괴담 호텔 탈출기")
        self.assertEqual(recovered["heretic_url"], "https://novelpia.com/novel/102155")
        self.assertEqual(recovered["matched_clue"], "full_title_surface")

    def test_official_url_recall_normalizes_munpia_mobile_detail_query(self):
        identity = {
            "work_resolution": "unresolved",
            "title_resolution_state": "ocr_explicit_title_unresolved",
            "post_side_text": "문피아가 밀어주나보네",
            "post_core_text": "문피아가 밀어주나보네",
            "image_evidence_catalog": [
                {
                    "explicit_work_title": "잠들지 못하는 밤의 추적자",
                    "title_role": "work_title",
                    "promotion_eligible": True,
                }
            ],
            "search_evidence_catalog": [
                {
                    "title": "잠들지 못하는 밤의 추적자 - 문피아 웹소설",
                    "url": "http://mm.munpia.com/?menu=novel&id=525712",
                    "source_tier": "novel_platform",
                }
            ],
        }

        recovered = official_url_recoverable(identity)

        self.assertIsNotNone(recovered)
        self.assertEqual(recovered["official_title"], "잠들지 못하는 밤의 추적자")
        self.assertEqual(recovered["heretic_url"], "https://m.munpia.com/novel/detail/525712")
        self.assertEqual(recovered["matched_clue"], "ocr_explicit_title")

    def test_official_url_recall_blocks_genre_descriptor_surface_on_weak_anchor(self):
        # A post that merely contains a genre/descriptor surface ("ts인방물") must NOT
        # be promoted to the same-named work via full_title_surface — the post is using
        # it as a genre word, not a specific-work reference (precision leak guard).
        identity = {
            "work_resolution": "unresolved",
            "title_resolution_state": "unresolved_matchable",
            "post_side_text": "고능아보면 ts인방물도 결국 재능임",
            "post_core_text": "고능아보면 ts인방물도 결국 재능임",
            "search_evidence_catalog": [
                {
                    "title": "ts인방물",
                    "url": "https://novelpia.com/novel/94786",
                    "source_tier": "novel_platform",
                }
            ],
        }

        self.assertIsNone(official_url_recoverable(identity))

    def test_official_url_recall_allows_genre_named_work_via_ocr_strong_anchor(self):
        # A genre-ish title is still recoverable when a HARD anchor (OCR explicit
        # work-title screenshot) ties the post to that specific work.
        identity = {
            "work_resolution": "unresolved",
            "title_resolution_state": "ocr_explicit_title_unresolved",
            "post_side_text": "이거 표지 보고 바로 읽음",
            "post_core_text": "이거 표지 보고 바로 읽음",
            "image_evidence_catalog": [
                {
                    "explicit_work_title": "ts인방물",
                    "title_role": "work_title",
                    "promotion_eligible": True,
                }
            ],
            "search_evidence_catalog": [
                {
                    "title": "ts인방물",
                    "url": "https://novelpia.com/novel/94786",
                    "source_tier": "novel_platform",
                }
            ],
        }

        recovered = official_url_recoverable(identity)

        self.assertIsNotNone(recovered)
        self.assertEqual(recovered["matched_clue"], "ocr_explicit_title")

    def test_official_url_recall_blocks_context_only_url_without_anchor(self):
        identity = {
            "work_resolution": "none",
            "title_resolution_state": "context_only",
            "post_side_text": "오늘 점심 뭐 먹냐",
            "post_core_text": "오늘 점심 뭐 먹냐",
            "search_evidence_catalog": [
                {
                    "title": "괴담 호텔 탈출기",
                    "url": "https://novelpia.com/novel/102155",
                    "source_tier": "official_detail",
                }
            ],
        }

        self.assertIsNone(official_url_recoverable(identity))

    def test_official_url_recall_rejects_non_detail_viewer_url(self):
        identity = {
            "work_resolution": "unresolved",
            "title_resolution_state": "unresolved_matchable",
            "post_side_text": "괴담 호텔 탈출기 후기",
            "post_core_text": "괴담 호텔 탈출기 후기",
            "search_evidence_catalog": [
                {
                    "title": "괴담 호텔 탈출기",
                    "url": "https://novelpia.com/viewer/102155",
                    "source_tier": "official_detail",
                }
            ],
        }

        self.assertIsNone(official_url_recoverable(identity))

    def test_official_url_recall_uses_ocr_title_only_with_official_match(self):
        identity = {
            "work_resolution": "unresolved",
            "title_resolution_state": "ocr_explicit_title_unresolved",
            "post_side_text": "읽기 힘듦",
            "post_core_text": "읽기 힘듦",
            "image_evidence_catalog": [
                {
                    "explicit_work_title": "가족 친화적인 게임",
                    "title_role": "work_title",
                    "promotion_eligible": True,
                }
            ],
            "search_evidence_catalog": [
                {
                    "title": "가족 친화적인 게임",
                    "url": "https://novelpia.com/novel/282407",
                    "source_tier": "official_detail",
                }
            ],
        }

        recovered = official_url_recoverable(identity)

        self.assertIsNotNone(recovered)
        self.assertEqual(recovered["matched_clue"], "ocr_explicit_title")

    def test_official_url_recall_accepts_body_url_candidate_when_url_is_in_post(self):
        identity = {
            "work_resolution": "unresolved",
            "title_resolution_state": "unresolved_matchable",
            "post_side_text": "추천 https://novelpia.com/novel/236152",
            "post_core_text": "추천 https://novelpia.com/novel/236152",
            "body_official_detail_candidates": [
                {
                    "title": "사랑 그 시작은 늘 아름답다 하지만",
                    "url": "https://novelpia.com/novel/236152",
                }
            ],
        }

        recovered = official_url_recoverable(identity)

        self.assertIsNotNone(recovered)
        self.assertEqual(recovered["matched_clue"], "official_url_in_body")

    def test_official_url_recall_accepts_confirmed_alias_clue(self):
        identity = {
            "work_resolution": "unresolved",
            "title_resolution_state": "unresolved_matchable",
            "post_side_text": "오늘 담텔기 오냐?",
            "post_core_text": "오늘 담텔기 오냐?",
            "alias_clues": [{"alias": "담텔기", "title": "괴담 호텔 탈출기"}],
            "search_evidence_catalog": [
                {
                    "title": "괴담 호텔 탈출기",
                    "url": "https://novelpia.com/novel/102155",
                    "source_tier": "official_detail",
                }
            ],
        }

        recovered = official_url_recoverable(identity)

        self.assertIsNotNone(recovered)
        self.assertEqual(recovered["matched_clue"], "confirmed_alias:담텔기")

    def test_official_url_recall_prefers_bracket_post_cue_over_shared_alias_tag(self):
        identity = {
            "work_resolution": "unresolved",
            "title_resolution_state": "unresolved_matchable",
            "post_side_text": "랫따싶 림월드 요소 생각나게 하는거 좋네에...",
            "post_core_text": "랫따싶 림월드 요소 생각나게 하는거 좋네에...",
            "alias_clues": [{"alias": "랫따싶", "title": "쳇바퀴의 생쥐 사도가 되었다"}],
            "image_evidence_catalog": [
                {
                    "ocr_text": "림월드 방어 건물 제작 스킬이 늘었으려나. 회차를 다시 시작하고 싶을 정도.",
                    "visual_summary": "웹소설 본문 텍스트 화면. 게임 '림월드'의 요소를 묘사합니다.",
                    "work_cues": ["림월드", "제작 스킬", "방어 건물"],
                }
            ],
            "search_evidence_catalog": [
                {
                    "title": "쳇바퀴의 생쥐 사도가 되었다",
                    "url": "https://novelpia.com/novel/406113",
                    "source_tier": "official_detail",
                    "snippet": "랫따싶. #판타지 #전생 #성장. 생쥐 미소녀로 전생했더니 쥐의 여신과 만났다.",
                    "rank": 1,
                },
                {
                    "title": "[림월드]변방계에서 회귀자로 살아남기",
                    "url": "https://novelpia.com/novel/382324",
                    "source_tier": "official_detail",
                    "snippet": "단, 죽어서만. #패러디 #림월드 #랫따싶. 잡탕 종족모드가 적용된 변방계에 떨어졌다.",
                    "rank": 2,
                },
            ],
        }

        recovered = official_url_recoverable(identity)

        self.assertIsNotNone(recovered)
        self.assertEqual(recovered["official_title"], "[림월드]변방계에서 회귀자로 살아남기")
        self.assertEqual(recovered["heretic_url"], "https://novelpia.com/novel/382324")
        self.assertEqual(recovered["matched_clue"], "bracket_alias:림월드")

    def test_under_resolved_seed_keeps_candidate_without_promoting_title(self):
        identity = {
            "is_novel_related": True,
            "title_resolution_state": "unresolved_matchable",
            "work_resolution": "unresolved",
            "title_candidates": [{"title": "후보작"}],
            "novel_identity": None,
        }

        audit = build_candidate_audit_fields(
            identity,
            {"disagreement_type": "under_resolved_false_negative"},
        )

        self.assertEqual(audit["candidate_ledger_status"], "promotion_blocked")
        self.assertTrue(audit["promotion_blocked"])
        self.assertEqual(audit["candidate_ledger"]["title_candidates"], ["후보작"])

    def test_unresolved_entity_mentions_are_preserved_as_hold_candidates(self):
        identity = {
            "is_novel_related": True,
            "is_resolved_work_discussion": False,
            "title_resolution_allowed": False,
            "title_resolution_state": "adjacent",
            "work_resolution": "none",
            "discussion_type": "trope_discussion",
            "topicality": "adjacent_relevant",
            "novel_identity": None,
            "entity_mentions": [
                {
                    "text": "기계공주",
                    "entity_type": "character",
                    "confidence": "Medium",
                    "role": "character_focus",
                }
            ],
        }

        audit = build_candidate_audit_fields(identity, None)

        self.assertEqual(audit["candidate_ledger_status"], "promotion_blocked")
        self.assertTrue(audit["promotion_blocked"])
        self.assertEqual(audit["candidate_ledger"]["candidate_count"], 1)
        self.assertEqual(audit["candidate_ledger"]["title_candidates"], ["기계공주"])
        self.assertFalse(audit["safe_resolved"])

    def test_entity_mentions_do_not_pollute_resolved_titles(self):
        identity = {
            "is_novel_related": True,
            "is_resolved_work_discussion": False,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "unresolved",
            "discussion_type": "review",
            "novel_identity": {
                "official_title": "가챠 중독자의 퓨전펑크 생활",
                "heretic_url": "https://novelpia.com/novel/387014",
                "confidence": "High",
            },
            "entity_mentions": [
                {
                    "text": "세드릭",
                    "entity_type": "character",
                    "confidence": "Medium",
                    "role": "character_focus",
                }
            ],
        }

        audit = build_candidate_audit_fields(identity, None)

        self.assertEqual(audit["candidate_ledger_status"], "safe_resolved")
        self.assertEqual(audit["candidate_ledger"]["candidate_count"], 0)
        self.assertEqual(audit["candidate_ledger"]["title_candidates"], [])
        self.assertTrue(audit["safe_resolved"])

    def test_post_title_surface_hint_preserves_media_adaptation_candidate(self):
        identity = {
            "is_novel_related": False,
            "is_resolved_work_discussion": False,
            "title_resolution_allowed": False,
            "title_resolution_state": "nonwork",
            "work_resolution": "none",
            "discussion_type": "off_topic",
            "topicality": "unrelated",
            "novel_identity": None,
        }

        added = apply_post_surface_candidate_hints(
            identity,
            "월야환담 웹툰 레진판은 기록말소행임???",
        )
        audit = build_candidate_audit_fields(identity, None)

        self.assertEqual(added, ["월야환담"])
        self.assertEqual(audit["candidate_ledger_status"], "promotion_blocked")
        self.assertIn("월야환담", audit["candidate_ledger"]["title_candidates"])
        self.assertFalse(audit["hold_without_candidates"])

    def test_post_title_surface_hint_ignores_generic_and_resolved_titles(self):
        generic = {
            "is_novel_related": True,
            "title_resolution_allowed": False,
            "title_resolution_state": "adjacent",
            "work_resolution": "none",
            "novel_identity": None,
        }
        resolved = {
            "is_novel_related": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "novel_identity": {"official_title": "기존작", "confidence": "High"},
        }

        self.assertEqual(apply_post_surface_candidate_hints(generic, "웹툰 뭐봄?"), [])
        self.assertEqual(apply_post_surface_candidate_hints(resolved, "다른작 웹툰 후기"), [])
        self.assertNotIn("title_candidates", generic)
        self.assertNotIn("title_candidates", resolved)

    def test_post_title_surface_hint_preserves_ts_short_alias_candidate(self):
        identity = {
            "is_novel_related": True,
            "is_resolved_work_discussion": False,
            "title_resolution_allowed": False,
            "title_resolution_state": "adjacent",
            "work_resolution": "none",
            "discussion_type": "trope_discussion",
            "novel_identity": None,
        }

        added = apply_post_surface_candidate_hints(identity, "TS) 방타스) 이쪽 빽이 더 쎄지롱~")
        audit = build_candidate_audit_fields(identity, None)

        self.assertEqual(added, ["방타스"])
        self.assertEqual(audit["candidate_ledger_status"], "promotion_blocked")
        self.assertEqual(audit["candidate_ledger"]["title_candidates"], ["방타스"])

    def test_post_title_surface_hint_preserves_image_character_surface_candidate(self):
        identity = {
            "is_novel_related": True,
            "is_resolved_work_discussion": False,
            "title_resolution_allowed": False,
            "title_resolution_state": "context_only",
            "work_resolution": "none",
            "discussion_type": "undecodable_reference",
            "novel_identity": None,
            "image_evidence_catalog": [
                {
                    "evidence_type": "character_visual_only",
                    "title_role": "unknown",
                    "promotion_eligible": False,
                }
            ],
        }

        added = apply_post_surface_candidate_hints(identity, "담청 근데 왜 뿔꺾기당함?")
        audit = build_candidate_audit_fields(identity, None)

        self.assertEqual(added, ["담청"])
        self.assertEqual(audit["candidate_ledger_status"], "promotion_blocked")
        self.assertEqual(audit["candidate_ledger"]["title_candidates"], ["담청"])
        self.assertFalse(audit["safe_resolved"])

    def test_precision_seed_with_promoted_title_is_linted(self):
        identity = {
            "is_relevant": False,
            "is_resolved_work_discussion": False,
            "title_resolution_allowed": False,
            "title_resolution_state": "context_only",
            "work_resolution": "none",
            "discussion_type": "off_topic",
            "novel_identity": {"official_title": "novel.munpia.com", "confidence": "High"},
        }

        audit = build_candidate_audit_fields(
            identity,
            {"disagreement_type": "garbage_title"},
        )

        self.assertEqual(audit["candidate_ledger_status"], "official_title_lint")
        self.assertIn("official_title_looks_like_url_or_domain", audit["official_title_lint"])
        self.assertFalse(audit["safe_resolved"])

    def test_url_domain_official_title_is_demoted_but_candidates_are_kept(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "novel_identity": {
                "official_title": "novel.munpia.com",
                "heretic_url": "https://novel.munpia.com/482835",
                "confidence": "High",
            },
            "title_candidates": [
                {
                    "official_title": "슬라임 먹고 능력 흡수 헌터",
                    "source_tier": "official_detail",
                }
            ],
            "consistency_flags": [],
        }

        blocked = apply_official_title_promotion_guard(identity)
        fields = apply_candidate_audit_fields(
            identity,
            {"disagreement_type": "cross_media_or_famous_mismatch"},
        )

        self.assertEqual(blocked, ["official_title_looks_like_url_or_domain"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertIsNone(identity["novel_identity"]["heretic_url"])
        self.assertEqual(identity["novel_identity"]["confidence"], "None")
        self.assertEqual(identity["blocked_official_title"], "novel.munpia.com")
        self.assertEqual(identity["blocked_official_title_url"], "https://novel.munpia.com/482835")
        self.assertEqual(identity["work_resolution"], "unresolved")
        self.assertEqual(identity["title_resolution_state"], "unresolved_matchable")
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertFalse(identity["is_resolved_work_discussion"])
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        self.assertTrue(fields["promotion_blocked"])
        self.assertEqual(fields["candidate_ledger"]["pipeline_official_title"], None)
        self.assertEqual(
            fields["candidate_ledger"]["title_candidates"],
            ["슬라임 먹고 능력 흡수 헌터"],
        )
        self.assertEqual(
            fields["candidate_ledger"]["blocked_official_title"],
            "novel.munpia.com",
        )
        self.assertIn("official_title_looks_like_url_or_domain", fields["official_title_lint"])
        self.assertIn("official_title_looks_like_url_or_domain", identity["consistency_flags"])

    def test_snippet_like_official_title_is_demoted_but_preserved(self):
        snippet_title = (
            "개요 정신 질환자란 망상, 환각, 사고나 기분의 장애 등으로 인하여 "
            "독립적으로 일상생활을 영위하는 데 중대한 제약이 있는 사람을 말한다."
        )
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "novel_identity": {
                "official_title": snippet_title,
                "heretic_url": "https://ridibooks.com/books/120104954",
                "confidence": "High",
            },
            "title_candidates": [{"official_title": "정신병동에도 아침이 와요"}],
            "consistency_flags": [],
        }

        blocked = apply_official_title_promotion_guard(identity)
        fields = apply_candidate_audit_fields(
            identity,
            {"disagreement_type": "conflicting_or_multi_candidate"},
        )

        self.assertEqual(blocked, ["official_title_looks_like_search_snippet"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(identity["blocked_official_title"], snippet_title)
        self.assertEqual(identity["title_resolution_state"], "unresolved_matchable")
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertIn("official_title_looks_like_search_snippet", fields["official_title_lint"])
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")

    def test_listing_description_official_title_is_demoted_but_preserved(self):
        description_title = "괴한들에게 납치당했더니 여자아이가 되어버렸다. …이득 아닌가? [아니었다.]"
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "post_core_text": "어케 주인공 죄목이 납치담금세뇌테러불법투기셍태계교란희롱준강간",
            "novel_identity": {
                "official_title": description_title,
                "heretic_url": "https://novelpia.com/novel/436108",
                "confidence": "High",
            },
            "image_evidence_catalog": [
                {
                    "ocr_text": "B급 모험가 밤도깨비 에이브가 되어 있었다.",
                    "title_role": "unknown",
                    "promotion_eligible": False,
                    "work_cues": ["밤도깨비 에이브"],
                }
            ],
            "search_evidence_catalog": [
                {
                    "title": description_title,
                    "url": "https://novelpia.com/novel/436108",
                    "source_tier": "official_detail",
                },
                {
                    "title": "명문가와 기업이 지배하는 퓨전펑크 도시 한양.",
                    "url": "https://novelpia.com/novel/435653",
                    "source_tier": "official_detail",
                    "snippet": f"{description_title} 집으로 돌아오긴 했는데 이제 뭐하지?",
                },
                {
                    "title": "집으로 돌아오긴 했는데 이제 뭐하지?",
                    "url": "https://novelpia.com/novel/432172",
                    "source_tier": "official_detail",
                    "snippet": f"명문가와 기업이 지배하는 퓨전펑크 도시 한양. {description_title}",
                },
            ],
            "title_candidates": [
                {
                    "official_title": description_title,
                    "heretic_url": "https://novelpia.com/novel/436108",
                    "source_tier": "official_detail",
                }
            ],
            "consistency_flags": [],
        }

        blocked = apply_official_title_promotion_guard(identity)
        fields = apply_candidate_audit_fields(
            identity,
            {"disagreement_type": "over_resolved"},
        )

        self.assertEqual(blocked, ["official_title_looks_like_listing_description"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertIsNone(identity["novel_identity"]["heretic_url"])
        self.assertEqual(identity["blocked_official_title"], description_title)
        self.assertEqual(identity["blocked_official_title_url"], "https://novelpia.com/novel/436108")
        self.assertEqual(identity["title_resolution_state"], "unresolved_matchable")
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertIn("official_title_looks_like_listing_description", fields["official_title_lint"])
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        self.assertFalse(fields["safe_resolved"])

    def test_breadcrumb_official_title_is_demoted_but_preserved(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "novel_identity": {
                "official_title": "나무위키 namu.wiki ›",
                "confidence": "High",
            },
            "consistency_flags": [],
        }

        blocked = apply_official_title_promotion_guard(identity)

        self.assertEqual(blocked, ["official_title_looks_like_breadcrumb"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(identity["blocked_official_title"], "나무위키 namu.wiki ›")

    def test_title_noisy_ocr_seed_with_official_platform_evidence_is_safe_resolved(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "review",
            "novel_identity": {
                "official_title": "소설 속 마녀를 주웠다",
                "heretic_url": "https://novelpia.com/novel/308028",
                "confidence": "High",
            },
            "search_evidence_catalog": [
                {
                    "title": "소설 속 마녀를 주웠다",
                    "url": "https://novelpia.com/novel/308028",
                    "source_tier": "novel_platform",
                }
            ],
        }

        fields = apply_candidate_audit_fields(
            identity,
            {"disagreement_type": "title_noisy_ocr"},
        )

        self.assertEqual(fields["candidate_ledger_status"], "safe_resolved")
        self.assertEqual(fields["output_consistency_lint"], [])
        self.assertTrue(fields["safe_resolved"])

    def test_title_noisy_ocr_seed_rejects_primary_work_self_claim_without_title_match(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "review",
            "novel_identity": {
                "official_title": "전쟁 명장으로 착각당했다",
                "heretic_url": "https://novelpia.com/novel/383680",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "전쟁 명장으로 착각당했다",
                "heretic_url": "https://novelpia.com/novel/383680",
                "source_tier": "official_detail",
            },
            "search_evidence_catalog": [
                {
                    "title": "불패의 명장으로 착각당했다",
                    "url": "https://novelpia.com/novel/383680",
                    "source_tier": "novel_platform",
                }
            ],
        }

        fields = apply_candidate_audit_fields(
            identity,
            {"disagreement_type": "title_noisy_ocr"},
        )

        self.assertEqual(fields["candidate_ledger_status"], "output_consistency_lint")
        self.assertEqual(fields["output_consistency_lint"], ["judge_hygiene_seed_title_noisy_ocr"])
        self.assertFalse(fields["safe_resolved"])

    def test_title_noisy_ocr_seed_realigns_when_image_and_official_search_match(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "review",
            "novel_identity": {
                "official_title": "전쟁 명장으로 착각당했다",
                "heretic_url": "https://novelpia.com/novel/383680",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "전쟁 명장으로 착각당했다",
                "heretic_url": "https://novelpia.com/novel/383680",
                "source_tier": "official_detail",
            },
            "image_evidence_catalog": [
                {
                    "explicit_work_title": "불패의 명장으로 착각당했다",
                    "title_role": "work_title",
                    "promotion_eligible": True,
                }
            ],
            "search_evidence_catalog": [
                {
                    "title": "불패의 명장으로 착각당했다",
                    "url": "https://novelpia.com/novel/383680",
                    "source_tier": "novel_platform",
                }
            ],
        }

        corrected = apply_judge_seed_title_hygiene_guard(
            identity,
            {"disagreement_type": "title_noisy_ocr"},
        )
        fields = apply_candidate_audit_fields(
            identity,
            {"disagreement_type": "title_noisy_ocr"},
        )

        self.assertEqual(corrected, ["title_noisy_ocr_realigned_to_official_image_search_evidence"])
        self.assertEqual(identity["novel_identity"]["official_title"], "불패의 명장으로 착각당했다")
        self.assertEqual(identity["primary_work"]["official_title"], "불패의 명장으로 착각당했다")
        self.assertEqual(fields["candidate_ledger_status"], "safe_resolved")
        self.assertEqual(fields["output_consistency_lint"], [])
        self.assertTrue(fields["safe_resolved"])

    def test_title_noisy_ocr_seed_holds_ocr_title_without_official_evidence(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "review",
            "novel_identity": {
                "official_title": "비틀 저서라도 세상은 구해...",
                "confidence": "High",
            },
            "image_evidence_catalog": [
                {
                    "explicit_work_title": "비틀 저서라도 세상은 구해...",
                    "title_role": "work_title",
                    "promotion_eligible": True,
                }
            ],
            "search_evidence_catalog": [
                {
                    "title": "[PC] 네이버 시리즈",
                    "url": "https://series.naver.com/",
                    "source_tier": "novel_platform",
                }
            ],
        }

        blocked = apply_judge_seed_unverified_ocr_title_guard(
            identity,
            {"disagreement_type": "title_noisy_ocr"},
        )
        fields = apply_candidate_audit_fields(
            identity,
            {"disagreement_type": "title_noisy_ocr"},
        )

        self.assertEqual(blocked, ["title_noisy_ocr_without_official_evidence"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(identity["blocked_official_title"], "비틀 저서라도 세상은 구해...")
        self.assertEqual(identity["work_resolution"], "unresolved")
        self.assertEqual(identity["title_resolution_state"], "ocr_explicit_title_unresolved")
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertEqual(fields["candidate_ledger_status"], "hold_unresolved")
        self.assertEqual(fields["output_consistency_lint"], [])
        self.assertTrue(fields["hold_unresolved"])

    def test_title_noisy_ocr_seed_holds_official_title_that_conflicts_with_image_title(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "review",
            "novel_identity": {
                "official_title": "주관적인 모바일 앱",
                "heretic_url": "https://novelpia.com/novel/32979",
                "confidence": "Medium",
            },
            "title_candidates": [
                {
                    "official_title": "주관적인 모바일 앱",
                    "heretic_url": "https://novelpia.com/novel/32979",
                    "source_tier": "mixed",
                },
                {
                    "official_title": "빛을 저sera도 세상은 구해...",
                    "source_tier": "llm_only",
                },
            ],
            "image_evidence_catalog": [
                {
                    "explicit_work_title": "빛을 저sera도 세상은 구해...",
                    "title_role": "work_title",
                    "promotion_eligible": True,
                }
            ],
            "search_evidence_catalog": [
                {
                    "title": "주관적인 모바일 앱",
                    "url": "https://novelpia.com/novel/32979",
                    "source_tier": "novel_platform",
                }
            ],
            "consistency_flags": [
                "vlm_ocr_title_conflict_with_final_title",
                "image_surface_title_unverified_without_official_evidence",
            ],
        }

        blocked = apply_judge_seed_title_image_mismatch_guard(
            identity,
            {"disagreement_type": "title_noisy_ocr"},
        )
        fields = apply_candidate_audit_fields(
            identity,
            {"disagreement_type": "title_noisy_ocr"},
        )

        self.assertEqual(blocked, ["title_noisy_ocr_conflicts_with_direct_image_title"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertIsNone(identity["novel_identity"]["heretic_url"])
        self.assertEqual(identity["blocked_official_title"], "주관적인 모바일 앱")
        self.assertEqual(identity["blocked_official_title_url"], "https://novelpia.com/novel/32979")
        self.assertEqual(identity["work_resolution"], "unresolved")
        self.assertEqual(identity["title_resolution_state"], "ocr_explicit_title_unresolved")
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertEqual(fields["candidate_ledger_status"], "hold_unresolved")
        self.assertEqual(fields["output_consistency_lint"], [])
        self.assertIn("빛을 저sera도 세상은 구해...", fields["candidate_ledger"]["title_candidates"])

    def test_precision_seed_with_weak_non_novel_support_is_demoted_to_candidate(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "review",
            "novel_identity": {"official_title": "이문열 삼국지", "confidence": "High"},
            "primary_work": {
                "official_title": "이문열 삼국지",
                "source_tier": "llm_only",
            },
            "search_evidence_catalog": [
                {"title": "삼국지 - 나무위키", "source_tier": "wiki"}
            ],
        }

        blocked = apply_judge_seed_precision_guard(
            identity,
            {"disagreement_type": "cross_media_or_famous_mismatch"},
        )
        fields = apply_candidate_audit_fields(
            identity,
            {"disagreement_type": "cross_media_or_famous_mismatch"},
        )

        self.assertEqual(blocked, ["precision_seed_weak_source_title_without_official_support"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(identity["work_resolution"], "unresolved")
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        self.assertEqual(fields["candidate_ledger"]["blocked_official_title"], "이문열 삼국지")
        self.assertEqual(fields["candidate_ledger"]["title_candidates"], ["이문열 삼국지"])

    def test_precision_seed_with_platform_url_still_requires_review(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "review",
            "heretic_url": "https://page.kakao.com/content/51726202",
            "novel_identity": {
                "official_title": "인간 실격",
                "heretic_url": "https://page.kakao.com/content/51726202",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "인간 실격",
                "heretic_url": "https://page.kakao.com/content/51726202",
                "source_tier": "official_detail",
            },
            "search_evidence_catalog": [
                {
                    "title": "인간 실격",
                    "url": "https://page.kakao.com/content/51726202",
                    "source_tier": "official_detail",
                }
            ],
        }

        blocked = apply_judge_seed_precision_guard(
            identity,
            {"disagreement_type": "cross_media_or_famous_mismatch"},
        )
        fields = apply_candidate_audit_fields(
            identity,
            {"disagreement_type": "cross_media_or_famous_mismatch"},
        )

        self.assertEqual(blocked, ["precision_seed_official_title_requires_review"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertIsNone(identity["novel_identity"]["heretic_url"])
        self.assertIsNone(identity["heretic_url"])
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        self.assertEqual(fields["candidate_ledger"]["blocked_official_title"], "인간 실격")
        self.assertEqual(fields["candidate_ledger"]["blocked_official_title_url"], "https://page.kakao.com/content/51726202")

    def test_precision_seed_with_confirmed_alias_official_detail_is_not_demoted(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "anchor_type": "image",
            "anchor_strength": "high",
            "context_sources": ["title", "search", "image"],
            "consistency_flags": [
                "verified_alias_official_detail_anchor",
                "confirmed_alias:아카메디",
                "explicit_alias_official_work_lock",
            ],
            "novel_identity": {
                "official_title": "아카메디 아카데미",
                "heretic_url": "https://novelpia.com/novel/22299",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "아카메디 아카데미",
                "heretic_url": "https://novelpia.com/novel/22299",
                "source_tier": "official_detail",
                "page_type": "novel_page",
                "reference_role": "primary",
            },
            "candidate_preservation_sources": [
                {
                    "official_title": "아카메디 아카데미",
                    "heretic_url": "https://novelpia.com/novel/22299",
                    "source_tier": "official_detail",
                    "page_type": "novel_page",
                    "reference_role": "primary",
                }
            ],
        }

        blocked = apply_judge_seed_precision_guard(
            identity,
            {"seed_bucket": "precision_identity_high", "disagreement_type": "garbage_title"},
        )
        fields = apply_candidate_audit_fields(
            identity,
            {"seed_bucket": "precision_identity_high", "disagreement_type": "garbage_title"},
        )

        self.assertEqual(blocked, [])
        self.assertEqual(identity["novel_identity"]["official_title"], "아카메디 아카데미")
        self.assertIn("precision_seed_independent_official_detail_supported", identity["consistency_flags"])
        self.assertEqual(fields["candidate_ledger_status"], "safe_resolved")
        self.assertEqual(fields["identity_consistency_lint"], [])

    def test_phase2_hold_precision_seed_blocks_official_detail_bypass(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "primary_subject_type": "work_discussion",
            "anchor_type": "title_alias",
            "anchor_strength": "medium",
            "context_sources": ["title", "body", "comments", "search", "image"],
            "consistency_flags": [
                "verified_alias_official_detail_anchor",
                "confirmed_alias:아생갤",
                "explicit_alias_official_work_lock",
                "weak_public_title_bridge_verified_alias_detail_exempt",
            ],
            "novel_identity": {
                "official_title": "아카데미 생존 갤러리",
                "heretic_url": "https://novelpia.com/novel/380218",
                "confidence": "Medium",
            },
            "primary_work": {
                "official_title": "아카데미 생존 갤러리",
                "heretic_url": "https://novelpia.com/novel/380218",
                "alias_or_mention": "아생갤",
                "source_tier": "official_detail",
                "page_type": "novel_page",
                "reference_role": "primary",
            },
            "candidate_preservation_sources": [
                {
                    "official_title": "아카데미 생존 갤러리",
                    "heretic_url": "https://novelpia.com/novel/380218",
                    "alias_or_mention": "아생갤",
                    "source_tier": "official_detail",
                    "page_type": "novel_page",
                    "reference_role": "primary",
                }
            ],
        }

        blocked = apply_judge_seed_precision_guard(
            identity,
            {
                "seed_group": "precision_identity_high",
                "disagreement_type": "over_resolved",
                "phase2_resolution_label": "HOLD",
                "phase2_recommended_action": "re_search",
                "phase2_fix_axis": "resolution_promotion_gate",
            },
        )
        fields = apply_candidate_audit_fields(
            identity,
            {
                "seed_group": "precision_identity_high",
                "disagreement_type": "over_resolved",
                "phase2_resolution_label": "HOLD",
                "phase2_recommended_action": "re_search",
                "phase2_fix_axis": "resolution_promotion_gate",
            },
        )

        self.assertEqual(blocked, ["phase2_hold_seed_requires_review"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertNotIn(
            "precision_seed_independent_official_detail_supported",
            identity.get("consistency_flags", []),
        )
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        self.assertEqual(fields["candidate_ledger"]["blocked_official_title"], "아카데미 생존 갤러리")

    def test_precision_seed_conflict_flags_do_not_bypass_on_official_detail(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "anchor_type": "title_alias",
            "anchor_strength": "high",
            "context_sources": ["title", "search", "image"],
            "primary_subject_type": "multi_work_bundle",
            "consistency_flags": [
                "official_url_recall_gate_recovered",
                "title_body_official_detail_anchor",
                "vlm_ocr_title_conflict_with_final_title",
                "ocr_title_conflict_with_stable_alias",
            ],
            "novel_identity": {
                "official_title": "괴한들에게 납치당했더니 여자아이가 되어버렸다. …이득 아닌가? [아니었다.]",
                "heretic_url": "https://novelpia.com/novel/436108",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "괴한들에게 납치당했더니 여자아이가 되어버렸다. …이득 아닌가? [아니었다.]",
                "heretic_url": "https://novelpia.com/novel/436108",
                "source_tier": "official_detail",
                "reference_role": "primary",
                "alias_or_mention": "납치 되어",
            },
            "candidate_preservation_sources": [
                {
                    "official_title": "괴한들에게 납치당했더니 여자아이가 되어버렸다. …이득 아닌가? [아니었다.]",
                    "heretic_url": "https://novelpia.com/novel/436108",
                    "source_tier": "official_detail",
                    "reference_role": "primary",
                    "alias_or_mention": "납치 되어",
                }
            ],
        }

        blocked = apply_judge_seed_precision_guard(
            identity,
            {"seed_bucket": "precision_identity_high", "disagreement_type": "over_resolved"},
        )
        fields = apply_candidate_audit_fields(
            identity,
            {"seed_bucket": "precision_identity_high", "disagreement_type": "over_resolved"},
        )

        self.assertEqual(blocked, ["precision_seed_official_title_requires_review"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        self.assertIn(
            "괴한들에게 납치당했더니 여자아이가 되어버렸다. …이득 아닌가? [아니었다.]",
            fields["candidate_ledger"]["title_candidates"],
        )

    def test_precision_seed_locked_official_reread_bypasses_stale_multi_work_clear(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "meme",
            "primary_subject_type": "work_discussion",
            "anchor_type": "title_alias",
            "anchor_strength": "high",
            "context_sources": ["title", "body", "comments", "search"],
            "consistency_flags": [
                "multi_work_title_cleared",
                "secondary_reference_official_alias_blocked_after_multi_work_title_cleared",
                "locked_official_candidate_rescued",
                "locked_official_rescue_cleared_stale_demotions",
                "final_semantic_reread_reviewed",
                "final_semantic_reread_accepted_resolution",
                "weak_public_title_bridge_locked_official_exempt",
            ],
            "novel_identity": {
                "official_title": "탐식의 재림",
                "heretic_url": "https://ridibooks.com/books/2008016338?srsltid=test",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "탐식의 재림",
                "heretic_url": "https://ridibooks.com/books/2008016338?srsltid=test",
                "source_tier": "official_detail",
                "reference_role": "primary",
                "locked": True,
            },
            "candidate_preservation_sources": [
                {
                    "official_title": "탐식의 재림",
                    "heretic_url": "https://ridibooks.com/books/2008016338?srsltid=test",
                    "source_tier": "official_detail",
                    "reference_role": "primary",
                }
            ],
            "search_evidence_catalog": [
                {
                    "title": "탐식의 재림 - 웹소설 - 카카오페이지",
                    "url": "https://page.kakao.com/content/50219568?tab_type=comment",
                    "source_tier": "novel_platform",
                    "purpose": "alias_bridge_search",
                },
                {
                    "title": "탐식의 재림 - 판타지 e북",
                    "url": "https://ridibooks.com/books/2008016338?srsltid=test",
                    "source_tier": "novel_platform",
                    "purpose": "adaptive_author",
                },
            ],
        }

        blocked = apply_judge_seed_precision_guard(
            identity,
            {"seed_bucket": "precision_wrong_work_control", "disagreement_type": "wrong_work"},
        )
        fields = apply_candidate_audit_fields(
            identity,
            {"seed_bucket": "precision_wrong_work_control", "disagreement_type": "wrong_work"},
        )

        self.assertEqual(blocked, [])
        self.assertEqual(identity["novel_identity"]["official_title"], "탐식의 재림")
        self.assertEqual(identity["work_resolution"], "resolved")
        self.assertIn("precision_seed_independent_official_detail_supported", identity["consistency_flags"])
        self.assertEqual(fields["candidate_ledger_status"], "safe_resolved")

    def test_precision_seed_verified_alias_reread_bypasses_stale_multi_work_clear(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "primary_subject_type": "multi_work_bundle",
            "anchor_type": "title_alias",
            "anchor_strength": "medium",
            "context_sources": ["title", "body", "comments", "search"],
            "consistency_flags": [
                "multi_work_title_cleared",
                "secondary_reference_official_alias_blocked_after_multi_work_title_cleared",
                "official_url_recall_gate_recovered",
                "confirmed_alias:설지후",
                "verified_alias_official_detail_anchor",
                "confirmed_alias:설지후 변화도 레전드",
                "official_detail_url_repaired_from_search",
                "final_semantic_reread_reviewed",
                "final_semantic_reread_accepted_resolution",
            ],
            "novel_identity": {
                "official_title": "탐식의 재림",
                "heretic_url": "https://page.kakao.com/content/50219568",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "탐식의 재림",
                "heretic_url": "https://page.kakao.com/content/50219568",
                "source_tier": "official_detail",
                "page_type": "novel_page",
                "reference_role": "candidate",
                "alias_or_mention": "설지후",
            },
            "candidate_preservation_sources": [
                {
                    "official_title": "탐식의 재림",
                    "heretic_url": "https://page.kakao.com/content/50219568",
                    "source_tier": "official_detail",
                    "page_type": "novel_page",
                    "reference_role": "candidate",
                    "alias_or_mention": "설지후",
                }
            ],
            "search_evidence_catalog": [
                {
                    "title": "탐식의 재림 - 웹소설 - 카카오페이지",
                    "url": "https://page.kakao.com/content/50219568",
                    "source_tier": "novel_platform",
                    "purpose": "official_detail",
                }
            ],
        }

        blocked = apply_judge_seed_precision_guard(
            identity,
            {"seed_bucket": "precision_identity_high", "disagreement_type": "over_resolved"},
        )
        fields = apply_candidate_audit_fields(
            identity,
            {"seed_bucket": "precision_identity_high", "disagreement_type": "over_resolved"},
        )

        self.assertEqual(blocked, [])
        self.assertEqual(identity["novel_identity"]["official_title"], "탐식의 재림")
        self.assertEqual(identity["novel_identity"]["heretic_url"], "https://page.kakao.com/content/50219568")
        self.assertEqual(identity["work_resolution"], "resolved")
        self.assertIn("precision_seed_independent_official_detail_supported", identity["consistency_flags"])
        self.assertEqual(fields["candidate_ledger_status"], "safe_resolved")

    def test_precision_seed_locked_official_reread_uses_primary_detail_support_when_catalog_title_is_unreadable(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "primary_subject_type": "work_discussion",
            "anchor_type": "title_alias",
            "anchor_strength": "high",
            "context_sources": ["title", "body", "comments", "search"],
            "consistency_flags": [
                "multi_work_title_cleared",
                "secondary_reference_official_alias_blocked_after_multi_work_title_cleared",
                "locked_official_candidate_rescued",
                "locked_official_rescue_cleared_stale_demotions",
                "final_semantic_reread_reviewed",
                "final_semantic_reread_accepted_resolution",
                "weak_public_title_bridge_locked_official_exempt",
            ],
            "novel_identity": {
                "official_title": "탐식의 재림",
                "heretic_url": "https://series.naver.com/novel/detail.series?productNo=2847498",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "탐식의 재림",
                "heretic_url": "https://series.naver.com/novel/detail.series?productNo=2847498",
                "source_tier": "official_detail",
                "page_type": "novel_page",
                "content_status": "active",
                "reference_role": "primary",
                "locked": True,
            },
            "candidate_preservation_sources": [
                {
                    "official_title": "탐식의 재림",
                    "heretic_url": "https://series.naver.com/novel/detail.series?productNo=2847498",
                    "source_tier": "official_detail",
                    "page_type": "novel_page",
                    "content_status": "active",
                    "reference_role": "primary",
                }
            ],
            "search_evidence_catalog": [
                {
                    "title": "??? ?? - ??? ???",
                    "url": "https://series.naver.com/novel/detail.series?productNo=2847498",
                    "source_tier": "novel_platform",
                    "purpose": "precomputed_source_evidence",
                }
            ],
        }

        blocked = apply_judge_seed_precision_guard(
            identity,
            {"seed_bucket": "precision_wrong_work_control", "disagreement_type": "wrong_work"},
        )
        fields = apply_candidate_audit_fields(
            identity,
            {"seed_bucket": "precision_wrong_work_control", "disagreement_type": "wrong_work"},
        )

        self.assertEqual(blocked, [])
        self.assertEqual(identity["novel_identity"]["official_title"], "탐식의 재림")
        self.assertIn("precision_seed_independent_official_detail_supported", identity["consistency_flags"])
        self.assertEqual(fields["candidate_ledger_status"], "safe_resolved")

    def test_precision_seed_locked_official_context_anchor_bypasses_stale_competing_recall(self):
        def make_identity(*, cleared_stale_demotions: bool):
            flags = [
                "multi_work_title_cleared",
                "secondary_reference_official_alias_blocked_after_multi_work_title_cleared",
                "official_url_recall_blocked_competing_candidate",
                "locked_official_candidate_rescued",
                "weak_public_title_bridge_locked_official_exempt",
            ]
            if cleared_stale_demotions:
                flags.append("locked_official_rescue_cleared_stale_demotions")
            return {
                "is_relevant": True,
                "is_novel_related": True,
                "is_resolved_work_discussion": True,
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "discussion_type": "character_talk",
                "primary_subject_type": "work_discussion",
                "anchor_type": "author",
                "anchor_strength": "medium",
                "context_sources": ["title", "body", "comments", "search"],
                "consistency_flags": flags,
                "novel_identity": {
                    "official_title": "탐식의 재림",
                    "heretic_url": "https://page.kakao.com/content/50219568",
                    "confidence": "High",
                },
                "primary_work": {
                    "official_title": "탐식의 재림",
                    "heretic_url": "https://page.kakao.com/content/50219568",
                    "source_tier": "official_detail",
                    "page_type": "novel_page",
                    "reference_role": "primary",
                    "locked": True,
                },
                "title_candidates": [
                    {
                        "official_title": "탐식의 재림",
                        "heretic_url": "https://page.kakao.com/content/50219568",
                        "source_tier": "official_detail",
                        "page_type": "novel_page",
                        "reference_role": "primary",
                        "locked": True,
                    },
                    {
                        "title": "@ㅇㅇ",
                        "source_tier": "comment_surface",
                        "promotion_policy": "hold_without_promotion",
                    },
                ],
                "search_evidence_catalog": [
                    {
                        "title": "탐식의 재림 - 웹소설 - 카카오페이지",
                        "url": "https://page.kakao.com/content/50219568",
                        "source_tier": "novel_platform",
                        "purpose": "precomputed_source_evidence",
                    }
                ],
            }

        identity = make_identity(cleared_stale_demotions=True)
        blocked = apply_judge_seed_precision_guard(
            identity,
            {"seed_bucket": "precision_wrong_work_control", "disagreement_type": "wrong_work"},
        )
        fields = apply_candidate_audit_fields(
            identity,
            {"seed_bucket": "precision_wrong_work_control", "disagreement_type": "wrong_work"},
        )

        self.assertEqual(blocked, [])
        self.assertEqual(identity["novel_identity"]["official_title"], "탐식의 재림")
        self.assertIn("precision_seed_independent_official_detail_supported", identity["consistency_flags"])
        self.assertEqual(fields["candidate_ledger_status"], "safe_resolved")

        uncleared = make_identity(cleared_stale_demotions=False)
        blocked = apply_judge_seed_precision_guard(
            uncleared,
            {"seed_bucket": "precision_wrong_work_control", "disagreement_type": "wrong_work"},
        )

        self.assertEqual(blocked, ["precision_seed_official_title_requires_review"])
        self.assertIsNone(uncleared["novel_identity"]["official_title"])

    def test_precision_seed_with_alias_source_and_title_anchor_is_not_demoted(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "anchor_type": "title_exact",
            "anchor_strength": "high",
            "context_sources": ["title", "search"],
            "novel_identity": {
                "official_title": "엑스칼리버 뽑습니다",
                "heretic_url": "https://novelpia.com/novel/229672",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "엑스칼리버 뽑습니다",
                "heretic_url": "https://novelpia.com/novel/229672",
                "alias_or_mention": "엑칼뽑",
                "source_tier": "official_detail",
                "page_type": "novel_page",
                "reference_role": "primary",
            },
            "candidate_preservation_sources": [
                {
                    "official_title": "엑스칼리버 뽑습니다",
                    "heretic_url": "https://novelpia.com/novel/229672",
                    "alias_or_mention": "엑칼뽑",
                    "source_tier": "official_detail",
                    "page_type": "novel_page",
                    "reference_role": "primary",
                }
            ],
        }

        blocked = apply_judge_seed_precision_guard(
            identity,
            {"seed_bucket": "precision_wrong_work_control", "disagreement_type": "wrong_work"},
        )
        fields = apply_candidate_audit_fields(
            identity,
            {"seed_bucket": "precision_wrong_work_control", "disagreement_type": "wrong_work"},
        )

        self.assertEqual(blocked, [])
        self.assertEqual(identity["novel_identity"]["official_title"], "엑스칼리버 뽑습니다")
        self.assertEqual(fields["candidate_ledger_status"], "safe_resolved")
        self.assertEqual(fields["identity_consistency_lint"], [])

    def test_precision_seed_author_plot_composite_alias_is_demoted_to_candidate(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "anchor_type": "title_exact",
            "anchor_strength": "high",
            "context_sources": ["title", "body", "comments", "search"],
            "novel_identity": {
                "official_title": "이세계에서 사이비로 살아남기",
                "heretic_url": "https://novelpia.com/novel/181771",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "이세계에서 사이비로 살아남기",
                "heretic_url": "https://novelpia.com/novel/181771",
                "source_tier": "official_detail",
                "page_type": "novel_page",
                "reference_role": "primary",
            },
            "slang_insight": {
                "detected_term": "미츄리",
                "decoded_term": "이세계에서 사이비로 살아남기",
                "alias_scope": "work_plus_author",
                "attached_entity_text": "미츄리 혼후순결",
                "attached_entity_type": "author",
                "store_reason": "composite_alias",
            },
            "candidate_preservation_sources": [
                {
                    "official_title": "이세계에서 사이비로 살아남기",
                    "heretic_url": "https://novelpia.com/novel/181771",
                    "source_tier": "official_detail",
                    "page_type": "novel_page",
                    "reference_role": "primary",
                }
            ],
        }

        blocked = apply_judge_seed_precision_guard(
            identity,
            {"seed_bucket": "precision_wrong_work_control", "disagreement_type": "wrong_work"},
        )
        fields = apply_candidate_audit_fields(
            identity,
            {"seed_bucket": "precision_wrong_work_control", "disagreement_type": "wrong_work"},
        )

        self.assertEqual(blocked, ["precision_seed_author_plot_composite_requires_review"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        self.assertIn(
            "이세계에서 사이비로 살아남기",
            fields["candidate_ledger"]["title_candidates"],
        )

    def test_precision_seed_contextual_author_plot_composite_without_type_is_demoted(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "primary_subject_type": "multi_work_bundle",
            "anchor_type": "title_alias",
            "anchor_strength": "high",
            "context_sources": ["title", "body", "comments", "search"],
            "consistency_flags": [
                "relation_hold_unresolved_recovered",
                "official_url_recall_gate_recovered",
                "search_catalog_contextual_work:미츄리 혼후순결",
                "search_catalog_contextual_work_recall_anchor",
            ],
            "novel_identity": {
                "official_title": "이세계에서 사이비로 살아남기",
                "heretic_url": "https://novelpia.com/novel/181771",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "이세계에서 사이비로 살아남기",
                "heretic_url": "https://novelpia.com/novel/181771",
                "alias_or_mention": "미츄리 혼후순결",
                "source_tier": "official_detail",
                "page_type": "novel_page",
                "reference_role": "primary",
            },
            "slang_insight": {
                "detected_term": "미츄리",
                "decoded_term": "이세계에서 사이비로 살아남기",
                "alias_scope": "work_plus_author",
                "attached_entity_text": "미츄리 혼후순결",
                "attached_entity_type": None,
                "store_reason": "composite_alias",
            },
            "candidate_preservation_sources": [
                {
                    "official_title": "이세계에서 사이비로 살아남기",
                    "heretic_url": "https://novelpia.com/novel/181771",
                    "alias_or_mention": "미츄리 혼후순결",
                    "source_tier": "official_detail",
                    "page_type": "novel_page",
                    "reference_role": "primary",
                }
            ],
        }

        blocked = apply_judge_seed_precision_guard(
            identity,
            {"seed_bucket": "precision_wrong_work_control", "disagreement_type": "wrong_work"},
        )
        fields = apply_candidate_audit_fields(
            identity,
            {"seed_bucket": "precision_wrong_work_control", "disagreement_type": "wrong_work"},
        )

        self.assertEqual(blocked, ["precision_seed_author_plot_composite_requires_review"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        self.assertIn(
            "이세계에서 사이비로 살아남기",
            fields["candidate_ledger"]["title_candidates"],
        )

    def test_precision_seed_same_url_official_detail_canonicalizes_before_bypass(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "review",
            "anchor_type": "title_alias",
            "anchor_strength": "medium",
            "context_sources": ["title", "search", "image"],
            "consistency_flags": [
                "verified_alias_official_detail_anchor",
                "confirmed_alias:기계공주",
                "explicit_alias_official_work_lock",
            ],
            "novel_identity": {
                "official_title": "헌터갤러리의 국가권력급",
                "heretic_url": "https://novelpia.com/novel/390228",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "헌터갤러리의 국가권력급",
                "heretic_url": "https://novelpia.com/novel/390228",
                "alias_or_mention": "기계공주",
                "source_tier": "official_detail",
                "page_type": "novel_page",
                "reference_role": "primary",
            },
            "candidate_preservation_sources": [
                {
                    "official_title": "헌터갤러리의 국가권력급 기계공주",
                    "heretic_url": "https://novelpia.com/novel/390228",
                    "source_tier": "official_detail",
                    "page_type": "novel_page|unknown",
                    "reference_role": "mentioned",
                }
            ],
        }

        blocked = apply_judge_seed_precision_guard(
            identity,
            {"seed_bucket": "precision_identity_high", "disagreement_type": "garbage_title"},
        )
        fields = apply_candidate_audit_fields(
            identity,
            {"seed_bucket": "precision_identity_high", "disagreement_type": "garbage_title"},
        )

        self.assertEqual(blocked, [])
        self.assertEqual(identity["novel_identity"]["official_title"], "헌터갤러리의 국가권력급 기계공주")
        self.assertIn("same_url_official_detail_canonicalized", identity["consistency_flags"])
        self.assertEqual(fields["candidate_ledger_status"], "safe_resolved")
        self.assertEqual(fields["identity_consistency_lint"], [])

    def test_precision_seed_bypass_prevents_later_weak_alias_bridge_demote(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "anchor_type": "image",
            "anchor_strength": "high",
            "context_sources": ["title", "search", "image"],
            "consistency_flags": [
                "verified_alias_official_detail_anchor",
                "confirmed_alias:기계공주",
                "explicit_alias_official_work_lock",
            ],
            "novel_identity": {
                "official_title": "헌터갤러리의 국가권력급 기계공주",
                "heretic_url": "https://novelpia.com/novel/390228",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "헌터갤러리의 국가권력급 기계공주",
                "heretic_url": "https://novelpia.com/novel/390228",
                "alias_or_mention": "기계공주",
                "source_tier": "official_detail",
                "page_type": "novel_page",
                "reference_role": "primary",
            },
            "candidate_preservation_sources": [
                {
                    "official_title": "헌터갤러리의 국가권력급 기계공주",
                    "heretic_url": "https://novelpia.com/novel/390228",
                    "alias_or_mention": "기계공주",
                    "source_tier": "official_detail",
                    "page_type": "novel_page",
                    "reference_role": "primary",
                }
            ],
        }

        precision_blocked = apply_judge_seed_precision_guard(
            identity,
            {"seed_bucket": "precision_identity_high", "disagreement_type": "garbage_title"},
        )
        weak_blocked = apply_weak_public_title_bridge_guard(identity, "기계공주 작가 여초딩임?")
        fields = apply_candidate_audit_fields(
            identity,
            {"seed_bucket": "precision_identity_high", "disagreement_type": "garbage_title"},
        )

        self.assertEqual(precision_blocked, [])
        self.assertEqual(weak_blocked, [])
        self.assertEqual(identity["novel_identity"]["official_title"], "헌터갤러리의 국가권력급 기계공주")
        self.assertEqual(fields["candidate_ledger_status"], "safe_resolved")

    def test_weak_alias_bridge_canonicalizes_same_url_before_demote(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "anchor_type": "title_alias",
            "anchor_strength": "medium",
            "context_sources": ["title", "search", "image"],
            "consistency_flags": [
                "verified_alias_official_detail_anchor",
                "confirmed_alias:기계공주",
                "official_url_recall_gate_recovered",
            ],
            "novel_identity": {
                "official_title": "헌터갤러리의 국가권력급",
                "heretic_url": "https://novelpia.com/novel/390228",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "헌터갤러리의 국가권력급",
                "heretic_url": "https://novelpia.com/novel/390228",
                "alias_or_mention": "기계공주",
                "source_tier": "official_detail",
                "page_type": "novel_page",
                "reference_role": "primary",
            },
            "title_candidates": [
                {
                    "official_title": "헌터갤러리의 국가권력급 기계공주",
                    "heretic_url": "https://novelpia.com/novel/390228",
                    "alias_or_mention": "기계공주",
                    "source_tier": "official_detail",
                    "page_type": "novel_page",
                    "reference_role": "candidate",
                }
            ],
        }

        weak_blocked = apply_weak_public_title_bridge_guard(identity, "기계공주는 작가가 일러를 잘 뽑음")
        fields = apply_candidate_audit_fields(
            identity,
            {"seed_bucket": "precision_identity_high", "disagreement_type": "garbage_title"},
        )

        self.assertEqual(weak_blocked, [])
        self.assertEqual(identity["novel_identity"]["official_title"], "헌터갤러리의 국가권력급 기계공주")
        self.assertIn("same_url_official_detail_canonicalized", identity["consistency_flags"])
        self.assertEqual(fields["candidate_ledger_status"], "safe_resolved")

    def test_platform_seo_suffix_is_removed_from_official_detail_title(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "anchor_type": "image",
            "anchor_strength": "high",
            "context_sources": ["title", "search", "image"],
            "consistency_flags": ["same_url_official_detail_canonicalized"],
            "novel_identity": {
                "official_title": "이거 럽코 빙의물인가요 - 문피아 웹소설",
                "heretic_url": "https://novel.munpia.com/533816",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "이거 럽코 빙의물인가요 - 문피아 웹소설",
                "heretic_url": "https://novel.munpia.com/533816",
                "alias_or_mention": "이거 럽코 빙의물인가요",
                "source_tier": "official_detail",
                "page_type": "novel_page",
                "reference_role": "primary",
            },
            "title_candidates": [
                {
                    "official_title": "이거 럽코 빙의물인가요 - 문피아 웹소설",
                    "heretic_url": "https://novel.munpia.com/533816",
                    "alias_or_mention": "이거 럽코 빙의물인가요",
                    "source_tier": "official_detail",
                    "page_type": "novel_page",
                    "reference_role": "primary",
                }
            ],
        }

        weak_blocked = apply_weak_public_title_bridge_guard(identity, "좆 됐 다 ! !")
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(weak_blocked, [])
        self.assertEqual(identity["novel_identity"]["official_title"], "이거 럽코 빙의물인가요")
        self.assertEqual(identity["primary_work"]["official_title"], "이거 럽코 빙의물인가요")
        self.assertEqual(identity["title_candidates"][0]["official_title"], "이거 럽코 빙의물인가요")
        self.assertIn("platform_seo_title_suffix_canonicalized", identity["consistency_flags"])
        self.assertEqual(fields["candidate_ledger_status"], "safe_resolved")

    def test_ocr_lpko_variant_does_not_conflict_with_same_official_detail_title(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "anchor_type": "image",
            "anchor_strength": "high",
            "context_sources": ["title", "search", "image"],
            "consistency_flags": [
                "same_url_official_detail_canonicalized",
                "confirmed_alias:Lp코 빙의물",
                "explicit_alias_official_work_lock",
            ],
            "novel_identity": {
                "official_title": "이거 럽 코 빙의물인가요 - 웹소설 문피아",
                "heretic_url": "https://novel.munpia.com/533816",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "이거 럽 코 빙의물인가요 - 웹소설 문피아",
                "heretic_url": "https://novel.munpia.com/533816",
                "source_tier": "official_detail",
                "page_type": "novel_page",
                "reference_role": "primary",
            },
            "title_candidates": [
                {
                    "official_title": "이거 럽 코 빙의물인가요 - 웹소설 문피아",
                    "heretic_url": "https://novel.munpia.com/533816",
                    "source_tier": "official_detail",
                    "page_type": "novel_page",
                    "reference_role": "primary",
                }
            ],
            "image_evidence_catalog": [
                {
                    "explicit_work_title": "이거 Lp코 빙의물인가요",
                    "title_role": "work_title",
                    "promotion_eligible": True,
                }
            ],
        }

        weak_blocked = apply_weak_public_title_bridge_guard(identity, "좆 됐 다 ! !")
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(weak_blocked, [])
        self.assertEqual(identity["novel_identity"]["official_title"], "이거 럽코 빙의물인가요")
        self.assertEqual(identity["primary_work"]["official_title"], "이거 럽코 빙의물인가요")
        self.assertIn("platform_seo_title_suffix_canonicalized", identity["consistency_flags"])
        self.assertEqual(fields["candidate_ledger_status"], "safe_resolved")

    def test_platform_seo_prefix_is_removed_from_official_detail_title(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "anchor_type": "image",
            "anchor_strength": "high",
            "novel_identity": {
                "official_title": "웹소설로 꿈꾸는 세상! - [림월드]변방계에서 회귀자로 살아남기",
                "heretic_url": "https://novelpia.com/novel/382324",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "웹소설로 꿈꾸는 세상! - [림월드]변방계에서 회귀자로 살아남기",
                "heretic_url": "https://novelpia.com/novel/382324",
                "source_tier": "official_detail",
                "page_type": "novel_page",
                "reference_role": "primary",
            },
            "title_candidates": [
                {
                    "official_title": "웹소설로 꿈꾸는 세상! - [림월드]변방계에서 회귀자로 살아남기",
                    "heretic_url": "https://novelpia.com/novel/382324",
                    "source_tier": "official_detail",
                    "page_type": "novel_page",
                    "reference_role": "primary",
                }
            ],
        }

        weak_blocked = apply_weak_public_title_bridge_guard(identity, "랫따싶 림월드 요소 생각나게 하는거 좋네에...")
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(weak_blocked, [])
        self.assertEqual(identity["novel_identity"]["official_title"], "[림월드]변방계에서 회귀자로 살아남기")
        self.assertEqual(identity["primary_work"]["official_title"], "[림월드]변방계에서 회귀자로 살아남기")
        self.assertIn("platform_seo_title_suffix_canonicalized", identity["consistency_flags"])
        self.assertEqual(fields["candidate_ledger_status"], "safe_resolved")

    def test_precision_seed_bypass_respects_hard_non_novel_context(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "anchor_type": "title_alias",
            "anchor_strength": "medium",
            "context_sources": ["title", "body", "comments", "search"],
            "consistency_flags": [
                "official_url_recall_blocked_hard_non_novel_context",
                "fanfic_derivative_title_unanchored_hold",
                "verified_alias_official_detail_anchor",
                "confirmed_alias:리제로",
                "explicit_alias_official_work_lock",
            ],
            "novel_identity": {
                "official_title": "(리제로)RE: 제로부터 다시 시작하는 이세계 생활",
                "heretic_url": "https://novelpia.com/novel/53722",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "(리제로)RE: 제로부터 다시 시작하는 이세계 생활",
                "heretic_url": "https://novelpia.com/novel/53722",
                "alias_or_mention": "리제로",
                "source_tier": "official_detail",
                "reference_role": "primary",
            },
            "candidate_preservation_sources": [
                {
                    "official_title": "(리제로)RE: 제로부터 다시 시작하는 이세계 생활",
                    "heretic_url": "https://novelpia.com/novel/53722",
                    "alias_or_mention": "리제로",
                    "source_tier": "official_detail",
                    "reference_role": "primary",
                }
            ],
        }

        blocked = apply_judge_seed_precision_guard(
            identity,
            {"seed_bucket": "precision_identity_high", "disagreement_type": "garbage_title"},
        )
        fields = apply_candidate_audit_fields(
            identity,
            {"seed_bucket": "precision_identity_high", "disagreement_type": "garbage_title"},
        )

        self.assertIn("precision_seed_official_title_requires_review", blocked)
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")

    def test_title_noisy_ocr_unresolved_candidate_is_hold_unresolved(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": False,
            "title_resolution_allowed": False,
            "title_resolution_state": "multi_work",
            "work_resolution": "multi_work",
            "discussion_type": "character_talk",
            "novel_identity": None,
            "title_candidates": [{"title": "판초 우의의 마법사"}],
        }

        fields = apply_candidate_audit_fields(
            identity,
            {"disagreement_type": "title_noisy_ocr"},
        )

        self.assertEqual(fields["candidate_ledger_status"], "hold_unresolved")
        self.assertTrue(fields["hold_unresolved"])
        self.assertEqual(fields["output_consistency_lint"], [])

    def test_image_ocr_explicit_weak_title_is_candidate_preserved_not_promoted(self):
        identity = {
            "is_relevant": False,
            "is_novel_related": True,
            "is_resolved_work_discussion": False,
            "title_resolution_allowed": False,
            "title_resolution_state": "ocr_explicit_title_unresolved",
            "work_resolution": "unresolved",
            "discussion_type": "recommendation",
            "topicality": "adjacent_relevant",
            "anchor_type": "image",
            "novel_identity": None,
            "image_evidence_catalog": [
                {
                    "explicit_work_title": "림월드",
                    "title_role": "unknown",
                    "promotion_eligible": False,
                    "work_cues": ["림월드", "랫킨모드", "2D 시네마틱 일러스트"],
                }
            ],
        }

        fields = apply_candidate_audit_fields(
            identity,
            {
                "seed_bucket": "recall_relevance_representative",
                "disagreement_type": "under_resolved_false_negative",
            },
        )

        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        self.assertEqual(fields["candidate_ledger"]["candidate_count"], 1)
        self.assertEqual(fields["candidate_ledger"]["title_candidates"], ["림월드"])
        self.assertFalse(fields["hold_without_candidates"])
        self.assertIsNone(identity["novel_identity"])

    def test_image_visual_cues_without_explicit_title_do_not_create_candidate(self):
        identity = {
            "is_relevant": False,
            "is_novel_related": True,
            "is_resolved_work_discussion": False,
            "title_resolution_allowed": False,
            "title_resolution_state": "ocr_explicit_title_unresolved",
            "work_resolution": "unresolved",
            "discussion_type": "recommendation",
            "anchor_type": "image",
            "novel_identity": None,
            "image_evidence_catalog": [
                {
                    "title_role": "unknown",
                    "promotion_eligible": False,
                    "work_cues": ["2D 시네마틱 일러스트", "모드"],
                }
            ],
        }

        fields = apply_candidate_audit_fields(
            identity,
            {
                "seed_bucket": "recall_relevance_representative",
                "disagreement_type": "under_resolved_false_negative",
            },
        )

        self.assertEqual(fields["candidate_ledger_status"], "hold_without_candidates")
        self.assertEqual(fields["candidate_ledger"]["candidate_count"], 0)
        self.assertTrue(fields["hold_without_candidates"])

    def test_completed779_under_resolved_seed_is_recall_hold(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": False,
            "title_resolution_allowed": False,
            "title_resolution_state": "unresolved_matchable",
            "work_resolution": "unresolved",
            "discussion_type": "general",
            "novel_identity": None,
        }

        fields = apply_candidate_audit_fields(
            identity,
            {
                "seed_bucket": "recall_relevance_representative",
                "disagreement_type": "under_resolved",
            },
        )

        self.assertEqual(fields["candidate_ledger"]["judge_seed_group"], "recall")
        self.assertEqual(fields["candidate_ledger_status"], "hold_without_candidates")
        self.assertFalse(fields["candidate_generation_miss"])
        self.assertTrue(fields["hold_without_candidates"])

    def test_completed779_recall_seed_preserves_audit_snapshot_candidates(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": False,
            "title_resolution_allowed": False,
            "title_resolution_state": "unresolved_matchable",
            "work_resolution": "unresolved",
            "discussion_type": "recommendation",
            "novel_identity": None,
            "candidate_preservation_sources": [
                {
                    "official_title": "이세계 TRPG 게임마스터",
                    "heretic_url": "https://novelpia.com/novel/370230",
                    "preservation_role": "recommendation_candidate",
                }
            ],
        }

        fields = apply_candidate_audit_fields(
            identity,
            {
                "seed_bucket": "recall_relevance_representative",
                "disagreement_type": "under_resolved",
            },
        )

        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        self.assertEqual(fields["candidate_ledger"]["candidate_count"], 1)
        self.assertEqual(
            fields["candidate_ledger"]["title_candidates"],
            ["이세계 TRPG 게임마스터"],
        )
        self.assertFalse(fields["hold_without_candidates"])

    def test_comment_multi_seed_candidates_are_promotion_blocked_not_generation_miss(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": False,
            "title_resolution_allowed": False,
            "title_resolution_state": "multi_work",
            "work_resolution": "multi_work",
            "discussion_type": "recommendation",
            "novel_identity": None,
            "title_candidates": [
                {"title": "사연 있는 악역으로 착각 당한다"},
                {"title": "제발 죽지 말아주세요, 공녀님"},
            ],
        }

        fields = apply_candidate_audit_fields(
            identity,
            {
                "seed_bucket": "candidate_comment_multi",
                "disagreement_type": "comment_explicit_title_missed",
            },
        )

        self.assertEqual(fields["candidate_ledger"]["judge_seed_group"], "candidate")
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        self.assertFalse(fields["candidate_generation_miss"])
        self.assertEqual(fields["candidate_ledger"]["candidate_count"], 2)

    def test_comment_surface_hint_preserves_recommendation_candidates_without_promotion(self):
        identity = {
            "is_relevant": False,
            "is_novel_related": True,
            "is_resolved_work_discussion": False,
            "title_resolution_allowed": False,
            "title_resolution_state": "adjacent",
            "work_resolution": "none",
            "discussion_type": "recommendation",
            "novel_identity": None,
        }

        added = apply_comment_surface_candidate_hints(
            identity,
            [
                "그롬 당신을 위한 비자발적 독재자 재밌다 존나 ㄱㄱ",
                "문피아의 목마신작, 즉사무림, 판초법사",
                "그거 병진이잖아",
                "양치기 초반 이후로 그닥 재미없어서 아쉬웠는데 신작은 좀 낫냐",
            ],
        )
        fields = apply_candidate_audit_fields(
            identity,
            {
                "seed_bucket": "candidate_comment_multi",
                "disagreement_type": "conflicting_or_multi_candidate",
            },
        )

        self.assertEqual(added, ["비자발적 독재자", "목마신작", "즉사무림", "판초법사"])
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        self.assertEqual(fields["candidate_ledger"]["candidate_count"], 4)
        self.assertFalse(fields["candidate_generation_miss"])
        self.assertIsNone(identity["novel_identity"])

    def test_comment_surface_hint_ignores_user_mentions(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": False,
            "title_resolution_allowed": False,
            "title_resolution_state": "author_new_work_context",
            "work_resolution": "none",
            "discussion_type": "recommendation",
            "novel_identity": None,
        }

        added = apply_comment_surface_candidate_hints(identity, ["@ㅇㅇ", "@reader 잘생인편 봤냐"])

        self.assertEqual(added, [])
        self.assertNotIn("comment_surface_title_candidates", identity)

    def test_recall_seed_expected_candidate_blocks_conflicting_final_title(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "review",
            "novel_identity": {
                "official_title": "양치기 마법사",
                "heretic_url": "https://m.munpia.com/novel/detail/429248",
                "confidence": "High",
            },
        }
        seed = {
            "seed_bucket": "recall_relevance_representative",
            "disagreement_type": "under_resolved",
            "independent_official_title": "몰락민족의 천재 기사",
            "independent_url": "https://series.naver.com/novel/detail.series?productNo=13683859",
        }

        reasons = apply_judge_seed_expected_candidate_preservation(identity, seed)
        fields = apply_candidate_audit_fields(identity, seed)

        self.assertIn("judge_recall_seed_expected_title_conflict_under_resolved", reasons)
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(identity["blocked_official_title"], "양치기 마법사")
        self.assertEqual(identity["expected_official_title_conflict"], "몰락민족의 천재 기사")
        self.assertEqual(identity["title_resolution_state"], "unresolved_matchable")
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        self.assertIn("몰락민족의 천재 기사", fields["candidate_ledger"]["title_candidates"])

    def test_precision_seed_expected_url_is_preserved_when_final_url_mismatches(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "review",
            "novel_identity": {
                "official_title": "아카데미 속 미움받는 악역이 되었다",
                "heretic_url": "https://novelpia.com/novel/38",
                "confidence": "High",
            },
        }
        seed = {
            "seed_bucket": "precision_identity_high",
            "disagreement_type": "wrong_work",
            "independent_official_title": "아카데미 속 미움받는 악역이 되었다",
            "independent_url": "https://novelpia.com/novel/387035",
        }

        reasons = apply_judge_seed_expected_candidate_preservation(identity, seed)
        fields = apply_candidate_audit_fields(identity, seed)

        self.assertIn("judge_precision_seed_expected_url_conflict_wrong_work", reasons)
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(identity["blocked_official_title_url"], "https://novelpia.com/novel/38")
        self.assertEqual(identity["expected_official_url_conflict"], "https://novelpia.com/novel/387035")
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        self.assertIn("아카데미 속 미움받는 악역이 되었다", fields["candidate_ledger"]["title_candidates"])

    def test_source_url_hygiene_seed_expected_title_is_preserved_as_candidate(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": False,
            "title_resolution_allowed": False,
            "title_resolution_state": "unresolved_matchable",
            "work_resolution": "unresolved",
            "discussion_type": "general",
            "novel_identity": None,
            "title_candidates": [
                {
                    "official_title": "아생갤",
                    "confidence": "Medium",
                    "source_tier": "post_title_surface",
                    "reference_role": "candidate",
                }
            ],
        }
        seed = {
            "seed_bucket": "source_url_hygiene",
            "disagreement_type": "reason_evidence_mismatch",
            "independent_official_title": "아카데미 생존 갤러리",
            "independent_url": "https://novelpia.com/novel/380218",
        }

        reasons = apply_judge_seed_expected_candidate_preservation(identity, seed)
        fields = apply_candidate_audit_fields(identity, seed)

        self.assertIn("judge_hygiene_seed_expected_candidate_preserved", reasons)
        self.assertIsNone(identity["novel_identity"])
        self.assertEqual(fields["candidate_ledger_status"], "output_consistency_lint")
        self.assertIn("아카데미 생존 갤러리", fields["candidate_ledger"]["title_candidates"])
        self.assertTrue(
            any(
                item.get("preservation_role") == "hygiene_expected_candidate"
                and item.get("heretic_url") == "https://novelpia.com/novel/380218"
                for item in fields["candidate_ledger"]["candidate_preservation_sources"]
            )
        )

    def test_trope_boundary_seed_blocks_public_title_but_preserves_candidate(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "topicality": "core_relevant",
            "novel_identity": {
                "official_title": "괴담 호텔 탈출기",
                "heretic_url": "https://novelpia.com/novel/102155",
                "confidence": "Medium",
            },
            "primary_work": {
                "official_title": "괴담 호텔 탈출기",
                "heretic_url": "https://novelpia.com/novel/102155",
                "source_tier": "official_detail",
                "reference_role": "primary",
            },
            "reason_lines": [
                "- 공식 제목: '괴담 호텔 탈출기'",
                "- 최종 공식 제목은 '괴담 호텔 탈출기'로 확정됨.",
                "- 제목/본문 앵커와 검색 근거를 종합하여 '괴담 호텔 탈출기' 관련 작품 토론으로 판정했습니다.",
            ],
        }
        seed = {
            "seed_bucket": "recall_relevance_representative",
            "disagreement_type": "trope_or_author_talk_risk",
            "independent_official_title": "괴담 호텔 탈출기",
            "independent_url": "https://novelpia.com/novel/102155",
        }

        apply_judge_seed_expected_candidate_preservation(identity, seed)
        reasons = apply_judge_seed_trope_boundary_hold_guard(identity, seed)
        fields = apply_candidate_audit_fields(identity, seed)

        self.assertIn("judge_trope_or_author_boundary_blocks_public_title", reasons)
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertFalse(identity["is_resolved_work_discussion"])
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertEqual(identity["title_resolution_state"], "adjacent")
        self.assertEqual(identity["discussion_type"], "trope_discussion")
        self.assertEqual(identity["primary_work"]["reference_role"], "trope_boundary_candidate")
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        self.assertIn("괴담 호텔 탈출기", fields["candidate_ledger"]["title_candidates"])
        self.assertNotIn("확정됨", "\n".join(str(line) for line in identity["reason_lines"]))
        self.assertIn("후보로 보존", "\n".join(str(line) for line in identity["reason_lines"]))

    def test_expected_candidate_conflict_marks_wrong_primary_as_blocked(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "review",
            "novel_identity": {
                "official_title": "7인의 피카레스크",
                "heretic_url": "https://novelpia.com/novel/396754",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "7인의 피카레스크",
                "heretic_url": "https://novelpia.com/novel/396754",
                "source_tier": "official_detail",
                "reference_role": "primary",
            },
            "reason_lines": [
                "- 공식 제목: '7인의 피카레스크'",
                "- 제목/본문 앵커와 검색 근거를 종합하여 '7인의 피카레스크' 관련 작품 토론으로 판정했습니다.",
                "- 최종 공식 제목은 '7인의 피카레스크'로 확정됨.",
            ],
        }
        seed = {
            "seed_bucket": "precision_identity_high",
            "disagreement_type": "wrong_work",
            "independent_official_title": "나의 악당들",
            "independent_url": "https://page.kakao.com/content/55826557",
        }

        reasons = apply_judge_seed_expected_candidate_preservation(identity, seed)
        fields = apply_candidate_audit_fields(identity, seed)

        self.assertIn("judge_precision_seed_expected_title_conflict_wrong_work", reasons)
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(identity["primary_work"]["reference_role"], "blocked_primary_work")
        self.assertEqual(identity["primary_work"]["promotion_policy"], "hold_without_promotion")
        self.assertEqual(identity["primary_work"]["blocked_by_judge_seed_expected_title"], "나의 악당들")
        self.assertIn("blocked_primary_work_conflict", identity["output_consistency_lint"])
        self.assertIn("나의 악당들", fields["candidate_ledger"]["title_candidates"])
        reason_text = "\n".join(str(line) for line in identity["reason_lines"])
        self.assertNotIn("확정됨", reason_text)
        self.assertIn("후보/HOLD로 보존", reason_text)
        self.assertIn("judge_precision_seed_conflict", reason_text)
        self.assertNotIn("확정됨", identity["reason"])
        self.assertIn("후보/HOLD로 보존", identity["reason"])

    def test_llm_only_sentence_candidates_are_pruned_but_evidence_candidates_remain(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": False,
            "title_resolution_allowed": False,
            "title_resolution_state": "unresolved_matchable",
            "work_resolution": "unresolved",
            "discussion_type": "general",
            "novel_identity": None,
            "title_candidates": [
                {
                    "official_title": "양치기 초반 이후로 그닥 재미없어서 아쉬웠는데 신작은 좀 낫냐",
                    "source_tier": "llm_only",
                    "reference_role": "candidate",
                },
                {
                    "official_title": "양치기 마법사",
                    "heretic_url": "https://m.munpia.com/novel/detail/429248",
                    "source_tier": "official_detail",
                },
                {
                    "official_title": "몰락민족의 천재 기사",
                    "heretic_url": "https://series.naver.com/novel/detail.series?productNo=13683859",
                    "source_tier": "judge_seed_expected",
                },
                {
                    "title": "ㄹㅇ 웹소에 널림...  - dc App",
                    "source_tier": "comment_surface",
                    "reference_role": "candidate",
                },
            ],
            "candidate_preservation_sources": [
                {
                    "official_title": "시발 언제와 그거",
                    "source_tier": "llm_only",
                    "reference_role": "candidate",
                },
                {
                    "official_title": "몰락민족의 천재 기사",
                    "heretic_url": "https://series.naver.com/novel/detail.series?productNo=13683859",
                    "source_tier": "judge_seed_expected",
                },
            ],
        }

        fields = apply_candidate_audit_fields(
            identity,
            {
                "seed_bucket": "recall_relevance_representative",
                "disagreement_type": "under_resolved_false_negative",
            },
        )

        self.assertEqual(
            identity["candidate_pruned_llm_only_surfaces"],
            [
                "양치기 초반 이후로 그닥 재미없어서 아쉬웠는데 신작은 좀 낫냐",
                "ㄹㅇ 웹소에 널림...  - dc App",
                "시발 언제와 그거",
            ],
        )
        self.assertIn("llm_only_sentence_candidate_pruned", identity["candidate_audit_lint"])
        self.assertNotIn(
            "양치기 초반 이후로 그닥 재미없어서 아쉬웠는데 신작은 좀 낫냐",
            fields["candidate_ledger"]["title_candidates"],
        )
        self.assertIn("양치기 마법사", fields["candidate_ledger"]["title_candidates"])
        self.assertIn("몰락민족의 천재 기사", fields["candidate_ledger"]["title_candidates"])

    def test_hygiene_expected_candidate_pollution_is_linted(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": False,
            "title_resolution_allowed": False,
            "title_resolution_state": "unresolved_matchable",
            "work_resolution": "unresolved",
            "discussion_type": "character_talk",
            "novel_identity": None,
            "title_candidates": [
                {
                    "official_title": "오늘의 3학년 1반",
                    "heretic_url": "https://m.munpia.com/novel/detail/61138",
                    "source_tier": "official_detail",
                    "reference_role": "primary",
                },
                {
                    "official_title": "어제의 너에게, 오늘의 나에게",
                    "heretic_url": "https://m.munpia.com/novel/detail/460459",
                    "source_tier": "mixed",
                    "reference_role": "primary",
                },
                {
                    "official_title": "아카데미 생존 갤러리",
                    "heretic_url": "https://novelpia.com/novel/380218",
                    "source_tier": "judge_seed_expected",
                    "reference_role": "candidate",
                },
            ],
        }
        seed = {
            "seed_bucket": "source_url_hygiene",
            "disagreement_type": "reason_evidence_mismatch",
            "independent_official_title": "아카데미 생존 갤러리",
            "independent_url": "https://novelpia.com/novel/380218",
        }

        fields = apply_candidate_audit_fields(identity, seed)

        self.assertIn(
            "judge_hygiene_seed_expected_candidate_polluted_by_concrete_alternates",
            fields["candidate_audit_lint"],
        )
        self.assertIn(
            "judge_hygiene_seed_expected_candidate_polluted_by_concrete_alternates",
            fields["candidate_ledger"]["candidate_audit_lint_reasons"],
        )
        self.assertIn("아카데미 생존 갤러리", fields["candidate_ledger"]["title_candidates"])

    def test_judge_expected_multi_title_member_is_not_pruned_as_llm_only_noise(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": False,
            "title_resolution_allowed": False,
            "title_resolution_state": "multi_work",
            "work_resolution": "multi_work",
            "discussion_type": "recommendation",
            "novel_identity": None,
            "title_candidates": [
                {
                    "official_title": "1990 할리우드 망나니 배우가 되었다",
                    "source_tier": "llm_only",
                    "reference_role": "candidate",
                },
                {
                    "official_title": "시리즈 기다리는 중인데 이새끼들 언제옴",
                    "source_tier": "llm_only",
                    "reference_role": "candidate",
                },
            ],
        }
        seed = {
            "seed_bucket": "recall_relevance_representative",
            "disagreement_type": "under_resolved_false_negative",
            "independent_official_title": (
                "multiple: 1990 할리우드 망나니 배우가 되었다; 포수가 육아를 잘함; "
                "미국 트럭커가 골동품으로 대박남; 몰락민족의 천재 기사"
            ),
        }

        fields = apply_candidate_audit_fields(identity, seed)

        self.assertIn("1990 할리우드 망나니 배우가 되었다", fields["candidate_ledger"]["title_candidates"])
        self.assertNotIn("1990 할리우드 망나니 배우가 되었다", identity["candidate_pruned_llm_only_surfaces"])
        self.assertIn("시리즈 기다리는 중인데 이새끼들 언제옴", identity["candidate_pruned_llm_only_surfaces"])
        self.assertNotIn("시리즈 기다리는 중인데 이새끼들 언제옴", fields["candidate_ledger"]["title_candidates"])

    def test_ocr_work_cues_are_preserved_for_multi_work_candidate_ledger(self):
        identity = {
            "is_relevant": False,
            "is_novel_related": True,
            "is_resolved_work_discussion": False,
            "title_resolution_allowed": False,
            "title_resolution_state": "adjacent",
            "work_resolution": "none",
            "discussion_type": "author_talk",
            "novel_identity": None,
            "image_evidence_catalog": [
                {
                    "evidence_type": "explicit_text",
                    "title_role": "unknown",
                    "promotion_eligible": False,
                    "work_cues": [
                        "1990 할리우드 망나니 배우가 되었다",
                        "포수가 육아를 잘함",
                        "미국 트러커가 골동품으로 대박남",
                        "몰락민족의 천재 기사",
                        "KAKAOPAGE",
                        "작가 홍길동",
                        "조회 12.3만",
                        "추천 421",
                        "12회차",
                        "2D 시네마틱 일러스트",
                    ],
                }
            ],
        }

        fields = apply_candidate_audit_fields(
            identity,
            {
                "seed_bucket": "recall_relevance_representative",
                "disagreement_type": "under_resolved_false_negative",
            },
        )

        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        for title in (
            "1990 할리우드 망나니 배우가 되었다",
            "포수가 육아를 잘함",
            "미국 트러커가 골동품으로 대박남",
            "몰락민족의 천재 기사",
        ):
            self.assertIn(title, fields["candidate_ledger"]["title_candidates"])
        for non_title in (
            "KAKAOPAGE",
            "작가 홍길동",
            "조회 12.3만",
            "추천 421",
            "12회차",
            "2D 시네마틱 일러스트",
        ):
            self.assertNotIn(non_title, fields["candidate_ledger"]["title_candidates"])

    def test_source_url_hygiene_reason_mismatch_lints_without_precision_demote(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "review",
            "novel_identity": {
                "official_title": "아카데미 생존 갤러리",
                "heretic_url": "https://novelpia.com/novel/415486",
                "confidence": "High",
            },
        }
        seed = {
            "seed_bucket": "source_url_hygiene",
            "disagreement_type": "reason_evidence_mismatch",
            "independent_official_title": "아카데미 생존 갤러리",
            "independent_url": "https://novelpia.com/novel/380218",
        }

        blocked = apply_judge_seed_precision_guard(identity, seed)
        fields = apply_candidate_audit_fields(identity, seed)

        self.assertEqual(blocked, [])
        self.assertEqual(identity["novel_identity"]["official_title"], "아카데미 생존 갤러리")
        self.assertEqual(fields["candidate_ledger"]["judge_seed_group"], "hygiene")
        self.assertEqual(fields["candidate_ledger_status"], "output_consistency_lint")
        self.assertIn("judge_hygiene_seed_reason_evidence_mismatch", fields["output_consistency_lint"])

    def test_source_url_hygiene_garbage_title_bucket_does_not_precision_demote(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "novel_identity": {
                "official_title": "괴담 호텔 탈출기",
                "heretic_url": "https://novelpia.com/novel/102155",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "괴담 호텔 탈출기",
                "heretic_url": "https://novelpia.com/novel/102155",
                "source_tier": "official_detail",
            },
        }
        seed = {
            "seed_bucket": "source_url_hygiene",
            "disagreement_type": "garbage_title",
            "independent_official_title": "괴담 호텔 탈출기",
            "independent_url": "https://novelpia.com/novel/102155",
        }

        blocked = apply_judge_seed_precision_guard(identity, seed)
        conflict = apply_judge_seed_hygiene_expected_title_guard(identity, seed)
        fields = apply_candidate_audit_fields(identity, seed)

        self.assertEqual(blocked, [])
        self.assertEqual(conflict, [])
        self.assertEqual(identity["novel_identity"]["official_title"], "괴담 호텔 탈출기")
        self.assertEqual(identity["novel_identity"]["heretic_url"], "https://novelpia.com/novel/102155")
        self.assertEqual(fields["candidate_ledger"]["judge_seed_group"], "hygiene")
        self.assertEqual(fields["candidate_ledger_status"], "output_consistency_lint")
        self.assertIn("judge_hygiene_seed_garbage_title", fields["output_consistency_lint"])

    def test_hygiene_alias_image_conflict_blocks_public_title(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "novel_identity": {
                "official_title": "괴담 호텔 탈출기",
                "heretic_url": "https://novelpia.com/novel/102155",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "괴담 호텔 탈출기",
                "heretic_url": "https://novelpia.com/novel/102155",
                "confidence": "High",
                "alias_or_mention": "괴담텔",
                "source_tier": "official_detail",
                "reference_role": "primary",
            },
            "consistency_flags": [
                "vlm_ocr_title_conflict_with_final_title",
                "ocr_title_conflict_with_stable_alias",
            ],
            "image_evidence_catalog": [
                {
                    "explicit_work_title": "狐神神社",
                    "evidence_type": "explicit_text",
                    "promotion_eligible": False,
                }
            ],
        }
        seed = {
            "seed_group": "candidate_comment_multi",
            "disagreement_type": "wrong_relevance",
            "severity": "high",
        }

        blocked = apply_judge_seed_hygiene_alias_conflict_guard(identity, seed)
        fields = apply_candidate_audit_fields(identity, seed)

        self.assertEqual(blocked, ["judge_hygiene_seed_alias_image_conflict_wrong_relevance"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertIsNone(identity["novel_identity"]["heretic_url"])
        self.assertEqual(identity["blocked_official_title"], "괴담 호텔 탈출기")
        self.assertEqual(identity["blocked_official_title_url"], "https://novelpia.com/novel/102155")
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertEqual(identity["work_resolution"], "unresolved")
        self.assertEqual(fields["candidate_ledger"]["judge_seed_group"], "hygiene")
        self.assertEqual(fields["candidate_ledger_status"], "output_consistency_lint")
        self.assertIn(
            "judge_hygiene_seed_alias_image_conflict_wrong_relevance",
            fields["output_consistency_lint"],
        )

    def test_hygiene_alias_guard_does_not_block_without_image_conflict(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "novel_identity": {
                "official_title": "괴담 호텔 탈출기",
                "heretic_url": "https://novelpia.com/novel/102155",
                "confidence": "High",
            },
            "consistency_flags": ["ocr_title_conflict_with_stable_alias"],
        }
        seed = {
            "seed_group": "candidate_comment_multi",
            "disagreement_type": "wrong_relevance",
        }

        blocked = apply_judge_seed_hygiene_alias_conflict_guard(identity, seed)

        self.assertEqual(blocked, [])
        self.assertEqual(identity["novel_identity"]["official_title"], "괴담 호텔 탈출기")
        self.assertTrue(identity["title_resolution_allowed"])

    def test_wrong_relevance_seed_public_title_is_candidate_hold(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "anchor_type": "none",
            "anchor_strength": "none",
            "primary_subject_type": "multi_work_bundle",
            "consistency_flags": [
                "official_url_recall_gate_recovered",
                "search_catalog_contextual_work:온세상이 온세상 세상이",
                "search_catalog_contextual_work_recall_anchor",
                "confirmed_context:온세상이 온세상 세상이",
            ],
            "novel_identity": {
                "official_title": "온 세상이 정신이상자다",
                "heretic_url": "https://novelpia.com/novel/380804",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "온 세상이 정신이상자다",
                "heretic_url": "https://novelpia.com/novel/380804",
                "confidence": "High",
                "alias_or_mention": "온세상이 온세상 세상이",
                "source_tier": "official_detail",
                "page_type": "novel_page",
                "reference_role": "primary",
            },
        }
        seed = {
            "seed_bucket": "candidate_comment_multi",
            "disagreement_type": "wrong_relevance",
            "severity": "high",
        }

        blocked = apply_judge_seed_wrong_relevance_public_title_guard(identity, seed)
        fields = apply_candidate_audit_fields(identity, seed)

        self.assertEqual(blocked, ["judge_candidate_seed_wrong_relevance_public_title_held"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertIsNone(identity["novel_identity"]["heretic_url"])
        self.assertEqual(identity["blocked_official_title"], "온 세상이 정신이상자다")
        self.assertEqual(identity["blocked_official_title_url"], "https://novelpia.com/novel/380804")
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertEqual(identity["work_resolution"], "unresolved")
        self.assertIn("온 세상이 정신이상자다", fields["candidate_ledger"]["title_candidates"])
        self.assertEqual(fields["candidate_ledger_status"], "output_consistency_lint")
        self.assertIn(
            "judge_candidate_seed_wrong_relevance_public_title_held",
            fields["output_consistency_lint"],
        )

    def test_source_url_hygiene_wrong_expected_title_is_demoted(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "review",
            "novel_identity": {
                "official_title": "가챠 중독자의 퓨전펑크 생활",
                "heretic_url": "https://novelpia.com/novel/387014",
                "confidence": "High",
            },
            "reason_lines": [
                "- 공식 제목: '가챠 중독자의 퓨전펑크 생활'",
                "- 제목/본문 앵커와 검색 근거를 종합하여 '가챠 중독자의 퓨전펑크 생활' 관련 작품 토론으로 판정했습니다.",
                "- 최종 공식 제목은 '가챠 중독자의 퓨전펑크 생활'로 확정됨.",
            ],
        }
        seed = {
            "seed_bucket": "source_url_hygiene",
            "disagreement_type": "title_correct_url_mismatch",
            "independent_official_title": "아카데미 생존 갤러리",
            "independent_url": "https://novelpia.com/novel/380218",
        }

        blocked = apply_judge_seed_hygiene_expected_title_guard(identity, seed)
        fields = apply_candidate_audit_fields(identity, seed)

        self.assertEqual(blocked, ["judge_hygiene_seed_expected_title_conflict_title_correct_url_mismatch"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertIsNone(identity["novel_identity"]["heretic_url"])
        self.assertEqual(identity["blocked_official_title"], "가챠 중독자의 퓨전펑크 생활")
        self.assertEqual(identity["expected_official_title_conflict"], "아카데미 생존 갤러리")
        self.assertEqual(identity["title_resolution_state"], "unresolved_matchable")
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertEqual(fields["candidate_ledger"]["judge_seed_group"], "hygiene")
        self.assertEqual(fields["candidate_ledger_status"], "output_consistency_lint")
        self.assertIn(
            "judge_hygiene_seed_expected_title_conflict_title_correct_url_mismatch",
            fields["output_consistency_lint"],
        )
        reason_text = "\n".join(str(line) for line in identity["reason_lines"])
        self.assertNotIn("확정됨", reason_text)
        self.assertIn("후보/HOLD로 보존", reason_text)
        self.assertIn("judge_hygiene_seed_conflict", reason_text)
        self.assertNotIn("확정됨", identity["reason"])
        self.assertIn("후보/HOLD로 보존", identity["reason"])

    def test_source_url_hygiene_ocr_close_title_variant_is_not_demoted(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "review",
            "novel_identity": {
                "official_title": "여대생 가랑이 사이 무릎 끓은 엄마들",
                "heretic_url": None,
                "confidence": "High",
            },
            "image_evidence_catalog": [
                {
                    "explicit_work_title": "여대생 가랑이 사이 무릎 끓은 엄마들",
                    "evidence_type": "explicit_text",
                    "title_role": "work_title",
                    "promotion_eligible": True,
                }
            ],
        }
        seed = {
            "seed_bucket": "source_url_hygiene",
            "disagreement_type": "heretic_url_null",
            "independent_official_title": "여대학생 가랑이 사이 무릎 꿇은 엄마들",
            "independent_url": None,
        }

        blocked = apply_judge_seed_hygiene_expected_title_guard(identity, seed)
        fields = apply_candidate_audit_fields(identity, seed)

        self.assertEqual(blocked, [])
        self.assertEqual(
            identity["novel_identity"]["official_title"],
            "여대생 가랑이 사이 무릎 끓은 엄마들",
        )
        self.assertEqual(identity["title_resolution_state"], "resolved")
        self.assertTrue(identity["title_resolution_allowed"])
        self.assertNotIn(
            "judge_hygiene_seed_expected_title_conflict_heretic_url_null",
            fields["output_consistency_lint"],
        )
        self.assertIn("judge_hygiene_seed_heretic_url_null", fields["output_consistency_lint"])

    def test_overresolved_generic_trope_seed_is_demoted_to_review_candidate(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "review",
            "novel_identity": {
                "official_title": "설정값 딸깍으로 판타지 시스템 정상화",
                "heretic_url": "https://novelpia.com/novel/399999",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "설정값 딸깍으로 판타지 시스템 정상화",
                "source_tier": "official_detail",
                "heretic_url": "https://novelpia.com/novel/399999",
            },
        }

        blocked = apply_judge_seed_precision_guard(
            identity,
            {
                "seed_bucket": "precision_identity_high",
                "disagreement_type": "overresolved_generic_trope",
            },
        )
        fields = apply_candidate_audit_fields(
            identity,
            {
                "seed_bucket": "precision_identity_high",
                "disagreement_type": "overresolved_generic_trope",
            },
        )

        self.assertEqual(blocked, ["precision_seed_official_title_requires_review"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(identity["blocked_official_title"], "설정값 딸깍으로 판타지 시스템 정상화")
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")

    def test_weak_alias_surface_public_title_bridge_is_held(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "anchor_type": "title_alias",
            "anchor_strength": "high",
            "novel_identity": {
                "official_title": "수상할 정도로 돈이 많은 성주님 1권 미리보기",
                "heretic_url": "https://ridibooks.com/books/3846015696/preview",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "수상할 정도로 돈이 많은 성주님 1권 미리보기",
                "heretic_url": "https://ridibooks.com/books/3846015696/preview",
                "confidence": "High",
                "alias_or_mention": "수상할 정도로",
                "source_tier": "official_detail",
            },
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "수상할 정도로 고해상도의 부모 캐릭터 보면")
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(blocked, ["weak_alias_surface_public_title_bridge"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(identity["blocked_official_title"], "수상할 정도로 돈이 많은 성주님 1권 미리보기")
        self.assertEqual(identity["title_resolution_state"], "unresolved_matchable")
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        self.assertIn("수상할 정도로 돈이 많은 성주님 1권 미리보기", fields["candidate_ledger"]["title_candidates"])

    def test_generic_genre_surface_public_title_bridge_is_held(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "anchor_type": "genre",
            "anchor_strength": "low",
            "novel_identity": {
                "official_title": "용사 파티",
                "heretic_url": "https://novelpia.com/novel/78257",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "용사 파티",
                "heretic_url": "https://novelpia.com/novel/78257",
                "confidence": "High",
                "source_tier": "official_detail",
            },
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "용사파티 << 비겁한 소수정예 암살단임")
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(blocked, ["generic_genre_surface_public_title_bridge"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")

    def test_generic_noun_verb_alias_bridge_is_held(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "anchor_type": "title_alias",
            "anchor_strength": "high",
            "novel_identity": {
                "official_title": "아카데미 특별전형 생도가 되었다",
                "heretic_url": "https://novelpia.com/novel/251984",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "아카데미 특별전형 생도가 되었다",
                "heretic_url": "https://novelpia.com/novel/251984",
                "confidence": "High",
                "alias_or_mention": "아카데미 되었다",
                "source_tier": "official_detail",
            },
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "로판속 아카데미 앞 두쫀쿠 가게 사장이 되었다")

        self.assertEqual(blocked, ["weak_alias_surface_public_title_bridge"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(identity["blocked_official_title"], "아카데미 특별전형 생도가 되었다")

    def test_template_overlap_official_detail_bridge_is_held_without_alias(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "meme",
            "anchor_type": "title_alias",
            "anchor_strength": "medium",
            "consistency_flags": ["vlm_ocr_title_conflict_with_final_title"],
            "novel_identity": {
                "official_title": "아카데미 야겜에 빙의했다.",
                "heretic_url": "https://novelpia.com/novel/1249",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "아카데미 야겜에 빙의했다.",
                "heretic_url": "https://novelpia.com/novel/1249",
                "confidence": "High",
                "source_tier": "official_detail",
                "locked": True,
            },
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "로판속 아카데미 앞 두쫀쿠 가게 사장이 되었다")

        self.assertEqual(blocked, ["weak_template_surface_public_title_bridge"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(identity["blocked_official_title"], "아카데미 야겜에 빙의했다.")
        self.assertEqual(identity["title_resolution_state"], "unresolved_matchable")

    def test_template_overlap_guard_keeps_direct_official_title_surface(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "anchor_type": "title_alias",
            "anchor_strength": "medium",
            "novel_identity": {
                "official_title": "아카데미 야겜에 빙의했다.",
                "heretic_url": "https://novelpia.com/novel/1249",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "아카데미 야겜에 빙의했다.",
                "heretic_url": "https://novelpia.com/novel/1249",
                "confidence": "High",
                "source_tier": "official_detail",
                "locked": True,
            },
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "아카데미 야겜에 빙의했다 재밌냐")

        self.assertEqual(blocked, [])
        self.assertEqual(identity["novel_identity"]["official_title"], "아카데미 야겜에 빙의했다.")

    def test_unconfirmed_alias_official_detail_bridge_is_held(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "anchor_type": "title_alias",
            "anchor_strength": "medium",
            "consistency_flags": ["batch_memory_exact_alias_rescued"],
            "novel_identity": {
                "official_title": "스페이스 오페라",
                "heretic_url": "https://novelpia.com/novel/181483",
                "confidence": "Medium",
            },
            "primary_work": {
                "official_title": "스페이스 오페라",
                "heretic_url": "https://novelpia.com/novel/181483",
                "confidence": "Medium",
                "alias_or_mention": "림월드",
                "source_tier": "official_detail",
            },
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "랫따싶 림월드 요소 생각나게 하는거 좋네에")
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(blocked, ["unconfirmed_alias_official_detail_bridge"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(identity["blocked_official_title"], "스페이스 오페라")
        self.assertEqual(identity["title_resolution_state"], "unresolved_matchable")
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        self.assertIn("스페이스 오페라", fields["candidate_ledger"]["title_candidates"])

    def test_title_led_consumption_alias_exempts_unconfirmed_official_detail_bridge(self):
        title = "탑의 성좌들이 날 애호한다"
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "primary_subject_type": "work_discussion",
            "anchor_type": "title_alias",
            "anchor_strength": "medium",
            "context_sources": ["title", "body", "comments", "search"],
            "consistency_flags": [
                "relation_hold_unresolved_recovered",
                "batch_memory_exact_alias_rescued",
                "batch_memory_alias_rescue_cleared_stale_demotions",
                "weak_public_title_bridge_batch_alias_exact_exempt",
            ],
            "novel_identity": {
                "official_title": title,
                "heretic_url": "https://novelpia.com/novel/377032",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": title,
                "heretic_url": "https://novelpia.com/novel/377032",
                "confidence": "High",
                "alias_or_mention": "탑성좌애호",
                "source_tier": "official_detail",
                "locked": True,
            },
            "search_evidence_catalog": [
                {
                    "title": "플러스",
                    "url": "https://novelpia.com/plus/all/date/5/?main_genre=",
                    "source_tier": "novel_platform",
                    "snippet": f"{title} PLUS 독점 연재중단 프리데이 1.74M.",
                }
            ],
        }

        blocked = apply_weak_public_title_bridge_guard(
            identity,
            "탑성좌애호 노벨피아 이거 연중했었네",
        )
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(blocked, [])
        self.assertEqual(identity["novel_identity"]["official_title"], title)
        self.assertEqual(fields["candidate_ledger_status"], "safe_resolved")
        self.assertNotIn("unconfirmed_alias_official_detail_bridge", identity.get("candidate_audit_lint", []))

    def test_title_led_consumption_title_marker_exempts_empty_body_alias_bridge(self):
        title = "암흑가 보스요? 제가요?"
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "primary_subject_type": "work_discussion",
            "anchor_type": "title_alias",
            "anchor_strength": "medium",
            "context_sources": ["title", "search"],
            "consistency_flags": [
                "title_lead_alias_official_detail_release",
                "weak_public_title_bridge_batch_alias_exact_exempt",
            ],
            "novel_identity": {
                "official_title": title,
                "heretic_url": "https://novelpia.com/novel/384111",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": title,
                "heretic_url": "https://novelpia.com/novel/384111",
                "confidence": "High",
                "alias_or_mention": "암흑가보스",
                "source_tier": "official_detail",
            },
            "search_evidence_catalog": [
                {
                    "title": f"{title} - 노벨피아",
                    "url": "https://novelpia.com/novel/384111",
                    "source_tier": "novel_platform",
                    "snippet": f"{title} 작가명 손아픈사람.",
                }
            ],
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "암흑가보스<<이거 재밋네")
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(blocked, [])
        self.assertEqual(identity["novel_identity"]["official_title"], title)
        self.assertEqual(fields["candidate_ledger_status"], "safe_resolved")

    def test_current_work_gate_title_led_alias_scope_exempts_weak_alias_scrub(self):
        title = "암흑가 보스요? 제가요?"
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "primary_subject_type": "work_discussion",
            "anchor_type": "none",
            "anchor_strength": "medium",
            "context_sources": ["title", "search", "image"],
            "consistency_flags": [
                "unresolved_worklike_hold:title_led_consumption",
                "locked_official_candidate_rescued",
                "weak_public_title_bridge_locked_official_exempt",
                "same_url_official_detail_canonicalized",
                "platform_seo_title_suffix_canonicalized",
            ],
            "novel_identity": {
                "official_title": title,
                "heretic_url": "https://novelpia.com/novel/384111",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": title,
                "heretic_url": "https://novelpia.com/novel/384111",
                "confidence": "High",
                "alias_or_mention": "암흑가보스",
                "source_tier": "official_detail",
                "page_type": "novel_page",
                "locked": True,
            },
            "promotion_decision": {
                "status": "candidate_only",
                "publish_allowed": False,
                "official_title": None,
                "official_url": None,
                "candidate_preserved": True,
                "reason_codes": [
                    "official_title_exists",
                    "row_discusses_work_as_work",
                    "scope_current_work",
                    "resolved_public_title_scope",
                    "official_detail_url",
                    "weak_alias_surface_public_title_bridge",
                    "serialized_public_identity_scrubbed",
                ],
                "bypassed_gate": False,
                "scope": {
                    "scope_kind": "current_work",
                    "confidence": "high",
                    "direct_bridge_sources": [
                        "resolved_public_title_scope",
                        "title",
                        "image",
                        "anchor_type:none",
                        "official_detail_url",
                        "title_led_consumption_bridge",
                    ],
                },
            },
            "promotion_gate_state": {
                "post_id": 11660257,
                "candidate_title": title,
                "candidate_url": "https://novelpia.com/novel/384111",
                "source": "resolved_public_title",
                "official_title_exists": True,
                "row_discusses_work_as_work": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "scope": {
                    "scope_kind": "current_work",
                    "confidence": "high",
                    "direct_bridge_sources": [
                        "resolved_public_title_scope",
                        "title",
                        "image",
                        "anchor_type:none",
                        "official_detail_url",
                        "title_led_consumption_bridge",
                    ],
                },
            },
            "search_evidence_catalog": [
                {
                    "title": f"웹소설로 꿈꾸는 세상! - {title} - 노벨피아",
                    "url": "https://novelpia.com/novel/384111",
                    "source_tier": "novel_platform",
                    "snippet": f"{title} 작가명 손아픈사람.",
                }
            ],
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "암흑가보스<<이거 재밋네")
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(blocked, [])
        self.assertEqual(identity["novel_identity"]["official_title"], title)
        self.assertEqual(fields["candidate_ledger_status"], "safe_resolved")

    def test_title_led_consumption_empty_body_alias_without_marker_still_blocks(self):
        title = "암흑가 보스요? 제가요?"
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "primary_subject_type": "work_discussion",
            "anchor_type": "title_alias",
            "anchor_strength": "medium",
            "context_sources": ["title", "search"],
            "consistency_flags": [
                "title_lead_alias_official_detail_release",
                "weak_public_title_bridge_batch_alias_exact_exempt",
            ],
            "novel_identity": {
                "official_title": title,
                "heretic_url": "https://novelpia.com/novel/384111",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": title,
                "heretic_url": "https://novelpia.com/novel/384111",
                "confidence": "High",
                "alias_or_mention": "암보스",
                "source_tier": "official_detail",
            },
            "search_evidence_catalog": [
                {
                    "title": f"{title} - 노벨피아",
                    "url": "https://novelpia.com/novel/384111",
                    "source_tier": "novel_platform",
                    "snippet": f"{title} 작가명 손아픈사람.",
                }
            ],
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "암보스 정보좀")
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(blocked, ["unconfirmed_alias_official_detail_bridge"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(identity["blocked_official_title"], title)
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")

    def test_shared_current_work_gate_exempts_unconfirmed_official_detail_bridge_without_live_hit(self):
        title = "탑의 성좌들이 날 애호한다"
        url = "https://novelpia.com/novel/377032"
        decision = {
            "status": "publish",
            "publish_allowed": True,
            "official_title": title,
            "official_url": url,
            "candidate_preserved": False,
            "reason_codes": [
                "official_title_exists",
                "row_discusses_work_as_work",
                "scope_current_work",
                "batch_alias_public_title_bridge",
                "official_detail_url",
            ],
            "bypassed_gate": False,
            "scope": {
                "scope_kind": "current_work",
                "confidence": "high",
                "direct_bridge_sources": [
                    "batch_alias_candidate_accepted",
                    "search_evidence_alias_inference",
                    "alias_surface",
                    "official_detail_url",
                ],
            },
        }
        gate_state = {
            "post_id": 11669928,
            "candidate_title": title,
            "candidate_url": url,
            "source": "search_evidence_alias_inference",
            "official_title_exists": True,
            "row_discusses_work_as_work": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "scope": decision["scope"],
        }
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "primary_subject_type": "work_discussion",
            "anchor_type": "title_alias",
            "anchor_strength": "medium",
            "context_sources": ["title", "body", "comments", "search"],
            "consistency_flags": [
                "relation_hold_unresolved_recovered",
                "batch_memory_exact_alias_rescued",
                "batch_memory_alias_rescue_cleared_stale_demotions",
                "weak_public_title_bridge_batch_alias_exact_exempt",
            ],
            "novel_identity": {
                "official_title": title,
                "heretic_url": url,
                "confidence": "High",
            },
            "primary_work": {
                "official_title": title,
                "heretic_url": url,
                "confidence": "High",
                "alias_or_mention": "탑성좌애호",
                "source_tier": "official_detail",
                "locked": True,
            },
            "promotion_decision": decision,
            "promotion_gate_state": gate_state,
            "search_evidence_catalog": [
                {
                    "title": "탑성좌애호 슬슬 방향성 다시 잡아야 한다고 봄",
                    "url": "https://gall.dcinside.com/mgallery/board/view/?id=genrenovel&no=11205338",
                    "source_tier": "community",
                    "snippet": "탑성좌애호 주인공 이야기",
                }
            ],
            "candidate_preservation_sources": [
                {
                    "official_title": title,
                    "heretic_url": url,
                    "confidence": "High",
                    "alias_or_mention": "탑성좌애호",
                    "source_tier": "official_detail",
                    "page_type": "novel_page",
                    "reference_role": "primary",
                    "preservation_role": "title_candidate",
                },
                {
                    "official_title": "슬프구나",
                    "confidence": "Low",
                    "source_tier": "comment_surface",
                    "promotion_policy": "hold_without_promotion",
                },
            ],
        }

        blocked = apply_weak_public_title_bridge_guard(
            identity,
            "탑성좌애호 노벨피아 이거 연중했었네",
        )
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(blocked, [])
        self.assertEqual(identity["novel_identity"]["official_title"], title)
        self.assertEqual(fields["candidate_ledger_status"], "safe_resolved")
        self.assertNotIn("unconfirmed_alias_official_detail_bridge", identity.get("candidate_audit_lint", []))
        self.assertEqual(fields["candidate_ledger"]["promotion_gate_state"], gate_state)

    def test_context_only_shared_gate_does_not_exempt_unconfirmed_official_detail_bridge(self):
        title = "스페이스 오페라"
        url = "https://novelpia.com/novel/181483"
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "primary_subject_type": "work_discussion",
            "anchor_type": "title_alias",
            "anchor_strength": "medium",
            "context_sources": ["title", "body", "comments", "search"],
            "consistency_flags": ["batch_memory_exact_alias_rescued"],
            "novel_identity": {
                "official_title": title,
                "heretic_url": url,
                "confidence": "Medium",
            },
            "primary_work": {
                "official_title": title,
                "heretic_url": url,
                "confidence": "Medium",
                "alias_or_mention": "림월드",
                "source_tier": "official_detail",
            },
            "promotion_decision": {
                "status": "publish",
                "publish_allowed": True,
                "official_title": title,
                "official_url": url,
                "reason_codes": [
                    "official_title_exists",
                    "row_discusses_work_as_work",
                    "scope_context_only",
                    "official_detail_url",
                ],
                "scope": {
                    "scope_kind": "context_only",
                    "direct_bridge_sources": ["official_detail_url"],
                },
            },
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "랫따싶 림월드 요소 생각나게 하는거 좋네에")
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(blocked, ["unconfirmed_alias_official_detail_bridge"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")

    def test_character_alias_official_detail_support_exempts_unconfirmed_bridge_hold(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "primary_subject_type": "work_discussion",
            "discussion_type": "character_talk",
            "anchor_type": "title_alias",
            "anchor_strength": "medium",
            "context_sources": ["title", "body", "comments", "search"],
            "consistency_flags": [
                "batch_memory_exact_alias_rescued",
                "batch_memory_alias_rescue_cleared_stale_demotions",
                "weak_public_title_bridge_batch_alias_exact_exempt",
                "fanfic_derivative_title_unanchored_hold",
            ],
            "novel_identity": {
                "official_title": "이 무림의 미친년은 나야",
                "heretic_url": "https://novelpia.com/novel/217943?sid=main5",
                "confidence": "Medium",
            },
            "primary_work": {
                "official_title": "이 무림의 미친년은 나야",
                "heretic_url": "https://novelpia.com/novel/217943?sid=main5",
                "confidence": "Medium",
                "alias_or_mention": "서문청",
                "source_tier": "official_detail",
            },
            "search_evidence_catalog": [
                {
                    "title": "이 무림의 미친년은 나야",
                    "url": "https://novelpia.com/novel/217943?sid=main5",
                    "source_tier": "novel_platform",
                    "purpose": "title_anchor_official_probe",
                    "rank": 1,
                }
            ],
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "서문청 무친년")

        self.assertEqual(blocked, [])
        self.assertEqual(identity["novel_identity"]["official_title"], "이 무림의 미친년은 나야")

    def test_recoverable_official_detail_candidate_preempts_comment_only_blocked_label(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": False,
            "title_resolution_allowed": False,
            "title_resolution_state": "ocr_explicit_title_unresolved",
            "work_resolution": "none",
            "anchor_type": "title_alias",
            "anchor_strength": "high",
            "blocked_official_title": "그래-맞아",
            "candidate_preservation_sources": [
                {
                    "official_title": "그래-맞아",
                    "alias_or_mention": "그래-맞아",
                    "source_tier": "community",
                    "reference_role": "candidate",
                    "preservation_role": "recommendation_candidate",
                    "promotion_policy": "hold_without_promotion",
                    "negative_evidence": ["comment_answer_preservation_only"],
                }
            ],
            "image_evidence_catalog": [
                {
                    "ocr_text": "림월드의 랫킨모드가 보인다",
                    "visual_summary": "랫킨 캐릭터들이 있는 림월드 팬아트",
                    "work_cues": ["림월드", "랫따싶"],
                    "promotion_eligible": False,
                }
            ],
            "search_evidence_catalog": [
                {
                    "title": "웹소설로 꿈꾸는 세상! - [림월드]변방계에서 회귀자로 살아남기 - 노벨피아",
                    "url": "https://novelpia.com/novel/382324",
                    "source_tier": "novel_platform",
                    "snippet": "#패러디 #림월드 #랫따싶",
                    "rank": 1,
                }
            ],
        }

        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(identity["blocked_official_title"], "[림월드]변방계에서 회귀자로 살아남기")
        self.assertEqual(identity["blocked_official_title_url"], "https://novelpia.com/novel/382324")
        self.assertEqual(identity["comment_surface_blocked_official_title"], "그래-맞아")
        self.assertIn(
            "blocked_candidate_representative_upgraded_to_official_detail",
            identity["candidate_audit_lint"],
        )
        ledger = fields["candidate_ledger"]
        self.assertEqual(ledger["blocked_official_title"], "[림월드]변방계에서 회귀자로 살아남기")
        first_source = ledger["candidate_preservation_sources"][0]
        self.assertEqual(first_source["official_title"], "[림월드]변방계에서 회귀자로 살아남기")
        self.assertEqual(first_source["promotion_policy"], "hold_without_promotion")
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")

    def test_batch_memory_alias_competing_hold_blocks_official_detail_exemption(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "primary_subject_type": "work_discussion",
            "anchor_type": "title_alias",
            "anchor_strength": "medium",
            "context_sources": ["title", "body", "comments", "search", "image"],
            "consistency_flags": [
                "batch_memory_exact_alias_rescued",
                "precision_seed_independent_official_detail_supported",
                "official_url_recall_blocked_competing_candidate",
                "expert_conflict",
                "multi_work_title_cleared",
                "secondary_reference_official_alias_blocked_after_multi_work_title_cleared",
                "budget_quarantine_candidate",
            ],
            "novel_identity": {
                "official_title": "[림월드]변방계에서 회귀자로 살아남기",
                "heretic_url": "https://novelpia.com/novel/382324",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "[림월드]변방계에서 회귀자로 살아남기",
                "heretic_url": "https://novelpia.com/novel/382324",
                "confidence": "High",
                "alias_or_mention": "랫따싶",
                "source_tier": "official_detail",
                "reference_role": "primary",
                "locked": True,
            },
            "title_candidates": [
                {
                    "official_title": "쳇바퀴의 생쥐 사도가 되었다",
                    "source_tier": "official_detail",
                    "promotion_policy": "hold_without_promotion",
                },
                {
                    "official_title": "[림월드]변방계에서 회귀자로 살아남기",
                    "heretic_url": "https://novelpia.com/novel/382324",
                    "source_tier": "official_detail",
                },
            ],
            "search_evidence_catalog": [
                {
                    "title": "웹소설로 꿈꾸는 세상! - [림월드]변방계에서 회귀자로 살아남기",
                    "url": "https://novelpia.com/novel/382324",
                    "source_tier": "official_detail",
                    "snippet": "#패러디 #림월드 #랫따싶",
                }
            ],
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "랫따싶 림월드 요소 생각나게 하는거 좋네에")
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(blocked, ["batch_memory_alias_competing_hold_public_title_bridge"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertIsNone(identity["novel_identity"]["heretic_url"])
        self.assertEqual(identity["blocked_official_title"], "[림월드]변방계에서 회귀자로 살아남기")
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertEqual(identity["title_resolution_state"], "unresolved_matchable")
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        self.assertIn("쳇바퀴의 생쥐 사도가 되었다", fields["candidate_ledger"]["title_candidates"])
        self.assertIn("[림월드]변방계에서 회귀자로 살아남기", fields["candidate_ledger"]["title_candidates"])

    def test_direct_image_reference_recommendation_conflict_holds_public_title(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "anchor_type": "none",
            "anchor_strength": "low",
            "consistency_flags": [
                "recommendation_context_only_no_work_anchor",
                "direct_image_reference_recommendation_hold",
                "official_url_recall_gate_recovered",
                "title_body_official_detail_anchor",
                "vlm_ocr_title_conflict_with_final_title",
                "ocr_title_conflict_with_stable_alias",
            ],
            "novel_identity": {
                "official_title": "[림월드]변방계 행성 하렘 생존기",
                "heretic_url": "https://novelpia.com/novel/196996",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "[림월드]변방계 행성 하렘 생존기",
                "heretic_url": "https://novelpia.com/novel/196996",
                "confidence": "High",
                "source_tier": "official_detail",
            },
            "title_candidates": [
                {
                    "official_title": "눈물을 마시는 새",
                    "source_tier": "image_ocr",
                    "promotion_policy": "hold_without_promotion",
                },
                {
                    "official_title": "[림월드]변방계 행성 하렘 생존기",
                    "heretic_url": "https://novelpia.com/novel/196996",
                    "source_tier": "official_detail",
                },
            ],
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "눈마새나 추천할까")
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(blocked, ["direct_image_reference_recommendation_public_title_conflict"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertIsNone(identity["novel_identity"]["heretic_url"])
        self.assertEqual(identity["blocked_official_title"], "[림월드]변방계 행성 하렘 생존기")
        self.assertEqual(identity["blocked_official_title_url"], "https://novelpia.com/novel/196996")
        self.assertEqual(identity["work_resolution"], "unresolved")
        self.assertEqual(identity["title_resolution_state"], "unresolved_matchable")
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        self.assertIn("눈물을 마시는 새", fields["candidate_ledger"]["title_candidates"])
        self.assertIn("[림월드]변방계 행성 하렘 생존기", fields["candidate_ledger"]["title_candidates"])
        self.assertIn(
            "direct_image_reference_recommendation_public_title_conflict",
            fields["candidate_audit_lint"],
        )

    def test_recommendation_context_only_conflict_holds_late_recall_title(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "primary_subject_type": "recommendation_request",
            "anchor_type": "title_alias",
            "anchor_strength": "high",
            "consistency_flags": [
                "recommendation_context_only_no_work_anchor",
                "notes_demoted_for_unresolved",
                "official_url_recall_gate_recovered",
                "title_body_search_result:게임 마땅히",
                "title_body_official_detail_anchor",
                "vlm_ocr_title_conflict_with_final_title",
                "ocr_title_conflict_with_stable_alias",
            ],
            "novel_identity": {
                "official_title": "게임이 자꾸 사람을 구원함",
                "heretic_url": "https://novelpia.com/novel/429951",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "게임이 자꾸 사람을 구원함",
                "heretic_url": "https://novelpia.com/novel/429951",
                "confidence": "High",
                "alias_or_mention": "게임 마땅히",
                "source_tier": "official_detail",
            },
            "title_candidates": [
                {"official_title": "RIMWORLD", "source_tier": "image_ocr"},
                {"official_title": "눈물을 마시는 새", "source_tier": "image_ocr"},
            ],
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "림월드 << 마땅히 장갤러라면 한번쯤은 해야만함")
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(blocked, ["recommendation_context_only_public_title_conflict"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertIsNone(identity["novel_identity"]["heretic_url"])
        self.assertEqual(identity["blocked_official_title"], "게임이 자꾸 사람을 구원함")
        self.assertEqual(identity["blocked_official_title_url"], "https://novelpia.com/novel/429951")
        self.assertEqual(identity["work_resolution"], "unresolved")
        self.assertEqual(identity["title_resolution_state"], "unresolved_matchable")
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        self.assertIn("RIMWORLD", fields["candidate_ledger"]["title_candidates"])
        self.assertIn("눈물을 마시는 새", fields["candidate_ledger"]["title_candidates"])
        self.assertIn("게임이 자꾸 사람을 구원함", fields["candidate_ledger"]["title_candidates"])

    def test_cross_media_title_body_official_detail_recall_is_held(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "primary_subject_type": "cross_media",
            "anchor_type": "title_alias",
            "anchor_strength": "high",
            "context_sources": ["title", "body", "comments", "search", "image"],
            "consistency_flags": [
                "notes_demoted_for_unresolved",
                "official_url_recall_gate_recovered",
                "title_body_search_result:림월드 랫따싶",
                "title_body_official_detail_anchor",
                "same_url_official_detail_canonicalized",
                "platform_seo_title_suffix_canonicalized",
                "precision_seed_independent_official_detail_supported",
            ],
            "novel_identity": {
                "official_title": "[림월드]변방계에서 회귀자로 살아남기",
                "heretic_url": "https://novelpia.com/novel/382324",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "[림월드]변방계에서 회귀자로 살아남기",
                "heretic_url": "https://novelpia.com/novel/382324",
                "confidence": "High",
                "alias_or_mention": "림월드 랫따싶",
                "source_tier": "official_detail",
                "reference_role": "primary",
            },
            "search_evidence_catalog": [
                {
                    "title": "웹소설로 꿈꾸는 세상! - [림월드]변방계에서 회귀자로 살아남기",
                    "url": "https://novelpia.com/novel/382324",
                    "source_tier": "official_detail",
                    "snippet": "#패러디 #림월드 #랫따싶",
                }
            ],
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "랫따싶 림월드 요소 생각나게 하는거 좋네에")
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(blocked, ["cross_media_title_body_official_detail_public_title_bridge"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(identity["blocked_official_title"], "[림월드]변방계에서 회귀자로 살아남기")
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        self.assertIn("[림월드]변방계에서 회귀자로 살아남기", fields["candidate_ledger"]["title_candidates"])

    def test_llm_only_exact_title_without_official_support_is_held(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "review_reaction",
            "primary_subject_type": "work_discussion",
            "anchor_type": "title_exact",
            "anchor_strength": "high",
            "context_sources": ["title", "body"],
            "consistency_flags": [],
            "novel_identity": {
                "official_title": "21세기 무림",
                "heretic_url": None,
                "confidence": "Low",
            },
            "primary_work": {
                "official_title": "21세기 무림",
                "heretic_url": None,
                "confidence": "High",
                "alias_or_mention": "21세기 무림",
                "source_tier": "llm_only",
                "reference_role": "primary",
            },
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "21세기 무림 이거 재미네 ㅋㅋㅋ")
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(blocked, ["weak_source_exact_title_without_official_support_public_title_bridge"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(identity["blocked_official_title"], "21세기 무림")
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        self.assertIn("21세기 무림", fields["candidate_ledger"]["title_candidates"])

    def test_image_scene_cues_hold_unverified_homonym_public_title(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "anchor_type": "title_alias",
            "anchor_strength": "medium",
            "novel_identity": {
                "official_title": "도네하지 마라",
                "heretic_url": "https://novelpia.com/novel/74240",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "도네하지 마라",
                "heretic_url": "https://novelpia.com/novel/74240",
                "confidence": "High",
                "source_tier": "official_detail",
            },
            "title_candidates": [
                {
                    "official_title": "알파카랑 눈싸움 하지마라",
                    "source_tier": "post_surface",
                    "promotion_policy": "hold_without_promotion",
                }
            ],
            "image_evidence_catalog": [
                {
                    "ocr_text": (
                        "그 사이에 낀 알파카가 나를 꼬라봤다. "
                        "시트러스가 한숨을 내쉬었다. "
                        "강시우 씨, 누누이 말하지만 알파카랑 눈싸움하지 마시라니까요."
                    ),
                    "visual_summary": "웹소설 본문 텍스트 스크린샷",
                    "title_role": "unknown",
                    "promotion_eligible": False,
                    "work_cues": ["강시우", "시트러스", "알파카 관련 대사"],
                }
            ],
            "search_evidence_catalog": [
                {
                    "title": "도네하지 마라",
                    "url": "https://novelpia.com/novel/74240",
                    "snippet": "너 그러다 아이돌 격투가 된다. 첫 화 무료보기.",
                    "query": "하지마라 노벨피아",
                    "source_tier": "novel_platform",
                }
            ],
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "알파카랑 눈싸움 하지마라")
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(blocked, ["image_scene_cues_unverified_public_title_bridge"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertIsNone(identity["novel_identity"]["heretic_url"])
        self.assertEqual(identity["blocked_official_title"], "도네하지 마라")
        self.assertEqual(identity["blocked_official_title_url"], "https://novelpia.com/novel/74240")
        self.assertEqual(identity["work_resolution"], "unresolved")
        self.assertEqual(identity["title_resolution_state"], "unresolved_matchable")
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        self.assertIn("알파카랑 눈싸움 하지마라", fields["candidate_ledger"]["title_candidates"])
        self.assertIn("도네하지 마라", fields["candidate_ledger"]["title_candidates"])

    def test_image_scene_cues_hold_author_anchor_without_cue_overlap(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "anchor_type": "author",
            "anchor_strength": "medium",
            "novel_identity": {
                "official_title": "도네하지 마라",
                "heretic_url": "https://novelpia.com/novel/74240",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "도네하지 마라",
                "heretic_url": "https://novelpia.com/novel/74240",
                "confidence": "High",
                "source_tier": "official_detail",
                "page_type": "novel_page",
            },
            "image_evidence_catalog": [
                {
                    "ocr_text": (
                        "그 사이에 끼인 알파카가 나를 꼬라봤다. "
                        "시트러스가 한숨을 내쉬었다. "
                        "강시우 씨, 누누이 말하지만 알파카랑 눈싸움하지 마시라니까요."
                    ),
                    "visual_summary": "웹소설 본문 텍스트 스크린샷",
                    "evidence_type": "scene_inference_only",
                    "title_role": "unknown",
                    "promotion_eligible": False,
                }
            ],
            "search_evidence_catalog": [
                {
                    "title": "도네하지 마라",
                    "url": "https://novelpia.com/novel/74240",
                    "snippet": "너 그러다 아이돌 격투가 된다. 첫 화 무료보기.",
                    "query": "하지마라 노벨피아",
                    "source_tier": "novel_platform",
                }
            ],
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "알파카랑 눈싸움 하지마라")
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(blocked, ["image_scene_cues_unverified_public_title_bridge"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(identity["blocked_official_title"], "도네하지 마라")
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")

    def test_none_surface_official_title_is_demoted(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "novel_identity": {
                "official_title": "없음",
                "heretic_url": "https://novelpia.com/novel/25974",
                "confidence": "High",
            },
        }

        blocked = apply_official_title_promotion_guard(identity)
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(blocked, ["official_title_looks_like_generic_non_title_surface"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(identity["blocked_official_title"], "없음")
        self.assertIn("official_title_looks_like_generic_non_title_surface", fields["official_title_lint"])
        self.assertFalse(fields["safe_resolved"])

    def test_webnovel_generic_evidence_label_official_title_is_demoted(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "novel_identity": {
                "official_title": "웹소설",
                "heretic_url": "https://novelpia.com/novel/12345",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "웹소설",
                "heretic_url": "https://novelpia.com/novel/12345",
                "confidence": "High",
                "source_tier": "official_detail",
            },
        }

        blocked = apply_official_title_promotion_guard(identity)
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(blocked, ["official_title_looks_like_generic_evidence_label"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(identity["blocked_official_title"], "웹소설")
        self.assertIn("official_title_looks_like_generic_evidence_label", fields["official_title_lint"])
        self.assertFalse(fields["safe_resolved"])
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")

    def test_author_angle_search_surface_uses_matching_official_detail_candidate(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "novel_identity": {
                "official_title": "피아조아 <시간을 달리는 소설가>",
                "heretic_url": None,
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "피아조아 <시간을 달리는 소설가>",
                "confidence": "High",
                "source_tier": "official_search",
            },
            "title_candidates": [
                {
                    "official_title": "피아조아 <시간을 달리는 소설가>",
                    "confidence": "High",
                    "source_tier": "official_search",
                },
                {
                    "official_title": "시간을 달리는 소설가",
                    "heretic_url": "https://novel.munpia.com/357213",
                    "confidence": "High",
                    "source_tier": "official_detail",
                    "page_type": "novel_page",
                },
            ],
            "reason": "공식 검색 결과 피아조아 <시간을 달리는 소설가>가 확인됨.",
            "reason_lines": ["피아조아 <시간을 달리는 소설가>를 공식 제목으로 선택"],
        }

        canonicalized = apply_author_angle_official_detail_canonicalization(identity)
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(canonicalized, ["author_angle_official_detail_canonicalized"])
        self.assertEqual(identity["novel_identity"]["official_title"], "시간을 달리는 소설가")
        self.assertEqual(identity["novel_identity"]["heretic_url"], "https://novel.munpia.com/357213")
        self.assertEqual(identity["primary_work"]["official_title"], "시간을 달리는 소설가")
        self.assertEqual(identity["primary_work"]["heretic_url"], "https://novel.munpia.com/357213")
        self.assertNotIn("피아조아 <시간을 달리는 소설가>", identity["reason"])
        self.assertNotIn("피아조아 <시간을 달리는 소설가>", "\n".join(identity["reason_lines"]))
        self.assertTrue(fields["safe_resolved"])

    def test_short_lead_public_title_bridge_is_held_without_confirmed_alias(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "anchor_type": "title_exact",
            "anchor_strength": "high",
            "novel_identity": {
                "official_title": "하남자의 탑 공략법",
                "heretic_url": "https://series.naver.com/novel/detail.series?productNo=11508059",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "하남자의 탑 공략법",
                "heretic_url": "https://series.naver.com/novel/detail.series?productNo=11508059",
                "confidence": "High",
                "source_tier": "official_detail",
            },
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "하남자 재밌냐")

        self.assertEqual(blocked, ["short_lead_surface_public_title_bridge"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(identity["blocked_official_title"], "하남자의 탑 공략법")

    def test_short_lead_public_title_bridge_is_held_with_confirmed_stem_alias(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "anchor_type": "title_exact",
            "anchor_strength": "high",
            "consistency_flags": [
                "confirmed_alias:하남자",
                "verified_alias_official_detail_anchor",
                "explicit_alias_official_work_lock",
            ],
            "novel_identity": {
                "official_title": "하남자의 탑 공략법",
                "heretic_url": "https://series.naver.com/novel/detail.series?productNo=11227324",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "하남자의 탑 공략법",
                "heretic_url": "https://series.naver.com/novel/detail.series?productNo=11227324",
                "confidence": "High",
                "source_tier": "official_detail",
            },
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "하남자 재밌냐")

        self.assertEqual(blocked, ["short_lead_surface_public_title_bridge"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(identity["blocked_official_title"], "하남자의 탑 공략법")

    def test_weak_alias_surface_is_held_with_confirmed_stem_alias(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "anchor_type": "title_alias",
            "anchor_strength": "high",
            "consistency_flags": [
                "confirmed_alias:하남자",
                "verified_alias_official_detail_anchor",
                "explicit_alias_official_work_lock",
            ],
            "novel_identity": {
                "official_title": "하남자의 탑 공략법",
                "heretic_url": "https://series.naver.com/novel/detail.series?productNo=11227324",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "하남자의 탑 공략법",
                "heretic_url": "https://series.naver.com/novel/detail.series?productNo=11227324",
                "confidence": "High",
                "alias_or_mention": "하남자",
                "source_tier": "official_detail",
            },
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "하남자 재밌냐")

        self.assertEqual(blocked, ["weak_alias_surface_public_title_bridge"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(identity["blocked_official_title"], "하남자의 탑 공략법")

    def test_direct_exact_short_official_title_is_not_weak_alias_held(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "anchor_type": "title_exact",
            "anchor_strength": "high",
            "novel_identity": {
                "official_title": "테라포밍",
                "heretic_url": "https://novelpia.com/novel/61947",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "테라포밍",
                "heretic_url": "https://novelpia.com/novel/61947",
                "confidence": "High",
                "alias_or_mention": "테라포밍",
                "source_tier": "official_detail",
            },
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "테라포밍 볼만함?")
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(blocked, [])
        self.assertEqual(identity["novel_identity"]["official_title"], "테라포밍")
        self.assertEqual(fields["candidate_ledger_status"], "safe_resolved")

    def test_current_work_gate_exact_short_title_is_not_weak_alias_held(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "primary_subject_type": "work_discussion",
            "anchor_type": "platform",
            "anchor_strength": "medium",
            "context_sources": ["title", "body", "comments", "search"],
            "consistency_flags": [
                "decoder_exact_post_title_surface_resolved",
                "official_detail_url_repaired_from_search",
            ],
            "novel_identity": {
                "official_title": "와인의 신",
                "heretic_url": "https://series.naver.com/novel/detail.series?productNo=13342533",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "와인의 신",
                "heretic_url": "https://series.naver.com/novel/detail.series?productNo=13342533",
                "confidence": "High",
                "alias_or_mention": "와인의 신",
                "source_tier": "official_detail",
                "page_type": "novel_page",
            },
            "promotion_decision": {
                "status": "publish",
                "publish_allowed": True,
                "official_title": "와인의 신",
                "official_url": "https://series.naver.com/novel/detail.series?productNo=13342533",
                "candidate_preserved": False,
                "reason_codes": [
                    "official_title_exists",
                    "row_discusses_work_as_work",
                    "scope_current_work",
                    "official_detail_url",
                ],
                "bypassed_gate": False,
                "scope": {
                    "scope_kind": "current_work",
                    "confidence": "high",
                    "direct_bridge_sources": ["row_discusses_work_as_work"],
                },
            },
            "promotion_gate_state": {
                "post_id": 11661876,
                "candidate_title": "와인의 신",
                "candidate_url": "https://series.naver.com/novel/detail.series?productNo=13342533",
                "source": "decoder_exact_post_title_surface_resolved",
                "official_title_exists": True,
                "row_discusses_work_as_work": True,
                "scope": {
                    "scope_kind": "current_work",
                    "confidence": "high",
                    "direct_bridge_sources": ["row_discusses_work_as_work"],
                },
            },
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "와인의신 재밌다")
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(blocked, [])
        self.assertEqual(identity["novel_identity"]["official_title"], "와인의 신")
        self.assertEqual(fields["candidate_ledger_status"], "safe_resolved")

    def test_same_url_official_page_title_replaces_character_alias_surface(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "primary_subject_type": "work_discussion",
            "anchor_type": "title_alias",
            "anchor_strength": "high",
            "context_sources": ["title", "body", "comments", "search"],
            "consistency_flags": [
                "decoder_exact_post_title_surface_resolved",
                "official_detail_url_repaired_from_search",
            ],
            "novel_identity": {
                "official_title": "설지후",
                "heretic_url": "https://page.kakao.com/content/50219568",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "설지후",
                "heretic_url": "https://page.kakao.com/content/50219568",
                "confidence": "High",
                "alias_or_mention": "설지후",
                "source_tier": "official_detail",
                "page_type": "novel_page",
            },
            "candidate_preservation_sources": [
                {
                    "official_title": "설지후",
                    "heretic_url": "https://page.kakao.com/content/50219568",
                    "confidence": "High",
                    "alias_or_mention": "설지후",
                    "source_tier": "official_detail",
                    "page_type": "novel_page",
                }
            ],
            "search_evidence_catalog": [
                {
                    "title": "탐식의 재림 - 웹소설 - 카카오페이지",
                    "url": "https://page.kakao.com/content/50219568",
                    "source_tier": "novel_platform",
                    "purpose": "precomputed_source_evidence",
                }
            ],
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "장갤 설지후 변화도 레전드임")
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(blocked, [])
        self.assertEqual(identity["novel_identity"]["official_title"], "탐식의 재림")
        self.assertEqual(identity["primary_work"]["official_title"], "탐식의 재림")
        self.assertEqual(fields["candidate_ledger_status"], "safe_resolved")

    def test_secondary_reference_precision_downgrade_rescue_is_held(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "anchor_type": "title_alias",
            "anchor_strength": "high",
            "primary_subject_type": "work_discussion",
            "consistency_flags": [
                "title_precision_downgrade",
                "primary_work_cleared_non_resolved",
                "secondary_reference_official_alias_rescued",
                "secondary_reference_official_alias_author_meta_override",
                "official_url_recall_gate_recovered",
                "confirmed_alias:황제분충",
            ],
            "novel_identity": {
                "official_title": "황제의 딸로 환생했다",
                "heretic_url": "https://novelpia.com/novel/250464",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "황제의 딸로 환생했다",
                "heretic_url": "https://novelpia.com/novel/250464",
                "confidence": "High",
                "alias_or_mention": "황제분충",
                "source_tier": "official_detail",
                "reference_role": "primary",
            },
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "황제분충 ㄱㅊ함?")
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(blocked, ["secondary_reference_precision_downgrade_public_title_bridge"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(identity["blocked_official_title"], "황제의 딸로 환생했다")
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")

    def test_promoted_image_work_title_conflict_holds_search_alias_title(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "anchor_type": "title_alias",
            "anchor_strength": "high",
            "consistency_flags": ["confirmed_alias:외신소환", "vlm_ocr_title_conflict_with_final_title"],
            "novel_identity": {
                "official_title": "무한을 이해한 나는 외신의 사제가 되었습니다",
                "heretic_url": "https://novelpia.com/novel/270445",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "무한을 이해한 나는 외신의 사제가 되었습니다",
                "heretic_url": "https://novelpia.com/novel/270445",
                "confidence": "High",
                "alias_or_mention": "외신소환",
                "source_tier": "official_detail",
            },
            "image_evidence_catalog": [
                {
                    "explicit_work_title": "교황님 아하세요 마왕 들어 가요",
                    "title_role": "work_title",
                    "promotion_eligible": True,
                }
            ],
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "념글 시발 외신소환 주문 뭐임")

        self.assertEqual(blocked, ["promoted_image_work_title_conflicts_with_public_title"])
        self.assertEqual(identity["title_resolution_state"], "ocr_explicit_title_unresolved")
        self.assertIsNone(identity["novel_identity"]["official_title"])

    def test_verified_alias_detail_lock_exempts_noisy_image_surface_conflict(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "primary_subject_type": "work_discussion",
            "anchor_type": "image",
            "anchor_strength": "high",
            "consistency_flags": [
                "direct_image_explicit_title_rescued",
                "verified_alias_official_detail_anchor",
                "confirmed_alias:Lp코",
                "explicit_alias_official_work_lock",
                "weak_public_title_bridge_verified_alias_detail_exempt",
            ],
            "novel_identity": {
                "official_title": "이거 럽코 빙의물인가요",
                "heretic_url": "https://novel.munpia.com/533816",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "이거 럽코 빙의물인가요",
                "heretic_url": "https://novel.munpia.com/533816",
                "confidence": "High",
                "alias_or_mention": "이거 Lp코 丙의물인가요",
                "source_tier": "official_detail",
                "page_type": "novel_page",
                "reference_role": "primary",
            },
            "image_evidence_catalog": [
                {
                    "explicit_work_title": "이거 Lp코 丙의물인가요",
                    "title_role": "work_title",
                    "promotion_eligible": True,
                }
            ],
            "search_evidence_catalog": [
                {
                    "title": "이거 럽코 빙의물인가요 - 문피아 웹소설",
                    "url": "https://novel.munpia.com/533816",
                    "source_tier": "novel_platform",
                }
            ],
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "문피아가 밀어주나보네")
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(blocked, [])
        self.assertEqual(identity["novel_identity"]["official_title"], "이거 럽코 빙의물인가요")
        self.assertEqual(fields["candidate_ledger_status"], "safe_resolved")
        self.assertNotIn(
            "promoted_image_work_title_conflicts_with_public_title",
            fields["identity_consistency_lint"],
        )

    def test_unverified_promoted_image_title_is_held_without_official_support(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "anchor_type": "image",
            "anchor_strength": "high",
            "consistency_flags": ["direct_image_explicit_title_rescued"],
            "novel_identity": {
                "official_title": "전 버듀바가 하고 싶은데요",
                "heretic_url": None,
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "전 버듀바가 하고 싶은데요",
                "confidence": "High",
                "source_tier": "llm_only",
            },
            "image_evidence_catalog": [
                {
                    "explicit_work_title": "전 버듀바가 하고 싶은데요",
                    "title_role": "work_title",
                    "promotion_eligible": True,
                }
            ],
        }

        blocked = apply_weak_public_title_bridge_guard(identity, "TS) 주서연 전차랑 줄다리기 하면 이길까?")
        fields = apply_candidate_audit_fields(identity, None)

        self.assertEqual(blocked, ["unverified_promoted_image_work_title_without_official_support"])
        self.assertEqual(identity["title_resolution_state"], "ocr_explicit_title_unresolved")
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertIn("전 버듀바가 하고 싶은데요", fields["candidate_ledger"]["title_candidates"])
        self.assertFalse(fields["safe_resolved"])

    def test_confirmed_alias_and_compatible_image_title_are_preserved(self):
        alias_identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "anchor_type": "title_alias",
            "anchor_strength": "medium",
            "consistency_flags": ["confirmed_alias:잘생인방", "verified_alias_official_detail_anchor"],
            "novel_identity": {
                "official_title": "잘생기면 인생이 편하다",
                "heretic_url": "https://novelpia.com/novel/300042",
                "confidence": "Medium",
            },
            "primary_work": {
                "official_title": "잘생기면 인생이 편하다",
                "heretic_url": "https://novelpia.com/novel/300042",
                "confidence": "Medium",
                "alias_or_mention": "잘생인방",
                "source_tier": "official_detail",
            },
        }
        image_identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "anchor_type": "title_alias",
            "anchor_strength": "high",
            "novel_identity": {
                "official_title": "주서연(전 버튜버가 하고 싶은데요)",
                "heretic_url": "https://novelpia.com/novel/275975",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": "주서연(전 버튜버가 하고 싶은데요)",
                "heretic_url": "https://novelpia.com/novel/275975",
                "confidence": "High",
                "alias_or_mention": "전 버튜버가 하고 싶은데요",
                "source_tier": "official_detail",
            },
            "image_evidence_catalog": [
                {
                    "explicit_work_title": "전 버튜버가 하고 싶은데요",
                    "title_role": "work_title",
                    "promotion_eligible": True,
                }
            ],
        }

        self.assertEqual(apply_weak_public_title_bridge_guard(alias_identity, "현대 하렘물은 진짜 잘쓰는 작가가 손에꼽네"), [])
        self.assertEqual(apply_weak_public_title_bridge_guard(image_identity, "TS) 주서연 전차랑 줄다리기 하면 이길까?"), [])
        self.assertEqual(alias_identity["novel_identity"]["official_title"], "잘생기면 인생이 편하다")
        self.assertEqual(image_identity["novel_identity"]["official_title"], "주서연(전 버튜버가 하고 싶은데요)")


class SourceEnrichedCanaryTest(unittest.TestCase):
    def test_restores_image_blocks_from_source_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            canary = root / "canary.jsonl"
            source = root / "source.json"
            out_dir = root / "out"
            canary.write_text(
                json.dumps(
                    {
                        "post_id": 1,
                        "title": "이미지 seed",
                        "content": ["본문", "[이미지 첨부: 원본 image URL 없음, img_count=1]"],
                        "_judge_seed": {"source_img_count": 1},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            source.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 1,
                            "title": "이미지 seed",
                            "content_blocks": [
                                {"type": "image", "url": "https://dcimg.example/a.jpg"},
                                {"type": "image", "url": "https://nstatic.dcinside.com/dc/m/img/gallview_loading_ori.gif"},
                                {"type": "text", "text": "본문"},
                            ],
                            "analysis_result": {"identity": {}},
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            manifest = build_source_enriched_canary(
                canary_input=canary,
                source_patterns=[source.as_posix()],
                out_dir=out_dir,
                prefix="seed",
            )

            self.assertEqual(manifest["restored_count"], 1)
            self.assertEqual(manifest["unrecovered_count"], 0)
            self.assertEqual(manifest["recommended_parallel"], 16)
            self.assertEqual(manifest["expected_effective_parallel"], 1)
            self.assertIn("--parallel 16", manifest["recommended_commands"]["expert_main_source_enriched_canary"])
            self.assertNotIn("--no-dashboard", manifest["recommended_commands"]["expert_main_source_enriched_canary"])
            self.assertEqual(
                manifest["execution_contract"]["dashboard_contract"]["dashboard_policy"],
                "WEB_DASHBOARD_REQUIRED_FOR_TEST_RUNS",
            )
            rows = [
                json.loads(line)
                for line in (out_dir / "seed_source_enriched_canary_input.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(rows[0]["image_urls"], ["https://dcimg.example/a.jpg"])
            self.assertEqual(rows[0]["_judge_seed"]["dropped_placeholder_image_count"], 1)


if __name__ == "__main__":
    unittest.main()
