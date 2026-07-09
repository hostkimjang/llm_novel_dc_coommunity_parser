from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _summary_int(summary: Mapping[str, Any], key: str) -> int:
    return int(summary.get(key) or 0)


def _row_search_health(split_report: Mapping[str, Any]) -> Mapping[str, Any]:
    health_evidence = split_report.get("health_evidence")
    if not isinstance(health_evidence, Mapping):
        return {}
    run_search = health_evidence.get("run_search_evidence")
    if not isinstance(run_search, Mapping):
        return {}
    row_health = run_search.get("row_search_health")
    return row_health if isinstance(row_health, Mapping) else {}


def _run_search_gate(split_report: Mapping[str, Any]) -> str | None:
    health_evidence = split_report.get("health_evidence")
    if not isinstance(health_evidence, Mapping):
        return None
    run_search = health_evidence.get("run_search_evidence")
    if not isinstance(run_search, Mapping):
        return None
    gate = run_search.get("gate")
    return str(gate) if gate is not None else None


def _post_ids(split_report: Mapping[str, Any], key: str) -> list[int]:
    derived = split_report.get("derived_sets")
    if not isinstance(derived, Mapping):
        return []
    values = derived.get(key)
    if not isinstance(values, list):
        return []
    out: list[int] = []
    for value in values:
        parsed = _to_int(value)
        if parsed is not None:
            out.append(parsed)
    return out


