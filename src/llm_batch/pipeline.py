from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .models import BatchInput, CommentInput, Inference, OutputItem, PickvelAnalysis, PickvelIdentity, PickvelOutputItemV2, PostInput
from .models import OutputItem as OutputItemModel
from .rules import NOISE_TERMS, NOVEL_SITES, SLANG_DICTIONARY, TROPE_TERMS, apply_rules
from .llm.client import LLMClient
from .search.client import MCPClient


def _ts() -> str:
    """타임스탬프 반환 (HH:MM:SS.mmm)"""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def _load_json_items(path: Path) -> List[dict]:
    raw = path.read_text(encoding="utf-8").strip()
    return _load_json_items_from_text(raw)


def _load_json_items_from_text(raw: str) -> List[dict]:
    raw = raw.strip()
    if not raw:
        return []
    if raw.startswith("["):
        return json.loads(raw)
    items: List[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(json.loads(line))
    return items


def _partition_items(items: Iterable[dict]) -> Tuple[List[PostInput], List[CommentInput]]:
    posts: List[PostInput] = []
    comments: List[CommentInput] = []
    for item in items:
        if "comment_id" in item:
            comments.append(CommentInput.model_validate(item))
        elif "post_id" in item:
            posts.append(PostInput.model_validate(item))
    return posts, comments


def _post_texts(post: PostInput) -> List[str]:
    texts: List[str] = []
    for block in post.content_blocks:
        if block.text:
            texts.append(block.text)
    return texts


def _lookup_title_from_url(mcp: MCPClient, url: str) -> Optional[str]:
    try:
        data = mcp.search(url)
    except Exception:
        return None
    for result in data.get("results", []):
        title = result.get("title")
        if title:
            return title
    return None


def _extract_url_candidate(text: str) -> Optional[str]:
    """
    댓글에서 URL 후보를 뽑아낸다.
    - 'https://...' / 'http://...' 는 그대로 사용
    - 'novelpia.com/...' 처럼 scheme 없는 도메인도 https:// 를 붙여서 처리
    """
    s = (text or "").strip()
    if not s:
        return None
    m = re.search(r"(https?://\\S+)", s, flags=re.IGNORECASE)
    if m:
        url = m.group(1)
    else:
        m2 = re.search(r"((?:novelpia\\.com|munpia\\.com|kakao\\.com)\\S+)", s, flags=re.IGNORECASE)
        if not m2:
            return None
        url = "https://" + m2.group(1)
    # 흔한 꼬리 구두점 제거
    url = url.rstrip(").,]\\'\\\"")
    return url


def _compact_search_response(data: dict) -> dict:
    """
    MCP(SearchXNG) 결과를 LLM에 넘길 때 토큰을 아끼기 위해 축약한다.
    - 상위 N개만
    - title/url/content만 유지하고 content는 길이 제한
    """
    try:
        top_k = int(os.getenv("MCP_TOP_K_RESULTS", "5"))
    except Exception:
        top_k = 5
    try:
        max_chars = int(os.getenv("MCP_MAX_CONTENT_CHARS", "0"))
    except Exception:
        max_chars = 0

    out = {"query": data.get("query"), "results": []}
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        return out

    for item in results[: max(1, top_k)]:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        url = item.get("url")
        content = item.get("content") or ""
        if not isinstance(content, str):
            content = str(content)
        if max_chars > 0 and len(content) > max_chars:
            content = content[:max_chars] + f"...(truncated,len={len(content)})"
        out["results"].append({"title": title, "url": url, "content": content})
    return out


def _trace_search_summary(post_id: int, query: str, compact: dict) -> None:
    if not compact or not isinstance(compact, dict):
        return
    results = compact.get("results")
    if not isinstance(results, list):
        results = []
    top = []
    for r in results[:3]:
        if not isinstance(r, dict):
            continue
        top.append({"title": r.get("title"), "url": r.get("url")})
    import json as _json  # local import to avoid polluting module namespace
    top_s = _json.dumps(top, ensure_ascii=False)
    print(f"[{_ts()}][trace] post_id={post_id} 검색 결과: query={query!r} count={len(results)}", file=sys.stderr)
    print(f"[{_ts()}][trace] post_id={post_id} 검색 TOP3: {top_s}", file=sys.stderr)


def _has_good_search_results(search_results: List[Dict[str, Any]], novel_sites: List[str]) -> bool:
    """
    검색 결과 중 소설 플랫폼의 실제 작품 페이지 URL이 있으면 True.
    Round 2를 스킵할지 판단하는 데 사용.
    
    주의: 검색 페이지, 카테고리 페이지, 리뷰 페이지는 '좋은 결과'가 아님.
    실제 작품 상세 페이지(novel/detail, novel/view 등)만 인정.
    """
    if not search_results:
        return False
    
    # 검색/카테고리/리스트 페이지 패턴 (이런 URL은 제외)
    excluded_patterns = [
        "detailSearchV2", "search", "categoryProductList",
        "category", "list", "ranking", "review.series",
        "page=", "orderType", "genreCode"
    ]
    
    for sr in search_results:
        results = sr.get("results", [])
        for r in results:
            url = r.get("url", "").lower()
            # 소설 플랫폼 URL인지 확인
            is_novel_site = any(site in url for site in novel_sites)
            if not is_novel_site:
                continue
            # 제외 패턴이 있으면 스킵
            if any(pat.lower() in url for pat in excluded_patterns):
                continue
            # 실제 작품 페이지 패턴 확인
            # munpia: novel/view, novel/detail
            # novelpia: novel/, content/
            # series.naver: detail.series, novel.series
            # joara: view/id=
            work_patterns = [
                "novel/view", "novel/detail", "/novel/",
                "detail.series", "novel.series",
                "view&id=", "menu=novel&action=view"
            ]
            if any(pat.lower() in url for pat in work_patterns):
                return True
    return False


def _has_novel_platform_url(search_results: List[Dict[str, Any]], novel_sites: List[str]) -> bool:
    """
    검색 결과에 소설 플랫폼 URL이 있는지 확인.
    커뮤니티 URL만 있으면 False 반환.
    """
    if not search_results:
        return False
    
    community_domains = ["dcinside.com", "fmkorea.com", "arca.live", "ruliweb.com", "theqoo.net", "clien.net"]
    
    for sr in search_results:
        results = sr.get("results", [])
        for r in results:
            url = r.get("url", "")
            # 소설 플랫폼 URL인지 확인
            for site in novel_sites:
                if site in url:
                    # 검색 결과 페이지가 아닌 실제 소설 페이지인지 확인
                    if "detailSearchV2" not in url and "search" not in url.lower():
                        return True
            # 위키 URL도 신뢰할 수 있는 출처
            if "namu.wiki" in url or "wikipedia.org" in url:
                return True
    return False


def _needs_refined_search(
    first_result: Any,
    search_results: List[Dict[str, Any]],
    novel_sites: List[str],
    detected_term: Optional[str],
) -> Tuple[bool, Optional[str]]:
    """
    1차 enrich 결과를 분석하여 추가 검색이 필요한지 판단.
    
    핵심 로직:
    1. official_title이 null이면 → 추가 검색 필요
    2. official_title이 있어도, 검색 결과에서 해당 제목이 실제로 확인되지 않으면 → 추가 검색 필요
       (LLM이 추론으로 잘못 매핑했을 가능성)
    
    Returns:
        (needs_search, refined_query): 추가 검색 필요 여부와 정제된 쿼리
    """
    novel_identity = getattr(first_result, "novel_identity", None)
    official_title = getattr(novel_identity, "official_title", None) if novel_identity else None
    confidence = getattr(novel_identity, "confidence", None) if novel_identity else None
    
    # detected_term 추출
    slang_insight = getattr(first_result, "slang_insight", None)
    if slang_insight:
        term = getattr(slang_insight, "detected_term", None) or detected_term
    else:
        term = detected_term
    
    # official_title이 있으면, 검색 결과에서 실제로 확인되는지 검증
    if official_title:
        title_verified = _verify_title_in_search_results(official_title, search_results, novel_sites)
        if title_verified:
            return False, None  # 검증됨 → 추가 검색 불필요
        # 검증 안 됨 → LLM이 추론으로 잘못 매핑했을 가능성, 추가 검색 필요
        if term:
            return True, f"({term}) (site:munpia.com OR site:novelpia.com OR site:joara.com)"
    
    # official_title=null이거나 confidence가 낮으면 추가 검색
    if official_title is None or confidence in ("None", "Low"):
        if term:
            return True, f"({term}) (site:munpia.com OR site:novelpia.com OR site:joara.com)"
    
    return False, None


def _verify_title_in_search_results(
    official_title: str,
    search_results: List[Dict[str, Any]],
    novel_sites: List[str],
) -> bool:
    """
    검색 결과에서 official_title이 실제로 확인되는지 검증.
    소설 플랫폼/위키 URL의 title 또는 content에 제목이 포함되어 있어야 함.
    """
    if not official_title or not search_results:
        return False
    
    title_lower = official_title.lower().strip()
    trusted_domains = list(novel_sites) + ["namu.wiki", "wikipedia.org"]
    
    for sr in search_results:
        results = sr.get("results", [])
        for r in results:
            url = r.get("url", "").lower()
            title = r.get("title", "").lower()
            content = r.get("content", "").lower()
            
            # 신뢰할 수 있는 도메인인지 확인
            is_trusted = any(domain in url for domain in trusted_domains)
            if not is_trusted:
                continue
            
            # 제목이 title 또는 content에 포함되어 있는지 확인
            if title_lower in title or title_lower in content:
                return True
    
    return False


def _extract_first_url(text: str) -> Optional[str]:
    if not text:
        return None
    m = re.search(r"(https?://\\S+)", text, flags=re.IGNORECASE)
    if not m:
        return None
    return m.group(1).rstrip(").,]\\'\\\"")


def _extract_json_list_text(text: str) -> str:
    """
    LLM이 ```json ...``` 같은 마크다운 펜스를 붙이는 경우가 있어 이를 제거하고,
    가능한 경우 JSON list 구간([..])만 뽑아낸다.
    - think 스트림 모드에서는 <think>...</think>가 앞에 올 수 있으므로 마지막 </think> 이후를 우선한다.
    """
    s = text.strip()
    if s.startswith("```"):
        # drop first fence line and last fence if present
        lines = s.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        s = "\n".join(lines).strip()

    # think 블록이 있으면 마지막 </think> 뒤만 사용
    if "</think>" in s:
        s = s.split("</think>")[-1].strip()

    # JSON list 시작점 후보를 뒤에서부터 찾아, 실제로 json.loads 가능한 구간을 선택
    # (LLM이 앞에 설명/think를 붙이거나, 중간에 []를 사용할 수 있음)
    starts = [m.start() for m in re.finditer(r"\[", s)]
    for st in reversed(starts):
        candidate = s[st:].strip()
        try:
            obj = json.loads(candidate)
            if isinstance(obj, list):
                return candidate
        except Exception:
            continue

    # fallback: 가장 넓은 대괄호 구간
    m = re.search(r"\[[\s\S]*\]", s)
    return m.group(0) if m else s


def _split_compound_token(token: str) -> List[str]:
    """
    긴 합성어 토큰을 2~4글자 서브토큰으로 분할.
    예: "즉사무림이유백" → ["즉사무림이유백", "즉사무림", "이유백", "즉사", "무림"]
    
    커뮤니티에서 "[작품약칭][캐릭터이름]" 형태로 붙여 쓰는 패턴 대응.
    """
    if len(token) < 5:
        return [token]
    
    results = [token]  # 원본 포함
    n = len(token)
    
    # 2~4글자 서브토큰 추출 (앞에서부터, 뒤에서부터)
    for size in [4, 3, 2]:
        if n >= size:
            # 앞에서 size글자
            front = token[:size]
            if front not in results:
                results.append(front)
            # 뒤에서 size글자
            back = token[-size:]
            if back not in results:
                results.append(back)
    
    # 5글자 이상이면 절반 분할도 시도 (예: 7글자 → 4+3 또는 3+4)
    if n >= 5:
        mid = n // 2
        for split_point in [mid, mid + 1, mid - 1]:
            if 2 <= split_point <= n - 2:
                left = token[:split_point]
                right = token[split_point:]
                if 2 <= len(left) <= 4 and left not in results:
                    results.append(left)
                if 2 <= len(right) <= 4 and right not in results:
                    results.append(right)
    
    return results


# 작품명/약칭이 아닐 가능성이 높은 일반 단어 (검색 시 필터링)
_COMMON_WORDS = {
    # 일반 명사
    "오늘", "내일", "어제", "이번", "다음", "지금", "나중", "처음", "마지막",
    "아침", "저녁", "오전", "오후", "새벽", "낮에", "밤에",
    "날씨", "밥먹", "점심", "저녁", "아침", "간식", "야식",
    "회사", "학교", "집에", "방에", "회의", "출근", "퇴근",
    "친구", "가족", "부모", "형제", "동생", "언니", "오빠", "누나",
    # 일반 동사/형용사
    "좋다", "싫다", "크다", "작다", "많다", "적다", "빠르", "느리",
    "맛있", "맛없", "예쁘", "이쁘", "멋있", "귀엽",
    "힘들", "쉽다", "어렵", "재밌", "지루", "슬프", "기쁘",
    # 일반 부사/감탄사
    "진짜", "정말", "너무", "매우", "완전", "엄청", "겁나", "존나",
    "그냥", "그래", "아니", "응응", "네네", "글쎄",
    # 커뮤니티 일반어
    "ㅋㅋㅋ", "ㅎㅎㅎ", "ㅠㅠㅠ", "ㅜㅜㅜ", "ㄷㄷㄷ", "ㄹㅇ",
    "아싸", "개꿀", "실화", "레전드", "ㄹㅈㄷ",
}


def _is_common_word(token: str) -> bool:
    """일반적인 단어(작품명이 아닐 가능성 높음)인지 확인"""
    if not token:
        return True
    # 정확히 일치하거나, 토큰이 일반 단어로 시작/끝나는 경우
    if token in _COMMON_WORDS:
        return True
    for cw in _COMMON_WORDS:
        if token.startswith(cw) or token.endswith(cw):
            return True
    return False


def _extract_title_prefix_tokens(post_title: str) -> List[str]:
    """
    제목 시작 부분에서 작품명 후보 토큰 추출.
    예: "즉사무림이유백 미래가 벌써 보이네" → ["즉사무림이유백", "즉사무림", "이유백", ...]
    예: "스포) 즉사무림 예상된 전개" → ["즉사무림"]
    
    일반 단어(날씨, 밥먹 등)는 제외.
    """
    if not post_title:
        return []
    
    # 접두사 제거 (스포), (약스포), 스포) 등
    cleaned = re.sub(r"^[\(\[]?\s*(스포|약스포|약후기|후기|결말|완결)\s*[\)\]]?\s*", "", post_title, flags=re.IGNORECASE)
    cleaned = cleaned.strip()
    
    if not cleaned:
        return []
    
    # 첫 번째 공백/특수문자 이전의 연속된 한글 추출
    match = re.match(r"^([가-힣]+)", cleaned)
    if not match:
        return []
    
    first_token = match.group(1)
    if len(first_token) < 2:
        return []
    
    # 일반 단어인지 체크 - 전체 토큰이 일반 단어면 빈 리스트 반환
    if _is_common_word(first_token):
        return []
    
    # 합성어 분할
    subtokens = _split_compound_token(first_token)
    # 서브토큰 중 일반 단어 제외
    return [t for t in subtokens if not _is_common_word(t)]


def _extract_alias_candidates(
    post_title: str,
    post_texts: List[str],
    comments: List[str],
) -> List[str]:
    """
    '정식 제목인지 확정이 아닌' 축약/별칭 후보를 뽑는다.
    - 주로 2~4글자 한글 토큰(예: 빌환/죽깨수/약먹마) 또는 혼용 표기
    - 너무 일반적인 단어/감탄사는 제외
    - 제목 첫 부분의 합성어는 분할하여 서브토큰도 추출
    """
    blob = " ".join([post_title or ""] + (post_texts or []) + (comments or []))
    if not blob.strip():
        return []

    # 0) 제목 첫 부분에서 작품명 후보 추출 (합성어 분할 포함)
    title_prefix_tokens = _extract_title_prefix_tokens(post_title)
    
    # 1) 2~4글자 한글 토큰(붙어있는 축약어) 후보
    raw_short = re.findall(r"[가-힣]{2,4}", blob)
    # 2) 5~20글자 제목/구절 후보(띄어쓰기 포함). 예: "돌마늘 기우제"
    raw_phrase = re.findall(r"[가-힣][가-힣\s]{3,19}[가-힣]", blob)
    raw = (raw_short or []) + (raw_phrase or []) + title_prefix_tokens
    if not raw:
        return []
        return []

    # 매우 흔한 잡토큰/감탄사/욕설류(최소) + 기능어(동사/조사성)
    # NOTE: 여기 stop은 "검색 가드레일을 발동시키면 안되는" 일반어/감탄사/기능어 위주
    stop = {
        # 일반 부사/감탄사
        "그냥", "진짜", "오늘", "이번", "이제는", "됐다", "가자", "저거", "이거",
        "너무", "빨리", "나름", "정말", "완전", "거의", "아직", "이미", "계속",
        "항상", "자주", "가끔", "아마", "아무래도", "어쨌든", "하여튼",
        # 일반 형용사/동사 (게시글에서 자주 나오는 일반어)
        "행복한", "좋구나", "불쌍해", "불쌍", "예상된", "예상한", "예상",
        "생각보다", "생각한", "좋긴", "싫긴", "재밌", "재미있", "지루",
        "죽이고", "살리고", "보여줘서", "보여주", "만들듯", "있으면", "없으면",
        "좋았", "싫었", "봤는데", "읽었", "썼는데",
        # 커뮤니티 메타
        "막화", "최신화", "결말", "감상", "스포", "다운", "회차",
        "시리즈", "광고", "광고보고", "왜이", "뭐냐", "뭐야", "뭐임",
        # 이모티콘/반응
        "ㅋㅋ", "ㅇㅇ", "ㄹㅇ", "ㄷㄷ", "ㅠㅠ", "ㅜㅜ",
        # 욕설류
        "시발", "존나", "개웃", "좆같", "좆밥",
        # 일반 명사/기능어
        "표지", "변경", "추천", "추천좀", "추천해", "추천해줘",
        "부탁", "부탁좀", "보니까", "같다", "뜻임", "이게",
        "갤러", "갤리", "장르", "소설", "작품", "작가",
        # 일반 동사/형용사 어간 (자주 오탐되는 것들)
        "전개긴하", "전개", "무섭네", "개무섭네", "문제", "효과", "한데", "해서",
        "위해", "사실", "살짝", "울컥", "생긴", "받는거", "찍긴", "하나", "써라",
        "써야댐", "현판이나", "신들", "창작물에", "따위로",
    }

    # 후보를 점수화해서 '축약어/별칭' 가능성이 높은 것부터 반환
    title_text = post_title or ""
    freq: Dict[str, int] = {}
    for t in raw:
        t = re.sub(r"\s+", " ", t).strip()
        if not t:
            continue
        freq[t] = freq.get(t, 0) + 1

    scored: List[tuple[int, str]] = []
    for t, c in freq.items():
        if t in stop:
            continue
        # 이미 사전 키/값에 있는 경우는 alias 후보에서 제외(룰에서 이미 처리됨)
        if t in SLANG_DICTIONARY or t in SLANG_DICTIONARY.values():
            continue
        if len(t) < 2 or len(t) > 20:
            continue

        score = 0
        no_space = (" " not in t)
        if t in title_text:
            score += 5
        # 2~4글자 무공백 토큰은 축약어일 가능성이 높음
        if no_space and 2 <= len(t) <= 4:
            score += 5
        # 띄어쓰기 포함 구절은 후보로는 두되 우선순위 낮춤(밈/티키타카 가능성)
        if not no_space:
            score -= 2
        score += min(3, c)  # 반복 등장 가중치
        scored.append((score, t))

    scored.sort(key=lambda x: (-x[0], len(x[1]), x[1]))
    out: List[str] = []
    for _, t in scored:
        # 조사/어미로 끝나는 흔한 형태 제거(오탐 방지)
        if re.search(r"(은|는|이|가|을|를|도|만|랑|처럼|같은|같다|임|냐|냐\\?|임\\?|보소|보니까)$", t):
            continue
        out.append(t)
        if len(out) >= 6:
            break
    return out


def _is_recommendation_request(post_title: str, post_texts: List[str]) -> bool:
    """
    '추천좀/추천해줘' 등 다수 작품을 찾는 요청 글은 단일 official_title로 확정하면 오탐이 된다.
    """
    blob = " ".join([(post_title or "")] + (post_texts or []))
    blob = blob.replace(" ", "")
    return any(k in blob for k in ("추천좀", "추천해줘", "추천해", "추천부탁", "추천"))


def _contains_korean(text: Optional[str]) -> bool:
    if not text or not isinstance(text, str):
        return False
    return bool(re.search(r"[가-힣]", text))

def _korean_ratio_ok(text: str) -> bool:
    """
    영어 문장에 한글 토큰만 몇 개 섞인 경우를 한국어로 오인하지 않기 위한 휴리스틱.
    - 라틴 문자가 한글보다 많으면 한국어로 보지 않는다.
    """
    if not isinstance(text, str) or not text:
        return False
    hangul = len(re.findall(r"[가-힣]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if hangul == 0:
        return False
    return latin <= hangul


def _reason_needs_korean_retry(reason: Optional[str]) -> bool:
    if not reason or not isinstance(reason, str):
        return False
    # 영어 비중이 높거나 한글이 거의 없는 reason은 재시도
    if (not _korean_ratio_ok(reason)) and re.search(r"[A-Za-z]", reason):
        return True
    return False


def _normalize_korean_fields(
    final_output: OutputItemModel,
    *,
    from_llm: bool,
) -> Tuple[OutputItemModel, Optional[str]]:
    """
    모델이 규칙을 위반해 영어로 type/topic/reason을 내보내는 경우가 있어 최소한의 호스트 후처리로 한국어를 보장한다.
    """
    # reason: "LLM 출력이 영어로 나온 경우"만 교정(룰의 'Noise/Unknown'까지 다 위반 처리하면 너무 시끄러움)
    original_reason: Optional[str] = None
    if from_llm and final_output.reason and isinstance(final_output.reason, str):
        if (not _korean_ratio_ok(final_output.reason)) and re.search(r"[A-Za-z]", final_output.reason):
            original_reason = final_output.reason
            final_output.reason = "한국어 reason 규칙 위반(원문은 trace 로그 참고)"

    # inference type/topic (LLM이 영어 라벨을 자주 사용)
    inf = getattr(final_output, "inference", None)
    if from_llm and inf is not None:
        try:
            t = getattr(inf, "type", None)
            topic = getattr(inf, "topic", None)
            mapping = {
                "Character Analysis": "캐릭터 분석",
                "Title Discussion": "작품 언급",
                "Title Recommendation": "작품 추천",
                "Recommended Novel": "작품 추천",
                "Recommendation": "추천",
                "Title Request": "제목 요청",
                "Concept / Trope Discussion": "클리셰/개념 담론",
            }
            if isinstance(t, str) and (not _korean_ratio_ok(t)) and re.search(r"[A-Za-z]", t):
                setattr(inf, "type", mapping.get(t, "담론"))
            if isinstance(topic, str) and (not _korean_ratio_ok(topic)) and re.search(r"[A-Za-z]", topic):
                setattr(inf, "topic", "주제(원문 영어)")
        except Exception:
            pass
    return final_output, original_reason


def _parse_llm_list_text(llm_text: str) -> Optional[List[dict]]:
    parsed = json.loads(_extract_json_list_text(llm_text))
    if isinstance(parsed, list) and parsed:
        if all(isinstance(x, str) for x in parsed):
            recovered: List[dict] = []
            for x in parsed:
                try:
                    obj = json.loads(x)
                    if isinstance(obj, dict):
                        recovered.append(obj)
                except Exception:
                    continue
            if recovered:
                return recovered
        if all(isinstance(x, dict) for x in parsed):
            return parsed
    return None


def _extract_request_title_candidates(comments: List[str]) -> List[str]:
    """
    추천/요청 글에서 "댓글로 나온 후보 작품명"만 추려 Stage2 detected_titles로 사용한다.
    - URL/짤/감탄/욕설 등은 제외
    - 너무 짧거나 일반어는 제외
    """
    stop = {
        "ㅇㅇ",
        "ㅇㅇ1",
        "ㅋㅋ",
        "ㅋ",
        "ㄹㅇ",
        "ㄴㄴ",
        "ㄱㅊ",
        "ㄱㅅ",
        "감사",
        "고마워",
        "저질러버렸다",
        "아,저질러버렸다",
    }
    out: List[str] = []
    for c in comments or []:
        s = (c or "").strip()
        if not s:
            continue
        if "http://" in s or "https://" in s:
            continue
        # 너무 길면(설명문) 후보로 보기 어려움
        if len(s) > 40:
            continue
        if s in stop:
            continue
        # 한글이 거의 없는 후보 제외
        if not re.search(r"[가-힣]", s):
            continue
        # 공백 포함 문장은 보통 설명/드립이라 제외(원하면 추후 포함)
        if " " in s:
            continue
        # 최소 길이
        if len(s) < 4:
            continue
        if s not in out:
            out.append(s)
    return out[:5]


def _build_request_analysis(post: PostInput, comments: List[str]) -> PickvelAnalysis:
    post_text = " ".join([post.title or ""] + _post_texts(post) + (comments or []))
    is_nsfw = any(k in (post_text or "") for k in ("성인", "19", "야설", "TS난교", "난교"))
    micro_tags: List[str] = []
    if is_nsfw:
        micro_tags.append("성인요소_언급")
    # 추천/요청글은 기본적으로 담론 태그를 과하게 뽑지 않는다.
    candidates = _extract_request_title_candidates(comments)
    detected_titles = [{"official_title": t, "confidence": "Low"} for t in candidates]
    return PickvelAnalysis(
        detected_titles=detected_titles,
        micro_tags=micro_tags,
        sentiment_profile={"pacing": "Unknown", "drift_risk": "Unknown", "sentiment": "Unknown"},
        is_nsfw=bool(is_nsfw),
        user_segment=None,
        notes="추천/요청 게시글: 댓글에 나온 후보만 Low로 기록(단일 작품 확정 금지).",
    )


def _apply_recommendation_request_guardrail(
    post: PostInput,
    post_texts: List[str],
    final_output: OutputItemModel,
) -> OutputItemModel:
    """
    추천/요청 글을 단일 작품 identity로 확정하는 오탐을 방지한다.
    - is_relevant는 유지(true)하되 novel_identity/evidence는 비운다.
    - Stage2에서 detected_titles로 '언급된 후보'를 뽑을 수 있게 한다.
    """
    if not _is_recommendation_request(post.title, post_texts):
        return final_output
    # 단순 요청성 글이면 단일 작품 확정 금지
    final_output.is_relevant = True
    final_output.novel_identity = None
    final_output.evidence = None
    # slang은 남길 가치가 낮아서 제거(원하면 추후 유지 가능)
    final_output.slang_insight = None
    final_output.inference = Inference(type="추천 요청", topic="추천/탐색 게시글")
    final_output.reason = "추천/요청 게시글로 단일 작품을 확정할 수 없음"
    return final_output


def _filter_micro_tags(tags: List[str]) -> List[str]:
    """
    Stage2가 댓글 드립/닉네임/잡토큰을 micro_tags로 뽑는 것을 방지하기 위해,
    허용된 마이크로태그만 통과시키는 후처리.
    """
    allow = {
        # pacing/구조
        "고구마",
        "사이다",
        "4드론",
        "드리프트",
        "드리프트_의심",
        "후집피",
        # 장르/하위담론(순화)
        "아카데미물",
        "정실_논쟁",
        "캣파이트",
        "분양",
        "킬링타임",
        "양판소",
        "착각계",
        "헌터물",
        "무협",
        "퓨전무협",
        "하렘",
        "순애",
        # 성인/자극(순화된 태그만)
        "성인요소_언급",
        "자극적_표현",
    }
    out: List[str] = []
    for t in tags or []:
        if not isinstance(t, str):
            continue
        t = t.strip()
        if t in allow and t not in out:
            out.append(t)
    return out


def _has_strong_alias_candidate(alias_candidates: List[str]) -> bool:
    """
    alias_candidates가 있어도 대부분은 '너무/예상된/좋구나' 같은 일반어라서
    그걸로 강제 검색하면 검색결과가 오염되고 LLM이 Noise로 도망가는 문제가 생김.
    강제 검색은 "짧은 축약어(2~4)" 또는 "제목처럼 보이는 구절(공백 포함)"일 때만 한다.
    """
    # _extract_alias_candidates의 stop과 동일한 의도(강제 검색을 막아야 하는 일반어)
    hard_stop = {
        # 일반 부사/감탄사
        "그냥", "진짜", "오늘", "이번", "이제는", "됐다", "가자", "저거", "이거",
        "너무", "빨리", "나름", "정말", "완전", "거의", "아직", "이미", "계속",
        "항상", "자주", "가끔", "아마", "아무래도", "어쨌든", "하여튼",
        # 일반 형용사/동사 (게시글에서 자주 나오는 일반어)
        "행복한", "좋구나", "불쌍해", "불쌍", "예상된", "예상한", "예상",
        "생각보다", "생각한", "좋긴", "싫긴", "재밌", "재미있", "지루",
        "죽이고", "살리고", "보여줘서", "보여주", "만들듯", "있으면", "없으면",
        "좋았", "싫었", "봤는데", "읽었", "썼는데",
        # 커뮤니티 메타
        "막화", "최신화", "결말", "감상", "스포", "다운", "회차",
        "시리즈", "광고", "광고보고", "왜이", "뭐냐", "뭐야", "뭐임",
        # 이모티콘/반응
        "ㅋㅋ", "ㅇㅇ", "ㄹㅇ", "ㄷㄷ", "ㅠㅠ", "ㅜㅜ",
        # 욕설류
        "시발", "존나", "개웃", "좆같", "좆밥",
        # 일반 명사/기능어
        "표지", "변경", "추천", "추천좀", "추천해", "추천해줘",
        "부탁", "부탁좀", "보니까", "같다", "뜻임", "이게",
        "갤러", "갤리", "장르", "소설", "작품", "작가",
        # 일반 동사/형용사 어간 (자주 오탐되는 것들)
        "전개긴하", "전개", "무섭네", "개무섭네", "문제", "효과", "한데", "해서",
        "위해", "사실", "살짝", "울컥", "생긴", "받는거", "찍긴", "하나", "써라",
        "써야댐", "현판이나", "신들", "창작물에", "따위로",
    }
    for t in alias_candidates or []:
        if not isinstance(t, str):
            continue
        t = t.strip()
        if not t:
            continue
        if t in hard_stop:
            continue
        if " " not in t and 2 <= len(t) <= 4:
            return True
        if " " in t and 5 <= len(t) <= 20:
            return True
    return False


def run_batch(
    batch: BatchInput,
    use_search: bool = True,
    use_llm: bool = False,
    trace: bool = False,
    llm_client: Optional[LLMClient] = None,
    limit: Optional[int] = None,
    agentic_search: bool = False,
    output_schema: str = "v1",
    analyze_metadata: bool = False,
    incremental_output_path: Optional[Path] = None,  # 각 항목 처리 후 즉시 저장
) -> List[OutputItem]:
    comment_map: Dict[int, List[str]] = {}
    for comment in batch.comments:
        comment_map.setdefault(comment.post_id, []).append(comment.content)

    mcp_client = MCPClient() if use_search else None
    if use_llm and llm_client is None:
        llm_client = LLMClient()
    # output_schema=v2이면 PickvelOutputItemV2가 들어간 list를 반환한다.
    # typing 호환을 위해 반환 타입은 List[OutputItem]로 두되, 실제 런타임 객체는 v2일 수 있다.
    outputs: List[Any] = []
    # incremental 저장용 (원본 + 분석 결과 포함)
    full_outputs: List[Dict[str, Any]] = []

    total = len(batch.posts)
    if limit is not None:
        total = min(total, max(0, int(limit)))
    
    # incremental 저장 시 파일 초기화
    if incremental_output_path:
        incremental_output_path.parent.mkdir(parents=True, exist_ok=True)
        incremental_output_path.write_text("[\n", encoding="utf-8")

    for idx, post in enumerate(batch.posts):
        if limit is not None and idx >= limit:
            break
        comments = comment_map.get(post.post_id, [])
        search_title = None
        if trace:
            print(
                f"\n{'='*60}\n[{_ts()}][진행] ({idx+1}/{max(1,total)}) post_id={post.post_id} 처리 시작\n[{_ts()}][진행] 제목: {post.title if post.title else '(없음)'}",
                file=sys.stderr,
            )
        # 기존 방식: 파이프라인이 URL을 감지하면 선제적으로 MCP 검색
        # agentic_search=True면 이 블록을 건너뛰고, LLM이 스스로 검색 필요/검색어를 제안하도록 한다.
        if use_search and mcp_client and (not agentic_search):
            for comment in comments:
                url_candidate = _extract_url_candidate(comment)
                if url_candidate:
                    if trace:
                        print(
                            f"[trace] post_id={post.post_id} (선제) 링크 감지 → 검색: {url_candidate}",
                            file=sys.stderr,
                        )
                    search_title = _lookup_title_from_url(mcp_client, url_candidate)
                    if search_title:
                        break

        rule_output = apply_rules(
            post_id=post.post_id,
            post_title=post.title,
            post_texts=_post_texts(post),
            comments=comments,
            search_title=search_title,
        )

        if trace:
            print(
                f"[{_ts()}][trace] post_id={post.post_id} 규칙 판정: {rule_output.model_dump(exclude_none=True)}",
                file=sys.stderr,
            )

        final_output: OutputItemModel = rule_output
        from_llm = False
        post_texts = _post_texts(post)
        is_req = _is_recommendation_request(post.title, post_texts)
        if use_llm and llm_client and rule_output.reason in ("Unknown",):
            alias_candidates = _extract_alias_candidates(post.title, _post_texts(post), comments)
            title_prefix_subtokens = _extract_title_prefix_tokens(post.title)
            llm_payload = [
                {
                    "post": post.model_dump(),
                    "comments": comments,
                    "rule_output": rule_output.model_dump(exclude_none=True),
                    "alias_candidates": alias_candidates,
                    "title_prefix_subtokens": title_prefix_subtokens,  # LLM이 합성어 분할 후보를 보고 판단
                    "rules_config": {
                        "novel_sites": list(NOVEL_SITES),
                        "slang_dictionary": SLANG_DICTIONARY,
                        "trope_terms": TROPE_TERMS,
                        "noise_terms": list(NOISE_TERMS),
                        "priority": [
                            "Evidence from comments (URL or [Title])",
                            "Dictionary alias hint (requires independent evidence before title resolution)",
                            "Trope/unknown capture",
                            "Noise filter",
                        ],
                    },
                    "note": "Apply the provided rules_config strictly. Return ONLY a JSON LIST matching the schema.",
                }
            ]

            if agentic_search and use_search and mcp_client:
                # LLM이 먼저 "검색 필요/검색어"를 JSON으로 제안 -> 우리가 MCP 검색 실행 -> search_results를 붙여 최종 LLM 호출
                try:
                    max_rounds = int(os.getenv("LLM_MAX_SEARCH_ROUNDS", "2"))
                    max_q = int(os.getenv("LLM_MAX_SEARCH_QUERIES", "3"))
                except Exception:
                    max_rounds, max_q = 2, 3

                search_results = []
                for r in range(max_rounds):
                    if trace:
                        print(f"[{_ts()}][trace] post_id={post.post_id} 검색 계획 수립(round={r+1})", file=sys.stderr)
                    plan = llm_client.plan_search(llm_payload)
                    if trace:
                        try:
                            plan_s = json.dumps(plan, ensure_ascii=False)
                        except Exception:
                            plan_s = str(plan)
                        print(f"[{_ts()}][trace] post_id={post.post_id} 검색 계획 출력: {plan_s}", file=sys.stderr)
                    need = bool(plan.get("need_search")) if isinstance(plan, dict) else False
                    queries = plan.get("queries") if isinstance(plan, dict) else None
                    why = plan.get("why", "") if isinstance(plan, dict) else ""
                    post_type = plan.get("post_type", "") if isinstance(plan, dict) else ""
                    
                    # LLM이 명시적으로 분류한 post_type으로 가드레일 스킵 여부 결정
                    # author_banter: 작가 비평/조롱 글 (작가명을 검색해도 작품 식별 불가)
                    skip_guardrail = post_type in ("general_discussion", "recommendation", "author_banter", "noise")
                    
                    # 가드레일:
                    # - rule_output=Unknown + alias_candidates가 있는데 need_search=false면,
                    #   "정식 제목인지 확인 안함" 문제가 생기므로 호스트가 강제로 검색을 수행한다.
                    # - 단, LLM이 specific_work가 아닌 다른 유형으로 판단했거나, Round 2+ 이미 검색 결과가 있으면 스킵
                    if (not need or not queries) and _has_strong_alias_candidate(alias_candidates) and not skip_guardrail and r == 0 and not search_results:
                        need = True
                        # 기본 쿼리 생성(짧고 효과적인 것 위주)
                        # 우선순위: 제목 첫 부분 서브토큰(2~4글자) > 일반 alias_candidates
                        # 제목 첫 부분에서 추출한 서브토큰 우선 사용
                        title_prefix_tokens = _extract_title_prefix_tokens(post.title)
                        # 2~4글자 토큰만 필터링하여 우선 검색 (축약어일 가능성 높음)
                        priority_terms = [t for t in title_prefix_tokens if 2 <= len(t) <= 4]
                        # 나머지 alias_candidates 중 2~4글자
                        other_terms = [t for t in alias_candidates if 2 <= len(t) <= 4 and t not in priority_terms]
                        search_terms = (priority_terms + other_terms)[:3]  # 최대 3개
                        
                        q_list = []
                        for term in search_terms:
                            # 먼저 일반 검색 (나무위키, 커뮤니티 해설 등 넓은 범위)
                            q_list.append(f"{term} 웹소설")
                            # 나무위키에서 웹소설 용어 해설 찾기
                            q_list.append(f"site:namu.wiki {term}")
                            # 소설 플랫폼 검색
                            q_list.append(f"site:munpia.com {term}")
                            q_list.append(f"site:novelpia.com {term}")
                            if len(q_list) >= max_q * 2:  # 후보를 많이 확보 후 앞에서 자름
                                break
                        queries = q_list[:max_q]
                        if trace:
                            print(
                                f"[trace] post_id={post.post_id} 가드레일: 제목토큰={priority_terms}, 별칭후보={other_terms} → 강제 검색",
                                file=sys.stderr,
                            )
                    elif (not need or not queries) and skip_guardrail:
                        if trace:
                            print(
                                f"[trace] post_id={post.post_id} post_type={post_type} → 검색 스킵",
                                file=sys.stderr,
                            )
                    elif (not need or not queries) and search_results:
                        if trace:
                            print(
                                f"[trace] post_id={post.post_id} 이미 검색 결과 있음 → 추가 검색 스킵",
                                file=sys.stderr,
                            )
                    if not need or not queries:
                        break

                    q_list = []
                    for q in queries:
                        if not isinstance(q, str):
                            continue
                        q = q.strip()
                        if q and q not in q_list:
                            q_list.append(q)
                        if len(q_list) >= max_q:
                            break
                    if not q_list:
                        break

                    if trace:
                        print(f"[{_ts()}][trace] post_id={post.post_id} 검색 필요 → 쿼리: {q_list}", file=sys.stderr)

                    for q in q_list:
                        if trace:
                            print(f"[{_ts()}][trace] post_id={post.post_id} MCP 검색 실행: {q}", file=sys.stderr)
                        try:
                            sr = mcp_client.search(q)
                        except Exception as exc:
                            sr = {"error": str(exc), "results": []}
                        compact = _compact_search_response(sr if isinstance(sr, dict) else {"query": q, "results": []})
                        if not compact.get("query"):
                            compact["query"] = q
                        if trace:
                            _trace_search_summary(post.post_id, q, compact)
                        search_results.append(compact)

                    llm_payload[0]["search_results"] = search_results

                    # Round 1 이후 좋은 결과가 있으면 Round 2 스킵
                    if r == 0 and _has_good_search_results(search_results, list(NOVEL_SITES)):
                        if trace:
                            print(f"[{_ts()}][trace] post_id={post.post_id} Round 1에서 좋은 결과 발견 → Round 2 스킵", file=sys.stderr)
                        break

                # === 점진적 분석 (Iterative Analysis) ===
                # 검색 후 바로 enrich 하지 않고, 중간 분석 → 추가 검색 → enrich 순서로 진행
                incremental_analysis = os.getenv("INCREMENTAL_ANALYSIS", "1") == "1"
                
                if incremental_analysis and search_results and alias_candidates:
                    try:
                        incremental_max_rounds = int(os.getenv("INCREMENTAL_MAX_ROUNDS", "2"))
                    except Exception:
                        incremental_max_rounds = 2
                    
                    detected_term = alias_candidates[0] if alias_candidates else None
                    
                    for inc_round in range(incremental_max_rounds):
                        if trace:
                            print(
                                f"[{_ts()}][trace] post_id={post.post_id} 점진적 분석 round={inc_round + 1}/{incremental_max_rounds}",
                                file=sys.stderr,
                            )
                        
                        # 중간 분석: 현재 검색 결과로 가설 생성
                        hypothesis_payload = {
                            "post": llm_payload[0].get("post", {}),
                            "detected_term": detected_term,
                            "search_results": search_results,
                            "alias_candidates": alias_candidates,
                        }
                        
                        hypothesis = llm_client.generate_hypothesis(hypothesis_payload)
                        
                        if trace:
                            try:
                                hyp_preview = json.dumps(hypothesis, ensure_ascii=False)[:300]
                                print(
                                    f"[{_ts()}][trace] post_id={post.post_id} 가설 생성: {hyp_preview}",
                                    file=sys.stderr,
                                )
                            except Exception:
                                pass
                        
                        # 가설 분석
                        hyp_data = hypothesis.get("hypothesis", {})
                        needs_verification = hyp_data.get("needs_verification", False)
                        verification_query = hyp_data.get("verification_query")
                        hyp_confidence = hyp_data.get("confidence", "None")
                        
                        # High 이상 confidence면 추가 검색 불필요
                        if hyp_confidence in ("High", "Max"):
                            if trace:
                                print(
                                    f"[{_ts()}][trace] post_id={post.post_id} 가설 confidence={hyp_confidence} → 추가 검색 스킵",
                                    file=sys.stderr,
                                )
                            # 가설 정보를 llm_payload에 추가하여 enrich에서 활용
                            llm_payload[0]["hypothesis"] = hypothesis
                            break
                        
                        # 추가 검색 필요
                        if needs_verification and verification_query and mcp_client:
                            if trace:
                                print(
                                    f"[{_ts()}][trace] post_id={post.post_id} 가설 검증 검색: {verification_query}",
                                    file=sys.stderr,
                                )
                            
                            try:
                                sr_verify = mcp_client.search(verification_query)
                                compact_verify = _compact_search_response(
                                    sr_verify if isinstance(sr_verify, dict)
                                    else {"query": verification_query, "results": []}
                                )
                                if not compact_verify.get("query"):
                                    compact_verify["query"] = verification_query
                                
                                if trace:
                                    _trace_search_summary(post.post_id, verification_query, compact_verify)
                                
                                # 새 검색 결과 추가
                                search_results.append(compact_verify)
                                llm_payload[0]["search_results"] = search_results
                                
                            except Exception as exc_verify:
                                if trace:
                                    print(
                                        f"[{_ts()}][trace] post_id={post.post_id} 검증 검색 오류: {exc_verify}",
                                        file=sys.stderr,
                                    )
                                break
                        else:
                            # 추가 검색 불필요하면 가설 정보만 전달
                            llm_payload[0]["hypothesis"] = hypothesis
                            break
                    
                    if trace:
                        print(
                            f"[{_ts()}][trace] post_id={post.post_id} 점진적 분석 완료, 검색 결과 총 {len(search_results)}개",
                            file=sys.stderr,
                        )
                # === 점진적 분석 끝 ===

            if trace:
                print(f"[{_ts()}][trace] post_id={post.post_id} LLM 판단 시작", file=sys.stderr)
                if getattr(llm_client, "stream", False):
                    print(f"[{_ts()}][trace] post_id={post.post_id} LLM 토큰 스트리밍(실시간)", file=sys.stderr)

            try:
                start = time.time()
                stop_event = threading.Event()
                progress_every = float(os.getenv("LLM_PROGRESS_EVERY", "5"))
                # local stream 모드면 하트비트는 의미가 없으니 끔
                if getattr(llm_client, "stream", False):
                    progress_every = 0

                def _heartbeat() -> None:
                    # keep printing while the request is running
                    while not stop_event.wait(progress_every):
                        elapsed = int(time.time() - start)
                        print(
                            f"[{_ts()}][trace] post_id={post.post_id} LLM 처리중... 경과={elapsed}s",
                            file=sys.stderr,
                        )

                hb_thread: Optional[threading.Thread] = None
                if trace and progress_every > 0:
                    hb_thread = threading.Thread(target=_heartbeat, daemon=True)
                    hb_thread.start()

                llm_text = llm_client.enrich_text(llm_payload)
                stop_event.set()
                if hb_thread:
                    hb_thread.join(timeout=0.2)

                if trace:
                    elapsed = time.time() - start
                    print(
                        f"[{_ts()}][trace] post_id={post.post_id} LLM 완료. 경과={elapsed:.1f}s",
                        file=sys.stderr,
                    )
                    usage = getattr(llm_client, "last_usage", None)
                    if isinstance(usage, dict) and usage:
                        pt = usage.get("prompt_tokens")
                        ct = usage.get("completion_tokens")
                        tt = usage.get("total_tokens")
                        speed = None
                        try:
                            if ct is not None and elapsed > 0:
                                speed = float(ct) / float(elapsed)
                        except Exception:
                            speed = None
                        extra = f" 토큰사용량(prompt={pt}, completion={ct}, total={tt})"
                        if speed is not None:
                            extra += f" 생성속도={speed:.2f} tok/s"
                        print(
                            f"[{_ts()}][trace] post_id={post.post_id} LLM 메타:{extra}",
                            file=sys.stderr,
                        )
                    if getattr(llm_client, "stream", False):
                        # stream 모드에서는 이미 stderr로 토큰이 출력되므로, raw 전문을 다시 찍지 않는다.
                        preview = (llm_text or "").replace("\r", "").strip()
                        print(f"[{_ts()}][trace] post_id={post.post_id} LLM raw (전체 {len(llm_text)}자):\n{preview}", file=sys.stderr)
                    else:
                        print(f"[{_ts()}][trace] post_id={post.post_id} LLM raw:\n{llm_text}", file=sys.stderr)

                parsed = _parse_llm_list_text(llm_text)
                if parsed:
                    final_output = OutputItemModel.model_validate(parsed[0])
                    from_llm = True

                    # === Deep Research 스타일 반복 검증 ===
                    # 안전장치: 최대 깊이 제한, 중복 쿼리 방지
                    try:
                        deep_research_max_depth = int(os.getenv("DEEP_RESEARCH_MAX_DEPTH", "2"))
                    except Exception:
                        deep_research_max_depth = 2
                    
                    deep_research_start = time.time()
                    tried_queries: set = set()  # 중복 쿼리 방지
                    current_depth = 0
                    
                    # 1차 enrich 결과가 불확실하면 정제된 검색으로 재시도
                    detected_term = None
                    # alias_candidates에서 첫 번째 후보를 detected_term으로 사용
                    if alias_candidates:
                        detected_term = alias_candidates[0]
                    
                    while current_depth < deep_research_max_depth:
                        needs_refined, refined_query = _needs_refined_search(
                            final_output, search_results, list(NOVEL_SITES), detected_term
                        )
                        
                        if not needs_refined or not refined_query or not mcp_client:
                            break
                        
                        # 중복 쿼리 방지
                        if refined_query in tried_queries:
                            if trace:
                                print(
                                    f"[{_ts()}][trace] post_id={post.post_id} Deep Research: "
                                    f"중복 쿼리 스킵: {refined_query}",
                                    file=sys.stderr,
                                )
                            break
                        tried_queries.add(refined_query)
                        current_depth += 1
                        
                        if trace:
                            print(
                                f"[{_ts()}][trace] post_id={post.post_id} Deep Research: "
                                f"depth={current_depth}/{deep_research_max_depth}, "
                                f"elapsed={elapsed:.1f}s, query={refined_query}",
                                file=sys.stderr,
                            )
                        
                        # 정제된 검색 실행
                        try:
                            sr_refined = mcp_client.search(refined_query)
                            compact_refined = _compact_search_response(
                                sr_refined if isinstance(sr_refined, dict) 
                                else {"query": refined_query, "results": []}
                            )
                            if not compact_refined.get("query"):
                                compact_refined["query"] = refined_query
                            
                            if trace:
                                _trace_search_summary(post.post_id, refined_query, compact_refined)
                            
                            # 정제된 결과가 유효하면 search_results에 추가하고 재 enrich
                            refined_results = compact_refined.get("results", [])
                            has_novel_url = any(
                                any(site in r.get("url", "") for site in NOVEL_SITES)
                                for r in refined_results
                            )
                            
                            if has_novel_url:
                                search_results.append(compact_refined)
                                llm_payload[0]["search_results"] = search_results
                                llm_payload[0]["note"] = (
                                    (llm_payload[0].get("note") or "")
                                    + f"\nDEEP_RESEARCH_ROUND_{current_depth + 1}: 정제된 검색 결과가 추가됨. "
                                    "소설 플랫폼(munpia.com 등) 결과를 우선 참조하세요."
                                ).strip()
                                
                                if trace:
                                    print(
                                        f"[{_ts()}][trace] post_id={post.post_id} Deep Research: "
                                        f"소설 플랫폼 결과 발견 → {current_depth + 1}차 enrich 실행",
                                        file=sys.stderr,
                                    )
                                
                                # 재 enrich 실행
                                llm_text_n = llm_client.enrich_text(llm_payload)
                                parsed_n = _parse_llm_list_text(llm_text_n)
                                if parsed_n:
                                    final_output_n = OutputItemModel.model_validate(parsed_n[0])
                                    # 결과가 더 좋으면 채택
                                    novel_id_n = getattr(final_output_n, "novel_identity", None)
                                    if novel_id_n and getattr(novel_id_n, "official_title", None):
                                        prev_title = getattr(
                                            getattr(final_output, "novel_identity", None), 
                                            "official_title", None
                                        )
                                        final_output = final_output_n
                                        if trace:
                                            print(
                                                f"[{_ts()}][trace] post_id={post.post_id} Deep Research: "
                                                f"{current_depth + 1}차 결과 채택 "
                                                f"(official_title={getattr(novel_id_n, 'official_title', None)})",
                                                file=sys.stderr,
                                            )
                                        # official_title을 찾았으면 더 이상 검색 불필요
                                        break
                                    else:
                                        if trace:
                                            print(
                                                f"[{_ts()}][trace] post_id={post.post_id} Deep Research: "
                                                f"{current_depth + 1}차 결과도 official_title 없음 → 이전 결과 유지",
                                                file=sys.stderr,
                                            )
                            else:
                                if trace:
                                    print(
                                        f"[{_ts()}][trace] post_id={post.post_id} Deep Research: "
                                        "정제된 검색에서도 소설 플랫폼 결과 없음 → 중단",
                                        file=sys.stderr,
                                    )
                                break  # 더 검색해도 소용없음
                        except Exception as exc_refined:
                            if trace:
                                print(
                                    f"[{_ts()}][trace] post_id={post.post_id} Deep Research 오류: {exc_refined}",
                                    file=sys.stderr,
                                )
                            break
                    
                    if trace and current_depth > 0:
                        total_elapsed = time.time() - deep_research_start
                        print(
                            f"[{_ts()}][trace] post_id={post.post_id} Deep Research 완료: "
                            f"depth={current_depth}, elapsed={total_elapsed:.1f}s",
                            file=sys.stderr,
                        )
                    # === Deep Research 끝 ===

                    # reason이 영어로만 나오면 LLM에 "한국어 reason만" 다시 강제
                    if _reason_needs_korean_retry(getattr(final_output, "reason", None)):
                        if trace:
                            print(
                                f"[{_ts()}][trace] post_id={post.post_id} reason 한국어 재시도",
                                file=sys.stderr,
                            )
                        retry_payload = [dict(llm_payload[0])]
                        note = retry_payload[0].get("note") or ""
                        retry_payload[0]["note"] = (
                            note
                            + "\nKOREAN_ONLY_REASON: reason은 반드시 한국어로만 작성. 영어 알파벳(A-Z) 금지."
                        ).strip()
                        llm_text = llm_client.enrich_text(retry_payload)
                        parsed_retry = _parse_llm_list_text(llm_text)
                        if parsed_retry:
                            final_output = OutputItemModel.model_validate(parsed_retry[0])
                            from_llm = True
            except Exception as exc:
                if trace:
                    print(f"[{_ts()}][trace] post_id={post.post_id} LLM 오류: {exc}", file=sys.stderr)
                # keep rule output on any LLM failure

        # 호스트 후처리(추천/요청 글은 Stage1 결과가 무엇이든 단일 작품 확정 금지)
        final_output = _apply_recommendation_request_guardrail(
            post=post, post_texts=post_texts, final_output=final_output
        )
        final_output, original_reason = _normalize_korean_fields(final_output, from_llm=from_llm)
        if trace and from_llm:
            try:
                preview2 = json.dumps(final_output.model_dump(exclude_none=True), ensure_ascii=False)
                if len(preview2) > 500:
                    preview2 = preview2[:500] + f"...(truncated,len={len(preview2)})"
                print(
                    f"[trace] post_id={post.post_id} LLM 후처리 결과(미리보기): {preview2}",
                    file=sys.stderr,
                )
                if original_reason:
                    print(
                        f"[trace] post_id={post.post_id} reason 원문(영문): {original_reason}",
                        file=sys.stderr,
                    )
            except Exception:
                pass
        if trace and agentic_search:
            # LLM이 search_results를 근거로 채택한 URL이 있다면 표시
            ev = getattr(final_output, "evidence", None)
            if ev and getattr(ev, "found_in_comment", True) is False:
                src = getattr(ev, "source_text", None) or ""
                chosen_url = _extract_first_url(src)
                if chosen_url:
                    print(
                        f"[trace] post_id={post.post_id} LLM이 검색 근거로 채택: {chosen_url}",
                        file=sys.stderr,
                    )

        # 2단계(메타추출): stage1 식별 결과를 기반으로 PickvelAnalysis를 생성한다.
        analysis_obj: Optional[PickvelAnalysis] = None
        if analyze_metadata and use_llm and llm_client:
            # noise로 판정되면 분석 비용 대비 가치가 낮으므로 기본적으로 스킵
            if getattr(final_output, "is_relevant", False):
                if is_req:
                    analysis_obj = _build_request_analysis(post, comments)
                    if trace:
                        preview = json.dumps(analysis_obj.model_dump(exclude_none=True), ensure_ascii=False)
                        if len(preview) > 500:
                            preview = preview[:500] + f"...(truncated,len={len(preview)})"
                        print(f"[trace] post_id={post.post_id} 메타추출(요청글-호스트강제) 미리보기: {preview}", file=sys.stderr)
                else:
                    if trace:
                        print(f"[trace] post_id={post.post_id} 메타추출 시작", file=sys.stderr)
                    analyze_payload = [
                        {
                            "post": post.model_dump(),
                            "comments": comments,
                            "stage1_identity": final_output.model_dump(exclude_none=True),
                            "rules_config": {
                                # 2단계도 도메인/사전 일부를 참고할 수 있게 전달
                                "novel_sites": list(NOVEL_SITES),
                                "slang_dictionary": SLANG_DICTIONARY,
                                "trope_terms": TROPE_TERMS,
                                "noise_terms": list(NOISE_TERMS),
                                # Stage2 micro_tags는 이 어휘 안에서만 선택하도록 유도(추가 가드)
                                "micro_tag_vocab": [
                                    "고구마",
                                    "사이다",
                                    "4드론",
                                    "드리프트",
                                    "드리프트_의심",
                                    "후집피",
                                    "아카데미물",
                                    "정실_논쟁",
                                    "캣파이트",
                                    "분양",
                                    "킬링타임",
                                    "양판소",
                                    "착각계",
                                    "헌터물",
                                    "무협",
                                    "퓨전무협",
                                    "하렘",
                                    "순애",
                                    "성인요소_언급",
                                    "자극적_표현",
                                ],
                            },
                            "note": "Stage2: Extract micro_tags/sentiment/drift/nsfw/user_segment for Pickvel. Do not invent titles/urls.",
                        }
                    ]
                    try:
                        raw = llm_client.analyze_metadata(analyze_payload)
                        if isinstance(raw, dict) and raw:
                            analysis_obj = PickvelAnalysis.model_validate(raw)
                            # 후처리: micro_tags 화이트리스트 필터
                            analysis_obj.micro_tags = _filter_micro_tags(list(analysis_obj.micro_tags))
                        if trace:
                            preview = json.dumps(raw, ensure_ascii=False)
                            if len(preview) > 500:
                                preview = preview[:500] + f"...(truncated,len={len(json.dumps(raw, ensure_ascii=False))})"
                            print(f"[trace] post_id={post.post_id} 메타추출 결과(미리보기): {preview}", file=sys.stderr)
                    except Exception as exc:
                        if trace:
                            print(f"[trace] post_id={post.post_id} 메타추출 오류: {exc}", file=sys.stderr)

        if output_schema.lower() == "v2":
            identity = PickvelIdentity(
                is_relevant=final_output.is_relevant,
                novel_identity=final_output.novel_identity,
                evidence=final_output.evidence,
                slang_insight=final_output.slang_insight,
                inference=final_output.inference,
                reason=final_output.reason,
            )
            output_item = PickvelOutputItemV2(post_id=post.post_id, identity=identity, analysis=analysis_obj)
            outputs.append(output_item)
        else:
            output_item = final_output
            outputs.append(output_item)
        
        # Incremental 저장: 원본 데이터 + 분석 결과를 함께 저장
        if incremental_output_path:
            # 원본 포스트 데이터 구성
            post_texts_list = _post_texts(post)
            full_item = {
                "post_id": post.post_id,
                "title": post.title,
                "author": post.author,
                "created_at": post.created_at,
                "url": post.url,
                "content": post_texts_list,  # 텍스트 블록들
                "comments": comments,
                "analysis_result": output_item.model_dump(exclude_none=True) if hasattr(output_item, 'model_dump') else {},
            }
            full_outputs.append(full_item)
            
            # 파일에 즉시 append (pretty print)
            with incremental_output_path.open("a", encoding="utf-8") as f:
                if idx > 0:
                    f.write(",\n")
                json_str = json.dumps(full_item, ensure_ascii=False, indent=2)
                # 들여쓰기 조정 (배열 안이므로 2칸씩 추가)
                indented = "\n".join("  " + line for line in json_str.split("\n"))
                f.write(indented)
            
            if trace:
                print(f"[{_ts()}][저장] post_id={post.post_id} → {incremental_output_path.name}", file=sys.stderr)

        if trace:
            result_summary = "LLM" if from_llm else "규칙"
            is_rel = getattr(final_output, 'is_relevant', False)
            reason = getattr(final_output, 'reason', '')
            print(f"[{_ts()}][진행] ({idx+1}/{max(1,total)}) post_id={post.post_id} 처리 완료 [{result_summary}] → is_relevant={is_rel}, reason={reason}", file=sys.stderr)

    # incremental 저장 마무리 (JSON 배열 닫기)
    if incremental_output_path:
        with incremental_output_path.open("a", encoding="utf-8") as f:
            f.write("\n]\n")
        if trace:
            print(f"[{_ts()}][저장] ✅ 전체 {len(full_outputs)}건 저장 완료 → {incremental_output_path}", file=sys.stderr)

    return outputs  # type: ignore[return-value]


def load_batch_from_file(path: Path) -> BatchInput:
    items = _load_json_items(path)
    posts, comments = _partition_items(items)
    return BatchInput(posts=posts, comments=comments)


def load_batch_from_text(text: str) -> BatchInput:
    items = _load_json_items_from_text(text)
    posts, comments = _partition_items(items)
    return BatchInput(posts=posts, comments=comments)

