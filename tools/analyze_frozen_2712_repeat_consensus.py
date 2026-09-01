#!/usr/bin/env python3
"""동일 frozen 입력의 3회 BEFORE/AFTER 실행을 post_id exact consensus로 분석한다.

결정적 계약(입력 집합ㆍmanifest comparability)은 즉시 실패한다. 의미 결과는
확률적이므로 3회 다수결만 시스템 변화로 집계하며, 단발 흔들림도 행별로 보존한다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

try:  # package import for tests and direct-script import for the documented CLI
    from tools.compare_frozen_2712_pair import (
        _expected, _index, _load_json_array, _load_jsonl, _quality, _runtime_state,
    )
except ModuleNotFoundError:  # pragma: no cover - exercised by direct CLI execution
    from compare_frozen_2712_pair import (
        _expected, _index, _load_json_array, _load_jsonl, _quality, _runtime_state,
    )


SCHEMA_VERSION = "frozen_2712_repeat_consensus_v1"
REPEAT_COUNT = 3
EXPECTED_REQUESTED_PARALLEL = 16


def _projection(state: Mapping[str, Any]) -> tuple[bool, str | None]:
    published = state.get("publish_allowed") is True
    title = state.get("official_title") if published else None
    return published, title if isinstance(title, str) and title.strip() else None


def _projection_row(value: tuple[bool, str | None], count: int) -> dict[str, Any]:
    published, title = value
    return {
        "label": "PUBLISH" if published else "NO_PUBLISH",
        "publish_allowed": published,
        "official_title": title,
        "count": count,
    }


def _consensus_projection(values: Sequence[tuple[bool, str | None]]) -> dict[str, Any]:
    counts = Counter(values)
    projection, count = sorted(
        counts.items(), key=lambda item: (-item[1], item[0][0], item[0][1] or "")
    )[0]
    has_majority = count >= (REPEAT_COUNT // 2 + 1)
    published, title = projection
    return {
        "label": ("PUBLISH" if published else "NO_PUBLISH") if has_majority else "NO_CONSENSUS",
        "title": title if has_majority else None,
        "publish_allowed": published if has_majority else None,
        "count": count,
        "fraction": count / REPEAT_COUNT,
        "fraction_label": {1: "ONE_OF_THREE", 2: "TWO_OF_THREE", 3: "THREE_OF_THREE"}[count],
        "unanimous": count == REPEAT_COUNT,
        "variance_count": len(counts) - 1,
    }


def _consensus_bool(values: Sequence[bool | None]) -> dict[str, Any]:
    counts = Counter(values)
    value, count = sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))[0]
    known = sum(item is not None for item in values)
    true_count = sum(item is True for item in values)
    false_count = sum(item is False for item in values)
    majority = value if count >= 2 and value is not None else None
    return {
        "label": "COMPLIANT" if majority is True else "NONCOMPLIANT" if majority is False else "NO_CONSENSUS",
        "value": majority,
        "counts": {"compliant": true_count, "noncompliant": false_count, "not_estimable": REPEAT_COUNT - known},
        "consensus_fraction": count / REPEAT_COUNT,
        "fraction_label": {1: "ONE_OF_THREE", 2: "TWO_OF_THREE", 3: "THREE_OF_THREE"}[count],
        "unanimous": count == REPEAT_COUNT,
        "variance_count": len(counts) - 1,
    }


def _check_repeat_sets(
    runs: Sequence[Sequence[dict[str, Any]]], arm: str
) -> tuple[list[str], list[dict[str, dict[str, Any]]]]:
    if len(runs) != REPEAT_COUNT:
        raise ValueError(f"{arm}: exactly {REPEAT_COUNT} runs are required for 3-run majority")
    order: list[str] | None = None
    reference: set[str] | None = None
    indexes: list[dict[str, dict[str, Any]]] = []
    for number, rows in enumerate(runs, start=1):
        current_order, current = _index(rows, f"{arm}[{number}]")
        current_ids = set(current_order)
        if reference is not None and current_ids != reference:
            raise ValueError(
                f"{arm}: post_id set mismatch at repeat {number}: "
                f"missing={sorted(reference-current_ids)[:10]}, extra={sorted(current_ids-reference)[:10]}"
            )
        order, reference = current_order if order is None else order, current_ids if reference is None else reference
        indexes.append(current)
    assert order is not None
    return order, indexes


def _nested(value: Mapping[str, Any], *paths: tuple[str, ...]) -> Any:
    for path in paths:
        current: Any = value
        for key in path:
            if not isinstance(current, Mapping) or key not in current:
                current = None
                break
            current = current[key]
        if current is not None:
            return current
    return None


def _manifest_value(manifest: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in manifest:
            return manifest[name]
    return None


def _int_manifest(manifest: Mapping[str, Any], *names: str) -> int | None:
    value = _manifest_value(manifest, *names)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _model_id(manifest: Mapping[str, Any]) -> Any:
    return _nested(
        manifest,
        ("llm_model",), ("model",), ("model_id",),
        ("runtime_config", "llm_model"), ("runtime", "llm_model"),
    )


def _snapshot_hash(manifest: Mapping[str, Any]) -> Any:
    return _nested(
        manifest,
        ("publication_input_snapshot_sha256",),
        ("input_snapshot_hash",), ("input_snapshot_sha256",),
        ("input_sha256",), ("input_snapshot", "sha256"),
        ("input_snapshot", "hash"),
    )


def _manifest_record(manifest: Mapping[str, Any], arm: str, repeat: int, input_count: int) -> dict[str, Any]:
    completed = _int_manifest(manifest, "completed_count", "completed")
    flushed = _int_manifest(manifest, "flushed_count", "flushed")
    pending = _int_manifest(manifest, "pending_count", "pending")
    failed = _int_manifest(manifest, "failed_count", "failed")
    runtime_gate = _nested(manifest, ("runtime_completion_gate", "status"))
    record = {
        "arm": arm,
        "repeat": repeat,
        "input_post_count": _int_manifest(manifest, "input_post_count"),
        "completed": completed,
        "flushed": flushed,
        "pending": pending,
        "failed": failed,
        "terminal_artifacts_finalized": manifest.get("terminal_artifacts_finalized"),
        "runtime_completion_gate": runtime_gate,
        "requested_parallel": _int_manifest(manifest, "requested_parallel"),
        "effective_parallel": _int_manifest(manifest, "effective_parallel"),
        "dashboard_enabled": manifest.get("dashboard_enabled"),
        "model": _model_id(manifest),
        "input_snapshot_hash": _snapshot_hash(manifest),
        "model_lineage": {
            key: manifest.get(key)
            for key in ("model_lineage", "model_version", "model_fingerprint", "model_provider", "run_id")
            if key in manifest
        },
    }
    required = {
        "input_post_count": record["input_post_count"] == input_count,
        "completed": completed == input_count,
        "flushed": flushed == input_count,
        "pending": pending == 0,
        "failed": failed == 0,
        "terminal_artifacts_finalized": record["terminal_artifacts_finalized"] is True,
        "runtime_completion_gate": runtime_gate == "GO",
        "requested_parallel": record["requested_parallel"] == EXPECTED_REQUESTED_PARALLEL,
        "effective_parallel": record["effective_parallel"] == min(input_count, EXPECTED_REQUESTED_PARALLEL),
        "dashboard_enabled": record["dashboard_enabled"] is True,
        "model": isinstance(record["model"], str) and bool(record["model"].strip()),
        "input_snapshot_hash": isinstance(record["input_snapshot_hash"], str) and bool(record["input_snapshot_hash"].strip()),
    }
    failures = sorted(key for key, valid in required.items() if not valid)
    if failures:
        raise ValueError(f"{arm}[{repeat}] manifest contract failure: {','.join(failures)}")
    return record


def _validate_manifests(
    before: Sequence[Mapping[str, Any]] | None,
    after: Sequence[Mapping[str, Any]] | None,
    input_count: int,
) -> dict[str, Any]:
    if before is None and after is None:
        return {"status": "NOT_SUPPLIED", "records": [], "model_lineage_caveats": ["MANIFEST_NOT_SUPPLIED"]}
    if before is None or after is None or len(before) != REPEAT_COUNT or len(after) != REPEAT_COUNT:
        raise ValueError("manifests must be supplied for every BEFORE and AFTER repeat")
    records = [
        _manifest_record(manifest, arm, repeat, input_count)
        for arm, manifests in (("before", before), ("after", after))
        for repeat, manifest in enumerate(manifests, start=1)
    ]
    for key in ("model", "input_snapshot_hash"):
        values = {str(record[key]) for record in records}
        if len(values) != 1:
            raise ValueError(f"manifest comparability failure: {key} differs across arms/repeats")
    lineage_serialized = {json.dumps(record["model_lineage"], ensure_ascii=False, sort_keys=True) for record in records}
    caveats = []
    if len(lineage_serialized) > 1:
        caveats.append("MODEL_LINEAGE_METADATA_VARIES; model identifier is equal but detailed lineage differs")
    if any(not record["model_lineage"] for record in records):
        caveats.append("MODEL_LINEAGE_METADATA_PARTIAL")
    return {"status": "GO", "records": records, "model_lineage_caveats": caveats}


def _known_observability(states: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    def numeric(section: str, field: str) -> dict[str, Any]:
        values = [state.get(section, {}).get(field) for state in states]
        known = [value for value in values if isinstance(value, (int, float)) and not isinstance(value, bool)]
        return {"value": sum(known) if known else None, "known_rows": len(known), "unknown_rows": len(values) - len(known), "status": "MEASURED" if len(known) == len(values) else "PARTIAL" if known else "NOT_ESTIMABLE"}

    status_values = [state["search_health"].get("status") for state in states]
    known_status = [value for value in status_values if isinstance(value, str) and value != "UNKNOWN"]
    router_values = [state.get("review_router") for state in states]
    known_router = [value for value in router_values if value in {"ROUTED", "NOT_ROUTED"}]
    boolean = {}
    numeric_counts = {}
    is_flags = {}
    for field, count_name, flag_name in (
        ("degraded", "degraded_count", "is_degraded"),
        ("unrecovered_degraded", "unrecovered_degraded_count", "is_unrecovered_degraded"),
    ):
        values = [state["search_health"].get(field) for state in states]
        # Runtime rows use non-negative query counts, while older/synthetic rows
        # may expose only a boolean.  Keep both meanings explicit and never
        # coerce a boolean into a numeric count (which would hide missing data).
        numeric_values = [
            value for value in values
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ]
        numeric_counts[count_name] = {
            "value": sum(numeric_values) if numeric_values else None,
            "known_rows": len(numeric_values),
            "unknown_rows": len(values) - len(numeric_values),
            "status": (
                "MEASURED" if len(numeric_values) == len(values)
                else "PARTIAL" if numeric_values
                else "NOT_ESTIMABLE"
            ),
        }
        flags = [
            value if isinstance(value, bool)
            else value > 0 if isinstance(value, (int, float))
            and not isinstance(value, bool)
            else None
            for value in values
        ]
        known_flags = [value for value in flags if isinstance(value, bool)]
        flag_summary = {
            "true": sum(known_flags),
            "false": len(known_flags) - sum(known_flags),
            "known_rows": len(known_flags),
            "unknown_rows": len(flags) - len(known_flags),
            "status": (
                "MEASURED" if len(known_flags) == len(flags)
                else "PARTIAL" if known_flags
                else "NOT_ESTIMABLE"
            ),
        }
        # Preserve the pre-existing bool-only summary exactly for consumers;
        # numeric rows remain unknown there.  The additive `is_flags` summary
        # is the canonical normalized bool view for mixed numeric/bool input.
        legacy_known = [value for value in values if isinstance(value, bool)]
        boolean[field] = {
            "true": sum(legacy_known),
            "false": len(legacy_known) - sum(legacy_known),
            "known_rows": len(legacy_known),
            "unknown_rows": len(values) - len(legacy_known),
            "status": (
                "MEASURED" if len(legacy_known) == len(values)
                else "PARTIAL" if legacy_known
                else "NOT_ESTIMABLE"
            ),
        }
        is_flags[flag_name] = flag_summary
    return {
        "review_router": {"counts": dict(sorted(Counter(known_router).items())), "known_rows": len(known_router), "unknown_rows": len(router_values) - len(known_router)},
        "search_health": {
            "status_counts": dict(sorted(Counter(known_status).items())),
            "status_known_rows": len(known_status),
            "status_unknown_rows": len(status_values) - len(known_status),
            "queries_issued": numeric("search_health", "queries_issued"),
            "counts": numeric_counts,
            "is_flags": is_flags,
            "booleans": boolean,
            # Direct aliases make the two meanings discoverable without
            # requiring consumers to know the additive grouping keys.
            "degraded_count": numeric_counts["degraded_count"],
            "unrecovered_degraded_count": numeric_counts["unrecovered_degraded_count"],
            "is_degraded": is_flags["is_degraded"],
            "is_unrecovered_degraded": is_flags["is_unrecovered_degraded"],
        },
        "cost": {field: numeric("cost", field) for field in ("expert_calls", "search_calls", "prompt_tokens", "completion_tokens", "total_tokens", "wall_ms")},
    }


def _cohorts(ledger_row: Mapping[str, Any]) -> list[str]:
    value = ledger_row.get("cohorts", ledger_row.get("cohort", ledger_row.get("regression_cohorts")))
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, list):
        names = sorted({item.strip() for item in value if isinstance(item, str) and item.strip()})
        if names:
            return names
    return ["UNCLASSIFIED"]


def _breakdowns(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    selectors = {
        "cohort": lambda row: row["cohorts"],
        "review_verdict": lambda row: [str(row["expected"].get("review_verdict") or "UNKNOWN")],
        "dashboard_action": lambda row: [str(row["expected"].get("dashboard_action") or "UNKNOWN")],
    }
    for name, select in selectors.items():
        buckets: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for row in rows:
            for key in select(row):
                bucket = buckets[key]
                bucket["posts"] += 1
                for arm in ("before", "after"):
                    consensus = row[arm]["adjudication_consensus"]["value"]
                    if consensus is True:
                        bucket[f"{arm}_majority_compliant"] += 1
                    elif consensus is False:
                        bucket[f"{arm}_majority_noncompliant"] += 1
                    else:
                        bucket[f"{arm}_no_consensus"] += 1
                if row["transition"]["systematic_improvement"]:
                    bucket["systematic_improvement"] += 1
                if row["transition"]["systematic_regression"]:
                    bucket["systematic_regression"] += 1
                if row["transition"]["after_unsafe_publish_any_run"]:
                    bucket["after_unsafe_publish_any_run"] += 1
        result[name] = {key: dict(sorted(value.items())) for key, value in sorted(buckets.items())}
    return result


def build_repeat_consensus_report(
    ledger_rows: Sequence[dict[str, Any]],
    before_runs: Sequence[Sequence[dict[str, Any]]],
    after_runs: Sequence[Sequence[dict[str, Any]]],
    *,
    before_manifests: Sequence[Mapping[str, Any]] | None = None,
    after_manifests: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    _, ledger = _index(ledger_rows, "ledger")
    before_order, before = _check_repeat_sets(before_runs, "BEFORE")
    after_order, after = _check_repeat_sets(after_runs, "AFTER")
    if set(before_order) != set(after_order):
        raise ValueError("BEFORE/AFTER post_id set mismatch across repeated arms")
    missing_ledger = sorted(set(before_order) - set(ledger))
    if missing_ledger:
        raise ValueError(f"paired post_id missing from ledger: {missing_ledger[:10]}")
    manifest_report = _validate_manifests(before_manifests, after_manifests, len(before_order))
    rows: list[dict[str, Any]] = []
    states_by_arm: dict[str, list[dict[str, Any]]] = {"before": [], "after": []}
    for post_id in before_order:
        expected = _expected(ledger[post_id])
        per_arm = {}
        for arm, indexes in (("before", before), ("after", after)):
            states = [_runtime_state(index[post_id]) for index in indexes]
            qualities = [_quality(expected, state) for state in states]
            projections = [_projection(state) for state in states]
            distribution = [_projection_row(value, count) for value, count in sorted(Counter(projections).items(), key=lambda item: (not item[0][0], item[0][1] or ""))]
            per_arm[arm] = {
                "public_projection_distribution": distribution,
                "exact_adjudicated_compliance_count": sum(quality["adjudication_compliant"] is True for quality in qualities),
                "adjudication_consensus": _consensus_bool([quality["adjudication_compliant"] for quality in qualities]),
                "public_consensus": _consensus_projection(projections),
                "unsafe_publish_any_run": any(quality["unsafe_publish"] for quality in qualities),
                "wrong_title_any_run": any(
                    state["publish_allowed"]
                    and isinstance(expected.get("expected_public_title"), str)
                    and state.get("official_title") != expected["expected_public_title"]
                    for state in states
                ),
                "quality_any_run": {key: any(quality[key] for quality in qualities) for key in ("correct_title_recovery", "false_positive", "wrong_work_error", "hold_integrity", "pass_retention")},
            }
            states_by_arm[arm].extend(states)
        before_consensus = per_arm["before"]["adjudication_consensus"]["value"]
        after_consensus = per_arm["after"]["adjudication_consensus"]["value"]
        rows.append({
            "schema_version": SCHEMA_VERSION,
            "post_id": post_id,
            "cohorts": _cohorts(ledger[post_id]),
            "expected": expected,
            **per_arm,
            "transition": {
                "systematic_improvement": before_consensus is False and after_consensus is True,
                "systematic_regression": before_consensus is True and after_consensus is False,
                "normal_to_abnormal_concentration": per_arm["after"]["adjudication_consensus"]["fraction_label"] if before_consensus is True and after_consensus is False else None,
                "after_unsafe_publish_any_run": per_arm["after"]["unsafe_publish_any_run"],
                "unsafe_publish_introduced_any_run": not per_arm["before"]["unsafe_publish_any_run"] and per_arm["after"]["unsafe_publish_any_run"],
                "unsafe_publish_resolved_all_runs": per_arm["before"]["unsafe_publish_any_run"] and not per_arm["after"]["unsafe_publish_any_run"],
                "unsafe_publish_persistent_any_run": per_arm["before"]["unsafe_publish_any_run"] and per_arm["after"]["unsafe_publish_any_run"],
                "wrong_title_any_run": per_arm["after"]["wrong_title_any_run"],
                "wrong_title_introduced_any_run": not per_arm["before"]["wrong_title_any_run"] and per_arm["after"]["wrong_title_any_run"],
                "wrong_title_resolved_all_runs": per_arm["before"]["wrong_title_any_run"] and not per_arm["after"]["wrong_title_any_run"],
                "wrong_title_persistent_any_run": per_arm["before"]["wrong_title_any_run"] and per_arm["after"]["wrong_title_any_run"],
            },
        })
    systematic_improvements = sum(row["transition"]["systematic_improvement"] for row in rows)
    systematic_regressions = sum(row["transition"]["systematic_regression"] for row in rows)
    unsafe_after = sum(row["transition"]["after_unsafe_publish_any_run"] for row in rows)
    unsafe_introduced = sum(row["transition"]["unsafe_publish_introduced_any_run"] for row in rows)
    wrong_title_introduced = sum(row["transition"]["wrong_title_introduced_any_run"] for row in rows)
    wobbles = sum(
        row[arm]["adjudication_consensus"]["fraction_label"] == "ONE_OF_THREE"
        for row in rows for arm in ("before", "after")
    )
    gate = (
        "REVIEW_REQUIRED_SYSTEMATIC_REGRESSION" if systematic_regressions
        else "REVIEW_REQUIRED_NEW_UNSAFE_PUBLICATION" if unsafe_introduced
        else "REVIEW_REQUIRED_NEW_WRONG_TITLE" if wrong_title_introduced
        else "MEASURED_SEMANTIC_VARIANCE_REVIEW" if wobbles
        else "MEASURED_NOT_AUTOMATICALLY_APPROVED"
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "pairing": {"status": "EXACT", "row_count": len(rows), "repeat_count": REPEAT_COUNT, "post_id_order_sha256": hashlib.sha256(json.dumps(before_order, separators=(",", ":")).encode()).hexdigest()},
        "manifest_comparability": manifest_report,
        "policy": {
            "deterministic_contract": "HARD_FAILURE: exact post_id, uniqueness, and supplied manifest comparability failures do not produce an approval report.",
            "stochastic_semantics": "3-run majority; ONE_OF_THREE is surfaced as wobble, TWO_OF_THREE and THREE_OF_THREE are consensus strengths.",
            "rollback": "Any unsafe publish or wrong title occurrence is surfaced and exact-paired as introduced, resolved, or persistent. An isolated semantic wobble is not a hard failure or automatic rollback without repeated concentration or systematic evidence.",
        },
        "metrics": {
            "systematic_improvements": systematic_improvements,
            "systematic_regressions": systematic_regressions,
            "normal_to_abnormal_concentration": dict(sorted(Counter(row["transition"]["normal_to_abnormal_concentration"] for row in rows if row["transition"]["normal_to_abnormal_concentration"]).items())),
            "unsafe_publish_any_run": {
                arm: sum(row[arm]["unsafe_publish_any_run"] for row in rows)
                for arm in ("before", "after")
            },
            "after_unsafe_publish_any_run": unsafe_after,
            "unsafe_publish_transition": {
                "introduced_any_run": unsafe_introduced,
                "resolved_all_runs": sum(row["transition"]["unsafe_publish_resolved_all_runs"] for row in rows),
                "persistent_any_run": sum(row["transition"]["unsafe_publish_persistent_any_run"] for row in rows),
            },
            "wrong_title_any_run": {
                arm: sum(row[arm]["wrong_title_any_run"] for row in rows)
                for arm in ("before", "after")
            },
            "wrong_title_transition": {
                "introduced_any_run": wrong_title_introduced,
                "resolved_all_runs": sum(row["transition"]["wrong_title_resolved_all_runs"] for row in rows),
                "persistent_any_run": sum(row["transition"]["wrong_title_persistent_any_run"] for row in rows),
            },
            "quality_any_run": {arm: {key: sum(row[arm]["quality_any_run"][key] for row in rows) for key in ("correct_title_recovery", "false_positive", "wrong_work_error", "hold_integrity", "pass_retention")} for arm in ("before", "after")},
            "adjudicated_compliance": {arm: {"majority_compliant": sum(row[arm]["adjudication_consensus"]["value"] is True for row in rows), "majority_noncompliant": sum(row[arm]["adjudication_consensus"]["value"] is False for row in rows), "no_consensus": sum(row[arm]["adjudication_consensus"]["value"] is None for row in rows), "exact_compliant_runs": sum(row[arm]["exact_adjudicated_compliance_count"] for row in rows)} for arm in ("before", "after")},
            "observability": {arm: _known_observability(states) for arm, states in states_by_arm.items()},
        },
        "breakdowns": _breakdowns(rows),
        "gate": gate,
    }
    return rows, summary


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--before", type=Path, action="append", required=True, help="repeatable JSON array; exactly three")
    parser.add_argument("--after", type=Path, action="append", required=True, help="repeatable JSON array; exactly three")
    parser.add_argument("--before-manifest", type=Path, action="append")
    parser.add_argument("--after-manifest", type=Path, action="append")
    parser.add_argument("--post-jsonl", type=Path, required=True)
    parser.add_argument("--summary-json", type=Path, required=True)
    args = parser.parse_args()
    try:
        before_manifests = [_load_manifest(path) for path in args.before_manifest] if args.before_manifest else None
        after_manifests = [_load_manifest(path) for path in args.after_manifest] if args.after_manifest else None
        rows, summary = build_repeat_consensus_report(
            _load_jsonl(args.ledger), [_load_json_array(path) for path in args.before], [_load_json_array(path) for path in args.after],
            before_manifests=before_manifests, after_manifests=after_manifests,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"gate": "HARD_FAILURE", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    _write_jsonl(args.post_jsonl, rows)
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"gate": summary["gate"], "rows": len(rows)}, ensure_ascii=False))
    return 0


def _load_manifest(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object manifest")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
