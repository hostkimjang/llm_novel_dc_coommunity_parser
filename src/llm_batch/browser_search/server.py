from __future__ import annotations

import os
import random
import re
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from fastapi import FastAPI
from pydantic import BaseModel


app = FastAPI(title="Browser Search Fallback")

_DRIVER = None
_DRIVER_CREATED_AT = 0.0
_DRIVER_USE_COUNT = 0
_PROVIDER_BLOCKED_UNTIL: Dict[str, float] = {}
_CACHE: Dict[tuple[str, int, str], Dict[str, Any]] = {}
_GOOGLE_SEARCH_LOCK = threading.Lock()
_GOOGLE_LAST_REQUEST_AT = 0.0

MAX_CACHE_ITEMS = 256
DRIVER_MAX_AGE_SEC = 900
DRIVER_MAX_USES = 80
PAGE_LOAD_TIMEOUT_SEC = 25
GOOGLE_DIRECT_PROVIDERS = ("cloak", "playwright", "ucd")


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name, "1" if default else "0").strip().lower()
    return val in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float, *, min_value: float = 0.0, max_value: float = 3600.0) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = float(raw)
    except Exception:
        value = default
    return max(min_value, min(max_value, value))


def _block_cooldown_sec() -> float:
    return _env_float("BROWSER_SEARCH_BLOCK_COOLDOWN_SEC", 7200.0, min_value=60.0, max_value=86400.0)


def _google_min_interval_sec() -> float:
    return _env_float("BROWSER_SEARCH_GOOGLE_MIN_INTERVAL_SEC", 45.0, min_value=0.0, max_value=600.0)


def _google_jitter_sec() -> float:
    return _env_float("BROWSER_SEARCH_GOOGLE_JITTER_SEC", 15.0, min_value=0.0, max_value=120.0)


def _provider_order() -> tuple[str, ...]:
    raw = os.getenv("BROWSER_SEARCH_PROVIDER_ORDER", "cloak,naver")
    providers: list[str] = []
    for token in raw.split(","):
        provider = token.strip().lower()
        if provider in {"cloak", "playwright", "ucd", "naver"} and provider not in providers:
            providers.append(provider)
    return tuple(providers or ["cloak", "naver"])


def _page_wait_ms() -> int:
    raw = os.getenv("BROWSER_SEARCH_WAIT_MS", "3000").strip()
    try:
        return max(0, min(int(raw), 10000))
    except Exception:
        return 3000


PROVIDER_ORDER = _provider_order()

GOOGLE_BLOCK_MARKERS = (
    "/sorry/",
    "detected unusual traffic",
    "unusual traffic from your computer network",
    "our systems have detected",
    "captcha",
    "g-recaptcha",
    "recaptcha",
    "consent.google",
    "before you continue",
)


class BrowserSearchRequest(BaseModel):
    query: str
    num_results: int = 10
    purpose: str = ""


def _cache_get(key: tuple[str, int, str]) -> Optional[Dict[str, Any]]:
    item = _CACHE.get(key)
    if item is None:
        return None
    return dict(item)


