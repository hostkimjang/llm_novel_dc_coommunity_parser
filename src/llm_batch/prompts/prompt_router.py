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
        "discussion_type가 author_talk/recommendation/trope_discussion/meta/community_banter이면 adjacent_relevant + is_relevant=false + official_title=null 가능성을 먼저 검토한다.",
        "discussion_type가 image_post/off_topic/noise/genre_opinion이면 is_relevant=false를 우선 검토한다.",
        "general_discussion은 작품 고유 앵커가 있을 때만 is_relevant=true를 허용한다.",
        "official_title에는 작품 정식명만 허용하며 플랫폼명/URL/커뮤니티 은어는 넣지 않는다.",
        "작품 본체 토론이 아니어도 작가/플랫폼/유료화/추천요청/장르 일반론이면 adjacent_relevant 성격의 주변 담론일 수 있으므로 noise로 단순 압축하지 마라.",
        "복수 작품 비교/추천/순서 질문은 단일 official_title 강제보다 multi-work 맥락을 우선 기술하라.",
        "정식 제목 미확정 또는 작가/플랫폼 메타 글에서는 notes/reason에 단일 작품 확정 문장을 쓰지 마라.",
        "decoded_term에는 Mixed Unknown/unknown/N/A 같은 실패 라벨을 쓰지 말고, 불명확하면 slang_insight=null을 우선한다.",
        "일반명사·트로프·장면용어·코스튬+인명 조합·개념어는 작품 고유 브리지가 없으면 작품 약칭으로 승격하지 않는다.",
        "의미/뜻/차이를 묻는 질문형 문맥에서는 검색 결과의 개념 문서를 작품 제목으로 승격하지 않는다.",
        "감지어와 해독어가 정규화 후 동일하고 공식 작품 브리지가 없으면, 슬랭이 아니라 일반 토픽으로 본다.",
        "약칭 후보가 OCR/이미지 표지 텍스트와 충돌하면 오염 문자열을 새 정식 제목으로 만들지 말고, 검증 가능한 URL/본문 앵커/기존 후보를 우선한다.",
        "짧은 표면형이 여러 공식 제목에 공통으로 들어가면 ambiguous_title_stem으로 보고, 본문 앵커가 닫힌 후보만 primary로 둔다. 나머지는 검색 이웃이지 comparison/recommendation/slang 후보가 아니다.",
        "slang_insight.detected_term은 최소 표면형만 넣는다. 감상/질문/상태 접미사(on/off/하렘임/몇화/너무/불쌍/무서워/후기/리뷰/봤다)는 detected_term에 포함하지 않는다.",
        "canonical_work_alias에는 정식 제목을 넣지 않는다. 순수 작품 약칭을 분리할 수 없으면 canonical_work_alias=null, store_in_slang_db=false로 둔다.",
        "정식 제목 그대로, 띄어쓰기 있는 구절, 문장형 제목 표면, 작품+캐릭터/작가/밈 합성 표현은 slang DB 저장 대상이 아니다.",
        "store_in_slang_db=true는 순수 작품 약칭(pure_work_alias)이고 감지어가 짧은 별칭 표면일 때만 허용한다.",
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
        "6) 모든 자연어 출력(reason/notes/evidence 등)은 한국어로 작성한다.",
        "7) 중국어(한자/중문 문장) 출력은 금지한다. 비한국어 원문은 한국어 요약으로 바꿔라.",
        "8) URL/고유 링크는 원문 유지 가능하나, 설명 문장은 반드시 한국어로 작성한다.",
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
    lines.extend(
        [
            "",
            "플랫폼 URL 판정 규칙:",
            "novelpia/munpia 등 공식 플랫폼 도메인이라도 /arena/, /community/, /review/ 같은 커뮤니티/리뷰 네임스페이스는 작품 상세가 아니다.",
            "이런 URL의 page title은 독자 리뷰/커뮤니티 글 제목일 수 있으므로, 별도 작품 상세 URL이나 명시적 alias bridge 없이는 정식 제목 후보로 잠그지 마라.",
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
    lines.extend(
        [
            "",
            "플랫폼 URL 판정 규칙:",
            "공식 플랫폼 도메인이라도 /arena/, /community/, /review/ 네임스페이스는 작품 상세가 아니라 커뮤니티/리뷰 페이지일 가능성이 높다.",
            "그 페이지 제목과 URL 존재만으로 official_title을 승격하지 말고, 별도 작품 상세 URL 또는 본문 직접 브리지를 요구하라.",
            "slang_insight 계약 규칙:",
            "작품 식별 단서(work_identifier_clue)와 DB에 저장할 지속 약칭(persistent_work_alias)을 분리하라.",
            "검색/OCR로 작품을 찾는 데 도움이 된 표현이라도, 재사용 가능한 순수 작품 약칭임이 확인되지 않으면 store_in_slang_db=false다.",
            "감지 표현이 '순수 작품 약칭'인지, '작품+캐릭터/작가 합성'인지 구분하라.",
            "작품+캐릭터/작가 합성이라면 canonical_work_alias에 순수 작품 약칭을 넣고 alias_scope를 work_plus_character/work_plus_author로 표시하라.",
            "합성 표현은 store_in_slang_db=false, 순수 작품 약칭만 store_in_slang_db=true로 표시하라.",
            "detected_term은 문장 전체가 아니라 실제 약칭 표면만 써라. '약칭 + 캐릭터/감상/질문/상태어'는 surface composite이므로 store_in_slang_db=false다.",
            "canonical_work_alias에 정식 제목을 복사하지 마라. 정식 제목뿐이면 canonical_work_alias=null, store_in_slang_db=false다.",
            "짧은 표면형이 복수 공식 제목의 공통 stem이면 alias_scope=mixed_unknown, store_in_slang_db=false로 두고 본문 앵커가 닫힌 후보만 primary로 판단하라.",
            "앵커가 약하지만 검색이 특정 후보로 수렴하면 noise로 단정하지 말고 title hold/unresolved 가능성을 설명하라.",
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


def _build_discourse_overlay(
    post: Optional[Dict[str, Any]],
    comments: Optional[List[str]],
    gatekeeper_result: Optional[Dict[str, Any]],
    ctx: Optional[Any],
) -> str:
    clues = (gatekeeper_result or {}).get("context_clues") or {}
    title = _norm((post or {}).get("title", ""))
    body = _norm(_join_text_blocks(post))
    comment_text = _norm(" ".join(comments or []))
    merged = f"{title} {body} {comment_text}".strip()

    lines = _build_common_overlay_lines(ctx)
    lines.extend(_build_domain_overlay(ctx))

    if clues.get("dc_opinion_prefix"):
        lines.extend(
            [
                "",
                f"의견 접두사 감지: {clues.get('dc_opinion_prefix')}",
                "접두사(예: 스포/질문/잡담)는 작품명이 아닌 담화 마커일 수 있으므로 도메인/의도 분류 근거에서 분리하라.",
            ]
        )

    if clues.get("multi_work_order_detected"):
        order_hits = clues.get("order_keywords_found") or []
        lines.extend(
            [
                "",
                "다작/순서 질문 담화 가능성:",
                f"order_keywords={order_hits}",
                "단일 작품 비평으로 단정하지 말고 recommendation/author_talk/작품군 비교 의도를 우선 검토하라.",
            ]
        )

    has_specific_anchor = _contains_any(
        merged,
        ("주인공", "작가", "회차", "전개", "서사", "복선", "캐릭터", "스포", "죽이고", "결말"),
    )
    if has_specific_anchor:
        lines.extend(
            [
                "",
                "담화-앵커 우선 규칙:",
                "제목/본문/댓글에 고유 앵커(인명·전개·회차·작가)가 반복되면 genre_discussion보다 discuss_work 가능성을 먼저 평가하라.",
            ]
        )

    if len(body) < 30:
        lines.extend(
            [
                "",
                "본문 단문 보정:",
                "본문이 짧아도 제목/댓글의 화행이 강하면 장르 일반론으로 과도 축소하지 말고 문맥 연속성을 점검하라.",
            ]
        )

    return "\n".join(lines)


def _build_arbiter_overlay(
    gatekeeper_result: Optional[Dict[str, Any]],
    decoder_result: Optional[Dict[str, Any]],
    verifier_result: Optional[Dict[str, Any]],
    discourse_result: Optional[Dict[str, Any]],
    ctx: Optional[Any],
) -> str:
    clues = (gatekeeper_result or {}).get("context_clues") or {}
    vf = (verifier_result or {}).get("verification_result") or {}
    dc_analysis = (discourse_result or {}).get("discourse_analysis") or {}

    lines = _build_common_overlay_lines(ctx)
    lines.extend(_build_domain_overlay(ctx))

    def _confidence_rank(conf: Any) -> int:
        c = _norm(conf)
        return {"none": 0, "low": 1, "medium": 2, "high": 3, "max": 4}.get(c, 0)

    def _extract_decoder_title_and_conf(decoder: Optional[Dict[str, Any]]) -> tuple[str, int]:
        if not isinstance(decoder, dict):
            return "", 0
        overall = decoder.get("overall_best_match") or {}
        if isinstance(overall, dict):
            t = _safe_str(overall.get("title")).strip()
            c = _confidence_rank(overall.get("confidence"))
            if t:
                return t, c
        best_title = ""
        best_conf = 0
        for term in decoder.get("decoded_terms") or []:
            if not isinstance(term, dict) or term.get("is_author_name"):
                continue
            bm = term.get("best_match") or {}
            t = _safe_str(bm.get("title")).strip()
            c = _confidence_rank(bm.get("confidence"))
            if t and c > best_conf:
                best_title = t
                best_conf = c
        return best_title, best_conf

    dc_title, dc_conf = _extract_decoder_title_and_conf(decoder_result)
    vf_relevant = vf.get("is_relevant")
    vf_title = ""
    vf_identity = vf.get("novel_identity") or {}
    if isinstance(vf_identity, dict):
        vf_title = _safe_str(
            vf_identity.get("official_novel_title")
            or vf_identity.get("official_title")
            or vf_identity.get("title")
        ).strip()
    vf_relation = vf.get("relation_judgment") or {}
    dc_domain = _norm(dc_analysis.get("primary_domain"))
    dc_intent = _norm(dc_analysis.get("intent"))

    if dc_title and vf_title and _norm(dc_title) == _norm(vf_title) and vf_relevant is True:
        lines.extend(
            [
                "",
                "강한 합의 신호:",
                f"Decoder/Verifier 합의 제목='{dc_title}'",
                "합의 제목을 뒤집으려면 본문 반증(맥락 불일치/앵커 부재/반례 링크)을 final_reasoning에 명시하라.",
            ]
        )

    if vf_relevant is False:
        lines.extend(
            [
                "",
                "Verifier 거부권 해석 규칙:",
                "거부를 유지/해제할 때는 '본문 앵커 강도'와 '검색 일치'를 분리해 설명하라.",
                "검색 결과 존재만으로 거부권을 해제하지 말고 본문 직접 근거(캐릭터/줄거리/회차/작가)를 요구하라.",
            ]
        )

    if isinstance(vf_relation, dict) and vf_relation:
        rel_type = _norm(vf_relation.get("relation_type"))
        rel_target = _norm(vf_relation.get("discussion_target"))
        rel_promotion = _norm(vf_relation.get("promotion_decision"))
        if rel_promotion in {"hold", "reject"}:
            lines.extend(
                [
                    "",
                    "Verifier relation-judge signal:",
                    f"relation_type={rel_type or 'unknown'}, discussion_target={rel_target or 'mixed_or_uncertain'}, promotion={rel_promotion}",
                    "장르/플랫폼/커뮤니티 메타 또는 thematic overlap 판정이면 제목을 되살리지 마라.",
                    "이 신호를 뒤집으려면 본문 안의 직접 앵커나 명시적 alias bridge를 final_reasoning에 제시하라.",
                ]
            )
    lines.extend(
        [
            "",
            "담론 범위 분해:",
            "먼저 이 글이 direct_work_discussion / adjacent_meta_or_fandom / multi_work_reference / work_internal_concept / generic_or_off_topic 중 무엇인지 내부적으로 분류하라.",
            "adjacent_meta_or_fandom이면 관련은 유지할 수 있지만 official_title은 null이 기본값이다.",
            "multi_work_reference면 대표 작품 하나를 억지로 고정하지 마라.",
            "review/arena/community post 제목, 팬아트 제목, 작품 내부 개념(곡명/무공/별칭)만으로 parent work를 확정하지 마라.",
            "parent work를 확정하려면 본문 직접 브리지, 명시적 alias bridge, 캐릭터-작품 강연결, 작품 상세 URL 중 하나 이상을 final_reasoning에 적어라.",
            "slang_insight/alias 최종 정합성:",
            "Verifier가 합성 alias(work_plus_character/work_plus_author)로 본 표현은 순수 작품 은어로 승격하지 마라.",
            "합성 alias라도 작품 관련성은 유지할 수 있지만, canonical_work_alias와 surface composite를 구분해 유지하라.",
            "정식 제목 그대로/띄어쓰기 구절/감상문/질문문/on-off 상태 표면은 DB 저장용 slang이 아니므로 store_in_slang_db=false로 유지하라.",
        ]
    )

    if dc_conf >= 3 and vf_relevant is True and dc_domain in _NOVEL_DOMAINS and dc_intent in {"discuss_work", "review", "spoiler"}:
        lines.extend(
            [
                "",
                "소설 담론 일치 신호:",
                "Discourse가 novel + discuss_work이고 Decoder/Verifier도 양성인 경우, 장르 일반론으로 축소 판정하지 마라.",
            ]
        )

    if clues.get("multi_work_order_detected"):
        lines.extend(
            [
                "",
                "다작/순서 질문 최종 판정:",
                "작품명이 여러 개면 '단일 official_title 강제'보다 질문 의도(순서/추천/비교)와 주제 대상을 먼저 확정하라.",
            ]
        )

    lines.extend(
        [
            "",
            "정합성 체크:",
            "final_decision, final_reasoning, evidence_chain의 결론이 모순되지 않게 작성하라.",
            "예: final_reasoning이 작품 토론 근거를 제시했다면 is_relevant=false/noise로 끝내지 마라.",
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


def build_discourse_system_prompt(
    base_system: str,
    *,
    post: Optional[Dict[str, Any]] = None,
    comments: Optional[List[str]] = None,
    gatekeeper_result: Optional[Dict[str, Any]] = None,
    ctx: Optional[Any] = None,
) -> str:
    overlay = _build_discourse_overlay(post, comments, gatekeeper_result, ctx)
    return f"{base_system}\n\n{overlay}" if overlay else base_system


def build_arbiter_system_prompt(
    base_system: str,
    *,
    gatekeeper_result: Optional[Dict[str, Any]] = None,
    decoder_result: Optional[Dict[str, Any]] = None,
    verifier_result: Optional[Dict[str, Any]] = None,
    discourse_result: Optional[Dict[str, Any]] = None,
    ctx: Optional[Any] = None,
) -> str:
    overlay = _build_arbiter_overlay(
        gatekeeper_result,
        decoder_result,
        verifier_result,
        discourse_result,
        ctx,
    )
    return f"{base_system}\n\n{overlay}" if overlay else base_system
