from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.run_research_local_benchmark_workflow import (
    WorkflowError,
    _partition_summary,
    build_runner_command,
    parse_dashboard_url,
    render_workflow_report,
    seal_workflow_manifest,
)
from src.llm_batch.grounding.research_local_benchmark import sha256_value


class ResearchBenchmarkWorkflowTests(unittest.TestCase):
    def test_partition_summary_carries_child_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "challenge.jsonl"
            metrics_path = root / "metrics.json"
            input_path.write_text("{}\n", encoding="utf-8")
            metrics_path.write_text(
                json.dumps(
                    {
                        "arms": {
                            "local_llm": {
                                "denominator": 4,
                                "correct": 1,
                                "accuracy": 0.25,
                                "terminal_status_counts": {"RESOLVED": 3, "ABSTAIN": 1},
                                "case_type_counts": {"CANDIDATE_MISS": 1},
                                "expected_action_counts": {"RESOLVED": 2, "ABSTAIN": 1, "NIL": 1},
                                "failure_stage_counts": {"CANDIDATE_RECALL_MISS": 1},
                                "candidate_recall": {
                                    "recall_at_5": {"numerator": 2, "denominator": 3},
                                },
                                "conditional_selection": {"numerator": 0, "denominator": 1},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            summary = _partition_summary(
                name="challenge",
                input_path=input_path,
                output_dir=root,
                manifest={
                    "artifacts": {"metrics": {"path": str(metrics_path)}},
                    "manifest_sha256": "manifest",
                    "benchmark_input_count": 4,
                    "requested_parallel": 16,
                    "effective_parallel": 4,
                    "completed_count": 16,
                    "terminal_status_counts": {"RESOLVED": 3, "ABSTAIN": 1},
                    "dashboard": {"status": "CONNECTED"},
                },
            )
        diagnostics = summary["arms"]["local_llm"]["diagnostics"]
        self.assertEqual({"CANDIDATE_MISS": 1}, diagnostics["case_type_counts"])
        self.assertEqual({"CANDIDATE_RECALL_MISS": 1}, diagnostics["failure_stage_counts"])
        self.assertEqual({"numerator": 2, "denominator": 3}, diagnostics["candidate_recall"]["recall_at_5"])
        self.assertEqual({"numerator": 0, "denominator": 1}, diagnostics["conditional_selection"])

    def test_dashboard_url_requires_loopback(self) -> None:
        self.assertEqual(("127.0.0.1", 8765), parse_dashboard_url("http://127.0.0.1:8765"))
        with self.assertRaises(WorkflowError):
            parse_dashboard_url("https://example.com:8765")
        with self.assertRaises(WorkflowError):
            parse_dashboard_url("http://127.0.0.1:8765/api")

    def test_runner_command_keeps_requested_parallel_sixteen(self) -> None:
        command = build_runner_command(
            input_path=Path("tests/fixtures/research_local_benchmark_v1.jsonl"),
            output_dir=Path("out/research/workflow/baseline"),
            dashboard_url="http://127.0.0.1:8765",
        )
        self.assertIn("--parallel", command)
        self.assertEqual("16", command[command.index("--parallel") + 1])
        self.assertIn("--dashboard-url", command)
        self.assertNotIn("--allow-configured-remote-vllm", command)
        with self.assertRaises(WorkflowError):
            build_runner_command(
                input_path=Path("input.jsonl"),
                output_dir=Path("out/research/workflow/baseline"),
                dashboard_url="http://127.0.0.1:8765",
                requested_parallel=4,
            )

    def test_runner_command_explicitly_forwards_configured_vllm_opt_in(self) -> None:
        command = build_runner_command(
            input_path=Path("tests/fixtures/research_local_benchmark_v1.jsonl"),
            output_dir=Path("out/research/workflow/baseline"),
            dashboard_url="http://127.0.0.1:8765",
            local_llm_endpoint="http://10.20.0.101:8000",
            local_llm_model="unsloth/gemma-4-26B-A4B-it-NVFP4",
            local_llm_fingerprint="a" * 64,
            allow_configured_remote_vllm=True,
        )
        self.assertIn("--allow-configured-remote-vllm", command)

    def test_runner_command_rejects_partial_or_unbound_vllm_identity(self) -> None:
        with self.assertRaises(WorkflowError):
            build_runner_command(
                input_path=Path("tests/fixtures/research_local_benchmark_v1.jsonl"),
                output_dir=Path("out/research/workflow/baseline"),
                dashboard_url="http://127.0.0.1:8765",
                local_llm_endpoint="http://10.20.0.101:8000",
                local_llm_model="unsloth/gemma-4-26B-A4B-it-NVFP4",
            )
        with self.assertRaises(WorkflowError):
            build_runner_command(
                input_path=Path("tests/fixtures/research_local_benchmark_v1.jsonl"),
                output_dir=Path("out/research/workflow/baseline"),
                dashboard_url="http://127.0.0.1:8765",
                allow_configured_remote_vllm=True,
            )

    def test_workflow_manifest_self_hash_is_sealed(self) -> None:
        manifest = seal_workflow_manifest({"schema_version": "test", "status": "PASS"})
        self.assertEqual(manifest["workflow_manifest_sha256"], sha256_value({"schema_version": "test", "status": "PASS"}))

    def test_workflow_report_is_korean_and_preserves_terminal_counts(self) -> None:
        manifest = {
            "schema_version": "research-local-grounding-workflow-v1",
            "claim_level": "RESEARCH_EVIDENCE_ONLY",
            "output_root": "out/research/workflow",
            "dashboard": {"status": "CONNECTED", "url": "http://127.0.0.1:8765"},
            "requested_parallel": 16,
            "partitions": {
                "baseline": {
                    "benchmark_input_count": 16,
                    "requested_parallel": 16,
                    "effective_parallel": 16,
                    "terminal_status_counts": {"RESOLVED": 44, "NIL": 4, "ABSTAIN": 0, "UNAVAILABLE": 16, "ERROR": 0},
                },
                "challenge": {
                    "benchmark_input_count": 4,
                    "requested_parallel": 16,
                    "effective_parallel": 4,
                    "terminal_status_counts": {"RESOLVED": 11, "NIL": 0, "ABSTAIN": 1, "UNAVAILABLE": 4, "ERROR": 0},
                    "arms": {
                        "local_llm": {
                            "diagnostics": {
                                "failure_stage_counts": {
                                    "CANDIDATE_RECALL_MISS": 1,
                                    "NIL_MISCLASSIFICATION": 1,
                                },
                                "candidate_recall": {
                                    "recall_at_5": {"numerator": 2, "denominator": 3},
                                },
                                "conditional_selection": {"numerator": 0, "denominator": 1},
                            },
                        },
                    },
                },
            },
            "tests": {"focused_unittest": {"status": "PASS"}},
        }
        report = render_workflow_report(manifest)
        self.assertIn("연구 전용", report)
        self.assertIn("16/16", report)
        self.assertIn("16/4", report)
        self.assertIn("UNAVAILABLE=16", report)
        self.assertIn("CANDIDATE_RECALL_MISS=1", report)
        self.assertIn("NIL_MISCLASSIFICATION=1", report)
        self.assertIn("Recall@5 `2/3`", report)
        self.assertIn("조건부 selection `0/1`", report)


if __name__ == "__main__":
    unittest.main()
