from __future__ import annotations

import os
import time
import random
import threading
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit, urlunsplit

import httpx


_ENDPOINT_SELECT_LOCK = threading.Lock()
_ENDPOINT_SELECT_NEXT = 0
_CLIENT_ENDPOINT_BACKOFF_LOCK = threading.Lock()
_CLIENT_ENDPOINT_BACKOFF_UNTIL: Dict[str, float] = {}


def _parse_endpoints(raw: str) -> List[str]:
    endpoints: List[str] = []
    for part in (raw or "").split(","):
        endpoint = _normalize_endpoint(part)
        if endpoint and endpoint not in endpoints:
            endpoints.append(endpoint)
    return endpoints


def _normalize_endpoint(endpoint: str) -> str:
    raw = str(endpoint or "").strip().rstrip("/")
    if not raw:
        return ""
    normalize_localhost = os.getenv("MCP_NORMALIZE_LOCALHOST", "1").strip().lower() not in {"0", "false", "no", "off"}
    if not normalize_localhost:
        return raw
    try:
        parts = urlsplit(raw)
        if parts.hostname and parts.hostname.lower() == "localhost":
            netloc = "127.0.0.1"
            if parts.port:
                netloc = f"{netloc}:{parts.port}"
            return urlunsplit((parts.scheme or "http", netloc, parts.path, parts.query, parts.fragment)).rstrip("/")
    except Exception:
        pass
    return raw


