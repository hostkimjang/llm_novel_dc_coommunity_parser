from __future__ import annotations

import os
import re
import time
import hashlib
import json
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import random
import base64

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sys

# ── UA 로테이션: 업스트림 차단 회피를 위해 실제 브라우저 UA를 순환 사용 ──
_BROWSER_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
]


def _random_browser_ua() -> str:
    return random.choice(_BROWSER_USER_AGENTS)


# ── 비한국어 노이즈 도메인 블랙리스트 ──
_NOISE_DOMAIN_BLACKLIST = {
    # 중국 포털/커뮤니티
    "zhihu.com", "www.zhihu.com", "zhuanlan.zhihu.com",
    "baidu.com", "www.baidu.com", "tieba.baidu.com", "baike.baidu.com", "zhidao.baidu.com",
    "bilibili.com", "www.bilibili.com",
    "douban.com", "www.douban.com",
    "weibo.com", "www.weibo.com",
    "sohu.com", "www.sohu.com",
    "sina.com.cn", "www.sina.com.cn",
    "163.com", "www.163.com",
    "qq.com", "www.qq.com",
    "csdn.net", "blog.csdn.net",
    "jianshu.com", "www.jianshu.com",
    "sogou.com", "www.sogou.com",
    "360.cn", "www.360.cn",
    "ifeng.com", "www.ifeng.com",
    "toutiao.com", "www.toutiao.com",
    "xiaohongshu.com", "www.xiaohongshu.com",
    "taobao.com", "www.taobao.com",
    "jd.com", "www.jd.com",
    "alipay.com", "www.alipay.com",
    "cnblogs.com", "www.cnblogs.com",
    "51cto.com", "www.51cto.com",
    "ithome.com", "www.ithome.com",
    # 인도 도메인
    "epfindia.gov.in",
}

# 블랙리스트 TLD 패턴 (중국 .cn, 인도 .in 정부 사이트 등)
_NOISE_TLD_PATTERNS = {".gov.in", ".gov.cn", ".edu.cn", ".ac.cn"}


def _is_blacklisted_host(hostname: str) -> bool:
    """도메인 블랙리스트 및 TLD 패턴 검사"""
    if hostname in _NOISE_DOMAIN_BLACKLIST:
        return True
    # 서브도메인도 검사 (예: xxx.zhihu.com)
    for bd in _NOISE_DOMAIN_BLACKLIST:
        if hostname.endswith("." + bd):
            return True
    # TLD 패턴 검사
    for tld in _NOISE_TLD_PATTERNS:
        if hostname.endswith(tld):
            return True
    return False


class SearchRequest(BaseModel):
    query: str
    num_results: int = 10  # 기본값: 10개 결과
    purpose: str = ""
    run_id: Optional[str] = None
    post_id: Optional[str] = None
    source_receipt: Optional[Dict[str, Any]] = None


class FetchRequest(BaseModel):
    url: str
    max_length: int = 0  # 0 = 무제한 (제한 없음)


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name, "1" if default else "0").strip().lower()
    return val in {"1", "true", "yes", "on"}


app = FastAPI(title="SearchXNG MCP Bridge")
SEARCHXNG_URL = os.getenv("SEARCHXNG_URL", "http://searchxng:8080")
CRAWL4AI_URL = os.getenv("CRAWL4AI_URL", "http://crawl4ai:11235")
DEFAULT_NUM_RESULTS = int(os.getenv("MCP_DEFAULT_NUM_RESULTS", "10"))
HEADLESS_SEARCH_ENABLED = _env_bool("HEADLESS_SEARCH_ENABLED", True)
HEADLESS_SEARCH_URL = os.getenv("HEADLESS_SEARCH_URL", "http://browser-search:8765/search").strip()
HEADLESS_COOLDOWN_SEC = 900
_HEADLESS_BACKOFF_UNTIL = 0.0
_RETRYABLE_SEARCH_STATUS = {403, 429, 500, 502, 503, 504}
_BLOCKED_ENGINES = {
    "yahoo",
    "yahoo_news",
    "wikidata",
    "wikipedia",
}
_DIRECTORY_ONLY_HOSTS = {
    "searx.space",
    "www.searx.space",
}
_ENDPOINT_BACKOFF_UNTIL: Dict[str, float] = {}
_DISCOVERY_CACHE: Dict[str, Any] = {"at": 0.0, "urls": []}

# 공개 인스턴스 발견 실패 시 사용할 하드코딩 폴백 인스턴스 목록
# - searx.space 접근 불가 시에도 최소한의 외부 인스턴스 사용 가능
# - 주기적으로 업데이트 필요 (searx.space에서 상위 안정 인스턴스 선별)
_HARDCODED_FALLBACK_INSTANCES: List[str] = [
    "https://search.im-in.space",
    "https://searxng.site",
    "https://search.mdosch.de",
    "https://searxng.website",
    "https://www.gruble.de",
]

# URL 페칭 허용 도메인 (웹소설 관련 공식/커뮤니티 + 주요 검색 결과 소스)
_ALLOWED_FETCH_DOMAINS = {
    # 위키/나무위키
    "namu.wiki", "ko.wikipedia.org",
    # 웹소설 공식 플랫폼
    "novelpia.com", "www.novelpia.com",
    "book.novelpia.com",
    "munpia.com", "mm.munpia.com", "m.munpia.com", "novel.munpia.com", "square.munpia.com",
    "series.naver.com", "m.series.naver.com",
    "ridibooks.com", "www.ridibooks.com",
    "kakaopage.com", "page.kakao.com",
    "joara.com", "www.joara.com",
    # 커뮤니티
    "arca.live",
    "gall.dcinside.com", "m.dcinside.com",
    "m.fmkorea.com", "www.fmkorea.com",
    "m.ruliweb.com", "www.ruliweb.com",
    "teamblind.com", "www.teamblind.com",
    # 블로그/리뷰
    "blog.naver.com", "m.blog.naver.com",
    "tistory.com",  # *.tistory.com 매칭용은 endswith 로직에서 처리
    "brunch.co.kr",
}

_OFFICIAL_PLATFORM_DOMAINS = {
    "novelpia.com", "www.novelpia.com",
    "book.novelpia.com",
    "munpia.com", "mm.munpia.com", "m.munpia.com", "novel.munpia.com", "square.munpia.com",
    "series.naver.com", "m.series.naver.com",
    "ridibooks.com", "www.ridibooks.com",
    "kakaopage.com", "page.kakao.com",
    "joara.com", "www.joara.com",
}

_COMMUNITY_DOMAINS = {
    "arca.live",
    "gall.dcinside.com", "m.dcinside.com",
    "m.fmkorea.com", "www.fmkorea.com",
    "m.ruliweb.com", "www.ruliweb.com",
    "teamblind.com", "www.teamblind.com",
}

_REFERENCE_DOMAINS = {
    "namu.wiki", "ko.wikipedia.org", "thewiki.kr",
    "blog.naver.com", "m.blog.naver.com", "brunch.co.kr",
}

_DIRECT_OFFICIAL_DETAIL_URL_RE = re.compile(
    r"(?i)"
    r"(?:novelpia\.com/novel/\d+|book\.novelpia\.com/novel/\d+|"
    r"(?:m\.)?novel\.munpia\.com/\d+|m\.munpia\.com/novel/detail/\d+|"
    r"(?:m|mm)\.munpia\.com/\?menu=novel&id=\d+|"
    r"page\.kakao\.com/content/\d+|"
    r"series\.naver\.com/novel/detail\.series\?productNo=\d+|"
    r"ridibooks\.com/books/\d+)"
)

_DIRECT_NON_DETAIL_URL_RE = re.compile(
    r"(?i)/(?:viewer|episode|search|ranking|rank|author|fanart|community|review|board|forum|arena|freeboard)(?:/|$)|"
    r"detailSearch|keyword=|tab_type=comment"
)

_QUERY_GENERIC_HANGUL_TOKENS = {
    "검색", "정식", "제목", "작품", "작품명", "작가", "추천", "리뷰", "후기",
    "웹소설", "소설", "문피아", "노벨피아", "시리즈", "카카오", "카카오페이지",
    "네이버", "플랫폼", "웹", "등장인물", "캐릭터", "정식제목", "의미", "뜻",
    "무슨", "어디", "나오는", "나오냐", "나오는지", "어디서", "정보",
}

def _get_searchxng_urls() -> List[str]:
    """
    SEARCHXNG_URLS(콤마구분)가 있으면 우선 사용, 없으면 SEARCHXNG_URL 단일값 사용.
    예: SEARCHXNG_URLS=http://searchxng:8080,https://searx.space
    """
    raw_list = os.getenv("SEARCHXNG_URLS", "").strip()
    urls: List[str] = []
    if raw_list:
        for u in raw_list.split(","):
            u2 = (u or "").strip().rstrip("/")
            if not u2:
                continue
            try:
                host = (urlparse(u2).hostname or "").lower()
            except Exception:
                host = ""
            # searx.space 자체는 인스턴스 디렉터리 포털이며 검색 API(/search)를 제공하지 않는다.
            # 잘못 추가되어도 자동 제외해 404 재시도를 방지한다.
            if host in _DIRECTORY_ONLY_HOSTS:
                continue
            if u2 not in urls:
                urls.append(u2)
    primary = (os.getenv("SEARCHXNG_URL", SEARCHXNG_URL) or "").strip().rstrip("/")
    if primary and primary not in urls:
        urls.insert(0, primary)

    # 공개 인스턴스 자동 발견 (옵션): searx.space instances.json 메타 기반 선별
    if _env_bool("MCP_DISCOVER_PUBLIC_INSTANCES", False):
        for u in _discover_public_instances():
            if u not in urls:
                urls.append(u)

    if not urls:
        urls = [SEARCHXNG_URL.rstrip("/")]
    return urls


def _discover_public_instances() -> List[str]:
    """searx.space 인스턴스 메타를 기반으로 공개 인스턴스 후보를 선별한다.

    주의:
    - 포털(searx.space) 자체는 제외한다.
    - 이 함수는 메타데이터 필터링만 수행한다(능동 프로빙 없음).
    - 실제 요청 실패는 런타임 백오프로 자동 격리된다.
    """
    now = time.time()
    ttl_sec = max(60, min(int(os.getenv("MCP_DISCOVERY_CACHE_SEC", "1800")), 86400))
    if (now - float(_DISCOVERY_CACHE.get("at", 0.0))) < ttl_sec:
        cached = _DISCOVERY_CACHE.get("urls") or []
        return [u for u in cached if isinstance(u, str)]

    source_url = os.getenv("MCP_DISCOVERY_SOURCE_URL", "https://searx.space/data/instances.json").strip()
    max_urls = max(1, min(int(os.getenv("MCP_DISCOVERY_MAX_URLS", "3")), 10))
    min_search_success = float(os.getenv("MCP_DISCOVERY_MIN_SEARCH_SUCCESS", "80.0"))

    discovered: List[str] = []
    try:
        resp = httpx.get(source_url, timeout=8.0)
        resp.raise_for_status()
        payload = resp.json()
        instances = payload.get("instances") or {}
        scored: List[tuple[float, str]] = []

        for raw_url, meta in instances.items():
            if not isinstance(raw_url, str) or not isinstance(meta, dict):
                continue
            url = raw_url.strip().rstrip("/")
            if not url.startswith(("http://", "https://")):
                continue
            try:
                host = (urlparse(url).hostname or "").lower()
            except Exception:
                host = ""
            if host in _DIRECTORY_ONLY_HOSTS:
                continue
            if meta.get("network_type") != "normal":
                continue
            if not bool(meta.get("main", False)):
                continue
            http_status = int((meta.get("http") or {}).get("status_code") or 0)
            if http_status != 200:
                continue
            search_ok = float((((meta.get("timing") or {}).get("search") or {}).get("success_percentage")) or 0.0)
            if search_ok < min_search_success:
                continue
            latency = float(((((meta.get("timing") or {}).get("initial") or {}).get("all") or {}).get("value")) or 999.0)
            scored.append((latency, url))

        scored.sort(key=lambda x: x[0])
        for _, u in scored[:max_urls]:
            discovered.append(u)

    except Exception as e:
        try:
            print(f"[mcp-bridge] public instance discovery failed: {e!r}", file=sys.stderr, flush=True)
        except Exception:
            pass
        discovered = []

    # 발견 실패 시 하드코딩 폴백 인스턴스 사용
    if not discovered:
        fallback_count = max(1, min(max_urls, len(_HARDCODED_FALLBACK_INSTANCES)))
        discovered = list(_HARDCODED_FALLBACK_INSTANCES[:fallback_count])
        try:
            print(
                f"[mcp-bridge] using {len(discovered)} hardcoded fallback instances",
                file=sys.stderr, flush=True,
            )
        except Exception:
            pass

    _DISCOVERY_CACHE["at"] = now
    _DISCOVERY_CACHE["urls"] = discovered
    return discovered


def _mark_endpoint_backoff(endpoint: str, status_code: Optional[int] = None, exc: Optional[Exception] = None) -> None:
    if not endpoint:
        return
    ttl = 60
    if status_code == 404:
        ttl = 6 * 60 * 60
    elif status_code in {403, 429}:
        ttl = 15 * 60
    elif status_code in _RETRYABLE_SEARCH_STATUS:
        ttl = 3 * 60
    elif isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        ttl = 90
    _ENDPOINT_BACKOFF_UNTIL[endpoint] = time.time() + ttl


def _active_searchxng_urls() -> List[str]:
    base = _get_searchxng_urls()
    now = time.time()
    active = [u for u in base if _ENDPOINT_BACKOFF_UNTIL.get(u, 0.0) <= now]
    return active or base


def _sanitize_engines(raw: str, default_csv: str) -> str:
    """Remove blocked engines and normalize comma-separated engine list."""
    parts = [p.strip() for p in (raw or "").split(",") if p.strip()]
    parts = [p for p in parts if p not in _BLOCKED_ENGINES]
    if not parts:
        parts = [p.strip() for p in default_csv.split(",") if p.strip()]
        parts = [p for p in parts if p not in _BLOCKED_ENGINES]
    return ",".join(parts)


def _contains_hangul(text: str) -> bool:
    return bool(re.search(r"[\uac00-\ud7a3]", text or ""))


def _extract_hangul_tokens(text: str) -> List[str]:
    toks = re.findall(r"[\uac00-\ud7a3]{2,}", text or "")
    # 길이가 너무 짧거나 의미 약한 범용어는 제외
    stop = {"검색", "정식", "제목", "작품", "작가", "추천", "리뷰", "웹소설", "소설"}
    out: List[str] = []
    seen = set()
    for t in toks:
        cand = [t]
        # 합성어를 보수적으로 분해해 부분 일치(예: 즉사무림 -> 즉사, 무림) 허용
        if len(t) >= 4:
            cand.extend([t[:2], t[2:]])
        if len(t) >= 6:
            cand.extend([t[:3], t[3:]])
        for c in cand:
            if c in stop or len(c) < 2:
                continue
            if c not in seen:
                seen.add(c)
                out.append(c)
    return out


