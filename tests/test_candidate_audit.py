import json
import tempfile
import unittest
from pathlib import Path

from llm_batch.candidate_audit import (
    apply_candidate_audit_fields,
    apply_comment_surface_candidate_hints,
    apply_judge_seed_expected_candidate_preservation,
    apply_judge_seed_hygiene_expected_title_guard,
    apply_judge_seed_precision_guard,
    apply_judge_seed_title_image_mismatch_guard,
    apply_judge_seed_title_hygiene_guard,
    apply_judge_seed_trope_boundary_hold_guard,
    apply_judge_seed_unverified_ocr_title_guard,
    apply_official_title_promotion_guard,
    apply_post_surface_candidate_hints,
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
        self.assertEqual(fields["candidate_ledger_status"], "promotion_blocked")
        self.assertEqual(fields["candidate_ledger"]["blocked_official_title"], "인간 실격")
        self.assertEqual(fields["candidate_ledger"]["blocked_official_title_url"], "https://page.kakao.com/content/51726202")

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
            rows = [
                json.loads(line)
                for line in (out_dir / "seed_source_enriched_canary_input.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(rows[0]["image_urls"], ["https://dcimg.example/a.jpg"])
            self.assertEqual(rows[0]["_judge_seed"]["dropped_placeholder_image_count"], 1)


if __name__ == "__main__":
    unittest.main()
