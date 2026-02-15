from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx


class MCPClient:
    def __init__(self, endpoint: Optional[str] = None, default_num_results: Optional[int] = None) -> None:
        self.endpoint = endpoint or os.getenv("MCP_ENDPOINT", "http://localhost:3333")
        self.default_num_results = default_num_results or int(os.getenv("MCP_DEFAULT_NUM_RESULTS", "10"))

    def search(self, query: str, num_results: Optional[int] = None) -> Dict[str, Any]:
        url = f"{self.endpoint.rstrip('/')}/mcp/search"
        payload = {
            "query": query,
            "num_results": num_results or self.default_num_results,
        }
        response = httpx.post(url, json=payload, timeout=20.0)
        response.raise_for_status()
        return response.json()

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

    def fetch(self, url: str, max_length: int = 2000) -> Optional[Dict[str, Any]]:
        """URL의 웹 페이지를 가져와서 텍스트와 구조적 정보를 반환한다.
        
        Returns:
            {url, domain, text, structured_info} 또는 실패 시 None
        """
        endpoint = f"{self.endpoint.rstrip('/')}/mcp/fetch"
        payload = {"url": url, "max_length": max_length}
        try:
            response = httpx.post(endpoint, json=payload, timeout=20.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

