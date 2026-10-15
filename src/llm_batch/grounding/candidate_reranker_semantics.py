"""고정 후보의 원문 출현별 의미역할 관측. 순수 SHADOW; 점수/정답/공개 권한 없음.

기존 v1 정책과 최종 context projection을 호출/변경하지 않는다. 작성자 절
정렬/인용/단언 검사만 재사용하고, 원문에 명시된 작은 관계 문법을 적용한다.
"""
from __future__ import annotations

import hashlib
import json
import re

from . import candidate_reranker_roles as _roles
from .claim_scope_contract import ASSERTED, ClaimScopeSource, Clause, clause_assertion
from .context_projection_contract import _author_clause_cut, _author_line_clauses, _negated_at

SCHEMA_VERSION = "candidate_preselection_semantics_v2"
SCORE_CONSUMPTION_STATUS = "NOT_CONSUMED_MODEL_POLICY_UNBOUND"
MAX_MATCHES = 4096
MAX_PER_CANDIDATE = 32
MAX_TOTAL = 128
MAX_RECEIPT_BYTES = 65536
MAX_UNRESOLVED = 128
_COUNTS = ("candidates", "unique_surfaces", "raw_matches", "boundary_rejected",
           "ambiguous_spans", "observed_candidates", "observations", "semantic_observations",
           "primary", "previous", "comparison", "mentioned", "unresolved", "alias_observations")
_NONEXEC = ("NOT_EXECUTED", "ERROR", "LIMIT_EXCEEDED", "INVALID_INPUT")
_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,95}\Z")
_SELF = r"(?:나는|저는|내가|제가|난|이 글에서는|이 글에서|이번 글에서는|이번 글에서)\s+"
_PRIMARY_ACT = r"(?:리뷰|평가|논의|소개|분석)(?:한다|합니다|했다|했습니다)"
_PREVIOUS = r"(?:전작|이전\s+작품)"
_AUTHOR = r"(?P<author>[가-힣A-Za-z][가-힣A-Za-z0-9]{1,23}\s+작가)"
_COP = r"(?:이다|입니다|이었다|였습니다|임)"
_COMPARATIVE = r"(?:재미있다|재밌다|좋다|낫다|길다|짧다|빠르다|느리다)"
_PRED_END = r"(?=$|[^가-힣A-Za-z0-9_]|고|며|는|던|더|면)"
_COPULA_SUFFIXES = tuple(cop + tail for cop in ("이다", "입니다", "이었다", "였습니다", "임")
    for tail in ("", "고", "라고", "며", "라며", "는", "라는", "면", "더라", "던데"))
_INELIGIBLE_AUTHOR = frozenset({"그", "이", "해당", "어떤", "다른", "같은", "한", "전", "현", "익명"})
_DEFER = re.compile(r"다고|라고|다며|라며|다는|라는|이라면|한다면|라면|카더라|더라|던데|듯|것\s*같|거\s*같|아니|않|못\s|(?<![가-힣])안\s|말고|빼고|제외")
_QUOTE_PAIRS = {"“": "”", "‘": "’", "「": "」", "『": "』", '"': '"', "'": "'"}
_SPEAKER_LABEL = re.compile(r"^\s*(?:[-*>]\s*)?(?P<label>[^:：\r\n]+?)[:：]")
_CONDITIONAL_SUFFIX = re.compile(r"^면")


def _bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(value):
    return hashlib.sha256(_bytes(value)).hexdigest()


PARSER_CONTRACT = {"version": "context_projection_native_v33_source_helpers_v1",
    "helpers": ["_author_line_clauses", "_author_clause_cut", "_negated_at", "clause_assertion"],
    "mapping": "RAW_CONTIGUOUS_ONLY", "final_projection": False}