def _select_endpoint(endpoints: List[str], strategy: str) -> str:
    global _ENDPOINT_SELECT_NEXT

    if not endpoints:
        return "http://127.0.0.1:3333"
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


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name, "1" if default else "0").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _readyz_payload_ok(payload: Dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    if str(payload.get("status") or "").lower() != "ok":
        return False
    return bool(
        payload.get("searxng")
        or payload.get("headless_search")
        or payload.get("direct_search_fallback")
    )


def _client_endpoint_backoff_sec() -> float:
    try:
        return max(5.0, min(float(os.getenv("MCP_CLIENT_ENDPOINT_BACKOFF_SEC", "90")), 3600.0))
    except Exception:
        return 90.0


def _mark_client_endpoint_backoff(endpoint: str) -> None:
    if not endpoint:
        return
    with _CLIENT_ENDPOINT_BACKOFF_LOCK:
        _CLIENT_ENDPOINT_BACKOFF_UNTIL[endpoint] = time.time() + _client_endpoint_backoff_sec()


def _is_client_endpoint_backed_off(endpoint: str) -> bool:
    if not endpoint:
        return False
    with _CLIENT_ENDPOINT_BACKOFF_LOCK:
        return _CLIENT_ENDPOINT_BACKOFF_UNTIL.get(endpoint, 0.0) > time.time()


class MCPClient:
    def __init__(self, endpoint: Optional[str] = None, default_num_results: Optional[int] = None) -> None:
        # 다중 MCP shard가 있을 때는 클라이언트 생성 시 1개를 골라 고정한다.
        # 이렇게 하면 한 워커의 search/fetch가 같은 shard를 타고, 뒤의 WARP 번들도 유지된다.
        raw_endpoints = (
            endpoint
            if endpoint is not None
            else (os.getenv("MCP_ENDPOINTS", "").strip() or os.getenv("MCP_ENDPOINT", "http://127.0.0.1:3333"))
        )
        parsed_endpoints = _parse_endpoints(raw_endpoints)
        self.endpoint_failover = _env_bool("MCP_CLIENT_ENDPOINT_FAILOVER", True)
        if endpoint is not None and self.endpoint_failover:
            # expert_main은 워커별 기본 shard를 단일 endpoint로 넘긴다. 런 중 shard가 죽으면
            # 같은 워커가 전체 MCP_ENDPOINTS pool 안에서 살아있는 shard로 우회할 수 있게 둔다.
            fallback_pool = _parse_endpoints(os.getenv("MCP_ENDPOINTS", ""))
            merged: List[str] = []
            for item in parsed_endpoints + fallback_pool:
                if item and item not in merged:
                    merged.append(item)
            self.endpoints = merged or parsed_endpoints
        else:
            self.endpoints = parsed_endpoints
        self.endpoint_strategy = os.getenv("MCP_ENDPOINT_STRATEGY", "round_robin")
        if endpoint is not None and parsed_endpoints:
            self.endpoint = parsed_endpoints[0]
        else:
            self.endpoint = _select_endpoint(self.endpoints, self.endpoint_strategy)
        self.default_num_results = default_num_results or int(os.getenv("MCP_DEFAULT_NUM_RESULTS", "10"))
        try:
            self.search_timeout_sec = max(3.0, min(float(os.getenv("MCP_CLIENT_SEARCH_TIMEOUT_SEC", "20")), 120.0))
        except Exception:
            self.search_timeout_sec = 20.0
        try:
            self.search_max_retries = max(0, min(int(os.getenv("MCP_CLIENT_SEARCH_MAX_RETRIES", "0")), 5))
        except Exception:
            self.search_max_retries = 0
        try:
            self.max_endpoints_per_search = max(
                1, min(int(os.getenv("MCP_CLIENT_MAX_ENDPOINTS_PER_SEARCH", "4")), 64)
            )
        except Exception:
            self.max_endpoints_per_search = 4
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

    def _candidate_endpoints(self) -> List[str]:
        endpoints: List[str] = []
        for item in [self.endpoint] + list(self.endpoints or []):
            item = _normalize_endpoint(item)
            if item and item not in endpoints:
                endpoints.append(item)
        if not endpoints:
            endpoints = ["http://127.0.0.1:3333"]
        if not self.endpoint_failover or len(endpoints) <= 1:
            return [endpoints[0]]

        active = [item for item in endpoints if not _is_client_endpoint_backed_off(item)]
        if active:
            return active
        return endpoints

    def search(self, query: str, num_results: Optional[int] = None, purpose: str = "") -> Dict[str, Any]:
        payload = {
            "query": query,
            "num_results": num_results or self.default_num_results,
            "purpose": purpose or "",
        }
        last_error: Optional[Exception] = None
        last_data: Optional[Dict[str, Any]] = None

        for endpoint in self._candidate_endpoints()[: self.max_endpoints_per_search]:
            url = f"{endpoint.rstrip('/')}/mcp/search"
            endpoint_degraded_empty = False
            endpoint_error = False
            for attempt in range(self.search_max_retries + 1):
                try:
                    response = httpx.post(url, json=payload, timeout=self.search_timeout_sec)
                    response.raise_for_status()
                    data = response.json()
                    if not isinstance(data, dict):
                        return {"query": query, "results": [], "total": 0}

                    results = data.get("results", [])
                    degraded = bool(data.get("degraded") or data.get("possible_throttle"))
                    if (
                        self.search_retry_on_degraded_empty
                        and isinstance(results, list)
                        and len(results) == 0
                        and degraded
                    ):
                        last_data = data
                        endpoint_degraded_empty = True
                        if attempt < self.search_max_retries:
                            sleep_sec = (self.search_retry_backoff_ms / 1000.0) * (attempt + 1)
                            time.sleep(sleep_sec)
                            continue
                        break

                    self.endpoint = endpoint
                    return data
                except httpx.HTTPError as exc:
                    last_error = exc
                    endpoint_error = True
                    if attempt >= self.search_max_retries:
                        break
                    sleep_sec = (self.search_retry_backoff_ms / 1000.0) * (attempt + 1)
                    time.sleep(sleep_sec)
                except Exception as exc:  # JSON parse 등 비HTTP 에러도 1회 재시도 허용
                    last_error = exc
                    endpoint_error = True
                    if attempt >= self.search_max_retries:
                        break
                    sleep_sec = (self.search_retry_backoff_ms / 1000.0) * (attempt + 1)
                    time.sleep(sleep_sec)

            if self.endpoint_failover and (endpoint_error or endpoint_degraded_empty):
                _mark_client_endpoint_backoff(endpoint)
                continue

        if last_data is not None:
            return last_data

        if last_error:
            raise last_error
        return {"query": query, "results": [], "total": 0}

    def health_check(self, timeout: float = 5.0, include_search: bool = True) -> Dict[str, Any]:
        """SearXNG/MCP Bridge 연결 상태를 확인한다.

        Returns:
            {"ok": True/False, "latency_ms": float, "error": str|None}
        """
        import time as _time

        try:
            max_search_latency_ms = max(1.0, float(os.getenv("MCP_HEALTH_SEARCH_MAX_LATENCY_MS", "8000")))
        except Exception:
            max_search_latency_ms = 8000.0
        try:
            min_search_results = max(0, int(os.getenv("MCP_HEALTH_SEARCH_MIN_RESULTS", "1")))
        except Exception:
            min_search_results = 1
        health_search_query = os.getenv("MCP_HEALTH_SEARCH_QUERY", "test").strip() or "test"

        def _search_result_count(data: Dict[str, Any]) -> int:
            results = data.get("results")
            if isinstance(results, list):
                return len(results)
            try:
                return max(0, int(data.get("total") or 0))
            except Exception:
                return 0

        def _search_health_failure(
            *,
            bridge_latency: float,
            search_latency: float,
            data: Dict[str, Any],
        ) -> Optional[Dict[str, Any]]:
            result_count = _search_result_count(data)
            degraded = bool(data.get("degraded") or data.get("possible_throttle"))
            base = {
                "ok": False,
                "latency_ms": round(bridge_latency, 1),
                "search_latency_ms": round(search_latency, 1),
                "search_result_count": result_count,
                "search_min_results": min_search_results,
                "search_max_latency_ms": max_search_latency_ms,
                "search_degraded": degraded,
                "search_query": health_search_query,
            }
            if search_latency > max_search_latency_ms:
                return {
                    **base,
                    "error": (
                        f"Bridge OK but search too slow: {search_latency:.0f}ms "
                        f"> {max_search_latency_ms:.0f}ms"
                    ),
                }
            if result_count < min_search_results:
                suffix = " (degraded/throttled)" if degraded else ""
                return {
                    **base,
                    "error": (
                        f"Bridge OK but search returned too few results: "
                        f"{result_count} < {min_search_results}{suffix}"
                    ),
                }
            return None

        t0 = _time.perf_counter()
        try:
            # 1) /healthz 시도
            url_check = f"{self.endpoint.rstrip('/')}/healthz"
            resp = httpx.get(url_check, timeout=timeout)
            latency = (_time.perf_counter() - t0) * 1000
            if resp.status_code == 200:
                if not include_search:
                    if _env_bool("MCP_HEALTH_USE_READYZ", True):
                        try:
                            ready_url = f"{self.endpoint.rstrip('/')}/readyz"
                            ready_resp = httpx.get(ready_url, timeout=timeout)
                            if ready_resp.status_code != 404:
                                ready_payload = ready_resp.json() if ready_resp.content else {}
                                ready_ok = ready_resp.status_code == 200 and _readyz_payload_ok(ready_payload)
                                if not ready_ok:
                                    return {
                                        "ok": False,
                                        "latency_ms": round(latency, 1),
                                        "search_latency_ms": 0.0,
                                        "error": f"Bridge OK but readyz degraded: {ready_payload}",
                                        "readyz_status": ready_resp.status_code,
                                    }
                        except httpx.HTTPStatusError:
                            pass
                        except Exception as e:
                            return {
                                "ok": False,
                                "latency_ms": round(latency, 1),
                                "search_latency_ms": 0.0,
                                "error": f"Bridge OK but readyz failed: {e}",
                            }
                    return {
                        "ok": True,
                        "latency_ms": round(latency, 1),
                        "search_latency_ms": 0.0,
                        "error": None,
                        "search_skipped": True,
                    }
                # 실제 검색도 한 번 테스트
                t1 = _time.perf_counter()
                try:
                    search_data = self.search(health_search_query, num_results=1, purpose="health_check")
                    search_latency = (_time.perf_counter() - t1) * 1000
                    failure = _search_health_failure(
                        bridge_latency=latency,
                        search_latency=search_latency,
                        data=search_data if isinstance(search_data, dict) else {},
                    )
                    if failure:
                        return failure
                    return {
                        "ok": True,
                        "latency_ms": round(latency, 1),
                        "search_latency_ms": round(search_latency, 1),
                        "search_result_count": _search_result_count(search_data),
                        "search_min_results": min_search_results,
                        "search_max_latency_ms": max_search_latency_ms,
                        "search_degraded": bool(search_data.get("degraded") or search_data.get("possible_throttle")),
                        "search_query": health_search_query,
                        "error": None,
                    }
                except Exception as e:
                    return {"ok": False, "latency_ms": round(latency, 1), "error": f"Bridge OK but search failed: {e}"}
            # 2) /healthz가 404면 직접 검색으로 폴백
            t1 = _time.perf_counter()
            try:
                search_data = self.search(health_search_query, num_results=1, purpose="health_check")
                search_latency = (_time.perf_counter() - t1) * 1000
                failure = _search_health_failure(
                    bridge_latency=search_latency,
                    search_latency=search_latency,
                    data=search_data if isinstance(search_data, dict) else {},
                )
                if failure:
                    return failure
                return {
                    "ok": True,
                    "latency_ms": round(search_latency, 1),
                    "search_latency_ms": round(search_latency, 1),
                    "search_result_count": _search_result_count(search_data),
                    "search_min_results": min_search_results,
                    "search_max_latency_ms": max_search_latency_ms,
                    "search_degraded": bool(search_data.get("degraded") or search_data.get("possible_throttle")),
                    "search_query": health_search_query,
                    "error": None,
                }
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
        payload = {"url": url, "max_length": max_length}
        for endpoint in self._candidate_endpoints():
            fetch_url = f"{endpoint.rstrip('/')}/mcp/fetch"
            try:
                response = httpx.post(fetch_url, json=payload, timeout=50.0)
                response.raise_for_status()
                self.endpoint = endpoint
                return response.json()
            except Exception:
                if self.endpoint_failover:
                    _mark_client_endpoint_backoff(endpoint)
                continue
        return None
