"""작성자의 원문 요청 대상과 생략된 서사 요청. 댓글 이름의 Low 보존만 지원한다."""
from __future__ import annotations

import re

from ..experts.source_spans import author_text_spans, direct_author_recommendation_request_spans, _DIRECT_REQUEST
from .context_projection_contract import _author_quote_spans, _carried_quote_ranges

WORD = r'0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ_'
TAIL = r'(?=(?:같은|비슷한)|(?:으로|에서|이라도|이라|라고|이나|은|는|이|가|을|를|도|만|의)?(?:\s|[.!?。！？,]|$))'
WORK_NOUN = r'(?<![' + WORD + r'])(?:웹소설|해외소설|번역소설|소설|작품|책)' + TAIL
GENRE_NOUN = r'(?<![' + WORD + r'])(?:무협|판타지|로판|선협|백합물|라노벨)(?:물|소설)?' + TAIL
OTHER_MEDIUM = r'(?:(?:판타지|SF|공포|로맨스)\s*)?(?:영화|웹툰|만화|애니메이션|애니|드라마|게임)|음식|요리|식당|맛집|메뉴|산책|공원|여행|장소'
NON_NOVEL_NOUN = r'(?<![' + WORD + r'])(?:' + OTHER_MEDIUM + r')(?:할\s*곳)?' + TAIL


def unquoted(match, quotes):
    return bool(match and not any(max(match.start(), lo) < min(match.end(), hi) for lo, hi in quotes))


def noun_quotes(text, quotes):
    # 명명 표제 내부의 '게임/영화/책'도 요청 대상 매체와 구분한다.
    ranges = list(quotes)
    for opening, closing in [('「', '」'), ('『', '』'), ('《', '》'), ('“', '”'), ('‘', '’'), ('"', '"'), ("'", "'")]:
        pattern = re.escape(opening) + '[^' + re.escape(opening + closing) + '\r\n]+' + re.escape(closing)
        ranges.extend(match.span() for match in re.finditer(pattern, text))
    return ranges


def current_author_text(text):
    return not (re.match(r'^\s*(?:>|[│|]|인용\s*[:：]|댓글\s*[:：]|'
        r'(?:기록|대화\s*기록|전재|원문|버튼\s*문구)\s*[:：]|'
        r'(?:친구|지인|동생|형|누나|언니|작가|누군가|다른\s*사람)(?:가|이|는|:|：))', text)
        or re.search(r'(?:냐고|달라고|라고)\s*(?:물|말|했|하|적|써)', text))


def request_has_non_novel_target(text, quotes):
    """같은 요청절의 명시 타매체/일상 명사를 확인한다. 이름 인용 내부는 제외한다."""
    masked = noun_quotes(text, quotes)
    others = [m for m in re.finditer(NON_NOVEL_NOUN, text, re.IGNORECASE) if unquoted(m, masked)]
    if not others:
        return False
    works = [m for m in re.finditer(WORK_NOUN, text, re.IGNORECASE) if unquoted(m, masked)]
    # '영화 같은 소설 추천'과 '소설 같은 영화 추천'은 마지막 요청 대상이 다르다.
    return not works or works[-1].start() < others[-1].start()


def explicit_other_medium_request(text, quotes):
    pattern = r'(?<![' + WORD + r'])(?:' + OTHER_MEDIUM + r')' + r'(?:의\s*(?:제목|작품명)|\s*(?:제목|작품명)|(?:을|를)?\s*(?:좀\s*)?추천)'
    return any(unquoted(m, noun_quotes(text, quotes)) for m in re.finditer(pattern, text, re.IGNORECASE))


def request_has_work_target(text, quotes):
    if request_has_non_novel_target(text, quotes):
        return False
    return any(unquoted(m, noun_quotes(text, quotes)) for m in re.finditer(
        WORK_NOUN + '|' + GENRE_NOUN + r'|(?<![' + WORD + r'])(?:읽을|읽으면)(?=\s|$)', text, re.IGNORECASE))


