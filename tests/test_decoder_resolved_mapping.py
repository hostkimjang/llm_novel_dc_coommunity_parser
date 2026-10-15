from __future__ import annotations

import unittest
from types import SimpleNamespace

from src.llm_batch.experts.decoder import DecoderExpert


class DecoderResolvedMappingTest(unittest.TestCase):
    def test_direct_image_conflict_genre_pattern_does_not_raise(self) -> None:
        decoder = DecoderExpert.__new__(DecoderExpert)
        decoder.emoji = "T"

        ctx = SimpleNamespace(
            post_data={
                "image_enrichment": [
                    {
                        "explicit_work_title": "이미지에 직접 나온 작품",
                        "title_role": "work_title",
                        "ocr_text": "#하렘물 이미지에 직접 나온 작품",
                    }
                ]
            }
        )

        refined = decoder._refine_resolved_mappings(
            ctx,
            [
                {
                    "abbrev": "하렘물",
                    "full": "검색으로 끌려온 다른 작품",
                    "source": "search",
                }
            ],
        )

        self.assertEqual(refined, [])


if __name__ == "__main__":
    unittest.main()
