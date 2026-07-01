"""Compare completed779 P0 seed baseline rows with a targeted canary result."""

from __future__ import annotations

import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_json_or_jsonl(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        rows = []
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows
    payload = load_json(path)
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "results", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    raise ValueError(f"unsupported row payload: {path}")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def row_by_post_id(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {int(row["post_id"]): row for row in rows if row.get("post_id") is not None}


def unwrap_result_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    """Accept both plain expert_main rows and completed wrapper rows."""

    if not isinstance(row, dict):
        return row
    nested = row.get("result")
    if isinstance(nested, dict):
        return nested
    return row


def normalize_seed_row(seed: dict[str, Any]) -> dict[str, Any]:
    """Accept both native-web seed rows and Loop 2 reimprovement queue rows."""

    if isinstance(seed.get("_judge_seed"), dict):
        normalized = dict(seed["_judge_seed"])
        if normalized.get("post_id") is None and seed.get("post_id") is not None:
            normalized["post_id"] = seed.get("post_id")
    else:
        normalized = dict(seed)
    if "independent_official_title" not in normalized and "expected_title" in normalized:
        normalized["independent_official_title"] = normalized.get("expected_title")
    if "independent_url" not in normalized and "expected_url" in normalized:
        normalized["independent_url"] = normalized.get("expected_url")
    if "pipeline_official_title" not in normalized and "before_title" in normalized:
        normalized["pipeline_official_title"] = normalized.get("before_title")
    if "pipeline_url" not in normalized and "before_url" in normalized:
        normalized["pipeline_url"] = normalized.get("before_url")
    if "source_identity" not in normalized:
        normalized["source_identity"] = {
            "official_title": normalized.get("pipeline_official_title"),
            "heretic_url": normalized.get("pipeline_url"),
            "candidate_count": 0,
        }
    if normalized.get("movement_status") is not None:
        normalized["source_queue_movement_status"] = normalized.get("movement_status")
    if normalized.get("observed_problem") is not None:
        normalized["source_queue_observed_problem"] = normalized.get("observed_problem")
    if normalized.get("seed_reason") is None and normalized.get("source_queue_movement_status"):
        normalized["seed_reason"] = "reimprovement_queue:" + str(normalized["source_queue_movement_status"])
    return normalized


def analysis_identity(row: dict[str, Any] | None) -> dict[str, Any]:
    row = unwrap_result_row(row)
    if not row:
        return {
            "official_title": None,
            "heretic_url": None,
            "is_novel_related": None,
            "is_resolved_work_discussion": None,
            "title_resolution_state": None,
            "title_resolution_allowed": None,
            "candidate_count": 0,
            "candidate_ledger_status": None,
            "lint_flags": [],
        }
    result = row.get("analysis_result") or {}
    identity = result.get("identity") or {}
    novel_identity = identity.get("novel_identity") or {}
    official_title = (
        novel_identity.get("official_title")
        or identity.get("official_title")
        or identity.get("official_novel_title")
    )
    heretic_url = novel_identity.get("heretic_url") or identity.get("heretic_url")
    lint_flags = []
    for key in (
        "official_title_lint",
        "identity_consistency_lint",
        "output_consistency_lint",
        "candidate_audit_lint",
    ):
        value = identity.get(key) or result.get(key)
        if value:
            lint_flags.append({key: value})
    candidate_titles: list[str] = []
    candidate_urls: list[str] = []
    candidate_url_evidence: list[dict[str, Any]] = []
    primary_work_title = None
    primary_work_url = None

    def add_candidate(value: Any) -> None:
        if not isinstance(value, dict):
            return
        title = value.get("official_title") or value.get("title") or value.get("work_title")
        url = value.get("heretic_url") or value.get("url")
        if isinstance(title, str) and title and title not in candidate_titles:
            candidate_titles.append(title)
        if isinstance(url, str) and url and url not in candidate_urls:
            candidate_urls.append(url)
        if isinstance(url, str) and url:
            candidate_url_evidence.append(
                {
                    "url": url,
                    "title": title,
                    "source_tier": value.get("source_tier"),
                    "page_type": value.get("page_type"),
                    "content_status": value.get("content_status"),
                    "negative_evidence": value.get("negative_evidence"),
                    "reference_role": value.get("reference_role"),
                }
            )

    primary_work = identity.get("primary_work")
    if isinstance(primary_work, dict):
        primary_work_title = primary_work.get("official_title") or primary_work.get("title") or primary_work.get("work_title")
        primary_work_url = primary_work.get("heretic_url") or primary_work.get("url")
    add_candidate(primary_work)
    for field in (
        "title_candidates",
        "mentioned_works",
        "recommendation_candidates",
        "secondary_reference_works",
    ):
        value = identity.get(field)
        if isinstance(value, list):
            for item in value:
                add_candidate(item)

    candidate_count = identity.get("candidate_ledger", {}).get("candidate_count")
    if not isinstance(candidate_count, int):
        candidate_count = len(candidate_titles)
    flat_lint_flags: list[str] = []
    for flag in identity.get("consistency_flags") or []:
        if flag:
            flat_lint_flags.append(str(flag))
    for item in lint_flags:
        if not isinstance(item, dict):
            continue
        for value in item.values():
            if isinstance(value, str):
                flat_lint_flags.append(value)
            elif isinstance(value, list):
                flat_lint_flags.extend(str(flag) for flag in value)
            elif isinstance(value, dict):
                flat_lint_flags.extend(str(flag) for flag in value.values())
    return {
        "official_title": official_title,
        "heretic_url": heretic_url,
        "is_novel_related": identity.get("is_novel_related"),
        "is_resolved_work_discussion": identity.get("is_resolved_work_discussion"),
        "title_resolution_state": identity.get("title_resolution_state"),
        "title_resolution_allowed": identity.get("title_resolution_allowed"),
        "candidate_count": candidate_count,
        "candidate_ledger_status": identity.get("candidate_ledger_status"),
        "candidate_titles": candidate_titles,
        "candidate_urls": candidate_urls,
        "candidate_url_evidence": candidate_url_evidence,
        "candidate_pruned_llm_only_surfaces": [
            str(item)
            for item in identity.get("candidate_pruned_llm_only_surfaces") or []
            if item
        ],
        "lint_flags": lint_flags,
        "flat_lint_flags": flat_lint_flags,
        "primary_work_title": primary_work_title,
        "primary_work_url": primary_work_url,
    }


def suspicious_title_shape(title: Any) -> bool:
    if not isinstance(title, str):
        return False
    text = " ".join(title.split())
    if not text:
        return False
    lowered = text.lower()
    if re.search(r"https?://|www\.", lowered):
        return True
    if re.fullmatch(r"[a-z0-9][a-z0-9._-]*\.(?:com|net|org|io|kr|co\.kr)(?:/.*)?", lowered):
        return True
    if len(text) > 80:
        return True
    breadcrumb_markers = ("namu.wiki", "›", ">", " - 나무위키")
    if any(marker in lowered for marker in breadcrumb_markers):
        return True
    snippet_markers = (
        "개요 ",
        "이란 ",
        "말한다.",
        "문피아에서",
        "연재를 시작",
        "대한민국의 웹소설",
        "줄임 말",
        "비하의 의미",
    )
    marker_hits = sum(1 for marker in snippet_markers if marker in text)
    return marker_hits >= 2


def compact_title(title: Any) -> str:
    if not isinstance(title, str):
        return ""
    return re.sub(r"[\s\W_]+", "", title, flags=re.UNICODE).lower()


def titles_match(expected: Any, observed: Any) -> bool:
    """Compare canary titles without turning OCR-close variants into hard fails."""

    expected_key = compact_title(expected)
    observed_key = compact_title(observed)
    if not expected_key or not observed_key:
        return False
    if expected_key == observed_key:
        return True
    shorter, longer = sorted((expected_key, observed_key), key=len)
    if len(shorter) >= 8 and longer.startswith(shorter):
        return True
    if min(len(expected_key), len(observed_key)) >= 10:
        return SequenceMatcher(None, expected_key, observed_key).ratio() >= 0.90
    return False


def url_evidence_strength(entry: dict[str, Any]) -> str:
    url = str(entry.get("url") or "").strip().lower()
    source_tier = str(entry.get("source_tier") or "").strip().lower()
    page_type = str(entry.get("page_type") or "").strip().lower()
    content_status = str(entry.get("content_status") or "").strip().lower()
    raw_negative = entry.get("negative_evidence") or []
    if isinstance(raw_negative, str):
        raw_negative = [raw_negative]
    negative_evidence = {str(item).strip().lower() for item in raw_negative}

    if source_tier == "judge_seed_expected":
        return "judge_seed_expected"
    if "namu.wiki" in url:
        return "wiki"
    if any(domain in url for domain in ("dcinside.com", "arca.live", "blog.naver.com")):
        return "community"

    official_detail = bool(
        re.search(r"novelpia\.com/novel/\d+", url)
        or re.search(r"novel\.munpia\.com/\d+", url)
        or "series.naver.com/novel/detail.series" in url
        or "page.kakao.com/content/" in url
    )
    if not official_detail:
        return "missing" if not url else "non_detail_or_unknown"

    if (
        content_status in {"unavailable", "deleted", "blocked"}
        or "url_deleted_or_unavailable" in negative_evidence
    ):
        return "unavailable_official_detail"
    if source_tier == "official_detail" or page_type == "novel_page":
        return "active_official_detail"
    if source_tier == "mixed":
        return "official_detail_mixed"
    return "official_detail_candidate"


def strongest_url_evidence_strength(entries: list[dict[str, Any]], expected_url: Any) -> str:
    expected = str(expected_url or "").strip()
    if not expected:
        return "missing"
    ranks = {
        "active_official_detail": 7,
        "official_detail_mixed": 6,
        "unavailable_official_detail": 5,
        "official_detail_candidate": 4,
        "judge_seed_expected": 3,
        "wiki": 2,
        "community": 1,
        "non_detail_or_unknown": 1,
        "missing": 0,
    }
    strengths = [
        url_evidence_strength(entry)
        for entry in entries
        if str(entry.get("url") or "").strip() == expected
    ]
    if not strengths:
        return "missing"
    return max(strengths, key=lambda item: ranks.get(item, 0))


def pruned_surface_matches_expected(expected: Any, pruned_surface: Any) -> bool:
    expected_key = compact_title(expected)
    pruned_key = compact_title(pruned_surface)
    if not expected_key or not pruned_key:
        return False
    if titles_match(expected, pruned_surface):
        return True
    if len(pruned_key) >= 4 and pruned_key in expected_key:
        return True
    if len(expected_key) >= 4 and expected_key in pruned_key:
        return True
    if min(len(expected_key), len(pruned_key)) >= 6:
        return SequenceMatcher(None, expected_key, pruned_key).ratio() >= 0.65
    return False


def benign_expected_candidate_prune(seed: dict[str, Any], after_identity: dict[str, Any]) -> bool:
    expected = seed.get("independent_official_title")
    expected_url = seed.get("independent_url")
    candidate_titles = after_identity.get("candidate_titles") or []
    candidate_urls = after_identity.get("candidate_urls") or []
    expected_in_candidates = bool(expected and any(titles_match(expected, title) for title in candidate_titles))
    expected_url_preserved = bool(
        not expected_url
        or after_identity.get("heretic_url") == expected_url
        or expected_url in candidate_urls
    )
    pruned_surfaces = after_identity.get("candidate_pruned_llm_only_surfaces") or []
    if not expected_in_candidates or not expected_url_preserved or not pruned_surfaces:
        return False
    return not any(
        pruned_surface_matches_expected(expected, surface)
        and not benign_pruned_expected_context_surface(expected, surface)
        for surface in pruned_surfaces
    )


def benign_pruned_expected_context_surface(expected: Any, surface: Any) -> bool:
    expected_text = str(expected or "").strip()
    surface_text = str(surface or "").strip()
    if not expected_text or not surface_text:
        return False
    expected_key = compact_title(expected_text)
    surface_key = compact_title(surface_text)
    if not expected_key or expected_key == surface_key or expected_key not in surface_key:
        return False
    context_markers = (
        "작가",
        "씨발",
        "ㅅㅂ",
        "돌아오",
        "연중",
        "유료화",
        "재밌",
        "재미",
        "보라고",
        "보셈",
        "봐라",
        "추천",
    )
    if any(marker in surface_text for marker in context_markers):
        return True
    return len(surface_key) >= len(expected_key) + 8 and bool(re.search(r"[가-힣](?:라|라고|네|냐|다|음|임)\b", surface_text))


def movement_status(seed: dict[str, Any], after_identity: dict[str, Any], after_present: bool) -> str:
    if not after_present:
        return "missing_after"
    bucket = seed.get("seed_bucket")
    after_title = after_identity.get("official_title")
    after_url = after_identity.get("heretic_url")
    expected = seed.get("independent_official_title")
    expected_url = seed.get("independent_url")
    bad_pipeline = seed.get("pipeline_official_title")
    state = after_identity.get("title_resolution_state")
    candidate_count = after_identity.get("candidate_count") or 0
    candidate_ledger_status = after_identity.get("candidate_ledger_status")
    lint_flags = after_identity.get("lint_flags") or []
    flat_lint_flags = [str(flag) for flag in after_identity.get("flat_lint_flags") or []]
    candidate_titles = after_identity.get("candidate_titles") or []
    candidate_urls = after_identity.get("candidate_urls") or []
    expected_in_candidates = bool(expected and any(titles_match(expected, title) for title in candidate_titles))
    expected_url_in_candidates = bool(expected_url and expected_url in candidate_urls)
    expected_url_preserved = bool(expected_url and (after_url == expected_url or expected_url_in_candidates))
    candidate_url_evidence = after_identity.get("candidate_url_evidence") or []

    def official_same_title_alt_url_preserved() -> bool:
        if not (after_url and expected):
            return False
        after_url_low = str(after_url).lower()
        official_detail_shape = any(
            marker in after_url_low
            for marker in (
                "novelpia.com/novel/",
                "novel.munpia.com/",
                "m.munpia.com/novel/detail",
                "series.naver.com/novel/detail",
                "page.kakao.com/content/",
                "joara.com/book/",
            )
        )
        if not official_detail_shape:
            return False
        for item in candidate_url_evidence:
            if not isinstance(item, dict):
                continue
            if item.get("url") != after_url:
                continue
            if not titles_match(expected, item.get("title")):
                continue
            tier = str(item.get("source_tier") or "").lower()
            page_type = str(item.get("page_type") or "").lower()
            negatives = {str(value) for value in item.get("negative_evidence") or []}
            if negatives & {"url_title_mismatch", "url_is_community_post", "url_is_listing", "listing_only"}:
                continue
            if tier in {"official_detail", "official_search", "mixed"} and page_type in {"", "novel_page", "official_detail"}:
                return True
        return False

    author_supported_alt_url = bool(
        after_url
        and expected_url
        and after_url != expected_url
        and expected_url_in_candidates
        and (
            "author_context_official_url_preferred" in flat_lint_flags
            or (
                "official_detail_url_repaired_from_search" in flat_lint_flags
                and official_same_title_alt_url_preserved()
            )
        )
    )
    hold_without_candidates = candidate_ledger_status == "hold_without_candidates" and not candidate_count
    prune_fired = "llm_only_sentence_candidate_pruned" in flat_lint_flags
    blocked_primary_work = any("blocked_primary_work" in flag for flag in flat_lint_flags)
    after_title_is_garbage = suspicious_title_shape(after_title)
    boundary_hold = (
        not expected
        and hold_without_candidates
        and not after_title
        and after_identity.get("is_novel_related") is True
        and after_identity.get("is_resolved_work_discussion") is not True
        and after_identity.get("title_resolution_allowed") is False
        and str(state or "") in {"adjacent", "context_only", "author_new_work_context", "hold", "unresolved_matchable"}
        and str(seed.get("disagreement_type") or "") in {
            "wrong_relevance",
            "relevance",
            "trope_or_author_talk_risk",
            "none",
            "uncertain",
        }
    )

    if after_title_is_garbage and (not expected or not titles_match(expected, after_title)):
        return "garbage_title_after"

    if bucket in {"precision_identity_high", "precision_wrong_work_control"}:
        if bad_pipeline and after_title == bad_pipeline and expected and not titles_match(expected, bad_pipeline):
            return "still_bad_pipeline_title"
        if expected and titles_match(expected, after_title):
            if expected_url and after_url != expected_url:
                if author_supported_alt_url:
                    return "resolved_expected_title_author_supported_alt_url"
                return "title_match_url_still_mismatched"
            return "resolved_expected_title"
        if expected_in_candidates:
            if expected_url and not expected_url_preserved:
                return "title_match_url_still_mismatched"
            if blocked_primary_work:
                return "blocked_candidate_needs_review"
            return "blocked_or_candidate_preserved"
        if after_title and bad_pipeline and after_title != bad_pipeline:
            return "moved_off_bad_pipeline_title"
        if expected and (not after_title or state in {"unresolved_matchable", "author_new_work_context", "hold"} or candidate_count):
            return "still_needs_precision_review"
        if not after_title or state in {"unresolved_matchable", "author_new_work_context", "hold"} or (candidate_count and not hold_without_candidates):
            return "blocked_or_candidate_preserved"
        return "still_needs_precision_review"
    if bucket == "source_url_hygiene":
        if expected and titles_match(expected, after_title) and expected_url and after_url == expected_url:
            return "resolved_expected_title_and_url"
        if expected and after_title and not titles_match(expected, after_title):
            return "title_or_url_still_mismatched"
        if expected_in_candidates and state in {"unresolved_matchable", "author_new_work_context", "hold"}:
            return "url_lint_preserved"
        if expected and not after_title and not expected_in_candidates:
            return "title_or_url_still_mismatched"
        if lint_flags or state in {"unresolved_matchable", "author_new_work_context", "hold"}:
            return "url_lint_preserved"
        if expected_url and after_url != expected_url:
            return "title_or_url_still_mismatched"
        if after_url and after_url != seed.get("pipeline_url"):
            return "url_changed_or_upgraded"
        return "source_hygiene_still_open"
    if bucket in {"candidate_comment_multi", "recall_relevance_representative"}:
        if (
            str(seed.get("disagreement_type") or "") == "trope_or_author_talk_risk"
            and expected
            and titles_match(expected, after_title)
        ):
            return "boundary_title_over_promoted"
        if expected and titles_match(expected, after_title):
            if expected_url and after_url != expected_url:
                if author_supported_alt_url:
                    return "resolved_expected_title_author_supported_alt_url"
                return "title_match_url_still_mismatched"
            return "resolved_expected_title"
        if expected and after_title and not titles_match(expected, after_title):
            return "title_or_url_still_mismatched"
        if expected_in_candidates:
            if prune_fired:
                if benign_expected_candidate_prune(seed, after_identity):
                    return "candidate_preserved_with_benign_prune"
                return "candidate_preserved_with_prune_review"
            return "candidate_or_human_review_preserved"
        if boundary_hold:
            return "boundary_hold_preserved"
        if not expected and after_title:
            return "unexpected_resolved_title"
        if candidate_ledger_status == "hold_without_candidates" and not candidate_count:
            return "still_under_resolved_or_noise"
        if expected and state in {"unresolved_matchable", "author_new_work_context", "hold"}:
            return "still_under_resolved_or_noise"
        if state in {"unresolved_matchable", "author_new_work_context", "hold"} and candidate_count:
            return "candidate_or_human_review_preserved"
        if after_title or candidate_count:
            return "candidate_or_human_review_preserved"
        return "still_under_resolved_or_noise"
    return "review"


def evidence_flags(seed: dict[str, Any], after_identity: dict[str, Any]) -> dict[str, Any]:
    expected = seed.get("independent_official_title")
    expected_url = seed.get("independent_url")
    after_title = after_identity.get("official_title")
    after_url = after_identity.get("heretic_url")
    candidate_titles = after_identity.get("candidate_titles") or []
    candidate_urls = after_identity.get("candidate_urls") or []
    flat_lint_flags = [str(flag) for flag in after_identity.get("flat_lint_flags") or []]
    expected_in_candidates = bool(expected and any(titles_match(expected, title) for title in candidate_titles))
    expected_url_in_candidates = bool(expected_url and expected_url in candidate_urls)
    hold_without_candidates = (
        after_identity.get("candidate_ledger_status") == "hold_without_candidates"
        and not (after_identity.get("candidate_count") or 0)
    )
    return {
        "expected_title_resolved": bool(expected and titles_match(expected, after_title)),
        "expected_title_in_candidates": expected_in_candidates,
        "expected_title_preserved": bool(expected and (titles_match(expected, after_title) or expected_in_candidates)),
        "expected_url_resolved": bool(expected_url and after_url == expected_url),
        "expected_url_in_candidates": expected_url_in_candidates,
        "expected_url_preserved": bool(expected_url and (after_url == expected_url or expected_url_in_candidates)),
        "expected_url_evidence_strength": strongest_url_evidence_strength(
            after_identity.get("candidate_url_evidence") or [],
            expected_url,
        ),
        "unexpected_resolved_title": bool(not expected and after_title),
        "hold_without_candidates": hold_without_candidates,
        "prune_fired": "llm_only_sentence_candidate_pruned" in flat_lint_flags,
        "benign_prune": benign_expected_candidate_prune(seed, after_identity),
        "blocked_primary_work": any("blocked_primary_work" in flag for flag in flat_lint_flags),
    }


def compare(
    seed_path: Path,
    after_path: Path,
    *,
    before_path: Path | None = None,
    only_after_posts: bool = False,
) -> dict[str, Any]:
    seed_rows = [normalize_seed_row(row) for row in load_json_or_jsonl(seed_path)]
    after_index = row_by_post_id(load_json_or_jsonl(after_path))
    before_index = row_by_post_id(load_json_or_jsonl(before_path)) if before_path else {}
    if only_after_posts:
        after_ids = set(after_index)
        seed_rows = [row for row in seed_rows if int(row["post_id"]) in after_ids]

    rows = []
    for seed in seed_rows:
        post_id = int(seed["post_id"])
        after_row = after_index.get(post_id)
        before_row = before_index.get(post_id)
        after_identity = analysis_identity(after_row)
        before_identity = analysis_identity(before_row) if before_row else seed.get("source_identity") or {}
        flags = evidence_flags(seed, after_identity)
        rows.append(
            {
                "post_id": post_id,
                "queue_role": seed.get("queue_role"),
                "selection_bucket": seed.get("selection_bucket"),
                "selection_reason": seed.get("selection_reason"),
                "seed_bucket": seed.get("seed_bucket"),
                "disagreement_type": seed.get("disagreement_type"),
                "recommended_action": seed.get("recommended_action"),
                "source_queue_movement_status": seed.get("source_queue_movement_status"),
                "source_queue_observed_problem": seed.get("source_queue_observed_problem"),
                "observed_problem": seed.get("observed_problem"),
                "suspected_code_hook": seed.get("suspected_code_hook"),
                "proposed_next_fix": seed.get("proposed_next_fix"),
                "required_test": seed.get("required_test"),
                "expected_independent_title": seed.get("independent_official_title"),
                "expected_independent_url": seed.get("independent_url"),
                "baseline_pipeline_title": seed.get("pipeline_official_title"),
                "baseline_pipeline_url": seed.get("pipeline_url"),
                "before_identity": before_identity,
                "after_present": after_row is not None,
                "after_identity": after_identity,
                "evidence_flags": flags,
                "movement_status": movement_status(seed, after_identity, after_row is not None),
            }
        )
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["movement_status"]] = counts.get(row["movement_status"], 0) + 1
    return {
        "seed_path": str(seed_path),
        "before_path": str(before_path) if before_path else None,
        "after_path": str(after_path),
        "total_seed_rows": len(seed_rows),
        "after_rows_matched": sum(1 for row in rows if row["after_present"]),
        "movement_status_counts": dict(sorted(counts.items())),
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "rows": rows,
    }


REIMPROVEMENT_STATUSES = {
    "boundary_title_over_promoted",
    "blocked_candidate_needs_review",
    "candidate_preserved_with_prune_review",
    "garbage_title_after",
    "missing_after",
    "still_bad_pipeline_title",
    "still_needs_precision_review",
    "title_match_url_still_mismatched",
    "title_or_url_still_mismatched",
    "unexpected_resolved_title",
    "source_hygiene_still_open",
    "still_under_resolved_or_noise",
}


def acceptance_status(row: dict[str, Any]) -> str:
    status = row.get("movement_status")
    if status in {
        "resolved_expected_title",
        "resolved_expected_title_and_url",
        "resolved_expected_title_author_supported_alt_url",
    }:
        return "resolved_correct"
    if status in {
        "blocked_or_candidate_preserved",
        "candidate_or_human_review_preserved",
        "candidate_preserved_with_benign_prune",
        "boundary_hold_preserved",
        "url_changed_or_upgraded",
        "url_lint_preserved",
        "moved_off_bad_pipeline_title",
    }:
        return "hold_candidate_conflict"
    if status in {"blocked_candidate_needs_review", "candidate_preserved_with_prune_review"}:
        return "review"
    if status in {
        "boundary_title_over_promoted",
        "garbage_title_after",
        "still_bad_pipeline_title",
        "title_match_url_still_mismatched",
        "title_or_url_still_mismatched",
        "unexpected_resolved_title",
    }:
        return "still_bad"
    if status == "missing_after":
        return "missing_after"
    return "ambiguous"


def build_reimprovement_queue(report: dict[str, Any], *, canary_kind: str) -> dict[str, Any]:
    queue_rows = []
    for row in report.get("rows") or []:
        if row.get("movement_status") not in REIMPROVEMENT_STATUSES:
            continue
        after = row.get("after_identity") or {}
        before = row.get("before_identity") or {}
        queue_rows.append(
            {
                "post_id": row.get("post_id"),
                "queue_role": row.get("queue_role"),
                "selection_bucket": row.get("selection_bucket"),
                "selection_reason": row.get("selection_reason"),
                "seed_bucket": row.get("seed_bucket"),
                "disagreement_type": row.get("disagreement_type"),
                "recommended_action": row.get("recommended_action"),
                "before_title": before.get("official_title") or row.get("baseline_pipeline_title"),
                "before_url": before.get("heretic_url") or row.get("baseline_pipeline_url"),
                "after_title": after.get("official_title"),
                "after_url": after.get("heretic_url"),
                "expected_title": row.get("expected_independent_title"),
                "expected_url": row.get("expected_independent_url"),
                "movement_status": row.get("movement_status"),
                "acceptance_status": acceptance_status(row),
                "observed_problem": (
                    row.get("observed_problem")
                    or row.get("source_queue_observed_problem")
                    or "compare_status:" + str(row.get("movement_status") or "")
                ),
                "source_queue_movement_status": row.get("source_queue_movement_status"),
                "source_queue_observed_problem": row.get("source_queue_observed_problem") or row.get("observed_problem"),
                "suspected_code_hook": row.get("suspected_code_hook") or "",
                "proposed_next_fix": row.get("proposed_next_fix") or "",
                "required_test": row.get("required_test") or "",
            }
        )
    return {
        "schema_version": 1,
        "canary_kind": canary_kind,
        "semantic_quality": report.get("semantic_quality"),
        "full_scan_approval": report.get("full_scan_approval"),
        "source": {
            "seed_path": report.get("seed_path"),
            "before_path": report.get("before_path"),
            "after_path": report.get("after_path"),
        },
        "rows": queue_rows,
    }


def _md_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.split())
    return text.replace("|", "\\|")


