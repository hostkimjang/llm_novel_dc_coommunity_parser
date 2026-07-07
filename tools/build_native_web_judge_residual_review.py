from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.codex_native_web_judge_ingest import all_verdicts


SOURCE_NATIVE_EXCLUDE = "exclude_from_regression_count_after_gate_wiring"


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _string(value: Any) -> str:
    return str(value or "").strip()


def _rows(payload: dict[str, Any], *, key: str = "rows") -> list[dict[str, Any]]:
    rows = payload.get(key)
    if not isinstance(rows, list):
        raise ValueError(f"payload must contain {key} list")
    return [row for row in rows if isinstance(row, dict)]


def _action_list(*values: str) -> list[str]:
    out: list[str] = []
    for value in values:
        if value and value not in out:
            out.append(value)
    return out


def _map_found_verdict(
    *,
    dispatch_row: dict[str, Any],
    verdict: dict[str, Any],
    judge_root: Path,
) -> dict[str, Any]:
    label = _string(verdict.get("resolution_label")) or "HOLD"
    disagreement = _string(verdict.get("disagreement_type")) or "none"
    likely = _string(verdict.get("likely_correct")) or "unknown"
    evidence = _string(verdict.get("search_evidence_grade")) or "Missing"
    independent_title = verdict.get("independent_official_title")
    independent_url = verdict.get("independent_url")
    pipeline_title = verdict.get("pipeline_official_title")
    pipeline_url = verdict.get("pipeline_url")

    if label == "ACCEPT" and likely == "pipeline" and disagreement == "none":
        actions = [SOURCE_NATIVE_EXCLUDE]
        source_native_verdict = (
            "codex_native_web_judge_pipeline_null_correct"
            if not pipeline_title and not independent_title
            else "codex_native_web_judge_pipeline_correct"
        )
        selected_title = pipeline_title if pipeline_title is not None else independent_title
        selected_url = pipeline_url if pipeline_url is not None else independent_url
    elif label == "REPROCESS":
        actions = _action_list(
            "native_web_judge_reprocess_required",
            "shared_promotion_gate_wiring_required" if independent_title and independent_url else "",
            "native_web_reverify_required" if evidence != "Strong" else "",
        )
        source_native_verdict = f"codex_native_web_judge_reprocess_{disagreement or 'review'}"
        selected_title = independent_title
        selected_url = independent_url
    elif label == "REJECT":
        actions = _action_list(
            "wrong_work_or_cross_media_policy_hold_required",
            "blind_or_policy_judge_required",
        )
        source_native_verdict = f"codex_native_web_judge_reject_{disagreement or 'review'}"
        selected_title = independent_title
        selected_url = independent_url
    elif label == "HOLD":
        actions = _action_list(
            "native_web_or_image_human_review_required",
            "official_detail_url_enrichment_required" if not independent_url and not pipeline_url else "",
        )
        source_native_verdict = f"codex_native_web_judge_hold_{disagreement or 'review'}"
        selected_title = independent_title if independent_title is not None else pipeline_title
        selected_url = independent_url if independent_url is not None else pipeline_url
    else:
        actions = ["native_web_or_image_human_review_required"]
        source_native_verdict = f"codex_native_web_judge_{label.lower() or 'review'}_{disagreement or 'review'}"
        selected_title = independent_title if independent_title is not None else pipeline_title
        selected_url = independent_url if independent_url is not None else pipeline_url

    return {
        "post_id": dispatch_row.get("post_id"),
        "triage_bucket": dispatch_row.get("triage_bucket"),
        "collateral_status": dispatch_row.get("collateral_status"),
        "post_title": dispatch_row.get("post_title"),
        "selected_option_id": "CODEX_NATIVE_WEB_JUDGE",
        "selected_title": selected_title,
        "selected_url": selected_url,
        "review_label": label,
        "source_native_verdict": source_native_verdict,
        "evidence_grade": evidence,
        "action": actions,
        "rationale_ko": verdict.get("korean_reason"),
        "evidence_refs": _action_list(
            f"{judge_root.as_posix()}/verdicts#post_id={dispatch_row.get('post_id')}",
            *[str(url) for url in verdict.get("source_urls") or []],
            *[str(ref) for ref in dispatch_row.get("evidence_refs") or []][:3],
        ),
        "codex_native_web_judge": {
            "resolution_label": label,
            "disagreement_type": disagreement,
            "likely_correct": likely,
            "recommended_action": verdict.get("recommended_action"),
            "independent_official_title": independent_title,
            "independent_url": independent_url,
            "pipeline_official_title": pipeline_title,
            "pipeline_url": pipeline_url,
        },
    }