def _cache_put(key: tuple[str, int, str], value: Dict[str, Any]) -> None:
    if len(_CACHE) >= MAX_CACHE_ITEMS:
        for old_key in list(_CACHE.keys())[: max(1, MAX_CACHE_ITEMS // 8)]:
            _CACHE.pop(old_key, None)
    _CACHE[key] = dict(value)


def _cleanup_driver() -> None:
    global _DRIVER, _DRIVER_CREATED_AT, _DRIVER_USE_COUNT
    if _DRIVER is not None:
        try:
            _DRIVER.quit()
        except Exception:
            pass
    _DRIVER = None
    _DRIVER_CREATED_AT = 0.0
    _DRIVER_USE_COUNT = 0


def _new_driver():
    import undetected_chromedriver as uc

    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=ko-KR")
    options.add_argument("--window-size=1365,1800")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

    user_data_dir = tempfile.mkdtemp(prefix="browser-search-profile-")
    options.add_argument(f"--user-data-dir={user_data_dir}")

    chrome_binary = os.getenv("BROWSER_SEARCH_CHROME_BINARY", "/usr/bin/chromium")
    if chrome_binary:
        options.binary_location = chrome_binary

    driver = uc.Chrome(options=options, browser_executable_path=chrome_binary or None, use_subprocess=True)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT_SEC)
    return driver


def _get_driver():
    global _DRIVER, _DRIVER_CREATED_AT, _DRIVER_USE_COUNT
    now = time.time()
    if (
        _DRIVER is None
        or (now - _DRIVER_CREATED_AT) > DRIVER_MAX_AGE_SEC
        or _DRIVER_USE_COUNT >= DRIVER_MAX_USES
    ):
        _cleanup_driver()
        _DRIVER = _new_driver()
        _DRIVER_CREATED_AT = now
        _DRIVER_USE_COUNT = 0
    _DRIVER_USE_COUNT += 1
    return _DRIVER


def _is_blocked_html(url: str, html: str) -> bool:
    raw = f"{url}\n{html or ''}".lower()
    return any(marker in raw for marker in GOOGLE_BLOCK_MARKERS)


def _clean_google_url(raw_url: str) -> str:
    url = str(raw_url or "").strip()
    if not url:
        return ""
    if url.startswith("/url?"):
        parsed = urlparse(url)
        q = parse_qs(parsed.query).get("q") or parse_qs(parsed.query).get("url")
        if q:
            url = q[0]
    elif "google.com/url?" in url:
        parsed = urlparse(url)
        q = parse_qs(parsed.query).get("q") or parse_qs(parsed.query).get("url")
        if q:
            url = q[0]
    url = unquote(url)
    if url.startswith("/"):
        return ""
    return url


def _clean_naver_url(raw_url: str) -> str:
    url = str(raw_url or "").strip()
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        query = parse_qs(parsed.query)
    except Exception:
        return url
    if host.endswith("naver.com"):
        for key in ("u", "url", "r"):
            vals = query.get(key)
            if vals:
                return unquote(vals[0])
    return unquote(url)


def _is_allowed_result_url(url: str) -> bool:
    if not url.startswith(("http://", "https://")):
        return False
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    if not host:
        return False
    if host == "google.com" or host.endswith(".google.com") or host.startswith("google."):
        return False
    # Keep Naver search/internal surfaces out, but allow useful verticals such as
    # series.naver.com when Naver returns an official novel detail page.
    if host == "naver.com":
        return False
    naver_blocked_hosts = (
        "www.naver.com",
        "search.naver.com",
        "m.search.naver.com",
        "adcr.naver.com",
        "help.naver.com",
        "nid.naver.com",
        "navercorp.com",
        "www.navercorp.com",
        "ssl.pstatic.net",
        "sstatic-g.rmcnmv.naver.net",
    )
    if any(host == h or host.endswith("." + h) for h in naver_blocked_hosts):
        return False
    blocked_hosts = (
        "webcache.googleusercontent.com",
        "policies.google.com",
        "support.google.com",
        "accounts.google.com",
        "translate.google.com",
    )
    if any(host == h.rstrip(".") or host.startswith(h) or host.endswith("." + h.rstrip(".")) for h in blocked_hosts):
        return False
    if "/aclk?" in url or "adurl=" in url:
        return False
    return True


def _is_detail_like_result_url(url: str) -> bool:
    try:
        parsed = urlparse(str(url or ""))
        host = (parsed.hostname or "").lower()
        path = parsed.path or ""
        query = parsed.query or ""
    except Exception:
        return False
    if not host:
        return False
    if host in {"novelpia.com", "www.novelpia.com", "m.novelpia.com"}:
        return bool(re.search(r"/novel/\d+", path))
    if host.endswith("munpia.com"):
        return bool(re.search(r"/novel(?:/detail)?/\d+|/novel/\d+", path))
    if host == "series.naver.com":
        return "productNo=" in query or "/novel/detail" in path
    if host == "page.kakao.com":
        return bool(re.search(r"/content/\d+", path))
    if host in {"ridibooks.com", "www.ridibooks.com"}:
        return bool(re.search(r"/books/\d+", path))
    if host in {"joara.com", "www.joara.com"}:
        return "bookCode=" in query or bool(re.search(r"/book/\d+", path))
    return False


def _is_noise_result_row(url: str, title: str, snippet: str, *, engine: str) -> bool:
    title_clean = " ".join(str(title or "").split()).strip()
    snippet_clean = " ".join(str(snippet or "").split()).strip()
    if not title_clean:
        return True

    title_norm = re.sub(r"[\s\W_]+", "", title_clean.lower())
    try:
        parsed = urlparse(str(url or ""))
        host = (parsed.hostname or "").lower()
        path = parsed.path or ""
    except Exception:
        host = ""
        path = ""

    generic_exact_titles = {
        "naver",
        "네이버",
        "네이버검색",
        "통합검색",
        "더보기",
        "이미지",
        "동영상",
        "뉴스",
        "쇼핑",
        "지도",
        "지식in",
        "지식iN",
        "블로그",
        "카페",
        "노벨피아",
        "문피아",
        "카카오페이지",
        "리디",
        "리디북스",
        "조아라",
    }
    generic_norms = {re.sub(r"[\s\W_]+", "", item.lower()) for item in generic_exact_titles}
    if title_norm in generic_norms and not _is_detail_like_result_url(url):
        return True

    if "naver" in engine:
        nav_noise = {
            "검색결과",
            "연관검색어",
            "인기글",
            "파워링크",
            "플레이스",
            "네이버페이",
            "네이버플러스",
            "로그인",
            "도움말",
            "전체서비스",
        }
        if any(token in title_clean or token in snippet_clean[:120] for token in nav_noise):
            return True
        if host.endswith("pstatic.net") or host.endswith("rmcnmv.naver.net"):
            return True
        if host in {"novelpia.com", "www.novelpia.com"} and path in {"", "/"}:
            return True
        if host.endswith("munpia.com") and path in {"", "/"}:
            return True
        if host == "page.kakao.com" and path in {"", "/"}:
            return True
    return False


def _provider_blocked(provider: str) -> bool:
    return time.time() < float(_PROVIDER_BLOCKED_UNTIL.get(provider, 0.0))


def _mark_provider_blocked(provider: str, cooldown_sec: Optional[float] = None) -> None:
    _PROVIDER_BLOCKED_UNTIL[provider] = time.time() + float(cooldown_sec or _block_cooldown_sec())


def _mark_google_direct_blocked() -> None:
    cooldown = _block_cooldown_sec()
    for provider in GOOGLE_DIRECT_PROVIDERS:
        _mark_provider_blocked(provider, cooldown)


def _wait_for_google_direct_slot() -> None:
    global _GOOGLE_LAST_REQUEST_AT
    min_interval = _google_min_interval_sec()
    jitter = _google_jitter_sec()
    if min_interval <= 0 and jitter <= 0:
        return
    with _GOOGLE_SEARCH_LOCK:
        now = time.time()
        target = _GOOGLE_LAST_REQUEST_AT + min_interval
        if jitter > 0:
            target += random.uniform(0.0, jitter)
        wait_sec = target - now
        if wait_sec > 0:
            time.sleep(wait_sec)
        _GOOGLE_LAST_REQUEST_AT = time.time()


def _blocked_until() -> float:
    active = [until for until in _PROVIDER_BLOCKED_UNTIL.values() if until > time.time()]
    return max(active) if active else 0.0


def _all_providers_blocked() -> bool:
    return all(_provider_blocked(provider) for provider in PROVIDER_ORDER)


def _normalize_link_rows(rows: List[Dict[str, Any]], limit: int, *, engine: str) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    seen_urls: set[str] = set()
    for row in rows or []:
        if len(results) >= limit:
            break
        if not isinstance(row, dict):
            continue
        raw_href = str(row.get("url") or "")
        href = _clean_naver_url(raw_href) if "naver" in engine else _clean_google_url(raw_href)
        title = str(row.get("title") or "").strip()
        snippet = str(row.get("content") or "").strip()
        if not title or len(title) < 2:
            continue
        if not _is_allowed_result_url(href):
            continue
        if _is_noise_result_row(href, title, snippet, engine=engine):
            continue
        if href in seen_urls:
            continue
        if not snippet and re.search(r"^(http|www\.|https)", title, re.IGNORECASE):
            continue
        seen_urls.add(href)
        results.append(
            {
                "title": title.splitlines()[0].strip(),
                "url": href,
                "content": snippet[:500],
                "engine": engine,
            }
        )
    return results


def _parse_naver_results(page: Any, limit: int) -> List[Dict[str, str]]:
    try:
        rows = page.evaluate(
            """(limit) => {
                const rows = [];
                const selectors = [
                    'a.link_tit',
                    'a.total_tit',
                    'a.title_link',
                    'a.api_txt_lines.total_tit',
                    'a.link_name',
                    'a.name_link'
                ];
                const seen = new Set();
                for (const selector of selectors) {
                    const anchors = Array.from(document.querySelectorAll(selector));
                    for (const a of anchors) {
                        if (rows.length >= limit * 80) break;
                        const href = a.href || '';
                        const title = (a.innerText || a.textContent || '').trim();
                        if (!href || !title || title.length < 2) continue;
                        const key = href + '|' + title;
                        if (seen.has(key)) continue;
                        seen.add(key);
                        let node = a;
                        let snippet = '';
                        for (let i = 0; i < 6 && node; i++) {
                            const text = (node.innerText || node.textContent || '').trim();
                            if (text && text.length > title.length + 10) {
                                snippet = text
                                    .split('\\n')
                                    .map((line) => line.trim())
                                    .filter((line) => {
                                        if (!line || line === title) return false;
                                        if (line.includes('http://') || line.includes('https://')) return false;
                                        if (line.length <= 1) return false;
                                        return true;
                                    })
                                    .join(' ')
                                    .trim();
                                break;
                            }
                            node = node.parentElement;
                        }
                        rows.push({title, url: href, content: snippet});
                    }
                    if (rows.length >= limit) break;
                }
                if (rows.length < limit) {
                    const fallbackAnchors = Array.from(document.querySelectorAll('a[href]'));
                    for (const a of fallbackAnchors) {
                        if (rows.length >= limit * 20) break;
                        if (!a.closest('li.bx, div.total_wrap, div.view_wrap, div.web_wrap, div.api_subject_bx, div.api_txt_lines')) continue;
                        if (a.closest('header, footer, nav, aside, .lnb, .gnb, .api_more_wrap')) continue;
                        const href = a.href || '';
                        const title = (a.innerText || a.textContent || '').trim();
                        if (!href || !title || title.length < 2) continue;
                        const key = href + '|' + title;
                        if (seen.has(key)) continue;
                        seen.add(key);
                        let node = a;
                        let snippet = '';
                        for (let i = 0; i < 6 && node; i++) {
                            const text = (node.innerText || node.textContent || '').trim();
                            if (text && text.length > title.length + 10) {
                                snippet = text
                                    .split('\\n')
                                    .map((line) => line.trim())
                                    .filter((line) => {
                                        if (!line || line === title) return false;
                                        if (line.includes('http://') || line.includes('https://')) return false;
                                        if (line.length <= 1) return false;
                                        return true;
                                    })
                                    .join(' ')
                                    .trim();
                                break;
                            }
                            node = node.parentElement;
                        }
                        rows.push({title, url: href, content: snippet});
                    }
                }
                return rows;
            }""",
            limit,
        )
    except Exception:
        rows = []
    return _normalize_link_rows(rows, limit, engine="headless_naver_playwright")


def _snippet_from_container(container: Any) -> str:
    selectors = [
        "div.VwiC3b",
        "div.IsZvec",
        "span.aCOpRe",
        "div[data-sncf]",
    ]
    for selector in selectors:
        try:
            elems = container.find_elements("css selector", selector)
        except Exception:
            elems = []
        texts = [str(e.text or "").strip() for e in elems if str(e.text or "").strip()]
        if texts:
            return " ".join(texts)[:500]
    try:
        text = str(container.text or "").strip()
    except Exception:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) > 1:
        return " ".join(lines[1:])[:500]
    return ""


