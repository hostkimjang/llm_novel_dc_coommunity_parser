"""
Stage 1: Gatekeeper Expert - 커뮤니티 문화 분석관
First-line filter for noise detection and entity extraction.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any, Dict, List, Optional

from .prompts import GATEKEEPER_SYSTEM, GATEKEEPER_PROMPT
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
            result = self._call_llm(user_prompt)
            
            # Enhance with Kiwi morphological analysis
            if self.use_kiwi:
                title = post.get("title", "")
                kiwi_entities = self._extract_morphemes_kiwi(title)
                result = self._merge_entities(result, kiwi_entities)
            
            # 🚨 코드 레벨 보강: 댓글에서 제목 답변 후보 추출
            result = self._postprocess_comment_titles(result, comments)
            
            # 🔥 이미지 전용 게시글 코드 레벨 감지
            result = self._detect_image_only_post(result, post)
            
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
    
    def _call_llm(self, user_prompt: str) -> Dict[str, Any]:
        """Call LLM and parse JSON response."""
        messages = [
            {"role": "system", "content": GATEKEEPER_SYSTEM},
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
        3. Extract all 2+ character segments
        4. Include original text segments
        
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
                    candidates.add(segment)
        
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
            import re
            stripped = comment.strip()
            # 한 줄짜리 댓글, 한글+영문+숫자+공백만, 3~30자, 초성만 제외
            if (stripped and '\n' not in stripped
                    and 3 <= len(stripped) <= 30
                    and re.fullmatch(r'[가-힣a-zA-Z0-9\s]+', stripped)
                    and not re.fullmatch(r'[ㄱ-ㅎㅏ-ㅣ]+', stripped)):
                comment_title_candidates.append(stripped)
        
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
