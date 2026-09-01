#!/usr/bin/env python3
"""BEFORE/AFTER expert_main JSON 배열을 post_id exact transition으로 비교한다.

이 도구는 frozen adjudication ledger를 정답 기준으로 사용한다. 두 arm의 post_id
집합이 정확히 같지 않거나 중복이 있으면 표와 지표를 만들지 않는다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "frozen_2712_post_id_exact_transition_v1"
HIGH_RISK_VERDICTS = {
    "FP_NONNOVEL",
    "WRONG_WORK",
    "FN_TITLE_MISSING",
    "DASHBOARD_TITLE_MISMATCH",
    "EVIDENCE_CONFLICT",
    "EVIDENCE_INSUFFICIENT",
    "MULTIWORK_HOLD_CORRECT",
}


def _post_id(row: Mapping[str, Any], label: str) -> str:
    value = row.get("post_id")
    if value is None or isinstance(value, bool) or not str(value).strip():
        raise ValueError(f"{label}: post_id missing or invalid")
    return str(value).strip()


def _load_json_array(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise ValueError(f"{path}: expected JSON array of objects")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"{path}: expected JSONL objects")
    return rows


def _index(rows: Sequence[dict[str, Any]], label: str) -> tuple[list[str], dict[str, dict[str, Any]]]:
    order: list[str] = []
    result: dict[str, dict[str, Any]] = {}
    duplicate: list[str] = []
    for row in rows:
        post_id = _post_id(row, label)
        if post_id in result:
            duplicate.append(post_id)
        else:
            order.append(post_id)
            result[post_id] = row
    if duplicate:
        raise ValueError(f"{label}: duplicate post_id values: {sorted(set(duplicate))[:10]}")
    return order, result


def _identity(row: Mapping[str, Any]) -> Mapping[str, Any]:
    analysis = row.get("analysis_result")
    if not isinstance(analysis, dict):
        return {}
    identity = analysis.get("identity")
    return identity if isinstance(identity, dict) else {}


def _runtime_state(row: Mapping[str, Any]) -> dict[str, Any]:
    identity = _identity(row)
    decision = identity.get("promotion_decision")
    decision = decision if isinstance(decision, dict) else {}
    novel = identity.get("novel_identity")
    novel = novel if isinstance(novel, dict) else {}
    publish_allowed = decision.get("publish_allowed")
    if not isinstance(publish_allowed, bool):
        publish_allowed = bool(novel.get("official_title") and identity.get("identity_state") == "resolved_title")
    official_title = decision.get("official_title") if publish_allowed else None
    if publish_allowed and not official_title:
        official_title = novel.get("official_title")

    route_value: Any = None
    for container, key in (
        (identity, "manual_semantic_review_required"),
        (identity, "semantic_review_required"),
        (identity, "review_required"),
        (row.get("run_meta") if isinstance(row.get("run_meta"), dict) else {}, "semantic_review_required"),
    ):
        if isinstance(container, dict) and isinstance(container.get(key), bool):
            route_value = container[key]
            break
    route_status = "ROUTED" if route_value is True else "NOT_ROUTED" if route_value is False else "UNKNOWN"

    health = identity.get("search_health")
    if not isinstance(health, dict):
        run_meta = row.get("run_meta") if isinstance(row.get("run_meta"), dict) else {}
        health = run_meta.get("search_health") if isinstance(run_meta.get("search_health"), dict) else {}
    cost = (row.get("run_meta") or {}).get("decision_cost_trace") if isinstance(row.get("run_meta"), dict) else None
    cost = cost if isinstance(cost, dict) else {}
    system_state = identity.get("system_state")
    runtime_normal = bool(identity) and system_state in {None, "clean"} and not row.get("error")
    return {
        "publish_allowed": publish_allowed,
        "official_title": official_title,
        "system_state": system_state,
        "identity_state": identity.get("identity_state"),
        "runtime_normal": runtime_normal,
        "review_router": route_status,
        "search_health": {
            "status": health.get("status") or "UNKNOWN",
            "queries_issued": health.get("queries_issued"),
            "degraded": health.get("degraded"),
            "unrecovered_degraded": health.get("unrecovered_degraded"),
        },
        "cost": {
            "expert_calls": cost.get("expert_calls"),
            "search_calls": cost.get("search_calls"),
            "prompt_tokens": cost.get("prompt_tokens"),
            "completion_tokens": cost.get("completion_tokens"),
            "total_tokens": cost.get("total_tokens"),
            "wall_ms": cost.get("wall_ms"),
        },
    }


def _expected(ledger_row: Mapping[str, Any]) -> dict[str, Any]:
    verdict = ledger_row.get("independent_semantic_verdict")
    if not isinstance(verdict, dict):
        raise ValueError(f"ledger post_id={_post_id(ledger_row, 'ledger')}: verdict missing")
    action = verdict.get("dashboard_action")
    expected_title = None
    if action == "KEEP":
        pipeline = ledger_row.get("pipeline")
        pipeline = pipeline if isinstance(pipeline, dict) else {}
        expected_title = (
            pipeline.get("official_title")
            or verdict.get("pipeline_title")
            or verdict.get("recommended_title")
            or verdict.get("dashboard_title_expected")
        )
    elif action == "CORRECT":
        expected_title = verdict.get("recommended_title") or verdict.get("dashboard_title_expected")
    return {
        "review_verdict": verdict.get("review_verdict"),
        "dashboard_action": action,
        "recommended_title": verdict.get("recommended_title"),
        "expected_public_title": expected_title,
    }


def _adjudication_compliant(expected: Mapping[str, Any], state: Mapping[str, Any]) -> bool | None:
    """Return adjudication compliance, or None when the ledger is not estimable."""
    action = expected.get("dashboard_action")
    if action in {"KEEP", "CORRECT"}:
        expected_title = expected.get("expected_public_title")
        if not isinstance(expected_title, str) or not expected_title.strip():
            return None
        return state["publish_allowed"] is True and state.get("official_title") == expected_title
    if action in {"HOLD", "REMOVE", "NOT_APPLICABLE"}:
        return state["publish_allowed"] is False
    return None


def _quality(expected: Mapping[str, Any], state: Mapping[str, Any]) -> dict[str, Any]:
    published = state["publish_allowed"] is True
    title = state.get("official_title")
    expected_title = expected.get("expected_public_title")
    verdict = expected.get("review_verdict")
    action = expected.get("dashboard_action")
    exact_expected = bool(expected_title) and published and title == expected_title
    unsafe = published and (not expected_title or title != expected_title)
    wrong_work_error = verdict == "WRONG_WORK" and (
        (expected_title is None and published) or (expected_title is not None and not exact_expected)
    )
    adjudication_compliant = _adjudication_compliant(expected, state)
    return {
        "adjudication_compliant": adjudication_compliant,
        "adjudication_compliance_status": (
            "COMPLIANT" if adjudication_compliant is True
            else "NONCOMPLIANT" if adjudication_compliant is False
            else "NOT_ESTIMABLE"
        ),
        "unsafe_publish": unsafe,
        "correct_title_recovery": verdict == "FN_TITLE_MISSING" and exact_expected,
        "false_positive": verdict == "FP_NONNOVEL" and published,
        "wrong_work_error": wrong_work_error,
        "hold_integrity": action == "HOLD" and not published,
        "pass_retention": verdict == "PASS" and exact_expected,
    }


def _numeric_summary(states: Sequence[Mapping[str, Any]], section: str, field: str) -> dict[str, Any]:
    values = [state[section].get(field) for state in states]
    valid = [value for value in values if isinstance(value, (int, float)) and not isinstance(value, bool)]
    return {
        "value": sum(valid) if valid else None,
        "known_rows": len(valid),
        "unknown_rows": len(values) - len(valid),
        "status": "MEASURED" if len(valid) == len(values) else "PARTIAL" if valid else "NOT_ESTIMABLE",
    }


def build_transition_report(
    ledger_rows: Sequence[dict[str, Any]],
    before_rows: Sequence[dict[str, Any]],
    after_rows: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    _, ledger_index = _index(ledger_rows, "ledger")
    before_order, before_index = _index(before_rows, "BEFORE")
    after_order, after_index = _index(after_rows, "AFTER")
    before_ids = set(before_order)
    after_ids = set(after_order)
    if before_ids != after_ids:
        raise ValueError(
            "BEFORE/AFTER post_id set mismatch: "
            f"missing_after={sorted(before_ids-after_ids)[:10]}, extra_after={sorted(after_ids-before_ids)[:10]}"
        )
    missing_ledger = sorted(before_ids - set(ledger_index))
    if missing_ledger:
        raise ValueError(f"paired post_id missing from ledger: {missing_ledger[:10]}")

    transitions: list[dict[str, Any]] = []
    for post_id in before_order:
        expected = _expected(ledger_index[post_id])
        before = _runtime_state(before_index[post_id])
        after = _runtime_state(after_index[post_id])
        before_quality = _quality(expected, before)
        after_quality = _quality(expected, after)
        transitions.append(
            {
                "schema_version": SCHEMA_VERSION,
                "post_id": post_id,
                "expected": expected,
                "before": {**before, "quality": before_quality},
                "after": {**after, "quality": after_quality},
                "transition": {
                    "public_title_changed": before.get("official_title") != after.get("official_title"),
                    "normal_to_abnormal_regression": (
                        before_quality["adjudication_compliant"] is True
                        and after_quality["adjudication_compliant"] is False
                    ),
                    "runtime_normal_to_abnormal_regression": before["runtime_normal"] and not after["runtime_normal"],
                    "review_router_changed": before["review_router"] != after["review_router"],
                },
            }
        )

    def count_quality(arm: str, key: str) -> int:
        return sum(bool(row[arm]["quality"][key]) for row in transitions)

    hold_total = sum(row["expected"]["dashboard_action"] == "HOLD" for row in transitions)
    pass_total = sum(row["expected"]["review_verdict"] == "PASS" for row in transitions)
    fn_total = sum(row["expected"]["review_verdict"] == "FN_TITLE_MISSING" for row in transitions)
    high_risk = [row for row in transitions if row["expected"]["review_verdict"] in HIGH_RISK_VERDICTS]
    before_states = [row["before"] for row in transitions]
    after_states = [row["after"] for row in transitions]
    search_before = Counter(row["before"]["search_health"]["status"] for row in transitions)
    search_after = Counter(row["after"]["search_health"]["status"] for row in transitions)
    normal_controls = [
        row for row in transitions
        if row["expected"]["review_verdict"] in {"PASS", "NOISE_CORRECT", "CONTEXT_ONLY_CORRECT"}
    ]

    def ratio(numerator: int, denominator: int, unknown: int) -> dict[str, Any]:
        return {
            "numerator": numerator,
            "denominator": denominator,
            "unknown_rows": unknown,
            "value": numerator / denominator if denominator else None,
            "status": "MEASURED" if denominator and not unknown else (
                "PARTIAL" if denominator else "NOT_ESTIMABLE"
            ),
        }

    review_router = {}
    for arm in ("before", "after"):
        high_risk_routed = sum(row[arm]["review_router"] == "ROUTED" for row in high_risk)
        high_risk_not_routed = sum(row[arm]["review_router"] == "NOT_ROUTED" for row in high_risk)
        high_risk_unknown = sum(row[arm]["review_router"] == "UNKNOWN" for row in high_risk)
        control_routed = sum(row[arm]["review_router"] == "ROUTED" for row in normal_controls)
        control_not_routed = sum(row[arm]["review_router"] == "NOT_ROUTED" for row in normal_controls)
        control_unknown = sum(row[arm]["review_router"] == "UNKNOWN" for row in normal_controls)
        review_router[arm] = {
            "high_risk_rows": len(high_risk),
            "routed": high_risk_routed,
            "not_routed": high_risk_not_routed,
            "unknown": high_risk_unknown,
            "high_risk_recall": ratio(high_risk_routed, high_risk_routed + high_risk_not_routed, high_risk_unknown),
            "normal_control_rows": len(normal_controls),
            "normal_control_routed": control_routed,
            "normal_control_not_routed": control_not_routed,
            "normal_control_unknown": control_unknown,
            "normal_control_false_review_rate": ratio(
                control_routed, control_routed + control_not_routed, control_unknown
            ),
        }
    semantic_known_pairs = sum(
        row["before"]["quality"]["adjudication_compliant"] in {True, False}
        and row["after"]["quality"]["adjudication_compliant"] in {True, False}
        for row in transitions
    )
    semantic_unknown_pairs = len(transitions) - semantic_known_pairs
    semantic_regressions = sum(row["transition"]["normal_to_abnormal_regression"] for row in transitions)
    costs = {
        arm: {
            field: _numeric_summary(states, "cost", field)
            for field in ("expert_calls", "search_calls", "prompt_tokens", "completion_tokens", "total_tokens", "wall_ms")
        }
        for arm, states in (("before", before_states), ("after", after_states))
    }
    for arm, states in (("before", before_states), ("after", after_states)):
        known_wall = [state["cost"].get("wall_ms") for state in states if isinstance(state["cost"].get("wall_ms"), (int, float))]
        costs[arm]["row_wall_ms_median"] = median(known_wall) if known_wall else None

    summary = {
        "schema_version": SCHEMA_VERSION,
        "pairing": {
            "status": "EXACT",
            "row_count": len(transitions),
            "post_id_order_sha256": hashlib.sha256(
                json.dumps(before_order, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        },
        "metrics": {
            "unsafe_publish": {arm: count_quality(arm, "unsafe_publish") for arm in ("before", "after")},
            "correct_title_recovery": {
                "eligible": fn_total,
                **{arm: count_quality(arm, "correct_title_recovery") for arm in ("before", "after")},
            },
            "false_positive": {arm: count_quality(arm, "false_positive") for arm in ("before", "after")},
            "wrong_work_error": {arm: count_quality(arm, "wrong_work_error") for arm in ("before", "after")},
            "hold_integrity": {
                "eligible": hold_total,
                **{arm: count_quality(arm, "hold_integrity") for arm in ("before", "after")},
            },
            "pass_retention": {
                "eligible": pass_total,
                **{arm: count_quality(arm, "pass_retention") for arm in ("before", "after")},
            },
            "adjudication_compliant": {
                arm: {
                    "compliant": sum(row[arm]["quality"]["adjudication_compliant"] is True for row in transitions),
                    "noncompliant": sum(row[arm]["quality"]["adjudication_compliant"] is False for row in transitions),
                    "not_estimable": sum(row[arm]["quality"]["adjudication_compliant"] is None for row in transitions),
                }
                for arm in ("before", "after")
            },
            "normal_to_abnormal_regression": sum(
                row["transition"]["normal_to_abnormal_regression"] for row in transitions
            ),
            "runtime_normal_to_abnormal_regression": sum(
                row["transition"]["runtime_normal_to_abnormal_regression"] for row in transitions
            ),
            "normal_to_abnormal_regression_observability": {
                "numerator": semantic_regressions,
                "denominator": semantic_known_pairs,
                "unknown_rows": semantic_unknown_pairs,
                "status": "MEASURED" if semantic_known_pairs and not semantic_unknown_pairs else (
                    "PARTIAL" if semantic_known_pairs else "NOT_ESTIMABLE"
                ),
            },
            "review_router": review_router,
            "search_health": {
                "before_status_counts": dict(sorted(search_before.items())),
                "after_status_counts": dict(sorted(search_after.items())),
                "before_queries": _numeric_summary(before_states, "search_health", "queries_issued"),
                "after_queries": _numeric_summary(after_states, "search_health", "queries_issued"),
                "before_unrecovered_degraded": _numeric_summary(before_states, "search_health", "unrecovered_degraded"),
                "after_unrecovered_degraded": _numeric_summary(after_states, "search_health", "unrecovered_degraded"),
            },
            "calls_tokens_wall": costs,
        },
        "gate": "MEASURED_NOT_AUTOMATICALLY_APPROVED",
    }
    return transitions, summary


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--transition-jsonl", type=Path, required=True)
    parser.add_argument("--summary-json", type=Path, required=True)
    args = parser.parse_args()
    transitions, summary = build_transition_report(
        _load_jsonl(args.ledger), _load_json_array(args.before), _load_json_array(args.after)
    )
    _write_jsonl(args.transition_jsonl, transitions)
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"gate": summary["gate"], "rows": len(transitions)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
