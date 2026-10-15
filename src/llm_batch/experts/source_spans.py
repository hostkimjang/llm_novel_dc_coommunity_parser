"""Source-preserving author text used by discourse and orchestration."""

from __future__ import annotations

import re
from typing import Any, Dict, List


_DERIVED_PREFIXES = (
    "[이미지 OCR]", "[이미지 요약]", "[이미지 설명]",
    "[VLM 요약]", "[VLM 설명]",
)
_DERIVED_PROVENANCE = (
    "ocr", "vlm", "generated", "summary", "image", "search", "link_preview",
)


def _original_author_text(value: Any) -> str:
    if isinstance(value, dict):
        if str(value.get("type") or "text").strip().lower() != "text":
            return ""
        if any(value.get(key) for key in ("url", "image_url", "href", "src")):
            return ""
        if any(
            str(value.get(key) or "").strip().lower() in {"true", "1", "yes"}
            for key in ("is_generated", "generated", "from_ocr", "is_ocr")
        ):
            return ""
        provenance = " ".join(
            str(value.get(key) or "")
            for key in ("source", "origin", "provenance", "generated_source")
        ).lower()
        if any(marker in provenance for marker in _DERIVED_PROVENANCE):
            return ""
        speaker = str(value.get("speaker") or "").strip().lower()
        if speaker and speaker not in {"author", "post_author"}:
            return ""
        if value.get("is_quote") is True or value.get("quoted") is True:
            return ""
        value = value.get("text") or value.get("content")
    if not isinstance(value, str):
        return ""
    if value.lstrip().startswith(_DERIVED_PREFIXES):
        return ""
    return value if value.strip() else ""


def author_text_spans(post: Any) -> List[Dict[str, Any]]:
    """Return only original post-author title/body spans, retaining block position."""
    if not isinstance(post, dict):
        return []
    spans: List[Dict[str, Any]] = []
    title = str(post.get("title") or "")
    if title.strip():
        spans.append({
            "text": title, "source": "author_title", "speaker": "author",
            "modality": "text", "position": 0,
        })
    blocks = post.get("content_blocks")
    if not isinstance(blocks, list) or not blocks:
        content = post.get("content")
        blocks = content if isinstance(content, (list, tuple)) else [content]
    for index, block in enumerate(blocks):
        text = _original_author_text(block)
        if text:
            spans.append({
                "text": text, "source": "author_body", "speaker": "author",
                "modality": "text", "position": index,
            })
    return spans


_DIRECT_REQUEST = re.compile(
    r"추천\s*(?:(?:좀\s*)?해\s*(?:줘|조|주라|주세요|줄래|주셈)|좀)"
)
_NEXT_READING_QUESTION = re.compile(r"(?:뭐|무엇을)\s*읽으면\s*좋을까")
_AUTHOR_SUBJECT = re.compile(r"(?<!\S)(?:나는|저는|내가|제가)\s+")
_OTHER_REQUEST_SPEAKER = r"(?:친구|지인|동생|형|누나|언니|작가|댓글|타인|누가|누군가|다른\s*사람)"
_QUOTE_LINE = re.compile(r"(?m)^[ \t]*(?:>|[│|]|인용\s*[:：]|댓글\s*[:：]).*")


