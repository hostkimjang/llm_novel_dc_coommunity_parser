"""
Stage 3: Verifier Expert - 증거 검증 분석관
Final evidence verification and confirmation.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from .prompts import (
    VERIFIER_SYSTEM,
    VERIFIER_PROMPT,
    build_verifier_system_prompt,
)
from .decoder import abbreviation_match_score
from ..grounding.candidate_generation import record_candidate_stage_receipt
from .utils import (
    parse_json_with_think_removal,
    build_search_aggregation_summary,
    _ts,
)
from ..domain.rules import OFFICIAL_PLATFORMS, GENRE_ARCHETYPE_TERMS, GENRE_KEYWORDS, is_novel_domain


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

    _GENERIC_RELATION_EXTRA_TERMS = (
        "무림맹", "맹주", "마교", "혈교", "정파", "사파", "혈파", "마파",
        "천마", "천마신교", "신교", "문파", "종파", "교단", "교주",
        "장문인", "문주", "소교주", "장로", "사부", "사형", "사제",
        "제자", "막내", "막내제자", "협객", "고수", "절정고수",
        "화경", "현경", "검법", "도법", "내공", "무공", "강호",
        "기사단", "마탑", "마법사", "드래곤", "엘프", "아카데미",
        "히로인", "주인공", "빌런", "헌터", "던전", "탑", "시스템",
    )

    @classmethod
    def _generic_relation_term_norms(cls) -> set[str]:
        terms: set[str] = set()
        for values in (GENRE_KEYWORDS or {}).values():
            for token in values:
                if isinstance(token, str) and token.strip():
                    terms.add(cls._norm_text(token))
        for token in GENRE_ARCHETYPE_TERMS:
            if isinstance(token, str) and token.strip():
                terms.add(cls._norm_text(token))
        for token in cls._GENERIC_RELATION_EXTRA_TERMS:
            if token:
                terms.add(cls._norm_text(token))
        return {term for term in terms if len(term) >= 2}

    @classmethod
    def _is_generic_relation_surface(cls, value: Any) -> bool:
        norm = cls._norm_text(value)
        if not norm or len(norm) < 2:
            return False
        generic_terms = cls._generic_relation_term_norms()
        if norm in generic_terms:
            return True
        remaining = norm
        for term in sorted(generic_terms, key=len, reverse=True):
            if len(term) < 2:
                continue
            remaining = remaining.replace(term, "")
            if not remaining:
                return True
        remaining = re.sub(r"(들|에|에서|으로|로|은|는|이|가|을|를|도|만|랑|와|과|네|임|냐|다)$", "", remaining)
        return not remaining

    @classmethod
    def _title_non_generic_terms(cls, title: Any) -> List[str]:
        terms: List[str] = []
        seen: set[str] = set()
        for token in re.findall(r"[가-힣A-Za-z0-9]{2,}", str(title or "")):
            norm = cls._norm_text(token)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            if not cls._is_generic_relation_surface(token):
                terms.append(norm)
        return terms

    @classmethod
    def _post_discussion_text(cls, post: Dict[str, Any], comments: Optional[List[str]] = None) -> str:
        chunks: List[str] = [str((post or {}).get("title") or "")]
        for block in ((post or {}).get("content_blocks") or (post or {}).get("content") or []):
            if isinstance(block, dict):
                chunks.append(str(block.get("text") or block.get("content") or ""))
            elif isinstance(block, str):
                chunks.append(block)
        chunks.extend(str(c or "") for c in (comments or []) if str(c or "").strip())
        return " ".join(chunk for chunk in chunks if str(chunk or "").strip())

    def _is_generic_relation_only_mapping(
        self,
        candidate_title: Any,
        post: Dict[str, Any],
        comments: Optional[List[str]] = None,
        alias_terms: Optional[List[str]] = None,
    ) -> bool:
        """
        Detect title promotion driven only by reusable genre/faction vocabulary.

        Example: post mentions "무림맹/마교/혈교" and search finds a real title
        "무림맹주 막내제자".  The shared terms prove the genre, not that work.
        """
        title = str(candidate_title or "").strip()
        if not title:
            return False
        post_text = self._post_discussion_text(post or {}, comments or [])
        post_norm = self._norm_text(post_text)
        title_norm = self._norm_text(title)
        if not post_norm or not title_norm:
            return False
        if title_norm in post_norm:
            return False

        generic_terms = self._generic_relation_term_norms()
        generic_hits = [
            term for term in generic_terms
            if term and term in title_norm and term in post_norm
        ]
        if not generic_hits:
            return False

        title_specific_terms = self._title_non_generic_terms(title)
        if any(term and term in post_norm for term in title_specific_terms):
            return False

        aliases = [
            str(alias or "").strip()
            for alias in (alias_terms or [])
            if str(alias or "").strip()
        ]
        non_generic_alias_hits = [
            alias for alias in aliases
            if self._norm_text(alias) in post_norm
            and not self._is_generic_relation_surface(alias)
        ]
        if non_generic_alias_hits:
            return False

        return True

    @staticmethod
    def _env_int(name: str, default: int, *, minimum: int, maximum: Optional[int] = None) -> int:
        """Read int env safely with bounds."""
        try:
            value = int(os.getenv(name, str(default)))
        except Exception:
            value = default
        value = max(minimum, value)
        if maximum is not None:
            value = min(maximum, value)
        return value

    @classmethod
    def _clip_text(
        cls,
        text: Any,
        max_chars: int,
        *,
        marker: str = "\n...[TRUNCATED]...\n",
        head_ratio: float = 0.72,
    ) -> str:
        """Head-tail clip to preserve context from both ends."""
        raw = str(text or "").strip()
        if max_chars <= 0 or len(raw) <= max_chars:
            return raw
        budget = max_chars - len(marker)
        if budget <= 40:
            return raw[:max_chars]
        head = max(20, int(budget * head_ratio))
        tail = max(20, budget - head)
        return raw[:head].rstrip() + marker + raw[-tail:].lstrip()

    _PLATFORM_BRANDING_NORMS = {
        "웹소설로꿈꾸는세상",
        "웹소설의유토피아",
        "노벨피아",
        "문피아",
        "카카오페이지",
        "네이버시리즈",
        "리디",
    }

    @classmethod
    def _is_platform_branding_title(cls, title: str) -> bool:
        import re
        if not isinstance(title, str):
            return False
        raw = title.strip()
        if not raw:
            return False
        norm = re.sub(r"[^\w가-힣]", "", raw).lower()
        if norm in cls._PLATFORM_BRANDING_NORMS:
            return True
        # "조아라 : 스토리 본능을 깨우다" 같은 플랫폼 브랜드 문구 차단
        if re.match(
            r"^(?:노벨피아|문피아|카카오페이지|네이버\s*시리즈|조아라|리디)\s*[:：]\s*.+$",
            raw,
            flags=re.IGNORECASE,
        ):
            return True
        return False

    @classmethod
    def _is_community_artifact_title(cls, title: Any) -> bool:
        """커뮤니티 검색 스니펫 라벨이 작품명처럼 들어오는 경우를 차단."""
        import re

        if not isinstance(title, str):
            return False
        raw = title.strip()
        if not raw:
            return False

        match = re.match(
            r"^(?:이미지|일반|공지|개념글|질문)\s+(.+)$",
            raw,
            flags=re.IGNORECASE,
        )
        if not match:
            return False

        tail = str(match.group(1) or "").strip()
        tail_norm = re.sub(r"[^0-9A-Za-z가-힣]", "", tail.lower())
        if not tail_norm:
            return True
        if cls._is_platform_branding_title(tail):
            return True
        return len(tail_norm) <= 20

    @staticmethod
    def _is_novel_detail_url(url: str) -> bool:
        """공식 플랫폼 URL 중 작품 상세 URL만 허용한다."""
        if not isinstance(url, str) or not url:
            return False
        try:
            from urllib.parse import urlparse
            import re

            parsed = urlparse(url)
            host = (parsed.netloc or "").lower()
            path = (parsed.path or "").lower()
            query = (parsed.query or "").lower()
        except Exception:
            return False

        # 검색/목록 URL 우선 차단
        if any(tok in path for tok in ("/arena/", "/community/", "/board/", "/forum/", "/review/", "/reviews/")):
            return False
        if any(tok in path for tok in ("/search", "/author", "/writers", "/ranking", "/best", "/genre", "/tag", "/list")):
            return False
        if any(tok in query for tok in ("search=", "q=", "query=", "keyword=", "writer=", "author=", "tag=", "genre=", "page=")):
            return False
        if ("kakao.page" in host or "page.kakao.com" in host) and "tab_type=comment" in query:
            return False

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
        return False

    @classmethod
    def _is_official_detail_evidence_url(cls, url: Any, trust_score: Optional[float] = None) -> bool:
        url_text = str(url or "").strip()
        if not url_text:
            return False
        if trust_score is not None:
            try:
                if float(trust_score) < 0.8:
                    return False
            except Exception:
                return False
        return cls._is_novel_detail_url(url_text)

    @staticmethod
    def _norm_text(value: Any) -> str:
        import re
        return re.sub(r"[^\w가-힣]", "", str(value or "")).lower()

    @classmethod
    def _confidence_to_unit(cls, value: Any, *, default: float = 0.0) -> float:
        if isinstance(value, (int, float)):
            try:
                raw = float(value)
            except Exception:
                return default
            if raw > 1.0:
                raw = raw / 100.0 if raw <= 100.0 else 1.0
            return max(0.0, min(1.0, raw))
        text = str(value or "").strip().lower()
        if not text:
            return default
        mapping = {
            "max": 1.0,
            "very_high": 0.95,
            "very high": 0.95,
            "high": 0.9,
            "medium": 0.65,
            "low": 0.35,
            "none": 0.0,
        }
        if text in mapping:
            return mapping[text]
        try:
            return max(0.0, min(1.0, float(text)))
        except Exception:
            return default

    @staticmethod
    def _contains_as_token(raw_text: str, token: str) -> bool:
        import re
        if not isinstance(raw_text, str) or not raw_text.strip():
            return False
        token = str(token or "").strip()
        if not token:
            return False
        pattern = re.compile(
            rf"(?<![가-힣A-Za-z0-9]){re.escape(token)}(?![가-힣A-Za-z0-9])"
        )
        return bool(pattern.search(raw_text))

    def _is_short_single_token_title(self, title: str) -> bool:
        import re
        raw = str(title or "").strip()
        if not raw:
            return False
        norm = self._norm_text(raw)
        if len(norm) == 0 or len(norm) > 3:
            return False
        tokens = re.findall(r"[가-힣A-Za-z0-9]+", raw)
        return len(tokens) == 1

    def _has_reliable_alias_bridge(
        self,
        title: str,
        post: Dict[str, Any],
        decoder_result: Dict[str, Any],
    ) -> bool:
        """
        약칭(original) -> 제목(best_match.title) 브리지가 신뢰 가능한지 확인.
        short title 오매칭 시 character_mention만으로 승격되는 것을 막기 위한 보조 가드.
        """
        title_norm = self._norm_text(title)
        if not title_norm:
            return False

        post_title_norm = self._norm_text((post or {}).get("title", ""))
        for term in (decoder_result or {}).get("decoded_terms", []):
            if not isinstance(term, dict):
                continue
            best = term.get("best_match") or {}
            bm_title = best.get("title")
            if self._norm_text(bm_title) != title_norm:
                continue

            original = str(term.get("original") or "").strip()
            original_norm = self._norm_text(original)
            if not original_norm or original_norm == title_norm:
                continue
            if original_norm not in post_title_norm:
                continue

            conf = str(best.get("confidence") or "").lower()
            grounding = term.get("grounding") or {}
            anchor = str(grounding.get("anchor_type") or "").lower()
            strong_anchor = anchor in {"title_mention", "character_title_link", "plot_mention"}

            has_official_candidate = False
            for cand in (term.get("candidates") or []):
                if not isinstance(cand, dict):
                    continue
                c_title = cand.get("official_novel_title") or cand.get("official_title")
                if self._norm_text(c_title) != title_norm:
                    continue
                c_url = str(cand.get("url") or "")
                if self._is_novel_detail_url(c_url):
                    has_official_candidate = True
                    break

            if conf in {"high", "max"} and (strong_anchor or has_official_candidate):
                return True
            if conf == "medium" and strong_anchor and has_official_candidate:
                return True

        return False

    @classmethod
    def _decoder_term_matches_title(cls, term: Dict[str, Any], title: str) -> bool:
        title_norm = cls._norm_text(title)
        if not title_norm or not isinstance(term, dict):
            return False

        best = term.get("best_match") or {}
        best_title = best.get("title") or best.get("official_novel_title")
        if cls._norm_text(best_title) == title_norm:
            return True

        for cand in (term.get("candidates") or []):
            if not isinstance(cand, dict):
                continue
            cand_title = (
                cand.get("official_novel_title")
                or cand.get("official_title")
                or cand.get("title")
            )
            if cls._norm_text(cand_title) == title_norm:
                return True
        return False

    @classmethod
    def _surface_in_text(cls, raw_text: str, surface: str) -> bool:
        if not isinstance(raw_text, str) or not raw_text.strip():
            return False
        surface = str(surface or "").strip()
        if not surface:
            return False
        surface_norm = cls._norm_text(surface)
        raw_norm = cls._norm_text(raw_text)
        if surface_norm and surface_norm in raw_norm:
            return True
        return cls._contains_as_token(raw_text, surface)

    @classmethod
    def _title_surface_matches(cls, observed: Any, target: Any) -> bool:
        observed_norm = cls._norm_text(observed)
        target_norm = cls._norm_text(target)
        if not observed_norm or not target_norm:
            return False
        return bool(
            observed_norm == target_norm
            or observed_norm in target_norm
            or target_norm in observed_norm
        )

    def _has_direct_title_tuple_support(
        self,
        ctx: Any,
        title: str,
    ) -> bool:
        if not ctx or not isinstance(title, str) or not title.strip():
            return False

        post_data = getattr(ctx, "post_data", None) or {}
        image_enrichment = [
            item for item in (post_data.get("image_enrichment") or [])
            if isinstance(item, dict)
        ]
        for item in image_enrichment:
            explicit_title = str(item.get("explicit_work_title") or "").strip()
            title_role = str(item.get("title_role") or "").strip()
            if title_role not in {"", "work_title"}:
                continue
            if not self._title_surface_matches(explicit_title, title):
                continue

            tuple_hits = 0
            if str(item.get("explicit_author_name") or "").strip():
                tuple_hits += 1
            item_blob = " ".join(
                str(item.get(key) or "")
                for key in ("ocr_text", "visual_summary", "screen_type", "surface_type")
            )
            if re.search(
                r"(?:작가명|작가|PLUS\s*연재|자유\s*연재|독점|조회\s*[0-9,]+|추천\s*[0-9,]+|\d+\s*(?:회차|화))",
                item_blob,
                flags=re.IGNORECASE,
            ):
                tuple_hits += 1
            if str(item.get("screen_type") or "").strip() == "work_surface":
                tuple_hits += 1
            if tuple_hits >= 2:
                return True

        text_chunks: List[str] = [str(post_data.get("title") or "")]
        for block in (post_data.get("content_blocks") or []):
            if isinstance(block, dict):
                text_chunks.append(str(block.get("text") or ""))
            elif isinstance(block, str):
                text_chunks.append(block)
        joined = " ".join(chunk for chunk in text_chunks if isinstance(chunk, str) and chunk.strip())
        if not joined or not self._surface_in_text(joined, title):
            return False

        tuple_hits = 0
        if re.search(r"(?:작가명|작가)\s*[가-힣A-Za-z0-9]{2,20}", joined):
            tuple_hits += 1
        if re.search(
            r"(?:PLUS\s*연재|자유\s*연재|독점|조회\s*[0-9,]+|추천\s*[0-9,]+|\d+\s*(?:회차|화)|노벨피아|문피아|시리즈|카카오페이지)",
            joined,
            flags=re.IGNORECASE,
        ):
            tuple_hits += 1
        if tuple_hits >= 2:
            return True

        # 댓글에 직접 작품 상세 URL이 있고, 게시글 제목이 그 작품명을 그대로 가리키는 경우는
        # OCR/VLM tuple support와 동급의 직접 증거로 본다.
        comments = list(getattr(ctx, "comments", None) or [])
        detail_urls: List[str] = []
        for comment in comments:
            if not isinstance(comment, str) or not comment.strip():
                continue
            for match in re.findall(r"https?://[^\s)>\"]+", comment):
                if self._is_novel_detail_url(match):
                    detail_urls.append(match.rstrip("/"))

        if detail_urls and self._surface_in_text(str(post_data.get("title") or ""), title):
            return True

        return tuple_hits >= 2

    def _detect_decoder_alias_mention(
        self,
        post: Dict[str, Any],
        comments: List[str],
        title: str,
        decoder_result: Dict[str, Any],
    ) -> Tuple[bool, bool, Optional[str]]:
        """Return (title_abbrev_mentioned, body_abbrev_mentioned, matched_alias)."""
        import re

        if not title:
            return False, False, None

        post_title = str((post or {}).get("title") or "")
        body_parts: List[str] = []
        for block in (post or {}).get("content_blocks", []) or []:
            if isinstance(block, dict) and block.get("text"):
                body_parts.append(str(block.get("text") or ""))
            elif isinstance(block, str):
                body_parts.append(block)
        post_body = " ".join(body_parts)
        comments_text = " ".join(c for c in (comments or []) if isinstance(c, str))
        body_and_comments = f"{post_body} {comments_text}".strip()

        for term in (decoder_result or {}).get("decoded_terms", []):
            if not isinstance(term, dict):
                continue
            if term.get("is_author_name"):
                continue
            if not self._decoder_term_matches_title(term, title):
                continue

            original = str(term.get("original") or "").strip()
            if len(self._norm_text(original)) < 2:
                continue

            alias_candidates: List[str] = [original]
            title_norm = self._norm_text(title)
            for token in re.findall(r"[가-힣A-Za-z0-9]{2,12}", original):
                token = str(token or "").strip()
                token_norm = self._norm_text(token)
                if len(token_norm) < 2 or token_norm == self._norm_text(original):
                    continue
                if (
                    token_norm in title_norm
                    or abbreviation_match_score(token, title) >= 0.72
                ) and token not in alias_candidates:
                    alias_candidates.append(token)

            for alias in alias_candidates:
                in_body_comments = self._surface_in_text(body_and_comments, alias)
                if in_body_comments:
                    return True, True, alias
            for alias in alias_candidates:
                in_title = self._surface_in_text(post_title, alias)
                if in_title:
                    return True, False, alias

        return False, False, None

    def _detect_verified_alias_grounding(
        self,
        post: Dict[str, Any],
        comments: List[str],
        title: str,
        decoder_result: Dict[str, Any],
        verification: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, bool, Optional[str]]:
        """Detect alias grounding from decoder terms first, then verifier slang_insight fallback."""
        title_abbrev_mentioned, body_abbrev_mentioned, matched_alias = self._detect_decoder_alias_mention(
            post,
            comments,
            title,
            decoder_result,
        )
        if title_abbrev_mentioned:
            return title_abbrev_mentioned, body_abbrev_mentioned, matched_alias

        slang_insight = (verification or {}).get("slang_insight") or {}
        if not isinstance(slang_insight, dict):
            slang_insight = {}

        detected_term = str(slang_insight.get("detected_term") or "").strip()
        decoded_term = str(slang_insight.get("decoded_term") or "").strip()
        decode_verified = slang_insight.get("decode_verified") is True

        if (
            len(self._norm_text(detected_term)) < 2
            or not decoded_term
            or self._norm_text(decoded_term) != self._norm_text(title)
            or not decode_verified
        ):
            return False, False, None

        post_title = str((post or {}).get("title") or "")
        body_parts: List[str] = []
        for block in (post or {}).get("content_blocks", []) or []:
            if isinstance(block, dict) and block.get("text"):
                body_parts.append(str(block.get("text") or ""))
            elif isinstance(block, str):
                body_parts.append(block)
        post_body = " ".join(body_parts)
        comments_text = " ".join(c for c in (comments or []) if isinstance(c, str))
        body_and_comments = f"{post_body} {comments_text}".strip()

        in_body_comments = self._surface_in_text(body_and_comments, detected_term)
        in_title = self._surface_in_text(post_title, detected_term)
        if in_body_comments:
            return True, True, detected_term
        if in_title:
            return True, False, detected_term
        return False, False, None

    def _has_short_title_official_support(
        self,
        title: str,
        all_search: List[Dict[str, Any]],
        ctx: Optional[Any],
    ) -> bool:
        """
        짧은 제목(<=3)이 공식 상세 페이지에서 '제목 필드' 기준으로 실제 지지되는지 확인.
        content/snippet 부분문자열만으로는 인정하지 않는다.
        """
        if not self._is_short_single_token_title(title):
            return True

        strict_hits = 0
        for sr in all_search or []:
            if not isinstance(sr, dict):
                continue
            sr_url = str(sr.get("url") or "")
            if not self._is_novel_detail_url(sr_url):
                continue
            sr_title = str(sr.get("title") or "")
            if self._contains_as_token(sr_title, title):
                strict_hits += 1

        for fe in (getattr(ctx, "fetched_page_info", None) or []):
            if not isinstance(fe, dict):
                continue
            fe_url = str(fe.get("url") or "")
            if not self._is_novel_detail_url(fe_url):
                continue
            structured = fe.get("structured_info") or {}
            if not isinstance(structured, dict):
                structured = {}
            candidates = [
                str(structured.get("title") or ""),
                str(structured.get("page_title") or ""),
            ]
            if any(self._contains_as_token(text, title) for text in candidates if text):
                strict_hits += 1

        # short-title은 최소 2개 이상의 독립적인 공식 필드 히트가 있어야 신뢰
        return strict_hits >= 2

    @classmethod
    def _is_author_new_work_post(cls, post: Dict[str, Any]) -> bool:
        import re

        raw_title = str((post or {}).get("title") or "")
        if not raw_title:
            return False
        norm = raw_title.lower().replace(" ", "")
        temporal_kws = ("신작", "최신작", "새작품", "이번작", "전작", "차기작", "신간")
        launch_kws = ("스타트", "초반", "초반부", "첫인상", "첫화", "도입", "출발")
        has_temporal = any(tok in norm for tok in temporal_kws)
        has_launch = any(tok in norm for tok in launch_kws)
        author_lead = bool(
            re.match(
                r"^\s*[가-힣A-Za-z0-9]{2,12}(?:꺼)?\s*(?:신작|최신작|새작품|이번작|전작|차기작|신간)",
                raw_title,
            )
        )
        return has_temporal or (author_lead and has_launch)

    @classmethod
    def _collect_author_surfaces(
        cls,
        decoder_result: Dict[str, Any],
        verification: Dict[str, Any],
    ) -> List[str]:
        seen: set[str] = set()
        out: List[str] = []

        def _add(value: Any) -> None:
            raw = str(value or "").strip()
            norm = cls._norm_text(raw)
            if not norm or norm in seen:
                return
            seen.add(norm)
            out.append(raw)

        for term in (decoder_result or {}).get("decoded_terms", []):
            if not isinstance(term, dict) or not term.get("is_author_name"):
                continue
            _add(term.get("original"))
            _add((term.get("author_info") or {}).get("name"))

        author_info = verification.get("author_info") or {}
        if isinstance(author_info, dict):
            _add(author_info.get("detected_author"))
        return out

    def _has_exact_official_title_support(
        self,
        title: str,
        all_search: List[Dict[str, Any]],
        ctx: Optional[Any],
    ) -> bool:
        title_norm = self._norm_text(title)
        if not title_norm:
            return False

        support_hits = 0
        for sr in all_search or []:
            if not isinstance(sr, dict):
                continue
            sr_url = str(sr.get("url") or "")
            if not self._is_novel_detail_url(sr_url):
                continue
            sr_title = str(sr.get("title") or "")
            if self._norm_text(sr_title) == title_norm or self._contains_as_token(sr_title, title):
                support_hits += 1

        for fe in (getattr(ctx, "fetched_page_info", None) or []):
            if not isinstance(fe, dict):
                continue
            fe_url = str(fe.get("url") or "")
            if not self._is_novel_detail_url(fe_url):
                continue
            structured = fe.get("structured_info") or {}
            if not isinstance(structured, dict):
                structured = {}
            candidates = [
                str(structured.get("title") or ""),
                str(structured.get("page_title") or ""),
            ]
            if any(self._norm_text(text) == title_norm or self._contains_as_token(text, title) for text in candidates if text):
                support_hits += 1

        return support_hits >= 1

    def _should_block_character_like_title(
        self,
        title: str,
        post: Dict[str, Any],
        comments: List[str],
        gatekeeper_result: Dict[str, Any],
        decoder_result: Dict[str, Any],
        verification: Dict[str, Any],
        all_search: List[Dict[str, Any]],
        ctx: Optional[Any],
    ) -> bool:
        """
        캐릭터명/문장성 단어가 official_title로 승격되는 케이스 차단.
        특히 short title + character_mention 앵커 조합을 보수적으로 제한한다.
        """
        import re

        title = str(title or "").strip()
        if not title:
            return False

        title_norm = self._norm_text(title)
        if not title_norm:
            return False

        is_short = self._is_short_single_token_title(title)
        if not is_short:
            return False

        post_title = str((post or {}).get("title") or "")
        body_parts = []
        for blk in (post or {}).get("content_blocks", []):
            if isinstance(blk, dict) and blk.get("text"):
                body_parts.append(str(blk.get("text")))
            elif isinstance(blk, str):
                body_parts.append(blk)
        body_text = " ".join(body_parts)
        comments_text = " ".join(comments or [])
        full_text = f"{post_title} {body_text} {comments_text}"
        full_text_norm = self._norm_text(full_text)

        title_token = ""
        title_tokens = re.findall(r"[가-힣A-Za-z0-9]+", title)
        if title_tokens:
            title_token = title_tokens[0]
        particle_suffixes = ("가", "이", "은", "는", "을", "를", "도", "만", "네", "다", "냐", "임", "듯")
        particle_collision = bool(
            title_token and any(f"{title_token}{sfx}" in full_text for sfx in particle_suffixes)
        )

        gk_chars = []
        if isinstance(gatekeeper_result, dict):
            ents = gatekeeper_result.get("detected_entities") or {}
            if isinstance(ents, dict):
                gk_chars = ents.get("possible_characters") or []
        gk_char_collision = any(self._norm_text(c) == title_norm for c in gk_chars if isinstance(c, str))

        decoder_char_collision = False
        for term in (decoder_result or {}).get("decoded_terms", []):
            if not isinstance(term, dict):
                continue
            if self._norm_text(term.get("original")) != title_norm:
                continue
            for interp in (term.get("interpretations") or []):
                if not isinstance(interp, dict):
                    continue
                interp_type = str(interp.get("type") or "").lower()
                if interp_type in {"character_name", "character"}:
                    decoder_char_collision = True
                    break
            if decoder_char_collision:
                break

        grounding = (verification or {}).get("grounding_check") or {}
        anchor = str(grounding.get("anchor_found") or "").lower()
        character_anchor = anchor in {"character_mention", "search_only", "none"}

        if not (particle_collision or gk_char_collision or decoder_char_collision or character_anchor):
            return False

        reliable_alias = self._has_reliable_alias_bridge(title, post, decoder_result or {})
        short_title_supported = self._has_short_title_official_support(title, all_search, ctx)

        # short title이 캐릭터 충돌 + character 중심 앵커인데,
        # 공식 상세 근거가 약하거나(alias bridge 부재)면 title 승격 차단.
        if character_anchor and not reliable_alias:
            return True
        if (particle_collision or gk_char_collision or decoder_char_collision) and not short_title_supported:
            return True

        return False

    def _compact_search_results(
        self,
        results: List[Dict[str, Any]],
        *,
        max_items: int,
        max_snippet: int,
    ) -> List[Dict[str, Any]]:
        """Keep only verifier-relevant search fields and clip long bodies."""
        compact: List[Dict[str, Any]] = []
        for i, sr in enumerate((results or [])[:max_items], 1):
            if not isinstance(sr, dict):
                continue

            item: Dict[str, Any] = {}
            for key in (
                "title",
                "url",
                "domain",
                "author",
                "content",
                "snippet",
                "_evidence_id",
                "_evidence_rank",
                "_is_derivative",
                "_derivative_of",
            ):
                value = sr.get(key)
                if value not in (None, "", [], {}):
                    item[key] = value

            if not item.get("_evidence_id"):
                item["_evidence_id"] = f"E{i:03d}"
            if not item.get("_evidence_rank"):
                item["_evidence_rank"] = i

            if item.get("title"):
                item["title"] = self._clip_text(item["title"], 240, marker=" ... ")

            for key in ("content", "snippet"):
                txt = str(item.get(key) or "")
                if txt:
                    item[key] = self._clip_text(txt, max_snippet)

            if item.get("content") and item.get("snippet"):
                if self._norm_text(item["content"]) == self._norm_text(item["snippet"]):
                    item.pop("snippet", None)
            elif item.get("snippet") and not item.get("content"):
                item["content"] = item.pop("snippet")

            url = str(item.get("url") or "")
            if url:
                item["is_official_detail_url"] = self._is_novel_detail_url(url)

            structured = sr.get("structured_info") or {}
            if isinstance(structured, dict):
                for sk in ("title", "page_title", "author", "page_type", "content_status"):
                    sval = structured.get(sk)
                    if sval not in (None, "", [], {}):
                        item[f"structured_{sk}"] = sval

            if item.get("_is_derivative"):
                derivative_of = str(item.get("_derivative_of") or "")
                orig_title = str(item.get("title") or "")
                item["title"] = (
                    f"{orig_title} "
                    f"(⚠️ 이 작품은 '{derivative_of}'의 2차창작/팬픽이며 원작 제목이 아닙니다)"
                )

            compact.append(item)
        return compact

    def _build_user_prompt(
        self,
        post: Dict[str, Any],
        comments: List[str],
        gatekeeper_result: Dict[str, Any],
        decoder_result: Dict[str, Any],
        verification_search: Optional[List[Dict[str, Any]]] = None,
        conversation_context: Optional[str] = None,
        ctx: Optional[Any] = None,
        *,
        compact_mode: bool = False,
    ) -> str:
        """Build verifier prompt with bounded evidence sizes."""
        post = post or {}
        comments = comments or []
        gatekeeper_result = gatekeeper_result or {}
        decoder_result = decoder_result or {}

        post_json = self._build_post_json(post, comments, compact=compact_mode)
        gatekeeper_summary = self._summarize_gatekeeper(gatekeeper_result)
        decoder_summary = self._summarize_decoder(decoder_result)

        if ctx and hasattr(ctx, "code_level_hints") and ctx.code_level_hints:
            corrections = []
            for hint in ctx.code_level_hints:
                if isinstance(hint, dict) and hint.get("type") == "abbreviation_correction":
                    corrections.append({
                        "original_term": hint.get("original_term", ""),
                        "corrected_title": hint.get("corrected_title", ""),
                        "abbreviation_score": hint.get("abbreviation_score", 0),
                        "source": hint.get("source", ""),
                    })
            if corrections:
                decoder_summary["abbreviation_corrections"] = corrections[:3]

        suspected_titles_info = ""
        if ctx and hasattr(ctx, "suspected_titles") and ctx.suspected_titles:
            suspected_items = []
            max_suspected = 2 if compact_mode else 3
            for st in ctx.suspected_titles[:max_suspected]:
                title = st.get("title", "Unknown")
                conf = st.get("confidence", 0.5)
                try:
                    conf_str = f"{float(conf):.2f}"
                except (ValueError, TypeError):
                    conf_str = str(conf)
                suspected_items.append(f"- {title} (conf={conf_str})")
            if suspected_items:
                suspected_titles_info = (
                    "\n\n=== SUSPECTED TITLES (의심 작품) ===\n"
                    + "\n".join(suspected_items)
                    + "\n"
                )

        if ctx and hasattr(ctx, "primary_domain") and ctx.primary_domain:
            discourse_context = (
                f"\nDiscourseAnalyzer 분석 결과:\n"
                f"- Primary Domain: {ctx.primary_domain}\n"
                f"- Intent: {ctx.discourse_intent or 'unknown'}\n\n"
                "이 정보를 활용하여 도메인 불일치 여부를 체크하세요.\n"
            )
        else:
            discourse_context = "DiscourseAnalyzer 정보 없음 (스킵 가능)"

        if compact_mode:
            max_items = self._env_int(
                "LLM_VERIFIER_COMPACT_MAX_SEARCH_ITEMS", 8, minimum=4, maximum=16
            )
            max_snippet = self._env_int(
                "LLM_VERIFIER_COMPACT_MAX_SEARCH_CHARS", 700, minimum=200, maximum=2400
            )
            max_conv_chars = self._env_int(
                "LLM_VERIFIER_COMPACT_MAX_CONV_CHARS", 1400, minimum=400, maximum=4000
            )
            search_agg_queries = 4
            search_agg_domains = 4
            search_agg_purposes = 4
            searched_query_cap = 6
            hint_cap = 2
        else:
            max_items = self._env_int(
                "LLM_VERIFIER_MAX_SEARCH_ITEMS", 12, minimum=4, maximum=20
            )
            max_snippet = self._env_int(
                "LLM_VERIFIER_MAX_SEARCH_CHARS", 1600, minimum=300, maximum=4000
            )
            max_conv_chars = self._env_int(
                "LLM_VERIFIER_MAX_CONV_CHARS", 3000, minimum=800, maximum=6000
            )
            search_agg_queries = 8
            search_agg_domains = 6
            search_agg_purposes = 6
            searched_query_cap = 12
            hint_cap = 3

        verification_search_compact = self._compact_search_results(
            verification_search or [],
            max_items=max_items,
            max_snippet=max_snippet,
        )

        context_section = ""
        if conversation_context:
            cc = str(conversation_context)
            if len(cc) > max_conv_chars:
                head = max(180, int(max_conv_chars * 0.6))
                tail = max(180, max_conv_chars - head)
                cc = cc[:head] + "\n...[CONVERSATION_TRUNCATED]...\n" + cc[-tail:]
            context_section = f"\n\n=== CONVERSATION HISTORY ===\n{cc}\n"

        user_prompt = VERIFIER_PROMPT.format(
            post_json=json.dumps(post_json, ensure_ascii=False, indent=2),
            gatekeeper_json=json.dumps(gatekeeper_summary, ensure_ascii=False, indent=2),
            decoder_json=json.dumps(decoder_summary, ensure_ascii=False, indent=2),
            verification_search_json=json.dumps(
                verification_search_compact, ensure_ascii=False, indent=2
            ),
            discourse_context=discourse_context,
        ) + suspected_titles_info + context_section

        if ctx:
            search_agg = build_search_aggregation_summary(
                ctx,
                extra_results=verification_search_compact,
                max_domains=search_agg_domains,
                max_purposes=search_agg_purposes,
                max_queries=search_agg_queries,
            )
            if search_agg:
                user_prompt += search_agg

        content_text_count = int(post_json.get("content_text_count") or 0)
        content_total_chars = int(post_json.get("content_total_chars") or 0)
        has_content_text = bool(post_json.get("has_content_text"))
        user_prompt += (
            "\n\n=== CODE FACTS: BODY PRESENCE ===\n"
            f"- has_content_text: {has_content_text}\n"
            f"- content_text_count: {content_text_count}\n"
            f"- content_total_chars: {content_total_chars}\n"
            "규칙: has_content_text=true 이면 '본문 비어있음/본문 없음'으로 판단하지 마세요.\n"
            "이 경우 본문은 존재하므로, 작품 고유 근거 부족 여부를 별도로 판단하세요.\n"
        )

        try:
            gk_clues = gatekeeper_result.get("context_clues") or {}
            title_body_continuation = bool(gk_clues.get("title_as_body_continuation"))
            joined_text = str(gk_clues.get("title_body_joined_text") or "").strip()
            if title_body_continuation and joined_text:
                user_prompt += (
                    "\n\n===  TITLE-BODY CONTINUATION HINT ===\n"
                    "이 포스트는 제목이 본문 첫 문장의 일부일 수 있습니다.\n"
                    "제목과 본문 첫 줄을 하나의 연속 발화로 먼저 읽고 근거를 평가하세요.\n"
                    f"- joined_text: {self._clip_text(joined_text, 220 if compact_mode else 360, marker=' ... ')}\n"
                )
        except Exception:
            pass

        if ctx and hasattr(ctx, "code_level_hints") and ctx.code_level_hints:
            hints_section = "\n\n=== CODE-LEVEL ABBREVIATION ANALYSIS (코드 레벨 약어 분석 결과) ===\n"
            hints_section += "아래는 코드 레벨 음절 매칭 알고리즘이 발견한 결과입니다.\n"
            hints_section += "이 분석은 약어의 각 음절이 후보 제목의 단어 첫 글자와 순서대로 매칭되는지를 검증합니다.\n"
            hints_section += "LLM 추론과 독립적인 객관적 분석이므로, 높은 score(>=0.8)는 강한 증거입니다.\n\n"
            for i, hint in enumerate(ctx.code_level_hints[:hint_cap], 1):
                hints_section += (
                    f"  [{i}] 약어: '{hint.get('effective_keyword', '?')}' : "
                    f"후보: '{hint.get('corrected_title', '?')}' "
                    f"(score={hint.get('abbreviation_score', 0):.2f}, "
                    f"source={hint.get('source', '?')})\n"
                    f"      근거: {self._clip_text(hint.get('reasoning', ''), 180 if compact_mode else 260, marker=' ... ')}\n"
                )
            hints_section += "\n 위 코드 분석 결과를 우선 고려하되, 검색 증거·본문 맥락과 교차 검증하세요.\n"
            hints_section += "코드 분석과 다른 제목을 선택하려면 명확한 반증을 제시하세요.\n"
            user_prompt += hints_section

        if ctx and hasattr(ctx, "searched_queries") and ctx.searched_queries:
            searched_list = sorted(ctx.searched_queries)[:searched_query_cap]
            user_prompt += "\n\n=== PREVIOUS SEARCHES (이미 실행된 검색 쿼리) ===\n"
            for q in searched_list:
                user_prompt += f"  - {self._clip_text(q, 120, marker=' ... ')}\n"
            if len(getattr(ctx, "searched_queries", []) or []) > len(searched_list):
                omitted = len((getattr(ctx, "searched_queries", []) or [])) - len(searched_list)
                user_prompt += f"  - ... {omitted}개 추가 쿼리는 생략됨\n"
            user_prompt += "\n verification_search 요청 시 위 쿼리는 이미 실행되었으므로 중복 요청하지 마세요.\n"
            user_prompt += "다른 관점/키워드로 새로운 쿼리를 작성하세요.\n"

        user_prompt += "\n '웹소설로 꿈꾸는 세상!'은 노벨피아 플랫폼 슬로건입니다. 이 표현만 확인되면 official_novel_title로 채택하지 마세요.\n"
        return user_prompt

    def _resolve_verifier_max_tokens(self, prompt_chars: int, *, compact_mode: bool = False) -> int:
        """Use a bounded verifier generation budget instead of the client max."""
        global_default = max(256, int(getattr(self.llm, "max_tokens", 65536)))
        default_cap = 4096 if compact_mode else 8192
        env_key = "LLM_VERIFIER_COMPACT_MAX_TOKENS" if compact_mode else "LLM_VERIFIER_MAX_TOKENS"
        hard_key = "LLM_VERIFIER_COMPACT_HARD_CAP" if compact_mode else "LLM_VERIFIER_HARD_CAP"
        hard_cap = self._env_int(hard_key, default_cap, minimum=256, maximum=global_default)
        configured = self._env_int(env_key, min(default_cap, hard_cap), minimum=256, maximum=global_default)

        global_limit = self._env_int(
            "LLM_EXPERT_MAX_TOKENS",
            hard_cap,
            minimum=256,
            maximum=max(256, getattr(self.llm, "max_tokens", configured)),
        )
        max_tokens = min(configured, hard_cap, global_limit, max(256, getattr(self.llm, "max_tokens", configured)))

        context_limit = self._env_int(
            "LLM_VERIFIER_CONTEXT_LIMIT_TOKENS",
            int(os.getenv("LLM_CONTEXT_LIMIT_TOKENS") or os.getenv("LLM_N_CTX") or "32768"),
            minimum=4096,
            maximum=262144,
        )
        reserve = self._env_int(
            "LLM_VERIFIER_CONTEXT_RESERVE_TOKENS",
            768 if compact_mode else 1024,
            minimum=256,
            maximum=4096,
        )
        estimated_prompt_tokens = max(1, prompt_chars // 2)
        available = max(256, context_limit - estimated_prompt_tokens - reserve)
        return max(256, min(max_tokens, available))

    def _resolve_relation_judge_max_tokens(self) -> int:
        """Relation judge returns compact JSON; keep it from inheriting the client max."""
        client_cap = max(192, int(getattr(self.llm, "max_tokens", 65536)))
        hard_cap = self._env_int(
            "LLM_RELATION_JUDGE_HARD_CAP",
            2048,
            minimum=192,
            maximum=client_cap,
        )
        configured = self._env_int(
            "LLM_RELATION_JUDGE_MAX_TOKENS",
            hard_cap,
            minimum=192,
            maximum=client_cap,
        )
        return min(configured, hard_cap, client_cap)
    
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
        import re  # analyze() 스코프 전역 — 후처리 가드에서 re.sub 안전 사용
        start_time = time.time()
        
        # None 체크
        post = post or {}
        comments = comments or []
        post_id = post.get("post_id", "?")
        gatekeeper_result = gatekeeper_result or {}
        decoder_result = decoder_result or {}

        primary_prompt = self._build_user_prompt(
            post,
            comments,
            gatekeeper_result,
            decoder_result,
            verification_search,
            conversation_context,
            ctx,
            compact_mode=False,
        )
        compact_prompt = self._build_user_prompt(
            post,
            comments,
            gatekeeper_result,
            decoder_result,
            verification_search,
            conversation_context,
            ctx,
            compact_mode=True,
        )

        max_prompt_chars = self._env_int(
            "LLM_VERIFIER_MAX_PROMPT_CHARS", 50000, minimum=8000, maximum=120000
        )
        use_compact_first = len(primary_prompt) > max_prompt_chars
        if use_compact_first:
            print(
                f"[{_ts()}][{self.emoji}] ⚠️ Verifier 프롬프트 과대: "
                f"{len(primary_prompt):,}자 > {max_prompt_chars:,}자 → compact 모드로 시작",
                file=sys.stderr,
            )
        user_prompt = compact_prompt if use_compact_first else primary_prompt
        compact_retry_prompt = None if use_compact_first else compact_prompt
        
        print(f"[{_ts()}][{self.emoji}] {self.name} 검증 시작: post_id={post_id}", file=sys.stderr)
        
        try:
            result = self._call_llm(
                user_prompt,
                gatekeeper_result=gatekeeper_result,
                decoder_result=decoder_result,
                ctx=ctx,
                compact_retry_prompt=compact_retry_prompt,
                primary_compact_mode=use_compact_first,
            )
            elapsed = time.time() - start_time
            
            verification = result.get("verification_result", {})
            novel_id = verification.get("novel_identity") or {}

            # 🔧 False Negative 복구:
            # LLM Verifier가 is_relevant=false로 내려도, 코드레벨 본문 앵커가 충분하면
            # 보수적으로 작품 토론으로 복구한다.
            # (커뮤니티 단문 반응글: 제목 약칭 + 짧은 감정 본문 패턴 대응)
            if not verification.get("is_relevant"):
                recovered = self._recover_false_negative_with_code_anchor(
                    post=post,
                    comments=comments,
                    gatekeeper_result=gatekeeper_result,
                    decoder_result=decoder_result,
                    verification=verification,
                    result=result,
                    ctx=ctx,
                )
                if recovered:
                    verification = result.get("verification_result", verification)
                    novel_id = verification.get("novel_identity") or {}
                    # 🆕 rescue된 결과를 LLM에 재해석 요청:
                    # 코드레벨 rescue는 is_relevant/title만 세팅하므로
                    # discussion_type, summary 등을 LLM이 재생성하도록 한다.
                    self._llm_reinterpret_rescue(
                        post=post,
                        comments=comments,
                        verification=verification,
                        novel_id=novel_id,
                    )

            if not verification.get("is_relevant"):
                bootstrap_novel_id = self._build_relation_bootstrap_novel_id(
                    post,
                    comments,
                    decoder_result,
                    verification,
                    ctx,
                    verification_search=verification_search,
                )
                if bootstrap_novel_id:
                    verification["novel_identity"] = bootstrap_novel_id
                    relation = self._call_relation_judge(
                        post,
                        comments,
                        gatekeeper_result,
                        decoder_result,
                        verification,
                        bootstrap_novel_id,
                        ctx=ctx,
                        verification_search=verification_search,
                    )
                    if relation:
                        print(
                            f"[{_ts()}][{self.emoji}] 🧭 relation judge bootstrap: "
                            f"title={bootstrap_novel_id.get('official_novel_title')}, "
                            f"type={relation.get('relation_type')}, "
                            f"target={relation.get('discussion_target')}, "
                            f"promotion={relation.get('promotion_decision')}, "
                            f"conf={relation.get('confidence')}",
                            file=sys.stderr,
                        )
                        self._apply_relation_judgment(relation, verification, bootstrap_novel_id)
                        novel_id = verification.get("novel_identity") or bootstrap_novel_id
            
            # 🔥 LLM 제목 환각 교정: 검색 결과/Decoder best_match와 대조
            if novel_id and ctx:
                llm_title = novel_id.get("official_novel_title") or novel_id.get("official_title")
                if llm_title:
                    _title_norm_v = re.sub(r"[^\w가-힣]", "", str(llm_title or "")).lower()
                    _post_title_norm_v = re.sub(r"[^\w가-힣]", "", str(post.get("title", "") or "")).lower()
                    _novel_url_v = str(novel_id.get("heretic_url") or "").strip()
                    _relation_v = verification.get("relation_judgment") or {}
                    _relation_promotion_v = str(_relation_v.get("promotion_decision") or "").strip().lower()
                    if _relation_promotion_v in {"promote", "accept", "keep"}:
                        _relation_promotion_v = "allow"
                    _skip_title_correction = bool(
                        _title_norm_v
                        and _title_norm_v in _post_title_norm_v
                        and self._is_novel_detail_url(_novel_url_v)
                        and _relation_promotion_v in {"", "allow", "hold"}
                    )
                    if _skip_title_correction:
                        print(
                            f"[{_ts()}][{self.emoji}] 🛡️ 제목 교정 스킵: "
                            f"post title exact support + official detail url "
                            f"(title='{llm_title}', url='{_novel_url_v}')",
                            file=sys.stderr,
                        )
                        corrected = llm_title
                    else:
                        all_search = (ctx.search_results or []) + (verification_search or [])
                        corrected = self._correct_title_from_evidence(llm_title, decoder_result, all_search)
                    if corrected != llm_title:
                        print(f"[{_ts()}][{self.emoji}] ⚠️ 제목 교정: LLM='{llm_title}' → '{corrected}'", file=sys.stderr)
                        if novel_id.get("official_novel_title"):
                            novel_id["official_novel_title"] = corrected or None
                        if novel_id.get("official_title"):
                            novel_id["official_title"] = corrected or None
            
            # 🚨 게시글 제목 도용 방지 (P0-4 선제 방어)
            # Verifier가 게시글 제목을 그대로 official_novel_title에 넣는 경우 차단
            verified_title = (novel_id.get("official_novel_title") or
                              novel_id.get("official_title")) if novel_id else None
            if verified_title and self._is_platform_branding_title(verified_title):
                print(
                    f"[{_ts()}][{self.emoji}] 🧹 플랫폼 슬로건 제목 제거: '{verified_title}'",
                    file=sys.stderr,
                )
                novel_id["official_novel_title"] = None
                if "official_title" in novel_id:
                    novel_id["official_title"] = None
                novel_id["confidence"] = "Low"
                verification["is_relevant"] = False
                verification["is_novel_discussion"] = False
                existing_rej = str(verification.get("rejection_reason") or "").strip()
                rej = "플랫폼 슬로건/브랜딩 문구만 확인됨(예: 웹소설로 꿈꾸는 세상). 작품명 증거 부족."
                verification["rejection_reason"] = f"{existing_rej} | {rej}".strip(" |")
                verified_title = None
            
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
                    post_title_norm = re.sub(r"[^0-9A-Za-z가-힣]", "", str(post.get("title", "") or "").lower())
                    verified_title_norm = re.sub(r"[^0-9A-Za-z가-힣]", "", str(verified_title or "").lower())
                    heretic_url_now = str(novel_id.get("heretic_url") or "").strip() if isinstance(novel_id, dict) else ""
                    strong_exact_title_support = bool(
                        verified_title_norm
                        and post_title_norm
                        and verified_title_norm in post_title_norm
                        and self._is_novel_detail_url(heretic_url_now)
                    )
                    # Verifier 제목에 차단된 아키타입 용어가 포함되어 있는지 확인
                    title_norm = verified_title.replace(" ", "")
                    for arch_term in blocked_archetypes:
                        if strong_exact_title_support:
                            break
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

            verified_title = (novel_id.get("official_novel_title") or
                              novel_id.get("official_title")) if novel_id else None
            if verified_title:
                all_search_for_char_guard = (ctx.search_results or []) + (verification_search or []) if ctx else (verification_search or [])
                if self._should_block_character_like_title(
                    verified_title,
                    post,
                    comments,
                    gatekeeper_result or {},
                    decoder_result or {},
                    verification or {},
                    all_search_for_char_guard,
                    ctx,
                ):
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ 캐릭터명-제목 충돌 차단: "
                        f"'{verified_title}' → official_title=null",
                        file=sys.stderr,
                    )
                    novel_id["official_novel_title"] = None
                    if "official_title" in novel_id:
                        novel_id["official_title"] = None
                    novel_id["confidence"] = "Low"
                    counter_args = verification.get("counter_arguments")
                    if not isinstance(counter_args, list):
                        counter_args = []
                        verification["counter_arguments"] = counter_args
                    counter_args.append({
                        "issue": "character_title_collision",
                        "severity": "major",
                        "action": "nullify_title",
                        "explanation": (
                            f"'{verified_title}'은(는) short title + 캐릭터 언급 충돌 패턴으로 "
                            "작품 제목 오인 가능성이 높음."
                        ),
                    })
                    verified_title = None
            
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

            # 🛡️ author_new_work/title_unresolved 가드:
            # 제목의 핵심 앵커가 "작가 + 신작"인데 Verifier가 작가명/대표작명을
            # official_title로 올리는 경로를 차단한다.
            verified_title_author_guard = (
                novel_id.get("official_novel_title") or novel_id.get("official_title")
            ) if novel_id else None
            if verified_title_author_guard:
                grounding = verification.get("grounding_check") or {}
                anchor_found = str(grounding.get("anchor_found") or "").strip().lower()
                if anchor_found == "author_mention" and self._is_author_new_work_post(post):
                    author_surfaces = self._collect_author_surfaces(decoder_result or {}, verification or {})
                    title_norm = self._norm_text(verified_title_author_guard)
                    author_match = any(self._norm_text(surface) == title_norm for surface in author_surfaces)
                    title_abbrev_mentioned, body_abbrev_mentioned, matched_alias = self._detect_decoder_alias_mention(
                        post,
                        comments or [],
                        verified_title_author_guard,
                        decoder_result or {},
                    )
                    post_title_text = str((post or {}).get("title") or "")
                    body_parts = []
                    for block in (post or {}).get("content_blocks", []) or []:
                        if isinstance(block, dict) and block.get("text"):
                            body_parts.append(str(block.get("text") or ""))
                        elif isinstance(block, str):
                            body_parts.append(block)
                    full_body = " ".join(body_parts + list(comments or []))
                    body_mentions_title = self._surface_in_text(full_body, verified_title_author_guard)
                    main_mentions_title = self._surface_in_text(
                        f"{post_title_text} {full_body}".strip(),
                        verified_title_author_guard,
                    )
                    has_official_title_support = False
                    if ctx:
                        all_search_author_guard = (ctx.search_results or []) + (verification_search or [])
                        has_official_title_support = self._has_exact_official_title_support(
                            verified_title_author_guard,
                            all_search_author_guard,
                            ctx,
                        )
                    # "[작가약칭] 신작 ..." 패턴은 대표작/최신작을 검색으로 역추론한 경우가 많다.
                    # 제목이나 제목 alias가 본문/댓글에 직접 없으면 official_title을 올리지 않는다.
                    if not main_mentions_title and not body_abbrev_mentioned:
                        print(
                            f"[{_ts()}][{self.emoji}] 🛡️ author_new_work 제목 미확정 보호: "
                            f"'{verified_title_author_guard}' → official_title=null "
                            f"(author_match={author_match}, alias={matched_alias or '-'}, "
                            f"official_support={has_official_title_support}, anchor={anchor_found})",
                            file=sys.stderr,
                        )
                        novel_id["official_novel_title"] = None
                        if "official_title" in novel_id:
                            novel_id["official_title"] = None
                        novel_id["confidence"] = "Low"
                        verification["author_info"] = verification.get("author_info") or {}
                        if isinstance(verification["author_info"], dict) and not verification["author_info"].get("detected_author"):
                            for surface in author_surfaces:
                                if self._norm_text(surface) != title_norm:
                                    verification["author_info"]["detected_author"] = surface
                                    break
                        unresolved = verification.get("unresolved_from_decoder")
                        if not isinstance(unresolved, list):
                            unresolved = []
                            verification["unresolved_from_decoder"] = unresolved
                        unresolved.append({
                            "term": verified_title_author_guard,
                            "verifier_interpretation": "author_new_work/title_unresolved",
                            "needs_search": True,
                        })
                        verified_title_author_guard = None

            # 🛡️ Decoder null + community_mention 시 confidence 하향
            # Decoder가 작품을 못 찾았는데 Verifier가 독자적으로 High 확신하면 위험
            # 단, Decoder가 에러로 null인 경우(NoneType 등)는 의도적 null이 아니므로 면제
            if novel_id and novel_id.get("evidence_type") == "community_mention":
                decoder_has_title = any(
                    t.get("best_match", {}).get("title")
                    for t in decoder_result.get("decoded_terms", [])
                )
                # Decoder 에러 여부 판별: notes에 에러 메시지 또는 decoded_terms 자체가 없음
                _decoder_notes = str(decoder_result.get("notes") or "")
                _decoder_errored = (
                    "Error" in _decoder_notes
                    or "NoneType" in _decoder_notes
                    or "Traceback" in _decoder_notes
                    or "object has no attribute" in _decoder_notes
                    or (not decoder_result.get("decoded_terms") and _decoder_notes)
                )
                if not decoder_has_title and novel_id.get("confidence") in ("High", "high"):
                    if _decoder_errored:
                        # Decoder 에러 시에는 다운그레이드하지 않음 — Verifier 판단 유지
                        print(
                            f"[{_ts()}][{self.emoji}] ⚠️ community_mention + Decoder 에러 → "
                            f"confidence 하향 면제 (Decoder notes='{_decoder_notes[:60]}')",
                            file=sys.stderr
                        )
                    else:
                        novel_id["confidence"] = "Low"
                        print(
                            f"[{_ts()}][{self.emoji}] 🛡️ community_mention + Decoder null → "
                            f"confidence 하향: High → Low",
                            file=sys.stderr
                        )

            # 🛡️ 아이디어 D: Verifier 제목이 검색 근거에 없는 경우 보정/무효화
            # 1) 검색 결과의 유사 제목으로 정규화 시도
            # 2) 그래도 부재면 환각 후보로 보고 신뢰도 하향 (조건부 title null)
            verified_title_d = (novel_id.get("official_novel_title")
                                or novel_id.get("official_title")) if novel_id else None
            if verified_title_d and ctx:
                import re as _re_d
                from difflib import SequenceMatcher as _Seq

                def _norm_title(s: str) -> str:
                    return _re_d.sub(r"[^\w가-힣]", "", str(s or "")).lower()

                def _search_title_candidates(items: List[Dict[str, Any]]) -> List[str]:
                    def _clean_candidate(raw_t: str) -> str:
                        t = str(raw_t or "").strip()
                        if not t:
                            return ""
                        # 커뮤니티 접미(- 사이트명 등) 제거
                        t = t.split(" - ")[0].strip()
                        # 제목 앞 태그 제거 ([추천], (스포) 등)
                        t = _re_d.sub(r"^\s*[\[(【].{1,12}[\])】]\s*", "", t).strip()
                        # 리뷰/후기/독후감/스포/추천 꼬리 제거
                        t = _re_d.sub(
                            r"\s*(?:리뷰|후기|독후감|감상(?:문)?|스포(?:일러)?|추천)\s*[.!?…]*\s*$",
                            "",
                            t,
                            flags=_re_d.IGNORECASE,
                        ).strip()
                        # 긴 문장형 헤드라인이면 첫 절만 사용
                        if len(t) >= 28 and _re_d.search(r"[,:;]", t):
                            head = _re_d.split(r"[,:;]", t, maxsplit=1)[0].strip()
                            if len(_norm_title(head)) >= 4:
                                t = head
                        return t

                    out: List[str] = []
                    seen: set[str] = set()
                    for it in items:
                        raw_t = str(it.get("title", "") or "").strip()
                        if not raw_t:
                            continue
                        cand = _clean_candidate(raw_t)
                        # 너무 짧거나 과도 일반명사는 제외
                        if len(cand) < 4:
                            continue
                        n = _norm_title(cand)
                        if not n or n in seen:
                            continue
                        seen.add(n)
                        out.append(cand)
                    return out

                all_search = (ctx.search_results or []) + (verification_search or [])
                title_norm = _norm_title(verified_title_d)
                decoder_has_title = any(
                    t.get("best_match", {}).get("title")
                    for t in decoder_result.get("decoded_terms", [])
                    if isinstance(t, dict)
                )
                decoder_title_match = any(
                    self._norm_text((t.get("best_match") or {}).get("title")) == title_norm
                    for t in decoder_result.get("decoded_terms", [])
                    if isinstance(t, dict)
                )
                title_in_search = False
                for sr in all_search:
                    sr_blob = _norm_title((sr.get("title", "") + " " + (sr.get("content", "") or sr.get("snippet", ""))))
                    if title_norm and title_norm in sr_blob:
                        title_in_search = True
                        break

                # 검색 제목 유사 후보로 보정
                if not title_in_search:
                    cands = _search_title_candidates(all_search)
                    best_ratio = 0.0
                    best_cand = ""
                    for c in cands:
                        rn = _norm_title(c)
                        if not rn:
                            continue
                        r = _Seq(None, title_norm, rn).ratio()
                        if r > best_ratio:
                            best_ratio = r
                            best_cand = c
                    if best_cand and best_ratio >= 0.72:
                        old_title = verified_title_d
                        novel_id["official_novel_title"] = best_cand
                        if "official_title" in novel_id:
                            novel_id["official_title"] = best_cand
                        verified_title_d = best_cand
                        title_norm = _norm_title(best_cand)
                        title_in_search = True
                        print(
                            f"[{_ts()}][{self.emoji}] 🔧 검색 유사제목 보정: "
                            f"'{old_title}' -> '{best_cand}' (ratio={best_ratio:.2f})",
                            file=sys.stderr,
                        )

                # 여전히 검색 근거가 없으면 환각 후보로 처리
                if not title_in_search:
                    old_conf = novel_id.get("confidence", "Low")
                    novel_id["confidence"] = "Low"
                    heretic_url_now = str(novel_id.get("heretic_url") or "").strip()
                    heretic_in_search = False
                    direct_title_tuple_support = self._has_direct_title_tuple_support(ctx, verified_title_d)
                    if heretic_url_now:
                        hu_norm = heretic_url_now.rstrip("/")
                        for sr in all_search:
                            sr_url = str(sr.get("url") or "").strip().rstrip("/")
                            if sr_url and sr_url == hu_norm:
                                heretic_in_search = True
                                break
                    should_nullify = (
                        (not decoder_has_title)
                        or (not decoder_title_match)
                        or novel_id.get("evidence_type") == "community_mention"
                        or (not self._is_novel_detail_url(heretic_url_now))
                        or (not heretic_in_search)
                    )
                    if direct_title_tuple_support:
                        should_nullify = False
                    if should_nullify:
                        novel_id["official_novel_title"] = None
                        if "official_title" in novel_id:
                            novel_id["official_title"] = None
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ 검색에 '{verified_title_d}' 부재 → "
                        f"환각 의심, confidence: {old_conf} → Low"
                        + (", title=null" if should_nullify else "")
                        + (" (direct OCR/VLM title tuple support)" if direct_title_tuple_support else ""),
                        file=sys.stderr,
                    )
                    counter_args = verification.get("counter_arguments")
                    if not isinstance(counter_args, list):
                        counter_args = []
                        verification["counter_arguments"] = counter_args
                    counter_args.append({
                        "issue": "search_absent_verified_title",
                        "severity": "critical" if should_nullify else "major",
                        "action": "nullify_title" if should_nullify else "downgrade_confidence",
                        "explanation": (
                            f"Verifier 제목 '{verified_title_d}'이(가) 검색 근거에 직접 등장하지 않아 "
                            + ("다만 direct OCR/VLM title tuple support가 있어 제목 nullify는 보류함." if direct_title_tuple_support else "독자 추정/환각 가능성이 높음.")
                        ),
                    })

            # 🛡️ Phase40: 소설 플랫폼 미출현 + 커뮤니티 전용 제목 필터
            # 검색에서 발견됐더라도, 소설 플랫폼(novelpia/munpia/series.naver 등)에 없고
            # 커뮤니티 게시글(DC갤/아카라이브/에펨코리아)에서만 등장하는 제목은
            # 밈/캐릭터 그룹명일 가능성이 높음 → confidence Low + Decoder null이면 title null
            import re  # Phase40 블록에서 re.sub 사용
            _cur_title = (novel_id.get("official_novel_title")
                          or novel_id.get("official_title")) if novel_id else None
            if _cur_title and ctx and verification.get("is_relevant"):
                _all_search_p40 = (ctx.search_results or []) + (verification_search or [])
                _platform_domains = (
                    "novelpia.com", "munpia.com", "series.naver.com",
                    "page.kakao.com", "joara.com", "ridibooks.com",
                    "namu.wiki",  # 나무위키는 작품 정보 페이지일 수 있으므로 허용
                )
                _community_domains = (
                    "dcinside.com", "arca.live", "fmkorea.com",
                    "ruliweb.com", "theqoo.net", "instiz.net",
                )
                _title_norm_p40 = re.sub(r"[^\w가-힣]", "", _cur_title).lower()
                _found_on_platform = False
                _found_on_community_only = False
                _title_mention_count = 0

                for sr in _all_search_p40:
                    sr_url = str(sr.get("url", ""))
                    sr_blob = re.sub(r"[^\w가-힣]", "", 
                        (sr.get("title", "") + " " + (sr.get("content", "") or sr.get("snippet", "")))).lower()
                    if _title_norm_p40 and _title_norm_p40 in sr_blob:
                        _title_mention_count += 1
                        if any(d in sr_url for d in _platform_domains):
                            _found_on_platform = True
                        elif any(d in sr_url for d in _community_domains):
                            _found_on_community_only = True

                if _title_mention_count > 0 and not _found_on_platform and _found_on_community_only:
                    # 커뮤니티에서만 발견됨 — 소설이 아닌 밈/캐릭터 그룹명 가능성
                    _decoder_has_this = any(
                        _title_norm_p40 == re.sub(r"[^\w가-힣]", "", 
                            str((t.get("best_match") or {}).get("title", ""))).lower()
                        for t in decoder_result.get("decoded_terms", [])
                        if isinstance(t, dict)
                    )
                    novel_id["confidence"] = "Low"
                    if not _decoder_has_this:
                        # Decoder도 이 제목을 모름 → title null
                        novel_id["official_novel_title"] = None
                        if "official_title" in novel_id:
                            novel_id["official_title"] = None
                        print(
                            f"[{_ts()}][{self.emoji}] 🛡️ Phase40 커뮤니티전용 제목 차단: "
                            f"'{_cur_title}' → 소설 플랫폼 미출현, 커뮤니티에서만 발견 "
                            f"(mentions={_title_mention_count}), Decoder도 미확인 → title=null",
                            file=sys.stderr,
                        )
                    else:
                        print(
                            f"[{_ts()}][{self.emoji}] ⚠️ Phase40 커뮤니티전용 제목 경고: "
                            f"'{_cur_title}' → 소설 플랫폼 미출현 → confidence=Low",
                            file=sys.stderr,
                        )

            # 제안 2: Verifier의 신뢰도를 ctx에 저장
            if ctx:
                confidence_str = novel_id.get("confidence", "low")
                confidence_map = {"high": 0.95, "medium": 0.7, "low": 0.4}
                ctx.expert_confidence["verifier"] = confidence_map.get(confidence_str, 0.5)
            
            # ━━ 개선: evidence_type 3분류 + candidate evidence bucket + source trust ━━
            # evidence_type을 post_span / search_snippet / official_url로 분류
            # 🆕 FIX: 모든 후보 제목에 대해 독립적으로 증거를 매칭/등록 (증거 편향 등록 방지)
            if ctx and verification.get("is_relevant") and novel_id:
                verified_ev_title = (
                    novel_id.get("official_novel_title")
                    or novel_id.get("official_title")
                )
                grounding_ev = verification.get("grounding_check", {})
                anchor_ev = grounding_ev.get("anchor_found", "none")
                
                # 🆕 전체 후보 제목 수집 (Verifier 선택 + suspected_titles + Decoder 후보)
                _all_candidate_titles: set[str] = set()
                if verified_ev_title:
                    _all_candidate_titles.add(verified_ev_title)
                for _st in (ctx.suspected_titles or []):
                    _st_t = _st.get("title") if isinstance(_st, dict) else None
                    if _st_t and isinstance(_st_t, str) and _st_t.strip():
                        _all_candidate_titles.add(_st_t.strip())
                _dec_out = ctx.expert_outputs.get("decoder") if hasattr(ctx, "expert_outputs") else None
                if isinstance(_dec_out, dict):
                    for _dt in (_dec_out.get("decoded_terms") or []):
                        if not isinstance(_dt, dict) or _dt.get("is_author_name"):
                            continue
                        _bm = _dt.get("best_match") or {}
                        _bm_t = _bm.get("title")
                        if _bm_t and isinstance(_bm_t, str) and _bm_t.strip():
                            _all_candidate_titles.add(_bm_t.strip())
                        for _cand in (_dt.get("candidates") or []):
                            if not isinstance(_cand, dict):
                                continue
                            _cand_t = _cand.get("official_novel_title")
                            if _cand_t and isinstance(_cand_t, str) and _cand_t.strip():
                                _all_candidate_titles.add(_cand_t.strip())

                # heretic_url은 바깥 스코프에서도 참조하므로 미리 초기화
                h_url = novel_id.get("heretic_url") if novel_id else None

                if verified_ev_title:
                    # 1) 본문 증거 분류 (post_span) — Verifier 선택 제목에만 적용
                    if anchor_ev in ("title_mention", "character_mention", 
                                     "plot_mention", "author_mention", "character_title_link"):
                        ctx.add_evidence_for_candidate(verified_ev_title, "post_span", {
                            "type": anchor_ev,
                            "source": "verifier_grounding",
                            "grounded": grounding_ev.get("decoder_grounded", False),
                        })
                    
                    # heretic_url이 있으면 해당 제목에 official_url로 등록
                    h_url_trust = ctx.score_source_trust(h_url) if h_url else 0.0
                    if h_url and self._is_official_detail_evidence_url(h_url, h_url_trust):
                        ctx.add_evidence_for_candidate(verified_ev_title, "official_url", {
                            "url": h_url,
                            "trust_score": h_url_trust,
                        })
                
                # 2) 🆕 검색 증거: 모든 후보 제목에 대해 독립적으로 매칭
                all_search_ev = (ctx.search_results or []) + (verification_search or [])
                for _cand_title in _all_candidate_titles:
                    _cand_norm = _cand_title.replace(" ", "")
                    _cand_short = self._is_short_single_token_title(_cand_title)
                    for sr in all_search_ev:
                        sr_text = (sr.get("title", "") + " " + (sr.get("content", "") or sr.get("snippet", "")))
                        sr_url = sr.get("url", "")
                        sr_match = False
                        if _cand_short:
                            if self._is_novel_detail_url(str(sr_url or "")) and self._contains_as_token(str(sr.get("title", "") or ""), _cand_title):
                                sr_match = True
                        else:
                            if _cand_norm in sr_text.replace(" ", ""):
                                sr_match = True

                        if not sr_match:
                            continue

                        trust = ctx.score_source_trust(sr_url)
                        ctx.add_evidence_for_candidate(_cand_title, "search_snippet", {
                            "url": sr_url,
                            "snippet": sr_text[:200],
                            "trust_score": trust,
                        })
                        # 소스 신뢰도 기록
                        if sr_url:
                            ctx.source_trust_scores[sr_url] = trust
                        # 3) 공식 URL 분류 (official_url)
                        if self._is_official_detail_evidence_url(sr_url, trust):
                            ctx.add_evidence_for_candidate(_cand_title, "official_url", {
                                "url": sr_url,
                                "title": str(sr.get("title") or ""),
                                "trust_score": trust,
                            })
                
                if _all_candidate_titles and len(_all_candidate_titles) > 1:
                    print(
                        f"[{_ts()}][{self.emoji}] 📊 전체 후보 증거 등록: {len(_all_candidate_titles)}건 "
                        f"({', '.join(repr(t) for t in sorted(_all_candidate_titles)[:4])}...)",
                        file=sys.stderr,
                    )
                    
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

                verified_title_bc = (
                    novel_id.get("official_novel_title")
                    or novel_id.get("official_title")
                )
                if verified_title_bc:
                    title_abbrev_mentioned, body_abbrev_mentioned, matched_alias = (
                        self._detect_verified_alias_grounding(
                            post,
                            comments,
                            verified_title_bc,
                            decoder_result,
                            verification,
                        )
                    )
                    if title_abbrev_mentioned:
                        grounding["title_abbrev_mentioned"] = True
                    if body_abbrev_mentioned:
                        grounding["body_abbrev_mentioned"] = True
                    if matched_alias:
                        grounding["matched_alias"] = matched_alias
                    if title_abbrev_mentioned and anchor_found in ("none", "search_only", ""):
                        grounding["anchor_found"] = (
                            "body_abbrev_mention" if body_abbrev_mentioned else "title_abbrev_mention"
                        )
                    if (not grounding.get("decoder_grounded", True)) and title_abbrev_mentioned:
                        grounding["grounding_issue"] = (
                            "본문/댓글의 축약어를 통해 작품 언급은 확인되나, 정식 제목/강한 직접 근거는 약함."
                            if body_abbrev_mentioned
                            else "제목의 축약어를 통해 작품 언급은 확인되나, 본문/댓글의 직접 근거는 약함."
                        )
                    verification["grounding_check"] = grounding

                relation_title = (
                    novel_id.get("official_novel_title")
                    or novel_id.get("official_title")
                )
                if relation_title and self._should_run_relation_judge(
                    post,
                    comments,
                    gatekeeper_result,
                    decoder_result,
                    verification,
                    novel_id,
                    ctx=ctx,
                ):
                    relation = self._call_relation_judge(
                        post,
                        comments,
                        gatekeeper_result,
                        decoder_result,
                        verification,
                        novel_id,
                        ctx=ctx,
                        verification_search=verification_search,
                    )
                    if relation:
                        print(
                            f"[{_ts()}][{self.emoji}] 🧭 relation judge: "
                            f"type={relation.get('relation_type')}, "
                            f"target={relation.get('discussion_target')}, "
                            f"promotion={relation.get('promotion_decision')}, "
                            f"conf={relation.get('confidence')}",
                            file=sys.stderr,
                        )
                        self._apply_relation_judgment(relation, verification, novel_id)
            
            # 제안 4: 불확실성 요인 수집
            if ctx and verification.get("is_relevant"):
                # 증거가 약한 경우 불확실성 누적
                evidence_type = novel_id.get("evidence_type", "")
                if evidence_type == "community_only":
                    ctx.uncertainty_sources.append("Verifier: 공식 플랫폼 증거 없음 (커뮤니티 포스트만)")
                
                grounding_check = verification.get("grounding_check", {})
                if not grounding_check.get("decoder_grounded", True):
                    if grounding_check.get("title_abbrev_mentioned"):
                        if grounding_check.get("body_abbrev_mentioned"):
                            ctx.uncertainty_sources.append(
                                "Verifier: 본문/댓글의 축약어를 통해 작품 언급은 확인되나, 정식 제목/강한 직접 근거는 약함"
                            )
                        else:
                            ctx.uncertainty_sources.append(
                                "Verifier: 제목의 축약어를 통해 작품 언급은 확인되나, 본문 직접 근거는 약함"
                            )
                    else:
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
            import traceback as _tb_err
            print(f"[{_ts()}][{self.emoji}] {self.name} 오류 ({elapsed:.1f}s): {e}", file=sys.stderr)
            _tb_err.print_exc(file=sys.stderr)
            return self._fallback_result(gatekeeper_result, decoder_result, str(e))
    
    def _correct_title_from_evidence(self, llm_title: str, decoder_result: Dict[str, Any], search_results: List[Dict[str, Any]]) -> str:
        """
        🔥 LLM이 생성한 제목을 Decoder best_match + 검색 결과와 대조하여 교정
        예: '죽었다 깨어나도 수선' (LLM 환각) → '죽었다 깨어도 수선' (검색 결과 정확)
        """
        llm_is_branding = self._is_platform_branding_title(llm_title)

        # 플랫폼 슬로건이면 Decoder에서 비-브랜딩 제목이 확인된 경우에만 대체, 아니면 제거
        if llm_is_branding:
            for term in decoder_result.get("decoded_terms", []):
                best = term.get("best_match", {})
                decoder_title = str(best.get("title") or "").strip()
                if decoder_title and (not self._is_platform_branding_title(decoder_title)):
                    return decoder_title
            return ""

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
            if not self._is_novel_detail_url(url):
                continue
            sr_title = sr.get("title", "")
            if self._is_platform_branding_title(sr_title):
                continue
            # "웹소설로 꿈꾸는 세상! - 죽었다 깨어도 수선" → "죽었다 깨어도 수선"
            if " - " in sr_title:
                sr_title = sr_title.split(" - ")[-1].strip()
            import re
            sr_title = re.sub(r'\s*\(r\d+\s*판\)$', '', sr_title).strip()
            if self._is_platform_branding_title(sr_title):
                continue
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
        
        # 🔧 꺾쇠 패턴 면제: 게시글 제목에 <작품명>이 명시된 경우 도용이 아님
        import re as _re_vguard
        _bracket_m = _re_vguard.search(r"[<＜《<](.+?)[>＞》>]", post_title)
        if _bracket_m:
            _bt_norm = _bracket_m.group(1).replace(" ", "").lower()
            _vt_norm = verified_title.replace(" ", "").lower()
            if (
                len(_bt_norm) >= 3
                and (
                    _bt_norm in _vt_norm
                    or _vt_norm in _bt_norm
                    or _re_vguard.sub(r"[^가-힣a-z0-9]", "", _bt_norm)
                       == _re_vguard.sub(r"[^가-힣a-z0-9]", "", _vt_norm)
                )
            ):
                print(
                    f"[{_ts()}][{self.emoji}] ✅ 꺾쇠 패턴 면제: "
                    f"post_title '{post_title}' 에 <{_bracket_m.group(1)}> 명시 → "
                    f"'{verified_title}' 도용 차단 스킵",
                    file=sys.stderr,
                )
                return
        
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
                    st["confidence"] = max(0.3, self._confidence_to_unit(st.get("confidence", 0.5), default=0.5) - 0.1)
                st["verified_by"] = "verifier"
                updated.append(st)
            elif is_relevant and confidence in ("high", "medium"):
                # 다른 작품이 확인됨: 이 후보는 유지하되 confidence 낮춤
                st["confidence"] = max(0.2, self._confidence_to_unit(st.get("confidence", 0.5), default=0.5) - 0.2)
                updated.append(st)
            else:
                # 관련 없음으로 판정: confidence 낮춤 (제거하지는 않음)
                st["confidence"] = max(0.1, self._confidence_to_unit(st.get("confidence", 0.5), default=0.5) - 0.3)
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
                    ranked_updated = sorted(
                        updated,
                        key=lambda x: x.get("confidence", 0),
                        reverse=True,
                    )
                    record_candidate_stage_receipt(
                        ctx,
                        producer="verifier",
                        stage="ranked_update",
                        observed_sources=ranked_updated,
                    )
                    ctx.suspected_titles = ranked_updated[:5]
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
                    # 🔧 Phase40: genre_discussion 경고가 있으면 더 강하게 억제
                    _discourse_warn_dn = str(getattr(ctx, "discourse_warning", "") or "").lower()
                    _has_genre_warn_dn = any(
                        tok in _discourse_warn_dn
                        for tok in ("genre_discussion", "discuss_genre")
                    )
                    if _has_genre_warn_dn:
                        new_conf = min(new_conf, 0.15)  # genre_discussion + Decoder null → 거의 차단
                        new_status = "genre_suppressed"
                        print(
                            f"[{_ts()}][{self.emoji}] 🛡️ Decoder-null+genre 가드: "
                            f"Decoder=null + discourse_warning=genre_discussion "
                            f"→ Verifier 독자 추가 '{verified_title}' conf={new_conf} (강력 억제)",
                            file=sys.stderr
                        )
                    else:
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
        
        ranked_updated = sorted(
            updated,
            key=lambda x: x.get("confidence", 0),
            reverse=True,
        )
        record_candidate_stage_receipt(
            ctx,
            producer="verifier",
            stage="ranked_update",
            observed_sources=ranked_updated,
        )
        ctx.suspected_titles = ranked_updated[:5]

        # 🆕 FIX-5: 댓글 질문→확인 패턴 감지 ("무한회귀?" + "ㅇㅇ" → 작품명 확인 신호)
        self._boost_comment_confirmed_title(ctx)

        print(f"[{_ts()}][{self.emoji}] 📋 suspected_titles 업데이트: {len(ctx.suspected_titles)}건", file=sys.stderr)
        for i, st in enumerate(ctx.suspected_titles, 1):
            title = st.get('title', 'N/A')
            conf = st.get('confidence', 'N/A')
            source = st.get('source_expert', 'unknown')
            print(f"[{_ts()}][{self.emoji}]    [{i}] {title} (conf={conf}, from={source})", file=sys.stderr)
    
    @staticmethod
    def _detect_comment_confirmation_pattern(comments: List[str]) -> Optional[str]:
        """
        🆕 FIX-5: 댓글에서 '제목?' + 'ㅇㅇ'/'응'/'맞아' 확인 패턴 탐지.
        예: "무한회귀?" → "ㅇㅇ" = 작품 제목 "무한회귀" 확인
        Returns: 확인된 제목 문자열 또는 None
        """
        if not comments or not isinstance(comments, list):
            return None
        import re
        _confirm_tokens = {
            "ㅇㅇ", "ㅇ", "응", "어", "맞아", "ㅇㅇㅇ", "ㄹㅇ", "ㅇㅇㅇㅇ",
            "맞음", "그거", "그거맞음", "ㅇㅇ맞아", "yes", "ㅇㅇ맞음",
        }
        for i, comment in enumerate(comments):
            if not isinstance(comment, str):
                continue
            c = comment.strip()
            # "제목?" 또는 "제목" 형태 (2~30자, 한글/영숫자)
            q_match = re.match(r"^([가-힣A-Za-z0-9\s]{2,30})\s*\??$", c)
            if q_match:
                candidate_title = q_match.group(1).strip()
                # 다음 댓글이 확인 토큰인지 체크
                for j in range(i + 1, min(i + 3, len(comments))):
                    next_c = comments[j].strip() if isinstance(comments[j], str) else ""
                    # @ㅇㅇ 등 인용 접두사 제거
                    next_c = re.sub(r"^@\S+\s*", "", next_c).strip()
                    next_norm = re.sub(r"\s+", "", next_c).lower()
                    if next_norm in _confirm_tokens:
                        return candidate_title
        return None

    def _boost_comment_confirmed_title(self, ctx: "ConversationContext") -> None:
        """댓글 확인 패턴으로 감지된 제목을 suspected_titles에서 boost."""
        confirmed = self._detect_comment_confirmation_pattern(ctx.comments or [])
        if not confirmed:
            return
        
        import re
        def _norm(s: str) -> str:
            return re.sub(r"[^\uac00-\ud7a3A-Za-z0-9]", "", str(s or "")).lower()
        
        confirmed_norm = _norm(confirmed)
        if not confirmed_norm or len(confirmed_norm) < 2:
            return
        
        boosted = False
        for st in (ctx.suspected_titles or []):
            st_title = st.get("title", "")
            st_norm = _norm(st_title)
            # 정규화 매칭 또는 부분 포함 매칭
            if confirmed_norm in st_norm or st_norm in confirmed_norm:
                old_conf = self._confidence_to_unit(st.get("confidence", 0.5), default=0.5)
                st["confidence"] = max(old_conf, 0.85)
                st["comment_confirmed"] = True
                boosted = True
                print(
                    f"[{_ts()}][{self.emoji}] 💬 댓글 확인 패턴 감지: "
                    f"'{confirmed}' → '{st_title}' (conf: {old_conf:.2f}→{st['confidence']:.2f})",
                    file=sys.stderr,
                )
        
        # 기존 후보에 없으면 새로 추가
        if not boosted:
            # 검색 결과에서 정식 제목 매칭 시도
            for sr in (ctx.search_results or []):
                if not isinstance(sr, dict):
                    continue
                sr_text = _norm(sr.get("title", "") + " " + (sr.get("content", "") or ""))
                if confirmed_norm in sr_text:
                    ctx.suspected_titles.append({
                        "title": confirmed,
                        "confidence": 0.8,
                        "source_expert": "comment_confirmation",
                        "status": "comment_confirmed",
                        "comment_confirmed": True,
                    })
                    print(
                        f"[{_ts()}][{self.emoji}] 💬 댓글 확인 패턴: 새 후보 추가 "
                        f"'{confirmed}' (검색 매칭 확인)",
                        file=sys.stderr,
                    )
                    break
        
        # 재정렬
        ranked_boosted = sorted(
            ctx.suspected_titles,
            key=lambda x: x.get("confidence", 0),
            reverse=True,
        )
        record_candidate_stage_receipt(
            ctx,
            producer="verifier",
            stage="comment_boost",
            observed_sources=ranked_boosted,
        )
        ctx.suspected_titles = ranked_boosted[:5]
    
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
            # 📌 candidates에서 플랫폼 URL/출처 정보를 포함 (Verifier가 증거를 볼 수 있게)
            _platform_sources = []
            for cand in term.get("candidates", []):
                if not isinstance(cand, dict):
                    continue
                cand_url = cand.get("url", "")
                cand_platform = cand.get("platform", "")
                if cand_url and any(d in cand_url for d in (
                    "novelpia.com", "munpia.com", "series.naver.com",
                    "page.kakao.com", "joara.com", "ridibooks.com",
                )):
                    _platform_sources.append({
                        "url": cand_url,
                        "platform": cand_platform,
                        "title": cand.get("official_novel_title", ""),
                    })
            if _platform_sources:
                entry["platform_evidence"] = _platform_sources[:2]
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
    
    def _build_post_json(
        self,
        post: Dict[str, Any],
        comments: List[str],
        *,
        compact: bool = False,
    ) -> Dict[str, Any]:
        """Build simplified post JSON with bounded body/comment sizes."""
        content_texts = []
        for block in post.get("content_blocks", []):
            if isinstance(block, dict) and block.get("text"):
                content_texts.append(block["text"])
            elif isinstance(block, str):
                content_texts.append(block)
        content_texts = [str(t).strip() for t in content_texts if str(t).strip()]
        content_total_chars = sum(len(t) for t in content_texts)

        if compact:
            max_total_content_chars = self._env_int(
                "LLM_VERIFIER_COMPACT_POST_CHARS", 1800, minimum=400, maximum=6000
            )
            max_block_chars = self._env_int(
                "LLM_VERIFIER_COMPACT_POST_BLOCK_CHARS", 700, minimum=120, maximum=2000
            )
            max_comments = self._env_int(
                "LLM_VERIFIER_COMPACT_COMMENT_COUNT", 4, minimum=0, maximum=10
            )
            max_comment_chars = self._env_int(
                "LLM_VERIFIER_COMPACT_COMMENT_CHARS", 160, minimum=40, maximum=800
            )
        else:
            max_total_content_chars = self._env_int(
                "LLM_VERIFIER_POST_CHARS", 3600, minimum=800, maximum=12000
            )
            max_block_chars = self._env_int(
                "LLM_VERIFIER_POST_BLOCK_CHARS", 1200, minimum=200, maximum=4000
            )
            max_comments = self._env_int(
                "LLM_VERIFIER_COMMENT_COUNT", 8, minimum=0, maximum=15
            )
            max_comment_chars = self._env_int(
                "LLM_VERIFIER_COMMENT_CHARS", 260, minimum=60, maximum=1200
            )

        clipped_content: List[str] = []
        remaining = max_total_content_chars
        content_truncated = False
        for text in content_texts:
            if remaining <= 80:
                content_truncated = True
                break
            clipped = self._clip_text(text, min(max_block_chars, remaining))
            if clipped:
                clipped_content.append(clipped)
                remaining -= len(clipped)
                if len(clipped) < len(text):
                    content_truncated = True
        if len(clipped_content) < len(content_texts):
            content_truncated = True

        clipped_comments = []
        comments_truncated = len(comments or []) > max_comments
        for comment in (comments or [])[:max_comments]:
            c = self._clip_text(comment, max_comment_chars, marker=" ... ")
            if c:
                clipped_comments.append(c)
                if len(str(comment or "").strip()) > len(c):
                    comments_truncated = True

        title_text = str(post.get("title", "") or "")
        title_body_joined = title_text
        if clipped_content:
            title_body_joined = f"{title_text} {clipped_content[0]}".strip()
        
        result = {
            "post_id": post.get("post_id"),
            "gallery_id": post.get("gallery_id", ""),
            "title": title_text,
            "post_author": post.get("post_author") or post.get("author", ""),
            "author": post.get("author", ""),
            "content": clipped_content,
            "title_body_joined_preview": self._clip_text(
                title_body_joined,
                320 if compact else 520,
                marker=" ... ",
            ),
            "content_text_count": len(content_texts),
            "content_total_chars": content_total_chars,
            "has_content_text": content_total_chars > 0,
            "content_truncated": content_truncated,
            "comments": clipped_comments,
            "comments_truncated": comments_truncated,
        }
        comment_context = post.get("comment_context_lines") or []
        if comment_context:
            result["comment_context"] = comment_context[:max_comments]
        comment_dialogue = post.get("comment_dialogue_context_lines") or []
        if comment_dialogue:
            result["comment_dialogue_context"] = comment_dialogue[:max_comments]
        return result
    
    def _call_llm(
        self,
        user_prompt: str,
        *,
        gatekeeper_result: Optional[Dict[str, Any]] = None,
        decoder_result: Optional[Dict[str, Any]] = None,
        ctx: Optional[Any] = None,
        compact_retry_prompt: Optional[str] = None,
        primary_compact_mode: bool = False,
    ) -> Dict[str, Any]:
        """Call LLM and retry once with a smaller prompt on truncation/empty output."""
        system_content = build_verifier_system_prompt(
            VERIFIER_SYSTEM,
            gatekeeper_result=gatekeeper_result,
            decoder_result=decoder_result,
            ctx=ctx,
        )
        messages = [{"role": "system", "content": system_content}]

        def _invoke(prompt: str, *, compact_mode: bool, tag: str) -> Dict[str, Any]:
            run_messages = messages + [{"role": "user", "content": prompt}]
            max_tokens = self._resolve_verifier_max_tokens(
                sum(len(m.get("content", "")) for m in run_messages),
                compact_mode=compact_mode,
            )
            if self.llm.print_timings:
                print(
                    f"[{_ts()}][{self.emoji}] {tag} max_tokens={max_tokens} "
                    f"(compact={compact_mode})",
                    file=sys.stderr,
                )
            response_text = self.llm._stream_chat_http(
                messages=run_messages,
                tag=tag,
                use_grammar=True,
                max_tokens=max_tokens,
            )
            finish_reason = str(getattr(self.llm, "last_finish_reason", "") or "").lower()
            if not str(response_text or "").strip():
                raise ValueError(f"empty verifier response (finish_reason={finish_reason or 'unknown'})")
            try:
                return self._parse_json_response(response_text)
            except ValueError:
                if finish_reason in {"length", "max_tokens"}:
                    raise ValueError(f"verifier truncated (finish_reason={finish_reason})")
                raise

        try:
            return _invoke(user_prompt, compact_mode=primary_compact_mode, tag="verifier")
        except ValueError as first_error:
            if not compact_retry_prompt:
                raise
            print(
                f"[{_ts()}][{self.emoji}] ⚠️ Verifier compact 재시도: {first_error}",
                file=sys.stderr,
            )
            return _invoke(compact_retry_prompt, compact_mode=True, tag="verifier_retry")
    
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
        best_url = None
        best_alias = None
        
        for term in decoder.get("decoded_terms", []):
            best = term.get("best_match", {})
            if best.get("title"):
                best_title = best["title"]
                best_confidence = "Low"  # Downgrade without verification
                best_url = best.get("url")
                best_alias = term.get("original")
                break
        
        is_noise = gatekeeper.get("is_noise", False)
        provisional_relevance = bool(best_title and not is_noise)
        provisional_novel_identity = None
        if best_title:
            provisional_novel_identity = {
                "official_title": best_title,
                "heretic_url": best_url,
                "confidence": best_confidence,
                "alias_or_mention": best_alias,
                "evidence_type": "verification_error_fallback",
            }
        
        # NOTE:
        # verifier 자체 실패와 "실제 비관련 판정"을 downstream이 구분할 수 있도록
        # verification_error 플래그와 임시 후보 정보를 함께 남긴다.
        return {
            "verification_result": {
                "is_relevant": False,  # 검증 실패 → False
                "is_novel_discussion": False,
                "novel_identity": provisional_novel_identity,
                "author_info": None,
                "rejection_reason": f"Verifier 검증 오류: {error}",
                "evidence_chain": [],
                "slang_insight": None,
                "inference": gatekeeper.get("inference"),
                "verification_error": True,
                "verification_error_stage": "verifier",
                "verification_error_message": error,
                "provisional_relevance": provisional_relevance,
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

    # ------------------------------------------------------------------
    # 🆕 rescue 결과 LLM 재해석
    # ------------------------------------------------------------------
    _RESCUE_REINTERPRET_PROMPT = """\
