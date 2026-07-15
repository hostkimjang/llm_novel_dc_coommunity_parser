from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import llm_batch.experts.arbiter as arbiter_module  # noqa: E402
from llm_batch.experts.arbiter import ArbiterExpert  # noqa: E402
from llm_batch.experts.deliberation import DeliberationOrchestrator  # noqa: E402
from llm_batch.experts.orchestrator import ConversationContext, ExpertType  # noqa: E402
from llm_batch.slang.slang_db import SlangDBManager, slang_db_alias_seed_is_safe  # noqa: E402


class DummyLLM:
    def __init__(self, response: dict | None = None):
        self.response = response or {}

    def _stream_chat_http(self, **_: object) -> str:
        return json.dumps(self.response, ensure_ascii=False)


def _arbiter(response: dict | None = None) -> ArbiterExpert:
    return ArbiterExpert(DummyLLM(response))


def _arbiter_response(title: str, *, discussion_type: str = "review") -> dict:
    return {
        "final_decision": {
            "is_relevant": True,
            "is_novel_discussion": True,
            "official_title": title,
            "official_novel_title": title,
            "heretic_url": "https://novelpia.com/novel/12345",
            "confidence": "High",
            "discussion_type": discussion_type,
            "reason": "LLM seed decision",
            "final_reasoning": "LLM seed decision",
            "notes": "",
        },
        "metadata": {},
        "evidence_chain": [],
    }


