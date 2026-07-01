"""
Monitor Event Bus — 싱글턴 상태 추적 + SSE 브로드캐스트

expert_main.py / orchestrator.py 에서
    from llm_batch.monitor.event_bus import monitor
    monitor.emit("post_start", {...})
형태로 호출하면, 웹 대시보드에 SSE로 실시간 전달됩니다.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class PostSummary:
    """포스트 처리 결과 요약 (대시보드 표시용)"""
    post_id: int
    title: str
    is_relevant: Optional[bool] = None
    official_title: Optional[str] = None
    confidence: Optional[str] = None
    discussion_type: Optional[str] = None
    elapsed: float = 0.0
    status: str = "pending"  # pending / processing / done / error


class MonitorState:
    """
    프로세스 전역 싱글턴 — 배치 진행 상태를 인메모리로 추적하고
    SSE 구독자에게 이벤트를 브로드캐스트합니다.
    
    병렬 모드 지원: 동시에 여러 포스트를 추적합니다.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

        # 배치 상태
        self.batch_running: bool = False
        self.batch_start_time: float = 0.0
        self.total_posts: int = 0
        self.current_index: int = 0  # 1-based (순차 모드용)
        self.input_file: str = ""
        self.output_file: str = ""
        self.parallel_count: int = 1  # 병렬 워커 수
        self.llm_suspended: bool = False
        self.llm_suspend_message: str = ""
        self.llm_suspend_error: str = ""
        self.llm_suspend_failure_count: int = 0
        self.llm_suspend_threshold: int = 0
        self.llm_suspend_started_at: str = ""
        self.llm_suspend_resumed_at: str = ""

        # 현재 처리 중인 포스트 (순차 모드 호환용)
        self.current_post_id: Optional[int] = None
        self.current_post_title: str = ""
        self.current_expert: str = ""  # gatekeeper, discourse, ...
        self.current_expert_status: str = ""  # running / done

        # 🔥 병렬 모드: 동시 진행 중인 포스트들
        self.active_posts: Dict[int, Dict[str, Any]] = {}  # {post_id: {title, expert, status, worker_id, flow_log, ...}}

        # 토큰 통계 (누적)
        self.token_usage: Dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

        # 검색 캐시 통계
        self.search_hits: int = 0
        self.search_misses: int = 0

        # 포스트별 결과 요약
        self.post_summaries: List[Dict[str, Any]] = []
        # 누계 카운터 — len(post_summaries) 파생이 아닌 명시적 카운터.
        # standalone 대시보드가 런 도중 재시작되면 스냅샷 리싱크가 요약을
        # 최근 500건으로만 복원하는데, 진행률은 이 카운터로 정확히 유지된다.
        self.done_count: int = 0
        self.relevant_done_count: int = 0
        self.noise_done_count: int = 0
        # post_complete 중복 적용 방지 (forwarder at-least-once 재전송/스냅샷+백로그 중복)
        self._summary_post_ids: set = set()

        # 최근 로그 라인 (ring buffer)
        self._log_lines: List[str] = []
        self._max_log_lines: int = 500

        # 워커별 로그 라인 (병렬 모드용)
        self._worker_log_lines: Dict[int, List[str]] = {}  # worker_id → [lines]

        # 파이프라인 실행 흐름 로그 (현재 포스트 — 순차 모드용)
        self._flow_log: List[Dict[str, Any]] = []

        # ── 포스트별 로그 라인 (처리 로그 보기용) ──
        self._post_log_lines: Dict[int, List[str]] = {}  # post_id → [lines]
        self._active_post_by_worker: Dict[int, int] = {}  # worker_id → post_id (현재 처리 중)

        # SSE 구독자 큐 (loop, queue)
        # 브로드캐스트는 메인 스레드에서 오고, 소비는 uvicorn 이벤트루프 스레드에서 하므로
        # loop.call_soon_threadsafe를 사용하기 위해 loop를 함께 저장한다.
        self._subscribers: List[Tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = []
        self._sub_lock = threading.Lock()

        # ─ SSE 로그 쓰로틀링 (병렬 모드 성능 최적화) ─
        # 이 태그를 포함한 로그 라인은 SSE에서 제외 (로그 파일에는 기록됨)
        self._LOG_SSE_SKIP_TAGS: frozenset = frozenset({
            '[llm-debug]', '[llm-stream]', '[llm-usage]', '[llm-context]',
        })
        self._log_sse_last_ts: float = 0.0
        self._LOG_SSE_MIN_INTERVAL: float = 0.05  # 50ms 최소 간격

        # 외부 standalone 대시보드로의 이벤트 전달자 (None이면 내장 모드 — 비용 0)
        self._forwarder: Optional[Any] = None

    # ─── 외부 호출 API ────────────────────────────────────

    def attach_forwarder(self, forwarder: Any) -> None:
        """외부 대시보드 forwarder를 연결한다 (expert_main 외부 대시보드 모드)."""
        self._forwarder = forwarder

    def emit(self, event_type: str, data: Optional[Dict[str, Any]] = None) -> None:
        """이벤트를 발행하고 SSE 구독자에게 브로드캐스트"""
        data = data or {}
        self._handle_event(event_type, data)

        payload = {
            "type": event_type,
            "data": data,
            "ts": datetime.now().isoformat(),
        }
        self._broadcast(payload)

        if self._forwarder is not None:
            try:
                self._forwarder.enqueue(
                    {"kind": "event", "type": event_type, "data": data, "ts": payload["ts"]}
                )
            except Exception:
                pass

    def ingest_event(
        self,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
        ts: Optional[str] = None,
    ) -> None:
        """외부 프로세스(expert_main forwarder)가 보낸 이벤트를 주입한다.

        emit()을 재사용하지 않는 이유: 원본 ts 보존 + forwarder 재전달 차단.
        """
        data = data or {}
        self._handle_event(event_type, data)
        self._broadcast({
            "type": event_type,
            "data": data,
            "ts": ts or datetime.now().isoformat(),
        })

    def load_status_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """forwarder 스냅샷 리싱크: 누계 카운터/요약을 정본 상태로 덮어쓴다.

        대시보드 프로세스가 런 도중 재시작되면 그 사이 이벤트가 유실되는데,
        expert_main 쪽 MonitorState가 항상 정본이므로 주기 스냅샷으로 치유한다.
        """
        with self._lock:
            self.batch_running = bool(snapshot.get("batch_running", self.batch_running))
            self.total_posts = int(snapshot.get("total_posts", self.total_posts) or 0)
            self.current_index = int(snapshot.get("current_index", self.current_index) or 0)
            self.input_file = snapshot.get("input_file", self.input_file) or self.input_file
            self.output_file = snapshot.get("output_file", self.output_file) or self.output_file
            self.parallel_count = int(snapshot.get("parallel_count", self.parallel_count) or 1)
            tu = snapshot.get("token_usage")
            if isinstance(tu, dict):
                self.token_usage = {
                    "prompt_tokens": int(tu.get("prompt_tokens", 0) or 0),
                    "completion_tokens": int(tu.get("completion_tokens", 0) or 0),
                    "total_tokens": int(tu.get("total_tokens", 0) or 0),
                }
            self.search_hits = int(snapshot.get("search_hits", self.search_hits) or 0)
            self.search_misses = int(snapshot.get("search_misses", self.search_misses) or 0)
            if snapshot.get("batch_start_time"):
                try:
                    self.batch_start_time = float(snapshot["batch_start_time"])
                except Exception:
                    pass
            summaries = snapshot.get("post_summaries")
            if isinstance(summaries, list) and len(summaries) > len(self.post_summaries):
                self.post_summaries = list(summaries)
                self._summary_post_ids = {
                    s.get("post_id") for s in self.post_summaries
                    if isinstance(s, dict) and s.get("post_id") is not None
                }
            # 누계 카운터 복원 — 스냅샷이 정본(expert_main)에서 오므로 max 패턴.
            # 요약 리스트가 500건 캡으로 잘려도 진행률은 이 값으로 유지된다.
            self.done_count = max(self.done_count, int(snapshot.get("done_count", 0) or 0))
            self.relevant_done_count = max(
                self.relevant_done_count, int(snapshot.get("relevant_count", 0) or 0)
            )
            self.noise_done_count = max(
                self.noise_done_count, int(snapshot.get("noise_count", 0) or 0)
            )
            # LLM suspend 상태 복원 — suspend 도중 대시보드가 재시작돼도
            # 웹 resume 버튼(standalone 분기)이 계속 동작해야 한다.
            # 스냅샷은 point-in-time 정본이라 resume 이후 스냅샷은 False를
            # 실어 오므로 stale suspend가 부활할 위험이 없다.
            if "llm_suspended" in snapshot:
                self.llm_suspended = bool(snapshot.get("llm_suspended"))
                self.llm_suspend_message = str(snapshot.get("llm_suspend_message", "") or "")
                self.llm_suspend_error = str(snapshot.get("llm_suspend_error", "") or "")
                self.llm_suspend_failure_count = int(snapshot.get("llm_suspend_failure_count", 0) or 0)
                self.llm_suspend_threshold = int(snapshot.get("llm_suspend_threshold", 0) or 0)
                self.llm_suspend_started_at = str(snapshot.get("llm_suspend_started_at", "") or "")
                self.llm_suspend_resumed_at = str(snapshot.get("llm_suspend_resumed_at", "") or "")

    def _store_log_line(self, line: str, worker_id: int) -> None:
        """로그 라인을 링버퍼/워커별/포스트별 버퍼에 저장 (락 포함)."""
        with self._lock:
            self._log_lines.append(line)
            if len(self._log_lines) > self._max_log_lines:
                self._log_lines = self._log_lines[-self._max_log_lines:]
            # 워커별 저장 (병렬 모드)
            if worker_id >= 0:
                if worker_id not in self._worker_log_lines:
                    self._worker_log_lines[worker_id] = []
                wlog = self._worker_log_lines[worker_id]
                wlog.append(line)
                if len(wlog) > self._max_log_lines:
                    self._worker_log_lines[worker_id] = wlog[-self._max_log_lines:]
            # 포스트별 저장 (워커가 현재 처리 중인 포스트에 연결)
            if worker_id >= 0 and worker_id in self._active_post_by_worker:
                pid = self._active_post_by_worker[worker_id]
                if pid in self._post_log_lines:
                    self._post_log_lines[pid].append(line)

    def ingest_log(self, line: str, worker_id: int = -1) -> None:
        """외부 프로세스(forwarder)가 보낸 로그 라인을 주입한다.

        발신 측 add_log가 이미 skip-tag 필터 + 50ms 쓰로틀(≤20줄/s)을 적용한
        뒤에만 forwarder로 보내므로, 수신 측에서 같은 쓰로틀을 다시 걸면
        배치(0.5s 단위) 도착 시 첫 줄만 SSE에 살아남는다. 그래서 여기서는
        저장 + 무조건 브로드캐스트만 한다 (forwarder 재전달도 없음).
        """
        self._store_log_line(line, worker_id)
        self._broadcast({
            "type": "log",
            "data": {"line": line, "worker_id": worker_id},
            "ts": datetime.now().isoformat(),
        })

    def add_log(self, line: str, worker_id: int = -1) -> None:
        """로그 라인 추가 (대시보드 로그 탭용)

        Args:
            line: 로그 라인
            worker_id: 워커 ID (-1 = 메인 스레드)
        """
        self._store_log_line(line, worker_id)

        # SSE 최적화: verbose LLM 태그는 SSE에서 제외 (로그 파일/REST API로는 조회 가능)
        for tag in self._LOG_SSE_SKIP_TAGS:
            if tag in line:
                return

        # SSE 쓰로틀: 최소 간격 미만이면 건너뛰기 (폭주 방지)
        now = time.time()
        if now - self._log_sse_last_ts < self._LOG_SSE_MIN_INTERVAL:
            return
        self._log_sse_last_ts = now

        self._broadcast({
            "type": "log",
            "data": {"line": line, "worker_id": worker_id},
            "ts": datetime.now().isoformat(),
        })

        # 외부 대시보드 전달 — SSE와 동일한 skip-tag/쓰로틀을 상속한 위치
        if self._forwarder is not None:
            try:
                self._forwarder.enqueue({"kind": "log", "line": line, "worker_id": worker_id})
            except Exception:
                pass

    def get_status(self) -> Dict[str, Any]:
        """현재 상태 스냅샷 반환 (REST API용)"""
        with self._lock:
            elapsed = time.time() - self.batch_start_time if self.batch_running else 0
            # len(post_summaries) 대신 누계 카운터 — standalone 리싱크(요약 500건
            # 캡) 후에도 진행률이 정확하다. 내장 모드에서는 두 값이 항상 같다.
            done_count = max(self.done_count, len(self.post_summaries))
            avg_time = elapsed / done_count if done_count > 0 else 0
            remaining = (self.total_posts - done_count) * avg_time if done_count > 0 else 0

            relevant_count = self.relevant_done_count
            noise_count = self.noise_done_count

            return {
                "batch_running": self.batch_running,
                "total_posts": self.total_posts,
                "current_index": self.current_index,
                "done_count": done_count,
                "progress_pct": round(done_count / self.total_posts * 100, 1) if self.total_posts else 0,
                "elapsed_sec": round(elapsed, 1),
                "avg_sec_per_post": round(avg_time, 1),
                "eta_sec": round(remaining, 1),
                "current_post_id": self.current_post_id,
                "current_post_title": self.current_post_title,
                "current_expert": self.current_expert,
                "current_expert_status": self.current_expert_status,
                "token_usage": dict(self.token_usage),
                "search_hits": self.search_hits,
                "search_misses": self.search_misses,
                "relevant_count": relevant_count,
                "noise_count": noise_count,
                "input_file": self.input_file,
                "output_file": self.output_file,
                "flow_log": list(self._flow_log),
                # 🔥 병렬 모드 필드
                "parallel_count": self.parallel_count,
                "active_posts": {str(k): dict(v) for k, v in self.active_posts.items()},
                "llm_suspended": self.llm_suspended,
                "llm_suspend_message": self.llm_suspend_message,
                "llm_suspend_error": self.llm_suspend_error,
                "llm_suspend_failure_count": self.llm_suspend_failure_count,
                "llm_suspend_threshold": self.llm_suspend_threshold,
                "llm_suspend_started_at": self.llm_suspend_started_at,
                "llm_suspend_resumed_at": self.llm_suspend_resumed_at,
            }

    def get_results(
        self,
        offset: int = 0,
        limit: int = 200,
        order: str = "desc",
        q: str = "",
        relevance: str = "all",
    ) -> Dict[str, Any]:
        """완료된 포스트 요약 목록을 페이지 단위로 반환

        q: 제목/공식제목/post_id 부분일치 검색 (대소문자 무시)
        relevance: all | relevant | noise
        """
        with self._lock:
            items = list(self.post_summaries)

        if relevance == "relevant":
            items = [it for it in items if it.get("is_relevant")]
        elif relevance == "noise":
            items = [it for it in items if not it.get("is_relevant")]
        needle = str(q or "").strip().lower()
        if needle:
            def _match(it: Dict[str, Any]) -> bool:
                return (
                    needle in str(it.get("title") or "").lower()
                    or needle in str(it.get("official_title") or "").lower()
                    or needle in str(it.get("post_id") or "")
                )
            items = [it for it in items if _match(it)]

        if order == "desc":
            items = list(reversed(items))
        total = len(items)
        page = items[offset:offset + limit]
        return {
            "items": page,
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": offset + limit < total,
            "q": needle,
            "relevance": relevance,
        }

    def get_result_summary(self, post_id: int) -> Optional[Dict[str, Any]]:
        """특정 post_id의 요약 정보를 반환합니다."""
        with self._lock:
            for item in reversed(self.post_summaries):
                if item.get("post_id") == post_id:
                    return dict(item)
        return None

    def get_logs(self, n: int = 200, worker_id: int = -1) -> List[str]:
        """최근 로그 n줄
        
        Args:
            n: 반환할 최대 줄 수
            worker_id: -1=전체, 0+=해당 워커만
        """
        with self._lock:
            if worker_id >= 0 and worker_id in self._worker_log_lines:
                return self._worker_log_lines[worker_id][-n:]
            return self._log_lines[-n:]

    def get_post_logs(self, post_id: int) -> List[str]:
        """특정 post_id의 인메모리 처리 로그를 반환합니다.
        
        현재 실행 중이거나 최근 완료된 포스트의 로그를 반환합니다.
        """
        with self._lock:
            return list(self._post_log_lines.get(post_id, []))

    # ─── SSE 구독 ──────────────────────────────────────────

    def subscribe(self) -> asyncio.Queue:
        """SSE 구독자 등록, Queue 반환"""
        q: asyncio.Queue = asyncio.Queue(maxsize=1024)
        loop = asyncio.get_running_loop()
        with self._sub_lock:
            self._subscribers.append((loop, q))
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._sub_lock:
            self._subscribers = [(loop, sub_q) for loop, sub_q in self._subscribers if sub_q is not q]

    # ─── 내부 ──────────────────────────────────────────────

    def _handle_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """이벤트 타입에 따라 내부 상태 갱신 (병렬 모드 대응)"""
        with self._lock:
            if event_type == "batch_start":
                self.batch_running = True
                self.batch_start_time = time.time()
                self.total_posts = data.get("total", 0)
                self.input_file = data.get("input_file", "")
                self.output_file = data.get("output_file", "")
                self.parallel_count = data.get("parallel_count", 1)
                self.current_index = 0
                self.post_summaries = []
                self.done_count = 0
                self.relevant_done_count = 0
                self.noise_done_count = 0
                self._summary_post_ids = set()
                self.active_posts = {}
                self.token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                self.search_hits = 0
                self.search_misses = 0
                self._flow_log = []
                self._worker_log_lines = {}
                self._post_log_lines = {}
                self._active_post_by_worker = {}
                self.llm_suspended = False
                self.llm_suspend_message = ""
                self.llm_suspend_error = ""
                self.llm_suspend_failure_count = 0
                self.llm_suspend_threshold = 0
                self.llm_suspend_started_at = ""
                self.llm_suspend_resumed_at = ""

            elif event_type == "post_start":
                post_id = data.get("post_id")
                self.current_index = data.get("index", 0)
                self.current_post_id = post_id
                self.current_post_title = data.get("title", "")
                self.current_expert = ""
                self.current_expert_status = ""
                
                # 병렬 모드: active_posts에 추가
                if post_id is not None:
                    self.active_posts[post_id] = {
                        "post_id": post_id,
                        "title": data.get("title", ""),
                        "index": data.get("index", 0),
                        "worker_id": data.get("worker_id", 0),
                        "expert": "",
                        "expert_status": "",
                        "flow_log": [],
                    }
                    # 포스트별 로그 버퍼 초기화 및 워커 매핑
                    worker_id = data.get("worker_id", 0)
                    self._post_log_lines[post_id] = []
                    self._active_post_by_worker[worker_id] = post_id
                    # 오래된 로그 정리 (최대 200개 포스트 보관)
                    if len(self._post_log_lines) > 200:
                        oldest = list(self._post_log_lines.keys())[0]
                        del self._post_log_lines[oldest]
                
                # 순차 모드 호환: flow_log 초기화
                if self.parallel_count <= 1:
                    self._flow_log = []

            elif event_type == "expert_phase":
                expert = data.get("expert", "")
                status = data.get("status", "")
                post_id = data.get("post_id")
                
                # 순차 모드 호환
                self.current_expert = expert
                self.current_expert_status = status
                
                # 병렬 모드: 해당 포스트의 전문가 상태 갱신
                if post_id is not None and post_id in self.active_posts:
                    self.active_posts[post_id]["expert"] = expert
                    self.active_posts[post_id]["expert_status"] = status
                    if status == "running":
                        flow = self.active_posts[post_id]["flow_log"]
                        flow.append({
                            "expert": expert,
                            "recall": bool(data.get("recall")),
                            "from": data.get("from", ""),
                            "reason": data.get("reason", ""),
                        })
                        # recall이 많은 포스트에서 무한 누적되면 /api/status의
                        # active_posts(32개)가 수십 KB로 비대해진다 — 최근 30건만.
                        # 절단량은 flow_dropped로 남겨 프론트가 "앞 N단계 생략"을
                        # 표시할 수 있게 한다.
                        if len(flow) > 30:
                            dropped = len(flow) - 30
                            self.active_posts[post_id]["flow_dropped"] = (
                                self.active_posts[post_id].get("flow_dropped", 0) + dropped
                            )
                            del flow[:dropped]
                
                # 순차 모드: flow_log에도 기록
                # (병렬 모드에서는 프론트가 이 리스트를 쓰지 않는데도 런 내내
                #  무한 누적되어 status 스냅샷/SSE 페이로드를 비대하게 만들므로
                #  순차 모드로 게이트한다)
                if status == "running" and self.parallel_count <= 1:
                    self._flow_log.append({
                        "expert": expert,
                        "recall": bool(data.get("recall")),
                        "from": data.get("from", ""),
                        "reason": data.get("reason", ""),
                    })

            elif event_type == "post_complete":
                post_id = data.get("post_id")
                self.current_expert = ""
                self.current_expert_status = ""

                # 워커→포스트 로그 라우팅 매핑은 여기서 끊지 않는다.
                # post_complete 직후에 출력되는 완료 요약/토큰 라인까지 이
                # 포스트의 처리 로그에 수집되어야 "끝이 잘리는" 문제가 없다.
                # 같은 워커의 다음 post_start가 매핑을 자연히 교체한다.

                # flow_log 결정: 병렬 모드면 active_posts에서, 순차면 self._flow_log
                if post_id is not None and post_id in self.active_posts:
                    active_flow = self.active_posts[post_id].get("flow_log", [])
                    summary = self._make_post_summary(data)
                    summary["flow_log"] = list(active_flow)
                    if self.active_posts[post_id].get("flow_dropped"):
                        summary["flow_dropped"] = self.active_posts[post_id]["flow_dropped"]
                    # active_posts에서 제거
                    del self.active_posts[post_id]
                else:
                    summary = self._make_post_summary(data)
                    summary["flow_log"] = list(self._flow_log)

                # 중복 적용 방지: forwarder 재전송(at-least-once)이나 스냅샷+백로그
                # 중복으로 같은 post_complete가 두 번 들어와도 카운터/토큰이
                # 이중 가산되지 않는다. (내장 모드에서는 post_id가 중복 emit되지
                # 않으므로 동작 변화 없음)
                if post_id is not None and post_id in self._summary_post_ids:
                    return
                if post_id is not None:
                    self._summary_post_ids.add(post_id)

                self.post_summaries.append(summary)
                self.done_count += 1
                if data.get("is_relevant"):
                    self.relevant_done_count += 1
                else:
                    self.noise_done_count += 1

                # 토큰 누적
                tu = data.get("token_usage")
                if tu:
                    self.token_usage["prompt_tokens"] += tu.get("prompt_tokens", 0)
                    self.token_usage["completion_tokens"] += tu.get("completion_tokens", 0)
                    self.token_usage["total_tokens"] += tu.get("total_tokens", 0)

            elif event_type == "search_stats":
                self.search_hits = data.get("hits", 0)
                self.search_misses = data.get("misses", 0)

            elif event_type == "llm_suspend":
                self.llm_suspended = True
                self.llm_suspend_message = str(data.get("message", "") or "")
                self.llm_suspend_error = str(data.get("last_error", "") or "")
                self.llm_suspend_failure_count = int(data.get("failure_count", 0) or 0)
                self.llm_suspend_threshold = int(data.get("threshold", 0) or 0)
                self.llm_suspend_started_at = str(data.get("started_at", "") or "")
                self.llm_suspend_resumed_at = ""

            elif event_type == "llm_resume":
                self.llm_suspended = False
                self.llm_suspend_message = str(data.get("message", "") or "")
                self.llm_suspend_error = str(data.get("last_error", "") or "")
                self.llm_suspend_failure_count = int(data.get("failure_count", 0) or 0)
                self.llm_suspend_threshold = int(data.get("threshold", 0) or 0)
                self.llm_suspend_resumed_at = str(data.get("resumed_at", "") or "")

            elif event_type == "batch_complete":
                self.batch_running = False
                self.active_posts = {}
                self.llm_suspended = False

    def _make_post_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """브라우저에 보낼 최소 요약만 보관합니다."""
        return {
            "post_id": data.get("post_id"),
            "title": data.get("title", ""),
            "author": data.get("author"),
            "created_at": data.get("created_at"),
            "url": data.get("url"),
            "is_relevant": data.get("is_relevant"),
            "official_title": data.get("official_title"),
            "confidence": data.get("confidence"),
            "discussion_type": data.get("discussion_type"),
            "topicality": data.get("topicality"),
            "subtype": data.get("subtype"),
            "work_resolution": data.get("work_resolution"),
            "relevance_scope": data.get("relevance_scope"),
            "anchor_type": data.get("anchor_type"),
            "anchor_strength": data.get("anchor_strength"),
            "context_sources": data.get("context_sources"),
            "consistency_flags": data.get("consistency_flags"),
            "primary_work": data.get("primary_work"),
            "title_candidates": data.get("title_candidates"),
            "mentioned_works": data.get("mentioned_works"),
            "comparison_target": data.get("comparison_target"),
            "recommendation_candidates": data.get("recommendation_candidates"),
            "novel_identity": data.get("novel_identity"),
            "reason": data.get("reason"),
            "reason_lines": data.get("reason_lines"),
            "analysis_notes": data.get("analysis_notes"),
            "elapsed": data.get("elapsed"),
            "token_usage": data.get("token_usage"),
            "worker_id": data.get("worker_id"),
        }

    def _broadcast(self, payload: Dict[str, Any]) -> None:
        """모든 SSE 구독자에게 이벤트 전송"""
        if payload.get("type") == "post_complete":
            slim_data = self._make_post_summary(payload.get("data") or {})
            # SSE 발행본에서 대형 텍스트 필드 제거 — 라이브 테이블 행 렌더에
            # 쓰이지 않고, 상세 모달은 /api/results/{post_id}로 전체를 받는다.
            # (post_summaries 저장본에는 그대로 남는다)
            for heavy_key in ("reason", "reason_lines", "analysis_notes"):
                slim_data.pop(heavy_key, None)
            flow_log = (payload.get("data") or {}).get("flow_log")
            if flow_log:
                slim_data["flow_log"] = flow_log
            payload = dict(payload)
            payload["data"] = slim_data

        msg = json.dumps(payload, ensure_ascii=False, default=str)
        dead: List[Tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = []

        def _push_to_queue(target_q: asyncio.Queue, message: str) -> None:
            try:
                target_q.put_nowait(message)
                return
            except asyncio.QueueFull:
                # 큐 가득 차면 오래된 메시지 일부를 버리고 최신 메시지를 우선 전달
                for _ in range(50):
                    try:
                        target_q.get_nowait()
                    except Exception:
                        break
                try:
                    target_q.put_nowait(message)
                except Exception:
                    pass
            except Exception:
                pass

        with self._sub_lock:
            subscribers_snapshot = list(self._subscribers)

        for loop, q in subscribers_snapshot:
            try:
                loop.call_soon_threadsafe(_push_to_queue, q, msg)
            except Exception:
                dead.append((loop, q))

        if dead:
            dead_set = {(id(loop), id(q)) for loop, q in dead}
            with self._sub_lock:
                self._subscribers = [
                    (loop, q)
                    for loop, q in self._subscribers
                    if (id(loop), id(q)) not in dead_set
                ]


# ─── 모듈 레벨 싱글턴 ─────────────────────────────────────
monitor = MonitorState()
