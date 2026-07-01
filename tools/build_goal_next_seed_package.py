from __future__ import annotations

import argparse
import glob
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


IMAGE_ISSUES = {
    "image_evidence_catalog_missing",
    "image_ocr_reason_without_public_vlm_counter",
    "browser_visual_or_direct_evidence_missing",
    "image_context_without_vlm_catalog",
}
RERUN_ISSUES = {
    *IMAGE_ISSUES,
    "comment_context_resolution_without_attribution",
    "search_only_resolved_title",
    "blocked_intent_resolved_title",
}
PARALLEL_MAX = 36


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                row.setdefault("_source_path", path.as_posix())
                row.setdefault("_source_line_number", line_no)
                rows.append(row)
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def post_id_key(value: Any) -> str:
    return str(value or "").strip()


def row_post_id(row: dict[str, Any]) -> str:
    return post_id_key(
        row.get("post_id")
        or row.get("article_id")
        or row.get("parent_id")
        or row.get("id")
        or row.get("no")
    )


def is_comment_row(row: dict[str, Any]) -> bool:
    kind = str(row.get("type") or row.get("row_type") or row.get("kind") or "").strip().lower()
    return kind == "comment" or row.get("comment_id") is not None


def image_url_from_block(block: Any) -> str:
    if not isinstance(block, dict):
        return ""
    if str(block.get("type") or "").lower() != "image" and not (
        block.get("url") or block.get("image_url") or block.get("src")
    ):
        return ""
    return str(block.get("url") or block.get("image_url") or block.get("src") or "").strip()


