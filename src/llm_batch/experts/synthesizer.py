"""
Stage 5.5: Synthesizer Expert — 증거 기반 종합 재해석기
Evidence-Based Re-Interpretation Specialist.

모든 전문가(Decoder, Verifier, Critic)가 분석을 마친 뒤,
축적된 증거(검색 결과, 해독된 용어, 검증 결과)를 바탕으로
원본 포스트를 처음부터 다시 읽고 심층 해석합니다.

목표:
- 초기 Decoder가 맥락 부족으로 놓친 숨은 참조 발견
- 검색으로 확인된 캐릭터/작품 정보를 원문에 매핑
- 댓글까지 포함한 전체 맥락에서 작품 연관성 재평가
- Arbiter에게 풍부한 재해석 결과를 전달
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any, Dict, List, Optional

from .utils import parse_json_with_think_removal, _ts


# ============================================================
# Synthesizer 프롬프트
# ============================================================

SYNTHESIZER_SYSTEM = """\
당신은 「증거 기반 재해석 전문가」입니다.

당신의 역할:
- 다른 전문가들이 수집한 모든 증거(검색 결과, 해독된 용어, 검증 결과)를 토대로
- 원본 포스트(제목 + 본문 전체 + 댓글 전체)를 처음부터 다시 읽고
- 증거가 없었을 때는 보이지 않던 숨은 의미, 캐릭터 참조, 작품 연관성을 찾아냅니다.

핵심 원칙:
1. 증거 없는 추측 금지 — 검색 결과나 전문가 발견에 근거해야 함
2. 원문의 모든 부분(제목, 본문, 댓글)을 빠짐없이 재해석
3. "이 단어가 캐릭터명인가?"를 검색 증거로 확인된 것만 연결
4. 댓글에서 추가 작품 관련 실마리 탐색 (작가명, 캐릭터명, 플랫폼명)
4.5. 밈/은어/약칭 문화 설명 — 커뮤니티 밈이나 은어가 발견되면 그 유래, 의미, 사용 맥락을 상세히 서술 (예: "엘루깐"이 무엇의 약칭이고, 어떤 논쟁/문화에서 쓰이는지)

합의 보존 원칙 (❗️ 최우선):
5. Decoder와 Verifier가 동일한 작품을 식별했으면 → 그것이 합의된 작품명입니다.
   이 합의를 뒤집으려면 반드시 다음이 필요합니다:
   a) 합의된 작품이 본문/댓글과 모순되는 구체적 증거
   b) 대안 작품이 본문/댓글과 일치하는 직접 증거 (검색 결과에서 해당 캐릭터명이나 줄거리가 확인된 경우만)
   c) 단순히 "동일 작가의 다른 작품" 언급은 뒤집기 근거가 될 수 없음
6. 검색 결과에서 "작가A의 다른 작품 추천" 형태의 결과는 부수 정보이지, 해당 포스트의 주제가 아닙니다.
7. evidence_alignment의 decoder_match는 Decoder의 실제 출력(best_match, confidence)을 근거로 판단.
   Decoder가 작품을 high/max confidence로 식별했으면 decoder_match는 strong이어야 합니다.
"""

SYNTHESIZER_PROMPT = """\
🔬 EVIDENCE-BASED RE-INTERPRETATION (증거 기반 재해석)

아래 원본 포스트를 모든 수집된 증거와 함께 처음부터 다시 읽고 심층 해석하세요.

━━━ 원본 포스트 (전문) ━━━
🆔 Post ID: {post_id}
📌 제목: {title}

📝 본문 전체:
{full_body}

💬 댓글 전체 ({comment_count}개):
{full_comments}

━━━ 수집된 증거 ━━━

🔤 Decoder 해독 결과:
{decoder_findings}

🔍 Verifier 검증 결과:
{verifier_findings}

📚 검색으로 확인된 정보:
{search_evidence}

{extra_context}

━━━ 재해석 지시 ━━━

