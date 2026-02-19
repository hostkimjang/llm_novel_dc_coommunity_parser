"""
Agentic Pipeline entrypoint.
Runs expert orchestration and converts final context into output models.
"""

from __future__ import annotations

import json
import os
import sys
import time
import textwrap
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
from .experts.synthesizer import SynthesizerExpert
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


# 제목에 직접 등장하는 검증 약칭 -> 정식 작품명 강제 매핑(후처리 안전장치)
KNOWN_TITLE_ABBREVIATIONS = {
    "아생갤": "아카데미 생존 갤러리",
    "아카생존": "아카데미 생존 갤러리",
    "아카생갤": "아카데미 생존 갤러리",
}


def _norm_domain_text(text: str) -> str:
    import re as _re_local
    return _re_local.sub(r"\s+", "", str(text or "").lower())


_DOMAIN_KEYWORDS = {
    "martial": {"무림", "강호", "협객", "협녀", "협", "수선", "선협"},
    "game": {"게임", "퀘스트", "튜토리얼", "레벨", "스킬", "랭킹", "길드", "로그인", "파밍", "npc"},
}


def _detect_domain_groups(text: str) -> set[str]:
    norm = _norm_domain_text(text)
    groups: set[str] = set()
    if not norm:
        return groups
    for group, kws in _DOMAIN_KEYWORDS.items():
        if any(kw in norm for kw in kws):
            groups.add(group)
    return groups


