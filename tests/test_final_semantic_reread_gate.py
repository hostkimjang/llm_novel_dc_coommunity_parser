from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_batch.agentic_pipeline import AgenticPipeline  # noqa: E402
from llm_batch.experts.discourse import DiscourseAnalyzer  # noqa: E402
from llm_batch.experts.orchestrator import ConversationContext, ExpertType, Orchestrator  # noqa: E402
from llm_batch.domain.models import DetectedTitle  # noqa: E402


class DummyMCP:
    pass


class FakeFinalSemanticRereadLLM:
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    def _stream_chat_http(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})
        return self.response


class FinalSemanticRereadGateTest(unittest.TestCase):
    def test_intent_permit_blocks_title_alias_search_after_semantic_seed_denial(self):
        calls = []

        def fake_search(query, purpose="search"):
            calls.append((query, purpose))
            return [{"title": "hit", "url": f"https://example.test/{len(calls)}", "content": "검색 결과"}]

        orchestrator = Orchestrator(experts={}, search_fn=fake_search)
        ctx = ConversationContext(
            post_id=11718080,
            post_data={
                "post_id": 11718080,
                "title": "소설 보는 친구 있으면 좋겠다",
                "content_blocks": [{"type": "text", "text": "밥 먹는데 같이 소설 볼 친구 있었으면 하는 한탄"}],
            },
            comments=[],
        )
        ctx.discourse_warning = "semantic_seed_review(no_work_anchor)"
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "community_banter",
                "detected_entities": {"possible_titles": ["친구"]},
                "key_terms": ["친구"],
                "context_clues": {},
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "community_banter",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )

        orchestrator._execute_searches(
            [
                {"query": "친구 웹소설", "purpose": "official_title_verify", "priority": 0},
                {"query": "친구", "purpose": "alias_raw_probe", "priority": 0},
                {"query": "친구 카카오페이지", "purpose": "platform_title_search", "priority": 0},
                {"query": "친구 추천", "purpose": "auto_search_seed", "priority": 0},
                {"query": "친구 작품", "purpose": "key_term_supplement", "priority": 0},
                {"query": "친구 정식명칭", "purpose": "known_abbr_fullname_search", "priority": 0},
                {"query": "친구 검증", "purpose": "verification_search", "priority": 0},
                {"query": "친구 웹소설 후보", "purpose": "unresolved_term_novel", "priority": 0},
                {"query": "친구 리콜", "purpose": "decoder_recall_verification", "priority": 0},
                {"query": "친구 정식 제목", "purpose": "ambiguous_title_track", "priority": 0},
                {"query": "친구 캐릭터", "purpose": "title_character_verification", "priority": 0},
                {"query": "친구 자동 검증", "purpose": "auto_verification", "priority": 0},
                {"query": "친구 플랫폼 검증", "purpose": "auto_platform_verification", "priority": 0},
                {"query": "친구 site:namu.wiki 웹소설", "purpose": "adaptive_wiki", "priority": 0},
                {"query": "친구 작가 웹소설", "purpose": "adaptive_author", "priority": 0},
                {"query": "친구 작가", "purpose": "author_works_search", "priority": 0},
                {"query": "친구 역검색", "purpose": "character_event_reverse_track", "priority": 0},
                {"query": "친구 반증 제목", "purpose": "counter_evidence_title_track", "priority": 0},
                {"query": "친구 뜻", "purpose": "term_definition", "priority": 1},
            ],
            post_id=11718080,
            ctx=ctx,
        )

        self.assertEqual(calls, [("친구 뜻", "term_definition")])
        self.assertIn("intent_permit_blocked_total", ctx.search_query_stats)
        self.assertGreaterEqual(ctx.search_query_stats["intent_permit_blocked_total"], 8)
        self.assertTrue(
            any("intent_permit_for_title_search=false" in item for item in ctx.uncertainty_sources)
        )

    def test_intent_permit_keeps_contextual_alias_bridge_under_semantic_seed_denial(self):
        orchestrator = Orchestrator(experts={}, search_fn=lambda *_args, **_kwargs: [])
        ctx = ConversationContext(
            post_id=11694019,
            post_data={
                "post_id": 11694019,
                "title": "미츄리 혼후순결에서 하인들에게도 멸시당한게 고증에 맞는거였구나",
                "content_blocks": [
                    {
                        "type": "text",
                        "text": "아내가 혼후순결 요구해서 섹스 안하니까 하인들도 멸시함",
                    }
                ],
            },
            comments=[],
        )
        ctx.discourse_warning = "semantic_seed_review(no_work_anchor)"
        gatekeeper = {
            "post_type": "community_banter",
            "detected_entities": {"possible_titles": ["미츄리"], "key_terms": ["혼후순결", "중세 문화", "고증"]},
            "context_clues": {},
        }
        ctx.set_expert_output(ExpertType.GATEKEEPER, gatekeeper)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "community_banter",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "semantic_seed_review_context_terms": ["혼후순결", "중세 문화", "고증"],
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )

        kept = orchestrator._prune_title_search_requests_for_intent_permit(
            ctx,
            [
                {"query": "미츄리 혼후순결 웹소설", "purpose": "alias_bridge_search", "priority": 0},
                {"query": "미츄리 중세 문화 웹소설", "purpose": "alias_bridge_search", "priority": 0},
                {"query": "친구 웹소설", "purpose": "alias_bridge_search", "priority": 0},
                {"query": "혼후순결 뜻", "purpose": "term_definition", "priority": 1},
            ],
            gatekeeper_result=gatekeeper,
            phase="unit",
        )

        self.assertEqual(
            [item["query"] for item in kept],
            ["미츄리 혼후순결 웹소설", "혼후순결 뜻"],
        )
        self.assertEqual(ctx.search_query_stats["intent_permit_blocked_total"], 2)

    def test_intent_permit_denies_unknown_purpose_by_default_after_semantic_seed_denial(self):
        orchestrator = Orchestrator(experts={}, search_fn=lambda *_args, **_kwargs: [])
        ctx = ConversationContext(
            post_id=11718080,
            post_data={
                "post_id": 11718080,
                "title": "소설 보는 친구 있으면 좋겠다",
                "content_blocks": [{"type": "text", "text": "같이 소설 볼 친구 있었으면 하는 한탄"}],
            },
            comments=[],
        )
        ctx.discourse_warning = "semantic_seed_review(no_work_anchor)"
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )

        kept = orchestrator._prune_title_search_requests_for_intent_permit(
            ctx,
            [
                {"query": "친구 미래 title probe", "purpose": "future_title_probe"},
                {"query": "친구 뜻", "purpose": "term_definition"},
            ],
            phase="unit",
        )

        self.assertEqual(kept, [{"query": "친구 뜻", "purpose": "term_definition"}])
        self.assertEqual(ctx.search_query_stats["intent_permit_blocked_total"], 1)

    def test_intent_permit_keeps_character_cluster_official_probe_under_seed_denial(self):
        orchestrator = Orchestrator(experts={}, search_fn=lambda *_args, **_kwargs: [])
        ctx = ConversationContext(
            post_id=11702072,
            post_data={
                "post_id": 11702072,
                "title": "호텔 캐릭터 얘기",
                "content_blocks": [{"type": "text", "text": "한가인 차진철 은솔 얘기"}],
            },
            comments=[],
        )
        ctx.discourse_warning = "semantic_seed_review(no_work_anchor)"
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        gatekeeper = {
            "detected_entities": {"possible_characters": ["한가인", "차진철", "은솔"]},
            "context_clues": {},
        }

        kept = orchestrator._prune_title_search_requests_for_intent_permit(
            ctx,
            [
                {"query": "한가인 차진철 웹소설 노벨피아", "purpose": "title_character_verification"},
                {"query": "호텔 웹소설", "purpose": "official_title_verify"},
                {"query": "한가인 뜻", "purpose": "term_definition"},
            ],
            gatekeeper_result=gatekeeper,
            phase="unit",
        )

        self.assertEqual(
            [item["query"] for item in kept],
            ["한가인 차진철 웹소설 노벨피아", "한가인 뜻"],
        )

    def test_low_specific_guard_keeps_character_setting_continuation_bridge(self):
        orchestrator = Orchestrator(experts={}, search_fn=lambda *_args, **_kwargs: [])
        ctx = ConversationContext(
            post_id=11702090,
            post_data={
                "post_id": 11702090,
                "title": "애초에 한가인이 아리한테 부등변 준 이유가",
                "content_blocks": [
                    {
                        "type": "text",
                        "text": "아직 깨달음 부족할때 정신 와리가리 하니까 자기 브레이크 걸어달라고 준건데",
                    },
                    {
                        "type": "text",
                        "text": "누구한테 준건진 뭐 의미없지 상현쌤 줬어도 제대로 못썼다고 하니까",
                    },
                ],
            },
            comments=["아리는 브레이크 걸기에는 너무 약해"],
        )
        gatekeeper = {
            "is_noise": False,
            "post_type": "work_discussion",
            "detected_entities": {
                "possible_titles": ["한가인", "아리"],
                "possible_characters": ["한가인", "아리"],
            },
            "key_terms": ["한가인", "아리", "부등변", "상현쌤"],
            "context_clues": {
                "title_as_body_continuation": True,
                "has_specific_names": True,
            },
            "search_requests": [
                {
                    "query": "한가인 아리 부등변 웹소설",
                    "purpose": "official_title_verify",
                    "priority": 1,
                }
            ],
        }

        guarded = orchestrator._apply_gatekeeper_low_specific_guard(ctx, gatekeeper)

        self.assertFalse(guarded["is_noise"])
        self.assertEqual(guarded["post_type"], "work_discussion")
        self.assertEqual(
            guarded["search_requests"],
            [
                {
                    "query": "한가인 아리 부등변 웹소설",
                    "purpose": "official_title_verify",
                    "priority": 1,
                }
            ],
        )
        self.assertTrue(
            orchestrator._has_character_setting_continuation_bridge(ctx, gatekeeper)
        )

    def test_intent_permit_keeps_converged_title_official_probe_under_seed_denial(self):
        orchestrator = Orchestrator(experts={}, search_fn=lambda *_args, **_kwargs: [])
        ctx = ConversationContext(
            post_id=11702087,
            post_data={
                "post_id": 11702087,
                "title": "그래서 아리는 소원으로 받은 유산이 뭐임?",
                "content_blocks": [{"type": "text", "text": "부등변은 가인이가 준거자너"}],
            },
            comments=["팀원과 남친"],
        )
        ctx.discourse_warning = "semantic_seed_review(no_work_anchor)"
        ctx.llm_snippet_analysis = {"identified_title": "괴담 호텔 탈출기"}
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "primary_domain": "novel_literature",
                    "domain_confidence": "high",
                    "intent": "ask_question",
                    "target_kind": "work",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        gatekeeper = {
            "post_type": "work_discussion",
            "detected_entities": {"possible_characters": ["아리", "가인"]},
            "context_clues": {},
        }

        kept = orchestrator._prune_title_search_requests_for_intent_permit(
            ctx,
            [
                {
                    "query": "괴담 호텔 탈출기 site:novelpia.com OR site:munpia.com",
                    "purpose": "official_title_verify",
                },
                {"query": "부등변 뜻 웹소설 설정", "purpose": "official_title_verify"},
            ],
            gatekeeper_result=gatekeeper,
            phase="unit",
        )

        self.assertEqual(
            [item["query"] for item in kept],
            ["괴담 호텔 탈출기 site:novelpia.com OR site:munpia.com"],
        )

    def test_intent_permit_blocks_comment_preservation_platform_probe_under_seed_denial(self):
        orchestrator = Orchestrator(experts={}, search_fn=lambda *_args, **_kwargs: [])
        ctx = ConversationContext(
            post_id=11702087,
            post_data={
                "post_id": 11702087,
                "title": "그래서 아리는 소원으로 받은 유산이 뭐임?",
                "content_blocks": [{"type": "text", "text": "부등변은 가인이가 준거자너"}],
            },
            comments=["소원에 유산 관련이 없었자너", "팀원과 남친"],
        )
        ctx.discourse_warning = "semantic_seed_review(no_work_anchor)"
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "primary_domain": "novel_literature",
                    "domain_confidence": "high",
                    "intent": "ask_question",
                    "target_kind": "work",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        gatekeeper = {
            "post_type": "work_discussion",
            "detected_entities": {"possible_characters": ["아리", "가인"]},
            "context_clues": {
                "comment_title_candidates": ["팀원과 남친"],
                "comment_title_candidate_details": [
                    {"text": "팀원과 남친", "speech_act": "unknown", "has_at_mention": False}
                ],
            },
        }

        kept = orchestrator._prune_title_search_requests_for_intent_permit(
            ctx,
            [
                {"query": "팀원과남친 웹소설 노벨피아", "purpose": "platform_title_search"},
                {"query": "아리 뜻", "purpose": "term_definition"},
            ],
            gatekeeper_result=gatekeeper,
            phase="unit",
        )

        self.assertEqual([item["query"] for item in kept], ["아리 뜻"])

    def test_intent_permit_allows_title_search_with_direct_image_work_anchor(self):
        calls = []

        def fake_search(query, purpose="search"):
            calls.append((query, purpose))
            return [{"title": "재벌가 차녀의 2회차 걸그룹", "url": "https://example.test/work", "content": "작품 상세"}]

        orchestrator = Orchestrator(experts={}, search_fn=fake_search)
        ctx = ConversationContext(
            post_id=11718082,
            post_data={
                "post_id": 11718082,
                "title": "두렵구나",
                "content_blocks": [{"type": "image", "url": "https://dcimg.example/a.jpg"}],
                "image_enrichment": [
                    {
                        "explicit_work_title": "재벌가 차녀의 2회차 걸그룹",
                        "explicit_author_name": "유은우",
                        "title_role": "work_title",
                        "evidence_type": "explicit_text",
                        "promotion_eligible": True,
                        "screen_type": "work_surface",
                        "surface_type": "episode_reader_page",
                        "ocr_text": "재벌가 차녀의 2회차 걸그룹 267화 카카오페이지",
                    }
                ],
            },
            comments=[],
        )
        ctx.discourse_warning = "semantic_seed_review(no_work_anchor)"
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "community_banter",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )

        orchestrator._execute_searches(
            [
                {
                    "query": "재벌가 차녀의 2회차 걸그룹 카카오페이지",
                    "purpose": "official_title_verify",
                    "priority": 0,
                }
            ],
            post_id=11718082,
            ctx=ctx,
        )

        self.assertEqual(
            calls,
            [("재벌가 차녀의 2회차 걸그룹 카카오페이지", "official_title_verify")],
        )
        self.assertNotIn("intent_permit_blocked_total", ctx.search_query_stats)
        with patch("llm_batch.experts.orchestrator.unresolved_ocr_alias_conflict_authority_blocked", return_value=True):
            self.assertEqual(orchestrator._protected_promotable_image_anchor_norms(ctx), (set(), set()))

    def test_unpromoted_direct_image_work_title_stays_diagnostic(self):
        for promotion in (None, False):
            with self.subTest(promotion=promotion):
                calls = []
                image = {
                    "explicit_work_title": "재벌가 차녀의 2회차 걸그룹",
                    "explicit_author_name": "유은우",
                    "title_role": "work_title",
                    "evidence_type": "explicit_text",
                    "screen_type": "work_surface",
                    "surface_type": "episode_reader_page",
                    "ocr_text": "재벌가 차녀의 2회차 걸그룹 267화 카카오페이지",
                }
                if promotion is not None:
                    image["promotion_eligible"] = promotion
                ctx = ConversationContext(
                    post_id=11718082,
                    post_data={"post_id": 11718082, "title": "두렵구나", "image_enrichment": [image]},
                    comments=[],
                )
                ctx.discourse_warning = "semantic_seed_review(no_work_anchor)"
                ctx.set_expert_output(ExpertType.DISCOURSE, {"discourse_analysis": {
                    "intent": "community_banter",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }})
                orchestrator = Orchestrator(
                    experts={}, search_fn=lambda query, purpose="search": calls.append((query, purpose)) or []
                )
                self.assertEqual(orchestrator._protected_promotable_image_anchor_norms(ctx), (set(), set()))
                orchestrator._execute_searches(
                    [{"query": "재벌가 차녀의 2회차 걸그룹 카카오페이지",
                      "purpose": "official_title_verify", "priority": 0}],
                    post_id=11718082, ctx=ctx,
                )
                self.assertEqual(calls, [
                    ("재벌가 차녀의 2회차 걸그룹 카카오페이지", "image_ocr_diagnostic_probe")
                ])
                with patch.object(orchestrator, "_title_search_intent_permit", return_value=(False, "no_work_anchor")):
                    self.assertEqual(orchestrator._prune_title_search_requests_for_intent_permit(ctx, [{
                        "query": "재벌가 차녀의 2회차 걸그룹 남캐일러 카카오페이지",
                        "purpose": "image_ocr_diagnostic_probe", "_ocr_diagnostic_only": True,
                    }]), [])

    def test_eligible_image_without_typed_title_or_evidence_cannot_seed_search(self):
        orchestrator = Orchestrator(experts={})
        image = {
            "explicit_work_title": "재벌가 차녀의 2회차 걸그룹",
            "explicit_author_name": "유은우",
            "promotion_eligible": True,
            "title_role": "work_title",
            "evidence_type": "explicit_text",
            "screen_type": "work_surface",
            "surface_type": "episode_reader_page",
            "ocr_text": "재벌가 차녀의 2회차 걸그룹 267화 카카오페이지",
        }
        request = {"query": "재벌가 차녀의 2회차 걸그룹 카카오페이지",
                   "purpose": "official_title_verify", "priority": 0}
        for missing_key in ("title_role", "evidence_type"):
            with self.subTest(missing_key=missing_key):
                incomplete = dict(image)
                incomplete.pop(missing_key)
                ctx = ConversationContext(
                    post_id=11718082,
                    post_data={"title": "두렵구나", "image_enrichment": [incomplete]},
                    comments=[],
                )
                self.assertEqual(orchestrator._protected_promotable_image_anchor_norms(ctx), (set(), set()))
                pruned = orchestrator._prune_image_only_title_seed_search_requests(ctx, [request])
                self.assertEqual(pruned, [])

    def test_query_poison_keeps_direct_ocr_work_cue_official_probe(self):
        calls = []

        def fake_search(query, purpose="search"):
            calls.append((query, purpose))
            return [{"title": "hit", "url": "https://example.test/work", "content": "작품 상세"}]

        orchestrator = Orchestrator(experts={}, search_fn=fake_search)
        ctx = ConversationContext(
            post_id=11677913,
            post_data={
                "post_id": 11677913,
                "title": "남캐일러 뽑아도 된다고",
                "content_blocks": [{"type": "image", "url": "https://dcimg.example/a.jpg"}],
                "surface_paraphrase_notes": [
                    {
                        "source_surface": "남캐일러",
                        "role": "non_title_semantic_context",
                    }
                ],
                "image_enrichment": [
                    {
                        "explicit_work_title": "천마",
                        "title_role": "unknown",
                        "evidence_type": "explicit_text",
                        "promotion_eligible": False,
                        "ocr_text": "천마 김캇트 이세계 검은머리 외국인",
                        "work_cues": ["천마", "김캇트", "이세계 검은머리 외국인"],
                    }
                ],
            },
            comments=[],
        )
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "image_post",
                "detected_entities": {
                    "possible_titles": ["천마", "이세계 검은머리 외국인"],
                    "possible_characters": ["김캇트"],
                },
                "key_terms": ["남캐일러", "천마", "김캇트"],
                "context_clues": {},
            },
        )
        ctx.discourse_warning = "semantic_seed_review(no_work_anchor)"
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "community_banter",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )

        diagnostic_results = orchestrator._execute_searches(
            [
                {
                    "query": "이세계 검은머리 외국인 웹소설 노벨피아",
                    "purpose": "official_title_verify",
                    "priority": 0,
                },
                {
                    "query": "남캐일러 웹소설 노벨피아",
                    "purpose": "official_title_verify",
                    "priority": 0,
                },
            ],
            post_id=11677913,
            ctx=ctx,
        )

        self.assertEqual(
            calls,
            [("이세계 검은머리 외국인 웹소설 노벨피아", "image_ocr_diagnostic_probe")],
        )
        self.assertNotIn("official_title_verify", [purpose for _, purpose in calls])
        self.assertEqual(len(diagnostic_results), 1)
        self.assertIs(diagnostic_results[0]["_ocr_diagnostic_only"], True)
        self.assertEqual(diagnostic_results[0]["_purpose"], "image_ocr_diagnostic_probe")
        diagnostic = {
            "query": "이세계 검은머리 외국인 웹소설 노벨피아",
            "purpose": "image_ocr_diagnostic_probe",
            "_ocr_diagnostic_only": True,
        }
        self.assertEqual(
            orchestrator._prune_title_search_requests_for_intent_permit(ctx, [dict(diagnostic, _ocr_diagnostic_only=False)]),
            [],
        )
        self.assertEqual(
            orchestrator._prune_title_search_requests_for_intent_permit(
                ctx, [dict(diagnostic, query="남캐일러 웹소설 노벨피아")]
            ),
            [],
        )
        with patch("llm_batch.experts.orchestrator.unresolved_ocr_alias_conflict_authority_blocked", return_value=True):
            self.assertEqual(
                orchestrator._prune_title_search_requests_for_intent_permit(ctx, [diagnostic]),
                [],
            )

    def test_search_result_carries_only_request_bound_ocr_diagnostic_flag(self):
        def fake_search(query, purpose="search"):
            url = (
                "https://www.munpia.com/novel/detail/222360"
                if purpose == "direct_ocr_alias_official_probe"
                else "https://novelpia.com/novel/102155"
            )
            return [{
                "title": "빌어먹을 환생" if "munpia" in url else "괴담 호텔 탈출기",
                "url": url, "content": "공식 작품 상세",
                "_ocr_diagnostic_only": True,  # search transport cannot grant this flag
            }]

        orchestrator = Orchestrator(experts={}, search_fn=fake_search)
        image_ctx = ConversationContext(
            post_id=11718099,
            post_data={
                "post_id": 11718099, "title": "빌환 표지변경됨",
                "image_enrichment": [{
                    "explicit_work_title": "빌어먹을 환생", "explicit_author_name": "목마",
                    "title_role": "unknown", "evidence_type": "cover_title",
                    "promotion_eligible": False,
                    "ocr_text": "MUNPIA 빌어먹을 환생 목마",
                }],
            },
            comments=[],
        )
        probe = orchestrator._direct_ocr_alias_official_probe_request(image_ctx)
        self.assertIsNotNone(probe)
        self.assertEqual(probe["purpose"], "direct_ocr_alias_official_probe")
        diagnostic_rows = orchestrator._execute_searches([probe], post_id=11718099, ctx=image_ctx)
        self.assertEqual(len(diagnostic_rows), 1)
        self.assertEqual(diagnostic_rows[0]["_purpose"], "direct_ocr_alias_official_probe")
        self.assertIs(diagnostic_rows[0]["_ocr_diagnostic_only"], True)
        image_ctx.add_search_results(diagnostic_rows)
        self.assertIs(image_ctx.search_results[0]["_ocr_diagnostic_only"], True)

        ordinary_ctx = ConversationContext(
            post_id=20010012,
            post_data={"post_id": 20010012, "title": "괴담 호텔 탈출기"},
            comments=[],
        )
        ordinary_rows = orchestrator._execute_searches([{
            "query": "괴담 호텔 탈출기 노벨피아", "purpose": "official_title_verify",
            "priority": 0,
        }], post_id=20010012, ctx=ordinary_ctx)
        self.assertEqual(len(ordinary_rows), 1)
        self.assertEqual(ordinary_rows[0]["_purpose"], "official_title_verify")
        self.assertNotIn("_ocr_diagnostic_only", ordinary_rows[0])
        ordinary_ctx.add_search_results(ordinary_rows)
        self.assertNotIn("_ocr_diagnostic_only", ordinary_ctx.search_results[0])

    def test_parallel_search_keeps_diagnostic_and_source_binding_on_own_result(self):
        class SearchTransport:
            def __init__(self):
                self.calls = []

            def search(self, query, purpose="search"):
                return self._search_with_meta(query, purpose)[0]

            def _search_with_meta(self, query, purpose="search", source_binding=None):
                self.calls.append((query, purpose, source_binding))
                key = "a" if "후보 가" in query else "b"
                return ([{"title": query, "url": f"https://example.test/{key}", "content": query}], {})

        transport = SearchTransport()
        orchestrator = Orchestrator(experts={}, search_fn=transport.search)
        binding = {"kind": "source_receipt", "id": "A"}
        with patch.dict("os.environ", {
            "PIPELINE_SEARCH_CONCURRENCY": "2",
            "LLM_ENABLE_CONTEXT_QUERY_RERANK": "0",
            "LLM_ENABLE_SMART_SEARCH_PRUNE": "0",
        }):
            rows = orchestrator._execute_searches([
                {"query": "후보 가 웹소설", "purpose": "image_ocr_diagnostic_probe",
                 "priority": 0, "_ocr_diagnostic_only": True, "source_binding": binding},
                {"query": "후보 나 웹소설", "purpose": "official_title_verify", "priority": 0},
            ], post_id=20010040)
        by_url = {row["url"]: row for row in rows}
        self.assertEqual(set(by_url), {"https://example.test/a", "https://example.test/b"})
        self.assertIs(by_url["https://example.test/a"]["_ocr_diagnostic_only"], True)
        self.assertEqual(by_url["https://example.test/a"]["_purpose"], "image_ocr_diagnostic_probe")
        self.assertNotIn("_ocr_diagnostic_only", by_url["https://example.test/b"])
        self.assertEqual(by_url["https://example.test/b"]["_purpose"], "official_title_verify")
        self.assertIn(("후보 가 웹소설", "image_ocr_diagnostic_probe", binding), transport.calls)
        self.assertIn(("후보 나 웹소설", "official_title_verify", None), transport.calls)

    def test_uncertain_ocr_phrase_fallback_requires_one_foreground_transcription(self):
        orchestrator = Orchestrator(experts={}, search_fn=lambda *_args, **_kwargs: [])
        base_image = {
            "explicit_work_title": "천마",
            "title_role": "unknown",
            "evidence_type": "explicit_text",
            "promotion_eligible": False,
            "ocr_text": "천마 김캇트 이세계 검은머리 외국인",
            "work_cues": ["천마", "이세계 검은머리 외국인"],
        }

        def permits(query, **overrides):
            image = {**base_image, **overrides}
            ctx = ConversationContext(
                post_id=11677913,
                post_data={"post_id": 11677913, "image_enrichment": [image]},
                comments=[],
            )
            return orchestrator._is_direct_image_ocr_work_phrase_query(query, ctx=ctx)

        self.assertTrue(permits("이세계 검은머리 외국인 웹소설 노벨피아"))
        self.assertTrue(permits('"이세계 검은머리 외국인" site:novelpia.com'))
        self.assertTrue(permits("소설가의 무림 외전 웹소설", ocr_text="소설가의 무림 외전", work_cues=[]))
        self.assertFalse(permits("소설가의 무림 외전", ocr_text="소설가의 무림 외전", work_cues=[]))
        self.assertFalse(permits("이세계 검은머리 외국인 site:evil.example"))
        self.assertFalse(permits("이세계 검은머리 외국인 웹소설 site:evil.example"))
        self.assertFalse(permits("이세계 검은머리 외국인 site:novelpia.com.evil.example"))
        self.assertFalse(permits("남캐일러 웹소설 노벨피아"))
        self.assertFalse(permits("이세계 검은머리 외국인 남캐일러 웹소설 노벨피아"))
        self.assertFalse(permits("이세계 외국인 웹소설 노벨피아"))
        self.assertFalse(permits("이세계 검은머리 외국인", ocr_text="", work_cues=["이세계", "검은머리 외국인"]))
        self.assertFalse(permits("이세계 검은머리 외국인 웹소설 노벨피아", title_role="work_title"))
        self.assertFalse(permits("이세계 검은머리 외국인 웹소설 노벨피아", evidence_type="scene_description"))
        self.assertFalse(permits("이세계 검은머리 외국인 웹소설 노벨피아", background_listing_only=True))
        self.assertFalse(permits("이세계 검은머리 외국인 웹소설 노벨피아", screen_type="search_results"))
        self.assertFalse(permits("이세계 검은머리 외국인 웹소설 노벨피아", surface_type="listing"))
        self.assertFalse(permits("이세계 검은머리 외국인 웹소설 노벨피아", focus_role="background_catalog"))
        self.assertFalse(permits("이세계 검은머리 외국인 웹소설 노벨피아", ocr_text="이세계 검은머리\n외국인", work_cues=[]))
        with patch("llm_batch.experts.orchestrator.unresolved_ocr_alias_conflict_authority_blocked", return_value=True):
            self.assertFalse(permits("이세계 검은머리 외국인 웹소설 노벨피아"))

    def test_rejects_search_promotion_after_context_only_expression_reread_review(self):
        fake_llm = FakeFinalSemanticRereadLLM(
            """
            {
              "decision": "REJECT",
              "is_specific_work_discussion": false,
              "evidence_strength": "Weak",
              "recommended_discussion_type": "community_banter",
              "reason": "표현 오타/축약 패턴(범용)은 검색 후보를 직접 지지하지 않는다."
            }
            """
        )
        pipeline = AgenticPipeline(llm=fake_llm, mcp=DummyMCP(), max_iterations=2)
        post_json = {
            "post_id": 11718091,
            "title": "소신발언)) 은영이 23센줄 몰랐음",
            "content_blocks": [{"type": "text", "text": "묘사만 보면 한 16살인줄???"}],
            "surface_paraphrase_notes": [
                {
                    "source_surface": "23센줄",
                    "role": "non_title_semantic_context",
                }
            ],
            "comment_context_lines": [
                "#1 speaker=user1 author=ㅇㅇ role=author_match_unverified comment_id=40479972"
            ],
            "comment_dialogue_context_lines": [
                "#1 speaker=user1 author=ㅇㅇ role=author_match_unverified comment_id=40479972 text=ㄹㅇ 머리도 안올렷잖아 더어린줄"
            ],
        }
        ctx = ConversationContext(
            post_id=11718091,
            post_data=post_json,
            comments=["ㄹㅇ 머리도 안올렷잖아 더어린줄"],
        )
        ctx.discourse_warning = "semantic_seed_review(no_work_anchor)"
        ctx.search_results = [
            {
                "_evidence_id": "E001",
                "title": "네이버 웹소설 검색 결과",
                "url": "https://example.test/search",
                "content": "검색어 일부만 겹치는 결과",
            }
        ]
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "express_opinion",
                    "target_kind": "character",
                    "semantic_seed_review": {
                        "content_interpretation": "표현 오타/축약 패턴(범용)으로 재검토해야 하는 비제목 자연어 표현이다.",
                        "is_specific_work_discussion": False,
                    },
                    "warnings": [
                        "semantic_seed_review_specific_work_denied",
                        "surface_paraphrase_non_title_terms_removed",
                    ],
                }
            },
        )

        review = pipeline._run_final_semantic_reread(
            ctx=ctx,
            is_relevant=True,
            official_title="네이버",
            discussion_type="general",
            verification_result={
                "is_relevant": True,
                "grounding_check": {"anchor_found": "search_only"},
            },
            final_decision={"is_relevant": True, "official_title": "네이버"},
        )
        action = pipeline._final_semantic_reread_action(review)

        self.assertEqual(review["decision"], "REJECT")
        self.assertTrue(action["changed"])
        self.assertEqual(action["discussion_type"], "community_banter")
        self.assertIn("final_semantic_reread_rejected_resolution", action["flags"])
        self.assertEqual(fake_llm.calls[0]["kwargs"].get("tag"), "final_semantic_reread")
        user_message = (fake_llm.calls[0]["kwargs"].get("messages") or [])[1]["content"]
        self.assertIn("표현 오타/축약 패턴(범용)", user_message)
        self.assertIn("정답 표현으로 결정적으로 치환하지 말고", user_message)
        self.assertNotIn("23세인 줄", user_message)
        self.assertNotIn("나이·외모", user_message)
        self.assertIn("#1 speaker=user1 author=ㅇㅇ role=author_match_unverified", user_message)
        self.assertIn("네이버", user_message)
        self.assertIn("표현 오타/축약 패턴(범용)", action["reason"])

    def test_non_relevant_reason_neutralizes_over_specific_work_topic(self):
        pipeline = AgenticPipeline(llm=FakeFinalSemanticRereadLLM("{}"), mcp=DummyMCP(), max_iterations=2)
        post_json = {
            "post_id": 11718091,
            "title": "소신발언)) 은영이 23센줄 몰랐음",
            "content": ["묘사만 보면 한 16살인줄???"],
            "comments": ["ㄹㅇ 머리도 안올렷잖아 더어린줄"],
            "surface_paraphrase_notes": [
                {
                    "kind": "expression_typo_abbreviation_or_spacing_candidate",
                    "source_surface": "23센줄",
                    "role": "non_title_semantic_context",
                    "interpretation": "packet_local_expression_reread_candidate",
                }
            ],
        }
        ctx = ConversationContext(post_id=11718091, post_data=post_json, comments=post_json["comments"])
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "express_opinion",
                    "target_kind": "character",
                    "semantic_seed_review": {
                        "post_intent": "직접 작품 앵커가 약한 짧은 반응이다.",
                        "content_interpretation": (
                            "작품 속 '은영'과 표면 표현은 작품 내 캐릭터에 대한 언급이며, "
                            "이는 작품 자체에 대한 논의로 해석됨."
                        ),
                        "is_specific_work_discussion": False,
                    },
                    "semantic_seed_review_context_terms": ["은영이", "23센줄"],
                    "surface_paraphrase_context_terms": ["은영이", "23센줄"],
                    "warnings": [
                        "semantic_seed_review_non_title_terms_removed",
                        "surface_paraphrase_non_title_terms_removed",
                    ],
                }
            },
        )

        reason = pipeline._format_non_relevant_reason(
            discussion_type="noise",
            rejection_reason="",
            verifier_reason="",
            arbiter_reason="",
            grounding_issue="",
            counter_arguments=[],
            ctx=ctx,
            verification_result={},
            final_decision={"is_relevant": False},
        )

        self.assertIn("특정 작품 식별 근거가 부족한 일반 잡담/불만", reason)
        self.assertNotIn("작품 자체에 대한 논의", reason)
        self.assertNotIn("작품 속", reason)
        self.assertNotIn("작품 내", reason)
        self.assertNotIn("작품 seed 제외: 은영이", reason)
        self.assertNotIn("작품 seed 제외: 은영이, 23센줄", reason)

    def test_surface_paraphrase_hint_does_not_sanitize_without_semantic_review(self):
        expert = DiscourseAnalyzer(FakeFinalSemanticRereadLLM("{}"))
        analysis = {
            "intent": "discuss_work",
            "target_kind": "work",
            "title_novel_terms": ["은영이", "23센줄"],
            "search_suggestions": [{"query": "은영이 표면표현 소설", "purpose": "probe"}],
            "warnings": [],
        }
        post_json = {
            "title": "소신발언)) 은영이 23센줄 몰랐음",
            "content": ["묘사만 보면 한 16살인줄???"],
            "comments": ["ㄹㅇ 머리도 안올렷잖아 더어린줄"],
            "surface_paraphrase_notes": [
                {
                    "source_surface": "23센줄",
                    "role": "non_title_semantic_context",
                }
            ],
        }

        result = expert._sanitize_surface_paraphrase_context(analysis, post_json)

        self.assertEqual(result["title_novel_terms"], ["은영이", "23센줄"])
        self.assertEqual(result["search_suggestions"][0]["query"], "은영이 표면표현 소설")
        self.assertNotIn("surface_paraphrase_non_title_terms_removed", result.get("warnings", []))

    def test_non_relevant_reason_weakens_unanchored_work_phrases(self):
        pipeline = AgenticPipeline(llm=FakeFinalSemanticRereadLLM("{}"), mcp=DummyMCP(), max_iterations=2)
        post_json = {
            "post_id": 11718091,
            "title": "소신발언)) 은영이 23센줄 몰랐음",
            "content": ["묘사만 보면 한 16살인줄???"],
            "surface_paraphrase_notes": [
                {
                    "source_surface": "23센줄",
                    "role": "non_title_semantic_context",
                }
            ],
        }
        ctx = ConversationContext(post_id=11718091, post_data=post_json, comments=[])
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "semantic_seed_review": {
                        "content_interpretation": "작품 내 특정 인물의 표면 반응이지만 작품명은 알 수 없다.",
                        "is_specific_work_discussion": False,
                    },
                    "semantic_seed_review_context_terms": ["은영"],
                    "warnings": ["semantic_seed_review_non_title_terms_removed"],
                }
            },
        )

        reason = pipeline._format_non_relevant_reason(
            discussion_type="noise",
            rejection_reason="",
            verifier_reason="",
            arbiter_reason="",
            grounding_issue="",
            counter_arguments=[],
            ctx=ctx,
            verification_result={},
            final_decision={"is_relevant": False, "official_title": None},
        )

        self.assertIn("문맥상 언급된 특정 인물의 표면 반응", reason)
        self.assertNotIn("작품 내", reason)
        self.assertNotIn("작품 속", reason)

    def test_semantic_seed_review_payload_uses_comment_context_lines(self):
        fake_llm = FakeFinalSemanticRereadLLM(
            """
            {
              "post_intent": "직접 작품 앵커가 약한 짧은 반응",
              "content_interpretation": "댓글까지 같은 표면 반응이며 직접 작품 앵커는 아니다.",
              "is_specific_work_discussion": false,
              "recommended_intent": "express_opinion",
              "recommended_target_kind": "character",
              "title_seed_reviews": [],
              "search_query_reviews": []
            }
            """
        )
        expert = DiscourseAnalyzer(fake_llm)
        analysis = {
            "intent": "discuss_work",
            "target_kind": "character",
            "title_novel_terms": ["은영이", "23센줄"],
            "search_suggestions": [{"query": "은영이 표면표현 소설", "purpose": "probe"}],
        }
        post_json = {
            "post_id": 11718091,
            "title": "소신발언)) 은영이 23센줄 몰랐음",
            "content": ["묘사만 보면 한 16살인줄???"],
            "comments": ["ㄹㅇ 머리도 안올렷잖아 더어린줄"],
            "comment_context_lines": [
                "#1 speaker=user1 author=ㅇㅇ role=author_match_unverified comment_id=40479972"
            ],
            "comment_dialogue_context_lines": [
                "#1 speaker=user1 author=ㅇㅇ role=author_match_unverified comment_id=40479972 text=ㄹㅇ 머리도 안올렷잖아 더어린줄"
            ],
            "surface_paraphrase_notes": [
                {
                    "source_surface": "23센줄",
                    "role": "non_title_semantic_context",
                }
            ],
        }

        review = expert._call_semantic_seed_review(analysis, post_json)

        self.assertIsInstance(review, dict)
        user_message = (fake_llm.calls[0]["kwargs"].get("messages") or [])[1]["content"]
        self.assertIn("comment_context", user_message)
        self.assertIn("comment_dialogue_context", user_message)
        self.assertIn("짧은 인명/캐릭터명처럼 보이는 seed는 단독으로 keep하지 않습니다", user_message)
        self.assertIn("직접 작품 앵커가 없으면 content_interpretation/reason에서", user_message)
        self.assertIn("다른 post에 재사용하지 않습니다", user_message)
        self.assertIn("정답 표현으로 결정적으로 치환하거나", user_message)
        self.assertIn("캐릭터명 단독 + 일반어 검색은 작품 식별을 보장하지 않으므로", user_message)
        self.assertIn("role=author_match_unverified", user_message)
        self.assertIn("ㄹㅇ 머리도 안올렷잖아 더어린줄", user_message)

    def test_stale_official_url_is_not_restored_after_freeze_clears_it(self):
        pipeline = AgenticPipeline(llm=FakeFinalSemanticRereadLLM("{}"), mcp=DummyMCP(), max_iterations=2)
        wrong_url = "https://book.novelpia.com/novel/13336"
        ctx = ConversationContext(
            post_id=11718097,
            post_data={
                "post_id": 11718097,
                "title": "망겜힐은 오행복 박태양이 빌런이였어야돼",
                "content_blocks": [{"type": "text", "text": "박태양과 오행복 서사 이야기"}],
            },
            comments=["검미성은 이런 전개를 더 밀었어야 함"],
        )
        ctx.search_results = [
            {
                "title": "앤드북스 - 노벨피아",
                "url": wrong_url,
                "content": "앤드북스 작품 페이지",
            }
        ]
        candidate = DetectedTitle(
            official_title="망겜의 힐러",
            heretic_url=wrong_url,
            confidence="High",
            source_tier="official_detail",
            reference_role="primary",
        )

        frozen = pipeline._freeze_identity_references(
            ctx=ctx,
            is_relevant=True,
            official_title="망겜의 힐러",
            heretic_url=wrong_url,
            confidence="High",
            topicality="core_relevant",
            work_resolution="resolved",
            title_candidates=[candidate],
            primary_work=candidate,
            mentioned_works=[],
            comparison_target=None,
            recommendation_candidates=[],
            future_watch_target=None,
            anchor_type="title_alias",
            consistency_flags=[],
        )

        self.assertIsNone(frozen["heretic_url"])
        self.assertIsNone(frozen["primary_work"].heretic_url)
        self.assertIn("official_detail_url_title_mismatch_cleared", frozen["consistency_flags"])

    def test_safe_official_url_rejects_stale_url_and_prefers_matching_search_url(self):
        pipeline = AgenticPipeline(llm=FakeFinalSemanticRereadLLM("{}"), mcp=DummyMCP(), max_iterations=2)
        wrong_url = "https://book.novelpia.com/novel/13336"
        correct_url = "https://series.naver.com/novel/detail.series?productNo=9146730"
        ctx = ConversationContext(
            post_id=11718097,
            post_data={"post_id": 11718097, "title": "망겜힐은 오행복 박태양이 빌런이였어야돼"},
            comments=[],
        )
        ctx.search_results = [
            {
                "title": "앤드북스 - 노벨피아",
                "url": wrong_url,
                "content": "앤드북스 작품 페이지",
            },
            {
                "title": "망겜의 힐러 - 네이버 시리즈",
                "url": correct_url,
                "content": "망겜의 힐러 웹소설. 작가 검미성.",
            },
        ]

        safe_url = pipeline._safe_official_detail_url_for_title(
            ctx,
            title="망겜의 힐러",
            candidate_url=wrong_url,
        )

        self.assertEqual(safe_url, correct_url)

    def test_safe_official_url_rejects_same_frame_wrong_core_title(self):
        pipeline = AgenticPipeline(llm=FakeFinalSemanticRereadLLM("{}"), mcp=DummyMCP(), max_iterations=2)
        wrong_url = "https://novelpia.com/novel/390001"
        correct_url = "https://novelpia.com/novel/380218"
        ctx = ConversationContext(
            post_id=11697267,
            post_data={"post_id": 11697267, "title": "헐... 아생갤 라나 정체 충격이네"},
            comments=["흑인녀가 아니였다고"],
        )
        ctx.search_results = [
            {
                "title": "아카데미 금태양 갤러리 - 노벨피아",
                "url": wrong_url,
                "content": "아카데미 금태양 갤러리 공식 작품 페이지",
            },
            {
                "title": "아카데미 생존 갤러리 - 노벨피아",
                "url": correct_url,
                "content": "아카데미 생존 갤러리 공식 작품 페이지",
            },
        ]
        ctx.fetched_page_info = [
            {
                "url": wrong_url,
                "structured_info": {
                    "title": "아카데미 금태양 갤러리",
                    "llm_identified_title": "아카데미 금태양 갤러리",
                    "page_type": "novel_page",
                    "content_status": "active",
                },
            }
        ]

        mismatch_title = pipeline._url_support_title_mismatch(
            ctx=ctx,
            url=wrong_url,
            title="아카데미 생존 갤러리",
        )
        safe_url = pipeline._safe_official_detail_url_for_title(
            ctx,
            title="아카데미 생존 갤러리",
            candidate_url=wrong_url,
        )

        self.assertEqual(mismatch_title, "아카데미 금태양 갤러리")
        self.assertEqual(safe_url, correct_url)

    def test_url_mismatch_allows_same_url_search_title_when_fetch_title_is_synopsis(self):
        pipeline = AgenticPipeline(llm=FakeFinalSemanticRereadLLM("{}"), mcp=DummyMCP(), max_iterations=2)
        correct_url = "https://m.munpia.com/novel/detail/328421"
        ctx = ConversationContext(
            post_id=11718097,
            post_data={"post_id": 11718097, "title": "망겜힐은 오행복 박태양이 빌런이였어야돼"},
            comments=[],
        )
        ctx.search_results = [
            {
                "title": "망겜의 힐러 - 문피아 웹소설 - Munpia",
                "url": correct_url,
                "content": "망겜의 힐러. 작가 검미성. 문피아 웹소설 작품 상세.",
            },
        ]
        ctx.fetched_page_info = [
            {
                "url": correct_url,
                "structured_info": {
                    "title": "한 소방관이 눈을 떴을 때 그는 망한 게임 속 힐러였다",
                    "page_title": "웹소설의 유토피아, 글세상 문피아",
                },
            }
        ]

        mismatch_title = pipeline._url_support_title_mismatch(
            ctx=ctx,
            url=correct_url,
            title="망겜의 힐러",
        )
        safe_url = pipeline._safe_official_detail_url_for_title(
            ctx,
            title="망겜의 힐러",
            candidate_url=correct_url,
        )

        self.assertIsNone(mismatch_title)
        self.assertEqual(safe_url, correct_url)

    def test_visual_only_vlm_note_is_not_claimed_as_title_grounding(self):
        pipeline = AgenticPipeline(llm=FakeFinalSemanticRereadLLM("{}"), mcp=DummyMCP(), max_iterations=2)
        ctx = ConversationContext(
            post_id=11718097,
            post_data={
                "post_id": 11718097,
                "title": "망겜힐은 오행복 박태양이 빌런이였어야돼",
                "vlm_enrichment_used": True,
                "image_enrichment": [
                    {
                        "visual_summary": "금발 캐릭터 팬아트",
                        "evidence_type": "character_visual_only",
                        "promotion_eligible": False,
                    }
                ],
            },
            comments=[],
        )

        note = pipeline._build_image_grounding_note(ctx, official_title="망겜의 힐러")

        self.assertIn("이미지는 장면 보조 정보만 제공했으며 OCR/표지 제목 근거는 확인되지 않았습니다.", note)
        self.assertNotIn("보강을 함께 사용", note)
        self.assertNotIn("망겜의 힐러의 제목", note)

    def test_verified_alias_official_detail_anchor_blocks_final_reread_nulling(self):
        pipeline = AgenticPipeline(llm=FakeFinalSemanticRereadLLM("{}"), mcp=DummyMCP(), max_iterations=2)
        title = "이세계 검은 머리 외국인"
        ctx = ConversationContext(
            post_id=11677913,
            post_data={
                "post_id": 11677913,
                "title": "남캐일러 뽑아도 된다고",
                "content_blocks": [
                    {
                        "type": "text",
                        "text": "천마 김캇트 이세계 검은머리 외국인 이런거 하라고",
                    }
                ],
            },
            comments=["캇트한테면 박혀도 좋아"],
        )
        ctx.search_results = [
            {
                "title": "웹소설로 꿈꾸는 세상! - 이세계 검은 머리 외국인 - 노벨피아",
                "url": "https://novelpia.com/novel/1082",
                "content": "작가 김갈비뼈. 주인공 김캇트.",
            }
        ]
        candidate = DetectedTitle(
            official_title=title,
            heretic_url="https://novelpia.com/novel/1082",
            confidence="High",
            alias_or_mention="김캇트",
            source_tier="official_detail",
            page_type="novel_page",
            content_status="active",
            reference_role="candidate",
        )

        keep = pipeline._should_keep_final_semantic_resolution_after_official_recall_anchor(
            ctx=ctx,
            official_title=title,
            verification_result={
                "grounding_check": {
                    "anchor_found": "character_mention",
                    "matched_alias": "김캇트",
                }
            },
            title_candidates=[candidate],
            consistency_flags=[
                "verified_alias_official_detail_anchor",
                "confirmed_alias:김캇트",
            ],
        )

        self.assertFalse(keep)

    def test_specific_work_alias_with_official_detail_keeps_final_reread_resolution(self):
        pipeline = AgenticPipeline(llm=FakeFinalSemanticRereadLLM("{}"), mcp=DummyMCP(), max_iterations=2)
        title = "[림월드]변방계에서 회귀자로 살아남기"
        url = "https://novelpia.com/novel/382324"
        ctx = ConversationContext(
            post_id=20010029,
            post_data={
                "post_id": 20010029,
                "title": "랫따싶 칸시가 정실이엿으면",
                "content_blocks": [{"type": "text", "text": "바로 시트러스 노예조교 on이엿을텐데"}],
                "image_enrichment": [{
                    "ocr_text": "Rim World -modded- 사료 섭취 -12 동물밥을 먹어야 했어.",
                    "visual_summary": "게임 UI 스타일의 텍스트가 있는 캐릭터 일러스트.",
                    "explicit_work_title": "Rim World",
                    "evidence_type": "explicit_text",
                    "work_cues": ["Rim World", "modded", "게임 UI 스타일의 텍스트"],
                }],
            },
            comments=["그치만 폐급이고 - dc App", "심지어 시트러스햄은 싸우는 폼보니까 강인함도 있겠다에요"],
        )
        ctx.set_expert_output(ExpertType.DISCOURSE, {"discourse_analysis": {
            "primary_domain": "gaming", "intent": "make_joke", "target_kind": "character",
        }})
        ctx.search_results = [{
            "title": title, "url": url,
            "content": "노벨피아 작품. #패러디 #림월드 #랫따싶.",
            "snippet": "단, 죽어서만. #패러디 #림월드 #랫따싶.",
            "query": "Rim World 웹소설 노벨피아",
        }]
        candidate, hit = pipeline._resolve_title_lead_alias_official_detail_release_candidate(ctx)
        self.assertIsNotNone(candidate)
        self.assertEqual(hit["source"], "title_lead_alias_official_detail_release")
        verification = {
            "is_relevant": True,
            "is_novel_discussion": True,
            "novel_identity": {"official_title": title, "heretic_url": url},
            "slang_insight": {
                "detected_term": "랫따싶", "canonical_work_alias": "랫따싶",
                "decoded_term": title, "decode_verified": True, "alias_scope": "pure_work_alias",
            },
            "grounding_check": {
                "anchor_found": "title_mention", "matched_alias": "랫따싶", "matched_title": title,
            },
            "relation_judgment": {
                "relation_type": "explicit_alias", "discussion_target": "specific_work",
                "promotion_decision": "allow", "observed_aliases": ["랫따싶"],
            },
        }
        self.assertTrue(pipeline._has_explicit_alias_official_work_lock(ctx, title, verification))
        self.assertTrue(pipeline._should_keep_final_semantic_resolution_after_official_recall_anchor(
            ctx=ctx, official_title=title, verification_result=verification,
            title_candidates=[candidate],
            consistency_flags=["verified_alias_official_detail_anchor", "confirmed_alias:랫따싶"],
        ))


if __name__ == "__main__":
    unittest.main()
