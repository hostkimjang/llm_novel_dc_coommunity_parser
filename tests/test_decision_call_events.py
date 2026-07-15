from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from src.llm_batch.ledger.decision_call_events import (
    DecisionCallLedgerConflict,
    DecisionCallLedgerError,
    DecisionCallLedgerIncomplete,
    DecisionCallLedgerRegistry,
    RowAttemptScope,
)
from src.llm_batch.ledger.publication_commit import build_publication_scope_descriptor


STARTED_AT = "2026-07-12T10:00:00+09:00"
FINISHED_AT = "2026-07-12T10:00:01+09:00"
START_NS = 1_000_000_000
FINISH_NS = 1_100_000_000
REQUEST_SHA = "a" * 64
RESPONSE_SHA = "b" * 64
DECISION_SHA = "d" * 64
RUN_SPEC_SHA = "e" * 64


def _scope(post_ids=(101,)):
    return build_publication_scope_descriptor(
        input_file_sha256="1" * 64,
        post_ids=list(post_ids),
        config_hash="decision-call-ledger-tests",
        release_fingerprint="2" * 64,
    )


class DecisionCallLedgerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.scope = _scope()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def registry(
        self,
        *,
        name: str = "ledger",
        scope=None,
        create_new: bool = True,
        bound: bool = True,
    ) -> DecisionCallLedgerRegistry:
        kwargs = {}
        if bound:
            kwargs = {
                "run_spec_sha256": RUN_SPEC_SHA,
                "pair_id": "pair-1",
                "arm": "BEFORE",
                "fresh_execution_mode": True,
            }
        return DecisionCallLedgerRegistry(
            self.root / name,
            scope_descriptor=scope or self.scope,
            create_new=create_new,
            enabled=True,
            **kwargs,
        )

    @staticmethod
    def row(
        registry: DecisionCallLedgerRegistry,
        *,
        run: str = "run-a",
        attempt: str = "row-attempt-a",
        index: int = 1,
        post_id: int = 101,
    ) -> RowAttemptScope:
        return registry.row_attempt(
            attempt_run_id=run,
            row_attempt_id=attempt,
            input_index=index,
            post_id=post_id,
        )

    @staticmethod
    def dispatch(
        registry: DecisionCallLedgerRegistry,
        row: RowAttemptScope,
        *,
        call_id: str = "call-0",
        logical_call_id: str = "logical-0",
        ordinal: int = 0,
        parent: str | None = None,
        start_ns: int = START_NS,
    ):
        return registry.record_dispatch_intent(
            row,
            logical_call_id=logical_call_id,
            call_id=call_id,
            retry_ordinal=ordinal,
            retry_of_call_id=parent,
            stage="GATEKEEPER",
            modality="TEXT",
            requested_model="requested-model",
            resolved_model=None,
            endpoint="http://127.0.0.1:8000/v1",
            backend="http",
            started_at=STARTED_AT,
            monotonic_started_ns=start_ns,
            request_sha256=REQUEST_SHA,
        )

    @staticmethod
    def terminal(
        registry: DecisionCallLedgerRegistry,
        row: RowAttemptScope,
        *,
        call_id: str = "call-0",
        status: str = "SUCCEEDED",
        provenance: str = "PROVIDER_REPORTED",
        prompt: int | None = 10,
        completion: int | None = 2,
        total: int | None = 12,
        response_sha: str | None = RESPONSE_SHA,
        error_type: str | None = None,
        error_sha: str | None = None,
        finish_ns: int = FINISH_NS,
    ):
        return registry.record_terminal(
            row,
            call_id=call_id,
            terminal_status=status,
            resolved_model="resolved-model",
            response_sha256=response_sha,
            usage_provenance=provenance,
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            error_type=error_type,
            error_message_sha256=error_sha,
            finished_at=FINISHED_AT,
            monotonic_finished_ns=finish_ns,
        )

    def test_roundtrip_idempotence_seal_link_and_readback(self) -> None:
        registry = self.registry()
        row = self.row(registry)
        first, created = self.dispatch(registry, row)
        replay, replay_created = self.dispatch(registry, row)
        self.assertTrue(created)
        self.assertFalse(replay_created)
        self.assertEqual(first, replay)

        terminal, terminal_created = self.terminal(registry, row)
        terminal_replay, terminal_replay_created = self.terminal(registry, row)
        self.assertTrue(terminal_created)
        self.assertFalse(terminal_replay_created)
        self.assertEqual(terminal, terminal_replay)

        seal, _ = registry.seal_row(
            row,
            sealed_at=FINISHED_AT,
            monotonic_finished_ns=FINISH_NS,
        )
        link, _ = registry.link_publication(
            row,
            publication_decision_id=DECISION_SHA,
            linked_at=FINISHED_AT,
        )
        self.assertEqual(link["payload"]["event_root_sha256"], seal["payload"]["event_root_sha256"])

        summary = registry.summary()
        self.assertEqual(summary["actual_kpi_status"], "PENDING_INDEPENDENT_READBACK")
        self.assertIsNone(summary["actual_metrics"]["expert_calls"])
        self.assertIsNone(summary["actual_metrics"]["total_tokens"])
        self.assertEqual(summary["derived_observation"]["expert_calls"], 1)
        self.assertEqual(summary["derived_observation"]["total_tokens"], 12)

        reopened = self.registry(create_new=False, bound=False)
        readback = reopened.readback()
        self.assertEqual(len(readback["frames"]), 4)
        self.assertEqual(
            readback["summary"]["actual_kpi_status"],
            "PENDING_INDEPENDENT_READBACK",
        )
        serialized = json.dumps(readback, ensure_ascii=False)
        self.assertNotIn("raw prompt body", serialized)
        self.assertNotIn("raw response body", serialized)

    def test_reload_rejects_frame_tamper(self) -> None:
        registry = self.registry()
        row = self.row(registry)
        self.dispatch(registry, row)
        frame_path = next((self.root / "ledger" / "frames").glob("dispatch_intent_*.json"))
        payload = json.loads(frame_path.read_text(encoding="utf-8"))
        payload["payload"]["request_sha256"] = "f" * 64
        frame_path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(DecisionCallLedgerError, "self hash"):
            self.registry(create_new=False, bound=False)

    def test_intent_without_terminal_is_partial_and_cannot_seal(self) -> None:
        registry = self.registry()
        row = self.row(registry)
        self.dispatch(registry, row)
        summary = registry.summary()
        self.assertEqual(summary["actual_kpi_status"], "NOT_ESTIMABLE")
        self.assertEqual(summary["open_call_count"], 1)
        self.assertIsNone(summary["actual_metrics"]["expert_calls"])
        with self.assertRaisesRegex(DecisionCallLedgerIncomplete, "without terminal"):
            registry.seal_row(
                row,
                sealed_at=FINISHED_AT,
                monotonic_finished_ns=FINISH_NS,
            )
        registry.abort_row(
            row,
            reason_code="PIPELINE_CRASH",
            aborted_at=FINISHED_AT,
            monotonic_finished_ns=FINISH_NS,
        )
        with self.assertRaisesRegex(DecisionCallLedgerConflict, "late terminal"):
            self.terminal(registry, row)

    def test_double_terminal_conflict(self) -> None:
        registry = self.registry()
        row = self.row(registry)
        self.dispatch(registry, row)
        self.terminal(
            registry,
            row,
            status="FAILED",
            provenance="UNAVAILABLE",
            prompt=None,
            completion=None,
            total=None,
            response_sha=None,
            error_type="TimeoutError",
            error_sha="3" * 64,
        )
        with self.assertRaisesRegex(DecisionCallLedgerConflict, "double terminal"):
            self.terminal(registry, row)

    def test_retry_gap_rejected_and_complete_retry_counts_physical_calls(self) -> None:
        registry = self.registry()
        row = self.row(registry)
        with self.assertRaisesRegex(DecisionCallLedgerError, "retry lineage gap"):
            self.dispatch(
                registry,
                row,
                call_id="call-1",
                logical_call_id="logical-0",
                ordinal=1,
                parent="call-0",
            )

        self.dispatch(registry, row, call_id="call-0")
        self.terminal(
            registry,
            row,
            call_id="call-0",
            status="FAILED",
            provenance="PROVIDER_REPORTED",
            prompt=4,
            completion=0,
            total=4,
            response_sha=None,
            error_type="ReadTimeout",
            error_sha="4" * 64,
        )
        self.dispatch(
            registry,
            row,
            call_id="call-1",
            logical_call_id="logical-0",
            ordinal=1,
            parent="call-0",
            start_ns=1_200_000_000,
        )
        self.terminal(
            registry,
            row,
            call_id="call-1",
            prompt=10,
            completion=2,
            total=12,
            finish_ns=1_300_000_000,
        )
        seal, _ = registry.seal_row(
            row,
            sealed_at=FINISHED_AT,
            monotonic_finished_ns=1_300_000_000,
        )
        self.assertEqual(seal["payload"]["expert_calls"], 2)
        self.assertEqual(seal["payload"]["retry_count"], 1)
        self.assertEqual(seal["payload"]["total_tokens"], 16)

    def test_scope_index_post_and_terminal_cross_row_are_rejected(self) -> None:
        scope = _scope((101, 102))
        registry = self.registry(name="cross", scope=scope)
        wrong = RowAttemptScope(
            publication_scope_id=scope.publication_scope_id,
            attempt_run_id="run-a",
            row_attempt_id="wrong",
            input_index=1,
            post_id=102,
        )
        with self.assertRaisesRegex(DecisionCallLedgerError, "input_index/post_id"):
            self.dispatch(registry, wrong)

        first = self.row(registry, post_id=101, index=1)
        second = self.row(
            registry,
            run="run-a",
            attempt="row-attempt-b",
            post_id=102,
            index=2,
        )
        self.dispatch(registry, first)
        with self.assertRaisesRegex(DecisionCallLedgerError, "cross-row"):
            self.terminal(registry, second)

    def test_late_event_after_seal_is_rejected(self) -> None:
        registry = self.registry()
        row = self.row(registry)
        registry.seal_row(
            row,
            sealed_at=FINISHED_AT,
            monotonic_finished_ns=FINISH_NS,
        )
        with self.assertRaisesRegex(DecisionCallLedgerConflict, "late dispatch"):
            self.dispatch(registry, row)

    def test_same_publication_decision_keeps_two_attempt_ledgers(self) -> None:
        registry = self.registry()
        first = self.row(registry, run="run-a", attempt="attempt-a")
        second = self.row(registry, run="run-b", attempt="attempt-b")

        self.dispatch(registry, first, call_id="call-a", logical_call_id="logical-a")
        self.terminal(
            registry,
            first,
            call_id="call-a",
            prompt=90,
            completion=10,
            total=100,
        )
        registry.seal_row(first, sealed_at=FINISHED_AT, monotonic_finished_ns=FINISH_NS)
        registry.link_publication(first, publication_decision_id=DECISION_SHA, linked_at=FINISHED_AT)

        self.dispatch(registry, second, call_id="call-b", logical_call_id="logical-b")
        self.terminal(
            registry,
            second,
            call_id="call-b",
            prompt=800,
            completion=100,
            total=900,
        )
        registry.seal_row(second, sealed_at=FINISHED_AT, monotonic_finished_ns=FINISH_NS)
        registry.link_publication(second, publication_decision_id=DECISION_SHA, linked_at=FINISHED_AT)

        summary = registry.summary()
        self.assertEqual(summary["row_attempt_count"], 2)
        self.assertEqual(summary["linked_row_attempt_count"], 2)
        self.assertEqual(summary["actual_kpi_status"], "NOT_ESTIMABLE")
        self.assertIn(
            "AMBIGUOUS_MULTIPLE_ATTEMPT_RUNS",
            summary["reason_codes"],
        )
        self.assertIsNone(summary["actual_metrics"]["expert_calls"])
        self.assertIsNone(summary["actual_metrics"]["total_tokens"])
        self.assertEqual(summary["derived_observation"]["expert_calls"], 2)
        self.assertEqual(summary["derived_observation"]["total_tokens"], 1000)
        links = [
            frame for frame in registry.readback()["frames"]
            if frame["frame_kind"] == "PUBLICATION_LINK"
        ]
        self.assertEqual(len(links), 2)
        self.assertEqual(
            {item["payload"]["publication_decision_id"] for item in links},
            {DECISION_SHA},
        )

    def test_usage_unavailable_seals_with_null_tokens_and_keeps_actual_kpi_null(self) -> None:
        registry = self.registry()
        row = self.row(registry)
        self.dispatch(registry, row)
        self.terminal(
            registry,
            row,
            provenance="UNAVAILABLE",
            prompt=None,
            completion=None,
            total=None,
        )
        seal, _ = registry.seal_row(
            row,
            sealed_at=FINISHED_AT,
            monotonic_finished_ns=FINISH_NS,
        )
        registry.link_publication(row, publication_decision_id=DECISION_SHA, linked_at=FINISHED_AT)
        self.assertEqual(seal["payload"]["usage_status"], "UNAVAILABLE")
        self.assertIsNone(seal["payload"]["total_tokens"])
        summary = registry.summary()
        self.assertEqual(summary["actual_kpi_status"], "NOT_ESTIMABLE")
        self.assertIn("USAGE_UNAVAILABLE", summary["reason_codes"])
        self.assertIsNone(summary["actual_metrics"]["expert_calls"])

    def test_unbound_and_disabled_paths_never_promote_actual_kpis(self) -> None:
        disabled = DecisionCallLedgerRegistry()
        self.assertEqual(disabled.summary()["instrumentation_status"], "DISABLED")
        self.assertEqual(disabled.summary()["actual_kpi_status"], "NOT_ESTIMABLE")

        unbound = self.registry(name="unbound", bound=False)
        row = self.row(unbound)
        unbound.seal_row(row, sealed_at=FINISHED_AT, monotonic_finished_ns=FINISH_NS)
        unbound.link_publication(row, publication_decision_id=DECISION_SHA, linked_at=FINISHED_AT)
        summary = unbound.summary()
        self.assertEqual(summary["measurement_binding_status"], "UNBOUND_PARTIAL")
        self.assertEqual(summary["actual_kpi_status"], "NOT_ESTIMABLE")
        self.assertIsNone(summary["actual_metrics"]["expert_calls"])

    def test_publication_link_requires_seal(self) -> None:
        registry = self.registry()
        row = self.row(registry)
        with self.assertRaisesRegex(DecisionCallLedgerIncomplete, "sealed row"):
            registry.link_publication(row, publication_decision_id=DECISION_SHA)


if __name__ == "__main__":
    unittest.main()
