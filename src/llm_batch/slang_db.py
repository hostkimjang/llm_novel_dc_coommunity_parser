from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .experts.decoder import abbreviation_match_score
from .rules import GENRE_ARCHETYPE_TERMS

_NORMALIZE_TERM_RE = re.compile(r"[^\uac00-\ud7a3A-Za-z0-9]")

_GENERIC_TERM_STOPLIST = {
    "로판",
    "현판",
    "판타지",
    "무협",
    "소설",
    "작품",
    "작가",
    "시리즈",
    "노벨피아",
    "문피아",
    "카카페",
    "추천",
    "리뷰",
    "광고",
    "회차",
    "유료화",
    "표지",
    "신작",
    "막화",
    "결말",
    "다운",
    "기우제",
}

_GENERIC_TERM_STOPLIST_NORMALIZED = {
    _NORMALIZE_TERM_RE.sub("", item).lower().strip()
    for item in _GENERIC_TERM_STOPLIST
}
_GENRE_ARCHETYPE_TERMS_NORMALIZED = {
    _NORMALIZE_TERM_RE.sub("", item).lower().strip()
    for item in GENRE_ARCHETYPE_TERMS
}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _normalize_term(text: Any) -> str:
    return _NORMALIZE_TERM_RE.sub("", str(text or "")).lower().strip()


def _normalize_title(text: Any) -> str:
    return _normalize_term(text)


def _is_generic_term(term: str) -> bool:
    raw = str(term or "").strip()
    norm = _normalize_term(raw)
    if not norm or len(norm) < 2:
        return True
    if norm in _GENERIC_TERM_STOPLIST_NORMALIZED:
        return True
    if norm in _GENRE_ARCHETYPE_TERMS_NORMALIZED:
        return True
    if re.fullmatch(r"(로판|판무|현판|무협|bl|gl|ts|ntr|장르|웹소설)", norm):
        return True
    return False


def _is_generic_title_label(title: str) -> bool:
    raw = str(title or "").strip()
    if not raw:
        return True
    tokens = [
        _NORMALIZE_TERM_RE.sub("", tok).lower().strip()
        for tok in re.findall(r"[가-힣A-Za-z0-9]+", raw)
    ]
    tokens = [tok for tok in tokens if tok]
    if not tokens:
        return True

    genre_tokens = {
        "판타지",
        "퓨전판타지",
        "로맨스",
        "로맨스판타지",
        "로판",
        "현판",
        "무협",
        "bl",
        "gl",
        "백합",
        "ts",
        "ntr",
        "sf",
        "헌터",
        "아카데미",
        "이세계",
        "장르",
    }
    medium_tokens = {"소설", "웹소설", "장르소설", "웹툰", "만화"}
    filler_tokens = {"형식", "표지", "표기", "작품"}

    if any(tok not in genre_tokens and tok not in medium_tokens and tok not in filler_tokens for tok in tokens):
        return False
    return bool(any(tok in genre_tokens for tok in tokens) and any(tok in medium_tokens for tok in tokens))


def _looks_sentence_like_term(term: str) -> bool:
    raw = str(term or "").strip()
    if not raw:
        return True
    norm = _normalize_term(raw)
    if not norm:
        return True
    tokens = [tok for tok in re.findall(r"[가-힣A-Za-z0-9]+", raw) if tok]
    if len(tokens) >= 4:
        return True
    if len(norm) >= 18:
        return True
    if len(tokens) >= 3 and len(norm) >= 10:
        return True
    if any(ch in raw for ch in ("\n", "?", "!", "…", ";", ":")):
        return True
    separator_count = sum(raw.count(ch) for ch in (",", "/", "|", "·"))
    if separator_count >= 2:
        return True
    if separator_count >= 1 and len(tokens) >= 2:
        return True
    sentence_tail_patterns = (
        r"(뭔데|뭐냐|맞냐|아니냐|같음|같다|아쉽노|가능하다는말이있다|더보고싶었는데|보고싶었는데|해결가능하다는말이있다)$",
    )
    if len(tokens) >= 2 and any(re.search(pat, raw) for pat in sentence_tail_patterns):
        return True
    return False


def _is_exact_title_alias(term: str, title: str) -> bool:
    return bool(_normalize_term(term) and _normalize_term(term) == _normalize_title(title))


def _term_aligns_with_title(term: str, title: str) -> bool:
    term_norm = _normalize_term(term)
    title_norm = _normalize_title(title)
    if not term_norm or not title_norm:
        return False
    if term_norm == title_norm:
        return False
    if term_norm in title_norm or title_norm.startswith(term_norm):
        return True
    try:
        return float(abbreviation_match_score(term, title)) >= 0.45
    except Exception:
        return False