def _map_missing_verdict(dispatch_row: dict[str, Any], judge_root: Path) -> dict[str, Any]:
    return {
        "post_id": dispatch_row.get("post_id"),
        "triage_bucket": dispatch_row.get("triage_bucket"),
        "collateral_status": dispatch_row.get("collateral_status"),
        "post_title": dispatch_row.get("post_title"),
        "selected_option_id": "HOLD",
        "selected_title": dispatch_row.get("selected_title"),
        "selected_url": dispatch_row.get("selected_url"),
        "review_label": "INFO_MISSING",
        "source_native_verdict": "codex_native_web_judge_missing_for_current_dispatch",
        "evidence_grade": "Missing",
        "action": ["native_web_or_image_evidence_required"],
        "rationale_ko": (
            "현재 residual dispatch에는 native-web/image evidence가 필요하지만, "
            "기존 Codex-native web judge 산출물에서 이 post_id 판정을 찾지 못했다. "
            "따라서 regression count 제외나 shared-gate publish 후보로 세지 않는다."
        ),
        "evidence_refs": _action_list(
            f"{judge_root.as_posix()}/verdicts#missing_post_id={dispatch_row.get('post_id')}",
            *[str(ref) for ref in dispatch_row.get("evidence_refs") or []][:3],
        ),
    }


