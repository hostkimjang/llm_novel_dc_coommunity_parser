from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


DEFAULT_RUN_ID = "20260531_221116_642030"
DEFAULT_PREFIX = "v431_targeted_followup_remaining"

REVIEW_ONLY_ACTIONS = {
    "comment_author_match_unverified_resolution_review_only": {
        "action": "human_review",
        "priority": "P1",
        "close_condition": "댓글 author 미확정 신호가 final title의 필수 근거가 아님을 packet에서 확인한다.",
    },
    "search_only_resolved_title_review_only": {
        "action": "human_review",
        "priority": "P1",
        "close_condition": "원문 title/alias와 official/platform evidence가 같은 final title을 직접 지지함을 확인한다.",
    },
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"Expected JSON object at {path}:{line_no}")
        rows.append(payload)
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def result_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("results", "rows", "items", "data"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    raise ValueError("Expected result JSON list or object containing results/rows/items/data")


def post_key(value: Any) -> str:
    return str(value).strip()


def body_excerpt(row: dict[str, Any], limit: int = 500) -> str:
    values: list[str] = []
    content = row.get("content")
    if isinstance(content, list):
        values.extend(str(item).strip() for item in content if str(item).strip())
    elif content:
        values.append(str(content).strip())
    blocks = row.get("content_blocks")
    if isinstance(blocks, list) and not values:
        for block in blocks:
            if isinstance(block, dict):
                if str(block.get("type") or "").lower() == "image":
                    continue
                text = block.get("text") or block.get("content")
            else:
                text = block
            if text:
                values.append(str(text).strip())
    text = " / ".join(values[:6])
    return text[: limit - 3].rstrip() + "..." if len(text) > limit else text


def comment_excerpt(row: dict[str, Any], limit: int = 500) -> str:
    comments = row.get("comments") or row.get("comments_raw") or []
    if not isinstance(comments, list):
        comments = [comments]
    values: list[str] = []
    for item in comments[:10]:
        if isinstance(item, dict):
            text = item.get("content") or item.get("text")
            author = item.get("author")
            if author and text:
                text = f"{author}: {text}"
        else:
            text = item
        if text:
            values.append(str(text).strip())
    text = " | ".join(values)
    return text[: limit - 3].rstrip() + "..." if len(text) > limit else text


def identity(row: dict[str, Any]) -> dict[str, Any]:
    analysis = row.get("analysis_result")
    if not isinstance(analysis, dict):
        return {}
    value = analysis.get("identity")
    return value if isinstance(value, dict) else {}


def _false_like(value: Any) -> bool:
    if value is False:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"false", "0", "no"}
    return False


def _promotion_blocked(ident: dict[str, Any]) -> bool:
    status = str(ident.get("candidate_ledger_status") or "").strip().lower()
    if status in {"promotion_blocked", "blocked", "hold_without_promotion"}:
        return True
    return _false_like(ident.get("title_resolution_allowed"))


def _primary_work_is_promoted(primary: dict[str, Any]) -> bool:
    blocked = primary.get("blocked_by_candidate_audit")
    if blocked is True or (isinstance(blocked, str) and blocked.strip().lower() == "true"):
        return False
    policy = str(primary.get("promotion_policy") or "").strip().lower()
    if policy in {"hold_without_promotion", "promotion_blocked", "candidate_only"}:
        return False
    role = str(primary.get("reference_role") or "").strip().lower()
    if role in {"candidate", "mentioned", "secondary", "reference"}:
        return False
    return True


def resolved_title(row: dict[str, Any]) -> Any:
    ident = identity(row)
    if _promotion_blocked(ident):
        return None
    novel = ident.get("novel_identity")
    if isinstance(novel, dict) and novel.get("official_title"):
        return novel.get("official_title")
    primary = ident.get("primary_work")
    if (
        isinstance(primary, dict)
        and primary.get("official_title")
        and _primary_work_is_promoted(primary)
    ):
        return primary.get("official_title")
    return None


def final_decision_fields(row: dict[str, Any]) -> dict[str, Any]:
    ident = identity(row)
    novel = ident.get("novel_identity") if isinstance(ident.get("novel_identity"), dict) else {}
    return {
        "is_relevant": ident.get("is_relevant"),
        "resolved_title": resolved_title(row),
        "confidence": novel.get("confidence"),
        "work_resolution": ident.get("work_resolution"),
        "discussion_type": ident.get("discussion_type"),
        "topicality": ident.get("topicality"),
        "title_resolution_state": ident.get("title_resolution_state"),
        "title_resolution_allowed": ident.get("title_resolution_allowed"),
        "anchor_type": ident.get("anchor_type"),
        "anchor_strength": ident.get("anchor_strength"),
    }


def summarize_evidence(row: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    catalog = identity(row).get("search_evidence_catalog") or []
    if not isinstance(catalog, list):
        return []
    out: list[dict[str, Any]] = []
    for item in catalog[:limit]:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "eid": item.get("eid"),
                "title": item.get("title"),
                "url": item.get("url"),
                "domain": item.get("domain"),
                "purpose": item.get("purpose"),
                "source_tier": item.get("source_tier"),
                "snippet": item.get("snippet"),
            }
        )
    return out