class ArbiterCuratedAliasGuardTest(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_known_abbr = arbiter_module.KNOWN_ABBREVIATIONS
        self._orig_known_title_abbr = arbiter_module.KNOWN_TITLE_ABBREVIATIONS
        arbiter_module.KNOWN_ABBREVIATIONS = {"abc": "Alpha Novel"}
        arbiter_module.KNOWN_TITLE_ABBREVIATIONS = {"담텔기": "괴담 호텔 탈출기"}

    def tearDown(self) -> None:
        arbiter_module.KNOWN_ABBREVIATIONS = self._orig_known_abbr
        arbiter_module.KNOWN_TITLE_ABBREVIATIONS = self._orig_known_title_abbr

    def test_bare_curated_alias_does_not_exempt_arbiter_guards(self):
        arbiter = _arbiter()
        ctx = ConversationContext(
            post_id=1,
            post_data={
                "post_id": 1,
                "title": "abc만 보였음",
                "content_blocks": [{"type": "text", "text": "밥 먹는데 같이 소설 볼 친구 있었으면 좋겠다는 잡담"}],
            },
            comments=[],
        )

        self.assertTrue(arbiter._curated_alias_for_title_mentioned_in_post_main(ctx, "Alpha Novel"))
        self.assertFalse(arbiter._has_curated_alias_contextual_work_anchor(ctx, "Alpha Novel"))
        self.assertFalse(arbiter._has_curated_alias_guard_exception(ctx, "Alpha Novel"))

    def test_semantic_no_work_blocks_curated_alias_guard_exception(self):
        arbiter = _arbiter()
        ctx = ConversationContext(
            post_id=2,
            post_data={
                "post_id": 2,
                "title": "abc 12화 스포라는 말만 봄",
                "content_blocks": [{"type": "text", "text": "작품 이야기가 아니라 그냥 잡담임"}],
            },
            comments=[],
        )
        ctx.uncertainty_sources.append("intent_permit_for_title_search=false(semantic_seed_review_not_specific_work)")
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "community_banter",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                }
            },
        )
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "community_banter",
                "detected_entities": {"possible_titles": ["abc"]},
                "context_clues": {"has_episode_reference": True, "is_spoiler_discussion": True},
            },
        )

        self.assertTrue(arbiter._curated_alias_for_title_mentioned_in_post_main(ctx, "Alpha Novel"))
        self.assertFalse(arbiter._has_curated_alias_contextual_work_anchor(ctx, "Alpha Novel"))
        self.assertFalse(arbiter._has_curated_alias_guard_exception(ctx, "Alpha Novel"))

    def test_forced_upgrade_blocks_alias_only_nonwork_relation_hold(self):
        arbiter = _arbiter()
        ctx = ConversationContext(
            post_id=4,
            post_data={
                "post_id": 4,
                "title": "가챠펑크 오늘 호텔 스트레스 많이 받을거야",
                "content_blocks": [
                    {"type": "text", "text": "아침 모르겠다는 것이야 아무것도 모름 경축 대성공"},
                    {"type": "text", "text": "근데 그런 스트레스도 필요하다"},
                ],
            },
            comments=[],
        )
        verifier_out = {
            "verification_result": {
                "grounding_check": {
                    "anchor_found": "title_mention",
                    "anchor_text": "가챠펑크 오늘 호텔 스트레스 많이 받을거야",
                },
                "counter_arguments": [
                    {
                        "issue": "본문의 맥락이 작품 토론이 아님",
                        "severity": "critical",
                        "action": "reject",
                    }
                ],
                "relation_judgment": {
                    "relation_type": "work_specific_nickname",
                    "discussion_target": "specific_work",
                    "promotion_decision": "hold",
                    "reason": (
                        "게시글의 제목인 '가챠펑크'는 후보 작품의 약칭일 가능성이 높으나 "
                        "작품의 줄거리, 캐릭터, 설정 등 구체적인 정보를 담고 있지 않고 "
                        "본문은 작품에 대한 논의가 아닌 커뮤니티 내의 농담입니다. "
                        "explicit_alias_bridge_count가 0임."
                    ),
                    "search_support_summary": {
                        "explicit_alias_bridge_count": 0,
                        "closed_bridge": False,
                        "converged_official_signal": True,
                        "bridge_quality": "weak",
                    },
                    "post_direct_grounding": False,
                },
            }
        }

        self.assertTrue(
            arbiter._should_block_memory_query_forced_upgrade(
                ctx,
                verifier_out,
                "가챠 중독자의 퓨전펑크 생활",
            )
        )

    def test_forced_upgrade_allows_specific_work_relation_allow(self):
        arbiter = _arbiter()
        ctx = ConversationContext(
            post_id=5,
            post_data={
                "post_id": 5,
                "title": "럽코빙의 원래도 그렇게 대놓고 언급 안했는데",
                "content_blocks": [
                    {"type": "text", "text": "전생 현실 언급 방식이랑 연중 직전 화 얘기"},
                ],
            },
            comments=[],
        )
        verifier_out = {
            "verification_result": {
                "grounding_check": {
                    "anchor_found": "title_mention",
                    "anchor_text": "럽코빙",
                },
                "counter_arguments": [],
                "relation_judgment": {
                    "relation_type": "work_specific_nickname",
                    "discussion_target": "specific_work",
                    "promotion_decision": "allow",
                    "reason": "본문이 연재 중단 및 전생 설정 언급 등 특정 작품의 전개 방식을 지목함",
                    "search_support_summary": {
                        "explicit_alias_bridge_count": 0,
                        "closed_bridge": False,
                        "converged_official_signal": True,
                        "bridge_quality": "weak",
                    },
                    "post_direct_grounding": False,
                },
            }
        }

        self.assertFalse(
            arbiter._should_block_memory_query_forced_upgrade(
                ctx,
                verifier_out,
                "이거 럽코 빙의물인가요",
            )
        )

    def test_work_context_curated_alias_can_exempt_arbiter_guards(self):
        arbiter = _arbiter()
        ctx = ConversationContext(
            post_id=3,
            post_data={
                "post_id": 3,
                "title": "abc 12화 스포 얘기",
                "content_blocks": [{"type": "text", "text": "주인공이 이번 회차에서 한 선택 이야기"}],
            },
            comments=[],
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "discuss_work",
                    "title_novel_terms": ["abc"],
                    "semantic_seed_review": {"is_specific_work_discussion": True},
                }
            },
        )
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "work_discussion",
                "detected_entities": {
                    "possible_titles": ["abc"],
                    "possible_characters": ["주인공"],
                },
                "context_clues": {"has_episode_reference": True, "is_spoiler_discussion": True},
            },
        )

        self.assertTrue(arbiter._curated_alias_for_title_mentioned_in_post_main(ctx, "Alpha Novel"))
        self.assertTrue(arbiter._has_curated_alias_contextual_work_anchor(ctx, "Alpha Novel"))
        self.assertTrue(arbiter._has_curated_alias_guard_exception(ctx, "Alpha Novel"))

    def test_loop324_originality_cue_prevents_curated_alias_null_overblock(self):
        arbiter_module.KNOWN_TITLE_ABBREVIATIONS = {
            "괴담출근": "괴담에 떨어져도 출근을 해야 하는구나"
        }
        arbiter = _arbiter()
        title = "괴담에 떨어져도 출근을 해야 하는구나"
        ctx = ConversationContext(
            post_id=11708443,
            post_data={
                "post_id": 11708443,
                "title": "괴담출근정도는 돼야 독창성 운운할수 있는거다",
                "content_blocks": [
                    {
                        "type": "ocr_text",
                        "text": "괴담출근이 SCP 재단에 영감을 받아 만들어진 작품인지 묻는 이미지 캡처",
                    }
                ],
            },
            comments=[],
        )
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "work_discussion",
                "detected_entities": {"possible_titles": ["괴담출근"]},
                "context_clues": {},
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "discuss_work",
                    "title_novel_terms": ["괴담출근"],
                    "semantic_seed_review": {"is_specific_work_discussion": True},
                }
            },
        )

        self.assertTrue(arbiter._curated_alias_for_title_mentioned_in_post_main(ctx, title))
        self.assertTrue(arbiter._has_curated_alias_contextual_work_anchor(ctx, title))
        self.assertFalse(arbiter._curated_alias_lacks_contextual_work_anchor(ctx, title))
        self.assertTrue(arbiter._has_curated_alias_guard_exception(ctx, title))

    def test_loop324_cover_change_cue_prevents_curated_alias_null_overblock(self):
        arbiter_module.KNOWN_TITLE_ABBREVIATIONS = {"빌환": "빌어먹을 환생"}
        arbiter = _arbiter()
        title = "빌어먹을 환생"
        ctx = ConversationContext(
            post_id=11718099,
            post_data={
                "post_id": 11718099,
                "title": "빌환 표지변경됨",
                "content_blocks": [],
            },
            comments=[],
        )
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "work_discussion",
                "detected_entities": {"possible_titles": ["빌환"]},
                "context_clues": {},
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "discuss_work",
                    "title_novel_terms": ["빌환"],
                    "semantic_seed_review": {"is_specific_work_discussion": True},
                }
            },
        )

        self.assertTrue(arbiter._curated_alias_for_title_mentioned_in_post_main(ctx, title))
        self.assertTrue(arbiter._has_curated_alias_contextual_work_anchor(ctx, title))
        self.assertFalse(arbiter._curated_alias_lacks_contextual_work_anchor(ctx, title))

    def test_loop347_slice_of_life_cue_prevents_gigongju_null_overblock(self):
        arbiter_module.KNOWN_TITLE_ABBREVIATIONS = {
            "기계공주": "헌터갤러리의 국가권력급 기계공주"
        }
        arbiter = _arbiter()
        title = "헌터갤러리의 국가권력급 기계공주"
        ctx = ConversationContext(
            post_id=11706827,
            post_data={
                "post_id": 11706827,
                "title": "기계공주는 그냥 계속 일상물로 있으면 좋겠음",
                "content_blocks": [
                    {
                        "type": "text",
                        "text": (
                            "현실에서 좆같은 일들 겪고 고민만 존나 쌓이고 그러니까 "
                            "소설에선 그냥 어린이 프로처럼 대충 해결함 대충 행복해짐 같은 게 보고 싶어"
                        ),
                    }
                ],
            },
            comments=[
                "딱 기계공주 최우선 후보군이네",
                "행복을 돌려줄게 장붕아.",
            ],
        )
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "work_discussion",
                "detected_entities": {"possible_titles": ["기계공주"]},
                "context_clues": {},
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "discuss_work",
                    "title_novel_terms": ["기계공주"],
                    "semantic_seed_review": {"is_specific_work_discussion": True},
                }
            },
        )

        self.assertTrue(arbiter._curated_alias_for_title_mentioned_in_post_main(ctx, title))
        self.assertTrue(arbiter._has_curated_alias_contextual_work_anchor(ctx, title))
        self.assertFalse(arbiter._curated_alias_lacks_contextual_work_anchor(ctx, title))

    def test_loop347_character_relation_cue_prevents_asaenggal_null_overblock(self):
        arbiter_module.KNOWN_TITLE_ABBREVIATIONS = {"아생갤": "아카데미 생존 갤러리"}
        arbiter = _arbiter()
        title = "아카데미 생존 갤러리"
        ctx = ConversationContext(
            post_id=11714907,
            post_data={
                "post_id": 11714907,
                "title": "아생갤 작가가 라나 견제 들어가네",
                "content_blocks": [
                    {"type": "text", "text": "극악무도한 엘리단..."},
                    {"type": "text", "text": "그래도 정실은 라나인것이야"},
                ],
            },
            comments=["견제가 아니라 이미 괴이잖아  - dc App"],
        )
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "work_discussion",
                "detected_entities": {
                    "possible_titles": ["아생갤"],
                    "possible_characters": ["라나"],
                },
                "context_clues": {},
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "discuss_work",
                    "title_novel_terms": ["아생갤"],
                    "semantic_seed_review": {"is_specific_work_discussion": True},
                }
            },
        )

        self.assertTrue(arbiter._curated_alias_for_title_mentioned_in_post_main(ctx, title))
        self.assertTrue(arbiter._has_curated_alias_contextual_work_anchor(ctx, title))
        self.assertFalse(arbiter._curated_alias_lacks_contextual_work_anchor(ctx, title))

    def test_deliberation_rebuild_prompt_uses_discourse_output_for_alias_hint(self):
        arbiter = _arbiter()
        deliberation = DeliberationOrchestrator(arbiter, arbiter.llm)
        ctx = ConversationContext(
            post_id=33,
            post_data={
                "post_id": 33,
                "title": "abc 12화 스포 얘기",
                "content_blocks": [{"type": "text", "text": "주인공 선택 얘기"}],
            },
            comments=[],
        )
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "novel_discussion",
                "detected_entities": {"possible_titles": ["abc"]},
                "context_clues": {"has_episode_reference": True, "is_spoiler_discussion": True},
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "episode_discussion",
                    "semantic_seed_review": {"is_specific_work_discussion": True},
                }
            },
        )

        prompt = deliberation._rebuild_arbiter_user_prompt(ctx, "\n[EVIDENCE]\n")

        self.assertIn("[EVIDENCE]", prompt)
        self.assertIn("abc 12화 스포 얘기", prompt)

    def test_comment_only_curated_alias_does_not_exempt_arbiter_guards(self):
        arbiter = _arbiter()
        ctx = ConversationContext(
            post_id=4,
            post_data={
                "post_id": 4,
                "title": "그냥 친구랑 소설 보고 싶다",
                "content_blocks": [{"type": "text", "text": "작품 특정 얘기가 아닌 잡담"}],
            },
            comments=["abc"],
        )

        self.assertFalse(arbiter._curated_alias_for_title_mentioned_in_post_main(ctx, "Alpha Novel"))
        self.assertFalse(arbiter._has_curated_alias_guard_exception(ctx, "Alpha Novel"))

    def test_strong_title_support_accepts_active_official_detail_search_hit(self):
        arbiter = _arbiter()
        ctx = ConversationContext(post_id=5, post_data={"post_id": 5, "title": "Alpha Novel 후기"}, comments=[])
        ctx.search_results = [
            {
                "title": "Alpha Novel - 노벨피아",
                "url": "https://novelpia.com/novel/12345",
                "content": "Alpha Novel 웹소설 공식 상세 페이지",
                "_trust_score": 0.9,
            }
        ]

        self.assertTrue(arbiter._has_strong_title_support(ctx, "Alpha Novel"))
        self.assertTrue(arbiter._has_official_title_evidence(ctx, "Alpha Novel"))
        self.assertTrue(arbiter._has_official_title_evidence(ctx, "Alpha Novel"))

    def test_strong_title_support_accepts_active_fetched_detail_title(self):
        arbiter = _arbiter()
        ctx = ConversationContext(post_id=6, post_data={"post_id": 6, "title": "Alpha Novel"}, comments=[])
        ctx.fetched_page_info = [
            {
                "url": "https://novelpia.com/novel/12345",
                "structured_info": {
                    "page_type": "novel_detail",
                    "title": "Alpha Novel",
                },
            }
        ]

        self.assertTrue(arbiter._has_strong_title_support(ctx, "Alpha Novel"))

    def test_strong_title_support_rejects_deleted_or_community_detail_state(self):
        arbiter = _arbiter()
        deleted_ctx = ConversationContext(post_id=7, post_data={"post_id": 7, "title": "Alpha Novel"}, comments=[])
        deleted_ctx.search_results = [
            {
                "title": "Alpha Novel - 노벨피아",
                "url": "https://novelpia.com/novel/12345",
                "content": "Alpha Novel",
                "_trust_score": 0.0,
            }
        ]
        deleted_ctx.fetched_page_info = [
            {
                "url": "https://novelpia.com/novel/12345",
                "structured_info": {
                    "page_type": "novel_detail",
                    "content_status": "deleted",
                    "title": "Alpha Novel",
                },
            }
        ]

        community_ctx = ConversationContext(post_id=8, post_data={"post_id": 8, "title": "Alpha Novel"}, comments=[])
        community_ctx.search_results = [
            {
                "title": "Alpha Novel - 커뮤니티 글",
                "url": "https://novelpia.com/novel/12345",
                "content": "Alpha Novel",
                "_trust_score": 0.0,
            }
        ]
        community_ctx.fetched_page_info = [
            {
                "url": "https://novelpia.com/novel/12345",
                "structured_info": {
                    "page_type": "community_post",
                    "title": "Alpha Novel",
                },
            }
        ]

        listing_ctx = ConversationContext(post_id=10, post_data={"post_id": 10, "title": "Alpha Novel"}, comments=[])
        listing_ctx.search_results = [
            {
                "title": "Alpha Novel - 노벨피아 목록",
                "url": "https://novelpia.com/novel/12345",
                "content": "Alpha Novel",
                "_trust_score": 0.0,
            }
        ]
        listing_ctx.fetched_page_info = [
            {
                "url": "https://novelpia.com/novel/12345",
                "structured_info": {
                    "page_type": "listing",
                    "title": "Alpha Novel",
                },
            }
        ]

        self.assertFalse(arbiter._has_strong_title_support(deleted_ctx, "Alpha Novel"))
        self.assertFalse(arbiter._has_strong_title_support(community_ctx, "Alpha Novel"))
        self.assertFalse(arbiter._has_strong_title_support(listing_ctx, "Alpha Novel"))
        self.assertFalse(arbiter._has_official_title_evidence(deleted_ctx, "Alpha Novel"))
        self.assertFalse(arbiter._has_official_title_evidence(community_ctx, "Alpha Novel"))
        self.assertFalse(arbiter._has_official_title_evidence(listing_ctx, "Alpha Novel"))

    def test_known_abbreviation_hint_without_official_detail_is_not_strong_support(self):
        arbiter = _arbiter()
        ctx = ConversationContext(post_id=9, post_data={"post_id": 9, "title": "abc 후기"}, comments=[])
        ctx.snippet_hints = {
            "abbreviation_hints": [
                {
                    "abbrev": "abc",
                    "full": "Alpha Novel",
                    "source": "known_abbreviation",
                    "confidence": "high",
                }
            ]
        }

        self.assertFalse(arbiter._has_strong_title_support(ctx, "Alpha Novel"))
        self.assertFalse(arbiter._has_official_title_evidence(ctx, "Alpha Novel"))

    def test_official_title_evidence_rejects_short_title_substring_only_match(self):
        arbiter = _arbiter()
        ctx = ConversationContext(post_id=11, post_data={"post_id": 11, "title": "오러 질문"}, comments=[])
        ctx.search_results = [
            {
                "title": "오러클 마법사 - 노벨피아",
                "url": "https://novelpia.com/novel/12345",
                "content": "오러클 마법사 공식 상세 페이지",
                "_trust_score": 0.95,
            }
        ]

        self.assertFalse(arbiter._has_official_title_evidence(ctx, "오러"))

    def test_meme_guard_blocks_abbrev_only_no_work_even_with_official_support(self):
        arbiter = _arbiter(_arbiter_response("Alpha Novel", discussion_type="meme"))
        ctx = ConversationContext(
            post_id=12,
            post_data={
                "post_id": 12,
                "title": "abcㅋㅋ",
                "content_blocks": [{"type": "text", "text": "웃김"}],
            },
            comments=[],
        )
        ctx.uncertainty_sources.append("intent_permit_for_title_search=false(semantic_seed_review_not_specific_work)")
        ctx.search_results = [
            {
                "title": "Alpha Novel - 노벨피아",
                "url": "https://novelpia.com/novel/12345",
                "content": "Alpha Novel 웹소설 공식 상세 페이지",
                "_trust_score": 0.95,
            }
        ]
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "community_banter",
                "detected_entities": {"possible_titles": ["abc"]},
                "context_clues": {},
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "community_banter",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                }
            },
        )
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "overall_confidence": "low",
                "decoded_terms": [
                    {
                        "original": "abc",
                        "best_match": {"title": "Alpha Novel", "confidence": "Low"},
                    }
                ],
            },
        )
        ctx.set_expert_output(
            ExpertType.VERIFIER,
            {
                "verification_result": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_novel_title": "Alpha Novel",
                        "confidence": "Medium",
                    },
                    "grounding_check": {
                        "anchor_found": "title_abbrev_mention",
                        "decoder_grounded": False,
                        "matched_alias": "abc",
                        "title_abbrev_mentioned": True,
                    },
                }
            },
        )

        decision = arbiter.analyze(ctx)["final_decision"]

        self.assertFalse(decision["is_relevant"])
        self.assertIsNone(decision["official_title"])
        self.assertTrue(decision.get("_meme_blocked"))

    def test_low_confidence_guard_blocks_abbrev_only_no_work_even_with_official_support(self):
        arbiter = _arbiter(_arbiter_response("Alpha Novel", discussion_type="review"))
        ctx = ConversationContext(
            post_id=13,
            post_data={
                "post_id": 13,
                "title": "abc 후기",
                "content_blocks": [
                    {
                        "type": "text",
                        "text": "밥 먹는데 같이 소설 보는 친구 있었으면 좋겠다는 일상 한탄 글입니다. 특정 작품 이야기는 아닙니다.",
                    }
                ],
            },
            comments=[],
        )
        ctx.uncertainty_sources.append("intent_permit_for_title_search=false(semantic_seed_review_not_specific_work)")
        ctx.search_results = [
            {
                "title": "Alpha Novel - 노벨피아",
                "url": "https://novelpia.com/novel/12345",
                "content": "Alpha Novel 웹소설 공식 상세 페이지",
                "_trust_score": 0.95,
            }
        ]
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "community_banter",
                "detected_entities": {"possible_titles": ["abc"]},
                "context_clues": {},
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "community_banter",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                }
            },
        )
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "overall_confidence": "low",
                "decoded_terms": [
                    {
                        "original": "abc",
                        "best_match": {"title": "Alpha Novel", "confidence": "Low"},
                    }
                ],
            },
        )
        ctx.set_expert_output(
            ExpertType.VERIFIER,
            {
                "verification_result": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_novel_title": "Alpha Novel",
                        "confidence": "Medium",
                    },
                    "grounding_check": {
                        "anchor_found": "title_abbrev_mention",
                        "decoder_grounded": False,
                        "matched_alias": "abc",
                        "title_abbrev_mentioned": True,
                    },
                    "slang_insight": {
                        "decode_verified": True,
                        "decoded_term": "Alpha Novel",
                    },
                }
            },
        )

        decision = arbiter.analyze(ctx)["final_decision"]

        self.assertFalse(decision["is_relevant"])
        self.assertIsNone(decision["official_title"])
        self.assertIn("저신뢰 차단", decision.get("notes", ""))

    def test_multi_work_guard_blocks_alias_only_single_title_for_compare_context(self):
        arbiter = _arbiter(_arbiter_response("Alpha Novel", discussion_type="review"))
        ctx = ConversationContext(
            post_id=14,
            post_data={
                "post_id": 14,
                "title": "abc랑 Beta Novel 어떰?",
                "content_blocks": [{"type": "text", "text": "둘 중에 뭐 볼지 고민"}],
            },
            comments=[],
        )
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "community_banter",
                "detected_entities": {"possible_titles": ["abc", "Beta Novel"]},
                "context_clues": {},
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "ask_compare",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                }
            },
        )
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "overall_confidence": "medium",
                "decoded_terms": [
                    {
                        "original": "abc",
                        "best_match": {"title": "Alpha Novel", "confidence": "Medium"},
                    },
                    {
                        "original": "Beta Novel",
                        "best_match": {"title": "Beta Novel", "confidence": "Medium"},
                    },
                ],
            },
        )
        ctx.set_expert_output(
            ExpertType.VERIFIER,
            {
                "verification_result": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_novel_title": "Alpha Novel",
                        "confidence": "Medium",
                    },
                    "grounding_check": {
                        "anchor_found": "title_abbrev_mention",
                        "matched_alias": "abc",
                        "title_abbrev_mentioned": True,
                    },
                }
            },
        )

        decision = arbiter.analyze(ctx)["final_decision"]

        self.assertIsNone(decision["official_title"])
        self.assertIsNone(decision["official_novel_title"])
        self.assertIn("multi_work_guard", decision.get("_title_null_block_reasons", []))

    def test_multi_work_guard_allows_curated_alias_with_work_anchor(self):
        arbiter = _arbiter(_arbiter_response("Alpha Novel", discussion_type="review"))
        ctx = ConversationContext(
            post_id=15,
            post_data={
                "post_id": 15,
                "title": "abc 12화랑 Beta Novel 비교 후기?",
                "content_blocks": [{"type": "text", "text": "주인공이 이번 회차에서 한 선택이 더 좋았음"}],
            },
            comments=[],
        )
        ctx.search_results = [
            {
                "title": "Alpha Novel - 노벨피아",
                "url": "https://novelpia.com/novel/12345",
                "content": "Alpha Novel 웹소설 공식 상세 페이지",
                "_trust_score": 0.95,
            }
        ]
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "work_discussion",
                "detected_entities": {
                    "possible_titles": ["abc", "Beta Novel"],
                    "possible_characters": ["주인공"],
                },
                "context_clues": {"has_episode_reference": True, "is_spoiler_discussion": True},
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "discuss_work",
                    "title_novel_terms": ["abc"],
                    "semantic_seed_review": {"is_specific_work_discussion": True},
                }
            },
        )
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "overall_confidence": "medium",
                "decoded_terms": [
                    {
                        "original": "abc",
                        "best_match": {"title": "Alpha Novel", "confidence": "Medium"},
                    },
                    {
                        "original": "Beta Novel",
                        "best_match": {"title": "Beta Novel", "confidence": "Medium"},
                    },
                ],
            },
        )
        ctx.set_expert_output(
            ExpertType.VERIFIER,
            {
                "verification_result": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_novel_title": "Alpha Novel",
                        "confidence": "Medium",
                    },
                    "grounding_check": {
                        "anchor_found": "plot_mention",
                        "matched_alias": "abc",
                        "title_abbrev_mentioned": True,
                    },
                }
            },
        )

        decision = arbiter.analyze(ctx)["final_decision"]

        self.assertTrue(decision["is_relevant"])
        self.assertEqual(decision["official_title"], "Alpha Novel")
        self.assertNotIn("multi_work_guard", decision.get("_title_null_block_reasons", []))

    def test_verifier_veto_does_not_accept_post_title_abbrev_without_hard_support(self):
        arbiter = _arbiter(_arbiter_response("Alpha Novel", discussion_type="review"))
        ctx = ConversationContext(
            post_id=16,
            post_data={
                "post_id": 16,
                "title": "abc 후기",
                "content_blocks": [{"type": "text", "text": "그냥 같이 소설 보는 친구 있었으면 좋겠다는 잡담"}],
            },
            comments=[],
        )
        ctx.snippet_hints = {
            "abbreviation_hints": [
                {
                    "abbrev": "abc",
                    "full": "Alpha Novel",
                    "source": "known_abbreviation",
                    "confidence": "high",
                }
            ]
        }
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "community_banter",
                "detected_entities": {"possible_titles": ["abc"]},
                "context_clues": {},
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "community_banter",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                }
            },
        )
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "overall_confidence": "medium",
                "decoded_terms": [
                    {
                        "original": "abc",
                        "best_match": {"title": "Alpha Novel", "confidence": "Medium"},
                        "grounding": {"anchor_type": "title_mention"},
                    }
                ],
            },
        )
        ctx.set_expert_output(
            ExpertType.VERIFIER,
            {
                "verification_result": {
                    "is_relevant": False,
                    "rejection_reason": "작품 본문 근거 없이 등록 약칭 표면만 있음",
                    "novel_identity": {
                        "official_novel_title": "Alpha Novel",
                        "confidence": "Medium",
                    },
                    "grounding_check": {
                        "anchor_found": "title_abbrev_mention",
                        "matched_alias": "abc",
                        "title_abbrev_mentioned": True,
                    },
                }
            },
        )

        decision = arbiter.analyze(ctx)["final_decision"]

        self.assertFalse(decision["is_relevant"])
        self.assertIsNone(decision["official_title"])
        self.assertFalse(decision.get("_verifier_veto_exempt", False))
        self.assertIn("Verifier 거부권", decision.get("notes", ""))

    def test_verifier_veto_allows_post_title_abbrev_with_hard_support(self):
        arbiter = _arbiter(_arbiter_response("괴담 호텔 탈출기", discussion_type="review"))
        ctx = ConversationContext(
            post_id=17,
            post_data={
                "post_id": 17,
                "title": "담텔기 12화 후기",
                "content_blocks": [{"type": "text", "text": "주인공이 이번 회차에서 한 선택이 좋았음"}],
            },
            comments=[],
        )
        ctx.snippet_hints = {
            "abbreviation_hints": [
                {
                    "abbrev": "담텔기",
                    "full": "괴담 호텔 탈출기",
                    "source": "known_abbreviation",
                    "confidence": "high",
                }
            ]
        }
        ctx.add_evidence_for_candidate(
            "괴담 호텔 탈출기",
            "official_url",
            {"url": "https://series.naver.com/novel/detail.series?productNo=12345", "title": "괴담 호텔 탈출기"},
        )
        ctx.search_results = [
            {
                "title": "괴담 호텔 탈출기 - 네이버 시리즈",
                "url": "https://series.naver.com/novel/detail.series?productNo=12345",
                "content": "괴담 호텔 탈출기 웹소설 공식 상세 페이지",
                "_trust_score": 0.95,
            }
        ]
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "work_discussion",
                "detected_entities": {
                    "possible_titles": ["담텔기"],
                    "possible_characters": ["주인공"],
                },
                "context_clues": {"has_episode_reference": True, "is_spoiler_discussion": True},
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "discuss_work",
                    "title_novel_terms": ["담텔기"],
                    "semantic_seed_review": {"is_specific_work_discussion": True},
                }
            },
        )
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "overall_confidence": "medium",
                "decoded_terms": [
                    {
                        "original": "담텔기",
                        "best_match": {"title": "괴담 호텔 탈출기", "confidence": "Medium"},
                        "grounding": {"anchor_type": "title_mention"},
                    }
                ],
            },
        )
        ctx.set_expert_output(
            ExpertType.VERIFIER,
            {
                "verification_result": {
                    "is_relevant": False,
                    "rejection_reason": "Verifier false지만 다른 전문가/공식 근거가 강함",
                    "novel_identity": {
                        "official_novel_title": "괴담 호텔 탈출기",
                        "confidence": "Medium",
                    },
                    "grounding_check": {
                        "anchor_found": "title_abbrev_mention",
                        "matched_alias": "담텔기",
                        "title_abbrev_mentioned": True,
                    },
                }
            },
        )

        decision = arbiter.analyze(ctx)["final_decision"]

        self.assertTrue(decision["is_relevant"])
        self.assertEqual(decision["official_title"], "괴담 호텔 탈출기")
        self.assertTrue(decision.get("_verifier_veto_exempt"))

    def test_gallery_homage_explicit_alias_bridge_prevents_asaenggal_null_overblock(self):
        arbiter_module.KNOWN_TITLE_ABBREVIATIONS = {"아생갤": "아카데미 생존 갤러리"}
        title = "아카데미 생존 갤러리"
        arbiter = _arbiter(
            {
                "final_decision": {
                    "is_relevant": True,
                    "is_novel_discussion": True,
                    "official_title": title,
                    "official_novel_title": title,
                    "heretic_url": None,
                    "confidence": "High",
                    "discussion_type": "character_talk",
                    "reason": "LLM seed decision",
                    "final_reasoning": "LLM seed decision",
                    "notes": "",
                    "suspected_titles": [{"title": title, "confidence": "High"}],
                },
                "metadata": {},
                "evidence_chain": [],
            }
        )
        ctx = ConversationContext(
            post_id=11694035,
            post_data={
                "post_id": 11694035,
                "title": "아생갤) 가장 무서웠던 순간이",
                "content_blocks": [
                    {"type": "text", "text": "폐허가 된 도심지라면"},
                    {"type": "text", "text": "지진이라도 난 거냐, 전쟁이라도 터진 거냐"},
                    {"type": "text", "text": "현생 서사가 대체 어떻게 되길래"},
                ],
            },
            comments=["얼탱ㅋㅋㅋㅋㅋ"],
        )
        ctx.uncertainty_sources.append("intent_permit_for_title_search=false(semantic_seed_review_not_specific_work)")
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "work_discussion",
                "detected_entities": {"possible_titles": ["아생", "아생갤"]},
                "context_clues": {},
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "express_opinion",
                    "title_novel_terms": ["아생갤"],
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                }
            },
        )
        ctx.set_expert_output(
            ExpertType.VERIFIER,
            {
                "verification_result": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_novel_title": title,
                        "confidence": "Low",
                        "evidence_type": "community_mention",
                    },
                    "grounding_check": {
                        "anchor_found": "title_mention",
                        "matched_alias": "아생갤",
                        "title_abbrev_mentioned": True,
                    },
                    "relation_judgment": {
                        "relation_type": "explicit_alias",
                        "discussion_target": "specific_work",
                        "promotion_decision": "allow",
                        "confidence": "high",
                        "evidence_summary": {
                            "official_detail_count": 0,
                            "community_post_count": 6,
                            "explicit_alias_bridge_count": 2,
                        },
                        "search_support_summary": {
                            "official_exact_title_count": 0,
                            "community_alias_support_count": 21,
                            "explicit_alias_bridge_count": 2,
                            "best_official_url": None,
                            "converged_official_signal": False,
                        },
                    },
                }
            },
        )

        self.assertTrue(arbiter._has_curated_alias_contextual_work_anchor(ctx, title))
        self.assertFalse(arbiter._curated_alias_lacks_contextual_work_anchor(ctx, title))

        decision = arbiter.analyze(ctx)["final_decision"]

        self.assertTrue(decision["is_relevant"])
        self.assertEqual(decision["official_title"], title)
        self.assertNotIn(
            "curated_alias_missing_contextual_work_anchor",
            decision.get("_title_null_block_reasons", []),
        )

    def test_verified_alias_bridge_accepts_aksalsip_comment_work_cue(self):
        arbiter_module.KNOWN_TITLE_ABBREVIATIONS = {"악살싶": "악당은 살고 싶다"}
        title = "악당은 살고 싶다"
        response = _arbiter_response(title, discussion_type="review")
        response["final_decision"]["suspected_titles"] = [
            {
                "title": title,
                "confidence": "Max",
                "reason": "약칭과 말투/강의씬 댓글 맥락이 작품 전개와 결속됨",
            }
        ]
        arbiter = _arbiter(response)
        ctx = ConversationContext(
            post_id=11671500,
            post_data={
                "post_id": 11671500,
                "title": "말투 바뀌는 거 악살싶에서는 호평받았었는데",
                "content_blocks": [
                    {"type": "image", "url": "https://example.invalid/yoshinoya.jpg"},
                    {"type": "text", "text": "흠"},
                ],
            },
            comments=[
                "그때도 말투강제 자체는 막 만장일치 호평까진 아니엇음",
                "말투고정되고 ㅈ간지 강의씬(표절) 보여주니까 캬 하고 본거지",
            ],
        )
        ctx.search_results = [
            {
                "title": "악당은 살고 싶다 - 웹소설 - 카카오페이지",
                "url": "https://page.kakao.com/content/56807841",
                "content": "악당은 살고 싶다 작품 공식 상세",
                "_trust_score": 0.95,
            },
            {
                "title": "[악살싶]악당도 살고 싶다",
                "url": "https://novelpia.com/novel/355931",
                "content": "[악당은 살고 싶다]를 원작으로 언급하는 파생/패러디 표면",
                "_is_derivative": True,
            },
        ]
        ctx.suspected_titles = [
            {
                "title": title,
                "confidence": "High",
                "source_expert": "verifier",
            }
        ]
        ctx.add_evidence_for_candidate(
            title,
            "official_url",
            {"url": "https://page.kakao.com/content/56807841", "title": title},
        )
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "work_discussion",
                "detected_entities": {"possible_titles": ["악살싶"]},
                "context_clues": {"has_specific_names": True},
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "primary_domain": "novel_literature",
                    "intent": "discuss_work",
                    "title_novel_terms": ["악살싶"],
                }
            },
        )
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "overall_best_match": {"title": title, "confidence": "high"},
                "decoded_terms": [
                    {
                        "original": "악살싶",
                        "best_match": {"title": title, "confidence": "High"},
                        "grounding": {"anchor_type": "title_mention"},
                    }
                ],
            },
        )
        ctx.set_expert_output(
            ExpertType.VERIFIER,
            {
                "verification_result": {
                    "is_relevant": True,
                    "is_novel_discussion": True,
                    "novel_identity": {
                        "official_novel_title": title,
                        "heretic_url": "https://page.kakao.com/content/56807841",
                        "confidence": "High",
                    },
                    "grounding_check": {
                        "anchor_found": "title_mention",
                        "matched_alias": "악살싶",
                        "title_abbrev_mentioned": True,
                    },
                    "slang_insight": {
                        "detected_term": "악살싶",
                        "decoded_term": title,
                        "decode_verified": True,
                        "canonical_work_alias": "악살싶",
                    },
                    "relation_judgment": {
                        "relation_type": "explicit_alias",
                        "discussion_target": "specific_work",
                        "promotion_decision": "allow",
                        "confidence": "high",
                        "evidence_summary": {
                            "official_detail_count": 4,
                            "community_post_count": 0,
                            "explicit_alias_bridge_count": 1,
                        },
                        "search_support_summary": {
                            "official_exact_title_count": 4,
                            "community_alias_support_count": 3,
                            "explicit_alias_bridge_count": 1,
                            "support_channel_count": 2,
                        },
                    },
                }
            },
        )

        self.assertTrue(arbiter._verified_contextual_alias_work_bridge_context(ctx, title))
        self.assertTrue(arbiter._has_curated_alias_contextual_work_anchor(ctx, title))
        self.assertFalse(arbiter._curated_alias_lacks_contextual_work_anchor(ctx, title))

        decision = arbiter.analyze(ctx)["final_decision"]

        self.assertTrue(decision["is_relevant"])
        self.assertEqual(decision["official_title"], title)
        self.assertNotIn(
            "curated_alias_missing_contextual_work_anchor",
            decision.get("_title_null_block_reasons", []),
        )

    def test_prefix_only_known_title_abbreviation_does_not_force_arbiter_public_title(self):
        arbiter_module.KNOWN_TITLE_ABBREVIATIONS = {"아생갤": "아카데미 생존 갤러리"}
        arbiter = _arbiter(
            {
                "final_decision": {
                    "is_relevant": True,
                    "is_novel_discussion": True,
                    "official_title": "아카데미 생존 갤러리",
                    "official_novel_title": "아카데미 생존 갤러리",
                    "heretic_url": "https://novelpia.com/novel/380218",
                    "confidence": "High",
                    "discussion_type": "review",
                    "reason": "LLM seed decision",
                    "final_reasoning": "LLM seed decision",
                    "notes": "",
                    "suspected_titles": [
                        {
                            "title": "아카데미 생존 갤러리",
                            "confidence": "High",
                            "source_expert": "arbiter_llm",
                        }
                    ],
                },
                "metadata": {},
                "evidence_chain": [],
            }
        )
        ctx = ConversationContext(
            post_id=11694035,
            post_data={
                "post_id": 11694035,
                "title": "아생갤) 가장 무서웠던 순간이",
                "content_blocks": [
                    {"type": "text", "text": "폐허가 된 도심지라면"},
                    {"type": "text", "text": "지진이라도 난 거냐, 전쟁이라도 터진 거냐"},
                    {"type": "text", "text": "현생 서사가 대체 어떻게 되길래"},
                ],
            },
            comments=["얼탱ㅋㅋㅋㅋㅋ"],
        )
        ctx.search_results = [
            {
                "title": "아카데미 생존 갤러리",
                "url": "https://novelpia.com/novel/380218",
                "content": "아생갤 웹소설 공식 상세 페이지",
                "_trust_score": 0.95,
            }
        ]
        ctx.suspected_titles = [
            {
                "title": "아카데미 생존 갤러리",
                "confidence": "High",
                "source_expert": "verifier",
            }
        ]
        ctx.add_evidence_for_candidate(
            "아카데미 생존 갤러리",
            "official_url",
            {"url": "https://novelpia.com/novel/380218", "title": "아카데미 생존 갤러리"},
        )
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "work_discussion",
                "detected_entities": {"possible_titles": ["아생갤"]},
                "context_clues": {},
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "express_opinion",
                    "title_novel_terms": ["아생갤"],
                    "semantic_seed_review": {"is_specific_work_discussion": True},
                }
            },
        )
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "overall_confidence": "high",
                "decoded_terms": [
                    {
                        "original": "아생갤",
                        "best_match": {"title": "아카데미 생존 갤러리", "confidence": "High"},
                        "grounding": {"anchor_type": "title_mention"},
                    }
                ],
            },
        )
        ctx.set_expert_output(
            ExpertType.VERIFIER,
            {
                "verification_result": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_novel_title": "아카데미 생존 갤러리",
                        "confidence": "High",
                        "heretic_url": "https://novelpia.com/novel/380218",
                    },
                    "grounding_check": {
                        "anchor_found": "title_mention",
                        "matched_alias": "아생갤",
                        "title_abbrev_mentioned": True,
                    },
                }
            },
        )

        decision = arbiter.analyze(ctx)["final_decision"]

        self.assertTrue(decision["is_relevant"])
        self.assertIsNone(decision["official_title"])
        self.assertIsNone(decision["official_novel_title"])
        self.assertIn(
            "curated_alias_missing_contextual_work_anchor",
            decision.get("_title_null_block_reasons", []),
        )


