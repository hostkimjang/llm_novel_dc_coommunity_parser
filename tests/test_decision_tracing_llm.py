from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import httpx

from src.llm_batch.ledger.decision_call_events import DecisionCallLedgerRegistry
from src.llm_batch.ledger.decision_tracing_llm import DecisionTracingLLMClient
from src.llm_batch.llm.client import LLMClient, retry_with_backoff
from src.llm_batch.ledger.publication_commit import build_publication_scope_descriptor


class _Response:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self.data


class DecisionTracingLLMClientTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        scope = build_publication_scope_descriptor(
            input_file_sha256="1" * 64,
            post_ids=[101],
            config_hash="decision-tracing-tests",
            release_fingerprint="2" * 64,
        )
        self.registry = DecisionCallLedgerRegistry(
            self.root / "ledger", scope_descriptor=scope, create_new=True, enabled=True,
            run_spec_sha256="3" * 64, pair_id="pair", arm="AFTER", fresh_execution_mode=True,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def client(self, **kwargs):
        client = DecisionTracingLLMClient(
            decision_call_ledger=self.registry, backend="http", endpoint="http://provider",
            model="requested", stream=False, server_type="vllm", **kwargs,
        )
        client.max_retries = 2
        client.retry_base_delay = 0
        client.begin_row_attempt("run", "row-1", 1, 101)
        return client

    def frames(self):
        return self.registry.readback()["frames"]

    def test_retry_failure_then_success_is_two_physical_calls(self):
        client = self.client()
        calls = [httpx.ConnectError("secret transport detail"), _Response({
            "model": "resolved", "usage": {
                "prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 9,
            }, "choices": [{"message": {"content": '{"ok":true}'}}],
        })]

        def post(*args, **kwargs):
            value = calls.pop(0)
            if isinstance(value, Exception):
                raise value
            return value

        with mock.patch("src.llm_batch.llm.client.httpx.post", side_effect=post):
            self.assertEqual(client._stream_chat_http(
                [{"role": "user", "content": "raw prompt secret"}], tag="gatekeeper"
            ), '{"ok":true}')
        client.seal_row_attempt()
        payloads = [f["payload"] for f in self.frames() if f["frame_kind"] == "TERMINAL"]
        self.assertEqual([p["terminal_status"] for p in sorted(payloads, key=lambda p: p["retry_ordinal"])],
                         ["FAILED", "SUCCEEDED"])
        second = max(payloads, key=lambda p: p["retry_ordinal"])
        self.assertEqual(second["usage_provenance"], "PROVIDER_REPORTED")
        self.assertEqual(second["total_tokens"], 9)

    def test_final_fallback_has_two_failed_calls_and_no_fake_success(self):
        client = self.client()
        with mock.patch("src.llm_batch.llm.client.httpx.post", side_effect=httpx.ConnectError("down")):
            self.assertEqual(client._stream_chat_http([], tag="decoder"), "{}")
        client.seal_row_attempt()
        terminals = [f["payload"] for f in self.frames() if f["frame_kind"] == "TERMINAL"]
        self.assertEqual(len(terminals), 2)
        self.assertEqual({p["terminal_status"] for p in terminals}, {"FAILED"})

    def test_unsupported_vlm_records_zero_calls(self):
        client = self.client()
        client.server_type = "llama"
        self.assertEqual(client.complete_multimodal_json("s", "u", []), {})
        client.seal_row_attempt()
        self.assertFalse(any(f["frame_kind"] == "DISPATCH_INTENT" for f in self.frames()))

    def test_thread_pool_calls_share_instance_row(self):
        client = self.client()
        with mock.patch.object(LLMClient, "_stream_chat_http", return_value="{}"):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(
                    lambda tag: client._stream_chat_http([], tag=tag),
                    ["critic", "synthesizer"],
                ))
        self.assertEqual(results, ["{}", "{}"])
        client.seal_row_attempt()
        dispatches = [f for f in self.frames() if f["frame_kind"] == "DISPATCH_INTENT"]
        self.assertEqual(len(dispatches), 2)
        self.assertEqual({f["row"]["row_attempt_id"] for f in dispatches}, {"row-1"})

    def test_raw_content_and_error_message_are_not_persisted(self):
        client = self.client()
        secret = "DO-NOT-PERSIST-RAW-CONTENT"
        with mock.patch("src.llm_batch.llm.client.httpx.post", side_effect=httpx.ConnectError(secret)):
            client._stream_chat_http([{"role": "user", "content": secret}], tag="verifier")
        client.seal_row_attempt()
        on_disk = "\n".join(path.read_text("utf-8") for path in (self.root / "ledger").rglob("*.json"))
        self.assertNotIn(secret, on_disk)

    def test_ledger_write_failure_does_not_change_result_and_aborts(self):
        client = self.client()
        with mock.patch.object(LLMClient, "_stream_chat_http", return_value='{"kept":true}'), \
             mock.patch.object(self.registry, "record_dispatch_intent", side_effect=OSError("ledger down")):
            result = client._stream_chat_http([], tag="arbiter")
        self.assertEqual(result, '{"kept":true}')
        self.assertTrue(client.trace_errors)
        client.seal_row_attempt()
        summary = self.registry.summary()
        self.assertEqual(summary["actual_kpi_status"], "NOT_ESTIMABLE")
        self.assertEqual(summary["aborted_row_attempt_count"], 1)

    def test_seal_and_publication_link_roundtrip_keeps_pending_readback(self):
        client = self.client()
        def completed(*args, **kwargs):
            client.last_usage = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
            client.last_usage_provenance = "PROVIDER_REPORTED"
            client.last_model = "resolved"
            return '{"ok":true}'

        with mock.patch.object(LLMClient, "_stream_chat_http", side_effect=completed):
            client._stream_chat_http([], tag="arbiter_jury_round_1")
        client.seal_row_attempt()
        client.link_row_publication({"receipt": "opaque"}, "d" * 64)
        summary = self.registry.summary()
        self.assertEqual(summary["linked_row_attempt_count"], 1)
        self.assertEqual(summary["actual_kpi_status"], "PENDING_INDEPENDENT_READBACK")
        dispatch = next(f for f in self.frames() if f["frame_kind"] == "DISPATCH_INTENT")
        self.assertEqual(dispatch["payload"]["stage"], "DELIBERATION")

    def test_estimated_usage_is_not_laundered_as_provider_reported(self):
        client = self.client()

        def completed(*args, **kwargs):
            client.last_usage = {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4}
            client.last_usage_provenance = "ESTIMATED"
            client.last_model = "resolved"
            return '{"ok":true}'

        with mock.patch.object(LLMClient, "_stream_chat_http", side_effect=completed):
            client._stream_chat_http([], tag="snippet_analyzer")
        client.seal_row_attempt()
        terminal = next(f for f in self.frames() if f["frame_kind"] == "TERMINAL")
        self.assertEqual(terminal["payload"]["usage_provenance"], "ESTIMATED")
        self.assertIn("USAGE_ESTIMATED", self.registry.summary()["reason_codes"])

    def test_known_dynamic_tags_and_row_error_reset(self):
        client = self.client()
        for tag, expected in (
            ("debate_advocate", "DELIBERATION"),
            ("snippet_analyzer", "SNIPPET_ANALYZER"),
            ("page_analyzer", "PAGE_ANALYZER"),
        ):
            self.assertEqual(client._normalize_stage(tag, "TEXT"), (expected, True))

        with mock.patch.object(LLMClient, "_stream_chat_http", return_value="{}"):
            client._stream_chat_http([], tag="unknown_stage")
        client.seal_row_attempt()
        self.assertTrue(client.trace_errors)
        client.begin_row_attempt("run-2", "row-2", 1, 101)
        self.assertFalse(client.trace_errors)

    def test_two_retry_operations_each_start_a_distinct_logical_call(self):
        client = self.client()

        def second_success():
            client.last_usage = {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3}
            client.last_usage_provenance = "PROVIDER_REPORTED"
            client.last_model = "resolved"
            return "ok"

        def invoke():
            retry_with_backoff(
                lambda: (_ for _ in ()).throw(ConnectionError("first operation")),
                max_retries=1,
                base_delay=0,
                on_failure=lambda _error: None,
            )
            return retry_with_backoff(second_success, max_retries=1, base_delay=0)

        value = client._trace_call(
            stage_tag="decoder",
            modality="TEXT",
            request_value={"safe": True},
            invoke=invoke,
        )
        self.assertEqual(value, "ok")
        client.seal_row_attempt()
        dispatches = [
            f["payload"] for f in self.frames() if f["frame_kind"] == "DISPATCH_INTENT"
        ]
        self.assertEqual([item["retry_ordinal"] for item in dispatches], [0, 0])
        self.assertEqual(len({item["logical_call_id"] for item in dispatches}), 2)
        self.assertTrue(all(item["retry_of_call_id"] is None for item in dispatches))

    def test_unhashable_request_does_not_change_provider_result_and_aborts_measurement(self):
        client = self.client()
        marker = object()
        value = client._trace_call(
            stage_tag="decoder",
            modality="TEXT",
            request_value={"unsupported": marker},
            invoke=lambda: "provider-result-preserved",
        )
        self.assertEqual(value, "provider-result-preserved")
        client.seal_row_attempt()
        self.assertTrue(any(item["operation"] == "REQUEST_HASH" for item in client.trace_errors))
        self.assertEqual(self.registry.summary()["aborted_row_attempt_count"], 1)

    def test_direct_local_style_call_does_not_inherit_stale_usage(self):
        client = self.client()
        client.last_usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        client.last_usage_provenance = "PROVIDER_REPORTED"
        client.last_model = "stale-model"
        with mock.patch.object(LLMClient, "_stream_chat_http", return_value="{}"):
            client._stream_chat_http([], tag="critic")
        client.seal_row_attempt()
        terminal = next(f for f in self.frames() if f["frame_kind"] == "TERMINAL")
        self.assertEqual(terminal["payload"]["usage_provenance"], "UNAVAILABLE")
        self.assertIsNone(terminal["payload"]["resolved_model"])


if __name__ == "__main__":
    unittest.main()
