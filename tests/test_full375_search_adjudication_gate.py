from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.llm_batch.promotion_gate import (
    EvidenceRecord,
    GroundingState,
    ScopeState,
    apply_publish_contract,
    evaluate_publish_contract,
)
from tools.build_full375_search_adjudication_gate import (
    PRODUCTION_GOLDEN_ROWS,
    PRODUCTION_PANEL_ROWS,
    PRODUCTION_SEARCH_SHARDS,
    _canonical_hash,
    _search_health,
    _source_hash,
    build_terminal_packet,
    build_search_gate,
)


RUN_ID = "20260710_120000_000000"
MODEL = "model"
ENDPOINT = "http://model"
ARTIFACT_PATH = str(Path(__file__).resolve())
ARTIFACT_SHA256 = hashlib.sha256(Path(ARTIFACT_PATH).read_bytes()).hexdigest()


def artifact_ref() -> dict:
    return {"path": ARTIFACT_PATH, "sha256": ARTIFACT_SHA256}


def row(
    post_id: int,
    *,
    title: str | None = None,
    status: str | None = "ok",
    unrecovered: int = 0,
) -> dict:
    if title is not None:
        scope = ScopeState(
            scope_kind="current_work",
            confidence="high",
            direct_bridge_sources=["row_discusses_work_as_work"],
        )
        state = GroundingState(
            post_id=post_id,
            candidate_title=title,
            source="full375_search_gate_test",
            official_title_exists=True,
            row_discusses_work_as_work=True,
            title_resolution_state="resolved",
            work_resolution="resolved",
            scope=scope,
        )
        evidence = [
            EvidenceRecord(
                kind="direct_title_surface",
                source_path_or_snippet=title,
                supports_publish=True,
                reason_code="row_discusses_work_as_work",
                candidate_title=title,
            )
        ]
        identity = {"novel_identity": {"confidence": "High"}}
    else:
        scope = ScopeState(scope_kind="unknown", confidence="high")
        state = GroundingState(
            post_id=post_id,
            candidate_title="Candidate",
            source="full375_search_gate_test",
            official_title_exists=True,
            row_discusses_work_as_work=False,
            title_resolution_state="unresolved_matchable",
            work_resolution="unresolved",
            scope=scope,
        )
        evidence = [
            EvidenceRecord(
                kind="candidate_surface",
                source_path_or_snippet="Candidate",
                supports_publish=False,
                reason_code="row_work_discussion_unverified",
                candidate_title="Candidate",
            )
        ]
        identity = {"novel_identity": None}

    apply_publish_contract(identity, evaluate_publish_contract(state, evidence))

    health = None
    if status is not None:
        degraded = 1 if status in {"SEARCH_DEGRADED", "SEARCH_DEGRADED_RECOVERED"} else 0
        health = {
            "queries_issued": 1,
            "upstream_zero": 0,
            "degraded": degraded,
            "degraded_zero": 0,
            "degraded_recovered": 1 if status == "SEARCH_DEGRADED_RECOVERED" else 0,
            "unrecovered_degraded": unrecovered,
            "status": status,
        }
        identity["search_health"] = health
    return {
        "post_id": post_id,
        "title": "source",
        "content": ["body"],
        "analysis_result": {"identity": identity},
        "run_meta": {
            "run_id": RUN_ID,
            "model": MODEL,
            "llm_endpoint": ENDPOINT,
            "requested_parallel": 16,
            "effective_parallel": 16,
            "mcp_health_include_search": True,
            "mcp_health_light_mode": False,
            "mcp_health_required_ok_count": 16,
            "mcp_health_ok_count": 16,
            "mcp_health_failure_count": 0,
            "search_health": health or {},
        },
    }


def manifest(rows: list[dict], **overrides: object) -> dict:
    post_ids = [str(item["post_id"]) for item in rows]
    payload = {
        "run_id": RUN_ID,
        "generated_at": "2026-07-10T19:00:00",
        "input_post_count": PRODUCTION_PANEL_ROWS,
        "completed_count": PRODUCTION_PANEL_ROWS,
        "flushed_count": PRODUCTION_PANEL_ROWS,
        "pending_count": 0,
        "failed_count": 0,
        "large_run_complete": True,
        "partial_flush_gap": False,
        "ordered_flush_blocked": False,
        "result_payload_sha256": _canonical_hash(rows),
        "input_post_id_order_sha256": _canonical_hash(post_ids),
        "input_post_id_set_sha256": _canonical_hash(sorted(post_ids)),
        "llm_model": MODEL,
        "llm_endpoint": ENDPOINT,
        "requested_parallel": 16,
        "effective_parallel": 16,
        "mcp_health_include_search": True,
        "mcp_health_light_mode": False,
        "mcp_health_required_ok_count": 16,
        "mcp_health_ok_count": 16,
    }
    payload.update(overrides)
    return payload


