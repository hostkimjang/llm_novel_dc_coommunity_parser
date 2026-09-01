from __future__ import annotations

import os
import socket
import sys
import threading
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
                yield 'data: {"model":"Qwen-resolved","choices":[{"delta":{"content":"{\\"ok\\":true}"},"finish_reason":null}]}\n'
                yield 'data: {"model":"Qwen-resolved","usage":{"prompt_tokens":2,"completion_tokens":1,"total_tokens":3},"choices":[{"delta":{},"finish_reason":"stop"}]}\n'
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
        self.assertEqual(client.last_model, "Qwen-resolved")
        self.assertEqual(client.last_usage_provenance, "PROVIDER_REPORTED")
        self.assertEqual(client.last_usage["total_tokens"], 3)

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

    def test_stream_chat_http_whitespace_content_does_not_satisfy_first_token_timeout(self):
        class _WhitespaceFirstStreamResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def raise_for_status(self) -> None:
                return None

            def iter_text(self):
                yield 'data: {"choices":[{"delta":{"content":"   "},"finish_reason":null}]}\n'
                time.sleep(0.02)
                yield 'data: {"choices":[{"delta":{"content":"\\t"},"finish_reason":null}]}\n'

        def _fake_stream(method, url, json=None, timeout=None):
            return _WhitespaceFirstStreamResponse()

        with patch.dict(
            os.environ,
            {
                "LLM_MAX_RETRIES": "1",
                "LLM_RETRY_DELAY": "0",
                "LLM_SUSPEND_ON_SERVER_ANOMALY": "0",
                "LLM_STREAM_FIRST_TOKEN_TIMEOUT_SECONDS": "0.001",
                "LLM_STREAM_IDLE_TIMEOUT_SECONDS": "30",
                "LLM_STREAM_SIGNAL_IDLE_TIMEOUT_SECONDS": "30",
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
                result = client._stream_chat_http([{"role": "user", "content": "ok"}], tag="arbiter")

        self.assertEqual(result, "{}")

    def test_stream_chat_http_signal_idle_timeout_after_whitespace_returns_failure_json(self):
        class _WhitespaceStallStreamResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def raise_for_status(self) -> None:
                return None

            def iter_text(self):
                yield 'data: {"choices":[{"delta":{"content":"{\\"ok\\""},"finish_reason":null}]}\n'
                for _ in range(3):
                    time.sleep(0.006)
                    yield 'data: {"choices":[{"delta":{"content":" "},"finish_reason":null}]}\n'

        def _fake_stream(method, url, json=None, timeout=None):
            return _WhitespaceStallStreamResponse()

        with patch.dict(
            os.environ,
            {
                "LLM_MAX_RETRIES": "1",
                "LLM_RETRY_DELAY": "0",
                "LLM_SUSPEND_ON_SERVER_ANOMALY": "0",
                "LLM_STREAM_FIRST_TOKEN_TIMEOUT_SECONDS": "30",
                "LLM_STREAM_IDLE_TIMEOUT_SECONDS": "30",
                "LLM_STREAM_SIGNAL_IDLE_TIMEOUT_SECONDS": "0.01",
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
                result = client._stream_chat_http([{"role": "user", "content": "ok"}], tag="arbiter")

        self.assertEqual(result, "{}")

    def test_stream_chat_http_signal_idle_after_completed_json_preserves_result(self):
        class _CompletedJsonThenWhitespaceStreamResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def raise_for_status(self) -> None:
                return None

            def iter_text(self):
                yield 'data: {"choices":[{"delta":{"content":"{\\"ok\\":true}"},"finish_reason":null}]}\n'
                for _ in range(3):
                    time.sleep(0.006)
                    yield 'data: {"choices":[{"delta":{"content":" "},"finish_reason":null}]}\n'

        def _fake_stream(method, url, json=None, timeout=None):
            return _CompletedJsonThenWhitespaceStreamResponse()

        with patch.dict(
            os.environ,
            {
                "LLM_MAX_RETRIES": "1",
                "LLM_RETRY_DELAY": "0",
                "LLM_SUSPEND_ON_SERVER_ANOMALY": "0",
                "LLM_STREAM_FIRST_TOKEN_TIMEOUT_SECONDS": "30",
                "LLM_STREAM_IDLE_TIMEOUT_SECONDS": "30",
                "LLM_STREAM_SIGNAL_IDLE_TIMEOUT_SECONDS": "0.01",
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
                result = client._stream_chat_http([{"role": "user", "content": "ok"}], tag="arbiter")

        self.assertEqual(result, '{"ok":true}')

    def test_stream_chat_http_hard_cap_drains_provider_usage_without_changing_result(self):
        class _HardCapThenUsageStreamResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def raise_for_status(self) -> None:
                return None

            def iter_text(self):
                yield 'data: {"model":"Qwen-resolved","choices":[{"delta":{"content":"abcdef"},"finish_reason":null}]}\n'
                yield 'data: {"model":"TAIL-MODEL-MUST-NOT-WIN","choices":[{"delta":{"content":"MUST_NOT_BE_APPENDED"},"finish_reason":"length"}]}\n'
                yield 'data: {"model":"TAIL-MODEL-MUST-NOT-WIN","usage":{"prompt_tokens":7,"completion_tokens":11,"total_tokens":18},"choices":[]}\n'
                yield "data: [DONE]\n"

        def _fake_stream(method, url, json=None, timeout=None):
            return _HardCapThenUsageStreamResponse()

        with patch.dict(
            os.environ,
            {
                "LLM_ACC_HARD_CAP": "5",
                "LLM_DRAIN_USAGE_AFTER_HARD_CAP": "1",
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
                result = client._stream_chat_http([{"role": "user", "content": "ok"}], tag="verifier")

        self.assertEqual(result, "abcdef")
        self.assertNotIn("MUST_NOT_BE_APPENDED", result)
        self.assertEqual(client.last_model, "Qwen-resolved")
        self.assertIsNone(client.last_finish_reason)
        self.assertEqual(client.last_usage_provenance, "PROVIDER_REPORTED")
        self.assertEqual(client.last_usage, {"prompt_tokens": 7, "completion_tokens": 11, "total_tokens": 18})

    def test_stream_chat_http_hard_cap_usage_drain_kill_switch_preserves_fail_close(self):
        consumed = []

        class _HardCapThenUsageStreamResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def raise_for_status(self) -> None:
                return None

            def iter_text(self):
                consumed.append("content")
                yield 'data: {"choices":[{"delta":{"content":"abcdef"},"finish_reason":null}]}\n'
                consumed.append("usage")
                yield 'data: {"usage":{"prompt_tokens":7,"completion_tokens":11,"total_tokens":18},"choices":[]}\n'

        def _fake_stream(method, url, json=None, timeout=None):
            return _HardCapThenUsageStreamResponse()

        with patch.dict(
            os.environ,
            {
                "LLM_ACC_HARD_CAP": "5",
                "LLM_DRAIN_USAGE_AFTER_HARD_CAP": "0",
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
                result = client._stream_chat_http([{"role": "user", "content": "ok"}], tag="verifier")

        self.assertEqual(result, "abcdef")
        # bounded drain iterator는 kill switch에서 다음 청크를 선소비하지 않는다.
        # 의미 결과와 ESTIMATED fail-close 계약은 기존과 동일하다.
        self.assertEqual(consumed, ["content"])
        self.assertEqual(client.last_usage_provenance, "ESTIMATED")

    def test_stream_chat_http_hard_cap_usage_drain_error_does_not_retry_or_change_result(self):
        stream_calls = []

        class _HardCapThenFailureStreamResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def raise_for_status(self) -> None:
                return None

            def iter_text(self):
                yield 'data: {"choices":[{"delta":{"content":"abcdef"},"finish_reason":null}]}\n'
                raise httpx.ReadTimeout("usage tail unavailable")

        def _fake_stream(method, url, json=None, timeout=None):
            stream_calls.append(1)
            return _HardCapThenFailureStreamResponse()

        with patch.dict(
            os.environ,
            {
                "LLM_ACC_HARD_CAP": "5",
                "LLM_DRAIN_USAGE_AFTER_HARD_CAP": "1",
                "LLM_MAX_RETRIES": "3",
                "LLM_RETRY_DELAY": "0",
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
                result = client._stream_chat_http([{"role": "user", "content": "ok"}], tag="synthesizer")

        self.assertEqual(result, "abcdef")
        self.assertEqual(stream_calls, [1])
        self.assertEqual(client.last_usage_provenance, "ESTIMATED")

    def test_stream_chat_http_hard_cap_usage_drain_nontransport_error_fails_closed(self):
        stream_calls = []

        class _HardCapThenInvalidTailStreamResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def raise_for_status(self) -> None:
                return None

            def iter_text(self):
                yield 'data: {"choices":[{"delta":{"content":"abcdef"},"finish_reason":null}]}\n'
                raise ValueError("invalid provider tail")

        def _fake_stream(method, url, json=None, timeout=None):
            stream_calls.append(1)
            return _HardCapThenInvalidTailStreamResponse()

        with patch.dict(
            os.environ,
            {
                "LLM_ACC_HARD_CAP": "5",
                "LLM_DRAIN_USAGE_AFTER_HARD_CAP": "1",
                "LLM_MAX_RETRIES": "3",
                "LLM_RETRY_DELAY": "0",
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
                result = client._stream_chat_http(
                    [{"role": "user", "content": "ok"}], tag="synthesizer"
                )

        self.assertEqual(result, "abcdef")
        self.assertEqual(stream_calls, [1])
        self.assertEqual(client.last_usage_provenance, "ESTIMATED")

    def test_stream_chat_http_hard_cap_waits_for_usage_seen_during_drain(self):
        consumed = []

        class _UsageBeforeCapThenFinalUsageStreamResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def raise_for_status(self) -> None:
                return None

            def iter_text(self):
                consumed.append("content_with_early_usage")
                yield 'data: {"usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2},"choices":[{"delta":{"content":"abcdef"},"finish_reason":null}]}\n'
                consumed.append("tail_without_usage")
                yield 'data: {"choices":[{"delta":{"content":"MUST_NOT_BE_APPENDED"},"finish_reason":null}]}\n'
                consumed.append("final_usage")
                yield 'data: {"usage":{"prompt_tokens":7,"completion_tokens":11,"total_tokens":18},"choices":[]}\n'

        def _fake_stream(method, url, json=None, timeout=None):
            return _UsageBeforeCapThenFinalUsageStreamResponse()

        with patch.dict(
            os.environ,
            {
                "LLM_ACC_HARD_CAP": "5",
                "LLM_DRAIN_USAGE_AFTER_HARD_CAP": "1",
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
                result = client._stream_chat_http(
                    [{"role": "user", "content": "ok"}], tag="verifier"
                )

        self.assertEqual(result, "abcdef")
        self.assertEqual(
            consumed,
            ["content_with_early_usage", "tail_without_usage", "final_usage"],
        )
        self.assertEqual(client.last_usage_provenance, "PROVIDER_REPORTED")
        self.assertEqual(client.last_usage["total_tokens"], 18)

    def test_stream_chat_http_hard_cap_usage_drain_stall_is_bounded_and_not_retried(self):
        stream_calls = []
        exit_threads = []
        reader_socket, peer_socket = socket.socketpair()

        class _FakeNetworkStream:
            def get_extra_info(self, info):
                return reader_socket if info == "socket" else None

        class _HardCapThenStalledStreamResponse:
            extensions = {"network_stream": _FakeNetworkStream()}

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                exit_threads.append(threading.current_thread().name)
                reader_socket.close()
                peer_socket.close()
                return False

            def raise_for_status(self) -> None:
                return None

            def iter_text(self):
                yield 'data: {"choices":[{"delta":{"content":"abcdef"},"finish_reason":null}]}\n'
                reader_socket.recv(1)

        def _fake_stream(method, url, json=None, timeout=None):
            stream_calls.append(1)
            return _HardCapThenStalledStreamResponse()

        with patch.dict(
            os.environ,
            {
                "LLM_ACC_HARD_CAP": "5",
                "LLM_DRAIN_USAGE_AFTER_HARD_CAP": "1",
                "LLM_USAGE_DRAIN_SIGNAL_IDLE_TIMEOUT_SECONDS": "0.02",
                "LLM_USAGE_DRAIN_MAX_SECONDS": "1",
                "LLM_MAX_RETRIES": "3",
                "LLM_RETRY_DELAY": "0",
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
            started = time.monotonic()
            with patch("llm_batch.llm.client.httpx.stream", side_effect=_fake_stream):
                result = client._stream_chat_http(
                    [{"role": "user", "content": "ok"}], tag="synthesizer-stall-test"
                )
            elapsed = time.monotonic() - started

        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline and any(
            thread.name == "llm-usage-drain-synthesizer-stall-test"
            and thread.is_alive()
            for thread in threading.enumerate()
        ):
            time.sleep(0.01)

        self.assertEqual(result, "abcdef")
        self.assertLess(elapsed, 0.5)
        self.assertEqual(stream_calls, [1])
        self.assertEqual(client.last_usage_provenance, "ESTIMATED")
        self.assertEqual(
            exit_threads,
            ["llm-usage-drain-synthesizer-stall-test"],
        )
        self.assertFalse(
            any(
                thread.name == "llm-usage-drain-synthesizer-stall-test"
                and thread.is_alive()
                for thread in threading.enumerate()
            )
        )

    def test_stream_chat_http_hard_cap_usage_drain_absolute_timeout_is_bounded(self):
        stream_calls = []

        class _HardCapThenHeartbeatForeverStreamResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def raise_for_status(self) -> None:
                return None

            def iter_text(self):
                yield 'data: {"choices":[{"delta":{"content":"abcdef"},"finish_reason":null}]}\n'
                while True:
                    time.sleep(0.005)
                    yield ": keepalive\n"

        def _fake_stream(method, url, json=None, timeout=None):
            stream_calls.append(1)
            return _HardCapThenHeartbeatForeverStreamResponse()

        with patch.dict(
            os.environ,
            {
                "LLM_ACC_HARD_CAP": "5",
                "LLM_DRAIN_USAGE_AFTER_HARD_CAP": "1",
                "LLM_USAGE_DRAIN_SIGNAL_IDLE_TIMEOUT_SECONDS": "1",
                "LLM_USAGE_DRAIN_MAX_SECONDS": "0.03",
                "LLM_MAX_RETRIES": "3",
                "LLM_RETRY_DELAY": "0",
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
            started = time.monotonic()
            with patch("llm_batch.llm.client.httpx.stream", side_effect=_fake_stream):
                result = client._stream_chat_http(
                    [{"role": "user", "content": "ok"}], tag="synthesizer"
                )
            elapsed = time.monotonic() - started

        self.assertEqual(result, "abcdef")
        self.assertLess(elapsed, 0.5)
        self.assertEqual(stream_calls, [1])
        self.assertEqual(client.last_usage_provenance, "ESTIMATED")

    def test_stream_chat_http_json_repeat_drains_usage_and_finish_reason_without_mutating_text(self):
        stream_calls = []

        class _JsonRepeatThenUsageStreamResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def raise_for_status(self) -> None:
                return None

            def iter_text(self):
                yield 'data: {"model":"Qwen-resolved","choices":[{"delta":{"content":"{\\"ok\\":true}{\\"repeat\\":true}"},"finish_reason":null}]}\n'
                yield 'data: {"model":"TAIL-MODEL-MUST-NOT-WIN","usage":{"prompt_tokens":7,"completion_tokens":11,"total_tokens":18},"choices":[{"delta":{"content":"MUST_NOT_BE_APPENDED"},"finish_reason":"stop"}]}\n'
                yield "data: [DONE]\n"

        def _fake_stream(method, url, json=None, timeout=None):
            stream_calls.append(1)
            return _JsonRepeatThenUsageStreamResponse()

        with patch.dict(
            os.environ,
            {"LLM_DRAIN_USAGE_AFTER_EARLY_STOP": "1"},
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
                result = client._stream_chat_http(
                    [{"role": "user", "content": "ok"}], tag="synthesizer"
                )

        self.assertEqual(result, '{"ok":true}')
        self.assertNotIn("MUST_NOT_BE_APPENDED", result)
        self.assertEqual(stream_calls, [1])
        self.assertEqual(client.last_model, "Qwen-resolved")
        self.assertEqual(client.last_finish_reason, "stop")
        self.assertEqual(client.last_usage_provenance, "PROVIDER_REPORTED")
        self.assertEqual(client.last_usage["total_tokens"], 18)

    def test_stream_chat_http_json_repeat_usage_drain_kill_switch_does_not_consume_tail(self):
        consumed = []

        class _JsonRepeatThenUsageStreamResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def raise_for_status(self) -> None:
                return None

            def iter_text(self):
                consumed.append("repeat")
                yield 'data: {"choices":[{"delta":{"content":"{\\"ok\\":true}{\\"repeat\\":true}"},"finish_reason":null}]}\n'
                consumed.append("tail_usage")
                yield 'data: {"usage":{"prompt_tokens":7,"completion_tokens":11,"total_tokens":18},"choices":[{"delta":{},"finish_reason":"stop"}]}\n'

        def _fake_stream(method, url, json=None, timeout=None):
            return _JsonRepeatThenUsageStreamResponse()

        with patch.dict(
            os.environ,
            {"LLM_DRAIN_USAGE_AFTER_EARLY_STOP": "0"},
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
                result = client._stream_chat_http(
                    [{"role": "user", "content": "ok"}], tag="synthesizer"
                )

        self.assertEqual(result, '{"ok":true}')
        self.assertEqual(consumed, ["repeat"])
        self.assertEqual(client.last_usage_provenance, "ESTIMATED")
        self.assertIsNone(client.last_finish_reason)

    def test_stream_chat_http_json_repeat_usage_drain_error_preserves_estimate_without_retry(self):
        stream_calls = []

        class _JsonRepeatThenFailureStreamResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def raise_for_status(self) -> None:
                return None

            def iter_text(self):
                yield 'data: {"choices":[{"delta":{"content":"{\\"ok\\":true}{\\"repeat\\":true}"},"finish_reason":null}]}\n'
                raise httpx.ReadTimeout("usage tail unavailable")

        def _fake_stream(method, url, json=None, timeout=None):
            stream_calls.append(1)
            return _JsonRepeatThenFailureStreamResponse()

        with patch.dict(
            os.environ,
            {
                "LLM_DRAIN_USAGE_AFTER_EARLY_STOP": "1",
                "LLM_MAX_RETRIES": "3",
                "LLM_RETRY_DELAY": "0",
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
                result = client._stream_chat_http(
                    [{"role": "user", "content": "ok"}], tag="synthesizer"
                )

        self.assertEqual(result, '{"ok":true}')
        self.assertEqual(stream_calls, [1])
        self.assertEqual(client.last_usage_provenance, "ESTIMATED")


if __name__ == "__main__":
    unittest.main()
