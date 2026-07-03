from __future__ import annotations

import base64
import json
import os
import select
import sys
import threading
import time
import socket
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TypeVar

import httpx

from .prompt import (
    ANALYZE_PROMPT,
    HYPOTHESIS_PROMPT,
    REASON_REVIEW_PROMPT,
    SEARCH_PLANNER_PROMPT,
    SYSTEM_PROMPT,
)

T = TypeVar("T")


def _env_flag(name: str, default: str = "0") -> bool:
    raw = str(os.getenv(name, default) or default).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return int(default)


def _stdin_is_interactive() -> bool:
    stdin = getattr(sys, "stdin", None)
    return bool(stdin and hasattr(stdin, "isatty") and stdin.isatty())


def _emit_monitor_event(event_type: str, data: Optional[Dict[str, Any]] = None) -> None:
    try:
        from llm_batch.monitor.event_bus import monitor

        monitor.emit(event_type, data or {})
    except Exception:
        return


class _LLMServerSuspendController:
    """공유 LLM transport 이상 감시 및 사용자 승인 재개 게이트."""

    def __init__(self) -> None:
        self._cv = threading.Condition()
        self._consecutive_failures = 0
        self._prompt_active = False
        self._last_error = ""
        self._noninteractive_notice_emitted = False
        self._resume_requested = False
        self._resume_source = ""
        self._console_line_buffer = ""

    def reset_for_tests(self) -> None:
        with self._cv:
            self._consecutive_failures = 0
            self._prompt_active = False
            self._last_error = ""
            self._noninteractive_notice_emitted = False
            self._resume_requested = False
            self._resume_source = ""
            self._console_line_buffer = ""
            self._cv.notify_all()

    def wait_if_paused(self) -> None:
        with self._cv:
            while self._prompt_active:
                self._cv.wait(timeout=0.2)

    def request_resume(self, source: str = "external") -> bool:
        with self._cv:
            if not self._prompt_active:
                return False
            self._resume_requested = True
            self._resume_source = str(source or "external").strip() or "external"
            self._cv.notify_all()
            return True

    def record_success(self) -> None:
        with self._cv:
            if self._prompt_active:
                return
            self._consecutive_failures = 0
            self._last_error = ""
            self._noninteractive_notice_emitted = False

    def record_final_failure(self, exc: Exception) -> None:
        if not self._is_server_anomaly(exc):
            self.record_success()
            return

        threshold = max(0, _env_int("LLM_SUSPEND_FAILURE_THRESHOLD", 3))
        enabled = _env_flag("LLM_SUSPEND_ON_SERVER_ANOMALY", "1")
        interactive = _stdin_is_interactive()

        should_prompt = False
        should_warn_noninteractive = False
        count = 0
        error_text = f"{type(exc).__name__}: {exc}"

        with self._cv:
            self._consecutive_failures += 1
            self._last_error = error_text
            count = self._consecutive_failures
            self._resume_requested = False
            self._resume_source = ""
            self._console_line_buffer = ""

            if not enabled or threshold <= 0 or count < threshold:
                return

            if not interactive:
                if not self._noninteractive_notice_emitted:
                    self._noninteractive_notice_emitted = True
                    should_warn_noninteractive = True
                return

            if self._prompt_active:
                return

            self._prompt_active = True
            should_prompt = True

        if should_warn_noninteractive:
            ts = time.strftime("%H:%M:%S")
            self._write_notice(
                f"[{ts}][llm-watchdog] LLM 서버 이상 응답이 {count}회 누적됐지만 "
                "현재 표준입력이 비대화형이라 일시중지를 건너뜁니다."
            )
            return

        if not should_prompt:
            return

        started_at = datetime.now().isoformat()
        _emit_monitor_event(
            "llm_suspend",
            {
                "failure_count": count,
                "threshold": threshold,
                "last_error": error_text,
                "started_at": started_at,
                "message": "HTTP 스트리밍 오류가 관측되었습니다. 관리자님은 LLM 서버측을 확인해주세요.",
            },
        )
        resume_source = "unknown"
        try:
            resume_source = self._prompt_until_resume(
                count=count,
                threshold=threshold,
                error_text=error_text,
            )
        finally:
            _emit_monitor_event(
                "llm_resume",
                {
                    "failure_count": count,
                    "threshold": threshold,
                    "last_error": error_text,
                    "started_at": started_at,
                    "resumed_at": datetime.now().isoformat(),
                    "resumed_by": resume_source,
                    "message": self._resume_message_for_source(resume_source),
                },
            )
            with self._cv:
                self._consecutive_failures = 0
                self._last_error = ""
                self._noninteractive_notice_emitted = False
                self._prompt_active = False
                self._resume_requested = False
                self._resume_source = ""
                self._console_line_buffer = ""
                self._cv.notify_all()

    @staticmethod
    def _is_server_anomaly(exc: Exception) -> bool:
        if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, ConnectionError, OSError)):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            try:
                status_code = int(exc.response.status_code)
            except Exception:
                status_code = 0
            if status_code == 429 or status_code >= 500:
                return True
            if status_code in {404, 405}:
                # vLLM/llama 서버가 내려갔거나 프록시가 잘못 라우팅될 때
                # OpenAI 호환 chat/completions 경로가 404/405로 보이는 경우가 있다.
                try:
                    request_path = str(exc.request.url.path or "")
                except Exception:
                    request_path = ""
                if request_path.endswith("/chat/completions"):
                    return True
            return False
        if isinstance(exc, httpx.RequestError):
            return True
        return False

    @staticmethod
    def _iter_notice_streams():
        seen: set[int] = set()
        for stream in (getattr(sys, "__stderr__", None), getattr(sys, "stderr", None)):
            if stream is None:
                continue
            sid = id(stream)
            if sid in seen:
                continue
            seen.add(sid)
            yield stream

    def _write_notice(self, message: str, *, end: str = "\n") -> None:
        for stream in self._iter_notice_streams():
            try:
                print(message, end=end, file=stream, flush=True)
            except Exception:
                continue

    @staticmethod
    def _resume_message_for_source(source: str) -> str:
        source_norm = str(source or "").strip().lower()
        if source_norm in {"web_dashboard", "web_keyboard"}:
            return "웹 대시보드 사용자 확인 후 처리 재개"
        if source_norm == "terminal":
            return "터미널 사용자 확인 후 처리 재개"
        return "사용자 확인 후 처리 재개"

    def _take_resume_request(self) -> str:
        with self._cv:
            if not self._resume_requested:
                return ""
            source = self._resume_source or "external"
            self._resume_requested = False
            self._resume_source = ""
            return source

    def _poll_resume_input(self, timeout_s: float = 0.2) -> Optional[str]:
        stdin = getattr(sys, "stdin", None)
        if stdin is None:
            time.sleep(timeout_s)
            return None
        if os.name == "nt":
            return self._poll_resume_input_windows(timeout_s)
        return self._poll_resume_input_posix(stdin, timeout_s)

    def _poll_resume_input_posix(self, stdin: Any, timeout_s: float) -> Optional[str]:
        try:
            ready, _, _ = select.select([stdin], [], [], max(0.0, timeout_s))
        except Exception:
            time.sleep(timeout_s)
            return None
        if not ready:
            return None
        try:
            line = stdin.readline()
        except Exception:
            return ""
        if line is None:
            return ""
        return str(line).strip()

    def _poll_resume_input_windows(self, timeout_s: float) -> Optional[str]:
        try:
            import msvcrt  # type: ignore
        except Exception:
            time.sleep(timeout_s)
            return None

        deadline = time.monotonic() + max(0.0, timeout_s)
        while time.monotonic() < deadline:
            while msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in {"\r", "\n"}:
                    line = self._console_line_buffer
                    self._console_line_buffer = ""
                    return line.strip()
                if ch == "\003":
                    raise KeyboardInterrupt
                if ch in {"\b", "\x7f"}:
                    self._console_line_buffer = self._console_line_buffer[:-1]
                    continue
                self._console_line_buffer += ch
            time.sleep(0.05)
        return None

    def _prompt_until_resume(self, *, count: int, threshold: int, error_text: str) -> str:
        ts = time.strftime("%H:%M:%S")
        self._write_notice(
            f"\n[{ts}][llm-watchdog] ⚠️ HTTP 스트리밍 오류가 관측되었습니다. "
            "관리자님은 LLM 서버측을 확인해주세요. "
            f"(연속 실패 {count}회, 임계값 {threshold}회)"
        )
        if error_text:
            self._write_notice(f"[{ts}][llm-watchdog] 최근 오류: {error_text}")
        self._write_notice(
            f"[{ts}][llm-watchdog] 터미널에 y를 입력하거나 웹 대시보드에서 재개하세요.",
        )

        while True:
            resume_source = self._take_resume_request()
            if resume_source:
                ts_resume = time.strftime("%H:%M:%S")
                self._write_notice(
                    f"[{ts_resume}][llm-watchdog] {self._resume_message_for_source(resume_source)}"
                )
                return resume_source

            answer = self._poll_resume_input(timeout_s=0.2)
            if answer is None:
                continue
            if answer.strip().lower() == "y":
                ts_resume = time.strftime("%H:%M:%S")
                self._write_notice(f"[{ts_resume}][llm-watchdog] 터미널 사용자 확인 후 처리 재개")
                return "terminal"
            if answer.strip():
                ts_retry = time.strftime("%H:%M:%S")
                self._write_notice(
                    f"[{ts_retry}][llm-watchdog] 'y'를 입력하거나 웹 대시보드에서 재개하세요."
                )


_LLM_SERVER_SUSPEND_CONTROLLER = _LLMServerSuspendController()


def _reset_llm_server_suspend_controller_for_tests() -> None:
    _LLM_SERVER_SUSPEND_CONTROLLER.reset_for_tests()


def request_llm_server_resume(source: str = "external") -> bool:
    return _LLM_SERVER_SUSPEND_CONTROLLER.request_resume(source=source)


def retry_with_backoff(
    func: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 2.0,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None,
    on_failure: Optional[Callable[[Exception], T]] = None,
) -> T:
    """
    재시도 로직 (exponential backoff)
    
    Args:
        func: 실행할 함수
        max_retries: 최대 재시도 횟수 (기본 3)
        base_delay: 기본 대기 시간 (초, 기본 2)
        exceptions: 재시도할 예외 타입들
        on_retry: 재시도 시 호출할 콜백 (attempt, exception)
        on_failure: 모든 재시도 실패 시 호출할 콜백 (exception) -> fallback value
    
    Returns:
        함수 실행 결과 또는 fallback 값
        
    Note:
        Remote LLM 서버는 모든 HTTP 에러를 재시도 (일시적 장애 가능성)
    """
    last_exception = None
    for attempt in range(max_retries):
        _LLM_SERVER_SUSPEND_CONTROLLER.wait_if_paused()
        try:
            result = func()
            _LLM_SERVER_SUSPEND_CONTROLLER.record_success()
            return result
        except exceptions as e:
            last_exception = e
            retryable = True
            if isinstance(e, httpx.HTTPStatusError):
                try:
                    status_code = int(e.response.status_code)
                except Exception:
                    status_code = 0
                if status_code in {400, 401, 403, 413, 422}:
                    retryable = False
            
            if (not retryable) or attempt >= max_retries - 1:
                _LLM_SERVER_SUSPEND_CONTROLLER.record_final_failure(e)
                # 재시도하지 않거나 마지막 시도 실패
                ts = time.strftime("%H:%M:%S")
                print(
                    f"[{ts}][llm-error] 최종 실패 ({attempt + 1}회 시도): {type(e).__name__}: {e}",
                    file=sys.stderr,
                    flush=True,
                )
                if on_failure:
                    return on_failure(e)
                raise
            
            # 재시도 가능한 에러 (5xx, 네트워크 에러 등)
            delay = base_delay * (2 ** attempt)  # 2초, 4초, 8초
            if on_retry:
                on_retry(attempt + 1, e)
            else:
                ts = time.strftime("%H:%M:%S")
                print(
                    f"[{ts}][llm-retry] 시도 {attempt + 1}/{max_retries} 실패: {type(e).__name__}: {e}",
                    file=sys.stderr,
                    flush=True,
                )
                print(f"[{ts}][llm-retry] {delay:.1f}초 후 재시도...", file=sys.stderr, flush=True)
            time.sleep(delay)
    
    # Should not reach here, but for type checker
    raise last_exception  # type: ignore


