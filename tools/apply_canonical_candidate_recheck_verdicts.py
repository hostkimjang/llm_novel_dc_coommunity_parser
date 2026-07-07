from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


EVIDENCE_GRADES = {"Strong", "Medium", "Weak", "Missing"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _string(value: Any) -> str:
    return str(value or "").strip()


def _batch_rows_by_post_id(batch: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows = batch.get("rows")
    if not isinstance(rows, list):
        raise ValueError("canonical recheck batch JSON must contain rows list")
    indexed: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        post_id = row.get("post_id")
        if isinstance(post_id, int):
            indexed[post_id] = row
    return indexed


def _verdict_rows(verdicts: dict[str, Any] | None) -> list[dict[str, Any]]:
    if verdicts is None:
        return []
    rows = verdicts.get("rows")
    if rows is None:
        return []
    if not isinstance(rows, list):
        raise ValueError("verdict JSON rows must be a list")
    return [row for row in rows if isinstance(row, dict)]


def _evidence_grade(row: dict[str, Any]) -> str:
    return _string(row.get("evidence_grade") or row.get("evidence_strength"))


def _canonical_title(row: dict[str, Any], batch_row: dict[str, Any], verdict: str) -> Any:
    explicit = row.get("canonical_title")
    if _string(explicit):
        return explicit
    if verdict == "EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED":
        return batch_row.get("expected_or_source_native_title")
    if verdict == "CURRENT_PROJECTION_CANDIDATE_CONFIRMED":
        return batch_row.get("current_projection_candidate_title")
    return explicit


def _canonical_url(row: dict[str, Any], batch_row: dict[str, Any], verdict: str) -> Any:
    explicit = row.get("canonical_url")
    if _string(explicit):
        return explicit
    if verdict == "CURRENT_PROJECTION_CANDIDATE_CONFIRMED":
        return batch_row.get("current_projection_candidate_url")
    return explicit


def _validate_verdict_row(row: dict[str, Any], batch_row: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    verdict = _string(row.get("canonical_verdict"))
    allowed = {_string(item) for item in batch_row.get("allowed_verdicts") or [] if _string(item)}
    if not verdict:
        issues.append("missing_canonical_verdict")
    elif verdict not in allowed:
        issues.append("canonical_verdict_not_allowed_for_batch_row")

    grade = _evidence_grade(row)
    if not grade:
        issues.append("missing_evidence_grade")
    elif grade not in EVIDENCE_GRADES:
        issues.append("invalid_evidence_grade")

    if not _string(row.get("rationale_ko")):
        issues.append("missing_rationale_ko")
    refs = row.get("evidence_refs")
    if not isinstance(refs, list) or not refs:
        issues.append("missing_evidence_refs")

    if verdict == "RELATED_CANONICAL_VARIANT_CONFIRMED" and not _string(row.get("canonical_title")):
        issues.append("missing_canonical_title_for_related_variant")
    return issues


def _contract_for(batch_row: dict[str, Any], verdict: str) -> dict[str, Any]:
    contract = batch_row.get("after_verdict_contract")
    if not isinstance(contract, dict):
        return {}
    value = contract.get(verdict)
    return value if isinstance(value, dict) else {}


def _runtime_release_gate(batch_row: dict[str, Any]) -> str:
    contract = batch_row.get("after_verdict_contract")
    if isinstance(contract, dict):
        return _string(contract.get("current_runtime_release_gate"))
    return ""


def build_verdict_template(
    *,
    batch: dict[str, Any],
    batch_path: Path,
    review_id: str,
    scope: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    rows = list(_batch_rows_by_post_id(batch).values())
    return {
        "review_id": review_id,
        "scope": scope,
        "report_type": "canonical_candidate_recheck_verdict_template",
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_batch": str(batch_path),
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "instructions_ko": [
            "각 row의 canonical_verdict를 allowed_verdicts 중 하나로 채운다.",
            "판정 근거는 evidence_grade, rationale_ko, evidence_refs에 남긴다.",
            "RELATED_CANONICAL_VARIANT_CONFIRMED는 canonical_title을 반드시 채운다.",
            "이 template 자체는 verdict가 아니며 runtime replay나 approval을 열지 않는다.",
        ],
        "summary": {
            "template_rows": len(rows),
            "runtime_replay_allowed_rows": 0,
            "full375_collateral_gate": "NO-GO",
        },
        "rows": [
            {
                "post_id": row.get("post_id"),
                "review_lane": row.get("review_lane"),
                "expected_or_source_native_title": row.get("expected_or_source_native_title"),
                "current_projection_candidate_title": row.get("current_projection_candidate_title"),
                "current_projection_candidate_url": row.get("current_projection_candidate_url"),
                "candidate_support_state": row.get("candidate_support_state"),
                "search_gate": row.get("search_gate"),
                "allowed_verdicts": row.get("allowed_verdicts") or [],
                "canonical_verdict": "",
                "canonical_title": "",
                "canonical_url": "",
                "evidence_grade": "",
                "rationale_ko": "",
                "evidence_refs": [],
            }
            for row in rows
        ],
    }


def build_application_summary(
    *,
    batch: dict[str, Any],
    batch_path: Path,
    verdicts: dict[str, Any] | None = None,
    verdict_path: Path | None = None,
    review_id: str = "canonical_candidate_recheck_verdict_application",
    scope: str = "canonical candidate recheck verdict application",
    generated_at: str | None = None,
) -> dict[str, Any]:
    indexed = _batch_rows_by_post_id(batch)
    rows = _verdict_rows(verdicts)
    out_rows: list[dict[str, Any]] = []
    validation_issues: list[dict[str, Any]] = []
    seen_post_ids: set[int] = set()

    for row in rows:
        post_id = row.get("post_id")
        if not isinstance(post_id, int):
            validation_issues.append({"post_id": post_id, "issues": ["invalid_post_id"]})
            continue
        if post_id in seen_post_ids:
            validation_issues.append({"post_id": post_id, "issues": ["duplicate_verdict_post_id"]})
            continue
        seen_post_ids.add(post_id)
        batch_row = indexed.get(post_id)
        if batch_row is None:
            validation_issues.append({"post_id": post_id, "issues": ["post_id_not_in_canonical_batch"]})
            continue

        verdict = _string(row.get("canonical_verdict"))
        issues = _validate_verdict_row(row, batch_row)
        if issues:
            validation_issues.append({"post_id": post_id, "issues": issues})
        contract = _contract_for(batch_row, verdict)
        out_rows.append(
            {
                "post_id": post_id,
                "review_lane": batch_row.get("review_lane"),
                "canonical_verdict": verdict,
                "evidence_grade": _evidence_grade(row),
                "canonical_title": _canonical_title(row, batch_row, verdict),
                "canonical_url": _canonical_url(row, batch_row, verdict),
                "expected_or_source_native_title": batch_row.get("expected_or_source_native_title"),
                "current_projection_candidate_title": batch_row.get("current_projection_candidate_title"),
                "current_projection_candidate_url": batch_row.get("current_projection_candidate_url"),
                "candidate_support_state": batch_row.get("candidate_support_state"),
                "search_gate": batch_row.get("search_gate"),
                "primary_repair_lane": batch_row.get("primary_repair_lane"),
                "post_verdict_next_state": contract.get("next_state"),
                "runtime_release_condition": contract.get("runtime_release"),
                "current_runtime_release_gate": _runtime_release_gate(batch_row),
                "runtime_replay_allowed_after_verdict": False,
                "contract_test_required_before_runtime": True,
                "rationale_ko": row.get("rationale_ko"),
                "evidence_refs": row.get("evidence_refs") or [],
                "row_validation_issues": issues,
            }
        )

    reviewed_post_ids = {
        row.get("post_id")
        for row in out_rows
        if isinstance(row.get("post_id"), int)
    }
    unreviewed_post_ids = sorted(set(indexed) - reviewed_post_ids)
    verdict_counts = Counter(_string(row.get("canonical_verdict")) for row in out_rows)
    next_state_counts = Counter(_string(row.get("post_verdict_next_state")) for row in out_rows)
    release_counts = Counter(_string(row.get("runtime_release_condition")) for row in out_rows)
    review_lane_counts = Counter(_string(row.get("review_lane")) for row in out_rows)
    search_gate_counts = Counter(_string(row.get("search_gate")) for row in out_rows)

    gate = "NO-GO" if validation_issues else "REVIEW-LOCKED"
    return {
        "report_type": "canonical_candidate_recheck_verdict_application",
        "review_id": review_id,
        "scope": scope,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_batch": str(batch_path),
        "source_verdicts": str(verdict_path) if verdict_path else None,
        "gate": gate,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "batch_rows": len(indexed),
            "verdict_rows": len(rows),
            "reviewed_rows": len(out_rows),
            "accepted_verdict_rows": sum(1 for row in out_rows if not row.get("row_validation_issues")),
            "unreviewed_batch_rows": len(unreviewed_post_ids),
            "validation_issue_count": len(validation_issues),
            "canonical_verdict_counts": dict(verdict_counts),
            "post_verdict_next_state_counts": dict(next_state_counts),
            "runtime_release_condition_counts": dict(release_counts),
            "review_lane_counts": dict(review_lane_counts),
            "search_gate_counts": dict(search_gate_counts),
            "runtime_replay_allowed_rows": 0,
            "contract_test_required_rows": len(out_rows),
            "full375_collateral_gate": "NO-GO",
            "completion_gate": "full375 collateral GO + full_scan path",
        },
        "validation_issues": validation_issues,
        "unreviewed_post_ids": unreviewed_post_ids,
        "rows": out_rows,
        "next_actions": [
            "canonical verdict가 비어 있는 row는 source-native/blind 검토를 먼저 완료한다.",
            "유효한 verdict row도 contract test 통과 전에는 runtime replay 후보로 돌리지 않는다.",
            "runtime replay 뒤에도 full375 collateral GO 전에는 full_scan approval을 열지 않는다.",
            "semantic_quality=REVIEW-LOCKED, full_scan_approval=false를 유지한다.",
        ],
    }


def write_application_markdown(path: Path, summary: dict[str, Any]) -> None:
    counts = summary["summary"]
    lines = [
        f"# {summary.get('scope') or summary.get('review_id')}",
        "",
        "이 보고서는 canonical candidate recheck verdict를 gate/action queue로 전환하는 적용 결과다. "
        "verdict 자체가 없거나 계약 테스트가 닫히지 않으면 runtime replay와 approval은 열리지 않는다.",
        "",
        "## 요약",
        "",
        f"- gate: `{summary['gate']}`",
        f"- semantic_quality: `{summary['semantic_quality']}`",
        f"- full_scan_approval: `{str(summary['full_scan_approval']).lower()}`",
        f"- source batch: `{summary['source_batch']}`",
        f"- source verdicts: `{summary.get('source_verdicts')}`",
        f"- batch rows: `{counts['batch_rows']}`",
        f"- verdict rows: `{counts['verdict_rows']}`",
        f"- reviewed rows: `{counts['reviewed_rows']}`",
        f"- accepted verdict rows: `{counts['accepted_verdict_rows']}`",
        f"- unreviewed batch rows: `{counts['unreviewed_batch_rows']}`",
        f"- validation issues: `{counts['validation_issue_count']}`",
        f"- runtime_replay_allowed_rows: `{counts['runtime_replay_allowed_rows']}`",
        f"- full375 collateral: `{counts['full375_collateral_gate']}`",
        f"- completion gate: `{counts['completion_gate']}`",
        "",
        "## Verdict 집계",
        "",
    ]
    verdict_counts = counts.get("canonical_verdict_counts") or {}
    if verdict_counts:
        for verdict, count in sorted(verdict_counts.items()):
            lines.append(f"- `{verdict}`: `{count}`")
    else:
        lines.append("- 아직 적용된 canonical verdict가 없다.")

    lines.extend(["", "## 다음 상태 집계", ""])
    next_state_counts = counts.get("post_verdict_next_state_counts") or {}
    if next_state_counts:
        for state, count in sorted(next_state_counts.items()):
            lines.append(f"- `{state}`: `{count}`")
    else:
        lines.append("- 아직 contract action으로 전환된 row가 없다.")

    if summary.get("unreviewed_post_ids"):
        lines.extend(["", "## 미판정 post_id", ""])
        lines.append(", ".join(f"`{post_id}`" for post_id in summary["unreviewed_post_ids"]))

    if summary.get("validation_issues"):
        lines.extend(["", "## Validation Issues", ""])
        for issue in summary["validation_issues"]:
            lines.append(f"- `{issue.get('post_id')}`: `{', '.join(issue.get('issues') or [])}`")

    if summary.get("rows"):
        lines.extend(["", "## 행별 적용", ""])
        for row in summary["rows"]:
            lines.append(
                "- "
                f"`{row['post_id']}` verdict=`{row['canonical_verdict']}` "
                f"next=`{row.get('post_verdict_next_state')}` "
                f"runtime_release=`{row.get('runtime_release_condition')}`"
            )
            lines.append(f"  - 근거: {row.get('rationale_ko')}")

    lines.extend(
        [
            "",
            "## Gate 해석",
            "",
            "이 회차는 residual 단건 replay가 아니라 verdict 적용 경로의 계약화다. "
            "canonical verdict와 후속 contract test가 닫히기 전에는 B1 row를 runtime replay로 되돌리지 않는다. "
            "full375 collateral은 계속 `NO-GO`이고 goal은 `ACTIVE / NOT_COMPLETE`다.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def write_template_markdown(path: Path, template: dict[str, Any]) -> None:
    lines = [
        f"# {template.get('scope') or template.get('review_id')}",
        "",
        "이 파일은 canonical verdict 작성용 template이다. 자체로는 verdict, replay 허가, approval 근거가 아니다.",
        "",
        f"- source batch: `{template['source_batch']}`",
        f"- template rows: `{template['summary']['template_rows']}`",
        f"- runtime_replay_allowed_rows: `{template['summary']['runtime_replay_allowed_rows']}`",
        f"- full375 collateral: `{template['summary']['full375_collateral_gate']}`",
        "",
        "## Rows",
        "",
    ]
    for row in template["rows"]:
        allowed = ", ".join(row.get("allowed_verdicts") or [])
        lines.append(
            "- "
            f"`{row['post_id']}` lane=`{row.get('review_lane')}` "
            f"expected=`{row.get('expected_or_source_native_title')}` "
            f"candidate=`{row.get('current_projection_candidate_title')}`"
        )
        lines.append(f"  - allowed: {allowed}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply canonical candidate recheck verdicts to the runtime release gate.")
    parser.add_argument("--batch", required=True, type=Path)
    parser.add_argument("--verdicts", type=Path, default=None)
    parser.add_argument("--review-id", default="loop529_b1_canonical_verdict_application")
    parser.add_argument("--scope", default="Loop529 B1 canonical verdict application")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--output-template-json", type=Path, default=None)
    parser.add_argument("--output-template-md", type=Path, default=None)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    batch = load_json(args.batch)
    verdicts = load_json(args.verdicts) if args.verdicts else None
    generated_at = datetime.now().replace(microsecond=0).isoformat()
    summary = build_application_summary(
        batch=batch,
        batch_path=args.batch,
        verdicts=verdicts,
        verdict_path=args.verdicts,
        review_id=args.review_id,
        scope=args.scope,
        generated_at=generated_at,
    )
    write_json(args.output_json, summary)
    write_application_markdown(args.output_md, summary)

    if args.output_template_json or args.output_template_md:
        template = build_verdict_template(
            batch=batch,
            batch_path=args.batch,
            review_id=f"{args.review_id}_template",
            scope=f"{args.scope} verdict template",
            generated_at=generated_at,
        )
        if args.output_template_json:
            write_json(args.output_template_json, template)
        if args.output_template_md:
            write_template_markdown(args.output_template_md, template)

    print(json.dumps({"gate": summary["gate"], "summary": summary["summary"]}, ensure_ascii=False, indent=2))
    if args.fail_on_validation_issue and summary["validation_issues"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
