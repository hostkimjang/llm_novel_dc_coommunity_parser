"""Decoder 원관측의 작품 역할 모순. 표제 문자열이나 게시글 ID 목록은 사용하지 않는다."""
from __future__ import annotations

from copy import deepcopy
import re

from .source_title_hypothesis import title_hypothesis_source_support, _author_occurrences


def _key(value):
    return re.sub(r'\s+', '', value).casefold() if isinstance(value, str) else ''


WORK_ROLES = frozenset({'novel_title', 'work_title', 'work_alias', 'title_alias'})
# slang/community/genre는 실제 작품 약칭·갤러리형 표면과 양립할 수 있다.
# 그 enum만으로 이번 일반 문장 모순에 포함하지 않는다.
NONWORK_ROLES = frozenset({'general_noun', 'sentence', 'phrase'})


def decoder_title_role_conflicts(title, decoded_terms):
    """역할이 확인되지 않은 모든 후보를 지우지 않고, 같은 후보의 명시 모순만 찾는다."""
    target = _key(title)
    if not target or not isinstance(decoded_terms, list):
        return ()
    linked, conflicts = 0, []
    for index, term in enumerate(decoded_terms):
        if not isinstance(term, dict):
            continue
        best = term.get('best_match') if isinstance(term.get('best_match'), dict) else {}
        candidates = [value for value in term.get('candidates') or () if isinstance(value, dict)]
        candidate_rows = [value for value in candidates if target == _key(
            value.get('official_novel_title') or value.get('official_title') or value.get('title'))]
        if target != _key(best.get('title')) and not candidate_rows:
            continue
        linked += 1
        interpretations = [value for value in term.get('interpretations') or () if isinstance(value, dict)]
        types = {str(value.get('type') or '').strip().lower() for value in interpretations}
        own_work_role = any(str(value.get('type') or '').strip().lower() in WORK_ROLES
                            and _key(value.get('value')) == target for value in interpretations)
        reason = None
        if (target == _key(term.get('original')) and types and types <= NONWORK_ROLES
                and not own_work_role):
            reason = 'decoder_nonwork_interpretation_self_match'
        elif (candidate_rows and not _key(best.get('title')) and not own_work_role):
            reason = 'decoder_unselected_candidate_without_matching_work_interpretation'
        if reason:
            conflicts.append({'term_index': index, 'reason_code': reason,
                'original': term.get('original'), 'raw_decoder_term': deepcopy(term)})
    # 다른 독립 term이 같은 작품을 일관되게 해석한 경우에는 이번 좁은 모순으로
    # 그 긍정을 덮지 않는다. 일반적인 최종 공개/역할 guard는 계속 적용된다.
    return tuple(conflicts) if linked and linked == len(conflicts) else ()


def unresolved_decoder_title_role_conflicts(ctx, title, conflicts, *, official_title_supported,
                                           curated_registries=()):
    """원문 명명/독서, 출처의 명시 별칭 관계, 정확한 기존 사전 쌍을 재사용한다."""
    if not conflicts:
        return ()
    for item in conflicts:
        alias = item.get('original')
        if title_hypothesis_source_support(ctx, alias, title):
            return ()
        # 단독 문장형 공식 표제도 실제 같은 작품의 독립 공식 근거가 있으면 보존한다.
        # 다른 표면의 null 교정 후보에는 작품 존재만으로 별칭 관계를 만들어 주지 않는다.
        if official_title_supported and _key(alias) == _key(title):
            return ()
        if not isinstance(alias, str) or not _author_occurrences(ctx, alias):
            continue
        registered = {_key(value) for registry in curated_registries if isinstance(registry, dict)
                      for surface, value in registry.items() if _key(surface) == _key(alias)}
        if registered == {_key(title)}:
            return ()
    return conflicts