위 증거를 바탕으로 원본 포스트를 다시 읽고 다음을 분석하세요:

1. **텍스트 재해석**: 본문의 각 문장/표현이 실제로 무엇을 말하는지 증거 기반으로 해석
   - 예: "캐릭터갑이 불쌍해" → 검색 증거에서 캐릭터갑이 [작품명]의 캐릭터로 확인 → 캐릭터 감상
   - 예: "[작가명] 신작 초대남이 죆같은데" → 작가는 식별 가능하나, "신작"은 작성자 시점의 상대적 지칭이므로 정확한 제목을 특정할 수 없음 → 작품 비평이나 official_title은 null

2. **댓글 재해석**: 댓글에서 작품/캐릭터 관련 추가 실마리 발견
   - 댓글이 작품 맥락에서 반응하는지, 일상 맥락에서 반응하는지

3. **숨은 참조 발견**: 초기 Decoder가 놓쳤지만 증거로 뒷받침되는 참조
   - 캐릭터 이름이 일반 명사처럼 보여서 놓친 것
   - 줄거리 요소가 일상 표현처럼 보여서 놓친 것

4. **증거 정합성 평가**: 전문가들의 식별이 원문 맥락과 실제로 맞는지
   - Decoder가 식별한 작품이 본문/댓글의 내용과 일치하는가?
   - 검색에서 찾은 캐릭터가 본문에서 언급되는가?

5. **최종 확신도**: 모든 증거를 종합한 뒤의 판단
   - 이 포스트가 실제로 특정 작품에 대한 것인지
   - 아니면 다른 맥락(작가 품평, 일상, 밈 등)인지

6. **밈/은어/커뮤니티 문화 설명**: 게시물에서 밈, 은어, 약칭이 발견되면 그 문화적 맥락을 상세히 설명
   - 그 밈/약칭이 무엇의 줄임말이고, 어떤 의미인지 (예: "북모리엘루깐" = 북유럽+모리+엘리+루시아+깐부+α 등 여러 소설 히로인 이름 조합)
   - 커뮤니티에서 사람들이 어떤 맥락/의도로 사용하는지 (예: "히로인 정실 논쟁 떡밥", "추천 목록", "비교 논의" 등)
   - 관련 작품군이나 유래, 어떻게 생겨난 밈인지 (예: "원래 3명이었다가 6명으로 확장")
   - 이 정보를 synthesis_summary에 반드시 포함하세요

OUTPUT JSON:
{{
  "reinterpretation": {{
    "post_intent": "string (Korean) — 포스트의 실제 의도/목적 한 문장 요약",
    "text_analysis": [
      {{
        "segment": "원문 텍스트 일부",
        "interpretation": "증거 기반 해석 (Korean)",
        "evidence_source": "decoder|verifier|search|comment"
      }}
    ],
    "comment_insights": [
      {{
        "comment": "댓글 원문",
        "insight": "작품 관련 실마리 또는 맥락 (Korean)"
      }}
    ]
  }},
  "hidden_references": [
    {{
      "text": "원문에서 발견된 숨은 참조",
      "reference_type": "character|plot|author|platform|setting",
      "matched_to": "무엇에 매칭되는지",
      "evidence": "근거 (Korean)"
    }}
  ],
  "evidence_alignment": {{
    "decoder_match": "strong|partial|weak|contradicted",
    "decoder_reason": "string (Korean)",
    "verifier_match": "strong|partial|weak|contradicted",
    "verifier_reason": "string (Korean)",
    "overall_coherence": "high|medium|low — 전체 증거와 원문의 일관성"
  }},
  "confidence_assessment": {{
    "is_about_identified_work": true|false,
    "confidence": "Max|High|Medium|Low|None",
    "reasoning": "string (Korean) — 왜 이 확신도인지",
    "alternative_interpretation": "string|null (Korean) — 다른 해석 가능성"
  }},
  "synthesis_summary": "string (Korean) — Arbiter에게 전달할 핵심 요약 (3-5문장)"
}}

