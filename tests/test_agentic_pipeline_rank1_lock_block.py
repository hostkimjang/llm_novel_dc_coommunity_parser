"""rank1 (precision / 근본원인 B) 게이트 단위테스트 + title 보존 회귀.

대상: AgenticPipeline._abbrev_alias_lock_block_signal 와 _resolve_batch_memory_alias_candidate
chokepoint의 "음수 정합(decoder conflict) OR Verifier critical 반론 → 한 단계 강등(High→Medium,
locked True→False)·title 보존" 동작.

핵심 회귀 보장: blocked 시 candidate.official_title 은 그대로 보존되고(work_resolution resolved·recall 무손실)
locked/confidence 만 한 단계 내려간다. matched_url(official_detail 1차 앵커) 동반 시 면제(정당 lock 회귀 방지).
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


def _make_ctx(*, verifier=None, decoder=None, post_title="즉사무림 ㅈㄴ 재밌다", search_results=None):
    return _Ctx(
        _outputs={
            ExpertType.VERIFIER: {"verification_result": verifier or {}},
            ExpertType.DECODER: decoder or {},
            ExpertType.GATEKEEPER: {},
            ExpertType.DISCOURSE: {},
        },
        post_data={"title": post_title, "content_blocks": []},
        search_results=search_results or [],
        comments=[],
        discourse_warning="",
        discourse_intent="",
        primary_domain="",
    )


def _critical_verifier(action="reject"):
    return {"counter_arguments": [{"severity": "critical", "action": action, "issue": "본문 미언급"}]}


def _conflict_decoder(official_title="즉사기 들고 무림에 떨어지다", aligned=False):
    # conflict best_match 는 official_title 과 다른 제목을 가리키는 경합/충돌 디코드다
    # (_title_anchor_conflict=True). aligned=True 면 official_title 에 정합되는 별도 매칭을 추가해
    # conflict 가 상쇄됨을 검증한다.
    bm = {"title": "무림 가문의 천재", "confidence": "medium", "_title_anchor_conflict": True}
    terms = [{"original": "무림", "best_match": bm}]
    if aligned:
        terms.append(
            {"original": "즉사무림", "best_match": {"title": official_title, "confidence": "high"}}
        )
    return {"decoded_terms": terms}


class Rank1LockBlockSignalTest(unittest.TestCase):
    def setUp(self):
        self.p = object.__new__(AgenticPipeline)

    def test_clean_no_signal_not_blocked(self):
        ctx = _make_ctx()
        sig = self.p._abbrev_alias_lock_block_signal(ctx, "즉사기 들고 무림에 떨어지다", {})
        self.assertFalse(sig["blocked"])
        self.assertEqual(sig["reasons"], [])

    def test_verifier_critical_blocks(self):
        ctx = _make_ctx(verifier=_critical_verifier("reject"))
        sig = self.p._abbrev_alias_lock_block_signal(ctx, "즉사기 들고 무림에 떨어지다", _critical_verifier("reject"))
        self.assertTrue(sig["blocked"])
        self.assertIn("verifier_critical_counter", sig["reasons"])

    def test_verifier_critical_info_action_not_blocked(self):
        # severity critical 이지만 action 이 reject/nullify/downgrade 가 아니면 차단하지 않음
        vf = {"counter_arguments": [{"severity": "critical", "action": "note"}]}
        ctx = _make_ctx(verifier=vf)
        sig = self.p._abbrev_alias_lock_block_signal(ctx, "즉사기 들고 무림에 떨어지다", vf)
        self.assertFalse(sig["blocked"])

    def test_decoder_anchor_conflict_blocks(self):
        ctx = _make_ctx(decoder=_conflict_decoder(aligned=False))
        sig = self.p._abbrev_alias_lock_block_signal(ctx, "즉사기 들고 무림에 떨어지다", {})
        self.assertTrue(sig["blocked"])
        self.assertIn("decoder_anchor_conflict", sig["reasons"])

    def test_decoder_conflict_offset_by_aligned_match_not_blocked(self):
        # 같은 title 에 정합되는 decoder 매칭(rank>=2)이 있으면 conflict 상쇄 → 차단 안 함
        ctx = _make_ctx(decoder=_conflict_decoder(aligned=True))
        sig = self.p._abbrev_alias_lock_block_signal(ctx, "즉사기 들고 무림에 떨어지다", {})
        self.assertFalse(sig["blocked"])


class Rank1ChokepointDemoteTest(unittest.TestCase):
    """_resolve_batch_memory_alias_candidate chokepoint 통합: 강등·면제·title 보존."""

    def _pipeline_with_permissive_guards(self, *, matched_url=None):
        p = object.__new__(AgenticPipeline)
        p.batch_context = SimpleNamespace(
            enabled=True,
            resolve_abbreviation_surface=lambda surface: (
                {
                    "title": "즉사기 들고 무림에 떨어지다",
                    "alias": "즉사무림",
                    "confidence": 3,  # hit_confidence>=3 → 기본 rank3(High+locked)
                    "source": "batch_context",
                    "source_tier": "community",
                }
                if "즉사무림" in str(surface)
                else None
            ),
        )
        # chokepoint 도달까지의 가드들을 permissive 로 고정(게이트 효과만 격리 검증)
        permissive_false = (
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
        )
        for name in permissive_false:
            setattr(p, name, (lambda *a, **k: False))
        p._leading_discourse_marker = lambda *a, **k: ""
        p._search_inferred_alias_nonwork_block_reason = lambda *a, **k: ""
        p._can_promote_title_after_semantic_no_work = lambda *a, **k: True
        p._find_title_matched_official_url = lambda *a, **k: matched_url
        return p

    def _run(self, *, verifier=None, decoder=None, matched_url=None):
        p = self._pipeline_with_permissive_guards(matched_url=matched_url)
        ctx = _make_ctx(verifier=verifier, decoder=decoder)
        cand, hit = p._resolve_batch_memory_alias_candidate(ctx, verification_result=verifier or {})
        return cand, hit

    def test_baseline_no_signal_locks_high(self):
        cand, hit = self._run()
        self.assertIsNotNone(cand)
        self.assertEqual(cand.official_title, "즉사기 들고 무림에 떨어지다")
        self.assertTrue(cand.locked)
        self.assertEqual(cand.confidence, "High")

    def test_verifier_critical_demotes_but_preserves_title(self):
        cand, hit = self._run(verifier=_critical_verifier("reject"))
        self.assertIsNotNone(cand)
        # title 보존 회귀: official_title 은 baseline 과 동일하게 보존
        self.assertEqual(cand.official_title, "즉사기 들고 무림에 떨어지다")
        # locked/confidence 만 한 단계 강등
        self.assertFalse(cand.locked)
        self.assertEqual(cand.confidence, "Medium")

    def test_decoder_conflict_demotes_but_preserves_title(self):
        cand, hit = self._run(decoder=_conflict_decoder(aligned=False))
        self.assertIsNotNone(cand)
        self.assertEqual(cand.official_title, "즉사기 들고 무림에 떨어지다")
        self.assertFalse(cand.locked)
        self.assertEqual(cand.confidence, "Medium")

    def test_official_detail_matched_url_exempt_from_demote(self):
        # matched_url(official_detail 1차 앵커) 동반 시, critical 신호가 있어도 강등 면제
        cand, hit = self._run(
            verifier=_critical_verifier("reject"),
            matched_url="https://novel.naver.com/webnovel/list?novelId=12345",
        )
        self.assertIsNotNone(cand)
        self.assertEqual(cand.official_title, "즉사기 들고 무림에 떨어지다")
        self.assertTrue(cand.locked)
        self.assertEqual(cand.confidence, "High")
        self.assertEqual(cand.source_tier, "official_detail")


if __name__ == "__main__":
    unittest.main()
