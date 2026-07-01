from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter, defaultdict, OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse


RUN_ID = "20260505_214349_324347"
ROUND_NAME = "round2_failure_pattern_expansion"
SEED = f"{RUN_ID}:round2_failure_pattern_expansion:v1"

BUCKET_TARGETS = OrderedDict(
    [
        ("search_degraded_or_timeout", 20),
        ("reason_decision_contradiction", 20),
        ("final_semantic_reread_missing_for_semantic_seed", 20),
        ("final_semantic_reread_reviewed", 20),
        ("official_url_synopsis_or_branding_mismatch", 20),
        ("official_url_missing_for_resolved", 20),
        ("weak_evidence_but_strong_resolution", 20),
        ("generic_parenthetical_bridge", 20),
        ("unresolved_to_resolved", 20),
        ("multi_work_or_adjacent_risk", 20),
        ("trope_or_author_talk_risk", 20),
        ("slang_db_store_block_pending_family_noise", 20),
        ("comments_without_author_metadata", 20),
        ("comment_speaker_context_unavailable", 20),
        ("comment_author_ip_mismatch_dialogue", 20),
        ("comment_author_match_unverified_dialogue", 20),
        ("post_author_comment_not_independent_evidence", 20),
        ("comment_answer_side_conversation", 20),
        ("quote_alignment_missing_for_memory_query", 20),
        ("memory_query_resolved", 20),
        ("batch_memory_exact_alias_rescued_no_anchor", 20),
        ("critical_counter_but_resolved", 20),
        ("notes_demoted_then_resolved", 20),
        ("title_surface_primary_candidate_rescued", 20),
        ("reason_says_no_anchor_but_resolved", 20),
        ("search_absent_verified_title_direct_image_title", 20),
        ("official_title_evidence_true_but_zero_official_urls", 20),
        ("platform_non_detail_url_used_near_official_evidence", 20),
        ("VLM_OCR_involved", 20),
        ("image_evidence_catalog_missing", 20),
        ("vlm_ocr_public_state_weak", 20),
        ("worker_or_shard_degraded_window", 20),
        ("round2_false_negative_recall", 20),
    ]
)

LABELS = ["ACCEPT", "HOLD", "REPROCESS", "REJECT", "INFO_MISSING"]

RANDOM_CONTROL_RISK_BUCKET_PRIORITY = [
    "reason_decision_contradiction",
    "reason_says_no_anchor_but_resolved",
    "batch_memory_exact_alias_rescued_no_anchor",
    "quote_alignment_missing_for_memory_query",
    "memory_query_resolved",
    "title_surface_primary_candidate_rescued",
    "search_absent_verified_title_direct_image_title",
    "image_evidence_catalog_missing",
    "vlm_ocr_public_state_weak",
    "comments_without_author_metadata",
    "comment_speaker_context_unavailable",
    "critical_counter_but_resolved",
    "official_url_missing_for_resolved",
    "official_url_synopsis_or_branding_mismatch",
    "final_semantic_reread_missing_for_semantic_seed",
    "weak_evidence_but_strong_resolution",
    "search_degraded_or_timeout",
]

VIRTUAL_BATTLE_REVIEW_TERMS = (
    "줄다리기",
    "전차",
    "탱크",
    "대결",
    "vs",
    "비비",
    "이길까",
    "누가이김",
    "누가 이김",
    "누가이기",
    "강한편",
    "쌔",
    "쎄",
    "강함",
    "능력치",
    "힘겨루기",
)

GENERIC_TERMS = {
    "판타지 용어",
    "정신분열병",
    "2016",
    "Legend",
    "레전드",
}

GENERIC_INNER_KEYWORDS = [
    "용어",
    "장르",
    "설정",
    "개념",
    "판타지",
    "무협",
    "웹소설",
    "일반",
    "질병",
    "상태",
    "트로프",
    "클리셰",
    "직업",
    "속성",
]

GENERIC_EXPLANATORY_OUTER_TERMS = {
    "개념",
    "내용",
    "본문",
    "이미지",
    "요약",
    "작품",
    "정보",
    "장르",
    "설정",
}

TROPE_OR_META_KEYWORDS = [
    "작가",
    "신작",
    "장르",
    "클리셰",
    "설정",
    "세계관",
    "트로프",
    "소재",
    "오러",
    "마나",
    "회귀",
    "빙의",
    "헌터",
    "먼치킨",
    "용어",
    "연재",
    "휴재",
]

MULTI_OR_ADJACENT_KEYWORDS = [
    "추천",
    "비슷",
    "작품들",
    "작품 중",
    "작가",
    "신작",
    "후속작",
    "웹툰",
    "만화",
    "애니",
    "게임",
    "비교",
]

NOVEL_CUE_KEYWORDS = [
    "소설",
    "웹소",
    "웹소설",
    "문피아",
    "시리즈",
    "카카페",
    "카카오페이지",
    "리디",
    "조아라",
    "노벨피아",
    "연재",
    "작품",
    "주인공",
    "작가",
    "스포",
    "회차",
    "화",
]

MEMORY_QUERY_PATTERNS = [
    "무슨 소설",
    "뭐였지",
    "기억이 안남",
    "기억 안남",
    "본 대사",
    "찾아",
    "찾고",
]

QUOTE_OR_SCENE_RECALL_PATTERNS = [
    "대사",
    "문장",
    "구절",
    "장면",
    "내용",
    "인용",
    "봤던",
    "본 ",
    "본거",
    "본 거",
]

GENERIC_MEMORY_QUERY_PARTS = [
    "무슨소설",
    "뭔소설",
    "뭐였지",
    "기억이안남",
    "기억안남",
    "찾아",
    "찾고",
    "제목",
    "소설",
    "웹소설",
    "대사",
    "문장",
    "구절",
    "장면",
    "내용",
    "옛날",
]

IMAGE_OR_OCR_PATTERNS = [
    "[이미지",
    "이미지 첨부",
    "이미지 OCR",
    "이미지 요약",
    "OCR",
    "image",
    "?대?吏",
    "[?대?吏 泥⑤?]",
]

GENERIC_COMMENT_AUTHORS = {"ㅇㅇ", "익명", "유동", "무명", "anonymous", "anon", "unknown", "-"}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def infer_run_id(result_path: Path) -> str:
    for part in (result_path.name, *reversed(result_path.parts)):
        match = re.search(r"(?:expert_result_)?(\d{8}_\d{6}_\d+)", str(part))
        if match:
            return match.group(1)
    return RUN_ID


def load_source_integrity_summary(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"summary_path": path.as_posix(), "summary_load_error": True}
    if isinstance(payload, dict):
        payload = dict(payload)
        payload["summary_path"] = path.as_posix()
        return payload
    return {"summary_path": path.as_posix(), "summary_shape": type(payload).__name__}


def infer_source_dataset_kind(result_path: Path, summary: dict[str, Any] | None = None) -> str:
    name = result_path.name.lower()
    if "recovered" in name:
        return "checkpoint_recovered_completed_subset"
    if "expert_result_" in name:
        return "final_result_json"
    classification = str((summary or {}).get("integrity_classification") or "")
    if classification == "recoverable_pending_flush_gap":
        return "checkpoint_recovered_completed_subset"
    return "result_json"


def source_review_policy(result_path: Path, summary: dict[str, Any] | None = None) -> dict[str, Any]:
    summary = summary or {}
    kind = infer_source_dataset_kind(result_path, summary)
    large_run_complete = summary.get("large_run_complete")
    if kind == "checkpoint_recovered_completed_subset":
        approval_policy = (
            "checkpoint completed row를 복구한 subset이다. partial triage와 known-bad/high-risk 리뷰에는 사용할 수 있지만 "
            "원본 large run completion 또는 10만 건 semantic approval 근거로 쓰지 않는다."
        )
    elif large_run_complete is False:
        approval_policy = "source integrity summary가 large run incomplete를 보고하므로 semantic approval 근거로 쓰지 않는다."
    else:
        approval_policy = "manifest/checkpoint/log 정합성을 별도로 확인한 뒤 semantic review 근거로 사용한다."
    return {
        "source_dataset_kind": kind,
        "source_integrity_classification": summary.get("integrity_classification"),
        "recovery_safe_to_use_as_completed_subset": summary.get("recovery_safe_to_use_as_completed_subset"),
        "large_run_complete": large_run_complete,
        "approval_policy": approval_policy,
        "summary_path": summary.get("summary_path"),
        "counts": {
            "final_result_rows": summary.get("final_result_rows"),
            "checkpoint_completed_rows": summary.get("checkpoint_completed_rows"),
            "pending_snapshot_rows": summary.get("pending_snapshot_rows"),
            "recovered_rows": summary.get("recovered_rows"),
        },
    }