class SlangDBWriteGuardTest(unittest.TestCase):
    @staticmethod
    def _result(
        post_id: int,
        official_title: str,
        alias: str,
        *,
        slang_insight: dict | None = None,
        consistency_flags: list[str] | None = None,
    ) -> dict:
        candidate = {
            "official_title": official_title,
            "alias_or_mention": alias,
            "confidence": "High",
            "source_tier": "official_detail",
        }
        return {
            "post_id": post_id,
            "title": f"post-{post_id}",
            "created_at": "2026-07-14 18:00:00",
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "discussion_type": "general",
                    "topicality": "core_relevant",
                    "subtype": "resolved_work",
                    "work_resolution": "resolved",
                    "anchor_type": "title_alias",
                    "anchor_strength": "high",
                    "reason": "official_title_evidence: true",
                    "novel_identity": {
                        "official_title": official_title,
                        "heretic_url": f"https://example.com/{post_id}",
                        "confidence": "High",
                    },
                    "primary_work": dict(candidate),
                    "title_candidates": [dict(candidate)],
                    "mentioned_works": [],
                    "secondary_reference_works": [],
                    "slang_insight": slang_insight or {},
                    "consistency_flags": consistency_flags or [],
                    "entity_mentions": [],
                },
                "analysis": {},
            },
        }

    def test_high_confidence_unaligned_surfaces_do_not_enter_slang_db(self):
        cases = (
            (11713219, "옥수수", "지력"),
            (11716500, "조선에서 태종이 나를 픽함", "네이버"),
            (11713185, "[메이플스토리] 두 명의 대적자", "보내"),
            (11711592, "[프문]부족한 예술일수록 더욱 아름답게 피어나리라", "세상"),
            (11710055, "호랑이 새끼", "있었"),
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "slang_db.json"
            manager = SlangDBManager(path=path, run_id="guard-negative", enabled=True, flush_posts=20)
            for post_id, official_title, alias in cases:
                manager.record_result(self._result(post_id, official_title, alias))
            manager.finalize()
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["titles"], {})
        self.assertEqual(payload["family_aliases"], {})

    def test_store_false_blocks_surface_and_reference_bypass_but_preserves_independently_verified_alias(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "slang_db.json"
            manager = SlangDBManager(path=path, run_id="guard-veto", enabled=True, flush_posts=10)
            result = self._result(
                11718101,
                "망겜의 성기사",
                "망겜성",
                slang_insight={
                    "detected_term": "망겜성후기",
                    "decoded_term": "망겜의 성기사 + 후기",
                    "decode_verified": True,
                    "canonical_work_alias": "망겜성",
                    "alias_scope": "work_plus_other",
                    "store_in_slang_db": False,
                    "store_reason": "non_pure_work_alias",
                },
                consistency_flags=[
                    "confirmed_alias:망겜성",
                    "verified_alias_official_detail_anchor",
                ],
            )
            identity = result["analysis_result"]["identity"]
            identity["mentioned_works"] = [
                {
                    "official_title": "망겜성 외전",
                    "alias_or_mention": "망겜성",
                    "confidence": "High",
                    "source_tier": "official_detail",
                }
            ]
            identity["secondary_reference_works"] = [
                {
                    "official_title": "망겜성 단편",
                    "alias_or_mention": "망겜성",
                    "confidence": "High",
                    "source_tier": "official_detail",
                }
            ]
            manager.record_result(result)
            manager.finalize()
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(set(payload["titles"]), {"망겜의 성기사"})
        bucket = payload["titles"]["망겜의 성기사"]
        self.assertEqual([entry["term"] for entry in bucket["slang"]], ["망겜성"])
        self.assertNotIn("망겜성후기", [entry["term"] for entry in bucket["slang"]])
        self.assertEqual(bucket["conflicts"], [])

    def test_incomplete_or_inconsistent_store_true_contract_is_fail_closed(self):
        cases = (
            self._result(
                11,
                "괴담 호텔 탈출기",
                "연참",
                slang_insight={
                    "detected_term": "연참",
                    "decoded_term": "괴담 호텔 탈출기",
                    "decode_verified": True,
                    "canonical_work_alias": "쿠크루",
                    "alias_scope": "pure_work_alias",
                    "store_in_slang_db": True,
                    "store_reason": "pure_work_alias",
                },
            ),
            self._result(
                12,
                "옥수수",
                "지력",
                slang_insight={
                    "detected_term": "지력",
                    "decoded_term": "옥수수",
                    "decode_verified": True,
                    "canonical_work_alias": "지력",
                    "alias_scope": "pure_work_alias",
                    "store_in_slang_db": True,
                    "store_reason": "model_asserted",
                },
            ),
            self._result(
                13,
                "조선에서 태종이 나를 픽함",
                "네이버",
                slang_insight={
                    "detected_term": "네이버",
                    "decoded_term": "조선에서 태종이 나를 픽함",
                    "canonical_work_alias": "네이버",
                    "alias_scope": "pure_work_alias",
                    "store_in_slang_db": True,
                    "store_reason": "pure_work_alias",
                },
            ),
            self._result(
                14,
                "아카데미 생존 갤러리",
                "아생갤",
                slang_insight={
                    "detected_term": "아생갤",
                    "decoded_term": "전혀 다른 작품",
                    "decode_verified": True,
                    "canonical_work_alias": "아생갤",
                    "alias_scope": "pure_work_alias",
                    "store_in_slang_db": True,
                    "store_reason": "pure_work_alias",
                },
            ),
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "slang_db.json"
            manager = SlangDBManager(path=path, run_id="guard-incomplete", enabled=True, flush_posts=10)
            for result in cases:
                manager.record_result(result)
            manager.finalize()
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["titles"], {})

    def test_structural_similarity_without_pair_proof_is_not_collectable(self):
        cases = (
            (11716464, "페이 포인트", "페이트"),
            (11718079, "로판 속 주인공이 나만 좋아함", "로판이나"),
            (11716462, "니들 생각 다 들린다", "니생"),
            (11711608, "정의실현부 전략병기분대 부분대장입니다", "부분부분"),
            (11710067, "유니콘이 안심하고 먹을수 있는 노벨피아 사료들 ver 1.1", "유니콘들"),
            (11714907, "아카데미 생존 갤러리", "아생갤"),
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "slang_db.json"
            manager = SlangDBManager(path=path, run_id="guard-structural-only", enabled=True, flush_posts=20)
            for post_id, official_title, alias in cases:
                manager.record_result(self._result(post_id, official_title, alias))
            manager.finalize()
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["titles"], {})
        self.assertEqual(payload["family_aliases"], {})

    def test_reference_roles_do_not_mutate_slang_db_without_pair_proof(self):
        result = self._result(11718079, "기준 작품", "기준약칭")
        identity = result["analysis_result"]["identity"]
        identity["novel_identity"] = {"official_title": None, "heretic_url": None}
        identity["primary_work"] = None
        identity["title_candidates"] = []
        identity["recommendation_candidates"] = [
            {
                "official_title": "로판 속 주인공이 나만 좋아함",
                "alias_or_mention": "로판이나",
                "confidence": "High",
                "source_tier": "official_detail",
            }
        ]
        identity["mentioned_works"] = [
            {
                "official_title": "니들 생각 다 들린다",
                "alias_or_mention": "니생",
                "confidence": "High",
                "source_tier": "official_detail",
            }
        ]
        identity["secondary_reference_works"] = [
            {
                "official_title": "정의실현부 전략병기분대 부분대장입니다",
                "alias_or_mention": "부분부분",
                "confidence": "High",
                "source_tier": "official_detail",
            }
        ]
        identity["comparison_target"] = [
            {
                "official_title": "유니콘이 안심하고 먹을수 있는 노벨피아 사료들 ver 1.1",
                "alias_or_mention": "유니콘들",
                "confidence": "High",
                "source_tier": "official_detail",
            }
        ]

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "slang_db.json"
            manager = SlangDBManager(path=path, run_id="guard-reference-only", enabled=True, flush_posts=10)
            manager.record_result(result)
            manager.finalize()
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["titles"], {})

    def test_fully_verified_alias_pairs_remain_collectable(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "slang_db.json"
            manager = SlangDBManager(path=path, run_id="guard-positive", enabled=True, flush_posts=10)
            manager.record_result(
                self._result(
                    1,
                    "아카데미 생존 갤러리",
                    "아생갤",
                    consistency_flags=[
                        "confirmed_alias:아생갤",
                        "verified_alias_official_detail_anchor",
                    ],
                )
            )
            manager.record_result(
                self._result(
                    2,
                    "괴담 호텔 탈출기",
                    "쿠크루",
                    slang_insight={
                        "detected_term": "쿠크루",
                        "decoded_term": "괴담 호텔 탈출기",
                        "decode_verified": True,
                        "canonical_work_alias": "쿠크루",
                        "alias_scope": "pure_work_alias",
                        "store_in_slang_db": True,
                        "store_reason": "pure_work_alias",
                    },
                )
            )
            manager.record_result(
                self._result(
                    3,
                    "비구조 별칭 작품",
                    "별칭코드",
                    consistency_flags=[
                        "confirmed_alias:별칭코드",
                        "verified_alias_official_detail_anchor",
                    ],
                )
            )
            registry_result = self._result(4, "주무시기 전에 무엇을 하셨나요?", "주전무")
            registry_result["analysis_result"]["identity"]["novel_identity"]["alias_resolution_sources"] = [
                {
                    "alias": "주전무",
                    "canonical_title": "주무시기 전에 무엇을 하셨나요?",
                    "alias_resolution_source": "known_abbreviation",
                    "source_registry": "KNOWN_ABBREVIATIONS",
                }
            ]
            manager.record_result(registry_result)
            known_title_result = self._result(5, "아카데미 생존 갤러리", "아생갤")
            known_title_result["analysis_result"]["identity"]["novel_identity"]["alias_resolution_sources"] = [
                {
                    "alias": "아생갤",
                    "canonical_title": "아카데미 생존 갤러리",
                    "alias_resolution_source": "known_title_abbreviation",
                    "source_registry": "KNOWN_TITLE_ABBREVIATIONS",
                }
            ]
            manager.record_result(known_title_result)
            slang_dictionary_result = self._result(6, "로판 속 주인공이 나만 좋아함", "로나좋")
            slang_dictionary_result["analysis_result"]["identity"]["novel_identity"]["alias_resolution_sources"] = [
                {
                    "alias": "로나좋",
                    "canonical_title": "로판 속 주인공이 나만 좋아함",
                    "alias_resolution_source": "slang_dictionary",
                    "source_registry": "SLANG_DICTIONARY",
                }
            ]
            manager.record_result(slang_dictionary_result)
            manager.finalize()
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["titles"]["아카데미 생존 갤러리"]["slang"][0]["term"], "아생갤")
        self.assertEqual(payload["titles"]["괴담 호텔 탈출기"]["slang"][0]["term"], "쿠크루")
        self.assertEqual(payload["titles"]["비구조 별칭 작품"]["slang"][0]["term"], "별칭코드")
        self.assertEqual(payload["titles"]["주무시기 전에 무엇을 하셨나요?"]["slang"][0]["term"], "주전무")
        self.assertEqual(payload["titles"]["로판 속 주인공이 나만 좋아함"]["slang"][0]["term"], "로나좋")

    def test_registry_provenance_requires_exact_enum_tuple_and_real_mapping(self):
        cases = (
            (
                21,
                "주무시기 전에 무엇을 하셨나요?",
                "주전무",
                "known_abbreviation",
                "SLANG_DICTIONARY",
            ),
            (
                22,
                "임의 작품",
                "임의약칭",
                "known_abbreviation",
                "KNOWN_ABBREVIATIONS",
            ),
            (
                23,
                "다른 작품",
                "주전무",
                "known_abbreviation",
                "KNOWN_ABBREVIATIONS",
            ),
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "slang_db.json"
            manager = SlangDBManager(path=path, run_id="guard-registry-spoof", enabled=True, flush_posts=20)
            for post_id, title, alias, resolution_source, registry in cases:
                result = self._result(post_id, title, alias)
                result["analysis_result"]["identity"]["novel_identity"]["alias_resolution_sources"] = [
                    {
                        "alias": alias,
                        "canonical_title": title,
                        "alias_resolution_source": resolution_source,
                        "source_registry": registry,
                    }
                ]
                manager.record_result(result)
            manager.finalize()
            payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"titles": {}}

        self.assertEqual(payload["titles"], {})

    def test_non_boolean_store_values_are_fail_closed(self):
        malformed_values = ("false", "true", 0, 1, [], {})
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "slang_db.json"
            manager = SlangDBManager(path=path, run_id="guard-store-type", enabled=True, flush_posts=20)
            for post_id, raw_store in enumerate(malformed_values, start=31):
                manager.record_result(
                    self._result(
                        post_id,
                        "아카데미 생존 갤러리",
                        "아생갤",
                        slang_insight={
                            "detected_term": "아생갤",
                            "decoded_term": "아카데미 생존 갤러리",
                            "decode_verified": True,
                            "canonical_work_alias": "아생갤",
                            "alias_scope": "pure_work_alias",
                            "store_in_slang_db": raw_store,
                            "store_reason": "pure_work_alias",
                        },
                        consistency_flags=[
                            "confirmed_alias:아생갤",
                            "verified_alias_official_detail_anchor",
                        ],
                    )
                )
            manager.finalize()
            payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"titles": {}}

        self.assertEqual(payload["titles"], {})

    def test_persisted_unaligned_alias_cannot_seed_without_verified_contract(self):
        unsafe_entry = {"term": "지력", "sources": ["primary_work", "title_candidate"]}
        unsafe_bucket = {
            "examples": [
                {
                    "official_title": "옥수수",
                    "alias": "지력",
                    "source_roles": ["primary_work", "title_candidate"],
                }
            ]
        }
        self.assertFalse(slang_db_alias_seed_is_safe("옥수수", unsafe_entry, unsafe_bucket))

        structural_entry = {"term": "아생갤", "sources": ["primary_work", "title_candidate"]}
        self.assertFalse(slang_db_alias_seed_is_safe("아카데미 생존 갤러리", structural_entry, {"examples": []}))

        verified_entry = {"term": "쿠크루", "sources": ["slang_insight", "primary_work"]}
        verified_bucket = {
            "examples": [
                {
                    "official_title": "괴담 호텔 탈출기",
                    "alias": "쿠크루",
                    "slang_detected_term": "쿠크루",
                    "slang_decoded_term": "괴담 호텔 탈출기",
                    "slang_decode_verified": True,
                    "slang_canonical_alias": "쿠크루",
                    "slang_alias_scope": "pure_work_alias",
                    "slang_store_in_db": True,
                    "slang_store_reason": "pure_work_alias",
                }
            ]
        }
        self.assertTrue(slang_db_alias_seed_is_safe("괴담 호텔 탈출기", verified_entry, verified_bucket))

        punctuated_entry = {"term": "K-문제", "sources": ["primary_work", "title_candidate"]}
        punctuated_bucket = {
            "examples": [
                {
                    "official_title": "비구조 별칭 작품",
                    "alias": "K-문제",
                    "consistency_flags": [
                        "confirmed_alias:K-문제",
                        "verified_alias_official_detail_anchor",
                    ],
                }
            ]
        }
        self.assertTrue(
            slang_db_alias_seed_is_safe("비구조 별칭 작품", punctuated_entry, punctuated_bucket)
        )

        malformed_bucket = {
            "examples": [
                {
                    "official_title": "비구조 별칭 작품",
                    "alias": "K-문제",
                    "consistency_flags": 1,
                }
            ]
        }
        self.assertFalse(
            slang_db_alias_seed_is_safe("비구조 별칭 작품", punctuated_entry, malformed_bucket)
        )

        valid_registry_entry = {"term": "주전무", "sources": ["primary_work"]}
        valid_registry_bucket = {
            "examples": [
                {
                    "official_title": "주무시기 전에 무엇을 하셨나요?",
                    "alias": "주전무",
                    "source_roles": ["primary_work"],
                    "alias_resolution_sources": [
                        {
                            "alias": "주전무",
                            "canonical_title": "주무시기 전에 무엇을 하셨나요?",
                            "alias_resolution_source": "known_abbreviation",
                            "source_registry": "KNOWN_ABBREVIATIONS",
                        }
                    ],
                }
            ]
        }
        self.assertTrue(
            slang_db_alias_seed_is_safe(
                "주무시기 전에 무엇을 하셨나요?",
                valid_registry_entry,
                valid_registry_bucket,
            )
        )

        registry_entry = {"term": "주전무", "sources": ["secondary_reference"]}
        reference_only_registry_bucket = {
            "examples": [
                {
                    "official_title": "주무시기 전에 무엇을 하셨나요?",
                    "alias": "주전무",
                    "source_roles": ["secondary_reference"],
                    "alias_resolution_sources": [
                        {
                            "alias": "주전무",
                            "canonical_title": "주무시기 전에 무엇을 하셨나요?",
                            "alias_resolution_source": "known_abbreviation",
                            "source_registry": "KNOWN_ABBREVIATIONS",
                        }
                    ],
                }
            ]
        }
        self.assertFalse(
            slang_db_alias_seed_is_safe(
                "주무시기 전에 무엇을 하셨나요?",
                registry_entry,
                reference_only_registry_bucket,
            )
        )

        invalid_true_registry_bucket = {
            "examples": [
                {
                    "official_title": "주무시기 전에 무엇을 하셨나요?",
                    "alias": "주전무",
                    "source_roles": ["primary_work"],
                    "slang_store_in_db": True,
                    "slang_decode_verified": False,
                    "slang_detected_term": "주전무",
                    "slang_decoded_term": "주무시기 전에 무엇을 하셨나요?",
                    "slang_canonical_alias": "주전무",
                    "slang_alias_scope": "pure_work_alias",
                    "slang_store_reason": "pure_work_alias",
                    "alias_resolution_sources": [
                        {
                            "alias": "주전무",
                            "canonical_title": "주무시기 전에 무엇을 하셨나요?",
                            "alias_resolution_source": "known_abbreviation",
                            "source_registry": "KNOWN_ABBREVIATIONS",
                        }
                    ],
                }
            ]
        }
        self.assertFalse(
            slang_db_alias_seed_is_safe(
                "주무시기 전에 무엇을 하셨나요?",
                {"term": "주전무", "sources": ["primary_work"]},
                invalid_true_registry_bucket,
            )
        )


if __name__ == "__main__":
    unittest.main()
