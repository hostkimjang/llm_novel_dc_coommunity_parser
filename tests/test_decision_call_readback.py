from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.llm_batch.decision_call_events import DecisionCallLedgerRegistry, RowAttemptScope
from src.llm_batch.decision_call_readback import (
    compute_readback_report_sha256,
    read_decision_call_ledger,
    verify_readback_report_sha256,
)
import src.llm_batch.decision_call_readback as readback_module
from src.llm_batch.publication_commit import build_publication_scope_descriptor


STARTED = "2026-07-12T10:00:00+09:00"
FINISHED = "2026-07-12T10:00:01+09:00"
REQUEST_SHA = "a" * 64
RESPONSE_SHA = "b" * 64
DECISION_SHA = "d" * 64


class DecisionCallReadbackTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "ledger"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def registry(self, post_ids=(101,)) -> DecisionCallLedgerRegistry:
        scope = build_publication_scope_descriptor(
            input_file_sha256="1" * 64,
            post_ids=list(post_ids),
            config_hash="readback-test",
            release_fingerprint="2" * 64,
        )
        return DecisionCallLedgerRegistry(
            self.root, scope_descriptor=scope, create_new=True, enabled=True,
            run_spec_sha256="e" * 64, pair_id="pair-1", arm="AFTER",
            fresh_execution_mode=True,
        )

    @staticmethod
    def row(registry: DecisionCallLedgerRegistry, *, attempt: str = "row-1",
            index: int = 1, post_id: int = 101, run: str = "run-1") -> RowAttemptScope:
        return registry.row_attempt(
            attempt_run_id=run, row_attempt_id=attempt,
            input_index=index, post_id=post_id,
        )

    @staticmethod
    def call(registry: DecisionCallLedgerRegistry, row: RowAttemptScope, *,
             call_id: str, logical_id: str, ordinal: int = 0,
             parent: str | None = None, status: str = "SUCCEEDED",
             prompt: int = 5, completion: int = 2, start_ns: int = 1_000_000_000,
             resolved_model: str | None = "resolved",
             provenance: str = "PROVIDER_REPORTED") -> None:
        registry.record_dispatch_intent(
            row, logical_call_id=logical_id, call_id=call_id,
            retry_ordinal=ordinal, retry_of_call_id=parent, stage="GATEKEEPER",
            modality="TEXT", requested_model="requested", resolved_model=None,
            endpoint="http://provider", backend="http", started_at=STARTED,
            monotonic_started_ns=start_ns, request_sha256=REQUEST_SHA,
        )
        success = status == "SUCCEEDED"
        registry.record_terminal(
            row, call_id=call_id, terminal_status=status,
            resolved_model=resolved_model, response_sha256=RESPONSE_SHA if success else None,
            usage_provenance=provenance, prompt_tokens=prompt,
            completion_tokens=completion, total_tokens=prompt + completion,
            error_type=None if success else "ReadTimeout",
            error_message_sha256=None if success else "c" * 64,
            finished_at=FINISHED,
            monotonic_finished_ns=start_ns + 100_000_000,
        )

    @staticmethod
    def close(registry: DecisionCallLedgerRegistry, row: RowAttemptScope, *, link: bool = True) -> None:
        registry.seal_row(
            row, sealed_at=FINISHED, monotonic_finished_ns=2_000_000_000,
        )
        if link:
            registry.link_publication(
                row, publication_decision_id=DECISION_SHA, linked_at=FINISHED,
            )

    def test_exact_aggregate_retry_and_wal_comparison_receipts(self) -> None:
        registry = self.registry((101, 102))
        first = self.row(registry)
        self.call(registry, first, call_id="call-0", logical_id="logical-0",
                  status="FAILED", prompt=4, completion=0)
        self.call(registry, first, call_id="call-1", logical_id="logical-0",
                  ordinal=1, parent="call-0", prompt=10, completion=2,
                  start_ns=1_200_000_000)
        self.close(registry, first)
        second = self.row(registry, attempt="row-2", index=2, post_id=102)
        self.call(registry, second, call_id="call-2", logical_id="logical-2",
                  prompt=6, completion=1)
        self.close(registry, second)

        report = read_decision_call_ledger(self.root)

        self.assertEqual(report["gate_status"], "GO")
        self.assertEqual(report["aggregate_status"], "EXACT")
        self.assertEqual(report["actual_metrics"], {
            "expert_calls": 3, "text_calls": 3, "vlm_calls": 0,
            "retry_count": 1, "prompt_tokens": 20,
            "completion_tokens": 3, "total_tokens": 23,
            "physical_call_wall_ms_sum": 300,
        })
        self.assertEqual(report["attempts"]["successful"], 2)
        self.assertEqual(report["attempts"]["failed"], 1)
        self.assertEqual(report["attempts"]["retries"], 1)
        self.assertEqual(report["usage"]["provenance_counts"]["PROVIDER_REPORTED"], 3)
        self.assertEqual(report["coverage"]["attempt_run_ids"], ["run-1"])
        self.assertEqual(report["publication_recovery_status"], "NOT_ASSESSED")
        self.assertRegex(report["scope"]["scope_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            [(row["input_index"], row["post_id"], row["publication_decision_id"])
             for row in report["rows"]],
            [(1, 101, DECISION_SHA), (2, 102, DECISION_SHA)],
        )
        self.assertTrue(all(row["seal_frame_sha256"] == row["link_seal_frame_sha256"]
                            for row in report["rows"]))
        self.assertEqual(
            [row["expert_calls"] for row in report["rows"]],
            [2, 1],
        )
        self.assertEqual(
            [row["physical_call_wall_ms_sum"] for row in report["rows"]],
            [200, 100],
        )
        self.assertTrue(verify_readback_report_sha256(report))
        serialized = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("raw prompt", serialized.lower())
        self.assertNotIn("raw response", serialized.lower())

    def test_corruption_and_truncation_fail_closed(self) -> None:
        registry = self.registry()
        row = self.row(registry)
        self.call(registry, row, call_id="call-0", logical_id="logical-0")
        self.close(registry, row)
        frame = next((self.root / "frames").glob("terminal_*.json"))
        value = json.loads(frame.read_text(encoding="utf-8"))
        value["payload"]["prompt_tokens"] = 999
        frame.write_text(json.dumps(value), encoding="utf-8")
        corrupted = read_decision_call_ledger(self.root)
        self.assertEqual(corrupted["gate_status"], "NO-GO")
        self.assertIn("INVALID_FRAME", corrupted["reason_codes"])
        self.assertEqual(corrupted["actual_kpi_status"], "NOT_ESTIMABLE")

        frame.write_bytes(b'{"schema_version":')
        truncated = read_decision_call_ledger(self.root)
        self.assertEqual(truncated["gate_status"], "NO-GO")
        self.assertIn("INVALID_FRAME", truncated["reason_codes"])
        self.assertTrue(any("invalid frame JSON" in item["error"] for item in truncated["errors"]))

    def test_orphan_terminal_is_reported_and_not_estimable(self) -> None:
        registry = self.registry()
        row = self.row(registry)
        self.call(registry, row, call_id="call-0", logical_id="logical-0")
        self.close(registry, row)
        next((self.root / "frames").glob("dispatch_intent_*.json")).unlink()

        report = read_decision_call_ledger(self.root)

        self.assertIn("ORPHAN_TERMINAL", report["reason_codes"])
        self.assertEqual(report["findings"]["orphan_terminals"], ["call-0"])
        self.assertEqual(report["aggregate_status"], "NOT_ESTIMABLE")

    def test_unresolved_terminal_model_fails_closed(self) -> None:
        registry = self.registry()
        row = self.row(registry)
        self.call(registry, row, call_id="call-0", logical_id="logical-0",
                  resolved_model=None)
        self.close(registry, row)

        report = read_decision_call_ledger(self.root)

        self.assertIn("RESOLVED_MODEL_UNAVAILABLE", report["reason_codes"])
        self.assertEqual(report["actual_kpi_status"], "NOT_ESTIMABLE")
        self.assertTrue(all(value is None for value in report["actual_metrics"].values()))

    def test_estimated_usage_fails_closed_but_preserves_provenance(self) -> None:
        registry = self.registry()
        row = self.row(registry)
        self.call(registry, row, call_id="call-0", logical_id="logical-0",
                  provenance="ESTIMATED")
        self.close(registry, row)

        report = read_decision_call_ledger(self.root)

        self.assertIn("USAGE_ESTIMATED", report["reason_codes"])
        self.assertEqual(report["usage"]["provenance_counts"]["ESTIMATED"], 1)
        self.assertFalse(report["usage"]["aggregate_exact"])
        self.assertEqual(report["aggregate_status"], "NOT_ESTIMABLE")

    def test_multiple_attempt_runs_with_partial_coverage_are_ambiguous(self) -> None:
        registry = self.registry((101, 102))
        first = self.row(registry, attempt="row-a", run="run-a")
        self.call(registry, first, call_id="call-a", logical_id="logical-a")
        self.close(registry, first)
        second = self.row(registry, attempt="row-b", index=2, post_id=102, run="run-b")
        self.call(registry, second, call_id="call-b", logical_id="logical-b")
        self.close(registry, second)

        report = read_decision_call_ledger(self.root)

        self.assertEqual(report["coverage"]["attempt_run_ids"], ["run-a", "run-b"])
        self.assertIn("AMBIGUOUS_ATTEMPT_RUN", report["reason_codes"])
        self.assertIn("ROW_COVERAGE_INCOMPLETE", report["reason_codes"])
        self.assertEqual(report["actual_kpi_status"], "NOT_ESTIMABLE")

    def test_report_and_frame_set_hashes_are_stable_and_detect_tamper(self) -> None:
        registry = self.registry()
        row = self.row(registry)
        self.call(registry, row, call_id="call-0", logical_id="logical-0")
        self.close(registry, row)

        first = read_decision_call_ledger(self.root)
        second = read_decision_call_ledger(self.root)
        self.assertEqual(first["frame_set_sha256"], second["frame_set_sha256"])
        self.assertEqual(first["report_sha256"], second["report_sha256"])
        self.assertTrue(verify_readback_report_sha256(first))

        tampered = deepcopy(first)
        tampered["observed_metrics"]["total_tokens"] += 1
        self.assertFalse(verify_readback_report_sha256(tampered))
        recomputed = compute_readback_report_sha256(tampered)
        self.assertNotEqual(recomputed, first["report_sha256"])
        tampered["report_sha256"] = recomputed
        self.assertTrue(verify_readback_report_sha256(tampered))

    def test_unlinked_row_is_reported(self) -> None:
        registry = self.registry()
        row = self.row(registry)
        self.call(registry, row, call_id="call-0", logical_id="logical-0")
        self.close(registry, row, link=False)

        report = read_decision_call_ledger(self.root)

        self.assertIn("UNLINKED_ROW", report["reason_codes"])
        self.assertEqual(report["coverage"]["unlinked_rows"], ["row-1"])
        self.assertEqual(report["measurement_completion_status"], "NOT_ESTIMABLE")

    def test_frame_added_during_readback_is_forensic_no_go(self) -> None:
        registry = self.registry()
        row = self.row(registry)
        self.call(registry, row, call_id="call-0", logical_id="logical-0")
        self.close(registry, row)

        original = readback_module._stable_bytes
        mutated = False

        def add_late_frame(path: Path) -> bytes:
            nonlocal mutated
            raw = original(path)
            if path.parent.name == "frames" and not mutated:
                mutated = True
                (path.parent / "late.json").write_text("{}\n", encoding="utf-8")
            return raw

        with patch.object(readback_module, "_stable_bytes", side_effect=add_late_frame):
            report = read_decision_call_ledger(self.root)

        self.assertIn("FRAME_SET_CHANGED_DURING_READBACK", report["reason_codes"])
        self.assertEqual("NO-GO", report["gate_status"])
        self.assertEqual("NOT_ESTIMABLE", report["actual_kpi_status"])

    def test_frame_replaced_after_parse_is_forensic_no_go(self) -> None:
        registry = self.registry()
        row = self.row(registry)
        self.call(registry, row, call_id="call-0", logical_id="logical-0")
        self.close(registry, row)

        original = readback_module._stable_bytes
        mutated = False

        def replace_parsed_frame(path: Path) -> bytes:
            nonlocal mutated
            raw = original(path)
            if path.parent.name == "frames" and not mutated:
                mutated = True
                path.write_bytes(raw + b" ")
            return raw

        with patch.object(readback_module, "_stable_bytes", side_effect=replace_parsed_frame):
            report = read_decision_call_ledger(self.root)

        self.assertIn("FRAME_CHANGED_DURING_READBACK", report["reason_codes"])
        self.assertEqual("NO-GO", report["gate_status"])
        self.assertEqual("NOT_ESTIMABLE", report["actual_kpi_status"])

    def test_duplicate_row_coordinate_is_ambiguous(self) -> None:
        registry = self.registry()
        first = self.row(registry, attempt="row-a")
        self.call(registry, first, call_id="call-a", logical_id="logical-a")
        self.close(registry, first)
        duplicate = self.row(registry, attempt="row-b")
        self.call(registry, duplicate, call_id="call-b", logical_id="logical-b")
        self.close(registry, duplicate)

        report = read_decision_call_ledger(self.root)

        self.assertIn("AMBIGUOUS_ROW_ATTEMPT", report["reason_codes"])
        self.assertEqual(report["coverage"]["ambiguous_rows"], ["row-a", "row-b"])
        self.assertEqual(report["gate_status"], "NO-GO")
        self.assertEqual(report["aggregate_status"], "NOT_ESTIMABLE")


if __name__ == "__main__":
    unittest.main()