def load_preflight_summary(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return data if isinstance(data, dict) else None


def _same_resolved_path(left: Any, right: Path) -> bool:
    raw_left = str(left or "").strip()
    if not raw_left:
        return False
    try:
        return Path(raw_left).resolve() == right.resolve()
    except OSError:
        return raw_left.replace("\\", "/") == right.as_posix()


def preflight_source_gate_status(
    preflight: dict[str, Any] | None,
    *,
    result_path: Path,
    fail_on_locked_source: bool,
) -> dict[str, Any]:
    if not fail_on_locked_source:
        return {"exit_code": 0, "blocked": False, "reason": "not_requested"}
    if not isinstance(preflight, dict):
        return {"exit_code": 2, "blocked": True, "reason": "preflight_missing"}

    source_result_path = preflight.get("source_result_path")
    if not _same_resolved_path(source_result_path, result_path):
        return {
            "exit_code": 2,
            "blocked": True,
            "reason": "preflight_source_mismatch",
            "preflight_source_result_path": source_result_path,
            "requested_result_path": result_path.as_posix(),
        }

    gate = preflight.get("gate") if isinstance(preflight, dict) else {}
    overall = gate.get("overall") if isinstance(gate, dict) else None
    if overall == "REVIEW-LOCKED":
        return {
            "exit_code": 2,
            "blocked": True,
            "reason": "preflight_review_locked",
            "gate_overall": overall,
            "required_next_actions": gate.get("required_next_actions") if isinstance(gate, dict) else [],
        }
    return {
        "exit_code": 0,
        "blocked": False,
        "reason": "preflight_allows_source",
        "gate_overall": overall,
    }


def iter_json_array(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    decoder = json.JSONDecoder()
    chunk_size = 1024 * 1024 * 4
    with path.open("r", encoding="utf-8") as f:
        buf = ""
        pos = 0
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                return
            buf += chunk
            start = buf.find("[")
            if start >= 0:
                pos = start + 1
                break
            buf = ""

        row_index = 0
        while True:
            while True:
                while pos < len(buf) and buf[pos] in " \t\r\n,":
                    pos += 1
                if pos < len(buf):
                    break
                more = f.read(chunk_size)
                if not more:
                    return
                buf = ""
                pos = 0
                buf += more

            if buf[pos] == "]":
                return

            try:
                row, end = decoder.raw_decode(buf, pos)
            except json.JSONDecodeError:
                more = f.read(chunk_size)
                if not more:
                    raise
                buf = buf[pos:] + more
                pos = 0
                continue

            pos = end
            if isinstance(row, dict):
                row_index += 1
                yield row_index, row

            if pos > chunk_size:
                buf = buf[pos:]
                pos = 0


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " / ".join(as_text(item) for item in value if item is not None)
    if isinstance(value, dict):
        for key in ("text", "content", "body", "comment"):
            if key in value:
                return as_text(value.get(key))
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def excerpt(value: Any, limit: int = 360) -> str:
    text = re.sub(r"\s+", " ", as_text(value)).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def comments_excerpt(row: dict[str, Any], limit: int = 360) -> str:
    comments = row.get("comments")
    if not comments:
        return ""
    if isinstance(comments, list):
        parts = [excerpt(item, 160) for item in comments[:3]]
        return " / ".join(part for part in parts if part)[:limit]
    return excerpt(comments, limit)


def comment_metadata_from_row(row: dict[str, Any]) -> list[dict[str, Any]]:
    raw = row.get("comment_metadata")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _compact_author(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().lower())


def _is_generic_comment_author(value: Any) -> bool:
    return _compact_author(value) in GENERIC_COMMENT_AUTHORS


def post_ip_from_row(row: dict[str, Any]) -> str:
    for key in ("post_ip", "author_ip", "writer_ip", "ip"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def comment_author_ip_dialogue_facts(row: dict[str, Any], idn: dict[str, Any]) -> dict[str, Any]:
    """Find cases where anonymous comment authors need IP-aware dialogue review."""
    post_author = str(row.get("post_author") or row.get("author") or "").strip()
    post_ip = post_ip_from_row(row)
    metadata = comment_metadata_from_row(row)
    mismatch_records: list[dict[str, Any]] = []
    unverified_author_match_records: list[dict[str, Any]] = []
    suspicious_post_author_role_records: list[dict[str, Any]] = []
    post_author_records: list[dict[str, Any]] = []
    independent_records: list[dict[str, Any]] = []

    for rec in metadata:
        author = str(rec.get("author") or "").strip()
        ip = str(rec.get("ip") or "").strip()
        speaker = str(rec.get("speaker") or "").strip().lower()
        is_post_author = bool(rec.get("is_post_author")) or speaker == "post_author"
        same_author_text = bool(post_author and author and author == post_author)
        generic_author = _is_generic_comment_author(author) or _is_generic_comment_author(post_author)
        confirmed_post_author_by_ip = bool(post_ip and ip and ip == post_ip)
        if is_post_author:
            post_author_records.append(rec)
        else:
            independent_records.append(rec)
        if post_ip and ip and ip != post_ip and same_author_text and generic_author:
            mismatch_records.append(rec)
            if is_post_author:
                suspicious_post_author_role_records.append(rec)
        if (
            bool(rec.get("post_author_match_unverified"))
            or (
                same_author_text
                and generic_author
                and not confirmed_post_author_by_ip
                and not (post_ip and ip and ip != post_ip)
            )
        ):
            unverified_author_match_records.append(rec)
            if is_post_author and rec not in suspicious_post_author_role_records:
                suspicious_post_author_role_records.append(rec)

    flags = idn.get("consistency_flags") if isinstance(idn.get("consistency_flags"), list) else []
    flag_set = {str(flag) for flag in flags}
    reason = str(idn.get("reason") or "")
    comment_answer_side_conversation = bool(
        "comment_answer_side_conversation" in flag_set
        or "comment_answer_not_targeting_post" in flag_set
        or "comment_title_answer_rejected" in flag_set
        or "side_conversation" in reason
        or "reply_to_comment" in reason
    )

    return {
        "post_ip": post_ip,
        "comment_author_ip_mismatch_count": len(mismatch_records),
        "comment_author_ip_mismatch_examples": [
            {
                "index": rec.get("index"),
                "comment_id": rec.get("comment_id"),
                "author": rec.get("author"),
                "ip": rec.get("ip"),
                "speaker": rec.get("speaker"),
                "is_post_author": rec.get("is_post_author"),
            }
            for rec in mismatch_records[:5]
        ],
        "comment_author_match_unverified_count": len(unverified_author_match_records),
        "comment_author_match_unverified_examples": [
            {
                "index": rec.get("index"),
                "comment_id": rec.get("comment_id"),
                "author": rec.get("author"),
                "ip": rec.get("ip"),
                "speaker": rec.get("speaker"),
                "is_post_author": rec.get("is_post_author"),
                "post_author_match_unverified": rec.get("post_author_match_unverified"),
            }
            for rec in unverified_author_match_records[:5]
        ],
        "suspicious_post_author_role_count": len(suspicious_post_author_role_records),
        "post_author_comment_count": len(post_author_records),
        "independent_commenter_count": len(independent_records),
        "post_author_comment_not_independent_evidence": "post_author_comment_not_independent_evidence" in flag_set,
        "comment_answer_side_conversation": comment_answer_side_conversation,
    }


def _comment_context_line_from_metadata(index: int, rec: dict[str, Any]) -> str:
    parts = [
        f"#{int(rec.get('index') if rec.get('index') is not None else index) + 1}",
        f"speaker={rec.get('speaker') or rec.get('author') or 'unknown'}",
    ]
    if rec.get("author"):
        parts.append(f"author={rec.get('author')}")
    if rec.get("is_post_author"):
        parts.append("role=post_author")
    elif rec.get("post_author_match_unverified"):
        parts.append("role=author_match_unverified")
    if rec.get("ip"):
        parts.append(f"ip={rec.get('ip')}")
    if rec.get("reply_level") not in (None, "", 0, "0"):
        parts.append(f"reply_level={rec.get('reply_level')}")
    reply_to = rec.get("reply_to_comment_id") or rec.get("reply_to")
    if reply_to:
        parts.append(f"reply_to={reply_to}")
    if rec.get("comment_id"):
        parts.append(f"comment_id={rec.get('comment_id')}")
    return " ".join(str(part) for part in parts if part not in (None, ""))


def comment_context_lines_from_row(row: dict[str, Any]) -> tuple[list[str], str]:
    raw = row.get("comment_context_lines")
    if isinstance(raw, list):
        lines = [str(item) for item in raw if str(item or "").strip()]
        if lines:
            return lines, "row.comment_context_lines"

    metadata = comment_metadata_from_row(row)
    if metadata:
        return [
            _comment_context_line_from_metadata(index, rec)
            for index, rec in enumerate(metadata)
        ], "reconstructed_from_comment_metadata"

    return [], "missing"


def _comment_text_for_dialogue(comment: Any) -> str:
    if isinstance(comment, dict):
        text = comment.get("content") or comment.get("text") or ""
    else:
        text = comment
    return " ".join(str(text or "").split())


def comment_dialogue_context_lines_from_row(row: dict[str, Any]) -> tuple[list[str], str]:
    raw = row.get("comment_dialogue_context_lines")
    if isinstance(raw, list):
        lines = [str(item) for item in raw if str(item or "").strip()]
        if lines:
            return lines, "row.comment_dialogue_context_lines"

    comments = row.get("comments") if isinstance(row.get("comments"), list) else []
    metadata = comment_metadata_from_row(row)
    meta_by_index = {
        int(rec.get("index") or 0): rec
        for rec in metadata
        if isinstance(rec, dict)
    }
    lines: list[str] = []
    for index, comment in enumerate(comments[:15]):
        text = _comment_text_for_dialogue(comment)
        if not text:
            continue
        if len(text) > 140:
            text = text[:140].rstrip() + "..."
        rec = meta_by_index.get(index, {})
        prefix = _comment_context_line_from_metadata(index, rec) if rec else f"#{index + 1} speaker=unknown"
        lines.append(f"{prefix} text={text}")
    if lines:
        source = "reconstructed_from_comment_metadata_and_comments" if metadata else "reconstructed_from_comments_only"
        return lines, source

    return [], "missing"


def identity(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("analysis_result", {}).get("identity", {}) or {}


def content_blocks_from_row(row: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = row.get("content_blocks")
    if not isinstance(blocks, list):
        return []
    out: list[dict[str, Any]] = []
    for block in blocks:
        if isinstance(block, dict):
            block_type = str(block.get("type") or "").strip() or ("image" if block.get("url") else "text")
            rec: dict[str, Any] = {"type": block_type}
            text = str(block.get("text") or block.get("content") or "").strip()
            url = str(block.get("url") or block.get("image_url") or block.get("src") or "").strip()
            if text:
                rec["text"] = text
            if url:
                rec["url"] = url
            if rec.get("text") or rec.get("url"):
                out.append(rec)
        elif isinstance(block, str):
            text = block.strip()
            if text:
                out.append({"type": "text", "text": text})
    return out


def image_urls_from_row(row: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []

    def push(raw: Any) -> None:
        url = str(raw or "").strip()
        if url and url not in seen:
            seen.add(url)
            urls.append(url)

    raw_urls = row.get("image_urls")
    if isinstance(raw_urls, list):
        for url in raw_urls:
            push(url)
    for block in content_blocks_from_row(row):
        block_type = str(block.get("type") or "").strip().lower()
        url = str(block.get("url") or "").strip()
        if block_type in {"image", "img", "photo", "picture"} or re.search(
            r"\.(?:png|jpe?g|gif|webp)(?:[?#].*)?$", url, re.I
        ):
            push(url)
    return urls


def image_count_from_row(row: dict[str, Any]) -> int:
    raw = row.get("image_count")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = -1
    if value >= 0:
        return value
    return len(image_urls_from_row(row))


def image_evidence_catalog_from_identity(idn: dict[str, Any]) -> list[dict[str, Any]]:
    catalog = idn.get("image_evidence_catalog")
    if not isinstance(catalog, list):
        return []
    return [item for item in catalog if isinstance(item, dict)]


def official_title(idn: dict[str, Any]) -> str | None:
    novel = idn.get("novel_identity") or {}
    title = novel.get("official_title")
    if title:
        return str(title)
    primary = idn.get("primary_work") or {}
    title = primary.get("official_title")
    return str(title) if title else None


def source_tier(idn: dict[str, Any]) -> str | None:
    primary = idn.get("primary_work") or {}
    if primary.get("source_tier"):
        return str(primary.get("source_tier"))
    candidates = idn.get("title_candidates")
    if isinstance(candidates, list) and candidates:
        tier = candidates[0].get("source_tier") if isinstance(candidates[0], dict) else None
        return str(tier) if tier else None
    return None


def official_detail_url(idn: dict[str, Any]) -> str | None:
    novel = idn.get("novel_identity") or {}
    url = novel.get("heretic_url") if isinstance(novel, dict) else None
    if url:
        return str(url)
    primary = idn.get("primary_work") or {}
    url = primary.get("heretic_url") if isinstance(primary, dict) else None
    return str(url) if url else None


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


def has_any(text: str, needles: Iterable[str]) -> bool:
    return any(needle in text for needle in needles)


def compact_match_text(value: Any) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", as_text(value)).lower()


def is_novel_detail_url(url: str) -> bool:
    try:
        parsed = urlparse(str(url or "").strip())
    except Exception:
        return False
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    query = parse_qs(parsed.query)
    if "novelpia.com" in host:
        return bool(re.search(r"/novel/\d+", path))
    if "munpia.com" in host:
        return bool(
            re.search(r"/novel/\d+", path)
            or re.search(r"/novel/detail/\d+", path)
            or ("novel.munpia.com" in host and re.fullmatch(r"/\d+", path))
            or (
                str((query.get("menu") or [""])[0]).lower() == "novel"
                and bool(query.get("id"))
            )
        )
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
    try:
        host = urlparse(str(url or "").strip()).netloc.lower()
    except Exception:
        return False
    if not any(
        domain in host
        for domain in (
            "novelpia.com",
            "munpia.com",
            "series.naver.com",
            "page.kakao.com",
            "ridibooks.com",
            "joara.com",
        )
    ):
        return False
    return not is_novel_detail_url(url)


def evidence_catalog_support_counts(row: dict[str, Any], idn: dict[str, Any], resolved: str | None) -> dict[str, int]:
    """Count direct public support from structured evidence catalog fields.

    Some post-fix reruns preserve search hits in `identity.search_evidence_catalog`
    while the generated reason still contains stale `official_urls=0` counters.
    The qualitative labeler should use both public surfaces.
    """
    resolved_norm = compact_match_text(resolved or "")
    if not resolved_norm:
        return {"official_urls": 0, "search_snippets": 0, "platform_non_detail_urls": 0}

    official_tiers = {"official_detail", "official_search", "novel_platform"}
    official_urls: set[str] = set()
    platform_non_detail_urls: set[str] = set()
    search_snippet_keys: set[tuple[str, str]] = set()

    for item in evidence_catalog(row, idn, max_items=200):
        url = str(item.get("url") or "").strip()
        title = item.get("official_title") or ""
        snippet = item.get("snippet") or ""
        source_tier = str(item.get("source_tier") or "").strip().lower()
        sections = item.get("source_sections") or []
        searchable_norm = compact_match_text(" ".join([as_text(title), as_text(snippet)]))
        if resolved_norm not in searchable_norm:
            continue
        if snippet or "identity.search_evidence_catalog" in sections:
            search_snippet_keys.add((url, as_text(title)[:160]))
        if url and is_platform_non_detail_url(url):
            platform_non_detail_urls.add(url)
        if url and source_tier in official_tiers and is_novel_detail_url(url):
            official_urls.add(url)

    return {
        "official_urls": len(official_urls),
        "search_snippets": len(search_snippet_keys),
        "platform_non_detail_urls": len(platform_non_detail_urls),
    }


def memory_query_quote_terms(title: str, body: str, comments: str) -> list[str]:
    """Extract packet-local quote/source-anchor terms for memory-query review.

    These are not title aliases. They are raw post fragments that a search
    snippet or official page needs to directly align with before a remembered
    quote/scene can be treated as Strong evidence.
    """
    text = " ".join([title, body, comments])
    if not has_any(text, MEMORY_QUERY_PATTERNS) or not has_any(text, QUOTE_OR_SCENE_RECALL_PATTERNS):
        return []

    candidates: list[str] = []

    def push(raw: Any) -> None:
        value = re.sub(r"\s+", " ", as_text(raw)).strip(" \t\r\n\"'“”‘’[](){}<>")
        norm = compact_match_text(value)
        if len(norm) < 8 or len(norm) > 80:
            return
        if any(part and part in norm for part in GENERIC_MEMORY_QUERY_PARTS):
            return
        if value not in candidates:
            candidates.append(value)

    for quoted in re.findall(r"[\"“”'‘’](.{4,80}?)[\"“”'‘’]", text):
        push(quoted)

    push(title)

    for chunk in re.split(r"[\n\r/|。.!?！？]+", " ".join([body, comments])):
        chunk = chunk.strip()
        if has_any(chunk, MEMORY_QUERY_PATTERNS):
            continue
        push(chunk)

    return candidates[:8]


def quote_alignment_support_count(row: dict[str, Any], idn: dict[str, Any], quote_terms: list[str]) -> int:
    term_norms = [compact_match_text(term) for term in quote_terms if compact_match_text(term)]
    if not term_norms:
        return 0
    direct_sections = {
        "identity.evidence",
        "identity.search_evidence_catalog",
        "identity.image_evidence_catalog",
    }
    support_keys: set[tuple[str, str]] = set()
    for item in evidence_catalog(row, idn, max_items=200):
        sections = {str(section) for section in (item.get("source_sections") or [])}
        if not (sections & direct_sections):
            continue
        searchable = " ".join(
            as_text(item.get(key))
            for key in (
                "official_title",
                "alias_or_mention",
                "snippet",
                "ocr_text",
                "visual_summary",
                "explicit_work_title",
                "work_cues",
            )
        )
        searchable_norm = compact_match_text(searchable)
        if not searchable_norm:
            continue
        for term_norm in term_norms:
            if term_norm and term_norm in searchable_norm:
                support_keys.add((str(item.get("url") or ""), term_norm))
    return len(support_keys)


def evidence_snippets(reason: str) -> list[str]:
    snippets: list[str] = []
    for marker in ("[근거 요약]", "official_title_evidence", "evidence_bucket", "[최종 종합]", "[근거 스코어]"):
        idx = reason.find(marker)
        if idx >= 0:
            snippets.append(excerpt(reason[idx:], 520))
    deduped = []
    for item in snippets:
        if item not in deduped:
            deduped.append(item)
    return deduped[:4]


def evidence_urls(idn: dict[str, Any]) -> list[str]:
    ev = idn.get("evidence")
    urls: list[str] = []

    def push(raw: Any) -> None:
        url = str(raw or "").strip()
        if url and url not in urls:
            urls.append(url)

    if isinstance(ev, list):
        for item in ev:
            if isinstance(item, dict):
                push(item.get("url") or item.get("href"))
    elif isinstance(ev, dict):
        for key in ("url", "href"):
            push(ev.get(key))

    novel = idn.get("novel_identity") or {}
    if isinstance(novel, dict):
        push(novel.get("heretic_url") or novel.get("url"))

    primary = idn.get("primary_work") or {}
    if isinstance(primary, dict):
        push(primary.get("heretic_url") or primary.get("url"))

    for key in ("title_candidates", "mentioned_works", "secondary_reference_works"):
        items = idn.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                push(item.get("heretic_url") or item.get("url") or item.get("href"))

    catalog = idn.get("search_evidence_catalog")
    if isinstance(catalog, list):
        for item in catalog:
            if isinstance(item, dict):
                push(item.get("url") or item.get("href"))
    image_catalog = idn.get("image_evidence_catalog")
    if isinstance(image_catalog, list):
        for item in image_catalog:
            if isinstance(item, dict):
                push(item.get("source_url") or item.get("url") or item.get("href"))
    return urls


def evidence_catalog(row: dict[str, Any], idn: dict[str, Any], max_items: int = 24) -> list[dict[str, Any]]:
    """Build a public evidence catalog from result fields that actually exist.

    The server-poc package usually lacks raw search hit payloads, so this catalog
    preserves candidate URL/title/source metadata without pretending to have full
    raw search snippets.
    """
    catalog: list[dict[str, Any]] = []
    seen: dict[tuple[Any, ...], dict[str, Any]] = {}

    def first(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
        for key in keys:
            value = item.get(key)
            if value not in (None, "", []):
                return value
        return None

    def push(section: str, index: int | None, item: Any) -> None:
        if not isinstance(item, dict):
            return
        url = first(item, ("heretic_url", "url", "href", "source_url"))
        title = first(item, ("official_title", "title", "canonical_value", "explicit_work_title"))
        alias = first(item, ("alias_or_mention", "alias", "mention", "text"))
        snippet = first(item, ("snippet", "summary", "description", "source_text", "ocr_text", "visual_summary"))
        query = first(item, ("query", "search_query"))
        source_tier = first(item, ("source_tier", "source", "engine", "evidence_type"))
        page_type = first(item, ("page_type", "type", "title_role"))
        reference_role = first(item, ("reference_role", "role", "title_role"))
        if not any((url, title, alias, snippet, query, source_tier, page_type, reference_role)):
            return

        key = (
            str(url or ""),
            str(title or ""),
            str(alias or ""),
            str(snippet or "")[:160],
            str(source_tier or ""),
            str(page_type or ""),
            str(reference_role or ""),
        )
        existing = seen.get(key)
        if existing is not None:
            sections = existing.setdefault("source_sections", [])
            if section not in sections:
                sections.append(section)
            return

        row_out = {
            "source_sections": [section],
            "source_index": index,
            "official_title": title,
            "alias_or_mention": alias,
            "url": url,
            "source_tier": source_tier,
            "page_type": page_type,
            "content_status": item.get("content_status"),
            "confidence": item.get("confidence"),
            "locked": item.get("locked"),
            "negative_evidence": item.get("negative_evidence"),
            "reference_role": reference_role,
            "snippet": excerpt(snippet, 360) if snippet else None,
            "query": query,
            "entity_type": item.get("entity_type"),
            "evidence_type": item.get("evidence_type"),
            "title_role": item.get("title_role"),
            "explicit_work_title": item.get("explicit_work_title"),
            "explicit_author_name": item.get("explicit_author_name"),
            "ocr_text": excerpt(item.get("ocr_text"), 360) if item.get("ocr_text") else None,
            "visual_summary": excerpt(item.get("visual_summary"), 360) if item.get("visual_summary") else None,
            "work_cues": item.get("work_cues") if isinstance(item.get("work_cues"), list) else None,
            "promotion_eligible": item.get("promotion_eligible"),
            "rank": item.get("rank"),
            "width": item.get("width"),
            "height": item.get("height"),
            "mime_type": item.get("mime_type"),
        }
        seen[key] = row_out
        catalog.append(row_out)

    evidence = idn.get("evidence")
    if isinstance(evidence, list):
        for idx, item in enumerate(evidence):
            push("identity.evidence", idx, item)
    elif isinstance(evidence, dict):
        push("identity.evidence", None, evidence)

    for section in ("novel_identity", "primary_work"):
        push(f"identity.{section}", None, idn.get(section))

    for section in (
        "search_evidence_catalog",
        "image_evidence_catalog",
        "title_candidates",
        "mentioned_works",
        "secondary_reference_works",
        "recommendation_candidates",
        "entity_mentions",
    ):
        items = idn.get(section)
        if isinstance(items, list):
            for idx, item in enumerate(items):
                push(f"identity.{section}", idx, item)

    analysis = (row.get("analysis_result") or {}).get("analysis") or {}
    if isinstance(analysis, dict):
        items = analysis.get("detected_titles")
        if isinstance(items, list):
            for idx, item in enumerate(items):
                push("analysis.detected_titles", idx, item)

    return catalog[:max_items]


def detect_generic_bridge(text: str, resolved: str | None) -> tuple[bool, str | None]:
    if resolved and resolved.strip() in GENERIC_TERMS:
        return True, f"resolved_title_generic:{resolved.strip()}"
    if resolved and re.fullmatch(r"(19|20)\d{2}", resolved.strip()):
        return True, f"resolved_title_year:{resolved.strip()}"
    if resolved and has_any(resolved, [" 용어", "시리즈", "장르"]):
        return True, f"resolved_title_generic_surface:{resolved.strip()}"
    for match in re.finditer(r"([^\s()]{1,24})\(([^)]{1,40})\)", text):
        outer = match.group(1).strip("[]{}<>:：,，.;；/\\|\"'“”‘’")
        inner = match.group(2)
        if has_any(inner, GENERIC_INNER_KEYWORDS):
            if outer in GENERIC_EXPLANATORY_OUTER_TERMS:
                continue
            if not resolved or inner in resolved or resolved in inner or len(resolved) <= 12:
                return True, f"parenthetical_generic_bridge:{match.group(0)}"
    return False, None


def extract_facts(row_index: int, row: dict[str, Any]) -> dict[str, Any]:
    idn = identity(row)
    reason = as_text(idn.get("reason") or " / ".join(as_text(v) for v in idn.get("reason_lines") or []))
    title = as_text(row.get("title"))
    body = as_text(row.get("content"))
    comments = as_text(row.get("comments"))
    resolved = official_title(idn)
    primary = idn.get("primary_work") or {}
    flags = idn.get("consistency_flags") if isinstance(idn.get("consistency_flags"), list) else []
    flag_set = {str(flag) for flag in flags}
    combined_public = " ".join([title, body, comments, reason, resolved or ""])

    official_title_evidence = parse_bool_field("official_title_evidence", reason)
    title_in_post = parse_bool_field("title_in_post", reason)
    post_spans = parse_int(r"post_spans=(\d+)", reason)
    search_snippets = parse_int(r"search_snippets=(\d+)", reason)
    official_urls = parse_int(r"official_urls=(\d+)", reason)
    reason_official_urls = official_urls
    degraded_queries = parse_int(r"degraded_queries:\s*(\d+)", reason)
    executed_queries = parse_int(r"executed_queries:\s*(\d+)", reason)
    catalog_counts = evidence_catalog_support_counts(row, idn, resolved)
    catalog_official_urls = catalog_counts["official_urls"]
    catalog_search_snippets = catalog_counts["search_snippets"]
    platform_non_detail_urls = catalog_counts.get("platform_non_detail_urls", 0)
    if catalog_official_urls > (official_urls or 0):
        official_urls = catalog_official_urls
    if catalog_search_snippets > (search_snippets or 0):
        search_snippets = catalog_search_snippets
    if official_title_evidence is not True and catalog_official_urls > 0:
        official_title_evidence = True

    search_degraded = bool(
        has_any(reason, ["엔진경고", "검색 저하", "search degraded", "upstream", "무결과"])
        or (degraded_queries or 0) > 0
    )
    timeout = has_any(reason.lower(), ["timeout", "timed out", "시간초과"])
    degraded_majority = bool(
        executed_queries and degraded_queries is not None and degraded_queries >= max(2, executed_queries // 2)
    )
    weak_evidence = bool(
        official_title_evidence is False
        or source_tier(idn) == "llm_only"
        or has_any(reason, ["evidence_type: community_mention"])
        or ("official_urls=0" in reason and (official_urls or 0) == 0)
        or official_urls == 0
    )
    alias_resolution_sources = (
        (idn.get("novel_identity") or {}).get("alias_resolution_sources") or []
        if isinstance(idn.get("novel_identity"), dict)
        else []
    )
    registry_anchor_only_alias_resolution = any(
        isinstance(src, dict)
        and (
            str(src.get("promotion_evidence_tier") or "") == "registry_anchor_only"
            or src.get("confidence_demoted_without_hard_evidence") is True
        )
        for src in alias_resolution_sources
    )
    strong_resolution = bool(
        idn.get("is_relevant") is True
        and resolved
        and (
            str((idn.get("novel_identity") or {}).get("confidence") or "").lower() == "high"
            or idn.get("work_resolution") == "resolved"
            or idn.get("identity_state") == "resolved_title"
        )
    )

    generic_bridge, generic_reason = detect_generic_bridge(combined_public, resolved)
    slang = idn.get("slang_insight") if isinstance(idn.get("slang_insight"), dict) else {}
    context_sources = idn.get("context_sources") or []
    if not isinstance(context_sources, list):
        context_sources = [str(context_sources)]
    context_source_set = {str(v).lower() for v in context_sources}
    content_blocks = content_blocks_from_row(row)
    image_urls = image_urls_from_row(row)
    image_count = image_count_from_row(row)
    image_evidence_catalog = image_evidence_catalog_from_identity(idn)
    has_image_evidence_catalog = bool(image_evidence_catalog)

    text_without_reason = " ".join([title, body, comments])
    comment_rows = row.get("comments") if isinstance(row.get("comments"), list) else []
    comment_metadata_rows = comment_metadata_from_row(row)
    comment_context_lines, comment_context_source = comment_context_lines_from_row(row)
    comment_dialogue_context_lines, comment_dialogue_context_source = comment_dialogue_context_lines_from_row(row)
    comments_without_author_metadata = bool(comment_rows and not comment_metadata_rows)
    comment_speaker_context_unavailable = bool(comment_rows and not comment_context_lines)
    comment_dialogue = comment_author_ip_dialogue_facts(row, idn)
    memory_query_resolved = bool(resolved and has_any(text_without_reason, MEMORY_QUERY_PATTERNS))
    quote_anchor_terms = memory_query_quote_terms(title, body, comments)
    quote_alignment_support = quote_alignment_support_count(row, idn, quote_anchor_terms)
    candidate_official_page_hits = max(
        catalog_official_urls or 0,
        official_urls or 0,
        1 if official_detail_url(idn) else 0,
    )
    quote_alignment_missing_for_memory_query = bool(
        memory_query_resolved
        and quote_anchor_terms
        and candidate_official_page_hits > 0
        and quote_alignment_support == 0
    )
    novel_cues = has_any(text_without_reason, NOVEL_CUE_KEYWORDS)
    multi_risk = bool(
        idn.get("work_resolution") in {"multi_work", "ambiguous", "adjacent"}
        or bool(idn.get("secondary_reference_works"))
        or bool(idn.get("comparison_target"))
        or bool(idn.get("recommendation_candidates"))
        or has_any(text_without_reason, MULTI_OR_ADJACENT_KEYWORDS)
    )
    trope_risk = bool(
        str(idn.get("discussion_type") or "") in {"author_talk", "trope", "genre", "meta"}
        or str(idn.get("primary_subject_type") or "") in {"author", "trope", "setting", "genre"}
        or has_any(text_without_reason, TROPE_OR_META_KEYWORDS)
    )
    contradiction = bool(
        (idn.get("is_relevant") is False and resolved)
        or (idn.get("is_relevant") is True and str(idn.get("discussion_type") or "") in {"noise", "off_topic"})
        or ("판정: 비관련" in reason and idn.get("is_relevant") is True)
        or ("판정: 관련" in reason and idn.get("is_relevant") is False)
    )
    vlm_ocr = bool(
        "image" in context_source_set
        or has_any(combined_public, ["OCR", "이미지", "[이미지 첨부]", "image"])
    )
    vlm_ocr_public_state_weak = bool(
        has_any(combined_public, IMAGE_OR_OCR_PATTERNS)
        and "image" not in context_source_set
    )
    worker = (row.get("run_meta") or {}).get("worker_id")
    batch_memory_exact_alias_rescued = "batch_memory_exact_alias_rescued" in flag_set
    title_surface_primary_candidate_rescued = "title_surface_primary_candidate_rescued" in flag_set
    notes_demoted_for_unresolved = "notes_demoted_for_unresolved" in flag_set
    no_or_search_only_anchor = bool(
        has_any(
            reason,
            [
                "grounding_anchor: none",
                "grounding_anchor: search_only",
                "anchor_found: none",
                "anchor=none",
                "작품 고유 근거 부족",
                "고유 앵커",
            ],
        )
    )
    critical_counter_but_resolved = bool(
        resolved
        and (
            "(critical)" in reason
            or "critical" in reason.lower()
            or "Verifier critical counter" in reason
            or "검증 반론" in reason
        )
    )
    search_absent_verified_title = has_any(reason, ["search_absent_verified_title", "검색에", "검색 부재"])
    direct_image_title = bool(
        vlm_ocr
        and (
            "이미지 OCR" in reason
            or "OCR 표기 작품명 후보" in reason
            or "이미지 표기 작품명 후보" in reason
            or "cover_title" in reason
        )
    )
    image_evidence_expected = bool(
        image_count > 0
        or image_urls
        or "image" in context_source_set
        or direct_image_title
    )
    image_evidence_catalog_missing = bool(image_evidence_expected and not has_image_evidence_catalog)
    final_heretic_url = official_detail_url(idn)
    official_url_missing_for_resolved = bool(resolved and not final_heretic_url)
    strong_title_alias_or_direct_evidence = bool(
        resolved
        and official_title_evidence is True
        and ((official_urls or 0) > 0 or (catalog_official_urls or 0) > 0 or final_heretic_url)
        and (
            title_in_post is True
            or has_any(
                reason,
                [
                    "grounding_anchor: title_abbrev_mention",
                    "title_abbrev_mention",
                    "title_anchor_exact_probe",
                    "title_anchor_official_probe",
                    "title_in_post: true",
                    "제목 약칭",
                    "제목 표면",
                ],
            )
            or (
                source_tier(idn) in {"official_detail", "official_search", "novel_platform"}
                and (post_spans or 0) > 0
            )
        )
    )
    reason_says_no_anchor_but_resolved = bool(
        resolved
        and no_or_search_only_anchor
        and not strong_title_alias_or_direct_evidence
    )
    final_semantic_reread_record = idn.get("_final_semantic_reread")
    final_semantic_reread_reviewed = bool(
        isinstance(final_semantic_reread_record, dict)
        or any(str(flag).startswith("final_semantic_reread_") for flag in flags)
        or "final_semantic_reread" in reason
    )
    final_semantic_reread_rejected = bool(
        "final_semantic_reread_rejected_resolution" in flag_set
        or "final_semantic_reread_reprocess_resolution" in flag_set
        or (
            isinstance(final_semantic_reread_record, dict)
            and str(final_semantic_reread_record.get("decision") or "").upper() in {"REJECT", "HOLD", "REPROCESS"}
        )
    )
    semantic_seed_or_context_only_risk = bool(
        has_any(
            " ".join([reason, " ".join(str(flag) for flag in flags), " ".join(str(src) for src in context_sources)]),
            [
                "semantic_seed_review",
                "surface_paraphrase",
                "context_only",
                "context_only_no_work_anchor",
                "작품 seed 제외",
                "표면 표현 해석",
                "직접 작품 앵커가 없어",
                "final_semantic_reread",
            ],
        )
    )
    final_semantic_reread_missing_for_semantic_seed = bool(
        resolved
        and semantic_seed_or_context_only_risk
        and not final_semantic_reread_reviewed
    )
    official_url_synopsis_or_branding_mismatch = bool(
        any(
            flag in flag_set
            for flag in (
                "official_detail_url_repaired_from_search",
                "official_detail_url_title_mismatch_cleared",
                "batch_memory_alias_stale_official_url_cleared",
                "stable_alias_official_url_recovered",
            )
        )
        or has_any(reason, ["대표 제목 불일치", "URL 대표 제목", "official_detail_url_repaired_from_search"])
    )

    search_flags = []
    if search_degraded:
        search_flags.append("search_degraded")
    if timeout:
        search_flags.append("search_timeout")
    if official_title_evidence is False:
        search_flags.append("weak_or_absent_official_title_evidence")
    if official_urls == 0:
        search_flags.append("zero_official_urls")
    if degraded_majority:
        search_flags.append("degraded_majority")

    bucket_reasons: dict[str, list[str]] = {}
    if search_degraded or timeout:
        bucket_reasons["search_degraded_or_timeout"] = search_flags or ["search_flag_present"]
    if strong_resolution and weak_evidence:
        bucket_reasons["weak_evidence_but_strong_resolution"] = [
            "resolved/high-confidence 판정이 약한 공식/검색 근거에 기대고 있다."
        ]
    if generic_bridge:
        bucket_reasons["generic_parenthetical_bridge"] = [generic_reason or "generic surface bridge"]
    if strong_resolution and (weak_evidence or source_tier(idn) == "llm_only"):
        bucket_reasons["unresolved_to_resolved"] = [
            "proxy: checkpoint lineage가 없어 직접 전후 비교는 불가하며, 약한 공개 근거 또는 llm_only 근거로 resolved 된 row다."
        ]
    if multi_risk:
        bucket_reasons["multi_work_or_adjacent_risk"] = ["multi/adjacent/comparison/recommendation 단서가 있다."]
    if trope_risk:
        bucket_reasons["trope_or_author_talk_risk"] = ["trope/genre/author/meta 단서가 있다."]
    if contradiction:
        bucket_reasons["reason_decision_contradiction"] = ["공개 reason과 final field 사이에 충돌이 있다."]
    if slang:
        store_reason = str(slang.get("store_reason") or "")
        alias_scope = str(slang.get("alias_scope") or "")
        if (
            slang.get("store_in_slang_db") is not None
            or store_reason
            or alias_scope
            or slang.get("canonical_work_alias") is not None
        ):
            bucket_reasons["slang_db_store_block_pending_family_noise"] = [
                f"store={slang.get('store_in_slang_db')}; scope={alias_scope}; reason={store_reason}"
            ]
    if comments_without_author_metadata:
        bucket_reasons["comments_without_author_metadata"] = [
            "댓글은 있지만 result row에 comment_metadata가 없어 본문 작성자와 댓글 작성자 관계를 검증할 수 없다."
        ]
    if comment_speaker_context_unavailable:
        bucket_reasons["comment_speaker_context_unavailable"] = [
            "댓글은 있지만 comment_context_lines가 없어 self-comment/타인-comment 구분 근거가 부족하다."
        ]
    if comment_dialogue["comment_author_ip_mismatch_count"]:
        bucket_reasons["comment_author_ip_mismatch_dialogue"] = [
            "익명/공통 author가 post author와 같지만 comment IP가 post IP와 달라 대화 화자 분리가 필요하다."
        ]
    if comment_dialogue["comment_author_match_unverified_count"]:
        bucket_reasons["comment_author_match_unverified_dialogue"] = [
            "익명/공통 author가 post author와 같지만 IP 확인이 없어 원글 작성자 댓글로 확정할 수 없다."
        ]
    if comment_dialogue["post_author_comment_not_independent_evidence"]:
        bucket_reasons["post_author_comment_not_independent_evidence"] = [
            "final/result flag가 원글 작성자 댓글은 독립 작품 근거가 아니라고 표시했다."
        ]
    if comment_dialogue["comment_answer_side_conversation"]:
        bucket_reasons["comment_answer_side_conversation"] = [
            "댓글 title 후보가 원글 직접 답변이 아니라 reply/side conversation일 가능성이 있다."
        ]
    if quote_alignment_missing_for_memory_query:
        bucket_reasons["quote_alignment_missing_for_memory_query"] = [
            "memory-query/대사·장면 회수 글에서 공식 후보 페이지는 있으나 원문 quote/source anchor를 직접 지지하는 snippet/catalog 근거가 없다."
        ]
    if memory_query_resolved:
        bucket_reasons["memory_query_resolved"] = [
            "원문이 기억 회수/작품 찾기 문맥인데 final title이 resolved로 고정됐다."
        ]
    if batch_memory_exact_alias_rescued and resolved and no_or_search_only_anchor:
        bucket_reasons["batch_memory_exact_alias_rescued_no_anchor"] = [
            "batch memory exact alias rescue가 no-anchor/search-only/고유근거 부족 상태에서 final title을 되살렸다."
        ]
    if critical_counter_but_resolved:
        bucket_reasons["critical_counter_but_resolved"] = [
            "Verifier critical/검증 반론 신호가 있는데 final title이 resolved로 유지됐다."
        ]
    if notes_demoted_for_unresolved and resolved:
        bucket_reasons["notes_demoted_then_resolved"] = [
            "앞단에서 unresolved demotion이 있었지만 후단에서 final title이 다시 resolved 됐다."
        ]
    if title_surface_primary_candidate_rescued:
        bucket_reasons["title_surface_primary_candidate_rescued"] = [
            "title surface primary candidate rescue가 final title 확정에 개입했다."
        ]
    if official_url_missing_for_resolved:
        bucket_reasons["official_url_missing_for_resolved"] = [
            "final title은 resolved지만 final novel_identity.heretic_url이 비어 있다."
        ]
    if official_url_synopsis_or_branding_mismatch:
        bucket_reasons["official_url_synopsis_or_branding_mismatch"] = [
            "공식 URL 대표 제목/검색 제목/최종 title 사이의 불일치 또는 검색 기반 URL 회복 flag가 있다."
        ]
    if reason_says_no_anchor_but_resolved:
        bucket_reasons["reason_says_no_anchor_but_resolved"] = [
            "reason은 no-anchor/search-only/고유근거 부족을 말하지만 final title은 resolved다."
        ]
    if final_semantic_reread_missing_for_semantic_seed:
        bucket_reasons["final_semantic_reread_missing_for_semantic_seed"] = [
            "semantic seed/context-only 위험이 있는데 final resolved title에 대한 최종 의미 재독해 기록이 없다."
        ]
    if final_semantic_reread_reviewed:
        bucket_reasons["final_semantic_reread_reviewed"] = [
            "final candidate가 원문/evidence와 맞는지 최종 의미 재독해를 거쳤다."
        ]
    if search_absent_verified_title and direct_image_title and resolved:
        bucket_reasons["search_absent_verified_title_direct_image_title"] = [
            "검색 부재 검증 반론이 있는 image/OCR-derived title 또는 visual title 후보가 resolved 상태에 남았다."
        ]
    if strong_resolution and official_title_evidence is True and (reason_official_urls or 0) == 0:
        bucket_reasons["official_title_evidence_true_but_zero_official_urls"] = [
            "reason은 official_title_evidence=true를 말하지만 공개 reason bucket의 official_urls가 0이다."
        ]
    if strong_resolution and platform_non_detail_urls > 0:
        bucket_reasons["platform_non_detail_url_used_near_official_evidence"] = [
            f"작품 상세가 아닌 플랫폼 URL {platform_non_detail_urls}건이 official evidence 주변에 섞였다."
        ]
    if vlm_ocr:
        bucket_reasons["VLM_OCR_involved"] = ["image/OCR 공개 context source가 개입되어 있다."]
    if image_evidence_catalog_missing:
        bucket_reasons["image_evidence_catalog_missing"] = [
            "image_count/image_urls/context_sources/direct OCR title 신호가 있으나 identity.image_evidence_catalog가 없다."
        ]
    if vlm_ocr_public_state_weak:
        bucket_reasons["vlm_ocr_public_state_weak"] = [
            "원문/reason에 이미지 또는 OCR 단서가 있으나 context_sources의 image 근거가 약하다."
        ]
    if worker is not None and (search_degraded or timeout):
        bucket_reasons["worker_or_shard_degraded_window"] = [
            f"worker={worker}; row별 timestamp/shard window 근거는 없다."
        ]
    if not resolved and (idn.get("is_relevant") is True or (idn.get("is_relevant") is False and novel_cues)):
        bucket_reasons["round2_false_negative_recall"] = [
            "작품/도메인 단서가 보이지만 title recall 또는 relevance가 충분히 해결되지 않은 row다."
        ]

    return {
        "row_index": row_index,
        "row": row,
        "identity": idn,
        "title": title,
        "body": body,
        "comments": comments,
        "reason": reason,
        "resolved_title": resolved,
        "official_title_evidence": official_title_evidence,
        "title_in_post": title_in_post,
        "post_spans": post_spans,
        "search_snippets": search_snippets,
        "official_urls": official_urls,
        "reason_official_urls": reason_official_urls,
        "catalog_official_urls": catalog_official_urls,
        "catalog_search_snippets": catalog_search_snippets,
        "platform_non_detail_urls": platform_non_detail_urls,
        "comment_count": len(comment_rows),
        "comment_metadata_count": len(comment_metadata_rows),
        "comment_context_line_count": len(comment_context_lines),
        "comment_dialogue_context_line_count": len(comment_dialogue_context_lines),
        "comment_metadata": comment_metadata_rows,
        "comment_context_lines": comment_context_lines,
        "comment_context_source": comment_context_source,
        "comment_dialogue_context_lines": comment_dialogue_context_lines,
        "comment_dialogue_context_source": comment_dialogue_context_source,
        "post_ip": comment_dialogue["post_ip"],
        "comment_author_ip_mismatch_count": comment_dialogue["comment_author_ip_mismatch_count"],
        "comment_author_ip_mismatch_examples": comment_dialogue["comment_author_ip_mismatch_examples"],
        "comment_author_match_unverified_count": comment_dialogue["comment_author_match_unverified_count"],
        "comment_author_match_unverified_examples": comment_dialogue["comment_author_match_unverified_examples"],
        "suspicious_post_author_role_count": comment_dialogue["suspicious_post_author_role_count"],
        "post_author_comment_count": comment_dialogue["post_author_comment_count"],
        "independent_commenter_count": comment_dialogue["independent_commenter_count"],
        "post_author_comment_not_independent_evidence": comment_dialogue["post_author_comment_not_independent_evidence"],
        "comment_answer_side_conversation": comment_dialogue["comment_answer_side_conversation"],
        "memory_query_resolved": memory_query_resolved,
        "memory_query_quote_terms": quote_anchor_terms,
        "quote_alignment_support_count": quote_alignment_support,
        "candidate_official_page_hits": candidate_official_page_hits,
        "quote_alignment_missing_for_memory_query": quote_alignment_missing_for_memory_query,
        "batch_memory_exact_alias_rescued": batch_memory_exact_alias_rescued,
        "title_surface_primary_candidate_rescued": title_surface_primary_candidate_rescued,
        "notes_demoted_for_unresolved": notes_demoted_for_unresolved,
        "no_or_search_only_anchor": no_or_search_only_anchor,
        "critical_counter_but_resolved": critical_counter_but_resolved,
        "search_absent_verified_title": search_absent_verified_title,
        "direct_image_title": direct_image_title,
        "final_heretic_url": final_heretic_url,
        "official_url_missing_for_resolved": official_url_missing_for_resolved,
        "official_url_synopsis_or_branding_mismatch": official_url_synopsis_or_branding_mismatch,
        "strong_title_alias_or_direct_evidence": strong_title_alias_or_direct_evidence,
        "reason_says_no_anchor_but_resolved": reason_says_no_anchor_but_resolved,
        "final_semantic_reread_record": final_semantic_reread_record if isinstance(final_semantic_reread_record, dict) else {},
        "final_semantic_reread_reviewed": final_semantic_reread_reviewed,
        "final_semantic_reread_rejected": final_semantic_reread_rejected,
        "semantic_seed_or_context_only_risk": semantic_seed_or_context_only_risk,
        "final_semantic_reread_missing_for_semantic_seed": final_semantic_reread_missing_for_semantic_seed,
        "degraded_queries": degraded_queries,
        "executed_queries": executed_queries,
        "search_degraded": search_degraded,
        "timeout": timeout,
        "degraded_majority": degraded_majority,
        "weak_evidence": weak_evidence,
        "registry_anchor_only_alias_resolution": registry_anchor_only_alias_resolution,
        "strong_resolution": strong_resolution,
        "generic_bridge": generic_bridge,
        "generic_reason": generic_reason,
        "slang": slang,
        "context_sources": context_sources,
        "consistency_flags": idn.get("consistency_flags") or [],
        "content_blocks": content_blocks,
        "image_urls": image_urls,
        "image_count": image_count,
        "image_evidence_catalog": image_evidence_catalog,
        "image_evidence_catalog_count": len(image_evidence_catalog),
        "has_image_evidence_catalog": has_image_evidence_catalog,
        "image_evidence_catalog_missing": image_evidence_catalog_missing,
        "novel_cues": novel_cues,
        "multi_risk": multi_risk,
        "trope_risk": trope_risk,
        "contradiction": contradiction,
        "vlm_ocr": vlm_ocr,
        "vlm_ocr_public_state_weak": vlm_ocr_public_state_weak,
        "worker": worker,
        "search_flags": search_flags,
        "bucket_reasons": bucket_reasons,
        "source_tier": source_tier(idn),
    }


def final_decision_fields(idn: dict[str, Any]) -> dict[str, Any]:
    novel = idn.get("novel_identity") or {}
    return {
        "is_relevant": idn.get("is_relevant"),
        "official_title": novel.get("official_title"),
        "confidence": novel.get("confidence"),
        "alias_resolution_sources": novel.get("alias_resolution_sources") or [],
        "discussion_type": idn.get("discussion_type"),
        "topicality": idn.get("topicality"),
        "work_resolution": idn.get("work_resolution"),
        "identity_state": idn.get("identity_state"),
        "anchor_type": idn.get("anchor_type"),
        "anchor_strength": idn.get("anchor_strength"),
        "consistency_flags": idn.get("consistency_flags") or [],
    }


def evidence_grade(facts: dict[str, Any]) -> str:
    if not facts["reason"]:
        return "Missing"
    if facts["official_title_evidence"] is True and (facts["official_urls"] or 0) > 0:
        return "Strong"
    if facts["title_in_post"] is True and not facts["weak_evidence"]:
        return "Medium"
    if facts["title_in_post"] is True or (facts["search_snippets"] or 0) > 0:
        return "Medium" if not facts["strong_resolution"] else "Weak"
    return "Weak"


def infer_post_intent(facts: dict[str, Any]) -> str:
    idn = facts["identity"]
    text = " ".join([facts["title"], facts["body"], facts["comments"]])
    if not text.strip():
        return f"원문 텍스트 부족; topicality={idn.get('topicality')}"
    if has_any(text, ["찾", "제목", "뭔 소설", "뭔작", "추천"]):
        intent = "작품 찾기 또는 추천"
    elif has_any(text, ["작가", "신작", "연재", "휴재"]):
        intent = "작가 또는 연재/출간 이야기"
    elif has_any(text, TROPE_OR_META_KEYWORDS):
        intent = "트로프/장르/설정 이야기"
    elif has_any(text, ["스포", "후기", "재밌", "별로", "전개", "읽", "하차"]):
        intent = "작품 감상 또는 반응"
    elif idn.get("is_relevant") is False:
        intent = "잡담 또는 비관련"
    else:
        intent = "일반 언급"
    return f"{intent}: {excerpt(facts['title'] or facts['body'], 120)}; topicality={idn.get('topicality')}"


def review_label(packet: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    idn = facts["identity"]
    bucket = packet["bucket"]
    original_bucket = bucket
    applied_review_bucket = bucket
    if bucket == "random_control":
        for candidate in RANDOM_CONTROL_RISK_BUCKET_PRIORITY:
            if candidate in facts["bucket_reasons"]:
                bucket = candidate
                applied_review_bucket = candidate
                break
    grade = evidence_grade(facts)
    missing_text = not (facts["title"].strip() or facts["body"].strip() or facts["comments"].strip())
    missing_final = "is_relevant" not in final_decision_fields(idn)
    direct_work_evidence = bool(
        facts["official_title_evidence"] is True
        and (facts["official_urls"] or 0) > 0
        and facts["title_in_post"] is True
        and facts.get("source_tier") in {"official_detail", "novel_platform"}
    )

    label = "ACCEPT"
    action = "no_action"
    reason_quality = "이 packet의 공개 근거 수준에서 reason 강도는 허용 가능하다."
    alignment = "공개 title/body/comment, reason, final decision이 자연어적으로 정합적이다."
    boundary = []

    if missing_text or missing_final or not facts["reason"].strip():
        label = "INFO_MISSING"
        action = "human_review"
        grade = "Missing"
        alignment = "리뷰에 필요한 title/body/comment, reason 또는 final field가 부족하다."
        reason_quality = "사용 가능한 공개 필드만으로 reason 품질을 평가할 수 없다."
    elif facts["contradiction"]:
        label = "REJECT"
        action = "re_judge"
        alignment = "final field와 공개 reason/relevance가 서로 충돌한다."
        reason_quality = "reason/final decision 충돌이 사용 가능한 근거보다 더 크다."
        boundary.append("reason_decision_contradiction")
    elif bucket in {"comments_without_author_metadata", "comment_speaker_context_unavailable"}:
        if facts["comment_count"] and (
            facts["comment_metadata_count"] == 0
            or facts["comment_context_line_count"] == 0
        ):
            label = "INFO_MISSING"
            grade = "Missing"
        else:
            label = "HOLD"
        action = "human_review"
        alignment = "댓글이 판단 근거가 될 수 있으나 작성자/IP/본문 작성자와의 관계가 packet 공개 필드에 부족하다."
        reason_quality = "댓글 대화 맥락을 작품 근거로 쓰려면 self-comment와 타인 comment를 분리해야 한다."
        boundary.append("comment_speaker_context_missing")
    elif bucket == "comment_author_ip_mismatch_dialogue":
        label = "HOLD"
        action = "human_review"
        alignment = "익명 author가 같아도 IP가 달라 원글 작성자 발화와 독립 댓글을 구분해야 한다."
        reason_quality = "댓글 화자 메타는 작품명 근거가 아니라 dialogue 해석 근거이므로, final title rescue에 쓰였는지 확인해야 한다."
        boundary.append("comment_author_ip_mismatch")
    elif bucket == "comment_author_match_unverified_dialogue":
        flags = set(str(flag) for flag in (idn.get("consistency_flags") or []) if flag is not None)
        context_only_closed = bool(
            not facts["resolved_title"]
            and idn.get("is_relevant") is False
            and (
                str(idn.get("title_resolution_state") or "") == "context_only"
                or "context_only_no_work_anchor" in flags
            )
            and facts["comment_metadata_count"] > 0
            and facts["comment_context_line_count"] > 0
        )
        if context_only_closed:
            label = "ACCEPT"
            action = "no_action"
            alignment = "익명 author match는 미확정으로 보존됐고, final decision도 title-null/context-only라 댓글을 독립 작품 근거로 과승격하지 않았다."
            reason_quality = "author_match_unverified는 dialogue hint로만 남고 final title rescue에 쓰이지 않았으므로 이 packet의 no-title guard는 승인 가능하다."
        else:
            label = "HOLD"
            action = "human_review"
            alignment = "익명 author 문자열만 같고 IP 확인이 없어 원글 작성자 댓글인지 확정할 수 없다."
            reason_quality = "author_match_unverified 댓글은 대화 맥락 힌트일 뿐 독립 작품 근거나 post_author 발화로 세면 안 된다."
        boundary.append("comment_author_match_unverified")
    elif bucket == "post_author_comment_not_independent_evidence":
        label = "HOLD" if facts["resolved_title"] else "ACCEPT"
        action = "human_review" if facts["resolved_title"] else "no_action"
        alignment = "원글 작성자 댓글은 독립적인 제3자 작품 근거로 세면 안 된다."
        reason_quality = "post_author 댓글은 보충/정정 맥락으로 읽고 title evidence 강도를 낮춰야 한다."
        boundary.append("post_author_comment_not_independent")
    elif bucket == "comment_answer_side_conversation":
        label = "HOLD"
        action = "re_judge"
        alignment = "댓글 제목 후보가 원글 질문의 직접 답변인지 댓글끼리의 대화인지 불확실하다."
        reason_quality = "reply_to/mention/comment_id 관계를 보지 않고 댓글 표면 title만 final로 올리면 과확정 위험이 있다."
        boundary.append("comment_answer_side_conversation")
    elif bucket == "quote_alignment_missing_for_memory_query":
        label = "HOLD"
        action = "human_review"
        alignment = "공식 후보 페이지는 있지만, 원문 대사/장면/기억 회수 anchor를 직접 지지하는 snippet/catalog 근거가 없다."
        reason_quality = "memory-query는 후보 작품 페이지 hit만으로 Strong title evidence가 되지 않으며, quote/source alignment가 없으면 자동 확정하지 않는다."
        boundary.append("quote_alignment_missing")
    elif bucket == "memory_query_resolved":
        label = "REJECT" if facts["weak_evidence"] else "HOLD"
        action = "re_judge"
        alignment = "원문은 기억 회수/작품 찾기 문맥인데 final title이 확정되어 자연어 의도와 맞지 않을 위험이 크다."
        reason_quality = "검색 표면어나 일반어를 작품명처럼 고정하지 말고 unresolvable_memory_query로 남겨야 한다."
        boundary.append("memory_query")
    elif bucket == "batch_memory_exact_alias_rescued_no_anchor":
        label = "REJECT" if facts["weak_evidence"] or facts["official_urls"] == 0 else "HOLD"
        action = "slang_db_review"
        alignment = "no-anchor/search-only 상태에서 batch memory alias가 final title을 되살려 원문 의미보다 강하게 확정했을 위험이 있다."
        reason_quality = "batch memory hit는 독립 evidence가 아니므로 원문 앵커나 공식 URL 없이 Strong resolution을 만들면 안 된다."
        boundary.append("batch_memory_alias_overreach")
    elif bucket == "critical_counter_but_resolved":
        reason_lower = facts["reason"].lower()
        minor_alias_counter = bool(
            facts["strong_title_alias_or_direct_evidence"]
            and "minor" in reason_lower
            and (
                "약칭" in facts["reason"]
                or "정식명" in facts["reason"]
                or "정식 제목" in facts["reason"]
            )
            and "(critical)" not in reason_lower
            and "(major)" not in reason_lower
        )
        if minor_alias_counter:
            label = "ACCEPT"
            action = "no_action"
            alignment = "검증 반론은 약칭과 정식명 차이를 minor note로 남긴 것이며, 공식/플랫폼 근거가 resolved title을 직접 지지한다."
            reason_quality = "minor alias normalization counter는 true contradiction과 분리해 승인 가능 표본으로 본다."
            boundary.append("minor_alias_normalization_counter")
        else:
            label = "REJECT" if facts["weak_evidence"] else "HOLD"
            action = "re_judge"
            alignment = "Verifier critical/검증 반론이 있는데 final title이 resolved로 유지되어 전문가 간 충돌 해소가 부족하다."
            reason_quality = "critical counter는 final reason에서 약화 근거로 반영되어야 하며, 직접 반박 evidence 없이는 확정하면 안 된다."
            boundary.append("verifier_critical_counter")
    elif bucket == "notes_demoted_then_resolved":
        label = "HOLD"
        action = "re_judge"
        alignment = "앞단 demotion 이후 후단 rescue가 final title을 다시 올린 경로이므로 단조성 검토가 필요하다."
        reason_quality = "demotion 사유가 해소됐는지 공개 evidence로 확인하기 전에는 대량 승인 근거로 쓰기 어렵다."
        boundary.append("demotion_then_rescue")
    elif bucket == "title_surface_primary_candidate_rescued":
        label = "REJECT" if facts["weak_evidence"] else "HOLD"
        action = "re_judge"
        alignment = "제목 표면 rescue가 일반어/문장 조각을 작품명처럼 고정했을 위험이 있다."
        reason_quality = "title surface는 공식 상세 URL과 직접 원문 앵커가 함께 있을 때만 강한 근거로 쓸 수 있다."
        boundary.append("title_surface_rescue")
    elif bucket == "official_url_missing_for_resolved":
        label = "HOLD"
        action = "re_search"
        alignment = "final title은 resolved지만 final URL이 비어 있어 identity/evidence 동기화가 닫히지 않았다."
        reason_quality = "resolved title은 공식 URL 또는 직접 search evidence와 함께 닫혀야 한다."
        boundary.append("official_url_missing")
    elif bucket == "official_url_synopsis_or_branding_mismatch":
        if facts["resolved_title"] and facts["final_heretic_url"] and facts["official_title_evidence"] is True and (facts["official_urls"] or 0) > 0:
            label = "ACCEPT"
            action = "no_action"
            alignment = "공식 URL 대표 제목 불일치 위험은 있었지만 같은 URL 검색 title/snippet 또는 수리 flag가 최종 title과 URL을 정합적으로 지지한다."
            reason_quality = "fetch/page title이 시놉시스나 플랫폼 브랜딩으로 잡힌 케이스는 same-URL 검색 근거와 함께 평가해야 하며, 이 packet은 공개 근거상 수리 완료로 본다."
        else:
            label = "HOLD"
            action = "re_search"
            alignment = "공식 URL 대표 제목 불일치 또는 검색 기반 URL 회복 경로가 남아 있어 URL evidence를 별도 재확인해야 한다."
            reason_quality = "title correctness와 official URL strength를 분리하고, same-URL 검색 title/snippet이 직접 작품명을 지지하는지 확인해야 한다."
        boundary.append("official_url_synopsis_or_branding_mismatch")
    elif facts.get("registry_anchor_only_alias_resolution") and facts["strong_resolution"] and facts["weak_evidence"]:
        label = "HOLD"
        action = "re_judge"
        alignment = "등록 약칭 provenance는 남아 있지만 promotion_evidence_tier=registry_anchor_only라 공식/직접 근거 없이 resolved 결론을 승인하기 어렵다."
        reason_quality = "registry alias는 회수 단서이지 hard evidence가 아니므로 final decision을 Medium/HOLD로 검토해야 한다."
        boundary.append("registry_anchor_only_alias_resolution")
    elif bucket == "reason_says_no_anchor_but_resolved":
        label = "REJECT"
        action = "re_judge"
        alignment = "reason은 no-anchor/고유근거 부족을 말하지만 final title은 resolved라 자연어 근거와 결론이 충돌한다."
        reason_quality = "reason 내부 반론이 결론보다 약하게 처리되어 evidence보다 강한 final decision이 됐다."
        boundary.append("no_anchor_resolved")
    elif bucket == "final_semantic_reread_missing_for_semantic_seed":
        label = "REJECT" if facts["weak_evidence"] else "HOLD"
        action = "re_judge"
        alignment = "semantic seed/context-only 위험이 있는데 final resolved title이 최종 의미 재독해 없이 남아 자연어 의도보다 검색/alias가 강해졌을 수 있다."
        reason_quality = "검색 전 의미 재독해와 별도로, 후단에서 살아남은 final candidate도 원문 title/body/comment/evidence로 다시 확인해야 한다."
        boundary.append("final_semantic_reread_missing")
    elif bucket == "final_semantic_reread_reviewed":
        if facts["final_semantic_reread_rejected"] and facts["resolved_title"]:
            label = "REJECT"
            action = "re_judge"
            alignment = "final semantic reread가 보류/기각 신호를 냈는데도 resolved title이 남아 있다."
            reason_quality = "최종 의미 재독해 결과가 final fields에 반영되지 않았는지 확인해야 한다."
        elif facts["final_semantic_reread_rejected"]:
            label = "ACCEPT"
            action = "no_action"
            alignment = "final semantic reread가 약한 후보를 낮췄고 final result가 그 결론을 반영했다."
            reason_quality = "기각/보류된 후보가 final title로 남지 않았으므로 targeted guard는 동작한 것으로 본다."
        else:
            label = "HOLD" if facts["weak_evidence"] else "ACCEPT"
            action = "human_review" if label == "HOLD" else "no_action"
            alignment = "final semantic reread 기록이 있으나 high-risk 의미 재독해 bucket이므로 과차단/미차단 표본 리뷰가 필요할 수 있다."
            reason_quality = "공개 reread 결과와 final field가 같은 방향인지 확인한다."
        boundary.append("final_semantic_reread")
    elif bucket == "search_absent_verified_title_direct_image_title":
        label = "REPROCESS"
        action = "human_review"
        alignment = "검색 부재 검증 반론이 있는 image/OCR title 후보가 final resolved 상태에 남아 브라우저/비전 확인이 필요하다."
        reason_quality = "VLM/OCR direct title은 검색/원문/공식 근거와 충돌하면 Strong evidence가 아니라 visual conflict evidence다."
        boundary.append("visual_ocr_contradiction")
    elif bucket == "official_title_evidence_true_but_zero_official_urls":
        label = "HOLD"
        action = "re_search"
        alignment = "reason의 official_title_evidence=true와 official_urls=0이 함께 나타나 근거 강도가 일관되지 않다."
        reason_quality = "공식 상세 URL이 없으면 Strong evidence로 올리지 말고 URL/evidence bucket을 재확인해야 한다."
        boundary.append("official_evidence_count_mismatch")
    elif bucket == "platform_non_detail_url_used_near_official_evidence":
        if (
            facts["strong_title_alias_or_direct_evidence"]
            and facts["final_heretic_url"]
            and (facts["official_urls"] or 0) > 0
            and (facts["catalog_official_urls"] or 0) > 0
        ):
            label = "ACCEPT"
            action = "no_action"
            alignment = "플랫폼 non-detail URL이 주변에 섞였지만 final URL과 catalog official URL이 작품 상세를 직접 지지하고 원문 title/alias 앵커도 있다."
            reason_quality = "non-detail URL은 근거에서 분리하되, 별도의 official detail URL과 직접 title evidence가 충분하면 자동 re-search로 보내지 않는다."
        else:
            label = "HOLD"
            action = "re_search"
            alignment = "작품 상세가 아닌 플랫폼 URL이 official evidence 주변에 섞여 근거 강도를 부풀릴 수 있다."
            reason_quality = "author/list/search/comment-tab URL은 작품 상세 URL과 분리해 세야 한다."
        boundary.append("official_url_detail_filter")
    elif bucket == "image_evidence_catalog_missing":
        label = "REPROCESS"
        action = "re_run" if facts["image_count"] or facts["image_urls"] else "human_review"
        alignment = "이미지/VLM/OCR 근거가 판정에 들어간 것으로 보이지만 공개 image_evidence_catalog가 없어 자연어 리뷰가 원문 이미지 근거를 검증할 수 없다."
        reason_quality = "이미지 로딩, OCR 텍스트, VLM 요약, 명시 작품명/작가명은 packet의 공개 evidence로 남아야 하며 없으면 승인 근거로 쓰지 않는다."
        boundary.append("image_evidence_catalog_missing")
    elif bucket == "vlm_ocr_public_state_weak":
        label = "REPROCESS"
        action = "human_review"
        alignment = "이미지/OCR 단서가 보이지만 공개 context source가 약해 브라우저/비전 직접 확인 없이는 승인하기 어렵다."
        reason_quality = "이미지 로딩/스크린샷/VLM 결과를 별도 evidence로 남긴 뒤 재판정해야 한다."
        boundary.append("vlm_ocr_public_state_weak")
    elif bucket == "generic_parenthetical_bridge":
        if idn.get("is_relevant") is False and not facts["resolved_title"]:
            label = "ACCEPT"
            action = "no_action"
            alignment = "generic bridge 위험이 있었지만 final decision이 비관련/title null로 닫혀 판정 근거가 과확정되지 않았다."
            reason_quality = "generic bridge가 최종 작품 확정으로 쓰이지 않았으므로 이 packet은 승인 가능하다."
        elif facts["resolved_title"] in GENERIC_TERMS or re.fullmatch(r"(19|20)\d{2}", facts["resolved_title"] or ""):
            label = "REJECT"
            action = "re_judge"
            alignment = "resolved_title이 근거로 지지되는 작품명이 아니라 일반어/공통 표면형에 가깝다."
            reason_quality = "generic bridge는 직접 title 또는 공식 근거보다 약한 근거로 취급해야 한다."
        elif direct_work_evidence and not facts["search_degraded"] and not facts["degraded_majority"]:
            label = "ACCEPT"
            action = "no_action"
            alignment = "generic bridge 위험은 있었지만 원문 title span과 공식/플랫폼 상세 근거가 직접 작품 결론을 지지한다."
            reason_quality = "generic bridge가 아니라 직접 작품 근거가 결론을 지지하므로 이 packet은 승인 가능하다."
        elif direct_work_evidence and facts["search_degraded"]:
            label = "HOLD"
            action = "re_search"
            alignment = "직접 작품 근거는 있으나 검색 degraded 신호가 함께 있어 fresh search 확인 전 대량 승인 근거로 쓰기 어렵다."
            reason_quality = "generic bridge 자체보다 degraded search lineage가 남은 위험이므로 재검색 큐로 보낸다."
        else:
            label = "HOLD"
            action = "re_judge"
            alignment = "괄호/generic bridge가 직접 작품 근거보다 판정을 더 강하게 만든 위험이 있다."
            reason_quality = "generic bridge는 직접 title 또는 공식 근거보다 약한 근거로 취급해야 한다."
        boundary.append("generic_term")
    elif bucket == "worker_or_shard_degraded_window":
        label = "REPROCESS" if facts["weak_evidence"] else "HOLD"
        action = "re_search"
        alignment = "검색 degradation이 worker와 연결되지만 row별 shard/timestamp window 근거가 없다."
        reason_quality = "더 강한 run lineage 근거 없이 degraded-window 판정을 승인하지 않는다."
        boundary.append("search_degraded")
    elif bucket == "VLM_OCR_involved" and facts["weak_evidence"]:
        label = "REPROCESS"
        action = "re_run"
        alignment = "Image/OCR context가 개입했고 공개 근거가 약하다."
        reason_quality = "OCR/VLM 개입 row는 승인 전에 더 강한 field-level 근거가 필요하다."
        boundary.append("vlm_ocr")
    elif facts["strong_resolution"] and facts["weak_evidence"]:
        label = "REPROCESS" if facts["search_degraded"] and facts["degraded_majority"] else "HOLD"
        action = "re_search"
        alignment = "resolved/high-confidence 판정이 공개 field의 공식 근거로 직접 지지되지 않는다."
        reason_quality = "reason이 보이는 근거보다 강하므로 그럴듯한 후보로만 두고 승인하지 않는다."
        boundary.append("weak_evidence_strong_resolution")
    elif (
        idn.get("is_relevant") is True
        and not facts["resolved_title"]
        and str(idn.get("work_resolution") or "").strip().lower() in {"", "none", "unresolved", "unresolved_work"}
        and grade == "Weak"
        and (
            facts["search_degraded"]
            or facts["weak_evidence"]
            or facts["multi_risk"]
            or facts["trope_risk"]
            or (facts["official_urls"] == 0)
        )
    ):
        combined_text = " ".join([facts["title"], facts["body"], facts["comments"]]).lower()
        virtual_battle = has_any(combined_text, VIRTUAL_BATTLE_REVIEW_TERMS)
        label = "HOLD"
        action = "re_judge" if virtual_battle else "human_review"
        alignment = "관련 판정이지만 title null/unresolved이고 공개 근거가 Weak라서 품질 승인 근거로 쓰기 어렵다."
        reason_quality = "작품명 확정 없이 character/trope/adjacent 맥락만 남은 row는 자동 ACCEPT가 아니라 정책 검토 대상으로 둔다."
        boundary.append("weak_unresolved_boundary")
        if virtual_battle:
            boundary.append("character_virtual_battle")
    elif bucket == "round2_false_negative_recall":
        benign_title_null_boundary = bool(
            idn.get("is_relevant") is False
            and not facts["resolved_title"]
            and not facts["memory_query_resolved"]
            and not facts["memory_query_quote_terms"]
            and str(idn.get("title_resolution_state") or "") in {"adjacent", "context_only"}
            and str(idn.get("discussion_type") or "") in {"trope_discussion", "noise", "community_talk"}
        )
        if benign_title_null_boundary:
            label = "ACCEPT"
            action = "no_action"
            alignment = "소설/장르 단어는 있지만 final decision이 title-null adjacent/context-only로 닫혀 특정 작품 recall 실패가 아니라 경계 담론으로 처리됐다."
            reason_quality = "false-negative 후보로 과표집됐지만, 공개 reason과 final scope가 단일 작품 확정을 보류하는 방향으로 정합적이다."
        else:
            label = "REPROCESS" if idn.get("is_relevant") is True else "HOLD"
            action = "re_search" if label == "REPROCESS" else "human_review"
            alignment = "작품/도메인 단서가 보이지만 title recall 또는 relevance가 충분히 해결되지 않았다."
            reason_quality = "reason이 alias/work 근거를 과소 해결했을 수 있다."
        boundary.append("false_negative_recall")
    elif bucket == "slang_db_store_block_pending_family_noise":
        slang = facts["slang"] or {}
        store_reason = str(slang.get("store_reason") or "")
        alias_scope = str(slang.get("alias_scope") or "")
        flags = {str(flag or "") for flag in facts.get("consistency_flags") or []}
        store_blocked = slang.get("store_in_slang_db") is False
        surface_form_resolved_by_official_detail = bool(
            store_blocked
            and facts["resolved_title"]
            and facts["final_heretic_url"]
            and ((facts["official_urls"] or 0) > 0 or (facts["catalog_official_urls"] or 0) > 0)
            and (
                "official_detail_title_preferred_over_surface_form" in flags
                or "surface_form_duplicate_reference_pruned" in flags
            )
            and (
                alias_scope not in {"", "pure_work_alias"}
                or store_reason
                in {
                    "character_attached_composite",
                    "title_variant_surface",
                    "exact_title_not_alias",
                    "not_pure_work_alias",
                    "ocr_surface_variant",
                }
            )
        )
        if surface_form_resolved_by_official_detail:
            label = "ACCEPT"
            action = "no_action"
            alignment = "slang/OCR 표면형은 저장 차단됐고 official detail URL과 final title이 직접 지지되어 alias 오염 없이 닫혔다."
            reason_quality = "저장 차단된 표면형을 community alias로 승인하지 않고, official detail title preferred/pruned flag로 evidence boundary를 분리했다."
            boundary.append("slang_db_subtype_closed")
        elif store_reason != "pure_work_alias" or alias_scope not in {"", "pure_work_alias"}:
            label = "HOLD"
            action = "slang_db_review"
            alignment = "alias 경로를 승인하기 전에 slang_db 영향의 subtype 리뷰가 필요하다."
            reason_quality = "alias 저장 metadata만으로 자연어 판정을 승인하기에는 부족하다."
            boundary.append("slang_db_subtype")
    elif facts["multi_risk"] or facts["trope_risk"]:
        if idn.get("is_relevant") is True and facts["resolved_title"]:
            label = "HOLD" if grade in {"Weak", "Medium"} else "ACCEPT"
            action = "human_review" if label == "HOLD" else "no_action"
            alignment = "boundary/meta/multi-work 단서가 있어 work-level resolution에는 더 강한 확인이 필요하다."
            reason_quality = "직접 작품 근거가 강하지 않으면 boundary case를 대량 승인에서 제외한다."
            boundary.append("boundary_case")

    if facts["search_degraded"]:
        boundary.append("search_degraded")
    if facts["multi_risk"]:
        boundary.append("multi_or_adjacent")
    if facts["trope_risk"]:
        boundary.append("trope_or_author_talk")
    if facts["vlm_ocr"]:
        boundary.append("vlm_ocr")
    if facts["image_evidence_catalog_missing"]:
        boundary.append("image_evidence_catalog_missing")
    if facts["slang"]:
        boundary.append("slang_db")
    if facts.get("registry_anchor_only_alias_resolution"):
        boundary.append("registry_anchor_only_alias_resolution")
    if facts["generic_bridge"]:
        boundary.append("generic_parenthetical_bridge")

    if not boundary:
        boundary.append("none_detected")

    slang = facts["slang"] or {}
    if slang:
        slang_effect = (
            f"term={slang.get('detected_term')}; decoded={slang.get('decoded_term')}; "
            f"store={slang.get('store_in_slang_db')}; scope={slang.get('alias_scope')}; "
            f"reason={slang.get('store_reason')}"
        )
    else:
        slang_effect = "해당 없음 또는 추출 안 됨"

    return {
        "run_id": packet["run_id"],
        "packet_id": packet["packet_id"],
        "round": packet["round"],
        "bucket": original_bucket,
        "applied_review_bucket": applied_review_bucket,
        "sample_seed": packet["sample_seed"],
        "row_index": packet["line_number"],
        "post_id": packet["post_id"],
        "label": label,
        "action": action,
        "evidence_grade": grade,
        "post_intent": infer_post_intent(facts),
        "model_decision": (
            f"relevance={idn.get('is_relevant')}; resolved_title={facts['resolved_title']}; "
            f"discussion_type={idn.get('discussion_type')}; "
            f"work_resolution={idn.get('work_resolution')}; "
            f"confidence={(idn.get('novel_identity') or {}).get('confidence')}"
        ),
        "evidence_alignment": alignment,
        "reason_quality": reason_quality,
        "boundary_risk": sorted(set(boundary)),
        "slang_db_effect": slang_effect,
        "reviewer_note": (
            f"자연어 의미 리뷰. 적용 bucket={applied_review_bucket}. Bucket 근거: "
            f"{'; '.join(facts['bucket_reasons'].get(applied_review_bucket) or packet.get('bucket_match_reasons') or [])}. "
            f"Label={label}; action={action}."
        ),
    }


def build_packet(packet_id: str, bucket: str, facts: dict[str, Any], result_path: Path) -> dict[str, Any]:
    row = facts["row"]
    idn = facts["identity"]
    slang = facts["slang"] or {}
    run_meta = row.get("run_meta") or {}
    result_rel = result_path.as_posix()
    risk_tags = sorted(set([bucket] + list(facts["bucket_reasons"].keys()) + facts["search_flags"]))
    if facts["generic_reason"]:
        risk_tags.append(facts["generic_reason"])
    return {
        "run_id": run_meta.get("run_id") or RUN_ID,
        "packet_id": packet_id,
        "round": ROUND_NAME,
        "bucket": bucket,
        "sample_seed": SEED,
        "source_path": result_rel,
        "result_source_path": result_rel,
        "checkpoint_row_index": None,
        "line_number": facts["row_index"],
        "post_id": row.get("post_id"),
        "gallery_id": row.get("gallery_id"),
        "url": row.get("url"),
        "title": facts["title"],
        "post_author": row.get("post_author") or row.get("author"),
        "post_ip": facts["post_ip"],
        "content_blocks": facts["content_blocks"],
        "image_urls": facts["image_urls"],
        "image_count": facts["image_count"],
        "body_excerpt": excerpt(row.get("content"), 720),
        "comment_excerpt": comments_excerpt(row, 480),
        "comment_metadata": facts["comment_metadata"],
        "comment_context_lines": facts["comment_context_lines"],
        "comment_context_source": facts["comment_context_source"],
        "comment_dialogue_context_lines": facts["comment_dialogue_context_lines"],
        "comment_dialogue_context_source": facts["comment_dialogue_context_source"],
        "resolved_title": facts["resolved_title"],
        "relevance": idn.get("is_relevant"),
        "final_decision_fields": final_decision_fields(idn),
        "reason": facts["reason"],
        "risk_tags": risk_tags,
        "bucket_match_reasons": facts["bucket_reasons"].get(bucket, []),
        "search_health_flags": facts["search_flags"],
        "evidence_urls": evidence_urls(idn),
        "evidence_snippets": evidence_snippets(facts["reason"]),
        "evidence_catalog": evidence_catalog(row, idn),
        "evidence_counts": {
            "official_title_evidence": facts["official_title_evidence"],
            "title_in_post": facts["title_in_post"],
            "post_spans": facts["post_spans"],
            "search_snippets": facts["search_snippets"],
            "official_urls": facts["official_urls"],
            "reason_official_urls": facts["reason_official_urls"],
            "catalog_search_snippets": facts["catalog_search_snippets"],
            "catalog_official_urls": facts["catalog_official_urls"],
            "platform_non_detail_urls": facts["platform_non_detail_urls"],
            "comment_count": facts["comment_count"],
            "comment_metadata_count": facts["comment_metadata_count"],
            "comment_context_line_count": facts["comment_context_line_count"],
            "comment_context_source": facts["comment_context_source"],
            "comment_dialogue_context_line_count": facts["comment_dialogue_context_line_count"],
            "comment_dialogue_context_source": facts["comment_dialogue_context_source"],
            "post_ip": facts["post_ip"],
            "comment_author_ip_mismatch_count": facts["comment_author_ip_mismatch_count"],
            "comment_author_match_unverified_count": facts["comment_author_match_unverified_count"],
            "suspicious_post_author_role_count": facts["suspicious_post_author_role_count"],
            "post_author_comment_count": facts["post_author_comment_count"],
            "independent_commenter_count": facts["independent_commenter_count"],
            "memory_query_resolved": facts["memory_query_resolved"],
            "memory_query_quote_terms": facts["memory_query_quote_terms"],
            "quote_alignment_support_count": facts["quote_alignment_support_count"],
            "candidate_official_page_hits": facts["candidate_official_page_hits"],
            "quote_alignment_missing_for_memory_query": facts["quote_alignment_missing_for_memory_query"],
            "executed_queries": facts["executed_queries"],
            "degraded_queries": facts["degraded_queries"],
            "batch_memory_exact_alias_rescued": facts["batch_memory_exact_alias_rescued"],
            "title_surface_primary_candidate_rescued": facts["title_surface_primary_candidate_rescued"],
            "notes_demoted_for_unresolved": facts["notes_demoted_for_unresolved"],
            "no_or_search_only_anchor": facts["no_or_search_only_anchor"],
            "critical_counter_but_resolved": facts["critical_counter_but_resolved"],
            "search_absent_verified_title": facts["search_absent_verified_title"],
            "direct_image_title": facts["direct_image_title"],
            "final_heretic_url": facts["final_heretic_url"],
            "official_url_missing_for_resolved": facts["official_url_missing_for_resolved"],
            "official_url_synopsis_or_branding_mismatch": facts["official_url_synopsis_or_branding_mismatch"],
            "reason_says_no_anchor_but_resolved": facts["reason_says_no_anchor_but_resolved"],
            "semantic_seed_or_context_only_risk": facts["semantic_seed_or_context_only_risk"],
            "final_semantic_reread_reviewed": facts["final_semantic_reread_reviewed"],
            "final_semantic_reread_rejected": facts["final_semantic_reread_rejected"],
            "final_semantic_reread_missing_for_semantic_seed": facts["final_semantic_reread_missing_for_semantic_seed"],
            "image_count": facts["image_count"],
            "image_url_count": len(facts["image_urls"]),
            "image_evidence_catalog_count": facts["image_evidence_catalog_count"],
            "image_evidence_catalog_missing": facts["image_evidence_catalog_missing"],
        },
        "prompt_public_fields": {
            "gallery_id": row.get("gallery_id"),
            "post_author": row.get("post_author") or row.get("author"),
            "post_ip": facts["post_ip"],
            "content_blocks": facts["content_blocks"],
            "image_urls": facts["image_urls"],
            "image_count": facts["image_count"],
            "comment_metadata": facts["comment_metadata"],
            "comment_context_lines": facts["comment_context_lines"],
            "comment_context_source": facts["comment_context_source"],
            "comment_dialogue_context_lines": facts["comment_dialogue_context_lines"],
            "comment_dialogue_context_source": facts["comment_dialogue_context_source"],
        },
        "result_public_fields": {
            **final_decision_fields(idn),
            "gallery_id": row.get("gallery_id"),
            "post_author": row.get("post_author") or row.get("author"),
            "post_ip": facts["post_ip"],
            "comment_metadata_count": facts["comment_metadata_count"],
            "comment_context_line_count": facts["comment_context_line_count"],
            "comment_context_source": facts["comment_context_source"],
            "comment_dialogue_context_line_count": facts["comment_dialogue_context_line_count"],
            "comment_dialogue_context_source": facts["comment_dialogue_context_source"],
            "comment_author_ip_mismatch_count": facts["comment_author_ip_mismatch_count"],
            "comment_author_match_unverified_count": facts["comment_author_match_unverified_count"],
            "memory_query_resolved": facts["memory_query_resolved"],
            "memory_query_quote_terms": facts["memory_query_quote_terms"],
            "quote_alignment_support_count": facts["quote_alignment_support_count"],
            "candidate_official_page_hits": facts["candidate_official_page_hits"],
            "quote_alignment_missing_for_memory_query": facts["quote_alignment_missing_for_memory_query"],
            "batch_memory_exact_alias_rescued": facts["batch_memory_exact_alias_rescued"],
            "title_surface_primary_candidate_rescued": facts["title_surface_primary_candidate_rescued"],
            "critical_counter_but_resolved": facts["critical_counter_but_resolved"],
            "final_heretic_url": facts["final_heretic_url"],
            "official_url_missing_for_resolved": facts["official_url_missing_for_resolved"],
            "official_url_synopsis_or_branding_mismatch": facts["official_url_synopsis_or_branding_mismatch"],
            "semantic_seed_or_context_only_risk": facts["semantic_seed_or_context_only_risk"],
            "final_semantic_reread_reviewed": facts["final_semantic_reread_reviewed"],
            "final_semantic_reread_rejected": facts["final_semantic_reread_rejected"],
            "final_semantic_reread_missing_for_semantic_seed": facts["final_semantic_reread_missing_for_semantic_seed"],
            "image_count": facts["image_count"],
            "image_url_count": len(facts["image_urls"]),
            "image_evidence_catalog_count": facts["image_evidence_catalog_count"],
            "image_evidence_catalog_missing": facts["image_evidence_catalog_missing"],
        },
        "vlm_ocr_fields": {
            "context_sources": facts["context_sources"],
            "mentioned_image": bool(has_any(" ".join([facts["title"], facts["body"], facts["reason"]]), ["이미지", "[이미지 첨부]", "image"])),
            "mentioned_ocr": bool("OCR" in facts["reason"]),
            "public_state_weak": facts["vlm_ocr_public_state_weak"],
            "image_urls": facts["image_urls"],
            "image_count": facts["image_count"],
            "image_evidence_catalog": facts["image_evidence_catalog"],
            "image_evidence_catalog_count": facts["image_evidence_catalog_count"],
            "image_evidence_catalog_missing": facts["image_evidence_catalog_missing"],
        },
        "final_semantic_reread_fields": {
            "semantic_seed_or_context_only_risk": facts["semantic_seed_or_context_only_risk"],
            "reviewed": facts["final_semantic_reread_reviewed"],
            "rejected_or_reprocess": facts["final_semantic_reread_rejected"],
            "missing_for_semantic_seed": facts["final_semantic_reread_missing_for_semantic_seed"],
            "record": facts["final_semantic_reread_record"],
        },
        "slang_db_fields": {
            "detected_term": slang.get("detected_term"),
            "decoded_term": slang.get("decoded_term"),
            "decode_verified": slang.get("decode_verified"),
            "canonical_work_alias": slang.get("canonical_work_alias"),
            "alias_scope": slang.get("alias_scope"),
            "store_in_slang_db": slang.get("store_in_slang_db"),
            "store_reason": slang.get("store_reason"),
        },
        "worker": run_meta.get("worker_id"),
        "shard": run_meta.get("shard_id") or run_meta.get("shard"),
        "timestamp": row.get("created_at") or run_meta.get("timestamp"),
        "limitations": [
            "리뷰는 공개 title/body/comment/reason/final 필드만 사용한다.",
            "server-poc 패키지에는 checkpoint lineage가 없다.",
            "raw search hit payload가 없으면 evidence_catalog는 후보 URL/title/source metadata까지만 보존한다.",
            "row별 raw search snippet은 대체로 없으므로 reason excerpt를 공개 evidence snippet으로 사용한다.",
        ],
    }


def select_round2(
    result_path: Path,
    review_dir: Path,
    target_scale: float,
    source_integrity_summary: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    rng = random.Random(SEED)
    existing_labels = [
        row
        for row in load_jsonl(review_dir / "review_labels.jsonl")
        if row.get("round") != ROUND_NAME and row.get("bucket") != "random_control"
    ]
    existing_post_ids = {str(row.get("post_id")) for row in existing_labels if row.get("post_id") is not None}
    targets = OrderedDict((bucket, max(1, int(count * target_scale))) for bucket, count in BUCKET_TARGETS.items())
    reservoir_size = {bucket: max(target * 8, target + 20) for bucket, target in targets.items()}
    seen = Counter()
    pools: dict[str, list[dict[str, Any]]] = {bucket: [] for bucket in targets}
    total_rows = 0

    for row_index, row in iter_json_array(result_path):
        total_rows = row_index
        post_id = row.get("post_id")
        if post_id is None or str(post_id) in existing_post_ids:
            continue
        facts = extract_facts(row_index, row)
        for bucket in targets:
            if bucket not in facts["bucket_reasons"]:
                continue
            seen[bucket] += 1
            pool = pools[bucket]
            if len(pool) < reservoir_size[bucket]:
                pool.append(facts)
            else:
                replace = rng.randrange(seen[bucket])
                if replace < reservoir_size[bucket]:
                    pool[replace] = facts

    bucket_order = {bucket: idx for idx, bucket in enumerate(targets)}
    selection_order = sorted(targets, key=lambda bucket: (seen.get(bucket, 0), bucket_order[bucket]))
    selected: list[tuple[str, dict[str, Any]]] = []
    selected_post_ids: set[str] = set()
    for bucket in selection_order:
        target = targets[bucket]
        candidates = pools[bucket][:]
        rng.shuffle(candidates)
        added = 0
        for facts in candidates:
            post_id = str(facts["row"].get("post_id"))
            if post_id in selected_post_ids:
                continue
            selected.append((bucket, facts))
            selected_post_ids.add(post_id)
            added += 1
            if added >= target:
                break

    packets = []
    labels = []
    for idx, (bucket, facts) in enumerate(selected, start=1):
        packet = build_packet(f"R2-{idx:04d}", bucket, facts, result_path)
        packets.append(packet)
        labels.append(review_label(packet, facts))
    selected_counts = Counter(packet["bucket"] for packet in packets)
    target_shortfalls = {
        bucket: max(0, target - selected_counts.get(bucket, 0)) for bucket, target in targets.items()
    }
    coverage_ratios = {
        bucket: round(selected_counts.get(bucket, 0) / max(1, target), 6)
        for bucket, target in targets.items()
    }
    manifest = {
        "run_id": RUN_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "round": ROUND_NAME,
        "sample_seed": SEED,
        "source_result_path": result_path.as_posix(),
        "source_review_policy": source_review_policy(result_path, source_integrity_summary),
        "dedupe_key": "post_id",
        "excluded_existing_review_post_ids": len(existing_post_ids),
        "total_rows_scanned": total_rows,
        "target_scale": target_scale,
        "bucket_targets": targets,
        "target_total": sum(targets.values()),
        "selected_total": len(packets),
        "target_satisfied": all(value == 0 for value in target_shortfalls.values()),
        "target_shortfalls": target_shortfalls,
        "bucket_coverage_ratios": coverage_ratios,
        "selection_order": selection_order,
        "candidate_counts": {bucket: seen.get(bucket, 0) for bucket in targets},
        "selected_counts": {bucket: selected_counts.get(bucket, 0) for bucket in targets},
        "covered_counts": {
            bucket: sum(1 for packet in packets if bucket in set(packet.get("risk_tags") or []))
            for bucket in targets
        },
        "bucket_conditions": {
            "search_degraded_or_timeout": "reason/search 공개 field에 degraded, timeout, engine warning 또는 no-result 신호가 있다.",
            "weak_evidence_but_strong_resolution": "약한 공식/검색 근거인데 resolved/high-confidence relevant 판정을 받은 row다.",
            "generic_parenthetical_bridge": "resolved title 또는 괄호 bridge가 일반어/범주/year/common surface를 가리킨다.",
            "unresolved_to_resolved": "checkpoint lineage가 없어 proxy bucket으로 둔다. resolved row가 약한 근거 또는 llm-only 근거에 의존한다.",
            "multi_work_or_adjacent_risk": "multi-work, adjacent-domain, comparison, recommendation 또는 secondary-reference 단서가 있다.",
            "trope_or_author_talk_risk": "trope, genre, setting, author, publication 또는 meta-talk 단서가 있다.",
            "reason_decision_contradiction": "공개 reason과 final decision/relevance field가 충돌한다.",
            "slang_db_store_block_pending_family_noise": "slang_insight store/scope/reason metadata에 subtype review가 필요하다.",
            "comments_without_author_metadata": "댓글은 있지만 author/IP/comment_id metadata가 없어 대화 관계를 검토할 수 없다.",
            "comment_speaker_context_unavailable": "댓글은 있지만 speaker/context line이 없어 self-comment와 타인 comment를 구분하기 어렵다.",
            "comment_author_ip_mismatch_dialogue": "익명 author가 post author와 같지만 IP가 달라 speaker attribution 검토가 필요하다.",
            "comment_author_match_unverified_dialogue": "익명 author 문자열만 같고 IP 확인이 없어 post_author attribution을 확정할 수 없다.",
            "post_author_comment_not_independent_evidence": "post_author 댓글이 독립 작품 근거가 아니라고 flag된 row다.",
            "comment_answer_side_conversation": "댓글 title 후보가 원글 직접 답변이 아니라 side/reply conversation일 가능성이 있다.",
            "quote_alignment_missing_for_memory_query": "memory-query/대사·장면 회수 글에서 공식 후보 페이지는 있으나 원문 quote/source anchor를 직접 지지하는 snippet/catalog 근거가 없다.",
            "memory_query_resolved": "기억 회수/작품 찾기 문맥인데 final title이 resolved로 고정된 row다.",
            "batch_memory_exact_alias_rescued_no_anchor": "no-anchor/search-only/고유근거 부족 상태에서 batch memory exact alias rescue가 final title을 되살린 row다.",
            "critical_counter_but_resolved": "Verifier critical 또는 검증 반론이 final resolved title과 함께 남아 있는 row다.",
            "notes_demoted_then_resolved": "앞단 unresolved demotion 이후 후단 rescue가 다시 final title을 확정한 row다.",
            "title_surface_primary_candidate_rescued": "title surface primary candidate rescue가 final title 확정에 개입한 row다.",
            "official_url_missing_for_resolved": "final title은 resolved지만 final novel_identity.heretic_url이 비어 있는 row다.",
            "official_url_synopsis_or_branding_mismatch": "공식 URL 대표 제목이 시놉시스/브랜딩/다른 표면으로 잡혔거나 same-URL 검색 근거로 URL이 회복된 row다.",
            "reason_says_no_anchor_but_resolved": "reason은 no-anchor/search-only/고유근거 부족을 말하지만 final title은 resolved인 row다.",
            "search_absent_verified_title_direct_image_title": "검색 부재 검증 반론이 있는 image/OCR-derived title 또는 visual title 후보가 resolved 상태에 남은 row다.",
            "final_semantic_reread_missing_for_semantic_seed": "semantic seed/context-only 위험이 있는데 resolved title에 대한 final semantic reread 기록이 없는 row다.",
            "final_semantic_reread_reviewed": "후단 final candidate가 원문/evidence와 맞는지 final semantic reread를 거친 row다.",
            "VLM_OCR_involved": "image/OCR 공개 context source 또는 reason text가 개입되어 있다.",
            "image_evidence_catalog_missing": "이미지/VLM/OCR 근거가 있어야 하는 row인데 공개 identity.image_evidence_catalog가 없다.",
            "worker_or_shard_degraded_window": "degraded row에 worker id는 있으나 shard/timestamp window 근거가 없다.",
            "round2_false_negative_recall": "작품 단서가 보이지만 resolved title이 없거나 relevance가 과소 해결됐을 가능성이 있다.",
        },
        "limitations": [
            "server-poc 패키지에는 manifest/checkpoint lineage 또는 row별 search evidence URL이 없다.",
            "worker_or_shard_degraded_window는 worker_id만 있어 partial bucket이다.",
            "unresolved_to_resolved는 before/after checkpoint state가 없어 proxy bucket이다.",
            source_review_policy(result_path, source_integrity_summary)["approval_policy"],
        ],
    }
    return packets, labels, manifest


def label_counts(rows: list[dict[str, Any]]) -> Counter:
    return Counter(str(row.get("label")) for row in rows)


def nested_bucket_counts(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    bucket_counts: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        bucket_counts[str(row.get("bucket"))][str(row.get("label"))] += 1
    return {bucket: dict(counts) for bucket, counts in sorted(bucket_counts.items())}


def make_markdown_table(bucket_counts: dict[str, dict[str, int]]) -> str:
    lines = [
        "| 버킷 | ACCEPT | HOLD | REPROCESS | REJECT | INFO_MISSING |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for bucket, counts in sorted(bucket_counts.items()):
        lines.append(
            "| "
            + bucket
            + " | "
            + " | ".join(str(counts.get(label, 0)) for label in LABELS)
            + " |"
        )
    return "\n".join(lines)


def representative_rows(rows: list[dict[str, Any]], labels: Iterable[str], limit: int = 10) -> list[dict[str, Any]]:
    wanted = set(labels)
    return [row for row in rows if row.get("label") in wanted][:limit]


def write_round2_summary(path: Path, labels: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    counts = label_counts(labels)
    bucket_counts = nested_bucket_counts(labels)
    lines = [
        f"# Round 2 자연어 의미 품질 리뷰 - {RUN_ID}",
        "",
        f"생성 시각: {manifest['generated_at']}",
        "",
        "## 범위",
        "",
        "Round 2는 post id 전수가 아니라 실패 유형 기준으로 1차 자연어 리뷰를 확장한다.",
        "이 결과는 자동 run 정합성 감사와 분리된 자연어 의미 품질 표본이다.",
        "",
        "## 라벨 요약",
        "",
    ]
    for label in LABELS:
        lines.append(f"- `{label}`: `{counts.get(label, 0)}`")
    lines.extend(["", "## 버킷 x 라벨", "", make_markdown_table(bucket_counts), "", "## 후보 커버리지", ""])
    for bucket, target in manifest["bucket_targets"].items():
        lines.append(
            f"- `{bucket}`: 후보 `{manifest['candidate_counts'].get(bucket, 0)}`, "
            f"선택 `{manifest['selected_counts'].get(bucket, 0)}`, 목표 `{target}`"
        )
    lines.extend(["", "## 대표 non-ACCEPT row", ""])
    reps = representative_rows(labels, ["REJECT", "REPROCESS", "HOLD"], 18)
    for row in reps:
        lines.append(
            f"- `{row['packet_id']}` / post `{row['post_id']}` / 버킷 `{row['bucket']}` / "
            f"`{row['label']}` -> `{row['action']}`: {row['evidence_alignment']}"
        )
    lines.extend(["", "## 한계", ""])
    for item in manifest["limitations"]:
        lines.append(f"- {item}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_canonical_summaries(review_dir: Path, all_packets: list[dict[str, Any]], all_labels: list[dict[str, Any]], round2_manifest: dict[str, Any]) -> None:
    counts = label_counts(all_labels)
    action_counts = Counter(str(row.get("action")) for row in all_labels)
    bucket_counts = nested_bucket_counts(all_labels)
    round2_labels = [row for row in all_labels if row.get("round") == ROUND_NAME]
    random_labels = [row for row in all_labels if row.get("bucket") == "random_control"]
    source_policy = round2_manifest.get("source_review_policy") or {}

    summary = {
        "run_id": RUN_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "rows": len(all_labels),
        "label_counts": {label: counts.get(label, 0) for label in LABELS if counts.get(label, 0)},
        "action_counts": dict(action_counts),
        "standard_completion": {
            "round1_existing_packet_normalized": True,
            "random_control_100_300": len(random_labels) >= 100,
            "random_control_v3_1000": len(random_labels) >= 1000,
            "round2_failure_pattern_expansion": len(round2_labels) > 0,
            "round2_bucket_targets_satisfied": bool(round2_manifest.get("target_satisfied")),
            "dedicated_vlm_ocr_bucket": any(row.get("bucket") == "VLM_OCR_involved" for row in all_labels),
            "dedicated_worker_or_shard_degraded_window_bucket": any(
                row.get("bucket") == "worker_or_shard_degraded_window" for row in all_labels
            ),
            "slang_db_subtype_split": any(
                row.get("bucket") == "slang_db_store_block_pending_family_noise" for row in all_labels
            ),
        },
        "standard_completion_notes": {
            "worker_or_shard_degraded_window": "partial: worker_id는 있으나 shard/timestamp window source file은 없다.",
            "unresolved_to_resolved": "partial proxy: checkpoint before/after lineage가 없다.",
            "generic_parenthetical_bridge": "전용 bucket은 생성됐으나 정확한 bridge provenance는 공개 reason/title field로 제한된다.",
        },
        "bucket_label_counts": bucket_counts,
        "round2": {
            "sample_seed": SEED,
            "rows": len(round2_labels),
            "label_counts": dict(label_counts(round2_labels)),
            "selected_counts": round2_manifest.get("selected_counts"),
            "target_total": round2_manifest.get("target_total"),
            "selected_total": round2_manifest.get("selected_total"),
            "target_satisfied": round2_manifest.get("target_satisfied"),
            "target_shortfalls": round2_manifest.get("target_shortfalls"),
            "source_review_policy": round2_manifest.get("source_review_policy"),
            "manifest_path": str((review_dir / "round2_manifest.json").as_posix()),
            "packet_path": str((review_dir / "round2_packets.jsonl").as_posix()),
            "label_path": str((review_dir / "round2_labels.jsonl").as_posix()),
        },
        "gate": {
            "run_integrity": "REVIEW",
            "semantic_decision_quality": "NO-GO",
            "overall": "NO-GO",
        },
        "output_dir": review_dir.as_posix(),
    }
    (review_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sample_manifest = {
        "run_id": RUN_ID,
        "generated_at": summary["generated_at"],
        "review_standard": "docs/devs/QUALITATIVE_SEMANTIC_REVIEW_LOOP.md",
        "status": "round1_random_control_plus_round2_failure_pattern_expansion",
        "source_files": {
            "result_json": round2_manifest.get("source_result_path"),
            "source_integrity_summary": (round2_manifest.get("source_review_policy") or {}).get("summary_path"),
            "result_scan_json": None,
            "run_review_audit_json": None,
            "round2_manifest": str((review_dir / "round2_manifest.json").as_posix()),
        },
        "source_review_policy": round2_manifest.get("source_review_policy"),
        "sampling_method": {
            "dedupe_key": "post_id",
            "random_control_seed": f"{RUN_ID}:random_control:v2_unbiased",
            "round2_seed": SEED,
            "random_control_requirement": "satisfied_first_pass_100",
            "round2_requirement": "satisfied_failure_pattern_expansion",
            "high_risk_oversampling": "satisfied_with_dedicated_round2_buckets",
        },
        "sample_counts": {
            "total_rows": len(all_labels),
            "random_control_rows": len(random_labels),
            "round2_rows": len(round2_labels),
            "random_control_v3_1000_satisfied": len(random_labels) >= 1000,
            "round2_bucket_targets_satisfied": bool(round2_manifest.get("target_satisfied")),
            "round2_target_shortfalls": round2_manifest.get("target_shortfalls"),
            "bucket_counts": dict(Counter(str(row.get("bucket")) for row in all_labels)),
            "label_counts": {label: counts.get(label, 0) for label in LABELS if counts.get(label, 0)},
            "bucket_label_counts": bucket_counts,
        },
        "round2": round2_manifest,
        "limitations": [
            "자동 run audit는 자연어 의미 품질 리뷰와 분리된다.",
            "server-poc 패키지에는 원본 manifest/checkpoint/comparison evidence가 없다.",
            "targeted remediation/rerun으로 P0/P1 pattern 수정이 증명되기 전까지 GO는 차단된다.",
        ],
    }
    (review_dir / "sample_manifest.json").write_text(
        json.dumps(sample_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    pattern_lines = [
        f"# 패턴 요약 - {RUN_ID}",
        "",
        f"생성 시각: {summary['generated_at']}",
        "",
        "## 범위",
        "",
        "이 문서는 Round 2 실패 유형 확장 이후의 자연어 의미 품질 리뷰를 요약한다.",
        "자동 run 정합성과 자연어 판정 품질은 서로 다른 gate로 분리한다.",
        "",
        "## 라벨 요약",
        "",
    ]
    for label in LABELS:
        pattern_lines.append(f"- `{label}`: `{counts.get(label, 0)}`")
    pattern_lines.extend(["", "## 버킷 x 라벨", "", make_markdown_table(bucket_counts), ""])
    pattern_lines.extend(
        [
            "## Round 2 커버리지",
            "",
            f"- Seed: `{SEED}`",
            f"- Round 2 row 수: `{len(round2_labels)}`",
            f"- 목표 row 수: `{round2_manifest.get('target_total')}`",
            f"- 실제 선택 row 수: `{round2_manifest.get('selected_total')}`",
            f"- 목표 충족: `{round2_manifest.get('target_satisfied')}`",
            f"- 스캔한 후보 row 수: `{round2_manifest.get('total_rows_scanned')}`",
        ]
    )
    for bucket, selected in sorted((round2_manifest.get("selected_counts") or {}).items()):
        shortfall = (round2_manifest.get("target_shortfalls") or {}).get(bucket, 0)
        target = (round2_manifest.get("bucket_targets") or {}).get(bucket)
        pattern_lines.append(f"- `{bucket}`: 목표 `{target}`, 선택 `{selected}`, 부족 `{shortfall}`")
    pattern_lines.extend(["", "## 실패 패턴", ""])
    failure_patterns = [
        ("P1 systemic", "일반어/common surface 승격", ["generic_parenthetical_bridge", "generic_title_surface"]),
        (
            "P1 systemic",
            "약한 근거 또는 검색 의존 high-confidence resolution",
            ["weak_evidence_but_strong_resolution", "weak_evidence_resolved", "low_anchor_resolved"],
        ),
        ("P1 systemic", "검색 degraded 상태의 승인 위험", ["search_degraded_or_timeout", "degraded_majority_resolved"]),
        ("P1 systemic", "alias recall 손실 / false negative", ["round2_false_negative_recall", "relevant_without_title"]),
        ("P1 review", "slang_db alias subtype 위험", ["slang_db_store_block_pending_family_noise", "slang_noise_candidate"]),
        ("P1 review", "VLM/OCR 근거 공백", ["VLM_OCR_involved"]),
        (
            "P1 review",
            "댓글 author/IP dialogue attribution 위험",
            [
                "comment_author_ip_mismatch_dialogue",
                "comment_author_match_unverified_dialogue",
                "post_author_comment_not_independent_evidence",
                "comment_answer_side_conversation",
                "comments_without_author_metadata",
                "comment_speaker_context_unavailable",
            ],
        ),
        ("P1 review", "경계 drift: multi-work/adjacent/trope/author", ["multi_work_or_adjacent_risk", "trope_or_author_talk_risk"]),
        ("P2 run lineage", "worker/shard degraded window 근거 공백", ["worker_or_shard_degraded_window"]),
    ]
    labels_by_bucket = defaultdict(list)
    for row in all_labels:
        labels_by_bucket[str(row.get("bucket"))].append(row)
    for severity, title, buckets in failure_patterns:
        rows = [row for bucket in buckets for row in labels_by_bucket.get(bucket, []) if row.get("label") != "ACCEPT"]
        pattern_lines.extend([f"### {title}", "", f"- 상태: `{severity}`", f"- non-ACCEPT 수: `{len(rows)}`"])
        for row in rows[:8]:
            pattern_lines.append(
                f"- `{row['packet_id']}` / post `{row['post_id']}` / `{row['label']}` / "
                f"`{row['action']}`: {row['evidence_alignment']}"
            )
        if len(rows) > 8:
            pattern_lines.append(f"- ... 추가 `{len(rows) - 8}`건은 `review_labels.jsonl`에 있다.")
        pattern_lines.append("")
    pattern_lines.extend(
        [
            "## 포화 상태",
            "",
            "- 실패 패턴 포화: `not_reached`.",
            "- 이유: Round 2에서 전용 실패 유형 bucket을 추가했지만 P1 bucket 전반에서 non-ACCEPT row가 계속 발견됐다.",
            "- 다음 단계: gate를 바꾸기 전에 targeted remediation과 Round 3 P0/P1 검증을 수행한다.",
        ]
    )
    (review_dir / "pattern_summary.md").write_text("\n".join(pattern_lines) + "\n", encoding="utf-8")

    gate_evidence_lines = [
        f"- `Strong`: source dataset policy가 `{source_policy.get('source_dataset_kind')}`와 "
        f"`large_run_complete={source_policy.get('large_run_complete')}`를 manifest에 기록한다.",
        "- `Medium`: high-risk bucket에서 약한 근거, alias, generic-surface pattern이 반복 노출된다.",
        "- `Weak`: worker/shard degraded-window 리뷰에는 row별 shard/timestamp lineage가 부족하다.",
    ]
    if random_labels:
        if len(random_labels) >= 1000:
            gate_evidence_lines.append(f"- `Strong`: random control `{len(random_labels)}`건이 1,000건 baseline 기준을 충족한다.")
        elif len(random_labels) >= 100:
            gate_evidence_lines.append(
                f"- `Medium`: random control `{len(random_labels)}`건이 존재하지만 1,000건 baseline 기준에는 부족하다."
            )
        else:
            gate_evidence_lines.append(
                f"- `Weak`: random control `{len(random_labels)}`건만 존재한다. 전체 품질 기준선으로 사용하기에는 부족하다."
            )
    else:
        gate_evidence_lines.append("- `Missing`: random control baseline이 없으므로 전체 품질 기준선으로 사용할 수 없다.")
    if round2_manifest.get("target_satisfied") is True:
        gate_evidence_lines.append(
            f"- `Medium`: Round 2 high-risk target `{round2_manifest.get('selected_total')}/{round2_manifest.get('target_total')}`을 충족했다."
        )
    else:
        gate_evidence_lines.append(
            f"- `Missing`: Round 2 high-risk target이 미달이다. "
            f"selected `{round2_manifest.get('selected_total')}` / target `{round2_manifest.get('target_total')}`."
        )
    if "server-poc" in str(round2_manifest.get("source_result_path") or ""):
        gate_evidence_lines.append("- `Missing`: server-poc에는 원본 manifest/checkpoint/comparison evidence와 row별 search URL이 없다.")
    elif source_policy.get("source_dataset_kind") == "checkpoint_recovered_completed_subset":
        gate_evidence_lines.append(
            "- `Strong`: recovered subset은 checkpoint completed row 복구본이며 원본 large run approval 근거가 아님을 명시했다."
        )

    gate_lines = [
        f"# Gate 판정 - {RUN_ID}",
        "",
        f"생성 시각: {summary['generated_at']}",
        "",
        "## 판정",
        "",
        "- run 정합성: `REVIEW`",
        "- 자연어 판정 품질: `NO-GO`",
        "- 종합: `NO-GO`",
        "",
        "자동 감사는 run이 result row를 만들었다는 것만 증명한다. 자연어 판정 품질 승인을 의미하지 않는다.",
        "",
        "## 근거",
        "",
        f"- 정성 리뷰 row 수: `{len(all_labels)}`",
        f"- random control row 수: `{len(random_labels)}`",
        f"- Round 2 실패 유형 row 수: `{len(round2_labels)}`",
        f"- Round 2 target 충족: `{round2_manifest.get('target_satisfied')}`",
        f"- Round 2 target: `{round2_manifest.get('selected_total')}` / `{round2_manifest.get('target_total')}`",
        f"- 라벨 분포: "
        + ", ".join(f"`{label}={counts.get(label, 0)}`" for label in LABELS if counts.get(label, 0)),
        f"- non-ACCEPT row 수: `{len([row for row in all_labels if row.get('label') != 'ACCEPT'])}`",
        "",
        "## Source Policy",
        "",
        f"- source dataset kind: `{source_policy.get('source_dataset_kind')}`",
        f"- integrity classification: `{source_policy.get('source_integrity_classification')}`",
        f"- recovered subset safe: `{source_policy.get('recovery_safe_to_use_as_completed_subset')}`",
        f"- large run complete: `{source_policy.get('large_run_complete')}`",
        f"- policy: {source_policy.get('approval_policy')}",
        "",
        "## Gate 근거",
        "",
        *gate_evidence_lines,
        "",
        "## GO 전 필수 조건",
        "",
        "- P1 generic/common-surface promotion을 수정하거나 격리한다.",
        "- weak-evidence/high-confidence 및 degraded-search bucket을 재실행 또는 재검색한다.",
        "- alias를 신뢰 recall 근거로 저장하기 전에 slang_db subtype row를 리뷰한다.",
        "- P0/P1 후보에 Round 3를 수행하고 새로운 systemic failure pattern이 없음을 보인다.",
    ]
    (review_dir / "gate_decision.md").write_text("\n".join(gate_lines) + "\n", encoding="utf-8")

    queue_rows = [row for row in all_labels if row.get("label") != "ACCEPT"]
    queue_json = []
    for row in queue_rows:
        priority = "P1"
        if row.get("label") == "REJECT":
            priority = "P0/P1"
        elif row.get("label") == "HOLD":
            priority = "P2" if row.get("action") == "human_review" else "P1"
        queue_json.append(
            {
                "priority": priority,
                "packet_id": row.get("packet_id"),
                "post_id": row.get("post_id"),
                "bucket": row.get("bucket"),
                "label": row.get("label"),
                "action": row.get("action"),
                "evidence_grade": row.get("evidence_grade"),
                "rationale": row.get("evidence_alignment"),
            }
        )
    (review_dir / "action_queue.json").write_text(
        json.dumps(queue_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    action_lines = [
        f"# 액션 큐 - {RUN_ID}",
        "",
        f"생성 시각: {summary['generated_at']}",
        "",
        "## 요약",
        "",
    ]
    for action, count in sorted(action_counts.items()):
        action_lines.append(f"- `{action}`: `{count}`")
    action_lines.extend(["", "## non-ACCEPT 큐", ""])
    for item in queue_json[:80]:
        action_lines.append(
            f"- `{item['priority']}` `{item['packet_id']}` post `{item['post_id']}` "
            f"`{item['label']}` -> `{item['action']}` / `{item['bucket']}`: {item['rationale']}"
        )
    if len(queue_json) > 80:
        action_lines.append(f"- ... 추가 `{len(queue_json) - 80}`건은 `action_queue.json`에 있다.")
    (review_dir / "action_queue.md").write_text("\n".join(action_lines) + "\n", encoding="utf-8")


def main() -> int:
    global RUN_ID, SEED
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", default="server-poc/expert_result_20260505_214349_324347.json")
    parser.add_argument("--review-dir", default=None)
    parser.add_argument("--target-scale", type=float, default=1.0)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--source-integrity-summary", default=None)
    parser.add_argument("--preflight", default=None, help="Preflight JSON that must match --result for approval-oriented runs.")
    parser.add_argument(
        "--fail-on-locked-source",
        action="store_true",
        help="Exit with code 2 before writing outputs when --preflight is missing, mismatched, or REVIEW-LOCKED.",
    )
    args = parser.parse_args()

    root = repo_root()
    result_path = (root / args.result).resolve()
    summary_path = (root / args.source_integrity_summary).resolve() if args.source_integrity_summary else None
    source_integrity_summary = load_source_integrity_summary(summary_path)
    preflight_path = (root / args.preflight).resolve() if args.preflight else None
    preflight = load_preflight_summary(preflight_path)
    preflight_gate = preflight_source_gate_status(
        preflight,
        result_path=result_path,
        fail_on_locked_source=args.fail_on_locked_source,
    )
    if preflight_gate.get("blocked"):
        print(
            json.dumps(
                {
                    "blocked": True,
                    "tool": "build_qualitative_round2_review",
                    "preflight_path": preflight_path.as_posix() if preflight_path else None,
                    **preflight_gate,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return int(preflight_gate["exit_code"])

    RUN_ID = args.run_id or infer_run_id(result_path)
    SEED = f"{RUN_ID}:round2_failure_pattern_expansion:v1"
    review_dir = (root / (args.review_dir or f"qualitative_review/{RUN_ID}")).resolve()
    review_dir.mkdir(parents=True, exist_ok=True)

    packets, labels, manifest = select_round2(
        result_path,
        review_dir,
        args.target_scale,
        source_integrity_summary,
    )

    round2_manifest_path = review_dir / "round2_manifest.json"
    round2_packets_path = review_dir / "round2_packets.jsonl"
    round2_labels_path = review_dir / "round2_labels.jsonl"
    round2_summary_path = review_dir / "round2_summary.md"

    round2_manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_jsonl(round2_packets_path, packets)
    write_jsonl(round2_labels_path, labels)
    write_round2_summary(round2_summary_path, labels, manifest)

    existing_packets = [
        row for row in load_jsonl(review_dir / "review_packets.jsonl") if row.get("round") != ROUND_NAME
    ]
    existing_labels = [
        row for row in load_jsonl(review_dir / "review_labels.jsonl") if row.get("round") != ROUND_NAME
    ]
    all_packets = existing_packets + packets
    all_labels = existing_labels + labels
    write_jsonl(review_dir / "review_packets.jsonl", all_packets)
    write_jsonl(review_dir / "review_labels.jsonl", all_labels)
    write_canonical_summaries(review_dir, all_packets, all_labels, manifest)

    print(
        json.dumps(
            {
                "round2_packets": len(packets),
                "round2_label_counts": dict(label_counts(labels)),
                "round2_selected_counts": manifest.get("selected_counts"),
                "canonical_rows": len(all_labels),
                "output_dir": str(review_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
