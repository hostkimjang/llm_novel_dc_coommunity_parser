from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from tools.test_run_dashboard_policy import (
    dashboard_contract,
    expected_effective_parallel,
    requested_parallel_for_test_run,
)


RERUN_ACTIONS = {"re_judge", "re_search", "re_run"}
REVIEW_ACTIONS = {"human_review", "slang_db_review", "docs_issue", "comment_url_verify"}
MAX_PARALLEL = 36


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"Expected JSON object at {path}:{line_no}")
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


def post_id_key(value: Any) -> str:
    return str(value).strip()


def is_comment_row(row: dict[str, Any]) -> bool:
    kind = str(row.get("type") or row.get("row_type") or row.get("kind") or "").strip().lower()
    return kind == "comment" or row.get("comment_id") is not None


def extract_target_ids(labels: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    target_ids: list[str] = []
    for row in labels:
        pid = row.get("post_id")
        if pid is None:
            continue
        key = post_id_key(pid)
        if key in seen:
            continue
        seen.add(key)
        target_ids.append(key)
    return target_ids


def load_target_source_rows(source_path: Path, target_ids: set[str]) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, list[dict[str, Any]]],
    list[dict[str, Any]],
]:
    posts: dict[str, dict[str, Any]] = {}
    comments_by_post: dict[str, list[dict[str, Any]]] = {pid: [] for pid in target_ids}
    duplicate_post_rows: list[dict[str, Any]] = []

    with source_path.open("r", encoding="utf-8-sig") as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            pid = row.get("post_id") or row.get("article_id") or row.get("parent_id") or row.get("id") or row.get("no")
            if pid is None:
                continue
            key = post_id_key(pid)
            if key not in target_ids:
                continue
            if is_comment_row(row):
                item = dict(row)
                item.setdefault("post_id", pid)
                comments_by_post.setdefault(key, []).append(item)
                continue
            if key in posts:
                duplicate_post_rows.append(
                    {
                        "post_id": pid,
                        "line_number": line_no,
                        "title": row.get("title"),
                    }
                )
                continue
            item = dict(row)
            item["post_id"] = pid
            item["_source_line_number"] = line_no
            posts[key] = item

            if set(posts) == target_ids and all(pid in comments_by_post for pid in target_ids):
                # Keep scanning because comment rows can appear after post rows.
                pass

    return posts, comments_by_post, duplicate_post_rows


def as_text_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        value = [value]
    out: list[str] = []
    for item in value:
        if isinstance(item, dict):
            text = item.get("text") if item.get("text") is not None else item.get("content")
        else:
            text = item
        text = str(text or "").strip()
        if text:
            out.append(text)
    return out


def excerpt(value: Any, *, limit: int = 360) -> str:
    text = " / ".join(as_text_list(value))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        return text[: limit - 3].rstrip() + "..."
    return text


def comment_excerpt(comments: list[dict[str, Any]], *, limit: int = 360) -> str:
    parts = []
    for comment in comments[:8]:
        text = comment.get("content") if isinstance(comment, dict) else comment
        text = str(text or "").strip()
        if text:
            parts.append(text)
    text = " | ".join(parts)
    if len(text) > limit:
        return text[: limit - 3].rstrip() + "..."
    return text


def content_blocks_for_input(source: dict[str, Any]) -> list[Any] | None:
    blocks = source.get("content_blocks")
    if isinstance(blocks, list) and blocks:
        return blocks
    content = source.get("content")
    if isinstance(content, list) and content:
        return [{"type": "text", "text": str(item)} for item in content if str(item).strip()]
    if isinstance(content, str) and content.strip():
        return [{"type": "text", "text": content.strip()}]
    return None


