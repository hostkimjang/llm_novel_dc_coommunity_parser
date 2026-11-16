"""Slang DB 화면(``/api/slang-db``)용 표현 변환.

``slang_db.json``에서 읽은 payload를 제목별 화면 행과 전체 요약으로 바꾸는 순수 함수만 둔다.
파일 읽기, 경로, route는 ``monitor.server``에 남는다. 이 변환은 읽기 전용 표시이며 중앙
Slang DB 쓰기나 공개 판정 권한과 연결되지 않는다.
"""
from __future__ import annotations

from typing import Any, Dict, List


def _extract_term_list(bucket: Any, key: str) -> List[str]:
    if not isinstance(bucket, dict):
        return []

    terms: List[str] = []
    seen: set[str] = set()
    for entry in bucket.get(key) or []:
        raw_term = entry.get("term") if isinstance(entry, dict) else entry
        term = str(raw_term or "").strip()
        if not term or term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms


def _extract_slang_terms(bucket: Any) -> List[str]:
    return _extract_term_list(bucket, "slang")


def _extract_pending_terms(bucket: Any) -> List[str]:
    return _extract_term_list(bucket, "pending")


def _extract_conflict_terms(bucket: Any) -> List[str]:
    return _extract_term_list(bucket, "conflicts")


def _build_pending_kind_counts(bucket: Any) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    if not isinstance(bucket, dict):
        return counts
    for entry in bucket.get("pending") or []:
        if not isinstance(entry, dict):
            continue
        kind = str(entry.get("pending_kind") or "unknown").strip()
        if not kind:
            kind = "unknown"
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def _extract_example_preview(bucket: Any, *, limit: int = 3) -> List[Dict[str, Any]]:
    preview: List[Dict[str, Any]] = []
    if not isinstance(bucket, dict):
        return preview
    for example in (bucket.get("examples") or [])[:limit]:
        if not isinstance(example, dict):
            continue
        preview.append(
            {
                "post_id": example.get("post_id"),
                "alias": example.get("alias"),
                "bucket": example.get("bucket"),
                "source_role": example.get("source_role"),
                "discussion_type": example.get("discussion_type"),
                "work_resolution": example.get("work_resolution"),
                "pending_kind": example.get("pending_kind"),
                "classification_confidence": example.get("classification_confidence"),
                "created_at": example.get("created_at"),
            }
        )
    return preview


def _extract_family_alias_terms(payload: Dict[str, Any], title: str) -> List[str]:
    terms: List[str] = []
    seen: set[str] = set()
    for key, bucket in (payload.get("family_aliases") or {}).items():
        if not isinstance(bucket, dict):
            continue
        titles = [str(x).strip() for x in (bucket.get("titles") or []) if str(x).strip()]
        if str(title or "").strip() not in titles:
            continue
        term = str(bucket.get("term") or key or "").strip()
        if not term or term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms


def build_slang_db_payload(payload: Dict[str, Any], offset: int = 0, limit: int = 100) -> Dict[str, Any]:
    """제목순 화면 행을 만든 뒤 ``offset``/``limit``로 자른다. total과 summary는 전체 기준이다."""
    rows: List[Dict[str, Any]] = []
    summary = {
        "titles_with_slang": 0,
        "titles_with_pending": 0,
        "titles_with_conflicts": 0,
        "titles_with_family_aliases": 0,
    }

    for title, bucket in sorted((payload.get("titles") or {}).items(), key=lambda item: str(item[0])):
        title_text = str(title or "").strip()
        slang_terms = _extract_slang_terms(bucket)
        pending_terms = _extract_pending_terms(bucket)
        conflict_terms = _extract_conflict_terms(bucket)
        family_alias_terms = _extract_family_alias_terms(payload, title_text)
        example_preview = _extract_example_preview(bucket)
        pending_kind_counts = _build_pending_kind_counts(bucket)
        if slang_terms:
            summary["titles_with_slang"] += 1
        if pending_terms:
            summary["titles_with_pending"] += 1
        if conflict_terms:
            summary["titles_with_conflicts"] += 1
        if family_alias_terms:
            summary["titles_with_family_aliases"] += 1
        rows.append({
            "title": title_text,
            "slang_terms": slang_terms,
            "slang_count": len(slang_terms),
            "pending_terms": pending_terms,
            "pending_count": len(pending_terms),
            "pending_kind_counts": pending_kind_counts,
            "conflict_terms": conflict_terms,
            "conflict_count": len(conflict_terms),
            "family_alias_terms": family_alias_terms,
            "family_alias_count": len(family_alias_terms),
            "example_preview": example_preview,
            "example_count": len(bucket.get("examples") or []),
        })

    total = len(rows)
    page = rows[offset:offset + limit]
    return {
        "items": page,
        "total": total,
        "offset": offset,
        "limit": limit,
        "updated_at": payload.get("updated_at"),
        "summary": summary,
    }
