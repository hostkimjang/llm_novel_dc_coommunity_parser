"""콘텐츠 트리밍 & BM25 기반 관련 청크 리트리벌.

긴 웹페이지(나무위키 234K chars 등)를 LLM 프롬프트에 안전하게 넣기 위해
BM25 스코어링으로 검색 쿼리와 관련 높은 청크만 선택한다.

Usage:
    from src.llm_batch.search.content_trim import smart_trim_content

    trimmed = smart_trim_content(long_text, query="주전무쌍 웹소설", max_chars=8000)
"""
from __future__ import annotations

import atexit
import math
import re
import threading
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 설정 상수
# ---------------------------------------------------------------------------
_DEFAULT_CHUNK_SIZE = 800      # 청크 1개의 최대 문자 수
_DEFAULT_OVERLAP = 80          # 청크 간 오버랩 문자 수
_DEFAULT_TOP_K = 10            # BM25로 선택할 상위 청크 수
_DEFAULT_MAX_CHARS = 8000      # 최종 출력 최대 문자 수

# 나무위키 등에서 핵심 정보가 담긴 섹션 헤더 (BM25 부스트 대상)
_PRIORITY_HEADERS_KO = frozenset([
    "기본 정보", "개요", "줄거리", "작가", "장르", "연재", "약칭",
    "등장인물", "등장 인물", "발매 현황", "설정", "평가", "시놉시스",
    "인물 소개", "주요 등장인물", "제목", "작품 정보", "연재 정보",
    "소개", "스토리", "시리즈", "관련 작품",
])
_TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]+")
_TRIM_POOL_LOCK = threading.Lock()
_TRIM_PROCESS_POOLS: Dict[int, ProcessPoolExecutor] = {}


def _shutdown_trim_process_pools() -> None:
    with _TRIM_POOL_LOCK:
        pools = list(_TRIM_PROCESS_POOLS.values())
        _TRIM_PROCESS_POOLS.clear()
    for pool in pools:
        try:
            pool.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass


atexit.register(_shutdown_trim_process_pools)


def _get_trim_process_pool(max_workers: int) -> ProcessPoolExecutor:
    workers = max(1, min(int(max_workers or 1), 8))
    with _TRIM_POOL_LOCK:
        pool = _TRIM_PROCESS_POOLS.get(workers)
        if pool is None:
            pool = ProcessPoolExecutor(max_workers=workers)
            _TRIM_PROCESS_POOLS[workers] = pool
        return pool


# ---------------------------------------------------------------------------
# 1) Chunking — 마크다운 섹션 + 고정 크기 분할
# ---------------------------------------------------------------------------
def _chunk_markdown(
    md: str,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    overlap: int = _DEFAULT_OVERLAP,
) -> List[Dict]:
    """마크다운을 섹션 헤더 경계 + 고정 크기로 청킹.

    Returns:
        [{"text": str, "header": str, "index": int, "char_len": int}, ...]
    """
    if not md:
        return []

    chunks: List[Dict] = []

    # 1차: 마크다운 헤더(#, ##, ###) 경계로 분할
    sections = re.split(r'\n(?=#{1,3}\s)', md)

    for sec_idx, section in enumerate(sections):
        header_match = re.match(r'^(#{1,3})\s+(.+)', section)
        header = header_match.group(2).strip() if header_match else f"section_{sec_idx}"

        body = section.strip()
        if not body:
            continue

        if len(body) <= chunk_size:
            chunks.append({
                "text": body,
                "header": header,
                "index": len(chunks),
                "char_len": len(body),
            })
        else:
            # 2차: 문장/개행 단위로 분할
            sentences = re.split(r'(?<=[.!?\n])\s+', body)
            current = ""
            for sent in sentences:
                sent = sent.strip()
                if not sent:
                    continue
                # 문장 경계가 거의 없는 긴 blob은 하드 슬라이스로 강제 분할
                while len(sent) > chunk_size:
                    if current.strip():
                        chunks.append({
                            "text": current.strip(),
                            "header": header,
                            "index": len(chunks),
                            "char_len": len(current.strip()),
                        })
                        current = ""
                    hard_chunk = sent[:chunk_size]
                    chunks.append({
                        "text": hard_chunk.strip(),
                        "header": header,
                        "index": len(chunks),
                        "char_len": len(hard_chunk.strip()),
                    })
                    step = max(1, chunk_size - overlap)
                    sent = sent[step:].strip()
                if not sent:
                    continue
                if len(current) + len(sent) > chunk_size and current:
                    chunks.append({
                        "text": current.strip(),
                        "header": header,
                        "index": len(chunks),
                        "char_len": len(current.strip()),
                    })
                    # 오버랩: 마지막 N자를 다음 청크에 포함
                    current = current[-overlap:] + " " + sent
                else:
                    current = (current + " " + sent) if current else sent
            if current.strip():
                chunks.append({
                    "text": current.strip(),
                    "header": header,
                    "index": len(chunks),
                    "char_len": len(current.strip()),
                })

    return chunks


