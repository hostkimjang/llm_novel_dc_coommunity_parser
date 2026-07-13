from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

from tools.validate_launch_packet_intake import PENDING, validate_intake


def intake(**overrides):
    value = {
        "schema_version": "pipeline_launch_packet_intake_v1",
        "operator_id": "operator-example",
        "policy_owner_state": "PENDING_OWNER_DECISION",
        "source_backed_attestation": "PENDING_EXTERNAL",
        "manifest_path": None,
        "artifact_root": None,
        "requested_parallel": 16,
        "dashboard_required": True,
        "slang_access_mode": "OFF",
        "paired_command_plan": {
            "before_environment": {"PIPELINE_MEASUREMENT_EARLY_ROUTE_MODE": "OFF"},
            "after_environment": {"PIPELINE_MEASUREMENT_EARLY_ROUTE_MODE": "SOURCE_ONLY_V1"},
            "before_command": "python expert_main.py --input frozen.jsonl --output before --parallel 16 --reuse-shards-only --slang-db off --vlm on --ocr on --require-vlm-ocr-for-images",
            "after_command": "python expert_main.py --input frozen.jsonl --output after --parallel 16 --reuse-shards-only --slang-db off --vlm on --ocr on --require-vlm-ocr-for-images",
            "recovery_command": "python tools/recover_expert_run_from_checkpoint.py --manifest <manifest>",
        },
    }
    value.update(overrides)
    return value


class LaunchPacketIntakeTests(unittest.TestCase):
    def test_operator_template_runs_through_the_direct_cli(self):
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "tools" / "validate_launch_packet_intake.py"),
                "--intake",
                str(root / "docs" / "devs" / "templates" / "LAUNCH_PACKET_INTAKE_V1_TEMPLATE.json"),
            ],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(PENDING, payload["status"])
        self.assertFalse(payload["runtime_started"])
        self.assertFalse(payload["writes_performed"])

    def test_pending_external_input_is_not_a_runtime_failure(self):
        result = validate_intake(intake())
        self.assertEqual(PENDING, result["status"])
        self.assertIn("SOURCE_BACKED_PACKET_PENDING", result["pending_reasons"])
        self.assertFalse(result["runtime_started"])
        self.assertFalse(result["writes_performed"])

    def test_parallel_dashboard_and_slang_contract_is_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "parallel 16"):
            validate_intake(intake(requested_parallel=8))
        with self.assertRaisesRegex(ValueError, "dashboard ON"):
            value = intake()
            value["paired_command_plan"]["before_command"] += " --no-dashboard"
            validate_intake(value)

    def test_parallel_substring_and_pair_mismatch_are_rejected(self):
        value = intake()
        value["paired_command_plan"]["before_command"] = value["paired_command_plan"]["before_command"].replace(
            "--parallel 16", "--parallel 160"
        )
        with self.assertRaisesRegex(ValueError, "exact --parallel 16"):
            validate_intake(value)
        value = intake()
        value["paired_command_plan"]["after_command"] = value["paired_command_plan"]["after_command"].replace(
            "frozen.jsonl", "other.jsonl"
        )
        with self.assertRaisesRegex(ValueError, "same frozen input"):
            validate_intake(value)

    def test_environment_modes_and_distinct_outputs_are_required(self):
        value = intake()
        value["paired_command_plan"]["after_environment"] = {
            "PIPELINE_MEASUREMENT_EARLY_ROUTE_MODE": "OFF"
        }
        with self.assertRaisesRegex(ValueError, "SOURCE_ONLY_V1"):
            validate_intake(value)
        value = intake()
        value["paired_command_plan"]["after_command"] = value["paired_command_plan"]["after_command"].replace(
            "--output after", "--output before"
        )
        with self.assertRaisesRegex(ValueError, "distinct outputs"):
            validate_intake(value)

    def test_attestation_without_a_ready_manifest_remains_waiting(self):
        result = validate_intake(intake(
            policy_owner_state="OWNER_APPROVED_POLICY_V3",
            source_backed_attestation="SOURCE_BACKED_CONFIRMED",
        ))
        self.assertEqual(PENDING, result["status"])
        self.assertIn("MANIFEST_OR_ARTIFACT_ROOT_PENDING", result["pending_reasons"])


if __name__ == "__main__":
    unittest.main()