PARSER_CONTRACT_SHA256 = _sha(PARSER_CONTRACT)
POLICY = {"schema_version": SCHEMA_VERSION, "parser_contract_sha256": PARSER_CONTRACT_SHA256,
    "mention_policy_sha256": _roles.POLICY_SHA256, "input_roles": "MUST_BE_EMPTY",
    "additional_complete_copula_boundaries": list(_COPULA_SUFFIXES),
    "authority": "SOURCE_OBSERVATION_NOT_GOLD", "semantic_scope": "PER_OCCURRENCE_AUTHOR_ASSERTION",
    "grammar": {"self": _SELF, "primary_act": _PRIMARY_ACT, "previous": _PREVIOUS,
        "author": _AUTHOR, "copula": _COP, "comparative": _COMPARATIVE, "predicate_end": _PRED_END,
        "defer": _DEFER.pattern, "ineligible_authors": sorted(_INELIGIBLE_AUTHOR),
        "speaker_label": _SPEAKER_LABEL.pattern, "conditional_suffix": _CONDITIONAL_SUFFIX.pattern},
    "rules": ["AUTHOR_EXPLICIT_REVIEW", "AUTHOR_EXPLICIT_REVIEW_OBJECT",
        "NAMED_AUTHOR_PREVIOUS", "SAME_AUTHOR_PREVIOUS", "DIRECTED_THAN_COMPARISON", "DIRECTED_SIMILAR_COMPARISON"],
    "comments": "MENTIONED_ONLY", "ambiguity": "ALL_OVERLAPS_AND_SHARED_SURFACES_UNBOUND",
    "conflicts": "MENTIONED_ONLY", "aliases": "VALIDATED_EXPLICIT_EVIDENCE_ONLY",
    "unbalanced_quotation": "SEMANTICS_DEFERRED", "semantic_candidate_gate": "ELIGIBLE_WORK_WITHOUT_IDENTITY_CONFLICT",
    "quote_context": {"version": "raw_nested_quote_carry_v1", "pairs": _QUOTE_PAIRS,
        "body_fragments": "CARRIED_IN_SOURCE_ORDER", "title_and_comments": "SEPARATE",
        "unclosed_or_crossed": "DEFER_TO_CONTEXT_END", "word_internal_apostrophe": "OPAQUE"},
    "speaker_context": "UNQUOTED_CLAUSE_LABEL_THROUGH_LINE_OR_UNCLOSED_LABEL_BLOCK_DEFERRED",
    "speaker_label_exceptions": "OPAQUE_CANDIDATE_TITLE_URL_SCHEME_NUMERIC_TIME_V1",
    "offsets": "RAW_FRAGMENT_UNICODE_AND_UTF8", "score_consumption_status": SCORE_CONSUMPTION_STATUS,
    "max_raw_matches": MAX_MATCHES, "max_per_candidate": MAX_PER_CANDIDATE, "max_total": MAX_TOTAL,
    "max_unresolved": MAX_UNRESOLVED, "max_receipt_bytes": MAX_RECEIPT_BYTES,
    "publication_authority": False, "public_apply": False, "central_db_write": False}
POLICY_SHA256 = _sha(POLICY)


class SemanticObservationError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code):
    if not condition:
        raise SemanticObservationError(code)


def _seal(receipt):
    receipt["receipt_sha256"] = _sha({k: v for k, v in receipt.items() if k != "receipt_sha256"})
    _require(len(_bytes(receipt)) <= MAX_RECEIPT_BYTES, "SEMANTIC_RECEIPT_BYTE_LIMIT")
    return receipt


def _receipt(status, reasons, original=None, view=None, alias_validation=None, alias_evidence=None):
    source_sha = _sha(original["source_view"]) if original is not None else None
    return {"schema_version": SCHEMA_VERSION, "policy_sha256": POLICY_SHA256,
        "parser_contract_sha256": PARSER_CONTRACT_SHA256, "status": status, "reason_codes": reasons,
        "score_consumption_status": SCORE_CONSUMPTION_STATUS, "source_view_sha256": source_sha,
        "query_sha256": source_sha, "input_frozen_view_sha256": _sha(original) if original is not None else None,
        "frozen_view_sha256": _sha(view) if view is not None else None,
        "candidate_ids_sha256": _sha([c["candidate_id"] for c in original["candidates"]]) if original is not None else None,
        "alias_evidence_sha256": _sha(alias_evidence) if alias_evidence is not None else None,
        "alias_validation": alias_validation, "counts": dict.fromkeys(_COUNTS, 0 if original is not None else None),
        "observations": [], "unresolved": [], "publication_authority": False,
        "public_apply": False, "central_db_write": False}