# ---------------------------------------------------------------------------
# 2) BM25 Retrieval — 쿼리 관련 청크 선택
# ---------------------------------------------------------------------------
def _tokenize_ko(text: str) -> List[str]:
    """한국어 + 영문 어절 토큰화 + bigram."""
    words = _TOKEN_RE.findall(text.lower())
    bigrams = [f"{words[i]}_{words[i+1]}" for i in range(len(words) - 1)]
    return words + bigrams


def _smart_trim_job(payload: Dict[str, object]) -> str:
    return smart_trim_content(
        text=str(payload.get("text") or ""),
        query=str(payload.get("query") or ""),
        max_chars=int(payload.get("max_chars") or _DEFAULT_MAX_CHARS),
        chunk_size=int(payload.get("chunk_size") or _DEFAULT_CHUNK_SIZE),
        top_k=int(payload.get("top_k") or _DEFAULT_TOP_K),
    )


def _bm25_retrieve(
    query: str,
    chunks: List[Dict],
    top_k: int = _DEFAULT_TOP_K,
    k1: float = 1.5,
    b: float = 0.75,
) -> List[Dict]:
    """BM25 스코어링으로 쿼리와 관련 높은 청크 선택.

    한국어 형태소분석기 없이 어절+bigram으로 동작.
    핵심 섹션 헤더(개요, 줄거리 등)에 50% 부스트.
    """
    if not chunks or not query:
        return chunks[:top_k]

    query_tokens = _tokenize_ko(query)
    if not query_tokens:
        return chunks[:top_k]

    # 문서별 토큰 빈도
    doc_tokens_list = [_tokenize_ko(c["text"]) for c in chunks]
    doc_freqs = [Counter(dt) for dt in doc_tokens_list]
    doc_lens = [len(dt) for dt in doc_tokens_list]
    avg_dl = sum(doc_lens) / max(len(doc_lens), 1)

    N = len(chunks)

    # IDF
    idf: Dict[str, float] = {}
    for token in set(query_tokens):
        df = sum(1 for dt in doc_tokens_list if token in dt)
        idf[token] = math.log((N - df + 0.5) / (df + 0.5) + 1)

    # BM25 스코어
    scores: List[Tuple[float, int]] = []
    for i, chunk in enumerate(chunks):
        score = 0.0
        dl = doc_lens[i]
        for token in query_tokens:
            tf = doc_freqs[i].get(token, 0)
            if tf > 0:
                numerator = tf * (k1 + 1)
                denominator = tf + k1 * (1 - b + b * dl / max(avg_dl, 1))
                score += idf.get(token, 0) * numerator / denominator

        # 핵심 섹션 헤더 부스트
        header_lower = chunk["header"].lower().strip()
        if any(ph in header_lower for ph in _PRIORITY_HEADERS_KO):
            score *= 1.5

        # 첫 3개 세션(개요 부분) 약간 부스트
        if chunk["index"] < 3:
            score *= 1.2

        scores.append((score, i))

    # 상위 K개 선택 (원래 문서 순서 유지)
    scores.sort(reverse=True)
    selected_indices = sorted([idx for _, idx in scores[:top_k]])

    return [chunks[i] for i in selected_indices]


