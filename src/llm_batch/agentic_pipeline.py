"""
Agentic Pipeline entrypoint.
Runs expert orchestration and converts final context into output models.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .experts.orchestrator import Orchestrator, ExpertType, ConversationContext
from .experts.gatekeeper import GatekeeperExpert
from .experts.discourse import DiscourseAnalyzer
from .experts.decoder import DecoderExpert
from .experts.verifier import VerifierExpert
from .rules import OFFICIAL_PLATFORMS
from .experts.critic import CriticExpert
from .experts.arbiter import ArbiterExpert
from .models import PostInput, PickvelOutputItemV2, NovelIdentity, DetectedTitle, SentimentProfile, PickvelIdentity, PickvelAnalysis
from .rules import NOISE_TERMS, NOVEL_SITES, SLANG_DICTIONARY, TROPE_TERMS
from .llm.client import LLMClient
from .search.client import MCPClient


# Thread-local context for worker-aware logging
import threading
_thread_local = threading.local()
_log_lock = threading.Lock()

def _ts() -> str:
    wid = getattr(_thread_local, 'worker_id', None)
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    if wid is not None and getattr(_thread_local, 'parallel', 1) > 1:
        return f"{ts}|W{wid}"
    return ts


class AgenticPipeline:
    """Top-level pipeline for one post -> final structured output."""
    
    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        mcp: Optional[MCPClient] = None,
        output_dir: Optional[Path] = None,
        max_iterations: int = 10,  # Maximum expert iterations
        worker_id: int = 0,
        parallel_count: int = 1,
    ):
        self.llm = llm or LLMClient()
        self.mcp = mcp or MCPClient()
        self.output_dir = output_dir or Path("out")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_iterations = max_iterations
        self.worker_id = worker_id
        self.parallel_count = parallel_count
        
        # Expert instances
        self.experts = {
            ExpertType.GATEKEEPER: GatekeeperExpert(self.llm),
            ExpertType.DISCOURSE: DiscourseAnalyzer(self.llm),
            ExpertType.DECODER: DecoderExpert(self.llm),
            ExpertType.VERIFIER: VerifierExpert(self.llm),
            ExpertType.CRITIC: CriticExpert(self.llm),
            ExpertType.ARBITER: ArbiterExpert(self.llm),
        }
        
        # In-memory search cache (query -> compacted results)
        self._search_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._search_cache_hits = 0
        self._search_cache_misses = 0
        
        # Orchestrator
        self.orchestrator = Orchestrator(
            experts=self.experts,
            search_fn=self._search,
            fetch_fn=self._fetch,
            max_iterations=max_iterations,
            worker_id=worker_id,
            parallel_count=parallel_count,
        )
        
        # Rules config
        self.rules_config = {
            "novel_sites": NOVEL_SITES,
            "slang_dictionary": SLANG_DICTIONARY,
            "noise_terms": NOISE_TERMS,
            "trope_terms": TROPE_TERMS,
        }
        
        # Session knowledge sharing (disabled in parallel mode)
        self._use_session_knowledge = (parallel_count <= 1)
        self.session_knowledge = {
            "resolved_slang": {},
            "resolved_authors": {},
            "resolved_characters": {},
        }
    
    def _search(self, query: str) -> List[Dict[str, Any]]:
        """Run MCP search with in-memory query cache."""
        # Query cache lookup
        cache_key = query.strip().lower()
        if cache_key in self._search_cache:
            self._search_cache_hits += 1
            cached = self._search_cache[cache_key]
            print(
                  f"[{_ts()}] 🔁 검색 캐시 히트: '{query}' -> {len(cached)}건 "
                  f"(hit {self._search_cache_hits}/{self._search_cache_hits + self._search_cache_misses})",
                  file=sys.stderr)
            return cached
        
        self._search_cache_misses += 1
        
        try:
            raw = self.mcp.search(query)
            results = raw.get("results", []) if isinstance(raw, dict) else []
            
            # Compact results (top-k + content truncation)
            top_k = int(os.getenv("MCP_TOP_K_RESULTS", "10"))
            max_content = int(os.getenv("MCP_MAX_CONTENT_CHARS", "400"))
            
            # Compact results
            compacted = []
            for item in results[:top_k]:
                if not isinstance(item, dict):
                    continue
                content = item.get("content", "")
                if len(content) > max_content:
                    content = content[:max_content] + "..."
                compacted.append({
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "content": content,
                })
            
            # Cache store
            self._search_cache[cache_key] = compacted
            return compacted
        except Exception as e:
            print(f"[{_ts()}] 🔎 검색 오류: {e}", file=sys.stderr)
            return []
    
    def _fetch(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch URL details via MCP."""
        try:
            return self.mcp.fetch(url)
        except Exception as e:
            print(f"[{_ts()}] 🔗 fetch error: {url} -> {e}", file=sys.stderr)
            return None
    
    def process_post(self, post: PostInput) -> PickvelOutputItemV2:
        """
        Process a single post.
        
        Returns:
            PickvelOutputItemV2 with complete analysis
        """
        post_id = post.post_id
        start_time = time.time()
        
        # Set worker context for logs
        _thread_local.worker_id = self.worker_id
        _thread_local.parallel = self.parallel_count
        # Share worker context with expert utility logger
        from .experts.utils import set_worker_context
        set_worker_context(self.worker_id, self.parallel_count)
        
        print(f"\n{'='*70}", file=sys.stderr)
        print(f"[{_ts()}] 🚀 Agentic Pipeline start: Post {post_id} - {post.title[:50]}...", file=sys.stderr)
        print(f"{'='*70}", file=sys.stderr)
        
        # Prepare post payload for experts
        post_dict = self._post_to_dict(post)
        comments = self._extract_comments(post)
        
        try:
            # Run orchestrator
            ctx = self.orchestrator.process(
                post_data=post_dict,
                comments=comments,
                rules_config=self.rules_config,
            )
            
            # Share session knowledge
            if self._use_session_knowledge:
                ctx.session_knowledge = self.session_knowledge
            
            # Build output object
            result = self._context_to_output(ctx)
            
            # Update session knowledge if enabled
            if self._use_session_knowledge:
                self._update_session_knowledge(ctx, result)
            
            elapsed = time.time() - start_time
            
            # Token usage summary
            if hasattr(ctx, 'token_usage'):
                print(f"\n[{_ts()}] 📊 Post {post_id} token usage", file=sys.stderr)
                print(f"  prompt_tokens:     {ctx.token_usage['prompt_tokens']:,}", file=sys.stderr)
                print(f"  completion_tokens: {ctx.token_usage['completion_tokens']:,}", file=sys.stderr)
                print(f"  total_tokens:      {ctx.token_usage['total_tokens']:,}", file=sys.stderr)
            
            self._log_result(post_id, result, ctx, elapsed)
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[{_ts()}] ❌ processing error ({elapsed:.1f}s): {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return self._error_output(post_id, str(e))
    
    def _update_session_knowledge(self, ctx: ConversationContext, result: PickvelOutputItemV2) -> None:
        """
        Persist high-confidence session knowledge from a relevant result.

        This updates three maps:
        - resolved_slang: abbreviation/alias -> official title
        - resolved_authors: author name -> official title
        - resolved_characters: character -> official title
        """
        if not result.identity.is_relevant:
            return

        novel_identity = result.identity.novel_identity
        official_title = novel_identity.official_title if novel_identity else None
        confidence = (novel_identity.confidence if novel_identity else None) or "None"
        if not official_title:
            return

        # Avoid learning from weakly grounded outputs.
        discourse_warning = (getattr(ctx, "discourse_warning", "") or "").strip()
        verifier_out = ctx.get_expert_output(ExpertType.VERIFIER) or {}
        vf_result = verifier_out.get("verification_result") or {}
        grounding = vf_result.get("grounding_check") or {}
        anchor_found = str(grounding.get("anchor_found") or "none").lower()
        decoder_grounded = bool(grounding.get("decoder_grounded", True))

        if discourse_warning:
            print(
                f"[{_ts()}] session_knowledge skip (discourse_warning='{discourse_warning}'): "
                f"'{official_title}' ({confidence})",
                file=sys.stderr,
            )
            return

        if (not decoder_grounded) or (anchor_found in ("search_only", "none")):
            print(
                f"[{_ts()}] session_knowledge skip (weak grounding: "
                f"anchor={anchor_found}, decoder_grounded={decoder_grounded}): "
                f"'{official_title}' ({confidence})",
                file=sys.stderr,
            )
            return

        decoder_out = ctx.get_expert_output(ExpertType.DECODER) or {}
        decoded_terms = decoder_out.get("decoded_terms", [])
        if not isinstance(decoded_terms, list):
            decoded_terms = []

        def _conf_rank(value: Any) -> int:
            if isinstance(value, str):
                return {
                    "max": 4,
                    "high": 3,
                    "medium": 2,
                    "mid": 2,
                    "low": 1,
                    "none": 0,
                }.get(value.strip().lower(), 0)
            return 0

        current_conf_rank = _conf_rank(confidence)

        # 1) Learn slang/abbreviation mappings only from high-confidence outputs.
        if current_conf_rank >= 3:
            for term in decoded_terms:
                if not isinstance(term, dict):
                    continue

                slang_title = str(term.get("original") or "").strip()
                if not slang_title:
                    continue

                best_match = term.get("best_match") or {}
                if not isinstance(best_match, dict):
                    continue

                matched_title = best_match.get("title")
                if (
                    slang_title != official_title
                    and matched_title == official_title
                ):
                    existing = self.session_knowledge["resolved_slang"].get(slang_title, {})
                    existing_conf_rank = _conf_rank(existing.get("confidence", "none"))
                    if current_conf_rank >= existing_conf_rank:
                        self.session_knowledge["resolved_slang"][slang_title] = {
                            "official_title": official_title,
                            "confidence": confidence,
                            "post_id": ctx.post_id,
                        }
                        print(
                            f"[{_ts()}] session_knowledge update: "
                            f"'{slang_title}' -> '{official_title}' ({confidence})",
                            file=sys.stderr,
                        )
        else:
            print(
                f"[{_ts()}] session_knowledge skip (low confidence): "
                f"'{official_title}' ({confidence})",
                file=sys.stderr,
            )

        # 2) Learn author -> official title mapping.
        detected_author = None
        for term in decoded_terms:
            if not isinstance(term, dict):
                continue
            if not term.get("is_author_name"):
                continue
            author_info = term.get("author_info")
            if isinstance(author_info, dict):
                detected_author = author_info.get("author_name") or author_info.get("name")
            elif isinstance(author_info, str):
                detected_author = author_info
            if detected_author:
                break

        if detected_author:
            self.session_knowledge["resolved_authors"][str(detected_author)] = official_title

        # 3) Learn top character mentions from Gatekeeper.
        gatekeeper_out = ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
        detected_entities = gatekeeper_out.get("detected_entities") or {}
        possible_characters = detected_entities.get("possible_characters") or []
        if isinstance(possible_characters, list):
            for char in possible_characters[:3]:
                char_text = str(char).strip()
                if char_text:
                    self.session_knowledge["resolved_characters"][char_text] = official_title
    
    def _post_to_dict(self, post: PostInput) -> Dict[str, Any]:
        """Convert PostInput to dict."""
        content_blocks = []
        for block in post.content_blocks:
            if isinstance(block, dict):
                content_blocks.append(block)
            else:
                content_blocks.append({"type": "text", "text": str(block)})
        
        return {
            "post_id": post.post_id,
            "title": post.title,
            "author": post.author,
            "url": post.url,
            "content_blocks": content_blocks,
            "gallery_id": getattr(post, "gallery_id", ""),
        }
    
    def _extract_comments(self, post: PostInput) -> List[str]:
        """Extract comments from post."""
        comments = []
        for c in getattr(post, "comments", []):
            if isinstance(c, dict):
                text = c.get("content") or c.get("text") or ""
            else:
                text = str(c)
            if text.strip():
                comments.append(text.strip())
        return comments[:15]  # max 15 comments
    
    def _context_to_output(self, ctx: ConversationContext) -> PickvelOutputItemV2:
        """Convert context to PickvelOutputItemV2."""
        arbiter_out = ctx.get_expert_output(ExpertType.ARBITER) or {}
        final_decision = arbiter_out.get("final_decision", {})
        metadata = arbiter_out.get("metadata_synthesis", {})
        
        # Verifier output (fallback)
        verifier_out = ctx.get_expert_output(ExpertType.VERIFIER) or {}
        vf_result = verifier_out.get("verification_result", {})
        
        # Final relevance
        is_relevant = final_decision.get("is_relevant", vf_result.get("is_relevant", False))
        
        # If Arbiter deliberately nullified title, do not restore from verifier.
        _title_deliberately_null = final_decision.get("_title_deliberately_null", False)
        
        # Normalize official title
        if _title_deliberately_null:
            # Keep title null as explicitly requested by Arbiter.
            official_title = None
            print(
                f"[{_ts()}] arbiter deliberate null title: "
                f"_title_deliberately_null=True -> keep official_title=null",
                file=sys.stderr
            )
        else:
            official_title = final_decision.get("official_novel_title") or \
                            final_decision.get("official_title") or \
                            (vf_result.get("novel_identity") or {}).get("official_novel_title") or \
                            (vf_result.get("novel_identity") or {}).get("official_title")
        
        heretic_url = final_decision.get("heretic_url") or \
                        (vf_result.get("novel_identity") or {}).get("heretic_url") if not _title_deliberately_null else \
                        final_decision.get("heretic_url")
        confidence = final_decision.get("confidence", "None")
        
        # Final title correction from evidence pool
        if official_title:
            official_title = self._correct_title_final(official_title, ctx)
        
        # Discussion type normalization
        discussion_type = final_decision.get("discussion_type") or \
                         final_decision.get("post_type")  # fallback alias
        # Validate discussion type
        valid_types = {"review", "spoiler", "anticipation", "meme", "author_talk", 
                      "character_talk", "general", "meta", "recommendation", "trope_discussion",
                      "community_banter", "genre_opinion", "image_post", "off_topic", "noise"}
        if discussion_type not in valid_types:
            # Legacy type mapping
            type_mapping = {
                "work_discussion": "review",
                "author_criticism": "author_talk",
                "genre_discussion": "trope_discussion",
            }
            discussion_type = type_mapping.get(discussion_type, "general" if is_relevant else "noise")
        
        # Propagate gatekeeper genre_discussion when no entities exist.
        gatekeeper_out = ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
        gk_post_type = gatekeeper_out.get("post_type", "")
        gk_entities = gatekeeper_out.get("detected_entities") or {}
        gk_has_entities = bool(
            (gk_entities.get("possible_titles") or [])
            or (gk_entities.get("possible_authors") or [])
            or (gk_entities.get("possible_characters") or [])
        )
        if gk_post_type == "genre_discussion" and not gk_has_entities:
            if discussion_type not in ("noise", "trope_discussion", "genre_opinion"):
                print(
                    f"[{_ts()}] gatekeeper genre_discussion propagation: "
                    f"discussion_type='{discussion_type}' -> 'trope_discussion'",
                    file=sys.stderr
                )
                discussion_type = "trope_discussion"
        
        # Gatekeeper community_banter / image_post propagation guards.
        _work_identified_types = {
            "anticipation",
            "review",
            "spoiler",
            "character_talk",
            "meme",
            "general",
            "general_discussion",
        }
        suspected_titles = getattr(ctx, "suspected_titles", []) or []

        def _confidence_rank(conf_val: Any) -> int:
            if isinstance(conf_val, (int, float)):
                value = float(conf_val)
                if value >= 0.7:
                    return 3
                if value >= 0.5:
                    return 2
                if value >= 0.3:
                    return 1
                return 0
            if isinstance(conf_val, str):
                mapping = {"high": 3, "max": 3, "medium": 2, "mid": 2, "low": 1, "none": 0}
                return mapping.get(conf_val.strip().lower(), 0)
            return 0

        strong_suspected_titles = [
            st for st in suspected_titles
            if isinstance(st, dict)
            and st.get("title")
            and _confidence_rank(st.get("confidence")) >= 2
        ]
        has_strong_suspected_title = bool(strong_suspected_titles)
        strong_suspected_title = strong_suspected_titles[0].get("title") if has_strong_suspected_title else None

        vf_author_info = vf_result.get("author_info") or {}
        vf_detected_author = ""
        if isinstance(vf_author_info, dict):
            vf_detected_author = str(vf_author_info.get("detected_author") or "").strip()
        vf_grounding = vf_result.get("grounding_check") or {}
        vf_anchor = str(vf_grounding.get("anchor_found") or "").lower()
        has_work_anchor = vf_anchor in {
            "title_mention",
            "author_mention",
            "character_title_link",
            "character_mention",
            "plot_mention",
        }
        null_title_strong_work_evidence = (
            _title_deliberately_null
            and is_relevant
            and discussion_type in _work_identified_types
            and (has_strong_suspected_title or bool(vf_detected_author) or has_work_anchor)
        )
        _banter_override_blocked = (
            gk_post_type == "community_banter"
            and (
                (is_relevant and bool(official_title))
                or null_title_strong_work_evidence
                or (
                    is_relevant
                    and discussion_type in _work_identified_types
                    and has_strong_suspected_title
                )
            )
        )
        if gk_post_type == "community_banter" and discussion_type not in (
            "noise", "community_banter", "off_topic"
        ):
            if _banter_override_blocked:
                print(
                    f"[{_ts()}] community_banter override blocked: "
                    f"gatekeeper=community_banter but work evidence is strong"
                    f" (title='{official_title}', suspect='{strong_suspected_title}', "
                    f"author='{vf_detected_author}', anchor='{vf_anchor}', type='{discussion_type}')"
                    f" -> keep arbiter discussion_type",
                    file=sys.stderr
                )
            else:
                print(
                    f"[{_ts()}] gatekeeper community_banter propagation: "
                    f"discussion_type='{discussion_type}' -> 'community_banter'",
                    file=sys.stderr
                )
                discussion_type = "community_banter"
        
        if gk_post_type == "image_post" and not official_title and discussion_type not in (
            "noise", "image_post"
        ):
            print(
                f"[{_ts()}] gatekeeper image_post propagation: "
                f"discussion_type='{discussion_type}' -> 'image_post'",
                file=sys.stderr
            )
            discussion_type = "image_post"
        
        # discussion_type consistency with is_relevant
        always_irrelevant_types = {
            "noise",
            "meta",
            "author_talk",
            "recommendation",
            "trope_discussion",
            "community_banter",
            "genre_opinion",
            "image_post",
            "off_topic",
        }
        work_relevant_types = {
            "general",
            "review",
            "spoiler",
            "anticipation",
            "meme",
            "character_talk",
            "general_discussion",
        }

        if discussion_type in always_irrelevant_types:
            # 🔧 Phase27-C: is_relevant=True + 제목/증거 있음 → irrelevant 타입이어도 rescue
            _rescue_irrelevant_with_evidence = (
                is_relevant
                and bool(official_title)
                and discussion_type in always_irrelevant_types
            )
            recover_work_type_from_banter = (
                discussion_type == "community_banter"
                and _title_deliberately_null
                and is_relevant
                and (has_strong_suspected_title or bool(vf_detected_author) or has_work_anchor)
            )
            if _rescue_irrelevant_with_evidence:
                # Arbiter가 강제 승격 + title 적용까지 했는데, discussion_type만 교정 안 된 경우
                recovered_type = "general"
                print(
                    f"[{_ts()}] rescue: is_relevant=True + title='{official_title}' "
                    f"but discussion_type='{discussion_type}' -> '{recovered_type}' "
                    f"(Arbiter 강제승격 후 discussion_type 미교정 보정)",
                    file=sys.stderr,
                )
                discussion_type = recovered_type
            elif recover_work_type_from_banter:
                recovered_type = final_decision.get("discussion_type")
                if recovered_type not in _work_identified_types:
                    recovered_type = "general"
                print(
                    f"[{_ts()}] rescue: title=null with strong work evidence "
                    f"discussion_type='community_banter' -> '{recovered_type}' "
                    f"(suspect='{strong_suspected_title}', author='{vf_detected_author}', anchor='{vf_anchor}')",
                    file=sys.stderr,
                )
                discussion_type = recovered_type
            else:
                if is_relevant:
                    print(
                        f"[{_ts()}] consistency correction: discussion_type='{discussion_type}' -> is_relevant=false",
                        file=sys.stderr,
                    )
                print(
                    f"[{_ts()}] force non-relevant for non-work type: "
                    f"is_relevant=false + discussion_type='{discussion_type}' -> 'noise'",
                    file=sys.stderr,
                )
                is_relevant = False
                discussion_type = "noise"
                official_title = None
        elif is_relevant and discussion_type == "noise":
            discussion_type = "general"
        elif (not is_relevant) and discussion_type in work_relevant_types:
            print(
                f"[{_ts()}] consistency correction: is_relevant=false + "
                f"discussion_type='{discussion_type}' -> 'noise'",
                file=sys.stderr,
            )
            discussion_type = "noise"
        
        # Confidence normalization
        confidence = self._normalize_confidence(confidence)
        
        # Validate heretic_url against known search evidence.
        if heretic_url:
            heretic_url = self._validate_heretic_url(heretic_url, ctx)
        
        # Build NovelIdentity only for relevant outputs.
        novel_identity = None
        if is_relevant and (official_title or heretic_url):
            novel_identity = NovelIdentity(
                official_title=official_title,
                heretic_url=heretic_url,
                confidence=confidence,
            )
        
        # Reason synthesis
        reason = final_decision.get("final_reasoning") or arbiter_out.get("final_reasoning", "")
        
        # Fallback 1: conflict resolution reasoning
        if not reason:
            conflict_res = arbiter_out.get("conflict_resolution", [])
            if conflict_res and isinstance(conflict_res, list) and len(conflict_res) > 0:
                first_conflict = conflict_res[0]
                if isinstance(first_conflict, dict):
                    reason = first_conflict.get("reasoning", "") or first_conflict.get("arbiter_decision", "")
        
        # Fallback 2: final_decision.reason
        if not reason:
            reason = final_decision.get("reason", "")
        
        # Fallback 3: verifier reason
        if not reason:
            if not is_relevant:
                verification_result = vf_result.get("verification_result", {}) if vf_result else {}
                reason = verification_result.get("rejection_reason") or vf_result.get("reason", "")
            else:
                reason = vf_result.get("reason", "")

        # Fallback 4: gatekeeper noise reason
        if not reason:
            gk = ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
            if gk.get("is_noise"):
                reason = gk.get("noise_reason", "noise detected")

        # Fallback 5: deterministic default reason
        if not reason:
            if is_relevant and official_title:
                reason = (
                    f"작품 관련으로 판정되었습니다: '{official_title}'. "
                    f"discussion_type={discussion_type}."
                )
            elif is_relevant:
                reason = f"작품 관련으로 판정되었습니다. discussion_type={discussion_type}."
            else:
                reason = f"비관련 포스트로 판정되었습니다. discussion_type={discussion_type}."

        # Keep reason aligned with final relevance flags.
        reason = self._sanitize_reason(
            reason,
            is_relevant=is_relevant,
            discussion_type=discussion_type,
            official_title=official_title,
        )
        
        # DetectedTitle output
        detected_titles = []
        if official_title:
            detected_titles.append(DetectedTitle(
                official_title=official_title,
                heretic_url=heretic_url,
                confidence=confidence,
                alias_or_mention=None,
            ))
        
        # SentimentProfile output
        sentiment = self._normalize_sentiment(metadata.get("sentiment"))
        sentiment_profile = None
        if sentiment and sentiment != "Unknown":
            sentiment_profile = SentimentProfile(
                sentiment=sentiment,
                pacing="Unknown",
                drift_risk="Unknown",
            )
        
        # PickvelIdentity output
        identity = PickvelIdentity(
            is_relevant=is_relevant,
            novel_identity=novel_identity,
            discussion_type=discussion_type,  # normalized discussion type
            reason=reason if reason else None,
        )
        
        # PickvelAnalysis output
        analysis = None
        if detected_titles or metadata.get("micro_tags"):
            analysis = PickvelAnalysis(
                detected_titles=detected_titles if detected_titles else [],
                micro_tags=metadata.get("micro_tags", []),
                sentiment_profile=sentiment_profile,
                is_nsfw=bool(metadata.get("is_nsfw") or False),
            )
        
        return PickvelOutputItemV2(
            post_id=ctx.post_id,
            identity=identity,
            analysis=analysis,
        )

    @staticmethod
    def _normalize_sentiment(sentiment: Any) -> str:
        """
        Normalize sentiment label into allowed literal set.
        Handles noisy values like "Negative (Fear/Disgust)".
        """
        if not isinstance(sentiment, str) or not sentiment.strip():
            return "Unknown"

        s = sentiment.strip()
        valid = {"Positive", "Neutral", "Negative", "Mixed", "Unknown"}
        if s in valid:
            return s

        low = s.lower()
        if "positive" in low:
            return "Positive"
        if "negative" in low:
            return "Negative"
        if "neutral" in low:
            return "Neutral"
        if "mixed" in low:
            return "Mixed"
        return "Unknown"

    @staticmethod
    def _sanitize_reason(
        reason: str,
        *,
        is_relevant: bool,
        discussion_type: Optional[str],
        official_title: Optional[str],
    ) -> str:
        if not isinstance(reason, str) or not reason.strip():
            return reason

        low = reason.lower()
        true_markers = [
            "is_relevant=true",
            "is_relevant = true",
            "is_relevant는 true",
            "is novel discussion",
            "관련 포스트로 판정",
            "종합 판정: 관련 포스트",
        ]
        false_markers = [
            "is_relevant=false",
            "is_relevant = false",
            "is_relevant는 false",
            "is not relevant",
            "비관련 포스트로 판정",
            "종합 판정: 비관련 포스트",
            "노이즈로 분류",
        ]
        mentions_true = any(marker in low for marker in true_markers)
        mentions_false = any(marker in low for marker in false_markers)

        dt = discussion_type or "general"
        if is_relevant and mentions_false:
            if official_title:
                return (
                    f"관련 포스트로 판정됨: '{official_title}'. discussion_type={dt}. "
                    f"(reason 정합성 교정: 원문 reason에 is_relevant=false 표기)"
                )
            return (
                f"관련 포스트로 판정됨. discussion_type={dt}. "
                f"(reason 정합성 교정: 원문 reason에 is_relevant=false 표기)"
            )
        if (not is_relevant) and mentions_true:
            return (
                f"비관련 포스트로 판정됨. discussion_type={dt}. "
                f"(reason 정합성 교정: 원문 reason에 is_relevant=true 표기)"
            )

        return reason

    def _validate_heretic_url(self, url: str, ctx) -> Optional[str]:
        if not url:
            return None

        search_results = getattr(ctx, "search_results", None) or []
        identified_title = self._get_identified_title(ctx)
        url_norm = url.split("?")[0].rstrip("/").lower()

        for sr in search_results:
            sr_url = (sr.get("url") or "").split("?")[0].rstrip("/").lower()
            if not sr_url:
                continue
            if url_norm == sr_url or url_norm in sr_url or sr_url in url_norm:
                if self._is_sr_related_to_title(sr, identified_title):
                    return url
                break

        for expert_url in self._collect_expert_urls(ctx):
            eu_norm = expert_url.split("?")[0].rstrip("/").lower()
            for sr in search_results:
                sr_url = (sr.get("url") or "").split("?")[0].rstrip("/").lower()
                if not sr_url:
                    continue
                if eu_norm == sr_url or eu_norm in sr_url or sr_url in eu_norm:
                    if self._is_sr_related_to_title(sr, identified_title):
                        return expert_url

        if identified_title:
            matched_url = self._find_title_matched_official_url(identified_title, search_results)
            if matched_url:
                return matched_url

        return None

    def _is_sr_related_to_title(self, sr: dict, title: Optional[str]) -> bool:
        if not title:
            return True

        sr_text = ((sr.get("title") or "") + " " + (sr.get("content") or "")).lower()
        title_lower = title.lower()
        if title_lower in sr_text:
            return True

        import re

        title_words = [word for word in re.split(r"\s+", title_lower) if len(word) >= 2]
        if title_words:
            matched = sum(1 for word in title_words if word in sr_text)
            if matched >= max(1, len(title_words) // 2):
                return True

        for n in range(min(4, len(title_lower)), 1, -1):
            prefix = title_lower[:n]
            if len(prefix) >= 2 and prefix in sr_text:
                return True

        return False

    def _get_identified_title(self, ctx) -> Optional[str]:
        arbiter_out = ctx.get_expert_output(ExpertType.ARBITER) or {}
        final_decision = arbiter_out.get("final_decision") or {}
        title = final_decision.get("official_novel_title") or final_decision.get("official_title")
        if title:
            return title

        decoder_out = ctx.get_expert_output(ExpertType.DECODER) or {}
        for term in decoder_out.get("decoded_terms", []):
            best = term.get("best_match") or {}
            if best.get("title"):
                return best["title"]

        verifier_out = ctx.get_expert_output(ExpertType.VERIFIER) or {}
        novel_identity = (verifier_out.get("verification_result") or {}).get("novel_identity") or {}
        return novel_identity.get("official_novel_title") or novel_identity.get("official_title")

    def _collect_expert_urls(self, ctx) -> list[str]:
        urls: list[str] = []

        decoder_out = ctx.get_expert_output(ExpertType.DECODER) or {}
        for term in decoder_out.get("decoded_terms", []):
            for candidate in term.get("candidates", []):
                candidate_url = candidate.get("url")
                if candidate_url:
                    urls.append(candidate_url)

        verifier_out = ctx.get_expert_output(ExpertType.VERIFIER) or {}
        novel_identity = (verifier_out.get("verification_result") or {}).get("novel_identity") or {}
        verifier_url = novel_identity.get("heretic_url")
        if verifier_url:
            urls.append(verifier_url)

        def _platform_priority(url: str) -> int:
            for index, platform in enumerate(OFFICIAL_PLATFORMS):
                if platform in url:
                    return index
            return 999

        deduped = []
        seen = set()
        for url in urls:
            if url not in seen:
                seen.add(url)
                deduped.append(url)
        deduped.sort(key=_platform_priority)
        return deduped

    def _find_title_matched_official_url(
        self,
        title: str,
        search_results: list[dict],
    ) -> Optional[str]:
        import re

        title_words = [word for word in re.split(r"\s+", title) if len(word) >= 2]

        for sr in search_results:
            sr_url = sr.get("url") or ""
            if not any(platform in sr_url for platform in OFFICIAL_PLATFORMS):
                continue
            sr_text = (sr.get("title") or "") + " " + (sr.get("content") or "")
            if title in sr_text:
                return sr_url

        if len(title_words) >= 2:
            for sr in search_results:
                sr_url = sr.get("url") or ""
                if not any(platform in sr_url for platform in OFFICIAL_PLATFORMS):
                    continue
                sr_text = (sr.get("title") or "") + " " + (sr.get("content") or "")
                matched = sum(1 for word in title_words if word in sr_text)
                if matched >= min(2, len(title_words)):
                    return sr_url

        return None

    def _correct_title_final(self, title: str, ctx) -> str:
        candidates: list[str] = []

        decoder_out = ctx.get_expert_output(ExpertType.DECODER) or {}
        for term in decoder_out.get("decoded_terms", []):
            best = term.get("best_match") or {}
            if best.get("title"):
                candidates.append(best["title"])
            for candidate in term.get("candidates", []):
                candidate_title = candidate.get("official_novel_title")
                if candidate_title:
                    candidates.append(candidate_title)

        for sr in getattr(ctx, "search_results", []) or []:
            sr_title = sr.get("title")
            if isinstance(sr_title, str) and sr_title.strip():
                candidates.append(sr_title.strip())

        if not candidates:
            return title

        if title in candidates:
            return title

        from difflib import SequenceMatcher

        normalized = title.replace(" ", "").lower()
        best_candidate = title
        best_score = 0.0
        for candidate in set(candidates):
            if not isinstance(candidate, str):
                continue
            cand_norm = candidate.replace(" ", "").lower()
            if not cand_norm:
                continue
            score = SequenceMatcher(None, normalized, cand_norm).ratio()
            if score > best_score:
                best_score = score
                best_candidate = candidate

        if best_score >= 0.80:
            print(
                f"[{_ts()}] final title corrected: '{title}' -> '{best_candidate}' (score={best_score:.2f})",
                file=sys.stderr,
            )
            return best_candidate

        return title

    @staticmethod
    def _is_similar_title(title_a: str, title_b: str) -> bool:
        if abs(len(title_a) - len(title_b)) > 4:
            return False
        from difflib import SequenceMatcher
        return SequenceMatcher(None, title_a, title_b).ratio() >= 0.80

    @staticmethod
    def _normalize_confidence(conf: str) -> str:
        if not conf:
            return "None"

        conf_lower = str(conf).lower()
        if conf_lower in ("max", "high"):
            return "High"
        if conf_lower in ("mid", "medium"):
            return "Medium"
        if conf_lower in ("low",):
            return "Low"
        return "None"

    def _error_output(self, post_id: int, error: str) -> PickvelOutputItemV2:
        """Return fallback output on error."""
        return PickvelOutputItemV2(
            post_id=post_id,
            identity=PickvelIdentity(
                is_relevant=False,
                reason=f"처리 오류: {error}",
            ),
            analysis=None,
        )
    
    def _log_result(
        self,
        post_id: int,
        result: PickvelOutputItemV2,
        ctx: ConversationContext,
        elapsed: float,
    ) -> None:
        """Log final result summary."""
        print(f"\n[{_ts()}] {'='*50}", file=sys.stderr)
        print(f"[{_ts()}] ✅ Post {post_id} 완료 ({elapsed:.1f}s, {ctx.iteration} iterations)", file=sys.stderr)
        print(f"[{_ts()}]    is_relevant: {result.identity.is_relevant}", file=sys.stderr)
        if result.identity.novel_identity:
            print(f"[{_ts()}]    official_title: {result.identity.novel_identity.official_title}", file=sys.stderr)
            print(f"[{_ts()}]    confidence: {result.identity.novel_identity.confidence}", file=sys.stderr)
        print(f"[{_ts()}]    reason: {result.identity.reason or ''}", file=sys.stderr)
        
        # Expert consensus summary
        arbiter = ctx.get_expert_output(ExpertType.ARBITER) or {}
        consensus = arbiter.get("expert_consensus", {})
        if consensus:
            print(f"[{_ts()}]    unanimous: {consensus.get('unanimous')}", file=sys.stderr)
            print(f"[{_ts()}]    agreeing: {consensus.get('agreeing_experts', [])}", file=sys.stderr)
        print(f"[{_ts()}] {'='*50}", file=sys.stderr)


def run_agentic_pipeline(
    input_path: Path,
    output_path: Optional[Path] = None,
    limit: Optional[int] = None,
    mcp_endpoint: Optional[str] = None,
) -> None:
    """
    Run the full agentic pipeline from input JSON.
    """
    from .pipeline import _load_json_items, _partition_items
    
    # Load input posts
    raw_items = _load_json_items(input_path)
    posts, _ = _partition_items(raw_items)
    
    if limit:
        posts = posts[:limit]
    
    print(f"[{_ts()}] 📂 입력 로드: {input_path} ({len(posts)} posts)", file=sys.stderr)
    
    # Initialize pipeline
    llm = LLMClient()
    mcp = MCPClient(endpoint=mcp_endpoint) if mcp_endpoint else MCPClient()
    pipeline = AgenticPipeline(llm=llm, mcp=mcp)
    
    # Resolve output path
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = pipeline.output_dir / f"agentic_result_{timestamp}.json"
    
    results = []
    
    # Process posts
    for i, post in enumerate(posts, 1):
        print(f"\n[{_ts()}] ▶ 처리 진행: {i}/{len(posts)}", file=sys.stderr)
        
        result = pipeline.process_post(post)
        results.append(result.model_dump() if hasattr(result, "model_dump") else result)
        
        # Flush incremental output
        output_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    print(f"\n[{_ts()}] 💾 결과 저장 완료: {output_path}", file=sys.stderr)
    
    # Summary
    relevant = sum(1 for r in results if r.get("is_relevant"))
    identified = sum(1 for r in results if r.get("novel_identity", {}).get("official_title"))
    print(f"\n[{_ts()}] 📌 Summary:", file=sys.stderr)
    print(f"   Total: {len(results)}", file=sys.stderr)
    print(f"   Relevant: {relevant}", file=sys.stderr)
    print(f"   Identified: {identified}", file=sys.stderr)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m llm_batch.agentic_pipeline <input.json> [output.json] [limit]")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else None
    
    run_agentic_pipeline(input_path, output_path, limit)

