"""
BatchContextMemory — 포스트 간 지식 공유 (thread-safe)

병렬 모드에서도 안전하게 사용할 수 있는 배치 컨텍스트 메모리.
해소된 약칭, 작가명, 캐릭터, namu.wiki 페이지 캐시를 포스트 간에 공유한다.
"""

from __future__ import annotations

import sys
import os
import re
import threading
import time
from difflib import SequenceMatcher
from datetime import datetime
from typing import Any, Dict, List, Optional


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


class BatchContextMemory:
    """포스트 간 지식 공유 메모리 (thread-safe)."""

    NON_NOVEL_MEDIA_ALIAS_SEED_BLOCKLIST = {
        ("강연금", "강철의연금술사"),
        ("프리렌", "장송의프리렌"),
        ("시달소", "시간을달리는소녀"),
    }

    def __init__(self, enabled: bool = True, *, seed_log_mode: Optional[str] = None):
        self._lock = threading.RLock()
        self.enabled = enabled
        raw_seed_log_mode = (
            str(seed_log_mode or os.getenv("PIPELINE_BATCHMEM_SEED_LOG_MODE", "summary") or "summary")
            .strip()
            .lower()
        )
        self.seed_log_mode = raw_seed_log_mode if raw_seed_log_mode in {"summary", "full", "off"} else "summary"
        self._seed_log_summary: Dict[str, Any] = {"counts": {}, "previews": []}

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
            "abbreviation_seed_quarantined": 0,
            "abbreviation_seed_review_held": 0,
            "abbreviation_exact_title_skipped": 0,
            "abbreviation_title_variant_surface_skipped": 0,
            "abbreviation_pending_promotion_blocked": 0,
            "abbreviation_seed_log_suppressed": 0,
            "namu_cache_hits": 0,
            "namu_cache_misses": 0,
        }

    def _record_seed_log_event(self, kind: str, abbrev: str, title: str, detail: str = "") -> None:
        if self.seed_log_mode != "summary":
            return
        with self._lock:
            counts = self._seed_log_summary.setdefault("counts", {})
            counts[kind] = int(counts.get(kind) or 0) + 1
            self.stats["abbreviation_seed_log_suppressed"] = (
                int(self.stats.get("abbreviation_seed_log_suppressed") or 0) + 1
            )
            previews = self._seed_log_summary.setdefault("previews", [])
            if len(previews) < 6:
                pair = f"{abbrev}→{title}"
                previews.append(f"{kind}:{pair}{f' ({detail})' if detail else ''}")

    def flush_seed_log_summary(self, log_fn=None) -> Optional[str]:
        """Emit one compact summary for slang-db seed preload logs."""
        if self.seed_log_mode != "summary":
            return None
        with self._lock:
            counts = dict(self._seed_log_summary.get("counts") or {})
            previews = list(self._seed_log_summary.get("previews") or [])
            self._seed_log_summary = {"counts": {}, "previews": []}
        total = sum(int(v or 0) for v in counts.values())
        if total <= 0:
            return None
        ordered_keys = [
            "registered",
            "low_evidence_hold",
            "generic_hold",
            "quarantined",
            "pending_promotion_blocked",
            "promoted",
        ]
        parts = [f"{key}={int(counts.get(key) or 0)}" for key in ordered_keys if int(counts.get(key) or 0)]
        other = sorted(k for k in counts if k not in ordered_keys)
        parts.extend(f"{key}={int(counts.get(key) or 0)}" for key in other)
        msg = f"[{_ts()}] 🧠 BatchMem seed preload summary: total={total}"
        if parts:
            msg += f" ({', '.join(parts)})"
        if previews:
            msg += f", previews=[{'; '.join(previews)}]"
        if callable(log_fn):
            log_fn(msg)
        else:
            print(msg, file=sys.stderr)
        return msg

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

    @staticmethod
    def _looks_generic_inline_alias(abbrev: str, title: str) -> bool:
        """짧은 직접 부분일치 alias는 즉시 메모리 고정하지 않는다.

        하드코딩 단어 목록 대신 구조만 본다.
        - 길이가 짧고
        - 정식 제목 내부에 그대로 연속 출현하며
        - 제목의 일부 토큰(또는 조사 붙은 토큰)만 따온 형태면
          community alias라기보다 일반 부분문자열일 가능성이 높다.
        """
        abbr_norm = re.sub(r"[^\w가-힣]", "", str(abbrev or "")).lower()
        title_norm = re.sub(r"[^\w가-힣]", "", str(title or "")).lower()
        if not abbr_norm or not title_norm or abbr_norm == title_norm:
            return False
        if len(abbr_norm) < 2 or len(abbr_norm) > 5 or re.search(r"\d", abbr_norm):
            return False
        if abbr_norm not in title_norm:
            return False

        raw_tokens = [
            re.sub(r"[^\w가-힣]", "", tok).lower()
            for tok in re.split(r"\s+", str(title or "").strip())
            if str(tok or "").strip()
        ]
        tokens = [tok for tok in raw_tokens if tok]
        token_exact = abbr_norm in tokens
        token_affix = any(
            tok != abbr_norm
            and len(tok) - len(abbr_norm) <= 2
            and (tok.startswith(abbr_norm) or tok.endswith(abbr_norm))
            for tok in tokens
        )
        contiguous_substring = abbr_norm in title_norm
        title_surplus = len(title_norm) - len(abbr_norm)
        multi_chunk_title = len(tokens) >= 2

        return bool(
            contiguous_substring
            and title_surplus >= 3
            and (token_exact or token_affix or multi_chunk_title)
        )

    @classmethod
    def _looks_like_title_variant_surface(cls, abbrev: str, title: str) -> bool:
        """긴 표면문자열이 제목 OCR/오타 변형에 가까우면 alias로 학습하지 않는다.

        개별 표현을 고정하지 않고 구조만 본다. 짧은 커뮤니티 약칭은 통과시키고,
        긴 문자열이 정식 제목과 길이/문자열 유사도가 높게 겹치는 경우만
        packet-local 표면 변형으로 본다.
        """
        abbr_norm = cls._normalize(abbrev)
        title_norm = cls._normalize(title)
        if not abbr_norm or not title_norm or abbr_norm == title_norm:
            return False
        if len(abbr_norm) < 8 or len(title_norm) < 8:
            return False
        if abbr_norm in title_norm:
            title_surplus = len(title_norm) - len(abbr_norm)
            if title_surplus >= 2 and title_surplus <= max(8, int(len(title_norm) * 0.45)):
                return True
        if abs(len(abbr_norm) - len(title_norm)) > max(2, int(len(title_norm) * 0.25)):
            return False
        similarity = SequenceMatcher(None, abbr_norm, title_norm).ratio()
        if similarity >= 0.72:
            return True
        overlap = len(set(abbr_norm) & set(title_norm)) / max(1, len(set(abbr_norm) | set(title_norm)))
        return bool(overlap >= 0.72 and (abbr_norm[:2] == title_norm[:2] or abbr_norm[-2:] == title_norm[-2:]))

    @classmethod
    def _should_quarantine_abbreviation_seed(cls, abbrev: str, title: str) -> bool:
        abbr_norm = cls._normalize(abbrev)
        title_norm = cls._normalize(title)
        if not abbr_norm or not title_norm:
            return False
        return (abbr_norm, title_norm) in cls.NON_NOVEL_MEDIA_ALIAS_SEED_BLOCKLIST

    def register_abbreviation(
        self,
        abbrev: str,
        title: str,
        confidence: int = 2,
        *,
        fast_promote: bool = False,
        allow_pending_promotion: bool = True,
        log_events: bool = True,
    ) -> None:
        """약칭-제목 매핑 등록.
        
        confidence >= 3 or fast_promote=True: 즉시 resolved
        otherwise: pending에 축적 → 2회 이상 등장 시 승격
        allow_pending_promotion=False: 저근거 seed는 반복만으로 승격하지 않음
        """
        if not self.enabled or not abbrev or not title:
            return
        key = self._normalize(abbrev)
        title_key = self._normalize(title)
        generic_inline_alias = self._looks_generic_inline_alias(abbrev, title)
        seed_quarantined = self._should_quarantine_abbreviation_seed(abbrev, title)
        with self._lock:
            if key and title_key and key == title_key:
                self.stats["abbreviation_exact_title_skipped"] = (
                    int(self.stats.get("abbreviation_exact_title_skipped") or 0) + 1
                )
                return

            if seed_quarantined:
                self.stats["abbreviation_seed_quarantined"] = (
                    int(self.stats.get("abbreviation_seed_quarantined") or 0) + 1
                )
                if log_events:
                    print(
                        f"[{_ts()}] 🧠 BatchMem: 비소설 IP 약칭 seed 보류 '{abbrev}' → '{title}'",
                        file=sys.stderr,
                    )
                else:
                    self._record_seed_log_event("quarantined", abbrev, title)
                return

            if key in self.resolved_abbreviations:
                # 이미 해소됨 — 더 높은 신뢰도면 갱신
                existing = self.resolved_abbreviations[key]
                if confidence > existing.get("confidence", 0):
                    existing["title"] = title
                    existing["confidence"] = confidence
                return

            if (fast_promote or confidence >= 3) and not generic_inline_alias:
                self.pending_abbreviations.pop(key, None)
                self.resolved_abbreviations[key] = {
                    "alias": abbrev,
                    "title": title,
                    "confidence": confidence,
                    "hits": 0,
                    "registered_at": time.time(),
                }
                if log_events:
                    print(
                        f"[{_ts()}] 🧠 BatchMem: 약칭 즉시등록 '{abbrev}' → '{title}' (conf={confidence})",
                        file=sys.stderr,
                    )
                else:
                    self._record_seed_log_event("registered", abbrev, title, f"conf={confidence}")
                return

            if generic_inline_alias:
                if log_events:
                    print(
                        f"[{_ts()}] 🧠 BatchMem: 일반명사형 약칭 즉시등록 보류 '{abbrev}' → '{title}' "
                        f"(conf={confidence})",
                        file=sys.stderr,
                    )
                else:
                    self._record_seed_log_event("generic_hold", abbrev, title, f"conf={confidence}")

            # pending에 축적
            if key not in self.pending_abbreviations:
                self.pending_abbreviations[key] = {
                    "title": title,
                    "confidence": confidence,
                    "count": 1,
                    "generic_inline_alias": bool(generic_inline_alias),
                    "allow_pending_promotion": bool(allow_pending_promotion),
                }
            else:
                pending = self.pending_abbreviations[key]
                pending["count"] += 1
                pending["generic_inline_alias"] = bool(
                    pending.get("generic_inline_alias") or generic_inline_alias
                )
                pending["allow_pending_promotion"] = bool(
                    pending.get("allow_pending_promotion", True) and allow_pending_promotion
                )
                if confidence > pending.get("confidence", 0):
                    pending["confidence"] = confidence
                    pending["title"] = title

                # 2회 이상 → 승격
                if pending["count"] >= 2:
                    blocked_reason = None
                    if pending.get("generic_inline_alias"):
                        blocked_reason = "generic_inline_alias"
                    elif not pending.get("allow_pending_promotion", True):
                        blocked_reason = "low_evidence_seed"
                    if blocked_reason:
                        self.stats["abbreviation_pending_promotion_blocked"] = (
                            int(self.stats.get("abbreviation_pending_promotion_blocked") or 0) + 1
                        )
                        if log_events:
                            print(
                                f"[{_ts()}] 🧠 BatchMem: 약칭 승격 보류 '{abbrev}' → "
                                f"'{pending['title']}' (count={pending['count']}, reason={blocked_reason})",
                                file=sys.stderr,
                            )
                        else:
                            self._record_seed_log_event(
                                "pending_promotion_blocked",
                                abbrev,
                                str(pending.get("title") or title),
                                f"count={pending['count']}, reason={blocked_reason}",
                            )
                        return
                    entry = self.pending_abbreviations.pop(key)
                    self.resolved_abbreviations[key] = {
                        "alias": abbrev,
                        "title": entry["title"],
                        "confidence": entry["confidence"],
                        "hits": 0,
                        "registered_at": time.time(),
                    }
                    if log_events:
                        print(
                            f"[{_ts()}] 🧠 BatchMem: 약칭 승격 '{abbrev}' → '{entry['title']}' "
                            f"(count={entry['count']})",
                            file=sys.stderr,
                        )
                    else:
                        self._record_seed_log_event("promoted", abbrev, str(entry.get("title") or ""), f"count={entry['count']}")

    # ─── 작가 관련 ────────────────────────────────────────

    def register_abbreviation_seed(
        self,
        abbrev: str,
        title: str,
        *,
        count: int = 0,
        source_roles: Optional[List[str]] = None,
    ) -> None:
        """slang DB seed를 batch memory에 주입한다.

        `slang_insight` 없이 result/candidate 표면에서만 저장된 저근거 seed는
        즉시 resolved로 올리지 않고 pending에 둔다. 이렇게 해야 외부 만화/애니/게임
        IP alias가 다음 run에서 hard memory처럼 되살아나는 것을 줄일 수 있다.
        """
        try:
            seed_count = int(count or 0)
        except Exception:
            seed_count = 0
        roles = {str(role or "").strip().lower() for role in (source_roles or []) if str(role or "").strip()}
        has_structured_slang_support = "slang_insight" in roles
        strong_seed = bool(seed_count >= 3 or has_structured_slang_support)
        seed_quarantined = self._should_quarantine_abbreviation_seed(abbrev, title)
        if not seed_quarantined and not strong_seed and seed_count >= 2:
            with self._lock:
                self.stats["abbreviation_seed_review_held"] = (
                    int(self.stats.get("abbreviation_seed_review_held") or 0) + 1
                )
            if self.seed_log_mode == "full":
                print(
                    f"[{_ts()}] 🧠 BatchMem: 저근거 slang seed 즉시등록 보류 '{abbrev}' → '{title}' "
                    f"(count={seed_count}, sources={sorted(roles)})",
                    file=sys.stderr,
                )
            else:
                self._record_seed_log_event(
                    "low_evidence_hold",
                    abbrev,
                    title,
                    f"count={seed_count}, sources={sorted(roles)}",
                )
        self.register_abbreviation(
            abbrev,
            title,
            confidence=3 if strong_seed else 2,
            fast_promote=strong_seed,
            allow_pending_promotion=strong_seed,
            log_events=self.seed_log_mode == "full",
        )

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

    @classmethod
    def _decoded_term_is_author_like(
        cls,
        term: Dict[str, Any],
        *,
        identified_author: Optional[str] = None,
    ) -> bool:
        """작가/person anchor로 읽힌 surface는 약칭 후보로 학습하지 않는다."""
        if not isinstance(term, dict):
            return False
        if bool(term.get("is_author_name")):
            return True
        author_info = term.get("author_info")
        if isinstance(author_info, dict):
            for key in ("detected_author", "author_name", "name"):
                if str(author_info.get(key) or "").strip():
                    return True
        elif isinstance(author_info, str) and author_info.strip():
            return True
        role_blob = " ".join(
            str(term.get(key) or "").strip().lower()
            for key in ("entity_type", "term_type", "role", "source_role")
        )
        if "author" in role_blob or "작가" in role_blob:
            return True
        original_norm = cls._normalize(str(term.get("original") or "").strip())
        author_norm = cls._normalize(str(identified_author or "").strip())
        return bool(original_norm and author_norm and original_norm == author_norm)

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
                else:
                    stripped_key = self._strip_emotive_alias_affixes(key)
                    matched_alias_key = None
                    matched_entry = None
                    if stripped_key and stripped_key != key:
                        matched_entry = self.resolved_abbreviations.get(stripped_key)
                        matched_alias_key = stripped_key if matched_entry else None
                    if matched_entry is None:
                        for alias_key, alias_entry in self.resolved_abbreviations.items():
                            if not alias_key or len(alias_key) < 3:
                                continue
                            if alias_key not in key:
                                continue
                            if self._strip_emotive_alias_affixes(key) != alias_key:
                                continue
                            matched_alias_key = alias_key
                            matched_entry = alias_entry
                            break
                    if matched_entry and matched_alias_key:
                        matched_alias = str(matched_entry.get("alias") or matched_alias_key).strip()
                        abbreviation_hints.append({
                            "abbrev": matched_alias,
                            "full": matched_entry["title"],
                            "source": "batch_memory:alias_affix_stripped",
                            "confidence": matched_entry.get("confidence", 2),
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

    def resolve_abbreviation_surface(self, surface: str) -> Optional[Dict[str, Any]]:
        """감탄사/감상어가 붙은 표면 문자열에서 확정 alias를 직접 조회한다."""
        if not self.enabled or not surface:
            return None
        key = self._normalize(surface)
        if not key:
            return None
        with self._lock:
            entry = self.resolved_abbreviations.get(key)
            matched_key = key if entry else None
            source = "batch_memory"
            if entry is None:
                stripped_key = self._strip_emotive_alias_affixes(key)
                if stripped_key and stripped_key != key:
                    entry = self.resolved_abbreviations.get(stripped_key)
                    matched_key = stripped_key if entry else None
                    source = "batch_memory:alias_affix_stripped"
                if entry is None:
                    for alias_key, alias_entry in self.resolved_abbreviations.items():
                        if not alias_key or len(alias_key) < 3:
                            continue
                        if alias_key not in key:
                            continue
                        if self._strip_emotive_alias_affixes(key) != alias_key:
                            continue
                        entry = alias_entry
                        matched_key = alias_key
                        source = "batch_memory:alias_affix_stripped"
                        break
            if not entry or not matched_key:
                return None
            entry["hits"] = int(entry.get("hits") or 0) + 1
            return {
                "alias": str(entry.get("alias") or matched_key).strip() or matched_key,
                "title": str(entry.get("title") or "").strip(),
                "confidence": entry.get("confidence", 2),
                "source": source,
            }

    @staticmethod
    def _strip_emotive_alias_affixes(norm_text: str) -> str:
        """감탄사/감상어가 붙은 짧은 alias 표면에서 alias 본체를 복원한다.

        예: "아히집악너무좋아" -> "히집악".
        """
        text = re.sub(r"[^\w가-힣]", "", str(norm_text or "")).lower().strip()
        if not text:
            return ""
        prefixes = (
            "아",
            "와",
            "오",
            "어",
            "음",
            "흠",
            "근데",
            "근대",
        )
        suffixes = (
            "너무좋아",
            "너무좋다",
            "진짜좋아",
            "개좋아",
            "좋아",
            "좋다",
            "좋네",
            "재밌네",
            "재밌다",
            "재밌음",
            "별로",
            "유치하네",
            "유치함",
            "후기",
            "리뷰",
            "봤다",
            "보고옴",
            "보고왔다",
            "어떰",
            "어때",
        )
        changed = True
        while changed:
            changed = False
            for prefix in prefixes:
                if len(text) > len(prefix) + 2 and text.startswith(prefix):
                    text = text[len(prefix):]
                    changed = True
                    break
            for suffix in suffixes:
                if len(text) > len(suffix) + 2 and text.endswith(suffix):
                    text = text[: -len(suffix)]
                    changed = True
                    break
        return text

    def get_session_knowledge(self, key_terms: Optional[List[str]] = None) -> Dict[str, Any]:
        """Decoder가 바로 사용할 수 있는 session_knowledge 형태로 반환한다."""
        if not self.enabled:
            return {"resolved_slang": {}}
        hints = self.get_prior_hints(key_terms or [])
        resolved_slang: Dict[str, Dict[str, Any]] = {}
        for hint in hints.get("abbreviation_hints") or []:
            if not isinstance(hint, dict):
                continue
            alias = str(hint.get("abbrev") or "").strip()
            title = str(hint.get("full") or "").strip()
            if not alias or not title:
                continue
            key = self._normalize(alias)
            if not key:
                continue
            resolved_slang[key] = {
                "official_title": title,
                "confidence": hint.get("confidence", 2),
                "source": hint.get("source") or "batch_memory",
            }
        return {"resolved_slang": resolved_slang}

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
        consistency_flags = {
            str(flag or "").strip()
            for flag in (identity.get("consistency_flags") or [])
            if str(flag or "").strip()
        }
        consistency_flags_norm = {flag.lower() for flag in consistency_flags}
        title_resolution_allowed = identity.get("title_resolution_allowed")
        title_resolution_state = str(identity.get("title_resolution_state") or "").strip().lower()
        if (
            title_resolution_allowed is False
            or str(title_resolution_allowed).strip().lower() in {"false", "0", "no", "off"}
            or title_resolution_state in {"context_only", "nonwork", "unresolvable_memory_query"}
            or consistency_flags_norm
            & {
                "context_only_no_work_anchor",
                "semantic_seed_review_specific_work_denied",
                "semantic_seed_review_non_title_terms_removed",
                "surface_paraphrase_non_title_terms_removed",
                "batch_memory_alias_rescue_blocked_semantic_seed",
            }
        ):
            return
        image_surface_realigned = bool(
            consistency_flags
            & {
                "official_detail_title_preferred_over_surface_form",
                "search_supported_title_preferred_over_surface_form",
                "image_surface_title_unverified_without_official_evidence",
            }
        )

        if not official_title:
            return

        conf_rank = {"max": 4, "high": 3, "medium": 2, "mid": 2, "low": 1}.get(
            str(confidence_str).strip().lower(), 1
        )
        slang_insight = identity.get("slang_insight") or {}
        preferred_aliases: List[str] = []
        blocked_surface_norms: set[str] = set()
        canonical_alias_norm = ""
        if isinstance(slang_insight, dict):
            canonical_alias = str(slang_insight.get("canonical_work_alias") or "").strip()
            detected_term = str(slang_insight.get("detected_term") or "").strip()
            store_in_db = slang_insight.get("store_in_slang_db")
            if canonical_alias:
                preferred_aliases.append(canonical_alias)
                canonical_alias_norm = self._normalize(canonical_alias)
                if detected_term and self._normalize(detected_term) != self._normalize(canonical_alias):
                    blocked_surface_norms.add(self._normalize(detected_term))
            elif detected_term and store_in_db is not False:
                preferred_aliases.append(detected_term)

        # 약칭 학습
        if conf_rank >= 2:
            for alias in preferred_aliases:
                self.register_abbreviation(
                    alias,
                    official_title,
                    confidence=conf_rank,
                    fast_promote=(conf_rank >= 3),
                )
        if decoded_terms and conf_rank >= 2:
            for term in decoded_terms:
                if not isinstance(term, dict):
                    continue
                if self._decoded_term_is_author_like(term, identified_author=identified_author):
                    with self._lock:
                        self.stats["abbreviation_author_surface_skipped"] = (
                            int(self.stats.get("abbreviation_author_surface_skipped") or 0) + 1
                        )
                    continue
                original = str(term.get("original") or "").strip()
                if canonical_alias_norm and self._normalize(original) != canonical_alias_norm:
                    continue
                if self._normalize(original) in blocked_surface_norms:
                    continue
                best_match = term.get("best_match") or {}
                if not isinstance(best_match, dict):
                    continue
                matched_title = str(best_match.get("title") or "").strip()
                if not original or not matched_title:
                    continue
                if image_surface_realigned and self._normalize(original) != self._normalize(matched_title):
                    with self._lock:
                        self.stats["abbreviation_image_surface_skipped"] = (
                            int(self.stats.get("abbreviation_image_surface_skipped") or 0) + 1
                        )
                    continue
                if self._looks_like_title_variant_surface(original, matched_title):
                    with self._lock:
                        self.stats["abbreviation_title_variant_surface_skipped"] = (
                            int(self.stats.get("abbreviation_title_variant_surface_skipped") or 0) + 1
                        )
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
