from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def load_action_queue_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "build_goal_action_queue.py"
    spec = importlib.util.spec_from_file_location("build_goal_action_queue", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample_state_map() -> dict:
    return {
        "map_type": "goal_current_state_map",
        "goal_result_path": "out/expert_result.json",
        "original_run": {
            "input_post_count": 104502,
            "completed_count": 80,
            "flushed_count": 71,
            "pending_count": 9,
            "failed_count": 0,
            "result_rows": 71,
            "partial_signals": [
                "completed_count_lt_input_post_count",
                "pending_count_gt_zero",
                "flushed_count_lt_completed_count",
                "result_rows_lt_completed_count",
            ],
        },
        "source_review_policy": {
            "source_dataset_kind": "partial_final_result_json",
            "source_integrity_classification": "manifest_partial_run",
            "random_baseline": {
                "requested_sample_size": 1000,
                "available_rows": 71,
                "feasible": False,
                "shortfall": 929,
            },
        },
        "small_run_runtime_audit": {
            "runtime_contract": "GO",
            "requested_parallel": 36,
            "effective_parallel": 1,
            "log_evidence_present": True,
            "semantic_approval": "not_evaluated_by_runtime_contract_audit",
            "image_post_count": 1,
            "vlm_ocr_semantic_review_ready": True,
        },
        "reason_hygiene_scan": {
            "gate": "GO",
            "files_scanned": 4,
            "hit_files": 0,
            "hit_type_counts": {},
        },
        "gates": {
            "original_source_approval": "NO-GO",
            "small_run_runtime_contract": "GO",
            "latest_reason_hygiene": "GO",
            "semantic_approval": "REVIEW-LOCKED",
        },
        "critical_blockers": [{"code": "original_manifest_partial"}],
    }


def sample_semantic_coverage_audit() -> dict:
    return {
        "gate": "REVIEW-LOCKED",
        "semantic_approval": {"status": "not_granted_by_semantic_coverage_audit"},
        "coverage": {
            "total_rows": 71,
            "image_evidence_catalog_missing": 37,
            "image_context_without_vlm_catalog": 36,
            "browser_visual_missing": 37,
            "comment_metadata_missing": 55,
            "comment_dialogue_context_missing": 55,
            "final_semantic_reread_missing": 71,
            "final_semantic_reread_required": 4,
            "final_semantic_reread_required_missing": 2,
        },
        "issues": [
            {"code": "image_evidence_catalog_missing", "count": 37},
            {"code": "browser_visual_or_direct_evidence_missing", "count": 37},
        ],
    }


def sample_clean_targeted_state_without_source_preflight() -> dict:
    return {
        "map_type": "goal_current_state_map",
        "goal_result_path": "out/canary/targeted_result.json",
        "original_run": {
            "input_post_count": 1,
            "completed_count": 1,
            "flushed_count": 1,
            "pending_count": 0,
            "failed_count": 0,
            "result_rows": 1,
            "partial_signals": [],
        },
        "source_review_policy": {
            "path_present": False,
            "source_result_path": None,
            "source_dataset_kind": None,
            "source_integrity_classification": None,
            "large_run_complete": None,
            "random_baseline": {},
            "gate": {},
        },
        "small_run_runtime_audit": {
            "runtime_contract": "GO",
            "requested_parallel": 1,
            "effective_parallel": 1,
            "log_evidence_present": True,
            "semantic_approval": "not_evaluated_by_runtime_contract_audit",
            "image_post_count": 1,
            "vlm_ocr_semantic_review_ready": True,
        },
        "reason_hygiene_scan": {
            "gate": "GO",
            "files_scanned": 1,
            "hit_files": 0,
            "hit_type_counts": {},
        },
        "gates": {
            "original_source_approval": "REVIEW",
            "small_run_runtime_contract": "GO",
            "latest_reason_hygiene": "GO",
            "semantic_approval": "REVIEW-LOCKED",
        },
        "critical_blockers": [],
    }


def sample_process_snapshot_audit() -> dict:
    return {
        "gate": {"runtime_contract": "GO"},
        "process_snapshot": {
            "available": True,
            "source": "snapshot.json",
            "patterns": ["expert_main", "llm_batch", "vllm"],
            "matching_process_count": 0,
            "stale_process_candidate_count": 0,
        },
    }


def sample_hardcoded_alias_audit() -> dict:
    return {
        "registry_count": 4,
        "risk_class_counts": {"positive_resolution": 2, "quarantine": 1, "prompt_hint": 1},
        "gate_status_counts": {"INFO": 2, "REVIEW": 1, "REVIEW-LOCKED": 1},
        "gate": {
            "semantic_approval": "REVIEW-LOCKED",
            "positive_hardcoded_alias_blocker_count": 2,
            "quarantine_only_count": 1,
        },
        "positive_hardcoded_alias_blockers": [
            {
                "registry_name": "KNOWN_TITLE_ABBREVIATIONS",
                "file": "src/llm_batch/experts/utils.py",
                "line": 712,
                "gate_status": "REVIEW-LOCKED",
                "usage_kind_counts": {"search_context": 2},
            }
        ],
    }


def sample_hardcoded_alias_packet_review() -> dict:
    return {
        "summary": {
            "gate": "REVIEW",
            "semantic_approval": "not_granted_by_packet_review",
            "packet_coverage": "FOUND",
            "scanned_files": 388,
            "scanned_records": 763,
            "matched_packets": 11,
            "unique_post_context_registry_match_count": 11,
            "registry_match_counts": {"KNOWN_TITLE_ABBREVIATIONS": 13},
            "context_only_registry_match_counts": {
                "KNOWN_TITLE_ABBREVIATIONS": 16,
                "SLANG_DICTIONARY": 1,
            },
            "marker_hit_counts": {},
        }
    }


def sample_hardcoded_alias_packet_labels() -> list[dict]:
    return [
        {
            "review_id": "v409-hap-001",
            "source_packet_id": "out/result.json#1",
            "post_id": 11718120,
            "resolved_title": "괴담 호텔 탈출기",
            "review_label": "HOLD",
            "semantic_decision_quality": "ACCEPT",
            "action": ["human_review", "slang_db_review"],
            "risk_tags": ["provenance_missing"],
            "rationale_ko": "결론은 맞지만 provenance가 없다.",
        },
        {
            "review_id": "v409-hap-002",
            "source_packet_id": "out/result.json#2",
            "post_id": 11718120,
            "resolved_title": "한가인(괴담 호텔 탈출기)",
            "review_label": "REJECT",
            "semantic_decision_quality": "WRONG_CANONICAL_TITLE",
            "action": ["re_judge"],
            "risk_tags": ["wrong_canonical_title"],
            "rationale_ko": "canonical title이 틀어졌다.",
        },
    ]


def sample_closed_hardcoded_alias_packet_labels() -> list[dict]:
    return [
        {
            "review_id": f"v465-hap-{index:03d}",
            "source_packet_id": f"out/result.json#{index}",
            "post_id": 11718120,
            "resolved_title": "괴담 호텔 탈출기",
            "review_label": "ACCEPT",
            "semantic_decision_quality": "CLOSED_BY_V450_CANARY",
            "action": ["no_action"],
            "risk_tags": ["closed_by_v450_canary", "source_registry_present"],
            "rationale_ko": "최신 canary에서 source_registry와 공식 근거가 확인됐다.",
        }
        for index in range(1, 12)
    ]


class GoalActionQueueTest(unittest.TestCase):
    def test_builds_approval_blockers_from_partial_state(self):
        mod = load_action_queue_module()
        queue = mod.build_action_queue(sample_state_map())

        self.assertEqual(queue["summary"]["semantic_approval"], "REVIEW-LOCKED")
        self.assertIn("obtain_completed_vlm_ocr_source", queue["summary"]["approval_blockers"])
        self.assertIn("expanded_random_baseline_1000", queue["summary"]["approval_blockers"])
        actions = {item["action_id"]: item for item in queue["actions"]}
        self.assertFalse(actions["obtain_completed_vlm_ocr_source"]["executable_now"])
        self.assertFalse(actions["small_run_runtime_audit_required"]["executable_now"])
        self.assertEqual(actions["small_run_runtime_audit_required"]["status"], "done")
        self.assertTrue(actions["vlm_ocr_browser_visual_gate"]["requires_browser_visual"])

    def test_missing_completed_source_preflight_remains_approval_blocker(self):
        mod = load_action_queue_module()
        coverage = {
            "gate": "GO",
            "semantic_approval": {"status": "not_granted_by_semantic_coverage_audit"},
            "coverage": {
                "total_rows": 1,
                "browser_visual_missing": 0,
                "image_evidence_catalog_missing": 0,
                "image_context_without_vlm_catalog": 0,
            },
            "issues": [],
        }
        queue = mod.build_action_queue(
            sample_clean_targeted_state_without_source_preflight(),
            semantic_coverage_audit=coverage,
            process_snapshot_audit=sample_process_snapshot_audit(),
        )
        actions = {item["action_id"]: item for item in queue["actions"]}

        self.assertEqual(queue["summary"]["done"], 6)
        self.assertEqual(queue["summary"]["blocked_until_completed_source"], 4)
        self.assertEqual(queue["summary"]["ready_now"], 0)
        self.assertEqual(
            queue["summary"]["approval_blockers"],
            [
                "obtain_completed_vlm_ocr_source",
                "rerun_large_scale_preflight_on_completed_source",
                "expanded_random_baseline_1000",
                "p0_p1_high_risk_expansion",
            ],
        )
        self.assertTrue(
            actions["obtain_completed_vlm_ocr_source"]["evidence"][
                "missing_source_policy_blocks_approval"
            ]
        )
        self.assertTrue(
            actions["rerun_large_scale_preflight_on_completed_source"]["evidence"][
                "missing_source_policy_blocks_approval"
            ]
        )
        self.assertFalse(actions["semantic_coverage_audit_required_for_new_source"]["executable_now"])

    def test_visual_gate_evidence_separates_unique_browser_missing_from_signal_sum(self):
        mod = load_action_queue_module()
        audit = sample_semantic_coverage_audit()
        audit["coverage"]["browser_visual_missing"] = 12
        queue = mod.build_action_queue(sample_state_map(), semantic_coverage_audit=audit)

        action = next(item for item in queue["actions"] if item["action_id"] == "vlm_ocr_browser_visual_gate")

        self.assertEqual(action["evidence"]["source_browser_visual_missing"], 12)
        self.assertEqual(action["evidence"]["visual_gate_blocker_signal_count"], 85)
        self.assertIn("not unique post count", action["evidence"]["visual_gate_missing_count_note"])

    def test_runtime_go_is_done_action_not_semantic_approval(self):
        mod = load_action_queue_module()
        queue = mod.build_action_queue(sample_state_map())
        action = next(item for item in queue["actions"] if item["action_id"] == "small_run_runtime_audit_required")

        self.assertEqual(action["status"], "done")
        self.assertFalse(action["executable_now"])
        self.assertEqual(action["evidence"]["runtime_contract"], "GO")
        self.assertEqual(action["evidence"]["semantic_approval"], "not_evaluated_by_runtime_contract_audit")
        self.assertFalse(action["approval_blocker"])

    def test_markdown_lists_ready_and_blocked_counts(self):
        mod = load_action_queue_module()
        queue = mod.build_action_queue(sample_state_map())
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.md"
            mod.write_markdown(queue, path)
            text = path.read_text(encoding="utf-8")

        self.assertIn("# Goal 실행 큐", text)
        self.assertIn("## 승인 차단 항목", text)
        self.assertIn("## 실행 항목", text)
        self.assertIn("blocked_until_completed_source", text)
        self.assertIn("obtain_completed_vlm_ocr_source", text)
        self.assertIn("small_run_runtime_audit_required", text)

    def test_optional_audits_add_coverage_and_process_actions(self):
        mod = load_action_queue_module()
        queue = mod.build_action_queue(
            sample_state_map(),
            semantic_coverage_audit=sample_semantic_coverage_audit(),
            process_snapshot_audit=sample_process_snapshot_audit(),
            hardcoded_alias_audit=sample_hardcoded_alias_audit(),
            hardcoded_alias_packet_review=sample_hardcoded_alias_packet_review(),
            hardcoded_alias_packet_labels=sample_hardcoded_alias_packet_labels(),
        )

        actions = {item["action_id"]: item for item in queue["actions"]}
        self.assertEqual(queue["summary"]["semantic_coverage_gate"], "REVIEW-LOCKED")
        self.assertTrue(queue["summary"]["process_snapshot_available"])
        self.assertEqual(queue["summary"]["process_snapshot_stale_candidate_count"], 0)
        self.assertEqual(queue["summary"]["hardcoded_alias_gate"], "REVIEW-LOCKED")
        self.assertEqual(queue["summary"]["hardcoded_alias_positive_blocker_count"], 2)
        self.assertEqual(queue["summary"]["hardcoded_alias_packet_gate"], "REVIEW")
        self.assertEqual(queue["summary"]["hardcoded_alias_packet_coverage"], "FOUND")
        self.assertEqual(queue["summary"]["hardcoded_alias_packet_matched"], 11)
        self.assertEqual(queue["summary"]["hardcoded_alias_packet_unique_post_context_matches"], 11)
        self.assertEqual(queue["summary"]["hardcoded_alias_packet_label_gate"], "REVIEW")
        self.assertEqual(queue["summary"]["hardcoded_alias_packet_label_counts"], {"HOLD": 1, "REJECT": 1})
        self.assertIn("modern_semantic_coverage_source_required", queue["summary"]["approval_blockers"])
        self.assertIn("hardcoded_alias_risk_review_required", queue["summary"]["approval_blockers"])
        self.assertIn("hardcoded_alias_packet_review_required", queue["summary"]["approval_blockers"])
        self.assertIn("hardcoded_alias_packet_label_followup", queue["summary"]["approval_blockers"])
        self.assertFalse(actions["modern_semantic_coverage_source_required"]["executable_now"])
        self.assertTrue(actions["modern_semantic_coverage_source_required"]["requires_browser_visual"])
        self.assertEqual(
            actions["modern_semantic_coverage_source_required"]["evidence"]["final_semantic_reread_required"],
            4,
        )
        self.assertEqual(
            actions["modern_semantic_coverage_source_required"]["evidence"]["image_context_without_vlm_catalog"],
            36,
        )
        self.assertEqual(
            actions["process_snapshot_required_for_goal_reruns"]["status"],
            "done",
        )
        self.assertFalse(actions["process_snapshot_required_for_goal_reruns"]["executable_now"])
        self.assertTrue(actions["hardcoded_alias_risk_review_required"]["executable_now"])
        self.assertFalse(actions["hardcoded_alias_risk_review_required"]["requires_completed_source"])
        self.assertEqual(actions["hardcoded_alias_packet_review_required"]["status"], "ready_packet_review")
        self.assertEqual(
            actions["hardcoded_alias_packet_review_required"]["evidence"]["matched_packets"],
            11,
        )
        self.assertEqual(actions["hardcoded_alias_packet_label_followup"]["evidence"]["reject_count"], 1)
        self.assertEqual(actions["hardcoded_alias_packet_label_followup"]["evidence"]["hold_count"], 1)

    def test_packet_review_blocker_closes_when_all_matched_packets_have_accept_labels(self):
        mod = load_action_queue_module()
        queue = mod.build_action_queue(
            sample_state_map(),
            hardcoded_alias_audit=sample_hardcoded_alias_audit(),
            hardcoded_alias_packet_review=sample_hardcoded_alias_packet_review(),
            hardcoded_alias_packet_labels=sample_closed_hardcoded_alias_packet_labels(),
        )

        actions = {item["action_id"]: item for item in queue["actions"]}
        self.assertEqual(queue["summary"]["hardcoded_alias_packet_gate"], "REVIEW")
        self.assertEqual(queue["summary"]["hardcoded_alias_packet_effective_gate"], "GO")
        self.assertTrue(queue["summary"]["hardcoded_alias_packet_closed_by_labels"])
        self.assertEqual(queue["summary"]["hardcoded_alias_packet_unique_post_context_matches"], 11)
        self.assertNotIn(
            "hardcoded_alias_packet_review_required",
            queue["summary"]["approval_blockers"],
        )
        self.assertIn("hardcoded_alias_risk_review_required", queue["summary"]["approval_blockers"])
        self.assertFalse(actions["hardcoded_alias_packet_review_required"]["approval_blocker"])
        self.assertEqual(actions["hardcoded_alias_packet_review_required"]["status"], "closed_by_packet_labels")
        self.assertTrue(actions["hardcoded_alias_packet_review_required"]["evidence"]["closed_by_packet_labels"])
        self.assertEqual(actions["hardcoded_alias_packet_review_required"]["evidence"]["effective_gate"], "GO")
        self.assertFalse(actions["hardcoded_alias_packet_label_followup"]["approval_blocker"])
        self.assertFalse(actions["hardcoded_alias_packet_label_followup"]["executable_now"])
        self.assertEqual(actions["hardcoded_alias_packet_label_followup"]["status"], "closed_by_packet_labels")
        self.assertIn("모두 ACCEPT/no_action", actions["hardcoded_alias_packet_label_followup"]["next_step"])

    def test_current_source_green_audits_are_not_open_convergence_actions(self):
        mod = load_action_queue_module()
        coverage = {
            "gate": "GO",
            "semantic_approval": {"status": "not_granted_by_semantic_coverage_audit"},
            "coverage": {
                "total_rows": 1,
                "browser_visual_missing": 0,
                "image_evidence_catalog_missing": 0,
                "image_context_without_vlm_catalog": 0,
            },
            "issues": [],
        }
        queue = mod.build_action_queue(
            sample_state_map(),
            semantic_coverage_audit=coverage,
            process_snapshot_audit=sample_process_snapshot_audit(),
        )
        actions = {item["action_id"]: item for item in queue["actions"]}

        self.assertEqual(queue["summary"]["done"], 6)
        self.assertEqual(queue["summary"]["blocked_until_completed_source"], 4)
        self.assertEqual(actions["semantic_coverage_audit_required_for_new_source"]["status"], "done")
        self.assertFalse(actions["semantic_coverage_audit_required_for_new_source"]["executable_now"])
        self.assertEqual(actions["small_run_runtime_audit_required"]["status"], "done")
        self.assertEqual(actions["reason_hygiene_before_using_canary"]["status"], "done")
        self.assertEqual(actions["vlm_ocr_browser_visual_gate"]["status"], "done")
        self.assertEqual(actions["preserve_original_as_regression_seed_only"]["status"], "done")
        self.assertEqual(
            [item["action_id"] for item in queue["actions"] if item["status"] != "done"],
            [
                "obtain_completed_vlm_ocr_source",
                "rerun_large_scale_preflight_on_completed_source",
                "expanded_random_baseline_1000",
                "p0_p1_high_risk_expansion",
            ],
        )

    def test_packet_review_closure_uses_unique_post_context_matches(self):
        mod = load_action_queue_module()
        packet_review = sample_hardcoded_alias_packet_review()
        packet_review["summary"]["matched_packets"] = 40
        packet_review["summary"]["unique_post_context_registry_match_count"] = 1
        labels = sample_closed_hardcoded_alias_packet_labels()[:1]
        queue = mod.build_action_queue(
            sample_state_map(),
            hardcoded_alias_audit=sample_hardcoded_alias_audit(),
            hardcoded_alias_packet_review=packet_review,
            hardcoded_alias_packet_labels=labels,
        )

        actions = {item["action_id"]: item for item in queue["actions"]}
        self.assertEqual(queue["summary"]["hardcoded_alias_packet_effective_gate"], "GO")
        self.assertTrue(queue["summary"]["hardcoded_alias_packet_closed_by_labels"])
        self.assertEqual(queue["summary"]["hardcoded_alias_packet_matched"], 40)
        self.assertEqual(queue["summary"]["hardcoded_alias_packet_unique_post_context_matches"], 1)
        self.assertFalse(actions["hardcoded_alias_packet_review_required"]["approval_blocker"])
        self.assertEqual(
            actions["hardcoded_alias_packet_review_required"]["evidence"]["effective_gate"],
            "GO",
        )

    def test_markdown_includes_optional_audit_summary(self):
        mod = load_action_queue_module()
        queue = mod.build_action_queue(
            sample_state_map(),
            semantic_coverage_audit=sample_semantic_coverage_audit(),
            process_snapshot_audit=sample_process_snapshot_audit(),
            hardcoded_alias_audit=sample_hardcoded_alias_audit(),
            hardcoded_alias_packet_review=sample_hardcoded_alias_packet_review(),
            hardcoded_alias_packet_labels=sample_hardcoded_alias_packet_labels(),
        )
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.md"
            mod.write_markdown(queue, path)
            text = path.read_text(encoding="utf-8")

        self.assertIn("semantic_coverage_gate", text)
        self.assertIn("process_snapshot_stale_candidate_count", text)
        self.assertIn("hardcoded_alias_gate", text)
        self.assertIn("hardcoded_alias_packet_gate", text)
        self.assertIn("hardcoded_alias_packet_label_gate", text)
        self.assertIn("modern_semantic_coverage_source_required", text)
        self.assertIn("hardcoded_alias_risk_review_required", text)
        self.assertIn("hardcoded_alias_packet_review_required", text)
        self.assertIn("hardcoded_alias_packet_label_followup", text)


if __name__ == "__main__":
    unittest.main()
