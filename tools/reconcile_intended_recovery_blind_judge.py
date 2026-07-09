from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            if not line.strip():
                continue
            rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _norm_title(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace(" ", "")
    text = re.sub(r"[\[\]〈〉<>「」『』()（）:：,，.!?~\-_/|·]", "", text)
    return text.casefold()


def _verdict_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for key in ("rows", "verdicts", "review_verdicts", "source_verdicts"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def _post_id(row: dict[str, Any]) -> int | None:
    raw = row.get("post_id")
    if raw is None and isinstance(row.get("source_native_packet"), dict):
        raw = row["source_native_packet"].get("post_id")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _selected_title(row: dict[str, Any]) -> str | None:
    for key in ("selected_title", "official_title", "title"):
        value = row.get(key)
        if value:
            return str(value)
    return None


def _selected_url(row: dict[str, Any]) -> str | None:
    for key in ("selected_url", "heretic_url", "official_url"):
        value = row.get(key)
        if value:
            return str(value)
    return None


def _latest_prior_verdicts(paths: list[Path]) -> dict[int, dict[str, Any]]:
    indexed: dict[int, dict[str, Any]] = {}
    for path in sorted(paths, key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            payload = _load_json(path)
        except Exception:
            continue
        for row in _verdict_rows(payload):
            post_id = _post_id(row)
            if post_id is None or post_id in indexed:
                continue
            indexed[post_id] = {"path": path.as_posix(), "row": row}
    return indexed


def _judge_status(target: dict[str, Any], prior: dict[str, Any] | None) -> str:
    if target.get("search_status") not in (None, "", "ok"):
        return "search_health_hold"
    if prior is None:
        return "needs_new_blind_judge"
    row = prior["row"]
    if str(row.get("review_label") or "").upper() not in {"ACCEPT", "HOLD", "REJECT"}:
        return "prior_verdict_unusable"
    selected = _selected_title(row)
    after = target.get("after_title")
    expected = target.get("survey_correct_hypothesis")
    if str(row.get("review_label") or "").upper() == "ACCEPT":
        selected_norm = _norm_title(selected)
        if selected_norm and selected_norm == _norm_title(after):
            return "prior_blind_judge_accept_after_title"
        if selected_norm and selected_norm and selected_norm in _norm_title(expected):
            return "prior_blind_judge_accept_expected_but_after_differs"
        return "prior_blind_judge_disagrees_with_after"
    if str(row.get("review_label") or "").upper() == "HOLD":
        return "prior_blind_judge_hold"
    return "prior_blind_judge_reject"


def _markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"# {report['review_id']} intended recovery blind judge 대조",
        "",
        f"- gate: `{report['gate']}`",
        f"- semantic_quality: `{report['semantic_quality']}`",
        f"- full_scan_approval: `{str(report['full_scan_approval']).lower()}`",
        f"- 입력 행: `{summary['target_rows']}`",
        f"- prior verdict covered: `{summary['prior_verdict_covered']}`",
        f"- after title ACCEPT: `{summary['after_title_accept']}`",
        f"- expected는 맞지만 after_title 다름: `{summary['expected_accept_after_differs']}`",
        f"- prior disagreement/hold/reject: `{summary['prior_disagree_or_hold_or_reject']}`",
        f"- 새 blind judge 필요: `{summary['needs_new_blind_judge']}`",
        f"- search health 보류: `{summary['search_health_hold']}`",
        "",
        "## 판정 행",
        "",
    ]
    for row in report["rows"]:
        lines.append(
            "- "
            f"`{row['post_id']}` `{row['status']}` search=`{row['search_status']}` "
            f"after=`{row.get('after_title')}` selected=`{row.get('prior_selected_title')}` "
            f"expected=`{row.get('survey_correct_hypothesis')}` source=`{row.get('prior_verdict_path')}`"
        )
    lines.extend(
        [
            "",
            "## Gate 해석",
            "",
            "이 산출물은 intended recovery 28건을 기존 source-native/blind verdict와 대조한 회계 자료다. "
            "`prior_blind_judge_accept_after_title`만 회계 면제 후보로 볼 수 있고, "
            "`prior_blind_judge_accept_expected_but_after_differs`와 disagreement/hold/reject는 수정 또는 새 judge가 필요하다. "
            "search health가 ok가 아닌 행은 검색 복구 후 재실행 전까지 회귀 판정 근거로 쓰지 않는다.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile intended recovery rows with prior source-native blind verdicts.")
    parser.add_argument("--targets", required=True, type=Path)
    parser.add_argument("--prior-glob", action="append", default=[])
    parser.add_argument("--review-id", required=True)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    args = parser.parse_args()

    target_rows = _load_jsonl(args.targets)
    prior_paths: list[Path] = []
    for pattern in args.prior_glob:
        prior_paths.extend(Path().glob(pattern))
    prior = _latest_prior_verdicts(prior_paths)

    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for target in target_rows:
        post_id = int(target["post_id"])
        prior_item = prior.get(post_id)
        status = _judge_status(target, prior_item)
        counts[status] = counts.get(status, 0) + 1
        prior_row = prior_item["row"] if prior_item else {}
        rows.append(
            {
                "post_id": post_id,
                "status": status,
                "search_status": target.get("search_status"),
                "collateral_status": target.get("status"),
                "after_title": target.get("after_title"),
                "before_title": target.get("before_title"),
                "survey_failure_class": target.get("survey_failure_class"),
                "survey_correct_hypothesis": target.get("survey_correct_hypothesis"),
                "post_title": target.get("post_title"),
                "prior_verdict_path": prior_item["path"] if prior_item else None,
                "prior_review_label": prior_row.get("review_label"),
                "prior_selected_title": _selected_title(prior_row),
                "prior_selected_url": _selected_url(prior_row),
                "prior_evidence_grade": prior_row.get("evidence_grade"),
                "prior_rationale_ko": prior_row.get("rationale_ko"),
            }
        )

    summary = {
        "target_rows": len(target_rows),
        "prior_verdict_covered": sum(1 for row in rows if row.get("prior_verdict_path")),
        "after_title_accept": counts.get("prior_blind_judge_accept_after_title", 0),
        "expected_accept_after_differs": counts.get("prior_blind_judge_accept_expected_but_after_differs", 0),
        "prior_disagree_or_hold_or_reject": sum(
            counts.get(key, 0)
            for key in (
                "prior_blind_judge_disagrees_with_after",
                "prior_blind_judge_hold",
                "prior_blind_judge_reject",
                "prior_verdict_unusable",
            )
        ),
        "needs_new_blind_judge": counts.get("needs_new_blind_judge", 0),
        "search_health_hold": counts.get("search_health_hold", 0),
        "status_counts": counts,
    }
    report = {
        "review_id": args.review_id,
        "gate": "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": summary,
        "rows": rows,
    }
    _write_json(args.output_json, report)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(_markdown(report), encoding="utf-8", newline="\n")
    print(json.dumps({"gate": report["gate"], "summary": summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
