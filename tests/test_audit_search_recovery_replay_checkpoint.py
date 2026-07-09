from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.audit_search_recovery_replay_checkpoint import audit_replay, write_markdown


def _row(
    post_id: int,
    status: str,
    *,
    degraded: int = 0,
    unrecovered: int = 0,
    include_health: bool = True,
    null_title: bool = False,
    is_relevant: bool = True,
    is_resolved_work_discussion: bool | None = None,
    title_resolution_allowed: bool | None = None,
    work_resolution: str | None = None,
    context_sources: list[str] | None = None,
    search_evidence_catalog: list[dict] | None = None,
    promotion_decision: dict | None = None,
) -> dict:
    identity = {
        "is_relevant": is_relevant,
        "is_resolved_work_discussion": (
            (not null_title) if is_resolved_work_discussion is None else is_resolved_work_discussion
        ),
        "title_resolution_allowed": (
            (not null_title) if title_resolution_allowed is None else title_resolution_allowed
        ),
        "work_resolution": work_resolution or ("none" if null_title else "resolved"),
        "context_sources": context_sources or ["title", "body", "search"],
        "novel_identity": None if null_title else {"official_title": f"title {post_id}"},
    }
    if search_evidence_catalog is not None:
        identity["search_evidence_catalog"] = search_evidence_catalog
    if promotion_decision is not None:
        identity["promotion_decision"] = promotion_decision
    if include_health:
        identity["search_health"] = {
            "status": status,
            "queries_issued": 3,
            "degraded": degraded,
            "degraded_recovered": max(degraded - unrecovered, 0),
            "unrecovered_degraded": unrecovered,
        }
    return {
        "post_id": post_id,
        "analysis_result": {
            "identity": identity,
        },
    }


