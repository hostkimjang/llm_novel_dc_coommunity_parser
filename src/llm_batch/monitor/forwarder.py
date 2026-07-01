"""
DashboardForwarder — expert_main 이벤트를 외부 standalone 대시보드로 전달

expert_main이 시작 시 외부 대시보드(tools/dashboard_server.py)를 감지하면
내장 대시보드 대신 이 forwarder를 monitor 싱글턴에 attach한다.
이후 monitor.emit()/add_log()가 enqueue()를 호출하고, 데몬 스레드가
배치로 모아 POST {base_url}/api/ingest 로 전송한다.

설계 원칙:
- 파이프라인을 절대 블록하지 않는다 (deque maxlen = drop-oldest).
- 외부 대시보드가 죽어도 드롭만 하고 계속 진행한다 (서킷 브레이커).
- 복구 시 상태 스냅샷 리싱크로 유실분을 치유한다 (expert_main 쪽
  MonitorState가 항상 정본이므로 가능).
- forwarder 자체 경고는 sys.__stderr__로만 출력한다 — sys.stderr는
  expert_main의 _Tee를 거쳐 monitor.add_log → enqueue로 재진입하는
  피드백 루프가 생기기 때문.
"""

from __future__ import annotations

import atexit
import json
import sys
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional

import httpx

# 유실되면 대시보드 표시가 깨지는 이벤트 — 큐를 크게 잡고 실패 시 재적재
_CRITICAL_EVENT_TYPES = frozenset({
    "batch_start",
    "batch_complete",
    "post_start",
    "post_complete",
    "llm_suspend",
    "llm_resume",
})


