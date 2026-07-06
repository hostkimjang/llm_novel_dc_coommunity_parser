from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from tools.test_run_dashboard_policy import (
    dashboard_contract,
    expected_effective_parallel,
    requested_parallel_for_test_run,
)


RUN_ID = "20260505_214349_324347"
RERUN_ACTIONS = {"re_search", "re_judge", "re_run"}
REVIEW_ACTIONS = {"docs_issue", "human_review", "slang_db_review"}
GEMMA4_4B_PARALLEL_MAX = 36


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        return []
    if path.suffix.lower() == ".json":
        payload = json.loads(text)
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            rows = payload.get("rows") or payload.get("items") or payload.get("queue")
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
        raise ValueError(f"Expected JSON array or row container: {path}")
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        if line.strip():
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _is_comment_row(row: dict[str, Any]) -> bool:
    row_type = str(row.get("type") or row.get("row_type") or row.get("kind") or "").strip().lower()
    return row_type == "comment" or row.get("comment_id") is not None


def _post_id_from_row(row: dict[str, Any]) -> Any:
    return row.get("post_id") or row.get("article_id") or row.get("parent_id") or row.get("id") or row.get("no")


def load_result_index(path: Path) -> dict[str, dict[str, Any]]:
    rows = load_records(path)
    posts: dict[str, dict[str, Any]] = {}
    comments_by_post: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        post_id = _post_id_from_row(row)
        if post_id is None:
            continue
        post_key = str(post_id)
        if _is_comment_row(row):
            comments_by_post.setdefault(post_key, []).append(row)
            continue
        item = dict(row)
        item["post_id"] = post_id
        posts[post_key] = item

    for post_key, comments in comments_by_post.items():
        post = posts.get(post_key)
        if post is None:
            continue
        existing = post.get("comments")
        if existing in (None, ""):
            existing_list: list[Any] = []
        elif isinstance(existing, list):
            existing_list = list(existing)
        else:
            existing_list = [existing]
        seen_comment_ids = {
            str(item.get("comment_id"))
            for item in existing_list
            if isinstance(item, dict) and item.get("comment_id") is not None
        }
        for comment in comments:
            cid = comment.get("comment_id")
            if cid is not None and str(cid) in seen_comment_ids:
                continue
            existing_list.append(comment)
            if cid is not None:
                seen_comment_ids.add(str(cid))
        post["comments"] = existing_list
        post.setdefault("comments_raw", existing_list)
    return posts


