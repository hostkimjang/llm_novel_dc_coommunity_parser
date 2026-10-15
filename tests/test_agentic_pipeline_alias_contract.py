from __future__ import annotations

import unittest
from types import SimpleNamespace
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_batch.agentic_pipeline import AgenticPipeline  # noqa: E402
from llm_batch.domain.models import DetectedTitle  # noqa: E402
from llm_batch.prompts.expert_prompts import DECODER_SYSTEM, VERIFIER_PROMPT  # noqa: E402
from llm_batch.prompts.prompt_router import _build_relevance_contract_overlay  # noqa: E402


class DummyContext(SimpleNamespace):
    def get_expert_output(self, *_args, **_kwargs):
        return {}


class AgenticPipelineAliasContractTest(unittest.TestCase):
    def test_composite_alias_forces_store_false_and_extracts_canonical_alias(self):
        pipeline = object.__new__(AgenticPipeline)
        contract = pipeline._infer_slang_alias_contract(
            official_title="즉사기 들고 무림에 떨어지다",
            vf_slang={
                "detected_term": "즉사무림이유백",
                "decoded_term": "즉사기 들고 무림에 떨어지다 (주인공 이유백)",
                "store_in_slang_db": True,
            },
            entity_mentions=[
                {
                    "text": "이유백",
                    "entity_type": "character",
                    "role": "character_focus",
                }
            ],
        )
        self.assertEqual(contract["canonical_work_alias"], "즉사무림")
        self.assertEqual(contract["alias_scope"], "work_plus_character")
        self.assertEqual(contract["attached_entity_text"], "이유백")
        self.assertEqual(contract["attached_entity_type"], "character")
        self.assertFalse(contract["store_in_slang_db"])

    def test_unclear_pure_alias_without_canonical_is_forced_not_to_store(self):
        pipeline = object.__new__(AgenticPipeline)
        contract = pipeline._infer_slang_alias_contract(
            official_title="1929 대공황시대 공장주가 되었다",
            vf_slang={
                "detected_term": "개장빙",
                "decoded_term": "1929 대공황시대 공장주가 되었다",
                "alias_scope": "pure_work_alias",
                "store_in_slang_db": True,
            },
            entity_mentions=[],
        )
        self.assertFalse(contract["store_in_slang_db"])
        self.assertEqual(contract["store_reason"], "unclear_canonical_alias")

    def test_plain_meme_alias_scope_is_normalized_and_not_stored(self):
        pipeline = object.__new__(AgenticPipeline)
        contract = pipeline._infer_slang_alias_contract(
            official_title=None,
            vf_slang={
                "detected_term": "영역전개(Domain Expansion)",
                "decoded_term": "영역전개",
                "alias_scope": "meme",
                "attached_entity_type": "meme",
                "store_in_slang_db": True,
                "store_reason": "meme",
            },
            entity_mentions=[],
        )
        self.assertIsNone(contract["alias_scope"])
        self.assertFalse(contract["store_in_slang_db"])
        self.assertEqual(contract["store_reason"], "meme")

    def test_string_null_alias_scope_is_normalized_and_not_stored(self):
        pipeline = object.__new__(AgenticPipeline)
        contract = pipeline._infer_slang_alias_contract(
            official_title=None,
            vf_slang={
                "detected_term": "장붕이",
                "decoded_term": "장르소설 갤러리 이용자",
                "alias_scope": "null",
                "store_in_slang_db": True,
                "store_reason": "community_user_term",
            },
            entity_mentions=[],
        )
        self.assertIsNone(contract["alias_scope"])
        self.assertFalse(contract["store_in_slang_db"])
        self.assertEqual(contract["store_reason"], "community_user_term")

    def test_unresolved_author_talk_alias_is_not_marked_for_storage(self):
        pipeline = object.__new__(AgenticPipeline)
        contract = pipeline._infer_slang_alias_contract(
            official_title=None,
            vf_slang={
                "detected_term": "애호뉴비",
                "decoded_term": "애호받는 뉴비가 되었다",
                "canonical_work_alias": "애호뉴비",
                "alias_scope": "pure_work_alias",
                "store_in_slang_db": True,
                "store_reason": "pure_work_alias",
            },
            entity_mentions=[],
            discussion_type="author_talk",
            topicality="adjacent_relevant",
            subtype="author_meta",
            work_resolution="none",
        )
        self.assertFalse(contract["store_in_slang_db"])
        self.assertEqual(contract["store_reason"], "pure_work_alias")

    def test_phrase_surface_with_clean_alias_is_not_stored(self):
        pipeline = object.__new__(AgenticPipeline)
        contract = pipeline._infer_slang_alias_contract(
            official_title="즉사기 들고 무림에 떨어지다",
            vf_slang={
                "detected_term": "즉사무림 은영이 너무 불쌍해",
                "decoded_term": "즉사기 들고 무림에 떨어지다",
                "canonical_work_alias": "즉사무림",
                "alias_scope": "pure_work_alias",
                "attached_entity_text": "은영",
                "attached_entity_type": "character",
                "store_in_slang_db": True,
                "store_reason": "pure_work_alias",
            },
            entity_mentions=[],
        )
        self.assertEqual(contract["canonical_work_alias"], "즉사무림")
        self.assertEqual(contract["alias_scope"], "work_plus_character")
        self.assertFalse(contract["store_in_slang_db"])
        self.assertEqual(contract["store_reason"], "character_attached_composite")

    def test_status_suffix_alias_surface_is_not_stored(self):
        pipeline = object.__new__(AgenticPipeline)
        contract = pipeline._infer_slang_alias_contract(
            official_title="죽었다 깨어도 수선",
            vf_slang={
                "detected_term": "죽깨수 on",
                "decoded_term": "죽었다 깨어도 수선",
                "canonical_work_alias": "죽었다 깨어도 수선",
                "alias_scope": "pure_work_alias",
                "store_in_slang_db": True,
                "store_reason": "pure_work_alias",
            },
            entity_mentions=[],
        )
        self.assertFalse(contract["store_in_slang_db"])
        self.assertIn(contract["store_reason"], {"surface_phrase_contains_alias", "sentence_like_alias_surface"})

    def test_exact_title_surface_is_not_stored_as_slang(self):
        pipeline = object.__new__(AgenticPipeline)
        contract = pipeline._infer_slang_alias_contract(
            official_title="배드 본 블러드",
            vf_slang={
                "detected_term": "배드 본 블러드",
                "decoded_term": "배드 본 블러드",
                "canonical_work_alias": "배드 본 블러드",
                "alias_scope": "pure_work_alias",
                "store_in_slang_db": True,
                "store_reason": "pure_work_alias",
            },
            entity_mentions=[],
        )
        self.assertFalse(contract["store_in_slang_db"])
        self.assertEqual(contract["store_reason"], "exact_title_not_alias")
        self.assertIsNone(contract["canonical_work_alias"])
        self.assertIsNone(contract["alias_scope"])

    def test_exact_title_surface_is_not_surfaced_as_slang_without_distinct_alias(self):
        pipeline = object.__new__(AgenticPipeline)
        self.assertFalse(
            pipeline._should_surface_slang_insight(
                official_title="아카데미의 피해자",
                vf_slang={
                    "detected_term": "아카데미의 피해자",
                    "decoded_term": "아카데미의 피해자",
                    "canonical_work_alias": "아카데미의 피해자",
                    "alias_scope": "pure_work_alias",
                    "store_in_slang_db": False,
                    "store_reason": "exact_title_not_alias",
                },
            )
        )

    def test_exact_title_composite_preserves_clean_short_alias_candidate(self):
        pipeline = object.__new__(AgenticPipeline)
        contract = pipeline._infer_slang_alias_contract(
            official_title="탑 매니지먼트",
            vf_slang={
                "detected_term": "탑매/탑 매니지먼트",
                "decoded_term": "탑 매니지먼트",
                "canonical_work_alias": "탑 매니지먼트",
                "alias_scope": "pure_work_alias",
                "store_in_slang_db": True,
                "store_reason": "pure_work_alias",
            },
            entity_mentions=[],
        )
        self.assertEqual(contract["canonical_work_alias"], "탑매")
        self.assertFalse(contract["store_in_slang_db"])
        self.assertEqual(contract["store_reason"], "surface_phrase_contains_alias")

    def test_clean_initial_alias_overrides_erroneous_exact_title_block(self):
        pipeline = object.__new__(AgenticPipeline)
        contract = pipeline._infer_slang_alias_contract(
            official_title="탑 매니지먼트",
            vf_slang={
                "detected_term": "탑매",
                "decoded_term": "탑 매니지먼트",
                "canonical_work_alias": None,
                "alias_scope": "mixed_unknown",
                "store_in_slang_db": False,
                "store_reason": "exact_title_not_alias",
            },
            entity_mentions=[],
        )
        self.assertEqual(contract["canonical_work_alias"], "탑매")
        self.assertEqual(contract["alias_scope"], "pure_work_alias")
        self.assertTrue(contract["store_in_slang_db"])
        self.assertEqual(contract["store_reason"], "pure_work_alias")

    def test_sentence_surface_preserves_clean_alias_candidate_without_storing_phrase(self):
        pipeline = object.__new__(AgenticPipeline)
        contract = pipeline._infer_slang_alias_contract(
            official_title="환생 암살자 검술천재",
            vf_slang={
                "detected_term": "환암검천 후기",
                "decoded_term": "환생 암살자 검술천재",
                "canonical_work_alias": "환암검천",
                "alias_scope": "pure_work_alias",
                "store_in_slang_db": True,
                "store_reason": "pure_work_alias",
            },
            entity_mentions=[],
        )
        self.assertEqual(contract["canonical_work_alias"], "환암검천")
        self.assertFalse(contract["store_in_slang_db"])
        self.assertEqual(contract["store_reason"], "surface_phrase_contains_alias")

    def test_clean_pure_work_alias_still_stores(self):
        pipeline = object.__new__(AgenticPipeline)
        contract = pipeline._infer_slang_alias_contract(
            official_title="죽었다 깨어도 수선",
            vf_slang={
                "detected_term": "죽깨수",
                "decoded_term": "죽었다 깨어도 수선",
                "canonical_work_alias": "죽깨수",
                "alias_scope": "pure_work_alias",
                "store_in_slang_db": True,
                "store_reason": "pure_work_alias",
            },
            entity_mentions=[],
        )
        self.assertTrue(contract["store_in_slang_db"])
        self.assertEqual(contract["canonical_work_alias"], "죽깨수")

    def test_full_title_canonical_alias_is_replaced_by_clean_detected_alias(self):
        pipeline = object.__new__(AgenticPipeline)
        contract = pipeline._infer_slang_alias_contract(
            official_title="죽었다 깨어도 수선",
            vf_slang={
                "detected_term": "죽깨수",
                "decoded_term": "죽었다 깨어도 수선",
                "canonical_work_alias": "죽었다 깨어도 수선",
                "alias_scope": "pure_work_alias",
                "store_in_slang_db": True,
                "store_reason": "pure_work_alias",
            },
            entity_mentions=[],
        )
        self.assertTrue(contract["store_in_slang_db"])
        self.assertEqual(contract["canonical_work_alias"], "죽깨수")

    def test_spaced_alias_surface_is_not_stored(self):
        pipeline = object.__new__(AgenticPipeline)
        contract = pipeline._infer_slang_alias_contract(
            official_title="괴담 호텔 탈출기",
            vf_slang={
                "detected_term": "괴담텔 2부",
                "decoded_term": "괴담 호텔 탈출기",
                "canonical_work_alias": "괴담텔 2부",
                "alias_scope": "pure_work_alias",
                "store_in_slang_db": True,
                "store_reason": "pure_work_alias",
            },
            entity_mentions=[],
        )
        self.assertFalse(contract["store_in_slang_db"])
        self.assertEqual(contract["store_reason"], "spaced_alias_surface")

    def test_structured_alias_support_detects_supported_alias(self):
        pipeline = object.__new__(AgenticPipeline)
        supported = pipeline._slang_contract_has_structured_alias_support(
            official_title="망겜의 힐러",
            detected_term="망겜힐",
            canonical_work_alias="망겜의 힐러",
            primary_work={
                "official_title": "망겜의 힐러",
                "alias_or_mention": "망겜힐",
            },
            title_candidates=[],
            mentioned_works=[],
            secondary_reference_works=[],
            comparison_target=None,
            recommendation_candidates=[],
        )
        self.assertTrue(supported)

    def test_structured_alias_support_rejects_slang_only_candidate(self):
        pipeline = object.__new__(AgenticPipeline)
        supported = pipeline._slang_contract_has_structured_alias_support(
            official_title="1929 대공황시대 공장주가 되었다",
            detected_term="개장빙",
            canonical_work_alias=None,
            primary_work={
                "official_title": "1929 대공황시대 공장주가 되었다",
                "alias_or_mention": None,
            },
            title_candidates=[
                {
                    "official_title": "1929 대공황시대 공장주가 되었다",
                    "alias_or_mention": None,
                }
            ],
            mentioned_works=[],
            secondary_reference_works=[],
            comparison_target=None,
            recommendation_candidates=[],
        )
        self.assertFalse(supported)

    def test_mixed_unknown_label_is_not_surfaced_as_slang(self):
        pipeline = object.__new__(AgenticPipeline)
        self.assertFalse(
            pipeline._should_surface_slang_insight(
                official_title=None,
                vf_slang={
                    "detected_term": "바니걸 입은 세드릭",
                    "decoded_term": "Mixed Unknown",
                    "alias_scope": "mixed_unknown",
                    "store_in_slang_db": False,
                },
            )
        )

    def test_pillow_talk_trope_is_not_surfaced_as_slang_without_title(self):
        pipeline = object.__new__(AgenticPipeline)
        self.assertFalse(
            pipeline._should_surface_slang_insight(
                official_title=None,
                vf_slang={
                    "detected_term": "필로토크",
                    "decoded_term": "필로우 토크(Pillow Talk) - BL 소설 e북",
                    "alias_scope": "mixed_unknown",
                    "store_in_slang_db": False,
                },
            )
        )

    def test_passthrough_general_term_without_work_is_not_surfaced_as_slang(self):
        pipeline = object.__new__(AgenticPipeline)
        self.assertFalse(
            pipeline._should_surface_slang_insight(
                official_title=None,
                vf_slang={
                    "detected_term": "남자엘프",
                    "decoded_term": "남자엘프",
                    "alias_scope": "mixed_unknown",
                },
            )
        )

    def test_namu_short_meaning_question_is_general_concept_not_work(self):
        pipeline = object.__new__(AgenticPipeline)
        ctx = DummyContext(
            post_data={
                "title": "왜 적궁백시임? 홍궁백시는 뜻이다름?",
                "content_blocks": [{"type": "text", "text": "??"}],
            },
            comments=[],
            search_results=[],
        )
        candidate = DetectedTitle(
            official_title="적궁백시",
            heretic_url="https://namu.wiki/w/%EC%A0%81%EA%B6%81%EB%B0%B1%EC%8B%9C",
            confidence="Medium",
            source_tier="community",
        )
        self.assertTrue(
            pipeline._is_namu_general_concept_candidate(ctx=ctx, candidate=candidate)
        )

    def test_namu_work_with_platform_context_is_not_general_concept(self):
        pipeline = object.__new__(AgenticPipeline)
        ctx = DummyContext(
            post_data={
                "title": "노피아 최악의 파트너 재밌음?",
                "content_blocks": [],
            },
            comments=[],
            search_results=[],
        )
        candidate = DetectedTitle(
            official_title="최악의 파트너",
            heretic_url="https://namu.wiki/w/%EC%B5%9C%EC%95%85%EC%9D%98%20%ED%8C%8C%ED%8A%B8%EB%84%88",
            confidence="High",
            source_tier="official_detail",
        )
        self.assertFalse(
            pipeline._is_namu_general_concept_candidate(ctx=ctx, candidate=candidate)
        )

    def test_same_title_url_prefers_novelpia_over_ridi(self):
        pipeline = object.__new__(AgenticPipeline)
        url = pipeline._find_title_matched_official_url(
            "이상적인 성녀? 미안, 가짜 성녀입니다!",
            [
                {
                    "title": "이상적인 성녀? 미안, 가짜 성녀입니다! - 리디",
                    "url": "https://ridibooks.com/books/2036077240",
                    "content": "",
                },
                {
                    "title": "이상적인 성녀? 미안, 가짜 성녀입니다! - 노벨피아",
                    "url": "https://book.novelpia.com/novel/11341",
                    "content": "",
                },
            ],
        )
        self.assertEqual(url, "https://book.novelpia.com/novel/11341")

    def test_shared_title_stem_neighbor_does_not_block_locked_primary(self):
        pipeline = object.__new__(AgenticPipeline)
        ctx = DummyContext(
            post_data={
                "title": "마법소녀ㄴ 신아 집에서는 머리 풀고다니는건가",
                "content_blocks": [{"type": "text", "text": "한세진"}],
            },
            comments=[],
            search_results=[],
        )
        primary = DetectedTitle(
            official_title="마법소녀ㄴ은 은퇴하고 싶다",
            heretic_url="https://novelpia.com/novel/347507",
            confidence="Medium",
            alias_or_mention="마법소녀ㄴ",
            source_tier="official_detail",
            page_type="novel_page",
            content_status="active",
            locked=True,
        )
        search_neighbor = DetectedTitle(
            official_title="불꽃의 마법소녀ㄴ",
            heretic_url="https://novel.munpia.com/239488",
            confidence="Medium",
            alias_or_mention="마법소녀ㄴ",
            source_tier="official_detail",
            page_type="novel_page",
            content_status="active",
        )

        self.assertTrue(
            pipeline._is_ambiguous_title_stem_neighbor(
                ctx,
                winner=primary,
                other=search_neighbor,
            )
        )
        selected = pipeline._select_single_locked_official_candidate(
            title_candidates=[primary, search_neighbor],
            ctx=ctx,
        )

        self.assertIsNotNone(selected)
        self.assertEqual(selected.official_title, "마법소녀ㄴ은 은퇴하고 싶다")

    def test_directly_mentioned_shared_stem_title_still_blocks_lock_rescue(self):
        pipeline = object.__new__(AgenticPipeline)
        ctx = DummyContext(
            post_data={
                "title": "불꽃의 마법소녀ㄴ 최신화 어땠음",
                "content_blocks": [],
            },
            comments=[],
            search_results=[],
        )
        primary = DetectedTitle(
            official_title="마법소녀ㄴ은 은퇴하고 싶다",
            heretic_url="https://novelpia.com/novel/347507",
            confidence="Medium",
            alias_or_mention="마법소녀ㄴ",
            source_tier="official_detail",
            locked=True,
        )
        direct_other = DetectedTitle(
            official_title="불꽃의 마법소녀ㄴ",
            heretic_url="https://novel.munpia.com/239488",
            confidence="Medium",
            alias_or_mention="마법소녀ㄴ",
            source_tier="official_detail",
        )

        self.assertFalse(
            pipeline._is_ambiguous_title_stem_neighbor(
                ctx,
                winner=primary,
                other=direct_other,
            )
        )
        self.assertIsNone(
            pipeline._select_single_locked_official_candidate(
                title_candidates=[primary, direct_other],
                ctx=ctx,
            )
        )

    def test_shared_stem_neighbor_is_removed_from_outward_reference_roles(self):
        pipeline = object.__new__(AgenticPipeline)
        ctx = DummyContext(
            post_data={
                "title": "마법소녀ㄴ 신아 집에서는 머리 풀고다니는건가",
                "content_blocks": [{"type": "text", "text": "한세진"}],
            },
            comments=[],
            search_results=[],
        )
        primary = DetectedTitle(
            official_title="마법소녀ㄴ은 은퇴하고 싶다",
            heretic_url="https://novelpia.com/novel/347507",
            confidence="Medium",
            alias_or_mention="마법소녀ㄴ",
            source_tier="official_detail",
            locked=True,
            reference_role="primary",
        )
        search_neighbor = DetectedTitle(
            official_title="불꽃의 마법소녀ㄴ",
            heretic_url="https://novel.munpia.com/239488",
            confidence="Medium",
            alias_or_mention="마법소녀ㄴ",
            source_tier="official_detail",
            reference_role="mentioned",
        )

        mentioned, comparison, recs, secondary, flags = pipeline._prune_ambiguous_title_stem_neighbors(
            ctx=ctx,
            official_title="마법소녀ㄴ은 은퇴하고 싶다",
            primary_work=primary,
            title_candidates=[primary, search_neighbor],
            mentioned_works=[search_neighbor],
            comparison_target=search_neighbor,
            recommendation_candidates=[search_neighbor],
            secondary_reference_works=[search_neighbor],
        )

        self.assertEqual(mentioned, [])
        self.assertIsNone(comparison)
        self.assertEqual(recs, [])
        self.assertEqual(secondary, [])
        self.assertIn("ambiguous_title_stem_neighbor_pruned", flags)

    def test_weak_llm_only_title_can_be_replaced_by_url_backed_candidate(self):
        pipeline = object.__new__(AgenticPipeline)
        ctx = DummyContext(
            post_data={
                "title": "지금보니 ㅁㅁ세계 대역에서 추방시킨건 원래",
                "content_blocks": [
                    {"type": "text", "text": "탐태창이 ㅁㅁ세계에 밀려서 2위가 되버려서"},
                    {"type": "text", "text": "탐태창이 지금 현역이었으면 세종파딱 존나 팼지 ㅇㅇ"},
                ],
            },
            comments=[],
            search_results=[],
            fetched_page_info=[],
        )
        replacement = pipeline._select_url_backed_replacement_for_weak_final(
            ctx=ctx,
            final_title="탐란오리가 삼대장수 줄검 코락스 대체역사 소설",
            final_url=None,
            title_candidates=[
                DetectedTitle(
                    official_title="탐란오리가 삼대장수 줄검 코락스 대체역사 소설",
                    confidence="High",
                    source_tier="llm_only",
                ),
                DetectedTitle(
                    official_title="탐관오리가 상태창을 숨김",
                    heretic_url="https://namu.wiki/w/%ED%83%90%EA%B4%80%EC%98%A4%EB%A6%AC%EA%B0%80%20%EC%83%81%ED%83%9C%EC%B0%BD%EC%9D%84%20%EC%88%A8%EA%B9%80",
                    confidence="High",
                    source_tier="mixed",
                ),
            ],
        )
        self.assertIsNotNone(replacement)
        self.assertEqual(replacement.official_title, "탐관오리가 상태창을 숨김")

    def test_single_locked_official_candidate_rescues_from_ocr_noise(self):
        pipeline = object.__new__(AgenticPipeline)
        candidate = pipeline._select_single_locked_official_candidate(
            title_candidates=[
                DetectedTitle(
                    official_title="탐관오리가 상태창을 숨김",
                    heretic_url="https://book.novelpia.com/novel/97",
                    confidence="High",
                    alias_or_mention="탐태창",
                    source_tier="official_detail",
                    locked=True,
                ),
                DetectedTitle(
                    official_title="탐로몬리가 삼내창설줄",
                    confidence="High",
                    source_tier="llm_only",
                ),
                DetectedTitle(
                    official_title="50화무 탐관오리가 상태창을 숨김 코락스",
                    heretic_url="https://book.novelpia.com/novel/97",
                    confidence="High",
                    source_tier="mixed",
                ),
            ],
        )
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.official_title, "탐관오리가 상태창을 숨김")

    def test_author_anchor_conflict_clears_same_surface_wrong_work(self):
        pipeline = object.__new__(AgenticPipeline)
        ctx = DummyContext(
            post_data={
                "title": "작가갑 결혼순결에서 하인들에게도 멸시당한게 고증에 맞는거였구나",
                "content_blocks": [
                    {"type": "text", "text": "아내가 결혼순결 요구해서 집안 하인들도 멸시하는데"}
                ],
            },
            comments=[],
            snippet_hints={
                "author_hints": [
                    {"name": "작가갑", "source": "author_bridge"},
                ]
            },
            fetched_page_info=[
                {
                    "url": "https://page.kakao.com/content/123456",
                    "structured_info": {
                        "page_type": "novel_page",
                        "title": "결혼순결",
                        "author": "다른작가",
                    },
                }
            ],
            search_results=[
                {
                    "title": "작가갑 - 작가 - 리디",
                    "url": "https://ridibooks.com/author/1",
                    "content": "작가갑 작가의 작품을 확인하세요.",
                }
            ],
        )
        self.assertTrue(
            pipeline._has_author_anchor_title_author_conflict(
                ctx,
                title="결혼순결",
                url="https://page.kakao.com/content/123456",
            )
        )

    def test_author_anchor_no_conflict_when_candidate_author_matches(self):
        pipeline = object.__new__(AgenticPipeline)
        ctx = DummyContext(
            post_data={
                "title": "작가갑 결혼순결에서 하인들에게도 멸시당한게 고증에 맞는거였구나",
                "content_blocks": [],
            },
            comments=[],
            snippet_hints={"author_hints": [{"name": "작가갑", "source": "author_bridge"}]},
            fetched_page_info=[
                {
                    "url": "https://page.kakao.com/content/123456",
                    "structured_info": {
                        "page_type": "novel_page",
                        "title": "결혼순결",
                        "author": "작가갑",
                    },
                }
            ],
            search_results=[],
        )
        self.assertFalse(
            pipeline._has_author_anchor_title_author_conflict(
                ctx,
                title="결혼순결",
                url="https://page.kakao.com/content/123456",
            )
        )

    def test_author_prefixed_concept_title_risk_when_candidate_author_unknown(self):
        pipeline = object.__new__(AgenticPipeline)
        ctx = DummyContext(
            post_data={
                "title": "작가갑 결혼순결에서 하인들에게도 멸시당한게 고증에 맞는거였구나",
                "content_blocks": [
                    {"type": "text", "text": "아내가 결혼순결 요구해서 집안 하인들도 멸시하는데"},
                    {"type": "text", "text": "중세 문화에서는 결혼 인증이 혼인성사 같은 게 아니라 관계라서"},
                ],
            },
            comments=[],
            snippet_hints={"author_hints": [{"name": "작가갑", "source": "author_bridge"}]},
            fetched_page_info=[
                {
                    "url": "https://series.naver.com/novel/detail.series?productNo=123",
                    "structured_info": {
                        "page_type": "novel_page",
                        "title": "결혼순결",
                    },
                }
            ],
            search_results=[
                {
                    "title": "작가갑 - 나무위키",
                    "url": "https://namu.wiki/w/x",
                    "content": "작가는 작가갑. 대표작은 다른 작품이다.",
                },
                {
                    "title": "결혼순결 - 네이버 시리즈",
                    "url": "https://series.naver.com/novel/detail.series?productNo=123",
                    "content": "결혼순결 작품 소개",
                },
            ],
        )

        self.assertTrue(
            pipeline._has_author_prefixed_concept_title_risk(
                ctx,
                title="결혼순결",
                url="https://series.naver.com/novel/detail.series?productNo=123",
            )
        )

    def test_author_prefixed_concept_title_risk_skips_when_author_matches(self):
        pipeline = object.__new__(AgenticPipeline)
        ctx = DummyContext(
            post_data={
                "title": "작가갑 결혼순결에서 하인들에게도 멸시당한게 고증에 맞는거였구나",
                "content_blocks": [
                    {"type": "text", "text": "아내가 결혼순결 요구해서 집안 하인들도 멸시하는데"}
                ],
            },
            comments=[],
            snippet_hints={"author_hints": [{"name": "작가갑", "source": "author_bridge"}]},
            fetched_page_info=[
                {
                    "url": "https://series.naver.com/novel/detail.series?productNo=123",
                    "structured_info": {
                        "page_type": "novel_page",
                        "title": "결혼순결",
                        "author": "작가갑",
                    },
                }
            ],
            search_results=[],
        )

        self.assertFalse(
            pipeline._has_author_prefixed_concept_title_risk(
                ctx,
                title="결혼순결",
                url="https://series.naver.com/novel/detail.series?productNo=123",
            )
        )

    def test_prompt_overlay_contains_small_model_negative_examples(self):
        overlay = "\n".join(_build_relevance_contract_overlay())
        self.assertIn("Mixed Unknown", overlay)
        self.assertIn("일반명사", overlay)
        self.assertIn("트로프", overlay)
        self.assertIn("코스튬+인명", overlay)
        self.assertIn("의미/뜻/차이", overlay)
        self.assertIn("OCR/이미지", overlay)
        self.assertIn("canonical_work_alias에는 정식 제목을 넣지 않는다", overlay)
        self.assertIn("store_in_slang_db=true는 순수 작품 약칭", overlay)
        self.assertIn("ambiguous_title_stem", overlay)
        self.assertIn("정식 제목과 짧은 약칭이 함께 보이면", overlay)

    def test_expert_prompts_contain_small_model_slang_storage_contract(self):
        self.assertIn("소형 모델용 약칭 표면 분리 규칙", DECODER_SYSTEM)
        self.assertIn("문장 전체", DECODER_SYSTEM)
        self.assertIn("slang_insight DB 저장 계약", VERIFIER_PROMPT)
        self.assertIn("canonical_work_alias: 순수 작품 약칭만", VERIFIER_PROMPT)
        self.assertIn("store_in_slang_db=true는 pure_work_alias", VERIFIER_PROMPT)
        self.assertIn("ambiguous_title_stem", VERIFIER_PROMPT)
        self.assertIn("정식 제목과 짧은 약칭이 함께 보이면", VERIFIER_PROMPT)
        self.assertIn("noisy term은 차단하되 clean alias는 보존", VERIFIER_PROMPT)


if __name__ == "__main__":
    unittest.main()