def not_executed_receipt(reason_code="NOT_EXECUTED", *, status="NOT_EXECUTED"):
    _require(type(status) is str and status in _NONEXEC, "SEMANTIC_STATUS_INVALID")
    _require(type(reason_code) is str and _CODE.fullmatch(reason_code) is not None, "SEMANTIC_REASON_INVALID")
    return _seal(_receipt(status, [reason_code]))


def _span(fragment, start, end):
    text = fragment["text"]
    _require(0 <= start < end <= len(text), "SEMANTIC_SPAN_INVALID")
    exact = text[start:end]
    return {"raw_path": fragment["raw_path"], "start": start, "end": end,
        "byte_start": len(text[:start].encode("utf-8")), "byte_end": len(text[:end].encode("utf-8")),
        "text": exact, "text_sha256": hashlib.sha256(exact.encode("utf-8")).hexdigest()}


def _boundaries(text, start, end):
    if _roles._boundaries(text, start, end):
        return True
    if start and _roles._word(text[start - 1]):
        return False
    return any(text.startswith(suffix, end) and
        (end + len(suffix) == len(text) or not _roles._word(text[end + len(suffix)])) for suffix in _COPULA_SUFFIXES)


def _aliases(original, evidence, payloads):
    if evidence is None:
        _require(payloads in (None, {}), "SEMANTIC_ALIAS_EVIDENCE_MISSING")
        return {}, None
    # Fixed local validator only; no dynamic module/backend/callback execution.
    from .candidate_reranker_alias_evidence import observe_alias_evidence
    validated = observe_alias_evidence(original, alias_evidence=evidence, evidence_payloads=payloads)
    _require(validated["status"] != "LIMIT_EXCEEDED", "SEMANTIC_ALIAS_EVIDENCE_LIMIT")
    _require(validated["status"] not in ("INVALID_INPUT", "ERROR"), "SEMANTIC_ALIAS_EVIDENCE_INVALID")
    aliases = {}
    known_ids = {c["candidate_id"] for c in original["candidates"]}
    for binding in validated["bindings"]:
        _require(binding["binding_status"] == "UNIQUE" and binding["candidate_id"] in known_ids,
            "SEMANTIC_ALIAS_BINDING_INVALID")
        aliases.setdefault(binding["candidate_id"], []).append({"alias": binding["alias"],
            "evidence_ids": [binding["registry_entry_id"]],
            "occurrences": {(x["raw_path"], x["start"], x["end"]) for x in binding["occurrences"]}})
    return aliases, validated


def _speaker_label(text, surfaces=()):
    """인명 분류 없이 명시 라벨만 보류한다. 제목·URL·시각 콜론은 제외한다."""
    label = _SPEAKER_LABEL.match(text)
    if label is None or not label.group("label").strip():
        return None
    prefix, tail = label.group("label").strip(), text[label.end():]
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9+.-]*", prefix) and tail.startswith("//"):
        return None
    if re.fullmatch(r"[0-9]{1,2}", prefix) and re.match(r"[0-9]{2}(?![0-9])", tail):
        return None
    colon = label.end() - 1
    if any(text.startswith(surface, start) for surface in surfaces
           for start in range(max(0, colon - len(surface) + 1), colon + 1)):
        return None
    return label