def _parse_results(driver: Any, limit: int) -> List[Dict[str, str]]:
    try:
        anchors = driver.find_elements("css selector", "a")
    except Exception:
        anchors = []

    rows: List[Dict[str, Any]] = []
    for anchor in anchors:
        if len(rows) >= limit * 4:
            break
        try:
            href = _clean_google_url(anchor.get_attribute("href") or "")
            title = str(anchor.text or "").strip()
        except Exception:
            continue
        if not title or not href:
            continue

        container = anchor
        for _ in range(4):
            try:
                parent = container.find_element("xpath", "..")
            except Exception:
                break
            container = parent
            try:
                if container.find_elements("css selector", "h3"):
                    break
            except Exception:
                pass

        snippet = _snippet_from_container(container)
        rows.append({"title": title, "url": href, "content": snippet})
    return _normalize_link_rows(rows, limit, engine="headless_google_ucd")


def _parse_playwright_results(page: Any, limit: int) -> List[Dict[str, str]]:
    try:
        rows = page.evaluate(
            """(limit) => {
                const rows = [];
                const anchors = Array.from(document.querySelectorAll('a'));
                for (const a of anchors) {
                    const href = a.href || '';
                    const h3 = a.querySelector('h3');
                    if (!h3) continue;
                    if (rows.length >= limit * 4) break;
                    const title = ((h3 && h3.innerText) || a.innerText || a.textContent || '').trim();
                    if (!href || !title) continue;
                    let node = a;
                    let snippet = '';
                    for (let i = 0; i < 5 && node; i++) {
                        const text = (node.innerText || node.textContent || '').trim();
                        if (text && text.length > title.length + 10) {
                            snippet = text
                                .split('\\n')
                                .map((line) => line.trim())
                                .filter((line) => {
                                    if (!line || line === title) return false;
                                    const lowered = line.toLowerCase();
                                    if (lowered.startsWith('http://') || lowered.startsWith('https://')) return false;
                                    if (line.includes(' › ') || line.includes('://')) return false;
                                    return true;
                                })
                                .join(' ')
                                .trim();
                            break;
                        }
                        node = node.parentElement;
                    }
                    rows.push({title, url: href, content: snippet});
                }
                return rows;
            }""",
            limit,
        )
    except Exception:
        rows = []
    return _normalize_link_rows(rows, limit, engine="headless_google_playwright")