def image_urls(row: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for block in row.get("content_blocks") or []:
        url = image_url_from_block(block)
        if url and url not in urls:
            urls.append(url)
    return urls


def source_quality_score(row: dict[str, Any], comments: list[dict[str, Any]]) -> int:
    score = 0
    if row.get("content_blocks"):
        score += 8
    if image_urls(row):
        score += 12
    if row.get("content"):
        score += 3
    if row.get("title"):
        score += 2
    if row.get("url"):
        score += 2
    if comments:
        score += 3
    if row.get("analysis_result"):
        score -= 4
    return score


def dedupe_comments(comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []
    for comment in comments:
        cid = str(comment.get("comment_id") or "").strip()
        content = str(comment.get("content") or comment.get("content_html") or "").strip()
        key = (cid, content)
        if key in seen:
            continue
        seen.add(key)
        unique.append(comment)
    return unique


def collect_issue_targets(audit: dict[str, Any]) -> tuple[dict[str, set[str]], dict[str, str]]:
    target_issues: dict[str, set[str]] = defaultdict(set)
    issue_severity: dict[str, str] = {}
    for issue in audit.get("issues") or []:
        code = str(issue.get("code") or "").strip()
        if not code:
            continue
        issue_severity[code] = str(issue.get("severity") or "")
        for pid in issue.get("sample_post_ids") or []:
            key = post_id_key(pid)
            if key:
                target_issues[key].add(code)
    return target_issues, issue_severity


def normalize_result_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("results") or payload.get("rows") or payload.get("items") or []
    else:
        rows = []
    return [row for row in rows if isinstance(row, dict)]


def result_row_to_source(row: dict[str, Any], path: Path) -> dict[str, Any]:
    item = row.get("result") if isinstance(row.get("result"), dict) else row
    out = dict(item)
    out.setdefault("_source_path", path.as_posix())
    return out


def expand_source_globs(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        for match in glob.glob(pattern, recursive=True):
            path = Path(match)
            if path.is_file() and path not in paths:
                paths.append(path)
    return paths


def build_package(
    *,
    audit_path: Path,
    out_dir: Path,
    prefix: str,
    source_globs: list[str],
    result_paths: list[Path],
    run_id: str,
) -> dict[str, Any]:
    audit = load_json(audit_path)
    target_issues, issue_severity = collect_issue_targets(audit)
    target_ids = sorted(target_issues, key=lambda item: int(item) if item.isdigit() else item)

    posts_by_id: dict[str, dict[str, Any]] = {}
    comments_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for path in expand_source_globs(source_globs):
        for row in load_jsonl(path):
            pid = row_post_id(row)
            if not pid or pid not in target_issues:
                continue
            if is_comment_row(row):
                comments_by_id[pid].append(row)
                continue
            current = posts_by_id.get(pid)
            current_comments = comments_by_id.get(pid, [])
            if current is None or source_quality_score(row, current_comments) > source_quality_score(current, current_comments):
                posts_by_id[pid] = row

    for result_path in result_paths:
        if not result_path.exists():
            continue
        payload = load_json(result_path) if result_path.suffix.lower() == ".json" else None
        rows = normalize_result_rows(payload) if payload is not None else load_jsonl(result_path)
        for raw in rows:
            row = result_row_to_source(raw, result_path)
            pid = row_post_id(row)
            if not pid or pid not in target_issues or is_comment_row(row):
                continue
            current = posts_by_id.get(pid)
            current_comments = comments_by_id.get(pid, [])
            if current is None or source_quality_score(row, current_comments) > source_quality_score(current, current_comments):
                posts_by_id[pid] = row

    rerun_rows: list[dict[str, Any]] = []
    browser_targets: list[dict[str, Any]] = []
    missing_post_ids: list[str] = []
    fallback_without_image_url: list[str] = []

    for pid in target_ids:
        issues = sorted(target_issues[pid])
        row = posts_by_id.get(pid)
        comments = dedupe_comments(comments_by_id.get(pid, []))
        needs_rerun = bool(set(issues) & RERUN_ISSUES)
        needs_browser = bool(set(issues) & IMAGE_ISSUES)
        urls = image_urls(row or {})
        if row is None:
            missing_post_ids.append(pid)
        elif needs_rerun:
            out = dict(row)
            out["post_id"] = int(pid) if pid.isdigit() else pid
            out["_goal_seed_issue_codes"] = issues
            out["_goal_seed_source_quality"] = (
                "raw_input_with_image_url"
                if urls
                else "source_without_image_url"
            )
            rerun_rows.append(out)
            for comment in comments:
                comment_out = dict(comment)
                comment_out["_goal_seed_parent_issues"] = issues
                rerun_rows.append(comment_out)
            if needs_browser and not urls:
                fallback_without_image_url.append(pid)

        browser_targets.append(
            {
                "run_id": run_id,
                "post_id": int(pid) if pid.isdigit() else pid,
                "url": (row or {}).get("url")
                or f"https://gall.dcinside.com/mgallery/board/view/?id=genrenovel&no={pid}",
                "title": (row or {}).get("title"),
                "issue_codes": issues,
                "issue_severities": {code: issue_severity.get(code) for code in issues},
                "browser_visual_required": needs_browser,
                "image_urls_available_in_source": urls,
                "source_path": (row or {}).get("_source_path"),
                "source_line_number": (row or {}).get("_source_line_number"),
                "acceptance_gate": (
                    "본문 이미지 영역까지 스크롤한 뒤 article_image_count>0, "
                    "article_loaded_count==article_image_count, placeholder/incomplete/broken=0을 확인해야 한다."
                    if needs_browser
                    else "브라우저 확인은 보조 증거이며, 자연어 판정은 title/body/comment/evidence packet으로 별도 검토한다."
                ),
            }
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    rerun_path = out_dir / f"{prefix}_rerun_input.jsonl"
    result_path = out_dir / f"{prefix}_result.json"
    result_manifest_path = out_dir / f"{prefix}_result_manifest.json"
    browser_path = out_dir / f"{prefix}_browser_targets.jsonl"
    manifest_path = out_dir / f"{prefix}_manifest.json"
    summary_path = out_dir / f"{prefix}_summary_ko.md"
    runtime_audit_json = out_dir / f"{prefix}_runtime_audit.json"
    runtime_audit_md = out_dir / f"{prefix}_runtime_audit_ko.md"
    semantic_audit_json = out_dir / f"{prefix}_semantic_coverage_audit.json"
    semantic_audit_md = out_dir / f"{prefix}_semantic_coverage_audit_ko.md"
    reason_hygiene_json = out_dir / f"{prefix}_reason_hygiene.json"

    write_jsonl(rerun_path, rerun_rows)
    write_jsonl(browser_path, browser_targets)

    issue_counts = Counter(code for codes in target_issues.values() for code in codes)
    recommended_parallel = min(PARALLEL_MAX, len({row_post_id(row) for row in rerun_rows if not is_comment_row(row)}))
    recommended_commands = {
        "rerun": (
            f".\\venv\\Scripts\\python.exe expert_main.py --input {rerun_path.as_posix()} "
            f"--output {result_path.as_posix()} --server-type vllm --parallel {recommended_parallel} "
            "--reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on --require-vlm-ocr-for-images"
        ),
        "runtime_audit": (
            f".\\venv\\Scripts\\python.exe tools\\audit_goal_test_run_contract.py "
            f"--manifest {result_manifest_path.as_posix()} "
            f"--output-json {runtime_audit_json.as_posix()} --output-md {runtime_audit_md.as_posix()} "
            "--fail-on-no-go"
        ),
        "semantic_coverage_audit": (
            f".\\venv\\Scripts\\python.exe tools\\build_semantic_coverage_audit.py "
            f"--result {result_path.as_posix()} "
            f"--output-json {semantic_audit_json.as_posix()} --output-md {semantic_audit_md.as_posix()}"
        ),
        "reason_hygiene": (
            f".\\venv\\Scripts\\python.exe tools\\scan_reason_hygiene.py {result_path.as_posix()} "
            f"--json-out {reason_hygiene_json.as_posix()} --fail-on-hit"
        ),
    }
    manifest = {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_audit": audit_path.as_posix(),
        "target_post_count": len(target_ids),
        "rerun_row_count": len(rerun_rows),
        "rerun_post_count": len([row for row in rerun_rows if not is_comment_row(row)]),
        "browser_target_count": len(browser_targets),
        "browser_visual_required_count": sum(1 for row in browser_targets if row["browser_visual_required"]),
        "missing_post_ids": missing_post_ids,
        "fallback_without_image_url_post_ids": fallback_without_image_url,
        "issue_counts": dict(issue_counts),
        "recommended_parallel": recommended_parallel,
        "recommended_commands": recommended_commands,
        "execution_contract": {
            "expert_main_parallel_is_max": PARALLEL_MAX,
            "small_run_policy": "새 소규모 run은 --parallel min(input_count,36)을 권장한다. 과거 p36 run은 effective_parallel로 판단한다.",
            "required_flags": [
                "--server-type vllm",
                "--reuse-shards-only",
                "--no-dashboard",
                "--slang-db on",
                "--vlm on",
                "--ocr on",
                "--require-vlm-ocr-for-images",
            ],
            "forbidden_without_explicit_lifecycle_test": [
                "--allow-goal-shard-lifecycle",
                "--auto-up-shards",
                "--auto-recreate-shards",
            ],
        },
        "outputs": {
            "rerun_input": rerun_path.as_posix(),
            "expected_result": result_path.as_posix(),
            "expected_result_manifest": result_manifest_path.as_posix(),
            "browser_targets": browser_path.as_posix(),
            "manifest": manifest_path.as_posix(),
            "summary": summary_path.as_posix(),
        },
        "gate": {
            "semantic_approval": "REVIEW-LOCKED",
            "reason": "partial 원본의 issue sample을 다음 rerun/browser 검토 단위로 포장했을 뿐이며, 실제 completed VLM/OCR-on source와 expanded review가 아직 없다.",
        },
    }
    write_json(manifest_path, manifest)
    write_summary(summary_path, manifest)
    return manifest


def write_summary(path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# v504 다음 실행 seed 패키지",
        "",
        f"- 생성 시각: `{manifest['generated_at']}`",
        f"- target post 수: `{manifest['target_post_count']}`",
        f"- rerun post 수: `{manifest['rerun_post_count']}`",
        f"- rerun row 수: `{manifest['rerun_row_count']}`",
        f"- browser target 수: `{manifest['browser_target_count']}`",
        f"- browser visual required: `{manifest['browser_visual_required_count']}`",
        f"- missing post id: `{len(manifest['missing_post_ids'])}`",
        f"- image URL 없는 fallback: `{len(manifest['fallback_without_image_url_post_ids'])}`",
        "",
        "## Issue 분포",
        "",
    ]
    for key, count in sorted(manifest["issue_counts"].items()):
        lines.append(f"- `{key}`: `{count}`")
    lines.extend(
        [
            "",
            "## 실행 계약",
            "",
            f"- 권장 `--parallel`: `{manifest['recommended_parallel']}`",
            "- `36`은 Gemma 4 4B runtime worker 상한이며 Codex `spawn_agent` 병렬과 별개다.",
            "- 소규모 targeted run은 36 worker를 채우려고 재실행하지 않고 manifest의 `effective_parallel`로 판단한다.",
            "- 이미지 post는 VLM/OCR on과 browser visual/loading gate가 같이 필요하다.",
            "",
            "## 산출물",
            "",
        ]
    )
    for key, value in sorted(manifest["outputs"].items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## 권장 명령", ""])
    for command in manifest["recommended_commands"].values():
        lines.extend(["```powershell", command, "```", ""])
    lines.extend(
        [
            "",
            "## Gate",
            "",
            "- 이 패키지는 다음 실행/브라우저 확인 seed다.",
            "- `browser_visual_required` 대상은 아직 visual gate 완료가 아니다.",
            "- 각 대상은 Codex in-app Browser에서 원문 URL 또는 이미지 URL을 열어 article image count, loaded count, placeholder/incomplete/broken/lazy pending 상태, screenshot path, visible observation, OCR/reason/final decision alignment를 기록해야 한다.",
            "- 이 기록이 없으면 visual evidence grade는 Missing 또는 Weak이며, OCR 문자열, 검색 snippet, reason text만으로 Strong evidence나 semantic GO를 열지 않는다.",
            "- 실제 rerun 결과, runtime audit, semantic coverage audit, browser visual evidence, after-review 전까지 semantic approval은 `REVIEW-LOCKED`다.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build next rerun/browser seed package from a semantic coverage audit.")
    parser.add_argument("--audit-json", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--prefix", default="v504_next_seed")
    parser.add_argument("--run-id", default="20260528_141006_620986")
    parser.add_argument(
        "--source-glob",
        action="append",
        default=["tests/inputs/*.jsonl"],
        help="JSONL source glob. Can be passed multiple times.",
    )
    parser.add_argument(
        "--result-path",
        action="append",
        default=[
            "out/expert_result_20260528_141006_620986.json",
            "out/expert_result_20260528_141006_620986_checkpoint.jsonl",
        ],
    )
    args = parser.parse_args()
    manifest = build_package(
        audit_path=args.audit_json,
        out_dir=args.out_dir,
        prefix=args.prefix,
        source_globs=args.source_glob,
        result_paths=[Path(path) for path in args.result_path],
        run_id=args.run_id,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