def optional_packet_index(review_dir: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    packets_path = review_dir / "review_packets.jsonl"
    labels_path = review_dir / "review_labels.jsonl"
    packet_by_id: dict[str, dict[str, Any]] = {}
    label_by_id: dict[str, dict[str, Any]] = {}
    if packets_path.exists():
        packet_by_id = {
            str(row.get("packet_id")): row
            for row in load_records(packets_path)
            if row.get("packet_id") is not None
        }
    if labels_path.exists():
        label_by_id = {
            str(row.get("packet_id")): row
            for row in load_records(labels_path)
            if row.get("packet_id") is not None
        }
    return packet_by_id, label_by_id


def normalize_queue_row(
    queue: dict[str, Any],
    packet_by_id: dict[str, dict[str, Any]],
    label_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    packet_id = queue.get("base_packet_id") or queue.get("packet_id") or queue.get("rerun_packet_id")
    packet = packet_by_id.get(str(packet_id), {}) if packet_id is not None else {}
    label = label_by_id.get(str(packet_id), {}) if packet_id is not None else {}
    primary_pattern = (
        queue.get("primary_pattern")
        or label.get("applied_review_bucket")
        or label.get("bucket")
        or packet.get("applied_review_bucket")
        or packet.get("bucket")
        or queue.get("bucket")
    )
    patterns = queue.get("patterns")
    if not isinstance(patterns, list) or not patterns:
        patterns = []
        for value in (
            primary_pattern,
            *(packet.get("risk_tags") or [] if isinstance(packet.get("risk_tags"), list) else []),
            *(label.get("boundary_risk") or [] if isinstance(label.get("boundary_risk"), list) else []),
        ):
            if value and value not in patterns:
                patterns.append(value)
    out = dict(queue)
    out.update(
        {
            "final_action": queue.get("final_action") or queue.get("action"),
            "final_label": queue.get("final_label") or queue.get("label"),
            "final_evidence_grade": queue.get("final_evidence_grade") or queue.get("evidence_grade"),
            "base_packet_id": queue.get("base_packet_id") or packet_id,
            "rerun_packet_id": queue.get("rerun_packet_id"),
            "primary_pattern": primary_pattern,
            "patterns": patterns,
            "resolved_title": queue.get("resolved_title") or packet.get("resolved_title"),
            "relevance": queue.get("relevance") if queue.get("relevance") is not None else packet.get("relevance"),
            "reviewer_note": queue.get("reviewer_note") or queue.get("rationale") or label.get("reviewer_note"),
            "approval_state": queue.get("approval_state") or "queued_from_action_queue",
        }
    )
    return out


def body_excerpt(row: dict[str, Any], limit: int = 420) -> str:
    content = row.get("content") or []
    if not content and isinstance(row.get("content_blocks"), list):
        content = [
            block.get("text") if isinstance(block, dict) else block
            for block in row.get("content_blocks") or []
            if not isinstance(block, dict) or str(block.get("type") or "").lower() != "image"
        ]
    if not isinstance(content, list):
        content = [content]
    text = " / ".join(str(item).strip() for item in content[:4] if str(item).strip())
    if len(text) > limit:
        return text[: limit - 3].rstrip() + "..."
    return text


def comment_excerpt(row: dict[str, Any], limit: int = 420) -> str:
    comments = row.get("comments") or []
    if not isinstance(comments, list):
        comments = [comments]
    text = " | ".join(
        str(item.get("content") if isinstance(item, dict) else item).strip()
        for item in comments[:8]
        if str(item.get("content") if isinstance(item, dict) else item).strip()
    )
    if len(text) > limit:
        return text[: limit - 3].rstrip() + "..."
    return text


def identity_fields(row: dict[str, Any]) -> dict[str, Any]:
    analysis_result = row.get("analysis_result") if isinstance(row, dict) else {}
    if not isinstance(analysis_result, dict):
        return {}
    identity = analysis_result.get("identity")
    return identity if isinstance(identity, dict) else {}


def final_decision_fields(row: dict[str, Any]) -> dict[str, Any]:
    identity = identity_fields(row)
    novel = identity.get("novel_identity")
    if not isinstance(novel, dict):
        novel = {}
    primary = identity.get("primary_work")
    if not isinstance(primary, dict):
        primary = {}
    return {
        "is_relevant": identity.get("is_relevant"),
        "official_title": novel.get("official_title") or primary.get("official_title"),
        "work_resolution": identity.get("work_resolution"),
        "identity_state": identity.get("identity_state"),
        "discussion_type": identity.get("discussion_type"),
        "topicality": identity.get("topicality"),
    }


def slang_db_fields(row: dict[str, Any]) -> dict[str, Any]:
    identity = identity_fields(row)
    slang = identity.get("slang_insight")
    return slang if isinstance(slang, dict) else {}


def enrich_raw_input(source: dict[str, Any], queue: dict[str, Any]) -> dict[str, Any]:
    meta = {
        "source": "v78_current_remaining_action_inputs",
        "base_packet_id": queue.get("base_packet_id"),
        "rerun_packet_id": queue.get("rerun_packet_id"),
        "packet_id": queue.get("base_packet_id") or queue.get("rerun_packet_id"),
        "primary_pattern": queue.get("primary_pattern"),
        "patterns": queue.get("patterns") or [],
        "label": queue.get("final_label"),
        "action": queue.get("final_action"),
        "evidence_grade": queue.get("final_evidence_grade"),
        "source_state": queue.get("source_state"),
        "rationale": queue.get("reviewer_note"),
        "approval_state": queue.get("approval_state"),
    }
    return {
        "post_id": source.get("post_id"),
        "url": source.get("url"),
        "gallery_id": source.get("gallery_id"),
        "title": source.get("title"),
        "content": source.get("content"),
        "content_blocks": source.get("content_blocks"),
        "image_urls": source.get("image_urls"),
        "image_count": source.get("image_count"),
        "comments": source.get("comments"),
        "comments_raw": source.get("comments_raw"),
        "comment_metadata": source.get("comment_metadata"),
        "comment_context_lines": source.get("comment_context_lines"),
        "author": source.get("author"),
        "post_author": source.get("post_author") or source.get("author"),
        "ip": source.get("ip"),
        "author_ip": source.get("author_ip"),
        "post_ip": source.get("post_ip"),
        "created_at": source.get("created_at"),
        "_round3_target": meta,
        "_issue_regression": {
            "source_run_id": RUN_ID,
            "primary_pattern": queue.get("primary_pattern"),
            "previous_label": queue.get("final_label"),
            "previous_action": queue.get("final_action"),
            "previous_resolved_title": queue.get("resolved_title"),
            "previous_relevance": queue.get("relevance"),
            "previous_evidence_grade": queue.get("final_evidence_grade"),
            "reason": queue.get("reviewer_note"),
        },
    }


def review_packet(source: dict[str, Any], queue: dict[str, Any]) -> dict[str, Any]:
    identity = identity_fields(source)
    return {
        "run_id": RUN_ID,
        "post_id": source.get("post_id"),
        "url": source.get("url"),
        "gallery_id": source.get("gallery_id"),
        "post_author": source.get("post_author") or source.get("author"),
        "title": source.get("title"),
        "content_blocks": source.get("content_blocks") if isinstance(source.get("content_blocks"), list) else [],
        "image_urls": source.get("image_urls") if isinstance(source.get("image_urls"), list) else [],
        "image_count": source.get("image_count"),
        "body_excerpt": body_excerpt(source),
        "comment_excerpt": comment_excerpt(source),
        "comment_metadata": source.get("comment_metadata") if isinstance(source.get("comment_metadata"), list) else [],
        "comment_context_lines": source.get("comment_context_lines") if isinstance(source.get("comment_context_lines"), list) else [],
        "created_at": source.get("created_at"),
        "author": source.get("author"),
        "final_label": queue.get("final_label"),
        "final_action": queue.get("final_action"),
        "final_evidence_grade": queue.get("final_evidence_grade"),
        "primary_pattern": queue.get("primary_pattern"),
        "patterns": queue.get("patterns") or [],
        "source_state": queue.get("source_state"),
        "base_packet_id": queue.get("base_packet_id"),
        "rerun_packet_id": queue.get("rerun_packet_id"),
        "resolved_title": queue.get("resolved_title"),
        "relevance": queue.get("relevance"),
        "final_decision_fields": final_decision_fields(source),
        "reason": identity.get("reason"),
        "search_health_flags": identity.get("search_health_flags") or [],
        "slang_db_fields": slang_db_fields(source),
        "reviewer_note": queue.get("reviewer_note"),
        "approval_state": queue.get("approval_state"),
    }


def build_action_inputs(
    review_dir: Path,
    remaining_path: Path,
    source_result_path: Path,
    prefix: str,
) -> dict[str, Any]:
    packet_by_id, label_by_id = optional_packet_index(review_dir)
    remaining_rows = [
        normalize_queue_row(row, packet_by_id, label_by_id)
        for row in load_records(remaining_path)
    ]
    source_index = load_result_index(source_result_path)

    missing_post_ids: list[int | str] = []
    rerun_by_action: dict[str, list[dict[str, Any]]] = {action: [] for action in sorted(RERUN_ACTIONS)}
    review_by_action: dict[str, list[dict[str, Any]]] = {action: [] for action in sorted(REVIEW_ACTIONS)}
    all_review_packets: list[dict[str, Any]] = []
    browser_targets: list[dict[str, Any]] = []
    image_source_missing_post_ids: list[int | str] = []
    image_source_missing_seen: set[str] = set()
    rerun_seen_post_ids: set[str] = set()
    review_seen_keys: set[tuple[str, str]] = set()
    all_review_seen_keys: set[tuple[str, str]] = set()
    browser_seen_post_ids: set[str] = set()

    seen: set[str] = set()
    duplicate_post_ids: list[str] = []
    for queue in remaining_rows:
        post_id = str(queue.get("post_id"))
        if post_id in seen:
            duplicate_post_ids.append(post_id)
        else:
            seen.add(post_id)
        source = source_index.get(post_id)
        if source is None:
            missing_post_ids.append(queue.get("post_id"))
            continue

        action = str(queue.get("final_action") or "")
        packet = review_packet(source, queue)
        all_key = (action, post_id)
        if all_key not in all_review_seen_keys:
            all_review_packets.append(packet)
            all_review_seen_keys.add(all_key)
        if action in RERUN_ACTIONS and post_id not in rerun_seen_post_ids:
            rerun_by_action[action].append(enrich_raw_input(source, queue))
            rerun_seen_post_ids.add(post_id)
        if action in REVIEW_ACTIONS and all_key not in review_seen_keys:
            review_by_action[action].append(packet)
            review_seen_keys.add(all_key)
        image_related = bool(
            queue.get("primary_pattern") in {"vlm_ocr_evidence_gap", "image_evidence_catalog_missing", "VLM_OCR_involved"}
            or "image_evidence_catalog_missing" in (queue.get("patterns") or [])
            or "vlm_ocr" in str(queue.get("primary_pattern") or "").lower()
        )
        has_source_image = bool(source.get("image_urls") or any(
            isinstance(block, dict) and (block.get("url") or str(block.get("type") or "").lower() == "image")
            for block in (source.get("content_blocks") or [])
        ))
        if image_related and not has_source_image and post_id not in image_source_missing_seen:
            image_source_missing_post_ids.append(queue.get("post_id"))
            image_source_missing_seen.add(post_id)
        if (image_related or action == "re_run") and post_id not in browser_seen_post_ids:
            browser_targets.append(packet)
            browser_seen_post_ids.add(post_id)

    output_paths: dict[str, str] = {}
    for action, rows in rerun_by_action.items():
        path = review_dir / f"{prefix}_{action}_input.jsonl"
        write_jsonl(path, rows)
        output_paths[f"{action}_input"] = path.as_posix()
    for action, rows in review_by_action.items():
        path = review_dir / f"{prefix}_{action}_packets.jsonl"
        write_jsonl(path, rows)
        output_paths[f"{action}_packets"] = path.as_posix()

    all_review_path = review_dir / f"{prefix}_all_review_packets.jsonl"
    browser_path = review_dir / f"{prefix}_browser_targets.jsonl"
    write_jsonl(all_review_path, all_review_packets)
    write_jsonl(browser_path, browser_targets)
    output_paths["all_review_packets"] = all_review_path.as_posix()
    output_paths["browser_targets"] = browser_path.as_posix()

    rerun_combined: list[dict[str, Any]] = []
    for action in ["re_search", "re_judge", "re_run"]:
        rerun_combined.extend(rerun_by_action[action])
    rerun_combined_path = review_dir / f"{prefix}_rerun_combined_input.jsonl"
    write_jsonl(rerun_combined_path, rerun_combined)
    output_paths["rerun_combined_input"] = rerun_combined_path.as_posix()
    recommended_parallel = requested_parallel_for_test_run(len(rerun_combined))
    expected_parallel = expected_effective_parallel(len(rerun_combined))
    expert_main_flags = [
        f"--parallel {recommended_parallel}" if recommended_parallel else "no expert_main rerun input",
        "--reuse-shards-only",
        "--server-type vllm",
        "--vlm on",
        "--ocr on",
    ]

    manifest = {
        "run_id": RUN_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "remaining_queue_path": remaining_path.as_posix(),
        "source_result_path": source_result_path.as_posix(),
        "remaining_rows": len(remaining_rows),
        "unique_remaining_rows": len(seen),
        "missing_post_ids": missing_post_ids,
        "image_source_missing_post_ids": image_source_missing_post_ids,
        "duplicate_post_ids_removed": duplicate_post_ids,
        "label_counts": dict(Counter(str(row.get("final_label")) for row in remaining_rows)),
        "action_counts": dict(Counter(str(row.get("final_action")) for row in remaining_rows)),
        "primary_pattern_counts": dict(Counter(str(row.get("primary_pattern")) for row in remaining_rows)),
        "rerun_input_counts": {action: len(rows) for action, rows in rerun_by_action.items()},
        "review_packet_counts": {action: len(rows) for action, rows in review_by_action.items()},
        "browser_target_rows": len(browser_targets),
        "rerun_combined_rows": len(rerun_combined),
        "output_paths": output_paths,
        "execution_contract": {
            "model_family": "Gemma 4 4B",
            "expert_main_parallel_max": GEMMA4_4B_PARALLEL_MAX,
            "current_rerun_input_count": len(rerun_combined),
            "recommended_parallel_for_current_inputs": recommended_parallel,
            "expected_effective_parallel_for_current_inputs": expected_parallel,
            "runtime_parallel_policy": "test_run_requested_parallel_locked_to_16_by_user; expert_main records min(requested_parallel, input_post_count)",
            "small_input_policy": "do not rerun or restart shards just to satisfy parallel max; verify manifest effective_parallel",
            "MCP_SHARD_COUNT_policy": "not required for small reuse-only goal/test runs; reserve 36 for large runs or explicit shard audit",
            "dashboard_contract": dashboard_contract(),
            "required_flags": expert_main_flags,
            "blocked_until": "LLM endpoint responds successfully",
        },
        "gate": {
            "semantic_decision_quality": "NO-GO",
            "reason": "action inputs prepared; rerun/review outputs still required",
        },
    }

    manifest_path = review_dir / f"{prefix}_manifest.json"
    write_json(manifest_path, manifest)
    output_paths["manifest"] = manifest_path.as_posix()
    write_summary(review_dir / f"{prefix}_summary_ko.md", manifest)
    return manifest


def write_summary(path: Path, manifest: dict[str, Any]) -> None:
    prefix = path.stem.removesuffix("_summary_ko")
    lines = [
        f"# {prefix} 현재 잔여 action별 입력 패키지",
        "",
        f"- 생성 시각: `{manifest['generated_at']}`",
        f"- remaining rows: `{manifest['remaining_rows']}`",
        f"- rerun combined rows: `{manifest['rerun_combined_rows']}`",
        f"- browser target rows: `{manifest['browser_target_rows']}`",
        f"- missing post_id: `{len(manifest['missing_post_ids'])}`",
        f"- image source missing post_id: `{len(manifest.get('image_source_missing_post_ids') or [])}`",
        "",
        "## Action 분포",
        "",
    ]
    for key, count in sorted(manifest["action_counts"].items()):
        lines.append(f"- `{key}`: `{count}`")
    lines.extend(["", "## Pattern 분포", ""])
    for key, count in sorted(manifest["primary_pattern_counts"].items()):
        lines.append(f"- `{key}`: `{count}`")
    lines.extend(["", "## 산출물", ""])
    for key, value in sorted(manifest["output_paths"].items()):
        lines.append(f"- `{key}`: `{value}`")
    contract = manifest["execution_contract"]
    lines.extend(
        [
            "",
            "## 실행 계약",
            "",
            f"- 모델 계열: `{contract['model_family']}`",
            f"- parallel max: `{contract['expert_main_parallel_max']}`",
            f"- 현재 expert_main 재실행 입력 수: `{contract['current_rerun_input_count']}`",
            f"- 권장 `--parallel`: `{contract['recommended_parallel_for_current_inputs']}`",
            f"- 예상 effective parallel: `{contract['expected_effective_parallel_for_current_inputs']}`",
            f"- dashboard URL: `{contract['dashboard_contract']['dashboard_url']}`",
            f"- small input 정책: {contract['small_input_policy']}",
            f"- shard count 정책: {contract['MCP_SHARD_COUNT_policy']}",
            "- 필수 플래그:",
        ]
    )
    for flag in contract["required_flags"]:
        lines.append(f"  - `{flag}`")
    lines.extend(
        [
            "",
            "## Gate",
            "",
            "- 이 산출물은 최신 closure 잔여 큐를 실행/검토 단위로 나눈 것이다.",
            "- 실제 36워커 재실행, 브라우저/VLM 확인, 사람 리뷰 결과가 없으므로 semantic gate는 계속 `NO-GO / REVIEW-LOCKED`다.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    global RUN_ID
    parser = argparse.ArgumentParser(description="Build action-specific inputs from the current remaining closure queue.")
    parser.add_argument("--review-dir", default=f"qualitative_review/{RUN_ID}")
    parser.add_argument("--remaining", default=f"qualitative_review/{RUN_ID}/round3_exit_action_remaining_queue.jsonl")
    parser.add_argument("--source-result", default="server-poc/expert_result_20260505_214349_324347.json")
    parser.add_argument("--prefix", default="v78_current_remaining_action")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    if args.run_id:
        RUN_ID = args.run_id

    manifest = build_action_inputs(
        Path(args.review_dir),
        Path(args.remaining),
        Path(args.source_result),
        args.prefix,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
