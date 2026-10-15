from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_batch.experts.deliberation import EvidenceScorer  # noqa: E402
from llm_batch.experts.orchestrator import ConversationContext, ExpertType  # noqa: E402


def _ctx(*, title: str, intent: str, specific_work: bool, post_type: str) -> ConversationContext:
    ctx = ConversationContext(
        post_id=90010,
        post_data={
            "post_id": 90010,
            "title": title,
            "content_blocks": [{"type": "text", "text": "본문"}],
        },
        comments=[],
    )
    ctx.set_expert_output(
        ExpertType.GATEKEEPER,
        {
            "post_type": post_type,
            "key_terms": ["히집악"],
            "context_clues": {
                "has_episode_reference": post_type == "work_discussion",
            },
        },
    )
    warnings = [] if specific_work else ["semantic_seed_review_specific_work_denied"]
    ctx.set_expert_output(
        ExpertType.DISCOURSE,
        {
            "discourse_analysis": {
                "intent": intent,
                "semantic_seed_review": {"is_specific_work_discussion": specific_work},
                "warnings": warnings,
            }
        },
    )
    if not specific_work:
        ctx.uncertainty_sources.append(
            "intent_permit_for_title_search=false(semantic_seed_review_not_specific_work)"
        )
    return ctx


class DeliberationCuratedAliasGuardTest(unittest.TestCase):
    def test_curated_alias_no_work_context_is_not_positive_signal(self) -> None:
        ctx = _ctx(
            title="히집악 단어만 봄",
            intent="community_banter",
            specific_work=False,
            post_type="community_banter",
        )

        result = EvidenceScorer.compute(ctx)

        positives = {item["signal"] for item in result["positive_signals"]}
        self.assertNotIn("abbreviation_match", positives)
        self.assertTrue(
            any("curated alias hint lacks independent work anchor" in item for item in result["conflict_details"])
        )
        self.assertEqual(EvidenceScorer.build_curated_alias_prompt_note(ctx), "")

    def test_curated_alias_work_context_is_hint_not_strong_proof(self) -> None:
        ctx = _ctx(
            title="히집악 최신화 얘기",
            intent="discuss_work",
            specific_work=True,
            post_type="work_discussion",
        )

        result = EvidenceScorer.compute(ctx)
        note = EvidenceScorer.build_curated_alias_prompt_note(ctx)

        details = [
            item["detail"]
            for item in result["positive_signals"]
            if item["signal"] == "abbreviation_match"
        ]
        self.assertEqual(EvidenceScorer.WEIGHTS["abbreviation_match"], 1.0)
        self.assertTrue(details)
        self.assertIn("hint_with_work_anchor", details[0])
        self.assertIn("단독 확정 근거가 아닙니다", note)
        self.assertNotIn("확정적입니다", note)


if __name__ == "__main__":
    unittest.main()