def _perform_search_cloak(query: str, num_results: int) -> Dict[str, Any]:
    provider = "cloak"
    if _provider_blocked(provider):
        return {"results": [], "blocked": True, "raw_total": 0, "provider": provider}

    _wait_for_google_direct_slot()

    q = quote_plus(query)
    n = max(1, min(int(num_results or 10), 10))
    url = f"https://www.google.com/search?q={q}&hl=ko&gl=kr&pws=0&num={n}&udm=14"
    launch_args = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--lang=ko-KR",
        "--window-size=1365,1800",
    ]
    extra_args = os.getenv("BROWSER_SEARCH_CLOAK_ARGS", "").strip()
    if extra_args:
        launch_args.extend(arg.strip() for arg in extra_args.split() if arg.strip())

    try:
        from cloakbrowser import launch

        browser = launch(
            headless=_env_bool("BROWSER_SEARCH_HEADLESS", True),
            humanize=_env_bool("BROWSER_SEARCH_HUMANIZE", True),
            human_preset=os.getenv("BROWSER_SEARCH_HUMAN_PRESET", "default").strip() or "default",
            timezone="Asia/Seoul",
            locale="ko-KR",
            args=launch_args,
        )
        try:
            context = browser.new_context(
                locale="ko-KR",
                timezone_id="Asia/Seoul",
                viewport={"width": 1365, "height": 1800},
                extra_http_headers={
                    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                },
            )
            page = context.new_page()
            page.set_default_timeout(PAGE_LOAD_TIMEOUT_SEC * 1000)
            page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_SEC * 1000)
            page.wait_for_timeout(_page_wait_ms())
            html = page.content()
            current_url = page.url
            if _is_blocked_html(current_url, html):
                _mark_google_direct_blocked()
                return {"results": [], "blocked": True, "raw_total": 0, "provider": provider}
            results = _parse_playwright_results(page, n)
            for item in results:
                item["engine"] = "headless_google_cloak"
            return {
                "results": results,
                "blocked": False,
                "raw_total": len(results),
                "provider": provider,
            }
        finally:
            browser.close()
    except Exception as exc:
        return {"results": [], "blocked": False, "raw_total": 0, "error": str(exc), "provider": provider}


