"""문피아 상세의 제목·명시 byline 결속. 작품 공개 권한을 만들지 않는다."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from html.parser import HTMLParser
import re
from urllib.parse import parse_qs, urljoin, urlsplit
from typing import Any, List

SCHEMA = "munpia_author_byline_v1"
MAX_SOURCE_BYTES = 262144
_MUNPIA_OFFICIAL_DETAIL_URL = re.compile(r"https://www\.munpia\.com/novel/detail/[0-9]+\Z")
IGNORED = {"script", "style", "template", "nav", "aside", "footer"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def is_legacy_munpia_author_detail(url):
    if not isinstance(url, str):
        return False
    try:
        value = urlsplit(url)
        return (value.scheme == "https" and value.netloc == "novel.munpia.com"
                and re.fullmatch(r"/[0-9]+/?", value.path) is not None
                and not value.query and not value.fragment)
    except ValueError:
        return False


def is_modern_munpia_author_detail(url):
    return isinstance(url, str) and _MUNPIA_OFFICIAL_DETAIL_URL.fullmatch(url) is not None


def is_munpia_author_detail(url):
    return is_legacy_munpia_author_detail(url) or is_modern_munpia_author_detail(url)


def _name(value):
    if not isinstance(value, str) or any(c in value for c in "\r\n<>|/;,="):
        return None
    value = re.sub(r"[\s\u00a0]+", " ", value).strip()
    return value if 2 <= len(value) <= 30 else None


def _labelled(value):
    # 조사 끝말을 금지하지 않는다. 안내 문장의 '작가' 뒤 단어도 채집하지 않는다.
    match = re.fullmatch(r"(?:글(?:\s*[:：]\s*|\s+)|(?:작가|저자)\s*[:：]\s*)(.+)", value.strip())
    return _name(match.group(1)) if match else None


class _HeaderParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = {"tag": "root", "children": [], "parent": None}
        self.stack = [self.root]
        self.headings = []

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "children": [], "parent": self.stack[-1]}
        self.stack[-1]["children"].append(node)
        if tag == "h1":
            self.headings.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        self.stack[-1]["children"].append(data)


def _text(node):
    if isinstance(node, str):
        return node
    if _hidden(node):
        return ""
    return " ".join(_text(child) for child in node["children"])


def _hidden(node):
    while node is not None:
        attrs = node.get("attrs", {})
        style = re.sub(r"\s+", "", str(attrs.get("style") or "")).lower()
        if (node["tag"] in IGNORED or "hidden" in attrs
                or str(attrs.get("aria-hidden") or "").strip().lower() == "true"
                or re.search(r"(?:^|;)(?:display:none|visibility:(?:hidden|collapse))(?:!important)?(?:;|$)", style)):
            return True
        node = node["parent"]
    return False


def _html_claims(source, title):
    parser = _HeaderParser()
    parser.feed(source)
    headings = [node for node in parser.headings if not _hidden(node)]
    if not headings:
        return []
    heading = headings[0]
    if " ".join(_text(heading).split()).casefold() != " ".join(title.split()).casefold():
        return []
    siblings = heading["parent"]["children"]
    # 객체 동일성으로 찾고, 순환 parent를 가진 dict 값 비교는 피한다.
    index = next(i for i, node in enumerate(siblings) if node is heading)
    claims = []
    seen = set()
    for node in siblings[index + 1:]:
        if isinstance(node, dict) and (node["tag"] in IGNORED or node["tag"] == "h1"):
            break
        value = " ".join(_text(node).split())
        if not value:
            continue
        name = _labelled(value)
        if name is None:
            break
        # 원문은 이미 256 KiB로 제한된다. 인접 구간을 끝까지 읽어 뒤쪽 충돌을 놓치지 않는다.
        if name.casefold() not in seen:
            claims.append(name)
            seen.add(name.casefold())
    return claims


def _rendered_claims(source, title):
    lines = [line.strip() for line in source.splitlines()]
    start = next((i for i, line in enumerate(lines) if re.match(r"^#\s+\S", line)), None)
    if start is None or re.sub(r"^#\s+", "", lines[start]).casefold() != title.strip().casefold():
        return []
    header = [line for line in lines[start + 1:start + 7] if line]
    if len(header) < 3 or header[0] != "글":
        return []
    name = _name(header[1])
    metadata = re.match(r"^(?:총\s*\d+\s*(?:화|권)|연재|조회수|좋아요|선호작|글자수|작품등록일)", header[2])
    return [name] if name and metadata else []


def _munpia_detail_author_from_page(
    html: str, url: str, title: str, *, return_claims: bool = False,
) -> Any:
    """첫 가시 작품 표제의 byline과 같은 문서의 구조화 메타만 읽는다."""
    if not _MUNPIA_OFFICIAL_DETAIL_URL.fullmatch(url) or not title:
        return None

    import html as html_mod

    def _plain(value: Any) -> str:
        return re.sub(r"\s+", " ", html_mod.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))).strip()

    def _same_title(value: Any) -> bool:
        return _plain(value).casefold() == title.casefold()

    def _valid_author(value: Any) -> str:
        name = _plain(value)
        if not 2 <= len(name) <= 30 or name in {"작가", "작가명", "원작", "글작가", "unknown"}:
            return ""
        return name

    def _walk(node):
        if isinstance(node, dict):
            yield node
            for child in node["children"]:
                yield from _walk(child)

    def _same_detail_link(href):
        try:
            return _work_url(urljoin(url, str(href))) == _work_url(url)
        except ValueError:
            return False

    def _foreign_work_link(href):
        try:
            target = urljoin(url, str(href))
            coordinate = _work_url(target)
            if str(coordinate).startswith("munpia:"):
                return coordinate != _work_url(url)
            parts = urlsplit(target)
            host = (parts.hostname or "").lower()
        except ValueError:
            return True
        if parts.scheme.lower() not in {"http", "https"}:
            return False
        # byline 링크의 역할만 판별한다. 요청/공개 URL의 strict 정규화는 바꾸지 않는다.
        if host in {"www.munpia.com", "novel.munpia.com"}:
            pattern = r"/novel/detail/([0-9]+)/?" if host == "www.munpia.com" else r"/([0-9]+)/?"
            work = re.fullmatch(pattern, parts.path)
            if work:
                return "munpia:" + work.group(1) != _work_url(url)
        # 알려진 공식 작품 경로만 저자 프로필과 구분한다. 외부 링크 전체를 막지 않는다.
        if host in {"novelpia.com", "www.novelpia.com", "book.novelpia.com"}:
            return re.fullmatch(r"/novel/[0-9]+/?", parts.path) is not None
        if host in {"series.naver.com", "m.series.naver.com"}:
            return (parts.path in {"/novel/detail.series", "/comic/detail.series", "/ebook/detail.series"}
                    and any(re.fullmatch(r"[0-9]+", value)
                            for value in parse_qs(parts.query).get("productNo", ())))
        if host in {"page.kakao.com", "kakao.page"}:
            return re.fullmatch(r"/(?:content/[0-9]+|home/[^/]+/[0-9]+)/?", parts.path) is not None
        if host in {"ridibooks.com", "www.ridibooks.com"}:
            return re.fullmatch(r"/books/[0-9]+/?", parts.path) is not None
        return False

    def _work_region(node):
        if _hidden(node):
            return False
        current = node
        while current is not None:
            if current["tag"] == "head":
                return False
            attrs = current.get("attrs", {})
            if current["tag"] == "a" and attrs.get("href") and not _same_detail_link(attrs["href"]):
                return False
            current = current["parent"]
        return True

    def _heading_links_bound(node):
        return all(_same_detail_link(item["attrs"]["href"])
                   for item in _walk(node)
                   if item["tag"] == "a" and item["attrs"].get("href") and _text(item).strip())

    parser = _HeaderParser()
    parser.feed(html)
    # HTMLParser가 보존한 실제 문서 head만 사용한다. template/본문 속 가짜 head는 제외한다.
    document_children = list(parser.root["children"])
    for node in parser.root["children"]:
        if isinstance(node, dict) and node["tag"] == "html":
            document_children.extend(node["children"])
    head = next((node for node in document_children if isinstance(node, dict)
                 and node["tag"] == "head" and not _hidden(node)), None)
    head_nodes = [node for node in head["children"] if isinstance(node, dict)
                  and not _hidden({**node, "tag": "meta"})] if head else []
    document_urls = []
    for node in head_nodes:
        attrs = node["attrs"]
        if node["tag"] == "meta" and str(attrs.get("property") or "").lower() == "og:url":
            document_urls.append(attrs.get("content") or "")
        if node["tag"] == "link" and "canonical" in str(attrs.get("rel") or "").lower().split():
            document_urls.append(attrs.get("href") or "")
    if document_urls and any(value != url for value in document_urls):
        return [] if return_claims else None
    page_url_matches = bool(document_urls)

    heading = next((node for node in parser.headings
                    if _work_region(node) and _heading_links_bound(node)), None)
    if heading is not None and not _same_title(_text(heading)):
        return [] if return_claims else None
    authors: List[str] = []
    if heading is not None:
        siblings = heading["parent"]["children"]
        start = next(index for index, node in enumerate(siblings) if node is heading)
        for node in siblings[start + 1:]:
            if isinstance(node, str):
                if node.strip():
                    break
                continue
            if node["tag"] in {"nav", "aside", "footer"}:
                break
            if _hidden(node):
                continue
            if node["tag"] == "h1":
                if authors and _work_region(node) and _heading_links_bound(node) and _same_title(_text(node)):
                    continue  # 같은 가시 header의 반복 표제·byline 충돌도 끝까지 읽는다.
                break
            # h2는 현대 상세의 인접 byline 형식이다. 본문/다른 카드로 범위를 넓히지 않는다.
            if node["tag"] != "h2" or not _work_region(node):
                break
            work_links = [item["attrs"]["href"] for item in _walk(node)
                          if item["tag"] == "a" and item["attrs"].get("href") and _text(item).strip()
                          and _foreign_work_link(item["attrs"]["href"])]
            if work_links:
                break
            author = _valid_author(_text(node))
            if not author:
                break
            authors.append(author)

    # JSON-LD는 실제 head 안에서 같은 이름과 정확한 URL을 가진 항목만 사용한다.
    for node in head_nodes:
        attrs = node["attrs"]
        if node["tag"] != "script" or str(attrs.get("type") or "").lower() != "application/ld+json":
            continue
        try:
            payload = json.loads("".join(child for child in node["children"] if isinstance(child, str)))
        except (TypeError, ValueError):
            continue
        nodes = payload if isinstance(payload, list) else [payload]
        for item in nodes:
            if not isinstance(item, dict):
                continue
            entries = item.get("@graph") if isinstance(item.get("@graph"), list) else [item]
            for entry in entries:
                if not isinstance(entry, dict) or not _same_title(entry.get("name")):
                    continue
                if entry.get("url") not in (None, "", url) or (not entry.get("url") and not page_url_matches):
                    continue
                byline = entry.get("author")
                for author_entry in (byline if isinstance(byline, list) else [byline]):
                    if isinstance(author_entry, dict):
                        author_entry = author_entry.get("name")
                    if isinstance(author_entry, str):
                        author = _valid_author(author_entry)
                        if author:
                            authors.append(author)

    head_title = next((_text(node) for node in head_nodes if node["tag"] == "title"), "")
    for suffix in (" - 문피아 웹소설", " - 문피아"):
        if head_title.endswith(suffix):
            head_title = head_title[:-len(suffix)].strip()
            break
    if page_url_matches and (heading is not None or _same_title(head_title)):
        for node in head_nodes:
            attrs = node["attrs"]
            if node["tag"] == "meta" and str(attrs.get("name") or "").lower() == "author":
                author = _valid_author(attrs.get("content"))
                if author:
                    authors.append(author)

    unique = {author.casefold(): author for author in authors}
    return list(unique.values()) if return_claims else next(iter(unique.values())) if len(unique) == 1 else None


def _modern_rendered_claims(source, title):
    # 첫 작품 표제 아래의 명시 byline 구간만 읽는다. 본문·추천 카드로 넘어가지 않는다.
    lines = [line.strip() for line in source.splitlines()]
    start = next((i for i, line in enumerate(lines) if re.match(r"^#\s+\S", line)), None)
    if start is None or re.sub(r"^#\s+", "", lines[start]).casefold() != title.strip().casefold():
        return []
    header = [line for line in lines[start + 1:] if line]
    claims = []
    metadata_seen = False
    index = 0
    while index < len(header):
        value = header[index]
        if value == "글":
            if index + 1 >= len(header):
                return []
            name = _name(header[index + 1])
            if name is None:
                return []
            index += 2
        else:
            name = _labelled(value)
            index += 1
        if name is not None:
            claims.append(name)
            continue
        if claims and re.match(r"^(?:총\s*\d+\s*(?:화|권)|연재|조회수|좋아요|선호작|글자수|작품등록일|최근연재일|ISBN|완결(?:$|\s))", value):
            metadata_seen = True
            continue
        break
    return claims if metadata_seen else []


def byline_evidence(url, title, source, *, kind):
    """반환값은 명시 저자 위치의 재검산 자료다. 전송/공개 승인을 대신하지 않는다."""
    if (not is_munpia_author_detail(url) or not isinstance(title, str) or not title.strip()
            or not isinstance(source, str) or len(source.encode("utf-8")) > MAX_SOURCE_BYTES
            or kind not in {"html", "rendered_text"}):
        return None
    if is_modern_munpia_author_detail(url):
        claims = (_munpia_detail_author_from_page(source, url, title, return_claims=True)
                  if kind == "html" else _modern_rendered_claims(source, title))
    else:
        claims = (_html_claims if kind == "html" else _rendered_claims)(source, title)
    unique = {name.casefold(): name for name in claims}
    return {"schema_version": SCHEMA, "url": url, "title": title, "source_kind": kind,
            "source_text": source, "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "status": "VERIFIED" if len(unique) == 1 else "CONFLICT" if unique else "NO_EXPLICIT_BYLINE",
            "name": next(iter(unique.values())) if len(unique) == 1 else None,
            "publication_authority": False}


def valid_byline_evidence(proof):
    if not isinstance(proof, dict) or proof.get("schema_version") != SCHEMA:
        return False
    reproduced = byline_evidence(proof.get("url"), proof.get("title"), proof.get("source_text"), kind=proof.get("source_kind"))
    return reproduced is not None and reproduced == proof


def qualify_munpia_fetch(url, result):
    """캐시를 수정하지 않고 이번 소비용 복사본의 제목·저자 근거를 재검산한다."""
    if not is_munpia_author_detail(url) or not isinstance(result, dict):
        return result
    copied = deepcopy(result)
    structured = copied.get("structured_info")
    if not isinstance(structured, dict):
        return copied
    original_author = structured.get("author")
    title = structured.get("title")
    accepted = []
    previous = structured.get("author_byline")
    compatible = (result.get("url") == url and result.get("final_url", url) == url
                  and structured.get("content_status") not in {"deleted", "unavailable"}
                  and (not is_modern_munpia_author_detail(url)
                       or structured.get("page_type") == "novel_page"))
    invalid_previous = previous is not None and (
        not valid_byline_evidence(previous) or previous.get("url") != url or previous.get("title") != title)
    if compatible:
        if (valid_byline_evidence(previous) and previous["url"] == url and previous["title"] == title
                and previous["status"] != "NO_EXPLICIT_BYLINE"):
            accepted.append(previous)
        text_proof = byline_evidence(url, title, result.get("text"), kind="rendered_text")
        if text_proof is not None and text_proof["status"] != "NO_EXPLICIT_BYLINE":
            accepted.append(text_proof)
    names = {p["name"].casefold(): p["name"] for p in accepted if p["status"] == "VERIFIED"}
    conflict = any(p["status"] == "CONFLICT" for p in accepted) or len(names) > 1
    structured.pop("author", None)
    structured.pop("author_byline", None)
    if len(names) == 1 and not conflict and not invalid_previous:
        structured["author"] = next(iter(names.values()))
        structured["author_byline"] = next(p for p in accepted if p["status"] == "VERIFIED")
    structured["author_byline_observation"] = {
        "status": "INVALID" if invalid_previous else "VERIFIED" if structured.get("author_byline") else "CONFLICT" if conflict else "UNBOUND",
        "url": url, "title": title, "evidence": accepted,
        "original_author": original_author, "publication_authority": False,
    }
    return copied


def qualify_legacy_munpia_fetch(url, result):
    """기존 구형 URL 전용 호출 계약을 유지한다."""
    return qualify_munpia_fetch(url, result) if is_legacy_munpia_author_detail(url) else result


def compact_byline(proof):
    """모델 입력에는 재검산 원문 대신 제한된 위치·지문만 전달한다."""
    if not isinstance(proof, dict):
        return None
    return {key: proof.get(key) for key in (
        "schema_version", "url", "title", "source_kind", "source_sha256",
        "status", "name", "publication_authority")}


def model_facing_author_metadata(structured):
    copied = deepcopy(structured)
    if isinstance(copied, dict):
        if "author_byline" in copied:
            copied["author_byline"] = compact_byline(copied["author_byline"])
        observation = copied.get("author_byline_observation")
        if isinstance(observation, dict):
            copied["author_byline_observation"] = {
                key: observation.get(key) for key in ("status", "url", "title", "publication_authority")}
    return copied


def _work_url(url):
    # 같은 문피아 숫자 작품의 구형/현대 상세 표현만 연결한다. 공개 권한은 아니다.
    if is_legacy_munpia_author_detail(url):
        return "munpia:" + urlsplit(url).path.strip("/")
    if isinstance(url, str):
        try:
            parsed = urlsplit(url)
            match = re.fullmatch(r"/novel/detail/([0-9]+)/?", parsed.path)
            if (parsed.scheme == "https" and parsed.netloc == "www.munpia.com"
                    and match and not parsed.query and not parsed.fragment):
                return "munpia:" + match.group(1)
        except ValueError:
            pass
    return url if isinstance(url, str) else None


def _same_work(title, url, selected):
    return bool(isinstance(selected, dict) and isinstance(title, str) and title.strip()
                and isinstance(selected.get("official_title"), str)
                and " ".join(title.split()).casefold() == " ".join(selected["official_title"].split()).casefold()
                and url and selected.get("heretic_url") and _work_url(url) == _work_url(selected["heretic_url"]))


def select_author_evidence(author_hints, *, observations=(), selected=None):
    """동일 작품의 충돌을 끝까지 보존하며 다른 책·판본의 저자를 옮기지 않는다."""
    hints = author_hints if isinstance(author_hints, list) else []
    records = []
    for observation in observations or ():
        if not isinstance(observation, dict):
            continue
        proofs = observation.get("evidence") or []
        valid = (observation.get("status") == "VERIFIED" and bool(proofs)
                 and all(valid_byline_evidence(p) and p["status"] == "VERIFIED"
                         and p["url"] == observation.get("url") and p["title"] == observation.get("title")
                         for p in proofs)
                 and len({p["name"].casefold() for p in proofs}) == 1)
        records.append((observation.get("title"), observation.get("url"), proofs[0] if valid else None))
    for hint in hints:
        if not isinstance(hint, dict) or "author_byline" not in hint:
            continue
        proof = hint["author_byline"]
        if isinstance(proof, dict) and "source_text" not in proof:
            full = next((p for _, _, p in records if p is not None and compact_byline(p) == proof), None)
        else:
            full = proof
        valid = (hint.get("source") == "url_fetch" and valid_byline_evidence(full)
                 and full["status"] == "VERIFIED" and hint.get("name") == full["name"]
                 and hint.get("url") == full["url"])
        records.append((proof.get("title") if isinstance(proof, dict) else None,
                        hint.get("url"), full if valid else None))
        if not valid and isinstance(proof, dict) and proof.get("url") != hint.get("url"):
            records.append((proof.get("title"), proof.get("url"), None))
    if records:
        related = [r for r in records if selected is None or _same_work(r[0], r[1], selected)]
        # URL가 같은데 제목이 달라진 관측도 무관 자료로 버리지 않는다.
        if selected is not None:
            related += [r for r in records if r not in related and r[1]
                        and _work_url(r[1]) == _work_url(selected.get("heretic_url"))]
        valid = [p for _, _, p in related if p is not None
                 and (selected is None or _same_work(p["title"], p["url"], selected))]
        if related and len(valid) == len(related):
            pairs = {(p["title"], _work_url(p["url"]), p["name"]) for p in valid}
            if len(pairs) == 1:
                proof = valid[0]
                return proof["name"], {"schema_version": "munpia_author_work_binding_v1",
                    "name": proof["name"], "title": proof["title"], "url": proof["url"],
                    "source_sha256": proof["source_sha256"]}
        # 범위가 알려진 다른 플랫폼의 정상 힌트는 무관 문피아 관측에 막히지 않는다.
        if related or selected is None:
            return None, None
        hints = [h for h in hints if isinstance(h, dict) and "author_byline" not in h
                 and not is_legacy_munpia_author_detail(h.get("url"))
                 and _same_work(h.get("title") or h.get("work"), h.get("url"), selected)]
    for hint in hints:
        if isinstance(hint, dict) and hint.get("name") and hint.get("source") in (
                "url_fetch", "url_fetch_platform", "llm_snippet", "llm_term_role", "author_bridge"):
            return hint["name"], None
    return None, None


def select_author_hint(author_hints, *, observations=(), selected=None):
    return select_author_evidence(author_hints, observations=observations, selected=selected)[0]


def normalize_author_work_binding(value):
    if not isinstance(value, dict) or value.get("schema_version") != "munpia_author_work_binding_v1":
        return None
    limits = {"name": 30, "title": 240, "url": 256, "source_sha256": 64}
    if any(not isinstance(value.get(k), str) or not 0 < len(value[k]) <= n for k, n in limits.items()):
        return None
    if not is_munpia_author_detail(value["url"]) or not re.fullmatch(r"[0-9a-f]{64}", value["source_sha256"]):
        return None
    return {"schema_version": value["schema_version"], **{key: value[key] for key in limits}}


def author_for_identity(envelope, identity):
    author = envelope.get("identified_author") if isinstance(envelope, dict) else None
    if not isinstance(envelope, dict) or "identified_author_work" not in envelope:
        return author  # 기존 다른 출처의 envelope 계약은 유지한다.
    binding = normalize_author_work_binding(envelope["identified_author_work"])
    selected = identity.get("novel_identity") if isinstance(identity, dict) else None
    if binding and binding["name"] == author and _same_work(binding["title"], binding["url"], selected):
        return author
    return None