def _has_domain_conflict_for_mapping(source_term: str, candidate_title: str) -> bool:
    src_groups = _detect_domain_groups(source_term)
    cand_groups = _detect_domain_groups(candidate_title)
    if not src_groups or not cand_groups:
        return False
    if "martial" in src_groups and "game" in cand_groups and "martial" not in cand_groups:
        return True
    if "game" in src_groups and "martial" in cand_groups and "game" not in cand_groups:
        return True
    return False


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
            ExpertType.SYNTHESIZER: SynthesizerExpert(self.llm),
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

        # reason 합성 시 LLM 재검토 단계 (기본 활성)
        self.enable_reason_llm_review = os.getenv("PIPELINE_REASON_LLM_REVIEW", "1") == "1"
        self.reason_llm_review_min_candidates = max(
            1,
            int(os.getenv("PIPELINE_REASON_LLM_REVIEW_MIN_CANDIDATES", "2")),
        )
        # reason "다 설명 모드": 후보/근거 문자열 축약 비활성화 + 더 많은 근거 노출
        self.reason_full_mode = os.getenv(
            "PIPELINE_REASON_FULL_MODE",
            os.getenv("REASON_FULL_MODE", "1"),
        ) == "1"
        self.reason_full_candidate_cap = max(
            6,
            int(os.getenv("PIPELINE_REASON_FULL_CANDIDATE_CAP", "24")),
        )
        self.reason_wrap_width = max(
            70,
            int(os.getenv("PIPELINE_REASON_WRAP_WIDTH", "92")),
        )
        # heretic_url 후보 검증 시, fetched_page_info가 비어 있으면 1회 직접 fetch 시도
        self.enable_heretic_live_fetch = os.getenv("PIPELINE_HERETIC_LIVE_FETCH", "1") == "1"
        self._heretic_fetch_cache: Dict[str, Optional[Dict[str, Any]]] = {}
        
        # Session knowledge sharing (disabled in parallel mode)
        self._use_session_knowledge = (parallel_count <= 1)
        self.session_knowledge = {
            "resolved_slang": {},
            "pending_slang": {},
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

        # 🆕 session_knowledge 저장 조건 완화:
        # character_mention 앵커가 있으면, 캐릭터가 검색에서 작품과 연결 검증됐을 가능성이 높으므로 저장 허용
        # 또한 제목에 key_term이 있고 그 key_term이 약칭으로 해석된 경우도 허용
        _has_character_anchor = anchor_found == "character_mention"
        _has_title_anchor = anchor_found == "title_mention"
        _anchor_is_useful = _has_character_anchor or _has_title_anchor

        if (not decoder_grounded) and (not _anchor_is_useful):
            print(
                f"[{_ts()}] session_knowledge skip (weak grounding: "
                f"anchor={anchor_found}, decoder_grounded={decoder_grounded}): "
                f"'{official_title}' ({confidence})",
                file=sys.stderr,
            )
            return

        if _anchor_is_useful and not decoder_grounded:
            print(
                f"[{_ts()}] session_knowledge accepted (anchor={anchor_found} despite "
                f"decoder_grounded=False): '{official_title}' ({confidence})",
                file=sys.stderr,
            )

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

        # 추가 안전장치: 단일 전문가 과신호 대신 다중 증거 결속이 있는 경우에만 학습.
        _commitment = self._compute_title_commitment(ctx, official_title, vf_result)
        if not self._is_title_commitment_medium(_commitment):
            print(
                f"[{_ts()}] session_knowledge skip (weak commitment): "
                f"title='{official_title}', score={_commitment.get('score')}, "
                f"official={_commitment.get('official_evidence')}, "
                f"title_in_post={_commitment.get('title_in_context')}, "
                f"bucket={_commitment.get('bucket_score')}",
                file=sys.stderr,
            )
            return

        # 1) Learn slang/abbreviation mappings with 2-stage promotion:
        # pending_slang(누적 검증) -> resolved_slang(실사용).
        # 프롬프트를 건드리지 않고, 커뮤니티 잡신호 학습 오염만 줄인다.
        if current_conf_rank >= 2:
            pending_slang = self.session_knowledge.setdefault("pending_slang", {})
            resolved_slang = self.session_knowledge.setdefault("resolved_slang", {})
            _fast_promote = (current_conf_rank >= 3) and self._is_title_commitment_strong(_commitment)
            _promote_hits = 1 if _fast_promote else 2

            for term in decoded_terms:
                if not isinstance(term, dict):
                    continue

                slang_title = str(term.get("original") or "").strip()
                if not slang_title or len(slang_title) < 2:
                    continue

                best_match = term.get("best_match") or {}
                if not isinstance(best_match, dict):
                    continue

                matched_title = best_match.get("title")
                if slang_title == official_title or matched_title != official_title:
                    continue
                if _has_domain_conflict_for_mapping(slang_title, official_title):
                    print(
                        f"[{_ts()}] session_knowledge skip (domain conflict): "
                        f"'{slang_title}' -> '{official_title}'",
                        file=sys.stderr,
                    )
                    continue

                slang_key = self._normalize_match_text(slang_title) or slang_title.lower().strip()
                if not slang_key:
                    continue

                entry = pending_slang.get(slang_key, {})
                if not isinstance(entry, dict) or entry.get("official_title") != official_title:
                    entry = {
                        "official_title": official_title,
                        "confidence": confidence,
                        "post_id": ctx.post_id,
                        "hits": 0,
                        "sample_term": slang_title,
                        "last_commitment_score": 0,
                    }

                entry["hits"] = int(entry.get("hits", 0)) + 1
                entry["post_id"] = ctx.post_id
                entry["confidence"] = confidence
                entry["sample_term"] = slang_title
                entry["last_commitment_score"] = int(_commitment.get("score", 0))
                pending_slang[slang_key] = entry

                if int(entry.get("hits", 0)) >= _promote_hits:
                    existing = resolved_slang.get(slang_key, {})
                    existing_conf_rank = _conf_rank(existing.get("confidence", "none"))
                    if current_conf_rank >= existing_conf_rank:
                        resolved_slang[slang_key] = {
                            "official_title": official_title,
                            "confidence": confidence,
                            "post_id": ctx.post_id,
                            "sample_term": slang_title,
                        }
                        print(
                            f"[{_ts()}] session_knowledge promote: "
                            f"'{slang_title}'({slang_key}) -> '{official_title}' "
                            f"(hits={entry.get('hits')}, conf={confidence}, score={_commitment.get('score')})",
                            file=sys.stderr,
                        )
                    pending_slang.pop(slang_key, None)
                else:
                    print(
                        f"[{_ts()}] session_knowledge pending: "
                        f"'{slang_title}'({slang_key}) -> '{official_title}' "
                        f"(hits={entry.get('hits')}/{_promote_hits}, conf={confidence})",
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

        detected_author = self._normalize_author_candidate(detected_author)
        if detected_author:
            self.session_knowledge["resolved_authors"][detected_author] = official_title

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
        if isinstance(metadata, dict):
            _raw_author_meta = metadata.get("detected_author")
            _norm_author_meta = self._normalize_author_candidate(_raw_author_meta)
            if _norm_author_meta and _norm_author_meta != _raw_author_meta:
                metadata["detected_author"] = _norm_author_meta
                print(
                    f"[{_ts()}] 🧹 detected_author 정규화: "
                    f"'{_raw_author_meta}' -> '{_norm_author_meta}'",
                    file=sys.stderr,
                )

        # Verifier output (fallback)
        verifier_out = ctx.get_expert_output(ExpertType.VERIFIER) or {}
        vf_result = verifier_out.get("verification_result", {})
        
        # Final relevance
        is_relevant = final_decision.get("is_relevant", vf_result.get("is_relevant", False))
        
        # If Arbiter deliberately nullified title, do not restore from verifier.
        _title_deliberately_null = final_decision.get("_title_deliberately_null", False)
        _arb_official_title = final_decision.get("official_title")
        _arb_official_novel_title = final_decision.get("official_novel_title")
        
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
            # 중요: Arbiter 후처리에서 official_title을 교정할 수 있으므로
            # official_novel_title보다 official_title을 우선한다.
            official_title = _arb_official_title or \
                            _arb_official_novel_title or \
                            (vf_result.get("novel_identity") or {}).get("official_novel_title") or \
                            (vf_result.get("novel_identity") or {}).get("official_title")

            # Arbiter가 두 title 필드를 서로 다르게 내보낸 경우(LLM 원출력 vs 후처리 교정)
            # 후처리 교정값(official_title)을 canonical로 강제한다.
            try:
                _norm = lambda s: str(s or "").replace(" ", "").lower()
                if _arb_official_title and _arb_official_novel_title and _norm(_arb_official_title) != _norm(_arb_official_novel_title):
                    official_title = _arb_official_title
                    print(
                        f"[{_ts()}] 🛡️ Arbiter title 필드 충돌 교정: "
                        f"official_novel_title='{_arb_official_novel_title}' vs official_title='{_arb_official_title}' "
                        f"→ official_title 우선 적용",
                        file=sys.stderr,
                    )
            except Exception:
                pass
        
        heretic_url = final_decision.get("heretic_url") or \
                        (vf_result.get("novel_identity") or {}).get("heretic_url") if not _title_deliberately_null else \
                        final_decision.get("heretic_url")
        confidence = final_decision.get("confidence", "None")
        
        # Final title correction from evidence pool
        if official_title:
            official_title = self._correct_title_final(official_title, ctx)
            if official_title and self._is_platform_branding_title(official_title):
                print(
                    f"[{_ts()}] 🚫 platform branding title 제거: '{official_title}'",
                    file=sys.stderr,
                )
                official_title = None
        
        # Discussion type normalization
        discussion_type = final_decision.get("discussion_type") or \
                         final_decision.get("post_type")  # fallback alias
        # Validate discussion type
        valid_types = {"review", "spoiler", "anticipation", "meme", "author_talk", 
                      "character_talk", "general", "meta", "recommendation", "trope_discussion",
                      "community_banter", "genre_opinion", "image_post", "off_topic", "noise",
                      "undecodable_reference"}
        if discussion_type not in valid_types:
            # Legacy type mapping
            type_mapping = {
                "work_discussion": "review",
                "author_criticism": "author_talk",
                "genre_discussion": "trope_discussion",
            }
            discussion_type = type_mapping.get(discussion_type, "general" if is_relevant else "noise")

        # ── 가드 J0.5: Arbiter 드리프트 복구 (Verifier 강증거 우선) ──
        # 조건:
        # - Arbiter 최종 비관련
        # - Verifier는 관련 + high 계열
        # - 제목 약칭이 포스트 제목에 실제 존재
        # - 공식 플랫폼 URL/증거가 존재
        # - Decoder 런타임 불안정(NoneType 등) 또는 Synthesizer가 플랫폼약어 드리프트를 주장
        if not is_relevant:
            _vf_novel = vf_result.get("novel_identity") or {}
            _vf_title = (
                _vf_novel.get("official_novel_title")
                or _vf_novel.get("official_title")
                or ""
            )
            _vf_url = _vf_novel.get("heretic_url") or ""
            _vf_conf = str(
                vf_result.get("final_confidence")
                or _vf_novel.get("confidence")
                or ""
            ).strip().lower()
            _vf_ev_type = str(_vf_novel.get("evidence_type") or "").strip().lower()
            _vf_grounding_j05 = vf_result.get("grounding_check") or {}
            _vf_anchor_j05 = str(_vf_grounding_j05.get("anchor_found") or "").lower()
            _vf_anchor_strong_for_genre_j05 = _vf_anchor_j05 in {
                "character_mention",
                "character_title_link",
                "plot_mention",
                "author_mention",
            }
            _discourse_warn_j05 = str(getattr(ctx, "discourse_warning", "") or "").lower()
            _has_genre_warning_j05 = "genre_discussion" in _discourse_warn_j05

            _post_data_j05 = getattr(ctx, "post_data", None) or {}
            _post_title_j05 = str(_post_data_j05.get("title") or "")
            _vf_title_literal_in_post_j05 = bool(
                _vf_title and self._text_matches_title_strict(_post_title_j05, _vf_title)
            )
            _vf_abbrev_stable_j05 = bool(
                _vf_title and self._has_title_abbrev_stability_signal(ctx, _vf_title)
            )
            _vf_title_in_post = _vf_title_literal_in_post_j05 or _vf_abbrev_stable_j05
            _vf_has_official_ev = bool(
                (_vf_title and self._has_official_title_evidence(ctx, _vf_title))
                or (_vf_url and self._is_novel_platform_url(_vf_url))
            )

            _dec_out_j05 = ctx.get_expert_output(ExpertType.DECODER) or {}
            _dec_notes_j05 = str(_dec_out_j05.get("notes") or "").lower()
            _dec_conf_j05 = str(_dec_out_j05.get("overall_confidence") or "").strip().lower()
            _decoder_unstable_j05 = (
                ("nonetype" in _dec_notes_j05 and "iterable" in _dec_notes_j05)
                or _dec_conf_j05 in {"none", ""}
            )

            _syn_out_j05 = ctx.get_expert_output(ExpertType.SYNTHESIZER) or {}
            _syn_hidden_j05 = _syn_out_j05.get("hidden_references") or []
            _syn_platform_claim_j05 = any(
                isinstance(_hr, dict)
                and str(_hr.get("reference_type") or "").lower() in {
                    "platform_abbreviation",
                    "platform_site",
                    "platform",
                }
                for _hr in _syn_hidden_j05
            )
            _syn_ca_j05 = _syn_out_j05.get("confidence_assessment") or {}
            _syn_is_work_j05 = bool(_syn_ca_j05.get("is_about_identified_work"))

            _vf_strong_positive_j05 = (
                bool(vf_result.get("is_relevant"))
                and bool(_vf_title)
                and _vf_conf in {"high", "max"}
                and _vf_title_in_post
                and _vf_has_official_ev
                and (
                    _vf_ev_type in {"search_platform_url", "platform_url", "official_platform_url", "official_source"}
                    or _vf_has_official_ev
                )
            )
            if (
                _vf_strong_positive_j05
                and _has_genre_warning_j05
                and not _vf_anchor_strong_for_genre_j05
            ):
                _vf_strong_positive_j05 = False
                print(
                    f"[{_ts()}] 🛑 J0.5 승격 차단: genre_discussion 경고 + 약한 앵커 "
                    f"(anchor='{_vf_anchor_j05}', title_literal={_vf_title_literal_in_post_j05}, "
                    f"abbrev_stable={_vf_abbrev_stable_j05})",
                    file=sys.stderr,
                )
            _arbiter_drift_like_j05 = _decoder_unstable_j05 or (
                _syn_platform_claim_j05 and not _syn_is_work_j05
            )

            if _vf_strong_positive_j05 and _arbiter_drift_like_j05:
                _old_dt_j05 = discussion_type
                is_relevant = True
                _title_deliberately_null = False
                if not official_title:
                    official_title = str(_vf_title).strip() or None
                if not heretic_url and _vf_url:
                    heretic_url = _vf_url
                if discussion_type in {
                    "noise",
                    "community_banter",
                    "off_topic",
                    "meta",
                    "trope_discussion",
                    "genre_opinion",
                    "recommendation",
                    "image_post",
                    "undecodable_reference",
                }:
                    discussion_type = "general"
                if str(confidence).strip().lower() in {"none", "low", ""}:
                    confidence = "High"
                print(
                    f"[{_ts()}] 🔄 Arbiter drift 복구(J0.5): "
                    f"arbiter is_relevant=false -> verifier strong evidence 채택 "
                    f"(title='{official_title}', dt='{_old_dt_j05}'→'{discussion_type}', "
                    f"decoder_unstable={_decoder_unstable_j05}, synth_platform_claim={_syn_platform_claim_j05})",
                    file=sys.stderr,
                )
        
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
        
        # ━━ 🆕 Phase 11j: Post-Arbiter 가드 — 장르토론/추천요청 오탐 방지 ━━
        gk_context_clues_j = gatekeeper_out.get("context_clues") or {}

        # ── 가드 J1: Verifier 거부권 코드 레벨 시행 ──
        # Verifier가 is_relevant=False인데 Arbiter가 is_relevant=True로 뒤집은 경우,
        # 본문에 강한 작품 앵커가 없으면 Verifier 판정을 존중
        _vf_is_relevant = vf_result.get("is_relevant", True)
        _arb_veto_exempt_j = bool(final_decision.get("_verifier_veto_exempt"))
        if is_relevant and not _vf_is_relevant and official_title and not _arb_veto_exempt_j:
            # Verifier 거부를 뒤집으려면, "검색 힌트"만이 아닌 본문-증거 결속이 있어야 한다.
            _vf_grounding_j = vf_result.get("grounding_check") or {}
            _vf_anchor_j = str(_vf_grounding_j.get("anchor_found") or "").lower()
            _has_strong_anchor_j = _vf_anchor_j in {
                "title_mention", "author_mention", "character_title_link",
            }

            # 본문/제목/댓글에 최종 제목이 실제 등장하는지 확인
            _post_data_j = getattr(ctx, "post_data", None) or {}
            _chunks_j = [str(_post_data_j.get("title") or "")]
            _body_chunks_j = []
            for _blk_j in (_post_data_j.get("content_blocks") or []):
                if isinstance(_blk_j, dict):
                    _txt_j = str(_blk_j.get("text") or "")
                    _chunks_j.append(_txt_j)
                    if _txt_j.strip():
                        _body_chunks_j.append(_txt_j)
                elif isinstance(_blk_j, str):
                    _chunks_j.append(_blk_j)
                    if _blk_j.strip():
                        _body_chunks_j.append(_blk_j)
            _chunks_j.extend([c for c in (getattr(ctx, "comments", None) or []) if isinstance(c, str)])
            _full_text_norm_j = self._normalize_match_text(" ".join(_chunks_j))
            _body_text_raw_j = " ".join(_body_chunks_j).strip()
            _actual_body_chars_j = len(_body_text_raw_j)
            _title_norm_j = self._normalize_match_text(official_title)
            _title_in_context_j = bool(_title_norm_j and _title_norm_j in _full_text_norm_j)
            _official_evidence_j = self._has_official_title_evidence(ctx, official_title)

            # Decoder에서 고신뢰+강한 앵커가 있는 경우만 예외적으로 허용
            _dec_strong_j = False
            _dec_out_j = ctx.get_expert_output(ExpertType.DECODER) or {}
            for _dt_j in _dec_out_j.get("decoded_terms", []):
                _bm_j = _dt_j.get("best_match") or {}
                _gr_j = _dt_j.get("grounding") or {}
                _a_j = str(_gr_j.get("anchor_type") or "").lower()
                _c_j = str(_bm_j.get("confidence") or "").lower()
                if _a_j in ("title_mention", "character_title_link") and _c_j in ("high", "max"):
                    _dec_strong_j = True
                    break

            # snippet 약칭은 full-title 매핑 + 공식 근거가 있을 때만 인정
            _snippet_abbrev_match_j = False
            _sh_j = getattr(ctx, "snippet_hints", None) or {}
            _abbrev_hints_j = _sh_j.get("abbreviation_hints", []) or []
            _post_title_j = str((_post_data_j or {}).get("title") or "").replace(" ", "").lower()
            for _abh_j in _abbrev_hints_j:
                if not isinstance(_abh_j, dict):
                    continue
                _abbrev_raw_j = str(_abh_j.get("abbrev") or "")
                _full_raw_j = str(_abh_j.get("full") or "")
                _abbrev_j = _abbrev_raw_j.replace(" ", "").lower()
                if not _abbrev_j or _abbrev_j not in _post_title_j:
                    continue
                if _full_raw_j and self._normalize_match_text(_full_raw_j) == _title_norm_j:
                    _snippet_abbrev_match_j = True
                    break

            # Verifier가 "본문 미언급/고유정보 없음"을 주장하지만,
            # 실제 본문에 Gatekeeper 캐릭터명이 2개 이상 명시된 경우는 모순 신호로 본다.
            _vf_reason_blob_j = " | ".join(
                [
                    str(vf_result.get("reason") or ""),
                    str(vf_result.get("rejection_reason") or ""),
                    str(_vf_grounding_j.get("grounding_issue") or ""),
                ]
            ).lower()
            _vf_claims_no_anchor_j = any(
                _k in _vf_reason_blob_j
                for _k in (
                    "본문 미언급",
                    "작품 고유 정보",
                    "고유 정보",
                    "전혀 없음",
                    "키워드 우연",
                    "anchor_found\":\"none",
                )
            )
            _vf_claims_body_empty_j = any(
                _k in _vf_reason_blob_j
                for _k in (
                    "본문 비어",
                    "본문이 비어",
                    "본문 비었",
                    "본문 없음",
                    "본문없",
                    "body empty",
                    "empty body",
                )
            )
            _generic_char_terms_j = {
                "작가", "작품", "제목", "본문", "캐릭터", "주인공", "히로인",
                "전개", "결말", "신작", "소설", "웹소설", "만화",
            }
            _gk_chars_j = []
            for _ch_j in (gk_entities.get("possible_characters") or []):
                if not isinstance(_ch_j, str):
                    continue
                _ch_clean_j = _ch_j.strip()
                if len(_ch_clean_j) < 2 or _ch_clean_j in _generic_char_terms_j:
                    continue
                _gk_chars_j.append(_ch_clean_j)
            _char_hits_j = []
            for _ch_j in _gk_chars_j:
                _ch_norm_j = self._normalize_match_text(_ch_j)
                if _ch_norm_j and _ch_norm_j in _full_text_norm_j:
                    _char_hits_j.append(_ch_norm_j)
            _has_multi_char_anchor_j = len(set(_char_hits_j)) >= 2
            _discourse_intent_j = str(getattr(ctx, "discourse_intent", "") or "").lower()
            _is_work_intent_j = _discourse_intent_j in {"discuss_work", "review", "spoiler"}
            _verifier_no_anchor_contradiction_j = (
                _vf_claims_no_anchor_j
                and _has_multi_char_anchor_j
                and (_is_work_intent_j or gk_post_type == "work_discussion")
            )
            _verifier_body_empty_contradiction_j = (
                _vf_claims_body_empty_j
                and _actual_body_chars_j >= 5
                and (
                    _is_work_intent_j
                    or gk_post_type in {"work_discussion", "short_reaction"}
                    or _dec_strong_j
                    or _official_evidence_j
                )
            )
            _verifier_contradiction_j = (
                _verifier_no_anchor_contradiction_j
                or _verifier_body_empty_contradiction_j
            )

            _vf_counter_args_j = vf_result.get("counter_arguments") or []
            _vf_has_critical_reject_j = any(
                isinstance(_ca, dict)
                and str(_ca.get("severity") or "").lower() == "critical"
                and str(_ca.get("action") or "").lower() == "reject"
                for _ca in _vf_counter_args_j
            )

            _has_strong_override_j = (
                _has_strong_anchor_j
                or _dec_strong_j
                or (_official_evidence_j and (_title_in_context_j or _snippet_abbrev_match_j))
            )

            # critical reject인 경우엔 더 엄격: 공식근거 + 본문결속 + 강한앵커가 없으면 뒤집지 않는다.
            if _vf_has_critical_reject_j and not (
                _official_evidence_j and (_title_in_context_j or _snippet_abbrev_match_j) and _has_strong_anchor_j
            ):
                if _verifier_contradiction_j and (_dec_strong_j or _official_evidence_j):
                    print(
                        f"[{_ts()}] ⚖️ Verifier 거부권 예외(J1): "
                        f"본문 캐릭터 앵커 {len(set(_char_hits_j))}개 / 본문길이 {_actual_body_chars_j}자 "
                        f"+ 거부 사유 모순 감지 "
                        f"→ Arbiter 판정 유지 후보",
                        file=sys.stderr,
                    )
                    _has_strong_override_j = True
                else:
                    _has_strong_override_j = False

            if not _has_strong_override_j:
                # Verifier 거부 사유 추출
                _vf_reason = str(vf_result.get("reason") or vf_result.get("assessment") or "")[:100]
                print(
                    f"[{_ts()}] 🛡️ Verifier 거부권 시행: "
                    f"Verifier=False + 강한 앵커 없음 → Arbiter 판정('{official_title}') 기각. "
                    f"Verifier 사유: {_vf_reason}",
                    file=sys.stderr,
                )
                is_relevant = False
                official_title = None
                confidence = "None"
                discussion_type = "noise"
        
        # ── 가드 J2: DiscourseAnalyzer 장르토론 강제 시행 ──
        # Discourse가 discuss_genre intent로 판정했는데 Arbiter가 무시한 경우
        _discourse_warn_j = getattr(ctx, "discourse_warning", "") or ""
        _discourse_intent_j = getattr(ctx, "discourse_intent", "") or ""
        if (is_relevant and official_title
                and "discuss_genre" in _discourse_warn_j
                and _discourse_intent_j == "discuss_genre"):
            # 장르 토론 경고가 있으면, 본문에 매우 강한 증거가 없는 한 거부
            _vf_grounding_j2 = vf_result.get("grounding_check") or {}
            _vf_anchor_j2 = str(_vf_grounding_j2.get("anchor_found") or "").lower()
            _has_title_or_char = _vf_anchor_j2 in ("title_mention", "character_title_link")
            
            if not _has_title_or_char:
                _d_conf_j = str(getattr(ctx, "discourse_confidence", "medium")).lower()
                print(
                    f"[{_ts()}] 🛡️ Discourse 장르토론 시행: "
                    f"discuss_genre({_d_conf_j}) + 강한 앵커 없음 → "
                    f"'{official_title}' 기각",
                    file=sys.stderr,
                )
                is_relevant = False
                official_title = None
                confidence = "None"
                discussion_type = "trope_discussion"
        
        # ── 가드 J3: DC 의견 접두사 오탐 방지 ──
        # Gatekeeper가 "소신발언))" 등 DC 의견 접두사를 감지한 경우,
        # official_title이 해당 접두사 키워드와 동일/유사하면 기각
        _dc_opinion_kw = gk_context_clues_j.get("dc_opinion_prefix", "")
        if _dc_opinion_kw and is_relevant and official_title:
            _norm_opinion = _dc_opinion_kw.lower().replace(" ", "")
            _norm_title = official_title.lower().replace(" ", "")
            # "소신발언" → "소신발언2025" 같은 유사 매칭도 차단
            if _norm_title.startswith(_norm_opinion) or _norm_opinion in _norm_title:
                print(
                    f"[{_ts()}] 🛡️ DC 의견 접두사 가드: "
                    f"'{_dc_opinion_kw}' == '{official_title}'의 기반 → "
                    f"의견 태그를 작품명으로 오인 차단",
                    file=sys.stderr,
                )
                is_relevant = False
                official_title = None
                confidence = "None"
                discussion_type = "community_banter"
        
        # ── 가드 J4: 추천 요청 게시글 오탐 방지 ──
        # "X를 보고싶구나" 패턴 + 본문에 특정 작품 고유정보 없음 → 추천 게시글
        _is_recommendation_j = gk_context_clues_j.get("is_recommendation_request", False)
        if _is_recommendation_j and is_relevant and official_title:
            # 추천 요청인데 본문이 비어있거나 매우 짧으면 → 댓글 URL에서 매칭된 것
            content_blocks_j = []
            _post_j = ctx.post if hasattr(ctx, 'post') else {}
            for _block_j in (_post_j.get("content_blocks") or []):
                if isinstance(_block_j, dict) and _block_j.get("text"):
                    content_blocks_j.append(_block_j["text"])
                elif isinstance(_block_j, str):
                    content_blocks_j.append(_block_j)
            _body_len_j = sum(len(t.strip()) for t in content_blocks_j)
            
            # 본문 20자 미만이고 강한 앵커가 없으면 추천 요청으로 간주
            _vf_grounding_j4 = vf_result.get("grounding_check") or {}
            _vf_anchor_j4 = str(_vf_grounding_j4.get("anchor_found") or "").lower()
            _has_plot_mention = _vf_anchor_j4 in ("title_mention", "plot_mention", "character_title_link")
            
            if _body_len_j < 20 and not _has_plot_mention:
                print(
                    f"[{_ts()}] 🛡️ 추천 요청 가드: "
                    f"추천 요청 패턴 + 본문 {_body_len_j}자 + 앵커 없음 → "
                    f"'{official_title}' 기각 (댓글 추천을 주제로 오인 차단)",
                    file=sys.stderr,
                )
                is_relevant = False
                official_title = None
                confidence = "None"
                discussion_type = "recommendation"
        
        # ── 가드 J5: 비교 패턴 게시글 보정 ──
        # "X 신작봤는데 Y 하위호환" → 주제는 신작, Y는 비교 대상일 뿐
        _is_comparison_j = gk_context_clues_j.get("is_comparison_post", False)
        if _is_comparison_j and is_relevant and official_title:
            # confidence를 Low로 하향 (완전 차단은 아님, 부분 정당성 있을 수 있으므로)
            if confidence in ("High", "Max"):
                print(
                    f"[{_ts()}] ⚖️ 비교 패턴 보정: "
                    f"'{official_title}' confidence {confidence}→Low "
                    f"(비교 대상이 주제가 아닐 수 있음)",
                    file=sys.stderr,
                )
                confidence = "Low"
        
        # ── 가드 J6: 플랫폼 기능 가드 (Decoder 판정 존중) ──
        # Decoder가 "플랫폼 약칭 + 기능 용어(콘/뱃지/이모티콘)" 조합을 감지해
        # title=null로 처리했는데, Verifier/Arbiter가 다시 뒤집은 경우 기각.
        # 예: "노피아 가운데에서 빔 나오는 콘이 있는거보소" → 노벨피아 구독콘 이야기
        if is_relevant and official_title:
            _dec_out_j6 = ctx.get_expert_output(ExpertType.DECODER) or {}
            _dec_notes_j6 = str(_dec_out_j6.get("notes") or "")
            if "플랫폼 기능 가드" in _dec_notes_j6:
                # Decoder가 플랫폼 기능 가드를 발동했으면 Verifier/Arbiter 오버라이드 차단
                # 단, 본문에 캐릭터 고유명/줄거리 언급 같은 매우 강한 앵커가 있으면 예외
                _vf_grounding_j6 = vf_result.get("grounding_check") or {}
                _vf_anchor_j6 = str(_vf_grounding_j6.get("anchor_found") or "").lower()
                _has_character_or_plot = _vf_anchor_j6 in (
                    "character_mention", "plot_mention", "character_title_link",
                )
                if not _has_character_or_plot:
                    print(
                        f"[{_ts()}] 🛡️ 플랫폼 기능 가드(J6): "
                        f"Decoder가 플랫폼 기능 글로 판정 → Arbiter의 '{official_title}' 기각. "
                        f"(플랫폼 구독콘/뱃지/이모티콘 등에 대한 글)",
                        file=sys.stderr,
                    )
                    is_relevant = False
                    official_title = None
                    confidence = "None"
                    discussion_type = "meta"
        
        # ── 가드 J7: "신작" 패턴 가드 — 제목 추측 방지 + reason 동기화 ──
        # "[작가명] 신작 ..." 게시글에서 정확한 작품명을 알 수 없는 경우,
        # Arbiter/Synthesizer가 검색 결과에서 억지로 매칭한 제목을 걸러낸다.
        # 이 경우 is_relevant=True는 유지하되 official_title=null로 설정.
        _post_data_j7 = ctx.post_data or {}
        _post_title_j7_raw = str(_post_data_j7.get("title", "") or "")
        _post_title_j7 = _post_title_j7_raw.replace(" ", "")
        _shinwork_kws = ["신작", "최신작", "새작품", "이번작", "차기작", "신간"]
        _has_shinwork_in_title = any(kw in _post_title_j7 for kw in _shinwork_kws)
        
        if _has_shinwork_in_title and is_relevant and official_title:
            # 작가가 식별됐는지 확인
            _j7_author = ""
            _md_author_j7 = metadata.get("detected_author", "")
            if _md_author_j7:
                _j7_author = _md_author_j7
            if not _j7_author:
                _dec_out_j7 = ctx.get_expert_output(ExpertType.DECODER) or {}
                for _dt_j7 in _dec_out_j7.get("decoded_terms", []):
                    if _dt_j7.get("is_author_name"):
                        _ai_j7 = (_dt_j7.get("author_info") or {}).get("name", "")
                        if _ai_j7:
                            _j7_author = _ai_j7
                            break
            if not _j7_author:
                # 제목 선두의 "[작가명] 신작" 패턴에서 작가명 추정
                import re as _re_j7
                _m_j7 = _re_j7.match(r"^\s*([가-힣A-Za-z0-9]{2,12})\s*신작", _post_title_j7_raw)
                if _m_j7:
                    _j7_author = _m_j7.group(1).strip()
            
            if _j7_author:
                # 매칭된 제목이 본문에 실제로 등장하는지 확인
                _content_text_j7 = ""
                _content_blocks_j7 = _post_data_j7.get("content_blocks") or _post_data_j7.get("content") or []
                if isinstance(_content_blocks_j7, list):
                    for _blk_j7 in _content_blocks_j7:
                        if isinstance(_blk_j7, dict):
                            _content_text_j7 += _blk_j7.get("text", "")
                        elif isinstance(_blk_j7, str):
                            _content_text_j7 += _blk_j7
                _content_text_j7 = _content_text_j7.replace(" ", "")
                _title_norm_j7 = official_title.replace(" ", "")
                
                _title_in_body_j7 = _title_norm_j7 in _content_text_j7
                # 제목 앞 2글자 이상이 본문에 있는지도 체크 (약칭)
                _abbrev_in_body_j7 = False
                if len(_title_norm_j7) >= 4:
                    _abbrev_j7 = _title_norm_j7[:max(2, len(_title_norm_j7) // 2)]
                    _abbrev_in_body_j7 = _abbrev_j7 in _content_text_j7
                
                # 본문 직접 언급이 약해도,
                # 1) 게시글 제목에서의 토큰 겹침
                # 2) 공식 플랫폼 증거
                # 3) candidate evidence bucket
                # 중 하나가 충분하면 "신작 가드"로 즉시 null 처리하지 않는다.
                _title_overlap_in_post_j7 = self._text_matches_phrase(_post_title_j7_raw, official_title)
                _official_title_evidence_j7 = self._has_official_title_evidence(ctx, official_title)
                _bucket_j7 = self._get_candidate_evidence_bucket(ctx, official_title)
                _bucket_score_j7 = self._score_candidate_evidence_bucket(_bucket_j7)

                if (
                    not _title_in_body_j7
                    and not _abbrev_in_body_j7
                    and not _title_overlap_in_post_j7
                    and (not _official_title_evidence_j7)
                    and _bucket_score_j7 < 3
                ):
                    _old_title_j7 = official_title
                    print(
                        f"[{_ts()}] 🛡️ 신작 패턴 가드(J7): "
                        f"제목에 '신작' + 작가 '{_j7_author}' 식별 + "
                        f"매칭 제목 '{_old_title_j7}'가 본문에 미등장 → "
                        f"제목 불확정. 신작은 정확한 제목을 알 수 없으므로 title=null.",
                        file=sys.stderr,
                    )
                    official_title = None
                    confidence = "Low"
                    _title_deliberately_null = True
                    # reason에 잘못된 제목이 남아있으면 교정 마킹
                    ctx._j7_shinwork_reason_fix = {
                        "old_title": _old_title_j7,
                        "author": _j7_author,
                    }

        # ── 가드 J9: "신작" + 비공식 근거 제목 매칭 차단 ──
        # 작가 신작 글에서 본문 묘사어를 작품명으로 오매칭하는 케이스를 막는다.
        if _has_shinwork_in_title and is_relevant and official_title:
            _title_norm_j9 = official_title.replace(" ", "")
            _title_in_post_title_j9 = _title_norm_j9 in _post_title_j7
            _official_title_evidence_j9 = self._has_official_title_evidence(ctx, official_title)
            _title_overlap_j9 = self._text_matches_phrase(_post_title_j7_raw, official_title)
            _bucket_j9 = self._get_candidate_evidence_bucket(ctx, official_title)
            _bucket_score_j9 = self._score_candidate_evidence_bucket(_bucket_j9)
            if (
                (not _title_in_post_title_j9)
                and (not _title_overlap_j9)
                and (not _official_title_evidence_j9)
                and _bucket_score_j9 < 3
            ):
                print(
                    f"[{_ts()}] 🛡️ 신작-비공식 근거 차단(J9): "
                    f"title='{official_title}' is not in post title and no official platform evidence",
                    file=sys.stderr,
                )
                official_title = None
                confidence = "Low"
                discussion_type = "author_talk"
        
        # ── 가드 J8.5: 다작/순서질문은 단일 작품명 고정 금지 ──
        # 예: "유진성 글 다 본사람" + "광마회귀 -> 시불꽃 -> 칼취밤 ..."
        if is_relevant and official_title:
            _multi_ctx = self._detect_multi_work_order_context(ctx, vf_result)
            if _multi_ctx.get("is_multi_work_order") and int(_multi_ctx.get("decoded_title_count", 0)) >= 2:
                _old_title_j85 = official_title
                official_title = None
                heretic_url = None
                if confidence in ("High", "Max"):
                    confidence = "Medium"
                elif confidence in ("None", "", None):
                    confidence = "Low"
                discussion_type = "general"
                print(
                    f"[{_ts()}] 🧭 다작/순서질문 가드(J8.5): "
                    f"single-title '{_old_title_j85}' 강제 고정 해제 "
                    f"(decoded_titles={_multi_ctx.get('decoded_title_count')}, "
                    f"order_kw={_multi_ctx.get('has_order_keyword')}, arrow={_multi_ctx.get('has_arrow_chain')})",
                    file=sys.stderr,
                )

        # Gatekeeper community_banter / image_post propagation guards.

        # ── 가드 J8: 작가 비교/품평 게시글 오매칭 방지 ──
        # Decoder가 2명 이상의 작가를 식별했을 때, 특정 작품에 매칭되면 FP 가능성 높음
        # 예: "목마는 그냥 현판이나 써야댐" + "개돌도 후반 말아먹긴했지만" → 작가 비교
        #     매칭된 제목 "상태창이 사라졌다"는 개돌청년 작가의 대표작이지 이 글의 주제가 아님
        if is_relevant and official_title:
            _dec_out_j8 = ctx.get_expert_output(ExpertType.DECODER) or {}
            _decoded_terms_j8 = _dec_out_j8.get("decoded_terms", [])
            
            # 1) 명시적 is_author_name=true 카운트
            _explicit_authors_j8 = set()
            for _dt_j8 in _decoded_terms_j8:
                if _dt_j8.get("is_author_name"):
                    _orig_j8 = (_dt_j8.get("original") or "").strip()
                    if _orig_j8:
                        _explicit_authors_j8.add(_orig_j8)
            
            # 2) interpretations에 author_name이 있는 term 카운트
            _interp_authors_j8 = set()
            for _dt_j8 in _decoded_terms_j8:
                _orig_j8 = (_dt_j8.get("original") or "").strip()
                if not _orig_j8:
                    continue
                _interps_j8 = _dt_j8.get("interpretations", [])
                _has_author_j8 = any(
                    isinstance(i, dict) 
                    and i.get("type") == "author_name"
                    and i.get("context_fit") in ("high", "medium")
                    for i in _interps_j8
                )
                if _has_author_j8:
                    _interp_authors_j8.add(_orig_j8)
            
            # 3) snippet_analyzer의 relevant_authors도 참고
            _lsa_j8 = getattr(ctx, 'llm_snippet_analysis', None) or {}
            _snippet_authors_j8 = set()
            for _sa in (_lsa_j8.get("relevant_authors") or []):
                if isinstance(_sa, str) and len(_sa) >= 2:
                    _snippet_authors_j8.add(_sa)
            
            _all_authors_j8 = _explicit_authors_j8 | _interp_authors_j8
            # snippet_analyzer authors 중 decoded_terms에 겹치는 것도 카운트
            for _sa_j8 in _snippet_authors_j8:
                _sa_norm_j8 = _sa_j8.replace(" ", "").lower()
                for _dt_j8 in _decoded_terms_j8:
                    _orig_norm_j8 = (_dt_j8.get("original") or "").replace(" ", "").lower()
                    if _orig_norm_j8 and (
                        _sa_norm_j8.startswith(_orig_norm_j8)
                        or _orig_norm_j8 in _sa_norm_j8
                    ):
                        _all_authors_j8.add(_dt_j8.get("original", ""))
            
            if len(_all_authors_j8) >= 2:
                # 2명 이상의 작가가 감지됨 → 작가 비교/품평 가능성
                # 매칭된 제목이 앵커가 약한 경우에만 차단
                _vf_grounding_j8 = vf_result.get("grounding_check") or {}
                _vf_anchor_j8 = str(_vf_grounding_j8.get("anchor_found") or "").lower()
                _has_title_anchor_j8 = _vf_anchor_j8 in (
                    "title_mention", "character_title_link",
                )
                
                # Decoder에도 강한 title_mention이 있는지 확인
                _dec_has_title_mention_j8 = False
                for _dt_j8 in _decoded_terms_j8:
                    if _dt_j8.get("is_author_name"):
                        continue
                    _gr_j8 = _dt_j8.get("grounding") or {}
                    _a_j8 = str(_gr_j8.get("anchor_type") or "").lower()
                    _bm_j8 = _dt_j8.get("best_match") or {}
                    _c_j8 = str(_bm_j8.get("confidence") or "").lower()
                    if _a_j8 == "title_mention" and _c_j8 in ("high", "max"):
                        _dec_has_title_mention_j8 = True
                        break
                
                if not _has_title_anchor_j8 and not _dec_has_title_mention_j8:
                    print(
                        f"[{_ts()}] 🛡️ 작가비교 가드(J8): "
                        f"2+명 작가 감지 ({_all_authors_j8}) + "
                        f"앵커 약함(anchor={_vf_anchor_j8}) → "
                        f"'{official_title}' 매칭 기각 (작가 품평 글)",
                        file=sys.stderr,
                    )
                    is_relevant = False
                    official_title = None
                    confidence = "None"
                    discussion_type = "author_talk"
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
            "undecodable_reference",
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
            _official_evidence_rescue = self._has_official_title_evidence(ctx, official_title) if official_title else False
            _bucket_rescue = self._get_candidate_evidence_bucket(ctx, official_title) if official_title else {}
            _bucket_score_rescue = self._score_candidate_evidence_bucket(_bucket_rescue) if official_title else 0
            _arb_veto_exempt = bool(final_decision.get("_verifier_veto_exempt"))
            _rescue_irrelevant_with_evidence = (
                is_relevant
                and bool(official_title)
                and discussion_type in always_irrelevant_types
                and (_official_evidence_rescue or (has_work_anchor and _bucket_score_rescue > 0))
                and (_vf_is_relevant or _arb_veto_exempt)
            )
            
            # 🆕 author_talk + is_author_criticism + 다중 작품 예시 → rescue 차단
            # 작가 품평/비교 글에서 여러 작품을 예시로 꺼낸 경우,
            # 특정 단일 작품에 매칭하면 FP 발생
            if _rescue_irrelevant_with_evidence and discussion_type == "author_talk":
                _vf_is_author_criticism = False
                _vf_check = verifier_out.get("verification_result", {}) if verifier_out else {}
                _vf_author_info = _vf_check.get("author_info") or {}
                if isinstance(_vf_author_info, dict):
                    _vf_is_author_criticism = bool(_vf_author_info.get("is_author_criticism"))
                
                # Decoder가 2개 이상 고유 작품을 식별했는지 확인
                _decoder_titles = set()
                _dec_check = ctx.get_expert_output(ExpertType.DECODER) or {} if ctx else {}
                for _dt_at in _dec_check.get("decoded_terms", []):
                    _bm_at = _dt_at.get("best_match") or {}
                    _t_at = _bm_at.get("title")
                    if _t_at and str(_bm_at.get("confidence", "")).lower() not in ("none",):
                        _decoder_titles.add(_t_at)
                
                if _vf_is_author_criticism and len(_decoder_titles) >= 2:
                    _rescue_irrelevant_with_evidence = False
                    print(
                        f"[{_ts()}] 🛡️ author_talk rescue 차단: "
                        f"is_author_criticism=True + 다중 작품({len(_decoder_titles)}건) "
                        f"→ 작가 품평 글에서 예시 작품 매칭 방지",
                        file=sys.stderr,
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
                _gk_cc_force = (gatekeeper_out.get("context_clues") or {})
                _cc_masked_force = bool(_gk_cc_force.get("has_title_masking", False))
                _cc_short_fast_force = bool(_gk_cc_force.get("short_post_fast_path", False))
                _fallback_force = "undecodable_reference" if (_cc_masked_force or _cc_short_fast_force) else "noise"
                print(
                    f"[{_ts()}] force non-relevant for non-work type: "
                    f"is_relevant=false + discussion_type='{discussion_type}' -> '{_fallback_force}'"
                    + (" (마스킹/short-post)" if (_cc_masked_force or _cc_short_fast_force) else ""),
                    file=sys.stderr,
                )
                is_relevant = False
                discussion_type = _fallback_force
                official_title = None
        elif is_relevant and discussion_type == "noise":
            discussion_type = "general"
        elif is_relevant and discussion_type == "undecodable_reference":
            # undecodable인데 relevant=true면 모순 → general로 승격
            discussion_type = "general"
        elif (not is_relevant) and discussion_type in work_relevant_types:
            # 마스킹 여부에 따라 noise vs undecodable_reference 분리
            _gk_cc = (gatekeeper_out.get("context_clues") or {})
            _cc_masked = _gk_cc.get("has_title_masking", False)
            _cc_short_fast = _gk_cc.get("short_post_fast_path", False)
            _fallback = "undecodable_reference" if (_cc_masked or _cc_short_fast) else "noise"
            print(
                f"[{_ts()}] consistency correction: is_relevant=false + "
                f"discussion_type='{discussion_type}' -> '{_fallback}'"
                + (" (마스킹/short-post)" if (_cc_masked or _cc_short_fast) else ""),
                file=sys.stderr,
            )
            discussion_type = _fallback
        
        # ━━ 🆕 Gatekeeper context_clues 기반 confidence calibration ━━
        # 마스킹/회차 감지 결과를 활용하여 Decoder 결과의 신뢰도를 보정
        gk_context_clues = gatekeeper_out.get("context_clues") or {}
        _has_title_masking = gk_context_clues.get("has_title_masking", False)
        _has_episode_ref = gk_context_clues.get("has_episode_reference", False)
        _short_post_fast = gk_context_clues.get("short_post_fast_path", False)
        
        if _has_title_masking and is_relevant and official_title:
            # 마스킹된 제목인데 작품을 특정했다면 → confidence 하향
            # (실제로 특정할 수 있는 정보가 충분하지 않을 가능성)
            if confidence in ("High", "Max") and not has_work_anchor:
                print(
                    f"[{_ts()}] 🔒 마스킹 calibration: title_masked=True, "
                    f"'{official_title}' confidence {confidence}→Medium "
                    f"(마스킹 제목에서 강한 앵커 없이 매칭됨)",
                    file=sys.stderr,
                )
                confidence = "Medium"
        
        if _has_title_masking and not is_relevant:
            # 마스킹된 제목 + irrelevant로 판정 → 해독불가 정당화
            # 제목이 숨겨져 있으므로 작품 특정 실패는 정상
            # discussion_type을 noise 대신 undecodable_reference로 分離
            if discussion_type == "noise":
                discussion_type = "undecodable_reference"
                print(
                    f"[{_ts()}] 🔒 마스킹→undecodable_reference: title_masked=True, "
                    f"작품 언급 있으나 마스킹으로 특정 불가 (noise에서 분리)",
                    file=sys.stderr,
                )
        
        if _has_episode_ref and not _has_title_masking:
            # 회차 참조 있음 + 마스킹 없음 → 작품 논의 가능성 매우 높음
            if is_relevant and confidence in ("Low", "None", "Medium"):
                ep_info = gk_context_clues.get("episode_info", {})
                ep_text = ep_info.get("matched_text", "")
                print(
                    f"[{_ts()}] 📺 회차 calibration: episode='{ep_text}', "
                    f"confidence {confidence}→Medium (연재 작품 앵커 부스트)",
                    file=sys.stderr,
                )
                if confidence in ("Low", "None"):
                    confidence = "Medium"

        # ── 가드 J10: 비소설 도메인 + 공식 근거 부재 시 오매칭 차단 ──
        # 예: "히토미"처럼 플랫폼/장르 용어를 특정 작품으로 오인하는 케이스.
        if is_relevant and official_title:
            _discourse_out_j10 = ctx.get_expert_output(ExpertType.DISCOURSE) or {}
            _da_j10 = _discourse_out_j10.get("discourse_analysis") or {}
            _primary_domain_j10 = str(_da_j10.get("primary_domain") or "").strip().lower()
            _non_novel_domains_j10 = {
                "manga_comics",
                "daily_life",
                "other",
                "community_banter",
            }
            _official_title_evidence_j10 = self._has_official_title_evidence(ctx, official_title)
            _anchor_weak_j10 = vf_anchor in {"none", "search_only", "", "title_mention"}
            if (
                _primary_domain_j10 in _non_novel_domains_j10
                and not _official_title_evidence_j10
                and _anchor_weak_j10
                and not _has_episode_ref
            ):
                print(
                    f"[{_ts()}] 🚫 비소설 도메인 오매칭 차단(J10): "
                    f"domain={_primary_domain_j10}, title='{official_title}', anchor='{vf_anchor}'",
                    file=sys.stderr,
                )
                is_relevant = False
                official_title = None
                confidence = "None"
                discussion_type = "noise"
        elif is_relevant and not _vf_is_relevant and official_title and _arb_veto_exempt_j:
            _commit_j10 = self._compute_title_commitment(ctx, official_title, vf_result)
            if self._is_title_commitment_strong(_commit_j10):
                print(
                    f"[{_ts()}] 🔒 Verifier 거부권 재적용 스킵: "
                    f"_verifier_veto_exempt=True + strong_commitment "
                    f"(title='{official_title}', score={_commit_j10.get('score')}, "
                    f"official={_commit_j10.get('official_evidence')}, "
                    f"title_in_post={_commit_j10.get('title_in_context')}, "
                    f"bucket={_commit_j10.get('bucket_score')})",
                    file=sys.stderr,
                )
            else:
                _old_title_j10 = official_title
                _fallback_type_j10 = "undecodable_reference" if _has_title_masking else "noise"
                is_relevant = False
                official_title = None
                heretic_url = None
                confidence = "None"
                discussion_type = _fallback_type_j10
                print(
                    f"[{_ts()}] 🚫 Verifier 거부권 재적용(J10.5): "
                    f"_verifier_veto_exempt=True지만 commitment 약함 "
                    f"(title='{_old_title_j10}', score={_commit_j10.get('score')}, "
                    f"official={_commit_j10.get('official_evidence')}, "
                    f"title_in_post={_commit_j10.get('title_in_context')}, "
                    f"bucket={_commit_j10.get('bucket_score')}) "
                    f"→ is_relevant=false, discussion_type='{discussion_type}'",
                    file=sys.stderr,
                )
        
        # ━━ 개선: relevant=true 코드 레벨 하드 게이트 ━━
        # 3단계 증거등급(강/중/약) 기반 판정 (수치 0~1 대신 이산값)
        from .rules import EVIDENCE_GRADE_MAP, EVIDENCE_GRADE_STRONG, EVIDENCE_GRADE_MEDIUM, EVIDENCE_GRADE_WEAK
        
        # 현재 앵커의 증거등급 산출
        _evidence_grade = EVIDENCE_GRADE_MAP.get(vf_anchor, EVIDENCE_GRADE_WEAK)
        # 회차 참조가 있으면 최소 medium 보장
        if _has_episode_ref and _evidence_grade == EVIDENCE_GRADE_WEAK:
            _evidence_grade = EVIDENCE_GRADE_MEDIUM
        
        # 조건: "고유 앵커 1개 이상 + 본문 근거 1개 이상"이 없으면 relevant=false 강제
        # 현재 anchor/body_evidence가 프롬프트 수준 지시에만 있었던 것을 코드 레벨로 승격
        if is_relevant and official_title:
            _anchor_types_strong = {
                "title_mention", "author_mention", "character_title_link",
                "character_mention", "plot_mention",
            }
            _has_strong_anchor = vf_anchor in _anchor_types_strong
            _vf_decoder_grounded = vf_grounding.get("decoder_grounded", True)
            _body_evidence = vf_grounding.get("body_evidence", "")
            
            # 본문 증거 없음: anchor가 search_only/none이고 decoder_grounded도 false
            _no_body_evidence = (
                not _has_strong_anchor
                and not _vf_decoder_grounded
                and _body_evidence in ("none", "", None)
            )
            
            # title_body_consistency 하드 블록 (기존 warning → 차단 승격)
            _is_association = getattr(ctx, "is_association_post", False)
            _discourse_warn = getattr(ctx, "discourse_warning", "") or ""
            _association_block = _is_association and "title_body_mismatch" in _discourse_warn
            
            if _no_body_evidence or _association_block:
                _block_reason = "본문 앵커 부재" if _no_body_evidence else "제목-본문 불일치(연상글)"
                # 강한 suspected_title이나 작가 증거가 있으면 예외
                _rescue = has_strong_suspected_title and has_work_anchor
                
                # 🆕 Decoder grounding 기반 추가 rescue:
                # Verifier가 anchor='none'이라 해도, Decoder가 title_mention 앵커를
                # 보고했고 high-confidence best_match가 있으면 rescue
                if not _rescue and has_strong_suspected_title:
                    _dec_out_hg = ctx.get_expert_output(ExpertType.DECODER) or {}
                    for _dt_hg in _dec_out_hg.get("decoded_terms", []):
                        _bm_hg = _dt_hg.get("best_match") or {}
                        _gr_hg = _dt_hg.get("grounding") or {}
                        _anchor_hg = str(_gr_hg.get("anchor_type") or "").lower()
                        _conf_hg = str(_bm_hg.get("confidence") or "").lower()
                        _anchor_conflict_hg = bool(_bm_hg.get("_title_anchor_conflict"))
                        _abbr_mismatch_hg = bool(_bm_hg.get("_abbr_mismatch_downgrade"))
                        if _anchor_hg in ("title_mention", "character_title_link") and _conf_hg in ("high", "max"):
                            if _anchor_conflict_hg or _abbr_mismatch_hg:
                                continue
                            _rescue = True
                            print(
                                f"[{_ts()}] 🔄 Decoder title_mention rescue: "
                                f"'{_dt_hg.get('original')}' → '{_bm_hg.get('title')}' "
                                f"(anchor={_anchor_hg}, conf={_conf_hg})",
                                file=sys.stderr,
                            )
                            break
                
                # 🆕 캐릭터-작품 검색 검증 완료 시 하드 게이트 rescue
                if not _rescue and getattr(ctx, 'verified_character_work_links', []):
                    _rescue = True
                    _vcwl_t = [v.get("title", "") for v in ctx.verified_character_work_links]
                    print(
                        f"[{_ts()}] 🔄 캐릭터-작품 검증 rescue: "
                        f"verified_character_work_links={_vcwl_t}",
                        file=sys.stderr,
                    )
                
                if not _rescue:
                    # 하드 게이트 발동 시, 마스킹 제목이면 noise가 아닌 undecodable_reference
                    _fallback_type = "undecodable_reference" if _has_title_masking else "noise"
                    print(
                        f"[{_ts()}] 🚫 하드 게이트 발동: is_relevant=true→false "
                        f"({_block_reason}, anchor='{vf_anchor}', "
                        f"grounded={_vf_decoder_grounded}, association={_is_association})"
                        f" → discussion_type='{_fallback_type}'"
                        f" [증거등급: {_evidence_grade}]",
                        file=sys.stderr,
                    )
                    is_relevant = False
                    confidence = "None"
                    discussion_type = _fallback_type
                else:
                    print(
                        f"[{_ts()}] ⚠️ 하드 게이트 면제: {_block_reason}이지만 "
                        f"suspected_title='{strong_suspected_title}' + work_anchor 존재",
                        file=sys.stderr,
                    )

        # ── 가드 J11: 제목 앵커 드리프트 차단 ──
        # 제목/약칭 앵커가 가리키는 핵심 도메인 키워드와 최종 제목이 충돌하면
        # (예: 즉사'무림' ↔ 즉사기 들고 '게임' 속으로) 오매칭 가능성이 높다.
        if is_relevant and official_title:
            _official_title_evidence_j11 = self._has_official_title_evidence(ctx, official_title)
            _drift = self._detect_title_anchor_drift(
                ctx,
                official_title=official_title,
                vf_anchor=vf_anchor,
            )
            if _drift.get("is_drift") and (not _official_title_evidence_j11):
                _replacement_title = _drift.get("replacement_title")
                _anchor_kw = _drift.get("anchor_keywords", [])
                _title_kw = _drift.get("title_keywords", [])
                if _replacement_title:
                    _old_title = official_title
                    official_title = _replacement_title
                    if confidence in ("High", "Max"):
                        confidence = "Medium"
                    print(
                        f"[{_ts()}] 🔄 제목 드리프트 교정(J11): '{_old_title}' → '{official_title}' "
                        f"(anchor_kw={_anchor_kw}, title_kw={_title_kw})",
                        file=sys.stderr,
                    )
                else:
                    _fallback_type = "undecodable_reference" if _has_title_masking else "noise"
                    print(
                        f"[{_ts()}] 🚫 제목 드리프트 차단(J11): title='{official_title}', "
                        f"anchor_kw={_anchor_kw}, title_kw={_title_kw} "
                        f"→ is_relevant=false, discussion_type='{_fallback_type}'",
                        file=sys.stderr,
                    )
                    is_relevant = False
                    official_title = None
                    confidence = "None"
                    discussion_type = _fallback_type

        # ── 가드 J12: candidate evidence bucket 빈약성 차단 ──
        # 후보 제목별 증거 버킷이 비어 있고(혹은 매우 약하고),
        # 공식 플랫폼 근거/강한 앵커도 없으면 최종 매칭을 차단한다.
        if is_relevant and official_title:
            _bucket = self._get_candidate_evidence_bucket(ctx, official_title)
            _bucket_score = self._score_candidate_evidence_bucket(_bucket)
            _has_bucket_store = bool(getattr(ctx, "candidate_evidence", None))
            _official_title_evidence_j12 = self._has_official_title_evidence(ctx, official_title)
            _weak_anchor_j12 = vf_anchor in {"none", "search_only", "", "title_mention"}
            if (
                _has_bucket_store
                and _bucket_score <= 0
                and _weak_anchor_j12
                and (not _official_title_evidence_j12)
                and (not has_strong_suspected_title)
            ):
                _fallback_type = "undecodable_reference" if _has_title_masking else "noise"
                print(
                    f"[{_ts()}] 🚫 evidence bucket 차단(J12): title='{official_title}', "
                    f"bucket_score={_bucket_score}, anchor='{vf_anchor}', "
                    f"official_evidence={_official_title_evidence_j12} "
                    f"→ is_relevant=false, discussion_type='{_fallback_type}'",
                    file=sys.stderr,
                )
                is_relevant = False
                official_title = None
                confidence = "None"
                discussion_type = _fallback_type

        # ── 가드 J12.5: 약앵커 + 모호 후보 다중 충돌 시 단일 제목 고정 억제 ──
        # blanket 차단이 아닌 "모호도 높음" 조건에서만 발동.
        # 단, 제목 약칭 안정 신호가 강하면(제목 직접 약칭 + 검색 반복 언급) 면제한다.
        if is_relevant and official_title:
            _weak_anchor_j125 = vf_anchor in {"none", "search_only", "", "title_mention"}
            _official_title_evidence_j125 = self._has_official_title_evidence(ctx, official_title)
            _amb_j125 = self._analyze_title_ambiguity(ctx, official_title)
            _abbrev_stable_j125 = self._has_title_abbrev_stability_signal(ctx, official_title)
            if (
                _weak_anchor_j125
                and (not _official_title_evidence_j125)
                and _amb_j125.get("is_ambiguous", False)
                and (not _abbrev_stable_j125)
                and (not _has_episode_ref)
            ):
                _old_title_j125 = official_title
                official_title = None
                heretic_url = None
                _title_deliberately_null = True
                if confidence in ("High", "Max"):
                    confidence = "Medium"
                elif confidence in ("None", "", None):
                    confidence = "Low"
                if discussion_type in {"review", "spoiler", "character_talk", "meme"}:
                    discussion_type = "general"
                print(
                    f"[{_ts()}] 🧭 모호도 가드(J12.5): "
                    f"weak_anchor + ambiguous_candidates → single-title 고정 해제 "
                    f"('{_old_title_j125}' -> null, top_gap={_amb_j125.get('top_gap')}, "
                    f"candidate_count={_amb_j125.get('candidate_count')})",
                    file=sys.stderr,
                )
            elif _weak_anchor_j125 and _amb_j125.get("is_ambiguous", False) and _abbrev_stable_j125:
                print(
                    f"[{_ts()}] 🛡️ 모호도 가드 면제(J12.5): "
                    f"title='{official_title}' abbreviation stability signal=true",
                    file=sys.stderr,
                )
        
        # ━━ 개선: 일반어 패턴 부정 신호 (하드코딩 대신 패턴 기반) ━━
        # 고유명사/앵커가 없고, 매칭된 키워드가 일반어인 경우 → FP 의심
        if is_relevant and official_title and not has_work_anchor:
            _general_word_signal = self._check_general_word_signal(
                official_title, ctx, vf_grounding
            )
            if _general_word_signal:
                print(
                    f"[{_ts()}] 🚫 일반어 부정 신호: '{official_title}' → "
                    f"고유 앵커 없이 일반어 패턴만으로 매칭됨 → confidence 하향",
                    file=sys.stderr,
                )
                if confidence in ("High", "Max"):
                    confidence = "Low"
                if not has_strong_suspected_title:
                    is_relevant = False
                    discussion_type = "noise"
        
        # Confidence normalization
        confidence = self._normalize_confidence(confidence)
        
        # Validate heretic_url against search + fetched page evidence.
        if heretic_url:
            heretic_url = self._validate_heretic_url(
                heretic_url,
                ctx,
                identified_title=official_title,
            )
            # 검증된 heretic_url의 실제 페이지 제목으로 저신뢰 title 교정
            if is_relevant and heretic_url:
                fetched_title = self._extract_title_from_validated_url(ctx, heretic_url)
                if fetched_title:
                    official_is_branding = self._is_platform_branding_title(official_title)
                    fetched_is_branding = self._is_platform_branding_title(fetched_title)
                    has_official_title_evidence = bool(
                        official_title and self._has_official_title_evidence(ctx, official_title)
                    )
                    # official_title이 비어 있을 때 URL title로 신규 승격하지 않는다.
                    # (검색/작가목록/브랜딩 문구가 작품명으로 오염되는 케이스 방지)
                    should_replace = False
                    if official_title:
                        should_replace = (
                            (
                                confidence in ("Low", "None")
                                and (not has_official_title_evidence)
                                and (not self._text_matches_phrase(fetched_title, official_title))
                                and (not fetched_is_branding)
                            )
                            or (
                                official_is_branding
                                and not fetched_is_branding
                                and (not self._text_matches_phrase(fetched_title, official_title))
                            )
                        )
                    if should_replace:
                        old_title = official_title
                        official_title = fetched_title
                        print(
                            f"[{_ts()}] 🔄 heretic_url 제목 교정: "
                            f"'{old_title}' -> '{official_title}' "
                            f"(url={heretic_url}, conf={confidence})",
                            file=sys.stderr,
                        )

        # 검증된 약칭 기반 제목 강제 복구 (LLM 흔들림 방지)
        if is_relevant and official_title:
            official_title, heretic_url = self._apply_known_abbreviation_title_guard(
                ctx,
                official_title=official_title,
                heretic_url=heretic_url,
            )

        # ── 가드 J13: 약칭+커뮤니티 근거 단독 고정 차단 ──
        # 조건:
        # - 관련 판정이지만 공식 플랫폼 근거/검증 URL이 없음
        # - Verifier 근거 타입이 community_mention 중심
        # - 앵커가 title_mention(약칭) 수준이고 본문 고유명사도 빈약
        # - Synthesizer도 단일 작품 식별을 부정
        # => 단일 작품명을 확정하지 않고 undecodable_reference로 강등
        if is_relevant and official_title:
            _official_ev_j13 = self._has_official_title_evidence(ctx, official_title)
            _vf_novel_j13 = (vf_result.get("novel_identity") or {}) if isinstance(vf_result, dict) else {}
            _vf_ev_type_j13 = str(_vf_novel_j13.get("evidence_type") or "").strip().lower()
            _syn_out_j13 = ctx.get_expert_output(ExpertType.SYNTHESIZER) or {}
            _syn_ca_j13 = _syn_out_j13.get("confidence_assessment") or {}
            _syn_about_work_j13 = bool(_syn_ca_j13.get("is_about_identified_work"))
            _has_specific_names_j13 = bool(gk_context_clues.get("has_specific_names", False))

            _post_data_j13 = getattr(ctx, "post_data", None) or {}
            _title_text_j13 = str(_post_data_j13.get("title") or "")
            _body_chunks_j13: List[str] = []
            for _blk_j13 in (_post_data_j13.get("content_blocks") or []):
                if isinstance(_blk_j13, dict):
                    _body_chunks_j13.append(str(_blk_j13.get("text") or ""))
                elif isinstance(_blk_j13, str):
                    _body_chunks_j13.append(_blk_j13)
            _raw_post_j13 = " ".join([_title_text_j13] + _body_chunks_j13)
            _title_norm_j13 = self._normalize_match_text(official_title)
            _post_norm_j13 = self._normalize_match_text(_raw_post_j13)
            _has_full_title_literal_j13 = bool(
                _title_norm_j13 and _post_norm_j13 and _title_norm_j13 in _post_norm_j13
            )

            if (
                (not _official_ev_j13)
                and not heretic_url
                and vf_anchor in {"title_mention", "search_only", "none", ""}
                and _vf_ev_type_j13 in {"community_mention", "search_only", "community_title_match", ""}
                and (not _syn_about_work_j13)
                and (not _has_specific_names_j13)
                and (not _has_full_title_literal_j13)
                and (not _has_episode_ref)
            ):
                _old_title_j13 = official_title
                is_relevant = False
                official_title = None
                confidence = "Low" if confidence in ("High", "Max", "Medium") else confidence
                discussion_type = "undecodable_reference" if _has_title_masking else "noise"
                print(
                    f"[{_ts()}] 🚫 약칭-커뮤니티 단독 고정 차단(J13): "
                    f"title='{_old_title_j13}', anchor='{vf_anchor}', "
                    f"evidence_type='{_vf_ev_type_j13}', syn_about_work={_syn_about_work_j13}, "
                    f"official_evidence={_official_ev_j13}, heretic_url={bool(heretic_url)} "
                    f"→ is_relevant=false, discussion_type='{discussion_type}'",
                    file=sys.stderr,
                )
            else:
                # ── 가드 J13.5: URL 단독 승격 차단 ──
                # Decoder가 작품명을 끝내 식별하지 못했고, Verifier가 title_mention + URL 근거만으로
                # 승격한 케이스를 차단한다. (커뮤니티 복합어/합성어 제목 오매칭 방지)
                _dec_out_j135 = ctx.get_expert_output(ExpertType.DECODER) or {}
                _dec_has_title_j135 = False
                _dec_has_strong_anchor_j135 = False
                for _dt_j135 in _dec_out_j135.get("decoded_terms", []) or []:
                    if not isinstance(_dt_j135, dict):
                        continue
                    _bm_j135 = _dt_j135.get("best_match") or {}
                    _bm_title_j135 = str(_bm_j135.get("title") or "").strip()
                    _bm_conf_j135 = str(_bm_j135.get("confidence") or "").strip().lower()
                    _gr_j135 = _dt_j135.get("grounding") or {}
                    _anchor_j135 = str(_gr_j135.get("anchor_type") or "").strip().lower()
                    if _bm_title_j135 and _bm_conf_j135 not in ("none", ""):
                        _dec_has_title_j135 = True
                    if (
                        _bm_title_j135
                        and _bm_conf_j135 in ("high", "medium", "max")
                        and _anchor_j135 in ("character_title_link", "plot_mention", "character_mention", "author_mention")
                    ):
                        _dec_has_strong_anchor_j135 = True
                _has_verified_char_links_j135 = bool(getattr(ctx, "verified_character_work_links", []))
                if (
                    _vf_ev_type_j13 in {"search_platform_url", "official_url", "search_snippet", "community_mention", "community_title_match", ""}
                    and vf_anchor in {"title_mention", "search_only", "none", ""}
                    and (not _dec_has_title_j135)
                    and (not _dec_has_strong_anchor_j135)
                    and (not _has_full_title_literal_j13)
                    and (not _has_verified_char_links_j135)
                    and (not _has_episode_ref)
                ):
                    _old_title_j135 = official_title
                    is_relevant = False
                    official_title = None
                    heretic_url = None
                    confidence = "None"
                    discussion_type = "undecodable_reference" if _has_title_masking else "noise"
                    print(
                        f"[{_ts()}] 🚫 URL 단독 승격 차단(J13.5): "
                        f"title='{_old_title_j135}', evidence_type='{_vf_ev_type_j13}', "
                        f"anchor='{vf_anchor}', decoder_has_title={_dec_has_title_j135}, "
                        f"full_title_literal={_has_full_title_literal_j13}, "
                        f"verified_char_links={_has_verified_char_links_j135} "
                        f"→ is_relevant=false, discussion_type='{discussion_type}'",
                        file=sys.stderr,
                    )
        
        # Build NovelIdentity only for relevant outputs.
        novel_identity = None
        if is_relevant and (official_title or heretic_url):
            novel_identity = NovelIdentity(
                official_title=official_title,
                heretic_url=heretic_url,
                confidence=confidence,
            )
        
        # Reason synthesis
        # NOTE:
        # - vf_result는 이미 verifier_out["verification_result"] (inner payload)다.
        # - verifier_out은 {"verification_result": ..., "reason": ...} wrapper다.
        # 과거에는 vf_result에서 다시 verification_result를 꺼내면서 빈 dict가 되어
        # verifier inference/rejection 근거가 소실되었다.
        verification_result = vf_result if isinstance(vf_result, dict) else {}
        verifier_rejection_reason = verification_result.get("rejection_reason", "")
        verifier_reason = ""
        if isinstance(verifier_out, dict):
            verifier_reason = self._clean_reason_text(verifier_out.get("reason", ""))
        if not verifier_reason:
            verifier_reason = self._clean_reason_text(verification_result.get("reason", ""))
        arbiter_reason = final_decision.get("final_reasoning") or arbiter_out.get("final_reasoning", "")
        grounding_issue = (verification_result.get("grounding_check", {}) or {}).get("grounding_issue", "")
        counter_arguments = verification_result.get("counter_arguments", []) or []

        # 우선순위 개선:
        # 비관련 포스트는 단일 reason 문자열을 고정 우선순위로 고르지 않고
        # 후보 근거를 점수화해 상위 근거를 합성한다.
        reason = ""
        has_non_relevant_evidence = any(
            [
                verifier_rejection_reason,
                verifier_reason,
                grounding_issue,
                bool(counter_arguments),
                arbiter_reason,
            ]
        )
        if (not is_relevant) and has_non_relevant_evidence:
            # Arbiter 원출력(final_decision)과 후처리 최종값(is_relevant/discussion_type)이
            # 어긋나는 경우가 있어 reason 합성 필터가 잘못 동작할 수 있다.
            # reason 합성에는 "최종 반영 상태"를 우선 전달한다.
            _effective_final_decision = dict(final_decision or {})
            _effective_final_decision["is_relevant"] = is_relevant
            _effective_final_decision["discussion_type"] = discussion_type
            if official_title is None:
                _effective_final_decision["official_title"] = None
                _effective_final_decision["official_novel_title"] = None
            elif official_title:
                _effective_final_decision["official_title"] = official_title
                _effective_final_decision["official_novel_title"] = official_title
            reason = self._format_non_relevant_reason(
                discussion_type=discussion_type,
                rejection_reason=verifier_rejection_reason,
                verifier_reason=verifier_reason,
                arbiter_reason=arbiter_reason,
                grounding_issue=grounding_issue,
                counter_arguments=counter_arguments,
                ctx=ctx,
                verification_result=verification_result,
                final_decision=_effective_final_decision,
            )

        if not reason:
            reason = arbiter_reason

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
                reason = verification_result.get("rejection_reason") or verifier_reason
            else:
                reason = verifier_reason

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

        # ── 신작 패턴 가드(J7) reason 동기화 ──
        # J7에서 잘못된 제목을 null로 바꿨으면 reason도 교정
        _j7_fix = getattr(ctx, "_j7_shinwork_reason_fix", None)
        if _j7_fix and isinstance(reason, str) and reason.strip():
            _old_t = _j7_fix.get("old_title", "")
            _auth = _j7_fix.get("author", "")
            if _old_t and _old_t in reason:
                # 잘못된 제목을 reason에서 교정
                reason = reason.replace(
                    f"'{_old_t}'",
                    f"작가 '{_auth}'의 신작 (정식 제목 미확정)"
                ).replace(
                    f"\u2018{_old_t}\u2019",  # ' ' 형태
                    f"작가 '{_auth}'의 신작 (정식 제목 미확정)"
                )
                # 제목이 문장 내 따옴표 없이 등장하는 경우
                if _old_t in reason:
                    reason = reason.replace(
                        _old_t,
                        f"작가 '{_auth}'의 신작"
                    )
                reason += f" [신작 가드: 검색에서 '{_old_t}'을(를) 찾았으나, 게시글이 '{_auth} 신작'으로만 언급하여 정확한 제목을 확정할 수 없음]"
                print(
                    f"[{_ts()}] 🛡️ J7 reason 동기화: '{_old_t}' → '작가 {_auth}의 신작 (미확정)'",
                    file=sys.stderr,
                )
        
        # ── 시간참조 가드 reason 동기화 ──
        # Arbiter의 시간참조 가드가 title을 null로 바꿨을 때 (_title_deliberately_null)
        # reason에 해당 제목이 남아있으면 교정
        if _title_deliberately_null and not _j7_fix:
            _arb_notes = final_decision.get("notes", "")
            if "시간참조 불확정" in str(_arb_notes):
                # Arbiter가 원래 설정했던 제목 추출
                _orig_arb_title = (
                    arbiter_out.get("final_decision", {}).get("official_novel_title")
                    or arbiter_out.get("final_decision", {}).get("official_title")
                    or ""
                )
                if _orig_arb_title and isinstance(reason, str) and _orig_arb_title in reason:
                    # 작가 식별 시도
                    _sync_author = metadata.get("detected_author", "") or ""
                    _replacement = f"작가 '{_sync_author}'의 신작 (정식 제목 미확정)" if _sync_author else "(정식 제목 미확정)"
                    reason = reason.replace(f"'{_orig_arb_title}'", _replacement)
                    if _orig_arb_title in reason:
                        reason = reason.replace(_orig_arb_title, _replacement)
                    reason += f" [시간참조 가드: '{_orig_arb_title}'은(는) 본문에 미등장하여 제목 불확정]"
                    print(
                        f"[{_ts()}] 🛡️ 시간참조 reason 동기화: '{_orig_arb_title}' 교정 완료",
                        file=sys.stderr,
                    )

        # ── Arbiter title 필드 충돌 시 reason 동기화 ──
        # LLM 원출력 official_novel_title과 후처리 official_title이 다를 때
        # reason 안에 원출력 제목이 남아 최종 출력과 모순되는 문제를 교정한다.
        try:
            _norm = lambda s: str(s or "").replace(" ", "").lower()
            if (
                isinstance(reason, str)
                and reason
                and _arb_official_title
                and _arb_official_novel_title
                and _norm(_arb_official_title) != _norm(_arb_official_novel_title)
                and official_title
                and _norm(official_title) == _norm(_arb_official_title)
            ):
                if _arb_official_novel_title in reason:
                    reason = reason.replace(_arb_official_novel_title, _arb_official_title)
                    print(
                        f"[{_ts()}] 🛡️ reason 제목 동기화: "
                        f"'{_arb_official_novel_title}' -> '{_arb_official_title}'",
                        file=sys.stderr,
                    )
        except Exception:
            pass
        
        # Keep reason aligned with final relevance flags.
        reason = self._sanitize_reason(
            reason,
            is_relevant=is_relevant,
            discussion_type=discussion_type,
            official_title=official_title,
        )

        # JSON 가독성을 위해 reason 줄바꿈 정규화
        reason_lines = self._reason_to_lines(reason, width=self.reason_wrap_width)
        if reason_lines:
            reason = "\n".join(reason_lines)
        
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
            reason_lines=reason_lines if reason_lines else None,
        )
        
        # Notes 수집 (Decoder/Arbiter의 notes 전달)
        analysis_notes = self._collect_notes(ctx)
        
        # PickvelAnalysis output
        analysis = None
        if detected_titles or metadata.get("micro_tags"):
            analysis = PickvelAnalysis(
                detected_titles=detected_titles if detected_titles else [],
                micro_tags=metadata.get("micro_tags", []),
                sentiment_profile=sentiment_profile,
                is_nsfw=bool(metadata.get("is_nsfw") or False),
                notes=analysis_notes,
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
            "작품 토론으로 판단",
            "작품 토론으로 분류",
            "작품 토론임",
        ]
        false_markers = [
            "is_relevant=false",
            "is_relevant = false",
            "is_relevant는 false",
            "is not relevant",
            "비관련 포스트로 판정",
            "종합 판정: 비관련 포스트",
            "판정: 비관련",
            "discussion_type: noise",
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
        if (not is_relevant) and AgenticPipeline._has_non_relevant_strong_positive_judgment(reason):
            return (
                f"비관련 포스트로 판정됨. discussion_type={dt}. "
                f"(reason 정합성 교정: 원문 reason에 작품 관련 결론 문구가 포함됨)"
            )

        # 관련 판정인데 "작품 토론이 아니다" 류 표현이 섞이면 의미 충돌을 완화한다.
        if is_relevant:
            conflict_pairs = [
                ("특정 소설 작품에 대한 실제 토론이 아닌", "작품의 심층 설정 토론보다는"),
                ("특정 소설에 대한 글이 아니다", "특정 소설에 대한 기대·반응 글이다"),
                ("작품 토론이 아닌", "작품 내용 심층 토론보다는"),
            ]
            fixed = reason
            for before, after in conflict_pairs:
                if before in fixed:
                    fixed = fixed.replace(before, after)
            if fixed != reason:
                reason = fixed

        return reason

    @staticmethod
    def _reason_to_lines(reason: Any, *, width: int = 110) -> List[str]:
        """
        reason 문자열을 사람이 읽기 쉬운 줄 단위로 분해한다.
        - 기존 개행은 보존
        - ' | ' / '; ' 구분자는 우선 분할
        - 각 조각은 width 기준으로 wrap
        """
        if not isinstance(reason, str) or not reason.strip():
            return []

        import re

        base_lines = [ln.rstrip() for ln in reason.splitlines() if ln and ln.strip()]
        if not base_lines:
            return []

        # 기본: LLM이 만든 개행/섹션 구조를 신뢰한다.
        # 비구조 라인이 지나치게 길 때만 후처리 래핑을 적용해 가독성만 보정.
        trust_llm_breaks = os.getenv("PIPELINE_REASON_TRUST_LLM_BREAKS", "1") == "1"
        # 강제 하드 래핑이 필요할 때만 활성화(기본 비활성).
        hard_wrap = os.getenv("PIPELINE_REASON_HARD_WRAP", "0") == "1"

        def _is_structured_line(line: str) -> bool:
            s = line.lstrip()
            if not s:
                return False
            if s.startswith("["):
                return True
            if s.startswith(("- ", "* ", "> ")):
                return True
            if re.match(r"^\d+\.\s", s):
                return True
            return False

        out: List[str] = []
        for line in base_lines:
            if trust_llm_breaks:
                if _is_structured_line(line):
                    out.append(line)
                    continue
                # 적당한 길이의 일반 라인은 LLM 개행 그대로 유지
                if (not hard_wrap) and len(line) <= max(80, width * 4):
                    out.append(line)
                    continue
                if hard_wrap and len(line) <= max(80, width * 2):
                    out.append(line)
                    continue

            chunks = [c.strip() for c in re.split(r"\s+\|\s+|;\s+", line) if c and c.strip()]
            if not chunks:
                continue
            for chunk in chunks:
                wrapped = textwrap.wrap(
                    chunk,
                    width=max(40, width),
                    break_long_words=False,
                    break_on_hyphens=False,
                )
                if wrapped:
                    out.extend(wrapped)
                else:
                    out.append(chunk)
        return out

    @staticmethod
    def _clean_reason_text(text: Any) -> str:
        if not isinstance(text, str):
            return ""
        return " ".join(text.split())

    @staticmethod
    def _has_non_relevant_negative_markers(text: str) -> bool:
        if not text:
            return False
        t = text.lower()
        markers = (
            "비관련",
            "관련 없음",
            "노이즈",
            "noise",
            "판정: 비관련",
            "discussion_type: noise",
            "is_relevant=false",
            "작품 토론이 아님",
            "작품 토론이 아니다",
            "특정 작품 토론이 아님",
            "고유 정보 없음",
            "근거 부족",
            "일반 토론",
            "잡담",
            "거부",
            "기각",
        )
        return any(m in t for m in markers)

    @staticmethod
    def _has_non_relevant_positive_markers(text: str) -> bool:
        if not text:
            return False
        t = text.lower()
        markers = (
            "매칭됨",
            "매칭 확정",
            "작품 식별",
            "관련 포스트",
            "is_relevant=true",
            "해당 작품",
            "작품 토론으로 판단",
            "작품 토론으로 분류",
            "작품 토론임",
            "토론(리뷰)",
            "리뷰로 판단",
            "등장인물로 확인",
        )
        return any(m in t for m in markers)

    @staticmethod
    def _has_non_relevant_strong_positive_judgment(text: str) -> bool:
        if not text:
            return False
        t = text.lower()
        strong_markers = (
            "작품 토론으로 판단",
            "작품 토론으로 분류",
            "작품 토론임",
            "관련 포스트로 판정",
            "is_relevant=true",
            "is_relevant = true",
            "등장인물로 확인",
            "해당 작품의",
            "리뷰로 분류",
        )
        return any(m in t for m in strong_markers)

    def _sanitize_non_relevant_llm_reason(self, text: str) -> str:
        clean = self._clean_reason_text(text)
        if not clean:
            return ""
        # 비관련 reason인데 "작품 토론으로 판단" 류의 강한 관련 결론은 폐기.
        if self._has_non_relevant_strong_positive_judgment(clean):
            return ""
        # 비관련 reason인데 긍정 신호만 있으면(부정 신호 없음) 버리고 상위 근거로 대체한다.
        if self._has_non_relevant_positive_markers(clean) and not self._has_non_relevant_negative_markers(clean):
            return ""
        return clean

    def _clip_reason_text(self, text: Any, width: int) -> str:
        clean = self._clean_reason_text(text)
        if not clean:
            return ""
        if self.reason_full_mode:
            return clean
        return textwrap.shorten(clean, width=width, placeholder=" ...")

    @staticmethod
    def _severity_bonus(severity: str) -> float:
        sev = (severity or "").strip().lower()
        if sev == "critical":
            return 0.18
        if sev == "major":
            return 0.12
        if sev == "minor":
            return 0.06
        return 0.02

    def _rank_non_relevant_reason_candidates(
        self,
        *,
        rejection_reason: str,
        verifier_reason: str,
        arbiter_reason: str,
        grounding_issue: str,
        counter_arguments: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []

        def _push(source: str, text: Any, base: float, severity: str = "") -> None:
            clean = self._clean_reason_text(text)
            if not clean:
                return
            # 비관련 reason 랭킹에서는 강한 관련 결론 문장을 후보에서 제외한다.
            if self._has_non_relevant_strong_positive_judgment(clean):
                return
            if self._has_non_relevant_positive_markers(clean) and not self._has_non_relevant_negative_markers(clean):
                return

            score = base + self._severity_bonus(severity)
            if len(clean) >= 45:
                score += 0.02
            if len(clean) >= 100:
                score += 0.02
            if any(
                token in clean
                for token in (
                    "작품 고유 정보",
                    "본문",
                    "앵커",
                    "줄거리",
                    "캐릭터",
                    "키워드 우연",
                    "미언급",
                    "장르",
                    "일반론",
                )
            ):
                score += 0.03

            score = max(0.0, min(0.99, score))
            candidates.append(
                {
                    "source": source,
                    "text": clean,
                    "score": score,
                }
            )

        _push("Verifier.rejection_reason", rejection_reason, 0.90)
        _push("Verifier.grounding_issue", grounding_issue, 0.84)
        _push("Verifier.reason", verifier_reason, 0.76)
        _push("Arbiter.final_reasoning", arbiter_reason, 0.62)

        counter_iter = counter_arguments
        if not self.reason_full_mode:
            counter_iter = counter_arguments[:6]
        for idx, arg in enumerate(counter_iter):
            if not isinstance(arg, dict):
                continue
            issue = arg.get("issue", "")
            severity = str(arg.get("severity", "") or "")
            source = f"Verifier.counter_arguments[{idx + 1}]"
            _push(source, issue, 0.70, severity=severity)

        merged: List[Dict[str, Any]] = []
        for cand in candidates:
            cand_text = str(cand.get("text") or "")
            cand_key = self._normalize_match_text(cand_text)[:220] or cand_text
            existing = None
            for item in merged:
                existing_key = item.get("_key", "")
                if not existing_key:
                    continue
                if cand_key == existing_key or cand_key in existing_key or existing_key in cand_key:
                    existing = item
                    break

            if existing is None:
                merged.append(
                    {
                        "_key": cand_key,
                        "text": cand_text,
                        "score": float(cand.get("score", 0.0)),
                        "sources": [cand.get("source", "")],
                    }
                )
                continue

            existing["score"] = max(float(existing.get("score", 0.0)), float(cand.get("score", 0.0)))
            source = str(cand.get("source", "")).strip()
            if source and source not in existing.get("sources", []):
                existing["sources"].append(source)

        ranked = sorted(
            [{k: v for k, v in item.items() if k != "_key"} for item in merged],
            key=lambda item: (float(item["score"]), len(str(item["text"]))),
            reverse=True,
        )
        return ranked

    def _llm_review_non_relevant_reason(
        self,
        *,
        discussion_type: str,
        ranked_candidates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not self.enable_reason_llm_review:
            return {}
        if len(ranked_candidates) < self.reason_llm_review_min_candidates:
            return {}

        payload_candidates: List[Dict[str, Any]] = []
        candidate_slice = ranked_candidates[:8]
        if self.reason_full_mode:
            candidate_slice = ranked_candidates[: self.reason_full_candidate_cap]
        for idx, item in enumerate(candidate_slice, start=1):
            payload_candidates.append(
                {
                    "id": idx,
                    "score": round(float(item.get("score", 0.0)), 3),
                    "sources": item.get("sources", []),
                    "text": self._clip_reason_text(item.get("text", ""), width=260),
                }
            )

        payload = {
            "discussion_type": discussion_type,
            "candidates": payload_candidates,
        }

        try:
            reviewed = self.llm.review_reason_candidates(payload)
        except Exception as exc:
            print(f"[{_ts()}] ⚠️ reason LLM review 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
            return {}

        if not isinstance(reviewed, dict):
            return {}

        selected_ids = reviewed.get("selected_ids", [])
        if not isinstance(selected_ids, list):
            selected_ids = []
        normalized_ids: List[int] = []
        for sid in selected_ids:
            try:
                sid_int = int(sid)
            except Exception:
                continue
            if 1 <= sid_int <= len(payload_candidates):
                normalized_ids.append(sid_int)

        _primary = self._clean_reason_text(reviewed.get("primary_reason", ""))
        _merged = self._clean_reason_text(reviewed.get("merged_reason", ""))
        _note = self._clean_reason_text(reviewed.get("llm_review_note", ""))
        _conf = self._clean_reason_text(reviewed.get("review_confidence", ""))

        # 비관련 reason 정합성: LLM이 "매칭됨" 류 문장을 내면 제거
        _primary = self._sanitize_non_relevant_llm_reason(_primary)
        _merged = self._sanitize_non_relevant_llm_reason(_merged)

        return {
            "selected_ids": normalized_ids,
            "primary_reason": _primary,
            "merged_reason": _merged,
            "llm_review_note": _note,
            "review_confidence": _conf,
        }

    def _format_non_relevant_reason(
        self,
        *,
        discussion_type: Optional[str],
        rejection_reason: str,
        verifier_reason: str,
        arbiter_reason: str,
        grounding_issue: str,
        counter_arguments: List[Dict[str, Any]],
        ctx: Optional[ConversationContext] = None,
        verification_result: Optional[Dict[str, Any]] = None,
        final_decision: Optional[Dict[str, Any]] = None,
    ) -> str:
        """비관련 판정 reason을 섹션형 요약 + 점수 기반 근거로 구성한다."""
        dt = discussion_type or "noise"
        verification_result = verification_result or {}
        final_decision = final_decision or {}
        arbiter_reason_for_rank = self._clean_reason_text(arbiter_reason)
        if arbiter_reason_for_rank:
            _arb_lower = arbiter_reason_for_rank.lower()
            _arbiter_error = "arbiter 오류로 verifier 결과 사용" in _arb_lower
            _negative_markers = (
                "비관련",
                "관련 없음",
                "거부권",
                "작품 토론이 아니다",
                "일반 토론",
                "고유 정보 없음",
                "노이즈",
                "noise",
            )
            _positive_markers = (
                "작품 토론",
                "리뷰",
                "특정 작품",
                "is_relevant=true",
                "관련 포스트",
                "결말 내용",
            )
            _has_negative = any(tok in _arb_lower for tok in _negative_markers)
            _has_positive = any(tok in _arb_lower for tok in _positive_markers)
            if _arbiter_error:
                # Arbiter 예외 fallback 문구는 근거 오염을 유발하므로 점수 후보에서 제외
                arbiter_reason_for_rank = ""
            elif (
                final_decision.get("is_relevant") is False
                and (rejection_reason or verifier_reason)
                and _has_positive
                and not _has_negative
            ):
                # 최종 비관련인데 Arbiter 문구가 관련 판정을 주장하면 제외
                arbiter_reason_for_rank = ""
            elif (
                final_decision.get("is_relevant") is False
                and (rejection_reason or verifier_reason)
            ):
                # 최종 비관련일 때 Arbiter reason이 "관련" 결론을 명시하면 제외
                # (문장 일부에 부정 단어가 섞여도 결론이 관련 판정이면 근거 오염)
                _strong_positive_markers = (
                    "작품 토론으로 판정",
                    "관련 포스트로 판정",
                    "is_relevant=true",
                    "is_relevant = true",
                    "해당 웹소설에 대한 토론임",
                )
                if any(tok in _arb_lower for tok in _strong_positive_markers):
                    arbiter_reason_for_rank = ""

        def _brief(text: Any, width: int) -> str:
            clean = self._clean_reason_text(text)
            if not clean:
                return ""
            if self.reason_full_mode:
                return clean
            return textwrap.shorten(clean, width=max(20, width), placeholder=" ...")

        ranked = self._rank_non_relevant_reason_candidates(
            rejection_reason=rejection_reason,
            verifier_reason=verifier_reason,
            arbiter_reason=arbiter_reason_for_rank,
            grounding_issue=grounding_issue,
            counter_arguments=counter_arguments,
        )
        llm_review = self._llm_review_non_relevant_reason(
            discussion_type=dt,
            ranked_candidates=ranked,
        )

        reviewed_ids = llm_review.get("selected_ids", []) if isinstance(llm_review, dict) else []
        reviewed_items: List[Dict[str, Any]] = []
        for rid in reviewed_ids:
            if isinstance(rid, int) and 1 <= rid <= len(ranked):
                reviewed_items.append(ranked[rid - 1])
        if not reviewed_items:
            reviewed_items = ranked

        llm_primary_reason = self._clean_reason_text(
            llm_review.get("primary_reason", "") if isinstance(llm_review, dict) else ""
        )
        llm_merged_reason = self._clean_reason_text(
            llm_review.get("merged_reason", "") if isinstance(llm_review, dict) else ""
        )
        llm_note = self._clean_reason_text(
            llm_review.get("llm_review_note", "") if isinstance(llm_review, dict) else ""
        )
        llm_conf = self._clean_reason_text(
            llm_review.get("review_confidence", "") if isinstance(llm_review, dict) else ""
        )

        lines: List[str] = []

        if not ranked:
            lines.extend(["[판정 요약]", "- 판정: 비관련", f"- discussion_type: {dt}", "- 핵심 결론: 작품 고유 근거 부족"])
            return "\n".join(lines)

        top = reviewed_items[0]
        top_text = _brief(top.get("text", ""), width=220)
        if self.reason_full_mode:
            core_reason = self._clean_reason_text(llm_primary_reason) or self._clean_reason_text(top.get("text", ""))
        else:
            core_reason = _brief(llm_primary_reason, width=220) or top_text

        lines.extend(
            [
                "[판정 요약]",
                "- 판정: 비관련",
                f"- discussion_type: {dt}",
                f"- 핵심 결론: {core_reason}",
            ]
        )

        # 원문 요약
        post_title = ""
        post_body = ""
        comment_hints: List[str] = []
        inferred_topic = ""
        if ctx is not None:
            post_data = getattr(ctx, "post_data", None) or {}
            post_title = self._clean_reason_text(post_data.get("title", ""))
            body_chunks: List[str] = []
            for block in (post_data.get("content_blocks") or []):
                if isinstance(block, dict):
                    txt = self._clean_reason_text(block.get("text", ""))
                else:
                    txt = self._clean_reason_text(block)
                if txt:
                    body_chunks.append(txt)
                if len(body_chunks) >= 2:
                    break
            post_body = " / ".join(body_chunks)

            for c in (getattr(ctx, "comments", None) or [])[:3]:
                c_clean = self._clean_reason_text(c)
                if c_clean:
                    comment_hints.append(_brief(c_clean, width=100))

            # 원문 해석 주제는 최종 비관련 판정과 정합되도록 다중 근거를 종합한다.
            # 우선순위: Verifier/Discourse(고신뢰) > Synthesizer(보조)
            non_workish_types = {
                "noise",
                "trope_discussion",
                "genre_opinion",
                "community_banter",
                "off_topic",
                "meta",
                "image_post",
                "undecodable_reference",
            }
            verifier_topic = ""
            verifier_inference = verification_result.get("inference") or {}
            if isinstance(verifier_inference, dict):
                inf_type = self._clean_reason_text(verifier_inference.get("type", ""))
                inf_topic = self._clean_reason_text(verifier_inference.get("topic", ""))
                if inf_type and inf_topic:
                    inf_type_l = inf_type.lower()
                    inf_topic_l = inf_topic.lower()
                    # discussion 계열 타입은 접두어를 붙이지 않고 주제문만 사용한다.
                    if inf_type_l.endswith("_discussion") or inf_type_l in {"discuss_work", "discuss_genre", "express_opinion"}:
                        verifier_topic = inf_topic
                    else:
                        verifier_topic = inf_topic if inf_type_l in inf_topic_l else f"{inf_type}: {inf_topic}"
                elif inf_topic:
                    verifier_topic = inf_topic
                elif inf_type:
                    # 비관련 계열에서는 work_discussion 단독 타입을 주제로 쓰지 않는다.
                    inf_type_l = inf_type.lower()
                    if dt in non_workish_types and inf_type_l in {"work_discussion", "discuss_work"}:
                        verifier_topic = ""
                    else:
                        verifier_topic = inf_type

            discourse_intent = ""
            discourse_subject = ""
            discourse_out = ctx.get_expert_output(ExpertType.DISCOURSE) or {}
            discourse_analysis = discourse_out.get("discourse_analysis") or {}
            if isinstance(discourse_analysis, dict):
                discourse_intent = self._clean_reason_text(discourse_analysis.get("intent", ""))
                discourse_subject = self._clean_reason_text(discourse_analysis.get("real_subject", ""))

            synth_topic = ""
            synth_out = ctx.get_expert_output(ExpertType.SYNTHESIZER) or {}
            confidence_assessment = synth_out.get("confidence_assessment") or {}
            reinterpretation = synth_out.get("reinterpretation") or {}
            if isinstance(reinterpretation, dict):
                synth_topic = self._clean_reason_text(reinterpretation.get("post_intent", ""))
            if not synth_topic and isinstance(confidence_assessment, dict):
                synth_topic = self._clean_reason_text(confidence_assessment.get("reasoning", ""))

            topic_by_discussion_type = {
                "noise": "장르/트로프 일반 토론 또는 커뮤니티 잡담",
                "trope_discussion": "장르/트로프에 대한 일반 토론",
                "genre_opinion": "장르 설정/클리셰에 대한 일반 의견",
                "community_banter": "커뮤니티 은어/밈 중심 잡담",
                "author_talk": "작가/창작 성향에 대한 일반 토론 (특정 작품 미특정)",
                "recommendation": "추천 요청/탐색 질문 (특정 작품 미특정)",
                "meta": "플랫폼/커뮤니티 메타 이슈 토론",
                "off_topic": "소설과 무관한 일반 주제 토론",
                "image_post": "이미지 중심 게시글 (텍스트 근거 부족)",
                "undecodable_reference": "작품 관련 언급은 있으나 특정 작품 식별 불가",
            }
            generic_topic = topic_by_discussion_type.get(dt, "특정 작품 식별 근거가 부족한 일반 토론")

            title_hints: List[str] = []
            for st in (getattr(ctx, "suspected_titles", None) or []):
                if not isinstance(st, dict):
                    continue
                t = self._clean_reason_text(st.get("title", ""))
                if t:
                    title_hints.append(t)

            def _topic_looks_work_specific(topic_text: str) -> bool:
                if not topic_text:
                    return False
                # "작품" 단어 자체는 일반문맥에도 쓰이므로, 고유명사 신호가 섞였을 때만 작품특정으로 본다.
                strong_markers = (
                    "작품 '",
                    "작품 \"",
                    "웹소설의",
                    "주인공이",
                    "작가:",
                    "내용에 대한 감상",
                    "특정 작품",
                )
                if any(marker in topic_text for marker in strong_markers):
                    return True
                for hint in title_hints[:8]:
                    if self._text_matches_phrase(topic_text, hint):
                        return True
                return False

            if verifier_topic:
                inferred_topic = verifier_topic
            elif discourse_intent in {"discuss_genre", "genre_discussion", "express_opinion"}:
                inferred_topic = generic_topic
            elif discourse_subject and not _topic_looks_work_specific(discourse_subject):
                inferred_topic = discourse_subject
            elif synth_topic and not _topic_looks_work_specific(synth_topic):
                inferred_topic = synth_topic
            else:
                inferred_topic = generic_topic

            # 최종 가드: 비관련 판정 reason의 "원문 해석"은 작품 특정형 문구를 금지한다.
            if _topic_looks_work_specific(inferred_topic):
                inferred_topic = generic_topic

            # 추가 가드: 비관련 계열인데 해석 주제가 suspected_titles 토큰을 끌고오면 장르 일반론으로 강등.
            # 예: "후피집 (장르)"처럼 작품 약칭 토큰이 섞여도 최종 판정이 비관련이면 일반 주제로 유지.
            if dt in non_workish_types and inferred_topic and title_hints:
                stop_tokens = {"장르", "트로프", "일반", "토론", "의견", "설정", "밈", "잡담", "클리셰"}

                def _split_topic_tokens(text: str) -> List[str]:
                    raw = (
                        text.replace("(", " ")
                        .replace(")", " ")
                        .replace("/", " ")
                        .replace(":", " ")
                        .replace("-", " ")
                        .split()
                    )
                    out: List[str] = []
                    for token in raw:
                        norm = self._normalize_match_text(token)
                        if norm and len(norm) >= 2:
                            out.append(norm)
                    return out

                topic_tokens = [t for t in _split_topic_tokens(inferred_topic) if t not in stop_tokens]
                if topic_tokens:
                    hint_blob = " ".join(str(h) for h in title_hints[:8])
                    if any(tok in hint_blob for tok in topic_tokens):
                        inferred_topic = generic_topic

            inferred_topic = _brief(inferred_topic, width=180)

        if any([post_title, post_body, comment_hints, inferred_topic]):
            lines.append("")
            lines.append("[원문 해석]")
            if post_title:
                lines.append(f"- 제목: {_brief(post_title, width=120)}")
            if post_body:
                lines.append(f"- 본문 요약: {_brief(post_body, width=220)}")
            if comment_hints:
                lines.append(f"- 댓글 힌트: {' | '.join(comment_hints)}")
            if inferred_topic:
                lines.append(f"- 해석 주제: {_brief(inferred_topic, width=180)}")

        # 전문가별 판단 요약
        expert_lines: List[str] = []
        if ctx is not None:
            gatekeeper_out = ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
            gk_post_type = str(gatekeeper_out.get("post_type") or "").strip()
            gk_conf = str(gatekeeper_out.get("confidence") or "").strip()
            if gk_post_type or gk_conf:
                gk_parts = []
                if gk_post_type:
                    gk_parts.append(f"post_type={gk_post_type}")
                if gk_conf:
                    gk_parts.append(f"confidence={gk_conf}")
                expert_lines.append(f"- Gatekeeper: {', '.join(gk_parts)}")

            discourse_out = ctx.get_expert_output(ExpertType.DISCOURSE) or {}
            da = discourse_out.get("discourse_analysis") or {}
            if isinstance(da, dict):
                domain = str(da.get("primary_domain") or "").strip()
                intent = str(da.get("intent") or "").strip()
                if domain or intent:
                    d_parts = []
                    if domain:
                        d_parts.append(f"domain={domain}")
                    if intent:
                        d_parts.append(f"intent={intent}")
                    expert_lines.append(f"- Discourse: {', '.join(d_parts)}")

            decoder_out = ctx.get_expert_output(ExpertType.DECODER) or {}
            dec_conf = str(decoder_out.get("overall_confidence") or "").strip()
            dec_title = ""
            if isinstance(decoder_out.get("overall_best_match"), dict):
                dec_title = str((decoder_out.get("overall_best_match") or {}).get("title") or "").strip()
            if not dec_title:
                for term in decoder_out.get("decoded_terms", []):
                    bm = term.get("best_match") or {}
                    if bm.get("title"):
                        dec_title = str(bm.get("title")).strip()
                        break
            dec_parts = []
            if dec_title:
                dec_parts.append(f"title={dec_title}")
            if dec_conf:
                dec_parts.append(f"confidence={dec_conf}")
            if dec_parts:
                expert_lines.append(f"- Decoder: {', '.join(dec_parts)}")

            if rejection_reason:
                expert_lines.append(
                    f"- Verifier: {_brief(rejection_reason, width=220)}"
                )
            elif verifier_reason:
                expert_lines.append(
                    f"- Verifier: {_brief(verifier_reason, width=220)}"
                )
            if grounding_issue:
                expert_lines.append(
                    f"- Verifier grounding: {_brief(grounding_issue, width=180)}"
                )

            arbiter_out = ctx.get_expert_output(ExpertType.ARBITER) or {}
            consensus = arbiter_out.get("expert_consensus") or {}
            arb_parts = []
            if final_decision.get("discussion_type"):
                arb_parts.append(f"discussion_type={final_decision.get('discussion_type')}")
            if isinstance(consensus, dict) and "unanimous" in consensus:
                arb_parts.append(f"unanimous={consensus.get('unanimous')}")
            if arb_parts:
                expert_lines.append(f"- Arbiter: {', '.join(arb_parts)}")

        if expert_lines:
            lines.append("")
            lines.append("[전문가별 판단]")
            lines.extend(expert_lines)

        # 점수 기반 핵심 증거 (중복 제거)
        selected_evidence: List[Dict[str, Any]] = []
        seen_keys: List[str] = []
        display_items = reviewed_items
        if not self.reason_full_mode:
            display_items = reviewed_items[:6]
        else:
            display_items = reviewed_items[: self.reason_full_candidate_cap]

        for item in display_items:
            txt = self._clean_reason_text(item.get("text", ""))
            key = self._normalize_match_text(txt)[:220]
            if not key:
                continue
            duplicate = any(key == sk or key in sk or sk in key for sk in seen_keys)
            if duplicate:
                continue
            seen_keys.append(key)
            selected_evidence.append(item)

        lines.append("")
        lines.append("[핵심 증거]")
        for idx, item in enumerate(selected_evidence, start=1):
            sources = " + ".join(item.get("sources", []))
            text = self._clip_reason_text(item.get("text", ""), width=200)
            lines.append(f"{idx}. [{float(item.get('score', 0.0)):.2f}] {sources}: {text}")

        if llm_merged_reason or llm_note or llm_conf:
            lines.append("")
            lines.append("[LLM 검토]")
            if llm_conf:
                lines.append(f"- confidence: {llm_conf}")
            if llm_note:
                lines.append(f"- note: {_brief(llm_note, width=220)}")
            if llm_merged_reason:
                lines.append(f"- merged: {_brief(llm_merged_reason, width=240)}")

        # 최종 종합
        summary_text = llm_merged_reason
        if not summary_text:
            summary_snippets: List[str] = []
            for item in selected_evidence[:3]:
                if self.reason_full_mode:
                    snippet = self._clean_reason_text(item.get("text", ""))
                else:
                    snippet = _brief(item.get("text", ""), width=90)
                if snippet:
                    summary_snippets.append(snippet)
            summary_text = " | ".join(summary_snippets)
        if summary_text:
            lines.append("")
            lines.append("[최종 종합]")
            lines.append(f"- {summary_text}")

        return "\n".join(lines)

    def _validate_heretic_url(
        self,
        url: str,
        ctx,
        identified_title: Optional[str] = None,
    ) -> Optional[str]:
        """
        Validate `heretic_url` with stronger evidence:
        1) URL must point to a novel platform domain.
        2) Search snippet evidence must be related to selected title/author.
        3) If fetched page exists, use structured/title/author/text evidence for scoring.

        Returns:
            - best validated URL
            - None when evidence is weak or conflicting
        """
        if not url:
            return None

        search_results = getattr(ctx, "search_results", None) or []
        selected_title = identified_title or self._get_identified_title(ctx)
        selected_author = self._get_identified_author(ctx)

        candidate_urls: List[str] = [url]
        candidate_urls.extend(self._collect_expert_urls(ctx))
        if selected_title:
            matched_url = self._find_title_matched_official_url(selected_title, search_results)
            if matched_url:
                candidate_urls.append(matched_url)

        # URL 정규화 기준 dedupe
        deduped_candidates: List[str] = []
        seen_norms: set[str] = set()
        for cand in candidate_urls:
            cand_norm = self._normalize_url_for_match(cand)
            if not cand_norm or cand_norm in seen_norms:
                continue
            seen_norms.add(cand_norm)
            deduped_candidates.append(cand)

        evaluations: List[Dict[str, Any]] = []
        for cand in deduped_candidates:
            ev = self._evaluate_heretic_url_candidate(
                cand,
                ctx=ctx,
                search_results=search_results,
                identified_title=selected_title,
                identified_author=selected_author,
            )
            evaluations.append(ev)

        valid_evals = [ev for ev in evaluations if ev.get("valid")]
        if not valid_evals:
            # 디버깅용: 왜 전부 기각됐는지 상위 2개만 로그
            for ev in evaluations[:2]:
                print(
                    f"[{_ts()}] ⚠️ heretic_url 후보 기각: url='{ev.get('url')}', "
                    f"score={ev.get('score')}, reason={ev.get('invalid_reason')}",
                    file=sys.stderr,
                )
            return None

        valid_evals.sort(
            key=lambda ev: (
                float(ev.get("score", 0.0)),
                1 if ev.get("title_evidence") else 0,
                1 if ev.get("author_evidence") else 0,
            ),
            reverse=True,
        )
        best = valid_evals[0]

        # 입력 URL도 유효하고 점수가 비슷하면 입력값 유지 (불필요한 URL churn 방지)
        current_norm = self._normalize_url_for_match(url)
        current = next(
            (
                ev
                for ev in valid_evals
                if self._normalize_url_for_match(ev.get("url", "")) == current_norm
            ),
            None,
        )
        if current and float(current.get("score", 0.0)) + 0.75 >= float(best.get("score", 0.0)):
            return url

        if best.get("url") != url:
            print(
                f"[{_ts()}] 🔁 heretic_url 교체: '{url}' → '{best.get('url')}' "
                f"(score {current.get('score') if current else 'N/A'} → {best.get('score')}, "
                f"title_ev={best.get('title_evidence')}, author_ev={best.get('author_evidence')})",
                file=sys.stderr,
            )
        return best.get("url")

    @staticmethod
    def _url_title_mismatch(url: str, identified_title: str) -> bool:
        """URL 경로에 포함된 작품명이 identified_title과 다른지 확인.
        
        나무위키 등 위키 URL은 경로에 작품명이 인코딩되어 있으므로,
        URL을 디코딩하여 identified_title과 비교한다.
        
        예: URL = namu.wiki/w/즉사기 들고 게임 속으로
            title = 즉사기 들고 무림에 떨어지다
            → 경로의 "즉사기 들고 게임 속으로" ≠ title → mismatch!
        """
        import urllib.parse as _urlparse
        try:
            parsed = _urlparse.urlparse(url)
            path_decoded = _urlparse.unquote(parsed.path)
        except Exception:
            return False
        
        # 나무위키: /w/작품명
        if "namu.wiki" in url:
            # /w/ 뒤가 작품명
            if "/w/" in path_decoded:
                url_title = path_decoded.split("/w/", 1)[1].strip()
                url_title_norm = url_title.replace(" ", "")
                id_title_norm = identified_title.replace(" ", "")
                # 완전히 같으면 OK
                if url_title_norm == id_title_norm:
                    return False
                # 한쪽이 다른쪽을 포함하면 OK (하위문서 등)
                if id_title_norm in url_title_norm:
                    return False
                # 3글자 이상 공유 접두사 + 나머지가 다르면 mismatch
                # ("즉사기 들고 게임 속으로" vs "즉사기 들고 무림에 떨어지다")
                common_prefix_len = 0
                for a, b in zip(url_title_norm, id_title_norm):
                    if a == b:
                        common_prefix_len += 1
                    else:
                        break
                if common_prefix_len >= 3 and url_title_norm != id_title_norm:
                    return True  # 접두사는 같지만 나머지가 다름 → mismatch
                # 접두사 공유 없으면 → 전혀 다른 작품이므로 mismatch
                if common_prefix_len < 2:
                    return True
        
        return False

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

    def _has_official_title_evidence(self, ctx, title: Optional[str]) -> bool:
        """
        특정 제목이 공식 소설 플랫폼 증거로 확인되는지 판별.
        - 검색 결과의 공식 플랫폼 URL + 제목 매칭
        - fetch된 공식 플랫폼 페이지의 제목/본문 매칭
        """
        if not title:
            return False

        search_results = getattr(ctx, "search_results", None) or []
        title_norm = self._normalize_match_text(title)
        if not title_norm:
            return False

        for sr in search_results:
            if not isinstance(sr, dict):
                continue
            sr_url = str(sr.get("url") or "")
            if not self._is_novel_platform_url(sr_url):
                continue
            sr_text = f"{sr.get('title', '')} {sr.get('content', '')}"
            if self._text_matches_phrase(sr_text, title):
                return True

        fetched = getattr(ctx, "fetched_page_info", None) or []
        for fe in fetched:
            if not isinstance(fe, dict):
                continue
            fe_url = str(fe.get("url") or "")
            if not self._is_novel_platform_url(fe_url):
                continue
            structured = fe.get("structured_info") or {}
            if not isinstance(structured, dict):
                structured = {}
            candidates = [
                structured.get("title"),
                structured.get("page_title"),
                fe.get("title"),
                fe.get("page_title"),
            ]
            for cand in candidates:
                if cand and self._text_matches_phrase(str(cand), title):
                    return True
            preview = f"{fe.get('text_preview', '')} {structured.get('text_preview', '')}"
            if self._text_matches_phrase(preview, title):
                return True

        return False

    def _detect_multi_work_order_context(self, ctx, vf_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        다작/순서 질문 맥락 감지.
        - 순서 질문 키워드 + 화살표 체인 + 다수 작품 후보가 함께 나타나면
          단일 official_title 강제 고정을 피한다.
        """
        post_data = getattr(ctx, "post_data", None) or {}
        chunks: List[str] = [str(post_data.get("title") or "")]
        for block in post_data.get("content_blocks", []) or []:
            if isinstance(block, dict):
                chunks.append(str(block.get("text") or ""))
            elif isinstance(block, str):
                chunks.append(block)
        chunks.extend([c for c in (getattr(ctx, "comments", None) or []) if isinstance(c, str)])
        raw_text = " ".join(chunks)
        norm_text = self._normalize_match_text(raw_text)

        order_keywords = (
            "순서",
            "시간순서",
            "뭐부터",
            "먼저",
            "나머지",
            "다본",
            "다본사람",
            "정주행",
            "작품들",
        )
        has_order_keyword = any(kw in norm_text for kw in order_keywords)
        has_arrow_chain = ("->" in raw_text) or ("→" in raw_text)

        decoder_out = ctx.get_expert_output(ExpertType.DECODER) or {}
        decoded_title_norms: set[str] = set()
        for dt in decoder_out.get("decoded_terms", []) or []:
            if not isinstance(dt, dict):
                continue
            bm = dt.get("best_match") or {}
            title = bm.get("title")
            conf = str(bm.get("confidence") or "").lower()
            if not title or conf in ("", "none"):
                continue
            t_norm = self._normalize_match_text(title)
            if t_norm:
                decoded_title_norms.add(t_norm)

        decoded_title_count = len(decoded_title_norms)

        vf_author_info = vf_result.get("author_info") or {}
        detected_author = ""
        if isinstance(vf_author_info, dict):
            detected_author = str(vf_author_info.get("detected_author") or "").strip()
        has_author_focus = bool(detected_author) or any(
            kw in norm_text for kw in ("작가", "글다본", "유니버스", "작품순서")
        )

        is_multi_work_order = (
            (has_order_keyword or has_arrow_chain)
            and (decoded_title_count >= 2 or has_author_focus)
        )
        return {
            "is_multi_work_order": is_multi_work_order,
            "has_order_keyword": has_order_keyword,
            "has_arrow_chain": has_arrow_chain,
            "decoded_title_count": decoded_title_count,
            "has_author_focus": has_author_focus,
        }

    def _title_mentioned_in_post_context(self, ctx, title: Optional[str]) -> bool:
        """게시글 제목/본문/댓글에 title이 실제로 등장하는지 확인."""
        if not title:
            return False

        post_data = getattr(ctx, "post_data", None) or {}
        chunks: List[str] = [str(post_data.get("title") or "")]
        for block in post_data.get("content_blocks", []) or []:
            if isinstance(block, dict):
                chunks.append(str(block.get("text") or ""))
            elif isinstance(block, str):
                chunks.append(block)
        chunks.extend([c for c in (getattr(ctx, "comments", None) or []) if isinstance(c, str)])

        raw_text = " ".join(chunks)
        if not raw_text.strip():
            return False
        return self._text_matches_phrase(raw_text, title)

    def _compute_title_commitment(
        self,
        ctx,
        title: Optional[str],
        vf_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        최종 title 확정 신뢰도(Commitment) 계산.
        - 프롬프트를 바꾸지 않고 코드 레벨에서 다중 근거 결속도를 점수화한다.
        """
        if not title:
            return {
                "score": 0,
                "official_evidence": False,
                "title_in_context": False,
                "bucket_score": 0,
                "strong_anchor": False,
                "decoder_strong": False,
                "verifier_positive": False,
                "weak_anchor_penalty": False,
            }

        vf_result = vf_result or {}
        grounding = vf_result.get("grounding_check") or {}
        anchor_found = str(grounding.get("anchor_found") or "none").strip().lower()
        strong_anchor = anchor_found in {
            "title_mention",
            "author_mention",
            "character_mention",
            "character_title_link",
            "plot_mention",
        }
        weak_anchor_penalty = anchor_found in {"none", "search_only", ""}

        official_evidence = self._has_official_title_evidence(ctx, title)
        title_in_context = self._title_mentioned_in_post_context(ctx, title)
        bucket = self._get_candidate_evidence_bucket(ctx, title)
        bucket_score = self._score_candidate_evidence_bucket(bucket)

        decoder_out = ctx.get_expert_output(ExpertType.DECODER) or {}
        decoder_strong = False
        title_norm = self._normalize_match_text(title)
        for dt in decoder_out.get("decoded_terms", []) or []:
            if not isinstance(dt, dict) or dt.get("is_author_name"):
                continue
            bm = dt.get("best_match") or {}
            gr = dt.get("grounding") or {}
            bm_title = bm.get("title")
            if not bm_title:
                continue
            if self._normalize_match_text(bm_title) != title_norm:
                continue
            bm_conf = str(bm.get("confidence") or "").lower()
            anchor = str(gr.get("anchor_type") or "").lower()
            if bm_conf in {"high", "max"} and anchor in {"title_mention", "character_title_link", "plot_mention"}:
                decoder_strong = True
                break

        vf_conf = str(
            vf_result.get("final_confidence")
            or (vf_result.get("novel_identity") or {}).get("confidence")
            or ""
        ).lower()
        verifier_positive = bool(vf_result.get("is_relevant")) and vf_conf in {"high", "max", "medium"}

        score = 0
        if official_evidence:
            score += 3
        if title_in_context:
            score += 2
        if strong_anchor:
            score += 2
        if decoder_strong:
            score += 2
        if verifier_positive:
            score += 1
        if bucket_score >= 4:
            score += 2
        elif bucket_score >= 2:
            score += 1
        if weak_anchor_penalty and not title_in_context and not official_evidence:
            score -= 2

        return {
            "score": score,
            "official_evidence": official_evidence,
            "title_in_context": title_in_context,
            "bucket_score": bucket_score,
            "strong_anchor": strong_anchor,
            "decoder_strong": decoder_strong,
            "verifier_positive": verifier_positive,
            "weak_anchor_penalty": weak_anchor_penalty,
        }

    @staticmethod
    def _is_title_commitment_strong(commitment: Dict[str, Any]) -> bool:
        if not isinstance(commitment, dict):
            return False
        score = int(commitment.get("score", 0))
        if score < 6:
            return False
        if not (commitment.get("official_evidence") or commitment.get("title_in_context")):
            return False
        return bool(
            int(commitment.get("bucket_score", 0)) >= 2
            or commitment.get("strong_anchor")
            or commitment.get("decoder_strong")
        )

    @staticmethod
    def _is_title_commitment_medium(commitment: Dict[str, Any]) -> bool:
        if not isinstance(commitment, dict):
            return False
        score = int(commitment.get("score", 0))
        if score < 4:
            return False
        return bool(
            commitment.get("official_evidence")
            or commitment.get("title_in_context")
            or int(commitment.get("bucket_score", 0)) >= 3
        )

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

    @staticmethod
    def _normalize_url_for_match(url: str) -> str:
        return (url or "").split("?")[0].rstrip("/").lower()

    @staticmethod
    def _normalize_match_text(text: str) -> str:
        import re

        return re.sub(r"[^0-9a-zA-Z가-힣]", "", str(text or "").lower())

    @staticmethod
    def _normalize_author_candidate(raw: Any) -> str:
        """Normalize author token by trimming common trailing particles/suffixes.

        Example: "유진성의" -> "유진성"
        """
        import re

        if raw is None:
            return ""
        text = str(raw).strip()
        if not text:
            return ""

        # remove wrapping punctuation/quotes
        text = re.sub(r"^[\"'`“”‘’\(\[\{]+|[\"'`“”‘’\)\]\}]+$", "", text).strip()
        if not text:
            return ""

        # remove trailing role suffix first (e.g. "유진성 작가", "유진성님")
        text = re.sub(r"(?:\s*(?:작가|님|씨))$", "", text).strip()

        # remove a single trailing postposition only when token is long enough
        # to reduce false trims on short names.
        if len(text) >= 4:
            text = re.sub(r"(께서|에게|에서|으로|로)$", "", text).strip()
            text = re.sub(r"(의|은|는|이|가|을|를|와|과|도|만)$", "", text).strip()

        return text

    @staticmethod
    def _is_novel_platform_url(url: str) -> bool:
        if not url:
            return False
        url_l = url.lower()
        return any(site in url_l for site in NOVEL_SITES)

    @staticmethod
    def _is_novel_detail_url(url: str) -> bool:
        """플랫폼 내에서도 '작품 상세' 페이지인지 판별한다.

        검색/작가 목록/랭킹/장르 목록 URL은 작품 heretic_url 후보에서 제외한다.
        """
        if not url:
            return False
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            host = (parsed.netloc or "").lower()
            path = (parsed.path or "").lower()
            query = (parsed.query or "").lower()
        except Exception:
            return False

        # 명시적 상세 패턴
        import re
        if "novelpia.com" in host and re.search(r"/novel/\d+", path):
            return True
        if "series.naver.com" in host and "/novel/detail.series" in path and "productno=" in query:
            return True
        if "ridibooks.com" in host and re.search(r"^/books/\d+", path):
            return True
        if "munpia.com" in host and (("action=view" in query and "id=" in query) or re.search(r"/novel/\d+", path)):
            return True
        if "joara.com" in host and ("/book/" in path or "book_no=" in query or "bookcode=" in query):
            return True
        if ("kakao.page" in host or "page.kakao.com" in host) and "/content/" in path:
            return True

        # 검색/목록/작가 페이지 패턴
        listing_path_tokens = (
            "/search",
            "/author",
            "/authors",
            "/writer",
            "/writers",
            "/best",
            "/ranking",
            "/rank",
            "/genre",
            "/genres",
            "/tag",
            "/tags",
            "/category",
            "/categories",
            "/list",
            "/lists",
        )
        if any(tok in path for tok in listing_path_tokens):
            return False

        listing_query_tokens = (
            "search=",
            "q=",
            "query=",
            "keyword=",
            "writer=",
            "author=",
            "tag=",
            "genre=",
            "sort=",
            "order=",
            "page=",
            "search_type=",
            "search_val=",
        )
        if any(tok in query for tok in listing_query_tokens):
            return False

        # 보수적 fallback: 플랫폼 URL이면서 명백한 목록 패턴이 아니면 상세로 간주
        return bool(path and path != "/")

    @staticmethod
    def _looks_like_listing_title(title: Any) -> bool:
        if not isinstance(title, str):
            return False
        raw = title.strip()
        if not raw:
            return False
        low = raw.lower()
        markers = (
            "작가 -",
            "- 작가",
            "작가 페이지",
            "검색",
            "랭킹",
            "순위",
            "best",
            "genre",
            "category",
            "tag",
            "웹소설로 꿈꾸는 세상",
            "웹소설의 유토피아",
        )
        return any(m in low for m in markers)

    def _text_matches_phrase(self, text: str, phrase: str) -> bool:
        if not text or not phrase:
            return False

        text_l = str(text).lower()
        phrase_l = str(phrase).lower()
        if phrase_l in text_l:
            return True

        norm_text = self._normalize_match_text(text_l)
        norm_phrase = self._normalize_match_text(phrase_l)
        if norm_phrase and norm_phrase in norm_text:
            return True

        words = [w for w in phrase_l.split() if len(w) >= 2]
        if not words:
            return False
        matched = sum(1 for w in words if w in text_l)
        return matched >= max(1, len(words) // 2)

    def _text_matches_title_strict(self, text: str, title: str) -> bool:
        """Title matching stricter than `_text_matches_phrase`.

        URL 후보 검증 단계에서는 부분 겹침(예: "즉사기 들고")만으로 다른 작품 URL이
        통과하면 안 되므로, 제목 토큰의 높은 일치율을 요구한다.
        """
        if not text or not title:
            return False

        text_l = str(text).lower()
        title_l = str(title).lower()

        # 완전 부분일치/정규화 부분일치는 그대로 허용
        if title_l in text_l:
            return True

        norm_text = self._normalize_match_text(text_l)
        norm_title = self._normalize_match_text(title_l)
        if norm_title and norm_title in norm_text:
            return True

        import re

        title_words = [w for w in re.split(r"\s+", title_l) if len(w) >= 2]
        if not title_words:
            return False

        matched = sum(1 for w in title_words if w in text_l)
        ratio = matched / max(1, len(title_words))

        # 2단어 제목은 사실상 전부 일치해야 오인 가능성이 낮다.
        if len(title_words) <= 2:
            return matched == len(title_words)

        # 3단어 이상 제목은 75% 이상 토큰 일치 필요.
        return ratio >= 0.75

    def _get_identified_author(self, ctx) -> Optional[str]:
        # 1) Verifier author_info
        verifier_out = ctx.get_expert_output(ExpertType.VERIFIER) or {}
        verification = verifier_out.get("verification_result") or {}
        author_info = verification.get("author_info") or {}
        if isinstance(author_info, dict):
            detected = self._normalize_author_candidate(author_info.get("detected_author"))
            if detected:
                return detected

        # 2) Arbiter metadata
        arbiter_out = ctx.get_expert_output(ExpertType.ARBITER) or {}
        metadata = arbiter_out.get("metadata_synthesis") or {}
        if isinstance(metadata, dict):
            detected = self._normalize_author_candidate(metadata.get("detected_author"))
            if detected:
                return detected

        # 3) Decoder is_author_name
        decoder_out = ctx.get_expert_output(ExpertType.DECODER) or {}
        for term in decoder_out.get("decoded_terms", []):
            if not isinstance(term, dict) or not term.get("is_author_name"):
                continue
            author_info = term.get("author_info") or {}
            if isinstance(author_info, dict):
                detected = self._normalize_author_candidate(
                    author_info.get("name") or author_info.get("author_name")
                )
                if detected:
                    return detected
            original = self._normalize_author_candidate(term.get("original"))
            if original:
                return original

        # 4) snippet hints
        snippet_hints = getattr(ctx, "snippet_hints", None) or {}
        for hint in snippet_hints.get("author_hints", []) or []:
            if not isinstance(hint, dict):
                continue
            detected = self._normalize_author_candidate(hint.get("name"))
            if detected:
                return detected
        return None

    def _get_fetched_entries_for_url(self, ctx, url: str) -> List[Dict[str, Any]]:
        fetched = getattr(ctx, "fetched_page_info", None) or []
        target_norm = self._normalize_url_for_match(url)
        out: List[Dict[str, Any]] = []
        for item in fetched:
            if not isinstance(item, dict):
                continue
            item_url = item.get("url") or ""
            if not item_url:
                continue
            item_norm = self._normalize_url_for_match(item_url)
            if (
                item_norm == target_norm
                or (item_norm and target_norm and (item_norm in target_norm or target_norm in item_norm))
            ):
                out.append(item)
        return out

    def _normalize_title_candidate(self, raw: Any) -> str:
        import re

        if not isinstance(raw, str):
            return ""
        value = raw.strip()
        if not value:
            return ""

        value = re.sub(r"\s*\(r\d+\s*판\)\s*$", "", value, flags=re.IGNORECASE).strip()
        value = re.sub(r"^\[[^\]]{1,16}\]\s*", "", value).strip()

        lower_noise_tokens = (
            "만화",
            "웹툰",
            "웹소설",
            "e북",
            "ebook",
            "마이너 갤러리",
            "나무위키",
            "네이버 시리즈",
            "리디",
            "novelpia -",
            "웹소설로 꿈꾸는 세상",
            "플러스",
            "팬아트",
        )

        def _is_noise_chunk(chunk: str) -> bool:
            cl = chunk.lower()
            return any(tok in cl for tok in lower_noise_tokens)

        if " - " in value:
            parts = [p.strip() for p in value.split(" - ") if p.strip()]
            clean_parts = [p for p in parts if len(p) >= 2 and not _is_noise_chunk(p)]
            if clean_parts:
                value = max(clean_parts, key=len)
            elif parts:
                value = parts[0]
        elif " | " in value:
            parts = [p.strip() for p in value.split(" | ") if p.strip()]
            clean_parts = [p for p in parts if len(p) >= 2 and not _is_noise_chunk(p)]
            if clean_parts:
                value = max(clean_parts, key=len)
            elif parts:
                value = parts[0]

        value = re.sub(
            r"\s*-\s*(?:만화|웹툰|웹소설)\s*(?:e북|ebook)?\s*$",
            "",
            value,
            flags=re.IGNORECASE,
        ).strip()
        value = re.sub(r"\s{2,}", " ", value).strip()
        return value

    def _is_platform_branding_title(self, title: Any) -> bool:
        """플랫폼 슬로건/브랜드 문구인지 판별한다."""
        if not isinstance(title, str):
            return False
        raw = title.strip()
        if not raw:
            return False

        import re

        norm = re.sub(r"[^\w가-힣]", "", raw).lower()
        branding_norms = {
            "웹소설로꿈꾸는세상",
            "웹소설의유토피아",
            "노벨피아",
            "문피아",
            "카카오페이지",
            "네이버시리즈",
            "리디",
        }
        return norm in branding_norms

    def _extract_title_from_validated_url(self, ctx, url: str) -> Optional[str]:
        fetched_entries = self._get_fetched_entries_for_url(ctx, url)
        if not fetched_entries:
            fetched_one = self._fetch_and_attach_page_info(ctx, url)
            if fetched_one:
                fetched_entries = [fetched_one]

        candidates: List[str] = []
        for fe in fetched_entries:
            if not isinstance(fe, dict):
                continue
            structured = fe.get("structured_info") or {}
            if not isinstance(structured, dict):
                structured = {}
            for cand in (
                structured.get("title"),
                structured.get("page_title"),
                fe.get("title"),
                fe.get("page_title"),
            ):
                if self._is_platform_branding_title(cand) or self._looks_like_listing_title(cand):
                    continue
                norm = self._normalize_title_candidate(cand)
                if norm and len(norm) >= 2 and (not self._is_platform_branding_title(norm)):
                    candidates.append(norm)

        if not candidates:
            return None
        # 노이즈 제거 후 가장 긴 제목 우선
        return max(candidates, key=len)

    def _apply_known_abbreviation_title_guard(
        self,
        ctx,
        official_title: str,
        heretic_url: Optional[str],
    ) -> tuple[str, Optional[str]]:
        """검증된 약칭이 제목에 있으면 정식 제목으로 고정한다."""
        import re

        post_title = str((getattr(ctx, "post_data", {}) or {}).get("title", "") or "")
        post_norm = re.sub(r"[^\w가-힣]", "", post_title).lower()
        if not post_norm:
            return official_title, heretic_url

        cur_norm = re.sub(r"[^\w가-힣]", "", str(official_title or "")).lower()
        search_results = getattr(ctx, "search_results", []) or []

        for abbr, full_title in KNOWN_TITLE_ABBREVIATIONS.items():
            abbr_norm = re.sub(r"[^\w가-힣]", "", abbr).lower()
            full_norm = re.sub(r"[^\w가-힣]", "", full_title).lower()
            if not abbr_norm or abbr_norm not in post_norm:
                continue

            has_support = False

            # 1) suspected_titles에 정식 제목이 있으면 즉시 신뢰
            for st in getattr(ctx, "suspected_titles", []) or []:
                if not isinstance(st, dict):
                    continue
                st_title = str(st.get("title") or "")
                st_norm = re.sub(r"[^\w가-힣]", "", st_title).lower()
                if st_norm == full_norm:
                    has_support = True
                    break

            # 2) Decoder 결과에 정식 제목이 있으면 신뢰
            if not has_support:
                dec_out = ctx.get_expert_output(ExpertType.DECODER) or {}
                ov = dec_out.get("overall_best_match") or {}
                if isinstance(ov, dict):
                    ov_norm = re.sub(r"[^\w가-힣]", "", str(ov.get("title") or "")).lower()
                    if ov_norm == full_norm:
                        has_support = True
                if not has_support:
                    for dt in dec_out.get("decoded_terms", []) or []:
                        if not isinstance(dt, dict):
                            continue
                        bm = dt.get("best_match") or {}
                        bm_norm = re.sub(r"[^\w가-힣]", "", str(bm.get("title") or "")).lower()
                        if bm_norm == full_norm:
                            has_support = True
                            break

            # 3) 캐릭터-작품 검증 링크에 정식 제목이 있으면 신뢰
            if not has_support:
                for link in getattr(ctx, "verified_character_work_links", []) or []:
                    if not isinstance(link, dict):
                        continue
                    lk_norm = re.sub(r"[^\w가-힣]", "", str(link.get("title") or "")).lower()
                    if lk_norm == full_norm:
                        has_support = True
                        break

            # 4) 공식 플랫폼 검색 결과에 정식 제목이 있으면 신뢰
            matched_url = self._find_title_matched_official_url(full_title, search_results)
            if matched_url:
                has_support = True

            if not has_support:
                continue

            if cur_norm != full_norm:
                old = official_title
                official_title = full_title
                print(
                    f"[{_ts()}] 🧩 약칭-제목 가드: '{abbr}' 감지 + 증거 확인 "
                    f"→ '{old}' -> '{official_title}'",
                    file=sys.stderr,
                )

            # URL이 없거나 기존 URL이 약하면 정식 제목 기반 URL 보강
            if matched_url:
                heretic_url = self._validate_heretic_url(
                    matched_url,
                    ctx,
                    identified_title=official_title,
                )
            return official_title, heretic_url

        return official_title, heretic_url

    def _fetch_and_attach_page_info(self, ctx, url: str) -> Optional[Dict[str, Any]]:
        """
        fetched_page_info에 없는 URL을 1회 직접 fetch하여 컨텍스트에 부착한다.
        heretic_url 후보 검증의 정확도를 높이기 위한 보강 단계.
        """
        if not self.enable_heretic_live_fetch:
            return None
        if not url or (not self._is_novel_platform_url(url)):
            return None

        norm_url = self._normalize_url_for_match(url)
        if norm_url in self._heretic_fetch_cache:
            return self._heretic_fetch_cache.get(norm_url)

        raw = self._fetch(url)
        if not isinstance(raw, dict):
            self._heretic_fetch_cache[norm_url] = None
            return None

        structured = raw.get("structured_info") or {}
        if not isinstance(structured, dict):
            structured = {}
        text_preview = str(raw.get("text") or raw.get("text_preview") or "")[:500]
        entry = {
            "url": url,
            "structured_info": structured,
            "text_preview": text_preview,
        }

        if not hasattr(ctx, "fetched_page_info") or not isinstance(getattr(ctx, "fetched_page_info"), list):
            ctx.fetched_page_info = []

        # 중복 추가 방지
        already = False
        for ex in ctx.fetched_page_info:
            if not isinstance(ex, dict):
                continue
            ex_norm = self._normalize_url_for_match(str(ex.get("url") or ""))
            if ex_norm and (ex_norm == norm_url or ex_norm in norm_url or norm_url in ex_norm):
                already = True
                break
        if not already:
            ctx.fetched_page_info.append(entry)

        self._heretic_fetch_cache[norm_url] = entry
        print(
            f"[{_ts()}] 🔎 heretic_url 직접 fetch 보강: '{url}' "
            f"(title={structured.get('page_title') or structured.get('title') or '?'}, "
            f"author={structured.get('author') or '?'})",
            file=sys.stderr,
        )
        return entry

    def _author_supported_in_context(self, author: str, ctx) -> bool:
        author_norm = self._normalize_match_text(author)
        if not author_norm:
            return False

        snippet_hints = getattr(ctx, "snippet_hints", None) or {}
        for hint in snippet_hints.get("author_hints", []) or []:
            if not isinstance(hint, dict):
                continue
            hint_name = hint.get("name") or ""
            if self._normalize_match_text(hint_name) == author_norm:
                return True

        post_data = getattr(ctx, "post_data", None) or {}
        chunks: List[str] = [post_data.get("title", "")]
        for block in post_data.get("content_blocks", []) or []:
            if isinstance(block, dict):
                chunks.append(str(block.get("text") or ""))
            elif isinstance(block, str):
                chunks.append(block)
        chunks.extend([c for c in (getattr(ctx, "comments", None) or []) if isinstance(c, str)])
        full_text = " ".join(chunks)
        return author_norm in self._normalize_match_text(full_text)

    def _evaluate_heretic_url_candidate(
        self,
        url: str,
        ctx,
        search_results: List[Dict[str, Any]],
        identified_title: Optional[str],
        identified_author: Optional[str],
    ) -> Dict[str, Any]:
        score = 0.0
        title_evidence = False
        author_evidence = False
        invalid_reason = ""

        if not url or not isinstance(url, str) or not url.startswith("http"):
            return {
                "url": url,
                "score": score,
                "valid": False,
                "title_evidence": False,
                "author_evidence": False,
                "invalid_reason": "invalid_url",
            }

        # heretic_url은 소설 플랫폼 "작품 상세 링크"만 허용 (위키/커뮤니티/검색/작가목록 제외)
        if not self._is_novel_platform_url(url):
            return {
                "url": url,
                "score": score,
                "valid": False,
                "title_evidence": False,
                "author_evidence": False,
                "invalid_reason": "non_novel_platform_url",
            }
        if not self._is_novel_detail_url(url):
            return {
                "url": url,
                "score": score,
                "valid": False,
                "title_evidence": False,
                "author_evidence": False,
                "invalid_reason": "non_detail_platform_url",
            }

        if identified_title and self._url_title_mismatch(url, identified_title):
            return {
                "url": url,
                "score": score,
                "valid": False,
                "title_evidence": False,
                "author_evidence": False,
                "invalid_reason": "url_title_mismatch",
            }

        # Base score from source trust
        trust = 0.0
        if hasattr(ctx, "score_source_trust"):
            try:
                trust = float(ctx.score_source_trust(url))
            except Exception:
                trust = 0.0
        if trust >= 0.8:
            score += 2.0
        elif trust >= 0.4:
            score += 1.0

        target_norm = self._normalize_url_for_match(url)
        matched_search = []
        for sr in search_results:
            sr_url = sr.get("url") or ""
            sr_norm = self._normalize_url_for_match(sr_url)
            if not sr_norm:
                continue
            if sr_norm == target_norm or sr_norm in target_norm or target_norm in sr_norm:
                matched_search.append(sr)

        if matched_search:
            score += 1.0

        for sr in matched_search:
            sr_text = f"{sr.get('title', '')} {sr.get('content', '')}"
            if identified_title and self._text_matches_title_strict(sr_text, identified_title):
                title_evidence = True
                score += 2.0
            if identified_author and self._text_matches_phrase(sr_text, identified_author):
                author_evidence = True
                score += 1.5

        fetched_entries = self._get_fetched_entries_for_url(ctx, url)
        if not fetched_entries:
            fetched_one = self._fetch_and_attach_page_info(ctx, url)
            if fetched_one:
                fetched_entries = [fetched_one]
        if fetched_entries:
            score += 1.0

        for fe in fetched_entries:
            structured = fe.get("structured_info") or {}
            if not isinstance(structured, dict):
                structured = {}
            fetched_text = f"{fe.get('text_preview', '')} {structured.get('text_preview', '')}"

            for cand_title in (structured.get("title"), structured.get("page_title")):
                if not cand_title:
                    continue
                if identified_title and self._text_matches_title_strict(cand_title, identified_title):
                    title_evidence = True
                    score += 3.0
                    break

            if identified_title and self._text_matches_title_strict(fetched_text, identified_title):
                title_evidence = True
                score += 2.0

            fetched_author = str(structured.get("author") or "").strip()
            if fetched_author:
                if identified_author and self._text_matches_phrase(fetched_author, identified_author):
                    author_evidence = True
                    score += 3.0
                if self._author_supported_in_context(fetched_author, ctx):
                    author_evidence = True
                    score += 2.0

        # Validation rule:
        # - identified_title가 있으면 title evidence가 반드시 필요
        # - title이 없고 identified_author만 있으면 author evidence 필요
        # - 둘 다 없으면 충분한 점수(검색+fetch+trust) 필요
        valid = False
        if identified_title:
            valid = title_evidence and score >= 4.0
            if not valid:
                invalid_reason = "missing_title_evidence_or_low_score"
        elif identified_author:
            valid = author_evidence and score >= 4.0
            if not valid:
                invalid_reason = "missing_author_evidence_or_low_score"
        else:
            valid = score >= 5.0 and bool(matched_search or fetched_entries)
            if not valid:
                invalid_reason = "weak_evidence_no_title_or_author"

        return {
            "url": url,
            "score": score,
            "valid": valid,
            "title_evidence": title_evidence,
            "author_evidence": author_evidence,
            "invalid_reason": invalid_reason,
        }

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
        title = self._normalize_title_candidate(title) or title
        title_is_branding = self._is_platform_branding_title(title) or self._looks_like_listing_title(title)
        candidates: list[str] = []

        decoder_out = ctx.get_expert_output(ExpertType.DECODER) or {}
        for term in decoder_out.get("decoded_terms", []):
            if not isinstance(term, dict):
                continue
            best = term.get("best_match") or {}
            if best.get("title"):
                _c = self._normalize_title_candidate(best["title"])
                if _c and (not self._is_platform_branding_title(_c)) and (not self._looks_like_listing_title(_c)):
                    candidates.append(_c)
            for candidate in term.get("candidates", []):
                if not isinstance(candidate, dict):
                    continue
                candidate_title = candidate.get("official_novel_title")
                if candidate_title:
                    _c = self._normalize_title_candidate(candidate_title)
                    if _c and (not self._is_platform_branding_title(_c)) and (not self._looks_like_listing_title(_c)):
                        candidates.append(_c)

        for sr in getattr(ctx, "search_results", []) or []:
            sr_url = sr.get("url") or ""
            if not any(platform in sr_url for platform in OFFICIAL_PLATFORMS):
                continue
            sr_title = sr.get("title")
            if isinstance(sr_title, str) and sr_title.strip():
                _c = self._normalize_title_candidate(sr_title)
                if _c and (not self._is_platform_branding_title(_c)) and (not self._looks_like_listing_title(_c)):
                    candidates.append(_c)

        if not candidates:
            if title_is_branding:
                print(
                    f"[{_ts()}] final title branding/listing 제거: '{title}' -> ''",
                    file=sys.stderr,
                )
                return ""
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

        # 현재 title이 플랫폼 슬로건/리스트형이면 미확정으로 내려 오염 차단
        if title_is_branding:
            print(
                f"[{_ts()}] final title branding/listing 차단: '{title}'",
                file=sys.stderr,
            )
            return ""

        return title

    @staticmethod
    def _collect_notes(ctx) -> Optional[str]:
        """Decoder/Arbiter의 notes를 수집하여 줄바꿈 포맷팅된 문자열로 반환."""
        import re as _re_notes
        
        notes_parts: list[str] = []
        
        # 1순위: Arbiter notes
        arbiter_out = ctx.get_expert_output(ExpertType.ARBITER) or {}
        arb_notes = arbiter_out.get("notes")
        if arb_notes and isinstance(arb_notes, str) and arb_notes.strip():
            notes_parts.append(arb_notes.strip())
        
        # 2순위: Decoder notes (Arbiter가 없을 때만)
        if not notes_parts:
            decoder_out = ctx.get_expert_output(ExpertType.DECODER) or {}
            dec_notes = decoder_out.get("notes")
            if dec_notes and isinstance(dec_notes, str) and dec_notes.strip():
                notes_parts.append(dec_notes.strip())
        
        if not notes_parts:
            return None
        
        combined = "\n".join(notes_parts)
        
        # 번호 목록 줄바꿈 포맷팅: "1. ... 2. ... 3. ..." → 각각 줄바꿈
        # 이미 \n이 있으면 그대로, 없으면 "숫자. " 앞에 줄바꿈 삽입
        combined = _re_notes.sub(r'(?<!\n)\s*(\d+\.\s)', r'\n\1', combined)
        # 맨 앞 불필요한 줄바꿈 제거
        combined = combined.lstrip("\n")
        # Markdown bold (**...**) 제거 (JSON 출력용)
        combined = combined.replace("**", "")
        
        return combined if combined.strip() else None

    @staticmethod
    def _is_similar_title(title_a: str, title_b: str) -> bool:
        if abs(len(title_a) - len(title_b)) > 4:
            return False
        from difflib import SequenceMatcher
        return SequenceMatcher(None, title_a, title_b).ratio() >= 0.80

    def _collect_title_anchor_terms(self, ctx: "ConversationContext") -> List[str]:
        """Decoder/Gatekeeper에서 제목 앵커로 쓰인 원문 용어를 수집."""
        terms: List[str] = []

        decoder_out = ctx.get_expert_output(ExpertType.DECODER) or {}
        for dt in decoder_out.get("decoded_terms", []) or []:
            if not isinstance(dt, dict):
                continue
            grounding = dt.get("grounding") or {}
            anchor_type = str(grounding.get("anchor_type") or "").lower()
            if anchor_type not in {"title_mention", "character_title_link"}:
                continue
            original = str(dt.get("original") or "").strip()
            if len(original) >= 2:
                terms.append(original)

        gatekeeper_out = ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
        entities = gatekeeper_out.get("detected_entities") or {}
        for t in (entities.get("possible_titles") or [])[:8]:
            if not isinstance(t, str):
                continue
            t_clean = t.strip()
            if len(t_clean) >= 2:
                terms.append(t_clean)

        # 중복 제거 (정규화 기준)
        seen: set[str] = set()
        deduped: List[str] = []
        for t in terms:
            key = self._normalize_match_text(t)
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(t)
        return deduped

    @staticmethod
    def _extract_domain_keywords(text: str) -> set[str]:
        """작품 드리프트 판별용 도메인 키워드 추출."""
        if not text:
            return set()

        keyword_groups = (
            # 상호 배타적으로 자주 충돌하는 세계관 축
            ("무림", "게임", "헌터", "던전", "아카데미", "이세계"),
            # 호러/공간 축
            ("괴담", "호텔", "탈출기", "305호"),
            # 직업/역할 축
            ("상담사", "의사", "간호사"),
        )

        found: set[str] = set()
        no_space = str(text).replace(" ", "")
        for group in keyword_groups:
            for kw in group:
                if kw in no_space:
                    found.add(kw)
        return found

    @staticmethod
    def _confidence_rank_value(conf_val: Any) -> int:
        if isinstance(conf_val, (int, float)):
            v = float(conf_val)
            if v >= 0.7:
                return 3
            if v >= 0.5:
                return 2
            if v >= 0.3:
                return 1
            return 0
        if isinstance(conf_val, str):
            return {
                "max": 3,
                "high": 3,
                "medium": 2,
                "mid": 2,
                "low": 1,
                "none": 0,
            }.get(conf_val.strip().lower(), 0)
        return 0

    def _get_candidate_evidence_bucket(self, ctx: "ConversationContext", title: str) -> Dict[str, List[Any]]:
        """후보 제목의 evidence bucket 조회 (정규화/유사도 포함)."""
        store = getattr(ctx, "candidate_evidence", None) or {}
        if not isinstance(store, dict) or not store:
            return {"post_spans": [], "search_snippets": [], "official_urls": []}

        if title in store and isinstance(store[title], dict):
            bucket = store[title]
            return {
                "post_spans": list(bucket.get("post_spans") or []),
                "search_snippets": list(bucket.get("search_snippets") or []),
                "official_urls": list(bucket.get("official_urls") or []),
            }

        title_norm = self._normalize_match_text(title)
        best_key = ""
        best_score = 0.0
        for key in store.keys():
            if not isinstance(key, str):
                continue
            key_norm = self._normalize_match_text(key)
            if not key_norm:
                continue
            score = 0.0
            if key_norm == title_norm:
                score = 1.0
            elif title_norm and (title_norm in key_norm or key_norm in title_norm):
                score = 0.92
            elif self._is_similar_title(key, title):
                score = 0.85
            if score > best_score:
                best_score = score
                best_key = key

        if best_key and best_score >= 0.85 and isinstance(store.get(best_key), dict):
            bucket = store[best_key]
            return {
                "post_spans": list(bucket.get("post_spans") or []),
                "search_snippets": list(bucket.get("search_snippets") or []),
                "official_urls": list(bucket.get("official_urls") or []),
            }

        return {"post_spans": [], "search_snippets": [], "official_urls": []}

    @staticmethod
    def _score_candidate_evidence_bucket(bucket: Dict[str, List[Any]]) -> int:
        """후보 제목 버킷의 증거 강도 점수."""
        if not isinstance(bucket, dict):
            return 0

        def _uniq_count(items: Any) -> int:
            if not isinstance(items, list):
                return 0
            seen = set()
            for it in items:
                key = str(it)
                if key:
                    seen.add(key)
            return len(seen)

        post_cnt = _uniq_count(bucket.get("post_spans"))
        snippet_cnt = _uniq_count(bucket.get("search_snippets"))
        official_cnt = _uniq_count(bucket.get("official_urls"))

        # post 근거, 공식 URL 근거를 더 강하게 반영
        return (post_cnt * 2) + snippet_cnt + (official_cnt * 3)

    def _analyze_title_ambiguity(self, ctx: "ConversationContext", official_title: str) -> Dict[str, Any]:
        """
        현재 title 후보가 다중 경쟁 상태인지 분석.
        - suspected_titles + decoder best_match를 합쳐 후보 풀 구성
        - 유사 제목은 병합
        - 점수 차가 작고 강한 후보가 2개 이상이면 ambiguous
        """
        candidates: List[Dict[str, Any]] = []

        def _merge_candidate(title: str, confidence: Any, source: str) -> None:
            t = str(title or "").strip()
            if not t:
                return
            t_norm = self._normalize_match_text(t)
            if not t_norm:
                return
            rank = self._confidence_rank_value(confidence)
            if rank <= 0:
                return
            for c in candidates:
                c_norm = self._normalize_match_text(c.get("title", ""))
                if not c_norm:
                    continue
                if (
                    c_norm == t_norm
                    or t_norm in c_norm
                    or c_norm in t_norm
                    or self._is_similar_title(c.get("title", ""), t)
                ):
                    c["rank"] = max(int(c.get("rank", 0)), rank)
                    src = set(c.get("sources", []))
                    src.add(source)
                    c["sources"] = sorted(src)
                    # 더 정보량 많은 제목으로 교체
                    if len(t_norm) > len(c_norm):
                        c["title"] = t
                    return
            candidates.append({"title": t, "rank": rank, "sources": [source]})

        for st in getattr(ctx, "suspected_titles", []) or []:
            if not isinstance(st, dict):
                continue
            _merge_candidate(str(st.get("title") or ""), st.get("confidence"), "suspected")

        dec_out = ctx.get_expert_output(ExpertType.DECODER) or {}
        for dt in dec_out.get("decoded_terms", []) or []:
            if not isinstance(dt, dict):
                continue
            bm = dt.get("best_match") or {}
            _merge_candidate(str(bm.get("title") or ""), bm.get("confidence"), "decoder")

        if official_title:
            _merge_candidate(official_title, "medium", "official")

        scored: List[Dict[str, Any]] = []
        for c in candidates:
            t = str(c.get("title") or "").strip()
            if not t:
                continue
            rank = int(c.get("rank", 0))
            bucket_score = self._score_candidate_evidence_bucket(self._get_candidate_evidence_bucket(ctx, t))
            official_ev = self._has_official_title_evidence(ctx, t)
            score = (rank * 2) + min(bucket_score, 4) + (3 if official_ev else 0)
            scored.append(
                {
                    "title": t,
                    "rank": rank,
                    "score": score,
                    "official_evidence": official_ev,
                    "sources": list(c.get("sources", [])),
                }
            )

        scored.sort(key=lambda x: (x["score"], x["rank"], len(str(x["title"]))), reverse=True)
        if len(scored) < 2:
            return {
                "is_ambiguous": False,
                "candidate_count": len(scored),
                "top_gap": 99,
                "top_titles": [s.get("title") for s in scored[:2]],
            }

        top = scored[0]
        second = scored[1]
        top_gap = int(top.get("score", 0)) - int(second.get("score", 0))
        strong_cnt = sum(1 for s in scored if int(s.get("score", 0)) >= 4)

        ambiguous = (strong_cnt >= 2 and top_gap <= 2)
        if not ambiguous and len(scored) >= 3:
            third = scored[2]
            if (int(top.get("score", 0)) - int(third.get("score", 0))) <= 1:
                ambiguous = True

        # 상위 후보가 공식 근거가 있고 격차가 충분하면 모호로 보지 않음
        if top.get("official_evidence") and top_gap >= 2:
            ambiguous = False

        return {
            "is_ambiguous": bool(ambiguous),
            "candidate_count": len(scored),
            "top_gap": top_gap,
            "top_titles": [top.get("title"), second.get("title")],
            "scores": scored[:5],
        }

    def _has_title_abbrev_stability_signal(self, ctx: "ConversationContext", official_title: str) -> bool:
        """
        약어 기반 제목 식별의 안정 신호.
        - 제목에 직접 등장한 약어(original)
        - decoder의 title_mention + medium 이상
        - 검색 결과에서 해당 약어가 반복 등장
        """
        if not official_title:
            return False
        post_data = getattr(ctx, "post_data", None) or {}
        post_title_norm = self._normalize_match_text(str(post_data.get("title") or ""))
        if not post_title_norm:
            return False

        dec_out = ctx.get_expert_output(ExpertType.DECODER) or {}
        search_results = getattr(ctx, "search_results", None) or []

        for dt in dec_out.get("decoded_terms", []) or []:
            if not isinstance(dt, dict):
                continue
            orig = str(dt.get("original") or "").strip()
            if len(orig) < 2:
                continue
            orig_norm = self._normalize_match_text(orig)
            if not orig_norm or orig_norm not in post_title_norm:
                continue

            bm = dt.get("best_match") or {}
            bm_title = str(bm.get("title") or "").strip()
            if not bm_title:
                continue
            if not (
                self._text_matches_phrase(bm_title, official_title)
                or self._is_similar_title(bm_title, official_title)
            ):
                continue
            if self._confidence_rank_value(bm.get("confidence")) < 2:
                continue

            grounding = dt.get("grounding") or {}
            anchor = str(grounding.get("anchor_type") or "").lower()
            if anchor not in {"title_mention", "character_title_link"}:
                continue

            mention_cnt = 0
            for sr in search_results:
                if not isinstance(sr, dict):
                    continue
                sr_text = f"{sr.get('title', '')} {sr.get('content', '')}"
                if self._text_matches_phrase(sr_text, orig):
                    mention_cnt += 1
            if mention_cnt >= 2:
                return True

        return False

    def _pick_drift_replacement_title(
        self,
        ctx: "ConversationContext",
        *,
        anchor_keywords: set[str],
        exclude_title: str,
    ) -> Optional[str]:
        """앵커 키워드와 맞는 대체 제목 후보 선택."""
        if not anchor_keywords:
            return None

        candidates: Dict[str, int] = {}
        for st in getattr(ctx, "suspected_titles", []) or []:
            if not isinstance(st, dict):
                continue
            t = str(st.get("title") or "").strip()
            if not t:
                continue
            rank = self._confidence_rank_value(st.get("confidence"))
            candidates[t] = max(candidates.get(t, 0), rank)

        decoder_out = ctx.get_expert_output(ExpertType.DECODER) or {}
        for dt in decoder_out.get("decoded_terms", []) or []:
            if not isinstance(dt, dict):
                continue
            bm = dt.get("best_match") or {}
            t = str(bm.get("title") or "").strip()
            if not t:
                continue
            rank = self._confidence_rank_value(bm.get("confidence"))
            candidates[t] = max(candidates.get(t, 0), rank)

        exclude_norm = self._normalize_match_text(exclude_title)
        best_title = None
        best_score = -1.0

        for title, conf_rank in candidates.items():
            title_norm = self._normalize_match_text(title)
            if not title_norm or title_norm == exclude_norm:
                continue

            title_keywords = self._extract_domain_keywords(title)
            if not (title_keywords & anchor_keywords):
                continue

            score = float(conf_rank * 2)
            if self._has_official_title_evidence(ctx, title):
                score += 4.0
            score += float(self._score_candidate_evidence_bucket(self._get_candidate_evidence_bucket(ctx, title)))
            if score > best_score:
                best_score = score
                best_title = title

        if best_title and best_score >= 3.0:
            return best_title
        return None

    def _detect_title_anchor_drift(
        self,
        ctx: "ConversationContext",
        *,
        official_title: str,
        vf_anchor: str = "",
    ) -> Dict[str, Any]:
        """
        제목 앵커와 최종 제목의 도메인 키워드가 충돌하는지 검사.
        """
        anchor_terms = self._collect_title_anchor_terms(ctx)
        if not anchor_terms:
            return {"is_drift": False}

        anchor_keywords: set[str] = set()
        for term in anchor_terms:
            anchor_keywords.update(self._extract_domain_keywords(term))
        if not anchor_keywords:
            return {"is_drift": False}

        title_keywords = self._extract_domain_keywords(official_title)
        if not title_keywords:
            return {"is_drift": False}

        # 서로 키워드를 공유하면 드리프트 아님
        if anchor_keywords & title_keywords:
            return {"is_drift": False}

        # 본문 플롯/캐릭터 앵커 + 공식 근거가 충분하면 드리프트로 보지 않음
        if vf_anchor in {"plot_mention", "character_mention", "character_title_link"}:
            if self._has_official_title_evidence(ctx, official_title):
                return {"is_drift": False}

        replacement = self._pick_drift_replacement_title(
            ctx,
            anchor_keywords=anchor_keywords,
            exclude_title=official_title,
        )
        return {
            "is_drift": True,
            "anchor_keywords": sorted(anchor_keywords),
            "title_keywords": sorted(title_keywords),
            "replacement_title": replacement,
        }

    @staticmethod
    def _check_general_word_signal(
        official_title: str,
        ctx: "ConversationContext",
        vf_grounding: dict,
    ) -> bool:
        """
        일반어 패턴 부정 신호 검사.
        
        고유명사/앵커가 없이 일반어(욕설, 일상어, 플랫폼명)만으로 매칭된 경우 True 반환.
        하드코딩 단어 목록이 아닌, 구조적 패턴으로 판별:
        1. anchor가 없고
        2. decoder_grounded=false이고
        3. 본문에 작품 고유 정보(캐릭터명, 줄거리 키워드)가 없으면
        → 일반어로 우연히 매칭된 것으로 판정
        """
        from .rules import GENRE_ARCHETYPE_TERMS, PLATFORM_ABBREVIATIONS
        
        # 제목이 장르 아키타입 용어 자체이면 → 작품이 아닌 장르 언급
        title_norm = official_title.replace(" ", "")
        for archetype in GENRE_ARCHETYPE_TERMS:
            if title_norm == archetype.replace(" ", ""):
                return True
        
        # 제목이 플랫폼 약칭이면 → 플랫폼 논의
        for plat in PLATFORM_ABBREVIATIONS:
            if title_norm == plat.replace(" ", ""):
                return True
        
        # decoder_grounded=false이고 anchor도 없으면 → 고유 앵커 부재
        decoder_grounded = vf_grounding.get("decoder_grounded", True)
        anchor_found = str(vf_grounding.get("anchor_found", "")).lower()
        if not decoder_grounded and anchor_found in ("search_only", "none", ""):
            # 본문에 작품 고유 정보가 있는지 최종 체크
            # uncertainty_sources에 본문 증거 부재가 이미 기록되어 있으면 → 일반어 신호
            uncertainty = getattr(ctx, "uncertainty_sources", []) or []
            body_absent = any("본문에 작품 직접 언급 없음" in u for u in uncertainty)
            official_absent = any("공식 플랫폼 증거 없음" in u for u in uncertainty)
            if body_absent and official_absent:
                return True
        
        return False

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
        reason = f"처리 오류: {error}"
        reason_lines = self._reason_to_lines(reason, width=self.reason_wrap_width)
        return PickvelOutputItemV2(
            post_id=post_id,
            identity=PickvelIdentity(
                is_relevant=False,
                reason="\n".join(reason_lines) if reason_lines else reason,
                reason_lines=reason_lines if reason_lines else [reason],
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
        reason = result.identity.reason or ""
        reason_lines = reason.splitlines() if isinstance(reason, str) else [str(reason)]
        if reason_lines:
            print(f"[{_ts()}]    reason: {reason_lines[0]}", file=sys.stderr)
            for line in reason_lines[1:]:
                print(f"[{_ts()}]            {line}", file=sys.stderr)
        else:
            print(f"[{_ts()}]    reason: ", file=sys.stderr)
        
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

