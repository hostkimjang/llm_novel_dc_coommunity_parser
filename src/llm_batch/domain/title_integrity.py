"""Exact display-title integrity helpers for official work identities.

Leading square-bracket components are not all interchangeable.  Some are
presentation badges (for example ``[독점]``), while others are part of the
work identity (for example ``[림월드]``).  These helpers parse every leading
component and compare the remaining title body exactly after conservative
spacing/punctuation normalization.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, FrozenSet, Tuple
import unicodedata


_LEADING_COMPONENT_RE = re.compile(
    r"^\s*(?P<display>\[(?P<square>[^\]]{1,32})\]|【(?P<lenticular>[^】]{1,32})】)"
)
_TRAILING_COMPONENT_RE = re.compile(
    r"(?P<display>\[(?P<square>[^\]]{1,32})\]|【(?P<lenticular>[^】]{1,32})】)\s*$"
)
def normalize_title_integrity_token(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[\W_]+", "", normalized, flags=re.UNICODE)


PRESENTATION_BADGE_COMPONENTS: FrozenSet[str] = frozenset(
    normalize_title_integrity_token(value)
    for value in (
        "독점",
        "완결",
        "무료",
        "무료연재",
        "유료",
        "유료연재",
        "플러스",
        "챌린지",
        "신작",
        "공지",
        "이벤트",
        "성인",
        "19금",
        "웹소설",
        "소설",
        "노벨피아",
        "문피아",
        "카카오페이지",
        "네이버시리즈",
        "리디",
        "스포",
        "질문",
        "소신발언",
        "잡담",
        "후기",
        "리뷰",
        "념글",
        "근데",
        "약스포",
        "강스포",
        "추천",
        "정보",
    )
)


@dataclass(frozen=True)
class TitleIntegrityParts:
    identity_components: Tuple[str, ...]
    identity_component_displays: Tuple[str, ...]
    presentation_components: Tuple[str, ...]
    suffix_identity_components: Tuple[str, ...]
    suffix_identity_component_displays: Tuple[str, ...]
    suffix_presentation_components: Tuple[str, ...]
    base_display: str
    base_normalized: str


def parse_title_integrity_parts(
    value: Any,
    *,
    presentation_badges: FrozenSet[str] = PRESENTATION_BADGE_COMPONENTS,
) -> TitleIntegrityParts:
    remaining = str(value or "").strip()
    identity_components: list[str] = []
    identity_displays: list[str] = []
    presentation_components: list[str] = []
    suffix_identity_components: list[str] = []
    suffix_identity_displays: list[str] = []
    suffix_presentation_components: list[str] = []

    while remaining:
        match = _LEADING_COMPONENT_RE.match(remaining)
        if not match:
            break
        display = str(match.group("display") or "").strip()
        inner = match.group("square") or match.group("lenticular") or ""
        normalized = normalize_title_integrity_token(inner)
        remaining = remaining[match.end() :].lstrip()
        if not normalized:
            continue
        if normalized in presentation_badges:
            presentation_components.append(normalized)
        else:
            identity_components.append(normalized)
            identity_displays.append(display)

    while remaining:
        match = _TRAILING_COMPONENT_RE.search(remaining)
        if not match:
            break
        display = str(match.group("display") or "").strip()
        inner = match.group("square") or match.group("lenticular") or ""
        normalized = normalize_title_integrity_token(inner)
        remaining = remaining[: match.start()].rstrip()
        if not normalized:
            continue
        if normalized in presentation_badges:
            suffix_presentation_components.insert(0, normalized)
        else:
            suffix_identity_components.insert(0, normalized)
            suffix_identity_displays.insert(0, display)

    return TitleIntegrityParts(
        identity_components=tuple(identity_components),
        identity_component_displays=tuple(identity_displays),
        presentation_components=tuple(presentation_components),
        suffix_identity_components=tuple(suffix_identity_components),
        suffix_identity_component_displays=tuple(suffix_identity_displays),
        suffix_presentation_components=tuple(suffix_presentation_components),
        base_display=remaining.strip(),
        base_normalized=normalize_title_integrity_token(remaining),
    )


def exact_title_integrity_match(expected: Any, actual: Any) -> bool:
    if not str(expected or "").strip() or not str(actual or "").strip():
        return False
    expected_parts = parse_title_integrity_parts(expected)
    actual_parts = parse_title_integrity_parts(actual)
    return bool(
        expected_parts.base_normalized
        and expected_parts.base_normalized == actual_parts.base_normalized
        and expected_parts.identity_components == actual_parts.identity_components
        and expected_parts.suffix_identity_components
        == actual_parts.suffix_identity_components
    )
