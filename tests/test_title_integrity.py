from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_batch.domain.title_integrity import (  # noqa: E402
    exact_title_integrity_match,
    parse_title_integrity_parts,
)


class TitleIntegrityTest(unittest.TestCase):
    def test_repeated_identity_components_are_ordered_and_exact(self):
        parts = parse_title_integrity_parts("[TS][림월드] 작품명")

        self.assertEqual(parts.identity_components, ("ts", "림월드"))
        self.assertEqual(parts.base_normalized, "작품명")
        self.assertTrue(
            exact_title_integrity_match("[TS][림월드] 작품명", "【TS】【림월드】작품명")
        )
        self.assertFalse(exact_title_integrity_match("[TS][림월드]작품명", "[TS]작품명"))

    def test_base_and_identity_suffixes_are_not_fuzzy(self):
        self.assertFalse(exact_title_integrity_match("[림월드]작품명", "[림월드]작품명 외전"))
        self.assertFalse(exact_title_integrity_match("[림월드]작품명", "[다른게임]작품명"))
        self.assertFalse(exact_title_integrity_match("작품명", "작품명 외전"))

    def test_small_presentation_badges_do_not_change_identity(self):
        self.assertTrue(exact_title_integrity_match("작품명", "[독점][완결] 작품명"))
        self.assertTrue(exact_title_integrity_match("[림월드]작품명", "[독점][림월드] 작품명"))
        self.assertTrue(exact_title_integrity_match("작품명", "작품명 [독점][완결]"))
        self.assertFalse(exact_title_integrity_match("작품명", "작품명 [외전]"))

    def test_unicode_scripts_are_preserved_in_exact_key(self):
        self.assertTrue(
            exact_title_integrity_match(
                "Re:ゼロから始める異世界生活",
                "Ｒｅ：ゼロから始める異世界生活",
            )
        )
        self.assertFalse(
            exact_title_integrity_match(
                "Re:ゼロから始める異世界生活",
                "Re:世界から始める異世界生活",
            )
        )


if __name__ == "__main__":
    unittest.main()