def display_identity_title(identity: dict[str, Any]) -> str:
    title = identity.get("official_title")
    if title:
        return str(title)
    candidates = [str(item) for item in identity.get("candidate_titles") or [] if item]
    if not candidates:
        return ""
    return "candidate: " + " / ".join(candidates[:2])


def display_identity_url(identity: dict[str, Any]) -> str:
    url = identity.get("heretic_url")
    if url:
        return str(url)
    candidates = [str(item) for item in identity.get("candidate_urls") or [] if item]
    if not candidates:
        return ""
    return "candidate: " + " / ".join(candidates[:2])


def write_queue_markdown(path: Path, queue: dict[str, Any], *, title: str | None = None) -> None:
    rows = queue.get("rows") or []
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("movement_status") or "")
        counts[status] = counts.get(status, 0) + 1

    lines = [
        f"# {title or 'completed779 Reimprovement Loop 2 Remaining Queue'}",
        "",
        f"- canary kind: `{queue.get('canary_kind') or ''}`",
        f"- remaining rows: `{len(rows)}`",
        "- semantic quality: `REVIEW-LOCKED`",
        "- full scan approval: `false`",
        "",
        "## Movement Status",
        "",
    ]
    if counts:
        for key, value in sorted(counts.items()):
            lines.append(f"- `{key}`: `{value}`")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| post_id | role | selection | bucket | issue | before | after | expected | status | next evidence/fix |",
            "|---:|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in rows:
        before = " / ".join(
            item for item in [str(row.get("before_title") or ""), str(row.get("before_url") or "")] if item
        )
        after = " / ".join(
            item for item in [str(row.get("after_title") or ""), str(row.get("after_url") or "")] if item
        )
        expected = " / ".join(
            item for item in [str(row.get("expected_title") or ""), str(row.get("expected_url") or "")] if item
        )
        next_fix = row.get("source_queue_observed_problem") or row.get("observed_problem") or ""
        lines.append(
            "| {post_id} | {role} | {selection} | {bucket} | {issue} | {before} | {after} | {expected} | {status} | {next_fix} |".format(
                post_id=row.get("post_id") or "",
                role=_md_cell(row.get("queue_role")),
                selection=_md_cell(row.get("selection_bucket")),
                bucket=_md_cell(row.get("seed_bucket")),
                issue=_md_cell(row.get("disagreement_type")),
                before=_md_cell(before),
                after=_md_cell(after),
                expected=_md_cell(expected),
                status=_md_cell(row.get("movement_status")),
                next_fix=_md_cell(next_fix),
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# completed779 Improvement Compare",
        "",
        f"- seed rows: `{report['total_seed_rows']}`",
        f"- after rows matched: `{report['after_rows_matched']}`",
        "- semantic quality: `REVIEW-LOCKED`",
        "- full scan approval: `false`",
        "",
        "## Movement Status",
        "",
    ]
    for key, value in report["movement_status_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| post_id | bucket | issue | expected | after_title | after_url | status |",
            "|---:|---|---|---|---|---|---|",
        ]
    )
    for row in report["rows"]:
        after = row["after_identity"]
        lines.append(
            "| {post_id} | {bucket} | {issue} | {expected} | {after_title} | {after_url} | {status} |".format(
                post_id=row["post_id"],
                bucket=row.get("seed_bucket") or "",
                issue=row.get("disagreement_type") or "",
                expected=row.get("expected_independent_title") or "",
                after_title=_md_cell(display_identity_title(after)),
                after_url=_md_cell(display_identity_url(after)),
                status=row.get("movement_status") or "",
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--before", type=Path)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path, required=True)
    parser.add_argument("--out-queue", type=Path)
    parser.add_argument("--out-queue-md", type=Path)
    parser.add_argument("--canary-kind", default="targeted")
    parser.add_argument("--queue-title")
    parser.add_argument("--only-after-posts", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = compare(args.seed, args.after, before_path=args.before, only_after_posts=args.only_after_posts)
    write_json(args.out_json, report)
    write_markdown(args.out_md, report)
    if args.out_queue:
        queue = build_reimprovement_queue(report, canary_kind=args.canary_kind)
        write_json(args.out_queue, queue)
        if args.out_queue_md:
            write_queue_markdown(
                args.out_queue_md,
                queue,
                title=args.queue_title or f"completed779 {args.canary_kind} Remaining Queue",
            )
    print(
        json.dumps(
            {
                "total_seed_rows": report["total_seed_rows"],
                "after_rows_matched": report["after_rows_matched"],
                "movement_status_counts": report["movement_status_counts"],
                "out_json": str(args.out_json),
                "out_md": str(args.out_md),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