def _perform_search_playwright(query: str, num_results: int) -> Dict[str, Any]:
    provider = "playwright"
    if _provider_blocked(provider):
        return {"results": [], "blocked": True, "raw_total": 0, "provider": provider}

    _wait_for_google_direct_slot()

    q = quote_plus(query)
    n = max(1, min(int(num_results or 10), 10))
    url = f"https://www.google.com/search?q={q}&hl=ko&gl=kr&pws=0&num={n}&udm=14"
    chrome_binary = os.getenv("BROWSER_SEARCH_CHROME_BINARY", "/usr/bin/chromium")

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                executable_path=chrome_binary or None,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--lang=ko-KR",
                    "--window-size=1365,1800",
                ],
            )
            try:
                context = browser.new_context(
                    locale="ko-KR",
                    timezone_id="Asia/Seoul",
                    viewport={"width": 1365, "height": 1800},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    ),
                )
                page = context.new_page()
                page.set_default_timeout(PAGE_LOAD_TIMEOUT_SEC * 1000)
                page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_SEC * 1000)
                page.wait_for_timeout(_page_wait_ms())
                html = page.content()
                current_url = page.url
                if _is_blocked_html(current_url, html):
                    _mark_google_direct_blocked()
                    return {"results": [], "blocked": True, "raw_total": 0, "provider": provider}
                results = _parse_playwright_results(page, n)
                return {
                    "results": results,
                    "blocked": False,
                    "raw_total": len(results),
                    "provider": provider,
                }
            finally:
                browser.close()
    except Exception as exc:
        return {"results": [], "blocked": False, "raw_total": 0, "error": str(exc), "provider": provider}


