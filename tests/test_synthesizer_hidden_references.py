import contextlib
import io
import unittest

from src.llm_batch.experts.synthesizer import SynthesizerExpert


class _DummyContext:
    post_id = 11713200
    post_data = {
        "title": "후회프듀 셍피루상 걍 쉬운 남잔듯",
        "content_blocks": ["신아름이던가 세이코던가"],
    }
    comments = []
    search_results = []
    primary_domain = None
    verified_character_work_links = []
    snippet_hints = {}

    def get_expert_output(self, _expert_type):
        return {}


class SynthesizerHiddenReferencesTest(unittest.TestCase):
    def test_analyze_ignores_non_dict_hidden_reference_items(self):
        expert = SynthesizerExpert(llm_client=None)

        def fake_call_llm(_prompt):
            return {
                "synthesis_summary": "작품 약칭과 캐릭터명을 함께 해석했다.",
                "confidence_assessment": {
                    "is_about_identified_work": True,
                    "confidence": "high",
                },
                "evidence_alignment": {"overall_coherence": "high"},
                "hidden_references": [
                    11713200,
                    {
                        "reference_type": "alias",
                        "text": "후회프듀",
                        "matched_to": "100일 뒤에 먹히는 프로듀서",
                    },
                ],
            }

        expert._call_llm = fake_call_llm
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr):
            result = expert.analyze(_DummyContext())

        self.assertNotIn("error", result)
        self.assertIn("elapsed", result)
        self.assertIn("숨은 참조 1개", stderr.getvalue())
        self.assertIn("후회프듀", stderr.getvalue())

    def test_summarize_for_arbiter_ignores_non_dict_hidden_reference_items(self):
        summary = SynthesizerExpert.summarize_for_arbiter(
            {
                "synthesis_summary": "요약",
                "hidden_references": [
                    11713200,
                    {
                        "reference_type": "alias",
                        "text": "후회프듀",
                        "matched_to": "100일 뒤에 먹히는 프로듀서",
                    },
                ],
            }
        )

        self.assertIn("숨은 참조 1개", summary)
        self.assertIn("후회프듀", summary)
        self.assertNotIn("11713200", summary)


if __name__ == "__main__":
    unittest.main()