아래 게시글이 웹소설 "{title}"에 대한 토론인 것으로 코드 분석 결과 확인됐습니다.
이 정보를 바탕으로, 게시글의 discussion_type과 짧은 요약을 판정해 주세요.

=== 게시글 ===
제목: {post_title}
본문 (앞 500자): {body_preview}
댓글 (앞 3건): {comments_preview}

=== 판정 대상 소설 ===
제목: {title}
복구 근거: {recovery_note}

아래 JSON으로만 응답하세요:
{{
  "discussion_type": "review|recommendation|reaction|question|comparison|general_mention|news",
  "brief_summary": "string (50자 이내, 한국어)",
  "evidence_quality": "strong|moderate|weak"
}}
"""

    _RELATION_JUDGE_SYSTEM = (
        "당신은 웹소설 커뮤니티의 축약어/장르어/플랫폼 메타를 구분하는 판정기입니다. "
        "핵심 임무는 '이 표현이 특정 작품을 직접 지칭하는가'만 엄격히 판단하는 것입니다. "
        "장르 유사성, 줄거리 단어 겹침, 커뮤니티 반복 언급만으로는 작품 약칭으로 확정하지 마세요. "
        "불확실하면 hold/reject를 선택하고 JSON만 출력하세요."
    )

    _RELATION_JUDGE_PROMPT = """\
