"""
Stage 3: Verifier Expert - 증거 검증 분석관
Final evidence verification and confirmation.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any, Dict, List, Optional

from .prompts import VERIFIER_SYSTEM, VERIFIER_PROMPT
from .utils import parse_json_with_think_removal, _ts
from ..rules import OFFICIAL_PLATFORMS, GENRE_ARCHETYPE_TERMS


class VerifierExpert:
    """
    🔍 Verifier - Evidence Verification Analyst
    
    Responsibilities:
    - Cross-reference evidence from all sources
    - Final confirmation or rejection
    - Build evidence chain
    - Prevent false positives
    """
    
    def __init__(self, llm_client):
        self.llm = llm_client
        self.name = "Verifier"
        self.emoji = "🔍"
    
    def analyze(
        self,
        post: Dict[str, Any],
        comments: List[str],
        gatekeeper_result: Dict[str, Any],
        decoder_result: Dict[str, Any],
        verification_search: Optional[List[Dict[str, Any]]] = None,
        conversation_context: Optional[str] = None,
        ctx: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Verify decoded candidates and make final determination.
        
        Args:
            post: Original post data
            comments: Comment texts
            gatekeeper_result: Stage 1 output
            decoder_result: Stage 2 output
            verification_search: Additional search results for verification
            conversation_context: Optional conversation history from other experts
            
        Returns:
            VerifierResult with final identity, evidence chain, confidence
            May include request_expert/request_reason for dynamic routing
        """
        start_time = time.time()
        
        # None 체크
        post = post or {}
        comments = comments or []
        
        post_id = post.get("post_id", "?")
        
        # Build post JSON
        post_json = self._build_post_json(post, comments)
        
        # None 체크
        gatekeeper_result = gatekeeper_result or {}
        decoder_result = decoder_result or {}
        
        # 전문가 결과 요약 (토큰 절약)
        gatekeeper_summary = self._summarize_gatekeeper(gatekeeper_result)
        decoder_summary = self._summarize_decoder(decoder_result)
        
        # Suspected titles from Context (다른 전문가가 생성한 의심 작품 목록)
        suspected_titles_info = ""
        if ctx and hasattr(ctx, 'suspected_titles') and ctx.suspected_titles:
            suspected_items = []
            for st in ctx.suspected_titles[:3]:
                title = st.get('title', 'Unknown')
                conf = st.get('confidence', 0.5)
                try:
                    conf_str = f"{float(conf):.2f}"
                except (ValueError, TypeError):
                    conf_str = str(conf)
                suspected_items.append(f"- {title} (conf={conf_str})")
            suspected_titles_info = "\n\n=== SUSPECTED TITLES (의심 작품) ===\n" + "\n".join(suspected_items) + "\n"
        
        # 제안 1: DiscourseAnalyzer 결과를 Verifier에게 전달
        discourse_context = ""
        if ctx and hasattr(ctx, 'primary_domain') and ctx.primary_domain:
            discourse_context = f"""
DiscourseAnalyzer 분석 결과:
- Primary Domain: {ctx.primary_domain}
- Intent: {ctx.discourse_intent or 'unknown'}

이 정보를 활용하여 도메인 불일치 여부를 체크하세요.
"""
        else:
            discourse_context = "DiscourseAnalyzer 정보 없음 (스킵 가능)"
        
        # Format prompt
        context_section = ""
        if conversation_context:
            context_section = f"\n\n=== CONVERSATION HISTORY ===\n{conversation_context}\n"
        
        user_prompt = VERIFIER_PROMPT.format(
            post_json=json.dumps(post_json, ensure_ascii=False, indent=2),
            gatekeeper_json=json.dumps(gatekeeper_summary, ensure_ascii=False, indent=2),
            decoder_json=json.dumps(decoder_summary, ensure_ascii=False, indent=2),
            verification_search_json=json.dumps(verification_search or [], ensure_ascii=False, indent=2),
            discourse_context=discourse_context,
        ) + suspected_titles_info + context_section
        
        # 🆕 코드레벨 약어 분석 힌트 주입
        # Decoder 후처리에서 abbreviation_match_score로 발견한 매칭 정보를
        # Verifier LLM에게 전달 → 할루시네이션 방지 + 정확한 추론 유도
        if ctx and hasattr(ctx, 'code_level_hints') and ctx.code_level_hints:
            hints_section = "\n\n=== CODE-LEVEL ABBREVIATION ANALYSIS (코드 레벨 약어 분석 결과) ===\n"
            hints_section += "아래는 코드 레벨 음절 매칭 알고리즘이 발견한 결과입니다.\n"
            hints_section += "이 분석은 약어의 각 음절이 후보 제목의 단어 첫 글자와 순서대로 매칭되는지를 검증합니다.\n"
            hints_section += "LLM 추론과 독립적인 객관적 분석이므로, 높은 score(≥0.8)는 강한 증거입니다.\n\n"
            for i, hint in enumerate(ctx.code_level_hints[:3], 1):
                hints_section += (
                    f"  [{i}] 약어: '{hint.get('effective_keyword', '?')}' → "
                    f"후보: '{hint.get('corrected_title', '?')}' "
                    f"(score={hint.get('abbreviation_score', 0):.2f}, "
                    f"source={hint.get('source', '?')})\n"
                    f"      근거: {hint.get('reasoning', '')}\n"
                )
            hints_section += "\n⚠️ 위 코드 분석 결과를 우선 고려하되, 검색 증거·본문 맥락과 교차 검증하세요.\n"
            hints_section += "코드 분석과 다른 제목을 선택하려면 명확한 반증을 제시하세요.\n"
            user_prompt += hints_section
        
        # 이전 검색 쿼리 이력 전달 (중복 검색 방지)
        if ctx and hasattr(ctx, 'searched_queries') and ctx.searched_queries:
            searched_list = sorted(ctx.searched_queries)
            user_prompt += f"\n\n=== PREVIOUS SEARCHES (이미 실행된 검색 쿼리) ===\n"
            for q in searched_list:
                user_prompt += f"  - {q}\n"
            user_prompt += "\n⚠️ verification_search 요청 시 위 쿼리는 이미 실행되었으므로 중복 요청하지 마세요.\n"
            user_prompt += "다른 관점/키워드로 새로운 쿼리를 작성하세요.\n"
        
        print(f"[{_ts()}][{self.emoji}] {self.name} 검증 시작: post_id={post_id}", file=sys.stderr)
        
        try:
            result = self._call_llm(user_prompt)
            elapsed = time.time() - start_time
            
            verification = result.get("verification_result", {})
            novel_id = verification.get("novel_identity") or {}
            
            # 🔥 LLM 제목 환각 교정: 검색 결과/Decoder best_match와 대조
            if novel_id and ctx:
                llm_title = novel_id.get("official_novel_title") or novel_id.get("official_title")
                if llm_title:
                    all_search = (ctx.search_results or []) + (verification_search or [])
                    corrected = self._correct_title_from_evidence(llm_title, decoder_result, all_search)
                    if corrected != llm_title:
                        print(f"[{_ts()}][{self.emoji}] ⚠️ 제목 교정: LLM='{llm_title}' → '{corrected}'", file=sys.stderr)
                        if novel_id.get("official_novel_title"):
                            novel_id["official_novel_title"] = corrected
                        if novel_id.get("official_title"):
                            novel_id["official_title"] = corrected
            
            # 🚨 게시글 제목 도용 방지 (P0-4 선제 방어)
            # Verifier가 게시글 제목을 그대로 official_novel_title에 넣는 경우 차단
            verified_title = (novel_id.get("official_novel_title") or
                              novel_id.get("official_title")) if novel_id else None
            
            # 🛡️ 아키타입 용어 가드: Decoder가 차단한 아키타입 제목을 Verifier가 재도입하는 것 방지
            # Decoder의 decoded_terms에서 아키타입 차단된 원본 키워드를 확인하고,
            # Verifier 제목에 해당 아키타입 용어가 포함되어 있으면 차단
            if verified_title and decoder_result:
                blocked_archetypes = set()
                for term in decoder_result.get("decoded_terms", []):
                    original = (term.get("original") or "").strip()
                    if original in GENRE_ARCHETYPE_TERMS:
                        blocked_archetypes.add(original)
                    # Decoder가 title=None으로 차단한 아키타입도 감지
                    best = term.get("best_match") or {}
                    if (best.get("confidence") in ("none", None)
                            and not best.get("title")
                            and original in GENRE_ARCHETYPE_TERMS):
                        blocked_archetypes.add(original)
                
                if blocked_archetypes:
                    # Verifier 제목에 차단된 아키타입 용어가 포함되어 있는지 확인
                    title_norm = verified_title.replace(" ", "")
                    for arch_term in blocked_archetypes:
                        if arch_term.replace(" ", "") in title_norm:
                            print(
                                f"[{_ts()}][{self.emoji}] 🛡️ 아키타입 재도입 차단: "
                                f"Decoder가 '{arch_term}' 아키타입 차단 → "
                                f"Verifier '{verified_title}' 재도입 불허 → null 강제",
                                file=sys.stderr,
                            )
                            novel_id["official_novel_title"] = None
                            if "official_title" in novel_id:
                                novel_id["official_title"] = None
                            novel_id["confidence"] = "Low"
                            verified_title = None
                            break
            
            if verified_title:
                post_title = post.get("title", "")
                if post_title:
                    self._guard_post_title_as_novel(
                        novel_id, verified_title, post_title, decoder_result
                    )
            
            # 🛡️ 아이디어 F: heretic_url 자기참조 검증
            # Verifier가 제시한 증거 URL이 현재 분석 중인 게시글 자신의 URL이면
            # 순환 논증이므로 증거를 무효화하고 confidence 하향
            if novel_id and ctx:
                heretic_url = novel_id.get("heretic_url", "") or ""
                current_pid = str(post.get("post_id", ""))
                if heretic_url and current_pid and current_pid in heretic_url:
                    # dcinside URL에 자기 post_id가 포함 → 자기참조
                    if "dcinside.com" in heretic_url:
                        print(
                            f"[{_ts()}][{self.emoji}] 🛡️ heretic_url 자기참조 감지: "
                            f"'{heretic_url}' contains post_id={current_pid} → 증거 무효화",
                            file=sys.stderr,
                        )
                        novel_id["heretic_url"] = None
                        novel_id["confidence"] = "Low"
                        novel_id["evidence_type"] = "self_reference_invalid"

            # 🛡️ 아이디어 G: 작가명 vs 소설 제목 구분
            # 검색 결과에서 Verifier 제목이 '작가명'으로 등장하면 소설 제목이 아님
            # 단, Decoder가 별도로 작가명을 식별하고 이 제목과 구분한 경우에는 적용 안함
            verified_title_g = (novel_id.get("official_novel_title")
                                or novel_id.get("official_title")) if novel_id else None
            if verified_title_g and ctx and novel_id.get("confidence") in ("High", "high"):
                # 🆕 Decoder가 이미 작가명을 별도로 식별했는지 확인
                # Decoder가 is_author_name=true인 다른 term을 두고 이 title을 '작품'으로
                # 판정했으면, Verifier가 독자적으로 뒤집지 않음
                decoder_has_separate_author = False
                for dt in decoder_result.get("decoded_terms", []):
                    if dt.get("is_author_name"):
                        # 작가명 term이 있고, 그 작가의 작품으로 verified_title_g를 가리키면 통과
                        author_work = (dt.get("author_info") or {}).get("associated_work", "")
                        if author_work and author_work.replace(" ", "") == verified_title_g.replace(" ", ""):
                            decoder_has_separate_author = True
                            break
                        # associated_work이 없어도, 다른 term이 이 title을 best_match로 가지고 있으면
                        for other_dt in decoder_result.get("decoded_terms", []):
                            if other_dt is not dt and not other_dt.get("is_author_name"):
                                other_title = (other_dt.get("best_match") or {}).get("title", "")
                                if other_title and other_title.replace(" ", "") == verified_title_g.replace(" ", ""):
                                    decoder_has_separate_author = True
                                    break
                        if decoder_has_separate_author:
                            break

                if decoder_has_separate_author:
                    print(
                        f"[{_ts()}][{self.emoji}] 🔒 작가명 가드 스킵: '{verified_title_g}' "
                        f"— Decoder가 별도 작가명을 식별, 제목과 구분됨",
                        file=sys.stderr,
                    )
                else:
                    import re as _re_g
                    all_search_g = (ctx.search_results or []) + (verification_search or [])
                    # 🆕 패턴 개선: "제목 작가"가 아니라 "작가명: 제목" 같은 패턴만 매칭
                    # "작품제목 ... 작가 XXX" 패턴은 작품 정보 페이지이므로 오탐 방지
                    _esc_title = _re_g.escape(verified_title_g)
                    author_pattern = _re_g.compile(
                        r'작가명[.:\s]\s*' + _esc_title
                        + r'|작가[:\s]\s*' + _esc_title
                        + r'|글작가\s*' + _esc_title,
                        _re_g.IGNORECASE,
                    )
                    # "제목\s*작가" 패턴은 "작품 정보" 페이지의 "제목 ... 작가: XXX"와 혼동되므로 제거
                    for sr in all_search_g:
                        sr_text = (sr.get("title", "") + " " + (sr.get("content", "") or sr.get("snippet", "")))
                        if author_pattern.search(sr_text):
                            print(
                                f"[{_ts()}][{self.emoji}] 🛡️ 작가명 감지: '{verified_title_g}' "
                                f"→ 검색 결과에서 작가명으로 등장 → confidence 하향",
                                file=sys.stderr,
                            )
                            novel_id["confidence"] = "Low"
                            break

            # 🛡️ Decoder null + community_mention 시 confidence 하향
            # Decoder가 작품을 못 찾았는데 Verifier가 독자적으로 High 확신하면 위험
            if novel_id and novel_id.get("evidence_type") == "community_mention":
                decoder_has_title = any(
                    t.get("best_match", {}).get("title")
                    for t in decoder_result.get("decoded_terms", [])
                )
                if not decoder_has_title and novel_id.get("confidence") in ("High", "high"):
                    novel_id["confidence"] = "Low"
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ community_mention + Decoder null → "
                        f"confidence 하향: High → Low",
                        file=sys.stderr
                    )

            # 🛡️ 아이디어 D: Decoder null + Verifier 제목이 검색 결과에 없으면 환각
            # Decoder가 작품을 못 찾았는데 Verifier가 독자적으로 제목을 '발명'한 경우
            verified_title_d = (novel_id.get("official_novel_title")
                                or novel_id.get("official_title")) if novel_id else None
            if verified_title_d and ctx:
                decoder_has_title = any(
                    t.get("best_match", {}).get("title")
                    for t in decoder_result.get("decoded_terms", [])
                )
                if not decoder_has_title:
                    # 검색 결과에 이 제목이 정확히 존재하는지 확인
                    all_search = (ctx.search_results or []) + (verification_search or [])
                    title_in_search = False
                    title_norm = verified_title_d.replace(" ", "")
                    for sr in all_search:
                        sr_title = (sr.get("title", "") + " " + (sr.get("content", "") or sr.get("snippet", "")))
                        if title_norm in sr_title.replace(" ", ""):
                            title_in_search = True
                            break
                    if not title_in_search:
                        old_conf = novel_id.get("confidence", "Low")
                        novel_id["confidence"] = "Low"
                        print(
                            f"[{_ts()}][{self.emoji}] 🛡️ Decoder null + 검색에 '{verified_title_d}' 부재 → "
                            f"환각 의심, confidence: {old_conf} → Low",
                            file=sys.stderr,
                        )
            
            # 제안 2: Verifier의 신뢰도를 ctx에 저장
            if ctx:
                confidence_str = novel_id.get("confidence", "low")
                confidence_map = {"high": 0.95, "medium": 0.7, "low": 0.4}
                ctx.expert_confidence["verifier"] = confidence_map.get(confidence_str, 0.5)
            
            # ━━ 개선: evidence_type 3분류 + candidate evidence bucket + source trust ━━
            # evidence_type을 post_span / search_snippet / official_url로 분류
            if ctx and verification.get("is_relevant") and novel_id:
                verified_ev_title = (
                    novel_id.get("official_novel_title")
                    or novel_id.get("official_title")
                )
                grounding_ev = verification.get("grounding_check", {})
                anchor_ev = grounding_ev.get("anchor_found", "none")
                
                if verified_ev_title:
                    # 1) 본문 증거 분류 (post_span)
                    if anchor_ev in ("title_mention", "character_mention", 
                                     "plot_mention", "author_mention", "character_title_link"):
                        ctx.add_evidence_for_candidate(verified_ev_title, "post_span", {
                            "type": anchor_ev,
                            "source": "verifier_grounding",
                            "grounded": grounding_ev.get("decoder_grounded", False),
                        })
                    
                    # 2) 검색 증거 분류 (search_snippet) + 소스 신뢰도 가중치
                    all_search_ev = (ctx.search_results or []) + (verification_search or [])
                    title_norm_ev = verified_ev_title.replace(" ", "")
                    for sr in all_search_ev:
                        sr_text = (sr.get("title", "") + " " + (sr.get("content", "") or sr.get("snippet", "")))
                        sr_url = sr.get("url", "")
                        if title_norm_ev in sr_text.replace(" ", ""):
                            trust = ctx.score_source_trust(sr_url)
                            ctx.add_evidence_for_candidate(verified_ev_title, "search_snippet", {
                                "url": sr_url,
                                "snippet": sr_text[:200],
                                "trust_score": trust,
                            })
                            # 소스 신뢰도 기록
                            if sr_url:
                                ctx.source_trust_scores[sr_url] = trust
                            # 3) 공식 URL 분류 (official_url)
                            if trust >= 0.8:
                                ctx.add_evidence_for_candidate(verified_ev_title, "official_url", {
                                    "url": sr_url,
                                    "trust_score": trust,
                                })
                    
                    # heretic_url이 있으면 official_url로 등록
                    h_url = novel_id.get("heretic_url")
                    if h_url and ctx.score_source_trust(h_url) >= 0.8:
                        ctx.add_evidence_for_candidate(verified_ev_title, "official_url", {
                            "url": h_url,
                            "trust_score": ctx.score_source_trust(h_url),
                        })
                    
                    # 가설 상태머신 업데이트
                    ev_list = [anchor_ev]
                    if h_url:
                        ev_list.append(f"url:{h_url[:50]}")
                    ctx.update_hypothesis(
                        title=verified_ev_title,
                        confidence=novel_id.get("confidence", "low"),
                        evidence=ev_list,
                        step=ctx.iteration,
                    )
            
            # 🔥 본문 증거 교차검증 가드: LLM Verifier가 is_relevant=true로 판정했지만
            # grounding_check에서 decoder_grounded=false이면 코드 레벨 재검증
            if ctx and verification.get("is_relevant") and novel_id:
                grounding = verification.get("grounding_check", {})
                anchor_found = grounding.get("anchor_found", "none")
                decoder_grounded = grounding.get("decoder_grounded", True)
                
                if not decoder_grounded or anchor_found in ("search_only", "none"):
                    # Decoder도 본문 앵커를 못 찾았고, Verifier도 search_only/none인 경우
                    # → 코드 레벨에서 실제 본문을 확인하여 최종 판정
                    verified_title_bc = (
                        novel_id.get("official_novel_title")
                        or novel_id.get("official_title")
                    )
                    if verified_title_bc:
                        has_body_evidence = self._code_level_body_check(
                            post, comments, verified_title_bc, decoder_result
                        )
                        if not has_body_evidence:
                            old_conf = novel_id.get("confidence", "Low")
                            if old_conf in ("High", "high"):
                                novel_id["confidence"] = "Low"
                                print(
                                    f"[{_ts()}][{self.emoji}] 🛡️ 본문증거 교차검증: "
                                    f"'{verified_title_bc}' → grounding=false + "
                                    f"코드레벨 본문검증 실패 → confidence: {old_conf}→Low",
                                    file=sys.stderr,
                                )
                            elif old_conf in ("Medium", "medium"):
                                novel_id["confidence"] = "Low"
                                print(
                                    f"[{_ts()}][{self.emoji}] 🛡️ 본문증거 교차검증: "
                                    f"'{verified_title_bc}' → grounding=false + "
                                    f"코드레벨 본문검증 실패 → confidence: {old_conf}→Low",
                                    file=sys.stderr,
                                )
            
            # 제안 4: 불확실성 요인 수집
            if ctx and verification.get("is_relevant"):
                # 증거가 약한 경우 불확실성 누적
                evidence_type = novel_id.get("evidence_type", "")
                if evidence_type == "community_only":
                    ctx.uncertainty_sources.append("Verifier: 공식 플랫폼 증거 없음 (커뮤니티 포스트만)")
                
                grounding_check = verification.get("grounding_check", {})
                if not grounding_check.get("decoder_grounded", True):
                    ctx.uncertainty_sources.append("Verifier: 본문에 작품 직접 언급 없음 (제목만)")
                
                if confidence_str == "low":
                    ctx.uncertainty_sources.append(f"Verifier: 낮은 신뢰도 ({novel_id.get('notes', '')})")
            
            print(f"[{_ts()}][{self.emoji}] {self.name} 완료 ({elapsed:.1f}s): "
                    f"is_relevant={verification.get('is_relevant')}, "
                    f"title={novel_id.get('official_novel_title') or novel_id.get('official_title')}, "
                    f"confidence={novel_id.get('confidence')}", 
                    file=sys.stderr)
            
            # ⭐ suspected_titles 업데이트 (검증 결과 반영)
            if ctx:
                self._update_suspected_titles(result, ctx)
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[{_ts()}][{self.emoji}] {self.name} 오류 ({elapsed:.1f}s): {e}", file=sys.stderr)
            return self._fallback_result(gatekeeper_result, decoder_result, str(e))
    
    def _correct_title_from_evidence(self, llm_title: str, decoder_result: Dict[str, Any], search_results: List[Dict[str, Any]]) -> str:
        """
        🔥 LLM이 생성한 제목을 Decoder best_match + 검색 결과와 대조하여 교정
        예: '죽었다 깨어나도 수선' (LLM 환각) → '죽었다 깨어도 수선' (검색 결과 정확)
        """
        # 🔒 아이디어 B-1: LLM 제목이 Decoder best_match와 일치하면 교정 스킵
        # Decoder가 이미 올바르게 식별한 제목을 Verifier가 유사 이름의 다른 작품으로
        # 바꾸는 것을 방지 (빌어먹을 환생 → 따먹을 환생 문제)
        for term in decoder_result.get("decoded_terms", []):
            best = term.get("best_match", {})
            decoder_title = best.get("title")
            if decoder_title and decoder_title == llm_title:
                # LLM이 Decoder와 같은 답을 냈음 → 검색 결과로 교정하지 않음
                return llm_title

        # 1순위: Decoder의 best_match.title과 비교 (가장 신뢰)
        for term in decoder_result.get("decoded_terms", []):
            best = term.get("best_match", {})
            decoder_title = best.get("title")
            if decoder_title and decoder_title != llm_title:
                if self._is_similar_title(llm_title, decoder_title):
                    return decoder_title
        
        # 2순위: 검색 결과의 title 필드에서 공식 플랫폼 제목 비교
        official_platforms = OFFICIAL_PLATFORMS
        for sr in search_results:
            url = sr.get("url", "")
            if not any(p in url for p in official_platforms):
                continue
            sr_title = sr.get("title", "")
            # "웹소설로 꿈꾸는 세상! - 죽었다 깨어도 수선" → "죽었다 깨어도 수선"
            if " - " in sr_title:
                sr_title = sr_title.split(" - ")[-1].strip()
            import re
            sr_title = re.sub(r'\s*\(r\d+\s*판\)$', '', sr_title).strip()
            if sr_title and sr_title != llm_title and len(sr_title) >= 3:
                if self._is_similar_title(llm_title, sr_title):
                    return sr_title
        
        return llm_title
    
    def _is_similar_title(self, title_a: str, title_b: str) -> bool:
        """두 제목이 유사한지 (같은 작품의 표기 차이인지 판별)
        
        핵심: '빌어먹을 환생' vs '따먹을 환생'처럼 유사하지만
        완전히 다른 작품을 구분해야 함.
        """
        if abs(len(title_a) - len(title_b)) > 3:
            return False
        from difflib import SequenceMatcher
        ratio = SequenceMatcher(None, title_a, title_b).ratio()
        if ratio < 0.7:
            return False
        # 🔧 첫 어절(핵심어근)이 다르면 다른 작품으로 간주
        # '빌어먹을' vs '따먹을', 'K-문화의' vs '케데헌' 등
        first_a = title_a.split()[0] if title_a.split() else title_a
        first_b = title_b.split()[0] if title_b.split() else title_b
        if first_a != first_b and len(first_a) >= 2 and len(first_b) >= 2:
            # 첫 어절이 다르면 유사도 기준 상향 (0.85 이상 필요)
            if ratio < 0.85:
                return False
        return True
    
    def _guard_post_title_as_novel(
        self,
        novel_id: Dict[str, Any],
        verified_title: str,
        post_title: str,
        decoder_result: Dict[str, Any],
    ) -> None:
        """
        🚨 게시글 제목 도용 방지 (Arbiter P0-4의 선제 적용)
        
        LLM이 게시글 제목을 그대로 official_novel_title에 넣는 경우를 코드 레벨에서 차단.
        Decoder가 공식 플랫폼 URL 기반으로 확정한 제목이면 허용.
        """
        from difflib import SequenceMatcher
        norm_post = post_title.replace(" ", "")
        norm_title = verified_title.replace(" ", "")
        sim = SequenceMatcher(None, norm_post, norm_title).ratio()
        is_substring = norm_title in norm_post or norm_post in norm_title
        
        if not ((sim >= 0.7 or is_substring) and len(verified_title) > 3):
            return  # 유사하지 않으면 통과
        
        # 🔧 축약어 포함 패턴 예외: 제목이 게시글 제목의 작은 부분(접두사 등)일 때는 도용이 아님
        # 예: "즉사무림" ⊂ "즉사무림이유백 미래가 벌써 보이네" → 축약어+캐릭터명 합성 (정상)
        # 도용 = 게시글 제목 전체를 거의 그대로 소설 제목으로 넣은 경우
        if is_substring and norm_title in norm_post:
            title_ratio = len(norm_title) / max(len(norm_post), 1)
            if title_ratio < 0.6:
                # 소설 제목이 게시글 제목의 60% 미만 → 축약어로서 포함된 것 (도용 아님)
                print(
                    f"[{_ts()}][{self.emoji}] ✅ 축약어 포함 허용: "
                    f"'{verified_title}' ⊂ '{post_title}' "
                    f"(title_ratio={title_ratio:.2f} < 0.6, sim={sim:.2f})",
                    file=sys.stderr,
                )
                return
        
        # Decoder가 공식 플랫폼 URL 기반으로 확정한 제목인지 확인
        decoder_has_platform_url = False
        for term in decoder_result.get("decoded_terms", []):
            best = term.get("best_match") or {}
            if best and best.get("title") == verified_title:
                grounding = term.get("grounding") or {}
                if grounding.get("is_grounded") and grounding.get("anchor_type") in (
                    "platform_url", "official_api",
                ):
                    decoder_has_platform_url = True
                    break
                for cand in term.get("candidates") or []:
                    if cand.get("official_novel_title") == verified_title and cand.get("platform"):
                        decoder_has_platform_url = True
                        break
        
        if decoder_has_platform_url:
            return  # Decoder가 플랫폼 기반 확정 → 유효
        
        # 도용 감지 → null 강제
        print(
            f"[{_ts()}][{self.emoji}] 🚨 게시글 제목 도용 차단: "
            f"official_title='{verified_title}' ≈ post_title='{post_title}' "
            f"(sim={sim:.2f}) → null 강제",
            file=sys.stderr
        )
        novel_id["official_novel_title"] = None
        if "official_title" in novel_id:
            novel_id["official_title"] = None
        novel_id["confidence"] = "Low"
    
    def _update_suspected_titles(self, result: Dict[str, Any], ctx: Any) -> None:
        """
        ⭐ suspected_titles 업데이트 (검증 결과 반영)
        - 확인된 작품: status → 'verified', confidence ↑
        - 불확실한 작품: 제거 또는 confidence ↓
        """
        verification = result.get("verification_result", {})
        novel_id = verification.get("novel_identity") or {}
        
        verified_title = novel_id.get("official_novel_title") or novel_id.get("official_title")
        confidence = novel_id.get("confidence", "low")
        is_relevant = verification.get("is_relevant", False)
        
        if not hasattr(ctx, "suspected_titles") or not ctx.suspected_titles:
            return
        
        updated = []
        for st in ctx.suspected_titles:
            title = st.get("title", "")
            
            if is_relevant and verified_title and title == verified_title:
                # 검증 확인: status 업그레이드
                st["status"] = "verified"
                # confidence에 따라 차등 적용 (low면 기존 값 유지, 상향하지 않음)
                if confidence == "high":
                    st["confidence"] = 0.9
                elif confidence in ("medium", "Medium"):
                    st["confidence"] = 0.7
                else:
                    # Low confidence: 기존 값에서 소폭 하향 (Verifier가 확신 없음)
                    st["confidence"] = max(0.3, st.get("confidence", 0.5) - 0.1)
                st["verified_by"] = "verifier"
                updated.append(st)
            elif is_relevant and confidence in ("high", "medium"):
                # 다른 작품이 확인됨: 이 후보는 유지하되 confidence 낮춤
                st["confidence"] = max(0.2, st.get("confidence", 0.5) - 0.2)
                updated.append(st)
            else:
                # 관련 없음으로 판정: confidence 낮춤 (제거하지는 않음)
                st["confidence"] = max(0.1, st.get("confidence", 0.5) - 0.3)
                if st["confidence"] >= 0.2:  # 너무 낮으면 제거
                    updated.append(st)
        
        # 새로 확인된 작품 추가
        if is_relevant and verified_title:
            if not any(s.get("title") == verified_title for s in updated):
                # �️ 아이디어 H: Decoder가 작가명으로 식별한 이름은 suspected_titles에 추가 차단
                is_author_name_in_decoder = False
                if ctx and hasattr(ctx, 'expert_outputs'):
                    decoder_out_h = ctx.expert_outputs.get("decoder") or {}
                    for term in decoder_out_h.get("decoded_terms", []):
                        if term.get("is_author_name"):
                            author_info = term.get("author_info") or {}
                            author_name = author_info.get("name", "")
                            original = term.get("original", "")
                            if verified_title in (author_name, original):
                                is_author_name_in_decoder = True
                                break
                if is_author_name_in_decoder:
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ 작가명 차단: "
                        f"'{verified_title}'은 Decoder가 작가명으로 식별 → suspected_titles 추가 스킵",
                        file=sys.stderr,
                    )
                    # 작가명은 suspected_titles에 추가하지 않음
                    ctx.suspected_titles = sorted(updated, key=lambda x: x.get("confidence", 0), reverse=True)[:5]
                    return

                # �🔧 Phase26-B: Decoder 최종 결과가 null이면 Verifier 독자 추가의 confidence 제한
                decoder_final_null = False
                if ctx and hasattr(ctx, 'expert_outputs'):
                    decoder_out = ctx.expert_outputs.get("decoder") or {}
                    decoder_overall = decoder_out.get("overall_confidence", "")
                    decoder_has_title = any(
                        t.get("best_match", {}).get("title")
                        for t in decoder_out.get("decoded_terms", [])
                    )
                    if decoder_overall in ("none", "low") and not decoder_has_title:
                        decoder_final_null = True
                
                new_conf = 0.9 if confidence == "high" else 0.7
                new_status = "verified"
                if decoder_final_null:
                    new_conf = min(new_conf, 0.4)  # Decoder null이면 최대 0.4
                    new_status = "unconfirmed"
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ Decoder-null 가드: "
                        f"Decoder 최종=null → Verifier 독자 추가 '{verified_title}' conf={new_conf} (제한됨)",
                        file=sys.stderr
                    )
                
                updated.append({
                    "title": verified_title,
                    "confidence": new_conf,
                    "source_expert": "verifier",
                    "status": new_status,
                })
        
        ctx.suspected_titles = sorted(updated, key=lambda x: x.get("confidence", 0), reverse=True)[:5]
        print(f"[{_ts()}][{self.emoji}] 📋 suspected_titles 업데이트: {len(ctx.suspected_titles)}건", file=sys.stderr)
        for i, st in enumerate(ctx.suspected_titles, 1):
            title = st.get('title', 'N/A')
            conf = st.get('confidence', 'N/A')
            source = st.get('source_expert', 'unknown')
            print(f"[{_ts()}][{self.emoji}]    [{i}] {title} (conf={conf}, from={source})", file=sys.stderr)
    
    def _summarize_gatekeeper(self, gk: Dict[str, Any]) -> Dict[str, Any]:
        """Gatekeeper 결과 요약 (토큰 절약)"""
        if not gk:
            return {}
        
        entities = gk.get("detected_entities") or {}
        possible_titles = entities.get("possible_titles") or []
        possible_authors = entities.get("possible_authors") or []
        key_terms = gk.get("key_terms") or []
        
        return {
            "is_noise": gk.get("is_noise"),
            "post_type": gk.get("post_type"),
            "possible_titles": possible_titles[:3] if possible_titles else [],
            "possible_authors": possible_authors[:2] if possible_authors else [],
            "key_terms": key_terms[:5] if key_terms else [],
            "confidence": gk.get("confidence"),
        }
    
    def _summarize_decoder(self, dc: Dict[str, Any]) -> Dict[str, Any]:
        """Decoder 결과 요약 (토큰 절약)"""
        if not dc:
            return {}
        
        decoded = dc.get("decoded_terms") or []
        summary_terms = []
        blocked_archetypes = []
        for term in decoded[:3]:  # 최대 3개 용어만
            if not term:
                continue
            best = term.get("best_match") or {}
            original = term.get("original", "")
            entry = {
                "original": original,
                "title": best.get("title"),
                "confidence": best.get("confidence"),
            }
            # 작가명 식별 정보 전달
            if term.get("is_author_name"):
                ai = term.get("author_info") or {}
                entry["is_author_name"] = True
                entry["author_name"] = ai.get("name") or original
            # 아키타입 차단 정보 전달 (Verifier가 재도입하지 않도록)
            if (original.strip() in GENRE_ARCHETYPE_TERMS
                    and not best.get("title")
                    and best.get("confidence") in ("none", None)):
                entry["archetype_blocked"] = True
                blocked_archetypes.append(original.strip())
            summary_terms.append(entry)
        
        notes = dc.get("notes")
        summary = {
            "decoded_terms": summary_terms,
            "overall_confidence": dc.get("overall_confidence"),
            "needs_verification": dc.get("needs_verification"),
            "notes": notes[:200] if notes else None,
        }
        
        # 아키타입 차단 경고를 명시적으로 추가 (LLM 프롬프트에 전달)
        if blocked_archetypes:
            summary["archetype_warning"] = (
                f"⚠️ 다음 용어는 장르 아키타입으로 판정되어 소설 제목이 아닙니다: "
                f"{blocked_archetypes}. 이 용어가 포함된 제목을 식별하지 마세요."
            )
        
        return summary
    
    def _build_post_json(self, post: Dict[str, Any], comments: List[str]) -> Dict[str, Any]:
        """Build simplified post JSON."""
        content_texts = []
        for block in post.get("content_blocks", []):
            if isinstance(block, dict) and block.get("text"):
                content_texts.append(block["text"])
            elif isinstance(block, str):
                content_texts.append(block)
        
        return {
            "post_id": post.get("post_id"),
            "title": post.get("title", ""),
            "author": post.get("author", ""),
            "content": content_texts,
            "comments": comments[:10],
        }
    
    def _call_llm(self, user_prompt: str) -> Dict[str, Any]:
        """Call LLM and parse JSON response."""
        messages = [
            {"role": "system", "content": VERIFIER_SYSTEM},
            {"role": "user", "content": user_prompt},
        ]
        
        response_text = self.llm._stream_chat_http(
            messages=messages,
            tag="verifier",
            use_grammar=True,
        )
        
        return self._parse_json_response(response_text)
    
    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Extract and parse JSON from response, removing <think> blocks."""
        return parse_json_with_think_removal(text)
    
    def _fallback_result(
        self, 
        gatekeeper: Dict[str, Any], 
        decoder: Dict[str, Any],
        error: str
    ) -> Dict[str, Any]:
        """Build fallback result from previous stages."""
        # None 체크
        gatekeeper = gatekeeper or {}
        decoder = decoder or {}
        
        # Try to use decoder's best candidate
        best_title = None
        best_confidence = "None"
        
        for term in decoder.get("decoded_terms", []):
            best = term.get("best_match", {})
            if best.get("title"):
                best_title = best["title"]
                best_confidence = "Low"  # Downgrade without verification
                break
        
        is_noise = gatekeeper.get("is_noise", False)
        
        # CRITICAL: 검증 오류 발생 시 is_relevant=False (검증 실패)
        # JSON 파싱 에러 등으로 검증 자체가 불가능하므로 False로 처리
        return {
            "verification_result": {
                "is_relevant": False,  # 검증 실패 → False
                "is_novel_discussion": False,
                "novel_identity": None,  # 검증 실패 시 null
                "author_info": None,
                "rejection_reason": f"Verifier 검증 오류: {error}",
                "evidence_chain": [],
                "slang_insight": None,
                "inference": gatekeeper.get("inference"),
            },
            "final_confidence": "none",
            "reason": f"검증 오류로 인한 폴백 결과: {error}",
        }
    
    def get_final_identity(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract final identity from result."""
        verification = result.get("verification_result", {})
        return {
            "is_relevant": verification.get("is_relevant", False),
            "novel_identity": verification.get("novel_identity"),
            "evidence": verification.get("evidence_chain"),
            "slang_insight": verification.get("slang_insight"),
            "inference": verification.get("inference"),
            "reason": verification.get("reason") or result.get("reason"),
        }
    
    def is_confirmed(self, result: Dict[str, Any]) -> bool:
        """Check if a title was confirmed."""
        verification = result.get("verification_result", {})
        novel_id = verification.get("novel_identity") or {}
        official_title = novel_id.get("official_novel_title") or novel_id.get("official_title")
        return (
            official_title is not None
            and novel_id.get("confidence") in ("Max", "High", "Medium")
        )

    def _code_level_body_check(
        self,
        post: Dict[str, Any],
        comments: List[str],
        title: str,
        decoder_result: Dict[str, Any],
    ) -> bool:
        """
        🔥 코드 레벨 본문 증거 확인
        
        LLM의 grounding_check 결과가 false일 때, 코드 레벨에서 
        본문/댓글에 실제로 작품 관련 증거가 있는지 확인.
        
        Returns:
            True: 본문에 작품 관련 증거가 하나라도 있음
            False: 작품 관련 증거 없음 → FP 가능성 높음
        """
        # 게시글 전체 텍스트 수집
        post_title = post.get("title", "")
        body_parts = []
        for block in post.get("content_blocks", []):
            if isinstance(block, dict) and block.get("text"):
                body_parts.append(block["text"])
        post_body = " ".join(body_parts)
        comments_text = " ".join(comments or [])
        
        full_text = f"{post_title} {post_body} {comments_text}"
        full_text_norm = full_text.lower().replace(" ", "")
        
        if not full_text_norm:
            return False
        
        # 1) 제목 자체가 본문에 포함 (정식 제목 또는 부분)
        title_norm = title.lower().replace(" ", "")
        if title_norm in full_text_norm:
            return True
        
        # 2) 제목의 핵심 단어(2글자 이상)가 본문에 2개 이상 있는지
        title_words = [w for w in title.split() if len(w) >= 2]
        if title_words:
            word_hits = sum(
                1 for w in title_words
                if w.lower() in full_text.lower()
            )
            if word_hits >= 2:
                return True
        
        # 3) Decoder의 original term이 본문에 명시적으로 있는지 
        #    (약어가 명확히 존재하면 의도적 언급 가능성)
        for term in decoder_result.get("decoded_terms", []):
            original = (term.get("original") or "").strip()
            best = term.get("best_match") or {}
            if best.get("title") == title and original:
                orig_norm = original.lower().replace(" ", "")
                # 원본 약어가 제목에 포함 → 약어로 작품 언급 중
                if orig_norm in full_text_norm and len(orig_norm) >= 3:
                    # 추가 확인: 본문에 작품 토론 문맥이 있는지
                    # (줄거리, 캐릭터, 회차 관련 키워드)
                    work_context_keywords = [
                        # 서사/줄거리
                        "주인공", "캐릭터", "회차", "챕터", "전개", "결말",
                        "스포", "완결", "연재", "작가가", "후기", "리뷰",
                        "주인공이", "히로인", "빌런", "멘탈", "각성",
                        "표지", "변경", "휴재", "복귀", "신작",
                        "몇화", "몇회", "막화", "최신화",
                        # 독자 반응/감상
                        "읽었", "봤는데", "재밌", "꿀잼", "노잼", "감상",
                        "불쌍", "슬프", "눈물", "울컥", "ㅠㅠ", "ㅜㅜ",
                        "무섭", "소름", "충격", "반전", "감동",
                        # 캐릭터/사건 토론
                        "죽는", "죽었", "죽일", "죽이", "죽음",
                        "살아", "살렸", "살릴", "배신",
                        "가족", "형제", "부모", "사부",
                        "싸움", "대결", "전투", "승리", "패배",
                        "성장", "수련", "깨달",
                        # 욕설/강한 감정 (커뮤니티 표현)
                        "씹", "좆", "미쳤", "대박", "쩐다", "개쩔",
                        # 유료화/플랫폼 관련
                        "유료", "무료", "정주행", "정가",
                    ]
                    has_context = any(
                        kw in full_text
                        for kw in work_context_keywords
                    )
                    if has_context:
                        return True

                    # 🆕 추가: 포스트 제목에 약어가 있고 본문에 이모티콘/감정 표현이 있으면 OK
                    # ("즉사무림 은영이 너무 불쌍해" → 제목에 약어 + 감정 표현)
                    if orig_norm in post_title.lower().replace(" ", ""):
                        # 포스트 제목에 약어가 있으면 의도적 작품 언급
                        return True
        
        # 3.5) Decoder의 다른 term이 동일 제목에 high score로 매칭되어 있으면
        #      이 작품에 대한 토론이 확실 → 증거 인정
        high_score_terms = []
        for term in decoder_result.get("decoded_terms", []):
            best = term.get("best_match") or {}
            if best.get("title") == title and best.get("confidence") in ("high", "max"):
                high_score_terms.append(term.get("original", ""))
        if high_score_terms:
            # 같은 제목에 대해 다른 term이 high confidence → 작품 토론 확실
            return True

        # 4) 댓글에 작품 관련 URL이 있는지
        import re
        url_pattern = re.compile(
            r'(novelpia\.com|munpia\.com|namu\.wiki|kakaopage\.com|series\.naver\.com)'
        )
        if url_pattern.search(full_text):
            return True
        
        # 5) Decoder가 식별한 작가명이 본문/댓글에 있는지
        #    → 5종 본문 증거 중 "작가명 직접 언급"에 해당
        for term in decoder_result.get("decoded_terms", []):
            if not isinstance(term, dict):
                continue
            if term.get("is_author_name"):
                author_name = (term.get("original") or "").strip()
                if author_name and len(author_name) >= 2:
                    # 게시글 본문+댓글에 작가명이 있으면 증거로 인정
                    if author_name in full_text:
                        return True
                    # author_info에서도 확인
                    author_info = term.get("author_info") or {}
                    confirmed_name = (author_info.get("name") or "").strip()
                    if confirmed_name and len(confirmed_name) >= 2 and confirmed_name in full_text:
                        return True
        
        return False
