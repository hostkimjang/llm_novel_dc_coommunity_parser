from __future__ import annotations

import copy
import json
import os
import stat
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

from tools.build_interrupted_merge_trust_anchor import (
    _write_json_exclusive,
    build_trust_anchor,
)
from tools.merge_interrupted_run_results import (
    MERGE_BINDING_RECEIPT_FINALIZATION_MARKER,
    _canonical_hash,
    _sha256,
    _write_bytes_exclusive,
    build_merge,
    finalize_merge_binding_receipt,
    validate_finalized_merge_binding_receipt,
    validate_output_preflight,
    validate_premerge_trust_anchor,
    validate_residual_manifest_artifact_paths,
)


def run_meta(
    config_hash: str = "same",
    *,
    run_id: str,
    model: str = "Gemma",
    prompt_version: str = "prompt-v1",
) -> dict:
    return {
        "run_id": run_id,
        "model": model,
        "llm_endpoint": "http://model",
        "llm_mode": "remote",
        "prompt_version": prompt_version,
        "config_hash": config_hash,
        "requested_parallel_raw": 16,
        "requested_parallel": 16,
        "effective_parallel": 16,
        "parallel_policy": "effective_parallel=min(requested_parallel,input_post_count)",
        "model_parallel_max": None,
        "model_parallel_cap_applied": False,
        "model_parallel_cap_model": "Gemma",
        "mcp_health_include_search": True,
        "mcp_health_light_mode": False,
        "mcp_health_required_ok_count": 16,
        "mcp_health_checked_endpoint_count": 16,
        "mcp_health_probe_batch_size": 16,
        "mcp_health_probe_stopped_after_required_ok": False,
        "mcp_health_workers": 12,
        "mcp_health_attempts": 1,
        "mcp_health_timeout_sec": 8.0,
        "mcp_health_search_max_latency_ms": 8000.0,
        "mcp_health_search_min_results": 1,
        "mcp_health_ok_count": 16,
        "mcp_health_failure_count": 0,
        "mcp_healthy_endpoint_filter": False,
        "mcp_healthy_endpoint_filter_reason": "reuse_shards_only",
        "mcp_healthy_endpoint_filter_autogen": True,
        "mcp_healthy_autogen_endpoint_filter": False,
        "mcp_healthy_autogen_endpoint_filter_reason": "reuse_shards_only",
        "mcp_reuse_shards_only_health_filtered": False,
        "mcp_goal_run_health_filtered": False,
        "mcp_requested_endpoint_count_before_health_filter": 16,
        "mcp_healthy_endpoint_count": 16,
        "mcp_endpoint_count_after_health_filter": 16,
        "mcp_parallel_before_health_filter": 16,
        "mcp_parallel_after_health_filter": 16,
    }


def result_row(
    post_id: int,
    config_hash: str = "same",
    *,
    run_id: str,
    model: str = "Gemma",
    prompt_version: str = "prompt-v1",
) -> dict:
    return {
        "post_id": post_id,
        "title": f"row-{post_id}",
        "run_meta": run_meta(
            config_hash,
            run_id=run_id,
            model=model,
            prompt_version=prompt_version,
        ),
    }


def checkpoint(row: dict, global_idx: int) -> dict:
    return {"global_idx": global_idx, "post_id": row["post_id"], "status": "completed", "result": row}


