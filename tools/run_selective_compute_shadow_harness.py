from __future__ import annotations

"""P4 selective-compute 비용 라우팅 shadow-only 하네스.

저장된 Golden18과 worker 로그는 현재 기준선의 준비도만 확인한다. 실제
비용 절감률은 구조화된 call-event receipt와 after runtime이 없으므로
계산하지 않는다. 별도의 합성 fixture는 라우팅/산술/공격 방어 계약만
검증하며 실제 성능 주장으로 승격되지 않는다.
"""

import argparse
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable, Mapping, Optional, Sequence
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm_batch.selective_compute_shadow import (  # noqa: E402
    ACTION_ASSERT_NIL,
    ACTION_NONE,
    ACTION_RESOLVE,
    COST_STATUS_PARTIAL_LOG,
    COST_STATUS_SYNTHETIC,
    EVIDENCE_SCOPE_SAVED,
    EVIDENCE_SCOPE_SYNTHETIC,
    HARD_RISK_CODES,
    LANE_CHEAP_RULE,
    LANE_FULL_EXPERT,
    NIL_LABEL,
    REQUIRED_BINDING_NAMES,
    ROUTING_EVALUATION_SCHEMA,
    SelectiveComputeObservation,
    SelectiveComputePolicy,
    build_selective_compute_routing,
    canonical_hash,
    evaluate_selective_compute_receipts,
    selective_compute_observation_from_dict,
    selective_compute_routing_receipt_from_dict,
)


RUN_SPEC_SCHEMA = "selective-compute-shadow-runspec-v1"
REPORT_SCHEMA = "selective-compute-shadow-comparison-v1"
MODE = "SAVED_GOLDEN_PARTIAL_COST_BASELINE_AND_SYNTHETIC_ROUTER_CONTRACT_NO_RUNTIME"
OUTPUT_ROOT = ROOT / "out" / "selective_compute_shadow_harness_20260712"
DEFAULT_OUTPUT_DIR = OUTPUT_ROOT / "v19"

DEFAULT_P1_RUN_SPEC = ROOT / "out/candidate_set_nil_shadow_harness_20260711/v8/run_spec.json"
DEFAULT_P1_COMPARISON = ROOT / "out/candidate_set_nil_shadow_harness_20260711/v8/comparison.json"
DEFAULT_P2_RUN_SPEC = ROOT / "out/publication_exact_once_harness_20260711/v8/run_spec.json"
DEFAULT_P2_COMPARISON = ROOT / "out/publication_exact_once_harness_20260711/v8/comparison.json"
DEFAULT_P3_RUN_SPEC = ROOT / "out/candidate_set_calibration_shadow_harness_20260711/v18/run_spec.json"
DEFAULT_P3_COMPARISON = ROOT / "out/candidate_set_calibration_shadow_harness_20260711/v18/comparison.json"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else ROOT / path).resolve()


def _stored_path(value: str | Path) -> str:
    path = _resolve_path(value)
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _read_json(value: str | Path) -> Any:
    return json.loads(_resolve_path(value).read_text(encoding="utf-8-sig"))


def _read_json_snapshot(value: str | Path) -> tuple[Any, str]:
    path = _resolve_path(value)
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    return json.loads(payload.decode("utf-8-sig")), digest


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_ref(value: str | Path) -> dict[str, Any]:
    path = _resolve_path(value)
    if not path.is_file():
        raise ValueError(f"artifact missing: {path}")
    return {
        "path": _stored_path(path),
        "sha256": _sha256_file(path),
        "bytes": path.stat().st_size,
    }


def _validate_artifact_ref(value: Any, label: str) -> Path:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} artifact reference missing")
    path = _resolve_path(str(value.get("path") or ""))
    if _artifact_ref(path) != dict(value):
        raise ValueError(f"{label} artifact reference mismatch")
    return path


def _run_spec_self_hash(spec: Mapping[str, Any]) -> str:
    return canonical_hash(
        {
            key: value
            for key, value in spec.items()
            if key not in {"generated_at", "run_spec_sha256"}
        }
    )


def _validate_p3_parent_chain(
    *,
    p1_spec: Mapping[str, Any],
    p2_spec: Mapping[str, Any],
    p3_spec: Mapping[str, Any],
    p1_run_spec_path: str | Path,
    p1_comparison_path: str | Path,
    p2_run_spec_path: str | Path,
    p2_comparison_path: str | Path,
) -> dict[str, Any]:
    """Require P3 to be built from the exact P1/P2 chain consumed by P4."""

    p1_artifacts = p1_spec.get("artifacts")
    p3_artifacts = p3_spec.get("artifacts")
    p3_parent = p3_spec.get("parent_contract")
    if not isinstance(p1_artifacts, Mapping):
        raise ValueError("P1 artifact map missing for P4 lineage")
    if not isinstance(p3_artifacts, Mapping) or not isinstance(p3_parent, Mapping):
        raise ValueError("P3 parent chain missing for P4 lineage")
    if (
        p3_parent.get("p1_run_spec_self_hash") != p1_spec.get("run_spec_sha256")
        or p3_parent.get("p2_run_spec_self_hash") != p2_spec.get("run_spec_sha256")
    ):
        raise ValueError("P3 parent chain self-hash mismatch")
    expected_refs = {
        "parent_p1_run_spec": _artifact_ref(p1_run_spec_path),
        "parent_p1_comparison": _artifact_ref(p1_comparison_path),
        "parent_p2_run_spec": _artifact_ref(p2_run_spec_path),
        "parent_p2_comparison": _artifact_ref(p2_comparison_path),
    }
    for name, expected in expected_refs.items():
        value = p3_artifacts.get(name)
        if not isinstance(value, Mapping) or dict(value) != expected:
            raise ValueError(f"P3 parent chain artifact mismatch: {name}")
    p1_label_ref = p1_artifacts.get("label_ledger")
    p3_label_ref = p3_artifacts.get("label_ledger")
    _validate_artifact_ref(p1_label_ref, "P1 label ledger")
    _validate_artifact_ref(p3_label_ref, "P3 label ledger")
    if dict(p1_label_ref) != dict(p3_label_ref):
        raise ValueError("P1/P3 label ledger lineage mismatch")
    return dict(p3_label_ref)


def _percentile(values: Sequence[int], probability: float) -> Optional[int]:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(probability * len(ordered)) - 1))
    return ordered[index]


_ORCHESTRATOR_START_RE = re.compile(r"Orchestrator 시작: post_id=(\d+)")
_LLM_CONTEXT_RE = re.compile(r"\[llm-context\]\s+([^\s]+)\s+프롬프트:")
_POST_COMPLETE_RE = re.compile(r"✅ Post (\d+) 완료 \(([0-9.]+)s")
_VLM_REQUEST_RE = re.compile(r"VLM(?: OCR retry)? chunk request: post_id=(\d+)")
_TOKEN_BLOCK_RE = re.compile(
    r"Post (\d+) token usage\s*\r?\n"
    r"\s*prompt_tokens:\s*([\d,]+)\s*\r?\n"
    r"\s*completion_tokens:\s*([\d,]+)\s*\r?\n"
    r"\s*total_tokens:\s*([\d,]+)",
    re.MULTILINE,
)


def parse_sidecar_cost_logs(paths: Sequence[str | Path]) -> dict[str, dict[str, Any]]:
    """Reconstruct diagnostics only; this is not a canonical cost receipt."""
    rows: dict[str, dict[str, Any]] = {}

    def touch(post_id: str, path: Path, line_number: Optional[int], event: str) -> dict[str, Any]:
        row = rows.setdefault(post_id, {})
        source = _stored_path(path)
        source_logs = list(row.get("source_logs") or [])
        if source not in source_logs:
            source_logs.append(source)
        row["source_logs"] = sorted(source_logs)
        event_lines = dict(row.get("event_lines") or {})
        if line_number is not None:
            values = list(event_lines.get(event) or [])
            values.append({"source": source, "line": line_number})
            event_lines[event] = values
        row["event_lines"] = event_lines
        return row

    for value in paths:
        path = _resolve_path(value)
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        current_post: Optional[str] = None
        for line_number, line in enumerate(text.splitlines(), 1):
            vlm = _VLM_REQUEST_RE.search(line)
            if vlm:
                post_id = vlm.group(1)
                row = touch(post_id, path, line_number, "vlm_request")
                row["vlm_calls_observed"] = int(row.get("vlm_calls_observed") or 0) + 1
            start = _ORCHESTRATOR_START_RE.search(line)
            if start:
                current_post = start.group(1)
                row = touch(current_post, path, line_number, "orchestrator_start")
                row["orchestrator_start_count"] = int(
                    row.get("orchestrator_start_count") or 0
                ) + 1
                continue
            context = _LLM_CONTEXT_RE.search(line)
            if context and current_post is not None:
                row = touch(current_post, path, line_number, "llm_context")
                row["expert_prompt_calls_observed"] = int(
                    row.get("expert_prompt_calls_observed") or 0
                ) + 1
                tags = dict(row.get("llm_tags") or {})
                tag = context.group(1)
                tags[tag] = int(tags.get(tag) or 0) + 1
                row["llm_tags"] = dict(sorted(tags.items()))
            complete = _POST_COMPLETE_RE.search(line)
            if complete:
                post_id = complete.group(1)
                row = touch(post_id, path, line_number, "post_complete")
                row["post_complete_count"] = int(row.get("post_complete_count") or 0) + 1
                row["wall_ms_observed"] = round(float(complete.group(2)) * 1000)
                if current_post == post_id:
                    current_post = None
        for match in _TOKEN_BLOCK_RE.finditer(text):
            post_id = match.group(1)
            line_number = text.count("\n", 0, match.start()) + 1
            row = touch(post_id, path, line_number, "token_block")
            row["token_block_count"] = int(row.get("token_block_count") or 0) + 1
            row["prompt_tokens_observed"] = int(match.group(2).replace(",", ""))
            row["completion_tokens_observed"] = int(match.group(3).replace(",", ""))
            row["total_tokens_observed"] = int(match.group(4).replace(",", ""))
    for row in rows.values():
        row.setdefault("llm_tags", {})
        source_count = len(row.get("source_logs") or [])
        start_count = int(row.get("orchestrator_start_count") or 0)
        complete_count = int(row.get("post_complete_count") or 0)
        token_count = int(row.get("token_block_count") or 0)
        if source_count > 1:
            row["attribution_status"] = "AMBIGUOUS_MULTI_LOG"
        elif start_count != 1 or complete_count != 1 or token_count > 1:
            row["attribution_status"] = "PARTIAL_OR_AMBIGUOUS"
        else:
            row["attribution_status"] = "COMPLETE_SINGLE_ATTEMPT"
        if (
            "expert_prompt_calls_observed" not in row
            and row.get("attribution_status") == "COMPLETE_SINGLE_ATTEMPT"
            and row.get("total_tokens_observed") == 0
        ):
            row["expert_prompt_calls_observed"] = 0
            row["zero_call_evidence"] = "complete_attempt_with_explicit_zero_total_tokens"
    return rows


