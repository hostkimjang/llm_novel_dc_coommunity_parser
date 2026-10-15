"""이미지 후보와 원문 제목의 명시적 작품 약칭 충돌을 수집한다."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Mapping


def original_title_alias_conflicts(
    post_title: str,
    candidate_title: str,
    aliases: Mapping[str, str],
) -> list[dict[str, str]]:
    """본문·생성 문맥을 보지 않고 원문 제목의 단어 경계만 사용한다."""
    if not isinstance(post_title, str) or not isinstance(candidate_title, str):
        return []
    normalize = lambda text: re.sub(r'[^0-9a-z가-힣]', '', text.lower())
    candidate_key = normalize(candidate_title)
    if not candidate_key or not post_title.strip():
        return []
    word_chars = r'0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ_'
    particle = r'(?:에서|에게|한테|으로|하고|처럼|까지|부터|은|는|이|가|을|를|의|도|만|에|와|과|랑|로)?'
    conflicts: list[dict[str, str]] = []
    seen: set[str] = set()
    for alias, title in aliases.items():
        if not isinstance(alias, str) or not isinstance(title, str):
            continue
        alias = alias.strip()
        title = title.strip()
        title_key = normalize(title)
        if len(normalize(alias)) < 2 or not title_key or title_key == candidate_key or title_key in seen:
            continue
        literal = r'\s+'.join(re.escape(part) for part in alias.split())
        if not re.search(rf'(?<![{word_chars}]){literal}{particle}(?![{word_chars}])', post_title, re.IGNORECASE):
            continue
        seen.add(title_key)
        conflicts.append({'alias': alias, 'title': title, 'source_title': post_title})
    return conflicts

def image_title_alias_conflict_retry_records(
    normalized: dict,
    post_data: dict,
    aliases: Mapping[str, str],
) -> list[dict[str, str]]:
    """단일 강한 OCR 작품명이 유일한 원문 작품 약칭과 충돌하는지 확인한다."""
    images = normalized.get("images") or []
    if len(images) != 1 or not isinstance(images[0], dict):
        return []
    item = images[0]
    if not (
        item.get("promotion_eligible") is True
        and item.get("title_role") == "work_title"
        and item.get("evidence_type") in {"cover_title", "explicit_text"}
        and item.get("confidence") in {"High", "Max"}
        and str(item.get("source_url") or "").strip()
    ):
        return []
    title = item.get("explicit_work_title")
    post_title = post_data.get("title", "")
    conflicts = original_title_alias_conflicts(post_title, title, aliases)
    if len(conflicts) != 1:
        return []
    # 원문이 OCR 작품과 다른 작품을 함께 언급하는 경우에도 대상을 고르지 않는다.
    if original_title_alias_conflicts(post_title, conflicts[0]["title"], aliases):
        return []
    return [{**conflicts[0], "image_title": title, "source_url": item["source_url"]}]


def _ocr_title_key(value: object) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", value.lower()) if isinstance(value, str) else ""


def _credible_ocr_title_disagreement(first: object, retry: object) -> bool:
    """첫 직접 제목과 같은 이미지의 강한 재전사 불일치를 확인한다.

    재판독의 제목 승격 여부와 모순 증거 여부는 다르다. 역할 미확정 표지는
    명시된 work surface와 전사를 모두 갖출 때만 첫 판독의 확신을 낮춘다.
    이 예외로 재판독 제목 자체를 승인하지 않는다.
    """
    if not isinstance(first, dict) or not isinstance(retry, dict):
        return False
    for index, item in enumerate((first, retry)):
        title = _ocr_title_key(item.get("explicit_work_title"))
        promoted_title = (
            item.get("promotion_eligible") is True
            and item.get("title_role") == "work_title"
        )
        nonpromoting_cover_transcription = (
            index == 1
            and len(title) >= 4
            and item.get("promotion_eligible") is False
            and item.get("title_role") == "unknown"
            and item.get("evidence_type") == "cover_title"
            and item.get("screen_type") == "work_surface"
            and item.get("focus_role") == "work_anchor"
            and item.get("surface_type") in {"quoted_text_screenshot", "novel_cover", "official_detail_page"}
            and not item.get("background_listing_only")
            and type(item.get("game_ui_score")) in (int, float)
            and item["game_ui_score"] == 0
            and type(first.get("block_index")) is int
            and type(item.get("block_index")) is int
            and item["block_index"] >= 0
        )
        if not (
            title and title in _ocr_title_key(item.get("ocr_text"))
            and item.get("confidence") in ("High", "Max")
            and (promoted_title or nonpromoting_cover_transcription)
            and item.get("evidence_type") in ("cover_title", "explicit_text")
            and isinstance(item.get("source_url"), str) and item["source_url"].strip()
        ):
            return False
    return bool(
        first["source_url"] == retry["source_url"]
        and first.get("block_index") == retry.get("block_index")
        and _ocr_title_key(first["explicit_work_title"]) != _ocr_title_key(retry["explicit_work_title"])
    )


def _credible_ocr_title_reconfirmation(first: object, retry: object) -> bool:
    """Two strong reads of one image do not settle a conflicting source alias."""
    if not isinstance(first, dict) or not isinstance(retry, dict):
        return False
    title = _ocr_title_key(first.get("explicit_work_title"))
    return bool(
        title and title == _ocr_title_key(retry.get("explicit_work_title"))
        and first.get("source_url") and first.get("source_url") == retry.get("source_url")
        and type(first.get("block_index")) is int
        and first.get("block_index") == retry.get("block_index")
        and all(
            read.get("promotion_eligible") is True
            and read.get("title_role") == "work_title"
            and read.get("evidence_type") in {"cover_title", "explicit_text"}
            and read.get("confidence") in {"High", "Max"}
            and title in _ocr_title_key(read.get("ocr_text"))
            for read in (first, retry)
        )
    )


def unresolved_ocr_alias_conflict_authority_blocked(item: object) -> bool:
    """Return whether an unresolved alias-conflict reread may keep raw evidence only.

    The predicate is deliberately bound to one exact image and one exact conflict.
    It does not decide which title is correct.  It only distinguishes a preserved
    first read from a reread that independently confirmed decision authority.
    """
    if not isinstance(item, dict):
        return False
    review = item.get("ocr_alias_conflict_review")
    if not isinstance(review, dict) or review.get("status") != "unresolved":
        return False
    conflicts = review.get("source_alias_conflicts")
    if not isinstance(conflicts, list) or len(conflicts) != 1 or not isinstance(conflicts[0], dict):
        return False
    conflict = conflicts[0]
    first, retry = review.get("first_read"), review.get("retry_read")
    if not isinstance(first, dict) or not isinstance(retry, dict):
        return False

    source_url = item.get("source_url")
    block_index = item.get("block_index")
    if not isinstance(source_url, str) or not source_url.strip():
        return False
    if type(block_index) is not int or block_index < 0:
        return False
    if any(read.get("source_url") != source_url for read in (first, retry)):
        return False
    if any(type(read.get("block_index")) is not int or read.get("block_index") != block_index for read in (first, retry)):
        return False
    scalar_read_fields = (
        "explicit_work_title", "ocr_text", "confidence", "evidence_type",
        "title_role", "source_url", "screen_type", "focus_role", "surface_type",
    )
    if any(not isinstance(read.get(key), str) for read in (first, retry) for key in scalar_read_fields):
        return False
    if any(type(read.get("promotion_eligible")) is not bool for read in (first, retry)):
        return False
    if retry.get("background_listing_only") is not None and type(retry.get("background_listing_only")) is not bool:
        return False

    required_conflict_strings = ("alias", "title", "image_title", "source_title", "source_url")
    if any(not isinstance(conflict.get(key), str) or not conflict[key].strip() for key in required_conflict_strings):
        return False
    regenerated_conflicts = original_title_alias_conflicts(
        conflict["source_title"],
        conflict["image_title"],
        {conflict["alias"]: conflict["title"]},
    )
    if len(regenerated_conflicts) != 1:
        return False
    first_title_key = _ocr_title_key(first.get("explicit_work_title"))
    retry_title_key = _ocr_title_key(retry.get("explicit_work_title"))
    item_title_key = _ocr_title_key(item.get("explicit_work_title"))
    if not first_title_key or not retry_title_key:
        return False
    if not (
        conflict["source_url"] == source_url
        and _ocr_title_key(conflict["image_title"]) == first_title_key
        and _ocr_title_key(conflict["title"])
        and _ocr_title_key(conflict["title"]) != first_title_key
        and item_title_key == first_title_key
    ):
        return False

    first_is_promoted_work_title = bool(
        first.get("promotion_eligible") is True
        and first.get("title_role") == "work_title"
        and first.get("evidence_type") in {"cover_title", "explicit_text"}
        and first.get("confidence") in {"High", "Max"}
        and first_title_key in _ocr_title_key(first.get("ocr_text"))
    )
    if not first_is_promoted_work_title:
        return False

    if _credible_ocr_title_disagreement(first, retry):
        return True
    if _credible_ocr_title_reconfirmation(first, retry):
        return True
    if first_title_key != retry_title_key:
        return False

    game_ui_score = retry.get("game_ui_score")
    retry_is_nonpromoting_cover_transcription = bool(
        retry.get("promotion_eligible") is False
        and retry.get("title_role") == "unknown"
        and retry.get("evidence_type") == "cover_title"
        and retry.get("confidence") in {"High", "Max"}
        and retry.get("screen_type") == "work_surface"
        and retry.get("focus_role") == "work_anchor"
        and retry.get("surface_type") in {"quoted_text_screenshot", "novel_cover", "official_detail_page"}
        and retry.get("background_listing_only") is not True
        and type(game_ui_score) in (int, float)
        and game_ui_score == 0
        and retry_title_key in _ocr_title_key(retry.get("ocr_text"))
    )
    return retry_is_nonpromoting_cover_transcription


_UNRESOLVED_OCR_AUTHORITY_RECEIPT_FIELD = "_unresolved_ocr_authority_receipt_sha256"


def _unresolved_ocr_authority_binding(item: object) -> dict | None:
    """Build the exact raw binding that a compact catalog may later re-check."""
    if not unresolved_ocr_alias_conflict_authority_blocked(item) or not isinstance(item, dict):
        return None
    review = item["ocr_alias_conflict_review"]
    first = review["first_read"]
    retry = review["retry_read"]
    conflict = review["source_alias_conflicts"][0]
    read_fields = (
        "block_index", "explicit_work_title", "ocr_text", "confidence",
        "evidence_type", "promotion_eligible", "title_role", "source_url",
        "screen_type", "focus_role", "surface_type", "background_listing_only",
        "game_ui_score",
    )
    conflict_fields = ("alias", "title", "image_title", "source_title", "source_url")
    return {
        "source_url": first["source_url"],
        "block_index": first["block_index"],
        "explicit_work_title": first["explicit_work_title"],
        "status": review["status"],
        "first_read": {key: first.get(key) for key in read_fields},
        "retry_read": {key: retry.get(key) for key in read_fields},
        "source_alias_conflict": {key: conflict.get(key) for key in conflict_fields},
    }


def unresolved_ocr_alias_conflict_authority_receipt(item: object) -> str:
    """Return a deterministic receipt only after validating the full raw record."""
    binding = _unresolved_ocr_authority_binding(item)
    if binding is None:
        return ""
    payload = json.dumps(binding, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _catalog_display_projection(value: object, limit: int) -> str:
    if value is None:
        return ""
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text:
        return ""
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def projected_unresolved_ocr_alias_conflict_authority_blocked(item: object) -> bool:
    """Revalidate a blocked raw item after the public catalog display projection.

    A receipt alone is never authority.  The embedded raw review must still pass
    the full predicate, its receipt must match, and the displayed source/title
    must be exactly the producer's documented 500/220-character projection.
    """
    if unresolved_ocr_alias_conflict_authority_blocked(item):
        return True
    if not isinstance(item, dict):
        return False
    receipt = item.get(_UNRESOLVED_OCR_AUTHORITY_RECEIPT_FIELD)
    if not isinstance(receipt, str) or not re.fullmatch(r"[0-9a-f]{64}", receipt):
        return False
    review = item.get("ocr_alias_conflict_review")
    if not isinstance(review, dict) or not isinstance(review.get("first_read"), dict):
        return False
    first = review["first_read"]
    raw_item = dict(item)
    raw_item.pop(_UNRESOLVED_OCR_AUTHORITY_RECEIPT_FIELD, None)
    raw_item["source_url"] = first.get("source_url")
    raw_item["block_index"] = first.get("block_index")
    raw_item["explicit_work_title"] = first.get("explicit_work_title")
    expected = unresolved_ocr_alias_conflict_authority_receipt(raw_item)
    if not expected or receipt != expected:
        return False
    return bool(
        type(item.get("block_index")) is int
        and item.get("block_index") == first.get("block_index")
        and item.get("source_url") == _catalog_display_projection(first.get("source_url"), 500)
        and item.get("explicit_work_title")
        == _catalog_display_projection(first.get("explicit_work_title"), 220)
    )


def unresolved_ocr_alias_conflict_negative_title_variants(image_catalog: object) -> list[str]:
    """Keep blocked first reads as negative authority without re-promoting them."""
    if not isinstance(image_catalog, list):
        return []
    variants: list[str] = []
    seen: set[str] = set()
    for item in image_catalog:
        if not projected_unresolved_ocr_alias_conflict_authority_blocked(item):
            continue
        review = item.get("ocr_alias_conflict_review")
        first = review.get("first_read") if isinstance(review, dict) else None
        raw_title = first.get("explicit_work_title") if isinstance(first, dict) else None
        for title in (raw_title, item.get("explicit_work_title")):
            key = _ocr_title_key(title)
            if key and key not in seen:
                seen.add(key)
                variants.append(title)
    return variants


def uncertain_ocr_title_variants(image_catalog: object) -> list[str]:
    """검증된 불일치 이력에 속한 두 제목을 공개 보류용으로 보존한다."""
    if not isinstance(image_catalog, list):
        return []
    variants: list[str] = []
    seen: set[str] = set()
    for item in image_catalog:
        if not isinstance(item, dict):
            continue
        review = item.get("ocr_alias_conflict_review")
        if not isinstance(review, dict) or review.get("status") != "unresolved" or review.get("authority") != "uncertain":
            continue
        first, retry = review.get("first_read"), review.get("retry_read")
        if not _credible_ocr_title_disagreement(first, retry):
            continue
        if item.get("source_url") != first["source_url"]:
            continue
        for reading in (first, retry):
            title = reading["explicit_work_title"]
            key = _ocr_title_key(title)
            if key not in seen:
                seen.add(key)
                variants.append(title)
    return variants


def merge_image_title_alias_conflict_retry(
    base: dict,
    incoming: dict,
    conflicts: list[dict[str, str]],
) -> tuple[dict, str]:
    """실제 재판독이 원문과 직접 글자를 함께 확인한 경우만 판독 전체를 교체한다."""
    from copy import deepcopy

    merged = deepcopy(base)
    first = (base.get("images") or [])[0]
    retries = incoming.get("images") or []
    retry = retries[0] if len(retries) == 1 and isinstance(retries[0], dict) else {}
    compact = lambda value: re.sub(r"[^0-9a-z가-힣]", "", str(value or "").lower())
    retry_title = compact(retry.get("explicit_work_title"))
    canonical = compact(conflicts[0]["title"]) if len(conflicts) == 1 else ""
    first_author = compact(first.get("explicit_author_name"))
    corrected = bool(
        canonical and retry_title == canonical
        and retry.get("source_url") == first.get("source_url")
        and retry.get("block_index") == first.get("block_index")
        and retry.get("confidence") in {"High", "Max"}
        and retry.get("promotion_eligible") is True
        and retry.get("title_role") == "work_title"
        and retry.get("evidence_type") in {"cover_title", "explicit_text"}
        and retry_title in compact(retry.get("ocr_text"))
        and (not first_author or compact(retry.get("explicit_author_name")) == first_author)
    )
    status = "corrected" if corrected else "unresolved"
    selected = deepcopy(retry if corrected else first)
    disagreement = not corrected and len(conflicts) == 1 and _credible_ocr_title_disagreement(first, retry)
    reconfirmed_conflict = not corrected and len(conflicts) == 1 and _credible_ocr_title_reconfirmation(first, retry)
    uncertain = disagreement or reconfirmed_conflict
    if uncertain:
        selected.update(
            confidence="Low", evidence_type="explicit_text", title_role="unknown",
            promotion_eligible=False, focus_role="supporting_text", screen_type="text_surface",
        )
    selected["ocr_alias_conflict_review"] = {
        "status": status,
        "source_alias_conflicts": deepcopy(conflicts),
        "first_read": deepcopy(first),
        "retry_read": deepcopy(retry),
    }
    if uncertain:
        selected["ocr_alias_conflict_review"].update(
            authority="uncertain", authority_reason=(
                "source_alias_conflict_persists_after_reread"
                if reconfirmed_conflict else "conflicting_direct_readings"
            ),
        )
    merged["images"] = [selected]
    if corrected:
        merged["chunk_summary"] = incoming.get("chunk_summary") or base.get("chunk_summary")
    merged["limitations"] = list(dict.fromkeys([
        *(base.get("limitations") or []), *(incoming.get("limitations") or []),
    ]))
    return merged, status



def image_ocr_diagnostic_title_surfaces(image_items: object) -> list[str]:
    """Return raw OCR surfaces for diagnostics; this function grants no authority."""
    if not isinstance(image_items, list):
        return []
    surfaces: list[str] = []
    seen: set[str] = set()
    for item in image_items:
        if not isinstance(item, dict):
            continue
        review = item.get("ocr_alias_conflict_review")
        readings = [item]
        if isinstance(review, dict):
            readings.extend(review.get(key) for key in ("first_read", "retry_read"))
        for reading in readings:
            if not isinstance(reading, dict):
                continue
            if str(reading.get("evidence_type") or "").lower() not in {"explicit_text", "cover_title"}:
                continue
            value = reading.get("explicit_work_title")
            key = _ocr_title_key(value)
            if key and key not in seen:
                surfaces.append(value)
                seen.add(key)
    return surfaces



def mark_image_ocr_reader_diagnostics(
    text: object, image_items: object, *, accepted_title: str = "", original_text: str = "",
) -> str:
    """Only whole unsupported OCR spans receive a diagnostic wrapper.

    Preserve original author clauses and accepted canonical coordinates verbatim.
    These protected quotations grant no new work/alias/publication authority.
    """
    if not isinstance(text, str) or not text.strip():
        return text if isinstance(text, str) else ""
    accepted = _ocr_title_key(accepted_title)
    surfaces = [value for value in image_ocr_diagnostic_title_surfaces(image_items)
                if _ocr_title_key(value) != accepted
                and not image_ocr_source_title_visible(value, original_text)]
    if not surfaces:
        return text
    protected = [(match.start(), match.end()) for match in re.finditer(
        r"\[이미지 OCR 진단·비권한 인용\]「[^」]*」\(원시 판독·문맥 귀속 미검증\)", text)]
    if isinstance(accepted_title, str) and accepted_title.strip():
        protected.extend((match.start(), match.end()) for match in re.finditer(
            _image_ocr_whole_surface_pattern(accepted_title), text, re.IGNORECASE))
    if isinstance(original_text, str):
        # Actual complete author clauses only; never protect a generated mixed line.
        word = r"0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ_"
        for clause in re.findall(r"[^\n.!?。！？;；]+(?:[.!?。！？;；]|$)", original_text):
            clause = clause.strip()
            if not clause:
                continue
            for match in re.finditer(re.escape(clause), text):
                left_inside = bool(match.start() and re.match(rf"[{word}]", clause[0])
                                   and re.match(rf"[{word}]", text[match.start() - 1]))
                right_inside = bool(match.end() < len(text) and re.match(rf"[{word}]", clause[-1])
                                    and re.match(rf"[{word}]", text[match.end()]))
                if not left_inside and not right_inside:
                    protected.append((match.start(), match.end()))
    alternatives = [_image_ocr_whole_surface_pattern(value)
                    for value in sorted(set(surfaces), key=len, reverse=True)]
    parts, cursor = [], 0
    for match in re.finditer("|".join(alternatives), text, re.IGNORECASE):
        if any(match.start() < end and match.end() > start for start, end in protected):
            continue
        parts.append(text[cursor:match.start()])
        parts.append("[이미지 OCR 진단·비권한 인용]「" + match.group(0)
                     + "」(원시 판독·문맥 귀속 미검증)")
        cursor = match.end()
    parts.append(text[cursor:])
    return "".join(parts)


def image_ocr_source_title_visible(value: object, source_text: object) -> bool:
    """Bind a whole surface to actual original-author text; never a word fragment."""
    return bool(isinstance(value, str) and value.strip() and isinstance(source_text, str)
                and re.search(_image_ocr_whole_surface_pattern(value), source_text, re.IGNORECASE))

def _image_ocr_whole_surface_pattern(value: str) -> str:
    """Whole lexical surface with Korean particle lookahead; match excludes particle."""
    token = r"\s*".join(re.escape(part) for part in value.strip().split())
    word = r"0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ_"
    particle = r"(?:이라고|에서|에게|한테|으로|하고|처럼|까지|부터|라고|이라|이다|은|는|이|가|을|를|의|도|만|에|와|과|랑|로|라|다)?"
    return rf"(?<![{word}]){token}(?={particle}(?![{word}]))"
