"""검색 원문에 적힌 후보별 별칭 관계. 공개·학습 proof 계약은 확장하지 않는다."""
from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import urlsplit

from ..experts.source_spans import author_text_spans
from .anticipation_search_probe import source_bound_alias_assertion


_WORD = r"0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ_"
_FIELDS = ("title", "page_title", "content", "snippet", "description")
_MARKER = r"(?:약칭|별칭|줄임말|통칭|약어)"
_NONWORK_MEDIA = {"webtoon", "comic", "manga", "anime", "game", "movie", "comic_page", "manga_page"}


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _url(value):
    if not isinstance(value, str) or len(value) > 4096:
        return ""
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in {"https", "http"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.port not in {None, 80, 443}):
            return ""
    except ValueError:
        return ""
    return value


def _quotes(text):
    pairs = {'"': '"', "'": "'", '“': '”', '‘': '’', '「': '」', '『': '』'}
    ranges = []
    start, closing = None, None
    for index, char in enumerate(text):
        if (char == "'" and index and index + 1 < len(text)
                and re.fullmatch(r"[A-Za-z0-9]", text[index-1])
                and re.fullmatch(r"[A-Za-z0-9]", text[index+1])):
            continue  # 영어 단어 내부 apostrophe는 발화 인용 시작이 아니다.
        if index and text[index-1] == "\\":
            continue
        if closing:
            if char == closing:
                ranges.append((start, index + 1))
                start, closing = None, None
        elif char in pairs:
            start, closing = index, pairs[char]
    if closing:
        ranges.append((start, len(text)))
    return ranges


def _comment_spans(ctx, post):
    """댓글을 작성자 원문과 분리한다. 보존 carrier가 있으면 실제 전달 순서와 대조한다."""
    live = getattr(ctx, "comments", None) or []
    if not isinstance(live, (list, tuple)) or len(live) > 256 or any(type(x) is not str for x in live):
        return None
    original = getattr(ctx, "_final_source_original_inputs", None)
    records = None
    if original is not None:
        if not isinstance(original, (list, tuple)) or any(type(x) is not dict for x in original):
            return None
        records = [x for x in original if x.get("origin") == "comment"
                   and x.get("caller_disposition") == "passed_to_source"]
        if (any(type(x.get("raw_text")) is not str or type(x.get("original_index")) is not int
                or x["original_index"] < 0 for x in records)
                or len({x["original_index"] for x in records}) != len(records)
                or [x["raw_text"].strip() for x in records] != list(live)):
            return None
        for record in records:
            key = record.get("selection_key")
            if type(key) is not str or key not in {"", "content", "text"} or record.get("raw_path") != (
                    f"/comments/{record['original_index']}" + ("/" + key if key else "")):
                return None
    metadata = post.get("comment_metadata") or []
    metadata = metadata if isinstance(metadata, list) else []
    # carrier가 아직 없는 Decoder 단계에서는 완전한 순서/preview 대응이 있는 경우만 ID를 붙인다.
    complete_metadata = (len(metadata) == len(live) and all(
        type(item) is dict and type(item.get("index")) is int and item["index"] == i
        and item.get("content_preview") == text[:80]
        for i, (item, text) in enumerate(zip(metadata, live))))
    spans = []
    for index, text in enumerate(live):
        if not text.strip():
            continue
        record = records[index] if records is not None else None
        original_index = record["original_index"] if record else (index if complete_metadata else None)
        raw = record["raw_text"] if record else text
        path = record.get("raw_path") if record else f"/ctx/comments/{index}"
        matches = [item for item in metadata if isinstance(item, dict)
                   and type(item.get("index")) is int and item["index"] == original_index]
        comment_id = matches[0].get("comment_id") if len(matches) == 1 else None
        if not ((type(comment_id) is int and comment_id > 0)
                or (type(comment_id) is str and comment_id.strip())):
            comment_id = None
        spans.append({"text": text, "source": "comment", "speaker": "comment_author",
            "modality": "text", "position": index, "original_index": original_index,
            "raw_path": path, "raw_text": raw,
            "raw_text_offset": len(raw) - len(raw.lstrip()) if record else 0,
            "comment_id": comment_id,
            "binding": "original_comment_capture" if record else "live_context_comment"})
    return spans


