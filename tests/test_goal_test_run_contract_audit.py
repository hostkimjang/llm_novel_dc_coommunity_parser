from __future__ import annotations

import importlib.util
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from unittest import mock


def load_audit_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "audit_goal_test_run_contract.py"
    spec = importlib.util.spec_from_file_location("audit_goal_test_run_contract", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_expert_main_module():
    path = Path(__file__).resolve().parents[1] / "expert_main.py"
    spec = importlib.util.spec_from_file_location("expert_main_for_parallel_policy_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dashboard_manifest_fields() -> dict[str, object]:
    return {
        "dashboard_enabled": True,
        "dashboard_mode": "standalone_forward",
        "dashboard_url": "http://127.0.0.1:8080",
        "dashboard_standalone_forwarding": True,
        "dashboard_start_error": "",
    }


class GoalTestRunContractAuditTest(unittest.TestCase):
    def test_expert_main_caps_gemma_4_4b_parallel_as_model_max(self):
        mod = load_expert_main_module()

        capped = mod._apply_model_parallel_cap(64, "bg-digitalservices/Gemma-4-E4B-it-NVFP4")
        below_cap = mod._apply_model_parallel_cap(8, "bg-digitalservices/Gemma-4-E4B-it-NVFP4")
        uncapped = mod._apply_model_parallel_cap(64, "google/gemma-4-26B-A4B-it")

        self.assertEqual(capped["requested_parallel_raw"], 64)
        self.assertEqual(capped["requested_parallel"], 36)
        self.assertEqual(capped["model_parallel_max"], 36)
        self.assertTrue(capped["model_parallel_cap_applied"])
        self.assertEqual(below_cap["requested_parallel"], 8)
        self.assertFalse(below_cap["model_parallel_cap_applied"])
        self.assertIsNone(uncapped["model_parallel_max"])
        self.assertEqual(uncapped["requested_parallel"], 64)

    def test_default_process_patterns_do_not_match_codex_openai_processes(self):
        mod = load_audit_module()
        self.assertNotIn("openai", mod.DEFAULT_PROCESS_PATTERNS)

    def test_clean_small_goal_run_contract_is_go(self):
        mod = load_audit_module()
        manifest = {
            "run_id": "20260531_150000_000000",
            "input_post_count": 4,
            "llm_model": "bg-digitalservices/Gemma-4-E4B-it-NVFP4",
            "llm_endpoint": "http://10.20.0.101:8000/",
            "requested_parallel_raw": 64,
            "requested_parallel": 36,
            "effective_parallel": 4,
            "parallel_policy": "effective_parallel=min(min(requested_parallel_raw,model_parallel_max),input_post_count)",
            "model_parallel_max": 36,
            "model_parallel_cap_applied": True,
            "completed_count": 4,
            "flushed_count": 4,
            "pending_count": 0,
            "failed_count": 0,
            "image_post_count": 1,
            "vlm_enabled": True,
            "ocr_enabled": True,
            "vlm_ocr_semantic_review_ready": True,
            "mcp_auto_up_shards": False,
            "mcp_auto_recreate_shards": False,
            "mcp_local_shard_management_enabled": False,
            "mcp_local_shard_status_audit_allowed": False,
            "mcp_small_run_shard_lifecycle_blocked": True,
            "mcp_health_include_search": False,
            "mcp_health_light_mode": True,
            "mcp_health_required_ok_count": 4,
            "mcp_health_checked_endpoint_count": 4,
            "mcp_health_probe_batch_size": 4,
            "mcp_health_workers": 4,
            "mcp_health_attempts": 1,
            "mcp_health_timeout_sec": 8.0,
            "mcp_health_ok_count": 4,
            "mcp_health_failure_count": 0,
            "mcp_requested_endpoint_count_before_health_filter": 4,
            "mcp_endpoint_count_after_health_filter": 4,
            **dashboard_manifest_fields(),
        }

        audit = mod.audit_manifest(manifest)

        self.assertEqual(audit["gate"]["runtime_contract"], "GO")
        self.assertEqual(audit["issues"], [])
        self.assertEqual(audit["observed"]["requested_parallel_raw"], 64)
        self.assertEqual(audit["observed"]["requested_parallel"], 36)
        self.assertEqual(audit["observed"]["effective_parallel"], 4)
        self.assertEqual(audit["observed"]["model_parallel_max"], 36)
        self.assertTrue(audit["observed"]["model_parallel_cap_applied"])
        self.assertEqual(audit["gate"]["semantic_approval"], "not_evaluated_by_runtime_contract_audit")

    def test_small_goal_run_missing_light_health_fields_is_review(self):
        mod = load_audit_module()
        manifest = {
            "run_id": "20260601_180000_000000",
            "input_post_count": 2,
            "requested_parallel": 36,
            "effective_parallel": 2,
            "completed_count": 2,
            "flushed_count": 2,
            "pending_count": 0,
            "failed_count": 0,
            "image_post_count": 0,
            "vlm_enabled": True,
            "ocr_enabled": True,
            "vlm_ocr_semantic_review_ready": True,
            "mcp_auto_up_shards": False,
            "mcp_auto_recreate_shards": False,
            "mcp_local_shard_management_enabled": False,
            "mcp_small_run_shard_lifecycle_blocked": True,
        }

        audit = mod.audit_manifest(manifest)

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["gate"]["runtime_contract"], "REVIEW")
        self.assertIn("small_run_health_include_search_missing", codes)
        self.assertIn("small_run_health_light_mode_missing", codes)
        self.assertIn("mcp_health_checked_endpoint_count_missing", codes)

    def test_clean_small_goal_run_records_light_health_fields(self):
        mod = load_audit_module()
        manifest = {
            "run_id": "20260601_170000_000000",
            "input_post_count": 2,
            "llm_endpoint": "http://10.20.0.101:8000/",
            "requested_parallel_raw": 36,
            "requested_parallel": 36,
            "effective_parallel": 2,
            "completed_count": 2,
            "flushed_count": 2,
            "pending_count": 0,
            "failed_count": 0,
            "image_post_count": 0,
            "vlm_enabled": True,
            "ocr_enabled": True,
            "vlm_ocr_semantic_review_ready": True,
            "mcp_auto_up_shards": False,
            "mcp_auto_recreate_shards": False,
            "mcp_local_shard_management_enabled": False,
            "mcp_local_shard_status_audit_allowed": False,
            "mcp_small_run_shard_lifecycle_blocked": True,
            "mcp_health_include_search": False,
            "mcp_health_light_mode": True,
            "mcp_health_required_ok_count": 2,
            "mcp_health_checked_endpoint_count": 2,
            "mcp_health_probe_batch_size": 2,
            "mcp_health_probe_stopped_after_required_ok": True,
            "mcp_health_workers": 12,
            "mcp_health_attempts": 1,
            "mcp_health_timeout_sec": 8.0,
            "mcp_health_ok_count": 2,
            "mcp_health_failure_count": 0,
            "mcp_requested_endpoint_count_before_health_filter": 36,
            "mcp_endpoint_count_after_health_filter": 2,
            **dashboard_manifest_fields(),
        }

        audit = mod.audit_manifest(manifest)

        self.assertEqual(audit["gate"]["runtime_contract"], "GO")
        self.assertEqual(audit["issues"], [])
        self.assertFalse(audit["observed"]["mcp_health_include_search"])
        self.assertTrue(audit["observed"]["mcp_health_light_mode"])
        self.assertEqual(audit["observed"]["mcp_health_checked_endpoint_count"], 2)

    def test_small_goal_run_missing_dashboard_contract_is_review(self):
        mod = load_audit_module()
        manifest = {
            "input_post_count": 1,
            "llm_endpoint": "http://10.20.0.101:8000/",
            "requested_parallel": 16,
            "effective_parallel": 1,
            "completed_count": 1,
            "flushed_count": 1,
            "pending_count": 0,
            "failed_count": 0,
            "image_post_count": 0,
            "vlm_enabled": True,
            "ocr_enabled": True,
            "vlm_ocr_semantic_review_ready": True,
            "mcp_auto_up_shards": False,
            "mcp_auto_recreate_shards": False,
            "mcp_local_shard_management_enabled": False,
            "mcp_small_run_shard_lifecycle_blocked": True,
            "mcp_health_include_search": False,
            "mcp_health_light_mode": True,
            "mcp_health_required_ok_count": 1,
            "mcp_health_checked_endpoint_count": 1,
            "mcp_health_probe_batch_size": 1,
            "mcp_health_workers": 1,
            "mcp_health_attempts": 1,
            "mcp_health_timeout_sec": 8.0,
            "mcp_health_ok_count": 1,
            "mcp_health_failure_count": 0,
            "mcp_requested_endpoint_count_before_health_filter": 1,
            "mcp_endpoint_count_after_health_filter": 1,
        }

        audit = mod.audit_manifest(manifest)

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["gate"]["runtime_contract"], "REVIEW")
        self.assertIn("dashboard_enabled_missing", codes)

    def test_small_goal_run_disabled_dashboard_is_no_go(self):
        mod = load_audit_module()
        manifest = {
            "input_post_count": 1,
            "llm_endpoint": "http://10.20.0.101:8000/",
            "requested_parallel": 16,
            "effective_parallel": 1,
            "completed_count": 1,
            "flushed_count": 1,
            "pending_count": 0,
            "failed_count": 0,
            "image_post_count": 0,
            "vlm_enabled": True,
            "ocr_enabled": True,
            "vlm_ocr_semantic_review_ready": True,
            "mcp_auto_up_shards": False,
            "mcp_auto_recreate_shards": False,
            "mcp_local_shard_management_enabled": False,
            "mcp_small_run_shard_lifecycle_blocked": True,
            "mcp_health_include_search": False,
            "mcp_health_light_mode": True,
            "mcp_health_required_ok_count": 1,
            "mcp_health_checked_endpoint_count": 1,
            "mcp_health_probe_batch_size": 1,
            "mcp_health_workers": 1,
            "mcp_health_attempts": 1,
            "mcp_health_timeout_sec": 8.0,
            "mcp_health_ok_count": 1,
            "mcp_health_failure_count": 0,
            "mcp_requested_endpoint_count_before_health_filter": 1,
            "mcp_endpoint_count_after_health_filter": 1,
            "dashboard_enabled": False,
            "dashboard_mode": "disabled",
            "dashboard_url": "",
        }

        audit = mod.audit_manifest(manifest)

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["gate"]["runtime_contract"], "NO-GO")
        self.assertIn("dashboard_disabled_for_goal_test_run", codes)

    def test_small_goal_run_search_health_is_review(self):
        mod = load_audit_module()
        manifest = {
            "input_post_count": 2,
            "requested_parallel": 36,
            "effective_parallel": 2,
            "completed_count": 2,
            "flushed_count": 2,
            "pending_count": 0,
            "failed_count": 0,
            "image_post_count": 0,
            "vlm_enabled": True,
            "ocr_enabled": True,
            "vlm_ocr_semantic_review_ready": True,
            "mcp_auto_up_shards": False,
            "mcp_auto_recreate_shards": False,
            "mcp_local_shard_management_enabled": False,
            "mcp_small_run_shard_lifecycle_blocked": True,
            "mcp_health_include_search": True,
            "mcp_health_light_mode": True,
            "mcp_health_required_ok_count": 2,
            "mcp_health_checked_endpoint_count": 2,
            "mcp_requested_endpoint_count_before_health_filter": 2,
            "mcp_endpoint_count_after_health_filter": 2,
        }

        audit = mod.audit_manifest(manifest)

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["gate"]["runtime_contract"], "REVIEW")
        self.assertIn("small_run_health_include_search_true", codes)

    def test_small_goal_run_missing_llm_endpoint_is_review(self):
        mod = load_audit_module()
        manifest = {
            "input_post_count": 1,
            "requested_parallel": 36,
            "effective_parallel": 1,
            "completed_count": 1,
            "flushed_count": 1,
            "pending_count": 0,
            "failed_count": 0,
            "image_post_count": 0,
            "vlm_enabled": True,
            "ocr_enabled": True,
            "vlm_ocr_semantic_review_ready": True,
            "mcp_auto_up_shards": False,
            "mcp_auto_recreate_shards": False,
            "mcp_local_shard_management_enabled": False,
            "mcp_small_run_shard_lifecycle_blocked": True,
            "mcp_health_include_search": False,
            "mcp_health_light_mode": True,
            "mcp_health_required_ok_count": 1,
            "mcp_health_checked_endpoint_count": 1,
            "mcp_health_probe_batch_size": 1,
            "mcp_health_workers": 1,
            "mcp_health_attempts": 1,
            "mcp_health_timeout_sec": 8.0,
            "mcp_health_ok_count": 1,
            "mcp_health_failure_count": 0,
            "mcp_requested_endpoint_count_before_health_filter": 1,
            "mcp_endpoint_count_after_health_filter": 1,
        }

        audit = mod.audit_manifest(manifest)

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["gate"]["runtime_contract"], "REVIEW")
        self.assertIn("llm_endpoint_missing", codes)

    def test_health_endpoint_count_contradictions_are_no_go(self):
        mod = load_audit_module()
        manifest = {
            "input_post_count": 2,
            "llm_endpoint": "http://10.20.0.101:8000/",
            "requested_parallel": 36,
            "effective_parallel": 2,
            "completed_count": 2,
            "flushed_count": 2,
            "pending_count": 0,
            "failed_count": 0,
            "image_post_count": 0,
            "vlm_enabled": True,
            "ocr_enabled": True,
            "vlm_ocr_semantic_review_ready": True,
            "mcp_auto_up_shards": False,
            "mcp_auto_recreate_shards": False,
            "mcp_local_shard_management_enabled": False,
            "mcp_small_run_shard_lifecycle_blocked": True,
            "mcp_health_include_search": False,
            "mcp_health_light_mode": True,
            "mcp_health_required_ok_count": 2,
            "mcp_health_checked_endpoint_count": 1,
            "mcp_health_ok_count": 1,
            "mcp_health_failure_count": 0,
            "mcp_requested_endpoint_count_before_health_filter": 2,
            "mcp_endpoint_count_after_health_filter": 2,
        }

        audit = mod.audit_manifest(manifest)

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["gate"]["runtime_contract"], "NO-GO")
        self.assertIn("mcp_health_checked_endpoint_count_lt_endpoint_count_after_filter", codes)

    def test_health_ok_and_failure_count_violations_are_no_go(self):
        mod = load_audit_module()
        manifest = {
            "input_post_count": 2,
            "llm_endpoint": "http://10.20.0.101:8000/",
            "requested_parallel": 36,
            "effective_parallel": 2,
            "completed_count": 2,
            "flushed_count": 2,
            "pending_count": 0,
            "failed_count": 0,
            "image_post_count": 0,
            "vlm_enabled": True,
            "ocr_enabled": True,
            "vlm_ocr_semantic_review_ready": True,
            "mcp_auto_up_shards": False,
            "mcp_auto_recreate_shards": False,
            "mcp_local_shard_management_enabled": False,
            "mcp_small_run_shard_lifecycle_blocked": True,
            "mcp_health_include_search": False,
            "mcp_health_light_mode": True,
            "mcp_health_required_ok_count": 2,
            "mcp_health_checked_endpoint_count": 2,
            "mcp_health_probe_batch_size": 2,
            "mcp_health_workers": 2,
            "mcp_health_attempts": 1,
            "mcp_health_timeout_sec": 8.0,
            "mcp_health_ok_count": 1,
            "mcp_health_failure_count": 1,
            "mcp_requested_endpoint_count_before_health_filter": 2,
            "mcp_endpoint_count_after_health_filter": 2,
        }

        audit = mod.audit_manifest(manifest)

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["gate"]["runtime_contract"], "NO-GO")
        self.assertIn("mcp_health_ok_count_lt_required_ok_count", codes)
        self.assertIn("mcp_health_failure_count_gt_zero", codes)

    def test_lifecycle_flags_and_docker_log_hits_are_no_go(self):
        mod = load_audit_module()
        manifest = {
            "input_post_count": 2,
            "requested_parallel": 36,
            "effective_parallel": 2,
            "completed_count": 2,
            "flushed_count": 2,
            "pending_count": 0,
            "failed_count": 0,
            "image_post_count": 0,
            "vlm_enabled": True,
            "ocr_enabled": True,
            "vlm_ocr_semantic_review_ready": True,
            "mcp_auto_up_shards": True,
            "mcp_auto_recreate_shards": False,
            "mcp_local_shard_management_enabled": True,
            "mcp_small_run_shard_lifecycle_blocked": False,
        }
        with TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "expert_run.log"
            log_path.write_text(
                "startup\n"
                "docker compose up -d shard-1\n"
                "tools/warp_shards.py recreate 1\n",
                encoding="utf-8",
            )
            audit = mod.audit_manifest(manifest, log_paths=[log_path])

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["gate"]["runtime_contract"], "NO-GO")
        self.assertIn("mcp_auto_up_shards_true_for_small_goal_run", codes)
        self.assertIn("mcp_local_shard_management_enabled_true_for_small_goal_run", codes)
        self.assertIn("docker_or_shard_lifecycle_log_hits", codes)
        self.assertGreater(audit["log_scan"]["total_counts"]["docker_compose"], 0)

    def test_traceback_log_hit_is_no_go_runtime_exception(self):
        mod = load_audit_module()
        manifest = {
            "run_id": "20260615_231925_533889",
            "input_post_count": 1,
            "llm_endpoint": "http://10.20.0.101:8000/",
            "requested_parallel": 1,
            "effective_parallel": 1,
            "completed_count": 1,
            "flushed_count": 1,
            "pending_count": 0,
            "failed_count": 0,
            "image_post_count": 1,
            "vlm_enabled": True,
            "ocr_enabled": True,
            "vlm_ocr_semantic_review_ready": True,
            "mcp_auto_up_shards": False,
            "mcp_auto_recreate_shards": False,
            "mcp_local_shard_management_enabled": False,
            "mcp_small_run_shard_lifecycle_blocked": True,
            "mcp_health_include_search": False,
            "mcp_health_light_mode": True,
            "mcp_health_required_ok_count": 1,
            "mcp_health_checked_endpoint_count": 1,
            "mcp_health_probe_batch_size": 1,
            "mcp_health_workers": 1,
            "mcp_health_attempts": 1,
            "mcp_health_timeout_sec": 8.0,
            "mcp_health_ok_count": 1,
            "mcp_health_failure_count": 0,
            "mcp_requested_endpoint_count_before_health_filter": 1,
            "mcp_endpoint_count_after_health_filter": 1,
        }
        with TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "expert_run.log"
            log_path.write_text(
                "Deliberation 오류: name 'disc' is not defined\n"
                "Traceback (most recent call last):\n"
                "NameError: name 'disc' is not defined\n",
                encoding="utf-8",
            )
            audit = mod.audit_manifest(manifest, log_paths=[log_path])

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["gate"]["runtime_contract"], "NO-GO")
        self.assertIn("runtime_log_exception", codes)
        self.assertGreater(audit["log_scan"]["total_counts"]["python_traceback"], 0)

    def test_cli_auto_discovers_log_from_run_id(self):
        mod = load_audit_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "manifest.json"
            log_dir = root / "logs"
            output_json = root / "audit.json"
            log_dir.mkdir()
            run_id = "20260531_153000_123456"
            manifest_path.write_text(
                json.dumps(
                    {
                        "run_id": run_id,
                        "input_post_count": 1,
                        "llm_endpoint": "http://10.20.0.101:8000/",
                        "requested_parallel": 36,
                        "effective_parallel": 1,
                        "completed_count": 1,
                        "flushed_count": 1,
                        "pending_count": 0,
                        "failed_count": 0,
                        "image_post_count": 0,
                        "mcp_auto_up_shards": False,
                        "mcp_auto_recreate_shards": False,
                        "mcp_local_shard_management_enabled": False,
                        "mcp_small_run_shard_lifecycle_blocked": True,
                        "mcp_health_include_search": False,
                        "mcp_health_light_mode": True,
                        "mcp_health_required_ok_count": 1,
                        "mcp_health_checked_endpoint_count": 1,
                        "mcp_health_probe_batch_size": 1,
                        "mcp_health_workers": 1,
                        "mcp_health_attempts": 1,
                        "mcp_health_timeout_sec": 8.0,
                        "mcp_health_ok_count": 1,
                        "mcp_health_failure_count": 0,
                        "mcp_requested_endpoint_count_before_health_filter": 1,
                        "mcp_endpoint_count_after_health_filter": 1,
                        **dashboard_manifest_fields(),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (log_dir / f"expert_run_{run_id}.log").write_text("normal run\n", encoding="utf-8")

            import sys

            old_sys_argv = sys.argv[:]
            try:
                sys.argv = [
                    "audit_goal_test_run_contract.py",
                    "--manifest",
                    str(manifest_path),
                    "--log-dir",
                    str(log_dir),
                    "--output-json",
                    str(output_json),
                    "--fail-on-no-go",
                ]
                with redirect_stdout(io.StringIO()):
                    exit_code = mod.main()
            finally:
                sys.argv = old_sys_argv

            self.assertEqual(exit_code, 0)
            payload = json.loads(output_json.read_text(encoding="utf-8"))
        self.assertEqual(payload["gate"]["runtime_contract"], "GO")
        self.assertTrue(payload["auto_discovered_logs"])
        self.assertTrue(payload["log_evidence_present"])
        self.assertEqual(len(payload["log_paths"]), 1)
        self.assertFalse(payload["process_snapshot"]["enabled"])
        self.assertEqual(payload["process_snapshot"]["matching_process_count"], 0)

    def test_cli_process_snapshot_default_off_does_not_call_subprocess(self):
        mod = load_audit_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "manifest.json"
            output_json = root / "audit.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "input_post_count": 1,
                        "llm_endpoint": "http://10.20.0.101:8000/",
                        "requested_parallel": 36,
                        "effective_parallel": 1,
                        "completed_count": 1,
                        "flushed_count": 1,
                        "pending_count": 0,
                        "failed_count": 0,
                        "image_post_count": 0,
                        "mcp_auto_up_shards": False,
                        "mcp_auto_recreate_shards": False,
                        "mcp_local_shard_management_enabled": False,
                        "mcp_small_run_shard_lifecycle_blocked": True,
                        "mcp_health_include_search": False,
                        "mcp_health_light_mode": True,
                        "mcp_health_required_ok_count": 1,
                        "mcp_health_checked_endpoint_count": 1,
                        "mcp_health_probe_batch_size": 1,
                        "mcp_health_workers": 1,
                        "mcp_health_attempts": 1,
                        "mcp_health_timeout_sec": 8.0,
                        "mcp_health_ok_count": 1,
                        "mcp_health_failure_count": 0,
                        "mcp_requested_endpoint_count_before_health_filter": 1,
                        "mcp_endpoint_count_after_health_filter": 1,
                        **dashboard_manifest_fields(),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            import sys

            old_sys_argv = sys.argv[:]
            try:
                sys.argv = [
                    "audit_goal_test_run_contract.py",
                    "--manifest",
                    str(manifest_path),
                    "--output-json",
                    str(output_json),
                    "--no-require-log",
                ]
                with mock.patch.object(mod.subprocess, "run") as run_mock:
                    with redirect_stdout(io.StringIO()):
                        exit_code = mod.main()
            finally:
                sys.argv = old_sys_argv

            self.assertEqual(exit_code, 0)
            run_mock.assert_not_called()
            payload = json.loads(output_json.read_text(encoding="utf-8"))
        self.assertEqual(payload["gate"]["runtime_contract"], "GO")
        self.assertFalse(payload["process_snapshot"]["enabled"])
        self.assertFalse(payload["process_snapshot"]["available"])
        self.assertEqual(payload["process_snapshot"]["patterns"], list(mod.DEFAULT_PROCESS_PATTERNS))

    def test_cli_process_snapshot_failure_does_not_force_no_go(self):
        mod = load_audit_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "manifest.json"
            output_json = root / "audit.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "input_post_count": 1,
                        "llm_endpoint": "http://10.20.0.101:8000/",
                        "requested_parallel": 36,
                        "effective_parallel": 1,
                        "completed_count": 1,
                        "flushed_count": 1,
                        "pending_count": 0,
                        "failed_count": 0,
                        "image_post_count": 0,
                        "mcp_auto_up_shards": False,
                        "mcp_auto_recreate_shards": False,
                        "mcp_local_shard_management_enabled": False,
                        "mcp_small_run_shard_lifecycle_blocked": True,
                        "mcp_health_include_search": False,
                        "mcp_health_light_mode": True,
                        "mcp_health_required_ok_count": 1,
                        "mcp_health_checked_endpoint_count": 1,
                        "mcp_health_probe_batch_size": 1,
                        "mcp_health_workers": 1,
                        "mcp_health_attempts": 1,
                        "mcp_health_timeout_sec": 8.0,
                        "mcp_health_ok_count": 1,
                        "mcp_health_failure_count": 0,
                        "mcp_requested_endpoint_count_before_health_filter": 1,
                        "mcp_endpoint_count_after_health_filter": 1,
                        **dashboard_manifest_fields(),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            import sys

            old_sys_argv = sys.argv[:]
            try:
                sys.argv = [
                    "audit_goal_test_run_contract.py",
                    "--manifest",
                    str(manifest_path),
                    "--output-json",
                    str(output_json),
                    "--no-require-log",
                    "--collect-process-snapshot",
                ]
                with mock.patch.object(
                    mod.subprocess,
                    "run",
                    return_value=SimpleNamespace(returncode=1, stdout="", stderr="Get-CimInstance failed"),
                ):
                    with redirect_stdout(io.StringIO()):
                        exit_code = mod.main()
            finally:
                sys.argv = old_sys_argv

            self.assertEqual(exit_code, 0)
            payload = json.loads(output_json.read_text(encoding="utf-8"))
        self.assertEqual(payload["gate"]["runtime_contract"], "GO")
        self.assertEqual(payload["issues"], [])
        self.assertTrue(payload["process_snapshot"]["enabled"])
        self.assertFalse(payload["process_snapshot"]["available"])
        self.assertIn("Get-CimInstance failed", payload["process_snapshot"]["error"])

    def test_cli_process_snapshot_includes_mocked_matching_processes(self):
        mod = load_audit_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "manifest.json"
            output_json = root / "audit.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "input_post_count": 1,
                        "requested_parallel": 36,
                        "effective_parallel": 1,
                        "completed_count": 1,
                        "flushed_count": 1,
                        "pending_count": 0,
                        "failed_count": 0,
                        "image_post_count": 0,
                        "mcp_auto_up_shards": False,
                        "mcp_auto_recreate_shards": False,
                        "mcp_local_shard_management_enabled": False,
                        "mcp_small_run_shard_lifecycle_blocked": True,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            process_stdout = json.dumps(
                [
                    {
                        "pid": 4242,
                        "parent_pid": 100,
                        "creation_date": "2026-05-31T15:00:00.0000000+09:00",
                        "command_line": "python expert_main.py --input sample.jsonl --server-type vllm",
                    },
                    {
                        "pid": 4243,
                        "parent_pid": 100,
                        "creation_date": "2026-05-31T15:01:00.0000000+09:00",
                        "command_line": "python unrelated_script.py",
                    },
                ],
                ensure_ascii=False,
            )

            import sys

            old_sys_argv = sys.argv[:]
            try:
                sys.argv = [
                    "audit_goal_test_run_contract.py",
                    "--manifest",
                    str(manifest_path),
                    "--output-json",
                    str(output_json),
                    "--no-require-log",
                    "--collect-process-snapshot",
                    "--process-pattern",
                    "expert_main,llm_batch",
                    "--process-pattern",
                    "vllm",
                ]
                with mock.patch.object(
                    mod.subprocess,
                    "run",
                    return_value=SimpleNamespace(returncode=0, stdout=process_stdout, stderr=""),
                ):
                    with redirect_stdout(io.StringIO()):
                        exit_code = mod.main()
            finally:
                sys.argv = old_sys_argv

            self.assertEqual(exit_code, 0)
            payload = json.loads(output_json.read_text(encoding="utf-8"))
        snapshot = payload["process_snapshot"]
        self.assertTrue(snapshot["enabled"])
        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["patterns"], ["expert_main", "llm_batch", "vllm"])
        self.assertEqual(snapshot["matching_process_count"], 1)
        self.assertEqual(snapshot["stale_process_candidate_count"], 1)
        self.assertEqual(snapshot["processes"][0]["pid"], 4242)
        self.assertEqual(snapshot["processes"][0]["parent_pid"], 100)
        self.assertIn("expert_main.py", snapshot["processes"][0]["command_line"])

    def test_cli_process_snapshot_json_bypasses_subprocess(self):
        mod = load_audit_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "manifest.json"
            snapshot_path = root / "process_snapshot.json"
            output_json = root / "audit.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "input_post_count": 1,
                        "requested_parallel": 36,
                        "effective_parallel": 1,
                        "completed_count": 1,
                        "flushed_count": 1,
                        "pending_count": 0,
                        "failed_count": 0,
                        "image_post_count": 0,
                        "mcp_auto_up_shards": False,
                        "mcp_auto_recreate_shards": False,
                        "mcp_local_shard_management_enabled": False,
                        "mcp_small_run_shard_lifecycle_blocked": True,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            snapshot_path.write_text(
                json.dumps(
                    {
                        "processes": [
                            {
                                "ProcessId": 9001,
                                "ParentProcessId": 123,
                                "CreationDate": "2026-05-31T15:00:00+09:00",
                                "CommandLine": "python expert_main.py --server-type vllm",
                            },
                            {
                                "ProcessId": 9002,
                                "ParentProcessId": 123,
                                "CommandLine": "python helper.py",
                            },
                            {
                                "ProcessId": 9003,
                                "ParentProcessId": 123,
                                "CommandLine": (
                                    "powershell -Command \"Get-CimInstance Win32_Process | "
                                    "Where-Object { $_.CommandLine -match 'expert_main|llm_batch' }\""
                                ),
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            import sys

            old_sys_argv = sys.argv[:]
            try:
                sys.argv = [
                    "audit_goal_test_run_contract.py",
                    "--manifest",
                    str(manifest_path),
                    "--output-json",
                    str(output_json),
                    "--no-require-log",
                    "--collect-process-snapshot",
                    "--process-snapshot-json",
                    str(snapshot_path),
                    "--process-pattern",
                    "expert_main",
                ]
                with mock.patch.object(mod.subprocess, "run") as run_mock:
                    with redirect_stdout(io.StringIO()):
                        exit_code = mod.main()
            finally:
                sys.argv = old_sys_argv

            self.assertEqual(exit_code, 0)
            run_mock.assert_not_called()
            payload = json.loads(output_json.read_text(encoding="utf-8"))
        snapshot = payload["process_snapshot"]
        self.assertTrue(snapshot["enabled"])
        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["source"], str(snapshot_path))
        self.assertEqual(snapshot["input_path"], str(snapshot_path))
        self.assertEqual(snapshot["matching_process_count"], 1)
        self.assertEqual(snapshot["processes"][0]["pid"], 9001)

    def test_cli_missing_log_is_review_when_required(self):
        mod = load_audit_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "manifest.json"
            output_json = root / "audit.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "run_id": "20260531_153000_999999",
                        "input_post_count": 1,
                        "requested_parallel": 36,
                        "effective_parallel": 1,
                        "completed_count": 1,
                        "flushed_count": 1,
                        "pending_count": 0,
                        "failed_count": 0,
                        "image_post_count": 0,
                        "mcp_auto_up_shards": False,
                        "mcp_auto_recreate_shards": False,
                        "mcp_local_shard_management_enabled": False,
                        "mcp_small_run_shard_lifecycle_blocked": True,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            import sys

            old_sys_argv = sys.argv[:]
            try:
                sys.argv = [
                    "audit_goal_test_run_contract.py",
                    "--manifest",
                    str(manifest_path),
                    "--log-dir",
                    str(root / "logs"),
                    "--output-json",
                    str(output_json),
                ]
                with redirect_stdout(io.StringIO()):
                    exit_code = mod.main()
            finally:
                sys.argv = old_sys_argv

            self.assertEqual(exit_code, 0)
            payload = json.loads(output_json.read_text(encoding="utf-8"))
        self.assertEqual(payload["gate"]["runtime_contract"], "REVIEW")
        self.assertFalse(payload["log_evidence_present"])
        self.assertIn("log_evidence_missing", {item["code"] for item in payload["issues"]})

    def test_parallel_and_vlm_contract_violations_are_no_go(self):
        mod = load_audit_module()
        manifest = {
            "input_post_count": 1,
            "requested_parallel": 36,
            "effective_parallel": 8,
            "completed_count": 1,
            "flushed_count": 1,
            "pending_count": 0,
            "failed_count": 0,
            "image_post_count": 1,
            "vlm_enabled": False,
            "ocr_enabled": True,
            "vlm_ocr_semantic_review_ready": False,
            "mcp_auto_up_shards": False,
            "mcp_auto_recreate_shards": False,
            "mcp_local_shard_management_enabled": False,
            "mcp_small_run_shard_lifecycle_blocked": True,
        }

        audit = mod.audit_manifest(manifest)

        codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["gate"]["runtime_contract"], "NO-GO")
        self.assertIn("effective_parallel_exceeds_input_post_count", codes)
        self.assertIn("image_posts_without_vlm_ocr_ready", codes)

    def test_cli_writes_korean_markdown_and_no_go_exit_code(self):
        mod = load_audit_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "manifest.json"
            output_md = root / "audit.md"
            output_json = root / "audit.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "input_post_count": 1,
                        "requested_parallel": 37,
                        "effective_parallel": 1,
                        "completed_count": 1,
                        "flushed_count": 1,
                        "pending_count": 0,
                        "failed_count": 0,
                        "image_post_count": 0,
                        "mcp_auto_up_shards": False,
                        "mcp_auto_recreate_shards": False,
                        "mcp_local_shard_management_enabled": False,
                        "mcp_small_run_shard_lifecycle_blocked": True,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            import sys

            old_sys_argv = sys.argv[:]
            try:
                sys.argv = [
                    "audit_goal_test_run_contract.py",
                    "--manifest",
                    str(manifest_path),
                    "--output-json",
                    str(output_json),
                    "--output-md",
                    str(output_md),
                    "--fail-on-no-go",
                ]
                with redirect_stdout(io.StringIO()):
                    exit_code = mod.main()
            finally:
                sys.argv = old_sys_argv

            self.assertEqual(exit_code, 2)
            self.assertTrue(output_json.exists())
            text = output_md.read_text(encoding="utf-8")
            self.assertIn("# Goal/Test 런 계약 감사", text)
            self.assertIn("## 요약", text)
            self.assertIn("runtime_contract", text)
            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["gate"]["runtime_contract"], "NO-GO")


if __name__ == "__main__":
    unittest.main()
