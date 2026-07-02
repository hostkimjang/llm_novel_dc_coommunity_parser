# -*- coding: utf-8 -*-
"""
Expert 공통 유틸리티
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

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

_HAN_CHAR_RE = re.compile(r"[\u4E00-\u9FFF]")
_WS_MULTI_RE = re.compile(r"\s{2,}")


def _sanitize_non_korean_text(
    obj: Any,
    path: str = "",
) -> tuple[Any, int]:
    """
    LLM 출력 문자열에 중국어 한자/중문장이 섞이는 경우를 완화한다.
    - URL 필드는 원문 유지
    - 한자 포함 문자열은 한자 제거 후 공백 정리
    - 제거 후 빈 문자열이면 안전한 한국어 대체문으로 치환
    """
    if isinstance(obj, dict):
        changed_total = 0
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            child, changed = _sanitize_non_korean_text(v, f"{path}.{k}" if path else str(k))
            out[k] = child
            changed_total += changed
        return out, changed_total

    if isinstance(obj, list):
        changed_total = 0
        out_list: List[Any] = []
        for i, v in enumerate(obj):
            child, changed = _sanitize_non_korean_text(v, f"{path}[{i}]")
            out_list.append(child)
            changed_total += changed
        return out_list, changed_total

    if not isinstance(obj, str):
        return obj, 0

    text = obj
    if not text:
        return text, 0

    key = path.rsplit(".", 1)[-1].lower() if path else ""
    if key in {"url", "heretic_url", "wiki_url"}:
        return text, 0
    if text.startswith("http://") or text.startswith("https://"):
        return text, 0
    if not _HAN_CHAR_RE.search(text):
        return text, 0

    cleaned = _HAN_CHAR_RE.sub("", text)
    cleaned = _WS_MULTI_RE.sub(" ", cleaned).strip()
    if not cleaned:
        cleaned = "비한국어 원문 생략"

    if cleaned == text:
        return text, 0
    return cleaned, 1


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


_MALFORMED_STRING_SUFFIX_RE = re.compile(
    r'(:\s*)"((?:[^"\\]|\\.)*)"\s*([^,\}\]\n][^,\}\]\n]*?)\s*([,\}\]])'
)


def _merge_malformed_string_suffixes(text: str) -> tuple[str, bool]:
    """
    LLM이 문자열 값 뒤에 조사/설명 텍스트를 따옴표 밖에 붙이는 케이스를 보정한다.

    예:
      "value": "즉사기 들고 무림에 떨어지다"의 커뮤니티 약칭,
    =>
      "value": "즉사기 들고 무림에 떨어지다의 커뮤니티 약칭",
    """
    changed = False

    def _repl(match: re.Match[str]) -> str:
        nonlocal changed
        prefix = match.group(1)
        base_raw = match.group(2)
        suffix_raw = match.group(3)
        delimiter = match.group(4)

        suffix = suffix_raw.strip()
        if not suffix:
            return match.group(0)

        try:
            base = json.loads(f"\"{base_raw}\"")
        except Exception:
            base = base_raw

        merged = f"{base}{suffix}"
        changed = True
        return f"{prefix}{json.dumps(merged, ensure_ascii=False)}{delimiter}"

    repaired = _MALFORMED_STRING_SUFFIX_RE.sub(_repl, text)
    return repaired, changed


def _escape_control_chars_in_json_strings(text: str) -> tuple[str, bool]:
    """JSON 문자열 내부의 비이스케이프 제어문자를 안전하게 치환한다."""
    if not text:
        return text, False

    out: List[str] = []
    in_string = False
    escape_next = False
    changed = False

    for ch in text:
        if escape_next:
            out.append(ch)
            escape_next = False
            continue

        if ch == "\\" and in_string:
            out.append(ch)
            escape_next = True
            continue

        if ch == '"':
            out.append(ch)
            in_string = not in_string
            continue

        if in_string:
            code = ord(ch)
            if ch == "\n":
                out.append("\\n")
                changed = True
                continue
            if ch == "\r":
                out.append("\\r")
                changed = True
                continue
            if ch == "\t":
                out.append("\\t")
                changed = True
                continue
            if code < 0x20:
                out.append(f"\\u{code:04x}")
                changed = True
                continue

        out.append(ch)

    return "".join(out), changed


def _try_repair_json(broken: str) -> Dict[str, Any]:
    """
    불완전한 JSON 문자열 복구를 시도합니다.
    반복 루프 조기 종료로 JSON이 잘린 경우, 마지막 완전한 키-값 쌍까지 복구합니다.
    """
    # 흔한 케이스: 문자열 값 뒤 조사/설명이 따옴표 밖으로 나온 경우
    broken, suffix_fixed = _merge_malformed_string_suffixes(broken)
    if suffix_fixed:
        print(
            f"[utils] ⚠️ 문자열 suffix JSON 보정 적용 ({len(broken)}자)",
            file=sys.stderr,
        )
    broken, control_fixed = _escape_control_chars_in_json_strings(broken)
    if control_fixed:
        print(
            f"[utils] ⚠️ JSON 문자열 내부 제어문자 보정 적용 ({len(broken)}자)",
            file=sys.stderr,
        )

    # 전략: 뒤에서부터 잘라가며 닫는 괄호를 보충하여 파싱 시도
    # 마지막 완전한 값 경계를 찾음
    try:
        _repair_window = int(os.getenv("LLM_JSON_REPAIR_WINDOW", "6000"))
    except Exception:
        _repair_window = 6000
    _repair_window = max(1000, min(_repair_window, 20000))
    for trim_pos in range(len(broken), max(0, len(broken) - _repair_window), -1):
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
    sanitize_non_ko = os.getenv("LLM_SANITIZE_NON_KO_TEXT", "1").strip().lower() in {"1", "true", "yes", "on"}
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
                if sanitize_non_ko:
                    result, changed = _sanitize_non_korean_text(result)
                    if changed > 0:
                        print(f"[utils] ⚠️ 비한국어(중문) 문자열 정리: {changed}건", file=sys.stderr)
                return result
        except json.JSONDecodeError:
            repaired_first_obj, fixed = _merge_malformed_string_suffixes(first_obj)
            if fixed:
                try:
                    result = json.loads(repaired_first_obj)
                    if isinstance(result, dict):
                        forbidden_keys = {"thinking", "thought", "reasoning_process", "internal_reasoning"}
                        for key in list(result.keys()):
                            if key.lower() in forbidden_keys or key.lower().startswith("think"):
                                del result[key]
                        result = _sanitize_arrays(result)
                        if sanitize_non_ko:
                            result, changed = _sanitize_non_korean_text(result)
                            if changed > 0:
                                print(f"[utils] ⚠️ 비한국어(중문) 문자열 정리: {changed}건", file=sys.stderr)
                        print(
                            "[utils] ⚠️ malformed string suffix 보정으로 JSON 파싱 성공",
                            file=sys.stderr,
                        )
                        return result
                except json.JSONDecodeError:
                    pass
            repaired_first_obj, control_fixed = _escape_control_chars_in_json_strings(
                repaired_first_obj if fixed else first_obj
            )
            if control_fixed:
                try:
                    result = json.loads(repaired_first_obj)
                    if isinstance(result, dict):
                        forbidden_keys = {"thinking", "thought", "reasoning_process", "internal_reasoning"}
                        for key in list(result.keys()):
                            if key.lower() in forbidden_keys or key.lower().startswith("think"):
                                del result[key]
                        result = _sanitize_arrays(result)
                        if sanitize_non_ko:
                            result, changed = _sanitize_non_korean_text(result)
                            if changed > 0:
                                print(f"[utils] ⚠️ 비한국어(중문) 문자열 정리: {changed}건", file=sys.stderr)
                        print(
                            "[utils] ⚠️ control-char 보정으로 JSON 파싱 성공",
                            file=sys.stderr,
                        )
                        return result
                except json.JSONDecodeError:
                    pass
            # fall through to legacy rfind approach

    # 3-b. fallback: rfind 기반 추출 (반복 없는 일반 케이스)
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        json_str = text[start:end]
        json_str, suffix_fixed = _merge_malformed_string_suffixes(json_str)
        if suffix_fixed:
            print(
                "[utils] ⚠️ malformed string suffix 보정 적용 (fallback 경로)",
                file=sys.stderr,
            )
        json_str, control_fixed = _escape_control_chars_in_json_strings(json_str)
        if control_fixed:
            print(
                "[utils] ⚠️ JSON 문자열 내부 제어문자 보정 적용 (fallback 경로)",
                file=sys.stderr,
            )
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
        if sanitize_non_ko:
            result, changed = _sanitize_non_korean_text(result)
            if changed > 0:
                print(f"[utils] ⚠️ 비한국어(중문) 문자열 정리: {changed}건", file=sys.stderr)
        
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
            if sanitize_non_ko:
                result, changed = _sanitize_non_korean_text(result)
                if changed > 0:
                    print(f"[utils] ⚠️ 비한국어(중문) 문자열 정리: {changed}건", file=sys.stderr)
            return result
        except (ValueError, json.JSONDecodeError):
            pass
    
    raise ValueError(f"No valid JSON found in response: {text[:200]}")


def _safe_int(val: Any, default: int = 0) -> int:
    try:
        return int(val)
    except Exception:
        return default


def _top_domains_from_results(
    results: List[Dict[str, Any]],
    max_domains: int = 5,
) -> List[tuple[str, int]]:
    """검색 결과에서 도메인 빈도 상위 N개를 반환."""
    if not results:
        return []
    counts: Dict[str, int] = {}
    for sr in results:
        if not isinstance(sr, dict):
            continue
        url = str(sr.get("url") or "").strip()
        if not url:
            continue
        try:
            from urllib.parse import urlparse
            host = (urlparse(url).netloc or "").lower().replace("www.", "")
        except Exception:
            host = ""
        if not host:
            continue
        counts[host] = counts.get(host, 0) + 1
    if not counts:
        return []
    return sorted(counts.items(), key=lambda x: x[1], reverse=True)[:max_domains]


def build_search_aggregation_summary(
    ctx: Any,
    *,
    results: Optional[List[Dict[str, Any]]] = None,
    extra_results: Optional[List[Dict[str, Any]]] = None,
    max_domains: int = 5,
    max_purposes: int = 5,
    max_queries: int = 8,
) -> str:
    """
    LLM 프롬프트에 주입할 검색 집계 요약 블록을 생성한다.
    - 코드 레벨 집계(search_query_stats) + 결과 분포(도메인) + 실행 쿼리 샘플을 압축 제공
    """
    if ctx is None:
        return ""

    stats = getattr(ctx, "search_query_stats", None) or {}
    if not isinstance(stats, dict):
        stats = {}

    total_q = _safe_int(stats.get("total"))
    zero_q = _safe_int(stats.get("zero_result"))
    nonzero_q = _safe_int(stats.get("nonzero_result"))

    effective_total_q = _safe_int(stats.get("effective_total"))
    effective_zero_q = _safe_int(stats.get("effective_zero"))
    effective_nonzero_q = _safe_int(stats.get("effective_nonzero"))

    degraded_q = _safe_int(stats.get("degraded_total"))
    degraded_zero_q = _safe_int(stats.get("degraded_zero"))
    retried_q = _safe_int(stats.get("retried_total"))
    retry_attempts_q = _safe_int(stats.get("retry_attempts_total"))
    cache_hits_q = _safe_int(stats.get("cache_hit_total"))

    raw_total = _safe_int(stats.get("raw_total"))
    accepted_total = _safe_int(stats.get("accepted_total"))
    filtered_total = _safe_int(stats.get("filtered_total"))
    duplicate_total = _safe_int(stats.get("duplicate_total"))
    self_ref_total = _safe_int(stats.get("self_ref_total"))

    effective_mode = effective_total_q > 0

    # 검색 결과 결합(필요 시 외부 verification_search 포함)
    base_results: List[Dict[str, Any]] = []
    if isinstance(results, list):
        base_results.extend([r for r in results if isinstance(r, dict)])
    else:
        base_results.extend([r for r in (getattr(ctx, "search_results", None) or []) if isinstance(r, dict)])
    if isinstance(extra_results, list):
        base_results.extend([r for r in extra_results if isinstance(r, dict)])

    total_results = len(base_results)
    top_domains = _top_domains_from_results(base_results, max_domains=max_domains)

    executed_queries = list(getattr(ctx, "executed_queries", None) or [])
    if not executed_queries:
        executed_queries = sorted(getattr(ctx, "searched_queries", None) or [])
    recent_queries = [str(q).strip() for q in executed_queries[-max_queries:] if str(q).strip()]

    by_purpose = stats.get("by_purpose")
    purpose_parts: List[str] = []
    if isinstance(by_purpose, dict) and by_purpose:
        items = []
        for purpose, ps in by_purpose.items():
            if not isinstance(ps, dict):
                continue
            t = _safe_int(ps.get("total"))
            nz = _safe_int(ps.get("nonzero"))
            items.append((str(purpose), t, nz))
        items.sort(key=lambda x: x[1], reverse=True)
        for purpose, total, nonzero in items[:max_purposes]:
            purpose_parts.append(f"{purpose}={total}/{nonzero}")

    # 아무 정보도 없으면 섹션 생략
    if (
        total_q <= 0
        and total_results <= 0
        and raw_total <= 0
        and accepted_total <= 0
        and not recent_queries
    ):
        return ""

    lines: List[str] = []
    lines.append("\n\n=== SEARCH AGGREGATION SUMMARY (코드 집계) ===")
    lines.append(
        f"- query_counts: total={total_q}, nonzero={nonzero_q}, zero={zero_q}"
    )
    if effective_mode:
        lines.append(
            f"- effective_counts: total={effective_total_q}, nonzero={effective_nonzero_q}, "
            f"zero={effective_zero_q} (degraded_zero 제외)"
        )
    lines.append(
        f"- infra: degraded={degraded_q} (zero={degraded_zero_q}), retried={retried_q}, "
        f"retry_attempts={retry_attempts_q}, cache_hits={cache_hits_q}"
    )
    lines.append(
        f"- result_quality: raw={raw_total}, accepted={accepted_total}, filtered={filtered_total}, "
        f"duplicate={duplicate_total}, self_ref={self_ref_total}, accumulated={total_results}"
    )
    if purpose_parts:
        lines.append(f"- top_purposes: {', '.join(purpose_parts)}")
    if top_domains:
        dom_text = ", ".join(f"{d}({c})" for d, c in top_domains)
        lines.append(f"- top_domains: {dom_text}")
    if recent_queries:
        # 쿼리 한 줄 길이 과도 증가 방지
        q_text = " | ".join(recent_queries)
        if len(q_text) > 360:
            q_text = q_text[:360] + "..."
        lines.append(f"- recent_queries: {q_text}")
    lines.append(
        "- rules: raw_zero만으로 비관련 결론을 내리지 말고, "
        "effective_nonzero/infra(degraded, retries)와 본문 앵커를 함께 판단하세요."
    )
    return "\n".join(lines)


# ============================================================
# 도메인 충돌 감지 유틸 (B1 통합: decoder/arbiter/agentic_pipeline 공유)
# ============================================================

_DOMAIN_SIGNAL_GROUPS: Dict[str, tuple] = {
    "martial": (
        "무림", "강호", "협객", "협녀", "협", "수선", "선협",
        "내공", "검무", "사파", "문파",
    ),
    "game": (
        "게임", "퀘스트", "튜토리얼", "레벨", "스킬", "랭킹",
        "길드", "로그인", "파밍", "npc",
    ),
}

_DOMAIN_CONFLICT_RULES: tuple = (
    ("martial", "game"),
    ("game", "martial"),
)


def _norm_domain_text(text: str) -> str:
    """도메인 비교용 정규화: 한글+영숫자만 남기고 소문자화."""
    return re.sub(r"[^\uac00-\ud7a3A-Za-z0-9]", "", str(text or "")).lower()


def _detect_domain_groups(text: str) -> set:
    """텍스트에서 감지된 도메인 그룹 집합 반환."""
    norm = _norm_domain_text(text)
    if not norm:
        return set()
    groups: set = set()
    for group, signals in _DOMAIN_SIGNAL_GROUPS.items():
        if any(sig in norm for sig in signals):
            groups.add(group)
    return groups


def _has_domain_conflict_for_mapping(source_term: str, candidate_title: str) -> bool:
    """
    source_term과 candidate_title 간 세계관 도메인 충돌 판정.
    source가 도메인 A이고 candidate가 충돌 도메인 B에만 속하면 True.
    """
    src_groups = _detect_domain_groups(source_term)
    cand_groups = _detect_domain_groups(candidate_title)
    if not src_groups or not cand_groups:
        return False
    for src_group, cand_group in _DOMAIN_CONFLICT_RULES:
        if src_group in src_groups and cand_group in cand_groups and src_group not in cand_groups:
            return True
    return False


# ============================================================
# 알려진 제목 약어 (B1 통합: arbiter/agentic_pipeline 공유)
# ============================================================

KNOWN_TITLE_ABBREVIATIONS: Dict[str, str] = {
    # === 아카데미 생존 갤러리 ===
    "아생갤": "아카데미 생존 갤러리",
    "아카생존": "아카데미 생존 갤러리",
    "아카생갤": "아카데미 생존 갤러리",
    # === source-native strong aliases ===
    "댓천마": "댓글창의 천재 마법사",
    "전1시": "전지적 1인칭 시점",
    "탐재": "탐식의 재림",
    # === 엑스칼리버 뽑습니다 ===
    "엑칼뽑": "엑스칼리버 뽑습니다",
    # === 괴담/호러 ===
    "괴담텔": "괴담 호텔 탈출기",
    "니생들": "니들 생각 다 들린다",
    "괴라리": "괴담에 휘말렸다",
    "담텔기": "괴담 호텔 탈출기",
}


# ============================================================
# Kiwi 형태소 분석기 프로세스 전역 싱글톤 (B2)
# ============================================================

_kiwi_instance: Any = None
_kiwi_lock = threading.Lock()


def get_kiwi():
    """프로세스 전역 Kiwi 형태소 분석기 싱글톤 (lazy loading, thread-safe)."""
    global _kiwi_instance
    if _kiwi_instance is None:
        with _kiwi_lock:
            if _kiwi_instance is None:
                try:
                    from kiwipiepy import Kiwi
                    _kiwi_instance = Kiwi()
                except ImportError:
                    print("[warn] kiwipiepy not installed, using fallback", file=sys.stderr)
                    _kiwi_instance = False  # 설치 안됨 표시
    return _kiwi_instance if _kiwi_instance else None
