from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import llm_batch.agentic_pipeline as agentic_pipeline_module  # noqa: E402
from llm_batch.agentic_pipeline import AgenticPipeline  # noqa: E402
from llm_batch.experts.orchestrator import ConversationContext, ExpertType, Orchestrator  # noqa: E402
from llm_batch.models import DetectedTitle  # noqa: E402


class DummyLLM:
    pass


class DummyMCP:
    pass


def _build_pipeline() -> AgenticPipeline:
    return AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=2)


def _known_title_abbreviation_work_context() -> ConversationContext:
    ctx = ConversationContext(
        post_id=11718120,
        post_data={
            "post_id": 11718120,
            "title": "그러고보니 담텔기 작가의 말로 스포 아닌 스포했네",
            "normalized_title": "그러고보니 담텔기 작가의 말로 스포 아닌 스포했네",
            "content_blocks": [
                {"type": "text", "text": "305호 끝나면 휴재 > 곧 305호 끝난다"},
                {"type": "text", "text": "5회차까지 간 끝에 심판자와의 팬티레슬링 어디갔냐고 아오"},
            ],
        },
        comments=[],
    )
    ctx.set_expert_output(
        ExpertType.GATEKEEPER,
        {
            "post_type": "work_discussion",
            "detected_entities": {
                "possible_titles": ["담텔기", "305호"],
                "possible_characters": ["심판자"],
            },
            "context_clues": {
                "has_episode_reference": True,
                "is_spoiler_discussion": True,
            },
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
    return ctx


def _known_title_abbreviation_bare_alias_context() -> ConversationContext:
    return ConversationContext(
        post_id=11718080,
        post_data={
            "post_id": 11718080,
            "title": "담텔기 단어만 보였음",
            "content_blocks": [
                {"type": "text", "text": "밥 먹는데 같이 소설 볼 친구 있었으면 좋겠다는 잡담"},
            ],
        },
        comments=[],
    )


def _alpha_alias_work_context(alias: str = "abc") -> ConversationContext:
    ctx = ConversationContext(
        post_id=9003,
        post_data={
            "post_id": 9003,
            "title": f"{alias} 최신화 후기",
            "normalized_title": f"{alias} 최신화 후기",
            "content_blocks": [{"type": "text", "text": "오늘 회차 전개랑 작가의 말 얘기"}],
        },
        comments=[],
    )
    ctx.set_expert_output(
        ExpertType.GATEKEEPER,
        {
            "post_type": "work_discussion",
            "detected_entities": {"possible_titles": [alias]},
            "context_clues": {"has_episode_reference": True},
        },
    )
    ctx.set_expert_output(
        ExpertType.DISCOURSE,
        {
            "discourse_analysis": {
                "intent": "discuss_work",
                "title_novel_terms": [alias],
                "semantic_seed_review": {"is_specific_work_discussion": True},
            }
        },
    )
    return ctx


class KnownTitleAbbreviationSupportTest(unittest.TestCase):
    def test_known_title_abbreviation_counts_as_explicit_support_with_work_anchor(self):
        pipeline = _build_pipeline()
        ctx = _known_title_abbreviation_work_context()

        self.assertTrue(
            pipeline._known_abbreviation_alias_mentioned_in_post_main_context(
                ctx,
                "괴담 호텔 탈출기",
            )
        )
        self.assertTrue(
            pipeline._has_curated_alias_contextual_work_anchor(ctx, "괴담 호텔 탈출기")
        )

        support = pipeline._collect_title_support_kinds(ctx, "괴담 호텔 탈출기", vf_result={})

        self.assertIn("known_abbreviation_alias", support)
        self.assertIn("curated_alias_work_anchor", support)
        self.assertNotIn("post_main_mention", support)
        self.assertTrue(
            pipeline._has_explicit_title_support(
                ctx,
                "괴담 호텔 탈출기",
                vf_result={},
                support_kinds=support,
            )
        )
        self.assertTrue(pipeline._has_title_abbrev_stability_signal(ctx, "괴담 호텔 탈출기"))
        self.assertFalse(pipeline._has_title_abbrev_stability_signal(ctx, "어서오세요, 305호에!"))
        self.assertTrue(pipeline._known_title_abbreviation_context_locks_title(ctx, "괴담 호텔 탈출기"))

    def test_known_title_abbreviation_direct_promotion_uses_shared_registry(self):
        pipeline = _build_pipeline()
        ctx = _known_title_abbreviation_work_context()

        promoted = pipeline._try_promote_best_candidate(
            ctx,
            vf_result={"novel_identity": {}},
            final_decision={"is_relevant": True, "discussion_type": "work_discussion"},
        )

        self.assertIsNotNone(promoted)
        self.assertEqual(promoted[0], "괴담 호텔 탈출기")
        self.assertEqual(promoted[2], "Medium")
        self.assertIn("known_title_abbr:", promoted[3])
        self.assertIn("evidence=registry_anchor_only", promoted[3])
        self.assertTrue(getattr(ctx, "_known_abbreviation_promotion_demoted_without_hard_evidence", False))
        sources = pipeline._collect_alias_resolution_sources(ctx, "괴담 호텔 탈출기")
        self.assertIsNotNone(sources)
        self.assertEqual(sources[0]["source_registry"], "KNOWN_TITLE_ABBREVIATIONS")
        self.assertEqual(sources[0]["promotion_evidence_tier"], "registry_anchor_only")
        self.assertEqual(sources[0]["promotion_confidence"], "Medium")
        self.assertTrue(sources[0]["confidence_demoted_without_hard_evidence"])

    def test_registry_anchor_only_medium_is_serialized_in_final_output_alias_sources(self):
        pipeline = _build_pipeline()
        ctx = _known_title_abbreviation_work_context()

        promoted = pipeline._try_promote_best_candidate(
            ctx,
            vf_result={"novel_identity": {}},
            final_decision={"is_relevant": True, "discussion_type": "work_discussion"},
        )
        self.assertIsNotNone(promoted)
        promoted_title, _promoted_url, promoted_confidence, _promoted_source = promoted
        ctx.set_expert_output(
            ExpertType.ARBITER,
            {
                "final_decision": {
                    "is_relevant": True,
                    "official_title": promoted_title,
                    "official_novel_title": promoted_title,
                    "confidence": promoted_confidence,
                    "discussion_type": "work_discussion",
                },
                "metadata_synthesis": {},
            },
        )

        old_validator = pipeline._apply_output_consistency_validator
        pipeline._apply_output_consistency_validator = lambda **_kwargs: {
            "is_relevant": True,
            "discussion_type": "review",
            "topicality": "core_relevant",
            "subtype": "resolved_work",
            "work_resolution": "resolved",
            "anchor_type": "title_alias",
            "anchor_strength": "medium",
            "context_sources": ["title", "body"],
            "consistency_flags": [],
            "official_title": promoted_title,
            "confidence": promoted_confidence,
            "reason": "registry alias promotion serialized",
            "notes": "registry alias promotion serialized",
        }
        try:
            output = pipeline._context_to_output(ctx)
        finally:
            pipeline._apply_output_consistency_validator = old_validator

        identity = output.identity.novel_identity
        self.assertIsNotNone(identity)
        self.assertEqual(identity.official_title, "괴담 호텔 탈출기")
        self.assertEqual(identity.confidence, "Medium")
        self.assertIsNotNone(identity.alias_resolution_sources)
        source = identity.alias_resolution_sources[0]
        self.assertEqual(source["source_registry"], "KNOWN_TITLE_ABBREVIATIONS")
        self.assertEqual(source["promotion_evidence_tier"], "registry_anchor_only")
        self.assertEqual(source["promotion_confidence"], "Medium")
        self.assertTrue(source["confidence_demoted_without_hard_evidence"])

    def test_registry_anchor_only_reason_does_not_overstate_search_evidence(self):
        pipeline = _build_pipeline()
        ctx = _known_title_abbreviation_work_context()

        promoted = pipeline._try_promote_best_candidate(
            ctx,
            vf_result={"novel_identity": {}},
            final_decision={"is_relevant": True, "discussion_type": "work_discussion"},
        )

        self.assertIsNotNone(promoted)
        reason = pipeline._format_relevant_reason(
            discussion_type="review",
            official_title="괴담 호텔 탈출기",
            verifier_reason="",
            arbiter_reason="",
            grounding_issue="",
            counter_arguments=[],
            ctx=ctx,
            verification_result={"grounding_check": {"anchor_found": "title_abbrev_mention"}},
        )

        self.assertIn("- alias_promotion_evidence_tier: registry_anchor_only", reason)
        self.assertIn("- alias_promotion_confidence: Medium", reason)
        self.assertIn("- alias_confidence_demoted_without_hard_evidence: true", reason)
        self.assertIn("Strong 근거로 보지 않습니다", reason)

    def test_known_title_abbreviation_direct_promotion_allows_high_with_official_evidence(self):
        pipeline = _build_pipeline()
        original_registry = agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS
        try:
            agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS = {"abc": "Alpha Novel"}
            ctx = _alpha_alias_work_context("abc")
            ctx.search_results = [
                {
                    "title": "Alpha Novel",
                    "url": "https://series.naver.com/novel/detail.series?productNo=123456",
                    "content": "Alpha Novel 공식 작품 페이지",
                    "_trust_score": 1.0,
                }
            ]

            promoted = pipeline._try_promote_best_candidate(
                ctx,
                vf_result={"novel_identity": {}},
                final_decision={"is_relevant": True, "discussion_type": "work_discussion"},
            )

            self.assertIsNotNone(promoted)
            self.assertEqual(promoted[0], "Alpha Novel")
            self.assertEqual(promoted[2], "High")
            self.assertIn("known_title_abbr:abc", promoted[3])
            self.assertIn("evidence=hard_support", promoted[3])
            self.assertIn(
                "official_title_evidence",
                getattr(ctx, "_known_abbreviation_promotion_support_reasons", []),
            )
            self.assertFalse(getattr(ctx, "_known_abbreviation_promotion_demoted_without_hard_evidence", False))
            sources = pipeline._collect_alias_resolution_sources(ctx, "Alpha Novel")
            self.assertIsNotNone(sources)
            self.assertEqual(sources[0]["promotion_evidence_tier"], "hard_support")
            self.assertEqual(sources[0]["promotion_confidence"], "High")
            self.assertIn("official_title_evidence", sources[0]["promotion_support_reasons"])
            self.assertNotIn("confidence_demoted_without_hard_evidence", sources[0])
        finally:
            agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS = original_registry

    def test_known_abbreviation_direct_promotion_demotes_registry_anchor_without_hard_evidence(self):
        pipeline = _build_pipeline()
        original_abbrev_registry = agentic_pipeline_module.KNOWN_ABBREVIATIONS
        original_title_registry = agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS
        try:
            agentic_pipeline_module.KNOWN_ABBREVIATIONS = {"abc": "Alpha Novel"}
            agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS = {}
            ctx = _alpha_alias_work_context("abc")

            promoted = pipeline._try_promote_best_candidate(
                ctx,
                vf_result={"novel_identity": {}},
                final_decision={"is_relevant": True, "discussion_type": "work_discussion"},
            )

            self.assertIsNotNone(promoted)
            self.assertEqual(promoted[0], "Alpha Novel")
            self.assertEqual(promoted[2], "Medium")
            self.assertIn("known_abbr:abc", promoted[3])
            self.assertIn("evidence=registry_anchor_only", promoted[3])
            self.assertTrue(getattr(ctx, "_known_abbreviation_promotion_demoted_without_hard_evidence", False))
        finally:
            agentic_pipeline_module.KNOWN_ABBREVIATIONS = original_abbrev_registry
            agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS = original_title_registry

    def test_known_abbreviation_title_guard_does_not_rewrite_registry_anchor_only_suspected_title(self):
        pipeline = _build_pipeline()
        original_registry = agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS
        try:
            agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS = {"abc": "Alpha Novel"}
            ctx = ConversationContext(
                post_id=9004,
                post_data={
                    "post_id": 9004,
                    "title": "abc 잡담",
                    "content_blocks": [{"type": "text", "text": "오늘은 그냥 감상만 적음"}],
                },
                comments=[],
            )
            ctx.suspected_titles = [{"title": "Alpha Novel", "confidence": "Medium"}]

            title, url = pipeline._apply_known_abbreviation_title_guard(ctx, "abc", None)

            self.assertEqual(title, "abc")
            self.assertIsNone(url)
            self.assertTrue(getattr(ctx, "_known_abbreviation_title_guard_blocked_soft_support", False))
            self.assertEqual(getattr(ctx, "_known_abbreviation_title_guard_blocked_alias", ""), "abc")
            self.assertEqual(getattr(ctx, "_known_abbreviation_title_guard_blocked_title", ""), "Alpha Novel")
        finally:
            agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS = original_registry

    def test_known_abbreviation_title_guard_allows_rewrite_with_official_detail_hard_support(self):
        pipeline = _build_pipeline()
        original_registry = agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS
        try:
            agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS = {"abc": "Alpha Novel"}
            ctx = ConversationContext(
                post_id=9005,
                post_data={
                    "post_id": 9005,
                    "title": "abc 최신화 후기",
                    "content_blocks": [{"type": "text", "text": "오늘 회차 전개 이야기"}],
                },
                comments=[],
            )
            ctx.search_results = [
                {
                    "title": "Alpha Novel - 네이버 시리즈",
                    "url": "https://series.naver.com/novel/detail.series?productNo=123456",
                    "content": "Alpha Novel 공식 작품 페이지",
                }
            ]

            title, _url = pipeline._apply_known_abbreviation_title_guard(ctx, "abc", None)

            self.assertEqual(title, "Alpha Novel")
            self.assertFalse(getattr(ctx, "_known_abbreviation_title_guard_blocked_soft_support", False))
        finally:
            agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS = original_registry

    def test_prefix_only_known_title_abbreviation_official_detail_does_not_lock(self):
        pipeline = _build_pipeline()
        original_registry = agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS
        try:
            agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS = {"아생갤": "아카데미 생존 갤러리"}
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
            ctx.search_results = [
                {
                    "title": "아카데미 생존 갤러리",
                    "url": "https://novelpia.com/novel/380218",
                    "content": "아카데미 생존 갤러리 공식 작품 페이지",
                }
            ]

            self.assertTrue(
                pipeline._known_abbreviation_alias_mentioned_in_post_main_context(
                    ctx,
                    "아카데미 생존 갤러리",
                )
            )
            self.assertFalse(
                pipeline._has_curated_alias_contextual_work_anchor(
                    ctx,
                    "아카데미 생존 갤러리",
                )
            )
            self.assertFalse(
                pipeline._known_title_abbreviation_context_locks_title(
                    ctx,
                    "아카데미 생존 갤러리",
                )
            )

            title, url = pipeline._apply_known_abbreviation_title_guard(ctx, "아생갤", None)
            self.assertEqual(title, "아생갤")
            self.assertIsNone(url)
            self.assertTrue(getattr(ctx, "_known_abbreviation_title_guard_blocked_soft_support", False))
            self.assertEqual(getattr(ctx, "_known_abbreviation_title_guard_blocked_alias", ""), "아생갤")
            self.assertEqual(
                getattr(ctx, "_known_abbreviation_title_guard_blocked_title", ""),
                "아카데미 생존 갤러리",
            )

            candidate, hit = pipeline._resolve_batch_memory_alias_candidate(ctx, verification_result={})
            self.assertIsNone(candidate)
            self.assertIsNone(hit)
            self.assertEqual(
                getattr(ctx, "_batch_alias_rescue_blocked_nonwork_context_reason", ""),
                "known_title_abbreviation_missing_work_anchor",
            )
        finally:
            agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS = original_registry

    def test_no_work_context_blocks_known_abbreviation_title_guard_even_with_official_detail(self):
        pipeline = _build_pipeline()
        original_registry = agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS
        try:
            agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS = {"abc": "Alpha Novel"}
            ctx = ConversationContext(
                post_id=11718080,
                post_data={
                    "post_id": 11718080,
                    "title": "abc 보고 같이 밥먹을 친구 있었으면",
                    "content_blocks": [{"type": "text", "text": "작품 얘기가 아니라 같이 볼 친구 한탄"}],
                },
                comments=[],
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
            ctx.set_expert_output(
                ExpertType.ARBITER,
                {
                    "final_decision": {
                        "is_relevant": False,
                        "official_title": None,
                        "title_resolution_allowed": False,
                        "title_resolution_state": "context_only",
                        "discussion_type": "community_banter",
                    }
                },
            )
            ctx.search_results = [
                {
                    "title": "Alpha Novel - 네이버 시리즈",
                    "url": "https://series.naver.com/novel/detail.series?productNo=123456",
                    "content": "Alpha Novel 공식 작품 페이지",
                }
            ]

            title, url = pipeline._apply_known_abbreviation_title_guard(ctx, "abc", None)

            self.assertEqual(title, "abc")
            self.assertIsNone(url)
            self.assertTrue(getattr(ctx, "_known_abbreviation_title_guard_blocked_semantic_seed", False))
            self.assertEqual(getattr(ctx, "_known_abbreviation_title_guard_blocked_alias", ""), "abc")
            self.assertEqual(getattr(ctx, "_known_abbreviation_title_guard_blocked_title", ""), "Alpha Novel")
            self.assertEqual(
                getattr(ctx, "_semantic_no_work_title_promotion_blocked_source", ""),
                "known_abbreviation_title_guard:known_title_abbrev",
            )
        finally:
            agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS = original_registry

    def test_no_work_context_still_blocks_known_title_abbreviation_promotion_without_work_anchor(self):
        pipeline = _build_pipeline()
        ctx = ConversationContext(
            post_id=11718080,
            post_data={
                "post_id": 11718080,
                "title": "담텔기 단어만 보였음",
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
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "community_banter",
                "detected_entities": {"possible_titles": ["담텔기"]},
                "context_clues": {
                    "has_episode_reference": True,
                    "is_spoiler_discussion": True,
                },
            },
        )

        promoted = pipeline._try_promote_best_candidate(
            ctx,
            vf_result={"novel_identity": {}},
            final_decision={"is_relevant": True, "discussion_type": "community_banter"},
        )

        self.assertIsNone(promoted)
        self.assertTrue(getattr(ctx, "_known_abbreviation_promotion_blocked_semantic_seed", False))
        self.assertEqual(getattr(ctx, "_known_abbreviation_promotion_blocked_alias", None), "담텔기")
        self.assertFalse(pipeline._has_title_abbrev_stability_signal(ctx, "괴담 호텔 탈출기"))
        self.assertFalse(pipeline._has_curated_alias_contextual_work_anchor(ctx, "괴담 호텔 탈출기"))
        self.assertFalse(
            pipeline._has_direct_work_anchor_for_no_work_rescue(
                ctx,
                "괴담 호텔 탈출기",
                verification_result={},
                has_episode_ref=True,
            )
        )

    def test_update_question_known_title_abbreviation_survives_semantic_no_work_without_search(self):
        pipeline = _build_pipeline()
        ctx = ConversationContext(
            post_id=11652175,
            post_data={
                "post_id": 11652175,
                "title": "오늘 담텔기 오냐?",
                "normalized_title": "오늘 담텔기 오냐?",
                "content_blocks": [{"type": "text", "text": "아님 12시 넘어서 내일 새벽에 오냐"}],
            },
            comments=[],
        )
        ctx.uncertainty_sources.append("intent_permit_for_title_search=false(semantic_seed_review_not_specific_work)")
        ctx.discourse_warning = "non_novel(meta_platform,high)"
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "primary_domain": "meta_platform",
                    "intent": "ask_question",
                    "semantic_seed_review": {"is_specific_work_discussion": False},
                    "warnings": ["semantic_seed_review_specific_work_denied"],
                }
            },
        )
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "community_banter",
                "detected_entities": {"possible_titles": ["담텔기"]},
                "context_clues": {},
            },
        )

        self.assertTrue(
            pipeline._known_title_abbreviation_update_question_anchor(
                ctx,
                "괴담 호텔 탈출기",
                "담텔기",
            )
        )
        self.assertIsNone(
            pipeline._search_inferred_alias_nonwork_block_reason(
                ctx,
                title="괴담 호텔 탈출기",
                alias="담텔기",
                surface="오늘 담텔기 오냐?",
                verification_result={},
            )
        )
        candidate, hit = pipeline._resolve_batch_memory_alias_candidate(ctx, verification_result={})

        self.assertIsNotNone(candidate)
        self.assertIsNotNone(hit)
        self.assertEqual(candidate.official_title, "괴담 호텔 탈출기")
        self.assertEqual(candidate.alias_or_mention, "담텔기")
        self.assertEqual(hit["source"], "known_title_abbreviation")
        self.assertFalse(getattr(ctx, "_batch_alias_rescue_blocked_nonwork_context_reason", ""))

    def test_known_title_abbreviation_recall_prefers_leftmost_alias_lifecycle_context(self):
        pipeline = _build_pipeline()
        ctx = ConversationContext(
            post_id=11668324,
            post_data={
                "post_id": 11668324,
                "title": "니생들이랑 김괴라리 장갤픽 아니였음?",
                "normalized_title": "니생들이랑 김괴라리 장갤픽 아니였음?",
                "content_blocks": [{"type": "text", "text": "왜 점점 언급이 줄어드는것 같냐"}],
            },
            comments=["원래 작품 나오고 시간 지나면 언급 줄잖어"],
        )
        ctx.uncertainty_sources.append("intent_permit_for_title_search=false(semantic_seed_review_not_specific_work)")
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "primary_domain": "novel_literature",
                    "intent": "discuss_work",
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

        def recover(_ctx, *, title, alias_text="", **_kwargs):
            if title == "니들 생각 다 들린다":
                return "https://novelpia.com/novel/384318"
            if title == "괴담에 휘말렸다":
                return "https://novelpia.com/novel/363195"
            return None

        with patch.object(
            pipeline,
            "_recover_corrected_title_official_url",
            side_effect=recover,
        ) as recover_mock:
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

        self.assertIsNotNone(promotion)
        self.assertEqual(recovered_identity["official_title"], "니들 생각 다 들린다")
        self.assertEqual(recovered_identity["heretic_url"], "https://novelpia.com/novel/384318")
        self.assertIsNotNone(primary_work)
        self.assertEqual(primary_work.official_title, "니들 생각 다 들린다")
        self.assertEqual(recovered_candidates[0].alias_or_mention, "니생들")
        self.assertIn("known_title_abbreviation_official_detail_anchor", recovered_identity["consistency_flags"])
        self.assertIn("confirmed_alias:니생들", recovered_identity["consistency_flags"])
        self.assertEqual(recover_mock.call_args_list[0].kwargs["title"], "니들 생각 다 들린다")

    def test_known_title_abbreviation_recall_allows_character_setting_anchor(self):
        pipeline = _build_pipeline()
        original_registry = agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS
        try:
            agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS = {"아생갤": "아카데미 생존 갤러리"}
            ctx = ConversationContext(
                post_id=11697267,
                post_data={
                    "post_id": 11697267,
                    "title": "헐... 아생갤 라나 정체 충격이네",
                    "normalized_title": "헐... 아생갤 라나 정체 충격이네",
                    "content_blocks": [{"type": "text", "text": "라나가 북한국일 줄은 몰랐지...."}],
                },
                comments=["흑인녀가 아니였다고"],
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
                        "primary_domain": "novel_literature",
                        "intent": "discuss_work",
                        "semantic_seed_review": {"is_specific_work_discussion": True},
                    }
                },
            )

            extended_identity = {
                "is_relevant": True,
                "work_resolution": "unresolved",
                "title_resolution_state": "unresolved_matchable",
                "discussion_type": "general",
                "consistency_flags": [],
            }

            with patch.object(
                pipeline,
                "_recover_corrected_title_official_url",
                return_value="https://novelpia.com/novel/380218",
            ) as recover_mock:
                recovered_identity, recovered_candidates, primary_work, promotion = (
                    pipeline._apply_official_url_recall_promotion(
                        ctx=ctx,
                        extended_identity=extended_identity,
                        title_candidates=[],
                        primary_work=None,
                        verification_result={"is_relevant": True, "novel_identity": {}},
                        final_decision={"discussion_type": "character_talk"},
                    )
                )

            self.assertIsNotNone(promotion)
            self.assertEqual(recovered_identity["official_title"], "아카데미 생존 갤러리")
            self.assertEqual(recovered_identity["heretic_url"], "https://novelpia.com/novel/380218")
            self.assertIsNotNone(primary_work)
            self.assertEqual(primary_work.official_title, "아카데미 생존 갤러리")
            self.assertEqual(recovered_candidates[0].alias_or_mention, "아생갤")
            self.assertIn("known_title_abbreviation_official_detail_anchor", recovered_identity["consistency_flags"])
            self.assertIn("confirmed_alias:아생갤", recovered_identity["consistency_flags"])
            self.assertEqual(recover_mock.call_args.kwargs["title"], "아카데미 생존 갤러리")
        finally:
            agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS = original_registry

    def test_known_title_abbreviation_recall_blocks_competing_verified_body_work(self):
        pipeline = _build_pipeline()
        original_registry = agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS
        try:
            agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS = {"아생갤": "아카데미 생존 갤러리"}
            ctx = ConversationContext(
                post_id=11698880,
                post_data={
                    "post_id": 11698880,
                    "title": "아생갤 개 존나게 재밌군 ㅇㅇ",
                    "normalized_title": "아생갤 개 존나게 재밌군 ㅇㅇ",
                    "content_blocks": [
                        {"type": "text", "text": "가챠펑크 세드릭도 그렇고"},
                        {"type": "text", "text": "시원시원한 상남자라서 너무 좋구나"},
                    ],
                },
                comments=[],
            )
            ctx.verified_character_work_links = [
                {
                    "title": "가챠 중독자의 퓨전펑크 생활",
                    "abbreviation": "가챠펑크",
                    "character": "세드릭",
                    "confidence": "high",
                }
            ]
            ctx.set_expert_output(
                ExpertType.GATEKEEPER,
                {
                    "post_type": "work_discussion",
                    "detected_entities": {
                        "possible_titles": ["아생갤", "가챠펑크"],
                        "possible_characters": ["세드릭"],
                    },
                    "context_clues": {},
                },
            )
            ctx.set_expert_output(
                ExpertType.DISCOURSE,
                {
                    "discourse_analysis": {
                        "primary_domain": "novel_literature",
                        "intent": "discuss_work",
                        "semantic_seed_review": {"is_specific_work_discussion": True},
                    }
                },
            )
            title_candidates = [
                DetectedTitle(
                    official_title="가챠 중독자의 퓨전펑크 생활",
                    alias_or_mention="가챠펑크",
                    confidence="High",
                    source_tier="mixed",
                    reference_role="candidate",
                )
            ]
            extended_identity = {
                "is_relevant": True,
                "work_resolution": "unresolved",
                "title_resolution_state": "unresolved_matchable",
                "discussion_type": "general",
                "consistency_flags": [],
            }

            with patch.object(
                pipeline,
                "_recover_corrected_title_official_url",
                return_value="https://novelpia.com/novel/380218",
            ):
                recovered_identity, recovered_candidates, primary_work, promotion = (
                    pipeline._apply_official_url_recall_promotion(
                        ctx=ctx,
                        extended_identity=extended_identity,
                        title_candidates=title_candidates,
                        primary_work=None,
                        verification_result={"is_relevant": True, "novel_identity": {}},
                        final_decision={"discussion_type": "character_talk"},
                    )
                )

            self.assertIsNone(promotion)
            self.assertIsNone(primary_work)
            self.assertNotIn("official_title", recovered_identity)
            self.assertIn(
                "official_url_recall_blocked_body_verified_character_work_competes",
                recovered_identity["consistency_flags"],
            )
            self.assertIn(
                "body_verified_character_work_competes_with_title_led_alias",
                recovered_identity["consistency_flags"],
            )
            self.assertEqual(
                recovered_identity["blocked_official_title_competing_candidates"],
                ["가챠 중독자의 퓨전펑크 생활"],
            )
            self.assertTrue(
                any(
                    candidate.official_title == "아카데미 생존 갤러리"
                    and "body_verified_character_work_competes_with_title_led_alias"
                    in (candidate.negative_evidence or [])
                    for candidate in recovered_candidates
                )
            )
        finally:
            agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS = original_registry

    def test_known_title_abbreviation_recall_allows_character_setting_theory_anchor(self):
        pipeline = _build_pipeline()
        original_registry = agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS
        try:
            agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS = {"아생갤": "아카데미 생존 갤러리"}
            ctx = ConversationContext(
                post_id=11716448,
                post_data={
                    "post_id": 11716448,
                    "title": "아생갤 걍 히로인들 다 괴이 아니냐",
                    "normalized_title": "아생갤 걍 히로인들 다 괴이 아니냐",
                    "content_blocks": [
                        {"type": "text", "text": "아레스랑 연 있었다고 엘리가 인간 확정이라기엔"},
                        {"type": "text", "text": "괴이 확정인 라나도 홍차 마시고 아레스랑 연 있었다는 거 나왔었는데"},
                        {"type": "text", "text": "걍 히로인들 다 인간이었다가 괴이화된거 아녀??"},
                    ],
                },
                comments=[
                    "발상의 전환으로 라나가 인간일수도 있다고 봐보죠",
                    "다 인간에서 변질된거일수도",
                ],
            )
            ctx.set_expert_output(
                ExpertType.GATEKEEPER,
                {
                    "post_type": "work_discussion",
                    "detected_entities": {"possible_titles": ["아생갤"], "possible_characters": []},
                    "context_clues": {},
                },
            )
            ctx.set_expert_output(
                ExpertType.DISCOURSE,
                {
                    "discourse_analysis": {
                        "primary_domain": "novel_literature",
                        "intent": "discuss_work",
                        "semantic_seed_review": {"is_specific_work_discussion": True},
                    }
                },
            )

            extended_identity = {
                "is_relevant": True,
                "work_resolution": "unresolved",
                "title_resolution_state": "unresolved_matchable",
                "discussion_type": "general",
                "consistency_flags": [],
            }

            with patch.object(
                pipeline,
                "_recover_corrected_title_official_url",
                return_value="https://novelpia.com/novel/380218",
            ) as recover_mock:
                recovered_identity, recovered_candidates, primary_work, promotion = (
                    pipeline._apply_official_url_recall_promotion(
                        ctx=ctx,
                        extended_identity=extended_identity,
                        title_candidates=[],
                        primary_work=None,
                        verification_result={"is_relevant": True, "novel_identity": {}},
                        final_decision={"discussion_type": "character_talk"},
                    )
                )

            self.assertIsNotNone(promotion)
            self.assertEqual(recovered_identity["official_title"], "아카데미 생존 갤러리")
            self.assertEqual(recovered_identity["heretic_url"], "https://novelpia.com/novel/380218")
            self.assertIsNotNone(primary_work)
            self.assertEqual(primary_work.official_title, "아카데미 생존 갤러리")
            self.assertEqual(recovered_candidates[0].alias_or_mention, "아생갤")
            self.assertIn("known_title_abbreviation_official_detail_anchor", recovered_identity["consistency_flags"])
            self.assertIn("confirmed_alias:아생갤", recovered_identity["consistency_flags"])
            self.assertEqual(recover_mock.call_args.kwargs["title"], "아카데미 생존 갤러리")
        finally:
            agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS = original_registry

    def test_known_title_abbreviation_recall_covers_wrong_work_flip_repairs(self):
        pipeline = _build_pipeline()
        original_registry = agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS
        rows = [
            {
                "post_id": 11698890,
                "alias": "댓천마",
                "title": "댓글창의 천재 마법사",
                "url": "https://novelpia.com/novel/370230",
                "post_title": "댓천마 왜 얼공 안하냐",
                "body": [
                    "단상 위에 발판 밟고 올라가서 에헴 하니 기자들이 아니 저 어린애는 뭐지? 한국은 장난하는 건가?",
                    "갑자기 모래사장에서 고래 부술만큼 존나 큰 손 나와서 땅 찍고 주목. 이라고 읊조림과 동시에 더블오인 거 밝히고",
                    "그거듣고 데미갓 개빡쳐서 날아왔다가 한별이 얼굴보고 카디언 킴 찾는 장면",
                ],
                "characters": ["한별", "더블오", "데미갓"],
            },
            {
                "post_id": 11700500,
                "alias": "전1시",
                "title": "전지적 1인칭 시점",
                "url": "https://novelpia.com/novel/49942",
                "post_title": "전1시 지잔든 지선이 최강자라인 바로 밑이라더니",
                "body": [
                    "성검대 최강도 개같이 썰어버릴정도구나",
                    "근데 개좆밥시절 셰이가 뭘 할수 있죠?",
                ],
                "characters": ["셰이", "지선"],
            },
            {
                "post_id": 11705252,
                "alias": "탐재",
                "title": "탐식의 재림",
                "url": "https://page.kakao.com/content/50219568",
                "post_title": "ㄹㅇ존나 순수한 질문",
                "body": [
                    "(대충 탐재 주인공 설지후의 쓰레기력에 감탄하는 댓글들)",
                    "그 아래에 상황을 잘 모르는 순수한 개장빙이가 댓글을 다는데",
                ],
                "characters": ["설지후"],
            },
        ]
        registry = {row["alias"]: row["title"] for row in rows}

        def recover(_ctx, *, title, **_kwargs):
            for row in rows:
                if row["title"] == title:
                    return row["url"]
            return None

        try:
            agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS = registry
            with patch.object(
                pipeline,
                "_recover_corrected_title_official_url",
                side_effect=recover,
            ) as recover_mock:
                for row in rows:
                    with self.subTest(post_id=row["post_id"]):
                        ctx = ConversationContext(
                            post_id=row["post_id"],
                            post_data={
                                "post_id": row["post_id"],
                                "title": row["post_title"],
                                "normalized_title": row["post_title"],
                                "content_blocks": [
                                    {"type": "text", "text": text} for text in row["body"]
                                ],
                            },
                            comments=[],
                        )
                        ctx.set_expert_output(
                            ExpertType.GATEKEEPER,
                            {
                                "post_type": "work_discussion",
                                "detected_entities": {
                                    "possible_titles": [row["alias"]],
                                    "possible_characters": row["characters"],
                                },
                                "context_clues": {},
                            },
                        )
                        ctx.set_expert_output(
                            ExpertType.DISCOURSE,
                            {
                                "discourse_analysis": {
                                    "primary_domain": "novel_literature",
                                    "intent": "discuss_work",
                                    "semantic_seed_review": {"is_specific_work_discussion": True},
                                }
                            },
                        )

                        self.assertTrue(
                            pipeline._has_curated_alias_contextual_work_anchor(ctx, row["title"])
                        )
                        self.assertTrue(
                            pipeline._known_title_abbreviation_context_locks_title(ctx, row["title"])
                        )

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
                                verification_result={"is_relevant": True, "novel_identity": {}},
                                final_decision={"discussion_type": "character_talk"},
                            )
                        )

                        self.assertIsNotNone(promotion)
                        self.assertEqual(recovered_identity["official_title"], row["title"])
                        self.assertEqual(recovered_identity["heretic_url"], row["url"])
                        self.assertEqual(recovered_identity["work_resolution"], "resolved")
                        self.assertIsNotNone(primary_work)
                        self.assertEqual(primary_work.official_title, row["title"])
                        self.assertEqual(recovered_candidates[0].alias_or_mention, row["alias"])
                        self.assertIn(
                            "known_title_abbreviation_official_detail_anchor",
                            recovered_identity["consistency_flags"],
                        )
                        self.assertIn(
                            f"confirmed_alias:{row['alias']}",
                            recovered_identity["consistency_flags"],
                        )
            recovered_titles = [call.kwargs["title"] for call in recover_mock.call_args_list]
            self.assertEqual(recovered_titles, [row["title"] for row in rows])
        finally:
            agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS = original_registry

    def test_low_specific_gate_preserves_known_title_abbreviation(self):
        orchestrator = Orchestrator(experts={}, search_fn=None, fetch_fn=None)
        ctx = ConversationContext(
            post_id=11698890,
            post_data={
                "post_id": 11698890,
                "title": "댓천마 왜 얼공 안하냐",
                "content_blocks": [
                    {"type": "text", "text": "더블오인 거 밝히고 데미갓이 날아왔다가 한별이 얼굴보고 놀라는 장면"},
                ],
            },
            comments=[],
        )
        gatekeeper = {
            "is_noise": False,
            "post_type": "work_discussion",
            "detected_entities": {
                "possible_titles": ["댓천마"],
                "possible_characters": ["한별"],
                "possible_authors": [],
            },
            "key_terms": ["얼공", "데미갓", "카디언 킴"],
            "context_clues": {
                "title_as_body_continuation": True,
                "has_specific_names": True,
            },
            "search_requests": [
                {"query": "댓천마 웹소설", "purpose": "official_title_verify", "priority": 1},
            ],
        }

        guarded = orchestrator._apply_gatekeeper_low_specific_guard(ctx, dict(gatekeeper))

        self.assertFalse(guarded.get("is_noise"))
        self.assertEqual(guarded.get("post_type"), "work_discussion")
        self.assertEqual(guarded.get("search_requests"), gatekeeper["search_requests"])

    def test_known_title_abbreviation_recall_allows_character_appeal_anchor(self):
        pipeline = _build_pipeline()
        original_registry = agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS
        try:
            agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS = {"엑칼뽑": "엑스칼리버 뽑습니다"}
            ctx = ConversationContext(
                post_id=11692444,
                post_data={
                    "post_id": 11692444,
                    "title": "엑칼뽑 캐빨 어떰?",
                    "normalized_title": "엑칼뽑 캐빨 어떰?",
                    "content_blocks": [{"type": "text", "text": "평타 이상임?"}],
                },
                comments=["그 소설에 캐빨 빼면 남는게 있나"],
            )
            ctx.set_expert_output(
                ExpertType.GATEKEEPER,
                {
                    "post_type": "work_discussion",
                    "detected_entities": {"possible_titles": ["엑칼뽑"]},
                    "context_clues": {},
                },
            )
            ctx.set_expert_output(
                ExpertType.DISCOURSE,
                {
                    "discourse_analysis": {
                        "primary_domain": "novel_literature",
                        "intent": "discuss_work",
                        "semantic_seed_review": {"is_specific_work_discussion": True},
                    }
                },
            )

            extended_identity = {
                "is_relevant": True,
                "work_resolution": "unresolved",
                "title_resolution_state": "unresolved_matchable",
                "discussion_type": "general",
                "consistency_flags": [],
            }

            with patch.object(
                pipeline,
                "_recover_corrected_title_official_url",
                return_value="https://novelpia.com/novel/229672",
            ) as recover_mock:
                recovered_identity, recovered_candidates, primary_work, promotion = (
                    pipeline._apply_official_url_recall_promotion(
                        ctx=ctx,
                        extended_identity=extended_identity,
                        title_candidates=[],
                        primary_work=None,
                        verification_result={"is_relevant": True, "novel_identity": {}},
                        final_decision={"discussion_type": "general"},
                    )
                )

            self.assertIsNotNone(promotion)
            self.assertEqual(recovered_identity["official_title"], "엑스칼리버 뽑습니다")
            self.assertEqual(recovered_identity["heretic_url"], "https://novelpia.com/novel/229672")
            self.assertIsNotNone(primary_work)
            self.assertEqual(primary_work.official_title, "엑스칼리버 뽑습니다")
            self.assertEqual(recovered_candidates[0].alias_or_mention, "엑칼뽑")
            self.assertIn("known_title_abbreviation_official_detail_anchor", recovered_identity["consistency_flags"])
            self.assertIn("confirmed_alias:엑칼뽑", recovered_identity["consistency_flags"])
            self.assertEqual(recover_mock.call_args.kwargs["title"], "엑스칼리버 뽑습니다")
        finally:
            agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS = original_registry

    def test_bare_known_title_abbreviation_surface_does_not_promote_without_work_anchor(self):
        pipeline = _build_pipeline()
        ctx = _known_title_abbreviation_bare_alias_context()

        promoted = pipeline._try_promote_best_candidate(
            ctx,
            vf_result={"novel_identity": {}},
            final_decision={"is_relevant": True, "discussion_type": "work_discussion"},
        )

        self.assertIsNone(promoted)
        self.assertTrue(getattr(ctx, "_known_abbreviation_promotion_blocked_missing_anchor", False))
        self.assertEqual(getattr(ctx, "_known_abbreviation_promotion_blocked_alias", None), "담텔기")
        self.assertFalse(pipeline._has_title_abbrev_stability_signal(ctx, "괴담 호텔 탈출기"))
        self.assertFalse(pipeline._known_title_abbreviation_context_locks_title(ctx, "괴담 호텔 탈출기"))
        self.assertFalse(pipeline._has_curated_alias_resolution_anchor(ctx, "괴담 호텔 탈출기"))
        self.assertFalse(
            pipeline._has_alias_title_support(ctx=ctx, title="괴담 호텔 탈출기", vf_result={})
        )
        support = pipeline._collect_title_support_kinds(ctx, "괴담 호텔 탈출기", vf_result={})
        self.assertNotIn("known_abbreviation_alias", support)
        self.assertNotIn("curated_alias_work_anchor", support)
        self.assertNotIn("post_main_mention", support)
        self.assertFalse(
            pipeline._has_explicit_title_support(
                ctx,
                "괴담 호텔 탈출기",
                vf_result={},
                support_kinds=support,
            )
        )

    def test_comment_only_known_title_abbreviation_does_not_lock_title(self):
        pipeline = _build_pipeline()
        ctx = ConversationContext(
            post_id=11718080,
            post_data={
                "post_id": 11718080,
                "title": "그냥 친구랑 소설 보고 싶다",
                "content_blocks": [{"type": "text", "text": "작품 특정 얘기가 아닌 잡담"}],
            },
            comments=["담텔기"],
        )

        self.assertFalse(pipeline._known_title_abbreviation_context_locks_title(ctx, "괴담 호텔 탈출기"))

    def test_curated_alias_match_requires_visible_surface_not_accidental_substring(self):
        pipeline = _build_pipeline()
        original_registry = agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS
        try:
            agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS = {"abc": "Alpha Novel"}
            ctx = ConversationContext(
                post_id=9001,
                post_data={
                    "post_id": 9001,
                    "title": "xabcx는 그냥 일반 문자열",
                    "content_blocks": [{"type": "text", "text": "작품 얘기처럼 보여도 alias 표면은 분리되지 않았다"}],
                },
                comments=[],
            )
            ctx.set_expert_output(
                ExpertType.DISCOURSE,
                {
                    "discourse_analysis": {
                        "intent": "discuss_work",
                        "semantic_seed_review": {"is_specific_work_discussion": True},
                    }
                },
            )
            ctx.set_expert_output(
                ExpertType.GATEKEEPER,
                {
                    "post_type": "work_discussion",
                    "detected_entities": {"possible_titles": ["xabcx"]},
                    "context_clues": {"has_episode_reference": True},
                },
            )

            self.assertFalse(
                pipeline._known_abbreviation_alias_mentioned_in_post_main_context(ctx, "Alpha Novel")
            )
            self.assertIsNone(
                pipeline._try_promote_best_candidate(
                    ctx,
                    vf_result={"novel_identity": {}},
                    final_decision={"is_relevant": True, "discussion_type": "work_discussion"},
                )
            )

            ctx.post_data["title"] = "abc의 최신화 얘기"
            self.assertTrue(
                pipeline._known_abbreviation_alias_mentioned_in_post_main_context(ctx, "Alpha Novel")
            )
        finally:
            agentic_pipeline_module.KNOWN_TITLE_ABBREVIATIONS = original_registry

    def test_unmentioned_adjacent_rescue_candidate_is_not_kept_next_to_curated_alias_primary(self):
        pipeline = _build_pipeline()
        ctx = _known_title_abbreviation_work_context()

        original_select = pipeline._select_best_canonical_rescue_candidate
        try:
            pipeline._select_best_canonical_rescue_candidate = lambda **_kwargs: {
                "title": "괴담 학교 탈출기",
                "rescue": {
                    "strong": True,
                    "official_ev": True,
                    "alias_support": False,
                    "abbrev_stable": False,
                    "verified_char_links": False,
                },
            }
            candidates, primary, mentioned, future = pipeline._annotate_work_references(
                ctx=ctx,
                title_candidates=[
                    DetectedTitle(
                        official_title="괴담 호텔 탈출기",
                        confidence="High",
                        alias_or_mention="담텔기",
                        source_tier="community",
                    )
                ],
                official_title="괴담 호텔 탈출기",
                vf_result={"novel_identity": {}},
            )
        finally:
            pipeline._select_best_canonical_rescue_candidate = original_select

        titles = [cand.official_title for cand in candidates]

        self.assertEqual(primary.official_title, "괴담 호텔 탈출기")
        self.assertIn("괴담 호텔 탈출기", titles)
        self.assertNotIn("괴담 학교 탈출기", titles)
        self.assertEqual(mentioned, [])
        self.assertIsNone(future)

    def test_verified_image_title_blocks_unanchored_canonical_suspect_override(self):
        pipeline = _build_pipeline()
        ctx = ConversationContext(
            post_id=11718082,
            post_data={
                "post_id": 11718082,
                "title": "이게 백합 소설이 아니라니...",
                "content_blocks": [{"type": "text", "text": "두렵구나"}],
                "image_enrichment": [
                    {
                        "evidence_type": "explicit_text",
                        "title_role": "work_title",
                        "focus_role": "work_anchor",
                        "promotion_eligible": True,
                        "explicit_work_title": "재벌가 차녀의 2회차 결그룹",
                        "explicit_author_name": "유은우",
                    }
                ],
            },
            comments=[],
        )
        ctx.search_results = [
            {
                "title": "재벌가 차녀의 2회차 걸그룹 - 웹소설 - 카카오페이지",
                "url": "https://page.kakao.com/content/66692543",
                "content": "작가 유은우. 재벌가 차녀의 2회차 걸그룹 267화.",
                "query": "재벌가 차녀의 2회차 결그룹 유은우",
            },
            {
                "title": "맹인 성녀인데 눈이 보인다 [독점] - 네이버 시리즈",
                "url": "https://series.naver.com/novel/detail.series?productNo=1234567",
                "content": "다른 웹소설의 공식 페이지.",
                "query": "백합 소설",
            },
        ]

        current_profile = pipeline._canonical_work_rescue_strength(
            ctx=ctx,
            title="재벌가 차녀의 2회차 걸그룹",
        )
        replacement_profile = pipeline._canonical_work_rescue_strength(
            ctx=ctx,
            title="맹인 성녀인데 눈이 보인다 [독점]",
        )

        self.assertTrue(current_profile["official_ev"])
        self.assertFalse(
            pipeline._title_surface_mentioned_in_post_main_context(
                ctx,
                "맹인 성녀인데 눈이 보인다 [독점]",
            )
        )
        self.assertTrue(
            pipeline._should_preserve_verified_title_against_unanchored_canonical_override(
                ctx=ctx,
                current_title="재벌가 차녀의 2회차 걸그룹",
                replacement_title="맹인 성녀인데 눈이 보인다 [독점]",
                current_rescue_profile=current_profile,
                replacement_rescue_profile=replacement_profile,
            )
        )

    def test_shared_generic_keyword_does_not_hide_decoder_anchor_drift(self):
        pipeline = _build_pipeline()
        ctx = ConversationContext(
            post_id=9002,
            post_data={"post_id": 9002, "title": "괴담 학교 기숙사 얘기", "content_blocks": []},
            comments=[],
        )
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {"detected_entities": {"possible_titles": ["괴담 학교 기숙사"]}},
        )
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "decoded_terms": [
                    {
                        "original": "괴담 학교 기숙사",
                        "best_match": {
                            "title": "괴담 학교 기숙사",
                            "confidence": "High",
                            "_title_anchor_conflict": True,
                        },
                        "grounding": {"anchor_type": "title_mention"},
                    }
                ]
            },
        )

        drift = pipeline._detect_title_anchor_drift(ctx, official_title="괴담 호텔 탈출기")

        self.assertTrue(drift["is_drift"])
        self.assertEqual(drift["reason"], "decoder_anchor_conflict")

    def test_j11_forced_upgrade_official_title_survives_unverified_alias_replacement(self):
        pipeline = _build_pipeline()
        title = "잘생기면 인생이 편하다"
        ctx = ConversationContext(
            post_id=11713222,
            post_data={
                "post_id": 11713222,
                "title": "현대 하렘물은 진짜 잘쓰는 작가가 손에꼽네",
                "content_blocks": [
                    {"type": "text", "text": "잘생인방보는데 그냥 주인공이 여자를 오나홀로밖에 안보는거같음"},
                    {"type": "text", "text": "뭐 사랑도없고 고백부터 여러여자볼거니 이해해줘식이니까 개아찔하네"},
                ],
            },
            comments=[
                "판타지만 쓰던 작가라서 그런가",
                "전작도 잘생인편으로 현대하렘아님?",
                "그렇네 잘생인편 안봐서 까먹어버림",
            ],
        )
        ctx.suspected_titles = [{"title": "잘생인편", "confidence": "High"}]
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {"detected_entities": {"possible_titles": ["잘생인방", "잘생인편"]}},
        )
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "decoded_terms": [
                    {
                        "original": "잘생인방",
                        "best_match": {
                            "title": "잘생인편",
                            "confidence": "High",
                            "_title_anchor_conflict": True,
                        },
                        "grounding": {"anchor_type": "title_mention"},
                    }
                ]
            },
        )
        ctx.search_results = [
            {
                "title": f"웹소설로 꿈꾸는 세상! - {title} - 노벨피아",
                "url": "https://novelpia.com/novel/300042",
                "content": f"플러스작품 - {title}. 잘생인방으로 불리는 현대 하렘물.",
                "query": "잘생인방 현대 하렘물 웹소설",
            }
        ]

        drift = pipeline._detect_title_anchor_drift(ctx, official_title=title)

        self.assertTrue(drift["is_drift"])
        self.assertEqual(drift["reason"], "decoder_anchor_conflict")
        self.assertEqual(drift["replacement_title"], "잘생인편")
        self.assertTrue(pipeline._has_official_title_evidence(ctx, title))
        self.assertFalse(pipeline._has_official_title_evidence(ctx, "잘생인편"))
        self.assertGreater(pipeline._title_anchor_lexical_overlap(ctx, title), 0.0)
        self.assertTrue(
            pipeline._has_j11_forced_upgrade_official_anchor_lock(
                ctx,
                title,
                {"_forced_upgrade_best_title": title},
                official_title_evidence=True,
            )
        )
        self.assertFalse(
            pipeline._has_j11_forced_upgrade_official_anchor_lock(
                ctx,
                title,
                {},
                official_title_evidence=True,
            )
        )

    def test_stable_alias_conflict_ignores_decoder_descriptor_term(self):
        pipeline = _build_pipeline()
        ctx = ConversationContext(
            post_id=11698880,
            post_data={
                "post_id": 11698880,
                "title": "아생갤 개 존나게 재밌군 ㅇㅇ",
                "content_blocks": [
                    {"type": "text", "text": "가챠펑크 세드릭도 그렇고"},
                    {"type": "text", "text": "일본 씹찐따 주인공 처럼"},
                    {"type": "text", "text": "이런게 아닌 시원시원한 상남자라서"},
                ],
            },
            comments=[],
        )
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "decoded_terms": [
                    {
                        "original": "상남자",
                        "interpretations": [{"type": "general_noun", "value": "상남자"}],
                        "candidates": [{"official_novel_title": None}],
                        "best_match": {"title": None, "confidence": "none"},
                    },
                    {
                        "original": "가챠펑크",
                        "interpretations": [
                            {
                                "type": "novel_title",
                                "value": "가챠 중독자의 퓨전펑크 생활",
                            }
                        ],
                        "best_match": {
                            "title": "가챠 중독자의 퓨전펑크 생활",
                            "confidence": "high",
                        },
                    },
                ]
            },
        )

        self.assertTrue(
            pipeline._decoder_treats_alias_as_non_title_descriptor(
                ctx,
                "상남자",
                canonical_title="상남자 [독점]",
            )
        )
        self.assertFalse(
            pipeline._stable_batch_alias_conflicts_with_official_title(
                ctx,
                alias_text="상남자",
                canonical_title="상남자 [독점]",
                current_title="가챠 중독자의 퓨전펑크 생활",
                hit={"source": "search_evidence_alias_inference", "confidence": 3},
            )
        )

    def test_stable_alias_conflict_ignores_low_fit_title_when_descriptor_context_is_stronger(self):
        pipeline = _build_pipeline()
        ctx = ConversationContext(
            post_id=9160,
            post_data={
                "post_id": 9160,
                "title": "약칭 작품 캐릭터 후기",
                "content_blocks": [
                    {"type": "text", "text": "가챠펑크 세드릭도 그렇고"},
                    {"type": "text", "text": "이런게 아닌 시원시원한 상남자라서"},
                ],
            },
            comments=[],
        )
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "decoded_terms": [
                    {
                        "original": "상남자",
                        "interpretations": [
                            {
                                "type": "general_noun",
                                "value": "상남자",
                                "context_fit": "high",
                            },
                            {
                                "type": "novel_title",
                                "value": "상남자 [독점]",
                                "context_fit": "low",
                            },
                        ],
                        "candidates": [{"official_novel_title": "상남자 [독점]"}],
                        "best_match": {"title": None, "confidence": "none"},
                    },
                    {
                        "original": "가챠펑크",
                        "interpretations": [
                            {
                                "type": "novel_title",
                                "value": "가챠 중독자의 퓨전펑크 생활",
                                "context_fit": "high",
                            }
                        ],
                        "best_match": {
                            "title": "가챠 중독자의 퓨전펑크 생활",
                            "confidence": "high",
                        },
                    },
                ]
            },
        )

        self.assertTrue(
            pipeline._decoder_treats_alias_as_non_title_descriptor(
                ctx,
                "상남자",
                canonical_title="상남자 [독점]",
            )
        )
        self.assertFalse(
            pipeline._stable_batch_alias_conflicts_with_official_title(
                ctx,
                alias_text="상남자",
                canonical_title="상남자 [독점]",
                current_title="가챠 중독자의 퓨전펑크 생활",
                hit={"source": "search_evidence_alias_inference", "confidence": 3},
            )
        )

    def test_stable_alias_conflict_keeps_decoder_title_alias(self):
        pipeline = _build_pipeline()
        ctx = ConversationContext(
            post_id=9004,
            post_data={
                "post_id": 9004,
                "title": "즉사무림 최신화 후기",
                "content_blocks": [{"type": "text", "text": "즉사무림 전개 얘기"}],
            },
            comments=[],
        )
        ctx.set_expert_output(
            ExpertType.DECODER,
            {
                "decoded_terms": [
                    {
                        "original": "즉사무림",
                        "interpretations": [
                            {
                                "type": "novel_title",
                                "value": "즉사기 들고 무림에 떨어지다",
                            }
                        ],
                        "candidates": [
                            {"official_novel_title": "즉사기 들고 무림에 떨어지다"}
                        ],
                        "best_match": {
                            "title": "즉사기 들고 무림에 떨어지다",
                            "confidence": "high",
                        },
                    }
                ]
            },
        )

        self.assertFalse(
            pipeline._decoder_treats_alias_as_non_title_descriptor(
                ctx,
                "즉사무림",
                canonical_title="즉사기 들고 무림에 떨어지다",
            )
        )
        self.assertTrue(
            pipeline._stable_batch_alias_conflicts_with_official_title(
                ctx,
                alias_text="즉사무림",
                canonical_title="즉사기 들고 무림에 떨어지다",
                current_title="즉사수선전",
                hit={"source": "batch_memory", "confidence": 3},
            )
        )

    def test_stable_alias_conflict_bridge_ambiguous_for_attached_slang(self):
        pipeline = _build_pipeline()

        self.assertTrue(
            pipeline._stable_alias_conflict_bridge_is_ambiguous(
                {
                    "slang_insight": {
                        "detected_term": "럽코빙",
                        "decoded_term": "일본 럽코 만화의 부잣집 손녀딸로 빙의했는데 그냥저냥 엑스트라입니다.",
                        "alias_scope": "mixed_unknown",
                        "attached_entity_type": "other",
                        "store_in_slang_db": False,
                        "store_reason": "other_attached_composite",
                    }
                }
            )
        )
        self.assertTrue(
            pipeline._stable_alias_conflict_bridge_is_ambiguous(
                {
                    "slang_insight": {
                        "detected_term": "럽코 빙의물",
                        "decoded_term": "이거 럽코 빙의물인가요",
                        "alias_scope": "work_plus_character",
                        "store_in_slang_db": False,
                        "store_reason": "정식 제목이 포함된 문장형 표면",
                    }
                }
            )
        )
        self.assertFalse(
            pipeline._stable_alias_conflict_bridge_is_ambiguous(
                {
                    "slang_insight": {
                        "detected_term": "즉사무림",
                        "decoded_term": "즉사기 들고 무림에 떨어지다",
                        "alias_scope": "pure_work_alias",
                        "store_in_slang_db": True,
                        "store_reason": "pure_work_alias",
                    }
                }
            )
        )
        self.assertFalse(pipeline._stable_alias_conflict_bridge_is_ambiguous({}))

    def test_stable_alias_conflict_bridge_weak_relation_stays_hold(self):
        pipeline = _build_pipeline()

        weak_relation = {
            "relation_judgment": {
                "relation_type": "work_specific_nickname",
                "discussion_target": "specific_work",
                "promotion_decision": "allow",
                "post_direct_grounding": False,
                "search_support_summary": {
                    "explicit_alias_bridge_count": 0,
                    "closed_bridge": False,
                    "bridge_quality": "weak",
                },
            }
        }
        self.assertTrue(
            pipeline._stable_alias_conflict_bridge_has_weak_relation(weak_relation)
        )

        strong_relation = {
            "relation_judgment": {
                "relation_type": "work_specific_nickname",
                "discussion_target": "specific_work",
                "promotion_decision": "allow",
                "post_direct_grounding": False,
                "search_support_summary": {
                    "explicit_alias_bridge_count": 1,
                    "closed_bridge": False,
                    "bridge_quality": "weak",
                },
            }
        }
        self.assertFalse(
            pipeline._stable_alias_conflict_bridge_has_weak_relation(strong_relation)
        )

        direct_relation = {
            "relation_judgment": {
                "relation_type": "work_specific_nickname",
                "discussion_target": "specific_work",
                "promotion_decision": "allow",
                "post_direct_grounding": True,
                "search_support_summary": {
                    "explicit_alias_bridge_count": 0,
                    "closed_bridge": False,
                    "bridge_quality": "weak",
                },
            }
        }
        self.assertFalse(
            pipeline._stable_alias_conflict_bridge_has_weak_relation(direct_relation)
        )


if __name__ == "__main__":
    unittest.main()
