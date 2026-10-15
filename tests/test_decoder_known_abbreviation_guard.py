from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import llm_batch.experts.decoder as decoder_module  # noqa: E402
from llm_batch.experts.decoder import DecoderExpert  # noqa: E402


def _ctx(search_results: list[dict] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        expert_outputs={},
        post_data={"title": "", "content_blocks": []},
        comments=[],
        search_results=search_results or [],
        snippet_hints={},
    )


class DecoderKnownAbbreviationGuardTest(unittest.TestCase):
    def test_known_abbreviation_without_independent_evidence_stays_hint_only(self) -> None:
        decoder = DecoderExpert(llm_client=None)
        term = {
            "original": "주전무",
            "interpretations": [{"type": "novel_abbreviation", "context_fit": "medium"}],
            "best_match": {"title": None, "confidence": "low"},
        }

        rescued = decoder._rescue_null_title(
            original="주전무",
            term=term,
            title_pool=[],
            official_titles=[],
            search_results=[],
            ctx=_ctx(),
        )

        self.assertEqual(rescued, (None, 0.0, None))

    def test_known_abbreviation_does_not_override_llm_non_title_without_evidence(self) -> None:
        decoder = DecoderExpert(llm_client=None)
        term = {
            "original": "주전무",
            "interpretations": [{"type": "general_expression", "context_fit": "high"}],
            "best_match": {
                "title": None,
                "confidence": "none",
                "reason": "작품 제목이 아닌 일반적인 표현",
                "is_grounded": False,
            },
        }

        rescued = decoder._rescue_null_title(
            original="주전무",
            term=term,
            title_pool=[],
            official_titles=[],
            search_results=[],
            ctx=_ctx(),
        )

        self.assertEqual(rescued, (None, 0.0, None))

    def test_known_abbreviation_with_search_evidence_can_rescue(self) -> None:
        decoder = DecoderExpert(llm_client=None)
        term = {
            "original": "주전무",
            "interpretations": [{"type": "general_expression", "context_fit": "high"}],
            "best_match": {
                "title": None,
                "confidence": "none",
                "reason": "작품 제목이 아닌 일반적인 표현",
                "is_grounded": False,
            },
        }

        rescued = decoder._rescue_null_title(
            original="주전무",
            term=term,
            title_pool=[],
            official_titles=[],
            search_results=[
                {
                    "title": "주무시기 전에 무엇을 하셨나요? 작품 정보",
                    "url": "https://page.kakao.com/content/123",
                    "snippet": "주무시기 전에 무엇을 하셨나요? 웹소설 작품 상세",
                }
            ],
            ctx=_ctx(),
        )

        self.assertEqual(
            rescued,
            ("주무시기 전에 무엇을 하셨나요?", 0.95, "known_abbreviation"),
        )

    def test_resolved_mapping_known_match_without_anchor_does_not_seed_suspected_title(self) -> None:
        decoder = DecoderExpert(llm_client=None)
        original_registry = decoder_module.KNOWN_ABBREVIATIONS
        try:
            decoder_module.KNOWN_ABBREVIATIONS = {"가가": "전혀 다른 작품명"}
            ctx = _ctx()
            ctx._resolved_mappings = [("가가", "전혀 다른 작품명")]

            decoder._init_suspected_titles({"decoded_terms": []}, ctx)

            self.assertEqual(ctx.suspected_titles, [])
        finally:
            decoder_module.KNOWN_ABBREVIATIONS = original_registry

    def test_resolved_mapping_known_match_with_official_anchor_can_seed_suspected_title(self) -> None:
        decoder = DecoderExpert(llm_client=None)
        original_registry = decoder_module.KNOWN_ABBREVIATIONS
        try:
            decoder_module.KNOWN_ABBREVIATIONS = {"가가": "전혀 다른 작품명"}
            ctx = _ctx([
                {
                    "title": "웹소설로 꿈꾸는 세상! - 전혀 다른 작품명",
                    "url": "https://novelpia.com/novel/123",
                    "snippet": "전혀 다른 작품명 작품 상세",
                }
            ])
            ctx._resolved_mappings = [("가가", "전혀 다른 작품명")]

            decoder._init_suspected_titles({"decoded_terms": []}, ctx)

            self.assertEqual(len(ctx.suspected_titles), 1)
            self.assertEqual(ctx.suspected_titles[0]["title"], "전혀 다른 작품명")
            self.assertEqual(ctx.suspected_titles[0]["confidence"], 0.88)
        finally:
            decoder_module.KNOWN_ABBREVIATIONS = original_registry

    def test_high_fit_interpretation_known_match_without_anchor_does_not_promote(self) -> None:
        decoder = DecoderExpert(llm_client=None)
        original_registry = decoder_module.KNOWN_ABBREVIATIONS
        try:
            decoder_module.KNOWN_ABBREVIATIONS = {"가가": "전혀 다른 작품명"}
            result = {
                "decoded_terms": [
                    {
                        "original": "가가",
                        "best_match": {"title": None, "confidence": "none"},
                        "interpretations": [
                            {
                                "type": "novel_title",
                                "context_fit": "high",
                                "value": "전혀 다른 작품명",
                            }
                        ],
                    }
                ],
                "overall_confidence": "none",
            }

            cleaned = decoder._auto_promote_high_fit_interpretation(result, _ctx())

            self.assertIsNone(cleaned["decoded_terms"][0]["best_match"]["title"])
            self.assertEqual(cleaned["overall_confidence"], "none")
        finally:
            decoder_module.KNOWN_ABBREVIATIONS = original_registry

    def test_high_fit_interpretation_known_match_with_official_anchor_can_promote(self) -> None:
        decoder = DecoderExpert(llm_client=None)
        original_registry = decoder_module.KNOWN_ABBREVIATIONS
        try:
            decoder_module.KNOWN_ABBREVIATIONS = {"가가": "전혀 다른 작품명"}
            result = {
                "decoded_terms": [
                    {
                        "original": "가가",
                        "best_match": {"title": None, "confidence": "none"},
                        "interpretations": [
                            {
                                "type": "novel_title",
                                "context_fit": "high",
                                "value": "전혀 다른 작품명",
                            }
                        ],
                    }
                ],
                "overall_confidence": "none",
            }
            ctx = _ctx([
                {
                    "title": "웹소설로 꿈꾸는 세상! - 전혀 다른 작품명",
                    "url": "https://novelpia.com/novel/123",
                    "snippet": "전혀 다른 작품명 작품 상세",
                }
            ])

            promoted = decoder._auto_promote_high_fit_interpretation(result, ctx)

            self.assertEqual(
                promoted["decoded_terms"][0]["best_match"]["title"],
                "전혀 다른 작품명",
            )
            self.assertEqual(promoted["decoded_terms"][0]["best_match"]["confidence"], "medium")
        finally:
            decoder_module.KNOWN_ABBREVIATIONS = original_registry

    def test_weak_thematic_guard_does_not_treat_registry_pair_as_explicit_support(self) -> None:
        decoder = DecoderExpert(llm_client=None)
        original_registry = decoder_module.KNOWN_ABBREVIATIONS
        try:
            decoder_module.KNOWN_ABBREVIATIONS = {"abc": "전혀 다른 작품명"}
            result = {
                "decoded_terms": [
                    {
                        "original": "abc",
                        "best_match": {"title": "전혀 다른 작품명", "confidence": "medium"},
                        "grounding": {"anchor_type": "search_only"},
                        "candidates": [],
                    }
                ],
                "overall_confidence": "medium",
                "overall_best_match": {"title": "전혀 다른 작품명", "confidence": "medium"},
            }

            guarded = decoder._guard_weak_thematic_title_inference(result, _ctx())

            term = guarded["decoded_terms"][0]
            self.assertIsNone(term["best_match"]["title"])
            self.assertEqual(term["best_match"]["confidence"], "none")
            self.assertTrue(term["_weak_thematic_rejected"])
            self.assertEqual(guarded["overall_best_match"], {"title": None, "confidence": "none"})
        finally:
            decoder_module.KNOWN_ABBREVIATIONS = original_registry

    def test_weak_thematic_guard_keeps_official_blob_alias_bridge(self) -> None:
        decoder = DecoderExpert(llm_client=None)
        original_registry = decoder_module.KNOWN_ABBREVIATIONS
        try:
            decoder_module.KNOWN_ABBREVIATIONS = {"abc": "전혀 다른 작품명"}
            result = {
                "decoded_terms": [
                    {
                        "original": "abc",
                        "best_match": {"title": "전혀 다른 작품명", "confidence": "medium"},
                        "grounding": {"anchor_type": "search_only"},
                        "candidates": [],
                    }
                ],
                "overall_confidence": "medium",
                "overall_best_match": {"title": "전혀 다른 작품명", "confidence": "medium"},
            }
            ctx = _ctx([
                {
                    "title": "abc - 전혀 다른 작품명",
                    "url": "https://namu.wiki/w/%EC%A0%84%ED%98%80%20%EB%8B%A4%EB%A5%B8%20%EC%9E%91%ED%92%88%EB%AA%85",
                    "snippet": "abc는 전혀 다른 작품명의 약칭으로 쓰인다.",
                }
            ])

            guarded = decoder._guard_weak_thematic_title_inference(result, ctx)

            self.assertEqual(
                guarded["decoded_terms"][0]["best_match"],
                {"title": "전혀 다른 작품명", "confidence": "medium"},
            )
        finally:
            decoder_module.KNOWN_ABBREVIATIONS = original_registry


if __name__ == "__main__":
    unittest.main()
