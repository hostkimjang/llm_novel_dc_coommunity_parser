"""후보별 검색-only 거절과 원문 작품 참조를 보조 역할 경계에서 분리한다."""
from __future__ import annotations

import re
from types import SimpleNamespace

from .candidate_alias_relation import _source, candidate_alias_relation
from .degraded_reference_role import _explicit_reference_name, _naming_withdrawn
from .source_title_hypothesis import _author_occurrences


def _literal(text, value):
    return bool(isinstance(text, str) and value and re.search(
        r'(?<![0-9A-Za-z가-힣_])' + re.escape(value)
        + r'(?![0-9A-Za-z가-힣_])', text))


def _verification(ctx, supplied):
    if not isinstance(supplied, dict) or not supplied:
        supplied = (getattr(ctx, 'expert_outputs', None) or {}).get('verifier')
    if not isinstance(supplied, dict):
        return {}
    nested = supplied.get('verification_result')
    return nested if isinstance(nested, dict) else supplied


def _rejection_targets_title(item, title):
    # 명시 대상이 다르면 설명 속 비교 표제의 출현으로 그 대상을 바꾸지 않는다.
    declared = [item[key] for key in ('candidate_title', 'official_title')
                if item.get(key) is not None]
    if declared:
        return all(isinstance(value, str) and value.strip() == title for value in declared)
    # 단어 경계는 표제 경계가 아니다. '제목 외전'에서 '제목'만 잘라 거절하지 않는다.
    quoted = re.compile(r'''"([^"\r\n]*)"|'([^'\r\n]*)'|“([^”\r\n]*)”|‘([^’\r\n]*)’|「([^」\r\n]*)」|『([^』\r\n]*)』|《([^》\r\n]*)》''')
    for key in ('issue', 'explanation'):
        text = item.get(key)
        if isinstance(text, str) and any(
                next(value for value in match.groups() if value is not None).strip() == title
                for match in quoted.finditer(text)):
            return True
    return False


def _candidate_rejected(title, vf):
    grounding = vf.get('grounding_check')
    if (not isinstance(grounding, dict) or grounding.get('decoder_grounded') is not False
            or grounding.get('anchor_found') != 'search_only'):
        return False
    items = vf.get('counter_arguments')
    if not isinstance(items, list):
        return False
    for item in items:
        if (not isinstance(item, dict) or item.get('severity') != 'critical'
                or item.get('action') not in {'reject', 'nullify_title'}):
            continue
        if _rejection_targets_title(item, title):
            return True
    return False


def rejected_search_reference(pipeline, ctx, candidate, verification=None):
    """명시 거절된 그 후보만 제한한다. raw 후보·공개/학습 계약은 변경하지 않는다.

    공식/검색에 작품이 존재하는 것만으로 원문의 mentioned 관계를 만들지 않는다.
    원문 명명·독서 대상, 같은 원문 별칭의 명시 관계, 원문 인물과 검산된 작품
    연결은 해당 거절의 독립 반증으로 보존한다. 전역적인 missing-URL 필터가 아니다.
    """
    if ctx is None:
        return False
    title = getattr(candidate, 'official_title', None)
    if not isinstance(title, str) or not title.strip():
        return False
    title = title.strip()
    if not _candidate_rejected(title, _verification(ctx, verification)):
        return False
    spans = _source(ctx)
    if spans is None:
        return True  # 변경된 capture를 역할 반증으로 재사용하지 않는다.
    texts = [span['text'] for span in spans]
    if any(_explicit_reference_name(raw, title) for raw in texts):
        return False
    # 검산한 현재 원필드로만 기존 독서/명명 판독을 호출한다. raw capture를 다시 섞지 않는다.
    author = [span for span in spans if span['source'] != 'comment']
    view = SimpleNamespace(post_data={
        'title': next((x['text'] for x in author if x['source'] == 'author_title'), ''),
        'content_blocks': [{'type': 'text', 'text': x['text']} for x in author
                           if x['source'] != 'author_title']})
    if any(not _naming_withdrawn(hit['raw_text'], title, *hit['raw_span'])
           for hit in _author_occurrences(view, title, require_work_role=True)):
        return False
    aliases = [getattr(candidate, 'alias_or_mention', None)]
    decoder = (getattr(ctx, 'expert_outputs', None) or {}).get('decoder') or {}
    if isinstance(decoder, dict):
        for term in decoder.get('decoded_terms') or ():
            if not isinstance(term, dict):
                continue
            best = term.get('best_match') or {}
            candidates = term.get('candidates') or []
            best = best if isinstance(best, dict) else {}
            candidates = candidates if isinstance(candidates, (list, tuple)) else []
            titles = [best.get(key) for key in ('title', 'official_title', 'official_novel_title')]
            titles.extend(row.get('official_novel_title') for row in candidates if isinstance(row, dict))
            if title in titles:
                aliases.append(term.get('original'))
    for alias in dict.fromkeys(x for x in aliases if isinstance(x, str) and x.strip()):
        if candidate_alias_relation(ctx, title, alias) is not None:
            return False
    # 원문에 실제 붙인 공식 작품 URL은 검색에 같은 페이지가 있다는 것과 다르다.
    matched_url = pipeline._find_title_matched_official_url(
        title, getattr(ctx, 'search_results', None) or [])
    if matched_url and any(_literal(raw, matched_url) for raw in texts):
        return False
    # verified link의 존재뿐 아니라 그 인물의 원문 출현까지 요구한다.
    links = (getattr(ctx, 'verified_character_work_links', None) or ()) if (
        pipeline._has_strong_verified_character_work_links(ctx, title)) else ()
    for link in links:
        if (not isinstance(link, dict) or link.get('_weak_match')
                or (link.get('title') or link.get('work_title')) != title):
            continue
        character = link.get('character')
        if isinstance(character, str) and character.strip():
            visible = re.compile(r'(?<![0-9A-Za-z가-힣_])' + re.escape(character.strip())
                + r'(?:께서|에게|에서|으로|은|는|이|가|을|를|의|도|만|에|로)?(?![0-9A-Za-z가-힣_])')
            if any(visible.search(raw) for raw in texts):
                return False
    return True
