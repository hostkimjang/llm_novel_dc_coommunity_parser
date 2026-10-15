from __future__ import annotations

import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from src.llm_batch.grounding.research_local_benchmark import (
    Prediction,
    ResearchBenchmarkError,
    SCHEMA_VERSION,
    build_parallel_contract,
    effective_parallel,
    ensure_research_output_dir,
    load_and_validate_fixture,
    run_rows,
    summarize,
    validate_local_endpoint,
    validate_terminal_manifest,
    sha256_file,
    sha256_value,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/research_local_benchmark_v1.jsonl"
CHALLENGE_FIXTURE = ROOT / "tests/fixtures/research_local_benchmark_challenge_v1.jsonl"


class ResearchLocalBenchmarkTests(unittest.TestCase):
    def test_rights_safe_gold_lite_fixture(self) -> None:
        rows = load_and_validate_fixture(FIXTURE)
        self.assertEqual(16, len(rows))
        self.assertEqual(4, sum(row.get("blind_recheck") is not None for row in rows))
        self.assertTrue(all(row["rights"]["kind"] == "SYNTHETIC" for row in rows))

    def test_challenge_fixture_separates_diagnostic_cases(self) -> None:
        rows = load_and_validate_fixture(CHALLENGE_FIXTURE)
        self.assertEqual(4, len(rows))
        self.assertEqual(
            {"CANDIDATE_MISS", "COMPARISON_SELECTION", "ACTUAL_NIL", "AMBIGUOUS"},
            {row["case_type"] for row in rows},
        )
        self.assertEqual(1, sum(row.get("blind_recheck") is not None for row in rows))
        self.assertEqual({"SYNTHETIC"}, {row["rights"]["kind"] for row in rows})

    def test_candidate_recall_and_selection_are_separate(self) -> None:
        rows = load_and_validate_fixture(CHALLENGE_FIXTURE)
        predictions = run_rows(rows, requested_parallel=16)
        metrics = summarize(predictions)
        self.assertEqual(16, len(predictions))
        self.assertEqual({4}, {value["denominator"] for value in metrics["arms"].values()})
        self.assertEqual(4, metrics["partitions"]["default"]["arms"]["lexical_baseline"]["denominator"])
        self.assertEqual(
            3,
            metrics["arms"]["local_llm"]["candidate_recall"]["recall_at_5"]["denominator"],
        )
        local_miss = next(
            item
            for item in predictions
            if item["query_id"] == "challenge-001" and item["arm"] == "local_llm"
        )
        self.assertFalse(local_miss["gold_in_retrieval_top_k"])
        self.assertFalse(local_miss["gold_in_selection_candidates"])
        self.assertEqual("UNAVAILABLE", local_miss["failure_stage"])
        self.assertEqual(
            "CANDIDATE_RECALL_MISS",
            Prediction(
                "diagnostic",
                "probe",
                "wrong-candidate",
                "RESOLVED",
                0.0,
                candidate_ids=("retrieved",),
                selection_candidate_ids=("retrieved",),
            ).to_dict(
                gold_label="gold",
                case_type="CANDIDATE_MISS",
                expected_action="RESOLVED",
            )["failure_stage"],
        )

    def test_ambiguous_case_requires_abstain_action(self) -> None:
        rows = load_and_validate_fixture(CHALLENGE_FIXTURE)
        bad = dict(rows[3])
        bad["expected_action"] = "RESOLVED"
        bad["blind_recheck"] = {
            "reviewer_id": "independent-codex-agent-20260914",
            "reviewer_type": "independent_model_agent",
            "label": bad["gold_label"],
            "confidence": "medium",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.jsonl"
            path.write_text(json.dumps(bad, ensure_ascii=False) + "\n", encoding="utf-8")
            with self.assertRaises(ResearchBenchmarkError):
                load_and_validate_fixture(path)

    def test_all_terminal_states_remain_in_each_arm_denominator(self) -> None:
        rows = load_and_validate_fixture(FIXTURE)
        predictions = run_rows(rows, requested_parallel=16)
        metrics = summarize(predictions)
        self.assertEqual(64, len(predictions))
        self.assertEqual({16}, {value["denominator"] for value in metrics["arms"].values()})
        self.assertEqual(16, metrics["arms"]["local_llm"]["terminal_status_counts"]["UNAVAILABLE"])
        self.assertIsNone(metrics["arms"]["local_llm"]["accuracy"])
        self.assertEqual("ACCOUNTING_ONLY_WORST_CASE", metrics["arms"]["local_llm"]["operational_accuracy"]["status"])
        self.assertIsNone(metrics["comparisons"]["local_llm"]["accuracy_delta_vs_lexical_baseline"])
        self.assertEqual("NOT_ESTIMABLE", metrics["comparisons"]["local_llm"]["status"])
        self.assertIsNone(metrics["arms"]["local_llm"]["latency"]["mean_ms"])
        self.assertIsNone(metrics["arms"]["local_llm"]["closed_candidate_ranking"]["hit_at_1"]["value"])

    def test_effective_parallel_can_exceed_one_without_changing_row_contract(self) -> None:
        rows = load_and_validate_fixture(FIXTURE)[:3]
        predictions = run_rows(rows, requested_parallel=16)
        self.assertEqual(12, len(predictions))
        self.assertEqual(3, len({row["query_id"] for row in predictions}))
        self.assertEqual(3, effective_parallel(16, len(rows)))
        self.assertEqual(
            {
                "requested_parallel": 16,
                "effective_parallel": 3,
                "parallel_count": 3,
                "parallel_policy": "effective_parallel=min(requested_parallel,benchmark_input_count)",
            },
            build_parallel_contract(16, 3),
        )

    def test_full_terminal_taxonomy_is_conserved(self) -> None:
        statuses = ["RESOLVED", "NIL", "ABSTAIN", "UNAVAILABLE", "ERROR"]
        rows = [
            {
                "query_id": f"q-{status.lower()}",
                "arm": "taxonomy_probe",
                "gold_label": "__NIL__" if status == "NIL" else "candidate-a",
                "predicted_label": "__NIL__" if status == "NIL" else "candidate-a" if status == "RESOLVED" else None,
                "terminal_status": status,
                "correct": status in {"RESOLVED", "NIL"},
                "latency_ms": 1.0,
                "scores": [],
            }
            for status in statuses
        ]
        metric = summarize(rows)["arms"]["taxonomy_probe"]
        self.assertEqual(5, metric["denominator"])
        self.assertEqual({status: 1 for status in sorted(statuses)}, metric["terminal_status_counts"])
        self.assertEqual(5, sum(metric["terminal_status_counts"].values()))

    def test_research_output_namespace_and_overwrite_are_fail_closed(self) -> None:
        research_root = ROOT / "out/research"
        research_root.mkdir(parents=True, exist_ok=True)
        outside = ROOT / "out/not-research-output"
        with self.assertRaises(ResearchBenchmarkError):
            ensure_research_output_dir(outside, research_root)
        with tempfile.TemporaryDirectory(dir=research_root) as existing:
            with self.assertRaises(ResearchBenchmarkError):
                ensure_research_output_dir(Path(existing), research_root)
        fresh = research_root / "unit-fresh-output-boundary"
        self.assertEqual(fresh.resolve(), ensure_research_output_dir(fresh, research_root))

    def test_terminal_validator_accepts_valid_manifest_and_rejects_tamper(self) -> None:
        research_root = ROOT / "out/research"
        research_root.mkdir(parents=True, exist_ok=True)
        fixture_rows = load_and_validate_fixture(FIXTURE)[:1]
        predictions = run_rows(fixture_rows, requested_parallel=16)
        metrics = summarize(predictions)
        metrics["throughput"] = {"accounted_predictions": len(predictions), "accounted_predictions_per_sec": 1.0}
        with tempfile.TemporaryDirectory(dir=research_root) as directory:
            output = Path(directory)
            predictions_path = output / "predictions.json"
            metrics_path = output / "metrics.json"
            report_path = output / "report_ko.md"
            manifest_path = output / "manifest.json"
            input_path = output / "input.jsonl"
            input_path.write_text(
                json.dumps(fixture_rows[0], ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            predictions_path.write_text(json.dumps(predictions, ensure_ascii=False), encoding="utf-8")
            metrics_path.write_text(json.dumps(metrics, ensure_ascii=False), encoding="utf-8")
            report_path.write_text("# 테스트 보고서\n", encoding="utf-8")

            def ref(path: Path) -> dict[str, object]:
                return {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}

            counts = Counter(item["terminal_status"] for item in predictions)
            receipt = {"ok": True, "standalone": True, "service": "expert-pipeline-dashboard", "pid": 1}
            manifest = {
                "schema_version": SCHEMA_VERSION,
                "claim_level": "RESEARCH_EVIDENCE_ONLY",
                "publication_mode": "OFFLINE_SHADOW",
                "p0_authority_claimed": False,
                "production_authority_claimed": False,
                "full_scan_approval": False,
                "central_slang_db_write": False,
                "benchmark_input_count": 1,
                "requested_parallel": 16,
                "effective_parallel": 1,
                "parallel_policy": "effective_parallel=min(requested_parallel,benchmark_input_count)",
                "dashboard": {
                    "enabled": True,
                    "status": "CONNECTED",
                    "preflight_receipt": receipt,
                    "preflight_response_sha256": sha256_value(receipt),
                    "postflight_receipt": receipt,
                    "postflight_response_sha256": sha256_value(receipt),
                },
                "job_count": len(predictions),
                "completed_count": len(predictions),
                "terminal_status_counts": {
                    status: counts.get(status, 0)
                    for status in ("RESOLVED", "NIL", "ABSTAIN", "UNAVAILABLE", "ERROR")
                },
                "artifacts": {
                    "input": ref(input_path),
                    "predictions": ref(predictions_path),
                    "metrics": ref(metrics_path),
                    "report_ko": ref(report_path),
                },
                "metrics_sha256": sha256_value(metrics),
                "semantic_output_sha256": sha256_value(
                    [{key: value for key, value in item.items() if key != "latency_ms"} for item in predictions]
                ),
            }
            manifest["manifest_sha256"] = sha256_value(manifest)
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(manifest["manifest_sha256"], validate_terminal_manifest(manifest_path, research_root=research_root)["manifest_sha256"])
            predictions_path.write_text("[]", encoding="utf-8")
            with self.assertRaises(ResearchBenchmarkError):
                validate_terminal_manifest(manifest_path, research_root=research_root)

    def test_local_llm_endpoint_is_loopback_only(self) -> None:
        self.assertEqual("http://127.0.0.1:11434", validate_local_endpoint("http://127.0.0.1:11434/"))
        with self.assertRaises(ResearchBenchmarkError):
            validate_local_endpoint("https://example.com")
        self.assertEqual(
            "http://10.20.0.101:8000",
            validate_local_endpoint("http://10.20.0.101:8000/", allow_configured_remote=True),
        )

    def test_local_llm_request_uses_expert_main_vllm_no_thinking_contract(self) -> None:
        from unittest.mock import patch

        rows = load_and_validate_fixture(FIXTURE)[:1]
        with patch("src.llm_batch.grounding.research_local_benchmark.urllib.request.urlopen") as urlopen:
            response = urlopen.return_value.__enter__.return_value
            response.read.return_value = json.dumps(
                {
                    "choices": [
                        {"message": {"content": "work-academy-survivor"}}
                    ]
                }
            ).encode("utf-8")
            predictions = run_rows(
                rows,
                requested_parallel=1,
                local_llm_endpoint="http://10.20.0.101:8000",
                local_llm_model="unsloth/gemma-4-26B-A4B-it-NVFP4",
                allow_configured_remote=True,
            )
            request = next(
                call.args[0]
                for call in urlopen.call_args_list
                if getattr(call.args[0], "full_url", "").endswith("/v1/chat/completions")
            )
            body = json.loads(request.data.decode("utf-8"))
        self.assertEqual("RESOLVED", next(item["terminal_status"] for item in predictions if item["arm"] == "local_llm"))
        self.assertFalse(body["enable_thinking"])
        self.assertEqual({"enable_thinking": False}, body["chat_template_kwargs"])


if __name__ == "__main__":
    unittest.main()