def direct_author_recommendation_request_spans(post: Any) -> List[Dict[str, Any]]:
    """Return current author request clauses with original block-local offsets.

    Comments and derived blocks never enter this scan. Quote state carries
    across original body blocks, while every receipt keeps its own raw field.
    No quoted text is removed or joined to manufacture a source coordinate.
    """
    if not isinstance(post, dict):
        return []
    found: List[Dict[str, Any]] = []
    body_quote = ""
    for span in author_text_spans(post):
        raw = str(span["text"])
        source = span["source"]
        position = span["position"]
        field = "title" if source == "author_title" else (
            "content_blocks" if isinstance(post.get("content_blocks"), list)
            and post["content_blocks"] else "content"
        )
        values = post.get(field)
        block = values[position] if isinstance(values, (list, tuple)) else values
        text_key = ("text" if block.get("text") else "content") if isinstance(block, dict) else None
        quote = "" if source == "author_title" else body_quote
        quoted = [False] * len(raw)
        closed_quotes: List[int] = []
        boundaries = {0, len(raw)}
        for match in _QUOTE_LINE.finditer(raw):
            quoted[match.start():match.end()] = [True] * (match.end() - match.start())
            boundaries.update((match.start(), min(len(raw), match.end() + 1)))
        for index, char in enumerate(raw):
            if quoted[index]:
                continue
            if quote:
                quoted[index] = True
                if char == quote:
                    closed_quotes.append(index)
                    quote = ""
            elif char in {'"', '“', '‘'}:
                quoted[index] = True
                quote = {'"': '"', '“': '”', '‘': '’'}[char]
            elif char in ".!?。！？":
                boundaries.add(index + 1)
        if source == "author_body":
            body_quote = quote
        cuts = sorted(boundaries)
        for left, right in zip(cuts, cuts[1:]):
            clause = raw[left:right]
            requests = [(match, "explicit_recommendation") for match in _DIRECT_REQUEST.finditer(clause)]
            requests += [(match, "next_reading_question") for match in _NEXT_READING_QUESTION.finditer(clause)]
            for request, kind in sorted(requests, key=lambda item: item[0].start()):
                request_start, request_end = left + request.start(), left + request.end()
                if any(quoted[request_start:request_end]):
                    continue
                start = left + len(clause) - len(clause.lstrip())
                end = right - (len(clause) - len(clause.rstrip()))
                original_prefix = raw[start:request_start]
                if re.match(r"(?:만약|가령|예를\s*들어)\b", original_prefix):
                    continue
                subjects = [match for match in _AUTHOR_SUBJECT.finditer(raw[start:request_start])
                            if not any(quoted[start + match.start():start + match.end()])]
                labelled_scope = re.match(
                    r"(?:(?:기록|대화\s*기록|전재|원문|버튼\s*문구|화면\s*문구)\s*[:：]|"
                    + _OTHER_REQUEST_SPEAKER + r"\s*(?:[:：]|[이가]))",
                    original_prefix,
                )
                if labelled_scope:
                    # Decide the original label scope BEFORE selecting '나는'.
                    # A closed quoted utterance followed by an independent
                    # author subject is the observed P01 transition. An
                    # unquoted '친구: 나는...' remains the friend's speech.
                    if not subjects:
                        continue
                    author_start = start + subjects[-1].start()
                    preceding_closes = [index for index in closed_quotes if start <= index < author_start]
                    if not preceding_closes or not re.fullmatch(
                        r"[\s.!?。！？,;:：]*", raw[preceding_closes[-1] + 1:author_start],
                    ):
                        continue
                if subjects:
                    # A self-subject outside the friend's quote starts the
                    # independent author clause, without shifting raw offsets.
                    start += subjects[-1].start()
                target, tail = raw[start:request_start], raw[request_end:end].strip()
                if not subjects and re.search(
                    _OTHER_REQUEST_SPEAKER + r"\s*(?:[이가]|[:：])", target,
                ):
                    continue
                if re.match(r"(?:기록|대화\s*기록|전재|원문|버튼\s*문구|화면\s*문구)\s*[:：]", target):
                    continue
                if tail and not re.fullmatch(r"[?？!！.,。~\s]*", tail):
                    continue
                if len(re.sub(r"\s|[?？!！.,。]", "", target)) < 3:
                    continue
                found.append({
                    "source": source, "speaker": "author", "modality": "text",
                    "field": field, "position": position, "text_key": text_key,
                    "char_start": start, "char_end": end, "text": raw[start:end],
                    "request_start": request_start, "request_end": request_end,
                    "request_kind": kind,
                })
                break
    return found


def has_direct_author_recommendation_request(post: Any) -> bool:
    """Keep the existing bool API while sharing current source coordinates."""
    return bool(direct_author_recommendation_request_spans(post))
