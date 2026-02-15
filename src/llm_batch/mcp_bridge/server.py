from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sys


class SearchRequest(BaseModel):
    query: str
    num_results: int = 10  # 기본값: 10개 결과


class FetchRequest(BaseModel):
    url: str
    max_length: int = 2000  # 반환할 최대 텍스트 길이


app = FastAPI(title="SearchXNG MCP Bridge")
SEARCHXNG_URL = os.getenv("SEARCHXNG_URL", "http://searchxng:8080")
DEFAULT_NUM_RESULTS = int(os.getenv("MCP_DEFAULT_NUM_RESULTS", "10"))

# URL 페칭 허용 도메인 (웹소설 관련 공식/커뮤니티 + 주요 검색 결과 소스)
_ALLOWED_FETCH_DOMAINS = {
    # 위키/나무위키
    "namu.wiki", "ko.wikipedia.org",
    # 웹소설 공식 플랫폼
    "novelpia.com", "www.novelpia.com",
    "munpia.com", "mm.munpia.com", "m.munpia.com", "novel.munpia.com",
    "series.naver.com", "m.series.naver.com",
    "ridibooks.com", "www.ridibooks.com",
    "kakaopage.com", "page.kakao.com",
    "joara.com", "www.joara.com",
    # 커뮤니티
    "arca.live",
    "gall.dcinside.com", "m.dcinside.com",
    "m.fmkorea.com", "www.fmkorea.com",
    "m.ruliweb.com", "www.ruliweb.com",
    # 블로그/리뷰
    "blog.naver.com", "m.blog.naver.com",
    "tistory.com",  # *.tistory.com 매칭용은 endswith 로직에서 처리
    "brunch.co.kr",
}


@app.get("/healthz")
def healthz():
    """헬스체크 엔드포인트 — SearXNG 연결까지 확인"""
    try:
        resp = httpx.get(f"{SEARCHXNG_URL}/healthz", timeout=5.0)
        return {"status": "ok", "searxng": resp.status_code == 200}
    except Exception as e:
        return {"status": "degraded", "searxng": False, "error": str(e)}


@app.post("/mcp/search")
def mcp_search(request: SearchRequest) -> Dict[str, Any]:
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="query is required")

    num_results = request.num_results or DEFAULT_NUM_RESULTS
    params = {"q": request.query, "format": "json", "safesearch": "0", "pageno": "1"}
    # SearXNG botdetection은 X-Forwarded-For / X-Real-IP 헤더가 없으면 에러/차단을 유발할 수 있음.
    headers = {
        "User-Agent": "llm-batch/0.1 (+mcp-bridge)",
        "X-Forwarded-For": "127.0.0.1",
        "X-Real-IP": "127.0.0.1",
        "X-Forwarded-Proto": "http",
    }
    try:
        response = httpx.get(
            f"{SEARCHXNG_URL.rstrip('/')}/search",
            params=params,
            headers=headers,
            timeout=20.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        # 원인 파악을 위해 stderr에 디테일을 남긴다.
        try:
            print(f"[mcp-bridge] searchxng request failed: {exc!r}", file=sys.stderr, flush=True)
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    data = response.json()
    results: List[Dict[str, Any]] = []
    # 요청한 개수만큼만 반환 (SearXNG가 더 많이 반환할 수 있음)
    for item in data.get("results", [])[:num_results]:
        results.append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "content": item.get("content"),
            }
        )
    return {"query": request.query, "results": results, "total": len(data.get("results", []))}


def _extract_domain(url: str) -> str:
    """URL에서 도메인 추출"""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        return parsed.hostname or ""
    except Exception:
        return ""


def _html_to_text(html: str, max_length: int = 2000) -> str:
    """HTML → 순수 텍스트 추출 (경량, 외부 의존성 없음)"""
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
    # 길이 제한
    if len(text) > max_length:
        text = text[:max_length]
    return text


