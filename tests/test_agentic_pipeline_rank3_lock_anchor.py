"""rank3 (precision / 근본원인 B) 게이트 단위테스트 + title 보존 회귀.

대상: lock 부여를 'title_alias 단독 표면일치'에서 분리 — 본문 직앵커 / OCR 공식표제 / 공식 URL 중
1개 이상 동반 시에만 locked. 하드앵커 부재 시 locked 만 False 로 두고 official_title·confidence·
source_tier 는 보존(work_resolution=resolved·recall 손실 0).

핵심 회귀: 하드앵커가 없어 lock 이 해제될 때 official_title 과 confidence 가 보존되는지(title 보존),
하드앵커가 있을 때 lock 이 유지되는지. + OCR 공식표제 헬퍼 _has_image_explicit_title_anchor 의 판정.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_batch.agentic_pipeline import AgenticPipeline  # noqa: E402
from llm_batch.experts.orchestrator import ExpertType  # noqa: E402


class _Ctx(SimpleNamespace):
    def get_expert_output(self, expert, *_a, **_k):
        return (getattr(self, "_outputs", {}) or {}).get(expert, {})


def _make_ctx(*, image_enrichment=None, post_title="아생갤 개재밌네"):
    return _Ctx(
        _outputs={
            ExpertType.VERIFIER: {"verification_result": {}},
            ExpertType.DECODER: {},
            ExpertType.GATEKEEPER: {},
            ExpertType.DISCOURSE: {},
        },
        post_data={"title": post_title, "content_blocks": [], "image_enrichment": image_enrichment or []},
        search_results=[],
        comments=[],
        discourse_warning="",
        discourse_intent="",
        primary_domain="",
    )


class Rank3ImageExplicitTitleAnchorTest(unittest.TestCase):
    def setUp(self):
        self.p = object.__new__(AgenticPipeline)

    def test_cover_title_match_is_anchor(self):
        ctx = _make_ctx(image_enrichment=[
            {"explicit_work_title": "전지적 독자 시점", "evidence_type": "cover_title"},
        ])
        self.assertTrue(self.p._has_image_explicit_title_anchor(ctx, "전지적 독자 시점"))

    def test_explicit_text_match_is_anchor(self):
        ctx = _make_ctx(image_enrichment=[
            {"explicit_work_title": "전지적 독자 시점", "evidence_type": "explicit_text"},
        ])
        self.assertTrue(self.p._has_image_explicit_title_anchor(ctx, "전지적 독자 시점"))

    def test_mood_only_evidence_type_not_anchor(self):
        # 분위기/캐릭터/밈 류(evidence_type 이 explicit_text/cover_title 아님)는 앵커 아님(precision)
        ctx = _make_ctx(image_enrichment=[
            {"explicit_work_title": "전지적 독자 시점", "evidence_type": "scene_mood"},
        ])
        self.assertFalse(self.p._has_image_explicit_title_anchor(ctx, "전지적 독자 시점"))

    def test_title_mismatch_not_anchor(self):
        ctx = _make_ctx(image_enrichment=[
            {"explicit_work_title": "다른 작품", "evidence_type": "cover_title"},
        ])
        self.assertFalse(self.p._has_image_explicit_title_anchor(ctx, "전지적 독자 시점"))

    def test_no_image_enrichment_not_anchor(self):
        ctx = _make_ctx(image_enrichment=[])
        self.assertFalse(self.p._has_image_explicit_title_anchor(ctx, "전지적 독자 시점"))


class Rank3LockHardAnchorChokepointTest(unittest.TestCase):
    """_resolve_batch_memory_alias_candidate chokepoint 통합: 하드앵커 유무에 따른 lock + title 보존."""

    def _pipeline(self, *, matched_url=None, title_in_main=False, ocr_anchor=False, curated_anchor=False):
        p = object.__new__(AgenticPipeline)
        p.batch_context = SimpleNamespace(
            enabled=True,
            resolve_abbreviation_surface=lambda surface: (
                {
                    "title": "아카데미에서 살아남기",
                    "alias": "아생",
                    "confidence": 3,  # hit_confidence>=3 → base rank3(High)
                    "source": "batch_context",
                    "source_tier": "community",
                }
                if "아생" in str(surface)
                else None
            ),
        )
        for name in (
            "_is_generic_role_or_species_surface_title",
            "_is_platform_branding_title",
            "_looks_like_listing_title",
            "_is_structural_nonwork_title",
            "_is_discourse_marker_alias_surface",
            "_is_low_information_alias_surface",
            "_batch_alias_body_guess_conflicts_with_comment_answer",
            "_has_non_novel_media_evidence_for_title",
            "_has_final_non_webnovel_domain_marker",
            "_memory_query_blocks_batch_alias_rescue",
            "_is_low_specificity_rescue_key",
            "_has_family_alias_ambiguity",
        ):
            setattr(p, name, (lambda *a, **k: False))
        p._leading_discourse_marker = lambda *a, **k: ""
        p._search_inferred_alias_nonwork_block_reason = lambda *a, **k: ""
        p._can_promote_title_after_semantic_no_work = lambda *a, **k: True
        p._find_title_matched_official_url = lambda *a, **k: matched_url
        # rank1 신호(음수정합/critical)는 없음 → rank1 강등 미발화, rank3 효과만 격리
        p._abbrev_alias_lock_block_signal = lambda *a, **k: {"blocked": False, "reasons": []}
        # rank3 하드앵커 구성요소를 시나리오별로 제어
        p._title_mentioned_in_post_main_context = lambda *a, **k: title_in_main
        p._has_image_explicit_title_anchor = lambda *a, **k: ocr_anchor
        p._has_curated_alias_contextual_work_anchor = lambda *a, **k: curated_anchor
        return p

    def _run(self, **kw):
        p = self._pipeline(**kw)
        ctx = _make_ctx()
        return p._resolve_batch_memory_alias_candidate(ctx, verification_result={})

    def test_no_hard_anchor_unlocks_but_preserves_title_and_confidence(self):
        # 하드앵커 부재(본문직앵커/OCR/URL/curated 모두 없음) → locked=False 지만 title·High 보존(recall 손실 0)
        cand, hit = self._run(matched_url=None, title_in_main=False, ocr_anchor=False)
        self.assertIsNotNone(cand)
        self.assertEqual(cand.official_title, "아카데미에서 살아남기")  # title 보존 회귀
        self.assertFalse(cand.locked)
        self.assertEqual(cand.confidence, "High")  # rank3 는 confidence 를 내리지 않음(lock 만 분리)
        # fix1(displace 보호): unlock돼도 resolved_recall_anchor=True 로 다운스트림 displace 보호 신호 보존
        self.assertTrue(cand.resolved_recall_anchor)

    def test_curated_alias_contextual_anchor_keeps_lock(self):
        # fix2: 사람 큐레이션 확정 별칭 + 작품논의 컨텍스트 동반 시(다른 하드앵커 부재여도) lock 보존
        cand, hit = self._run(curated_anchor=True)
        self.assertTrue(cand.locked)
        self.assertEqual(cand.confidence, "High")
        self.assertEqual(cand.official_title, "아카데미에서 살아남기")

    def test_body_direct_anchor_keeps_lock(self):
        cand, hit = self._run(title_in_main=True)
        self.assertTrue(cand.locked)
        self.assertEqual(cand.confidence, "High")
        self.assertEqual(cand.official_title, "아카데미에서 살아남기")

    def test_ocr_official_title_anchor_keeps_lock(self):
        cand, hit = self._run(ocr_anchor=True)
        self.assertTrue(cand.locked)
        self.assertEqual(cand.confidence, "High")

    def test_official_url_keeps_lock(self):
        cand, hit = self._run(matched_url="https://novel.naver.com/webnovel/list?novelId=999")
        self.assertTrue(cand.locked)
        self.assertEqual(cand.confidence, "High")
        self.assertEqual(cand.source_tier, "official_detail")


class Rank3DisplaceProtectionTest(unittest.TestCase):
    """fix1: rank3 unlock(locked=False) 후보가 다운스트림 final-semantic-reread demotion 으로 displace 되지
    않도록 resolved_recall_anchor 가 has_official_candidate 를 보존하는지 직접 검증."""

    from llm_batch.domain.models import DetectedTitle as _DT  # noqa

    def _ctx(self):
        return _Ctx(
            _outputs={ExpertType.VERIFIER: {"verification_result": {}}, ExpertType.DECODER: {},
                      ExpertType.GATEKEEPER: {}, ExpertType.DISCOURSE: {}},
            post_data={"title": "아생갤 개재밌네", "content_blocks": []},
            search_results=[],
            comments=[],
        )

    def _pipeline(self):
        p = object.__new__(AgenticPipeline)
        # 후보 외 official 증거 경로를 모두 차단 → has_official_candidate 가 resolved_recall_anchor 로만 결정되게
        p._has_official_title_evidence = lambda *a, **k: False
        p._find_title_matched_official_url = lambda *a, **k: None
        p._collect_post_texts = lambda *a, **k: ("아생 갤 재밌네", "아생 추천 ㄱㄱ")
        return p

    def _cand(self, *, recall_anchor):
        from llm_batch.domain.models import DetectedTitle
        return DetectedTitle(
            official_title="아카데미에서 살아남기",
            alias_or_mention="아생",
            source_tier="community",
            locked=False,  # rank3 unlock 상태
            resolved_recall_anchor=recall_anchor,
            reference_role="primary",
        )

    def test_recall_anchor_preserves_official_candidate_protection(self):
        p = self._pipeline()
        ctx = self._ctx()
        out = p._verified_alias_context_for_final_semantic_reread(
            ctx=ctx, official_title="아카데미에서 살아남기", metadata={},
            verification_result={}, title_candidates=[self._cand(recall_anchor=True)],
        )
        # unlock(locked=False)·약 tier·공식증거 부재여도 resolved_recall_anchor 로 보호 유지
        self.assertTrue(out["has_official_evidence"])
        self.assertTrue(out["has_verified_alias"])

    def test_without_recall_anchor_protection_collapses(self):
        # 신호가 load-bearing 임을 증명: resolved_recall_anchor 없으면 보호 붕괴(=fix 전 displace 위험 재현)
        p = self._pipeline()
        ctx = self._ctx()
        out = p._verified_alias_context_for_final_semantic_reread(
            ctx=ctx, official_title="아카데미에서 살아남기", metadata={},
            verification_result={}, title_candidates=[self._cand(recall_anchor=False)],
        )
        self.assertFalse(out["has_official_evidence"])
        self.assertFalse(out["has_verified_alias"])


if __name__ == "__main__":
    unittest.main()
