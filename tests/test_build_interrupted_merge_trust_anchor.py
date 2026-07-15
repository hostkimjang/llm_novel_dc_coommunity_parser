from __future__ import annotations

import copy
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests.test_merge_interrupted_run_results import build_inputs, manifest, plan, result_row
from tools.build_interrupted_merge_trust_anchor import (
    _binding_token_commitment,
    _canonical_hash,
    _immutable_json_artifact,
    _process_state_windows,
    _write_json_exclusive,
    _resume_suspended_windows_process,
    FRESH375_RUNTIME_BINDING_ECHO_IMPLEMENTED,
    WINDOWS_CREATE_NO_WINDOW,
    WINDOWS_CREATE_SUSPENDED,
    build_fresh375_child_environment,
    build_fresh375_final_continuity_verification,
    build_fresh375_supervisor_start_event,
    build_fresh375_trust_anchor,
    build_trust_anchor,
    create_fresh375_run_start_snapshots_and_receipt,
    supervise_fresh375_run,
    validate_fresh375_supervisor_output_preflight,
    validate_fresh375_run_start_binding_receipt,
    validate_fresh375_consumer_trust_bundle,
    validate_fresh375_final_continuity_verification,
    validate_fresh375_supervisor_start_event,
)
from tools.build_adjusted_collateral_blind_packet import (
    FRESH375_CONSUMER_V2_CONTRACT,
    validate_fresh375_v2_consumer_contract,
)
from tools.merge_interrupted_run_results import _sha256


TEST_RUNTIME_RELEASE_FINGERPRINT = "9" * 64


