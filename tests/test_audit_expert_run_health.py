import json
import tempfile
import unittest
from pathlib import Path

from tools.audit_expert_run_health import (
    _build_flush_integrity,
    _build_search_evidence_gate,
    _count_result_rows,
    _load_input_post_lookup,
    _resolve_run_artifacts,
)


class AuditExpertRunHealthTest(unittest.TestCase):
    def test_resolves_launcher_prefix_from_manifest_run_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            out = repo / "out"
            logs = repo / "logs"
            out.mkdir()
            logs.mkdir()
            manifest = out / "expert_result_20260702_065632_479765_manifest.json"
            manifest.write_text(
                json.dumps({"run_id": "20260702_065642_030743"}, ensure_ascii=False),
                encoding="utf-8",
            )

            artifacts = _resolve_run_artifacts("20260702_065642_030743", repo=repo)

            self.assertEqual(artifacts["resolution"], "manifest_run_id_lookup")
            self.assertEqual(artifacts["artifact_prefix"], "20260702_065632_479765")
            self.assertEqual(artifacts["manifest"], manifest)
            self.assertEqual(
                artifacts["checkpoint"],
                out / "expert_result_20260702_065632_479765_checkpoint.jsonl",
            )
            self.assertEqual(
                artifacts["pending"],
                out / "expert_result_20260702_065632_479765_pending_snapshot.json",
            )

    def test_prefers_direct_prefix_when_manifest_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            out = repo / "out"
            logs = repo / "logs"
            out.mkdir()
            logs.mkdir()
            manifest = out / "expert_result_run123_manifest.json"
            manifest.write_text(json.dumps({"run_id": "run123"}), encoding="utf-8")

            artifacts = _resolve_run_artifacts("run123", repo=repo)

            self.assertEqual(artifacts["resolution"], "direct_prefix")
            self.assertEqual(artifacts["artifact_prefix"], "run123")
            self.assertEqual(artifacts["manifest"], manifest)

    def test_explicit_paths_override_default_expert_result_locations(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            sampling = repo / "out" / "sampling"
            logs = repo / "logs"
            sampling.mkdir(parents=True)
            logs.mkdir()
            manifest = sampling / "custom_manifest.json"
            checkpoint = sampling / "custom_checkpoint.jsonl"
            result_json = sampling / "custom_result.json"
            pending = sampling / "custom_pending.json"
            worker_log = logs / "custom_W0.log"
            manifest.write_text(json.dumps({"run_id": "sample-run"}), encoding="utf-8")
            checkpoint.write_text("", encoding="utf-8")
            result_json.write_text("[]", encoding="utf-8")
            pending.write_text("[]", encoding="utf-8")
            worker_log.write_text("worker log", encoding="utf-8")

            artifacts = _resolve_run_artifacts(
                "sample-run",
                repo=repo,
                manifest_path=str(manifest),
                checkpoint_path=str(checkpoint),
                result_json_path=str(result_json),
                pending_snapshot_path=str(pending),
                log_glob=str(logs / "custom_*.log"),
            )

            self.assertEqual(artifacts["resolution"], "explicit_paths")
            self.assertEqual(
                artifacts["explicit_overrides"],
                ["manifest", "checkpoint", "result_json", "pending_snapshot", "log_glob"],
            )
            self.assertEqual(artifacts["manifest"], manifest)
            self.assertEqual(artifacts["checkpoint"], checkpoint)
            self.assertEqual(artifacts["result_json"], result_json)
            self.assertEqual(artifacts["pending"], pending)
            self.assertEqual(artifacts["log_files"], [worker_log])

    def test_missing_explicit_manifest_does_not_fallback_to_run_id_lookup(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            out = repo / "out"
            logs = repo / "logs"
            out.mkdir()
            logs.mkdir()
            fallback_manifest = out / "expert_result_fallback_manifest.json"
            missing_manifest = out / "sampling" / "missing_manifest.json"
            fallback_manifest.write_text(json.dumps({"run_id": "sample-run"}), encoding="utf-8")

            artifacts = _resolve_run_artifacts(
                "sample-run",
                repo=repo,
                manifest_path=str(missing_manifest),
            )

            self.assertEqual(artifacts["resolution"], "explicit_paths")
            self.assertEqual(artifacts["manifest"], missing_manifest)
            self.assertNotEqual(artifacts["manifest"], fallback_manifest)

    def test_counts_result_rows_from_supported_json_shapes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            list_json = base / "list.json"
            rows_json = base / "rows.json"
            missing_json = base / "missing.json"
            list_json.write_text(json.dumps([{"post_id": 1}, {"post_id": 2}]), encoding="utf-8")
            rows_json.write_text(json.dumps({"rows": [1, 2, 3]}), encoding="utf-8")

            self.assertEqual(_count_result_rows(list_json)["row_count"], 2)
            self.assertEqual(_count_result_rows(list_json)["shape"], "list")
            self.assertEqual(_count_result_rows(rows_json)["row_count"], 3)
            self.assertEqual(_count_result_rows(rows_json)["shape"], "dict.rows")
            self.assertEqual(_count_result_rows(missing_json)["row_count"], None)
            self.assertEqual(_count_result_rows(missing_json)["exists"], False)
            self.assertEqual(_count_result_rows(missing_json)["load_error"], "missing")

    def test_input_post_lookup_uses_post_map_order_and_ignores_comment_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.jsonl"
            rows = [
                {"post_id": 100, "title": "first", "url": "https://example.test/100"},
                {"comment_id": "c1", "post_id": 100, "content": "comment"},
                {"post_id": 200, "title": "second", "url": "https://example.test/200"},
            ]
            input_path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
                encoding="utf-8",
            )

            lookup = _load_input_post_lookup(input_path)
            posts_by_idx = lookup["_posts_by_global_idx"]

            self.assertEqual(lookup["post_count"], 2)
            self.assertEqual(lookup["comment_row_count"], 1)
            self.assertEqual(posts_by_idx[1]["post_id"], 100)
            self.assertEqual(posts_by_idx[1]["source_line"], 1)
            self.assertEqual(posts_by_idx[2]["post_id"], 200)
            self.assertEqual(posts_by_idx[2]["source_line"], 3)

    def test_flush_integrity_go_for_clean_completed_source(self):
        audit = _build_flush_integrity(
            manifest_data={
                "input_post_count": 2,
                "completed_count": 2,
                "flushed_count": 2,
                "pending_count": 0,
                "failed_count": 0,
                "large_run_complete": True,
                "ordered_flush_blocked": False,
                "partial_flush_gap": False,
                "next_save_idx": 2,
            },
            status_counts={"completed": 2},
            result_audit={"row_count": 2},
            pending_count_actual=0,
            pending_samples=[],
            checkpoint_completed_indexes=[1, 2],
            pending_global_indexes=[],
            input_post_lookup={2: {"global_idx": 2, "post_id": 200, "title": "second"}},
        )

        self.assertEqual(audit["run_integrity_gate"], "GO")
        self.assertEqual(audit["classification"], "clean_completed_source")
        self.assertEqual(audit["blockers"], [])
        self.assertTrue(audit["completion_ready"])
        self.assertEqual(audit["frontier"]["status"], "ready_to_flush_or_flush_lag")
        self.assertEqual(audit["frontier"]["source_post"]["post_id"], 200)

    def test_flush_integrity_in_progress_for_ordered_flush_gap(self):
        audit = _build_flush_integrity(
            manifest_data={
                "input_post_count": 10,
                "completed_count": 6,
                "flushed_count": 4,
                "pending_count": 2,
                "failed_count": 0,
                "large_run_complete": False,
                "ordered_flush_blocked": True,
                "partial_flush_gap": True,
                "next_save_idx": 5,
            },
            status_counts={"completed": 6},
            result_audit={"row_count": 4},
            pending_count_actual=2,
            pending_samples=[{"global_idx": 5, "post_id": 123, "title": "held"}],
            checkpoint_completed_indexes=[1, 2, 3, 4, 6, 7],
            pending_global_indexes=[6, 7],
            input_post_lookup={5: {"global_idx": 5, "post_id": 500, "title": "frontier"}},
        )

        self.assertEqual(audit["run_integrity_gate"], "IN_PROGRESS")
        self.assertEqual(audit["classification"], "ordered_flush_gap_in_progress")
        self.assertIn("completed_count_lt_input_post_count", audit["blockers"])
        self.assertIn("flushed_count_lt_completed_count", audit["blockers"])
        self.assertIn("pending_count_gt_zero", audit["blockers"])
        self.assertIn("large_run_completion_not_proven", audit["blockers"])
        self.assertTrue(audit["consistency"]["result_rows_eq_flushed_count"])
        self.assertEqual(audit["pending_blocker_samples"][0]["post_id"], 123)
        self.assertEqual(audit["frontier"]["status"], "in_flight_or_missing")
        self.assertEqual(audit["frontier"]["frontier_gap_global_idx"], 5)
        self.assertEqual(audit["frontier"]["first_pending_at_or_after_frontier"], 6)
        self.assertEqual(audit["frontier"]["source_post"]["post_id"], 500)

    def test_flush_integrity_no_go_for_count_mismatch(self):
        audit = _build_flush_integrity(
            manifest_data={
                "input_post_count": 10,
                "completed_count": 6,
                "flushed_count": 4,
                "pending_count": 1,
                "failed_count": 0,
                "large_run_complete": False,
                "ordered_flush_blocked": True,
                "partial_flush_gap": True,
            },
            status_counts={"completed": 6},
            result_audit={"row_count": 3},
            pending_count_actual=2,
            pending_samples=[],
        )

        self.assertEqual(audit["run_integrity_gate"], "NO-GO")
        self.assertEqual(audit["classification"], "artifact_count_mismatch")
        self.assertIn("result_rows_ne_flushed_count", audit["blockers"])
        self.assertIn("pending_snapshot_rows_ne_manifest_pending", audit["blockers"])

    def test_search_evidence_requires_separate_audit_for_light_health_only(self):
        audit = _build_search_evidence_gate(
            manifest_data={
                "mcp_health_include_search": False,
                "mcp_health_light_mode": True,
                "mcp_health_ok_count": 36,
                "mcp_health_failure_count": 0,
            },
            rows=[],
            log_audit={"counts": {}},
        )

        self.assertEqual(audit["gate"], "SEPARATE_AUDIT_REQUIRED")
        self.assertFalse(audit["approval_ready"])
        self.assertFalse(audit["direct_probe_in_manifest"])
        self.assertIn("manifest_search_health_not_included", audit["blockers"])
        self.assertIn("manifest_light_health_only", audit["blockers"])

    def test_search_evidence_no_go_for_manifest_health_failures(self):
        audit = _build_search_evidence_gate(
            manifest_data={
                "mcp_health_include_search": True,
                "mcp_health_light_mode": False,
                "mcp_health_ok_count": 35,
                "mcp_health_failure_count": 1,
            },
            rows=[],
            log_audit={"counts": {}},
        )

        self.assertEqual(audit["gate"], "NO-GO")
        self.assertIn("mcp_health_failure_count_gt_zero", audit["blockers"])

    def test_search_evidence_reviews_row_or_log_degradation(self):
        audit = _build_search_evidence_gate(
            manifest_data={
                "mcp_health_include_search": True,
                "mcp_health_light_mode": False,
                "mcp_health_ok_count": 36,
                "mcp_health_failure_count": 0,
            },
            rows=[
                {
                    "result": {
                        "analysis_result": {
                            "identity": {
                                "search_health": {
                                    "queries_issued": 3,
                                    "upstream_zero": 1,
                                    "degraded": 1,
                                    "degraded_zero": 1,
                                    "status": "SEARCH_DEGRADED",
                                },
                                "search_health_flags": ["search_degraded_or_timeout"],
                            }
                        }
                    }
                }
            ],
            log_audit={"counts": {"search_timeout": 1, "search_degraded_detected": 1}},
        )

        self.assertEqual(audit["gate"], "REVIEW")
        self.assertEqual(audit["row_search_health"]["rows_with_search_health"], 1)
        self.assertEqual(audit["row_search_health"]["rows_with_degraded"], 1)
        self.assertEqual(audit["worker_log_search"]["search_timeout"], 1)
        self.assertIn("search_timeout_observed", audit["blockers"])
        self.assertIn("search_degraded_observed", audit["blockers"])


if __name__ == "__main__":
    unittest.main()