def _clauses(fragments, surfaces=()):
    """Return exact clause coordinates. Carry body quotes across source body lines."""
    result = {f["raw_path"]: [] for f in fragments}
    body_lines, body_locations = [], []
    groups = []
    for fragment in fragments:
        offset = 0
        lines = fragment["text"].splitlines(keepends=True)
        if not lines and fragment["text"]:
            lines = [fragment["text"]]
        locations = []
        for line in lines:
            locations.append((fragment, offset))
            offset += len(line)
        if fragment["kind"] == "BODY":
            body_lines.extend(lines)
            body_locations.extend(locations)
        else:
            groups.append((ClaimScopeSource(body_lines=tuple(lines)), locations))
    groups.append((ClaimScopeSource(body_lines=tuple(body_lines)), body_locations))
    quote_ranges = _raw_quote_ranges(fragments)
    for source, locations in groups:
        label_block = False
        for _, index, _, parts, boundaries, prefixes in _author_line_clauses(source):
            fragment, line_offset = locations[index]
            label_line = False
            for ci, (clause, boundary, prefix) in enumerate(zip(parts, boundaries, prefixes)):
                (a, b), _ = boundary
                if a < 0:
                    continue
                label = _speaker_label(clause.text, surfaces)
                if label and any(x < line_offset + a + label.end() and line_offset + a < y
                                 for x, y, _ in quote_ranges[fragment["raw_path"]]):
                    label = None
                if label:
                    tail = clause.text[label.end():]
                    if tail.lstrip()[:1] not in _QUOTE_PAIRS:
                        # 중간 절에서 시작한 별도 화자도 같은 줄의 후행절에 유지한다.
                        label_line = True
                    if not tail.strip():
                        # 라벨만 남은 줄은 작성자 복귀 근거가 없는 동안 보류한다.
                        label_block = True
                kept, _, _, lead, end, _, reason = _author_clause_cut(clause.text, *prefix)
                result[fragment["raw_path"]].append({"start": line_offset + a, "end": line_offset + b,
                    "clause": clause, "next": parts[ci + 1] if ci + 1 < len(parts) else None,
                    "kept": frozenset(kept[lead:end]), "reason": reason,
                    "label_block": label_block,
                    "label_line": label_line,
                    "quote_ranges": [(max(x, line_offset + a) - line_offset - a,
                        min(y, line_offset + b) - line_offset - a, why)
                        for x, y, why in quote_ranges[fragment["raw_path"]]
                        if x < line_offset + b and line_offset + a < y]})
    for records in result.values():
        for current, following in zip(records, records[1:]):
            if current["next"] is None:
                current["next"] = following["clause"]
    return result


def _raw_quote_ranges(fragments):
    """원문 좌표의 중첩 인용을 추적한다. 미종결 인용도 다음 줄에서 잊지 않는다.

    기존 v1 helper는 변경하지 않는다. 닫힌 인용 이후의 작성자 문장은 범위 밖에
    남기며, BODY 사이에만 상태를 이어서 title/comment를 오염시키지 않는다.
    """
    output = {fragment["raw_path"]: [] for fragment in fragments}
    groups = [[fragment for fragment in fragments if fragment["kind"] == "BODY"]]
    groups.extend([fragment] for fragment in fragments if fragment["kind"] != "BODY")
    for group in groups:
        text_parts, positions = [], []
        offset = 0
        for fragment in group:
            text_parts.append(fragment["text"])
            positions.append((fragment["raw_path"], offset, offset + len(fragment["text"])))
            offset += len(fragment["text"]) + 1
        text = "\n".join(text_parts)
        stack, spans = [], []
        for index, char in enumerate(text):
            # Don't / author's 같은 단어 내부 apostrophe를 발화 시작으로 삼지 않는다.
            if char in {"'", "’"} and index and index + 1 < len(text) and text[index - 1].isalnum() and text[index + 1].isalnum() and not (char == "’" and stack and stack[-1][0] == char):
                continue
            if stack and char == stack[-1][0]:
                _, start = stack.pop()
                if not stack:
                    spans.append((start, index + 1, "QUOTED_OR_REMOVED_SOURCE"))
            elif char in _QUOTE_PAIRS:
                stack.append((_QUOTE_PAIRS[char], index))
            elif char in _QUOTE_PAIRS.values():
                if stack:
                    # 교차 닫힘은 회복 시점을 추측하지 않고 나머지 문맥을 보류한다.
                    spans.append((stack[0][1], len(text), "UNBALANCED_QUOTATION"))
                    break
                spans.append((0, index + 1, "UNBALANCED_QUOTATION"))
        if stack:
            spans.append((stack[0][1], len(text), "UNBALANCED_QUOTATION"))
        for path, start, end in positions:
            output[path].extend((max(a, start) - start, min(b, end) - start, reason)
                               for a, b, reason in spans if a < end and start < b)
    return output