def _source(ctx):
    post = getattr(ctx, "post_data", None)
    if not isinstance(post, dict) or type(getattr(ctx, "post_id", None)) is not int:
        return None
    if ("post_id" in post and type(post["post_id"]) is not int) or post.get("post_id", ctx.post_id) != ctx.post_id:
        return None
    capture = getattr(ctx, "_batch_alias_original_source", None)
    if capture is not None:
        from ..domain.alias_learning import alias_source_from_context
        original = alias_source_from_context(ctx)
        if not original:
            return None
        old = [(x["source"], x["text"]) for x in author_text_spans(original)]
        live = [(x["source"], x["text"]) for x in author_text_spans(post)]
        if old != live:
            return None
        author_post = original
    else:
        author_post = post
    comments = _comment_spans(ctx, post)
    if comments is None:
        return None
    spans = author_text_spans(author_post) + comments
    if sum(len(x["text"]) for x in spans) > 32000:
        return None
    return spans


def _affirmative_clause(text, match, quote_ranges):
    title_span, alias_span = match.span("title"), match.span("alias")
    # 표제만 감싼 따옴표는 허용하지만 관계 자체를 인용한 발화는 사용하지 않는다.
    relation_points = (match.start("marker"),)
    if any(lo <= point < hi for lo, hi in quote_ranges for point in relation_points):
        return False
    masked = list(text)
    for lo, hi in (title_span, alias_span):
        masked[lo:hi] = " " * (hi-lo)
    outside = "".join(masked)
    # 표제 안 문장부호는 절 경계가 아니다. 외부 URI의 마침표도 표제 구간 밖이다.
    boundaries = [m.start() for m in re.finditer(r"[.!?。！？\n\r;；]", outside)
                  if not any(lo <= m.start() < hi for lo, hi in quote_ranges)]
    left = max((p + 1 for p in boundaries if p < match.start()), default=0)
    right = min((p for p in boundaries if p >= match.end()), default=len(text))
    prefix = outside[left:match.start()]
    tail = outside[match.end():right]
    terminal = outside[right:right+1]
    if terminal in {"?", "？"}:
        return False
    if re.search(r"(?:만약\s|가정(?:하면|하자|상)|예를\s*들어|가령\s|친구(?:가|는)\s|누군가(?:가|는)\s|인용\s*[:：])", prefix):
        return False
    if re.search(r"(?:웹툰|만화|애니메이션|게임|영화|드라마)\s*['\"「『]?\s*$", prefix):
        return False
    # 명명 자체의 부정/전언만 배제한다. 뒤의 독서·결말 평가 부정은 명명을 철회하지 않는다.
    if re.match(r"\s*(?:은|는|이|가)?\s*(?:아니(?:다|라|라고|라는|며|고)|아님|아닌|"
                r"잘못|오해|거짓|취소|철회|가칭|추정|일까|인가|맞나|이라면|라면|다면|가정)", tail):
        return False
    if re.search(r"(?:그|이)\s*(?:명명|선언|약칭|별칭)[^.!?\n]{0,24}(?:취소|철회|아니|잘못)", tail):
        return False
    if re.search(r"(?:부르|불렀|불리)[^.!?\n]{0,24}(?:가정|추정|취소|철회|친구|누군가)", tail):
        return False
    # 같은 필드의 뒤 문장이 바로 앞 명명을 철회하면 그 긍정 출현을 차용하지 않는다.
    following = outside[right+1:right+201] if right < len(text) else ""
    alias = re.escape(match.group("alias"))
    title = re.escape(match.group("title"))
    # 완결된 철회 부정은 명명 취소가 아니다. 전언/조건형은 이 예외에 넣지 않는다.
    # 나중의 별도 긍정 철회는 같은 기존 검색 범위에서 계속 찾는다.
    withdrawal = (rf"(?:취소|철회)(?!\s*하지\s*않(?:았다|는다|습니다|았습니다|다)"
                  rf"(?![{_WORD}]))")
    if re.search(rf"(?:{alias}(?:은|는|이라는)?|{title}(?:의|은|는)?|(?:그|이)\s*(?:명명|선언|{_MARKER}))[^.!?\n]{{0,32}}"
                 rf"(?:아니(?:다|라|라고)|아님|잘못|{withdrawal})", following):
        return False
    return True


