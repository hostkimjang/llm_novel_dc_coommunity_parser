"""
Stage 4: Critic Expert - 문학 비평 전문가
Metadata extraction and sentiment analysis.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any, Dict, List, Optional

from .prompts import CRITIC_SYSTEM, CRITIC_PROMPT
from .utils import parse_json_with_think_removal, _ts


class CriticExpert:
    """
    📖 Critic - Literary Critic / Content Analyst
    
    Responsibilities:
    - Extract metadata (micro-tags, sentiment)
    - NSFW/spoiler detection
    - Reader segment analysis
    """
    
    def __init__(self, llm_client):
        self.llm = llm_client
        self.name = "Critic"
        self.emoji = "📖"
    
    def analyze(
        self,
        post: Dict[str, Any],
        comments: List[str],
        verifier_result: Dict[str, Any],
        conversation_context: Optional[str] = None,
        ctx: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Extract metadata from confirmed novel discussion.
        
        Args:
            post: Original post data
            comments: Comment texts
            verifier_result: Stage 3 output
            conversation_context: Optional conversation history from other experts
            
        Returns:
            CriticResult with analysis metadata
        """
        start_time = time.time()
        post_id = post.get("post_id", "?")
        
        # verifier_result가 None이거나 에러인 경우 처리
        if not verifier_result or "error" in verifier_result:
            print(f"[{_ts()}][{self.emoji}] {self.name} 스킵: verifier_result 없음", file=sys.stderr)
            return self._empty_result()
        
        # Skip if not relevant
        verification = verifier_result.get("verification_result", {})
        if not verification.get("is_relevant"):
            print(f"[{_ts()}][{self.emoji}] {self.name} 스킵: is_relevant=False", file=sys.stderr)
            return self._empty_result()
        
        # Build post JSON
        post_json = self._build_post_json(post, comments)
        
        # Verifier 결과 요약 (토큰 압축)
        verifier_summary = self._summarize_verifier(verifier_result)
        
        # Suspected titles from Context (다른 전문가가 생성한 후보 작품 목록)
        suspected_titles_info = ""
        if ctx and hasattr(ctx, 'suspected_titles') and ctx.suspected_titles:
            suspected_items = []
            for st in ctx.suspected_titles[:3]:
                # 각 dict 타입 검사 추가
                if not isinstance(st, dict):
                    print(f"[{_ts()}][{self.emoji}] ⚠️  suspected_titles 항목이 dict가 아님: {type(st)}, value={st}", file=sys.stderr)
                    continue
                    
                title = st.get('title', 'Unknown')
                conf = st.get('confidence', 0.5)
                try:
                    conf_str = f"{float(conf):.2f}"
                except (ValueError, TypeError):
                    conf_str = str(conf)
                suspected_items.append(f"- {title} (conf={conf_str})")
            suspected_titles_info = "\n\n=== SUSPECTED TITLES (후보 작품) ===\n" + "\n".join(suspected_items) + "\n"
        
        # Format prompt
        user_prompt = CRITIC_PROMPT.format(
            verifier_json=json.dumps(verifier_summary, ensure_ascii=False, indent=2),
            post_json=json.dumps(post_json, ensure_ascii=False, indent=2),
        ) + suspected_titles_info
        
        print(f"[{_ts()}][{self.emoji}] {self.name} 분석 시작: post_id={post_id}", file=sys.stderr)
        
        try:
            result = self._call_llm(user_prompt)
            elapsed = time.time() - start_time
            
            analysis = result.get("analysis", {})
            print(f"[{_ts()}][{self.emoji}] {self.name} 완료 ({elapsed:.1f}s): "
                  f"sentiment={analysis.get('sentiment_profile', {}).get('sentiment')}, "
                  f"tags={analysis.get('micro_tags', [])}", 
                  file=sys.stderr)
            
            # 각 suspected_titles 항목별 분석 후 조정
            if ctx:
                self._adjust_suspected_titles(result, ctx)
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            import traceback
            print(f"[{_ts()}][{self.emoji}] {self.name} 에러 ({elapsed:.1f}s): {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return self._fallback_result(verifier_result)
    
    def _adjust_suspected_titles(self, result: Dict[str, Any], ctx: Any) -> None:
        """
        각 suspected_titles 항목별 분석 후 조정
        - 감정 분석과 일치하지 않는 항목에 flag 추가
        - 신뢰도가 낮은 항목 정리
        """
        if not hasattr(ctx, "suspected_titles") or not ctx.suspected_titles:
            return
        
        analysis = result.get("analysis", {})
        sentiment = analysis.get("sentiment_profile", {}).get("sentiment", "neutral")
        
        adjusted = []
        for st in ctx.suspected_titles:
            # 각 dict 타입 검사 추가
            if not isinstance(st, dict):
                print(f"[{_ts()}][{self.emoji}] ⚠️  suspected_titles 항목이 dict가 아님 (skip): {type(st)}", file=sys.stderr)
                continue
                
            # verified 상태는 유지
            if st.get("status") == "verified":
                adjusted.append(st)
                continue
            
            # 신뢰도가 너무 낮으면 제거
            if st.get("confidence", 0) < 0.2:
                continue
            
            # Critic 분석 반영 (멤버 플래그 추가)
            st["critic_reviewed"] = True
            adjusted.append(st)
        
        ctx.suspected_titles = adjusted[:5]
        print(f"[{_ts()}][{self.emoji}] suspected_titles filtered: {len(ctx.suspected_titles)}", file=sys.stderr)
        for i, st in enumerate(ctx.suspected_titles, 1):
            title = st.get('title', 'N/A')
            conf = st.get('confidence', 'N/A')
            source = st.get('source_expert', 'unknown')
            print(f"[{_ts()}][{self.emoji}]    [{i}] {title} (conf={conf}, from={source})", file=sys.stderr)
    
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
            "content": content_texts,
            "comments": comments[:10],
        }
    
    def _call_llm(self, user_prompt: str) -> Dict[str, Any]:
        """Call LLM and parse JSON response."""
        messages = [
            {"role": "system", "content": CRITIC_SYSTEM},
            {"role": "user", "content": user_prompt},
        ]
        
        response_text = self.llm._stream_chat_http(
            messages=messages,
            tag="critic",
            use_grammar=True,
        )
        
        return self._parse_json_response(response_text)
    
    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Extract and parse JSON from response, removing <think> blocks."""
        return parse_json_with_think_removal(text)
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result for non-relevant posts."""
        return {
            "analysis": None
        }
    
    def _fallback_result(self, verifier_result: Dict[str, Any]) -> Dict[str, Any]:
        """Build fallback result from verifier."""
        if not verifier_result or "error" in verifier_result:
            return self._empty_result()
            
        verification = verifier_result.get("verification_result", {})
        novel_id = verification.get("novel_identity", {})
        
        return {
            "analysis": {
                "detected_titles": [{
                    "official_title": novel_id.get("official_title"),
                    "heretic_url": novel_id.get("heretic_url"),
                    "confidence": novel_id.get("confidence", "None"),
                    "alias_or_mention": None,
                }] if novel_id.get("official_title") else [],
                "micro_tags": [],
                "sentiment_profile": {
                    "sentiment": "Unknown",
                    "pacing": "Unknown",
                    "drift_risk": "Unknown",
                },
                "is_nsfw": False,
                "spoiler_level": "none",
                "user_segment": None,
                "notes": "Critic 분석 실패로 기본값 사용",
            }
        }
    
    def get_analysis(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract analysis from result."""
        return result.get("analysis")
    
    def _summarize_verifier(self, vf: Dict[str, Any]) -> Dict[str, Any]:
        """Verifier 결과 ?붿빟 (토큰 압축)"""
        if not vf:
            return {}
        
        vr = vf.get("verification_result") or {}
        novel_id = vr.get("novel_identity") or {}
        
        return {
            "is_relevant": vr.get("is_relevant"),
            "is_novel_discussion": vr.get("is_novel_discussion"),
            "official_novel_title": novel_id.get("official_novel_title"),
            "heretic_url": novel_id.get("heretic_url"),
            "confidence": novel_id.get("confidence"),
            "evidence_type": novel_id.get("evidence_type"),
        }