아래 게시글에서 후보 작품 "{candidate_title}"를 official_title로 승격해도 되는지 판정하세요.

## 게시글
{post_json}

## Gatekeeper 요약
{gatekeeper_json}

## Decoder 요약
{decoder_json}

## 현재 Verifier 상태
{verification_json}

## 문제 표현 / 후보 관계
- candidate_title: {candidate_title}
- observed_aliases: {alias_json}

## 검색 근거 요약
{search_summary_json}

## 관련 검색 근거
{search_json}

## 판정 규칙
1. 다음 중 하나가 있어야 specific_work + allow로 본다.
   - 게시글 안에 정식 제목이 직접 언급됨
   - 검색/본문에서 "X는 Y의 약칭/줄임말/통칭" 같은 명시 브리지 존재
   - 커뮤니티 약칭이더라도 단일 작품을 직접 가리킨다는 강한 명시 근거 존재
2. 다음 규칙을 반드시 지켜라.
   - community_post가 여러 개 있어도 explicit_alias_bridge_count가 0이면 specific_work로 단정하지 마라.
   - official_detail_count가 있어도 alias와 title이 줄거리 단어로 함께 등장할 뿐 명시 브리지가 없으면 thematic_overlap_only 또는 mixed_or_uncertain이다.
   - 단, 게시글 표면 alias가 있고 official_exact_title_count>=1 이며 support_channel_count>=2 로 여러 검색 경로가 같은 공식 작품에 수렴하면 specific_work는 검토할 수 있다. 이 경우 본문 직접 앵커가 약하면 promotion_decision은 allow보다 hold를 우선 검토하라.
   - 게시글 본문 직접 앵커가 없고 검색 근거가 community/listing 중심이면 discussion_target은 specific_work보다 mixed_or_uncertain / community_banter / genre_general 쪽을 우선 검토하라.
   - work_specific_nickname은 실제 별칭 근거가 있을 때만 쓰고, 장르 복합어/분위기어/서비스 카테고리어에는 쓰지 마라.
   - 무림맹/마교/혈교/정파/사파/천마/제자/맹주 같은 무협 세력·역할어, 또는 헌터/던전/마탑/아카데미 같은 장르어만 후보 제목과 겹치면 explicit_alias가 아니다.
   - 후보 제목의 비일반 고유 요소(캐릭터명, 독자적 제목 조각, 작가명, 회차/플롯)가 게시글/댓글에 없으면 genre_or_trope_label 또는 thematic_overlap_only로 보라.
   - review/arena/community page 제목은 작품 존재의 보조 단서일 수는 있어도, 그 제목 자체를 official_title 후보로 승격하는 직접 근거가 아니다.
