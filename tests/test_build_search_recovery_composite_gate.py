from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from llm_batch.promotion_gate import (
    EvidenceRecord,
    GroundingState,
    ScopeState,
    apply_publish_contract,
    evaluate_publish_contract,
)
from tools.audit_publication_contract_convergence import audit_rows as audit_publication_rows
from tools.audit_regression_safe_golden import build_audit as build_golden_audit
from tools.build_full375_search_adjudication_gate import (
    build_terminal_packet,
    build_terminal_template,
)
from tools.build_search_recovery_composite_gate import (
    _artifact,
    _uniform_row_contract,
    build_composite_gate,
    expected_runtime_config_hash,
    file_sha256,
)


class SearchRecoveryCompositeGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    @staticmethod
    def write_json(path: Path, value: object) -> None:
        path.write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def write_jsonl(path: Path, rows: list[dict]) -> None:
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )

    @staticmethod
    def search_health(*, clean: bool) -> dict:
        return {
            "queries_issued": 2,
            "upstream_zero": 0,
            "degraded": 0 if clean else 1,
            "degraded_zero": 0 if clean else 1,
            "degraded_recovered": 0,
            "unrecovered_degraded": 0 if clean else 1,
            "status": "ok" if clean else "SEARCH_DEGRADED",
        }

    @staticmethod
    def identity(post_id: int, *, published: bool) -> dict:
        title = f"작품 {post_id}" if published else None
        state = GroundingState(
            post_id=post_id,
            candidate_title=title if published else "",
            candidate_url=f"https://example.test/work/{post_id}" if published else "",
            source="search_recovery_test" if published else "hold_without_candidates",
            official_title_exists=published,
            row_discusses_work_as_work=published,
            title_resolution_state="resolved" if published else "",
            work_resolution="resolved" if published else "",
            scope=(
                ScopeState(
                    scope_kind="current_work",
                    confidence="high",
                    direct_bridge_sources=["explicit_alias_relation", "official_detail_url"],
                )
                if published
                else ScopeState(
                    scope_kind="unknown",
                    confidence="low",
                    conflict_reason_codes=["hold_without_candidates"],
                )
            ),
        )
        evidence = (
            [
                EvidenceRecord(
                    kind="alias_bridge",
                    source_path_or_snippet=title or "",
                    supports_publish=True,
                    reason_code="explicit_alias_relation",
                    candidate_title=title,
                ),
                EvidenceRecord(
                    kind="official_detail_url",
                    source_path_or_snippet=f"https://example.test/work/{post_id}",
                    reason_code="official_detail_url",
                    candidate_title=title,
                    candidate_url=f"https://example.test/work/{post_id}",
                    title_url_match=True,
                ),
            ]
            if published
            else []
        )
        identity: dict = {}
        apply_publish_contract(identity, evaluate_publish_contract(state, evidence))
        return identity

    def manifest(self, path: Path, *, count: int, run_id: str) -> dict:
        endpoints = ",".join(f"http://127.0.0.1:{3332 + index}" for index in range(1, 17))
        return {
            "run_id": run_id,
            "output_file": str(path),
            "runtime_release_fingerprint_sha256": "a" * 64,
            "requested_parallel_raw": 16,
            "requested_parallel": 16,
            "effective_parallel": min(count, 16),
            "parallel_count": min(count, 16),
            "parallel_policy": "effective_parallel=min(requested_parallel,input_post_count)",
            "model_parallel_max": None,
            "model_parallel_cap_applied": False,
            "model_parallel_cap_model": "bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4",
            "llm_model": "bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4",
            "llm_endpoint": "http://10.20.0.101:8000",
            "llm_stream_first_token_timeout_seconds": 45.0,
            "llm_stream_idle_timeout_seconds": 45.0,
            "llm_stream_signal_idle_timeout_seconds": 45.0,
            "dashboard_enabled": True,
            "dashboard_mode": "standalone_forward",
            "dashboard_standalone_forwarding": True,
            "input_post_count": count,
            "vlm_enabled": True,
            "ocr_enabled": True,
            "vlm_ocr_semantic_review_ready": True,
            "vlm_ocr_semantic_review_required_for_images": True,
            "vlm_ocr_semantic_review_blocker": False,
            "mcp_endpoints": endpoints,
            "mcp_auto_up_shards": False,
            "mcp_auto_recreate_shards": False,
            "mcp_auto_scale_up_missing_shards": False,
            "mcp_local_shard_management_enabled": False,
            "mcp_local_shard_status_audit": False,
            "mcp_local_shard_status_audit_requested": False,
            "mcp_local_shard_status_audit_allowed": False,
            "mcp_shard_lifecycle_policy": "test-policy",
            "mcp_allow_goal_shard_lifecycle": False,
            "mcp_command_shard_lifecycle_allowed": False,
            "mcp_interactive_codex_run": True,
            "mcp_env_shard_lifecycle_requested": False,
            "mcp_env_shard_lifecycle_global_opt_in": False,
            "mcp_env_shard_lifecycle_allowed": False,
            "mcp_env_shard_lifecycle_blocked_by_context": False,
            "mcp_shard_lifecycle_block_threshold": 36,
            "mcp_run_post_count_for_lifecycle": count,
            "mcp_small_targeted_run": True,
            "mcp_small_run_shard_lifecycle_blocked": True,
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
            "mcp_missing_shard_scale_up_allowed": False,
            "mcp_missing_shard_scale_up_triggered": False,
            "mcp_missing_shard_scale_up_shards": "",
            "mcp_missing_shard_scale_up_recovered_endpoints": 0,
            "mcp_missing_shard_scale_up_error": "",
            "mcp_healthy_endpoint_filter": False,
            "mcp_healthy_endpoint_filter_reason": "reuse_shards_only",
            "mcp_healthy_endpoint_filter_autogen": False,
            "mcp_healthy_autogen_endpoint_filter": False,
            "mcp_healthy_autogen_endpoint_filter_reason": "reuse_shards_only",
            "mcp_reuse_shards_only_health_filtered": False,
            "mcp_goal_run_health_filtered": False,
            "mcp_requested_endpoint_count_before_health_filter": 16,
            "mcp_healthy_endpoint_count": 16,
            "mcp_endpoint_count_after_health_filter": 16,
            "mcp_parallel_before_health_filter": min(count, 16),
            "mcp_parallel_after_health_filter": min(count, 16),
            "completed_count": count,
            "flushed_count": count,
            "pending_count": 0,
            "failed_count": 0,
            "partial_flush_gap": False,
            "ordered_flush_blocked": False,
            "large_run_complete": True,
        }

    def result_rows(
        self,
        post_ids: list[int],
        *,
        manifest: dict,
        dirty_ids: set[int] | None = None,
    ) -> list[dict]:
        dirty_ids = dirty_ids or set()
        rows: list[dict] = []
        for worker_id, post_id in enumerate(post_ids):
            published = post_id <= 6
            meta = {
                "runtime_release_fingerprint_sha256": "a" * 64,
                "run_id": manifest["run_id"],
                "model": manifest["llm_model"],
                "llm_mode": "remote",
                "llm_endpoint": manifest["llm_endpoint"],
                "prompt_version": "2026-03-30-semantic-contract-v1",
                "config_hash": "pending",
                "requested_parallel_raw": 16,
                "requested_parallel": 16,
                "effective_parallel": manifest["effective_parallel"],
                "parallel_policy": manifest["parallel_policy"],
                "model_parallel_max": None,
                "model_parallel_cap_applied": False,
                "model_parallel_cap_model": manifest["llm_model"],
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
                "mcp_healthy_endpoint_filter_autogen": False,
                "mcp_healthy_autogen_endpoint_filter": False,
                "mcp_healthy_autogen_endpoint_filter_reason": "reuse_shards_only",
                "mcp_reuse_shards_only_health_filtered": False,
                "mcp_goal_run_health_filtered": False,
                "mcp_requested_endpoint_count_before_health_filter": 16,
                "mcp_healthy_endpoint_count": 16,
                "mcp_endpoint_count_after_health_filter": 16,
                "mcp_parallel_before_health_filter": manifest["effective_parallel"],
                "mcp_parallel_after_health_filter": manifest["effective_parallel"],
                "worker_id": worker_id,
                "search_health": self.search_health(clean=post_id not in dirty_ids),
            }
            rows.append(
                {
                    "post_id": post_id,
                    "title": f"source {post_id}",
                    "content": f"본문 {post_id}",
                    "comments": [],
                    "analysis_result": {"identity": self.identity(post_id, published=published)},
                    "run_meta": meta,
                }
            )
        row_contract, _ = _uniform_row_contract(rows)
        config_hash = expected_runtime_config_hash(manifest, row_contract)
        for row in rows:
            row["run_meta"]["config_hash"] = config_hash
        return rows

    @staticmethod
    def query_audit(*, phase: str, scope: str) -> dict:
        shards = []
        for shard in range(1, 17):
            shards.append(
                {
                    "shard": shard,
                    "ok": True,
                    "healthz": {"ok": True},
                    "readyz": {"ok": True},
                    "search_probe": {
                        "ok": True,
                        "degraded": False,
                        "query": "검색 복구 검증",
                        "purpose": f"{scope}_{phase}",
                    },
                    "docker": {
                        name: {"ok": True}
                        for name in ("warp", "searchxng", "mcp_bridge", "browser_search")
                    },
                }
            )
        return {
            "generated_at": (
                "2026-07-10T11:59:00+09:00" if phase == "preflight" else "2026-07-10T12:05:00+09:00"
            ),
            "count": 16,
            "ok_count": 16,
            "bad_count": 0,
            "search_probe_summary": {
                "enabled": True,
                "query": "검색 복구 검증",
                "ok_count": 16,
                "bad_count": 0,
                "degraded_count": 0,
                "forbidden_engine_count": 0,
            },
            "shards": shards,
        }

    def fixture(self) -> dict:
        original_result = self.root / "original.json"
        original_manifest = self.root / "original_manifest.json"
        golden_manifest = self.root / "golden.json"
        prepare_gate = self.root / "prepare.json"
        terminal_ledger = self.root / "terminal.jsonl"
        consensus_report = self.root / "consensus.json"

        original_manifest_payload = self.manifest(
            original_result, count=18, run_id="20260710_120000_000001"
        )
        original_rows = self.result_rows(
            list(range(1, 19)), manifest=original_manifest_payload, dirty_ids=set(range(1, 11))
        )
        golden_rows = [
            {
                "post_id": post_id,
                "golden_role": "positive_expected_work" if post_id <= 6 else "negative_no_public_work",
                "failure_class": "unit",
                "severity": "high",
                "expected_no_public_title": post_id > 6,
                "expected_title_or_hypothesis": f"작품 {post_id}" if post_id <= 6 else None,
                "note": "unit",
            }
            for post_id in range(1, 19)
        ]
        self.write_json(original_result, original_rows)
        self.write_json(original_manifest, original_manifest_payload)
        self.write_json(golden_manifest, {"rows": golden_rows})
        self.write_json(
            prepare_gate,
            {
                "report_type": "full375_search_adjudication_gate",
                "row_count": 18,
                "required_search_hard_blocker": 6,
                "unreviewed_search_rows": 4,
                "required_search_hard_blocker_rows": [{"post_id": post_id} for post_id in range(1, 7)],
                "unreviewed_search_row_details": [{"post_id": post_id} for post_id in range(7, 11)],
                "artifact_provenance": {
                    "result": {"path": str(original_result), "sha256": file_sha256(original_result)},
                    "manifest": {"path": str(original_manifest), "sha256": file_sha256(original_manifest)},
                    "golden_manifest": {"path": str(golden_manifest), "sha256": file_sha256(golden_manifest)},
                },
            },
        )

        packet_path = self.root / "packet.jsonl"
        blind_path = self.root / "blind.json"
        independent_path = self.root / "independent.json"
        self.write_json(blind_path, {"kind": "blind"})
        self.write_json(independent_path, {"kind": "independent"})
        terminal_source_rows = [original_rows[8], original_rows[9]]
        packet_rows = build_terminal_packet(terminal_source_rows)
        self.write_jsonl(packet_path, packet_rows)
        packet_ref = {"path": str(packet_path), "sha256": file_sha256(packet_path)}
        artifact_refs = [
            packet_ref,
            {"path": str(blind_path), "sha256": file_sha256(blind_path)},
            {"path": str(independent_path), "sha256": file_sha256(independent_path)},
        ]
        terminal_rows = build_terminal_template(
            terminal_source_rows, packet_rows=packet_rows, packet_ref=packet_ref
        )
        for row in terminal_rows:
            row.update(
                {
                    "terminal_label": "INFO_MISSING",
                    "classification": "safe_no_public_terminal",
                    "row_rationale": "두 독립 검토가 public null 안전 종결에 합의했다.",
                    "evidence_refs": copy.deepcopy(artifact_refs),
                    "test_replay_artifacts": copy.deepcopy(artifact_refs),
                    "attempted_lanes": ["blind review", "independent review"],
                    "missing_or_conflicting_evidence": ["검색 근거가 불완전하다."],
                    "candidate_unavailable_reason": "공식 작품 후보를 확정할 근거가 없다.",
                    "publication_violation": False,
                    "unblock_condition": "새 공식 근거가 생기면 재검토한다.",
                    "independent_review": {
                        "role": "independent_reviewer",
                        "reviewer": "independent",
                        "review_id": "independent-id",
                        "reviewed_at": "2026-07-10T12:10:00+09:00",
                        "artifact_ref": artifact_refs[2],
                    },
                }
            )
            packet = next(item for item in packet_rows if item["post_id"] == row["post_id"])
            row["blind_verdict"].update(
                {
                    "blind": True,
                    "method": "source_native_blind",
                    "classification": "safe_no_public_terminal",
                    "terminal_label": "INFO_MISSING",
                    "reviewer": "blind",
                    "model": "codex-subagent",
                    "run_id": "blind-run",
                    "review_id": "blind-id",
                    "packet_ref": packet_ref,
                    "packet_sha256": packet_ref["sha256"],
                    "packet_row_sha256": packet["packet_row_sha256"],
                }
            )
        self.write_jsonl(terminal_ledger, terminal_rows)
        self.write_json(
            consensus_report,
            {
                "report_type": "search_terminal_consensus_report_v2",
                "builder_gate": "GO",
                "consensus_post_ids": [9, 10],
                "excluded_rows": [
                    {
                        "post_id": post_id,
                        "blind": {"classification": "blocker", "terminal_safe": False},
                    }
                    for post_id in (7, 8)
                ],
                "input_artifacts": {
                    "result": {"path": str(original_result), "sha256": file_sha256(original_result)}
                },
                "output_artifacts": {
                    "ledger": {
                        "path": str(terminal_ledger),
                        "sha256": file_sha256(terminal_ledger),
                        "row_count": 2,
                    }
                },
            },
        )

        replay_groups = []
        for group_index, post_ids in enumerate((list(range(1, 7)), [7, 8]), 1):
            result_path = self.root / f"replay{group_index}.json"
            manifest_path = self.root / f"replay{group_index}_manifest.json"
            preflight_path = self.root / f"replay{group_index}_pre.json"
            postflight_path = self.root / f"replay{group_index}_post.json"
            publication_path = self.root / f"replay{group_index}_publication.json"
            golden_audit_path = self.root / f"replay{group_index}_golden.json"
            manifest_payload = self.manifest(
                result_path,
                count=len(post_ids),
                run_id=f"20260710_120000_00000{group_index + 1}",
            )
            rows = self.result_rows(post_ids, manifest=manifest_payload)
            self.write_json(result_path, rows)
            self.write_json(manifest_path, manifest_payload)
            self.write_json(preflight_path, self.query_audit(phase="preflight", scope=f"replay{group_index}"))
            self.write_json(postflight_path, self.query_audit(phase="postflight", scope=f"replay{group_index}"))
            publication = audit_publication_rows(rows)
            publication["result_artifacts"] = [_artifact(result_path, row_count=len(rows))]
            self.write_json(publication_path, publication)
            golden_audit = build_golden_audit(
                canary_rows=rows,
                golden_rows=golden_rows,
                run_manifest=manifest_payload,
                canary_result=result_path,
                canary_manifest=manifest_path,
                golden_manifest=golden_manifest,
            )
            self.write_json(golden_audit_path, golden_audit)
            replay_groups.append(
                {
                    "result": result_path,
                    "manifest": manifest_path,
                    "preflight": preflight_path,
                    "postflight": postflight_path,
                    "publication": publication_path,
                    "golden": golden_audit_path,
                }
            )
        return {
            "original_result": original_result,
            "original_manifest": original_manifest,
            "prepare": prepare_gate,
            "golden": golden_manifest,
            "terminal": terminal_ledger,
            "consensus": consensus_report,
            "replays": replay_groups,
        }

    def build(self, fixture: dict) -> dict:
        replays = fixture["replays"]
        return build_composite_gate(
            original_result=fixture["original_result"],
            original_manifest=fixture["original_manifest"],
            original_search_prepare_gate=fixture["prepare"],
            golden_manifest=fixture["golden"],
            replay_results=[item["result"] for item in replays],
            replay_manifests=[item["manifest"] for item in replays],
            replay_preflights=[item["preflight"] for item in replays],
            replay_postflights=[item["postflight"] for item in replays],
            replay_publication_audits=[item["publication"] for item in replays],
            replay_golden_audits=[item["golden"] for item in replays],
            terminal_ledger=fixture["terminal"],
            terminal_consensus_report=fixture["consensus"],
        )

    def test_happy_path_accounts_exact_6_plus_2_replay_and_2_terminal(self) -> None:
        fixture = self.fixture()
        report = self.build(fixture)
        self.assertEqual(report["gate"], "GO", report["blockers"])
        self.assertEqual(report["required_search_hard_blocker"], 0)
        self.assertEqual(report["unreviewed_search_rows"], 0)
        self.assertEqual(
            report["original_issue_accounting"]["replay_union_post_ids"],
            [str(value) for value in range(1, 9)],
        )
        self.assertEqual(
            report["original_issue_accounting"]["terminal_consensus_safe_post_ids"],
            ["9", "10"],
        )
        self.assertFalse(report["semantic_result_policy"]["best_of_semantic_merge_performed"])

    def test_missing_extra_and_duplicate_replay_coverage_fail_closed(self) -> None:
        mutations = {
            "missing": lambda rows: rows[:-1],
            "extra": lambda rows: rows[:-1] + [copy.deepcopy(rows[0]) | {"post_id": 11}],
            "duplicate": lambda rows: rows + [copy.deepcopy(rows[0])],
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                fixture = self.fixture()
                path = fixture["replays"][0]["result"]
                rows = json.loads(path.read_text(encoding="utf-8"))
                self.write_json(path, mutate(rows))
                report = self.build(fixture)
                self.assertEqual(report["gate"], "NO-GO")
                self.assertTrue(any("coverage" in issue or "replay_union" in issue for issue in report["blockers"]))

    def test_dirty_row_search_fails_closed(self) -> None:
        fixture = self.fixture()
        path = fixture["replays"][0]["result"]
        rows = json.loads(path.read_text(encoding="utf-8"))
        rows[0]["run_meta"]["search_health"] = self.search_health(clean=False)
        self.write_json(path, rows)
        report = self.build(fixture)
        self.assertTrue(any("row_search" in issue for issue in report["blockers"]))

    def test_runtime_fingerprint_and_config_drift_fail_closed(self) -> None:
        for field, value, expected in (
            ("runtime_release_fingerprint_sha256", "b" * 64, "runtime_contract_drift"),
            ("config_hash", "forged-config", "config_hash_not_slang_db_off_contract"),
        ):
            with self.subTest(field=field):
                fixture = self.fixture()
                path = fixture["replays"][0]["result"]
                rows = json.loads(path.read_text(encoding="utf-8"))
                for row in rows:
                    row["run_meta"][field] = value
                self.write_json(path, rows)
                report = self.build(fixture)
                self.assertTrue(any(expected in issue for issue in report["blockers"]))

    def test_publication_and_golden_failure_fail_closed(self) -> None:
        fixture = self.fixture()
        publication_path = fixture["replays"][0]["publication"]
        publication = json.loads(publication_path.read_text(encoding="utf-8"))
        publication["gate"] = "NO-GO"
        self.write_json(publication_path, publication)
        golden_path = fixture["replays"][1]["golden"]
        golden = json.loads(golden_path.read_text(encoding="utf-8"))
        target = next(row for row in golden["rows"] if row["post_id"] == 7)
        target["passed"] = False
        self.write_json(golden_path, golden)
        report = self.build(fixture)
        self.assertTrue(any("publication_gate_not_go" in issue for issue in report["blockers"]))
        self.assertTrue(any("golden_replay_semantic_not_pass" in issue for issue in report["blockers"]))

    def test_terminal_forgery_fails_even_when_consensus_hash_is_rebound(self) -> None:
        fixture = self.fixture()
        terminal_rows = [json.loads(line) for line in fixture["terminal"].read_text(encoding="utf-8").splitlines()]
        terminal_rows[0]["promotion_decision"]["publish_allowed"] = True
        self.write_jsonl(fixture["terminal"], terminal_rows)
        consensus = json.loads(fixture["consensus"].read_text(encoding="utf-8"))
        consensus["output_artifacts"]["ledger"]["sha256"] = file_sha256(fixture["terminal"])
        self.write_json(fixture["consensus"], consensus)
        report = self.build(fixture)
        self.assertTrue(any("terminal_promotion_decision_mismatch" in issue for issue in report["blockers"]))

    def test_preflight_or_postflight_degraded_fails_closed(self) -> None:
        fixture = self.fixture()
        path = fixture["replays"][0]["preflight"]
        audit = json.loads(path.read_text(encoding="utf-8"))
        audit["search_probe_summary"]["degraded_count"] = 1
        self.write_json(path, audit)
        report = self.build(fixture)
        self.assertTrue(any("query_probe_not_healthy16" in issue for issue in report["blockers"]))

    def test_coverage_overlap_and_original_result_reuse_are_forbidden(self) -> None:
        fixture = self.fixture()
        first = fixture["replays"][0]
        second = fixture["replays"][1]
        rows = json.loads(second["result"].read_text(encoding="utf-8"))
        rows[0] = json.loads(first["result"].read_text(encoding="utf-8"))[0]
        self.write_json(second["result"], rows)
        report = self.build(fixture)
        self.assertTrue(any("coverage_overlap" in issue for issue in report["blockers"]))

        fixture = self.fixture()
        fixture["replays"][0]["result"] = fixture["original_result"]
        report = self.build(fixture)
        self.assertTrue(any("best_of_merge_or_original_reuse_forbidden" in issue for issue in report["blockers"]))

    def test_result_byte_mutation_after_audits_breaks_sha_binding(self) -> None:
        fixture = self.fixture()
        path = fixture["replays"][0]["result"]
        path.write_bytes(path.read_bytes() + b" \n")
        report = self.build(fixture)
        self.assertTrue(any("publication_result_sha256_mismatch" in issue for issue in report["blockers"]))
        self.assertTrue(any("golden_after_result_sha256_mismatch" in issue for issue in report["blockers"]))


if __name__ == "__main__":
    unittest.main()
