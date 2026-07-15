from __future__ import annotations

from pathlib import Path
import json
import tempfile
import threading
import unittest
from unittest import mock

from src.llm_batch.ledger.decision_call_events import DecisionCallLedgerRegistry
from src.llm_batch.ledger.decision_ledger_dual_write import (
    DecisionLedgerV2DualWriteAdapter,
    _sha,
)
from src.llm_batch.ledger.decision_ledger_v2 import DecisionCallLedgerV2, DecisionLedgerV2Error
from src.llm_batch.ledger.decision_tracing_llm import DecisionTracingLLMClient
from src.llm_batch.llm.client import LLMClient
from src.llm_batch.ledger.publication_commit import build_publication_scope_descriptor
from expert_main import (
    _decision_affecting_publication_config,
    _decision_ledger_v2_off_status,
    _maybe_enable_decision_ledger_v2_shadow,
    _publication_decision_environment,
)


def scope():
    return build_publication_scope_descriptor(
        input_file_sha256="1" * 64,
        post_ids=[101],
        config_hash="dual-write-shadow-test",
        release_fingerprint="2" * 64,
    )


class DecisionLedgerDualWriteTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.legacy = DecisionCallLedgerRegistry(
            self.root / "legacy",
            scope_descriptor=scope(),
            create_new=True,
            enabled=True,
            run_spec_sha256="3" * 64,
            pair_id="pair-dual",
            arm="BEFORE",
            fresh_execution_mode=True,
        )

    def tearDown(self):
        self.temporary.cleanup()

    def record_dispatch(self, ledger, *, call_id="call-0"):
        row = ledger.row_attempt(
            attempt_run_id="run-a", row_attempt_id="row-a", input_index=1, post_id=101
        )
        return ledger.record_dispatch_intent(
            row,
            logical_call_id=f"logical-{call_id}",
            call_id=call_id,
            retry_ordinal=0,
            stage="GATEKEEPER",
            modality="TEXT",
            requested_model="requested-model",
            resolved_model=None,
            endpoint="http://127.0.0.1:8000/v1",
            backend="http",
            request_sha256="a" * 64,
        )

    def test_default_off_creates_no_v2_files_and_preserves_legacy(self):
        v2_root = self.root / "v2"
        adapter = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=False
        )
        frame, created = self.record_dispatch(adapter)
        self.assertTrue(created)
        self.assertEqual(frame, self.legacy.readback()["frames"][0])
        self.assertFalse(v2_root.exists())
        self.assertFalse(adapter.shadow_status()["shadow_enabled"])

    def test_explicit_shadow_dual_write_is_equivalent_and_noninterfering(self):
        v2_root = self.root / "v2"
        adapter = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True
        )
        result = self.record_dispatch(adapter)
        self.assertEqual(result[0], self.legacy.readback()["frames"][0])
        self.assertTrue(adapter.shadow_enabled)
        self.assertEqual(
            self.legacy.readback()["frames"],
            DecisionCallLedgerV2(
                v2_root,
                scope_sha256=self.legacy.readback()["scope"]["scope_sha256"],
            ).replay(),
        )
        self.assertFalse(adapter.shadow_status()["public_result_interference"])

    def test_shadow_mode_does_not_change_publication_fingerprint_inputs(self):
        shared = {
            "llm_mode": "server",
            "decision_call_measurement": {"mode": "SHADOW"},
        }
        off = {
            **shared,
            "decision_ledger_v2_shadow": {"mode": "OFF", "enabled": False},
        }
        enabled = {
            **shared,
            "decision_ledger_v2_shadow": {
                "mode": "DUAL_WRITE_SHADOW",
                "enabled": True,
            },
        }
        self.assertEqual(
            _decision_affecting_publication_config(off),
            _decision_affecting_publication_config(enabled),
        )
        self.assertEqual(
            _publication_decision_environment(
                {
                    "LLM_MODEL": "model",
                    "PIPELINE_DECISION_LEDGER_V2_SHADOW_MODE": "OFF",
                }
            ),
            _publication_decision_environment(
                {
                    "LLM_MODEL": "model",
                    "PIPELINE_DECISION_LEDGER_V2_SHADOW_MODE": "DUAL_WRITE_SHADOW",
                }
            ),
        )

    def test_v2_append_failure_disables_only_shadow_after_legacy_commit(self):
        adapter = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=self.root / "v2", shadow_enabled=True
        )
        assert adapter._v2 is not None
        with mock.patch.object(adapter._v2, "append", side_effect=DecisionLedgerV2Error("boom")):
            frame, created = self.record_dispatch(adapter)
        self.assertTrue(created)
        self.assertIn(frame, self.legacy.readback()["frames"])
        self.assertFalse(adapter.shadow_enabled)
        self.assertIn("V2_APPEND_FAILED", adapter.shadow_status()["reason_code"])

    def test_restart_reconciles_a_legacy_only_committed_frame(self):
        v2_root = self.root / "v2"
        adapter = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True
        )
        self.record_dispatch(adapter)
        row = self.legacy.row_attempt(
            attempt_run_id="run-a", row_attempt_id="row-a", input_index=1, post_id=101
        )
        self.legacy.record_terminal(
            row,
            call_id="call-0",
            terminal_status="SUCCEEDED",
            resolved_model="resolved-model",
            response_sha256="b" * 64,
            usage_provenance="PROVIDER_REPORTED",
            prompt_tokens=2,
            completion_tokens=1,
            total_tokens=3,
        )
        restarted = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True, reconcile_on_start=True
        )
        self.assertTrue(restarted.shadow_enabled)
        self.assertEqual(2, restarted.shadow_status()["v2_frame_count"])

    def test_concurrent_reconcile_cannot_duplicate_a_committed_legacy_frame(self):
        v2_root = self.root / "v2"
        adapter = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True
        )
        started = threading.Event()
        finished = threading.Event()

        def write():
            started.set()
            try:
                self.record_dispatch(adapter)
            finally:
                finished.set()

        # Holding the adapter lock forces the writer to stop before its legacy
        # commit.  This is the ordering guarantee that prevents reconcile from
        # observing an authoritative frame that has not yet been mirrored.
        with adapter._lock:
            worker = threading.Thread(target=write)
            worker.start()
            self.assertTrue(started.wait(5))
            self.assertEqual([], self.legacy.readback()["frames"])
            status = adapter.reconcile_from_legacy()
            self.assertTrue(status["shadow_enabled"])
        self.assertTrue(finished.wait(5))
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(1, len(self.legacy.readback()["frames"]))
        scope_sha256 = self.legacy.readback()["scope"]["scope_sha256"]
        self.assertEqual(
            self.legacy.readback()["frames"],
            DecisionCallLedgerV2(v2_root, scope_sha256=scope_sha256).replay(),
        )
        self.assertTrue(adapter.reconcile_from_legacy()["shadow_enabled"])
        restarted = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True, reconcile_on_start=True
        )
        self.assertTrue(restarted.shadow_enabled)
        self.assertEqual(1, restarted.shadow_status()["v2_frame_count"])

    def test_cross_adapter_reconcile_waits_for_legacy_commit_and_mirror(self):
        v2_root = self.root / "v2"
        writer_adapter = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True
        )
        restart_adapter = DecisionLedgerV2DualWriteAdapter(
            self.legacy,
            v2_root=v2_root,
            shadow_enabled=True,
            reconcile_on_start=False,
        )
        mirror_entered = threading.Event()
        release_mirror = threading.Event()
        reconcile_finished = threading.Event()
        original_mirror = writer_adapter._mirror_created_frame
        reconcile_result = {}

        def delayed_mirror(frame):
            mirror_entered.set()
            self.assertTrue(release_mirror.wait(5))
            original_mirror(frame)

        def write():
            self.record_dispatch(writer_adapter)

        def reconcile():
            try:
                reconcile_result.update(restart_adapter.reconcile_from_legacy())
            finally:
                reconcile_finished.set()

        writer_adapter._mirror_created_frame = delayed_mirror
        writer = threading.Thread(target=write)
        writer.start()
        self.assertTrue(mirror_entered.wait(5))
        self.assertEqual(1, len(self.legacy.readback()["frames"]))
        reconciler = threading.Thread(target=reconcile)
        reconciler.start()
        self.assertFalse(reconcile_finished.wait(0.1))
        release_mirror.set()
        writer.join(5)
        reconciler.join(5)
        self.assertFalse(writer.is_alive())
        self.assertFalse(reconciler.is_alive())
        self.assertTrue(reconcile_result["shadow_enabled"])
        scope_sha256 = self.legacy.readback()["scope"]["scope_sha256"]
        v2_frames = DecisionCallLedgerV2(
            v2_root, scope_sha256=scope_sha256
        ).replay()
        self.assertEqual(self.legacy.readback()["frames"], v2_frames)
        self.assertEqual(1, len(v2_frames))
        restarted = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True
        )
        self.assertTrue(restarted.shadow_enabled)
        self.assertEqual(1, restarted.shadow_status()["v2_frame_count"])

    def test_cross_adapter_rollback_stops_future_mirrors_after_inflight_write(self):
        v2_root = self.root / "v2"
        writer_adapter = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True
        )
        rollback_adapter = DecisionLedgerV2DualWriteAdapter(
            self.legacy,
            v2_root=v2_root,
            shadow_enabled=True,
            reconcile_on_start=False,
        )
        mirror_entered = threading.Event()
        release_mirror = threading.Event()
        rollback_finished = threading.Event()
        original_mirror = writer_adapter._mirror_created_frame

        def delayed_mirror(frame):
            mirror_entered.set()
            self.assertTrue(release_mirror.wait(5))
            original_mirror(frame)

        writer_adapter._mirror_created_frame = delayed_mirror
        first = threading.Thread(target=lambda: self.record_dispatch(writer_adapter))
        first.start()
        self.assertTrue(mirror_entered.wait(5))

        def rollback():
            try:
                rollback_adapter.disable_shadow("OPERATOR_ROLLBACK")
            finally:
                rollback_finished.set()

        rollback_thread = threading.Thread(target=rollback)
        rollback_thread.start()
        self.assertFalse(rollback_finished.wait(0.1))
        release_mirror.set()
        first.join(5)
        rollback_thread.join(5)
        self.assertFalse(first.is_alive())
        self.assertFalse(rollback_thread.is_alive())
        self.assertFalse(rollback_adapter.shadow_enabled)

        stale_status = writer_adapter.shadow_status()
        self.assertFalse(stale_status["shadow_enabled"])
        self.assertEqual("OPERATOR_ROLLBACK", stale_status["reason_code"])

        # The stale writer adapter must re-read the shared DISABLED control
        # before its next authoritative write and stay legacy-only.
        self.record_dispatch(writer_adapter, call_id="call-1")
        self.assertFalse(writer_adapter.shadow_enabled)
        self.assertEqual("OPERATOR_ROLLBACK", writer_adapter.shadow_status()["reason_code"])
        self.assertEqual(2, len(self.legacy.readback()["frames"]))
        scope_sha256 = self.legacy.readback()["scope"]["scope_sha256"]
        self.assertEqual(
            1,
            len(DecisionCallLedgerV2(v2_root, scope_sha256=scope_sha256).replay()),
        )
        restarted = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True
        )
        self.assertFalse(restarted.shadow_enabled)
        self.assertEqual("OPERATOR_ROLLBACK", restarted.shadow_status()["reason_code"])

    def test_explicit_rollback_persists_across_restart(self):
        v2_root = self.root / "v2"
        adapter = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True
        )
        adapter.disable_shadow("OPERATOR_ROLLBACK")
        restarted = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True
        )
        self.assertFalse(restarted.shadow_enabled)
        self.assertEqual("OPERATOR_ROLLBACK", restarted.shadow_status()["reason_code"])
        self.record_dispatch(restarted)
        status = restarted.shadow_status()
        self.assertIsNone(status["v2_frame_count"])
        self.assertTrue(status["rollback_latched"])
        self.assertTrue(status["rollback_persisted"])

    def test_rollback_latch_wins_over_self_rehashed_enabled_control(self):
        v2_root = self.root / "v2"
        adapter = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True
        )
        adapter.disable_shadow("OPERATOR_ROLLBACK")
        control_path = v2_root / "dual_write_control.json"
        value = json.loads(control_path.read_text(encoding="utf-8"))
        value["status"] = "ENABLED"
        value["reason_code"] = "EXPLICIT_SHADOW_ENABLE"
        material = {key: item for key, item in value.items() if key != "control_sha256"}
        value["control_sha256"] = _sha(material)
        control_path.write_text(json.dumps(value), encoding="utf-8")
        restarted = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True
        )
        status = restarted.shadow_status()
        self.assertFalse(restarted.shadow_enabled)
        self.assertEqual("OPERATOR_ROLLBACK", status["reason_code"])
        self.assertTrue(status["rollback_latched"])
        self.assertTrue(status["rollback_persisted"])

    def test_rollback_latch_failure_is_visible_and_shadow_stays_disabled(self):
        adapter = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=self.root / "v2", shadow_enabled=True
        )
        with mock.patch(
            "src.llm_batch.ledger.decision_ledger_dual_write._atomic_create_once",
            side_effect=OSError("disk"),
        ):
            status = adapter.disable_shadow("OPERATOR_ROLLBACK")
        self.assertFalse(adapter.shadow_enabled)
        self.assertFalse(status["rollback_persisted"])
        self.assertIn("ROLLBACK_LATCH_PERSIST_FAILED_OSERROR", status["reason_code"])
        self.assertEqual(
            "ROLLBACK_LATCH_PERSIST_FAILED_OSERROR",
            status["rollback_persist_error"],
        )

    def test_latch_survives_control_write_failure_and_disables_restart(self):
        v2_root = self.root / "v2"
        adapter = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True
        )
        with mock.patch(
            "src.llm_batch.ledger.decision_ledger_dual_write._atomic",
            side_effect=OSError("control disk"),
        ):
            status = adapter.disable_shadow("OPERATOR_ROLLBACK")
        self.assertTrue(status["rollback_persisted"])
        self.assertFalse(status["control_persisted"])
        self.assertEqual("CONTROL_PERSIST_FAILED_OSERROR", status["control_persist_error"])
        restarted = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True
        )
        self.assertFalse(restarted.shadow_enabled)
        self.assertTrue(restarted.shadow_status()["rollback_persisted"])

    def test_attempt_and_output_identity_are_bound_or_explicitly_limited(self):
        v2_root = self.root / "v2"
        limited = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True
        )
        self.assertEqual(
            "EXPLICIT_NULL_LIMITED", limited.shadow_status()["attempt_binding_status"]
        )
        limited.disable_shadow("TEST_RESET")

        second_root = self.root / "v2-bound"
        bound = DecisionLedgerV2DualWriteAdapter(
            self.legacy,
            v2_root=second_root,
            shadow_enabled=True,
            attempt_run_id="attempt-1",
            output_attempt_sha256="4" * 64,
        )
        self.assertEqual("BOUND", bound.shadow_status()["attempt_binding_status"])
        control = json.loads(
            (second_root / "dual_write_control.json").read_text(encoding="utf-8")
        )
        self.assertEqual("attempt-1", control["binding"]["attempt_run_id"])
        self.assertEqual("4" * 64, control["binding"]["output_attempt_sha256"])

    def test_receipt_failure_marks_evidence_incomplete_across_restart(self):
        v2_root = self.root / "v2"
        adapter = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True
        )
        assert adapter._receipt_wal is not None
        with mock.patch.object(adapter._receipt_wal, "append", side_effect=OSError("receipt")):
            self.record_dispatch(adapter)
        status = adapter.shadow_status()
        self.assertTrue(adapter.shadow_enabled)
        self.assertFalse(status["shadow_evidence_complete"])
        self.assertIn("RECEIPT_APPEND_FAILED_OSERROR", status["shadow_evidence_reason"])
        self.assertFalse(status["actual_metrics_eligible"])
        restarted = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True
        )
        restarted_status = restarted.shadow_status()
        self.assertTrue(restarted.shadow_enabled)
        self.assertFalse(restarted_status["shadow_evidence_complete"])
        self.assertFalse(restarted_status["actual_metrics_eligible"])

    def test_restart_detects_v2_append_without_frame_receipt(self):
        v2_root = self.root / "v2"
        adapter = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True
        )
        frame, created = self.record_dispatch(self.legacy)
        self.assertTrue(created)
        assert adapter._v2 is not None
        adapter._v2.append(frame)

        restarted = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True
        )
        status = restarted.shadow_status()
        self.assertTrue(restarted.shadow_enabled)
        self.assertFalse(status["shadow_evidence_complete"])
        self.assertIn("RECEIPT_COVERAGE_FAILED", status["shadow_evidence_reason"])
        self.assertFalse(status["actual_metrics_eligible"])

    def test_off_helper_does_not_import_or_construct_dual_write_adapter(self):
        sentinel = object()
        with mock.patch("builtins.__import__", side_effect=AssertionError("must not import")):
            result = _maybe_enable_decision_ledger_v2_shadow(
                sentinel,
                shadow_config={"enabled": False},
                v2_root=self.root / "unused",
                attempt_run_id="attempt",
                output_attempt_sha256="5" * 64,
            )
        self.assertIs(sentinel, result)
        off_status = _decision_ledger_v2_off_status()
        self.assertFalse(off_status["actual_metrics_eligible"])
        self.assertFalse(off_status["shadow_evidence_complete"])
        self.assertEqual("OFF_BY_DEFAULT", off_status["shadow_evidence_reason"])
        self.assertEqual(
            {
                "schema_version",
                "shadow_enabled",
                "status",
                "reason_code",
                "legacy_authoritative",
                "public_result_interference",
                "v2_frame_count",
                "v2_index_sha256",
                "actual_metrics",
                "actual_metrics_eligible",
                "rollback_latched",
                "rollback_persisted",
                "control_persisted",
                "rollback_persist_error",
                "control_persist_error",
                "shadow_evidence_complete",
                "shadow_evidence_reason",
                "attempt_binding_status",
            },
            set(off_status),
        )

    def test_tampered_control_fail_closes_shadow_but_legacy_still_writes(self):
        v2_root = self.root / "v2"
        adapter = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True
        )
        control_path = v2_root / "dual_write_control.json"
        value = json.loads(control_path.read_text(encoding="utf-8"))
        value["reason_code"] = "TAMPERED"
        control_path.write_text(json.dumps(value), encoding="utf-8")
        restarted = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True
        )
        self.assertFalse(restarted.shadow_enabled)
        self.assertIn("SETUP_FAILED", restarted.shadow_status()["reason_code"])
        _, created = self.record_dispatch(restarted)
        self.assertTrue(created)
        self.assertEqual(1, len(self.legacy.readback()["frames"]))

    def test_complete_v2_corruption_is_not_repaired_and_legacy_stays_authoritative(self):
        v2_root = self.root / "v2"
        adapter = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True
        )
        self.record_dispatch(adapter)
        segment = next((v2_root / "segments").glob("*.fwal"))
        raw = bytearray(segment.read_bytes())
        raw[-1] ^= 0x01
        segment.write_bytes(raw)
        restarted = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True
        )
        self.assertFalse(restarted.shadow_enabled)
        self.assertIn("SETUP_FAILED", restarted.shadow_status()["reason_code"])
        self.assertEqual(self.legacy.readback(), restarted.readback())

    def test_tracing_client_uses_adapter_without_changing_legacy_frames(self):
        v2_root = self.root / "v2"
        adapter = DecisionLedgerV2DualWriteAdapter(
            self.legacy, v2_root=v2_root, shadow_enabled=True
        )
        client = DecisionTracingLLMClient(
            decision_call_ledger=adapter,
            backend="http",
            endpoint="http://provider",
            model="requested-model",
            stream=False,
            server_type="vllm",
        )
        client.begin_row_attempt("run-a", "row-a", 1, 101)
        with mock.patch.object(LLMClient, "_stream_chat_http", return_value="ok"):
            self.assertEqual("ok", client._stream_chat_http([], tag="gatekeeper"))
        client.seal_row_attempt()
        legacy_frames = self.legacy.readback()["frames"]
        v2_frames = DecisionCallLedgerV2(
            v2_root,
            scope_sha256=self.legacy.readback()["scope"]["scope_sha256"],
        ).replay()
        self.assertEqual(legacy_frames, sorted(v2_frames, key=lambda item: (item["frame_kind"], item["identity_sha256"])))
        self.assertFalse(adapter.shadow_status()["public_result_interference"])


if __name__ == "__main__":
    unittest.main()
