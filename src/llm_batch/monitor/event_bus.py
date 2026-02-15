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
from typing import Any, Dict, List, Optional


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

        # 최근 로그 라인 (ring buffer)
        self._log_lines: List[str] = []
        self._max_log_lines: int = 500

        # 워커별 로그 라인 (병렬 모드용)
        self._worker_log_lines: Dict[int, List[str]] = {}  # worker_id → [lines]

        # 파이프라인 실행 흐름 로그 (현재 포스트 — 순차 모드용)
        self._flow_log: List[Dict[str, Any]] = []

        # SSE 구독자 큐
        self._subscribers: List[asyncio.Queue] = []
        self._sub_lock = threading.Lock()

    # ─── 외부 호출 API ────────────────────────────────────

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

    def add_log(self, line: str, worker_id: int = -1) -> None:
        """로그 라인 추가 (대시보드 로그 탭용)
        
        Args:
            line: 로그 라인
            worker_id: 워커 ID (-1 = 메인 스레드)
        """
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

        self._broadcast({
            "type": "log",
            "data": {"line": line, "worker_id": worker_id},
            "ts": datetime.now().isoformat(),
        })

    def get_status(self) -> Dict[str, Any]:
        """현재 상태 스냅샷 반환 (REST API용)"""
        with self._lock:
            elapsed = time.time() - self.batch_start_time if self.batch_running else 0
            done_count = len(self.post_summaries)
            avg_time = elapsed / done_count if done_count > 0 else 0
            remaining = (self.total_posts - done_count) * avg_time if done_count > 0 else 0

            relevant_count = sum(1 for p in self.post_summaries if p.get("is_relevant"))
            noise_count = sum(1 for p in self.post_summaries if not p.get("is_relevant"))

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
            }

    def get_results(self) -> List[Dict[str, Any]]:
        """완료된 포스트 요약 목록 (flow_log 포함)"""
        with self._lock:
            return list(self.post_summaries)

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

    # ─── SSE 구독 ──────────────────────────────────────────

    def subscribe(self) -> asyncio.Queue:
        """SSE 구독자 등록, Queue 반환"""
        q: asyncio.Queue = asyncio.Queue(maxsize=1024)
        with self._sub_lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._sub_lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

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
                self.active_posts = {}
                self.token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                self.search_hits = 0
                self.search_misses = 0
                self._flow_log = []
                self._worker_log_lines = {}

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
                        self.active_posts[post_id]["flow_log"].append({
                            "expert": expert,
                            "recall": bool(data.get("recall")),
                            "from": data.get("from", ""),
                            "reason": data.get("reason", ""),
                        })
                
                # 순차 모드: flow_log에도 기록
                if status == "running":
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
                
                # flow_log 결정: 병렬 모드면 active_posts에서, 순차면 self._flow_log
                if post_id is not None and post_id in self.active_posts:
                    active_flow = self.active_posts[post_id].get("flow_log", [])
                    summary = dict(data)
                    summary["flow_log"] = list(active_flow)
                    data["flow_log"] = list(active_flow)
                    # active_posts에서 제거
                    del self.active_posts[post_id]
                else:
                    summary = dict(data)
                    summary["flow_log"] = list(self._flow_log)
                    data["flow_log"] = list(self._flow_log)
                
                self.post_summaries.append(summary)

                # 토큰 누적
                tu = data.get("token_usage")
                if tu:
                    self.token_usage["prompt_tokens"] += tu.get("prompt_tokens", 0)
                    self.token_usage["completion_tokens"] += tu.get("completion_tokens", 0)
                    self.token_usage["total_tokens"] += tu.get("total_tokens", 0)

            elif event_type == "search_stats":
                self.search_hits = data.get("hits", 0)
                self.search_misses = data.get("misses", 0)

            elif event_type == "batch_complete":
                self.batch_running = False
                self.active_posts = {}

    def _broadcast(self, payload: Dict[str, Any]) -> None:
        """모든 SSE 구독자에게 이벤트 전송"""
        msg = json.dumps(payload, ensure_ascii=False, default=str)
        dead: List[asyncio.Queue] = []
        with self._sub_lock:
            for q in self._subscribers:
                try:
                    q.put_nowait(msg)
                except asyncio.QueueFull:
                    # 큐 가득 차면 오래된 메시지 50개 버리고 재시도
                    try:
                        for _ in range(50):
                            q.get_nowait()
                        q.put_nowait(msg)
                    except Exception:
                        dead.append(q)
                except Exception:
                    dead.append(q)
            for q in dead:
                self._subscribers.remove(q)


# ─── 모듈 레벨 싱글턴 ─────────────────────────────────────
monitor = MonitorState()