3. 다음은 절대 allow가 아니다.
   - 장르/트로프/분위기 단어만 겹침
   - 플랫폼 카테고리/장르 목록/서비스 페이지
   - 커뮤니티에서 같은 단어가 반복될 뿐, 특정 작품을 직접 지칭한다는 명시 근거 없음
   - 줄거리 안에 비슷한 단어가 같이 나온다는 이유만으로 연결
4. 게시글의 실제 담론 대상도 함께 판정하라.
   - specific_work
   - genre_general
   - platform_meta
   - community_banter
   - mixed_or_uncertain
5. specific_work라도 제목 승격 근거가 부족하면 promotion_decision은 hold다.
6. genre_general / platform_meta / community_banter / mixed_or_uncertain 이면 promotion_decision은 reject 또는 hold여야 한다.
7. 커뮤니티 반복 사례만 있고 explicit alias bridge가 없으면 discussion_target은 specific_work보다 mixed_or_uncertain / community_banter / genre_general 쪽을 우선 검토하라.

OUTPUT JSON:
{{
  "relation_type": "exact_title" | "explicit_alias" | "work_specific_nickname" | "genre_or_trope_label" | "platform_or_category" | "community_slang_or_meta" | "thematic_overlap_only" | "unknown",
  "discussion_target": "specific_work" | "genre_general" | "platform_meta" | "community_banter" | "mixed_or_uncertain",
  "promotion_decision": "allow" | "hold" | "reject",
  "confidence": "high" | "medium" | "low",
  "reason": "string",
  "key_evidence": ["string"]
}}
"""

    def _llm_reinterpret_rescue(
        self,
        post: Dict[str, Any],
        comments: List[str],
        verification: Dict[str, Any],
        novel_id: Dict[str, Any],
    ) -> None:
        """
        코드레벨 rescue로 복구된 결과에 LLM 재해석을 적용.
        discussion_type, brief_summary를 LLM이 새로 생성한다.
        실패 시 기존 rescue 결과를 그대로 유지.
        """
        import sys, json, time
        title = novel_id.get("official_novel_title") or novel_id.get("official_title") or ""
        if not title:
            return

        post_title = str(post.get("title") or "")[:200]
        body_parts = []
        for block in (post.get("content_blocks") or []):
            if isinstance(block, dict):
                body_parts.append(str(block.get("text") or ""))
            elif isinstance(block, str):
                body_parts.append(block)
        body_text = " ".join(body_parts)[:500]
        comments_preview = " | ".join(c[:80] for c in (comments or [])[:3])
        recovery_note = str(verification.get("recovery_note") or "코드레벨 앵커 복구")[:200]

        prompt = self._RESCUE_REINTERPRET_PROMPT.format(
            title=title,
            post_title=post_title,
            body_preview=body_text or "(본문 없음)",
            comments_preview=comments_preview or "(댓글 없음)",
            recovery_note=recovery_note,
        )

        try:
            messages = [
                {"role": "system", "content": "당신은 웹소설 커뮤니티 게시글 분석 전문가입니다. JSON만 응답하세요."},
                {"role": "user", "content": prompt},
            ]
            raw = self.llm._stream_chat_http(
                messages=messages,
                tag="verifier_rescue_reinterpret",
                use_grammar=True,
            )
            parsed = parse_json_with_think_removal(raw)

            # discussion_type 반영
            dt = parsed.get("discussion_type")
            if dt and isinstance(dt, str):
                verification["discussion_type"] = dt

            # brief_summary 반영
            bs = parsed.get("brief_summary")
            if bs and isinstance(bs, str):
                verification["rescue_llm_summary"] = bs

            # evidence_quality → confidence 하향 보정
            eq = str(parsed.get("evidence_quality", "")).lower()
            if eq == "weak" and novel_id.get("confidence") in ("High", "Max"):
                novel_id["confidence"] = "Medium"
                novel_id["_rescue_llm_downgraded"] = True

            print(
                f"[{_ts()}][{self.emoji}] 🔄 Rescue LLM 재해석 완료: "
                f"type={dt}, quality={eq}, summary={str(bs)[:40]}",
                file=sys.stderr,
            )
        except Exception as e:
            # 실패 시 기존 rescue 결과 유지 (silent)
            print(
                f"[{_ts()}][{self.emoji}] ⚠️ Rescue LLM 재해석 실패 (기존 결과 유지): {e}",
                file=sys.stderr,
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
        
        # ─── Phase29: 순환참조 방지 ───
        # Decoder가 post_title에서 추출한 term을 body_check가 다시 post_title에서 찾으면
        # 증거 순환(title→decoder→body_check→title)이 발생한다.
        # 따라서 full_text에서 post_title을 제외하고 본문+댓글만으로 검증한다.
        body_and_comments = f"{post_body} {comments_text}"
        body_and_comments_norm = body_and_comments.lower().replace(" ", "")
        
        if not body_and_comments_norm:
            return False

        candidate_alias_terms: List[str] = []
        for term in (decoder_result or {}).get("decoded_terms", []):
            if not isinstance(term, dict):
                continue
            best = term.get("best_match") or {}
            best_title = best.get("title") or best.get("official_novel_title")
            if self._norm_text(best_title) != self._norm_text(title):
                continue
            original = str(term.get("original") or "").strip()
            if original:
                candidate_alias_terms.append(original)
        if self._is_generic_relation_only_mapping(title, post, comments, candidate_alias_terms):
            return False
        
        # 1) 정식 제목이 본문+댓글에 포함 (제목 제외)
        title_norm = title.lower().replace(" ", "")
        if title_norm in body_and_comments_norm:
            return True
        
        # 2) 정식 제목의 핵심 단어(2글자 이상)가 본문+댓글에 2개 이상 있는지
        body_and_comments_lower = body_and_comments.lower()
        title_words = [w for w in title.split() if len(w) >= 2]
        if title_words:
            word_hits = sum(
                1 for w in title_words
                if w.lower() in body_and_comments_lower
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
                # 원본 약어가 본문+댓글에 포함 → 약어로 작품 언급 중
                # Phase29: 제목 순환참조 방지를 위해 body_and_comments_norm 사용
                if orig_norm in body_and_comments_norm and len(orig_norm) >= 3:
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
                        kw in body_and_comments
                        for kw in work_context_keywords
                    )
                    if has_context:
                        return True

                    # 🆕 추가: 포스트 제목에 약어가 있고 본문에 이모티콘/감정 표현이 있으면 OK
                    # 단, short title이 조사와 결합된 인명 형태(예: 은영이/은영은)면
                    # 제목 증거로 단독 인정하지 않는다.
                    title_token = title.strip()
                    short_title = len(title_norm) <= 3 and len(title_token) <= 3
                    particle_suffixes = ("가", "이", "은", "는", "을", "를", "도", "만", "네", "다", "냐")
                    particle_collision = any(
                        f"{title_token}{sfx}" in body_and_comments
                        for sfx in particle_suffixes
                    ) if title_token else False

                    # Phase29: 약어가 post_title에 있는 것은 순환참조이므로,
                    # 본문+댓글에도 있어야 진정한 증거로 인정
                    if orig_norm in body_and_comments_norm:
                        if not (short_title and particle_collision):
                            # 포스트 제목 약어 앵커 + 캐릭터명 충돌 아님
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
            # 단, short title은 구조적 작품표지(작품/제목/웹소설 등)가 함께 있어야 인정
            if len(title_norm) <= 3:
                structural_markers = ("작품", "제목", "웹소설", "소설", "연재", "정식")
                if any(m in body_and_comments for m in structural_markers):
                    return True
            else:
                return True

        # 4) 댓글에 작품 관련 URL이 있는지
        import re
        url_pattern = re.compile(
            r'(novelpia\.com|munpia\.com|namu\.wiki|kakaopage\.com|series\.naver\.com)'
        )
        if url_pattern.search(body_and_comments):
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
                    if author_name in body_and_comments:
                        return True
                    # author_info에서도 확인
                    author_info = term.get("author_info") or {}
                    confirmed_name = (author_info.get("name") or "").strip()
                    if confirmed_name and len(confirmed_name) >= 2 and confirmed_name in body_and_comments:
                        return True

        # 6) 제목 주도 반응글(커뮤니티 단문형) 보강
        #    패턴: 제목에 작품 약칭/앵커 + 본문은 짧은 감정 반응(슬프네, ㅠㅠ 등) + 댓글이 사건 확인형(누구 죽었노 등)
        #    목적: 본문 정보량이 낮아도 제목-본문 연속문맥을 작품 반응글로 인식
        try:
            post_title_norm = post_title.lower().replace(" ", "")
            post_body_norm = post_body.lower().replace(" ", "")
            comments_norm = comments_text.lower().replace(" ", "")

            short_body = len(post_body.strip()) <= 48
            affective_markers = (
                "슬프", "울컥", "눈물", "어흑", "ㅠㅠ", "ㅜㅜ", "좆", "존나", "충격", "불쌍",
            )
            reaction_in_text = any(m in post_body_norm for m in affective_markers)
            reaction_in_comments = any(m in comments_norm for m in affective_markers)
            event_check_markers = (
                "누구죽", "누가죽", "죽었노", "죽었냐", "막화", "최신화", "이번화",
            )
            has_event_check = any(m in comments_norm for m in event_check_markers)

            has_title_anchor_term = False
            for term in decoder_result.get("decoded_terms", []):
                if not isinstance(term, dict):
                    continue
                best = term.get("best_match") or {}
                if best.get("title") != title:
                    continue
                original = str(term.get("original") or "").strip().lower().replace(" ", "")
                if original and len(original) >= 2 and original in post_title_norm:
                    has_title_anchor_term = True
                    break

            if has_title_anchor_term and short_body and (reaction_in_text or reaction_in_comments or has_event_check):
                return True
        except Exception:
            pass
        
        return False

    def _select_decoder_title_candidate(
        self,
        decoder_result: Dict[str, Any],
        post_title: str,
    ) -> Optional[Dict[str, str]]:
        """
        Decoder 결과에서 본문/제목 기반 복구에 쓸 대표 작품 후보를 선택한다.
        (단일 후보 반환 — 하위 호환)
        """
        candidates = self._select_decoder_title_candidates(decoder_result, post_title, top_n=1)
        return candidates[0] if candidates else None

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # A3: 다중 후보 선택 (Decoder multi-candidate competition)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def _select_decoder_title_candidates(
        self,
        decoder_result: Dict[str, Any],
        post_title: str,
        *,
        top_n: int = 3,
    ) -> List[Dict[str, str]]:
        """
        Decoder 결과에서 상위 N개의 작품 후보를 점수 순으로 반환한다.

        우선순위:
        1) 제목에 직접 등장한 원어(original)를 가진 term
        2) best_match.title 존재
        3) confidence(high > medium > low)

        Returns:
            [{title, confidence, url, original, score}, ...] (최대 top_n개)
        """
        decoder_result = decoder_result or {}
        title_norm = (post_title or "").lower().replace(" ", "")

        conf_rank = {"high": 3, "medium": 2, "low": 1, "max": 4}
        scored: List[Dict[str, Any]] = []

        for term in decoder_result.get("decoded_terms", []):
            if not isinstance(term, dict):
                continue
            bm = term.get("best_match") or {}
            cand_title = str(bm.get("title") or "").strip()
            cand_conf = str(bm.get("confidence") or "").lower()
            if not cand_title or cand_conf in ("none", ""):
                continue

            original = str(term.get("original") or "").strip()
            original_norm = original.lower().replace(" ", "")
            title_anchor_bonus = 1 if (original_norm and original_norm in title_norm) else 0
            score = conf_rank.get(cand_conf, 0) * 10 + title_anchor_bonus

            cand_url = ""
            for c in (term.get("candidates") or []):
                if not isinstance(c, dict):
                    continue
                c_title = str(c.get("official_novel_title") or c.get("official_title") or "").strip()
                if c_title and c_title == cand_title:
                    cand_url = str(c.get("url") or "").strip()
                    break

            scored.append({
                "title": cand_title,
                "confidence": cand_conf,
                "url": cand_url,
                "original": original,
                "score": score,
            })

        # 점수 내림차순 정렬 후 중복 제목 제거
        scored.sort(key=lambda x: x["score"], reverse=True)
        seen_titles: set = set()
        unique: List[Dict[str, str]] = []
        for item in scored:
            t_norm = item["title"].lower().replace(" ", "")
            if t_norm in seen_titles:
                continue
            seen_titles.add(t_norm)
            unique.append(item)
            if len(unique) >= top_n:
                break

        return unique

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # A5: LLM 기반 후보 크로스체크
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def _llm_cross_check_candidates(
        self,
        post: Dict[str, Any],
        comments: List[str],
        candidates: List[Dict[str, str]],
        gatekeeper_result: Dict[str, Any],
        decoder_result: Dict[str, Any],
        ctx: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        LLM 기반 후보 크로스체크.

        code_level_body_check로 확정 못한 경우, LLM에게 게시글 본문·댓글과
        Decoder 후보를 함께 제시하여 실제 논의 중인 작품을 판별한다.

        Returns:
            선택된 후보 dict (title, confidence, url, original, evidence_summary)
            또는 None (어떤 후보도 해당하지 않음)
        """
        if not candidates:
            return None

        post_title = str(post.get("title") or "")
        body_parts = []
        for block in post.get("content_blocks", []):
            if isinstance(block, dict) and block.get("text"):
                body_parts.append(block["text"])
        body_text = "\n".join(body_parts)
        comments_text = "\n".join(f"- {c}" for c in (comments or [])[:15])

        # 후보 목록 구성 (최대 3개)
        candidate_lines = []
        for i, cand in enumerate(candidates[:3], 1):
            candidate_lines.append(
                f'{i}. 정식 제목: "{cand.get("title", "")}" '
                f'(원문 표현: "{cand.get("original", "")}", '
                f'Decoder 신뢰도: {cand.get("confidence", "unknown")})'
            )
        candidates_block = "\n".join(candidate_lines)

        gk_post_type = str(gatekeeper_result.get("post_type") or "")
        gk_inference = str(gatekeeper_result.get("inference") or "")

        user_prompt = f"""당신은 웹소설 커뮤니티 게시글 분석 전문가입니다.
아래 게시글과 후보 작품 목록을 보고, 이 게시글이 실제로 **어떤 특정 웹소설 작품**에 대해 논의하고 있는지 판별하세요.

## 게시글 정보
- 게시글 제목: {post_title}
- Gatekeeper 분류: {gk_post_type}
- Gatekeeper 추론: {gk_inference[:200]}

## 게시글 본문
{body_text[:2000]}

## 댓글 (최대 15개)
{comments_text[:1500]}

## Decoder가 식별한 후보 작품
{candidates_block}

## 판별 기준
1. 게시글 본문이나 댓글에서 후보 작품과 관련된 **구체적 증거**를 찾으세요:
   - 작품 제목이나 약칭의 직접 언급
   - 해당 작품의 캐릭터명, 고유명사, 줄거리 요소
   - 작가명 언급 + 작품 연관성
   - "몇화", "연재", "완결" 등 연재 작품 토론 맥락
   - 독자 감상/반응 (스포, 감동, 분노 등)
2. 게시글 제목에만 약칭이 있고 본문/댓글에는 관련 증거가 전혀 없으면 "none"으로 판정하세요.
3. 여러 후보 중 증거가 가장 강한 것을 선택하세요.
4. 일반적인 장르 토론, 작가 비평(특정 작품이 아닌), 커뮤니티 잡담은 "none"입니다.

## 출력 형식 (JSON)
{{
  "selected_index": 1,
  "selected_title": "선택된 작품의 정식 제목",
  "confidence": "high" | "medium" | "low" | "none",
  "evidence_summary": "선택 근거를 1-2문장으로 설명",
  "body_evidence_found": true
}}

- selected_index: 후보 번호 (1부터 시작). 해당 작품이 없으면 0
- confidence가 "none"이면 selected_index=0, selected_title=""로 설정
- body_evidence_found: 본문이나 댓글에서 작품 관련 구체적 증거를 발견했으면 true"""

        try:
            messages = [
                {"role": "system", "content": "당신은 웹소설 커뮤니티 게시글에서 특정 작품이 논의되고 있는지 판별하는 전문가입니다. 반드시 JSON으로 응답하세요."},
                {"role": "user", "content": user_prompt},
            ]
            response_text = self.llm._stream_chat_http(
                messages=messages,
                tag="verifier",
                use_grammar=True,
                max_tokens=512,
            )
            parsed = parse_json_with_think_removal(response_text)
            if not isinstance(parsed, dict):
                print(
                    f"[{_ts()}][{self.emoji}] ⚠️ LLM 크로스체크 파싱 실패",
                    file=sys.stderr,
                )
                return None

            selected_idx = int(parsed.get("selected_index") or 0)
            confidence = str(parsed.get("confidence") or "none").lower()
            body_evidence = bool(parsed.get("body_evidence_found", False))
            evidence_summary = str(parsed.get("evidence_summary") or "")

            if confidence == "none" or selected_idx < 1 or not body_evidence:
                print(
                    f"[{_ts()}][{self.emoji}] 🔍 LLM 크로스체크 결과: 해당 작품 없음 "
                    f"(conf={confidence}, idx={selected_idx}, evidence={body_evidence})",
                    file=sys.stderr,
                )
                return None

            if selected_idx > len(candidates):
                return None

            selected = candidates[selected_idx - 1]
            # LLM 신뢰도가 low이면 복구하지 않음 (보수적)
            if confidence == "low":
                print(
                    f"[{_ts()}][{self.emoji}] 🔍 LLM 크로스체크: low confidence → 복구 안 함 "
                    f"(title='{selected.get('title')}')",
                    file=sys.stderr,
                )
                return None

            print(
                f"[{_ts()}][{self.emoji}] ✅ LLM 크로스체크 성공: "
                f"title='{selected.get('title')}', conf={confidence}, "
                f"evidence='{evidence_summary[:80]}'",
                file=sys.stderr,
            )
            return {
                "title": selected.get("title", ""),
                "confidence": confidence,
                "url": selected.get("url", ""),
                "original": selected.get("original", ""),
                "evidence_summary": evidence_summary,
                "cross_check_source": "llm",
            }

        except Exception as exc:
            print(
                f"[{_ts()}][{self.emoji}] ⚠️ LLM 크로스체크 예외: {exc}",
                file=sys.stderr,
            )
            return None

    @staticmethod
    def _normalize_relation_type(value: Any) -> str:
        raw = str(value or "").strip().lower()
        mapping = {
            "exact": "exact_title",
            "exact_match": "exact_title",
            "explicit": "explicit_alias",
            "explicit_bridge": "explicit_alias",
            "alias": "explicit_alias",
            "nickname": "work_specific_nickname",
            "genre": "genre_or_trope_label",
            "genre_label": "genre_or_trope_label",
            "trope": "genre_or_trope_label",
            "platform": "platform_or_category",
            "category": "platform_or_category",
            "meta": "community_slang_or_meta",
            "community": "community_slang_or_meta",
            "slang": "community_slang_or_meta",
            "thematic": "thematic_overlap_only",
            "theme_overlap": "thematic_overlap_only",
        }
        return mapping.get(raw, raw or "unknown")

    @staticmethod
    def _normalize_relation_target(value: Any) -> str:
        raw = str(value or "").strip().lower()
        mapping = {
            "specific": "specific_work",
            "work": "specific_work",
            "specific_work_discussion": "specific_work",
            "genre": "genre_general",
            "genre_general_talk": "genre_general",
            "platform": "platform_meta",
            "meta": "platform_meta",
            "community": "community_banter",
            "banter": "community_banter",
            "uncertain": "mixed_or_uncertain",
            "mixed": "mixed_or_uncertain",
        }
        return mapping.get(raw, raw or "mixed_or_uncertain")

    @staticmethod
    def _normalize_promotion_decision(value: Any) -> str:
        raw = str(value or "").strip().lower()
        mapping = {
            "allow_title_promotion": "allow",
            "promote": "allow",
            "accept": "allow",
            "keep": "allow",
            "defer": "hold",
            "pending": "hold",
            "nullify": "reject",
            "block": "reject",
            "deny": "reject",
        }
        return mapping.get(raw, raw or "hold")

    def _collect_relation_aliases(
        self,
        title: str,
        post: Dict[str, Any],
        comments: List[str],
        decoder_result: Dict[str, Any],
        verification: Dict[str, Any],
        ctx: Optional[Any] = None,
    ) -> List[str]:
        aliases: List[str] = []
        seen: set[str] = set()
        post_title = str((post or {}).get("title") or "")
        full_text = " ".join(
            [post_title]
            + [
                str(block.get("text") or "")
                for block in ((post or {}).get("content_blocks") or [])
                if isinstance(block, dict)
            ]
            + [c for c in (comments or []) if isinstance(c, str)]
        )

        def _push(raw: Any) -> None:
            alias = str(raw or "").strip()
            if not alias:
                return
            norm = self._norm_text(alias)
            if not norm or norm == self._norm_text(title) or norm in seen:
                return
            seen.add(norm)
            aliases.append(alias)

        def _push_surface_alias(raw: Any) -> None:
            alias = str(raw or "").strip()
            if not alias or not self._is_bootstrap_surface_alias(alias):
                return
            if not self._surface_in_text(full_text, alias):
                return
            _push(alias)

        def _push_mapping_alias(mapping: Any) -> None:
            if not isinstance(mapping, dict):
                return
            abbrev = mapping.get("abbrev") or mapping.get("alias") or mapping.get("term")
            full = mapping.get("full") or mapping.get("title") or mapping.get("official_title")
            if not abbrev or not full:
                return
            if self._norm_text(full) != self._norm_text(title):
                return
            _push_surface_alias(abbrev)

        grounding = (verification or {}).get("grounding_check") or {}
        _push(grounding.get("matched_alias"))

        for term in (decoder_result or {}).get("decoded_terms", []):
            if not isinstance(term, dict):
                continue
            best = term.get("best_match") or {}
            best_title = best.get("title") or best.get("official_novel_title")
            if self._norm_text(best_title) != self._norm_text(title):
                continue
            grounding = term.get("grounding") or {}
            anchor_type = str(grounding.get("anchor_type") or "").strip().lower()
            if anchor_type in {"character_mention", "plot_mention"}:
                continue
            _push(term.get("original"))

        slang_insight = (verification or {}).get("slang_insight") or {}
        if isinstance(slang_insight, dict):
            decoded = slang_insight.get("decoded_term") or slang_insight.get("official_title")
            if self._norm_text(decoded) == self._norm_text(title):
                _push_surface_alias(
                    slang_insight.get("canonical_work_alias")
                    or slang_insight.get("detected_term")
                )

        snippet_hints = getattr(ctx, "snippet_hints", None) if ctx is not None else None
        if isinstance(snippet_hints, dict):
            for key in ("abbreviation_hints", "abbreviation_mappings"):
                for mapping in snippet_hints.get(key) or []:
                    _push_mapping_alias(mapping)

        ctx_abbrevs = getattr(ctx, "abbreviation_mappings", None) if ctx is not None else None
        if isinstance(ctx_abbrevs, dict):
            for abbrev, full in ctx_abbrevs.items():
                _push_mapping_alias({"abbrev": abbrev, "full": full})

        for alias in list(aliases):
            if not self._surface_in_text(full_text, alias):
                continue

        return aliases[:4]

    def _is_bootstrap_surface_alias(self, term: Any) -> bool:
        raw = str(term or "").strip()
        if not raw:
            return False
        norm = self._norm_text(raw)
        if len(norm) < 3 or len(norm) > 12:
            return False
        if self._is_platform_branding_title(raw):
            return False
        genre_norms = {
            self._norm_text(token)
            for token in GENRE_ARCHETYPE_TERMS
            if isinstance(token, str) and token.strip()
        }
        if norm in genre_norms:
            return False
        return True

    def _collect_bootstrap_surface_aliases(
        self,
        post: Dict[str, Any],
        comments: List[str],
        decoder_result: Dict[str, Any],
        verification: Dict[str, Any],
    ) -> List[str]:
        aliases: List[str] = []
        seen: set[str] = set()
        full_text = " ".join(
            [str((post or {}).get("title") or "")]
            + [
                str(block.get("text") or "")
                for block in ((post or {}).get("content_blocks") or [])
                if isinstance(block, dict)
            ]
            + [str(c) for c in (comments or []) if isinstance(c, str)]
        ).strip()

        def _push(raw: Any) -> None:
            alias = str(raw or "").strip()
            if not alias or not self._is_bootstrap_surface_alias(alias):
                return
            if not self._surface_in_text(full_text, alias):
                return
            norm = self._norm_text(alias)
            if norm in seen:
                return
            seen.add(norm)
            aliases.append(alias)

        grounding = (verification or {}).get("grounding_check") or {}
        _push(grounding.get("matched_alias"))

        for term in (decoder_result or {}).get("decoded_terms") or []:
            if not isinstance(term, dict):
                continue
            _push(term.get("original"))

        for term in (decoder_result or {}).get("unresolved_terms") or []:
            if not isinstance(term, dict):
                continue
            _push(term.get("term"))

        return aliases[:6]

    @classmethod
    def _extract_official_detail_title_candidate(cls, value: Any) -> str:
        import re

        raw = str(value or "").strip()
        if not raw:
            return ""

        candidate = raw
        if " - " in candidate:
            parts = [part.strip() for part in candidate.split(" - ") if part.strip()]
            for part in reversed(parts):
                if not cls._is_platform_branding_title(part):
                    candidate = part
                    break

        candidate = re.sub(r"\s*\(r\d+\s*판\)$", "", candidate).strip()
        candidate = re.sub(
            r"\s*-\s*(?:문피아\s*웹소설|웹소설\s*문피아|노벨피아|네이버\s*시리즈|카카오페이지|조아라.*|웹소설)$",
            "",
            candidate,
            flags=re.IGNORECASE,
        ).strip()
        if cls._is_platform_branding_title(candidate):
            return ""
        if cls._is_community_artifact_title(candidate):
            return ""
        norm = cls._norm_text(candidate)
        if len(norm) < 4:
            return ""
        return candidate

    def _collect_relation_bootstrap_candidates(
        self,
        post: Dict[str, Any],
        comments: List[str],
        decoder_result: Dict[str, Any],
        verification: Dict[str, Any],
        ctx: Optional[Any],
        verification_search: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        seen_titles: set[str] = set()

        def _push(title: Any, *, source: str, url: Any = None, confidence: Any = None) -> None:
            candidate_title = self._extract_official_detail_title_candidate(title)
            if not candidate_title:
                return
            if self._is_community_artifact_title(candidate_title):
                return
            title_norm = self._norm_text(candidate_title)
            if title_norm in seen_titles:
                return
            seen_titles.add(title_norm)
            candidates.append({
                "title": candidate_title,
                "source": source,
                "url": str(url or "").strip() or None,
                "confidence": str(confidence or "").strip().lower() or None,
            })

        decoder_candidate = self._select_decoder_title_candidate(
            decoder_result or {},
            str((post or {}).get("title") or ""),
        )
        if isinstance(decoder_candidate, dict):
            _push(
                decoder_candidate.get("title"),
                source="decoder",
                url=decoder_candidate.get("url"),
                confidence=decoder_candidate.get("confidence"),
            )

        if ctx and hasattr(ctx, "suspected_titles"):
            for st in (ctx.suspected_titles or []):
                if not isinstance(st, dict):
                    continue
                _push(
                    st.get("title"),
                    source="suspected",
                    url=st.get("url"),
                    confidence=st.get("confidence"),
                )

        all_search = (ctx.search_results or []) + (verification_search or []) if ctx else (verification_search or [])
        for sr in all_search:
            if not isinstance(sr, dict):
                continue
            sr_url = str(sr.get("url") or "")
            if not self._is_novel_detail_url(sr_url):
                continue
            page_analysis = sr.get("page_analysis") if isinstance(sr.get("page_analysis"), dict) else {}
            _push(
                page_analysis.get("novel_title") or sr.get("novel_title") or sr.get("resolved_title") or sr.get("title"),
                source="official_search",
                url=sr_url,
            )

        return candidates

    @staticmethod
    def _normalize_search_purpose(value: Any) -> str:
        raw = str(value or "").strip().lower()
        if ":" in raw:
            raw = raw.split(":", 1)[0].strip()
        return raw

    @staticmethod
    def _is_community_discussion_url(value: Any) -> bool:
        url = str(value or "").strip().lower()
        return any(
            domain in url
            for domain in (
                "dcinside.com",
                "arca.live",
                "fmkorea.com",
                "ruliweb.com",
                "theqoo.net",
                "instiz.net",
            )
        )

    def _build_relation_search_support_summary(
        self,
        title: str,
        alias_terms: List[str],
        search_results: List[Dict[str, Any]],
        *,
        ctx: Optional[Any] = None,
        post: Optional[Dict[str, Any]] = None,
        comments: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if self._is_community_artifact_title(title):
            return {
                "official_exact_title_count": 0,
                "official_alias_context_count": 0,
                "community_alias_support_count": 0,
                "explicit_alias_bridge_count": 0,
                "support_channel_count": 0,
                "support_purposes": [],
                "alias_in_post_count": 0,
                "best_official_url": None,
                "converged_official_signal": False,
            }
        title_norm = self._norm_text(title)
        alias_norms = {
            self._norm_text(alias)
            for alias in (alias_terms or [])
            if self._norm_text(alias)
        }
        post_text = " ".join(
            [str((post or {}).get("title") or "")]
            + [
                str(block.get("text") or "")
                for block in ((post or {}).get("content_blocks") or [])
                if isinstance(block, dict)
            ]
            + [str(c) for c in (comments or []) if isinstance(c, str)]
        ).strip()
        bridge_profile = {}
        if ctx is not None and hasattr(ctx, "get_candidate_bridge_profile"):
            try:
                bridge_profile = ctx.get_candidate_bridge_profile(title) or {}
            except Exception:
                bridge_profile = {}

        official_exact_urls: set[str] = set()
        official_alias_urls: set[str] = set()
        community_alias_urls: set[str] = set()
        support_purposes: set[str] = set()
        explicit_alias_bridge_count = 0
        best_official_url = ""
        title_words = [tok for tok in re.findall(r"[가-힣A-Za-z0-9]+", title) if len(tok) >= 2]

        for sr in search_results or []:
            if not isinstance(sr, dict):
                continue
            sr_title = str(sr.get("title") or "")
            sr_content = str(sr.get("content") or sr.get("snippet") or "")
            sr_query = str(sr.get("_query") or "")
            sr_url = str(sr.get("url") or "")
            sr_blob = f"{sr_title} {sr_content}".strip()
            sr_blob_norm = self._norm_text(sr_blob)
            if not sr_blob_norm:
                continue

            alias_hits = [alias for alias in alias_norms if alias and alias in sr_blob_norm]
            explicit_alias_bridge = self._has_explicit_alias_bridge_text(
                alias_hits=alias_hits,
                candidate_title=title,
                text=sr_blob,
            )
            if explicit_alias_bridge:
                explicit_alias_bridge_count += 1

            purpose_key = self._normalize_search_purpose(sr.get("_purpose"))
            title_hit = bool(
                title_norm
                and (
                    title_norm in self._norm_text(sr_title)
                    or title_norm in sr_blob_norm
                    or self._contains_as_token(sr_title, title)
                    or sum(1 for word in title_words if word in sr_title) >= min(2, len(title_words))
                )
            )
            if self._is_novel_detail_url(sr_url):
                if title_hit:
                    official_exact_urls.add(sr_url)
                    if purpose_key:
                        support_purposes.add(purpose_key)
                    if not best_official_url:
                        best_official_url = sr_url
                if alias_hits:
                    official_alias_urls.add(sr_url)
                    if purpose_key:
                        support_purposes.add(purpose_key)
                    if not best_official_url and (
                        self._norm_text(sr_query) in alias_norms
                        or title_hit
                    ):
                        best_official_url = sr_url
            else:
                page_type = str(sr.get("page_type") or "").lower()
                if (page_type == "community_post" or self._is_community_discussion_url(sr_url)) and alias_hits:
                    community_alias_urls.add(sr_url or sr_title)

        alias_in_post_count = sum(
            1 for alias in (alias_terms or [])
            if str(alias).strip() and self._surface_in_text(post_text, str(alias))
        )
        support_channel_count = len(support_purposes)
        related_anchor_hit_count = int(bridge_profile.get("related_anchor_hit_count") or 0)
        author_context_match_count = int(1 if bridge_profile.get("author_context_bridge") else 0)
        character_context_match_count = max(
            0,
            related_anchor_hit_count - int(bridge_profile.get("author_marker_hit_count") or 0),
        )
        closed_bridge = bool(bridge_profile.get("closed_bridge"))
        converged_official_signal = bool(
            alias_in_post_count >= 1
            and len(official_exact_urls) >= 1
            and (
                support_channel_count >= 2
                or len(community_alias_urls) >= 2
                or explicit_alias_bridge_count >= 1
            )
        )

        return {
            "official_exact_title_count": len(official_exact_urls),
            "official_alias_context_count": len(official_alias_urls),
            "community_alias_support_count": len(community_alias_urls),
            "explicit_alias_bridge_count": explicit_alias_bridge_count,
            "support_channel_count": support_channel_count,
            "support_purposes": sorted(support_purposes),
            "alias_in_post_count": alias_in_post_count,
            "best_official_url": best_official_url or None,
            "converged_official_signal": converged_official_signal,
            "bridge_quality": str(bridge_profile.get("bridge_quality") or "weak"),
            "closed_bridge": closed_bridge,
            "related_anchor_hit_count": related_anchor_hit_count,
            "author_context_match_count": author_context_match_count,
            "character_context_match_count": character_context_match_count,
            "matched_related_anchor_terms": list(bridge_profile.get("matched_related_anchor_terms") or [])[:4],
            "author_context_anchor_terms": list(bridge_profile.get("author_context_anchor_terms") or [])[:4],
        }

    def _select_relation_judge_search_results(
        self,
        title: str,
        alias_terms: List[str],
        search_results: List[Dict[str, Any]],
        *,
        max_items: int = 6,
    ) -> List[Dict[str, Any]]:
        title_norm = self._norm_text(title)
        alias_norms = {
            self._norm_text(alias)
            for alias in (alias_terms or [])
            if self._norm_text(alias)
        }
        scored: List[tuple[int, Dict[str, Any]]] = []
        for idx, sr in enumerate(search_results or [], 1):
            if not isinstance(sr, dict):
                continue
            title_blob = str(sr.get("title") or "")
            content_blob = str(sr.get("content") or sr.get("snippet") or "")
            url = str(sr.get("url") or "")
            blob = f"{title_blob} {content_blob}".strip()
            blob_norm = self._norm_text(blob)
            if not blob_norm:
                continue

            page_type = str(sr.get("page_type") or "").lower()
            source_class = "other"
            if self._is_novel_detail_url(url):
                source_class = "official_detail"
            elif page_type == "community_post" or self._is_community_discussion_url(url):
                source_class = "community_post"
            elif page_type == "listing":
                source_class = "listing_or_category"

            score = 0
            title_hit = bool(
                title_norm
                and (
                    title_norm in blob_norm
                    or self._contains_as_token(title_blob, title)
                )
            )
            if title_hit:
                score += 4
            alias_hits = [alias for alias in alias_norms if alias and alias in blob_norm]
            if alias_hits:
                score += 2
            explicit_alias_bridge = self._has_explicit_alias_bridge_text(
                alias_hits=alias_hits,
                candidate_title=title,
                text=blob,
            )
            if explicit_alias_bridge:
                score += 6
            if source_class == "official_detail":
                score += 2
                if title_hit:
                    score += 5
            elif source_class == "community_post":
                score -= 1
                if alias_hits:
                    score += 1
            elif source_class == "listing_or_category":
                score -= 2
            if page_type in {"novel_page", "community_post", "listing"}:
                score += 1

            if score <= 0:
                continue

            item = {
                "_evidence_rank": idx,
                "title": self._clip_text(title_blob, 180, marker=" ... "),
                "url": url,
                "content": self._clip_text(content_blob, 360, marker=" ... "),
                "is_official_detail_url": source_class == "official_detail",
                "source_class": source_class,
                "alias_hits": alias_hits[:3],
                "explicit_alias_bridge": explicit_alias_bridge,
                "official_exact_title": bool(source_class == "official_detail" and title_hit),
                "purpose": self._normalize_search_purpose(sr.get("_purpose")),
            }
            if page_type:
                item["page_type"] = page_type
            scored.append((score, item))

        scored.sort(
            key=lambda pair: (
                pair[0],
                1 if pair[1].get("is_official_detail_url") else 0,
                -int(pair[1].get("_evidence_rank") or 0),
            ),
            reverse=True,
        )
        return [item for _, item in scored[:max_items]]

    @staticmethod
    def _has_explicit_alias_bridge_text(
        *,
        alias_hits: List[str],
        candidate_title: str,
        text: str,
    ) -> bool:
        import re

        raw = str(text or "").strip()
        candidate = str(candidate_title or "").strip()
        if not raw or not candidate or not alias_hits:
            return False

        bridge_patterns = [
            r"(?:약칭|줄임말|줄여서|통칭|별칭|약어|약자로|불린다|부른다|라고\s*한다|라고\s*부른다)",
            r"(?:정식\s*제목|정식명|작품명|원제|제목)",
            r"[=:→\-]",
        ]
        alias_regex = "|".join(re.escape(alias) for alias in alias_hits if str(alias or "").strip())
        if not alias_regex:
            return False

        candidate_near_front = bool(re.search(re.escape(candidate), raw[:240], flags=re.IGNORECASE))
        if candidate_near_front:
            alias_phrase_patterns = [
                rf"(?:약칭|줄임말|줄여서|통칭|별칭|약어)\s*(?:은|는|이|가|을|를|로|으로|:|=|-)?\s*(?:{alias_regex})",
                rf"(?:{alias_regex})\s*(?:은|는|이|가)?\s*(?:약칭|줄임말|통칭|별칭|약어)",
            ]
            if any(re.search(pattern, raw, flags=re.IGNORECASE | re.DOTALL) for pattern in alias_phrase_patterns):
                return True

        patterns = [
            rf"(?:{alias_regex}).{{0,20}}(?:{re.escape(candidate)}).{{0,20}}(?:{'|'.join(bridge_patterns)})",
            rf"(?:{alias_regex}).{{0,20}}(?:{'|'.join(bridge_patterns)}).{{0,30}}(?:{re.escape(candidate)})",
            rf"(?:{re.escape(candidate)}).{{0,20}}(?:{'|'.join(bridge_patterns)}).{{0,20}}(?:{alias_regex})",
        ]
        return any(re.search(pattern, raw, flags=re.IGNORECASE | re.DOTALL) for pattern in patterns)

    @staticmethod
    def _summarize_relation_evidence(evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
        summary = {
            "total_items": 0,
            "official_detail_count": 0,
            "community_post_count": 0,
            "listing_or_category_count": 0,
            "explicit_alias_bridge_count": 0,
        }
        for item in evidence or []:
            if not isinstance(item, dict):
                continue
            summary["total_items"] += 1
            source_class = str(item.get("source_class") or "").strip().lower()
            if source_class == "official_detail":
                summary["official_detail_count"] += 1
            elif source_class == "community_post":
                summary["community_post_count"] += 1
            elif source_class == "listing_or_category":
                summary["listing_or_category_count"] += 1
            if item.get("explicit_alias_bridge"):
                summary["explicit_alias_bridge_count"] += 1
        return summary

    def _should_run_relation_judge(
        self,
        post: Dict[str, Any],
        comments: List[str],
        gatekeeper_result: Dict[str, Any],
        decoder_result: Dict[str, Any],
        verification: Dict[str, Any],
        novel_id: Dict[str, Any],
        ctx: Optional[Any] = None,
    ) -> bool:
        title = str(
            (novel_id or {}).get("official_novel_title")
            or (novel_id or {}).get("official_title")
            or ""
        ).strip()
        if not title:
            return False

        grounding = (verification or {}).get("grounding_check") or {}
        anchor = str(grounding.get("anchor_found") or "none").strip().lower()
        decoder_grounded = bool(grounding.get("decoder_grounded", True))
        gatekeeper_post_type = str((gatekeeper_result or {}).get("post_type") or "").strip().lower()
        evidence_type = str((novel_id or {}).get("evidence_type") or "").strip().lower()
        post_json = self._build_post_json(post or {}, comments or [], compact=True)
        has_body_text = bool(post_json.get("has_content_text"))
        title_in_main = self._surface_in_text(
            f"{post.get('title', '')} " + " ".join(
                str(block.get("text") or "")
                for block in (post.get("content_blocks") or [])
                if isinstance(block, dict)
            ),
            title,
        )
        alias_terms = self._collect_relation_aliases(
            title,
            post,
            comments,
            decoder_result,
            verification,
            ctx=ctx,
        )
        weak_anchor = anchor in {
            "none",
            "search_only",
            "title_abbrev_mention",
            "body_abbrev_mention",
            "community_mention",
            "character_mention",
            "",
        }
        suspicious_post_type = gatekeeper_post_type in {"meta", "community_banter", "genre_discussion"}
        suspicious_evidence = evidence_type in {"community_mention", "search_platform_url", "search_only"}

        return bool(
            weak_anchor
            or (not decoder_grounded)
            or (not has_body_text)
            or (not title_in_main)
            or alias_terms
            or suspicious_post_type
            or suspicious_evidence
        )

    def _call_relation_judge(
        self,
        post: Dict[str, Any],
        comments: List[str],
        gatekeeper_result: Dict[str, Any],
        decoder_result: Dict[str, Any],
        verification: Dict[str, Any],
        novel_id: Dict[str, Any],
        ctx: Optional[Any] = None,
        verification_search: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        title = str(
            (novel_id or {}).get("official_novel_title")
            or (novel_id or {}).get("official_title")
            or ""
        ).strip()
        if not title:
            return None

        alias_terms = self._collect_relation_aliases(
            title,
            post,
            comments,
            decoder_result,
            verification,
            ctx=ctx,
        )
        all_search = (ctx.search_results or []) + (verification_search or []) if ctx else (verification_search or [])
        evidence = self._select_relation_judge_search_results(
            title,
            alias_terms,
            all_search,
            max_items=self._env_int("LLM_RELATION_JUDGE_MAX_SEARCH_ITEMS", 6, minimum=3, maximum=10),
        )
        evidence_summary = self._summarize_relation_evidence(evidence)
        search_support_summary = self._build_relation_search_support_summary(
            title,
            alias_terms,
            all_search,
            ctx=ctx,
            post=post,
            comments=comments,
        )
        post_text = " ".join(
            [str((post or {}).get("title") or "")]
            + [
                str(block.get("text") or "")
                for block in ((post or {}).get("content_blocks") or [])
                if isinstance(block, dict)
            ]
        ).strip()
        post_direct_grounding = bool(self._surface_in_text(post_text, title))
        generic_relation_only = self._is_generic_relation_only_mapping(
            title,
            post or {},
            comments or [],
            alias_terms,
        )

        prompt = self._RELATION_JUDGE_PROMPT.format(
            candidate_title=title,
            post_json=json.dumps(self._build_post_json(post, comments, compact=True), ensure_ascii=False, indent=2),
            gatekeeper_json=json.dumps(self._summarize_gatekeeper(gatekeeper_result or {}), ensure_ascii=False, indent=2),
            decoder_json=json.dumps(self._summarize_decoder(decoder_result or {}), ensure_ascii=False, indent=2),
            verification_json=json.dumps(
                {
                    "is_relevant": verification.get("is_relevant"),
                    "grounding_check": verification.get("grounding_check"),
                    "counter_arguments": (verification.get("counter_arguments") or [])[:4],
                    "novel_identity": {
                        "official_novel_title": title,
                        "heretic_url": (novel_id or {}).get("heretic_url"),
                        "confidence": (novel_id or {}).get("confidence"),
                        "evidence_type": (novel_id or {}).get("evidence_type"),
                    },
                    "inference": verification.get("inference"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            alias_json=json.dumps(alias_terms, ensure_ascii=False),
            search_summary_json=json.dumps(
                {
                    **evidence_summary,
                    **search_support_summary,
                    "post_direct_grounding": post_direct_grounding,
                    "generic_relation_only": generic_relation_only,
                },
                ensure_ascii=False,
                indent=2,
            ),
            search_json=json.dumps(evidence, ensure_ascii=False, indent=2),
        )

        try:
            messages = [
                {"role": "system", "content": self._RELATION_JUDGE_SYSTEM},
                {"role": "user", "content": prompt},
            ]
            response_text = self.llm._stream_chat_http(
                messages=messages,
                tag="verifier_relation_judge",
                use_grammar=True,
                max_tokens=self._resolve_relation_judge_max_tokens(),
            )
            parsed = parse_json_with_think_removal(response_text)
            if not isinstance(parsed, dict):
                return None
            relation_type = self._normalize_relation_type(parsed.get("relation_type"))
            discussion_target = self._normalize_relation_target(parsed.get("discussion_target"))
            promotion_decision = self._normalize_promotion_decision(parsed.get("promotion_decision"))
            confidence = str(parsed.get("confidence") or "low").strip().lower()
            if confidence not in {"high", "medium", "low"}:
                confidence = "low"
            if generic_relation_only:
                relation_type = "genre_or_trope_label"
                discussion_target = "genre_general" if discussion_target != "platform_meta" else discussion_target
                promotion_decision = "reject"
            return {
                "relation_type": relation_type or "unknown",
                "discussion_target": discussion_target or "mixed_or_uncertain",
                "promotion_decision": promotion_decision or "hold",
                "confidence": confidence,
                "reason": str(parsed.get("reason") or "").strip(),
                "key_evidence": [
                    str(item).strip()
                    for item in (parsed.get("key_evidence") or [])
                    if str(item).strip()
                ][:4],
                "candidate_title": title,
                "observed_aliases": alias_terms[:4],
                "evidence_summary": evidence_summary,
                "search_support_summary": search_support_summary,
                "post_direct_grounding": post_direct_grounding,
                "generic_relation_only": generic_relation_only,
            }
        except Exception as exc:
            print(
                f"[{_ts()}][{self.emoji}] ⚠️ relation judge 예외: {exc}",
                file=sys.stderr,
            )
            return None

    def _apply_relation_judgment(
        self,
        relation: Dict[str, Any],
        verification: Dict[str, Any],
        novel_id: Dict[str, Any],
    ) -> None:
        if not isinstance(relation, dict) or not isinstance(verification, dict) or not isinstance(novel_id, dict):
            return

        promotion = self._normalize_promotion_decision(relation.get("promotion_decision"))
        target = self._normalize_relation_target(relation.get("discussion_target"))
        relation_type = self._normalize_relation_type(relation.get("relation_type"))
        reason = str(relation.get("reason") or "").strip()
        key_evidence = relation.get("key_evidence") or []
        evidence_summary = relation.get("evidence_summary") if isinstance(relation.get("evidence_summary"), dict) else {}
        search_support_summary = relation.get("search_support_summary") if isinstance(relation.get("search_support_summary"), dict) else {}
        explicit_bridge_count = max(
            int(evidence_summary.get("explicit_alias_bridge_count") or 0),
            int(search_support_summary.get("explicit_alias_bridge_count") or 0),
        )
        community_count = int(evidence_summary.get("community_post_count") or 0)
        official_detail_count = int(evidence_summary.get("official_detail_count") or 0)
        official_exact_title_count = int(search_support_summary.get("official_exact_title_count") or 0)
        official_alias_context_count = int(search_support_summary.get("official_alias_context_count") or 0)
        community_alias_support_count = int(search_support_summary.get("community_alias_support_count") or 0)
        support_channel_count = int(search_support_summary.get("support_channel_count") or 0)
        alias_in_post_count = int(search_support_summary.get("alias_in_post_count") or 0)
        converged_official_signal = bool(search_support_summary.get("converged_official_signal"))
        related_anchor_hit_count = int(search_support_summary.get("related_anchor_hit_count") or 0)
        author_context_match_count = int(search_support_summary.get("author_context_match_count") or 0)
        closed_bridge = bool(search_support_summary.get("closed_bridge"))
        best_official_url = str(search_support_summary.get("best_official_url") or "").strip()
        post_direct_grounding = bool(relation.get("post_direct_grounding"))
        generic_relation_only = bool(relation.get("generic_relation_only"))
        grounding = verification.get("grounding_check") if isinstance(verification.get("grounding_check"), dict) else {}
        anchor_found = str(grounding.get("anchor_found") or "").strip().lower()
        anchor_text = str(grounding.get("anchor_text") or "").strip()
        decoder_grounded = bool(grounding.get("decoder_grounded", True))
        title_abbrev_mentioned = bool(grounding.get("title_abbrev_mentioned"))
        body_abbrev_mentioned = bool(grounding.get("body_abbrev_mentioned"))
        matched_alias = str(grounding.get("matched_alias") or "").strip()
        observed_aliases = [
            str(alias).strip()
            for alias in (relation.get("observed_aliases") or [])
            if str(alias).strip()
        ]
        slang_insight = verification.get("slang_insight") if isinstance(verification.get("slang_insight"), dict) else {}
        slang_detected = str((slang_insight or {}).get("detected_term") or "").strip()
        slang_decoded = str((slang_insight or {}).get("decoded_term") or "").strip()
        slang_decode_verified = bool((slang_insight or {}).get("decode_verified"))
        current_title = (
            novel_id.get("official_novel_title")
            or novel_id.get("official_title")
            or str(relation.get("candidate_title") or "").strip()
        )
        current_title_norm = self._norm_text(current_title)
        direct_title_surface_confirmed = bool(
            current_title_norm
            and any(
                self._norm_text(surface) == current_title_norm
                or (
                    len(current_title_norm) >= 3
                    and current_title_norm in self._norm_text(surface)
                )
                for surface in [matched_alias, anchor_text, *observed_aliases]
                if str(surface or "").strip()
            )
        )
        alias_grounding_confirmed = bool(
            alias_in_post_count >= 1
            and official_exact_title_count >= 1
            and (
                community_alias_support_count >= 1
                or official_alias_context_count >= 1
                or explicit_bridge_count >= 1
                or community_count >= 1
            )
            and (
                matched_alias
                or title_abbrev_mentioned
                or body_abbrev_mentioned
                or (
                    slang_decode_verified
                    and slang_detected
                    and slang_decoded
                    and self._norm_text(slang_decoded) == self._norm_text(current_title)
                )
            )
        )
        work_meme_anchor_confirmed = bool(
            current_title
            and not self._is_community_artifact_title(current_title)
            and alias_grounding_confirmed
            and official_exact_title_count >= 1
            and matched_alias
            and (
                official_alias_context_count >= 1
                or community_alias_support_count >= 2
                or support_channel_count >= 2
                or explicit_bridge_count >= 1
                or converged_official_signal
            )
            and (
                anchor_found in {
                    "title_reaction_link",
                    "decoder_grounded_official",
                    "character_title_link",
                    "llm_cross_check",
                }
                or (
                    decoder_grounded
                    and anchor_found in {
                        "title_mention",
                        "title_abbrev_mention",
                        "body_abbrev_mention",
                        "character_mention",
                        "plot_mention",
                    }
                    and (anchor_found != "title_mention" or matched_alias or title_abbrev_mentioned)
                    and len(observed_aliases) >= 1
                )
            )
        )
        character_setting_official_convergence = bool(
            current_title
            and not self._is_community_artifact_title(current_title)
            and promotion in {"hold", "reject"}
            and relation_type == "thematic_overlap_only"
            and target in {"mixed_or_uncertain", "community_banter"}
            and explicit_bridge_count <= 0
            and decoder_grounded
            and anchor_found in {
                "character_mention",
                "character_title_link",
                "plot_mention",
                "decoder_grounded_official",
                "llm_cross_check",
            }
            and official_detail_count >= 2
            and official_exact_title_count >= 1
            and (bool(best_official_url) or converged_official_signal)
            and not generic_relation_only
        )
        exact_title_direct_official_support = bool(
            current_title
            and not self._is_community_artifact_title(current_title)
            and promotion == "hold"
            and relation_type in {"exact_title", "thematic_overlap_only"}
            and target in {"specific_work", "mixed_or_uncertain"}
            and post_direct_grounding
            and decoder_grounded
            and direct_title_surface_confirmed
            and (
                anchor_found in {
                    "title_mention",
                    "title_abbrev_mention",
                    "body_abbrev_mention",
                    "decoder_grounded_official",
                    "llm_cross_check",
                }
                or title_abbrev_mentioned
                or body_abbrev_mentioned
                or matched_alias
            )
            and alias_in_post_count >= 1
            and official_exact_title_count >= 1
            and (
                bool(best_official_url)
                or converged_official_signal
                or official_detail_count >= 1
            )
            and not generic_relation_only
        )

        if generic_relation_only:
            relation_type = "genre_or_trope_label"
            if target == "specific_work":
                target = "genre_general"
            promotion = "reject"
            reason = (
                reason
                or "후보 제목과 게시글의 연결이 무림/세력/역할 같은 일반 장르어 겹침뿐이라 특정 작품 승격을 차단함"
            )

        if exact_title_direct_official_support:
            relation_type = "exact_title"
            target = "specific_work"
            promotion = "allow"
            reason = (
                "원문에 후보 제목 표면이 직접 있고 공식 상세 검색이 같은 제목으로 수렴하여 "
                "relation hold를 exact-title allow로 정규화함"
            )
            novel_id["official_novel_title"] = current_title
            if "official_title" in novel_id:
                novel_id["official_title"] = current_title
            if best_official_url and not novel_id.get("heretic_url"):
                novel_id["heretic_url"] = best_official_url
            novel_id["confidence"] = novel_id.get("confidence") or "Medium"
        elif (
            promotion in {"hold", "reject"}
            and relation_type == "thematic_overlap_only"
            and target in {"mixed_or_uncertain", "community_banter"}
            and alias_grounding_confirmed
        ):
            relation_type = "explicit_alias" if body_abbrev_mentioned else "work_specific_nickname"
            target = "specific_work"
            promotion = "hold"
            reason = (
                reason
                or "게시글 표면 alias와 공식 상세 페이지, 커뮤니티 alias 사용례가 같은 작품으로 수렴하여 특정 작품 hold로 유지함"
            )
        elif character_setting_official_convergence:
            relation_type = "work_specific_nickname"
            target = "specific_work"
            promotion = "hold"
            reason = (
                "작품명 직접 브리지는 부족하지만 캐릭터/설정 앵커와 공식 상세 URL이 같은 작품으로 수렴하여 "
                "특정 작품 hold로 유지함"
            )
        elif (
            promotion in {"reject", "hold"}
            and target == "community_banter"
            and relation_type in {
                "community_slang_or_meta",
                "thematic_overlap_only",
                "work_specific_nickname",
                "explicit_alias",
            }
            and work_meme_anchor_confirmed
        ):
            relation_type = "work_specific_nickname" if matched_alias else "explicit_alias"
            target = "specific_work"
            promotion = "hold"
            reason = (
                reason
                or "짧은 반응글이지만 게시글 표면 alias, 공식 상세 지원, 댓글 고유 앵커가 같은 작품으로 수렴하여 작품 밈/반응글 hold로 유지함"
            )

        verification["relation_judgment"] = {
            "relation_type": relation_type,
            "discussion_target": target,
            "promotion_decision": promotion,
            "confidence": str(relation.get("confidence") or "low"),
            "reason": reason,
            "key_evidence": key_evidence[:4] if isinstance(key_evidence, list) else [],
            "observed_aliases": observed_aliases[:4],
            "evidence_summary": evidence_summary,
            "search_support_summary": search_support_summary,
            "post_direct_grounding": post_direct_grounding,
            "generic_relation_only": generic_relation_only,
        }

        counter_args = verification.get("counter_arguments")
        if not isinstance(counter_args, list):
            counter_args = []
            verification["counter_arguments"] = counter_args

        if promotion == "allow":
            verification["is_relevant"] = True
            verification["is_novel_discussion"] = True
            verification["rejection_reason"] = None
            return

        strong_character_or_plot_anchor = anchor_found in {
            "character_mention",
            "character_title_link",
            "plot_mention",
            "decoder_grounded_official",
            "llm_cross_check",
            "title_reaction_link",
        }
        official_platform_with_character_anchor = bool(
            current_title
            and promotion == "hold"
            and target == "specific_work"
            and relation_type in {"explicit_alias", "work_specific_nickname"}
            and explicit_bridge_count <= 0
            and (strong_character_or_plot_anchor or work_meme_anchor_confirmed)
            and (
                official_detail_count >= 1
                or official_exact_title_count >= 1
                or converged_official_signal
                or bool(best_official_url)
            )
        )
        official_platform_with_alias_bridge = bool(
            current_title
            and promotion == "hold"
            and target == "specific_work"
            and relation_type in {"explicit_alias", "work_specific_nickname"}
            and explicit_bridge_count >= 1
            and alias_in_post_count >= 1
            and official_exact_title_count >= 1
            and (
                official_detail_count >= 1
                or bool(best_official_url)
                or converged_official_signal
            )
            and not generic_relation_only
        )
        if official_platform_with_character_anchor or official_platform_with_alias_bridge:
            novel_id["official_novel_title"] = current_title
            if "official_title" in novel_id:
                novel_id["official_title"] = current_title
            if best_official_url and not novel_id.get("heretic_url"):
                novel_id["heretic_url"] = best_official_url
            novel_id["confidence"] = novel_id.get("confidence") or "Medium"
            verification["is_relevant"] = True
            verification["is_novel_discussion"] = True
            verification["rejection_reason"] = None
            if reason:
                verification["relation_hold_reason"] = reason
            counter_args.append(
                {
                    "issue": f"relation_judge:{relation_type}",
                    "severity": "minor",
                    "action": "note_only",
                    "explanation": (
                        reason
                        or "explicit_alias_bridge는 부족하지만 공식 플랫폼 URL과 캐릭터/플롯 앵커가 확인되어 제목 nullify는 생략함"
                    ),
                }
            )
            return

        if current_title:
            novel_id["official_novel_title"] = None
            if "official_title" in novel_id:
                novel_id["official_title"] = None
            novel_id["heretic_url"] = None
            novel_id["confidence"] = "Low"

        severity = "major" if promotion == "hold" else "critical"
        counter_args.append(
            {
                "issue": f"relation_judge:{relation_type}",
                "severity": severity,
                "action": "nullify_title" if promotion != "allow" else "note_only",
                "explanation": reason or f"관계 판정상 {relation_type}/{target} → title 승격 불가",
            }
        )

        if (
            promotion == "hold"
            and target == "specific_work"
            and not post_direct_grounding
            and explicit_bridge_count <= 0
        ):
            # 검색 기반 약칭 해석만으로 official_title 승격은 막되,
            # LLM이 explicit_alias/work_specific_nickname 으로 읽은 strong community alias는
            # 작품 관련성 자체까지 버리면 과보수 FN이 생긴다.
            keep_specific_work_hold = bool(
                (
                    relation_type in {"explicit_alias", "work_specific_nickname"}
                    and community_count >= 2
                    and len(list(relation.get("observed_aliases") or [])) >= 1
                )
                or (
                    converged_official_signal
                    and official_exact_title_count >= 1
                    and alias_in_post_count >= 1
                    and support_channel_count >= 2
                )
                or alias_grounding_confirmed
                or (
                    author_context_match_count >= 1
                    and related_anchor_hit_count >= 1
                    and official_exact_title_count >= 1
                )
                or closed_bridge
            )
            if keep_specific_work_hold:
                reason = (
                    reason
                    or "검색 기반 약칭 해석으로 특정 작품 가능성은 높지만, 게시글 내부 직접 브리지가 부족해 제목 승격은 보류함"
                )
                verification["relation_judgment"]["reason"] = reason
            else:
                target = "mixed_or_uncertain" if community_count > 0 or official_detail_count > 0 else "community_banter"
                promotion = "reject"
                reason = (
                    reason
                    or "검색상 관련 흔적은 있으나 게시글 내부 직접 앵커나 명시적 alias bridge가 없어 특정 작품으로 유지할 수 없음"
                )
                verification["relation_judgment"]["discussion_target"] = target
                verification["relation_judgment"]["promotion_decision"] = promotion
                verification["relation_judgment"]["reason"] = reason

        if promotion == "hold" and target == "specific_work":
            verification["is_relevant"] = True
            verification["is_novel_discussion"] = True
            if verification.get("rejection_reason"):
                verification["previous_rejection_reason"] = verification.get("rejection_reason")
            verification["rejection_reason"] = None
            if reason:
                verification["relation_hold_reason"] = reason
            return

        verification["is_relevant"] = False
        verification["is_novel_discussion"] = False
        verification["rejection_reason"] = reason or f"{target} 문맥으로 판단되어 작품 title 승격 거부"
        target_to_type = {
            "genre_general": ("genre_discussion", "장르/트로프 일반 논의"),
            "platform_meta": ("meta", "플랫폼/카테고리/서비스 메타"),
            "community_banter": ("community_banter", "커뮤니티 잡담/반응"),
            "mixed_or_uncertain": ("noise", "특정 작품 단정 불가"),
        }
        mapped = target_to_type.get(target)
        if mapped:
            verification["inference"] = {
                "type": mapped[0],
                "topic": mapped[1],
            }

    def _build_relation_bootstrap_novel_id(
        self,
        post: Dict[str, Any],
        comments: List[str],
        decoder_result: Dict[str, Any],
        verification: Dict[str, Any],
        ctx: Optional[Any],
        verification_search: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        candidate_pool = self._collect_relation_bootstrap_candidates(
            post,
            comments,
            decoder_result,
            verification,
            ctx,
            verification_search=verification_search,
        )
        if not candidate_pool:
            return None

        all_search = (ctx.search_results or []) + (verification_search or []) if ctx else (verification_search or [])
        surface_aliases = self._collect_bootstrap_surface_aliases(
            post,
            comments,
            decoder_result or {},
            verification or {},
        )

        best_choice: Optional[Dict[str, Any]] = None
        best_score = float("-inf")

        for candidate in candidate_pool:
            candidate_title = str(candidate.get("title") or "").strip()
            if not candidate_title:
                continue

            alias_terms = self._collect_relation_aliases(
                candidate_title,
                post or {},
                comments or [],
                decoder_result or {},
                verification or {},
                ctx=ctx,
            )
            for alias in surface_aliases:
                if alias and alias not in alias_terms:
                    alias_terms.append(alias)

            support_summary = self._build_relation_search_support_summary(
                candidate_title,
                alias_terms,
                all_search,
                ctx=ctx,
                post=post,
                comments=comments,
            )
            official_exact = int(support_summary.get("official_exact_title_count") or 0)
            support_channels = int(support_summary.get("support_channel_count") or 0)
            community_support = int(support_summary.get("community_alias_support_count") or 0)
            official_alias = int(support_summary.get("official_alias_context_count") or 0)
            explicit_bridge = int(support_summary.get("explicit_alias_bridge_count") or 0)
            alias_in_post = int(support_summary.get("alias_in_post_count") or 0)
            converged = bool(support_summary.get("converged_official_signal"))
            near_converged = bool(
                alias_in_post >= 1
                and official_exact >= 1
                and (
                    support_channels >= 2
                    or (support_channels >= 1 and community_support >= 1)
                    or official_alias >= 1
                    or explicit_bridge >= 1
                )
            )
            if not converged and not near_converged:
                continue

            score = (
                official_exact * 5
                + support_channels * 3
                + community_support * 2
                + official_alias * 2
                + explicit_bridge * 4
                + alias_in_post * 2
            )
            if converged:
                score += 12
            if str(candidate.get("source") or "") == "official_search":
                score += 4
            if str(candidate.get("source") or "") == "decoder":
                score += 1

            if score > best_score:
                best_score = score
                best_choice = {
                    "candidate": candidate,
                    "support_summary": support_summary,
                    "converged": converged,
                }

        if not best_choice:
            return None

        candidate = best_choice["candidate"]
        support_summary = best_choice["support_summary"]
        confidence_in = str(candidate.get("confidence") or "").strip().lower()
        confidence_out = "High" if best_choice.get("converged") or confidence_in in {"high", "max"} else "Medium"
        candidate_title = str(candidate.get("title") or "").strip()
        return {
            "official_novel_title": candidate_title,
            "official_title": candidate_title,
            "heretic_url": str(candidate.get("url") or support_summary.get("best_official_url") or "").strip() or None,
            "confidence": confidence_out,
            "evidence_type": "converged_search_bootstrap",
            "notes": f"search convergence bootstrap ({candidate.get('source')})",
            "search_support_summary": support_summary,
        }

    def _recover_false_negative_with_code_anchor(
        self,
        post: Dict[str, Any],
        comments: List[str],
        gatekeeper_result: Dict[str, Any],
        decoder_result: Dict[str, Any],
        verification: Dict[str, Any],
        result: Dict[str, Any],
        ctx: Optional[Any] = None,
    ) -> bool:
        """
        is_relevant=false 판정을 코드레벨 앵커 기반으로 제한적 복구한다.

        적용 조건(보수적):
        - Gatekeeper가 work_discussion 계열
        - Decoder에서 제목 후보를 확보
        - _code_level_body_check가 True
        """
        import re

        def _norm_text(raw: Any) -> str:
            return re.sub(r"[^0-9a-zA-Z가-힣]", "", str(raw or "").lower())

        def _has_strong_abbrev_recovery_evidence(
            _ctx: Any,
            *,
            _candidate_title: str,
            _candidate_original: str,
            _post_title: str,
        ) -> bool:
            if not _ctx:
                return False
            cand_title = str(_candidate_title or "").strip()
            cand_orig = str(_candidate_original or "").strip()
            if not cand_title or not cand_orig:
                return False

            cand_title_norm = _norm_text(cand_title)
            cand_orig_norm = _norm_text(cand_orig)
            post_title_norm = _norm_text(_post_title)
            if not cand_title_norm or not cand_orig_norm:
                return False
            if cand_orig_norm not in post_title_norm:
                return False

            snippet_hints = getattr(_ctx, "snippet_hints", None) or {}
            for ah in (snippet_hints.get("abbreviation_hints") or []):
                if not isinstance(ah, dict):
                    continue
                ab = str(ah.get("abbrev") or "").strip()
                full = str(ah.get("full") or "").strip()
                if not ab or not full:
                    continue
                if _norm_text(ab) != cand_orig_norm:
                    continue
                full_norm = _norm_text(full)
                if full_norm == cand_title_norm or self._is_similar_title(full, cand_title):
                    return True

            # 후보 증거 버킷 fallback (제목 key가 정확히 일치하지 않아도 유사키 허용)
            candidate_evidence = getattr(_ctx, "candidate_evidence", None) or {}
            if isinstance(candidate_evidence, dict) and candidate_evidence:
                for k, bucket in candidate_evidence.items():
                    if not isinstance(bucket, dict):
                        continue
                    k_str = str(k or "")
                    if not k_str:
                        continue
                    if (_norm_text(k_str) != cand_title_norm) and (not self._is_similar_title(k_str, cand_title)):
                        continue
                    official_urls = bucket.get("official_urls") or []
                    snippets = bucket.get("search_snippets") or []
                    if isinstance(official_urls, list) and len(official_urls) >= 1:
                        return True
                    if isinstance(snippets, list) and len(snippets) >= 2:
                        return True

            return False

        def _has_author_criticism_lock(vf: Dict[str, Any], gk: Dict[str, Any], p: Dict[str, Any]) -> tuple[bool, List[str]]:
            signals: List[str] = []
            reject_hits = 0
            vf = vf or {}
            gk = gk or {}
            p = p or {}

            # 1) Verifier 자체 신호
            author_info = vf.get("author_info") or {}
            if isinstance(author_info, dict) and author_info.get("is_author_criticism") is True:
                signals.append("author_info.is_author_criticism=true")

            inf = vf.get("inference") or {}
            inf_type = str((inf.get("type") if isinstance(inf, dict) else "") or "").lower()
            if inf_type in {"author_criticism", "author_talk", "author_discussion"}:
                signals.append(f"inference.type={inf_type}")

            # 2) 거절 사유/반론 신호 (명시적 reject를 최우선)
            rej = str(vf.get("rejection_reason") or "").strip()
            if rej:
                if re.search(r"(작가|필명).*(비평|품평|조언)|작가\s*비평|특정\s*웹소설이\s*아닌", rej):
                    signals.append("rejection_reason=author_criticism_pattern")

            counter_args = vf.get("counter_arguments")
            if isinstance(counter_args, list):
                for ca in counter_args:
                    if not isinstance(ca, dict):
                        continue
                    action = str(ca.get("action") or "").lower()
                    severity = str(ca.get("severity") or "").lower()
                    blob = " ".join(
                        str(ca.get(k) or "")
                        for k in ("issue", "explanation", "argument")
                    )
                    blob = blob.strip()
                    is_authorish = bool(
                        re.search(r"(작가|필명|명령형|조언|품평|비평|현판|써라|써야)", blob)
                    )
                    if action == "reject" and severity in {"critical", "major"} and is_authorish:
                        reject_hits += 1
                if reject_hits >= 1:
                    signals.append(f"counter_arguments.reject_hits={reject_hits}")

            # 3) Gatekeeper / 원문 문체 신호
            gk_type = str(gk.get("post_type") or "").lower()
            if gk_type in {"author_criticism", "author_talk"}:
                signals.append(f"gatekeeper.post_type={gk_type}")

            post_title = str(p.get("title") or "")
            body_text = " ".join(
                str(b.get("text") or "") for b in (p.get("content_blocks") or []) if isinstance(b, dict)
            )
            full_text = f"{post_title} {body_text}"
            # 작가 대상 명령형(써라/해라/써야댐) + 비교 예시 문맥
            if re.search(r"(작가|목마|개돌).{0,12}(써라|해라|써야|해야)", full_text):
                signals.append("imperative_author_advice")

            strong_signals = [
                s for s in signals
                if not str(s).startswith("counter_arguments.reject_hits=")
            ]
            author_surface_signal = bool(
                re.search(r"(작가|필명|연재자|저자)", full_text)
            )
            lock = bool(
                strong_signals
                or (reject_hits >= 1 and author_surface_signal)
            )
            return lock, signals

        def _has_grounded_official_decoder_candidate(_candidate: Optional[Dict[str, Any]]) -> bool:
            if not isinstance(_candidate, dict):
                return False
            cand_title = str(_candidate.get("title") or "").strip()
            cand_url = str(_candidate.get("url") or "").strip()
            cand_conf = str(_candidate.get("confidence") or "").strip().lower()
            if not cand_title or cand_conf not in {"medium", "high", "max"}:
                return False
            if not self._is_novel_detail_url(cand_url):
                return False

            for _term in (decoder_result or {}).get("decoded_terms", []):
                if not isinstance(_term, dict) or _term.get("is_author_name"):
                    continue
                _bm = _term.get("best_match") or {}
                if str(_bm.get("title") or "").strip() != cand_title:
                    continue
                grounding = _term.get("grounding") or {}
                if not isinstance(grounding, dict) or not grounding.get("is_grounded"):
                    continue
                anchor = str(grounding.get("anchor_type") or "").strip().lower()
                if anchor in {
                    "title_mention",
                    "plot_mention",
                    "character_mention",
                    "author_mention",
                    "character_title_link",
                }:
                    return True
            return False

        def _build_context_abbrev_candidate(_ctx: Any, _post_title: str) -> Optional[Dict[str, str]]:
            if not _ctx:
                return None
            post_title_norm = _norm_text(_post_title)
            if not post_title_norm:
                return None

            snippet_hints = getattr(_ctx, "snippet_hints", None) or {}
            candidate_evidence = getattr(_ctx, "candidate_evidence", None) or {}
            all_search = list(getattr(_ctx, "search_results", None) or [])

            best_candidate = None
            best_score = -1
            for ah in (snippet_hints.get("abbreviation_hints") or []):
                if not isinstance(ah, dict):
                    continue
                ab = str(ah.get("abbrev") or "").strip()
                full = str(ah.get("full") or "").strip()
                if not ab or not full:
                    continue
                if _norm_text(ab) not in post_title_norm:
                    continue

                strong_support = _has_strong_abbrev_recovery_evidence(
                    _ctx,
                    _candidate_title=full,
                    _candidate_original=ab,
                    _post_title=_post_title,
                )
                exact_official = self._has_exact_official_title_support(full, all_search, _ctx)
                if not (strong_support or exact_official):
                    continue

                best_url = ""
                bucket = candidate_evidence.get(full) if isinstance(candidate_evidence, dict) else None
                if isinstance(bucket, dict):
                    official_urls = bucket.get("official_urls") or []
                    if isinstance(official_urls, list) and official_urls:
                        first = official_urls[0]
                        if isinstance(first, dict):
                            best_url = str(first.get("url") or "").strip()
                        else:
                            best_url = str(first or "").strip()
                if not best_url:
                    for sr in all_search:
                        if not isinstance(sr, dict):
                            continue
                        sr_title = str(sr.get("title") or "")
                        sr_url = str(sr.get("url") or "")
                        if self._norm_text(full) in self._norm_text(sr_title) and self._is_novel_detail_url(sr_url):
                            best_url = sr_url
                            break

                score = 0
                if strong_support:
                    score += 2
                if exact_official:
                    score += 2
                if best_url:
                    score += 1
                if score > best_score:
                    best_score = score
                    best_candidate = {
                        "title": full,
                        "confidence": "high" if score >= 4 else "medium",
                        "url": best_url,
                        "original": ab,
                        "score": score,
                        "source": "context_abbreviation_recovery",
                    }

            # snippet_hints가 비어도, 검색 결과 자체에서 "약칭은 X" + 공식 제목이 함께 잡히면 후보 생성
            alias_cues = ("약칭", "줄임말", "통칭", "줄여서")
            for sr in all_search:
                if not isinstance(sr, dict):
                    continue
                sr_url = str(sr.get("url") or "").strip()
                if not self._is_novel_detail_url(sr_url):
                    continue
                sr_title = str(sr.get("title") or "").strip()
                sr_content = str(sr.get("content") or "")
                sr_title_norm = _norm_text(sr_title)
                if not sr_title_norm:
                    continue
                # 플랫폼 branding 제거 후 제목 후보 추정
                title_guess = sr_title
                if " - " in title_guess:
                    parts = [p.strip() for p in title_guess.split(" - ") if p.strip()]
                    if parts:
                        title_guess = parts[-2] if len(parts) >= 2 else parts[0]
                title_guess = str(title_guess).strip()
                title_guess_norm = _norm_text(title_guess)
                if not title_guess_norm:
                    continue

                if not any(cue in sr_content for cue in alias_cues):
                    continue
                for token in re.findall(r"[가-힣A-Za-z0-9]{2,12}", _post_title):
                    token_norm = _norm_text(token)
                    if len(token_norm) < 2 or token_norm not in post_title_norm:
                        continue
                    if token_norm not in _norm_text(sr_content):
                        continue
                    score = 3
                    if self._has_exact_official_title_support(title_guess, all_search, _ctx):
                        score += 2
                    if score > best_score:
                        best_score = score
                        best_candidate = {
                            "title": title_guess,
                            "confidence": "high" if score >= 4 else "medium",
                            "url": sr_url,
                            "original": token,
                            "score": score,
                            "source": "search_alias_bridge_recovery",
                        }
            return best_candidate

        post = post or {}
        verification = verification or {}
        gatekeeper_result = gatekeeper_result or {}
        decoder_result = decoder_result or {}

        # 🔒 작가 비평 맥락에서는 False-negative 복구를 금지한다.
        # 이유: 예시 작품명이 많아 title_reaction_link가 쉽게 성립해 FP가 발생함.
        # 단, author_discussion (작가 스타일 논의) post_type이면 lock을 적용하지 않는다.
        _gk_post_type = str(gatekeeper_result.get("post_type") or "").lower()
        _author_lock, _author_signals = _has_author_criticism_lock(verification, gatekeeper_result, post)
        if _author_lock and _gk_post_type != "author_discussion":
            # 🔧 예외: Decoder가 게시글 제목 약어를 High confidence로 식별하고
            #   코드 레벨 본문 증거도 있으면, 작가 비평이 아니라 "작품 설정 토론"일 가능성 높음
            # 예: "즉사무림은 너무 학문적인내용은 피해야할듯" → 즉사기 들고 무림에 떨어지다 설정 비판
            _override_author_lock = False
            _post_title_ac = str(post.get("title") or "")
            for _dt_ac in (decoder_result or {}).get("decoded_terms", []):
                if not isinstance(_dt_ac, dict):
                    continue
                _bm_ac = _dt_ac.get("best_match") or {}
                _bm_title_ac = str(_bm_ac.get("title") or "").strip()
                _bm_conf_ac = str(_bm_ac.get("confidence") or "").lower()
                _orig_ac = str(_dt_ac.get("original") or "").strip()
                if (
                    _bm_title_ac
                    and _bm_conf_ac in ("high", "max", "medium")
                    and _orig_ac
                    and len(_orig_ac) >= 2
                    and _orig_ac.lower().replace(" ", "") in _post_title_ac.lower().replace(" ", "")
                ):
                    _override_author_lock = True
                    break
            if not _override_author_lock:
                print(
                    f"[{_ts()}][{self.emoji}] 🛡️ False-negative 복구 차단(author_criticism): "
                    f"signals={_author_signals[:4]}",
                    file=sys.stderr,
                )
                return False
            else:
                print(
                    f"[{_ts()}][{self.emoji}] 🔓 author_criticism 차단 우회: "
                    f"Decoder가 제목 약어 '{_orig_ac}'→'{_bm_title_ac}' High 식별 "
                    f"→ 작품 설정 토론으로 판단",
                    file=sys.stderr,
                )

        post_title = str(post.get("title") or "")
        candidate = self._select_decoder_title_candidate(decoder_result, post_title)
        strong_grounded_decoder_candidate = _has_grounded_official_decoder_candidate(candidate)
        _ctx_candidate = _build_context_abbrev_candidate(ctx, post_title)
        if _ctx_candidate and (
            (not candidate)
            or len(str(_ctx_candidate.get("original") or "")) < len(str((candidate or {}).get("original") or ""))
            or not strong_grounded_decoder_candidate
        ):
            candidate = _ctx_candidate
            strong_grounded_decoder_candidate = True
            print(
                f"[{_ts()}][{self.emoji}] 🔧 FN 복구 후보 보강: "
                f"title='{candidate.get('title')}', original='{candidate.get('original')}', "
                f"source={candidate.get('source')}",
                file=sys.stderr,
            )
        post_type = str(gatekeeper_result.get("post_type") or "").lower()
        if post_type not in ("work_discussion", "work_comparison", "author_discussion"):
            short_reaction_worklike = bool(
                post_type == "short_reaction"
                and strong_grounded_decoder_candidate
                and len(comments or []) >= 1
            )
            if not short_reaction_worklike:
                return False
            print(
                f"[{_ts()}][{self.emoji}] 🔓 FN 복구 예외: "
                f"short_reaction 이지만 댓글 앵커 + grounded decoder candidate="
                f"'{candidate.get('title') if isinstance(candidate, dict) else ''}'",
                file=sys.stderr,
            )

        # ━━━ P0-1: Verifier critical 반론 존중 (Phase29: 임계값 2→1) ━━━
        # Verifier LLM이 critical+reject 반론을 1개 이상 냈으면
        # LLM의 문맥 판단을 코드가 뒤집지 않는다.
        _counter_args = verification.get("counter_arguments", [])
        if isinstance(_counter_args, list):
            _critical_reject_count = sum(
                1 for ca in _counter_args
                if isinstance(ca, dict)
                and str(ca.get("severity", "")).lower() == "critical"
                and str(ca.get("action", "")).lower() in ("reject", "block", "deny", "veto")
            )
            if _critical_reject_count >= 1:
                if strong_grounded_decoder_candidate:
                    print(
                        f"[{_ts()}][{self.emoji}] 🔓 FN 복구 예외: "
                        f"critical_reject x{_critical_reject_count} 이지만 "
                        f"Decoder grounded official candidate='{candidate.get('title')}' 유지",
                        file=sys.stderr,
                    )
                else:
                    print(
                        f"[{_ts()}][{self.emoji}] \U0001f6e1\ufe0f FN 복구 차단(critical_reject x{_critical_reject_count}): "
                        f"Verifier LLM의 critical 반론을 존중",
                        file=sys.stderr,
                    )
                    return False

        # ━━━ P0-2: genre_discussion 경고 시 복구 차단 ━━━
        # DiscourseAnalyzer가 genre_discussion을 감지했고 본문이 짧으면
        # 장르 일반론이지 특정 작품 토론이 아닌 것으로 판단.
        if ctx:
            _discourse_warn_fnr = str(getattr(ctx, "discourse_warning", "") or "").lower()
            _has_genre_warn = any(
                tok in _discourse_warn_fnr
                for tok in ("genre_discussion", "discuss_genre", "community_banter")
            )
            if _has_genre_warn:
                _body_len_fnr = sum(
                    len(str(b.get("text", "")))
                    for b in (post.get("content_blocks") or [])
                    if isinstance(b, dict)
                )
                if _body_len_fnr < 150:
                    print(
                        f"[{_ts()}][{self.emoji}] \U0001f6e1\ufe0f FN 복구 차단(genre_discussion + short_body={_body_len_fnr}): "
                        f"discourse_warning='{_discourse_warn_fnr[:60]}'",
                        file=sys.stderr,
                    )
                    return False

        # ━━━ Phase29: 본문 정보량 최소치 가드 ━━━
        # 본문이 극히 짧고(순수 감탄사 수준) 댓글도 0건이면
        # 작품 특정 정보가 전무하므로 recovery를 금지한다.
        _body_text_fnr = " ".join(
            str(b.get("text") or "") for b in (post.get("content_blocks") or [])
            if isinstance(b, dict)
        ).strip()
        _comments_fnr = comments or []
        _body_chars_fnr = len(_body_text_fnr)
        if _body_chars_fnr < 20 and len(_comments_fnr) == 0:
            print(
                f"[{_ts()}][{self.emoji}] \U0001f6e1\ufe0f FN 복구 차단(low_info: body={_body_chars_fnr}c, comments=0): "
                f"본문 정보량 부족으로 recovery 금지",
                file=sys.stderr,
            )
            return False

        if not candidate:
            return False

        candidate_title = candidate.get("title") or ""
        if not candidate_title:
            return False

        if self._is_generic_relation_only_mapping(
            candidate_title,
            post,
            comments,
            [str(candidate.get("original") or "").strip()],
        ):
            print(
                f"[{_ts()}][{self.emoji}] 🛡️ FN 복구 차단(generic_relation_only): "
                f"title='{candidate_title}', original='{candidate.get('original') or ''}'",
                file=sys.stderr,
            )
            return False

        # ━━━ Phase29-C3: 다중 작품 캐릭터명 confidence 제한 ━━━
        # 동일 anchor term이 3개 이상 서로 다른 작품에 매칭되면,
        # 어느 작품인지 확정할 수 없으므로 recovery를 차단한다.
        _orig_term = str(candidate.get("original") or "").strip()
        if _orig_term:
            _distinct_titles_for_orig = set()
            for _dt_c3 in (decoder_result or {}).get("decoded_terms", []):
                if not isinstance(_dt_c3, dict):
                    continue
                if str(_dt_c3.get("original") or "").strip() != _orig_term:
                    continue
                # best_match
                _bm_c3 = _dt_c3.get("best_match") or {}
                _bm_t_c3 = str(_bm_c3.get("title") or "").strip()
                if _bm_t_c3:
                    _distinct_titles_for_orig.add(_bm_t_c3)
                # candidates 리스트
                for _cand_c3 in (_dt_c3.get("candidates") or []):
                    if not isinstance(_cand_c3, dict):
                        continue
                    _ct_c3 = str(
                        _cand_c3.get("official_novel_title")
                        or _cand_c3.get("official_title")
                        or ""
                    ).strip()
                    _cc_c3 = str(_cand_c3.get("confidence") or "").lower()
                    if _ct_c3 and _cc_c3 in ("high", "medium", "max"):
                        _distinct_titles_for_orig.add(_ct_c3)
            if len(_distinct_titles_for_orig) >= 3:
                print(
                    f"[{_ts()}][{self.emoji}] \U0001f6e1\ufe0f FN 복구 차단(multi_title x{len(_distinct_titles_for_orig)}): "
                    f"anchor='{_orig_term}' → {sorted(_distinct_titles_for_orig)[:4]}",
                    file=sys.stderr,
                )
                return False

        # ━━━ P0-3: 비소설 엔티티 목록 필터링 ━━━
        # 교육 프로그램, 이벤트 등 소설이 아닌 엔티티로의 매칭 차단
        _NON_NOVEL_ENTITIES = {
            "문피아 아카데미 365일 모집합니다",
            "문피아 아카데미 365일",
            "노벨피아 아카데미",
            "웹소설 아카데미",
            "카카오페이지 스테이지",
        }
        _cand_norm_check = candidate_title.replace(" ", "").lower()
        for _ne in _NON_NOVEL_ENTITIES:
            if _ne.replace(" ", "").lower() == _cand_norm_check:
                print(
                    f"[{_ts()}][{self.emoji}] \U0001f6e1\ufe0f FN 복구 차단(non_novel_entity): "
                    f"'{candidate_title}' 는 소설이 아닌 엔티티",
                    file=sys.stderr,
                )
                return False

        # ━━━ A3+A5: 본문 증거 확인 (코드 fast-path → LLM 크로스체크 fallback) ━━━
        _code_check_passed = self._code_level_body_check(post, comments, candidate_title, decoder_result)
        _recovery_source = "code_level_anchor_recovery"

        if not _code_check_passed and strong_grounded_decoder_candidate:
            _code_check_passed = True
            _recovery_source = "decoder_grounded_official_recovery"

        if not _code_check_passed:
            # Code-level 체크 실패 → LLM 크로스체크로 재시도 (A5: 댓글 LLM 크로스체크)
            _all_candidates = self._select_decoder_title_candidates(decoder_result, post_title, top_n=3)
            _llm_result = self._llm_cross_check_candidates(
                post, comments, _all_candidates, gatekeeper_result, decoder_result, ctx,
            )
            if _llm_result is None:
                return False
            # LLM이 선택한 후보로 갱신
            candidate = _llm_result
            candidate_title = candidate.get("title") or ""
            if not candidate_title:
                return False
            _recovery_source = "llm_cross_check_recovery"

        # Discourse가 명시적으로 비소설 도메인일 때는 복구 보류
        if ctx and getattr(ctx, "primary_domain", ""):
            pd = str(getattr(ctx, "primary_domain", "")).lower()
            if not is_novel_domain(pd):
                _allow_non_novel_recover = _has_strong_abbrev_recovery_evidence(
                    ctx,
                    _candidate_title=candidate_title,
                    _candidate_original=str(candidate.get("original") or ""),
                    _post_title=post_title,
                )
                if not _allow_non_novel_recover:
                    return False
                print(
                    f"[{_ts()}][{self.emoji}] 🧩 non_novel 도메인 예외복구 허용: "
                    f"primary_domain='{pd}', title='{candidate_title}'",
                    file=sys.stderr,
                )

        conf_in = str(candidate.get("confidence") or "").lower()
        conf_out = "High" if conf_in in ("high", "max") else "Medium"

        novel_identity = verification.get("novel_identity")
        if not isinstance(novel_identity, dict):
            novel_identity = {}
        novel_identity["official_novel_title"] = candidate_title
        if candidate.get("url"):
            novel_identity["heretic_url"] = candidate["url"]
        novel_identity["confidence"] = conf_out
        novel_identity["evidence_type"] = _recovery_source
        verification["novel_identity"] = novel_identity

        verification["is_relevant"] = True
        verification["is_novel_discussion"] = True

        grounding = verification.get("grounding_check")
        if not isinstance(grounding, dict):
            grounding = {}
        grounding["decoder_grounded"] = True
        grounding["anchor_text"] = (post_title or "")[:120]
        grounding["grounding_issue"] = None
        verification["grounding_check"] = grounding

        prev_rej = str(verification.get("rejection_reason") or "").strip()
        if prev_rej:
            verification["recovered_from_rejection_reason"] = prev_rej
        verification["rejection_reason"] = None

        if _recovery_source == "llm_cross_check_recovery":
            _evidence_note = candidate.get("evidence_summary", "")
            recovery_reason = (
                f"LLM 크로스체크 복구: '{candidate.get('original') or candidate_title}' → "
                f"'{candidate_title}' (증거: {_evidence_note[:100]})"
            )
            grounding["anchor_found"] = "llm_cross_check"
        elif _recovery_source == "decoder_grounded_official_recovery":
            recovery_reason = (
                f"Decoder grounded official 복구: '{candidate.get('original') or candidate_title}' → "
                f"'{candidate_title}' (official_url + 본문 설정/작가 앵커 확인)"
            )
            grounding["anchor_found"] = "decoder_grounded_official"
        else:
            recovery_reason = (
                f"코드레벨 복구: 제목 앵커('{candidate.get('original') or candidate_title}') + "
                "단문 반응 본문 패턴이 확인되어 작품 토론으로 재판정."
            )
            grounding["anchor_found"] = "title_reaction_link"
        result["reason"] = recovery_reason
        verification["recovery_note"] = recovery_reason

        print(
            f"[{_ts()}][{self.emoji}] 🔧 False-negative 복구: "
            f"title='{candidate_title}', conf={conf_out}, "
            f"anchor={grounding['anchor_found']}, source={_recovery_source}",
            file=sys.stderr,
        )
        return True
