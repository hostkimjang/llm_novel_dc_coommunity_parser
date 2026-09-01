import unittest

from src.llm_batch.agentic_pipeline import AgenticPipeline


class AgenticPipelineVerifierShapeGuardTest(unittest.TestCase):
    def test_valid_mapping_is_preserved(self):
        payload = {"decoded_term": "정식 제목"}

        normalized = AgenticPipeline._verifier_mapping(payload)

        self.assertIs(normalized, payload)

    def test_list_payload_fails_closed_to_empty_mapping(self):
        self.assertEqual(
            AgenticPipeline._verifier_mapping([{"decoded_term": "오염 후보"}]),
            {},
        )

    def test_none_and_scalar_payloads_fail_closed(self):
        for value in (None, "decoded", 1, True):
            with self.subTest(value=value):
                self.assertEqual(AgenticPipeline._verifier_mapping(value), {})


if __name__ == "__main__":
    unittest.main()
