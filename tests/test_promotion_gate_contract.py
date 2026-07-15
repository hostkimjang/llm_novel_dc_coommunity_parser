from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_batch.agentic_pipeline import AgenticPipeline  # noqa: E402
from llm_batch.grounding.candidate_audit import (  # noqa: E402
    apply_candidate_audit_fields,
    build_candidate_audit_fields,
    has_authoritative_publish_contract,
)
from llm_batch.experts.orchestrator import ConversationContext, ExpertType  # noqa: E402
from llm_batch.domain.models import DetectedTitle  # noqa: E402
from llm_batch.promotion_gate import (  # noqa: E402
    candidate_inventory_evidence_from_sources,
    candidate_inventory_pairs,
    EvidenceRecord,
    GroundingState,
    ScopeState,
    apply_publish_contract,
    can_publish_title,
    evaluate_publish_contract,
    grounding_state_from_dict,
    normalize_blocked_resolution_state,
)
from tools.audit_publication_contract_convergence import audit_rows  # noqa: E402


class DummyLLM:
    pass


class DummyMCP:
    pass


class PromotionGateContractTest(unittest.TestCase):
    @staticmethod
    def _fetched_novel_detail(url: str, title: str, **structured_overrides):
        structured = {
            "title": title,
            "page_title": title,
            "page_type": "novel_page",
            "content_status": "active",
        }
        structured.update(structured_overrides)
        return {"url": url, "structured_info": structured}

    @staticmethod
    def _direct_image_context(
        *,
        post_id: int,
        title: str,
        post_title: str = "",
        body_text: str = "",
    ) -> ConversationContext:
        content_blocks = [{"type": "image", "text": ""}]
        if body_text:
            content_blocks.append({"type": "text", "text": body_text})
        return ConversationContext(
            post_id=post_id,
            post_data={
                "post_id": post_id,
                "title": post_title,
                "content_blocks": content_blocks,
                "image_enrichment": [
                    {
                        "ocr_text": f"{title} 작가명 테스트작가 자유 연재 조회 10 추천 3 4회차",
                        "explicit_work_title": title,
                        "explicit_author_name": "테스트작가",
                        "work_cues": [title, "조회 10", "추천 3", "4회차"],
                        "evidence_type": "explicit_text",
                        "title_role": "work_title",
                        "focus_role": "work_anchor",
                        "screen_type": "work_surface",
                        "surface_type": "official_detail_page",
                        "promotion_eligible": True,
                        "confidence": "High",
                    }
                ],
            },
            comments=[],
        )

    def _decide(self, **overrides):
        state = GroundingState(
            post_id=overrides.pop("post_id", 0),
            candidate_title=overrides.pop("candidate_title", "가챠 중독자의 퓨전펑크 생활"),
            candidate_url=overrides.pop("candidate_url", "https://novelpia.com/novel/387014"),
            source=overrides.pop("source", "contract_test"),
            official_title_exists=overrides.pop("official_title_exists", True),
            row_discusses_work_as_work=overrides.pop("row_discusses_work_as_work", False),
            title_resolution_state=overrides.pop("title_resolution_state", "context_only"),
            work_resolution=overrides.pop("work_resolution", "unresolved"),
            discussion_type=overrides.pop("discussion_type", "community_banter"),
            prior_variance_quarantine=overrides.pop("prior_variance_quarantine", False),
            same_title_source_movement=overrides.pop("same_title_source_movement", False),
            caveated_alias_boundary=overrides.pop("caveated_alias_boundary", False),
            scope=overrides.pop("scope", None),
        )
        self.assertFalse(overrides, f"unused overrides: {overrides}")
        return can_publish_title(
            state,
            [
                EvidenceRecord(
                    kind="official_detail_url",
                    strength="strong",
                    source_path_or_snippet=state.candidate_url,
                    supports_publish=False,
                    reason_code="official_detail_url",
                )
            ],
        )

    def test_11668288_official_exists_but_unstable_row_discussion_is_quarantine(self):
        decision = self._decide(
            post_id=11668288,
            prior_variance_quarantine=True,
            title_resolution_state="nonwork",
        )

        self.assertEqual(decision.status, "quarantine")
        self.assertFalse(decision.publish_allowed)
        self.assertTrue(decision.candidate_preserved)
        self.assertFalse(decision.bypassed_gate)
        self.assertIn("official_title_exists", decision.reason_codes)
        self.assertIn("row_discussion_missing", decision.reason_codes)
        self.assertIn("variance_quarantine", decision.reason_codes)

    def test_11706832_caveated_alias_boundary_needs_direct_work_bridge(self):
        decision = self._decide(
            post_id=11706832,
            candidate_title="황제의 딸로 환생했다",
            candidate_url="https://novelpia.com/novel/318282",
            caveated_alias_boundary=True,
            title_resolution_state="context_only",
        )

        self.assertEqual(decision.status, "candidate_only")
        self.assertFalse(decision.publish_allowed)
        self.assertTrue(decision.candidate_preserved)
        self.assertFalse(decision.bypassed_gate)
        self.assertIn("caveated_alias_boundary", decision.reason_codes)

    def test_11658615_same_title_source_movement_is_not_approval(self):
        decision = self._decide(
            post_id=11658615,
            row_discusses_work_as_work=True,
            discussion_type="review",
            title_resolution_state="resolved",
            work_resolution="resolved",
            same_title_source_movement=True,
        )

        self.assertEqual(decision.status, "quarantine")
        self.assertFalse(decision.publish_allowed)
        self.assertTrue(decision.candidate_preserved)
        self.assertIn("same_title_source_movement", decision.reason_codes)
        self.assertFalse(decision.bypassed_gate)

    def test_prior_variance_rows_are_candidate_only_until_replay_agrees(self):
        for post_id in (11669928, 11674712):
            with self.subTest(post_id=post_id):
                decision = self._decide(
                    post_id=post_id,
                    row_discusses_work_as_work=True,
                    discussion_type="review",
                    title_resolution_state="resolved",
                    work_resolution="resolved",
                    prior_variance_quarantine=True,
                )
                self.assertEqual(decision.status, "quarantine")
                self.assertFalse(decision.publish_allowed)
                self.assertTrue(decision.candidate_preserved)
                self.assertFalse(decision.bypassed_gate)

    def test_11694035_golden_negative_blocks_public_title_without_work_bridge(self):
        decision = self._decide(
            post_id=11694035,
            candidate_title="없음",
            candidate_url="",
            official_title_exists=False,
            title_resolution_state="nonwork",
            work_resolution="none",
        )

        self.assertEqual(decision.status, "candidate_only")
        self.assertFalse(decision.publish_allowed)
        self.assertTrue(decision.candidate_preserved)
        self.assertIn("nonwork", decision.reason_codes)
        self.assertFalse(decision.bypassed_gate)

    def test_candidate_audit_does_not_safe_resolve_gate_blocked_public_title(self):
        blocked_decision = self._decide(post_id=11668288, prior_variance_quarantine=True).to_dict()
        identity = {
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "review",
            "novel_identity": {
                "official_title": "가챠 중독자의 퓨전펑크 생활",
                "heretic_url": "https://novelpia.com/novel/387014",
                "confidence": "High",
            },
            "candidate_ledger": {"promotion_decision": blocked_decision},
        }

        audit = build_candidate_audit_fields(identity, None)

        self.assertEqual(audit["candidate_ledger_status"], "promotion_blocked")
        self.assertFalse(audit["safe_resolved"])
        self.assertEqual(audit["candidate_ledger"]["promotion_decision"]["status"], "quarantine")
        self.assertFalse(audit["candidate_ledger"]["promotion_decision"]["bypassed_gate"])

    def test_agentic_semantic_no_work_gate_records_decision_without_publish(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        title = "가챠 중독자의 퓨전펑크 생활"
        ctx = ConversationContext(
            post_id=11668288,
            post_data={"post_id": 11668288, "title": "가챠펑크 밈인가"},
            comments=["그냥 장갤 밈 아님?"],
        )
        ctx.search_results = [
            {
                "title": title,
                "url": "https://novelpia.com/novel/387014",
                "content": "노벨피아 작품 상세",
            }
        ]
        final_decision = {
            "title_resolution_allowed": False,
            "title_resolution_state": "nonwork",
            "work_resolution": "none",
            "discussion_type": "community_banter",
        }

        old_detail_urls = pipeline._official_detail_exact_title_urls_for_no_work_anchor
        old_find_url = pipeline._find_title_matched_official_url
        old_official_evidence = pipeline._has_official_title_evidence
        pipeline._has_official_title_evidence = lambda *_args, **_kwargs: True
        pipeline._official_detail_exact_title_urls_for_no_work_anchor = (
            lambda *_args, **_kwargs: ["https://novelpia.com/novel/387014"]
        )
        pipeline._find_title_matched_official_url = (
            lambda *_args, **_kwargs: "https://novelpia.com/novel/387014"
        )
        try:
            allowed = pipeline._can_promote_title_after_semantic_no_work(
                ctx,
                title,
                source="official_url_recall_gate",
                final_decision=final_decision,
                verification_result={},
                title_candidates=[],
            )
        finally:
            pipeline._has_official_title_evidence = old_official_evidence
            pipeline._official_detail_exact_title_urls_for_no_work_anchor = old_detail_urls
            pipeline._find_title_matched_official_url = old_find_url

        self.assertFalse(allowed)
        decision = getattr(ctx, "_last_promotion_gate_decision")
        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertFalse(decision["bypassed_gate"])
        self.assertIn("official_detail_url", decision["reason_codes"])
        self.assertIn("row_discussion_missing", decision["reason_codes"])
        self.assertIn("scope_not_current_work", decision["reason_codes"])
        state = final_decision["_promotion_gate_state"]
        self.assertIn(state["scope"]["scope_kind"], {"context_only", "platform_meta_nonwork"})
        self.assertEqual(final_decision["_promotion_gate_decision"]["status"], "candidate_only")

    def test_scope_state_current_work_allows_directly_grounded_publish(self):
        state = GroundingState(
            post_id=11713222,
            candidate_title="잘생기면 편해지는 인방 생활",
            candidate_url="https://novelpia.com/novel/384016",
            source="scope_contract_test",
            official_title_exists=True,
            row_discusses_work_as_work=True,
            title_resolution_state="resolved",
            work_resolution="resolved",
            discussion_type="review",
            scope=ScopeState(
                scope_kind="current_work",
                confidence="high",
                direct_bridge_sources=["direct_body_alias", "official_detail_url"],
                competing_candidates=["잘생기면 인생이 편하다"],
            ),
        )

        decision = can_publish_title(
            state,
            [
                EvidenceRecord(
                    kind="alias_bridge",
                    strength="strong",
                    source_path_or_snippet=state.candidate_title,
                    supports_publish=True,
                    reason_code="alias_bridge",
                    candidate_title=state.candidate_title,
                )
            ],
        )

        self.assertEqual(decision.status, "publish")
        self.assertTrue(decision.publish_allowed)
        self.assertEqual(decision.official_title, "잘생기면 편해지는 인방 생활")
        self.assertIn("scope_current_work", decision.reason_codes)
        self.assertNotIn("scope_not_current_work", decision.reason_codes)
        self.assertFalse(decision.bypassed_gate)

    def test_v2_contract_is_deeply_frozen_and_has_stable_input_fingerprint(self):
        state = GroundingState(
            post_id=1,
            candidate_title="테스트 작품",
            source="frozen_contract_test",
            official_title_exists=True,
            row_discusses_work_as_work=True,
            scope=ScopeState(
                scope_kind="current_work",
                confidence="high",
                direct_bridge_sources=["explicit_alias_relation"],
            ),
        )
        evidence = [
            EvidenceRecord(
                kind="alias_bridge",
                strength="strong",
                source_path_or_snippet="테스트 작품",
                supports_publish=True,
                reason_code="alias_bridge",
                candidate_title="테스트 작품",
            )
        ]

        first = evaluate_publish_contract(state, evidence)
        second = evaluate_publish_contract(state, evidence)

        self.assertEqual(first.input_fingerprint, second.input_fingerprint)
        self.assertEqual(len(first.input_fingerprint), 64)
        self.assertIsInstance(first.evidence, tuple)
        self.assertIsInstance(first.state.scope.direct_bridge_sources, tuple)
        self.assertIsInstance(first.decision.reason_codes, tuple)
        with self.assertRaises(FrozenInstanceError):
            first.decision.publish_allowed = False
        with self.assertRaises(AttributeError):
            first.state.scope.direct_bridge_sources.append("forged")

    def test_serialized_post_gate_context_cannot_change_deterministic_trace(self):
        state = GroundingState(
            post_id=10,
            candidate_title="테스트 작품",
            source="deterministic_trace_test",
            official_title_exists=True,
            row_discusses_work_as_work=True,
            title_resolution_state="resolved",
            work_resolution="resolved",
            scope=ScopeState(
                scope_kind="current_work",
                confidence="high",
                direct_bridge_sources=["explicit_alias_relation"],
            ),
        )
        evidence = [
            EvidenceRecord(
                kind="alias_bridge",
                supports_publish=True,
                candidate_title=state.candidate_title,
                source_path_or_snippet=state.candidate_title,
            )
        ]

        clean = evaluate_publish_contract(state, evidence)
        forged = evaluate_publish_contract(
            state,
            evidence,
            post_gate_context={
                "title_resolution_allowed": False,
                "title_resolution_state": "context_only",
                "work_resolution": "unresolved",
            },
        )

        self.assertEqual(forged.trace.to_dict(), clean.trace.to_dict())
        self.assertTrue(forged.trace.post_gate_identity.title_resolution_allowed)
        self.assertEqual(forged.trace.post_gate_identity.title_resolution_state, "resolved")
        self.assertEqual(forged.trace.post_gate_identity.work_resolution, "resolved")

    def test_missing_scope_fails_closed_even_when_caller_claims_current_work(self):
        state = GroundingState(
            post_id=2,
            candidate_title="테스트 작품",
            source="missing_scope_test",
            official_title_exists=True,
            row_discusses_work_as_work=True,
            scope=None,
        )
        decision = can_publish_title(
            state,
            [
                EvidenceRecord(
                    kind="alias_bridge",
                    supports_publish=True,
                    candidate_title="테스트 작품",
                    source_path_or_snippet="테스트 작품",
                )
            ],
        )

        self.assertFalse(decision.publish_allowed)
        self.assertTrue(decision.candidate_preserved)
        self.assertFalse(decision.bypassed_gate)
        self.assertIn("fail_closed_scope_missing", decision.reason_codes)
        self.assertIn("scope_not_current_work", decision.reason_codes)

    def test_candidate_bound_evidence_prevents_competing_title_switch(self):
        state = GroundingState(
            post_id=3,
            candidate_title="현재 후보",
            source="competing_candidate_test",
            official_title_exists=True,
            row_discusses_work_as_work=True,
            scope=ScopeState(
                scope_kind="current_work",
                confidence="high",
                direct_bridge_sources=["explicit_alias_relation"],
                competing_candidates=["경쟁 후보"],
            ),
        )
        decision = can_publish_title(
            state,
            [
                EvidenceRecord(
                    kind="alias_bridge",
                    supports_publish=True,
                    candidate_title="경쟁 후보",
                    source_path_or_snippet="경쟁 후보",
                )
            ],
        )

        self.assertEqual(decision.status, "hold")
        self.assertFalse(decision.publish_allowed)
        self.assertTrue(decision.candidate_preserved)
        self.assertFalse(decision.bypassed_gate)

    def test_url_requires_candidate_bound_pair_evidence_but_title_can_publish(self):
        state = GroundingState(
            post_id=4,
            candidate_title="테스트 작품",
            candidate_url="https://series.naver.com/novel/detail.series?productNo=123&utm_source=x",
            source="url_pair_test",
            official_title_exists=True,
            row_discusses_work_as_work=True,
            scope=ScopeState(
                scope_kind="current_work",
                confidence="high",
                direct_bridge_sources=["explicit_alias_relation"],
            ),
        )
        bridge = EvidenceRecord(
            kind="alias_bridge",
            supports_publish=True,
            candidate_title=state.candidate_title,
            source_path_or_snippet=state.candidate_title,
        )

        missing = can_publish_title(state, [bridge])
        verified = can_publish_title(
            state,
            [
                bridge,
                EvidenceRecord(
                    kind="official_detail_url",
                    candidate_title=state.candidate_title,
                    candidate_url="https://series.naver.com/novel/detail.series?utm_campaign=y&productNo=123",
                    source_path_or_snippet="https://series.naver.com/novel/detail.series?productNo=123",
                    title_url_match=True,
                ),
            ],
        )

        self.assertTrue(missing.publish_allowed)
        self.assertIsNone(missing.official_url)
        self.assertIn("official_url_evidence_missing", missing.reason_codes)
        self.assertTrue(verified.publish_allowed)
        self.assertEqual(verified.official_url, state.candidate_url)
        self.assertIn("title_url_pair_verified", verified.reason_codes)

    def test_bound_url_mismatch_withholds_url_without_losing_safe_title(self):
        state = GroundingState(
            post_id=5,
            candidate_title="테스트 작품",
            candidate_url="https://novelpia.com/novel/123?sid=main5",
            source="url_mismatch_test",
            official_title_exists=True,
            row_discusses_work_as_work=True,
            scope=ScopeState(
                scope_kind="current_work",
                confidence="high",
                direct_bridge_sources=["explicit_alias_relation"],
            ),
        )
        decision = can_publish_title(
            state,
            [
                EvidenceRecord(
                    kind="alias_bridge",
                    supports_publish=True,
                    candidate_title=state.candidate_title,
                    source_path_or_snippet=state.candidate_title,
                ),
                EvidenceRecord(
                    kind="official_detail_url",
                    candidate_title=state.candidate_title,
                    candidate_url="https://novelpia.com/novel/123",
                    source_path_or_snippet="https://novelpia.com/novel/123",
                    title_url_match=False,
                ),
            ],
        )

        self.assertTrue(decision.publish_allowed)
        self.assertEqual(decision.official_title, state.candidate_title)
        self.assertIsNone(decision.official_url)
        self.assertFalse(decision.candidate_preserved)
        self.assertFalse(decision.bypassed_gate)
        self.assertIn("official_url_withheld_by_title_mismatch", decision.reason_codes)

    def test_context_only_alias_and_golden_ocr_candidate_are_preserved_without_publish(self):
        cases = [
            (11694035, "아카데미 생존 갤러리", "아생갤", "context_only"),
            (11663540, "전 버디가 하고 싶은데요", "OCR", "image_ocr_derived_work"),
        ]
        for post_id, candidate_title, surface, scope_kind in cases:
            with self.subTest(post_id=post_id):
                state = GroundingState(
                    post_id=post_id,
                    candidate_title=candidate_title,
                    source="candidate_preservation_test",
                    official_title_exists=True,
                    row_discusses_work_as_work=False,
                    scope=ScopeState(
                        scope_kind=scope_kind,
                        confidence="low",
                        direct_bridge_sources=[surface],
                    ),
                )
                contract = evaluate_publish_contract(
                    state,
                    [
                        EvidenceRecord(
                            kind="candidate_surface",
                            source_path_or_snippet=surface,
                            supports_publish=False,
                            candidate_title=candidate_title,
                        )
                    ],
                )
                identity = {
                    "official_title": "stale",
                    "official_url": "https://example.invalid/stale",
                    "novel_identity": {
                        "official_title": "stale",
                        "heretic_url": "https://example.invalid/stale",
                        "confidence": "Low",
                    },
                }

                apply_publish_contract(identity, contract)

                self.assertFalse(contract.decision.publish_allowed)
                self.assertTrue(contract.decision.candidate_preserved)
                self.assertFalse(contract.decision.bypassed_gate)
                self.assertIsNone(identity["official_title"])
                self.assertIsNone(identity["official_url"])
                self.assertIsNone(identity["novel_identity"]["official_title"])
                self.assertEqual(identity["blocked_official_title"], candidate_title)
                self.assertEqual(
                    identity["candidate_ledger"]["blocked_official_title"],
                    candidate_title,
                )
                self.assertEqual(
                    identity["publish_contract_input_fingerprint"],
                    contract.input_fingerprint,
                )

    def test_source_native_official_detail_url_is_identity_only_and_search_only_is_not_source(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        title = "소스 URL 작품"
        url = "https://novelpia.com/novel/123456"
        candidate = DetectedTitle(
            official_title=title,
            heretic_url=url,
            confidence="High",
            source_tier="official_detail",
            reference_role="primary",
        )
        source_ctx = ConversationContext(
            post_id=11663514,
            post_data={
                "post_id": 11663514,
                "title": "이 링크 쪽 이야기",
                "content_blocks": [{"type": "link", "url": url}],
            },
            comments=[],
        )
        search_only_ctx = ConversationContext(
            post_id=11663514,
            post_data={"post_id": 11663514, "title": "이 링크 쪽 이야기"},
            comments=[],
        )
        search_only_ctx.search_results = [
            {"title": title, "url": url, "content": "official detail"}
        ]

        source_bridge = pipeline._post_discusses_work_as_work(
            source_ctx,
            title,
            source="resolved_public_title_scope",
            title_candidates=[candidate],
        )
        search_only_bridge = pipeline._post_discusses_work_as_work(
            search_only_ctx,
            title,
            source="resolved_public_title_scope",
            title_candidates=[candidate],
        )
        decision = pipeline._record_resolved_public_title_gate_decision(
            source_ctx,
            title,
            candidate_url=url,
            final_decision={
                "work_resolution": "resolved",
                "title_resolution_state": "resolved",
                "title_resolution_allowed": True,
                "is_resolved_work_discussion": True,
                "discussion_type": "review",
            },
            verification_result={},
            title_candidates=[candidate],
            resolution_scope_fields={
                "work_resolution": "resolved",
                "title_resolution_state": "resolved",
                "title_resolution_allowed": True,
                "is_resolved_work_discussion": True,
            },
        )

        self.assertFalse(source_bridge)
        self.assertFalse(search_only_bridge)
        self.assertFalse(decision["publish_allowed"])
        self.assertTrue(decision["candidate_preserved"])
        self.assertFalse(decision["bypassed_gate"])

    def test_source_native_identity_uses_body_url_and_fetched_canonical_title(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        url = "https://novel.munpia.com/486006"
        ctx = ConversationContext(
            post_id=20020001,
            post_data={
                "title": "표면 제목은 다른 드립",
                "content_blocks": [
                    {"type": "text", "text": url},
                    {"type": "text", "text": "작품 설정과 캐릭터를 소개합니다"},
                ],
            },
            comments=[],
        )
        ctx.fetched_page_info = [
            self._fetched_novel_detail(url, "마탄 속의 제국")
        ]

        with patch.object(
            pipeline,
            "_summarize_url_page_state",
            return_value={
                "has_fetched_entry": True,
                "has_active_detail_like": True,
                "is_novel_page": True,
                "content_statuses": ["active"],
                "is_deleted_or_unavailable": False,
                "is_community_post": False,
                "is_listing": False,
            },
        ), patch.object(
            pipeline,
            "_is_title_matched_non_novel_media_url",
            return_value=False,
        ):
            identity = pipeline._source_native_official_detail_identity(ctx)

        self.assertEqual(identity["title"], "마탄 속의 제국")
        self.assertEqual(identity["url"], url)

    def test_direct_image_identity_without_non_image_relation_stays_hold(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        title = "이미지에만 적힌 작품"
        candidate = DetectedTitle(
            official_title=title,
            heretic_url="https://novelpia.com/novel/20020002",
            confidence="High",
            source_tier="official_detail",
        )
        ctx = ConversationContext(
            post_id=20020002,
            post_data={
                "title": "이 작가 도대체 뭘 쓴 거야",
                "content_blocks": [{"type": "text", "text": "이런 것도 썼어요?"}],
            },
            comments=[],
        )

        with patch.object(
            pipeline, "_has_low_specificity_alias_nonwork_context_block", return_value=False
        ), patch.object(
            pipeline, "_platform_meta_image_title_requires_hold", return_value=False
        ), patch.object(
            pipeline, "_non_novel_media_blocks_work_bridge", return_value=False
        ), patch.object(
            pipeline, "_image_scene_only_candidate_lacks_publish_surface", return_value=False
        ), patch.object(
            pipeline,
            "_has_candidate_bound_non_image_alias_official_detail_bridge",
            return_value=False,
        ), patch.object(
            pipeline, "_has_structured_direct_image_work_surface_evidence", return_value=True
        ), patch.object(
            pipeline, "_has_ocr_catalog_official_title_evidence", return_value=True
        ):
            discusses = pipeline._post_discusses_work_as_work(
                ctx,
                title,
                source="direct_image_work_surface_lock",
                title_candidates=[candidate],
            )

        self.assertFalse(discusses)

    def test_general_title_quality_blocker_is_enforced_inside_shared_contract(self):
        title = "웹소설로 꿈꾸는 세상! - 노벨피아"
        state = GroundingState(
            post_id=6,
            candidate_title=title,
            source="candidate_quality_test",
            official_title_exists=True,
            row_discusses_work_as_work=True,
            scope=ScopeState(
                scope_kind="current_work",
                confidence="high",
                direct_bridge_sources=["direct_source_official_detail_url"],
            ),
        )
        decision = can_publish_title(
            state,
            [
                EvidenceRecord(
                    kind="direct_source_official_detail_url",
                    source_path_or_snippet=title,
                    supports_publish=True,
                    candidate_title=title,
                ),
                EvidenceRecord(
                    kind="candidate_quality_blocker",
                    source_path_or_snippet=title,
                    supports_publish=False,
                    reason_code="official_title_looks_like_search_snippet",
                    candidate_title=title,
                ),
            ],
        )

        self.assertFalse(decision.publish_allowed)
        self.assertTrue(decision.candidate_preserved)
        self.assertFalse(decision.bypassed_gate)
        self.assertIn("official_title_looks_like_search_snippet", decision.reason_codes)

    def test_current_work_scope_cannot_override_explicit_context_only_resolution(self):
        state = GroundingState(
            post_id=11679547,
            candidate_title="테스트 작품",
            candidate_url="https://novelpia.com/novel/1",
            source="scope_reason_normalization_test",
            official_title_exists=True,
            row_discusses_work_as_work=True,
            title_resolution_state="context_only",
            work_resolution="context_only",
            discussion_type="community_banter",
            scope=ScopeState(
                scope_kind="current_work",
                confidence="high",
                direct_bridge_sources=["row_discusses_work_as_work"],
            ),
        )

        decision = can_publish_title(
            state,
            [
                EvidenceRecord(
                    kind="work_bridge",
                    strength="strong",
                    source_path_or_snippet=state.candidate_title,
                    supports_publish=True,
                    reason_code="row_discusses_work_as_work",
                    candidate_title=state.candidate_title,
                )
            ],
        )

        self.assertEqual(decision.status, "candidate_only")
        self.assertFalse(decision.publish_allowed)
        self.assertTrue(decision.candidate_preserved)
        self.assertIn("row_discusses_work_as_work", decision.reason_codes)
        self.assertIn("scope_current_work", decision.reason_codes)
        self.assertIn("title_resolution_state_not_publishable", decision.reason_codes)
        self.assertIn("work_resolution_not_publishable", decision.reason_codes)
        self.assertNotIn("context_only", decision.reason_codes)
        self.assertNotIn("community_banter", decision.reason_codes)
        self.assertNotIn("scope_not_current_work", decision.reason_codes)

    def test_current_work_scope_cannot_publish_unresolved_work_state(self):
        state = GroundingState(
            post_id=11716475,
            candidate_title="일편독심[一片毒心]",
            candidate_url="https://novelpia.com/novel/84",
            source="official_url_recall_gate",
            official_title_exists=True,
            row_discusses_work_as_work=True,
            title_resolution_state="resolved",
            work_resolution="unresolved",
            discussion_type="review",
            scope=ScopeState(
                scope_kind="current_work",
                confidence="high",
                direct_bridge_sources=["row_discusses_work_as_work"],
            ),
        )

        decision = can_publish_title(
            state,
            [
                EvidenceRecord(
                    kind="work_bridge",
                    strength="strong",
                    source_path_or_snippet=state.candidate_title,
                    supports_publish=True,
                    reason_code="row_discusses_work_as_work",
                    candidate_title=state.candidate_title,
                )
            ],
        )

        self.assertEqual(decision.status, "candidate_only")
        self.assertFalse(decision.publish_allowed)
        self.assertTrue(decision.candidate_preserved)
        self.assertIn("work_resolution_not_publishable", decision.reason_codes)
        self.assertNotIn("title_resolution_state_not_publishable", decision.reason_codes)

    def test_canonical_contract_normalizes_blocked_resolution_and_mirrors_both_reasons(self):
        state = GroundingState(
            post_id=11716475,
            candidate_title="일편독심[一片毒心]",
            candidate_url="https://novelpia.com/novel/84",
            source="official_url_recall_gate",
            official_title_exists=True,
            row_discusses_work_as_work=True,
            title_resolution_state="resolved",
            work_resolution="unresolved",
            discussion_type="review",
            scope=ScopeState(
                scope_kind="current_work",
                confidence="high",
                direct_bridge_sources=["row_discusses_work_as_work"],
            ),
        )
        evidence = [
            EvidenceRecord(
                kind="work_bridge",
                strength="strong",
                source_path_or_snippet=state.candidate_title,
                supports_publish=True,
                reason_code="row_discusses_work_as_work",
                candidate_title=state.candidate_title,
            )
        ]

        contract = evaluate_publish_contract(state, evidence)
        identity = {"novel_identity": {"official_title": state.candidate_title}}
        apply_publish_contract(identity, contract)

        self.assertEqual(contract.state.title_resolution_state, "unresolved_matchable")
        self.assertFalse(contract.decision.publish_allowed)
        self.assertIn(
            "blocked_candidate_resolution_state_normalized",
            contract.decision.reason_codes,
        )
        self.assertIn(
            "title_resolution_state_not_publishable",
            contract.decision.reason_codes,
        )
        self.assertIn("work_resolution_not_publishable", contract.decision.reason_codes)
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertEqual(
            identity["candidate_ledger"]["promotion_decision"],
            identity["promotion_decision"],
        )

    def test_current_work_scope_still_publishes_resolved_state(self):
        state = GroundingState(
            post_id=11714907,
            candidate_title="아카데미 생존 갤러리",
            candidate_url="https://novelpia.com/novel/380218",
            source="resolved_state_control",
            official_title_exists=True,
            row_discusses_work_as_work=True,
            title_resolution_state="resolved",
            work_resolution="resolved",
            discussion_type="review",
            scope=ScopeState(
                scope_kind="current_work",
                confidence="high",
                direct_bridge_sources=["row_discusses_work_as_work"],
            ),
        )

        decision = can_publish_title(
            state,
            [
                EvidenceRecord(
                    kind="work_bridge",
                    strength="strong",
                    source_path_or_snippet=state.candidate_title,
                    supports_publish=True,
                    reason_code="row_discusses_work_as_work",
                    candidate_title=state.candidate_title,
                )
            ],
        )

        self.assertEqual(decision.status, "publish")
        self.assertTrue(decision.publish_allowed)
        self.assertNotIn("title_resolution_state_not_publishable", decision.reason_codes)
        self.assertNotIn("work_resolution_not_publishable", decision.reason_codes)

    def test_current_work_scope_blocks_every_explicit_hold_title_state(self):
        for title_state in (
            "unresolved_matchable",
            "unresolvable_memory_query",
            "context_only",
            "author_new_work_context",
            "ocr_explicit_title_unresolved",
            "multi_work",
            "adjacent",
            "nonwork",
            "technical_missing",
            "future_hold_state",
        ):
            with self.subTest(title_resolution_state=title_state):
                state = GroundingState(
                    post_id=11714907,
                    candidate_title="아카데미 생존 갤러리",
                    official_title_exists=True,
                    row_discusses_work_as_work=True,
                    title_resolution_state=title_state,
                    work_resolution="resolved",
                    discussion_type="review",
                    scope=ScopeState(
                        scope_kind="current_work",
                        confidence="high",
                        direct_bridge_sources=["row_discusses_work_as_work"],
                    ),
                )
                decision = can_publish_title(
                    state,
                    [
                        EvidenceRecord(
                            kind="work_bridge",
                            strength="strong",
                            source_path_or_snippet=state.candidate_title,
                            supports_publish=True,
                            reason_code="row_discusses_work_as_work",
                            candidate_title=state.candidate_title,
                        )
                    ],
                )

                self.assertEqual(decision.status, "candidate_only")
                self.assertFalse(decision.publish_allowed)
                self.assertTrue(decision.candidate_preserved)
                self.assertIn(
                    "title_resolution_state_not_publishable",
                    decision.reason_codes,
                )

    def test_current_work_scope_blocks_every_explicit_nonresolved_work_state(self):
        for work_state in (
            "unresolved",
            "multi_work",
            "none",
            "hold",
            "hold_unresolved",
            "future_hold_state",
        ):
            with self.subTest(work_resolution=work_state):
                state = GroundingState(
                    post_id=11714907,
                    candidate_title="아카데미 생존 갤러리",
                    official_title_exists=True,
                    row_discusses_work_as_work=True,
                    title_resolution_state="resolved",
                    work_resolution=work_state,
                    discussion_type="review",
                    scope=ScopeState(
                        scope_kind="current_work",
                        confidence="high",
                        direct_bridge_sources=["row_discusses_work_as_work"],
                    ),
                )
                decision = can_publish_title(
                    state,
                    [
                        EvidenceRecord(
                            kind="work_bridge",
                            strength="strong",
                            source_path_or_snippet=state.candidate_title,
                            supports_publish=True,
                            reason_code="row_discusses_work_as_work",
                            candidate_title=state.candidate_title,
                        )
                    ],
                )

                self.assertEqual(decision.status, "candidate_only")
                self.assertFalse(decision.publish_allowed)
                self.assertTrue(decision.candidate_preserved)
                self.assertIn("work_resolution_not_publishable", decision.reason_codes)

    def test_noncurrent_scope_normalizes_row_discussion_marker(self):
        state = GroundingState(
            post_id=11700483,
            candidate_title="테스트 작품",
            candidate_url="https://novelpia.com/novel/2",
            source="scope_reason_normalization_test",
            official_title_exists=True,
            row_discusses_work_as_work=True,
            title_resolution_state="context_only",
            work_resolution="context_only",
            discussion_type="community_banter",
            scope=ScopeState(
                scope_kind="context_only",
                confidence="medium",
                conflict_reason_codes=["scope_context_only"],
            ),
        )

        decision = can_publish_title(state)

        self.assertEqual(decision.status, "candidate_only")
        self.assertIn("row_discussion_present_noncurrent_scope", decision.reason_codes)
        self.assertIn("scope_context_only", decision.reason_codes)
        self.assertIn("scope_not_current_work", decision.reason_codes)
        self.assertNotIn("row_discusses_work_as_work", decision.reason_codes)
        self.assertNotIn("scope_current_work", decision.reason_codes)

    def test_scope_state_unknown_blocks_11669928_title_lead_until_contract_confirms_current_work(self):
        decision = self._decide(
            post_id=11669928,
            candidate_title="탑의 성좌들이 날 애호한다",
            candidate_url="https://novelpia.com/novel/377032",
            row_discusses_work_as_work=True,
            discussion_type="review",
            title_resolution_state="resolved",
            work_resolution="resolved",
            scope=ScopeState(
                scope_kind="unknown",
                confidence="low",
                direct_bridge_sources=["title_lead_alias", "official_detail_url"],
                conflict_reason_codes=["scope_unconfirmed_discontinued_context"],
            ),
        )

        self.assertEqual(decision.status, "candidate_only")
        self.assertFalse(decision.publish_allowed)
        self.assertTrue(decision.candidate_preserved)
        self.assertIn("scope_unknown", decision.reason_codes)
        self.assertIn("scope_not_current_work", decision.reason_codes)
        self.assertIn("scope_unconfirmed_discontinued_context", decision.reason_codes)

    def test_scope_state_previous_work_blocks_11713222_comment_candidate(self):
        decision = self._decide(
            post_id=11713222,
            candidate_title="잘생기면 인생이 편하다",
            candidate_url="https://novelpia.com/novel/300042",
            row_discusses_work_as_work=True,
            discussion_type="review",
            title_resolution_state="resolved",
            work_resolution="resolved",
            scope=ScopeState(
                scope_kind="previous_work",
                confidence="high",
                direct_bridge_sources=["comment_previous_work_alias", "official_detail_url"],
                competing_candidates=["잘생기면 편해지는 인방 생활"],
                conflict_reason_codes=["current_work_candidate_competes_with_previous_work"],
            ),
        )

        self.assertEqual(decision.status, "candidate_only")
        self.assertFalse(decision.publish_allowed)
        self.assertTrue(decision.candidate_preserved)
        self.assertIn("scope_previous_work", decision.reason_codes)
        self.assertIn("scope_not_current_work", decision.reason_codes)
        self.assertIn("current_work_candidate_competes_with_previous_work", decision.reason_codes)

    def test_scope_state_image_ocr_candidate_blocks_11695623_until_row_scope_is_confirmed(self):
        decision = self._decide(
            post_id=11695623,
            candidate_title="[림월드]변방계에서 회귀자로 살아남기",
            candidate_url="",
            row_discusses_work_as_work=True,
            discussion_type="review",
            title_resolution_state="resolved",
            work_resolution="resolved",
            scope=ScopeState(
                scope_kind="image_ocr_derived_work",
                confidence="medium",
                direct_bridge_sources=["ocr_title"],
                competing_candidates=["그래-맞아"],
                conflict_reason_codes=["packet_candidate_variance"],
            ),
        )

        self.assertEqual(decision.status, "candidate_only")
        self.assertFalse(decision.publish_allowed)
        self.assertTrue(decision.candidate_preserved)
        self.assertIn("scope_image_ocr_derived_work", decision.reason_codes)
        self.assertIn("packet_candidate_variance", decision.reason_codes)

    def test_acknowledged_previous_work_override_records_scope_gate_candidate_only(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        ctx = ConversationContext(
            post_id=11713222,
            post_data={"post_id": 11713222, "title": "잘생편 얘기"},
            comments=["전작 잘생기면 인생이 편하다 쪽 별칭도 같이 언급됨"],
        )
        final_decision = {}
        state = GroundingState(
            post_id=11713222,
            candidate_title="잘생기면 인생이 편하다",
            candidate_url="https://novelpia.com/novel/300042",
            source="acknowledged_previous_work_comment_override",
            official_title_exists=True,
            row_discusses_work_as_work=False,
            title_resolution_state="context_only",
            work_resolution="multi_work",
            discussion_type="review",
            scope=ScopeState(
                scope_kind="previous_work",
                confidence="medium",
                direct_bridge_sources=["comment_previous_work_alias", "official_detail_url"],
                competing_candidates=["잘생기면 편해지는 인방 생활"],
                conflict_reason_codes=["current_work_candidate_competes_with_previous_work"],
            ),
        )

        decision = pipeline._record_public_title_gate_decision(
            ctx,
            state,
            [
                EvidenceRecord(
                    kind="comment_previous_work_alias",
                    strength="strong",
                    source_path_or_snippet="잘생기면",
                    supports_publish=False,
                    reason_code="comment_previous_work_alias",
                ),
                EvidenceRecord(
                    kind="official_detail_url",
                    strength="strong",
                    source_path_or_snippet="https://novelpia.com/novel/300042",
                    supports_publish=False,
                    reason_code="official_detail_url",
                ),
            ],
            final_decision=final_decision,
        )

        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertFalse(decision["bypassed_gate"])
        self.assertEqual(
            final_decision["_promotion_gate_state"]["scope"]["scope_kind"],
            "previous_work",
        )
        self.assertIn("scope_not_current_work", decision["reason_codes"])
        self.assertIn(
            "current_work_candidate_competes_with_previous_work",
            decision["reason_codes"],
        )
        self.assertEqual(getattr(ctx, "_last_promotion_gate_decision"), decision)

    def test_batch_alias_public_title_records_current_scope_gate(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        ctx = ConversationContext(
            post_id=11660257,
            post_data={"post_id": 11660257, "title": "암보스 봤는데 좋음"},
            comments=[],
        )
        candidate = DetectedTitle(
            official_title="암흑가 보스요? 제가요?",
            heretic_url="https://novelpia.com/novel/384111",
            confidence="High",
            alias_or_mention="암보스",
            source_tier="official_detail",
            reference_role="primary",
        )
        hit = {
            "alias": "암보스",
            "source": "batch_memory",
            "matched_url": "https://novelpia.com/novel/384111",
        }
        final_decision = {
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
            "discussion_type": "general",
        }

        decision = pipeline._record_batch_alias_public_title_gate_decision(
            ctx,
            candidate,
            hit,
            final_decision=final_decision,
            verification_result={},
        )

        self.assertEqual(decision["status"], "publish")
        self.assertTrue(decision["publish_allowed"])
        self.assertFalse(decision["bypassed_gate"])
        self.assertIn("scope_current_work", decision["reason_codes"])
        self.assertIn("batch_alias_public_title_bridge", decision["reason_codes"])
        self.assertEqual(
            final_decision["_promotion_gate_state"]["scope"]["scope_kind"],
            "current_work",
        )
        self.assertIn(
            "batch_alias_candidate_accepted",
            final_decision["_promotion_gate_state"]["scope"]["direct_bridge_sources"],
        )
        self.assertEqual(getattr(ctx, "_last_promotion_gate_decision"), decision)

    def test_direct_image_work_surface_records_current_scope_gate(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        ocr_title = "여대생 가랑이 사이 무릎 꿇은 엄마들"
        ctx = ConversationContext(
            post_id=11716480,
            post_data={
                "post_id": 11716480,
                "title": "아오 포티햄",
                "content_blocks": [{"type": "image", "text": ""}],
                "image_enrichment": [
                    {
                        "ocr_text": f"{ocr_title} 작가명 후타보로 자유 연재 조회 335 추천 14 4회차",
                        "explicit_work_title": ocr_title,
                        "explicit_author_name": "후타보로",
                        "work_cues": [ocr_title, "조회 335", "추천 14", "4회차"],
                        "evidence_type": "explicit_text",
                        "title_role": "work_title",
                        "focus_role": "work_anchor",
                        "screen_type": "work_surface",
                        "surface_type": "official_detail_page",
                        "promotion_eligible": True,
                        "confidence": "High",
                    }
                ],
            },
            comments=[],
        )
        final_decision = {
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
            "discussion_type": "review",
        }

        decision = pipeline._record_direct_image_work_surface_gate_decision(
            ctx,
            ocr_title,
            final_decision=final_decision,
            verification_result={},
        )

        self.assertEqual(decision["status"], "publish")
        self.assertTrue(decision["publish_allowed"])
        self.assertFalse(decision["bypassed_gate"])
        self.assertIn("scope_current_work", decision["reason_codes"])
        self.assertIn("direct_image_work_surface_bridge", decision["reason_codes"])
        self.assertIn("ocr_catalog_official_title", decision["reason_codes"])
        self.assertEqual(
            final_decision["_promotion_gate_state"]["scope"]["scope_kind"],
            "current_work",
        )
        self.assertIn(
            "direct_image_work_surface_lock",
            final_decision["_promotion_gate_state"]["scope"]["direct_bridge_sources"],
        )
        self.assertIn(
            "ocr_catalog_official_title",
            final_decision["_promotion_gate_state"]["scope"]["direct_bridge_sources"],
        )
        self.assertEqual(getattr(ctx, "_last_promotion_gate_decision"), decision)

    def test_direct_image_webtoon_media_is_candidate_hold_for_novel_parser(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        title = "그레이스 길들이기"
        ctx = ConversationContext(
            post_id=11682761,
            post_data={
                "post_id": 11682761,
                "title": "목마 도대체 뭘쓴거야",
                "content_blocks": [{"type": "image", "text": ""}],
                "image_enrichment": [
                    {
                        "ocr_text": (
                            "그레이스 길들이기 웹툰 · GL · 전체 46 · 완결 · "
                            "목마, 서림 시대극 GL 주종관계 백합 드라마"
                        ),
                        "explicit_work_title": title,
                        "explicit_author_name": "목마",
                        "work_cues": [title, "웹툰", "전체 46", "완결"],
                        "evidence_type": "explicit_text",
                        "title_role": "work_title",
                        "focus_role": "work_anchor",
                        "screen_type": "work_surface",
                        "surface_type": "official_detail_page",
                        "promotion_eligible": True,
                        "confidence": "High",
                    }
                ],
            },
            comments=["내가아는 목마가 맞음?"],
        )
        ctx.search_results = [
            {
                "eid": "E001",
                "title": "그레이스 길들이기 [GL] - 웹툰 - 카카오페이지",
                "url": "https://page.kakao.com/content/53590339?tab_type=about",
                "content": "서림, 목마. 웹툰. GL. 전체 46화 완결.",
                "source_tier": "non_novel_media_platform",
            }
        ]
        final_decision = {
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
            "discussion_type": "review",
        }

        self.assertTrue(pipeline._has_structured_direct_image_work_surface_evidence(ctx, title))
        self.assertTrue(pipeline._has_ocr_catalog_official_title_evidence(ctx, title))
        self.assertTrue(pipeline._has_non_novel_media_evidence_for_title(ctx, title))
        self.assertFalse(
            pipeline._has_specific_work_non_novel_media_exemption(ctx, title, {})
        )

        late_gate_decision = {}
        self.assertFalse(
            pipeline._can_promote_title_after_semantic_no_work(
                ctx,
                title,
                source="direct_image_work_surface_lock",
                final_decision=late_gate_decision,
                verification_result={},
                title_candidates=[
                    DetectedTitle(
                        official_title=title,
                        heretic_url="https://page.kakao.com/content/53590339?tab_type=about",
                        confidence="High",
                        source_tier="mixed",
                    )
                ],
            )
        )
        self.assertEqual(
            late_gate_decision["_promotion_gate_state"]["scope"]["scope_kind"],
            "platform_meta_nonwork",
        )
        self.assertIn(
            "non_novel_media_evidence",
            late_gate_decision["_promotion_gate_decision"]["reason_codes"],
        )

        decision = pipeline._record_direct_image_work_surface_gate_decision(
            ctx,
            title,
            candidate_url="https://page.kakao.com/content/53590339?tab_type=about",
            final_decision=final_decision,
            verification_result={},
        )

        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertTrue(decision["candidate_preserved"])
        self.assertFalse(decision["bypassed_gate"])
        self.assertEqual(
            final_decision["_promotion_gate_state"]["scope"]["scope_kind"],
            "platform_meta_nonwork",
        )
        self.assertIn("non_novel_media_evidence", decision["reason_codes"])

    def test_direct_image_webnovel_ocr_remains_publishable(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        title = "전 버튜버가 하고 싶은데요"
        url = "https://novelpia.com/novel/275975"
        ctx = ConversationContext(
            post_id=11663540,
            post_data={
                "post_id": 11663540,
                "title": "TS) 주서연 전차랑 줄다리기 하면 이길까?",
                "content_blocks": [{"type": "image", "text": ""}],
                "image_enrichment": [
                    {
                        "ocr_text": (
                            f"{title} 작가명 플라나리아햄버거 자유 연재 "
                            "조회 335 추천 14 4회차"
                        ),
                        "explicit_work_title": title,
                        "explicit_author_name": "플라나리아햄버거",
                        "work_cues": [title, "조회 335", "추천 14", "4회차"],
                        "evidence_type": "explicit_text",
                        "title_role": "work_title",
                        "focus_role": "work_anchor",
                        "screen_type": "work_surface",
                        "surface_type": "official_detail_page",
                        "promotion_eligible": True,
                        "confidence": "High",
                    }
                ],
            },
            comments=[],
        )
        ctx.search_results = [
            {
                "title": f"웹소설로 꿈꾸는 세상! - {title} - 노벨피아",
                "url": url,
                "content": f"{title} 웹소설. 플라나리아햄버거 작가.",
                "source_tier": "official_detail",
            }
        ]
        final_decision = {
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
            "discussion_type": "review",
        }

        self.assertFalse(pipeline._has_non_novel_media_evidence_for_title(ctx, title))
        self.assertTrue(
            pipeline._can_promote_title_after_semantic_no_work(
                ctx,
                title,
                source="direct_image_work_surface_lock",
                final_decision={},
                verification_result={},
                title_candidates=[
                    DetectedTitle(
                        official_title=title,
                        heretic_url=url,
                        confidence="High",
                        source_tier="official_detail",
                    )
                ],
            )
        )
        decision = pipeline._record_direct_image_work_surface_gate_decision(
            ctx,
            title,
            candidate_url=url,
            final_decision=final_decision,
            verification_result={},
        )

        self.assertEqual(decision["status"], "publish")
        self.assertTrue(decision["publish_allowed"])
        self.assertFalse(decision["candidate_preserved"])
        self.assertFalse(decision["bypassed_gate"])
        self.assertEqual(
            final_decision["_promotion_gate_state"]["scope"]["scope_kind"],
            "current_work",
        )

    def test_title_led_alias_public_title_records_current_scope_gate(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        title = "탑의 성좌들이 날 애호한다"
        ctx = ConversationContext(
            post_id=11669928,
            post_data={"post_id": 11669928, "title": "탑성좌애호 노벨피아 이거 연중했었네"},
            comments=["재밌게 봤는데 갑자기 연중이라 아까움"],
        )
        ctx.search_results = [
            {
                "title": f"웹소설로 꿈꾸는 세상! - {title} - 노벨피아",
                "url": "https://novelpia.com/novel/377032",
                "content": f"{title} PLUS 독점 연재중단. 탑성좌애호 노벨피아.",
            }
        ]
        final_decision = {
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
            "discussion_type": "review",
        }
        verification_result = {
            "grounding_check": {
                "matched_alias": "탑성좌애호",
                "title_abbrev_mentioned": True,
            }
        }
        acceptance = {
            "decision": "accept",
            "score": 8,
            "title_led_consumption_bridge": True,
        }

        decision = pipeline._record_title_led_alias_public_title_gate_decision(
            ctx,
            title,
            final_decision=final_decision,
            verification_result=verification_result,
            title_candidates=[
                DetectedTitle(
                    official_title=title,
                    heretic_url="https://novelpia.com/novel/377032",
                    confidence="High",
                    alias_or_mention="탑성좌애호",
                    source_tier="official_detail",
                    reference_role="primary",
                )
            ],
            acceptance=acceptance,
        )

        self.assertEqual(decision["status"], "publish")
        self.assertTrue(decision["publish_allowed"])
        self.assertFalse(decision["bypassed_gate"])
        self.assertIn("scope_current_work", decision["reason_codes"])
        self.assertIn("title_led_consumption_bridge", decision["reason_codes"])
        self.assertIn("title_acceptance_accept", decision["reason_codes"])
        self.assertEqual(
            final_decision["_promotion_gate_state"]["scope"]["scope_kind"],
            "current_work",
        )
        self.assertIn(
            "title_led_consumption_bridge",
            final_decision["_promotion_gate_state"]["scope"]["direct_bridge_sources"],
        )
        self.assertIn(
            "alias_surface",
            final_decision["_promotion_gate_state"]["scope"]["direct_bridge_sources"],
        )
        self.assertEqual(getattr(ctx, "_last_promotion_gate_decision"), decision)

    def test_title_led_alias_public_title_blocks_competing_verified_body_work(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        title = "아카데미 생존 갤러리"
        competing_title = "가챠 중독자의 퓨전펑크 생활"
        ctx = ConversationContext(
            post_id=11698880,
            post_data={
                "post_id": 11698880,
                "title": "아생갤 개 존나게 재밌군 ㅇㅇ",
                "content_blocks": [
                    {"type": "text", "text": "가챠펑크 세드릭도 그렇고"},
                    {"type": "text", "text": "시원시원한 상남자라서 좋구나"},
                ],
            },
            comments=[],
        )
        ctx.verified_character_work_links = [
            {
                "title": competing_title,
                "character": "세드릭",
                "abbreviation": "가챠펑크",
                "url": "https://namu.wiki/w/example",
            }
        ]
        ctx.search_results = [
            {
                "title": f"웹소설로 꿈꾸는 세상! - {title} - 노벨피아",
                "url": "https://novelpia.com/novel/380218",
                "content": f"{title} 아생갤 노벨피아.",
            }
        ]
        final_decision = {
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
            "discussion_type": "character_talk",
        }
        verification_result = {
            "grounding_check": {
                "matched_alias": "아생갤",
                "title_abbrev_mentioned": True,
            }
        }
        acceptance = {
            "decision": "accept",
            "score": 8,
            "title_led_consumption_bridge": True,
        }

        decision = pipeline._record_title_led_alias_public_title_gate_decision(
            ctx,
            title,
            candidate_url="https://novelpia.com/novel/380218",
            final_decision=final_decision,
            verification_result=verification_result,
            title_candidates=[
                DetectedTitle(
                    official_title=title,
                    heretic_url="https://novelpia.com/novel/380218",
                    confidence="High",
                    alias_or_mention="아생갤",
                    source_tier="official_detail",
                    reference_role="primary",
                ),
                DetectedTitle(
                    official_title=competing_title,
                    confidence="High",
                    alias_or_mention="가챠펑크",
                    source_tier="mixed",
                    reference_role="mentioned",
                ),
            ],
            acceptance=acceptance,
        )

        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertTrue(decision["candidate_preserved"])
        self.assertIn("scope_context_only", decision["reason_codes"])
        self.assertIn(
            "body_verified_character_work_competes_with_title_led_alias",
            decision["reason_codes"],
        )
        scope = final_decision["_promotion_gate_state"]["scope"]
        self.assertEqual(scope["scope_kind"], "context_only")
        self.assertIn(competing_title, scope["competing_candidates"])
        self.assertIn(
            "body_verified_character_work_competes_with_title_led_alias",
            scope["conflict_reason_codes"],
        )

    def test_resolved_public_title_records_current_scope_gate_without_serialization_inference(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        title = "이 무림의 미친년은 나야"
        ctx = ConversationContext(
            post_id=11674712,
            post_data={"post_id": 11674712, "title": "작가 신작 얘기"},
            comments=["이 무림의 미친년은 나야 이번 화 재밌음"],
        )
        final_decision = {
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
            "title_resolution_allowed": True,
            "is_resolved_work_discussion": True,
            "discussion_type": "character_talk",
            "context_sources": ["title", "body", "comments", "search"],
            "anchor_type": "author",
        }
        resolution_scope_fields = {
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
            "title_resolution_allowed": True,
            "is_resolved_work_discussion": True,
        }

        decision = pipeline._record_resolved_public_title_gate_decision(
            ctx,
            title,
            candidate_url="https://novelpia.com/novel/217943?sid=main5",
            final_decision=final_decision,
            verification_result={},
            title_candidates=[
                DetectedTitle(
                    official_title=title,
                    heretic_url="https://novelpia.com/novel/217943?sid=main5",
                    confidence="High",
                    source_tier="official_detail",
                    page_type="novel_page",
                    reference_role="primary",
                )
            ],
            resolution_scope_fields=resolution_scope_fields,
        )

        self.assertEqual(decision["status"], "publish")
        self.assertTrue(decision["publish_allowed"])
        self.assertFalse(decision["bypassed_gate"])
        self.assertEqual(decision["official_title"], title)
        self.assertIn("scope_current_work", decision["reason_codes"])
        self.assertIn("resolved_public_title_scope", decision["reason_codes"])
        self.assertIn("official_detail_url", decision["reason_codes"])
        self.assertNotIn(
            "final_publication_decision_inferred_from_serialized_identity",
            decision["reason_codes"],
        )
        self.assertEqual(
            final_decision["_promotion_gate_state"]["scope"]["scope_kind"],
            "current_work",
        )
        self.assertIn(
            "resolved_public_title_scope",
            final_decision["_promotion_gate_state"]["scope"]["direct_bridge_sources"],
        )
        self.assertIn(
            "anchor_type:author",
            final_decision["_promotion_gate_state"]["scope"]["direct_bridge_sources"],
        )
        self.assertEqual(getattr(ctx, "_last_promotion_gate_decision"), decision)

    def test_resolved_public_title_gate_blocks_context_only_hold_flags(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        title = "[림월드]변방계에서 회귀자로 살아남기"
        ctx = ConversationContext(
            post_id=11695623,
            post_data={"post_id": 11695623, "title": "랫따싶에서 따먹고싶다는애들이"},
            comments=["그래-맞아"],
        )
        final_decision = {
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
            "title_resolution_allowed": True,
            "is_resolved_work_discussion": True,
            "discussion_type": "general",
            "context_sources": ["title", "body", "comments", "image"],
            "anchor_type": "title_alias",
            "consistency_flags": [
                "recommendation_context_only_no_work_anchor",
                "unresolved_worklike_hold:alias_character_discussion",
            ],
        }

        decision = pipeline._record_resolved_public_title_gate_decision(
            ctx,
            title,
            candidate_url="https://novelpia.com/novel/382324",
            final_decision=final_decision,
            verification_result={},
            title_candidates=[
                DetectedTitle(
                    official_title=title,
                    heretic_url="https://novelpia.com/novel/382324",
                    confidence="High",
                    source_tier="official_detail",
                    page_type="novel_page",
                    reference_role="primary",
                )
            ],
            resolution_scope_fields={
                "work_resolution": "resolved",
                "title_resolution_state": "resolved",
                "title_resolution_allowed": True,
                "is_resolved_work_discussion": True,
            },
        )

        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertTrue(decision["candidate_preserved"])
        self.assertIn("scope_context_only", decision["reason_codes"])
        self.assertIn("scope_not_current_work", decision["reason_codes"])
        self.assertIn("recommendation_context_only_no_work_anchor", decision["reason_codes"])
        self.assertEqual(
            final_decision["_promotion_gate_state"]["scope"]["scope_kind"],
            "context_only",
        )
        self.assertIn(
            "recommendation_context_only_no_work_anchor",
            final_decision["_promotion_gate_state"]["scope"]["conflict_reason_codes"],
        )
        self.assertEqual(getattr(ctx, "_last_promotion_gate_decision"), decision)

    def test_resolved_public_title_gate_allows_title_led_consumption_hold_flag(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        title = "암흑가 보스요? 제가요?"
        ctx = ConversationContext(
            post_id=11660257,
            post_data={"post_id": 11660257, "title": "암흑가보스<<이거 재밋네"},
            comments=[],
        )
        ctx.set_expert_output(
            ExpertType.GATEKEEPER,
            {
                "post_type": "short_reaction",
                "detected_entities": {"possible_titles": ["암흑가보스"]},
            },
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "express_opinion",
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
            }
        ]
        final_decision = {
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
            "title_resolution_allowed": True,
            "is_resolved_work_discussion": True,
            "discussion_type": "general",
            "context_sources": ["title", "search", "image"],
            "anchor_type": "none",
            "consistency_flags": ["unresolved_worklike_hold:title_led_consumption"],
        }

        decision = pipeline._record_resolved_public_title_gate_decision(
            ctx,
            title,
            candidate_url="https://novelpia.com/novel/384111",
            final_decision=final_decision,
            verification_result={},
            title_candidates=[
                DetectedTitle(
                    official_title=title,
                    heretic_url="https://novelpia.com/novel/384111",
                    confidence="High",
                    alias_or_mention="암흑가보스",
                    source_tier="official_detail",
                    page_type="novel_page",
                    reference_role="primary",
                )
            ],
            resolution_scope_fields=final_decision,
        )

        self.assertEqual(decision["status"], "publish")
        self.assertTrue(decision["publish_allowed"])
        self.assertIn("scope_current_work", decision["reason_codes"])
        self.assertNotIn("unresolved_worklike_hold:title_led_consumption", decision["reason_codes"])
        self.assertEqual(final_decision["_promotion_gate_state"]["scope"]["scope_kind"], "current_work")

    def test_resolved_public_title_gate_blocks_previous_work_when_direct_body_candidate_competes(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        previous_title = "잘생기면 인생이 편하다"
        current_title = "잘생기면 편해지는 인방 생활"
        ctx = ConversationContext(
            post_id=11713222,
            post_data={
                "post_id": 11713222,
                "title": "현대 하렘물은 진짜 잘쓰는 작가가 손에꼽네",
                "content_blocks": [
                    {
                        "type": "text",
                        "text": "잘생인방보는데 그냥 주인공이 여자를 오나홀로밖에 안보는거같음",
                    }
                ],
            },
            comments=["전작도 잘생인편으로 현대하렘아님?", "그렇네 잘생인편 안봐서 까먹어버림"],
        )
        final_decision = {
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
            "title_resolution_allowed": True,
            "is_resolved_work_discussion": True,
            "discussion_type": "general",
            "context_sources": ["title", "body", "comments", "search"],
            "anchor_type": "title_alias",
            "consistency_flags": [
                "acknowledged_previous_work_comment:잘생인편",
                "acknowledged_previous_work_comment_override",
                "acknowledged_previous_work_comment_anchor",
                "confirmed_alias:잘생인편",
            ],
        }

        decision = pipeline._record_resolved_public_title_gate_decision(
            ctx,
            previous_title,
            candidate_url="https://novelpia.com/novel/300042",
            final_decision=final_decision,
            verification_result={},
            title_candidates=[
                DetectedTitle(
                    official_title=previous_title,
                    heretic_url="https://novelpia.com/novel/300042",
                    confidence="High",
                    alias_or_mention="잘생인편",
                    source_tier="official_detail",
                    page_type="novel_page",
                    reference_role="primary",
                ),
                DetectedTitle(
                    official_title=current_title,
                    heretic_url="https://novelpia.com/novel/384016",
                    confidence="High",
                    alias_or_mention="잘생인방",
                    source_tier="official_detail",
                    page_type="novel_page",
                    reference_role="primary",
                ),
            ],
            resolution_scope_fields=final_decision,
        )

        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertTrue(decision["candidate_preserved"])
        self.assertIn("scope_previous_work", decision["reason_codes"])
        self.assertIn("scope_not_current_work", decision["reason_codes"])
        self.assertIn("current_work_candidate_competes_with_previous_work", decision["reason_codes"])
        scope = final_decision["_promotion_gate_state"]["scope"]
        self.assertEqual(scope["scope_kind"], "previous_work")
        self.assertIn(current_title, scope["competing_candidates"])
        self.assertIn("direct_body_competing_official_detail", scope["direct_bridge_sources"])
        self.assertEqual(getattr(ctx, "_last_promotion_gate_decision"), decision)

    def test_resolved_public_title_gate_does_not_record_unresolved_scope(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        ctx = ConversationContext(
            post_id=11694035,
            post_data={"post_id": 11694035, "title": "잡담"},
            comments=[],
        )
        final_decision = {
            "work_resolution": "unresolved",
            "title_resolution_state": "unresolved_matchable",
            "title_resolution_allowed": False,
            "is_resolved_work_discussion": False,
            "discussion_type": "community_banter",
        }

        decision = pipeline._record_resolved_public_title_gate_decision(
            ctx,
            "없음",
            candidate_url="",
            final_decision=final_decision,
            verification_result={},
            title_candidates=[],
            resolution_scope_fields=final_decision,
        )

        self.assertEqual(decision, {})
        self.assertFalse(hasattr(ctx, "_last_promotion_gate_decision"))
        self.assertNotIn("_promotion_gate_decision", final_decision)

    def test_candidate_audit_preserves_ledger_promotion_gate_state(self):
        decision = {
            "status": "publish",
            "publish_allowed": True,
            "official_title": "이 무림의 미친년은 나야",
            "official_url": "https://novelpia.com/novel/217943",
            "candidate_preserved": False,
            "reason_codes": [
                "official_title_exists",
                "row_discusses_work_as_work",
                "scope_current_work",
                "resolved_public_title_scope",
            ],
            "bypassed_gate": False,
        }
        gate_state = {
            "post_id": 11674712,
            "candidate_title": "이 무림의 미친년은 나야",
            "candidate_url": "https://novelpia.com/novel/217943",
            "source": "resolved_public_title",
            "official_title_exists": True,
            "row_discusses_work_as_work": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "scope": {
                "scope_kind": "current_work",
                "confidence": "high",
                "direct_bridge_sources": [
                    "resolved_public_title_scope",
                    "official_detail_url",
                ],
                "competing_candidates": [],
                "conflict_reason_codes": [],
            },
        }
        gate_evidence = [
            {
                "kind": "resolved_public_title_scope",
                "strength": "strong",
                "source_path_or_snippet": "이 무림의 미친년은 나야",
                "supports_publish": True,
                "reason_code": "resolved_public_title_scope",
            }
        ]
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "title_resolution_state": "resolved",
            "title_resolution_allowed": True,
            "work_resolution": "resolved",
            "discussion_type": "character_talk",
            "novel_identity": {
                "official_title": "이 무림의 미친년은 나야",
                "heretic_url": "https://novelpia.com/novel/217943",
                "confidence": "High",
            },
            "candidate_ledger": {
                "promotion_decision": decision,
                "promotion_gate_state": gate_state,
                "promotion_gate_evidence": gate_evidence,
            },
        }

        fields = build_candidate_audit_fields(identity, None)

        ledger = fields["candidate_ledger"]
        self.assertEqual(ledger["promotion_decision"], decision)
        self.assertEqual(ledger["promotion_gate_state"], gate_state)
        self.assertEqual(ledger["promotion_gate_evidence"], gate_evidence)
        self.assertEqual(ledger["promotion_gate_state"]["scope"]["scope_kind"], "current_work")

    def test_candidate_audit_preserves_complete_v2_contract_mirror(self):
        title = "계약 미러 작품"
        url = "https://novelpia.com/novel/123456"
        contract = evaluate_publish_contract(
            GroundingState(
                post_id=123,
                candidate_title=title,
                candidate_url=url,
                official_title_exists=True,
                row_discusses_work_as_work=True,
                title_resolution_state="resolved",
                work_resolution="resolved",
                scope=ScopeState(scope_kind="current_work", confidence="high"),
            ),
            [
                EvidenceRecord(
                    kind="alias_bridge",
                    supports_publish=True,
                    candidate_title=title,
                ),
                EvidenceRecord(
                    kind="official_detail_url",
                    candidate_title=title,
                    candidate_url=url,
                    title_url_match=True,
                ),
            ],
        )
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": True,
            "discussion_type": "review",
            "novel_identity": {"confidence": "High"},
        }
        apply_publish_contract(identity, contract)

        fields = build_candidate_audit_fields(identity, None)
        ledger = fields["candidate_ledger"]

        for field in (
            "promotion_decision",
            "promotion_gate_state",
            "promotion_gate_evidence",
            "publish_contract_trace",
            "publish_ledger",
            "publish_contract_input_fingerprint",
            "publish_contract_version",
            "candidate_ledger_status",
            "title_resolution_allowed",
            "title_resolution_state",
            "work_resolution",
            "promotion_blocked",
            "hold_without_candidates",
            "safe_resolved",
        ):
            with self.subTest(field=field):
                self.assertEqual(ledger[field], identity[field])

    def test_candidate_audit_is_observational_for_v2_inventory(self):
        sources = [
            {
                "official_title": "후보 A",
                "heretic_url": "https://novelpia.com/novel/1001",
                "source_tier": "official_detail",
            },
            {
                "official_title": "존나 언제와 아쉬웠음 소개문",
                "source_tier": "llm_only",
            },
        ]
        evidence = candidate_inventory_evidence_from_sources(sources)
        contract = evaluate_publish_contract(
            GroundingState(
                post_id=11700470,
                candidate_title="",
                candidate_inventory_count=len(evidence),
            ),
            evidence,
        )
        identity = {
            "title_candidates": [dict(item) for item in sources],
            "candidate_preservation_sources": [dict(item) for item in sources],
            "candidate_ledger": {
                "candidate_preservation_sources": [dict(item) for item in sources],
            },
        }
        apply_publish_contract(identity, contract)
        identity["secondary_reference_works"] = [
            {"official_title": "관측 전용 보조 후보", "reference_role": "secondary"}
        ]
        expected_title_candidates = [dict(item) for item in identity["title_candidates"]]
        expected_preservation = [
            dict(item) for item in identity["candidate_preservation_sources"]
        ]
        expected_ledger_inventory = {
            field: identity["candidate_ledger"].get(field)
            for field in (
                "title_candidates",
                "candidate_count",
                "candidate_preservation_sources",
            )
        }
        expected_fingerprint = identity["publish_contract_input_fingerprint"]
        expected_decision = dict(identity["promotion_decision"])

        apply_candidate_audit_fields(identity, None)

        self.assertEqual(identity["title_candidates"], expected_title_candidates)
        self.assertEqual(identity["candidate_preservation_sources"], expected_preservation)
        self.assertEqual(identity["publish_contract_input_fingerprint"], expected_fingerprint)
        self.assertEqual(identity["promotion_decision"], expected_decision)
        for field, expected in expected_ledger_inventory.items():
            with self.subTest(ledger_inventory_field=field):
                self.assertEqual(identity["candidate_ledger"].get(field), expected)
        self.assertNotIn(
            "관측 전용 보조 후보",
            identity["candidate_ledger"].get("title_candidates") or [],
        )

    def test_candidate_audit_marker_only_v2_does_not_rebuild_inventory(self):
        sources = [
            {
                "official_title": "후보 A",
                "heretic_url": "https://novelpia.com/novel/1001",
            }
        ]
        evidence = candidate_inventory_evidence_from_sources(sources)
        contract = evaluate_publish_contract(
            GroundingState(
                post_id=20010064,
                candidate_title="",
                candidate_inventory_count=1,
            ),
            evidence,
        )
        identity = {
            "title_candidates": list(sources),
            "candidate_preservation_sources": list(sources),
            "secondary_reference_works": [
                {"official_title": "관측 전용 보조 후보"}
            ],
            "candidate_ledger": {
                "candidate_preservation_sources": list(sources),
            },
        }
        apply_publish_contract(identity, contract)
        identity.pop("publish_contract_version", None)
        identity["candidate_ledger"].pop("publish_contract_version", None)
        identity["promotion_decision"].pop("contract_version", None)
        identity["candidate_ledger"]["promotion_decision"].pop(
            "contract_version",
            None,
        )
        self.assertTrue(has_authoritative_publish_contract(identity))
        expected_inventory = {
            field: identity["candidate_ledger"].get(field)
            for field in (
                "title_candidates",
                "candidate_count",
                "candidate_preservation_sources",
            )
        }

        apply_candidate_audit_fields(identity, None)

        for field, expected in expected_inventory.items():
            self.assertEqual(identity["candidate_ledger"].get(field), expected)
        self.assertNotIn(
            "관측 전용 보조 후보",
            identity["candidate_ledger"].get("title_candidates") or [],
        )

    def test_candidate_audit_ledger_only_marker_does_not_run_legacy_pruning(self):
        sources = [
            {
                "official_title": "존나 언제와 아쉬웠음 소개문",
                "source_tier": "llm_only",
            }
        ]
        evidence = candidate_inventory_evidence_from_sources(sources)
        contract = evaluate_publish_contract(
            GroundingState(
                post_id=20010068,
                candidate_title="",
                candidate_inventory_count=1,
            ),
            evidence,
        )
        identity = {
            "title_candidates": list(sources),
            "candidate_preservation_sources": list(sources),
            "candidate_ledger": {
                "candidate_preservation_sources": list(sources),
            },
        }
        apply_publish_contract(identity, contract)
        identity.pop("publish_contract_version", None)
        identity["candidate_ledger"].pop("publish_contract_version", None)
        identity["promotion_decision"].pop("contract_version", None)
        identity["candidate_ledger"]["promotion_decision"].pop(
            "contract_version",
            None,
        )
        identity.pop("promotion_gate_state", None)
        identity.pop("promotion_gate_evidence", None)
        identity.pop("publish_contract_trace", None)
        self.assertTrue(has_authoritative_publish_contract(identity))
        expected_titles = [dict(item) for item in identity["title_candidates"]]
        expected_ledger_sources = [
            dict(item)
            for item in identity["candidate_ledger"]["candidate_preservation_sources"]
        ]

        apply_candidate_audit_fields(identity, None)

        self.assertEqual(identity["title_candidates"], expected_titles)
        self.assertEqual(
            identity["candidate_ledger"]["candidate_preservation_sources"],
            expected_ledger_sources,
        )
        self.assertNotIn("candidate_pruned_llm_only_surfaces", identity)

    def test_blocked_resolved_candidate_normalizes_public_hold_state(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        ctx = ConversationContext(
            post_id=20010061,
            post_data={"post_id": 20010061, "title": "관계가 불확실한 후보 이야기"},
            comments=[],
        )
        final_decision = {}
        state = GroundingState(
            post_id=20010061,
            candidate_title="파생 후보 작품",
            candidate_url="https://novelpia.com/novel/900061",
            source="search_evidence_alias_inference",
            official_title_exists=True,
            row_discusses_work_as_work=False,
            title_resolution_state="resolved",
            work_resolution="resolved",
            discussion_type="character_talk",
            scope=ScopeState(
                scope_kind="unknown",
                confidence="low",
                conflict_reason_codes=["shared_work_bridge_missing"],
            ),
        )

        decision = pipeline._record_public_title_gate_decision(
            ctx,
            state,
            [
                EvidenceRecord(
                    kind="official_detail_url",
                    strength="strong",
                    source_path_or_snippet=state.candidate_url,
                    supports_publish=False,
                    reason_code="official_detail_url",
                    candidate_title=state.candidate_title,
                    candidate_url=state.candidate_url,
                    title_url_match=True,
                )
            ],
            final_decision=final_decision,
        )

        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertTrue(decision["candidate_preserved"])
        self.assertFalse(decision["bypassed_gate"])
        self.assertEqual(
            final_decision["_promotion_gate_state"]["title_resolution_state"],
            "unresolved_matchable",
        )
        self.assertEqual(
            final_decision["_promotion_gate_state"]["work_resolution"],
            "unresolved",
        )
        self.assertIn(
            "blocked_candidate_resolution_state_normalized",
            decision["reason_codes"],
        )

    def test_inventory_only_contract_preserves_candidates_without_selecting_public_title(self):
        sources = [
            {
                "official_title": "후보 A",
                "heretic_url": "https://novelpia.com/novel/1001",
                "preservation_role": "title_candidate",
            },
            {
                "official_title": "후보 B",
                "preservation_role": "title_candidate",
            },
        ]
        inventory_evidence = candidate_inventory_evidence_from_sources(sources)
        state = GroundingState(
            post_id=11700470,
            candidate_title="",
            source="serializer_missing_typed_contract",
            official_title_exists=False,
            row_discusses_work_as_work=False,
            title_resolution_state="unresolved_matchable",
            work_resolution="unresolved",
            discussion_type="character_talk",
            candidate_inventory_count=len(inventory_evidence),
            scope=None,
        )

        contract = evaluate_publish_contract(state, inventory_evidence)

        self.assertEqual(contract.decision.status, "candidate_only")
        self.assertFalse(contract.decision.publish_allowed)
        self.assertIsNone(contract.decision.official_title)
        self.assertIsNone(contract.decision.official_url)
        self.assertTrue(contract.decision.candidate_preserved)
        self.assertFalse(contract.decision.bypassed_gate)
        self.assertIn(
            "candidate_inventory_preserved_without_selection",
            contract.decision.reason_codes,
        )
        self.assertEqual(
            contract.trace.post_gate_identity.candidate_ledger_status,
            "promotion_blocked",
        )

        identity = {
            "novel_identity": {"official_title": None, "heretic_url": None},
            "title_candidates": list(sources),
            "candidate_ledger": {
                "candidate_preservation_sources": list(sources),
            },
        }
        apply_publish_contract(identity, contract)

        self.assertEqual(identity["title_candidates"], sources)
        self.assertEqual(
            identity["candidate_ledger"]["candidate_preservation_sources"],
            sources,
        )
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertTrue(identity["promotion_blocked"])
        self.assertFalse(identity["hold_without_candidates"])
        self.assertFalse(identity["safe_resolved"])

    def test_serializer_existing_contract_empty_boundary_freezes_two_candidate_inventory(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        prior = evaluate_publish_contract(
            GroundingState(
                post_id=11700470,
                candidate_title="이전 단일 후보",
                official_title_exists=False,
                row_discusses_work_as_work=False,
            ),
            [],
        )
        sources = [
            {"official_title": "후보 A", "heretic_url": "https://novelpia.com/novel/1001"},
            {"official_title": "후보 B"},
        ]
        evidence = candidate_inventory_evidence_from_sources(sources)

        contract = pipeline._build_serializer_inventory_only_publish_contract(
            prior_contract=prior,
            inventory_evidence=evidence,
            extended_identity={
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "discussion_type": "character_talk",
            },
        )

        self.assertEqual(contract.state.candidate_title, "")
        self.assertEqual(contract.state.candidate_inventory_count, 2)
        self.assertEqual(contract.decision.status, "candidate_only")
        self.assertTrue(contract.decision.candidate_preserved)
        self.assertFalse(contract.decision.publish_allowed)
        self.assertFalse(contract.decision.bypassed_gate)
        self.assertIsNone(contract.decision.official_title)
        self.assertIsNone(contract.decision.official_url)

    def test_serializer_inventory_only_normalizes_blocked_resolved_context(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        prior = evaluate_publish_contract(
            GroundingState(
                post_id=20010065,
                candidate_title="이전 후보",
                official_title_exists=False,
                row_discusses_work_as_work=False,
            ),
            [],
        )
        evidence = candidate_inventory_evidence_from_sources(
            [{"official_title": "보존 후보"}]
        )

        contract = pipeline._build_serializer_inventory_only_publish_contract(
            prior_contract=prior,
            inventory_evidence=evidence,
            extended_identity={
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "discussion_type": "character_talk",
            },
        )

        self.assertEqual(contract.decision.status, "candidate_only")
        self.assertFalse(contract.decision.publish_allowed)
        self.assertTrue(contract.decision.candidate_preserved)
        self.assertFalse(contract.decision.bypassed_gate)
        self.assertEqual(contract.state.title_resolution_state, "unresolved_matchable")
        self.assertEqual(contract.state.work_resolution, "unresolved")
        self.assertEqual(
            contract.trace.post_gate_identity.title_resolution_state,
            "unresolved_matchable",
        )
        self.assertIn(
            "blocked_candidate_resolution_state_normalized",
            contract.decision.reason_codes,
        )

    def test_serializer_inventory_only_can_select_one_verified_pair_for_safe_hold(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        title = "보존할 정확한 후보"
        url = "https://novelpia.com/novel/20020003"
        prior = evaluate_publish_contract(
            GroundingState(
                post_id=20020003,
                candidate_title="",
                official_title_exists=False,
                row_discusses_work_as_work=False,
            ),
            [],
        )
        evidence = candidate_inventory_evidence_from_sources(
            [{"official_title": title, "heretic_url": url}]
        )

        contract = pipeline._build_serializer_inventory_only_publish_contract(
            prior_contract=prior,
            inventory_evidence=evidence,
            extended_identity={
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "discussion_type": "author_talk",
            },
            selected_candidate_title=title,
            selected_candidate_url=url,
            selected_scope_kind="context_only",
        )

        self.assertEqual(contract.decision.status, "candidate_only")
        self.assertFalse(contract.decision.publish_allowed)
        self.assertTrue(contract.decision.candidate_preserved)
        self.assertFalse(contract.decision.bypassed_gate)
        self.assertEqual(contract.state.candidate_title, title)
        self.assertEqual(contract.state.candidate_url, url)
        self.assertEqual(contract.state.scope.scope_kind, "context_only")
        self.assertEqual(contract.state.scope.direct_bridge_sources, ())
        self.assertIn("official_title_exists", contract.decision.reason_codes)
        self.assertIn("scope_context_only", contract.decision.reason_codes)
        self.assertIn("official_detail_url", contract.decision.reason_codes)

    def test_serializer_hold_selector_chooses_unique_packet_bound_official_pair(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        title = "이미지에 확인된 작품"
        url = "https://ridibooks.com/books/20020004"
        ctx = ConversationContext(
            post_id=20020004,
            post_data={"title": "이 작가 이런 것도 썼어?"},
            comments=[],
        )
        evidence = candidate_inventory_evidence_from_sources(
            [
                {"official_title": title, "heretic_url": url},
                {"official_title": "선택하면 안 되는 제목 전용 후보"},
            ]
        )
        ctx.fetched_page_info = [self._fetched_novel_detail(url, title)]

        with patch.object(
            pipeline, "_source_native_official_detail_identity", return_value={}
        ), patch.object(
            pipeline, "_is_title_matched_non_novel_media_url", return_value=False
        ), patch.object(
            pipeline, "_title_mentioned_in_non_image_main_context", return_value=False
        ), patch.object(
            pipeline, "_title_matches_direct_image_partial", return_value=True
        ), patch.object(
            pipeline, "_has_structured_direct_image_work_surface_evidence", return_value=True
        ):
            selected = pipeline._select_authoritative_serializer_hold_candidate(
                ctx=ctx,
                inventory_evidence=evidence,
            )

        self.assertEqual(selected, {"title": title, "url": url})

    def test_serializer_mismatch_contract_binds_inventory_and_normalizes_hold(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        prior = evaluate_publish_contract(
            GroundingState(
                post_id=20010069,
                candidate_title="이전 typed 후보",
                candidate_url="https://novelpia.com/novel/900069",
                official_title_exists=True,
                row_discusses_work_as_work=True,
                title_resolution_state="resolved",
                work_resolution="resolved",
                scope=ScopeState(
                    scope_kind="current_work",
                    confidence="high",
                    direct_bridge_sources=["contract_test"],
                ),
            ),
            [
                EvidenceRecord(
                    kind="contract_test",
                    strength="strong",
                    supports_publish=True,
                    reason_code="contract_test",
                    candidate_title="이전 typed 후보",
                    candidate_url="https://novelpia.com/novel/900069",
                    title_url_match=True,
                )
            ],
        )
        inventory = candidate_inventory_evidence_from_sources(
            [
                {
                    "official_title": "이전 typed 후보",
                    "heretic_url": "https://novelpia.com/novel/900069",
                },
                {
                    "official_title": "후단 boundary 후보",
                    "heretic_url": "https://novelpia.com/novel/900070",
                },
                {
                    "official_title": "검색 보존 후보",
                    "heretic_url": "https://novelpia.com/novel/900071",
                },
            ]
        )

        contract = pipeline._build_serializer_mismatch_publish_contract(
            prior_contract=prior,
            boundary_candidate_title="후단 boundary 후보",
            boundary_candidate_url="https://novelpia.com/novel/900070",
            inventory_evidence=inventory,
            extended_identity={
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "discussion_type": "meme",
            },
        )

        self.assertEqual(contract.state.candidate_inventory_count, 3)
        self.assertEqual(contract.state.candidate_title, "")
        self.assertEqual(contract.state.candidate_url, "")
        self.assertEqual(contract.state.title_resolution_state, "unresolved_matchable")
        self.assertEqual(contract.state.work_resolution, "unresolved")
        self.assertEqual(contract.decision.status, "candidate_only")
        self.assertFalse(contract.decision.publish_allowed)
        self.assertTrue(contract.decision.candidate_preserved)
        self.assertFalse(contract.decision.bypassed_gate)
        self.assertIn("post_gate_candidate_mismatch", contract.decision.reason_codes)
        self.assertIn(
            "blocked_candidate_resolution_state_normalized",
            contract.decision.reason_codes,
        )
        self.assertEqual(
            len([record for record in contract.evidence if record.kind == "candidate_preservation"]),
            3,
        )

    def test_shared_blocked_resolution_normalizer_handles_either_resolved_axis(self):
        self.assertEqual(
            normalize_blocked_resolution_state("resolved", "context_only"),
            ("unresolved_matchable", "context_only", True),
        )
        self.assertEqual(
            normalize_blocked_resolution_state("context_only", "resolved"),
            ("context_only", "unresolved", True),
        )
        self.assertEqual(
            normalize_blocked_resolution_state("unresolved_matchable", "unresolved"),
            ("unresolved_matchable", "unresolved", False),
        )

    def test_evaluate_contract_normalizes_scope_blocked_resolved_even_when_row_discusses(self):
        contract = evaluate_publish_contract(
            GroundingState(
                post_id=20010070,
                candidate_title="scope 차단 후보",
                row_discusses_work_as_work=True,
                title_resolution_state="resolved",
                work_resolution="resolved",
                scope=ScopeState(
                    scope_kind="context_only",
                    confidence="low",
                    conflict_reason_codes=["context_only"],
                ),
            ),
            [],
        )

        self.assertFalse(contract.decision.publish_allowed)
        self.assertEqual(contract.state.title_resolution_state, "unresolved_matchable")
        self.assertEqual(contract.state.work_resolution, "unresolved")
        self.assertEqual(
            contract.trace.post_gate_identity.title_resolution_state,
            "unresolved_matchable",
        )
        self.assertIn(
            "blocked_candidate_resolution_state_normalized",
            contract.decision.reason_codes,
        )

    def test_source_native_two_body_detail_urls_fail_closed(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        first_url = "https://novelpia.com/novel/910001"
        second_url = "https://novelpia.com/novel/910002"
        ctx = ConversationContext(
            post_id=910001,
            post_data={
                "title": "두 작품 링크 묶음",
                "content_blocks": [
                    {"type": "link", "url": first_url},
                    {"type": "link", "url": second_url},
                ],
            },
            comments=[],
        )
        ctx.fetched_page_info = [
            self._fetched_novel_detail(first_url, "첫 번째 작품"),
            self._fetched_novel_detail(second_url, "두 번째 작품"),
        ]

        identity = pipeline._source_native_official_detail_identity(ctx)

        self.assertEqual(identity, {})
        self.assertTrue(ctx._source_native_official_detail_identity_checked)
        self.assertEqual(ctx._source_native_official_detail_identity, {})

    def test_source_native_detail_plus_platform_nondetail_url_fails_closed(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        detail_url = "https://novelpia.com/novel/910017"
        viewer_url = "https://novelpia.com/viewer/910017/1"
        ctx = ConversationContext(
            post_id=910017,
            post_data={
                "title": "플랫폼 링크 묶음",
                "content_blocks": [
                    {"type": "link", "url": detail_url},
                    {"type": "link", "url": viewer_url},
                ],
            },
            comments=[],
        )
        ctx.fetched_page_info = [
            self._fetched_novel_detail(detail_url, "선택하면 안 되는 단일 작품")
        ]

        identity = pipeline._source_native_official_detail_identity(ctx)

        self.assertEqual(identity, {})
        self.assertTrue(ctx._source_native_official_detail_identity_checked)
        self.assertEqual(ctx._source_native_official_detail_identity, {})

    def test_source_native_conflicting_fetched_canonical_titles_fail_closed(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        url = "https://novel.munpia.com/910003"
        ctx = ConversationContext(
            post_id=910003,
            post_data={
                "title": "공식 링크 확인",
                "content_blocks": [{"type": "link", "url": url}],
            },
            comments=[],
        )
        ctx.fetched_page_info = [
            {
                "url": url,
                "structured_info": {
                    "title": "서로 다른 정식 제목 A",
                    "page_title": "서로 다른 정식 제목 B",
                    "page_type": "novel_page",
                    "content_status": "active",
                },
            }
        ]

        self.assertEqual(pipeline._canonical_fetched_title_for_url(ctx, url), None)
        self.assertEqual(pipeline._source_native_official_detail_identity(ctx), {})

    def test_source_native_preserves_authoritative_bracketed_title_component(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        url = "https://novelpia.com/novel/910022"
        title = "[림월드]변방계에서 회귀자로 살아남기"
        ctx = ConversationContext(
            post_id=910022,
            post_data={
                "title": "신작 홍보",
                "content_blocks": [
                    {"type": "link", "url": url},
                    {"type": "text", "text": "이번 작품을 연재합니다"},
                ],
            },
            comments=[],
        )
        ctx.fetched_page_info = [self._fetched_novel_detail(url, title)]

        self.assertEqual(pipeline._canonical_fetched_title_for_url(ctx, url), title)
        self.assertEqual(
            pipeline._source_native_official_detail_identity(ctx),
            {"title": title, "url": url},
        )

    def test_source_native_strips_explicit_ui_badge_from_fetched_display_title(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)

        self.assertEqual(
            pipeline._normalize_authoritative_fetched_title_display("[독점] 실제 작품명"),
            "실제 작품명",
        )

    def test_source_native_fetched_url_prefix_collision_fails_closed(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        requested_url = "https://novelpia.com/novel/91003"
        longer_id_url = "https://novelpia.com/novel/910030"
        ctx = ConversationContext(
            post_id=910018,
            post_data={
                "title": "신작 홍보",
                "content_blocks": [
                    {"type": "link", "url": requested_url},
                    {"type": "text", "text": "많은 관심 부탁드립니다"},
                ],
            },
            comments=[],
        )
        ctx.fetched_page_info = [
            self._fetched_novel_detail(longer_id_url, "더 긴 ID의 다른 작품")
        ]

        identity = pipeline._source_native_official_detail_identity(ctx)

        self.assertEqual(identity, {})
        self.assertTrue(ctx._source_native_official_detail_identity_checked)
        self.assertEqual(ctx._source_native_official_detail_identity, {})

    def test_source_native_exact_page_state_ignores_deleted_prefix_neighbor(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        requested_url = "https://novelpia.com/novel/91003"
        longer_id_url = "https://novelpia.com/novel/910030"
        title = "정확 URL의 작품"
        ctx = ConversationContext(
            post_id=910021,
            post_data={
                "title": title,
                "content_blocks": [
                    {"type": "link", "url": requested_url},
                    {"type": "text", "text": f"{title} 주인공 전개를 소개합니다"},
                ],
            },
            comments=[],
        )
        ctx.fetched_page_info = [
            self._fetched_novel_detail(requested_url, title),
            self._fetched_novel_detail(
                longer_id_url,
                "삭제된 이웃 ID 작품",
                content_status="deleted",
            ),
        ]

        identity = pipeline._source_native_official_detail_identity(ctx)

        self.assertEqual(identity, {"title": title, "url": requested_url})

    def test_source_native_comment_and_search_only_urls_are_excluded(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        url = "https://novelpia.com/novel/910004"
        title = "검색에만 나온 작품"
        ctx = ConversationContext(
            post_id=910004,
            post_data={
                "title": "댓글 링크가 뭔지 물어봄",
                "content_blocks": [{"type": "text", "text": "본문에는 링크가 없다"}],
            },
            comments=[f"이 작품인가? {url}"],
        )
        ctx.search_results = [{"title": title, "url": url, "content": title}]
        ctx.fetched_page_info = [self._fetched_novel_detail(url, title)]

        self.assertEqual(pipeline._source_native_official_detail_identity(ctx), {})

    def test_source_native_positive_identity_is_memoized_against_search_and_fetch_mutation(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        url = "https://novelpia.com/novel/910005"
        title = "고정된 정식 제목"
        ctx = ConversationContext(
            post_id=910005,
            post_data={
                "title": "공식 작품 링크",
                "content_blocks": [{"type": "link", "url": url}],
            },
            comments=[],
        )
        ctx.fetched_page_info = [self._fetched_novel_detail(url, title)]

        first = pipeline._source_native_official_detail_identity(ctx)
        ctx.search_results = [
            {"title": "뒤늦게 들어온 검색 오염 제목", "url": url, "content": "오염"}
        ]
        ctx.fetched_page_info[0]["structured_info"]["title"] = "변경된 페치 제목"
        ctx.fetched_page_info[0]["structured_info"]["page_title"] = "변경된 페치 제목"
        second = pipeline._source_native_official_detail_identity(ctx)

        self.assertEqual(first, {"title": title, "url": url})
        self.assertEqual(second, first)

    def test_source_native_negative_identity_is_memoized_after_late_input_mutation(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        url = "https://novelpia.com/novel/910006"
        ctx = ConversationContext(
            post_id=910006,
            post_data={
                "title": "링크 없음",
                "content_blocks": [{"type": "text", "text": "본문 근거 없음"}],
            },
            comments=[],
        )

        first = pipeline._source_native_official_detail_identity(ctx)
        ctx.post_data["content_blocks"].append({"type": "link", "url": url})
        ctx.search_results = [{"title": "늦게 추가된 작품", "url": url}]
        ctx.fetched_page_info = [self._fetched_novel_detail(url, "늦게 추가된 작품")]
        second = pipeline._source_native_official_detail_identity(ctx)

        self.assertEqual(first, {})
        self.assertEqual(second, {})
        self.assertTrue(ctx._source_native_official_detail_identity_checked)

    def test_source_native_exact_identity_without_relation_is_context_only_hold(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        title = "유리 성채"
        url = "https://novelpia.com/novel/910007"
        ctx = ConversationContext(
            post_id=910007,
            post_data={
                "title": title,
                "content_blocks": [{"type": "link", "url": url}],
            },
            comments=[],
        )

        decision = pipeline._record_source_native_official_detail_gate_decision(
            ctx,
            title,
            candidate_url=url,
            final_decision={},
            verification_result={},
        )

        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertTrue(decision["candidate_preserved"])
        self.assertFalse(decision["bypassed_gate"])
        self.assertEqual(
            ctx._last_promotion_gate_state["scope"]["scope_kind"],
            "context_only",
        )
        self.assertIn(
            "source_native_identity_without_non_image_relation_bridge",
            decision["reason_codes"],
        )

    def test_source_native_plot_or_promotion_relation_can_publish(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        title = "유리 성채"
        url = "https://novelpia.com/novel/910008"
        relation_texts = (
            f"{title} 주인공 설정과 캐릭터 전개를 소개합니다",
            "신작 홍보입니다 많은 관심 부탁드립니다",
        )

        for index, relation_text in enumerate(relation_texts):
            with self.subTest(relation_text=relation_text):
                ctx = ConversationContext(
                    post_id=910008 + index,
                    post_data={
                        "title": "새 글 안내",
                        "content_blocks": [
                            {"type": "link", "url": url},
                            {"type": "text", "text": relation_text},
                        ],
                    },
                    comments=[],
                )

                decision = pipeline._record_source_native_official_detail_gate_decision(
                    ctx,
                    title,
                    candidate_url=url,
                    final_decision={},
                    verification_result={},
                )

                self.assertEqual(decision["status"], "publish")
                self.assertTrue(decision["publish_allowed"])
                self.assertFalse(decision["candidate_preserved"])
                self.assertFalse(decision["bypassed_gate"])
                self.assertEqual(
                    ctx._last_promotion_gate_state["scope"]["scope_kind"],
                    "current_work",
                )
                self.assertIn(
                    "source_native_non_image_work_relation_bridge",
                    decision["reason_codes"],
                )

    def test_source_native_generic_relation_for_different_named_work_stays_hold(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        title = "URL이 가리킨 작품"
        url = "https://novelpia.com/novel/910015"
        ctx = ConversationContext(
            post_id=910015,
            post_data={
                "title": "다른 작품 설명",
                "content_blocks": [
                    {"type": "link", "url": url},
                    {
                        "type": "text",
                        "text": "별개의 작품 B: 주인공 설정과 캐릭터 전개를 소개합니다",
                    },
                ],
            },
            comments=[],
        )

        decision = pipeline._record_source_native_official_detail_gate_decision(
            ctx,
            title,
            candidate_url=url,
            final_decision={},
            verification_result={},
        )

        self.assertFalse(decision["publish_allowed"])
        self.assertTrue(decision["candidate_preserved"])
        self.assertFalse(decision["bypassed_gate"])
        self.assertEqual(
            ctx._last_promotion_gate_state["scope"]["scope_kind"],
            "context_only",
        )

    def test_source_native_promotion_for_explicit_different_work_stays_hold(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        title = "URL이 가리킨 작품"
        url = "https://novelpia.com/novel/910016"
        ctx = ConversationContext(
            post_id=910016,
            post_data={
                "title": "신작 안내",
                "content_blocks": [
                    {"type": "link", "url": url},
                    {
                        "type": "text",
                        "text": "작품명: 별개의 작품 B 신작 홍보입니다. 많은 관심 부탁드립니다",
                    },
                ],
            },
            comments=[],
        )

        decision = pipeline._record_source_native_official_detail_gate_decision(
            ctx,
            title,
            candidate_url=url,
            final_decision={},
            verification_result={},
        )

        self.assertFalse(decision["publish_allowed"])
        self.assertTrue(decision["candidate_preserved"])
        self.assertFalse(decision["bypassed_gate"])
        self.assertEqual(
            ctx._last_promotion_gate_state["scope"]["scope_kind"],
            "context_only",
        )

    def test_direct_image_typed_author_meta_without_non_image_text_is_context_only_hold(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        title = "사진 속의 연재작"
        ctx = self._direct_image_context(post_id=910010, title=title)
        final_decision = {
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
            "discussion_type": "author_meta",
        }

        decision = pipeline._record_direct_image_work_surface_gate_decision(
            ctx,
            title,
            candidate_url="https://novelpia.com/novel/910010",
            final_decision=final_decision,
            verification_result={},
        )

        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertTrue(decision["candidate_preserved"])
        self.assertFalse(decision["bypassed_gate"])
        self.assertEqual(
            final_decision["_promotion_gate_state"]["scope"]["scope_kind"],
            "context_only",
        )
        self.assertEqual(
            final_decision["_promotion_gate_state"]["scope"]["direct_bridge_sources"],
            [],
        )
        self.assertIn(
            "image_identity_without_non_image_relation_bridge",
            decision["reason_codes"],
        )

    def test_direct_image_author_meta_later_typed_field_cannot_be_shadowed(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        title = "이미지 정체성 후보"
        ctx = self._direct_image_context(post_id=910014, title=title)
        final_decision = {
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
            "primary_subject_type": "person",
            "subtype": "author_talk",
            "discussion_type": "author_meta",
        }

        decision = pipeline._record_direct_image_work_surface_gate_decision(
            ctx,
            title,
            candidate_url="https://novelpia.com/novel/910014",
            final_decision=final_decision,
            verification_result={},
        )

        self.assertFalse(decision["publish_allowed"])
        self.assertTrue(decision["candidate_preserved"])
        self.assertFalse(decision["bypassed_gate"])
        self.assertEqual(
            final_decision["_promotion_gate_state"]["scope"]["scope_kind"],
            "context_only",
        )
        self.assertIn(
            "image_identity_without_non_image_relation_bridge",
            decision["reason_codes"],
        )

    def test_direct_image_author_meta_exact_title_alone_stays_hold(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        title = "사진 속의 연재작"
        ctx = self._direct_image_context(
            post_id=910011,
            title=title,
            post_title=title,
        )
        final_decision = {
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
            "discussion_type": "author_talk",
        }

        decision = pipeline._record_direct_image_work_surface_gate_decision(
            ctx,
            title,
            candidate_url="https://novelpia.com/novel/910011",
            final_decision=final_decision,
            verification_result={},
        )

        self.assertFalse(decision["publish_allowed"])
        self.assertEqual(
            final_decision["_promotion_gate_state"]["scope"]["scope_kind"],
            "context_only",
        )
        self.assertIn(
            "image_identity_without_non_image_relation_bridge",
            decision["reason_codes"],
        )

    def test_direct_image_author_meta_with_specific_work_relation_can_publish(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        title = "사진 속의 연재작"
        ctx = self._direct_image_context(
            post_id=910012,
            title=title,
            post_title=f"{title} 이번 화 전개 좋더라",
        )
        final_decision = {
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
            "discussion_type": "author_meta",
        }

        decision = pipeline._record_direct_image_work_surface_gate_decision(
            ctx,
            title,
            candidate_url="https://novelpia.com/novel/910012",
            final_decision=final_decision,
            verification_result={},
        )

        self.assertEqual(decision["status"], "publish")
        self.assertTrue(decision["publish_allowed"])
        self.assertFalse(decision["bypassed_gate"])
        self.assertEqual(
            final_decision["_promotion_gate_state"]["scope"]["scope_kind"],
            "current_work",
        )

    def test_direct_image_normal_image_only_work_surface_remains_publishable(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        title = "사진 속의 연재작"
        ctx = self._direct_image_context(post_id=910013, title=title)
        final_decision = {
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
            "discussion_type": "review",
        }

        decision = pipeline._record_direct_image_work_surface_gate_decision(
            ctx,
            title,
            candidate_url="https://novelpia.com/novel/910013",
            final_decision=final_decision,
            verification_result={},
        )

        self.assertEqual(decision["status"], "publish")
        self.assertTrue(decision["publish_allowed"])
        self.assertFalse(decision["bypassed_gate"])
        self.assertEqual(
            final_decision["_promotion_gate_state"]["scope"]["scope_kind"],
            "current_work",
        )

    def test_direct_image_wrong_plausible_detail_url_is_withheld(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        title = "OCR로 확인된 작품"
        wrong_url = "https://novelpia.com/novel/999999"
        ctx = self._direct_image_context(post_id=910019, title=title)
        ctx.fetched_page_info = [
            self._fetched_novel_detail(wrong_url, "URL이 실제로 가리키는 다른 작품")
        ]
        final_decision = {
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
            "discussion_type": "review",
        }

        decision = pipeline._record_direct_image_work_surface_gate_decision(
            ctx,
            title,
            candidate_url=wrong_url,
            final_decision=final_decision,
            verification_result={},
        )

        self.assertTrue(decision["publish_allowed"])
        self.assertEqual(decision["official_title"], title)
        self.assertIsNone(decision["official_url"])
        self.assertFalse(decision["bypassed_gate"])
        self.assertEqual(ctx._last_promotion_gate_state["candidate_url"], "")
        self.assertTrue(
            any(
                item["reason_code"] == "direct_image_official_url_pair_unverified"
                and item["title_url_match"] is False
                for item in ctx._last_promotion_gate_evidence
            )
        )

    def test_direct_image_exact_fetched_title_url_pair_is_publishable(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        title = "OCR로 확인된 작품"
        url = "https://novelpia.com/novel/910020"
        ctx = self._direct_image_context(post_id=910020, title=title)
        ctx.fetched_page_info = [self._fetched_novel_detail(url, title)]

        decision = pipeline._record_direct_image_work_surface_gate_decision(
            ctx,
            title,
            candidate_url=url,
            final_decision={
                "work_resolution": "resolved",
                "title_resolution_state": "resolved",
                "discussion_type": "review",
            },
            verification_result={},
        )

        self.assertTrue(decision["publish_allowed"])
        self.assertEqual(decision["official_title"], title)
        self.assertEqual(decision["official_url"], url)
        self.assertFalse(decision["bypassed_gate"])
        self.assertIn("title_url_pair_verified", decision["reason_codes"])

    def test_direct_image_deleted_exact_title_url_is_withheld(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        title = "삭제 전 OCR로 확인된 작품"
        url = "https://novelpia.com/novel/910023"
        ctx = self._direct_image_context(post_id=910023, title=title)
        ctx.fetched_page_info = [
            self._fetched_novel_detail(url, title, content_status="deleted")
        ]

        decision = pipeline._record_direct_image_work_surface_gate_decision(
            ctx,
            title,
            candidate_url=url,
            final_decision={
                "work_resolution": "resolved",
                "title_resolution_state": "resolved",
                "discussion_type": "review",
            },
            verification_result={},
        )

        self.assertTrue(decision["publish_allowed"])
        self.assertEqual(decision["official_title"], title)
        self.assertIsNone(decision["official_url"])
        self.assertFalse(decision["bypassed_gate"])
        self.assertTrue(
            any(
                item["reason_code"] == "direct_image_official_url_pair_unverified"
                and item["candidate_url"] == url
                and item["title_url_match"] is False
                for item in ctx._last_promotion_gate_evidence
            )
        )

    def test_serializer_selector_accepts_cached_source_native_authority(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        title = "캐시에 고정된 작품"
        url = "https://novelpia.com/novel/910014"
        ctx = ConversationContext(
            post_id=910014,
            post_data={"title": "검색 결과와 무관한 글"},
            comments=[],
        )
        ctx._source_native_official_detail_identity_checked = True
        ctx._source_native_official_detail_identity = {"title": title, "url": url}
        evidence = candidate_inventory_evidence_from_sources(
            [{"official_title": title, "heretic_url": url}]
        )

        selected = pipeline._select_authoritative_serializer_hold_candidate(
            ctx=ctx,
            inventory_evidence=evidence,
            prior_contract=None,
        )

        self.assertEqual(selected, {"title": title, "url": url})

    def test_serializer_selector_accepts_prior_typed_exact_pair_authority(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        title = "타입 계약으로 검증된 작품"
        url = "https://novelpia.com/novel/910015"
        ctx = ConversationContext(
            post_id=910015,
            post_data={"title": "이미지에 작품이 표시됨"},
            comments=[],
        )
        evidence = candidate_inventory_evidence_from_sources(
            [{"official_title": title, "heretic_url": url}]
        )
        prior = evaluate_publish_contract(
            GroundingState(
                post_id=910015,
                candidate_title=title,
                candidate_url=url,
                official_title_exists=True,
                row_discusses_work_as_work=False,
                scope=ScopeState(scope_kind="context_only", confidence="high"),
            ),
            [
                EvidenceRecord(
                    kind="prior_typed_exact_pair",
                    supports_publish=False,
                    candidate_title=title,
                    candidate_url=url,
                    title_url_match=True,
                )
            ],
        )

        with patch.object(
            pipeline, "_title_matches_direct_image_partial", return_value=True
        ):
            selected = pipeline._select_authoritative_serializer_hold_candidate(
                ctx=ctx,
                inventory_evidence=evidence,
                prior_contract=prior,
            )

        self.assertEqual(selected, {"title": title, "url": url})

    def test_serializer_selector_accepts_fetched_exact_pair_authority(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        title = "페치 정식 제목 작품"
        url = "https://novel.munpia.com/910016"
        ctx = ConversationContext(
            post_id=910016,
            post_data={"title": "이미지 작품 확인"},
            comments=[],
        )
        ctx.fetched_page_info = [self._fetched_novel_detail(url, title)]
        evidence = candidate_inventory_evidence_from_sources(
            [{"official_title": title, "heretic_url": url}]
        )

        with patch.object(
            pipeline, "_title_matches_direct_image_partial", return_value=True
        ):
            selected = pipeline._select_authoritative_serializer_hold_candidate(
                ctx=ctx,
                inventory_evidence=evidence,
            )

        self.assertEqual(selected, {"title": title, "url": url})

    def test_serializer_two_verified_pairs_are_ambiguous_and_unselected(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        pairs = (
            ("검증된 첫 작품", "https://novelpia.com/novel/910017"),
            ("검증된 둘째 작품", "https://novelpia.com/novel/910018"),
        )
        ctx = ConversationContext(
            post_id=910017,
            post_data={"title": "이미지 후보 둘"},
            comments=[],
        )
        evidence = candidate_inventory_evidence_from_sources(
            [
                {"official_title": title, "heretic_url": url}
                for title, url in pairs
            ]
        )
        prior = evaluate_publish_contract(
            GroundingState(
                post_id=910017,
                candidate_title="",
                row_discusses_work_as_work=False,
                scope=ScopeState(scope_kind="unknown", confidence="low"),
            ),
            [
                EvidenceRecord(
                    kind="prior_typed_exact_pair",
                    supports_publish=False,
                    candidate_title=title,
                    candidate_url=url,
                    title_url_match=True,
                )
                for title, url in pairs
            ],
        )

        with patch.object(
            pipeline, "_title_matches_direct_image_partial", return_value=True
        ):
            selected = pipeline._select_authoritative_serializer_hold_candidate(
                ctx=ctx,
                inventory_evidence=evidence,
                prior_contract=prior,
            )

        self.assertEqual(selected, {})

    def test_serializer_url_shape_without_authority_is_not_selected(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        title = "URL 모양만 그럴듯한 작품"
        url = "https://novelpia.com/novel/910019"
        ctx = ConversationContext(
            post_id=910019,
            post_data={"title": "이미지 후보"},
            comments=[],
        )
        evidence = candidate_inventory_evidence_from_sources(
            [{"official_title": title, "heretic_url": url}]
        )

        with patch.object(
            pipeline, "_title_matches_direct_image_partial", return_value=True
        ):
            selected = pipeline._select_authoritative_serializer_hold_candidate(
                ctx=ctx,
                inventory_evidence=evidence,
                prior_contract=None,
            )

        self.assertEqual(selected, {})

    def test_serializer_unselected_inventory_has_non_null_scope_and_clears_public_leaks(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        sources = [
            {
                "official_title": "보존 후보 A",
                "heretic_url": "https://novelpia.com/novel/910020",
            },
            {
                "official_title": "보존 후보 B",
                "heretic_url": "https://novelpia.com/novel/910021",
            },
        ]
        evidence = candidate_inventory_evidence_from_sources(sources)
        no_prior_ctx = ConversationContext(
            post_id=910020,
            post_data={"title": "검증 전 후보 둘"},
            comments=[],
        )
        with patch.object(
            pipeline, "_title_matches_direct_image_partial", return_value=True
        ):
            self.assertEqual(
                pipeline._select_authoritative_serializer_hold_candidate(
                    ctx=no_prior_ctx,
                    inventory_evidence=evidence,
                    prior_contract=None,
                ),
                {},
            )
        no_prior_seed = evaluate_publish_contract(
            GroundingState(
                post_id=910020,
                candidate_title="",
                row_discusses_work_as_work=False,
                scope=ScopeState(
                    scope_kind="unknown",
                    confidence="low",
                    conflict_reason_codes=["serializer_missing_typed_contract"],
                ),
            ),
            [],
        )

        contract = pipeline._build_serializer_inventory_only_publish_contract(
            prior_contract=no_prior_seed,
            inventory_evidence=evidence,
            extended_identity={
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "discussion_type": "author_meta",
            },
        )

        self.assertIsNotNone(contract.state.scope)
        self.assertEqual(contract.state.scope.scope_kind, "unknown")
        self.assertFalse(contract.decision.publish_allowed)
        self.assertTrue(contract.decision.candidate_preserved)
        self.assertFalse(contract.decision.bypassed_gate)
        self.assertIn(
            "candidate_inventory_unselected",
            contract.state.scope.conflict_reason_codes,
        )

        identity = {
            "official_title": "새면 안 되는 제목",
            "official_url": "https://example.invalid/leak",
            "novel_identity": {
                "official_title": "새면 안 되는 제목",
                "heretic_url": "https://example.invalid/leak",
                "confidence": "High",
            },
            "title_candidates": list(sources),
            "candidate_ledger": {
                "candidate_preservation_sources": list(sources),
            },
        }

        apply_publish_contract(identity, contract)

        self.assertIsNone(identity["official_title"])
        self.assertIsNone(identity["official_url"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertIsNone(identity["novel_identity"]["heretic_url"])
        self.assertEqual(identity["title_candidates"], sources)
        self.assertFalse(identity["promotion_decision"]["publish_allowed"])
        self.assertFalse(identity["promotion_decision"]["bypassed_gate"])

    def test_titleless_url_candidate_is_preserved_without_publication(self):
        state = GroundingState(
            post_id=20010066,
            candidate_title="",
            candidate_url="https://novelpia.com/novel/900066",
            row_discusses_work_as_work=False,
        )

        decision = can_publish_title(state, [])

        self.assertEqual(decision.status, "candidate_only")
        self.assertFalse(decision.publish_allowed)
        self.assertIsNone(decision.official_title)
        self.assertIsNone(decision.official_url)
        self.assertTrue(decision.candidate_preserved)
        self.assertFalse(decision.bypassed_gate)
        self.assertIn("candidate_url_preserved_without_title", decision.reason_codes)

    def test_inventory_contract_count_evidence_mismatch_fails_closed(self):
        evidence = candidate_inventory_evidence_from_sources(
            [{"official_title": "후보 A"}]
        )
        state = GroundingState(
            post_id=11700470,
            candidate_title="",
            candidate_inventory_count=2,
        )

        decision = can_publish_title(state, evidence)

        self.assertEqual(decision.status, "reject")
        self.assertFalse(decision.publish_allowed)
        self.assertFalse(decision.candidate_preserved)
        self.assertIn("candidate_inventory_evidence_mismatch", decision.reason_codes)

    def test_inventory_payload_changes_fingerprint_and_zero_default_is_omitted(self):
        zero_state = GroundingState(post_id=1, candidate_title="")
        self.assertNotIn("candidate_inventory_count", zero_state.to_dict())

        evidence_a = candidate_inventory_evidence_from_sources(
            [{"official_title": "후보 A"}]
        )
        evidence_b = candidate_inventory_evidence_from_sources(
            [{"official_title": "후보 B"}]
        )
        contract_a = evaluate_publish_contract(
            GroundingState(post_id=1, candidate_title="", candidate_inventory_count=1),
            evidence_a,
        )
        contract_b = evaluate_publish_contract(
            GroundingState(post_id=1, candidate_title="", candidate_inventory_count=1),
            evidence_b,
        )

        self.assertNotEqual(contract_a.input_fingerprint, contract_b.input_fingerprint)

    def test_candidate_inventory_count_rejects_noncanonical_numeric_values(self):
        for invalid in ("", "01", 1.9, True, -1):
            with self.subTest(value=invalid):
                with self.assertRaisesRegex(ValueError, "nonnegative int"):
                    GroundingState(
                        post_id=1,
                        candidate_title="",
                        candidate_inventory_count=invalid,
                    )
                with self.assertRaisesRegex(ValueError, "nonnegative int"):
                    grounding_state_from_dict(
                        {
                            "post_id": 1,
                            "candidate_title": "",
                            "candidate_inventory_count": invalid,
                        }
                    )

    def test_shared_gate_restores_authoritative_leading_identity_components(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        body_title = "변방계에서 회귀자로 살아남기"
        canonical_title = "[림월드]변방계에서 회귀자로 살아남기"
        url = "https://novelpia.com/novel/382324"
        ctx = ConversationContext(post_id=11698897, post_data={}, comments=[])
        ctx.fetched_page_info = [self._fetched_novel_detail(url, canonical_title)]
        final_decision = {}

        decision = pipeline._record_public_title_gate_decision(
            ctx,
            GroundingState(
                post_id=11698897,
                candidate_title=body_title,
                candidate_url=url,
                official_title_exists=True,
                row_discusses_work_as_work=True,
                title_resolution_state="resolved",
                work_resolution="resolved",
                scope=ScopeState(
                    scope_kind="current_work",
                    confidence="high",
                    direct_bridge_sources=["contract_test"],
                ),
            ),
            [
                EvidenceRecord(
                    kind="contract_test",
                    supports_publish=True,
                    reason_code="contract_test",
                    candidate_title=body_title,
                    candidate_url=url,
                    title_url_match=True,
                )
            ],
            final_decision=final_decision,
        )

        self.assertTrue(decision["publish_allowed"])
        self.assertEqual(decision["official_title"], canonical_title)
        self.assertEqual(decision["official_url"], url)
        self.assertFalse(decision["bypassed_gate"])
        self.assertEqual(ctx._last_promotion_gate_state["candidate_title"], canonical_title)
        self.assertEqual(
            ctx._last_promotion_gate_evidence[0]["candidate_title"], canonical_title
        )
        self.assertEqual(
            final_decision["_official_detail_display_binding"]["reason_code"],
            "official_detail_display_identity_component_restored",
        )

    def test_shared_gate_holds_different_authoritative_identity_component(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        candidate_title = "[다른게임]변방계에서 회귀자로 살아남기"
        canonical_title = "[림월드]변방계에서 회귀자로 살아남기"
        url = "https://novelpia.com/novel/382324"
        ctx = ConversationContext(post_id=11698897, post_data={}, comments=[])
        ctx.fetched_page_info = [self._fetched_novel_detail(url, canonical_title)]

        decision = pipeline._record_public_title_gate_decision(
            ctx,
            GroundingState(
                post_id=11698897,
                candidate_title=candidate_title,
                candidate_url=url,
                official_title_exists=True,
                row_discusses_work_as_work=True,
                title_resolution_state="resolved",
                work_resolution="resolved",
                scope=ScopeState(
                    scope_kind="current_work",
                    confidence="high",
                    direct_bridge_sources=["contract_test"],
                ),
            ),
            [
                EvidenceRecord(
                    kind="contract_test",
                    supports_publish=True,
                    reason_code="contract_test",
                    candidate_title=candidate_title,
                    candidate_url=url,
                    title_url_match=True,
                )
            ],
        )

        self.assertFalse(decision["publish_allowed"])
        self.assertTrue(decision["candidate_preserved"])
        self.assertFalse(decision["bypassed_gate"])
        self.assertIsNone(decision["official_title"])
        self.assertIsNone(decision["official_url"])
        self.assertIn("official_detail_display_title_mismatch", decision["reason_codes"])
        self.assertTrue(
            any(
                item["title_url_match"] is False
                and item["reason_code"] == "official_detail_display_title_mismatch"
                for item in ctx._last_promotion_gate_evidence
            )
        )

    def test_shared_gate_never_verifies_unfetched_detail_url(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        title = "관계 근거만 독립적으로 확인된 작품"
        url = "https://novelpia.com/novel/999991"
        ctx = ConversationContext(post_id=999991, post_data={}, comments=[])

        decision = pipeline._record_public_title_gate_decision(
            ctx,
            GroundingState(
                post_id=999991,
                candidate_title=title,
                candidate_url=url,
                official_title_exists=True,
                row_discusses_work_as_work=True,
                title_resolution_state="resolved",
                work_resolution="resolved",
                scope=ScopeState(
                    scope_kind="current_work",
                    confidence="high",
                    direct_bridge_sources=["independent_title_relation"],
                ),
            ),
            [
                EvidenceRecord(
                    kind="independent_title_relation",
                    supports_publish=True,
                    reason_code="independent_title_relation",
                    candidate_title=title,
                    candidate_url=url,
                    title_url_match=True,
                )
            ],
        )

        self.assertTrue(decision["publish_allowed"])
        self.assertEqual(decision["official_title"], title)
        self.assertIsNone(decision["official_url"])
        self.assertNotIn("title_url_pair_verified", decision["reason_codes"])
        self.assertFalse(decision["bypassed_gate"])
        self.assertIsNone(ctx._last_promotion_gate_evidence[0]["title_url_match"])

    def test_correct_title_final_restores_exact_url_canonical_display(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        body_title = "변방계에서 회귀자로 살아남기"
        canonical_title = "[림월드]변방계에서 회귀자로 살아남기"
        url = "https://novelpia.com/novel/382324"
        ctx = ConversationContext(post_id=11698897, post_data={}, comments=[])
        ctx.fetched_page_info = [self._fetched_novel_detail(url, canonical_title)]

        corrected = pipeline._correct_title_final(
            body_title,
            ctx,
            candidate_url=url,
        )

        self.assertEqual(corrected, canonical_title)

    def test_authoritative_display_normalizer_separates_badges_and_identity(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)

        self.assertEqual(
            pipeline._normalize_authoritative_fetched_title_display(
                "[독점][림월드]작품명 [완결]"
            ),
            "[림월드]작품명",
        )
        self.assertEqual(
            pipeline._normalize_authoritative_fetched_title_display(
                "[TS]작품명 [외전]"
            ),
            "[TS]작품명[외전]",
        )

    def test_shared_gate_does_not_launder_wrong_same_url_publish_evidence(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        body_title = "Border Realm Returner"
        canonical_title = "[RimWorld] Border Realm Returner"
        wrong_title = "Completely Different Work"
        url = "https://novelpia.com/novel/382324"
        ctx = ConversationContext(post_id=382324, post_data={}, comments=[])
        ctx.fetched_page_info = [self._fetched_novel_detail(url, canonical_title)]

        decision = pipeline._record_public_title_gate_decision(
            ctx,
            GroundingState(
                post_id=382324,
                candidate_title=body_title,
                candidate_url=url,
                official_title_exists=True,
                row_discusses_work_as_work=True,
                title_resolution_state="resolved",
                work_resolution="resolved",
                scope=ScopeState(
                    scope_kind="current_work",
                    confidence="high",
                    direct_bridge_sources=["contract_test"],
                ),
            ),
            [
                EvidenceRecord(
                    kind="forged_wrong_work_relation",
                    supports_publish=True,
                    reason_code="forged_wrong_work_relation",
                    candidate_title=wrong_title,
                    candidate_url=url,
                    title_url_match=True,
                )
            ],
        )

        self.assertFalse(decision["publish_allowed"])
        self.assertTrue(decision["candidate_preserved"])
        self.assertFalse(decision["bypassed_gate"])
        wrong_record = next(
            item
            for item in ctx._last_promotion_gate_evidence
            if item["kind"] == "forged_wrong_work_relation"
        )
        self.assertEqual(wrong_record["candidate_title"], wrong_title)
        self.assertFalse(wrong_record["supports_publish"])
        self.assertFalse(wrong_record["title_url_match"])

    def test_source_native_rechecks_late_fetched_deleted_page(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        url = "https://novelpia.com/novel/990001"
        ctx = ConversationContext(
            post_id=990001,
            post_data={
                "content_blocks": [
                    {"type": "text", "text": f"신작 작품 이야기 {url}"}
                ]
            },
            comments=[],
        )
        deleted_entry = self._fetched_novel_detail(
            url,
            "Late Deleted Exact Work",
            content_status="deleted",
        )

        def attach_deleted(_ctx, _url):
            _ctx.fetched_page_info = [deleted_entry]
            return deleted_entry

        with patch.object(
            pipeline,
            "_fetch_and_attach_page_info",
            side_effect=attach_deleted,
        ):
            identity = pipeline._source_native_official_detail_identity(ctx)

        self.assertEqual(identity, {})
        self.assertEqual(ctx._source_native_official_detail_identity, {})

    def test_fetched_canonical_consensus_preserves_distinct_unicode_titles(self):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        url = "https://novelpia.com/novel/990002"
        ctx = ConversationContext(post_id=990002, post_data={}, comments=[])
        ctx.fetched_page_info = [
            self._fetched_novel_detail(
                url,
                "Re:ゼロから始める異世界生活",
                page_title="Re:世界から始める異世界生活",
            )
        ]

        self.assertIsNone(pipeline._canonical_fetched_title_for_url(ctx, url))

    def test_publish_candidate_binding_does_not_collapse_distinct_unicode_titles(self):
        state = GroundingState(
            post_id=990003,
            candidate_title="Re:ゼロから始める異世界生活",
            row_discusses_work_as_work=True,
            scope=ScopeState(
                scope_kind="current_work",
                confidence="high",
                direct_bridge_sources=["contract_test"],
            ),
        )
        decision = can_publish_title(
            state,
            [
                EvidenceRecord(
                    kind="different_unicode_work",
                    supports_publish=True,
                    reason_code="different_unicode_work",
                    candidate_title="Re:世界から始める異世界生活",
                )
            ],
        )

        self.assertFalse(decision.publish_allowed)
        self.assertTrue(decision.candidate_preserved)
        self.assertFalse(decision.bypassed_gate)


class TitleBodySubjectConflictContractTest(unittest.TestCase):
    """Generalized subject arbitration without production title/post literals."""

    TITLE_A = "헤드라인 표면 작품"
    TITLE_B = "본문 인물 연결 작품"
    ALIAS_A = "헤드작"
    ALIAS_B = "본문작"
    CHARACTER_B = "본문인물"
    URL_A = "https://novelpia.com/novel/910101"
    URL_B = "https://novelpia.com/novel/910102"

    @staticmethod
    def _candidate(
        title,
        url,
        alias,
        *,
        role="primary",
        locked=True,
        active=True,
        source_tier="official_detail",
        page_type="novel_page",
    ):
        return DetectedTitle(
            official_title=title,
            heretic_url=url,
            confidence="High",
            alias_or_mention=alias,
            source_tier=source_tier,
            page_type=page_type,
            content_status="active" if active else "unavailable",
            locked=locked,
            reference_role=role,
        )

    @classmethod
    def _ctx(cls, *, body_text=None, title_alias=None):
        title_alias = title_alias or cls.ALIAS_A
        body_text = body_text or f"{cls.ALIAS_B} {cls.CHARACTER_B} 전개가 좋다"
        return ConversationContext(
            post_id=910100,
            post_data={
                "post_id": 910100,
                "title": f"{title_alias} 정말 재미있다",
                "content_blocks": [{"type": "text", "text": body_text}],
            },
            comments=[],
        )

    @staticmethod
    def _source(candidate, role):
        return {
            "official_title": candidate.official_title,
            "heretic_url": candidate.heretic_url,
            "confidence": candidate.confidence,
            "alias_or_mention": candidate.alias_or_mention,
            "source_tier": candidate.source_tier,
            "page_type": candidate.page_type,
            "content_status": candidate.content_status,
            "reference_role": candidate.reference_role,
            "preservation_role": role,
        }

    @classmethod
    def _final_decision(
        cls,
        candidate_a,
        candidate_b,
        *,
        primary,
        comparison=None,
    ):
        return {
            "discussion_type": "review",
            "work_resolution": "resolved",
            "title_resolution_state": "resolved",
            "primary_subject_type": "work_discussion",
            "primary_subject_text": f"메인 화제는 '{primary.official_title}' 감상이다.",
            "primary_work": cls._source(primary, "primary_work"),
            "comparison_target": (
                cls._source(comparison, "comparison_target") if comparison else None
            ),
            "title_candidates": [
                cls._source(candidate_a, "title_candidate"),
                cls._source(candidate_b, "title_candidate"),
            ],
            "candidate_preservation_sources": [
                cls._source(candidate_a, "title_candidate"),
                cls._source(candidate_b, "title_candidate"),
            ],
        }

    @classmethod
    def _run_gate(
        cls,
        *,
        candidate_a=None,
        candidate_b=None,
        ctx=None,
        primary=None,
        comparison=None,
        with_body_link=True,
    ):
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.enable_heretic_live_fetch = False
        candidate_a = candidate_a or cls._candidate(
            cls.TITLE_A, cls.URL_A, cls.ALIAS_A
        )
        candidate_b = candidate_b or cls._candidate(
            cls.TITLE_B, cls.URL_B, cls.ALIAS_B
        )
        ctx = ctx or cls._ctx()
        if with_body_link:
            ctx.verified_character_work_links = [
                {
                    "title": candidate_b.official_title,
                    "url": candidate_b.heretic_url,
                    "character": cls.CHARACTER_B,
                    "abbreviation": candidate_b.alias_or_mention,
                    "alias": candidate_b.alias_or_mention,
                    "matched_alias": candidate_b.alias_or_mention,
                }
            ]
        else:
            ctx.verified_character_work_links = []
        final_decision = cls._final_decision(
            candidate_a,
            candidate_b,
            primary=primary or candidate_a,
            comparison=comparison,
        )

        def _safe_url(*args, **kwargs):
            title = str(kwargs.get("title") or (args[1] if len(args) > 1 else ""))
            candidate_url = str(kwargs.get("candidate_url") or "")
            if candidate_url:
                return candidate_url
            if title == candidate_a.official_title:
                return candidate_a.heretic_url
            if title == candidate_b.official_title:
                return candidate_b.heretic_url
            return ""

        def _display_binding(_ctx, title, url, **_kwargs):
            return {
                "status": "compatible",
                "canonical_title": str(title or ""),
                "canonical_url": str(url or ""),
                "reason_code": "official_detail_display_title_exact",
            }

        with patch.object(
            pipeline,
            "_safe_official_detail_url_for_title",
            side_effect=_safe_url,
        ), patch.object(
            pipeline,
            "_official_detail_display_title_binding",
            side_effect=_display_binding,
        ), patch.object(
            pipeline,
            "_post_discusses_work_as_work",
            return_value=True,
        ):
            decision = pipeline._record_batch_alias_public_title_gate_decision(
                ctx,
                candidate_a,
                {
                    "alias": candidate_a.alias_or_mention,
                    "title": candidate_a.official_title,
                    "matched_url": candidate_a.heretic_url,
                    "source": "title_lead_alias_official_detail_release",
                    "source_tier": "official_detail",
                },
                final_decision=final_decision,
                verification_result={
                    "primary_work": cls._source(primary or candidate_a, "primary_work"),
                    "primary_subject_type": "work_discussion",
                    "primary_subject_text": (
                        f"메인 화제는 '{(primary or candidate_a).official_title}' 감상이다."
                    ),
                },
                title_candidates=[candidate_a, candidate_b],
            )
        return pipeline, ctx, final_decision, decision

    def test_ambiguous_title_body_subject_conflict_holds_and_preserves_both_pairs(self):
        pipeline, ctx, final_decision, decision = self._run_gate()

        self.assertEqual(len(pipeline._normalize_match_text(self.ALIAS_A)), 3)
        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertIsNone(decision["official_title"])
        self.assertIsNone(decision["official_url"])
        self.assertTrue(decision["candidate_preserved"])
        self.assertFalse(decision["bypassed_gate"])
        self.assertEqual(decision["scope"]["scope_kind"], "context_only")
        self.assertIn(
            "title_body_subject_conflict_unresolved", decision["reason_codes"]
        )
        self.assertIn(self.TITLE_B, decision["scope"]["competing_candidates"])
        inventory_pairs = {
            (record.get("candidate_title"), record.get("candidate_url"))
            for record in final_decision["_promotion_gate_evidence"]
            if record.get("kind") == "candidate_preservation"
        }
        self.assertEqual(
            inventory_pairs,
            {(self.TITLE_A, self.URL_A), (self.TITLE_B, self.URL_B)},
        )
        self.assertEqual(
            ctx._last_publish_contract.trace.post_gate_identity.candidate_ledger_status,
            "promotion_blocked",
        )
        self.assertEqual(
            candidate_inventory_pairs(ctx._last_publish_contract.evidence),
            frozenset(
                {
                    (self.TITLE_A, self.URL_A),
                    (self.TITLE_B, self.URL_B),
                }
            ),
        )
        serialized_identity = {
            "official_title": self.TITLE_A,
            "heretic_url": self.URL_A,
            "novel_identity": {
                "official_title": self.TITLE_A,
                "heretic_url": self.URL_A,
                "confidence": "High",
            },
        }
        apply_publish_contract(serialized_identity, ctx._last_publish_contract)
        convergence = audit_rows(
            [
                {
                    "post_id": 910100,
                    "analysis_result": {"identity": serialized_identity},
                }
            ]
        )
        self.assertEqual(convergence["gate"], "GO")
        self.assertEqual(convergence["summary"]["violation_row_count"], 0)

    def test_explicit_comparison_keeps_clear_title_primary_publish(self):
        candidate_a = self._candidate(self.TITLE_A, self.URL_A, self.ALIAS_A)
        candidate_b = self._candidate(
            self.TITLE_B,
            self.URL_B,
            self.ALIAS_B,
            role="mentioned",
        )
        _, _, _, decision = self._run_gate(
            candidate_a=candidate_a,
            candidate_b=candidate_b,
            primary=candidate_a,
            comparison=candidate_b,
        )

        self.assertEqual(decision["status"], "publish")
        self.assertTrue(decision["publish_allowed"])
        self.assertEqual(decision["official_title"], self.TITLE_A)
        self.assertEqual(decision["official_url"], self.URL_A)
        self.assertFalse(decision["bypassed_gate"])
        self.assertNotIn(
            "title_body_subject_conflict_unresolved", decision["reason_codes"]
        )

    def test_explicit_body_primary_selects_body_candidate_and_preserves_headline_candidate(self):
        candidate_a = self._candidate(
            self.TITLE_A,
            self.URL_A,
            self.ALIAS_A,
            role="mentioned",
        )
        candidate_b = self._candidate(self.TITLE_B, self.URL_B, self.ALIAS_B)
        _, ctx, final_decision, decision = self._run_gate(
            candidate_a=candidate_a,
            candidate_b=candidate_b,
            primary=candidate_b,
        )

        self.assertEqual(decision["status"], "publish")
        self.assertTrue(decision["publish_allowed"])
        self.assertEqual(decision["official_title"], self.TITLE_B)
        self.assertEqual(decision["official_url"], self.URL_B)
        self.assertFalse(decision["bypassed_gate"])
        self.assertFalse(ctx._last_publish_contract.trace.bypassed_gate)
        self.assertTrue(ctx._title_body_subject_body_primary_selected)
        preserved_pairs = {
            (source.get("official_title"), source.get("heretic_url"))
            for source in final_decision["candidate_preservation_sources"]
        }
        self.assertIn((self.TITLE_A, self.URL_A), preserved_pairs)
        self.assertEqual(
            candidate_inventory_pairs(ctx._last_publish_contract.evidence),
            frozenset(
                {
                    (self.TITLE_A, self.URL_A),
                    (self.TITLE_B, self.URL_B),
                }
            ),
        )

    def test_same_official_pair_does_not_create_false_subject_conflict(self):
        candidate_a = self._candidate(self.TITLE_A, self.URL_A, self.ALIAS_A)
        candidate_b = self._candidate(
            "헤드라인 표면 작품 [정식판]",
            self.URL_A,
            self.ALIAS_B,
        )
        _, _, _, decision = self._run_gate(
            candidate_a=candidate_a,
            candidate_b=candidate_b,
            primary=candidate_a,
        )

        self.assertEqual(decision["status"], "publish")
        self.assertTrue(decision["publish_allowed"])
        self.assertNotIn(
            "title_body_subject_conflict_unresolved", decision["reason_codes"]
        )

    def test_search_only_secondary_candidate_does_not_overblock_title_primary(self):
        ctx = self._ctx(body_text="헤드작 주인공 전개가 시원해서 좋다")
        search_only_b = self._candidate(
            self.TITLE_B,
            "https://novelpia.com/search?keyword=secondary-work",
            self.ALIAS_B,
            role="mentioned",
            source_tier="official_search",
            page_type="search_result",
        )
        _, _, _, decision = self._run_gate(
            ctx=ctx,
            candidate_b=search_only_b,
            with_body_link=False,
        )

        self.assertEqual(decision["status"], "publish")
        self.assertTrue(decision["publish_allowed"])
        self.assertEqual(decision["official_title"], self.TITLE_A)
        self.assertNotIn(self.TITLE_B, decision["scope"]["competing_candidates"])
        self.assertNotIn(
            "title_body_subject_conflict_unresolved", decision["reason_codes"]
        )


if __name__ == "__main__":
    unittest.main()