def _is_korean_friendly_host(url: str) -> bool:
    try:
        from urllib.parse import urlparse

        host = (urlparse(url or "").hostname or "").lower()
    except Exception:
        host = ""
    if not host:
        return False
    if host.endswith(".kr"):
        return True
    for dom in _ALLOWED_FETCH_DOMAINS:
        _d = str(dom or "").lower()
        if host == _d or host.endswith("." + _d):
            return True
    return False


def _host_matches(hostname: str, allowed: set[str]) -> bool:
    if not hostname:
        return False
    for dom in allowed:
        _d = str(dom or "").lower()
        if hostname == _d or hostname.endswith("." + _d):
            return True
    return False


def _classify_korean_host(url: str) -> str:
    try:
        host = (urlparse(url or "").hostname or "").lower()
    except Exception:
        host = ""
    if _host_matches(host, _OFFICIAL_PLATFORM_DOMAINS):
        return "official"
    if _host_matches(host, _COMMUNITY_DOMAINS):
        return "community"
    if _host_matches(host, _REFERENCE_DOMAINS) or host.endswith(".tistory.com"):
        return "reference"
    if host.endswith(".kr"):
        return "korean"
    return "other"


def _is_direct_official_detail_url(url: str) -> bool:
    return bool(_DIRECT_OFFICIAL_DETAIL_URL_RE.search(str(url or "")))


def _is_direct_non_detail_url(url: str) -> bool:
    text = str(url or "")
    if not text:
        return True
    try:
        host = (urlparse(text).hostname or "").lower()
    except Exception:
        host = ""
    if _host_matches(host, _REFERENCE_DOMAINS) or _host_matches(host, _COMMUNITY_DOMAINS):
        return True
    return bool(_DIRECT_NON_DETAIL_URL_RE.search(text))


def _extract_query_core_tokens(query: str) -> List[str]:
    toks = re.findall(r"[\uac00-\ud7a3]{2,}[\u3131-\u314e]?", query or "")
    out: List[str] = []
    seen = set()
    for tok in toks:
        if tok in _QUERY_GENERIC_HANGUL_TOKENS or len(tok) < 2:
            continue
        if tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out


def _query_token_fragments(token: str) -> List[str]:
    norm = re.sub(r"\s+", "", token or "")
    if len(norm) < 4:
        return []
    frags: List[str] = []
    for cand in (norm[:2], norm[-2:], norm[:3], norm[-3:]):
        if len(cand) < 2 or cand in _QUERY_GENERIC_HANGUL_TOKENS:
            continue
        if cand not in frags:
            frags.append(cand)
    return frags


_PURPOSE_RELAXED_TITLE_RESOLUTION = {
    "official_title_verify",
    "platform_title_search",
    "title_search_community",
    "alias_bridge_search",
    "known_abbr_fullname_search",
    "abbreviation_fullname_search",
    "abbreviation_verification",
    "decoder_recall_verification",
    "adaptive_official_url",
    "adaptive_wiki",
}

_PURPOSE_HEADLESS_ALLOWED = {
    "official_title_verify",
    "platform_title_search",
    "adaptive_official_url",
    "abbreviation_verification",
    "title_search_community",
    "alias_bridge_search",
    "known_abbr_fullname_search",
    "abbreviation_fullname_search",
    "decoder_recall_verification",
}

_PURPOSE_HEADLESS_CRITICAL_OFFICIAL = {
    "official_title_verify",
    "platform_title_search",
    "adaptive_official_url",
    "abbreviation_verification",
}

_PURPOSE_HEADLESS_EXCLUDED = {
    "trope_discussion",
    "genre_trope_discussion",
    "recommendation",
    "recommendation_request",
    "term_definition",
    "dictionary",
    "meaning",
    "counter_evidence_character_track",
}

_PURPOSE_STRICT_ANCHOR = {
    "community_chain_search",
    "community_chain_verify",
    "character_verify",
    "character_event_reverse_track",
    "counter_evidence_character_track",
}

_NOVEL_CUE_TOKENS = {
    "웹소설", "소설", "문피아", "노벨피아", "시리즈", "카카오페이지", "조아라",
    "리디", "작가", "연재", "완결", "줄거리", "선호작", "추천수", "#novel",
}


def _purpose_key(raw: str) -> str:
    return str(raw or "").split(":", 1)[0].strip().lower()


def _has_novel_cues(text: str) -> bool:
    norm = (text or "").lower()
    if not norm:
        return False
    return any(tok.lower() in norm for tok in _NOVEL_CUE_TOKENS)


def _source_bound_compound_wiki_character_role(
    query: str, item: Dict[str, Any], purpose: str,
) -> bool:
    """Keep an exact work wiki row when a compound query names its character.

    This is search-row retention only. It does not decide the work identity or
    bypass the later relation and publication gates.
    """
    if _purpose_key(purpose) != "title_anchor_exact_probe":
        return False
    query_text = str(query or "").strip()
    if not re.fullmatch(r"[가-힣]{6,20}", query_text):
        return False
    url = str(item.get("url") or "").strip()
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if (parsed.hostname or "").lower() not in {"namu.wiki", "thewiki.kr"}:
        return False
    if not parsed.path.startswith("/w/"):
        return False
    page_title = unquote(parsed.path[3:]).replace("_", " ").strip()
    row_title = str(item.get("title") or "").strip()
    normalize = lambda value: re.sub(r"[^0-9A-Za-z가-힣]", "", value.lower())
    if not page_title or "/" in page_title or normalize(page_title) != normalize(row_title):
        return False
    content = str(item.get("content") or "").strip()
    if not content:
        return False
    clauses = [part.strip() for part in re.split(r"(?<=[.!?。！？])|[\r\n]+", content) if part.strip()]
    nonaffirmative = re.compile(
        r"[?？]|다른\s*(?:작품|소설)|별개|비교(?!적)|아니|않|없|오인|혼동|착각|무관|"
        r"(?:일|인|했을)\s*수(?:도)?\s*있|가정|추정|소문|것\s*같|듯(?:하|싶)|"
        r"등장하지|나오지|(?:의부|스승|등장인물|주인공).{0,8}(?:아니|아님)"
    )
    for index, clause in enumerate(clauses):
        if nonaffirmative.search(clause):
            continue
        following = " ".join(clauses[index + 1:index + 3])
        if re.match(r"^(?:아니|정정|틀리|오류|그렇지\s*않)", following) or re.search(
            r"다른\s*(?:작품|소설)|별개|무관|"
            r"(?:이|해당)\s*작품.{0,12}(?:나오지|등장하지|아니)", following,
        ):
            continue
        for length in (2, 3, 4):
            if len(query_text) - length < 3:
                continue
            character = re.escape(query_text[-length:])
            if re.search(
                rf"(?<![0-9A-Za-z가-힣]){character}"
                r"(?:은|는|이|가|의)?\s*(?:작가|저자)(?:는|은|가|를|의)?(?![0-9A-Za-z가-힣])",
                clause,
            ):
                continue
            role = re.compile(
                rf"(?<![0-9A-Za-z가-힣]){character}"
                rf"(?:은|는|이|가|을|를|의|도|만)?(?![0-9A-Za-z가-힣]).{{0,24}}"
                r"(?:주인공|등장인물|캐릭터|인물|의부|스승)"
            )
            if role.search(clause):
                return True
    return False


def _non_korean_noise_reason(query: str, item: Dict[str, Any], purpose: str = "") -> Optional[str]:
    """
    한글 질의에서 한국 웹소설 문맥과 무관한 외국어 결과의 필터 사유를 반환한다.

    None 이면 유지, 문자열이면 해당 사유로 브릿지에서 제외한다.
    """
    if not _contains_hangul(query):
        return None
    url = str(item.get("url") or "")
    # 0) 노이즈 도메인 블랙리스트 (중국 포털, 인도 정부 등)
    try:
        _host = (urlparse(url).hostname or "").lower()
    except Exception:
        _host = ""
    if _is_blacklisted_host(_host):
        return f"blacklisted_host:{_host or 'unknown'}"
    title = str(item.get("title") or "")
    content = str(item.get("content") or "")
    merged = f"{title} {content}"
    host_kind = _classify_korean_host(url)
    purpose_key = _purpose_key(purpose)
    novel_cues = _has_novel_cues(merged)
    # 2) 한글이 전혀 없으면 바로 노이즈
    if not _contains_hangul(merged):
        return f"no_hangul:{host_kind}"
    # 3) 질의의 한글 핵심 토큰이 스니펫에 없으면 노이즈
    q_tokens = _extract_query_core_tokens(query)
    if q_tokens:
        merged_norm = re.sub(r"\s+", "", merged)
        full_overlap = any(tok in merged_norm for tok in q_tokens)
        frag_overlap = any(
            frag in merged_norm
            for tok in q_tokens
            for frag in _query_token_fragments(tok)
        )
        if purpose_key in _PURPOSE_RELAXED_TITLE_RESOLUTION:
            # 제목/플랫폼 검증 계열은 약칭→정식명 브리지가 필요한 경우가 많다.
            # 공식/커뮤니티/참고 도메인에서는 "웹소설/연재/작가/플랫폼" 단서가 있으면
            # 질의 토큰 직접 일치가 약해도 일단 후보를 남긴다.
            if host_kind == "official":
                if not (full_overlap or frag_overlap or novel_cues):
                    return f"token_mismatch:{host_kind}"
            elif host_kind in {"community", "reference", "korean"}:
                if not (full_overlap or frag_overlap or novel_cues):
                    return f"token_mismatch:{host_kind}"
            else:
                if not (full_overlap or frag_overlap):
                    return f"token_mismatch:{host_kind or 'other'}"
        elif purpose_key in _PURPOSE_STRICT_ANCHOR:
            # 캐릭터/체인 검색은 인명 일반어 노이즈가 많아서 더 엄격하게 본다.
            if not (full_overlap or frag_overlap):
                return f"strict_anchor_mismatch:{host_kind or 'other'}"
            if len(q_tokens) <= 1 and not novel_cues:
                return f"strict_anchor_without_novel_cue:{host_kind or 'other'}"
        elif host_kind == "official":
            if not (full_overlap or frag_overlap):
                return f"token_mismatch:{host_kind}"
        elif host_kind == "community":
            if not (full_overlap or frag_overlap):
                return f"token_mismatch:{host_kind}"
        elif host_kind in {"reference", "korean"}:
            if not full_overlap and not _source_bound_compound_wiki_character_role(
                query, item, purpose,
            ):
                return f"token_mismatch:{host_kind}"
        else:
            if not full_overlap:
                return f"token_mismatch:{host_kind or 'other'}"
    # 4) 중국어/일본어/베트남어 위주 콘텐츠 탐지 (한글이 있더라도 중국어가 더 많으면 노이즈)
    _cjk_non_hangul = len(re.findall(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]', merged))
    _hangul_count = len(re.findall(r'[\uac00-\ud7a3]', merged))
    if _cjk_non_hangul > 0 and _cjk_non_hangul > _hangul_count * 2:
        return f"cjk_dominant:{host_kind or 'other'}"
    return None


def _is_non_korean_noise_result(query: str, item: Dict[str, Any], purpose: str = "") -> bool:
    return _non_korean_noise_reason(query, item, purpose) is not None


def _merge_count_map(dst: Dict[str, int], src: Dict[str, int]) -> None:
    for key, value in (src or {}).items():
        if not key:
            continue
        try:
            delta = int(value)
        except Exception:
            continue
        if delta <= 0:
            continue
        dst[key] = int(dst.get(key, 0)) + delta


def _filter_korean_noise(
    query: str,
    items: List[Dict[str, Any]],
    purpose: str = "",
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, int]]:
    kept: List[Dict[str, Any]] = []
    removed: List[Dict[str, Any]] = []
    reason_counts: Dict[str, int] = {}

    for item in items or []:
        if not isinstance(item, dict):
            continue
        reason = _non_korean_noise_reason(query, item, purpose)
        if not reason:
            kept.append(item)
            continue
        reason_key = str(reason).split(":", 1)[0].strip() or "unknown"
        reason_counts[reason_key] = int(reason_counts.get(reason_key, 0)) + 1
        removed_item = dict(item)
        removed_item["filter_reason"] = reason
        removed.append(removed_item)

    return kept, removed, reason_counts


