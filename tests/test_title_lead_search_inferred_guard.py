from __future__ import annotations

import ast
import os
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_batch.agentic_pipeline import AgenticPipeline  # noqa: E402
from llm_batch.domain.batch_context import BatchContextMemory  # noqa: E402
from llm_batch.grounding.candidate_audit import apply_weak_public_title_bridge_guard  # noqa: E402
from llm_batch.experts.decoder import (  # noqa: E402
    DecoderExpert,
    is_snippet_artifact_title_expansion,
)
from llm_batch.experts.orchestrator import ConversationContext, ExpertType, Orchestrator  # noqa: E402
from llm_batch.experts.verifier import VerifierExpert  # noqa: E402
from llm_batch.domain.models import (  # noqa: E402
    ContentBlock,
    DetectedTitle,
    NovelIdentity,
    PickvelIdentity,
    PickvelOutputItemV2,
    PostInput,
    SlangInsight,
)
from llm_batch.promotion_gate import (  # noqa: E402
    GroundingState,
    evaluate_publish_contract,
)


class DummyLLM:
    pass


class JSONLLM:
    def __init__(self, payload):
        self.payload = payload
        self.max_tokens = 8192

    def _stream_chat_http(self, **_kwargs):
        import json

        return json.dumps(self.payload, ensure_ascii=False)


class DummyMCP:
    pass


class FailOnSearchMCP:
    def search(self, *_args, **_kwargs):
        raise AssertionError("search should not run when semantic no-work blocks URL recovery")


class CountingSearchMCP:
    def __init__(self):
        self.calls = []

    def search(self, query, purpose=""):
        self.calls.append({"query": query, "purpose": purpose})
        return {
            "results": [
                {
                    "title": "재벌가 차녀의 2회차 걸그룹 - 웹소설 - 카카오페이지",
                    "url": "https://page.kakao.com/content/66692543",
                    "content": "작가 유은우. 재벌가 차녀의 2회차 걸그룹 267화.",
                }
            ]
        }


def build_pipeline() -> AgenticPipeline:
    return AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=2)


def mark_no_work_seed(ctx: ConversationContext) -> None:
    ctx.uncertainty_sources.append(
        "intent_permit_for_title_search=false(semantic_seed_review_not_specific_work)"
    )
    ctx.discourse_warning = "community_banter(no_work_anchor)"
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



def _baseline_source_snapshot(ctx):
    """제품이 원문·댓글을 바꾸지 않았는지만 비교한다."""
    import hashlib
    import json
    raw=json.dumps({"post":ctx.post_data,"comments":ctx.comments},
                   ensure_ascii=False,sort_keys=True,separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf8")).hexdigest()


def _baseline_synthetic_fetched_detail(case, pipeline, ctx, title, url, *, candidate_title):
    """합성 fetch 입력을 실제 display guard로 확인한다. 권한 반환값 stub 없음."""
    before=pipeline._official_detail_display_title_binding(ctx,candidate_title,url,fetch_if_missing=False)
    case.assertEqual(before["status"],"unavailable")
    ctx.fetched_page_info = list(getattr(ctx,"fetched_page_info",None) or []) + [{
        "url":url,
        "structured_info":{"title":title,"page_type":"novel_page","content_status":"active"},
    }]
    binding=pipeline._official_detail_display_title_binding(ctx,candidate_title,url,fetch_if_missing=False)
    case.assertEqual(binding["status"],"compatible")
    case.assertEqual(binding["canonical_title"],title)


def _baseline_record_contract(case, ctx, decision, source_before, scenario):
    """실제 gate의 state/evidence/지문을 ROOT 로그에 보존한다."""
    import json
    case.assertEqual(_baseline_source_snapshot(ctx),source_before)
    case.assertTrue(decision.get("input_fingerprint"))
    print("[baseline_contract_fixture_observation] "+json.dumps({
        "scenario":scenario,"source_sha256":source_before,"decision":decision,
        "state":ctx._last_promotion_gate_state,"evidence":ctx._last_promotion_gate_evidence,
        "synthetic_fixture_only":True,"network_observation":False,
    },ensure_ascii=False,sort_keys=True))


class TitleLeadSearchInferredGuardTest(unittest.TestCase):

    def test_baseline_confirmed_typed_image_initial_executes_exactly_two_ocr_queries(self):
        calls = []

        def search_fn(query, purpose=""):
            calls.append((query, purpose))
            return []

        orchestrator = Orchestrator(experts={}, search_fn=search_fn)
        ctx = ConversationContext(
            post_id=11716480,
            post_data={
                "post_id": 11716480,
                "title": "아생갤 볼만함?",
                "content_blocks": [{"type": "image", "url": "https://dcimg.example/11716480.jpg"}],
                "image_enrichment": [
                    {
                        "evidence_type": "explicit_text",
                        "title_role": "work_title",
                        "screen_type": "work_surface",
                        "surface_type": "official_detail_page",
                        "explicit_work_title": "아카데미 생존 갤러리",
                        "explicit_author_name": "테스트작가",
                    }
                ],
            },
            comments=[],
        )
        gatekeeper = {
            "post_type": "work_discussion",
            "detected_entities": {"possible_titles": ["아생갤"]},
            "context_clues": {"title_as_body_continuation": True},
        }
        ctx.set_expert_output(ExpertType.GATEKEEPER, gatekeeper)
        # 합성 외부 공식 관측: 실제 네트워크 조회를 수행했다는 뜻이 아니다.
        ctx.fetched_page_info = [{
            "url": "https://novelpia.com/novel/380218",
            "structured_info": {"title": "아카데미 생존 갤러리",
                                "page_type": "novel_page", "content_status": "active"},
        }]
        source_before = _baseline_source_snapshot(ctx)
        requests = orchestrator._clamp_typed_image_work_title_initial_search_requests(
            ctx,
            [
                {"query": "아생갤 노벨피아", "purpose": "platform_title_search", "priority": 1},
                {"query": "시리즈 아생갤 작가", "purpose": "platform_title_search", "priority": 2},
            ],
            phase="test_pre_execute",
        )

        orchestrator._execute_searches(
            requests,
            ctx.post_id,
            ctx=ctx,
            initial_typed_title_only=True,
        )

        self.assertEqual(
            {query for query, _purpose in calls},
            {
                '"아카데미 생존 갤러리" "테스트작가"',
                '"아카데미 생존 갤러리" 노벨피아',
            },
        )
        self.assertEqual(len(calls), 2)

        self.assertEqual(_baseline_source_snapshot(ctx), source_before)


    def test_baseline_alias_canonicalization_with_allow_and_exact_fetched_binding(self):
        pipeline = build_pipeline()
        alias_title = "암흑가보스"
        official_title = "암흑가 보스요? 제가요?"
        official_url = "https://novelpia.com/novel/384111"
        weak_phrase_competitor = "암흑가 보스의 버려진 딸이 되었다"
        weak_competitor_url = "https://ridibooks.com/books/3863000164"
        post = PostInput(
            post_id=11660257,
            title="암흑가보스<<이거 재밋네",
            author="ㅇㅇ",
            content_blocks=[],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.llm_snippet_analysis = {
            "identified_title": official_title,
            "abbreviation_mappings": [{"abbrev": alias_title, "full": official_title}],
        }
        ctx.search_results = [
            {
                "title": official_title,
                "url": official_url,
                "content": "암흑가 보스요? 제가요? 작가명 손아픈사람. PLUS 독점. #현대 #판타지 #하렘",
                "query": "암흑가보스 노벨피아",
                "source_tier": "official_detail",
            },
            {
                "title": f"{weak_phrase_competitor} - 로판 e북",
                "url": weak_competitor_url,
                "content": "암흑가 보스의 버려진 딸이 되었다 작품소개.",
                "query": "시리즈 암흑가보스 작가",
                "source_tier": "novel_platform",
            },
        ]
        final_decision = {
            "discussion_type": "general",
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
            "_raw_llm_title": official_title,
        }
        vf_result = {
            "novel_identity": {
                "official_title": official_title,
                "official_novel_title": official_title,
                "heretic_url": official_url,
            },
            "grounding_check": {
                "anchor_found": "title_mention",
                "title_abbrev_mentioned": True,
                "matched_alias": alias_title,
            },
            "slang_insight": {
                "detected_term": alias_title,
                "decoded_term": official_title,
                "decode_verified": True,
                "alias_scope": "pure_work_alias",
            },
            "relation_judgment": {
                "relation_type": "explicit_alias",
                "discussion_target": "specific_work",
                "promotion_decision": "allow",
            },
        }
        candidates = [
            DetectedTitle(
                official_title=alias_title,
                heretic_url=official_url,
                confidence="High",
                source_tier="official_detail",
                page_type="novel_page",
            ),
            DetectedTitle(
                official_title=official_title,
                confidence="High",
                source_tier="community",
            ),
        ]

        _baseline_synthetic_fetched_detail(self, pipeline, ctx, official_title, official_url,
                                           candidate_title=official_title)
        source_before = _baseline_source_snapshot(ctx)

        decision = pipeline._record_title_led_alias_public_title_gate_decision(
            ctx,
            alias_title,
            candidate_url=official_url,
            final_decision=final_decision,
            verification_result=vf_result,
            title_candidates=candidates,
            acceptance={"decision": "accept", "title_led_consumption_bridge": True, "score": 29},
        )

        _baseline_record_contract(self, ctx, decision, source_before, "synthetic_alias_allow")

        self.assertEqual(decision["status"], "publish")
        self.assertTrue(decision["publish_allowed"])
        self.assertEqual(decision["official_title"], official_title)
        self.assertEqual(decision["official_url"], official_url)
        self.assertIn("title_led_alias_official_detail_canonicalized", decision["reason_codes"])
        state = ctx._last_promotion_gate_state
        self.assertTrue(state["row_discusses_work_as_work"])
        self.assertEqual(state["scope"]["scope_kind"], "current_work")
        self.assertEqual(state["scope"]["conflict_reason_codes"], [])
        self.assertIn("title_led_alias_official_detail_canonicalized", state["scope"]["direct_bridge_sources"])
        self.assertNotIn("title_led_alias_contextual_official_detail_competes", decision["reason_codes"])
        self.assertNotIn(weak_phrase_competitor, state["scope"]["competing_candidates"])

        self.assertEqual(vf_result["relation_judgment"]["promotion_decision"], "allow")


    def test_baseline_munpia_brand_tail_with_synthetic_author_work_relation(self):
        pipeline = build_pipeline()
        title = "전지적 독자 시점"
        url = "https://novel.munpia.com/104753"
        post = PostInput(
            post_id=11677915,
            title="전독시 읽고 감상 남김",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="이 새끼의 최애작품은 뭔지 알아내서"),
                ContentBlock(type="text", text="메차쿠차 비난하고 ntr하고 싶음"),
            ],
            comments=["응 느그 전독시 느그 배본블 ㅋ"],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=post.comments,
        )
        ctx.search_results = [
            {
                "title": f"{title} - 문피아 웹소설 - Munpia",
                "url": url,
                "content": f"전독시로 불리는 {title}. 싱숑 작가.",
                "query": "전독시 문피아",
                "source_tier": "official_detail",
            }
        ]
        final_decision = {
            "discussion_type": "meme",
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
        }
        vf_result = {
            "grounding_check": {
                "anchor_found": "title_abbrev_mention",
                "title_abbrev_mentioned": True,
                "matched_alias": "전독시",
            },
            "slang_insight": {
                "detected_term": "전독시",
                "decoded_term": title,
                "decode_verified": True,
                "alias_scope": "pure_work_alias",
            },
        }

        _baseline_synthetic_fetched_detail(self, pipeline, ctx, title, url,
                                           candidate_title=title)
        source_before = _baseline_source_snapshot(ctx)

        decision = pipeline._record_title_led_alias_public_title_gate_decision(
            ctx,
            title,
            candidate_url=url,
            final_decision=final_decision,
            verification_result=vf_result,
            title_candidates=[
                DetectedTitle(
                    official_title=title,
                    heretic_url=url,
                    confidence="High",
                    alias_or_mention="전독시",
                    source_tier="official_detail",
                    page_type="novel_page",
                )
            ],
            acceptance={"decision": "accept", "title_led_consumption_bridge": True, "score": 29},
        )

        _baseline_record_contract(self, ctx, decision, source_before, "synthetic_author_munpia")

        self.assertEqual(decision["status"], "publish")
        self.assertTrue(decision["publish_allowed"])
        self.assertEqual(decision["official_title"], title)
        self.assertNotIn("title_led_alias_contextual_official_detail_competes", decision["reason_codes"])
        state = ctx._last_promotion_gate_state
        self.assertTrue(state["row_discusses_work_as_work"])
        self.assertEqual(state["scope"]["scope_kind"], "current_work")
        self.assertEqual(state["scope"]["competing_candidates"], [])


    def test_baseline_unofficial_extension_with_synthetic_author_work_relation(self):
        pipeline = build_pipeline()
        exact_title = "가챠 중독자의 퓨전펑크 생활"
        extended_title = "가챠 중독자의 퓨전펑크 생활 볼려고 했는데"
        post = PostInput(
            post_id=11698880,
            title="가챠펑크 읽고 감상 남김",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="가챠펑크 세드릭도 그렇고"),
                ContentBlock(type="text", text="시원시원한 상남자라서 너무 좋구나"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        final_decision = {
            "discussion_type": "character_talk",
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
            "primary_subject_type": "work_discussion",
            "slang_insight": {
                "detected_term": "가챠펑크",
                "decoded_term": exact_title,
                "decode_verified": True,
                "canonical_work_alias": "가챠펑크",
            },
            "entity_mentions": [
                {
                    "text": "가챠펑크",
                    "entity_type": "work",
                    "canonical_value": exact_title,
                    "confidence": "High",
                    "role": "primary",
                }
            ],
        }
        vf_result = {
            "grounding_check": {
                "anchor_found": "character_mention",
                "title_abbrev_mentioned": True,
                "body_abbrev_mentioned": True,
                "matched_alias": "가챠펑크",
            }
        }
        title_candidates = [
            DetectedTitle(
                official_title=exact_title,
                heretic_url="https://namu.wiki/w/가챠%20중독자의%20퓨전펑크%20생활",
                confidence="High",
                alias_or_mention="가챠펑크",
                source_tier="llm_only",
                locked=True,
                reference_role="primary",
            )
        ]

        source_before = _baseline_source_snapshot(ctx)

        decision = pipeline._record_title_led_alias_public_title_gate_decision(
            ctx,
            extended_title,
            candidate_url=None,
            final_decision=final_decision,
            verification_result=vf_result,
            title_candidates=title_candidates,
            acceptance={"decision": "accept", "title_led_consumption_bridge": True, "score": 24},
        )

        _baseline_record_contract(self, ctx, decision, source_before, "synthetic_author_title_only")

        self.assertEqual(decision["status"], "publish")
        self.assertTrue(decision["publish_allowed"])
        self.assertEqual(decision["official_title"], exact_title)
        self.assertIsNone(decision["official_url"])
        self.assertIn("preserved_title_candidate_selected", decision["reason_codes"])
        state = ctx._last_promotion_gate_state
        self.assertEqual(state["candidate_title"], exact_title)
        self.assertIn("title_extension_trimmed", state["scope"]["direct_bridge_sources"])
        self.assertEqual(state["scope"]["competing_candidates"], [])


    def test_direct_image_work_title_search_injection_is_exact_and_bounded(self):
        orchestrator = Orchestrator(experts={})
        ctx = ConversationContext(
            post_id=11716480,
            post_data={
                "post_id": 11716480,
                "image_enrichment": [
                    {
                        "evidence_type": "explicit_text",
                        "title_role": "work_title",
                        "screen_type": "work_surface",
                        "explicit_work_title": "재벌가 차녀의 2회차 걸그룹",
                        "explicit_author_name": "유은우",
                        "ocr_text": "#로맨스 UI 홈 추천 작품 재벌가 차녀의 2회차 걸그룹",
                        "work_cues": ["재벌가 차녀", "2회차", "걸그룹", "#로맨스"],
                    }
                ],
            },
            comments=[],
        )

        requests = orchestrator._inject_image_work_cue_search_requests(ctx, [])

        self.assertEqual(
            [request["query"] for request in requests],
            [
                '"재벌가 차녀의 2회차 걸그룹" "유은우"',
                '"재벌가 차녀의 2회차 걸그룹" 노벨피아',
            ],
        )
        self.assertTrue(all(request["purpose"] == "image_work_cue_search" for request in requests))
        self.assertFalse(any('"재벌가" "걸그룹"' in request["query"] for request in requests))
        self.assertFalse(any("#로맨스" in request["query"] for request in requests))

        existing = [
            {
                "query": "재벌가 차녀의 2회차 걸그룹 유은우",
                "purpose": "official_title_verify",
                "priority": 0,
            }
        ]
        deduped = orchestrator._inject_image_work_cue_search_requests(ctx, existing)
        self.assertEqual(len(deduped), 2)
        self.assertEqual(
            [request["query"] for request in deduped],
            [
                '"재벌가 차녀의 2회차 걸그룹" "유은우"',
                '"재벌가 차녀의 2회차 걸그룹" 노벨피아',
            ],
        )

        clamped = orchestrator._clamp_typed_image_work_title_initial_search_requests(
            ctx,
            [
                *existing,
                {
                    "query": "재벌가 차녀의 2회차 걸그룹 review",
                    "purpose": "title_search_community",
                    "priority": 1,
                },
            ],
            phase="test",
        )
        self.assertEqual(
            [request["query"] for request in clamped],
            [
                '"재벌가 차녀의 2회차 걸그룹" "유은우"',
                '"재벌가 차녀의 2회차 걸그룹" 노벨피아',
            ],
        )

        ctx.post_data["image_enrichment"][0]["title_role"] = "unknown"
        unknown_role_requests = orchestrator._inject_image_work_cue_search_requests(
            ctx,
            [],
        )
        self.assertEqual(
            [request["query"] for request in unknown_role_requests],
            [
                '"재벌가 차녀의 2회차 걸그룹" "유은우"',
                '"재벌가 차녀의 2회차 걸그룹" 노벨피아',
            ],
        )
        mark_no_work_seed(ctx)
        kept_unknown_role_requests = orchestrator._prune_title_search_requests_for_intent_permit(
            ctx,
            unknown_role_requests,
            phase="test_unknown_typed_title",
        )
        self.assertEqual(
            [request["query"] for request in kept_unknown_role_requests],
            [
                '"재벌가 차녀의 2회차 걸그룹" "유은우"',
                '"재벌가 차녀의 2회차 걸그룹" 노벨피아',
            ],
        )
        noncanonical_kept = orchestrator._prune_title_search_requests_for_intent_permit(
            ctx,
            [
                {
                    "query": '"재벌가 차녀의 2회차 걸그룹" review novelpia',
                    "purpose": "image_work_cue_search",
                    "priority": 0,
                },
                {
                    "query": 'site:novelpia.com/novel "재벌가 차녀의 2회차 걸그룹" review',
                    "purpose": "image_work_cue_search",
                    "priority": 0,
                },
                {
                    "query": '"재벌가 차녀의 2회차 걸그룹" "유은우" review',
                    "purpose": "image_work_cue_search",
                    "priority": 0,
                },
            ],
            phase="test_unknown_noncanonical",
        )
        self.assertEqual(noncanonical_kept, [])

    def test_typed_image_initial_execute_searches_remains_exactly_two(self):
        calls = []

        def search_fn(query, purpose=""):
            calls.append((query, purpose))
            return []

        orchestrator = Orchestrator(experts={}, search_fn=search_fn)
        ctx = ConversationContext(
            post_id=11716480,
            post_data={
                "post_id": 11716480,
                "title": "아생갤 볼만함?",
                "content_blocks": [{"type": "image", "url": "https://dcimg.example/11716480.jpg"}],
                "image_enrichment": [
                    {
                        "evidence_type": "explicit_text",
                        "title_role": "work_title",
                        "screen_type": "work_surface",
                        "surface_type": "official_detail_page",
                        "explicit_work_title": "아카데미 생존 갤러리",
                        "explicit_author_name": "테스트작가",
                    }
                ],
            },
            comments=[],
        )
        gatekeeper = {
            "post_type": "work_discussion",
            "detected_entities": {"possible_titles": ["아생갤"]},
            "context_clues": {"title_as_body_continuation": True},
        }
        ctx.set_expert_output(ExpertType.GATEKEEPER, gatekeeper)
        source_before = _baseline_source_snapshot(ctx)
        requests = orchestrator._clamp_typed_image_work_title_initial_search_requests(
            ctx,
            [
                {"query": "아생갤 노벨피아", "purpose": "platform_title_search", "priority": 1},
                {"query": "시리즈 아생갤 작가", "purpose": "platform_title_search", "priority": 2},
            ],
            phase="test_pre_execute",
        )

        orchestrator._execute_searches(
            requests,
            ctx.post_id,
            ctx=ctx,
            initial_typed_title_only=True,
        )

        self.assertEqual(
            {query for query, _purpose in calls},
            {
                '"아카데미 생존 갤러리" "테스트작가"',
                'site:novelpia.com/novel "아생갤"',
            },
        )
        self.assertEqual(len(calls), 2)

        self.assertEqual(_baseline_source_snapshot(ctx), source_before)
        self.assertEqual(len(ctx.search_results), 0)

    def test_late_image_ocr_recall_uses_only_typed_explicit_work_title(self):
        mcp = CountingSearchMCP()
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=mcp, max_iterations=2)
        typed_title = "재벌가 차녀의 2회차 걸그룹"
        raw_ocr = "#로맨스 UI 홈 추천 독점 신작 지금 무료보기"
        ctx = ConversationContext(
            post_id=11716480,
            post_data={
                "post_id": 11716480,
                "title": "이거 무슨 작품임 이미지 봐줘",
                "content_blocks": [{"type": "image", "url": "https://dcimg.example/11716480.jpg"}],
                "image_enrichment": [
                    {
                        "evidence_type": "explicit_text",
                        "title_role": "work_title",
                        "explicit_work_title": typed_title,
                        "ocr_text": raw_ocr,
                    }
                ],
            },
            comments=[],
        )
        search_calls = []

        def empty_search_with_meta(query, *, purpose):
            search_calls.append((query, purpose))
            return [], {"provider": "unit_test"}

        with patch.object(pipeline, "_search_with_meta", side_effect=empty_search_with_meta):
            pipeline._title_body_listing_official_url_recall_promotion(
                ctx,
                extended_identity={},
                final_decision={},
                verification_result={},
            )

        ocr_calls = [query for query, purpose in search_calls if purpose == "ocr_phrase_official_url_recall"]
        self.assertEqual(
            ocr_calls,
            [
                f'site:novelpia.com/novel "{typed_title}"',
                f'"{typed_title}" 노벨피아',
            ],
        )
        self.assertFalse(any(raw_ocr in query or "#로맨스" in query or "무료보기" in query for query in ocr_calls))

        ctx.executed_queries = [f'"{typed_title}" review']
        search_calls.clear()
        with patch.object(pipeline, "_search_with_meta", side_effect=empty_search_with_meta):
            pipeline._title_body_listing_official_url_recall_promotion(
                ctx,
                extended_identity={},
                final_decision={},
                verification_result={},
            )
        self.assertEqual(
            [query for query, purpose in search_calls if purpose == "ocr_phrase_official_url_recall"],
            [
                f'site:novelpia.com/novel "{typed_title}"',
                f'"{typed_title}" 노벨피아',
            ],
        )

        ctx.executed_queries = [f'"{typed_title}"']
        search_calls.clear()
        with patch.object(pipeline, "_search_with_meta", side_effect=empty_search_with_meta):
            pipeline._title_body_listing_official_url_recall_promotion(
                ctx,
                extended_identity={},
                final_decision={},
                verification_result={},
            )
        self.assertFalse(
            any(
                purpose == "ocr_phrase_official_url_recall"
                for _query, purpose in search_calls
            )
        )

        ctx.executed_queries = [
            f'"{typed_title}" "유은우"',
            f'"{typed_title}" 노벨피아',
        ]
        search_calls.clear()
        with patch.object(pipeline, "_search_with_meta", side_effect=empty_search_with_meta):
            pipeline._title_body_listing_official_url_recall_promotion(
                ctx,
                extended_identity={},
                final_decision={},
                verification_result={},
            )
        self.assertFalse(
            any(
                purpose == "ocr_phrase_official_url_recall"
                for _query, purpose in search_calls
            )
        )

    def test_expert_url_prefilter_keeps_selected_and_direct_official_urls(self):
        pipeline = build_pipeline()
        selected_title = "재벌가 차녀의 2회차 걸그룹"
        direct_url = "https://novelpia.com/novel/100003"
        related_url = "https://novelpia.com/novel/100001"
        snippet_related_url = "https://novelpia.com/novel/100004"
        unrelated_url = "https://novelpia.com/novel/100002"
        ctx = ConversationContext(
            post_id=11716480,
            post_data={
                "post_id": 11716480,
                "title": "작품 URL 확인",
                "content_blocks": [{"type": "text", "text": f"직접 링크 {direct_url}"}],
            },
            comments=[],
        )
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "decoded_terms": [
                    {
                        "candidates": [
                            {"title": selected_title, "url": related_url},
                            {"title": "무관한 공식 작품", "url": unrelated_url},
                            {"url": direct_url},
                            {"url": snippet_related_url},
                        ]
                    }
                ]
            },
        )
        ctx.set_expert_output(
            ExpertType.VERIFIER,
            {
                "verification_result": {
                    "novel_identity": {
                        "official_title": "무관한 공식 작품",
                        "heretic_url": unrelated_url,
                    }
                }
            },
        )
        search_results = [
            {
                "title": f"{selected_title} - 노벨피아",
                "url": snippet_related_url,
                "content": "작가 유은우의 공식 작품 상세",
            }
        ]

        urls = pipeline._collect_expert_urls(
            ctx,
            selected_title=selected_title,
            selected_author="유은우",
            search_results=search_results,
        )

        self.assertEqual(set(urls), {related_url, direct_url, snippet_related_url})
        self.assertNotIn(unrelated_url, urls)

    def test_heretic_url_prefetch_blocks_unrelated_candidate_before_live_fetch(self):
        pipeline = build_pipeline()
        selected_title = "재벌가 차녀의 2회차 걸그룹"
        unrelated_url = "https://novelpia.com/novel/100002"
        ctx = ConversationContext(
            post_id=11716480,
            post_data={
                "post_id": 11716480,
                "title": "작품 URL 확인",
                "content_blocks": [{"type": "text", "text": "링크 없음"}],
            },
            comments=[],
        )
        ctx.search_results = [
            {
                "title": "무관한 공식 작품",
                "url": unrelated_url,
                "content": "노벨피아 작품 상세",
            }
        ]

        with patch.object(
            pipeline,
            "_fetch_and_attach_page_info",
            side_effect=AssertionError("unrelated URL must be filtered before live fetch"),
        ) as fetch:
            validated = pipeline._validate_heretic_url(
                unrelated_url,
                ctx,
                identified_title=selected_title,
            )

        self.assertIsNone(validated)
        fetch.assert_not_called()

    def test_heretic_url_prefetch_blocks_generic_candidate_without_selected_identity(self):
        pipeline = build_pipeline()
        unrelated_url = "https://novelpia.com/novel/210295"
        ctx = ConversationContext(
            post_id=11716480,
            post_data={
                "post_id": 11716480,
                "title": "아오 포티햄",
                "content_blocks": [{"type": "text", "text": "나만 볼 수 없지"}],
            },
            comments=[],
        )
        ctx.search_results = [
            {
                "title": "보빔 깔개는 레즈 순애 조교를 당하고 싶다",
                "url": unrelated_url,
                "content": "레즈비언 웹소설 노벨피아",
                "query": "레즈비언 웹소설 노벨피아",
            }
        ]

        with patch.object(
            pipeline,
            "_fetch_and_attach_page_info",
            side_effect=AssertionError("identity-less generic URL must not be live-fetched"),
        ) as fetch:
            validated = pipeline._validate_heretic_url(unrelated_url, ctx)

        self.assertIsNone(validated)
        fetch.assert_not_called()

    def test_heretic_url_prefetch_keeps_direct_packet_official_url(self):
        pipeline = build_pipeline()
        selected_title = "재벌가 차녀의 2회차 걸그룹"
        direct_url = "https://novelpia.com/novel/100003"
        ctx = ConversationContext(
            post_id=11716480,
            post_data={
                "post_id": 11716480,
                "title": selected_title,
                "content_blocks": [
                    {"type": "text", "text": f"직접 링크 {direct_url}"}
                ],
            },
            comments=[],
        )
        ctx.search_results = []
        fetched = {
            "url": direct_url,
            "text_preview": selected_title,
            "structured_info": {
                "title": selected_title,
                "page_title": selected_title,
                "content_status": "active",
            },
        }

        with patch.object(
            pipeline,
            "_fetch_and_attach_page_info",
            return_value=fetched,
        ) as fetch:
            validated = pipeline._validate_heretic_url(
                direct_url,
                ctx,
                identified_title=selected_title,
            )

        self.assertEqual(validated, direct_url)
        fetch.assert_called_once_with(ctx, direct_url)

    def test_heretic_url_prefetch_keeps_direct_comment_official_url(self):
        pipeline = build_pipeline()
        selected_title = "재벌가 차녀의 2회차 걸그룹"
        direct_url = "https://novelpia.com/novel/100005"
        ctx = ConversationContext(
            post_id=11716480,
            post_data={
                "post_id": 11716480,
                "title": "댓글 링크 확인",
                "content_blocks": [{"type": "text", "text": "본문 링크 없음"}],
            },
            comments=[f"작품 링크 {direct_url}"],
        )
        ctx.search_results = []
        fetched = {
            "url": direct_url,
            "text_preview": selected_title,
            "structured_info": {
                "title": selected_title,
                "page_title": selected_title,
                "content_status": "active",
            },
        }

        with patch.object(
            pipeline,
            "_fetch_and_attach_page_info",
            return_value=fetched,
        ) as fetch:
            validated = pipeline._validate_heretic_url(
                direct_url,
                ctx,
                identified_title=selected_title,
            )

        self.assertEqual(validated, direct_url)
        fetch.assert_called_once_with(ctx, direct_url)

    def test_heretic_url_prefetch_keeps_exact_selected_title_search_evidence(self):
        pipeline = build_pipeline()
        selected_title = "재벌가 차녀의 2회차 걸그룹"
        candidate_url = "https://novelpia.com/novel/100006"
        ctx = ConversationContext(
            post_id=11716480,
            post_data={
                "post_id": 11716480,
                "title": "작품 URL 확인",
                "content_blocks": [{"type": "text", "text": "본문 링크 없음"}],
            },
            comments=[],
        )
        ctx.search_results = [
            {
                "title": f"{selected_title} - 노벨피아",
                "url": candidate_url,
                "content": "작가 유은우의 공식 작품 상세",
                "query": f'"{selected_title}" 노벨피아',
                "from_query": f'"{selected_title}" 노벨피아',
            }
        ]
        fetched = {
            "url": candidate_url,
            "text_preview": selected_title,
            "structured_info": {
                "title": selected_title,
                "page_title": selected_title,
                "content_status": "active",
            },
        }

        with patch.object(
            pipeline,
            "_fetch_and_attach_page_info",
            return_value=fetched,
        ) as fetch:
            validated = pipeline._validate_heretic_url(
                candidate_url,
                ctx,
                identified_title=selected_title,
            )

        self.assertEqual(validated, candidate_url)
        fetch.assert_called_once_with(ctx, candidate_url)

    def test_search_alias_inference_filters_munpia_brand_tail(self):
        pipeline = build_pipeline()

        candidates = pipeline._search_result_candidate_titles_for_alias_inference(
            {
                "title": "전지적 독자 시점 - 문피아 웹소설 - Munpia",
                "url": "https://novel.munpia.com/104753",
                "content": "전독시로 불리는 문피아 웹소설.",
            },
            pipeline._normalize_match_text("전독시"),
        )

        self.assertIn("전지적 독자 시점", candidates)
        self.assertNotIn("Munpia", candidates)

    def test_search_alias_inference_filters_novelpia_listing_label(self):
        pipeline = build_pipeline()

        candidates = pipeline._search_result_candidate_titles_for_alias_inference(
            {
                "title": "플러스작품 - 이 무림의 미친년은 나야 - 노벨피아",
                "url": "https://novelpia.com/novel/217943",
                "content": "무친년으로 불리는 노벨피아 무협 웹소설.",
            },
            pipeline._normalize_match_text("무친년"),
        )

        self.assertIn("이 무림의 미친년은 나야", candidates)
        self.assertNotIn("플러스작품", candidates)

    def test_title_led_gate_ignores_munpia_brand_tail_competitor(self):
        pipeline = build_pipeline()
        title = "전지적 독자 시점"
        url = "https://novel.munpia.com/104753"
        post = PostInput(
            post_id=11677915,
            title="내가 재밌게 본 거 별거 없다고 리뷰하면 화가남",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="이 새끼의 최애작품은 뭔지 알아내서"),
                ContentBlock(type="text", text="메차쿠차 비난하고 ntr하고 싶음"),
            ],
            comments=["응 느그 전독시 느그 배본블 ㅋ"],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=post.comments,
        )
        ctx.search_results = [
            {
                "title": f"{title} - 문피아 웹소설 - Munpia",
                "url": url,
                "content": f"전독시로 불리는 {title}. 싱숑 작가.",
                "query": "전독시 문피아",
                "source_tier": "official_detail",
            }
        ]
        final_decision = {
            "discussion_type": "meme",
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
        }
        vf_result = {
            "grounding_check": {
                "anchor_found": "title_abbrev_mention",
                "title_abbrev_mentioned": True,
                "matched_alias": "전독시",
            },
            "slang_insight": {
                "detected_term": "전독시",
                "decoded_term": title,
                "decode_verified": True,
                "alias_scope": "pure_work_alias",
            },
        }

        source_before = _baseline_source_snapshot(ctx)

        decision = pipeline._record_title_led_alias_public_title_gate_decision(
            ctx,
            title,
            candidate_url=url,
            final_decision=final_decision,
            verification_result=vf_result,
            title_candidates=[
                DetectedTitle(
                    official_title=title,
                    heretic_url=url,
                    confidence="High",
                    alias_or_mention="전독시",
                    source_tier="official_detail",
                    page_type="novel_page",
                )
            ],
            acceptance={"decision": "accept", "title_led_consumption_bridge": True, "score": 29},
        )

        _baseline_record_contract(self, ctx, decision, source_before, "munpia_original_source")

        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertIsNone(decision["official_title"])
        self.assertNotIn("title_led_alias_contextual_official_detail_competes", decision["reason_codes"])
        state = ctx._last_promotion_gate_state
        self.assertFalse(state["row_discusses_work_as_work"])
        self.assertEqual(state["scope"]["scope_kind"], "context_only")
        self.assertEqual(state["scope"]["competing_candidates"], [])

        self.assertIsNone(decision["official_url"])

        self.assertIn("shared_work_bridge_missing", state["scope"]["conflict_reason_codes"])
        self.assertEqual(state["candidate_title"], title)

    def test_title_led_gate_ignores_novelpia_listing_label_competitor(self):
        pipeline = build_pipeline()
        title = "이 무림의 미친년은 나야"
        url = "https://novelpia.com/novel/217943"
        post = PostInput(
            post_id=11682780,
            title="근데 무친년은 뭉청이 지금 화경 대원만인데 현경 찍으면 ㅆㅂㅋㅋ",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="십대마공이랑 북명신공 마스터하고"),
                ContentBlock(type="text", text="독고구검 체화해서 마스터하면"),
            ],
            comments=["무친년이 김용소설 영향 씨게 받아서 그런것도 있음"],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=post.comments,
        )
        ctx.search_results = [
            {
                "title": f"플러스작품 - {title} - 노벨피아",
                "url": url,
                "content": f"무친년으로 불리는 {title}. 무협 웹소설.",
                "query": "무친년 노벨피아",
                "source_tier": "official_detail",
            }
        ]
        final_decision = {
            "discussion_type": "general",
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
        }
        vf_result = {
            "grounding_check": {
                "anchor_found": "title_abbrev_mention",
                "title_abbrev_mentioned": True,
                "matched_alias": "무친년",
            },
            "slang_insight": {
                "detected_term": "무친년",
                "decoded_term": title,
                "decode_verified": True,
                "alias_scope": "pure_work_alias",
            },
        }

        decision = pipeline._record_title_led_alias_public_title_gate_decision(
            ctx,
            title,
            candidate_url=url,
            final_decision=final_decision,
            verification_result=vf_result,
            title_candidates=[
                DetectedTitle(
                    official_title=title,
                    heretic_url=url,
                    confidence="High",
                    alias_or_mention="무친년",
                    source_tier="official_detail",
                    page_type="novel_page",
                )
            ],
            acceptance={"decision": "accept", "title_led_consumption_bridge": True, "score": 29},
        )

        self.assertEqual(decision["status"], "publish")
        self.assertTrue(decision["publish_allowed"])
        self.assertEqual(decision["official_title"], title)
        self.assertNotIn("title_led_alias_contextual_official_detail_competes", decision["reason_codes"])
        state = ctx._last_promotion_gate_state
        self.assertTrue(state["row_discusses_work_as_work"])
        self.assertEqual(state["scope"]["scope_kind"], "current_work")
        self.assertEqual(state["scope"]["competing_candidates"], [])

    def test_sanitize_reason_neutralizes_code_guard_flip_marker_for_relevant_result(self):
        reason = (
            "[판정 요약]\n"
            "- 판정: 관련\n"
            "- discussion_type: general\n"
            "- 공식 제목: '전 버튜버가 하고 싶은데요'\n"
            "[근거 스코어]\n"
            "- title_resolution: +2 (공식 제목 근거 확인)\n"
            "[코드가드 consistency: LLM(False)→최종(True)]"
        )

        sanitized = AgenticPipeline._sanitize_reason(
            reason,
            is_relevant=True,
            discussion_type="general",
            official_title="전 버튜버가 하고 싶은데요",
        )

        self.assertIn("전 버튜버가 하고 싶은데요", sanitized)
        self.assertIn("[코드가드 consistency: 내부 정합성 가드 적용]", sanitized)
        self.assertNotIn("LLM(False)→최종(True)", sanitized)

    def test_snippet_artifact_title_expansion_blocks_cover_alias_mapping(self):
        self.assertTrue(is_snippet_artifact_title_expansion("테라포밍", "테라포밍 표지"))
        self.assertTrue(is_snippet_artifact_title_expansion("테라포밍", "테라포밍 팬아트"))
        self.assertFalse(
            is_snippet_artifact_title_expansion(
                "기계공주",
                "헌터갤러리의 국가권력급 기계공주",
            )
        )

    def test_orchestrator_skips_fanart_title_followup_and_fetch_hint(self):
        orchestrator = Orchestrator(experts={})
        search_results = [
            {
                "title": "테라포밍 표지 - 노벨피아",
                "url": "https://novelpia.com/fanart/all/view_816983/",
                "content": "출처: https://novelpia.com/novel/61947",
            }
        ]

        hints = orchestrator._extract_hints_from_snippets(search_results, ["테라포밍"])

        self.assertEqual(hints["fetchable_urls"], [])
        self.assertFalse(
            any(h.get("full") == "테라포밍 표지" for h in hints["abbreviation_hints"])
        )
        followups = orchestrator._extract_resolved_title_followup_queries(
            search_results,
            ["테라포밍"],
            {
                "post_type": "work_discussion",
                "detected_entities": {"possible_titles": ["테라포밍"]},
            },
            {
                "title_hints": [
                    {"title": "테라포밍 표지", "source": "llm_snippet"},
                ],
                "author_hints": [],
                "abbreviation_hints": [
                    {"abbrev": "테라포밍", "full": "테라포밍 표지", "source": "llm_snippet"},
                ],
            },
            {"identified_title": "테라포밍 표지"},
        )

        self.assertEqual(followups, [])

    def test_decoder_does_not_persist_snippet_artifact_mapping(self):
        ctx = ConversationContext(
            post_id=11660237,
            post_data={"post_id": 11660237, "title": "테라포밍 얘기"},
            comments=[],
        )
        ctx.snippet_hints = {
            "abbreviation_hints": [
                {
                    "abbrev": "테라포밍",
                    "full": "테라포밍 표지",
                    "source": "llm_snippet",
                }
            ]
        }
        decoder = DecoderExpert(
            JSONLLM(
                {
                    "decoded_terms": [],
                    "overall_confidence": "none",
                    "verification_search": [],
                    "unresolved_terms": ["테라포밍"],
                }
            )
        )

        decoder.analyze(
            {
                "_post_id": 11660237,
                "key_terms": ["테라포밍"],
                "detected_entities": {"possible_titles": ["테라포밍"]},
            },
            [],
            {},
            ctx=ctx,
        )

        self.assertEqual(getattr(ctx, "_resolved_mappings", []), [])

    def test_recommendation_comment_answers_are_preserved_as_candidates(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11706856,
            title="요세의 백합계의 슈퍼스타는 뭐임",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="알려다오 장붕")],
            comments=[
                "누드모드",
                "초 가구야 공주",
                "내가 연인이 될 수 있을리 없잔ㄴㅎ아 무리무리무리!(무리가 아니었다?!)재밌게봄",
                "너",
                "나",
                "@아이아\n제-하하하!!! 짤도 달릴수 있다고",
            ],
        )
        ctx = ConversationContext(post_id=11706856, post_data=pipeline._post_to_dict(post), comments=post.comments)

        candidates = pipeline._collect_local_candidate_preservation_hints(
            ctx=ctx,
            discussion_type="undecodable_reference",
        )
        titles = [cand.official_title for cand in candidates]

        self.assertIn("누드모드", titles)
        self.assertIn("초 가구야 공주", titles)
        self.assertIn("내가 연인이 될 수 있을리 없잔ㄴㅎ아 무리무리무리!(무리가 아니었다?!)", titles)
        self.assertNotIn("너", titles)
        self.assertNotIn("나", titles)
        self.assertTrue(all(cand.confidence == "Low" for cand in candidates))
        self.assertTrue(all("comment_answer_preservation_only" in (cand.negative_evidence or []) for cand in candidates[:3]))

    def test_reply_chain_slash_title_answers_are_preserved_without_single_promotion(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11716478,
            title="근친물은 무조건 1장녀 2작은누나 3여동생 공식이네",
            author="북부",
            content_blocks=[ContentBlock(type="text", text="항상 먼저 따먹히는건 만만한 작은누나고")],
            comments=[
                "2작품이 똑같이 가길래...",
                "@북부\n2개 제목 혹시 알려줄 수 있음?",
                "@ㅇㅇ2(220.94)\n가족친화적게임 / 엄마가 낳은 정실들",
            ],
        )
        ctx = ConversationContext(post_id=11716478, post_data=pipeline._post_to_dict(post), comments=post.comments)

        candidates = pipeline._collect_local_candidate_preservation_hints(
            ctx=ctx,
            discussion_type="recommendation",
        )
        titles = [cand.official_title for cand in candidates]

        self.assertIn("가족친화적게임", titles)
        self.assertIn("엄마가 낳은 정실들", titles)
        self.assertGreaterEqual(len(titles), 2)
        self.assertTrue(all(cand.reference_role == "candidate" for cand in candidates))

    def test_local_hold_candidate_snapshot_keeps_preservation_type(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11716478,
            title="근친물은 무조건 1장녀 2작은누나 3여동생 공식이네",
            author="북부",
            content_blocks=[ContentBlock(type="text", text="항상 먼저 따먹히는건 만만한 작은누나고")],
            comments=[
                "2작품이 똑같이 가길래...",
                "@북부\n2개 제목 혹시 알려줄 수 있음?",
                "@ㅇㅇ2(220.94)\n가족친화적게임 / 엄마가 낳은 정실들",
            ],
        )
        ctx = ConversationContext(post_id=11716478, post_data=pipeline._post_to_dict(post), comments=post.comments)
        candidates = pipeline._collect_local_candidate_preservation_hints(
            ctx=ctx,
            discussion_type="recommendation",
        )

        snapshot = pipeline._build_candidate_preservation_sources(
            title_candidates=[],
            mentioned_works=[],
            comparison_target=None,
            recommendation_candidates=candidates,
            secondary_reference_works=None,
        )

        by_title = {row["official_title"]: row for row in snapshot}
        self.assertEqual(by_title["가족친화적게임"]["preservation_role"], "recommendation_candidate")
        self.assertEqual(by_title["가족친화적게임"]["local_preservation_type"], "comment_answer_hold")
        self.assertEqual(by_title["가족친화적게임"]["promotion_policy"], "hold_without_promotion")
        self.assertIn("comment_answer_preservation_only", by_title["가족친화적게임"]["negative_evidence"])

    def test_platform_title_official_alias_candidate_is_skipped(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11660257,
            title="암흑가보스<<이거 재밋네",
            author="ㅇㅇ",
            content_blocks=[],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {"discourse_analysis": {"title_novel_terms": ["암흑가보스"]}},
        )
        ctx.search_results = [
            {
                "title": "노벨피아",
                "url": "https://novelpia.com/novel/301395",
                "content": "노벨피아 - 웹소설로 꿈꾸는 세상!",
            },
            {
                "title": "암흑가 보스요? 제가요?",
                "url": "https://novelpia.com/novel/384111",
                "content": "암흑가 보스요? 제가요? 작가명 손아픈사람.",
            },
        ]
        pipeline._has_batch_alias_verified_no_work_release_context = lambda *_args, **_kwargs: True
        pipeline._safe_official_detail_url_for_title = (
            lambda _ctx, *, title, candidate_url: candidate_url
        )
        pipeline._has_post_alias_official_detail_bridge_anchor = lambda *_args, **_kwargs: True
        pipeline._secondary_reference_deliberate_null_blocks_rescue = lambda *_args, **_kwargs: False

        candidate, hit = pipeline._search_results_official_alias_candidate(ctx)

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.official_title, "암흑가 보스요? 제가요?")
        self.assertEqual(candidate.heretic_url, "https://novelpia.com/novel/384111")
        self.assertEqual(hit["source"], "search_official_detail_alias")

    def test_blocked_search_alias_candidate_is_preserved_for_hold(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11660257,
            title="암흑가보스<<이거 재밋네",
            author="ㅇㅇ",
            content_blocks=[],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx._batch_alias_rescue_blocked_nonwork_context_reason = "genre_discussion_nonwork_context"
        ctx._batch_alias_rescue_blocked_nonwork_context_title = "암흑가 보스요? 제가요?"
        ctx._batch_alias_rescue_blocked_nonwork_context_alias = "암흑가보스"
        ctx._batch_alias_rescue_blocked_nonwork_context_source = "search_evidence_alias_inference"
        ctx._batch_alias_rescue_blocked_nonwork_context_url = "https://novelpia.com/novel/384111"

        candidates = pipeline._collect_local_candidate_preservation_hints(
            ctx=ctx,
            discussion_type="general",
        )
        snapshot = pipeline._build_candidate_preservation_sources(
            title_candidates=[],
            mentioned_works=[],
            comparison_target=None,
            recommendation_candidates=candidates,
            secondary_reference_works=None,
        )

        by_title = {row["official_title"]: row for row in snapshot}
        self.assertIn("암흑가 보스요? 제가요?", by_title)
        self.assertEqual(
            by_title["암흑가 보스요? 제가요?"]["heretic_url"],
            "https://novelpia.com/novel/384111",
        )
        self.assertEqual(by_title["암흑가 보스요? 제가요?"]["promotion_policy"], "hold_without_promotion")
        self.assertIn(
            "batch_alias_nonwork_context_hold_without_promotion",
            by_title["암흑가 보스요? 제가요?"]["negative_evidence"],
        )

    def test_rejected_search_alias_inference_candidate_is_pruned_from_hold_snapshot(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11698897,
            title="랫따싶 림월드 요소 생각나게 하는거 좋네에...",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="게임적 요소 있는거 아주 굿")],
            comments=["랫따싶 이거 참 잘쓴 패러디야"],
        )
        ctx = ConversationContext(post_id=11698897, post_data=pipeline._post_to_dict(post), comments=post.comments)
        ctx._batch_alias_rescue_blocked_precision_reason = "title_lead_relation_or_competition"
        ctx._batch_alias_rescue_blocked_precision_title = "스페이스 오페라"
        ctx._batch_alias_rescue_blocked_precision_source = "search_evidence_alias_inference"
        extended_identity = {"consistency_flags": ["weak_alias_surface_public_title_bridge"]}

        pruned = pipeline._prune_rejected_alias_inference_candidates_for_hold(
            ctx=ctx,
            title_candidates=[
                DetectedTitle(
                    official_title="랫따싶",
                    confidence="High",
                    alias_or_mention="랫따싶",
                    source_tier="mixed",
                    negative_evidence=["weak_alias_surface_public_title_bridge"],
                    reference_role="candidate",
                ),
                DetectedTitle(
                    official_title="스페이스 오페라",
                    heretic_url="https://novelpia.com/novel/181483",
                    confidence="High",
                    source_tier="mixed",
                    reference_role="primary",
                ),
            ],
            extended_identity=extended_identity,
        )
        snapshot = pipeline._build_candidate_preservation_sources(
            title_candidates=pruned,
            mentioned_works=[],
            comparison_target=None,
            recommendation_candidates=[],
            secondary_reference_works=None,
        )

        self.assertEqual([cand.official_title for cand in pruned], ["랫따싶"])
        self.assertEqual([row["official_title"] for row in snapshot], ["랫따싶"])
        self.assertIn("candidate_ledger_rejected_alias_inference_pruned", extended_identity["consistency_flags"])

    def test_short_and_compound_alias_hold_candidates_do_not_need_expected_title(self):
        pipeline = build_pipeline()
        short_post = PostInput(
            post_id=11697255,
            title="판초 무서우..",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="척추를 데드스페이스 리퍼로 상상하고 읽으니까 몰입이 심해졌어")
            ],
            comments=[],
        )
        short_ctx = ConversationContext(
            post_id=11697255,
            post_data=pipeline._post_to_dict(short_post),
            comments=[],
        )
        compound_post = PostInput(
            post_id=11703624,
            title="판초법사 경찰력 사용하면서도 1달 이상 정보통제가 가능함?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="전국 경찰력 다 동원하는데 소문이 안날수가 있나?")],
            comments=[],
        )
        compound_ctx = ConversationContext(
            post_id=11703624,
            post_data=pipeline._post_to_dict(compound_post),
            comments=[],
        )

        short_titles = [
            cand.official_title
            for cand in pipeline._collect_local_candidate_preservation_hints(
                ctx=short_ctx,
                discussion_type="noise",
            )
        ]
        compound_titles = [
            cand.official_title
            for cand in pipeline._collect_local_candidate_preservation_hints(
                ctx=compound_ctx,
                discussion_type="noise",
            )
        ]

        self.assertEqual(short_titles, ["판초"])
        self.assertEqual(compound_titles, ["판초법사"])

    def test_character_setting_cluster_is_held_but_common_names_are_not(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11702072,
            title="결국 호텔 전부깨도 위대한자 될 포텐은 한가인밖에 없지않나?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="넓게봐도 차진철 박승엽정도까지 같은데")],
            comments=[
                "혈통빨 대은솔도 되지 않을까",
                "상현이나 은솔까지 가능할듯",
                "포텐은 가인 은솔 승엽 정도만 가지고 있는듯 더쳐주면 진철?",
            ],
        )
        ctx = ConversationContext(post_id=11702072, post_data=pipeline._post_to_dict(post), comments=post.comments)
        common_post = PostInput(
            post_id=1,
            title="철수 영희 민수 오늘 밥먹음?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="그냥 학교 얘기")],
            comments=["영희도 가능할듯"],
        )
        common_ctx = ConversationContext(post_id=1, post_data=pipeline._post_to_dict(common_post), comments=common_post.comments)

        candidates = pipeline._collect_local_candidate_preservation_hints(
            ctx=ctx,
            discussion_type="undecodable_reference",
        )
        common_candidates = pipeline._collect_local_candidate_preservation_hints(
            ctx=common_ctx,
            discussion_type="undecodable_reference",
        )

        self.assertEqual(len(candidates), 1)
        self.assertIn("character_setting_cluster_hold_without_promotion", candidates[0].negative_evidence or [])
        self.assertEqual(common_candidates, [])

    def test_raw_search_with_meta_call_sites_stay_guarded(self):
        source_path = Path(__file__).resolve().parents[1] / "src" / "llm_batch" / "agentic_pipeline.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        parents = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent

        call_sites = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (
                isinstance(func, ast.Attribute)
                and func.attr == "_search_with_meta"
            ):
                continue

            parent = parents.get(node)
            function_name = None
            while parent is not None:
                if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    function_name = parent.name
                    break
                parent = parents.get(parent)
            call_sites.append((function_name, node.lineno))

        allowed_functions = {
            "_search",
            "_recover_corrected_title_official_url",
            "_run_image_ocr_platform_phrase_searches",
            "_run_title_alias_platform_searches",
        }
        self.assertEqual(
            sorted({name for name, _line in call_sites}),
            sorted(allowed_functions),
            msg=f"raw _search_with_meta call sites changed: {call_sites}",
        )

        recovery = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "_recover_corrected_title_official_url"
        )
        recovery_calls = {
            call.func.attr
            for call in ast.walk(recovery)
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
        }
        self.assertIn("_semantic_seed_no_work_signal", recovery_calls)
        self.assertIn(
            "_has_direct_post_or_visual_work_anchor_for_no_work_search_rescue",
            recovery_calls,
        )

    def test_no_work_seed_blocks_title_lead_search_inferred_candidate(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11718080,
            title="망겜힐은 밥먹을때 같이 볼 친구 있었으면",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(
                    type="text",
                    text="그냥 밥 먹는데 옆에서 같이 소설 얘기할 친구 있었으면 좋겠다는 한탄임",
                )
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=11718080, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.uncertainty_sources.append(
            "intent_permit_for_title_search=false(semantic_seed_review_not_specific_work)"
        )
        ctx.discourse_warning = "non_novel(gaming,high):short_alias_probe"
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "express_opinion",
                    "primary_domain": "gaming",
                    "domain_confidence": "high",
                    "target_kind": "none",
                    "title_novel_terms": ["가챠펑크"],
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "decoded_terms": [
                    {
                        "original": "망겜힐",
                        "best_match": {"title": "망겜의 힐러", "confidence": "Medium"},
                        "grounding": {"anchor_type": "title_mention"},
                    }
                ]
            },
        )
        ctx.canonical_title_lock = "망겜의 힐러"
        ctx.llm_snippet_analysis = {
            "identified_title": "망겜의 힐러",
            "abbreviation_mappings": [{"abbrev": "망겜힐", "full": "망겜의 힐러"}],
        }
        ctx.search_results = [
            {
                "title": "망겜의 힐러 - 네이버 시리즈",
                "url": "https://series.naver.com/novel/detail.series?productNo=7774",
                "content": "망겜힐 웹소설 작품 페이지. 장르 판타지. 작가 검미성.",
                "query": "망겜힐 웹소설",
            },
            {
                "title": "망겜의 힐러 - 리디",
                "url": "https://ridibooks.com/books/123",
                "content": "망겜힐 웹소설 작품 상세 리뷰. 작가 검미성.",
                "query": "망겜힐 웹소설",
            },
        ]

        self.assertEqual(pipeline._extract_post_title_lead_alias_terms(ctx), ["망겜힐"])
        self.assertTrue(pipeline._semantic_seed_no_work_signal(ctx))
        self.assertFalse(pipeline._has_title_lead_alias_search_work_support(ctx, "망겜의 힐러"))
        self.assertFalse(pipeline._has_search_evidence_alias_stability_signal(ctx, "망겜의 힐러"))
        self.assertFalse(pipeline._has_title_abbrev_stability_signal(ctx, "망겜의 힐러"))
        self.assertFalse(pipeline._has_snippet_canonical_alias_lock_support(ctx, "망겜의 힐러"))
        self.assertEqual(pipeline._build_title_lead_alias_search_inferred_candidates(ctx), [])

        acceptance = {
            "decision": "hold",
            "relation_type": "explicit_alias",
            "relation_target": "specific_work",
            "relation_promotion": "hold",
            "official_nonwiki_count": 1,
            "strong_body_grounding": True,
            "notes": ["stable_nickname_bridge"],
            "commitment": {"title_in_context": True, "decoder_strong": True},
        }
        rescue = {
            "strong": True,
            "official_ev": True,
            "title_in_context": True,
            "abbrev_stable": True,
        }
        self.assertFalse(
            pipeline._allow_stable_hold_canonical_rescue(
                ctx=ctx,
                title="망겜의 힐러",
                acceptance=acceptance,
                rescue=rescue,
                vf_result={},
            )
        )

    def test_semantic_no_work_signal_reads_arbiter_final_decision_from_context(self):
        pipeline = build_pipeline()
        title = "망겜의 힐러"
        post = PostInput(
            post_id=11718080,
            title="망겜힐 같이 볼 친구 있었으면",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="소설 자체보다 같이 볼 친구가 있으면 좋겠다는 잡담")],
            comments=[],
        )
        ctx = ConversationContext(post_id=11718080, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.set_expert_output(
            ExpertType.ARBITER,
            {
                "final_decision": {
                    "title_resolution_allowed": False,
                    "title_resolution_state": "context_only",
                    "_title_null_block_reasons": ["semantic_seed_review_guard"],
                }
            },
        )
        ctx.search_results = [
            {
                "title": "망겜의 힐러 - 네이버 시리즈",
                "url": "https://series.naver.com/novel/detail.series?productNo=7774",
                "content": "망겜의 힐러 웹소설 작품 페이지",
            }
        ]

        self.assertTrue(pipeline._semantic_seed_no_work_signal(ctx))
        self.assertFalse(
            pipeline._can_promote_title_after_semantic_no_work(
                ctx,
                title,
                source="unit_test_arbiter_final_decision",
                verification_result={"grounding_check": {"anchor_found": "search_only"}},
            )
        )

    def test_stable_hold_canonical_rescue_cannot_override_arbiter_context_only(self):
        pipeline = build_pipeline()
        title = "망겜의 힐러"
        post = PostInput(
            post_id=11718080,
            title="망겜힐 같이 볼 친구 있었으면",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="같이 소설 볼 친구가 있었으면 하는 생활 잡담")],
            comments=[],
        )
        ctx = ConversationContext(post_id=11718080, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.set_expert_output(
            ExpertType.ARBITER,
            {
                "final_decision": {
                    "title_resolution_allowed": False,
                    "title_resolution_state": "context_only",
                    "_title_null_block_reasons": ["semantic_seed_review_guard"],
                }
            },
        )
        acceptance = {
            "decision": "hold",
            "relation_type": "explicit_alias",
            "relation_target": "specific_work",
            "relation_promotion": "hold",
            "official_nonwiki_count": 1,
            "strong_body_grounding": True,
            "notes": ["stable_nickname_bridge"],
            "commitment": {"title_in_context": True, "decoder_strong": True},
        }
        rescue = {
            "strong": True,
            "official_ev": True,
            "title_in_context": True,
            "abbrev_stable": True,
        }

        self.assertFalse(
            pipeline._allow_stable_hold_canonical_rescue(
                ctx=ctx,
                title=title,
                acceptance=acceptance,
                rescue=rescue,
                vf_result={},
            )
        )

    def test_platform_meta_relation_reject_blocks_strongest_canonical_rescue(self):
        pipeline = build_pipeline()
        title = "전 버튜버가 하고 싶은데요"
        url = "https://novelpia.com/novel/275975"
        post = PostInput(
            post_id=11658668,
            title="문피아에서는 수정하면 욕 처먹는거고",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", url="https://example.test/11658668.png"),
                ContentBlock(type="text", text="여기서도 쿠사리 먹고 표지 내리면 소신있는거고"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=11658668, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.post_data["image_enrichment"] = [
            {
                "ocr_text": "ACTOR 아이, 탈의 주인공 전 버튜버가 하고 싶은데요",
                "visual_summary": "노란색 배경의 캐릭터 일러스트",
                "explicit_work_title": title,
                "evidence_type": "cover_title",
                "title_role": "unknown",
                "promotion_eligible": False,
                "work_cues": ["ACTOR", title, "아이, 탈의 주인공"],
            }
        ]

        verification_result = {
            "is_relevant": False,
            "relation_judgment": {
                "relation_type": "thematic_overlap_only",
                "discussion_target": "specific_work",
                "promotion_decision": "reject",
            },
            "grounding_check": {"anchor_found": "title_mention"},
            "counter_arguments": [
                {"severity": "critical", "reason": "본문이 플랫폼 메타 토론임"}
            ],
        }
        final_decision = {"_title_null_block_reasons": []}
        self.assertEqual(
            pipeline._should_block_title_promotion_for_meta_primary_subject(
                ctx=ctx,
                vf_result=verification_result,
                final_decision=final_decision,
            ),
            (True, "platform_release_meta"),
        )

        old_select = pipeline._select_best_canonical_rescue_candidate
        old_acceptance = pipeline._compute_title_acceptance
        old_url = pipeline._find_title_matched_official_url
        pipeline._select_best_canonical_rescue_candidate = lambda **_kwargs: {
            "title": title,
            "score": 24,
            "rescue": {
                "strong": True,
                "official_ev": True,
                "canonical_convergence": True,
                "alias_support": True,
                "bucket_score": 4,
                "search_hits": 14,
            },
        }
        pipeline._compute_title_acceptance = lambda *_args, **_kwargs: {
            "decision": "accept",
            "strong_body_grounding": True,
        }
        pipeline._find_title_matched_official_url = lambda *_args, **_kwargs: url

        try:
            fixed = pipeline._validate_final_identity_state(
                ctx=ctx,
                is_relevant=False,
                discussion_type="general",
                official_title=None,
                heretic_url=None,
                confidence="None",
                verification_result=verification_result,
                final_decision=final_decision,
                vf_anchor="title_mention",
                has_episode_ref=False,
                title_candidates=[],
            )
        finally:
            pipeline._select_best_canonical_rescue_candidate = old_select
            pipeline._compute_title_acceptance = old_acceptance
            pipeline._find_title_matched_official_url = old_url

        self.assertEqual(fixed, (False, "noise", None, None, "None"))
        self.assertTrue(getattr(ctx, "_platform_meta_relation_reject_canonical_rescue_blocked", False))
        self.assertIn(
            "platform_meta_relation_reject_canonical_rescue_blocked",
            final_decision["_title_null_block_reasons"],
        )

    def test_resolved_public_title_gate_blocks_image_ineligible_platform_meta_scope(self):
        pipeline = build_pipeline()
        title = "전 버튜버가 하고 싶은데요"
        url = "https://novelpia.com/novel/275975"
        post = PostInput(
            post_id=11658668,
            title="문피아에서는 수정하면 욕 처먹는거고",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", url="https://example.test/11658668.png"),
                ContentBlock(type="text", text="여기서도 쿠사리 먹고 내리면 소신있는거고"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=11658668, post_data=pipeline._post_to_dict(post), comments=[])
        image_item = {
            "ocr_text": "ACTOR 아이, 탈의 주인공 전 버튜버가 하고 싶은데요",
            "visual_summary": "노란색 배경의 캐릭터 일러스트",
            "explicit_work_title": title,
            "evidence_type": "cover_title",
            "title_role": "unknown",
            "promotion_eligible": False,
            "work_cues": ["ACTOR", title, "아이, 탈의 주인공"],
        }
        ctx.post_data["image_enrichment"] = [image_item]
        ctx.verified_character_work_links = [
            {
                "title": title,
                "character": "주서연",
                "url": url,
            }
        ]
        ctx.search_results = [
            {
                "title": title,
                "url": url,
                "content": "노벨피아 공식 작품 상세",
            }
        ]
        final_decision = {
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "review",
            "context_sources": ["title", "body", "search", "image"],
            "anchor_type": "image",
            "image_evidence_catalog": [image_item],
        }

        decision = pipeline._record_resolved_public_title_gate_decision(
            ctx,
            title,
            candidate_url=url,
            final_decision=final_decision,
            verification_result={
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
            },
            source="serialized_public_identity",
        )

        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertTrue(decision["candidate_preserved"])
        self.assertIn("scope_context_only", decision["reason_codes"])
        self.assertIn("scope_not_current_work", decision["reason_codes"])
        self.assertIn("image_title_not_promotion_eligible", decision["reason_codes"])
        self.assertEqual(final_decision["_promotion_gate_state"]["scope"]["scope_kind"], "context_only")

    def test_resolved_public_title_gate_keeps_platform_meta_image_hold_when_title_seen(self):
        pipeline = build_pipeline()
        title = "전 버튜버가 하고 싶은데요"
        url = "https://novelpia.com/novel/275975"
        post = PostInput(
            post_id=11658668,
            title="문피아에서는 수정하면 욕 처먹는거고",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", url="https://example.test/11658668.png"),
                ContentBlock(type="text", text="여기서도 쿠사리 먹고 내리면 소신있는거고"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=11658668, post_data=pipeline._post_to_dict(post), comments=[])
        image_item = {
            "ocr_text": "ACTOR 아이, 탈의 주인공 전 버튜버가 하고 싶은데요",
            "visual_summary": "노란색 배경의 캐릭터 일러스트",
            "explicit_work_title": title,
            "evidence_type": "cover_title",
            "title_role": "unknown",
            "promotion_eligible": False,
            "work_cues": ["ACTOR", title, "아이, 탈의 주인공"],
        }
        ctx.post_data["image_enrichment"] = [image_item]
        ctx.search_results = [
            {
                "title": title,
                "url": url,
                "content": "노벨피아 공식 작품 상세",
            }
        ]
        final_decision = {
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "review",
            "context_sources": ["title", "body", "search", "image"],
            "anchor_type": "image",
            "consistency_flags": ["platform_meta_multi_title_blocked"],
            "image_evidence_catalog": [image_item],
        }
        old_visible = pipeline._title_mentioned_in_non_image_main_context
        pipeline._title_mentioned_in_non_image_main_context = lambda *_args, **_kwargs: True
        try:
            decision = pipeline._record_resolved_public_title_gate_decision(
                ctx,
                title,
                candidate_url=url,
                final_decision=final_decision,
                verification_result={
                    "title_resolution_allowed": True,
                    "title_resolution_state": "resolved",
                    "work_resolution": "resolved",
                },
                source="serialized_public_identity",
            )
        finally:
            pipeline._title_mentioned_in_non_image_main_context = old_visible

        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertIn("image_title_not_promotion_eligible", decision["reason_codes"])
        self.assertIn("platform_meta_multi_title_blocked", decision["reason_codes"])
        self.assertEqual(final_decision["_promotion_gate_state"]["scope"]["scope_kind"], "context_only")

    def test_batch_alias_semantic_no_work_respects_platform_meta_image_hold(self):
        pipeline = build_pipeline()
        title = "전 버튜버가 하고 싶은데요"
        url = "https://novelpia.com/novel/275975"
        post = PostInput(
            post_id=11658668,
            title="문피아에서는 수정하면 욕 처먹는거고",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", url="https://example.test/11658668.png"),
                ContentBlock(type="text", text="여기서도 쿠사리 먹고 내리면 소신있는거고"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=11658668, post_data=pipeline._post_to_dict(post), comments=[])
        image_item = {
            "ocr_text": "ACTOR ...의 주인공 전 버튜버가 하고 싶은데요",
            "visual_summary": "노란색 배경의 캐릭터 표지",
            "explicit_work_title": title,
            "evidence_type": "cover_title",
            "title_role": "unknown",
            "promotion_eligible": False,
            "work_cues": [title, "ACTOR"],
        }
        ctx.post_data["image_enrichment"] = [image_item]
        ctx.search_results = [
            {
                "title": title,
                "url": url,
                "content": "노벨피아 공식 작품 상세",
            }
        ]
        final_decision = {
            "title_resolution_allowed": False,
            "title_resolution_state": "context_only",
            "work_resolution": "unresolved",
            "image_evidence_catalog": [image_item],
        }

        old_detail_urls = pipeline._official_detail_exact_title_urls_for_no_work_anchor
        old_find_url = pipeline._find_title_matched_official_url
        old_official_evidence = pipeline._has_official_title_evidence
        pipeline._has_official_title_evidence = lambda *_args, **_kwargs: True
        pipeline._official_detail_exact_title_urls_for_no_work_anchor = lambda *_args, **_kwargs: [url]
        pipeline._find_title_matched_official_url = lambda *_args, **_kwargs: url
        try:
            allowed = pipeline._can_promote_title_after_semantic_no_work(
                ctx,
                title,
                source="batch_memory_exact_alias_rescued",
                final_decision=final_decision,
                verification_result={},
                title_candidates=[],
            )
        finally:
            pipeline._has_official_title_evidence = old_official_evidence
            pipeline._official_detail_exact_title_urls_for_no_work_anchor = old_detail_urls
            pipeline._find_title_matched_official_url = old_find_url

        self.assertFalse(allowed)
        decision = final_decision["_promotion_gate_decision"]
        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertIn("platform_meta_image_title_hard_hold", decision["reason_codes"])
        self.assertIn("scope_context_only", decision["reason_codes"])
        self.assertEqual(final_decision["_promotion_gate_state"]["scope"]["scope_kind"], "context_only")
        self.assertFalse(
            pipeline._post_discusses_work_as_work(
                ctx,
                title,
                source="batch_memory_exact_alias_rescued",
                final_decision=final_decision,
                verification_result={},
            )
        )

    def test_batch_alias_semantic_no_work_blocks_platform_meta_ocr_text_without_catalog(self):
        pipeline = build_pipeline()
        title = "전 버튜버가 하고 싶은데요"
        url = "https://novelpia.com/novel/275975"
        post = PostInput(
            post_id=11658668,
            title="문피아에서는 수정하면 욕 처먹는거고",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", url="https://example.test/11658668.png"),
                ContentBlock(type="ocr_text", text="ACTOR ...의 주인공 전 버튜버가 하고 싶은데요"),
                ContentBlock(type="text", text="여기서도 쿠사리 먹고 내리면 소신있는거고"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=11658668, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.search_results = [
            {
                "title": title,
                "url": url,
                "content": "노벨피아 공식 작품 상세",
            }
        ]
        final_decision = {
            "title_resolution_allowed": False,
            "title_resolution_state": "context_only",
            "work_resolution": "unresolved",
        }

        old_detail_urls = pipeline._official_detail_exact_title_urls_for_no_work_anchor
        old_find_url = pipeline._find_title_matched_official_url
        old_official_evidence = pipeline._has_official_title_evidence
        pipeline._has_official_title_evidence = lambda *_args, **_kwargs: True
        pipeline._official_detail_exact_title_urls_for_no_work_anchor = lambda *_args, **_kwargs: [url]
        pipeline._find_title_matched_official_url = lambda *_args, **_kwargs: url
        try:
            allowed = pipeline._can_promote_title_after_semantic_no_work(
                ctx,
                title,
                source="batch_memory_exact_alias_rescued",
                final_decision=final_decision,
                verification_result={},
                title_candidates=[],
            )
        finally:
            pipeline._has_official_title_evidence = old_official_evidence
            pipeline._official_detail_exact_title_urls_for_no_work_anchor = old_detail_urls
            pipeline._find_title_matched_official_url = old_find_url

        self.assertFalse(allowed)
        decision = final_decision["_promotion_gate_decision"]
        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertIn("platform_meta_image_title_hard_hold", decision["reason_codes"])
        self.assertIn("scope_context_only", decision["reason_codes"])

    def test_batch_alias_semantic_no_work_blocks_low_specificity_alias_after_relation_hold(self):
        pipeline = build_pipeline()
        title = "SSS급 죽어야 사는 헌터"
        url = "https://series.naver.com/novel/detail.series?productNo=3962389"
        post = PostInput(
            post_id=11713212,
            title="지력 무한일 때 가장 효과 좋은 작물이 머임",
            author="메타쨩",
            content_blocks=[
                ContentBlock(
                    type="text",
                    text="절대 SSS급 지력무한 영지를 손에 넣었다 를 쓰려는 건 아니고",
                )
            ],
            comments=["옥수수가 깡패 아닌가", "귀농물은 한번두 안바서.."],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        mark_no_work_seed(ctx)
        ctx.search_results = [
            {
                "title": title,
                "url": url,
                "content": f"{title} 작품 상세. 가장 alias candidate.",
                "query": "SSS급 지력무한 영지를 손에 넣었다",
            }
        ]
        final_decision = {
            "title_resolution_allowed": False,
            "title_resolution_state": "context_only",
            "work_resolution": "unresolved",
            "_title_deliberately_null": True,
            "consistency_flags": [
                "official_url_recall_blocked_relation_non_work_context",
                "batch_memory_alias_rescue_blocked_deliberate_null",
            ],
        }
        verification_result = {
            "title_resolution_allowed": False,
            "title_resolution_state": "context_only",
            "work_resolution": "unresolved",
            "relation_judgment": {
                "relation_type": "thematic_overlap_only",
                "discussion_target": "genre_general",
                "promotion_decision": "reject",
            },
            "counter_arguments": [
                {
                    "severity": "critical",
                    "issue": "본문의 예시 문구는 특정 작품 토론이 아니라 부정된 설정 가정입니다.",
                }
            ],
        }
        title_candidates = [
            DetectedTitle(
                official_title=title,
                heretic_url=url,
                confidence="Medium",
                alias_or_mention="가장",
                source_tier="official_detail",
                reference_role="primary",
            )
        ]

        old_release_context = pipeline._has_batch_alias_verified_no_work_release_context
        pipeline._has_batch_alias_verified_no_work_release_context = lambda *_args, **_kwargs: True
        try:
            self.assertFalse(
                pipeline._has_post_alias_official_detail_bridge_anchor(
                    ctx,
                    title,
                    alias_text="가장",
                )
            )
            allowed = pipeline._can_promote_title_after_semantic_no_work(
                ctx,
                title,
                source="batch_memory_exact_alias_rescued",
                final_decision=final_decision,
                verification_result=verification_result,
                title_candidates=title_candidates,
            )
        finally:
            pipeline._has_batch_alias_verified_no_work_release_context = old_release_context

        self.assertFalse(allowed)
        decision = final_decision["_promotion_gate_decision"]
        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertIn("row_discussion_missing", decision["reason_codes"])
        self.assertIn("scope_context_only", decision["reason_codes"])
        self.assertIn("low_specificity_alias_nonwork_context", decision["reason_codes"])

    def test_final_semantic_guard_does_not_keep_low_specificity_alias_relation_hold(self):
        pipeline = build_pipeline()
        title = "SSS급 죽어야 사는 헌터"
        url = "https://series.naver.com/novel/detail.series?productNo=3962389"
        post = PostInput(
            post_id=11713212,
            title="지력 무한일 때 가장 효과 좋은 작물이 머임",
            author="메타쨩",
            content_blocks=[
                ContentBlock(
                    type="text",
                    text="절대 SSS급 지력무한 영지를 손에 넣었다 를 쓰려는 건 아니고",
                )
            ],
            comments=["옥수수가 깡패 아닌가"],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        ctx.search_results = [
            {
                "title": title,
                "url": url,
                "content": f"{title} 작품 상세. 가장 alias candidate.",
                "query": "SSS급 지력무한 영지를 손에 넣었다",
            }
        ]
        flags = [
            "official_url_recall_gate_recovered",
            "post_alias_official_detail_bridge_anchor",
            "confirmed_alias:가장",
            "official_url_recall_blocked_relation_non_work_context",
            "batch_memory_alias_rescue_blocked_after_title_deliberately_null",
        ]

        old_release_context = pipeline._has_batch_alias_verified_no_work_release_context
        pipeline._has_batch_alias_verified_no_work_release_context = lambda *_args, **_kwargs: True
        try:
            keep = pipeline._should_keep_final_semantic_resolution_after_official_recall_anchor(
                ctx=ctx,
                official_title=title,
                verification_result={
                    "relation_judgment": {
                        "relation_type": "thematic_overlap_only",
                        "discussion_target": "genre_general",
                        "promotion_decision": "reject",
                    },
                    "counter_arguments": [{"severity": "critical", "issue": "specific work not discussed"}],
                },
                title_candidates=[
                    DetectedTitle(
                        official_title=title,
                        heretic_url=url,
                        confidence="Medium",
                        alias_or_mention="가장",
                        source_tier="official_detail",
                        reference_role="primary",
                    )
                ],
                consistency_flags=flags,
            )
        finally:
            pipeline._has_batch_alias_verified_no_work_release_context = old_release_context

        self.assertFalse(keep)

    def test_verified_contextual_alias_wrapper_uses_shared_work_predicate(self):
        pipeline = build_pipeline()
        ctx = ConversationContext(
            post_id=11600000,
            post_data={"post_id": 11600000, "title": "별칭 얘기"},
            comments=[],
        )
        calls = {}
        old_predicate = pipeline._post_discusses_work_as_work

        def fake_predicate(*args, **kwargs):
            calls["args"] = args
            calls["kwargs"] = kwargs
            return True

        pipeline._post_discusses_work_as_work = fake_predicate
        try:
            self.assertTrue(
                pipeline._has_verified_contextual_alias_work_bridge(
                    ctx,
                    "테스트 작품",
                    {"relation_judgment": {"relation_type": "explicit_alias"}},
                )
            )
        finally:
            pipeline._post_discusses_work_as_work = old_predicate

        self.assertEqual(calls["args"][1], "테스트 작품")
        self.assertEqual(calls["kwargs"]["source"], "verified_contextual_alias_work_bridge")

    def test_resolved_public_title_scope_blocks_character_collision_alias_variant(self):
        pipeline = build_pipeline()
        title = "조선 퇴마록"
        url = "https://m.munpia.com/novel/detail/424777"
        post = PostInput(
            post_id=11663535,
            title="퇴마록에 온갖 능력 다나오네 생각해보니",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(
                    type="text",
                    text=(
                        "박신부 - 신성 오오라, 예수 만남\n"
                        "이현암 - 무협캐릭터, 부동심결, 월향검, 청홍검 사용\n"
                        "승희 - 신의 아바타\n"
                        "장준후 - 주술, 술법캐"
                    ),
                )
            ],
            comments=["괜히 그시절 goat이 아니지", "도서관 죽치고 앉아있었을 듯"],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        ctx.search_results = [
            {
                "title": "조선 퇴마록 - 문피아 웹소설",
                "url": url,
                "content": "조선 퇴마록 작품 상세 페이지",
            }
        ]
        final_decision = {
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "review",
            "context_sources": ["title", "body", "comments", "search"],
            "anchor_type": "title_alias",
        }
        verification_result = {
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "grounding_check": {
                "anchor_found": "character_mention",
                "anchor_text": "박신부, 이현암, 승희, 장준후",
            },
            "counter_arguments": [
                {
                    "issue": "character_title_collision",
                    "severity": "major",
                    "action": "nullify_title",
                    "explanation": "short title + 캐릭터 언급 충돌 패턴",
                }
            ],
        }

        decision = pipeline._record_resolved_public_title_gate_decision(
            ctx,
            title,
            candidate_url=url,
            final_decision=final_decision,
            verification_result=verification_result,
            source="serialized_public_identity",
        )

        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertTrue(decision["candidate_preserved"])
        self.assertIn("scope_context_only", decision["reason_codes"])
        self.assertIn("character_title_collision", decision["reason_codes"])
        self.assertIn("missing_direct_candidate_title", decision["reason_codes"])
        self.assertEqual(final_decision["_promotion_gate_state"]["scope"]["scope_kind"], "context_only")

    def test_resolved_public_title_scope_blocks_unpreserved_body_compound_character_anchor(self):
        pipeline = build_pipeline()
        title = "아카데미 생존 갤러리"
        url = "https://novelpia.com/novel/380218"
        post = PostInput(
            post_id=11698880,
            title="아생갤 개 존나게 재밌군 ㅇㅇ",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="가챠펑크 세드릭도 그렇고"),
                ContentBlock(type="text", text="이런게 아닌 시원시원한 상남자라서 좋구나"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.search_results = [{"title": "아카데미 생존 갤러리", "url": url, "content": "아생갤 작품 상세"}]
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "decoded_terms": [
                    {
                        "original": "아생갤",
                        "best_match": {"title": title, "confidence": "high"},
                    },
                    {
                        "original": "가챠펑크 세드릭",
                        "morphehens": ["가챠펑크", "세드릭"],
                        "interpretations": [{"type": "character_name", "value": "세드릭"}],
                        "best_match": {"title": None, "confidence": "none"},
                    },
                ]
            },
        )
        final_decision = {
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "context_sources": ["title", "body", "search", "image"],
            "anchor_type": "title_exact",
            "entity_mentions": [
                {
                    "text": "가챠펑크 세드릭",
                    "entity_type": "character",
                    "canonical_value": None,
                    "source": "decoder",
                    "role": "character_focus",
                }
            ],
        }
        verification_result = {
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "grounding_check": {"anchor_found": "title_mention", "matched_alias": "아생갤"},
        }

        decision = pipeline._record_resolved_public_title_gate_decision(
            ctx,
            title,
            candidate_url=url,
            final_decision=final_decision,
            verification_result=verification_result,
            title_candidates=[
                DetectedTitle(
                    official_title=title,
                    heretic_url=url,
                    confidence="High",
                    alias_or_mention="아생갤",
                    source_tier="official_detail",
                    page_type="novel_page",
                    reference_role="primary",
                )
            ],
            source="serialized_public_identity",
        )

        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertIn("scope_context_only", decision["reason_codes"])
        self.assertIn("unresolved_body_character_work_anchor", decision["reason_codes"])
        self.assertIn("missing_body_work_bridge", decision["reason_codes"])
        scope = final_decision["_promotion_gate_state"]["scope"]
        self.assertEqual(scope["scope_kind"], "context_only")
        self.assertIn("unresolved_body_character_work_anchor", scope["conflict_reason_codes"])

    def test_resolved_public_title_scope_allows_body_compound_when_current_alias_is_in_body(self):
        pipeline = build_pipeline()
        title = "아카데미 생존 갤러리"
        url = "https://novelpia.com/novel/380218"
        post = PostInput(
            post_id=11698881,
            title="아생갤 개 존나게 재밌군 ㅇㅇ",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="아생갤 아레스도 그렇고"),
                ContentBlock(type="text", text="이번화 주인공 성격이 좋구나"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.search_results = [{"title": "아카데미 생존 갤러리", "url": url, "content": "아생갤 작품 상세"}]
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "decoded_terms": [
                    {
                        "original": "아생갤",
                        "best_match": {"title": title, "confidence": "high"},
                    },
                    {
                        "original": "아생갤 아레스",
                        "morphehens": ["아생갤", "아레스"],
                        "interpretations": [{"type": "character_name", "value": "아레스"}],
                        "best_match": {"title": None, "confidence": "none"},
                    },
                ]
            },
        )
        final_decision = {
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "context_sources": ["title", "body", "search"],
            "anchor_type": "title_exact",
        }

        decision = pipeline._record_resolved_public_title_gate_decision(
            ctx,
            title,
            candidate_url=url,
            final_decision=final_decision,
            verification_result={
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "grounding_check": {"anchor_found": "title_mention", "matched_alias": "아생갤"},
            },
            title_candidates=[
                DetectedTitle(
                    official_title=title,
                    heretic_url=url,
                    confidence="High",
                    alias_or_mention="아생갤",
                    source_tier="official_detail",
                    page_type="novel_page",
                    reference_role="primary",
                )
            ],
            source="serialized_public_identity",
        )

        self.assertEqual(decision["status"], "publish")
        self.assertTrue(decision["publish_allowed"])
        self.assertNotIn("unresolved_body_character_work_anchor", decision["reason_codes"])
        self.assertEqual(final_decision["_promotion_gate_state"]["scope"]["scope_kind"], "current_work")

    def test_resolved_public_title_scope_allows_character_collision_when_candidate_title_is_direct(self):
        pipeline = build_pipeline()
        title = "조선 퇴마록"
        url = "https://m.munpia.com/novel/detail/424777"
        post = PostInput(
            post_id=11663535,
            title="조선 퇴마록에 온갖 능력 다나오네 생각해보니",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="박신부랑 이현암 설정 이야기")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.search_results = [{"title": "조선 퇴마록 - 문피아 웹소설", "url": url, "content": "작품 상세"}]
        final_decision = {
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "review",
            "context_sources": ["title", "body", "search"],
            "anchor_type": "title_alias",
        }
        verification_result = {
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "grounding_check": {"anchor_found": "character_mention"},
            "counter_arguments": [
                {
                    "issue": "character_title_collision",
                    "severity": "major",
                    "action": "nullify_title",
                }
            ],
        }

        decision = pipeline._record_resolved_public_title_gate_decision(
            ctx,
            title,
            candidate_url=url,
            final_decision=final_decision,
            verification_result=verification_result,
            source="serialized_public_identity",
        )

        self.assertEqual(decision["status"], "publish")
        self.assertTrue(decision["publish_allowed"])
        self.assertNotIn("character_title_collision", decision["reason_codes"])
        self.assertEqual(final_decision["_promotion_gate_state"]["scope"]["scope_kind"], "current_work")

    def test_resolved_public_title_scope_blocks_direct_competing_official_surface(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11713222,
            title="현대 하렘물은 진짜 잘쓰는 작가가 손에꼽네",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="판타지만 쓰던 작가라서 그런가")],
            comments=["그렇네 잘생인편 안봐서 까먹어버림"],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        final_decision = {
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "review",
            "context_sources": ["title", "body", "comments", "search"],
            "anchor_type": "title_exact",
        }
        title_candidates = [
            DetectedTitle(
                official_title="잘생기면 편해지는 인방 생활",
                heretic_url="https://novelpia.com/novel/384016",
                confidence="High",
                alias_or_mention="잘생인방",
                source_tier="official_detail",
                page_type="novel_page",
                reference_role="primary",
            ),
            DetectedTitle(
                official_title="잘생기면 인생이 편하다",
                heretic_url="https://novelpia.com/novel/300042",
                confidence="High",
                alias_or_mention="잘생인편",
                source_tier="official_detail",
                page_type="novel_page",
                reference_role="candidate",
            ),
        ]

        decision = pipeline._record_resolved_public_title_gate_decision(
            ctx,
            "잘생기면 편해지는 인방 생활",
            candidate_url="https://novelpia.com/novel/384016",
            final_decision=final_decision,
            verification_result={
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
            },
            title_candidates=title_candidates,
            source="serialized_public_identity",
        )

        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertIn("scope_context_only", decision["reason_codes"])
        self.assertIn("direct_competing_work_surface", decision["reason_codes"])
        scope = final_decision["_promotion_gate_state"]["scope"]
        self.assertEqual(scope["scope_kind"], "context_only")
        self.assertIn("잘생기면 인생이 편하다", scope["competing_candidates"])

    def test_resolved_public_title_scope_blocks_image_search_only_candidate_without_surface(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11700470,
            title="어케 주인공 죄목이",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", url="https://example.invalid/panel.png"),
                ContentBlock(type="text", text="교수형 가스라이팅 같은 죄목만 보임"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        final_decision = {
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "context_sources": ["title", "body", "search", "image"],
            "anchor_type": "title_alias",
        }

        decision = pipeline._record_resolved_public_title_gate_decision(
            ctx,
            "세계 최강 미소녀에게 납치당했습니다",
            candidate_url="https://novelpia.com/novel/201411",
            final_decision=final_decision,
            verification_result={
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "grounding_check": {"anchor_found": "plot_mention"},
            },
            title_candidates=[
                DetectedTitle(
                    official_title="세계 최강 미소녀에게 납치당했습니다",
                    heretic_url="https://novelpia.com/novel/201411",
                    confidence="High",
                    alias_or_mention="납치 미소녀",
                    source_tier="official_detail",
                    page_type="novel_page",
                    reference_role="primary",
                )
            ],
            source="serialized_public_identity",
        )

        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertIn("scope_context_only", decision["reason_codes"])
        self.assertIn("image_scope_missing_candidate_surface", decision["reason_codes"])
        self.assertEqual(final_decision["_promotion_gate_state"]["scope"]["scope_kind"], "context_only")

    def test_late_title_rescue_paths_share_semantic_no_work_gate(self):
        source_path = Path(__file__).resolve().parents[1] / "src" / "llm_batch" / "agentic_pipeline.py"
        source = source_path.read_text(encoding="utf-8")

        expected_sources = [
            "structural_title_rescued",
            "question_title_official_match_recovered",
            "locked_official_candidate_rescued",
            "direct_full_title_candidate_rescued",
            "title_surface_primary_candidate_rescued",
            "short_support_anticipation_recovered",
            "short_alias_spoiler_recovered",
            "generic_relation_alias_rescued",
            "comment_title_answer_recovered",
            "comment_url_answer_recovered",
            "comment_plot_answer_recovered",
            "character_parenthetical_title_resolved",
            "character_page_title_resolved",
            "multi_work_placeholder_collapsed",
            "canonical_relevance_lock_rescued",
            "post_main_official_url_title_recovered_from_null",
            "direct_image_explicit_title_rescued",
            "batch_memory_exact_alias_rescued",
        ]
        for source_label in expected_sources:
            matches = list(re.finditer(rf'source="{re.escape(source_label)}"', source))
            self.assertTrue(matches, msg=f"missing semantic no-work gate source={source_label}")
            blocks = [
                source[max(0, match.start() - 320): match.end() + 420]
                for match in matches
            ]
            self.assertTrue(
                any(
                    "_can_promote_title_after_semantic_no_work" in block
                    or "_post_discusses_work_as_work" in block
                    for block in blocks
                ),
                msg=f"source={source_label} bypasses the shared work predicate",
            )
        semantic_gate_start = source.index("def _can_promote_title_after_semantic_no_work")
        semantic_gate = source[semantic_gate_start: semantic_gate_start + 50000]
        self.assertIn("_post_discusses_work_as_work", semantic_gate)

    def test_positive_work_seed_still_allows_title_lead_search_inferred_candidate(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11718097,
            title="망겜힐은 오행복 박태양이 빌런이어야돼",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="박태양과 ts녀, 족장님 관련 전개를 비평함")],
            comments=[],
        )
        ctx = ConversationContext(post_id=11718097, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.canonical_title_lock = "망겜의 힐러"
        ctx.llm_snippet_analysis = {
            "identified_title": "망겜의 힐러",
            "abbreviation_mappings": [{"abbrev": "망겜힐", "full": "망겜의 힐러"}],
        }
        ctx.search_results = [
            {
                "title": "망겜의 힐러 - 네이버 시리즈",
                "url": "https://series.naver.com/novel/detail.series?productNo=7774",
                "content": "망겜힐 웹소설 작품 페이지. 장르 판타지. 작가 검미성.",
                "query": "망겜힐 웹소설",
            },
            {
                "title": "망겜의 힐러 - 리디",
                "url": "https://ridibooks.com/books/123",
                "content": "망겜힐 웹소설 작품 상세 리뷰. 작가 검미성.",
                "query": "망겜힐 웹소설",
            },
        ]

        candidates = pipeline._build_title_lead_alias_search_inferred_candidates(ctx)

        self.assertTrue(pipeline._has_title_lead_alias_search_work_support(ctx, "망겜의 힐러"))
        self.assertTrue(pipeline._has_search_evidence_alias_stability_signal(ctx, "망겜의 힐러"))
        self.assertTrue(pipeline._has_snippet_canonical_alias_lock_support(ctx, "망겜의 힐러"))
        self.assertEqual([candidate.official_title for candidate in candidates], ["망겜의 힐러"])
        self.assertEqual(candidates[0].alias_or_mention, "망겜힐")

    def test_serializer_mismatch_preserves_contextual_official_alias_candidate_without_publish(self):
        pipeline = build_pipeline()
        alias = "랫테스트"
        contextual_title = "[행성건설]원조 생존 패러디"
        boundary_title = "후속 생쥐 작품"
        post = PostInput(
            post_id=20018097,
            title=f"{alias} 행성건설 요소가 좋음",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="제작과 생존 장면을 읽고 감상함"),
                ContentBlock(type="ocr_text", text="행성건설 방어 건물 제작 도구"),
            ],
            comments=[],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=[f"{alias} 원조 패러디가 잘 썼음"],
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "discuss_work",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "title_novel_terms": [alias],
                }
            },
        )
        ctx.llm_snippet_analysis = {
            "identified_title": contextual_title,
            "abbreviation_mappings": [{"abbrev": alias, "full": contextual_title}],
        }
        ctx.search_results = [
            {
                "title": f"웹소설로 꿈꾸는 세상! - {contextual_title}",
                "url": "https://novelpia.com/novel/910001",
                "content": f"#패러디 #행성건설 #{alias} 웹소설 작품 작가 완결",
                "query": f"{alias} 노벨피아",
            },
            {
                "title": f"웹소설로 꿈꾸는 세상! - {boundary_title} - 노벨피아",
                "url": "https://novelpia.com/novel/910002",
                "content": f"#전생 #제작 #갤러리 #{alias} 웹소설 작품",
                "query": f"{alias} 노벨피아",
            },
            {
                "title": f"(리뷰) [{alias}]원조 생존 패러디 완결 리뷰 - 갤러리",
                "url": "https://gall.dcinside.com/mgallery/board/view/?id=example&no=1",
                "content": f"{alias} 원조 생존 패러디 완결 리뷰 웹소설 작품",
                "query": f"{alias} 노벨피아",
            },
        ]
        prior = evaluate_publish_contract(
            GroundingState(
                post_id=post.post_id,
                candidate_title="이전 typed 후보",
                candidate_url="https://novelpia.com/novel/910000",
                official_title_exists=True,
                row_discusses_work_as_work=False,
            ),
            [],
        )
        existing = [
            DetectedTitle(
                official_title=boundary_title,
                heretic_url="https://novelpia.com/novel/910002",
                confidence="High",
                source_tier="official_detail",
                reference_role="primary",
            )
        ]

        preserved, added = pipeline._append_serializer_mismatch_candidate_preservation_candidates(
            ctx=ctx,
            title_candidates=existing,
            prior_contract=prior,
            boundary_title=boundary_title,
            boundary_url="https://novelpia.com/novel/910002",
        )

        by_url = {
            candidate.heretic_url: candidate
            for candidate in preserved
            if candidate.heretic_url
        }
        self.assertEqual(added, 2)
        self.assertIn("https://novelpia.com/novel/910000", by_url)
        self.assertIn("https://novelpia.com/novel/910001", by_url)
        self.assertIn("https://novelpia.com/novel/910002", by_url)
        self.assertEqual(by_url["https://novelpia.com/novel/910001"].official_title, contextual_title)
        self.assertEqual(by_url["https://novelpia.com/novel/910001"].reference_role, "candidate")
        self.assertFalse(by_url["https://novelpia.com/novel/910001"].locked)
        self.assertIn(
            "search_alias_candidate_preservation_only",
            by_url["https://novelpia.com/novel/910001"].negative_evidence or [],
        )
        self.assertNotIn(
            "갤러리",
            [candidate.official_title for candidate in preserved],
        )

    def test_non_official_title_lead_search_inferred_candidate_is_capped_at_medium(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11718098,
            title="망겜힐은 최신화 후기",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="작가와 회차 전개를 길게 이야기함")],
            comments=[],
        )
        ctx = ConversationContext(post_id=11718098, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.llm_snippet_analysis = {
            "identified_title": "망겜의 힐러",
            "abbreviation_mappings": [{"abbrev": "망겜힐", "full": "망겜의 힐러"}],
        }
        ctx.search_results = [
            {
                "title": "망겜의 힐러 - 리디북스",
                "url": "https://example.com/books/123",
                "content": "망겜힐 웹소설 장르소설 작가 연재 완결 리뷰",
                "query": "망겜힐 웹소설",
            },
            {
                "title": "망겜의 힐러 - 장르소설 리뷰",
                "url": "https://example.com/review/123",
                "content": "망겜힐 웹소설 장르소설 작가 연재 완결 감상",
                "query": "망겜힐 장르소설",
            },
        ]

        candidates = pipeline._build_title_lead_alias_search_inferred_candidates(ctx)

        self.assertEqual([candidate.official_title for candidate in candidates], ["망겜의 힐러"])
        self.assertEqual(candidates[0].source_tier, "mixed")
        self.assertEqual(candidates[0].confidence, "Medium")
        self.assertIn("non_official_alias_search_support", candidates[0].negative_evidence or [])

    def test_non_official_search_alias_stability_is_soft_only_for_canonical_rescue(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11718099,
            title="망겜힐 최신화 후기",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="작가와 회차 전개를 길게 이야기함")],
            comments=[],
        )
        ctx = ConversationContext(post_id=11718099, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.llm_snippet_analysis = {
            "identified_title": "망겜의 힐러",
            "abbreviation_mappings": [{"abbrev": "망겜힐", "full": "망겜의 힐러"}],
        }
        ctx.search_results = [
            {
                "title": "망겜의 힐러 - 리디북스",
                "url": "https://example.com/books/123",
                "content": "망겜힐 웹소설 장르소설 작가 연재 완결 리뷰",
                "query": "망겜힐 웹소설",
            },
            {
                "title": "망겜의 힐러 - 장르소설 리뷰",
                "url": "https://example.com/review/123",
                "content": "망겜힐 웹소설 장르소설 작가 연재 완결 감상",
                "query": "망겜힐 장르소설",
            },
        ]

        rescue = pipeline._canonical_work_rescue_strength(
            ctx=ctx,
            title="망겜의 힐러",
            vf_result={"is_relevant": False, "grounding_check": {"anchor_found": "search_only"}},
        )

        self.assertTrue(pipeline._has_search_evidence_alias_stability_signal(ctx, "망겜의 힐러"))
        self.assertTrue(pipeline._has_title_abbrev_stability_signal(ctx, "망겜의 힐러"))
        self.assertFalse(pipeline._has_title_abbrev_stability_hard_support(ctx, "망겜의 힐러"))
        self.assertTrue(rescue["abbrev_stable"])
        self.assertFalse(rescue["abbrev_hard_support"])
        self.assertFalse(rescue["strong"])

    def test_j1_verifier_veto_keeps_reject_on_nonofficial_search_alias_stability(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11718100,
            title="망겜힐 최신화 후기",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="작가와 회차 전개를 길게 이야기함")],
            comments=[],
        )
        ctx = ConversationContext(post_id=11718100, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.discourse_intent = "discuss_work"
        ctx.primary_domain = "novel_literature"
        ctx.llm_snippet_analysis = {
            "identified_title": "망겜의 힐러",
            "abbreviation_mappings": [{"abbrev": "망겜힐", "full": "망겜의 힐러"}],
        }
        ctx.search_results = [
            {
                "title": "망겜의 힐러 - 리디북스",
                "url": "https://example.com/books/123",
                "content": "망겜힐 웹소설 장르소설 작가 연재 완결 리뷰",
                "query": "망겜힐 웹소설",
            },
            {
                "title": "망겜의 힐러 - 장르소설 리뷰",
                "url": "https://example.com/review/123",
                "content": "망겜힐 웹소설 장르소설 작가 연재 완결 감상",
                "query": "망겜힐 장르소설",
            },
        ]
        for idx, sr in enumerate(ctx.search_results, start=1):
            ctx.add_evidence_for_candidate(
                "망겜의 힐러",
                f"search_snippet_{idx}",
                {"url": sr["url"], "title": sr["title"], "content": sr["content"]},
            )
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "work_discussion",
                "detected_entities": {"possible_titles": ["망겜힐"]},
                "context_clues": {},
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "discuss_work",
                    "title_novel_terms": ["망겜힐"],
                    "semantic_seed_review": {"is_specific_work_discussion": True},
                },
            },
        )
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "overall_confidence": "medium",
                "decoded_terms": [
                    {
                        "original": "망겜힐",
                        "best_match": {"title": "망겜의 힐러", "confidence": "Medium"},
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
                    "reason": "비공식 검색 별칭 반복 외 본문 고유 근거 없음",
                    "rejection_reason": "검색어만 겹치며 작품 고유 정보가 없음",
                    "novel_identity": {
                        "official_novel_title": "망겜의 힐러",
                        "confidence": "Medium",
                    },
                    "grounding_check": {
                        "anchor_found": "none",
                        "grounding_issue": "작품 고유 정보 없음",
                    },
                    "counter_arguments": [
                        {"severity": "minor", "action": "review", "reason": "search_only"}
                    ],
                }
            },
        )
        ctx.set_expert_output(
            ExpertType.ARBITER,
            {
                "final_decision": {
                    "is_relevant": True,
                    "official_title": "망겜의 힐러",
                    "official_novel_title": "망겜의 힐러",
                    "confidence": "High",
                    "discussion_type": "work_discussion",
                    "final_reasoning": "비공식 검색 별칭 안정 신호로 작품 토론으로 판단",
                },
                "metadata_synthesis": {},
            },
        )

        old_validator = pipeline._apply_output_consistency_validator
        old_select = pipeline._select_best_canonical_rescue_candidate
        pipeline._select_best_canonical_rescue_candidate = lambda **_kwargs: {
            "title": None,
            "rescue": {},
            "score": 0,
        }
        pipeline._apply_output_consistency_validator = lambda **kwargs: {
            "is_relevant": kwargs["is_relevant"],
            "discussion_type": kwargs.get("discussion_type") or "noise",
            "topicality": "core_relevant" if kwargs["is_relevant"] else "unrelated",
            "subtype": "resolved_work" if kwargs.get("official_title") else "other_quarantine",
            "work_resolution": "resolved" if kwargs.get("official_title") else "none",
            "anchor_type": "title_alias" if kwargs.get("official_title") else "none",
            "anchor_strength": "medium" if kwargs.get("official_title") else "none",
            "context_sources": [],
            "consistency_flags": [],
            "official_title": kwargs.get("official_title"),
            "confidence": kwargs.get("confidence"),
            "reason": kwargs.get("reason") or "",
            "notes": kwargs.get("notes") or "",
        }
        try:
            output = pipeline._context_to_output(ctx)
        finally:
            pipeline._apply_output_consistency_validator = old_validator
            pipeline._select_best_canonical_rescue_candidate = old_select

        self.assertTrue(pipeline._has_title_abbrev_stability_signal(ctx, "망겜의 힐러"))
        self.assertFalse(pipeline._has_title_abbrev_stability_hard_support(ctx, "망겜의 힐러"))
        self.assertFalse(output.identity.is_relevant)
        self.assertIsNone(output.identity.novel_identity)

    def test_no_work_seed_blocks_corrected_title_url_recovery_search(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=FailOnSearchMCP(), max_iterations=2)
        post = PostInput(
            post_id=11718080,
            title="망겜힐은 밥먹을때 같이 볼 친구 있었으면",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(
                    type="text",
                    text="작품 감상이 아니라 소설 보는 친구 있으면 좋겠다는 잡담",
                )
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=11718080, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)
        ctx.search_results = [
            {
                "title": "망겜의 힐러 - 네이버 시리즈",
                "url": "https://series.naver.com/novel/detail.series?productNo=7774",
                "content": "망겜힐 웹소설 작품 페이지",
                "query": "망겜힐 웹소설",
            }
        ]

        recovered = pipeline._recover_corrected_title_official_url(
            ctx,
            title="망겜의 힐러",
            alias_text="망겜힐",
            purpose="batch_memory_alias_official_url_recovery",
        )

        self.assertIsNone(recovered)

    def test_no_work_seed_blocks_search_inferred_alias_even_with_official_url(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11718080,
            title="망겜힐은 밥먹을때 같이 볼 친구 있었으면",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(
                    type="text",
                    text="작품 감상이 아니라 소설 보는 친구 있으면 좋겠다는 잡담",
                )
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=11718080, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)
        ctx.search_results = [
            {
                "title": "망겜의 힐러 - 네이버 시리즈",
                "url": "https://series.naver.com/novel/detail.series?productNo=7774",
                "content": "망겜힐 웹소설 작품 페이지",
                "query": "망겜힐 웹소설",
            }
        ]

        self.assertTrue(pipeline._has_official_title_evidence(ctx, "망겜의 힐러"))
        self.assertFalse(
            pipeline._has_direct_post_or_visual_work_anchor_for_no_work_search_rescue(
                ctx,
                "망겜의 힐러",
            )
        )
        block_reason = pipeline._search_inferred_alias_nonwork_block_reason(
            ctx,
            title="망겜의 힐러",
            alias="망겜힐",
            surface="망겜힐은 밥먹을때 같이 볼 친구 있었으면",
            verification_result={},
        )

        self.assertEqual(block_reason, "semantic_seed_no_work_context")

    def test_no_work_batch_alias_rescue_blocks_search_inference_with_matched_url(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11718080,
            title="망겜힐은 밥먹을때 같이 볼 친구 있었으면",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(
                    type="text",
                    text="작품 감상이 아니라 소설 보는 친구 있으면 좋겠다는 잡담",
                )
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=11718080, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)

        old_infer = pipeline._infer_alias_title_from_search_evidence
        pipeline._infer_alias_title_from_search_evidence = lambda _ctx, _surface: {
            "source": "search_evidence_alias_inference",
            "source_tier": "official_detail",
            "title": "망겜의 힐러",
            "alias": "망겜힐",
            "confidence": 3,
            "matched_url": "https://series.naver.com/novel/detail.series?productNo=7774",
        }
        try:
            candidate, hit = pipeline._resolve_batch_memory_alias_candidate(ctx, verification_result={})
        finally:
            pipeline._infer_alias_title_from_search_evidence = old_infer

        self.assertIsNone(candidate)
        self.assertIsNone(hit)
        self.assertEqual(
            getattr(ctx, "_batch_alias_rescue_blocked_nonwork_context_reason", None),
            "semantic_seed_no_work_context",
        )
        self.assertEqual(
            getattr(ctx, "_batch_alias_rescue_blocked_nonwork_context_title", None),
            "망겜의 힐러",
        )

    def test_batch_alias_rescue_blocks_common_noun_culture_alias(self):
        pipeline = build_pipeline()

        class CultureAliasMemory:
            enabled = True

            def resolve_abbreviation_surface(self, surface):
                if surface == "문화":
                    return {
                        "source": "batch_memory_exact_alias_rescued",
                        "source_tier": "official_detail",
                        "title": "그녀의 순결이 타락할 때까지",
                        "alias": "문화",
                        "confidence": 3,
                        "matched_url": "https://novelpia.com/novel/166048",
                    }
                return None

        pipeline.batch_context = CultureAliasMemory()
        post = PostInput(
            post_id=11694019,
            title="미츄리 혼후순결에서 하인들에게도 멸시당한게 고증에 맞는거였구나",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="프시케 혼후순결 서약 문화 얘기")
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=11694019, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "detected_entities": {"possible_titles": []},
                "key_terms": ["문화"],
            },
        )

        self.assertTrue(pipeline._is_low_information_alias_surface("문화"))
        candidate, hit = pipeline._resolve_batch_memory_alias_candidate(ctx, verification_result={})

        self.assertIsNone(candidate)
        self.assertIsNone(hit)

    def test_batch_alias_rescue_blocks_common_connector_not_alias(self):
        pipeline = build_pipeline()

        class ConnectorAliasMemory:
            enabled = True

            def resolve_abbreviation_surface(self, surface):
                if "아니라" in str(surface or ""):
                    return {
                        "source": "search_evidence_alias_inference",
                        "source_tier": "official_detail",
                        "title": "그녀의 순결이 타락할 때까지",
                        "alias": "아니라",
                        "confidence": 3,
                        "matched_url": "https://novelpia.com/novel/166048",
                    }
                return None

        pipeline.batch_context = ConnectorAliasMemory()
        post = PostInput(
            post_id=11694019,
            title="미츄리 혼후순결에서 하인들에게도 멸시당한게 고증에 맞는거였구나",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="프시케 서약이 아니라 가문 문제로 봐야 하는 장면")
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=11694019, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "detected_entities": {"possible_titles": ["아니라"]},
                "key_terms": ["미츄리", "혼후순결", "아니라"],
            },
        )

        self.assertTrue(pipeline._is_low_information_alias_surface("아니라"))
        self.assertTrue(pipeline._is_low_information_alias_surface("모든"))
        self.assertTrue(pipeline._is_low_information_alias_surface("수상할"))
        self.assertTrue(pipeline._is_low_information_alias_surface("정도로"))
        candidate, hit = pipeline._resolve_batch_memory_alias_candidate(ctx, verification_result={})

        self.assertIsNone(candidate)
        self.assertIsNone(hit)

    def test_batch_alias_rescue_blocks_generic_element_alias(self):
        pipeline = build_pipeline()

        class ElementAliasMemory:
            enabled = True

            def resolve_abbreviation_surface(self, surface):
                if "요소" in str(surface or ""):
                    return {
                        "source": "search_evidence_alias_inference",
                        "source_tier": "official_detail",
                        "title": "마지막 희망",
                        "alias": "요소",
                        "confidence": 3,
                        "matched_url": "https://novelpia.com/novel/9817",
                    }
                return None

        pipeline.batch_context = ElementAliasMemory()
        post = PostInput(
            post_id=11698897,
            title="랫따싶 림월드 요소 생각나게 하는거 좋네에...",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="게임적 요소 있는거 아주 굿")
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=11698897, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "detected_entities": {"possible_titles": ["랫따싶"]},
                "key_terms": ["랫따싶", "림월드", "요소"],
            },
        )

        self.assertTrue(pipeline._is_low_information_alias_surface("요소"))
        candidate, hit = pipeline._resolve_batch_memory_alias_candidate(ctx, verification_result={})

        self.assertIsNone(candidate)
        self.assertIsNone(hit)

    def test_batch_alias_rescue_blocks_common_noun_legend_alias(self):
        pipeline = build_pipeline()

        class LegendAliasMemory:
            enabled = True

            def resolve_abbreviation_surface(self, surface):
                if "레전드" in str(surface or ""):
                    return {
                        "source": "search_evidence_alias_inference",
                        "source_tier": "official_detail",
                        "title": "한국 레전드 프로게이머인 내가 일본판타지 사정에 휘말린 것에 대하여",
                        "alias": "레전드",
                        "confidence": 3,
                        "matched_url": "https://novelpia.com/novel/143896",
                    }
                return None

        pipeline.batch_context = LegendAliasMemory()
        post = PostInput(
            post_id=11705231,
            title="장갤 설지후 변화도 레전드임",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="실제 소설에선 설지후는 걍 개쓰레기인데"),
                ContentBlock(type="text", text="로유진은 설지후 쓰레기로만 설정했는데 장갤 밈이 생김"),
            ],
            comments=["탐식 6년전인가에 다 읽고"],
        )
        ctx = ConversationContext(post_id=11705231, post_data=pipeline._post_to_dict(post), comments=post.comments)
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "detected_entities": {"possible_titles": ["레전드"]},
                "key_terms": ["설지후", "레전드"],
            },
        )

        self.assertTrue(pipeline._is_low_information_alias_surface("레전드"))
        candidate, hit = pipeline._resolve_batch_memory_alias_candidate(ctx, verification_result={})

        self.assertIsNone(candidate)
        self.assertIsNone(hit)

    def test_batch_alias_rescue_blocks_common_noun_reality_alias(self):
        pipeline = build_pipeline()

        class RealityAliasMemory:
            enabled = True

            def resolve_abbreviation_surface(self, surface):
                if str(surface or "") == "현실":
                    return {
                        "source": "search_evidence_alias_inference",
                        "source_tier": "official_detail",
                        "title": "한국 레전드 프로게이머인 내가 일본판타지 사정에 휘말린 것에 대하여",
                        "alias": "현실",
                        "confidence": 3,
                        "matched_url": "https://novelpia.com/novel/143896",
                    }
                return None

        pipeline.batch_context = RealityAliasMemory()
        post = PostInput(
            post_id=11705231,
            title="장갤 설지후 변화도 레전드임",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="실제 소설에선 현실 설지후는 걍 개쓰레기인데")],
            comments=[],
        )
        ctx = ConversationContext(post_id=11705231, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "detected_entities": {"possible_titles": ["현실"]},
                "key_terms": ["현실", "설지후"],
            },
        )

        self.assertTrue(pipeline._is_low_information_alias_surface("현실"))
        candidate, hit = pipeline._resolve_batch_memory_alias_candidate(ctx, verification_result={})

        self.assertIsNone(candidate)
        self.assertIsNone(hit)

    def test_batch_alias_rescue_blocks_common_determiner_which_alias(self):
        pipeline = build_pipeline()

        class WhichAliasMemory:
            enabled = True

            def resolve_abbreviation_surface(self, surface):
                if "어느" in str(surface or ""):
                    return {
                        "source": "search_evidence_alias_inference",
                        "source_tier": "official_detail",
                        "title": "한국 레전드 프로게이머인 내가 일본판타지 사정에 휘말린 것에 대하여",
                        "alias": "어느",
                        "confidence": 3,
                        "matched_url": "https://novelpia.com/novel/143896",
                    }
                return None

        pipeline.batch_context = WhichAliasMemory()
        post = PostInput(
            post_id=11705231,
            title="장갤 설지후 변화도 레전드임",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="실제 소설에선 어느 순간 설지후는 걍 개쓰레기인데"),
                ContentBlock(type="text", text="로유진은 설지후 쓰레기로만 설정했는데 장갤 밈이 생김"),
            ],
            comments=["탐식 6년전인가에 다 읽고"],
        )
        ctx = ConversationContext(post_id=11705231, post_data=pipeline._post_to_dict(post), comments=post.comments)
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "detected_entities": {"possible_titles": ["어느"]},
                "key_terms": ["설지후", "어느"],
            },
        )

        self.assertTrue(pipeline._is_low_information_alias_surface("어느"))
        candidate, hit = pipeline._resolve_batch_memory_alias_candidate(ctx, verification_result={})

        self.assertIsNone(candidate)
        self.assertIsNone(hit)

    def test_batch_alias_rescue_blocks_character_name_search_inference_without_title_anchor(self):
        pipeline = build_pipeline()

        class CharacterAliasMemory:
            enabled = True

            def resolve_abbreviation_surface(self, surface):
                if "에이브" in str(surface or ""):
                    return {
                        "source": "search_evidence_alias_inference",
                        "source_tier": "wiki",
                        "title": "보물섬(소설)",
                        "alias": "에이브",
                        "confidence": 3,
                        "matched_url": "https://namu.wiki/w/보물섬(소설)",
                    }
                return None

        pipeline.batch_context = CharacterAliasMemory()
        post = PostInput(
            post_id=11700470,
            title="어케 주인공 죄목이",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="B급 모험가 밤도깨비 에이브 납치 세뇌 엘프 방생")
            ],
            comments=["교수형"],
        )
        ctx = ConversationContext(post_id=11700470, post_data=pipeline._post_to_dict(post), comments=post.comments)
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "detected_entities": {"possible_characters": ["에이브"], "possible_titles": ["밤도깨비 에이브"]},
                "key_terms": ["밤도깨비 에이브", "B급 모험가"],
            },
        )
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "decoded_terms": [
                    {
                        "original": "밤도깨비 에이브",
                        "interpretations": [{"type": "character", "value": "에이브"}],
                        "best_match": {"anchor_type": "character_mention"},
                    }
                ]
            },
        )

        self.assertTrue(pipeline._is_search_inferred_character_alias_surface(ctx, "에이브"))
        candidate, hit = pipeline._resolve_batch_memory_alias_candidate(ctx, verification_result={})

        self.assertIsNone(candidate)
        self.assertIsNone(hit)
        self.assertEqual(getattr(ctx, "_batch_alias_rescue_blocked_character_alias", None), "에이브")
        self.assertEqual(
            getattr(ctx, "_batch_alias_rescue_blocked_character_alias_title", None),
            "보물섬(소설)",
        )

    def test_deliberated_character_setting_convergence_reads_final_decision_jury(self):
        pipeline = build_pipeline()
        title = "탐식의 재림"
        post = PostInput(
            post_id=11705231,
            title="장갤 설지후 변화도 레전드임",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="실제 소설에선 설지후는 걍 개쓰레기인데"),
                ContentBlock(type="text", text="로유진은 설지후 쓰레기로만 설정했고 유선화 자매 얘기도 나옴"),
            ],
            comments=["탐식 6년전인가에 다 읽고"],
        )
        ctx = ConversationContext(
            post_id=11705231,
            post_data=pipeline._post_to_dict(post),
            comments=post.comments,
        )
        ctx.search_results = [
            {
                "title": "탐식의 재림 - 판타지 e북 - 리디",
                "url": "https://ridibooks.com/books/2008016338",
                "content": "탐식의 재림 작품소개. 설지후와 로유진.",
            },
            {
                "title": "탐식의 재림 - 웹소설 - 카카오페이지",
                "url": "https://page.kakao.com/content/50219568?tab_type=comment",
                "content": "로유진. 탐식의 재림. 설지후.",
            },
        ]
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "primary_domain": "novel_literature",
                    "intent": "express_opinion",
                    "target_kind": "work",
                }
            },
        )
        ctx.set_expert_output(
            ExpertType.SYNTHESIZER,
            {
                "confidence_assessment": {
                    "is_about_identified_work": True,
                    "confidence": "Max",
                },
                "hidden_references": [
                    {
                        "reference_type": "character",
                        "matched_to": "탐식의 재림 - 설지후",
                        "evidence": "검색 결과에서 설지후가 탐식의 재림 주인공으로 확인됨",
                    }
                ],
            },
        )
        vf_result = {
            "is_relevant": False,
            "grounding_check": {"anchor_found": "character_mention"},
            "relation_judgment": {
                "relation_type": "thematic_overlap_only",
                "discussion_target": "specific_work",
                "promotion_decision": "reject",
            },
        }
        final_decision = {
            "official_novel_title": title,
            "official_title": title,
            "suspected_titles": [{"title": title, "confidence": "Max"}],
            "final_reasoning": "Jury와 Judge가 탐식의 재림으로 수렴",
            "_deliberation": {"jury_votes": {"relevant": 3, "irrelevant": 0}},
        }

        self.assertTrue(
            pipeline._has_deliberated_character_setting_work_convergence(
                ctx,
                title,
                vf_result=vf_result,
                final_decision=final_decision,
            )
        )

    def test_deliberated_character_setting_convergence_bypasses_community_banter_relation_block(self):
        pipeline = build_pipeline()
        title = "탐식의 재림"
        post = PostInput(
            post_id=11705231,
            title="장갤 설지후 변화도 레전드임",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="실제 소설에선 설지후는 걍 개쓰레기인데"),
                ContentBlock(type="text", text="로유진은 설지후 쓰레기로만 설정했고 유선화 자매 얘기도 나옴"),
            ],
            comments=["아니 나 탐식 6년전인가에 다 읽고도 그렇게 기억중이었는데"],
        )
        ctx = ConversationContext(
            post_id=11705231,
            post_data=pipeline._post_to_dict(post),
            comments=post.comments,
        )
        ctx.search_results = [
            {
                "title": "탐식의 재림 - 판타지 e북 - 리디",
                "url": "https://ridibooks.com/books/2008016338",
                "content": "탐식의 재림 작품소개. 설지후와 로유진.",
            },
            {
                "title": "탐식의 재림 - 웹소설 - 카카오페이지",
                "url": "https://page.kakao.com/content/50219568?tab_type=comment",
                "content": "로유진. 탐식의 재림. 설지후.",
            },
        ]
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "primary_domain": "novel_literature",
                    "intent": "express_opinion",
                    "target_kind": "work",
                }
            },
        )
        ctx.set_expert_output(
            ExpertType.SYNTHESIZER,
            {
                "confidence_assessment": {
                    "is_about_identified_work": True,
                    "confidence": "Max",
                },
                "hidden_references": [
                    {
                        "reference_type": "character",
                        "matched_to": "탐식의 재림 - 설지후",
                    }
                ],
            },
        )
        final_decision = {
            "official_novel_title": title,
            "official_title": title,
            "suspected_titles": [{"title": title, "confidence": "Max"}],
            "_deliberation": {
                "jury_votes": {"relevant": 3, "irrelevant": 0},
                "final_reasoning": "설지후, 유선화, 로유진은 탐식의 재림 캐릭터/작가 설정으로 수렴한다.",
            },
        }
        ctx.set_expert_output(
            ExpertType.ARBITER,
            {
                "final_decision": final_decision,
                "_deliberation": final_decision["_deliberation"],
            },
        )
        vf_result = {
            "is_relevant": False,
            "grounding_check": {
                "decoder_grounded": True,
                "anchor_text": "설지후, 유선화, 로유진",
                "anchor_found": "character_mention",
            },
            "relation_judgment": {
                "relation_type": "thematic_overlap_only",
                "discussion_target": "community_banter",
                "promotion_decision": "hold",
            },
        }
        ctx.set_expert_output(ExpertType.VERIFIER, {"verification_result": vf_result})

        self.assertIn(
            "https://page.kakao.com/content/50219568",
            pipeline._official_detail_exact_title_urls_for_no_work_anchor(ctx, title),
        )
        acceptance = pipeline._compute_title_acceptance(ctx, title, vf_result)

        self.assertEqual(acceptance["decision"], "accept")
        self.assertIn("deliberated_character_setting_convergence", acceptance["notes"])
        self.assertEqual(pipeline._correct_title_final(title, ctx), title)

    def test_hoegwi_suseonjeon_character_setting_convergence_uses_shared_work_bridge(self):
        pipeline = build_pipeline()
        title = "회귀수선전"
        post = PostInput(
            post_id=11669933,
            title="중경계에서 첨 만난게 해방상제임?",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="서휼 따라가서 지하에서 버티는 시합하다가 만난거"),
            ],
            comments=["그거 미래의 주인공", "ㅇㅇ"],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=post.comments,
        )
        ctx.search_results = [
            {
                "title": "회귀수선전/등장인물/수계 - 나무위키",
                "url": "https://namu.wiki/w/%ED%9A%8C%EA%B7%80%EC%88%98%EC%84%A0%EC%A0%84/%EB%93%B1%EC%9E%A5%EC%9D%B8%EB%AC%BC/%EC%88%98%EA%B3%84",
                "content": "회귀수선전 등장인물 문서. 서휼, 해방상제, 중경계 관련 설정.",
            },
            {
                "title": "회귀수선전 - 나무위키",
                "url": "https://namu.wiki/w/%ED%9A%8C%EA%B7%80%EC%88%98%EC%84%A0%EC%A0%84",
                "content": "한국의 선협 웹소설 회귀수선전. 중경계와 해방상제 설정이 언급된다.",
            },
        ]
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "primary_domain": "novel_literature",
                    "intent": "discuss_work",
                    "target_kind": "work",
                }
            },
        )
        ctx.set_expert_output(
            ExpertType.SYNTHESIZER,
            {
                "confidence_assessment": {
                    "is_about_identified_work": True,
                    "confidence": "Max",
                },
                "hidden_references": [
                    {
                        "reference_type": "character_setting",
                        "matched_to": "회귀수선전 - 서휼/해방상제/중경계",
                    }
                ],
            },
        )
        final_decision = {
            "official_novel_title": title,
            "official_title": title,
            "suspected_titles": [{"title": title, "confidence": "High"}],
            "_deliberation": {
                "jury_votes": {"relevant": 3, "irrelevant": 0},
                "final_reasoning": "중경계, 서휼, 해방상제 설정은 회귀수선전 인물/세계관으로 수렴한다.",
            },
        }
        vf_result = {
            "is_relevant": False,
            "grounding_check": {
                "anchor_found": "setting_mention",
                "anchor_text": "중경계, 서휼, 해방상제",
            },
            "relation_judgment": {
                "relation_type": "setting_work_link",
                "discussion_target": "specific_work",
                "promotion_decision": "hold",
            },
        }

        self.assertTrue(
            pipeline._has_deliberated_character_setting_work_convergence(
                ctx,
                title,
                vf_result=vf_result,
                final_decision=final_decision,
            )
        )
        self.assertTrue(
            pipeline._post_discusses_work_as_work(
                ctx,
                title,
                final_decision=final_decision,
                verification_result=vf_result,
            )
        )

    def test_character_setting_convergence_rejects_conflicting_hidden_work_cluster(self):
        pipeline = build_pipeline()
        title = "회귀수선전"
        post = PostInput(
            post_id=11669933,
            title="중경계에서 첨 만난게 해방상제임?",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="서휼 따라가서 지하에서 버티는 시합하다가 만난거"),
            ],
            comments=["그거 미래의 주인공"],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=post.comments,
        )
        ctx.search_results = [
            {
                "title": "회귀수선전 - 나무위키",
                "url": "https://namu.wiki/w/%ED%9A%8C%EA%B7%80%EC%88%98%EC%84%A0%EC%A0%84",
                "content": "회귀수선전 작품 소개.",
            },
            {
                "title": "회귀수선전/등장인물",
                "url": "https://namu.wiki/w/example",
                "content": "작품 등장인물 소개.",
            },
        ]
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "primary_domain": "novel_literature",
                    "intent": "discuss_work",
                    "target_kind": "work",
                }
            },
        )
        ctx.set_expert_output(
            ExpertType.SYNTHESIZER,
            {
                "confidence_assessment": {
                    "is_about_identified_work": True,
                    "confidence": "Max",
                },
                "hidden_references": [
                    {
                        "reference_type": "character_setting",
                        "matched_to": "삼천세계 - 중경계/해방상제",
                    }
                ],
            },
        )
        final_decision = {
            "official_novel_title": title,
            "official_title": title,
            "_deliberation": {
                "jury_votes": {"relevant": 3, "irrelevant": 0},
                "final_reasoning": "회귀수선전으로 수렴한다.",
            },
        }
        vf_result = {
            "grounding_check": {"anchor_found": "setting_mention"},
            "relation_judgment": {
                "relation_type": "setting_work_link",
                "discussion_target": "specific_work",
                "promotion_decision": "hold",
            },
        }

        self.assertFalse(
            pipeline._has_deliberated_character_setting_work_convergence(
                ctx,
                title,
                vf_result=vf_result,
                final_decision=final_decision,
            )
        )
        self.assertFalse(
            pipeline._post_discusses_work_as_work(
                ctx,
                title,
                final_decision=final_decision,
                verification_result=vf_result,
            )
        )

    def test_contextual_alias_official_lock_allows_comment_abbrev_and_short_names(self):
        pipeline = build_pipeline()
        title = "탐식의 재림"
        post = PostInput(
            post_id=11705231,
            title="장갤 설지후 변화도 레전드임",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="실제 소설에선 현실 설지후는 걍 개쓰레기인데"),
                ContentBlock(type="text", text="로유진은 설지후 쓰레기로만 설정했고 유선화 자매 얘기도 나옴"),
            ],
            comments=["아니 나 탐식 6년전인가에 다 읽고도 그렇게 기억중이었는데"],
        )
        ctx = ConversationContext(
            post_id=11705231,
            post_data=pipeline._post_to_dict(post),
            comments=post.comments,
        )
        ctx.search_results = [
            {
                "title": "탐식의 재림 - 판타지 e북 - 리디",
                "url": "https://ridibooks.com/books/2008016338",
                "domain": "ridibooks.com",
                "source_tier": "official_platform",
                "content": "탐식의 재림 작품소개. 작가 로유진. 주인공 설지후.",
            },
            {
                "title": "탐식의 재림 - 웹소설 - 카카오페이지",
                "url": "https://page.kakao.com/content/50219568?tab_type=comment",
                "domain": "page.kakao.com",
                "source_tier": "official_platform",
                "content": "로유진. 탐식의 재림. 설지후.",
            },
        ]
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "detected_entities": {
                    "possible_characters": ["설지후", "유선화"],
                    "possible_authors": ["로유진"],
                }
            },
        )
        ctx.set_expert_output(
            ExpertType.SYNTHESIZER,
            {
                "confidence_assessment": {
                    "is_about_identified_work": True,
                    "confidence": "Max",
                },
                "hidden_references": [
                    {
                        "text": "탐식",
                        "reference_type": "title",
                        "matched_to": "탐식의 재림",
                    }
                ],
            },
        )
        vf_result = {
            "is_relevant": True,
            "novel_identity": {
                "official_novel_title": title,
                "heretic_url": "https://ridibooks.com/books/2008016338",
            },
            "grounding_check": {"anchor_found": "character_mention"},
            "relation_judgment": {
                "relation_type": "explicit_alias",
                "discussion_target": "specific_work",
                "promotion_decision": "hold",
                "reason": "댓글에서 '탐식'이라는 표현이 등장하며 탐식의 재림을 지칭하는 명확한 약칭입니다.",
                "key_evidence": ["댓글 내 '탐식 6년전인가에 다 읽고도' 문구"],
                "search_support_summary": {
                    "official_exact_title_count": 2,
                    "alias_in_post_count": 0,
                    "explicit_alias_bridge_count": 0,
                    "best_official_url": "https://ridibooks.com/books/2008016338",
                },
            },
        }

        self.assertTrue(pipeline._has_contextual_alias_official_detail_lock(ctx, title, vf_result))
        self.assertFalse(
            pipeline._relation_hold_should_block_title_resolution(
                ctx=ctx,
                official_title=title,
                verification_result=vf_result,
            )
        )

    def test_batch_alias_rescue_blocks_common_noun_certification_search_alias(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11694019,
            title="미츄리 혼후순결에서 하인들에게도 멸시당한게 고증에 맞는거였구나",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="중세 문화에서는 결혼 인증이 섹스라서")
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=11694019, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.search_results = [
            {
                "title": "웹소설로 꿈꾸는 세상! - 그녀의 순결이 타락할 때까지 - 노벨피아",
                "url": "https://novelpia.com/novel/166048",
                "content": "성인 인증 후 이용 가능한 작품 페이지. 그녀의 순결이 타락할 때까지.",
                "query": "결혼 인증 노벨피아",
                "source_tier": "novel_platform",
            }
        ]
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "detected_entities": {"possible_titles": ["결혼 인증"]},
                "key_terms": ["결혼 인증", "인증"],
            },
        )

        forms = pipeline._alias_forms_for_search_inference("결혼 인증")
        self.assertNotIn("결혼인증", forms)
        self.assertNotIn("인증", forms)

        candidate, hit = pipeline._resolve_batch_memory_alias_candidate(ctx, verification_result={})

        self.assertIsNone(candidate)
        self.assertIsNone(hit)

    def test_context_only_resolution_fields_block_search_inferred_alias_without_discourse(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11718080,
            title="망겜힐 같이 볼 친구 있었으면",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="작품 특정 없이 소설 같이 볼 친구 얘기")
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=11718080, post_data=pipeline._post_to_dict(post), comments=[])
        verification_result = {
            "title_resolution_state": "context_only",
            "title_resolution_allowed": False,
        }

        block_reason = pipeline._search_inferred_alias_nonwork_block_reason(
            ctx,
            title="망겜의 힐러",
            alias="망겜힐",
            surface="망겜힐 같이 볼 친구 있었으면",
            verification_result=verification_result,
        )

        self.assertEqual(block_reason, "semantic_seed_no_work_context")

    def test_direct_image_anchor_allows_corrected_title_url_recovery_search(self):
        mcp = CountingSearchMCP()
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=mcp, max_iterations=2)
        post = PostInput(
            post_id=11718082,
            title="이게 백합 소설이 아니라니...",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="두렵구나")],
            comments=[],
        )
        post_dict = pipeline._post_to_dict(post)
        post_dict["image_enrichment"] = [
            {
                "evidence_type": "explicit_text",
                "title_role": "work_title",
                "focus_role": "work_anchor",
                "promotion_eligible": True,
                "explicit_work_title": "재벌가 차녀의 2회차 걸그룹",
                "explicit_author_name": "유은우",
                "work_cues": ["KAKAOPAGE"],
            }
        ]
        ctx = ConversationContext(post_id=11718082, post_data=post_dict, comments=[])
        mark_no_work_seed(ctx)

        recovered = pipeline._recover_corrected_title_official_url(
            ctx,
            title="재벌가 차녀의 2회차 걸그룹",
            alias_text="",
            purpose="corrected_title_official_url_recovery",
        )

        self.assertTrue(mcp.calls)
        self.assertEqual(recovered, "https://page.kakao.com/content/66692543")

    def test_direct_image_anchor_allows_search_inferred_alias_nonwork_context(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11718082,
            title="이게 백합 소설이 아니라니...",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="두렵구나")],
            comments=[],
        )
        post_dict = pipeline._post_to_dict(post)
        post_dict["image_enrichment"] = [
            {
                "evidence_type": "explicit_text",
                "title_role": "work_title",
                "focus_role": "work_anchor",
                "promotion_eligible": True,
                "explicit_work_title": "재벌가 차녀의 2회차 걸그룹",
            }
        ]
        ctx = ConversationContext(post_id=11718082, post_data=post_dict, comments=[])
        mark_no_work_seed(ctx)

        block_reason = pipeline._search_inferred_alias_nonwork_block_reason(
            ctx,
            title="재벌가 차녀의 2회차 걸그룹",
            alias="제벨가 차녀의 2회차 결그룹",
            surface="제벨가 차녀의 2회차 결그룹",
            verification_result={},
        )

        self.assertIsNone(block_reason)

    def test_no_work_seed_blocks_decoder_alias_title_support_without_direct_anchor(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11718080,
            title="망겜힐 같이 볼 친구 있었으면",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="작품 얘기가 아니라 식사 중 한탄")],
            comments=[],
        )
        ctx = ConversationContext(post_id=11718080, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "decoded_terms": [
                    {
                        "original": "망겜힐",
                        "best_match": {"title": "망겜의 힐러", "confidence": "High"},
                    }
                ]
            },
        )

        self.assertFalse(
            pipeline._has_alias_title_support(
                ctx=ctx,
                title="망겜의 힐러",
                vf_result={},
            )
        )

    def test_no_work_strict_anchor_excludes_decoder_alias_and_official_url(self):
        pipeline = build_pipeline()
        title = "망겜의 힐러"
        post = PostInput(
            post_id=11718080,
            title="망겜힐 같이 볼 친구 있었으면",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="밥 먹을 때 같이 소설 볼 친구 있었으면 하는 한탄")],
            comments=[],
        )
        ctx = ConversationContext(post_id=11718080, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)
        ctx.search_results = [
            {
                "title": "망겜의 힐러 - 네이버 시리즈",
                "url": "https://series.naver.com/novel/detail.series?productNo=7774",
                "content": "망겜의 힐러 웹소설 작품 페이지",
            }
        ]
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "decoded_terms": [
                    {
                        "original": "망겜힐",
                        "best_match": {"title": title, "confidence": "High"},
                    }
                ]
            },
        )
        verification_result = {
            "grounding_check": {"anchor_found": "title_abbrev_mention"},
        }

        self.assertTrue(pipeline._has_official_title_evidence(ctx, title))
        self.assertFalse(
            pipeline._has_direct_work_anchor_for_no_work_rescue(
                ctx,
                title,
                verification_result=verification_result,
                has_episode_ref=True,
            )
        )
        self.assertFalse(
            pipeline._can_promote_title_after_semantic_no_work(
                ctx,
                title,
                source="unit_test",
                verification_result=verification_result,
            )
        )

        acceptance = pipeline._compute_title_acceptance(
            ctx,
            title,
            verification_result,
            has_episode_ref=True,
            heretic_url="https://series.naver.com/novel/detail.series?productNo=7774",
        )

        self.assertEqual(acceptance["decision"], "reject")
        self.assertTrue(acceptance["semantic_no_work_block"])
        self.assertIn("semantic_no_work_without_direct_anchor", acceptance["notes"])

    def test_no_work_official_url_gate_preserves_verified_alias_detail_as_candidate_only(self):
        pipeline = build_pipeline()
        title = "망겜의 힐러"
        post = PostInput(
            post_id=20010001,
            title="힐겜 최신화 좋았음",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="주인공 빌런 전개 얘기하는 글")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "discuss_work",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        ctx.search_results = [
            {
                "title": "망겜의 힐러",
                "url": "https://series.naver.com/novel/detail.series?productNo=7774",
                "content": "망겜의 힐러 웹소설 작품 페이지",
            }
        ]
        verification_result = {
            "slang_insight": {
                "detected_term": "힐겜",
                "canonical_work_alias": "힐겜",
                "decoded_term": title,
                "decode_verified": True,
                "alias_scope": "pure_work_alias",
            },
            "grounding_check": {"anchor_found": "title_abbrev_mention", "matched_alias": "힐겜"},
            "relation_judgment": {
                "relation_type": "explicit_alias",
                "discussion_target": "specific_work",
                "promotion_decision": "allow",
            },
            "novel_identity": {"official_title": title},
        }

        self.assertFalse(
            pipeline._has_strict_direct_work_anchor_for_no_work_rescue(
                ctx,
                title,
                verification_result=verification_result,
            )
        )
        self.assertTrue(
            pipeline._has_verified_alias_official_detail_anchor(
                ctx,
                title,
                verification_result=verification_result,
                title_candidates=[],
            )
        )
        self.assertFalse(
            pipeline._can_promote_title_after_semantic_no_work(
                ctx,
                title,
                source="official_url_recall_gate",
                verification_result=verification_result,
                title_candidates=[],
            )
        )
        self.assertTrue(getattr(ctx, "_verified_alias_official_detail_anchor", False))

    def test_no_work_verified_alias_detail_anchor_stays_narrow(self):
        pipeline = build_pipeline()
        title = "망겜의 힐러"

        def _ctx_for(title_text: str, *, intent: str = "discuss_work") -> ConversationContext:
            post = PostInput(
                post_id=20010002,
                title=title_text,
                author="ㅇㅇ",
                content_blocks=[ContentBlock(type="text", text="본문은 짧은 약칭 언급만 있음")],
                comments=[],
            )
            ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
            mark_no_work_seed(ctx)
            ctx.set_expert_output(
                ExpertType.DISCOURSE,
                {
                    "discourse_analysis": {
                        "intent": intent,
                        "target_kind": "work",
                        "primary_domain": "novel_literature",
                        "semantic_seed_review": {"is_specific_work_discussion": False},
                        "warnings": ["semantic_seed_review_specific_work_denied"],
                    }
                },
            )
            ctx.search_results = [
                {
                    "title": title,
                    "url": "https://series.naver.com/novel/detail.series?productNo=7774",
                    "content": "망겜의 힐러 웹소설 작품 페이지",
                }
            ]
            return ctx

        verification_result = {
            "slang_insight": {
                "detected_term": "힐겜",
                "canonical_work_alias": "힐겜",
                "decoded_term": title,
                "decode_verified": True,
                "alias_scope": "pure_work_alias",
            },
            "grounding_check": {"anchor_found": "title_abbrev_mention", "matched_alias": "힐겜"},
            "relation_judgment": {
                "relation_type": "explicit_alias",
                "discussion_target": "specific_work",
                "promotion_decision": "allow",
            },
            "novel_identity": {"official_title": title},
        }

        positive_ctx = _ctx_for("힐겜 최신화 좋았음")
        self.assertFalse(
            pipeline._can_promote_title_after_semantic_no_work(
                positive_ctx,
                title,
                source="batch_memory_exact_alias_rescued",
                verification_result=verification_result,
                title_candidates=[],
            )
        )

        recommendation_ctx = _ctx_for("힐겜 같은 소설 추천 좀", intent="request_recommendation")
        self.assertFalse(
            pipeline._can_promote_title_after_semantic_no_work(
                recommendation_ctx,
                title,
                source="official_url_recall_gate",
                verification_result=verification_result,
                title_candidates=[],
            )
        )

        competing_ctx = _ctx_for("힐겜 최신화 좋았음")
        competing_non_specific_verification = {
            **verification_result,
            "relation_judgment": {
                "relation_type": "thematic_overlap_only",
                "discussion_target": "comparison",
                "promotion_decision": "hold",
            },
        }
        self.assertFalse(
            pipeline._can_promote_title_after_semantic_no_work(
                competing_ctx,
                title,
                source="official_url_recall_gate",
                verification_result=competing_non_specific_verification,
                title_candidates=[
                    DetectedTitle(
                        official_title="다른 공식 작품",
                        heretic_url="https://novelpia.com/novel/999999",
                        confidence="High",
                    )
                ],
            )
        )

        relation_risk_ctx = _ctx_for("힐겜 12화 느낌 나네")
        risky_verification = {
            **verification_result,
            "relation_judgment": {
                "relation_type": "thematic_overlap_only",
                "discussion_target": "comparison",
                "promotion_decision": "keep_unresolved",
            },
            "counter_arguments": [
                {"issue": "약칭 표면이 비교/인접 화제일 수 있음", "severity": "major"}
            ],
        }
        self.assertFalse(
            pipeline._can_promote_title_after_semantic_no_work(
                relation_risk_ctx,
                title,
                source="official_url_recall_gate",
                verification_result=risky_verification,
                title_candidates=[],
            )
        )

    def test_relation_summary_alias_detail_lock_releases_stale_no_work_block(self):
        pipeline = build_pipeline()
        title = "탐식의 재림"
        post = PostInput(
            post_id=11705231,
            title="장갤 설지후 변화도 레전드임",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="설지후 유선화 캐릭터 설정 변화 이야기")],
            comments=["아니 나 탐식 6년전인가에 다 읽고도 그렇게 기억중이었는데"],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        mark_no_work_seed(ctx)
        ctx.search_results = [
            {
                "title": "탐식의 재림 - 웹소설 - 카카오페이지",
                "url": "https://page.kakao.com/content/50219568",
                "content": "탐식의 재림 웹소설 작품 페이지. 작가 로유진. 설지후 유선화 등장.",
            },
            {
                "title": "탐식의 재림",
                "url": "https://series.naver.com/novel/detail.series?productNo=2847498",
                "content": "탐식의 재림 네이버 시리즈 웹소설. 작가 로유진.",
            },
        ]
        verification_result = {
            "is_relevant": True,
            "is_novel_discussion": True,
            "novel_identity": {
                "official_title": title,
                "evidence_type": "search_platform_url",
            },
            "grounding_check": {
                "anchor_found": "character_mention",
                "anchor_text": "설지후, 유선화",
            },
            "relation_judgment": {
                "relation_type": "explicit_alias",
                "discussion_target": "specific_work",
                "promotion_decision": "allow",
                "search_support_summary": {
                    "official_exact_title_count": 2,
                    "alias_in_post_count": 1,
                    "explicit_alias_bridge_count": 3,
                },
            },
        }

        acceptance = pipeline._compute_title_acceptance(ctx, title, verification_result)

        self.assertEqual(acceptance["decision"], "accept")
        self.assertFalse(acceptance["semantic_no_work_block"])
        self.assertTrue(acceptance["strong_body_grounding"])
        self.assertIn("relation_official_alias_bridge", acceptance["notes"])

        no_alias_verification = {
            **verification_result,
            "relation_judgment": {
                **verification_result["relation_judgment"],
                "search_support_summary": {
                    "official_exact_title_count": 2,
                    "alias_in_post_count": 0,
                    "explicit_alias_bridge_count": 0,
                },
            },
        }
        zero_count_acceptance = pipeline._compute_title_acceptance(ctx, title, no_alias_verification)
        self.assertEqual(zero_count_acceptance["decision"], "accept")
        self.assertFalse(zero_count_acceptance["semantic_no_work_block"])
        self.assertIn("relation_official_alias_bridge", zero_count_acceptance["notes"])

        locked_candidate = DetectedTitle(
            official_title=title,
            heretic_url="https://series.naver.com/novel/detail.series?productNo=2847498",
            confidence="High",
            source_tier="official_detail",
            page_type="novel_page",
            content_status="active",
            locked=True,
            reference_role="primary",
        )
        sentence_like_alias_verification = {
            **no_alias_verification,
            "slang_insight": {
                "detected_term": "설지후 변화도 레전드임",
                "decoded_term": "탐식의 재림 (설지후 캐릭터 설정 변화)",
                "decode_verified": True,
                "alias_scope": "work_plus_character",
                "attached_entity_text": "설지후 변화도 레전드임",
                "attached_entity_type": "character",
                "store_in_slang_db": False,
                "store_reason": "sentence_like_alias_surface",
            },
        }
        self.assertFalse(
            pipeline._locked_official_candidate_has_unresolved_alias_risk(
                ctx=ctx,
                candidate=locked_candidate,
                verification_result=sentence_like_alias_verification,
                consistency_flags=["multi_work_title_cleared"],
            )
        )

        no_packet_alias_post = PostInput(
            post_id=11705231,
            title="장갤 설지후 변화도 레전드임",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="설지후 유선화 캐릭터 설정 변화 이야기")],
            comments=["아니 나 예전에 다 읽고도 그렇게 기억중이었는데"],
        )
        no_packet_alias_ctx = ConversationContext(
            post_id=no_packet_alias_post.post_id,
            post_data=pipeline._post_to_dict(no_packet_alias_post),
            comments=no_packet_alias_post.comments,
        )
        mark_no_work_seed(no_packet_alias_ctx)
        no_packet_alias_ctx.search_results = list(ctx.search_results)

        blocked = pipeline._compute_title_acceptance(no_packet_alias_ctx, title, no_alias_verification)
        self.assertEqual(blocked["decision"], "reject")
        self.assertTrue(blocked["semantic_no_work_block"])
        self.assertTrue(
            pipeline._locked_official_candidate_has_unresolved_alias_risk(
                ctx=no_packet_alias_ctx,
                candidate=locked_candidate,
                verification_result=sentence_like_alias_verification,
                consistency_flags=["multi_work_title_cleared"],
            )
        )

    def test_verified_alias_detail_anchor_blocks_title_form_food_parody_prompt(self):
        pipeline = build_pipeline()
        title = "두바이의 쫀득한 여초딩 재벌 9세"
        alias = "두쫀쿠"
        post = PostInput(
            post_id=20010052,
            title="로판속 아카데미 앞 두쫀쿠 가게 사장이 되었다",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="[이미지 OCR] 高校 保健体育"),
                ContentBlock(type="text", text="와 진지하게 월억킥 가능할듯"),
                ContentBlock(type="text", text="빨리 쓰셈 ㄱㄱ"),
                ContentBlock(type="text", text="누가 빨리 연재해"),
            ],
            comments=[
                "중간에 소면 카다이프 써서 사형당하고 완",
                "피스타치오 선물 옵션으로 재벌되기",
                "두바이의 쫀득한 여초딩 재벌 9세 읽었음",
            ],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "context_clues": {
                    "title_as_body_continuation": True,
                    "title_body_joined_text": (
                        "로판속 아카데미 앞 두쫀쿠 가게 사장이 되었다 "
                        "[이미지 OCR] 高校 保健体育 와 진지하게 월억킥 가능할듯"
                    ),
                }
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "discuss_work",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        ctx.search_results = [
            {
                "title": title,
                "url": "https://novelpia.com/novel/419119",
                "content": "자유연재작품 - 여기 두바이인데 왜 두쫀쿠가 없어어어어!!!",
                "query": "두쫀쿠 웹소설 노벨피아",
            },
            {
                "title": "로판 속 2인자가 되었다.",
                "url": "https://novelpia.com/novel/347986",
                "content": "노벨피아 자유연재작품 - 로판 속 2인자가 되었다.",
                "query": "로판속 되었다",
            },
            {
                "title": "로판속 아카데미에서 하렘을?",
                "url": "https://novelpia.com/novel/407819",
                "content": "자유연재작품 - 로판속 아카데미에서 하렘을?",
                "query": "로판속 아카데미 웹소설",
            },
        ]
        verification_result = {
            "is_relevant": True,
            "is_novel_discussion": True,
            "novel_identity": {"official_title": title},
            "slang_insight": {
                "detected_term": alias,
                "canonical_work_alias": alias,
                "decoded_term": title,
                "decode_verified": True,
                "alias_scope": "pure_work_alias",
            },
            "grounding_check": {
                "anchor_found": "title_abbrev_mention",
                "matched_alias": alias,
                "matched_title": title,
            },
            "relation_judgment": {
                "relation_type": "explicit_alias",
                "discussion_target": "specific_work",
                "promotion_decision": "allow",
            },
        }

        self.assertFalse(
            pipeline._has_verified_alias_official_detail_anchor(
                ctx,
                title,
                verification_result=verification_result,
                title_candidates=[],
            )
        )
        self.assertTrue(getattr(ctx, "_verified_alias_title_form_parody_blocked", False))
        self.assertEqual(getattr(ctx, "_verified_alias_title_form_parody_blocked_alias", ""), alias)
        self.assertFalse(
            pipeline._can_promote_title_after_semantic_no_work(
                ctx,
                title,
                source="official_url_recall_gate",
                verification_result=verification_result,
                title_candidates=[],
            )
        )
        self.assertFalse(
            pipeline._should_keep_final_semantic_resolution_after_official_recall_anchor(
                ctx=ctx,
                official_title=title,
                verification_result=verification_result,
                title_candidates=[],
                consistency_flags=[
                    "official_url_recall_gate_recovered",
                    "verified_alias_official_detail_anchor",
                    f"confirmed_alias:{alias}",
                ],
            )
        )
        self.assertFalse(
            pipeline._has_title_body_official_detail_anchor(
                ctx,
                "로판속 아카데미에서 하렘을?",
            )
        )
        self.assertEqual(
            getattr(ctx, "_title_body_title_form_parody_blocked_title", ""),
            "로판속 아카데미에서 하렘을?",
        )
        self.assertFalse(
            pipeline._has_title_body_official_detail_anchor(
                ctx,
                "로판 속 2인자가 되었다.",
            )
        )
        self.assertTrue(getattr(ctx, "_title_body_title_form_parody_blocked", False))
        self.assertEqual(
            getattr(ctx, "_title_body_title_form_parody_blocked_title", ""),
            "로판 속 2인자가 되었다.",
        )
        self.assertFalse(
            pipeline._should_keep_final_semantic_resolution_after_official_recall_anchor(
                ctx=ctx,
                official_title="로판 속 2인자가 되었다.",
                verification_result=verification_result,
                title_candidates=[],
                consistency_flags=[
                    "official_url_recall_gate_recovered",
                    "title_body_official_detail_anchor",
                ],
            )
        )

    def test_title_form_parody_intent_is_directional_and_comment_independent(self):
        pipeline = build_pipeline()
        candidate = "두바이의 쫀득한 여초딩 재벌 9세"
        alias = "두쫀쿠"

        def _ctx(body: str, comments=None):
            post = PostInput(
                post_id=20010067,
                title="로판속 아카데미 앞 두쫀쿠 가게 사장이 되었다",
                author="ㅇㅇ",
                content_blocks=[ContentBlock(type="text", text=body)],
                comments=list(comments or []),
            )
            return ConversationContext(
                post_id=post.post_id,
                post_data=pipeline._post_to_dict(post),
                comments=post.comments,
            )

        reviewed = _ctx(
            "이 작품 진짜 재밌더라 문체도 좋음",
            comments=["누가 써줘", f"{candidate} 읽고 싶다"],
        )
        future_desire = _ctx("이런 거 읽고 싶다 누가 써줘")

        self.assertEqual(
            pipeline._verified_alias_title_form_parody_block_reason(
                ctx=reviewed,
                title=candidate,
                alias=alias,
            ),
            "",
        )
        self.assertEqual(
            pipeline._verified_alias_title_form_parody_block_reason(
                ctx=future_desire,
                title=candidate,
                alias=alias,
            ),
            "title_form_parody_alias_without_work_issue_anchor",
        )
        for ctx in (reviewed, future_desire):
            self.assertEqual(
                pipeline._title_body_title_form_parody_block_reason(
                    ctx=ctx,
                    title="로판속 아카데미에서 하렘을?",
                ),
                "title_body_generic_title_form_parody_without_work_issue_anchor",
            )

    def test_verified_alias_detail_anchor_does_not_override_meta_platform_no_work_state(self):
        pipeline = build_pipeline()
        title = "괴담 호텔 탈출기"
        post = PostInput(
            post_id=20010003,
            title="오늘 담텔기 오냐?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="아님 12시 넘어서 내일 새벽에 오냐")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)
        ctx.discourse_warning = "non_novel(meta_platform,high)"
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "ask_question",
                    "target_kind": "platform",
                    "primary_domain": "meta_platform",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        ctx.search_results = [
            {
                "title": title,
                "url": "https://novelpia.com/novel/102155",
                "content": "괴담 호텔 탈출기 웹소설 작품 페이지",
            }
        ]
        verification_result = {
            "is_relevant": True,
            "is_novel_discussion": True,
            "slang_insight": {
                "detected_term": "담텔기",
                "canonical_work_alias": "담텔기",
                "decoded_term": title,
                "decode_verified": True,
                "alias_scope": "pure_work_alias",
            },
            "grounding_check": {"anchor_found": "title_abbrev_mention", "matched_alias": "담텔기"},
            "relation_judgment": {
                "relation_type": "work_specific_nickname",
                "discussion_target": "specific_work",
                "promotion_decision": "allow",
            },
            "novel_identity": {"official_title": title},
        }

        self.assertFalse(
            pipeline._can_promote_title_after_semantic_no_work(
                ctx,
                title,
                source="official_url_recall_gate",
                verification_result=verification_result,
                title_candidates=[],
            )
        )
        self.assertEqual(getattr(ctx, "_verified_alias_official_detail_anchor_alias", ""), "담텔기")

    def test_relation_judge_recovers_character_cluster_with_official_detail(self):
        verifier = VerifierExpert(llm_client=DummyLLM())
        title = "괴담 호텔 탈출기"
        url = "https://novelpia.com/novel/102155"
        relation = {
            "relation_type": "thematic_overlap_only",
            "discussion_target": "mixed_or_uncertain",
            "promotion_decision": "hold",
            "confidence": "medium",
            "reason": "작품명을 직접 언급하지 않았으나 캐릭터/설정 cluster가 후보 작품과 겹침",
            "key_evidence": ["아리", "가인", "파이어오니파티"],
            "evidence_summary": {
                "total_items": 6,
                "official_detail_count": 6,
                "community_post_count": 0,
                "listing_or_category_count": 0,
                "explicit_alias_bridge_count": 0,
            },
            "search_support_summary": {
                "official_exact_title_count": 8,
                "support_channel_count": 1,
                "best_official_url": url,
                "converged_official_signal": False,
                "related_anchor_hit_count": 0,
            },
            "post_direct_grounding": False,
        }
        verification = {
            "is_relevant": False,
            "is_novel_discussion": False,
            "grounding_check": {
                "decoder_grounded": True,
                "anchor_found": "character_mention",
                "anchor_text": "부등변은 가인이가 준거자너",
            },
            "counter_arguments": [],
            "rejection_reason": "명시적 제목 브리지가 없어 hold",
        }
        novel_id = {
            "official_novel_title": title,
            "official_title": title,
            "heretic_url": url,
            "confidence": "Low",
        }

        verifier._apply_relation_judgment(relation, verification, novel_id)

        relation_judgment = verification["relation_judgment"]
        self.assertTrue(verification["is_relevant"])
        self.assertTrue(verification["is_novel_discussion"])
        self.assertIsNone(verification["rejection_reason"])
        self.assertEqual(novel_id["official_novel_title"], title)
        self.assertEqual(novel_id["official_title"], title)
        self.assertEqual(novel_id["heretic_url"], url)
        self.assertEqual(relation_judgment["relation_type"], "work_specific_nickname")
        self.assertEqual(relation_judgment["discussion_target"], "specific_work")
        self.assertEqual(relation_judgment["promotion_decision"], "hold")
        self.assertIn("캐릭터/설정 앵커", verification["relation_hold_reason"])
        self.assertEqual(verification["counter_arguments"][-1]["action"], "note_only")

    def test_relation_judge_keeps_weak_character_overlap_unresolved(self):
        verifier = VerifierExpert(llm_client=DummyLLM())
        relation = {
            "relation_type": "thematic_overlap_only",
            "discussion_target": "mixed_or_uncertain",
            "promotion_decision": "hold",
            "confidence": "low",
            "reason": "인물명 일부만 후보와 겹침",
            "key_evidence": ["아리"],
            "evidence_summary": {
                "total_items": 2,
                "official_detail_count": 1,
                "community_post_count": 0,
                "listing_or_category_count": 1,
                "explicit_alias_bridge_count": 0,
            },
            "search_support_summary": {
                "official_exact_title_count": 0,
                "support_channel_count": 1,
                "best_official_url": "",
                "converged_official_signal": False,
                "related_anchor_hit_count": 0,
            },
            "post_direct_grounding": False,
        }
        verification = {
            "is_relevant": False,
            "is_novel_discussion": False,
            "grounding_check": {
                "decoder_grounded": True,
                "anchor_found": "character_mention",
                "anchor_text": "아리",
            },
            "counter_arguments": [],
            "rejection_reason": "명시적 제목 브리지가 없어 hold",
        }
        novel_id = {
            "official_novel_title": "괴담 호텔 탈출기",
            "official_title": "괴담 호텔 탈출기",
            "heretic_url": "https://novelpia.com/novel/102155",
            "confidence": "Low",
        }

        verifier._apply_relation_judgment(relation, verification, novel_id)

        self.assertFalse(verification["is_relevant"])
        self.assertFalse(verification["is_novel_discussion"])
        self.assertIsNone(novel_id["official_novel_title"])
        self.assertIsNone(novel_id["official_title"])
        self.assertIsNone(novel_id["heretic_url"])
        self.assertEqual(verification["counter_arguments"][-1]["action"], "nullify_title")

    def test_relation_judge_exact_title_direct_official_support_is_not_hard_hold(self):
        verifier = VerifierExpert(llm_client=DummyLLM())
        title = "테라포밍"
        url = "https://novelpia.com/novel/61947"
        relation = {
            "relation_type": "exact_title",
            "discussion_target": "specific_work",
            "promotion_decision": "hold",
            "confidence": "medium",
            "reason": "일반 명사 가능성 때문에 보류",
            "key_evidence": ["게시글 제목 '테라포밍 볼만함?'"],
            "evidence_summary": {
                "official_detail_count": 1,
                "explicit_alias_bridge_count": 0,
            },
            "search_support_summary": {
                "official_exact_title_count": 1,
                "alias_in_post_count": 1,
                "best_official_url": url,
                "converged_official_signal": True,
                "explicit_alias_bridge_count": 0,
            },
            "post_direct_grounding": True,
        }
        verification = {
            "is_relevant": True,
            "is_novel_discussion": True,
            "grounding_check": {
                "decoder_grounded": True,
                "anchor_found": "title_mention",
                "anchor_text": title,
                "title_abbrev_mentioned": True,
                "matched_alias": title,
            },
            "counter_arguments": [],
            "rejection_reason": None,
        }
        novel_id = {
            "official_novel_title": title,
            "official_title": title,
            "heretic_url": url,
            "confidence": "High",
        }

        verifier._apply_relation_judgment(relation, verification, novel_id)

        self.assertTrue(verification["is_relevant"])
        self.assertTrue(verification["is_novel_discussion"])
        self.assertEqual(novel_id["official_novel_title"], title)
        self.assertEqual(novel_id["official_title"], title)
        self.assertEqual(novel_id["heretic_url"], url)
        self.assertEqual(verification["relation_judgment"]["relation_type"], "exact_title")
        self.assertEqual(verification["relation_judgment"]["discussion_target"], "specific_work")
        self.assertEqual(verification["relation_judgment"]["promotion_decision"], "allow")
        self.assertFalse(
            any(arg.get("action") == "nullify_title" for arg in verification["counter_arguments"])
        )

    def test_relation_judge_thematic_hold_with_direct_official_title_surface_allows(self):
        verifier = VerifierExpert(llm_client=DummyLLM())
        title = "테라포밍"
        url = "https://novelpia.com/novel/61947"
        relation = {
            "relation_type": "thematic_overlap_only",
            "discussion_target": "mixed_or_uncertain",
            "promotion_decision": "hold",
            "confidence": "medium",
            "reason": "일반 명사 가능성 때문에 보류",
            "key_evidence": ["게시글 제목 '테라포밍 볼만함?'"],
            "evidence_summary": {
                "official_detail_count": 6,
                "explicit_alias_bridge_count": 0,
            },
            "search_support_summary": {
                "official_exact_title_count": 11,
                "alias_in_post_count": 1,
                "best_official_url": url,
                "converged_official_signal": True,
                "explicit_alias_bridge_count": 0,
            },
            "post_direct_grounding": True,
            "generic_relation_only": False,
        }
        verification = {
            "is_relevant": False,
            "is_novel_discussion": False,
            "grounding_check": {
                "decoder_grounded": True,
                "anchor_found": "title_mention",
                "anchor_text": title,
                "title_abbrev_mentioned": True,
                "matched_alias": title,
            },
            "counter_arguments": [],
            "rejection_reason": "명시적 브리지가 부족하여 hold",
        }
        novel_id = {
            "official_novel_title": title,
            "official_title": title,
            "heretic_url": url,
            "confidence": "High",
        }

        verifier._apply_relation_judgment(relation, verification, novel_id)

        self.assertTrue(verification["is_relevant"])
        self.assertTrue(verification["is_novel_discussion"])
        self.assertIsNone(verification["rejection_reason"])
        self.assertEqual(novel_id["official_novel_title"], title)
        self.assertEqual(novel_id["official_title"], title)
        self.assertEqual(novel_id["heretic_url"], url)
        self.assertEqual(verification["relation_judgment"]["relation_type"], "exact_title")
        self.assertEqual(verification["relation_judgment"]["discussion_target"], "specific_work")
        self.assertEqual(verification["relation_judgment"]["promotion_decision"], "allow")
        self.assertFalse(
            any(arg.get("action") == "nullify_title" for arg in verification["counter_arguments"])
        )

    def test_relation_judge_exact_title_search_only_still_holds_candidate(self):
        verifier = VerifierExpert(llm_client=DummyLLM())
        title = "테라포밍"
        url = "https://novelpia.com/novel/61947"
        relation = {
            "relation_type": "exact_title",
            "discussion_target": "specific_work",
            "promotion_decision": "hold",
            "confidence": "medium",
            "reason": "검색 결과에서만 제목이 확인됨",
            "evidence_summary": {
                "official_detail_count": 1,
                "explicit_alias_bridge_count": 0,
            },
            "search_support_summary": {
                "official_exact_title_count": 1,
                "alias_in_post_count": 1,
                "best_official_url": url,
                "converged_official_signal": True,
                "explicit_alias_bridge_count": 0,
            },
            "post_direct_grounding": False,
        }
        verification = {
            "is_relevant": False,
            "is_novel_discussion": False,
            "grounding_check": {
                "decoder_grounded": True,
                "anchor_found": "search_only",
                "anchor_text": "",
            },
            "counter_arguments": [],
            "rejection_reason": "원문 직접 근거 없음",
        }
        novel_id = {
            "official_novel_title": title,
            "official_title": title,
            "heretic_url": url,
            "confidence": "Low",
        }

        verifier._apply_relation_judgment(relation, verification, novel_id)

        self.assertFalse(verification["is_relevant"])
        self.assertFalse(verification["is_novel_discussion"])
        self.assertIsNone(novel_id["official_novel_title"])
        self.assertIsNone(novel_id["official_title"])
        self.assertIsNone(novel_id["heretic_url"])
        self.assertEqual(verification["counter_arguments"][-1]["action"], "nullify_title")

    def test_relation_support_counts_community_alias_by_domain_without_page_type(self):
        verifier = VerifierExpert(llm_client=DummyLLM())
        summary = verifier._build_relation_search_support_summary(
            "황제폐하가 웹소설 작가임을 숨김",
            ["황제분충"],
            [
                {
                    "title": "장르소설 마이너 갤러리 - 황제분충 오늘도 맛있엇다",
                    "url": "https://m.dcinside.com/board/genrenovel/11774966",
                    "content": "황제분충은 연재주기랑 필력만 좀 좋앗음",
                },
                {
                    "title": "황제폐하가 웹소설 작가임을 숨김 짧은 리뷰",
                    "url": "https://arca.live/b/novelchannel/156565543",
                    "content": "황제분충 황제 필력이 거의 고금제일 수준인듯",
                },
                {
                    "title": "웹소설로 꿈꾸는 세상! - 황제폐하가 웹소설 작가임을 숨김 - 노벨피아",
                    "url": "https://novelpia.com/novel/385635",
                    "content": "[ 황제폐하가 웹소설 작가임을 숨김 ]",
                    "_purpose": "author_verify",
                },
            ],
            post={"title": "황제분충 ㄱㅊ함?", "content_blocks": [{"text": "문피안가"}]},
            comments=["노피아"],
        )

        self.assertEqual(summary["official_exact_title_count"], 1)
        self.assertEqual(summary["community_alias_support_count"], 2)
        self.assertEqual(summary["alias_in_post_count"], 1)
        self.assertEqual(summary["best_official_url"], "https://novelpia.com/novel/385635")

    def test_relation_judge_preserves_short_alias_with_official_and_community_support(self):
        verifier = VerifierExpert(llm_client=DummyLLM())
        title = "황제폐하가 웹소설 작가임을 숨김"
        url = "https://novelpia.com/novel/385635"
        relation = {
            "relation_type": "thematic_overlap_only",
            "discussion_target": "mixed_or_uncertain",
            "promotion_decision": "hold",
            "confidence": "medium",
            "reason": "명시적 별칭 등식은 부족하지만 검색상 작품 밈으로 반복됨",
            "key_evidence": ["황제분충"],
            "observed_aliases": ["황제분충"],
            "evidence_summary": {
                "total_items": 6,
                "official_detail_count": 2,
                "community_post_count": 0,
                "listing_or_category_count": 0,
                "explicit_alias_bridge_count": 0,
            },
            "search_support_summary": {
                "official_exact_title_count": 1,
                "official_alias_context_count": 0,
                "community_alias_support_count": 2,
                "explicit_alias_bridge_count": 0,
                "support_channel_count": 1,
                "alias_in_post_count": 1,
                "best_official_url": url,
                "converged_official_signal": True,
            },
            "post_direct_grounding": False,
        }
        verification = {
            "is_relevant": False,
            "is_novel_discussion": False,
            "grounding_check": {
                "decoder_grounded": True,
                "anchor_found": "title_mention",
                "title_abbrev_mentioned": True,
                "matched_alias": "황제분충",
            },
            "slang_insight": {
                "detected_term": "황제분충",
                "canonical_work_alias": "황제분충",
                "decoded_term": title,
                "decode_verified": True,
                "alias_scope": "pure_work_alias",
            },
            "counter_arguments": [],
            "rejection_reason": "명시적 alias bridge 부족",
        }
        novel_id = {
            "official_novel_title": title,
            "official_title": title,
            "heretic_url": url,
            "confidence": "Low",
        }

        verifier._apply_relation_judgment(relation, verification, novel_id)

        self.assertTrue(verification["is_relevant"])
        self.assertTrue(verification["is_novel_discussion"])
        self.assertIsNone(verification["rejection_reason"])
        self.assertEqual(novel_id["official_novel_title"], title)
        self.assertEqual(novel_id["official_title"], title)
        self.assertEqual(novel_id["heretic_url"], url)
        self.assertEqual(verification["relation_judgment"]["relation_type"], "work_specific_nickname")
        self.assertEqual(verification["relation_judgment"]["discussion_target"], "specific_work")
        self.assertEqual(verification["relation_judgment"]["promotion_decision"], "hold")
        self.assertEqual(verification["counter_arguments"][-1]["action"], "note_only")

    def test_relation_aliases_include_snippet_abbreviation_mapping(self):
        verifier = VerifierExpert(llm_client=DummyLLM())
        title = "헌터갤러리의 국가권력급 기계공주"
        ctx = type("Ctx", (), {})()
        ctx.snippet_hints = {
            "abbreviation_hints": [
                {"abbrev": "기계공주", "full": title},
            ]
        }

        aliases = verifier._collect_relation_aliases(
            title,
            {
                "title": "기계공주 이제 슬슬 갤에서 말한대로 가는건가",
                "content_blocks": [{"text": "곧 대가리똑딱당하겠노"}],
            },
            [],
            {
                "decoded_terms": [
                    {
                        "original": "기계공주 이제 슬슬 갤에서 말한대로 가는건가",
                        "best_match": {"title": title},
                        "grounding": {"anchor_type": "title_mention"},
                    }
                ]
            },
            {
                "grounding_check": {
                    "matched_alias": "기계공주 이제 슬슬 갤에서 말한대로 가는건가",
                    "title_abbrev_mentioned": True,
                }
            },
            ctx=ctx,
        )

        self.assertIn("기계공주", aliases)

    def test_relation_support_counts_candidate_page_alias_phrase(self):
        verifier = VerifierExpert(llm_client=DummyLLM())
        title = "헌터갤러리의 국가권력급 기계공주"
        url = "https://novelpia.com/novel/390228"

        summary = verifier._build_relation_search_support_summary(
            title,
            ["기계공주"],
            [
                {
                    "title": "웹소설로 꿈꾸는 세상! - 헌터갤러리의 국가권력급 기계공주 - 노벨피아",
                    "url": url,
                    "content": "플러스작품 - 오랜만에 욕조에 몸이나 담글까 했더니.",
                    "_purpose": "title_anchor_official_probe",
                },
                {
                    "title": "헌터갤러리의 국가권력급 기계공주 - 나무위키",
                    "url": "https://namu.wiki/w/%ED%97%8C%ED%84%B0%EA%B0%A4%EB%9F%AC%EB%A6%AC%EC%9D%98",
                    "content": "한국의 현대 판타지 웹소설. 약칭은 기계공주이며 작가는 쟈장가이다.",
                    "_purpose": "title_anchor_official_probe",
                },
            ],
            post={
                "title": "기계공주 이제 슬슬 갤에서 말한대로 가는건가",
                "content_blocks": [{"text": "곧 대가리똑딱당하겠노"}],
            },
            comments=[],
        )

        self.assertEqual(summary["official_exact_title_count"], 1)
        self.assertEqual(summary["alias_in_post_count"], 1)
        self.assertEqual(summary["explicit_alias_bridge_count"], 1)
        self.assertEqual(summary["best_official_url"], url)

    def test_relation_judge_preserves_short_alias_with_official_wiki_alias_bridge(self):
        verifier = VerifierExpert(llm_client=DummyLLM())
        title = "헌터갤러리의 국가권력급 기계공주"
        url = "https://novelpia.com/novel/390228"
        relation = {
            "relation_type": "thematic_overlap_only",
            "discussion_target": "mixed_or_uncertain",
            "promotion_decision": "hold",
            "confidence": "medium",
            "reason": "명시적 브리지가 부족하다고 판단함",
            "key_evidence": ["기계공주"],
            "observed_aliases": ["기계공주"],
            "evidence_summary": {
                "total_items": 4,
                "official_detail_count": 1,
                "community_post_count": 0,
                "listing_or_category_count": 0,
                "explicit_alias_bridge_count": 1,
            },
            "search_support_summary": {
                "official_exact_title_count": 1,
                "official_alias_context_count": 0,
                "community_alias_support_count": 0,
                "explicit_alias_bridge_count": 1,
                "support_channel_count": 1,
                "alias_in_post_count": 1,
                "best_official_url": url,
                "converged_official_signal": False,
            },
            "post_direct_grounding": False,
        }
        verification = {
            "is_relevant": False,
            "is_novel_discussion": False,
            "grounding_check": {
                "decoder_grounded": True,
                "anchor_found": "title_mention",
                "title_abbrev_mentioned": True,
                "matched_alias": "기계공주",
            },
            "slang_insight": {
                "detected_term": "기계공주",
                "canonical_work_alias": "기계공주",
                "decoded_term": title,
                "decode_verified": True,
                "alias_scope": "pure_work_alias",
            },
            "counter_arguments": [],
            "rejection_reason": "명시적 alias bridge 부족",
        }
        novel_id = {
            "official_novel_title": title,
            "official_title": title,
            "heretic_url": url,
            "confidence": "Low",
        }

        verifier._apply_relation_judgment(relation, verification, novel_id)

        self.assertTrue(verification["is_relevant"])
        self.assertTrue(verification["is_novel_discussion"])
        self.assertIsNone(verification["rejection_reason"])
        self.assertEqual(novel_id["official_novel_title"], title)
        self.assertEqual(novel_id["official_title"], title)
        self.assertEqual(novel_id["heretic_url"], url)
        self.assertEqual(verification["relation_judgment"]["relation_type"], "work_specific_nickname")
        self.assertEqual(verification["relation_judgment"]["discussion_target"], "specific_work")
        self.assertEqual(verification["relation_judgment"]["promotion_decision"], "hold")
        self.assertEqual(verification["counter_arguments"][-1]["action"], "note_only")

    def test_relation_alias_official_detail_lock_protects_verifier_title(self):
        pipeline = build_pipeline()
        title = "황제폐하가 웹소설 작가임을 숨김"
        post = PostInput(
            post_id=11706832,
            title="황제분충 ㄱㅊ함?",
            author="기계새",
            content_blocks=[ContentBlock(type="text", text="문피안가")],
            comments=["노피아", "ㅇㅇ, 노피아", "표절물인가"],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        vf_result = {
            "novel_identity": {
                "official_novel_title": title,
                "heretic_url": "https://novelpia.com/novel/385635",
                "evidence_type": "search_platform_url",
            },
            "grounding_check": {
                "anchor_found": "title_mention",
                "title_abbrev_mentioned": True,
                "matched_alias": "황제분충",
            },
            "slang_insight": {
                "detected_term": "황제분충",
                "canonical_work_alias": "황제분충",
                "decoded_term": title,
                "decode_verified": True,
                "alias_scope": "pure_work_alias",
            },
            "relation_judgment": {
                "relation_type": "work_specific_nickname",
                "discussion_target": "specific_work",
                "promotion_decision": "hold",
                "search_support_summary": {
                    "official_exact_title_count": 1,
                    "community_alias_support_count": 11,
                    "alias_in_post_count": 1,
                    "best_official_url": "https://novelpia.com/novel/385635",
                    "converged_official_signal": True,
                },
            },
        }

        self.assertTrue(
            pipeline._has_relation_alias_official_detail_lock(ctx, title, vf_result)
        )
        self.assertFalse(
            pipeline._relation_hold_should_block_title_resolution(
                ctx=ctx,
                official_title=title,
                verification_result=vf_result,
            )
        )

    def test_verified_contextual_alias_work_bridge_unblocks_relation_hold(self):
        pipeline = build_pipeline()
        title = "이세계에서 사이비로 살아남기"
        post = PostInput(
            post_id=11694019,
            title="미츄리 혼후순결에서 하인들에게도 멸시당한게 고증에 맞는거였구나",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(
                    type="text",
                    text="아내가 혼후순결 요구해서 섹스 안하니까 집안 하인들도 멸시하는 장면 얘기",
                )
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.search_results = [
            {
                "title": "이세계에서 사이비로 살아남기 - 나무위키",
                "url": "https://namu.wiki/w/example",
                "content": "대한민국의 성인 퓨전 판타지 웹소설. 작가는 미츄리. 혼후순결이라는 개념이 등장한다.",
            },
            {
                "title": "미츄리의 신신신신작, 이세계에서 사이비로 살아남기",
                "url": "https://arca.live/b/novelchannel/77980889",
                "content": "혼전혼후 순결 설정을 다루는 장르소설 채널 글",
            },
        ]
        vf_result = {
            "novel_identity": {
                "official_novel_title": title,
                "evidence_type": "community_mention",
            },
            "grounding_check": {
                "anchor_found": "title_mention",
                "anchor_text": "미츄리",
                "matched_alias": "미츄리",
                "title_abbrev_mentioned": True,
            },
            "slang_insight": {
                "detected_term": "미츄리",
                "canonical_work_alias": "미츄리",
                "decoded_term": f"{title} (작가: 미츄리)",
                "decode_verified": True,
                "alias_scope": "pure_work_alias",
                "attached_entity_type": "work_plus_character",
            },
            "relation_judgment": {
                "relation_type": "work_specific_nickname",
                "discussion_target": "specific_work",
                "promotion_decision": "hold",
                "observed_aliases": ["미츄리"],
                "post_direct_grounding": False,
                "search_support_summary": {
                    "community_alias_support_count": 2,
                    "explicit_alias_bridge_count": 1,
                    "alias_in_post_count": 1,
                    "converged_official_signal": False,
                    "closed_bridge": False,
                },
            },
        }

        self.assertTrue(
            pipeline._has_verified_contextual_alias_work_bridge(ctx, title, vf_result)
        )
        self.assertTrue(
            pipeline._post_discusses_work_as_work(
                ctx,
                title,
                source="verified_contextual_alias_work_bridge",
                verification_result=vf_result,
            )
        )
        self.assertFalse(
            pipeline._relation_hold_should_block_title_resolution(
                ctx=ctx,
                official_title=title,
                verification_result=vf_result,
            )
        )

    def test_character_parenthetical_bridge_unblocks_relation_hold_for_setting_discussion(self):
        pipeline = build_pipeline()
        title = "괴담 호텔 탈출기"
        post = PostInput(
            post_id=11702090,
            title="애초에 한가인이 아리한테 부등변 준 이유가",
            author="WildFlower",
            content_blocks=[
                ContentBlock(
                    type="text",
                    text="아직 깨달음 부족할때 정신 와리가리 하니까 자기 브레이크 걸어달라고 준건데",
                ),
                ContentBlock(
                    type="text",
                    text="누구한테 준건진 뭐 의미없지 상현쌤 줬어도 제대로 못썼다고 하니까",
                ),
            ],
            comments=["아리는 브레이크 걸기에는 너무 약해"],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        ctx.search_results = [
            {
                "title": "한가인(괴담 호텔 탈출기) - 나무위키",
                "url": "https://namu.wiki/w/%ED%95%9C%EA%B0%80%EC%9D%B8(%EA%B4%B4%EB%8B%B4%20%ED%98%B8%ED%85%94%20%ED%83%88%EC%B6%9C%EA%B8%B0)",
                "content": "한가인은 괴담 호텔 탈출기의 등장인물이다. 아리와 부등변 설정이 함께 언급된다.",
            },
            {
                "title": "마지막 황녀, 아리 연 - 웹소설",
                "url": "https://page.kakao.com/content/47822679",
                "content": "아리 연이라는 다른 작품 상세.",
            },
        ]
        vf_result = {
            "is_relevant": True,
            "is_novel_discussion": True,
            "novel_identity": {
                "official_novel_title": title,
                "official_title": title,
                "heretic_url": "https://namu.wiki/w/%ED%95%9C%EA%B0%80%EC%9D%B8(%EA%B4%B4%EB%8B%B4%20%ED%98%B8%ED%85%94%20%ED%83%88%EC%B6%9C%EA%B8%B0)",
                "confidence": "High",
                "evidence_type": "wiki",
            },
            "grounding_check": {
                "decoder_grounded": True,
                "anchor_found": "character_mention",
                "anchor_text": "한가인, 아리, 부등변",
            },
            "relation_judgment": {
                "relation_type": "work_specific_nickname",
                "discussion_target": "specific_work",
                "promotion_decision": "hold",
                "post_direct_grounding": False,
                "search_support_summary": {
                    "official_exact_title_count": 0,
                    "official_alias_context_count": 2,
                    "community_alias_support_count": 2,
                    "explicit_alias_bridge_count": 0,
                    "alias_in_post_count": 1,
                    "support_channel_count": 1,
                    "bridge_quality": "character_parenthetical",
                    "closed_bridge": True,
                    "character_context_match_count": 1,
                    "matched_related_anchor_terms": ["한가인"],
                },
            },
        }

        self.assertTrue(pipeline._has_specific_character_parenthetical_work_link(ctx, title))
        self.assertFalse(
            pipeline._relation_hold_should_block_title_resolution(
                ctx=ctx,
                official_title=title,
                verification_result=vf_result,
            )
        )
        self.assertTrue(
            pipeline._relation_hold_should_block_title_resolution(
                ctx=ctx,
                official_title="마지막 황녀, 아리 연",
                verification_result=vf_result,
            )
        )

    def test_verified_contextual_alias_work_bridge_requires_post_specific_anchor(self):
        pipeline = build_pipeline()
        title = "이세계에서 사이비로 살아남기"
        post = PostInput(
            post_id=11694019,
            title="미츄리 그냥 재밌음",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="작품 고유 설정 없이 작가명만 언급")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.search_results = [
            {
                "title": "미츄리의 신신신신작, 이세계에서 사이비로 살아남기",
                "url": "https://arca.live/b/novelchannel/77980889",
                "content": "작가는 미츄리라는 일반 소개만 있는 글",
            }
        ]
        vf_result = {
            "novel_identity": {"official_novel_title": title, "evidence_type": "community_mention"},
            "grounding_check": {"anchor_found": "title_mention", "matched_alias": "미츄리"},
            "slang_insight": {
                "detected_term": "미츄리",
                "canonical_work_alias": "미츄리",
                "decoded_term": title,
                "decode_verified": True,
                "alias_scope": "pure_work_alias",
            },
            "relation_judgment": {
                "relation_type": "work_specific_nickname",
                "discussion_target": "specific_work",
                "promotion_decision": "hold",
                "observed_aliases": ["미츄리"],
                "post_direct_grounding": False,
                "search_support_summary": {
                    "community_alias_support_count": 1,
                    "explicit_alias_bridge_count": 1,
                    "alias_in_post_count": 1,
                    "converged_official_signal": False,
                },
            },
        }

        self.assertFalse(
            pipeline._has_verified_contextual_alias_work_bridge(ctx, title, vf_result)
        )
        self.assertFalse(
            pipeline._post_discusses_work_as_work(
                ctx,
                title,
                source="verified_contextual_alias_work_bridge",
                verification_result=vf_result,
            )
        )
        self.assertTrue(
            pipeline._relation_hold_should_block_title_resolution(
                ctx=ctx,
                official_title=title,
                verification_result=vf_result,
            )
        )

    def test_verified_contextual_alias_work_bridge_allows_relation_allow_without_extra_anchor(self):
        pipeline = build_pipeline()
        title = "이세계에서 사이비로 살아남기"
        post = PostInput(
            post_id=11694019,
            title="미츄리 혼후순결 좋았음",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="작품 고증 얘기")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.search_results = [
            {
                "title": "미츄리의 신신신신작, 이세계에서 사이비로 살아남기",
                "url": "https://arca.live/b/novelchannel/77980889",
                "content": "작가는 미츄리이며 혼후순결 설정을 다룬다.",
            }
        ]
        vf_result = {
            "slang_insight": {
                "detected_term": "미츄리",
                "canonical_work_alias": "미츄리",
                "decoded_term": title,
                "decode_verified": True,
                "alias_scope": "work_plus_author",
            },
            "relation_judgment": {
                "relation_type": "explicit_alias",
                "discussion_target": "specific_work",
                "promotion_decision": "allow",
                "observed_aliases": ["미츄리", "혼후순결"],
                "post_direct_grounding": False,
                "search_support_summary": {
                    "community_alias_support_count": 1,
                    "explicit_alias_bridge_count": 1,
                    "alias_in_post_count": 2,
                    "converged_official_signal": False,
                },
            },
        }

        self.assertTrue(
            pipeline._has_verified_contextual_alias_work_bridge(ctx, title, vf_result)
        )
        self.assertTrue(
            pipeline._post_discusses_work_as_work(
                ctx,
                title,
                source="verified_contextual_alias_work_bridge",
                verification_result=vf_result,
            )
        )

    def test_contextual_alias_official_detail_lock_handles_author_plus_setting_bridge(self):
        pipeline = build_pipeline()
        title = "이세계에서 사이비로 살아남기"
        post = PostInput(
            post_id=11694019,
            title="미츄리 혼후순결에서 하인들에게도 멸시당한게 고증에 맞는거였구나",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(
                    type="text",
                    text="아내가 혼후순결 요구해서 섹스 안하니까 집안 하인들도 멸시하는데",
                )
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.search_results = [
            {
                "title": "이세계에서 사이비로 살아남기 (r96 판) - 나무위키",
                "url": "https://namu.wiki/w/example",
                "content": "노벨피아에서 연재하였다. 혼후순결이라는 개념이 등장한다.",
            },
            {
                "title": "미츄리의 신신신신작, 이세계에서 사이비로 살아남기",
                "url": "https://arca.live/b/novelchannel/77980889",
                "content": "혼전혼후 순결 설정을 다루는 장르소설 채널 글",
            },
            {
                "title": "이세계에서 사이비로 살아남기",
                "url": "https://novelpia.com/novel/181771",
                "content": "암흑 시대의 사이비 대주교가 되어 있었다. 저 미츄리에게 저작권이 있다.",
            },
        ]
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "decoded_terms": [
                    {
                        "original": "미츄리",
                        "best_match": {"title": title, "confidence": "high"},
                        "candidates": [{"official_novel_title": title}],
                    }
                ]
            },
        )
        vf_result = {
            "relation_judgment": {
                "relation_type": "work_specific_nickname",
                "discussion_target": "specific_work",
                "promotion_decision": "hold",
                "post_direct_grounding": False,
                "search_support_summary": {
                    "community_alias_support_count": 0,
                    "explicit_alias_bridge_count": 0,
                    "alias_in_post_count": 0,
                },
            },
        }

        self.assertTrue(
            pipeline._has_contextual_alias_official_detail_lock(ctx, title, vf_result)
        )
        self.assertFalse(
            pipeline._relation_hold_should_block_title_resolution(
                ctx=ctx,
                official_title=title,
                verification_result=vf_result,
            )
        )

    def test_contextual_alias_official_detail_lock_accepts_catalog_bridge_without_platform_detail(self):
        pipeline = build_pipeline()
        title = "이세계에서 사이비로 살아남기"
        post = PostInput(
            post_id=11694019,
            title="미츄리 혼후순결에서 하인들에게도 멸시당한게 고증에 맞는거였구나",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="혼후순결 고증 얘기")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.search_results = [
            {
                "title": "이세계에서 사이비로 살아남기 - 나무위키",
                "url": "https://namu.wiki/w/example",
                "content": "혼후순결이라는 개념이 등장한다. 작가는 미츄리.",
            },
            {
                "title": "미츄리의 신신신신작, 이세계에서 사이비로 살아남기",
                "url": "https://arca.live/b/novelchannel/77980889",
                "content": "혼전혼후 순결 설정을 다루는 글",
            },
        ]
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "decoded_terms": [
                    {
                        "original": "미츄리",
                        "best_match": {"title": title, "confidence": "high"},
                        "candidates": [{"official_novel_title": title}],
                    }
                ]
            },
        )

        self.assertTrue(
            pipeline._has_contextual_alias_official_detail_lock(ctx, title, {})
        )

    def test_contextual_alias_official_detail_lock_requires_catalog_alias_without_platform_detail(self):
        pipeline = build_pipeline()
        title = "이세계에서 사이비로 살아남기"
        post = PostInput(
            post_id=11694019,
            title="미츄리 혼후순결에서 하인들에게도 멸시당한게 고증에 맞는거였구나",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="혼후순결 고증 얘기")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.search_results = [
            {
                "title": "이세계에서 사이비로 살아남기 - 나무위키",
                "url": "https://namu.wiki/w/example",
                "content": "혼후순결이라는 개념이 등장한다.",
            },
            {
                "title": "혼후순결 설정 정리",
                "url": "https://arca.live/b/novelchannel/77980889",
                "content": "혼전혼후 순결 설정을 다루는 글",
            },
        ]
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "decoded_terms": [
                    {
                        "original": "미츄리",
                        "best_match": {"title": title, "confidence": "high"},
                        "candidates": [{"official_novel_title": title}],
                    }
                ]
            },
        )

        self.assertFalse(
            pipeline._has_contextual_alias_official_detail_lock(ctx, title, {})
        )

    def test_precision_guard_preserves_contextual_catalog_alias_bridge(self):
        pipeline = build_pipeline()
        title = "이세계에서 사이비로 살아남기"
        post = PostInput(
            post_id=11694019,
            title="미츄리 혼후순결에서 하인들에게도 멸시당한게 고증에 맞는거였구나",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="혼후순결 고증 얘기")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.search_results = [
            {
                "title": "미츄리의 신신신신작, 이세계에서 사이비로 살아남기",
                "url": "https://arca.live/b/novelchannel/77980889",
                "source_tier": "community",
                "content": "혼전혼후 순결 설정을 다루는 장르소설 채널 글",
            },
            {
                "title": "이세계에서 사이비로 살아남기 - 나무위키",
                "url": "https://namu.wiki/w/example",
                "source_tier": "wiki",
                "content": "혼후순결이라는 개념이 등장한다.",
            },
        ]
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "decoded_terms": [
                    {
                        "original": "미츄리",
                        "best_match": {"title": title, "confidence": "high"},
                        "candidates": [{"official_novel_title": title}],
                    }
                ]
            },
        )

        picked, confidence, flags = pipeline._guard_official_title_precision(
            ctx=ctx,
            official_title=title,
            confidence="High",
            title_candidates=[DetectedTitle(official_title=title, confidence="High", source_tier="community")],
            vf_result={"grounding_check": {"anchor_found": "title_mention"}},
        )

        self.assertEqual(picked, title)
        self.assertEqual(confidence, "High")
        self.assertNotIn("title_precision_downgrade", flags)

    def test_precision_guard_still_downgrades_catalog_context_without_alias(self):
        pipeline = build_pipeline()
        title = "이세계에서 사이비로 살아남기"
        post = PostInput(
            post_id=11694019,
            title="미츄리 혼후순결에서 하인들에게도 멸시당한게 고증에 맞는거였구나",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="혼후순결 고증 얘기")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.search_results = [
            {
                "title": "이세계에서 사이비로 살아남기 - 나무위키",
                "url": "https://namu.wiki/w/example",
                "source_tier": "wiki",
                "content": "혼후순결이라는 개념이 등장한다.",
            },
            {
                "title": "혼후순결 설정 정리",
                "url": "https://arca.live/b/novelchannel/77980889",
                "source_tier": "community",
                "content": "혼전혼후 순결 설정을 다루는 글",
            },
        ]

        picked, confidence, flags = pipeline._guard_official_title_precision(
            ctx=ctx,
            official_title=title,
            confidence="High",
            title_candidates=[DetectedTitle(official_title=title, confidence="High", source_tier="community")],
            vf_result={"grounding_check": {"anchor_found": "title_mention"}},
        )

        self.assertIsNone(picked)
        self.assertEqual(confidence, "Low")
        self.assertIn("title_precision_downgrade", flags)

    def test_precision_guard_blocks_search_absent_verifier_repromotion_even_with_exact_text(self):
        pipeline = build_pipeline()
        title = "21세기 무림"
        post = PostInput(
            post_id=11666713,
            title="21세기 무림 이거 재미네 ㅋㅋㅋ",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="무틀딱 각혈하게 만드는 작품인 줄 알았는데"),
                ContentBlock(type="text", text="진지할 땐 진지하고 무협스러움이 가득한 작품이네 ㅋㅋ"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])

        picked, confidence, flags = pipeline._guard_official_title_precision(
            ctx=ctx,
            official_title=title,
            confidence="High",
            title_candidates=[
                DetectedTitle(
                    official_title=title,
                    confidence="High",
                    source_tier="llm_only",
                    reference_role="primary",
                )
            ],
            vf_result={
                "counter_arguments": [
                    {
                        "issue": "search_absent_verified_title",
                        "severity": "critical",
                        "action": "nullify_title",
                        "explanation": "검색 결과에서 공식 작품 근거를 찾지 못했습니다.",
                    }
                ],
                "grounding_check": {"anchor_found": "title_mention"},
            },
        )

        self.assertIsNone(picked)
        self.assertEqual(confidence, "Low")
        self.assertIn("verifier_title_repromotion_veto", flags)

    def test_search_catalog_contextual_work_recall_recovers_wiki_author_setting_bridge(self):
        pipeline = build_pipeline()
        title = "이세계에서 사이비로 살아남기"
        post = PostInput(
            post_id=11694019,
            title="미츄리 혼후순결에서 하인들에게도 멸시당한게 고증에 맞는거였구나",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(
                    type="text",
                    text="아내가 혼후순결 요구해서 섹스 안하니까 하인들도 멸시하는데",
                )
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.search_results = [
            {
                "title": "나무위키",
                "url": "https://namu.wiki/w/%EC%9D%B4%EC%84%B8%EA%B3%84%EC%97%90%EC%84%9C%20%EC%82%AC%EC%9D%B4%EB%B9%84%EB%A1%9C%20%EC%82%B4%EC%95%84%EB%82%A8%EA%B8%B0",
                "content": "이세계에서 사이비로 살아남기 노벨피아 연재 작품. 작가 미츄리. 프시케의 혼후순결 선언.",
                "rank": 1,
            },
            {
                "title": "이세계에서 사이비로 살아남기",
                "url": "https://novelpia.com/novel/181771",
                "content": "작가 미츄리의 성인 퓨전 판타지 웹소설.",
                "rank": 2,
            },
        ]
        verification_result = {
            "relation_judgment": {
                "relation_type": "thematic_overlap_only",
                "discussion_target": "genre_general",
                "promotion_decision": "reject",
            }
        }

        recovered_identity, candidates, primary, promotion = pipeline._apply_official_url_recall_promotion(
            ctx=ctx,
            extended_identity={
                "is_relevant": False,
                "topicality": "adjacent_relevant",
                "work_resolution": "none",
                "consistency_flags": [],
            },
            title_candidates=[],
            primary_work=None,
            verification_result=verification_result,
            final_decision={"discussion_type": "trope_discussion"},
        )

        self.assertIsNotNone(promotion)
        self.assertEqual(recovered_identity["official_title"], title)
        self.assertEqual(recovered_identity["heretic_url"], "https://novelpia.com/novel/181771")
        self.assertTrue(recovered_identity["is_relevant"])
        self.assertIn(
            "search_catalog_contextual_work_recall_anchor",
            recovered_identity["consistency_flags"],
        )
        self.assertEqual(candidates[0].official_title, title)
        self.assertEqual(primary.official_title, title)

    def test_search_catalog_contextual_work_recall_blocks_generic_trope_page(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11673082,
            title="용사파티 << ㅈㄴ비겁한 소수정예 암살단임",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="마왕이랑 사천왕 1대1 붙이는 장르 트롭 얘기")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.search_results = [
            {
                "title": "용사 파티",
                "url": "https://novelpia.com/novel/111111",
                "content": "용사파티와 마왕, 사천왕이 나오는 판타지 웹소설.",
                "rank": 1,
            }
        ]

        promotion = pipeline._search_catalog_contextual_work_recall_promotion(
            ctx,
            extended_identity={"consistency_flags": []},
            final_decision={},
            verification_result={},
        )

        self.assertIsNone(promotion)

    def test_search_catalog_contextual_work_recall_blocks_setting_only_platform_detail(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11694019,
            title="미츄리 혼후순결에서 하인들에게도 멸시당한게 고증에 맞는거였구나",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(
                    type="text",
                    text="아내가 혼후순결 요구해서 섹스 안하니까 하인들도 멸시하는데",
                )
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.search_results = [
            {
                "title": "그녀의 순결이 타락할 때까지",
                "url": "https://novelpia.com/novel/166048",
                "content": "그녀의 순결이 타락할 때까지. 혼후순결에서 혼후순결 설정을 다루는 웹소설.",
                "rank": 1,
            }
        ]

        promotion = pipeline._search_catalog_contextual_work_recall_promotion(
            ctx,
            extended_identity={"consistency_flags": []},
            final_decision={},
            verification_result={},
        )

        self.assertIsNone(promotion)

    def test_search_catalog_contextual_work_recall_prefers_visual_bracket_alias_candidate(self):
        pipeline = build_pipeline()
        title = "[림월드]변방계에서 회귀자로 살아남기"
        url = "https://novelpia.com/novel/382324"
        post = PostInput(
            post_id=11673086,
            title="랫따싶 칸시가 정실이엿으면",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="바로 시트러스 노예조교 on이엿을텐데")],
            comments=["심지어 시트러스햄은 싸우는 폼보니까 강인함도 있겠다에요"],
        )
        post_data = pipeline._post_to_dict(post)
        post_data["image_enrichment"] = [
            {
                "ocr_text": "RimWorld -modded- 사료 섭취 -12 동물밥을 먹어야 했어.",
                "visual_summary": "RimWorld 게임 UI와 캐릭터 일러스트.",
                "explicit_work_title": "RimWorld",
                "evidence_type": "explicit_text",
                "work_cues": ["RimWorld", "modded", "사료 섭취"],
            }
        ]
        ctx = ConversationContext(post_id=post.post_id, post_data=post_data, comments=post.comments)
        ctx.search_results = [
            {
                "title": "웹소설로 꿈꾸는 세상! - 쳇바퀴의 생쥐 사도가 되었다 - 노벨피아",
                "url": "https://novelpia.com/novel/406113",
                "snippet": "판타지 #전생 #TS #이세계 #수인 #성장 #랫따싶. 생쥐 미소녀로 전생했더니...",
                "query": "랫따싶 노벨피아",
                "rank": 1,
            },
            {
                "title": f"웹소설로 꿈꾸는 세상! - {title}",
                "url": url,
                "snippet": "단, 죽어서만. 첫 화 보기. #패러디 #림월드 #랫따싶.",
                "query": "랫따싶 노벨피아",
                "rank": 2,
            },
        ]

        promotion = pipeline._search_catalog_contextual_work_recall_promotion(
            ctx,
            extended_identity={"consistency_flags": []},
            final_decision={},
            verification_result={},
        )

        self.assertIsNotNone(promotion)
        self.assertEqual(promotion["official_title"], title)
        self.assertEqual(promotion["heretic_url"], url)
        self.assertIn("visual_bracket_context", promotion["matched_clue"])

    def test_search_catalog_contextual_work_recall_uses_verified_wiki_when_platform_url_absent(self):
        pipeline = build_pipeline()
        title = "이세계에서 사이비로 살아남기"
        wiki_url = "https://namu.wiki/w/%EC%9D%B4%EC%84%B8%EA%B3%84%EC%97%90%EC%84%9C%20%EC%82%AC%EC%9D%B4%EB%B9%84%EB%A1%9C%20%EC%82%B4%EC%95%84%EB%82%A8%EA%B8%B0"
        post = PostInput(
            post_id=11694019,
            title="미츄리 혼후순결에서 하인들에게도 멸시당한게 고증에 맞는거였구나",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(
                    type="text",
                    text="아내가 혼후순결 요구해서 섹스 안하니까 중세 문화에서는 하인들도 멸시함",
                )
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.search_results = [
            {
                "title": "나무위키",
                "url": wiki_url,
                "content": "이세계에서 사이비로 살아남기 노벨피아 연재 웹소설. 작가 미츄리. 프시케의 혼후순결 선언.",
                "rank": 1,
            }
        ]
        verification_result = {
            "novel_identity": {"official_novel_title": title, "confidence": "High"},
            "title_resolution_allowed": False,
            "relation_judgment": {
                "relation_type": "thematic_overlap_only",
                "discussion_target": "mixed_or_uncertain",
                "promotion_decision": "hold",
            },
        }

        recovered_identity, candidates, primary, promotion = pipeline._apply_official_url_recall_promotion(
            ctx=ctx,
            extended_identity={
                "is_relevant": False,
                "topicality": "adjacent_relevant",
                "work_resolution": "none",
                "consistency_flags": [],
            },
            title_candidates=[],
            primary_work=None,
            verification_result=verification_result,
            final_decision={
                "discussion_type": "general",
                "_title_deliberately_null": True,
                "title_resolution_allowed": False,
            },
        )

        self.assertIsNotNone(promotion)
        self.assertEqual(promotion["source_tier"], "mixed")
        self.assertEqual(recovered_identity["official_title"], title)
        self.assertEqual(recovered_identity["heretic_url"], wiki_url)
        self.assertTrue(recovered_identity["is_relevant"])
        self.assertIn("검색 catalog 작품 페이지", recovered_identity["reason"])
        self.assertIn(
            "search_catalog_contextual_work_recall_anchor",
            recovered_identity["consistency_flags"],
        )
        self.assertEqual(candidates[0].source_tier, "mixed")
        self.assertEqual(primary.official_title, title)

    def test_contextual_alias_bridge_prefers_author_work_over_same_surface_title(self):
        pipeline = build_pipeline()
        current_title = "혼후순결"
        expected_title = "이세계에서 사이비로 살아남기"
        post = PostInput(
            post_id=11694019,
            title="미츄리 혼후순결에서 하인들에게도 멸시당한게 고증에 맞는거였구나",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="아내가 혼후순결 요구해서 섹스 안하니까")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.search_results = [
            {
                "title": "개요 대한민국의 성인 퓨전 판타지 웹소설. 작가는 미츄리",
                "url": "https://namu.wiki/w/이세계에서 사이비로 살아남기",
                "content": "프시케는 혼후순결 선언 때문에 독자들에게 욕을 먹고 있다. 미츄리의 소설.",
            },
            {
                "title": "미츄리의 신신신신작, 이세계에서 사이비로 살아남기",
                "url": "https://arca.live/b/novelchannel/77980889",
                "content": "혼후순결 설정을 다루는 장르소설 채널 글",
            },
            {
                "title": "혼후순결 - 웹소설",
                "url": "https://page.kakao.com/content/60742024",
                "content": "동명 로맨스 웹소설",
            },
        ]
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "decoded_terms": [
                    {
                        "original": "미츄리",
                        "best_match": {"title": expected_title, "confidence": "high"},
                        "candidates": [{"official_novel_title": expected_title}],
                        "is_author_name": True,
                    },
                    {
                        "original": "혼후순결",
                        "best_match": {"title": current_title, "confidence": "high"},
                        "candidates": [{"official_novel_title": current_title}],
                    },
                ]
            },
        )
        vf_result = {
            "slang_insight": {
                "detected_term": "미츄리",
                "decoded_term": f"{expected_title} (작가: 미츄리)",
                "decode_verified": True,
                "alias_scope": "work_plus_author",
            },
            "relation_judgment": {
                "relation_type": "work_specific_nickname",
                "discussion_target": "specific_work",
                "promotion_decision": "hold",
                "post_direct_grounding": True,
                "search_support_summary": {
                    "official_exact_title_count": 4,
                    "explicit_alias_bridge_count": 0,
                    "alias_in_post_count": 0,
                    "community_alias_support_count": 0,
                },
            },
        }

        self.assertEqual(
            pipeline._pick_contextual_alias_bridge_alternative(ctx, current_title, vf_result),
            expected_title,
        )

    def test_known_abbreviation_guard_replaces_same_surface_official_title_with_contextual_bridge(self):
        pipeline = build_pipeline()
        current_title = "혼후순결"
        expected_title = "이세계에서 사이비로 살아남기"
        post = PostInput(
            post_id=11694019,
            title="미츄리 혼후순결에서 하인들에게도 멸시당한게 고증에 맞는거였구나",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="아내가 혼후순결 요구해서 섹스 안하니까")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.search_results = [
            {
                "title": "혼후순결 - 웹소설",
                "url": "https://page.kakao.com/content/60742024?tab_type=about",
                "source_tier": "official_platform",
                "content": "동명 로맨스 웹소설",
            },
            {
                "title": "혼후순결",
                "url": "https://series.naver.com/novel/detail.series?productNo=8311763",
                "source_tier": "official_platform",
                "content": "아누보리 로맨스 작품",
            },
            {
                "title": "미츄리의 신신신신작, 이세계에서 사이비로 살아남기",
                "url": "https://arca.live/b/novelchannel/77980889",
                "source_tier": "community",
                "content": "혼후순결 설정을 다루는 장르소설 채널 글",
            },
            {
                "title": "이세계에서 사이비로 살아남기 - 나무위키",
                "url": "https://namu.wiki/w/이세계에서 사이비로 살아남기",
                "source_tier": "wiki",
                "content": "작가는 미츄리. 혼후순결이라는 설정이 등장한다.",
            },
        ]
        ctx.llm_snippet_analysis = {
            "abbreviation_mappings": [
                {"abbrev": "혼후순결", "full": expected_title},
            ],
        }

        picked_title, picked_url = pipeline._apply_known_abbreviation_title_guard(
            ctx,
            current_title,
            "https://page.kakao.com/content/60742024?tab_type=about",
        )

        self.assertEqual(picked_title, expected_title)
        self.assertIsNone(picked_url)

    def test_known_abbreviation_guard_keeps_same_surface_official_without_contextual_bridge(self):
        pipeline = build_pipeline()
        current_title = "혼후순결"
        expected_title = "이세계에서 사이비로 살아남기"
        post = PostInput(
            post_id=11694019,
            title="미츄리 혼후순결에서 하인들에게도 멸시당한게 고증에 맞는거였구나",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="아내가 혼후순결 요구해서 섹스 안하니까")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.search_results = [
            {
                "title": "혼후순결 - 웹소설",
                "url": "https://page.kakao.com/content/60742024?tab_type=about",
                "source_tier": "official_platform",
                "content": "동명 로맨스 웹소설",
            },
            {
                "title": "이세계에서 사이비로 살아남기 - 나무위키",
                "url": "https://namu.wiki/w/이세계에서 사이비로 살아남기",
                "source_tier": "wiki",
                "content": "혼후순결이라는 설정이 등장한다.",
            },
        ]
        ctx.llm_snippet_analysis = {
            "abbreviation_mappings": [
                {"abbrev": "혼후순결", "full": expected_title},
            ],
        }

        picked_title, picked_url = pipeline._apply_known_abbreviation_title_guard(
            ctx,
            current_title,
            "https://page.kakao.com/content/60742024?tab_type=about",
        )

        self.assertEqual(picked_title, current_title)
        self.assertEqual(picked_url, "https://page.kakao.com/content/60742024?tab_type=about")

    def test_relation_hold_blocks_character_scene_official_promotion_without_alias_bridge(self):
        pipeline = build_pipeline()
        title = "바람과 별무리"
        post = PostInput(
            post_id=11700470,
            title="어케 주인공 죄목이",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", url="https://example.test/scene.png"),
            ],
            comments=["교수형"],
        )
        post_dict = pipeline._post_to_dict(post)
        post_dict["image_enrichment"] = [
            {
                "source_url": "https://example.test/scene.png",
                "ocr_text": (
                    "참고인의 모든 변론이 끝났다. 얼굴도 모르는 미소녀를 납치 후 "
                    "가스라이팅을 반복했고 B급 모험가 밤도깨비 에이브가 되어 있었다."
                ),
                "explicit_work_title": "",
                "evidence_type": "scene_text",
                "screen_type": "work_scene",
                "work_cues": ["B급 모험가 밤도깨비 에이브", "미소녀 납치"],
                "promotion_eligible": False,
            }
        ]
        ctx = ConversationContext(post_id=post.post_id, post_data=post_dict, comments=post.comments)
        ctx.search_results = [
            {
                "title": "바람과 별무리/등장인물 - 나무위키",
                "url": "https://namu.wiki/w/%EB%B0%94%EB%9E%8C%EA%B3%BC%20%EB%B3%84%EB%AC%B4%EB%A6%AC/%EB%93%B1%EC%9E%A5%EC%9D%B8%EB%AC%BC",
                "content": "밤도깨비처럼 만들고 주인공 일행을 공격하다 실패한다.",
                "from_query": "밤도깨비 에이브 웹소설",
            },
            {
                "title": "웹소설로 꿈꾸는 세상! - 바람과 별무리 - 노벨피아",
                "url": "https://novelpia.com/novel/25974",
                "content": "범선, 모험, 화약- 바람과 별무리.",
                "from_query": "바람과 별무리 웹소설 노벨피아",
            },
        ]
        vf_result = {
            "is_relevant": True,
            "is_novel_discussion": True,
            "final_confidence": "high",
            "novel_identity": {
                "official_novel_title": title,
                "official_title": title,
                "heretic_url": "https://novelpia.com/novel/25974",
                "confidence": "High",
                "evidence_type": "search_platform_url",
            },
            "grounding_check": {
                "decoder_grounded": True,
                "anchor_found": "character_mention",
                "anchor_text": "B급 모험가 밤도깨비 에이브",
                "matched_alias": "밤도깨비 에이브",
            },
            "slang_insight": {
                "detected_term": "밤도깨비 에이브",
                "decoded_term": title,
                "decode_verified": True,
                "alias_scope": "work_plus_character",
            },
            "relation_judgment": {
                "relation_type": "work_specific_nickname",
                "discussion_target": "specific_work",
                "promotion_decision": "hold",
                "reason": "검색 엔진의 부분 일치에 의한 추론일 뿐 명시적 alias bridge가 부족합니다.",
                "post_direct_grounding": False,
                "search_support_summary": {
                    "official_exact_title_count": 1,
                    "community_alias_support_count": 0,
                    "explicit_alias_bridge_count": 0,
                    "alias_in_post_count": 0,
                    "best_official_url": "https://novelpia.com/novel/25974",
                    "converged_official_signal": False,
                },
            },
        }
        ctx.set_expert_output(ExpertType.VERIFIER, {"verification_result": vf_result})
        final_decision = {"is_relevant": True, "discussion_type": "character_talk"}

        self.assertFalse(
            pipeline._has_relation_alias_official_detail_lock(ctx, title, vf_result)
        )
        self.assertTrue(
            pipeline._relation_hold_should_block_title_resolution(
                ctx=ctx,
                official_title=title,
                verification_result=vf_result,
            )
        )
        self.assertIsNone(pipeline._try_promote_best_candidate(ctx, vf_result, final_decision))

    def test_official_url_recall_context_blocks_gaming_and_competing_titles(self):
        pipeline = build_pipeline()
        title = "쳇바퀴의 생쥐 사도가 되었다"
        post = PostInput(
            post_id=20010004,
            title="랫따싶 모드밸런스면 보이드정도까진 나올만함",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="랫킨 모드 밸런스랑 보이드 레이드 얘기")],
            comments=["랫킨은 김치 모드임"],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {"discourse_analysis": {"primary_domain": "gaming", "intent": "express_opinion", "target_kind": "none"}},
        )
        verification_result = {
            "slang_insight": {
                "detected_term": "랫따싶",
                "canonical_work_alias": "랫따싶",
                "decoded_term": title,
                "decode_verified": True,
                "alias_scope": "pure_work_alias",
            },
            "relation_judgment": {
                "relation_type": "thematic_overlap_only",
                "discussion_target": "community_banter",
                "promotion_decision": "reject",
            },
            "counter_arguments": [{"issue": "도메인 불일치", "severity": "critical"}],
        }

        self.assertEqual(
            pipeline._official_url_recall_hard_context_block_reason(
                ctx,
                title=title,
                verification_result=verification_result,
                final_decision={"discussion_type": "off_topic", "final_reasoning": "게임 모드 밸런스 글"},
            ),
            "hard_non_novel_context",
        )

        competing = [
            DetectedTitle(
                official_title="다른 공식 작품",
                heretic_url="https://novelpia.com/novel/999999",
                confidence="High",
            )
        ]
        self.assertTrue(
            pipeline._official_url_recall_competing_title_blocked(
                ctx,
                "조향사의 헌터상담기록",
                competing,
                "https://novelpia.com/novel/123456",
            )
        )

    def test_search_alias_inference_prefers_bracket_post_cue_over_shared_alias_tag(self):
        pipeline = build_pipeline()
        post_data = {
            "title": "랫따싶 림월드 요소 생각나게 하는거 좋네에...",
            "normalized_title": "랫따싶 림월드 요소 생각나게 하는거 좋네에...",
            "content_blocks": [
                {"type": "text", "text": "게임적 요소 있는거 아주 굿"},
            ],
            "image_enrichment": [
                {
                    "ocr_text": "림월드 방어 건물 제작 스킬이 늘었으려나. 회차를 다시 시작하고 싶을 정도.",
                    "visual_summary": "웹소설 본문 텍스트 화면. 게임 '림월드'의 요소를 묘사합니다.",
                    "work_cues": ["림월드", "제작 스킬", "방어 건물"],
                }
            ],
        }
        ctx = ConversationContext(post_id=11698897, post_data=post_data, comments=[])
        correct = {
            "title": "[림월드]변방계에서 회귀자로 살아남기",
            "url": "https://novelpia.com/novel/382324",
            "snippet": "단, 죽어서만. #패러디 #림월드 #랫따싶. 잡탕 종족모드가 적용된 변방계에 떨어졌다.",
            "query": "랫따싶",
            "source_tier": "official_detail",
        }
        wrong = {
            "title": "쳇바퀴의 생쥐 사도가 되었다",
            "url": "https://novelpia.com/novel/406113",
            "snippet": "랫따싶. #판타지 #전생 #성장. 생쥐 미소녀로 전생했더니 쥐의 여신과 만났다.",
            "query": "랫따싶 웹소설 노벨피아",
            "source_tier": "official_detail",
        }
        ctx.search_results = [wrong, correct]

        hit = pipeline._infer_alias_title_from_search_evidence(ctx, post_data["title"])

        self.assertIsNotNone(hit)
        self.assertEqual(hit["title"], "[림월드]변방계에서 회귀자로 살아남기")
        self.assertEqual(hit["matched_url"], "https://novelpia.com/novel/382324")

    def test_title_led_gate_selects_visual_bracket_competitor_when_search_context_prefers_other_official_detail(self):
        pipeline = build_pipeline()
        wrong_title = "쳇바퀴의 생쥐 사도가 되었다"
        wrong_url = "https://novelpia.com/novel/406113"
        correct_title = "[림월드]변방계에서 회귀자로 살아남기"
        correct_url = "https://novelpia.com/novel/382324"
        post = PostInput(
            post_id=11698897,
            title="랫따싶 림월드 요소 생각나게 하는거 좋네에...",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", url="https://example.test/rimworld.png"),
                ContentBlock(type="text", text="게임적 요소 있는거 아주 굿"),
            ],
            comments=["랫따싶 이거 참 잘쓴 패러디야"],
        )
        post_data = pipeline._post_to_dict(post)
        post_data["image_enrichment"] = [
            {
                "ocr_text": "림월드 최대의 적폐 건물, 기지가치 대비 살상력 GOAT. 목발 제작 스킬이 늘었으려나.",
                "visual_summary": "웹소설 본문 텍스트 화면. 게임 림월드 요소와 제작 장면을 묘사.",
                "work_cues": ["림월드", "방어건물", "제작 스킬"],
            }
        ]
        ctx = ConversationContext(post_id=post.post_id, post_data=post_data, comments=post.comments)
        ctx.search_results = [
            {
                "title": wrong_title,
                "url": wrong_url,
                "content": "랫따싶. #판타지 #전생 #성장. 생쥐 미소녀로 전생했더니 쥐의 여신과 만났다.",
                "query": "랫따싶 노벨피아",
                "source_tier": "official_detail",
            },
            {
                "title": correct_title,
                "url": correct_url,
                "content": "단, 죽어서만. #패러디 #림월드 #랫따싶. 잡탕 종족모드가 적용된 변방계에 떨어졌다.",
                "query": "랫따싶 노벨피아",
                "source_tier": "official_detail",
            },
        ]
        final_decision = {
            "discussion_type": "character_talk",
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
        }
        vf_result = {
            "grounding_check": {
                "anchor_found": "title_abbrev_mention",
                "title_abbrev_mentioned": True,
                "matched_alias": "랫따싶",
            },
            "slang_insight": {
                "detected_term": "랫따싶",
                "decoded_term": wrong_title,
                "decode_verified": True,
                "alias_scope": "pure_work_alias",
            },
        }
        candidates = [
            DetectedTitle(
                official_title=wrong_title,
                heretic_url=wrong_url,
                confidence="High",
                alias_or_mention="랫따싶",
                source_tier="official_detail",
                page_type="novel_page",
            )
        ]

        _baseline_synthetic_fetched_detail(self, pipeline, ctx, correct_title, correct_url,
                                           candidate_title=correct_title)
        source_before = _baseline_source_snapshot(ctx)

        decision = pipeline._record_title_led_alias_public_title_gate_decision(
            ctx,
            wrong_title,
            candidate_url=wrong_url,
            final_decision=final_decision,
            verification_result=vf_result,
            title_candidates=candidates,
            acceptance={"decision": "accept", "title_led_consumption_bridge": True, "score": 29},
        )

        _baseline_record_contract(self, ctx, decision, source_before, "visual_select")

        self.assertEqual(decision["status"], "publish")
        self.assertTrue(decision["publish_allowed"])
        self.assertEqual(decision["official_title"], correct_title)
        self.assertEqual(decision["official_url"], correct_url)
        self.assertIn("scope_current_work", decision["reason_codes"])
        self.assertIn(
            "title_led_alias_contextual_official_detail_selected",
            decision["reason_codes"],
        )
        self.assertIn(
            "official_detail_bracket_visual_release_context",
            decision["reason_codes"],
        )
        state = ctx._last_promotion_gate_state
        self.assertEqual(state["candidate_title"], correct_title)
        self.assertTrue(state["row_discusses_work_as_work"])
        self.assertEqual(state["scope"]["scope_kind"], "current_work")
        self.assertIn(
            "contextual_alias_official_detail_selected",
            state["scope"]["direct_bridge_sources"],
        )
        self.assertIn(
            "official_detail_bracket_visual_release_context",
            state["scope"]["direct_bridge_sources"],
        )
        self.assertEqual(state["scope"]["conflict_reason_codes"], [])
        self.assertEqual(state["scope"]["competing_candidates"], [])
        evidence = ctx._last_promotion_gate_evidence
        self.assertTrue(
            any(item["kind"] == "contextual_alias_official_detail_selected" for item in evidence)
        )
        self.assertTrue(
            any(item["kind"] == "official_detail_bracket_visual_release_context" for item in evidence)
        )

    def test_title_led_gate_blocks_shared_alias_competitor_without_packet_visual_or_bracket_context(self):
        pipeline = build_pipeline()
        wrong_title = "쳇바퀴의 생쥐 사도가 되었다"
        wrong_url = "https://novelpia.com/novel/406113"
        correct_title = "[림월드]변방계에서 회귀자로 살아남기"
        correct_url = "https://novelpia.com/novel/382324"
        post = PostInput(
            post_id=1169889701,
            title="랫따싶 요소 생각나게 하는거 좋네에...",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="게임적 요소 있는거 아주 굿")],
            comments=["랫따싶 이거 참 잘쓴 패러디야"],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=post.comments,
        )
        ctx.search_results = [
            {
                "title": wrong_title,
                "url": wrong_url,
                "content": "랫따싶. #판타지 #전생 #성장. 생쥐 미소녀로 전생했더니 쥐의 여신과 만났다.",
                "query": "랫따싶 노벨피아",
                "source_tier": "official_detail",
            },
            {
                "title": correct_title,
                "url": correct_url,
                "content": "단, 죽어서만. #패러디 #림월드 #랫따싶. 잡탕 종족모드가 적용된 변방계에 떨어졌다.",
                "query": "랫따싶 노벨피아",
                "source_tier": "official_detail",
            },
        ]
        final_decision = {
            "discussion_type": "character_talk",
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
        }
        vf_result = {
            "grounding_check": {
                "anchor_found": "title_abbrev_mention",
                "title_abbrev_mentioned": True,
                "matched_alias": "랫따싶",
            },
            "slang_insight": {
                "detected_term": "랫따싶",
                "decoded_term": wrong_title,
                "decode_verified": True,
                "alias_scope": "pure_work_alias",
            },
        }
        candidates = [
            DetectedTitle(
                official_title=wrong_title,
                heretic_url=wrong_url,
                confidence="High",
                alias_or_mention="랫따싶",
                source_tier="official_detail",
                page_type="novel_page",
            )
        ]

        decision = pipeline._record_title_led_alias_public_title_gate_decision(
            ctx,
            wrong_title,
            candidate_url=wrong_url,
            final_decision=final_decision,
            verification_result=vf_result,
            title_candidates=candidates,
            acceptance={"decision": "accept", "title_led_consumption_bridge": True, "score": 29},
        )

        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertIn("scope_context_only", decision["reason_codes"])
        self.assertIn(
            "title_led_alias_contextual_official_detail_competes",
            decision["reason_codes"],
        )
        state = ctx._last_promotion_gate_state
        self.assertFalse(state["row_discusses_work_as_work"])
        self.assertEqual(state["scope"]["scope_kind"], "context_only")
        self.assertTrue(
            any("변방계에서 회귀자로 살아남기" in title for title in state["scope"]["competing_candidates"])
        )
        evidence = ctx._last_promotion_gate_evidence
        self.assertTrue(
            any(item["kind"] == "contextual_alias_official_detail_competition" for item in evidence)
        )

    def test_title_led_gate_canonicalizes_alias_surface_to_official_detail_title(self):
        pipeline = build_pipeline()
        alias_title = "암흑가보스"
        official_title = "암흑가 보스요? 제가요?"
        official_url = "https://novelpia.com/novel/384111"
        weak_phrase_competitor = "암흑가 보스의 버려진 딸이 되었다"
        weak_competitor_url = "https://ridibooks.com/books/3863000164"
        post = PostInput(
            post_id=11660257,
            title="암흑가보스<<이거 재밋네",
            author="ㅇㅇ",
            content_blocks=[],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.llm_snippet_analysis = {
            "identified_title": official_title,
            "abbreviation_mappings": [{"abbrev": alias_title, "full": official_title}],
        }
        ctx.search_results = [
            {
                "title": official_title,
                "url": official_url,
                "content": "암흑가 보스요? 제가요? 작가명 손아픈사람. PLUS 독점. #현대 #판타지 #하렘",
                "query": "암흑가보스 노벨피아",
                "source_tier": "official_detail",
            },
            {
                "title": f"{weak_phrase_competitor} - 로판 e북",
                "url": weak_competitor_url,
                "content": "암흑가 보스의 버려진 딸이 되었다 작품소개.",
                "query": "시리즈 암흑가보스 작가",
                "source_tier": "novel_platform",
            },
        ]
        final_decision = {
            "discussion_type": "general",
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
            "_raw_llm_title": official_title,
        }
        vf_result = {
            "novel_identity": {
                "official_title": official_title,
                "official_novel_title": official_title,
                "heretic_url": official_url,
            },
            "grounding_check": {
                "anchor_found": "title_mention",
                "title_abbrev_mentioned": True,
                "matched_alias": alias_title,
            },
            "slang_insight": {
                "detected_term": alias_title,
                "decoded_term": official_title,
                "decode_verified": True,
                "alias_scope": "pure_work_alias",
            },
            "relation_judgment": {
                "relation_type": "explicit_alias",
                "discussion_target": "specific_work",
                "promotion_decision": "hold",
            },
        }
        candidates = [
            DetectedTitle(
                official_title=alias_title,
                heretic_url=official_url,
                confidence="High",
                source_tier="official_detail",
                page_type="novel_page",
            ),
            DetectedTitle(
                official_title=official_title,
                confidence="High",
                source_tier="community",
            ),
        ]

        _baseline_synthetic_fetched_detail(self, pipeline, ctx, official_title, official_url,
                                           candidate_title=official_title)
        source_before = _baseline_source_snapshot(ctx)

        decision = pipeline._record_title_led_alias_public_title_gate_decision(
            ctx,
            alias_title,
            candidate_url=official_url,
            final_decision=final_decision,
            verification_result=vf_result,
            title_candidates=candidates,
            acceptance={"decision": "accept", "title_led_consumption_bridge": True, "score": 29},
        )

        _baseline_record_contract(self, ctx, decision, source_before, "alias")

        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertIsNone(decision["official_title"])
        self.assertIsNone(decision["official_url"])
        self.assertIn("title_led_alias_official_detail_canonicalized", decision["reason_codes"])
        state = ctx._last_promotion_gate_state
        self.assertTrue(state["row_discusses_work_as_work"])
        self.assertEqual(state["scope"]["scope_kind"], "current_work")
        self.assertEqual(state["scope"]["conflict_reason_codes"], [])
        self.assertIn("title_led_alias_official_detail_canonicalized", state["scope"]["direct_bridge_sources"])
        self.assertNotIn("title_led_alias_contextual_official_detail_competes", decision["reason_codes"])
        self.assertNotIn(weak_phrase_competitor, state["scope"]["competing_candidates"])

        self.assertEqual(state["candidate_title"], official_title)
        self.assertEqual(state["semantic_publication"]["evidence_status"], "insufficient")
        self.assertEqual(vf_result["relation_judgment"]["promotion_decision"], "hold")

    def test_title_led_gate_keeps_current_visual_bracket_candidate_when_shared_alias_competitor_exists(self):
        pipeline = build_pipeline()
        correct_title = "변방계에서 회귀자로 살아남기"
        canonical_title = "[림월드]변방계에서 회귀자로 살아남기"
        correct_url = "https://novelpia.com/novel/382324"
        wrong_title = "쳇바퀴의 생쥐 사도가 되었다"
        wrong_url = "https://novelpia.com/novel/406113"
        post = PostInput(
            post_id=11698897,
            title="랫따싶 림월드 요소 생각나게 하는거 좋네에...",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", url="https://example.test/rimworld.png"),
                ContentBlock(type="text", text="게임적 요소 있는거 아주 굿"),
            ],
            comments=["랫따싶 이거 참 잘쓴 패러디야"],
        )
        post_data = pipeline._post_to_dict(post)
        post_data["image_enrichment"] = [
            {
                "ocr_text": "림월드 최대의 적폐 건물. 목발 제작 스킬이 늘었으려나.",
                "visual_summary": "웹소설 본문 텍스트 화면. 게임 림월드 요소와 제작 장면을 묘사.",
                "work_cues": ["림월드", "방어건물", "제작 스킬"],
            }
        ]
        ctx = ConversationContext(post_id=post.post_id, post_data=post_data, comments=post.comments)
        ctx.search_results = [
            {
                "title": canonical_title,
                "url": correct_url,
                "content": "단, 죽어서만. #패러디 #림월드 #랫따싶.",
                "query": "랫따싶 노벨피아",
                "source_tier": "official_detail",
            },
            {
                "title": wrong_title,
                "url": wrong_url,
                "content": "랫따싶. #판타지 #전생 #성장. 생쥐 미소녀로 전생했더니 쥐의 여신과 만났다.",
                "query": "랫따싶 노벨피아",
                "source_tier": "official_detail",
            },
        ]
        final_decision = {
            "discussion_type": "review",
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
        }
        vf_result = {
            "grounding_check": {
                "anchor_found": "title_mention",
                "title_abbrev_mentioned": True,
                "matched_alias": "랫따싶",
            },
            "slang_insight": {
                "detected_term": "랫따싶",
                "decoded_term": "[림월드]변방계에서 회귀자로 살아남기",
                "decode_verified": True,
                "alias_scope": "pure_work_alias",
            },
        }

        _baseline_synthetic_fetched_detail(self, pipeline, ctx, canonical_title, correct_url,
                                           candidate_title=correct_title)
        source_before = _baseline_source_snapshot(ctx)

        decision = pipeline._record_title_led_alias_public_title_gate_decision(
            ctx,
            correct_title,
            candidate_url=correct_url,
            final_decision=final_decision,
            verification_result=vf_result,
            title_candidates=[
                DetectedTitle(
                    official_title=correct_title,
                    heretic_url=correct_url,
                    confidence="High",
                    alias_or_mention="랫따싶",
                    source_tier="official_detail",
                    page_type="novel_page",
                ),
                DetectedTitle(
                    official_title=wrong_title,
                    heretic_url=wrong_url,
                    confidence="High",
                    alias_or_mention="랫따싶",
                    source_tier="official_detail",
                    page_type="novel_page",
                ),
            ],
            acceptance={"decision": "accept", "title_led_consumption_bridge": True, "score": 22},
        )

        _baseline_record_contract(self, ctx, decision, source_before, "visual_keep")

        self.assertEqual(decision["status"], "publish")
        self.assertTrue(decision["publish_allowed"])
        self.assertEqual(decision["official_title"], canonical_title)
        self.assertEqual(decision["official_url"], correct_url)
        state = ctx._last_promotion_gate_state
        self.assertEqual(state["candidate_title"], canonical_title)
        self.assertTrue(state["row_discusses_work_as_work"])
        self.assertEqual(state["scope"]["scope_kind"], "current_work")
        self.assertEqual(state["scope"]["conflict_reason_codes"], [])
        self.assertEqual(state["scope"]["competing_candidates"], [])
        evidence = ctx._last_promotion_gate_evidence
        self.assertTrue(
            any(
                item["kind"] == "contextual_alias_official_detail_nonblocking_competition"
                and item["source_path_or_snippet"] == wrong_title
                for item in evidence
            )
        )
        self.assertTrue(
            any(item["kind"] == "official_detail_bracket_visual_release_context" for item in evidence)
        )

    def test_packet_bound_visual_release_does_not_let_wrong_candidate_piggyback(self):
        pipeline = build_pipeline()
        wrong_title = "쳇바퀴의 생쥐 사도가 되었다"
        correct_title = "변방계에서 회귀자로 살아남기"
        bracket_title = "[림월드]변방계에서 회귀자로 살아남기"
        post = PostInput(
            post_id=21698897,
            title="랫따싶 림월드 요소 생각나게 하는거 좋네에...",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", url="https://example.test/rimworld.png"),
                ContentBlock(type="text", text="게임적 요소 있는거 아주 굿"),
            ],
            comments=["랫따싶 이거 참 잘쓴 패러디야"],
        )
        post_data = pipeline._post_to_dict(post)
        post_data["image_enrichment"] = [
            {
                "ocr_text": "림월드 최대의 적폐 건물. 목발 제작 스킬이 늘었으려나.",
                "visual_summary": "웹소설 본문 텍스트 화면. 게임 림월드 요소와 제작 장면을 묘사.",
                "work_cues": ["림월드", "방어건물", "제작 스킬"],
            }
        ]
        ctx = ConversationContext(post_id=post.post_id, post_data=post_data, comments=post.comments)
        ctx.search_results = [
            {
                "title": wrong_title,
                "url": "https://novelpia.com/novel/406113",
                "content": "랫따싶. #판타지 #전생 #성장.",
                "query": "랫따싶 노벨피아",
            },
            {
                "title": bracket_title,
                "url": "https://novelpia.com/novel/382324",
                "content": "단, 죽어서만. #패러디 #림월드 #랫따싶.",
                "query": "랫따싶 노벨피아",
            },
        ]

        self.assertFalse(
            pipeline._has_packet_bound_official_detail_visual_release_candidate(ctx, wrong_title)
        )
        self.assertTrue(
            pipeline._has_packet_bound_official_detail_visual_release_candidate(ctx, correct_title)
        )
        self.assertTrue(
            pipeline._has_packet_bound_official_detail_visual_release_candidate(ctx, bracket_title)
        )

    def test_official_url_recall_verified_alias_can_override_final_noise_and_competing_candidate(self):
        pipeline = build_pipeline()
        title = "잘생기면 편해지는 인방 생활"
        post = PostInput(
            post_id=20010005,
            title="잘생인방 뭔일 터짐?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="노피아가 뽑아준 표지 얘기 계속 나오네")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "discuss_work",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        ctx.search_results = [
            {
                "title": title,
                "url": "https://novelpia.com/novel/384016",
                "content": f"{title} 웹소설 작품 페이지. #잘생인방",
            }
        ]
        verification_result = {
            "is_relevant": True,
            "is_novel_discussion": True,
            "novel_identity": {"official_title": title},
            "slang_insight": {
                "detected_term": "잘생인방",
                "canonical_work_alias": "잘생인방",
                "decoded_term": title,
                "decode_verified": True,
                "alias_scope": "pure_work_alias",
            },
            "grounding_check": {
                "anchor_found": "title_abbrev_mention",
                "matched_alias": "잘생인방",
                "matched_title": title,
            },
            "relation_judgment": {
                "relation_type": "explicit_alias",
                "discussion_target": "specific_work",
                "promotion_decision": "allow",
            },
        }
        extended_identity = {
            "is_relevant": False,
            "work_resolution": "none",
            "title_resolution_state": "unresolved_matchable",
            "discussion_type": "noise",
            "consistency_flags": [],
        }
        title_candidates = [
            DetectedTitle(
                official_title="다른 공식 작품",
                heretic_url="https://novelpia.com/novel/999999",
                confidence="High",
            )
        ]

        recovered_identity, recovered_candidates, primary_work, promotion = (
            pipeline._apply_official_url_recall_promotion(
                ctx=ctx,
                extended_identity=extended_identity,
                title_candidates=title_candidates,
                primary_work=None,
                verification_result=verification_result,
                final_decision={"discussion_type": "noise", "final_reasoning": "웹소설 토론으로 보기 어려움"},
            )
        )

        self.assertIsNotNone(promotion)
        self.assertEqual(recovered_identity["official_title"], title)
        self.assertEqual(recovered_identity["heretic_url"], "https://novelpia.com/novel/384016")
        self.assertIsNotNone(primary_work)
        self.assertEqual(recovered_candidates[0].official_title, title)
        self.assertIn("official_url_recall_gate_recovered", recovered_identity["consistency_flags"])
        self.assertIn("verified_alias_official_detail_anchor", recovered_identity["consistency_flags"])
        self.assertIn("confirmed_alias:잘생인방", recovered_identity["consistency_flags"])

    def test_official_url_recall_blocks_alias_only_competing_candidate_after_unresolved_demote(self):
        pipeline = build_pipeline()
        title = "[림월드]변방계에서 회귀자로 살아남기"
        url = "https://novelpia.com/novel/382324"
        post = PostInput(
            post_id=20010006,
            title="랫따싶 이거 참 잘쓴 패러디야",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="림월드 변방계 이벤트 얘기라 후보는 남기되 바로 확정하긴 애매함")
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)
        ctx.search_results = [
            {
                "title": f"웹소설로 꿈꾸는 세상! - {title} - 노벨피아",
                "url": url,
                "content": f"{title}. #림월드 #랫따싶",
                "query": "랫따싶 림월드 노벨피아",
            },
            {
                "title": "웹소설로 꿈꾸는 세상! - [림월드] 오늘의 변방계 평균 - 노벨피아",
                "url": "https://novelpia.com/novel/399991",
                "content": "#림월드 #변방계",
                "query": "랫따싶 림월드 노벨피아",
            },
        ]
        extended_identity = {
            "is_relevant": True,
            "work_resolution": "unresolved",
            "title_resolution_state": "unresolved_matchable",
            "discussion_type": "general",
            "consistency_flags": ["notes_demoted_for_unresolved"],
        }
        verification_result = {
            "is_relevant": True,
            "is_novel_discussion": True,
            "novel_identity": {"official_title": title},
            "slang_insight": {
                "detected_term": "랫따싶",
                "canonical_work_alias": "랫따싶",
                "decoded_term": title,
                "decode_verified": True,
                "alias_scope": "pure_work_alias",
            },
            "grounding_check": {
                "anchor_found": "title_abbrev_mention",
                "matched_alias": "랫따싶",
                "matched_title": title,
            },
            "relation_judgment": {
                "relation_type": "explicit_alias",
                "discussion_target": "specific_work",
                "promotion_decision": "allow",
            },
        }
        title_candidates = [
            DetectedTitle(
                official_title="변방계에서 회귀자로 살아남기",
                heretic_url=url,
                confidence="High",
                source_tier="official_detail",
                reference_role="candidate",
            ),
            DetectedTitle(
                official_title="랫따싶 이거 참 잘쓴 패러디야",
                confidence="Medium",
                source_tier="llm_only",
                reference_role="mentioned",
            ),
        ]

        with patch(
            "llm_batch.agentic_pipeline.official_url_recoverable",
            return_value={
                "official_title": title,
                "heretic_url": url,
                "source_tier": "official_detail",
                "matched_clue": "confirmed_alias:랫따싶",
                "confidence": "High",
            },
        ), patch.object(
            pipeline,
            "_has_verified_alias_official_detail_anchor",
            return_value=True,
        ):
            recovered_identity, recovered_candidates, primary_work, promotion = (
                pipeline._apply_official_url_recall_promotion(
                    ctx=ctx,
                    extended_identity=extended_identity,
                    title_candidates=title_candidates,
                    primary_work=None,
                    verification_result=verification_result,
                    final_decision={"discussion_type": "general"},
                )
            )

        self.assertIsNone(promotion)
        self.assertIsNone(primary_work)
        self.assertNotIn("official_title", recovered_identity)
        self.assertEqual(recovered_candidates, title_candidates)
        self.assertIn(
            "official_url_recall_blocked_competing_candidate",
            recovered_identity["consistency_flags"],
        )
        self.assertIn(
            "official_url_recall_blocked_alias_only_competing_candidate",
            recovered_identity["consistency_flags"],
        )

    def test_known_title_abbreviation_official_url_recall_allows_update_question_no_work(self):
        pipeline = build_pipeline()
        title = "괴담 호텔 탈출기"
        post = PostInput(
            post_id=20010008,
            title="오늘 담텔기 오냐?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="아님 12시 넘어서 내일 새벽에 오냐")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "ask_question",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        ctx.search_results = [
            {
                "title": "담텔기 on - 장르소설 마이너 갤러리",
                "url": "https://gall.dcinside.com/mgallery/board/view/?id=genrenovel&no=12431961",
                "content": "담텔기 연참과 최신화 대기 글",
            }
        ]
        extended_identity = {
            "is_relevant": False,
            "work_resolution": "none",
            "title_resolution_state": "unresolved_matchable",
            "discussion_type": "noise",
            "consistency_flags": [],
        }

        with patch.object(
            pipeline,
            "_recover_corrected_title_official_url",
            return_value="https://novelpia.com/novel/102155",
        ) as recover:
            recovered_identity, recovered_candidates, primary_work, promotion = (
                pipeline._apply_official_url_recall_promotion(
                    ctx=ctx,
                    extended_identity=extended_identity,
                    title_candidates=[],
                    primary_work=None,
                    verification_result={
                        "is_relevant": False,
                        "novel_identity": {},
                        "grounding_check": {"grounding_issue": "정식 명칭 부재"},
                    },
                    final_decision={"discussion_type": "noise", "final_reasoning": "정식 명칭이 없어 노이즈"},
                )
            )

        self.assertTrue(
            pipeline._known_title_abbreviation_update_question_anchor(ctx, title, "담텔기")
        )
        self.assertIsNotNone(promotion)
        self.assertEqual(recovered_identity["official_title"], title)
        self.assertEqual(recovered_identity["heretic_url"], "https://novelpia.com/novel/102155")
        self.assertEqual(primary_work.official_title, title)
        self.assertEqual(recovered_candidates[0].alias_or_mention, "담텔기")
        self.assertIn("known_title_abbreviation_official_detail_anchor", recovered_identity["consistency_flags"])
        self.assertIn("confirmed_alias:담텔기", recovered_identity["consistency_flags"])
        recover.assert_called_once()

    def test_known_title_abbreviation_official_url_recall_allows_scene_narrative_bridge(self):
        pipeline = build_pipeline()
        title = "아카데미 생존 갤러리"
        post = PostInput(
            post_id=20010038,
            title="아생갤) 가장 무서웠던 순간이",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(
                    type="text",
                    text="폐허가 된 도심지 장면과 현생 서사가 대체 어떻게 되길래",
                )
            ],
            comments=[],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=[],
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "discuss_work",
                    "primary_domain": "novel_literature",
                }
            },
        )

        with patch.object(
            pipeline,
            "_recover_corrected_title_official_url",
            return_value="https://novelpia.com/novel/380218",
        ) as recover:
            promotion = pipeline._known_title_abbreviation_official_url_recall_promotion(
                ctx,
                extended_identity={},
                final_decision={"discussion_type": "character_talk"},
                verification_result={},
            )

        self.assertTrue(
            pipeline._known_title_abbreviation_post_work_bridge(
                ctx,
                title,
                "아생갤",
            )
        )
        self.assertIsNotNone(promotion)
        self.assertEqual(promotion["official_title"], title)
        self.assertEqual(
            promotion["heretic_url"],
            "https://novelpia.com/novel/380218",
        )
        recover.assert_called_once()

    def test_title_anchor_recovers_known_abbreviation_official_from_bridge_filtered_preview(self):
        class FilteredOfficialSearch:
            def search(self, query, purpose=""):
                return []

            def _search_with_meta(self, query, purpose=""):
                return [], {
                    "raw_total": 1,
                    "lang_filtered": 1,
                    "lang_filter_reasons": {"token_mismatch:official": 1},
                    "filtered_preview": [
                        {
                            "title": "웹소설로 꿈꾸는 세상! - 괴담 호텔 탈출기 - 노벨피아",
                            "url": "https://novelpia.com/novel/102155",
                            "content": "노벨피아에서 연재 중인 웹소설 괴담 호텔 탈출기.",
                            "filter_reason": "token_mismatch:official",
                        }
                    ],
                }

        search = FilteredOfficialSearch()
        orchestrator = Orchestrator(experts={}, search_fn=search.search)
        ctx = ConversationContext(
            post_id=20010037,
            post_data={
                "title": "오늘 담텔기 오냐?",
                "content_blocks": [{"type": "text", "text": "아님 12시 넘어서 내일 새벽에 오냐"}],
            },
            comments=[],
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {"discourse_analysis": {"primary_domain": "novel_literature", "intent": "ask_question"}},
        )

        with patch.dict(os.environ, {"PIPELINE_SEARCH_CONCURRENCY": "1"}):
            results = orchestrator._execute_searches(
                [{"purpose": "title_anchor_official_probe", "priority": 0, "query": "담텔기 노벨피아"}],
                post_id=ctx.post_id,
                ctx=ctx,
            )

        self.assertEqual(results[0]["url"], "https://novelpia.com/novel/102155")
        self.assertTrue(results[0].get("_bridge_filtered_recovered"))
        self.assertEqual(results[0]["_purpose"], "title_anchor_official_probe")

    def test_corrected_title_url_recovery_prefers_site_scoped_novelpia_detail_query(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=CountingSearchMCP(), max_iterations=2)
        title = "괴담 호텔 탈출기"
        post = PostInput(
            post_id=20010024,
            title="오늘 담텔기 오냐?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="아님 12시 넘어서 내일 새벽에 오냐")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)

        recovered = pipeline._recover_corrected_title_official_url(
            ctx,
            title=title,
            alias_text="담텔기",
            purpose="known_title_abbreviation_official_url_recall",
            allow_known_abbreviation_anchor=True,
        )

        self.assertIsNone(recovered)
        self.assertGreaterEqual(len(pipeline.mcp.calls), 1)
        self.assertEqual(
            pipeline.mcp.calls[0]["query"],
            'site:novelpia.com/novel "괴담 호텔 탈출기"',
        )

    def test_confirmed_alias_known_abbreviation_recall_allows_update_question_no_work(self):
        pipeline = build_pipeline()
        title = "괴담 호텔 탈출기"
        post = PostInput(
            post_id=20010010,
            title="오늘 담텔기 오냐?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="노피아 최신화 지각인가")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "ask_question",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        extended_identity = {
            "is_relevant": False,
            "work_resolution": "none",
            "title_resolution_state": "unresolved_matchable",
            "discussion_type": "noise",
            "consistency_flags": [],
        }

        with patch(
            "llm_batch.agentic_pipeline.official_url_recoverable",
            return_value={
                "official_title": title,
                "heretic_url": "https://novelpia.com/novel/102155",
                "source_tier": "official_detail",
                "matched_clue": "confirmed_alias:담텔기",
                "confidence": "High",
            },
        ):
            recovered_identity, recovered_candidates, primary_work, promotion = (
                pipeline._apply_official_url_recall_promotion(
                    ctx=ctx,
                    extended_identity=extended_identity,
                    title_candidates=[
                        DetectedTitle(
                            official_title="다른 공식 작품",
                            heretic_url="https://novelpia.com/novel/999999",
                            confidence="High",
                        )
                    ],
                    primary_work=None,
                    verification_result={"is_relevant": False, "novel_identity": {}},
                    final_decision={"discussion_type": "noise", "final_reasoning": "웹소설 토론으로 보기 어려움"},
                )
            )

        self.assertIsNotNone(promotion)
        self.assertEqual(recovered_identity["official_title"], title)
        self.assertEqual(recovered_identity["heretic_url"], "https://novelpia.com/novel/102155")
        self.assertEqual(primary_work.official_title, title)
        self.assertEqual(recovered_candidates[0].alias_or_mention, "담텔기")
        self.assertIn("known_title_abbreviation_official_detail_anchor", recovered_identity["consistency_flags"])
        self.assertIn("confirmed_alias:담텔기", recovered_identity["consistency_flags"])

    def test_title_body_official_detail_anchor_allows_no_work_recall(self):
        pipeline = build_pipeline()
        title = "두바이의 쫀득한 여초딩 재벌 9세"
        post = PostInput(
            post_id=20010011,
            title="두바이만 붙이면 잘되네",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="두바이 쫀득 뷰지로 ts 환생 배우 노맨스 인방 #TS #배우")
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "context_clues": {
                    "title_as_body_continuation": True,
                    "title_body_joined_text": "두바이만 붙이면 잘되네 두바이 쫀득 뷰지로 ts 환생 배우 노맨스 인방 #TS #배우",
                },
                "search_requests": [{"purpose": "official_title_verify", "query": "두바이 쫀득 뷰지 웹소설"}],
                "detected_entities": {"possible_titles": ["두바이 쫀득 뷰지"]},
            },
        )
        ctx.search_results = [
            {
                "title": title,
                "url": "https://novelpia.com/novel/420829",
                "content": f"{title} 웹소설 작품 페이지.",
            }
        ]
        ctx.fetched_page_info = [
            {
                "url": "https://novelpia.com/novel/420829",
                "title": "403 Forbidden",
                "page_title": "403 Forbidden",
                "structured_info": {
                    "content_status": "unavailable",
                    "content_status_source": "llm",
                    "title": "403 Forbidden",
                    "page_title": "403 Forbidden",
                },
            }
        ]
        extended_identity = {
            "is_relevant": True,
            "work_resolution": "unresolved",
            "title_resolution_state": "unresolved_matchable",
            "discussion_type": "general",
            "consistency_flags": [],
            "topicality": "core_relevant",
        }

        with patch(
            "llm_batch.agentic_pipeline.official_url_recoverable",
            return_value={
                "official_title": title,
                "heretic_url": "https://novelpia.com/novel/420829",
                "source_tier": "official_detail",
                "matched_clue": "full_title_surface:두바이 쫀득 뷰지",
                "confidence": "High",
            },
        ):
            recovered_identity, recovered_candidates, primary_work, promotion = (
                pipeline._apply_official_url_recall_promotion(
                    ctx=ctx,
                    extended_identity=extended_identity,
                    title_candidates=[
                        DetectedTitle(
                            official_title="다른 공식 작품",
                            heretic_url="https://novelpia.com/novel/999999",
                            confidence="High",
                        )
                    ],
                    primary_work=None,
                    verification_result={
                        "is_relevant": False,
                        "novel_identity": {},
                        "relation_judgment": {
                            "relation_type": "thematic_overlap_only",
                            "discussion_target": "genre_general",
                            "promotion_decision": "hold",
                        },
                    },
                    final_decision={"discussion_type": "noise", "final_reasoning": "정식 작품 토론이 불명확"},
                )
            )

        self.assertIsNotNone(promotion)
        self.assertEqual(recovered_identity["official_title"], title)
        self.assertEqual(recovered_identity["heretic_url"], "https://novelpia.com/novel/420829")
        self.assertEqual(primary_work.official_title, title)
        self.assertIn("title_body_official_detail_anchor", recovered_identity["consistency_flags"])
        self.assertEqual(recovered_candidates[0].official_title, title)

    def test_title_body_official_detail_anchor_guards_final_reread_without_recall_flag(self):
        pipeline = build_pipeline()
        title = "두바이의 쫀득한 여초딩 재벌 9세"
        post = PostInput(
            post_id=20010022,
            title="두바이만 붙이면 잘되네",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(
                    type="text",
                    text="두바이 쫀득 뷰지로 ts 환생했더니 한국에서 모셔가려고 난리 #TS #배우 #노맨스 #인방",
                )
            ],
            comments=["두바이 불끈 자지한테 암타당해서 전용케이스됨"],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "context_clues": {
                    "title_as_body_continuation": True,
                    "title_body_joined_text": (
                        "두바이만 붙이면 잘되네 "
                        "두바이 쫀득 뷰지로 ts 환생했더니 한국에서 모셔가려고 난리 #TS #배우 #노맨스 #인방"
                    ),
                }
            },
        )
        ctx.search_results = [
            {
                "title": f"웹소설로 꿈꾸는 세상! - {title} - 노벨피아",
                "url": "https://novelpia.com/novel/419119",
                "content": f"{title} #TS #배우 #노맨스 #인방",
                "from_query": "두바이 쫀득 TS 환생 인방 노벨피아",
            }
        ]

        keep = pipeline._should_keep_final_semantic_resolution_after_official_recall_anchor(
            ctx=ctx,
            official_title=title,
            verification_result={},
            title_candidates=[],
            consistency_flags=[],
        )

        self.assertTrue(keep)

    def test_title_body_listing_snippet_recall_verifies_official_detail_url(self):
        pipeline = build_pipeline()
        title = "두바이의 쫀득한 여초딩 재벌 9세"
        post = PostInput(
            post_id=20010015,
            title="두바이만 붙이면 잘되네",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="두바이 쫀득 뷰지로 ts 환생했더니 한국에서 모셔가려고 난리"),
                ContentBlock(type="text", text="#TS #배우 #노맨스 #인방"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "context_clues": {
                    "title_as_body_continuation": True,
                    "title_body_joined_text": "두바이만 붙이면 잘되네 두바이 쫀득 뷰지로 ts 환생했더니 한국에서 모셔가려고 난리 #TS #배우 #노맨스 #인방",
                }
            },
        )
        ctx.search_results = [
            {
                "title": "웹소설로 꿈꾸는 세상! - 자유연재 - 노벨피아",
                "url": "https://novelpia.com/freestory/view/view/72/TS/zlib?main_genre=&is_please_write=",
                "content": "... 환생 #TS. 25.06.29 UP. 자유 90년대 마법소녀는 응답 ... 두바이의 쫀득한 여초딩 재벌 9세 자유 ...",
                "query": "두바이 쫀득 TS 환생 인방 노벨피아",
                "purpose": "title_body_sanitized_platform_probe",
            }
        ]

        def recover(_ctx, *, title, **_kwargs):
            _ctx.search_results.append(
                {
                    "title": f"웹소설로 꿈꾸는 세상! - {title} - 노벨피아",
                    "url": "https://novelpia.com/novel/420829",
                    "content": f"플러스작품 - {title}.",
                }
            )
            return "https://novelpia.com/novel/420829"

        with patch("llm_batch.agentic_pipeline.official_url_recoverable", return_value=None), patch.object(
            pipeline,
            "_recover_corrected_title_official_url",
            side_effect=recover,
        ) as recover_mock:
            recovered_identity, recovered_candidates, primary_work, promotion = (
                pipeline._apply_official_url_recall_promotion(
                    ctx=ctx,
                    extended_identity={
                        "is_relevant": False,
                        "work_resolution": "none",
                        "title_resolution_state": "adjacent",
                        "discussion_type": "trope_discussion",
                        "consistency_flags": [],
                    },
                    title_candidates=[],
                    primary_work=None,
                    verification_result={
                        "is_relevant": False,
                        "novel_identity": {},
                        "relation_judgment": {
                            "relation_type": "thematic_overlap_only",
                            "discussion_target": "genre_general",
                            "promotion_decision": "hold",
                        },
                    },
                    final_decision={"discussion_type": "noise", "final_reasoning": "정식 작품 토론이 불명확"},
                )
            )

        self.assertIsNotNone(promotion)
        self.assertEqual(recovered_identity["official_title"], title)
        self.assertEqual(recovered_identity["heretic_url"], "https://novelpia.com/novel/420829")
        self.assertEqual(primary_work.official_title, title)
        self.assertEqual(recovered_candidates[0].official_title, title)
        self.assertIn("title_body_official_detail_anchor", recovered_identity["consistency_flags"])
        recover_mock.assert_called_once()

    def test_title_body_recall_ignores_low_information_common_surface(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=20010016,
            title="아생갤) 가장 무서웠던 순간이",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="내 주변에 있던 모든 것들이 사라지고 폐허가 된 도심지였다"),
                ContentBlock(type="text", text="현생 서사가 대체 어떻게 되길래"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "context_clues": {
                    "title_as_body_continuation": True,
                    "title_body_joined_text": (
                        "아생갤 가장 무서웠던 순간이 내 주변에 있던 모든 것들이 사라지고 "
                        "폐허가 된 도심지였다"
                    ),
                }
            },
        )
        ctx.search_results = [
            {
                "title": "모든 한글 사용료 청구",
                "url": "https://novelpia.com/novel/382055",
                "content": "노벨피아 작품 페이지",
                "query": "아생갤 노벨피아",
                "purpose": "title_alias_platform_recall",
            }
        ]
        ctx.fetched_page_info = [
            {
                "url": "https://novelpia.com/novel/382055",
                "title": "모든 한글 사용료 청구",
                "page_title": "모든 한글 사용료 청구",
                "structured_info": {
                    "title": "모든 한글 사용료 청구",
                    "page_title": "모든 한글 사용료 청구",
                    "content_status": "ok",
                    "content_status_source": "llm",
                },
            }
        ]

        promotion = pipeline._title_body_listing_official_url_recall_promotion(
            ctx,
            extended_identity={},
            verification_result={
                "relation_judgment": {
                    "relation_type": "thematic_overlap_only",
                    "discussion_target": "community_banter",
                    "promotion_decision": "hold",
                }
            },
            final_decision={"discussion_type": "noise", "_title_deliberately_null": True},
        )

        self.assertIsNone(promotion)
        self.assertFalse(getattr(ctx, "_title_body_official_detail_anchor", False))

    def test_title_body_recall_ignores_descriptive_modifier_surface(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=20010017,
            title="표지 수상할 정도로 좋네",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="수상할 정도로 고해상도의 표지라서 그냥 감상 중"),
                ContentBlock(type="text", text="작품명은 모르겠고 이미지 퀄리티 이야기임"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "context_clues": {
                    "title_as_body_continuation": True,
                    "title_body_joined_text": (
                        "표지 수상할 정도로 좋네 수상할 정도로 고해상도의 표지라서 그냥 감상 중"
                    ),
                }
            },
        )
        ctx.search_results = [
            {
                "title": "수상할 정도로 돈이 많은 성주님 [독점]",
                "url": "https://novelpia.com/novel/507153",
                "content": "노벨피아 작품 페이지",
                "query": "수상할 정도로 노벨피아",
                "purpose": "title_alias_platform_recall",
            }
        ]
        ctx.fetched_page_info = [
            {
                "url": "https://novelpia.com/novel/507153",
                "title": "수상할 정도로 돈이 많은 성주님 [독점]",
                "page_title": "수상할 정도로 돈이 많은 성주님 [독점]",
                "structured_info": {
                    "title": "수상할 정도로 돈이 많은 성주님 [독점]",
                    "page_title": "수상할 정도로 돈이 많은 성주님 [독점]",
                    "content_status": "ok",
                    "content_status_source": "llm",
                },
            }
        ]

        promotion = pipeline._title_body_listing_official_url_recall_promotion(
            ctx,
            extended_identity={},
            verification_result={
                "relation_judgment": {
                    "relation_type": "thematic_overlap_only",
                    "discussion_target": "community_banter",
                    "promotion_decision": "hold",
                }
            },
            final_decision={"discussion_type": "noise", "_title_deliberately_null": True},
        )

        self.assertIsNone(promotion)
        self.assertFalse(getattr(ctx, "_title_body_official_detail_anchor", False))

    def test_typed_image_title_platform_search_recovers_official_detail_title(self):
        class OcrPhraseSearchMCP:
            def __init__(self):
                self.calls = []

            def search(self, query, purpose=""):
                self.calls.append({"query": query, "purpose": purpose})
                if '"[림월드]변방계에서 회귀자로 살아남기"' in query:
                    return {
                        "results": [
                            {
                                "title": "[림월드]변방계에서 회귀자로 살아남기",
                                "url": "https://novelpia.com/novel/382324",
                                "content": "플러스작품 - [림월드]변방계에서 회귀자로 살아남기.",
                            }
                        ]
                    }
                return {"results": []}

        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=OcrPhraseSearchMCP(), max_iterations=2)
        title = "[림월드]변방계에서 회귀자로 살아남기"
        post = PostInput(
            post_id=20010025,
            title="랫따싶 림월드 요소 생각나게 하는거 좋네에",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", url="https://example.test/rimworld.png"),
                ContentBlock(type="text", text="게임적 요소 있는거 아주 굿"),
            ],
            comments=[],
        )
        post_data = pipeline._post_to_dict(post)
        post_data["image_enrichment"] = [
            {
                "explicit_work_title": title,
                "ocr_text": (
                    "림월드 최대의 적폐 건물, 기지 가치 대비 살상력 GOAT, "
                    "초반 생존의 150%는 먹고 들어가는 방어물계의 대협."
                ),
                "visual_summary": "소설 본문을 캡처한 이미지",
                "work_cues": ["림월드", "방어건물", "제작 스킬"],
                "evidence_type": "explicit_text",
                "title_role": "work_title",
            }
        ]
        ctx = ConversationContext(post_id=post.post_id, post_data=post_data, comments=[])
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "context_clues": {
                    "title_as_body_continuation": False,
                }
            },
        )
        ctx.search_results = []

        with patch("llm_batch.agentic_pipeline.official_url_recoverable", return_value=None):
            recovered_identity, recovered_candidates, primary_work, promotion = (
                pipeline._apply_official_url_recall_promotion(
                    ctx=ctx,
                    extended_identity={
                        "is_relevant": False,
                        "work_resolution": "none",
                        "title_resolution_state": "adjacent",
                        "discussion_type": "trope_discussion",
                        "consistency_flags": [],
                    },
                    title_candidates=[],
                    primary_work=None,
                    verification_result={
                        "is_relevant": False,
                        "novel_identity": {},
                        "relation_judgment": {
                            "relation_type": "thematic_overlap_only",
                            "discussion_target": "genre_general",
                            "promotion_decision": "hold",
                        },
                    },
                    final_decision={"discussion_type": "noise", "final_reasoning": "림월드 게임 요소 잡담"},
                )
            )

        self.assertIsNotNone(promotion)
        self.assertEqual(recovered_identity["official_title"], title)
        self.assertEqual(recovered_identity["heretic_url"], "https://novelpia.com/novel/382324")
        self.assertEqual(primary_work.official_title, title)
        self.assertIn("림월드", recovered_candidates[0].alias_or_mention)
        self.assertIn("title_body_official_detail_anchor", recovered_identity["consistency_flags"])
        self.assertTrue(
            any(call["purpose"] == "ocr_phrase_official_url_recall" for call in pipeline.mcp.calls)
        )
        self.assertFalse(
            any("림월드 최대의 적폐 건물" in call["query"] for call in pipeline.mcp.calls)
        )

    def test_official_url_recall_prefers_image_ocr_platform_url(self):
        pipeline = build_pipeline()
        title = "재벌집 막내아들"
        series_url = "https://series.naver.com/novel/detail.series?productNo=4340987"
        kakao_url = "https://page.kakao.com/content/53230180"
        post_data = {
            "post_id": 11658637,
            "title": "재막아)영기는 진짜 답이 없구나",
            "content_blocks": [
                {"type": "image", "url": "https://example.test/reborn-rich-series.png"},
            ],
            "image_enrichment": [
                {
                    "explicit_work_title": title,
                    "explicit_author_name": "산경(山景)",
                    "ocr_text": "재벌집 막내아들 · 474화 산경(山景) SERIES",
                    "visual_summary": "웹소설 본문 텍스트 스크린샷",
                    "work_cues": [title, "순양전기", "영기"],
                    "surface_type": "quoted_text_screenshot",
                    "promotion_eligible": True,
                }
            ],
        }
        ctx = ConversationContext(post_id=11658637, post_data=post_data, comments=[])
        ctx.search_results = [
            {
                "title": "카카오페이지",
                "url": kakao_url,
                "content": "재벌집 막내아들 - 웹소설 현판 TOP",
            },
            {
                "title": "네이버 시리즈",
                "url": series_url,
                "content": "재벌집 막내아들 - 네이버 시리즈 552화 완결 #NOVEL 산경",
            },
        ]

        with patch(
            "llm_batch.agentic_pipeline.official_url_recoverable",
            return_value={
                "official_title": title,
                "heretic_url": kakao_url,
                "source_tier": "official_detail",
                "matched_clue": "search_catalog_contextual_work:재막아 재벌집 막내아들",
                "confidence": "High",
            },
        ), patch.object(
            pipeline,
            "_can_promote_title_after_semantic_no_work",
            return_value=True,
        ):
            recovered_identity, recovered_candidates, primary_work, promotion = (
                pipeline._apply_official_url_recall_promotion(
                    ctx=ctx,
                    extended_identity={
                        "is_relevant": False,
                        "work_resolution": "none",
                        "title_resolution_state": "adjacent",
                        "discussion_type": "character_talk",
                        "consistency_flags": [],
                    },
                    title_candidates=[],
                    primary_work=None,
                    verification_result={
                        "is_relevant": True,
                        "grounding_check": {"anchor_found": "character_mention"},
                    },
                    final_decision={"discussion_type": "character_talk"},
                )
            )

        self.assertIsNotNone(promotion)
        self.assertEqual(recovered_identity["official_title"], title)
        self.assertEqual(recovered_identity["heretic_url"], series_url)
        self.assertEqual(primary_work.heretic_url, series_url)
        self.assertEqual(recovered_candidates[0].heretic_url, series_url)
        self.assertIn("image_platform_official_url_preferred", recovered_identity["consistency_flags"])

    def test_title_alias_platform_search_recovers_ocr_blurb_detail_title(self):
        class AliasSearchMCP:
            def __init__(self):
                self.calls = []

            def search(self, query, purpose=""):
                self.calls.append({"query": query, "purpose": purpose})
                if query == "랫따싶 노벨피아":
                    return {
                        "results": [
                            {
                                "title": "웹소설로 꿈꾸는 세상! - [림월드]변방계에서 회귀자로 살아남기",
                                "url": "https://novelpia.com/novel/382324",
                                "content": (
                                    "잡탕 종족모드가 적용된 변방계에 떨어졌다. "
                                    "#패러디 #림월드 #랫따싶"
                                ),
                            }
                        ]
                    }
                return {"results": []}

        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=AliasSearchMCP(), max_iterations=2)
        title = "[림월드]변방계에서 회귀자로 살아남기"
        post = PostInput(
            post_id=20010026,
            title="랫따싶 림월드 요소 생각나게 하는거 좋네에",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", url="https://example.test/rimworld.png"),
                ContentBlock(type="text", text="게임적 요소 있는거 아주 굿"),
            ],
            comments=["랫따싶 이거 참 잘쓴 패러디야"],
        )
        post_data = pipeline._post_to_dict(post)
        post_data["image_enrichment"] = [
            {
                "ocr_text": "림월드 최대의 적폐 건물, 기지가치 대비 살상력 GOAT",
                "visual_summary": "웹소설 본문 텍스트 스크린샷",
                "work_cues": ["림월드", "방어건물", "제작 스킬"],
                "evidence_type": "explicit_text",
                "title_role": "unknown",
            }
        ]
        ctx = ConversationContext(post_id=post.post_id, post_data=post_data, comments=post.comments)
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "context_clues": {
                    "title_as_body_continuation": False,
                }
            },
        )
        ctx.search_results = []

        with patch("llm_batch.agentic_pipeline.official_url_recoverable", return_value=None):
            recovered_identity, recovered_candidates, primary_work, promotion = (
                pipeline._apply_official_url_recall_promotion(
                    ctx=ctx,
                    extended_identity={
                        "is_relevant": False,
                        "work_resolution": "none",
                        "title_resolution_state": "adjacent",
                        "discussion_type": "trope_discussion",
                        "consistency_flags": [],
                    },
                    title_candidates=[],
                    primary_work=None,
                    verification_result={
                        "is_relevant": False,
                        "novel_identity": {},
                        "relation_judgment": {
                            "relation_type": "thematic_overlap_only",
                            "discussion_target": "genre_general",
                            "promotion_decision": "hold",
                        },
                    },
                    final_decision={"discussion_type": "noise", "final_reasoning": "림월드 게임 요소 잡담"},
                )
            )

        self.assertIsNotNone(promotion)
        self.assertEqual(recovered_identity["official_title"], title)
        self.assertEqual(recovered_identity["heretic_url"], "https://novelpia.com/novel/382324")
        self.assertEqual(primary_work.official_title, title)
        self.assertIn("림월드", recovered_candidates[0].alias_or_mention)
        self.assertIn("랫따싶", recovered_candidates[0].alias_or_mention)
        self.assertIn("title_body_official_detail_anchor", recovered_identity["consistency_flags"])
        self.assertTrue(
            any(call["purpose"] == "title_alias_platform_recall" for call in pipeline.mcp.calls)
        )

    def test_title_alias_platform_search_strips_particles_and_accepts_compact_title_abbrev(self):
        class AliasSearchMCP:
            def __init__(self):
                self.calls = []

            def search(self, query, purpose=""):
                self.calls.append({"query": query, "purpose": purpose})
                if query == "니생들 노벨피아":
                    return {
                        "results": [
                            {
                                "title": "웹소설로 꿈꾸는 세상! - 니들 생각 다 들린다 - 노벨피아",
                                "url": "https://novelpia.com/novel/384318",
                                "content": "노벨피아 작품 니들 생각 다 들린다. 장르소설 갤러리에서 니생들로 불리는 작품.",
                            }
                        ]
                    }
                if query == "김괴라리 노벨피아":
                    return {
                        "results": [
                            {
                                "title": "웹소설로 꿈꾸는 세상! - 괴담에 휘말렸다 - 노벨피아",
                                "url": "https://novelpia.com/novel/363195",
                                "content": "김괴라리 별칭으로 언급되는 괴담에 휘말렸다.",
                            }
                        ]
                    }
                return {"results": []}

        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=AliasSearchMCP(), max_iterations=2)
        post = PostInput(
            post_id=20010027,
            title="니생들이랑 김괴라리 장갤픽 아니였음?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="둘 다 노벨피아 작품 얘기임")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "context_clues": {
                    "title_as_body_continuation": True,
                    "title_body_joined_text": "니생들이랑 김괴라리 장갤픽 아니였음? 둘 다 노벨피아 작품 얘기임",
                }
            },
        )
        ctx.search_results = []

        with (
            patch("llm_batch.agentic_pipeline.official_url_recoverable", return_value=None),
            patch.object(pipeline, "_search_catalog_contextual_work_recall_promotion", return_value=None),
        ):
            recovered_identity, recovered_candidates, primary_work, promotion = (
                pipeline._apply_official_url_recall_promotion(
                    ctx=ctx,
                    extended_identity={
                        "is_relevant": True,
                        "work_resolution": "unresolved",
                        "title_resolution_state": "unresolved_matchable",
                        "discussion_type": "general",
                        "consistency_flags": [],
                    },
                    title_candidates=[],
                    primary_work=None,
                    verification_result={
                        "is_relevant": True,
                        "is_novel_discussion": True,
                        "relation_judgment": {
                            "relation_type": "explicit_alias",
                            "discussion_target": "specific_work",
                            "promotion_decision": "hold",
                        },
                    },
                    final_decision={"discussion_type": "general"},
                )
            )

        self.assertIsNotNone(promotion)
        self.assertEqual(recovered_identity["official_title"], "니들 생각 다 들린다")
        self.assertEqual(recovered_identity["heretic_url"], "https://novelpia.com/novel/384318")
        self.assertEqual(primary_work.official_title, "니들 생각 다 들린다")
        self.assertIn("title_body_official_detail_anchor", recovered_identity["consistency_flags"])
        self.assertIn("title_body_search_result:니생들", recovered_identity["consistency_flags"])
        self.assertEqual(recovered_candidates[0].alias_or_mention, "니생들")
        self.assertIn(
            {"query": "니생들 노벨피아", "purpose": "title_alias_platform_recall"},
            pipeline.mcp.calls,
        )
        self.assertFalse(any(call["query"].startswith("김괴라리") for call in pipeline.mcp.calls))

    def test_title_alias_platform_search_rejects_tag_only_alias_when_title_abbrev_does_not_match(self):
        class AliasSearchMCP:
            def __init__(self):
                self.calls = []

            def search(self, query, purpose=""):
                self.calls.append({"query": query, "purpose": purpose})
                if query == "랫따싶 노벨피아":
                    return {
                        "results": [
                            {
                                "title": "웹소설로 꿈꾸는 세상! - 쳇바퀴의 생쥐 사도가 되었다 - 노벨피아",
                                "url": "https://novelpia.com/novel/406113",
                                "content": "랫따싶. #판타지 #전생 #성장. 생쥐 미소녀로 전생했더니 쥐의 여신과 만났다.",
                            }
                        ]
                    }
                return {"results": []}

        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=AliasSearchMCP(), max_iterations=2)
        post = PostInput(
            post_id=20010028,
            title="랫따싶이 머 퍼리말하는거임?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="노벨피아 작품 별칭 물어보는 글")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "context_clues": {
                    "title_as_body_continuation": True,
                    "title_body_joined_text": "랫따싶이 머 퍼리말하는거임? 노벨피아 작품 별칭 물어보는 글",
                }
            },
        )
        ctx.search_results = []

        with (
            patch("llm_batch.agentic_pipeline.official_url_recoverable", return_value=None),
            patch.object(pipeline, "_search_catalog_contextual_work_recall_promotion", return_value=None),
        ):
            recovered_identity, recovered_candidates, primary_work, promotion = (
                pipeline._apply_official_url_recall_promotion(
                    ctx=ctx,
                    extended_identity={
                        "is_relevant": True,
                        "work_resolution": "unresolved",
                        "title_resolution_state": "unresolved_matchable",
                        "discussion_type": "general",
                        "consistency_flags": [],
                    },
                    title_candidates=[],
                    primary_work=None,
                    verification_result={
                        "is_relevant": True,
                        "is_novel_discussion": True,
                        "relation_judgment": {
                            "relation_type": "explicit_alias",
                            "discussion_target": "specific_work",
                            "promotion_decision": "hold",
                        },
                    },
                    final_decision={"discussion_type": "general"},
                )
            )

        self.assertIsNone(promotion)
        self.assertIsNone(primary_work)
        self.assertEqual(recovered_candidates, [])
        self.assertIsNone(recovered_identity.get("official_title"))
        self.assertIn(
            {"query": "랫따싶 노벨피아", "purpose": "title_alias_platform_recall"},
            pipeline.mcp.calls,
        )

    def test_title_lead_alias_release_keeps_visual_cue_no_work_candidate_only(self):
        pipeline = build_pipeline()
        title = "[림월드]변방계에서 회귀자로 살아남기"
        url = "https://novelpia.com/novel/382324"
        post = PostInput(
            post_id=20010029,
            title="랫따싶 칸시가 정실이엿으면",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="바로 시트러스 노예조교 on이엿을텐데")],
            comments=[
                "그치만 폐급이고 - dc App",
                "심지어 시트러스햄은 싸우는 폼보니까 강인함도 있겠다에요",
            ],
        )
        post_data = pipeline._post_to_dict(post)
        post_data["image_enrichment"] = [
            {
                "ocr_text": "Rim World -modded- 사료 섭취 -12 동물밥을 먹어야 했어.",
                "visual_summary": "게임 UI 스타일의 텍스트가 있는 캐릭터 일러스트.",
                "explicit_work_title": "Rim World",
                "evidence_type": "explicit_text",
                "work_cues": ["Rim World", "modded", "게임 UI 스타일의 텍스트"],
            }
        ]
        ctx = ConversationContext(post_id=post.post_id, post_data=post_data, comments=post.comments)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {"discourse_analysis": {"primary_domain": "gaming", "intent": "make_joke", "target_kind": "character"}},
        )
        ctx.search_results = [
            {
                "title": title,
                "url": url,
                "content": "노벨피아 작품. #패러디 #림월드 #랫따싶.",
                "snippet": "단, 죽어서만. #패러디 #림월드 #랫따싶.",
                "query": "Rim World 웹소설 노벨피아",
            }
        ]

        candidate, hit = pipeline._resolve_title_lead_alias_official_detail_release_candidate(ctx)

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.official_title, title)
        self.assertEqual(candidate.heretic_url, url)
        self.assertEqual(candidate.alias_or_mention, "랫따싶")
        self.assertEqual(hit["source"], "title_lead_alias_official_detail_release")

        verification_result = {
            "is_relevant": True,
            "is_novel_discussion": True,
            "novel_identity": {"official_title": title, "heretic_url": url},
            "slang_insight": {
                "detected_term": "랫따싶",
                "canonical_work_alias": "랫따싶",
                "decoded_term": title,
                "decode_verified": True,
                "alias_scope": "pure_work_alias",
            },
            "grounding_check": {
                "anchor_found": "title_mention",
                "matched_alias": "랫따싶",
                "matched_title": title,
            },
            "relation_judgment": {
                "relation_type": "explicit_alias",
                "discussion_target": "specific_work",
                "promotion_decision": "allow",
                "observed_aliases": ["랫따싶"],
            },
        }
        self.assertTrue(
            pipeline._has_verified_alias_official_detail_anchor(
                ctx,
                title,
                verification_result=verification_result,
                title_candidates=[candidate],
            )
        )
        self.assertTrue(
            pipeline._has_explicit_alias_official_work_lock(
                ctx,
                title,
                verification_result,
            )
        )

        ctx.uncertainty_sources.append(
            "intent_permit_for_title_search=false(semantic_seed_review_not_specific_work)"
        )
        ctx.discourse_warning = "community_banter(no_work_anchor)"
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "primary_domain": "gaming",
                    "intent": "make_joke",
                    "target_kind": "character",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        self.assertFalse(
            pipeline._can_promote_title_after_semantic_no_work(
                ctx,
                title,
                source="official_url_recall_gate",
                verification_result=verification_result,
                title_candidates=[candidate],
            )
        )

    def test_title_lead_alias_release_keeps_tag_only_question_blocked(self):
        pipeline = build_pipeline()
        title = "[림월드]변방계에서 회귀자로 살아남기"
        post = PostInput(
            post_id=20010030,
            title="랫따싶이 머 퍼리말하는거임?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="노벨피아 태그에 있는 별칭 물어보는 글")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "primary_domain": "community",
                    "intent": "ask_question",
                    "target_kind": "community",
                }
            },
        )
        ctx.search_results = [
            {
                "title": title,
                "url": "https://novelpia.com/novel/382324",
                "content": "노벨피아 작품. #패러디 #림월드 #랫따싶.",
                "snippet": "단, 죽어서만. #패러디 #림월드 #랫따싶.",
                "query": "랫따싶 노벨피아",
            }
        ]

        candidate, hit = pipeline._resolve_title_lead_alias_official_detail_release_candidate(ctx)

        self.assertIsNone(candidate)
        self.assertIsNone(hit)

    def test_batch_alias_verified_official_detail_does_not_override_no_work_state(self):
        pipeline = build_pipeline()
        title = "잘생기면 편해지는 인방 생활"
        post = PostInput(
            post_id=20010012,
            title="잘생인방 뭔일 터짐?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="알려주면 노나메 임신 질싸짤 공유하")],
            comments=["노피아가 뽑아준 표지때문에", "표지가 별로래"],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=post.comments,
        )
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "share_information",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "title_novel_terms": ["잘생인방"],
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        ctx.search_results = [
            {
                "title": f"웹소설로 꿈꾸는 세상! - {title} - 노벨피아",
                "url": "https://novelpia.com/novel/384016",
                "content": f"{title} 작품 페이지.",
            }
        ]

        self.assertFalse(
            pipeline._can_promote_title_after_semantic_no_work(
                ctx,
                title,
                source="batch_memory_exact_alias_rescued",
                verification_result={
                    "is_relevant": True,
                    "is_novel_discussion": True,
                    "novel_identity": {"official_title": title},
                    "grounding_check": {
                        "anchor_found": "title_mention",
                        "anchor_text": "잘생인방",
                        "matched_alias": "잘생인방",
                        "matched_title": title,
                    },
                    "relation_judgment": {
                        "relation_type": "explicit_alias",
                        "discussion_target": "specific_work",
                        "promotion_decision": "hold",
                    },
                    "slang_insight": {
                        "detected_term": "잘생인방",
                        "decoded_term": title,
                        "decode_verified": True,
                        "canonical_work_alias": "잘생인방",
                        "alias_scope": "pure_work_alias",
                    },
                },
            )
        )

    def test_post_alias_official_detail_bridge_locks_meta_platform_drift(self):
        pipeline = build_pipeline()
        title = "괴담 호텔 탈출기"
        post = PostInput(
            post_id=20010013,
            title="오늘 담텔기 오냐?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="아님 12시 넘어서 내일 새벽에 오냐")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)
        ctx.discourse_warning = "non_novel(meta_platform,high)"
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "ask_question",
                    "target_kind": "platform",
                    "primary_domain": "meta_platform",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        ctx.llm_snippet_analysis = {
            "abbreviation_mappings": [{"abbrev": "담텔기", "full": title}]
        }
        ctx.search_results = [
            {
                "title": f"웹소설로 꿈꾸는 세상! - {title} - 노벨피아",
                "url": "https://novelpia.com/novel/102155",
                "content": "노벨피아에서 연재중인 소설 괴담 호텔 탈출기의 줄임말 담텔기.",
                "query": "담텔기 웹소설 노벨피아",
            }
        ]

        self.assertTrue(
            pipeline._has_post_alias_official_detail_bridge_anchor(
                ctx,
                title,
                alias_text="담텔기",
            )
        )
        self.assertEqual(getattr(ctx, "_post_alias_official_detail_bridge_alias", ""), "담텔기")
        acceptance = pipeline._compute_title_acceptance(
            ctx,
            title,
            {"grounding_check": {"anchor_found": "title_mention"}},
            heretic_url="https://novelpia.com/novel/102155",
        )
        self.assertNotEqual(acceptance["decision"], "reject")
        self.assertIn("official_detail_bridge_anchor", acceptance["notes"])
        self.assertFalse(acceptance["semantic_no_work_block"])

    def test_filtered_official_detail_supports_safe_url_and_post_alias_bridge(self):
        pipeline = build_pipeline()
        title = "괴담 호텔 탈출기"
        post = PostInput(
            post_id=20010016,
            title="오늘 담텔기 오냐?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="아님 12시 넘어서 내일 새벽에 오냐")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.filtered_search_results = [
            {
                "title": f"웹소설로 꿈꾸는 세상! - {title} - 노벨피아",
                "url": "https://novelpia.com/novel/102155",
                "content": f"플러스작품 - {title}.",
                "filter_reason": "token_mismatch:official",
                "filtered": True,
            }
        ]

        self.assertEqual(
            pipeline._filtered_official_detail_url_for_title(ctx, title),
            "https://novelpia.com/novel/102155",
        )
        self.assertEqual(
            pipeline._safe_official_detail_url_for_title(ctx, title=title),
            "https://novelpia.com/novel/102155",
        )
        self.assertTrue(
            pipeline._has_post_alias_official_detail_bridge_anchor(
                ctx,
                title,
                alias_text="담텔기",
            )
        )
        self.assertEqual(getattr(ctx, "_post_alias_official_detail_bridge_alias", ""), "담텔기")

    def test_post_alias_official_detail_recall_overrides_relation_block(self):
        pipeline = build_pipeline()
        title = "잘생기면 편해지는 인방 생활"
        post = PostInput(
            post_id=20010017,
            title="잘생인방 뭔일 터짐?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="알려주면 노나메 임신 질싸짤 공유하")],
            comments=["노피아가 뽑아준 표지때문에", "표지가 별로래"],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "share_information",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        ctx.search_results = [
            {
                "title": f"웹소설로 꿈꾸는 세상! - {title} - 노벨피아",
                "url": "https://novelpia.com/novel/384016",
                "content": f"플러스작품 - {title}. 잘생인방으로 불리는 작품.",
                "query": "잘생인방",
            }
        ]

        with patch(
            "llm_batch.agentic_pipeline.official_url_recoverable",
            return_value={
                "official_title": title,
                "heretic_url": "https://novelpia.com/novel/384016",
                "source_tier": "official_detail",
                "matched_clue": "confirmed_alias:잘생인방",
                "confidence": "High",
            },
        ):
            recovered_identity, recovered_candidates, primary_work, promotion = (
                pipeline._apply_official_url_recall_promotion(
                    ctx=ctx,
                    extended_identity={
                        "is_relevant": False,
                        "work_resolution": "none",
                        "title_resolution_state": "adjacent",
                        "discussion_type": "author_talk",
                        "consistency_flags": [],
                    },
                    title_candidates=[
                        DetectedTitle(
                            official_title="공유하",
                            heretic_url="",
                            confidence="Medium",
                            source_tier="llm_only",
                        )
                    ],
                    primary_work=None,
                    verification_result={
                        "is_relevant": False,
                        "is_novel_discussion": False,
                        "novel_identity": {},
                        "grounding_check": {"anchor_found": "title_mention"},
                        "relation_judgment": {
                            "relation_type": "explicit_alias",
                            "discussion_target": "mixed_or_uncertain",
                            "promotion_decision": "reject",
                        },
                    },
                    final_decision={"discussion_type": "noise", "final_reasoning": "웹소설 토론으로 보기 어려움"},
                )
            )

        self.assertIsNotNone(promotion)
        self.assertEqual(recovered_identity["official_title"], title)
        self.assertEqual(recovered_identity["heretic_url"], "https://novelpia.com/novel/384016")
        self.assertEqual(primary_work.official_title, title)
        self.assertEqual(recovered_candidates[0].alias_or_mention, "잘생인방")
        self.assertIn("post_alias_official_detail_bridge_anchor", recovered_identity["consistency_flags"])
        self.assertIn("confirmed_alias:잘생인방", recovered_identity["consistency_flags"])

    def test_post_alias_official_detail_acceptance_overrides_thematic_reject(self):
        pipeline = build_pipeline()
        title = "잘생기면 편해지는 인방 생활"
        post = PostInput(
            post_id=20010020,
            title="잘생인방 뭔일 터짐?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="알려주면 노나메 임신 질싸짤 공유하")],
            comments=["노피아가 뽑아준 표지때문에", "표지가 별로래"],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "share_information",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        ctx.search_results = [
            {
                "title": f"웹소설로 꿈꾸는 세상! - {title} - 노벨피아",
                "url": "https://novelpia.com/novel/384016",
                "content": f"플러스작품 - {title}.",
                "from_query": "잘생인방",
            }
        ]
        vf_result = {
            "is_relevant": False,
            "is_novel_discussion": False,
            "novel_identity": {"evidence_type": "search_platform_url"},
            "grounding_check": {"anchor_found": "title_mention"},
            "relation_judgment": {
                "relation_type": "thematic_overlap_only",
                "discussion_target": "genre_general",
                "promotion_decision": "reject",
            },
        }

        acceptance = pipeline._compute_title_acceptance(
            ctx,
            title,
            vf_result,
            heretic_url="https://novelpia.com/novel/384016",
        )

        self.assertEqual(acceptance["decision"], "accept")
        self.assertIn("official_detail_issue_alias_bridge", acceptance["notes"])

    def test_relation_summary_alias_issue_bridge_overrides_reject(self):
        pipeline = build_pipeline()
        title = "잘생기면 편해지는 인방 생활"
        post = PostInput(
            post_id=20010021,
            title="잘생인방 뭔일 터짐?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="알려주면 노나메 임신 질싸짤 공유하")],
            comments=["노피아가 뽑아준 표지때문에", "표지가 별로래"],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "share_information",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "title_novel_terms": ["잘생인방"],
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        vf_result = {
            "is_relevant": False,
            "is_novel_discussion": False,
            "novel_identity": {"evidence_type": "search_platform_url"},
            "grounding_check": {
                "anchor_found": "title_mention",
                "title_abbrev_mentioned": True,
                "matched_alias": "잘생인방",
            },
            "slang_insight": {
                "detected_term": "잘생인방",
                "decoded_term": title,
                "decode_verified": True,
                "canonical_work_alias": "잘생인방",
                "alias_scope": "pure_work_alias",
            },
            "relation_judgment": {
                "relation_type": "explicit_alias",
                "discussion_target": "mixed_or_uncertain",
                "promotion_decision": "reject",
                "search_support_summary": {"official_exact_title_count": 1},
            },
        }

        acceptance = pipeline._compute_title_acceptance(ctx, title, vf_result)

        self.assertEqual(acceptance["decision"], "accept")
        self.assertIn("official_detail_issue_alias_bridge", acceptance["notes"])
        self.assertIn("relation_official_alias_bridge", acceptance["notes"])

    def test_title_led_discontinuation_alias_accepts_official_detail_hold(self):
        pipeline = build_pipeline()
        title = "탑의 성좌들이 날 애호한다"
        post = PostInput(
            post_id=11669928,
            title="탑성좌애호 노벨피아 이거 연중했었네",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="안돼~~")],
            comments=[
                "슬프구나",
                "대충 입가리고 슬프다고 하는 콘",
                "존나 뜬금 없이 뒤져버림",
                "이유를 모르겠음 그냥 갑자기 죽어버림",
                "솔직히 힐집악라이크 댓천마라이크 중에 제일 재밌게 봤는데 존나 아까움",
            ],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "short_reaction",
                "detected_entities": {
                    "possible_titles": ["탑성좌애호"],
                    "key_terms": ["노벨피아", "연중"],
                },
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "express_opinion",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "title_novel_terms": ["탑성좌애호"],
                }
            },
        )
        ctx.search_results = [
            {
                "title": f"웹소설로 꿈꾸는 세상! - {title} - 노벨피아",
                "url": "https://novelpia.com/novel/377032",
                "content": f"{title} PLUS 독점 연재중단. 탑성좌애호 노벨피아.",
                "from_query": "탑성좌애호 노벨피아",
            }
        ]
        vf_result = {
            "is_relevant": True,
            "is_novel_discussion": True,
            "novel_identity": {"evidence_type": "search_platform_url"},
            "grounding_check": {
                "anchor_found": "title_abbrev_mention",
                "title_abbrev_mentioned": True,
                "matched_alias": "탑성좌애호",
            },
            "relation_judgment": {
                "relation_type": "explicit_alias",
                "discussion_target": "specific_work",
                "promotion_decision": "hold",
                "search_support_summary": {
                    "official_exact_title_count": 1,
                    "alias_in_post_count": 1,
                    "explicit_alias_bridge_count": 0,
                },
            },
        }

        self.assertTrue(pipeline._has_title_led_work_consumption_signal(ctx))
        acceptance = pipeline._compute_title_acceptance(
            ctx,
            title,
            vf_result,
            heretic_url="https://novelpia.com/novel/377032",
        )

        self.assertEqual(acceptance["decision"], "accept")
        self.assertTrue(acceptance["title_led_consumption_bridge"])
        self.assertIn("title_led_consumption_bridge", acceptance["notes"])
        self.assertIn("strong_body_grounding", acceptance["notes"])
        self.assertEqual(acceptance["relation_promotion"], "hold")

    def test_title_led_evaluation_marker_accepts_empty_body_official_alias_bridge(self):
        pipeline = build_pipeline()
        title = "암흑가 보스요? 제가요?"
        post = PostInput(
            post_id=11660257,
            title="암흑가보스<<이거 재밋네",
            author="ㅇㅇ",
            content_blocks=[],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "short_reaction",
                "detected_entities": {
                    "possible_titles": ["암흑가보스"],
                    "key_terms": ["재밋네"],
                },
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "express_opinion",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "title_novel_terms": ["암흑가보스"],
                }
            },
        )
        ctx.search_results = [
            {
                "title": f"웹소설로 꿈꾸는 세상! - {title} - 노벨피아",
                "url": "https://novelpia.com/novel/384111",
                "content": f"{title} 작가명 손아픈사람.",
                "from_query": "암흑가보스 노벨피아",
            }
        ]
        vf_result = {
            "is_relevant": True,
            "is_novel_discussion": True,
            "novel_identity": {"evidence_type": "search_platform_url"},
            "grounding_check": {
                "anchor_found": "title_abbrev_mention",
                "title_abbrev_mentioned": True,
                "matched_alias": "암흑가보스",
            },
            "relation_judgment": {
                "relation_type": "title_alias",
                "discussion_target": "specific_work",
                "promotion_decision": "hold",
                "search_support_summary": {
                    "official_exact_title_count": 1,
                    "alias_in_post_count": 1,
                    "explicit_alias_bridge_count": 0,
                },
            },
        }

        self.assertTrue(pipeline._has_title_led_work_consumption_signal(ctx))
        acceptance = pipeline._compute_title_acceptance(
            ctx,
            title,
            vf_result,
            heretic_url="https://novelpia.com/novel/384111",
        )

        self.assertEqual(acceptance["decision"], "accept")
        self.assertTrue(acceptance["title_led_consumption_bridge"])
        self.assertIn("title_led_consumption_bridge", acceptance["notes"])

    def test_title_led_evaluation_marker_accepts_question_style_official_title(self):
        pipeline = build_pipeline()
        title = "테라포밍"
        post = PostInput(
            post_id=11660237,
            title="테라포밍 볼만함?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="주인공 멍창하다는 말 많던데 초반도 봐야함?")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "short_reaction",
                "detected_entities": {
                    "possible_titles": ["테라포밍"],
                    "key_terms": ["볼만함"],
                },
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "ask_question",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "title_novel_terms": ["테라포밍"],
                }
            },
        )
        ctx.search_results = [
            {
                "title": "웹소설로 꿈꾸는 세상! - 테라포밍 - 노벨피아",
                "url": "https://novelpia.com/novel/61947",
                "content": "테라포밍 PLUS 독점 연재중.",
                "from_query": "테라포밍 노벨피아",
            }
        ]
        vf_result = {
            "is_relevant": True,
            "is_novel_discussion": True,
            "novel_identity": {"evidence_type": "search_platform_url"},
            "grounding_check": {
                "anchor_found": "title_abbrev_mention",
                "title_abbrev_mentioned": True,
                "matched_alias": "테라포밍",
            },
            "relation_judgment": {
                "relation_type": "exact_title",
                "discussion_target": "specific_work",
                "promotion_decision": "hold",
                "search_support_summary": {
                    "official_exact_title_count": 1,
                    "alias_in_post_count": 1,
                    "explicit_alias_bridge_count": 0,
                },
            },
        }

        self.assertTrue(pipeline._has_title_led_work_consumption_signal(ctx))
        acceptance = pipeline._compute_title_acceptance(
            ctx,
            title,
            vf_result,
            heretic_url="https://novelpia.com/novel/61947",
        )

        self.assertEqual(acceptance["decision"], "accept")
        self.assertTrue(acceptance["title_led_consumption_bridge"])
        self.assertIn("title_led_consumption_bridge", acceptance["notes"])

    def test_title_led_gate_cannot_replace_prior_context_only_with_unresolved_state(self):
        pipeline = build_pipeline()
        title = "테라포밍"
        url = "https://novelpia.com/novel/61947"
        post = PostInput(
            post_id=11660237,
            title="테라포밍 볼만함?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="주인공 멍창하다는 말 많던데")],
            comments=["ㅇㅇ 야스 개꼴림 쥬지터짐"],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "short_reaction",
                "detected_entities": {
                    "possible_titles": [title],
                    "key_terms": ["볼만함"],
                },
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "ask_question",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "title_novel_terms": [title],
                }
            },
        )
        ctx.search_results = [
            {
                "title": "웹소설로 꿈꾸는 세상! - 테라포밍 - 노벨피아",
                "url": url,
                "content": "테라포밍 PLUS 독점 연재중.",
                "from_query": "테라포밍 노벨피아",
            }
        ]
        ctx._last_promotion_gate_decision = {
            "status": "candidate_only",
            "publish_allowed": False,
            "official_title": None,
            "official_url": None,
            "candidate_preserved": True,
            "reason_codes": ["scope_context_only"],
            "scope": {
                "scope_kind": "context_only",
                "direct_bridge_sources": ["official_detail_candidate"],
            },
        }
        final_decision = {
            "discussion_type": "general",
            "work_resolution": "unresolved",
            "title_resolution_state": "unresolved_matchable",
        }
        vf_result = {
            "is_relevant": True,
            "is_novel_discussion": True,
            "novel_identity": {"evidence_type": "search_platform_url"},
            "grounding_check": {
                "anchor_found": "title_abbrev_mention",
                "title_abbrev_mentioned": True,
                "matched_alias": title,
            },
            "relation_judgment": {
                "relation_type": "exact_title",
                "discussion_target": "mixed_or_uncertain",
                "promotion_decision": "hold",
                "search_support_summary": {
                    "official_exact_title_count": 1,
                    "alias_in_post_count": 1,
                    "best_official_url": url,
                },
            },
        }
        acceptance = pipeline._compute_title_acceptance(ctx, title, vf_result, heretic_url=url)

        decision = pipeline._record_title_led_alias_public_title_gate_decision(
            ctx,
            title,
            candidate_url=url,
            final_decision=final_decision,
            verification_result=vf_result,
            title_candidates=[
                DetectedTitle(
                    official_title=title,
                    heretic_url=url,
                    confidence="High",
                    alias_or_mention=title,
                    source_tier="official_detail",
                    page_type="novel_page",
                )
            ],
            acceptance=acceptance,
        )

        self.assertFalse(decision["publish_allowed"])
        self.assertIsNone(ctx._last_promotion_gate_decision["official_title"])
        self.assertEqual(ctx._last_promotion_gate_state["scope"]["scope_kind"], "current_work")
        self.assertIn(
            "title_led_consumption_bridge",
            ctx._last_promotion_gate_state["scope"]["direct_bridge_sources"],
        )
        self.assertIsNone(final_decision["_promotion_gate_decision"]["official_url"])

    def test_title_led_gate_blocks_unpreserved_body_compound_character_anchor(self):
        pipeline = build_pipeline()
        title_led_title = "아카데미 생존 갤러리"
        title_led_url = "https://novelpia.com/novel/380218"
        post = PostInput(
            post_id=11698880,
            title="아생갤 개 존나게 재밌군 ㅇㅇ",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="가챠펑크 세드릭도 그렇고"),
                ContentBlock(type="text", text="시원시원한 상남자라서 너무 좋구나"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.search_results = [
            {
                "title": "아카데미 생존 갤러리",
                "url": title_led_url,
                "content": "아카데미 생존 갤러리 작품 상세.",
            }
        ]
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "decoded_terms": [
                    {
                        "original": "아생갤",
                        "best_match": {"title": title_led_title, "confidence": "high"},
                    },
                    {
                        "original": "가챠펑크 세드릭",
                        "morphehens": ["가챠펑크", "세드릭"],
                        "interpretations": [{"type": "character_name", "value": "세드릭"}],
                        "best_match": {"title": None, "confidence": "none"},
                    },
                ]
            },
        )
        final_decision = {
            "discussion_type": "character_talk",
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
        }
        vf_result = {
            "grounding_check": {
                "anchor_found": "title_abbrev_mention",
                "title_abbrev_mentioned": True,
                "matched_alias": "아생갤",
            }
        }
        candidates = [
            DetectedTitle(
                official_title=title_led_title,
                heretic_url=title_led_url,
                confidence="High",
                alias_or_mention="아생갤",
                source_tier="official_detail",
                page_type="novel_page",
            )
        ]

        decision = pipeline._record_title_led_alias_public_title_gate_decision(
            ctx,
            title_led_title,
            candidate_url=title_led_url,
            final_decision=final_decision,
            verification_result=vf_result,
            title_candidates=candidates,
            acceptance={"decision": "accept", "title_led_consumption_bridge": True, "score": 27},
        )

        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertIn("scope_context_only", decision["reason_codes"])
        self.assertIn("unresolved_body_character_work_anchor", decision["reason_codes"])
        self.assertIn("missing_body_work_bridge", decision["reason_codes"])
        state = ctx._last_promotion_gate_state
        self.assertFalse(state["row_discusses_work_as_work"])
        self.assertEqual(state["scope"]["scope_kind"], "context_only")
        self.assertIn("unresolved_body_character_work_anchor", state["scope"]["conflict_reason_codes"])
        self.assertEqual(state["scope"]["competing_candidates"], [])

    def test_title_led_gate_selects_body_verified_work_when_title_led_alias_competes(self):
        pipeline = build_pipeline()
        title_led_title = "아카데미 생존 갤러리"
        title_led_url = "https://novelpia.com/novel/380218"
        body_title = "가챠 중독자의 퓨전펑크 생활"
        body_url = "https://novelpia.com/novel/387014"
        post = PostInput(
            post_id=11698880,
            title="아생갤 개 존나게 재밌군 ㅇㅇ",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="가챠펑크 세드릭도 그렇고"),
                ContentBlock(type="text", text="시원시원한 상남자라서 너무 좋구나"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.verified_character_work_links = [
            {
                "title": body_title,
                "url": body_url,
                "character": "세드릭",
                "alias": "가챠펑크",
                "matched_alias": "가챠펑크",
            }
        ]
        final_decision = {
            "discussion_type": "general",
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
        }
        vf_result = {
            "grounding_check": {
                "anchor_found": "title_abbrev_mention",
                "title_abbrev_mentioned": True,
                "matched_alias": "가챠펑크",
            }
        }
        candidates = [
            DetectedTitle(
                official_title=body_title,
                heretic_url=body_url,
                confidence="High",
                alias_or_mention="가챠펑크",
                source_tier="official_detail",
                page_type="novel_page",
            ),
            DetectedTitle(
                official_title=title_led_title,
                heretic_url=title_led_url,
                confidence="High",
                alias_or_mention="아생갤",
                source_tier="official_detail",
                page_type="novel_page",
            ),
        ]

        _baseline_synthetic_fetched_detail(self, pipeline, ctx, body_title, body_url,
                                           candidate_title=body_title)
        source_before = _baseline_source_snapshot(ctx)

        decision = pipeline._record_title_led_alias_public_title_gate_decision(
            ctx,
            title_led_title,
            candidate_url=title_led_url,
            final_decision=final_decision,
            verification_result=vf_result,
            title_candidates=candidates,
            acceptance={"decision": "accept", "title_led_consumption_bridge": True, "score": 27},
        )

        _baseline_record_contract(self, ctx, decision, source_before, "body_title")

        self.assertEqual(decision["status"], "publish")
        self.assertTrue(decision["publish_allowed"])
        self.assertEqual(decision["official_title"], body_title)
        self.assertEqual(decision["official_url"], body_url)
        self.assertIn("body_verified_work_candidate_selected", decision["reason_codes"])
        state = ctx._last_promotion_gate_state
        self.assertTrue(state["row_discusses_work_as_work"])
        self.assertEqual(state["candidate_title"], body_title)
        self.assertEqual(state["scope"]["scope_kind"], "current_work")
        self.assertEqual(state["scope"]["competing_candidates"], [])
        self.assertIn(
            "body_verified_work_candidate_bridge",
            state["scope"]["direct_bridge_sources"],
        )
        evidence = ctx._last_promotion_gate_evidence
        alias_sources = [
            item["source_path_or_snippet"]
            for item in evidence
            if item["kind"] in {"body_verified_work_candidate_selected", "alias_bridge"}
        ]
        self.assertIn("가챠펑크", alias_sources)

    def test_resolved_public_gate_selects_body_verified_work_for_known_abbreviation_competition(self):
        pipeline = build_pipeline()
        title_led_title = "아카데미 생존 갤러리"
        title_led_url = "https://novelpia.com/novel/380218"
        body_title = "가챠 중독자의 퓨전펑크 생활"
        body_url = "https://novelpia.com/novel/387014"
        post = PostInput(
            post_id=11698880,
            title="아생갤 개 존나게 재밌군 ㅇㅇ",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="가챠펑크 세드릭도 그렇고"),
                ContentBlock(type="text", text="시원시원한 상남자라서 너무 좋구나"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.search_results = [
            {"title": title_led_title, "url": title_led_url, "content": "작품 상세"},
            {"title": body_title, "url": body_url, "content": "가챠펑크 세드릭 등장"},
        ]
        ctx.verified_character_work_links = [
            {
                "title": body_title,
                "url": body_url,
                "character": "세드릭",
                "alias": "가챠펑크",
                "matched_alias": "가챠펑크",
            }
        ]
        final_decision = {
            "title_resolution_allowed": True,
            "is_resolved_work_discussion": True,
            "discussion_type": "general",
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
            "primary_subject_type": "work_discussion",
            "entity_mentions": [
                {
                    "text": "가챠펑크",
                    "entity_type": "work",
                    "canonical_value": body_title,
                    "confidence": "High",
                    "role": "primary",
                }
            ],
        }
        candidates = [
            DetectedTitle(
                official_title=body_title,
                heretic_url=body_url,
                confidence="High",
                alias_or_mention="가챠펑크",
                source_tier="official_detail",
                page_type="novel_page",
            ),
            DetectedTitle(
                official_title=title_led_title,
                heretic_url=title_led_url,
                confidence="High",
                alias_or_mention="아생갤",
                source_tier="official_detail",
                page_type="novel_page",
            ),
        ]

        _baseline_synthetic_fetched_detail(self, pipeline, ctx, body_title, body_url,
                                           candidate_title=body_title)
        source_before = _baseline_source_snapshot(ctx)

        decision = pipeline._record_resolved_public_title_gate_decision(
            ctx,
            title_led_title,
            candidate_url=title_led_url,
            final_decision=final_decision,
            verification_result={},
            title_candidates=candidates,
            source="known_abbreviation_title_guard:known_title_abbrev",
        )

        _baseline_record_contract(self, ctx, decision, source_before, "body_resolved")

        self.assertEqual(decision["status"], "publish")
        self.assertTrue(decision["publish_allowed"])
        self.assertEqual(decision["official_title"], body_title)
        self.assertEqual(decision["official_url"], body_url)
        self.assertIn("body_verified_work_candidate_selected", decision["reason_codes"])
        state = ctx._last_promotion_gate_state
        self.assertEqual(state["candidate_title"], body_title)
        self.assertEqual(state["source"], "known_abbreviation_title_guard:known_title_abbrev")
        self.assertIn("body_verified_work_candidate_bridge", state["scope"]["direct_bridge_sources"])

    def test_known_abbreviation_guard_selects_body_verified_work_before_semantic_gate_publish(self):
        pipeline = build_pipeline()
        title_led_title = "아카데미 생존 갤러리"
        title_led_url = "https://novelpia.com/novel/380218"
        body_title = "가챠 중독자의 퓨전펑크 생활"
        body_url = "https://novelpia.com/novel/387014"
        post = PostInput(
            post_id=11698880,
            title="아생갤 개 존나게 재밌군 ㅇㅇ",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="가챠펑크 세드릭도 그렇고"),
                ContentBlock(type="text", text="시원시원한 상남자라서 너무 좋구나"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)
        ctx.search_results = [
            {"title": title_led_title, "url": title_led_url, "content": "작품 상세"},
            {"title": body_title, "url": body_url, "content": "가챠펑크 세드릭 등장"},
        ]
        ctx.verified_character_work_links = [
            {
                "title": body_title,
                "url": body_url,
                "character": "세드릭",
                "alias": "가챠펑크",
                "matched_alias": "가챠펑크",
            }
        ]
        final_decision = {
            "discussion_type": "general",
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
            "primary_subject_type": "work_discussion",
            "entity_mentions": [
                {
                    "text": "가챠펑크",
                    "entity_type": "work",
                    "canonical_value": body_title,
                    "confidence": "High",
                    "role": "primary",
                }
            ],
        }
        candidates = [
            DetectedTitle(
                official_title=body_title,
                heretic_url=body_url,
                confidence="High",
                alias_or_mention="가챠펑크",
                source_tier="official_detail",
                page_type="novel_page",
            ),
            DetectedTitle(
                official_title=title_led_title,
                heretic_url=title_led_url,
                confidence="High",
                alias_or_mention="아생갤",
                source_tier="official_detail",
                page_type="novel_page",
            ),
        ]

        with patch.dict(
            "llm_batch.agentic_pipeline.KNOWN_TITLE_ABBREVIATIONS",
            {"아생갤": title_led_title},
            clear=False,
        ):
            picked_title, picked_url = pipeline._apply_known_abbreviation_title_guard(
                ctx,
                "아생갤",
                None,
                final_decision=final_decision,
                verification_result={},
                title_candidates=candidates,
            )

        self.assertEqual(picked_title, body_title)
        self.assertEqual(picked_url, body_url)
        gate = ctx._last_promotion_gate_decision
        self.assertEqual(gate["status"], "publish")
        self.assertEqual(gate["official_title"], body_title)
        self.assertIn("body_verified_work_candidate_selected", gate["reason_codes"])

    def test_title_led_gate_trims_unofficial_search_title_extension_to_preserved_candidate(self):
        pipeline = build_pipeline()
        exact_title = "가챠 중독자의 퓨전펑크 생활"
        extended_title = "가챠 중독자의 퓨전펑크 생활 볼려고 했는데"
        post = PostInput(
            post_id=11698880,
            title="아생갤 개 존나게 재밌군 ㅇㅇ",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="가챠펑크 세드릭도 그렇고"),
                ContentBlock(type="text", text="시원시원한 상남자라서 너무 좋구나"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        final_decision = {
            "discussion_type": "character_talk",
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
            "primary_subject_type": "work_discussion",
            "slang_insight": {
                "detected_term": "가챠펑크",
                "decoded_term": exact_title,
                "decode_verified": True,
                "canonical_work_alias": "가챠펑크",
            },
            "entity_mentions": [
                {
                    "text": "가챠펑크",
                    "entity_type": "work",
                    "canonical_value": exact_title,
                    "confidence": "High",
                    "role": "primary",
                }
            ],
        }
        vf_result = {
            "grounding_check": {
                "anchor_found": "character_mention",
                "title_abbrev_mentioned": True,
                "body_abbrev_mentioned": True,
                "matched_alias": "가챠펑크",
            }
        }
        title_candidates = [
            DetectedTitle(
                official_title=exact_title,
                heretic_url="https://namu.wiki/w/가챠%20중독자의%20퓨전펑크%20생활",
                confidence="High",
                alias_or_mention="가챠펑크",
                source_tier="llm_only",
                locked=True,
                reference_role="primary",
            )
        ]

        source_before = _baseline_source_snapshot(ctx)

        decision = pipeline._record_title_led_alias_public_title_gate_decision(
            ctx,
            extended_title,
            candidate_url=None,
            final_decision=final_decision,
            verification_result=vf_result,
            title_candidates=title_candidates,
            acceptance={"decision": "accept", "title_led_consumption_bridge": True, "score": 24},
        )

        _baseline_record_contract(self, ctx, decision, source_before, "trim_original_source")

        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertIsNone(decision["official_title"])
        self.assertIsNone(decision["official_url"])
        self.assertIn("preserved_title_candidate_selected", decision["reason_codes"])
        state = ctx._last_promotion_gate_state
        self.assertEqual(state["candidate_title"], exact_title)
        self.assertIn("title_extension_trimmed", state["scope"]["direct_bridge_sources"])
        self.assertEqual(state["scope"]["competing_candidates"], [])

        self.assertIn("shared_work_bridge_missing", state["scope"]["conflict_reason_codes"])
        self.assertEqual(state["candidate_title"], exact_title)

    def test_batch_alias_gate_blocks_body_verified_character_work_competition(self):
        pipeline = build_pipeline()
        body_title = "가챠 중독자의 퓨전펑크 생활"
        title_led_title = "아카데미 생존 갤러리"
        title_led_url = "https://novelpia.com/novel/390001"
        ctx = ConversationContext(
            post_id=11698880,
            post_data={
                "post_id": 11698880,
                "title": "아생갤 개 존나게 재밌군 ㅇㅇ",
                "content_blocks": [
                    {"type": "text", "text": "가챠펑크 세드릭도 그렇고"},
                    {"type": "text", "text": "시원시원한 상남자라서 너무 좋구나"},
                ],
            },
            comments=[],
        )
        final_decision = {
            "consistency_flags": [
                "official_url_recall_blocked_body_verified_character_work_competes",
                "body_verified_character_work_competes_with_title_led_alias",
            ],
            "blocked_official_title_competing_candidates": [body_title],
        }
        candidate = DetectedTitle(
            official_title=title_led_title,
            heretic_url=title_led_url,
            confidence="High",
            alias_or_mention="아생갤",
            source_tier="official_detail",
            page_type="novel_page",
        )

        decision = pipeline._record_batch_alias_public_title_gate_decision(
            ctx,
            candidate,
            {"alias": "아생갤", "source": "known_title_abbreviation"},
            final_decision=final_decision,
            verification_result={},
        )

        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        state = ctx._last_promotion_gate_state
        self.assertFalse(state["row_discusses_work_as_work"])
        self.assertEqual(state["scope"]["scope_kind"], "context_only")
        self.assertEqual(state["scope"]["competing_candidates"], [body_title])
        self.assertIn(
            "body_verified_character_work_competes_with_title_led_alias",
            state["scope"]["conflict_reason_codes"],
        )

    def test_batch_alias_gate_preserves_unresolved_body_verified_work_candidate_only(self):
        pipeline = build_pipeline()
        body_title = "가챠 중독자의 퓨전펑크 생활"
        body_url = "https://novelpia.com/novel/387014"
        title_led_title = "아카데미 생존 갤러리"
        title_led_url = "https://novelpia.com/novel/390001"
        ctx = ConversationContext(
            post_id=11698880,
            post_data={
                "post_id": 11698880,
                "title": "아생갤 개 존나게 재밌군 ㅇㅇ",
                "content_blocks": [
                    {"type": "text", "text": "가챠펑크 세드릭도 그렇고"},
                    {"type": "text", "text": "시원시원한 상남자라서 너무 좋구나"},
                ],
            },
            comments=[],
        )
        final_decision = {
            "discussion_type": "character_talk",
            "work_resolution": "resolved",
            "title_resolution_state": "unresolved_matchable",
            "primary_subject_type": "work_discussion",
            "primary_subject_text": "메인 화제는 '가챠 중독자의 퓨전펑크 생활' 캐릭터/장면 반응입니다.",
            "slang_insight": {
                "detected_term": "가챠펑크",
                "decoded_term": body_title,
                "decode_verified": True,
                "canonical_work_alias": "가챠펑크",
                "alias_scope": "pure_work_alias",
            },
            "entity_mentions": [
                {
                    "text": "가챠펑크",
                    "entity_type": "work",
                    "canonical_value": body_title,
                    "confidence": "High",
                    "role": "primary",
                }
            ],
            "consistency_flags": [
                "official_url_recall_blocked_body_verified_character_work_competes",
                "body_verified_character_work_competes_with_title_led_alias",
            ],
            "blocked_official_title_competing_candidates": [body_title],
            "candidate_preservation_sources": [
                {
                    "official_title": body_title,
                    "heretic_url": body_url,
                    "confidence": "High",
                    "alias_or_mention": "가챠펑크",
                    "source_tier": "official_detail",
                    "page_type": "novel_page",
                    "content_status": "active",
                    "reference_role": "primary",
                }
            ],
        }
        candidate = DetectedTitle(
            official_title=title_led_title,
            heretic_url=title_led_url,
            confidence="High",
            alias_or_mention="아생갤",
            source_tier="official_detail",
            page_type="novel_page",
        )

        decision = pipeline._record_batch_alias_public_title_gate_decision(
            ctx,
            candidate,
            {"alias": "아생갤", "source": "known_title_abbreviation"},
            final_decision=final_decision,
            verification_result={},
            title_candidates=[
                DetectedTitle(
                    official_title=body_title,
                    heretic_url=body_url,
                    confidence="High",
                    alias_or_mention="가챠펑크",
                    source_tier="official_detail",
                    page_type="novel_page",
                    content_status="active",
                    locked=True,
                )
            ],
        )

        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertIsNone(decision["official_title"])
        self.assertIsNone(decision["official_url"])
        self.assertIn("body_verified_work_candidate_selected", decision["reason_codes"])
        state = ctx._last_promotion_gate_state
        self.assertEqual(state["candidate_title"], body_title)
        self.assertTrue(state["row_discusses_work_as_work"])
        self.assertEqual(state["scope"]["scope_kind"], "current_work")
        self.assertIn("body_verified_work_candidate_bridge", state["scope"]["direct_bridge_sources"])

    def test_title_led_evaluation_preserves_site_scoped_official_probe_under_recommendation_budget(self):
        calls = []

        def search_fn(query, purpose=""):
            calls.append((query, purpose))
            return []

        orchestrator = Orchestrator(experts={}, search_fn=search_fn)
        ctx = ConversationContext(
            post_id=11660237,
            post_data={
                "title": "테라포밍 볼만함?",
                "content_blocks": [{"type": "text", "text": "주인공 멍창하다는 말 많던데"}],
            },
            comments=["ㅇㅇ 야스 개꼴림 쥬지터짐"],
        )
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "recommendation",
                "context_clues": {"is_asking_recommendation": True},
                "detected_entities": {"possible_titles": ["테라포밍"]},
                "key_terms": ["볼만함"],
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "request_recommendation",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "title_novel_terms": ["테라포밍"],
                }
            },
        )
        requests = [
            {"purpose": "official_title_verify", "priority": 0, "query": "테라포밍 웹소설"},
            {"purpose": "title_anchor_official_probe", "priority": 0, "query": "테라포밍 노벨피아"},
            {"purpose": "title_search_community", "priority": 0, "query": "테라포밍 디시"},
            {"purpose": "platform_title_search", "priority": 1, "query": "테라포밍 노벨피아"},
        ]

        self.assertTrue(orchestrator._has_title_led_work_consumption_search_signal(ctx))

        with patch.dict(os.environ, {"PIPELINE_SEARCH_CONCURRENCY": "1"}):
            orchestrator._execute_searches(requests, post_id=ctx.post_id, ctx=ctx)

        self.assertEqual(ctx.search_budget_profile, "core_fast_resolve")
        self.assertEqual(ctx.search_budget_limit, 6)
        self.assertGreaterEqual(len(calls), 1)
        self.assertEqual(
            calls[0],
            ('site:novelpia.com/novel "테라포밍"', "title_anchor_official_probe"),
        )
        self.assertEqual(calls[1], ("시리즈 테라포밍 작가", "platform_title_search"))
        self.assertEqual(calls[2], ("테라포밍 노벨피아", "platform_title_search"))
        self.assertEqual(
            [call for call in calls if call[0] == "테라포밍 노벨피아"],
            [("테라포밍 노벨피아", "platform_title_search")],
        )

    def test_title_led_consumption_signal_revives_low_specific_noise_official_probe(self):
        class StaticExpert:
            def __init__(self, payload):
                self.payload = payload

            def analyze(self, *_args, **_kwargs):
                return self.payload

        calls = []

        def search_fn(query, purpose=""):
            calls.append((query, purpose))
            return []

        orchestrator = Orchestrator(
            experts={
                ExpertType.GATEKEEPER: StaticExpert(
                    {
                        "is_noise": True,
                        "noise_reason": "제목-본문 연속문이며 제목 파편만 존재하는 저특이 잡담 패턴",
                        "post_type": "community_banter",
                        "detected_entities": {
                            "possible_titles": ["암흑가보스"],
                            "possible_authors": [],
                            "possible_characters": [],
                            "platforms_mentioned": [],
                        },
                        "key_terms": ["암흑가보스", "재밋네"],
                        "context_clues": {
                            "title_as_body_continuation": True,
                            "has_specific_names": False,
                        },
                        "search_requests": [],
                        "confidence": "low",
                    }
                ),
                ExpertType.DISCOURSE: StaticExpert(
                    {
                        "discourse_analysis": {
                            "primary_domain": "novel_literature",
                            "domain_confidence": "high",
                            "intent": "discuss_work",
                            "target_kind": "work",
                            "title_body_consistency": True,
                            "is_association_not_discussion": False,
                            "title_novel_terms": ["암흑가보스"],
                            "domain_evidence": ["암흑가보스", "재밋네"],
                        }
                    }
                ),
            },
            search_fn=search_fn,
            fetch_fn=None,
        )

        ctx = orchestrator.process(
            post_data={
                "post_id": 11660257,
                "title": "암흑가보스<<이거 재밋네",
                "content_blocks": [{"type": "image", "url": "https://example.test/cover.jpg"}],
                "neighbor_hints": {"repeated_terms": []},
                "compound_anchor_terms": [],
            },
            comments=[],
            rules_config={},
        )

        gatekeeper_out = ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
        self.assertFalse(gatekeeper_out.get("is_noise"))
        self.assertEqual(gatekeeper_out.get("post_type"), "work_discussion")
        self.assertEqual(getattr(ctx, "noise_override_reason", ""), "title_led_work_consumption")
        self.assertEqual(
            calls[0],
            ('site:novelpia.com/novel "암흑가보스"', "title_anchor_official_probe"),
        )
        self.assertIn(("암흑가보스 노벨피아", "platform_title_search"), calls)

    def test_title_led_mixed_input_injects_naver_series_author_probe_before_budget_tail(self):
        calls = []

        def search_fn(query, purpose=""):
            calls.append((query, purpose))
            return []

        orchestrator = Orchestrator(experts={}, search_fn=search_fn)
        ctx = ConversationContext(
            post_id=11668307,
            post_data={
                "title": "빛세구 궁금한 점 있음",
                "content_blocks": [
                    {
                        "type": "text",
                        "text": (
                            "다시보는 중인데, 각 행성에서 재능이 제일 뛰어난 사람만 골라오는 거 아님? "
                            "전부 엘리트일 텐데 왜 튜토리얼에 폐급이 있지?"
                        ),
                    }
                ],
            },
            comments=[
                "그거 신경쓰면 대부분의 웹소 못 봄  - dc App",
                "이건 중요한 거임... 행성 1위들끼리 급을 나누는 것부터 흥미로운데 행성 1위가 폐급이면...",
            ],
        )
        gatekeeper = {
            "post_type": "work_discussion",
            "detected_entities": {"possible_titles": ["빛세구"]},
        }
        ctx.set_expert_output(ExpertType.GATEKEEPER, gatekeeper)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "ask_question",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "title_novel_terms": ["빛세구"],
                }
            },
        )
        requests = [
            {"purpose": "platform_title_search", "priority": 0, "query": "빛세구 노벨피아"},
            {"purpose": "title_anchor_exact_probe", "priority": 1, "query": "빛세구궁금한"},
            {"purpose": "platform_title_search", "priority": 1, "query": '"빛세구" "시리즈" 웹소설'},
            {"purpose": "abbreviation_meaning_search", "priority": 1, "query": "빛세구 줄임"},
        ]

        self.assertTrue(orchestrator._has_title_led_work_consumption_search_signal(ctx))

        with patch.dict(os.environ, {"PIPELINE_SEARCH_CONCURRENCY": "1"}):
            orchestrator._execute_searches(requests, post_id=ctx.post_id, ctx=ctx)

        queries = [query for query, _purpose in calls]
        self.assertEqual(ctx.search_budget_profile, "core_fast_resolve")
        self.assertEqual(ctx.search_budget_limit, 6)
        self.assertIn("시리즈 빛세구 작가", queries[:3])
        self.assertNotIn('"빛세구" "시리즈" 웹소설', queries)
        self.assertLess(
            queries.index("시리즈 빛세구 작가"),
            queries.index("빛세구궁금한"),
        )

    def test_title_led_platform_probe_normalizer_routes_unscoped_novelpia_query_away_from_official_cap(self):
        orchestrator = Orchestrator(experts={}, search_fn=lambda *_args, **_kwargs: [])
        ctx = ConversationContext(
            post_id=11660237,
            post_data={
                "title": "테라포밍 볼만함?",
                "content_blocks": [{"type": "text", "text": "주인공 멍창하다는 말 많던데"}],
            },
            comments=["ㅇㅇ 야스 개꼴림 쥬지터짐"],
        )
        gatekeeper = {
            "post_type": "recommendation",
            "context_clues": {"is_asking_recommendation": True},
            "detected_entities": {"possible_titles": ["테라포밍"]},
        }
        ctx.set_expert_output(ExpertType.GATEKEEPER, gatekeeper)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "request_recommendation",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "title_novel_terms": ["테라포밍"],
                }
            },
        )
        requests = [
            {
                "purpose": "title_anchor_official_probe",
                "priority": 0,
                "query": 'site:novelpia.com/novel "테라포밍"',
            },
            {"purpose": "title_anchor_official_probe", "priority": 3, "query": "테라포밍 노벨피아"},
        ]

        normalized = orchestrator._normalize_title_led_platform_probe_purposes(
            ctx,
            requests,
            gatekeeper_result=gatekeeper,
            phase="test",
        )

        self.assertEqual(normalized[0]["purpose"], "title_anchor_official_probe")
        self.assertEqual(normalized[0]["priority"], 0)
        self.assertEqual(normalized[1]["purpose"], "platform_title_search")
        self.assertEqual(normalized[1]["priority"], -1)
        self.assertTrue(normalized[1]["_title_led_official_detail_probe"])

    def test_title_led_current_work_gate_exempts_generic_genre_bridge_guard(self):
        title = "테라포밍"
        url = "https://novelpia.com/novel/61947"
        identity = {
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "primary_subject_type": "work_discussion",
            "anchor_type": "genre",
            "anchor_strength": "low",
            "context_sources": ["title", "body", "comments", "search", "image"],
            "novel_identity": {
                "official_title": title,
                "heretic_url": url,
                "confidence": "High",
            },
            "primary_work": {
                "official_title": title,
                "heretic_url": url,
                "alias_or_mention": title,
                "source_tier": "official_detail",
                "page_type": "novel_page",
                "reference_role": "primary",
            },
            "consistency_flags": [
                "title_led_evaluation_official_candidate_rescued",
                "title_led_consumption_bridge",
            ],
            "search_evidence_catalog": [
                {
                    "title": title,
                    "url": url,
                    "source_tier": "novel_platform",
                    "purpose": "adaptive_abbreviation",
                }
            ],
            "promotion_decision": {
                "status": "publish",
                "publish_allowed": True,
                "official_title": title,
                "official_url": url,
                "reason_codes": [
                    "official_title_exists",
                    "row_discusses_work_as_work",
                    "scope_current_work",
                    "title_led_consumption_bridge",
                    "official_detail_url",
                ],
                "scope": {
                    "scope_kind": "current_work",
                    "confidence": "high",
                    "direct_bridge_sources": [
                        "title_led_consumption_bridge",
                        "alias_surface",
                        "official_detail_url",
                    ],
                },
            },
            "promotion_gate_state": {
                "candidate_title": title,
                "candidate_url": url,
                "official_title_exists": True,
                "row_discusses_work_as_work": True,
                "scope": {
                    "scope_kind": "current_work",
                    "confidence": "high",
                    "direct_bridge_sources": [
                        "title_led_consumption_bridge",
                        "alias_surface",
                        "official_detail_url",
                    ],
                },
            },
        }

        self.assertEqual(
            apply_weak_public_title_bridge_guard(identity, "테라포밍 볼만함?"),
            [],
        )
        self.assertTrue(identity["title_resolution_allowed"])
        self.assertEqual(identity["novel_identity"]["official_title"], title)

    def test_title_led_generic_genre_bridge_requires_official_detail(self):
        title = "테라포밍"
        identity = {
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "general",
            "primary_subject_type": "work_discussion",
            "anchor_type": "genre",
            "anchor_strength": "low",
            "context_sources": ["title", "body", "search"],
            "novel_identity": {
                "official_title": title,
                "confidence": "High",
            },
            "primary_work": {
                "official_title": title,
                "alias_or_mention": title,
                "source_tier": "web",
                "reference_role": "primary",
            },
            "consistency_flags": [
                "title_led_evaluation_official_candidate_rescued",
                "title_led_consumption_bridge",
            ],
            "promotion_decision": {
                "status": "publish",
                "publish_allowed": True,
                "official_title": title,
                "reason_codes": [
                    "official_title_exists",
                    "row_discusses_work_as_work",
                    "scope_current_work",
                    "title_led_consumption_bridge",
                ],
                "scope": {
                    "scope_kind": "current_work",
                    "confidence": "high",
                    "direct_bridge_sources": ["title_led_consumption_bridge"],
                },
            },
        }

        self.assertEqual(
            apply_weak_public_title_bridge_guard(identity, "테라포밍 볼만함?"),
            ["generic_genre_surface_public_title_bridge"],
        )
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertIsNone(identity["novel_identity"]["official_title"])

    def test_known_abbreviation_exact_title_consumption_exempts_weak_source_guard(self):
        title = "게임 마인드의 중세 현대인"
        identity = {
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "primary_subject_type": "work_discussion",
            "anchor_type": "title_exact",
            "anchor_strength": "high",
            "context_sources": ["title", "body", "search"],
            "novel_identity": {
                "official_title": title,
                "heretic_url": "https://ssn.so/series/204335/",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": title,
                "heretic_url": "https://ssn.so/series/204335/",
                "alias_or_mention": "중세 현대인",
                "source_tier": "llm_only",
                "page_type": "novel_page",
                "reference_role": "primary",
            },
            "promotion_decision": {
                "status": "candidate_only",
                "publish_allowed": False,
                "official_title": None,
                "reason_codes": [
                    "row_discusses_work_as_work",
                    "context_only",
                    "scope_current_work",
                    "work_consumption_marker",
                    "alias_bridge",
                    "serialized_public_identity_scrubbed",
                ],
                "scope": {
                    "scope_kind": "current_work",
                    "confidence": "high",
                    "direct_bridge_sources": ["row_discusses_work_as_work"],
                },
            },
            "promotion_gate_state": {
                "candidate_title": title,
                "candidate_url": "",
                "source": "known_abbreviation_title_guard:decoder_best_match",
                "official_title_exists": False,
                "row_discusses_work_as_work": True,
                "scope": {
                    "scope_kind": "current_work",
                    "confidence": "high",
                    "direct_bridge_sources": ["row_discusses_work_as_work"],
                },
            },
        }

        self.assertEqual(
            apply_weak_public_title_bridge_guard(identity, "게임 마인드의 중세 현대인 좋았다..."),
            [],
        )
        self.assertTrue(identity["title_resolution_allowed"])
        self.assertEqual(identity["novel_identity"]["official_title"], title)
        self.assertIn(
            "known_abbreviation_exact_title_public_title_bridge",
            identity["consistency_flags"],
        )

    def test_known_abbreviation_exact_title_requires_work_consumption_marker(self):
        title = "게임 마인드의 중세 현대인"
        identity = {
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "primary_subject_type": "work_discussion",
            "anchor_type": "title_exact",
            "anchor_strength": "high",
            "context_sources": ["title", "body", "search"],
            "novel_identity": {
                "official_title": title,
                "heretic_url": "https://ssn.so/series/204335/",
                "confidence": "High",
            },
            "primary_work": {
                "official_title": title,
                "heretic_url": "https://ssn.so/series/204335/",
                "alias_or_mention": "중세 현대인",
                "source_tier": "llm_only",
                "page_type": "novel_page",
                "reference_role": "primary",
            },
            "promotion_decision": {
                "status": "candidate_only",
                "publish_allowed": False,
                "official_title": None,
                "reason_codes": [
                    "row_discusses_work_as_work",
                    "scope_current_work",
                    "alias_bridge",
                    "serialized_public_identity_scrubbed",
                ],
                "scope": {
                    "scope_kind": "current_work",
                    "confidence": "high",
                    "direct_bridge_sources": ["row_discusses_work_as_work"],
                },
            },
            "promotion_gate_state": {
                "candidate_title": title,
                "candidate_url": "",
                "source": "known_abbreviation_title_guard:decoder_best_match",
                "official_title_exists": False,
                "row_discusses_work_as_work": True,
                "scope": {
                    "scope_kind": "current_work",
                    "confidence": "high",
                    "direct_bridge_sources": ["row_discusses_work_as_work"],
                },
            },
        }

        self.assertEqual(
            apply_weak_public_title_bridge_guard(identity, "게임 마인드의 중세 현대인이라는 말이 웃김"),
            ["weak_source_exact_title_without_official_support_public_title_bridge"],
        )
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertIsNone(identity["novel_identity"]["official_title"])

    def test_title_led_evaluation_question_picks_official_detail_candidate(self):
        pipeline = build_pipeline()
        title = "테라포밍"
        post = PostInput(
            post_id=11660237,
            title="테라포밍 볼만함?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="주인공 멍창하다는 말 많던데")],
            comments=["ㅇㅇ 야스 개꼴림 쥬지터짐"],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "short_reaction",
                "detected_entities": {
                    "possible_titles": ["테라포밍"],
                    "key_terms": ["볼만함"],
                },
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "ask_question",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "title_novel_terms": ["테라포밍"],
                }
            },
        )

        candidate = pipeline._pick_title_led_evaluation_official_candidate(
            ctx,
            title_candidates=[
                DetectedTitle(
                    official_title=title,
                    heretic_url="https://novelpia.com/novel/61947",
                    confidence="High",
                    alias_or_mention="테라포밍",
                    source_tier="official_detail",
                    page_type="novel_page",
                    reference_role="primary",
                )
            ],
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.official_title, title)
        self.assertEqual(candidate.heretic_url, "https://novelpia.com/novel/61947")

    def test_title_led_evaluation_prefers_structured_body_primary_over_headline_context(self):
        pipeline = build_pipeline()
        headline_title = "아카데미 생존 갤러리"
        headline_url = "https://novelpia.com/novel/380218"
        body_title = "가챠 중독자의 퓨전펑크 생활"
        body_url = "https://novelpia.com/novel/387014"
        post = PostInput(
            post_id=11698880,
            title="아생갤 개 존나게 재밌군 ㅇㅇ",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="가챠펑크 세드릭도 그렇고"),
                ContentBlock(type="text", text="시원시원한 상남자라서 너무 좋구나"),
            ],
            comments=[],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=[],
        )
        ctx.verified_character_work_links = [
            {
                "title": body_title,
                "url": body_url,
                "character": "세드릭",
                "alias": "가챠펑크",
                "matched_alias": "가챠펑크",
            }
        ]
        ctx.search_results = [
            {"title": headline_title, "url": headline_url, "content": "작품 상세"},
            {"title": body_title, "url": body_url, "content": "가챠펑크 세드릭 등장"},
        ]
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "work_discussion",
                "detected_entities": {"possible_titles": ["아생갤", "가챠펑크"]},
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "discuss_work",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "title_novel_terms": ["아생갤", "가챠펑크"],
                }
            },
        )
        candidates = [
            DetectedTitle(
                official_title=headline_title,
                heretic_url=headline_url,
                confidence="High",
                alias_or_mention="아생갤",
                source_tier="official_detail",
                page_type="novel_page",
                reference_role="mentioned",
            ),
            DetectedTitle(
                official_title=body_title,
                heretic_url=body_url,
                confidence="High",
                alias_or_mention="가챠펑크",
                source_tier="official_detail",
                page_type="novel_page",
                reference_role="primary",
            ),
        ]
        final_decision = {
            "official_title": body_title,
            "primary_work": {"official_title": body_title},
            "discussion_type": "general",
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
        }
        verification_result = {
            "novel_identity": {
                "official_novel_title": body_title,
                "heretic_url": body_url,
            }
        }

        candidate = pipeline._pick_title_led_evaluation_official_candidate(
            ctx,
            title_candidates=candidates,
            final_decision=final_decision,
            verification_result=verification_result,
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.official_title, body_title)
        self.assertEqual(candidate.heretic_url, body_url)
        self.assertTrue(ctx._title_led_body_primary_candidate_selected)
        self.assertEqual(ctx._title_led_headline_context_candidate_title, headline_title)

        validated = pipeline._apply_output_consistency_validator(
            ctx=ctx,
            is_relevant=False,
            discussion_type="undecodable_reference",
            official_title=None,
            confidence="Low",
            reason="작품 후보를 확정하지 못했습니다.",
            notes="작품 후보를 확정하지 못했습니다.",
            title_candidates=candidates,
            primary_work=None,
            mentioned_works=[],
            comparison_target=None,
            recommendation_candidates=[],
            metadata={},
            verification_result=verification_result,
            final_decision=final_decision,
        )

        self.assertEqual(validated["official_title"], body_title)
        self.assertEqual(validated["heretic_url"], body_url)
        self.assertEqual(validated["primary_work"].official_title, body_title)
        self.assertIn(
            "title_led_evaluation_official_candidate_rescued",
            validated["consistency_flags"],
        )

    def test_title_led_evaluation_does_not_select_weak_body_character_link(self):
        pipeline = build_pipeline()
        headline_title = "아카데미 생존 갤러리"
        headline_url = "https://novelpia.com/novel/380218"
        body_title = "가챠 중독자의 퓨전펑크 생활"
        body_url = "https://novelpia.com/novel/387014"
        post = PostInput(
            post_id=21698880,
            title="아생갤 개 존나게 재밌군 ㅇㅇ",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="가챠펑크 세드릭도 그렇고")],
            comments=[],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=[],
        )
        ctx.verified_character_work_links = [
            {
                "title": body_title,
                "url": body_url,
                "character": "세드릭",
                "alias": "가챠펑크",
                "_weak_match": True,
            }
        ]
        ctx.search_results = [
            {"title": headline_title, "url": headline_url, "content": "작품 상세"},
            {"title": body_title, "url": body_url, "content": "작품 상세"},
        ]
        ctx.set_expert_output(ExpertType.GATEKEEPER, {"post_type": "work_discussion"})
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {"discourse_analysis": {"intent": "discuss_work", "primary_domain": "novel_literature"}},
        )
        candidates = [
            DetectedTitle(
                official_title=headline_title,
                heretic_url=headline_url,
                confidence="High",
                alias_or_mention="아생갤",
                source_tier="official_detail",
                page_type="novel_page",
                reference_role="mentioned",
            ),
            DetectedTitle(
                official_title=body_title,
                heretic_url=body_url,
                confidence="High",
                alias_or_mention="가챠펑크",
                source_tier="official_detail",
                page_type="novel_page",
                reference_role="primary",
            ),
        ]

        candidate = pipeline._pick_title_led_evaluation_official_candidate(
            ctx,
            title_candidates=candidates,
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.official_title, headline_title)
        self.assertFalse(getattr(ctx, "_title_led_body_primary_candidate_selected", False))

    def test_title_led_evaluation_keeps_headline_when_it_has_body_surface(self):
        pipeline = build_pipeline()
        headline_title = "아카데미 생존 갤러리"
        headline_url = "https://novelpia.com/novel/380218"
        body_title = "가챠 중독자의 퓨전펑크 생활"
        body_url = "https://novelpia.com/novel/387014"
        post = PostInput(
            post_id=21698881,
            title="아생갤 개 존나게 재밌군 ㅇㅇ",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="아생갤 아레스도 좋고 가챠펑크 세드릭도 좋음")
            ],
            comments=[],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=[],
        )
        ctx.verified_character_work_links = [
            {
                "title": body_title,
                "url": body_url,
                "character": "세드릭",
                "alias": "가챠펑크",
            }
        ]
        ctx.search_results = [
            {"title": headline_title, "url": headline_url, "content": "작품 상세"},
            {"title": body_title, "url": body_url, "content": "작품 상세"},
        ]
        ctx.set_expert_output(ExpertType.GATEKEEPER, {"post_type": "work_discussion"})
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {"discourse_analysis": {"intent": "discuss_work", "primary_domain": "novel_literature"}},
        )
        candidates = [
            DetectedTitle(
                official_title=headline_title,
                heretic_url=headline_url,
                confidence="High",
                alias_or_mention="아생갤",
                source_tier="official_detail",
                page_type="novel_page",
                reference_role="primary",
            ),
            DetectedTitle(
                official_title=body_title,
                heretic_url=body_url,
                confidence="High",
                alias_or_mention="가챠펑크",
                source_tier="official_detail",
                page_type="novel_page",
                reference_role="mentioned",
            ),
        ]

        candidate = pipeline._pick_title_led_evaluation_official_candidate(
            ctx,
            title_candidates=candidates,
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.official_title, headline_title)

    def test_title_led_evaluation_does_not_promote_explicit_comparison_target(self):
        pipeline = build_pipeline()
        headline_title = "아카데미 생존 갤러리"
        headline_url = "https://novelpia.com/novel/380218"
        body_title = "가챠 중독자의 퓨전펑크 생활"
        body_url = "https://novelpia.com/novel/387014"
        post = PostInput(
            post_id=21698882,
            title="아생갤 개 존나게 재밌군 ㅇㅇ",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="가챠펑크 세드릭도 그렇고")],
            comments=[],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=[],
        )
        ctx.verified_character_work_links = [
            {
                "title": body_title,
                "url": body_url,
                "character": "세드릭",
                "alias": "가챠펑크",
            }
        ]
        ctx.search_results = [
            {"title": headline_title, "url": headline_url, "content": "작품 상세"},
            {"title": body_title, "url": body_url, "content": "작품 상세"},
        ]
        ctx.set_expert_output(ExpertType.GATEKEEPER, {"post_type": "work_discussion"})
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {"discourse_analysis": {"intent": "discuss_work", "primary_domain": "novel_literature"}},
        )
        headline_candidate = DetectedTitle(
            official_title=headline_title,
            heretic_url=headline_url,
            confidence="High",
            alias_or_mention="아생갤",
            source_tier="official_detail",
            page_type="novel_page",
            reference_role="primary",
        )
        body_candidate = DetectedTitle(
            official_title=body_title,
            heretic_url=body_url,
            confidence="High",
            alias_or_mention="가챠펑크",
            source_tier="official_detail",
            page_type="novel_page",
            reference_role="primary",
        )

        candidate = pipeline._pick_title_led_evaluation_official_candidate(
            ctx,
            title_candidates=[headline_candidate, body_candidate],
            primary_work=headline_candidate,
            final_decision={
                "primary_work": {"official_title": headline_title},
                "comparison_target": {"official_title": body_title},
            },
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.official_title, headline_title)
        self.assertFalse(getattr(ctx, "_title_led_body_primary_candidate_selected", False))

    def test_secondary_reference_official_alias_overrides_author_meta_block(self):
        pipeline = build_pipeline()
        title = "잘생기면 편해지는 인방 생활"
        post = PostInput(
            post_id=20010022,
            title="잘생인방 뭔일 터짐?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="민트초코주먹밥 작가 필력 얘기하다가 노피아 표지 때문에 터졌네")],
            comments=["노피아가 뽑아준 표지때문에", "표지가 별로래"],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        mark_no_work_seed(ctx)
        metadata = {"detected_author": "민트초코주먹밥"}
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "share_information",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "title_novel_terms": ["잘생인방"],
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        ctx.search_results = [
            {
                "title": title,
                "url": "https://novelpia.com/novel/384016",
                "content": f"플러스작품 - {title}.",
                "query": "잘생인방",
            }
        ]
        extended_identity = {
            "topicality": "adjacent_relevant",
            "subtype": "author_meta",
            "secondary_reference_works": [
                {
                    "official_title": title,
                    "heretic_url": "https://novelpia.com/novel/384016",
                    "confidence": "High",
                    "alias_or_mention": "잘생인방",
                    "source_tier": "official_detail",
                    "page_type": "novel_page",
                    "content_status": "active",
                }
            ],
        }

        self.assertTrue(
            pipeline._has_author_benchmark_or_advice_signal(
                ctx=ctx,
                metadata=metadata,
                verification_result={},
                official_title=None,
            )
        )
        candidate, hit = pipeline._secondary_reference_author_meta_alias_candidate(
            ctx,
            extended_identity,
            metadata=metadata,
            verification_result={},
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.official_title, title)
        self.assertEqual(candidate.heretic_url, "https://novelpia.com/novel/384016")
        self.assertEqual(hit["source"], "secondary_reference_official_detail")

    def test_secondary_reference_official_alias_does_not_override_deliberately_null_title(self):
        pipeline = build_pipeline()
        title = "잘생기면 편해지는 인방 생활"
        post = PostInput(
            post_id=11706832,
            title="잘생인방 뭔일 터짐?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="민트초코주먹밥 작가 필력 얘기하다가 노피아 표지 때문에 터졌네")],
            comments=["노피아가 뽑아준 표지때문에", "표지가 별로래"],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.ARBITER,
            {
                "final_decision": {
                    "is_relevant": False,
                    "discussion_type": "noise",
                    "_title_deliberately_null": True,
                }
            },
        )
        ctx.search_results = [
            {
                "title": title,
                "url": "https://novelpia.com/novel/384016",
                "content": f"플러스작품 - {title}.",
                "query": "잘생인방",
            }
        ]
        extended_identity = {
            "topicality": "adjacent_relevant",
            "subtype": "author_meta",
            "consistency_flags": [],
            "secondary_reference_works": [
                {
                    "official_title": title,
                    "heretic_url": "https://novelpia.com/novel/384016",
                    "confidence": "High",
                    "alias_or_mention": "잘생인방",
                    "source_tier": "official_detail",
                    "page_type": "novel_page",
                    "content_status": "active",
                }
            ],
        }

        candidate, hit = pipeline._secondary_reference_author_meta_alias_candidate(
            ctx,
            extended_identity,
            metadata={},
            verification_result={},
        )

        self.assertIsNone(candidate)
        self.assertIsNone(hit)
        flags = set(extended_identity.get("consistency_flags") or [])
        self.assertIn("secondary_reference_official_alias_blocked_after_title_deliberately_null", flags)
        self.assertIn("batch_memory_alias_rescue_blocked_after_title_deliberately_null", flags)

    def test_official_url_recall_blocks_title_body_only_after_deliberate_no_work_null(self):
        pipeline = build_pipeline()
        title = "무능한게 아니라 전설이였다고?"
        url = "https://novelpia.com/novel/371917"
        post = PostInput(
            post_id=11658621,
            title="아니 변명이 아니라 진짜였다고",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="KANA BU 2023.2")],
            comments=["진짜 실제 이름 못쓰는거 싫어서 이번 기회에 편결 도전하는거임??"],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        mark_no_work_seed(ctx)
        ctx.search_results = [
            {
                "title": f"웹소설로 꿈꾸는 세상! - {title} - 노벨피아",
                "url": url,
                "content": f"플러스 작품 - {title}.",
                "query": "아니 진짜였다고",
            }
        ]
        setattr(ctx, "_title_body_official_detail_anchor_title", title)
        setattr(ctx, "_title_body_official_detail_anchor_url", url)
        setattr(ctx, "_title_body_official_detail_anchor_surface", "아니 진짜였다고")

        verification_result = {
            "is_relevant": False,
            "is_novel_discussion": False,
            "counter_arguments": [{"severity": "major", "reason": "post is not a specific work discussion"}],
            "relation_judgment": {
                "relation_type": "thematic_overlap_only",
                "discussion_target": "community_banter",
                "promotion_decision": "reject",
            },
        }
        final_decision = {
            "is_relevant": False,
            "discussion_type": "general",
            "_title_deliberately_null": True,
        }
        extended_identity = {"consistency_flags": []}

        with patch(
            "llm_batch.agentic_pipeline.official_url_recoverable",
            return_value={
                "official_title": title,
                "heretic_url": url,
                "source_tier": "official_detail",
                "matched_clue": "title_body_search_result:아니 진짜였다고",
                "confidence": "High",
            },
        ):
            updated, candidates, primary, promotion = pipeline._apply_official_url_recall_promotion(
                ctx=ctx,
                extended_identity=extended_identity,
                title_candidates=[],
                primary_work=None,
                verification_result=verification_result,
                final_decision=final_decision,
            )

        self.assertIsNone(promotion)
        self.assertEqual(candidates, [])
        self.assertIsNone(primary)
        self.assertNotIn("official_title", updated)
        flags = set(updated.get("consistency_flags") or [])
        self.assertIn("official_url_recall_blocked_no_work_title_body_only", flags)
        self.assertIn("official_url_recall_blocked_relation_non_work_context", flags)

    def test_title_body_work_review_anchor_allows_deliberate_no_work_recall(self):
        pipeline = build_pipeline()
        title = "21세기 무림세가"
        url = "https://series.naver.com/novel/detail.series?productNo=11607472"
        post = PostInput(
            post_id=11666713,
            title="21세기 무림 이거 재미네 ㅋㅋㅋ",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="무틀딱 각혈하게 만드는 작품인 줄 알았는데"),
                ContentBlock(type="text", text="진지할 땐 진지하고 무협스러움이 가득한 작품이네 ㅋㅋ"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "review",
                "detected_entities": {"possible_titles": ["21세기 무림"]},
                "context_clues": {
                    "title_as_body_continuation": True,
                    "title_body_joined_text": (
                        "21세기 무림 이거 재미네 ㅋㅋㅋ "
                        "무틀딱 각혈하게 만드는 작품인 줄 알았는데 "
                        "진지할 땐 진지하고 무협스러움이 가득한 작품이네 ㅋㅋ"
                    ),
                },
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "primary_domain": "novel_literature",
                    "intent": "express_opinion",
                    "title_novel_terms": ["21세기 무림"],
                }
            },
        )
        ctx.search_results = [
            {
                "title": f"{title} - 네이버 시리즈",
                "url": url,
                "content": f"웹소설 {title} 작품 상세 페이지.",
                "source_tier": "official_detail",
            }
        ]
        setattr(ctx, "_title_body_official_detail_anchor_title", title)
        setattr(ctx, "_title_body_official_detail_anchor_url", url)
        setattr(ctx, "_title_body_official_detail_anchor_surface", "21세기 무림")

        verification_result = {
            "is_relevant": False,
            "is_novel_discussion": False,
            "relation_judgment": {
                "relation_type": "thematic_overlap_only",
                "discussion_target": "genre_general",
                "promotion_decision": "hold",
            },
        }
        final_decision = {
            "is_relevant": False,
            "discussion_type": "noise",
            "_title_deliberately_null": True,
        }
        extended_identity = {
            "is_relevant": False,
            "work_resolution": "none",
            "title_resolution_state": "unresolved_matchable",
            "discussion_type": "noise",
            "consistency_flags": [],
        }

        with patch(
            "llm_batch.agentic_pipeline.official_url_recoverable",
            return_value={
                "official_title": title,
                "heretic_url": url,
                "source_tier": "official_detail",
                "matched_clue": "title_body_search_result:21세기 무림",
                "confidence": "High",
            },
        ):
            updated, candidates, primary, promotion = pipeline._apply_official_url_recall_promotion(
                ctx=ctx,
                extended_identity=extended_identity,
                title_candidates=[],
                primary_work=None,
                verification_result=verification_result,
                final_decision=final_decision,
            )

        self.assertIsNotNone(promotion)
        self.assertEqual(updated["official_title"], title)
        self.assertEqual(updated["heretic_url"], url)
        self.assertEqual(updated["work_resolution"], "resolved")
        self.assertEqual(primary.official_title, title)
        self.assertEqual(candidates[0].official_title, title)
        flags = set(updated.get("consistency_flags") or [])
        self.assertIn("title_body_official_detail_anchor", flags)
        self.assertIn("title_body_work_review_official_detail_anchor", flags)
        self.assertNotIn("official_url_recall_blocked_no_work_title_body_only", flags)

    def test_official_url_recall_blocks_cross_media_title_body_only_hold(self):
        pipeline = build_pipeline()
        title = "[림월드]변방계에서 회귀자로 살아남기"
        url = "https://novelpia.com/novel/382324"
        post = PostInput(
            post_id=11698897,
            title="랫따싶 림월드 요소 생각나게 하는거 좋네에",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", url="https://example.test/rimworld.png"),
                ContentBlock(type="text", text="게임적 요소 있는거 아주 굿"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)
        setattr(ctx, "_title_body_official_detail_anchor_title", title)
        setattr(ctx, "_title_body_official_detail_anchor_url", url)
        setattr(ctx, "_title_body_official_detail_anchor_surface", "림월드 랫따싶")

        extended_identity = {
            "is_relevant": False,
            "work_resolution": "none",
            "title_resolution_state": "adjacent",
            "discussion_type": "trope_discussion",
            "primary_subject_type": "cross_media",
            "primary_subject_text": "메인 화제는 웹소설이 아닌 타 매체/게임 쪽 담론입니다.",
            "consistency_flags": ["expert_conflict", "budget_quarantine_candidate", "title_hold"],
        }

        with patch(
            "llm_batch.agentic_pipeline.official_url_recoverable",
            return_value={
                "official_title": title,
                "heretic_url": url,
                "source_tier": "official_detail",
                "matched_clue": "title_body_search_result:림월드 랫따싶",
                "confidence": "High",
            },
        ):
            updated, candidates, primary, promotion = pipeline._apply_official_url_recall_promotion(
                ctx=ctx,
                extended_identity=extended_identity,
                title_candidates=[],
                primary_work=None,
                verification_result={
                    "is_relevant": False,
                    "novel_identity": {},
                    "relation_judgment": {
                        "relation_type": "thematic_overlap_only",
                        "discussion_target": "genre_general",
                        "promotion_decision": "hold",
                    },
                },
                final_decision={
                    "discussion_type": "noise",
                    "primary_subject_type": "cross_media",
                    "final_reasoning": "림월드 게임 요소 잡담",
                },
            )

        self.assertIsNone(promotion)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].official_title, title)
        self.assertEqual(candidates[0].heretic_url, url)
        self.assertEqual(candidates[0].reference_role, "candidate")
        self.assertIn("cross_media_title_body_hold_without_promotion", candidates[0].negative_evidence or [])
        self.assertIsNone(primary)
        self.assertNotIn("official_title", updated)
        self.assertEqual(updated["blocked_official_title"], title)
        self.assertEqual(updated["blocked_official_title_url"], url)
        flags = set(updated.get("consistency_flags") or [])
        self.assertIn("official_url_recall_blocked_cross_media_title_body_hold", flags)
        self.assertIn("official_url_recall_blocked_no_work_title_body_only", flags)
        self.assertIn("cross_media_official_detail_candidate_preserved", flags)

    def test_title_body_work_review_anchor_blocks_inserted_wrong_title(self):
        pipeline = build_pipeline()
        wrong_title = "21세기 헌터가된 무림인"
        url = "https://novelpia.com/novel/309879"
        post = PostInput(
            post_id=11666713,
            title="21세기 무림 이거 재미네 ㅋㅋㅋ",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="무틀딱 각혈하게 만드는 작품인 줄 알았는데"),
                ContentBlock(type="text", text="진지할 땐 진지하고 무협스러움이 가득한 작품이네 ㅋㅋ"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "review",
                "detected_entities": {"possible_titles": ["21세기 무림"]},
                "context_clues": {
                    "title_as_body_continuation": True,
                    "title_body_joined_text": (
                        "21세기 무림 이거 재미네 ㅋㅋㅋ "
                        "무틀딱 각혈하게 만드는 작품인 줄 알았는데 "
                        "진지할 땐 진지하고 무협스러움이 가득한 작품이네 ㅋㅋ"
                    ),
                },
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "primary_domain": "novel_literature",
                    "intent": "express_opinion",
                    "title_novel_terms": ["21세기 무림"],
                }
            },
        )
        ctx.search_results = [
            {
                "title": f"웹소설로 꿈꾸는 세상! - {wrong_title} - 노벨피아",
                "url": url,
                "content": f"웹소설 {wrong_title} 작품 상세 페이지.",
                "source_tier": "official_detail",
            }
        ]
        setattr(ctx, "_title_body_official_detail_anchor_title", wrong_title)
        setattr(ctx, "_title_body_official_detail_anchor_url", url)
        setattr(ctx, "_title_body_official_detail_anchor_surface", "21세기 무림")

        with patch(
            "llm_batch.agentic_pipeline.official_url_recoverable",
            return_value={
                "official_title": wrong_title,
                "heretic_url": url,
                "source_tier": "official_detail",
                "matched_clue": "title_body_search_result:21세기 무림",
                "confidence": "High",
            },
        ):
            updated, candidates, primary, promotion = pipeline._apply_official_url_recall_promotion(
                ctx=ctx,
                extended_identity={
                    "is_relevant": False,
                    "work_resolution": "none",
                    "title_resolution_state": "unresolved_matchable",
                    "discussion_type": "noise",
                    "consistency_flags": [],
                },
                title_candidates=[],
                primary_work=None,
                verification_result={
                    "is_relevant": False,
                    "is_novel_discussion": False,
                    "relation_judgment": {
                        "relation_type": "thematic_overlap_only",
                        "discussion_target": "genre_general",
                        "promotion_decision": "hold",
                    },
                },
                final_decision={
                    "is_relevant": False,
                    "discussion_type": "noise",
                    "_title_deliberately_null": True,
                },
            )

        self.assertIsNone(promotion)
        self.assertEqual(candidates, [])
        self.assertIsNone(primary)
        self.assertNotIn("official_title", updated)
        flags = set(updated.get("consistency_flags") or [])
        self.assertIn("official_url_recall_blocked_title_body_work_review_surface_mismatch", flags)
        self.assertNotIn("title_body_work_review_official_detail_anchor", flags)

    def test_secondary_reference_official_alias_blocks_platform_alias_after_multi_work_clear(self):
        pipeline = build_pipeline()
        title = "브로드웨이의 신"
        url = "https://series.naver.com/novel/detail.series?productNo=10647472"
        post = PostInput(
            post_id=11718105,
            title="시리즈 기다리는 중인데 이새끼들 언제옴..",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="특히 뇌조꺼는 표지도 없어")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        extended_identity = {
            "topicality": "adjacent_relevant",
            "subtype": "multi_work",
            "consistency_flags": ["multi_work_title_cleared"],
            "secondary_reference_works": [
                {
                    "official_title": title,
                    "heretic_url": url,
                    "confidence": "High",
                    "alias_or_mention": "시리즈",
                    "source_tier": "official_detail",
                    "page_type": "novel_page",
                    "content_status": "active",
                }
            ],
        }

        candidate, hit = pipeline._secondary_reference_author_meta_alias_candidate(
            ctx,
            extended_identity,
            metadata={},
            verification_result={},
        )

        self.assertIsNone(candidate)
        self.assertIsNone(hit)
        flags = set(extended_identity.get("consistency_flags") or [])
        self.assertIn("secondary_reference_official_alias_blocked_after_multi_work_title_cleared", flags)

    def test_search_official_alias_blocks_platform_alias_surface(self):
        pipeline = build_pipeline()
        title = "브로드웨이의 신"
        url = "https://series.naver.com/novel/detail.series?productNo=10647472"
        post = PostInput(
            post_id=11718105,
            title="시리즈 기다리는 중인데 이새끼들 언제옴..",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="특히 뇌조꺼는 표지도 없어")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        ctx.set_expert_output(
            ExpertType.VERIFIER,
            {
                "verification_result": {
                    "grounding_check": {"anchor_text": "시리즈", "matched_alias": "시리즈"},
                    "relation_judgment": {"observed_aliases": ["시리즈"]},
                }
            },
        )
        ctx.search_results = [
            {
                "title": title,
                "url": url,
                "content": f"{title}. 네이버 시리즈 독점 웹소설.",
                "query": "시리즈",
            }
        ]

        candidate, hit = pipeline._search_results_official_alias_candidate(
            ctx,
            extended_identity={"consistency_flags": []},
        )

        self.assertIsNone(candidate)
        self.assertIsNone(hit)
        self.assertTrue(pipeline._is_platform_alias_surface("시리즈"))
        self.assertFalse(
            pipeline._has_post_alias_official_detail_bridge_anchor(
                ctx,
                title,
                alias_text="시리즈",
            )
        )

    def test_search_official_alias_fallback_overrides_author_meta_without_secondary_refs(self):
        pipeline = build_pipeline()
        title = "잘생기면 편해지는 인방 생활"
        post = PostInput(
            post_id=20010023,
            title="잘생인방 뭔일 터짐?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="노피아 표지 때문에 터졌다던데")],
            comments=["노피아가 뽑아준 표지때문에"],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "make_joke",
                    "target_kind": "none",
                    "primary_domain": "novel_literature",
                    "title_novel_terms": ["잘생인방"],
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        ctx.set_expert_output(
            ExpertType.VERIFIER,
            {
                "verification_result": {
                    "grounding_check": {
                        "anchor_found": "title_mention",
                        "anchor_text": "잘생인방",
                        "title_abbrev_mentioned": True,
                        "matched_alias": "잘생인방",
                    },
                    "relation_judgment": {
                        "relation_type": "explicit_alias",
                        "discussion_target": "specific_work",
                        "promotion_decision": "hold",
                        "observed_aliases": ["잘생인방"],
                    },
                }
            },
        )
        ctx.search_results = [
            {
                "title": title,
                "url": "https://novelpia.com/novel/384016",
                "content": f"플러스작품 - {title}.",
                "query": "잘생인방",
                "source_tier": "novel_platform",
            }
        ]

        candidate, hit = pipeline._secondary_reference_author_meta_alias_candidate(
            ctx,
            {"topicality": "adjacent_relevant", "subtype": "author_meta"},
            metadata={"detected_author": "민트초코주먹밥"},
            verification_result={},
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.official_title, title)
        self.assertEqual(candidate.heretic_url, "https://novelpia.com/novel/384016")
        self.assertEqual(hit["source"], "search_official_detail_alias")
        self.assertEqual(getattr(ctx, "_post_alias_official_detail_bridge_alias", ""), "잘생인방")

    def test_issue_title_lead_alias_fallback_does_not_need_verifier_alias(self):
        pipeline = build_pipeline()
        title = "잘생기면 편해지는 인방 생활"
        post = PostInput(
            post_id=20010024,
            title="잘생인방 뭔일 터짐?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="알려주면 노나메 임신 질싸짤 공유하")],
            comments=["노피아가 뽑아준 표지때문에", "표지가 별로래"],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "ask_question",
                    "target_kind": "author",
                    "primary_domain": "novel_literature",
                    "title_novel_terms": [],
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        ctx.search_results = [
            {
                "title": f"웹소설로 꿈꾸는 세상! - {title} - 노벨피아",
                "url": "https://novelpia.com/novel/384016",
                "content": f"플러스작품 - {title}.",
                "query": "잘생인방 노벨피아",
                "source_tier": "novel_platform",
            }
        ]

        self.assertIn("잘생인방", pipeline._extract_post_title_lead_alias_terms(ctx))
        candidate, hit = pipeline._secondary_reference_author_meta_alias_candidate(
            ctx,
            {"topicality": "adjacent_relevant", "subtype": "author_meta"},
            metadata={"detected_author": "민트초코주먹밥"},
            verification_result={},
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.official_title, title)
        self.assertEqual(candidate.heretic_url, "https://novelpia.com/novel/384016")
        self.assertEqual(hit["source"], "search_official_detail_alias")
        self.assertEqual(getattr(ctx, "_post_alias_official_detail_bridge_alias", ""), "잘생인방")

    def test_title_surface_rescue_preserves_near_title_url_without_no_work_publish(self):
        pipeline = build_pipeline()
        title = "두바이의 쫀득한 여초딩 재벌 9세"
        post = PostInput(
            post_id=20010023,
            title="두바이만 붙이면 잘되네",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="두바이 쫀득 뷰지로 ts 환생했더니 한국에서 모셔가려고 난리"),
                ContentBlock(type="text", text="#TS #배우 #노맨스 #인방"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "context_clues": {
                    "title_as_body_continuation": True,
                    "title_body_joined_text": (
                        "두바이만 붙이면 잘되네 두바이 쫀득 뷰지로 ts 환생했더니 "
                        "한국에서 모셔가려고 난리 #TS #배우 #노맨스 #인방"
                    ),
                }
            },
        )
        title_candidates = [
            DetectedTitle(official_title=title, confidence="High", source_tier="community"),
            DetectedTitle(
                official_title="두바의 쫀득한 여초딩 재벌 9세",
                heretic_url="https://novelpia.com/novel/419119",
                confidence="High",
                source_tier="official_detail",
            ),
        ]

        self.assertEqual(
            pipeline._near_title_official_detail_url_from_candidates(
                ctx,
                title,
                title_candidates=title_candidates,
            ),
            "https://novelpia.com/novel/419119",
        )
        self.assertFalse(
            pipeline._can_promote_title_after_semantic_no_work(
                ctx,
                title,
                source="title_surface_primary_candidate_rescued",
                title_candidates=title_candidates,
            )
        )

    def test_post_alias_detail_bridge_requires_issue_or_known_update_context(self):
        pipeline = build_pipeline()
        title = "조향사의 헌터상담기록"
        post = PostInput(
            post_id=20010018,
            title="헌터상담은 완결나기전엔 야스안함?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="세상에")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "discuss_work",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        ctx.search_results = [
            {
                "title": title,
                "url": "https://novelpia.com/novel/364983",
                "content": f"{title}. 돌아가려면 헌터를 상담해야 한다.",
                "query": "헌터상담 웹소설",
            }
        ]

        self.assertFalse(
            pipeline._has_post_alias_official_detail_bridge_anchor(
                ctx,
                title,
                alias_text="헌터상담",
            )
        )
        self.assertFalse(
            pipeline._can_promote_title_after_semantic_no_work(
                ctx,
                title,
                source="official_url_recall_gate",
                verification_result={"grounding_check": {"anchor_found": "title_mention"}},
            )
        )

    def test_known_abbreviation_update_question_recovers_url_but_does_not_publish_no_work(self):
        pipeline = build_pipeline()
        title = "괴담 호텔 탈출기"
        post = PostInput(
            post_id=20010019,
            title="오늘 담텔기 오냐?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="아님 12시 넘어서 내일 새벽에 오냐")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "ask_question",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )

        self.assertFalse(
            pipeline._can_promote_title_after_semantic_no_work(
                ctx,
                title,
                source="batch_memory_exact_alias_rescued",
                verification_result={"grounding_check": {"anchor_found": "title_abbrev_mention"}},
            )
        )

        with patch.object(
            pipeline,
            "_search_with_meta",
            return_value=(
                [
                    {
                        "title": f"웹소설로 꿈꾸는 세상! - {title} - 노벨피아",
                        "url": "https://novelpia.com/novel/102155",
                        "content": f"플러스작품 - {title}.",
                    }
                ],
                {},
            ),
        ):
            recovered_url = pipeline._recover_corrected_title_official_url(
                ctx,
                title=title,
                alias_text="담텔기",
                purpose="batch_memory_alias_official_url_recovery",
                allow_known_abbreviation_anchor=True,
            )

        self.assertEqual(recovered_url, "https://novelpia.com/novel/102155")

    def test_title_lead_alias_official_detail_resolves_issue_alias_but_holds_rejected_no_work(self):
        pipeline = build_pipeline()
        title = "잘생기면 편해지는 인방 생활"
        post = PostInput(
            post_id=20010014,
            title="잘생인방 뭔일 터짐?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="알려주면 노나메 임신 질싸짤 공유하")],
            comments=["노피아가 뽑아준 표지때문에", "표지가 별로래"],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=post.comments,
        )
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "share_information",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        ctx.search_results = [
            {
                "title": f"웹소설로 꿈꾸는 세상! - {title} - 노벨피아",
                "url": "https://novelpia.com/novel/384016",
                "content": f"플러스작품 - {title}. 잘생인방으로 불리는 작품.",
                "query": "잘생인방",
            },
            {
                "title": "공유하 - 커뮤니티 잡담",
                "url": "https://example.invalid/noise",
                "content": "본문 끝 token 잡음",
                "query": "공유하 웹소설",
            },
        ]
        verification_result = {
            "is_relevant": False,
            "is_novel_discussion": False,
            "novel_identity": {},
            "grounding_check": {"anchor_found": "title_mention"},
            "relation_judgment": {
                "relation_type": "explicit_alias",
                "discussion_target": "mixed_or_uncertain",
                "promotion_decision": "reject",
            },
        }

        candidate, hit = pipeline._resolve_batch_memory_alias_candidate(
            ctx,
            verification_result=verification_result,
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.official_title, title)
        self.assertEqual(candidate.alias_or_mention, "잘생인방")
        self.assertEqual(hit["source"], "title_lead_alias_official_detail_release")
        self.assertIsNone(
            pipeline._search_inferred_alias_nonwork_block_reason(
                ctx,
                title=title,
                alias="잘생인방",
                surface="잘생인방",
                verification_result=verification_result,
            )
        )
        self.assertFalse(
            pipeline._can_promote_title_after_semantic_no_work(
                ctx,
                title,
                source="batch_memory_exact_alias_rescued",
                verification_result=verification_result,
            )
        )

    def test_final_semantic_reread_guard_keeps_known_abbreviation_official_recall(self):
        pipeline = build_pipeline()
        title = "괴담 호텔 탈출기"
        post = PostInput(
            post_id=20010012,
            title="오늘 담텔기 오냐?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="아님 12시 넘어서 내일 새벽에 오냐")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "ask_question",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        ctx.search_results = [
            {
                "title": title,
                "url": "https://novelpia.com/novel/102155",
                "content": f"{title} 작품 페이지.",
            }
        ]

        self.assertTrue(
            pipeline._should_keep_final_semantic_resolution_after_official_recall_anchor(
                ctx=ctx,
                official_title=title,
                verification_result={"is_relevant": False},
                title_candidates=[
                    DetectedTitle(
                        official_title=title,
                        heretic_url="https://novelpia.com/novel/102155",
                        confidence="High",
                        source_tier="official_detail",
                        alias_or_mention="담텔기",
                    )
                ],
                consistency_flags=[
                    "official_url_recall_gate_recovered",
                    "confirmed_alias:담텔기",
                    "known_title_abbreviation_official_detail_anchor",
                ],
            )
        )

    def test_short_worklike_alias_probe_bypasses_semantic_seed_early_stop(self):
        orchestrator = Orchestrator(experts={})
        ctx = ConversationContext(
            post_id=20010013,
            post_data={
                "title": "잘생인방 뭔일 터짐?",
                "content_blocks": [{"type": "text", "text": "알려주면 노나메 임신 질싸짤 공유하"}],
            },
            comments=["노피아가 뽑아준 표지 얘기 계속 나오네"],
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "ask_question",
                    "primary_domain": "novel_literature",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                    "semantic_seed_review_context_terms": ["잘생인방"],
                    "search_suggestions": [{"query": "노벨피아 잘생인방"}],
                }
            },
        )
        gatekeeper = {"search_requests": [], "detected_entities": {"possible_titles": ["잘생인방"]}}
        self.assertTrue(orchestrator._has_short_worklike_alias_search_probe(ctx, gatekeeper))

        reaction_ctx = ConversationContext(
            post_id=11660259,
            post_data={
                "title": "기계공주 이제 슬슬 갤에서 말한대로 가는건가",
                "content_blocks": [{"type": "text", "text": "곧 대가리똑딱당하겠노"}],
            },
            comments=[],
        )
        reaction_ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "express_opinion",
                    "target_kind": "character",
                    "primary_domain": "novel_literature",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": [
                        "semantic_seed_review_non_title_terms_removed",
                        "semantic_seed_review_search_suggestions_removed",
                        "semantic_seed_review_specific_work_denied",
                    ],
                    "semantic_seed_review_context_terms": ["기계공주"],
                    "search_suggestions": [],
                }
            },
        )
        reaction_gatekeeper = {
            "search_requests": [],
            "detected_entities": {"possible_titles": ["기계공주 이제 슬슬 갤에서 말한대로 가는건가"]},
        }
        self.assertTrue(orchestrator._has_short_worklike_alias_search_probe(reaction_ctx, reaction_gatekeeper))

        kept = orchestrator._prune_title_search_requests_for_intent_permit(
            ctx,
            [
                {"purpose": "title_anchor_official_probe", "query": "잘생인방 웹소설 노벨피아"},
                {"purpose": "community_site_probe", "query": "site:gall.dcinside.com 잘생인방"},
                {"purpose": "alias_raw_probe", "query": "잘생인방"},
            ],
            gatekeeper_result=gatekeeper,
            phase="unit",
        )
        self.assertEqual(
            [item["query"] for item in kept],
            ["잘생인방 웹소설 노벨피아", "site:gall.dcinside.com 잘생인방", "잘생인방"],
        )

        negative = ConversationContext(
            post_id=20010014,
            post_data={"title": "랫따싶 모드밸런스면 보이드정도까진 나올만함", "content_blocks": []},
            comments=[],
        )
        negative.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "express_opinion",
                    "primary_domain": "gaming",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "search_suggestions": [{"query": "랫따싶 림월드"}],
                }
            },
        )
        self.assertFalse(orchestrator._has_short_worklike_alias_search_probe(negative, {}))

    def test_visual_title_lead_alias_probe_survives_gaming_semantic_demotion(self):
        orchestrator = Orchestrator(experts={})
        ctx = ConversationContext(
            post_id=11668288,
            post_data={
                "title": "가챠펑크 오늘 호텔 스트레스 많이 받을거야",
                "content_blocks": [
                    {"type": "image", "image_url": "https://example.test/a.png"},
                    {"type": "text", "text": "[이미지 OCR] 아침 모르겠다는 것이야...! 아무것도 모름 경축 대성공!"},
                    {"type": "text", "text": "근데 그런 스트레스도 필요하다"},
                ],
            },
            comments=[],
        )
        gatekeeper = {
            "post_type": "community_banter",
            "detected_entities": {"possible_titles": ["가챠펑크"]},
            "key_terms": ["가챠펑크", "호텔", "스트레스"],
            "context_clues": {"title_as_body_continuation": True},
            "search_requests": [
                {"query": "가챠펑크 웹소설", "purpose": "official_title_verify", "priority": 1},
            ],
        }
        ctx.set_expert_output(ExpertType.GATEKEEPER, gatekeeper)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "express_opinion",
                    "target_kind": "unknown",
                    "primary_domain": "gaming",
                    "domain_confidence": "high",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": [
                        "semantic_seed_review_non_title_terms_removed",
                        "semantic_seed_review_search_suggestions_removed",
                        "semantic_seed_review_specific_work_denied",
                    ],
                    "semantic_seed_review_context_terms": ["가챠펑크"],
                    "search_suggestions": [
                        {"query": "가챠펑크 호텔"},
                        {"query": "가챠펑크 아침 모르겠다는 것이야"},
                    ],
                }
            },
        )

        self.assertTrue(orchestrator._has_short_worklike_alias_search_probe(ctx, gatekeeper))
        limit, reason = orchestrator._should_limit_non_novel_expansion(ctx, gatekeeper)
        self.assertFalse(limit, reason)
        self.assertEqual(orchestrator._derive_auto_search_seed_terms(ctx, gatekeeper), ["가챠펑크"])
        kept = orchestrator._prune_title_search_requests_for_intent_permit(
            ctx,
            [
                {"purpose": "title_search_community", "query": "가챠펑크"},
                {"purpose": "official_title_verify", "query": "가챠펑크 노벨피아"},
                {"purpose": "term_definition", "query": "가챠 뜻"},
            ],
            gatekeeper_result=gatekeeper,
            phase="unit",
        )
        self.assertEqual(
            [item["query"] for item in kept],
            ["가챠펑크", "가챠펑크 노벨피아", "가챠 뜻"],
        )
        low_specific_kept = orchestrator._prune_low_specificity_seed_search_requests(
            ctx,
            [
                {"purpose": "platform_title_search", "query": "가챠펑크 웹소설 노벨피아"},
                {"purpose": "official_title_verify", "query": "가챠펑크 정식 제목"},
                {"purpose": "term_definition", "query": "가챠 뜻"},
            ],
            gatekeeper_result=gatekeeper,
        )
        self.assertIn(
            "가챠펑크 웹소설 노벨피아",
            [item["query"] for item in low_specific_kept],
        )

    def test_title_lead_alias_official_detail_release_preserves_candidate_under_semantic_no_work(self):
        pipeline = build_pipeline()
        title = "가챠 중독자의 퓨전펑크 생활"
        url = "https://novelpia.com/novel/387014"
        post = PostInput(
            post_id=11668288,
            title="가챠펑크 오늘 호텔 스트레스 많이 받을거야",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", image_url="https://example.test/a.png"),
                ContentBlock(type="text", text="[이미지 OCR] 아침 모르겠다는 것이야...! 아무것도 모름 대성공!"),
                ContentBlock(type="text", text="근데 그런 스트레스도 필요하다"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.llm_snippet_analysis = {
            "identified_title": title,
            "abbreviation_mappings": [{"abbrev": "가챠펑크", "full": title}],
        }
        ctx.search_results = [
            {
                "title": f"{title} - 노벨피아",
                "url": url,
                "content": "가챠펑크 웹소설 작품 페이지. 작가 섦게지는꽃. 노벨피아 연재.",
                "snippet": "가챠펑크 웹소설 작품 페이지. 작가 섦게지는꽃. 노벨피아 연재.",
                "query": "가챠펑크 노벨피아",
            },
            {
                "title": title,
                "url": "https://namu.wiki/w/가챠%20중독자의%20퓨전펑크%20생활",
                "content": "가챠펑크.jpg 장르 판타지, 라이트노벨, 하렘. 작가 섦게지는꽃. 연재처 노벨피아.",
                "snippet": "가챠펑크.jpg 장르 판타지, 라이트노벨, 하렘. 작가 섦게지는꽃. 연재처 노벨피아.",
                "query": "가챠펑크 뜻",
            },
            {
                "title": f"노피아 [가챠펑크], {title} 리뷰 - 판타지 갤러리",
                "url": "https://gall.dcinside.com/board/view/?id=fantasy_n&no=123",
                "content": "웹소설 리뷰. 가챠펑크는 가챠 중독자의 퓨전펑크 생활을 뜻한다.",
                "snippet": "웹소설 리뷰. 가챠펑크는 가챠 중독자의 퓨전펑크 생활을 뜻한다.",
                "query": "site:gall.dcinside.com 가챠펑크",
            },
        ]
        mark_no_work_seed(ctx)

        self.assertFalse(pipeline._has_title_lead_alias_search_work_support(ctx, title))
        self.assertTrue(
            pipeline._has_title_lead_alias_search_work_support(
                ctx,
                title,
                allow_semantic_no_work=True,
            )
        )
        self.assertTrue(pipeline._has_batch_alias_verified_no_work_release_context(ctx, title))

        candidate, hit = pipeline._resolve_batch_memory_alias_candidate(ctx, verification_result={})

        self.assertIsNotNone(candidate)
        self.assertIsNotNone(hit)
        self.assertEqual(candidate.official_title, title)
        self.assertEqual(candidate.heretic_url, url)
        self.assertEqual(candidate.alias_or_mention, "가챠펑크")
        self.assertTrue(candidate.locked)
        self.assertTrue(candidate.resolved_recall_anchor)
        self.assertEqual(hit["source"], "title_lead_alias_official_detail_release")
        self.assertEqual(
            apply_weak_public_title_bridge_guard(
                {
                    "title_resolution_allowed": True,
                    "title_resolution_state": "resolved",
                    "work_resolution": "resolved",
                    "anchor_type": "title_alias",
                    "anchor_strength": "medium",
                    "novel_identity": {"official_title": title, "heretic_url": url},
                    "primary_work": {
                        "official_title": title,
                        "heretic_url": url,
                        "alias_or_mention": "가챠펑크",
                        "source_tier": "official_detail",
                        "locked": True,
                    },
                    "consistency_flags": [
                        "batch_memory_exact_alias_rescued",
                        "title_lead_alias_official_detail_release",
                        "verified_alias_official_detail_anchor",
                        "explicit_alias_official_work_lock",
                        "confirmed_alias:가챠펑크",
                    ],
                },
                post.title,
            ),
            [],
        )
        self.assertFalse(
            pipeline._can_promote_title_after_semantic_no_work(
                ctx,
                title,
                source="batch_memory_exact_alias_rescued",
                verification_result={
                    "is_relevant": True,
                    "is_novel_discussion": True,
                    "novel_identity": {"official_title": title, "heretic_url": url},
                },
                title_candidates=[candidate],
            )
        )

    def test_consumption_title_lead_alias_release_preserves_candidate_under_semantic_no_work(self):
        pipeline = build_pipeline()
        title = "심해의 마법사"
        url = "https://m.munpia.com/novel/detail/483667"
        post = PostInput(
            post_id=11705250,
            title="심해법사 묵혀둔거 간만에 보니까 ㄹㅇ 맛있네",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="권 단위로 몰아봐야 맛있는 소설")],
            comments=["그거 실 쓰는애 죽이는거 까지 보고 좀 루즈해져서 묵혔는데 뒤에도 괜찮음?"],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "share_opinion",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        ctx.search_results = [
            {
                "title": f"{title} - 문피아 웹소설",
                "url": url,
                "content": "문피아 작품 페이지. 작가 상한김밥. 판타지 마법 전생 정통.",
                "snippet": "심해법사 웹소설 작품 페이지.",
                "query": "심해법사 문피아",
            },
            {
                "title": f"{title} - 나무위키",
                "url": "https://namu.wiki/w/%EC%8B%AC%ED%95%B4%EC%9D%98%20%EB%A7%88%EB%B2%95%EC%82%AC",
                "content": "문피아 웹소설. 작가는 상한김밥. 약칭 심해법사.",
                "snippet": "심해법사 약칭 설명.",
                "query": "심해법사",
            },
        ]

        self.assertIn("심해법사", pipeline._extract_post_title_lead_alias_terms(ctx))
        self.assertFalse(pipeline._has_title_lead_alias_search_work_support(ctx, title))
        self.assertTrue(
            pipeline._has_title_lead_alias_search_work_support(
                ctx,
                title,
                allow_semantic_no_work=True,
            )
        )
        self.assertTrue(pipeline._has_batch_alias_verified_no_work_release_context(ctx, title))
        self.assertFalse(
            pipeline._can_promote_title_after_semantic_no_work(
                ctx,
                title,
                source="batch_memory_exact_alias_rescued",
                verification_result={
                    "is_relevant": True,
                    "is_novel_discussion": True,
                    "novel_identity": {"official_title": title, "heretic_url": url},
                    "grounding_check": {
                        "anchor_found": "title_mention",
                        "anchor_text": "심해법사",
                        "matched_alias": "심해법사",
                        "matched_title": title,
                    },
                },
            )
        )

    def test_title_led_body_consumption_question_uses_search_alias_bridge(self):
        pipeline = build_pipeline()
        title = "빚을 져서라도 세상은 구해야 할 거 아니야"
        url = "https://series.naver.com/novel/detail.series?productNo=13598334"
        post = PostInput(
            post_id=11668307,
            title="빛세구 궁금한 점 있음",
            author="비듬빙수슝슝",
            content_blocks=[
                ContentBlock(
                    type="text",
                    text=(
                        "다시보는 중인데, 각 행성에서 재능이 제일 뛰어난 사람만 골라오는 거 아님? "
                        "전부 엘리트일 텐데 왜 튜토리얼에 폐급이 있지?"
                    ),
                )
            ],
            comments=[
                "그거 신경쓰면 대부분의 웹소 못 봄  - dc App",
                "이건 중요한 거임... 행성 1위들끼리 급을 나누는 것부터 흥미로운데 행성 1위가 폐급이면...",
                "@비듬빙수슝슝\n그 행성이 개씹 폐급이라고 봐야지 ㅇㅇ\n전독시에도 비슷한 내용 있음",
            ],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "ask_question",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        ctx.search_results = [
            {
                "title": f"{title} - 네이버 시리즈",
                "url": url,
                "content": "네이버 시리즈 웹소설. 작가 1_394. 판타지 연재 중.",
                "snippet": "네이버 시리즈 웹소설 공식 상세.",
                "query": "빛세구 네이버 시리즈",
            },
            {
                "title": "빛세구가 뭐 줄임말임? - 장르소설 마이너 갤러리",
                "url": "https://m.dcinside.com/board/genrenovel/11826680",
                "content": f"빛세구는 {title}를 말함. 웹소설 약칭 질의 답변.",
                "snippet": f"빛세구 답변: {title}",
                "query": "빛세구 줄임말",
            },
        ]

        self.assertTrue(pipeline._has_title_led_work_consumption_signal(ctx))
        self.assertIn("빛세구", pipeline._extract_post_title_lead_alias_terms(ctx))
        self.assertTrue(
            pipeline._has_title_lead_alias_search_work_support(
                ctx,
                title,
                allow_semantic_no_work=True,
            )
        )
        self.assertTrue(pipeline._has_batch_alias_verified_no_work_release_context(ctx, title))

        candidate, hit = pipeline._resolve_batch_memory_alias_candidate(ctx, verification_result={})

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.official_title, title)
        self.assertEqual(candidate.heretic_url, url)
        self.assertEqual(candidate.alias_or_mention, "빛세구")
        self.assertTrue(candidate.locked)
        self.assertTrue(candidate.resolved_recall_anchor)
        self.assertEqual(hit["source"], "title_lead_alias_official_detail_release")

    def test_visual_title_lead_alias_probe_rejects_game_context_query(self):
        orchestrator = Orchestrator(experts={})
        ctx = ConversationContext(
            post_id=20010015,
            post_data={
                "title": "랫따싶 모드밸런스면 보이드정도까진 나올만함",
                "content_blocks": [{"type": "image", "image_url": "https://example.test/game.png"}],
            },
            comments=[],
        )
        gatekeeper = {
            "detected_entities": {"possible_titles": ["랫따싶"]},
            "context_clues": {"title_as_body_continuation": True},
            "search_requests": [
                {"query": "랫따싶 림월드", "purpose": "title_search_community", "priority": 1}
            ],
        }
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "express_opinion",
                    "primary_domain": "gaming",
                    "domain_confidence": "high",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "semantic_seed_review_context_terms": ["랫따싶"],
                    "search_suggestions": [{"query": "랫따싶 림월드"}],
                }
            },
        )

        self.assertFalse(orchestrator._has_short_worklike_alias_search_probe(ctx, gatekeeper))

    def test_short_worklike_alias_probe_keeps_particle_alias_and_style_review_queries(self):
        orchestrator = Orchestrator(experts={})

        platform_ctx = ConversationContext(
            post_id=11706832,
            post_data={
                "title": "황제분충 ㄱㅊ함?",
                "content_blocks": [{"type": "text", "text": "문피안가"}],
            },
            comments=["노피아가 맞는듯"],
        )
        platform_ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "ask_question",
                    "primary_domain": "novel_literature",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                    "semantic_seed_review_context_terms": ["황제분충"],
                    "search_suggestions": [{"query": "황제분충 노벨피아"}],
                }
            },
        )
        platform_gatekeeper = {"detected_entities": {"possible_titles": ["황제분충"]}}
        platform_ctx.set_expert_output(ExpertType.GATEKEEPER, platform_gatekeeper)
        self.assertTrue(orchestrator._has_short_worklike_alias_search_probe(platform_ctx, platform_gatekeeper))
        platform_budget = orchestrator._derive_search_budget_profile(
            platform_ctx,
            [
                {"purpose": "alias_raw_probe", "query": "황제분충", "priority": 0},
                {"purpose": "platform_title_search", "query": "황제분충 노벨피아", "priority": 1},
                {"purpose": "community_site_probe", "query": "site:gall.dcinside.com 황제분충", "priority": 3},
                {
                    "purpose": "official_title_verify",
                    "query": "(site:novelpia.com OR site:munpia.com OR site:series.naver.com) 황제분충",
                    "priority": 1,
                },
            ],
        )
        self.assertEqual(platform_budget["profile"], "short_alias_bridge")
        self.assertGreaterEqual(platform_budget["max_q"], 6)
        self.assertFalse(platform_budget["stop_after_official_hit"])
        platform_kept = orchestrator._prune_title_search_requests_for_intent_permit(
            platform_ctx,
            [
                {"purpose": "author_verify", "query": "황제분충 작가"},
                {"purpose": "abbreviation_fullname_search", "query": "황제분충 정식 명칭"},
                {"purpose": "term_definition", "query": "힘숨 뜻"},
            ],
            gatekeeper_result=platform_gatekeeper,
            phase="unit",
        )
        platform_kept_queries = [item["query"] for item in platform_kept]
        self.assertIn("황제분충 작가", platform_kept_queries)
        self.assertIn("황제분충 정식 명칭", platform_kept_queries)

        style_ctx = ConversationContext(
            post_id=11711600,
            post_data={
                "title": "망카데미가 유독 힘숨이 심한거 같다",
                "content_blocks": [{"type": "text", "text": "아카데미물인데 주인공 힘숨 전개가 심함"}],
            },
            comments=[],
        )
        style_ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "express_opinion",
                    "primary_domain": "novel_literature",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                    "semantic_seed_review_context_terms": ["망카데미가"],
                    "search_suggestions": [{"query": "망카데미 노벨피아"}],
                }
            },
        )
        style_gatekeeper = {"detected_entities": {"possible_titles": ["망카데미가"]}}
        self.assertTrue(orchestrator._has_short_worklike_alias_search_probe(style_ctx, style_gatekeeper))

        kept = orchestrator._prune_title_search_requests_for_intent_permit(
            style_ctx,
            [
                {"purpose": "title_anchor_official_probe", "query": "망카데미 웹소설 노벨피아"},
                {"purpose": "community_site_probe", "query": "site:gall.dcinside.com 망카데미"},
                {"purpose": "term_definition", "query": "힘숨 뜻"},
            ],
            gatekeeper_result=style_gatekeeper,
            phase="unit",
        )
        self.assertEqual(
            [item["query"] for item in kept],
            ["망카데미 웹소설 노벨피아", "site:gall.dcinside.com 망카데미", "힘숨 뜻"],
        )

    def test_short_alias_bridge_prefers_community_and_filters_false_officials(self):
        orchestrator = Orchestrator(experts={})
        captured_queries = []

        def fake_search(query, purpose):
            captured_queries.append((query, purpose))
            if "site:gall.dcinside.com" in query:
                return [
                    {
                        "title": "황제분충 황제폐하 어쩌고",
                        "url": "https://gall.dcinside.com/mgallery/board/view/?id=genrenovel&no=200",
                        "content": "황제폐하가 웹소설 작가임을 숨김 이야기",
                    }
                ]
            if "노벨피아" in query:
                return [
                    {
                        "title": "웹소설로 꿈꾸는 세상! - 황제의 딸로 환생했다 - 노벨피아",
                        "url": "https://novelpia.com/novel/250464",
                        "content": "황제의 딸로 환생했다 작품 페이지",
                    }
                ]
            if "작가" in query:
                return [
                    {
                        "title": "웹소설로 꿈꾸는 세상! - 황제폐하가 웹소설 작가임을 숨김 - 노벨피아",
                        "url": "https://novelpia.com/novel/385635",
                        "content": "어쩌다보니 황제가 된 웹소설 작가의 이야기",
                    }
                ]
            if "줄임" in query:
                return [
                    {
                        "title": "필드의 황제 - 노벨피아",
                        "url": "https://novelpia.com/novel/326651",
                        "content": "필드의 황제 작품 페이지",
                    }
                ]
            return []

        orchestrator.search_fn = fake_search
        ctx = ConversationContext(
            post_id=11706832,
            post_data={
                "title": "황제분충 ㄱㅊ함?",
                "content_blocks": [{"type": "text", "text": "문피안가"}],
            },
            comments=["노피아"],
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "ask_question",
                    "primary_domain": "novel_literature",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                    "semantic_seed_review_context_terms": ["황제분충"],
                    "search_suggestions": [{"query": "황제분충 노벨피아"}],
                }
            },
        )
        gatekeeper = {"detected_entities": {"possible_titles": ["황제분충"]}}
        ctx.set_expert_output(ExpertType.GATEKEEPER, gatekeeper)

        results = orchestrator._execute_searches(
            [
                {"purpose": "title_anchor_official_probe", "query": "황제분충 노벨피아", "priority": 0},
                {"purpose": "community_site_probe", "query": "site:gall.dcinside.com 황제분충", "priority": 3},
                {"purpose": "title_search_community", "query": '"황제분충" 웹소설', "priority": 1},
                {"purpose": "adaptive_abbreviation", "query": "황제분충 줄임 웹소설 정식 제목", "priority": 4},
                {"purpose": "author_verify", "query": "황제분충 작가", "priority": 5},
            ],
            post_id=11706832,
            ctx=ctx,
        )

        self.assertEqual(captured_queries[0][0], '"황제분충" 웹소설')
        self.assertEqual(captured_queries[1][0], "site:gall.dcinside.com 황제분충")
        urls = [item.get("url") for item in results]
        self.assertIn("https://gall.dcinside.com/mgallery/board/view/?id=genrenovel&no=200", urls)
        self.assertIn("https://novelpia.com/novel/385635", urls)
        self.assertNotIn("https://novelpia.com/novel/250464", urls)
        self.assertNotIn("https://novelpia.com/novel/326651", urls)

    def test_internal_work_cluster_probe_bypasses_semantic_seed_early_stop(self):
        orchestrator = Orchestrator(experts={})
        ctx = ConversationContext(
            post_id=20010015,
            post_data={
                "title": "그래서 아리는 소원으로 받은 유산이 뭐임?",
                "content_blocks": [
                    {"type": "text", "text": "Qna에 없었음? 부등변은 가인이가 준거자너 파이어오니파티가 유산이야?"}
                ],
            },
            comments=["소원에 유산 관련이 없었자너", "팀원과 남친"],
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "ask_question",
                    "target_kind": "character",
                    "primary_domain": "novel_literature",
                    "domain_confidence": "high",
                    "domain_evidence": ["아리", "가인", "부등변", "파이어오니파티"],
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": [
                        "semantic_seed_review_non_title_terms_removed",
                        "semantic_seed_review_search_suggestions_removed",
                        "semantic_seed_review_specific_work_denied",
                    ],
                    "semantic_seed_review_context_terms": ["아리"],
                }
            },
        )
        gatekeeper = {
            "post_type": "work_discussion",
            "context_clues": {"has_specific_names": True},
            "detected_entities": {"possible_characters": ["아리", "가인"], "possible_titles": ["아리"]},
            "key_terms": ["아리", "소원", "유산", "부등변", "가인", "파이어오니파티"],
        }

        self.assertTrue(orchestrator._has_discourse_semantic_seed_demotion(ctx))
        self.assertTrue(orchestrator._has_internal_work_cluster_search_probe(ctx, gatekeeper))

        kept = orchestrator._prune_title_search_requests_for_intent_permit(
            ctx,
            [
                {"purpose": "official_title_verify", "query": "아리 소원 유산 웹소설"},
                {"purpose": "title_search_community", "query": "아리 가인 부등변 소설"},
                {"purpose": "term_definition", "query": "파이어오니파티 뜻"},
            ],
            gatekeeper_result=gatekeeper,
            phase="unit",
        )
        self.assertEqual(
            [item["query"] for item in kept],
            ["아리 가인 부등변 소설", "파이어오니파티 뜻"],
        )

    def test_korean_connective_lead_token_is_low_specificity_seed(self):
        orchestrator = Orchestrator(experts={})
        self.assertTrue(orchestrator._is_low_specificity_search_seed("그래서"))
        self.assertTrue(orchestrator._is_low_specificity_search_seed("그러니까"))
        self.assertTrue(orchestrator._is_low_specificity_search_seed("근데"))

    def test_internal_work_signal_hold_does_not_revive_hard_gaming_context(self):
        pipeline = build_pipeline()
        title = "쳇바퀴의 생쥐 사도가 되었다"
        post = PostInput(
            post_id=20010006,
            title="랫따싶 모드밸런스면 보이드정도까진 나올만함",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="림월드 모드 밸런스랑 보이드 레이드 얘기")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.discourse_warning = "non_novel(gaming,high)"
        ctx.set_expert_output(ExpertType.GATEKEEPER, {"gatekeeping": {"post_type": "work_discussion"}})
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "primary_domain": "gaming",
                    "intent": "express_opinion",
                    "target_kind": "community",
                }
            },
        )
        verification_result = {
            "novel_identity": {"official_title": title},
            "counter_arguments": [{"issue": "게임 모드 문맥이라 웹소설 작품 토론이 아님", "severity": "critical"}],
            "grounding_check": {"grounding_issue": "림월드 게임 모드"},
            "relation_judgment": {
                "relation_type": "thematic_overlap_only",
                "discussion_target": "community_banter",
                "promotion_decision": "hold",
            },
        }

        self.assertFalse(
            pipeline._has_internal_work_signal_unresolved_hold(
                ctx=ctx,
                verification_result=verification_result,
            )
        )

    def test_title_body_official_search_probe_bypasses_semantic_seed_demotion_only_for_work_blurb(self):
        orchestrator = Orchestrator(experts={})
        ctx = ConversationContext(
            post_id=20010007,
            post_data={
                "title": "두바이만 붙이면 잘되네",
                "content_blocks": [
                    {
                        "type": "text",
                        "text": "두바이 쫀득 뷰지로 ts 환생 배우 노맨스 인방 #TS #배우",
                    }
                ],
            },
            comments=[],
        )
        positive_gatekeeper = {
            "context_clues": {
                "title_as_body_continuation": True,
                "title_body_joined_text": "두바이만 붙이면 잘되네 두바이 쫀득 뷰지로 ts 환생 배우 노맨스 인방 #TS #배우",
            },
            "search_requests": [{"purpose": "official_title_verify", "query": "두바이 쫀득 뷰지 웹소설"}],
            "detected_entities": {"possible_titles": ["두바이 쫀득 뷰지"]},
        }
        self.assertTrue(orchestrator._has_title_body_official_search_probe(ctx, positive_gatekeeper))

        negative_gatekeeper = {
            "context_clues": {
                "title_as_body_continuation": True,
                "title_body_joined_text": "그냥 커뮤니티 잡담 길게 이어지는 글이다",
            },
            "search_requests": [{"purpose": "semantic_followup", "query": "커뮤니티 잡담"}],
            "detected_entities": {"possible_titles": ["잡담"]},
        }
        self.assertFalse(orchestrator._has_title_body_official_search_probe(ctx, negative_gatekeeper))

    def test_intent_permit_keeps_title_body_official_probe_queries(self):
        orchestrator = Orchestrator(experts={})
        ctx = ConversationContext(
            post_id=20010009,
            post_data={
                "title": "두바이만 붙이면 잘되네",
                "content_blocks": [
                    {
                        "type": "text",
                        "text": "두바이 쫀득 뷰지로 ts 환생했더니 한국에서 모셔가려고 난리 #TS #배우",
                    }
                ],
            },
            comments=[],
        )
        ctx.uncertainty_sources.append(
            "intent_permit_for_title_search=false(semantic_seed_review_not_specific_work)"
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "discuss_genre",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        gatekeeper = {
            "context_clues": {
                "title_as_body_continuation": True,
                "title_body_joined_text": "두바이만 붙이면 잘되네 두바이 쫀득 뷰지로 ts 환생 배우 #TS",
            },
            "search_requests": [{"purpose": "official_title_verify", "query": "두바이 쫀득 뷰지 웹소설"}],
            "detected_entities": {"possible_titles": ["두바이 쫀득 뷰지"]},
        }
        requests = [
            {
                "purpose": "title_body_sanitized_platform_probe",
                "query": "site:novelpia.com/novel 두바이 쫀득 TS 환생 인방",
            },
            {"purpose": "official_title_verify", "query": "두바이 쫀득 뷰지 웹소설"},
            {"purpose": "", "query": "두바이 TS 환생 웹소설"},
            {"purpose": "alias_raw_probe", "query": "두바이"},
            {"purpose": "ambiguous_meaning_track", "query": "두바이 뜻"},
        ]

        kept = orchestrator._prune_title_search_requests_for_intent_permit(
            ctx,
            requests,
            gatekeeper_result=gatekeeper,
            phase="unit",
        )

        self.assertEqual(
            [item["query"] for item in kept],
            [
                "site:novelpia.com/novel 두바이 쫀득 TS 환생 인방",
                "두바이 쫀득 뷰지 웹소설",
                "두바이 TS 환생 웹소설",
                "두바이 뜻",
            ],
        )

    def test_title_body_work_review_official_probe_survives_surface_pruning(self):
        orchestrator = Orchestrator(experts={})
        ctx = ConversationContext(
            post_id=11666713,
            post_data={
                "title": "21세기 무림 이거 재미네 ㅋㅋㅋ",
                "content_blocks": [
                    {"type": "text", "text": "무틀딱 각혈하게 만드는 작품인 줄 알았는데"},
                    {"type": "text", "text": "진지할 땐 진지하고 무협스러움이 가득한 작품이네 ㅋㅋ"},
                ],
            },
            comments=[],
        )
        gatekeeper = {
            "post_type": "review",
            "detected_entities": {"possible_titles": ["21세기 무림"]},
            "context_clues": {
                "title_as_body_continuation": True,
                "title_body_joined_text": (
                    "21세기 무림 이거 재미네 ㅋㅋㅋ "
                    "무틀딱 각혈하게 만드는 작품인 줄 알았는데 "
                    "진지할 땐 진지하고 무협스러움이 가득한 작품이네 ㅋㅋ"
                ),
            },
            "search_requests": [{"purpose": "official_title_verify", "query": "21세기 무림 웹소설"}],
            "key_terms": ["21세기 무림", "작품"],
        }
        ctx.set_expert_output(ExpertType.GATEKEEPER, gatekeeper)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "primary_domain": "novel_literature",
                    "intent": "express_opinion",
                    "title_novel_terms": ["21세기 무림"],
                    "semantic_seed_review": {"is_specific_work_discussion": True},
                }
            },
        )
        requests = [
            {"purpose": "official_title_verify", "query": "21세기 무림 웹소설"},
            {"purpose": "platform_title_search", "query": "21세기 무림 노벨피아"},
            {"purpose": "platform_title_search", "query": "시리즈 21세기 무림 작가"},
        ]

        sanitized = orchestrator._sanitize_query_poison_search_requests(
            requests,
            ctx=ctx,
            gatekeeper_result=gatekeeper,
            phase="unit",
        )
        kept = orchestrator._prune_low_specificity_seed_search_requests(
            ctx,
            sanitized,
            gatekeeper_result=gatekeeper,
        )

        self.assertEqual([item["query"] for item in kept], [item["query"] for item in requests])

    def test_decoder_keeps_official_keyword_bound_title_over_higher_abbreviation_alt(self):
        decoder = DecoderExpert(JSONLLM({"decoded_terms": [], "overall_confidence": "none"}))
        ctx = ConversationContext(
            post_id=11666713,
            post_data={
                "title": "21세기 무림 이거 재미네 ㅋㅋㅋ",
                "content_blocks": [
                    {"type": "text", "text": "무틀딱 각혈하게 만드는 작품인 줄 알았는데"},
                    {"type": "text", "text": "진지할 땐 진지하고 무협스러움이 가득한 작품이네 ㅋㅋ"},
                ],
            },
            comments=[],
        )
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "review",
                "detected_entities": {"possible_titles": ["21세기 무림"]},
                "key_terms": ["21세기 무림", "작품"],
                "context_clues": {
                    "title_as_body_continuation": True,
                    "title_body_joined_text": (
                        "21세기 무림 이거 재미네 ㅋㅋㅋ "
                        "무틀딱 각혈하게 만드는 작품인 줄 알았는데 "
                        "진지할 땐 진지하고 무협스러움이 가득한 작품이네 ㅋㅋ"
                    ),
                },
            },
        )
        ctx.search_results = [
            {
                "title": "21세기 무림세가",
                "url": "https://series.naver.com/novel/detail.series?productNo=1894278",
                "content": "21세기 무림세가. 21세기 무림 키워드로 확인되는 네이버 시리즈 웹소설.",
                "source_tier": "official_detail",
            },
            {
                "title": "21세기 무림세가",
                "url": "https://page.kakao.com/content/49668687?tab_type=about",
                "content": "21세기 무림세가 웹소설. 무림세가 서사.",
                "source_tier": "official_detail",
            },
            {
                "title": "웹소설로 꿈꾸는 세상! - 21세기를 여행하는 무림인을 위한 안내서",
                "url": "https://novelpia.com/novel/384498",
                "content": "21세기를 여행하는 무림인을 위한 안내서 작품 상세.",
                "source_tier": "official_detail",
            },
        ]
        result = {
            "decoded_terms": [
                {
                    "original": "21세기 무림",
                    "morphemes": ["21세기", "무림"],
                    "interpretations": [
                        {
                            "type": "novel_title",
                            "value": "21세기 무림세가",
                            "context_fit": "high",
                        }
                    ],
                    "best_match": {
                        "title": "21세기 무림세가",
                        "confidence": "high",
                        "url": "https://series.naver.com/novel/detail.series?productNo=1894278",
                    },
                    "candidates": [
                        {
                            "official_novel_title": "21세기 무림세가",
                            "url": "https://series.naver.com/novel/detail.series?productNo=1894278",
                            "platform": "naver_series",
                        }
                    ],
                    "grounding": {
                        "is_grounded": True,
                        "anchor_type": "title_mention",
                        "anchor_evidence": "21세기 무림 이거 재미네",
                    },
                }
            ],
            "overall_confidence": "high",
        }

        updated = decoder._validate_morpheme_in_title(result, ctx)

        self.assertEqual(
            updated["decoded_terms"][0]["best_match"]["title"],
            "21세기 무림세가",
        )
        self.assertFalse(
            any(
                hint.get("type") == "abbreviation_correction"
                and hint.get("corrected_title") == "21세기를 여행하는 무림인을 위한 안내서"
                for hint in getattr(ctx, "code_level_hints", [])
            )
        )

    def test_title_body_work_review_probe_does_not_rescue_plain_community_noise(self):
        orchestrator = Orchestrator(experts={})
        ctx = ConversationContext(
            post_id=20010010,
            post_data={
                "title": "그냥 잡담",
                "content_blocks": [{"type": "text", "text": "커뮤니티 잡담 길게 이어지는 글이다"}],
            },
            comments=[],
        )
        gatekeeper = {
            "post_type": "community_banter",
            "detected_entities": {"possible_titles": ["잡담"]},
            "context_clues": {
                "title_as_body_continuation": True,
                "title_body_joined_text": "그냥 잡담 커뮤니티 잡담 길게 이어지는 글이다",
            },
            "search_requests": [{"purpose": "official_title_verify", "query": "잡담 웹소설"}],
        }
        ctx.set_expert_output(ExpertType.GATEKEEPER, gatekeeper)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "primary_domain": "novel_literature",
                    "intent": "community_banter",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                }
            },
        )

        self.assertFalse(
            orchestrator._is_title_body_work_official_probe_query(
                "잡담 웹소설",
                ctx=ctx,
                gatekeeper_result=gatekeeper,
                purpose="official_title_verify",
            )
        )

    def test_low_specific_prune_keeps_title_body_compact_official_anchor(self):
        orchestrator = Orchestrator(experts={})
        ctx = ConversationContext(
            post_id=20010011,
            post_data={
                "title": "두바이만 붙이면 잘되네",
                "content_blocks": [
                    {
                        "type": "text",
                        "text": "두바이 쫀득 뷰지로 ts 환생 배우 노맨스 인방 #TS #배우",
                    }
                ],
            },
            comments=[],
        )
        ctx.discourse_warning = "discuss_genre(medium)"
        gatekeeper = {
            "context_clues": {
                "title_as_body_continuation": True,
                "title_body_joined_text": "두바이만 붙이면 잘되네 두바이 쫀득 뷰지로 ts 환생 배우 #TS",
            },
            "search_requests": [{"purpose": "official_title_verify", "query": "두바이 쫀득 뷰지 웹소설"}],
            "detected_entities": {"possible_titles": ["두바이 쫀득 뷰지", "두바"]},
            "key_terms": ["TS", "노맨스", "배우"],
        }
        requests = [
            {"purpose": "title_anchor_official_probe", "query": "두바 노벨피아"},
            {"purpose": "title_search_community", "query": "두바이 웹소설"},
        ]

        kept = orchestrator._prune_low_specificity_seed_search_requests(
            ctx,
            requests,
            gatekeeper_result=gatekeeper,
        )

        self.assertIn("두바 노벨피아", [item["query"] for item in kept])

    def test_low_specific_prune_keeps_weak_title_body_compact_official_anchor(self):
        orchestrator = Orchestrator(experts={})
        ctx = ConversationContext(
            post_id=20010012,
            post_data={
                "title": "두바이만 붙이면 잘되네",
                "content_blocks": [
                    {
                        "type": "text",
                        "text": "두바이 쫀득 뷰지로 ts 환생했더니 한국에서 모셔가려고 난리",
                    },
                    {"type": "text", "text": "#TS #배우 #노맨스 #인방"},
                ],
            },
            comments=["두바이 불끈 자지한테 암타당해서 전용케이스됨"],
        )
        gatekeeper = {
            "context_clues": {
                "title_as_body_continuation": True,
                "title_body_joined_text": (
                    "두바이만 붙이면 잘되네 "
                    "두바이 쫀득 뷰지로 ts 환생했더니 한국에서 모셔가려고 난리 "
                    "#TS #배우 #노맨스 #인방"
                ),
            },
            "search_requests": [
                {"purpose": "official_title_verify", "query": "두바이 웹소설"},
                {"purpose": "official_title_verify", "query": "두바이 TS 환생 배우 인방"},
            ],
            "detected_entities": {"possible_titles": ["두바이"]},
            "key_terms": ["두바이", "TS 환생", "배우", "노맨스", "인방"],
        }
        requests = [
            {"purpose": "title_anchor_exact_probe", "query": "두바"},
            {"purpose": "title_anchor_official_probe", "query": "두바 노벨피아"},
            {"purpose": "title_anchor_official_probe", "query": "두바 웹소설"},
            {"purpose": "official_title_verify", "query": "두바이 웹소설"},
        ]

        kept = orchestrator._prune_low_specificity_seed_search_requests(
            ctx,
            requests,
            gatekeeper_result=gatekeeper,
        )

        kept_queries = [item["query"] for item in kept]
        self.assertIn("두바 노벨피아", kept_queries)
        self.assertNotIn("두바", kept_queries)

    def test_title_body_probe_rerank_prefers_site_scoped_detail_queries(self):
        calls = []

        def search_fn(query, purpose=""):
            calls.append((query, purpose))
            return []

        orchestrator = Orchestrator(experts={}, search_fn=search_fn)
        ctx = ConversationContext(
            post_id=20010010,
            post_data={
                "title": "두바이만 붙이면 잘되네",
                "content_blocks": [
                    {
                        "type": "text",
                        "text": "두바이 쫀득 뷰지로 ts 환생했더니 한국에서 모셔가려고 난리 #TS #배우",
                    }
                ],
            },
            comments=[],
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {"discourse_analysis": {"primary_domain": "novel_literature", "intent": "discuss_genre"}},
        )
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "genre_discussion",
                "context_clues": {
                    "title_as_body_continuation": True,
                    "title_body_joined_text": "두바이만 붙이면 잘되네 두바이 쫀득 뷰지로 ts 환생 배우 #TS",
                },
                "search_requests": [
                    {"purpose": "official_title_verify", "query": "두바이 쫀득 뷰지 웹소설"},
                ],
                "detected_entities": {"possible_titles": ["두바이 쫀득 뷰지"]},
            },
        )
        requests = [
            {
                "purpose": "title_body_sanitized_platform_probe",
                "priority": 0,
                "query": 'site:novelpia.com/novel "두바이" "쫀득" "TS"',
            },
            {
                "purpose": "title_body_sanitized_platform_probe",
                "priority": 0,
                "query": "site:novelpia.com/novel 두바이 쫀득 TS 환생 인방",
            },
            {
                "purpose": "title_body_sanitized_platform_probe",
                "priority": 0,
                "query": "두바이 쫀득 TS 환생 인방 노벨피아",
            },
            {
                "purpose": "title_anchor_official_probe",
                "priority": 0,
                "query": "두바 노벨피아",
            },
            {
                "purpose": "title_body_sanitized_platform_probe",
                "priority": 0,
                "query": "두바이 TS 환생 노벨피아",
            },
            {
                "purpose": "title_body_sanitized_platform_probe",
                "priority": 0,
                "query": 'site:novelpia.com/novel "두바이" "쫀득"',
            },
            {
                "purpose": "title_body_sanitized_platform_probe",
                "priority": 0,
                "query": '"두바이" "쫀득" "TS" "노벨피아"',
            },
            {
                "purpose": "title_body_sanitized_platform_probe",
                "priority": 0,
                "query": "두바이 쫀득 TS 환생 인방 웹소설",
            },
        ]

        with patch.dict(os.environ, {"PIPELINE_SEARCH_CONCURRENCY": "1"}):
            orchestrator._execute_searches(requests, post_id=ctx.post_id, ctx=ctx)

        first_six = [query for query, _purpose in calls[:6]]
        self.assertIn("site:novelpia.com/novel 두바이 쫀득 TS 환생 인방", first_six[:3])
        self.assertIn('site:novelpia.com/novel "두바이" "쫀득" "TS"', first_six[:3])
        self.assertIn("두바 노벨피아", first_six)
        self.assertIn(("두바 노벨피아", "title_anchor_official_probe"), calls)

    def test_core_fast_demotes_broad_multi_site_or_official_probe_below_platform_text_queries(self):
        calls = []

        def search_fn(query, purpose=""):
            calls.append((query, purpose))
            return []

        orchestrator = Orchestrator(experts={}, search_fn=search_fn)
        ctx = ConversationContext(
            post_id=11660258,
            post_data={
                "title": "괴담텔 아리야...",
                "content_blocks": [{"type": "text", "text": "니 엄만 이제 디졌어"}],
            },
            comments=[],
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {"discourse_analysis": {"primary_domain": "novel_literature", "intent": "discuss_work"}},
        )
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {"post_type": "work_discussion", "detected_entities": {"possible_titles": ["괴담 호텔 탈출기"]}},
        )
        requests = [
            {
                "purpose": "official_title_verify",
                "priority": 0,
                "query": (
                    "(site:novelpia.com OR site:munpia.com OR site:series.naver.com "
                    "OR site:page.kakao.com OR site:joara.com) 괴담 호텔 탈출기"
                ),
            },
            {
                "purpose": "official_title_verify",
                "priority": 0,
                "query": "괴담 호텔 탈출기 웹소설 문피아",
            },
            {
                "purpose": "official_title_verify",
                "priority": 0,
                "query": "괴담 호텔 탈출기 웹소설 노벨피아",
            },
        ]

        with patch.object(
            orchestrator,
            "_derive_search_budget_profile",
            return_value={"profile": "core_fast_resolve", "max_q": 5, "stop_after_official_hit": False},
        ), patch.dict(
            os.environ,
            {"PIPELINE_SEARCH_CONCURRENCY": "1", "LLM_ENABLE_CONTEXT_QUERY_RERANK": "1"},
        ):
            orchestrator._execute_searches(requests, post_id=ctx.post_id, ctx=ctx)

        executed = [query for query, _purpose in calls]
        self.assertEqual(executed, ["괴담 호텔 탈출기 웹소설 문피아", "괴담 호텔 탈출기 웹소설 노벨피아"])

    def test_core_fast_keeps_specific_title_body_probe_after_generic_nonzero(self):
        calls = []

        def search_fn(query, purpose=""):
            calls.append((query, purpose))
            return [{"title": "검색 결과", "url": f"https://example.test/{len(calls)}", "content": "nonzero"}]

        orchestrator = Orchestrator(experts={}, search_fn=search_fn)
        ctx = ConversationContext(
            post_id=11713222,
            post_data={
                "title": "현대 하렘물은 진짜 잘쓰는 작가가 손에꼽네",
                "content_blocks": [
                    {"type": "text", "text": "잘생인방보는데 주인공이 여자를 도구처럼 보는 전개 얘기"}
                ],
            },
            comments=["전작도 잘생인편으로 현대하렘아님?"],
        )
        gatekeeper = {
            "post_type": "work_discussion",
            "detected_entities": {"possible_titles": ["잘생인방", "잘생인편"]},
            "context_clues": {
                "title_as_body_continuation": True,
                "title_body_joined_text": "현대 하렘물은 진짜 잘쓰는 작가 잘생인방 주인공 전개 인방",
            },
            "key_terms": ["잘생인방", "잘생인편", "현대 하렘물"],
        }
        ctx.set_expert_output(ExpertType.GATEKEEPER, gatekeeper)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {"discourse_analysis": {"primary_domain": "novel_literature", "intent": "discuss_work"}},
        )
        requests = [
            {
                "purpose": "title_body_sanitized_platform_probe",
                "priority": 0,
                "query": 'site:novelpia.com/novel "잘생인방" "잘생인편" "인방"',
            },
            {
                "purpose": "title_body_sanitized_platform_probe",
                "priority": 0,
                "query": "site:novelpia.com/novel 잘생인방 잘생인편 현대하렘 인방",
            },
            {
                "purpose": "title_body_sanitized_platform_probe",
                "priority": 0,
                "query": "잘생인방 현대하렘 웹소설 노벨피아",
            },
        ]

        with patch.object(
            orchestrator,
            "_derive_search_budget_profile",
            return_value={"profile": "core_fast_resolve", "max_q": 5, "stop_after_official_hit": False},
        ), patch.dict(os.environ, {"PIPELINE_SEARCH_CONCURRENCY": "1"}):
            orchestrator._execute_searches(requests, post_id=ctx.post_id, ctx=ctx)

        executed = [query for query, _purpose in calls]
        self.assertGreaterEqual(len(executed), 3)
        self.assertIn("잘생인방 현대하렘 웹소설 노벨피아", executed)

    def test_core_fast_keeps_direct_body_alias_probe_after_two_nonzero_broad_queries(self):
        calls = []

        def search_fn(query, purpose=""):
            calls.append((query, purpose))
            return [{"title": f"검색 결과 {len(calls)}", "url": f"https://example.test/{len(calls)}"}]

        orchestrator = Orchestrator(experts={}, search_fn=search_fn)
        ctx = ConversationContext(
            post_id=11698880,
            post_data={
                "title": "아생갤 개 존나게 재밌군 ㅇㅇ",
                "content_blocks": [
                    {"type": "text", "text": "가챠펑크 세드릭도 그렇고 주인공이 시원시원해서 좋구나"}
                ],
            },
            comments=[],
        )
        gatekeeper = {
            "post_type": "work_discussion",
            "detected_entities": {
                "possible_titles": ["아생갤", "가챠펑크"],
                "possible_characters": ["세드릭"],
            },
            "context_clues": {
                "title_as_body_continuation": True,
                "title_body_joined_text": "아생갤 가챠펑크 세드릭 주인공",
            },
            "key_terms": ["아생갤", "가챠펑크", "세드릭"],
        }
        ctx.set_expert_output(ExpertType.GATEKEEPER, gatekeeper)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {"discourse_analysis": {"primary_domain": "novel_literature", "intent": "express_opinion"}},
        )
        self.assertIn(
            "가챠펑크",
            orchestrator._collect_direct_worklike_alias_probe_norms(ctx, gatekeeper),
        )
        requests = [
            {"purpose": "platform_title_search", "priority": 0, "query": "아생갤 노벨피아"},
            {"purpose": "platform_title_search", "priority": 0, "query": "시리즈 아생갤 작가"},
            {"purpose": "official_title_verify", "priority": 2, "query": "가챠펑크 세드릭"},
        ]

        with patch.object(
            orchestrator,
            "_derive_search_budget_profile",
            return_value={"profile": "core_fast_resolve", "max_q": 5, "stop_after_official_hit": False},
        ), patch.dict(
            os.environ,
            {"PIPELINE_SEARCH_CONCURRENCY": "1", "LLM_ENABLE_CONTEXT_QUERY_RERANK": "0"},
        ):
            orchestrator._execute_searches(requests, post_id=ctx.post_id, ctx=ctx)

        executed = [query for query, _purpose in calls]
        self.assertGreaterEqual(len(executed), 3)
        self.assertIn("가챠펑크 세드릭", executed)

    def test_non_novel_early_exit_sees_direct_body_alias_character_probe(self):
        orchestrator = Orchestrator(experts={})
        ctx = ConversationContext(
            post_id=11698880,
            post_data={
                "title": "아생갤 개 존나게 재밌군 ㅇㅇ",
                "content_blocks": [
                    {"type": "text", "text": "가챠펑크 세드릭도 그렇고 주인공이 시원시원해서 좋구나"},
                    {"type": "image", "image_url": "https://example.test/spongebob.png"},
                ],
            },
            comments=[],
        )
        gatekeeper = {
            "post_type": "community_banter",
            "detected_entities": {
                "possible_titles": ["아생갤", "스폰지밥"],
                "possible_characters": ["스폰지밥", "뚱이", "세드릭"],
            },
            "key_terms": ["아생갤", "가챠펑크", "세드릭"],
            "search_requests": [
                {"purpose": "title_search_community", "priority": 2, "query": "가챠펑크 세드릭"},
            ],
        }
        ctx.set_expert_output(ExpertType.GATEKEEPER, gatekeeper)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "make_joke",
                    "target_kind": "community",
                    "primary_domain": "memes_humor",
                    "domain_confidence": "high",
                }
            },
        )

        self.assertNotIn(
            "가챠펑크",
            orchestrator._collect_direct_worklike_alias_probe_norms(ctx, gatekeeper),
        )
        self.assertTrue(
            orchestrator._has_direct_worklike_alias_character_search_probe(ctx, gatekeeper)
        )

    def test_non_novel_early_exit_uses_discourse_alias_character_probe(self):
        orchestrator = Orchestrator(experts={})
        ctx = ConversationContext(
            post_id=11698880,
            post_data={
                "title": "아생갤 개 존나게 재밌군 ㅇㅇ",
                "content_blocks": [
                    {"type": "text", "text": "가챠펑크 세드릭도 그렇고 주인공이 시원시원해서 좋구나"},
                    {"type": "image", "image_url": "https://example.test/spongebob.png"},
                ],
            },
            comments=[],
        )
        gatekeeper = {
            "post_type": "community_banter",
            "detected_entities": {
                "possible_titles": ["스폰지밥"],
                "possible_characters": ["스폰지밥", "뚱이"],
            },
            "context_clues": {
                "title_as_body_continuation": True,
                "title_body_joined_text": "아생갤 가챠펑크 세드릭 주인공",
            },
            "key_terms": ["아생갤", "가챠펑크", "세드릭"],
            "search_requests": [],
        }
        ctx.set_expert_output(ExpertType.GATEKEEPER, gatekeeper)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "make_joke",
                    "target_kind": "genre",
                    "primary_domain": "anime",
                    "domain_confidence": "high",
                    "search_suggestions": [
                        {
                            "priority": 1,
                            "query": "가챠펑크 세드릭",
                            "purpose": "특정 작품 캐릭터명인지, 장르/밈 언급인지 검색으로 확인",
                        }
                    ],
                }
            },
        )

        self.assertTrue(
            orchestrator._has_direct_worklike_alias_character_search_probe(ctx, gatekeeper)
        )

    def test_non_novel_early_exit_ignores_image_character_without_body_pair(self):
        orchestrator = Orchestrator(experts={})
        ctx = ConversationContext(
            post_id=11698880,
            post_data={
                "title": "아생갤 개 존나게 재밌군 ㅇㅇ",
                "content_blocks": [
                    {"type": "text", "text": "가챠펑크 세드릭도 그렇고 주인공이 시원시원해서 좋구나"},
                    {"type": "image", "image_url": "https://example.test/spongebob.png"},
                ],
            },
            comments=[],
        )
        gatekeeper = {
            "post_type": "community_banter",
            "detected_entities": {
                "possible_titles": ["아생갤", "스폰지밥"],
                "possible_characters": ["스폰지밥", "뚱이", "세드릭"],
            },
            "key_terms": ["아생갤", "가챠펑크", "세드릭"],
            "search_requests": [
                {"purpose": "title_search_community", "priority": 2, "query": "가챠펑크 스폰지밥"},
            ],
        }
        ctx.set_expert_output(ExpertType.GATEKEEPER, gatekeeper)

        self.assertFalse(
            orchestrator._has_direct_worklike_alias_character_search_probe(ctx, gatekeeper)
        )

    def test_injects_direct_worklike_alias_character_search_probe(self):
        orchestrator = Orchestrator(experts={})
        ctx = ConversationContext(
            post_id=11663521,
            post_data={
                "title": "TS) 시스터즈 퍼스트 정신머리 고치려면",
                "content_blocks": [
                    {"type": "text", "text": "고쳐질때까지 토우마가 갱생펀치 갈기면 되지 않을까?"},
                    {"type": "image", "image_url": "https://example.test/touma.png"},
                ],
            },
            comments=[],
        )
        gatekeeper = {
            "post_type": "character_talk",
            "detected_entities": {
                "possible_titles": ["시스터즈 퍼스트"],
                "possible_characters": ["토우마"],
            },
            "context_clues": {
                "title_as_body_continuation": True,
                "title_body_joined_text": "시스터즈 퍼스트 토우마 갱생펀치",
            },
            "key_terms": ["시스터즈 퍼스트", "토우마"],
        }
        ctx.set_expert_output(ExpertType.GATEKEEPER, gatekeeper)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {"discourse_analysis": {"primary_domain": "novel_literature", "intent": "character_talk"}},
        )

        requests = [
            {"purpose": "title_search_community", "priority": 2, "query": "시스터즈 퍼스트 리뷰"},
        ]
        injected = orchestrator._inject_direct_worklike_alias_character_search_requests(
            ctx,
            requests,
            gatekeeper_result=gatekeeper,
        )
        queries = [item["query"] for item in injected]

        self.assertEqual(queries[0], "시스터즈 퍼스트 토우마")
        self.assertIn("시스터즈 퍼스트 토우마 웹소설", queries)
        self.assertLess(queries.index("시스터즈 퍼스트 토우마"), queries.index("시스터즈 퍼스트 리뷰"))
        kept = orchestrator._prune_title_search_requests_for_intent_permit(
            ctx,
            injected,
            gatekeeper_result=gatekeeper,
            phase="unit",
        )
        self.assertIn("시스터즈 퍼스트 토우마", [item["query"] for item in kept])

    def test_direct_worklike_alias_character_injection_requires_direct_character_surface(self):
        orchestrator = Orchestrator(experts={})
        ctx = ConversationContext(
            post_id=11663521,
            post_data={
                "title": "TS) 시스터즈 퍼스트 정신머리 고치려면",
                "content_blocks": [
                    {"type": "text", "text": "고쳐질때까지 토우마가 갱생펀치 갈기면 되지 않을까?"},
                    {"type": "image", "image_url": "https://example.test/misaka.png"},
                ],
            },
            comments=[],
        )
        gatekeeper = {
            "post_type": "character_talk",
            "detected_entities": {
                "possible_titles": ["시스터즈 퍼스트"],
                "possible_characters": ["미사카"],
            },
            "context_clues": {
                "title_as_body_continuation": True,
                "title_body_joined_text": "시스터즈 퍼스트 토우마 갱생펀치",
            },
            "key_terms": ["시스터즈 퍼스트", "미사카"],
        }
        ctx.set_expert_output(ExpertType.GATEKEEPER, gatekeeper)

        requests = [
            {"purpose": "title_search_community", "priority": 2, "query": "시스터즈 퍼스트 리뷰"},
        ]
        injected = orchestrator._inject_direct_worklike_alias_character_search_requests(
            ctx,
            requests,
            gatekeeper_result=gatekeeper,
        )

        self.assertEqual(injected, requests)

    def test_direct_body_alias_probe_processed_after_broad_genre_official_hit(self):
        calls = []

        def search_fn(query, purpose=""):
            calls.append((query, purpose))
            if "잘생인방" in query:
                return [
                    {
                        "title": "잘생기면 편해지는 인방 생활 - 노벨피아",
                        "url": "https://novelpia.com/novel/384016",
                        "content": "잘생인방은 잘생기면 편해지는 인방 생활을 가리키는 웹소설 약칭.",
                    }
                ]
            return [
                {
                    "title": "웹소설로 꿈꾸는 세상! - 연예계 물을 하렘물로 바꿔버리는 법 - 노벨피아",
                    "url": "https://novelpia.com/novel/299220",
                    "content": "현대판타지 하렘 노벨피아 작품 페이지.",
                }
            ]

        orchestrator = Orchestrator(experts={}, search_fn=search_fn)
        ctx = ConversationContext(
            post_id=11713222,
            post_data={
                "title": "현대 하렘물은 진짜 잘쓰는 작가가 손에꼽네",
                "content_blocks": [
                    {
                        "type": "text",
                        "text": "잘생인방보는데 그냥 주인공이 여자를 도구처럼 보는 전개 얘기",
                    }
                ],
            },
            comments=["전작도 잘생인편으로 현대하렘아님?"],
        )
        ctx.discourse_warning = "semantic_seed_review(no_work_anchor)"
        gatekeeper = {
            "post_type": "work_discussion",
            "detected_entities": {"possible_titles": ["잘생인방", "잘생인편"]},
            "context_clues": {
                "title_as_body_continuation": True,
                "title_body_joined_text": "현대 하렘물 작가 잘생인방 주인공 여자 전개 인방",
            },
            "key_terms": ["잘생인방", "잘생인편", "현대 하렘물"],
            "search_requests": [
                {"purpose": "official_title_verify", "query": "잘생인방 웹소설"},
                {"purpose": "title_search_community", "query": "잘생인방 정식명칭"},
            ],
        }
        ctx.set_expert_output(ExpertType.GATEKEEPER, gatekeeper)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "primary_domain": "novel_literature",
                    "intent": "request_recommendation",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                    "semantic_seed_review_context_terms": ["잘생인방"],
                }
            },
        )
        self.assertEqual(
            orchestrator._collect_direct_worklike_alias_probe_norms(ctx, gatekeeper),
            {"잘생인방"},
        )

        requests = [
            {"purpose": "title_anchor_official_probe", "priority": 0, "query": "현대 하렘물 노벨피아"},
            {"purpose": "official_title_verify", "priority": 1, "query": "잘생인방 웹소설"},
            {"purpose": "title_search_community", "priority": 1, "query": "잘생인방 정식명칭"},
            {"purpose": "author_verify", "priority": 1, "query": "잘생인방 작가"},
        ]
        kept = orchestrator._prune_title_search_requests_for_intent_permit(
            ctx,
            requests,
            gatekeeper_result=gatekeeper,
            phase="unit",
        )
        self.assertIn("잘생인방 작가", [item["query"] for item in kept])

        with patch.dict(os.environ, {"PIPELINE_SEARCH_CONCURRENCY": "2"}):
            results = orchestrator._execute_searches(kept, post_id=ctx.post_id, ctx=ctx)

        result_urls = [item.get("url") for item in results]
        self.assertIn("https://novelpia.com/novel/384016", result_urls)
        self.assertEqual(ctx.search_budget_profile, "core_fast_resolve")
        self.assertGreaterEqual(ctx.search_budget_limit, 6)
        self.assertIn("잘생인방 웹소설", [query for query, _purpose in calls])

    def test_try_promote_best_candidate_blocks_no_work_decoder_alias_official_only(self):
        pipeline = build_pipeline()
        title = "망겜의 힐러"
        post = PostInput(
            post_id=11718080,
            title="망겜힐 같이 볼 친구 있었으면",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="작품 얘기라기보다 같이 볼 친구가 있으면 좋겠다는 잡담")],
            comments=[],
        )
        ctx = ConversationContext(post_id=11718080, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)
        ctx.search_results = [
            {
                "title": "망겜의 힐러 - 네이버 시리즈",
                "url": "https://series.naver.com/novel/detail.series?productNo=7774",
                "content": "망겜의 힐러 웹소설 작품 페이지",
            }
        ]
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "decoded_terms": [
                    {
                        "original": "망겜힐",
                        "best_match": {
                            "title": title,
                            "confidence": "High",
                            "heretic_url": "https://series.naver.com/novel/detail.series?productNo=7774",
                        },
                    }
                ]
            },
        )

        promoted = pipeline._try_promote_best_candidate(
            ctx,
            {
                "grounding_check": {"anchor_found": "title_abbrev_mention"},
                "novel_identity": {},
            },
            {
                "_title_deliberately_null": True,
                "_title_null_block_reasons": ["semantic_seed_review_guard"],
            },
        )

        self.assertIsNone(promoted)
        self.assertTrue(getattr(ctx, "_semantic_no_work_title_promotion_blocked", False))
        self.assertEqual(getattr(ctx, "_semantic_no_work_title_promotion_blocked_title", None), title)

    def test_safe_single_candidate_unresolved_promotion_blocks_no_work_official_only(self):
        pipeline = build_pipeline()
        title = "망겜의 힐러"
        post = PostInput(
            post_id=11718080,
            title="망겜힐 같이 볼 친구 있었으면",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="식사 중 같이 소설 볼 친구가 있었으면 하는 한탄")],
            comments=[],
        )
        ctx = ConversationContext(post_id=11718080, post_data=pipeline._post_to_dict(post), comments=[])
        mark_no_work_seed(ctx)
        ctx.set_expert_output(
            ExpertType.ARBITER,
            {"final_decision": {"_title_deliberately_null": True}},
        )
        ctx.search_results = [
            {
                "title": "망겜의 힐러 - 네이버 시리즈",
                "url": "https://series.naver.com/novel/detail.series?productNo=7774",
                "content": "망겜의 힐러 웹소설 작품 페이지",
            }
        ]
        candidate = DetectedTitle(
            official_title=title,
            confidence="High",
            source_tier="official_detail",
            heretic_url="https://series.naver.com/novel/detail.series?productNo=7774",
        )

        picked = pipeline._pick_safe_single_candidate_unresolved_promotion(
            ctx=ctx,
            title_candidates=[candidate],
            discussion_type="general",
            subtype="unresolved_work",
            official_title=None,
            work_resolution="unresolved",
            consistency_flags=[],
            verification_result={"grounding_check": {"anchor_found": "search_only"}},
            comparison_target=None,
            recommendation_candidates=[],
        )

        self.assertIsNone(picked)
        self.assertTrue(getattr(ctx, "_semantic_no_work_title_promotion_blocked", False))

    def test_non_novel_literature_warning_blocks_ocr_title_promotion(self):
        pipeline = build_pipeline()
        title = "파우스트 1"
        post = PostInput(
            post_id=11706871,
            title="독후감 쓰려고 파우스트 읽었었는데 결말에서 벙쪘음",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", text=""),
                ContentBlock(type="text", text="갑자기 신이 나타나서 내가 이겼음 악마 너 졌음"),
            ],
            comments=["데우스 엑스 마키나"],
        )
        ctx = ConversationContext(post_id=11706871, post_data=pipeline._post_to_dict(post), comments=post.comments)
        ctx.discourse_warning = "non_novel(literature,high)"
        ctx.post_data["image_enrichment"] = [
            {
                "ocr_text": "파우스트 1 민음사 세계문학전집",
                "explicit_work_title": title,
                "work_cues": [title, "민음사", "세계문학전집"],
                "evidence_type": "cover_title",
                "title_role": "work_title",
                "focus_role": "work_anchor",
                "screen_type": "work_surface",
                "surface_type": "book_cover",
                "promotion_eligible": True,
                "confidence": "High",
            }
        ]
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "primary_domain": "literature",
                    "warnings": ["non_novel(literature,high)"],
                    "reasoning": "고전 문학 독후감으로 웹소설 작품 담론이 아님",
                }
            },
        )

        self.assertFalse(pipeline._has_image_primary_promotion_signal(ctx, title))
        self.assertFalse(pipeline._has_ocr_catalog_official_title_evidence(ctx, title))

        acceptance = pipeline._compute_title_acceptance(ctx, title, {})
        self.assertNotEqual(acceptance["decision"], "accept")
        self.assertIn("non_novel_warning", acceptance["notes"])

        final_decision = {}
        allowed = pipeline._can_promote_title_after_semantic_no_work(
            ctx,
            title,
            source="direct_full_title_candidate_rescued",
            final_decision=final_decision,
            verification_result={},
        )

        self.assertFalse(allowed)
        self.assertTrue(getattr(ctx, "_non_novel_discourse_title_promotion_blocked", False))
        self.assertEqual(getattr(ctx, "_non_novel_discourse_title_promotion_blocked_title", None), title)
        self.assertIn(
            "non_novel_discourse_title_promotion_blocked",
            final_decision.get("_title_null_block_reasons", []),
        )

    def test_resolved_public_title_gate_blocks_image_scene_only_official_detail(self):
        pipeline = build_pipeline()
        title = "세계 최강 미소녀에게 납치당했습니다"
        url = "https://novelpia.com/novel/201411"
        image_evidence = {
            "ocr_text": (
                "참고인의 모든 변론이 끝났다. 얼굴도 모르는 미소녀를 납치 후, "
                "가스라이팅을 반복한 후 세뇌를 걸어서 마을에 테러를 일으켰고. "
                "B급 모험가 '밤'도깨비 에이브가 되어 있었다."
            ),
            "evidence_type": "explicit_text",
            "title_role": "unknown",
            "promotion_eligible": False,
            "work_cues": ["B급 모험가 '밤'도깨비 에이브", "미소녀 납치"],
        }
        post = PostInput(
            post_id=11700470,
            title="어케 주인공 죄목이",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", url="https://dcimg.example/11700470.jpg"),
                ContentBlock(type="text", text="납치담금세뇌테러불법투기셍태계교란희롱준강간"),
            ],
            comments=["교수형"],
        )
        ctx = ConversationContext(
            post_id=11700470,
            post_data=pipeline._post_to_dict(post),
            comments=post.comments,
        )
        ctx.post_data["image_enrichment"] = [dict(image_evidence)]
        candidate = DetectedTitle(
            official_title=title,
            heretic_url=url,
            confidence="High",
            alias_or_mention="납치 미소녀",
            source_tier="official_detail",
            page_type="novel_page",
            reference_role="primary",
        )

        decision = pipeline._record_resolved_public_title_gate_decision(
            ctx,
            title,
            candidate_url=url,
            title_candidates=[candidate],
            resolution_scope_fields={
                "is_resolved_work_discussion": True,
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "discussion_type": "character_talk",
                "anchor_type": "title_alias",
                "context_sources": ["title", "body", "comments", "search"],
                "image_evidence_catalog": [dict(image_evidence)],
            },
            verification_result={
                "grounding_check": {"anchor_found": "plot_mention"},
                "novel_identity": {"evidence_type": "search_platform_url"},
            },
        )

        self.assertFalse(decision["publish_allowed"])
        self.assertEqual(decision["status"], "candidate_only")
        self.assertIn(
            "image_scope_missing_candidate_surface",
            decision["reason_codes"],
        )
        self.assertFalse(ctx._last_promotion_gate_state["row_discusses_work_as_work"])

    def test_resolved_public_title_gate_builds_runtime_image_catalog_before_serialization(self):
        pipeline = build_pipeline()
        title = "세계 최강 미소녀에게 납치당했습니다"
        url = "https://novelpia.com/novel/201411"
        image_evidence = {
            "ocr_text": (
                "참고인의 모든 변론이 끝났다. 얼굴도 모르는 미소녀를 납치 후, "
                "B급 모험가 '밤'도깨비 에이브가 되어 있었다."
            ),
            "evidence_type": "explicit_text",
            "title_role": "unknown",
            "promotion_eligible": False,
            "work_cues": ["B급 모험가 '밤'도깨비 에이브", "미소녀 납치"],
        }
        post = PostInput(
            post_id=11700470,
            title="어케 주인공 죄목이",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", url="https://dcimg.example/11700470.jpg"),
                ContentBlock(type="text", text="납치담금세뇌테러불법투기셍태계교란희롱준강간"),
            ],
            comments=["교수형"],
        )
        ctx = ConversationContext(
            post_id=11700470,
            post_data=pipeline._post_to_dict(post),
            comments=post.comments,
        )
        ctx.post_data["image_enrichment"] = [dict(image_evidence)]
        candidate = DetectedTitle(
            official_title=title,
            heretic_url=url,
            confidence="High",
            alias_or_mention="납치 미소녀",
            source_tier="official_detail",
            page_type="novel_page",
            reference_role="primary",
        )

        decision = pipeline._record_resolved_public_title_gate_decision(
            ctx,
            title,
            candidate_url=url,
            title_candidates=[candidate],
            resolution_scope_fields={
                "is_resolved_work_discussion": True,
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "discussion_type": "character_talk",
                "anchor_type": "title_alias",
                "context_sources": ["title", "body", "comments", "search"],
            },
            verification_result={
                "grounding_check": {"anchor_found": "plot_mention"},
                "novel_identity": {"evidence_type": "search_platform_url"},
            },
        )

        self.assertFalse(decision["publish_allowed"])
        self.assertEqual(decision["status"], "candidate_only")
        self.assertIn(
            "image_scope_missing_candidate_surface",
            decision["reason_codes"],
        )
        self.assertFalse(ctx._last_promotion_gate_state["row_discusses_work_as_work"])

    def test_injected_ocr_scene_cannot_be_reused_as_non_image_candidate_surface(self):
        pipeline = build_pipeline()
        title = "미소녀 마개조 부서"
        url = "https://novelpia.com/novel/89714"
        post = PostInput(
            post_id=11700470,
            title="어케 주인공 죄목이",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", url="https://dcimg.example/11700470.jpg"),
                ContentBlock(type="text", text="납치담금세뇌테러불법투기셍태계교란희롱준강간"),
            ],
            comments=["교수형"],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=post.comments,
        )
        ctx.post_data["image_enrichment"] = [
            {
                "block_index": 0,
                "ocr_text": (
                    "참고인의 모든 변론이 끝났다. 얼굴도 모르는 미소녀를 납치 후, "
                    "가스라이팅을 반복하고 B급 모험가 밤도깨비 에이브가 되었다."
                ),
                "visual_summary": "웹소설 본문 스크랩 이미지",
                "evidence_type": "explicit_text",
                "title_role": "unknown",
                "focus_role": "supporting_text",
                "surface_type": "quoted_text_screenshot",
                "promotion_eligible": False,
                "work_cues": ["미소녀 납치", "밤도깨비 에이브"],
            }
        ]
        pipeline._inject_image_enrichment_blocks(ctx.post_data)
        candidate = DetectedTitle(
            official_title=title,
            heretic_url=url,
            confidence="High",
            alias_or_mention="미소녀 납치",
            source_tier="official_detail",
            page_type="novel_page",
            locked=True,
            reference_role="primary",
        )
        ctx.search_results = [
            {
                "title": title,
                "url": url,
                "content": "#세뇌 #납치 작품 상세",
                "source_tier": "novel_platform",
            }
        ]
        verification_result = {
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "grounding_check": {"anchor_found": "character_mention"},
            "relation_judgment": {
                "relation_type": "work_specific_nickname",
                "discussion_target": "specific_work",
                "promotion_decision": "hold",
                "explicit_alias_bridge_count": 0,
                "post_direct_grounding": False,
            },
        }
        final_decision = {
            "is_resolved_work_discussion": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "context_sources": ["title", "body", "comments", "search", "image"],
            "anchor_type": "title_exact",
            "consistency_flags": [
                "locked_official_candidate_rescued",
                "weak_public_title_bridge_locked_official_exempt",
            ],
        }

        self.assertTrue(pipeline._title_candidate_mentioned(ctx, candidate, include_comments=True))
        self.assertFalse(
            pipeline._has_strict_non_image_candidate_surface(
                ctx,
                title,
                title_candidates=[candidate],
                final_decision=final_decision,
            )
        )
        self.assertTrue(
            pipeline._image_scene_only_candidate_lacks_publish_surface(
                ctx,
                title,
                title_candidates=[candidate],
                final_decision=final_decision,
                verification_result=verification_result,
            )
        )

        decision = pipeline._record_resolved_public_title_gate_decision(
            ctx,
            title,
            candidate_url=url,
            final_decision=final_decision,
            verification_result=verification_result,
            title_candidates=[candidate],
            resolution_scope_fields={
                "is_resolved_work_discussion": True,
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "discussion_type": "character_talk",
                "anchor_type": "title_exact",
                "context_sources": ["title", "body", "comments", "search", "image"],
            },
        )

        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertTrue(decision["candidate_preserved"])
        self.assertFalse(decision["bypassed_gate"])
        self.assertIsNone(decision["official_title"])
        self.assertIsNone(decision["official_url"])
        self.assertIn("image_scope_missing_candidate_surface", decision["reason_codes"])
        self.assertEqual(decision["scope"]["scope_kind"], "context_only")

    def test_image_scene_hold_allows_real_non_image_candidate_alias_surface(self):
        pipeline = build_pipeline()
        title = "미소녀 마개조 부서"
        post = PostInput(
            post_id=21700470,
            title="미소녀 납치 이번화 죄목이 너무 많음",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="image", url="https://dcimg.example/positive.jpg")],
            comments=[],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=[],
        )
        ctx.post_data["image_enrichment"] = [
            {
                "block_index": 0,
                "ocr_text": "작품 속 장면 문장",
                "evidence_type": "explicit_text",
                "title_role": "unknown",
                "promotion_eligible": False,
            }
        ]
        pipeline._inject_image_enrichment_blocks(ctx.post_data)
        candidate = DetectedTitle(
            official_title=title,
            heretic_url="https://novelpia.com/novel/89714",
            confidence="High",
            alias_or_mention="미소녀 납치",
            source_tier="official_detail",
            page_type="novel_page",
        )
        verification_result = {
            "relation_judgment": {
                "promotion_decision": "hold",
                "explicit_alias_bridge_count": 0,
                "post_direct_grounding": False,
            }
        }

        self.assertTrue(
            pipeline._has_strict_non_image_candidate_surface(
                ctx,
                title,
                title_candidates=[candidate],
            )
        )
        self.assertFalse(
            pipeline._image_scene_only_candidate_lacks_publish_surface(
                ctx,
                title,
                title_candidates=[candidate],
                verification_result=verification_result,
            )
        )

    def test_image_scene_llm_promote_and_forged_catalog_cannot_override_provenance(self):
        pipeline = build_pipeline()
        title = "미소녀 마개조 부서"
        post = PostInput(
            post_id=21700471,
            title="어케 주인공 죄목이",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="image", url="https://dcimg.example/scene.jpg")],
            comments=[],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=[],
        )
        ctx.post_data["image_enrichment"] = [
            {
                "block_index": 0,
                "ocr_text": "미소녀를 납치 후 세뇌하는 장면",
                "explicit_work_title": title,
                "evidence_type": "cover_title",
                "title_role": "work_title",
                "focus_role": "work_anchor",
                "screen_type": "text_surface",
                "surface_type": "quoted_text_screenshot",
                "promotion_eligible": False,
            }
        ]
        pipeline._inject_image_enrichment_blocks(ctx.post_data)
        candidate = DetectedTitle(
            official_title=title,
            heretic_url="https://novelpia.com/novel/89714",
            confidence="High",
            alias_or_mention="미소녀 납치",
            source_tier="official_detail",
            page_type="novel_page",
        )
        forged_final = {
            "image_evidence_catalog": [
                {
                    "explicit_work_title": title,
                    "evidence_type": "explicit_text",
                    "title_role": "work_title",
                    "focus_role": "work_anchor",
                    "promotion_eligible": True,
                }
            ]
        }
        verifier_promote = {
            "relation_judgment": {
                "promotion_decision": "promote",
                "explicit_alias_bridge_count": 1,
                "post_direct_grounding": True,
            }
        }

        self.assertFalse(
            pipeline._has_structured_direct_image_work_surface_evidence(ctx, title)
        )
        self.assertTrue(
            pipeline._image_scene_only_candidate_lacks_publish_surface(
                ctx,
                title,
                title_candidates=[candidate],
                final_decision=forged_final,
                verification_result=verifier_promote,
            )
        )
        self.assertFalse(
            pipeline._post_discusses_work_as_work(
                ctx,
                title,
                source="resolved_public_title_scope",
                final_decision=forged_final,
                verification_result=verifier_promote,
                title_candidates=[candidate],
            )
        )

    def test_late_canonical_rescue_skips_image_scene_hold_without_candidate_surface(self):
        pipeline = build_pipeline()
        image_evidence = {
            "ocr_text": (
                "참고인의 모든 변론이 끝났다. 얼굴도 모르는 미소녀를 납치 후, "
                "B급 모험가 '밤'도깨비 에이브가 되어 있었다."
            ),
            "evidence_type": "explicit_text",
            "title_role": "unknown",
            "promotion_eligible": False,
            "work_cues": ["B급 모험가 '밤'도깨비 에이브", "미소녀 납치"],
        }
        post = PostInput(
            post_id=11700470,
            title="어케 주인공 죄목이",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", url="https://dcimg.example/11700470.jpg"),
                ContentBlock(type="text", text="납치담금세뇌테러불법투기셍태계교란희롱준강간"),
            ],
            comments=["교수형"],
        )
        ctx = ConversationContext(
            post_id=11700470,
            post_data=pipeline._post_to_dict(post),
            comments=post.comments,
        )
        ctx.post_data["image_enrichment"] = [dict(image_evidence)]
        ctx.discourse_warning = "decoder_forced_match(3rd_attempt)"
        final_decision = {
            "_title_deliberately_null": True,
            "_title_null_block_reasons": ["image_scope_missing_candidate_surface"],
        }
        verification_result = {
            "relation_judgment": {
                "relation_type": "thematic_overlap_only",
                "promotion_decision": "reject",
            },
            "grounding_check": {"anchor_found": "plot_mention"},
        }

        self.assertTrue(
            pipeline._should_skip_late_canonical_rescue_for_image_scene_hold(
                ctx,
                strong_suspected_title=None,
                title_deliberately_null=True,
                title_null_block_reasons={"image_scope_missing_candidate_surface"},
                direct_strong_suspected_title_support=False,
                final_decision=final_decision,
                verification_result=verification_result,
            )
        )
        self.assertEqual(
            getattr(ctx, "_image_scene_hold_canonical_rescue_skip_reason", None),
            "image_scene_no_candidate_surface",
        )

    def test_late_canonical_rescue_skips_non_promotable_image_partial_title(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11700470,
            title="어케 주인공 죄목이",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", url="https://dcimg.example/11700470.jpg"),
                ContentBlock(type="text", text="납치담금세뇌테러불법투기셍태계교란희롱준강간"),
            ],
            comments=["교수형"],
        )
        ctx = ConversationContext(
            post_id=11700470,
            post_data=pipeline._post_to_dict(post),
            comments=post.comments,
        )
        ctx.post_data["image_enrichment"] = [
            {
                "ocr_text": "B급 모험가 '밤'도깨비 에이브가 되어 있었다.",
                "explicit_work_title": "밤도깨비 에이브",
                "evidence_type": "explicit_text",
                "title_role": "work_title",
                "promotion_eligible": False,
                "work_cues": ["B급 모험가 '밤'도깨비 에이브", "에이브"],
            }
        ]
        ctx.discourse_warning = "decoder_forced_match(3rd_attempt)"
        self.assertTrue(pipeline._title_matches_direct_image_partial(ctx, "밤도깨비"))

        self.assertTrue(
            pipeline._should_skip_late_canonical_rescue_for_image_scene_hold(
                ctx,
                strong_suspected_title="밤도깨비",
                title_deliberately_null=True,
                title_null_block_reasons={"image_scope_missing_candidate_surface"},
                direct_strong_suspected_title_support=False,
                final_decision={
                    "_title_deliberately_null": True,
                    "_title_null_block_reasons": ["image_scope_missing_candidate_surface"],
                },
                verification_result={
                    "relation_judgment": {
                        "relation_type": "thematic_overlap_only",
                        "promotion_decision": "reject",
                    }
                },
            )
        )

    def test_late_canonical_rescue_ignores_llm_convergence_without_local_publish_surface(self):
        pipeline = build_pipeline()
        title = "미소녀 마개조 부서"
        post = PostInput(
            post_id=11700470,
            title="어케 주인공 죄목이",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", url="https://dcimg.example/11700470.jpg"),
                ContentBlock(type="text", text="납치담금세뇌테러불법투기생태계교란희롱준강간"),
            ],
            comments=["교수형"],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=post.comments,
        )
        ctx.post_data["image_enrichment"] = [
            {
                "ocr_text": "얼굴도 모르는 미소녀를 납치 후 B급 모험가 에이브가 되어 있었다.",
                "explicit_work_title": title,
                "evidence_type": "explicit_text",
                "title_role": "work_title",
                "focus_role": "supporting_text",
                "promotion_eligible": False,
                "work_cues": ["미소녀", "에이브"],
            }
        ]
        ctx.discourse_warning = "decoder_forced_match(3rd_attempt)"
        final_decision = {
            "official_title": title,
            "_title_deliberately_null": True,
            "_title_null_block_reasons": ["image_scope_missing_candidate_surface"],
        }
        verification_result = {
            "novel_identity": {"official_title": title},
            "relation_judgment": {
                "relation_type": "thematic_overlap_only",
                "promotion_decision": "hold",
            },
        }

        with (
            patch.object(
                pipeline,
                "_has_strong_verified_character_work_links",
                return_value=True,
            ),
            patch.object(
                pipeline,
                "_has_deliberated_character_setting_work_convergence",
                return_value=True,
            ),
        ):
            self.assertTrue(
                pipeline._should_skip_late_canonical_rescue_for_image_scene_hold(
                    ctx,
                    strong_suspected_title=title,
                    title_deliberately_null=True,
                    title_null_block_reasons={"image_scope_missing_candidate_surface"},
                    # Reproduces the old caller path where LLM convergence made
                    # this broad diagnostic boolean true.
                    direct_strong_suspected_title_support=True,
                    final_decision=final_decision,
                    verification_result=verification_result,
                )
            )

    def test_late_canonical_rescue_keeps_promotable_direct_image_title(self):
        pipeline = build_pipeline()
        title = "전 버튜버가 하고 싶은데요"
        post = PostInput(
            post_id=11663540,
            title="TS) 주서연 전차랑 줄다리기 하면 이길까?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="image", url="https://dcimg.example/11663540.jpg")],
            comments=[],
        )
        ctx = ConversationContext(
            post_id=11663540,
            post_data=pipeline._post_to_dict(post),
            comments=[],
        )
        ctx.post_data["image_enrichment"] = [
            {
                "ocr_text": "ACTOR 아이, 탈의 주인공 전 버튜버가 하고 싶은데요",
                "explicit_work_title": title,
                "evidence_type": "cover_title",
                "title_role": "work_title",
                "focus_role": "work_anchor",
                "screen_type": "work_surface",
                "surface_type": "official_detail_page",
                "promotion_eligible": True,
                "work_cues": [title, "주인공"],
            }
        ]

        self.assertFalse(
            pipeline._should_skip_late_canonical_rescue_for_image_scene_hold(
                ctx,
                strong_suspected_title=title,
                title_deliberately_null=True,
                title_null_block_reasons={"image_scope_missing_candidate_surface"},
                direct_strong_suspected_title_support=False,
                final_decision={"_title_deliberately_null": True},
                verification_result={"relation_judgment": {"promotion_decision": "hold"}},
            )
        )

    def test_image_primary_promotion_rejects_non_boolean_eligibility_values(self):
        pipeline = build_pipeline()
        title = "재벌가 차녀의 2회차 걸그룹"
        for invalid_value in ("false", 0, 1):
            with self.subTest(promotion_eligible=invalid_value):
                post = PostInput(
                    post_id=21718082,
                    title="이게 백합 소설이 아니라니...",
                    author="ㅇㅇ",
                    content_blocks=[ContentBlock(type="text", text="두렵구나")],
                    comments=[],
                )
                post_data = pipeline._post_to_dict(post)
                post_data["image_enrichment"] = [
                    {
                        "evidence_type": "explicit_text",
                        "title_role": "work_title",
                        "focus_role": "work_anchor",
                        "promotion_eligible": invalid_value,
                        "explicit_work_title": title,
                        "explicit_author_name": "유은우",
                    }
                ]
                ctx = ConversationContext(
                    post_id=post.post_id,
                    post_data=post_data,
                    comments=[],
                )

                self.assertFalse(pipeline._has_image_primary_promotion_signal(ctx, title))
                self.assertTrue(
                    pipeline._image_scene_only_candidate_lacks_publish_surface(ctx, title)
                )

    def test_physical_classic_book_cover_without_warning_does_not_rescue_public_title(self):
        pipeline = build_pipeline()
        title = "파우스트 1"
        post = PostInput(
            post_id=11706871,
            title="독후감 쓰려고 파우스트 읽었었는데 결말에서 벙쪘음",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", text=""),
                ContentBlock(type="text", text="갑자기 신이 나타나서 내가 이겼음 악마 너 졌음"),
            ],
            comments=["데우스 엑스 마키나"],
        )
        post_dict = pipeline._post_to_dict(post)
        post_dict["image_enrichment"] = [
            {
                "ocr_text": "세계문학전집 21 파우스트 1 Faust 요한 볼프강 폰 괴테 정서용 옮김 민음사",
                "visual_summary": "고전 문학 도서의 표지 이미지입니다.",
                "explicit_work_title": title,
                "explicit_author_name": "요한 볼프강 폰 괴테",
                "work_cues": [title, "요한 볼프강 폰 괴테", "세계문학전집 21", "민음사"],
                "evidence_type": "cover_title",
                "title_role": "work_title",
                "focus_role": "work_anchor",
                "screen_type": "work_surface",
                "surface_type": "book_cover",
                "promotion_eligible": True,
                "confidence": "High",
            }
        ]
        ctx = ConversationContext(post_id=11706871, post_data=post_dict, comments=post.comments)
        candidate = DetectedTitle(
            official_title=title,
            confidence="High",
            source_tier="llm_only",
            reference_role="candidate",
        )

        self.assertFalse(pipeline._has_image_primary_promotion_signal(ctx, title))
        self.assertFalse(pipeline._has_structured_direct_image_work_surface_evidence(ctx, title))
        self.assertFalse(pipeline._has_ocr_catalog_official_title_evidence(ctx, title))

        picked = pipeline._pick_direct_full_title_candidate_for_hold(
            ctx=ctx,
            title_candidates=[candidate],
            verification_result={"grounding_check": {"anchor_found": "title_mention"}},
        )
        self.assertIsNone(picked)

    def test_memory_query_unsupported_title_uses_valid_output_subtype(self):
        pipeline = build_pipeline()
        title = "망겜의 힐러"
        post = PostInput(
            post_id=11718083,
            title="너에겐 네가 위기에 처했을때",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(
                    type="text",
                    text=(
                        "널 위해 달려와줄 친구가 3명쯤 있다 "
                        "옛날에 무슨 소설에서 본 대사였는데 작품명이 기억 안남"
                    ),
                )
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=11718083, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.search_results = [
            {
                "title": f"{title} - 네이버 시리즈",
                "url": "https://series.naver.com/novel/detail.series?productNo=7774",
                "content": "검색 결과가 제목 단어와만 약하게 겹침",
            }
        ]
        verification_result = {
            "relation_judgment": {"discussion_target": "memory_query"},
            "grounding_check": {"anchor_found": "plot_mention"},
        }

        with patch.object(
            pipeline,
            "_guard_official_title_precision",
            return_value=(title, "High", []),
        ), patch.object(pipeline, "_is_memory_query_without_direct_resolution", return_value=True):
            taxonomy = pipeline._apply_output_consistency_validator(
                ctx=ctx,
                is_relevant=True,
                discussion_type="general",
                official_title=title,
                confidence="High",
                reason="검색 제목 단어가 겹쳐 후보가 올라왔지만 대사 출처 직접 증거는 부족",
                notes=None,
                title_candidates=[],
                primary_work=None,
                mentioned_works=[],
                comparison_target=None,
                recommendation_candidates=[],
                metadata={},
                verification_result=verification_result,
            )

        self.assertFalse(taxonomy["is_relevant"])
        self.assertIsNone(taxonomy["official_title"])
        self.assertEqual(taxonomy["subtype"], "unresolved_work")
        self.assertNotEqual(taxonomy["subtype"], "memory_query")
        self.assertEqual(taxonomy["work_resolution"], "none")
        self.assertEqual(taxonomy["discussion_type"], "undecodable_reference")
        self.assertIn("memory_query_unsupported_title_blocked", taxonomy["consistency_flags"])

    def test_ts_trope_weak_unresolved_uses_trope_discussion_reason(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11718118,
            title="ts물에서 진짜 대협은",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="대놓고 스윗하면 안 되고"),
                ContentBlock(type="text", text="나중에 주인공이랑 이어져도 안됨"),
                ContentBlock(type="text", text="그냥 주인공을 조용히 뒤에서 챙겨주기만 하고"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=11718118, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "express_opinion",
                    "target_kind": "trope",
                    "semantic_seed_review": {
                        "is_specific_work_discussion": False,
                        "content_interpretation": "표현 오타/축약 패턴(범용)",
                    },
                }
            },
        )
        verification_result = {
            "grounding_check": {"anchor_found": "none"},
            "relation_judgment": {
                "discussion_target": "genre_general",
                "relation_type": "genre_or_trope_label",
                "promotion_decision": "reject",
            },
        }

        taxonomy = pipeline._apply_output_consistency_validator(
            ctx=ctx,
            is_relevant=True,
            discussion_type="noise",
            official_title=None,
            confidence="Medium",
            reason="",
            notes=None,
            title_candidates=[],
            primary_work=None,
            mentioned_works=[],
            comparison_target=None,
            recommendation_candidates=[],
            metadata={},
            verification_result=verification_result,
        )

        self.assertFalse(taxonomy["is_relevant"])
        self.assertIsNone(taxonomy["official_title"])
        self.assertEqual(taxonomy["topicality"], "adjacent_relevant")
        self.assertEqual(taxonomy["subtype"], "genre_trope_discussion")
        self.assertEqual(taxonomy["discussion_type"], "trope_discussion")
        self.assertIn("genre_trope_context_only_no_work_anchor", taxonomy["consistency_flags"])
        self.assertNotIn("weak_character_reaction_unresolved_blocked", taxonomy["consistency_flags"])
        self.assertIn("장르/트로프 일반론", taxonomy["reason"])
        self.assertNotIn("핵심 결론: 표현 오타/축약 패턴", taxonomy["reason"])

    def test_acknowledged_previous_work_comment_cannot_steal_direct_body_alias(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11713222,
            title="현대 하렘물은 진짜 잘쓰는 작가가 손에꼽네",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(
                    type="text",
                    text="잘생인방보는데 그냥 주인공이 여자를 오나홀로밖에 안보는거같음",
                )
            ],
            comments=[
                "판타지만 쓰던 작가라서 그런가",
                "전작도 잘생인편으로 현대하렘아님?  - dc App",
                "@ㅇㅇ\n그렇네 잘생인편 안봐서 까먹어버림",
            ],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=post.comments,
        )
        candidate = DetectedTitle(
            official_title="잘생기면 인생이 편하다",
            heretic_url="https://novelpia.com/novel/300042",
            confidence="High",
            alias_or_mention="잘생인편",
            source_tier="official_detail",
            page_type="novel_page",
        )

        can_override = pipeline._acknowledged_previous_work_candidate_can_override_current_lock(
            ctx=ctx,
            current_title="잘생기면 편해지는 인방 생활",
            candidate=candidate,
            verification_result={
                "grounding_check": {
                    "anchor_found": "title_mention",
                    "matched_alias": "잘생인방",
                },
                "relation_judgment": {"observed_aliases": ["잘생인방"]},
                "slang_insight": {"canonical_work_alias": "잘생인방"},
            },
        )

        self.assertFalse(can_override)

        can_override_fast_path = pipeline._acknowledged_previous_work_candidate_can_override_current_lock(
            ctx=ctx,
            current_title="잘생기면 편해지는 인방 생활",
            candidate=candidate,
            verification_result={
                "grounding_check": {
                    "anchor_found": "title_mention",
                    "matched_alias": "잘생인방",
                },
                "relation_judgment": {
                    "relation_type": "explicit_alias",
                    "discussion_target": "specific_work",
                    "promotion_decision": "allow",
                    "observed_aliases": ["잘생인방"],
                },
                "slang_insight": {"canonical_work_alias": "잘생인방"},
            },
            allow_verified_current_alias_bypass=True,
        )

        self.assertFalse(can_override_fast_path)

    def test_final_title_correction_does_not_bypass_direct_body_alias_conflict(self):
        pipeline = build_pipeline()
        current_title = "잘생기면 편해지는 인방 생활"
        current_url = "https://novelpia.com/novel/384016"
        previous_title = "잘생기면 인생이 편하다"
        previous_url = "https://novelpia.com/novel/300042"
        post = PostInput(
            post_id=11713222,
            title="현대 하렘물은 진짜 잘쓰는 작가가 손에꼽네",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(
                    type="text",
                    text="잘생인방보는데 그냥 주인공이 여자를 오나홀로밖에 안보는거같음",
                )
            ],
            comments=[
                "전작도 잘생인편으로 현대하렘아님?",
                "@ㅇㅇ\n그렇네 잘생인편 안봐서 까먹어버림",
            ],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=post.comments,
        )
        ctx.search_results = [
            {
                "title": f"웹소설로 꿈꾸는 세상! - {previous_title} - 노벨피아",
                "url": previous_url,
                "content": f"{previous_title} 작가 민트초코주먹밥.",
            }
        ]
        verification_result = {
            "grounding_check": {
                "anchor_found": "title_mention",
                "matched_alias": "잘생인방",
            },
            "relation_judgment": {
                "relation_type": "explicit_alias",
                "discussion_target": "specific_work",
                "promotion_decision": "allow",
                "observed_aliases": ["잘생인방"],
            },
            "slang_insight": {"canonical_work_alias": "잘생인방"},
            "novel_identity": {
                "official_title": current_title,
                "heretic_url": current_url,
                "confidence": "High",
            },
        }
        ctx.set_expert_output(ExpertType.VERIFIER, {"verification_result": verification_result})

        with patch.object(
            pipeline,
            "_safe_official_detail_url_for_title",
            side_effect=lambda *args, **kwargs: kwargs.get("candidate_url") or "",
        ):
            corrected = pipeline._correct_title_final(current_title, ctx)
            taxonomy = pipeline._apply_output_consistency_validator(
                ctx=ctx,
                is_relevant=True,
                discussion_type="review",
                official_title=corrected,
                confidence="High",
                reason="본문 alias는 현재 작품이고 댓글 alias는 전작 후보",
                notes=None,
                title_candidates=[
                    DetectedTitle(
                        official_title=current_title,
                        heretic_url=current_url,
                        confidence="High",
                        alias_or_mention="잘생인방",
                        source_tier="official_detail",
                        page_type="novel_page",
                        reference_role="primary",
                    )
                ],
                primary_work=DetectedTitle(
                    official_title=current_title,
                    heretic_url=current_url,
                    confidence="High",
                    alias_or_mention="잘생인방",
                    source_tier="official_detail",
                    page_type="novel_page",
                    reference_role="primary",
                ),
                mentioned_works=[],
                comparison_target=None,
                recommendation_candidates=[],
                metadata={},
                verification_result=verification_result,
            )

        self.assertEqual(corrected, current_title)
        self.assertNotEqual(corrected, previous_title)
        self.assertFalse(hasattr(ctx, "_acknowledged_previous_work_comment_override_title"))
        self.assertEqual(taxonomy["official_title"], current_title)
        self.assertIn("acknowledged_previous_work_candidate_preserved", taxonomy["consistency_flags"])
        preserved_titles = set()
        for row in taxonomy.get("mentioned_works") or []:
            if isinstance(row, dict):
                preserved_titles.add(row.get("official_title"))
            else:
                preserved_titles.add(getattr(row, "official_title", None))
        self.assertIn(previous_title, preserved_titles)

    def test_multi_work_previous_comment_keeps_direct_body_alias_primary(self):
        pipeline = build_pipeline()
        current_title = "잘생기면 편해지는 인방 생활"
        current_url = "https://novelpia.com/novel/384016"
        previous_title = "잘생기면 인생이 편하다"
        previous_url = "https://novelpia.com/novel/300042"
        post = PostInput(
            post_id=11713222,
            title="현대 하렘물은 진짜 잘쓰는 작가가 손에꼽네",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(
                    type="text",
                    text="잘생인방보는데 그냥 주인공이 여자를 오나홀로밖에 안보는거같음",
                )
            ],
            comments=[
                "판타지만 쓰던 작가라서 그런가",
                "전작도 잘생인편으로 현대하렘아님?",
                "@ㅇㅇ\n그렇네 잘생인편 안봐서 까먹어버림",
            ],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=post.comments,
        )
        current = DetectedTitle(
            official_title=current_title,
            heretic_url=current_url,
            confidence="High",
            alias_or_mention="잘생인방",
            source_tier="official_detail",
            page_type="novel_page",
            reference_role="primary",
        )
        previous = DetectedTitle(
            official_title=previous_title,
            heretic_url=previous_url,
            confidence="High",
            alias_or_mention="잘생인편",
            source_tier="official_detail",
            page_type="novel_page",
            reference_role="mentioned",
        )
        verification_result = {
            "grounding_check": {
                "anchor_found": "title_mention",
                "matched_alias": "잘생인방",
            },
            "relation_judgment": {
                "relation_type": "explicit_alias",
                "discussion_target": "specific_work",
                "promotion_decision": "allow",
                "observed_aliases": ["잘생인방"],
            },
            "slang_insight": {"canonical_work_alias": "잘생인방"},
            "novel_identity": {
                "official_title": current_title,
                "heretic_url": current_url,
                "confidence": "High",
            },
        }

        with patch.object(
            pipeline,
            "_guard_official_title_precision",
            return_value=(current_title, "High", []),
        ), patch.object(
            pipeline,
            "_safe_official_detail_url_for_title",
            side_effect=lambda *args, **kwargs: kwargs.get("candidate_url") or "",
        ):
            taxonomy = pipeline._apply_output_consistency_validator(
                ctx=ctx,
                is_relevant=True,
                discussion_type="review",
                official_title=current_title,
                confidence="High",
                reason="본문 별칭은 현재 작품, 댓글 별칭은 전작 후보",
                notes=None,
                title_candidates=[current, previous],
                primary_work=current,
                mentioned_works=[previous],
                comparison_target=previous,
                recommendation_candidates=[],
                metadata={},
                verification_result=verification_result,
            )

        self.assertEqual(taxonomy["official_title"], current_title)
        self.assertEqual(taxonomy["heretic_url"], current_url)
        self.assertEqual(taxonomy["work_resolution"], "resolved")
        self.assertNotIn("acknowledged_previous_work_comment_override", taxonomy["consistency_flags"])
        self.assertIn("direct_current_alias_primary_preserved", taxonomy["consistency_flags"])

    def test_acknowledged_previous_work_scope_lock_recovers_final_decision_from_context(self):
        pipeline = build_pipeline()
        title = "잘생기면 인생이 편하다"
        url = "https://novelpia.com/novel/384016"
        post = PostInput(
            post_id=11713222,
            title="현대 하렘물은 진짜 잘쓰는 작가가 손에꼽네",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="전작이랑 같은 작품이라고 댓글에서 인정됨")],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        final_decision = {"discussion_type": "noise", "heretic_url": url}
        ctx.set_expert_output(ExpertType.ARBITER, {"final_decision": final_decision})
        setattr(ctx, "_acknowledged_previous_work_comment_override_url", url)

        with patch.object(
            pipeline,
            "_guard_official_title_precision",
            return_value=(title, "High", []),
        ), patch.object(
            pipeline,
            "_acknowledged_previous_work_comment_override_locks_title",
            return_value=True,
        ):
            taxonomy = pipeline._apply_output_consistency_validator(
                ctx=ctx,
                is_relevant=True,
                discussion_type="noise",
                official_title=title,
                confidence="High",
                reason="댓글에서 전작 언급을 인정",
                notes=None,
                title_candidates=[],
                primary_work=DetectedTitle(
                    official_title=title,
                    heretic_url=url,
                    confidence="High",
                ),
                mentioned_works=[],
                comparison_target=None,
                recommendation_candidates=[],
                metadata={},
                verification_result={
                    "grounding_check": {"anchor_found": "title_mention"},
                    "novel_identity": {"official_title": title, "heretic_url": url},
                },
            )

        self.assertTrue(taxonomy["is_relevant"])
        self.assertEqual(taxonomy["official_title"], title)
        self.assertEqual(taxonomy["work_resolution"], "resolved")
        self.assertIn("acknowledged_previous_work_scope_resolved", taxonomy["consistency_flags"])
        self.assertEqual(final_decision["official_title"], title)
        self.assertEqual(final_decision["work_resolution"], "resolved")

    def test_verifier_counter_argument_blocks_generic_setting_public_title_promotion(self):
        pipeline = build_pipeline()
        title = "SSS급 운빨로 무한 레벨업"
        post = PostInput(
            post_id=11713212,
            title="지력 무한일 때 가장 효과 좋은 작물이 머임",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(
                    type="text",
                    text="절대 SSS급 지력무한 영지를 손에 넣었다 를 쓰려는 건 아니고",
                )
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.discourse_warning = "discuss_genre(high)"

        with patch.object(
            pipeline,
            "_guard_official_title_precision",
            return_value=(title, "High", []),
        ):
            taxonomy = pipeline._apply_output_consistency_validator(
                ctx=ctx,
                is_relevant=True,
                discussion_type="general",
                official_title=title,
                confidence="High",
                reason="검색 결과에 공식 작품이 있으나 게시글은 가상 설정 질문",
                notes=None,
                title_candidates=[
                    DetectedTitle(
                        official_title=title,
                        heretic_url="https://novel.munpia.com/383628",
                        confidence="High",
                        source_tier="official_detail",
                        reference_role="primary",
                    )
                ],
                primary_work=DetectedTitle(
                    official_title=title,
                    heretic_url="https://novel.munpia.com/383628",
                    confidence="High",
                    source_tier="official_detail",
                    reference_role="primary",
                ),
                mentioned_works=[],
                comparison_target=None,
                recommendation_candidates=[],
                metadata={},
                verification_result={
                    "counter_arguments": [
                        {
                            "severity": "critical",
                            "reason": "본문의 '지력 무한'은 특정 작품의 제목이 아닌 일반적인 설정/트로프임",
                        },
                        {
                            "severity": "major",
                            "reason": "작성자가 '쓰려는 건 아니고'라고 명시하며 가상의 상황을 가정함",
                        },
                    ],
                    "grounding_check": {"anchor_found": "title_mention"},
                },
            )

        self.assertFalse(taxonomy["is_relevant"])
        self.assertIsNone(taxonomy["official_title"])
        self.assertEqual(taxonomy["work_resolution"], "none")
        self.assertEqual(taxonomy["discussion_type"], "trope_discussion")
        self.assertIn("verifier_counter_title_promotion_blocked", taxonomy["consistency_flags"])

    def test_ts_trope_context_only_guard_runs_without_surface_reread_signal(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11718118,
            title="ts물에서 진짜 대협은",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="대놓고 스윗하면 안 되고"),
                ContentBlock(type="text", text="나중에 주인공이랑 이어져도 안됨"),
                ContentBlock(type="text", text="웃으며 마음 접고 떠나주는 게 찐 대협인듯"),
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=11718118, post_data=pipeline._post_to_dict(post), comments=[])
        verification_result = {"grounding_check": {"anchor_found": "none"}}

        taxonomy = pipeline._apply_output_consistency_validator(
            ctx=ctx,
            is_relevant=False,
            discussion_type="off_topic",
            official_title=None,
            confidence="Low",
            reason="제목-본문 연속문이며 저특이 제목 후보만 존재하는 커뮤니티 잡담 패턴",
            notes=None,
            title_candidates=[],
            primary_work=None,
            mentioned_works=[],
            comparison_target=None,
            recommendation_candidates=[],
            metadata={},
            verification_result=verification_result,
        )

        self.assertFalse(taxonomy["is_relevant"])
        self.assertEqual(taxonomy["topicality"], "adjacent_relevant")
        self.assertEqual(taxonomy["subtype"], "genre_trope_discussion")
        self.assertEqual(taxonomy["discussion_type"], "trope_discussion")
        self.assertIn("genre_trope_context_only_no_work_anchor", taxonomy["consistency_flags"])
        self.assertNotIn("weak_character_reaction_unresolved_blocked", taxonomy["consistency_flags"])
        self.assertIn("장르/트로프 일반론", taxonomy["reason"])

    def test_character_surface_reread_weak_unresolved_uses_undecodable_reason(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11718091,
            title="소신발언)) 은영이 23센줄 몰랐음",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="묘사만 보면 한 16살인줄???")],
            comments=["ㄹㅇ 머리도 안올렷잖아 더어린줄"],
        )
        post_data = pipeline._post_to_dict(post)
        post_data["comment_metadata"] = [
            {
                "comment_id": "40479972",
                "author": "ㅇㅇ",
                "speaker": "user1",
                "is_post_author": False,
                "post_author_match_unverified": True,
            }
        ]
        ctx = ConversationContext(post_id=11718091, post_data=post_data, comments=post.comments)
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "community_banter",
                    "semantic_seed_review": {
                        "is_specific_work_discussion": False,
                        "content_interpretation": "표현 오타/축약 패턴(범용)",
                    },
                }
            },
        )
        verification_result = {
            "grounding_check": {"anchor_found": "none"},
            "relation_judgment": {
                "discussion_target": "community_banter",
                "promotion_decision": "reject",
            },
        }

        taxonomy = pipeline._apply_output_consistency_validator(
            ctx=ctx,
            is_relevant=True,
            discussion_type="noise",
            official_title=None,
            confidence="Medium",
            reason="",
            notes=None,
            title_candidates=[],
            primary_work=None,
            mentioned_works=[],
            comparison_target=None,
            recommendation_candidates=[],
            metadata={},
            verification_result=verification_result,
        )

        self.assertFalse(taxonomy["is_relevant"])
        self.assertIsNone(taxonomy["official_title"])
        self.assertEqual(taxonomy["topicality"], "unrelated")
        self.assertEqual(taxonomy["subtype"], "unresolved_work")
        self.assertEqual(taxonomy["discussion_type"], "undecodable_reference")
        self.assertIn("weak_character_reaction_unresolved_blocked", taxonomy["consistency_flags"])
        self.assertIn("comment_author_match_unverified_not_independent_evidence", taxonomy["consistency_flags"])
        self.assertIn("캐릭터·나이·외형 반응", taxonomy["reason"])
        self.assertNotIn("핵심 결론: 표현 오타/축약 패턴", taxonomy["reason"])

    def test_no_work_direct_image_candidate_requires_canonical_resolved_state(self):
        pipeline = build_pipeline()
        title = "재벌가 차녀의 2회차 걸그룹"
        post = PostInput(
            post_id=11718082,
            title="이게 백합 소설이 아니라니...",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="두렵구나")],
            comments=[],
        )
        post_dict = pipeline._post_to_dict(post)
        post_dict["image_enrichment"] = [
            {
                "evidence_type": "explicit_text",
                "title_role": "work_title",
                "focus_role": "work_anchor",
                "promotion_eligible": True,
                "explicit_work_title": title,
                "explicit_author_name": "유은우",
            }
        ]
        ctx = ConversationContext(post_id=11718082, post_data=post_dict, comments=[])
        mark_no_work_seed(ctx)

        self.assertFalse(
            pipeline._can_promote_title_after_semantic_no_work(
                ctx,
                title,
                source="unit_test_direct_image",
                verification_result={},
            )
        )

    def test_batch_context_wrapper_passes_resolution_fields_before_learning(self):
        batch_context = BatchContextMemory(enabled=True)
        pipeline = AgenticPipeline(
            llm=DummyLLM(),
            mcp=DummyMCP(),
            max_iterations=2,
            batch_context=batch_context,
        )
        post = PostInput(
            post_id=11718080,
            title="망겜힐 같이 볼 친구 있었으면",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="작품 특정 없이 소설 같이 볼 친구 얘기")],
            comments=[],
        )
        ctx = ConversationContext(post_id=11718080, post_data=pipeline._post_to_dict(post), comments=[])
        result = PickvelOutputItemV2(
            post_id=11718080,
            identity=PickvelIdentity(
                is_relevant=True,
                title_resolution_state="context_only",
                title_resolution_allowed=False,
                novel_identity=NovelIdentity(official_title="망겜의 힐러", confidence="High"),
                discussion_type="community_banter",
                subtype="daily_life",
                work_resolution="none",
                anchor_type="none",
                consistency_flags=["semantic_seed_review_specific_work_denied"],
                slang_insight=SlangInsight(
                    detected_term="망겜힐",
                    decoded_term="망겜의 힐러",
                    canonical_work_alias="망겜힐",
                    store_in_slang_db=True,
                ),
            ),
        )

        pipeline._learn_batch_context(ctx, result)

        self.assertIsNone(batch_context.get_abbreviation("망겜힐"))
        self.assertNotIn("망겜힐", batch_context.resolved_abbreviations)
        self.assertNotIn("망겜힐", batch_context.pending_abbreviations)

    def test_session_knowledge_skips_context_only_result_without_direct_anchor(self):
        pipeline = build_pipeline()
        title = "망겜의 힐러"
        post = PostInput(
            post_id=11718080,
            title="망겜힐 같이 볼 친구 있었으면",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="같이 소설 볼 친구 얘기라 특정 작품 감상은 아님")],
            comments=[],
        )
        ctx = ConversationContext(post_id=11718080, post_data=pipeline._post_to_dict(post), comments=[])
        result = PickvelOutputItemV2(
            post_id=11718080,
            identity=PickvelIdentity(
                is_relevant=True,
                title_resolution_state="context_only",
                title_resolution_allowed=False,
                novel_identity=NovelIdentity(official_title=title, confidence="High"),
                discussion_type="community_banter",
                subtype="daily_life",
                work_resolution="none",
                anchor_type="none",
                consistency_flags=["semantic_seed_review_specific_work_denied"],
                slang_insight=SlangInsight(
                    detected_term="망겜힐",
                    decoded_term=title,
                    canonical_work_alias="망겜힐",
                    store_in_slang_db=True,
                ),
            ),
        )

        with patch.object(
            pipeline,
            "_compute_title_commitment",
            return_value={
                "score": 15,
                "official_evidence": True,
                "title_in_context": True,
                "bucket_score": 5,
            },
        ), patch.object(pipeline, "_is_title_commitment_medium", return_value=True), patch.object(
            pipeline,
            "_is_title_commitment_strong",
            return_value=True,
        ), patch.object(pipeline, "_has_official_title_evidence", return_value=True), patch.object(
            pipeline,
            "_title_mentioned_in_post_main_context",
            return_value=True,
        ):
            pipeline._update_session_knowledge(ctx, result)

        slang_key = pipeline._normalize_match_text("망겜힐")
        self.assertNotIn(slang_key, pipeline.session_knowledge.get("resolved_slang", {}))
        self.assertNotIn(slang_key, pipeline.session_knowledge.get("pending_slang", {}))

    def test_image_ocr_variant_reason_does_not_overstate_title_in_post(self):
        pipeline = build_pipeline()
        official = "재벌가 차녀의 2회차 걸그룹"
        ocr_variant = "제벨가 차녀의 2회차 결그룹"
        ctx = ConversationContext(
            post_id=11718082,
            post_data={
                "post_id": 11718082,
                "title": "이거 제목 뭐였지",
                "content_blocks": [{"type": "ocr_text", "text": ocr_variant}],
                "vlm_enrichment_used": True,
                "image_enrichment": [
                    {
                        "evidence_type": "explicit_text",
                        "explicit_work_title": ocr_variant,
                        "title_role": "work_title",
                        "promotion_eligible": True,
                    }
                ],
            },
            comments=[],
        )
        ctx.search_results = [
            {
                "title": "재벌가 차녀의 2회차 걸그룹 - 웹소설 - 카카오페이지",
                "url": "https://page.kakao.com/content/66692543",
                "content": "유은우. 재벌가 차녀의 2회차 걸그룹 267화.",
            }
        ]
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "decoded_terms": [
                    {
                        "original": ocr_variant,
                        "best_match": {"title": official},
                    }
                ]
            },
        )

        reason = pipeline._format_relevant_reason(
            discussion_type="character_talk",
            official_title=official,
            verifier_reason="이미지 OCR과 공식 검색 결과를 함께 확인",
            arbiter_reason="공식 URL 근거로 최종 제목을 정리",
            grounding_issue="",
            counter_arguments=[],
            ctx=ctx,
            verification_result={
                "grounding_check": {"anchor_found": "image"},
                "novel_identity": {"evidence_type": "image_ocr"},
            },
        )

        self.assertIn("- title_in_post: false", reason)
        self.assertIn("- image_ocr_variant: true", reason)
        self.assertIn("- official_search_resolution: true", reason)
        score_reason = "\n".join(
            pipeline._build_reason_scoreboard_lines(
                ctx=ctx,
                is_relevant=True,
                official_title=official,
                heretic_url="https://page.kakao.com/content/66692543",
                discussion_type="character_talk",
                verification_result={
                    "grounding_check": {"anchor_found": "image"},
                    "novel_identity": {"evidence_type": "image_ocr"},
                },
                final_decision=None,
            )
        )
        self.assertNotIn("title_in_post: +2", score_reason)
        self.assertIn("이미지 OCR 변형은 원문 직접 제목 언급과 분리", score_reason)
        taxonomy = pipeline._derive_output_taxonomy(
            ctx=ctx,
            is_relevant=True,
            discussion_type="character_talk",
            official_title=official,
            title_candidates=[],
            primary_work=None,
            mentioned_works=[],
            comparison_target=None,
            recommendation_candidates=[],
            metadata={},
            verification_result={
                "grounding_check": {"anchor_found": "image"},
                "novel_identity": {"evidence_type": "image_ocr"},
            },
        )
        self.assertEqual("image", taxonomy.get("anchor_type"))

        cleaned = pipeline._sanitize_slang_cultural_context_for_image_conflict(
            "게시글 제목에 사용된 축약어/오타로 보임",
            ctx=ctx,
            official_title=official,
        )
        self.assertNotIn("게시글 제목에 사용된", cleaned or "")
        self.assertIn("이미지 OCR/표지에서 감지된", cleaned or "")

        runtime_like = pipeline._sanitize_slang_cultural_context_for_image_conflict(
            (
                "원문에서 사용된 '제벨가'는 검색 결과를 통해 '재벌가'로 해석되었으며, "
                "이는 일반적인 한국어 오타/표기 오류로 간주된다. "
                "'결그룹'은 '걸그룹'의 오타 또는 약칭으로 판단된다. "
                "이 단어들은 해당 소설의 고유 명칭에 해당한다."
            ),
            ctx=ctx,
            official_title=official,
        )
        self.assertNotIn("일반적인 한국어 오타/표기 오류", runtime_like or "")
        self.assertNotIn("오타 또는 약칭", runtime_like or "")
        self.assertIn("packet-local OCR/표기 변형", runtime_like or "")
        self.assertIn("지속 별칭이나 전역 오타 규칙으로 저장하지 않는다", runtime_like or "")

        v455_like = pipeline._sanitize_slang_cultural_context_for_image_conflict(
            (
                "게시글에서 사용된 '제벨가'는 검색 결과와 '재벌가'로 해석되었으며, "
                "이는 작품의 고유 명칭으로 추정된다. "
                "'결그룹'은 '걸그룹'의 오타 또는 약칭으로 판단된다. "
                "이 단어들은 해당 작품의 제목을 구성하는 핵심 요소이다."
            ),
            ctx=ctx,
            official_title=official,
        )
        self.assertNotIn("게시글에서 사용된", v455_like or "")
        self.assertNotIn("작품의 고유 명칭", v455_like or "")
        self.assertNotIn("오타 또는 약칭", v455_like or "")
        self.assertNotIn("제목을 구성하는 핵심 요소", v455_like or "")
        self.assertIn("이미지 OCR/표지에서 감지된", v455_like or "")
        self.assertIn("packet-local 작품 식별 단서", v455_like or "")
        self.assertIn("지속 별칭이나 전역 오타 규칙으로 저장하지 않는다", v455_like or "")

        v456_like = pipeline._sanitize_slang_cultural_context_for_image_conflict(
            (
                "게시글 제목과 본문 내용(OCR)에 등장하는 '결그룹'은 검색 결과에서 "
                "'걸그룹'으로 정정되었으며, 이는 해당 작품의 공식적인 제목으로 확인됨."
            ),
            ctx=ctx,
            official_title=official,
        )
        self.assertNotIn("게시글 제목과 본문 내용", v456_like or "")
        self.assertNotIn("공식적인 제목으로 확인", v456_like or "")
        self.assertIn("이미지 OCR/표지에서 감지된", v456_like or "")
        self.assertIn("packet-local OCR/표기 변형 단서", v456_like or "")

        v457_like = pipeline._sanitize_slang_cultural_context_for_image_conflict(
            (
                "제목에 사용된 '제벨가'는 검색 결과에서 '재벌가'로 정정되었으며, "
                "이는 일반적인 오타 또는 축약으로 판단된다."
            ),
            ctx=ctx,
            official_title=official,
        )
        self.assertNotIn("제목에 사용된", v457_like or "")
        self.assertNotIn("일반적인 오타 또는 축약", v457_like or "")
        self.assertIn("이미지 OCR/표지에서 감지된", v457_like or "")
        self.assertIn("packet-local OCR/표기 변형 단서", v457_like or "")

        v459_like = pipeline._sanitize_slang_cultural_context_for_image_conflict(
            (
                "이미지 OCR을 통해 특정 웹소설의 일부를 인용한 것으로, "
                "'재벌가', '차녀', '결그룹' 등의 키워드를 통해 작품의 설정을 언급하고 있습니다. "
                "이미지 OCR/표지에서 감지된 '제벨가 차녀의 2회차 결그룹'은 "
                "공식 제목 '재벌가 차녀의 2회차 걸그룹'의 비표준적인 커뮤니티 약칭 또는 OCR 오인으로 추정된다. "
                "이는 해당 작품의 줄거리(캐릭터 간의 관계)를 언급하는 데 사용되었다."
            ),
            ctx=ctx,
            official_title=official,
        )
        self.assertNotIn("특정 웹소설의 일부를 인용", v459_like or "")
        self.assertNotIn("작품의 설정", v459_like or "")
        self.assertNotIn("비표준적인 커뮤니티 약칭", v459_like or "")
        self.assertNotIn("OCR 오인", v459_like or "")
        self.assertNotIn("작품의 줄거리", v459_like or "")
        self.assertNotIn("캐릭터 간의 관계", v459_like or "")
        self.assertIn("이미지 OCR/표지에서 텍스트 표면과 작품 단서", v459_like or "")
        self.assertIn("packet-local OCR/표기 변형 단서", v459_like or "")
        self.assertIn("이미지 본문 장면과 작품 식별을 보조", v459_like or "")

    def test_ocr_only_title_reason_does_not_claim_official_search_evidence(self):
        pipeline = build_pipeline()
        title = "여대생 가랑이 사이 무릎 끓은 엄마들"
        ctx = ConversationContext(
            post_id=11716480,
            post_data={
                "post_id": 11716480,
                "title": "아오 포티햄",
                "content_blocks": [
                    {"type": "image", "url": "https://example.invalid/image.jpg"},
                    {"type": "ocr_text", "text": f"{title} 작가명 후타보로 조회 335 추천 14 회차 4회차"},
                ],
                "vlm_enrichment_used": True,
                "image_enrichment": [
                    {
                        "evidence_type": "explicit_text",
                        "explicit_work_title": title,
                        "explicit_author_name": "후타보로",
                        "title_role": "work_title",
                        "focus_role": "work_anchor",
                        "promotion_eligible": True,
                        "ocr_text": f"{title} 작가명 후타보로 조회 335 추천 14 회차 4회차",
                        "work_cues": ["조회 335", "추천 14", "회차 4회차"],
                    }
                ],
            },
            comments=[],
        )
        ctx.search_results = []

        reason = pipeline._format_relevant_reason(
            discussion_type="review",
            official_title=title,
            verifier_reason="OCR에서 작품 상세를 확인",
            arbiter_reason="OCR 근거로 작품명 후보 유지",
            grounding_issue="",
            counter_arguments=[],
            ctx=ctx,
            verification_result={
                "grounding_check": {"anchor_found": "title_mention"},
                "novel_identity": {"evidence_type": "search_platform_url"},
            },
        )

        self.assertIn("- evidence_type: image_ocr_title", reason)
        self.assertIn("- image_ocr_title_evidence: true", reason)
        self.assertIn("- official_title_evidence: false", reason)
        self.assertNotIn("- official_search_resolution: true", reason)
        self.assertIn("source hygiene", reason)

        score_reason = "\n".join(
            pipeline._build_reason_scoreboard_lines(
                ctx=ctx,
                is_relevant=True,
                official_title=title,
                heretic_url=None,
                discussion_type="review",
                verification_result={
                    "grounding_check": {"anchor_found": "title_mention"},
                    "novel_identity": {"evidence_type": "search_platform_url"},
                },
                final_decision=None,
            )
        )
        self.assertIn("image_ocr_title_evidence", score_reason)
        self.assertNotIn("official_title_evidence: +3", score_reason)

    def test_author_anchor_conflict_preserves_character_parenthetical_ocr_correction(self):
        pipeline = build_pipeline()
        title = "전 버튜버가 하고 싶은데요"
        post = PostInput(
            post_id=11663540,
            title="TS) 주서연 전차랑 줄다리기 하면 이길까?",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="내가 봤을땐 이 고릴라년이 가볍게 이길것 같은데")
            ],
            comments=[],
        )
        post_dict = pipeline._post_to_dict(post)
        post_dict["image_enrichment"] = [
            {
                "evidence_type": "cover_title",
                "title_role": "unknown",
                "focus_role": "work_anchor",
                "screen_type": "work_surface",
                "surface_type": "quoted_text_screenshot",
                "promotion_eligible": True,
                "explicit_work_title": "전 버두비가 하고 싶은데요",
                "ocr_text": "ACTOR JU SEO YEON 노블피아 COVER STORY 주서연 단독 인터뷰 전 버두비가 하고 싶은데요",
                "work_cues": ["노블피아", "주서연"],
            }
        ]
        ctx = ConversationContext(post_id=11663540, post_data=post_dict, comments=[])
        ctx.search_results = [
            {
                "title": "주서연(전 버튜버가 하고 싶은데요) - 나무위키",
                "url": "https://namu.wiki/w/주서연(전%20버튜버가%20하고%20싶은데요)",
                "content": "주서연은 전 버튜버가 하고 싶은데요의 주인공이다.",
            },
            {
                "title": "전 버튜버가 하고 싶은데요 - 나무위키",
                "url": "https://namu.wiki/w/전%20버튜버가%20하고%20싶은데요",
                "content": "작가 플라나리아햄버거. 주서연.",
            },
        ]

        self.assertTrue(pipeline._has_specific_character_parenthetical_work_link(ctx, title))
        self.assertTrue(pipeline._should_preserve_title_against_author_anchor_conflict(ctx, title))

    def test_direct_image_ocr_variant_uses_public_character_parenthetical_title(self):
        pipeline = build_pipeline()
        title = "전 버튜버가 하고 싶은데요"
        post = PostInput(
            post_id=11663540,
            title="TS) 주서연 전차랑 줄다리기 하면 이길까?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="image", url="https://dcimg.example/11663540.jpg")],
            comments=[
                "주서연이 클리로 줄다리기해야 아슬아슬하게 대결 성립됨",
                "전차 주제에 주서연이랑 비비려하네",
            ],
        )
        post_dict = pipeline._post_to_dict(post)
        post_dict["image_enrichment"] = [
            {
                "evidence_type": "cover_title",
                "title_role": "unknown",
                "focus_role": "work_anchor",
                "screen_type": "work_surface",
                "surface_type": "quoted_text_screenshot",
                "promotion_eligible": False,
                "explicit_work_title": "전 버두바가 하고 싶으데요",
                "ocr_text": "ACTOR JU SEO YEON COVER STORY 전 버두바가 하고 싶으데요",
                "visual_summary": "노벨피아 웹소설 표지 이미지이며 작품명이 크게 보임",
                "work_cues": ["노벨피아", "주서연"],
                "confidence": "Max",
            }
        ]
        ctx = ConversationContext(post_id=11663540, post_data=post_dict, comments=post.comments)
        ctx.search_results = [
            {
                "title": "주서연(전 버튜버가 하고 싶은데요) - 나무위키",
                "url": "https://namu.wiki/w/주서연(전%20버튜버가%20하고%20싶은데요)",
                "content": "주서연은 전 버튜버가 하고 싶은데요의 주인공이다.",
            }
        ]

        image_candidate = pipeline._pick_promotable_direct_image_work_title_candidate(ctx)
        self.assertIsNotNone(image_candidate)
        self.assertEqual(image_candidate.official_title, title)
        self.assertIn("public canonical variant", image_candidate.alias_or_mention)
        self.assertTrue(pipeline._has_ocr_catalog_official_title_evidence(ctx, title))

        no_bridge_ctx = ConversationContext(post_id=11663540, post_data=post_dict, comments=post.comments)
        no_bridge_ctx.search_results = []
        no_bridge_candidate = pipeline._pick_promotable_direct_image_work_title_candidate(no_bridge_ctx)
        self.assertIsNotNone(no_bridge_candidate)
        self.assertEqual(no_bridge_candidate.official_title, "전 버두바가 하고 싶으데요")
        self.assertNotIn("public canonical variant", no_bridge_candidate.alias_or_mention)

    def test_direct_image_rescue_rejects_non_promotable_brand_sign_cover_anchor(self):
        pipeline = build_pipeline()
        title = "吉野家 (요시노야)"
        post = PostInput(
            post_id=11671500,
            title="말투 바뀌는 거 악살싶에서는 호평받았었는데",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", url="https://dcimg.example/11671500.jpg"),
                ContentBlock(type="text", text="흠"),
            ],
            comments=["그때도 말투강제 자체는 막 만장일치 호평까진 아니엇음"],
        )
        post_dict = pipeline._post_to_dict(post)
        post_dict["image_enrichment"] = [
            {
                "evidence_type": "cover_title",
                "title_role": "unknown",
                "focus_role": "work_anchor",
                "screen_type": "work_surface",
                "surface_type": "quoted_text_screenshot",
                "promotion_eligible": False,
                "explicit_work_title": title,
                "ocr_text": "吉野家 YOSHINOYA",
                "visual_summary": (
                    "밤 시간대, 밝게 빛나는 요시노야 음식점 앞을 배경으로 "
                    "교복을 입은 소녀들이 서 있는 애니메이션 스타일 일러스트"
                ),
                "work_cues": ["요시노야(Yoshinoya) 간판", "애니메이션 스타일 일러스트"],
                "confidence": "High",
            }
        ]
        ctx = ConversationContext(post_id=11671500, post_data=post_dict, comments=post.comments)

        self.assertEqual(pipeline._collect_direct_image_titles(ctx), [title])
        self.assertIsNone(pipeline._pick_promotable_direct_image_work_title_candidate(ctx))
        self.assertFalse(pipeline._has_image_primary_promotion_signal(ctx, title))

    def test_final_precision_demotes_community_only_alias_title_without_official_detail(self):
        pipeline = build_pipeline()
        title = "아카데미 생존 갤러리"
        post = PostInput(
            post_id=11694035,
            title="아생갤) 가장 무서웠던 순간이",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="폐허가 된 도심지라면 현생 서사가 대체 어떻게 되길래")
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=11694035, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.search_results = [
            {
                "title": "<아생갤>의 구조에 대한 분석 - 장르소설 마이너 갤러리",
                "url": "https://gall.dcinside.com/mgallery/board/view/?id=genrenovel&no=1",
                "source_tier": "community",
                "content": "<아생갤>, 아카데미 생존 갤러리는 어떤 작품인가?",
            },
            {
                "title": "아생갤 오늘자가 웃긴게 - 장르소설 마이너 갤러리",
                "url": "https://gall.dcinside.com/mgallery/board/view/?id=genrenovel&no=2",
                "source_tier": "community",
                "content": "아생갤이 노벨피아의 특정 웹소설이라는 커뮤니티 언급",
            },
        ]
        candidate = DetectedTitle(
            official_title=title,
            confidence="High",
            source_tier="community",
            reference_role="primary",
        )

        profile = pipeline._final_precision_title_demote_profile(
            ctx=ctx,
            official_title=title,
            verification_result={
                "novel_identity": {"official_novel_title": title, "evidence_type": "community_mention"},
                "grounding_check": {"anchor_found": "title_mention"},
                "relation_judgment": {
                    "discussion_target": "community_banter",
                    "promotion_decision": "hold",
                },
            },
            consistency_flags=["expert_conflict", "budget_quarantine_candidate"],
            primary_work=candidate,
            title_candidates=[candidate],
        )

        self.assertTrue(profile["demote"])
        self.assertEqual(profile["flag"], "track_b_precision_demoted_community_only_title")
        self.assertEqual(profile["reason"], "community_only_title_without_official_detail")

    def test_final_precision_preserves_community_alias_title_with_official_detail(self):
        pipeline = build_pipeline()
        title = "아카데미 생존 갤러리"
        post = PostInput(
            post_id=11694035,
            title="아생갤) 가장 무서웠던 순간이",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="폐허가 된 도심지라면 현생 서사가 대체 어떻게 되길래")
            ],
            comments=[],
        )
        ctx = ConversationContext(post_id=11694035, post_data=pipeline._post_to_dict(post), comments=[])
        official_url = "https://novelpia.com/novel/123456"
        ctx.search_results = [
            {
                "title": "웹소설로 꿈꾸는 세상! - 아카데미 생존 갤러리 - 노벨피아",
                "url": official_url,
                "source_tier": "novel_platform",
                "content": "아카데미 생존 갤러리 작품 상세",
            }
        ]
        candidate = DetectedTitle(
            official_title=title,
            heretic_url=official_url,
            confidence="High",
            source_tier="official_detail",
            reference_role="primary",
        )

        profile = pipeline._final_precision_title_demote_profile(
            ctx=ctx,
            official_title=title,
            heretic_url=official_url,
            verification_result={
                "novel_identity": {"official_novel_title": title, "evidence_type": "community_mention"},
                "grounding_check": {"anchor_found": "title_mention"},
                "relation_judgment": {
                    "discussion_target": "specific_work",
                    "promotion_decision": "promote",
                },
            },
            consistency_flags=["expert_conflict", "budget_quarantine_candidate"],
            primary_work=candidate,
            title_candidates=[candidate],
        )

        self.assertFalse(profile["demote"])

    def test_freeze_prefers_primary_reference_over_alias_surface_neighbor(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11658637,
            title="재막아)영기는 진짜 답이 없구나",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="진양철이 윤기 좋아하는 이유가 있다"),
            ],
            comments=["살인까지 종용한 놈이니 에휴"],
        )
        post_dict = pipeline._post_to_dict(post)
        post_dict["image_enrichment"] = [
            {
                "promotion_eligible": True,
                "evidence_type": "cover_title",
                "focus_role": "work_anchor",
                "title_role": "work_title",
                "screen_type": "work_surface",
                "surface_type": "episode_reader_page",
                "explicit_work_title": "재벌집 막내아들",
                "ocr_text": "재벌집 막내아들 · 474화 산경(山景) SERIES",
                "work_cues": ["재벌집 막내아들", "산경", "SERIES"],
            }
        ]
        ctx = ConversationContext(post_id=11658637, post_data=post_dict, comments=post.comments)
        noisy = DetectedTitle(
            official_title="일본 재벌집 막내아들",
            heretic_url="https://ridibooks.com/books/3586025015",
            confidence="High",
            alias_or_mention="재벌집 막내아들",
            source_tier="official_detail",
            page_type="novel_page",
            locked=True,
            reference_role="candidate",
        )
        primary = DetectedTitle(
            official_title="재벌집 막내아들",
            heretic_url="https://series.naver.com/novel/detail.series?productNo=4340987",
            confidence="High",
            alias_or_mention="재막아",
            source_tier="official_detail",
            page_type="novel_page",
            locked=True,
            reference_role="primary",
        )

        frozen = pipeline._freeze_identity_references(
            ctx=ctx,
            is_relevant=True,
            official_title="일본 재벌집 막내아들",
            heretic_url="https://ridibooks.com/books/3586025015",
            confidence="High",
            topicality="core_relevant",
            work_resolution="resolved",
            title_candidates=[noisy, primary],
            primary_work=noisy,
            mentioned_works=[],
            comparison_target=None,
            recommendation_candidates=[],
            future_watch_target=None,
            anchor_type="title_mention",
            consistency_flags=[],
        )

        self.assertEqual(frozen["official_title"], "재벌집 막내아들")
        self.assertEqual(
            frozen["heretic_url"],
            "https://series.naver.com/novel/detail.series?productNo=4340987",
        )
        self.assertIn(
            "primary_reference_candidate_preferred_over_alias_surface",
            frozen["consistency_flags"],
        )

    def test_freeze_prefers_primary_reference_when_ocr_work_cue_matches_alias(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11677913,
            title="남캐일러 뽑아도 된다고",
            author="메이즈",
            content_blocks=[
                ContentBlock(type="text", text="이런거 하라고"),
                ContentBlock(type="text", text="허리 얇은데도 게이같지 않잖아"),
            ],
            comments=["게2", "솔직히 저것도 썸네일 BL로 바꾸면....", "캇트한테면 박혀도 좋아"],
        )
        post_dict = pipeline._post_to_dict(post)
        post_dict["image_enrichment"] = [
            {
                "promotion_eligible": True,
                "evidence_type": "cover_title",
                "focus_role": "work_anchor",
                "title_role": "unknown",
                "screen_type": "work_surface",
                "surface_type": "quoted_text_screenshot",
                "explicit_work_title": "천마 (天魔)",
                "ocr_text": "天魔 김 캇 트 이세계 검은머리 외국인",
                "work_cues": ["천마", "김 캇 트", "이세계 검은머리 외국인"],
            }
        ]
        ctx = ConversationContext(post_id=11677913, post_data=post_dict, comments=post.comments)
        noisy = DetectedTitle(
            official_title="이세계 검은머리 똥양인",
            heretic_url="https://novelpia.com/novel/6090",
            confidence="High",
            alias_or_mention="이세계 검은 머리 외국인",
            source_tier="official_detail",
            page_type="novel_page",
            locked=True,
            reference_role="candidate",
        )
        primary = DetectedTitle(
            official_title="이세계 검은 머리 외국인",
            heretic_url="https://novelpia.com/novel/1082",
            confidence="High",
            alias_or_mention="이세계 검은머리 외국인",
            source_tier="official_detail",
            page_type="novel_page",
            reference_role="primary",
        )

        frozen = pipeline._freeze_identity_references(
            ctx=ctx,
            is_relevant=True,
            official_title="이세계 검은머리 똥양인",
            heretic_url="https://novelpia.com/novel/6090",
            confidence="High",
            topicality="core_relevant",
            work_resolution="resolved",
            title_candidates=[noisy, primary],
            primary_work=noisy,
            mentioned_works=[],
            comparison_target=None,
            recommendation_candidates=[],
            future_watch_target=None,
            anchor_type="title_alias",
            consistency_flags=[],
        )

        self.assertEqual(frozen["official_title"], "이세계 검은 머리 외국인")
        self.assertEqual(frozen["heretic_url"], "https://novelpia.com/novel/1082")
        self.assertIn(
            "primary_reference_candidate_preferred_over_alias_surface",
            frozen["consistency_flags"],
        )

    def test_freeze_keeps_alias_surface_when_final_title_is_direct_image_title(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11658637,
            title="직접 이미지 제목",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="이미지 직접 제목을 말함")],
            comments=[],
        )
        post_dict = pipeline._post_to_dict(post)
        post_dict["image_enrichment"] = [
            {
                "promotion_eligible": True,
                "evidence_type": "cover_title",
                "focus_role": "work_anchor",
                "title_role": "work_title",
                "screen_type": "work_surface",
                "surface_type": "episode_reader_page",
                "explicit_work_title": "일본 재벌집 막내아들",
                "ocr_text": "일본 재벌집 막내아들 1화",
                "work_cues": ["일본 재벌집 막내아들"],
            }
        ]
        ctx = ConversationContext(post_id=11658637, post_data=post_dict, comments=[])
        noisy = DetectedTitle(
            official_title="일본 재벌집 막내아들",
            heretic_url="https://ridibooks.com/books/3586025015",
            confidence="High",
            alias_or_mention="재벌집 막내아들",
            source_tier="official_detail",
            page_type="novel_page",
            locked=True,
            reference_role="candidate",
        )
        primary = DetectedTitle(
            official_title="재벌집 막내아들",
            heretic_url="https://series.naver.com/novel/detail.series?productNo=4340987",
            confidence="High",
            source_tier="official_detail",
            page_type="novel_page",
            reference_role="primary",
        )

        frozen = pipeline._freeze_identity_references(
            ctx=ctx,
            is_relevant=True,
            official_title="일본 재벌집 막내아들",
            heretic_url="https://ridibooks.com/books/3586025015",
            confidence="High",
            topicality="core_relevant",
            work_resolution="resolved",
            title_candidates=[noisy, primary],
            primary_work=noisy,
            mentioned_works=[],
            comparison_target=None,
            recommendation_candidates=[],
            future_watch_target=None,
            anchor_type="title_mention",
            consistency_flags=[],
        )

        self.assertEqual(frozen["official_title"], "일본 재벌집 막내아들")
        self.assertNotIn(
            "primary_reference_candidate_preferred_over_alias_surface",
            frozen["consistency_flags"],
        )

    def test_freeze_does_not_promote_blog_review_suffix_over_official_detail_title(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11677913,
            title="남캐일러 뽑아도 된다고",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="이런거 하라고")],
            comments=["캇트한테면 박혀도 좋아"],
        )
        post_dict = pipeline._post_to_dict(post)
        post_dict["image_enrichment"] = [
            {
                "promotion_eligible": True,
                "evidence_type": "explicit_text",
                "focus_role": "work_anchor",
                "title_role": "work_title",
                "screen_type": "work_surface",
                "surface_type": "quoted_text_screenshot",
                "explicit_work_title": "이세계 검은 머리 외국인",
                "ocr_text": "천마 김캇트 이세계 검은머리 외국인",
                "work_cues": ["천마", "김캇트", "이세계 검은머리 외국인"],
            }
        ]
        ctx = ConversationContext(post_id=11677913, post_data=post_dict, comments=post.comments)
        ctx.search_results = [
            {
                "rank": 1,
                "source_rank": 1,
                "title": "웹소설로 꿈꾸는 세상! - 이세계 검은 머리 외국인 - 노벨피아",
                "url": "https://novelpia.com/novel/1082",
                "content": "작가 김갈비뼈. 주인공 김캇트.",
            },
            {
                "rank": 4,
                "source_rank": 4,
                "title": "[웹소설]이세계 검은 머리 외국인 감상중 - 네이버 블로그",
                "url": "https://m.blog.naver.com/kkkkk095/222379348010",
                "content": "노벨피아에서 독점 연재중.",
            },
        ]
        ctx.fetched_page_info = [
            {
                "url": "https://novelpia.com/novel/1082",
                "structured_info": {
                    "page_type": "novel_page",
                    "content_status": "active",
                    "title": "이세계 검은 머리 외국인",
                    "author": "김갈비뼈",
                },
            }
        ]
        primary = DetectedTitle(
            official_title="이세계 검은 머리 외국인",
            heretic_url="https://novelpia.com/novel/1082",
            confidence="High",
            alias_or_mention="검은머리 외국인",
            source_tier="official_detail",
            page_type="novel_page",
            content_status="active",
            locked=True,
            reference_role="primary",
        )

        frozen = pipeline._freeze_identity_references(
            ctx=ctx,
            is_relevant=True,
            official_title="이세계 검은 머리 외국인",
            heretic_url="https://novelpia.com/novel/1082",
            confidence="High",
            topicality="core_relevant",
            work_resolution="resolved",
            title_candidates=[primary],
            primary_work=primary,
            mentioned_works=[],
            comparison_target=None,
            recommendation_candidates=[],
            future_watch_target=None,
            anchor_type="title_alias",
            consistency_flags=[],
        )

        self.assertEqual(frozen["official_title"], "이세계 검은 머리 외국인")
        self.assertEqual(frozen["heretic_url"], "https://novelpia.com/novel/1082")
        self.assertNotIn(
            "search_supported_title_preferred_over_surface_form",
            frozen["consistency_flags"],
        )

    def test_freeze_does_not_promote_author_volume_wrapper_over_ocr_title(self):
        pipeline = build_pipeline()
        title = "재벌집 막내아들"
        munpia_url = "https://m.munpia.com/novel/detail/69583"
        post = PostInput(
            post_id=11658637,
            title="재막아)영기는 진짜 답이 없구나",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="순양전기 계약서")],
            comments=["살인까지 종용한 놈이니 에휴"],
        )
        post_dict = pipeline._post_to_dict(post)
        post_dict["image_enrichment"] = [
            {
                "promotion_eligible": True,
                "evidence_type": "explicit_text",
                "focus_role": "work_anchor",
                "title_role": "work_title",
                "screen_type": "work_surface",
                "surface_type": "quoted_text_screenshot",
                "explicit_work_title": title,
                "explicit_author_name": "산경",
                "ocr_text": "재벌집 막내아들 · 474화 산경(山景) SERIES",
                "work_cues": [title, "순양전기", "영기"],
            }
        ]
        ctx = ConversationContext(post_id=11658637, post_data=post_dict, comments=post.comments)
        ctx.search_results = [
            {
                "rank": 1,
                "source_rank": 1,
                "title": "재벌집 막내아들 - 문피아 웹소설",
                "url": munpia_url,
                "content": "작가 산경. 직장인, 샐러리맨이라고 부르지만 사실은 머슴이다.",
            },
            {
                "rank": 8,
                "source_rank": 8,
                "title": "산경 <재벌집 막내아들1> - 네이버 블로그",
                "url": "https://m.blog.naver.com/animus98/223066135082",
                "content": "재벌집 막내아들 1권 감상.",
            },
        ]
        ctx.fetched_page_info = [
            {
                "url": munpia_url,
                "structured_info": {
                    "page_type": "novel_page",
                    "content_status": "active",
                    "title": title,
                    "author": "산경",
                },
            }
        ]
        primary = DetectedTitle(
            official_title=title,
            heretic_url=munpia_url,
            confidence="High",
            alias_or_mention="재막아",
            source_tier="official_detail",
            page_type="novel_page",
            content_status="active",
            locked=True,
            reference_role="primary",
        )

        frozen = pipeline._freeze_identity_references(
            ctx=ctx,
            is_relevant=True,
            official_title=title,
            heretic_url=munpia_url,
            confidence="High",
            topicality="core_relevant",
            work_resolution="resolved",
            title_candidates=[primary],
            primary_work=primary,
            mentioned_works=[],
            comparison_target=None,
            recommendation_candidates=[],
            future_watch_target=None,
            anchor_type="title_alias",
            consistency_flags=[],
        )

        self.assertEqual(frozen["official_title"], title)
        self.assertEqual(frozen["heretic_url"], munpia_url)
        self.assertNotIn(
            "search_supported_title_preferred_over_surface_form",
            frozen["consistency_flags"],
        )

    def test_final_precision_preserves_community_alias_title_with_contextual_detail_lock(self):
        pipeline = build_pipeline()
        title = "이세계에서 사이비로 살아남기"
        post = PostInput(
            post_id=11694019,
            title="리바이벌 이거 사이비 맞냐",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="공식 상세 검색으로 리바이벌 alias가 닫힌 케이스")],
            comments=[],
        )
        ctx = ConversationContext(post_id=11694019, post_data=pipeline._post_to_dict(post), comments=[])
        candidate = DetectedTitle(
            official_title=title,
            confidence="High",
            source_tier="community",
            reference_role="primary",
        )

        with patch.object(pipeline, "_has_contextual_alias_official_detail_lock", return_value=True):
            profile = pipeline._final_precision_title_demote_profile(
                ctx=ctx,
                official_title=title,
                verification_result={
                    "novel_identity": {"official_novel_title": title, "evidence_type": "community_mention"},
                    "grounding_check": {"anchor_found": "search_only", "matched_alias": "리바이벌"},
                    "relation_judgment": {
                        "discussion_target": "community_banter",
                        "promotion_decision": "hold",
                        "observed_aliases": ["리바이벌"],
                    },
                },
                consistency_flags=["expert_conflict", "budget_quarantine_candidate"],
                primary_work=candidate,
                title_candidates=[candidate],
            )

        self.assertFalse(profile["demote"])

    def test_discuss_genre_anchor_accepts_verified_public_work_detail_lock(self):
        pipeline = build_pipeline()
        title = "탐식의 재림"
        post = PostInput(
            post_id=11705231,
            title="장갤 설지후 변화도 레전드임",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="설지후 캐릭터 변화 이야기")],
            comments=[],
        )
        ctx = ConversationContext(post_id=11705231, post_data=pipeline._post_to_dict(post), comments=[])
        ctx.verified_character_work_links = [
            {
                "title": title,
                "character": "설지후",
                "url": "https://page.kakao.com/content/12345678",
            }
        ]

        self.assertTrue(
            pipeline._has_discuss_genre_specific_work_anchor(
                ctx,
                title,
                {"grounding_check": {"anchor_found": "none"}},
            )
        )

    def test_source_evidence_seed_rows_reach_initial_search_results(self):
        pipeline = build_pipeline()
        title = "탐식의 재림"
        post = PostInput(
            post_id=11705231,
            title="장갤 설지후 변화도 레전드임",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="설지후 캐릭터 변화 이야기")],
            comments=[],
            native_web_seed={
                "official_title": title,
                "urls": [
                    "https://page.kakao.com/content/50219568",
                    "https://page.kakao.com/content/50219568?tab_type=comment",
                    "https://series.naver.com/novel/detail.series?productNo=2847498",
                ],
            },
        )

        post_data = pipeline._post_to_dict(post)
        seeded = Orchestrator._source_evidence_search_results_from_post_data(post_data)
        urls = {item.get("url") for item in seeded}
        titles = {item.get("title") for item in seeded}

        self.assertIn("https://page.kakao.com/content/50219568", urls)
        self.assertIn("https://series.naver.com/novel/detail.series?productNo=2847498", urls)
        self.assertEqual(len(seeded), 2)
        self.assertTrue(any(title in str(seed_title or "") for seed_title in titles))

        ctx = ConversationContext(post_id=11705231, post_data=post_data, comments=[])
        self.assertEqual(ctx.add_search_results(seeded), 2)
        self.assertEqual(ctx.search_results[0]["_evidence_id"], "E001")

    def test_multi_work_collapse_ignores_pruned_llm_sentence_comparison_under_public_lock(self):
        pipeline = build_pipeline()
        title = "이세계에서 사이비로 살아남기"
        post = PostInput(
            post_id=11694019,
            title="미츄리 혼후순결에서 하인들에게도 멸시당한게 고증에 맞는거였구나",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="아내가 혼후순결 요구해서 하인들도 멸시하는 설정 얘기")
            ],
            comments=["부부는 아니고 간소화된 입양 같은 걸로"],
        )
        ctx = ConversationContext(post_id=11694019, post_data=pipeline._post_to_dict(post), comments=post.comments)
        candidate = DetectedTitle(
            official_title=title,
            heretic_url="https://namu.wiki/w/이세계에서%20사이비로%20살아남기",
            confidence="High",
            source_tier="llm_only",
            reference_role="primary",
        )
        comparison = DetectedTitle(
            official_title="부부는 아니고 간소화된 입양 같은 걸로",
            confidence="Medium",
            source_tier="llm_only",
            reference_role="mentioned",
        )

        with patch.object(
            pipeline,
            "_guard_official_title_precision",
            return_value=(title, "High", ["llm_only_sentence_candidate_pruned"]),
        ), patch.object(
            pipeline,
            "_derive_output_taxonomy",
            return_value={
                "topicality": "core_relevant",
                "subtype": "multi_work_compare",
                "work_resolution": "multi_work",
                "anchor_type": "title_exact",
                "anchor_strength": "high",
            },
        ), patch.object(
            pipeline,
            "_derive_primary_subject_interpretation",
            return_value={},
        ), patch.object(
            pipeline,
            "_has_verified_public_work_detail_lock",
            return_value=True,
        ), patch.object(
            pipeline,
            "_can_promote_title_after_semantic_no_work",
            return_value=True,
        ):
            taxonomy = pipeline._apply_output_consistency_validator(
                ctx=ctx,
                is_relevant=True,
                discussion_type="character_talk",
                official_title=title,
                confidence="High",
                reason="특정 작품 설정 논의",
                notes=None,
                title_candidates=[candidate],
                primary_work=candidate,
                mentioned_works=[],
                comparison_target=comparison,
                recommendation_candidates=[],
                metadata={},
                verification_result={
                    "grounding_check": {"anchor_found": "plot_mention"},
                    "relation_judgment": {
                        "relation_type": "work_specific_nickname",
                        "discussion_target": "specific_work",
                        "promotion_decision": "hold",
                    },
                },
            )

        self.assertTrue(taxonomy["is_relevant"])
        self.assertEqual(taxonomy["official_title"], title)
        self.assertEqual(taxonomy["work_resolution"], "resolved")
        self.assertIn("multi_work_placeholder_collapsed", taxonomy["consistency_flags"])
        self.assertIn("weak_llm_only_sentence_comparison_ignored", taxonomy["consistency_flags"])

    def test_multi_work_guard_preserves_explicit_alias_official_lock(self):
        pipeline = build_pipeline()
        title = "잘생기면 인생이 편하다"
        post = PostInput(
            post_id=11713222,
            title="현대 하렘물은 진짜 잘쓰는 작가가 손에꼽네",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="잘생인방보는데 그냥 주인공이 여자를 도구로만 보는거같음")
            ],
            comments=["전작도 잘생인편으로 현대하렘아님?", "그렇네 잘생인편 안봐서 까먹어버림"],
        )
        ctx = ConversationContext(post_id=11713222, post_data=pipeline._post_to_dict(post), comments=post.comments)
        ctx.search_results = [
            {
                "title": "웹소설로 꿈꾸는 세상! - 잘생기면 인생이 편하다 - 노벨피아",
                "url": "https://novelpia.com/novel/300042",
                "source_tier": "official_detail",
                "content": "플러스작품 - 잘생기면 인생이 편하다",
            }
        ]
        ctx.set_expert_output(
            ExpertType.SYNTHESIZER,
            {
                "hidden_references": [
                    {
                        "text": "잘생인방",
                        "reference_type": "title",
                        "matched_to": title,
                    },
                    {
                        "text": "잘생인편",
                        "reference_type": "title",
                        "matched_to": title,
                    },
                ]
            },
        )
        candidate = DetectedTitle(
            official_title=title,
            heretic_url="https://novelpia.com/novel/300042",
            confidence="Max",
            source_tier="official_detail",
            reference_role="primary",
        )

        with patch.object(
            pipeline,
            "_guard_official_title_precision",
            return_value=(title, "Max", []),
        ), patch.object(
            pipeline,
            "_derive_output_taxonomy",
            return_value={
                "topicality": "core_relevant",
                "subtype": "multi_work_compare",
                "work_resolution": "multi_work",
                "anchor_type": "title_alias",
                "anchor_strength": "high",
            },
        ), patch.object(
            pipeline,
            "_derive_primary_subject_interpretation",
            return_value={},
        ), patch.object(
            pipeline,
            "_has_verified_public_work_detail_lock",
            return_value=True,
        ), patch.object(
            pipeline,
            "_final_title_rejection_profile",
            return_value={"reject": False},
        ):
            taxonomy = pipeline._apply_output_consistency_validator(
                ctx=ctx,
                is_relevant=True,
                discussion_type="recommendation",
                official_title=title,
                confidence="Max",
                reason="명시 약칭과 공식 URL이 같은 작품으로 수렴",
                notes=None,
                title_candidates=[candidate],
                primary_work=candidate,
                mentioned_works=[],
                comparison_target=DetectedTitle(
                    official_title="잘생인편",
                    confidence="Medium",
                    source_tier="community",
                    reference_role="mentioned",
                ),
                recommendation_candidates=[],
                metadata={},
                verification_result={
                    "is_relevant": True,
                    "is_novel_discussion": True,
                    "novel_identity": {
                        "official_novel_title": title,
                        "heretic_url": "https://novelpia.com/novel/300042",
                        "evidence_type": "search_platform_url",
                    },
                    "grounding_check": {
                        "anchor_found": "title_mention",
                        "matched_alias": "잘생인방",
                        "title_abbrev_mentioned": True,
                        "body_abbrev_mentioned": True,
                    },
                    "slang_insight": {
                        "detected_term": "잘생인방",
                        "canonical_work_alias": "잘생인편",
                    },
                    "relation_judgment": {
                        "relation_type": "explicit_alias",
                        "discussion_target": "specific_work",
                        "promotion_decision": "allow",
                        "observed_aliases": ["잘생인방", "잘생인편"],
                    },
                },
            )

        self.assertTrue(taxonomy["is_relevant"])
        self.assertEqual(taxonomy["official_title"], title)
        self.assertEqual(taxonomy["work_resolution"], "resolved")
        self.assertEqual(taxonomy["subtype"], "resolved_work")
        self.assertIn("multi_work_explicit_alias_official_lock", taxonomy["consistency_flags"])
        self.assertNotIn("multi_work_title_cleared", taxonomy["consistency_flags"])
        self.assertNotIn("recommendation_context_only_no_work_anchor", taxonomy["consistency_flags"])

    def test_weak_bridge_keeps_verified_alias_official_detail_relation(self):
        pipeline = build_pipeline()
        title = "이세계 검은 머리 외국인"
        url = "https://novelpia.com/novel/1082"
        post = PostInput(
            post_id=11677913,
            title="남캐일러 뽑아도 된다고",
            author="메이즈",
            content_blocks=[
                ContentBlock(type="image", url="https://example.test/katt.png"),
                ContentBlock(type="text", text="이런거 하라고"),
            ],
            comments=["캇트한테면 박혀도 좋아"],
        )
        post_data = pipeline._post_to_dict(post)
        post_data["image_enrichment"] = [
            {
                "promotion_eligible": True,
                "evidence_type": "explicit_text",
                "focus_role": "work_anchor",
                "title_role": "work_title",
                "screen_type": "work_surface",
                "surface_type": "fanart_or_character_illustration",
                "explicit_work_title": "천마",
                "ocr_text": "천마 김 캇 트 이세계 검은머리 외국인",
                "work_cues": ["천마", "김 캇 트", "이세계 검은머리 외국인"],
            }
        ]
        ctx = ConversationContext(post_id=11677913, post_data=post_data, comments=post.comments)
        ctx.search_results = [
            {
                "title": "이세계 검은 머리 외국인",
                "url": url,
                "content": "노벨피아 작품. 작가 김갈비뼈. 주인공 김캇트.",
            }
        ]
        candidate = DetectedTitle(
            official_title=title,
            heretic_url=url,
            confidence="High",
            alias_or_mention="천마 김 캇 트 이세계 검은머리 외국인",
            source_tier="official_detail",
            page_type="novel_page",
            reference_role="primary",
        )

        with patch.object(
            pipeline,
            "_guard_official_title_precision",
            return_value=(title, "High", []),
        ), patch.object(
            pipeline,
            "_derive_output_taxonomy",
            return_value={
                "topicality": "core_relevant",
                "subtype": "resolved_work",
                "work_resolution": "resolved",
                "anchor_type": "title_alias",
                "anchor_strength": "high",
            },
        ), patch.object(
            pipeline,
            "_derive_primary_subject_interpretation",
            return_value={},
        ), patch.object(
            pipeline,
            "_final_title_rejection_profile",
            return_value={"reject": False},
        ):
            taxonomy = pipeline._apply_output_consistency_validator(
                ctx=ctx,
                is_relevant=True,
                discussion_type="character_talk",
                official_title=title,
                confidence="High",
                reason="OCR와 댓글의 캇트 언급이 공식 작품 상세와 연결됨",
                notes=None,
                title_candidates=[candidate],
                primary_work=candidate,
                mentioned_works=[],
                comparison_target=None,
                recommendation_candidates=[],
                metadata={},
                verification_result={
                    "is_relevant": True,
                    "is_novel_discussion": True,
                    "novel_identity": {
                        "official_novel_title": title,
                        "heretic_url": url,
                        "evidence_type": "search_platform_url",
                    },
                    "grounding_check": {
                        "anchor_found": "character_mention",
                        "matched_alias": "천마 김 캇 트 이세계 검은머리 외국인",
                    },
                    "relation_judgment": {
                        "relation_type": "explicit_alias",
                        "discussion_target": "specific_work",
                        "promotion_decision": "allow",
                        "confidence": "high",
                    },
                },
            )

        self.assertTrue(taxonomy["is_relevant"])
        self.assertEqual(taxonomy["official_title"], title)
        self.assertEqual(taxonomy["work_resolution"], "resolved")
        self.assertNotIn("promoted_image_work_title_conflicts_with_public_title", taxonomy["consistency_flags"])


    def test_work_abbreviation_is_not_generic_character_parenthetical_provenance(self):
        pipeline = build_pipeline()
        title = "가챠 중독자의 퓨전펑크 생활"
        ctx = ConversationContext(
            post_id=11698880,
            post_data={"post_id": 11698880, "title": "아생갤 개 존나게 재밌군"},
            comments=[],
        )
        ctx.verified_character_work_links = [
            {"title": title, "abbreviation": "가챠펑크"}
        ]

        self.assertFalse(
            pipeline._has_generic_character_parenthetical_bridge(ctx, title)
        )

        ctx.verified_character_work_links = [
            {"title": title, "character": "세드릭", "abbreviation": "가챠펑크"}
        ]
        self.assertTrue(
            pipeline._has_generic_character_parenthetical_bridge(ctx, title)
        )

    def test_title_led_body_primary_does_not_require_headline_official_url(self):
        pipeline = build_pipeline()
        headline_title = "아카데미 생존 갤러리"
        body_title = "가챠 중독자의 퓨전펑크 생활"
        body_url = "https://novelpia.com/novel/387014"
        post = PostInput(
            post_id=11698880,
            title="아생갤 개 존나게 재밌군 ㅇㅇ",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="가챠펑크 세드릭도 그렇고"),
                ContentBlock(type="text", text="시원시원한 상남자라서 너무 좋구나"),
            ],
            comments=[],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=[],
        )
        ctx.verified_character_work_links = [
            {
                "title": body_title,
                "url": body_url,
                "character": "세드릭",
                "abbreviation": "가챠펑크",
                "alias": "가챠펑크",
                "matched_alias": "가챠펑크",
            }
        ]
        ctx.search_results = [
            {"title": body_title, "url": body_url, "content": "가챠펑크 세드릭 등장"},
        ]
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "work_discussion",
                "detected_entities": {"possible_titles": ["아생갤", "가챠펑크"]},
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "discuss_work",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                    "title_novel_terms": ["아생갤", "가챠펑크"],
                }
            },
        )
        candidates = [
            DetectedTitle(
                official_title=headline_title,
                confidence="Medium",
                alias_or_mention="아생갤",
                source_tier="mixed",
                reference_role="candidate",
            ),
            DetectedTitle(
                official_title=body_title,
                heretic_url=body_url,
                confidence="High",
                alias_or_mention="가챠펑크",
                source_tier="official_detail",
                page_type="novel_page",
                reference_role="primary",
            ),
        ]
        final_decision = {
            "official_title": body_title,
            "primary_work": {"official_title": body_title},
            "discussion_type": "general",
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
        }
        verification_result = {
            "novel_identity": {
                "official_novel_title": body_title,
                "heretic_url": body_url,
            },
            "primary_work": {"official_title": body_title},
        }

        candidate = pipeline._pick_title_led_evaluation_official_candidate(
            ctx,
            title_candidates=candidates,
            final_decision=final_decision,
            verification_result=verification_result,
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.official_title, body_title)
        self.assertEqual(candidate.heretic_url, body_url)
        self.assertTrue(ctx._title_led_body_primary_candidate_selected)
        self.assertEqual(ctx._title_led_headline_context_candidate_title, headline_title)

    def test_title_led_body_primary_ignores_comment_only_other_work_alias(self):
        pipeline = build_pipeline()
        headline_title = "아카데미 생존 갤러리"
        headline_url = "https://novelpia.com/novel/380218"
        body_title = "가챠 중독자의 퓨전펑크 생활"
        body_url = "https://novelpia.com/novel/387014"
        post = PostInput(
            post_id=21698883,
            title="아생갤 개 존나게 재밌군 ㅇㅇ",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="시원시원해서 좋음")],
            comments=["가챠펑크 세드릭도 괜찮더라"],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=post.comments,
        )
        ctx.verified_character_work_links = [
            {
                "title": body_title,
                "url": body_url,
                "character": "세드릭",
                "abbreviation": "가챠펑크",
                "alias": "가챠펑크",
            }
        ]
        ctx.search_results = [
            {"title": headline_title, "url": headline_url, "content": "작품 상세"},
            {"title": body_title, "url": body_url, "content": "가챠펑크 작품 상세"},
        ]
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "work_discussion",
                "detected_entities": {"possible_titles": ["아생갤"]},
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "discuss_work",
                    "primary_domain": "novel_literature",
                    "title_novel_terms": ["아생갤"],
                }
            },
        )
        headline = DetectedTitle(
            official_title=headline_title,
            heretic_url=headline_url,
            confidence="High",
            alias_or_mention="아생갤",
            source_tier="official_detail",
            page_type="novel_page",
            reference_role="primary",
        )
        other = DetectedTitle(
            official_title=body_title,
            heretic_url=body_url,
            confidence="High",
            alias_or_mention="가챠펑크",
            source_tier="official_detail",
            page_type="novel_page",
            reference_role="primary",
        )

        candidate = pipeline._pick_title_led_evaluation_official_candidate(
            ctx,
            title_candidates=[headline, other],
            primary_work=other,
            final_decision={"official_title": body_title, "primary_work": {"official_title": body_title}},
            verification_result={"novel_identity": {"official_novel_title": body_title}},
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.official_title, headline_title)
        self.assertFalse(getattr(ctx, "_title_led_body_primary_candidate_selected", False))

    def test_exact_current_title_lock_ignores_unrelated_manga_search_competitor(self):
        pipeline = build_pipeline()
        title = "테라포밍"
        url = "https://novelpia.com/novel/61947"
        post = PostInput(
            post_id=11660237,
            title="테라포밍 볼만함?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="주인공 멍청하다는 말 많던데")],
            comments=[],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=[],
        )
        ctx.search_results = [
            {
                "title": title,
                "url": url,
                "content": "노벨피아 웹소설 작품 상세",
                "query": "테라포밍 노벨피아",
            },
            {
                "title": "테라포마스 - 만화 e북 - 리디",
                "url": "https://ridibooks.com/books/1019005884",
                "content": "화성 테라포밍이 진행되는 만화 e북",
                "query": "시리즈 테라포밍 작가",
            },
        ]
        candidate = DetectedTitle(
            official_title=title,
            heretic_url=url,
            confidence="High",
            alias_or_mention=title,
            source_tier="official_detail",
            page_type="novel_page",
            locked=True,
            reference_role="primary",
        )
        verification_result = {
            "is_relevant": True,
            "is_novel_discussion": True,
            "novel_identity": {"official_novel_title": title, "heretic_url": url},
            "grounding_check": {
                "anchor_found": "title_exact",
                "title_abbrev_mentioned": True,
                "matched_alias": title,
            },
            "relation_judgment": {
                "relation_type": "explicit_alias",
                "discussion_target": "specific_work",
                "promotion_decision": "allow",
            },
        }

        decision = pipeline._record_title_led_alias_public_title_gate_decision(
            ctx,
            title,
            candidate_url=url,
            final_decision={
                "discussion_type": "review",
                "work_resolution": "resolved",
                "title_resolution_state": "resolved",
            },
            verification_result=verification_result,
            title_candidates=[candidate],
            acceptance={"decision": "accept", "title_led_consumption_bridge": True, "score": 30},
        )

        self.assertEqual(decision["status"], "publish")
        self.assertTrue(decision["publish_allowed"])
        self.assertEqual(decision["official_title"], title)
        self.assertFalse(decision["bypassed_gate"])
        self.assertNotIn(
            "title_led_alias_contextual_official_detail_competes",
            decision["reason_codes"],
        )
        self.assertIn(
            "exact_current_title_official_detail_lock",
            ctx._last_promotion_gate_state["scope"]["direct_bridge_sources"],
        )
        self.assertEqual(ctx._last_promotion_gate_state["scope"]["competing_candidates"], [])
        self.assertTrue(
            any(
                item.get("reason") == "non_novel_or_derivative"
                for item in ctx._ignored_search_only_contextual_competitors
            )
        )

    def test_exact_current_title_lock_keeps_candidate_role_packet_alias_competitor(self):
        pipeline = build_pipeline()
        title = "정확한 작품명"
        url = "https://novelpia.com/novel/61001"
        other_title = "실제로 함께 비교한 작품"
        other_url = "https://novelpia.com/novel/61002"
        post = PostInput(
            post_id=21660237,
            title="정확한 작품명 볼만함?",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="text", text="비교작이랑 비교하면 어느 쪽이 나음?")
            ],
            comments=[],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=[],
        )
        ctx.search_results = [
            {
                "title": title,
                "url": url,
                "content": "노벨피아 웹소설 작품 상세",
                "query": "정확한 작품명 노벨피아",
            },
            {
                "title": other_title,
                "url": other_url,
                "content": f"{title}과 독자가 비교하는 다른 웹소설",
                "query": "정확한 작품명 비교 작품",
            },
        ]
        current = DetectedTitle(
            official_title=title,
            heretic_url=url,
            confidence="High",
            alias_or_mention=title,
            source_tier="official_detail",
            page_type="novel_page",
            locked=True,
            reference_role="primary",
        )
        competitor = DetectedTitle(
            official_title=other_title,
            heretic_url=other_url,
            confidence="High",
            alias_or_mention="비교작",
            source_tier="official_detail",
            page_type="novel_page",
            locked=True,
            reference_role="candidate",
        )
        verification_result = {
            "is_relevant": True,
            "is_novel_discussion": True,
            "novel_identity": {"official_novel_title": title, "heretic_url": url},
            "grounding_check": {
                "anchor_found": "title_exact",
                "title_abbrev_mentioned": True,
                "matched_alias": title,
            },
        }

        decision = pipeline._record_title_led_alias_public_title_gate_decision(
            ctx,
            title,
            candidate_url=url,
            final_decision={
                "discussion_type": "comparison",
                "work_resolution": "resolved",
                "title_resolution_state": "resolved",
                "comparison_target": {"official_title": other_title},
            },
            verification_result=verification_result,
            title_candidates=[current, competitor],
            acceptance={"decision": "accept", "title_led_consumption_bridge": True, "score": 30},
        )

        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertIn(
            "title_led_alias_contextual_official_detail_competes",
            decision["reason_codes"],
        )
        self.assertIn(
            other_title,
            ctx._last_promotion_gate_state["scope"]["competing_candidates"],
        )

    def test_exact_current_title_lock_is_not_inherited_after_canonical_title_change(self):
        pipeline = build_pipeline()
        title = "Alpha"
        canonical_title = "Alpha Novel"
        url = "https://novelpia.com/novel/61003"
        post = PostInput(
            post_id=21660238,
            title="Alpha 볼만함?",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="주인공 전개가 궁금함")],
            comments=[],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=[],
        )
        ctx.search_results = [
            {"title": title, "url": url, "content": "노벨피아 웹소설 작품 상세"}
        ]
        candidate = DetectedTitle(
            official_title=title,
            heretic_url=url,
            confidence="High",
            alias_or_mention=title,
            source_tier="official_detail",
            page_type="novel_page",
            locked=True,
            reference_role="primary",
        )

        with patch.object(
            pipeline,
            "_infer_alias_title_from_search_evidence",
            return_value={"title": canonical_title, "matched_url": url, "confidence": 3},
        ), patch.object(
            pipeline,
            "_safe_official_detail_url_for_title",
            return_value=url,
        ), patch.object(
            pipeline,
            "_source_title_matches_candidate",
            return_value=True,
        ):
            decision = pipeline._record_title_led_alias_public_title_gate_decision(
                ctx,
                title,
                candidate_url=url,
                final_decision={
                    "discussion_type": "review",
                    "work_resolution": "resolved",
                    "title_resolution_state": "resolved",
                },
                verification_result={
                    "novel_identity": {"official_novel_title": title, "heretic_url": url},
                    "grounding_check": {"anchor_found": "title_exact", "matched_alias": title},
                },
                title_candidates=[candidate],
                acceptance={"decision": "accept", "title_led_consumption_bridge": True},
            )

        self.assertFalse(decision["publish_allowed"])
        self.assertIn(
            "title_led_alias_official_detail_canonicalized",
            ctx._last_promotion_gate_state["scope"]["direct_bridge_sources"],
        )
        self.assertNotIn(
            "exact_current_title_official_detail_lock",
            ctx._last_promotion_gate_state["scope"]["direct_bridge_sources"],
        )

    def test_normalized_platform_title_still_detects_strong_manga_ebook_payload(self):
        pipeline = build_pipeline()
        self.assertTrue(
            pipeline._is_non_novel_media_platform_detail_hit(
                {
                    "title": "테라포마스",
                    "url": "https://ridibooks.com/books/1019005884",
                    "content": "테라포마스 - 만화 e북 - 리디. 화성 테라포밍 이야기.",
                },
                "테라포마스",
            )
        )

    def test_structured_manga_type_dominates_page_type_and_novel_title_marker(self):
        pipeline = build_pipeline()
        for row in (
            {
                "title": "테라포마스",
                "url": "https://ridibooks.com/books/1019005884",
                "media_type": "manga",
                "page_type": "product_detail",
            },
            {
                "title": "테라포마스 #NOVEL",
                "url": "https://ridibooks.com/books/1019005884",
                "media_type": "manga",
            },
        ):
            with self.subTest(row=row):
                self.assertTrue(
                    pipeline._is_non_novel_media_platform_detail_hit(
                        row,
                        "테라포마스",
                    )
                )

    def test_candidate_bound_non_image_alias_survives_incidental_image_fail_close(self):
        pipeline = build_pipeline()
        title = "빚을 져서라도 세상은 구해야 할 거 아니야"
        url = "https://series.naver.com/novel/detail.series?productNo=13598334"
        post = PostInput(
            post_id=11668307,
            title="빛세구 궁금한 점 있음",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", url="https://dcimg.example/incidental.jpg"),
                ContentBlock(type="text", text="다시보는 중인데 튜토리얼에 왜 폐급이 있지?"),
            ],
            comments=[],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=[],
        )
        ctx.post_data["image_enrichment"] = [
            {
                "ocr_text": "관계없는 장면",
                "evidence_type": "explicit_text",
                "title_role": "unknown",
                "promotion_eligible": False,
            }
        ]
        pipeline._inject_image_enrichment_blocks(ctx.post_data)
        ctx.search_results = [
            {
                "title": f"{title} [독점]",
                "url": url,
                "content": f"#NOVEL. {title}. 약칭 빛세구. 작품 상세.",
                "query": "시리즈 빛세구 작가",
            }
        ]
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "ask_question",
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                }
            },
        )
        candidate = DetectedTitle(
            official_title=title,
            heretic_url=url,
            confidence="High",
            alias_or_mention=None,
            source_tier="official_detail",
            page_type="novel_page",
            locked=True,
            reference_role="primary",
        )
        verification_result = {
            "is_relevant": True,
            "is_novel_discussion": True,
            "novel_identity": {"official_novel_title": title, "heretic_url": url},
            "grounding_check": {
                "anchor_found": "title_abbrev_mention",
                "title_abbrev_mentioned": True,
                "matched_alias": "빛세구",
                "matched_title": title,
            },
            "relation_judgment": {
                "relation_type": "explicit_alias",
                "discussion_target": "specific_work",
                "promotion_decision": "allow",
            },
        }

        self.assertTrue(
            pipeline._has_candidate_bound_non_image_alias_official_detail_bridge(
                ctx,
                title,
                title_candidates=[candidate],
                final_decision={"discussion_type": "review"},
                verification_result=verification_result,
            )
        )
        self.assertFalse(
            pipeline._image_scene_only_candidate_lacks_publish_surface(
                ctx,
                title,
                title_candidates=[candidate],
                final_decision={"discussion_type": "review"},
                verification_result=verification_result,
            )
        )
        self.assertTrue(
            pipeline._post_discusses_work_as_work(
                ctx,
                title,
                source="locked_official_candidate_rescued",
                final_decision={"discussion_type": "review"},
                verification_result=verification_result,
                title_candidates=[candidate],
            )
        )

    def test_candidate_bound_alias_rejects_forged_verifier_without_trusted_binding(self):
        pipeline = build_pipeline()
        title = "Completely Different Novel"
        alias = "ArbitraryAlias"
        url = "https://novelpia.com/novel/61999"
        post = PostInput(
            post_id=21668307,
            title=f"{alias} 작품 회차 궁금",
            author="ㅇㅇ",
            content_blocks=[
                ContentBlock(type="image", url="https://dcimg.example/unrelated.jpg"),
                ContentBlock(type="text", text="주인공 설정이 궁금함"),
            ],
            comments=[],
        )
        ctx = ConversationContext(
            post_id=post.post_id,
            post_data=pipeline._post_to_dict(post),
            comments=[],
        )
        ctx.post_data["image_enrichment"] = [
            {
                "ocr_text": "관계없는 장면",
                "title_role": "unknown",
                "promotion_eligible": False,
            }
        ]
        pipeline._inject_image_enrichment_blocks(ctx.post_data)
        ctx.search_results = [
            {
                "title": title,
                "url": url,
                "content": f"{title} 공식 작품 상세",
                "query": f"{alias} 웹소설",
            }
        ]
        candidate = DetectedTitle(
            official_title=title,
            heretic_url=url,
            confidence="High",
            source_tier="official_detail",
            page_type="novel_page",
            locked=True,
            reference_role="primary",
        )
        forged_verifier = {
            "is_relevant": True,
            "is_novel_discussion": True,
            "novel_identity": {"official_novel_title": title, "heretic_url": url},
            "grounding_check": {
                "anchor_found": "title_alias",
                "matched_alias": alias,
                "matched_title": title,
            },
            "relation_judgment": {
                "relation_type": "explicit_alias",
                "discussion_target": "specific_work",
                "promotion_decision": "allow",
            },
        }

        self.assertEqual(
            pipeline._trusted_non_llm_alias_official_detail_binding_source(
                ctx,
                title=title,
                alias=alias,
                exact_urls=[url],
            ),
            "",
        )
        self.assertFalse(
            pipeline._has_candidate_bound_non_image_alias_official_detail_bridge(
                ctx,
                title,
                title_candidates=[candidate],
                final_decision={"discussion_type": "review"},
                verification_result=forged_verifier,
            )
        )
        self.assertTrue(
            pipeline._image_scene_only_candidate_lacks_publish_surface(
                ctx,
                title,
                title_candidates=[candidate],
                final_decision={"discussion_type": "review"},
                verification_result=forged_verifier,
            )
        )


if __name__ == "__main__":
    unittest.main()
