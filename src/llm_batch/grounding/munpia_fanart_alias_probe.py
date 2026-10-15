"""문피아 팬아트 상세 페이지의 제목과 연결된 작품 카드를 한 출처에 묶는다.

이 함수는 이미 신뢰 경로로 수집한 상세 HTML 한 행만 판독한다. 검색 요약,
다른 페이지의 작품 카드, 모델 추론은 약어 관계의 빈칸을 채울 수 없다.
"""

from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit

from ..domain.title_integrity import exact_title_integrity_match
from .anticipation_search_probe import source_bound_search_row_fingerprint


_VOID_TAGS = frozenset({
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
    'meta', 'param', 'source', 'track', 'wbr',
})
_ALIAS_TOKEN = re.compile(r'[0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ_]{2,32}\Z')


def _munpia_url(value: Any, *, fanart: bool) -> str:
    if not isinstance(value, str):
        return ''
    try:
        parts = urlsplit(value)
        if (
            parts.scheme != 'https'
            or parts.hostname != 'www.munpia.com'
            or parts.username or parts.password
            or parts.port not in (None, 443)
            or parts.query or parts.fragment
        ):
            return ''
    except ValueError:
        return ''
    pattern = (
        r'/communities/novels-fanart/posts/[1-9][0-9]*'
        if fanart else r'/novel/detail/[1-9][0-9]*'
    )
    if not re.fullmatch(pattern, parts.path):
        return ''
    return f'https://www.munpia.com{parts.path}'


def _clean(value: str) -> str:
    return re.sub(r'\s+', ' ', value).strip()


class _FanartDetailParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, set[str]]] = []
        self.canonical: list[str] = []
        self.og_urls: list[str] = []
        self.article_titles: list[str] = []
        self.cards: list[dict[str, Any]] = []
        self._article_parts: list[str] | None = None
        self._card: dict[str, Any] | None = None
        self._card_parts: list[str] | None = None
        self._author_parts: list[str] | None = None

    def _within(self, name: str) -> bool:
        return any(name in classes for _, classes in self.stack)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = set((values.get('class') or '').split())
        if tag == 'link' and 'canonical' in (values.get('rel') or '').split():
            self.canonical.append(values.get('href') or '')
        if tag == 'meta' and values.get('property') == 'og:url':
            self.og_urls.append(values.get('content') or '')
        if tag == 'div' and 'article-title' in classes and self._within('view-title'):
            self._article_parts = []
        if (
            tag == 'a' and 'review-novel' in classes
            and self._within('view-article-wrap')
        ):
            self._card = {'url': values.get('href') or '', 'title': '', 'author': ''}
        if self._card is not None and tag == 'div':
            if 'novel-title' in classes:
                self._card_parts = []
            if 'novel-author' in classes:
                self._author_parts = []
        if tag not in _VOID_TAGS:
            self.stack.append((tag, classes))

    def handle_data(self, data: str) -> None:
        if self._article_parts is not None:
            self._article_parts.append(data)
        if self._card_parts is not None:
            self._card_parts.append(data)
        if self._author_parts is not None:
            self._author_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack or self.stack[-1][0] != tag:
            return
        _, classes = self.stack.pop()
        if tag == 'div' and 'article-title' in classes and self._article_parts is not None:
            self.article_titles.append(_clean(''.join(self._article_parts)))
            self._article_parts = None
        if tag == 'div' and 'novel-title' in classes and self._card_parts is not None:
            if self._card is not None:
                self._card['title'] = _clean(''.join(self._card_parts))
            self._card_parts = None
        if tag == 'div' and 'novel-author' in classes and self._author_parts is not None:
            if self._card is not None:
                self._card['author'] = _clean(''.join(self._author_parts))
            self._author_parts = None
        if tag == 'a' and 'review-novel' in classes and self._card is not None:
            self.cards.append(self._card)
            self._card = None


def source_bound_munpia_fanart_alias_assertion(
    title: str,
    alias_terms: list[str],
    official_detail_url: str,
    row: dict[str, Any],
) -> dict[str, str] | None:
    """상세 글 제목의 약어와 같은 글의 연결된 작품 카드만 결합한다.

    ``row['content']``는 신뢰된 수집기가 해당 ``row['url']``에서 받은 원본
    HTML이어야 한다. 반환값은 후보 증거이며, 독립 검증 없이 게시 승인하지 않는다.
    """
    if (
        not isinstance(title, str) or not isinstance(alias_terms, list)
        or not isinstance(official_detail_url, str) or not isinstance(row, dict)
    ):
        return None
    source_url = _munpia_url(row.get('url'), fanart=True)
    card_url = _munpia_url(official_detail_url, fanart=False)
    raw_html = row.get('content')
    raw_title = row.get('title')
    if (
        not source_url or not card_url or not isinstance(raw_html, str)
        or not 100 <= len(raw_html) <= 2_000_000
        or not isinstance(raw_title, str) or not raw_title.strip()
    ):
        return None
    parser = _FanartDetailParser()
    parser.feed(raw_html)
    parser.close()
    if (
        parser.canonical != [source_url]
        or parser.og_urls != [source_url]
        or len(parser.article_titles) != 1
        or len(parser.cards) != 1
    ):
        return None
    article_title = parser.article_titles[0]
    card = parser.cards[0]
    if (
        _clean(raw_title) != article_title
        or _munpia_url(card['url'], fanart=False) != card_url
        or not exact_title_integrity_match(title, card['title'])
        or not card['author']
    ):
        return None
    matches: list[str] = []
    for value in alias_terms:
        alias = value.strip() if isinstance(value, str) else ''
        if not _ALIAS_TOKEN.fullmatch(alias) or alias in matches:
            continue
        if re.match(rf'^{re.escape(alias)}(?=$|[\s:：·,，(（\[【])', article_title):
            matches.append(alias)
    if len(matches) != 1:
        return None
    alias = matches[0]
    suffix = article_title[len(alias):].lstrip()
    if re.search(r'(?:아니|않|말고|잘못|오해|착각|다른\s*(?:작품|소설))', suffix[:40]):
        return None
    row_sha256 = source_bound_search_row_fingerprint(row)
    if not row_sha256:
        return None
    return {
        'alias': alias,
        'title': card['title'],
        'author': card['author'],
        'source_url': source_url,
        'official_detail_url': card_url,
        'source_row_sha256': row_sha256,
        'source_html_sha256': hashlib.sha256(raw_html.encode('utf-8')).hexdigest(),
        'evidence_type': 'munpia_fanart_title_linked_novel_card',
    }
