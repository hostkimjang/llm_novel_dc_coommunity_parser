from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from src.llm_batch.ledger.decision_call_events import DecisionCallLedgerRegistry
from src.llm_batch.ledger.decision_tracing_llm import DecisionTracingLLMClient
from src.llm_batch.llm.client import LLMClient
from src.llm_batch.ledger.publication_commit import (
    PublicationCommitRegistry,
    commit_publication_result,
    compute_publication_decision_commit,
)
from tests.test_publication_decision_commit import _scope_descriptor, _valid_result


class DecisionCallPublicationIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.scope = _scope_descriptor((101,))
        self.call_ledger = DecisionCallLedgerRegistry(
            self.root / "call-ledger",
            scope_descriptor=self.scope,
            create_new=True,
            enabled=True,
            run_spec_sha256="3" * 64,
            pair_id="pair-1",
            arm="AFTER",
            fresh_execution_mode=True,
        )
        self.publication = PublicationCommitRegistry(
            self.root / "publication.jsonl",
            scope_descriptor=self.scope,
            create_new=True,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def traced_attempt(self, *, run_id: str, row_id: str, total_tokens: int):
        client = DecisionTracingLLMClient(
            decision_call_ledger=self.call_ledger,
            backend="http",
            endpoint="http://provider",
            model="requested-model",
            stream=False,
            server_type="vllm",
        )
        row = client.begin_row_attempt(run_id, row_id, 1, 101)

        def completed(*_args, **_kwargs):
            client.last_usage = {
                "prompt_tokens": total_tokens - 1,
                "completion_tokens": 1,
                "total_tokens": total_tokens,
            }
            client.last_usage_provenance = "PROVIDER_REPORTED"
            client.last_model = "resolved-model"
            return '{"ok":true}'

        with mock.patch.object(LLMClient, "_stream_chat_http", side_effect=completed):
            client._stream_chat_http([], tag="gatekeeper")
        seal, _ = client.seal_row_attempt()
        return row, seal

    @staticmethod
    def attach_attempt_fields(result: dict, *, row, seal, arm: str) -> None:
        result["run_meta"] = {
            "decision_call_ledger": {
                "row": row.to_dict(),
                "event_root_sha256": seal["payload"]["event_root_sha256"],
            },
            "decision_call_ledger_summary": {
                "actual_kpi_status": "PENDING_INDEPENDENT_READBACK",
                "derived_observation": {
                    "expert_calls": seal["payload"]["expert_calls"],
                    "total_tokens": seal["payload"]["total_tokens"],
                },
            },
            "decision_call_attempt_receipt": {
                "row_attempt_id": row.row_attempt_id,
                "publication_link_status": "PENDING_EXTERNAL_LEDGER_LINK",
            },
            "decision_call_measurement": {"pair_id": "pair-1", "arm": arm},
            "measurement_execution_source": "NORMAL_PUBLICATION_OWNER",
        }

    def test_two_execution_attempts_keep_costs_but_one_publication_decision(self) -> None:
        first_scope, first_seal = self.traced_attempt(
            run_id="attempt-a",
            row_id="row-a",
            total_tokens=100,
        )
        first_result = _valid_result(post_id=101)
        self.attach_attempt_fields(
            first_result,
            row=first_scope,
            seal=first_seal,
            arm="BEFORE",
        )
        first_preview = compute_publication_decision_commit(
            first_result,
            publication_scope_id=self.scope.publication_scope_id,
            attempt_run_id="attempt-a",
            input_index=1,
            post_id=101,
        )
        first_receipt, first_created = commit_publication_result(
            first_result,
            registry=self.publication,
            attempt_run_id="attempt-a",
            input_index=1,
            post_id=101,
        )
        self.assertTrue(first_created)
        self.assertEqual(first_preview.decision_id, first_receipt.decision_id)
        self.call_ledger.link_publication(
            first_scope,
            publication_decision_id=first_receipt.decision_id,
        )

        second_scope, second_seal = self.traced_attempt(
            run_id="attempt-b",
            row_id="row-b",
            total_tokens=900,
        )
        second_result = deepcopy(_valid_result(post_id=101))
        self.attach_attempt_fields(
            second_result,
            row=second_scope,
            seal=second_seal,
            arm="AFTER",
        )
        second_preview = compute_publication_decision_commit(
            second_result,
            publication_scope_id=self.scope.publication_scope_id,
            attempt_run_id="attempt-b",
            input_index=1,
            post_id=101,
        )
        second_receipt, second_created = commit_publication_result(
            second_result,
            registry=self.publication,
            attempt_run_id="attempt-b",
            input_index=1,
            post_id=101,
        )
        self.assertFalse(second_created)
        self.assertEqual(first_receipt.decision_id, second_preview.decision_id)
        self.assertEqual(first_receipt.decision_id, second_receipt.decision_id)
        self.call_ledger.link_publication(
            second_scope,
            publication_decision_id=second_receipt.decision_id,
        )

        self.assertEqual(self.publication.count, 1)
        summary = self.call_ledger.summary()
        self.assertEqual(summary["row_attempt_count"], 2)
        self.assertEqual(summary["linked_row_attempt_count"], 2)
        self.assertEqual(summary["derived_observation"]["expert_calls"], 2)
        self.assertEqual(summary["derived_observation"]["total_tokens"], 1000)
        self.assertIn("AMBIGUOUS_MULTIPLE_ATTEMPT_RUNS", summary["reason_codes"])
        self.assertIsNone(summary["actual_metrics"]["expert_calls"])


if __name__ == "__main__":
    unittest.main()
