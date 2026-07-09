from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.compare_completed779_improvement import load_json_or_jsonl  # noqa: E402


FP_DISAGREEMENT_TYPES = {
    "over_resolved",
    "wrong_work",
    "wrong_relevance",
    "garbage_title",
    "cross_media_or_famous_mismatch",
    "wrong_discussion_type",
}

SEARCH_DEFER_STATUSES = {"SEARCH_DEGRADED", "SEARCH_DEGRADED_RECOVERED"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _identity(row: dict[str, Any]) -> dict[str, Any]:
    analysis = row.get("analysis_result")
    if not isinstance(analysis, dict):
        return {}
    identity = analysis.get("identity")
    return identity if isinstance(identity, dict) else {}


def _search_health(row: dict[str, Any]) -> dict[str, Any] | None:
    for source in (_identity(row).get("search_health"), row.get("search_health")):
        if isinstance(source, dict):
            return source
    return None


def _search_status(row: dict[str, Any] | None) -> tuple[str, dict[str, Any] | None]:
    if row is None:
        return "RESULT_ROW_MISSING", None
    health = _search_health(row)
    if not isinstance(health, dict):
        return "MISSING", None
    status = str(health.get("status") or "").strip() or "MISSING"
    return status, health


def _survey_errors(path: Path) -> dict[int, dict[str, Any]]:
    payload = load_json(path)
    errors = payload.get("errors") if isinstance(payload, dict) else None
    if not isinstance(errors, list):
        raise ValueError(f"survey errors file has no errors list: {path}")
    out: dict[int, dict[str, Any]] = {}
    for row in errors:
        if not isinstance(row, dict):
            continue
        try:
            out[int(row["post_id"])] = row
        except Exception:
            continue
    return out


def _raw_regression_rows(collateral: dict[str, Any]) -> list[dict[str, Any]]:
    rows = collateral.get("rows")
    if not isinstance(rows, list):
        raise ValueError("collateral compare has no rows list")
    return [row for row in rows if isinstance(row, dict) and row.get("is_regression")]


def _title_from_identity(row: dict[str, Any], key: str) -> str | None:
    identity = row.get(key)
    if isinstance(identity, dict):
        value = identity.get("official_title")
        return str(value) if value is not None else None
    return None


def _health_number(health: dict[str, Any] | None, *keys: str) -> Any:
    if not isinstance(health, dict):
        return None
    for key in keys:
        if key in health:
            return health.get(key)
    return None


def classify_rows(
    *,
    collateral_compare: dict[str, Any],
    survey_errors: dict[int, dict[str, Any]],
    after_rows: list[dict[str, Any]],
    split_id: str,
    health_audit: dict[str, Any] | None = None,
    search_shard_audit: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    after_by_post_id: dict[int, dict[str, Any]] = {}
    for row in after_rows:
        if isinstance(row, dict) and row.get("post_id") is not None:
            try:
                after_by_post_id[int(row["post_id"])] = row
            except Exception:
                pass

    rows: list[dict[str, Any]] = []
    for row in _raw_regression_rows(collateral_compare):
        post_id = int(row["post_id"])
        survey = survey_errors.get(post_id)
        after_row = after_by_post_id.get(post_id)
        search_status, search_health = _search_status(after_row)
        survey_disagreement = str((survey or {}).get("disagreement_type") or "")
        survey_failure = str((survey or {}).get("failure_class") or "")
        tags: list[str] = []

        expected_fp = (
            row.get("status") == "resolved_to_null"
            and survey is not None
            and survey_disagreement in FP_DISAGREEMENT_TYPES
        )
        recall_recovery = (
            row.get("status") == "null_to_resolved"
            and survey is not None
            and survey_failure == "recall_miss"
        )
        wrong_work_repair = (
            row.get("status") == "resolved_to_different_title"
            and survey is not None
            and survey_failure == "wrong_work_among_aliases"
        )
        search_deferred = search_status in SEARCH_DEFER_STATUSES
        search_missing = search_status in {"MISSING", "RESULT_ROW_MISSING"}

        if expected_fp:
            tags.append("expected_fp_removal")
        if recall_recovery:
            tags.append("intended_recall_miss_recovery")
        if wrong_work_repair:
            tags.append("intended_wrong_work_repair")
        if search_deferred:
            tags.append("search_health_deferred")
        if search_missing:
            tags.append("search_health_missing_not_admissible")

        if expected_fp:
            primary_action = "expected_fp_removal_exempt"
        elif recall_recovery or wrong_work_repair:
            primary_action = "blind_judge_title_correctness"
        elif search_deferred:
            primary_action = "hold_for_search_recovery_rerun"
        elif search_missing:
            primary_action = "hold_for_search_health_missing"
        else:
            primary_action = "true_triage_ok_search_nonfp"

        rows.append(
            {
                "post_id": post_id,
                "status": row.get("status"),
                "primary_action": primary_action,
                "tags": tags,
                "before_title": _title_from_identity(row, "before_identity"),
                "after_title": _title_from_identity(row, "after_identity"),
                "survey_failure_class": survey_failure or None,
                "survey_disagreement_type": survey_disagreement or None,
                "survey_judge_label": (survey or {}).get("judge_label"),
                "survey_correct_hypothesis": (survey or {}).get("correct_hypothesis"),
                "survey_url": (survey or {}).get("url"),
                "search_status": search_status,
                "search_queries": _health_number(search_health, "queries", "queries_issued", "query_total"),
                "search_degraded": _health_number(search_health, "degraded", "degraded_count"),
                "search_degraded_recovered": _health_number(
                    search_health,
                    "degraded_recovered",
                    "degraded_recovered_count",
                ),
                "search_unrecovered_degraded": _health_number(
                    search_health,
                    "unrecovered_degraded",
                    "unrecovered_degraded_count",
                ),
                "post_title": after_row.get("title") if isinstance(after_row, dict) else None,
            }
        )

    action_counts = Counter(row["primary_action"] for row in rows)
    tag_counts = Counter(tag for row in rows for tag in row.get("tags") or [])
    search_counts = Counter(row["search_status"] for row in rows)
    status_counts = Counter(row["status"] for row in rows)
    ok_non_fp_rows = [
        row for row in rows if row["search_status"] == "ok" and "expected_fp_removal" not in row["tags"]
    ]
    true_triage_rows = [row for row in rows if row["primary_action"] == "true_triage_ok_search_nonfp"]
    search_overlay_rows = [row for row in rows if "search_health_deferred" in row["tags"]]
    expected_rows = [row for row in rows if row["primary_action"] == "expected_fp_removal_exempt"]
    blind_rows = [row for row in rows if row["primary_action"] == "blind_judge_title_correctness"]

    health_search = (health_audit or {}).get("search_evidence") if isinstance(health_audit, dict) else None
    report = {
        "report_type": "collateral_survey_search_health_split",
        "split_id": split_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "gate": "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "source_compare_id": collateral_compare.get("compare_id"),
        "raw_regression_rows": len(rows),
        "summary": {
            "status_counts": dict(status_counts),
            "search_status_counts": dict(search_counts),
            "tag_counts": dict(tag_counts),
            "primary_action_counts": dict(action_counts),
            "expected_fp_removal_rows": len(expected_rows),
            "intended_recovery_blind_judge_rows": len(blind_rows),
            "intended_recall_miss_rows": tag_counts.get("intended_recall_miss_recovery", 0),
            "intended_wrong_work_rows": tag_counts.get("intended_wrong_work_repair", 0),
            "search_degraded_or_recovered_overlay_rows": len(search_overlay_rows),
            "ok_search_non_fp_rows_before_blind_judge": len(ok_non_fp_rows),
            "true_triage_ok_search_nonfp_rows": len(true_triage_rows),
            "search_health_missing_rows": search_counts.get("MISSING", 0)
            + search_counts.get("RESULT_ROW_MISSING", 0),
        },
        "policy": {
            "expected_fp_removal_exempt": (
                "resolved_to_null rows that match detection survey false-positive labels are legitimate removals."
            ),
            "intended_recovery_requires_blind_judge": (
                "survey recall_miss and wrong_work repair rows need blind title-correctness confirmation before exemption/fix."
            ),
            "search_degraded_not_admissible": (
                "Rows with SEARCH_DEGRADED or SEARCH_DEGRADED_RECOVERED are held until search recovery rerun."
            ),
            "full375_rerun_requires_search_recovery_first": True,
        },
        "health_evidence": {
            "run_search_evidence": health_search,
            "search_shard_audit": {
                "path": (search_shard_audit or {}).get("_path"),
                "ok_count": (search_shard_audit or {}).get("ok_count"),
                "count": (search_shard_audit or {}).get("count"),
                "bad_shards": (search_shard_audit or {}).get("bad_shards"),
            }
            if search_shard_audit
            else None,
        },
        "rows": rows,
        "derived_sets": {
            "expected_fp_removal_post_ids": [row["post_id"] for row in expected_rows],
            "intended_recovery_blind_judge_post_ids": [row["post_id"] for row in blind_rows],
            "search_degraded_or_recovered_post_ids": [row["post_id"] for row in search_overlay_rows],
            "true_triage_ok_search_nonfp_post_ids": [row["post_id"] for row in true_triage_rows],
        },
    }
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    summary = report["summary"]
    derived = report["derived_sets"]
    source_compare_id = str(report.get("source_compare_id") or report["split_id"])
    row_search_health = (
        ((report.get("health_evidence") or {}).get("run_search_evidence") or {}).get("row_search_health")
        if isinstance((report.get("health_evidence") or {}).get("run_search_evidence"), dict)
        else None
    )
    degraded_total = (row_search_health or {}).get("degraded_total") if isinstance(row_search_health, dict) else None
    unrecovered_total = (
        (row_search_health or {}).get("unrecovered_degraded_total")
        if isinstance(row_search_health, dict)
        else None
    )
    search_boundary_line = (
        f"- `{source_compare_id}` health audit는 degraded query `{degraded_total}`, "
        f"unrecovered degraded `{unrecovered_total}`를 기록했다."
        if degraded_total is not None or unrecovered_total is not None
        else f"- `{source_compare_id}` 행 search health가 ok가 아닌 경우 collateral 변화는 회귀 판정 근거로 쓰지 않는다."
    )
    lines = [
        f"# {report['split_id']} raw regression survey/search-health 3분",
        "",
        "- gate: `REVIEW-LOCKED`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "- full_scan_approval: `false`",
        f"- raw regression rows: `{report['raw_regression_rows']}`",
        "",
        "## 3분 결과",
        "",
        f"- expected_fp_removal 회계 면제: `{summary['expected_fp_removal_rows']}`",
        (
            "- intended recovery blind-judge 대상: "
            f"`{summary['intended_recovery_blind_judge_rows']}` "
            f"(recall_miss `{summary['intended_recall_miss_rows']}`, "
            f"wrong_work `{summary['intended_wrong_work_rows']}`)"
        ),
        (
            "- search degraded/recovered overlay 보류: "
            f"`{summary['search_degraded_or_recovered_overlay_rows']}`"
        ),
        (
            "- ok-search & non-FP 후보: "
            f"`{summary['ok_search_non_fp_rows_before_blind_judge']}` "
            f"(blind-judge 의도 복구 제외 후 진짜 triage `{summary['true_triage_ok_search_nonfp_rows']}`)"
        ),
        f"- search health missing: `{summary['search_health_missing_rows']}`",
        "",
        "## 검색 선결",
        "",
        search_boundary_line,
        "- `SEARCH_DEGRADED` 또는 `SEARCH_DEGRADED_RECOVERED` 행의 collateral 변화는 회귀 판정 근거로 쓰지 않는다.",
        "- full375 재실행 전 검색 인프라 복구와 degraded/recovered 행 재실행이 선행이다.",
        "",
        "## Post IDs",
        "",
        "- expected_fp_removal: " + ", ".join(str(x) for x in derived["expected_fp_removal_post_ids"]),
        "- intended_recovery_blind_judge: "
        + ", ".join(str(x) for x in derived["intended_recovery_blind_judge_post_ids"]),
        "- true_triage_ok_search_nonfp: "
        + ", ".join(str(x) for x in derived["true_triage_ok_search_nonfp_post_ids"]),
        "",
        "## Gate 해석",
        "",
        (
            f"`{source_compare_id}` raw regression은 일괄 P0 triage 대상이 아니다. 먼저 survey FP 제거는 정당 제거로 "
            "회계 면제하고, 의도 복구 row는 제목 정답성 blind judge만 통과시키며, "
            "search health가 정상인 non-FP 잔여만 실제 triage 대상으로 다룬다."
        ),
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def write_subset_markdown(
    path: Path,
    *,
    title: str,
    rows: list[dict[str, Any]],
    description: str,
) -> None:
    lines = [
        f"# {title}",
        "",
        description,
        "",
        f"- rows: `{len(rows)}`",
        "- gate: `REVIEW-LOCKED`",
        "- full_scan_approval: `false`",
        "",
        "## Rows",
        "",
    ]
    for row in rows:
        lines.append(
            "- `{post_id}` `{status}` search=`{search}` before=`{before}` after=`{after}` "
            "survey=`{survey}` expected=`{expected}` post=`{post}`".format(
                post_id=row.get("post_id"),
                status=row.get("status"),
                search=row.get("search_status"),
                before=row.get("before_title"),
                after=row.get("after_title"),
                survey=row.get("survey_failure_class") or row.get("survey_disagreement_type"),
                expected=row.get("survey_correct_hypothesis"),
                post=row.get("post_title"),
            )
        )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Split collateral regressions by survey labels and row search health.")
    parser.add_argument("--collateral-compare", required=True, type=Path)
    parser.add_argument("--survey-errors", required=True, type=Path)
    parser.add_argument("--after-result", required=True, type=Path)
    parser.add_argument("--health-audit", type=Path, default=None)
    parser.add_argument("--search-shard-audit", type=Path, default=None)
    parser.add_argument("--split-id", default="collateral_survey_search_health_split")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--blind-judge-jsonl", type=Path, default=None)
    parser.add_argument("--search-deferred-jsonl", type=Path, default=None)
    parser.add_argument("--true-triage-jsonl", type=Path, default=None)
    parser.add_argument("--blind-judge-md", type=Path, default=None)
    parser.add_argument("--search-deferred-md", type=Path, default=None)
    parser.add_argument("--true-triage-md", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    search_shard_audit = load_json(args.search_shard_audit) if args.search_shard_audit else None
    if isinstance(search_shard_audit, dict) and args.search_shard_audit:
        search_shard_audit["_path"] = str(args.search_shard_audit)
    report = classify_rows(
        collateral_compare=load_json(args.collateral_compare),
        survey_errors=_survey_errors(args.survey_errors),
        after_rows=load_json_or_jsonl(args.after_result),
        split_id=args.split_id,
        health_audit=load_json(args.health_audit) if args.health_audit else None,
        search_shard_audit=search_shard_audit,
    )
    write_json(args.output_json, report)
    write_markdown(args.output_md, report)

    blind_rows = [row for row in report["rows"] if row["primary_action"] == "blind_judge_title_correctness"]
    search_rows = [row for row in report["rows"] if "search_health_deferred" in row.get("tags", [])]
    triage_rows = [row for row in report["rows"] if row["primary_action"] == "true_triage_ok_search_nonfp"]

    if args.blind_judge_jsonl:
        write_jsonl(
            args.blind_judge_jsonl,
            blind_rows,
        )
    if args.search_deferred_jsonl:
        write_jsonl(
            args.search_deferred_jsonl,
            search_rows,
        )
    if args.true_triage_jsonl:
        write_jsonl(
            args.true_triage_jsonl,
            triage_rows,
        )
    if args.blind_judge_md:
        write_subset_markdown(
            args.blind_judge_md,
            title=f"{args.split_id} intended recovery blind-judge batch",
            rows=blind_rows,
            description=(
                "Survey recall_miss/wrong_work 방향과 일치하는 복구 후보만 모은 batch다. "
                "judge는 제목 정답성만 확인하고, search-degraded overlay는 별도 검색 복구 gate에 남긴다."
            ),
        )
    if args.search_deferred_md:
        write_subset_markdown(
            args.search_deferred_md,
            title=f"{args.split_id} search degraded/recovered hold",
            rows=search_rows,
            description=(
                "Row search_health가 SEARCH_DEGRADED 또는 SEARCH_DEGRADED_RECOVERED인 raw regression이다. "
                "검색 복구 후 해당 행만 재실행하기 전까지 collateral regression evidence로 쓰지 않는다."
            ),
        )
    if args.true_triage_md:
        write_subset_markdown(
            args.true_triage_md,
            title=f"{args.split_id} true ok-search non-FP triage",
            rows=triage_rows,
            description=(
                "Search status가 ok이고 detection_survey FP 제거 또는 의도 복구 blind-judge 대상이 아닌 "
                "잔여 raw regression이다. 현재 기준 실제 triage 후보로 다룬다."
            ),
        )

    print(
        json.dumps(
            {
                "gate": report["gate"],
                "raw_regression_rows": report["raw_regression_rows"],
                **report["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
