# -*- coding: utf-8 -*-
"""
Expert 공통 유틸리티
"""

from __future__ import annotations

import json
import re
import sys
import threading
from datetime import datetime
from typing import Any, Dict

# ─── 스레드 안전 타임스탬프 (워커 ID 포함) ───────────────
_ts_thread_local = threading.local()

def _ts() -> str:
    """병렬 모드에서 워커 ID를 포함하는 타임스탬프"""
    wid = getattr(_ts_thread_local, 'worker_id', None)
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    if wid is not None and getattr(_ts_thread_local, 'parallel', 1) > 1:
        return f"{ts}|W{wid}"
    return ts

def set_worker_context(worker_id: int, parallel_count: int = 1) -> None:
    """현재 스레드에 워커 컨텍스트 설정 (파이프라인에서 호출)"""
    _ts_thread_local.worker_id = worker_id
    _ts_thread_local.parallel = parallel_count


# 배열 반복 루프 방어: 필드별 최대 허용 길이
_ARRAY_MAX_LENGTHS: Dict[str, int] = {
    "morphemes": 10,
    "micro_tags": 15,
    "detected_titles": 10,
    "counter_arguments": 10,
    "evidence_chain": 10,
    "domain_evidence": 10,
    "secondary_domains": 10,
    "key_terms": 15,
    "search_requests": 10,
    # 🆕 Decoder 배열 제한 (반복 루프 방어)
    "decoded_terms": 10,
    "candidates": 5,
    "unresolved_terms": 5,
    "self_questions": 5,
    "verification_search": 5,
    "search_suggestions": 5,
}
# 위에 없는 배열 필드의 기본 최대 길이
_DEFAULT_ARRAY_MAX = 15


def _extract_first_complete_json(text: str) -> str | None:
    """
    텍스트에서 첫 번째 완전한 JSON 객체를 브라켓 카운팅으로 추출합니다.
    
    LLM이 같은 JSON을 여러 번 반복 출력하는 경우, rfind("}")로는 불완전한
    마지막 복사본의 }를 잡게 됩니다. 이 함수는 첫 번째 완전한 {} 쌍을 추출합니다.
    
    Returns:
        첫 번째 완전한 JSON 문자열, 또는 None (완전한 객체 없음)
    """
    start = text.find("{")
    if start < 0:
        return None
    
    depth = 0
    in_string = False
    escape_next = False
    
    for i in range(start, len(text)):
        c = text[i]
        
        if escape_next:
            escape_next = False
            continue
        
        if c == '\\' and in_string:
            escape_next = True
            continue
        
        if c == '"' and not escape_next:
            in_string = not in_string
            continue
        
        if in_string:
            continue
        
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                candidate = text[start:i + 1]
                # 추출한 블록 뒤에 또 다른 JSON이 시작되면 반복 출력임
                remaining = text[i + 1:].lstrip()
                if remaining.startswith("{"):
                    print(
                        f"[utils] ⚠️ JSON 반복 출력 감지: 첫 번째 완전 객체 추출 "
                        f"({len(candidate)}자, 잔여 {len(remaining)}자 무시)",
                        file=sys.stderr,
                    )
                return candidate
    
    return None  # 완전한 객체 없음 (열린 괄호 미닫힘)


def _try_repair_json(broken: str) -> Dict[str, Any]:
    """
    불완전한 JSON 문자열 복구를 시도합니다.
    반복 루프 조기 종료로 JSON이 잘린 경우, 마지막 완전한 키-값 쌍까지 복구합니다.
    """
    # 전략: 뒤에서부터 잘라가며 닫는 괄호를 보충하여 파싱 시도
    # 마지막 완전한 값 경계를 찾음
    for trim_pos in range(len(broken), max(0, len(broken) - 2000), -1):
        snippet = broken[:trim_pos].rstrip().rstrip(",")
        # 열린 괄호/대괄호 수 계산
        opens_brace = snippet.count("{") - snippet.count("}")
        opens_bracket = snippet.count("[") - snippet.count("]")
        # 문자열 내부가 아닌지 간단히 확인
        closing = "]" * max(0, opens_bracket) + "}" * max(0, opens_brace)
        candidate = snippet + closing
        try:
            result = json.loads(candidate)
            if isinstance(result, dict):
                print(
                    f"[utils] ⚠️ 불완전 JSON 복구 성공 (원본 {len(broken)}자 → {trim_pos}자에서 절단)",
                    file=sys.stderr,
                )
                return result
        except json.JSONDecodeError:
            continue
    raise ValueError(f"JSON 복구 실패: {broken[:200]}")