class InterruptedMergeTrustAnchorTest(unittest.TestCase):
    def test_fresh375_runtime_binding_echo_capability_is_enabled(self) -> None:
        self.assertTrue(FRESH375_RUNTIME_BINDING_ECHO_IMPLEMENTED)

    def _fixed_files(self, root: Path) -> tuple[Path, Path, Path, list[dict], list[dict], list[dict]]:
        source_rows = [{"post_id": 1}, {"post_id": 2}, {"post_id": 3}]
        baseline_rows = [{"post_id": 1}, {"post_id": 2}, {"post_id": 3}]
        golden_rows = [{"post_id": 1}]
        source = root / "panel.jsonl"
        baseline = root / "baseline.json"
        golden = root / "golden.json"
        source.write_text(
            "".join(json.dumps(row) + "\n" for row in source_rows),
            encoding="utf-8",
        )
        baseline.write_text(json.dumps(baseline_rows), encoding="utf-8")
        golden.write_text(json.dumps({"rows": golden_rows}), encoding="utf-8")
        (root / "expert_main.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "src").mkdir()
        (root / "src" / "runtime.py").write_text("RUNTIME = True\n", encoding="utf-8")
        return source, baseline, golden, source_rows, baseline_rows, golden_rows

    def _anchor(
        self,
        root: Path,
        *,
        source_manifest_overrides: dict[str, object] | None = None,
    ) -> tuple[dict, dict]:
        inputs = build_inputs()
        inputs["source_manifest"].update(source_manifest_overrides or {})
        residual_partial = [inputs["residual_rows"][0]]
        residual_manifest = inputs["residual_manifest"] | {
            "completed_count": 1,
            "flushed_count": 1,
            "pending_count": 0,
            "next_save_idx": 2,
            "large_run_complete": False,
        }
        source, baseline, golden, source_rows, baseline_rows, golden_rows = self._fixed_files(root)
        recovered_path = root / "recovered.json"
        recovery_summary_path = root / "recovery_summary.json"
        source_checkpoint_path = root / "source_checkpoint.jsonl"
        source_manifest_path = root / "source_manifest.json"
        source_plan_path = root / "source_plan.json"
        residual_input_path = root / "residual_input.jsonl"
        residual_plan_path = root / "residual_plan.json"
        recovered_path.write_text(json.dumps(inputs["recovered_rows"]), encoding="utf-8")
        recovery_summary_path.write_text(
            json.dumps(inputs["recovery_summary"]), encoding="utf-8"
        )
        source_checkpoint_path.write_text(
            "".join(
                json.dumps(row) + "\n" for row in inputs["recovered_checkpoint_rows"]
            ),
            encoding="utf-8",
        )
        source_manifest_path.write_text(
            json.dumps(inputs["source_manifest"]), encoding="utf-8"
        )
        source_plan_path.write_text(json.dumps(inputs["source_plan"]), encoding="utf-8")
        residual_input_rows = [source_rows[0], source_rows[2]]
        residual_input_path.write_text(
            "".join(json.dumps(row) + "\n" for row in residual_input_rows),
            encoding="utf-8",
        )
        residual_plan_path.write_text(
            json.dumps(inputs["residual_plan"]), encoding="utf-8"
        )
        anchor = build_trust_anchor(
            source_rows=source_rows,
            baseline_rows=baseline_rows,
            golden_rows=golden_rows,
            recovered_rows=inputs["recovered_rows"],
            source_checkpoint_rows=inputs["recovered_checkpoint_rows"],
            recovery_summary=inputs["recovery_summary"],
            source_manifest=inputs["source_manifest"],
            source_plan=inputs["source_plan"],
            residual_partial_rows=residual_partial,
            residual_input_rows=residual_input_rows,
            residual_manifest=residual_manifest,
            residual_plan=inputs["residual_plan"],
            source_jsonl=source,
            recovered_result_path=recovered_path,
            recovery_summary_path=recovery_summary_path,
            source_checkpoint_path=source_checkpoint_path,
            source_manifest_path=source_manifest_path,
            source_plan_path=source_plan_path,
            residual_input_path=residual_input_path,
            residual_plan_path=residual_plan_path,
            baseline_result=baseline,
            golden_manifest=golden,
            runtime_root=root,
            expected_source_run_id="source",
            expected_residual_run_id="residual",
            expected_source_count=3,
            expected_recovered_count=1,
            expected_residual_count=2,
            expected_source_flushed_count=1,
            expected_source_pending_count=0,
            expected_golden_count=1,
            expected_panel_sha256=_sha256(source),
            expected_baseline_sha256=_sha256(baseline),
            expected_golden_sha256=_sha256(golden),
            generated_at="2026-07-10T06:00:00",
            allow_untrusted_test_roots=True,
        )
        return anchor, {
            **inputs,
            "residual_partial_rows": residual_partial,
            "residual_partial_manifest": residual_manifest,
            "source_path": source,
            "baseline_path": baseline,
            "golden_path": golden,
            "source_checkpoint_rows": inputs["recovered_checkpoint_rows"],
            "residual_input_rows": residual_input_rows,
            "recovered_path": recovered_path,
            "recovery_summary_path": recovery_summary_path,
            "source_checkpoint_path": source_checkpoint_path,
            "source_manifest_path": source_manifest_path,
            "source_plan_path": source_plan_path,
            "residual_input_path": residual_input_path,
            "residual_plan_path": residual_plan_path,
        }

    def _fresh_plan(
        self,
        root: Path,
        *,
        source: Path,
        live_result: Path,
    ) -> tuple[dict, Path]:
        payload = plan()
        run = payload["planned_runs"][0]
        argv = run["command_argv"]
        argv[2] = str(source.resolve())
        argv[argv.index("--output") + 1] = str(live_result.resolve())
        run["output_json"] = str(live_result.resolve())
        run["manifest_json"] = str(
            live_result.with_name(f"{live_result.stem}_manifest.json").resolve()
        )
        payload["runtime_contract"]["fresh375_binding_echo"] = {
            "required": True,
            "environment_name": "FRESH375_RUN_BINDING_TOKEN",
            "manifest_field": "fresh375_run_binding_token",
            "row_run_meta_field": "fresh375_run_binding_token",
            "echo_scope": "manifest_and_every_result_row",
        }
        for required_env in (
            payload["required_env"],
            payload["runtime_contract"]["required_env"],
            run["required_env"],
        ):
            required_env[
                "RUNTIME_RELEASE_FINGERPRINT_SHA256"
            ] = TEST_RUNTIME_RELEASE_FINGERPRINT
        plan_path = root / "fresh_plan.json"
        plan_path.write_text(json.dumps(payload), encoding="utf-8")
        payload["plan_path"] = str(plan_path.resolve())
        return payload, plan_path

    @staticmethod
    def _make_tree_writable(root: Path) -> None:
        for path in sorted(root.rglob("*"), reverse=True):
            if path.is_file():
                try:
                    path.chmod(stat.S_IREAD | stat.S_IWRITE)
                except OSError:
                    pass

    def _fresh_run_start_context(
        self,
        root: Path,
        *,
        capture: bool = True,
        runtime_fingerprint_echo: str = TEST_RUNTIME_RELEASE_FINGERPRINT,
    ) -> dict[str, object]:
        source, baseline, golden, source_rows, baseline_rows, golden_rows = self._fixed_files(root)
        live_result_path = root / "fresh_live.json"
        live_manifest_path = live_result_path.with_name(
            f"{live_result_path.stem}_manifest.json"
        )
        fresh_plan, fresh_plan_path = self._fresh_plan(
            root,
            source=source,
            live_result=live_result_path,
        )
        anchor = build_fresh375_trust_anchor(
            source_rows=source_rows,
            baseline_rows=baseline_rows,
            golden_rows=golden_rows,
            fresh_plan=fresh_plan,
            fresh_plan_path=fresh_plan_path,
            source_jsonl=source,
            baseline_result=baseline,
            golden_manifest=golden,
            runtime_root=root,
            expected_prompt_version="prompt-v2",
            expected_fresh_run_id=None,
            expected_source_count=3,
            expected_golden_count=1,
            expected_panel_sha256=_sha256(source),
            expected_baseline_sha256=_sha256(baseline),
            expected_golden_sha256=_sha256(golden),
            allow_untrusted_test_roots=True,
        )
        anchor_path = root / "fresh_anchor.json"
        _write_json_exclusive(anchor_path, anchor)
        source.chmod(stat.S_IREAD)
        fresh_plan_path.chmod(stat.S_IREAD)
        partial_rows = [result_row(1, run_id="fresh", prompt_version="prompt-v2")]
        binding_token = "c" * 64
        partial_rows[0]["run_meta"]["fresh375_run_binding_token"] = binding_token
        partial_rows[0]["run_meta"][
            "runtime_release_fingerprint_sha256"
        ] = runtime_fingerprint_echo
        partial_manifest = manifest(
            "fresh",
            3,
            completed=1,
            flushed=1,
            pending=0,
            large_run_complete=False,
        )
        partial_manifest["output_file"] = str(live_result_path.resolve())
        partial_manifest["fresh375_run_binding_token"] = binding_token
        partial_manifest[
            "runtime_release_fingerprint_sha256"
        ] = runtime_fingerprint_echo
        live_result_path.write_text(json.dumps(partial_rows), encoding="utf-8")
        live_manifest_path.write_text(json.dumps(partial_manifest), encoding="utf-8")
        live_checkpoint_path = live_result_path.with_name(
            f"{live_result_path.stem}_checkpoint.jsonl"
        )
        live_pending_path = live_result_path.with_name(
            f"{live_result_path.stem}_pending_snapshot.json"
        )
        live_checkpoint_path.write_text(
            json.dumps(
                {
                    "global_idx": 1,
                    "post_id": 1,
                    "status": "completed",
                    "result": partial_rows[0],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        live_pending_path.write_text("[]\n", encoding="utf-8")
        start_event_path = root / "fresh_start_event.json"
        snapshot_result_path = root / "fresh_start_result_snapshot.json"
        snapshot_manifest_path = root / "fresh_start_manifest_snapshot.json"
        receipt_path = root / "fresh_run_start_receipt.json"
        final_verification_path = root / "fresh_final_continuity.json"
        stdout_log_path = root / "fresh_supervisor.stdout.log"
        stderr_log_path = root / "fresh_supervisor.stderr.log"
        anchor_binding = {
            "path": str(anchor_path.resolve()),
            "sha256": _sha256(anchor_path),
            "anchor_version": anchor["anchor_version"],
            "release_fingerprint_sha256": anchor["release_fingerprint_sha256"],
        }
        _, child_environment_binding = build_fresh375_child_environment(
            anchored_runtime_env=anchor["execution_contract"]["effective_env"],
            binding_token=binding_token,
        )
        start_event = build_fresh375_supervisor_start_event(
            pre_run_anchor_binding=anchor_binding,
            plan_artifact=anchor["immutable_components"]["fresh_plan"],
            execution_contract=anchor["execution_contract"],
            binding_token_commitment=_binding_token_commitment(binding_token),
            child_environment_binding=child_environment_binding,
            process_id=4242,
            process_creation_time_unix=1234.5,
            process_handle_value=777,
            supervisor_process_id=99,
            live_result_path=live_result_path,
            live_manifest_path=live_manifest_path,
            live_checkpoint_path=live_checkpoint_path,
            live_pending_path=live_pending_path,
            snapshot_result_path=snapshot_result_path,
            snapshot_manifest_path=snapshot_manifest_path,
            receipt_path=receipt_path,
            final_verification_path=final_verification_path,
            stdout_log_path=stdout_log_path,
            stderr_log_path=stderr_log_path,
            generated_at="2026-07-10T07:00:00+09:00",
        )
        _write_json_exclusive(start_event_path, start_event)
        process_state_provider = lambda pid: {
            "alive": True,
            "pid": pid,
            "creation_time_unix": 1234.5,
            "handle_value": 777,
            "handle_source": "Popen._handle",
        }
        context: dict[str, object] = {
            "source": source,
            "source_rows": source_rows,
            "baseline": baseline,
            "golden": golden,
            "anchor": anchor,
            "anchor_path": anchor_path,
            "fresh_plan": fresh_plan,
            "fresh_plan_path": fresh_plan_path,
            "partial_rows": partial_rows,
            "live_result_path": live_result_path,
            "partial_manifest": partial_manifest,
            "live_manifest_path": live_manifest_path,
            "live_checkpoint_path": live_checkpoint_path,
            "live_pending_path": live_pending_path,
            "start_event": start_event,
            "start_event_path": start_event_path,
            "snapshot_result_path": snapshot_result_path,
            "snapshot_manifest_path": snapshot_manifest_path,
            "receipt_path": receipt_path,
            "final_verification_path": final_verification_path,
            "stdout_log_path": stdout_log_path,
            "stderr_log_path": stderr_log_path,
            "binding_token": binding_token,
            "runtime_fingerprint_echo": runtime_fingerprint_echo,
            "process_state_provider": process_state_provider,
            "runtime_root": root,
        }
        if capture:
            context["receipt"] = self._capture_fresh_run_start(context)
        return context

    def _capture_fresh_run_start(
        self,
        context: dict[str, object],
        *,
        process_state_provider=None,
        allow_untrusted_test_roots: bool = True,
    ) -> dict:
        return create_fresh375_run_start_snapshots_and_receipt(
            pre_run_anchor=context["anchor"],
            pre_run_anchor_path=context["anchor_path"],
            expected_anchor_sha256=_sha256(context["anchor_path"]),
            supervisor_start_event=context["start_event"],
            supervisor_start_event_path=context["start_event_path"],
            live_result_path=context["live_result_path"],
            live_manifest_path=context["live_manifest_path"],
            live_checkpoint_path=context["live_checkpoint_path"],
            live_pending_path=context["live_pending_path"],
            snapshot_result_path=context["snapshot_result_path"],
            snapshot_manifest_path=context["snapshot_manifest_path"],
            receipt_path=context["receipt_path"],
            source_rows=context["source_rows"],
            source_jsonl=context["source"],
            fresh_plan=context["fresh_plan"],
            fresh_plan_path=context["fresh_plan_path"],
            runtime_root=context["runtime_root"],
            process_state_provider=(
                process_state_provider or context["process_state_provider"]
            ),
            allow_untrusted_test_roots=allow_untrusted_test_roots,
        )

    def test_interrupted_anchor_captures_stable_precompletion_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            anchor, _ = self._anchor(Path(tmp))
            self.assertEqual(anchor["gate"], "GO")
            self.assertEqual(anchor["topology"]["profile"], "interrupted_merge_75_300")
            self.assertTrue(anchor["generated_before_completion"])
            self.assertEqual(anchor["partition_integrity"]["gate"], "GO")
            self.assertEqual(anchor["partition_integrity"]["overlap_count"], 0)
            self.assertIn("source_checkpoint", anchor["immutable_components"])
            self.assertIn("residual_input", anchor["immutable_components"])
            self.assertEqual(anchor["expected_counts"]["residual_rows"], 2)
            self.assertEqual(
                anchor["configuration_hashes"]["stable_runtime_fingerprint_sha256"],
                anchor["stable_runtime_fingerprint_sha256"],
            )
            self.assertTrue(anchor["approval_boundary"]["mutable_residual_manifest_byte_hash_excluded"])

    def test_completed_residual_cannot_create_precompletion_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            anchor, context = self._anchor(root)
            self.assertEqual(anchor["gate"], "GO")
            with self.assertRaisesRegex(ValueError, "pre-completion partial run"):
                build_trust_anchor(
                    source_rows=[{"post_id": 1}, {"post_id": 2}, {"post_id": 3}],
                    baseline_rows=[{"post_id": 1}, {"post_id": 2}, {"post_id": 3}],
                    golden_rows=[{"post_id": 1}],
                    recovered_rows=context["recovered_rows"],
                    source_checkpoint_rows=context["source_checkpoint_rows"],
                    recovery_summary=context["recovery_summary"],
                    source_manifest=context["source_manifest"],
                    source_plan=context["source_plan"],
                    residual_partial_rows=context["residual_rows"],
                    residual_input_rows=context["residual_input_rows"],
                    residual_manifest=context["residual_manifest"],
                    residual_plan=context["residual_plan"],
                    source_jsonl=context["source_path"],
                    recovered_result_path=context["recovered_path"],
                    recovery_summary_path=context["recovery_summary_path"],
                    source_checkpoint_path=context["source_checkpoint_path"],
                    source_manifest_path=context["source_manifest_path"],
                    source_plan_path=context["source_plan_path"],
                    residual_input_path=context["residual_input_path"],
                    residual_plan_path=context["residual_plan_path"],
                    baseline_result=context["baseline_path"],
                    golden_manifest=context["golden_path"],
                    runtime_root=root,
                    expected_source_run_id="source",
                    expected_residual_run_id="residual",
                    expected_source_count=3,
                    expected_recovered_count=1,
                    expected_residual_count=2,
                    expected_source_flushed_count=1,
                    expected_source_pending_count=0,
                    expected_golden_count=1,
                    expected_panel_sha256=_sha256(context["source_path"]),
                    expected_baseline_sha256=_sha256(context["baseline_path"]),
                    expected_golden_sha256=_sha256(context["golden_path"]),
                    allow_untrusted_test_roots=True,
                )

    def test_source_interruption_snapshot_must_match_recovery_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "source interrupted manifest pending_count mismatch"):
                self._anchor(Path(tmp), source_manifest_overrides={"pending_count": 1})

    def test_nonproduction_roots_are_not_accepted_without_test_injection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, baseline, golden, source_rows, baseline_rows, golden_rows = self._fixed_files(root)
            fresh_plan, fresh_plan_path = self._fresh_plan(
                root,
                source=source,
                live_result=root / "fresh_live.json",
            )
            with self.assertRaisesRegex(ValueError, "production trust anchor scope"):
                build_fresh375_trust_anchor(
                    source_rows=source_rows,
                    baseline_rows=baseline_rows,
                    golden_rows=golden_rows,
                    fresh_plan=fresh_plan,
                    fresh_plan_path=fresh_plan_path,
                    source_jsonl=source,
                    baseline_result=baseline,
                    golden_manifest=golden,
                    runtime_root=root,
                    expected_prompt_version="prompt-v2",
                    expected_fresh_run_id=None,
                    expected_source_count=3,
                    expected_golden_count=1,
                    expected_panel_sha256=_sha256(source),
                    expected_baseline_sha256=_sha256(baseline),
                    expected_golden_sha256=_sha256(golden),
                )

    def test_fresh375_profile_is_prerun_and_topology_specific(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            try:
                context = self._fresh_run_start_context(root)
                anchor = context["anchor"]
                receipt = context["receipt"]
                self.assertEqual(anchor["topology"]["profile"], "fresh375")
                self.assertIsNone(anchor["run_ids"]["fresh"])
                self.assertTrue(anchor["generated_before_completion"])
                self.assertEqual(
                    anchor["release_fingerprint_sha256"],
                    anchor["configuration_hashes"]["release_fingerprint_sha256"],
                )
                self.assertEqual(anchor["binding_phase"], "pre_run_release_anchor")
                self.assertEqual(
                    anchor["prompt_version_binding"]["gate"],
                    "PENDING_RUN_START_RECEIPT",
                )
                plan_binding = anchor["immutable_components"]["fresh_plan"]
                self.assertEqual(plan_binding["path"], str(context["fresh_plan_path"].resolve()))
                self.assertEqual(plan_binding["byte_sha256"], _sha256(context["fresh_plan_path"]))
                self.assertIn("canonical_sha256", plan_binding)
                self.assertGreater(plan_binding["size_bytes"], 0)
                execution = anchor["execution_contract"]
                self.assertTrue(Path(execution["executable"]["path"]).is_absolute())
                self.assertEqual(
                    execution["executable"]["byte_sha256"],
                    _sha256(Path(execution["executable"]["path"])),
                )
                self.assertEqual(execution["cwd"], str(root.resolve()))
                self.assertTrue(
                    execution["child_environment_policy"][
                        "wholesale_environment_inheritance_forbidden"
                    ]
                )
                self.assertEqual(
                    receipt["binding_phase"],
                    "supervised_immutable_first_durable_flush",
                )
                self.assertEqual(receipt["prompt_version_binding"]["gate"], "GO")
                self.assertEqual(
                    receipt["pre_run_anchor"]["release_fingerprint_sha256"],
                    anchor["release_fingerprint_sha256"],
                )
                self.assertTrue(receipt["finalized"])
                self.assertFalse(
                    receipt["live_artifact_diagnostics"][
                        "live_partial_bytes_hashed_or_bound"
                    ]
                )
                self.assertNotIn("pre_dispatch_nonce", context["start_event"])
                self.assertEqual(
                    context["start_event"][
                        "pre_dispatch_binding_token_commitment"
                    ],
                    _binding_token_commitment(context["binding_token"]),
                )
                self.assertNotEqual(
                    receipt["snapshot_result"]["path"],
                    receipt["live_artifact_diagnostics"]["result_path"],
                )
                self.assertEqual(
                    validate_fresh375_supervisor_start_event(
                        context["start_event"], event_path=context["start_event_path"]
                    )["gate"],
                    "GO",
                )
                self.assertEqual(
                    validate_fresh375_run_start_binding_receipt(
                        receipt,
                        receipt_path=context["receipt_path"],
                        verify_artifact_bytes=True,
                    )["gate"],
                    "GO",
                )
            finally:
                self._make_tree_writable(root)

    def test_writer_is_exclusive_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "anchor.json"
            receipt = _write_json_exclusive(path, {"gate": "GO"})
            try:
                self.assertTrue(receipt["read_only"])
                self.assertFalse(path.stat().st_mode & stat.S_IWRITE)
                with self.assertRaises(FileExistsError):
                    _write_json_exclusive(path, {"gate": "NO-GO"})
            finally:
                path.chmod(stat.S_IREAD | stat.S_IWRITE)

    def test_fresh_run_start_rejects_empty_and_mismatched_run_ids(self) -> None:
        for case in ("empty_manifest", "mismatched_rows"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                try:
                    context = self._fresh_run_start_context(root, capture=False)
                    if case == "empty_manifest":
                        changed_manifest = copy.deepcopy(context["partial_manifest"])
                        changed_manifest["run_id"] = ""
                        context["live_manifest_path"].write_text(
                            json.dumps(changed_manifest), encoding="utf-8"
                        )
                        with self.assertRaisesRegex(ValueError, "run_id is empty"):
                            self._capture_fresh_run_start(context)
                    else:
                        changed_rows = copy.deepcopy(context["partial_rows"])
                        changed_rows[0]["run_meta"]["run_id"] = "other-run"
                        context["live_result_path"].write_text(
                            json.dumps(changed_rows), encoding="utf-8"
                        )
                        with self.assertRaisesRegex(ValueError, "row/manifest run_id mismatch"):
                            self._capture_fresh_run_start(context)
                finally:
                    self._make_tree_writable(root)

    def test_fresh_run_start_rejects_postcompletion_fabrication(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            try:
                context = self._fresh_run_start_context(root, capture=False)
                complete_manifest = copy.deepcopy(context["partial_manifest"])
                complete_manifest.update(
                    {
                        "completed_count": 3,
                        "flushed_count": 3,
                        "pending_count": 0,
                        "large_run_complete": True,
                    }
                )
                complete_rows = [
                    result_row(post_id, run_id="fresh", prompt_version="prompt-v2")
                    for post_id in (1, 2, 3)
                ]
                context["live_result_path"].write_text(
                    json.dumps(complete_rows), encoding="utf-8"
                )
                context["live_manifest_path"].write_text(
                    json.dumps(complete_manifest), encoding="utf-8"
                )
                with self.assertRaisesRegex(ValueError, "complete or not a durable flush"):
                    self._capture_fresh_run_start(context)
            finally:
                self._make_tree_writable(root)

    def test_production_snapshot_rejects_injected_fake_process_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            try:
                context = self._fresh_run_start_context(root, capture=False)
                with self.assertRaisesRegex(ValueError, "supervisor-owned Popen capability"):
                    self._capture_fresh_run_start(
                        context,
                        process_state_provider=context["process_state_provider"],
                        allow_untrusted_test_roots=False,
                    )
                self.assertFalse(context["snapshot_result_path"].exists())
                self.assertFalse(context["receipt_path"].exists())
            finally:
                self._make_tree_writable(root)

    def test_fresh_run_start_rejects_tampered_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            try:
                context = self._fresh_run_start_context(root)
                receipt = context["receipt"]
                tampered = copy.deepcopy(receipt)
                tampered["run_id"] = "tampered"
                with self.assertRaisesRegex(ValueError, "self-digest mismatch"):
                    validate_fresh375_run_start_binding_receipt(tampered)
                legacy = copy.deepcopy(receipt)
                legacy["schema_version"] = "fresh375-run-start-binding-v1"
                with self.assertRaisesRegex(ValueError, "type/version/finalization invalid"):
                    validate_fresh375_run_start_binding_receipt(legacy)
            finally:
                self._make_tree_writable(root)

    def test_fresh_run_start_receipt_cannot_be_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            try:
                context = self._fresh_run_start_context(root)
                receipt = context["receipt"]
                self.assertEqual(
                    validate_fresh375_run_start_binding_receipt(
                        json.loads(context["receipt_path"].read_text(encoding="utf-8")),
                        receipt_path=context["receipt_path"],
                        verify_artifact_bytes=True,
                    )["gate"],
                    "GO",
                )
                with self.assertRaises(FileExistsError):
                    self._capture_fresh_run_start(context)
            finally:
                self._make_tree_writable(root)

    def test_fresh_run_start_rejects_plan_input_env_and_output_drift(self) -> None:
        for case in ("input", "env", "output"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                try:
                    context = self._fresh_run_start_context(root, capture=False)
                    plan_path = context["fresh_plan_path"]
                    plan_path.chmod(stat.S_IREAD | stat.S_IWRITE)
                    changed = {
                        key: value
                        for key, value in copy.deepcopy(context["fresh_plan"]).items()
                        if key != "plan_path"
                    }
                    run = changed["planned_runs"][0]
                    if case == "input":
                        run["command_argv"][2] = str((root / "other.jsonl").resolve())
                    elif case == "env":
                        changed["required_env"]["MCP_HEALTH_REQUIRED_OK"] = "15"
                    else:
                        other = str((root / "other_output.json").resolve())
                        run["command_argv"][run["command_argv"].index("--output") + 1] = other
                        run["output_json"] = other
                        run["manifest_json"] = str((root / "other_output_manifest.json").resolve())
                    plan_path.write_text(json.dumps(changed), encoding="utf-8")
                    plan_path.chmod(stat.S_IREAD)
                    changed["plan_path"] = str(plan_path.resolve())
                    context["fresh_plan"] = changed
                    with self.assertRaisesRegex(
                        ValueError,
                        "plan bytes/canonical payload changed",
                    ):
                        self._capture_fresh_run_start(context)
                    self.assertFalse(context["snapshot_result_path"].exists())
                    self.assertFalse(context["receipt_path"].exists())
                finally:
                    self._make_tree_writable(root)

    def test_fresh_start_event_rejects_snapshot_live_path_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            try:
                context = self._fresh_run_start_context(root, capture=False)
                anchor = context["anchor"]
                with self.assertRaisesRegex(ValueError, "must be distinct"):
                    build_fresh375_supervisor_start_event(
                        pre_run_anchor_binding=context["start_event"]["pre_run_anchor"],
                        plan_artifact=anchor["immutable_components"]["fresh_plan"],
                        execution_contract=anchor["execution_contract"],
                        binding_token_commitment=context["start_event"][
                            "pre_dispatch_binding_token_commitment"
                        ],
                        child_environment_binding=context["start_event"][
                            "execution_binding"
                        ]["child_environment"],
                        process_id=4242,
                        process_creation_time_unix=1234.5,
                        process_handle_value=777,
                        supervisor_process_id=99,
                        live_result_path=context["live_result_path"],
                        live_manifest_path=context["live_manifest_path"],
                        live_checkpoint_path=context["live_checkpoint_path"],
                        live_pending_path=context["live_pending_path"],
                        snapshot_result_path=context["live_result_path"],
                        snapshot_manifest_path=context["snapshot_manifest_path"],
                        receipt_path=context["receipt_path"],
                        final_verification_path=context["final_verification_path"],
                        stdout_log_path=context["stdout_log_path"],
                        stderr_log_path=context["stderr_log_path"],
                    )
            finally:
                self._make_tree_writable(root)

    def test_child_environment_is_minimal_and_drops_unplanned_semantic_env(self) -> None:
        child, binding = build_fresh375_child_environment(
            anchored_runtime_env={"MCP_HEALTH_INCLUDE_SEARCH": "1"},
            source_environment={
                "SYSTEMROOT": r"C:\Windows",
                "PATH": r"C:\Windows\System32",
                "UNPLANNED_SEMANTIC_OVERRIDE": "must-not-leak",
                "OPENAI_API_KEY": "must-not-leak",
            },
            binding_token="d" * 64,
        )
        self.assertEqual(
            set(child),
            {
                "SYSTEMROOT",
                "PATH",
                "MCP_HEALTH_INCLUDE_SEARCH",
                "FRESH375_RUN_BINDING_TOKEN",
            },
        )
        self.assertNotIn("UNPLANNED_SEMANTIC_OVERRIDE", child)
        self.assertNotIn("OPENAI_API_KEY", child)
        self.assertTrue(binding["values_redacted"])
        self.assertNotIn("must-not-leak", json.dumps(binding))
        self.assertEqual(
            binding["value_sha256"]["FRESH375_RUN_BINDING_TOKEN"],
            _binding_token_commitment("d" * 64),
        )

    def test_allowlisted_os_environment_drift_invalidates_anchor_before_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            try:
                context = self._fresh_run_start_context(root, capture=False)
                with patch.dict(os.environ, {"TEMP": str(root / "drifted-temp")}):
                    with self.assertRaisesRegex(
                        ValueError, "execution contract changed"
                    ):
                        self._capture_fresh_run_start(context)
                self.assertFalse(context["snapshot_result_path"].exists())
                self.assertFalse(context["receipt_path"].exists())
            finally:
                self._make_tree_writable(root)

    def test_missing_or_drifted_binding_token_echo_fails_before_snapshot(self) -> None:
        for case in ("manifest_missing", "row_drift"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                try:
                    context = self._fresh_run_start_context(root, capture=False)
                    if case == "manifest_missing":
                        changed_manifest = copy.deepcopy(context["partial_manifest"])
                        changed_manifest.pop("fresh375_run_binding_token")
                        context["live_manifest_path"].write_text(
                            json.dumps(changed_manifest), encoding="utf-8"
                        )
                    else:
                        changed_rows = copy.deepcopy(context["partial_rows"])
                        changed_rows[0]["run_meta"][
                            "fresh375_run_binding_token"
                        ] = "e" * 64
                        context["live_result_path"].write_text(
                            json.dumps(changed_rows), encoding="utf-8"
                        )
                    with self.assertRaisesRegex(ValueError, "binding-token"):
                        self._capture_fresh_run_start(context)
                    self.assertFalse(context["snapshot_result_path"].exists())
                    self.assertFalse(context["receipt_path"].exists())
                finally:
                    self._make_tree_writable(root)

    def test_supervisor_output_preflight_rejects_any_canonical_collision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            try:
                context = self._fresh_run_start_context(root, capture=False)
                with self.assertRaisesRegex(ValueError, "canonical paths collide"):
                    validate_fresh375_supervisor_output_preflight(
                        immutable_input_paths=[
                            context["anchor_path"],
                            context["fresh_plan_path"],
                            context["source"],
                        ],
                        execution_contract=context["anchor"]["execution_contract"],
                        live_result_path=context["live_result_path"],
                        live_manifest_path=context["live_manifest_path"],
                        live_checkpoint_path=context["live_checkpoint_path"],
                        live_pending_path=context["live_pending_path"],
                        supervisor_start_event_path=context["start_event_path"],
                        snapshot_result_path=context["snapshot_result_path"],
                        snapshot_manifest_path=context["snapshot_manifest_path"],
                        receipt_path=context["receipt_path"],
                        final_verification_path=context["final_verification_path"],
                        stdout_log_path=context["receipt_path"],
                        stderr_log_path=context["stderr_log_path"],
                    )
            finally:
                self._make_tree_writable(root)

    def test_fresh_run_start_rejects_pid_creation_mismatch_before_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            try:
                context = self._fresh_run_start_context(root, capture=False)
                mismatched_provider = lambda pid: {
                    "alive": True,
                    "pid": pid,
                    "creation_time_unix": 9999.0,
                    "handle_value": 777,
                    "handle_source": "Popen._handle",
                }
                with self.assertRaisesRegex(ValueError, "not the bound live Popen handle"):
                    self._capture_fresh_run_start(
                        context,
                        process_state_provider=mismatched_provider,
                    )
                self.assertFalse(context["snapshot_result_path"].exists())
                self.assertFalse(context["receipt_path"].exists())
            finally:
                self._make_tree_writable(root)

    def test_fresh_final_completion_preserves_snapshot_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            try:
                context = self._fresh_run_start_context(root)
                final_rows = [
                    copy.deepcopy(context["partial_rows"][0]),
                    result_row(2, run_id="fresh", prompt_version="prompt-v2"),
                    result_row(3, run_id="fresh", prompt_version="prompt-v2"),
                ]
                for row in final_rows:
                    row["run_meta"]["fresh375_run_binding_token"] = context[
                        "binding_token"
                    ]
                    row["run_meta"][
                        "runtime_release_fingerprint_sha256"
                    ] = context["runtime_fingerprint_echo"]
                final_manifest = manifest("fresh", 3)
                final_manifest["output_file"] = str(context["live_result_path"].resolve())
                final_manifest["fresh375_run_binding_token"] = context["binding_token"]
                final_manifest[
                    "runtime_release_fingerprint_sha256"
                ] = context["runtime_fingerprint_echo"]
                final_checkpoint_rows = [
                    {
                        "global_idx": index,
                        "post_id": row["post_id"],
                        "status": "completed",
                        "result": row,
                    }
                    for index, row in enumerate(final_rows, start=1)
                ]
                context["live_result_path"].write_text(
                    json.dumps(final_rows), encoding="utf-8"
                )
                context["live_manifest_path"].write_text(
                    json.dumps(final_manifest), encoding="utf-8"
                )
                context["live_checkpoint_path"].write_text(
                    "".join(json.dumps(row) + "\n" for row in final_checkpoint_rows),
                    encoding="utf-8",
                )
                context["live_pending_path"].write_text("[]\n", encoding="utf-8")
                for path in (
                    context["live_result_path"],
                    context["live_manifest_path"],
                    context["live_checkpoint_path"],
                    context["live_pending_path"],
                ):
                    path.chmod(stat.S_IREAD)
                verification = build_fresh375_final_continuity_verification(
                    receipt=context["receipt"],
                    receipt_path=context["receipt_path"],
                    final_rows=final_rows,
                    final_result_path=context["live_result_path"],
                    final_manifest=final_manifest,
                    final_manifest_path=context["live_manifest_path"],
                    final_checkpoint_rows=final_checkpoint_rows,
                    final_checkpoint_path=context["live_checkpoint_path"],
                    final_pending=[],
                    final_pending_path=context["live_pending_path"],
                    source_rows=context["source_rows"],
                    process_exit_code=0,
                    generated_at="2026-07-10T08:00:00+09:00",
                )
                self.assertEqual(verification["gate"], "GO")
                self.assertTrue(verification["continuity"]["exact_prefix_preserved"])
                self.assertEqual(
                    verification["finalization"]["marker"],
                    "FRESH375_FINAL_ARTIFACT_SET_COMMITTED_LAST",
                )
                self.assertEqual(
                    set(verification["final_artifacts"]),
                    {"result", "manifest", "checkpoint", "pending"},
                )
                for name, path in {
                    "result": context["live_result_path"],
                    "manifest": context["live_manifest_path"],
                    "checkpoint": context["live_checkpoint_path"],
                    "pending": context["live_pending_path"],
                }.items():
                    self.assertEqual(
                        verification["final_artifacts"][name]["byte_sha256"],
                        _sha256(path),
                    )
                    self.assertFalse(path.stat().st_mode & stat.S_IWRITE)
                _write_json_exclusive(
                    context["final_verification_path"], verification
                )
                self.assertEqual(
                    validate_fresh375_final_continuity_verification(
                        verification=verification,
                        verification_path=context["final_verification_path"],
                        source_rows=context["source_rows"],
                    )["gate"],
                    "GO",
                )
                consumer = validate_fresh375_consumer_trust_bundle(
                    pre_run_anchor_path=context["anchor_path"],
                    compiled_anchor_path=context["anchor_path"],
                    compiled_anchor_sha256=_sha256(context["anchor_path"]),
                    supervisor_start_event_path=context["start_event_path"],
                    run_start_receipt_path=context["receipt_path"],
                    final_continuity_path=context["final_verification_path"],
                    source_jsonl=context["source"],
                )
                self.assertEqual(consumer["schema"], "fresh375-consumer-trust-bundle-v2")
                adjusted_consumer = validate_fresh375_v2_consumer_contract(
                    pre_run_anchor_path=context["anchor_path"],
                    compiled_anchor_path=context["anchor_path"],
                    compiled_anchor_sha256=_sha256(context["anchor_path"]),
                    supervisor_start_event_path=context["start_event_path"],
                    snapshot_result_path=context["snapshot_result_path"],
                    snapshot_manifest_path=context["snapshot_manifest_path"],
                    run_start_receipt_path=context["receipt_path"],
                    final_continuity_path=context["final_verification_path"],
                    source_jsonl=context["source"],
                    final_result_path=context["live_result_path"],
                    final_manifest_path=context["live_manifest_path"],
                    final_checkpoint_path=context["live_checkpoint_path"],
                    final_pending_path=context["live_pending_path"],
                )
                self.assertEqual(
                    adjusted_consumer["consumer_contract"],
                    FRESH375_CONSUMER_V2_CONTRACT,
                )
                self.assertEqual(
                    adjusted_consumer["current_runtime_fingerprint_sha256"],
                    TEST_RUNTIME_RELEASE_FINGERPRINT,
                )
                with self.assertRaisesRegex(ValueError, "start-event path mismatch"):
                    validate_fresh375_v2_consumer_contract(
                        pre_run_anchor_path=context["anchor_path"],
                        compiled_anchor_path=context["anchor_path"],
                        compiled_anchor_sha256=_sha256(context["anchor_path"]),
                        supervisor_start_event_path=context["start_event_path"],
                        snapshot_result_path=context["live_result_path"],
                        snapshot_manifest_path=context["snapshot_manifest_path"],
                        run_start_receipt_path=context["receipt_path"],
                        final_continuity_path=context["final_verification_path"],
                        source_jsonl=context["source"],
                        final_result_path=context["live_result_path"],
                        final_manifest_path=context["live_manifest_path"],
                        final_checkpoint_path=context["live_checkpoint_path"],
                        final_pending_path=context["live_pending_path"],
                    )
                with self.assertRaisesRegex(ValueError, "sha256 pin mismatch"):
                    validate_fresh375_consumer_trust_bundle(
                        pre_run_anchor_path=context["anchor_path"],
                        compiled_anchor_path=context["anchor_path"],
                        compiled_anchor_sha256="0" * 64,
                        supervisor_start_event_path=context["start_event_path"],
                        run_start_receipt_path=context["receipt_path"],
                        final_continuity_path=context["final_verification_path"],
                        source_jsonl=context["source"],
                    )
                tampered_rows = copy.deepcopy(final_rows)
                tampered_rows[0]["title"] = "tampered-after-receipt"
                context["live_result_path"].chmod(stat.S_IREAD | stat.S_IWRITE)
                context["live_result_path"].write_text(
                    json.dumps(tampered_rows), encoding="utf-8"
                )
                context["live_result_path"].chmod(stat.S_IREAD)
                tampered_checkpoint_rows = copy.deepcopy(final_checkpoint_rows)
                tampered_checkpoint_rows[0]["result"] = tampered_rows[0]
                context["live_checkpoint_path"].chmod(
                    stat.S_IREAD | stat.S_IWRITE
                )
                context["live_checkpoint_path"].write_text(
                    "".join(
                        json.dumps(row) + "\n" for row in tampered_checkpoint_rows
                    ),
                    encoding="utf-8",
                )
                context["live_checkpoint_path"].chmod(stat.S_IREAD)
                with self.assertRaisesRegex(ValueError, "preserve immutable snapshot prefix"):
                    build_fresh375_final_continuity_verification(
                        receipt=context["receipt"],
                        receipt_path=context["receipt_path"],
                        final_rows=tampered_rows,
                        final_result_path=context["live_result_path"],
                        final_manifest=final_manifest,
                        final_manifest_path=context["live_manifest_path"],
                        final_checkpoint_rows=tampered_checkpoint_rows,
                        final_checkpoint_path=context["live_checkpoint_path"],
                        final_pending=[],
                        final_pending_path=context["live_pending_path"],
                        source_rows=context["source_rows"],
                        process_exit_code=0,
                    )
            finally:
                self._make_tree_writable(root)

    def test_adjusted_consumer_rejects_internally_bound_wrong_runtime_fingerprint_echo(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            try:
                wrong_fingerprint = "8" * 64
                context = self._fresh_run_start_context(
                    root,
                    runtime_fingerprint_echo=wrong_fingerprint,
                )
                final_rows = [
                    copy.deepcopy(context["partial_rows"][0]),
                    result_row(2, run_id="fresh", prompt_version="prompt-v2"),
                    result_row(3, run_id="fresh", prompt_version="prompt-v2"),
                ]
                for row in final_rows:
                    row["run_meta"]["fresh375_run_binding_token"] = context[
                        "binding_token"
                    ]
                    row["run_meta"][
                        "runtime_release_fingerprint_sha256"
                    ] = wrong_fingerprint
                final_manifest = manifest("fresh", 3)
                final_manifest["output_file"] = str(
                    context["live_result_path"].resolve()
                )
                final_manifest["fresh375_run_binding_token"] = context[
                    "binding_token"
                ]
                final_manifest[
                    "runtime_release_fingerprint_sha256"
                ] = wrong_fingerprint
                checkpoint_rows = [
                    {
                        "global_idx": index,
                        "post_id": row["post_id"],
                        "status": "completed",
                        "result": row,
                    }
                    for index, row in enumerate(final_rows, start=1)
                ]
                context["live_result_path"].write_text(
                    json.dumps(final_rows), encoding="utf-8"
                )
                context["live_manifest_path"].write_text(
                    json.dumps(final_manifest), encoding="utf-8"
                )
                context["live_checkpoint_path"].write_text(
                    "".join(json.dumps(row) + "\n" for row in checkpoint_rows),
                    encoding="utf-8",
                )
                context["live_pending_path"].write_text("[]\n", encoding="utf-8")
                for path in (
                    context["live_result_path"],
                    context["live_manifest_path"],
                    context["live_checkpoint_path"],
                    context["live_pending_path"],
                ):
                    path.chmod(stat.S_IREAD)
                continuity = build_fresh375_final_continuity_verification(
                    receipt=context["receipt"],
                    receipt_path=context["receipt_path"],
                    final_rows=final_rows,
                    final_result_path=context["live_result_path"],
                    final_manifest=final_manifest,
                    final_manifest_path=context["live_manifest_path"],
                    final_checkpoint_rows=checkpoint_rows,
                    final_checkpoint_path=context["live_checkpoint_path"],
                    final_pending=[],
                    final_pending_path=context["live_pending_path"],
                    source_rows=context["source_rows"],
                    process_exit_code=0,
                )
                _write_json_exclusive(context["final_verification_path"], continuity)

                with self.assertRaisesRegex(
                    ValueError,
                    "current runtime fingerprint echo mismatch",
                ):
                    validate_fresh375_v2_consumer_contract(
                        pre_run_anchor_path=context["anchor_path"],
                        compiled_anchor_path=context["anchor_path"],
                        compiled_anchor_sha256=_sha256(context["anchor_path"]),
                        supervisor_start_event_path=context["start_event_path"],
                        snapshot_result_path=context["snapshot_result_path"],
                        snapshot_manifest_path=context["snapshot_manifest_path"],
                        run_start_receipt_path=context["receipt_path"],
                        final_continuity_path=context["final_verification_path"],
                        source_jsonl=context["source"],
                        final_result_path=context["live_result_path"],
                        final_manifest_path=context["live_manifest_path"],
                        final_checkpoint_path=context["live_checkpoint_path"],
                        final_pending_path=context["live_pending_path"],
                    )
            finally:
                self._make_tree_writable(root)

    def test_adjusted_consumer_rejects_self_resealed_execution_contract_drift(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            try:
                context = self._fresh_run_start_context(root)
                event = copy.deepcopy(context["start_event"])
                event["execution_binding"]["runtime_contract"]["slang_db"] = "on"
                event.pop("start_event_payload_sha256")
                event["start_event_payload_sha256"] = _canonical_hash(event)
                context["start_event_path"].chmod(stat.S_IREAD | stat.S_IWRITE)
                context["start_event_path"].write_text(
                    json.dumps(event), encoding="utf-8"
                )
                context["start_event_path"].chmod(stat.S_IREAD)

                receipt = copy.deepcopy(context["receipt"])
                receipt["supervisor_start_event"] = _immutable_json_artifact(
                    path=context["start_event_path"],
                    payload=event,
                )
                receipt["process_continuity"][
                    "start_event_payload_sha256"
                ] = event["start_event_payload_sha256"]
                receipt.pop("receipt_payload_sha256")
                receipt["receipt_payload_sha256"] = _canonical_hash(receipt)
                context["receipt_path"].chmod(stat.S_IREAD | stat.S_IWRITE)
                context["receipt_path"].write_text(
                    json.dumps(receipt), encoding="utf-8"
                )
                context["receipt_path"].chmod(stat.S_IREAD)

                final_rows = [
                    copy.deepcopy(context["partial_rows"][0]),
                    result_row(2, run_id="fresh", prompt_version="prompt-v2"),
                    result_row(3, run_id="fresh", prompt_version="prompt-v2"),
                ]
                for row in final_rows:
                    row["run_meta"]["fresh375_run_binding_token"] = context[
                        "binding_token"
                    ]
                    row["run_meta"][
                        "runtime_release_fingerprint_sha256"
                    ] = TEST_RUNTIME_RELEASE_FINGERPRINT
                final_manifest = manifest("fresh", 3)
                final_manifest["output_file"] = str(
                    context["live_result_path"].resolve()
                )
                final_manifest["fresh375_run_binding_token"] = context[
                    "binding_token"
                ]
                final_manifest[
                    "runtime_release_fingerprint_sha256"
                ] = TEST_RUNTIME_RELEASE_FINGERPRINT
                checkpoint_rows = [
                    {
                        "global_idx": index,
                        "post_id": row["post_id"],
                        "status": "completed",
                        "result": row,
                    }
                    for index, row in enumerate(final_rows, start=1)
                ]
                context["live_result_path"].write_text(
                    json.dumps(final_rows), encoding="utf-8"
                )
                context["live_manifest_path"].write_text(
                    json.dumps(final_manifest), encoding="utf-8"
                )
                context["live_checkpoint_path"].write_text(
                    "".join(json.dumps(row) + "\n" for row in checkpoint_rows),
                    encoding="utf-8",
                )
                context["live_pending_path"].write_text("[]\n", encoding="utf-8")
                for path in (
                    context["live_result_path"],
                    context["live_manifest_path"],
                    context["live_checkpoint_path"],
                    context["live_pending_path"],
                ):
                    path.chmod(stat.S_IREAD)
                continuity = build_fresh375_final_continuity_verification(
                    receipt=receipt,
                    receipt_path=context["receipt_path"],
                    final_rows=final_rows,
                    final_result_path=context["live_result_path"],
                    final_manifest=final_manifest,
                    final_manifest_path=context["live_manifest_path"],
                    final_checkpoint_rows=checkpoint_rows,
                    final_checkpoint_path=context["live_checkpoint_path"],
                    final_pending=[],
                    final_pending_path=context["live_pending_path"],
                    source_rows=context["source_rows"],
                    process_exit_code=0,
                )
                _write_json_exclusive(context["final_verification_path"], continuity)
                self.assertEqual(
                    validate_fresh375_consumer_trust_bundle(
                        pre_run_anchor_path=context["anchor_path"],
                        compiled_anchor_path=context["anchor_path"],
                        compiled_anchor_sha256=_sha256(context["anchor_path"]),
                        supervisor_start_event_path=context["start_event_path"],
                        run_start_receipt_path=context["receipt_path"],
                        final_continuity_path=context["final_verification_path"],
                        source_jsonl=context["source"],
                    )["gate"],
                    "GO",
                )
                with self.assertRaisesRegex(
                    ValueError,
                    "command/model/search execution contract drift",
                ):
                    validate_fresh375_v2_consumer_contract(
                        pre_run_anchor_path=context["anchor_path"],
                        compiled_anchor_path=context["anchor_path"],
                        compiled_anchor_sha256=_sha256(context["anchor_path"]),
                        supervisor_start_event_path=context["start_event_path"],
                        snapshot_result_path=context["snapshot_result_path"],
                        snapshot_manifest_path=context["snapshot_manifest_path"],
                        run_start_receipt_path=context["receipt_path"],
                        final_continuity_path=context["final_verification_path"],
                        source_jsonl=context["source"],
                        final_result_path=context["live_result_path"],
                        final_manifest_path=context["live_manifest_path"],
                        final_checkpoint_path=context["live_checkpoint_path"],
                        final_pending_path=context["live_pending_path"],
                    )
            finally:
                self._make_tree_writable(root)

    def test_windows_resume_uses_ntresumeprocess_on_bound_handle(self) -> None:
        ntdll = MagicMock()
        ntdll.NtResumeProcess.return_value = 0
        process = SimpleNamespace(_handle=1234)
        with patch(
            "tools.build_interrupted_merge_trust_anchor.os",
            SimpleNamespace(name="nt"),
        ), patch("ctypes.WinDLL", return_value=ntdll) as win_dll:
            _resume_suspended_windows_process(process)
        win_dll.assert_called_once_with("ntdll")
        called_handle = ntdll.NtResumeProcess.call_args.args[0]
        self.assertEqual(called_handle.value, 1234)

    @unittest.skipUnless(os.name == "nt", "Windows suspended-process integration")
    def test_real_windows_child_cannot_run_before_start_event_then_resumes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(WINDOWS_CREATE_SUSPENDED, 0x00000004)
            self.assertEqual(WINDOWS_CREATE_NO_WINDOW, 0x08000000)
            marker = root / "child_ran.txt"
            start_event = root / "start_event.json"
            process: subprocess.Popen | None = None
            resumed = False
            try:
                command = [
                    sys.executable,
                    "-c",
                    (
                        "from pathlib import Path; import sys; "
                        "Path(sys.argv[1]).write_text('ran', encoding='utf-8')"
                    ),
                    str(marker),
                ]
                process = subprocess.Popen(
                    command,
                    cwd=root,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=(
                        WINDOWS_CREATE_NO_WINDOW | WINDOWS_CREATE_SUSPENDED
                    ),
                )
                process_handle = int(process._handle)  # type: ignore[attr-defined]
                state = _process_state_windows(
                    process.pid,
                    process_handle=process_handle,
                )
                self.assertTrue(state["alive"])
                self.assertEqual(state["handle_value"], process_handle)
                self.assertEqual(state["handle_source"], "Popen._handle")
                time.sleep(0.15)
                self.assertFalse(marker.exists())
                _write_json_exclusive(
                    start_event,
                    {
                        "pid": process.pid,
                        "creation_time_unix": state["creation_time_unix"],
                        "create_suspended_flag": WINDOWS_CREATE_SUSPENDED,
                    },
                )
                self.assertTrue(start_event.exists())
                _resume_suspended_windows_process(process)
                resumed = True
                self.assertEqual(process.wait(timeout=10), 0)
                self.assertEqual(marker.read_text(encoding="utf-8"), "ran")
            finally:
                if process is not None and process.poll() is None:
                    if not resumed:
                        _resume_suspended_windows_process(process)
                    process.kill()
                    process.wait(timeout=10)
                self._make_tree_writable(root)

    @unittest.skipUnless(os.name == "nt", "Windows OpenProcess integration")
    def test_real_windows_openprocess_state_query_uses_typed_handle(self) -> None:
        state = _process_state_windows(os.getpid())
        self.assertTrue(state["alive"])
        self.assertEqual(state["pid"], os.getpid())
        self.assertEqual(state["handle_source"], "OpenProcess")
        self.assertGreater(state["handle_value"], 0)
        self.assertGreater(state["creation_time_unix"], 0)

    def test_supervisor_fails_closed_outside_windows_before_file_access(self) -> None:
        missing = Path("must-not-be-read.json")
        with patch(
            "tools.build_interrupted_merge_trust_anchor.os",
            SimpleNamespace(name="posix"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Windows-only"):
                supervise_fresh375_run(
                    pre_run_anchor_path=missing,
                    expected_anchor_sha256="0" * 64,
                    fresh_plan_path=missing,
                    source_jsonl=missing,
                    runtime_root=Path.cwd(),
                    live_result_path=missing,
                    live_manifest_path=missing,
                    live_checkpoint_path=missing,
                    live_pending_path=missing,
                    supervisor_start_event_path=missing,
                    snapshot_result_path=missing,
                    snapshot_manifest_path=missing,
                    receipt_path=missing,
                    final_verification_path=missing,
                    log_dir=missing,
                )

    @unittest.skipUnless(os.name == "nt", "Windows runtime-wiring gate")
    def test_supervisor_passes_runtime_echo_capability_gate_before_anchor_read(self) -> None:
        missing = Path("must-not-be-read.json")
        with self.assertRaises(FileNotFoundError):
            supervise_fresh375_run(
                pre_run_anchor_path=missing,
                expected_anchor_sha256="0" * 64,
                fresh_plan_path=missing,
                source_jsonl=missing,
                runtime_root=Path.cwd(),
                live_result_path=missing,
                live_manifest_path=missing,
                live_checkpoint_path=missing,
                live_pending_path=missing,
                supervisor_start_event_path=missing,
                snapshot_result_path=missing,
                snapshot_manifest_path=missing,
                receipt_path=missing,
                final_verification_path=missing,
                log_dir=missing,
            )

    def test_direct_entrypoint_help_bootstraps_repo_import(self) -> None:
        tool = Path(__file__).resolve().parents[1] / "tools" / "build_interrupted_merge_trust_anchor.py"
        completed = subprocess.run(
            [sys.executable, str(tool), "--help"],
            cwd=tool.parents[1],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--profile", completed.stdout)
        self.assertIn("fresh375_supervisor", completed.stdout)


if __name__ == "__main__":
    unittest.main()