# ---------------------------------------------------------------------------
# 3) 공개 API — smart_trim_content
# ---------------------------------------------------------------------------
def smart_trim_content(
    text: str,
    query: str = "",
    max_chars: int = _DEFAULT_MAX_CHARS,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    top_k: int = _DEFAULT_TOP_K,
) -> str:
    """긴 텍스트를 BM25 기반으로 관련 청크만 추출하여 max_chars 이내로 트리밍.

    - text가 max_chars 이하이면 그대로 반환 (트리밍 불필요)
    - query가 비어있으면 앞부분 max_chars 단순 절단
    - query가 있으면 BM25 청킹 → 리트리벌 → 관련 청크 연결

    Args:
        text: 원본 텍스트 (예: crawl4ai 결과 234K chars)
        query: 검색 쿼리 (예: "주전무쌍 웹소설 작가")
        max_chars: 최종 출력 최대 문자 수
        chunk_size: 청크 1개 최대 문자 수
        top_k: BM25로 선택할 상위 청크 수

    Returns:
        트리밍된 텍스트 (max_chars 이내)
    """
    if not text:
        return ""

    # 이미 짧으면 그대로
    if len(text) <= max_chars:
        return text

    # 쿼리가 없으면 단순 절단 (앞부분 + 말줄임)
    if not query or not query.strip():
        return text[:max_chars - 20] + "\n...[TRIMMED]..."

    # BM25 청킹 + 리트리벌
    chunks = _chunk_markdown(text, chunk_size=chunk_size)
    if not chunks:
        return text[:max_chars - 20] + "\n...[TRIMMED]..."

    relevant = _bm25_retrieve(query, chunks, top_k=top_k)

    # 관련 청크를 연결하되 max_chars 이내로
    result_parts: List[str] = []
    total = 0
    for chunk in relevant:
        part = chunk["text"]
        if total + len(part) > max_chars:
            remaining = max_chars - total - 20
            if remaining > 100:
                result_parts.append(part[:remaining] + "...")
            break
        result_parts.append(part)
        total += len(part) + 4  # 구분자 \n---\n 길이 고려

    return "\n---\n".join(result_parts)


def smart_trim_contents_parallel(
    payloads: List[Dict[str, object]],
    *,
    max_workers: int = 2,
) -> List[str]:
    """여러 long text를 ProcessPool로 병렬 BM25 트리밍한다.

    payload 형식:
        {
            "text": str,
            "query": str,
            "max_chars": int,
            "chunk_size": int,
            "top_k": int,
        }
    """
    if not payloads:
        return []

    workers = max(1, min(int(max_workers or 1), len(payloads), 8))
    if workers <= 1 or len(payloads) <= 1:
        return [_smart_trim_job(p) for p in payloads]

    pool = _get_trim_process_pool(workers)
    futures = [pool.submit(_smart_trim_job, p) for p in payloads]
    return [f.result() for f in futures]


def trim_search_results_content(
    search_results: List[Dict],
    max_per_item: int = 6000,
    max_total: int = 40000,
) -> List[Dict]:
    """검색 결과 리스트의 content 필드를 트리밍.

    Decoder에 json.dumps로 전달하기 전에 호출하여
    토큰 오버플로를 예방한다.

    Args:
        search_results: 검색 결과 리스트 (각 항목에 content 필드)
        max_per_item: 항목당 content 최대 문자 수
        max_total: 전체 content 합산 최대 문자 수

    Returns:
        트리밍된 search_results (원본 수정 없이 복사본 반환)
    """
    if not search_results:
        return search_results

    import copy
    trimmed = copy.deepcopy(search_results)
    total_len = 0

    for item in trimmed:
        content = item.get("content") or ""

        # 항목별 제한
        if len(content) > max_per_item:
            content = content[:max_per_item - 20] + "\n...[CONTENT_TRIMMED]..."
            item["content"] = content

        total_len += len(content)

        # 전체 합산 제한 — 초과 시 이후 항목의 content 대폭 축소
        if total_len > max_total:
            excess = total_len - max_total
            if len(content) > excess + 200:
                item["content"] = content[:len(content) - excess - 20] + "\n...[TOTAL_LIMIT_TRIMMED]..."
            else:
                # content가 이미 짧으면 snippet만 남김
                snippet = item.get("snippet") or content[:300]
                item["content"] = snippet[:300] + "\n...[TOTAL_LIMIT]..."
            total_len = max_total  # 더 이상 누적 안 함

    return trimmed
