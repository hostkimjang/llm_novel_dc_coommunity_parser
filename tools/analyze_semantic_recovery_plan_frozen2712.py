#!/usr/bin/env python3
"""Replay P1 PLAN_ONLY receipts over the persisted 2,712-row publication scope."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm_batch.ledger.publication_commit import (
    compute_publication_decision_commit,
    validate_publication_result_commit,
)
from src.llm_batch.measurement.semantic_recovery_plan import (
    PLAN_UNKNOWN,
    build_semantic_recovery_plan_receipt,
    validate_semantic_recovery_plan_receipt,
)


SCHEMA_VERSION = "semantic_recovery_plan_frozen2712_replay_v1"
DEFAULT_CHECKPOINT = ROOT / "out/expert_result_20260715_143806_848671_checkpoint.jsonl"
DEFAULT_LEDGER = ROOT / "out/live_combined_row_review_20260715_143806_848671_2712_20260716/final_2712_row_adjudication_ledger.jsonl"
DEFAULT_DENOMINATORS = {
    "ledger_rows": 2712,
    "published_intervention": 35,
    "high_risk_union": 872,
    "fn_title_missing": 339,
    "fp_non_novel": 72,
    "wrong_work": 36,
    "multiwork": 91,
    "dashboard_title_mismatch": 7,
    "evidence_conflict": 25,
    "evidence_insufficient": 302,
    "pass": 230,
    "safe_no_title": 1580,
    "ultra_safe_no_title": 188,
}
HIGH_RISK_VERDICTS = frozenset(
    {
        "FN_TITLE_MISSING",
        "FP_NONNOVEL",
        "WRONG_WORK",
        "MULTIWORK_HOLD_CORRECT",
        "DASHBOARD_TITLE_MISMATCH",
        "EVIDENCE_CONFLICT",
        "EVIDENCE_INSUFFICIENT",
    }
)


def _post_id(row: Mapping[str, Any], label: str) -> str:
    value = row.get("post_id")
    if value is None or isinstance(value, bool) or not str(value).strip():
        raise ValueError(f"{label}: invalid post_id")
    return str(value).strip()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ValueError(f"missing file: {path}")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"{path}: JSONL objects required")
    return rows


def _index(
    rows: Sequence[dict[str, Any]], label: str
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    order: list[str] = []
    index: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for row in rows:
        post_id = _post_id(row, label)
        if post_id in index:
            duplicates.append(post_id)
            continue
        order.append(post_id)
        index[post_id] = row
    if duplicates:
        raise ValueError(f"{label}: duplicate post_id values: {sorted(set(duplicates))[:10]}")
    return order, index


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _ledger_view(row: Mapping[str, Any]) -> tuple[str, str, set[str]]:
    verdict = row.get("independent_semantic_verdict")
    if not isinstance(verdict, Mapping):
        raise ValueError(f"ledger {_post_id(row, 'ledger')}: semantic verdict missing")
    review_verdict = str(verdict.get("review_verdict") or "UNKNOWN")
    action = str(verdict.get("dashboard_action") or "UNKNOWN")
    pipeline = row.get("pipeline") if isinstance(row.get("pipeline"), Mapping) else {}
    source = row.get("source_evidence") if isinstance(row.get("source_evidence"), Mapping) else {}
    cohorts: set[str] = set()
    if pipeline.get("publish_allowed") is True and action != "KEEP":
        cohorts.add("published_intervention")
    if review_verdict in HIGH_RISK_VERDICTS:
        cohorts.add("high_risk_union")
    mapping = {
        "FN_TITLE_MISSING": "fn_title_missing",
        "FP_NONNOVEL": "fp_non_novel",
        "WRONG_WORK": "wrong_work",
        "MULTIWORK_HOLD_CORRECT": "multiwork",
        "DASHBOARD_TITLE_MISMATCH": "dashboard_title_mismatch",
        "EVIDENCE_CONFLICT": "evidence_conflict",
        "EVIDENCE_INSUFFICIENT": "evidence_insufficient",
        "PASS": "pass",
    }
    if review_verdict in mapping:
        cohorts.add(mapping[review_verdict])
    if review_verdict in {"NOISE_CORRECT", "CONTEXT_ONLY_CORRECT"} and action == "NOT_APPLICABLE":
        cohorts.add("safe_no_title")
        if (
            source.get("image_count") == 0
            and source.get("comments_count") == 0
            and not source.get("explicit_ocr_titles")
            and not source.get("title_candidates")
        ):
            cohorts.add("ultra_safe_no_title")
    return review_verdict, action, cohorts


def _breakdown_entry(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    state_counts = Counter(row["plan_state"] for row in rows)
    query_allowed = sum(row["query_execution_allowed"] is True for row in rows)
    return {
        "denominator": len(rows),
        "plan_state_counts": dict(sorted(state_counts.items())),
        "query_execution_allowed_rows": query_allowed,
        "canonical_binding_rows": sum(row["canonical_binding_count"] > 0 for row in rows),
        "raw_ocr_evidence_rows": sum(row["raw_ocr_evidence_count"] > 0 for row in rows),
    }


def _offline_breakdowns(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_verdict: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    by_action: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    by_cohort: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_verdict[row["review_verdict"]].append(row)
        by_action[row["dashboard_action"]].append(row)
        for cohort in row["cohorts"]:
            by_cohort[cohort].append(row)
    return {
        "verdict": {
            name: _breakdown_entry(items) for name, items in sorted(by_verdict.items())
        },
        "action": {
            name: _breakdown_entry(items) for name, items in sorted(by_action.items())
        },
        "cohort": {
            name: _breakdown_entry(items) for name, items in sorted(by_cohort.items())
        },
        "cohort_overlap_caveat_ko": (
            "cohort는 중첩될 수 있으므로 개별 건수를 합산해 전체 효과로 해석하지 않는다."
        ),
    }


def build_recovery_plan_replay_report(
    *, checkpoint_rows: Sequence[dict[str, Any]], ledger_rows: Sequence[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    checkpoint_order, checkpoint = _index(checkpoint_rows, "checkpoint")
    ledger_order, ledger = _index(ledger_rows, "ledger")
    checkpoint_ids, ledger_ids = set(checkpoint_order), set(ledger_order)
    missing = ledger_ids - checkpoint_ids
    if missing:
        raise ValueError(f"checkpoint missing ledger post_id values: {sorted(missing)[:10]}")

    output_rows: list[dict[str, Any]] = []
    states: Counter[str] = Counter()
    blockers: Counter[str] = Counter()
    media_actions: Counter[str] = Counter()
    relation_evidence_counts: Counter[str] = Counter()
    relation_rows: Counter[str] = Counter()
    query_purposes: Counter[str] = Counter()
    max_queries: Counter[int] = Counter()
    canonical_ids: set[str] = set()
    canonical_binding_rows = canonical_binding_count = 0
    ocr_rows = ocr_count = 0
    query_allowed_rows = 0
    planned_query_budget = 0
    search_calls = network_calls = public_apply_true = 0
    receipt_coverage = unknown_rows = 0
    decision_drift = stable_drift = projection_drift = 0

    # No ledger data is read inside this loop until after the receipt and
    # noninterference result have been finalized.
    pending_offline: dict[str, tuple[str, str, set[str]]] = {}
    for post_id in ledger_order:
        checkpoint_row = checkpoint[post_id]
        result = checkpoint_row.get("result")
        commit = checkpoint_row.get("publication_commit")
        input_index = checkpoint_row.get("global_idx")
        if checkpoint_row.get("status") != "completed":
            raise ValueError(f"checkpoint {post_id}: completed status required")
        if not isinstance(result, Mapping) or not isinstance(commit, Mapping):
            raise ValueError(f"checkpoint {post_id}: result/publication_commit required")
        authoritative = validate_publication_result_commit(
            result,
            commit,
            expected_scope_id=commit.get("publication_scope_id"),
            expected_input_index=input_index,
            expected_post_id=post_id,
        )
        receipt = build_semantic_recovery_plan_receipt(
            result,
            authoritative,
            attempt_run_id=authoritative.attempt_run_id,
        )
        validate_semantic_recovery_plan_receipt(
            receipt,
            result=result,
            expected_publication_receipt=authoritative,
            expected_scope_id=authoritative.publication_scope_id,
            expected_input_index=input_index,
            expected_post_id=post_id,
            expected_attempt_run_id=authoritative.attempt_run_id,
        )
        receipt_coverage += 1
        attached = copy.deepcopy(dict(result))
        run_meta = attached.get("run_meta")
        if not isinstance(run_meta, dict):
            run_meta = {}
            attached["run_meta"] = run_meta
        run_meta["semantic_recovery_plan_receipt"] = receipt
        recomputed = compute_publication_decision_commit(
            attached,
            publication_scope_id=authoritative.publication_scope_id,
            attempt_run_id=authoritative.attempt_run_id,
            input_index=input_index,
            post_id=post_id,
        )
        decision_equal = recomputed.decision_id == authoritative.decision_id
        stable_equal = (
            recomputed.stable_result_sha256 == authoritative.stable_result_sha256
        )
        projection_equal = (
            recomputed.public_projection_sha256
            == authoritative.public_projection_sha256
        )
        decision_drift += not decision_equal
        stable_drift += not stable_equal
        projection_drift += not projection_equal

        plan = receipt["plan"]
        query = plan["query_plan"]
        bindings = plan["canonical_bindings"]
        states[plan["state"]] += 1
        blockers.update(plan["blocker_codes"])
        media_actions[plan["media_action"]] += 1
        query_purposes.update(query["purposes"])
        max_queries[query["max_queries"]] += 1
        query_allowed_rows += query["query_execution_allowed"] is True
        planned_query_budget += query["max_queries"]
        search_calls += plan["search_calls_executed"]
        network_calls += plan["network_calls_executed"]
        public_apply_true += receipt["public_apply"] is True
        unknown_rows += plan["state"] == PLAN_UNKNOWN
        for role, count in plan["relationship_counts"].items():
            relation_evidence_counts[role] += count
            relation_rows[role] += count > 0
        if bindings:
            canonical_binding_rows += 1
            canonical_binding_count += len(bindings)
            canonical_ids.update(binding["canonical_work_id"] for binding in bindings)
        if plan["raw_ocr_evidence_count"]:
            ocr_rows += 1
            ocr_count += plan["raw_ocr_evidence_count"]
        pending_offline[post_id] = _ledger_view(ledger[post_id])
        output_rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "post_id": post_id,
                "plan_receipt": receipt,
                "noninterference": {
                    "decision_id_equal": decision_equal,
                    "stable_result_sha256_equal": stable_equal,
                    "public_projection_sha256_equal": projection_equal,
                },
            }
        )

    metric_rows: list[dict[str, Any]] = []
    for row in output_rows:
        review_verdict, action, cohorts = pending_offline[row["post_id"]]
        row["offline_evaluation"] = {
            "review_verdict": review_verdict,
            "dashboard_action": action,
            "cohorts": sorted(cohorts),
        }
        plan = row["plan_receipt"]["plan"]
        metric_rows.append(
            {
                "review_verdict": review_verdict,
                "dashboard_action": action,
                "cohorts": cohorts,
                "plan_state": plan["state"],
                "query_execution_allowed": plan["query_plan"][
                    "query_execution_allowed"
                ],
                "canonical_binding_count": len(plan["canonical_bindings"]),
                "raw_ocr_evidence_count": plan["raw_ocr_evidence_count"],
            }
        )
    breakdowns = _offline_breakdowns(metric_rows)
    integrity_go = (
        len(output_rows) == len(ledger_rows)
        and receipt_coverage == len(ledger_rows)
        and unknown_rows == 0
        and decision_drift == 0
        and stable_drift == 0
        and projection_drift == 0
        and search_calls == 0
        and network_calls == 0
        and public_apply_true == 0
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "coverage": {
            "ledger_rows": len(ledger_rows),
            "checkpoint_rows": len(checkpoint_rows),
            "exact_joined_rows": len(output_rows),
            "checkpoint_duplicate_post_ids": 0,
            "ledger_duplicate_post_ids": 0,
            "checkpoint_missing_ledger_rows": len(missing),
            "raw_extra_rows": len(checkpoint_ids - ledger_ids),
            "receipt_covered_rows": receipt_coverage,
            "receipt_coverage_rate": (
                receipt_coverage / len(ledger_rows) if ledger_rows else None
            ),
        },
        "plan": {
            "state_counts": dict(sorted(states.items())),
            "blocker_counts": dict(sorted(blockers.items())),
            "media_action_counts": dict(sorted(media_actions.items())),
            "relationship_evidence_counts": dict(
                sorted(relation_evidence_counts.items())
            ),
            "relationship_rows": dict(sorted(relation_rows.items())),
            "canonical_binding_rows": canonical_binding_rows,
            "canonical_binding_count": canonical_binding_count,
            "canonical_unique_work_id_count": len(canonical_ids),
            "raw_ocr_evidence_rows": ocr_rows,
            "raw_ocr_evidence_count": ocr_count,
            "query_purpose_counts": dict(sorted(query_purposes.items())),
            "query_execution_allowed_rows": query_allowed_rows,
            "max_queries_distribution": {
                str(key): value for key, value in sorted(max_queries.items())
            },
            "planned_query_budget": planned_query_budget,
            "search_calls_executed": search_calls,
            "network_calls_executed": network_calls,
            "public_apply_true_rows": public_apply_true,
            "unknown_rows": unknown_rows,
        },
        "noninterference": {
            "decision_id_drift_rows": decision_drift,
            "stable_result_sha256_drift_rows": stable_drift,
            "public_projection_sha256_drift_rows": projection_drift,
        },
        "offline_evaluation_only": breakdowns,
        "gates": {
            "integrity_gate": "GO" if integrity_go else "NO_GO",
            "semantic_effectiveness_gate": "NO_GO",
            "semantic_effectiveness_reasons": [
                "PLAN_ONLY_NO_RUNTIME_EFFECT_MEASUREMENT",
                "FROZEN_OFFLINE_EVALUATION_ONLY",
            ],
            "mode": "PLAN_ONLY",
            "public_apply": False,
            "full_scan_approval": False,
        },
    }
    return output_rows, summary


def _validate_default_denominators(summary: Mapping[str, Any]) -> None:
    coverage = summary["coverage"]
    if coverage["ledger_rows"] != DEFAULT_DENOMINATORS["ledger_rows"]:
        raise ValueError(
            f"default ledger denominator expected 2712, got {coverage['ledger_rows']}"
        )
    cohorts = summary["offline_evaluation_only"]["cohort"]
    for name, expected in DEFAULT_DENOMINATORS.items():
        if name == "ledger_rows":
            continue
        actual = cohorts.get(name, {}).get("denominator", 0)
        if actual != expected:
            raise ValueError(
                f"default cohort denominator {name}: expected {expected}, got {actual}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--rows-jsonl", type=Path, required=True)
    parser.add_argument("--summary-json", type=Path, required=True)
    parser.add_argument("--no-default-denominator-check", action="store_true")
    args = parser.parse_args()
    rows, summary = build_recovery_plan_replay_report(
        checkpoint_rows=_read_jsonl(args.checkpoint),
        ledger_rows=_read_jsonl(args.ledger),
    )
    if not args.no_default_denominator_check:
        _validate_default_denominators(summary)
    summary["source_hashes"] = {
        "checkpoint_sha256": _file_sha256(args.checkpoint),
        "ledger_sha256": _file_sha256(args.ledger),
    }
    _atomic_write(
        args.rows_jsonl,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        ),
    )
    _atomic_write(
        args.summary_json,
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )


if __name__ == "__main__":
    main()
