import contextlib
import io
import os
import unittest

from src.llm_batch.experts.synthesizer import SynthesizerExpert


class _FakeLLM:
    def __init__(
        self,
        *,
        provenance="PROVIDER_REPORTED",
        finish_reason="stop",
        backend="http",
        stream=True,
        max_tokens=65536,
    ):
        self.provenance = provenance
        self.finish_reason = finish_reason
        self.backend = backend
        self.stream = stream
        self.max_tokens = max_tokens
        self.last_usage_provenance = "STALE"
        self.last_finish_reason = "STALE"
        self.call_kwargs = None

    def _stream_chat_http(self, **kwargs):
        self.call_kwargs = kwargs
        self.last_usage_provenance = self.provenance
        self.last_finish_reason = self.finish_reason
        return '{"synthesis_summary":"정상 요약"}'


class _DummyContext:
    post_id = 1
    post_data = {"title": "테스트", "content_blocks": ["본문"]}
    comments = []
    search_results = []
    primary_domain = None
    verified_character_work_links = []
    snippet_hints = {}

    def get_expert_output(self, _expert_type):
        return {}


class SynthesizerHardcapQuarantineTest(unittest.TestCase):
    _ENV_KEYS = (
        "LLM_SYNTHESIZER_MAX_TOKENS",
        "LLM_SYNTHESIZER_REQUIRE_TRUSTED_TERMINAL",
        "LLM_EXPERT_MAX_TOKENS",
        "LLM_MAX_TOKENS",
    )

    def _clean_env(self):
        original = {key: os.environ.get(key) for key in self._ENV_KEYS}
        for key in self._ENV_KEYS:
            os.environ.pop(key, None)

        def restore():
            for key in self._ENV_KEYS:
                os.environ.pop(key, None)
            for key, value in original.items():
                if value is not None:
                    os.environ[key] = value

        self.addCleanup(restore)

    def _call_quietly(self, expert):
        with contextlib.redirect_stderr(io.StringIO()):
            return expert._call_llm("테스트")

    def test_default_stage_cap_is_2048(self):
        self._clean_env()
        llm = _FakeLLM(max_tokens=65536)

        result = self._call_quietly(SynthesizerExpert(llm))

        self.assertEqual(result["synthesis_summary"], "정상 요약")
        self.assertEqual(llm.call_kwargs["max_tokens"], 2048)

    def test_stage_cap_respects_global_and_client_caps_without_floor_raise(self):
        self._clean_env()
        os.environ["LLM_SYNTHESIZER_MAX_TOKENS"] = "4096"
        os.environ["LLM_EXPERT_MAX_TOKENS"] = "3000"
        llm = _FakeLLM(max_tokens=2500)

        self._call_quietly(SynthesizerExpert(llm))
        self.assertEqual(llm.call_kwargs["max_tokens"], 2500)

        os.environ["LLM_EXPERT_MAX_TOKENS"] = "128"
        self._call_quietly(SynthesizerExpert(llm))
        self.assertEqual(llm.call_kwargs["max_tokens"], 128)

    def test_parseable_estimated_stream_is_quarantined(self):
        self._clean_env()
        llm = _FakeLLM(provenance="ESTIMATED", finish_reason=None)

        result = self._call_quietly(SynthesizerExpert(llm))

        self.assertIsNone(result)

    def test_parseable_unavailable_stream_is_quarantined(self):
        self._clean_env()
        llm = _FakeLLM(provenance="UNAVAILABLE", finish_reason="stop")

        result = self._call_quietly(SynthesizerExpert(llm))

        self.assertIsNone(result)

    def test_parseable_length_terminal_is_quarantined(self):
        self._clean_env()
        llm = _FakeLLM(provenance="PROVIDER_REPORTED", finish_reason="length")

        result = self._call_quietly(SynthesizerExpert(llm))

        self.assertIsNone(result)

    def test_parseable_max_tokens_terminal_is_quarantined(self):
        self._clean_env()
        llm = _FakeLLM(
            provenance="PROVIDER_REPORTED",
            finish_reason="max_tokens",
        )

        result = self._call_quietly(SynthesizerExpert(llm))

        self.assertIsNone(result)

    def test_provider_terminal_metadata_is_normalized(self):
        self._clean_env()
        llm = _FakeLLM(
            provenance=" provider_reported ",
            finish_reason=" STOP ",
        )

        result = self._call_quietly(SynthesizerExpert(llm))

        self.assertEqual(result["synthesis_summary"], "정상 요약")

    def test_http_stream_requires_explicit_stop_terminal(self):
        self._clean_env()
        llm = _FakeLLM(provenance="PROVIDER_REPORTED", finish_reason=None)

        result = self._call_quietly(SynthesizerExpert(llm))

        self.assertIsNone(result)

    def test_rollback_switch_restores_parseable_truncated_result(self):
        self._clean_env()
        os.environ["LLM_SYNTHESIZER_REQUIRE_TRUSTED_TERMINAL"] = "0"
        llm = _FakeLLM(provenance="ESTIMATED", finish_reason=None)

        result = self._call_quietly(SynthesizerExpert(llm))

        self.assertEqual(result["synthesis_summary"], "정상 요약")

    def test_local_missing_terminal_metadata_keeps_legacy_behavior(self):
        self._clean_env()
        llm = _FakeLLM(
            provenance=None,
            finish_reason=None,
            backend="local",
            stream=True,
        )

        result = self._call_quietly(SynthesizerExpert(llm))

        self.assertEqual(result["synthesis_summary"], "정상 요약")

    def test_http_nonstream_provider_result_keeps_legacy_behavior(self):
        self._clean_env()
        llm = _FakeLLM(
            provenance="PROVIDER_REPORTED",
            finish_reason=None,
            backend="http",
            stream=False,
        )

        result = self._call_quietly(SynthesizerExpert(llm))

        self.assertEqual(result["synthesis_summary"], "정상 요약")

    def test_quarantined_result_does_not_reach_arbiter_summary(self):
        self._clean_env()
        llm = _FakeLLM(provenance="ESTIMATED", finish_reason=None)
        expert = SynthesizerExpert(llm)

        with contextlib.redirect_stderr(io.StringIO()):
            result = expert.analyze(_DummyContext())

        self.assertIn("error", result)
        self.assertEqual(SynthesizerExpert.summarize_for_arbiter(result), "")

    def test_stale_metadata_is_cleared_before_call(self):
        self._clean_env()

        class _NoMetadataLLM(_FakeLLM):
            def _stream_chat_http(self, **kwargs):
                self.call_kwargs = kwargs
                return '{"synthesis_summary":"파싱 가능"}'

        llm = _NoMetadataLLM()

        result = self._call_quietly(SynthesizerExpert(llm))

        self.assertIsNone(result)
        self.assertIsNone(llm.last_usage_provenance)
        self.assertIsNone(llm.last_finish_reason)


if __name__ == "__main__":
    unittest.main()