def _looks_strong_pipeline_alias(
    *,
    source_role: str,
    source_tier: str,
    confidence: str,
    term: str,
    official_title: str,
    candidate_title: str,
) -> bool:
    confidence_norm = str(confidence or "").strip().lower()
    source_tier_norm = str(source_tier or "").strip().lower()
    if _is_exact_title_alias(term, candidate_title):
        return False
    if _normalize_title(official_title) and _normalize_title(candidate_title) != _normalize_title(official_title):
        return False
    if source_role in {"primary_work", "title_candidate"} and confidence_norm in {"high", "medium"}:
        return True
    if source_role == "slang_insight":
        return True
    if source_tier_norm in {
        "official_detail",
        "official",
        "search_platform_url",
        "platform",
        "verified",
    }:
        return True
    return False


def _is_reviewable_context(
    *,
    topicality: str,
    subtype: str,
    work_resolution: str,
    discussion_type: str,
    anchor_type: str,
) -> bool:
    topicality_norm = str(topicality or "").strip().lower()
    subtype_norm = str(subtype or "").strip().lower()
    work_resolution_norm = str(work_resolution or "").strip().lower()
    discussion_type_norm = str(discussion_type or "").strip().lower()
    anchor_type_norm = str(anchor_type or "").strip().lower()

    if topicality_norm == "unrelated":
        return False
    if subtype_norm in {
        "daily_life",
        "realworld_social_talk",
        "cross_media_game",
        "pure_meme",
        "other_quarantine",
    }:
        return False
    if discussion_type_norm in {"noise", "undecodable_reference"} and topicality_norm != "adjacent_relevant":
        return False
    if anchor_type_norm == "image" and work_resolution_norm not in {"resolved", "unresolved", "multi_work"}:
        return False
    if topicality_norm in {"core_relevant", "adjacent_relevant"}:
        return True
    return work_resolution_norm in {"resolved", "unresolved", "multi_work"}


def _example_is_reviewable(example: Dict[str, Any]) -> bool:
    return _is_reviewable_context(
        topicality=str(example.get("topicality") or ""),
        subtype=str(example.get("subtype") or ""),
        work_resolution=str(example.get("work_resolution") or ""),
        discussion_type=str(example.get("discussion_type") or ""),
        anchor_type=str(example.get("anchor_type") or ""),
    )


def _empty_title_bucket() -> Dict[str, Any]:
    return {
        "raw_titles": [],
        "slang": [],
        "pending": [],
        "conflicts": [],
        "examples": [],
        "updated_at": None,
    }


def _empty_family_alias_bucket(term: str = "") -> Dict[str, Any]:
    raw = str(term or "").strip()
    return {
        "term": raw,
        "normalized_term": _normalize_term(raw),
        "variant_terms": [raw] if raw else [],
        "titles": [],
        "sources": [],
        "count": 0,
        "examples": [],
        "last_seen": None,
        "updated_at": None,
    }


