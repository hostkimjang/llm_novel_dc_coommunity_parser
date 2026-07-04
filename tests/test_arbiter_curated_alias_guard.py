from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import llm_batch.experts.arbiter as arbiter_module  # noqa: E402
from llm_batch.experts.arbiter import ArbiterExpert  # noqa: E402
from llm_batch.experts.deliberation import DeliberationOrchestrator  # noqa: E402
from llm_batch.experts.orchestrator import ConversationContext, ExpertType  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