class LLMClient:
    def __init__(
        self,
        backend: Optional[str] = None,
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
        model_path: Optional[str] = None,
        chat_format: Optional[str] = None,
        stream: Optional[bool] = None,
        profile: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        min_p: Optional[float] = None,
        repeat_penalty: Optional[float] = None,
        max_tokens: Optional[int] = None,
        server_type: Optional[str] = None,
    ) -> None:
        self.backend = (backend or os.getenv("LLM_BACKEND", "http")).lower()
        # 서빙 엔진 선택: "llama" (llama-server / llama.cpp) 또는 "vllm" (vLLM)
        self.server_type = (server_type or os.getenv("LLM_SERVER_TYPE", "llama")).lower()
        if self.server_type not in ("llama", "vllm"):
            self.server_type = "llama"
        self.endpoint = endpoint or os.getenv("LLM_ENDPOINT", "http://127.0.0.1:8080")
        self.model = model or os.getenv("LLM_MODEL", "unsloth/GLM-4.7-Flash-GGUF:IQ3_XXS")
        self.model_path = model_path or os.getenv("LLM_MODEL_PATH")
        # chat_format은 모델마다 다르므로 기본값 강제하지 않고, GGUF 메타데이터 기반 자동 추정을 우선한다.
        self.chat_format = chat_format or os.getenv("LLM_CHAT_FORMAT")
        self.timeout_s = float(os.getenv("LLM_TIMEOUT", "300"))
        self.max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))
        self.retry_base_delay = float(os.getenv("LLM_RETRY_DELAY", "2.0"))
        self.stream = (
            stream
            if stream is not None
            else os.getenv("LLM_STREAM", "0") == "1"
        )

        # Sampling defaults (Z.ai recommended)
        self.profile = (profile or os.getenv("LLM_PROFILE", "tool")).lower()
        if self.profile not in ("tool", "general"):
            self.profile = "tool"

        default_temp = 0.7 if self.profile == "tool" else 1.0
        default_top_p = 1.0 if self.profile == "tool" else 0.95
        default_min_p = 0.01  # llama.cpp default 0.05 is often too high
        default_repeat_penalty = 1.0  # disable

        self.temperature = float(os.getenv("LLM_TEMP", str(default_temp))) if temperature is None else float(temperature)
        self.top_p = float(os.getenv("LLM_TOP_P", str(default_top_p))) if top_p is None else float(top_p)
        self.min_p = float(os.getenv("LLM_MIN_P", str(default_min_p))) if min_p is None else float(min_p)
        self.repeat_penalty = float(os.getenv("LLM_REPEAT_PENALTY", str(default_repeat_penalty))) if repeat_penalty is None else float(repeat_penalty)
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "32768")) if max_tokens is None else int(max_tokens)
        self.json_grammar = os.getenv("LLM_JSON_GRAMMAR", "1") == "1"
        # A안: <think>... </think> 스트리밍 + 마지막에 JSON만 출력(identify에서 grammar를 끔)
        self.think_stream = os.getenv("LLM_THINK_STREAM", "0") == "1"
        # GLM-4.7-Flash 등 reasoning 모델의 내부 thinking 활성화 여부
        # 0=비활성(빠름, JSON만 출력), 1=활성(느림, <think>블록 출력)
        self.enable_thinking = os.getenv("LLM_ENABLE_THINKING", "0") == "1"
        self.print_timings = os.getenv("LLM_PRINT_TIMINGS", "0") == "1"
        self.debug_dump_messages = os.getenv("LLM_DEBUG_DUMP_MESSAGES", "0") == "1"
        # 0 또는 음수면 truncate 없이 전체 출력
        self.debug_dump_max_chars = int(os.getenv("LLM_DEBUG_DUMP_MAX_CHARS", "0"))

        # last call meta (for tracing)
        self.last_usage: Optional[Dict[str, Any]] = None
        self.last_model: Optional[str] = None
        self.last_finish_reason: Optional[str] = None

        self._local_llm = None
        self._local_lock = threading.Lock()
        self._json_grammar_obj = None
        self._json_object_grammar_obj = None

    def _resolve_reason_review_max_tokens(self) -> int:
        try:
            default_cap = max(256, int(self.max_tokens))
        except Exception:
            default_cap = 65536
        try:
            configured = int(os.getenv("LLM_REASON_REVIEW_MAX_TOKENS", str(default_cap)))
        except Exception:
            configured = default_cap
        return max(256, min(configured, default_cap))

    @property
    def is_vllm(self) -> bool:
        """현재 서빙 엔진이 vLLM인지 여부"""
        return self.server_type == "vllm"

    def _adapt_body_for_server(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        서빙 엔진(llama-server vs vLLM)에 따라 HTTP request body를 변환한다.

        llama-server (기본):
          - repeat_penalty, min_p, chat_template_kwargs, enable_thinking 그대로 사용
        vLLM:
          - repeat_penalty → repetition_penalty (OpenAI 호환 이름)
          - chat_template_kwargs 유지 (chat template이 enable_thinking 같은 런타임 플래그를 읽을 수 있음)
          - top_k, presence_penalty 등 vLLM 전용 샘플링 파라미터 추가
          - min_p: vLLM extra_body로 지원
          - enable_thinking: vLLM에서도 지원 (chat_template에 따라 다름)
        """
        if self.server_type != "vllm":
            return body

        # repeat_penalty → repetition_penalty
        if "repeat_penalty" in body:
            val = body.pop("repeat_penalty")
            body["repetition_penalty"] = val

        # vLLM 전용 샘플링 파라미터 (환경변수로 오버라이드 가능)
        # top_k: vLLM은 top_k를 직접 지원 (llama-server는 top_k 미지원)
        vllm_top_k = int(os.getenv("LLM_VLLM_TOP_K", "20"))
        if vllm_top_k > 0 and "top_k" not in body:
            body["top_k"] = vllm_top_k

        # presence_penalty: vLLM OpenAI 호환 API 기본 지원
        vllm_presence_penalty = float(os.getenv("LLM_VLLM_PRESENCE_PENALTY", "1.5"))
        if "presence_penalty" not in body:
            body["presence_penalty"] = vllm_presence_penalty

        return body

    @staticmethod
    def _looks_korean(s: str) -> bool:
        if not isinstance(s, str) or not s.strip():
            return False
        # "한글이 조금이라도 있으면 OK"는 너무 약함(영어 문장에 한글 토큰 몇 개 섞이는 케이스가 많음)
        # - 라틴 문자가 한글보다 많으면 "한국어로 작성" 규칙 위반으로 본다.
        re_mod = __import__("re")
        hangul = len(re_mod.findall(r"[가-힣]", s))
        latin = len(re_mod.findall(r"[A-Za-z]", s))
        if hangul == 0:
            return False
        if latin > hangul:
            return False
        return True

    @staticmethod
    def _timestamp() -> str:
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S.%f")[:-3]

    def _resolve_json_stream_guard(self) -> tuple[bool, int, int]:
        enabled = os.getenv("LLM_ABORT_AFTER_JSON", "1") == "1"
        try:
            piece_cap = int(os.getenv("LLM_POST_JSON_PIECE_CAP", "1"))
        except Exception:
            piece_cap = 1
        try:
            char_cap = int(os.getenv("LLM_POST_JSON_CHAR_CAP", "24"))
        except Exception:
            char_cap = 24
        return enabled, max(1, min(piece_cap, 8)), max(1, min(char_cap, 4096))

    def _should_abort_after_json_continuation(
        self,
        *,
        json_mode: bool,
        post_json_piece_count: int,
        post_json_char_count: int,
        fragment: str,
    ) -> Optional[str]:
        enabled, piece_cap, char_cap = self._resolve_json_stream_guard()
        if not enabled or not json_mode:
            return None
        if not isinstance(fragment, str) or not fragment.strip():
            return None
        if post_json_piece_count >= piece_cap:
            return f"post_json_piece_cap({post_json_piece_count}>={piece_cap})"
        if post_json_char_count >= char_cap:
            return f"post_json_char_cap({post_json_char_count}>={char_cap})"
        return None

    @staticmethod
    def _trim_to_completed_json(raw_text: str, json_complete_pos: int) -> str:
        if not isinstance(raw_text, str):
            return ""
        if json_complete_pos < 0:
            return raw_text
        return raw_text[:json_complete_pos].rstrip()

    def _print_usage_details(self, tag: str, data: Dict[str, Any], elapsed_s: float = 0.0) -> None:
        """스크린샷과 같은 상세 토큰 사용량 출력"""
        if not self.print_timings:
            return
        try:
            ts = self._timestamp()
            usage = data.get("usage", {}) if isinstance(data, dict) else {}
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

            # 속도 계산
            if elapsed_s > 0:
                response_tok_s = completion_tokens / elapsed_s if completion_tokens else 0
                prompt_tok_s = prompt_tokens / elapsed_s if prompt_tokens else 0
            else:
                response_tok_s = 0
                prompt_tok_s = 0

            # 상세 출력
            print(f"[{ts}][llm-usage] ── {tag} ──", file=sys.stderr, flush=True)
            print(f"  prompt_tokens: {prompt_tokens}", file=sys.stderr, flush=True)
            print(f"  completion_tokens: {completion_tokens}", file=sys.stderr, flush=True)
            print(f"  total_tokens: {total_tokens}", file=sys.stderr, flush=True)
            if elapsed_s > 0:
                print(f"  elapsed: {elapsed_s:.2f}s", file=sys.stderr, flush=True)
                print(f"  response_tok/s: {response_tok_s:.2f}", file=sys.stderr, flush=True)
                print(f"  prompt_tok/s: {prompt_tok_s:.2f}", file=sys.stderr, flush=True)

            # completion_tokens_details가 있으면 출력
            details = usage.get("completion_tokens_details", {})
            if details:
                print(f"  completion_tokens_details:", file=sys.stderr, flush=True)
                for k, v in details.items():
                    print(f"    {k}: {v}", file=sys.stderr, flush=True)
        except Exception:
            pass

    @staticmethod
    def _replace_lone_surrogates(value: Any) -> Any:
        """Replace invalid UTF-16 surrogate codepoints before JSON transport."""
        if isinstance(value, str):
            if not any(0xD800 <= ord(ch) <= 0xDFFF for ch in value):
                return value
            return "".join("\ufffd" if 0xD800 <= ord(ch) <= 0xDFFF else ch for ch in value)
        if isinstance(value, list):
            return [LLMClient._replace_lone_surrogates(item) for item in value]
        if isinstance(value, tuple):
            return tuple(LLMClient._replace_lone_surrogates(item) for item in value)
        if isinstance(value, dict):
            return {
                LLMClient._replace_lone_surrogates(key): LLMClient._replace_lone_surrogates(item)
                for key, item in value.items()
            }
        return value

    def _dump_messages(self, tag: str, messages: List[Dict[str, Any]]) -> None:
        if not self.debug_dump_messages:
            return
        try:
            ts = self._timestamp()
            # 보기 좋게: role별로 한 줄 요약 + content (전체 또는 제한)
            safe = []
            for m in messages:
                role = m.get("role")
                content = m.get("content", "")
                if not isinstance(content, str):
                    content = str(content)
                total_len = len(content)
                # debug_dump_max_chars가 0 이하면 truncate 없이 전체 출력
                if self.debug_dump_max_chars > 0 and total_len > self.debug_dump_max_chars:
                    content = content[: self.debug_dump_max_chars] + f"\n...(truncated,len={total_len})"
                safe.append({"role": role, "len": total_len, "content": content})

            print(f"[{ts}][llm-debug] FINAL PROMPT {tag}", file=sys.stderr, flush=True)
            for item in safe:
                r = item.get("role")
                ln = item.get("len")
                print(f"[{ts}][llm-debug]   - role={r} chars={ln}", file=sys.stderr, flush=True)
                print(f"[{ts}][llm-debug]     {item.get('content')}", file=sys.stderr, flush=True)
        except Exception:
            return

    def _dump_request_body(self, tag: str, url: str, body: Dict[str, Any]) -> None:
        if not self.debug_dump_messages:
            return
        try:
            ts = self._timestamp()
            payload = body if isinstance(body, dict) else {"body": body}
            dump = json.dumps(payload, ensure_ascii=False, indent=2)
            if self.debug_dump_max_chars > 0 and len(dump) > self.debug_dump_max_chars:
                dump = dump[: self.debug_dump_max_chars] + f"\n...(truncated,len={len(dump)})"
            print(f"[{ts}][llm-debug] REQUEST BODY {tag}", file=sys.stderr, flush=True)
            print(f"[{ts}][llm-debug]   url={url}", file=sys.stderr, flush=True)
            print(f"[{ts}][llm-debug]   {dump}", file=sys.stderr, flush=True)
        except Exception:
            return

    @staticmethod
    def _is_socket_transport_error(exc: Exception) -> bool:
        if isinstance(exc, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError)):
            return True
        if isinstance(exc, (socket.timeout, OSError)):
            msg = str(exc).lower()
            return (
                "socket.send() raised exception" in msg
                or "connection reset" in msg
                or "connection aborted" in msg
                or "connection closed" in msg
                or "bad file descriptor" in msg
            )
        return False

    def _http_stream_completion(
        self, 
        url: str, 
        body: Dict[str, Any], 
        tag: str,
        messages: Optional[List[Dict[str, Any]]] = None,
        quiet: bool = False,
        json_mode: Optional[bool] = None,
    ) -> str:
        """
        HTTP 백엔드로 스트리밍 요청을 보내고, 실시간으로 토큰을 출력하며 전체 텍스트를 반환한다.
        llama-server의 SSE(Server-Sent Events) 스트리밍을 처리한다.
        
        Args:
            url: API endpoint
            body: Request body
            tag: Log tag
            messages: Chat messages (for token estimation if server doesn't provide usage)
        """
        import time as _time
        import json as _json
        
        if json_mode is None:
            json_mode = bool(((body or {}).get("response_format") or {}).get("type") == "json_object")

        # body를 복사하여 stream 옵션 추가 (원본 수정 방지)
        stream_body = dict(body)
        stream_body["stream"] = True
        stream_body = self._replace_lone_surrogates(stream_body)
        _start = _time.time()
        ts = self._timestamp()
        print(f"[{ts}][llm-stream] ▶ {tag} 토큰 생성 시작...", file=sys.stderr, flush=True)
        
        acc: List[str] = []
        token_count = 0
        last_usage = None
        last_finish_reason = None
        all_chunks: List[Dict[str, Any]] = []  # 모든 청크 저장 (디버깅용)
        first_token_at: Optional[float] = None
        last_chunk_at: Optional[float] = None
        last_progress_log_at = _start
        sse_event_count = 0
        content_chunk_count = 0
        reasoning_chunk_count = 0
        whitespace_content_chunk_count = 0
        signal_chunk_count = 0
        last_signal_at: Optional[float] = None
        
        # ── 반복 루프 다계층 방어 ──
        loop_detected = False
        try:
            _ACC_HARD_CAP = int(os.getenv("LLM_ACC_HARD_CAP", "131000"))
        except (ValueError, TypeError):
            _ACC_HARD_CAP = 131000    # 누적 문자 하드캡 (vLLM --max-model-len 131072 대응)
        _TEXT_CHECK_INTERVAL = 40     # 40토큰마다 텍스트 레벨 반복 검사
        # 패턴 길이별 임계값: 짧은 패턴은 JSON 구조상 정상 반복될 수 있어 관대하게
        _TEXT_REPEAT_THRESHOLDS = {8: 15, 15: 10, 30: 7, 60: 6, 120: 5}
        # URL/퍼센트인코딩 조각은 정상적으로 길게 반복될 수 있어 훨씬 느슨하게 본다.
        _URL_REPEAT_THRESHOLD = 200
        # JSON value 리터럴 패턴: 이것들로 끝나는 짧은 패턴은 정상 JSON 구조
        _JSON_VALUE_SUFFIXES = ('null', 'false', 'true', '0', '0.0')
        _last_text_check_count = 0    # 마지막 텍스트 검사 시 토큰 카운트
        # JSON 객체 반복 감지: 첫 완전 JSON 형성 후 또 {가 오면 반복
        _json_depth = 0               # 현재 JSON 중괄호 깊이
        _json_started = False         # 첫 { 발견 여부
        _json_in_string = False       # JSON 문자열 내부인지
        _json_escape = False          # 이스케이프 문자 처리
        _json_complete_pos = -1       # 첫 완전 JSON 객체 완료 위치
        _json_complete_at: Optional[float] = None
        _json_complete_event_count = 0
        _json_complete_piece_count = 0
        _post_json_piece_count = 0
        _post_json_char_count = 0
        _post_json_first_logged = False
        _post_json_tail = ""
        try:
            _STREAM_GAP_WARN_S = float(os.getenv("LLM_STREAM_GAP_WARN_SECONDS", "30"))
        except (ValueError, TypeError):
            _STREAM_GAP_WARN_S = 30.0
        try:
            _STREAM_PROGRESS_INTERVAL_S = float(os.getenv("LLM_STREAM_PROGRESS_INTERVAL_SECONDS", "15"))
        except (ValueError, TypeError):
            _STREAM_PROGRESS_INTERVAL_S = 15.0
        try:
            _STREAM_PROGRESS_MIN_CHUNKS = int(os.getenv("LLM_STREAM_PROGRESS_MIN_CHUNKS", "200"))
        except (ValueError, TypeError):
            _STREAM_PROGRESS_MIN_CHUNKS = 200

        def _stream_timeout_env(name: str) -> Optional[float]:
            raw = os.getenv(name)
            if raw is None:
                return None
            try:
                value = float(raw)
            except (ValueError, TypeError):
                return None
            return value if value > 0 else None

        _STREAM_FIRST_TOKEN_TIMEOUT_S = _stream_timeout_env("LLM_STREAM_FIRST_TOKEN_TIMEOUT_SECONDS")
        _STREAM_IDLE_TIMEOUT_S = _stream_timeout_env("LLM_STREAM_IDLE_TIMEOUT_SECONDS")
        _STREAM_SIGNAL_IDLE_TIMEOUT_S = _stream_timeout_env("LLM_STREAM_SIGNAL_IDLE_TIMEOUT_SECONDS")
        if _STREAM_SIGNAL_IDLE_TIMEOUT_S is None:
            _STREAM_SIGNAL_IDLE_TIMEOUT_S = _STREAM_IDLE_TIMEOUT_S
        _stream_read_timeout_candidates = [
            value
            for value in (
                _STREAM_FIRST_TOKEN_TIMEOUT_S,
                _STREAM_IDLE_TIMEOUT_S,
                _STREAM_SIGNAL_IDLE_TIMEOUT_S,
            )
            if value is not None
        ]
        _stream_timeout: float | httpx.Timeout = self.timeout_s
        if _stream_read_timeout_candidates:
            _stream_read_timeout_s = min([self.timeout_s, *_stream_read_timeout_candidates])
            _stream_timeout = httpx.Timeout(self.timeout_s, read=_stream_read_timeout_s)

        def _record_stream_signal(kind: str, now: float) -> None:
            nonlocal first_token_at, last_signal_at, signal_chunk_count
            signal_chunk_count += 1
            last_signal_at = now
            if first_token_at is None:
                first_token_at = now
                ts_ttft = self._timestamp()
                print(
                    f"[{ts_ttft}][llm-stream] ⏱️ {tag} TTFT={first_token_at - _start:.2f}s "
                    f"({kind} first signal, events={sse_event_count})",
                    file=sys.stderr,
                    flush=True,
                )
        
        try:
            # httpx streaming with iter_text() for better SSE handling
            with httpx.stream("POST", url, json=stream_body, timeout=_stream_timeout) as response:
                response.raise_for_status()
                
                # SSE 버퍼: 줄 단위로 누적
                buffer = ""
                for text_chunk in response.iter_text():
                    if loop_detected:
                        break
                    _chunk_now = _time.time()
                    if (
                        last_signal_at is not None
                        and _STREAM_SIGNAL_IDLE_TIMEOUT_S is not None
                        and (_chunk_now - last_signal_at) >= _STREAM_SIGNAL_IDLE_TIMEOUT_S
                    ):
                        _signal_gap = _chunk_now - last_signal_at
                        if _json_complete_pos >= 0:
                            ts_signal = self._timestamp()
                            print(
                                f"\n[{ts_signal}][llm-stream] ⚠️ {tag} JSON 완성 후 의미 토큰 공백 "
                                f"{_signal_gap:.2f}s 감지, 완성 JSON 보존 후 조기 종료 "
                                f"(limit={_STREAM_SIGNAL_IDLE_TIMEOUT_S:.2f}s, "
                                f"events={sse_event_count}, content_chunks={content_chunk_count}, "
                                f"whitespace_content_chunks={whitespace_content_chunk_count}, "
                                f"signals={signal_chunk_count})",
                                file=sys.stderr,
                                flush=True,
                            )
                            loop_detected = True
                            break
                        raise httpx.ReadTimeout(
                            f"{tag} stream signal idle timeout after {_signal_gap:.2f}s "
                            f"(limit={_STREAM_SIGNAL_IDLE_TIMEOUT_S:.2f}s, "
                            f"events={sse_event_count}, content_chunks={content_chunk_count}, "
                            f"whitespace_content_chunks={whitespace_content_chunk_count}, "
                            f"signals={signal_chunk_count})"
                        )
                    if last_chunk_at is not None:
                        _gap = _chunk_now - last_chunk_at
                        if _gap >= _STREAM_GAP_WARN_S:
                            ts_gap = self._timestamp()
                            print(
                                f"[{ts_gap}][llm-stream] ⏳ {tag} 청크 공백 {_gap:.2f}s 후 수신 재개 "
                                f"(events={sse_event_count}, content_chunks={content_chunk_count}, "
                                f"reasoning_chunks={reasoning_chunk_count}, pieces={token_count})",
                                file=sys.stderr,
                                flush=True,
                            )
                        if _STREAM_IDLE_TIMEOUT_S is not None and _gap >= _STREAM_IDLE_TIMEOUT_S:
                            raise httpx.ReadTimeout(
                                f"{tag} stream idle timeout after {_gap:.2f}s "
                                f"(limit={_STREAM_IDLE_TIMEOUT_S:.2f}s)"
                            )
                    last_chunk_at = _chunk_now
                    if (
                        first_token_at is None
                        and _STREAM_FIRST_TOKEN_TIMEOUT_S is not None
                        and (_chunk_now - _start) >= _STREAM_FIRST_TOKEN_TIMEOUT_S
                    ):
                        raise httpx.ReadTimeout(
                            f"{tag} stream first-token timeout after {_chunk_now - _start:.2f}s "
                            f"(limit={_STREAM_FIRST_TOKEN_TIMEOUT_S:.2f}s)"
                        )
                    buffer += text_chunk
                    
                    # 줄 단위로 처리 (SSE는 \n 또는 \r\n으로 구분)
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        
                        if not line:
                            continue
                        
                        # SSE format: "data: {...}" 또는 "data:{...}"
                        if line.startswith("data:"):
                            sse_event_count += 1
                            data_str = line[5:].strip()  # "data:" 이후
                            if data_str == "[DONE]":
                                break
                            if not data_str:
                                continue
                            try:
                                chunk = _json.loads(data_str)
                                all_chunks.append(chunk)  # 모든 청크 저장
                                
                                # usage 정보 추출 (마지막 청크 또는 중간 청크에 포함될 수 있음)
                                if "usage" in chunk:
                                    last_usage = chunk["usage"]
                                    if self.print_timings:
                                        ts_debug = self._timestamp()
                                        print(f"\n[{ts_debug}][llm-debug] usage 발견: {last_usage}", file=sys.stderr, flush=True)
                                
                                # 토큰 추출
                                choices = chunk.get("choices", [])
                                if choices:
                                    fr = choices[0].get("finish_reason")
                                    if fr is not None:
                                        last_finish_reason = str(fr)
                                    delta = choices[0].get("delta", {})
                                    # reasoning_content 먼저 출력 (--reasoning-format deepseek 사용 시)
                                    reasoning = delta.get("reasoning_content", "")
                                    if reasoning:
                                        reasoning_chunk_count += 1
                                        if reasoning.strip():
                                            _record_stream_signal("reasoning", _chunk_now)
                                        # reasoning은 출력만 하고 acc에는 추가하지 않음 (최종 JSON에 포함 안됨)
                                        token_count += 1
                                        if not quiet:
                                            print(reasoning, end="", file=sys.stderr, flush=True)
                                    # content 출력
                                    piece = delta.get("content", "")
                                    if piece:
                                        _json_was_complete = _json_complete_pos >= 0
                                        _acc_len_before_piece = sum(len(s) for s in acc)
                                        content_chunk_count += 1
                                        if piece.strip():
                                            _record_stream_signal("content", _chunk_now)
                                        else:
                                            whitespace_content_chunk_count += 1
                                        acc.append(piece)
                                        token_count += 1
                                        if not quiet:
                                            print(piece, end="", file=sys.stderr, flush=True)

                                        _now = _time.time()
                                        if (
                                            (_now - last_progress_log_at) >= _STREAM_PROGRESS_INTERVAL_S
                                            and (content_chunk_count + reasoning_chunk_count) >= _STREAM_PROGRESS_MIN_CHUNKS
                                        ):
                                            ts_prog = self._timestamp()
                                            print(
                                                f"\n[{ts_prog}][llm-stream] … {tag} 진행중 "
                                                f"(elapsed={_now - _start:.2f}s, events={sse_event_count}, "
                                                f"content_chunks={content_chunk_count}, reasoning_chunks={reasoning_chunk_count}, "
                                                f"pieces={token_count}, acc_chars={sum(len(s) for s in acc):,})",
                                                file=sys.stderr,
                                                flush=True,
                                            )
                                            last_progress_log_at = _now
                                        
                                        # ── 다계층 반복 루프 방어 ──
                                        
                                        # (0) JSON 객체 반복 감지 (대규모 JSON 통째 반복 방어)
                                        for _idx, _ch in enumerate(piece):
                                            if _json_escape:
                                                _json_escape = False
                                                continue
                                            if _ch == '\\' and _json_in_string:
                                                _json_escape = True
                                                continue
                                            if _ch == '"':
                                                _json_in_string = not _json_in_string
                                                continue
                                            if _json_in_string:
                                                continue
                                            if _ch == '{':
                                                if not _json_started:
                                                    _json_started = True
                                                if _json_complete_pos >= 0:
                                                    # 이미 완전한 JSON이 형성된 후 새 {가 시작됨 → 반복
                                                    _acc_len_now = sum(len(s) for s in acc)
                                                    ts = self._timestamp()
                                                    print(
                                                        f"\n[{ts}][llm-stream] ⚠️ JSON 객체 반복 감지 "
                                                        f"(첫 객체 {_json_complete_pos}자에서 완료, "
                                                        f"총 {_acc_len_now}자), 조기 종료",
                                                        file=sys.stderr, flush=True,
                                                    )
                                                    loop_detected = True
                                                    break
                                                _json_depth += 1
                                            elif _ch == '}':
                                                _json_depth -= 1
                                                if _json_depth == 0 and _json_started and _json_complete_pos < 0:
                                                    _json_complete_pos = _acc_len_before_piece + _idx + 1
                                                    _json_complete_at = _time.time()
                                                    _json_complete_event_count = sse_event_count
                                                    _json_complete_piece_count = token_count
                                                    ts_json = self._timestamp()
                                                    print(
                                                        f"\n[{ts_json}][llm-stream] ✅ {tag} 첫 JSON 완성 "
                                                        f"(elapsed={_json_complete_at - _start:.2f}s, "
                                                        f"events={_json_complete_event_count}, pieces={_json_complete_piece_count}, "
                                                        f"chars={_json_complete_pos:,})",
                                                        file=sys.stderr,
                                                        flush=True,
                                                    )
                                        if loop_detected:
                                            break

                                        _post_json_fragment = ""
                                        if _json_complete_pos >= 0:
                                            _offset_in_piece = max(0, _json_complete_pos - _acc_len_before_piece)
                                            if _offset_in_piece < len(piece):
                                                _post_json_fragment = piece[_offset_in_piece:]
                                        if _json_was_complete or _post_json_fragment:
                                            _fragment = _post_json_fragment if _post_json_fragment else piece
                                            _sig_fragment = _fragment.strip()
                                            if _sig_fragment:
                                                _post_json_piece_count += 1
                                                _post_json_char_count += len(_sig_fragment)
                                                _post_json_tail = ("".join(([_post_json_tail, _sig_fragment])))[-400:]
                                                _abort_reason = self._should_abort_after_json_continuation(
                                                    json_mode=bool(json_mode),
                                                    post_json_piece_count=_post_json_piece_count,
                                                    post_json_char_count=_post_json_char_count,
                                                    fragment=_sig_fragment,
                                                )
                                                if _abort_reason:
                                                    ts_abort = self._timestamp()
                                                    print(
                                                        f"\n[{ts_abort}][llm-stream] ⚠️ {tag} JSON 후속 생성 차단 "
                                                        f"({_abort_reason})",
                                                        file=sys.stderr,
                                                        flush=True,
                                                    )
                                                    loop_detected = True
                                            if not _post_json_first_logged:
                                                ts_post_json = self._timestamp()
                                                _since_complete = (
                                                    (_time.time() - _json_complete_at)
                                                    if _json_complete_at is not None
                                                    else 0.0
                                                )
                                                print(
                                                    f"\n[{ts_post_json}][llm-stream] ⚠️ {tag} JSON 완성 후 추가 생성 시작 "
                                                    f"(since_complete={_since_complete:.2f}s, "
                                                    f"post_json_pieces={_post_json_piece_count}, "
                                                    f"post_json_chars={_post_json_char_count})",
                                                    file=sys.stderr,
                                                    flush=True,
                                                )
                                                _post_json_first_logged = True
                                        if loop_detected:
                                            break
                                        
                                        # (1) 누적 문자 하드캡
                                        _acc_len = sum(len(s) for s in acc)
                                        if _acc_len > _ACC_HARD_CAP:
                                            ts = self._timestamp()
                                            print(f"\n[{ts}][llm-stream] ⚠️ 누적 출력 하드캡 초과 ({_acc_len:,}자 > {_ACC_HARD_CAP:,}), 조기 종료", file=sys.stderr, flush=True)
                                            loop_detected = True
                                            break
                                        
                                        # (2) 텍스트 레벨 반복 패턴 탐지 (N토큰마다)
                                        if token_count - _last_text_check_count >= _TEXT_CHECK_INTERVAL:
                                            _last_text_check_count = token_count
                                            _full = "".join(acc)
                                            _tail = _full[-800:] if len(_full) > 800 else _full
                                            if len(_tail) >= 100:
                                                _found_loop = False
                                                # 꼬리에서 다양한 길이의 부분문자열을 뽑아 전체에서 count
                                                for _plen in (8, 15, 30, 60, 120):
                                                    if _plen > len(_tail) // 3:
                                                        continue
                                                    # 꼬리 끝에서 패턴 후보 추출
                                                    _candidate = _tail[-_plen:]
                                                    # JSON 구조 문자(공백/따옴표/괄호/콜론/콤마)로만 구성된 패턴은 무시
                                                    _content_chars = _candidate.translate(str.maketrans('', '', ' \t\n\r"{}[]:,'))
                                                    if len(_content_chars) < max(2, _plen // 3):
                                                        continue
                                                    # JSON value 리터럴(null/false/true)로 끝나는 짧은 패턴은 정상 구조
                                                    _stripped_cand = _candidate.strip()
                                                    if _plen <= 15 and any(_stripped_cand.endswith(sv) for sv in _JSON_VALUE_SUFFIXES):
                                                        continue
                                                    _cnt = _tail.count(_candidate)
                                                    _threshold = _TEXT_REPEAT_THRESHOLDS.get(_plen, 5)
                                                    _cand_l = _candidate.lower()
                                                    _pct_cnt = _candidate.count("%")
                                                    _looks_urlish = (
                                                        ("http" in _cand_l)
                                                        or ("www." in _cand_l)
                                                        or (".com" in _cand_l)
                                                        or (".net" in _cand_l)
                                                        or ("viewimage.php" in _cand_l)
                                                        or ("%2f" in _cand_l)
                                                        or ("%3a" in _cand_l)
                                                        or ("%20" in _cand_l)
                                                        or (_pct_cnt >= max(2, _plen // 8))
                                                    )
                                                    if _looks_urlish:
                                                        _threshold = max(_threshold, _URL_REPEAT_THRESHOLD)
                                                    if _cnt >= _threshold:
                                                        ts = self._timestamp()
                                                        _show = _candidate[:30].replace('\n', '\\n')
                                                        print(f"\n[{ts}][llm-stream] ⚠️ 텍스트 반복 감지 ('{_show}' x{_cnt}, 패턴{_plen}자), 조기 종료", file=sys.stderr, flush=True)
                                                        _found_loop = True
                                                        break
                                                if _found_loop:
                                                    loop_detected = True
                                                    break
                            except _json.JSONDecodeError:
                                continue
        except Exception as e:
            ts = self._timestamp()
            print(f"\n[{ts}][llm-error] HTTP 스트리밍 오류: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            raise
        
        _elapsed = _time.time() - _start
        ts = self._timestamp()
        print(f"\n[{ts}][llm-stream] ■ {tag} 완료 ({_elapsed:.2f}s)", file=sys.stderr, flush=True)
        if last_finish_reason:
            print(
                f"[{ts}][llm-stream] finish_reason={last_finish_reason}",
                file=sys.stderr,
                flush=True,
            )
            if last_finish_reason.lower() in {"length", "max_tokens"}:
                print(
                    f"[{ts}][llm-warn] 출력이 max_tokens 제한으로 종료됐을 가능성",
                    file=sys.stderr,
                    flush=True,
                )
        
        # compact JSON(줄바꿈 없음)으로 출력된 경우 pretty-print 재출력
        _raw = "".join(acc).strip()
        if json_mode and _json_complete_pos >= 0:
            _raw = self._trim_to_completed_json(_raw, _json_complete_pos)
        if _json_complete_pos >= 0:
            _post_json_tail_final = (_raw[_json_complete_pos:] if _json_complete_pos < len(_raw) else "")
            _post_json_tail_final = _post_json_tail_final[-400:]
            _json_complete_elapsed = (
                (_json_complete_at - _start)
                if _json_complete_at is not None
                else None
            )
            _json_summary = (
                f"[{ts}][llm-stream] 📌 {tag} JSON 이후 추가 생성 요약 "
                f"(post_json_pieces={_post_json_piece_count}, post_json_chars={_post_json_char_count}, "
                f"json_complete_chars={_json_complete_pos:,}, total_chars={len(_raw):,}, "
                f"json_complete_elapsed={_json_complete_elapsed:.2f}s)"
                if _json_complete_elapsed is not None
                else
                f"[{ts}][llm-stream] 📌 {tag} JSON 이후 추가 생성 요약 "
                f"(post_json_pieces={_post_json_piece_count}, post_json_chars={_post_json_char_count}, "
                f"json_complete_chars={_json_complete_pos:,}, total_chars={len(_raw):,})"
            )
            print(
                _json_summary,
                file=sys.stderr,
                flush=True,
            )
            if _post_json_tail_final:
                print(
                    f"[{ts}][llm-stream] 📌 {tag} post-JSON tail: {_post_json_tail_final[:400]}",
                    file=sys.stderr,
                    flush=True,
                )
        if _raw and "\n" not in _raw and _raw.startswith("{"):
            try:
                _parsed = _json.loads(_raw)
                _pretty = _json.dumps(_parsed, ensure_ascii=False, indent=2)
                print(f"[{ts}][llm-stream] (pretty-reprint)\n{_pretty}", file=sys.stderr, flush=True)
            except Exception:
                pass
        
        # usage 정보 처리 및 정규화
        if last_usage:
            # 서버에서 usage를 제공한 경우
            prompt_tokens = last_usage.get('prompt_tokens', 0)
            completion_tokens = last_usage.get('completion_tokens', token_count)
            total_tokens = last_usage.get('total_tokens', prompt_tokens + completion_tokens)
            
            if self.print_timings:
                print(f"[{ts}][llm-debug] 서버 제공 usage 사용: prompt={prompt_tokens}, completion={completion_tokens}", file=sys.stderr, flush=True)
        else:
            # 서버에서 usage를 제공하지 않은 경우 - 메시지 길이로 추정
            if messages:
                # 메시지 길이 기반 prompt_tokens 추정 (대략 3~4자 = 1토큰)
                prompt_chars = sum(len(m.get("content", "")) for m in messages)
                prompt_tokens = max(1, prompt_chars // 3)  # 최소 1 토큰
                if self.print_timings:
                    print(f"[{ts}][llm-debug] 메시지 길이 추정: {prompt_chars} chars ≈ {prompt_tokens} tokens", file=sys.stderr, flush=True)
            else:
                prompt_tokens = 0
                if self.print_timings:
                    print(f"[{ts}][llm-warn] 메시지 정보 없음, prompt_tokens=0", file=sys.stderr, flush=True)
            
            completion_tokens = token_count
            total_tokens = prompt_tokens + token_count
            
            if self.print_timings:
                print(f"[{ts}][llm-debug] 추정된 usage: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}", file=sys.stderr, flush=True)
                print(f"[{ts}][llm-debug] 수신한 청크 수: {len(all_chunks)}", file=sys.stderr, flush=True)
        
        # 정규화된 usage 저장
        self.last_usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
        self.last_finish_reason = last_finish_reason
        
        # 출력
        if self.print_timings:
            print(f"[{ts}][llm-usage] ── {tag} ──", file=sys.stderr, flush=True)
            print(f"  prompt_tokens: {prompt_tokens}", file=sys.stderr, flush=True)
            print(f"  completion_tokens: {completion_tokens}", file=sys.stderr, flush=True)
            print(f"  total_tokens: {total_tokens}", file=sys.stderr, flush=True)
            print(f"  elapsed: {_elapsed:.2f}s", file=sys.stderr, flush=True)
            if _elapsed > 0:
                print(f"  response_tok/s: {completion_tokens / _elapsed:.2f}", file=sys.stderr, flush=True)
                if prompt_tokens > 0:
                    print(f"  prompt_tok/s: {prompt_tokens / _elapsed:.2f}", file=sys.stderr, flush=True)
        return _raw

    def _resolve_expert_temperature(self, tag: str, temperature: Optional[float] = None) -> float:
        """전문가별 temperature 해석.
        
        우선순위: 직접 전달 > 환경변수 LLM_TEMP_{TAG} > 인스턴스 기본값
        예: tag="arbiter" → LLM_TEMP_ARBITER 환경변수 조회
        """
        if temperature is not None:
            return temperature
        env_key = f"LLM_TEMP_{tag.upper()}"
        env_val = os.getenv(env_key)
        if env_val is not None:
            try:
                return float(env_val)
            except ValueError:
                pass
        return self.temperature

    def _stream_chat_http(
        self,
        messages: List[Dict[str, Any]],
        tag: str = "expert",
        use_grammar: bool = True,
        max_tokens: Optional[int] = None,
        quiet: bool = False,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Expert 시스템을 위한 범용 스트리밍 채팅 호출 (HTTP 및 Local 백엔드 모두 지원).
        
        Args:
            messages: [{"role": "system"|"user", "content": str}, ...]
            tag: 로그용 태그 (예: "gatekeeper", "decoder", ...)
            use_grammar: JSON object grammar 강제 여부
            max_tokens: 최대 토큰 수 (None이면 self.max_tokens 사용)
            temperature: 전문가별 temperature (None이면 LLM_TEMP_{TAG} → self.temperature 순 적용)
            
        Returns:
            LLM 응답 텍스트 (JSON 문자열)
        """
        # 전문가별 temperature 해석
        resolved_temp = self._resolve_expert_temperature(tag, temperature)
        messages = self._replace_lone_surrogates(messages)
        
        # Local 백엔드 처리
        if self.backend == "local":
            return self._stream_chat_local(messages, tag, use_grammar, max_tokens, temperature=resolved_temp)
        
        # HTTP 백엔드 처리
        url = f"{self.endpoint.rstrip('/')}/v1/chat/completions"
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": resolved_temp,
            "top_p": self.top_p,
            "min_p": self.min_p,
            "repeat_penalty": self.repeat_penalty,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
            # JSON output 강제 - thinking 활성화 시 response_format 사용 안 함 (충돌)
            # thinking이 활성화되면 <think>블록 + JSON을 출력하므로 후처리 필요
            "response_format": {"type": "json_object"} if (use_grammar and not self.enable_thinking) else None,
            # thinking 활성화 설정
            "enable_thinking": self.enable_thinking,
            "chat_template_kwargs": {"enable_thinking": self.enable_thinking},
        }
        if self.server_type == "vllm":
            body["stream_options"] = {"include_usage": True}
        
        # body에서 None 값 제거
        body = {k: v for k, v in body.items() if v is not None}
        # 서빙 엔진별 파라미터 변환
        body = self._adapt_body_for_server(body)
        body = self._replace_lone_surrogates(body)
        
        # 토큰 수 추정 및 로그 출력
        total_chars = sum(len(msg.get("content", "")) for msg in messages)
        # 대략적인 토큰 수 추정: 한글은 ~2.5자/토큰, 영어는 ~4자/토큰
        # 보수적으로 2자/토큰으로 추정 (한글이 많으면 높게 나옴)
        estimated_tokens = total_chars // 2
        ts = self._timestamp()
        _temp_info = f" temp={resolved_temp}" if resolved_temp != self.temperature else ""
        _resolved_max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        print(
            f"[{ts}][llm-context] {tag} 프롬프트: {total_chars:,}자 (~{estimated_tokens:,} 토큰 추정)"
            f"{_temp_info} max_tokens={_resolved_max_tokens}",
            file=sys.stderr,
            flush=True,
        )
        
        # 컨텍스트 경고:
        # LLM_CONTEXT_LIMIT_TOKENS 우선, 없으면 LLM_N_CTX 사용 (기본 131072: vLLM --max-model-len 대응)
        _ctx_limit_raw = os.getenv("LLM_CONTEXT_LIMIT_TOKENS") or os.getenv("LLM_N_CTX") or "131072"
        try:
            context_limit = int(_ctx_limit_raw)
        except Exception:
            context_limit = 131072
        context_limit = max(4096, context_limit)
        if estimated_tokens > context_limit:
            print(
                f"[{ts}][llm-warn] ⚠️  컨텍스트 초과 가능: {estimated_tokens:,} > {context_limit:,} 토큰",
                file=sys.stderr,
                flush=True,
            )
        elif estimated_tokens >= int(context_limit * 0.9):
            print(
                f"[{ts}][llm-warn] ⚠️  컨텍스트 임박: {estimated_tokens:,}/{context_limit:,} 토큰",
                file=sys.stderr,
                flush=True,
            )
        
        self._dump_messages(tag, messages)
        self._dump_request_body(tag, url, body)

        if self.stream:
            def _do_non_stream_fallback() -> str:
                import time as _time
                _start = _time.time()
                ts = self._timestamp()
                print(f"[{ts}][llm] nonstream fallback 시작...", file=sys.stderr, flush=True)
                response = httpx.post(url, json=self._replace_lone_surrogates(body), timeout=self.timeout_s)
                response.raise_for_status()
                data = response.json()
                _elapsed = _time.time() - _start
                ts = self._timestamp()
                print(f"[{ts}][llm] nonstream fallback 종료 ({_elapsed:.2f}s)", file=sys.stderr, flush=True)
                usage = data.get("usage") if isinstance(data, dict) else None
                if usage:
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)
                    total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
                else:
                    prompt_tokens = 0
                    completion_tokens = 0
                    total_tokens = 0
                self.last_usage = {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                }
                self.last_model = data.get("model") if isinstance(data, dict) else None
                self._print_usage_details(tag, {"usage": self.last_usage}, _elapsed)
                try:
                    return data["choices"][0]["message"]["content"]
                except (KeyError, IndexError):
                    return "{}"

            def _do_stream():
                return self._http_stream_completion(url, body, tag, messages, quiet=quiet, json_mode=use_grammar)

            try:
                return retry_with_backoff(
                    _do_stream,
                    max_retries=self.max_retries,
                    base_delay=self.retry_base_delay,
                    exceptions=(httpx.HTTPError, httpx.TimeoutException, ConnectionError, OSError),
                    on_failure=lambda e: "{}",  # 최종 실패시 빈 JSON 반환
                )
            except Exception as e:
                if self._is_socket_transport_error(e):
                    ts = self._timestamp()
                    print(
                        f"[{ts}][llm-stream] 스트림 전송/수신 오류 감지, 비스트리밍 재시도: {type(e).__name__}",
                        file=sys.stderr,
                        flush=True,
                    )
                    return retry_with_backoff(
                        _do_non_stream_fallback,
                        max_retries=self.max_retries,
                        base_delay=self.retry_base_delay,
                        exceptions=(httpx.HTTPError, httpx.TimeoutException, ConnectionError, OSError),
                        on_failure=lambda e: "{}",
                    )
                raise
        # socket/stream 장애 시 비스트리밍 폴백용 임시 함수
        
        # 스트리밍 모드면 _http_stream_completion 사용 (재시도 로직 포함)
        if False:
            def _do_stream():
                return self._http_stream_completion(url, body, tag, messages)
            
            return retry_with_backoff(
                _do_stream,
                max_retries=self.max_retries,
                base_delay=self.retry_base_delay,
                exceptions=(httpx.HTTPError, httpx.TimeoutException, ConnectionError, OSError),
                on_failure=lambda e: "{}",  # 최종 실패시 빈 JSON 반환
            )
        
        # 비스트리밍 모드 (재시도 로직 포함)
        def _do_non_stream():
            import time as _time
            _start = _time.time()
            ts = self._timestamp()
            print(f"[{ts}][llm] ▶ {tag} 요청 시작...", file=sys.stderr, flush=True)
            
            response = httpx.post(url, json=self._replace_lone_surrogates(body), timeout=self.timeout_s)
            response.raise_for_status()
            data = response.json()
            
            _elapsed = _time.time() - _start
            ts = self._timestamp()
            print(f"[{ts}][llm] ■ {tag} 완료 ({_elapsed:.2f}s)", file=sys.stderr, flush=True)
            
            # usage 정규화 및 저장
            usage = data.get("usage") if isinstance(data, dict) else None
            if usage:
                prompt_tokens = usage.get('prompt_tokens', 0)
                completion_tokens = usage.get('completion_tokens', 0)
                total_tokens = usage.get('total_tokens', prompt_tokens + completion_tokens)
            else:
                prompt_tokens = 0
                completion_tokens = 0
                total_tokens = 0
            
            self.last_usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }
            self.last_model = data.get("model") if isinstance(data, dict) else None
            self._print_usage_details(tag, {"usage": self.last_usage}, _elapsed)
            
            try:
                content = data["choices"][0]["message"]["content"]
                return content
            except (KeyError, IndexError):
                return "{}"
        
        return retry_with_backoff(
            _do_non_stream,
            max_retries=self.max_retries,
            base_delay=self.retry_base_delay,
            exceptions=(httpx.HTTPError, httpx.TimeoutException, ConnectionError, OSError),
            on_failure=lambda e: "{}",  # 최종 실패시 빈 JSON 반환
        )
    
    def _stream_chat_local(
        self,
        messages: List[Dict[str, Any]],
        tag: str = "expert",
        use_grammar: bool = True,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Expert 시스템을 위한 Local 백엔드 스트리밍 채팅 호출.
        
        Args:
            messages: [{"role": "system"|"user", "content": str}, ...]
            tag: 로그용 태그 (예: "gatekeeper", "decoder", ...)
            use_grammar: JSON object grammar 강제 여부
            max_tokens: 최대 토큰 수 (None이면 self.max_tokens 사용)
            temperature: 전문가별 temperature (None이면 self.temperature 사용)
            
        Returns:
            LLM 응답 텍스트 (JSON 문자열)
        """
        import time as _time
        
        resolved_temp = temperature if temperature is not None else self.temperature
        
        llm = self._get_local_llm()
        self._dump_messages(tag, messages)
        
        _start = _time.time()
        ts = self._timestamp()
        
        # 스트리밍 모드
        if self.stream:
            print(f"[{ts}][llm-stream] ▶ {tag} 토큰 생성 시작...", file=sys.stderr, flush=True)
            
            chunks = llm.create_chat_completion(
                messages=messages,
                temperature=resolved_temp,
                top_p=self.top_p,
                min_p=self.min_p,
                repeat_penalty=self.repeat_penalty,
                max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
                grammar=None if self.think_stream or not use_grammar else self._get_json_object_grammar(),
                stream=True,
            )
            
            acc: List[str] = []
            token_count = 0
            last_chunk = None
            last_finish_reason = None
            
            # ── 반복 루프 다계층 방어 ──
            _loop_detected = False
            try:
                _ACC_HARD_CAP = int(os.getenv("LLM_ACC_HARD_CAP", "131000"))
            except (ValueError, TypeError):
                _ACC_HARD_CAP = 131000
            _TEXT_CHECK_INTERVAL = 40
            _TEXT_REPEAT_THRESHOLDS = {8: 15, 15: 10, 30: 7, 60: 6, 120: 5}
            # URL/퍼센트인코딩 조각은 정상적으로 길게 반복될 수 있어 훨씬 느슨하게 본다.
            _URL_REPEAT_THRESHOLD = 200
            _JSON_VALUE_SUFFIXES = ('null', 'false', 'true', '0', '0.0')
            _last_text_check_count = 0
            # JSON 객체 반복 감지
            _json_depth = 0
            _json_started = False
            _json_in_string = False
            _json_escape = False
            _json_complete_pos = -1
            _json_complete_at: Optional[float] = None
            _post_json_piece_count = 0
            _post_json_char_count = 0
            _post_json_first_logged = False
            _post_json_tail = ""
            
            for chunk in chunks:
                if _loop_detected:
                    break
                last_chunk = chunk
                try:
                    ch0 = chunk["choices"][0]
                    fr = ch0.get("finish_reason")
                    if fr is not None:
                        last_finish_reason = str(fr)
                    delta = ch0.get("delta", {})
                    piece = delta.get("content", "")
                except Exception:
                    piece = ""
                if piece:
                    _json_was_complete = _json_complete_pos >= 0
                    _acc_len_before_piece = sum(len(s) for s in acc)
                    acc.append(piece)
                    token_count += 1
                    print(piece, end="", file=sys.stderr, flush=True)
                    
                    # ── 다계층 반복 루프 방어 ──
                    
                    # (0) JSON 객체 반복 감지
                    for _idx, _ch in enumerate(piece):
                        if _json_escape:
                            _json_escape = False
                            continue
                        if _ch == '\\' and _json_in_string:
                            _json_escape = True
                            continue
                        if _ch == '"':
                            _json_in_string = not _json_in_string
                            continue
                        if _json_in_string:
                            continue
                        if _ch == '{':
                            if not _json_started:
                                _json_started = True
                            if _json_complete_pos >= 0:
                                _acc_len_now = sum(len(s) for s in acc)
                                ts = self._timestamp()
                                print(
                                    f"\n[{ts}][llm-stream] ⚠️ JSON 객체 반복 감지 "
                                    f"(첫 객체 {_json_complete_pos}자에서 완료, "
                                    f"총 {_acc_len_now}자), 조기 종료",
                                    file=sys.stderr, flush=True,
                                )
                                _loop_detected = True
                                break
                            _json_depth += 1
                        elif _ch == '}':
                            _json_depth -= 1
                            if _json_depth == 0 and _json_started and _json_complete_pos < 0:
                                _json_complete_pos = _acc_len_before_piece + _idx + 1
                                _json_complete_at = _time.time()
                    if _loop_detected:
                        break

                    _post_json_fragment = ""
                    if _json_complete_pos >= 0:
                        _offset_in_piece = max(0, _json_complete_pos - _acc_len_before_piece)
                        if _offset_in_piece < len(piece):
                            _post_json_fragment = piece[_offset_in_piece:]
                    if _json_was_complete or _post_json_fragment:
                        _fragment = _post_json_fragment if _post_json_fragment else piece
                        _sig_fragment = _fragment.strip()
                        if _sig_fragment:
                            _post_json_piece_count += 1
                            _post_json_char_count += len(_sig_fragment)
                            _post_json_tail = ("".join(([_post_json_tail, _sig_fragment])))[-400:]
                            _abort_reason = self._should_abort_after_json_continuation(
                                json_mode=bool(use_grammar),
                                post_json_piece_count=_post_json_piece_count,
                                post_json_char_count=_post_json_char_count,
                                fragment=_sig_fragment,
                            )
                            if _abort_reason:
                                ts_abort = self._timestamp()
                                print(
                                    f"\n[{ts_abort}][llm-stream] ⚠️ {tag} JSON 후속 생성 차단 "
                                    f"({_abort_reason})",
                                    file=sys.stderr,
                                    flush=True,
                                )
                                _loop_detected = True
                        if not _post_json_first_logged and _sig_fragment:
                            ts_post_json = self._timestamp()
                            _since_complete = (
                                (_time.time() - _json_complete_at)
                                if _json_complete_at is not None
                                else 0.0
                            )
                            print(
                                f"\n[{ts_post_json}][llm-stream] ⚠️ {tag} JSON 완성 후 추가 생성 시작 "
                                f"(since_complete={_since_complete:.2f}s, "
                                f"post_json_pieces={_post_json_piece_count}, "
                                f"post_json_chars={_post_json_char_count})",
                                file=sys.stderr,
                                flush=True,
                            )
                            _post_json_first_logged = True
                    if _loop_detected:
                        break
                    
                    # (1) 누적 문자 하드캡
                    _acc_len = sum(len(s) for s in acc)
                    if _acc_len > _ACC_HARD_CAP:
                        ts = self._timestamp()
                        print(f"\n[{ts}][llm-stream] ⚠️ 누적 출력 하드캡 초과 ({_acc_len:,}자 > {_ACC_HARD_CAP:,}), 조기 종료", file=sys.stderr, flush=True)
                        _loop_detected = True
                        break
                    
                    # (2) 텍스트 레벨 반복 패턴 탐지 (N토큰마다)
                    if token_count - _last_text_check_count >= _TEXT_CHECK_INTERVAL:
                        _last_text_check_count = token_count
                        _full = "".join(acc)
                        _tail = _full[-800:] if len(_full) > 800 else _full
                        if len(_tail) >= 100:
                            _found_loop = False
                            # 꼬리에서 다양한 길이의 부분문자열을 뽑아 전체에서 count
                            for _plen in (8, 15, 30, 60, 120):
                                if _plen > len(_tail) // 3:
                                    continue
                                _candidate = _tail[-_plen:]
                                # JSON 구조 문자(공백/따옴표/괄호/콜론/콤마)로만 구성된 패턴은 무시
                                _content_chars = _candidate.translate(str.maketrans('', '', ' \t\n\r"{}[]:,'))
                                if len(_content_chars) < max(2, _plen // 3):
                                    continue
                                # JSON value 리터럴(null/false/true)로 끝나는 짧은 패턴은 정상 구조
                                _stripped_cand = _candidate.strip()
                                if _plen <= 15 and any(_stripped_cand.endswith(sv) for sv in _JSON_VALUE_SUFFIXES):
                                    continue
                                _cnt = _tail.count(_candidate)
                                _threshold = _TEXT_REPEAT_THRESHOLDS.get(_plen, 5)
                                _cand_l = _candidate.lower()
                                _pct_cnt = _candidate.count("%")
                                _looks_urlish = (
                                    ("http" in _cand_l)
                                    or ("www." in _cand_l)
                                    or (".com" in _cand_l)
                                    or (".net" in _cand_l)
                                    or ("viewimage.php" in _cand_l)
                                    or ("%2f" in _cand_l)
                                    or ("%3a" in _cand_l)
                                    or ("%20" in _cand_l)
                                    or (_pct_cnt >= max(2, _plen // 8))
                                )
                                if _looks_urlish:
                                    _threshold = max(_threshold, _URL_REPEAT_THRESHOLD)
                                if _cnt >= _threshold:
                                    ts = self._timestamp()
                                    _show = _candidate[:30].replace('\n', '\\n')
                                    print(f"\n[{ts}][llm-stream] ⚠️ 텍스트 반복 감지 ('{_show}' x{_cnt}, 패턴{_plen}자), 조기 종료", file=sys.stderr, flush=True)
                                    _found_loop = True
                                    break
                            if _found_loop:
                                _loop_detected = True
                                break
            
            _elapsed = _time.time() - _start
            ts = self._timestamp()
            print(f"\n[{ts}][llm-stream] ■ {tag} 완료 ({_elapsed:.2f}s)", file=sys.stderr, flush=True)
            if last_finish_reason:
                print(
                    f"[{ts}][llm-stream] finish_reason={last_finish_reason}",
                    file=sys.stderr,
                    flush=True,
                )
                if last_finish_reason.lower() in {"length", "max_tokens"}:
                    print(
                        f"[{ts}][llm-warn] 출력이 max_tokens 제한으로 종료됐을 가능성",
                        file=sys.stderr,
                        flush=True,
                    )
            
            # compact JSON(줄바꿈 없음)으로 출력된 경우 pretty-print 재출력
            _raw = "".join(acc).strip()
            if use_grammar and _json_complete_pos >= 0:
                _raw = self._trim_to_completed_json(_raw, _json_complete_pos)
            if _raw and "\n" not in _raw and _raw.startswith("{"):
                try:
                    import json as _json_local
                    _parsed = _json_local.loads(_raw)
                    _pretty = _json_local.dumps(_parsed, ensure_ascii=False, indent=2)
                    print(f"[{ts}][llm-stream] (pretty-reprint)\n{_pretty}", file=sys.stderr, flush=True)
                except Exception:
                    pass
            
            # usage 정보 추출 및 정규화
            usage = last_chunk.get("usage") if last_chunk and isinstance(last_chunk, dict) else None
            
            if usage:
                prompt_tokens = usage.get('prompt_tokens', 0)
                completion_tokens = usage.get('completion_tokens', token_count)
                total_tokens = usage.get('total_tokens', prompt_tokens + completion_tokens)
            else:
                # 추정치 계산
                prompt_chars = sum(len(m.get("content", "")) for m in messages)
                prompt_tokens = prompt_chars // 3
                completion_tokens = token_count
                total_tokens = prompt_tokens + token_count
            
            # 정규화된 usage 저장
            self.last_usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }
            self.last_finish_reason = last_finish_reason
            
            # 출력
            if self.print_timings:
                print(f"[{ts}][llm-usage] ── {tag} ──", file=sys.stderr, flush=True)
                print(f"  prompt_tokens: {prompt_tokens}{' (추정)' if not usage else ''}", file=sys.stderr, flush=True)
                print(f"  completion_tokens: {completion_tokens}", file=sys.stderr, flush=True)
                print(f"  total_tokens: {total_tokens}{' (추정)' if not usage else ''}", file=sys.stderr, flush=True)
                print(f"  elapsed: {_elapsed:.2f}s", file=sys.stderr, flush=True)
                if _elapsed > 0:
                    print(f"  response_tok/s: {completion_tokens / _elapsed:.2f}", file=sys.stderr, flush=True)
                    if prompt_tokens > 0:
                        print(f"  prompt_tok/s: {prompt_tokens / _elapsed:.2f}", file=sys.stderr, flush=True)
                try:
                    llm.print_timings()
                    llm.reset_timings()
                except Exception:
                    pass
            
            return "".join(acc)
        
        # 비스트리밍 모드
        print(f"[{ts}][llm] ▶ {tag} 요청 시작...", file=sys.stderr, flush=True)
        
        data = llm.create_chat_completion(
            messages=messages,
            temperature=self.temperature,
            top_p=self.top_p,
            min_p=self.min_p,
            repeat_penalty=self.repeat_penalty,
            max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
            grammar=None if self.think_stream or not use_grammar else self._get_json_object_grammar(),
        )
        
        _elapsed = _time.time() - _start
        ts = self._timestamp()
        print(f"[{ts}][llm] ■ {tag} 완료 ({_elapsed:.2f}s)", file=sys.stderr, flush=True)
        
        self.last_usage = data.get("usage") if isinstance(data, dict) else None
        self.last_model = data.get("model") if isinstance(data, dict) else None
        self._print_usage_details(tag, data, _elapsed)
        
        if self.print_timings:
            try:
                llm.print_timings()
                llm.reset_timings()
            except Exception:
                pass
        
        try:
            content = data["choices"][0]["message"]["content"]
            return content
        except (KeyError, IndexError):
            return "{}"

    def enrich(self, payload: List[Dict[str, Any]]) -> Dict[str, Any]:
        if self.backend == "local":
            def _do_local():
                data = self._enrich_local(payload)
                self.last_usage = data.get("usage") if isinstance(data, dict) else None
                self.last_model = data.get("model") if isinstance(data, dict) else None
                return data
            
            return retry_with_backoff(
                _do_local,
                max_retries=self.max_retries,
                base_delay=self.retry_base_delay,
                exceptions=(Exception,),
                on_failure=lambda e: {"choices": [{"message": {"content": "[]"}}], "error": str(e)},
            )
        
        url = f"{self.endpoint.rstrip('/')}/v1/chat/completions"
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": __import__("json").dumps(payload, ensure_ascii=False)},
            ],
            "temperature": self.temperature,
            "top_p": self.top_p,
            "min_p": self.min_p,
            "repeat_penalty": self.repeat_penalty,
            "max_tokens": self.max_tokens,
            # llama-server에서 GLM 모델의 thinking 활성화
            "enable_thinking": self.enable_thinking,
            "chat_template_kwargs": {"enable_thinking": self.enable_thinking},
        }
        body = self._adapt_body_for_server(body)
        
        def _do_http():
            response = httpx.post(url, json=body, timeout=self.timeout_s)
            response.raise_for_status()
            data = response.json()
            self.last_usage = data.get("usage") if isinstance(data, dict) else None
            self.last_model = data.get("model") if isinstance(data, dict) else None
            return data
        
        return retry_with_backoff(
            _do_http,
            max_retries=self.max_retries,
            base_delay=self.retry_base_delay,
            exceptions=(httpx.HTTPError, httpx.TimeoutException, ConnectionError, OSError),
            on_failure=lambda e: {"choices": [{"message": {"content": "[]"}}], "error": str(e)},
        )

    def _get_local_llm(self):
        if self._local_llm is not None:
            return self._local_llm

        with self._local_lock:
            if self._local_llm is not None:
                return self._local_llm

            if not self.model_path:
                raise RuntimeError(
                    "LLM_BACKEND=local 인 경우 LLM_MODEL_PATH (GGUF 파일 경로)가 필요합니다."
                )

            try:
                from llama_cpp import Llama  # type: ignore
                from llama_cpp import llama_cpp  # type: ignore
                from llama_cpp import llama_chat_format as lcf  # type: ignore
            except Exception as exc:  # pragma: no cover
                raise RuntimeError(
                    "llama-cpp-python이 설치되어 있지 않습니다. `pip install llama-cpp-python`를 먼저 실행하세요."
                ) from exc

            # CUDA/빌드 정보 출력(원하면)
            if os.getenv("LLM_PRINT_SYSTEM_INFO", "0") == "1":
                try:
                    print(llama_cpp.llama_print_system_info(), file=sys.stderr)
                except Exception:
                    pass

            n_ctx = int(os.getenv("LLM_N_CTX", "4096"))
            n_threads_env = int(os.getenv("LLM_N_THREADS", "0"))
            n_threads = n_threads_env if n_threads_env > 0 else None
            n_gpu_layers = int(os.getenv("LLM_N_GPU_LAYERS", "0"))

            # 1) GGUF의 tokenizer.chat_template(Jinja)가 있으면 그걸 최우선으로 사용 (가장 정확)
            # 2) 없으면 기존처럼 chat_format 추정/폴백
            chat_handler = None
            chosen_chat_format = self.chat_format

            use_jinja = os.getenv("LLM_USE_GGUF_JINJA", "1") == "1"
            if use_jinja:
                meta_probe = None
                try:
                    meta_probe = Llama(
                        model_path=self.model_path,
                        vocab_only=True,
                        n_ctx=16,
                        n_gpu_layers=0,
                        verbose=False,
                    )
                    meta = getattr(meta_probe, "metadata", {}) or {}
                    template = meta.get("tokenizer.chat_template")
                    
                    # vocab_only probe는 메타데이터만 읽고 즉시 정리
                    if meta_probe is not None:
                        try:
                            # 명시적으로 컨텍스트 해제
                            if hasattr(meta_probe, '_ctx'):
                                meta_probe._ctx = None
                            if hasattr(meta_probe, 'close'):
                                meta_probe.close()
                        except Exception:
                            pass
                        try:
                            del meta_probe
                        except Exception:
                            pass
                        meta_probe = None
                    
                    if template:
                        # bos/eos 토큰 문자열이 비어도 formatter는 동작하며, 템플릿 자체가 주로 역할 토큰을 정의한다.
                        eos_id = meta.get("tokenizer.ggml.eos_token_id")
                        try:
                            eos_id_int = int(eos_id) if eos_id is not None else None
                        except Exception:
                            eos_id_int = None

                        bos = "<s>"
                        eos = "</s>"
                        
                        # GLM-4.7-Flash 등 reasoning 모델: enable_thinking 설정에 따라 템플릿 수정
                        # enable_thinking=False면 <think> 블록을 생성하지 않음 (빠른 출력)
                        if not self.enable_thinking:
                            # chat_template의 enable_thinking 조건을 강제로 False로 설정
                            # "else '<think>'" -> "</think>'" (reasoning 비활성화)
                            old_pattern = "{{- '</think>' if (enable_thinking is defined and not enable_thinking) else '<think>' -}}"
                            new_pattern = "{{- '</think>' -}}"
                            if old_pattern in template:
                                template = template.replace(old_pattern, new_pattern)
                                if os.getenv("LLM_PRINT_SYSTEM_INFO", "0") == "1":
                                    print("[llm] enable_thinking=False (reasoning disabled)", file=sys.stderr)
                        
                        formatter = lcf.Jinja2ChatFormatter(
                            template=template,
                            eos_token=eos,
                            bos_token=bos,
                            add_generation_prompt=True,
                            stop_token_ids=[eos_id_int] if eos_id_int is not None else None,
                        )
                        self._local_llm = None  # ensure not set early
                        chat_handler = lcf.chat_formatter_to_chat_completion_handler(formatter)
                        chosen_chat_format = None
                        if os.getenv("LLM_PRINT_SYSTEM_INFO", "0") == "1":
                            print("[llm] chat_template=gguf(tokenizer.chat_template)", file=sys.stderr)
                except Exception:
                    chat_handler = None
                finally:
                    # vocab_only probe를 명시적으로 정리하여 메모리/리소스 해제
                    if meta_probe is not None:
                        try:
                            if hasattr(meta_probe, '_ctx'):
                                meta_probe._ctx = None
                            if hasattr(meta_probe, 'close'):
                                meta_probe.close()
                        except Exception:
                            pass
                        try:
                            del meta_probe
                        except Exception:
                            pass
                        meta_probe = None

            if chat_handler is None:
                if not chosen_chat_format:
                    try:
                        chosen_chat_format = lcf.guess_chat_format_from_gguf_metadata(self.model_path)
                    except Exception:
                        chosen_chat_format = None
                if not chosen_chat_format:
                    chosen_chat_format = "chatml"
                if os.getenv("LLM_PRINT_SYSTEM_INFO", "0") == "1":
                    print(f"[llm] chat_format={chosen_chat_format}", file=sys.stderr)

            # Flash Attention & KV Cache 설정
            flash_attn = os.getenv("LLM_FLASH_ATTN", "1") == "1"
            # KV cache quantization 타입 매핑 (llama_cpp 내부 enum 값)
            # GGML_TYPE: f32=0, f16=1, q4_0=2, q4_1=3, q5_0=6, q5_1=7, q8_0=8
            cache_type_map = {
                "f32": 0, "f16": 1, "q4_0": 2, "q4_1": 3,
                "q5_0": 6, "q5_1": 7, "q8_0": 8,
            }
            cache_type_k_str = os.getenv("LLM_CACHE_TYPE_K", "f16")
            cache_type_v_str = os.getenv("LLM_CACHE_TYPE_V", "f16")
            cache_type_k = cache_type_map.get(cache_type_k_str, 1)  # 기본 f16
            cache_type_v = cache_type_map.get(cache_type_v_str, 1)

            if os.getenv("LLM_PRINT_SYSTEM_INFO", "0") == "1":
                print(f"[llm] flash_attn={flash_attn}, cache_type_k={cache_type_k_str}({cache_type_k}), cache_type_v={cache_type_v_str}({cache_type_v})", file=sys.stderr)

            self._local_llm = Llama(
                model_path=self.model_path,
                n_ctx=n_ctx,
                n_threads=n_threads,
                n_gpu_layers=n_gpu_layers,
                chat_format=chosen_chat_format,
                chat_handler=chat_handler,
                flash_attn=flash_attn,
                type_k=cache_type_k,
                type_v=cache_type_v,
                verbose=False,
            )
            return self._local_llm

    def _get_json_array_grammar(self):
        """
        출력이 JSON 외 텍스트(분석/설명)로 새는 것을 막기 위해 JSON array 문법을 강제한다.
        - 모델이 반드시 '[' 로 시작하는 유효한 JSON만 생성 가능
        """
        if not self.json_grammar:
            return None
        if self._json_grammar_obj is not None:
            return self._json_grammar_obj
        try:
            from llama_cpp import LlamaGrammar  # type: ignore
        except Exception:
            return None

        # Generic JSON grammar (array root) for llama.cpp GBNF
        grammar = r"""
root ::= ws array ws
array ::= "[" ws (value (ws "," ws value)*)? ws "]"
value ::= object | array | string | number | "true" | "false" | "null"
object ::= "{" ws (member (ws "," ws member)*)? ws "}"
member ::= string ws ":" ws value
string ::= "\"" chars "\""
chars ::= (char)*
char ::= unescaped | escape
unescaped ::= [^"\\\x00-\x1F]
escape ::= "\\" (["\\/bfnrt] | "u" hex hex hex hex)
hex ::= [0-9a-fA-F]
number ::= integer fraction? exponent?
integer ::= "-"? ("0" | [1-9] [0-9]*)
fraction ::= "." [0-9]+
exponent ::= [eE] [+-]? [0-9]+
ws ::= [ \t\n\r]*
"""
        self._json_grammar_obj = LlamaGrammar.from_string(grammar)
        return self._json_grammar_obj

    def _get_json_object_grammar(self):
        if not self.json_grammar:
            return None
        if self._json_object_grammar_obj is not None:
            return self._json_object_grammar_obj
        try:
            from llama_cpp import LlamaGrammar  # type: ignore
        except Exception:
            return None

        grammar = r"""
root ::= ws object ws
array ::= "[" ws (value (ws "," ws value)*)? ws "]"
value ::= object | array | string | number | "true" | "false" | "null"
object ::= "{" ws (member (ws "," ws member)*)? ws "}"
member ::= string ws ":" ws value
string ::= "\"" chars "\""
chars ::= (char)*
char ::= unescaped | escape
unescaped ::= [^"\\\x00-\x1F]
escape ::= "\\" (["\\/bfnrt] | "u" hex hex hex hex)
hex ::= [0-9a-fA-F]
number ::= integer fraction? exponent?
integer ::= "-"? ("0" | [1-9] [0-9]*)
fraction ::= "." [0-9]+
exponent ::= [eE] [+-]? [0-9]+
ws ::= [ \t\n\r]*
"""
        self._json_object_grammar_obj = LlamaGrammar.from_string(grammar)
        return self._json_object_grammar_obj

    @staticmethod
    def _parse_json_object_best_effort(text: str) -> Optional[Dict[str, Any]]:
        import json
        import re

        if not isinstance(text, str):
            return None

        s = text.strip()
        if not s:
            return None

        s = re.sub(r"<think>[\s\S]*?</think>", "", s, flags=re.IGNORECASE).strip()
        s = re.sub(r"</think>", "", s, flags=re.IGNORECASE).strip()

        fence_matches = list(re.finditer(r"```(?:json)?\s*([\s\S]*?)```", s, flags=re.IGNORECASE))
        if fence_matches:
            s = fence_matches[-1].group(1).strip()

        try:
            obj = json.loads(s)
            return obj if isinstance(obj, dict) else None
        except Exception:
            pass

        brace_depth = 0
        start_idx = -1
        for i, ch in enumerate(s):
            if ch == "{":
                if brace_depth == 0:
                    start_idx = i
                brace_depth += 1
            elif ch == "}":
                brace_depth -= 1
                if brace_depth == 0 and start_idx >= 0:
                    try:
                        obj = json.loads(s[start_idx:i + 1])
                        return obj if isinstance(obj, dict) else None
                    except Exception:
                        start_idx = -1
                        continue
        return None

    def complete_json(
        self,
        system_prompt: str,
        user_payload: Any,
        *,
        tag: str = "complete_json",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Generic JSON-object completion helper for ad-hoc structured tasks."""
        import json as _json
        import time as _time

        user_content = (
            user_payload
            if isinstance(user_payload, str)
            else _json.dumps(user_payload, ensure_ascii=False)
        )
        messages = [
            {"role": "system", "content": str(system_prompt or "")},
            {"role": "user", "content": user_content},
        ]
        self._dump_messages(tag, messages)
        _start = _time.time()
        resolved_temp = self.temperature if temperature is None else float(temperature)
        resolved_max_tokens = max(128, min(self.max_tokens, int(max_tokens or 640)))

        if self.backend == "local":
            llm = self._get_local_llm()
            ts = self._timestamp()
            print(f"[{ts}][llm-stream] ▶ {tag} 생성 시작...", file=sys.stderr, flush=True)

            if self.think_stream and self.stream:
                chunks = llm.create_chat_completion(
                    messages=messages,
                    temperature=resolved_temp,
                    top_p=self.top_p,
                    min_p=self.min_p,
                    repeat_penalty=self.repeat_penalty,
                    max_tokens=resolved_max_tokens,
                    grammar=None,
                    stream=True,
                )
                acc: List[str] = []
                token_count = 0
                last_chunk = None
                for chunk in chunks:
                    last_chunk = chunk
                    try:
                        delta = chunk["choices"][0].get("delta", {})
                        piece = delta.get("content", "")
                    except Exception:
                        piece = ""
                    if piece:
                        acc.append(piece)
                        token_count += 1
                        print(piece, end="", file=sys.stderr, flush=True)

                _elapsed = _time.time() - _start
                ts = self._timestamp()
                print(f"\n[{ts}][llm-stream] ■ {tag} 완료 ({_elapsed:.2f}s)", file=sys.stderr, flush=True)
                if self.print_timings and isinstance(last_chunk, dict):
                    self._print_usage_details(tag, last_chunk, _elapsed)
                parsed = self._parse_json_object_best_effort("".join(acc))
                return parsed if parsed else {}

            data = llm.create_chat_completion(
                messages=messages,
                temperature=resolved_temp,
                top_p=self.top_p,
                min_p=self.min_p,
                repeat_penalty=self.repeat_penalty,
                max_tokens=resolved_max_tokens,
                grammar=None if self.think_stream else self._get_json_object_grammar(),
            )
            _elapsed = _time.time() - _start
            ts = self._timestamp()
            print(f"[{ts}][llm-stream] ■ {tag} 완료 ({_elapsed:.2f}s)", file=sys.stderr, flush=True)
            self._print_usage_details(tag, data, _elapsed)
            try:
                self.last_usage = data.get("usage") if isinstance(data, dict) else None
                self.last_model = data.get("model") if isinstance(data, dict) else None
                content = data["choices"][0]["message"]["content"]
            except Exception:
                return {}
            parsed = self._parse_json_object_best_effort(content)
            return parsed if parsed else {}

        url = f"{self.endpoint.rstrip('/')}/v1/chat/completions"
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": resolved_temp,
            "top_p": self.top_p,
            "min_p": self.min_p,
            "repeat_penalty": self.repeat_penalty,
            "max_tokens": resolved_max_tokens,
            "response_format": {"type": "json_object"},
            "enable_thinking": False,
        }
        body = self._adapt_body_for_server(body)

        if self.stream:
            def _do_http_stream() -> Dict[str, Any]:
                content = self._http_stream_completion(url, body, tag, messages)
                parsed = self._parse_json_object_best_effort(content)
                return parsed if parsed else {}

            return retry_with_backoff(
                _do_http_stream,
                max_retries=self.max_retries,
                base_delay=self.retry_base_delay,
                exceptions=(httpx.HTTPError, httpx.TimeoutException, ConnectionError, OSError),
                on_failure=lambda e: {},
            )

        def _do_http() -> Dict[str, Any]:
            resp = httpx.post(url, json=body, timeout=self.timeout_s)
            resp.raise_for_status()
            data = resp.json()
            self.last_usage = data.get("usage") if isinstance(data, dict) else None
            self.last_model = data.get("model") if isinstance(data, dict) else None
            try:
                content = data["choices"][0]["message"]["content"]
            except Exception:
                return {}
            parsed = self._parse_json_object_best_effort(content)
            return parsed if parsed else {}

        return retry_with_backoff(
            _do_http,
            max_retries=self.max_retries,
            base_delay=self.retry_base_delay,
            exceptions=(httpx.HTTPError, httpx.TimeoutException, ConnectionError, OSError),
            on_failure=lambda e: {},
        )

    def _build_multimodal_user_content(
        self,
        user_text: str,
        images: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        content: List[Dict[str, Any]] = [{"type": "text", "text": str(user_text or "")}]
        for image in images:
            if not isinstance(image, dict):
                continue
            data_url = str(image.get("data_url") or "").strip()
            raw_data = image.get("data") or image.get("bytes")
            mime_type = str(image.get("mime_type") or "image/jpeg").strip() or "image/jpeg"
            if not data_url:
                if not isinstance(raw_data, (bytes, bytearray)):
                    continue
                encoded = base64.b64encode(bytes(raw_data)).decode("ascii")
                data_url = f"data:{mime_type};base64,{encoded}"
            image_url: Dict[str, Any] = {"url": data_url}
            detail = str(image.get("detail") or "").strip()
            if detail:
                image_url["detail"] = detail
            content.append({"type": "image_url", "image_url": image_url})
        return content

    def complete_multimodal_json(
        self,
        system_prompt: str,
        user_text: str,
        images: List[Dict[str, Any]],
        *,
        tag: str = "complete_multimodal_json",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Remote vLLM 전용 멀티모달 JSON-object completion helper."""
        if self.backend == "local" or self.server_type != "vllm":
            return {}

        user_content = self._build_multimodal_user_content(user_text, images)
        messages = [
            {"role": "system", "content": str(system_prompt or "")},
            {"role": "user", "content": user_content},
        ]
        debug_messages = [
            {"role": "system", "content": str(system_prompt or "")},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "text": str(user_text or ""),
                        "image_count": len(images or []),
                        "image_sources": [
                            {
                                "source_url": str((img or {}).get("source_url") or ""),
                                "mime_type": str((img or {}).get("mime_type") or ""),
                                "size": len((img or {}).get("data") or (img or {}).get("bytes") or b""),
                            }
                            for img in (images or [])
                            if isinstance(img, dict)
                        ],
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        self._dump_messages(tag, debug_messages)

        resolved_temp = self.temperature if temperature is None else float(temperature)
        default_vlm_max = int(os.getenv("LLM_VLM_MAX_TOKENS", "12288"))
        resolved_max_tokens = max(512, min(self.max_tokens, int(max_tokens or default_vlm_max)))
        url = f"{self.endpoint.rstrip('/')}/v1/chat/completions"
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": resolved_temp,
            "top_p": self.top_p,
            "min_p": self.min_p,
            "repeat_penalty": self.repeat_penalty,
            "max_tokens": resolved_max_tokens,
            "response_format": {"type": "json_object"},
            "enable_thinking": False,
        }
        body = self._adapt_body_for_server(body)

        def _do_http() -> Dict[str, Any]:
            resp = httpx.post(url, json=body, timeout=self.timeout_s)
            resp.raise_for_status()
            data = resp.json()
            self.last_usage = data.get("usage") if isinstance(data, dict) else None
            self.last_model = data.get("model") if isinstance(data, dict) else None
            try:
                content = data["choices"][0]["message"]["content"]
            except Exception:
                return {}
            parsed = self._parse_json_object_best_effort(content)
            return parsed if parsed else {}

        return retry_with_backoff(
            _do_http,
            max_retries=self.max_retries,
            base_delay=self.retry_base_delay,
            exceptions=(httpx.HTTPError, httpx.TimeoutException, ConnectionError, OSError),
            on_failure=lambda e: {},
        )

    def plan_search(self, payload: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        LLM이 스스로 검색 필요 여부/검색어를 제안하게 하는 1단계 호출.
        반환은 JSON object여야 한다.
        """
        import time as _time
        messages = [
            {"role": "system", "content": SEARCH_PLANNER_PROMPT},
            {"role": "user", "content": __import__("json").dumps(payload, ensure_ascii=False)},
        ]
        self._dump_messages("plan_search", messages)
        _start = _time.time()

        def _parse_json_object_best_effort(text: str) -> Optional[Dict[str, Any]]:
            """
            LLM 출력에서 JSON object를 추출한다.
            - markdown code fence 제거 (```json ... ```)
            - <think>...</think> 블록 제거
            - 첫 번째 {...} 매칭
            """
            import re
            import json
            
            if not isinstance(text, str):
                return None
            s = text.strip()
            
            # 1) <think>...</think> 블록 제거 (reasoning output)
            s = re.sub(r"<think>[\s\S]*?</think>", "", s, flags=re.IGNORECASE)
            s = s.strip()
            
            # 2) markdown code fence 제거: ```json ... ``` 또는 ``` ... ```
            # 먼저 코드 블록 내용만 추출 시도
            fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", s, flags=re.IGNORECASE)
            if fence_match:
                s = fence_match.group(1).strip()
            
            # 3) 직접 JSON 파싱 시도
            try:
                obj = json.loads(s)
                return obj if isinstance(obj, dict) else None
            except Exception:
                pass
            
            # 4) 첫 번째 {...} 블록 추출 (greedy하게 마지막 }까지)
            m = re.search(r"\{[\s\S]*\}", s)
            if not m:
                return None
            try:
                obj = json.loads(m.group(0))
                return obj if isinstance(obj, dict) else None
            except Exception:
                return None

        if self.backend == "local":
            llm = self._get_local_llm()
            ts = self._timestamp()
            print(f"[{ts}][llm-stream] ▶ plan_search 생성 시작...", file=sys.stderr, flush=True)
            
            # think_stream 모드면 스트리밍으로 reasoning 출력
            if self.think_stream and self.stream:
                chunks = llm.create_chat_completion(
                    messages=messages,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    min_p=self.min_p,
                    repeat_penalty=self.repeat_penalty,
                    max_tokens=self.max_tokens,  # LLM_MAX_TOKENS 환경변수로 통일 관리
                    grammar=None,
                    stream=True,
                )
                acc: List[str] = []
                token_count = 0
                last_chunk = None
                for chunk in chunks:
                    last_chunk = chunk
                    try:
                        delta = chunk["choices"][0].get("delta", {})
                        piece = delta.get("content", "")
                    except Exception:
                        piece = ""
                    if piece:
                        acc.append(piece)
                        token_count += 1
                        print(piece, end="", file=sys.stderr, flush=True)
                
                _elapsed = _time.time() - _start
                ts = self._timestamp()
                print(f"\n[{ts}][llm-stream] ■ plan_search 완료 ({_elapsed:.2f}s)", file=sys.stderr, flush=True)
                
                # usage 정보 출력
                usage = last_chunk.get("usage") if last_chunk and isinstance(last_chunk, dict) else None
                if self.print_timings:
                    print(f"[{ts}][llm-usage] ── plan_search ──", file=sys.stderr, flush=True)
                    if usage:
                        print(f"  prompt_tokens: {usage.get('prompt_tokens', 0)}", file=sys.stderr, flush=True)
                        print(f"  completion_tokens: {usage.get('completion_tokens', token_count)}", file=sys.stderr, flush=True)
                        print(f"  total_tokens: {usage.get('total_tokens', 0)}", file=sys.stderr, flush=True)
                    else:
                        prompt_chars = sum(len(m.get("content", "")) for m in messages)
                        est_prompt_tokens = prompt_chars // 3
                        print(f"  prompt_tokens (추정): ~{est_prompt_tokens}", file=sys.stderr, flush=True)
                        print(f"  completion_tokens: {token_count}", file=sys.stderr, flush=True)
                        print(f"  total_tokens (추정): ~{est_prompt_tokens + token_count}", file=sys.stderr, flush=True)
                    print(f"  elapsed: {_elapsed:.2f}s", file=sys.stderr, flush=True)
                    if _elapsed > 0:
                        print(f"  response_tok/s: {token_count / _elapsed:.2f}", file=sys.stderr, flush=True)
                
                content = "".join(acc)
                parsed = _parse_json_object_best_effort(content)
                if parsed is None:
                    return {"need_search": False, "queries": [], "why": "파싱 실패"}
                why = parsed.get("why", "")
                if isinstance(why, str) and why and not self._looks_korean(why):
                    parsed["why"] = "검색 계획 사유(원문이 한국어가 아님)"
                return parsed
            
            # 비스트리밍 모드 (기존)
            data = llm.create_chat_completion(
                messages=messages,
                temperature=self.temperature,
                top_p=self.top_p,
                min_p=self.min_p,
                repeat_penalty=self.repeat_penalty,
                max_tokens=self.max_tokens,  # LLM_MAX_TOKENS 환경변수로 통일 관리
                grammar=None if self.think_stream else self._get_json_object_grammar(),
            )
            _elapsed = _time.time() - _start
            ts = self._timestamp()
            print(f"[{ts}][llm-stream] ■ plan_search 완료 ({_elapsed:.2f}s)", file=sys.stderr, flush=True)
            self._print_usage_details("plan_search", data, _elapsed)
            try:
                self.last_usage = data.get("usage") if isinstance(data, dict) else None
                self.last_model = data.get("model") if isinstance(data, dict) else None
                content = data["choices"][0]["message"]["content"]
                parsed = _parse_json_object_best_effort(content)
                if parsed is None:
                    return {"need_search": False, "queries": [], "why": "파싱 실패"}
                why = parsed.get("why", "")
                if isinstance(why, str) and why and not self._looks_korean(why):
                    parsed["why"] = "검색 계획 사유(원문이 한국어가 아님)"
                return parsed
            except Exception:
                return {"need_search": False, "queries": [], "why": "파싱 실패"}

        # http backend: best-effort (server may or may not support response_format)
        url = f"{self.endpoint.rstrip('/')}/v1/chat/completions"
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "min_p": self.min_p,
            "repeat_penalty": self.repeat_penalty,
            "max_tokens": max(64, min(self.max_tokens, 256)),
            "response_format": {"type": "json_object"},
            # llama-server에서 GLM 모델의 thinking 활성화
            "enable_thinking": self.enable_thinking,
            "chat_template_kwargs": {"enable_thinking": self.enable_thinking},
        }
        body = self._adapt_body_for_server(body)
        
        # 스트리밍 모드면 HTTP 스트리밍 사용
        if self.stream:
            def _do_http_stream():
                content = self._http_stream_completion(url, body, "plan_search", messages)
                parsed = _parse_json_object_best_effort(content)
                if parsed is None:
                    return {"need_search": False, "queries": [], "why": "파싱 실패"}
                why = parsed.get("why", "")
                if isinstance(why, str) and why and not self._looks_korean(why):
                    parsed["why"] = "검색 계획 사유(원문이 한국어가 아님)"
                return parsed
            
            return retry_with_backoff(
                _do_http_stream,
                max_retries=self.max_retries,
                base_delay=self.retry_base_delay,
                exceptions=(httpx.HTTPError, httpx.TimeoutException, ConnectionError, OSError),
                on_failure=lambda e: {"need_search": False, "queries": [], "why": f"LLM 오류: {type(e).__name__}"},
            )
        
        def _do_http():
            resp = httpx.post(url, json=body, timeout=self.timeout_s)
            resp.raise_for_status()
            data = resp.json()
            self.last_usage = data.get("usage") if isinstance(data, dict) else None
            self.last_model = data.get("model") if isinstance(data, dict) else None
            try:
                content = data["choices"][0]["message"]["content"]
                parsed = _parse_json_object_best_effort(content)
                if parsed is None:
                    return {"need_search": False, "queries": [], "why": "파싱 실패"}
                why = parsed.get("why", "")
                if isinstance(why, str) and why and not self._looks_korean(why):
                    parsed["why"] = "검색 계획 사유(원문이 한국어가 아님)"
                return parsed
            except Exception:
                return {"need_search": False, "queries": [], "why": "파싱 실패"}
        
        return retry_with_backoff(
            _do_http,
            max_retries=self.max_retries,
            base_delay=self.retry_base_delay,
            exceptions=(httpx.HTTPError, httpx.TimeoutException, ConnectionError, OSError),
            on_failure=lambda e: {"need_search": False, "queries": [], "why": f"LLM 오류: {type(e).__name__}"},
        )

    def generate_hypothesis(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        중간 분석 단계: 검색 결과를 보고 축약어가 무슨 작품인지 가설 생성.
        점진적 분석의 핵심 - enrich 전에 문맥을 파악하고 추가 검색 필요 여부 판단.
        
        Args:
            payload: {
                "post": {...},
                "detected_term": "축약어",
                "search_results": [...],
                "alias_candidates": [...]
            }
        
        Returns:
            {
                "hypothesis": {"likely_title": ..., "confidence": ..., ...},
                "search_quality": {...},
                "morphological_analysis": {...}
            }
        """
        import time as _time
        import json as _json
        
        messages = [
            {"role": "system", "content": HYPOTHESIS_PROMPT},
            {"role": "user", "content": _json.dumps(payload, ensure_ascii=False)},
        ]
        self._dump_messages("hypothesis", messages)
        _start = _time.time()

        def _parse_json_object(text: str) -> Optional[Dict[str, Any]]:
            import re
            import json
            if not isinstance(text, str):
                return None
            s = text.strip()
            s = re.sub(r"<think>[\s\S]*?</think>", "", s, flags=re.IGNORECASE).strip()
            fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", s, flags=re.IGNORECASE)
            if fence_match:
                s = fence_match.group(1).strip()
            try:
                obj = json.loads(s)
                return obj if isinstance(obj, dict) else None
            except Exception:
                pass
            m = re.search(r"\{[\s\S]*\}", s)
            if not m:
                return None
            try:
                obj = json.loads(m.group(0))
                return obj if isinstance(obj, dict) else None
            except Exception:
                return None

        default_response = {
            "hypothesis": {"likely_title": None, "confidence": "None", "reasoning": "분석 실패", "needs_verification": False, "verification_query": None},
            "search_quality": {"has_novel_platform_result": False, "has_wiki_result": False, "best_matching_url": None, "relevance_score": "None"},
            "morphological_analysis": {"term_breakdown": "", "possible_expansions": [], "match_type": "none"}
        }

        if self.backend == "local":
            llm = self._get_local_llm()
            ts = self._timestamp()
            print(f"[{ts}][llm-stream] ▶ hypothesis 생성 시작...", file=sys.stderr, flush=True)
            
            if self.think_stream and self.stream:
                chunks = llm.create_chat_completion(
                    messages=messages,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    min_p=self.min_p,
                    repeat_penalty=self.repeat_penalty,
                    max_tokens=self.max_tokens,
                    grammar=None,
                    stream=True,
                )
                acc: List[str] = []
                token_count = 0
                for chunk in chunks:
                    try:
                        delta = chunk["choices"][0].get("delta", {})
                        piece = delta.get("content", "")
                    except Exception:
                        piece = ""
                    if piece:
                        acc.append(piece)
                        token_count += 1
                        print(piece, end="", file=sys.stderr, flush=True)
                
                _elapsed = _time.time() - _start
                ts = self._timestamp()
                print(f"\n[{ts}][llm-stream] ■ hypothesis 완료 ({_elapsed:.2f}s)", file=sys.stderr, flush=True)
                
                content = "".join(acc)
                parsed = _parse_json_object(content)
                return parsed if parsed else default_response
            
            # 비스트리밍
            data = llm.create_chat_completion(
                messages=messages,
                temperature=self.temperature,
                top_p=self.top_p,
                min_p=self.min_p,
                repeat_penalty=self.repeat_penalty,
                max_tokens=self.max_tokens,
                grammar=None if self.think_stream else self._get_json_object_grammar(),
            )
            _elapsed = _time.time() - _start
            ts = self._timestamp()
            print(f"[{ts}][llm-stream] ■ hypothesis 완료 ({_elapsed:.2f}s)", file=sys.stderr, flush=True)
            self._print_usage_details("hypothesis", data, _elapsed)
            try:
                content = data["choices"][0]["message"]["content"]
                parsed = _parse_json_object(content)
                return parsed if parsed else default_response
            except Exception:
                return default_response

        # HTTP backend
        url = f"{self.endpoint.rstrip('/')}/v1/chat/completions"
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "min_p": self.min_p,
            "repeat_penalty": self.repeat_penalty,
            "max_tokens": min(self.max_tokens, 512),
            "response_format": {"type": "json_object"},
            "enable_thinking": self.enable_thinking,
            "chat_template_kwargs": {"enable_thinking": self.enable_thinking},
        }
        body = self._adapt_body_for_server(body)
        
        if self.stream:
            def _do_http_stream():
                content = self._http_stream_completion(url, body, "hypothesis", messages)
                parsed = _parse_json_object(content)
                return parsed if parsed else default_response
            
            return retry_with_backoff(
                _do_http_stream,
                max_retries=self.max_retries,
                base_delay=self.retry_base_delay,
                exceptions=(httpx.HTTPError, httpx.TimeoutException, ConnectionError, OSError),
                on_failure=lambda e: default_response,
            )
        
        def _do_http():
            resp = httpx.post(url, json=body, timeout=self.timeout_s)
            resp.raise_for_status()
            data = resp.json()
            self.last_usage = data.get("usage") if isinstance(data, dict) else None
            try:
                content = data["choices"][0]["message"]["content"]
                parsed = _parse_json_object(content)
                return parsed if parsed else default_response
            except Exception:
                return default_response
        
        return retry_with_backoff(
            _do_http,
            max_retries=self.max_retries,
            base_delay=self.retry_base_delay,
            exceptions=(httpx.HTTPError, httpx.TimeoutException, ConnectionError, OSError),
            on_failure=lambda e: default_response,
        )

    def review_reason_candidates(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        reason 후보(점수/근거)를 LLM이 재검토해 최종 merged reason을 생성한다.

        Args:
            payload: {
                "discussion_type": str,
                "candidates": [{"id": int, "score": float, "sources": [str], "text": str}]
            }
        """
        import time as _time
        import json as _json
        import re as _re

        messages = [
            {"role": "system", "content": REASON_REVIEW_PROMPT},
            {"role": "user", "content": _json.dumps(payload, ensure_ascii=False)},
        ]
        self._dump_messages("reason_review", messages)
        _start = _time.time()

        def _parse_json_object(text: str) -> Optional[Dict[str, Any]]:
            if not isinstance(text, str):
                return None
            s = text.strip()
            s = _re.sub(r"<think>[\s\S]*?</think>", "", s, flags=_re.IGNORECASE).strip()
            fence_match = _re.search(r"```(?:json)?\s*([\s\S]*?)```", s, flags=_re.IGNORECASE)
            if fence_match:
                s = fence_match.group(1).strip()
            try:
                obj = _json.loads(s)
                return obj if isinstance(obj, dict) else None
            except Exception:
                pass
            m = _re.search(r"\{[\s\S]*\}", s)
            if not m:
                return None
            try:
                obj = _json.loads(m.group(0))
                return obj if isinstance(obj, dict) else None
            except Exception:
                return None

        default_response = {
            "selected_ids": [],
            "primary_reason": "",
            "merged_reason": "",
            "llm_review_note": "LLM reason review 실패",
            "review_confidence": "Low",
        }
        _reason_review_max_tokens = self._resolve_reason_review_max_tokens()

        if self.backend == "local":
            llm = self._get_local_llm()
            ts = self._timestamp()
            print(f"[{ts}][llm-stream] ▶ reason_review 생성 시작...", file=sys.stderr, flush=True)

            if self.think_stream and self.stream:
                chunks = llm.create_chat_completion(
                    messages=messages,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    min_p=self.min_p,
                    repeat_penalty=self.repeat_penalty,
                    max_tokens=_reason_review_max_tokens,
                    grammar=None,
                    stream=True,
                )
                acc: List[str] = []
                token_count = 0
                last_chunk = None
                for chunk in chunks:
                    last_chunk = chunk
                    try:
                        delta = chunk["choices"][0].get("delta", {})
                        piece = delta.get("content", "")
                    except Exception:
                        piece = ""
                    if piece:
                        acc.append(piece)
                        token_count += 1
                        print(piece, end="", file=sys.stderr, flush=True)

                _elapsed = _time.time() - _start
                ts = self._timestamp()
                print(f"\n[{ts}][llm-stream] ■ reason_review 완료 ({_elapsed:.2f}s)", file=sys.stderr, flush=True)

                usage = last_chunk.get("usage") if last_chunk and isinstance(last_chunk, dict) else None
                if self.print_timings:
                    print(f"[{ts}][llm-usage] ── reason_review ──", file=sys.stderr, flush=True)
                    if usage:
                        print(f"  prompt_tokens: {usage.get('prompt_tokens', 0)}", file=sys.stderr, flush=True)
                        print(
                            f"  completion_tokens: {usage.get('completion_tokens', token_count)}",
                            file=sys.stderr,
                            flush=True,
                        )
                        print(f"  total_tokens: {usage.get('total_tokens', 0)}", file=sys.stderr, flush=True)
                    else:
                        prompt_chars = sum(len(m.get("content", "")) for m in messages)
                        est_prompt_tokens = prompt_chars // 3
                        print(f"  prompt_tokens (추정): ~{est_prompt_tokens}", file=sys.stderr, flush=True)
                        print(f"  completion_tokens: {token_count}", file=sys.stderr, flush=True)
                        print(
                            f"  total_tokens (추정): ~{est_prompt_tokens + token_count}",
                            file=sys.stderr,
                            flush=True,
                        )
                    print(f"  elapsed: {_elapsed:.2f}s", file=sys.stderr, flush=True)
                    if _elapsed > 0:
                        print(f"  response_tok/s: {token_count / _elapsed:.2f}", file=sys.stderr, flush=True)

                parsed = _parse_json_object("".join(acc))
                return parsed if parsed else default_response

            data = llm.create_chat_completion(
                messages=messages,
                temperature=self.temperature,
                top_p=self.top_p,
                min_p=self.min_p,
                repeat_penalty=self.repeat_penalty,
                max_tokens=_reason_review_max_tokens,
                grammar=None if self.think_stream else self._get_json_object_grammar(),
            )
            _elapsed = _time.time() - _start
            ts = self._timestamp()
            print(f"[{ts}][llm-stream] ■ reason_review 완료 ({_elapsed:.2f}s)", file=sys.stderr, flush=True)
            self._print_usage_details("reason_review", data, _elapsed)
            try:
                content = data["choices"][0]["message"]["content"]
                parsed = _parse_json_object(content)
                return parsed if parsed else default_response
            except Exception:
                return default_response

        # HTTP backend
        url = f"{self.endpoint.rstrip('/')}/v1/chat/completions"
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "min_p": self.min_p,
            "repeat_penalty": self.repeat_penalty,
            "max_tokens": _reason_review_max_tokens,
            "response_format": {"type": "json_object"},
            "enable_thinking": self.enable_thinking,
            "chat_template_kwargs": {"enable_thinking": self.enable_thinking},
        }
        if self.server_type == "vllm":
            body["stream_options"] = {"include_usage": True}
        body = self._adapt_body_for_server(body)

        if self.stream:
            def _do_http_stream():
                content = self._http_stream_completion(url, body, "reason_review", messages)
                parsed = _parse_json_object(content)
                return parsed if parsed else default_response

            return retry_with_backoff(
                _do_http_stream,
                max_retries=self.max_retries,
                base_delay=self.retry_base_delay,
                exceptions=(httpx.HTTPError, httpx.TimeoutException, ConnectionError, OSError),
                on_failure=lambda e: default_response,
            )

        def _do_http():
            resp = httpx.post(url, json=body, timeout=self.timeout_s)
            resp.raise_for_status()
            data = resp.json()
            self.last_usage = data.get("usage") if isinstance(data, dict) else None
            self.last_model = data.get("model") if isinstance(data, dict) else None
            try:
                content = data["choices"][0]["message"]["content"]
                parsed = _parse_json_object(content)
                return parsed if parsed else default_response
            except Exception:
                return default_response

        return retry_with_backoff(
            _do_http,
            max_retries=self.max_retries,
            base_delay=self.retry_base_delay,
            exceptions=(httpx.HTTPError, httpx.TimeoutException, ConnectionError, OSError),
            on_failure=lambda e: default_response,
        )

    def analyze_metadata(self, payload: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        2단계: 작품(식별 결과 포함) 기반으로 담론 메타데이터(마이크로 태그/감성/드리프트/NSFW/세그먼트)를 추출.
        반환은 JSON object여야 한다.
        """
        import time as _time
        messages = [
            {"role": "system", "content": ANALYZE_PROMPT},
            {"role": "user", "content": __import__("json").dumps(payload, ensure_ascii=False)},
        ]
        self._dump_messages("analyze", messages)
        _start = _time.time()

        if self.backend == "local":
            llm = self._get_local_llm()
            ts = self._timestamp()
            print(f"[{ts}][llm-stream] ▶ analyze 생성 시작...", file=sys.stderr, flush=True)
            
            # think_stream 모드면 스트리밍으로 reasoning 출력
            if self.think_stream and self.stream:
                chunks = llm.create_chat_completion(
                    messages=messages,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    min_p=self.min_p,
                    repeat_penalty=self.repeat_penalty,
                    max_tokens=self.max_tokens,  # LLM_MAX_TOKENS 환경변수로 통일 관리
                    grammar=None,
                    stream=True,
                )
                acc: List[str] = []
                token_count = 0
                last_chunk = None
                for chunk in chunks:
                    last_chunk = chunk
                    try:
                        delta = chunk["choices"][0].get("delta", {})
                        piece = delta.get("content", "")
                    except Exception:
                        piece = ""
                    if piece:
                        acc.append(piece)
                        token_count += 1
                        print(piece, end="", file=sys.stderr, flush=True)
                
                _elapsed = _time.time() - _start
                ts = self._timestamp()
                print(f"\n[{ts}][llm-stream] ■ analyze 완료 ({_elapsed:.2f}s)", file=sys.stderr, flush=True)
                
                # usage 정보 출력
                usage = last_chunk.get("usage") if last_chunk and isinstance(last_chunk, dict) else None
                if self.print_timings:
                    print(f"[{ts}][llm-usage] ── analyze ──", file=sys.stderr, flush=True)
                    if usage:
                        print(f"  prompt_tokens: {usage.get('prompt_tokens', 0)}", file=sys.stderr, flush=True)
                        print(f"  completion_tokens: {usage.get('completion_tokens', token_count)}", file=sys.stderr, flush=True)
                        print(f"  total_tokens: {usage.get('total_tokens', 0)}", file=sys.stderr, flush=True)
                    else:
                        prompt_chars = sum(len(m.get("content", "")) for m in messages)
                        est_prompt_tokens = prompt_chars // 3
                        print(f"  prompt_tokens (추정): ~{est_prompt_tokens}", file=sys.stderr, flush=True)
                        print(f"  completion_tokens: {token_count}", file=sys.stderr, flush=True)
                        print(f"  total_tokens (추정): ~{est_prompt_tokens + token_count}", file=sys.stderr, flush=True)
                    print(f"  elapsed: {_elapsed:.2f}s", file=sys.stderr, flush=True)
                    if _elapsed > 0:
                        print(f"  response_tok/s: {token_count / _elapsed:.2f}", file=sys.stderr, flush=True)
                
                content = "".join(acc)
                # JSON 파싱 시도 (마크다운 펜스, think 블록 제거)
                try:
                    import re as _re
                    import json as _json
                    s = content.strip()
                    # 1) <think>...</think> 블록 제거 (있으면)
                    s = _re.sub(r"<think>[\s\S]*?</think>", "", s, flags=_re.IGNORECASE)
                    s = s.strip()
                    # 2) </think> 닫는 태그만 있는 경우도 제거 (간혹 열린 태그 없이 닫힘만 있음)
                    s = _re.sub(r"</think>", "", s, flags=_re.IGNORECASE)
                    s = s.strip()
                    # 3) markdown code fence에서 JSON 추출 (가장 마지막 fence 우선)
                    fence_matches = list(_re.finditer(r"```(?:json)?\s*([\s\S]*?)```", s, flags=_re.IGNORECASE))
                    if fence_matches:
                        # 마지막 코드 블록 사용 (reasoning 후 JSON 출력 패턴 대응)
                        s = fence_matches[-1].group(1).strip()
                    # 4) 직접 JSON 파싱 시도
                    try:
                        return _json.loads(s)
                    except Exception:
                        pass
                    # 5) 첫 번째 {...} 블록 추출 (non-greedy로 가장 바깥 객체 찾기)
                    brace_depth = 0
                    start_idx = -1
                    for i, c in enumerate(s):
                        if c == '{':
                            if brace_depth == 0:
                                start_idx = i
                            brace_depth += 1
                        elif c == '}':
                            brace_depth -= 1
                            if brace_depth == 0 and start_idx >= 0:
                                try:
                                    return _json.loads(s[start_idx:i+1])
                                except Exception:
                                    pass
                                start_idx = -1
                    return {}
                except Exception:
                    return {}
            
            # 비스트리밍 모드 (기존)
            data = llm.create_chat_completion(
                messages=messages,
                temperature=self.temperature,
                top_p=self.top_p,
                min_p=self.min_p,
                repeat_penalty=self.repeat_penalty,
                max_tokens=self.max_tokens,  # LLM_MAX_TOKENS 환경변수로 통일 관리
                grammar=None if self.think_stream else self._get_json_object_grammar(),
            )
            _elapsed = _time.time() - _start
            ts = self._timestamp()
            print(f"[{ts}][llm-stream] ■ analyze 완료 ({_elapsed:.2f}s)", file=sys.stderr, flush=True)
            self._print_usage_details("analyze", data, _elapsed)
            try:
                self.last_usage = data.get("usage") if isinstance(data, dict) else None
                self.last_model = data.get("model") if isinstance(data, dict) else None
                content = data["choices"][0]["message"]["content"]
                return __import__("json").loads(content)
            except Exception:
                return {}

        url = f"{self.endpoint.rstrip('/')}/v1/chat/completions"
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "min_p": self.min_p,
            "repeat_penalty": self.repeat_penalty,
            "max_tokens": max(128, min(self.max_tokens, 512)),
            "response_format": {"type": "json_object"},
            # llama-server에서 GLM 모델의 thinking 활성화
            "enable_thinking": self.enable_thinking,
            "chat_template_kwargs": {"enable_thinking": self.enable_thinking},
        }
        body = self._adapt_body_for_server(body)
        
        # 스트리밍 모드면 HTTP 스트리밍 사용
        if self.stream:
            def _do_http_stream():
                import json as _json
                import re as _re
                content = self._http_stream_completion(url, body, "analyze", messages)
                # JSON 파싱 (think 블록, markdown fence 제거)
                s = content.strip()
                s = _re.sub(r"<think>[\s\S]*?</think>", "", s, flags=_re.IGNORECASE)
                s = _re.sub(r"</think>", "", s, flags=_re.IGNORECASE)
                s = s.strip()
                fence_matches = list(_re.finditer(r"```(?:json)?\s*([\s\S]*?)```", s, flags=_re.IGNORECASE))
                if fence_matches:
                    s = fence_matches[-1].group(1).strip()
                try:
                    return _json.loads(s)
                except Exception:
                    pass
                # {...} 블록 추출
                brace_depth = 0
                start_idx = -1
                for i, c in enumerate(s):
                    if c == '{':
                        if brace_depth == 0:
                            start_idx = i
                        brace_depth += 1
                    elif c == '}':
                        brace_depth -= 1
                        if brace_depth == 0 and start_idx >= 0:
                            try:
                                return _json.loads(s[start_idx:i+1])
                            except Exception:
                                pass
                            start_idx = -1
                return {}
            
            return retry_with_backoff(
                _do_http_stream,
                max_retries=self.max_retries,
                base_delay=self.retry_base_delay,
                exceptions=(httpx.HTTPError, httpx.TimeoutException, ConnectionError, OSError),
                on_failure=lambda e: {},
            )
        
        def _do_http():
            resp = httpx.post(url, json=body, timeout=self.timeout_s)
            resp.raise_for_status()
            data = resp.json()
            self.last_usage = data.get("usage") if isinstance(data, dict) else None
            self.last_model = data.get("model") if isinstance(data, dict) else None
            try:
                content = data["choices"][0]["message"]["content"]
                return __import__("json").loads(content)
            except Exception:
                return {}
        
        return retry_with_backoff(
            _do_http,
            max_retries=self.max_retries,
            base_delay=self.retry_base_delay,
            exceptions=(httpx.HTTPError, httpx.TimeoutException, ConnectionError, OSError),
            on_failure=lambda e: {},
        )

    def _enrich_local(self, payload: List[Dict[str, Any]]) -> Dict[str, Any]:
        llm = self._get_local_llm()

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": __import__("json").dumps(payload, ensure_ascii=False)},
        ]
        self._dump_messages("enrich", messages)

        # llama-cpp-python의 create_chat_completion은 OpenAI 호환 형태를 반환함
        data = llm.create_chat_completion(
            messages=messages,
            temperature=self.temperature,
            top_p=self.top_p,
            min_p=self.min_p,
            repeat_penalty=self.repeat_penalty,
            max_tokens=self.max_tokens,
            grammar=None if self.think_stream else self._get_json_array_grammar(),
        )
        if self.print_timings:
            try:
                llm.print_timings()
                llm.reset_timings()
            except Exception:
                pass
        return data

    def enrich_text(self, payload: List[Dict[str, Any]]) -> str:
        if self.backend == "local" and self.stream:
            self.last_usage = None
            self.last_model = None
            
            def _do_stream():
                return self._enrich_text_local_stream(payload)
            
            return retry_with_backoff(
                _do_stream,
                max_retries=self.max_retries,
                base_delay=self.retry_base_delay,
                exceptions=(Exception,),
                on_failure=lambda e: "[]",  # 빈 JSON 배열 반환
            )
        
        # HTTP 백엔드에서도 스트리밍 지원
        if self.backend == "http" and self.stream:
            self.last_usage = None
            self.last_model = None
            url = f"{self.endpoint.rstrip('/')}/v1/chat/completions"
            body = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": __import__("json").dumps(payload, ensure_ascii=False)},
                ],
                "temperature": self.temperature,
                "top_p": self.top_p,
                "min_p": self.min_p,
                "repeat_penalty": self.repeat_penalty,
                "max_tokens": self.max_tokens,
                # llama-server에서 GLM 모델의 thinking 활성화
                "enable_thinking": self.enable_thinking,
                "chat_template_kwargs": {"enable_thinking": self.enable_thinking},
            }
            body = self._adapt_body_for_server(body)
            self._dump_messages("enrich_http_stream", body["messages"])
            
            def _do_http_stream():
                return self._http_stream_completion(url, body, "enrich", messages)
            
            return retry_with_backoff(
                _do_http_stream,
                max_retries=self.max_retries,
                base_delay=self.retry_base_delay,
                exceptions=(httpx.HTTPError, httpx.TimeoutException, ConnectionError, OSError),
                on_failure=lambda e: "[]",
            )

        data = self.enrich(payload)
        try:
            return data["choices"][0]["message"]["content"]
        except Exception:
            return str(data)

    def _enrich_text_local_stream(self, payload: List[Dict[str, Any]]) -> str:
        import time as _time
        llm = self._get_local_llm()
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": __import__("json").dumps(payload, ensure_ascii=False)},
        ]
        self._dump_messages("enrich_stream", messages)
        _start = _time.time()

        chunks = llm.create_chat_completion(
            messages=messages,
            temperature=self.temperature,
            top_p=self.top_p,
            min_p=self.min_p,
            repeat_penalty=self.repeat_penalty,
            max_tokens=self.max_tokens,
            grammar=None if self.think_stream else self._get_json_array_grammar(),
            stream=True,
        )

        acc: List[str] = []
        token_count = 0
        last_chunk = None  # 마지막 청크에서 usage 정보 추출용
        ts = self._timestamp()
        print(f"[{ts}][llm-stream] ▶ enrich 토큰 생성 시작...", file=sys.stderr, flush=True)
        for chunk in chunks:
            last_chunk = chunk  # 마지막 청크 저장
            try:
                delta = chunk["choices"][0].get("delta", {})
                piece = delta.get("content", "")
            except Exception:
                piece = ""
            if piece:
                acc.append(piece)
                token_count += 1
                # 진행 상황: 생성되는 텍스트를 stderr로 실시간 출력
                print(piece, end="", file=sys.stderr, flush=True)

        _elapsed = _time.time() - _start
        # stderr 줄 정리 및 토큰 사용량 표시
        ts = self._timestamp()
        if acc:
            print(f"\n[{ts}][llm-stream] ■ enrich 완료 ({_elapsed:.2f}s)", file=sys.stderr, flush=True)

        # 스트리밍 마지막 청크에서 usage 정보 추출 시도
        usage = None
        if last_chunk and isinstance(last_chunk, dict):
            usage = last_chunk.get("usage")
        
        if self.print_timings:
            print(f"[{ts}][llm-usage] ── enrich_stream ──", file=sys.stderr, flush=True)
            if usage:
                # 정확한 usage 정보 사용
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", token_count)
                total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
                print(f"  prompt_tokens: {prompt_tokens}", file=sys.stderr, flush=True)
                print(f"  completion_tokens: {completion_tokens}", file=sys.stderr, flush=True)
                print(f"  total_tokens: {total_tokens}", file=sys.stderr, flush=True)
            else:
                # 폴백: 추정값 사용
                prompt_chars = sum(len(m.get("content", "")) for m in messages)
                est_prompt_tokens = prompt_chars // 3
                print(f"  prompt_tokens (추정): ~{est_prompt_tokens}", file=sys.stderr, flush=True)
                print(f"  completion_tokens: {token_count}", file=sys.stderr, flush=True)
                print(f"  total_tokens (추정): ~{est_prompt_tokens + token_count}", file=sys.stderr, flush=True)
            print(f"  elapsed: {_elapsed:.2f}s", file=sys.stderr, flush=True)
            if _elapsed > 0:
                print(f"  response_tok/s: {token_count / _elapsed:.2f}", file=sys.stderr, flush=True)
            try:
                llm.print_timings()
                llm.reset_timings()
            except Exception:
                pass

        return "".join(acc)
