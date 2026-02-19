"""
Stage 1: Gatekeeper Expert - 커뮤니티 문화 분석관
First-line filter for noise detection and entity extraction.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any, Dict, List, Optional

from .prompts import (
    GATEKEEPER_SYSTEM,
    GATEKEEPER_PROMPT,
    build_gatekeeper_system_prompt,
)
from .utils import parse_json_with_think_removal, _ts


class GatekeeperExpert:
    """
    🎭 Gatekeeper - Community Culture Analyst
    
    Responsibilities:
    - Classify posts (noise, work discussion, recommendation, etc.)
    - Detect entities (titles, authors, characters)
    - Suggest search strategies
    - Combine LLM analysis + Kiwi morphological analysis
    """
    
    def __init__(self, llm_client):
        self.llm = llm_client
        self.name = "Gatekeeper"
        self.emoji = "🎭"
        
        # Initialize Kiwi morphological analyzer
        try:
            from kiwipiepy import Kiwi
            self.kiwi = Kiwi()
            self.use_kiwi = True
        except ImportError:
            self.kiwi = None
            self.use_kiwi = False
    
    def analyze(
        self,
        post: Dict[str, Any],
        comments: List[str],
        rules_config: Dict[str, Any],
        ctx: Optional[Any] = None,  # ConversationContext 추가
    ) -> Dict[str, Any]:
        """
        Analyze a post and return classification + entities + search requests.
        
        Args:
            post: Post data (title, content, author, etc.)
            comments: List of comment texts
            rules_config: Configuration with noise_terms, slang_dictionary, etc.
            
        Returns:
            GatekeeperResult with is_noise, post_type, entities, search_requests
        """
        start_time = time.time()
        
        # None 체크
        post = post or {}
        comments = comments or []
        rules_config = rules_config or {}
        
        # Build post JSON for prompt
        post_json = self._build_post_json(post, comments)
        
        # Format prompt
        user_prompt = GATEKEEPER_PROMPT.format(
            post_json=json.dumps(post_json, ensure_ascii=False, indent=2)
        )
        
        print(f"[{_ts()}][{self.emoji}] {self.name} 분석 시작: post_id={post.get('post_id')}", file=sys.stderr)
        
        try:
            # Call LLM
            result = self._call_llm(
                user_prompt,
                post=post,
                comments=comments,
                ctx=ctx,
            )
            
            # Enhance with Kiwi morphological analysis
            if self.use_kiwi:
                title = post.get("title", "")
                kiwi_entities = self._extract_morphemes_kiwi(title)
                result = self._merge_entities(result, kiwi_entities)
            
            # 🚨 코드 레벨 보강: 댓글에서 제목 답변 후보 추출
            result = self._postprocess_comment_titles(result, comments)
            
            # 🔥 이미지 전용 게시글 코드 레벨 감지
            result = self._detect_image_only_post(result, post)
            
            # 🆕 장르 접두사 태그 파싱 (TS), BL) 등)
            result = self._parse_genre_prefix_tags(result, post)
            
            # 🆕 회차 번호 감지 (N화/N회/N일차 → 연재 작품 앵커)
            result = self._detect_episode_numbers(result, post, comments)
            
            # 🆕 제목 마스킹 감지 (ㅁㅁ, ■■ → 해독 불가 플래그)
            result = self._detect_title_masking(result, post)
            
            # 🆕 Phase 11j: 장르 토론 / 추천 요청 코드 레벨 감지
            result = self._detect_genre_discussion_patterns(result, post, comments)
            
            # 🆕 다작/순서 질문 감지 (작가 전작 순서, A->B->C 체인 등)
            result = self._detect_multi_work_order_patterns(result, post, comments)
            
            elapsed = time.time() - start_time
            
            # 제안 2: Gatekeeper의 신뢰도를 ctx에 저장
            if ctx:
                confidence_str = result.get("confidence", "medium")
                confidence_map = {"high": 0.8, "medium": 0.6, "low": 0.4}
                ctx.expert_confidence["gatekeeper"] = confidence_map.get(confidence_str, 0.6)
            
            print(f"[{_ts()}][{self.emoji}] {self.name} 완료 ({elapsed:.1f}s): "
                  f"is_noise={result.get('is_noise')}, post_type={result.get('post_type')}", 
                  file=sys.stderr)
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[{_ts()}][{self.emoji}] {self.name} 오류 ({elapsed:.1f}s): {e}", file=sys.stderr)
            # Return safe default
            return self._default_result(str(e))
    
    def _build_post_json(self, post: Dict[str, Any], comments: List[str]) -> Dict[str, Any]:
        """Build simplified post JSON for the prompt."""
        # Extract text content
        content_texts = []
        image_count = 0
        total_blocks = 0
        for block in post.get("content_blocks", []):
            total_blocks += 1
            if isinstance(block, dict):
                if block.get("text"):
                    content_texts.append(block["text"])
                elif block.get("type") == "image" or block.get("src"):
                    image_count += 1
            elif isinstance(block, str):
                content_texts.append(block)
        
        result = {
            "post_id": post.get("post_id"),
            "title": post.get("title", ""),
            "author": post.get("author", ""),
            "content": content_texts,
            "comments": comments[:10],  # Limit comments
        }
        
        # 🔥 이미지 전용 게시글 정보 추가
        if total_blocks > 0:
            result["_content_stats"] = {
                "total_blocks": total_blocks,
                "image_blocks": image_count,
                "text_blocks": total_blocks - image_count,
                "is_image_dominant": image_count > 0 and len(content_texts) == 0,
            }
        
        return result
    
    def _call_llm(
        self,
        user_prompt: str,
        *,
        post: Optional[Dict[str, Any]] = None,
        comments: Optional[List[str]] = None,
        ctx: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Call LLM and parse JSON response."""
        system_content = build_gatekeeper_system_prompt(
            GATEKEEPER_SYSTEM,
            post=post,
            comments=comments,
            ctx=ctx,
        )
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt},
        ]
        
        # Use streaming for progress visibility
        response_text = self.llm._stream_chat_http(
            messages=messages,
            tag="gatekeeper",
            use_grammar=True,
        )
        
        # Parse JSON
        return self._parse_json_response(response_text)
    
    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Extract and parse JSON from response, removing <think> blocks."""
        return parse_json_with_think_removal(text)
    
    def _default_result(self, error: str) -> Dict[str, Any]:
        """Return default result on error."""
        return {
            "is_noise": False,
            "noise_reason": None,
            "post_type": "unknown",
            "detected_entities": {
                "possible_titles": [],
                "possible_authors": [],
                "possible_characters": [],
                "platforms_mentioned": [],
            },
            "key_terms": [],
            "context_clues": {
                "has_url_in_comments": False,
                "has_specific_names": False,
                "is_asking_recommendation": False,
                "is_spoiler_discussion": False,
            },
            "search_requests": [],
            "confidence": "low",
            "notes": f"분석 오류: {error}",
        }
    
    def should_skip_further_analysis(self, result: Dict[str, Any]) -> bool:
        """Check if post should be skipped (is noise)."""
    
    def _extract_morphemes_kiwi(self, title: str) -> List[str]:
        """
        Extract possible title candidates using Kiwi morphological analysis.
        
        Strategy:
        1. Extract all nouns (NNG, NNP) - common/proper nouns
        2. Extract compound nouns (NNB) - bound nouns
        3. Extract all 2+ character segments (with linguistic filtering)
        4. Include original text segments
        
        Noise filtering:
        - n-gram segments containing verbal morphemes are excluded
        - Only noun-dominant segments pass (valid title candidates)
        
        Args:
            title: Post title to analyze
            
        Returns:
            List of possible title strings
        """
        if not self.kiwi or not title:
            return []
        
        candidates = set()
        
        try:
            # Tokenize with Kiwi
            result = self.kiwi.tokenize(title)
            
            # Extract nouns (명사)
            for token in result:
                form = token.form
                tag = token.tag
                
                # Include all noun types
                if tag in ('NNG', 'NNP', 'NNB'):  # 일반명사, 고유명사, 의존명사
                    if len(form) >= 2:  # 2글자 이상
                        candidates.add(form)
                
                # Include foreign words (SL, SH, SN)
                elif tag in ('SL', 'SH', 'SN'):  # 외국어, 한자, 숫자
                    if len(form) >= 1:  # 1글자 이상 (영문 약어 포함)
                        candidates.add(form)
            
            # Extract compound patterns (복합 명사 패턴)
            # Split title into all possible 2+ character segments
            # 🆕 OPT: 공백/구두점/조사만으로 구성된 세그먼트는 제외
            _JOSA_CHARS = set('을를이가는은의에서와과도만으로부터')
            raw_segments: list[str] = []
            for i in range(len(title)):
                for j in range(i + 2, min(i + 6, len(title) + 1)):  # 2-5글자
                    segment = title[i:j]
                    if not segment:
                        continue
                    # 공백/구두점 포함 세그먼트 스킵
                    if any(c in segment for c in ' \t)(!?.,;:'):
                        continue
                    # 조사만으로 구성된 세그먼트 스킵
                    if all(c in _JOSA_CHARS for c in segment):
                        continue
                    # 한글 2음절 이상 연속 포함 요구
                    korean_count = sum(1 for c in segment if ord('가') <= ord(c) <= ord('힣'))
                    if korean_count < 2:
                        continue
                    raw_segments.append(segment)
            
            # ── n-gram 노이즈 필터: Kiwi 형태소 분석으로 검증 ──
            # 동사어미(EC/EF/EP), 형용사어간(VA), 접속부사(MAJ) 등이
            # 포함된 세그먼트는 유효한 제목 후보가 아님
            _VERBAL_TAGS = {
                'VV', 'VA', 'VX', 'VCP', 'VCN',   # 동사/형용사 어간
                'EC', 'EF', 'EP', 'ETN', 'ETM',    # 어미류
                'MAJ',                              # 접속부사 (하지만, 그런데)
            }
            for seg in raw_segments:
                # 이미 Kiwi 명사 후보에 있으면 그대로 통과
                if seg in candidates:
                    continue
                try:
                    seg_tokens = self.kiwi.tokenize(seg)
                    # 세그먼트 내 형태소 태그 확인
                    seg_tags = {t.tag for t in seg_tokens}
                    has_verbal = bool(seg_tags & _VERBAL_TAGS)
                    has_noun = bool(seg_tags & {'NNG', 'NNP', 'NNB', 'SL', 'SH'})
                    # 동사/형용사 어미가 있으면 → 노이즈 (제외)
                    # 단, 모든 형태소가 명사류이면 → 유효 (통과)
                    if has_verbal:
                        continue
                    if has_noun:
                        candidates.add(seg)
                except Exception:
                    # Kiwi 오류 시 보수적으로 포함
                    candidates.add(seg)
        
        except Exception as e:
            print(f"[{_ts()}][{self.emoji}] Kiwi 분석 오류: {e}", file=sys.stderr)
        
        return sorted(list(candidates), key=len, reverse=True)  # 긴 것부터
    
    def _merge_entities(
        self, 
        llm_result: Dict[str, Any], 
        kiwi_entities: List[str]
    ) -> Dict[str, Any]:
        """
        Merge LLM-detected entities with Kiwi-detected entities.
        
        Strategy:
        - Keep all LLM entities (they have context)
        - Add Kiwi entities that LLM missed
        - Deduplicate
        
        Args:
            llm_result: Result from LLM analysis
            kiwi_entities: Entities from Kiwi morphological analysis
            
        Returns:
            Merged result
        """
        detected = llm_result.get("detected_entities") or {}
        llm_titles = detected.get("possible_titles") or []
        
        # Combine and deduplicate (preserve order: LLM first, then Kiwi)
        combined = list(llm_titles)  # Start with LLM results
        
        for entity in kiwi_entities:
            if entity not in combined:
                combined.append(entity)
        
        # 🆕 커뮤니티 접두어 패턴 정제: "소신발언)", "스포)" 등 제거
        from ..rules import COMMUNITY_PREFIX_PATTERNS
        cleaned = []
        for title in combined:
            if not isinstance(title, str):
                cleaned.append(title)
                continue
            _t = title.strip()
            _stripped = _t
            for prefix in COMMUNITY_PREFIX_PATTERNS:
                if _t.startswith(prefix):
                    _stripped = _t[len(prefix):].strip()
                    break
            # 접두어 제거 후 남은 부분이 2자 이상이면 교체, 아니면 원래 제목 유지
            if _stripped and len(_stripped) >= 2 and _stripped != _t:
                if _stripped not in cleaned:
                    cleaned.append(_stripped)
                print(
                    f"[{_ts()}][{self.emoji}] 🏷️ 커뮤니티 접두어 제거: '{_t}' → '{_stripped}'",
                    file=sys.stderr,
                )
            else:
                cleaned.append(_t)
        combined = cleaned
        
        # Update result
        detected["possible_titles"] = combined
        llm_result["detected_entities"] = detected
        
        return llm_result
    
    # ── 댓글 제목 후보 추출 ───────────────────────
    
    def _postprocess_comment_titles(
        self,
        result: Dict[str, Any],
        comments: List[str],
    ) -> Dict[str, Any]:
        """
        코드 레벨 후처리: 댓글 중 제목 답변으로 보이는 것을 possible_titles에 추가.
        
        플랫폼 판별은 하지 않음 — 그것은 검색 결과를 가진 후속 단계에서 처리.
        여기서는 순수하게 "댓글이 제목을 답변한 것 같은가"만 판단.
        """
        detected = result.get("detected_entities") or {}
        possible_titles = detected.get("possible_titles") or []
        
        comment_title_candidates = []
        
        for comment in (comments or []):
            raw = (comment or "").strip()
            if not raw:
                continue

            # 멀티라인 댓글은 "첫 줄=제목, 다음 줄=설명" 패턴이 흔하다.
            # 예) "Harry Potter: Ero World\n200화 정도 연재..."
            candidate_lines = [raw]
            if "\n" in raw:
                candidate_lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]

            for stripped in candidate_lines:
                # 구조적으로 제목 후보가 될 수 있는지 먼저 검사
                if not self._is_title_like_surface(stripped):
                    continue

                # 문장 행위 분류(질문/요청/설명/답변)
                # 질문·요청·설명은 제목 후보에서 제외하고, 답변형만 채택
                speech_act = self._classify_comment_speech_act(stripped)
                if speech_act != "answer_like":
                    continue

                comment_title_candidates.append(stripped)

        # 동일 댓글/중복 줄 제거
        if comment_title_candidates:
            _deduped = []
            _seen = set()
            for ct in comment_title_candidates:
                key = ct.replace(" ", "").lower()
                if key in _seen:
                    continue
                _seen.add(key)
                _deduped.append(ct)
            comment_title_candidates = _deduped
        
        # 댓글 제목 후보를 possible_titles에 추가
        for ct in comment_title_candidates:
            if ct not in possible_titles:
                possible_titles.append(ct)
        
        if comment_title_candidates:
            print(
                f"[{_ts()}][{self.emoji}] 📝 댓글 제목 후보 추출: {comment_title_candidates}",
                file=sys.stderr,
            )
        
        detected["possible_titles"] = possible_titles
        result["detected_entities"] = detected
        
        return result

    # ── 다작/순서 질문 감지 ──────────────────────────────

    def _detect_multi_work_order_patterns(
        self,
        result: Dict[str, Any],
        post: Dict[str, Any],
        comments: List[str],
    ) -> Dict[str, Any]:
        """
        다작/순서 질문(작가 전작 소비 순서, 작품 체인 나열)을 일반 패턴으로 감지.

        하드코딩된 특정 작품명이 아니라, 담화 구조 신호를 사용한다:
        - 순서/입문/정주행 질문 키워드
        - 화살표 체인(->, →)
        - 리스트형 나열(쉼표, 슬래시 등)
        - 작가 중심 질문(작가명/글 다 본 사람, 전작)
        """
        import re

        title = str(post.get("title") or "")
        body_texts: List[str] = []
        for block in post.get("content_blocks", []) or []:
            if isinstance(block, dict):
                txt = block.get("text")
                if txt:
                    body_texts.append(str(txt))
            elif isinstance(block, str):
                body_texts.append(block)

        comment_texts = [c for c in (comments or []) if isinstance(c, str)]
        merged = " ".join([title] + body_texts + comment_texts)
        merged_norm = merged.replace(" ", "")

        order_keywords = (
            "뭐부터", "순서", "시간순", "읽는순", "보는순", "정주행",
            "입문", "나머지", "먼저", "다본", "다 보", "전작", "작품순",
        )
        order_hits = [kw for kw in order_keywords if kw in merged_norm]

        has_question_form = ("?" in merged) or any(
            q in merged for q in ("어떻게", "뭐부터", "뭘", "어느거", "추천")
        )
        has_arrow_chain = ("->" in merged) or ("→" in merged)

        # 작가 중심 담화: "OOO 글 다 본사람", "작가 전작" 류
        has_author_focus = bool(
            re.search(r"(작가|글)\s*(다\s*본|전작|작품|순서)", title)
            or re.search(r"([가-힣A-Za-z0-9]{2,12})\s*글\s*다\s*본", title)
            or ("작가" in merged and "전작" in merged)
        )

        # 리스트형 작품 나열(구분자 포함 라인)
        list_like_count = 0
        delimiter_pat = re.compile(r"(,|/|\||·|→|->)")
        token_pat = re.compile(r"[가-힣A-Za-z0-9]{2,20}")
        for line in ([title] + body_texts + comment_texts)[:40]:
            if not line or not delimiter_pat.search(line):
                continue
            token_count = len(token_pat.findall(line))
            if token_count >= 3:
                list_like_count += 1

        is_multi_order = bool(
            order_hits
            and (has_arrow_chain or list_like_count >= 1 or has_author_focus)
            and (has_question_form or "나머지" in merged_norm or "다본" in merged_norm)
        )

        if not is_multi_order:
            return result

        context_clues = result.get("context_clues") or {}
        context_clues["multi_work_order_detected"] = True
        context_clues["order_keywords_found"] = order_hits[:6]
        context_clues["has_arrow_chain"] = has_arrow_chain
        context_clues["has_author_focus"] = has_author_focus
        context_clues["list_like_count"] = list_like_count
        context_clues["should_avoid_single_title_fixation"] = True
        result["context_clues"] = context_clues

        old_type = result.get("post_type", "")
        if old_type in ("work_discussion", "unknown"):
            result["post_type"] = "recommendation"

        print(
            f"[{_ts()}][{self.emoji}] 🧭 다작/순서질문 감지: "
            f"order_hits={order_hits[:4]}, arrow={has_arrow_chain}, "
            f"author_focus={has_author_focus}, list_like={list_like_count} "
            f"→ post_type '{old_type}' -> '{result.get('post_type')}'",
            file=sys.stderr,
        )
        return result

    def _is_title_like_surface(self, text: str) -> bool:
        """
        댓글이 "제목 후보" 형태인지 구조적으로 판별한다.
        (어휘 블랙리스트보다 표면/형태소 특징을 우선 사용)
        """
        import re
        
        stripped = (text or "").strip()
        if not stripped:
            return False
        if '\n' in stripped:
            return False
        if not (2 <= len(stripped) <= 40):
            return False
        
        # URL/멘션/해시류는 제목 후보 아님
        if re.search(r'https?://|www\.|@[A-Za-z0-9_]|#[A-Za-z0-9_]+', stripped, flags=re.I):
            return False
        
        # 제목 표면으로 허용되는 문자군
        if not re.fullmatch(r"[가-힣a-zA-Z0-9\s\-\._:!,'\"~·]+", stripped):
            return False
        
        # 초성/모음만으로 구성된 문자열 제외
        if re.fullmatch(r'[ㄱ-ㅎㅏ-ㅣ\s]+', stripped):
            return False
        
        # 숫자만/기호성 텍스트 제외
        if re.fullmatch(r'[0-9\s]+', stripped):
            return False
        
        return True

    def _classify_comment_speech_act(self, text: str) -> str:
        """
        한국어 문맥 기반 문장행위 판별.
        
        Returns:
          - question
          - request
          - explanation
          - answer_like
        """
        import re
        
        stripped = (text or "").strip()
        compact = re.sub(r"\s+", "", stripped.lower())
        
        # 1) 문장부호 기반 빠른 판별
        if re.search(r'[?？]+\s*$', stripped):
            return "question"
        
        # 2) 일반적 의문/질의 어휘 + 종결 패턴 (하드코딩 단어 나열 최소화)
        has_interrogative = bool(re.search(r'(뭐|무엇|몇|누구|어디|왜|어떻게|언제|얼마|무슨|제목|작품명|번호)', compact))
        q_ending = bool(re.search(r'(임|냐|야|인가|인지|일까|일까요|일까나|뭔데|뭔가|뭐임)$', compact))
        if has_interrogative and (q_ending or len(compact) <= 14):
            return "question"
        
        # 3) 요청/명령 패턴
        if re.search(r'(알려|추천|찾아|보여|던져|공유|좌표|링크|출처)', compact):
            if re.search(r'(줘|좀|요|부탁|plz|ㄱ)$', compact) or len(compact) <= 12:
                return "request"
        
        # 4) 설명형 패턴 (근거/방법/위치 설명)
        if re.search(r'(초반|페이지|번역|제목에|적혀|나옴|보면|바로|검색|찾는법|나와)', compact):
            return "explanation"
        
        # 5) 형태소 기반 일반화 (질문형 토큰 사전 의존도 감소)
        if self.use_kiwi and self.kiwi:
            try:
                toks = self.kiwi.tokenize(stripped)
            except Exception:
                toks = []
            
            if toks:
                noun_tags = {"NNG", "NNP", "NNB", "SL", "SH", "SN", "XR"}
                pred_tags = {"VV", "VA", "VX", "VCP", "VCN", "XSV", "XSA"}
                ending_tags = {"EF", "EC", "EP", "ETN", "ETM"}
                nominal_title_heads = {"법", "방법", "세계", "일지", "기록", "이야기", "공략", "매뉴얼"}
                
                noun_cnt = 0
                pred_cnt = 0
                ending_cnt = 0
                josa_cnt = 0
                
                for tk in toks:
                    tag = tk.tag
                    if tag in noun_tags:
                        noun_cnt += 1
                    if tag in pred_tags:
                        pred_cnt += 1
                    if tag in ending_tags:
                        ending_cnt += 1
                    if tag.startswith("J"):
                        josa_cnt += 1
                
                # 제목 답변은 대체로 "명사구"에 가깝고,
                # 설명/질문/요청은 용언+어미/조사 비율이 높다.
                lex_base = max(1, noun_cnt + pred_cnt)
                noun_ratio = noun_cnt / lex_base
                last_tag = toks[-1].tag
                last_form = str(toks[-1].form)
                
                # "...하는법"처럼 용언 관형화 + 명사 헤드로 끝나는 패턴은 제목형으로 허용
                if last_tag in noun_tags and last_form in nominal_title_heads:
                    return "answer_like"
                
                if pred_cnt > 0 and noun_ratio < 0.75:
                    return "explanation"
                # 종결형 어미가 붙은 서술문만 설명으로 간주
                if ending_cnt > 0 and pred_cnt > 0 and last_tag not in noun_tags:
                    return "explanation"
                if josa_cnt >= 2 and noun_ratio < 0.8:
                    return "explanation"
        
        return "answer_like"
    
    def get_search_queries(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract search queries from result, sorted by priority."""
        requests = result.get("search_requests", [])
        # Sort by priority (1=highest)
        return sorted(requests, key=lambda x: x.get("priority", 99))

    def _detect_image_only_post(
        self,
        result: Dict[str, Any],
        post: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        🔥 이미지 전용 게시글 코드 레벨 감지
        
        content_blocks가 모두 이미지(type=image)이고 텍스트가 없는 경우,
        LLM이 이를 감지하지 못했을 때 코드 레벨에서 image_post로 강제 분류.
        
        FP 패턴 대응:
        - "글 쓰고 보니까" (제목만 있고 본문은 이미지만) → LLM이 work_discussion으로 분류
        - 이미지만 있는 포스트는 소설 작품 논의가 아닐 가능성 매우 높음
        """
        content_blocks = post.get("content_blocks", [])
        if not content_blocks:
            return result
        
        # 텍스트 블록과 이미지 블록 분리
        text_blocks = []
        image_blocks = []
        for block in content_blocks:
            if isinstance(block, dict):
                if block.get("text") and block["text"].strip():
                    text_blocks.append(block["text"])
                elif block.get("type") == "image" or block.get("src"):
                    image_blocks.append(block)
            elif isinstance(block, str) and block.strip():
                text_blocks.append(block)
        
        # 이미지만 있고 텍스트가 없는 경우 (또는 텍스트가 매우 짧음)
        total_text_len = sum(len(t.strip()) for t in text_blocks)
        
        if image_blocks and total_text_len < 10:
            # LLM이 이미 image_post/noise로 분류했으면 스킵
            current_post_type = result.get("post_type", "")
            if current_post_type in ("image_post", "noise"):
                return result
            
            # 코드 레벨 오버라이드: image_post로 강제 분류
            old_type = current_post_type
            result["post_type"] = "image_post"
            result["is_noise"] = True
            result["noise_reason"] = (
                f"이미지 전용 게시글 (이미지 {len(image_blocks)}개, "
                f"텍스트 {total_text_len}자) - 소설 작품 논의 불가"
            )
            
            print(
                f"[{_ts()}][{self.emoji}] 🖼️ 이미지 전용 감지: "
                f"post_type='{old_type}' → 'image_post' "
                f"(image={len(image_blocks)}, text={total_text_len}자)",
                file=sys.stderr,
            )
        
        return result

    # ── 장르 접두사 태그 파싱 ──────────────────────────

    def _parse_genre_prefix_tags(
        self,
        result: Dict[str, Any],
        post: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        🆕 장르 접두사 태그 파싱
        
        DC 갤러리 관행: 제목 앞에 "TS) 골렘이 어떻게 우는거지" 형태로
        장르 태그를 붙이는 패턴. 또한 "챗생사) 꺾였구나" 같이 약칭+) 형태도 포함.
        
        동작:
        1. 알려진 장르 접두사(GENRE_PREFIX_TAGS)를 제거하고 나머지를 제목 후보로
        2. 미지의 "약칭)" 패턴을 감지하면 약칭을 key_terms에 추가
        3. 장르 힌트를 context_clues에 저장
        """
        import re
        from ..rules import GENRE_PREFIX_TAGS
        
        title = post.get("title", "").strip()
        if not title:
            return result
        
        detected = result.get("detected_entities") or {}
        possible_titles = detected.get("possible_titles") or []
        key_terms = result.get("key_terms") or []
        context_clues = result.get("context_clues") or {}
        
        genre_hints = []
        remaining_title = title
        
        # 1) 알려진 장르 접두사 매칭
        for prefix in GENRE_PREFIX_TAGS:
            if remaining_title.startswith(prefix):
                genre_hint = prefix.rstrip(")")
                genre_hints.append(genre_hint)
                remaining_title = remaining_title[len(prefix):].strip()
                print(
                    f"[{_ts()}][{self.emoji}] 🏷️ 장르 접두사 감지: '{prefix}' → 힌트='{genre_hint}'",
                    file=sys.stderr,
                )
                break
        
        # 2) 미지의 "약칭)" 패턴: 한글 2~6자 + ")" 형태
        #    예: "챗생사)" → 약칭 "챗생사"를 key_terms에 추가
        if not genre_hints:
            prefix_match = re.match(r'^([가-힣a-zA-Z]{1,6})\)\s*', remaining_title)
            if prefix_match:
                abbrev = prefix_match.group(1)
                remaining_after = remaining_title[prefix_match.end():].strip()
                # 약칭 뒤에 실제 내용이 있어야 유효한 접두사
                if remaining_after and len(remaining_after) >= 2:
                    genre_hints.append(abbrev)
                    remaining_title = remaining_after
                    # 약칭을 key_terms에 추가 (검색 후보)
                    if abbrev not in key_terms:
                        key_terms.append(abbrev)
                    # 약칭을 possible_titles에도 추가
                    if abbrev not in possible_titles:
                        possible_titles.append(abbrev)
                    print(
                        f"[{_ts()}][{self.emoji}] 🏷️ 약칭 접두사 감지: '{abbrev})' "
                        f"→ key_terms/possible_titles 추가, 나머지='{remaining_after[:30]}'",
                        file=sys.stderr,
                    )
        
        # 3) 중첩 접두사 (TS) 챗생사) ... 형태)
        if genre_hints and remaining_title:
            nested_match = re.match(r'^([가-힣a-zA-Z]{1,6})\)\s*', remaining_title)
            if nested_match:
                nested_abbrev = nested_match.group(1)
                remaining_after = remaining_title[nested_match.end():].strip()
                if remaining_after and len(remaining_after) >= 2:
                    genre_hints.append(nested_abbrev)
                    remaining_title = remaining_after
                    if nested_abbrev not in key_terms:
                        key_terms.append(nested_abbrev)
                    if nested_abbrev not in possible_titles:
                        possible_titles.append(nested_abbrev)
                    print(
                        f"[{_ts()}][{self.emoji}] 🏷️ 중첩 접두사 감지: '{nested_abbrev})'",
                        file=sys.stderr,
                    )
        
        # 결과 업데이트
        if genre_hints:
            context_clues["genre_prefix_tags"] = genre_hints
            context_clues["title_after_prefix_strip"] = remaining_title
            result["context_clues"] = context_clues
            
            detected["possible_titles"] = possible_titles
            result["detected_entities"] = detected
            result["key_terms"] = key_terms
        
        return result

    # ── 회차 번호 감지 ──────────────────────────────

    def _detect_episode_numbers(
        self,
        result: Dict[str, Any],
        post: Dict[str, Any],
        comments: List[str],
    ) -> Dict[str, Any]:
        """
        🆕 회차 번호 감지 (N화/N회/N일차 등)
        
        "수호룡 550화", "■■세계 1234회", "방티알 1034일차" 등의 패턴.
        회차 숫자가 있으면 "연재 작품 논의"가 거의 확실한 강력한 앵커 신호.
        
        결과에 has_episode_reference=True, episode_info={} 를 context_clues에 추가.
        """
        from ..rules import EPISODE_NUMBER_PATTERN
        
        title = post.get("title", "").strip()
        content_texts = []
        for block in post.get("content_blocks", []):
            if isinstance(block, dict) and block.get("text"):
                content_texts.append(block["text"])
            elif isinstance(block, str):
                content_texts.append(block)
        body = " ".join(content_texts[:3])[:200]
        
        context_clues = result.get("context_clues") or {}
        
        # 제목에서 회차 패턴 검색
        all_matches = []
        for text_source, source_name in [(title, "title"), (body, "body")]:
            if not text_source:
                continue
            for m in EPISODE_NUMBER_PATTERN.finditer(text_source):
                episode_num = int(m.group(1))
                # 회차 번호의 현실적 범위 (1~9999)
                if 1 <= episode_num <= 9999:
                    all_matches.append({
                        "episode_number": episode_num,
                        "matched_text": m.group(0),
                        "source": source_name,
                    })
        
        if all_matches:
            context_clues["has_episode_reference"] = True
            context_clues["episode_info"] = all_matches[0]  # 첫 번째 매치
            result["context_clues"] = context_clues
            
            # 회차 참조가 있으면 noise 판정 방지 (작품 논의 확실)
            if result.get("is_noise") and result.get("post_type") != "image_post":
                ep_text = all_matches[0]["matched_text"]
                print(
                    f"[{_ts()}][{self.emoji}] 📺 회차 번호 감지 + noise 해제: "
                    f"'{ep_text}' → 연재 작품 논의 확실",
                    file=sys.stderr,
                )
                result["is_noise"] = False
                result["noise_reason"] = None
                if result.get("post_type") == "noise":
                    result["post_type"] = "work_discussion"
            else:
                print(
                    f"[{_ts()}][{self.emoji}] 📺 회차 번호 감지: "
                    f"'{all_matches[0]['matched_text']}' (작품 앵커 신호)",
                    file=sys.stderr,
                )
        
        return result

    # ── 제목 마스킹 감지 ──────────────────────────────

    def _detect_title_masking(
        self,
        result: Dict[str, Any],
        post: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        🆕 제목 마스킹 감지 (ㅁㅁ세계, ■■세계 등)
        
        갤러리 사용자가 의도적으로 작품명을 ㅁㅁ, ■■ 등으로 가리는 패턴.
        이 경우 Decoder가 해독을 시도해도 정보 자체가 없으므로,
        "해독 불가"를 정당한 판정으로 인정하는 플래그를 설정.
        
        결과에 has_title_masking=True를 context_clues에 추가.
        작품 논의가 확실하지만 제목 특정은 불가능함을 후속 Expert에 알림.
        """
        from ..rules import TITLE_MASKING_PATTERNS
        
        title = post.get("title", "").strip()
        if not title:
            return result
        
        context_clues = result.get("context_clues") or {}
        
        for mask_pattern in TITLE_MASKING_PATTERNS:
            if mask_pattern in title:
                context_clues["has_title_masking"] = True
                context_clues["masking_pattern"] = mask_pattern
                result["context_clues"] = context_clues
                
                print(
                    f"[{_ts()}][{self.emoji}] 🔒 제목 마스킹 감지: "
                    f"'{mask_pattern}' in '{title[:30]}' → 해독 불가 플래그 설정",
                    file=sys.stderr,
                )
                
                # 마스킹된 제목은 작품 논의이지만 특정 불가
                # is_noise는 건드리지 않음 (다른 정보로 판단 가능할 수 있음)
                break
        
        return result
    # ── Phase 11j: 장르 토론 / 추천 요청 코드 레벨 감지 ──────────

    def _detect_genre_discussion_patterns(
        self,
        result: Dict[str, Any],
        post: Dict[str, Any],
        comments: List[str],
    ) -> Dict[str, Any]:
        """
        🆕 Phase 11j: 장르 토론 / 추천 요청 코드 레벨 감지
        
        LLM이 놓치는 장르 토론 패턴을 코드 레벨에서 감지하여
        context_clues에 플래그를 설정. 후속 전문가가 이를 참고.
        
        감지 패턴:
        1. DC 의견 접두사 패턴: "소신발언)) X" → 의견 게시글
        2. 장르 일반론 패턴: "X이나 Y에서 Z" → 장르/트로프 토론
        3. 추천 요청 패턴: "X를 보고싶구나" → 추천 요청
        4. 본문 부정 표현: "본적없음", "못봤음" → 장르 소재 토론
        """
        import re
        from ..rules import (
            DC_OPINION_KEYWORDS,
            RECOMMENDATION_REQUEST_SUFFIXES,
            GENRE_DISCUSSION_TITLE_INDICATORS,
            GENRE_ARCHETYPE_TERMS,
        )
        
        title = post.get("title", "").strip()
        if not title:
            return result
        
        context_clues = result.get("context_clues") or {}
        _flags = []  # 감지된 패턴 목록
        
        # ── 본문 텍스트 추출 ──
        content_texts = []
        for block in post.get("content_blocks", []):
            if isinstance(block, dict) and block.get("text"):
                content_texts.append(block["text"])
            elif isinstance(block, str):
                content_texts.append(block)
        body = " ".join(content_texts).strip()
        
        title_lower = title.lower().replace(" ", "")
        
        # ━━ 패턴 1: DC 의견 접두사 "소신발언))" ━━
        # "소신발언)) X" → "소신발언"은 작품명이 아니라 의견 태그
        for kw in DC_OPINION_KEYWORDS:
            # 패턴: "소신발언))" 또는 "소신발언 ))" 또는 "소신발언)"
            pat = re.compile(
                r'^' + re.escape(kw) + r'\s*\)+\s*', re.IGNORECASE
            )
            if pat.match(title):
                _flags.append(f"dc_opinion_prefix:{kw}")
                # 이 키워드는 작품 약칭이 아님을 명시
                context_clues["dc_opinion_prefix"] = kw
                context_clues["dc_opinion_remainder"] = pat.sub("", title).strip()
                print(
                    f"[{_ts()}][{self.emoji}] 🏷️ DC 의견 접두사 감지: "
                    f"'{kw})' in '{title[:40]}' → 작품명 아닌 의견 태그",
                    file=sys.stderr,
                )
                break
        
        # ━━ 패턴 2: 장르 일반론 제목 패턴 ━━
        # "로판이나 웹소에서 가주습격은...", "백합에 난입이 이론상..."
        _genre_indicators_found = []
        for indicator in GENRE_DISCUSSION_TITLE_INDICATORS:
            if indicator in title:
                _genre_indicators_found.append(indicator)
        
        # 장르 아키타입 용어가 제목에 포함되면서 장르 일반론 지시어도 있으면 → 강한 장르 토론 신호
        _archetype_in_title = []
        for archetype in GENRE_ARCHETYPE_TERMS:
            if archetype.lower() in title_lower:
                _archetype_in_title.append(archetype)
        
        if _genre_indicators_found and _archetype_in_title:
            _flags.append(f"genre_discussion_title:{'+'.join(_archetype_in_title)}")
            context_clues["genre_discussion_detected"] = True
            context_clues["genre_discussion_indicators"] = _genre_indicators_found
            context_clues["genre_archetypes_in_title"] = _archetype_in_title
            print(
                f"[{_ts()}][{self.emoji}] 🎭 장르 토론 제목 감지: "
                f"아키타입={_archetype_in_title}, 지시어={_genre_indicators_found} "
                f"in '{title[:40]}'",
                file=sys.stderr,
            )
        
        # ━━ 패턴 3: 추천 요청 패턴 ━━
        # "후타 암타물을 보고싶구나..", "빌환 추천좀"
        for suffix in RECOMMENDATION_REQUEST_SUFFIXES:
            if title.rstrip(".!? ").endswith(suffix):
                _flags.append(f"recommendation_request:{suffix}")
                context_clues["is_recommendation_request"] = True
                context_clues["recommendation_suffix"] = suffix
                print(
                    f"[{_ts()}][{self.emoji}] 🔍 추천 요청 감지: "
                    f"'{suffix}' in '{title[:40]}' → 추천 요청 게시글",
                    file=sys.stderr,
                )
                break
        
        # ━━ 패턴 4: 본문 부정 표현 (장르 소재 토론) ━━
        # "본적없음", "못봤음" → "이 소재/장르의 작품을 본 적 없다" = 장르 토론
        _negation_patterns = (
            "본적없", "본적 없", "본 적 없",
            "못봤", "못 봤", "읽어본적없", "읽은적없",
            "없는거같", "없는 거 같", "없는것같",
        )
        _body_combined = body + " " + " ".join(comments[:5]) if comments else body
        for neg_pat in _negation_patterns:
            if neg_pat in _body_combined:
                # 추가 조건: 장르/소재 용어도 함께 있어야 함
                if _archetype_in_title or _genre_indicators_found:
                    _flags.append(f"genre_negation:{neg_pat}")
                    context_clues["genre_negation_detected"] = True
                    print(
                        f"[{_ts()}][{self.emoji}] 🚫 장르 소재 부정 표현: "
                        f"'{neg_pat}' + 장르키워드 → 소재 토론 확정",
                        file=sys.stderr,
                    )
                    break
        
        # ━━ 패턴 5: "X 신작봤는데 Y 하위호환" 비교 패턴 ━━
        # 주어는 신작(이름 불명), Y는 비교 대상일 뿐
        _comparison_match = re.search(
            r'신작.{0,10}(하위호환|상위호환|열화판|짝퉁|카피|유사)', title
        )
        if _comparison_match:
            _flags.append(f"comparison_pattern:{_comparison_match.group(1)}")
            context_clues["is_comparison_post"] = True
            context_clues["comparison_type"] = _comparison_match.group(1)
            print(
                f"[{_ts()}][{self.emoji}] ⚖️ 비교 패턴 감지: "
                f"'신작...{_comparison_match.group(1)}' in '{title[:40]}' "
                f"→ 비교 대상은 주제가 아님",
                file=sys.stderr,
            )
        
        # ━━ 결과 반영 ━━
        if _flags:
            context_clues["genre_discussion_flags"] = _flags
            result["context_clues"] = context_clues
            
            # 장르 토론 or 추천 요청이 강하게 감지되면 post_type 보정
            _strong_genre = (
                context_clues.get("genre_discussion_detected")
                and context_clues.get("genre_negation_detected")
            )
            _strong_opinion = bool(context_clues.get("dc_opinion_prefix"))
            _strong_recommendation = bool(context_clues.get("is_recommendation_request"))
            
            current_post_type = result.get("post_type", "")
            if _strong_genre and current_post_type not in ("genre_discussion", "noise"):
                result["post_type"] = "genre_discussion"
                print(
                    f"[{_ts()}][{self.emoji}] 🎭 post_type 보정: "
                    f"'{current_post_type}' → 'genre_discussion' (장르토론+부정표현)",
                    file=sys.stderr,
                )
            elif _strong_recommendation and current_post_type == "work_discussion":
                result["post_type"] = "recommendation"
                context_clues["is_asking_recommendation"] = True
                result["context_clues"] = context_clues
                print(
                    f"[{_ts()}][{self.emoji}] 🔍 post_type 보정: "
                    f"'{current_post_type}' → 'recommendation' (추천요청)",
                    file=sys.stderr,
                )
        
        return result
