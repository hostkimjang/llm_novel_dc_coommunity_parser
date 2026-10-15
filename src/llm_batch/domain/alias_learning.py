"""게시글별 별칭 학습 자격. 작품 공개 신뢰도는 이 모듈의 입력이 아니다."""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from copy import deepcopy


SCHEMA = "source_bound_alias_learning_v3"
EXTERNAL_SCHEMA = "source_bound_alias_learning_v4"
_EXTERNAL_KEYS = ("title", "page_title", "url", "content", "snippet", "description")
_ASSERTION_KEYS = {"title", "alias_surface", "support_surface", "source_url", "source_title",
                   "source_row_sha256", "source_text_sha256", "assertion_sentence_sha256"}
_WORD = r"0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ_"
_PARTICLE = r"(?:에서|에게|한테|으로|하고|처럼|까지|부터|은|는|이|가|을|를|의|도|만|에|와|과|랑|로)?"
_RANK = {"max": 4, "high": 3, "medium": 2, "mid": 2, "low": 1}


def _key(value):
    return re.sub(r"\s+", "", value).casefold() if isinstance(value, str) else ""


def _sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _rank(value):
    return _RANK.get(value.lower().strip(), 0) if isinstance(value, str) else 0


def capture_alias_source(post):
    """이미지 보강 전에 원문 field/index/역할 표시를 따로 보존한다."""
    data = post if isinstance(post, Mapping) else post.model_dump()
    captured = deepcopy({key: data.get(key) for key in ("post_id", "title", "content_blocks")})
    captured["_alias_capture_scope_sha256"] = _source_scope_sha(_fields(captured), _boundary_fields(captured))
    return captured


def alias_source_from_context(ctx):
    # source 없는 구형/부분 context를 working post의 파생 문구로 보충하지 않는다.
    source = getattr(ctx, "_batch_alias_original_source", None)
    if (not isinstance(source, Mapping) or type(source.get("post_id")) is not int
        or type(getattr(ctx, "post_id", None)) is not int or source["post_id"] != ctx.post_id):
        return {}
    if source.get("_alias_capture_scope_sha256") != _source_scope_sha(_fields(source), _boundary_fields(source)):
        return {}
    return source


def _flag(block, keys):
    return any(str(block.get(key) or "").strip().lower() in {"true", "1", "yes"} for key in keys)


def _derived_block(block):
    """파생 문구는 lexical 근거뿐 아니라 원문의 발화 경계를 바꿀 권한도 없다."""
    if _flag(block, ("is_generated", "generated", "from_ocr", "is_ocr", "model_generated")):
        return True
    provenance = " ".join(str(block.get(k) or "") for k in ("source", "origin", "provenance", "generated_source")).lower()
    if any(word in provenance for word in ("ocr", "vlm", "generated", "summary", "image", "search", "link_preview")):
        return True
    text = block.get("text")
    return isinstance(text, str) and text.lstrip().startswith(("[이미지", "[VLM"))


def _fields(post):
    """댓글과 파생 자료를 작성자 원문으로 차용하지 않는다. 원래 index는 유지한다."""
    if not isinstance(post, Mapping) or type(post.get("post_id")) is not int:
        return []
    result = []
    if isinstance(post.get("title"), str):
        result.append(("/title", post["title"]))
    blocks = post.get("content_blocks")
    if isinstance(blocks, list):
        for index, block in enumerate(blocks):
            if not isinstance(block, Mapping) or block.get("type", "text") != "text":
                continue
            if _derived_block(block) or _flag(block, ("is_quote", "quoted", "is_quoted")):
                continue
            if block.get("is_post_author") is False or (block.get("speaker") or "author") not in {"author", "op", "post_author", "original_author"}:
                continue
            text = block.get("text")
            if isinstance(text, str):
                result.append((f"/content_blocks/{index}/text", text))
    return result