def manifest(
    run_id: str,
    count: int,
    *,
    completed: int | None = None,
    flushed: int | None = None,
    pending: int = 0,
    large_run_complete: bool = True,
) -> dict:
    completed = count if completed is None else completed
    flushed = completed if flushed is None else flushed
    return {
        "run_id": run_id,
        "input_post_count": count,
        "completed_count": completed,
        "flushed_count": flushed,
        "pending_count": pending,
        "failed_count": 0,
        "next_save_idx": flushed + 1,
        "large_run_complete": large_run_complete,
        "llm_model": "Gemma",
        "llm_endpoint": "http://model",
        "llm_stream_first_token_timeout_seconds": "45",
        "llm_stream_idle_timeout_seconds": "45",
        "llm_stream_signal_idle_timeout_seconds": "45",
        "requested_parallel_raw": 16,
        "requested_parallel": 16,
        "effective_parallel": 16,
        "parallel_policy": "effective_parallel=min(requested_parallel,input_post_count)",
        "model_parallel_max": None,
        "model_parallel_cap_applied": False,
        "model_parallel_cap_model": "Gemma",
        "mcp_endpoints": ",".join(f"http://127.0.0.1:{3333 + index}" for index in range(16)),
        "mcp_health_include_search": True,
        "mcp_health_light_mode": False,
        "mcp_health_required_ok_count": 16,
        "mcp_health_checked_endpoint_count": 16,
        "mcp_health_probe_batch_size": 16,
        "mcp_health_probe_stopped_after_required_ok": False,
        "mcp_health_workers": 12,
        "mcp_health_attempts": 1,
        "mcp_health_timeout_sec": 8.0,
        "mcp_health_search_max_latency_ms": 8000.0,
        "mcp_health_search_min_results": 1,
        "mcp_health_ok_count": 16,
        "mcp_health_failure_count": 0,
        "mcp_healthy_endpoint_filter": False,
        "mcp_healthy_endpoint_filter_reason": "reuse_shards_only",
        "mcp_healthy_endpoint_filter_autogen": True,
        "mcp_healthy_autogen_endpoint_filter": False,
        "mcp_healthy_autogen_endpoint_filter_reason": "reuse_shards_only",
        "mcp_reuse_shards_only_health_filtered": False,
        "mcp_goal_run_health_filtered": False,
        "mcp_requested_endpoint_count_before_health_filter": 16,
        "mcp_healthy_endpoint_count": 16,
        "mcp_endpoint_count_after_health_filter": 16,
        "mcp_parallel_before_health_filter": 16,
        "mcp_parallel_after_health_filter": 16,
        "vlm_enabled": True,
        "ocr_enabled": True,
        "vlm_ocr_semantic_review_ready": True,
        "vlm_ocr_semantic_review_required_for_images": True,
        "dashboard_enabled": True,
        "dashboard_mode": "standalone_forward",
        "dashboard_standalone_forwarding": True,
    }


def plan(extra: list[str] | None = None) -> dict:
    required_env = {
        "MCP_HEALTH_INCLUDE_SEARCH": "1",
        "MCP_HEALTH_LIGHT_MODE": "0",
        "MCP_HEALTH_REQUIRED_OK": "16",
        "MCP_HEALTH_PROBE_BATCH_SIZE": "16",
    }
    argv = [
        "python",
        "expert_main.py",
        "input.jsonl",
        "--output",
        "output.json",
        "--llm-model",
        "Gemma",
        "--llm-endpoint",
        "http://model",
        "--reuse-shards-only",
        "--slang-db",
        "off",
        "--parallel",
        "16",
        "--vlm",
        "on",
        "--ocr",
        "on",
        "--require-vlm-ocr-for-images",
    ]
    if extra:
        argv.extend(extra)
    return {
        "required_env": dict(required_env),
        "runtime_contract": {
            "requested_parallel": 16,
            "dashboard_required": True,
            "no_dashboard_forbidden": True,
            "reuse_shards_only": True,
            "slang_db": "off",
            "vlm": "on",
            "ocr": "on",
            "require_vlm_ocr_for_images": True,
            "required_env": dict(required_env),
        },
        "planned_runs": [{"command_argv": argv, "required_env": dict(required_env)}],
    }


def build_inputs() -> dict:
    source = [{"post_id": 1}, {"post_id": 2}, {"post_id": 3}]
    recovered = [result_row(2, "source-size-hash", run_id="source")]
    residual = [
        result_row(1, "residual-size-hash", run_id="residual"),
        result_row(3, "residual-size-hash", run_id="residual"),
    ]
    source_manifest = manifest(
        "source",
        3,
        completed=1,
        flushed=1,
        pending=0,
        large_run_complete=False,
    )
    return {
        "source_rows": source,
        "recovered_rows": recovered,
        "recovered_checkpoint_rows": [checkpoint(recovered[0], 2)],
        "recovery_summary": {
            "run_id": "source",
            "integrity_classification": "recoverable_pending_flush_gap",
            "recovery_safe_to_use_as_completed_subset": True,
            "recovered_rows": 1,
            "checkpoint_completed_rows": 1,
            "checkpoint_failed_rows": 0,
            "manifest": {
                field: source_manifest[field]
                for field in (
                    "input_post_count",
                    "completed_count",
                    "flushed_count",
                    "pending_count",
                    "failed_count",
                    "next_save_idx",
                )
            },
        },
        "source_manifest": source_manifest,
        "residual_input_rows": [source[0], source[2]],
        "residual_rows": residual,
        "residual_checkpoint_rows": [checkpoint(residual[0], 1), checkpoint(residual[1], 2)],
        "residual_pending_rows": [],
        "residual_manifest": manifest("residual", 2),
        "source_plan": plan(),
        "residual_plan": plan(),
        "expected_source_count": 3,
        "expected_recovered_count": 1,
        "expected_residual_count": 2,
    }


