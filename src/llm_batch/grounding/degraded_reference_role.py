"""URL 불일치로 강등된 진단 후보와 원문의 작품 참조 역할을 분리한다."""
from __future__ import annotations

import re

from ..experts.source_spans import author_text_spans, _DERIVED_PREFIXES
from .source_title_hypothesis import _author_occurrences

_NAME_PAIRS = {'「': '」', '『': '』', '《': '》', '"': '"', "'": "'", '“': '”', '‘': '’'}
_POSTFIX_NAME = re.compile(
    r'\s*(?:이라는|라는|이란|란)\s*(?:웹소설|소설|작품)'
    r'(?=$|[\s.,!?]|(?:을|를|은|는|이)(?=$|\s))')
_NAMING_LINK = re.compile(
    r'\s*(?:이라고|라고|이라|라)\s*'
    r'(?:(?:썼|적었|붙였|불렀|표현했|말했)(?:지만|는데|으나|다[.!])'
    r'|(?:쓴|적은|붙인|부른|표현한|말한)\s*(?:것|거|건)(?:은|는|이|가)?)\s*')
_NAME_KIND = r'(?:(?:실제|정식)\s*)?(?:작품명|제목|(?:웹소설|소설|작품)의\s*(?:제목|이름|표제))'
_DIRECT_NAME_DENIAL = re.compile(
    r'\s*(?:은|는|이|가)?\s*(?:(?:실제|정식)\s*)?'
    r'(?:(?:작품명|제목|소설|작품)(?:은|는|이|가)?\s*)?(?:아니|아님)')
_READ_REFERENCE_END = re.compile(
    r'\s*(?:을|를)\s*(?:비교해\s*)?(?:(?:안|못)\s*)?'
    r'읽(?:었다|었음|었어요|었습니다|지\s*않았다|지\s*않았음|지\s*않았어요|지\s*않았습니다)'
    r'\s*[.!。！]\s*')


def _naming_withdrawn(raw, title, lo, hi):
    """현재 표제 출현에 직접 이어진 명명 부정만 읽는다. 다른 출현은 덮지 않는다."""
    right = raw[hi:]
    closing = _NAME_PAIRS.get(raw[lo-1:lo] if lo else '')
    if closing and right.startswith(closing):
        right = right[len(closing):]
    if _DIRECT_NAME_DENIAL.match(right):
        return True
    if re.match(r'\s*(?:이?라는)\s*(?:말|표현|문구)', right):
        return True
    postfix = _POSTFIX_NAME.match(right)
    object_tail = right[postfix.end():] if postfix else right
    if postfix and _DIRECT_NAME_DENIAL.match(object_tail):
        return True
    link = _NAMING_LINK.match(right)
    reading = _READ_REFERENCE_END.match(object_tail)
    if link is None and reading is None:
        return False
    # 명명/표기 행위의 바로 다음 논항만 받는다. 일반 독서 부정이나
    # 필드 뒤쪽의 임의 부정문을 검색하지 않고, 원필드 밖으로도 나가지 않는다.
    names = [re.escape(title), *(re.escape(a + title + z) for a, z in _NAME_PAIRS.items())]
    subject = (r'(?:그건|이건|그것은|이것은|그\s*(?:이름|표현|제목)(?:은|는)|'
               r'(?:' + '|'.join(names) + r')(?:은|는|이|가))')
    # 독서절 뒤에서는 다음 문장의 동일 이름/지시어를 반드시 요구한다.
    # '읽지 않았다' 자체는 명명 부정이 아니며, 다른 독립 명명 출현도 전역 차단하지 않는다.
    tail = right[link.end():] if link else object_tail[reading.end():]
    subject_pattern = r'(?:' + subject + r'\s*)' + ('?' if link else '')
    return bool(re.match(r'\s*' + subject_pattern + _NAME_KIND
                         + r'(?:은|는|이|가)?\s*(?:아니|아님)', tail))