def _sanitize_arrays(obj: Any, path: str = "") -> Any:
    """재귀적으로 JSON 객체 내 모든 배열의 반복 루프를 감지·절삭하고 중복을 제거합니다."""
    if isinstance(obj, dict):
        return {k: _sanitize_arrays(v, f"{path}.{k}") for k, v in obj.items()}
    elif isinstance(obj, list):
        field_name = path.rsplit(".", 1)[-1] if path else ""
        max_len = _ARRAY_MAX_LENGTHS.get(field_name, _DEFAULT_ARRAY_MAX)
        
        # (0) 빈 문자열 / 공백만 있는 문자열 제거
        if obj and all(isinstance(x, str) for x in obj):
            cleaned = [x for x in obj if x.strip()]
            if len(cleaned) < len(obj):
                obj = cleaned
        
        # (1) 중복 제거: 문자열 배열에서 동일 값 3회 이상 등장 시 1개로 축소
        if obj and all(isinstance(x, str) for x in obj):
            from collections import Counter
            counts = Counter(obj)
            dedup_targets = {v for v, c in counts.items() if c >= 3}
            if dedup_targets:
                seen_dedup = set()
                deduped = []
                for item in obj:
                    if item in dedup_targets:
                        if item not in seen_dedup:
                            seen_dedup.add(item)
                            deduped.append(item)
                        # 이미 본 중복 항목은 건너뜀
                    else:
                        deduped.append(item)
                if len(deduped) < len(obj):
                    print(
                        f"[utils] ⚠️ 배열 중복 제거: {path} ({len(obj)}개 → {len(deduped)}개)",
                        file=sys.stderr,
                    )
                    obj = deduped
        
        # (2) 길이 절삭
        if len(obj) > max_len:
            print(
                f"[utils] ⚠️ 배열 반복 루프 감지: {path} ({len(obj)}개 → {max_len}개 절삭)",
                file=sys.stderr,
            )
            obj = obj[:max_len]
        return [_sanitize_arrays(item, f"{path}[]") for item in obj]
    return obj


def parse_json_with_think_removal(text: str) -> Dict[str, Any]:
    """
    LLM 응답에서 <think> 블록을 제거하고 JSON을 파싱합니다.
    
    GLM-4 등 reasoning 모델은 <think>...</think> 블록을 먼저 출력하고
    그 뒤에 JSON을 출력합니다. 이 함수는 think 블록을 제거하고 JSON만 추출합니다.
    
    또한 JSON 내부에 "thinking" 필드가 있으면 제거합니다.
    """
    text = text.strip()
    
    # 1. <think>...</think> 블록 제거 (여러 개 있을 수 있음)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = text.strip()
    
    # 2. Markdown fence 제거
    if text.startswith("```"):
        lines = text.split("\n")
        # ```json 또는 ``` 제거
        if lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    
    # 3. JSON 객체 추출 — 반복 출력 방어: 첫 번째 완전한 JSON 우선 추출
    first_obj = _extract_first_complete_json(text)
    if first_obj:
        try:
            result = json.loads(first_obj)
            if isinstance(result, dict):
                # 4. "thinking" 관련 필드 제거
                forbidden_keys = {"thinking", "thought", "reasoning_process", "internal_reasoning"}
                for key in list(result.keys()):
                    if key.lower() in forbidden_keys or key.lower().startswith("think"):
                        del result[key]
                # 5. 배열 반복 루프 방어
                result = _sanitize_arrays(result)
                return result
        except json.JSONDecodeError:
            pass  # fall through to legacy rfind approach

    # 3-b. fallback: rfind 기반 추출 (반복 없는 일반 케이스)
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        json_str = text[start:end]
        try:
            result = json.loads(json_str)
        except json.JSONDecodeError:
            # 불완전 JSON 복구 시도 (반복 루프 조기 종료로 잘린 경우)
            result = _try_repair_json(json_str)
        
        # 4. "thinking" 관련 필드 제거
        forbidden_keys = {"thinking", "thought", "reasoning_process", "internal_reasoning"}
        for key in list(result.keys()):
            if key.lower() in forbidden_keys or key.lower().startswith("think"):
                del result[key]
        
        # 5. 배열 반복 루프 방어 (모든 Expert 공통)
        result = _sanitize_arrays(result)
        
        return result
    
    # `{` 는 있지만 `}` 가 없는 경우 (완전히 잘린 JSON)
    if start >= 0:
        json_str = text[start:]
        try:
            result = _try_repair_json(json_str)
            forbidden_keys = {"thinking", "thought", "reasoning_process", "internal_reasoning"}
            for key in list(result.keys()):
                if key.lower() in forbidden_keys or key.lower().startswith("think"):
                    del result[key]
            result = _sanitize_arrays(result)
            return result
        except (ValueError, json.JSONDecodeError):
            pass
    
    raise ValueError(f"No valid JSON found in response: {text[:200]}")
