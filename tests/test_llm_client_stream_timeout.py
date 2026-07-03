from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_batch.llm.client import LLMClient, _reset_llm_server_suspend_controller_for_tests  # noqa: E402


class LLMClientStreamTimeoutTest(unittest.TestCase):
    def setUp(self) -> None:
        _reset_llm_server_suspend_controller_for_tests()

    def tearDown(self) -> None:
        _reset_llm_server_suspend_controller_for_tests()

    def test_stream_chat_http_uses_first_token_timeout_for_stream_read(self):
        class _FakeStreamResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def raise_for_status(self) -> None:
                return None

            def iter_text(self):
                yield 'data: {"choices":[{"delta":{"content":"{\\"ok\\":true}"},"finish_reason":null}]}\n'
                yield 'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n'
                yield "data: [DONE]\n"

        seen = {}

        def _fake_stream(method, url, json=None, timeout=None):
            seen["method"] = method
            seen["url"] = url
            seen["timeout"] = timeout
            return _FakeStreamResponse()

        with patch.dict(
            os.environ,
            {
                "LLM_TIMEOUT": "99",
                "LLM_STREAM_FIRST_TOKEN_TIMEOUT_SECONDS": "7",
                "LLM_STREAM_IDLE_TIMEOUT_SECONDS": "11",
            },
            clear=False,
        ):
            client = LLMClient(
                backend="http",
                endpoint="http://llm.test",
                model="Qwen",
                server_type="vllm",
                stream=True,
            )
            with patch("llm_batch.llm.client.httpx.stream", side_effect=_fake_stream):
                result = client._stream_chat_http([{"role": "user", "content": "ok"}], tag="gatekeeper")

        self.assertEqual(result, '{"ok":true}')
        self.assertIsInstance(seen["timeout"], httpx.Timeout)
        self.assertEqual(seen["timeout"].read, 7.0)
        self.assertEqual(seen["timeout"].connect, 99.0)

    def test_stream_chat_http_first_token_timeout_returns_failure_json(self):
        class _SlowHeartbeatStreamResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def raise_for_status(self) -> None:
                return None

            def iter_text(self):
                yield ": keepalive\n"
                time.sleep(0.02)
                yield 'data: {"choices":[{"delta":{"content":"{\\"ok\\":true}"},"finish_reason":"stop"}]}\n'

        def _fake_stream(method, url, json=None, timeout=None):
            return _SlowHeartbeatStreamResponse()

        with patch.dict(
            os.environ,
            {
                "LLM_MAX_RETRIES": "1",
                "LLM_SUSPEND_ON_SERVER_ANOMALY": "0",
                "LLM_STREAM_FIRST_TOKEN_TIMEOUT_SECONDS": "0.001",
            },
            clear=False,
        ):
            client = LLMClient(
                backend="http",
                endpoint="http://llm.test",
                model="Qwen",
                server_type="vllm",
                stream=True,
            )
            with patch("llm_batch.llm.client.httpx.stream", side_effect=_fake_stream):
                result = client._stream_chat_http([{"role": "user", "content": "ok"}], tag="gatekeeper")

        self.assertEqual(result, "{}")


if __name__ == "__main__":
    unittest.main()