def _perform_search_ucd(query: str, num_results: int) -> Dict[str, Any]:
    provider = "ucd"
    if _provider_blocked(provider):
        return {"results": [], "blocked": True, "raw_total": 0, "provider": provider}

    _wait_for_google_direct_slot()

    q = quote_plus(query)
    n = max(1, min(int(num_results or 10), 10))
    url = f"https://www.google.com/search?q={q}&hl=ko&gl=kr&pws=0&num={n}&udm=14"

    try:
        driver = _get_driver()
        driver.get(url)
        time.sleep(_page_wait_ms() / 1000.0)
        html = driver.page_source or ""
        current_url = driver.current_url or url
        if _is_blocked_html(current_url, html):
            _mark_google_direct_blocked()
            _cleanup_driver()
            return {"results": [], "blocked": True, "raw_total": 0, "provider": provider}

        results = _parse_results(driver, n)
        return {"results": results, "blocked": False, "raw_total": len(results), "provider": provider}
    except Exception as exc:
        _cleanup_driver()
        return {"results": [], "blocked": False, "raw_total": 0, "error": str(exc), "provider": provider}


def _perform_search_naver(query: str, num_results: int) -> Dict[str, Any]:
    provider = "naver"
    if _provider_blocked(provider):
        return {"results": [], "blocked": True, "raw_total": 0, "provider": provider}

    q = quote_plus(query)
    n = max(1, min(int(num_results or 10), 10))
    url = f"https://search.naver.com/search.naver?where=web&query={q}"
    chrome_binary = os.getenv("BROWSER_SEARCH_CHROME_BINARY", "/usr/bin/chromium")

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                executable_path=chrome_binary or None,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--lang=ko-KR",
                    "--window-size=1365,1800",
                ],
            )
            try:
                context = browser.new_context(
                    locale="ko-KR",
                    timezone_id="Asia/Seoul",
                    viewport={"width": 1365, "height": 1800},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/147.0.0.0 Safari/537.36"
                    ),
                    extra_http_headers={
                        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                    },
                )
                page = context.new_page()
                page.set_default_timeout(PAGE_LOAD_TIMEOUT_SEC * 1000)
                page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_SEC * 1000)
                page.wait_for_timeout(_page_wait_ms())
                html = page.content()
                current_url = page.url
                naver_blocked = bool(
                    "자동입력 방지" in html
                    or "보안 확인" in html
                    or "비정상적인 접근" in html
                    or "captcha.naver.com" in html.lower()
                    or "nid.naver.com/login" in current_url.lower()
                )
                if naver_blocked:
                    _mark_provider_blocked(provider, cooldown_sec=min(_block_cooldown_sec(), 1800))
                    return {"results": [], "blocked": True, "raw_total": 0, "provider": provider}
                results = _parse_naver_results(page, n)
                return {
                    "results": results,
                    "blocked": False,
                    "raw_total": len(results),
                    "provider": provider,
                }
            finally:
                browser.close()
    except Exception as exc:
        return {"results": [], "blocked": False, "raw_total": 0, "error": str(exc), "provider": provider}


