"""카카오 URL의 경로 역할만 판별한다. 작품·매체 일치나 URL 변환은 수행하지 않는다."""
from __future__ import annotations

import re
from typing import NamedTuple
from urllib.parse import parse_qsl, unquote, urlsplit


class KakaoRoute(NamedTuple):
    role: str
    content_id: str
    episode_id: str = ""


def parse_kakao_route(url: str, *, non_detail_tabs: set[str] | None = None) -> KakaoRoute | None:
    if not isinstance(url, str) or not url or any(ch.isspace() for ch in url):
        return None
    try:
        parts = urlsplit(url)
        if parts.scheme.lower() not in {"http", "https"}:
            return None
        if (parts.hostname or "").lower() not in {"page.kakao.com", "kakao.page"}:
            return None
        if parts.username is not None or parts.password is not None or parts.fragment:
            return None
        if parts.port not in {None, 80 if parts.scheme.lower() == "http" else 443}:
            return None
    except ValueError:
        return None
    path = parts.path
    if re.search(r"%(?![0-9A-Fa-f]{2})", path):
        return None
    root = re.fullmatch(r"/content/([0-9]+)/?", path)
    home = re.fullmatch(r"/home/([^/]+)/([0-9]+)/?", path)
    viewer = re.fullmatch(r"/content/([0-9]+)/viewer/([0-9]+)/?", path)
    if root:
        route = KakaoRoute("work_detail_root", root.group(1))
    elif home:
        slug = unquote(home.group(1))
        if not slug.strip() or slug in {".", ".."} or any(c in slug for c in "/\\\x00"):
            return None
        route = KakaoRoute("work_home", home.group(2))
    elif viewer:
        return KakaoRoute("episode_viewer", viewer.group(1), viewer.group(2))
    else:
        return None
    tabs = non_detail_tabs if non_detail_tabs is not None else {"comment", "comments", "notice", "notices"}
    tab_values = [value.lower() for key, value in parse_qsl(parts.query, keep_blank_values=True)
                  if key.lower() == "tab_type"]
    if len(tab_values) > 1:
        return None
    if tab_values and tab_values[0] in tabs:
        return KakaoRoute("non_detail_tab", route.content_id)
    return route


def is_kakao_work_detail_url(url: str) -> bool:
    route = parse_kakao_route(url)
    return route is not None and route.role in {"work_detail_root", "work_home"}
