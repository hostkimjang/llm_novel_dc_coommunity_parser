"""
Multi-Expert Staged Pipeline
4-stage analysis with expert personas and iterative search.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .experts import GatekeeperExpert, DecoderExpert, VerifierExpert, CriticExpert
from .experts.prompts import assemble_final_output
from .models import PostInput, PickvelOutputItemV2
from .rules import NOISE_TERMS, NOVEL_SITES, SLANG_DICTIONARY, TROPE_TERMS, apply_rules
from .llm.client import LLMClient
from .search.client import MCPClient


def _ts() -> str:
    """Timestamp for logging."""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


class StagedPipeline:
    """
    Multi-Expert Analysis Pipeline
    
    Stages:
    1. Gatekeeper: Noise filter, entity detection, search planning
    2. Decoder: Abbreviation restoration, candidate generation
    3. Verifier: Evidence verification, final confirmation
    4. Critic: Metadata extraction, sentiment analysis
    
    Each stage can request searches, and results are shared between stages.
    """
    
    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        mcp: Optional[MCPClient] = None,
        output_dir: Optional[Path] = None,
    ):
        self.llm = llm or LLMClient()
        self.mcp = mcp or MCPClient()
        self.output_dir = output_dir or Path("out")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize experts
        self.gatekeeper = GatekeeperExpert(self.llm)
        self.decoder = DecoderExpert(self.llm)
        self.verifier = VerifierExpert(self.llm)
        self.critic = CriticExpert(self.llm)
        
        # Configuration
        self.max_searches_per_stage = int(os.getenv("STAGED_MAX_SEARCHES", "3"))
        self.enable_verification_search = os.getenv("STAGED_VERIFY_SEARCH", "1") == "1"
        
        # Search cache to avoid duplicates
        self._search_cache: Dict[str, List[Dict[str, Any]]] = {}
        
        # Rules config
        self.rules_config = {
            "novel_sites": NOVEL_SITES,
            "slang_dictionary": SLANG_DICTIONARY,
            "noise_terms": NOISE_TERMS,
            "trope_terms": TROPE_TERMS,
        }
    
    def process_post(self, post: PostInput) -> PickvelOutputItemV2:
        """
        Process a single post through all expert stages.
        
        Args:
            post: Input post data
            
        Returns:
            PickvelOutputItemV2 with complete analysis
        """
        post_id = post.post_id
        start_time = time.time()
        
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"[{_ts()}] 📋 Post {post_id} 분석 시작: {post.title[:50]}...", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        
        # Convert post to dict for experts
        post_dict = self._post_to_dict(post)
        comments = self._extract_comments(post)
        
        # Clear search cache for new post
        self._search_cache.clear()
        
        try:
            # ===== STAGE 1: Gatekeeper =====
            gatekeeper_result = self._run_gatekeeper(post_dict, comments)
            
            # Early exit if noise
            if gatekeeper_result.get("is_noise"):
                elapsed = time.time() - start_time
                print(f"[{_ts()}] ⏹️ 노이즈 필터링 완료 ({elapsed:.1f}s)", file=sys.stderr)
                return self._build_noise_output(post_id, gatekeeper_result)
            
            # ===== SEARCH PHASE 1: Gatekeeper requests =====
            search_results = self._execute_searches(
                gatekeeper_result.get("search_requests", []),
                post_id
            )
            
            # ===== STAGE 2: Decoder =====
            decoder_result = self._run_decoder(gatekeeper_result, search_results)
            
            # ===== SEARCH PHASE 2: Verification search (if needed) =====
            verification_results = []
            if self.enable_verification_search and self.decoder.needs_verification_search(decoder_result):
                verify_query = self.decoder.get_verification_query(decoder_result)
                if verify_query:
                    verification_results = self._execute_searches(
                        [{"query": verify_query["query"], "purpose": "verify", "priority": 1}],
                        post_id
                    )
            
            # ===== STAGE 3: Verifier =====
            verifier_result = self._run_verifier(
                post_dict, comments, gatekeeper_result, decoder_result, verification_results
            )
            
            # ===== STAGE 4: Critic =====
            critic_result = self._run_critic(post_dict, comments, verifier_result)
            
            # ===== Assemble final output =====
            final_output = assemble_final_output(
                post_id,
                gatekeeper_result,
                decoder_result,
                verifier_result,
                critic_result,
            )
            
            elapsed = time.time() - start_time
            self._log_final_result(post_id, final_output, elapsed)
            
            return self._dict_to_output(post_id, final_output)
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[{_ts()}] ❌ 처리 오류 ({elapsed:.1f}s): {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return self._build_error_output(post_id, str(e))
    
    def _run_gatekeeper(
        self, 
        post_dict: Dict[str, Any], 
        comments: List[str]
    ) -> Dict[str, Any]:
        """Run Stage 1: Gatekeeper."""
        print(f"\n[{_ts()}] ━━━ Stage 1: 🎭 Gatekeeper ━━━", file=sys.stderr)
        result = self.gatekeeper.analyze(post_dict, comments, self.rules_config)
        result["_post_id"] = post_dict.get("post_id")
        return result
    
    def _run_decoder(
        self,
        gatekeeper_result: Dict[str, Any],
        search_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Run Stage 2: Decoder."""
        print(f"\n[{_ts()}] ━━━ Stage 2: 🔤 Decoder ━━━", file=sys.stderr)
        return self.decoder.analyze(
            gatekeeper_result,
            search_results,
            self.rules_config.get("slang_dictionary", {}),
        )
    
    def _run_verifier(
        self,
        post_dict: Dict[str, Any],
        comments: List[str],
        gatekeeper_result: Dict[str, Any],
        decoder_result: Dict[str, Any],
        verification_search: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Run Stage 3: Verifier."""
        print(f"\n[{_ts()}] ━━━ Stage 3: 🔍 Verifier ━━━", file=sys.stderr)
        return self.verifier.analyze(
            post_dict,
            comments,
            gatekeeper_result,
            decoder_result,
            verification_search,
        )
    
    def _run_critic(
        self,
        post_dict: Dict[str, Any],
        comments: List[str],
        verifier_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run Stage 4: Critic."""
        print(f"\n[{_ts()}] ━━━ Stage 4: 📚 Critic ━━━", file=sys.stderr)
        return self.critic.analyze(post_dict, comments, verifier_result)
    
    def _execute_searches(
        self,
        search_requests: List[Dict[str, Any]],
        post_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Execute search requests and return combined results.
        Uses caching to avoid duplicate queries.
        """
        if not search_requests:
            return []
        
        all_results = []
        executed = 0
        
        for req in search_requests[:self.max_searches_per_stage]:
            query = req.get("query", "").strip()
            if not query:
                continue
            
            # Check cache
            if query in self._search_cache:
                print(f"[{_ts()}] 🔎 캐시 사용: {query[:50]}...", file=sys.stderr)
                all_results.extend(self._search_cache[query])
                continue
            
            # Execute search
            try:
                print(f"[{_ts()}] 🔎 검색 실행: {query[:50]}...", file=sys.stderr)
                raw_results = self.mcp.search(query)
                
                # Compact results
                compact = self._compact_results(raw_results)
                results = compact.get("results", [])
                
                # Cache and collect
                self._search_cache[query] = results
                all_results.extend(results)
                
                print(f"[{_ts()}] 🔎 검색 결과: {len(results)}건", file=sys.stderr)
                executed += 1
                
            except Exception as e:
                print(f"[{_ts()}] 🔎 검색 오류: {e}", file=sys.stderr)
        
        return all_results
    
    def _compact_results(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Compact search results for LLM input."""
        top_k = int(os.getenv("MCP_TOP_K_RESULTS", "5"))
        max_chars = int(os.getenv("MCP_MAX_CONTENT_CHARS", "0"))
        
        out = {"query": raw.get("query"), "results": []}
        results = raw.get("results", [])
        
        for item in results[:top_k]:
            if not isinstance(item, dict):
                continue
            content = item.get("content", "")
            if max_chars > 0 and len(content) > max_chars:
                content = content[:max_chars] + "..."
            out["results"].append({
                "title": item.get("title"),
                "url": item.get("url"),
                "content": content,
            })
        
        return out
    
    def _post_to_dict(self, post: PostInput) -> Dict[str, Any]:
        """Convert PostInput to dict for experts."""
        content_blocks = []
        for block in post.content_blocks:
            if hasattr(block, 'text') and block.text:
                content_blocks.append({"text": block.text})
            elif hasattr(block, 'image_url') and block.image_url:
                content_blocks.append({"image_url": block.image_url})
        
        return {
            "post_id": post.post_id,
            "title": post.title,
            "author": post.author,
            "created_at": str(post.created_at) if post.created_at else None,
            "url": post.url,
            "content_blocks": content_blocks,
        }
    
    def _extract_comments(self, post: PostInput) -> List[str]:
        """Extract comment texts from post."""
        comments = []
        for c in post.comments or []:
            text = c.text if hasattr(c, 'text') else str(c)
            if text and text.strip():
                comments.append(text.strip())
        return comments
    
    def _build_noise_output(
        self, 
        post_id: int, 
        gatekeeper_result: Dict[str, Any]
    ) -> PickvelOutputItemV2:
        """Build output for noise posts."""
        return PickvelOutputItemV2(
            post_id=post_id,
            identity={
                "is_relevant": False,
                "reason": gatekeeper_result.get("noise_reason") or "Noise",
            },
            analysis=None,
        )
    
    def _build_error_output(self, post_id: int, error: str) -> PickvelOutputItemV2:
        """Build output for error cases."""
        return PickvelOutputItemV2(
            post_id=post_id,
            identity={
                "is_relevant": False,
                "reason": f"처리 오류: {error}",
            },
            analysis=None,
        )
    
    def _dict_to_output(self, post_id: int, final: Dict[str, Any]) -> PickvelOutputItemV2:
        """Convert assembled dict to PickvelOutputItemV2."""
        # Normalize confidence values (LLM sometimes outputs lowercase)
        final = self._normalize_confidence(final)
        
        # Debug: Check normalized analysis
        analysis = final.get("analysis")
        if analysis and "detected_titles" in analysis:
            for i, title in enumerate(analysis.get("detected_titles", [])):
                conf = title.get("confidence")
                if conf and conf not in ("None", "Low", "Medium", "High", "Max"):
                    print(f"[DEBUG] Post {post_id}: detected_titles[{i}].confidence = '{conf}' (INVALID!)", file=sys.stderr)
                    # Force normalize
                    title["confidence"] = "None"
        
        return PickvelOutputItemV2(
            post_id=post_id,
            identity=final.get("identity", {"is_relevant": False}),
            analysis=analysis,
        )
    
    def _normalize_confidence(self, data: Any) -> Any:
        """Recursively normalize confidence values to proper case."""
        confidence_map = {
            "none": "None", "low": "Low", "medium": "Medium",
            "high": "High", "max": "Max",
            # Handle other common variations
            "NONE": "None", "LOW": "Low", "MEDIUM": "Medium",
            "HIGH": "High", "MAX": "Max",
            # Handle unexpected values
            "unknown": "None", "Unknown": "None", "UNKNOWN": "None",
        }
        
        if isinstance(data, dict):
            result = {}
            for k, v in data.items():
                if k == "confidence" and isinstance(v, str):
                    result[k] = confidence_map.get(v, v)
                else:
                    result[k] = self._normalize_confidence(v)
            return result
        elif isinstance(data, list):
            return [self._normalize_confidence(item) for item in data]
        return data
    
    def _log_final_result(
        self, 
        post_id: int, 
        final: Dict[str, Any], 
        elapsed: float
    ) -> None:
        """Log final result summary."""
        identity = final.get("identity", {})
        is_relevant = identity.get("is_relevant", False)
        novel_id = identity.get("novel_identity", {})
        title = novel_id.get("official_title") if novel_id else None
        confidence = novel_id.get("confidence") if novel_id else None
        
        print(f"\n[{_ts()}] ✅ Post {post_id} 완료 ({elapsed:.1f}s)", file=sys.stderr)
        print(f"    is_relevant: {is_relevant}", file=sys.stderr)
        if title:
            print(f"    official_title: {title}", file=sys.stderr)
            print(f"    confidence: {confidence}", file=sys.stderr)
        print(f"    reason: {identity.get('reason', 'N/A')}", file=sys.stderr)


def run_staged_pipeline(
    input_path: Path,
    output_path: Optional[Path] = None,
    limit: Optional[int] = None,
) -> None:
    """
    Run the staged pipeline on an input file.
    
    Args:
        input_path: Path to input JSON/JSONL file
        output_path: Path for output file (auto-generated if None)
        limit: Maximum number of posts to process
    """
    from .pipeline import _load_json_items, _partition_items
    
    # Load input
    raw_items = _load_json_items(input_path)
    posts, _ = _partition_items(raw_items)
    
    if limit:
        posts = posts[:limit]
    
    print(f"[{_ts()}] 📂 입력: {input_path} ({len(posts)}개 게시글)", file=sys.stderr)
    
    # Setup pipeline
    pipeline = StagedPipeline()
    
    # Setup output
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = pipeline.output_dir / f"staged_result_{timestamp}.json"
    
    results = []
    
    # Process each post
    for i, post in enumerate(posts, 1):
        print(f"\n[{_ts()}] 📊 진행: {i}/{len(posts)}", file=sys.stderr)
        
        result = pipeline.process_post(post)
        results.append(result.model_dump() if hasattr(result, 'model_dump') else result)
        
        # Save incrementally
        output_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    print(f"\n[{_ts()}] 💾 결과 저장: {output_path}", file=sys.stderr)
    print(f"[{_ts()}] ✨ 완료: {len(results)}개 처리됨", file=sys.stderr)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m llm_batch.staged_pipeline <input.json> [output.json] [limit]")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else None
    
    run_staged_pipeline(input_path, output_path, limit)