def _copy_carry_rows(carry_reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for review in carry_reviews:
        review_id = review.get("review_id")
        for row in review.get("rows") or []:
            if not isinstance(row, dict):
                continue
            copied = dict(row)
            copied["carried_from_review_id"] = review_id
            rows.append(copied)
    return rows


def _summary(rows: list[dict[str, Any]], *, batch_review_rows: int) -> dict[str, Any]:
    label_counts = Counter(_string(row.get("review_label")) for row in rows)
    info_missing_rows = label_counts.get("INFO_MISSING", 0)
    action_counts: Counter[str] = Counter()
    bucket_counts = Counter(_string(row.get("triage_bucket")) for row in rows)
    verdict_counts = Counter(_string(row.get("source_native_verdict")) for row in rows)
    for row in rows:
        for action in row.get("action") or []:
            action_counts[_string(action)] += 1
    exclusion_candidates = action_counts.get(SOURCE_NATIVE_EXCLUDE, 0)
    return {
        "batch_review_rows": batch_review_rows,
        "reviewed_rows": len(rows),
        "source_native_decision_rows": max(len(rows) - info_missing_rows, 0),
        "info_missing_rows": info_missing_rows,
        "unreviewed_batch_rows": max(batch_review_rows - len(rows), 0),
        "unreviewed_or_info_missing_batch_rows": max(batch_review_rows - (len(rows) - info_missing_rows), 0),
        "validation_issue_count": 0,
        "counts_by_bucket": dict(bucket_counts),
        "label_counts": dict(label_counts),
        "source_native_verdict_counts": dict(verdict_counts),
        "action_counts": dict(action_counts),
        "queue_transition": {
            "original_p0_rows": batch_review_rows,
            "source_native_reviewed_rows": len(rows),
            "source_native_decision_rows": max(len(rows) - info_missing_rows, 0),
            "info_missing_rows": info_missing_rows,
            "exclusion_candidate_rows": exclusion_candidates,
            "repair_required_rows": label_counts.get("REPROCESS", 0),
            "policy_or_native_review_required_rows": label_counts.get("HOLD", 0)
            + label_counts.get("REJECT", 0),
            "residual_action_queue_rows": max(batch_review_rows - exclusion_candidates, 0),
            "validation_issue_count": 0,
            "full_collateral_approval_open": False,
            "exclusion_requires_gate_wiring": exclusion_candidates > 0,
        },
    }


def build_review(
    *,
    dispatch: dict[str, Any],
    judge_root: Path,
    carry_reviews: list[dict[str, Any]],
    review_id: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    dispatch_rows = _rows(dispatch)
    verdict_by_post_id = {row["post_id"]: row for row in all_verdicts(judge_root)}
    rows = _copy_carry_rows(carry_reviews)
    found_post_ids: list[int] = []
    missing_post_ids: list[int] = []

    for dispatch_row in dispatch_rows:
        post_id = dispatch_row.get("post_id")
        verdict = verdict_by_post_id.get(post_id)
        if verdict is None:
            missing_post_ids.append(post_id)
            rows.append(_map_missing_verdict(dispatch_row, judge_root))
        else:
            found_post_ids.append(post_id)
            rows.append(_map_found_verdict(dispatch_row=dispatch_row, verdict=verdict, judge_root=judge_root))

    batch_review_rows = len(rows)
    return {
        "report_type": "native_web_judge_residual_source_native_review",
        "review_id": review_id,
        "scope": "residual46 native-web/image evidence batch with carried source-native exclusions",
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_dispatch": dispatch.get("dispatch_id") or dispatch.get("queue_id"),
        "source_judge_root": str(judge_root),
        "source_carry_review_ids": [review.get("review_id") for review in carry_reviews],
        "gate": "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            **_summary(rows, batch_review_rows=batch_review_rows),
            "dispatch_rows": len(dispatch_rows),
            "carried_rows": sum(len(review.get("rows") or []) for review in carry_reviews),
            "codex_native_web_found_rows": len(found_post_ids),
            "codex_native_web_missing_rows": len(missing_post_ids),
            "found_post_ids": found_post_ids,
            "missing_post_ids": missing_post_ids,
        },
        "validation_issues": [],
        "rows": rows,
        "approval_boundary": {
            "accept_rows_are_exclusion_candidates_not_approval": True,
            "reprocess_rows_require_shared_promotion_gate_before_publish": True,
            "hold_reject_info_missing_rows_do_not_reduce_ordinary_queue": True,
            "full375_collateral_go_required": True,
            "semantic_quality_remains_review_locked": True,
            "full_scan_approval": False,
        },
    }


def write_markdown(path: Path, review: dict[str, Any]) -> None:
    summary = review["summary"]
    lines = [
        f"# {review['review_id']}",
        "",
        "Loop593 remaining residual 18건에 기존 Codex-native web judge 산출물을 결합한 batch 검토다. "
        "이 문서는 새 runtime replay나 full375 GO가 아니며, `ACCEPT`는 regression count 제외 후보일 뿐 approval이 아니다.",
        "",
        "## 요약",
        "",
        f"- gate: `{review['gate']}`",
        f"- semantic_quality: `{review['semantic_quality']}`",
        f"- full_scan_approval: `{str(review['full_scan_approval']).lower()}`",
        f"- dispatch rows: `{summary['dispatch_rows']}`",
        f"- carried rows: `{summary['carried_rows']}`",
        f"- codex-native found/missing: `{summary['codex_native_web_found_rows']}/{summary['codex_native_web_missing_rows']}`",
        f"- reviewed rows: `{summary['reviewed_rows']}`",
        f"- source-native decision rows: `{summary['source_native_decision_rows']}`",
        f"- info missing rows: `{summary['info_missing_rows']}`",
        f"- exclusion candidates: `{summary['queue_transition']['exclusion_candidate_rows']}`",
        f"- residual action queue rows after exclusion candidates: `{summary['queue_transition']['residual_action_queue_rows']}`",
        "",
        "## 라벨 집계",
        "",
    ]
    for label, count in sorted(summary["label_counts"].items()):
        lines.append(f"- `{label}`: `{count}`")
    lines.extend(["", "## Action 집계", ""])
    for action, count in sorted(summary["action_counts"].items()):
        lines.append(f"- `{action}`: `{count}`")
    lines.extend(["", "## Codex-native judge 누락 post_id", ""])
    lines.append("- " + ", ".join(f"`{pid}`" for pid in summary["missing_post_ids"]))
    lines.extend(["", "## 행별 판정", ""])
    for row in review["rows"]:
        actions = ", ".join(row.get("action") or [])
        lines.append(
            "- "
            f"`{row.get('post_id')}` `{row.get('review_label')}` "
            f"`{row.get('source_native_verdict')}` selected=`{row.get('selected_title')}` action=`{actions}`"
        )
        lines.append(f"  - 근거: {row.get('rationale_ko')}")
    lines.extend(
        [
            "",
            "## Gate 해석",
            "",
            "`REPROCESS` 행은 shared promotion gate와 공식 detail URL 검증을 통과하기 전 publish 후보로 줄이지 않는다. "
            "`HOLD`, `REJECT`, `INFO_MISSING` 행은 native-web/image 또는 policy 검토가 더 필요하므로 ordinary residual에 남긴다. "
            "full375 collateral `GO`와 full_scan 경로가 정의되기 전까지 `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build residual review from Codex-native web judge verdicts.")
    parser.add_argument("--dispatch", required=True, type=Path)
    parser.add_argument("--judge-root", required=True, type=Path)
    parser.add_argument("--carry-review", action="append", default=[], type=Path)
    parser.add_argument("--review-id", required=True)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    review = build_review(
        dispatch=load_json(args.dispatch),
        judge_root=args.judge_root,
        carry_reviews=[load_json(path) for path in args.carry_review],
        review_id=args.review_id,
    )
    write_json(args.output_json, review)
    write_markdown(args.output_md, review)
    print(json.dumps({"gate": review["gate"], "summary": review["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
