#!/usr/bin/env python3
"""Replay the strict review-only router against the persisted 2,712-row scope.

Router construction receives only a checkpoint result and its publication
receipt.  The separate review ledger and cohort files are read only after that
step, solely to calculate offline metrics.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm_batch.ledger.publication_commit import (
    compute_publication_decision_commit,
    validate_publication_result_commit,
)
from src.llm_batch.measurement.semantic_review_router import (
    REVIEW_REQUIRED,
    build_semantic_review_router_receipt,
    validate_semantic_review_router_receipt,
)


SCHEMA_VERSION = "semantic_review_router_frozen2712_replay_v1"
DEFAULT_CHECKPOINT = ROOT / "out/expert_result_20260715_143806_848671_checkpoint.jsonl"
DEFAULT_LEDGER = ROOT / "out/live_combined_row_review_20260715_143806_848671_2712_20260716/final_2712_row_adjudication_ledger.jsonl"
DEFAULT_RAW_RESULT = ROOT / "out/expert_result_20260715_143806_848671.json"
DEFAULT_COHORT_DIR = ROOT / "out/regression_safe_2712_improvement_20260716/frozen_bundles_cap32/cohorts"

COHORT_FILES = {
    "published_intervention": "published_intervention.jsonl",
    "fn_title_missing": "fn_title_missing.jsonl",
    "fp_non_novel": "fp_non_novel.jsonl",
    "wrong_work": "wrong_work.jsonl",
    "multiwork": "multiwork.jsonl",
    "dashboard_title_mismatch": "dashboard_title_mismatch.jsonl",
    "arbitration": "arbitration.jsonl",
    "pass": "pass.jsonl",
    "safe_no_title": "safe_no_title.jsonl",
    "ultra_safe_no_title": "ultra_safe_no_title.jsonl",
}
DEFAULT_DENOMINATORS = {
    "published_intervention": 35,
    "fn_title_missing": 339,
    "fp_non_novel": 72,
    "wrong_work": 36,
    "multiwork": 91,
    "dashboard_title_mismatch": 7,
    "arbitration": 64,
    "pass": 230,
    "safe_no_title": 1580,
    "ultra_safe_no_title": 188,
    "evidence_conflict": 25,
    "evidence_insufficient": 302,
    "high_risk_union": 872,
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


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
        raise ValueError(f"{path}: JSONL row must be an object")
    return rows


def _read_json_array(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ValueError(f"missing file: {path}")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise ValueError(f"{path}: JSON array of objects required")
    return value


def _index(rows: Sequence[dict[str, Any]], label: str) -> tuple[list[str], dict[str, dict[str, Any]]]:
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


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
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


def _offline_view(ledger_row: Mapping[str, Any], memberships: Sequence[str]) -> dict[str, Any]:
    verdict = ledger_row.get("independent_semantic_verdict")
    if not isinstance(verdict, Mapping):
        raise ValueError(f"ledger {_post_id(ledger_row, 'ledger')}: semantic verdict missing")
    return {
        "review_verdict": verdict.get("review_verdict"),
        "dashboard_action": verdict.get("dashboard_action"),
        "cohorts": sorted(memberships),
    }


def _load_cohorts(
    cohort_dir: Path,
    *,
    ledger_ids: set[str],
    enforce_default_denominators: bool,
) -> dict[str, set[str]]:
    cohorts: dict[str, set[str]] = {}
    for name, filename in COHORT_FILES.items():
        path = cohort_dir / filename
        order, indexed = _index(_read_jsonl(path), f"cohort:{name}")
        identifiers = set(order)
        extra = identifiers - ledger_ids
        if extra:
            raise ValueError(f"cohort:{name}: post_id not in ledger: {sorted(extra)[:10]}")
        if enforce_default_denominators and len(identifiers) != DEFAULT_DENOMINATORS[name]:
            raise ValueError(
                f"cohort:{name}: expected {DEFAULT_DENOMINATORS[name]} rows, got {len(identifiers)}"
            )
        cohorts[name] = identifiers
    return cohorts


def _expected_predicate_sets(ledger_rows: Sequence[dict[str, Any]]) -> dict[str, set[str]]:
    result = {name: set() for name in COHORT_FILES}
    for row in ledger_rows:
        post_id = _post_id(row, "ledger")
        verdict = row.get("independent_semantic_verdict")
        if not isinstance(verdict, Mapping):
            raise ValueError(f"ledger {post_id}: semantic verdict missing")
        review_verdict, action = verdict.get("review_verdict"), verdict.get("dashboard_action")
        pipeline = row.get("pipeline") if isinstance(row.get("pipeline"), Mapping) else {}
        source = row.get("source_evidence") if isinstance(row.get("source_evidence"), Mapping) else {}
        if pipeline.get("publish_allowed") is True and action != "KEEP":
            result["published_intervention"].add(post_id)
        mapping = {
            "FN_TITLE_MISSING": "fn_title_missing",
            "FP_NONNOVEL": "fp_non_novel",
            "WRONG_WORK": "wrong_work",
            "MULTIWORK_HOLD_CORRECT": "multiwork",
            "DASHBOARD_TITLE_MISMATCH": "dashboard_title_mismatch",
            "PASS": "pass",
        }
        if review_verdict in mapping:
            result[mapping[review_verdict]].add(post_id)
        if review_verdict in {"NOISE_CORRECT", "CONTEXT_ONLY_CORRECT"} and action == "NOT_APPLICABLE":
            result["safe_no_title"].add(post_id)
            if (
                source.get("image_count") == 0
                and not source.get("explicit_ocr_titles")
                and not source.get("title_candidates")
                and source.get("comments_count") == 0
            ):
                result["ultra_safe_no_title"].add(post_id)
    return result


def _validate_cohort_predicates(
    cohorts: Mapping[str, set[str]], ledger_rows: Sequence[dict[str, Any]]
) -> None:
    expected = _expected_predicate_sets(ledger_rows)
    for name in expected:
        if name == "arbitration":
            continue
        if cohorts[name] != expected[name]:
            raise ValueError(
                f"cohort:{name}: ledger predicate mismatch "
                f"missing={sorted(expected[name] - cohorts[name])[:10]}, "
                f"extra={sorted(cohorts[name] - expected[name])[:10]}"
            )


def _metric(ids: set[str], routed: set[str]) -> dict[str, Any]:
    count, denominator = len(ids & routed), len(ids)
    return {
        "routed": count,
        "denominator": denominator,
        "rate": count / denominator if denominator else None,
    }


def build_router_replay_report(
    *,
    checkpoint_rows: Sequence[dict[str, Any]],
    ledger_rows: Sequence[dict[str, Any]],
    raw_rows: Sequence[dict[str, Any]],
    cohorts: Mapping[str, set[str]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    checkpoint_order, checkpoint = _index(checkpoint_rows, "checkpoint")
    ledger_order, ledger = _index(ledger_rows, "ledger")
    raw_order, raw = _index(raw_rows, "raw_result")
    ledger_ids, checkpoint_ids, raw_ids = set(ledger_order), set(checkpoint_order), set(raw_order)
    missing_checkpoint, missing_raw = ledger_ids - checkpoint_ids, ledger_ids - raw_ids
    if missing_checkpoint or missing_raw:
        raise ValueError(
            "ledger source join mismatch: "
            f"missing_checkpoint={sorted(missing_checkpoint)[:10]}, missing_raw={sorted(missing_raw)[:10]}"
        )
    for name, identifiers in cohorts.items():
        extra = set(identifiers) - ledger_ids
        if extra:
            raise ValueError(f"cohort:{name}: post_id not in ledger: {sorted(extra)[:10]}")
    _validate_cohort_predicates(cohorts, ledger_rows)
    membership = {
        post_id: [name for name, values in cohorts.items() if post_id in values]
        for post_id in ledger_order
    }
    rows: list[dict[str, Any]] = []
    states: Counter[str] = Counter()
    triggers: Counter[str] = Counter()
    unknown = 0
    decision_drift = stable_drift = projection_drift = 0
    receipt_coverage = 0
    for post_id in ledger_order:
        checkpoint_row = checkpoint[post_id]
        result = checkpoint_row.get("result")
        commit = checkpoint_row.get("publication_commit")
        if not isinstance(result, Mapping) or not isinstance(commit, Mapping):
            raise ValueError(f"checkpoint {post_id}: result/publication_commit required")
        index = checkpoint_row.get("global_idx")
        validate_publication_result_commit(
            result,
            commit,
            expected_scope_id=commit.get("publication_scope_id"),
            expected_input_index=index,
            expected_post_id=post_id,
        )
        attempt_run_id = commit.get("attempt_run_id")
        receipt = build_semantic_review_router_receipt(
            result, commit, attempt_run_id=attempt_run_id
        )
        validate_semantic_review_router_receipt(
            receipt,
            result=result,
            expected_publication_receipt=commit,
            expected_scope_id=commit.get("publication_scope_id"),
            expected_input_index=index,
            expected_post_id=post_id,
            expected_attempt_run_id=attempt_run_id,
        )
        receipt_coverage += 1
        attached = copy.deepcopy(dict(result))
        run_meta = attached.get("run_meta")
        if not isinstance(run_meta, dict):
            run_meta = {}
            attached["run_meta"] = run_meta
        run_meta["semantic_review_router_receipt"] = receipt
        recomputed = compute_publication_decision_commit(
            attached,
            publication_scope_id=commit.get("publication_scope_id"),
            attempt_run_id=attempt_run_id,
            input_index=index,
            post_id=post_id,
        )
        decision_equal = recomputed.decision_id == commit.get("decision_id")
        stable_equal = recomputed.stable_result_sha256 == commit.get("stable_result_sha256")
        projection_equal = recomputed.public_projection_sha256 == commit.get("public_projection_sha256")
        decision_drift += not decision_equal
        stable_drift += not stable_equal
        projection_drift += not projection_equal
        state = receipt["state"]
        states[state] += 1
        triggers.update(receipt["trigger_codes"])
        unknown += state == "UNKNOWN"
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "post_id": post_id,
                "router": {
                    "state": state,
                    "trigger_codes": receipt["trigger_codes"],
                    "unknown_reason_codes": receipt["unknown_reason_codes"],
                    "public_apply": receipt["public_apply"],
                    "receipt": receipt,
                },
                "noninterference": {
                    "decision_id_equal": decision_equal,
                    "stable_result_sha256_equal": stable_equal,
                    "public_projection_sha256_equal": projection_equal,
                },
                "offline_evaluation": _offline_view(ledger[post_id], membership[post_id]),
            }
        )
    routed = {row["post_id"] for row in rows if row["router"]["state"] == REVIEW_REQUIRED}
    verdict_sets = {
        "fn_title_missing": {pid for pid in ledger_ids if ledger[pid]["independent_semantic_verdict"]["review_verdict"] == "FN_TITLE_MISSING"},
        "fp_non_novel": {pid for pid in ledger_ids if ledger[pid]["independent_semantic_verdict"]["review_verdict"] == "FP_NONNOVEL"},
        "wrong_work": {pid for pid in ledger_ids if ledger[pid]["independent_semantic_verdict"]["review_verdict"] == "WRONG_WORK"},
        "multiwork": {pid for pid in ledger_ids if ledger[pid]["independent_semantic_verdict"]["review_verdict"] == "MULTIWORK_HOLD_CORRECT"},
        "dashboard_title_mismatch": {pid for pid in ledger_ids if ledger[pid]["independent_semantic_verdict"]["review_verdict"] == "DASHBOARD_TITLE_MISMATCH"},
        "evidence_conflict": {pid for pid in ledger_ids if ledger[pid]["independent_semantic_verdict"]["review_verdict"] == "EVIDENCE_CONFLICT"},
        "evidence_insufficient": {pid for pid in ledger_ids if ledger[pid]["independent_semantic_verdict"]["review_verdict"] == "EVIDENCE_INSUFFICIENT"},
    }
    high_risk_union = set().union(*verdict_sets.values())
    metrics = {name: _metric(values, routed) for name, values in verdict_sets.items()}
    metrics.update({name: _metric(values, routed) for name, values in cohorts.items()})
    metrics["high_risk_union"] = _metric(high_risk_union, routed)
    integrity_go = (
        len(rows) == len(ledger_rows)
        and receipt_coverage == len(ledger_rows)
        and unknown == 0
        and decision_drift == 0
        and stable_drift == 0
        and projection_drift == 0
    )
    semantic_reasons = []
    if not integrity_go:
        semantic_reasons.append("INTEGRITY_GATE_NOT_GO")
    for name in ("high_risk_union", "published_intervention"):
        if metrics[name]["rate"] != 1.0:
            semantic_reasons.append(f"{name.upper()}_RECALL_BELOW_100_PERCENT")
    for name in ("pass", "safe_no_title", "ultra_safe_no_title"):
        if metrics[name]["routed"]:
            semantic_reasons.append(f"{name.upper()}_FALSE_REVIEW_NONZERO")
    summary = {
        "schema_version": SCHEMA_VERSION,
        "scope": {
            "ledger_rows": len(ledger_rows),
            "checkpoint_rows": len(checkpoint_rows),
            "raw_rows": len(raw_rows),
            "exact_joined_rows": len(rows),
            "checkpoint_extra_rows": len(checkpoint_ids - ledger_ids),
            "raw_extra_rows": len(raw_ids - ledger_ids),
            "raw_extra_expected_inventory": 395,
        },
        "coverage": {
            "checkpoint_missing": len(missing_checkpoint),
            "raw_missing": len(missing_raw),
            "receipt_covered": receipt_coverage,
            "receipt_coverage_rate": receipt_coverage / len(ledger_rows) if ledger_rows else None,
        },
        "router": {
            "state_counts": dict(sorted(states.items())),
            "trigger_counts": dict(sorted(triggers.items())),
            "unknown_rows": unknown,
            "public_apply_true_rows": sum(row["router"]["public_apply"] is True for row in rows),
        },
        "noninterference": {
            "decision_id_drift_rows": decision_drift,
            "stable_result_sha256_drift_rows": stable_drift,
            "public_projection_sha256_drift_rows": projection_drift,
        },
        "offline_evaluation_only": {
            "metrics": metrics,
            "denominators": {name: values["denominator"] for name, values in metrics.items()},
            "cohort_overlap_caveat_ko": "cohort는 중첩될 수 있으므로 개별 routed 건수를 합산해 전체 효과로 해석하지 않는다.",
        },
        "gates": {
            "integrity_gate": "GO" if integrity_go else "NO_GO",
            "semantic_router_gate": "GO" if not semantic_reasons else "NO_GO",
            "semantic_router_gate_reasons": semantic_reasons,
            "mode": "REVIEW_ONLY",
            "public_apply": False,
            "full_scan_approval": False,
        },
    }
    return rows, summary


def _validate_default_denominators(summary: Mapping[str, Any]) -> None:
    metrics = summary["offline_evaluation_only"]["metrics"]
    for name, expected in DEFAULT_DENOMINATORS.items():
        if metrics[name]["denominator"] != expected:
            raise ValueError(f"default denominator {name}: expected {expected}, got {metrics[name]['denominator']}")
    if summary["scope"]["raw_extra_rows"] != 395:
        raise ValueError(f"raw extra inventory expected 395, got {summary['scope']['raw_extra_rows']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--raw-result", type=Path, default=DEFAULT_RAW_RESULT)
    parser.add_argument("--cohort-dir", type=Path, default=DEFAULT_COHORT_DIR)
    parser.add_argument("--rows-jsonl", type=Path, required=True)
    parser.add_argument("--summary-json", type=Path, required=True)
    parser.add_argument("--no-default-denominator-check", action="store_true")
    args = parser.parse_args()
    ledger_rows = _read_jsonl(args.ledger)
    cohorts = _load_cohorts(
        args.cohort_dir,
        ledger_ids=set(_index(ledger_rows, "ledger")[0]),
        enforce_default_denominators=not args.no_default_denominator_check,
    )
    rows, summary = build_router_replay_report(
        checkpoint_rows=_read_jsonl(args.checkpoint),
        ledger_rows=ledger_rows,
        raw_rows=_read_json_array(args.raw_result),
        cohorts=cohorts,
    )
    if not args.no_default_denominator_check:
        _validate_default_denominators(summary)
    summary["source_hashes"] = {
        "checkpoint_sha256": _file_sha256(args.checkpoint),
        "ledger_sha256": _file_sha256(args.ledger),
        "raw_result_sha256": _file_sha256(args.raw_result),
        "cohort_file_sha256": {
            name: _file_sha256(args.cohort_dir / filename)
            for name, filename in sorted(COHORT_FILES.items())
        },
    }
    _atomic_write(args.rows_jsonl, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows))
    _atomic_write(args.summary_json, json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
