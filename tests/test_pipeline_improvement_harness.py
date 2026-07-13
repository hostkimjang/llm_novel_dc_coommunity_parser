from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from src.llm_batch.promotion_gate import (
    can_publish_title,
    evidence_records_from_payload,
    grounding_state_from_dict,
)
from tools.run_pipeline_improvement_harness import (
    PROBABILITY_STATUS,
    STATIC_MODE,
    _canonical_hash,
    _sha256_file,
    build_static_projection,
    create_run_spec,
    validate_run_spec,
    write_comparison,
    write_run_spec,
)


RUN_ID = "20260711_000000_000000"
RUNTIME_FINGERPRINT = "a" * 64
MODEL = "test-model"
ENDPOINT = "http://test-model"
PROMPT_VERSION = "test-prompt-v1"
CONFIG_HASH = "test-config-hash"


def result_row(
    post_id: int,
    *,
    title: str | None,
    publish_allowed: bool,
    candidate_preserved: bool,
) -> dict:
    evidence = []
    if title:
        evidence.append(
            {
                "candidate_title": title,
                "candidate_url": f"https://example.test/{post_id}",
                "supports_publish": publish_allowed,
            }
        )
    state_payload = {
        "post_id": post_id,
        "candidate_title": title or "",
        "candidate_url": f"https://example.test/{post_id}" if title else "",
        "source": "pipeline_improvement_harness_test",
        "official_title_exists": bool(title),
        "row_discusses_work_as_work": publish_allowed,
        "title_resolution_state": "resolved" if publish_allowed else "unresolved_matchable",
        "work_resolution": "resolved" if publish_allowed else "unresolved",
        "scope": {
            "scope_kind": "current_work" if publish_allowed else "unknown",
            "confidence": "high",
            "direct_bridge_sources": ["explicit_alias_relation"] if publish_allowed else [],
            "competing_candidates": [],
            "conflict_reason_codes": [],
        },
    }
    decision = can_publish_title(
        grounding_state_from_dict(state_payload), evidence_records_from_payload(evidence)
    ).to_dict()
    if decision["candidate_preserved"] is not candidate_preserved:
        raise AssertionError("fixture candidate_preserved expectation mismatch")
    identity = {
        "novel_identity": (
            {"official_title": decision["official_title"], "official_url": decision["official_url"]}
            if decision["publish_allowed"]
            else None
        ),
        "promotion_decision": decision,
        "promotion_gate_state": state_payload,
        "promotion_gate_evidence": evidence,
    }
    return {
        "post_id": post_id,
        "title": f"source-{post_id}",
        "analysis_result": {"identity": identity},
        "run_meta": {
            "runtime_release_fingerprint_sha256": RUNTIME_FINGERPRINT,
            "run_id": RUN_ID,
            "model": MODEL,
            "llm_endpoint": ENDPOINT,
            "prompt_version": PROMPT_VERSION,
            "config_hash": CONFIG_HASH,
            "requested_parallel": 16,
            "effective_parallel": 16,
            "mcp_health_include_search": True,
            "mcp_health_light_mode": False,
        },
    }


class PipelineImprovementHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.input_path = self.root / "input.jsonl"
        self.baseline_path = self.root / "baseline.json"
        self.gate_path = self.root / "retrieval_gate.json"
        self.baseline_manifest_path = self.root / "baseline_manifest.json"
        self.runtime_plan_path = self.root / "runtime_plan.json"
        self.integrity_path = self.root / "integrity.json"
        self.active_manifest_path = self.root / "expert_result_active_manifest.json"
        self.rows = [
            result_row(1, title="작품 하나", publish_allowed=True, candidate_preserved=False),
            result_row(2, title="작품 둘", publish_allowed=False, candidate_preserved=True),
            result_row(3, title="작품 셋", publish_allowed=True, candidate_preserved=False),
        ]
        self.input_path.write_text(
            "".join(
                json.dumps({"post_id": row["post_id"], "title": row["title"]}, ensure_ascii=False)
                + "\n"
                for row in self.rows
            ),
            encoding="utf-8",
        )
        self.baseline_path.write_text(
            json.dumps(self.rows, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self.gate = {
            "gate": "NO-GO",
            "row_count": 3,
            "required_search_hard_blocker": 2,
            "required_search_hard_blocker_rows": [
                {
                    "post_id": 1,
                    "search_status": "SEARCH_DEGRADED",
                    "unrecovered_degraded": 2,
                    "publish_dependency": True,
                },
                {
                    "post_id": 2,
                    "search_status": "SEARCH_DEGRADED",
                    "unrecovered_degraded": 1,
                    "publish_dependency": True,
                },
            ],
            "artifact_provenance": {},
        }
        self.gate_path.write_text(
            json.dumps(self.gate, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self.baseline_manifest = {
            "run_id": RUN_ID,
            "runtime_release_fingerprint_sha256": RUNTIME_FINGERPRINT,
            "input_post_count": 3,
            "completed_count": 3,
            "flushed_count": 3,
            "pending_count": 0,
            "failed_count": 0,
            "large_run_complete": True,
            "requested_parallel": 16,
            "effective_parallel": 16,
            "llm_model": MODEL,
            "llm_endpoint": ENDPOINT,
            "dashboard_enabled": True,
            "mcp_health_include_search": True,
            "mcp_health_light_mode": False,
            "vlm_enabled": True,
            "ocr_enabled": True,
        }
        self.baseline_manifest_path.write_text(
            json.dumps(self.baseline_manifest), encoding="utf-8"
        )
        self.gate["artifact_provenance"] = {
            "result": {
                "path": str(self.baseline_path),
                "sha256": _sha256_file(self.baseline_path),
            },
            "manifest": {
                "path": str(self.baseline_manifest_path),
                "sha256": _sha256_file(self.baseline_manifest_path),
            },
        }
        self.gate_path.write_text(json.dumps(self.gate), encoding="utf-8")
        self.runtime_plan = {
            "runtime_release_fingerprint_sha256": RUNTIME_FINGERPRINT,
            "source_input": {"sha256": _sha256_file(self.input_path)},
            "output_contract": {
                "output_json": str(self.baseline_path),
                "manifest_json": str(self.baseline_manifest_path),
            },
            "runtime_contract": {
                "model": MODEL,
                "endpoint": ENDPOINT,
                "prompt_version": PROMPT_VERSION,
                "requested_parallel": 16,
                "effective_parallel_expected": 16,
                "dashboard_required": True,
                "search_include": True,
                "search_light_mode": False,
                "slang_db": "off",
                "vlm": "on",
                "ocr": "on",
            },
        }
        self.runtime_plan_path.write_text(json.dumps(self.runtime_plan), encoding="utf-8")
        self.integrity = {
            "runtime_integrity_gate": "GO",
            "run_id": RUN_ID,
            "runtime_release_fingerprint_sha256": RUNTIME_FINGERPRINT,
            "counts": {
                "input": 3,
                "result": 3,
                "checkpoint": 3,
                "pending": 0,
                "failed": 0,
                "missing": 0,
                "extra": 0,
                "duplicate": 0,
            },
            "runtime_contract": {
                "model": MODEL,
                "requested_parallel": 16,
                "effective_parallel": 16,
                "dashboard_enabled": True,
                "search_include": True,
                "search_light_mode": False,
                "healthy_shards": "16/16",
                "slang_db_requested": "off",
                "vlm_enabled": True,
                "ocr_enabled": True,
                "vlm_ocr_ready": True,
            },
            "artifact_sha256": {
                "input": _sha256_file(self.input_path),
                "result": _sha256_file(self.baseline_path),
                "manifest": _sha256_file(self.baseline_manifest_path),
            },
        }
        self.integrity_path.write_text(json.dumps(self.integrity), encoding="utf-8")
        self.active_manifest_path.write_text(
            json.dumps(
                {
                    "run_id": "active",
                    "input_post_count": 100,
                    "completed_count": 4,
                    "flushed_count": 3,
                    "pending_count": 1,
                    "failed_count": 0,
                    "large_run_complete": False,
                    "requested_parallel": 16,
                    "effective_parallel": 16,
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def spec(self) -> dict:
        return create_run_spec(
            input_path=self.input_path,
            baseline_path=self.baseline_path,
            baseline_manifest_path=self.baseline_manifest_path,
            runtime_plan_path=self.runtime_plan_path,
            integrity_artifact_path=self.integrity_path,
            retrieval_gate_path=self.gate_path,
            active_manifest_path=self.active_manifest_path,
        )

    def refresh_baseline_bindings(self) -> None:
        self.gate["artifact_provenance"]["result"]["sha256"] = _sha256_file(
            self.baseline_path
        )
        self.gate_path.write_text(json.dumps(self.gate), encoding="utf-8")
        self.integrity["artifact_sha256"]["result"] = _sha256_file(self.baseline_path)
        self.integrity_path.write_text(json.dumps(self.integrity), encoding="utf-8")

    def write_spec(self) -> Path:
        path = self.root / "harness" / "run_spec.json"
        write_run_spec(self.spec(), path)
        return path

    def test_freeze_binds_artifacts_and_post_ids(self) -> None:
        spec = self.spec()
        self.assertEqual(STATIC_MODE, spec["mode"])
        self.assertEqual(3, spec["post_contract"]["row_count"])
        self.assertEqual(2, spec["retrieval_contract"]["required_search_hard_blocker"])
        self.assertEqual(RUN_ID, spec["baseline_runtime_contract"]["run_id"])
        self.assertEqual(PROMPT_VERSION, spec["baseline_runtime_contract"]["prompt_version"])
        self.assertEqual(CONFIG_HASH, spec["baseline_runtime_contract"]["config_hash"])
        self.assertIn("promotion_gate", spec["implementation_contract"]["artifacts"])
        payload = {key: value for key, value in spec.items() if key != "run_spec_sha256"}
        self.assertEqual(_canonical_hash(payload), spec["run_spec_sha256"])
        self.assertFalse(spec["future_runtime_contract"]["runtime_executed_in_this_phase"])
        self.assertFalse(spec["active_production_run"]["runtime_execution_allowed"])

    def test_projection_blocks_unsafe_publish_and_preserves_candidate(self) -> None:
        report = build_static_projection(self.write_spec())
        self.assertEqual({"before": 1, "after": 0, "delta": -1}, report["before_after"]["unsafe_publish"])
        self.assertEqual(2, report["before_after"]["decision_changed_rows"])
        self.assertEqual(1, report["before_after"]["decision_status_changed_rows"])
        self.assertEqual(2, report["before_after"]["typed_gate_invoked_rows"])
        self.assertEqual(2, report["before_after"]["baseline_gate_replay_exact_rows"])
        self.assertEqual(1, report["before_after"]["public_output_changed_rows"])
        self.assertEqual(0, report["before_after"]["candidate_missing_after"])
        self.assertEqual("GO", report["gates"]["retrieval_failclose_safety"])
        self.assertEqual("NO-GO", report["gates"]["retrieval_evidence"])
        self.assertEqual(
            "PARTIAL_SAFETY_IMPROVEMENT_NOT_RUNTIME_VALIDATED",
            report["gates"]["overall"],
        )
        targeted = {str(row["post_id"]): row for row in report["rows"] if row["targeted_required_search_failclose"]}
        self.assertFalse(targeted["1"]["after_projection"]["public_exposed"])
        self.assertTrue(targeted["1"]["after_projection"]["candidate_preserved"])
        self.assertIn(
            "search_evidence_missing",
            targeted["1"]["after_projection"]["reason_codes"],
        )
        self.assertFalse(targeted["2"]["after_projection"]["public_exposed"])

    def test_probability_is_not_fabricated(self) -> None:
        report = build_static_projection(self.write_spec())
        self.assertEqual(PROBABILITY_STATUS, report["accuracy_percentage_shadow"]["status"])
        self.assertIsNone(report["accuracy_percentage_shadow"]["ece"])
        for row in report["rows"]:
            self.assertEqual(PROBABILITY_STATUS, row["accuracy_percentage_shadow"]["status"])
            self.assertIsNone(row["accuracy_percentage_shadow"]["p_resolve"])

    def test_frozen_baseline_decision_must_replay_exactly(self) -> None:
        rows = copy.deepcopy(self.rows)
        rows[0]["analysis_result"]["identity"]["promotion_decision"]["status"] = "candidate_only"
        self.baseline_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        self.refresh_baseline_bindings()
        with self.assertRaisesRegex(ValueError, "does not reproduce frozen baseline decision"):
            build_static_projection(self.write_spec())

    def test_mixed_runtime_metadata_is_rejected(self) -> None:
        rows = copy.deepcopy(self.rows)
        rows[1]["run_meta"]["config_hash"] = "different-config"
        self.baseline_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        self.refresh_baseline_bindings()
        with self.assertRaisesRegex(ValueError, "mixed runtime metadata"):
            self.spec()

    def test_duplicate_input_post_id_is_rejected(self) -> None:
        with self.input_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"post_id": 1}) + "\n")
        with self.assertRaisesRegex(ValueError, "duplicate post_id"):
            self.spec()

    def test_post_id_order_mismatch_is_rejected(self) -> None:
        reversed_rows = list(reversed(self.rows))
        self.baseline_path.write_text(json.dumps(reversed_rows, ensure_ascii=False), encoding="utf-8")
        self.refresh_baseline_bindings()
        with self.assertRaisesRegex(ValueError, "post_id_order_sha256 mismatch"):
            self.spec()

    def test_artifact_tamper_after_freeze_is_rejected(self) -> None:
        spec_path = self.write_spec()
        rows = copy.deepcopy(self.rows)
        rows[0]["title"] = "tampered"
        self.baseline_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "artifact sha256 mismatch"):
            validate_run_spec(spec_path)

    def test_run_spec_self_hash_tamper_is_rejected(self) -> None:
        spec_path = self.write_spec()
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        spec["future_runtime_contract"]["requested_parallel"] = 8
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "self hash mismatch"):
            validate_run_spec(spec_path)

    def test_runtime_parallel_other_than_16_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires --runtime-parallel 16"):
            create_run_spec(
                input_path=self.input_path,
                baseline_path=self.baseline_path,
                baseline_manifest_path=self.baseline_manifest_path,
                runtime_plan_path=self.runtime_plan_path,
                integrity_artifact_path=self.integrity_path,
                retrieval_gate_path=self.gate_path,
                runtime_parallel=8,
            )

    def test_active_result_prefix_output_is_rejected(self) -> None:
        spec = self.spec()
        output = self.root / "expert_result_active_projection.json"
        with self.assertRaisesRegex(ValueError, "overlaps active production result prefix"):
            write_run_spec(spec, output)

    def test_candidate_missing_keeps_safety_gate_closed(self) -> None:
        rows = copy.deepcopy(self.rows)
        rows[1]["analysis_result"]["identity"]["promotion_gate_evidence"] = []
        rows[1]["analysis_result"]["identity"]["promotion_decision"]["candidate_preserved"] = False
        rows[1]["analysis_result"]["identity"]["promotion_gate_state"]["candidate_title"] = ""
        rows[1]["analysis_result"]["identity"]["promotion_gate_state"]["candidate_url"] = ""
        identity = rows[1]["analysis_result"]["identity"]
        identity["promotion_decision"] = can_publish_title(
            grounding_state_from_dict(identity["promotion_gate_state"]),
            evidence_records_from_payload(identity["promotion_gate_evidence"]),
        ).to_dict()
        identity["novel_identity"] = None
        self.baseline_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        self.refresh_baseline_bindings()
        report = build_static_projection(self.write_spec())
        self.assertEqual(1, report["before_after"]["candidate_missing_after"])
        self.assertEqual("NO-GO", report["gates"]["retrieval_failclose_safety"])

    def test_comparison_writes_korean_markdown_without_overwrite(self) -> None:
        spec_path = self.write_spec()
        report = build_static_projection(spec_path)
        json_path = self.root / "harness" / "comparison.json"
        md_path = self.root / "harness" / "comparison.md"
        written_json, written_md = write_comparison(
            report,
            output_json=json_path,
            output_md=md_path,
            active_manifest=self.active_manifest_path,
        )
        self.assertTrue(written_json.is_file())
        markdown = written_md.read_text(encoding="utf-8")
        self.assertIn("검색 미복구 상태의 작품 공개", markdown)
        self.assertIn("정확도 퍼센트", markdown)
        with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
            write_comparison(
                report,
                output_json=json_path,
                output_md=self.root / "harness" / "second.md",
                active_manifest=self.active_manifest_path,
            )


if __name__ == "__main__":
    unittest.main()