def audit_split_report(
    split_report: Mapping[str, Any],
    *,
    audit_id: str,
    expected_counts: Mapping[str, int | None] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    summary = split_report.get("summary")
    if not isinstance(summary, Mapping):
        raise ValueError("split report has no summary object")

    row_health = _row_search_health(split_report)
    run_search_gate = _run_search_gate(split_report)
    degraded_total = _to_int(row_health.get("degraded_total"))
    unrecovered_total = _to_int(row_health.get("unrecovered_degraded_total"))
    search_overlay_rows = _summary_int(summary, "search_degraded_or_recovered_overlay_rows")
    search_missing_rows = _summary_int(summary, "search_health_missing_rows")
    run_search_ok = (
        (run_search_gate in {None, "GO"})
        and (degraded_total in {None, 0})
        and (unrecovered_total in {None, 0})
        and search_overlay_rows == 0
        and search_missing_rows == 0
    )

    validation_issues: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    expected = dict(expected_counts or {})
    actual_counts = {
        "raw_regression_rows": int(split_report.get("raw_regression_rows") or 0),
        "expected_fp_removal_rows": _summary_int(summary, "expected_fp_removal_rows"),
        "intended_recovery_blind_judge_rows": _summary_int(
            summary,
            "intended_recovery_blind_judge_rows",
        ),
        "intended_recall_miss_rows": _summary_int(summary, "intended_recall_miss_rows"),
        "intended_wrong_work_rows": _summary_int(summary, "intended_wrong_work_rows"),
        "search_degraded_or_recovered_overlay_rows": search_overlay_rows,
        "ok_search_non_fp_rows_before_blind_judge": _summary_int(
            summary,
            "ok_search_non_fp_rows_before_blind_judge",
        ),
        "true_triage_ok_search_nonfp_rows": _summary_int(
            summary,
            "true_triage_ok_search_nonfp_rows",
        ),
        "search_health_missing_rows": search_missing_rows,
        "degraded_query_total": degraded_total,
        "unrecovered_degraded_total": unrecovered_total,
    }
    for key, expected_value in expected.items():
        if expected_value is None:
            continue
        actual = actual_counts.get(key)
        if actual != expected_value:
            validation_issues.append(
                {
                    "code": "expected_count_mismatch",
                    "field": key,
                    "expected": expected_value,
                    "actual": actual,
                }
            )

    if not run_search_ok:
        blockers.append(
            {
                "code": "search_health_not_admissible",
                "run_search_gate": run_search_gate,
                "degraded_query_total": degraded_total,
                "unrecovered_degraded_total": unrecovered_total,
                "search_overlay_rows": search_overlay_rows,
                "search_health_missing_rows": search_missing_rows,
            }
        )
    admissibility_gate = "GO" if run_search_ok and not validation_issues else "NO-GO"

    return {
        "report_type": "collateral_regression_admissibility_audit",
        "audit_id": audit_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_split_id": split_report.get("split_id"),
        "source_compare_id": split_report.get("source_compare_id"),
        "gate": admissibility_gate,
        "collateral_regression_evidence": "ADMISSIBLE" if run_search_ok else "NOT_ADMISSIBLE",
        "full375_rerun_gate": (
            "READY_FOR_FULL375_COLLATERAL_REPLAY"
            if run_search_ok
            else "BLOCKED_UNTIL_SEARCH_RECOVERY_FOR_HELD_ROWS"
        ),
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": actual_counts,
        "policy": {
            "expected_fp_removal": "accounting_exempt_when_detection_survey_fp",
            "intended_recovery": "blind_judge_title_correctness_before_exemption_or_fix",
            "search_non_ok": "defer_until_search_recovery_and_same_rows_rerun",
            "true_triage_scope": "ok_search_non_fp_only",
            "search_health_non_ok_run": "not_regression_judgment_evidence",
        },
        "post_id_sets": {
            "expected_fp_removal_post_ids": _post_ids(split_report, "expected_fp_removal_post_ids"),
            "intended_recovery_blind_judge_post_ids": _post_ids(
                split_report,
                "intended_recovery_blind_judge_post_ids",
            ),
            "search_degraded_or_recovered_post_ids": _post_ids(
                split_report,
                "search_degraded_or_recovered_post_ids",
            ),
            "true_triage_ok_search_nonfp_post_ids": _post_ids(
                split_report,
                "true_triage_ok_search_nonfp_post_ids",
            ),
        },
        "validation": {
            "expected_counts": expected,
            "issue_count": len(validation_issues),
            "issues": validation_issues,
        },
        "blockers": {
            "count": len(blockers),
            "items": blockers,
        },
    }


def write_markdown(path: Path, report: Mapping[str, Any]) -> None:
    summary = report["summary"]
    post_id_sets = report["post_id_sets"]
    lines = [
        f"# {report['audit_id']} collateral 판정 적격성 감사",
        "",
        "## 결론",
        "",
        f"- gate: `{report['gate']}`",
        f"- collateral regression evidence: `{report['collateral_regression_evidence']}`",
        f"- full375 rerun gate: `{report['full375_rerun_gate']}`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "- full_scan_approval: `false`",
        "",
        "## 3분 회계",
        "",
        f"- raw regression rows: `{summary['raw_regression_rows']}`",
        f"- expected_fp_removal 회계 면제: `{summary['expected_fp_removal_rows']}`",
        (
            "- intended recovery blind judge: "
            f"`{summary['intended_recovery_blind_judge_rows']}` "
            f"(recall_miss `{summary['intended_recall_miss_rows']}`, "
            f"wrong_work `{summary['intended_wrong_work_rows']}`)"
        ),
        f"- search degraded/recovered 판정 보류: `{summary['search_degraded_or_recovered_overlay_rows']}`",
        f"- search health missing: `{summary['search_health_missing_rows']}`",
        (
            "- ok-search & non-FP 후보: "
            f"`{summary['ok_search_non_fp_rows_before_blind_judge']}` "
            f"(의도 복구 제외 후 실제 triage `{summary['true_triage_ok_search_nonfp_rows']}`)"
        ),
        "",
        "## 검색 선결",
        "",
        (
            f"- degraded query `{summary['degraded_query_total']}`, "
            f"unrecovered degraded `{summary['unrecovered_degraded_total']}`."
        ),
        "- search health가 ok가 아닌 run의 collateral은 회귀 판정 근거로 쓰지 않는다.",
        "- search degraded/recovered 행은 검색 복구 후 해당 행만 재실행해 재판정한다.",
        "- full375 재실행은 검색 인프라 복구와 보류 행 재실행 뒤에만 연다.",
        "",
        "## 실제 triage post_id",
        "",
        "- true_triage_ok_search_nonfp: "
        + ", ".join(str(x) for x in post_id_sets["true_triage_ok_search_nonfp_post_ids"]),
        "",
        "## 검증",
        "",
        f"- issue_count: `{report['validation']['issue_count']}`",
    ]
    for issue in report["validation"]["issues"]:
        lines.append(
            "- `{code}` field=`{field}` expected=`{expected}` actual=`{actual}`".format(
                code=issue.get("code"),
                field=issue.get("field"),
                expected=issue.get("expected"),
                actual=issue.get("actual"),
            )
        )
    lines.extend(
        [
            "",
            "## 차단 사유",
            "",
            f"- blocker_count: `{report['blockers']['count']}`",
        ]
    )
    for blocker in report["blockers"]["items"]:
        lines.append(
            "- `{code}` gate=`{gate}` degraded_query=`{degraded}` unrecovered=`{unrecovered}` "
            "overlay=`{overlay}` missing=`{missing}`".format(
                code=blocker.get("code"),
                gate=blocker.get("run_search_gate"),
                degraded=blocker.get("degraded_query_total"),
                unrecovered=blocker.get("unrecovered_degraded_total"),
                overlay=blocker.get("search_overlay_rows"),
                missing=blocker.get("search_health_missing_rows"),
            )
        )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit whether collateral regressions are admissible evidence.")
    parser.add_argument("--split-report", required=True, type=Path)
    parser.add_argument("--audit-id", required=True)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--expect-raw-regression", type=int)
    parser.add_argument("--expect-expected-fp-removal", type=int)
    parser.add_argument("--expect-intended-recovery", type=int)
    parser.add_argument("--expect-intended-recall-miss", type=int)
    parser.add_argument("--expect-intended-wrong-work", type=int)
    parser.add_argument("--expect-search-overlay", type=int)
    parser.add_argument("--expect-ok-search-non-fp", type=int)
    parser.add_argument("--expect-true-triage", type=int)
    parser.add_argument("--expect-search-missing", type=int)
    parser.add_argument("--expect-degraded-query", type=int)
    parser.add_argument("--expect-unrecovered-degraded", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    expected_counts = {
        "raw_regression_rows": args.expect_raw_regression,
        "expected_fp_removal_rows": args.expect_expected_fp_removal,
        "intended_recovery_blind_judge_rows": args.expect_intended_recovery,
        "intended_recall_miss_rows": args.expect_intended_recall_miss,
        "intended_wrong_work_rows": args.expect_intended_wrong_work,
        "search_degraded_or_recovered_overlay_rows": args.expect_search_overlay,
        "ok_search_non_fp_rows_before_blind_judge": args.expect_ok_search_non_fp,
        "true_triage_ok_search_nonfp_rows": args.expect_true_triage,
        "search_health_missing_rows": args.expect_search_missing,
        "degraded_query_total": args.expect_degraded_query,
        "unrecovered_degraded_total": args.expect_unrecovered_degraded,
    }
    report = audit_split_report(
        load_json(args.split_report),
        audit_id=args.audit_id,
        expected_counts=expected_counts,
    )
    write_json(args.output_json, report)
    write_markdown(args.output_md, report)
    print(
        json.dumps(
            {
                "gate": report["gate"],
                "collateral_regression_evidence": report["collateral_regression_evidence"],
                "full375_rerun_gate": report["full375_rerun_gate"],
                "validation_issue_count": report["validation"]["issue_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if report["validation"]["issue_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
