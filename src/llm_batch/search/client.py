from __future__ import annotations

import os
import time
import random
import threading
from typing import Any, Dict, List, Optional

import httpx


_ENDPOINT_SELECT_LOCK = threading.Lock()
_ENDPOINT_SELECT_NEXT = 0


def _parse_endpoints(raw: str) -> List[str]:
    endpoints: List[str] = []
    for part in (raw or "").split(","):
        endpoint = part.strip().rstrip("/")
        if endpoint and endpoint not in endpoints:
            endpoints.append(endpoint)
    return endpoints


def _select_endpoint(endpoints: List[str], strategy: str) -> str:
    global _ENDPOINT_SELECT_NEXT

    if not endpoints:
        return "http://localhost:3333"
    if len(endpoints) == 1:
        return endpoints[0]

    mode = (strategy or "round_robin").strip().lower()
    if mode == "random":
        return random.choice(endpoints)
    if mode == "first":
        return endpoints[0]

    with _ENDPOINT_SELECT_LOCK:
        idx = _ENDPOINT_SELECT_NEXT % len(endpoints)
        _ENDPOINT_SELECT_NEXT += 1
    return endpoints[idx]


class MCPClient:
    def __init__(self, endpoint: Optional[str] = None, default_num_results: Optional[int] = None) -> None:
        # 다중 MCP shard가 있을 때는 클라이언트 생성 시 1개를 골라 고정한다.
        # 이렇게 하면 한 워커의 search/fetch가 같은 shard를 타고, 뒤의 WARP 번들도 유지된다.
        raw_endpoints = (
            endpoint
            if endpoint is not None
            else (os.getenv("MCP_ENDPOINTS", "").strip() or os.getenv("MCP_ENDPOINT", "http://localhost:3333"))
        )
        self.endpoints = _parse_endpoints(raw_endpoints)
        self.endpoint_strategy = os.getenv("MCP_ENDPOINT_STRATEGY", "round_robin")
        self.endpoint = _select_endpoint(self.endpoints, self.endpoint_strategy)
        self.default_num_results = default_num_results or int(os.getenv("MCP_DEFAULT_NUM_RESULTS", "10"))
        try:
            self.search_max_retries = max(0, min(int(os.getenv("MCP_CLIENT_SEARCH_MAX_RETRIES", "2")), 5))
        except Exception:
            self.search_max_retries = 1
        try:
            self.search_retry_backoff_ms = max(
                50, min(int(os.getenv("MCP_CLIENT_SEARCH_RETRY_BACKOFF_MS", "250")), 5000)
            )
        except Exception:
            self.search_retry_backoff_ms = 250
        self.search_retry_on_degraded_empty = (
            os.getenv("MCP_CLIENT_SEARCH_RETRY_ON_DEGRADED_EMPTY", "1").strip().lower()
            in {"1", "true", "yes", "on"}
        )

    def search(self, query: str, num_results: Optional[int] = None, purpose: str = "") -> Dict[str, Any]:
        url = f"{self.endpoint.rstrip('/')}/mcp/search"
        payload = {
            "query": query,
            "num_results": num_results or self.default_num_results,
            "purpose": purpose or "",
        }
        last_error: Optional[Exception] = None
        for attempt in range(self.search_max_retries + 1):
            try:
                response = httpx.post(url, json=payload, timeout=20.0)
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    return {"query": query, "results": [], "total": 0}

                results = data.get("results", [])
                degraded = bool(data.get("degraded") or data.get("possible_throttle"))
                if (
                    self.search_retry_on_degraded_empty
                    and attempt < self.search_max_retries
                    and isinstance(results, list)
                    and len(results) == 0
                    and degraded
                ):
                    sleep_sec = (self.search_retry_backoff_ms / 1000.0) * (attempt + 1)
                    time.sleep(sleep_sec)
                    continue

                return data
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt >= self.search_max_retries:
                    break
                sleep_sec = (self.search_retry_backoff_ms / 1000.0) * (attempt + 1)
                time.sleep(sleep_sec)
            except Exception as exc:  # JSON parse 등 비HTTP 에러도 1회 재시도 허용
                last_error = exc
                if attempt >= self.search_max_retries:
                    break
                sleep_sec = (self.search_retry_backoff_ms / 1000.0) * (attempt + 1)
                time.sleep(sleep_sec)

        if last_error:
            raise last_error
        return {"query": query, "results": [], "total": 0}

    def health_check(self, timeout: float = 5.0) -> Dict[str, Any]:
        """SearXNG/MCP Bridge 연결 상태를 확인한다.

        Returns:
            {"ok": True/False, "latency_ms": float, "error": str|None}
        """
        import time as _time
        t0 = _time.perf_counter()
        try:
            # 1) /healthz 시도
            url_check = f"{self.endpoint.rstrip('/')}/healthz"
            resp = httpx.get(url_check, timeout=timeout)
            latency = (_time.perf_counter() - t0) * 1000
            if resp.status_code == 200:
                # 실제 검색도 한 번 테스트
                t1 = _time.perf_counter()
                try:
                    self.search("test", num_results=1)
                    search_latency = (_time.perf_counter() - t1) * 1000
                    return {"ok": True, "latency_ms": round(latency, 1), "search_latency_ms": round(search_latency, 1), "error": None}
                except Exception as e:
                    return {"ok": False, "latency_ms": round(latency, 1), "error": f"Bridge OK but search failed: {e}"}
            # 2) /healthz가 404면 직접 검색으로 폴백
            t1 = _time.perf_counter()
            try:
                self.search("test", num_results=1)
                search_latency = (_time.perf_counter() - t1) * 1000
                return {"ok": True, "latency_ms": round(search_latency, 1), "search_latency_ms": round(search_latency, 1), "error": None}
            except Exception as e:
                return {"ok": False, "latency_ms": round(latency, 1), "error": f"Bridge responded but search failed: {e}"}
        except httpx.ConnectError:
            latency = (_time.perf_counter() - t0) * 1000
            return {"ok": False, "latency_ms": round(latency, 1), "error": "연결 거부 — Docker 컨테이너(SearXNG/MCP Bridge)가 실행 중인지 확인하세요"}
        except httpx.TimeoutException:
            latency = (_time.perf_counter() - t0) * 1000
            return {"ok": False, "latency_ms": round(latency, 1), "error": f"타임아웃 ({timeout}s)"}
        except Exception as e:
            latency = (_time.perf_counter() - t0) * 1000
            return {"ok": False, "latency_ms": round(latency, 1), "error": str(e)}

    def fetch(self, url: str, max_length: int = 0) -> Optional[Dict[str, Any]]:
        """URL의 웹 페이지를 가져와서 텍스트와 구조적 정보를 반환한다.

        max_length=0 이면 길이 제한 없이 전문 반환.
        Crawl4AI 연동 후 Playwright 기반 렌더링이 포함되어
        기존 대비 더 풍부한 본문 콘텐츠(마크다운)를 반환한다.

        Returns:
            {url, domain, text, structured_info} 또는 실패 시 None
        """
        endpoint = f"{self.endpoint.rstrip('/')}/mcp/fetch"
        payload = {"url": url, "max_length": max_length}
        try:
            response = httpx.post(endpoint, json=payload, timeout=50.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None
