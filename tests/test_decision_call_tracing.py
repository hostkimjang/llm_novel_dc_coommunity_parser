from __future__ import annotations

from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

from src.llm_batch.decision_call_events import DecisionCallLedgerRegistry
from src.llm_batch.decision_tracing_llm import DecisionTracingLLMClient
from src.llm_batch.llm.client import LLMClient, retry_with_backoff
from src.llm_batch.publication_commit import build_publication_scope_descriptor


def _scope():
    return build_publication_scope_descriptor(
        input_file_sha256="1" * 64,
        post_ids=[101],
        config_hash="decision-trace-adversarial-tests",
        release_fingerprint="2" * 64,
    )


class DecisionTracingAdversarialTest(unittest.TestCase):
    def _client(self, root: Path) -> tuple[DecisionTracingLLMClient, DecisionCallLedgerRegistry]:
        ledger = DecisionCallLedgerRegistry(
            root / "ledger",
            scope_descriptor=_scope(),
            create_new=True,
            enabled=True,
            run_spec_sha256="3" * 64,
            pair_id="pair-1",
            arm="BEFORE",
            fresh_execution_mode=True,
        )
        client = DecisionTracingLLMClient(
            decision_call_ledger=ledger,
            backend="http",
            endpoint="http://provider",
            model="requested-model",
            stream=False,
            server_type="vllm",
        )
        client.begin_row_attempt("run-a", "row-a", 1, 101)
        return client, ledger

    def test_empty_success_fallback_is_failed_and_not_sealable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client, ledger = self._client(Path(directory))

            def fallback(*_args, **_kwargs):
                client.last_usage = {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                }
                client.last_usage_provenance = "PROVIDER_REPORTED"
                return {}

            with mock.patch.object(LLMClient, "_stream_chat_http", side_effect=fallback):
                self.assertEqual(client._stream_chat_http([], tag="gatekeeper"), {})

            closed, created = client.seal_row_attempt()
            self.assertTrue(created)
            self.assertEqual(closed["frame_kind"], "ROW_ABORT")
            frames = ledger.readback()["frames"]
            self.assertEqual(
                [frame["payload"].get("terminal_status") for frame in frames if frame["frame_kind"] == "TERMINAL"],
                ["FAILED"],
            )

    def test_reason_review_known_nonempty_fallback_is_failed_and_not_sealable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client, ledger = self._client(Path(directory))
            fallback = {
                "selected_ids": [],
                "primary_reason": "",
                "merged_reason": "",
                "llm_review_note": "LLM reason review 실패",
                "review_confidence": "Low",
            }

            def malformed_success(*_args, **_kwargs):
                client.last_usage = {
                    "prompt_tokens": 2,
                    "completion_tokens": 1,
                    "total_tokens": 3,
                }
                client.last_usage_provenance = "PROVIDER_REPORTED"
                client.last_model = "resolved-model"
                return dict(fallback)

            with mock.patch.object(
                LLMClient,
                "review_reason_candidates",
                side_effect=malformed_success,
            ):
                self.assertEqual(client.review_reason_candidates({"rows": []}), fallback)

            closed, created = client.seal_row_attempt()
            self.assertTrue(created)
            self.assertEqual(closed["frame_kind"], "ROW_ABORT")
            terminals = [
                frame["payload"]
                for frame in ledger.readback()["frames"]
                if frame["frame_kind"] == "TERMINAL"
            ]
            self.assertEqual([item["terminal_status"] for item in terminals], ["FAILED"])
            self.assertEqual(terminals[0]["error_type"], "InvalidProviderResponse")

    def test_second_retry_operation_resets_ordinal_without_breaking_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client, ledger = self._client(Path(directory))

            def provider(*_args, **_kwargs):
                def first():
                    client.last_usage = {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3}
                    client.last_usage_provenance = "PROVIDER_REPORTED"
                    return "first"

                def second():
                    client.last_usage = {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3}
                    client.last_usage_provenance = "PROVIDER_REPORTED"
                    return "second"

                return retry_with_backoff(first, max_retries=1, base_delay=0) + retry_with_backoff(
                    second, max_retries=1, base_delay=0
                )

            with mock.patch.object(LLMClient, "_stream_chat_http", side_effect=provider):
                self.assertEqual(client._stream_chat_http([], tag="gatekeeper"), "firstsecond")

            dispatches = [
                frame for frame in ledger.readback()["frames"] if frame["frame_kind"] == "DISPATCH_INTENT"
            ]
            self.assertEqual([frame["payload"]["retry_ordinal"] for frame in dispatches], [0, 0])
            self.assertEqual(
                len({frame["payload"]["logical_call_id"] for frame in dispatches}),
                2,
            )
            seal, _ = client.seal_row_attempt()
            self.assertEqual(seal["payload"]["expert_calls"], 2)

    def test_seal_during_provider_invoke_aborts_without_late_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client, ledger = self._client(Path(directory))
            entered = threading.Event()
            release = threading.Event()

            def slow_provider(*_args, **_kwargs):
                entered.set()
                release.wait(timeout=3)
                client.last_usage = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
                client.last_usage_provenance = "PROVIDER_REPORTED"
                return "late"

            outputs: list[str] = []
            with mock.patch.object(LLMClient, "_stream_chat_http", side_effect=slow_provider):
                worker = threading.Thread(
                    target=lambda: outputs.append(client._stream_chat_http([], tag="gatekeeper"))
                )
                worker.start()
                self.assertTrue(entered.wait(timeout=3))
                closed, _ = client.seal_row_attempt()
                release.set()
                worker.join(timeout=3)

            self.assertEqual(closed["frame_kind"], "ROW_ABORT")
            self.assertEqual(outputs, ["late"])
            frames = ledger.readback()["frames"]
            self.assertFalse(any(frame["frame_kind"] == "TERMINAL" for frame in frames))


if __name__ == "__main__":
    unittest.main()