def candidate_alias_relation(ctx, title, alias, *, rows=None):
    """현재 원문 alias와 같은 외부 필드의 명명 관계를 재검산해 비권한 증거로 반환한다.

    재호출 때 원문·row·필드·URL·span을 새로 읽으며 캐시나 등록을 수행하지 않는다.
    서로 다른 작품의 경쟁 선언은 각각 후보 증거일 뿐 어느 쪽의 공개 승인도 아니다.
    """
    if (not isinstance(title, str) or not 2 <= len(title.strip()) <= 240
            or not isinstance(alias, str) or not re.fullmatch(rf"[{_WORD}]{{2,32}}", alias)):
        return None
    title = title.strip()
    spans = _source(ctx)
    if spans is None:
        return None
    visible = re.compile(rf"(?<![{_WORD}]){re.escape(alias)}"
                         rf"(?:께서|에게|에서|으로|은|는|이|가|을|를|의|도|만|에|로)?(?![{_WORD}])")
    source_hits = [(i, m.span()) for i, item in enumerate(spans) for m in visible.finditer(item["text"])]
    if not source_hits:
        return None
    hit_details = []
    for index, span in source_hits:
        source = spans[index]
        offset = source.get("raw_text_offset", 0)
        hit_details.append({"source_index": index, "source": source["source"],
            "speaker": source["speaker"], "position": source["position"],
            "original_index": source.get("original_index"), "comment_id": source.get("comment_id"),
            "raw_path": source.get("raw_path"), "binding": source.get("binding", "author_text"),
            "alias_span": [span[0], span[0] + len(alias)],
            "raw_alias_span": [offset + span[0], offset + span[0] + len(alias)]})
    rows = getattr(ctx, "search_results", None) if rows is None else rows
    if not isinstance(rows, (list, tuple)) or len(rows) > 256:
        return None
    title_pattern = r"\s+".join(re.escape(x) for x in title.split())
    t = rf"(?P<title>{title_pattern})"
    a = rf"(?P<alias>{re.escape(alias)})"
    boundary = rf"(?:이다|임|이라고|라고|이라는|이라|은|는|이|가|을|를|의|도|만)?(?![{_WORD}])"
    patterns = (
        re.compile(rf"(?<![{_WORD}]){t}['\"”’」』]?\s*(?:[,，:：]\s*)?(?:의\s*)?"
                   rf"(?P<marker>{_MARKER})(?:은|는|이|가|:|=)?\s*['\"“‘「『]?{a}['\"”’」』]?{boundary}"),
        re.compile(rf"(?<![{_WORD}]){t}['\"”’」』]?\s*(?:[,，:：]\s*|(?:을|를)\s*)?"
                   rf"(?P<marker>줄여서|줄여)\s*['\"“‘「『]?{a}['\"”’」』]?{boundary}"),
        re.compile(rf"(?<![{_WORD}]){a}['\"”’」』]?\s*(?:은|는|이란|란)\s*['\"“‘「『]?"
                   rf"{t}['\"”’」』]?\s*(?:의\s*)?(?P<marker>{_MARKER})"),
    )
    clean_rows = []
    for index, row in enumerate(rows[:120]):
        if not isinstance(row, dict) or not _url(row.get("url")):
            continue
        if (row.get("_ocr_diagnostic_only") is True or row.get("_purpose") == "image_ocr_diagnostic_probe"
                or str(row.get("media_type") or "").lower() in _NONWORK_MEDIA
                or str(row.get("page_type") or "").lower() in _NONWORK_MEDIA):
            continue
        rejected_same_field = False
        for field in _FIELDS:
            text = row.get(field)
            if not isinstance(text, str) or len(text) > 30000:
                continue
            quote_ranges = _quotes(text)
            for pattern in patterns:
                for match in pattern.finditer(text):
                    if not _affirmative_clause(text, match, quote_ranges):
                        rejected_same_field = True
                        continue
                    payload = {k: row.get(k) for k in (*_FIELDS, "url", "media_type", "page_type", "_ocr_diagnostic_only", "_purpose")}
                    try:
                        row_fingerprint = _digest(payload)
                    except (TypeError, ValueError):
                        continue
                    return {
                        "schema_version": "source_candidate_alias_relation_v2",
                        "relation_kind": "same_field_explicit_declaration",
                        "title": title, "alias": alias, "post_id": ctx.post_id,
                        "source_fields_sha256": _digest(spans), "source_hits": source_hits,
                        "source_hit_details": hit_details,
                        "row_index": index, "row_relation_fields_sha256": row_fingerprint,
                        "source_url": row["url"], "field": field, "field_sha256": _digest(text),
                        "title_span": list(match.span("title")), "alias_span": list(match.span("alias")),
                        "declaration_span": list(match.span()),
                        "publication_authority": False, "learning_authority": False,
                    }
        if not rejected_same_field:
            clean_rows.append(row)
    # 기존 정확한 Namu 문서 소유권 계약은 그대로 사용한다. 임의 cross-field 추론이 아니다.
    strict = source_bound_alias_assertion(title, [alias], clean_rows,
        source_text="\n".join(x["text"] for x in spans))
    if strict:
        return {"schema_version": "source_candidate_alias_relation_v2",
            "relation_kind": "existing_strict_document_alias_contract", "title": title,
            "alias": alias, "post_id": ctx.post_id, "source_fields_sha256": _digest(spans),
            "source_hits": source_hits, "source_hit_details": hit_details,
            "strict_document_assertion": strict, "publication_authority": False, "learning_authority": False}
    return None