def bare_work_recommendation_request(text, quotes):
    """기존 helper의 3글자 최소 대상보다 짧은 명시 책/소설 목적어만 보완한다."""
    if not current_author_text(text) or request_has_non_novel_target(text, quotes):
        return False
    match = re.fullmatch(r'\s*' + WORK_NOUN + r'(?:을|를|은|는|도|만)?\s*'
        + _DIRECT_REQUEST.pattern + r'\s*[.!?。！？~]*\s*', text)
    return unquoted(match, quotes)


def novel_existence_request(text, quotes):
    """소설을 찾는 존재 질문. 보고/가정된 질문이나 단순 존재 단언은 제외한다."""
    if not current_author_text(text) or request_has_non_novel_target(text, quotes):
        return None
    if re.search(r'만약|가령|(?:이라|라|다)면|없(?:다면|으면)|있(?:다면|으면)', text):
        return None
    noun = WORK_NOUN
    pattern = noun + r'(?:은|는|이|가|도|좀)?\s*(?:어디\s*)?(?:없(?:냐|나요|나|을까)|있(?:냐|나요|나|을까))\s*[?？!！.。~]*\s*$'
    for match in re.finditer(pattern, text, re.IGNORECASE):
        if unquoted(match, quotes):
            return match.span()
    return None


def unlabelled_reply_is_predication(text):
    """명칭 표지 없는 답변의 끝맺은 서술을 구분한다. 이름의 단어 목록은 없다."""
    raw = str(text or '').rstrip(' .!?。！？~…ㅋㅎ')
    if not raw:
        return False
    from ..promotion_gate import _edition_kiwi
    kiwi = _edition_kiwi()
    if kiwi is None:
        return True  # 새 회수 경로의 무표지 답변을 판독할 수 없으면 보류한다.
    tokens = list(kiwi.tokenize(raw))
    if not tokens:
        return True
    last = tokens[-1]
    if last.start + last.len != len(raw) or last.tag not in {'EF', 'ETN'}:
        return False
    return any(token.tag.split('-')[0] in {'VV', 'VA', 'VX', 'VCP', 'VCN'} for token in tokens[-5:])


def nominal_mul_ending_is_lexical(text):
    """Low 응답에서만 X물 추정과 물로 끝나는 실제 명사를 구분한다.

    명시 장르/구조/반응/요청 관계 필터를 대체하지 않는다. native 토큰이
    원문 전체를 빈틈없이 명사로 읽고 말미가 독립 '물'이 아닐 때만 근거가 있다.
    """
    if not isinstance(text, str) or not re.fullmatch(r'[가-힣]{3,5}물', text):
        return False
    from ..promotion_gate import _edition_kiwi
    try:
        kiwi = _edition_kiwi()
        if kiwi is None:
            return False
        tokens = list(kiwi.tokenize(text))
    except Exception:
        return False
    # 한 토큰 전체가 명사인 것만으로 장르 접미 추정을 해제하지 않는다.
    # 앞 명사와 분리된 말미 명사가 원문의 별도 구간으로 확인되어야 한다.
    if len(tokens) < 2:
        return False
    cursor = 0
    for token in tokens:
        if (token.tag not in {'NNG', 'NNP'} or token.start != cursor or token.len <= 0
                or text[token.start:token.start + token.len] != token.form):
            return False
        cursor = token.start + token.len
    last = tokens[-1]
    return (cursor == len(text) and len(last.form) >= 2
            and last.form.endswith('물') and last.form != '물')