def _boundary_fields(post):
    """선별 전 원래 text/quote의 경계만 보존한다. quote 내용은 학습 표면이 아니다."""
    if not isinstance(post, Mapping) or not isinstance(post.get("content_blocks"), list):
        return []
    result = []
    for index, block in enumerate(post["content_blocks"]):
        if (not isinstance(block, Mapping) or block.get("type", "text") not in {"text", "quote", "blockquote"}
            or _derived_block(block) or not isinstance(block.get("text"), str)):
            continue
        result.append({"path": f"/content_blocks/{index}/text", "text": block["text"],
                       "kind": block.get("type", "text"),
                       "quoted": block.get("type") in {"quote", "blockquote"} or _flag(block, ("is_quote", "quoted", "is_quoted")),
                       "speaker": str(block.get("speaker") or "author"),
                       "author_denied": block.get("is_post_author") is False})
    return result


def _source_scope_sha(fields, boundaries):
    return _corpus_sha({"schema_version": "alias_original_scope_v1", "lexical_fields": fields, "boundary_fields": boundaries})


def _corpus_sha(fields):
    return _sha(json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _quoted_ranges(text):
    pairs = {'"': '"', "'": "'", "“": "”", "‘": "’", "「": "」", "『": "』"}
    stack, ranges = [], []
    for i, char in enumerate(text):
        backslashes = 0
        j = i - 1
        while j >= 0 and text[j] == "\\":
            backslashes += 1
            j -= 1
        word_apostrophe = (char == "'" and i > 0 and i + 1 < len(text)
            and text[i - 1].isalnum() and text[i + 1].isalnum()
            and (not stack or stack[-1][1] != "'"
                 or re.fullmatch(r"[A-Za-z]{2}", text[i - 1] + text[i + 1]) is not None))
        # 열린 단일 인용 뒤 한글 조사는 닫힘이다. John's 같은 영문 내부 apostrophe는 유지한다.
        if backslashes % 2 or word_apostrophe:
            continue
        if stack and char == stack[-1][1]:
            start, _ = stack.pop()
            ranges.append((start, i + 1))
        elif char in pairs:
            stack.append((i, pairs[char]))
    ranges.extend((start, len(text)) for start, _ in stack)
    return ranges


def _external_speech_at(text, position, *, quote_blocks=()):
    """줄/field 경계를 넘는 명시 전언 범위. 빈 줄만으로 화자 복귀를 추정하지 않는다."""
    quotes = _quoted_ranges(text)
    active, active_end, offset = False, None, 0
    other = re.compile(
        r"(?:인용|댓글|전언|대화|타인|친구|지인|누군가|다른\s*사람|다른\s*작성자|"
        r"독자|이용자|사용자|익명)(?:\s*[0-9A-Za-z가-힣_]{1,16})?"
        r"|.{1,32}(?:의\s*(?:말|댓글|발언)|(?:가|이)\s*(?:말했다|썼다|적었다))"
    )
    own = {"작성자", "글쓴이", "문서 작성자", "필자", "나", "저", "내 설명", "내 의견"}
    section = re.compile(r"(?:(?:작품|소설|문서|별칭|약칭|연재)\s*)?"
                         r"(?:개요|소개|정보|설명|약칭|별칭|줄임말|통칭|약어|명칭|표기|유래|용례|줄거리|목차)")
    for line in text.splitlines(keepends=True):
        start = offset + len(line) - len(line.lstrip())
        if start > position:
            break
        if active_end is not None and start >= active_end:
            active, active_end = False, None
        # 발화 안의 '작성자:'나 '인용 끝'은 바깥 화자를 바꾸지 않는다.
        quoted = any(lo <= start < hi for lo, hi in quotes)
        stripped = line.strip()
        if not quoted:
            label = re.match(r"^([^:：\n\r]{1,48})\s*[:：]", stripped)
            if label:
                name = label[1].strip()
                label_started = False
                if name in own:
                    active, active_end = False, None
                elif other.fullmatch(name):
                    active, active_end = True, None
                    label_started = True
                elif not stripped[label.end():].strip() and not section.fullmatch(name):
                    # 단독 '이름:'은 화자/표제 중 어느 쪽인지 미확정이다. 임의 작성자 권한을 주지 않는다.
                    active, active_end = True, None
                    label_started = True
                if label_started and any(lo <= start < hi for lo, hi in quote_blocks):
                    # 구조화된 원래 quote 안의 라벨은 바로 뒤 발화의 닫힌 따옴표까지만 소유한다.
                    # 일반 text의 라벨 뒤 이름 인용은 이 자동 종료 규칙에 넣지 않는다.
                    opener = start + label.end()
                    while opener < len(text) and text[opener].isspace():
                        opener += 1
                    pair = {'"': '"', "'": "'", "“": "”", "‘": "’", "「": "」", "『": "』"}
                    if any(lo <= opener < hi for lo, hi in quote_blocks):
                        active_end = next((hi for lo, hi in quotes if lo == opener and hi > lo + 1
                                           and pair.get(text[lo]) == text[hi - 1]), None)
            elif re.fullmatch(r"[\[（(]?(?:인용|전언|발화|대화)\s*(?:끝|종료)[\]）)]?[.!]?", stripped):
                active, active_end = False, None
        if offset + len(line) > position:
            return active and (active_end is None or position < active_end)
        offset += len(line)
    return active


def _source_occurrences(fields, alias, title, boundaries):
    body = [(record["path"], record["text"]) for record in boundaries]
    body_text = "\n".join(text for _, text in body)
    offsets, quote_blocks, offset = {}, [], 0
    for record in boundaries:
        path, text = record["path"], record["text"]
        offsets[path] = offset
        if record["quoted"]:
            quote_blocks.append((offset, offset + len(text)))
        offset += len(text) + 1
    for path, text in fields:
        joined = text if path == "/title" else body_text
        if path != "/title" and path not in offsets:
            continue
        base = 0 if path == "/title" else offsets[path]
        ranges = _quoted_ranges(joined)
        if text.lstrip().startswith(">"):
            continue
        pattern = rf"(?<![{_WORD}]){re.escape(alias)}(?={_PARTICLE}(?![{_WORD}]))"
        spans = {match.span() for match in re.finditer(pattern, text)}
        declaration = _explicit_relation_span(text, alias, title)
        if declaration is not None:
            spans.add(declaration)
        for start, end in sorted(spans):
            if _external_speech_at(joined, base + start, quote_blocks=() if path == "/title" else quote_blocks):
                continue
            # 이름 자체의 따옴표만 허용한다. 여러 블록에 걸친 발화 인용은 제외한다.
            if any(a <= base + start < b and (a, b) != (base + start - 1, base + end + 1) for a, b in ranges):
                continue
            yield path, text, start, end


def _quoted_name(value):
    literal = re.escape(value)
    return "(?:" + "|".join([literal] + [re.escape(a) + literal + re.escape(b) for a, b in [('"','"'), ("'","'"), ('「','」'), ('『','』'), ('“','”'), ('‘','’')]]) + ")"


def _explicit_relation_span(text, alias, title):
    """완결된 작성자 명명문만 채택한다. 문장형 이름은 이름 인용 안에서 그대로 비교한다."""
    a, t = _quoted_name(alias), _quoted_name(title)
    ending = r"(?:이다|입니다|라고\s*부른다|으로\s*부른다)[.!]?"
    patterns = [
        rf"{t}의\s*(?:약칭|별칭|줄임말)(?:은|는)\s*{a}(?:{ending})",
        rf"{a}(?:은|는)\s*{t}의\s*(?:약칭|별칭|줄임말){ending}",
    ]
    for index, pattern in enumerate(patterns):
        if re.fullmatch(pattern, text.strip()):
            start = text.rfind(alias) if index == 0 else text.find(alias)
            return start, start + len(alias)
    return None


def _registry_match(alias, title, registries):
    titles = {_key(mapping[alias]) for mapping in registries if isinstance(mapping, Mapping) and alias in mapping}
    return titles == {_key(title)}


def _source_relation(fields, alias, title, registries, boundaries):
    for path, text, start, end in _source_occurrences(fields, alias, title, boundaries):
        explicit = _explicit_relation_span(text, alias, title) == (start, end)
        # 명명 관계를 부정/가정하는 문맥은 사전 항목의 존재만으로 뒤집지 않는다.
        denied = re.search(r"(?:약칭|별칭|줄임말).{0,30}(?:아니|않|가정|라면|다면)", text)
        if explicit:
            yield path, text, start, end, "author_alias_declaration"
        elif not denied and _registry_match(alias, title, registries):
            yield path, text, start, end, "curated_alias_relation"


def _external_document_key(row):
    """문서 신원만 비교한다. 소설 소개/명명 권한은 기존 판독기가 별도로 판단한다."""
    from urllib.parse import unquote, urlsplit
    from ..grounding.anticipation_search_probe import _compact_source_title
    if not isinstance(row, dict):
        return None
    url, raw_title = row.get("url"), row.get("title") or row.get("page_title")
    if not isinstance(url, str) or not isinstance(raw_title, str):
        return None
    try:
        parsed = urlsplit(url)
        path = unquote(parsed.path)
        if (parsed.scheme != "https" or parsed.hostname not in {"namu.wiki", "www.namu.wiki"}
            or parsed.username or parsed.password or parsed.port not in (None, 443) or not path.startswith("/w/")):
            return None
    except ValueError:
        return None
    url_title = path[3:].strip("/")
    source_title = re.sub(r"\s*[-–]\s*나무위키(?::대문)?\s*$", "", raw_title).strip()
    key = _compact_source_title(source_title)
    if "/" in url_title or not 6 <= len(key) <= 80 or _compact_source_title(url_title) != key:
        return None
    # 같은 문서의 fragment/기본 port/www 차이는 새 문서가 아니다. 질의는 합치지 않는다.
    return key, url_title, parsed.query


def _external_rows(rows):
    """검증 가능한 문서의 모든 반환 행을 보존한다. 소개 없는 반박도 버리지 않는다."""
    from ..grounding.anticipation_search_probe import (
        _source_bound_wiki_rows, source_bound_search_row_fingerprint,
    )
    if not isinstance(rows, list) or len(rows) > 120:
        return None
    eligible = {row["source_row_sha256"] for row in _source_bound_wiki_rows(rows)}
    documents = {_external_document_key(row) for row in rows
                 if source_bound_search_row_fingerprint(row) in eligible}
    documents.discard(None)
    out, seen, total = [], set(), 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("_ocr_diagnostic_only") is True or row.get("_purpose") == "image_ocr_diagnostic_probe":
            continue
        fingerprint = source_bound_search_row_fingerprint(row)
        if _external_document_key(row) not in documents or fingerprint in seen:
            continue
        provenance = " ".join(str(row.get(key) or "") for key in
            ("source", "origin", "provenance", "generated_source", "_source")).lower()
        if (any(str(row.get(key) or "").lower() in {"true", "1", "yes"} for key in
                ("is_generated", "generated", "from_ocr", "is_ocr", "model_generated"))
            or any(marker in provenance for marker in ("llm", "model", "generated", "ocr", "vlm", "summary"))):
            return None
        projected = {key: row[key] for key in _EXTERNAL_KEYS if isinstance(row.get(key), str)}
        if any(len(value) > (2048 if key == "url" else 500 if key in {"title", "page_title"} else 6000)
               for key, value in projected.items()):
            return None
        body = "\n".join(projected[key] for key in ("content", "snippet", "description") if key in projected)
        # 기존 검증기의 6000자 절단 뒤에 반박 문장이 숨지 않도록 절단 없이 보존한다.
        if len(body) > 6000:
            return None
        total += sum(len(value) for value in projected.values())
        if total > 24000 or len(out) >= 24:
            return None
        assert source_bound_search_row_fingerprint(projected) == fingerprint
        seen.add(fingerprint)
        out.append(projected)
    return out


def _direct_external_source_reference(text, start, end):
    """외부 선언도 원문의 타인 발화나 명명 관계 부정을 작성자 근거로 바꾸지 않는다."""
    left = max(text.rfind("\n", 0, start), text.rfind(".", 0, start)) + 1
    right = min((pos for sep in ("\n", ".") if (pos := text.find(sep, end)) >= 0), default=len(text))
    clause = text[left:right]
    if re.match(r"^\s*(?:>|인용\s*[:：]|댓글\s*[:：]|(?:친구|지인|누군가|다른\s*사람)(?:이|가|는|:|：))", clause):
        return False
    if re.search(r"(?:라고|다고|라며|다며)\s*(?:말|했|하더|전했|적었|썼)", clause):
        return False
    if re.search(r"(?:약칭|별칭|줄임말|작품명|소설명).{0,30}(?:아니|않|가정|라면|다면)", clause):
        return False
    return True


def _owned_external_assertion(row, assertion, alias, title):
    """기존 선언 판독을 통과한 같은 문장의 외부 인용 범위를 추가로 검산한다."""
    body = "\n".join(row[key] for key in ("content", "snippet", "description") if isinstance(row.get(key), str))
    quotes = _quoted_ranges(body)
    for match in re.finditer(r"([^.!?。！？\n\r]+)([.!?。！？]?)", body):
        sentence = match[1].strip() + match[2]
        if _sha(sentence) != assertion["assertion_sentence_sha256"]:
            continue
        start = match.start(1) + len(match[1]) - len(match[1].lstrip())
        end = match.end()
        if sentence.lstrip().startswith(">"):
            continue
        if _external_speech_at(body, start):
            continue
        if any(max(start, lo) < min(end, hi) and body[lo + 1:hi - 1].strip() not in {alias, title}
               for lo, hi in quotes):
            continue
        prefix = body[:start].rstrip()
        prior = prefix.rsplit("\n", 1)[-1] if prefix else ""
        if re.search(r"(?:인용|댓글|(?:말|전|썼|적었)(?:했다|한다|다))\s*[:：]?\s*$", prior):
            continue
        return True
    return False


def _external_assertion_evidence(rows, alias, title, source_text):
    """Verifier가 쓰는 동일 source-bound 판독기를 다시 실행한다. 요약/count는 근거가 아니다."""
    from ..grounding.anticipation_search_probe import (
        source_bound_alias_assertion, source_bound_search_row_fingerprint,
        _source_bound_sentence_parts, _compact_source_title,
    )
    projected = _external_rows(rows)
    if not projected:
        return None
    assertion = source_bound_alias_assertion(title, [alias], projected, source_text=source_text)
    if (not isinstance(assertion, dict) or set(assertion) != _ASSERTION_KEYS
        or assertion.get("alias_surface") != alias or _key(assertion.get("title")) != _key(title)
        or assertion.get("support_surface") != ""):
        return None
    # 같은 문서가 여러 검색 행으로 돌아온 경우 반박 행을 버리고 긍정 행만 고르지 않는다.
    # 관계를 만드는 판독은 위 원형 함수만 맡는다. 이 확인은 거부 방향으로만 작동한다.
    negative = re.compile(r"아니|않|잘못|오해|착각|거짓|오류|다른\s*(?:작품|소설|제목|문서)|별개\s*(?:작품|소설|제목|문서)|(?:후보|가칭|임시명|추정)")
    marker = re.compile(r"약칭|줄임말|통칭|별칭|약어")
    for row in projected:
        document = _external_document_key(row)
        if document is None or document[0] != _compact_source_title(title):
            continue
        body = "\n".join(row[key] for key in ("content", "snippet", "description") if isinstance(row.get(key), str))
        if any(negative.search(sentence) and (alias in sentence or marker.search(sentence))
               for sentence, _ in _source_bound_sentence_parts(body)):
            return None
    selected = [row for row in projected if source_bound_search_row_fingerprint(row) == assertion["source_row_sha256"]]
    if len(selected) != 1 or not _owned_external_assertion(selected[0], assertion, alias, title):
        return None
    return {"schema_version": "alias_external_assertion_witness_v2",
            "row_scope": "complete_bound_document_rows_within_bounded_search_input",
            "rows": projected, "rows_sha256": _corpus_sha(projected), "assertion": dict(assertion)}


def _normalize_external_evidence(value, alias, title):
    if not isinstance(value, Mapping) or set(value) != {"schema_version", "row_scope", "rows", "rows_sha256", "assertion"}:
        return None
    if value["schema_version"] != "alias_external_assertion_witness_v2" or value["row_scope"] != "complete_bound_document_rows_within_bounded_search_input":
        return None
    rows, assertion = value["rows"], value["assertion"]
    if (not isinstance(rows, list) or not 1 <= len(rows) <= 24 or not isinstance(assertion, dict)
        or set(assertion) != _ASSERTION_KEYS or any(not isinstance(v, str) or len(v) > 2048 for v in assertion.values())):
        return None
    if any(not isinstance(row, dict) or not set(row).issubset(_EXTERNAL_KEYS)
           or any(not isinstance(v, str) for v in row.values()) for row in rows):
        return None
    projected = _external_rows(rows)
    if projected != rows or value["rows_sha256"] != _corpus_sha(rows):
        return None
    # source_text/span는 소비 시 실제 원문으로 재검산한다. 여기서는 보존된 행의 선언만 검산한다.
    expected = _external_assertion_evidence(rows, alias, title, alias)
    if expected != value:
        return None
    return deepcopy(expected)


def build_alias_learning_terms(post, decoder, verification, *, registries, search_rows=None):
    """개별 검증과 원문 역할을 함께 만족한 순수 작품 별칭만 반환한다."""
    if not isinstance(decoder, Mapping) or not isinstance(verification, Mapping) or decoder.get("needs_verification") is not False:
        return []
    slang, relation, identity = (verification.get(k) for k in ("slang_insight", "relation_judgment", "novel_identity"))
    if not all(isinstance(v, Mapping) for v in (slang, relation, identity)):
        return []
    alias = slang.get("canonical_work_alias") or slang.get("detected_term")
    title = identity.get("official_novel_title") or identity.get("official_title")
    if not isinstance(alias, str) or not 1 <= len(alias) <= 160 or alias != alias.strip() or not isinstance(title, str) or not 1 <= len(title) <= 240 or title != title.strip():
        return []
    if (verification.get("is_relevant") is not True or slang.get("decode_verified") is not True
        or slang.get("alias_scope") not in {"pure_work_alias", "work_plus_character"}
        or _key(slang.get("decoded_term")) != _key(title)
        or relation.get("relation_type") not in {"explicit_alias", "title_alias", "work_alias"}
        or relation.get("discussion_target") != "specific_work"
        or relation.get("promotion_decision") not in {"allow", "promote", "publish"}
        or relation.get("generic_relation_only") is True or relation.get("qualified_topic_hold") is True):
        return []
    fields = _fields(post)
    boundaries = _boundary_fields(post)
    terms = decoder.get("decoded_terms")
    if not fields or not isinstance(terms, list):
        return []
    # 합성 표면의 신뢰도를 분리된 별칭에 재사용하지 않는다. 정확히 그 별칭을 검증해야 한다.
    matches = [term for term in terms if isinstance(term, Mapping) and term.get("original") == alias]
    if len(matches) != 1:
        return []
    term = matches[0]
    best = term.get("best_match")
    interpretations = term.get("interpretations")
    if (term.get("is_author_name") is True or not isinstance(best, Mapping)
        or _key(best.get("title")) != _key(title) or not isinstance(interpretations, list) or not interpretations
        or any(not isinstance(item, Mapping) or item.get("type") not in {"novel_title", "work_alias", "title_alias"}
               or _key(item.get("value")) != _key(title) for item in interpretations)):
        return []
    decoder_rank, verifier_rank = _rank(best.get("confidence")), _rank(relation.get("confidence"))
    confidence = min(decoder_rank, verifier_rank)
    if confidence < 2:
        return []
    observations = [(path, text, start, end, kind, None)
                    for path, text, start, end, kind in _source_relation(fields, alias, title, registries, boundaries)]
    if not observations and search_rows:
        for path, text, start, end in _source_occurrences(fields, alias, title, boundaries):
            if not _direct_external_source_reference(text, start, end):
                continue
            external = _external_assertion_evidence(search_rows, alias, title, text)
            if external:
                observations.append((path, text, start, end, "external_source_bound_alias_assertion", external))
    for path, text, start, end, kind, external in observations:
        proof = {"schema_version": SCHEMA, "post_id": post["post_id"], "source_path": path,
                 "source_span": [start, end], "source_text_sha256": _sha(text),
                 "source_corpus_sha256": _source_scope_sha(fields, boundaries), "relation_kind": kind,
                 "alias": alias, "title": title, "decoder_confidence": decoder_rank,
                 "verifier_confidence": verifier_rank, "alias_confidence": confidence}
        if external is not None:
            proof.update(schema_version=EXTERNAL_SCHEMA, external_evidence=external,
                         relation_type=relation["relation_type"], discussion_target="specific_work",
                         decode_verified=True, relation_decision=relation["promotion_decision"])
        return [{"original": alias, "source_role": "work_alias",
                 "best_match": {"title": title, "confidence": {2: "medium", 3: "high", 4: "max"}[confidence]},
                 "learning_evidence": proof}]
    return []


def normalize_alias_learning_evidence(value):
    if not isinstance(value, Mapping) or value.get("schema_version") not in {SCHEMA, EXTERNAL_SCHEMA}:
        return None
    keys = {"schema_version", "post_id", "source_path", "source_span", "source_text_sha256", "source_corpus_sha256", "relation_kind", "alias", "title", "decoder_confidence", "verifier_confidence", "alias_confidence"}
    external = value.get("schema_version") == EXTERNAL_SCHEMA
    if external:
        keys |= {"external_evidence", "relation_type", "discussion_target", "decode_verified", "relation_decision"}
    if set(value) != keys or type(value.get("post_id")) is not int:
        return None
    for key, limit in (("alias", 160), ("title", 240), ("source_path", 80)):
        if not isinstance(value[key], str) or not 1 <= len(value[key]) <= limit or value[key] != value[key].strip():
            return None
    if not re.fullmatch(r"/title|/content_blocks/\d+/text", value["source_path"]):
        return None
    if any(not isinstance(value[k], str) or not re.fullmatch(r"[0-9a-f]{64}", value[k]) for k in ("source_text_sha256", "source_corpus_sha256")):
        return None
    span = value["source_span"]
    if not isinstance(span, list) or len(span) != 2 or any(type(i) is not int for i in span) or not 0 <= span[0] < span[1] or span[1] - span[0] != len(value["alias"]):
        return None
    allowed = {"external_source_bound_alias_assertion"} if external else {"author_alias_declaration", "curated_alias_relation"}
    if value["relation_kind"] not in allowed:
        return None
    if any(type(value[k]) is not int or value[k] not in {2, 3, 4} for k in ("decoder_confidence", "verifier_confidence", "alias_confidence")):
        return None
    if value["alias_confidence"] != min(value["decoder_confidence"], value["verifier_confidence"]):
        return None
    normalized = {key: list(value[key]) if key == "source_span" else value[key] for key in sorted(keys)}
    if external:
        if (value["relation_type"] not in {"explicit_alias", "title_alias", "work_alias"}
            or value["discussion_target"] != "specific_work" or value["decode_verified"] is not True
            or value["relation_decision"] not in {"allow", "promote", "publish"}):
            return None
        witness = _normalize_external_evidence(value["external_evidence"], value["alias"], value["title"])
        if witness is None:
            return None
        normalized["external_evidence"] = witness
    return normalized


def eligible_alias_confidence(post, term, official_title, *, registries):
    """저장 후 소비 시 원문·개별 관계·공개 작품을 재검산한다. 레거시 추측은 승격하지 않는다."""
    if not isinstance(term, Mapping):
        return 0
    proof = normalize_alias_learning_evidence(term.get("learning_evidence"))
    best = term.get("best_match")
    if not proof or not isinstance(post, Mapping) or not isinstance(best, Mapping):
        return 0
    if (type(post.get("post_id")) is not int or proof["post_id"] != post["post_id"]
        or term.get("source_role") != "work_alias" or term.get("original") != proof["alias"]
        or best.get("title") != proof["title"] or _key(official_title) != _key(proof["title"])
        or _rank(best.get("confidence")) != proof["alias_confidence"]):
        return 0
    fields = _fields(post)
    boundaries = _boundary_fields(post)
    if _source_scope_sha(fields, boundaries) != proof["source_corpus_sha256"]:
        return 0
    if proof["schema_version"] == EXTERNAL_SCHEMA:
        for path, text, start, end in _source_occurrences(fields, proof["alias"], proof["title"], boundaries):
            if (path == proof["source_path"] and [start, end] == proof["source_span"]
                and _sha(text) == proof["source_text_sha256"]
                and _direct_external_source_reference(text, start, end)
                and _external_assertion_evidence(proof["external_evidence"]["rows"], proof["alias"], proof["title"], text) == proof["external_evidence"]):
                return proof["alias_confidence"]
        return 0
    for path, text, start, end, kind in _source_relation(fields, proof["alias"], proof["title"], registries, boundaries):
        if (path == proof["source_path"] and [start, end] == proof["source_span"]
            and _sha(text) == proof["source_text_sha256"] and kind == proof["relation_kind"]):
            return proof["alias_confidence"]
    return 0
