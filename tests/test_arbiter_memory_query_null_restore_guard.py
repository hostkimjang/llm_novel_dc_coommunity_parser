from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_batch.experts.arbiter import ArbiterExpert  # noqa: E402
from llm_batch.experts.orchestrator import ConversationContext, ExpertType  # noqa: E402


class JsonLLM:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def _stream_chat_http(self, **_: object) -> str:
        return json.dumps(self.payload, ensure_ascii=False)


class ArbiterMemoryQueryNullRestoreGuardTest(unittest.TestCase):
    def test_memory_query_guard_runs_before_verifier_null_restore(self) -> None:
        title = "너에겐 푸름"
        arbiter = ArbiterExpert(
            JsonLLM(
                {
                    "final_decision": {
                        "is_relevant": True,
                        "is_novel_discussion": True,
                        "official_title": None,
                        "official_novel_title": None,
                        "heretic_url": None,
                        "confidence": "Low",
                        "discussion_type": "undecodable_reference",
                        "reason": "대사 기억 회수 글이라 특정 작품 확정은 보류.",
                        "final_reasoning": "대사 기억 회수 글이라 특정 작품 확정은 보류.",
                    },
                    "metadata": {},
                    "evidence_chain": [],
                }
            )
        )
        ctx = ConversationContext(
            post_id=11718083,
            post_data={
                "post_id": 11718083,
                "title": "너에겐 네가 위기에 처했을때",
                "content_blocks": [
                    {"type": "text", "text": "옛날에 무슨 소설에서 본 대사였는데 기억이 안남"},
                    {"type": "text", "text": "친구 3명이 구해주는 장면이었는데 뭐였지"},
                ],
            },
            comments=[],
        )
        ctx.search_budget_profile = "memory_query_lookup"
        ctx.add_evidence_for_candidate(title, "official_url", "https://novelpia.com/novel/342156")
        ctx.set_expert_output(
            ExpertType.VERIFIER,
            {
                "verification_result": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_novel_title": title,
                        "official_title": title,
                        "confidence": "High",
                        "heretic_url": "https://novelpia.com/novel/342156",
                    },
                    "grounding_check": {
                        "anchor_found": "plot_mention",
                        "anchor_text": "친구 3명이 구해주는 장면",
                    },
                    "relation_judgment": {
                        "promotion_decision": "hold",
                        "post_direct_grounding": False,
                        "relation_type": "thematic_overlap_only",
                        "reason": "후보 작품과 직접 연결된다는 명시적 브리지 증거가 부족합니다.",
                        "search_support_summary": {
                            "bridge_quality": "supporting",
                            "explicit_alias_bridge_count": 0,
                            "closed_bridge": False,
                            "converged_official_signal": False,
                        },
                    },
                    "counter_arguments": [
                        {"severity": "major", "action": "downgrade_confidence"}
                    ],
                }
            },
        )

        result = arbiter.analyze(ctx)
        decision = result["final_decision"]

        self.assertIsNone(decision.get("official_title"))
        self.assertIsNone(decision.get("official_novel_title"))
        self.assertIsNone(decision.get("heretic_url"))
        self.assertTrue(decision.get("_title_deliberately_null"))
        self.assertIn(
            "memory_query_forced_upgrade_guard",
            decision.get("_title_null_block_reasons") or [],
        )


if __name__ == "__main__":
    unittest.main()
