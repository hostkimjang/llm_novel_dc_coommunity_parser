from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


KNOWN_BAD_EXPECTATIONS = {
    11718083: "memory_query_should_not_resolve",
    11718099: "billhwan_alias_should_resolve_bireomeogeul_hwansaeng",
    11718091: "weak_character_reaction_should_not_resolve",
    11718097: "manggemhil_alias_should_resolve_manggameui_healer",
}

GENERIC_RESOLVED_TITLES = {
    "네이버",
    "표지변경",
    "소신발언",
    "연재",
    "작가",
    "완결",
    "리뷰",
    "추천",
    "판타지",
    "웹소설",
}

MEMORY_QUERY_PATTERNS = [
    "무슨 소설",
    "뭐였지",
    "기억이 안남",
    "기억 안남",
    "본 대사",
    "찾아",
    "찾고",
]

IMAGE_PATTERNS = ["[이미지", "이미지 첨부", "이미지 OCR", "이미지 요약", "OCR"]


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " / ".join(as_text(item) for item in value if item is not None)
    if isinstance(value, dict):
        for key in ("text", "content", "body", "comment", "title"):
            if key in value:
                return as_text(value.get(key))
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def excerpt(value: Any, limit: int = 260) -> str:
    text = re.sub(r"\s+", " ", as_text(value)).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def parse_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def parse_bool_field(name: str, text: str) -> bool | None:
    match = re.search(rf"{re.escape(name)}:\s*(true|false)", text, re.I)
    if not match:
        return None
    return match.group(1).lower() == "true"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_result_rows(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("results", "rows", "items"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    raise ValueError(f"Unsupported result JSON shape: {path}")


def load_checkpoint_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            payload = json.loads(line)
            result = payload.get("result") if isinstance(payload, dict) else None
            if isinstance(result, dict):
                result = dict(result)
                result["_checkpoint_line"] = line_no
                result["_checkpoint_status"] = payload.get("status")
                rows.append(result)
    return rows


def identity(row: dict[str, Any]) -> dict[str, Any]:
    return ((row.get("analysis_result") or {}).get("identity") or {}) if isinstance(row, dict) else {}


def resolved_title(idn: dict[str, Any]) -> str | None:
    for key in ("novel_identity", "primary_work"):
        item = idn.get(key)
        if isinstance(item, dict) and item.get("official_title"):
            return str(item.get("official_title"))
    return None


def heretic_url(idn: dict[str, Any]) -> str | None:
    for key in ("novel_identity", "primary_work"):
        item = idn.get(key)
        if isinstance(item, dict):
            url = item.get("heretic_url") or item.get("url")
            if url:
                return str(url)
    return None


def iter_candidate_dicts(idn: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key in (
        "novel_identity",
        "primary_work",
        "evidence",
        "search_evidence_catalog",
        "title_candidates",
        "mentioned_works",
        "secondary_reference_works",
        "recommendation_candidates",
        "entity_mentions",
    ):
        value = idn.get(key)
        if isinstance(value, dict):
            out.append(value)
        elif isinstance(value, list):
            out.extend(item for item in value if isinstance(item, dict))
    return out


def collect_urls(idn: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for item in iter_candidate_dicts(idn):
        for key in ("heretic_url", "url", "href", "source_url"):
            raw = str(item.get(key) or "").strip()
            if raw and raw not in seen:
                seen.add(raw)
                urls.append(raw)
    return urls


def is_novel_detail_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    query = parse_qs(parsed.query)
    if "novelpia.com" in host:
        return bool(re.search(r"/novel/\d+", path))
    if "munpia.com" in host:
        return bool(re.search(r"/novel/\d+", path))
    if "series.naver.com" in host:
        return path.endswith("/novel/detail.series") and bool(query.get("productNo") or query.get("productno"))
    if "page.kakao.com" in host:
        tab_type = str((query.get("tab_type") or [""])[0]).lower()
        return bool(re.search(r"/content/\d+", path)) and tab_type != "comment"
    if "ridibooks.com" in host:
        return bool(re.search(r"/books/\d+", path))
    if "joara.com" in host:
        return bool(re.search(r"/book/\d+", path) or re.search(r"/novel/\d+", path))
    return False


def is_platform_non_detail_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    platform = any(
        domain in host
        for domain in (
            "novelpia.com",
            "munpia.com",
            "series.naver.com",
            "page.kakao.com",
            "ridibooks.com",
            "joara.com",
        )
    )
    return platform and not is_novel_detail_url(url)


def row_facts(row: dict[str, Any], *, source: str, final_present: bool) -> dict[str, Any]:
    idn = identity(row)
    reason = as_text(idn.get("reason") or " / ".join(as_text(v) for v in idn.get("reason_lines") or []))
    title = as_text(row.get("title"))
    body = as_text(row.get("content"))
    comments = row.get("comments") if isinstance(row.get("comments"), list) else []
    text_public = " ".join([title, body, as_text(comments)])
    resolved = resolved_title(idn)
    urls = collect_urls(idn)
    detail_urls = [url for url in urls if is_novel_detail_url(url)]
    non_detail_platform_urls = [url for url in urls if is_platform_non_detail_url(url)]
    reason_official_urls = parse_int(r"official_urls=(\d+)", reason)
    reason_search_snippets = parse_int(r"search_snippets=(\d+)", reason)
    reason_post_spans = parse_int(r"post_spans=(\d+)", reason)
    official_title_evidence = parse_bool_field("official_title_evidence", reason)
    title_in_post = parse_bool_field("title_in_post", reason)
    degraded_queries = parse_int(r"degraded_queries:\s*(\d+)", reason)
    flags: list[str] = []
    pid = int(row.get("post_id") or 0)

    if not final_present:
        flags.append("run_integrity_checkpoint_completed_missing_from_final_result")
    if pid in KNOWN_BAD_EXPECTATIONS:
        flags.append(f"known_bad:{KNOWN_BAD_EXPECTATIONS[pid]}")
    if resolved and any(pattern in text_public for pattern in MEMORY_QUERY_PATTERNS):
        flags.append("memory_query_resolved")
    if resolved and str(resolved).strip() in GENERIC_RESOLVED_TITLES:
        flags.append("generic_resolved_title")
    if resolved and len(str(resolved).strip()) <= 4 and title_in_post is False:
        flags.append("short_title_without_post_anchor")
    if resolved and not detail_urls:
        flags.append("resolved_without_detail_url")
    if resolved and reason_official_urls and reason_official_urls > 0 and not detail_urls:
        flags.append("official_url_count_mismatch")
    if resolved and non_detail_platform_urls and (reason_official_urls or 0) > 0:
        flags.append("platform_non_detail_url_used_near_official_evidence")
    if resolved and official_title_evidence is True and (reason_official_urls or 0) == 0:
        flags.append("official_title_evidence_true_but_zero_official_urls")
    if resolved and official_title_evidence is False:
        flags.append("official_title_evidence_false_resolved")
    if resolved and (reason_post_spans == 0 or title_in_post is False):
        flags.append("resolved_without_direct_post_title_anchor")
    if resolved and (reason_search_snippets or 0) == 0 and (reason_official_urls or 0) == 0:
        flags.append("zero_search_and_official_bucket_resolved")
    if resolved and (degraded_queries or 0) > 0:
        flags.append("search_degraded_resolved")
    if comments and not row.get("comment_metadata"):
        flags.append("comments_without_author_metadata")
    if comments and not row.get("comment_context_lines"):
        flags.append("comment_speaker_context_unavailable")
    if any(pattern in text_public or pattern in reason for pattern in IMAGE_PATTERNS):
        flags.append("image_or_ocr_involved")
        if not idn.get("vlm_ocr_fields") and "image" not in {str(v).lower() for v in idn.get("context_sources") or []}:
            flags.append("vlm_ocr_public_state_weak")
    if resolved and idn.get("is_relevant") is False:
        flags.append("decision_contradiction_resolved_but_not_relevant")

    weak_strong = (
        bool(resolved)
        and idn.get("is_relevant") is True
        and (
            official_title_evidence is False
            or title_in_post is False
            or (reason_post_spans == 0 and (reason_official_urls or 0) == 0)
            or "유의사항" in reason
        )
    )
    if weak_strong:
        flags.append("weak_evidence_but_strong_resolution")

    return {
        "source": source,
        "final_present": final_present,
        "post_id": pid or row.get("post_id"),
        "checkpoint_line": row.get("_checkpoint_line"),
        "checkpoint_status": row.get("_checkpoint_status"),
        "title": title,
        "body_excerpt": excerpt(row.get("content"), 360),
        "comment_count": len(comments),
        "comment_metadata_count": len(row.get("comment_metadata") or []),
        "resolved_title": resolved,
        "heretic_url": heretic_url(idn),
        "detail_url_count": len(detail_urls),
        "non_detail_platform_url_count": len(non_detail_platform_urls),
        "sample_detail_urls": detail_urls[:3],
        "sample_non_detail_platform_urls": non_detail_platform_urls[:3],
        "is_relevant": idn.get("is_relevant"),
        "discussion_type": idn.get("discussion_type"),
        "work_resolution": idn.get("work_resolution"),
        "title_resolution_state": idn.get("title_resolution_state"),
        "official_title_evidence": official_title_evidence,
        "title_in_post": title_in_post,
        "reason_post_spans": reason_post_spans,
        "reason_search_snippets": reason_search_snippets,
        "reason_official_urls": reason_official_urls,
        "degraded_queries": degraded_queries,
        "flags": sorted(set(flags)),
        "reason_excerpt": excerpt(reason, 520),
    }


def merge_rows(final_rows: list[dict[str, Any]], checkpoint_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    final_by_id = {str(row.get("post_id")): row for row in final_rows if row.get("post_id") is not None}
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in checkpoint_rows:
        key = str(row.get("post_id"))
        if key in final_by_id:
            merged.append(row_facts(final_by_id[key], source="final_result", final_present=True))
        else:
            merged.append(row_facts(row, source="checkpoint_only", final_present=False))
        seen.add(key)
    for row in final_rows:
        key = str(row.get("post_id"))
        if key not in seen:
            merged.append(row_facts(row, source="final_result_only", final_present=True))
    return merged


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", required=True)
    parser.add_argument("--checkpoint")
    parser.add_argument("--manifest")
    parser.add_argument("--pending-snapshot")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--prefix", default="original_semantic_pattern_scan")
    args = parser.parse_args()

    result_path = Path(args.result)
    checkpoint_path = Path(args.checkpoint) if args.checkpoint else result_path.with_name(result_path.stem + "_checkpoint.jsonl")
    manifest_path = Path(args.manifest) if args.manifest else result_path.with_name(result_path.stem + "_manifest.json")
    pending_path = Path(args.pending_snapshot) if args.pending_snapshot else result_path.with_name(result_path.stem + "_pending_snapshot.json")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    final_rows = load_result_rows(result_path)
    checkpoint_rows = load_checkpoint_rows(checkpoint_path)
    manifest = load_json(manifest_path) if manifest_path.exists() else {}
    pending_snapshot = load_json(pending_path) if pending_path.exists() else []
    facts = merge_rows(final_rows, checkpoint_rows)

    flag_counts = Counter(flag for row in facts for flag in row["flags"])
    by_flag: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in facts:
        for flag in row["flags"]:
            if len(by_flag[flag]) < 20:
                by_flag[flag].append(row)

    known_bad = {str(row["post_id"]): row for row in facts if int(row.get("post_id") or 0) in KNOWN_BAD_EXPECTATIONS}
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_result_path": str(result_path),
        "checkpoint_path": str(checkpoint_path),
        "manifest_path": str(manifest_path),
        "pending_snapshot_path": str(pending_path),
        "run_id": manifest.get("run_id"),
        "input_post_count": manifest.get("input_post_count"),
        "manifest_completed_count": manifest.get("completed_count"),
        "manifest_flushed_count": manifest.get("flushed_count"),
        "manifest_pending_count": manifest.get("pending_count"),
        "manifest_failed_count": manifest.get("failed_count"),
        "final_result_rows": len(final_rows),
        "checkpoint_completed_rows": len(checkpoint_rows),
        "pending_snapshot_rows": len(pending_snapshot) if isinstance(pending_snapshot, list) else None,
        "unique_scanned_rows": len(facts),
        "flag_counts": dict(flag_counts.most_common()),
        "known_bad": known_bad,
        "examples_by_flag": {flag: rows for flag, rows in sorted(by_flag.items())},
    }

    summary_path = out_dir / f"{args.prefix}.json"
    examples_path = out_dir / f"{args.prefix}_examples.jsonl"
    report_path = out_dir / f"{args.prefix}_ko.md"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_jsonl(examples_path, [row for rows in by_flag.values() for row in rows])

    top_lines = []
    for flag, count in flag_counts.most_common(20):
        sample = by_flag[flag][0] if by_flag.get(flag) else {}
        top_lines.append(
            f"- `{flag}`: {count}건. 예: post_id `{sample.get('post_id')}`, "
            f"resolved `{sample.get('resolved_title')}`, title `{sample.get('title')}`"
        )

    known_lines = []
    for pid in sorted(KNOWN_BAD_EXPECTATIONS):
        row = known_bad.get(str(pid))
        if not row:
            known_lines.append(f"- `{pid}`: 결과 row 없음")
            continue
        known_lines.append(
            f"- `{pid}`: expected `{KNOWN_BAD_EXPECTATIONS[pid]}`, original resolved `{row.get('resolved_title')}`, "
            f"flags={', '.join(row.get('flags') or [])}"
        )

    report = f"""# 원본 semantic pattern scan

- 생성 시각: `{summary['generated_at']}`
- 원본 result: `{result_path}`
- checkpoint: `{checkpoint_path}`
- manifest: `{manifest_path}`
- run_id: `{summary['run_id']}`

## Run Integrity

- manifest input_post_count: `{summary['input_post_count']}`
- manifest completed/flushed/pending/failed: `{summary['manifest_completed_count']}` / `{summary['manifest_flushed_count']}` / `{summary['manifest_pending_count']}` / `{summary['manifest_failed_count']}`
- final result rows: `{summary['final_result_rows']}`
- checkpoint completed rows: `{summary['checkpoint_completed_rows']}`
- pending snapshot rows: `{summary['pending_snapshot_rows']}`

판정: 이 산출물은 104,502건 전체 완료 결과가 아니라 partial run 산출물이다. semantic approval 근거가 아니라 known-bad와 반복 실패 유형을 찾는 triage 근거로만 사용한다.

## Known-Bad 확인

{chr(10).join(known_lines)}

## 상위 반복 패턴

{chr(10).join(top_lines)}

## 해석

- `comments_without_author_metadata`와 `comment_speaker_context_unavailable`는 본문 작성자와 댓글 작성자의 관계를 후단이 안정적으로 검토하기 어렵다는 뜻이다.
- `memory_query_resolved`, `generic_resolved_title`, `weak_evidence_but_strong_resolution`는 자연어 의도 이해보다 검색 표면어/일반어가 title로 승격된 위험을 가리킨다.
- `official_url_count_mismatch`, `resolved_without_detail_url`, `platform_non_detail_url_used_near_official_evidence`는 reason의 근거 강도와 final URL 상태가 어긋난 케이스다.
- `image_or_ocr_involved`와 `vlm_ocr_public_state_weak`는 브라우저/스크린샷/VLM 직접 확인 bucket으로 보내야 한다.

## 산출물

- JSON summary: `{summary_path}`
- examples JSONL: `{examples_path}`
"""
    report_path.write_text(report, encoding="utf-8")
    print(f"wrote {summary_path}")
    print(f"wrote {examples_path}")
    print(f"wrote {report_path}")
    print(json.dumps({k: summary[k] for k in ("run_id", "final_result_rows", "checkpoint_completed_rows", "flag_counts")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
