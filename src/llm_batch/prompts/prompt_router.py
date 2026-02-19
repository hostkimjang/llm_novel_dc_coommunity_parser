"""Dynamic system prompt overlays for expert routing.

This module keeps the existing large expert prompts intact and appends
small, context-aware overlays to improve robustness on Korean community text.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


_NOVEL_DOMAINS = {"novel_literature", "novel_work"}


def _safe_str(value: Any) -> str:
    return str(value or "")


def _norm(value: Any) -> str:
    return " ".join(_safe_str(value).strip().split()).lower()


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    if not text:
        return False
    return any(k in text for k in keywords)


def _join_text_blocks(post: Optional[Dict[str, Any]]) -> str:
    if not isinstance(post, dict):
        return ""
    parts: List[str] = []
    for block in post.get("content_blocks", []) or []:
        if isinstance(block, dict):
            t = block.get("text")
            if t:
                parts.append(_safe_str(t))
        elif isinstance(block, str):
            parts.append(block)
    return " ".join(parts)


def _build_time_attack_overlay(ctx: Optional[Any]) -> List[str]:
    if ctx is None:
        return []

    urgency = ""
    remaining_steps: Optional[int] = None

    get_time_status = getattr(ctx, "get_time_status", None)
    if callable(get_time_status):
        try:
            status = get_time_status() or {}
            urgency = _safe_str(status.get("urgency", "")).upper()
            rs = status.get("remaining_steps")
            if isinstance(rs, int):
                remaining_steps = rs
        except Exception:
            urgency = ""

    if not urgency:
        try:
            current = int(getattr(ctx, "iteration", 0))
            maximum = int(getattr(ctx, "max_iterations", 0))
            remaining_steps = max(maximum - current, 0)
            if remaining_steps <= 2:
                urgency = "CRITICAL"
            elif remaining_steps <= 4:
                urgency = "HIGH"
            else:
                urgency = "NORMAL"
        except Exception:
            return []

    lines: List[str] = [
        "",
        f"Time-attack status: urgency={urgency}, remaining_steps={remaining_steps if remaining_steps is not None else 'unknown'}",
    ]
    if urgency == "CRITICAL":
        lines.extend(
            [
                "CRITICAL 모드: 새 가설/요청 확장을 중단하고, 현재 증거로 즉시 결론 + 불확실성만 명확히 기술한다.",
            ]
        )
    elif urgency == "HIGH":
        lines.extend(
            [
                "HIGH 모드: 추가 탐색보다 기존 후보 검증/반례 점검을 우선하고, 새 협업 요청은 최소화한다.",
            ]
        )
    else:
        lines.extend(
            [
                "NORMAL 모드: 필요 시 협업 요청과 추가 검증을 수행하되, 근거 없는 확정은 금지한다.",
            ]
        )
    return lines


def _build_relevance_contract_overlay() -> List[str]:
    return [
        "",
        "Relevance contract (expert_main post-processing alignment):",
        "discussion_type가 author_talk/recommendation/trope_discussion/meta/community_banter/image_post/off_topic/noise/genre_opinion이면 is_relevant=false를 우선 검토한다.",
        "general_discussion은 작품 고유 앵커가 있을 때만 is_relevant=true를 허용한다.",
        "official_title에는 작품 정식명만 허용하며 플랫폼명/URL/커뮤니티 은어는 넣지 않는다.",
    ]


def _build_collaboration_contract_overlay() -> List[str]:
    return [
        "",
        "Collaboration contract:",
        "request_expert를 사용하면 request_reason + request_context.question + 불확실 용어를 함께 남긴다.",
        "증거가 이미 충분하거나 타임어택이 HIGH/CRITICAL이면 새 요청 대신 현재 증거 정리/판정에 집중한다.",
    ]


def _build_common_overlay_lines(ctx: Optional[Any]) -> List[str]:
    lines = [
        "=== DYNAMIC KOREAN UNDERSTANDING OVERLAY ===",
        "Runtime guardrails (high priority for this sample):",
        "1) 일반명사/고유명사 구분은 단어 자체가 아니라 문장 기능(조사, 술어, 담화 역할)으로 판단한다.",
        "2) 검색 결과 매칭 전에 본문/댓글 앵커(캐릭터, 줄거리, 작가, 회차, 플랫폼 URL) 존재를 먼저 확인한다.",
        "3) 제목-본문-댓글 담화가 끊기면 특정 작품 매칭보다 장르/커뮤니티 일반론 가능성을 우선 검토한다.",
        "4) 확신 없는 용어는 추정 확정 대신 unresolved 처리하고 추가 검증을 요청한다.",
        "5) 가설 대입 검증: 후보 제목을 원문 문장에 대입했을 때 의미 비약이 생기면 후보를 배제한다.",
    ]
    lines.extend(_build_time_attack_overlay(ctx))
    lines.extend(_build_relevance_contract_overlay())
    lines.extend(_build_collaboration_contract_overlay())
    return lines


def _build_domain_overlay(ctx: Optional[Any]) -> List[str]:
    domain = _norm(getattr(ctx, "primary_domain", ""))
    if not domain or domain in _NOVEL_DOMAINS:
        return []
    intent = _safe_str(getattr(ctx, "discourse_intent", "")) or "unknown"
    return [
        "",
        f"Domain warning: primary_domain={domain}, intent={intent}",
        "현재 담화 도메인이 소설 바깥일 가능성이 높다. 작품명 확정 기준을 더 엄격히 적용하라.",
    ]


def _build_gatekeeper_overlay(
    post: Optional[Dict[str, Any]],
    comments: Optional[List[str]],
    ctx: Optional[Any],
) -> str:
    title = _norm((post or {}).get("title", ""))
    body = _norm(_join_text_blocks(post))
    comment_text = _norm(" ".join(comments or []))
    merged = f"{title} {body} {comment_text}".strip()

    lines = _build_common_overlay_lines(ctx)
    lines.extend(_build_domain_overlay(ctx))

    platform_like = _contains_any(
        merged,
        ("히토미", "노피아", "노벨피아", "문피아", "카카페", "리디", "시리즈"),
    )
    if platform_like:
        lines.extend(
            [
                "",
                "플랫폼/사이트 동형어 주의:",
                "단어가 사이트/플랫폼/서비스명으로도 쓰이면, 작품 고유 앵커가 나오기 전까지는 플랫폼 해석을 우선한다.",
            ]
        )

    short_body = len(body) < 30
    if short_body:
        lines.extend(
            [
                "",
                "본문 단문/생략 모드:",
                "본문이 짧으면 댓글의 화행(질문/설명/요청)과 제목의 문장 기능 분석 비중을 높여라.",
            ]
        )

    question_heavy = _contains_any(comment_text, ("번호머임", "번호 뭐", "뭐임", "머임", "몇화", "?"))
    if question_heavy:
        lines.extend(
            [
                "",
                "댓글 질문형 다수 감지:",
                "'번호/뭐임' 류 질문은 ID/코드/출처 요청일 수 있다. 이를 곧바로 작품명 증거로 간주하지 마라.",
            ]
        )

    merged_no_space = merged.replace(" ", "")
    order_query_like = (
        _contains_any(
            merged_no_space,
            ("뭐부터", "순서", "시간순", "정주행", "입문", "나머지", "전작", "다본", "읽는순", "보는순"),
        )
        and _contains_any(merged, ("?", "추천", "봐야", "볼만"))
    )
    if order_query_like:
        lines.extend(
            [
                "",
                "다작/순서 질문 가능성:",
                "작가 전작/작품 순서 질문일 수 있다. 단일 작품명 확정보다 recommendation/author_talk 맥락을 우선 검토하라.",
            ]
        )

    return "\n".join(lines)


def _build_decoder_overlay(
    gatekeeper_result: Optional[Dict[str, Any]],
    ctx: Optional[Any],
) -> str:
    clues = (gatekeeper_result or {}).get("context_clues") or {}
    lines = _build_common_overlay_lines(ctx)
    lines.extend(_build_domain_overlay(ctx))

    if clues.get("genre_discussion_detected"):
        lines.extend(
            [
                "",
                "장르 일반론 시그널 감지:",
                "장르/트로프 키워드(연상여친, 모성애 등)는 작품명으로 강제 매핑하지 말고 고유 앵커가 있을 때만 확정한다.",
            ]
        )
    if clues.get("is_recommendation_request"):
        lines.extend(
            [
                "",
                "추천 요청 모드:",
                "추천 댓글의 타 작품명은 참고 정보일 뿐, 원문의 핵심 지칭 대상과 분리해서 판단한다.",
            ]
        )
    if clues.get("dc_opinion_prefix"):
        lines.extend(
            [
                "",
                f"의견 접두사 감지: {clues.get('dc_opinion_prefix')}",
                "의견 접두사는 작품 약칭이 아니라 담화 마커일 수 있으니 작품명 후보로 승격하지 마라.",
            ]
        )
    if clues.get("has_title_masking"):
        lines.extend(
            [
                "",
                "제목 마스킹 감지:",
                "마스킹 텍스트는 해독 과신 금지. 근거 부족 시 unresolved/null로 남겨라.",
            ]
        )
    if clues.get("has_episode_reference"):
        lines.extend(
            [
                "",
                "회차 앵커 감지:",
                "회차 정보는 강한 작품 소비 맥락 신호다. 해당 앵커와 연결되는 후보를 우선 검증하라.",
            ]
        )
    if clues.get("multi_work_order_detected"):
        order_hits = clues.get("order_keywords_found") or []
        lines.extend(
            [
                "",
                "다작/순서 질문 신호 감지:",
                f"order_keywords={order_hits}",
                "이 경우 단일 official_title 강제 고정 금지. 작품군/작가 전작 맥락을 우선 해석하라.",
                "후보가 2개 이상이면 best_match를 성급히 확정하지 말고 unresolved_terms에 순서질문 맥락을 기록하라.",
            ]
        )

    return "\n".join(lines)


def _build_verifier_overlay(
    gatekeeper_result: Optional[Dict[str, Any]],
    decoder_result: Optional[Dict[str, Any]],
    ctx: Optional[Any],
) -> str:
    clues = (gatekeeper_result or {}).get("context_clues") or {}
    lines = _build_common_overlay_lines(ctx)
    lines.extend(_build_domain_overlay(ctx))

    if clues.get("genre_discussion_detected"):
        lines.extend(
            [
                "",
                "장르 담론 우선 검증:",
                "작품 고유 정보가 비어 있으면 genre/community 토론으로 결론내고 키워드 우연일치를 반론으로 명시하라.",
            ]
        )

    unresolved = (decoder_result or {}).get("unresolved_terms") or []
    if unresolved:
        lines.extend(
            [
                "",
                "Decoder 미해결 용어 존재:",
                "미해결 용어가 핵심이면 성급한 작품 확정 대신 불확실성/추가검색 필요성을 결론에 반영하라.",
            ]
        )
    if clues.get("multi_work_order_detected"):
        order_hits = clues.get("order_keywords_found") or []
        lines.extend(
            [
                "",
                "다작/순서 질문 검증 모드:",
                f"order_keywords={order_hits}",
                "원문 목적이 '작품 순서/전작 추천'이면 단일 작품 확정보다 recommendation/general 판정을 우선한다.",
                "작품명이 여럿 언급돼도 비교/순서 예시인지, 특정 작품 토론인지 분리해 결론을 내라.",
            ]
        )

    return "\n".join(lines)


def build_gatekeeper_system_prompt(
    base_system: str,
    *,
    post: Optional[Dict[str, Any]] = None,
    comments: Optional[List[str]] = None,
    ctx: Optional[Any] = None,
) -> str:
    overlay = _build_gatekeeper_overlay(post, comments, ctx)
    return f"{base_system}\n\n{overlay}" if overlay else base_system


def build_decoder_system_prompt(
    base_system: str,
    *,
    gatekeeper_result: Optional[Dict[str, Any]] = None,
    ctx: Optional[Any] = None,
) -> str:
    overlay = _build_decoder_overlay(gatekeeper_result, ctx)
    return f"{base_system}\n\n{overlay}" if overlay else base_system


def build_verifier_system_prompt(
    base_system: str,
    *,
    gatekeeper_result: Optional[Dict[str, Any]] = None,
    decoder_result: Optional[Dict[str, Any]] = None,
    ctx: Optional[Any] = None,
) -> str:
    overlay = _build_verifier_overlay(gatekeeper_result, decoder_result, ctx)
    return f"{base_system}\n\n{overlay}" if overlay else base_system