def query_audit(
    kind: str = "preflight",
    *,
    generated_at: str | None = None,
    count: int = PRODUCTION_SEARCH_SHARDS,
) -> dict:
    when = generated_at or (
        "2026-07-10T11:55:00" if kind == "preflight" else "2026-07-10T20:00:00"
    )
    query = "괴담 호텔 탈출기 웹소설"
    return {
        "generated_at": when,
        "count": count,
        "ok_count": count,
        "bad_count": 0,
        "search_probe_summary": {
            "enabled": True,
            "ok_count": count,
            "bad_count": 0,
            "degraded_count": 0,
            "forbidden_engine_count": 0,
            "query": query,
        },
        "shards": [
            {
                "shard": shard,
                "ok": True,
                "healthz": {"ok": True},
                "readyz": {"ok": True},
                "search_probe": {
                    "ok": True,
                    "query": query,
                    "purpose": f"unit_{kind}",
                },
                "docker": {
                    "warp": {"ok": True},
                    "searchxng": {"ok": True},
                    "mcp_bridge": {"ok": True},
                    "browser_search": {"ok": True},
                },
            }
            for shard in range(1, count + 1)
        ],
    }


def golden_rows(*, positive_post_ids: set[int] | None = None) -> list[dict]:
    positive = positive_post_ids or set()
    return [
        {
            "post_id": post_id,
            "golden_role": "positive_expected_work" if post_id in positive else "negative_no_public_work",
            "expected_no_public_title": post_id not in positive,
        }
        for post_id in range(1, PRODUCTION_GOLDEN_ROWS + 1)
    ]


def terminal(runtime_row: dict) -> dict:
    source_hash = _source_hash(runtime_row)
    identity = runtime_row["analysis_result"]["identity"]
    packet = build_terminal_packet([runtime_row])[0]
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".jsonl",
        delete=False,
    ) as handle:
        handle.write(json.dumps(packet, ensure_ascii=False) + "\n")
        packet_path = handle.name
    packet_ref = {
        "path": packet_path,
        "sha256": hashlib.sha256(Path(packet_path).read_bytes()).hexdigest(),
    }
    return {
        "post_id": runtime_row["post_id"],
        "source_hash": source_hash,
        "input_hash": source_hash,
        "terminal_label": "INFO_MISSING",
        "classification": "safe_no_public_terminal",
        "row_rationale": "검색 근거가 없어 public identity를 세우지 않는 독립 판결이다.",
        "evidence_refs": [artifact_ref()],
        "before_after": {
            "before": {"source_hash": source_hash},
            "after": {
                "official_title": None,
                "official_url": None,
                "publish_allowed": False,
            },
        },
        "blind_verdict": {
            "blind": True,
            "method": "source_native_blind",
            "classification": "safe_no_public_terminal",
            "terminal_label": "INFO_MISSING",
            "reviewer": "judge",
            "model": "gpt-5.6-sol",
            "run_id": "judge-run",
            "review_id": "blind-review-1",
            "packet_ref": packet_ref,
            "packet_sha256": packet_ref["sha256"],
            "packet_row_sha256": packet["packet_row_sha256"],
        },
        "promotion_decision": copy.deepcopy(identity["promotion_decision"]),
        "publish_contract_trace": copy.deepcopy(identity["publish_contract_trace"]),
        "test_replay_artifacts": [artifact_ref()],
        "attempted_lanes": ["search"],
        "missing_or_conflicting_evidence": ["search health missing"],
        "search_health_snapshot_sha256": _canonical_hash(_search_health(runtime_row)),
        "candidate_unavailable_reason": None,
        "publication_violation": False,
        "unblock_condition": "search source becomes available",
        "independent_review": {
            "role": "independent_reviewer",
            "reviewer": "auditor",
            "review_id": "independent-review-1",
            "reviewed_at": "2026-07-10T20:10:00",
            "artifact_ref": artifact_ref(),
        },
    }