def _grammar(clause, occurrences):
    """Candidate-local relation proposals with exact raw clause spans, not labels."""
    text = clause["clause"].text
    proposals = []
    for item in occurrences:
        surface, start, end = item["surface"], item["start"] - clause["start"], item["end"] - clause["start"]
        escaped = re.escape(surface)

        def add(pattern, role, rule, related=()):
            for match in re.finditer(pattern, text):
                if match.span("mention") != (start, end):
                    continue
                cue = match.span("cue")
                rel = list(related)
                if "author" in match.re.groupindex:
                    author = match.group("author").split()[0]
                    if author in _INELIGIBLE_AUTHOR:
                        continue
                    rel.append(match.span("author"))
                proposals.append({"item": item, "role": role, "rule": rule,
                    "cues": [cue, match.span()], "related": rel, "range": match.span()})

        add(r"^\s*" + _SELF + r"(?P<mention>" + escaped + r")(?:을|를)\s*(?P<cue>" + _PRIMARY_ACT + ")" + _PRED_END,
            "PRIMARY", "AUTHOR_EXPLICIT_REVIEW")
        add(r"^\s*(?P<cue>이 글의\s*(?:리뷰|평가|논의|분석)\s*대상)(?:은|는)\s*(?P<mention>" + escaped + ")" + _COP + _PRED_END,
            "PRIMARY", "AUTHOR_EXPLICIT_REVIEW_OBJECT")
        add(r"(?P<mention>" + escaped + r")(?:은|는)\s*" + _AUTHOR + r"의\s*(?P<cue>" + _PREVIOUS + ")" + _COP + _PRED_END,
            "PREVIOUS", "NAMED_AUTHOR_PREVIOUS")
        add(_AUTHOR + r"의\s*(?P<cue>" + _PREVIOUS + r")(?:은|는)\s*(?P<mention>" + escaped + ")" + _COP + _PRED_END,
            "PREVIOUS", "NAMED_AUTHOR_PREVIOUS")
        for other in occurrences:
            if item["candidate_index"] == other["candidate_index"] or not other["semantic_eligible"]:
                continue
            other_start, other_end = other["start"] - clause["start"], other["end"] - clause["start"]
            target = re.escape(other["surface"])
            patterns = [
                (r"(?P<other>" + target + r")(?:을|를)\s*쓴\s*작가의\s*(?P<cue>" + _PREVIOUS + r")(?:은|는)\s*(?P<mention>" + escaped + ")" + _COP + _PRED_END,
                    "PREVIOUS", "SAME_AUTHOR_PREVIOUS"),
                (r"(?P<mention>" + escaped + r")(?:은|는)\s*(?P<other>" + target + r")(?:을|를)\s*쓴\s*작가의\s*(?P<cue>" + _PREVIOUS + ")" + _COP + _PRED_END,
                    "PREVIOUS", "SAME_AUTHOR_PREVIOUS"),
                (r"(?P<mention>" + escaped + r")(?P<cue>보다)\s*(?P<other>" + target + r")(?:은|는|이|가)\s*더\s*" + _COMPARATIVE + _PRED_END,
                    "COMPARISON", "DIRECTED_THAN_COMPARISON"),
                (r"(?P<other>" + target + r")(?:은|는|이|가)\s*(?P<mention>" + escaped + r")(?:과|와)\s*(?P<cue>비슷하다|유사하다)" + _PRED_END,
                    "COMPARISON", "DIRECTED_SIMILAR_COMPARISON"),
            ]
            for pattern, role, rule in patterns:
                for match in re.finditer(pattern, text):
                    if match.span("mention") != (start, end) or match.span("other") != (other_start, other_end):
                        continue
                    proposals.append({"item": item, "role": role, "rule": rule,
                        "cues": [match.span("cue"), match.span()], "related": [match.span("other")], "range": match.span()})
    return proposals