def elliptic_narrative_request(post):
    """같은 작성자의 비교 추천+독서 영역 또는 장면·서사 선호를 원필드별로 결속한다.

    갤러리명/모델 target/후보 제목 목록은 사용하지 않는다. 모호한 이름의
    작품 정체를 확정하지 않으며 source comparison의 공개/주작품 carrier도 만들지 않는다.
    """
    units = []
    for span in author_text_spans(post):
        offset = 0
        for part in span['text'].splitlines(keepends=True):
            text = part.rstrip('\r\n')
            units.append({'origin': 'post_title' if span['source'] == 'author_title' else 'body_line',
                'original_index': span['position'], 'raw_span': [offset, offset + len(text)], 'text': text,
                'source': span['source']})
            offset += len(part)
    bodies = [u for u in units if u['origin'] == 'body_line']
    bounds = iter(_carried_quote_ranges([u['text'] for u in bodies]))
    for unit in units:
        unit['quotes'] = _author_quote_spans(unit['text'], *(next(bounds) if unit['origin'] == 'body_line' else (0, -1)))
    def pointer(unit):
        return {key: unit[key] for key in ('origin', 'original_index', 'raw_span', 'text')}
    def matches(unit, pattern):
        return current_author_text(unit['text']) and any(unquoted(m, unit['quotes']) for m in re.finditer(pattern, unit['text']))
    # explicit 타매체가 있는 생략 문맥은 novel 요청으로 채우지 않는다.
    if any(current_author_text(u['text']) and request_has_non_novel_target(u['text'], u['quotes']) for u in units):
        return {}
    for request in direct_author_recommendation_request_spans(post):
        relative_request = request['request_start'] - request['char_start']
        prefix = request['text'][:relative_request]
        comparison = re.fullmatch(r'\s*(?:(?:나는|내가|난|저는|제가)\s+)?'
            r'(?P<name>[^\r\n]{1,80}?)\s*(?P<comparison>같은|비슷한)\s*(?:거|것)(?:로|으로|을|를)?\s*', prefix)
        if comparison is None:
            continue
        unit = next((u for u in units if u['source'] == request['source'] and u['original_index'] == request['position']
            and u['raw_span'][0] <= request['request_start'] < request['request_end'] <= u['raw_span'][1]), None)
        if unit is None or not current_author_text(unit['text']):
            continue
        raw_name = comparison['name']
        lo = request['char_start'] + comparison.start('name') + len(raw_name) - len(raw_name.lstrip())
        hi = request['char_start'] + comparison.end('name') - len(raw_name) + len(raw_name.rstrip())
        name = raw_name.strip()
        if not name or any(mark in name for mark in '\n\r;'):
            continue
        # 요청절 전체를 인용/전언에서 떼어내거나 quoted NP를 임의로 작품으로 승격하지 않는다.
        local_start, local_end = request['request_start'] - unit['raw_span'][0], request['request_end'] - unit['raw_span'][0]
        if any(max(local_start, a) < min(local_end, b) for a, b in unit['quotes']):
            continue
        reading = [u for u in units if matches(u, WORK_NOUN + r'|(?<![' + WORD + r'])읽(?:고\s*싶|을|는|었)')]
        scene = [u for u in units if matches(u, r'(?<![' + WORD + r'])(?:씬|장면|전개)(?:이|가|을|를)?\s*'
            r'(?:나오는\s*(?:거|것)(?:이|을|를)?\s*)?(?:보고\s*싶(?:다|어|음|네요)|원한다)\s*[.!?~]*\s*$')]
        preference = [u for u in units if matches(u, r'(?<![' + WORD + r'])(?:유열|피폐|후회|구원|성장|복수)(?:물|서사|전개)?'
            r'(?:이|가|을|를)?\s*(?:보고\s*싶(?:다|어|음|네요)|원한다)\s*[.!?~]*\s*$')]
        support = reading[:1] or ([scene[0], preference[0]] if scene and preference and scene[0] is not preference[0] else [])
        if not support:
            continue
        selected = [unit] + [u for u in support if u is not unit]
        return {'kind': 'source_elliptic_narrative_recommendation_request',
            'source_units': [pointer(u) for u in selected],
            'comparison_observation': {'surface': name, 'raw_span': [lo, hi], 'source': request['source'],
                'original_index': request['position'], 'comparator': comparison['comparison'],
                'request_raw_span': [request['request_start'], request['request_end']]},
            'source_authority': False, 'supports_publish': False, 'scope': 'low_reply_preservation_only'}
    return {}