class Full375SearchAdjudicationGateTest(unittest.TestCase):
    @staticmethod
    def panel(*special_rows: dict) -> list[dict]:
        by_id = {int(item["post_id"]): item for item in special_rows}
        return [
            by_id.get(post_id) or row(post_id, status="ok")
            for post_id in range(1, PRODUCTION_PANEL_ROWS + 1)
        ]

    def build(
        self,
        rows: list[dict],
        terminals: list[dict] | None = None,
        *,
        positive_golden: set[int] | None = None,
    ) -> dict:
        panel = self.panel(*rows)
        return build_search_gate(
            rows=panel,
            manifest=manifest(panel),
            preflight=query_audit(),
            postflight=query_audit("postflight"),
            terminal_rows=terminals or [],
            golden_rows=golden_rows(positive_post_ids=positive_golden),
            expected_rows=PRODUCTION_PANEL_ROWS,
            expected_shards=PRODUCTION_SEARCH_SHARDS,
            expected_probe_scope="unit",
        )

    def test_publish_dependency_missing_search_is_hard_blocker(self) -> None:
        runtime_row = row(1, title="Published", status=None)
        report = self.build([runtime_row])
        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["required_search_hard_blocker"], 1)

    def test_no_public_missing_search_requires_terminal_ledger(self) -> None:
        runtime_row = row(1, status=None)
        missing = self.build([runtime_row])
        closed = self.build([runtime_row], [terminal(runtime_row)])
        self.assertEqual(missing["unreviewed_search_rows"], 1)
        self.assertEqual(closed["unreviewed_search_rows"], 0)
        self.assertEqual(closed["terminal_adjudicated_search_rows"], 1)
        self.assertEqual(closed["gate"], "GO")

    def test_recovered_only_with_no_unrecovered_is_observation(self) -> None:
        report = self.build([row(1, status="SEARCH_DEGRADED_RECOVERED", unrecovered=0)])
        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["recovered_only_observation_count"], 1)

    def test_query_postflight_degraded_blocks_gate(self) -> None:
        panel = self.panel()
        bad = query_audit("postflight")
        bad["search_probe_summary"]["degraded_count"] = 1
        report = build_search_gate(
            rows=panel,
            manifest=manifest(panel),
            preflight=query_audit(),
            postflight=bad,
            terminal_rows=[],
            golden_rows=golden_rows(),
            expected_probe_scope="unit",
        )
        self.assertIn("postflight_query_degraded_nonzero", report["infrastructure_issues"])

    def test_ok_status_with_unrecovered_degraded_is_still_hard_blocker(self) -> None:
        report = self.build([row(1, title="Published", status="ok", unrecovered=7)])
        self.assertEqual(report["required_search_hard_blocker"], 1)

    def test_ok_status_with_unrecovered_degraded_zero_is_not_clean(self) -> None:
        runtime_row = row(1, title="Published", status="ok")
        health = runtime_row["analysis_result"]["identity"]["search_health"]
        health.update({"degraded": 7, "degraded_zero": 7, "degraded_recovered": 0})
        runtime_row["run_meta"]["search_health"] = copy.deepcopy(health)
        report = self.build([runtime_row])
        self.assertEqual(report["required_search_hard_blocker"], 1)

    def test_minimal_search_health_schema_is_rejected(self) -> None:
        runtime_row = row(1, title="Published", status="ok")
        minimal = {"status": "ok", "unrecovered_degraded": 0}
        runtime_row["analysis_result"]["identity"]["search_health"] = minimal
        runtime_row["run_meta"]["search_health"] = minimal
        report = self.build([runtime_row])
        self.assertEqual(report["required_search_hard_blocker"], 1)

    def test_root_public_title_leak_is_detected_as_publish_dependency(self) -> None:
        runtime_row = row(1, status=None)
        runtime_row["analysis_result"]["identity"]["official_title"] = "LEAKED PUBLIC"
        report = self.build([runtime_row])
        self.assertEqual(report["required_search_hard_blocker"], 1)

    def test_incomplete_or_missing_manifest_fields_are_never_go(self) -> None:
        panel = self.panel()
        bad = manifest(panel, completed_count=0, large_run_complete=False)
        bad.pop("pending_count")
        bad.pop("failed_count")
        report = build_search_gate(
            rows=panel,
            manifest=bad,
            preflight=query_audit(),
            postflight=query_audit("postflight"),
            terminal_rows=[],
            golden_rows=golden_rows(),
            expected_probe_scope="unit",
        )
        self.assertIn("manifest_pending_count_missing", report["infrastructure_issues"])
        self.assertIn("manifest_failed_count_missing", report["infrastructure_issues"])

    def test_stale_or_unrelated_query_audits_are_rejected(self) -> None:
        panel = self.panel()
        stale = query_audit(generated_at="2000-01-01T00:00:00")
        unrelated = query_audit("postflight", generated_at="2000-01-02T00:00:00")
        unrelated["search_probe_summary"]["query"] = "unrelated"
        report = build_search_gate(
            rows=panel,
            manifest=manifest(panel),
            preflight=stale,
            postflight=unrelated,
            terminal_rows=[],
            golden_rows=golden_rows(),
            expected_probe_scope="unit",
        )
        self.assertIn("preflight_stale_for_runtime", report["infrastructure_issues"])
        self.assertIn("postflight_before_runtime_completion", report["infrastructure_issues"])

    def test_expected_scope_cannot_shrink_rows_or_shards(self) -> None:
        one = [row(1)]
        report = build_search_gate(
            rows=one,
            manifest=manifest(one, input_post_count=1, completed_count=1, flushed_count=1, mcp_health_ok_count=1),
            preflight=query_audit(count=1),
            postflight=query_audit("postflight", count=1),
            terminal_rows=[],
            golden_rows=golden_rows(),
            expected_rows=1,
            expected_shards=1,
            expected_probe_scope="unit",
        )
        self.assertIn("production_expected_rows_must_equal_375", report["infrastructure_issues"])
        self.assertIn("production_expected_shards_must_equal_16", report["infrastructure_issues"])

    def test_result_run_ids_and_payload_hash_must_bind_manifest(self) -> None:
        panel = self.panel()
        bad_manifest = manifest(panel)
        for item in panel:
            item["run_meta"]["run_id"] = "unrelated"
        report = build_search_gate(
            rows=panel,
            manifest=bad_manifest,
            preflight=query_audit(),
            postflight=query_audit("postflight"),
            terminal_rows=[],
            golden_rows=golden_rows(),
            expected_probe_scope="unit",
        )
        self.assertTrue(any("result_manifest_run_composition_mismatch" in x for x in report["infrastructure_issues"]))

    def test_top_level_audit_counts_cannot_hide_one_detail_shard(self) -> None:
        panel = self.panel()
        bad = query_audit("postflight")
        bad["shards"] = bad["shards"][:1]
        report = build_search_gate(
            rows=panel,
            manifest=manifest(panel),
            preflight=query_audit(),
            postflight=bad,
            terminal_rows=[],
            golden_rows=golden_rows(),
            expected_probe_scope="unit",
        )
        self.assertIn("postflight_shard_detail_count_mismatch", report["infrastructure_issues"])

    def test_terminal_requires_valid_blind_and_independent_provenance(self) -> None:
        runtime_row = row(1, status=None)
        forged = terminal(runtime_row)
        forged["blind_verdict"] = {"label": "PUBLISH"}
        forged["independent_review"] = "self"
        forged["evidence_refs"] = ["fake"]
        report = self.build([runtime_row], [forged])
        issues = report["unreviewed_search_row_details"][0]["issues"]
        self.assertIn("terminal_independent_review_invalid", issues)
        self.assertTrue(any("terminal_evidence_refs" in issue for issue in issues))

    def test_terminal_blind_packet_payload_tamper_is_rejected(self) -> None:
        runtime_row = row(1, status=None)
        forged = terminal(runtime_row)
        packet_path = Path(forged["blind_verdict"]["packet_ref"]["path"])
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        packet["source"]["reason_lines"] = ["private leak"]
        packet_path.write_text(json.dumps(packet, ensure_ascii=False) + "\n", encoding="utf-8")
        file_hash = hashlib.sha256(packet_path.read_bytes()).hexdigest()
        forged["blind_verdict"]["packet_ref"]["sha256"] = file_hash
        forged["blind_verdict"]["packet_sha256"] = file_hash
        report = self.build([runtime_row], [forged])
        issues = report["unreviewed_search_row_details"][0]["issues"]
        self.assertIn("terminal_blind_packet_source_payload_mismatch", issues)
        self.assertIn("terminal_blind_packet_row_hash_mismatch", issues)

    def test_postflight_must_follow_runtime_completion(self) -> None:
        panel = self.panel()
        report = build_search_gate(
            rows=panel,
            manifest=manifest(panel, generated_at="2026-07-10T19:00:00"),
            preflight=query_audit(),
            postflight=query_audit("postflight", generated_at="2026-07-10T18:00:00"),
            terminal_rows=[],
            golden_rows=golden_rows(),
            expected_probe_scope="unit",
        )
        self.assertIn("postflight_before_runtime_completion", report["infrastructure_issues"])

    def test_positive_golden_search_loss_cannot_be_terminal_exempt(self) -> None:
        runtime_row = row(1, status=None)
        report = self.build([runtime_row], [terminal(runtime_row)], positive_golden={1})
        self.assertEqual(report["required_search_hard_blocker"], 1)
        self.assertEqual(report["terminal_adjudicated_search_rows"], 0)


if __name__ == "__main__":
    unittest.main()