def _hold_reason(record, proposal, occurrences):
    clause = record["clause"]
    start, end = proposal["range"]
    for a, b, reason in record["quote_ranges"]:
        if start < b and a < end:
            return reason
    if record["label_block"] or record["label_line"]:
        return "SOURCE_SPEAKER_LABEL_UNRESOLVED"
    if record["reason"]:
        return "SOURCE_" + record["reason"].upper()
    if any(i not in record["kept"] for i in range(start, end)):
        return "QUOTED_OR_REMOVED_SOURCE"
    masked = list(clause.text)
    for item in occurrences:
        a, b = item["start"] - record["start"], item["end"] - record["start"]
        masked[a:b] = " " * (b - a)
    masked_text = "".join(masked)
    # 후보명 안의 ':'나 '면'을 해석하지 않고 관계 밖의 명시 라벨/술어 suffix만 본다.
    if _speaker_label(masked_text):
        return "SOURCE_SPEAKER_LABEL_UNRESOLVED"
    if "role" in proposal and _CONDITIONAL_SUFFIX.match(clause.text[end:]):
        return "CONDITIONAL_RELATION"
    state = clause_assertion(Clause(masked_text, clause.quotes, clause.terminal), start, end, record["next"])
    if state != ASSERTED:
        return "SOURCE_" + state.upper()
    if any(masked_text.count(a) != masked_text.count(b) for a, b in (("“", "”"), ("‘", "’"), ("「", "」"), ("『", "』"))) or masked_text.count('"') % 2:
        return "UNBALANCED_QUOTATION"
    # Titles are opaque: a title containing '아니' is not proposition negation.
    if _DEFER.search(masked_text) or _negated_at(masked_text, start, end):
        return "NEGATED_REPORTED_OR_HEDGED_RELATION"
    return None


def _mention_hold(record, item, occurrences):
    start, end = item["start"] - record["start"], item["end"] - record["start"]
    return _hold_reason(record, {"range": (start, end)}, occurrences)


