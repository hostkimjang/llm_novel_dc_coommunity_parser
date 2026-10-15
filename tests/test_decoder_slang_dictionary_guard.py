from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_batch.experts.decoder import DecoderExpert  # noqa: E402


class DecoderSlangDictionaryGuardTest(unittest.TestCase):
    def test_dictionary_match_does_not_create_high_confidence_best_match(self) -> None:
        decoder = DecoderExpert(llm_client=None)
        result = {"decoded_terms": [], "overall_confidence": "low"}

        merged = decoder._merge_dict_matches(
            result,
            {"전독시": "전지적 독자 시점"},
            ctx=None,
        )

        self.assertEqual(merged["overall_confidence"], "low")
        term = merged["decoded_terms"][0]
        self.assertEqual(term["original"], "전독시")
        self.assertEqual(term["best_match"], {"title": None, "confidence": "none"})
        self.assertEqual(
            term["resolution_note"],
            "dictionary_alias_hint_requires_independent_evidence",
        )
        self.assertEqual(term["candidates"][0]["official_title"], "전지적 독자 시점")
        self.assertEqual(term["candidates"][0]["search_evidence"], "slang_dictionary_hint")
        self.assertTrue(term["candidates"][0]["dictionary_alias_hint"])

    def test_dictionary_match_does_not_override_existing_best_match(self) -> None:
        decoder = DecoderExpert(llm_client=None)
        result = {
            "overall_confidence": "medium",
            "decoded_terms": [
                {
                    "original": "전독시",
                    "best_match": {"title": "검색으로 검증된 제목", "confidence": "medium"},
                    "candidates": [],
                }
            ],
        }

        merged = decoder._merge_dict_matches(
            result,
            {"전독시": "전지적 독자 시점"},
            ctx=None,
        )

        term = merged["decoded_terms"][0]
        self.assertEqual(term["best_match"], {"title": "검색으로 검증된 제목", "confidence": "medium"})
        self.assertEqual(term["candidates"][0]["search_evidence"], "slang_dictionary_hint")

    def test_sanitize_removes_dictionary_only_high_best_match(self) -> None:
        decoder = DecoderExpert(llm_client=None)
        result = {
            "decoded_terms": [
                {
                    "original": "전독시",
                    "best_match": {"title": "전지적 독자 시점", "confidence": "high"},
                    "candidates": [
                        {
                            "official_title": "전지적 독자 시점",
                            "search_evidence": "slang_dictionary",
                            "dictionary_alias_hint": True,
                        }
                    ],
                }
            ],
        }

        cleaned = decoder._sanitize_cross_term_dictionary_inference(
            result,
            {"전독시": "전지적 독자 시점"},
        )

        term = cleaned["decoded_terms"][0]
        self.assertEqual(term["best_match"]["title"], None)
        self.assertEqual(term["best_match"]["confidence"], "none")
        self.assertEqual(
            term["resolution_note"],
            "dictionary_alias_hint_requires_independent_evidence",
        )

    def test_sanitize_keeps_dictionary_title_with_independent_url_support(self) -> None:
        decoder = DecoderExpert(llm_client=None)
        result = {
            "decoded_terms": [
                {
                    "original": "전독시",
                    "best_match": {"title": "전지적 독자 시점", "confidence": "high"},
                    "candidates": [
                        {
                            "official_title": "전지적 독자 시점",
                            "url": "https://page.kakao.com/content/123",
                            "search_evidence": "카카오페이지 작품 상세 페이지 제목 일치",
                        }
                    ],
                }
            ],
        }

        cleaned = decoder._sanitize_cross_term_dictionary_inference(
            result,
            {"전독시": "전지적 독자 시점"},
        )

        self.assertEqual(
            cleaned["decoded_terms"][0]["best_match"],
            {"title": "전지적 독자 시점", "confidence": "high"},
        )


if __name__ == "__main__":
    unittest.main()
