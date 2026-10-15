"""원문 인물과 작품 소유의 등장인물 문서를 Low 후보 관측으로만 연결한다."""
from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import unquote, urlsplit

from .candidate_alias_relation import _source
from ..domain.alias_learning import alias_source_from_context, _boundary_fields, _quoted_ranges
from ..domain.title_integrity import exact_title_integrity_match


CHARACTER_WORK_CANDIDATE_HOLD = "source_character_work_candidate_only"
_WORD = r"0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ_"


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _author_inputs(ctx):
    spans = _source(ctx)
    if spans is None:
        return []
    # lexical 필드만 같아도 원래 quote 블록 경계가 바뀌면 작성자 권한을 재사용하지 않는다.
    if getattr(ctx, "_batch_alias_original_source", None) is not None:
        if _boundary_fields(alias_source_from_context(ctx)) != _boundary_fields(ctx.post_data):
            return []
    author = [span for span in spans if span["source"] in {"author_title", "author_body"}]
    original = getattr(ctx, "_final_source_original_inputs", None)
    if original is not None:
        if not isinstance(original, (list, tuple)) or any(type(x) is not dict for x in original):
            return []
        captured = {(x.get("origin"), x.get("original_index")): x.get("raw_text")
            for x in original if x.get("caller_disposition") == "passed_to_source"
            and x.get("origin") in {"post_title", "body_line"}}
        live = {("post_title" if x["source"] == "author_title" else "body_line", x["position"]): x["text"]
            for x in author}
        if captured != live:
            return []
    return author


def _person_occurrences(spans, character, anchor, post):
    pattern = re.compile(r"(?<![" + _WORD + r"])" + re.escape(character)
        + r"(?=(?:께서|에게|에서|으로|은|는|이|가|을|를|의|도|만|와|과|에|로)?(?:$|[^" + _WORD + r"]))")
    # 기존 alias 원문 판독과 같은 선별 전 text/quote 순서를 사용한다.
    # 이미지/OCR의 따옴표는 열림/닫힘을 만들지 않고, 이미지가 원문 열린 인용을 닫지도 않는다.
    body = {int(re.search(r"/content_blocks/(\d+)/", item["path"])[1]): item
            for item in _boundary_fields(post)}
    for span in spans:
        if span["source"] == "author_body" and span["position"] not in body:
            body[span["position"]] = {"text": span["text"], "quoted": False}
    offsets, blocks, pieces, offset = {}, [], [], 0
    for position, item in sorted(body.items()):
        offsets[position] = offset
        text = item["text"]
        if item["quoted"]:
            blocks.append((offset, offset + len(text)))
        pieces.append(text)
        offset += len(text) + 1
    body_quotes = [*_quoted_ranges("\n".join(pieces)), *blocks]
    found = []
    for span in spans:
        raw = span["text"]
        base = 0 if span["source"] == "author_title" else offsets[span["position"]]
        quotes = _quoted_ranges(raw) if span["source"] == "author_title" else body_quotes
        for hit in pattern.finditer(raw):
            if any(lo <= base + hit.start() < hi for lo, hi in quotes):
                continue
            if not any(m.start() <= hit.start() and hit.end() <= m.end()
                       for m in re.finditer(re.escape(anchor), raw)):
                continue
            found.append({"source": span["source"], "original_index": span["position"],
                "raw_span": [hit.start(), hit.end()], "raw_text": raw})
    return found


def _wiki_owner(row):
    if (not isinstance(row, dict) or row.get("_ocr_diagnostic_only") is True
            or row.get("_purpose") == "image_ocr_diagnostic_probe"
            or row.get("purpose") == "image_ocr_diagnostic_probe"):
        return None
    if any(str(row.get(key) or "").lower() in {
            "webtoon", "comic", "manga", "anime", "game", "movie", "non_novel_media_platform"
            } for key in ("media_type", "page_type", "source_tier")):
        return None
    url, title = row.get("url"), row.get("title")
    if not isinstance(url, str) or not isinstance(title, str) or len(url) > 4096 or len(title) > 300:
        return None
    try:
        parsed = urlsplit(url)
        if (parsed.scheme not in {"http", "https"} or parsed.hostname != "namu.wiki"
                or parsed.username or parsed.password or parsed.port not in {None, 80, 443}
                or parsed.query or parsed.fragment):
            return None
    except ValueError:
        return None
    path = unquote(parsed.path)
    if not path.startswith("/w/") or not path.endswith("/등장인물"):
        return None
    owner = path[3:-len("/등장인물")]
    if not owner or "/" in owner or len(owner) > 160:
        return None
    headline = re.fullmatch(r"(.+?)/등장인물(?:\s+-\s+나무위키)?", title.strip())
    if not headline or not exact_title_integrity_match(owner, headline.group(1)):
        return None
    return owner


