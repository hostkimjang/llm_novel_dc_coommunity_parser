from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def load_state_map_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "build_goal_current_state_map.py"
    spec = importlib.util.spec_from_file_location("build_goal_current_state_map", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GoalCurrentStateMapTest(unittest.TestCase):
    def test_partial_original_source_stays_review_locked(self):
        mod = load_state_map_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = root / "expert_result_20260528_141006_620986.json"
            result.write_text(json.dumps([{"post_id": 1}], ensure_ascii=False), encoding="utf-8")
            result.with_name(f"{result.stem}_manifest.json").write_text(
                json.dumps(
                    {
                        "run_id": "20260528_141006_620986",
                        "input_post_count": 100000,
                        "completed_count": 80,
                        "flushed_count": 71,
                        "pending_count": 9,
                        "failed_count": 0,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            preflight = root / "preflight.json"
            preflight.write_text(
                json.dumps(
                    {
                        "source_review_policy": {
                            "source_dataset_kind": "partial_final_result_json",
                            "source_integrity_classification": "manifest_partial_run",
                            "large_run_complete": False,
                        },
                        "random_baseline": {
                            "requested_sample_size": 1000,
                            "available_rows": 71,
                            "feasible": False,
                            "shortfall": 929,
                        },
                        "gate": {
                            "overall": "REVIEW-LOCKED",
                            "semantic_preflight": "REVIEW-LOCKED",
                            "run_integrity": "REVIEW",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = mod.build_state_map(result, preflight_path=preflight)

        self.assertEqual(report["gates"]["original_source_approval"], "NO-GO")
        self.assertEqual(report["gates"]["semantic_approval"], "REVIEW-LOCKED")
        codes = {item["code"] for item in report["critical_blockers"]}
        self.assertIn("original_manifest_partial", codes)
        self.assertIn("random_baseline_infeasible", codes)

    def test_runtime_go_does_not_become_semantic_go(self):
        mod = load_state_map_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = root / "result.json"
            result.write_text(json.dumps([{"post_id": 1}], ensure_ascii=False), encoding="utf-8")
            result.with_name("result_manifest.json").write_text(
                json.dumps(
                    {
                        "run_id": "run",
                        "input_post_count": 1,
                        "completed_count": 1,
                        "flushed_count": 1,
                        "pending_count": 0,
                        "failed_count": 0,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            audit = root / "audit.json"
            audit.write_text(
                json.dumps(
                    {
                        "auto_discovered_logs": True,
                        "log_evidence_present": True,
                        "observed": {
                            "run_id": "small",
                            "requested_parallel": 36,
                            "effective_parallel": 1,
                            "input_post_count": 1,
                            "completed_count": 1,
                            "flushed_count": 1,
                            "pending_count": 0,
                            "failed_count": 0,
                            "vlm_ocr_semantic_review_ready": True,
                        },
                        "gate": {
                            "runtime_contract": "GO",
                            "semantic_approval": "not_evaluated_by_runtime_contract_audit",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = mod.build_state_map(result, runtime_audit_path=audit)

        self.assertEqual(report["gates"]["small_run_runtime_contract"], "GO")
        self.assertEqual(report["gates"]["semantic_approval"], "REVIEW-LOCKED")
        self.assertEqual(
            report["small_run_runtime_audit"]["semantic_approval"],
            "not_evaluated_by_runtime_contract_audit",
        )

    def test_markdown_is_korean_and_lists_blockers(self):
        mod = load_state_map_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = root / "result.json"
            result.write_text(json.dumps([], ensure_ascii=False), encoding="utf-8")
            result.with_name("result_manifest.json").write_text(
                json.dumps(
                    {
                        "run_id": "run",
                        "input_post_count": 10,
                        "completed_count": 1,
                        "flushed_count": 1,
                        "pending_count": 0,
                        "failed_count": 0,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            report = mod.build_state_map(result)
            output = root / "state.md"
            mod.write_markdown(report, output)

            text = output.read_text(encoding="utf-8")

        self.assertIn("# Goal 현재 상태 맵", text)
        self.assertIn("10만 semantic approval", text)
        self.assertIn("original_manifest_partial", text)


if __name__ == "__main__":
    unittest.main()
