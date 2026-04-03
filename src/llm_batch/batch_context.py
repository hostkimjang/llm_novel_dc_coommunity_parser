"""
BatchContextMemory — 포스트 간 지식 공유 (thread-safe)

병렬 모드에서도 안전하게 사용할 수 있는 배치 컨텍스트 메모리.
해소된 약칭, 작가명, 캐릭터, namu.wiki 페이지 캐시를 포스트 간에 공유한다.
"""

from __future__ import annotations

import sys
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


class BatchContextMemory:
    """포스트 간 지식 공유 메모리 (thread-safe)."""

    def __init__(self, enabled: bool = True):
        self._lock = threading.Lock()
        self.enabled = enabled

        # ── 약칭 → 정식 제목 매핑 ──
        # key: normalized abbreviation, value: {"title": str, "confidence": int, "hits": int}
        self.resolved_abbreviations: Dict[str, Dict[str, Any]] = {}

        # ── 검증 대기 약칭 (2회 이상 확인되면 승격) ──
        self.pending_abbreviations: Dict[str, Dict[str, Any]] = {}

        # ── 작가명 → 대표 작품 매핑 ──
        self.resolved_authors: Dict[str, Dict[str, Any]] = {}

        # ── 캐릭터 → 작품 매핑 ──
        self.resolved_characters: Dict[str, Dict[str, Any]] = {}

        # ── namu.wiki 캐시: URL → 페이지 추출 정보 ──
        self.namu_wiki_cache: Dict[str, Dict[str, Any]] = {}

        # ── 통계 ──
        self.stats = {
            "total_posts": 0,
            "abbreviation_lookups": 0,
            "abbreviation_hits": 0,
            "namu_cache_hits": 0,
            "namu_cache_misses": 0,
        }

    # ─── 약칭 관련 ────────────────────────────────────────

    def get_abbreviation(self, abbrev: str) -> Optional[str]:
        """약칭에 대한 정식 제목 반환 (resolved만).
        
        Returns:
            정식 제목 문자열 또는 None
        """
        if not self.enabled or not abbrev:
            return None
        key = self._normalize(abbrev)
        with self._lock:
            self.stats["abbreviation_lookups"] += 1
            entry = self.resolved_abbreviations.get(key)
            if entry:
                entry["hits"] = entry.get("hits", 0) + 1
                self.stats["abbreviation_hits"] += 1
                return entry["title"]
            return None

    def register_abbreviation(
        self,
        abbrev: str,
        title: str,
        confidence: int = 2,
        *,
        fast_promote: bool = False,
    ) -> None:
        """약칭-제목 매핑 등록.
        
        confidence >= 3 or fast_promote=True: 즉시 resolved
        otherwise: pending에 축적 → 2회 이상 등장 시 승격
        """
        if not self.enabled or not abbrev or not title:
            return
        key = self._normalize(abbrev)
        with self._lock:
            if key in self.resolved_abbreviations:
                # 이미 해소됨 — 더 높은 신뢰도면 갱신
                existing = self.resolved_abbreviations[key]
                if confidence > existing.get("confidence", 0):
                    existing["title"] = title
                    existing["confidence"] = confidence
                return

            if fast_promote or confidence >= 3:
                self.resolved_abbreviations[key] = {
                    "title": title,
                    "confidence": confidence,
                    "hits": 0,
                    "registered_at": time.time(),
                }
                print(
                    f"[{_ts()}] 🧠 BatchMem: 약칭 즉시등록 '{abbrev}' → '{title}' (conf={confidence})",
                    file=sys.stderr,
                )
                return

            # pending에 축적
            if key not in self.pending_abbreviations:
                self.pending_abbreviations[key] = {
                    "title": title,
                    "confidence": confidence,
                    "count": 1,
                }
            else:
                self.pending_abbreviations[key]["count"] += 1
                if confidence > self.pending_abbreviations[key].get("confidence", 0):
                    self.pending_abbreviations[key]["confidence"] = confidence
                    self.pending_abbreviations[key]["title"] = title

                # 2회 이상 → 승격
                if self.pending_abbreviations[key]["count"] >= 2:
                    entry = self.pending_abbreviations.pop(key)
                    self.resolved_abbreviations[key] = {
                        "title": entry["title"],
                        "confidence": entry["confidence"],
                        "hits": 0,
                        "registered_at": time.time(),
                    }
                    print(
                        f"[{_ts()}] 🧠 BatchMem: 약칭 승격 '{abbrev}' → '{entry['title']}' "
                        f"(count={entry['count']})",
                        file=sys.stderr,
                    )

    # ─── 작가 관련 ────────────────────────────────────────

    def get_author_works(self, author: str) -> Optional[Dict[str, Any]]:
        """작가명으로 등록된 작품 정보 반환."""
        if not self.enabled or not author:
            return None
        key = self._normalize(author)
        with self._lock:
            return self.resolved_authors.get(key)

    def register_author(self, author: str, title: str, confidence: int = 2) -> None:
        """작가-작품 매핑 등록."""
        if not self.enabled or not author or not title:
            return
        key = self._normalize(author)
        with self._lock:
            if key not in self.resolved_authors or confidence > self.resolved_authors[key].get("confidence", 0):
                self.resolved_authors[key] = {
                    "title": title,
                    "confidence": confidence,
                    "registered_at": time.time(),
                }

    # ─── 캐릭터 관련 ──────────────────────────────────────

    def get_character_work(self, character: str) -> Optional[str]:
        """캐릭터명으로 연결된 작품 제목 반환."""
        if not self.enabled or not character:
            return None
        key = self._normalize(character)
        with self._lock:
            entry = self.resolved_characters.get(key)
            return entry["title"] if entry else None

    def register_character(self, character: str, title: str, confidence: int = 2) -> None:
        """캐릭터-작품 매핑 등록."""
        if not self.enabled or not character or not title:
            return
        key = self._normalize(character)
        with self._lock:
            if key not in self.resolved_characters or confidence > self.resolved_characters[key].get("confidence", 0):
                self.resolved_characters[key] = {
                    "title": title,
                    "confidence": confidence,
                    "registered_at": time.time(),
                }

    # ─── namu.wiki 캐시 ───────────────────────────────────

    def get_namu_page(self, url: str) -> Optional[Dict[str, Any]]:
        """캐시된 namu.wiki 페이지 정보 반환."""
        if not self.enabled or not url:
            return None
        with self._lock:
            entry = self.namu_wiki_cache.get(url.strip())
            if entry is not None:
                self.stats["namu_cache_hits"] += 1
                return entry
            self.stats["namu_cache_misses"] += 1
            return None

    def cache_namu_page(self, url: str, info: Dict[str, Any]) -> None:
        """namu.wiki 페이지 정보를 캐시에 저장."""
        if not self.enabled or not url:
            return
        with self._lock:
            self.namu_wiki_cache[url.strip()] = info

    # ─── 배치 힌트 주입 ───────────────────────────────────

    def get_prior_hints(self, key_terms: List[str]) -> Dict[str, Any]:
        """key_terms에 매칭되는 사전 지식을 힌트 형태로 반환.
        
        Returns:
            {
                "abbreviation_hints": [{"abbrev": str, "full": str, "source": "batch_memory"}],
                "author_hints": [{"name": str, "title": str, "source": "batch_memory"}],
                "character_hints": [{"character": str, "title": str, "source": "batch_memory"}],
            }
        """
        if not self.enabled:
            return {"abbreviation_hints": [], "author_hints": [], "character_hints": []}

        abbreviation_hints = []
        author_hints = []
        character_hints = []

        with self._lock:
            for term in (key_terms or []):
                if not isinstance(term, str) or not term.strip():
                    continue
                key = self._normalize(term)

                # 약칭 매칭
                entry = self.resolved_abbreviations.get(key)
                if entry:
                    abbreviation_hints.append({
                        "abbrev": term,
                        "full": entry["title"],
                        "source": "batch_memory",
                        "confidence": entry.get("confidence", 2),
                    })

                # 작가 매칭
                author_entry = self.resolved_authors.get(key)
                if author_entry:
                    author_hints.append({
                        "name": term,
                        "title": author_entry["title"],
                        "source": "batch_memory",
                    })

                # 캐릭터 매칭
                char_entry = self.resolved_characters.get(key)
                if char_entry:
                    character_hints.append({
                        "character": term,
                        "title": char_entry["title"],
                        "source": "batch_memory",
                    })

        return {
            "abbreviation_hints": abbreviation_hints,
            "author_hints": author_hints,
            "character_hints": character_hints,
        }

    # ─── 포스트 완료 후 학습 ──────────────────────────────

    def learn_from_result(
        self,
        result: Dict[str, Any],
        *,
        decoded_terms: Optional[List[Dict[str, Any]]] = None,
        identified_author: Optional[str] = None,
        identified_characters: Optional[List[str]] = None,
    ) -> None:
        """분석 완료된 포스트에서 지식 추출 및 등록.
        
        Args:
            result: 분석 결과 (identity 포함)
            decoded_terms: Decoder가 해석한 용어 목록
            identified_author: 확인된 작가명
            identified_characters: 확인된 캐릭터 목록
        """
        if not self.enabled:
            return

        with self._lock:
            self.stats["total_posts"] += 1

        identity = result.get("identity") or result.get("analysis_result", {}).get("identity", {})
        if not identity:
            return

        is_relevant = identity.get("is_relevant", False)
        if not is_relevant:
            return

        novel_identity = identity.get("novel_identity") or {}
        official_title = novel_identity.get("official_title", "")
        confidence_str = novel_identity.get("confidence", "low")

        if not official_title:
            return

        conf_rank = {"max": 4, "high": 3, "medium": 2, "mid": 2, "low": 1}.get(
            str(confidence_str).strip().lower(), 1
        )

        # 약칭 학습
        if decoded_terms and conf_rank >= 2:
            for term in decoded_terms:
                if not isinstance(term, dict):
                    continue
                original = str(term.get("original") or "").strip()
                best_match = term.get("best_match") or {}
                if not isinstance(best_match, dict):
                    continue
                matched_title = str(best_match.get("title") or "").strip()
                if not original or not matched_title:
                    continue
                self.register_abbreviation(
                    original,
                    matched_title,
                    confidence=conf_rank,
                    fast_promote=(conf_rank >= 3),
                )

        # 작가 학습
        if identified_author and conf_rank >= 2:
            self.register_author(identified_author, official_title, confidence=conf_rank)

        # 캐릭터 학습
        if identified_characters and conf_rank >= 2:
            for char in identified_characters:
                if isinstance(char, str) and char.strip():
                    self.register_character(char.strip(), official_title, confidence=conf_rank)

    # ─── 유틸리티 ─────────────────────────────────────────

    @staticmethod
    def _normalize(text: str) -> str:
        """정규화: 공백/특수문자 제거, 소문자화."""
        import re
        return re.sub(r"[^\uac00-\ud7a3A-Za-z0-9]", "", str(text or "")).lower()

    def summary(self) -> str:
        """현재 메모리 상태 요약."""
        with self._lock:
            return (
                f"BatchContextMemory: "
                f"abbrevs={len(self.resolved_abbreviations)}"
                f"(+{len(self.pending_abbreviations)} pending), "
                f"authors={len(self.resolved_authors)}, "
                f"chars={len(self.resolved_characters)}, "
                f"namu_cache={len(self.namu_wiki_cache)}, "
                f"stats={self.stats}"
            )