class MergeInterruptedRunResultsTest(unittest.TestCase):
    def _trust_fixture(self, root: Path) -> tuple[dict, dict, Path, Path, Path, dict[str, Path]]:
        inputs = build_inputs()
        source_path = root / "panel.jsonl"
        baseline_path = root / "baseline.json"
        golden_path = root / "golden.json"
        source_path.write_text(
            "".join(json.dumps(row) + "\n" for row in inputs["source_rows"]),
            encoding="utf-8",
        )
        baseline_path.write_text(json.dumps(inputs["source_rows"]), encoding="utf-8")
        golden_path.write_text(json.dumps({"rows": [{"post_id": 1}]}), encoding="utf-8")
        (root / "expert_main.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "src").mkdir()
        (root / "src" / "runtime.py").write_text("RUNTIME = 1\n", encoding="utf-8")
        artifact_paths = {
            "recovered": root / "recovered.json",
            "recovery_summary": root / "recovery_summary.json",
            "source_checkpoint": root / "source_checkpoint.jsonl",
            "source_manifest": root / "source_manifest.json",
            "source_plan": root / "source_plan.json",
            "residual_input": root / "residual_input.jsonl",
            "residual_plan": root / "residual_plan.json",
        }
        artifact_paths["recovered"].write_text(
            json.dumps(inputs["recovered_rows"]), encoding="utf-8"
        )
        artifact_paths["recovery_summary"].write_text(
            json.dumps(inputs["recovery_summary"]), encoding="utf-8"
        )
        artifact_paths["source_checkpoint"].write_text(
            "".join(
                json.dumps(row) + "\n" for row in inputs["recovered_checkpoint_rows"]
            ),
            encoding="utf-8",
        )
        artifact_paths["source_manifest"].write_text(
            json.dumps(inputs["source_manifest"]), encoding="utf-8"
        )
        artifact_paths["source_plan"].write_text(
            json.dumps(inputs["source_plan"]), encoding="utf-8"
        )
        artifact_paths["residual_input"].write_text(
            "".join(
                json.dumps(row) + "\n" for row in inputs["residual_input_rows"]
            ),
            encoding="utf-8",
        )
        artifact_paths["residual_plan"].write_text(
            json.dumps(inputs["residual_plan"]), encoding="utf-8"
        )
        partial_manifest = copy.deepcopy(inputs["residual_manifest"])
        partial_manifest.update(
            {
                "completed_count": 1,
                "flushed_count": 1,
                "pending_count": 0,
                "next_save_idx": 2,
                "large_run_complete": False,
            }
        )
        generated_at = datetime.fromtimestamp(time.time() - 10).replace(microsecond=0).isoformat()
        anchor = build_trust_anchor(
            source_rows=inputs["source_rows"],
            baseline_rows=inputs["source_rows"],
            golden_rows=[{"post_id": 1}],
            recovered_rows=inputs["recovered_rows"],
            source_checkpoint_rows=inputs["recovered_checkpoint_rows"],
            recovery_summary=inputs["recovery_summary"],
            source_manifest=inputs["source_manifest"],
            source_plan=inputs["source_plan"],
            residual_partial_rows=[inputs["residual_rows"][0]],
            residual_input_rows=inputs["residual_input_rows"],
            residual_manifest=partial_manifest,
            residual_plan=inputs["residual_plan"],
            source_jsonl=source_path,
            recovered_result_path=artifact_paths["recovered"],
            recovery_summary_path=artifact_paths["recovery_summary"],
            source_checkpoint_path=artifact_paths["source_checkpoint"],
            source_manifest_path=artifact_paths["source_manifest"],
            source_plan_path=artifact_paths["source_plan"],
            residual_input_path=artifact_paths["residual_input"],
            residual_plan_path=artifact_paths["residual_plan"],
            baseline_result=baseline_path,
            golden_manifest=golden_path,
            runtime_root=root,
            expected_source_run_id="source",
            expected_residual_run_id="residual",
            expected_source_count=3,
            expected_recovered_count=1,
            expected_residual_count=2,
            expected_source_flushed_count=1,
            expected_source_pending_count=0,
            expected_golden_count=1,
            expected_panel_sha256=_sha256(source_path),
            expected_baseline_sha256=_sha256(baseline_path),
            expected_golden_sha256=_sha256(golden_path),
            generated_at=generated_at,
            allow_untrusted_test_roots=True,
        )
        anchor_path = root / "trust_anchor.json"
        _write_json_exclusive(anchor_path, anchor)
        final_manifest_path = root / "residual_manifest.json"
        final_manifest_path.write_text(json.dumps(inputs["residual_manifest"]), encoding="utf-8")
        now = time.time()
        anchor_path.chmod(stat.S_IREAD | stat.S_IWRITE)
        os.utime(anchor_path, (now - 5, now - 5))
        os.utime(final_manifest_path, (now, now))
        anchor_path.chmod(stat.S_IREAD)
        return inputs, anchor, anchor_path, final_manifest_path, source_path, artifact_paths

    def test_merges_nonprefix_recovery_in_original_order(self) -> None:
        merged, merged_checkpoint, integrity = build_merge(**build_inputs())

        self.assertEqual([row["post_id"] for row in merged], [1, 2, 3])
        self.assertEqual([row["global_idx"] for row in merged_checkpoint], [1, 2, 3])
        self.assertEqual(integrity["gate"], "GO")
        self.assertTrue(integrity["post_id_integrity"]["original_order_preserved"])
        self.assertEqual(integrity["post_id_integrity"]["missing_post_ids"], [])
        self.assertEqual(
            integrity["runtime_homogeneity"]["component_raw_config_hashes"],
            {"source": "source-size-hash", "residual": "residual-size-hash"},
        )
        self.assertFalse(
            integrity["runtime_homogeneity"]["raw_config_hash_cross_run_equality_required"]
        )
        self.assertIn(
            "input_post_count",
            integrity["runtime_homogeneity"]["raw_config_hash_size_dependent_reason"],
        )

    def test_rejects_overlap_or_missing_partition(self) -> None:
        inputs = build_inputs()
        inputs["residual_rows"] = [
            result_row(1, "residual-size-hash", run_id="residual"),
            result_row(2, "residual-size-hash", run_id="residual"),
        ]
        inputs["residual_checkpoint_rows"] = [
            checkpoint(inputs["residual_rows"][0], 1),
            checkpoint(inputs["residual_rows"][1], 2),
        ]
        with self.assertRaisesRegex(ValueError, "partition mismatch"):
            build_merge(**inputs)

    def test_rejects_residual_result_order_different_from_anchored_input(self) -> None:
        inputs = build_inputs()
        inputs["residual_rows"] = list(reversed(inputs["residual_rows"]))
        with self.assertRaisesRegex(ValueError, "residual result order"):
            build_merge(**inputs)

    def test_rejects_stable_row_runtime_mismatch(self) -> None:
        inputs = build_inputs()
        inputs["residual_rows"] = [
            result_row(
                1,
                "residual-size-hash",
                run_id="residual",
                prompt_version="prompt-v2",
            ),
            result_row(
                3,
                "residual-size-hash",
                run_id="residual",
                prompt_version="prompt-v2",
            ),
        ]
        inputs["residual_checkpoint_rows"] = [
            checkpoint(inputs["residual_rows"][0], 1),
            checkpoint(inputs["residual_rows"][1], 2),
        ]
        with self.assertRaisesRegex(ValueError, "row runtime signature mismatch"):
            build_merge(**inputs)

    def test_rejects_runtime_command_contract_mismatch(self) -> None:
        inputs = build_inputs()
        inputs["residual_plan"] = plan(["--different-runtime-flag"])
        with self.assertRaisesRegex(ValueError, "runtime plan contract mismatch"):
            build_merge(**inputs)

    def test_rejects_incomplete_residual_manifest(self) -> None:
        inputs = build_inputs()
        inputs["residual_manifest"] = copy.deepcopy(inputs["residual_manifest"])
        inputs["residual_manifest"]["flushed_count"] = 1
        with self.assertRaisesRegex(ValueError, "flushed_count mismatch"):
            build_merge(**inputs)

    def test_rejects_recovered_checkpoint_global_idx_not_bound_to_panel(self) -> None:
        inputs = build_inputs()
        inputs["recovered_checkpoint_rows"] = [checkpoint(inputs["recovered_rows"][0], 999)]

        with self.assertRaisesRegex(ValueError, "recovered source checkpoint global_idx mismatch"):
            build_merge(**inputs)

    def test_rejects_residual_checkpoint_global_idx_not_bound_to_residual_order(self) -> None:
        inputs = build_inputs()
        inputs["residual_checkpoint_rows"] = [
            checkpoint(inputs["residual_rows"][0], 2),
            checkpoint(inputs["residual_rows"][1], 1),
        ]

        with self.assertRaisesRegex(ValueError, "residual checkpoint global_idx mismatch"):
            build_merge(**inputs)

    def test_rejects_row_manifest_model_mismatch_even_when_both_cohorts_match(self) -> None:
        inputs = build_inputs()
        inputs["recovered_rows"] = [
            result_row(2, "source-size-hash", run_id="source", model="ROW-MODEL")
        ]
        inputs["residual_rows"] = [
            result_row(1, "residual-size-hash", run_id="residual", model="ROW-MODEL"),
            result_row(3, "residual-size-hash", run_id="residual", model="ROW-MODEL"),
        ]
        inputs["recovered_checkpoint_rows"] = [checkpoint(inputs["recovered_rows"][0], 2)]
        inputs["residual_checkpoint_rows"] = [
            checkpoint(inputs["residual_rows"][0], 1),
            checkpoint(inputs["residual_rows"][1], 2),
        ]

        with self.assertRaisesRegex(ValueError, "row/manifest stable field mismatch"):
            build_merge(**inputs)

    def test_rejects_required_env_sources_that_disagree(self) -> None:
        inputs = build_inputs()
        inputs["residual_plan"] = copy.deepcopy(inputs["residual_plan"])
        inputs["residual_plan"]["required_env"]["MCP_HEALTH_LIGHT_MODE"] = "1"

        with self.assertRaisesRegex(ValueError, "required_env sources disagree"):
            build_merge(**inputs)

    def test_rejects_runtime_contract_stable_subset_mismatch(self) -> None:
        inputs = build_inputs()
        inputs["residual_plan"] = copy.deepcopy(inputs["residual_plan"])
        inputs["residual_plan"]["runtime_contract"]["slang_db"] = "on"

        with self.assertRaisesRegex(ValueError, "runtime plan contract mismatch"):
            build_merge(**inputs)

    def test_rejects_plan_manifest_model_mismatch_even_when_plans_match(self) -> None:
        inputs = build_inputs()
        for key in ("source_plan", "residual_plan"):
            inputs[key] = copy.deepcopy(inputs[key])
            argv = inputs[key]["planned_runs"][0]["command_argv"]
            argv[argv.index("--llm-model") + 1] = "PLAN-ONLY-MODEL"

        with self.assertRaisesRegex(ValueError, "plan/manifest contract mismatch"):
            build_merge(**inputs)

    def test_premerge_trust_anchor_revalidates_completed_residual(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs, anchor, anchor_path, final_manifest_path, source_path, paths = self._trust_fixture(root)
            try:
                binding = validate_premerge_trust_anchor(
                    anchor=anchor,
                    anchor_path=anchor_path,
                    source_jsonl=source_path,
                    recovered_result_path=paths["recovered"],
                    source_checkpoint_rows=inputs["recovered_checkpoint_rows"],
                    source_checkpoint_path=paths["source_checkpoint"],
                    recovery_summary_path=paths["recovery_summary"],
                    source_manifest=inputs["source_manifest"],
                    source_manifest_path=paths["source_manifest"],
                    source_plan=inputs["source_plan"],
                    source_plan_path=paths["source_plan"],
                    recovered_rows=inputs["recovered_rows"],
                    recovery_summary=inputs["recovery_summary"],
                    residual_input_rows=inputs["residual_input_rows"],
                    residual_input_path=paths["residual_input"],
                    residual_manifest=inputs["residual_manifest"],
                    residual_manifest_path=final_manifest_path,
                    residual_plan=inputs["residual_plan"],
                    residual_plan_path=paths["residual_plan"],
                    residual_rows=inputs["residual_rows"],
                    expected_source_count=3,
                    expected_recovered_count=1,
                    expected_residual_count=2,
                    repo_root=root,
                    allow_untrusted_test_roots=True,
                    expected_trust_anchor_sha256=_sha256(anchor_path),
                )
                self.assertEqual(binding["gate"], "GO")
                self.assertEqual(binding["topology_profile"], "interrupted_merge_75_300")
                self.assertEqual(binding["sha256"], _sha256(anchor_path))
                self.assertEqual(
                    binding["stable_runtime_fingerprint_sha256"],
                    anchor["stable_runtime_fingerprint_sha256"],
                )
                with self.assertRaisesRegex(ValueError, "test trust anchor sha256 mismatch"):
                    validate_premerge_trust_anchor(
                        anchor=anchor,
                        anchor_path=anchor_path,
                        source_jsonl=source_path,
                        recovered_result_path=paths["recovered"],
                        source_checkpoint_rows=inputs["recovered_checkpoint_rows"],
                        source_checkpoint_path=paths["source_checkpoint"],
                        recovery_summary_path=paths["recovery_summary"],
                        source_manifest=inputs["source_manifest"],
                        source_manifest_path=paths["source_manifest"],
                        source_plan=inputs["source_plan"],
                        source_plan_path=paths["source_plan"],
                        recovered_rows=inputs["recovered_rows"],
                        recovery_summary=inputs["recovery_summary"],
                        residual_input_rows=inputs["residual_input_rows"],
                        residual_input_path=paths["residual_input"],
                        residual_manifest=inputs["residual_manifest"],
                        residual_manifest_path=final_manifest_path,
                        residual_plan=inputs["residual_plan"],
                        residual_plan_path=paths["residual_plan"],
                        residual_rows=inputs["residual_rows"],
                        expected_source_count=3,
                        expected_recovered_count=1,
                        expected_residual_count=2,
                        repo_root=root,
                        allow_untrusted_test_roots=True,
                        expected_trust_anchor_sha256="0" * 64,
                    )
            finally:
                anchor_path.chmod(stat.S_IREAD | stat.S_IWRITE)

    def test_output_preflight_is_confined_distinct_and_collision_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kwargs = {
                "output_result": root / "result.json",
                "output_checkpoint": root / "checkpoint.jsonl",
                "output_pending": root / "pending.json",
                "output_manifest": root / "manifest.json",
                "output_integrity_json": root / "integrity.json",
                "output_integrity_md": root / "integrity.md",
                "output_binding_receipt": root / "receipt.json",
                "repo_root": root,
                "allow_untrusted_test_roots": True,
            }
            paths = validate_output_preflight(**kwargs)
            self.assertEqual(set(paths), {
                "result", "checkpoint", "pending", "manifest",
                "integrity_json", "integrity_md", "binding_receipt",
            })
            kwargs["output_result"].write_text("collision", encoding="utf-8")
            with self.assertRaisesRegex(FileExistsError, "preflight collision"):
                validate_output_preflight(**kwargs)

    def test_residual_manifest_paths_are_exactly_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = root / "result.json"
            checkpoint_path = root / "checkpoint.jsonl"
            pending = root / "pending.json"
            manifest_payload = {
                "output_file": str(result),
                "checkpoint_jsonl": str(checkpoint_path),
                "pending_snapshot": str(pending),
            }
            validate_residual_manifest_artifact_paths(
                residual_manifest=manifest_payload,
                residual_result=result,
                residual_checkpoint=checkpoint_path,
                residual_pending=pending,
                repo_root=root,
            )
            manifest_payload["output_file"] = str(root / "other.json")
            with self.assertRaisesRegex(ValueError, "output_file path mismatch"):
                validate_residual_manifest_artifact_paths(
                    residual_manifest=manifest_payload,
                    residual_result=result,
                    residual_checkpoint=checkpoint_path,
                    residual_pending=pending,
                    repo_root=root,
                )

    def test_merge_binding_receipt_requires_finalization_and_self_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt_path = root / "receipt.json"
            trust = {
                "path": str(root / "anchor.json"),
                "sha256": "a" * 64,
                "anchor_version": "interrupted-merge-trust-v2",
                "release_fingerprint_sha256": "b" * 64,
            }
            result_binding = {
                "path": str(root / "result.json"),
                "byte_sha256": "c" * 64,
                "canonical_sha256": "d" * 64,
                "size_bytes": 10,
                "row_count": 3,
                "post_id_order_sha256": "e" * 64,
                "post_id_set_sha256": "f" * 64,
            }
            row_binding = {
                "path": str(root / "rows.json"),
                "byte_sha256": "1" * 64,
                "canonical_sha256": "2" * 64,
                "size_bytes": 3,
                "row_count": 0,
            }
            document_binding = {
                "path": str(root / "document.json"),
                "byte_sha256": "3" * 64,
                "canonical_sha256": "4" * 64,
                "size_bytes": 4,
            }
            receipt = finalize_merge_binding_receipt(
                {
                    "gate": "GO",
                    "preflight_paths": {"binding_receipt": str(receipt_path.resolve())},
                    "trust_anchor": trust,
                    "output_artifacts": {
                        "result": result_binding,
                        "checkpoint": row_binding,
                        "pending": row_binding,
                    },
                    "manifest": document_binding,
                    "integrity": document_binding,
                    "integrity_markdown": {
                        "path": str(root / "integrity.md"),
                        "byte_sha256": "5" * 64,
                        "size_bytes": 5,
                    },
                    "approval_boundary": {
                        "production_full_scan_approval": False,
                    },
                }
            )
            self.assertTrue(receipt["finalized"])
            self.assertEqual(
                receipt["finalization"]["marker"],
                MERGE_BINDING_RECEIPT_FINALIZATION_MARKER,
            )
            self.assertEqual(
                validate_finalized_merge_binding_receipt(
                    receipt,
                    receipt_path=receipt_path,
                )["gate"],
                "GO",
            )
            tampered = copy.deepcopy(receipt)
            tampered["gate"] = "NO-GO"
            with self.assertRaisesRegex(ValueError, "not finalized GO"):
                validate_finalized_merge_binding_receipt(tampered)

    def test_merge_output_writer_is_exclusive_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.json"
            try:
                _write_bytes_exclusive(path, b"{}\n")
                self.assertFalse(path.stat().st_mode & stat.S_IWRITE)
                with self.assertRaises(FileExistsError):
                    _write_bytes_exclusive(path, b"replace\n")
            finally:
                if path.exists():
                    path.chmod(stat.S_IREAD | stat.S_IWRITE)

    def test_finalized_receipt_verifies_actual_read_only_artifact_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = {
                "result": root / "result.json",
                "checkpoint": root / "checkpoint.jsonl",
                "pending": root / "pending.json",
                "manifest": root / "manifest.json",
                "integrity": root / "integrity.json",
                "markdown": root / "integrity.md",
                "receipt": root / "receipt.json",
            }
            trust = {
                "path": str((root / "anchor.json").resolve()),
                "sha256": "a" * 64,
                "anchor_version": "interrupted-merge-trust-v2",
                "release_fingerprint_sha256": "b" * 64,
            }
            result_payload = [{"post_id": 1}]
            checkpoint_payload = [checkpoint(result_payload[0], 1)]
            pending_payload: list[dict] = []
            manifest_payload = {"premerge_trust_anchor": trust}
            integrity_payload = {"premerge_trust_anchor": trust}
            payloads = {
                "result": (json.dumps(result_payload) + "\n").encode(),
                "checkpoint": (json.dumps(checkpoint_payload[0]) + "\n").encode(),
                "pending": (json.dumps(pending_payload) + "\n").encode(),
                "manifest": (json.dumps(manifest_payload) + "\n").encode(),
                "integrity": (json.dumps(integrity_payload) + "\n").encode(),
                "markdown": b"# integrity\n",
            }
            try:
                for name, payload in payloads.items():
                    _write_bytes_exclusive(paths[name], payload)
                output_artifacts = {
                    "result": {
                        "path": str(paths["result"].resolve()),
                        "byte_sha256": _sha256(paths["result"]),
                        "canonical_sha256": _canonical_hash(result_payload),
                        "size_bytes": paths["result"].stat().st_size,
                        "row_count": 1,
                        "post_id_order_sha256": _canonical_hash(["1"]),
                        "post_id_set_sha256": _canonical_hash(["1"]),
                    },
                    "checkpoint": {
                        "path": str(paths["checkpoint"].resolve()),
                        "byte_sha256": _sha256(paths["checkpoint"]),
                        "canonical_sha256": _canonical_hash(checkpoint_payload),
                        "size_bytes": paths["checkpoint"].stat().st_size,
                        "row_count": 1,
                    },
                    "pending": {
                        "path": str(paths["pending"].resolve()),
                        "byte_sha256": _sha256(paths["pending"]),
                        "canonical_sha256": _canonical_hash(pending_payload),
                        "size_bytes": paths["pending"].stat().st_size,
                        "row_count": 0,
                    },
                }
                receipt = finalize_merge_binding_receipt(
                    {
                        "gate": "GO",
                        "preflight_paths": {
                            "binding_receipt": str(paths["receipt"].resolve())
                        },
                        "trust_anchor": trust,
                        "output_artifacts": output_artifacts,
                        "manifest": {
                            "path": str(paths["manifest"].resolve()),
                            "byte_sha256": _sha256(paths["manifest"]),
                            "canonical_sha256": _canonical_hash(manifest_payload),
                            "size_bytes": paths["manifest"].stat().st_size,
                        },
                        "integrity": {
                            "path": str(paths["integrity"].resolve()),
                            "byte_sha256": _sha256(paths["integrity"]),
                            "canonical_sha256": _canonical_hash(integrity_payload),
                            "size_bytes": paths["integrity"].stat().st_size,
                        },
                        "integrity_markdown": {
                            "path": str(paths["markdown"].resolve()),
                            "byte_sha256": _sha256(paths["markdown"]),
                            "size_bytes": paths["markdown"].stat().st_size,
                        },
                        "approval_boundary": {
                            "production_full_scan_approval": False,
                        },
                    }
                )
                _write_json_exclusive(paths["receipt"], receipt)
                self.assertEqual(
                    validate_finalized_merge_binding_receipt(
                        json.loads(paths["receipt"].read_text(encoding="utf-8")),
                        receipt_path=paths["receipt"],
                        verify_artifact_bytes=True,
                    )["gate"],
                    "GO",
                )
            finally:
                for path in paths.values():
                    if path.exists():
                        path.chmod(stat.S_IREAD | stat.S_IWRITE)
            tampered = copy.deepcopy(receipt)
            tampered["trust_anchor"]["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "self-digest mismatch"):
                validate_finalized_merge_binding_receipt(tampered)

    def test_premerge_anchor_created_after_completion_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs, anchor, anchor_path, final_manifest_path, source_path, paths = self._trust_fixture(root)
            try:
                now = time.time()
                anchor_path.chmod(stat.S_IREAD | stat.S_IWRITE)
                os.utime(anchor_path, (now, now))
                os.utime(final_manifest_path, (now - 5, now - 5))
                anchor_path.chmod(stat.S_IREAD)
                with self.assertRaisesRegex(ValueError, "not frozen before residual completion"):
                    validate_premerge_trust_anchor(
                        anchor=anchor,
                        anchor_path=anchor_path,
                        source_jsonl=source_path,
                        recovered_result_path=paths["recovered"],
                        source_checkpoint_rows=inputs["recovered_checkpoint_rows"],
                        source_checkpoint_path=paths["source_checkpoint"],
                        recovery_summary_path=paths["recovery_summary"],
                        source_manifest=inputs["source_manifest"],
                        source_manifest_path=paths["source_manifest"],
                        source_plan=inputs["source_plan"],
                        source_plan_path=paths["source_plan"],
                        recovered_rows=inputs["recovered_rows"],
                        recovery_summary=inputs["recovery_summary"],
                        residual_input_rows=inputs["residual_input_rows"],
                        residual_input_path=paths["residual_input"],
                        residual_manifest=inputs["residual_manifest"],
                        residual_manifest_path=final_manifest_path,
                        residual_plan=inputs["residual_plan"],
                        residual_plan_path=paths["residual_plan"],
                        residual_rows=inputs["residual_rows"],
                        expected_source_count=3,
                        expected_recovered_count=1,
                        expected_residual_count=2,
                        repo_root=root,
                        allow_untrusted_test_roots=True,
                        expected_trust_anchor_sha256=_sha256(anchor_path),
                    )
            finally:
                anchor_path.chmod(stat.S_IREAD | stat.S_IWRITE)

    def test_premerge_anchor_rejects_runtime_code_tree_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs, anchor, anchor_path, final_manifest_path, source_path, paths = self._trust_fixture(root)
            try:
                (root / "src" / "runtime.py").write_text("RUNTIME = 2\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "runtime code tree changed"):
                    validate_premerge_trust_anchor(
                        anchor=anchor,
                        anchor_path=anchor_path,
                        source_jsonl=source_path,
                        recovered_result_path=paths["recovered"],
                        source_checkpoint_rows=inputs["recovered_checkpoint_rows"],
                        source_checkpoint_path=paths["source_checkpoint"],
                        recovery_summary_path=paths["recovery_summary"],
                        source_manifest=inputs["source_manifest"],
                        source_manifest_path=paths["source_manifest"],
                        source_plan=inputs["source_plan"],
                        source_plan_path=paths["source_plan"],
                        recovered_rows=inputs["recovered_rows"],
                        recovery_summary=inputs["recovery_summary"],
                        residual_input_rows=inputs["residual_input_rows"],
                        residual_input_path=paths["residual_input"],
                        residual_manifest=inputs["residual_manifest"],
                        residual_manifest_path=final_manifest_path,
                        residual_plan=inputs["residual_plan"],
                        residual_plan_path=paths["residual_plan"],
                        residual_rows=inputs["residual_rows"],
                        expected_source_count=3,
                        expected_recovered_count=1,
                        expected_residual_count=2,
                        repo_root=root,
                        allow_untrusted_test_roots=True,
                        expected_trust_anchor_sha256=_sha256(anchor_path),
                    )
            finally:
                anchor_path.chmod(stat.S_IREAD | stat.S_IWRITE)


if __name__ == "__main__":
    unittest.main()
