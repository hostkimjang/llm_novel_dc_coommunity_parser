"""Keep stored analysis notes traceable to the evidence shipped with the row."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence


_EID = re.compile(r"(?<![A-Za-z0-9])E\d{3}(?!\d)", re.IGNORECASE)
_SENTENCE = re.compile(r"(?<=[.!?。])\s+|\n+")
_PROTAGONIST_NAME = re.compile(r"(?<![가-힣])주인공\s+([가-힣]{2,8}?)(?=\s|과|와|의|이|가|은|는|을|를|[,.!?]|$)")
_QUOTED_SURFACE = re.compile(r"['‘“]([^'’”]{2,40})['’”]")


def _source_texts(
    post: Mapping[str, Any] | None,
    comments: Sequence[Any] | None,
    catalog: Sequence[Mapping[str, Any]],
) -> list[str]:
    texts: list[str] = []
    if isinstance(post, Mapping):
        texts.append(str(post.get("title") or ""))
        for block in post.get("content_blocks") or []:
            if isinstance(block, Mapping) and block.get("type") == "text":
                texts.append(str(block.get("text") or ""))
    for comment in comments or []:
        if isinstance(comment, Mapping):
            texts.append(str(comment.get("content") or ""))
        elif isinstance(comment, str):
            texts.append(comment)
    for row in catalog:
        if isinstance(row, Mapping):
            texts.append(str(row.get("snippet") or row.get("content") or ""))
    return texts


def _explicit_protagonist_relation(name: str, texts: Sequence[str]) -> bool:
    escaped = re.escape(name)
    name_end = r"(?=$|[^가-힣]|(?:이다|입니다|이|가|은|는|을|를|과|와|의)(?=$|[^가-힣]))"
    patterns = (
        re.compile(rf"주인공\s*(?:은|이|:|：)?\s*{escaped}{name_end}"),
        re.compile(rf"(?<![가-힣]){escaped}\s*(?:은|는|이|가)\s*주인공"),
    )
    for text in texts:
        for pattern in patterns:
            for match in pattern.finditer(text):
                tail = text[match.end():match.end() + 12].split(".", 1)[0]
                if not re.match(r"^\s*(?:이|가|은|는)?\s*아니", tail):
                    return True
    return False


def _remove_false_comment_attribution(notes: str, comments: Sequence[Any] | None) -> str:
    """Do not attribute search-derived names to comments that lack them."""
    comment_text = " ".join(
        str(item.get("content") or "") if isinstance(item, Mapping) else str(item)
        for item in comments or []
    )

    def unsupported(clause: str) -> bool:
        quoted = _QUOTED_SURFACE.findall(clause)
        def explicitly_negated(name: str) -> bool:
            return bool(re.search(
                rf"['‘“]?{re.escape(name)}['’”]?\s*(?:을|를|은|는|이|가)?\s*"
                r"(?:언급하지\s*않|언급되지\s*않|등장하지\s*않|"
                r"나오지\s*않|적히지\s*않|쓰이지\s*않|없습니다)",
                clause,
            ))
        return bool(quoted) and any(
            name not in comment_text and not explicitly_negated(name)
            for name in quoted
        )

    search_comment = re.compile(
        r"(검색 결과 E\d{3}에서[^.。\n]*?),\s*(본문 댓글에서도[^.。\n]*[.。])"
    )

    def retain_search(match: re.Match[str]) -> str:
        if not unsupported(match.group(2)):
            return match.group(0)
        prefix = match.group(1).rstrip()
        prefix = re.sub(r"하였고$", "했습니다", prefix)
        return prefix + "."

    notes = search_comment.sub(retain_search, notes)
    comments_claim = re.compile(r"댓글들은[^.。\n]*[.。]")
    return comments_claim.sub(
        lambda match: "" if unsupported(match.group(0)) else match.group(0), notes
    )


def sanitize_analysis_notes_evidence(
    notes: str | None,
    *,
    catalog: Sequence[Mapping[str, Any]] | None,
    post: Mapping[str, Any] | None = None,
    comments: Sequence[Any] | None = None,
) -> str | None:
    """Drop unsupported note clauses while leaving title and gate fields alone.

    EIDs must exist in the *stored* catalog, not only in a larger prompt-time
    search pool. An untraceable citation invalidates its sentence. A named
    protagonist claim needs an explicit relation in a source sentence; merely
    mentioning the name and ``주인공`` in different clauses is insufficient.
    """
    if not isinstance(notes, str) or not notes.strip():
        return None
    notes = _remove_false_comment_attribution(notes.strip(), comments)
    rows = [row for row in (catalog or []) if isinstance(row, Mapping)]
    if not rows:
        return notes.strip()
    valid_eids = {str(row.get("eid") or "").upper() for row in rows}
    sources = _source_texts(post, comments, rows)
    cleaned: list[str] = []
    changed = False
    for raw_sentence in _SENTENCE.split(notes.strip()):
        sentence = raw_sentence.strip()
        if not sentence:
            continue
        if any(match.group().upper() not in valid_eids for match in _EID.finditer(sentence)):
            changed = True
            continue
        revised = _PROTAGONIST_NAME.sub(
            lambda match: match.group() if _explicit_protagonist_relation(match.group(1), sources)
            else match.group(1),
            sentence,
        )
        changed = changed or revised != sentence
        cleaned.append(revised)
    return ("\n".join(cleaned) or None) if changed else notes.strip()