class DashboardForwarder:
    def __init__(
        self,
        base_url: str,
        *,
        monitor: Any = None,
        ingest_token: str = "",
        flush_interval: float = 0.5,
        heartbeat_interval: float = 2.0,
        snapshot_interval: float = 30.0,
        batch_max: int = 300,
        critical_maxlen: int = 20000,
        bulk_maxlen: int = 3000,
        request_timeout: float = 3.0,
        circuit_fail_threshold: int = 3,
        circuit_probe_interval: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._monitor = monitor
        self._ingest_token = ingest_token
        self._flush_interval = flush_interval
        self._heartbeat_interval = heartbeat_interval
        self._snapshot_interval = snapshot_interval
        self._batch_max = batch_max
        self._request_timeout = request_timeout
        self._circuit_fail_threshold = circuit_fail_threshold
        self._circuit_probe_interval = circuit_probe_interval

        self._lock = threading.Lock()
        self._critical: deque = deque(maxlen=critical_maxlen)
        self._bulk: deque = deque(maxlen=bulk_maxlen)
        self._seq = 0  # 배치 내 발행 순서 복원용 (critical/bulk 분리로 인한 역전 방지)

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._client: Optional[httpx.Client] = None

        self._fail_streak = 0
        self._circuit_open = False
        self._last_post_ts = 0.0
        self._last_snapshot_ts = 0.0
        self._last_warn_ts = 0.0
        self._dropped_bulk = 0
        self._stopped = False

    # ─── 외부 API ──────────────────────────────────────────

    def start(self) -> None:
        if self._thread is not None:
            return
        self._client = httpx.Client(timeout=self._request_timeout)
        self._thread = threading.Thread(target=self._run, daemon=True, name="dashboard-forwarder")
        self._thread.start()
        atexit.register(self.flush_and_stop)

    def enqueue(self, item: Dict[str, Any]) -> None:
        """monitor.emit/add_log에서 호출 — 절대 블록하지 않는다."""
        if self._stopped:
            return
        critical = item.get("kind") == "event" and item.get("type") in _CRITICAL_EVENT_TYPES
        with self._lock:
            item["_seq"] = self._seq
            self._seq += 1
            if critical:
                self._critical.append(item)
            else:
                if len(self._bulk) == self._bulk.maxlen:
                    self._dropped_bulk += 1
                self._bulk.append(item)

    def flush_and_stop(self, timeout: float = 5.0) -> None:
        """잔여 critical 큐(batch_complete 포함)를 전송 시도 후 종료."""
        if self._stopped:
            return
        self._stopped = True
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=max(0.1, timeout - 1.0))
        # 스레드가 미처 못 보낸 잔여 큐를 데드라인 내에서 반복 전송.
        # 첫 실패 시 예외로 탈출(대시보드가 죽어 있으면 즉시 포기).
        deadline = time.time() + max(0.5, timeout - 1.0)
        try:
            while time.time() < deadline:
                batch = self._drain_batch(limit=self._batch_max * 4)
                if not batch:
                    break
                self._post_items(batch)
            # 최종 스냅샷 — MonitorState가 정본이므로 드레인이 잘리거나 일부
            # 실패해도 batch_running 등 상태를 확정시킨다.
            snapshot = self._make_snapshot_item()
            if snapshot is not None:
                self._post_items([snapshot])
        except Exception:
            pass
        client = self._client
        if client is not None:
            try:
                client.close()
            except Exception:
                pass

    # ─── 내부 ──────────────────────────────────────────────

    def _warn(self, message: str) -> None:
        now = time.time()
        if now - self._last_warn_ts < 60.0:
            return
        self._last_warn_ts = now
        try:
            print(f"[dashboard-forwarder] {message}", file=sys.__stderr__, flush=True)
        except Exception:
            pass

    def _drain_batch(self, *, include_bulk: bool = True, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        limit = limit or self._batch_max
        items: List[Dict[str, Any]] = []
        with self._lock:
            while self._critical and len(items) < limit:
                items.append(self._critical.popleft())
            if include_bulk:
                while self._bulk and len(items) < limit:
                    items.append(self._bulk.popleft())
            dropped = self._dropped_bulk
            self._dropped_bulk = 0
        # 같은 플러시 윈도우 내 발행 순서 복원 — critical-우선 드레인은 보존
        # 정책일 뿐, 전송/적용 순서까지 뒤집으면 수신 측 _handle_event가
        # post_complete를 선행 expert_phase보다 먼저 적용하게 된다.
        items.sort(key=lambda i: i.get("_seq", 0))
        if dropped and items:
            items.append({
                "kind": "log",
                "line": f"[dashboard-forwarder] bulk 이벤트 {dropped}건 드롭(큐 포화)",
                "worker_id": -1,
            })
        return items

    def _requeue_critical(self, items: List[Dict[str, Any]]) -> None:
        criticals = [
            item
            for item in items
            if item.get("kind") == "event" and item.get("type") in _CRITICAL_EVENT_TYPES
        ]
        if not criticals:
            return
        with self._lock:
            self._critical.extendleft(reversed(criticals))

    def _post_items(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        assert self._client is not None
        headers = {"Content-Type": "application/json"}
        if self._ingest_token:
            headers["X-Ingest-Token"] = self._ingest_token
        body = json.dumps({"items": items}, ensure_ascii=False, default=str)
        resp = self._client.post(f"{self._base_url}/api/ingest", content=body, headers=headers)
        resp.raise_for_status()
        self._last_post_ts = time.time()
        try:
            return resp.json() or {}
        except Exception:
            return {}

    def _make_snapshot_item(self) -> Optional[Dict[str, Any]]:
        if self._monitor is None:
            return None
        try:
            status = self._monitor.get_status()
            # flow_log는 수신 측 load_status_snapshot이 읽지 않고, 순차 모드용
            # 리스트라 스냅샷 페이로드만 키운다 — 제외.
            status.pop("flow_log", None)
            status["batch_start_time"] = getattr(self._monitor, "batch_start_time", 0.0)
            # 요약 리스트는 클 수 있으므로 최근 500건만 — 진행률/카운트는
            # status의 done_count/relevant_count/noise_count 누계 카운터가 정본.
            summaries = getattr(self._monitor, "post_summaries", None)
            if isinstance(summaries, list):
                status["post_summaries"] = list(summaries[-500:])
            return {"kind": "status_snapshot", "data": status}
        except Exception:
            return None

    def _handle_response(self, payload: Dict[str, Any]) -> None:
        if not payload.get("resume_requested"):
            return
        try:
            from llm_batch.llm.client import request_llm_server_resume

            request_llm_server_resume(source="web_dashboard")
        except Exception as exc:
            self._warn(f"원격 resume 요청 처리 실패: {exc}")

    def _probe_health(self) -> bool:
        """복구 프로브 — health 핸드셰이크 + 빈 배치 ingest로 인증 경로까지 검증.

        standalone 플래그를 요구하는 이유: standalone이 죽은 사이 같은 포트를
        다른 expert_main의 내장 대시보드가 차지하면 교차 주입이 되기 때문.
        빈 배치 ingest를 함께 보내는 이유: 토큰 불일치(403) 시 프로브만 성공해
        서킷이 무한 플랩하며 bulk를 조용히 버리는 상태를 막기 위함.
        """
        assert self._client is not None
        try:
            resp = self._client.get(f"{self._base_url}/api/health", timeout=2.0)
            data = resp.json()
            if not (
                bool(data.get("ok"))
                and data.get("service") == "expert-pipeline-monitor"
                and bool(data.get("standalone"))
            ):
                return False
            self._post_items([])
            return True
        except Exception:
            return False

    def _run(self) -> None:
        while not self._stop.wait(self._flush_interval):
            try:
                if self._circuit_open:
                    # down 상태: 주기적 health 프로브만, 복구 시 스냅샷 리싱크
                    if time.time() - self._last_post_ts < self._circuit_probe_interval:
                        continue
                    self._last_post_ts = time.time()
                    if not self._probe_health():
                        continue
                    self._circuit_open = False
                    self._fail_streak = 0
                    # 스냅샷은 보존된 critical 백로그 '뒤'에 보내야 한다 —
                    # 앞에 보내면 스냅샷에 이미 반영된 post_complete 백로그가
                    # 다시 적용되며 중복된다(수신 측 dedupe가 2차 방어).
                    # _last_snapshot_ts를 리셋하면 아래 주기 스냅샷 블록이
                    # 이번 iteration의 드레인된 배치 끝에 스냅샷을 붙인다.
                    self._last_snapshot_ts = 0.0
                    self._warn("외부 대시보드 재연결 — 스냅샷 리싱크")

                batch = self._drain_batch()

                # 주기 스냅샷(드리프트 치유) — 평시 30초에 1회
                now = time.time()
                if now - self._last_snapshot_ts >= self._snapshot_interval:
                    self._last_snapshot_ts = now
                    snapshot = self._make_snapshot_item()
                    if snapshot is not None:
                        batch.append(snapshot)

                # 큐가 비어도 heartbeat 주기로 빈 배치 POST (resume piggyback 수신용)
                if not batch and now - self._last_post_ts < self._heartbeat_interval:
                    continue

                try:
                    payload = self._post_items(batch)
                except Exception as exc:
                    self._fail_streak += 1
                    self._requeue_critical(batch)
                    if (
                        isinstance(exc, httpx.HTTPStatusError)
                        and exc.response is not None
                        and exc.response.status_code == 403
                    ):
                        # 토큰 불일치/모드 불일치는 즉시 드러나야 하는 설정 오류
                        self._last_warn_ts = 0.0
                        self._warn(
                            "ingest 403 — DASHBOARD_INGEST_TOKEN을 양쪽 프로세스에 "
                            "동일하게 설정했는지, 대상이 standalone 대시보드인지 확인하세요"
                        )
                    if self._fail_streak >= self._circuit_fail_threshold:
                        self._circuit_open = True
                        self._warn(
                            f"외부 대시보드 전송 실패 {self._fail_streak}회 — "
                            f"드롭 모드 전환(critical은 보존, {self._circuit_probe_interval:.0f}s 간격 재시도): {exc}"
                        )
                    continue

                self._fail_streak = 0
                self._handle_response(payload)
            except Exception as exc:
                # forwarder는 어떤 경우에도 죽지 않는다
                self._warn(f"forwarder 루프 오류: {exc}")
