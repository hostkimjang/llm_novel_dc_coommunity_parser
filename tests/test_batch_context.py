from __future__ import annotations

import unittest
import io
from contextlib import redirect_stderr
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_batch.domain.batch_context import BatchContextMemory  # noqa: E402
from alias_learning_test_inputs import qualified_learning_input


class BatchContextMemoryContractTest(unittest.TestCase):
    def test_composite_alias_learns_only_canonical_work_alias(self):
        memory = BatchContextMemory(enabled=True)
        result = {
            "identity": {
                "is_relevant": True,
                "novel_identity": {
                    "official_title": "즉사기 들고 무림에 떨어지다",
                    "confidence": "High",
                },
                "slang_insight": {
                    "detected_term": "즉사무림이유백",
                    "decoded_term": "즉사기 들고 무림에 떨어지다 + 이유백",
                    "canonical_work_alias": "즉사무림",
                    "alias_scope": "work_plus_character",
                    "store_in_slang_db": False,
                    "store_reason": "character_attached_composite",
                },
            }
        }
        decoded_terms = [
            {
                "original": "즉사무림이유백",
                "best_match": {
                    "title": "즉사기 들고 무림에 떨어지다",
                },
            }
        ]
        result, decoded_terms = qualified_learning_input(result, decoded_terms)
        memory.learn_from_result(result, decoded_terms=decoded_terms)
        self.assertEqual(memory.get_abbreviation("즉사무림"), "즉사기 들고 무림에 떨어지다")
        self.assertIsNone(memory.get_abbreviation("즉사무림이유백"))

    def test_pure_alias_contract_learns_alias_normally(self):
        memory = BatchContextMemory(enabled=True)
        result = {
            "identity": {
                "is_relevant": True,
                "novel_identity": {
                    "official_title": "죽었다 깨어도 수선",
                    "confidence": "High",
                },
                "slang_insight": {
                    "detected_term": "죽깨수",
                    "decoded_term": "죽었다 깨어도 수선",
                    "canonical_work_alias": "죽깨수",
                    "alias_scope": "pure_work_alias",
                    "store_in_slang_db": True,
                    "store_reason": "pure_work_alias",
                },
            }
        }
        result, decoded_terms = qualified_learning_input(
            result,
            [
                {
                    "original": "이제는 죽깨수 올 때 됐다",
                    "best_match": {
                        "title": "죽었다 깨어도 수선",
                    },
                }
            ],
        )
        memory.learn_from_result(result, decoded_terms=decoded_terms)
        self.assertEqual(memory.get_abbreviation("죽깨수"), "죽었다 깨어도 수선")
        self.assertIsNone(memory.get_abbreviation("이제는 죽깨수 올 때 됐다"))

    def test_exact_title_surface_is_not_learned_as_batch_alias(self):
        memory = BatchContextMemory(enabled=True)
        result = {
            "identity": {
                "is_relevant": True,
                "novel_identity": {
                    "official_title": "아카데미의 피해자",
                    "confidence": "High",
                },
                "slang_insight": {
                    "detected_term": "아카데미의 피해자",
                    "decoded_term": "아카데미의 피해자",
                    "canonical_work_alias": None,
                    "alias_scope": "pure_work_alias",
                    "store_in_slang_db": False,
                    "store_reason": "exact_title_not_alias",
                },
            }
        }
        memory.learn_from_result(
            result,
            decoded_terms=[
                {
                    "original": "아카데미의 피해자",
                    "best_match": {
                        "title": "아카데미의 피해자",
                    },
                }
            ],
        )

        self.assertIsNone(memory.get_abbreviation("아카데미의 피해자"))
        self.assertNotIn(memory._normalize("아카데미의 피해자"), memory.resolved_abbreviations)
        self.assertNotIn(memory._normalize("아카데미의 피해자"), memory.pending_abbreviations)
        self.assertEqual(memory.stats.get("abbreviation_exact_title_skipped"), 1)

    def test_slang_db_seed_without_structured_slang_support_stays_pending(self):
        memory = BatchContextMemory(enabled=True)

        memory.register_abbreviation_seed(
            "폰무림",
            "스마트폰 IN 무림학관",
            count=2,
            source_roles=["primary_work", "title_candidate"],
        )

        self.assertIsNone(memory.get_abbreviation("폰무림"))
        self.assertIn(memory._normalize("폰무림"), memory.pending_abbreviations)
        self.assertEqual(memory.stats.get("abbreviation_seed_review_held"), 1)

    def test_repeated_low_evidence_seed_does_not_promote_from_pending(self):
        memory = BatchContextMemory(enabled=True)

        for _ in range(2):
            memory.register_abbreviation_seed(
                "폰무림",
                "스마트폰 IN 무림학관",
                count=2,
                source_roles=["primary_work", "title_candidate"],
            )

        key = memory._normalize("폰무림")
        self.assertIsNone(memory.get_abbreviation("폰무림"))
        self.assertIn(key, memory.pending_abbreviations)
        self.assertEqual(memory.pending_abbreviations[key]["count"], 2)
        self.assertFalse(memory.pending_abbreviations[key]["allow_pending_promotion"])
        self.assertEqual(memory.stats.get("abbreviation_seed_review_held"), 2)
        self.assertEqual(memory.stats.get("abbreviation_pending_promotion_blocked"), 1)

    def test_repeated_generic_inline_alias_does_not_promote_from_pending(self):
        memory = BatchContextMemory(enabled=True)

        for _ in range(2):
            memory.register_abbreviation(
                "카드아카",
                "카드 아카데미 1타강사",
                confidence=3,
            )

        key = memory._normalize("카드아카")
        self.assertIsNone(memory.get_abbreviation("카드아카"))
        self.assertIn(key, memory.pending_abbreviations)
        self.assertEqual(memory.pending_abbreviations[key]["count"], 2)
        self.assertTrue(memory.pending_abbreviations[key]["generic_inline_alias"])
        self.assertEqual(memory.stats.get("abbreviation_pending_promotion_blocked"), 1)

    def test_slang_db_seed_with_structured_slang_support_promotes(self):
        memory = BatchContextMemory(enabled=True)

        memory.register_abbreviation_seed(
            "검머대",
            "검은머리 미군 대원수",
            count=2,
            source_roles=["primary_work", "slang_insight", "title_candidate"],
        )

        self.assertEqual(memory.get_abbreviation("검머대"), "검은머리 미군 대원수")
        self.assertNotIn(memory._normalize("검머대"), memory.pending_abbreviations)

    def test_slang_db_seed_logging_defaults_to_summary(self):
        memory = BatchContextMemory(enabled=True, seed_log_mode="summary")
        err = io.StringIO()

        with redirect_stderr(err):
            memory.register_abbreviation_seed(
                "검머대",
                "검은머리 미군 대원수",
                count=3,
                source_roles=["primary_work", "slang_insight", "title_candidate"],
            )

        self.assertEqual(err.getvalue(), "")
        messages = []
        summary = memory.flush_seed_log_summary(log_fn=messages.append)
        self.assertIsNotNone(summary)
        self.assertEqual(messages, [summary])
        self.assertIn("BatchMem seed preload summary", summary)
        self.assertIn("registered=1", summary)
        self.assertIn("검머대", summary)
        self.assertGreaterEqual(memory.stats.get("abbreviation_seed_log_suppressed", 0), 1)

    def test_slang_db_seed_logging_full_keeps_per_alias_lines(self):
        memory = BatchContextMemory(enabled=True, seed_log_mode="full")
        err = io.StringIO()

        with redirect_stderr(err):
            memory.register_abbreviation_seed(
                "검머대",
                "검은머리 미군 대원수",
                count=3,
                source_roles=["primary_work", "slang_insight", "title_candidate"],
            )

        self.assertIn("약칭 즉시등록", err.getvalue())
        self.assertIsNone(memory.flush_seed_log_summary(log_fn=lambda _msg: None))

    def test_known_non_novel_media_seed_is_quarantined_before_pending(self):
        memory = BatchContextMemory(enabled=True)

        memory.register_abbreviation_seed(
            "강연금",
            "강철의 연금술사",
            count=2,
            source_roles=["primary_work", "title_candidate"],
        )

        self.assertIsNone(memory.get_abbreviation("강연금"))
        self.assertNotIn(memory._normalize("강연금"), memory.pending_abbreviations)
        self.assertEqual(memory.stats.get("abbreviation_seed_quarantined"), 1)
        self.assertEqual(memory.stats.get("abbreviation_seed_review_held"), 0)

    def test_known_non_novel_media_seed_with_structured_support_is_quarantined(self):
        memory = BatchContextMemory(enabled=True)

        memory.register_abbreviation_seed(
            "프리렌",
            "장송의 프리렌",
            count=3,
            source_roles=["primary_work", "slang_insight", "title_candidate"],
        )

        self.assertIsNone(memory.get_abbreviation("프리렌"))
        self.assertNotIn(memory._normalize("프리렌"), memory.pending_abbreviations)
        self.assertEqual(memory.stats.get("abbreviation_seed_quarantined"), 1)

    def test_known_non_novel_media_alias_from_result_is_not_learned(self):
        memory = BatchContextMemory(enabled=True)

        result = {
            "identity": {
                "is_relevant": True,
                "novel_identity": {
                    "official_title": "시간을 달리는 소녀",
                    "confidence": "High",
                },
                "slang_insight": {
                    "detected_term": "시달소",
                    "decoded_term": "시간을 달리는 소녀",
                    "canonical_work_alias": "시달소",
                    "alias_scope": "pure_work_alias",
                    "store_in_slang_db": True,
                    "store_reason": "pure_work_alias",
                },
            }
        }

        memory.learn_from_result(result, decoded_terms=[])

        self.assertIsNone(memory.get_abbreviation("시달소"))
        self.assertNotIn(memory._normalize("시달소"), memory.pending_abbreviations)
        self.assertEqual(memory.stats.get("abbreviation_seed_quarantined"), 1)

    def test_title_resolution_disallowed_result_is_not_learned(self):
        memory = BatchContextMemory(enabled=True)
        result = {
            "identity": {
                "is_relevant": True,
                "title_resolution_state": "context_only",
                "title_resolution_allowed": False,
                "consistency_flags": ["semantic_seed_review_specific_work_denied"],
                "novel_identity": {
                    "official_title": "Alpha Beta Novel",
                    "confidence": "High",
                },
                "slang_insight": {
                    "detected_term": "abcxyz",
                    "decoded_term": "Alpha Beta Novel",
                    "canonical_work_alias": "abcxyz",
                    "alias_scope": "pure_work_alias",
                    "store_in_slang_db": True,
                    "store_reason": "pure_work_alias",
                },
            }
        }

        memory.learn_from_result(
            result,
            decoded_terms=[
                {
                    "original": "abcxyz",
                    "best_match": {"title": "Alpha Beta Novel"},
                }
            ],
        )

        self.assertIsNone(memory.get_abbreviation("abcxyz"))
        self.assertNotIn(memory._normalize("abcxyz"), memory.pending_abbreviations)

if __name__ == "__main__":
    unittest.main()
