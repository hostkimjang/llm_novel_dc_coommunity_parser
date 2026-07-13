from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import src.llm_batch.paired_measurement_readback as paired_readback_module
from src.llm_batch.decision_call_events import DecisionCallLedgerRegistry
from src.llm_batch.decision_call_readback import read_decision_call_ledger
from src.llm_batch.early_route_measurement import (
    ACCURACY_NOT_ESTIMABLE,
    ARM_AFTER,
    LANE_CHEAP_NIL,
    EarlyRoutePolicyV1,
    EarlyRouteSourceView,
    canonical_hash,
    compare_early_route,
    decide_early_route,
)
from src.llm_batch.selective_compute_shadow import (
    COST_STATUS_PARTIAL_RUNTIME,
    DecisionCostTrace,
)
from src.llm_batch.paired_measurement_readback import (
    REFERENCE_COPY_COST_ONLY,
    RUN_SPEC_SCHEMA_VERSION,
    build_paired_measurement_run_spec,
    build_paired_measurement_readback,
    validate_paired_measurement_run_spec,
    validate_paired_measurement_readback,
    verify_paired_report_sha256,
)
from src.llm_batch.publication_commit import (
    PublicationCommitRegistry,
    build_publication_scope_descriptor,
    commit_publication_result,
    compute_publication_decision_commit,
)
from tests.test_publication_decision_commit import _valid_result
from tools.recover_expert_run_from_checkpoint import (
    publish_paired_recovery_artifacts,
)
from tools.run_paired_measurement_readback import render_korean_report


STARTED = "2026-07-12T10:00:00+09:00"
FINISHED = "2026-07-12T10:00:01+09:00"
PAIR_ID = "paired-readback-test"
PUBLICATION_CONFIG_SHA = "c" * 64
DECISION_ENVIRONMENT_SHA = "d" * 64
SLANG_INPUT_SHA = "e" * 64
RELEASE_FINGERPRINT = "f" * 64


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _self_hash(value: dict, field: str) -> str:
    return _canonical_hash({key: item for key, item in value.items() if key != field})


def _runtime_fields(input_count: int) -> dict:
    return {
        "llm_model": "paired-test-model",
        "llm_endpoint": "http://provider",
        "requested_parallel": 16,
        "effective_parallel": min(input_count, 16),
        "parallel_policy": "effective_parallel=min(requested_parallel,input_post_count)",
        "vlm_enabled": False,
        "ocr_enabled": False,
        "vlm_ocr_semantic_review_ready": True,
        "dashboard_enabled": True,
        "mcp_health_include_search": True,
        "mcp_health_light_mode": False,
        "mcp_health_ok_count": 16,
        "mcp_health_failure_count": 0,
        "mcp_healthy_endpoint_filter_reason": "reuse_shards_only",
        "publication_config_sha256": PUBLICATION_CONFIG_SHA,
        "publication_decision_environment_sha256": DECISION_ENVIRONMENT_SHA,
        "publication_slang_db_input_sha256": SLANG_INPUT_SHA,
        "publication_release_fingerprint": RELEASE_FINGERPRINT,
    }


def _claimed_input_path(manifest_path: Path) -> Path:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    claim_path = Path(manifest["output_attempt_claim"])
    claim = json.loads(claim_path.read_text(encoding="utf-8"))
    return Path(claim["input_file"])


def _shared_measurement_fields() -> dict:
    mutable_binding = {
        "schema_version": "paired_measurement_mutable_context_binding_v1",
        "mutable_context_mode": "FROZEN_OFF",
        "batch_context_enabled": False,
        "slang_access_mode": "OFF",
        "central_slang_db_write_allowed": False,
    }
    return {
        "mode": "REQUIRED",
        "execution_mode": "FRESH_EXECUTION_REQUIRED",
        "binding_status": "BOUND",
        "fresh_execution_required": True,
        "actual_kpi_eligible": True,
        "early_route_mode": "SOURCE_ONLY_V1",
        "mutable_context_mode": "FROZEN_OFF",
        "mutable_context_frozen": True,
        "slang_access_mode": "OFF",
        "central_slang_db_write_allowed": False,
        "mutable_context_binding": mutable_binding,
        "mutable_context_binding_sha256": _canonical_hash(mutable_binding),
    }


def _arm_measurement_fields() -> dict[str, dict]:
    return {
        "BEFORE": {
            "early_route_enabled": False,
            "early_route_enable_status": "DISABLED_CONDITIONS_NOT_MET",
        },
        "AFTER": {
            "early_route_enabled": True,
            "early_route_enable_status": "ENABLED_AFTER_REQUIRED_FRESH_SOURCE_ONLY_V1",
        },
    }


def _execution_receipt(decision) -> dict:
    skipped = decision.selected_lane == LANE_CHEAP_NIL
    payload = {
        "schema_version": "early_route_execution_receipt_v1",
        "mode": "SOURCE_ONLY_V1",
        "route_decision": decision.to_dict(),
        "execution_status": (
            "CHEAP_ZERO_CALL_AUTHORITATIVE_REFERENCE_COPY"
            if skipped
            else "FULL_EXPERT_EXECUTED"
        ),
        "compute_skip_applied": skipped,
        "public_action_applied": False,
        "production_enable_allowed": False,
        "accuracy_status": ACCURACY_NOT_ESTIMABLE,
    }
    return {**payload, "receipt_sha256": _canonical_hash(payload)}