def _extract_namu_wiki_info(html: str) -> Dict[str, Any]:
    """나무위키 페이지에서 작품 정보를 구조적으로 추출"""
    info: Dict[str, Any] = {}
    
    # 제목 추출 (h1.title 또는 document-title)
    title_match = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
    if title_match:
        raw_title = title_match.group(1)
        # " - 나무위키" 제거
        raw_title = re.sub(r'\s*[-–—]\s*나무위키\s*$', '', raw_title).strip()
        info["page_title"] = raw_title
    
    text = _html_to_text(html, max_length=5000)
    
    # 약칭 패턴: "약칭은 X", "약칭은 X 또는 Y"
    abbrev_match = re.search(r'약칭(?:은|으로)\s+([^\s,.]+(?:\s+또는\s+[^\s,.]+)*)', text)
    if abbrev_match:
        info["abbreviations"] = [a.strip() for a in abbrev_match.group(1).split("또는")]
    
    # 작가 패턴: "작가는 X", "X 작가의", "작가명 X"
    author_match = re.search(r"['\"]?([가-힣A-Za-z0-9_]+)['\"]?\s*작가의", text)
    if author_match:
        info["author"] = author_match.group(1)
    else:
        author_match2 = re.search(r'작가(?:는|명)\s+["\']?([가-힣A-Za-z0-9_]+)', text)
        if author_match2:
            info["author"] = author_match2.group(1)
    
    # 장르 패턴
    genre_match = re.search(r'(?:장르|분류)\s*[:\s]\s*([^\n.]{3,30})', text)
    if genre_match:
        info["genre"] = genre_match.group(1).strip()
    
    # 연재 플랫폼
    for platform in ("노벨피아", "문피아", "카카오페이지", "네이버 시리즈"):
        if platform in text:
            info.setdefault("platforms", []).append(platform)
    
    info["text_preview"] = text[:2000]
    return info


def _extract_novel_platform_info(html: str, url: str) -> Dict[str, Any]:
    """노벨피아/문피아 등 공식 플랫폼 페이지에서 정보 추출"""
    info: Dict[str, Any] = {}
    
    # <title> 태그에서 제목 추출
    title_match = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
    if title_match:
        raw_title = title_match.group(1).strip()
        # 플랫폼 접미사 제거
        for suffix in (" - 노벨피아", " - 웹소설로 꿈꾸는 세상!", " - 문피아",
                        " | 카카오페이지", " - 네이버 시리즈"):
            if raw_title.endswith(suffix):
                raw_title = raw_title[:-len(suffix)].strip()
        info["title"] = raw_title
    
    text = _html_to_text(html, max_length=3000)
    
    # 작가명 추출
    author_match = re.search(r'작가(?:명|:)\s*([가-힣A-Za-z0-9_]+)', text)
    if author_match:
        info["author"] = author_match.group(1)
    
    # 장르/태그 추출
    tags = re.findall(r'#([가-힣A-Za-z]+)', text)
    if tags:
        info["tags"] = tags[:10]
    
    info["text_preview"] = text[:2000]
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
        if len(fallback_text) > max_length:
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
    
    웹소설 관련 공식/커뮤니티 도메인만 허용하여 악용 방지.
    나무위키, 노벨피아, 문피아 등의 페이지에서 작품 정보를 구조적으로 추출.
    
    직접 fetch 실패 시 SearXNG site: 검색으로 fallback하여
    검색엔진 캐시에서 콘텐츠를 획득한다.
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
        raise HTTPException(
            status_code=403,
            detail=f"Domain '{domain}' is not in the allowed list for fetching"
        )
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    
    fetch_error: Optional[str] = None
    html: Optional[str] = None
    
    try:
        response = httpx.get(url, headers=headers, timeout=15.0, follow_redirects=True)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type or "application/xhtml" in content_type:
            html = response.text
        else:
            fetch_error = f"Not HTML content: {content_type}"
    except httpx.HTTPError as exc:
        fetch_error = str(exc)
        try:
            print(f"[mcp-bridge] direct fetch failed, trying searxng fallback: {url} → {exc!r}",
                  file=sys.stderr, flush=True)
        except Exception:
            pass
    
    # --- 직접 fetch 실패 → SearXNG site: 검색 fallback ---
    if html is None:
        fallback_result = _searxng_site_fallback(url, domain, request.max_length)
        if fallback_result is not None:
            # fallback 성공 — 검색엔진 캐시에서 콘텐츠 획득
            fallback_result["direct_fetch_error"] = fetch_error
            return fallback_result
        # fallback도 실패 — 에러 반환
        raise HTTPException(
            status_code=502,
            detail=f"Fetch failed (direct + searxng fallback): {fetch_error}"
        )
    
    # --- 직접 fetch 성공 → 기존 로직 ---
    # 도메인별 구조적 정보 추출
    structured_info: Dict[str, Any] = {}
    if "namu.wiki" in domain:
        structured_info = _extract_namu_wiki_info(html)
    elif any(p in domain for p in ("novelpia", "munpia", "kakaopage", "series.naver", "joara")):
        structured_info = _extract_novel_platform_info(html, url)
    else:
        # 범용: 최소한 <title>과 본문 미리보기 추출
        title_match = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
        if title_match:
            structured_info["title"] = title_match.group(1).strip()
    
    # 일반 텍스트 추출 — 본문 내용을 충분히 보존
    text = _html_to_text(html, max_length=request.max_length)
    
    return {
        "url": url,
        "domain": domain,
        "text": text,
        "structured_info": structured_info,
    }


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("MCP_PORT", "3333")))


if __name__ == "__main__":
    main()