def _relation_contradicted(row, owner, character):
    """문서의 모든 저장 필드에서 같은 인물/소유 작품의 명시 반증을 먼저 읽는다."""
    person = r"(?<![" + _WORD + r"])" + re.escape(character)
    subject = person + r"(?:은|는|이|가)?\s*"
    work = r"(?:(?:이|그|해당|본)\s*(?:작품|소설)|[\"'「『]?" + re.escape(owner) + r"[\"'」』]?)"
    membership = subject + r"(?:" + work + r"(?:의)?\s*)?(?:등장인물|캐릭터|인물)"
    # 어간/관형절을 반증으로 자르지 않는다. 관계를 직접 단언한 완결 술어만 읽는다.
    # 의문문과 인용 속 술어는 문서의 독립 반증으로 승격하지 않는다.
    assertion_end = r"(?=[ \t]*(?:[.。!！]|\r?\n|$))"
    expressions = (
        membership + r"(?:이|은|는)?\s*(?:아니다|아닙니다|아니었다|아니었습니다|아님)",
        subject + r"(?:" + work + r"(?:에|에는)?\s*)?등장하지\s*(?:않는다|않습니다|않았다|않았습니다|않음)",
        subject + r"(?:" + work + r"(?:와|과|에)?\s*)?무관(?:하다|합니다|했다|했습니다|함)",
        subject + r"(?:다른|타|외부)\s*(?:작품|소설)의?\s*(?:등장인물|캐릭터|인물)"
            r"(?:이다|입니다|이었다|임)",
        membership + r"(?:이)?라는\s*(?:설명|기재|관계|정보)(?:은|는|를)?\s*"
            r"(?:(?:철회|취소)\s*(?:됐다|되었다|되었습니다|한다|했다|했습니다|함|됨)"
            r"|(?:잘못|오류)(?:이다|입니다|였다|였습니다|임))",
    )
    for field in ("content", "snippet", "description"):
        text = row.get(field)
        if not isinstance(text, str) or len(text) > 12000:
            continue
        quotes = _quoted_ranges(text)
        for pattern in expressions:
            for match in re.finditer(pattern + assertion_end, text):
                if not any(lo <= match.start() < hi for lo, hi in quotes):
                    return True
    return False


def _owned_character_text(row, owner, character):
    if _relation_contradicted(row, owner, character):
        return None
    # 제목과 snippet의 소유 작품명이 같고, 그 등장인물 목록이라는 서술 자체가 긍정문이어야 한다.
    heading = re.compile(r"^\s*(?:개요\s+)?(?:웹소설|소설)\s+[\"'「『]?"
        + re.escape(owner) + r"[\"'」』]?의\s+등장인물을\s+정리한\s+문서(?:이다|입니다)?\s*[.。]")
    person = re.compile(r"(?<![" + _WORD + r"])" + re.escape(character)
        + r"(?=(?:께서|에게|에서|으로|은|는|이|가|을|를|의|도|만|와|과|에|로)?(?:$|[^" + _WORD + r"]))")
    for field in ("content", "snippet", "description"):
        text = row.get(field)
        if not isinstance(text, str) or len(text) > 12000:
            continue
        start = heading.match(text)
        if not start:
            continue
        hits = list(person.finditer(text, start.end()))
        if not hits:
            continue
        # 다른 작품의 인물/관계 철회 문장에만 있는 이름을 이 문서의 소유 작품에 붙이지 않는다.
        usable = []
        for hit in hits:
            left = max(text.rfind(".", start.end(), hit.start()), text.rfind("\n", start.end(), hit.start()), start.end() - 1) + 1
            right_hits = [pos for mark in (".", "\n", "。") if (pos := text.find(mark, hit.end())) >= 0]
            clause = text[left:min(right_hits) if right_hits else len(text)]
            if (re.search(r"다른\s*작품|타\s*작품|외부\s*작품|단순\s*비교|언급만|잘못\s*기재|철회|취소", clause)
                    or re.search(r"(?:등장인물|캐릭터|인물)(?:이|은|는)?\s*(?:아니|아님|아닌)", clause)
                    or re.search(r"등장하지\s*않|무관하", clause)):
                continue
            usable.append([hit.start(), hit.end()])
        if usable:
            return {"field": field, "text": text, "header_span": [start.start(), start.end()],
                "character_spans": usable}
    return None