def image_urls_from_source(source: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    explicit = source.get("image_urls")
    if isinstance(explicit, list):
        urls.extend(str(item).strip() for item in explicit if str(item).strip())
    for block in source.get("content_blocks") or []:
        if not isinstance(block, dict):
            continue
        url = str(block.get("url") or block.get("image_url") or block.get("src") or "").strip()
        block_type = str(block.get("type") or "").strip().lower()
        if url and (block_type in {"image", "img", "photo", "picture"} or "viewimage" in url or "dcimg" in url):
            urls.append(url)
    return list(dict.fromkeys(urls))


def label_text(row: dict[str, Any]) -> str:
    return " ".join(
        str(row.get(key) or "")
        for key in ("label", "action", "evidence_grade", "rationale_ko", "title", "resolved_title")
    )


def recommended_actions(label: dict[str, Any]) -> list[str]:
    action = str(label.get("action") or "").strip()
    label_value = str(label.get("label") or "").strip()
    text = label_text(label)
    actions: list[str] = []
    if action:
        actions.append(action)
    if label_value == "REJECT" and action == "human_review":
        actions.append("re_judge")
    if label_value == "HOLD" and action == "human_review" and re.search(r"댓글|comment|URL|url", text):
        actions.extend(["re_search", "comment_url_verify"])
    if re.search(r"canonical drift|wrong canonical|다른 작가|신작 문맥|title-like anchor|직접 title", text, re.I):
        actions.append("re_search")
    if re.search(r"platform|플랫폼|커뮤니티명|갤러리명", text, re.I) and label_value == "REJECT":
        actions.append("re_judge")
    if not actions:
        actions.append("human_review")
    return list(dict.fromkeys(actions))


def primary_pattern(label: dict[str, Any]) -> str:
    buckets = label.get("buckets")
    if isinstance(buckets, list) and buckets:
        return "+".join(str(item) for item in buckets)
    bucket = label.get("bucket")
    if bucket:
        return str(bucket)
    return "search_only_blocked_intent_followup"


def build_input_row(source: dict[str, Any], comments: list[dict[str, Any]], label: dict[str, Any]) -> dict[str, Any]:
    actions = recommended_actions(label)
    blocks = content_blocks_for_input(source)
    image_urls = image_urls_from_source(source)
    row = {
        "post_id": source.get("post_id"),
        "url": source.get("url"),
        "gallery_id": source.get("gallery_id"),
        "title": source.get("title"),
        "content_blocks": blocks or [],
        "comments": comments,
        "comments_raw": comments,
        "author": source.get("author"),
        "post_author": source.get("post_author") or source.get("author"),
        "ip": source.get("ip"),
        "author_ip": source.get("author_ip"),
        "post_ip": source.get("post_ip"),
        "created_at": source.get("created_at"),
        "page_no": source.get("page_no"),
        "_round3_target": {
            "source": "search_only_blocked_intent_followup",
            "review_id": label.get("review_id"),
            "primary_pattern": primary_pattern(label),
            "patterns": label.get("buckets") if isinstance(label.get("buckets"), list) else [primary_pattern(label)],
            "label": label.get("label"),
            "action": label.get("action"),
            "recommended_actions": actions,
            "evidence_grade": label.get("evidence_grade"),
            "resolved_title": label.get("resolved_title"),
            "rationale_ko": label.get("rationale_ko"),
            "approval_state": "approval_excluded_until_followup_review",
        },
        "_issue_regression": {
            "source_run_id": "20260528_141006_620986",
            "review_id": label.get("review_id"),
            "previous_label": label.get("label"),
            "previous_action": label.get("action"),
            "recommended_actions": actions,
            "previous_resolved_title": label.get("resolved_title"),
            "previous_evidence_grade": label.get("evidence_grade"),
            "source_line_number": source.get("_source_line_number"),
            "source_quality": "source_input_recovered",
            "requires_vlm_ocr": bool(image_urls),
            "requires_browser_visual": bool(image_urls),
        },
    }
    if image_urls:
        row["image_urls"] = image_urls
        row["image_count"] = len(image_urls)
    return row


def build_review_packet(source: dict[str, Any], comments: list[dict[str, Any]], label: dict[str, Any]) -> dict[str, Any]:
    image_urls = image_urls_from_source(source)
    return {
        "run_id": "20260528_141006_620986",
        "review_id": label.get("review_id"),
        "post_id": source.get("post_id"),
        "url": source.get("url"),
        "gallery_id": source.get("gallery_id"),
        "source_path": source.get("_source_path"),
        "source_line_number": source.get("_source_line_number"),
        "post_author": source.get("post_author") or source.get("author"),
        "title": source.get("title"),
        "body_excerpt": excerpt(source.get("content_blocks") or source.get("content")),
        "comment_excerpt": comment_excerpt(comments),
        "comment_count": len(comments),
        "image_urls": image_urls,
        "image_count": len(image_urls),
        "previous_resolved_title": label.get("resolved_title"),
        "previous_label": label.get("label"),
        "previous_action": label.get("action"),
        "recommended_actions": recommended_actions(label),
        "previous_evidence_grade": label.get("evidence_grade"),
        "primary_pattern": primary_pattern(label),
        "buckets": label.get("buckets") if isinstance(label.get("buckets"), list) else [],
        "rationale_ko": label.get("rationale_ko"),
        "source_quality": "source_input_recovered",
        "approval_state": "REVIEW-LOCKED",
    }


def build_followup_package(
    *,
    labels_path: Path,
    source_path: Path,
    out_dir: Path,
    prefix: str,
) -> dict[str, Any]:
    labels = load_jsonl(labels_path)
    target_ids = extract_target_ids(labels)
    posts, comments_by_post, duplicate_post_rows = load_target_source_rows(source_path, set(target_ids))
    labels_by_post = {post_id_key(row.get("post_id")): row for row in labels if row.get("post_id") is not None}

    input_rows: list[dict[str, Any]] = []
    review_packets: list[dict[str, Any]] = []
    missing_post_ids: list[str] = []
    per_action_inputs: dict[str, list[dict[str, Any]]] = {}
    per_action_packets: dict[str, list[dict[str, Any]]] = {}
    browser_targets: list[dict[str, Any]] = []

    for pid in target_ids:
        label = labels_by_post.get(pid, {})
        source = posts.get(pid)
        if source is None:
            missing_post_ids.append(pid)
            continue
        source["_source_path"] = source_path.as_posix()
        comments = comments_by_post.get(pid, [])
        input_row = build_input_row(source, comments, label)
        packet = build_review_packet(source, comments, label)
        actions = recommended_actions(label)
        if any(action in RERUN_ACTIONS for action in actions):
            input_rows.append(input_row)
        review_packets.append(packet)
        if packet["image_count"]:
            browser_targets.append(packet)
        for action in actions:
            if action in RERUN_ACTIONS:
                per_action_inputs.setdefault(action, []).append(input_row)
            if action in REVIEW_ACTIONS:
                per_action_packets.setdefault(action, []).append(packet)

    out_dir.mkdir(parents=True, exist_ok=True)
    output_paths: dict[str, str] = {}
    combined_input_path = out_dir / f"{prefix}_rerun_combined_input.jsonl"
    review_packets_path = out_dir / f"{prefix}_review_packets.jsonl"
    browser_targets_path = out_dir / f"{prefix}_browser_targets.jsonl"
    write_jsonl(combined_input_path, input_rows)
    write_jsonl(review_packets_path, review_packets)
    write_jsonl(browser_targets_path, browser_targets)
    output_paths["rerun_combined_input"] = combined_input_path.as_posix()
    output_paths["review_packets"] = review_packets_path.as_posix()
    output_paths["browser_targets"] = browser_targets_path.as_posix()

    for action, rows in sorted(per_action_inputs.items()):
        path = out_dir / f"{prefix}_{action}_input.jsonl"
        write_jsonl(path, rows)
        output_paths[f"{action}_input"] = path.as_posix()
    for action, rows in sorted(per_action_packets.items()):
        path = out_dir / f"{prefix}_{action}_packets.jsonl"
        write_jsonl(path, rows)
        output_paths[f"{action}_packets"] = path.as_posix()

    action_counts: Counter[str] = Counter()
    for label in labels:
        for action in recommended_actions(label):
            action_counts[action] += 1
    recommended_requested_parallel = requested_parallel_for_test_run(len(input_rows))
    recommended_parallel = expected_effective_parallel(len(input_rows))
    result_path = out_dir / f"{prefix}_result.json"
    result_manifest_path = out_dir / f"{prefix}_result_manifest.json"
    preflight_json_path = out_dir / f"{prefix}_preflight.json"
    preflight_md_path = out_dir / f"{prefix}_preflight_ko.md"

    manifest = {
        "run_id": "20260528_141006_620986",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "labels_path": labels_path.as_posix(),
        "source_path": source_path.as_posix(),
        "target_post_ids": target_ids,
        "target_count": len(target_ids),
        "source_post_rows_found": len(posts),
        "source_comment_rows_found": sum(len(rows) for rows in comments_by_post.values()),
        "missing_post_ids": missing_post_ids,
        "duplicate_post_rows_skipped": duplicate_post_rows,
        "label_counts": dict(Counter(str(row.get("label") or "UNKNOWN") for row in labels)),
        "original_action_counts": dict(Counter(str(row.get("action") or "UNKNOWN") for row in labels)),
        "recommended_action_counts": dict(action_counts),
        "rerun_combined_rows": len(input_rows),
        "review_packet_rows": len(review_packets),
        "browser_target_rows": len(browser_targets),
        "image_post_ids": [row["post_id"] for row in browser_targets],
        "output_paths": output_paths,
        "parallel_policy": {
            "requested_parallel_max": MAX_PARALLEL,
            "recommended_requested_parallel": recommended_requested_parallel,
            "expected_effective_parallel": recommended_parallel,
            "rule": "신규 테스트런/검증런은 expert_main --parallel 16을 요청하고, effective workers는 min(input_post_count, 16)로 manifest에서 확인한다.",
        },
        "execution_contract": {
            "server_type": "vllm",
            "slang_db": "on",
            "vlm": "on",
            "ocr": "on",
            "require_vlm_ocr_for_images": True,
            "reuse_shards_only": True,
            "dashboard_contract": dashboard_contract(manifest_path=result_manifest_path, python_executable=".\\venv\\Scripts\\python.exe"),
            "forbidden_flags": [
                "--no-dashboard",
                "--allow-goal-shard-lifecycle",
                "--auto-up-shards",
                "--auto-recreate-shards",
            ],
        },
        "recommended_preflight_command": (
            f".\\venv\\Scripts\\python.exe tools\\preflight_expert_rerun_runtime.py "
            f"--input {combined_input_path} --manifest {out_dir / (prefix + '_manifest.json')} "
            f"--expected-shards 36 --workers 36 --output-json {preflight_json_path} "
            f"--output-md {preflight_md_path} --strict"
        ),
        "recommended_rerun_command": (
            f".\\venv\\Scripts\\python.exe expert_main.py --input {combined_input_path} "
            f"--output {result_path} --server-type vllm --parallel {recommended_requested_parallel} --reuse-shards-only "
            "--slang-db on --vlm on --ocr on --require-vlm-ocr-for-images"
        ),
        "gate": {
            "run_integrity": "REVIEW",
            "semantic_decision_quality": "REVIEW-LOCKED",
            "overall": "REVIEW-LOCKED",
            "reason": "follow-up inputs are prepared, but targeted rerun/browser/after-review are not complete.",
        },
    }
    manifest_path = out_dir / f"{prefix}_manifest.json"
    write_json(manifest_path, manifest)
    output_paths["manifest"] = manifest_path.as_posix()
    write_summary(out_dir / f"{prefix}_summary_ko.md", manifest)
    return manifest


def write_summary(path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# search-only / blocked-intent 후속 입력 패키지",
        "",
        f"- 생성 시각: `{manifest['generated_at']}`",
        f"- labels: `{manifest['labels_path']}`",
        f"- source: `{manifest['source_path']}`",
        f"- 대상 post: `{manifest['target_count']}`",
        f"- source post rows found: `{manifest['source_post_rows_found']}`",
        f"- source comment rows found: `{manifest['source_comment_rows_found']}`",
        f"- rerun combined rows: `{manifest['rerun_combined_rows']}`",
        f"- browser target rows: `{manifest['browser_target_rows']}`",
        f"- missing post ids: `{len(manifest['missing_post_ids'])}`",
        "",
        "## 라벨 분포",
        "",
    ]
    for key, count in sorted(manifest["label_counts"].items()):
        lines.append(f"- `{key}`: `{count}`")
    lines.extend(["", "## 권장 action 분포", ""])
    for key, count in sorted(manifest["recommended_action_counts"].items()):
        lines.append(f"- `{key}`: `{count}`")
    lines.extend(["", "## 산출물", ""])
    for key, value in sorted(manifest["output_paths"].items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## 병렬/실행 계약",
            "",
            f"- recommended requested parallel: `{manifest['parallel_policy']['recommended_requested_parallel']}`",
            f"- expected effective parallel: `{manifest['parallel_policy']['expected_effective_parallel']}`",
            f"- dashboard URL: `{manifest['execution_contract']['dashboard_contract']['dashboard_url']}`",
            f"- 정책: {manifest['parallel_policy']['rule']}",
            "- Codex `spawn_agent` 병렬 검토와 `expert_main.py --parallel` runtime worker cap은 별개다.",
            "- 소규모 targeted rerun은 16 worker를 채우려고 재실행하지 않고 manifest의 effective_parallel로 판단한다.",
            "- Docker compose/shard lifecycle flag는 금지하고 `--reuse-shards-only`로 현재 서버 상태를 재사용한다.",
            "- VLM/OCR 기준 테스트이므로 이미지 post가 있으면 `--vlm on --ocr on --require-vlm-ocr-for-images`를 사용한다.",
            "",
            "## 권장 preflight",
            "",
            "```powershell",
            manifest["recommended_preflight_command"],
            "```",
            "",
            "## 권장 rerun",
            "",
            "```powershell",
            manifest["recommended_rerun_command"],
            "```",
            "",
            "## Gate",
            "",
            "- 이 패키지는 후속 실행 준비물이다. 실제 rerun, browser visual 확인, after-review 전까지 semantic gate는 `REVIEW-LOCKED`다.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build follow-up rerun/review inputs for search-only and blocked-intent qualitative labels."
    )
    parser.add_argument("--labels", required=True, type=Path)
    parser.add_argument("--source-jsonl", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--prefix", default="search_only_blocked_intent_followup")
    args = parser.parse_args()

    manifest = build_followup_package(
        labels_path=args.labels,
        source_path=args.source_jsonl,
        out_dir=args.out_dir,
        prefix=args.prefix,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