def summarize_image_evidence(row: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    catalog = identity(row).get("image_evidence_catalog") or []
    if not isinstance(catalog, list):
        return []
    out: list[dict[str, Any]] = []
    for item in catalog[:limit]:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "eid": item.get("eid"),
                "source_url": item.get("source_url"),
                "evidence_type": item.get("evidence_type"),
                "title_role": item.get("title_role"),
                "promotion_eligible": item.get("promotion_eligible"),
                "visual_summary": item.get("visual_summary"),
            }
        )
    return out


def source_packet(row: dict[str, Any], queue_item: dict[str, Any], result_path: Path) -> dict[str, Any]:
    ident = identity(row)
    return {
        "queue_id": queue_item["queue_id"],
        "queue_type": queue_item["queue_type"],
        "post_id": row.get("post_id"),
        "source_result_path": result_path.as_posix(),
        "url": row.get("url"),
        "gallery_id": row.get("gallery_id"),
        "title": row.get("title"),
        "body_excerpt": body_excerpt(row),
        "comment_excerpt": comment_excerpt(row),
        "comment_metadata": row.get("comment_metadata") if isinstance(row.get("comment_metadata"), list) else [],
        "comment_dialogue_context_lines": row.get("comment_dialogue_context_lines")
        if isinstance(row.get("comment_dialogue_context_lines"), list)
        else [],
        "image_urls": row.get("image_urls") if isinstance(row.get("image_urls"), list) else [],
        "image_count": row.get("image_count"),
        "final_decision_fields": final_decision_fields(row),
        "reason": ident.get("reason"),
        "search_health_flags": ident.get("search_health_flags") or [],
        "slang_db_fields": ident.get("slang_insight") if isinstance(ident.get("slang_insight"), dict) else {},
        "evidence": summarize_evidence(row),
        "image_evidence": summarize_image_evidence(row),
        "review_question": queue_item["review_question"],
        "close_condition": queue_item["close_condition"],
    }


