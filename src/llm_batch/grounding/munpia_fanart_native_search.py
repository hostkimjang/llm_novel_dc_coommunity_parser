"""문피아 팬아트 목록에서 후보 게시물 URL만 제한적으로 발견한다.

목록 제목은 약어·작품 관계의 근거가 아니다. 상세 페이지와 작품 상세는 별도로
수집·검증해야 하며, 이 함수는 원본 HTML을 호출자에게 전달하지 않는다.
"""

from __future__ import annotations

import hashlib
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urlencode, urlsplit


_LIST_URL = 'https://www.munpia.com/communities/novels-fanart/posts'
_ALIAS = re.compile(r'[0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ_]{2,32}\Z')
_POST_PATH = re.compile(r'/communities/novels-fanart/posts/[1-9][0-9]*\Z')
_VOID_TAGS = frozenset({
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
    'meta', 'param', 'source', 'track', 'wbr',
})
_MAX_BYTES = 512_000
_MAX_RESULTS = 5
_TIMEOUT_SEC = 4.0


@dataclass(frozen=True)
class NativeListingResponse:
    status_code: int
    final_url: str
    body: bytes


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _fetch_listing(url: str, timeout_sec: float, max_bytes: int) -> NativeListingResponse:
    deadline = time.monotonic() + timeout_sec
    request = urllib.request.Request(
        url,
        headers={
            'Accept': 'text/html',
            'Accept-Language': 'ko-KR',
            'User-Agent': 'NovelMatchSourceDiscovery/1.0',
        },
    )
    with urllib.request.build_opener(_NoRedirect).open(request, timeout=timeout_sec) as response:
        length = response.headers.get('Content-Length')
        if length and int(length) > max_bytes:
            return NativeListingResponse(response.status, response.geturl(), b'')
        chunks: list[bytes] = []
        total = 0
        while total <= max_bytes:
            if time.monotonic() >= deadline:
                return NativeListingResponse(response.status, response.geturl(), b'')
            chunk = response.read1(min(16_384, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        if time.monotonic() >= deadline:
            return NativeListingResponse(response.status, response.geturl(), b'')
        return NativeListingResponse(
            response.status, response.geturl(), b''.join(chunks),
        )


def _post_url(value: str) -> str:
    try:
        parts = urlsplit(value)
        if (
            parts.scheme != 'https' or parts.hostname != 'www.munpia.com'
            or parts.username or parts.password or parts.port not in (None, 443)
            or parts.fragment or not _POST_PATH.fullmatch(parts.path)
        ):
            return ''
    except ValueError:
        return ''
    return 'https://www.munpia.com' + parts.path


class _ListingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.rows: list[tuple[str, str]] = []
        self._row: dict[str, str] | None = None
        self._row_depth = 0
        self._title_parts: list[str] | None = None
        self._title_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = set((values.get('class') or '').split())
        if tag == 'div' and 'article-list' in classes and self._row is None:
            self._row = {'href': '', 'title': ''}
            self._row_depth = len(self.stack) + 1
        elif self._row is not None:
            if tag == 'a' and 'article-meta' in classes:
                self._row['href'] = values.get('href') or ''
            if tag == 'div' and 'article-title' in classes and self._row['href']:
                self._title_parts = []
                self._title_depth = len(self.stack) + 1
        if tag not in _VOID_TAGS:
            self.stack.append(tag)

    def handle_data(self, data: str) -> None:
        if self._title_parts is not None:
            self._title_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack or self.stack[-1] != tag:
            return
        if self._title_parts is not None and len(self.stack) == self._title_depth:
            if self._row is not None:
                self._row['title'] = ' '.join(''.join(self._title_parts).split())
            self._title_parts = None
        if self._row is not None and len(self.stack) == self._row_depth:
            self.rows.append((self._row['href'], self._row['title']))
            self._row = None
        self.stack.pop()


def discover_munpia_fanart_post_candidates(
    alias: str,
    *,
    fetcher: Callable[[str, float, int], NativeListingResponse] | None = None,
) -> list[dict[str, str | int]]:
    """전체 기간 제목 검색의 첫 페이지에서 게시물 후보 최대 5건을 반환한다.

    ``fetcher(url, timeout_sec, max_bytes)``는 HTTP 테스트 주입점이다. 실패 또는
    형식 불일치 시 빈 목록을 반환한다. 반환되는 제목은 목록 표시값일 뿐이다.
    """
    if not isinstance(alias, str) or not _ALIAS.fullmatch(alias):
        return []
    request_url = _LIST_URL + '?' + urlencode({
        'dateRange': 'ALL_DAYS',
        'searchType': 'SUBJECT',
        'searchKeyword': alias,
    })
    try:
        result = (fetcher or _fetch_listing)(request_url, _TIMEOUT_SEC, _MAX_BYTES)
        if not isinstance(result, NativeListingResponse):
            return []
        if (
            not isinstance(result.status_code, int)
            or isinstance(result.status_code, bool)
            or not isinstance(result.final_url, str)
            or not isinstance(result.body, bytes)
        ):
            return []
        final = urlsplit(result.final_url)
        if (
            result.status_code < 200 or result.status_code >= 300
            or final.scheme != 'https' or final.hostname != 'www.munpia.com'
            or final.username or final.password or final.port not in (None, 443)
            or result.final_url != request_url
            or len(result.body) > _MAX_BYTES
        ):
            return []
        html = result.body.decode('utf-8')
        parser = _ListingParser()
        parser.feed(html)
        parser.close()
    except (OSError, ValueError, UnicodeError, urllib.error.URLError, TypeError, RuntimeError):
        return []
    digest = hashlib.sha256(result.body).hexdigest()
    candidates: list[dict[str, str | int]] = []
    seen: set[str] = set()
    for href, title in parser.rows:
        post_url = _post_url(href)
        if (
            not post_url or post_url in seen
            or not re.match(rf'^{re.escape(alias)}(?=$|[\s:：·,，(（\[【])', title)
            or '팬아트' not in title[len(alias):]
        ):
            continue
        seen.add(post_url)
        candidates.append({
            'alias': alias,
            'post_url': post_url,
            'post_title': title,
            'listing_request_url': request_url,
            'listing_final_url': result.final_url,
            'listing_status_code': result.status_code,
            'listing_body_sha256': digest,
            'evidence_type': 'munpia_fanart_native_listing_discovery_only',
        })
        if len(candidates) >= _MAX_RESULTS:
            break
    return candidates