class AuditSearchRecoveryReplayCheckpointTest(unittest.TestCase):
    def test_partial_degraded_subset_is_no_go(self) -> None:
        report = audit_replay(
            recovered_rows=[
                _row(1, "SEARCH_DEGRADED", degraded=2, unrecovered=1),
                _row(2, "SEARCH_DEGRADED_RECOVERED", degraded=1, unrecovered=0),
            ],
            input_manifest={"summary": {"runtime_input_rows": 3}},
            recovery_summary={"large_run_complete": False, "checkpoint_completed_rows": 2},
            audit_id="test",
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["summary"]["completed_rows"], 2)
        self.assertEqual(report["summary"]["status_counts"]["SEARCH_DEGRADED"], 1)
        self.assertIn("partial_replay_not_all_deferred_rows_completed", report["summary"]["blockers"])
        self.assertIn("row_search_hard_blocker_observed", report["summary"]["blockers"])
        self.assertIn("unrecovered_degraded_queries_observed", report["summary"]["blockers"])

    def test_complete_all_ok_subset_is_go(self) -> None:
        report = audit_replay(
            recovered_rows=[_row(1, "ok"), _row(2, "ok")],
            input_manifest={"summary": {"runtime_input_rows": 2}},
            recovery_summary={"large_run_complete": True, "checkpoint_completed_rows": 2},
            audit_id="test",
        )

        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["summary"]["non_ok_row_count"], 0)
        self.assertEqual(report["summary"]["blockers"], [])

    def test_recovered_degraded_observations_do_not_hard_block(self) -> None:
        report = audit_replay(
            recovered_rows=[
                _row(1, "SEARCH_DEGRADED_RECOVERED", degraded=2, unrecovered=0),
                _row(2, "ok", degraded=1, unrecovered=0),
            ],
            input_manifest={"summary": {"runtime_input_rows": 2}},
            recovery_summary={"large_run_complete": True, "checkpoint_completed_rows": 2},
            audit_id="test",
        )

        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["summary"]["hard_blocker_row_count"], 0)
        self.assertEqual(report["summary"]["recovered_observation_row_count"], 2)
        self.assertEqual(report["summary"]["total_unrecovered_degraded"], 0)

    def test_missing_search_health_hard_blocks(self) -> None:
        report = audit_replay(
            recovered_rows=[_row(1, "MISSING", include_health=False)],
            input_manifest={"summary": {"runtime_input_rows": 1}},
            recovery_summary={"large_run_complete": True, "checkpoint_completed_rows": 1},
            audit_id="test",
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["summary"]["missing_search_health_row_count"], 1)
        self.assertEqual(report["summary"]["hard_missing_search_health_row_count"], 1)
        self.assertIn("search_health_missing_observed", report["summary"]["blockers"])

    def test_missing_search_health_without_search_needed_is_observation(self) -> None:
        report = audit_replay(
            recovered_rows=[
                _row(
                    11710021,
                    "MISSING",
                    include_health=False,
                    null_title=True,
                    is_relevant=False,
                    is_resolved_work_discussion=False,
                    title_resolution_allowed=False,
                    work_resolution="none",
                    context_sources=["title", "body", "comments"],
                    promotion_decision={
                        "status": "candidate_only",
                        "publish_allowed": False,
                        "official_title": None,
                    },
                )
            ],
            input_manifest={"summary": {"runtime_input_rows": 1}},
            recovery_summary={"large_run_complete": True, "checkpoint_completed_rows": 1},
            audit_id="test",
        )

        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["summary"]["missing_search_health_row_count"], 1)
        self.assertEqual(report["summary"]["hard_missing_search_health_row_count"], 0)
        self.assertEqual(report["summary"]["search_not_required_observation_row_count"], 1)
        self.assertEqual(report["summary"]["blockers"], [])
        self.assertIsNone(report["rows"][0]["search_blocker_reason"])
        self.assertEqual(report["rows"][0]["search_missing_observation"], "search_not_required_null_result")

    def test_missing_search_health_with_search_catalog_still_hard_blocks(self) -> None:
        report = audit_replay(
            recovered_rows=[
                _row(
                    1,
                    "MISSING",
                    include_health=False,
                    null_title=True,
                    is_relevant=False,
                    is_resolved_work_discussion=False,
                    title_resolution_allowed=False,
                    work_resolution="none",
                    context_sources=["title", "body"],
                    search_evidence_catalog=[{"query": "title probe", "url": "https://example.test"}],
                )
            ],
            input_manifest={"summary": {"runtime_input_rows": 1}},
            recovery_summary={"large_run_complete": True, "checkpoint_completed_rows": 1},
            audit_id="test",
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["summary"]["hard_missing_search_health_row_count"], 1)
        self.assertEqual(report["summary"]["search_not_required_observation_row_count"], 0)
        self.assertIn("search_health_missing_observed", report["summary"]["blockers"])

    def test_accepts_expert_run_health_summary_shape(self) -> None:
        report = audit_replay(
            recovered_rows=[_row(1, "ok")],
            input_manifest={"summary": {"runtime_input_rows": 1}},
            recovery_summary={
                "run_id": "run-1",
                "result_rows": 1,
                "checkpoint_rows": 1,
                "manifest": {"large_run_complete": True},
                "flush_integrity": {
                    "classification": "clean_completed_source",
                    "completion_ready": True,
                    "blockers": [],
                    "counts": {
                        "checkpoint_completed_count": 1,
                        "checkpoint_failed_count": 0,
                        "result_rows": 1,
                    },
                },
            },
            audit_id="test",
        )

        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["recovery_summary"]["run_id"], "run-1")
        self.assertEqual(report["recovery_summary"]["integrity_classification"], "clean_completed_source")
        self.assertTrue(report["recovery_summary"]["large_run_complete"])
        self.assertEqual(report["recovery_summary"]["checkpoint_completed_rows"], 1)

    def test_markdown_interpretation_matches_go_gate(self) -> None:
        report = audit_replay(
            recovered_rows=[_row(1, "ok")],
            input_manifest={"summary": {"runtime_input_rows": 1}},
            recovery_summary={"large_run_complete": True, "checkpoint_completed_rows": 1},
            audit_id="test",
        )

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "audit.md"
            write_markdown(report, output)
            text = output.read_text(encoding="utf-8")

        self.assertIn("검색 복구 gate를 통과", text)
        self.assertIn("full375 collateral GO나 full_scan approval이 아니다", text)


if __name__ == "__main__":
    unittest.main()