def label_hold_items(
    labels: list[dict[str, Any]],
    result_index: dict[str, dict[str, Any]],
    result_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    queue: list[dict[str, Any]] = []
    packets: list[dict[str, Any]] = []
    for row in labels:
        if str(row.get("label") or "").upper() != "HOLD":
            continue
        pid = post_key(row.get("post_id"))
        source = result_index.get(pid, {})
        action = str(row.get("action") or "human_review")
        queue_item = {
            "queue_id": f"{DEFAULT_PREFIX}-hold-{pid}-{action}",
            "queue_type": "hold_followup",
            "post_id": row.get("post_id"),
            "priority": "P1",
            "label": "HOLD",
            "action": action,
            "evidence_grade": row.get("evidence_grade"),
            "source": "v429_guarded_after_review",
            "primary_pattern": row.get("primary_pattern") or row.get("bucket") or row.get("applied_review_bucket"),
            "patterns": row.get("patterns") or [],
            "review_question": "v428 재실행으로 false positive는 해소됐지만, v429 HOLD action이 요구한 추가 확인이 닫혔는가?",
            "close_condition": "댓글 URL 검증, quote/title recall, human alignment 중 해당 action의 직접 근거가 packet에 남아야 한다.",
            "reviewer_note": row.get("reviewer_note"),
            "final_decision_fields": final_decision_fields(source) if source else {},
        }
        queue.append(queue_item)
        if source:
            packets.append(source_packet(source, queue_item, result_path))
    return queue, packets


def coverage_review_only_items(
    coverage: dict[str, Any],
    labels_by_post: dict[str, dict[str, Any]],
    result_index: dict[str, dict[str, Any]],
    result_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    queue: list[dict[str, Any]] = []
    packets: list[dict[str, Any]] = []
    for issue in coverage.get("issues") or []:
        if not isinstance(issue, dict):
            continue
        code = str(issue.get("code") or "")
        if code not in REVIEW_ONLY_ACTIONS:
            continue
        policy = REVIEW_ONLY_ACTIONS[code]
        for post_id in issue.get("sample_post_ids") or []:
            pid = post_key(post_id)
            source = result_index.get(pid, {})
            label = labels_by_post.get(pid, {})
            queue_item = {
                "queue_id": f"{DEFAULT_PREFIX}-review-only-{pid}-{code}",
                "queue_type": "coverage_review_only",
                "post_id": post_id,
                "priority": policy["priority"],
                "label": "REVIEW_ONLY",
                "action": policy["action"],
                "evidence_grade": label.get("evidence_grade") or "Medium",
                "source": "v430_semantic_coverage_refined",
                "coverage_code": code,
                "primary_pattern": code,
                "patterns": [code],
                "review_question": issue.get("recommended_action"),
                "close_condition": policy["close_condition"],
                "reviewer_note": issue.get("description"),
                "final_decision_fields": final_decision_fields(source) if source else {},
            }
            queue.append(queue_item)
            if source:
                packets.append(source_packet(source, queue_item, result_path))
    return queue, packets


def build_queue(labels_path: Path, coverage_path: Path, result_path: Path, prefix: str) -> dict[str, Any]:
    labels = load_jsonl(labels_path)
    coverage = load_json(coverage_path)
    rows = result_rows(load_json(result_path))
    result_index = {post_key(row.get("post_id")): row for row in rows if row.get("post_id") is not None}
    labels_by_post = {post_key(row.get("post_id")): row for row in labels if row.get("post_id") is not None}

    global DEFAULT_PREFIX
    DEFAULT_PREFIX = prefix

    hold_queue, hold_packets = label_hold_items(labels, result_index, result_path)
    review_queue, review_packets = coverage_review_only_items(
        coverage, labels_by_post, result_index, result_path
    )
    queue = hold_queue + review_queue
    packets = hold_packets + review_packets

    missing_packet_posts = [
        item["post_id"] for item in queue if post_key(item.get("post_id")) not in result_index
    ]

    manifest = {
        "run_id": DEFAULT_RUN_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "labels_path": labels_path.as_posix(),
        "coverage_path": coverage_path.as_posix(),
        "result_path": result_path.as_posix(),
        "source_result_rows": len(rows),
        "queue_items": len(queue),
        "packet_items": len(packets),
        "unique_posts": len({post_key(item.get("post_id")) for item in queue}),
        "missing_packet_posts": missing_packet_posts,
        "label_counts": dict(sorted(Counter(str(item.get("label")) for item in queue).items())),
        "queue_type_counts": dict(sorted(Counter(str(item.get("queue_type")) for item in queue).items())),
        "action_counts": dict(sorted(Counter(str(item.get("action")) for item in queue).items())),
        "priority_counts": dict(sorted(Counter(str(item.get("priority")) for item in queue).items())),
        "targeted_followup_gate": "REVIEW" if queue else "GO",
        "semantic_approval": "not_granted_by_targeted_followup_queue",
        "overall_100k_semantic_gate": "REVIEW-LOCKED",
        "overall_100k_reason": "v431은 targeted follow-up 잔여 큐이며 completed source와 expanded random/high-risk review를 대체하지 않는다.",
        "close_conditions": {
            item["queue_id"]: item["close_condition"]
            for item in queue
        },
    }
    return {"manifest": manifest, "queue": queue, "packets": packets}


def write_markdown(payload: dict[str, Any], path: Path) -> None:
    manifest = payload["manifest"]
    queue = payload["queue"]
    lines = [
        "# Targeted Follow-up Remaining Queue",
        "",
        "## 요약",
        "",
        f"- targeted_followup_gate: `{manifest['targeted_followup_gate']}`",
        f"- semantic_approval: `{manifest['semantic_approval']}`",
        f"- overall_100k_semantic_gate: `{manifest['overall_100k_semantic_gate']}`",
        f"- queue_items: `{manifest['queue_items']}`",
        f"- unique_posts: `{manifest['unique_posts']}`",
        "",
        "## 분포",
        "",
        f"- label_counts: `{manifest['label_counts']}`",
        f"- queue_type_counts: `{manifest['queue_type_counts']}`",
        f"- action_counts: `{manifest['action_counts']}`",
        "",
        "## 남은 항목",
        "",
        "| post_id | type | label | action | priority | close condition |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in queue:
        lines.append(
            "| {post_id} | `{queue_type}` | `{label}` | `{action}` | `{priority}` | {close_condition} |".format(
                post_id=item.get("post_id"),
                queue_type=item.get("queue_type"),
                label=item.get("label"),
                action=item.get("action"),
                priority=item.get("priority"),
                close_condition=str(item.get("close_condition") or "").replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## 판정 메모",
            "",
            "- 이 큐는 v428/v429/v430 targeted follow-up의 미종결 항목만 다룬다.",
            "- `REVIEW_ONLY`는 hard blocker가 아니라 packet-level 확인 대상이지만, approval evidence도 아니다.",
            "- 전체 10만 건 semantic approval은 completed VLM/OCR-on source와 expanded random/high-risk review 전까지 계속 `REVIEW-LOCKED`다.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build remaining queue from v429 labels and v430 coverage.")
    parser.add_argument("--labels", required=True)
    parser.add_argument("--coverage", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    payload = build_queue(Path(args.labels), Path(args.coverage), Path(args.result), args.prefix)
    write_json(output_dir / f"{args.prefix}_manifest.json", payload["manifest"])
    write_jsonl(output_dir / f"{args.prefix}_queue.jsonl", payload["queue"])
    write_jsonl(output_dir / f"{args.prefix}_packets.jsonl", payload["packets"])
    write_markdown(payload, output_dir / f"{args.prefix}_summary_ko.md")
    print(json.dumps(payload["manifest"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
