"""Exact-title MENTIONED observations before selection; no semantic role inference.

Public API (pure; no import-time IO):
  observe_preselection_roles(frozen_view) -> (validated_deepcopy_view, metadata)
  validate_metadata(metadata, *, frozen_view=None) -> validated JSON deepcopy
  not_executed_metadata(reason_code="NOT_EXECUTED", *, status="NOT_EXECUTED")
  SCHEMA_VERSION, POLICY, POLICY_SHA256

Metadata exact keys: schema_version, policy_sha256, status, reason_codes,
frozen_view_sha256, counts. The digest binds the enriched view. With a view,
validate_metadata independently replays the observer from its empty-role copy.
Without a view it validates metadata shape only, not source binding.
Executed statuses: OBSERVED, NO_MATCH, AMBIGUOUS. Nonexecution helper statuses:
NOT_EXECUTED, ERROR, LIMIT_EXCEEDED, INVALID_INPUT (digest/count values null).
PRIMARY/PREVIOUS/COMPARISON remain unimplemented. Aliases are not consumed.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata

SCHEMA_VERSION = "candidate_preselection_roles_v1"
MAX_MATCHES = 4096
MAX_PER_CANDIDATE = 32
MAX_TOTAL = 128
_COUNT_KEYS = ("candidates", "unique_titles", "raw_matches", "boundary_rejected",
               "ambiguous_spans", "observed_candidates", "observations")
_SUCCESS = frozenset({"OBSERVED", "NO_MATCH", "AMBIGUOUS"})
_NOT_EXECUTED = frozenset({"NOT_EXECUTED", "ERROR", "LIMIT_EXCEEDED", "INVALID_INPUT"})
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,95}\Z")
# One explicit particle, optionally followed by a bounded topic/additive/polite
# tail. The entire suffix must terminate at a non-word boundary: 은행/이름 fail.
_PARTICLES = ("은", "는", "이", "가", "을", "를", "의", "도", "만", "과", "와",
              "랑", "이랑", "보다", "처럼", "에서", "에게", "한테", "에", "로", "으로",
              "부터", "까지", "께서", "께", "밖에")
_PARTICLE_TAILS = ("", "은", "는", "도", "만", "요")
_SUFFIXES = frozenset(first + tail for first in _PARTICLES for tail in _PARTICLE_TAILS)


def _bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(value):
    return hashlib.sha256(_bytes(value)).hexdigest()


def _policy():
    return {"schema_version": SCHEMA_VERSION, "stage": "PRE_SELECTION",
            "authority": "SOURCE_OBSERVATION_NOT_GOLD", "semantic_roles_supported": ["MENTIONED"],
            "semantic_roles_not_implemented": ["PRIMARY", "PREVIOUS", "COMPARISON"],
            "surfaces": "EXACT_TITLES_ONLY_ALIASES_IGNORED", "normalization": "NONE",
            "input_roles": "MUST_BE_EMPTY", "same_title_multiple_candidates": "UNBOUND",
            "overlapping_boundary_valid_spans": "ALL_UNBOUND",
            "left_boundary": "START_OR_NON_UNICODE_WORD",
            "right_boundary": "END_OR_NON_UNICODE_WORD_OR_FULL_LISTED_KOREAN_PARTICLE",
            "word_characters": "ALNUM_UNDERSCORE_UNICODE_MARK_OR_FORMAT",
            "unicode_version": unicodedata.unidata_version,
            "korean_particles": list(_PARTICLES), "particle_tails": list(_PARTICLE_TAILS),
            "offsets": "PYTHON_UNICODE_CHARACTERS_PER_RAW_FRAGMENT",
            "span_sha256": "UTF8_EXACT_SOURCE_SLICE", "max_raw_matches": MAX_MATCHES,
            "max_roles_per_candidate": MAX_PER_CANDIDATE, "max_roles_total": MAX_TOTAL,
            "generation_status": "PRESERVED_SCORER_COMPLETE_GATE_UNCHANGED",
            "publication_authority": False, "public_apply": False, "central_db_write": False}


POLICY = _policy()
POLICY_SHA256 = _sha(POLICY)


class RoleObservationError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code):
    if not condition:
        raise RoleObservationError(code)


def _word(char):
    category = unicodedata.category(char)
    return char == "_" or char.isalnum() or category.startswith("M") or category == "Cf"


def _boundaries(text, start, end):
    if start and _word(text[start - 1]):
        return False
    if end == len(text) or not _word(text[end]):
        return True
    return any(text.startswith(suffix, end) and
               (end + len(suffix) == len(text) or not _word(text[end + len(suffix)]))
               for suffix in _SUFFIXES)


def _metadata(status, reasons, view, counts):
    return {"schema_version": SCHEMA_VERSION, "policy_sha256": _sha(_policy()),
            "status": status, "reason_codes": reasons,
            "frozen_view_sha256": _sha(view) if view is not None else None, "counts": counts}


def not_executed_metadata(reason_code="NOT_EXECUTED", *, status="NOT_EXECUTED"):
    _require(type(status) is str and status in _NOT_EXECUTED, "ROLE_METADATA_STATUS_INVALID")
    _require(type(reason_code) is str and _CODE.fullmatch(reason_code) is not None, "ROLE_METADATA_REASON_INVALID")
    return _metadata(status, [reason_code], None, dict.fromkeys(_COUNT_KEYS))


def observe_preselection_roles(frozen_view):
    """Add literal mentions only; never mutate the caller, IDs or other fields."""
    from .candidate_reranker_shadow import _validate_view
    view = _validate_view(frozen_view)
    candidates = view["candidates"]
    _require(all(not item["role_observations"] for item in candidates), "ROLE_INPUT_NOT_EMPTY")
    by_title = {}
    for index, candidate in enumerate(candidates):
        for title in candidate["titles"]:
            by_title.setdefault(title, set()).add(index)
    counts = dict.fromkeys(_COUNT_KEYS, 0)
    counts.update(candidates=len(candidates), unique_titles=len(by_title))
    # Fragment order, then source character offsets give stable observations.
    for fragment in view["source_view"]["fragments"]:
        text, matches = fragment["text"], []
        for title in sorted(by_title):
            offset = 0
            while True:
                start = text.find(title, offset)
                if start < 0:
                    break
                end, offset = start + len(title), start + 1
                counts["raw_matches"] += 1
                _require(counts["raw_matches"] <= MAX_MATCHES, "ROLE_MATCH_SCAN_LIMIT")
                if not _boundaries(text, start, end):
                    counts["boundary_rejected"] += 1
                    continue
                matches.append((start, end, title))
        matches.sort()
        ambiguous = {index for index, (_, _, title) in enumerate(matches) if len(by_title[title]) != 1}
        # All connected overlapping intervals are ambiguous, including same-ID
        # titles. No arbitrary longest-title or first-candidate tie breaking.
        cluster, high = [], -1
        for index, (start, end, _) in enumerate(matches):
            if start >= high:
                if len(cluster) > 1:
                    ambiguous.update(cluster)
                cluster = [index]
                high = end
            else:
                cluster.append(index)
                high = max(high, end)
        if len(cluster) > 1:
            ambiguous.update(cluster)
        counts["ambiguous_spans"] += len(ambiguous)
        for index, (start, end, title) in enumerate(matches):
            if index in ambiguous:
                continue
            candidate_index = next(iter(by_title[title]))
            roles = candidates[candidate_index]["role_observations"]
            _require(len(roles) < MAX_PER_CANDIDATE and counts["observations"] < MAX_TOTAL, "ROLE_OBSERVATION_LIMIT")
            roles.append({"role": "MENTIONED", "raw_path": fragment["raw_path"], "start": start, "end": end,
                          "text_sha256": hashlib.sha256(text[start:end].encode("utf-8")).hexdigest()})
            counts["observations"] += 1
    counts["observed_candidates"] = sum(bool(item["role_observations"]) for item in candidates)
    status = "OBSERVED" if counts["observations"] else "AMBIGUOUS" if counts["ambiguous_spans"] else "NO_MATCH"
    reasons = ["EXACT_TITLE_MENTIONED_ONLY"]
    if counts["boundary_rejected"]:
        reasons.append("WORD_BOUNDARY_REJECTED")
    if counts["ambiguous_spans"]:
        reasons.append("AMBIGUOUS_TITLE_SPANS_UNBOUND")
    if not counts["observations"]:
        reasons.append("NO_BOUND_TITLE_MENTION")
    # Includes the existing byte-size and role caps; never silently truncate.
    view = _validate_view(view)
    return view, _metadata(status, reasons, view, counts)


def validate_metadata(metadata, *, frozen_view=None):
    """Validate shape; a supplied enriched view additionally verifies replay."""
    _require(type(metadata) is dict and set(metadata) == {"schema_version", "policy_sha256", "status",
              "reason_codes", "frozen_view_sha256", "counts"}, "ROLE_METADATA_SCHEMA_INVALID")
    _require(metadata["schema_version"] == SCHEMA_VERSION and metadata["policy_sha256"] == _sha(_policy()),
             "ROLE_METADATA_POLICY_MISMATCH")
    status, counts, reasons = metadata["status"], metadata["counts"], metadata["reason_codes"]
    _require(type(status) is str and status in _SUCCESS | _NOT_EXECUTED, "ROLE_METADATA_STATUS_INVALID")
    _require(type(reasons) is list and 1 <= len(reasons) <= 4 and
             all(type(code) is str and _CODE.fullmatch(code) is not None for code in reasons)
             and len(set(reasons)) == len(reasons), "ROLE_METADATA_REASON_INVALID")
    _require(type(counts) is dict and set(counts) == set(_COUNT_KEYS), "ROLE_METADATA_COUNTS_INVALID")
    if status in _NOT_EXECUTED:
        _require(metadata["frozen_view_sha256"] is None and all(value is None for value in counts.values()), "ROLE_METADATA_NONEXECUTION_INVALID")
    else:
        _require(type(metadata["frozen_view_sha256"]) is str and _HASH.fullmatch(metadata["frozen_view_sha256"]) is not None,
                 "ROLE_METADATA_SHA_INVALID")
        _require(all(type(value) is int and 0 <= value <= MAX_MATCHES for value in counts.values()), "ROLE_METADATA_COUNTS_INVALID")
        _require(counts["observed_candidates"] <= counts["candidates"] <= 20
                 and counts["unique_titles"] <= counts["candidates"] * 16
                 and counts["observations"] <= MAX_TOTAL
                 and counts["observed_candidates"] <= counts["observations"] <= counts["observed_candidates"] * MAX_PER_CANDIDATE
                 and counts["raw_matches"] == counts["boundary_rejected"] + counts["ambiguous_spans"] + counts["observations"],
                 "ROLE_METADATA_COUNTS_INVALID")
        expected_status = "OBSERVED" if counts["observations"] else "AMBIGUOUS" if counts["ambiguous_spans"] else "NO_MATCH"
        _require(status == expected_status, "ROLE_METADATA_STATUS_INVALID")
        expected_reasons = ["EXACT_TITLE_MENTIONED_ONLY"]
        if counts["boundary_rejected"]:
            expected_reasons.append("WORD_BOUNDARY_REJECTED")
        if counts["ambiguous_spans"]:
            expected_reasons.append("AMBIGUOUS_TITLE_SPANS_UNBOUND")
        if not counts["observations"]:
            expected_reasons.append("NO_BOUND_TITLE_MENTION")
        _require(reasons == expected_reasons, "ROLE_METADATA_REASON_INVALID")
    if frozen_view is not None:
        from .candidate_reranker_shadow import _validate_view
        view = _validate_view(frozen_view)
        _require(status in _SUCCESS and metadata["frozen_view_sha256"] == _sha(view), "ROLE_METADATA_VIEW_MISMATCH")
        bare = json.loads(_bytes(view))
        for candidate in bare["candidates"]:
            candidate["role_observations"] = []
        expected_view, expected_meta = observe_preselection_roles(bare)
        _require(_bytes(view) == _bytes(expected_view) and _bytes(metadata) == _bytes(expected_meta), "ROLE_METADATA_REPLAY_MISMATCH")
    return json.loads(_bytes(metadata))
