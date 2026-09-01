from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import run_measurement_prereq_canary as canary


class MeasurementPrereqCanaryTests(unittest.TestCase):
    def test_selects_exact_row_and_writes_atomic_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.jsonl"
            source.write_bytes(
                b'{"post_id": 101, "title": "first"}\n'
                b'{"post_id": "202", "title": "second"}\n'
            )
            row, output, digest = canary._write_selected_input(source, root / "out", "202")
            self.assertEqual(row["post_id"], "202")
            self.assertEqual(output.read_bytes(), b'{"post_id": "202", "title": "second"}\n')
            self.assertEqual(digest, canary._sha256_bytes(output.read_bytes()))
            # An exact replay is accepted; a different selection cannot overwrite it.
            canary._write_selected_input(source, root / "out", "202")
            with self.assertRaisesRegex(RuntimeError, "existing immutable artifact differs"):
                canary._write_selected_input(source, root / "out", "101")

    def test_duplicate_post_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.jsonl"
            source.write_text('{"post_id": 7}\n{"post_id": "7"}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exactly one row"):
                canary._select_input_row(source, "7")

    def test_source_validator_uses_effective_parallel_minimum(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            payload = {
                "input_post_count": 1,
                "completed_count": 1,
                "flushed_count": 1,
                "pending_count": 0,
                "failed_count": 0,
                "requested_parallel": 16,
                "effective_parallel": 1,
                "dashboard_enabled": True,
                "terminal_artifacts_finalized": True,
                "publication_commit_count": 1,
                "publication_execution_mode": "NORMAL_PUBLICATION_OWNER",
                "recovery_activation_requested_mode": "OFF",
                "large_run_complete": True,
                "publication_input_snapshot_sha256": "a" * 64,
                "mcp_health_include_search": True,
                "mcp_health_light_mode": False,
                "mcp_health_ok_count": 16,
                "mcp_health_failure_count": 0,
                "runtime_completion_gate": {"status": "GO"},
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = canary._validate_source_manifest(
                path, input_sha256="a" * 64, row_count=1, health_required_ok=16
            )
            self.assertEqual(result["effective_parallel"], 1)

    def test_command_keeps_dashboard_and_requested_parallel(self) -> None:
        command = canary._command(
            python=Path("python"),
            input_path=Path("input.jsonl"),
            output_path=Path("result.json"),
            llm_endpoint="http://llm",
            llm_model="model",
        )
        self.assertIn("16", command)
        self.assertNotIn("--no-dashboard", command)

    def test_main_runs_source_then_after_with_recovery_off(self) -> None:
        source_row = {"post_id": 4242, "title": "target"}
        source_manifest = {
            "publication_scope_id": "scope",
            "publication_release_fingerprint": "release",
            "publication_config_sha256": "config",
            "publication_decision_environment_sha256": "environment",
        }
        observed_manifest = {
            "measurement_gate": {"status": "NO_GO", "reason_codes": ["ROW_MEASUREMENT_MISSING"]},
            "decision_call_ledger_summary": {"reason_codes": ["UNLINKED_ROW_ATTEMPT"]},
        }
        checkpoint = {
            "linked_call_measurement_count": 0,
            "unlinked_call_measurement_count": 1,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.jsonl"
            source.write_text(json.dumps(source_row) + "\n", encoding="utf-8")
            argv = [
                "run_measurement_prereq_canary.py",
                "--input", str(source),
                "--post-id", "4242",
                "--output-root", str(root / "canary"),
                "--active-manifest", str(root / "active.json"),
            ]
            calls: list[tuple[list[str], dict[str, str], Path]] = []

            def fake_run(command: list[str], *, env: dict[str, str], output_path: Path) -> None:
                calls.append((command, env, output_path))

            with patch.object(sys, "argv", argv), patch.object(canary, "_active_endpoint_protection"), patch.object(canary, "_dashboard_health", return_value={"standalone": True}), patch.object(canary, "_run_once", side_effect=fake_run), patch.object(canary, "_validate_source_manifest", return_value=source_manifest), patch.object(canary, "_validate_observation_manifest", return_value=observed_manifest), patch.object(canary, "_validate_observation_checkpoint", return_value=checkpoint):
                canary.main()

            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0][2].name, "source_owner.json")
            self.assertEqual(calls[1][2].name, "observed_after.json")
            self.assertEqual(calls[0][1]["RECOVERY_ACTIVATION_MODE"], "OFF")
            self.assertEqual(calls[1][1]["RECOVERY_ACTIVATION_MODE"], "OFF")
            self.assertEqual(calls[1][1]["PIPELINE_MEASUREMENT_ARM"], "AFTER")
            self.assertEqual(calls[1][1]["PIPELINE_MEASUREMENT_EXECUTION_MODE"], "FRESH_SEMANTIC_OBSERVATION_REQUIRED")
            summary = json.loads((root / "canary" / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["input"]["post_id"], 4242)
            self.assertEqual(summary["measurement_gate"], "NO_GO")
            self.assertEqual(summary["ledger_summary"]["unlinked"], 1)
            self.assertFalse(summary["public_apply"])
            self.assertFalse(summary["production_enable_allowed"])
            self.assertFalse(summary["full_scan_approval"])


if __name__ == "__main__":
    unittest.main()