def _perform_search(query: str, num_results: int) -> Dict[str, Any]:
    if _all_providers_blocked():
        return {"results": [], "blocked": True, "raw_total": 0, "cached": False}

    errors: List[str] = []
    blocked_providers: List[str] = []
    for provider in PROVIDER_ORDER:
        if provider == "cloak":
            result = _perform_search_cloak(query, num_results)
        elif provider == "playwright":
            result = _perform_search_playwright(query, num_results)
        elif provider == "ucd":
            result = _perform_search_ucd(query, num_results)
        elif provider == "naver":
            result = _perform_search_naver(query, num_results)
        else:
            continue
        if result.get("skipped"):
            continue
        if result.get("blocked"):
            blocked_providers.append(str(result.get("provider") or provider))
            has_later_non_google = any(
                later not in GOOGLE_DIRECT_PROVIDERS
                for later in PROVIDER_ORDER[PROVIDER_ORDER.index(provider) + 1 :]
            )
            if provider in GOOGLE_DIRECT_PROVIDERS and not has_later_non_google:
                break
            continue
        if result.get("error"):
            errors.append(f"{result.get('provider') or provider}:{result.get('error')}")
            continue
        if result.get("results"):
            result["cached"] = False
            result["blocked_providers"] = blocked_providers
            result["errors"] = errors
            return result
        errors.append(f"{result.get('provider') or provider}:empty")
    active_provider_count = len(PROVIDER_ORDER)
    direct_google_blocked = any(provider in GOOGLE_DIRECT_PROVIDERS for provider in blocked_providers)

    return {
        "results": [],
        "blocked": bool(blocked_providers) and (direct_google_blocked or len(blocked_providers) >= active_provider_count),
        "blocked_providers": blocked_providers,
        "raw_total": 0,
        "errors": errors,
        "cached": False,
    }


@app.post("/search")
def search(request: BrowserSearchRequest) -> Dict[str, Any]:
    query = request.query.strip()
    if not query:
        return {"results": [], "blocked": False, "raw_total": 0}
    n = max(1, min(int(request.num_results or 10), 10))
    key = (query, n, str(request.purpose or ""))
    cached = _cache_get(key)
    if cached is not None:
        cached["cached"] = True
        return cached

    result = _perform_search(query, n)
    if not result.get("blocked") and not result.get("error"):
        _cache_put(key, result)
    return result


@app.get("/healthz")
def healthz() -> Dict[str, Any]:
    blocked_until = _blocked_until()
    return {
        "status": "blocked" if blocked_until else "ok",
        "blocked_until": blocked_until,
        "provider_blocked_until": dict(_PROVIDER_BLOCKED_UNTIL),
        "providers": list(PROVIDER_ORDER),
        "google_direct_min_interval_sec": _google_min_interval_sec(),
        "google_direct_jitter_sec": _google_jitter_sec(),
        "block_cooldown_sec": _block_cooldown_sec(),
        "cache_size": len(_CACHE),
        "driver_alive": _DRIVER is not None,
    }


@app.on_event("shutdown")
def shutdown() -> None:
    _cleanup_driver()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8765)