def _reference_fields(ctx):
    """원필드별 참조를 읽는다. 인용/댓글을 작성자 주장으로 바꾸지는 않는다."""
    captured = getattr(ctx, '_final_source_original_inputs', None)
    if captured is not None:
        values = [item.get('raw_text') for item in captured if isinstance(item, dict)
                  and item.get('origin') in {'post_title', 'body_line', 'comment'}
                  and item.get('caller_disposition') == 'passed_to_source']
    else:
        values = [span['text'] for span in author_text_spans(getattr(ctx, 'post_data', None) or {})]
        comments = getattr(ctx, '_final_source_original_comment_refs', None)
        if comments is None:
            comments = getattr(ctx, 'comments', None) or ()
        values.extend((item.get('content') or item.get('text') or '') if isinstance(item, dict)
                      else item for item in comments)
    return tuple(value for value in values if isinstance(value, str)
                 and value.strip() and not value.lstrip().startswith(_DERIVED_PREFIXES))


def _explicit_reference_name(raw, title):
    """한 원필드 안의 명명구만 인정한다. 읽기·화자·공개 권한 증명은 아니다."""
    pairs = _NAME_PAIRS
    for hit in re.finditer(re.escape(title), raw):
        lo, hi = hit.span()
        opening = raw[lo-1:lo] if lo else ''
        left, right = raw[:lo], raw[hi:]
        if opening in pairs:
            if not right.startswith(pairs[opening]):
                continue
            left, right = raw[:lo-1], right[1:]
        elif ((lo and re.match(r'[0-9A-Za-z가-힣]', opening))
              or (right and re.match(r'[0-9A-Za-z가-힣]', right)
                  and not _POSTFIX_NAME.match(right)
                  and not re.match(r'(?:을|를|은|는|이|가|의|와|과|처럼|같은|이라는|라고|이다|입니다|임)(?=$|\s|[.,!?])', right))):
            continue
        if _naming_withdrawn(raw, title, lo, hi):
            continue
        postfix = _POSTFIX_NAME.match(right)
        # 소설 + 별도 표제, 또는 제목/작품명 선언. 일반 단어의 단독 출현은 부족하다.
        marker = re.search(r'(?:웹소설|소설|작품)\s+$|(?:작품명|(?:웹소설|소설|작품)의\s*(?:제목|표제))(?:은|는|이|:|：)\s*$', left)
        if marker is None and opening in pairs:
            marker = re.search(r'(?:웹소설|소설|작품)\s*$', left)
        if marker is None and postfix is None:
            continue
        if opening not in pairs and postfix is None and not re.match(
                r'\s*(?:$|[.!?]|(?:이다|입니다|임)(?=$|[.!?\s])|(?:을|를|은|는|이|가|의|와|과)(?=$|\s))', right):
            continue  # '소설 + 소재 단어 + 줄거리'를 제목 명명으로 읽지 않는다.
        return True
    return False


def unbound_degraded_reference(ctx, candidate):
    """URL 불일치 진단은 유지하되 독립 작품 지칭 없는 mentioned/secondary를 막는다.

    정상 URL/별칭, 다른 원인의 미해결 후보, 공개 작품 권한은 이 함수의 범위 밖이다.
    공식 페이지에 같은 단어가 있다는 사실만으로 원문 역할을 대신하지 않는다.
    """
    if ctx is None or candidate is None:
        return False
    title = getattr(candidate, 'official_title', None)
    if not isinstance(title, str) or not title.strip():
        return False
    if getattr(candidate, 'heretic_url', None) or getattr(candidate, 'alias_or_mention', None):
        return False
    if str(getattr(candidate, 'source_tier', '') or '').lower() not in {'llm_only', 'community', 'mixed'}:
        return False
    negative = tuple(str(value) for value in (getattr(candidate, 'negative_evidence', None) or ()))
    if 'candidate_source_missing_url' not in negative or not any(value.startswith('url_title_mismatch:') for value in negative):
        return False
    title = title.strip()
    # 기존 정상 독서/평가/명명 문법은 그대로 재사용한다.
    for occurrence in _author_occurrences(ctx, title, require_work_role=True):
        raw = occurrence['raw_text']
        lo, hi = occurrence['raw_span']
        if _naming_withdrawn(raw, title, lo, hi):
            continue
        opening, closing = raw[lo-1:lo] if lo else '', raw[hi:hi+1]
        if opening in _NAME_PAIRS or closing in _NAME_PAIRS.values():
            if _NAME_PAIRS.get(opening) != closing:
                continue  # 다른 원필드의 괄호와 이어 붙이지 않는다.
        return False
    # 인용 및 댓글의 명명도 보조 참조는 될 수 있다. 현재 작성자의 독서로 승격하지 않는다.
    return not any(_explicit_reference_name(raw, title) for raw in _reference_fields(ctx))