CRITICAL:
- 증거에 없는 작품/캐릭터를 추측하지 마세요
- 검색 결과에서 확인된 것만 연결하세요
- "모르겠다"가 잘못된 추측보다 낫습니다
- 검색 근거 인용 시 search_evidence에 제공된 EID(`[E001]` 형식)만 사용하세요.
- 임의 번호(`[1]`, `[2]`) 생성 금지.

⚠️ 합의 보존 규칙 (절대 위반 금지):
- Decoder와 Verifier가 동일한 작품을 high confidence로 식별했으면,
  그 작품을 다른 작품으로 교체하지 마세요.
- "동일 작가의 다른 작품"이 검색되었다고 해서 해당 포스트가 다른 작품에 대한 것이라고 뒤집지 마세요.
  예: "작가A 작품X를 논의하는 글"에서 "작가A의 다른 작품Y가 검색됨" → 이것은 작품Y에 대한 글이 아닙니다.
- hidden_references는 "Decoder/Verifier가 놓친 추가 참조"이지,
  "이미 맞캔 작품 대신 다른 작품을 넣는 곳"이 아닙니다.

RETURN ONLY THE JSON."""


class SynthesizerExpert:
    """
    🔬 Synthesizer — 증거 기반 종합 재해석기

    모든 전문가 분석 완료 후, 축적된 증거를 바탕으로
    원본 포스트를 처음부터 다시 읽고 심층 해석합니다.
    """

    def __init__(self, llm_client):
        self.llm = llm_client
        self.name = "Synthesizer"
        self.emoji = "🔬"

    @staticmethod
    def _hidden_reference_dicts(hidden: Any) -> List[Dict[str, Any]]:
        if isinstance(hidden, dict):
            return [hidden]
        if not isinstance(hidden, list):
            return []
        return [item for item in hidden if isinstance(item, dict)]

    def _call_llm(self, user_prompt: str) -> Optional[Dict[str, Any]]:
        """LLM 호출 + JSON 파싱"""
        response_text = ""
        try:
            import os
            _default_max_tokens = os.getenv(
                "LLM_EXPERT_MAX_TOKENS",
                os.getenv("LLM_MAX_TOKENS", "32768"),
            )
            max_tokens = int(_default_max_tokens)
            max_tokens = max(512, min(max_tokens, 65536))
            messages = [
                {"role": "system", "content": SYNTHESIZER_SYSTEM},
                {"role": "user", "content": user_prompt},
            ]

            response_text = self.llm._stream_chat_http(
                messages=messages,
                tag="synthesizer",
                use_grammar=True,
                max_tokens=max_tokens,
            )

            if not response_text:
                return None

            parsed = parse_json_with_think_removal(response_text)
            return parsed
        except Exception as e:
            _finish_reason = getattr(self.llm, "last_finish_reason", None)
            _raw_len = len(response_text or "")
            _tail = (response_text or "")[-240:].replace("\n", " ")
            print(
                f"[{_ts()}][{self.emoji}] {self.name} LLM 오류: {e} "
                f"(max_tokens={max_tokens}, finish_reason={_finish_reason}, raw_len={_raw_len})",
                file=sys.stderr,
            )
            if _tail:
                print(
                    f"[{_ts()}][{self.emoji}] {self.name} 응답 꼬리(디버그): {_tail}",
                    file=sys.stderr,
                )
            return None

    # ------------------------------------------------------------------ #
    #  공개 API
    # ------------------------------------------------------------------ #

    def analyze(
        self,
        ctx: "ConversationContext",
    ) -> Dict[str, Any]:
        """
        증거 기반으로 원본 포스트를 재해석합니다.

        Args:
            ctx: 모든 전문가 출력과 검색 결과가 담긴 ConversationContext

        Returns:
            재해석 결과 dict
        """
        start_time = time.time()

        print(
            f"[{_ts()}][{self.emoji}] {self.name} 증거 기반 재해석 시작: post_id={ctx.post_id}",
            file=sys.stderr,
        )

        from .orchestrator import ExpertType

        # ── 1. 원본 포스트 전문 구성 ──
        post_data = ctx.post_data or {}
        title = post_data.get("title", "(제목 없음)")

        # 본문 전체 (잘라내지 않음!)
        content_blocks = post_data.get("content_blocks", [])
        full_body_parts: List[str] = []
        for block in content_blocks:
            if isinstance(block, str):
                full_body_parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text") or block.get("content")
                if text:
                    full_body_parts.append(str(text))
                elif block.get("type") == "image":
                    full_body_parts.append("[이미지]")
            else:
                full_body_parts.append(str(block))
        full_body = "\n".join(full_body_parts) if full_body_parts else "(본문 없음)"

        # 본문 길이 제한 (극단적으로 긴 경우 2000자)
        if len(full_body) > 2000:
            full_body = full_body[:2000] + "\n... (이하 생략)"

        # 댓글 전체
        comments = ctx.comments or []
        if comments:
            full_comments = "\n".join(
                f"[{i + 1}] {c}" for i, c in enumerate(comments[:20])  # 최대 20개
            )
        else:
            full_comments = "(댓글 없음)"
        comment_context_lines = [
            str(line)
            for line in ((post_data or {}).get("comment_context_lines") or [])[:20]
            if str(line).strip()
        ]
        comment_dialogue_lines = [
            str(line)
            for line in ((post_data or {}).get("comment_dialogue_context_lines") or [])[:20]
            if str(line).strip()
        ]

        # ── 2. Decoder 발견사항 요약 ──
        decoder_out = ctx.get_expert_output(ExpertType.DECODER) or {}
        decoder_findings = self._format_decoder_findings(decoder_out)

        # ── 3. Verifier 발견사항 요약 ──
        verifier_out = ctx.get_expert_output(ExpertType.VERIFIER) or {}
        verifier_findings = self._format_verifier_findings(verifier_out)

        # ── 4. 검색 증거 (상위 관련 결과) ──
        search_results = ctx.search_results or []
        search_evidence = self._format_search_evidence(search_results)

        # ── 5. 추가 맥락 (가설 이력, Discourse 분석, snippet 힌트 등) ──
        extra_parts: List[str] = []

        # Discourse 분석 결과
        if hasattr(ctx, "primary_domain") and ctx.primary_domain:
            extra_parts.append(
                f"📊 Discourse 분석: domain={ctx.primary_domain}, intent={getattr(ctx, 'discourse_intent', '?')}"
            )
        if comment_context_lines:
            extra_parts.append(
                "댓글 작성자/대화 맥락: "
                + " / ".join(comment_context_lines)
                + " (role=post_author는 본문 작성자의 댓글)"
            )
        if comment_dialogue_lines:
            extra_parts.append(
                "댓글 발화 재구성: "
                + " / ".join(comment_dialogue_lines)
                + " (speaker/author/ip는 대화 흐름 추적용이며 작품명 증거가 아님)"
            )

        discourse_out = ctx.get_expert_output(ExpertType.DISCOURSE) or {}
        if discourse_out:
            da = discourse_out.get("discourse_analysis", {})
            if da.get("is_association_not_discussion"):
                extra_parts.append("⚠️ DiscourseAnalyzer 판정: 연상글 (작품 토론이 아님)")
            if da.get("primary_domain") and da["primary_domain"] != "novel_literature":
                extra_parts.append(f"⚠️ Discourse 도메인: {da['primary_domain']} (비소설)")

        # Critic 결과
        critic_out = ctx.get_expert_output(ExpertType.CRITIC) or {}
        if critic_out and critic_out.get("detected_titles"):
            titles_str = ", ".join(str(t) for t in critic_out["detected_titles"][:3])
            extra_parts.append(f"📚 Critic 감지 제목: {titles_str}")

        # verified_character_work_links
        if hasattr(ctx, "verified_character_work_links") and ctx.verified_character_work_links:
            links = ctx.verified_character_work_links
            links_str = ", ".join(
                f"{l.get('character', '?')}→{l.get('work_title', '?')}"
                for l in links[:5]
            )
            extra_parts.append(f"✅ 검증된 캐릭터-작품 링크: {links_str}")

        # snippet 힌트
        if hasattr(ctx, "snippet_hints") and ctx.snippet_hints:
            hints = ctx.snippet_hints
            if hints.get("title_hints"):
                extra_parts.append(f"💡 제목 힌트: {', '.join(str(h) for h in hints['title_hints'][:3])}")
            if hints.get("abbreviation_hints"):
                extra_parts.append(
                    f"💡 약어 힌트: {', '.join(str(h) for h in hints['abbreviation_hints'][:3])}"
                )

        extra_context = "\n".join(extra_parts) if extra_parts else "(추가 맥락 없음)"

        # ── 6. 프롬프트 조합 + LLM 호출 ──
        user_prompt = SYNTHESIZER_PROMPT.format(
            post_id=ctx.post_id,
            title=title,
            full_body=full_body,
            comment_count=len(comments),
            full_comments=full_comments,
            decoder_findings=decoder_findings,
            verifier_findings=verifier_findings,
            search_evidence=search_evidence,
            extra_context=extra_context,
        )

        result = self._call_llm(user_prompt)
        elapsed = time.time() - start_time

        if not result:
            print(
                f"[{_ts()}][{self.emoji}] {self.name} LLM 응답 실패 → 빈 결과 반환 ({elapsed:.1f}s)",
                file=sys.stderr,
            )
            return {"error": "Synthesizer LLM returned None", "elapsed": elapsed}

        # ── 7. 결과 로깅 ──
        conf_assess = result.get("confidence_assessment", {})
        ev_align = result.get("evidence_alignment", {})
        summary = result.get("synthesis_summary", "")

        print(
            f"[{_ts()}][{self.emoji}] {self.name} 완료 ({elapsed:.1f}s): "
            f"is_about_work={conf_assess.get('is_about_identified_work')}, "
            f"confidence={conf_assess.get('confidence')}, "
            f"coherence={ev_align.get('overall_coherence')}",
            file=sys.stderr,
        )

        hidden_refs = self._hidden_reference_dicts(result.get("hidden_references", []))
        if hidden_refs:
            print(
                f"[{_ts()}][{self.emoji}]   숨은 참조 {len(hidden_refs)}개 발견:",
                file=sys.stderr,
            )
            for h in hidden_refs[:3]:
                print(
                    f"[{_ts()}][{self.emoji}]     - [{h.get('reference_type', '?')}] "
                    f"\"{h.get('text', '')}\" → {h.get('matched_to', '?')}",
                    file=sys.stderr,
                )

        if summary:
            # 요약 첫 200자만 로그
            print(
                f"[{_ts()}][{self.emoji}]   요약: {summary[:200]}",
                file=sys.stderr,
            )

        result["elapsed"] = elapsed
        return result

    # ------------------------------------------------------------------ #
    #  내부 포맷터
    # ------------------------------------------------------------------ #

    def _format_decoder_findings(self, decoder_out: Dict[str, Any]) -> str:
        """Decoder 결과를 읽기 쉽게 포맷"""
        if not decoder_out:
            return "(Decoder 결과 없음)"

        parts: List[str] = []
        overall_conf = decoder_out.get("overall_confidence", "?")
        parts.append(f"전체 신뢰도: {overall_conf}")

        decoded_terms = decoder_out.get("decoded_terms", [])
        for i, term in enumerate(decoded_terms[:5], 1):
            if not isinstance(term, dict):
                continue
            original = term.get("original", "?")
            best_match = term.get("best_match", {}) or {}
            title = best_match.get("title", "미식별")
            conf = best_match.get("confidence", "?")
            url = best_match.get("url", "")

            # 후보 목록
            candidates = term.get("candidates", [])
            cand_str = ""
            if candidates and isinstance(candidates, list):
                cand_names = [
                    c.get("official_novel_title", "?")
                    for c in candidates[:3]
                    if isinstance(c, dict) and c.get("official_novel_title")
                ]
                if cand_names:
                    cand_str = f" (후보: {', '.join(cand_names)})"

            parts.append(
                f"[{i}] \"{original}\" → {title} ({conf}){cand_str}"
                + (f"\n    URL: {url}" if url else "")
            )

            # 근거(grounding) 정보
            grounding = term.get("grounding", {})
            if isinstance(grounding, dict) and grounding:
                body_refs = grounding.get("body_text_references", [])
                if body_refs:
                    parts.append(f"    본문 근거: {', '.join(str(r) for r in body_refs[:3])}")

            # is_author_name 표시
            if term.get("is_author_name"):
                parts.append(f"    ⚠️ 작가명으로 분류됨")

        return "\n".join(parts) if parts else "(해독 결과 없음)"

    def _format_verifier_findings(self, verifier_out: Dict[str, Any]) -> str:
        """Verifier 결과를 읽기 쉽게 포맷"""
        if not verifier_out:
            return "(Verifier 결과 없음)"

        vr = verifier_out.get("verification_result", {})
        if not vr:
            return "(검증 결과 없음)"

        parts: List[str] = []
        parts.append(f"관련성: {vr.get('is_relevant', '?')}")

        novel_id = vr.get("novel_identity", {}) or {}
        novel_title = novel_id.get("official_novel_title") or novel_id.get("official_title")
        if novel_title:
            parts.append(f"작품: {novel_title} ({novel_id.get('confidence', '?')})")
        if novel_id.get("heretic_url"):
            parts.append(f"URL: {novel_id['heretic_url']}")

        # grounding_check
        gc = vr.get("grounding_check", {}) or {}
        if gc:
            parts.append(
                f"근거 확인: anchor={gc.get('anchor_found', '?')}, "
                f"decoder_grounded={gc.get('decoder_grounded', '?')}"
            )

        relation = vr.get("relation_judgment", {}) or {}
        if relation:
            parts.append(
                f"관계판정: type={relation.get('relation_type', '?')}, "
                f"target={relation.get('discussion_target', '?')}, "
                f"promotion={relation.get('promotion_decision', '?')}, "
                f"confidence={relation.get('confidence', '?')}"
            )
            relation_reason = str(
                relation.get("reason")
                or vr.get("relation_hold_reason")
                or ""
            ).strip()
            if relation_reason:
                parts.append(f"관계판정 사유: {relation_reason}")

        # 반론
        counter_args = vr.get("counter_arguments", [])
        if counter_args:
            for ca in counter_args[:2]:
                if isinstance(ca, dict):
                    counter_text = str(
                        ca.get("explanation")
                        or ca.get("argument")
                        or ca.get("issue")
                        or ""
                    ).strip()
                    parts.append(
                        f"⚠️ 반론: {counter_text or '?'} "
                        f"(severity={ca.get('severity', '?')}, action={ca.get('action', '?')})"
                    )

        # author_info
        author_info = vr.get("author_info", {}) or {}
        if author_info.get("is_author_criticism"):
            parts.append(
                f"📝 작가비평: detected_author={author_info.get('detected_author', '?')}"
            )

        return "\n".join(parts) if parts else "(검증 정보 없음)"

    def _format_search_evidence(self, search_results: List[Dict[str, Any]]) -> str:
        """검색 결과를 요약 포맷"""
        if not search_results:
            return "(검색 결과 없음)"

        # 전역 canonical EID 순서(_evidence_rank) 유지
        ranked_results: List[Dict[str, Any]] = []
        for i, r in enumerate(search_results, 1):
            if not isinstance(r, dict):
                continue
            try:
                rank = int(r.get("_evidence_rank")) if r.get("_evidence_rank") is not None else 10**9
            except Exception:
                rank = 10**9
            r2 = dict(r)
            r2["_rank"] = rank
            if not r2.get("_evidence_id"):
                r2["_evidence_id"] = f"T{i:03d}"
            ranked_results.append(r2)
        ranked_results.sort(key=lambda r: (r.get("_rank", 10**9), str(r.get("_evidence_id") or "")))

        parts: List[str] = []
        for r in ranked_results[:20]:
            eid = str(r.get("_evidence_id") or "").strip() or "T???"
            title = str(r.get("title", "")).strip()
            url = str(r.get("url", "")).strip()
            content = str(r.get("content", "")).strip()
            trust = float(r.get("_trust_score", 0) or 0)
            purpose = str(r.get("_purpose", "")).strip()
            query = str(r.get("_query", "")).strip()

            # 내용 200자 제한
            if len(content) > 200:
                content = content[:200] + "..."

            meta_lines = ""
            if purpose:
                meta_lines += f"    purpose: {purpose}\n"
            if query:
                meta_lines += f"    from_query: {query}\n"
            parts.append(
                f"[{eid}] {title}\n"
                f"    URL: {url}\n"
                f"{meta_lines}"
                f"    신뢰도: {trust:.1f}\n"
                f"    내용: {content}"
            )

        return "\n".join(parts)

    # ------------------------------------------------------------------ #
    #  Arbiter 전달용 요약 생성
    # ------------------------------------------------------------------ #

    @staticmethod
    def summarize_for_arbiter(synth_result: Dict[str, Any]) -> str:
        """
        Synthesizer 결과를 Arbiter 프롬프트에 삽입할 compact 요약으로 변환.
        """
        if not synth_result or "error" in synth_result:
            return ""

        parts: List[str] = []
        parts.append("\n\n=== 🔬 SYNTHESIZER (증거 기반 재해석) ===")

        # 핵심 요약
        summary = synth_result.get("synthesis_summary", "")
        if summary:
            parts.append(f"📋 요약: {summary}")

        # 확신도 평가
        conf = synth_result.get("confidence_assessment", {})
        if conf:
            parts.append(
                f"🎯 판정: is_about_work={conf.get('is_about_identified_work')}, "
                f"confidence={conf.get('confidence')}"
            )
            reasoning = conf.get("reasoning", "")
            if reasoning:
                parts.append(f"   이유: {reasoning[:200]}")
            alt = conf.get("alternative_interpretation")
            if alt:
                parts.append(f"   대안 해석: {alt[:150]}")

        # 증거 정합성
        ev = synth_result.get("evidence_alignment", {})
        if ev:
            parts.append(
                f"📊 정합성: decoder={ev.get('decoder_match')}, "
                f"verifier={ev.get('verifier_match')}, "
                f"overall={ev.get('overall_coherence')}"
            )

        # 숨은 참조
        hidden_refs = SynthesizerExpert._hidden_reference_dicts(
            synth_result.get("hidden_references", [])
        )
        if hidden_refs:
            parts.append(f"🔎 숨은 참조 {len(hidden_refs)}개:")
            for h in hidden_refs[:3]:
                ref_type = h.get("reference_type", "?")
                text = h.get("text", "")
                matched = h.get("matched_to", "?")
                parts.append(f"   [{ref_type}] \"{text}\" → {matched}")

        # 댓글 인사이트
        reinterp = synth_result.get("reinterpretation", {})
        comment_insights = reinterp.get("comment_insights", [])
        if comment_insights:
            meaningful = [
                ci for ci in comment_insights
                if isinstance(ci, dict) and ci.get("insight")
            ]
            if meaningful:
                parts.append(f"💬 댓글 인사이트 {len(meaningful)}개:")
                for ci in meaningful[:2]:
                    parts.append(f"   \"{ci.get('comment', '')[:50]}\" → {ci.get('insight', '')[:100]}")

        return "\n".join(parts)
