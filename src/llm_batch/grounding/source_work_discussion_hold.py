"""표제가 가리키는 대상과 직접 독서 발화를 미확정 작품담론으로만 보존한다."""
from __future__ import annotations

import hashlib
import re

from ..experts.source_spans import author_text_spans
from .claim_scope_contract import ASSERTED, Clause, ClaimScopeSource, clause_assertion
from .context_projection_contract import _author_line_clauses, _author_clause_cut


def marked_work_reading_hold(post, discourse):
    """모델의 작품 가설을 원문 표지·작성자 독서절로 재검산한다.

    후보 작품의 정답이나 별칭 관계를 증명하지 않는다. 한 표제 표면과
    한 직접 독서절만 수용하여 다른 작품·댓글·인용의 근거가 섞이지 않는다.
    """
    if not isinstance(post, dict) or not isinstance(discourse, dict):
        return None
    if (discourse.get("primary_domain") != "novel_literature"
            or discourse.get("target_kind") != "work"
            or discourse.get("title_body_consistency") is not True
            or discourse.get("is_association_not_discussion") is not False):
        return None
    spans = author_text_spans(post)
    titles = [s for s in spans if s["source"] == "author_title"]
    bodies = [s for s in spans if s["source"] == "author_body"]
    if len(titles) != 1 or len(bodies) != 1:
        return None
    terms = discourse.get("title_novel_terms")
    if not isinstance(terms, list) or len(terms) != 1 or not isinstance(terms[0], str):
        return None
    surface = terms[0].strip()
    if not re.fullmatch(r"[가-힣A-Za-z0-9][가-힣A-Za-z0-9 ]{1,39}", surface):
        return None
    title, body = titles[0]["text"], bodies[0]["text"]
    hits = list(re.finditer(r"(?<![가-힣A-Za-z0-9])" + re.escape(surface) + r"\s*<<(?!=|<)", title))
    if len(hits) != 1 or title.count("<<") != 1:
        return None
    hit = hits[0]
    source = ClaimScopeSource(post_title=title, body_lines=(body,))
    units = list(_author_line_clauses(source))
    admitted = {}
    for origin, index, _, clauses, boundaries, cuts in units:
        # 둘 이상의 절, 전언/철회/분리된 인용은 이 좁은 근거의 범위 밖이다.
        if len(clauses) != 1:
            return None
        clause, boundary, cut = clauses[0], boundaries[0], cuts[0]
        kept, quotes, _, lead, stop, _, reason = _author_clause_cut(
            clause.text, *cut, header=origin == "post_title")
        if reason or boundary[0][0] != 0:
            return None
        admitted[origin] = (clause, set(kept[lead:stop]), tuple(quotes))
    if set(admitted) != {"post_title", "body_line"}:
        return None
    if not set(range(hit.start(), hit.start() + len(surface))).issubset(admitted["post_title"][1]):
        return None
    reading = re.fullmatch(
        r"\s*(?:(?:나는|난|내가|저는|제가)\s+)?(?:이거|이것|이\s*작품|이\s*소설)(?:는|은|을|를)?\s*"
        r"(?P<reading>중도\s*하차(?:함|했다|했음|했어요|했습니다)|읽(?:었다|었음|었어요|었습니다))"
        r"\s*[.!。！]*\s*", body)
    if reading is None:
        return None
    clause, kept, quotes = admitted["body_line"]
    lo, hi = reading.span("reading")
    if (not set(range(lo, hi)).issubset(kept)
            or clause_assertion(Clause(clause.text, quotes, clause.terminal), lo, hi, None) != ASSERTED):
        return None
    return {
        "surface": surface, "basis": "marked_title_and_direct_deictic_reading",
        "title_span": [hit.start(), hit.start() + len(surface)],
        "title_sha256": hashlib.sha256(title.encode()).hexdigest(),
        "body_index": bodies[0]["position"], "reading_span": [lo, hi],
        "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "publication_authority": False, "learning_authority": False,
    }