class PairedMeasurementReadbackTests(unittest.TestCase):
    def test_run_spec_freeze_builder_binds_complete_source_and_runtime_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            before, _, _, _ = self._fixture(Path(tmp))
            input_path = _claimed_input_path(before)
            spec = build_paired_measurement_run_spec(
                input_path=input_path,
                source_manifest_path=before,
                pair_id=PAIR_ID,
                slang_access_mode="OFF",
            )
            frozen = Path(tmp) / "frozen_run_spec.json"
            frozen.write_text(
                json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            validated = validate_paired_measurement_run_spec(frozen)
            self.assertEqual(spec, validated)
            self.assertEqual(16, spec["frozen_conditions"]["runtime_manifest_fields"]["requested_parallel"])
            self.assertEqual(
                "reuse_shards_only",
                spec["frozen_conditions"]["runtime_manifest_fields"][
                    "mcp_healthy_endpoint_filter_reason"
                ],
            )

    def test_run_spec_freeze_rejects_light_or_incomplete_source_runtime(self) -> None:
        for field, value in (
            ("mcp_health_light_mode", True),
            ("mcp_health_failure_count", 1),
            ("large_run_complete", False),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                before, _, _, _ = self._fixture(Path(tmp))
                input_path = _claimed_input_path(before)
                manifest = json.loads(before.read_text(encoding="utf-8"))
                manifest[field] = value
                before.write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                with self.assertRaises(ValueError):
                    build_paired_measurement_run_spec(
                        input_path=input_path,
                        source_manifest_path=before,
                        pair_id=PAIR_ID,
                    )

    def _fixture(
        self,
        root: Path,
        *,
        after_zero_indices: set[int] | None = None,
        input_format: str = "jsonl",
        input_post_ids: list[int] | None = None,
        with_execution_envelope: bool = False,
    ) -> tuple[Path, Path, Path, Path]:
        post_ids = [101, 102]
        serialized_post_ids = post_ids if input_post_ids is None else input_post_ids
        input_rows = [
            {"post_id": post_id, "title": f"입력 {post_id}"}
            for post_id in serialized_post_ids
        ]
        if input_format == "jsonl":
            input_bytes = (
                "\n".join(
                    json.dumps(row, ensure_ascii=False, sort_keys=True)
                    for row in input_rows
                )
                + "\n"
            ).encode("utf-8")
            input_suffix = ".jsonl"
        elif input_format == "json":
            input_bytes = (
                json.dumps(input_rows, ensure_ascii=False, indent=2) + "\n"
            ).encode("utf-8")
            input_suffix = ".json"
        else:
            raise AssertionError(f"unsupported fixture input format: {input_format}")
        input_snapshot_sha256 = hashlib.sha256(input_bytes).hexdigest()
        input_paths = {
            arm: root / f"{arm.lower()}_input{input_suffix}"
            for arm in ("BEFORE", "AFTER")
        }
        for input_path in input_paths.values():
            input_path.write_bytes(input_bytes)
        descriptor = build_publication_scope_descriptor(
            input_file_sha256=input_snapshot_sha256,
            post_ids=post_ids,
            config_hash=PUBLICATION_CONFIG_SHA,
            release_fingerprint=RELEASE_FINGERPRINT,
        )
        wal_path = root / "publication_commits.jsonl"
        publication = PublicationCommitRegistry(
            wal_path,
            scope_descriptor=descriptor,
            create_new=True,
        )
        runtime_fields = _runtime_fields(len(post_ids))
        authoritative_results = {
            1: _valid_result(post_id=101, publish=False),
            2: _valid_result(post_id=102, publish=True),
        }
        for result in authoritative_results.values():
            result["run_meta"] = {
                "model": runtime_fields["llm_model"],
                "effective_parallel": runtime_fields["effective_parallel"],
            }
        authoritative_receipts = {}
        for index, post_id in enumerate(post_ids, 1):
            receipt, created = commit_publication_result(
                authoritative_results[index],
                registry=publication,
                attempt_run_id="authoritative-run",
                input_index=index,
                post_id=post_id,
            )
            self.assertTrue(created)
            authoritative_receipts[index] = receipt

        shared_measurement = _shared_measurement_fields()
        if with_execution_envelope:
            shared_measurement["execution_envelope_policy"] = {
                "schema_version": "paired_measurement_execution_envelope_policy_v1",
                "bootstrap_seed": 7,
                "bootstrap_replicates": 100,
                "alpha": 0.05,
                "min_comparable_rows": 2,
            }
        arm_fields = _arm_measurement_fields()
        run_spec = {
            "schema_version": RUN_SPEC_SCHEMA_VERSION,
            "pair_id": PAIR_ID,
            "publication_scope_id": descriptor.publication_scope_id,
            "publication_input_snapshot_sha256": descriptor.input_file_sha256,
            "input_post_count": len(post_ids),
            "ordered_post_ids": post_ids,
            "frozen_conditions": {
                "runtime_manifest_fields": runtime_fields,
                "shared_measurement_fields": shared_measurement,
                "arm_measurement_fields": arm_fields,
            },
            "recovery_policy": "ALLOW_RECOVERED_ARMS_EXACT_BOUND_WITNESS_ONLY",
            "approval_boundary": {
                "semantic_quality": "REVIEW-LOCKED",
                "production_enable_allowed": False,
                "full_scan_approval": False,
            },
        }
        run_spec["run_spec_sha256"] = _canonical_hash(run_spec)
        run_spec_path = root / "paired_run_spec.json"
        run_spec_path.write_text(
            json.dumps(run_spec, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        after_zero_indices = {1} if after_zero_indices is None else after_zero_indices
        cheap_route_indices = {1} if 1 in after_zero_indices else set()
        manifest_paths: dict[str, Path] = {}
        for arm in ("BEFORE", "AFTER"):
            run_id = f"run-{arm.lower()}"
            measurement = {
                **deepcopy(shared_measurement),
                **arm_fields[arm],
                "run_spec_sha256": run_spec["run_spec_sha256"],
                "pair_id": PAIR_ID,
                "arm": arm,
            }
            ledger_path = root / f"{arm.lower()}_ledger"
            registry = DecisionCallLedgerRegistry(
                ledger_path,
                scope_descriptor=descriptor,
                create_new=True,
                enabled=True,
                run_spec_sha256=run_spec["run_spec_sha256"],
                pair_id=PAIR_ID,
                arm=arm,
                fresh_execution_mode=True,
            )
            for index, post_id in enumerate(post_ids, 1):
                row = registry.row_attempt(
                    attempt_run_id=run_id,
                    row_attempt_id=f"{run_id}-row-{index}",
                    input_index=index,
                    post_id=post_id,
                )
                should_call = arm == "BEFORE" or index not in after_zero_indices
                if should_call:
                    call_id = f"{run_id}-call-{index}"
                    registry.record_dispatch_intent(
                        row,
                        logical_call_id=f"logical-{index}",
                        call_id=call_id,
                        retry_ordinal=0,
                        retry_of_call_id=None,
                        stage="GATEKEEPER",
                        modality="TEXT",
                        requested_model=runtime_fields["llm_model"],
                        resolved_model=None,
                        endpoint=runtime_fields["llm_endpoint"],
                        backend="http",
                        started_at=STARTED,
                        monotonic_started_ns=1_000_000_000,
                        request_sha256="1" * 64,
                    )
                    registry.record_terminal(
                        row,
                        call_id=call_id,
                        terminal_status="SUCCEEDED",
                        resolved_model=runtime_fields["llm_model"],
                        response_sha256="2" * 64,
                        usage_provenance="PROVIDER_REPORTED",
                        prompt_tokens=10,
                        completion_tokens=2,
                        total_tokens=12,
                        finished_at=FINISHED,
                        monotonic_finished_ns=1_100_000_000,
                    )
                registry.seal_row(
                    row,
                    sealed_at=FINISHED,
                    monotonic_finished_ns=1_200_000_000,
                )
                registry.link_publication(
                    row,
                    publication_decision_id=authoritative_receipts[index].decision_id,
                    linked_at=FINISHED,
                )

            output_rows = []
            for index, post_id in enumerate(post_ids, 1):
                output_row = deepcopy(authoritative_results[index])
                run_meta = {
                    "run_id": run_id,
                    "model": runtime_fields["llm_model"],
                    "effective_parallel": runtime_fields["effective_parallel"],
                    "decision_call_measurement": deepcopy(measurement),
                    "measurement_execution_source": "FRESH_EXECUTION_NO_PUBLIC_WRITE",
                }
                if with_execution_envelope:
                    before_wall = 100 * index
                    wall_ms = before_wall if arm == "BEFORE" else 80 * index
                    run_meta["decision_cost_trace"] = DecisionCostTrace.create(
                        publication_scope_id=descriptor.publication_scope_id,
                        run_id=run_id,
                        input_index=index,
                        post_id=post_id,
                        model_tier=runtime_fields["llm_model"],
                        processing_started_at=STARTED,
                        processing_finished_at=FINISHED,
                        wall_ms=wall_ms,
                        prompt_tokens=None,
                        completion_tokens=None,
                        total_tokens=None,
                        expert_calls=None,
                        search_calls=None,
                        retry_count=None,
                        vlm_chunks=None,
                        measurement_status=COST_STATUS_PARTIAL_RUNTIME,
                    ).to_dict()
                output_row["run_meta"] = run_meta
                if arm == "AFTER":
                    title = (
                        "ㅋㅋㅋ!!!"
                        if index in cheap_route_indices
                        else "작품 제목"
                    )
                    source = EarlyRouteSourceView.create(
                        publication_scope_id=descriptor.publication_scope_id,
                        pair_id=PAIR_ID,
                        arm=ARM_AFTER,
                        input_index=index,
                        post_id=post_id,
                        source_input_sha256=canonical_hash(
                            {"input_index": index, "post_id": post_id, "title": title}
                        ),
                        title=title,
                    )
                    decision = decide_early_route(source, EarlyRoutePolicyV1.create())
                    execution = _execution_receipt(decision)
                    run_meta["early_route_measurement"] = {
                        "execution_receipt": execution,
                        "comparison_receipt": None,
                    }
                    current_receipt = compute_publication_decision_commit(
                        output_row,
                        publication_scope_id=descriptor.publication_scope_id,
                        attempt_run_id=run_id,
                        input_index=index,
                        post_id=post_id,
                    )
                    authoritative = authoritative_receipts[index]
                    promotion = authoritative_results[index]["analysis_result"]["identity"][
                        "promotion_decision"
                    ]
                    comparison = compare_early_route(
                        decision,
                        authoritative_wal_receipt_sha256=authoritative.commit_sha256,
                        authoritative_wal_outcome=authoritative.outcome,
                        authoritative_publish_allowed=authoritative.publish_allowed,
                        authoritative_title=(
                            promotion.get("official_title")
                            if authoritative.publish_allowed
                            else None
                        ),
                        authoritative_url=(
                            promotion.get("official_url")
                            if authoritative.publish_allowed
                            else None
                        ),
                        public_projection_before_sha256=(
                            authoritative.public_projection_sha256
                        ),
                        public_projection_after_sha256=(
                            current_receipt.public_projection_sha256
                        ),
                    )
                    run_meta["early_route_measurement"][
                        "comparison_receipt"
                    ] = comparison.to_dict()
                output_rows.append(output_row)

            output_path = root / f"{arm.lower()}_result.json"
            output_path.write_text(
                json.dumps(output_rows, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            claim_path = root / f"{arm.lower()}_result_attempt_claim.json"
            claim = {
                "schema_version": "expert_output_attempt_claim_v1",
                "run_id": run_id,
                "pid": 1234,
                "output_file": str(output_path.resolve()),
                "input_file": str(input_paths[arm].resolve()),
                "decision_call_ledger_mode": "REQUIRED",
                "decision_call_ledger_path": str(ledger_path.resolve()),
                "decision_call_measurement": measurement,
            }
            claim_bytes = (
                json.dumps(
                    claim,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
            claim_path.write_bytes(claim_bytes)
            ledger_scope = json.loads(
                (ledger_path / "scope.json").read_text(encoding="utf-8")
            )
            cheap_count = len(cheap_route_indices) if arm == "AFTER" else 0
            manifest = {
                "run_id": run_id,
                "output_file": str(output_path),
                "input_post_count": len(post_ids),
                "completed_count": len(post_ids),
                "flushed_count": len(post_ids),
                "pending_count": 0,
                "failed_count": 0,
                "publication_commit_count": len(post_ids),
                "large_run_complete": True,
                "terminal_artifacts_finalized": True,
                "publication_scope_id": descriptor.publication_scope_id,
                "publication_input_snapshot_sha256": descriptor.input_file_sha256,
                "publication_commit_journal": str(wal_path),
                "publication_execution_mode": "FRESH_EXECUTION_NO_PUBLIC_WRITE",
                "decision_call_measurement": measurement,
                "decision_call_ledger_path": str(ledger_path),
                "decision_call_ledger_scope_sha256": ledger_scope["scope_sha256"],
                "runtime_completion_gate": {"status": "GO"},
                "measurement_gate": {"status": "GO"},
                "early_route_execution_gate": {
                    "schema_version": "early_route_execution_gate_v1",
                    "required": arm == "AFTER",
                    "status": "GO" if arm == "AFTER" else "NOT_REQUIRED",
                    "expected_input_count": len(post_ids),
                    "observed_route_count": len(post_ids) if arm == "AFTER" else 0,
                    "observed_comparison_count": (
                        len(post_ids) if arm == "AFTER" else 0
                    ),
                    "cheap_count": cheap_count,
                    "cheap_zero_call_writer_verified_count": cheap_count,
                    "reason_codes": [],
                },
                "output_attempt_claim": str(claim_path),
                "output_attempt_claim_sha256": hashlib.sha256(claim_bytes).hexdigest(),
                **runtime_fields,
            }
            manifest_path = root / f"{arm.lower()}_manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            manifest_paths[arm] = manifest_path
        return (
            manifest_paths["BEFORE"],
            manifest_paths["AFTER"],
            wal_path,
            run_spec_path,
        )

    def test_execution_envelope_binds_full_expert_e2e_percentiles_and_paired_ci(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            before, after, _, run_spec = self._fixture(
                Path(tmp),
                after_zero_indices=set(),
                with_execution_envelope=True,
            )
            report = self._build(before, after, run_spec)
            latency = report["non_cost_metrics"]["end_to_end_latency"]
            self.assertEqual("EXACT_PRODUCTION_INFERENCE_COMPARABLE_ROWS_ONLY", latency["status"])
            envelope = latency["execution_envelope"]
            self.assertEqual(2, envelope["comparable_row_count"])
            self.assertEqual(150.0, envelope["p50"]["before"])
            self.assertEqual(120.0, envelope["p50"]["after"])
            self.assertLess(envelope["p50"]["paired_ci_upper"], 0.0)
            self.assertIsNotNone(report["sources"]["before_execution_envelope"])

    def test_execution_envelope_policy_fails_closed_when_a_trace_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            before, after, _, run_spec = self._fixture(
                Path(tmp),
                after_zero_indices=set(),
                with_execution_envelope=True,
            )
            rows = json.loads(after.with_name("after_result.json").read_text(encoding="utf-8"))
            rows[0]["run_meta"].pop("decision_cost_trace")
            after.with_name("after_result.json").write_text(
                json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "decision cost trace"):
                self._build(before, after, run_spec)

    def _publish_recovered_arm(
        self,
        *,
        source_manifest_path: Path,
        run_spec_path: Path,
        root: Path,
    ) -> dict[str, Path]:
        source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
        arm = source_manifest["decision_call_measurement"]["arm"]
        source_result_path = Path(source_manifest["output_file"])
        output_rows = json.loads(source_result_path.read_text(encoding="utf-8"))
        checkpoint_path = root / f"{arm.lower()}_recovery_checkpoint.jsonl"
        checkpoint_rows = []
        for index, result in enumerate(output_rows, 1):
            post_id = result["post_id"]
            checkpoint_rows.append(
                {
                    "global_idx": index,
                    "post_id": post_id,
                    "status": "completed",
                    "result": result,
                    "publication_commit": compute_publication_decision_commit(
                        result,
                        publication_scope_id=source_manifest["publication_scope_id"],
                        attempt_run_id=source_manifest["run_id"],
                        input_index=index,
                        post_id=post_id,
                    ).to_dict(),
                }
            )
        checkpoint_path.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in checkpoint_rows)
            + "\n",
            encoding="utf-8",
        )
        pending_path = root / f"{arm.lower()}_recovery_pending.json"
        pending_path.write_text("[]\n", encoding="utf-8")
        source_manifest["checkpoint_jsonl"] = str(checkpoint_path)
        source_manifest["pending_snapshot"] = str(pending_path)
        source_manifest_path.write_text(
            json.dumps(source_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        recovered_output_path = root / f"{arm.lower()}_recovered_result.json"
        recovered_output_path.write_text(
            json.dumps(output_rows, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        ledger_report = read_decision_call_ledger(
            Path(source_manifest["decision_call_ledger_path"])
        )
        wal_path = Path(source_manifest["publication_commit_journal"])
        wal_raw = wal_path.read_bytes()
        wal_count = len([line for line in wal_raw.splitlines() if line.strip()])
        fresh_gate = {
            "status": "GO",
            "measurement_eligible": True,
            "actual_kpi_status": "INDEPENDENTLY_VERIFIED_EXACT",
            "recovery_action": "NONE",
            "reason_codes": [],
            "ledger_path": str(Path(source_manifest["decision_call_ledger_path"])),
            "independent_readback": {
                "gate_status": "GO",
                "report_sha256": ledger_report["report_sha256"],
                "reason_codes": [],
            },
            "publication_wal_sha256_before": hashlib.sha256(wal_raw).hexdigest(),
            "publication_wal_sha256_after": hashlib.sha256(wal_raw).hexdigest(),
            "publication_wal_event_count_before": wal_count,
            "publication_wal_event_count_after": wal_count,
            "publication_wal_unchanged": True,
        }
        summary_path = root / f"{arm.lower()}_recovery_summary.json"
        summary = {
            "run_id": source_manifest["run_id"],
            "source_result_path": str(source_result_path),
            "source_checkpoint_path": str(checkpoint_path),
            "source_pending_snapshot_path": str(pending_path),
            "recovered_output_path": str(recovered_output_path),
            "recovery_source": "publication_commit_wal_current",
            "fresh_measurement_recovery": fresh_gate,
            "checkpoint_rows": len(checkpoint_rows),
            "checkpoint_completed_rows": len(checkpoint_rows),
            "checkpoint_failed_rows": 0,
            "pending_snapshot_rows": 0,
            "recovered_rows": len(output_rows),
            "recovery_safe_to_use_as_completed_subset": True,
            "large_run_complete": True,
            "semantic_quality": "REVIEW-LOCKED",
            "full_scan_approval": False,
        }
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        witness_path = root / f"{arm.lower()}_recovery_witness.json"
        recovered_manifest_path = root / f"{arm.lower()}_recovered_manifest.json"
        publish_paired_recovery_artifacts(
            paired_run_spec_path=run_spec_path,
            source_manifest_path=source_manifest_path,
            source_checkpoint_path=checkpoint_path,
            source_pending_snapshot_path=pending_path,
            recovery_summary_path=summary_path,
            recovered_output_path=recovered_output_path,
            recovery_witness_output_path=witness_path,
            recovered_manifest_output_path=recovered_manifest_path,
        )
        return {
            "source_manifest": source_manifest_path,
            "source_result": source_result_path,
            "checkpoint": checkpoint_path,
            "pending": pending_path,
            "summary": summary_path,
            "recovered_output": recovered_output_path,
            "witness": witness_path,
            "recovered_manifest": recovered_manifest_path,
            "wal": wal_path,
            "claim": Path(source_manifest["output_attempt_claim"]),
        }

    def _build(self, before: Path, after: Path, run_spec: Path) -> dict:
        return build_paired_measurement_readback(
            run_spec_path=run_spec,
            before_manifest_path=before,
            after_manifest_path=after,
        )

    def test_reference_copy_is_separate_from_production_savings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            before, after, _, run_spec = self._fixture(Path(tmp))
            report = self._build(before, after, run_spec)
            self.assertEqual(
                "GO_COST_READBACK_ONLY_ACCURACY_NOT_ESTIMABLE",
                report["status"],
            )
            calls = report["actual_cost_metrics"]["expert_calls"]
            self.assertEqual(
                (1, 1, 0.0),
                (calls["before"], calls["after"], calls["reduction_percent"]),
            )
            self.assertEqual(
                "EXACT_PRODUCTION_INFERENCE_COMPARABLE_ROWS_ONLY",
                calls["status"],
            )
            counterfactual = report["counterfactual_reference_copy_cost"]
            self.assertEqual(REFERENCE_COPY_COST_ONLY, counterfactual["classification"])
            self.assertFalse(counterfactual["production_savings_kpi_eligible"])
            reference_calls = counterfactual["cost_metrics"]["expert_calls"]
            self.assertEqual(
                (1, 0, 100.0, REFERENCE_COPY_COST_ONLY),
                (
                    reference_calls["before"],
                    reference_calls["after"],
                    reference_calls["reduction_percent"],
                    reference_calls["status"],
                ),
            )
            tokens = report["actual_cost_metrics"]["total_tokens"]
            self.assertEqual((12, 12, 0.0), (tokens["before"], tokens["after"], tokens["reduction_percent"]))
            wall = report["actual_cost_metrics"]["physical_call_wall_ms_sum"]
            self.assertEqual((100, 100, 0.0), (wall["before"], wall["after"], wall["reduction_percent"]))
            zero = report["zero_physical_call_coverage"]
            self.assertEqual(1, zero["authorized_reference_copy_zero_call_count"])
            self.assertEqual(0, zero["unexplained_zero_call_count"])
            self.assertFalse(zero["production_savings_kpi_eligible"])
            self.assertEqual(
                "NOT_ESTIMABLE_NOT_BOUND_IN_THIS_REPORT",
                report["gates"]["frozen_actual_accuracy"],
            )
            self.assertTrue(
                all(
                    item["value"] is None
                    for item in report["non_cost_metrics"].values()
                )
            )
            self.assertEqual("REVIEW-LOCKED", report["gates"]["semantic_quality"])
            self.assertFalse(report["gates"]["production_enable_allowed"])
            self.assertFalse(report["gates"]["full_scan_approval"])
            self.assertTrue(verify_paired_report_sha256(report))
            rendered = render_korean_report(report)
            self.assertIn("REFERENCE_COPY_COST_ONLY", rendered)
            self.assertIn("production 절감 KPI", rendered)
            self.assertIn("정확도 정답이나 운영 승인을 대신하지 않는다", rendered)
            validate_paired_measurement_readback(
                report,
                run_spec_path=run_spec,
                before_manifest_path=before,
                after_manifest_path=after,
            )

    def test_exact_source_replayed_witness_accepts_recovered_before_and_after(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before, after, _, run_spec = self._fixture(root)
            before_recovery = self._publish_recovered_arm(
                source_manifest_path=before,
                run_spec_path=run_spec,
                root=root,
            )
            after_recovery = self._publish_recovered_arm(
                source_manifest_path=after,
                run_spec_path=run_spec,
                root=root,
            )
            report = self._build(
                before_recovery["recovered_manifest"],
                after_recovery["recovered_manifest"],
                run_spec,
            )
            self.assertEqual(
                "GO_EXACT_BOUND_WITNESS_REPLAY",
                report["gates"]["recovery_measurement_support"],
            )
            self.assertIsNotNone(report["sources"]["before_recovery_witness"])
            self.assertIsNotNone(report["sources"]["after_recovery_witness"])
            self.assertGreaterEqual(
                len(report["sources"]["before_recovery_sources"]), 9
            )
            validate_paired_measurement_readback(
                report,
                run_spec_path=run_spec,
                before_manifest_path=before_recovery["recovered_manifest"],
                after_manifest_path=after_recovery["recovered_manifest"],
            )

    def test_recovery_witness_self_rehash_cannot_launder_partial_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before, after, _, run_spec = self._fixture(root)
            recovery = self._publish_recovered_arm(
                source_manifest_path=before,
                run_spec_path=run_spec,
                root=root,
            )
            rows = [
                json.loads(line)
                for line in recovery["checkpoint"].read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            rows[0]["status"] = "failed"
            recovery["checkpoint"].write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
                encoding="utf-8",
            )
            witness = json.loads(recovery["witness"].read_text(encoding="utf-8"))
            raw = recovery["checkpoint"].read_bytes()
            witness["source_checkpoint"] = {
                "path": str(recovery["checkpoint"].resolve()),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
            witness["witness_sha256"] = _self_hash(witness, "witness_sha256")
            recovery["witness"].write_text(
                json.dumps(witness, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError, "source counts mismatch|non-completed"
            ):
                self._build(recovery["recovered_manifest"], after, run_spec)

    def test_recovery_witness_rejects_wal_and_bound_source_changes(self) -> None:
        for source_name in (
            "wal",
            "source_manifest",
            "source_result",
            "pending",
            "summary",
            "recovered_output",
            "claim",
        ):
            with self.subTest(source_name=source_name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                before, after, _, run_spec = self._fixture(root)
                recovery = self._publish_recovered_arm(
                    source_manifest_path=before,
                    run_spec_path=run_spec,
                    root=root,
                )
                target = recovery[source_name]
                target.write_bytes(target.read_bytes() + b" \n")
                with self.assertRaises(ValueError):
                    self._build(recovery["recovered_manifest"], after, run_spec)

    def test_recovery_witness_rejects_multi_attempt_ledger_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before, after, _, run_spec = self._fixture(root)
            recovery = self._publish_recovered_arm(
                source_manifest_path=before,
                run_spec_path=run_spec,
                root=root,
            )
            original = paired_readback_module.read_decision_call_ledger

            def multi_attempt(path):
                report = original(path)
                if Path(path).resolve() == Path(
                    json.loads(before.read_text(encoding="utf-8"))[
                        "decision_call_ledger_path"
                    ]
                ).resolve():
                    report = deepcopy(report)
                    report["coverage"]["attempt_run_ids"] = ["run-before", "retry-run"]
                    report["coverage"]["attempt_run_count"] = 2
                    report["report_sha256"] = _self_hash(report, "report_sha256")
                return report

            with patch.object(
                paired_readback_module,
                "read_decision_call_ledger",
                side_effect=multi_attempt,
            ), self.assertRaises(ValueError):
                self._build(recovery["recovered_manifest"], after, run_spec)

    def test_no_go_republication_removes_stale_witness_and_manifest_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before, _, _, run_spec = self._fixture(root)
            recovery = self._publish_recovered_arm(
                source_manifest_path=before,
                run_spec_path=run_spec,
                root=root,
            )
            summary = json.loads(recovery["summary"].read_text(encoding="utf-8"))
            summary["fresh_measurement_recovery"]["status"] = "NO-GO"
            summary["fresh_measurement_recovery"]["measurement_eligible"] = False
            recovery["summary"].write_text(
                json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "not exact GO"):
                publish_paired_recovery_artifacts(
                    paired_run_spec_path=run_spec,
                    source_manifest_path=recovery["source_manifest"],
                    source_checkpoint_path=recovery["checkpoint"],
                    source_pending_snapshot_path=recovery["pending"],
                    recovery_summary_path=recovery["summary"],
                    recovered_output_path=recovery["recovered_output"],
                    recovery_witness_output_path=recovery["witness"],
                    recovered_manifest_output_path=recovery["recovered_manifest"],
                )
            self.assertFalse(recovery["witness"].exists())
            self.assertFalse(recovery["recovered_manifest"].exists())

    def test_self_rehashed_report_forgery_is_rejected_by_source_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            before, after, _, run_spec = self._fixture(Path(tmp))
            report = self._build(before, after, run_spec)
            report["actual_cost_metrics"]["expert_calls"]["after"] = 0
            report["report_sha256"] = _self_hash(report, "report_sha256")
            self.assertTrue(verify_paired_report_sha256(report))
            with self.assertRaisesRegex(ValueError, "source replay"):
                validate_paired_measurement_readback(
                    report,
                    run_spec_path=run_spec,
                    before_manifest_path=before,
                    after_manifest_path=after,
                )

    def test_self_rehashed_output_receipt_tamper_fails_source_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            before, after, _, run_spec = self._fixture(Path(tmp))
            report = self._build(before, after, run_spec)
            rows = json.loads(after.with_name("after_result.json").read_text(encoding="utf-8"))
            execution = rows[0]["run_meta"]["early_route_measurement"]["execution_receipt"]
            execution["execution_status"] = "FULL_EXPERT_EXECUTED"
            execution["receipt_sha256"] = _self_hash(execution, "receipt_sha256")
            after.with_name("after_result.json").write_text(
                json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "source replay"):
                validate_paired_measurement_readback(
                    report,
                    run_spec_path=run_spec,
                    before_manifest_path=before,
                    after_manifest_path=after,
                )

    def test_output_empty_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            before, after, _, run_spec = self._fixture(Path(tmp))
            after.with_name("after_result.json").write_text("[]\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "output row coverage"):
                self._build(before, after, run_spec)

    def test_json_array_input_bytes_and_order_are_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            before, after, _, run_spec = self._fixture(
                Path(tmp), input_format="json"
            )
            report = self._build(before, after, run_spec)
            self.assertEqual("JSON_ARRAY", report["sources"]["before_input"]["format"])
            self.assertEqual("JSON_ARRAY", report["sources"]["after_input"]["format"])
            self.assertEqual(
                report["run_spec_sha256"],
                report["sources"]["run_spec"]["self_hash"],
            )
            self.assertEqual("GO", report["gates"]["input_bytes_and_order_bound"])

    def test_missing_claimed_input_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            before, after, _, run_spec = self._fixture(Path(tmp))
            after.with_name("after_input.jsonl").unlink()
            with self.assertRaisesRegex(ValueError, "artifact missing.*after_input"):
                self._build(before, after, run_spec)

    def test_tampered_input_bytes_fail_stored_report_source_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            before, after, _, run_spec = self._fixture(Path(tmp))
            report = self._build(before, after, run_spec)
            input_path = after.with_name("after_input.jsonl")
            rows = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines()]
            rows[0]["title"] = "바이트 위조"
            input_path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "source replay.*input bytes SHA"):
                validate_paired_measurement_readback(
                    report,
                    run_spec_path=run_spec,
                    before_manifest_path=before,
                    after_manifest_path=after,
                )

    def test_reordered_input_post_ids_are_rejected_even_when_bytes_are_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            before, after, _, run_spec = self._fixture(
                Path(tmp), input_post_ids=[102, 101]
            )
            with self.assertRaisesRegex(ValueError, "input ordered post_id coverage differs"):
                self._build(before, after, run_spec)

    def test_runtime_llm_model_and_effective_parallel_tamper_are_rejected(self) -> None:
        for field, value in (("llm_model", "tampered-model"), ("effective_parallel", 1)):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                before, after, _, run_spec = self._fixture(Path(tmp))
                manifest = json.loads(after.read_text(encoding="utf-8"))
                manifest[field] = value
                after.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, f"runtime field {field} differs from RunSpec"):
                    self._build(before, after, run_spec)

    def test_run_spec_plain_and_self_rehashed_tamper_are_rejected(self) -> None:
        for self_rehash in (False, True):
            with self.subTest(self_rehash=self_rehash), tempfile.TemporaryDirectory() as tmp:
                before, after, _, run_spec = self._fixture(Path(tmp))
                spec = json.loads(run_spec.read_text(encoding="utf-8"))
                spec["frozen_conditions"]["runtime_manifest_fields"]["llm_model"] = (
                    "tampered-model"
                )
                if self_rehash:
                    spec["run_spec_sha256"] = _self_hash(spec, "run_spec_sha256")
                run_spec.write_text(json.dumps(spec), encoding="utf-8")
                expected = "differs from RunSpec" if self_rehash else "RunSpec self hash mismatch"
                with self.assertRaisesRegex(ValueError, expected):
                    self._build(before, after, run_spec)

    def test_self_rehashed_run_spec_tamper_fails_stored_report_source_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            before, after, _, run_spec = self._fixture(Path(tmp))
            report = self._build(before, after, run_spec)
            spec = json.loads(run_spec.read_text(encoding="utf-8"))
            spec["frozen_conditions"]["runtime_manifest_fields"]["llm_model"] = "tampered-model"
            spec["run_spec_sha256"] = _self_hash(spec, "run_spec_sha256")
            run_spec.write_text(json.dumps(spec), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source replay"):
                validate_paired_measurement_readback(
                    report,
                    run_spec_path=run_spec,
                    before_manifest_path=before,
                    after_manifest_path=after,
                )

    def test_unexplained_zero_call_full_lane_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            before, after, _, run_spec = self._fixture(
                Path(tmp), after_zero_indices={1, 2}
            )
            with self.assertRaisesRegex(ValueError, "unexplained zero physical calls"):
                self._build(before, after, run_spec)

    def test_manifest_measurement_binding_tamper_fails(self) -> None:
        for field, value in (
            ("run_spec_sha256", "0" * 64),
            ("pair_id", "different-pair"),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                before, after, _, run_spec = self._fixture(Path(tmp))
                manifest = json.loads(after.read_text(encoding="utf-8"))
                manifest["decision_call_measurement"][field] = value
                after.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, f"measurement {field} differs from RunSpec"):
                    self._build(before, after, run_spec)

    def test_authoritative_wal_tamper_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            before, after, wal, run_spec = self._fixture(Path(tmp))
            wal.write_bytes(wal.read_bytes() + b"{}\n")
            with self.assertRaises(ValueError):
                self._build(before, after, run_spec)

    def test_incomplete_terminal_manifest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            before, after, _, run_spec = self._fixture(Path(tmp))
            manifest = json.loads(after.read_text(encoding="utf-8"))
            manifest["large_run_complete"] = False
            after.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "large_run_complete"):
                self._build(before, after, run_spec)

    def test_recovered_arm_is_explicitly_rejected_without_witness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            before, after, _, run_spec = self._fixture(Path(tmp))
            manifest = json.loads(after.read_text(encoding="utf-8"))
            manifest["fresh_measurement_recovery"] = {"status": "GO"}
            after.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(
                ValueError,
                "recovered arm rejected: no independently bound recovery witness",
            ):
                self._build(before, after, run_spec)

    def test_final_ledger_replay_rejects_changed_frame_or_report_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            before, after, _, run_spec = self._fixture(Path(tmp))
            original = paired_readback_module.read_decision_call_ledger
            call_count = 0

            def replay_with_final_mutation(path):
                nonlocal call_count
                call_count += 1
                report = original(path)
                if call_count == 3:
                    report = deepcopy(report)
                    report["frame_set_sha256"] = "0" * 64
                return report

            with patch.object(
                paired_readback_module,
                "read_decision_call_ledger",
                side_effect=replay_with_final_mutation,
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "decision-call ledger changed before final replay",
                ):
                    self._build(before, after, run_spec)


if __name__ == "__main__":
    unittest.main()