def observe_preselection_semantics(frozen_view, *, alias_evidence=None, evidence_payloads=None):
    from .candidate_reranker_shadow import _validate_view
    try:
        original = _validate_view(frozen_view)
        _require(all(not c["role_observations"] for c in original["candidates"]), "SEMANTIC_INPUT_ROLES_NOT_EMPTY")
        alias_map, alias_validation = _aliases(original, alias_evidence, evidence_payloads)
        view = json.loads(_bytes(original))
        candidates = view["candidates"]
        by_surface = {}
        for index, candidate in enumerate(candidates):
            for title in candidate["titles"]:
                by_surface.setdefault(title, {})[index] = ("EXACT_TITLE", [], None)
            for entry in alias_map.get(candidate["candidate_id"], []):
                surface = entry["alias"]
                owners = by_surface.setdefault(surface, {})
                if index not in owners:
                    owners[index] = ("VERIFIED_ALIAS", list(entry["evidence_ids"]), set(entry["occurrences"]))
                elif owners[index][0] == "VERIFIED_ALIAS":
                    owners[index][1].extend(x for x in entry["evidence_ids"] if x not in owners[index][1])
                    owners[index][2].update(entry["occurrences"])
                if surface not in candidate["aliases"]:
                    candidate["aliases"].append(surface)
        receipt = _receipt("NO_MATCH", [], original, view, alias_validation, alias_evidence)
        counts = receipt["counts"]
        counts.update(candidates=len(candidates), unique_surfaces=len(by_surface))
        contexts = _clauses(view["source_view"]["fragments"], by_surface)

        def unresolved(fragment, item, reasons, indices=None):
            _require(len(receipt["unresolved"]) < MAX_UNRESOLVED, "SEMANTIC_UNRESOLVED_LIMIT")
            indices = indices if indices is not None else [item["candidate_index"]]
            receipt["unresolved"].append({"candidate_ids": [candidates[i]["candidate_id"] for i in sorted(indices)],
                "mention": _span(fragment, item["start"], item["end"]), "reason_codes": sorted(set(reasons))})

        for fragment in view["source_view"]["fragments"]:
            matches = []
            for surface, owners in sorted(by_surface.items()):
                offset = 0
                while True:
                    start = fragment["text"].find(surface, offset)
                    if start < 0:
                        break
                    end = start + len(surface)
                    offset = start + 1
                    counts["raw_matches"] += 1
                    _require(counts["raw_matches"] <= MAX_MATCHES, "SEMANTIC_RAW_MATCH_LIMIT")
                    if not _boundaries(fragment["text"], start, end):
                        counts["boundary_rejected"] += 1
                        continue
                    allowed = {i: info for i, info in owners.items() if info[2] is None or
                        (fragment["raw_path"], start, end) in info[2]}
                    if allowed:
                        matches.append({"start": start, "end": end, "surface": surface, "owners": allowed})
            matches.sort(key=lambda x: (x["start"], x["end"], x["surface"]))
            unique = []
            for item in matches:
                overlaps = any(other is not item and item["start"] < other["end"] and other["start"] < item["end"] for other in matches)
                if len(item["owners"]) != 1 or overlaps:
                    counts["ambiguous_spans"] += 1
                    unresolved(fragment, item, ["SHARED_SURFACE" if len(item["owners"]) != 1 else "OVERLAPPING_SURFACES"], item["owners"])
                else:
                    item["candidate_index"] = next(iter(item["owners"]))
                    candidate = candidates[item["candidate_index"]]
                    item["semantic_eligible"] = (candidate["event_eligible"] and
                        not candidate["identity_conflict"] and candidate["option_kind"] == "WORK_CANDIDATE")
                    unique.append(item)
            proposals, holds = {}, {}
            for record in contexts[fragment["raw_path"]]:
                local = [m for m in unique if record["start"] <= m["start"] < m["end"] <= record["end"]]
                for item in local:
                    holds[(item["start"], item["end"], item["candidate_index"])] = (
                        "COMMENT_SEMANTICS_DEFERRED" if fragment["kind"] == "COMMENT" else _mention_hold(record, item, local))
                for proposal in _grammar(record, local):
                    item = proposal["item"]
                    reason = "COMMENT_SEMANTICS_DEFERRED" if fragment["kind"] == "COMMENT" else _hold_reason(record, proposal, local)
                    if candidates[item["candidate_index"]]["identity_conflict"]:
                        reason = "CANDIDATE_IDENTITY_CONFLICT"
                    elif not candidates[item["candidate_index"]]["event_eligible"] or candidates[item["candidate_index"]]["option_kind"] != "WORK_CANDIDATE":
                        reason = "SEMANTIC_CANDIDATE_NOT_ELIGIBLE"
                    proposal.update(record=record, reason=reason)
                    proposals.setdefault((item["start"], item["end"], item["candidate_index"]), []).append(proposal)
            for item in unique:
                index = item["candidate_index"]
                related = proposals.get((item["start"], item["end"], index), [])
                hold = holds.get((item["start"], item["end"], index), "RAW_ALIGNMENT_UNAVAILABLE")
                valid = [p for p in related if p["reason"] is None and hold is None]
                roles = {p["role"] for p in valid}
                reasons = [p["reason"] for p in related if p["reason"]]
                if hold:
                    reasons.append(hold)
                chosen = None
                if len(roles) > 1:
                    reasons.append("CONFLICTING_SEMANTIC_ROLES")
                elif valid:
                    # Multiple proofs of the same role are not collapsed by a vote;
                    # retain all cues/related spans in deterministic source order.
                    chosen = valid[0]
                if reasons:
                    unresolved(fragment, item, reasons)
                role = chosen["role"] if chosen is not None else "MENTIONED"
                mention_kind, evidence_ids, _ = item["owners"][index]
                detail = {"candidate_id": candidates[index]["candidate_id"], "role": role,
                    "mention_kind": mention_kind, "mention": _span(fragment, item["start"], item["end"]),
                    "relation_cues": [], "related_mentions": [],
                    "speaker": "COMMENT" if fragment["kind"] == "COMMENT" else "AUTHOR",
                    "assertion": "ASSERTED" if chosen else "MENTION_ONLY",
                    "rule_id": chosen["rule"] if chosen else "EXACT_MENTION", "alias_evidence_ids": evidence_ids}
                if chosen:
                    for field, key in (("relation_cues", "cues"), ("related_mentions", "related")):
                        ranges = sorted({(p["record"]["start"] + a, p["record"]["start"] + b) for p in valid for a, b in p[key]})
                        detail[field] = [_span(fragment, a, b) for a, b in ranges]
                receipt["observations"].append(detail)
                candidates[index]["role_observations"].append({"role": role, **{k: detail["mention"][k] for k in ("raw_path", "start", "end", "text_sha256")}})
                _require(len(candidates[index]["role_observations"]) <= MAX_PER_CANDIDATE, "SEMANTIC_PER_CANDIDATE_LIMIT")
                _require(len(receipt["observations"]) <= MAX_TOTAL, "SEMANTIC_TOTAL_LIMIT")
                counts[role.lower()] += 1
                counts["alias_observations"] += int(mention_kind == "VERIFIED_ALIAS")
        counts["observations"] = len(receipt["observations"])
        counts["observed_candidates"] = sum(bool(c["role_observations"]) for c in candidates)
        counts["semantic_observations"] = counts["primary"] + counts["previous"] + counts["comparison"]
        counts["unresolved"] = len(receipt["unresolved"])
        receipt["status"] = "OBSERVED" if counts["observations"] else "AMBIGUOUS" if (counts["ambiguous_spans"] or
            alias_validation is not None and alias_validation["status"] == "AMBIGUOUS") else "NO_MATCH"
        receipt["reason_codes"] = sorted({reason for entry in receipt["unresolved"] for reason in entry["reason_codes"]})
        if not counts["observations"] and not counts["ambiguous_spans"]:
            receipt["reason_codes"].append("NO_EXACT_SOURCE_MENTION")
        if alias_validation is not None and alias_validation["status"] not in ("BOUND", "NO_MATCH"):
            receipt["reason_codes"].append("ALIAS_EVIDENCE_" + alias_validation["status"])
        receipt["frozen_view_sha256"] = _sha(view)
        _validate_view(view)
        return view, _seal(receipt)
    except SemanticObservationError:
        raise
    except (ValueError, TypeError, KeyError, UnicodeError, ImportError, AttributeError, RecursionError, OverflowError) as exc:
        code = getattr(exc, "code", "")
        raise SemanticObservationError("SEMANTIC_INPUT_LIMIT" if type(code) is str and "LIMIT" in code
            else "SEMANTIC_INPUT_OR_EVIDENCE_INVALID") from exc


def validate_semantic_observation(original_view, enriched_view, receipt, *, alias_evidence=None, evidence_payloads=None):
    try:
        expected_view, expected_receipt = observe_preselection_semantics(original_view,
            alias_evidence=alias_evidence, evidence_payloads=evidence_payloads)
        _require(_bytes(enriched_view) == _bytes(expected_view), "SEMANTIC_ENRICHED_VIEW_MISMATCH")
        _require(_bytes(receipt) == _bytes(expected_receipt), "SEMANTIC_RECEIPT_MISMATCH")
        return expected_receipt
    except SemanticObservationError:
        raise
    except (ValueError, TypeError, UnicodeError) as exc:
        raise SemanticObservationError("SEMANTIC_RECEIPT_INVALID") from exc