def _cost_baseline_summary(
    baseline_rows: Sequence[Mapping[str, Any]],
    log_refs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    log_paths = [_validate_artifact_ref(ref, "worker log") for ref in log_refs]
    diagnostics = parse_sidecar_cost_logs(log_paths)
    post_ids = [str(row.get("post_id")) for row in baseline_rows]
    observed = [post_id for post_id in post_ids if post_id in diagnostics]
    covered = [
        post_id
        for post_id in observed
        if diagnostics[post_id].get("attribution_status") == "COMPLETE_SINGLE_ATTEMPT"
    ]
    token_rows = [
        diagnostics[post_id]
        for post_id in covered
        if diagnostics[post_id].get("total_tokens_observed") is not None
    ]
    wall_rows = [
        diagnostics[post_id]
        for post_id in covered
        if diagnostics[post_id].get("wall_ms_observed") is not None
    ]
    call_rows = [
        diagnostics[post_id]
        for post_id in covered
        if diagnostics[post_id].get("expert_prompt_calls_observed") is not None
    ]
    ordered_diagnostics = {
        post_id: diagnostics.get(post_id, {})
        for post_id in post_ids
    }
    wall_values = [int(row["wall_ms_observed"]) for row in wall_rows]
    return {
        "status": COST_STATUS_PARTIAL_LOG,
        "row_count": len(post_ids),
        "sidecar_log_count": len(log_refs),
        "post_id_log_coverage": len(observed),
        "complete_single_attempt_attribution": len(covered),
        "ambiguous_or_partial_attribution": len(observed) - len(covered),
        "token_aggregate_coverage": len(token_rows),
        "wall_time_coverage": len(wall_rows),
        "expert_prompt_call_coverage": len(call_rows),
        "canonical_per_post_cost_receipt": False,
        "structured_call_events": False,
        "price_table_bound": False,
        "diagnostic_only": {
            "expert_prompt_calls_observed": sum(
                int(row.get("expert_prompt_calls_observed") or 0) for row in call_rows
            ),
            "vlm_calls_observed": sum(
                int(diagnostics[post_id].get("vlm_calls_observed") or 0)
                for post_id in covered
            ),
            "total_tokens_observed": sum(
                int(row.get("total_tokens_observed") or 0) for row in token_rows
            ),
            "wall_ms_p50_observed": _percentile(wall_values, 0.50),
            "wall_ms_p95_observed": _percentile(wall_values, 0.95),
        },
        "reason_codes": [
            "saved_rows_do_not_contain_per_call_events",
            "worker_logs_are_sidecar_text_not_canonical_receipts",
            "after_runtime_not_run",
            "money_cost_not_estimable_without_bound_price_table",
        ],
        "rows": ordered_diagnostics,
    }


def _implementation_contract() -> dict[str, Any]:
    refs = {
        "harness_tool": _artifact_ref(Path(__file__)),
        "routing_contract": _artifact_ref(ROOT / "src/llm_batch/selective_compute_shadow.py"),
        "future_runtime_instrumentation": _artifact_ref(ROOT / "expert_main.py"),
        "runtime_call_graph": _artifact_ref(ROOT / "src/llm_batch/agentic_pipeline.py"),
        "physical_call_ledger_contract": _artifact_ref(ROOT / "src/llm_batch/decision_call_events.py"),
        "physical_call_independent_reader": _artifact_ref(
            ROOT / "src/llm_batch/decision_call_readback.py"
        ),
        "physical_call_wrapper": _artifact_ref(ROOT / "src/llm_batch/decision_tracing_llm.py"),
        "after_source_only_router": _artifact_ref(
            ROOT / "src/llm_batch/early_route_measurement.py"
        ),
        "paired_measurement_reader": _artifact_ref(
            ROOT / "src/llm_batch/paired_measurement_readback.py"
        ),
        "paired_measurement_cli": _artifact_ref(
            ROOT / "tools/run_paired_measurement_readback.py"
        ),
        "physical_retry_observer": _artifact_ref(ROOT / "src/llm_batch/llm/client.py"),
        "publication_cost_noninterference": _artifact_ref(ROOT / "src/llm_batch/publication_commit.py"),
        "recovery_tool": _artifact_ref(ROOT / "tools/recover_expert_run_from_checkpoint.py"),
        "contract_tests": _artifact_ref(ROOT / "tests/test_selective_compute_shadow_contract.py"),
        "harness_tests": _artifact_ref(ROOT / "tests/test_selective_compute_shadow_harness.py"),
        "ledger_contract_tests": _artifact_ref(ROOT / "tests/test_decision_call_events.py"),
        "ledger_independent_reader_tests": _artifact_ref(
            ROOT / "tests/test_decision_call_readback.py"
        ),
        "early_route_contract_tests": _artifact_ref(
            ROOT / "tests/test_early_route_measurement.py"
        ),
        "early_route_runtime_tests": _artifact_ref(
            ROOT / "tests/test_expert_main_early_route_measurement.py"
        ),
        "paired_measurement_reader_tests": _artifact_ref(
            ROOT / "tests/test_paired_measurement_readback.py"
        ),
        "wrapper_tests": _artifact_ref(ROOT / "tests/test_decision_tracing_llm.py"),
        "wrapper_adversarial_tests": _artifact_ref(ROOT / "tests/test_decision_call_tracing.py"),
        "retry_observer_tests": _artifact_ref(ROOT / "tests/test_llm_retry_observer.py"),
        "stream_provenance_tests": _artifact_ref(ROOT / "tests/test_llm_client_stream_timeout.py"),
        "publication_tests": _artifact_ref(ROOT / "tests/test_publication_decision_commit.py"),
        "publication_call_integration_tests": _artifact_ref(ROOT / "tests/test_decision_call_publication_integration.py"),
        "runtime_binding_tests": _artifact_ref(ROOT / "tests/test_expert_main_decision_call_measurement.py"),
        "recovery_tests": _artifact_ref(ROOT / "tests/test_recover_expert_run_from_checkpoint.py"),
        "fresh_measurement_recovery_tests": _artifact_ref(
            ROOT / "tests/test_fresh_measurement_recovery.py"
        ),
    }
    return {
        "artifacts": refs,
        "sha256": canonical_hash(
            {name: ref["sha256"] for name, ref in sorted(refs.items())}
        ),
    }


def _comparison_semantic_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = json.loads(json.dumps(dict(value), ensure_ascii=False))
    snapshot.pop("generated_at", None)
    return snapshot


def _validate_parent_comparison_semantics(
    *,
    stage: str,
    run_spec_path: Path,
    comparison_path: Path,
) -> dict[str, Any]:
    stored, comparison_snapshot_sha256 = _read_json_snapshot(comparison_path)
    if not isinstance(stored, dict):
        raise ValueError(f"{stage} parent comparison must be a JSON object")
    run_spec_snapshot, run_spec_snapshot_sha256 = _read_json_snapshot(run_spec_path)
    if not isinstance(run_spec_snapshot, Mapping):
        raise ValueError(f"{stage} parent RunSpec must be a JSON object")
    if stage == "P1":
        from tools.run_candidate_set_nil_shadow_harness import (
            build_saved_artifact_comparison,
        )

        rebuilt = build_saved_artifact_comparison(
            run_spec_path,
            verify_implementation=False,
        )
    elif stage == "P2":
        from tools.run_publication_exact_once_harness import build_comparison

        rebuilt = build_comparison(run_spec_path, verify_implementation=False)
    elif stage == "P3":
        from tools.run_candidate_set_calibration_shadow_harness import (
            _validate_comparison_report,
            build_comparison,
        )

        stored = _validate_comparison_report(
            stored,
            verify_implementation=False,
        )
        rebuilt = build_comparison(run_spec_path, verify_implementation=False)
    else:
        raise ValueError(f"unsupported parent comparison stage: {stage}")
    if _comparison_semantic_payload(stored) != _comparison_semantic_payload(rebuilt):
        raise ValueError(f"{stage} parent comparison semantic replay mismatch")
    run_ref = stored.get("run_spec")
    if not isinstance(run_ref, Mapping):
        raise ValueError(f"{stage} parent comparison RunSpec reference missing")
    referenced_path = _resolve_path(str(run_ref.get("path") or ""))
    if referenced_path != run_spec_path.resolve():
        raise ValueError(f"{stage} parent comparison points to another RunSpec")
    referenced_file_sha256 = run_ref.get("sha256") or run_ref.get("file_sha256")
    if referenced_file_sha256 != run_spec_snapshot_sha256:
        raise ValueError(f"{stage} parent comparison RunSpec file digest mismatch")
    if run_ref.get("self_hash") != run_spec_snapshot.get("run_spec_sha256"):
        raise ValueError(f"{stage} parent comparison RunSpec self-hash mismatch")
    if (
        _sha256_file(run_spec_path) != run_spec_snapshot_sha256
        or _sha256_file(comparison_path) != comparison_snapshot_sha256
    ):
        raise ValueError(f"{stage} parent artifacts changed during semantic replay")
    return stored


def _kpi_contract() -> dict[str, Any]:
    payload = {
        "target_policy": "NO_FIRM_NUMERIC_TARGET_UNTIL_FROZEN_ACTUAL_BASELINE",
        "primary": {
            "safe_auto_coverage": {
                "meaning_ko": "동결 라벨 행 중 안전 게이트를 모두 통과하고 정답과 일치한 자동 처리 행의 비율",
                "numerator": "correct cheap-lane terminal rows",
                "denominator": "valid frozen labeled rows",
                "source": "bound routing receipt + frozen label ledger",
                "null_rule": "동결 라벨 또는 actual readback이 없으면 null/NOT_ESTIMABLE",
            },
            "expert_escalation_rate": {
                "meaning_ko": "전체 관측 행 중 기존 full-expert 경로가 필요한 행의 비율",
                "numerator": "FULL_EXPERT_REQUIRED rows",
                "denominator": "bound routing rows",
                "source": "shadow routing receipt",
                "null_rule": "행 결속이 불완전하면 null",
            },
            "expert_calls_per_post": {
                "meaning_ko": "완료 행 1건당 구조화된 비싼 모델 호출 수",
                "numerator": "typed expert call events",
                "denominator": "finalized rows",
                "source": "structured decision cost trace",
                "null_rule": "로그 추정치만 있으면 null/NOT_ESTIMABLE",
            },
            "wall_time_per_post": {
                "meaning_ko": "동일 RunSpec의 before/after 실제 완료 시각으로 잰 행별 지연",
                "numerator": "finished_at - started_at",
                "denominator": "finalized rows",
                "source": "typed decision event + publication commit",
                "null_rule": "after runtime이 없으면 null/NOT_ESTIMABLE_NO_AFTER_RUNTIME",
            },
        },
        "guardrails": [
            "hard_risk_routed_cheap == 0",
            "public_decision_changed == 0",
            "candidate_set_changed == 0",
            "route_or_action_applied == 0",
            "false_safe_rows == 0 on frozen labels",
            "retrieval fail-close and VLM/OCR readiness remain mandatory",
            "queue zero and processed count are not approval",
        ],
        "null_semantics": {
            "NOT_ESTIMABLE": "필요한 실제 증거가 없음",
            "NOT_APPLICABLE": "구조상 해당하지 않음",
            "PARTIAL_OBSERVATION": "값은 보이나 완료 KPI로 승격할 수 없음",
            "zero": "증거로 확인된 실제 0에만 사용",
        },
    }
    return {**payload, "contract_sha256": canonical_hash(payload)}


def _p4_contract() -> dict[str, Any]:
    return {
        "router_changes_compute_lane_only": True,
        "public_decision_fields_writable": [],
        "unknown_routes_to_full_expert": True,
        "actual_source_readback": "IMPLEMENTED_FOUNDATION_NO_ACTUAL_PAIR",
        "actual_cheap_lane_allowed": False,
        "synthetic_cheap_lane_contract_only": True,
        "actual_cost_metrics": "NULL_UNTIL_COMPLETED_PAIRED_SOURCE_REPLAY",
        "typed_physical_call_ledger": "IMPLEMENTED_BOUNDED_V1_WITH_INDEPENDENT_READER",
        "after_source_only_early_route": "IMPLEMENTED_MEASUREMENT_ONLY",
        "reference_copy_cost_classification": "REFERENCE_COPY_COST_ONLY_NOT_PRODUCTION_SAVINGS",
        "paired_run_spec_freeze": "IMPLEMENTED_NO_ACTUAL_RUN_SPEC",
        "paired_source_replay": "IMPLEMENTED_NO_ACTUAL_BEFORE_AFTER_ARTIFACTS",
        "writer_actual_kpi": "NULL_PENDING_COMPLETED_FRESH_PAIR",
        "publication_measurement_mode": "FRESH_EXECUTION_NO_PUBLIC_WRITE",
        "recovery_cost_readback": "IMPLEMENTED_FAIL_CLOSED_NO_ACTUAL_RECOVERY_RUN",
        "ledger_storage_scope": "BOUNDED_18_59_ONLY",
        "production_enable_allowed": False,
        "production_storage_upgrade_required": "APPEND_ONLY_FRAMED_WAL_V2",
        "hard_risk_codes": list(HARD_RISK_CODES),
        "operational_effect": "NONE_SHADOW_ONLY",
        "route_applied": False,
        "parallel_default_for_future_runtime": 16,
        "dashboard_required_for_future_runtime": True,
    }


def _collect_worker_log_refs(baseline_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    paths: set[Path] = set()
    for row in baseline_rows:
        run_meta = row.get("run_meta")
        if not isinstance(run_meta, Mapping):
            raise ValueError("baseline row run_meta missing")
        value = run_meta.get("worker_log_file")
        if not value:
            raise ValueError("baseline row worker_log_file missing")
        paths.add(_resolve_path(str(value)))
    return [_artifact_ref(path) for path in sorted(paths, key=str)]


def create_run_spec(
    *,
    parent_p1_run_spec_path: str | Path,
    parent_p1_comparison_path: str | Path,
    parent_p2_run_spec_path: str | Path,
    parent_p2_comparison_path: str | Path,
    parent_p3_run_spec_path: str | Path,
    parent_p3_comparison_path: str | Path,
) -> dict[str, Any]:
    from tools.run_candidate_set_calibration_shadow_harness import validate_run_spec as validate_p3
    from tools.run_candidate_set_nil_shadow_harness import validate_run_spec as validate_p1
    from tools.run_publication_exact_once_harness import validate_run_spec as validate_p2

    p1_spec, p1_rows, _ = validate_p1(parent_p1_run_spec_path, verify_implementation=False)
    p2_spec, p2_rows = validate_p2(parent_p2_run_spec_path, verify_implementation=False)
    p3_spec, _ = validate_p3(parent_p3_run_spec_path, verify_implementation=False)
    p1_comparison = _validate_parent_comparison_semantics(
        stage="P1",
        run_spec_path=_resolve_path(parent_p1_run_spec_path),
        comparison_path=_resolve_path(parent_p1_comparison_path),
    )
    p2_comparison = _validate_parent_comparison_semantics(
        stage="P2",
        run_spec_path=_resolve_path(parent_p2_run_spec_path),
        comparison_path=_resolve_path(parent_p2_comparison_path),
    )
    p3_comparison = _validate_parent_comparison_semantics(
        stage="P3",
        run_spec_path=_resolve_path(parent_p3_run_spec_path),
        comparison_path=_resolve_path(parent_p3_comparison_path),
    )
    p3_label_ref = _validate_p3_parent_chain(
        p1_spec=p1_spec,
        p2_spec=p2_spec,
        p3_spec=p3_spec,
        p1_run_spec_path=parent_p1_run_spec_path,
        p1_comparison_path=parent_p1_comparison_path,
        p2_run_spec_path=parent_p2_run_spec_path,
        p2_comparison_path=parent_p2_comparison_path,
    )
    baseline_ref = p1_spec.get("artifacts", {}).get("baseline_result")
    baseline_path = _validate_artifact_ref(baseline_ref, "P1 baseline result")
    baseline_rows = _read_json(baseline_path)
    if (
        len(p1_rows) != 18
        or len(p2_rows) != 18
        or not isinstance(baseline_rows, list)
        or len(baseline_rows) != 18
    ):
        raise ValueError("P4 parent scope must be exact Golden18")
    log_refs = _collect_worker_log_refs(baseline_rows)
    cost_summary = _cost_baseline_summary(baseline_rows, log_refs)
    artifacts = {
        "parent_p1_run_spec": _artifact_ref(parent_p1_run_spec_path),
        "parent_p1_comparison": _artifact_ref(parent_p1_comparison_path),
        "parent_p2_run_spec": _artifact_ref(parent_p2_run_spec_path),
        "parent_p2_comparison": _artifact_ref(parent_p2_comparison_path),
        "parent_p3_run_spec": _artifact_ref(parent_p3_run_spec_path),
        "parent_p3_comparison": _artifact_ref(parent_p3_comparison_path),
        "p3_label_ledger": p3_label_ref,
        "baseline_result": _artifact_ref(baseline_path),
        "worker_logs": log_refs,
    }
    spec: dict[str, Any] = {
        "schema_version": RUN_SPEC_SCHEMA,
        "generated_at": _now(),
        "mode": MODE,
        "artifacts": artifacts,
        "parent_contract": {
            "p1_run_spec_sha256": p1_spec.get("run_spec_sha256"),
            "p2_run_spec_sha256": p2_spec.get("run_spec_sha256"),
            "p3_run_spec_sha256": p3_spec.get("run_spec_sha256"),
            "row_count": 18,
            "p1_probability": p1_comparison.get("gates", {}).get("probability"),
            "p1_candidate_set_recall": p1_comparison.get("gates", {}).get("candidate_set_recall"),
            "p2_runtime": p2_comparison.get("gates", {}).get("production_runtime"),
            "p3_actual_dataset": p3_comparison.get("gates", {}).get("actual_calibration_dataset"),
            "p3_actual_readback": p3_comparison.get("gates", {}).get("actual_artifact_readback"),
            "p3_label_ledger_sha256": p3_label_ref["sha256"],
        },
        "policies": {
            "saved_golden_readiness": SelectiveComputePolicy.create(EVIDENCE_SCOPE_SAVED).to_dict(),
            "synthetic_contract": SelectiveComputePolicy.create(EVIDENCE_SCOPE_SYNTHETIC).to_dict(),
        },
        "kpi_contract": _kpi_contract(),
        "cost_baseline": {
            key: value for key, value in cost_summary.items() if key != "rows"
        },
        "p4_contract": _p4_contract(),
        "implementation_contract": _implementation_contract(),
        "runtime_validation": "NOT_RUN",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
    }
    spec["run_spec_sha256"] = _run_spec_self_hash(spec)
    return spec


def validate_run_spec_dict(spec: Mapping[str, Any]) -> dict[str, Any]:
    from tools.run_candidate_set_calibration_shadow_harness import validate_run_spec as validate_p3
    from tools.run_candidate_set_nil_shadow_harness import validate_run_spec as validate_p1
    from tools.run_publication_exact_once_harness import validate_run_spec as validate_p2

    if spec.get("schema_version") != RUN_SPEC_SCHEMA or spec.get("mode") != MODE:
        raise ValueError("unsupported P4 run spec")
    if spec.get("run_spec_sha256") != _run_spec_self_hash(spec):
        raise ValueError("P4 run spec self hash mismatch")
    if spec.get("runtime_validation") != "NOT_RUN":
        raise ValueError("P4 runtime boundary mismatch")
    if spec.get("semantic_quality") != "REVIEW-LOCKED" or spec.get("full_scan_approval") is not False:
        raise ValueError("P4 approval boundary mismatch")
    artifacts = spec.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise ValueError("P4 artifact map missing")
    paths = {
        name: _validate_artifact_ref(artifacts.get(name), name)
        for name in (
            "parent_p1_run_spec",
            "parent_p1_comparison",
            "parent_p2_run_spec",
            "parent_p2_comparison",
            "parent_p3_run_spec",
            "parent_p3_comparison",
            "p3_label_ledger",
            "baseline_result",
        )
    }
    log_refs = artifacts.get("worker_logs")
    if not isinstance(log_refs, list) or not log_refs:
        raise ValueError("P4 worker log refs missing")
    for index, ref in enumerate(log_refs):
        _validate_artifact_ref(ref, f"worker log {index}")
    p1_spec, p1_rows, _ = validate_p1(paths["parent_p1_run_spec"], verify_implementation=False)
    p2_spec, p2_rows = validate_p2(paths["parent_p2_run_spec"], verify_implementation=False)
    p3_spec, _ = validate_p3(paths["parent_p3_run_spec"], verify_implementation=False)
    p3_label_ref = _validate_p3_parent_chain(
        p1_spec=p1_spec,
        p2_spec=p2_spec,
        p3_spec=p3_spec,
        p1_run_spec_path=paths["parent_p1_run_spec"],
        p1_comparison_path=paths["parent_p1_comparison"],
        p2_run_spec_path=paths["parent_p2_run_spec"],
        p2_comparison_path=paths["parent_p2_comparison"],
    )
    if dict(artifacts["p3_label_ledger"]) != p3_label_ref:
        raise ValueError("P4 P3 label ledger binding mismatch")
    label_ledger = _read_json(paths["p3_label_ledger"])
    label_rows = label_ledger.get("rows") if isinstance(label_ledger, Mapping) else None
    if not isinstance(label_rows, list) or len(label_rows) != 18:
        raise ValueError("P4 P3 label ledger row count mismatch")
    if _artifact_ref(paths["p3_label_ledger"]) != p3_label_ref:
        raise ValueError("P4 P3 label ledger changed during validation")
    baseline_rows = _read_json(paths["baseline_result"])
    if (
        len(p1_rows) != 18
        or len(p2_rows) != 18
        or not isinstance(baseline_rows, list)
        or len(baseline_rows) != 18
    ):
        raise ValueError("P4 parent Golden18 row count mismatch")
    if _artifact_ref(paths["baseline_result"]) != dict(artifacts["baseline_result"]):
        raise ValueError("P4 baseline result binding mismatch")
    parent = spec.get("parent_contract")
    p1_comparison = _validate_parent_comparison_semantics(
        stage="P1",
        run_spec_path=paths["parent_p1_run_spec"],
        comparison_path=paths["parent_p1_comparison"],
    )
    p2_comparison = _validate_parent_comparison_semantics(
        stage="P2",
        run_spec_path=paths["parent_p2_run_spec"],
        comparison_path=paths["parent_p2_comparison"],
    )
    p3_comparison = _validate_parent_comparison_semantics(
        stage="P3",
        run_spec_path=paths["parent_p3_run_spec"],
        comparison_path=paths["parent_p3_comparison"],
    )
    expected_parent = {
        "p1_run_spec_sha256": p1_spec.get("run_spec_sha256"),
        "p2_run_spec_sha256": p2_spec.get("run_spec_sha256"),
        "p3_run_spec_sha256": p3_spec.get("run_spec_sha256"),
        "row_count": 18,
        "p1_probability": p1_comparison.get("gates", {}).get("probability"),
        "p1_candidate_set_recall": p1_comparison.get("gates", {}).get("candidate_set_recall"),
        "p2_runtime": p2_comparison.get("gates", {}).get("production_runtime"),
        "p3_actual_dataset": p3_comparison.get("gates", {}).get("actual_calibration_dataset"),
        "p3_actual_readback": p3_comparison.get("gates", {}).get("actual_artifact_readback"),
        "p3_label_ledger_sha256": p3_label_ref["sha256"],
    }
    if parent != expected_parent:
        raise ValueError("P4 parent contract mismatch")
    policies = spec.get("policies")
    if not isinstance(policies, Mapping):
        raise ValueError("P4 policies missing")
    expected_policies = {
        "saved_golden_readiness": SelectiveComputePolicy.create(EVIDENCE_SCOPE_SAVED).to_dict(),
        "synthetic_contract": SelectiveComputePolicy.create(EVIDENCE_SCOPE_SYNTHETIC).to_dict(),
    }
    if policies != expected_policies:
        raise ValueError("P4 routing policy binding mismatch")
    if spec.get("kpi_contract") != _kpi_contract():
        raise ValueError("P4 KPI contract mismatch")
    expected_cost = _cost_baseline_summary(baseline_rows, log_refs)
    if spec.get("cost_baseline") != {
        key: value for key, value in expected_cost.items() if key != "rows"
    }:
        raise ValueError("P4 partial cost baseline mismatch")
    expected_p4_contract = _p4_contract()
    if spec.get("p4_contract") != expected_p4_contract:
        raise ValueError("P4 selective-compute contract mismatch")
    implementation = spec.get("implementation_contract")
    if not isinstance(implementation, Mapping) or not isinstance(implementation.get("artifacts"), Mapping):
        raise ValueError("P4 implementation contract missing")
    expected_implementation = _implementation_contract()
    if implementation != expected_implementation:
        raise ValueError("P4 implementation contract mismatch")
    hashes: dict[str, str] = {}
    for name, ref in implementation["artifacts"].items():
        hashes[str(name)] = _sha256_file(
            _validate_artifact_ref(ref, f"implementation {name}")
        )
    if implementation.get("sha256") != canonical_hash(dict(sorted(hashes.items()))):
        raise ValueError("P4 implementation contract fingerprint mismatch")
    return {
        "p1_spec": p1_spec,
        "p1_rows": p1_rows,
        "baseline_rows": baseline_rows,
        "p1_comparison": p1_comparison,
        "p2_comparison": p2_comparison,
        "p3_comparison": p3_comparison,
        "label_ledger_rows": label_rows,
        "cost_diagnostics": expected_cost,
    }


def validate_run_spec(path: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    spec = _read_json(path)
    if not isinstance(spec, dict):
        raise ValueError("P4 run spec must be a JSON object")
    return spec, validate_run_spec_dict(spec)


def _binding_payloads(
    raw_row: Mapping[str, Any],
    p1_row: Mapping[str, Any],
    label_row: Mapping[str, Any],
) -> dict[str, Any]:
    analysis = raw_row.get("analysis_result")
    identity = analysis.get("identity") if isinstance(analysis, Mapping) else {}
    identity = identity if isinstance(identity, Mapping) else {}
    promotion = identity.get("promotion_decision")
    promotion = promotion if isinstance(promotion, Mapping) else {}
    run_meta = raw_row.get("run_meta")
    run_meta = run_meta if isinstance(run_meta, Mapping) else {}
    values = {
        "source_input": {
            "post_id": raw_row.get("post_id"),
            "title": raw_row.get("title"),
            "content": raw_row.get("content"),
            "comments": raw_row.get("comments"),
            "image_urls": raw_row.get("image_urls"),
        },
        "post_content_blocks": raw_row.get("content_blocks"),
        "comments": raw_row.get("comment_metadata") or raw_row.get("comments"),
        "image_url_inventory": raw_row.get("image_urls"),
        "candidate_generation_metadata": p1_row.get("candidate_generation"),
        "candidate_producer_plan_set": identity.get("candidate_producer_plans")
        or {"status": "UNKNOWN_NOT_EXPOSED"},
        "candidate_producer_receipt_set": identity.get("candidate_producer_receipts")
        or {"status": "UNKNOWN_NOT_EXPOSED"},
        "candidate_set": p1_row.get("candidate_set"),
        "search_health": identity.get("search_health") or run_meta.get("search_health"),
        "retrieval_state": identity.get("promotion_gate_evidence")
        or {"status": "UNKNOWN_NOT_EXPOSED"},
        "vlm_ocr_execution": {
            key: identity.get(key)
            for key in (
                "vlm_enabled",
                "ocr_enabled",
                "vlm_enrichment_used",
                "image_fetch_count",
                "image_fetch_success",
                "vlm_chunks_sent",
                "vlm_total_bytes",
                "image_enrichment_limitations",
            )
        },
        "image_evidence_catalog": identity.get("image_evidence_catalog"),
        "scope_state": promotion.get("scope") or identity.get("promotion_gate_state"),
        "promotion_gate_state": identity.get("promotion_gate_state"),
        "promotion_gate_evidence": identity.get("promotion_gate_evidence"),
        "judge_packet": {
            "source": "P1 label ledger",
            "post_id": label_row.get("post_id"),
        },
        "judge_verdict": label_row,
        "budget_scope": {
            key: run_meta.get(key)
            for key in (
                "run_id",
                "model",
                "requested_parallel",
                "effective_parallel",
                "config_hash",
            )
        },
    }
    if tuple(sorted(values)) != REQUIRED_BINDING_NAMES:
        raise ValueError("actual binding payload names mismatch")
    return values


def _scope_status(promotion: Mapping[str, Any]) -> str:
    scope = promotion.get("scope")
    scope_kind = str(scope.get("scope_kind") or "") if isinstance(scope, Mapping) else ""
    if scope_kind == "current_work":
        return "CURRENT_WORK"
    if scope_kind in {"referenced_work", "multi_work", "non_work"}:
        return "NOT_CURRENT_WORK"
    return "UNKNOWN"


def _build_saved_observations(
    spec: Mapping[str, Any],
    context: Mapping[str, Any],
) -> list[SelectiveComputeObservation]:
    p1_rows = context["p1_comparison"].get("rows")
    baseline_rows = context["baseline_rows"]
    labels = context.get("label_ledger_rows")
    if not isinstance(p1_rows, list) or not isinstance(labels, list):
        raise ValueError("P4 saved source rows missing")
    raw_by_post = {str(row.get("post_id")): row for row in baseline_rows}
    label_by_post = {str(row.get("post_id")): row for row in labels}
    diagnostics = context["cost_diagnostics"]["rows"]
    scope_id = f"p4-saved-{spec['run_spec_sha256'][:16]}"
    observations: list[SelectiveComputeObservation] = []
    for index, p1_row in enumerate(p1_rows):
        post_id = str(p1_row.get("post_id"))
        raw = raw_by_post.get(post_id)
        label = label_by_post.get(post_id)
        if not isinstance(raw, Mapping) or not isinstance(label, Mapping):
            raise ValueError(f"saved row binding missing for {post_id}")
        analysis = raw.get("analysis_result")
        identity = analysis.get("identity") if isinstance(analysis, Mapping) else {}
        identity = identity if isinstance(identity, Mapping) else {}
        promotion = identity.get("promotion_decision")
        promotion = promotion if isinstance(promotion, Mapping) else {}
        public = p1_row.get("public_noninterference")
        candidate_set = p1_row.get("candidate_set")
        generation = p1_row.get("candidate_generation")
        if not isinstance(public, Mapping) or not isinstance(candidate_set, Mapping) or not isinstance(generation, Mapping):
            raise ValueError(f"P1 row contract missing for {post_id}")
        bindings = {
            name: canonical_hash(value)
            for name, value in _binding_payloads(raw, p1_row, label).items()
        }
        search_health = identity.get("search_health")
        search_health = search_health if isinstance(search_health, Mapping) else {}
        search_status = str(search_health.get("status") or "").lower()
        if search_status == "ok" and int(search_health.get("unrecovered_degraded") or 0) == 0:
            routed_search_status = "HEALTHY"
        elif search_status:
            routed_search_status = "DEGRADED"
        else:
            routed_search_status = "UNKNOWN"
        image_count = int(raw.get("image_count") or 0)
        if image_count > 0:
            vlm_requirement = "REQUIRED"
            vlm_status = (
                "COMPLETE"
                if bool(identity.get("vlm_enrichment_used"))
                and int(identity.get("vlm_chunks_sent") or 0) > 0
                else "INCOMPLETE"
            )
        else:
            vlm_requirement = "NOT_REQUIRED"
            vlm_status = "NOT_APPLICABLE"
        publish_clean = bool(promotion.get("publish_allowed")) and promotion.get("bypassed_gate") is False
        diag = diagnostics.get(post_id) if isinstance(diagnostics, Mapping) else {}
        diag = diag if isinstance(diag, Mapping) else {}
        cost_digest = canonical_hash(
            {
                "status": COST_STATUS_PARTIAL_LOG,
                "worker_logs": spec["artifacts"]["worker_logs"],
                "post_id": post_id,
                "diagnostic": diag,
            }
        )
        publication_input = public.get("publish_contract_input_fingerprint")
        if not isinstance(publication_input, str) or len(publication_input) != 64:
            publication_input = canonical_hash(public)
        candidate_fingerprint = candidate_set.get("candidate_set_fingerprint")
        if not isinstance(candidate_fingerprint, str) or len(candidate_fingerprint) != 64:
            candidate_fingerprint = canonical_hash(candidate_set)
        public_before = str(public.get("before_sha256") or canonical_hash(public))
        public_after = str(public.get("after_sha256") or canonical_hash(public))
        observations.append(
            SelectiveComputeObservation.create(
                evidence_scope=EVIDENCE_SCOPE_SAVED,
                publication_scope_id=scope_id,
                attempt_run_id=str(raw.get("run_meta", {}).get("run_id") or "saved-golden"),
                input_index=index,
                post_id=post_id,
                binding_digests=bindings,
                publication_input_fingerprint=publication_input,
                baseline_decision_fingerprint=canonical_hash(promotion),
                baseline_publication_before_fingerprint=public_before,
                baseline_publication_after_fingerprint=public_after,
                candidate_set_before_fingerprint=candidate_fingerprint,
                candidate_set_after_fingerprint=candidate_fingerprint,
                source_binding_status="VALID",
                search_requirement_status="UNKNOWN",
                search_health_status=routed_search_status,
                producer_proof_status="UNKNOWN",
                candidate_generation_status=str(generation.get("status") or "UNKNOWN"),
                candidate_conflict_status="UNKNOWN",
                vlm_ocr_requirement_status=vlm_requirement,
                vlm_ocr_status=vlm_status,
                publication_status="CLEAN" if publish_clean else "HOLD",
                judge_coverage_status=(
                    "UNJUDGED" if str(label.get("truth_kind")) == "UNJUDGED" else "COMPLETE"
                ),
                scope_status=_scope_status(promotion),
                calibration_status="NOT_AVAILABLE",
                budget_binding_status="UNKNOWN",
                cheap_terminal_status="NOT_VERIFIED",
                proposed_terminal_action=ACTION_NONE,
                proposed_selected_label=None,
                cost_evidence_status=COST_STATUS_PARTIAL_LOG,
                cost_evidence_digest=cost_digest,
                baseline_expert_calls=diag.get("expert_prompt_calls_observed"),
                baseline_total_tokens=diag.get("total_tokens_observed"),
                baseline_wall_ms=diag.get("wall_ms_observed"),
            )
        )
    return observations


def _synthetic_observation(
    *,
    post_id: str,
    input_index: int,
    action: str,
    label: str,
) -> SelectiveComputeObservation:
    hashes = {
        name: canonical_hash({"synthetic": post_id, "binding": name})
        for name in REQUIRED_BINDING_NAMES
    }
    public = canonical_hash({"synthetic": post_id, "public": "unchanged"})
    candidate = canonical_hash({"synthetic": post_id, "candidate": "unchanged"})
    return SelectiveComputeObservation.create(
        evidence_scope=EVIDENCE_SCOPE_SYNTHETIC,
        publication_scope_id="p4-synthetic-contract",
        attempt_run_id="p4-synthetic-no-runtime",
        input_index=input_index,
        post_id=post_id,
        binding_digests=hashes,
        publication_input_fingerprint=canonical_hash({"synthetic": post_id, "input": True}),
        baseline_decision_fingerprint=canonical_hash({"synthetic": post_id, "decision": True}),
        baseline_publication_before_fingerprint=public,
        baseline_publication_after_fingerprint=public,
        candidate_set_before_fingerprint=candidate,
        candidate_set_after_fingerprint=candidate,
        source_binding_status="VALID",
        search_requirement_status="REQUIRED",
        search_health_status="HEALTHY",
        producer_proof_status="COMPLETE",
        candidate_generation_status="COMPLETE",
        candidate_conflict_status="NONE",
        vlm_ocr_requirement_status="NOT_REQUIRED",
        vlm_ocr_status="NOT_APPLICABLE",
        publication_status="CLEAN",
        judge_coverage_status="COMPLETE",
        scope_status="CURRENT_WORK",
        calibration_status="SYNTHETIC_BOUND",
        budget_binding_status="VALID",
        cheap_terminal_status=(
            "VERIFIED_DETERMINISTIC_NIL"
            if action == ACTION_ASSERT_NIL
            else "VERIFIED_DETERMINISTIC_RESOLVE"
        ),
        proposed_terminal_action=action,
        proposed_selected_label=label,
        cost_evidence_status=COST_STATUS_SYNTHETIC,
        cost_evidence_digest=canonical_hash({"synthetic": post_id, "calls": 4}),
        baseline_expert_calls=4,
        baseline_total_tokens=400,
        baseline_wall_ms=4_000,
    )


def _replace_observation(
    observation: SelectiveComputeObservation,
    **changes: Any,
) -> SelectiveComputeObservation:
    payload = observation.payload_without_observation_fingerprint()
    payload["binding_digests"] = observation.binding_digests
    payload.update(changes)
    return SelectiveComputeObservation.create(**payload)


def _build_synthetic_contract() -> dict[str, Any]:
    policy = SelectiveComputePolicy.create(EVIDENCE_SCOPE_SYNTHETIC)
    observations = [
        _synthetic_observation(
            post_id="synthetic-safe-nil",
            input_index=0,
            action=ACTION_ASSERT_NIL,
            label=NIL_LABEL,
        ),
        _synthetic_observation(
            post_id="synthetic-safe-resolve",
            input_index=1,
            action=ACTION_RESOLVE,
            label="cand_safe",
        ),
        _replace_observation(
            _synthetic_observation(
                post_id="synthetic-search-blocked",
                input_index=2,
                action=ACTION_RESOLVE,
                label="cand_search",
            ),
            search_health_status="BLOCKED",
        ),
        _replace_observation(
            _synthetic_observation(
                post_id="synthetic-multi-work",
                input_index=3,
                action=ACTION_RESOLVE,
                label="cand_multi",
            ),
            candidate_conflict_status="MULTI_WORK",
        ),
    ]
    receipts = [build_selective_compute_routing(item, policy) for item in observations]
    truth = {
        "synthetic-safe-nil": NIL_LABEL,
        "synthetic-safe-resolve": "cand_safe",
        "synthetic-search-blocked": "cand_search",
        "synthetic-multi-work": "cand_multi",
    }
    evaluation = evaluate_selective_compute_receipts(
        receipts,
        observations,
        policy,
        truth_labels=truth,
    )
    return {
        "evidence_scope": EVIDENCE_SCOPE_SYNTHETIC,
        "actual_performance_claim_allowed": False,
        "observations": [item.to_dict() for item in observations],
        "receipts": [item.to_dict() for item in receipts],
        "truth_labels": truth,
        "evaluation": evaluation,
        "before_after_fixture_math": {
            "row_count": 4,
            "before_full_expert_calls": 16,
            "after_shadow_calls": 8,
            "avoided_calls": 8,
            "avoidance_rate": 0.5,
            "status": "SYNTHETIC_CONTRACT_ONLY_NOT_ACTUAL_SAVINGS",
        },
    }


def _run_attack_suite() -> dict[str, Any]:
    policy = SelectiveComputePolicy.create(EVIDENCE_SCOPE_SYNTHETIC)
    base = _synthetic_observation(
        post_id="attack-base",
        input_index=0,
        action=ACTION_ASSERT_NIL,
        label=NIL_LABEL,
    )
    status_attacks: list[tuple[str, dict[str, Any], str]] = [
        ("search_requirement_unknown", {"search_requirement_status": "UNKNOWN", "search_health_status": "UNKNOWN"}, "SEARCH_REQUIRED_OR_UNKNOWN"),
        ("search_not_required_laundering", {"search_requirement_status": "NOT_REQUIRED", "search_health_status": "DEGRADED"}, "SEARCH_DEGRADED_OR_BLOCKED"),
        ("producer_incomplete", {"producer_proof_status": "INCOMPLETE"}, "PRODUCER_PROOF_NOT_COMPLETE"),
        ("candidate_unknown", {"candidate_generation_status": "UNKNOWN"}, "CANDIDATE_GENERATION_UNKNOWN"),
        ("candidate_truncated", {"candidate_generation_status": "TRUNCATED"}, "CANDIDATE_GENERATION_TRUNCATED"),
        ("multi_work", {"candidate_conflict_status": "MULTI_WORK"}, "MULTI_WORK_OR_IDENTITY_CONFLICT"),
        ("vlm_missing", {"vlm_ocr_requirement_status": "REQUIRED", "vlm_ocr_status": "INCOMPLETE"}, "VLM_OCR_REQUIRED_NOT_COMPLETE"),
        ("vlm_conflict", {"vlm_ocr_requirement_status": "REQUIRED", "vlm_ocr_status": "CONFLICT"}, "VLM_OCR_TITLE_CONFLICT"),
        ("publication_hold", {"publication_status": "HOLD"}, "PUBLICATION_HOLD_OR_QUARANTINE"),
        ("unjudged", {"judge_coverage_status": "UNJUDGED"}, "UNJUDGED_OR_INVALID_VERDICT"),
        ("scope_unknown", {"scope_status": "UNKNOWN"}, "SCOPE_UNKNOWN_OR_NOT_CURRENT_WORK"),
        ("source_binding_invalid", {"source_binding_status": "INVALID"}, "SOURCE_BINDING_INVALID"),
        ("calibration_missing", {"calibration_status": "NOT_AVAILABLE"}, "CALIBRATION_ACTUAL_NOT_BOUND"),
        ("budget_laundering", {"budget_binding_status": "INVALID"}, "BUDGET_SCOPE_INVALID"),
        ("terminal_unverified", {"cheap_terminal_status": "NOT_VERIFIED", "proposed_terminal_action": ACTION_NONE, "proposed_selected_label": None}, "CHEAP_TERMINAL_NOT_VERIFIED"),
    ]
    rows: list[dict[str, Any]] = []
    false_cheap = 0
    for name, changes, expected in status_attacks:
        observation = _replace_observation(base, **changes)
        receipt = build_selective_compute_routing(observation, policy)
        blocked = receipt.selected_compute_lane == LANE_FULL_EXPERT and expected in receipt.hard_risk_codes
        if receipt.selected_compute_lane == LANE_CHEAP_RULE:
            false_cheap += 1
        rows.append(
            {
                "attack": name,
                "expected": expected,
                "outcome": "FULL_EXPERT_REQUIRED" if blocked else "FAILED",
                "false_cheap": receipt.selected_compute_lane == LANE_CHEAP_RULE,
            }
        )
    rejection_attacks: list[tuple[str, Callable[[], Any]]] = [
        (
            "public_fingerprint_mutation",
            lambda: _replace_observation(
                base,
                baseline_publication_after_fingerprint=canonical_hash("forged-public"),
            ),
        ),
        (
            "candidate_set_mutation",
            lambda: _replace_observation(
                base,
                candidate_set_after_fingerprint=canonical_hash("forged-candidates"),
            ),
        ),
        (
            "forged_action_applied",
            lambda: selective_compute_routing_receipt_from_dict(
                _forge_receipt(build_selective_compute_routing(base, policy), "action_applied", True)
            ),
        ),
        (
            "forged_route_applied",
            lambda: selective_compute_routing_receipt_from_dict(
                _forge_receipt(build_selective_compute_routing(base, policy), "route_applied", True)
            ),
        ),
        (
            "partial_cost_laundered_numeric",
            lambda: selective_compute_routing_receipt_from_dict(
                _forge_partial_cost_laundering(build_selective_compute_routing(base, policy))
            ),
        ),
    ]
    for name, attack in rejection_attacks:
        try:
            attack()
        except (TypeError, ValueError):
            rows.append(
                {
                    "attack": name,
                    "expected": "REJECTED",
                    "outcome": "REJECTED",
                    "false_cheap": False,
                }
            )
        else:
            rows.append(
                {
                    "attack": name,
                    "expected": "REJECTED",
                    "outcome": "FAILED",
                    "false_cheap": True,
                }
            )
            false_cheap += 1
    return {
        "attack_count": len(rows),
        "blocked_or_rejected": sum(row["outcome"] != "FAILED" for row in rows),
        "false_cheap_count": false_cheap,
        "rows": rows,
    }


def _forge_receipt(receipt: Any, field_name: str, value: Any) -> dict[str, Any]:
    payload = receipt.to_dict()
    payload[field_name] = value
    payload["receipt_sha256"] = canonical_hash(
        {key: item for key, item in payload.items() if key != "receipt_sha256"}
    )
    return payload


def _forge_partial_cost_laundering(receipt: Any) -> dict[str, Any]:
    payload = receipt.to_dict()
    payload.update(
        {
            "cost_metric_status": "NOT_ESTIMABLE",
            "baseline_expert_calls": 4,
            "shadow_expert_calls": 0,
            "expert_call_units_avoided": 4,
        }
    )
    payload["receipt_sha256"] = canonical_hash(
        {key: item for key, item in payload.items() if key != "receipt_sha256"}
    )
    return payload


def _function_guide_ko() -> dict[str, str]:
    return {
        "shadow_router": "게시글의 공개 제목을 정하는 기능이 아니라, 기존 full-expert 경로가 필요한지 관측만 하는 기능",
        "hard_risk": "검색 실패·후보 누락·복수 작품·이미지 근거 부족처럼 싸게 처리하면 위험한 조건",
        "safe_auto_coverage": "동결 라벨에서 안전 조건을 모두 통과하고 정답까지 맞은 자동 처리 범위",
        "expert_escalation_rate": "전체 글 중 기존 비싼 전문가 단계로 보내야 하는 비율",
        "partial_sidecar_log": "단계·token·시간은 보이지만 정식 행별 비용 영수증이 아니어서 비용 KPI로 확정할 수 없는 로그",
        "synthetic_contract": "가짜 입력으로 계산식과 안전 차단만 시험한 결과이며 실제 정확도·절감률이 아님",
        "public_noninterference": "라우터가 official_title, URL, promotion decision, CandidateSet을 전혀 바꾸지 않는 불변식",
        "typed_call_ledger": "물리 model send의 intent와 성공·실패 terminal을 retry까지 별도 attempt 원장에 남기는 기능",
        "independent_call_reader": "writer를 믿지 않고 원장 frame을 다시 읽어 호출·retry·token과 source snapshot을 계산하는 기능",
        "after_source_only_route": "AFTER 측정에서 원문 신호가 있으면 full, 완전히 빈 신호만 deterministic NIL 0-call 후보로 보내는 기능",
        "reference_copy_cost": "0-call cheap 행이 authoritative WAL 복사임을 표시해 production 절감 KPI에서 제외하는 분류",
        "paired_source_replay": "RunSpec·실제 input/output·WAL·ledger·route receipt를 다시 읽어 동일 BEFORE/AFTER인지 확인하는 기능",
        "measurement_no_public_write": "paired 측정은 기존 WAL을 0-call replay하지 않고 재실행하되 공개 판정 WAL에는 새로 쓰지 않는 기능",
        "bounded_storage_gate": "현재 immutable-frame v1을 18/59 검증에만 허용하고 104k production에서는 막는 확장성 안전장치",
    }


def _limits_ko() -> list[str]:
    return [
        "Golden18 저장 행에는 구조화된 expert call event가 없다.",
        "typed physical-call ledger·독립 reader·AFTER source-only route·paired source replay는 구현했지만 새 runtime에서 아직 실행하지 않았다.",
        "저장 Golden18에는 새 ledger/route artifact가 없어 actual KPI는 null이다.",
        "원장 v1은 frame별 전역 reload와 small-file 구조라 18/59 bounded 전용이며 104k production enable은 금지된다.",
        "fresh recovery fail-closed gate는 구현됐지만 실제 강제 중단·재시작 paired run은 없다.",
        "worker log 진단값은 canonical 비용 영수증이 아니다.",
        "P3 FROZEN_ACTUAL bytes/coverage/prediction reader와 bootstrap 기반은 구현됐지만 actual dataset/output이 없다.",
        "after runtime을 실행하지 않아 실제 지연·호출·비용 절감률은 null이다.",
        "합성 4행 결과를 실제 정확도나 비용 절감률로 인용하면 안 된다.",
        "현재 active 104k production run은 건드리지 않았다.",
    ]


def build_comparison(spec: Mapping[str, Any]) -> dict[str, Any]:
    context = validate_run_spec_dict(spec)
    saved_policy = SelectiveComputePolicy.create(EVIDENCE_SCOPE_SAVED)
    saved_observations = _build_saved_observations(spec, context)
    saved_receipts = [
        build_selective_compute_routing(item, saved_policy)
        for item in saved_observations
    ]
    saved_evaluation = evaluate_selective_compute_receipts(
        saved_receipts,
        saved_observations,
        saved_policy,
        truth_labels=None,
        actual_evidence_readback=False,
    )
    synthetic = _build_synthetic_contract()
    attacks = _run_attack_suite()
    public_unchanged = sum(
        not item.public_decision_changed and not item.candidate_set_changed
        for item in saved_receipts
    )
    comparison: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA,
        "generated_at": _now(),
        "mode": MODE,
        "run_spec_sha256": spec["run_spec_sha256"],
        "function_guide_ko": _function_guide_ko(),
        "actual_saved_golden": {
            "evidence_scope": EVIDENCE_SCOPE_SAVED,
            "row_count": len(saved_receipts),
            "cost_baseline": context["cost_diagnostics"],
            "observations": [item.to_dict() for item in saved_observations],
            "receipts": [item.to_dict() for item in saved_receipts],
            "evaluation": saved_evaluation,
            "before_after": {
                "before": "PARTIAL_SIDECAR_LOG",
                "after": "SHADOW_ROUTE_ONLY_NO_RUNTIME",
                "actual_cost_delta": None,
                "actual_cost_delta_status": "NOT_ESTIMABLE",
                "public_contract_unchanged_rows": public_unchanged,
            },
        },
        "synthetic_contract": synthetic,
        "adversarial_contract": attacks,
        "gates": {
            "artifact_integrity": "GO",
            "hard_risk_fail_close": (
                "GO_SYNTHETIC_ONLY" if attacks["false_cheap_count"] == 0 else "NO_GO"
            ),
            "public_noninterference": "GO",
            "actual_cost_baseline": "PARTIAL_SIDECAR_LOG",
            "actual_source_readback": "IMPLEMENTED_FOUNDATION_NO_ACTUAL_PAIR",
            "actual_cost_delta": "NOT_ESTIMABLE",
            "actual_accuracy_and_safe_coverage": "NOT_ESTIMABLE",
            "synthetic_math": "GO_SYNTHETIC_ONLY",
            "future_runtime_instrumentation": (
                "IMPLEMENTED_READER_ROUTER_PAIRED_HARNESS_NOT_RUNTIME_EXECUTED"
            ),
            "runtime_validation": "NOT_RUN",
            "semantic_quality": "REVIEW-LOCKED",
            "full_scan_approval": False,
            "overall": "GO_P4_SHADOW_CONTRACT_FOUNDATION_ONLY",
            "goal": "ACTIVE_NOT_COMPLETE",
        },
        "limits": _limits_ko(),
        "runtime_validation": "NOT_RUN",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
    }
    validate_comparison(comparison, spec)
    return comparison


def validate_comparison(comparison: Mapping[str, Any], spec: Mapping[str, Any]) -> None:
    context = validate_run_spec_dict(spec)
    expected_top_keys = {
        "schema_version",
        "generated_at",
        "mode",
        "run_spec_sha256",
        "function_guide_ko",
        "actual_saved_golden",
        "synthetic_contract",
        "adversarial_contract",
        "gates",
        "limits",
        "runtime_validation",
        "semantic_quality",
        "full_scan_approval",
    }
    if set(comparison) != expected_top_keys:
        raise ValueError("P4 comparison top-level shape mismatch")
    if comparison.get("schema_version") != REPORT_SCHEMA or comparison.get("mode") != MODE:
        raise ValueError("unsupported P4 comparison schema")
    if comparison.get("run_spec_sha256") != spec.get("run_spec_sha256"):
        raise ValueError("P4 comparison RunSpec binding mismatch")
    if comparison.get("function_guide_ko") != _function_guide_ko():
        raise ValueError("P4 Korean function guide mismatch")
    if comparison.get("runtime_validation") != "NOT_RUN":
        raise ValueError("P4 comparison runtime boundary mismatch")
    if comparison.get("semantic_quality") != "REVIEW-LOCKED" or comparison.get("full_scan_approval") is not False:
        raise ValueError("P4 comparison approval boundary mismatch")
    actual = comparison.get("actual_saved_golden")
    if not isinstance(actual, Mapping):
        raise ValueError("P4 actual saved section missing")
    if set(actual) != {
        "evidence_scope",
        "row_count",
        "cost_baseline",
        "observations",
        "receipts",
        "evaluation",
        "before_after",
    }:
        raise ValueError("P4 actual saved section shape mismatch")
    if actual.get("evidence_scope") != EVIDENCE_SCOPE_SAVED or actual.get("row_count") != 18:
        raise ValueError("P4 actual saved scope mismatch")
    saved_observations = [
        selective_compute_observation_from_dict(item)
        for item in actual.get("observations", [])
    ]
    saved_receipts = [
        selective_compute_routing_receipt_from_dict(item)
        for item in actual.get("receipts", [])
    ]
    expected_saved_observations = _build_saved_observations(spec, context)
    expected_saved_receipts = [
        build_selective_compute_routing(
            item,
            SelectiveComputePolicy.create(EVIDENCE_SCOPE_SAVED),
        )
        for item in expected_saved_observations
    ]
    if [item.to_dict() for item in saved_observations] != [
        item.to_dict() for item in expected_saved_observations
    ]:
        raise ValueError("P4 saved observation/source binding mismatch")
    if [item.to_dict() for item in saved_receipts] != [
        item.to_dict() for item in expected_saved_receipts
    ]:
        raise ValueError("P4 saved receipt/source replay mismatch")
    saved_evaluation = evaluate_selective_compute_receipts(
        expected_saved_receipts,
        expected_saved_observations,
        SelectiveComputePolicy.create(EVIDENCE_SCOPE_SAVED),
        truth_labels=None,
        actual_evidence_readback=False,
    )
    if actual.get("evaluation") != saved_evaluation:
        raise ValueError("P4 saved evaluation replay mismatch")
    if actual.get("cost_baseline") != context["cost_diagnostics"]:
        raise ValueError("P4 saved cost diagnostic binding mismatch")
    if len(saved_receipts) != 18 or any(
        item.selected_compute_lane != LANE_FULL_EXPERT for item in saved_receipts
    ):
        raise ValueError("P4 saved Golden18 must fail-close to full expert")
    if any(
        metric.get("value") is not None
        for name, metric in saved_evaluation["primary_metrics"].items()
        if name != "expert_escalation_rate"
    ):
        raise ValueError("P4 actual headline cost/quality metrics must remain null")
    if actual.get("before_after") != {
        "before": "PARTIAL_SIDECAR_LOG",
        "after": "SHADOW_ROUTE_ONLY_NO_RUNTIME",
        "actual_cost_delta": None,
        "actual_cost_delta_status": "NOT_ESTIMABLE",
        "public_contract_unchanged_rows": 18,
    }:
        raise ValueError("P4 actual before/after boundary mismatch")
    synthetic = comparison.get("synthetic_contract")
    if not isinstance(synthetic, Mapping) or synthetic.get("actual_performance_claim_allowed") is not False:
        raise ValueError("P4 synthetic scope boundary missing")
    synthetic_observations = [
        selective_compute_observation_from_dict(item)
        for item in synthetic.get("observations", [])
    ]
    synthetic_receipts = [
        selective_compute_routing_receipt_from_dict(item)
        for item in synthetic.get("receipts", [])
    ]
    synthetic_evaluation = evaluate_selective_compute_receipts(
        synthetic_receipts,
        synthetic_observations,
        SelectiveComputePolicy.create(EVIDENCE_SCOPE_SYNTHETIC),
        truth_labels=dict(synthetic.get("truth_labels") or {}),
    )
    if synthetic.get("evaluation") != synthetic_evaluation:
        raise ValueError("P4 synthetic evaluation replay mismatch")
    if synthetic_evaluation.get("schema_version") != ROUTING_EVALUATION_SCHEMA:
        raise ValueError("P4 synthetic evaluation schema mismatch")
    if synthetic != _build_synthetic_contract():
        raise ValueError("P4 synthetic contract source replay mismatch")
    math_fixture = synthetic.get("before_after_fixture_math")
    if math_fixture != {
        "row_count": 4,
        "before_full_expert_calls": 16,
        "after_shadow_calls": 8,
        "avoided_calls": 8,
        "avoidance_rate": 0.5,
        "status": "SYNTHETIC_CONTRACT_ONLY_NOT_ACTUAL_SAVINGS",
    }:
        raise ValueError("P4 synthetic before/after math mismatch")
    attacks = comparison.get("adversarial_contract")
    if not isinstance(attacks, Mapping) or attacks.get("attack_count") != 20:
        raise ValueError("P4 attack suite coverage mismatch")
    if attacks.get("blocked_or_rejected") != 20 or attacks.get("false_cheap_count") != 0:
        raise ValueError("P4 false-cheap attack escaped")
    if attacks != _run_attack_suite():
        raise ValueError("P4 adversarial contract replay mismatch")
    gates = comparison.get("gates")
    if not isinstance(gates, Mapping):
        raise ValueError("P4 gates missing")
    expected_gates = {
        "artifact_integrity": "GO",
        "hard_risk_fail_close": "GO_SYNTHETIC_ONLY",
        "public_noninterference": "GO",
        "actual_cost_baseline": "PARTIAL_SIDECAR_LOG",
        "actual_source_readback": "IMPLEMENTED_FOUNDATION_NO_ACTUAL_PAIR",
        "actual_cost_delta": "NOT_ESTIMABLE",
        "actual_accuracy_and_safe_coverage": "NOT_ESTIMABLE",
        "synthetic_math": "GO_SYNTHETIC_ONLY",
        "future_runtime_instrumentation": (
            "IMPLEMENTED_READER_ROUTER_PAIRED_HARNESS_NOT_RUNTIME_EXECUTED"
        ),
        "runtime_validation": "NOT_RUN",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "overall": "GO_P4_SHADOW_CONTRACT_FOUNDATION_ONLY",
        "goal": "ACTIVE_NOT_COMPLETE",
    }
    if gates != expected_gates:
        raise ValueError("P4 comparison gate boundary mismatch")
    if comparison.get("limits") != _limits_ko():
        raise ValueError("P4 limitations boundary mismatch")


def render_markdown(
    comparison: Mapping[str, Any],
    spec: Mapping[str, Any],
) -> str:
    validate_comparison(comparison, spec)
    actual = comparison["actual_saved_golden"]
    actual_eval = actual["evaluation"]
    synthetic = comparison["synthetic_contract"]
    synthetic_eval = synthetic["evaluation"]
    cost = actual["cost_baseline"]
    attacks = comparison["adversarial_contract"]
    lines = [
        "# P4 선택적 비용 라우팅 개선 전·후 하네스",
        "",
        "> 판정: `GO_P4_SHADOW_CONTRACT_FOUNDATION_ONLY / actual cost delta NOT_ESTIMABLE / runtime NOT_RUN / REVIEW-LOCKED / full_scan_approval=false`",
        "",
        "## 기능을 쉽게 읽는 표",
        "",
        "| 기능 | 하는 일 | 하지 않는 일 |",
        "|---|---|---|",
    ]
    for name, meaning in comparison["function_guide_ko"].items():
        not_do = (
            "공개 제목·URL·판정을 바꾸지 않는다."
            if name in {"shadow_router", "public_noninterference"}
            else "실제 성능 수치로 승격하지 않는다."
        )
        lines.append(f"| `{name}` | {meaning} | {not_do} |")
    lines.extend(
        [
            "",
            "## 저장된 Golden18: 실제 기준선 준비도",
            "",
            f"- 대상: `{actual['row_count']}`행, 라우팅 결과 `FULL_EXPERT_REQUIRED={actual_eval['lane_counts'][LANE_FULL_EXPERT]}`, `CHEAP_RULE_ELIGIBLE={actual_eval['lane_counts'][LANE_CHEAP_RULE]}`",
            f"- public/CandidateSet 불변: `{actual['before_after']['public_contract_unchanged_rows']}/18`",
            f"- worker 로그 post_id 커버리지: `{cost['post_id_log_coverage']}/{cost['row_count']}`",
            f"- 로그에서 보이는 진단값: expert prompt `{cost['diagnostic_only']['expert_prompt_calls_observed']}`회, VLM `{cost['diagnostic_only']['vlm_calls_observed']}`회, total token `{cost['diagnostic_only']['total_tokens_observed']}`",
            "- 위 진단값은 `PARTIAL_SIDECAR_LOG`이며 canonical 비용 영수증이 아니다. 따라서 실제 calls/post, 비용 절감률, p95 개선률은 모두 `null/NOT_ESTIMABLE`이다.",
            "",
            "| 실제 KPI | 값 | 상태 | 뜻 |",
            "|---|---:|---|---|",
        ]
    )
    metric_meanings = {
        "safe_auto_coverage": "안전 조건과 정답을 함께 만족한 자동 처리 범위",
        "expert_escalation_rate": "shadow가 full-expert를 요구한 행 비율",
        "expert_calls_per_post": "구조화된 모델 호출 수/행",
        "expert_call_avoidance_rate": "구조화된 before 호출 중 줄어든 비율",
        "wall_time_per_post": "실제 after runtime 행별 시간",
    }
    for name, metric in actual_eval["primary_metrics"].items():
        value = "null" if metric["value"] is None else str(metric["value"])
        lines.append(f"| `{name}` | `{value}` | `{metric['status']}` | {metric_meanings[name]} |")
    lines.extend(
        [
            "",
            "## 합성 4행 개선 전·후 계약",
            "",
            "합성 fixture에서는 before `16` 호출 단위, shadow after `8`, 회피 `8/16=50%`가 계산된다. 이는 계산식과 라우팅 계약 시험일 뿐 실제 파이프라인 절감률이 아니다.",
            "",
            f"- 합성 safe auto coverage: `{synthetic_eval['primary_metrics']['safe_auto_coverage']['value']}` (`SYNTHETIC_CONTRACT_ONLY`)",
            f"- 합성 expert escalation rate: `{synthetic_eval['primary_metrics']['expert_escalation_rate']['value']}`",
            f"- 합성 calls/post: `{synthetic_eval['primary_metrics']['expert_calls_per_post']['value']}`",
            "",
            "## false-cheap 적대 테스트",
            "",
            f"- 공격 `{attacks['attack_count']}`개 중 차단/거부 `{attacks['blocked_or_rejected']}`개",
            f"- 위험한 행이 cheap으로 빠진 수: `{attacks['false_cheap_count']}`",
            "- 검색 상태 세탁, candidate UNKNOWN/TRUNCATED, 복수 작품, VLM/OCR 누락·충돌, HOLD 덮어쓰기, 미판결, cross-binding·budget 세탁, public/CandidateSet 변조를 포함한다.",
            "",
            "## 다음 실행 게이트",
            "",
            "1. `DecisionCostTrace` v1은 partial 진단이고, sibling typed call ledger와 독립 reader가 physical retry·실패·token을 재계산하도록 구현됐다. 아직 새 runtime에서 실행하지 않았다.",
            "2. paired RunSpec freeze와 input/output/WAL/ledger/route를 묶는 paired source replay를 구현했다. authoritative WAL reference-copy 0-call은 actual production 절감에서 제외한다.",
            "3. immutable-frame v1은 18/59 bounded 검증 전용이다. frame별 전역 reload·small-file 구조이므로 WAL v2와 crash/scale 검증 전 104k production enable은 금지한다.",
            "4. P3 actual dataset/readback output을 만든 뒤 동일 RunSpec·동결셋에서 fresh BEFORE/AFTER를 paired 실행한다.",
            "5. 미래 검증런은 `--parallel 16`, dashboard ON을 유지하며, 그 전에는 실제 public routing을 열지 않는다.",
            "",
            "## 승인 경계",
            "",
            "- `runtime_validation=NOT_RUN`",
            "- `semantic_quality=REVIEW-LOCKED`",
            "- `full_scan_approval=false`",
            "- queue 0 또는 처리 건수는 품질 승인 근거가 아니다.",
        ]
    )
    return "\n".join(lines) + "\n"


def _exclusive_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        if path.read_bytes() != payload:
            raise ValueError(f"immutable artifact conflict: {path}")
    if path.read_bytes() != payload:
        raise ValueError(f"artifact readback mismatch: {path}")


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def write_bundle(
    spec: Mapping[str, Any],
    comparison: Mapping[str, Any],
    output_dir: str | Path,
) -> dict[str, Path]:
    try:
        spec_snapshot = json.loads(json.dumps(dict(spec), ensure_ascii=False))
        comparison_snapshot = json.loads(
            json.dumps(dict(comparison), ensure_ascii=False)
        )
    except (TypeError, ValueError) as error:
        raise ValueError(f"P4 immutable bundle snapshot failed: {error}") from error
    validate_run_spec_dict(spec_snapshot)
    validate_comparison(comparison_snapshot, spec_snapshot)
    markdown = render_markdown(comparison_snapshot, spec_snapshot)
    directory = _resolve_path(output_dir)
    paths = {
        "run_spec": directory / "run_spec.json",
        "comparison_json": directory / "comparison.json",
        "comparison_markdown": directory / "comparison.md",
    }
    payloads = {
        "run_spec": (json.dumps(spec_snapshot, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        "comparison_json": (
            json.dumps(comparison_snapshot, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8"),
        "comparison_markdown": markdown.encode("utf-8"),
    }
    if directory.exists():
        if not directory.is_dir():
            raise ValueError(f"immutable artifact target is not a directory: {directory}")
        for name in ("run_spec", "comparison_json", "comparison_markdown"):
            if not paths[name].is_file() or paths[name].read_bytes() != payloads[name]:
                raise ValueError(f"immutable artifact conflict: {paths[name]}")
    else:
        directory.parent.mkdir(parents=True, exist_ok=True)
        staging = directory.with_name(f".{directory.name}.tmp-{uuid4().hex}")
        staging.mkdir()
        staging_paths = {
            name: staging / path.name for name, path in paths.items()
        }
        try:
            for name in ("run_spec", "comparison_json", "comparison_markdown"):
                _exclusive_write(staging_paths[name], payloads[name])
            _fsync_directory(staging)
            staged_spec = _read_json(staging_paths["run_spec"])
            staged_comparison = _read_json(staging_paths["comparison_json"])
            validate_run_spec_dict(staged_spec)
            validate_comparison(staged_comparison, staged_spec)
            if staging_paths["comparison_markdown"].read_text(encoding="utf-8") != markdown:
                raise ValueError("P4 staged markdown readback mismatch")
            try:
                staging.rename(directory)
            except OSError:
                if not directory.is_dir() or any(
                    not paths[name].is_file()
                    or paths[name].read_bytes() != payloads[name]
                    for name in ("run_spec", "comparison_json", "comparison_markdown")
                ):
                    raise
            _fsync_directory(directory.parent)
        finally:
            if staging.exists():
                for path in staging_paths.values():
                    if path.is_file():
                        path.unlink()
                staging.rmdir()
    read_spec, _ = validate_run_spec(paths["run_spec"])
    read_comparison = _read_json(paths["comparison_json"])
    validate_comparison(read_comparison, read_spec)
    if paths["comparison_markdown"].read_text(encoding="utf-8") != markdown:
        raise ValueError("P4 markdown readback mismatch")
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p1-run-spec", default=str(DEFAULT_P1_RUN_SPEC))
    parser.add_argument("--p1-comparison", default=str(DEFAULT_P1_COMPARISON))
    parser.add_argument("--p2-run-spec", default=str(DEFAULT_P2_RUN_SPEC))
    parser.add_argument("--p2-comparison", default=str(DEFAULT_P2_COMPARISON))
    parser.add_argument("--p3-run-spec", default=str(DEFAULT_P3_RUN_SPEC))
    parser.add_argument("--p3-comparison", default=str(DEFAULT_P3_COMPARISON))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()
    spec = create_run_spec(
        parent_p1_run_spec_path=args.p1_run_spec,
        parent_p1_comparison_path=args.p1_comparison,
        parent_p2_run_spec_path=args.p2_run_spec,
        parent_p2_comparison_path=args.p2_comparison,
        parent_p3_run_spec_path=args.p3_run_spec,
        parent_p3_comparison_path=args.p3_comparison,
    )
    comparison = build_comparison(spec)
    paths = write_bundle(spec, comparison, args.output_dir)
    print(
        json.dumps(
            {
                "gate": comparison["gates"]["overall"],
                "actual_cost_delta": comparison["gates"]["actual_cost_delta"],
                "saved_full_expert_rows": comparison["actual_saved_golden"]["evaluation"]["lane_counts"][LANE_FULL_EXPERT],
                "attack_false_cheap": comparison["adversarial_contract"]["false_cheap_count"],
                "run_spec_sha256": spec["run_spec_sha256"],
                "artifacts": {name: _stored_path(path) for name, path in paths.items()},
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