def _normalize_bucket_shape(title: str, bucket: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    bucket = bucket if isinstance(bucket, dict) else {}
    raw_titles = bucket.get("raw_titles")
    if isinstance(raw_titles, str):
        raw_title_list = [raw_titles]
    elif isinstance(raw_titles, list):
        raw_title_list = [str(x).strip() for x in raw_titles if str(x).strip()]
    else:
        raw_title_list = []
    if str(title).strip():
        raw_title_list.append(str(title).strip())
    return {
        "raw_titles": sorted({x for x in raw_title_list if x}),
        "slang": list(bucket.get("slang") or []),
        "pending": list(bucket.get("pending") or []),
        "conflicts": list(bucket.get("conflicts") or []),
        "examples": list(bucket.get("examples") or []),
        "updated_at": bucket.get("updated_at"),
    }


def _normalize_family_alias_shape(term: str, bucket: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    bucket = bucket if isinstance(bucket, dict) else {}
    raw = str(term or bucket.get("term") or "").strip()
    variant_terms_raw = bucket.get("variant_terms")
    if isinstance(variant_terms_raw, str):
        variant_terms = [variant_terms_raw]
    elif isinstance(variant_terms_raw, list):
        variant_terms = [str(x).strip() for x in variant_terms_raw if str(x).strip()]
    else:
        variant_terms = []
    if raw:
        variant_terms.append(raw)
    titles_raw = bucket.get("titles")
    if isinstance(titles_raw, str):
        titles = [titles_raw]
    elif isinstance(titles_raw, list):
        titles = [str(x).strip() for x in titles_raw if str(x).strip()]
    else:
        titles = []
    sources_raw = bucket.get("sources")
    if isinstance(sources_raw, str):
        sources = [sources_raw]
    elif isinstance(sources_raw, list):
        sources = [str(x).strip() for x in sources_raw if str(x).strip()]
    else:
        sources = []
    display_term = min(variant_terms, key=len) if variant_terms else raw
    normalized_term = _normalize_term(display_term or raw)
    return {
        "term": display_term,
        "normalized_term": normalized_term,
        "variant_terms": sorted({x for x in variant_terms if x}),
        "titles": sorted({x for x in titles if x}),
        "sources": sorted({x for x in sources if x}),
        "count": int(bucket.get("count") or 0),
        "examples": list(bucket.get("examples") or []),
        "last_seen": bucket.get("last_seen"),
        "updated_at": bucket.get("updated_at"),
    }


def _empty_db() -> Dict[str, Any]:
    return {
        "version": 2,
        "updated_at": None,
        "titles": {},
        "family_aliases": {},
    }


class SlangDBManager:
    def __init__(
        self,
        *,
        path: Path,
        run_id: str,
        enabled: bool = False,
        flush_posts: int = 5,
        flush_seconds: int = 5,
        max_examples_per_title: int = 30,
        log_fn: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.path = Path(path)
        self.run_id = str(run_id or "").strip() or "unknown"
        self.enabled = bool(enabled)
        self.flush_posts = max(1, int(flush_posts))
        self.flush_seconds = max(1, int(flush_seconds))
        self.max_examples_per_title = max(1, int(max_examples_per_title))
        self.log_fn = log_fn
        self._db = self._load_db()
        self._processed_since_flush = 0
        self._observations_since_flush = 0
        self._touched_titles_since_flush: set[str] = set()
        self._dirty = False
        self._last_flush_monotonic = time.monotonic()

    def _load_db(self) -> Dict[str, Any]:
        if not self.enabled:
            return _empty_db()
        source_path = self.path
        if not source_path.exists():
            legacy_path = self._legacy_path()
            if legacy_path is not None and legacy_path.exists():
                source_path = legacy_path
            else:
                return _empty_db()
        try:
            payload = json.loads(source_path.read_text(encoding="utf-8"))
        except Exception:
            return _empty_db()
        if not isinstance(payload, dict):
            return _empty_db()
        titles = payload.get("titles")
        if not isinstance(titles, dict):
            payload["titles"] = {}
        family_aliases = payload.get("family_aliases")
        if not isinstance(family_aliases, dict):
            payload["family_aliases"] = {}
        payload["version"] = max(int(payload.get("version") or 0), 2)
        payload.setdefault("updated_at", None)
        for title, bucket in list((payload.get("titles") or {}).items()):
            if not isinstance(bucket, dict):
                payload["titles"][title] = _empty_title_bucket()
                continue
            payload["titles"][title] = _normalize_bucket_shape(str(title), bucket)
        for term, bucket in list((payload.get("family_aliases") or {}).items()):
            if not isinstance(bucket, dict):
                payload["family_aliases"][term] = _empty_family_alias_bucket(str(term))
                continue
            payload["family_aliases"][term] = _normalize_family_alias_shape(str(term), bucket)
        return payload

    def _legacy_path(self) -> Optional[Path]:
        try:
            if self.path.name != "slang_db.json":
                return None
            if self.path.parent.name != "slang_db":
                return None
            legacy = self.path.parent.parent / "slang_db.json"
            if legacy.resolve() == self.path.resolve():
                return None
            return legacy
        except Exception:
            return None

    def record_result(self, full_result: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        self._processed_since_flush += 1
        for obs in self._extract_observations(full_result):
            self._merge_observation(obs)
        self.maybe_flush()

    def maybe_flush(self) -> None:
        if not self.enabled or not self._dirty:
            return
        elapsed = time.monotonic() - self._last_flush_monotonic
        if self._processed_since_flush >= self.flush_posts:
            self.flush(force=True, reason=f"posts>={self.flush_posts}")
            return
        if elapsed >= self.flush_seconds:
            self.flush(force=True, reason=f"seconds>={self.flush_seconds}")

    def flush(self, *, force: bool = False, reason: str = "manual") -> None:
        if not self.enabled:
            return
        if not self._dirty and not force:
            return
        buffered_posts = self._processed_since_flush
        buffered_observations = self._observations_since_flush
        touched_titles = sorted(self._touched_titles_since_flush)
        self._rebuild_conflicts()
        written_at = _now_iso()
        self._db["version"] = max(int(self._db.get("version") or 0), 2)
        self._db["updated_at"] = written_at
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(self._db, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(self.path)
        self._log_flush(
            buffered_posts=buffered_posts,
            buffered_observations=buffered_observations,
            touched_titles=touched_titles,
            written_at=written_at,
            reason=reason,
        )
        self._processed_since_flush = 0
        self._observations_since_flush = 0
        self._touched_titles_since_flush.clear()
        self._dirty = False
        self._last_flush_monotonic = time.monotonic()

    def finalize(self) -> None:
        if not self.enabled:
            return
        self.flush(force=True, reason="finalize")

    @property
    def data(self) -> Dict[str, Any]:
        return self._db

    def _ensure_bucket(self, title: str) -> Dict[str, Any]:
        titles = self._db.setdefault("titles", {})
        if title not in titles or not isinstance(titles[title], dict):
            titles[title] = _empty_title_bucket()
        titles[title] = _normalize_bucket_shape(title, titles[title])
        bucket = titles[title]
        return bucket

    def _ensure_family_alias_bucket(self, term: str) -> Tuple[str, Dict[str, Any]]:
        family_aliases = self._db.setdefault("family_aliases", {})
        normalized = _normalize_term(term)
        if not normalized:
            key = str(term or "").strip()
            family_aliases[key] = _normalize_family_alias_shape(key, family_aliases.get(key))
            return key, family_aliases[key]

        for key, bucket in list(family_aliases.items()):
            bucket_norm = _normalize_term((bucket or {}).get("normalized_term") or key)
            if bucket_norm == normalized:
                family_aliases[key] = _normalize_family_alias_shape(str(key), bucket)
                return key, family_aliases[key]

        key = str(term or "").strip() or normalized
        family_aliases[key] = _empty_family_alias_bucket(key)
        family_aliases[key] = _normalize_family_alias_shape(key, family_aliases[key])
        return key, family_aliases[key]

    def _remove_alias_from_title_buckets(self, normalized_term: str) -> None:
        if not normalized_term:
            return
        titles = self._db.setdefault("titles", {})
        for title, bucket in list(titles.items()):
            if not isinstance(bucket, dict):
                continue
            bucket["slang"] = [
                item
                for item in (bucket.get("slang") or [])
                if _normalize_term(item.get("normalized_term") or item.get("term")) != normalized_term
            ]
            bucket["pending"] = [
                item
                for item in (bucket.get("pending") or [])
                if _normalize_term(item.get("normalized_term") or item.get("term")) != normalized_term
            ]
            bucket["conflicts"] = [
                item
                for item in (bucket.get("conflicts") or [])
                if _normalize_term(item.get("normalized_term") or item.get("term")) != normalized_term
            ]
            titles[title] = _normalize_bucket_shape(title, bucket)

    def _merge_family_alias_observation(self, obs: Dict[str, Any]) -> None:
        term = str(obs.get("term") or "").strip()
        if not term:
            return
        title = str(obs.get("official_title") or "").strip()
        normalized_term = _normalize_term(term)
        if not normalized_term:
            return

        key, bucket = self._ensure_family_alias_bucket(term)
        variant_terms = set(str(x).strip() for x in (bucket.get("variant_terms") or []) if str(x).strip())
        variant_terms.add(term)
        bucket["variant_terms"] = sorted(variant_terms)
        bucket["term"] = min(bucket["variant_terms"], key=len) if bucket["variant_terms"] else term
        bucket["normalized_term"] = normalized_term
        if title:
            titles = set(str(x).strip() for x in (bucket.get("titles") or []) if str(x).strip())
            titles.add(title)
            bucket["titles"] = sorted(titles)
        bucket["count"] = int(bucket.get("count") or 0) + 1
        bucket["last_seen"] = obs.get("seen_at") or _now_iso()
        sources = set(str(x).strip() for x in (bucket.get("sources") or []) if str(x).strip())
        sources.update(str(x).strip() for x in (obs.get("sources") or []) if str(x).strip())
        bucket["sources"] = sorted(sources)

        example = dict(obs.get("example") or {})
        if example:
            examples = bucket.get("examples") or []
            example_key = (
                str(example.get("post_id") or ""),
                normalized_term,
                str(example.get("official_title") or "").strip(),
            )
            if not any(
                (
                    str(e.get("post_id") or ""),
                    _normalize_term(e.get("alias") or ""),
                    str(e.get("official_title") or "").strip(),
                ) == example_key
                for e in examples
            ):
                examples.append(example)
                if len(examples) > self.max_examples_per_title:
                    del examples[:-self.max_examples_per_title]
            bucket["examples"] = examples

        bucket["updated_at"] = obs.get("seen_at") or _now_iso()
        self._db.setdefault("family_aliases", {})[key] = _normalize_family_alias_shape(key, bucket)
        self._remove_alias_from_title_buckets(normalized_term)
        self._observations_since_flush += 1
        self._touched_titles_since_flush.add(f"family_alias:{key}")
        self._dirty = True

    def _merge_observation(self, obs: Dict[str, Any]) -> None:
        title = str(obs.get("official_title") or "").strip()
        term = str(obs.get("term") or "").strip()
        bucket_name = str(obs.get("bucket") or "").strip().lower()
        if bucket_name == "family_alias":
            self._merge_family_alias_observation(obs)
            return
        if not title or not term:
            return
        bucket = self._ensure_bucket(title)
        target_key = "slang" if obs.get("bucket") == "slang" else "pending"
        entries = bucket[target_key]
        normalized_term = _normalize_term(term)
        if not normalized_term:
            return

        existing = None
        for entry in entries:
            if _normalize_term(entry.get("normalized_term") or entry.get("term")) == normalized_term:
                existing = entry
                break

        if existing is None:
            existing = {
                "term": term,
                "normalized_term": normalized_term,
                "count": 0,
                "sources": [],
                "last_seen": None,
            }
            entries.append(existing)

        existing["term"] = term if len(term) >= len(str(existing.get("term") or "")) else existing.get("term")
        existing["count"] = int(existing.get("count") or 0) + 1
        existing["last_seen"] = obs.get("seen_at") or _now_iso()
        existing_sources = {str(x) for x in (existing.get("sources") or []) if str(x).strip()}
        existing_sources.update(str(x) for x in (obs.get("sources") or []) if str(x).strip())
        existing["sources"] = sorted(existing_sources)
        if target_key == "slang":
            bucket["pending"] = [
                item
                for item in (bucket.get("pending") or [])
                if _normalize_term(item.get("normalized_term") or item.get("term")) != normalized_term
            ]
        raw_titles = bucket.get("raw_titles")
        if isinstance(raw_titles, str):
            raw_titles = [raw_titles]
        elif not isinstance(raw_titles, list):
            raw_titles = []
        if title not in raw_titles:
            raw_titles.append(title)
        bucket["raw_titles"] = sorted({str(x).strip() for x in raw_titles if str(x).strip()})
        bucket = _normalize_bucket_shape(title, bucket)
        self._db.setdefault("titles", {})[title] = bucket

        example = dict(obs.get("example") or {})
        if example:
            examples = bucket["examples"]
            example_key = (
                str(example.get("post_id") or ""),
                normalized_term,
                str(example.get("bucket") or target_key),
            )
            if not any(
                (
                    str(e.get("post_id") or ""),
                    _normalize_term(e.get("alias") or ""),
                    str(e.get("bucket") or ""),
                ) == example_key
                for e in examples
            ):
                examples.append(example)
                if len(examples) > self.max_examples_per_title:
                    del examples[:-self.max_examples_per_title]

        bucket["updated_at"] = obs.get("seen_at") or _now_iso()
        self._observations_since_flush += 1
        self._touched_titles_since_flush.add(title)
        self._dirty = True

    def _log_flush(
        self,
        *,
        buffered_posts: int,
        buffered_observations: int,
        touched_titles: List[str],
        written_at: str,
        reason: str,
    ) -> None:
        if not self.log_fn:
            return
        title_preview = ", ".join(touched_titles[:5])
        if len(touched_titles) > 5:
            title_preview += f" ... (+{len(touched_titles) - 5})"
        if not title_preview:
            title_preview = "-"
        self.log_fn(
            "🗂️ Slang DB flush: "
            f"reason={reason}, buffered_posts={buffered_posts}, buffered_observations={buffered_observations}, "
            f"titles={len(touched_titles)} [{title_preview}], written_at={written_at}, path={self.path}"
        )

    def _rebuild_conflicts(self) -> None:
        titles = self._db.setdefault("titles", {})
        family_aliases = self._db.setdefault("family_aliases", {})
        self._prune_unreviewable_entries()
        for key, bucket in list(family_aliases.items()):
            normalized = _normalize_term((bucket or {}).get("normalized_term") or key)
            titles_list = [str(x).strip() for x in ((bucket or {}).get("titles") or []) if str(x).strip()]
            examples = list((bucket or {}).get("examples") or [])
            if not normalized or (not titles_list and not examples):
                family_aliases.pop(key, None)
                continue
            family_aliases[key] = _normalize_family_alias_shape(key, bucket)
        family_alias_norms = {
            _normalize_term((bucket or {}).get("normalized_term") or key)
            for key, bucket in family_aliases.items()
            if _normalize_term((bucket or {}).get("normalized_term") or key)
        }
        for title, bucket in list(titles.items()):
            if not isinstance(bucket, dict):
                continue
            for source_key in ("slang", "pending", "conflicts"):
                bucket[source_key] = [
                    item
                    for item in (bucket.get(source_key) or [])
                    if _normalize_term(item.get("normalized_term") or item.get("term")) not in family_alias_norms
                ]
            titles[title] = _normalize_bucket_shape(title, bucket)

        alias_map: Dict[str, List[Tuple[str, Dict[str, Any], str]]] = {}
        for title, bucket in titles.items():
            if not isinstance(bucket, dict):
                continue
            bucket["conflicts"] = []
            for source_key in ("slang", "pending"):
                for entry in (bucket.get(source_key) or []):
                    norm = _normalize_term(entry.get("normalized_term") or entry.get("term"))
                    if not norm or norm in family_alias_norms:
                        continue
                    alias_map.setdefault(norm, []).append((title, entry, source_key))
            for example in (bucket.get("examples") or []):
                if not isinstance(example, dict):
                    continue
                alias = str(example.get("alias") or "").strip()
                if (
                    not alias
                    or _is_generic_term(alias)
                    or _looks_sentence_like_term(alias)
                    or _is_exact_title_alias(alias, title)
                ):
                    continue
                norm = _normalize_term(alias)
                if not norm or norm in family_alias_norms:
                    continue
                alias_map.setdefault(norm, []).append(
                    (
                        title,
                        {
                            "term": alias,
                            "last_seen": example.get("seen_at") or bucket.get("updated_at"),
                        },
                        "example",
                    )
                )

        for norm_term, refs in list(alias_map.items()):
            title_names = sorted({title for title, _, _ in refs})
            if len(title_names) < 3:
                continue
            display_term = ""
            last_seen = ""
            sources = set()
            examples: List[Dict[str, Any]] = []
            for title, entry, source_key in refs:
                if source_key in {"slang", "pending"}:
                    bucket = titles.get(title) or {}
                    bucket["slang"] = [
                        item for item in (bucket.get("slang") or [])
                        if _normalize_term(item.get("normalized_term") or item.get("term")) != norm_term
                    ]
                    bucket["pending"] = [
                        item for item in (bucket.get("pending") or [])
                        if _normalize_term(item.get("normalized_term") or item.get("term")) != norm_term
                    ]
                    titles[title] = _normalize_bucket_shape(title, bucket)
                if not display_term:
                    display_term = str(entry.get("term") or "").strip()
                last_seen = max(last_seen, str(entry.get("last_seen") or ""))
                if source_key and source_key != "example":
                    sources.add(str(source_key))
            for title in title_names:
                bucket = titles.get(title) or {}
                examples.extend(
                    [
                        e for e in (bucket.get("examples") or [])
                        if _normalize_term(e.get("alias") or "") == norm_term
                    ]
                )

            key, family_bucket = self._ensure_family_alias_bucket(display_term or norm_term)
            family_bucket["titles"] = sorted({*list(family_bucket.get("titles") or []), *title_names})
            family_bucket["sources"] = sorted({*list(family_bucket.get("sources") or []), *sources})
            family_bucket["count"] = max(int(family_bucket.get("count") or 0), len(examples))
            family_bucket["last_seen"] = last_seen or family_bucket.get("last_seen") or _now_iso()
            merged_examples = list(family_bucket.get("examples") or [])
            for example in examples[-self.max_examples_per_title :]:
                example_key = (
                    str(example.get("post_id") or ""),
                    _normalize_term(example.get("alias") or ""),
                    str(example.get("official_title") or "").strip(),
                )
                if any(
                    (
                        str(e.get("post_id") or ""),
                        _normalize_term(e.get("alias") or ""),
                        str(e.get("official_title") or "").strip(),
                    ) == example_key
                    for e in merged_examples
                ):
                    continue
                merged_examples.append(example)
            if len(merged_examples) > self.max_examples_per_title:
                del merged_examples[:-self.max_examples_per_title]
            family_bucket["examples"] = merged_examples
            family_bucket["updated_at"] = family_bucket.get("last_seen")
            family_aliases[key] = _normalize_family_alias_shape(key, family_bucket)
            family_alias_norms.add(norm_term)
            alias_map.pop(norm_term, None)

        for norm_term, refs in alias_map.items():
            title_names = sorted({title for title, _, _ in refs})
            if len(title_names) <= 1:
                continue
            display_term = ""
            last_seen = ""
            for title, entry, source_key in refs:
                if source_key in {"slang", "pending"}:
                    bucket = titles.get(title) or {}
                    bucket["slang"] = [
                        item for item in (bucket.get("slang") or [])
                        if _normalize_term(item.get("normalized_term") or item.get("term")) != norm_term
                    ]
                    bucket["pending"] = [
                        item for item in (bucket.get("pending") or [])
                        if _normalize_term(item.get("normalized_term") or item.get("term")) != norm_term
                    ]
                if not display_term:
                    display_term = str(entry.get("term") or "").strip()
                last_seen = max(last_seen, str(entry.get("last_seen") or ""))

            for title in title_names:
                bucket = titles.get(title) or {}
                examples = [
                    e for e in (bucket.get("examples") or [])
                    if _normalize_term(e.get("alias") or "") == norm_term
                ]
                bucket["conflicts"] = [
                    item for item in (bucket.get("conflicts") or [])
                    if _normalize_term(item.get("normalized_term") or item.get("term")) != norm_term
                ]
                bucket["conflicts"].append(
                    {
                        "term": display_term or norm_term,
                        "normalized_term": norm_term,
                        "titles": title_names,
                        "post_ids": sorted(
                            {
                                int(e.get("post_id"))
                                for e in examples
                                if str(e.get("post_id") or "").isdigit()
                            }
                        ),
                        "examples": examples[-5:],
                        "last_seen": last_seen or _now_iso(),
                    }
                )

    def _prune_unreviewable_entries(self) -> None:
        titles = self._db.setdefault("titles", {})
        for title, bucket in list(titles.items()):
            if not isinstance(bucket, dict):
                continue
            examples = list(bucket.get("examples") or [])
            if not isinstance(examples, list):
                examples = []
            pending_entries = list(bucket.get("pending") or [])
            kept_pending: List[Dict[str, Any]] = []
            removed_norms: set[str] = set()

            for entry in pending_entries:
                norm = _normalize_term(entry.get("normalized_term") or entry.get("term"))
                if not norm:
                    continue
                matching_examples = [
                    e for e in examples
                    if _normalize_term(e.get("alias") or "") == norm
                ]
                if matching_examples and not any(_example_is_reviewable(e) for e in matching_examples):
                    removed_norms.add(norm)
                    continue
                kept_pending.append(entry)

            if removed_norms:
                bucket["pending"] = kept_pending
                bucket["examples"] = [
                    e for e in examples
                    if not (
                        _normalize_term(e.get("alias") or "") in removed_norms
                        and str(e.get("bucket") or "") == "pending"
                    )
                ]
                bucket["updated_at"] = _now_iso()

            if not (bucket.get("slang") or bucket.get("pending") or bucket.get("conflicts") or bucket.get("examples")):
                titles.pop(title, None)

    def _extract_observations(self, full_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        result_dict = ((full_result or {}).get("analysis_result") or {})
        if not isinstance(result_dict, dict):
            return []
        identity = result_dict.get("identity") or {}
        if not isinstance(identity, dict):
            return []

        topicality = str(identity.get("topicality") or "").strip().lower()
        subtype = str(identity.get("subtype") or "").strip().lower()
        work_resolution = str(identity.get("work_resolution") or "").strip().lower()
        anchor_type = str(identity.get("anchor_type") or "").strip().lower()
        anchor_strength = str(identity.get("anchor_strength") or "").strip()
        discussion_type = str(identity.get("discussion_type") or "").strip()
        consistency_flags = {
            str(flag or "").strip().lower()
            for flag in (identity.get("consistency_flags") or [])
            if str(flag or "").strip()
        }
        novel_identity = identity.get("novel_identity") or {}
        if not isinstance(novel_identity, dict):
            novel_identity = {}
        official_title = str(novel_identity.get("official_title") or "").strip()
        heretic_url = str(novel_identity.get("heretic_url") or "").strip()
        confidence = str(novel_identity.get("confidence") or "").strip()
        reason = str(identity.get("reason") or "")
        slang_insight = identity.get("slang_insight") or {}
        if not isinstance(slang_insight, dict):
            slang_insight = {}
        is_reviewable_context = _is_reviewable_context(
            topicality=topicality,
            subtype=subtype,
            work_resolution=work_resolution,
            discussion_type=discussion_type,
            anchor_type=anchor_type,
        )
        if not is_reviewable_context:
            return []

        is_confirmable = bool(
            topicality == "core_relevant"
            and work_resolution == "resolved"
            and official_title
            and subtype not in {
                "author_meta",
                "platform_meta",
                "release_serialization_meta",
                "recommendation_request",
                "genre_trope_discussion",
                "community_work_banter",
                "multi_work_compare",
            }
            and (
                bool(heretic_url)
                or "official_title_evidence: true" in reason.lower()
                or anchor_type in {"title_exact", "title_alias", "character", "image"}
            )
        )

        seen_at = _now_iso()
        example_base = {
            "post_id": full_result.get("post_id"),
            "run_id": self.run_id,
            "topicality": topicality or None,
            "subtype": subtype or None,
            "work_resolution": work_resolution or None,
            "confidence": confidence or None,
            "anchor_type": anchor_type or None,
            "anchor_strength": anchor_strength or None,
            "created_at": full_result.get("created_at"),
            "discussion_type": discussion_type or None,
            "consistency_flags": sorted(consistency_flags) if consistency_flags else None,
        }
        family_alias_signal = bool(
            consistency_flags & {
                "family_alias_precision_hold",
                "family_alias_group_unresolved",
                "family_alias_announcement_unresolved",
            }
        )

        slang_fallback_title = ""
        slang_fallback_source_tier = ""
        allow_pending_slang_insight = bool(
            not official_title
            and topicality == "core_relevant"
            and work_resolution in {"resolved", "unresolved"}
            and subtype not in {
                "author_meta",
                "platform_meta",
                "release_serialization_meta",
                "recommendation_request",
                "genre_trope_discussion",
                "community_work_banter",
                "multi_work_compare",
            }
            and discussion_type not in {"noise", "author_talk", "meta", "undecodable_reference"}
        )

        refs: Dict[Tuple[str, str], Dict[str, Any]] = {}

        def _append_ref(
            source_role: str,
            title: Any,
            term: Any,
            *,
            confidence_hint: Any = None,
            source_tier: Any = None,
        ) -> None:
            title_raw = str(title or "").strip()
            term_raw = str(term or "").strip()
            if (
                not title_raw
                or not term_raw
                or _is_generic_term(term_raw)
                or _is_generic_title_label(title_raw)
                or _looks_sentence_like_term(term_raw)
                or _is_exact_title_alias(term_raw, title_raw)
            ):
                return
            confidence_raw = str(confidence_hint or "").strip()
            source_tier_raw = str(source_tier or "").strip()
            if (
                not official_title
                and consistency_flags & {
                    "verifier_title_repromotion_veto",
                    "canonical_title_blocked",
                }
                and source_role in {"slang_insight", "primary_work", "title_candidate"}
            ):
                return
            aligns = _term_aligns_with_title(term_raw, title_raw)
            if not aligns and not _looks_strong_pipeline_alias(
                source_role=source_role,
                source_tier=source_tier_raw,
                confidence=confidence_raw,
                term=term_raw,
                official_title=official_title,
                candidate_title=title_raw,
            ):
                return
            key = (_normalize_title(title_raw), _normalize_term(term_raw))
            existing = refs.get(key)
            if existing is None:
                refs[key] = {
                    "title": title_raw,
                    "term": term_raw,
                    "sources": {source_role},
                    "family_alias": bool(
                        family_alias_signal
                        and source_role in {"slang_insight", "primary_work", "title_candidate"}
                    ),
                }
                return
            if len(term_raw) >= len(str(existing.get("term") or "")):
                existing["term"] = term_raw
            if len(title_raw) >= len(str(existing.get("title") or "")):
                existing["title"] = title_raw
            existing["sources"].add(source_role)
            existing["family_alias"] = bool(
                existing.get("family_alias")
                or (
                    family_alias_signal
                    and source_role in {"slang_insight", "primary_work", "title_candidate"}
                )
            )

        def _iter_title_objs(raw: Any) -> List[Dict[str, Any]]:
            if isinstance(raw, dict):
                return [raw]
            if isinstance(raw, list):
                return [x for x in raw if isinstance(x, dict)]
            return []

        if allow_pending_slang_insight:
            decoded_term = str(slang_insight.get("decoded_term") or "").strip()
            for obj in _iter_title_objs(identity.get("primary_work")) + _iter_title_objs(identity.get("title_candidates")):
                cand_title = str((obj or {}).get("official_title") or "").strip()
                if not cand_title or _is_generic_title_label(cand_title):
                    continue
                if decoded_term and _normalize_title(decoded_term) != _normalize_title(cand_title):
                    continue
                slang_fallback_title = cand_title
                slang_fallback_source_tier = str((obj or {}).get("source_tier") or "").strip()
                break

        if official_title or slang_fallback_title:
            _append_ref(
                "slang_insight",
                official_title or slang_fallback_title or slang_insight.get("decoded_term"),
                slang_insight.get("detected_term"),
                confidence_hint=confidence or slang_insight.get("confidence"),
                source_tier="verified" if official_title else (slang_fallback_source_tier or "pending"),
            )

        for obj in _iter_title_objs(identity.get("primary_work")):
            _append_ref(
                "primary_work",
                obj.get("official_title") or official_title,
                obj.get("alias_or_mention"),
                confidence_hint=obj.get("confidence") or confidence,
                source_tier=obj.get("source_tier"),
            )
        for obj in _iter_title_objs(identity.get("title_candidates")):
            _append_ref(
                "title_candidate",
                obj.get("official_title"),
                obj.get("alias_or_mention"),
                confidence_hint=obj.get("confidence") or confidence,
                source_tier=obj.get("source_tier"),
            )
        for obj in _iter_title_objs(identity.get("mentioned_works")):
            _append_ref(
                "mentioned_work",
                obj.get("official_title"),
                obj.get("alias_or_mention"),
                confidence_hint=obj.get("confidence") or confidence,
                source_tier=obj.get("source_tier"),
            )
        for obj in _iter_title_objs(identity.get("secondary_reference_works")):
            _append_ref(
                "secondary_reference",
                obj.get("official_title"),
                obj.get("alias_or_mention"),
                confidence_hint=obj.get("confidence") or confidence,
                source_tier=obj.get("source_tier"),
            )
        for obj in _iter_title_objs(identity.get("recommendation_candidates")):
            _append_ref(
                "recommendation_candidate",
                obj.get("official_title"),
                obj.get("alias_or_mention"),
                confidence_hint=obj.get("confidence") or confidence,
                source_tier=obj.get("source_tier"),
            )
        for obj in _iter_title_objs(identity.get("comparison_target")):
            _append_ref(
                "comparison_target",
                obj.get("official_title"),
                obj.get("alias_or_mention"),
                confidence_hint=obj.get("confidence") or confidence,
                source_tier=obj.get("source_tier"),
            )

        observations: List[Dict[str, Any]] = []
        for ref in refs.values():
            title = str(ref.get("title") or "").strip()
            term = str(ref.get("term") or "").strip()
            source_roles = sorted(str(x) for x in (ref.get("sources") or set()) if str(x).strip())
            if ref.get("family_alias"):
                bucket = "family_alias"
            else:
                bucket = "slang" if (is_confirmable and _normalize_title(title) == _normalize_title(official_title)) else "pending"
            observations.append(
                {
                    "official_title": title,
                    "term": term,
                    "bucket": bucket,
                    "sources": source_roles,
                    "seen_at": seen_at,
                    "example": {
                        **example_base,
                        "alias": term,
                        "official_title": title,
                        "bucket": bucket,
                        "source_role": source_roles[0] if source_roles else None,
                        "source_roles": source_roles,
                    },
                }
            )

        return observations