def _dedupe_search_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        title = str(item.get("title") or "").strip()
        key = (url, title)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _dedupe_by_url(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen_urls: set[str] = set()
    seen_title_url: set[tuple[str, str]] = set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        title = str(item.get("title") or "").strip()
        if url:
            key_url = re.sub(r"#.*$", "", url)
            if key_url in seen_urls:
                continue
            seen_urls.add(key_url)
        else:
            key = (title, str(item.get("content") or "")[:80])
            if key in seen_title_url:
                continue
            seen_title_url.add(key)
        deduped.append(item)
    return deduped


_DIRECT_SEARCH_PROVIDERS = {"naver", "bing"}
_DIRECT_SEARCH_EXCLUDED_HOSTS = {
    "search.naver.com",
    "m.search.naver.com",
    "www.naver.com",
    "naver.com",
    "search.shopping.naver.com",
    "dict.naver.com",
    "map.naver.com",
    "m.map.naver.com",
    "book.naver.com",
    "ader.naver.com",
    "adcr.naver.com",
    "m.adcr.naver.com",
    "www.bing.com",
    "bing.com",
    "www.google.com",
    "google.com",
    "search.daum.net",
}


class _SearchAnchorParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self._in_anchor = False
        self._href = ""
        self._parts: List[str] = []
        self.anchors: List[Dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        if tag.lower() != "a":
            return
        attr_map = {str(k).lower(): str(v or "") for k, v in attrs}
        href = attr_map.get("href", "").strip()
        if not href:
            return
        self._in_anchor = True
        self._href = urljoin(self.base_url, href)
        self._parts = []

    def handle_data(self, data: str) -> None:
        if self._in_anchor and data:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._in_anchor:
            return
        text = re.sub(r"\s+", " ", " ".join(self._parts)).strip()
        if text and self._href:
            self.anchors.append({"title": text, "url": self._href})
        self._in_anchor = False
        self._href = ""
        self._parts = []


def _decode_bing_redirect_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        encoded = (qs.get("u") or [""])[0]
        if not encoded:
            return url
        if encoded.startswith("a1"):
            encoded = encoded[2:]
        padded = encoded + "=" * (-len(encoded) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8", "ignore")
        return decoded if decoded.startswith(("http://", "https://")) else url
    except Exception:
        return url


def _clean_direct_search_url(url: str) -> str:
    candidate = unquote(str(url or "").strip())
    if not candidate:
        return ""
    parsed = urlparse(candidate)
    host = (parsed.hostname or "").lower()
    if host in {"www.bing.com", "bing.com"} and parsed.path.startswith("/ck/"):
        candidate = _decode_bing_redirect_url(candidate)
        parsed = urlparse(candidate)
        host = (parsed.hostname or "").lower()
    if host in _DIRECT_SEARCH_EXCLUDED_HOSTS:
        qs = parse_qs(parsed.query)
        for key in ("url", "u", "r", "target"):
            for raw in qs.get(key, []):
                decoded = _decode_bing_redirect_url(unquote(raw))
                if decoded.startswith(("http://", "https://")):
                    return _clean_direct_search_url(decoded)
        return ""
    if not candidate.startswith(("http://", "https://")):
        return ""
    if re.search(r"\.(?:css|js|png|jpe?g|gif|svg|ico)(?:$|[?#])", candidate, re.IGNORECASE):
        return ""
    return candidate


def _is_naver_original_product_id_url(url: str) -> bool:
    """Search-form Series identifiers need normal fetch/redirect before detail use."""
    try:
        parsed = urlparse(str(url or ""))
        query = parse_qs(parsed.query, keep_blank_values=True)
        original_ids = [value for key, values in query.items()
                        if key.lower() == "originalproductid" for value in values]
        return bool(
            parsed.scheme == "https"
            and (parsed.hostname or "").lower() in {"series.naver.com", "m.series.naver.com"}
            and parsed.username is None and parsed.password is None
            and parsed.port is None and "#" not in url
            and parsed.path.lower() in {"/novel/detail.series", "/novel/detail.nhn"}
            and len(query) == 1 and len(original_ids) == 1
            and re.fullmatch(r"[0-9]+", original_ids[0]) is not None
        )
    except ValueError:
        return False


def _title_from_direct_url(url: str) -> str:
    try:
        parsed = urlparse(url or "")
        host = (parsed.hostname or "").lower()
        path = unquote(parsed.path or "")
    except Exception:
        return ""
    if host == "namu.wiki" and path.startswith("/w/"):
        title = path.split("/w/", 1)[1].split("/", 1)[0]
        return re.sub(r"[_\s]+", " ", title).strip()
    if host in {"arca.live"} and "/b/" in path:
        return ""
    return ""


def _is_direct_search_breadcrumb_title(title: str, url: str) -> bool:
    clean = re.sub(r"\s+", " ", title or "").strip()
    if not clean:
        return True
    lower = clean.lower()
    try:
        host = (urlparse(url or "").hostname or "").lower()
    except Exception:
        host = ""
    if clean in {"NAVER", "Bing", "Google", "Daum"}:
        return True
    if clean.endswith("›"):
        return True
    if "›" in clean and host:
        host_label = host.replace("www.", "").split(".", 1)[0]
        if host_label and host_label in lower and len(clean) <= 80:
            return True
    if host and lower in {host, host.replace("www.", ""), f"{host} ›"}:
        return True
    return False


def _direct_search_url(provider: str, query: str) -> str:
    from urllib.parse import urlencode

    if provider == "naver":
        return "https://search.naver.com/search.naver?" + urlencode({"query": query})
    if provider == "bing":
        return "https://www.bing.com/search?" + urlencode({"q": query})
    raise ValueError(f"unsupported direct search provider: {provider}")


def _normalize_direct_search_items(
    *,
    html: str,
    provider: str,
    base_url: str,
    query: str,
    purpose: str,
    limit: int,
) -> List[Dict[str, Any]]:
    parser = _SearchAnchorParser(base_url)
    try:
        parser.feed(html or "")
    except Exception:
        return []
    items: List[Dict[str, Any]] = []
    seen_urls: set[str] = set()
    for anchor in parser.anchors:
        title = re.sub(r"\s+", " ", str(anchor.get("title") or "")).strip()
        url = _clean_direct_search_url(anchor.get("url") or "")
        if not title or len(title) < 2 or not url:
            continue
        clean_title = re.sub(r"\s*[-|:]\s*(네이버\s*검색|Bing|검색)$", "", title).strip()
        if _is_direct_search_breadcrumb_title(clean_title or title, url):
            recovered_title = _title_from_direct_url(url)
            if not recovered_title:
                continue
            clean_title = recovered_title
        item = {
            "title": clean_title or title,
            "url": url,
            "content": clean_title or title,
            "engine": f"direct_{provider}",
            "source_url_original": url,
            "official_detail_verified": False,
            "official_detail_verification_state": "hold_pending_normal_fetch_redirect",
        }
        if _non_korean_noise_reason(query, item, purpose):
            continue
        key = re.sub(r"#.*$", "", url)
        if key in seen_urls:
            continue
        seen_urls.add(key)
        items.append(item)
        if len(items) >= limit:
            break
    return items


def _direct_search_fallback_reason(
    *,
    filtered_items: List[Dict[str, Any]],
    degraded: bool,
    possible_throttle: bool,
    num_results: int,
    raw_items: Optional[List[Dict[str, Any]]] = None,
    filtered_out_items: Optional[List[Dict[str, Any]]] = None,
    filter_reason_counts: Optional[Dict[str, int]] = None,
) -> str:
    if not _env_bool("MCP_DIRECT_SEARCH_FALLBACK", True):
        return ""
    accepted_count = len(filtered_items or [])
    raw_count = len(raw_items or [])
    reason_counts = filter_reason_counts or {}
    mismatch_count = sum(
        int(reason_counts.get(key, 0) or 0)
        for key in ("token_mismatch", "no_hangul", "blacklisted_host", "cjk_dominant")
    )
    noise_ratio = _foreign_noise_ratio(list(filtered_out_items or []) + list(raw_items or []))
    if accepted_count == 0:
        if raw_count >= 8 and mismatch_count >= max(4, raw_count // 2):
            return "low_bridge_after_filter"
        if raw_count >= 8 and noise_ratio >= 0.65:
            return "foreign_noise_dominant"
        return "empty_results"
    if (degraded or possible_throttle) and accepted_count < min(3, max(1, num_results // 3)):
        return "degraded_low_accepted"
    if raw_count >= 8 and accepted_count <= 2 and mismatch_count >= max(4, raw_count // 2):
        return "low_bridge_after_filter"
    if raw_count >= 8 and noise_ratio >= 0.65 and accepted_count < num_results:
        return "foreign_noise_dominant"
    return ""


def _run_exact_title_direct_fallback_reason(
    request: SearchRequest,
    *,
    filtered_items: List[Dict[str, Any]],
    raw_items: List[Dict[str, Any]],
    filtered_out_items: List[Dict[str, Any]],
) -> str:
    """Fail-closed direct-search gate for a scoped exact-title research bridge."""
    if not _env_bool("MCP_DIRECT_SEARCH_FALLBACK", False):
        return ""
    if _purpose_key(request.purpose) != "official_title_verify":
        return ""
    if not _run_direct_source_binding_digest(request):
        return ""
    if filtered_items:
        return ""
    if not raw_items:
        return "run_exact_title_empty"
    if len(raw_items) != 10 or len(filtered_out_items) != 10:
        return ""
    unrelated_reasons = ("token_mismatch:", "no_hangul:", "blacklisted_host:", "cjk_dominant:")
    for raw, rejected in zip(raw_items, filtered_out_items):
        if not isinstance(raw, dict) or not isinstance(rejected, dict):
            return ""
        url = str(raw.get("url") or "").strip()
        if not url or "filter_reason" in raw:
            return ""
        # _filter_korean_noise copies the exact raw item and adds one reason.
        # A matching URL alone does not bind a rejection to its source row.
        if {key: value for key, value in rejected.items() if key != "filter_reason"} != raw:
            return ""
        reason = str(rejected.get("filter_reason") or "")
        if not reason.startswith(unrelated_reasons):
            return ""
        if _non_korean_noise_reason(request.query, raw, request.purpose) != reason:
            return ""
    return "run_exact_title_irrelevant10"


def _run_direct_source_binding_digest(request: SearchRequest) -> str:
    """Validate one pinned run/row and return its runtime source receipt digest."""
    run_id = str(request.run_id or "").strip()
    post_id = str(request.post_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", run_id):
        return ""
    if not re.fullmatch(r"[0-9]{1,20}", post_id):
        return ""
    if run_id != os.getenv("MCP_DIRECT_SEARCH_RUN_ID", "").strip():
        return ""
    if post_id != os.getenv("MCP_DIRECT_SEARCH_POST_ID", "").strip():
        return ""
    receipt = request.source_receipt
    fields = {
        "schema_version", "run_id", "post_id", "canonical_title",
        "author_alias_span", "author_source", "original_post_sha256",
        "alias_relation_evidence_ref", "alias_relation_evidence_sha256",
        "relation_kind", "required_site_query",
    }
    if not isinstance(receipt, dict) or set(receipt) != fields:
        return ""
    if any(not isinstance(receipt.get(key), str) for key in fields):
        return ""
    if (receipt["schema_version"] != "source_bound_canonical_title_v1"
            or receipt["relation_kind"] != "alias_of"
            or receipt["run_id"] != run_id
            or receipt["post_id"] != post_id
            or receipt["author_source"] not in {"author_title", "author_body"}):
        return ""
    normalized_query = re.sub(r"\s+", " ", request.query or "").strip()
    normalized_title = re.sub(r"\s+", " ", receipt["canonical_title"]).strip()
    if not normalized_query or normalized_query != normalized_title:
        return ""
    if re.search(r"(?i)(?:\bsite:|https?://|[\"“”‘’])", normalized_query):
        return ""
    if receipt["required_site_query"] not in {
        f'site:novelpia.com/novel "{normalized_title}"',
        f'site:munpia.com "{normalized_title}"',
    }:
        return ""
    if not 1 <= len(receipt["author_alias_span"].strip()) <= 120:
        return ""
    if not 1 <= len(receipt["alias_relation_evidence_ref"].strip()) <= 500:
        return ""
    if not all(re.fullmatch(r"[0-9a-f]{64}", receipt[key]) for key in (
        "original_post_sha256", "alias_relation_evidence_sha256",
    )):
        return ""
    from hashlib import sha256
    from json import dumps

    digest = sha256(dumps(
        receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return digest


def _direct_search_fallback_readyz_ok() -> bool:
    if _env_bool("MCP_DIRECT_SEARCH_EXACT_TITLE_ONLY", False):
        return False
    if not _env_bool("MCP_DIRECT_SEARCH_FALLBACK_READYZ_OK", False):
        return False
    if not _env_bool("MCP_DIRECT_SEARCH_FALLBACK", True):
        return False
    providers = [
        p.strip().lower()
        for p in os.getenv("MCP_DIRECT_SEARCH_PROVIDERS", "naver,bing").split(",")
        if p.strip().lower() in _DIRECT_SEARCH_PROVIDERS
    ]
    return bool(providers)


def _call_direct_search_fallback(query: str, num_results: int, purpose: str) -> Dict[str, Any]:
    providers_raw = os.getenv("MCP_DIRECT_SEARCH_PROVIDERS", "naver,bing")
    providers = list(dict.fromkeys(
        p.strip().lower()
        for p in providers_raw.split(",")
        if p.strip().lower() in _DIRECT_SEARCH_PROVIDERS
    )) or ["naver", "bing"]
    try:
        timeout_sec = max(3.0, min(float(os.getenv("MCP_DIRECT_SEARCH_TIMEOUT_SEC", "12")), 30.0))
    except Exception:
        timeout_sec = 12.0
    max_items = max(1, min(int(num_results or DEFAULT_NUM_RESULTS), 10))
    headers = {
        "User-Agent": _random_browser_ua(),
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    items: List[Dict[str, Any]] = []
    errors: List[str] = []
    used_providers: List[str] = []
    attempted_providers: List[str] = []
    for provider in providers:
        attempted_providers.append(provider)
        search_url = _direct_search_url(provider, query)
        try:
            resp = httpx.get(search_url, headers=headers, timeout=timeout_sec, follow_redirects=True)
            resp.raise_for_status()
            found = _normalize_direct_search_items(
                html=resp.text,
                provider=provider,
                base_url=search_url,
                query=query,
                purpose=purpose,
                limit=max_items,
            )
            if found:
                used_providers.append(provider)
                items = _dedupe_by_url(items + found)
            if len(items) >= max_items:
                break
        except Exception as exc:
            errors.append(f"{provider}:{exc}")
    return {
        "results": _rank_direct_search_items(items, query)[:max_items],
        "count": len(_rank_direct_search_items(items, query)[:max_items]),
        "providers": used_providers,
        "attempted_providers": attempted_providers,
        "errors": errors[-5:],
    }


def _rank_direct_search_items(items: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    def _rank(item: Dict[str, Any], idx: int) -> tuple[int, int, int]:
        url = str(item.get("url") or "")
        kind = _classify_korean_host(url)
        if _is_direct_official_detail_url(url):
            tier = 0
        elif kind == "official" and not _is_direct_non_detail_url(url):
            tier = 1
        else:
            tier = {
                "official": 2,
                "reference": 3,
                "community": 4,
                "korean": 5,
            }.get(kind, 6)
        merged = re.sub(r"\s+", "", f"{item.get('title') or ''} {item.get('content') or ''}")
        overlap = sum(1 for tok in _extract_query_core_tokens(query) if tok and tok in merged)
        return (tier, -overlap, idx)

    return [
        item
        for _, item in sorted(
            enumerate(items or []),
            key=lambda pair: _rank(pair[1], pair[0]),
        )
    ]


def _has_official_platform_result(items: List[Dict[str, Any]]) -> bool:
    for item in items or []:
        if not isinstance(item, dict):
            continue
        try:
            host = (urlparse(str(item.get("url") or "")).hostname or "").lower()
        except Exception:
            host = ""
        if _host_matches(host, _OFFICIAL_PLATFORM_DOMAINS):
            return True
    return False


def _is_short_generic_query(query: str) -> bool:
    tokens = _extract_query_core_tokens(query)
    if not tokens:
        return True
    non_generic = [tok for tok in tokens if tok not in _QUERY_GENERIC_HANGUL_TOKENS]
    if len(non_generic) == 1 and len(non_generic[0]) <= 2:
        return True
    return False


def _is_meaning_only_query(query: str, purpose: str) -> bool:
    purpose_key = _purpose_key(purpose)
    if purpose_key in {"term_definition", "dictionary", "meaning"}:
        return True
    q = str(query or "")
    if re.search(r"(뜻|의미|차이|무슨\s*뜻|무슨\s*의미)", q) and not re.search(
        r"(정식\s*제목|작품명|웹소설|소설|노벨피아|문피아|시리즈|카카오페이지)",
        q,
    ):
        return True
    return False


def _foreign_noise_ratio(items: List[Dict[str, Any]]) -> float:
    if not items:
        return 0.0
    noisy = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        reason = str(item.get("filter_reason") or "")
        if reason.startswith(("no_hangul", "blacklisted_host", "cjk_dominant", "token_mismatch")):
            noisy += 1
            continue
        merged = f"{item.get('title') or ''} {item.get('content') or ''}"
        hangul = len(re.findall(r"[\uac00-\ud7a3]", merged))
        cjk = len(re.findall(r"[\u4e00-\u9fff\u3040-\u30ff]", merged))
        latin = len(re.findall(r"[A-Za-z]", merged))
        if (cjk > hangul * 2 and cjk > 6) or (latin > max(20, hangul * 5)):
            noisy += 1
    return noisy / max(1, len(items))


def _headless_fallback_reason(
    *,
    request: SearchRequest,
    filtered_items: List[Dict[str, Any]],
    raw_items: List[Dict[str, Any]],
    filtered_out_items: List[Dict[str, Any]],
    filter_reason_counts: Dict[str, int],
    degraded: bool,
    possible_throttle: bool,
    num_results: int,
) -> Optional[str]:
    if not HEADLESS_SEARCH_ENABLED:
        return None
    if time.time() < _HEADLESS_BACKOFF_UNTIL:
        return None
    query = request.query.strip()
    purpose_key = _purpose_key(request.purpose)
    if not _contains_hangul(query):
        return None
    if purpose_key in _PURPOSE_HEADLESS_EXCLUDED:
        return None
    if _is_meaning_only_query(query, request.purpose):
        return None
    if _is_short_generic_query(query):
        return None

    accepted_count = len(filtered_items or [])
    raw_count = len(raw_items or [])
    official_missing = not _has_official_platform_result(filtered_items)
    allowed_purpose = purpose_key in _PURPOSE_HEADLESS_ALLOWED
    critical_official_purpose = purpose_key in _PURPOSE_HEADLESS_CRITICAL_OFFICIAL
    noise_ratio = _foreign_noise_ratio(list(filtered_out_items or []) + list(raw_items or []))
    mismatch_count = sum(
        int(filter_reason_counts.get(key, 0))
        for key in ("token_mismatch", "no_hangul", "blacklisted_host", "cjk_dominant")
    )

    if accepted_count == 0:
        return "empty_results"
    if (degraded or possible_throttle) and accepted_count < min(3, max(1, num_results // 3)):
        return "degraded_low_accepted"
    if raw_count >= 8 and accepted_count <= 2 and mismatch_count >= max(4, raw_count // 2):
        return "low_bridge_after_filter"
    if raw_count >= 8 and noise_ratio >= 0.65 and accepted_count < num_results:
        return "foreign_noise_dominant"
    if critical_official_purpose and official_missing and accepted_count < min(5, max(2, num_results // 2)):
        return "official_candidate_missing"
    if allowed_purpose and official_missing and (degraded or accepted_count < 3 or mismatch_count >= 5):
        return "official_candidate_missing"
    return None


def _call_headless_search(query: str, num_results: int, purpose: str) -> Dict[str, Any]:
    global _HEADLESS_BACKOFF_UNTIL
    try:
        response = httpx.post(
            HEADLESS_SEARCH_URL,
            json={
                "query": query,
                "num_results": max(1, min(int(num_results or 10), 10)),
                "purpose": purpose or "",
            },
            timeout=45.0,
        )
        response.raise_for_status()
        payload = response.json() if response.content else {}
        if bool(payload.get("blocked")):
            _HEADLESS_BACKOFF_UNTIL = time.time() + HEADLESS_COOLDOWN_SEC
        return payload if isinstance(payload, dict) else {"results": [], "blocked": False, "raw_total": 0}
    except Exception as exc:
        _HEADLESS_BACKOFF_UNTIL = time.time() + min(HEADLESS_COOLDOWN_SEC, 120)
        try:
            print(f"[mcp-bridge] headless fallback failed: {exc!r}", file=sys.stderr, flush=True)
        except Exception:
            pass
        return {"results": [], "blocked": False, "raw_total": 0, "error": str(exc)}


def _normalize_headless_items(payload: Dict[str, Any], query: str, purpose: str) -> List[Dict[str, Any]]:
    raw_results = payload.get("results") or []
    normalized: List[Dict[str, Any]] = []
    if not isinstance(raw_results, list):
        return normalized
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        candidate = {
            "title": str(item.get("title") or "").strip(),
            "url": str(item.get("url") or "").strip(),
            "content": str(item.get("content") or "").strip(),
            "engine": str(item.get("engine") or "headless_google").strip() or "headless_google",
        }
        if not candidate["title"] or not candidate["url"]:
            continue
        if _non_korean_noise_reason(query, candidate, purpose):
            continue
        normalized.append(candidate)
    return normalized


def _build_search_preview_items(items: List[Dict[str, Any]], *, limit: int = 5) -> List[Dict[str, Any]]:
    preview: List[Dict[str, Any]] = []
    try:
        safe_limit = max(1, min(int(limit), 10))
    except Exception:
        safe_limit = 5

    for item in (items or [])[:safe_limit]:
        if not isinstance(item, dict):
            continue
        preview.append(
            {
                "title": str(item.get("title") or "").strip(),
                "url": str(item.get("url") or "").strip(),
                "content": str(item.get("content") or "").strip()[:240],
                "engine": str(item.get("engine") or "").strip(),
                "filter_reason": str(item.get("filter_reason") or "").strip(),
            }
        )
    return preview


@app.get("/readyz")
@app.get("/healthz/deep")
def readyz():
    """깊은 준비 상태 확인 — SearXNG/headless 연결까지 확인한다."""
    urls = _get_searchxng_urls()
    checks: List[Dict[str, Any]] = []
    any_ok = False
    for u in urls:
        try:
            resp = httpx.get(f"{u}/healthz", timeout=5.0)
            ok = bool(resp.status_code == 200)
            checks.append(
                {
                    "url": u,
                    "ok": ok,
                    "status_code": resp.status_code,
                    "backoff_until": _ENDPOINT_BACKOFF_UNTIL.get(u, 0.0),
                }
            )
            any_ok = any_ok or ok
        except Exception as e:
            checks.append(
                {
                    "url": u,
                    "ok": False,
                    "error": str(e),
                    "backoff_until": _ENDPOINT_BACKOFF_UNTIL.get(u, 0.0),
                }
            )
    headless_ok = _headless_health_ok()
    direct_fallback_ready = _direct_search_fallback_readyz_ok()
    return {
        "status": "ok" if (any_ok or headless_ok or direct_fallback_ready) else "degraded",
        "searxng": any_ok,
        "headless_search": headless_ok,
        "direct_search_fallback": direct_fallback_ready,
        "direct_search_degraded_provider": bool(direct_fallback_ready and not any_ok and not headless_ok),
        "checks": checks,
    }


def _headless_health_ok() -> bool:
    if not HEADLESS_SEARCH_ENABLED:
        return False
    try:
        url = HEADLESS_SEARCH_URL.rsplit("/", 1)[0].rstrip("/") + "/healthz"
        response = httpx.get(url, timeout=2.0)
        return response.status_code == 200
    except Exception:
        return False


@app.post("/mcp/search")
def mcp_search(request: SearchRequest) -> Dict[str, Any]:
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="query is required")

    num_results = request.num_results or DEFAULT_NUM_RESULTS
    params = {"q": request.query, "format": "json", "safesearch": "0", "pageno": "1"}
    default_language = os.getenv("MCP_SEARCH_LANGUAGE", "ko-KR").strip()
    if default_language:
        params["language"] = default_language
    try:
        max_retries = max(0, min(int(os.getenv("MCP_SEARCH_MAX_RETRIES", "1")), 8))
    except Exception:
        max_retries = 1
    try:
        max_pages = max(1, min(int(os.getenv("MCP_SEARCH_MAX_PAGES", "2")), 5))
    except Exception:
        max_pages = 2
    try:
        backoff_ms = max(50, min(int(os.getenv("MCP_SEARCH_RETRY_BACKOFF_MS", "250")), 5000))
    except Exception:
        backoff_ms = 250
    retry_on_empty = _env_bool("MCP_SEARCH_RETRY_ON_EMPTY", True)
    soft_fail = _env_bool("MCP_SEARCH_SOFT_FAIL", True)
    timeout_sec = float(os.getenv("MCP_SEARCH_TIMEOUT_SEC", "20"))
    endpoint_candidates = _active_searchxng_urls()
    # 기본 엔진을 명시해 인스턴스 기본값(yahoo/wikidata 등) 유입을 방지한다.
    # presearch는 access denied가 반복되어 모든 검색을 degraded로 만들 수 있어 기본값에서 제외한다.
    # CAPTCHA가 잦은 startpage/duckduckgo/brave는 기본값에서 제외한다.
    _query_has_hangul = _contains_hangul(request.query)
    _default_primary = "google,bing,webcrawler,naver"
    _default_fallback = "webcrawler,google,bing,naver"
    primary_engines = _sanitize_engines(
        os.getenv("MCP_SEARCH_ENGINES", _default_primary).strip(),
        _default_primary,
    )
    fallback_engines = _sanitize_engines(
        os.getenv("MCP_SEARCH_FALLBACK_ENGINES", _default_fallback).strip(),
        _default_fallback,
    )

    # SearXNG botdetection은 X-Forwarded-For / X-Real-IP 헤더가 없으면 에러/차단을 유발할 수 있음.
    # 실제 브라우저 UA 로테이션으로 업스트림 검색엔진 차단 회피
    headers = {
        "User-Agent": _random_browser_ua(),
        "X-Forwarded-For": "127.0.0.1",
        "X-Real-IP": "127.0.0.1",
        "X-Forwarded-Proto": "http",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    data: Dict[str, Any] = {}
    attempts = 0
    possible_throttle = False
    retry_errors: List[str] = []
    used_endpoint = endpoint_candidates[0] if endpoint_candidates else SEARCHXNG_URL.rstrip("/")
    local_endpoint = used_endpoint
    remote_candidates = endpoint_candidates[1:] if len(endpoint_candidates) > 1 else []

    _local_degraded = False  # 로컬 인스턴스에서 연속 저하 감지
    pages_fetched = 0
    filtered_out_items: List[Dict[str, Any]] = []
    filter_reason_counts: Dict[str, int] = {}

    for attempt in range(max_retries + 1):
        attempts = attempt + 1
        # 재시도 전략:
        # 1) local + primary engines
        # 2) local + fallback engines (단, 로컬 저하면 즉시 remote로 전환)
        # 3+) remote endpoints 라운드로빈 (엔진 미지정 — 원격 인스턴스 기본 엔진 사용)
        if attempt == 0:
            used_endpoint = local_endpoint
        elif attempt == 1 and not _local_degraded:
            used_endpoint = local_endpoint
        else:
            if remote_candidates:
                # 로컬 저하 시 attempt=1부터 바로 원격 사용
                ridx = (attempt - (1 if _local_degraded else 2)) % len(remote_candidates)
                used_endpoint = remote_candidates[ridx]
            else:
                used_endpoint = local_endpoint
        req_params = dict(params)
        if used_endpoint == local_endpoint:
            if attempt == 0 and primary_engines:
                req_params["engines"] = primary_engines
            elif attempt > 0 and fallback_engines:
                req_params["engines"] = fallback_engines
        # 원격 인스턴스에서는 site: 접두어를 제거한 단순 쿼리 사용
        # (공개 인스턴스는 site: 연산자 지원이 불안정할 수 있음)
        if used_endpoint != local_endpoint and "site:" in req_params.get("q", ""):
            _orig_q = req_params["q"]
            _clean_q = re.sub(r"site:\S+\s*(?:OR\s+site:\S+\s*)*", "", _orig_q).strip()
            if _clean_q:
                req_params["q"] = _clean_q
        try:
            response = httpx.get(
                f"{used_endpoint.rstrip('/')}/search",
                params=req_params,
                headers=headers,
                timeout=timeout_sec,
            )
            status = int(response.status_code)
            if status in _RETRYABLE_SEARCH_STATUS:
                possible_throttle = True
                _mark_endpoint_backoff(used_endpoint, status_code=status)
                if attempt < max_retries:
                    retry_errors.append(f"http:{status}")
                    sleep_sec = (backoff_ms / 1000.0) * (attempt + 1)
                    time.sleep(sleep_sec)
                    continue
            response.raise_for_status()
            data = response.json() if response.content else {}
        except httpx.HTTPError as exc:
            # 원인 파악을 위해 stderr에 디테일을 남긴다.
            try:
                print(
                    f"[mcp-bridge] searchxng request failed: endpoint={used_endpoint} err={exc!r}",
                    file=sys.stderr,
                    flush=True,
                )
            except Exception:
                pass
            retry_errors.append(str(exc))
            status_code = None
            if isinstance(exc, httpx.HTTPStatusError):
                status_code = int(exc.response.status_code)
            # 일부 퍼블릭 인스턴스는 /search JSON API를 비활성화(404)한다.
            # 이런 경우 현재 인스턴스를 건너뛰고 다음 시도로 넘어간다.
            if status_code == 404 and attempt < max_retries:
                _mark_endpoint_backoff(used_endpoint, status_code=status_code)
                retry_errors.append("http:404(search_api_unsupported)")
                sleep_sec = (backoff_ms / 1000.0) * (attempt + 1)
                time.sleep(sleep_sec)
                continue
            if status_code in _RETRYABLE_SEARCH_STATUS and attempt < max_retries:
                possible_throttle = True
                _mark_endpoint_backoff(used_endpoint, status_code=status_code)
                sleep_sec = (backoff_ms / 1000.0) * (attempt + 1)
                time.sleep(sleep_sec)
                continue
            if attempt < max_retries and isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
                _mark_endpoint_backoff(used_endpoint, status_code=status_code, exc=exc)
                sleep_sec = (backoff_ms / 1000.0) * (attempt + 1)
                time.sleep(sleep_sec)
                continue
            if soft_fail:
                data = {
                    "results": [],
                    "errors": retry_errors[-5:],
                    "unresponsive_engines": [],
                }
                break
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        # 1페이지가 비한국어/브릿지 필터로 비거나, accepted 결과가 부족해도
        # 짧은 추가 페이지를 훑어 관련 결과를 보충한다. 과도한 page/retry는
        # direct/headless fallback 진입을 늦춰 큰 런의 flush를 막을 수 있다.
        raw_items = list(data.get("results", []) or [])
        if _query_has_hangul:
            filtered_items, _removed_items, _removed_counts = _filter_korean_noise(
                request.query,
                raw_items,
                request.purpose,
            )
            filtered_out_items = list(_removed_items)
            filter_reason_counts = dict(_removed_counts)
        else:
            filtered_items = list(raw_items)
        pages_fetched = 1
        all_filtered_first_page = bool(raw_items) and not filtered_items

        if max_pages > 1 and (len(filtered_items) < num_results or all_filtered_first_page):
            for page_no in range(2, max_pages + 1):
                page_params = dict(req_params)
                page_params["pageno"] = str(page_no)
                try:
                    page_response = httpx.get(
                        f"{used_endpoint.rstrip('/')}/search",
                        params=page_params,
                        headers=headers,
                        timeout=timeout_sec,
                    )
                    if int(page_response.status_code) in _RETRYABLE_SEARCH_STATUS:
                        possible_throttle = True
                        retry_errors.append(f"page{page_no}:http:{int(page_response.status_code)}")
                        # 1페이지 raw가 전부 필터된 경우에는 다음 페이지를 더 훑어본다.
                        if all_filtered_first_page and page_no < max_pages:
                            continue
                        break
                    page_response.raise_for_status()
                    page_data = page_response.json() if page_response.content else {}
                except Exception as exc:
                    retry_errors.append(f"page{page_no}:{exc}")
                    if all_filtered_first_page and page_no < max_pages:
                        continue
                    break

                page_raw_items = list(page_data.get("results", []) or [])
                if not page_raw_items:
                    if all_filtered_first_page and page_no < max_pages:
                        continue
                    break
                if _query_has_hangul:
                    page_filtered_items, _page_removed, _page_removed_counts = _filter_korean_noise(
                        request.query,
                        page_raw_items,
                        request.purpose,
                    )
                    filtered_out_items.extend(_page_removed)
                    _merge_count_map(filter_reason_counts, _page_removed_counts)
                else:
                    page_filtered_items = list(page_raw_items)
                raw_items.extend(page_raw_items)
                filtered_items.extend(page_filtered_items)
                pages_fetched = page_no
                if len(filtered_items) >= num_results:
                    break

        raw_items = _dedupe_search_items(raw_items)
        filtered_items = _dedupe_search_items(filtered_items)
        data = dict(data or {})
        data["results"] = filtered_items

        raw_results = raw_items
        unresponsive_engines = data.get("unresponsive_engines") or []
        engine_errors = data.get("errors") or []
        degraded = bool(unresponsive_engines) or bool(engine_errors)
        empty_result = len(filtered_items) == 0

        # 로컬 인스턴스에서 저하/빈결과 감지 시 → 다음 시도부터 원격으로 전환
        if used_endpoint == local_endpoint and (degraded or (empty_result and possible_throttle)):
            _local_degraded = True

        # 한국어 질의에서 naver 단독 무결과일 때는 1회 fallback 엔진으로 재시도한다.
        if (
            empty_result
            and _query_has_hangul
            and attempt == 0
            and fallback_engines
            and fallback_engines != primary_engines
            and max_retries > 0
        ):
            sleep_sec = max(0.05, backoff_ms / 1000.0)
            time.sleep(sleep_sec)
            continue
        if empty_result and retry_on_empty and attempt < max_retries:
            # 200 + 빈 결과가 연속될 때, 엔진 지연/차단 가능성을 고려해 짧게 재시도
            if degraded:
                possible_throttle = True
            if degraded or possible_throttle:
                sleep_sec = (backoff_ms / 1000.0) * (attempt + 1)
                time.sleep(sleep_sec)
                continue
        break

    raw_items = raw_items if 'raw_items' in locals() else list(data.get("results", []) or [])
    filtered_items = filtered_items if 'filtered_items' in locals() else list(data.get("results", []) or [])

    _unresponsive = data.get("unresponsive_engines") or []
    _engine_errors = data.get("errors") or []
    degraded = bool(_unresponsive) or bool(_engine_errors)
    headless_used = False
    headless_reason = ""
    headless_count = 0
    headless_blocked = False
    headless_error = ""
    direct_search_used = False
    direct_search_reason = ""
    direct_search_count = 0
    direct_search_held_candidates: List[Dict[str, Any]] = []
    direct_search_providers: List[str] = []
    direct_search_attempted_providers: List[str] = []
    direct_search_errors: List[str] = []

    fallback_reason = _headless_fallback_reason(
        request=request,
        filtered_items=filtered_items,
        raw_items=raw_items,
        filtered_out_items=filtered_out_items,
        filter_reason_counts=filter_reason_counts,
        degraded=degraded,
        possible_throttle=possible_throttle,
        num_results=num_results,
    )
    if fallback_reason:
        headless_reason = fallback_reason
        headless_payload = _call_headless_search(request.query, num_results, request.purpose)
        headless_blocked = bool(headless_payload.get("blocked"))
        headless_error = str(headless_payload.get("error") or "")
        headless_items = _normalize_headless_items(headless_payload, request.query, request.purpose)
        headless_count = len(headless_items)
        headless_used = True
        if headless_items:
            filtered_items = _dedupe_by_url(list(filtered_items or []) + headless_items)
            raw_items = _dedupe_by_url(list(raw_items or []) + headless_items)
        try:
            print(
                "[mcp-bridge] headless_google fallback: "
                f"reason={fallback_reason}, accepted={headless_count}, "
                f"blocked={headless_blocked}, error={headless_error[:120]}",
                file=sys.stderr,
                flush=True,
            )
        except Exception:
            pass

    direct_search_pre_raw_total = len(raw_items)
    direct_search_pre_accepted_total = len(filtered_items)
    direct_search_source_receipt_sha256 = ""
    if _env_bool("MCP_DIRECT_SEARCH_EXACT_TITLE_ONLY", False):
        if _purpose_key(request.purpose) == "official_title_verify":
            direct_search_source_receipt_sha256 = _run_direct_source_binding_digest(request)
        direct_reason = _run_exact_title_direct_fallback_reason(
            request,
            filtered_items=filtered_items,
            raw_items=raw_items,
            filtered_out_items=filtered_out_items,
        )
    else:
        direct_reason = _direct_search_fallback_reason(
            filtered_items=filtered_items,
            raw_items=raw_items,
            filtered_out_items=filtered_out_items,
            filter_reason_counts=filter_reason_counts,
            degraded=degraded,
            possible_throttle=possible_throttle,
            num_results=num_results,
        )
    if direct_reason:
        direct_search_reason = direct_reason
        direct_payload = _call_direct_search_fallback(request.query, num_results, request.purpose)
        direct_items = []
        for item in (direct_payload.get("results") or []):
            if not isinstance(item, dict):
                continue
            if _is_naver_original_product_id_url(str(item.get("url") or "")):
                direct_search_held_candidates.append({
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "source_url_original": item.get("source_url_original") or item.get("url"),
                    "engine": item.get("engine"),
                    "official_detail_verified": False,
                    "official_detail_verification_state": "hold_pending_normal_fetch_redirect",
                })
            else:
                direct_items.append(item)
        direct_search_count = len(direct_items)
        direct_search_providers = list(direct_payload.get("providers") or [])
        direct_search_attempted_providers = list(direct_payload.get("attempted_providers") or [])
        direct_search_errors = list(direct_payload.get("errors") or [])
        direct_search_used = True
        if direct_items:
            filtered_items = _dedupe_by_url(list(filtered_items or []) + direct_items)
            raw_items = _dedupe_by_url(list(raw_items or []) + direct_items)
        try:
            print(
                "[mcp-bridge] direct_search fallback: "
                f"reason={direct_reason}, accepted={direct_search_count}, "
                f"providers={direct_search_providers}, errors={direct_search_errors[:2]}",
                file=sys.stderr,
                flush=True,
            )
        except Exception:
            pass

    results: List[Dict[str, Any]] = []
    # 요청한 개수만큼만 반환 (SearXNG가 더 많이 반환할 수 있음)
    for item in filtered_items[:num_results]:
        result_item = {
            "title": item.get("title"),
            "url": item.get("url"),
            "content": item.get("content"),
            "engine": item.get("engine"),
        }
        if str(item.get("engine") or "").startswith("direct_"):
            result_item.update({
                "source_url_original": item.get("source_url_original") or item.get("url"),
                "official_detail_verified": False,
                "official_detail_verification_state": "hold_pending_normal_fetch_redirect",
            })
        results.append(result_item)
    fallback_recovered = bool((headless_used and headless_count > 0) or (direct_search_used and direct_search_count > 0))
    degraded_recovered = bool((degraded or possible_throttle) and fallback_recovered and results)
    return {
        "query": request.query,
        "results": results,
        "total": len(filtered_items),
        "raw_total": len(raw_items),
        "raw_preview": _build_search_preview_items(raw_items, limit=5),
        "filtered_preview": _build_search_preview_items(filtered_out_items, limit=5),
        "lang_filtered": max(0, len(raw_items) - len(filtered_items)),
        "lang_filter_reasons": filter_reason_counts,
        "attempts": attempts,
        "retry_count": max(0, attempts - 1),
        "pages_fetched": pages_fetched,
        "possible_throttle": possible_throttle,
        "degraded": degraded,
        "engines": (fallback_engines if attempts > 1 else primary_engines),
        "requested_language": default_language,
        "request_accept_language": headers.get("Accept-Language", ""),
        "provider_url": used_endpoint,
        "provider_candidates": endpoint_candidates,
        "unresponsive_engines": _unresponsive if isinstance(_unresponsive, list) else [],
        "engine_errors": _engine_errors if isinstance(_engine_errors, list) else retry_errors[-5:],
        "headless_used": headless_used,
        "headless_reason": headless_reason,
        "headless_count": headless_count,
        "headless_blocked": headless_blocked,
        "headless_error": headless_error,
        "fallback_recovered": fallback_recovered,
        "degraded_recovered": degraded_recovered,
        "direct_search_used": direct_search_used,
        "direct_search_binding_verified": bool(direct_search_source_receipt_sha256),
        "direct_search_source_receipt_sha256": direct_search_source_receipt_sha256,
        "direct_search_degraded_provider": direct_search_used,
        "direct_search_pre_raw_total": direct_search_pre_raw_total,
        "direct_search_pre_accepted_total": direct_search_pre_accepted_total,
        "direct_search_reason": direct_search_reason,
        "direct_search_count": direct_search_count,
        "direct_search_held_count": len(direct_search_held_candidates),
        "direct_search_held_candidates": direct_search_held_candidates[:num_results],
        "direct_search_providers": direct_search_providers,
        "direct_search_attempted_providers": direct_search_attempted_providers,
        "direct_search_errors": direct_search_errors,
    }


def _extract_domain(url: str) -> str:
    """URL에서 도메인 추출"""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        return parsed.hostname or ""
    except Exception:
        return ""


def _html_to_text(html: str, max_length: int = 0) -> str:
    """HTML → 순수 텍스트 추출 (경량, 외부 의존성 없음)
    
    max_length=0 이면 길이 제한 없음 (전문 반환).
    """
    # script, style 태그 제거
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<header[^>]*>.*?</header>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # 모든 HTML 태그 제거
    text = re.sub(r'<[^>]+>', ' ', text)
    # HTML 엔티티 디코딩
    import html as html_mod
    text = html_mod.unescape(text)
    # 연속 공백/개행 정리
    text = re.sub(r'\s+', ' ', text).strip()
    # 길이 제한 (max_length > 0 일 때만)
    if max_length > 0 and len(text) > max_length:
        text = text[:max_length]
    return text


# ---------------------------------------------------------------------------
# 마크다운 클리닝 — crawl4ai 반환 마크다운에서 LLM에 불필요한 요소 제거
# ---------------------------------------------------------------------------

def _clean_markdown_for_llm(md: str) -> str:
    """crawl4ai 마크다운에서 URL/이미지/네비게이션 노이즈를 제거하여 텍스트만 남긴다.

    나무위키 등 링크 밀도가 높은 페이지에서 233K→30~50K로 대폭 축소.
    LLM 컨텍스트 효율을 위해 의미 있는 텍스트만 보존한다.
    """
    if not md:
        return md
    import re as _re_cm

    # 1) 이미지 제거: ![alt](url) → (빈 문자열)
    md = _re_cm.sub(r'!\[[^\]]*\]\([^)]*\)', '', md)

    # 2) 하이퍼링크 → 텍스트만 보존: [텍스트](url) → 텍스트
    #    중첩 대괄호 처리: [[편집]](url) → [편집]
    md = _re_cm.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', md)
    # 나무위키 [[편집]](url) 잔여 처리 (2pass)
    md = _re_cm.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', md)

    # 3) 베어 URL 제거 (http/https로 시작하는 단독 URL)
    md = _re_cm.sub(r'https?://\S+', '', md)

    # 4) [편집] 같은 잔여 위키 액션 링크 텍스트 제거
    md = _re_cm.sub(r'\[편집\]', '', md)

    # 4) 빈 마크다운 헤더 제거 (# 만 남은 줄)
    md = _re_cm.sub(r'^#+\s*$', '', md, flags=_re_cm.MULTILINE)

    # 5) 연속 빈 줄 정리 (3줄 이상 → 2줄)
    md = _re_cm.sub(r'\n{3,}', '\n\n', md)

    # 6) 각 줄 앞뒤 공백 정리 + 빈 줄 최소화
    lines = md.split('\n')
    cleaned = []
    prev_empty = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if not prev_empty:
                cleaned.append('')
            prev_empty = True
        else:
            cleaned.append(stripped)
            prev_empty = False

    return '\n'.join(cleaned).strip()


# ---------------------------------------------------------------------------
# Crawl4AI 연동 — Playwright 기반 심층 크롤링 + 마크다운 변환
# ---------------------------------------------------------------------------

_MUNPIA_FANART_DETAIL_URL = re.compile(
    r"https://www\.munpia\.com/communities/novels-fanart/posts/[0-9]+\Z"
)
_MUNPIA_OFFICIAL_DETAIL_URL = re.compile(
    r"https://www\.munpia\.com/novel/detail/[0-9]+\Z"
)
_MAX_FANART_RAW_HTML_BYTES = 2 * 1024 * 1024


def _is_munpia_official_detail_shell(url: str, info: Dict[str, Any]) -> bool:
    """Identify the generic JS shell returned for an exact Munpia detail page."""
    return bool(
        _MUNPIA_OFFICIAL_DETAIL_URL.fullmatch(url)
        and str(info.get("title") or "").strip().casefold() == "novel - munpia"
        and not info.get("author")
        and info.get("content_status") in {None, "unavailable"}
    )


def _has_munpia_official_detail_content(info: Dict[str, Any]) -> bool:
    """Require a parsed work identity before accepting a shell retry."""
    return bool(
        info.get("page_type") == "novel_page"
        and info.get("content_status") == "active"
        and str(info.get("title") or "").strip()
        and str(info.get("title") or "").strip().casefold() != "novel - munpia"
        and str(info.get("author") or "").strip()
    )


def _fetch_transport_provenance(
    requested_url: str, final_url: Any, method: str, status_code: Any,
) -> Dict[str, Any]:
    """Expose the observed destination of one successful page fetch."""
    if not isinstance(final_url, str) or not final_url.strip():
        return {}
    if method not in {"crawl4ai", "httpx"}:
        return {}
    if type(status_code) is not int or not 200 <= status_code < 300:
        return {}
    requested = urlparse(requested_url)
    final = urlparse(final_url)
    if (requested.scheme not in {"http", "https"} or not requested.netloc
            or final.scheme not in {"http", "https"} or not final.netloc):
        return {}
    return {
        "final_url": final_url,
        "fetch_transport_provenance": {
            "requested_url": requested_url,
            "final_url": final_url,
            "method": method,
            "status_code": status_code,
            "redirected": final_url != requested_url,
        },
    }


def _munpia_official_detail_transport_receipt(
    requested_url: str, final_url: Any, method: str, status_code: Any,
) -> Dict[str, Any]:
    """Expose only transport provenance for one exact Munpia novel detail."""
    if not _MUNPIA_OFFICIAL_DETAIL_URL.fullmatch(requested_url):
        return {}
    if not isinstance(final_url, str) or final_url != requested_url:
        return {}
    if method not in {"crawl4ai", "httpx"}:
        return {}
    if type(status_code) is not int or not 200 <= status_code < 300:
        return {}
    return {"official_detail_transport_provenance": {
        "requested_url": requested_url,
        "final_url": final_url,
        "method": method,
        "status_code": status_code,
    }}


def _fanart_raw_html_receipt(
    requested_url: str, original_html: Any, final_url: Any,
    method: str, status_code: Any,
) -> Dict[str, Any]:
    """정확한 팬아트 상세 응답에 한해 원본 HTML의 후보 전송 영수증을 만든다."""
    if not _MUNPIA_FANART_DETAIL_URL.fullmatch(requested_url):
        return {}
    if not isinstance(final_url, str) or final_url != requested_url:
        return {}
    if type(status_code) is not int or not 200 <= status_code < 300:
        return {}
    if not isinstance(original_html, str) or not original_html:
        return {}
    try:
        encoded = original_html.encode("utf-8")
    except UnicodeEncodeError:
        return {}
    if len(encoded) > _MAX_FANART_RAW_HTML_BYTES:
        return {}
    return {
        "raw_html": original_html,
        "raw_html_sha256": hashlib.sha256(encoded).hexdigest(),
        "raw_html_provenance": {
            "requested_url": requested_url,
            "final_url": final_url,
            "method": method,
            "status_code": status_code,
        },
    }


def _crawl4ai_fetch(url: str, max_length: int = 0) -> Optional[Dict[str, Any]]:
    """Crawl4AI Docker 서비스를 호출하여 페이지 마크다운을 획득한다.

    max_length=0 이면 길이 제한 없음 (전문 반환).

    Returns:
        성공 시 markdown·기존 추출용 html과 원본 HTML·최종 URL·상태 metadata dict,
        실패 시 None.
    """
    crawl4ai_url = CRAWL4AI_URL.rstrip("/")

    # ── JS 헤비 사이트 감지: text_mode=False로 전환 + 추가 대기 ──
    _JS_HEAVY_DOMAINS = ("novelpia.com", "kakaopage.com", "page.kakao.com", "series.naver.com", "munpia.com")
    _is_js_heavy = any(d in url for d in _JS_HEAVY_DOMAINS)

    # ── wait_until 전략 ──
    # 현대 웹사이트 대부분은 광고/트래킹/웹소켓 등으로 networkidle에 도달 불가.
    # 기본값을 domcontentloaded로 하고, delay_before_return_html로 JS 렌더링 대기.
    _delay = 5 if _is_js_heavy else 3  # JS 헤비 사이트는 5초, 일반 3초

    # ── 1) /crawl 엔드포인트 호출 ──
    payload = {
        "urls": [url],
        "browser_config": {
            "type": "BrowserConfig",
            "params": {
                "headless": True,
                "text_mode": not _is_js_heavy,  # JS 헤비 사이트는 이미지 포함 렌더링
            },
        },
        "crawler_config": {
            "type": "CrawlerRunConfig",
            "params": {
                "cache_mode": "bypass",
                "exclude_external_links": True,
                "excluded_tags": ["nav", "footer", "header", "aside", "script", "style"],
                "word_count_threshold": 5,
                "page_timeout": 60000,
                "wait_until": "domcontentloaded",
                "delay_before_return_html": _delay,
            },
        },
    }

    try:
        resp = httpx.post(
            f"{crawl4ai_url}/crawl",
            json=payload,
            timeout=90.0 if _is_js_heavy else 60.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        try:
            print(
                f"[mcp-bridge][crawl4ai] /crawl request failed: {url} → {exc!r}",
                file=sys.stderr, flush=True,
            )
        except Exception:
            pass
        return None

    # ── 2) 응답 파싱 ──
    # Crawl4AI /crawl 은 결과를 results[] 배열로 반환한다.
    results = data if isinstance(data, list) else data.get("results", data.get("result", []))
    if isinstance(results, dict):
        results = [results]
    if not results:
        return None

    first = results[0] if isinstance(results, list) else results
    if not first.get("success", False):
        err_msg = first.get("error_message", "unknown")
        try:
            print(
                f"[mcp-bridge][crawl4ai] crawl unsuccessful: {url} → {err_msg}",
                file=sys.stderr, flush=True,
            )
        except Exception:
            pass
        return None

    # 마크다운 추출 — Crawl4AI 0.5.x+ 에서는 markdown이 dict일 수 있음
    md_field = first.get("markdown")
    markdown = ""
    if isinstance(md_field, dict):
        # fit_markdown > raw_markdown > markdown_with_citations 순으로 선호
        markdown = (
            md_field.get("fit_markdown")
            or md_field.get("raw_markdown")
            or md_field.get("markdown_with_citations")
            or ""
        )
    elif isinstance(md_field, str):
        markdown = md_field

    # 최상위 fit_markdown 필드도 확인 (구버전 호환)
    if not markdown:
        markdown = first.get("fit_markdown") or ""

    if not markdown:
        return None

    # 길이 제한 (max_length > 0 일 때만)
    if max_length > 0 and len(markdown) > max_length:
        markdown = markdown[:max_length]

    raw_html = first.get("html") or first.get("cleaned_html") or None

    try:
        print(
            f"[mcp-bridge][crawl4ai] success: {url}  md_len={len(markdown)}",
            file=sys.stderr, flush=True,
        )
    except Exception:
        pass

    return {
        "markdown": markdown,
        "html": raw_html,
        "original_html": first.get("html"),
        # CrawlResult.url is the requested URL; only redirected_url describes
        # the actual response destination. Missing destination fails closed.
        "final_url": first.get("redirected_url"),
        "status_code": first.get("status_code"),
    }


def _crawl4ai_health_ok() -> bool:
    """Crawl4AI 서비스가 살아있는지 빠르게 확인."""
    try:
        r = httpx.get(f"{CRAWL4AI_URL.rstrip('/')}/health", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False


def _extract_namu_wiki_info(html: str) -> Dict[str, Any]:
    """나무위키 페이지에서 작품 정보를 구조적으로 추출 (강화버전)"""
    info: Dict[str, Any] = {}
    info["page_type"] = "wiki"
    
    # 제목 추출 (h1.title 또는 document-title)
    title_match = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
    if title_match:
        raw_title = title_match.group(1)
        # " - 나무위키" 제거
        raw_title = re.sub(r'\s*[-–—]\s*나무위키\s*$', '', raw_title).strip()
        # 리비전 번호 제거: "(r173 판)" → ""
        raw_title = re.sub(r'\s*\(r\d+\s*판?\)\s*$', '', raw_title).strip()
        info["page_title"] = raw_title
    
    text = _html_to_text(html)  # 전문 추출 (길이 제한 없음)
    
    # ── 약칭 패턴 (5종으로 확대) ──
    _abbreviations: List[str] = []
    _abbrev_patterns = [
        # "약칭은 X", "약칭은 X 또는 Y"
        re.compile(r'약칭(?:은|으로)\s+([^\s,.]+(?:\s+또는\s+[^\s,.]+)*)'),
        # "줄여서 X라고", "줄여서 X로"
        re.compile(r'줄여서\s+([가-힣A-Za-z0-9]{2,10})(?:라고|로|이라)'),
        # "통칭 X", "통상 X"
        re.compile(r'(?:통칭|통상)\s+([가-힣A-Za-z0-9]{2,10})'),
        # "약칭: X" / "약칭 : X"
        re.compile(r'약칭\s*[:：]\s*([가-힣A-Za-z0-9]{2,10})'),
        # "(약칭 X)"
        re.compile(r'\(약칭\s+([가-힣A-Za-z0-9]{2,10})\)'),
    ]
    for pat in _abbrev_patterns:
        for m in pat.finditer(text[:3000]):
            for part in m.group(1).split("또는"):
                a = part.strip()
                if a and len(a) >= 2 and a not in _abbreviations:
                    _abbreviations.append(a)
    if _abbreviations:
        info["abbreviations"] = _abbreviations
    
    # ── 작가 패턴 (확대) ──
    _author_patterns = [
        re.compile(r"['\"]?([가-힣A-Za-z0-9_]{2,20})['\"]?\s*작가의"),
        re.compile(r'작가(?:는|명)\s+["\']?([가-힣A-Za-z0-9_]{2,20})'),
        re.compile(r'(?:글|원작)\s*[:：]?\s*["\']?([가-힣A-Za-z0-9_]{2,20})["\']?\s*(?:\||$|\n)'),
        re.compile(r'(?:저자|필자|작성자)\s*[:：]?\s*["\']?([가-힣A-Za-z0-9_]{2,20})'),
    ]
    for pat in _author_patterns:
        m = pat.search(text[:3000])
        if m:
            author_cand = m.group(1).strip()
            if author_cand and len(author_cand) >= 2 and author_cand not in (
                "작가", "작품", "소설", "웹소설", "원작", "글작가"
            ):
                info["author"] = author_cand
                break
    
    # ── 장르 패턴 ──
    genre_match = re.search(r'(?:장르|분류)\s*[:\s]\s*([^\n.]{3,40})', text)
    if genre_match:
        info["genre"] = genre_match.group(1).strip()
    
    # ── 연재 상태 ──
    for status_kw, status_val in [
        ("완결", "completed"), ("연재중", "ongoing"), ("연재 중", "ongoing"),
        ("휴재", "hiatus"), ("휴재중", "hiatus"),
    ]:
        if status_kw in text[:2000]:
            info["serialization_status"] = status_val
            break
    
    # ── 연재 플랫폼 ──
    for platform in ("노벨피아", "문피아", "카카오페이지", "네이버 시리즈", "조아라", "리디북스"):
        if platform in text:
            info.setdefault("platforms", []).append(platform)
    
    # ── 등장인물 추출 (나무위키 '등장인물' 섹션) ──
    _characters: List[str] = []
    # 패턴1: "등장인물" 섹션 이후 이름 패턴
    char_section = re.search(r'등장인물|등장\s*캐릭터|주요\s*인물', text)
    if char_section:
        char_text = text[char_section.end():char_section.end() + 1500]
        # 한국 이름 패턴: 2-4글자 한글 이름
        char_names = re.findall(
            r'(?:^|\n|\s)([가-힣]{2,4})(?:\s*[-:·]|\s*\()',
            char_text
        )
        for cn in char_names[:15]:
            cn = cn.strip()
            if cn and len(cn) >= 2 and cn not in _characters:
                # 일반 명사 제외
                if cn not in ("등장인물", "주인공", "히로인", "조연", "악역", "주요인물",
                              "보스몹", "사이드", "서브히로인"):
                    _characters.append(cn)
    if _characters:
        info["characters"] = _characters[:10]
    
    # ── 화수 정보 ──
    ep_match = re.search(r'(?:총\s*)?([\d,]+)\s*(?:화|회|편|장)', text[:2000])
    if ep_match:
        try:
            info["episode_count"] = int(ep_match.group(1).replace(",", ""))
        except ValueError:
            pass
    
    info["text_preview"] = text  # 전문 반환 (길이 제한 제거)
    return info


def _mine_novel_title_from_community(text: str) -> Optional[str]:
    """커뮤니티 게시글 본문에서 실제 소설 제목을 채굴한다.

    패턴 예시:
      - "망겜의 성기사 읽고 있는데"
      - "〇〇이라는 소설 추천"
      - "〇〇 연재중인데"
      - "[〇〇] 감상"
    """
    if not text:
        return None

    _patterns = [
        # "〇〇 읽고 있는데 / 읽었는데 / 읽는중"
        re.compile(
            r'["\']?([가-힣A-Za-z0-9][가-힣A-Za-z0-9\s]{2,30}?)["\']?\s*'
            r'(?:읽고\s*있|읽었|읽는\s*중|정주행|보고\s*있|봤는데)',
        ),
        # "〇〇이라는/라는 소설/작품"
        re.compile(
            r'["\']?([가-힣A-Za-z0-9][가-힣A-Za-z0-9\s]{2,30}?)["\']?\s*'
            r'(?:이라는|라는)\s*(?:소설|작품|웹소설)',
        ),
        # "〇〇 추천 / 〇〇 소설 추천"
        re.compile(
            r'["\']?([가-힣A-Za-z0-9][가-힣A-Za-z0-9\s]{2,30}?)["\']?\s*'
            r'(?:소설\s*)?(?:추천합니다|추천드|추천함|강추)',
        ),
        # "〇〇 연재중 / 완결"
        re.compile(
            r'["\']?([가-힣A-Za-z0-9][가-힣A-Za-z0-9\s]{2,30}?)["\']?\s*'
            r'(?:연재중|연재\s*중|완결|휴재)',
        ),
        # "[〇〇] 또는 <〇〇> 형태"
        re.compile(
            r'[\[<「『]([가-힣A-Za-z0-9][가-힣A-Za-z0-9\s]{2,30}?)[\]>」』]',
        ),
    ]

    # 텍스트 상위 1500자에서 탐색
    search_text = text[:1500]
    _GENERIC = {
        "이", "그", "저", "이거", "그거", "저거", "뭐", "어떤", "무슨",
        "이건", "그건", "요즘", "최근", "다른", "비슷한", "같은",
    }
    for pat in _patterns:
        m = pat.search(search_text)
        if m:
            candidate = m.group(1).strip()
            # 일반어/대명사 필터
            if candidate and len(candidate) >= 3 and candidate not in _GENERIC:
                return candidate
    return None


def _classify_platform_page_type(url: str, html: str) -> str:
    """플랫폼 URL + HTML 구조로 페이지 유형을 분류한다.

    Returns:
        "novel_page"      - 작품 메인/뷰어 페이지 (제목·작가 신뢰 가능)
        "community_post"  - 독자 커뮤니티/게시판 글 (제목은 게시글 제목, 소설 제목 아님)
        "search_page"     - 검색 결과 페이지
        "unknown"         - 분류 불가
    """
    url_lower = (url or "").lower()

    # ── 문피아 커뮤니티 (독자마당 / 자유게시판) ──
    if "square.munpia.com" in url_lower:
        return "community_post"
    if re.search(r"munpia\.com/(?:board|community|forum|square|free)", url_lower):
        return "community_post"

    # ── 노벨피아 커뮤니티 ──
    if re.search(r"novelpia\.com/(?:freeboard|forum|community|board|arena)", url_lower):
        return "community_post"
    # 노벨피아 뷰어 = 작품 페이지
    if re.search(r"novelpia\.com/(?:novel|viewer)", url_lower):
        return "novel_page"

    # ── 문피아 소설 페이지 ──
    if re.search(r"munpia\.com/(?:novel|book|page)", url_lower):
        return "novel_page"

    # ── 카카오/네이버/조아라/리디 ──
    if re.search(r"(?:kakaopage|page\.kakao|series\.naver|joara|ridibooks)\.com", url_lower):
        return "novel_page"

    # ── HTML 기반 보조 판정 (URL로 구분 불가 시) ──
    if html:
        html_lower = html[:5000].lower()
        # 커뮤니티 시그널: 댓글 입력란, 게시판 네비게이션 등
        _community_signals = (
            "글쓰기", "댓글 작성", "게시판", "추천하기", "비추천",
            "comment-write", "reply-form", "board-list",
        )
        _novel_signals = (
            "연재중", "작가:", "총 화", "이어보기", "첫화보기",
            "novel-info", "author-name", "episode-list",
        )
        community_score = sum(1 for s in _community_signals if s in html_lower)
        novel_score = sum(1 for s in _novel_signals if s in html_lower)
        if community_score >= 2 and community_score > novel_score:
            return "community_post"
        if novel_score >= 2 and novel_score > community_score:
            return "novel_page"

    return "unknown"


def _is_munpia_canvas_viewer(url: str, html: str) -> bool:
    parsed = urlparse(url)
    if (
        (parsed.hostname or "").lower() not in {"munpia.com", "www.munpia.com"}
        or not re.fullmatch(r"/novel/viewer/\d+/\d+/?", parsed.path)
        or "_scrollCanvas_" not in (html or "")
    ):
        return False
    # A real HTML body can coexist with layout canvases. Only visible body
    # candidates outside comments/recommendations should disable the guard.
    class _HtmlEpisodeBodyProbe(HTMLParser):
        _void_tags = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

        def __init__(self) -> None:
            super().__init__()
            self.stack: List[tuple[str, str]] = []
            self.has_body = False

        def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
            if tag not in self._void_tags:
                values = dict(attrs)
                marker = f"{values.get('id') or ''} {values.get('class') or ''}".lower()
                self.stack.append((tag, marker))

        def handle_endtag(self, tag: str) -> None:
            for index in range(len(self.stack) - 1, -1, -1):
                if self.stack[index][0] == tag:
                    del self.stack[index:]
                    break

        def handle_data(self, data: str) -> None:
            if not data.strip() or any(tag in {"script", "style", "template"} for tag, _ in self.stack):
                return
            markers = [marker for _, marker in self.stack]
            if any(
                any(token in marker for token in (
                    "_comment", "_recommend", "_endpage", "_footer", "_toolbar", "_sidebar", "_tutorial",
                ))
                for marker in markers
            ):
                return
            explicit_body = any(
                re.search(r"(?:chapter|episode|novel|story|reader)[-_ ]?(?:body|content|text)", marker)
                for marker in markers
            )
            in_viewer_section = any(
                "_viewersec" in marker or "_contentarea" in marker
                for marker in markers
            )
            in_article = any(tag == "article" for tag, _ in self.stack)
            if explicit_body or (in_article and in_viewer_section):
                self.has_body = True

    html_body_probe = _HtmlEpisodeBodyProbe()
    html_body_probe.feed(html)
    if html_body_probe.has_body:
        return False

    class _ScrollSpacerProbe(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.depth = 0
            self.spacer_count = 0
            self.canvas_count = 0
            self.has_text = False
            self.end_page_depth = 0
            self.ignored_depth = 0

        def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
            if self.ignored_depth:
                if tag in {"script", "style", "template"}:
                    self.ignored_depth += 1
                return
            if self.depth and tag in {"script", "style", "template"}:
                self.ignored_depth = 1
                return
            classes = str(dict(attrs).get("class") or "").split()
            if tag == "div" and self.depth == 0 and any(
                value.startswith("_scrollSpacer_") for value in classes
            ):
                self.depth = 1
                self.spacer_count += 1
            elif self.depth:
                if tag == "div":
                    self.depth += 1
                    if any(value.startswith("_endPageScrollWrapper_") for value in classes):
                        self.end_page_depth = self.depth
                elif tag == "canvas" and any(
                    value.startswith("_scrollCanvas_") for value in classes
                ):
                    self.canvas_count += 1

        def handle_endtag(self, tag: str) -> None:
            if self.ignored_depth:
                if tag in {"script", "style", "template"}:
                    self.ignored_depth -= 1
                return
            if tag == "div" and self.depth:
                if self.depth == self.end_page_depth:
                    self.end_page_depth = 0
                self.depth -= 1

        def handle_data(self, data: str) -> None:
            if self.depth and not self.end_page_depth and not self.ignored_depth and data.strip():
                self.has_text = True

    probe = _ScrollSpacerProbe()
    probe.feed(html)
    return probe.spacer_count == 1 and probe.canvas_count > 0 and not probe.has_text


def _sanitize_munpia_canvas_viewer_text(
    url: str, html: str, text: str, structured_info: Dict[str, Any],
) -> tuple[str, Dict[str, Any]]:
    """Keep a canvas viewer's reader comments out of official episode evidence."""
    if not _is_munpia_canvas_viewer(url, html):
        return text, structured_info

    # The episode is drawn on canvas. HTML/Markdown can still contain reader
    # comments, recommendations, and navigation; none is episode body text.
    safe_info = {
        key: value for key, value in structured_info.items()
        if key in {"title", "page_type", "content_status", "fetch_method"}
    }
    safe_info["reader_body_extraction"] = "canvas_not_extracted"
    safe_info["reader_comments_excluded"] = True
    safe_text = f"회차 페이지 제목: {safe_info['title']}" if safe_info.get("title") else ""
    safe_info["text_preview"] = safe_text
    return safe_text, safe_info


def _munpia_detail_author_from_page(
    html: str, url: str, title: str, *, return_claims: bool = False,
) -> Any:
    """기존 현대형 HTML 판독을 캐시 proof 재검산과 같은 구현으로 공유한다."""
    from ..grounding.munpia_author_byline import _munpia_detail_author_from_page as read_author
    return read_author(html, url, title, return_claims=return_claims)


def _munpia_rendered_header_author(
    url: str, info: Dict[str, Any], rendered_text: str, raw_html: str,
    transport_receipt: Dict[str, Any],
) -> Optional[str]:
    """Read a missing byline only beside the first exact work heading in rendered text."""
    provenance = transport_receipt.get("official_detail_transport_provenance")
    if not isinstance(provenance, dict) or provenance.get("method") != "crawl4ai":
        return None
    if not _MUNPIA_OFFICIAL_DETAIL_URL.fullmatch(url):
        return None
    if (provenance.get("requested_url") != url or provenance.get("final_url") != url
            or type(provenance.get("status_code")) is not int
            or not 200 <= provenance["status_code"] < 300):
        return None
    if info.get("page_type") != "novel_page" or info.get("content_status") != "active":
        return None
    if str(info.get("author") or "").strip():
        return None
    title = str(info.get("title") or "").strip()
    if not title or title.casefold() == "novel - munpia":
        return None
    # A conflicting title-bound HTML field is an ambiguity, not permission to
    # replace it with the rendered byline.
    if raw_html and _munpia_detail_author_from_page(
        raw_html, url, title, return_claims=True,
    ):
        return None
    lines = [line.strip() for line in str(rendered_text or "").splitlines()]
    heading_at = next((i for i, line in enumerate(lines) if re.match(r"^#\s+\S", line)), None)
    if heading_at is None:
        return None
    heading = re.sub(r"^#\s+", "", lines[heading_at]).strip()
    if heading.casefold() != title.casefold():
        return None
    header = [line for line in lines[heading_at + 1:heading_at + 6] if line]
    if len(header) < 3 or header[0] != "글":
        return None
    author = header[1].strip()
    if not re.fullmatch(r"[가-힣A-Za-z0-9_·]{2,30}", author):
        return None
    if author in {"작가", "작가명", "원작", "글작가", "unknown"}:
        return None
    if not re.match(r"^(?:총\s*\d+\s*화|연재|조회수|좋아요|선호작|글자수|작품등록일)", header[2]):
        return None
    return author


def _extract_novel_platform_info(html: str, url: str) -> Dict[str, Any]:
    """노벨피아/문피아 등 공식 플랫폼 페이지에서 정보 추출"""
    info: Dict[str, Any] = {}

    # ── page_type 분류 (커뮤니티 vs 소설 페이지) ──
    page_type = _classify_platform_page_type(url, html)
    info["page_type"] = page_type
    
    # <title> 태그에서 제목 추출
    title_match = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
    if title_match:
        raw_title = title_match.group(1).strip()
        # 플랫폼 접미사 제거
        for suffix in (" - 노벨피아", " - 웹소설로 꿈꾸는 세상!", " - 문피아 웹소설", " - 문피아",
                        " | 카카오페이지", " - 네이버 시리즈"):
            if raw_title.endswith(suffix):
                raw_title = raw_title[:-len(suffix)].strip()
        # 플랫폼 접두사 제거 (예: "노벨피아 - 웹소설로 꿈꾸는 세상! - 작품명")
        for prefix in ("노벨피아 - 웹소설로 꿈꾸는 세상! - ",
                        "노벨피아 - ", "문피아 - "):
            if raw_title.startswith(prefix):
                raw_title = raw_title[len(prefix):].strip()
        info["title"] = raw_title

        # 커뮤니티 글이면 title을 page_title(게시글 제목)로 저장하고 title 제거
        if page_type == "community_post":
            info["page_title"] = raw_title
            info.pop("title", None)
    
    text = _html_to_text(html)  # 전문 추출 (길이 제한 없음)

    # ── Phase 34: 삭제/비공개/미존재 작품 감지 ──
    # crawl4ai로 실제 페이지를 방문했을 때, 삭제된 소설인지 콘텐츠 기반 검증
    _content_status = "active"  # 기본값: 정상
    if page_type in ("novel_page", "unknown") or not text or len(text.strip()) < 80:
        _deleted_patterns = [
            r"삭제된\s*작품", r"작품이?\s*삭제", r"해당\s*작품은?\s*삭제",
            r"존재하지\s*않는\s*(?:작품|페이지|소설)",
            r"찾을\s*수\s*없(?:습니다|는)", r"접근할\s*수\s*없",
            r"비공개\s*(?:처리|작품|된)", r"작품을?\s*비공개",
            r"서비스가?\s*종료", r"연재\s*(?:중단|취소)",
            r"삭제\s*(?:되었습니다|됐습니다|됨)",
            r"해당\s*(?:페이지|콘텐츠)(?:를?|는?)\s*(?:찾을|존재|확인)",
            r"This\s+(?:novel|work|page)\s+(?:has been|is)\s+(?:deleted|removed)",
            r"페이지를?\s*찾을\s*수\s*없",
            r"요청하신\s*페이지",
        ]
        _check_text = (text or "")[:1500].lower() + " " + html[:3000].lower()
        for _dp in _deleted_patterns:
            if re.search(_dp, _check_text, re.IGNORECASE):
                _content_status = "deleted"
                break
        # 추가: 본문이 극히 짧으면(소설페이지인데 80자 미만) unavailable 의심
        if _content_status == "active" and page_type == "novel_page":
            _stripped = (text or "").strip()
            if len(_stripped) < 80 and not _is_munpia_canvas_viewer(url, html):
                _content_status = "unavailable"
    info["content_status"] = _content_status
    if _content_status != "active":
        try:
            print(
                f"[mcp-bridge] ⚠️ content_status={_content_status}: {url}",
                file=sys.stderr, flush=True,
            )
        except Exception:
            pass

    # ── 커뮤니티 게시글이면 본문에서 실제 소설 제목 마이닝 ──
    if page_type == "community_post" and text:
        _novel_title_from_community = _mine_novel_title_from_community(text)
        if _novel_title_from_community:
            info["mined_novel_title"] = _novel_title_from_community
            try:
                print(
                    f"[mcp-bridge] 📌 community→novel title mined: "
                    f"'{_novel_title_from_community}' from {url}",
                    file=sys.stderr, flush=True,
                )
            except Exception:
                pass
    
    # 작가명 추출 (플랫폼별 표기 편차 대응)
    def _clean_author_name(name: str) -> str:
        import html as _html

        cleaned = _html.unescape(str(name or "")).strip()
        cleaned = re.sub(r"[\s\u00A0]+", " ", cleaned)
        cleaned = cleaned.strip(" \"'|[]()")
        # 구분자 이후 꼬리 제거
        cleaned = re.split(r"[|,/·•\-]", cleaned)[0].strip()
        if len(cleaned) < 2 or len(cleaned) > 30:
            return ""
        if cleaned in {"작가", "작가명", "원작", "글작가", "unknown"}:
            return ""
        return cleaned

    from ..grounding.munpia_author_byline import is_legacy_munpia_author_detail, is_munpia_author_detail, byline_evidence
    author_candidates: List[str] = []
    legacy_munpia_author_detail = is_legacy_munpia_author_detail(url)
    if is_munpia_author_detail(url):
        author_proof = byline_evidence(url, str(info.get("title") or ""), html, kind="html")
        if author_proof is not None:
            info["author_byline"] = author_proof
            if author_proof["status"] == "VERIFIED":
                info["author"] = author_proof["name"]
    munpia_detail = bool(_MUNPIA_OFFICIAL_DETAIL_URL.fullmatch(url)) or legacy_munpia_author_detail
    if munpia_detail and page_type == "novel_page":
        author = _munpia_detail_author_from_page(html, url, str(info.get("title") or ""))
        if author:
            info["author"] = author

    # 1) 텍스트 기반 패턴
    text_patterns = [
        r"(?:작가명|작가|글작가|원작)\s*[:：]?\s*[\"']?([가-힣A-Za-z0-9_]{2,30})",
        r"[\"']?([가-힣A-Za-z0-9_]{2,30})[\"']?\s*(?:작가의|작가님의)",
    ]
    if not munpia_detail:
        for pat in text_patterns:
            for m in re.finditer(pat, text):
                cand = _clean_author_name(m.group(1))
                if cand:
                    author_candidates.append(cand)

    # 2) HTML 메타/JSON-LD 기반 패턴
    html_patterns = [
        r'<meta[^>]+(?:name|property)=["\']author["\'][^>]+content=["\']([^"\']{2,60})["\']',
        r'"authorName"\s*:\s*"([^"]{2,60})"',
        r'"author"\s*:\s*\{[^{}]{0,300}?"name"\s*:\s*"([^"]{2,60})"',
        r'"writer"\s*:\s*"([^"]{2,60})"',
    ]
    if not munpia_detail:
        for pat in html_patterns:
            for m in re.finditer(pat, html, re.IGNORECASE):
                cand = _clean_author_name(m.group(1))
                if cand:
                    author_candidates.append(cand)

    # 중복 제거 후 첫 후보 채택
    seen_authors = set()
    deduped_authors: List[str] = []
    for cand in author_candidates:
        key = cand.lower()
        if key in seen_authors:
            continue
        seen_authors.add(key)
        deduped_authors.append(cand)
    if deduped_authors:
        info["author"] = deduped_authors[0]
    
    # 장르/태그 추출
    tags = re.findall(r'#([가-힣A-Za-z]+)', text)
    if tags:
        info["tags"] = tags[:10]
    
    # ── 장르 메타태그 추출 ──
    genre_meta = re.findall(
        r'(?:장르|분류|카테고리)\s*[:：]?\s*([가-힣A-Za-z/,·\s]{2,40})',
        text[:1000]
    )
    if genre_meta:
        info["genre"] = genre_meta[0].strip()
    
    # ── 연재 상태 추출 ──
    for status_kw, status_val in [
        ("완결", "completed"), ("연재중", "ongoing"), ("연재 중", "ongoing"),
        ("휴재", "hiatus"),
    ]:
        if status_kw in text[:1500]:
            info["serialization_status"] = status_val
            break
    
    # ── 화수/편수 추출 ──
    ep_match = re.search(r'(?:총\s*)?([\d,]+)\s*(?:화|회|편|장)', text[:1500])
    if ep_match:
        try:
            info["episode_count"] = int(ep_match.group(1).replace(",", ""))
        except ValueError:
            pass
    
    # ── HTML에서 JSON-LD 장르/태그 추가 추출 ──
    for m in re.finditer(r'"genre"\s*:\s*"([^"]{2,40})"', html[:5000], re.IGNORECASE):
        if "genre" not in info:
            info["genre"] = m.group(1).strip()
    for m in re.finditer(r'"keywords"\s*:\s*"([^"]{2,100})"', html[:5000], re.IGNORECASE):
        kw_list = [k.strip() for k in m.group(1).split(",") if k.strip()]
        info.setdefault("tags", []).extend(kw_list[:10])
        break
    
    info["text_preview"] = text  # 전문 반환 (길이 제한 제거)
    return info


def _searxng_site_fallback(url: str, domain: str, max_length: int) -> Optional[Dict[str, Any]]:
    """직접 fetch 실패 시 SearXNG site: 검색으로 대체 콘텐츠를 획득한다.
    
    검색엔진(Google/Bing 등)이 이미 크롤링한 내용을 SearXNG가 중계하므로,
    사이트가 봇을 차단하더라도 검색엔진 캐시에서 콘텐츠를 가져올 수 있다.
    """
    from urllib.parse import urlparse, unquote
    try:
        parsed = urlparse(url)
        # URL 경로에서 키워드 추출 (숫자 ID, 슬래시 제거 → 의미 있는 토큰)
        path_parts = [unquote(p) for p in parsed.path.strip("/").split("/") if p]
        # 쿼리 구성: "site:domain path_keyword1 path_keyword2"
        # 경로가 너무 길면 마지막 2개만 (보통 게시판/게시글 ID)
        path_keywords = " ".join(path_parts[-2:]) if len(path_parts) > 2 else " ".join(path_parts)
        query = f"site:{domain} {path_keywords}".strip()

        params = {"q": query, "format": "json", "safesearch": "0", "pageno": "1"}
        headers = {
            "User-Agent": "llm-batch/0.1 (+mcp-bridge)",
            "X-Forwarded-For": "127.0.0.1",
            "X-Real-IP": "127.0.0.1",
            "X-Forwarded-Proto": "http",
        }
        resp = httpx.get(
            f"{SEARCHXNG_URL.rstrip('/')}/search",
            params=params, headers=headers, timeout=15.0,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return None

        # 원본 URL과 가장 가까운 결과를 우선 선택
        best = results[0]
        for r in results[:5]:
            if r.get("url", "").rstrip("/") == url.rstrip("/"):
                best = r
                break

        # 여러 검색 결과의 content를 합쳐서 최대한 정보를 확보
        combined_texts: List[str] = []
        for r in results[:5]:
            c = (r.get("content") or "").strip()
            if c and c not in combined_texts:
                combined_texts.append(c)
        fallback_text = " | ".join(combined_texts)
        # searxng fallback도 길이 제한 없이 전문 반환
        # (max_length > 0 일 때만 잘라줌)
        if max_length > 0 and len(fallback_text) > max_length:
            fallback_text = fallback_text[:max_length]

        structured_info: Dict[str, Any] = {}
        if best.get("title"):
            structured_info["title"] = best["title"]
        structured_info["fallback_source"] = "searxng_site_search"
        structured_info["fallback_query"] = query
        structured_info["fallback_result_count"] = len(results)

        return {
            "url": url,
            "domain": domain,
            "text": fallback_text,
            "structured_info": structured_info,
            "fallback": True,
        }
    except Exception as exc:
        try:
            print(f"[mcp-bridge] searxng fallback also failed: {url} → {exc!r}",
                  file=sys.stderr, flush=True)
        except Exception:
            pass
        return None


@app.post("/mcp/fetch")
def mcp_fetch(request: FetchRequest) -> Dict[str, Any]:
    """URL의 웹 페이지를 가져와서 텍스트를 추출하여 반환한다.

    크롤링 우선 순위:
      1) Crawl4AI (Playwright 기반 심층 크롤링 + 마크다운 변환)
      2) httpx 직접 fetch + regex 텍스트 추출  (Crawl4AI 다운 시)
      3) SearXNG site: 검색 fallback       (위 모두 실패 시)

    웹소설 관련 공식/커뮤니티 도메인만 허용하여 악용 방지.
    나무위키, 노벨피아, 문피아 등의 페이지에서 작품 정보를 구조적으로 추출.
    """
    url = request.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="url is required")

    # 도메인 허용 체크
    domain = _extract_domain(url)
    is_allowed = any(domain == d or domain.endswith("." + d) for d in _ALLOWED_FETCH_DOMAINS)
    # tistory 서브도메인 허용 (xxx.tistory.com)
    if not is_allowed and domain and domain.endswith(".tistory.com"):
        is_allowed = True
    if not is_allowed:
        # 허용 도메인이 아니어도 SearXNG 캐시 기반 fallback은 시도한다.
        fallback_result = _searxng_site_fallback(url, domain, request.max_length)
        if fallback_result is not None:
            fallback_result["restricted_domain"] = True
            fallback_result["direct_fetch_error"] = "domain_not_allowed"
            try:
                print(
                    f"[mcp-bridge] restricted domain fallback success: {url}",
                    file=sys.stderr, flush=True,
                )
            except Exception:
                pass
            return fallback_result
        raise HTTPException(
            status_code=403,
            detail=f"Domain '{domain}' is not in the allowed list for fetching",
        )

    # ── 1단계: Crawl4AI 심층 크롤링 시도 ──
    crawl4ai_result = _crawl4ai_fetch(url)  # 길이 제한 없이 전문 크롤링
    crawl4ai_shell_result: Optional[Dict[str, Any]] = None
    if crawl4ai_result is not None:
        markdown_text = crawl4ai_result["markdown"]
        raw_html = crawl4ai_result.get("html")

        # 구조적 정보 추출 — Crawl4AI가 반환한 HTML이 있으면 기존 추출기를 재활용
        structured_info: Dict[str, Any] = {}
        if raw_html:
            if "namu.wiki" in domain:
                structured_info = _extract_namu_wiki_info(raw_html)
            elif any(p in domain for p in ("novelpia", "munpia", "kakaopage", "series.naver", "joara")):
                structured_info = _extract_novel_platform_info(raw_html, url)
            else:
                title_match = re.search(r'<title>([^<]+)</title>', raw_html, re.IGNORECASE)
                if title_match:
                    structured_info["title"] = title_match.group(1).strip()
                # 커뮤니티 도메인이면 page_type 설정
                _community_domains = ("dcinside", "fmkorea", "ruliweb", "arca.live", "teamblind")
                if any(cd in domain for cd in _community_domains):
                    structured_info["page_type"] = "community_post"
                    # 커뮤니티 본문에서 소설 제목 마이닝
                    _comm_text = _html_to_text(raw_html)  # 전문 추출
                    _mined = _mine_novel_title_from_community(_comm_text)
                    if _mined:
                        structured_info["mined_novel_title"] = _mined
                elif any(bd in domain for bd in ("tistory", "blog.naver", "brunch")):
                    structured_info["page_type"] = "blog"
                else:
                    structured_info["page_type"] = "unknown"
        else:
            # HTML 없으면 마크다운 첫 줄에서 제목 추출 시도
            first_line = (markdown_text.split("\n", 1)[0] or "").strip().lstrip("# ").strip()
            if first_line:
                structured_info["title"] = first_line

        structured_info["fetch_method"] = "crawl4ai"

        # 최종 텍스트 — 마크다운 클리닝 후 반환 (URL/이미지 노이즈 제거)
        final_text = _clean_markdown_for_llm(markdown_text)
        final_text, structured_info = _sanitize_munpia_canvas_viewer_text(
            url, raw_html or "", final_text, structured_info,
        )
        transport_receipt = _munpia_official_detail_transport_receipt(
            url, crawl4ai_result.get("final_url"), "crawl4ai",
            crawl4ai_result.get("status_code"),
        )
        if not structured_info.get("author"):
            rendered_author = _munpia_rendered_header_author(
                url, structured_info, final_text, raw_html or "", transport_receipt,
            )
            if rendered_author:
                structured_info["author"] = rendered_author

        crawl_result = {
            "url": url,
            "domain": domain,
            "text": final_text,
            "structured_info": structured_info,
            **_fetch_transport_provenance(
                url, crawl4ai_result.get("final_url"), "crawl4ai",
                crawl4ai_result.get("status_code"),
            ),
            **_fanart_raw_html_receipt(
                url, crawl4ai_result.get("original_html"),
                crawl4ai_result.get("final_url"), "crawl4ai",
                crawl4ai_result.get("status_code"),
            ),
            **transport_receipt,
        }
        if _is_munpia_official_detail_shell(url, structured_info):
            crawl4ai_shell_result = crawl_result
        else:
            return crawl_result

    # ── 2단계: httpx 직접 fetch (기존 경량 경로) ──
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    fetch_error: Optional[str] = None
    html: Optional[str] = None
    direct_response: Optional[httpx.Response] = None

    try:
        response = httpx.get(url, headers=headers, timeout=15.0, follow_redirects=True)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type or "application/xhtml" in content_type:
            html = response.text
            direct_response = response
        else:
            fetch_error = f"Not HTML content: {content_type}"
    except httpx.HTTPError as exc:
        fetch_error = str(exc)
        try:
            print(
                f"[mcp-bridge] direct fetch failed, trying searxng fallback: {url} → {exc!r}",
                file=sys.stderr, flush=True,
            )
        except Exception:
            pass

    # ── 3단계: 직접 fetch 실패 → SearXNG site: 검색 fallback ──
    if html is None:
        if crawl4ai_shell_result is not None:
            return crawl4ai_shell_result
        fallback_result = _searxng_site_fallback(url, domain, request.max_length)
        if fallback_result is not None:
            fallback_result["direct_fetch_error"] = fetch_error
            return fallback_result
        raise HTTPException(
            status_code=502,
            detail=f"Fetch failed (crawl4ai + direct + searxng fallback): {fetch_error}",
        )

    # ── httpx 성공 → 기존 텍스트 추출 로직 ──
    structured_info_httpx: Dict[str, Any] = {}
    if "namu.wiki" in domain:
        structured_info_httpx = _extract_namu_wiki_info(html)
    elif any(p in domain for p in ("novelpia", "munpia", "kakaopage", "series.naver", "joara")):
        structured_info_httpx = _extract_novel_platform_info(html, url)
    else:
        title_match = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
        if title_match:
            structured_info_httpx["title"] = title_match.group(1).strip()

    if _is_munpia_official_detail_shell(url, structured_info_httpx):
        # Munpia serves this 200 shell for a spoofed Chrome UA. The default
        # httpx UA currently receives the work page; retry this exact route once.
        retry_headers = {k: v for k, v in headers.items() if k.lower() != "user-agent"}
        try:
            retry_response = httpx.get(
                url, headers=retry_headers, timeout=15.0, follow_redirects=True,
            )
            retry_response.raise_for_status()
            retry_content_type = retry_response.headers.get("content-type", "").lower()
            if (
                str(retry_response.url) == url
                and 200 <= retry_response.status_code < 300
                and ("text/html" in retry_content_type or "application/xhtml" in retry_content_type)
            ):
                retry_info = _extract_novel_platform_info(retry_response.text, url)
                if _has_munpia_official_detail_content(retry_info):
                    html = retry_response.text
                    direct_response = retry_response
                    structured_info_httpx = retry_info
        except httpx.HTTPError:
            pass

    if crawl4ai_shell_result is not None and not (
        direct_response is not None
        and str(direct_response.url) == url
        and 200 <= direct_response.status_code < 300
        and _has_munpia_official_detail_content(structured_info_httpx)
    ):
        return crawl4ai_shell_result

    structured_info_httpx["fetch_method"] = "httpx"

    text = _html_to_text(html)  # 전문 추출 (길이 제한 없음)
    text, structured_info_httpx = _sanitize_munpia_canvas_viewer_text(
        url, html, text, structured_info_httpx,
    )

    return {
        "url": url,
        "domain": domain,
        "text": text,
        "structured_info": structured_info_httpx,
        **_fetch_transport_provenance(
            url, str(direct_response.url) if direct_response is not None else None,
            "httpx", direct_response.status_code if direct_response is not None else None,
        ),
        **_fanart_raw_html_receipt(
            url, html, str(direct_response.url) if direct_response is not None else None,
            "httpx", direct_response.status_code if direct_response is not None else None,
        ),
        **_munpia_official_detail_transport_receipt(
            url, str(direct_response.url) if direct_response is not None else None,
            "httpx", direct_response.status_code if direct_response is not None else None,
        ),
    }


@app.get("/health")
@app.get("/healthz")
def health_check() -> Dict[str, Any]:
    """빠른 liveness 확인.

    expert_main startup에서 40개 이상의 shard를 동시에 확인하므로,
    여기서는 내부 검색/크롤러/backend 호출을 하지 않는다. 깊은 준비 상태는
    /readyz 또는 /healthz/deep에서 확인한다.
    """
    return {
        "status": "ok",
        "bridge": True,
        "searchxng_url": SEARCHXNG_URL,
        "headless_search_enabled": HEADLESS_SEARCH_ENABLED,
    }


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("MCP_PORT", "3333")))


if __name__ == "__main__":
    main()