def character_work_candidates(ctx):
    """공식 권한/인명 별칭을 발급하지 않는 후보별 원자료 관측. 입력 객체를 바꾸지 않는다."""
    spans = _author_inputs(ctx)
    if not spans:
        return []
    outputs = getattr(ctx, "expert_outputs", None) or {}
    decoder = outputs.get("decoder") if isinstance(outputs, dict) else None
    if not isinstance(decoder, dict) or not isinstance(decoder.get("decoded_terms"), list):
        return []
    rows = getattr(ctx, "search_results", None) or []
    if not isinstance(rows, (list, tuple)) or len(rows) > 128:
        return []
    # 일반 검색 dedup은 percent encoding을 해제하지 않는다. 같은 Namu 문서의
    # 저장 표현만 묶고, 작품명 유사도나 다른 문서의 반증을 전역으로 합치지 않는다.
    document_rows, owned_rows = {}, []
    for row_index, row in enumerate(rows):
        owner = _wiki_owner(row)
        if not owner:
            continue
        document = unquote(urlsplit(row["url"]).path)  # _wiki_owner가 host/경로/역할을 먼저 검증했다.
        document_rows.setdefault(document, []).append(row)
        owned_rows.append((row_index, row, owner, document))
    observed = []
    for term_index, term in enumerate(decoder["decoded_terms"][:32]):
        if not isinstance(term, dict) or term.get("is_author_name") is not False:
            continue
        character = term.get("original")
        ground = term.get("grounding")
        if (not isinstance(character, str) or not 2 <= len(character) <= 24
                or not isinstance(ground, dict) or ground.get("is_grounded") is not True
                or ground.get("anchor_type") != "character_mention"):
            continue
        interpretations = term.get("interpretations") or []
        if not isinstance(interpretations, list) or any(isinstance(i, dict) and i.get("type") in
                {"novel_title", "work_title", "work_alias", "title_alias", "author_name"} for i in interpretations):
            continue
        if not any(isinstance(i, dict) and i.get("type") == "character_name"
                   and i.get("value") == character and i.get("context_fit") in {"high", "medium"}
                   for i in interpretations):
            continue
        anchor = ground.get("anchor_evidence")
        if not isinstance(anchor, str) or not anchor:
            continue
        occurrences = _person_occurrences(spans, character, anchor, ctx.post_data)
        if not occurrences:
            continue
        try:
            term_sha256 = _digest(term)
        except (TypeError, ValueError, OverflowError, RecursionError):
            continue  # strict digest 불가인 이 term만 보충 대상에서 제외한다.
        owners = []
        document_vetoes = {}
        for row_index, row, owner, document in owned_rows:
            if exact_title_integrity_match(owner, character):
                continue
            if document not in document_vetoes:
                document_vetoes[document] = any(_relation_contradicted(peer, owner, character)
                    for peer in document_rows[document])
            if document_vetoes[document]:
                continue
            text_proof = _owned_character_text(row, owner, character)
            if text_proof:
                try:
                    row_sha256 = _digest(row)
                except (TypeError, ValueError, OverflowError, RecursionError):
                    continue  # raw metadata를 지우거나 NaN을 허용하지 않는다.
                owners.append((row_index, row, owner, text_proof, row_sha256))
        owner_keys = {re.sub(r"\s+", "", owner).casefold() for _, _, owner, _, _ in owners}
        if len(owner_keys) != 1:
            continue  # 동명 인물/복수 작품 문서가 경쟁하면 이 fallback은 선택하지 않는다.
        candidates = term.get("candidates") or []
        if not isinstance(candidates, list):
            continue
        for row_index, row, owner, text_proof, row_sha256 in owners:
            for candidate in candidates:
                if not isinstance(candidate, dict) or candidate.get("url") != row["url"]:
                    continue
                title = candidate.get("official_novel_title")
                if not isinstance(title, str) or not exact_title_integrity_match(title, owner):
                    continue
                proof = {"schema_version": "source_character_work_candidate_v1", "title": title,
                    "character": character, "post_id": ctx.post_id, "term_index": term_index,
                    "source_occurrences": occurrences, "search_row_index": row_index,
                    "search_row_sha256": row_sha256, "decoder_term_sha256": term_sha256,
                    "evidence_url": row["url"], "evidence_id": row.get("eid"), "text_proof": text_proof,
                    "publication_authority": False, "alias_authority": False, "supports_publish": False}
                try:
                    proof["fingerprint"] = _digest(proof)
                except (TypeError, ValueError, OverflowError, RecursionError):
                    continue
                if not any(p["title"] == title for p in observed):
                    observed.append(proof)
    return observed[:8]
