from __future__ import annotations

import argparse
import glob
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


PLACEHOLDER_IMAGE_MARKERS = ("gallview_loading_ori.gif",)


def post_id_key(value: Any) -> str:
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if isinstance(item, dict):
                rows.append(item)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def expand_patterns(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        matches = glob.glob(pattern, recursive=True)
        if not matches and Path(pattern).is_file():
            matches = [pattern]
        for match in matches:
            path = Path(match)
            if path.is_file() and path not in paths:
                paths.append(path)
    return paths


def normalize_result_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        rows = payload.get("results") or payload.get("rows") or payload.get("items") or []
        return [row for row in rows if isinstance(row, dict)]
    return []


def load_source_file(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        raw_rows = load_jsonl(path)
        rows = []
        for item in raw_rows:
            row = item.get("result") if "result" in item and isinstance(item.get("result"), dict) else item
            if isinstance(row, dict):
                rows.append(row)
    else:
        rows = normalize_result_rows(load_json(path))
    for row in rows:
        row.setdefault("_source_path", path.as_posix())
    return rows


def block_url(block: Any) -> str:
    if not isinstance(block, dict):
        return ""
    return str(block.get("url") or block.get("image_url") or block.get("src") or "").strip()


def is_placeholder_url(url: str) -> bool:
    lowered = url.lower()
    return any(marker in lowered for marker in PLACEHOLDER_IMAGE_MARKERS)


def public_content_blocks(row: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str], int]:
    raw_blocks = row.get("content_blocks")
    if raw_blocks is None:
        raw_blocks = row.get("content") or []
    if isinstance(raw_blocks, str):
        raw_blocks = [raw_blocks]
    if not isinstance(raw_blocks, list):
        raw_blocks = [raw_blocks]

    blocks: list[dict[str, Any]] = []
    image_urls: list[str] = []
    dropped_placeholder_count = 0
    seen_urls: set[str] = set()

    for raw in raw_blocks:
        if isinstance(raw, dict):
            url = block_url(raw)
            text = str(raw.get("text") or raw.get("content") or "").strip()
            block_type = str(raw.get("type") or ("image" if url else "text") or "text").strip()
        else:
            url = ""
            text = str(raw or "").strip()
            block_type = "text"

        if url:
            if is_placeholder_url(url):
                dropped_placeholder_count += 1
                continue
            rec = {"type": "image", "url": url}
            if text:
                rec["text"] = text
            blocks.append(rec)
            if url not in seen_urls:
                seen_urls.add(url)
                image_urls.append(url)
        elif text:
            blocks.append({"type": block_type if block_type else "text", "text": text})

    for url in row.get("image_urls") or []:
        url = str(url or "").strip()
        if not url or url in seen_urls:
            continue
        if is_placeholder_url(url):
            dropped_placeholder_count += 1
            continue
        blocks.insert(0, {"type": "image", "url": url})
        seen_urls.add(url)
        image_urls.append(url)

    return blocks, image_urls, dropped_placeholder_count


def source_quality_score(row: dict[str, Any]) -> int:
    blocks, image_urls, _ = public_content_blocks(row)
    score = 0
    if blocks:
        score += 20
    if image_urls:
        score += 50
    if row.get("comments"):
        score += 5
    if row.get("comment_metadata"):
        score += 4
    if row.get("analysis_result"):
        score += 2
    return score


def index_sources(paths: list[Path], wanted_ids: set[str]) -> dict[str, dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for path in paths:
        for row in load_source_file(path):
            pid = post_id_key(row.get("post_id"))
            if pid not in wanted_ids:
                continue
            current = best.get(pid)
            if current is None or source_quality_score(row) > source_quality_score(current):
                best[pid] = row
    return best


def has_image_urls(row: dict[str, Any]) -> bool:
    _, image_urls, _ = public_content_blocks(row)
    return bool(image_urls)


def build_enriched_row(canary_row: dict[str, Any], source_row: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    pid = post_id_key(canary_row.get("post_id"))
    judge_seed = dict(canary_row.get("_judge_seed") or {})
    source_img_count = int(judge_seed.get("source_img_count") or canary_row.get("img_count") or canary_row.get("image_count") or 0)
    before_has_url = has_image_urls(canary_row)

    if source_row is None:
        enriched = dict(canary_row)
        status = "not_image_seed" if source_img_count <= 0 else "source_missing"
        reason = "source row was not found" if source_img_count > 0 else "source row has no image seed"
        restored_blocks: list[dict[str, Any]] = []
        restored_urls: list[str] = []
        dropped = 0
    else:
        restored_blocks, restored_urls, dropped = public_content_blocks(source_row)
        enriched = {
            key: value
            for key, value in source_row.items()
            if key not in {"analysis_result", "run_meta", "pipe", "reason", "_source_path"}
        }
        if not restored_blocks and canary_row.get("content"):
            enriched["content"] = canary_row.get("content")
        enriched["content_blocks"] = restored_blocks
        enriched["image_urls"] = restored_urls
        enriched["image_count"] = len(restored_urls)
        enriched.setdefault("gallery_id", canary_row.get("gallery_id") or "genrenovel")
        enriched.setdefault(
            "url",
            canary_row.get("url")
            or f"https://gall.dcinside.com/mgallery/board/view/?id=genrenovel&no={pid}",
        )
        if "comments" not in enriched and "comments" in canary_row:
            enriched["comments"] = canary_row.get("comments")
        if source_img_count <= 0:
            status = "not_image_seed"
            reason = "canary row did not require image URL restoration"
        elif before_has_url:
            status = "already_had_image_urls"
            reason = "canary row already had image URLs"
        elif restored_urls:
            status = "restored"
            reason = ""
        else:
            status = "source_without_image_urls"
            reason = "source row found but no non-placeholder image URLs were present"

    judge_seed.update(
        {
            "source_enriched": status in {"restored", "already_had_image_urls"},
            "source_enrichment_status": status,
            "source_enrichment_reason": reason,
            "source_enrichment_source_path": (source_row or {}).get("_source_path"),
            "source_img_count": source_img_count,
            "restored_image_url_count": len(restored_urls),
            "dropped_placeholder_image_count": dropped,
        }
    )
    enriched["_judge_seed"] = judge_seed

    report = {
        "post_id": int(pid) if pid.isdigit() else pid,
        "source_img_count": source_img_count,
        "before_has_image_url": before_has_url,
        "restore_status": status,
        "restore_reason": reason,
        "source_path": (source_row or {}).get("_source_path"),
        "restored_image_url_count": len(restored_urls),
        "dropped_placeholder_image_count": dropped,
    }
    return enriched, report


def write_report_md(path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# JUDGE3905 source-enriched canary restore report",
        "",
        f"- generated_at: `{manifest['generated_at']}`",
        f"- input_count: `{manifest['input_count']}`",
        f"- image_seed_count: `{manifest['image_seed_count']}`",
        f"- missing_image_url_count: `{manifest['missing_image_url_count']}`",
        f"- restored_count: `{manifest['restored_count']}`",
        f"- unrecovered_count: `{manifest['unrecovered_count']}`",
        f"- requested_parallel: `{manifest['recommended_parallel']}`",
        f"- expected_effective_parallel: `{manifest['expected_effective_parallel']}`",
        f"- dashboard_url: `{manifest['execution_contract']['dashboard_contract']['dashboard_url']}`",
        f"- output_input: `{manifest['outputs']['source_enriched_canary_input']}`",
        "",
        "## Restore Status Counts",
        "",
    ]
    for key, value in sorted(manifest["counts"]["by_restore_status"].items()):
        lines.append(f"- `{key}`: `{value}`")
    if manifest["unrecovered"]:
        lines.extend(["", "## Unrecovered", ""])
        for row in manifest["unrecovered"]:
            lines.append(f"- `{row['post_id']}`: `{row['restore_status']}` / {row['restore_reason']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def build_source_enriched_canary(
    *,
    canary_input: Path,
    source_patterns: list[str],
    out_dir: Path,
    prefix: str,
) -> dict[str, Any]:
    canary_rows = load_jsonl(canary_input)
    wanted_ids = {post_id_key(row.get("post_id")) for row in canary_rows}
    source_paths = expand_patterns(source_patterns)
    source_by_id = index_sources(source_paths, wanted_ids)

    enriched_rows: list[dict[str, Any]] = []
    restore_rows: list[dict[str, Any]] = []
    for row in canary_rows:
        pid = post_id_key(row.get("post_id"))
        enriched, report = build_enriched_row(row, source_by_id.get(pid))
        enriched_rows.append(enriched)
        restore_rows.append(report)

    out_dir.mkdir(parents=True, exist_ok=True)
    input_path = out_dir / f"{prefix}_source_enriched_canary_input.jsonl"
    manifest_path = out_dir / f"{prefix}_source_enriched_canary_manifest.json"
    report_json_path = out_dir / f"{prefix}_source_enriched_canary_restore_report.json"
    report_md_path = out_dir / f"{prefix}_source_enriched_canary_restore_report_ko.md"
    expected_result_path = out_dir / f"{prefix}_source_enriched_canary_result.json"
    expected_compare_path = out_dir / f"{prefix}_source_enriched_canary_compare.json"
    expected_compare_md_path = out_dir / f"{prefix}_source_enriched_canary_compare_ko.md"
    expected_manifest_path = expected_result_path.with_name(expected_result_path.stem + "_manifest.json")

    image_seed_count = sum(1 for row in restore_rows if int(row.get("source_img_count") or 0) > 0)
    missing_image_url_count = sum(
        1
        for row in restore_rows
        if int(row.get("source_img_count") or 0) > 0 and not row.get("before_has_image_url")
    )
    restored_count = sum(1 for row in restore_rows if row.get("restore_status") == "restored")
    recommended_parallel = requested_parallel_for_test_run(len(enriched_rows))
    expected_parallel = expected_effective_parallel(len(enriched_rows))
    unrecovered = [
        row
        for row in restore_rows
        if int(row.get("source_img_count") or 0) > 0
        and row.get("restore_status") not in {"restored", "already_had_image_urls"}
    ]

    manifest = {
        "generated_at": now(),
        "canary_input": canary_input.as_posix(),
        "source_patterns": source_patterns,
        "source_paths": [path.as_posix() for path in source_paths],
        "input_count": len(canary_rows),
        "recommended_parallel": recommended_parallel,
        "expected_effective_parallel": expected_parallel,
        "image_seed_count": image_seed_count,
        "missing_image_url_count": missing_image_url_count,
        "restored_count": restored_count,
        "unrecovered_count": len(unrecovered),
        "canary_post_ids": [row.get("post_id") for row in enriched_rows],
        "counts": {
            "by_restore_status": dict(Counter(row["restore_status"] for row in restore_rows)),
        },
        "restore_rows": restore_rows,
        "unrecovered": unrecovered,
        "outputs": {
            "source_enriched_canary_input": input_path.as_posix(),
            "manifest": manifest_path.as_posix(),
            "restore_report_json": report_json_path.as_posix(),
            "restore_report_md": report_md_path.as_posix(),
            "expected_result": expected_result_path.as_posix(),
            "expected_compare_json": expected_compare_path.as_posix(),
            "expected_compare_md": expected_compare_md_path.as_posix(),
        },
        "recommended_commands": {
            "expert_main_source_enriched_canary": (
                f"python expert_main.py --input {input_path.as_posix()} "
                f"--output {expected_result_path.as_posix()} --server-type vllm "
                f"--parallel {recommended_parallel} --reuse-shards-only "
                "--slang-db on --vlm on --ocr on --require-vlm-ocr-for-images"
            ),
            "compare_after_source_enriched_canary": (
                f"python tools/build_judge_seed_registry.py compare "
                f"--registry out/judge3905_p0_seed_registry/judge3905_p0_seed_registry.json "
                f"--canary-result {expected_result_path.as_posix()} "
                f"--manifest {manifest_path.as_posix()} "
                f"--output-json {expected_compare_path.as_posix()} "
                f"--output-md {expected_compare_md_path.as_posix()}"
            ),
        },
        "execution_contract": {
            "test_run_requested_parallel": recommended_parallel,
            "expected_effective_parallel": expected_parallel,
            "dashboard_contract": dashboard_contract(manifest_path=expected_manifest_path),
            "forbidden_flags": ["--no-dashboard"],
        },
        "gate": {
            "run_integrity": "PENDING",
            "semantic_quality": "REVIEW-LOCKED",
            "reason": "source restoration only; expert_main source-enriched canary and compare are required.",
        },
    }

    write_jsonl(input_path, enriched_rows)
    write_json(manifest_path, manifest)
    write_json(report_json_path, {"generated_at": manifest["generated_at"], "rows": restore_rows})
    write_report_md(report_md_path, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a source-enriched JUDGE3905 canary input.")
    parser.add_argument("--canary-input", type=Path, required=True)
    parser.add_argument("--source", action="append", required=True, help="Source JSON/JSONL path or glob. Repeatable.")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--prefix", default="judge3905_p0")
    args = parser.parse_args()
    manifest = build_source_enriched_canary(
        canary_input=args.canary_input,
        source_patterns=args.source,
        out_dir=args.out_dir,
        prefix=args.prefix,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
