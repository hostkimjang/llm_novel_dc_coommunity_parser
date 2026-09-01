#!/usr/bin/env python3
"""32개 frozen recovery sidecar BEFORE/OFF ↔ AFTER/AUDIT_ONLY 3회 관측을 분석한다.

공개 결정의 권한은 source-owner PublicationDecisionCommit과 각 관측 행의
publication_shadow_observation_v1 영수증뿐이다. 관측 실행의 CLI identity는
제목/품질 관측치로만 사용하며 권한 승격 근거로 사용하지 않는다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm_batch.ledger.publication_commit import validate_publication_result_commit
from src.llm_batch.ledger.decision_call_readback import read_decision_call_ledger
from src.llm_batch.measurement.publication_shadow_observation import validate_publication_shadow_observation
from src.llm_batch.measurement.semantic_review_router import (
    validate_semantic_review_router_receipt,
)
from src.llm_batch.measurement.semantic_recovery_plan import (
    validate_semantic_recovery_plan_receipt,
)

SCHEMA_VERSION = "recovery_sidecar_grouped_ab_analysis_v1"
REPEATS, INPUT_COUNT = 3, 32
DEFAULT_ROOT = ROOT / "out/regression_safe_2712_improvement_20260717/fresh_cross_family_recovery_sidecar_ab_v2"
DEFAULT_LEDGER = ROOT / "out/live_combined_row_review_20260715_143806_848671_2712_20260716/final_2712_row_adjudication_ledger.jsonl"

AttemptCoordinate = tuple[int, str]
AttemptOverrides = Mapping[AttemptCoordinate, Path]


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    values = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if not all(isinstance(value, dict) for value in values):
        raise ValueError(f"JSONL objects required: {path}")
    return values


def _pid(value: Any, label: str) -> str:
    if value is None or isinstance(value, bool) or not str(value).strip():
        raise ValueError(f"{label}: invalid post_id")
    return str(value).strip()


def _index(rows: Sequence[Mapping[str, Any]], label: str) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        post_id = _pid(row.get("post_id"), label)
        if post_id in result:
            raise ValueError(f"{label}: duplicate post_id {post_id}")
        result[post_id] = row
    return result


def _norm_title(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    import unicodedata
    normalized = "".join(character for character in unicodedata.normalize("NFKC", value).casefold() if character.isalnum())
    return normalized or None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _state(result: Mapping[str, Any], *, commit: Any = None, observation: Mapping[str, Any] | None = None) -> dict[str, Any]:
    identity = result.get("analysis_result", {}).get("identity", {})
    identity = identity if isinstance(identity, Mapping) else {}
    decision = identity.get("promotion_decision", {})
    decision = decision if isinstance(decision, Mapping) else {}
    novel = identity.get("novel_identity", {})
    novel = novel if isinstance(novel, Mapping) else {}
    publish = getattr(commit, "publish_allowed", None)
    if not isinstance(publish, bool):
        publish = decision.get("publish_allowed")
    if not isinstance(publish, bool):
        publish = bool(novel.get("official_title") and identity.get("identity_state") == "resolved_title")
    title = decision.get("official_title") or novel.get("official_title") if publish else None
    meta = result.get("run_meta", {}) if isinstance(result.get("run_meta"), Mapping) else {}
    health = identity.get("search_health") if isinstance(identity.get("search_health"), Mapping) else meta.get("search_health", {})
    health = health if isinstance(health, Mapping) else {}
    router_receipt = meta.get("semantic_review_router_receipt")
    router_state = None
    router_source = "MISSING"
    if isinstance(router_receipt, Mapping):
        normalized_router = validate_semantic_review_router_receipt(
            router_receipt,
            result=result,
            expected_publication_receipt=commit,
        )
        router_state = normalized_router["state"]
        router_source = "ATTEMPT_LOCAL_RECEIPT"
    else:
        legacy_router = next(
            (
                identity[key]
                for key in (
                    "manual_semantic_review_required",
                    "semantic_review_required",
                    "review_required",
                )
                if isinstance(identity.get(key), bool)
            ),
            None,
        )
        if isinstance(legacy_router, bool):
            router_state = "REVIEW_REQUIRED" if legacy_router else "NO_REVIEW"
            router_source = "LEGACY_IDENTITY_BOOL"
    plan_receipt = meta.get("semantic_recovery_plan_receipt")
    plan_state = "UNKNOWN"
    plan_source = "MISSING"
    plan_view: Mapping[str, Any] = {}
    if isinstance(plan_receipt, Mapping):
        normalized_plan = validate_semantic_recovery_plan_receipt(
            plan_receipt,
            result=result,
            expected_publication_receipt=commit,
        )
        plan_view = normalized_plan["plan"]
        plan_state = str(plan_view["state"])
        plan_source = "ATTEMPT_LOCAL_RECEIPT"
    if observation is not None and getattr(commit, "public_projection_sha256", None) != observation["observed_decision"]["public_projection_sha256"]:
        raise ValueError("validated observation public projection is not bound to final commit")
    return {"publish_allowed": publish, "outcome": getattr(commit, "outcome", "PUBLISH" if publish else "HOLD"), "official_title": title if isinstance(title, str) and title.strip() else None,
            "public_projection": (publish, _norm_title(title) if publish else None),
            "router": (
                "ROUTED"
                if router_state == "REVIEW_REQUIRED"
                else "NOT_ROUTED"
                if router_state in {"NO_REVIEW", "NOT_APPLICABLE"}
                else "UNKNOWN"
            ),
            "router_state": router_state or "UNKNOWN",
            "router_source": router_source,
            "plan_state": plan_state,
            "plan_source": plan_source,
            "plan_public_apply": (
                plan_receipt.get("public_apply")
                if isinstance(plan_receipt, Mapping)
                else None
            ),
            "plan_search_calls_executed": plan_view.get("search_calls_executed"),
            "plan_network_calls_executed": plan_view.get("network_calls_executed"),
            "plan_query_execution_allowed": (
                plan_view.get("query_plan", {}).get("query_execution_allowed")
                if isinstance(plan_view.get("query_plan"), Mapping)
                else None
            ),
            "plan_canonical_binding_count": (
                len(plan_view.get("canonical_bindings") or [])
                if isinstance(plan_view.get("canonical_bindings"), list)
                else None
            ),
            "search_status": health.get("status") if isinstance(health.get("status"), str) else "UNKNOWN",
            "search_queries_issued": health.get("queries_issued"), "search_degraded": health.get("degraded"), "search_unrecovered_degraded": health.get("unrecovered_degraded"),
            "cost": meta.get("decision_cost_trace") if isinstance(meta.get("decision_cost_trace"), Mapping) else {},
            "runtime_normal": identity.get("system_state") in (None, "clean") and not result.get("error")}


def _expected(row: Mapping[str, Any]) -> dict[str, Any]:
    verdict = row.get("independent_semantic_verdict", {})
    if not isinstance(verdict, Mapping):
        raise ValueError(f"ledger {_pid(row.get('post_id'), 'ledger')}: semantic verdict missing")
    action = verdict.get("dashboard_action")
    title = None
    if action == "KEEP":
        pipeline = row.get("pipeline", {}) if isinstance(row.get("pipeline"), Mapping) else {}
        title = pipeline.get("official_title") or verdict.get("pipeline_title") or verdict.get("recommended_title") or verdict.get("dashboard_title_expected")
    elif action == "CORRECT":
        title = verdict.get("recommended_title") or verdict.get("dashboard_title_expected")
    return {"review_verdict": verdict.get("review_verdict"), "dashboard_action": action,
            "recommended_title": verdict.get("recommended_title"), "expected_public_title": title,
            "expected_title_normalized": _norm_title(title)}


def _quality(expected: Mapping[str, Any], state: Mapping[str, Any]) -> dict[str, Any]:
    published, title = state["publish_allowed"], state["public_projection"][1]
    wanted = expected["expected_title_normalized"]
    exact = bool(wanted) and published and title == wanted
    action, verdict = expected["dashboard_action"], expected["review_verdict"]
    compliant = exact if action in {"KEEP", "CORRECT"} and wanted else (not published if action in {"HOLD", "REMOVE", "NOT_APPLICABLE"} else None)
    wrong_title_publish = bool(published and wanted and title != wanted)
    return {"adjudication_compliant": compliant, "unsafe_publish": bool(published and (not wanted or title != wanted)), "wrong_title_publish": wrong_title_publish,
            "correct_title_recovery": verdict == "FN_TITLE_MISSING" and exact,
            "false_positive": verdict == "FP_NONNOVEL" and published,
            "wrong_work_unrecovered": verdict == "WRONG_WORK" and compliant is False,
            "hold_integrity": action == "HOLD" and not published,
            "pass_retention": verdict == "PASS" and exact}


def _consensus(values: Sequence[Any]) -> dict[str, Any]:
    counts = Counter(values)
    value, count = sorted(counts.items(), key=lambda item: (-item[1], repr(item[0])))[0]
    return {"value": value if count >= 2 else None, "count": count, "two_of_three_majority": count >= 2,
            "unanimous": count == 3, "variance_count": len(counts) - 1,
            "fraction_label": {1: "ONE_OF_THREE", 2: "TWO_OF_THREE", 3: "THREE_OF_THREE"}[count]}


def _manifest(path: Path, arm: str, repeat: int) -> dict[str, Any]:
    value = _load_json(path)
    required = {"input_post_count": 32, "completed_count": 32, "flushed_count": 32, "pending_count": 0, "failed_count": 0,
                "requested_parallel": 16, "effective_parallel": 16, "dashboard_enabled": True, "terminal_artifacts_finalized": True,
                "publication_execution_mode": "FRESH_SHADOW_OBSERVATION_NO_PUBLIC_WRITE", "recovery_activation_status": "SKIPPED_FRESH_MEASUREMENT"}
    bad = [key for key, wanted in required.items() if value.get(key) != wanted]
    if value.get("recovery_activation_requested_mode") != ("OFF" if arm == "before" else "AUDIT_ONLY"):
        bad.append("recovery_activation_requested_mode")
    for gate, expected in (("runtime_completion_gate", "GO"), ("publication_noninterference_gate", "GO"), ("publication_shadow_observation", "GO")):
        if not isinstance(value.get(gate), Mapping) or value[gate].get("status") != expected:
            bad.append(gate)
    noninterference = value.get("publication_noninterference_gate", {})
    observation = value.get("publication_shadow_observation", {})
    if noninterference.get("public_write_allowed") is not False or noninterference.get("start_wal_sha256") != noninterference.get("current_wal_sha256"):
        bad.append("WAL_noninterference")
    if observation.get("public_apply") is not False or observation.get("observed_observation_count") != 32:
        bad.append("shadow_public_apply_or_coverage")
    if bad:
        raise ValueError(f"{arm}[{repeat}] manifest contract failure: {','.join(sorted(bad))}")
    return value


def _attempt_paths(
    root: Path,
    repeat: int,
    arm: str,
    overrides: AttemptOverrides,
) -> tuple[Path, Path, Path, bool]:
    coordinate = (repeat, arm)
    output = overrides.get(coordinate)
    overridden = output is not None
    if output is None:
        output = root / f"repeat_{repeat}" / f"{arm}.json"
    output = Path(output).resolve()
    if output.suffix != ".json":
        raise ValueError(f"{arm}[{repeat}] override output must be a JSON file")
    manifest = output.with_name(f"{output.stem}_manifest.json")
    checkpoint = output.with_name(f"{output.stem}_checkpoint.jsonl")
    return output, manifest, checkpoint, overridden


def _parse_run_id_time(run_id: Any) -> datetime:
    value = str(run_id or "")
    try:
        return datetime.strptime(value[:15], "%Y%m%d_%H%M%S")
    except ValueError as error:
        raise ValueError(f"replacement run_id timestamp is invalid: {value!r}") from error


def _replacement_qualification(
    *,
    root: Path,
    overrides: AttemptOverrides,
    replacement_policy_path: Path | None,
    attempt_sources: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not overrides:
        if replacement_policy_path is not None:
            raise ValueError("replacement policy requires at least one attempt override")
        return {
            "status": "NOT_APPLICABLE",
            "semantic_result_blind": None,
            "attempt_overrides": [],
        }
    if replacement_policy_path is None:
        raise ValueError("attempt override requires a precommitted replacement policy")
    policy_path = replacement_policy_path.resolve()
    policy = _load_json(policy_path)
    if policy.get("schema_version") != "measurement_incomplete_arm_replacement_policy_v1":
        raise ValueError("replacement policy schema mismatch")
    if Path(str(policy.get("source_series_root") or "")).resolve() != root.resolve():
        raise ValueError("replacement policy source root mismatch")
    selection = policy.get("selection_policy")
    if not isinstance(selection, Mapping):
        raise ValueError("replacement policy selection block missing")
    required_selection = {
        "semantic_result_blind": True,
        "accept_first_terminal_attempt_matching_all_gates": True,
    }
    for key, expected in required_selection.items():
        if selection.get(key) is not expected:
            raise ValueError(f"replacement policy is not measurement-blind: {key}")
    overwrite_allowed = selection.get(
        "original_or_prior_attempt_overwrite_allowed",
        selection.get("original_artifact_overwrite_allowed"),
    )
    if overwrite_allowed is not False:
        raise ValueError("replacement policy does not forbid original overwrite")

    policy_created = datetime.fromisoformat(str(policy.get("created_at_kst") or ""))
    policy_created_naive = policy_created.replace(tzinfo=None)
    source_by_coordinate = {
        (int(item["repeat_index"]), str(item["arm"])): item
        for item in attempt_sources
    }
    qualified: list[dict[str, Any]] = []
    for coordinate, output in sorted(overrides.items()):
        repeat, arm = coordinate
        if repeat not in range(1, REPEATS + 1) or arm not in {"before", "after"}:
            raise ValueError(f"invalid attempt override coordinate: {coordinate}")
        source = source_by_coordinate.get(coordinate)
        if not isinstance(source, Mapping) or source.get("overridden") is not True:
            raise ValueError(f"attempt override was not selected: {coordinate}")
        if _parse_run_id_time(source.get("run_id")) <= policy_created_naive:
            raise ValueError("replacement policy was not recorded before replacement run")
        original_manifest_path = root / f"repeat_{repeat}" / f"{arm}_manifest.json"
        original_manifest = _load_json(original_manifest_path)
        original_gate = original_manifest.get("measurement_gate")
        original_gate = original_gate if isinstance(original_gate, Mapping) else {}
        if original_gate.get("status") != "NO_GO":
            raise ValueError("replacement target original measurement gate is not NO_GO")
        replacement_manifest = _load_json(Path(str(source["manifest"])))
        replacement_gate = replacement_manifest.get("measurement_gate")
        replacement_gate = replacement_gate if isinstance(replacement_gate, Mapping) else {}
        if replacement_gate.get("status") != "GO":
            raise ValueError("replacement measurement gate is not GO")
        qualified.append(
            {
                "repeat_index": repeat,
                "arm": arm.upper(),
                "original": {
                    "run_id": original_manifest.get("run_id"),
                    "manifest": str(original_manifest_path.resolve()),
                    "measurement_gate": original_gate.get("status"),
                    "measurement_reason_codes": original_gate.get("reason_codes", []),
                },
                "replacement": {
                    "run_id": replacement_manifest.get("run_id"),
                    "output": str(Path(output).resolve()),
                    "manifest": str(Path(str(source["manifest"])).resolve()),
                    "measurement_gate": replacement_gate.get("status"),
                },
            }
        )
    return {
        "status": "GO_MEASUREMENT_BLIND_REPLACEMENT_QUALIFIED",
        "semantic_result_blind": True,
        "policy": str(policy_path),
        "policy_sha256": _sha256_file(policy_path),
        "attempt_overrides": qualified,
    }


def _source(root: Path) -> tuple[list[str], dict[str, Mapping[str, Any]], dict[str, Any], dict[str, dict[str, Any]]]:
    manifest = _load_json(root / "source_owner_manifest.json")
    if manifest.get("runtime_completion_gate", {}).get("status") != "GO":
        raise ValueError("source owner runtime gate is not GO")
    rows = _load_jsonl(root / "source_owner_checkpoint.jsonl")
    if len(rows) != INPUT_COUNT:
        raise ValueError("source owner is partial or does not contain 32 rows")
    index = _index(rows, "source owner")
    positions: dict[str, dict[str, Any]] = {}
    for row in rows:
        post_id, result = _pid(row.get("post_id"), "source owner"), row.get("result")
        if not isinstance(result, Mapping): raise ValueError("source owner result missing")
        receipt = validate_publication_result_commit(result, row.get("publication_commit"), expected_input_index=row.get("global_idx"), expected_post_id=row.get("post_id"))
        positions[post_id] = {"decision_id": receipt.decision_id, "scope_id": receipt.publication_scope_id, "input_index": receipt.input_index, "commit": receipt}
    return list(index), index, manifest, positions


def _checkpoint(path: Path, *, arm: str, repeat: int, source_ids: set[str], authority: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    rows = _load_jsonl(path)
    if len(rows) != INPUT_COUNT: raise ValueError(f"{arm}[{repeat}] partial checkpoint")
    index = _index(rows, f"{arm}[{repeat}]")
    if set(index) != source_ids: raise ValueError(f"{arm}[{repeat}] post_id exact set mismatch")
    validated: dict[str, dict[str, Any]] = {}
    for post_id, row in index.items():
        result = row.get("result")
        if not isinstance(result, Mapping): raise ValueError(f"{arm}[{repeat}] {post_id}: result missing")
        observed = validate_publication_result_commit(result, row.get("publication_commit"), expected_input_index=row.get("global_idx"), expected_post_id=row.get("post_id"))
        meta = result.get("run_meta", {}) if isinstance(result.get("run_meta"), Mapping) else {}
        receipt = validate_publication_shadow_observation(meta.get("publication_shadow_observation"))
        if str(receipt["post_id"]) != post_id or receipt["input_index"] != row.get("global_idx"):
            raise ValueError(f"{arm}[{repeat}] {post_id}: shadow coordinate mismatch")
        if (receipt["publication_scope_id"] != authority[post_id]["scope_id"] or receipt["input_index"] != authority[post_id]["input_index"]
                or receipt["observed_decision"]["decision_id"] != observed.decision_id
                or receipt["observed_decision"]["outcome"] != observed.outcome
                or receipt["observed_decision"]["publish_allowed"] is not observed.publish_allowed
                or receipt["authoritative_decision"]["decision_id"] != authority[post_id]["decision_id"]):
            raise ValueError(f"{arm}[{repeat}] {post_id}: shadow authority binding mismatch")
        validated[post_id] = {"row": row, "result": result, "commit": observed, "observation": receipt}
    return validated


_HIGH_RISK = {"FP_NONNOVEL", "WRONG_WORK", "FN_TITLE_MISSING", "DASHBOARD_TITLE_MISMATCH", "EVIDENCE_CONFLICT", "EVIDENCE_INSUFFICIENT", "MULTIWORK_HOLD_CORRECT"}


def _measurement_status(manifest: Mapping[str, Any]) -> tuple[str, list[str]]:
    gate = manifest.get("measurement_gate", {})
    gate = gate if isinstance(gate, Mapping) else {}
    ledger = manifest.get("decision_call_ledger_summary", {})
    ledger = ledger if isinstance(ledger, Mapping) else {}
    reasons = [
        str(value)
        for source in (gate.get("reason_codes", []), ledger.get("reason_codes", []))
        if isinstance(source, list)
        for value in source
    ]
    missing = []
    if not gate:
        missing.append("MEASUREMENT_GATE_MISSING")
    if not ledger:
        missing.append("DECISION_CALL_LEDGER_SUMMARY_MISSING")
    gate_go = gate.get("status") == "GO"
    ledger_go = ledger.get("ledger_status") in {"GO", "COMPLETE"}
    kpi_go = ledger.get("actual_kpi_status") in {"GO", "MEASURED", "ESTIMABLE"}
    return (
        "GO" if gate_go and ledger_go and kpi_go and not missing else "NO_GO",
        sorted(set(reasons + missing)),
    )


def _measurement_status_with_readback(
    manifest: Mapping[str, Any],
    readback: Mapping[str, Any] | None,
) -> tuple[str, list[str]]:
    if readback is None:
        return _measurement_status(manifest)
    reasons = [str(value) for value in readback.get("reason_codes", [])]
    exact = (
        readback.get("gate_status") == "GO"
        and readback.get("aggregate_status") == "EXACT"
        and readback.get("actual_kpi_status") == "EXACT"
        and readback.get("measurement_completion_status") == "EXACT"
        and readback.get("usage", {}).get("aggregate_exact") is True
    )
    return ("GO" if exact else "NO_GO", sorted(set(reasons)))


def _independent_call_readback(
    *,
    output_path: Path,
    checkpoint_path: Path,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    ledger_path = output_path.with_name(f"{output_path.stem}_decision_call_ledger")
    checkpoint_rows = _load_jsonl(checkpoint_path)
    recorded_paths: set[str] = set()
    for row in checkpoint_rows:
        result = row.get("result")
        meta = result.get("run_meta") if isinstance(result, Mapping) else None
        ledger_ref = meta.get("decision_call_ledger") if isinstance(meta, Mapping) else None
        recorded = ledger_ref.get("path") if isinstance(ledger_ref, Mapping) else None
        if not isinstance(recorded, str) or not recorded.strip():
            raise ValueError("checkpoint decision-call ledger path is missing")
        recorded_paths.add(str(Path(recorded).resolve()))
    if recorded_paths != {str(ledger_path.resolve())}:
        raise ValueError("checkpoint decision-call ledger path differs from output sibling")

    report = read_decision_call_ledger(ledger_path)
    coverage = report.get("coverage")
    coverage = coverage if isinstance(coverage, Mapping) else {}
    expected_run_id = str(manifest.get("run_id") or "")
    if (
        report.get("gate_status") != "GO"
        or report.get("aggregate_status") != "EXACT"
        or report.get("actual_kpi_status") != "EXACT"
        or report.get("measurement_completion_status") != "EXACT"
        or report.get("usage", {}).get("aggregate_exact") is not True
        or coverage.get("attempt_run_ids") != [expected_run_id]
        or coverage.get("attempt_run_count") != 1
        or coverage.get("observed_row_count") != INPUT_COUNT
        or coverage.get("sealed_row_count") != INPUT_COUNT
        or coverage.get("linked_row_count") != INPUT_COUNT
        or coverage.get("unlinked_rows") != []
        or coverage.get("ambiguous_rows") != []
        or report.get("attempts", {}).get("open") != 0
    ):
        raise ValueError(f"independent call readback is not exact: {ledger_path}")
    scope = report.get("scope")
    scope = scope if isinstance(scope, Mapping) else {}
    if (
        scope.get("publication_scope_id") != manifest.get("publication_scope_id")
        or scope.get("scope_sha256") != manifest.get("decision_call_ledger_scope_sha256")
        or scope.get("expected_row_count") != INPUT_COUNT
    ):
        raise ValueError("independent call readback scope differs from manifest")
    bindings = scope.get("measurement_bindings")
    measurement = manifest.get("decision_call_measurement")
    if not isinstance(bindings, Mapping) or not isinstance(measurement, Mapping):
        raise ValueError("independent call readback measurement binding is missing")
    expected_bindings = {
        "run_spec_sha256": measurement.get("run_spec_sha256"),
        "pair_id": measurement.get("pair_id"),
        "arm": measurement.get("arm"),
        "fresh_execution_mode": True,
    }
    if dict(bindings) != expected_bindings:
        raise ValueError("independent call readback binding differs from manifest")
    actual = report.get("actual_metrics")
    actual = actual if isinstance(actual, Mapping) else {}
    derived = manifest.get("decision_call_ledger_summary", {}).get("derived_observation")
    derived = derived if isinstance(derived, Mapping) else {}
    for field in ("expert_calls", "prompt_tokens", "completion_tokens", "total_tokens"):
        if actual.get(field) != derived.get(field):
            raise ValueError(f"independent call readback metric differs from manifest: {field}")
    return report


def _router_metrics(rows: Sequence[Mapping[str, Any]], arm: str) -> dict[str, Any]:
    states = [state for row in rows for state in row[arm]["_states"]]
    unknown = sum(state["router"] == "UNKNOWN" for state in states)
    state_distribution = Counter(state["router_state"] for state in states)
    source_distribution = Counter(state["router_source"] for state in states)
    high = [state for row in rows if row["frozen_review"]["review_verdict"] in _HIGH_RISK for state in row[arm]["_states"]]
    controls = [
        state
        for row in rows
        if row["frozen_review"]["review_verdict"]
        in {"PASS", "NOISE_CORRECT", "CONTEXT_ONLY_CORRECT"}
        for state in row[arm]["_states"]
    ]
    def rate(values: list[Mapping[str, Any]], desired: str) -> dict[str, Any]:
        known = [value for value in values if value["router"] != "UNKNOWN"]
        count = sum(value["router"] == desired for value in known)
        return {"count": count, "known_denominator": len(known), "unknown": len(values) - len(known), "rate": count / len(known) if known else None}
    recall, false_review = rate(high, "ROUTED"), rate(controls, "ROUTED")
    return {"unknown_rows": unknown,
            "state_distribution": dict(sorted(state_distribution.items())),
            "source_distribution": dict(sorted(source_distribution.items())),
            "receipt_coverage": sum(state["router_source"] == "ATTEMPT_LOCAL_RECEIPT" for state in states),
            "high_risk_recall": recall, "normal_control_false_review": false_review,
            "green": unknown == 0 and recall["known_denominator"] > 0 and recall["rate"] == 1.0}


def _search_metrics(rows: Sequence[Mapping[str, Any]], arm: str) -> dict[str, Any]:
    states = [state for row in rows for state in row[arm]["_states"]]
    statuses = Counter(state["search_status"] for state in states)
    numeric = lambda key: [state[key] for state in states if isinstance(state[key], (int, float)) and not isinstance(state[key], bool)]
    allowed = {"ok", "healthy", "go", "search_healthy", "not_applicable"}
    return {"status_distribution": dict(sorted(statuses.items())), "unknown_rows": statuses.get("UNKNOWN", 0),
            "not_applicable_rows": statuses.get("NOT_APPLICABLE", 0),
            "queries_issued": {"value": sum(numeric("search_queries_issued")), "known_rows": len(numeric("search_queries_issued"))},
            "degraded": {"value": sum(numeric("search_degraded")), "known_rows": len(numeric("search_degraded"))},
            "unrecovered_degraded": {"value": sum(numeric("search_unrecovered_degraded")), "known_rows": len(numeric("search_unrecovered_degraded"))},
            "green": all(isinstance(state["search_status"], str) and state["search_status"].casefold() in allowed for state in states)}


def _plan_metrics(rows: Sequence[Mapping[str, Any]], arm: str) -> dict[str, Any]:
    states = [state for row in rows for state in row[arm]["_states"]]
    distribution = Counter(state["plan_state"] for state in states)
    receipt_coverage = sum(
        state["plan_source"] == "ATTEMPT_LOCAL_RECEIPT" for state in states
    )
    public_apply_true = sum(state["plan_public_apply"] is True for state in states)
    search_calls = sum(
        int(state["plan_search_calls_executed"] or 0) for state in states
    )
    network_calls = sum(
        int(state["plan_network_calls_executed"] or 0) for state in states
    )
    query_allowed = sum(
        state["plan_query_execution_allowed"] is True for state in states
    )
    canonical_bindings = sum(
        int(state["plan_canonical_binding_count"] or 0) for state in states
    )
    unknown = distribution.get("UNKNOWN", 0)
    return {
        "state_distribution": dict(sorted(distribution.items())),
        "receipt_coverage": receipt_coverage,
        "missing_receipts": len(states) - receipt_coverage,
        "unknown_rows": unknown,
        "public_apply_true_rows": public_apply_true,
        "search_calls_executed": search_calls,
        "network_calls_executed": network_calls,
        "query_execution_allowed_rows": query_allowed,
        "canonical_binding_count": canonical_bindings,
        "green": (
            receipt_coverage == len(states)
            and unknown == 0
            and public_apply_true == 0
            and search_calls == 0
            and network_calls == 0
        ),
    }


def _run_wall_time_observation(manifest: Mapping[str, Any]) -> dict[str, Any]:
    for key in ("total_time_seconds", "elapsed_seconds", "duration_seconds"):
        value = manifest.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return {"seconds": float(value), "source": f"manifest.{key}"}
    run_id = manifest.get("run_id")
    if isinstance(run_id, str) and run_id.strip():
        log_path = ROOT / "logs" / f"expert_run_{run_id.strip()}.log"
        if log_path.is_file():
            matches = re.findall(
                r"Total Time:\s*([0-9]+(?:\.[0-9]+)?)s",
                log_path.read_text(encoding="utf-8", errors="replace"),
            )
            if matches:
                return {"seconds": float(matches[-1]), "source": str(log_path)}
    return {"seconds": None, "source": "NOT_ESTIMABLE"}


def build_report(
    root: Path,
    ledger_path: Path,
    *,
    attempt_overrides: AttemptOverrides | None = None,
    replacement_policy_path: Path | None = None,
    independent_call_readback: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    overrides = dict(attempt_overrides or {})
    order, source, source_manifest, authority = _source(root)
    if len(order) != INPUT_COUNT or len(set(order)) != INPUT_COUNT: raise ValueError("source exact 32 post_id requirement failed")
    ledger = _index(_load_jsonl(ledger_path), "frozen ledger")
    if not set(order).issubset(ledger): raise ValueError("frozen ledger missing source post_id")
    manifests, runs = {"before": [], "after": []}, {"before": [], "after": []}
    call_readbacks: dict[str, list[dict[str, Any]]] = {"before": [], "after": []}
    attempt_sources: list[dict[str, Any]] = []
    for repeat in range(1, 4):
        for arm in ("before", "after"):
            output_path, manifest_path, checkpoint_path, overridden = _attempt_paths(
                root, repeat, arm, overrides
            )
            manifest = _manifest(manifest_path, arm, repeat)
            manifests[arm].append(manifest)
            runs[arm].append(_checkpoint(checkpoint_path, arm=arm, repeat=repeat, source_ids=set(order), authority=authority))
            independent_report = (
                _independent_call_readback(
                    output_path=output_path,
                    checkpoint_path=checkpoint_path,
                    manifest=manifest,
                )
                if independent_call_readback
                else None
            )
            if independent_report is not None:
                call_readbacks[arm].append(independent_report)
            attempt_sources.append(
                {
                    "repeat_index": repeat,
                    "arm": arm,
                    "run_id": manifest.get("run_id"),
                    "output": str(output_path),
                    "manifest": str(manifest_path),
                    "checkpoint": str(checkpoint_path),
                    "overridden": overridden,
                    "runtime_gate": manifest["runtime_completion_gate"]["status"],
                    "measurement_gate": manifest["measurement_gate"]["status"],
                    "noninterference_gate": manifest["publication_noninterference_gate"]["status"],
                    "independent_call_readback": (
                        {
                            "gate_status": independent_report["gate_status"],
                            "actual_kpi_status": independent_report["actual_kpi_status"],
                            "ledger_path": independent_report["ledger_path"],
                            "frame_set_sha256": independent_report["frame_set_sha256"],
                            "report_sha256": independent_report["report_sha256"],
                            "actual_metrics": independent_report["actual_metrics"],
                        }
                        if independent_report is not None
                        else None
                    ),
                }
            )
    attempt_selection = _replacement_qualification(
        root=root,
        overrides=overrides,
        replacement_policy_path=replacement_policy_path,
        attempt_sources=attempt_sources,
    )
    wal_hashes = {m["publication_noninterference_gate"]["start_wal_sha256"] for arm in manifests.values() for m in arm}
    if len(wal_hashes) != 1: raise ValueError("WAL noninterference hash differs across observation runs")
    wal_path_value = source_manifest.get("publication_commit_journal")
    if not isinstance(wal_path_value, str) or not wal_path_value.strip():
        raise ValueError("source owner publication WAL path missing")
    wal_path = Path(wal_path_value)
    if not wal_path.is_absolute():
        wal_path = ROOT / wal_path
    if not wal_path.is_file():
        raise ValueError(f"source owner publication WAL missing: {wal_path}")
    actual_wal_sha256 = _sha256_file(wal_path)
    if {actual_wal_sha256} != wal_hashes:
        raise ValueError("actual publication WAL SHA differs from observation anchors")
    actual_wal_event_count = sum(
        bool(line.strip())
        for line in wal_path.read_text(encoding="utf-8-sig").splitlines()
    )
    anchored_event_counts = {
        int(gate[key])
        for arm_manifests in manifests.values()
        for manifest in arm_manifests
        for gate in [manifest["publication_noninterference_gate"]]
        for key in ("start_wal_event_count", "current_wal_event_count")
        if isinstance(gate.get(key), int) and not isinstance(gate.get(key), bool)
    }
    if anchored_event_counts != {actual_wal_event_count}:
        raise ValueError("actual publication WAL event count differs from observation anchors")
    rows = []
    for post_id in order:
        expected = _expected(ledger[post_id])
        source_state = _state(source[post_id]["result"], commit=authority[post_id]["commit"])
        source_quality = _quality(expected, source_state)
        arms: dict[str, Any] = {}
        for arm in ("before", "after"):
            states = [_state(run[post_id]["result"], commit=run[post_id]["commit"], observation=run[post_id]["observation"]) for run in runs[arm]]
            quality = [_quality(expected, state) for state in states]
            projections = [state["public_projection"] for state in states]
            arms[arm] = {"observed_projections": [{"publish_allowed": s["publish_allowed"], "official_title": s["official_title"], "projection": s["public_projection"], "outcome": s["outcome"]} for s in states],
                         "modal_projection": _consensus(projections), "exact_adjudication_compliant_count": sum(q["adjudication_compliant"] is True for q in quality),
                         "adjudication_consensus": _consensus([q["adjudication_compliant"] for q in quality]),
                         "quality": {key: {"any_run": any(q[key] is True for q in quality), "exact_run_count": sum(q[key] is True for q in quality), "majority": _consensus([q[key] for q in quality])["value"]} for key in quality[0]},
                         "source_projection_drift_count": sum(s["public_projection"] != source_state["public_projection"] for s in states)}
            arms[arm]["_states"] = states
        b, a = arms["before"], arms["after"]
        rows.append({"schema_version": SCHEMA_VERSION, "post_id": post_id, "frozen_review": expected,
                     "authoritative_source_projection": {"publish_allowed": source_state["publish_allowed"], "outcome": source_state["outcome"], "official_title": source_state["official_title"], "publication_decision_id": authority[post_id]["decision_id"]}, "authoritative_source_adjudication": source_quality,
                     **arms, "transition": {"cross_arm_normal_to_abnormal_descriptive": b["adjudication_consensus"]["value"] is True and a["adjudication_consensus"]["value"] is False,
                                                "source_recurrent_regression": {arm: source_quality["adjudication_compliant"] is True and arms[arm]["adjudication_consensus"]["value"] is False for arm in ("before", "after")},
                                                "source_new_unsafe_recurrent": {arm: not source_quality["unsafe_publish"] and arms[arm]["quality"]["unsafe_publish"]["majority"] is True for arm in ("before", "after")},
                                                "source_new_wrong_title_recurrent": {arm: not source_quality["wrong_title_publish"] and arms[arm]["quality"]["wrong_title_publish"]["majority"] is True for arm in ("before", "after")}}})
    measurement = [
        _measurement_status_with_readback(
            manifest,
            call_readbacks[arm][index] if independent_call_readback else None,
        )
        for arm, arm_manifests in manifests.items()
        for index, manifest in enumerate(arm_manifests)
    ]
    measurement_go = all(status == "GO" for status, _ in measurement)
    def eligible(row: Mapping[str, Any], key: str) -> bool:
        verdict = row["frozen_review"]["review_verdict"]
        action = row["frozen_review"]["dashboard_action"]
        if key == "correct_title_recovery":
            return verdict == "FN_TITLE_MISSING"
        if key == "false_positive":
            return verdict == "FP_NONNOVEL"
        if key == "wrong_work_unrecovered":
            return verdict == "WRONG_WORK"
        if key == "hold_integrity":
            return action == "HOLD"
        if key == "pass_retention":
            return verdict == "PASS"
        return True
    def quality_metrics(arm: str, key: str) -> dict[str, Any]:
        selected = [row for row in rows if eligible(row, key)]
        return {
            "eligible_posts": len(selected),
            "any_run_posts": sum(row[arm]["quality"][key]["any_run"] for row in selected),
            "exact_run_total": sum(row[arm]["quality"][key]["exact_run_count"] for row in selected),
            "majority_posts": sum(row[arm]["quality"][key]["majority"] is True for row in selected),
            "majority_true_post_ids": [
                row["post_id"]
                for row in selected
                if row[arm]["quality"][key]["majority"] is True
            ],
            "any_run_post_ids": [
                row["post_id"]
                for row in selected
                if row[arm]["quality"][key]["any_run"]
            ],
        }
    routers = {arm: _router_metrics(rows, arm) for arm in ("before", "after")}
    searches = {arm: _search_metrics(rows, arm) for arm in ("before", "after")}
    plans = {arm: _plan_metrics(rows, arm) for arm in ("before", "after")}
    regressions = {arm: sum(row["transition"]["source_recurrent_regression"][arm] for row in rows) for arm in ("before", "after")}
    new_unsafe = {arm: sum(row["transition"]["source_new_unsafe_recurrent"][arm] for row in rows) for arm in ("before", "after")}
    new_wrong = {arm: sum(row["transition"]["source_new_wrong_title_recurrent"][arm] for row in rows) for arm in ("before", "after")}
    quality_summary = {key: {arm: quality_metrics(arm, key) for arm in ("before", "after")} for key in ("unsafe_publish", "wrong_title_publish", "correct_title_recovery", "false_positive", "wrong_work_unrecovered", "hold_integrity", "pass_retention")}
    majority_compliance = {
        arm: {
            "compliant_posts": sum(row[arm]["adjudication_consensus"]["value"] is True for row in rows),
            "noncompliant_posts": sum(row[arm]["adjudication_consensus"]["value"] is False for row in rows),
            "no_consensus_posts": sum(row[arm]["adjudication_consensus"]["value"] is None for row in rows),
            "noncompliant_post_ids": [row["post_id"] for row in rows if row[arm]["adjudication_consensus"]["value"] is False],
        }
        for arm in ("before", "after")
    }
    recovery_effect_missing = quality_summary["correct_title_recovery"]["after"]["majority_posts"] == 0
    pass_retention_incomplete = quality_summary["pass_retention"]["after"]["majority_posts"] < quality_summary["pass_retention"]["after"]["eligible_posts"]
    wrong_work_unresolved = quality_summary["wrong_work_unrecovered"]["after"]["majority_posts"] > 0
    semantic_gate = "NO_GO" if any(regressions.values()) or any(new_unsafe.values()) or any(new_wrong.values()) or recovery_effect_missing or pass_retention_incomplete or wrong_work_unresolved or not measurement_go or not all(routers[a]["green"] and searches[a]["green"] and plans[a]["green"] for a in ("before", "after")) else "GO"
    cost_fields = ("expert_calls", "search_calls", "prompt_tokens", "completion_tokens", "total_tokens")
    observed_states = {arm: [state for row in rows for state in row[arm]["_states"]] for arm in ("before", "after")}
    observed_partial_by_arm = {
        arm: {
            field: sum(
                state["cost"].get(field, 0)
                for state in observed_states[arm]
                if isinstance(state["cost"].get(field), (int, float))
            )
            for field in cost_fields
        }
        for arm in ("before", "after")
    }
    observed_partial = {
        field: sum(observed_partial_by_arm[arm][field] for arm in ("before", "after"))
        for field in cost_fields
    }
    # Call intent counts remain useful structural observations even when usage
    # is unavailable/estimated.  Prefer the immutable ledger readback aggregate
    # over row-level decision_cost_trace, which intentionally omits this field.
    ledger_call_counts_by_arm: dict[str, list[int]] = {"before": [], "after": []}
    for arm, arm_manifests in manifests.items():
        for manifest in arm_manifests:
            summary = manifest.get("decision_call_ledger_summary")
            summary = summary if isinstance(summary, Mapping) else {}
            derived = summary.get("derived_observation")
            derived = derived if isinstance(derived, Mapping) else {}
            value = derived.get("expert_calls")
            if isinstance(value, int) and not isinstance(value, bool):
                ledger_call_counts_by_arm[arm].append(value)
    if all(len(values) == REPEATS for values in ledger_call_counts_by_arm.values()):
        for arm, values in ledger_call_counts_by_arm.items():
            observed_partial_by_arm[arm]["expert_calls"] = sum(values)
        observed_partial["expert_calls"] = sum(sum(values) for values in ledger_call_counts_by_arm.values())
    else:
        observed_partial_by_arm["before"]["expert_calls"] = None
        observed_partial_by_arm["after"]["expert_calls"] = None
        observed_partial["expert_calls"] = None
    if measurement_go and independent_call_readback:
        exact_by_arm = {
            arm: {
                field: sum(report["actual_metrics"][field] for report in call_readbacks[arm])
                for field in ("expert_calls", "prompt_tokens", "completion_tokens", "total_tokens")
            }
            for arm in ("before", "after")
        }
        for arm in ("before", "after"):
            exact_by_arm[arm]["search_calls"] = observed_partial_by_arm[arm]["search_calls"]
        costs = {
            field: {
                "status": "MEASURED",
                "value": sum(exact_by_arm[arm][field] for arm in ("before", "after")),
                "by_arm": {arm: exact_by_arm[arm][field] for arm in ("before", "after")},
                "source": (
                    "IMMUTABLE_DECISION_CALL_LEDGER_INDEPENDENT_READBACK"
                    if field != "search_calls"
                    else "ROW_DECISION_COST_TRACE"
                ),
            }
            for field in cost_fields
        }
    elif measurement_go:
        costs = {field: {"status": "MEASURED", "value": observed_partial[field], "by_arm": {arm: observed_partial_by_arm[arm][field] for arm in ("before", "after")}} for field in cost_fields}
    else:
        costs = {field: {"status": "NOT_ESTIMABLE", "value": None, "reason": "DECISION_CALL_MEASUREMENT_NOT_GO", "observational_partial": observed_partial[field], "observational_partial_by_arm": {arm: observed_partial_by_arm[arm][field] for arm in ("before", "after")}} for field in cost_fields}
    wall = {}
    for arm in manifests:
        observations = [_run_wall_time_observation(manifest) for manifest in manifests[arm]]
        known_seconds = [
            item["seconds"]
            for item in observations
            if isinstance(item["seconds"], (int, float))
        ]
        wall[arm] = {
            "row_wall_ms_observational_partial": sum(
                state["cost"].get("wall_ms", 0)
                for state in observed_states[arm]
                if isinstance(state["cost"].get("wall_ms"), (int, float))
            ),
            "run_total_seconds": sum(known_seconds) if known_seconds else None,
            "known_runs": len(known_seconds),
            "unknown_runs": len(observations) - len(known_seconds),
            "runs": observations,
        }
    source_bindings = {key: source_manifest.get(key) for key in ("publication_scope_id", "publication_input_snapshot_sha256", "llm_model", "model") if source_manifest.get(key) is not None}
    comparison_fields = ("publication_scope_id", "publication_input_snapshot_sha256", "llm_model", "model")
    comparability = {field: {str(manifest.get(field)) for arm in manifests.values() for manifest in arm} for field in comparison_fields}
    if any(len(values) > 1 for values in comparability.values() if values != {"None"}):
        raise ValueError("source/input/model comparability differs across observation runs")
    for field, source_value in source_bindings.items():
        observed_values = comparability[field]
        if observed_values != {"None"} and observed_values != {str(source_value)}:
            raise ValueError(f"source/input/model comparability differs from source: {field}")
    independent_readback_summary = {
        "status": "GO" if independent_call_readback and measurement_go else "NOT_RUN" if not independent_call_readback else "NO_GO",
        "arm_report_count": {arm: len(call_readbacks[arm]) for arm in ("before", "after")},
        "actual_metrics": {
            arm: {
                field: sum(report["actual_metrics"][field] for report in call_readbacks[arm])
                for field in (
                    "expert_calls", "text_calls", "vlm_calls", "retry_count",
                    "prompt_tokens", "completion_tokens", "total_tokens",
                    "physical_call_wall_ms_sum",
                )
            }
            for arm in ("before", "after")
        } if independent_call_readback else None,
    }
    summary = {"schema_version": SCHEMA_VERSION, "pairing": {"status": "EXACT", "row_count": 32, "repeat_count": 3, "post_id_order_sha256": hashlib.sha256(json.dumps(order, separators=(",", ":")).encode()).hexdigest()},
               "attempt_selection": attempt_selection,
               "attempt_sources": attempt_sources,
               "independent_call_readback": independent_readback_summary,
               "comparability": {"source_bindings": source_bindings, "observation_values": {key: sorted(value) for key, value in comparability.items()}, "wal": {"path": str(wal_path), "manifest_anchor_sha256": sorted(wal_hashes), "actual_sha256": actual_wal_sha256, "actual_event_count": actual_wal_event_count}, "status": "GO"},
               "authority": {"source_owner_manifest": str(root / "source_owner_manifest.json"), "receipt": "validated publication_shadow_observation_v1 observed_decision", "source_commit": "validated PublicationDecisionCommit outcome/publish_allowed", "public_apply": False, "wal_noninterference": "GO"},
               "causal_warning": "AFTER is SKIPPED_FRESH_MEASUREMENT; fresh stochastic observation does not establish a sidecar causal effect.",
               "metrics": {"quality": quality_summary, "adjudication_majority_compliance": majority_compliance, "source_relative_recurrent": {"source_compliant_to_noncompliant": regressions, "new_unsafe_publish": new_unsafe, "new_wrong_title_publish": new_wrong}, "cross_arm_descriptive_normal_to_abnormal": sum(row["transition"]["cross_arm_normal_to_abnormal_descriptive"] for row in rows), "source_projection_drift_frequency": {arm: sum(r[arm]["source_projection_drift_count"] for r in rows) for arm in ("before", "after")}, "repeats": {arm: {"unanimous_posts": sum(r[arm]["modal_projection"]["unanimous"] for r in rows), "variable_posts": sum(not r[arm]["modal_projection"]["unanimous"] for r in rows), "distinct_projection_excess": sum(r[arm]["modal_projection"]["variance_count"] for r in rows)} for arm in ("before", "after")}, "router": routers, "search": searches, "recovery_plan": plans, "wall_time_observation": wall, "decision_calls_tokens_cost": costs},
               "measurement_gate": "GO" if measurement_go else "NO_GO", "semantic_auto_activation_gate": semantic_gate,
               "measurement_reason_codes": sorted({reason for _, reasons in measurement for reason in reasons}),
               "gate_reasons": [reason for reason, active in (("SOURCE_RELATIVE_RECURRENT_REGRESSION", any(regressions.values())), ("SOURCE_RELATIVE_NEW_UNSAFE_PUBLISH", any(new_unsafe.values())), ("SOURCE_RELATIVE_NEW_WRONG_TITLE", any(new_wrong.values())), ("RECOVERY_EFFECT_NOT_DEMONSTRATED", recovery_effect_missing), ("PASS_RETENTION_INCOMPLETE", pass_retention_incomplete), ("WRONG_WORK_CORRECTION_UNRESOLVED", wrong_work_unresolved), ("MEASUREMENT_NOT_GREEN", not measurement_go), ("SEARCH_OR_ROUTER_NOT_GREEN", not all(routers[a]["green"] and searches[a]["green"] for a in ("before", "after"))), ("RECOVERY_PLAN_NOT_GREEN", not all(plans[a]["green"] for a in ("before", "after")))) if active]}
    for row in rows:
        for arm in ("before", "after"):
            row[arm].pop("_states", None)
    return rows, summary


def _atomic(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(payload, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally: temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT); parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--attempt-override",
        action="append",
        default=[],
        metavar="REPEAT:ARM:OUTPUT_JSON",
        help="측정 실패 arm을 원본 보존 replacement output으로 명시적으로 대체",
    )
    parser.add_argument("--replacement-policy", type=Path, default=None)
    parser.add_argument(
        "--independent-call-readback",
        action="store_true",
        help="선택된 6개 immutable call ledger를 독립 재판독해 actual KPI를 결속",
    )
    args = parser.parse_args(); output = args.output_dir or args.root / "grouped_analysis"
    try:
        overrides: dict[AttemptCoordinate, Path] = {}
        for raw in args.attempt_override:
            parts = str(raw).split(":", 2)
            if len(parts) != 3:
                raise ValueError(f"invalid attempt override: {raw!r}")
            repeat_text, arm, output_text = parts
            coordinate = (int(repeat_text), arm.casefold())
            if coordinate in overrides:
                raise ValueError(f"duplicate attempt override: {coordinate}")
            overrides[coordinate] = Path(output_text)
        rows, summary = build_report(
            args.root,
            args.ledger,
            attempt_overrides=overrides,
            replacement_policy_path=args.replacement_policy,
            independent_call_readback=args.independent_call_readback,
        )
        _atomic(output / "transitions.jsonl", "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows))
        _atomic(output / "report.json", json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"gate": "HARD_FAILURE", "error": str(error)}, ensure_ascii=False), file=sys.stderr); return 2
    print(json.dumps({"gate": summary["semantic_auto_activation_gate"], "rows": len(rows)}, ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
