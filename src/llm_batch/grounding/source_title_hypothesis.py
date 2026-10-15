"""추정 풀이의 후보 승격만 검산한다. 정상 제목의 기존 회수 기준은 바꾸지 않는다."""
from __future__ import annotations

from copy import copy
import hashlib
import re
from urllib.parse import urlsplit

from ..experts.source_spans import author_text_spans
from ..promotion_gate import _supported_official_work_url
from .claim_scope_contract import (
    ASSERTED, NEGATED, QUESTION, Clause, ClaimScopeSource, clause_assertion,
    _CORRECTION_START,
)
from .context_projection_contract import (
    _author_line_clauses, _author_clause_cut, _SURFACE_TAIL, _surface_relation, _cue_backed,
)


def is_title_hypothesis_surface(title):
    """novel_title/fit/best_match 자체가 아니라 값에 붙은 풀이 표지만 본다."""
    raw = str(title or '').strip()
    return bool(re.search(
        r'(?:\((?:추정|가칭|임시\s*제목|또는\s*유사\s*제목)\)|'
        r'(?:^|\s)(?:등(?:의|을)?\s*)?(?:약칭|약자|줄임말)\s*'
        r'(?:가능성|추정|후보|불명|미상|일\s*(?:수|가능성)|으로\s*추정)'
        r'(?:\s*(?:있음|있다|됨|임))?)[.!?]*$', raw))


def _explicit_work_object_name(clause, start, end, marker, admitted, next_clause):
    """독서 사건의 단언과 별개인 명시 작품 목적어. 반환 좌표는 원절 기준이다.

    소설/작품 표지, 정확한 표제, 목적격 조사, 독서 술어가 한 작성자 절에
    모두 있어야 한다. 부정·질문·예정은 이름 후보만 보존하며 독서 proof가 아니다.
    전언·가정·명명 부정은 문형 전체 일치와 기존 작성자 범위로 제외한다.
    """
    assertion = clause_assertion(clause, start, end, next_clause)
    if assertion not in {ASSERTED, NEGATED, QUESTION}:
        return None
    # 질문/부정은 기존 절 판정에서 정정보다 먼저 반환되므로 별도로 재확인한다.
    if next_clause is not None and _CORRECTION_START.match(next_clause.text):
        return None
    pairs = {"'": "'", '"': '"', '「': '」', '『': '』', '《': '》', '“': '”', '‘': '’'}
    opening = clause.text[start-1:start] if start else ''
    closing = clause.text[end:end+1]
    name_start, name_end = start, end
    if opening in pairs or closing in pairs.values():
        if opening not in pairs or closing != pairs[opening]:
            return None
        name_start, name_end = start-1, end+1
    prefix = re.fullmatch(
        r'\s*(?:(?:나는|난|내가|저는|제가)\s+)?(?P<work_marker>웹소설|소설|작품)\s+',
        clause.text[:name_start])
    if prefix is None:
        return None
    negative = (r'(?:읽지\s*(?:않았다|않았음|않았어요|않았습니다|않는다|않음|않아요|않습니다)'
                r'|(?:안|못)\s*읽(?:었다|었음|었어요|었습니다|는다|음|어요|습니다))')
    question = r'읽(?:었(?:나|나요|니|는가|을까)|을(?:까|까요))'
    planned = r'읽을\s*(?:예정|계획)(?:이다|임|입니다|이야|이에요)?'
    suffix = re.fullmatch(
        rf'(?P<object_particle>을|를)\s*(?P<reading_predicate>'
        rf'(?P<negative>{negative})|(?P<question>{question})|(?P<planned>{planned}))'
        r'\s*[.!?。！？]*\s*', clause.text[name_end:])
    if suffix is None:
        return None
    spans = {'work_marker': prefix.span('work_marker'), 'named_object': (name_start, name_end)}
    spans.update({key: (name_end + suffix.start(key), name_end + suffix.end(key))
                  for key in ('object_particle', 'reading_predicate')})
    if not set(range(spans['work_marker'][0], spans['reading_predicate'][1])).issubset(admitted):
        return None
    # 이어지는 절이 같은 이름/그것의 작품명 역할을 직접 철회한 경우도 보존 예외가 아니다.
    if next_clause is not None:
        name = '(?:' + '|'.join(re.escape(value) for value in (
            marker, *(opening + marker + closing for opening, closing in pairs.items()))) + ')'
        denial = (rf'\s*(?:{name}(?:은|는|이|가)|그건|이건|그것은|이것은)\s*'
                  r'(?:작품명|(?:소설|작품)의\s*(?:제목|이름|표제))(?:은|는|이|가)?\s*'
                  r'(?:아니(?:다|라|고|야|에요|었다|었음|었어요|었습니다)|아님|아닙니다)\s*[.!。！]*\s*')
        if re.fullmatch(denial, next_clause.text):
            return None
    mode = 'question' if assertion == QUESTION or suffix.group('question') else (
        'negative' if suffix.group('negative') else 'planned')
    return {'kind': 'explicit_work_object_name', 'scope': 'candidate_name_only',
            'reading_action_mode': mode, 'reading_predicate_negative': bool(suffix.group('negative')),
            'reading_action_asserted': False, 'supports_current_work': False, 'counts_as_core': False,
            'publication_authority': False, 'supports_publish': False,
            'clause_assertion': assertion, 'clause_spans': spans}


def _author_occurrences(ctx, surface, *, require_work_role=False):
    if not isinstance(surface, str) or not surface.strip():
        return ()
    inputs = getattr(ctx, '_final_source_original_inputs', None)
    if inputs is None:
        inputs = tuple({'origin': 'post_title' if x['source'] == 'author_title' else 'body_line',
                        'original_index': x['position'], 'raw_text': x['text'],
                        'caller_disposition': 'passed_to_source'}
                       for x in author_text_spans(getattr(ctx, 'post_data', None) or {}))
    records = [x for x in inputs if isinstance(x, dict)
               and x.get('origin') in {'post_title', 'body_line'}
               and x.get('caller_disposition') == 'passed_to_source'
               and isinstance(x.get('raw_text'), str)]
    titles = [x for x in records if x['origin'] == 'post_title']
    bodies = [x for x in records if x['origin'] == 'body_line']
    # 제목 내부의 ?, 마침표, 괄호는 발화의 질문/추정이 아니다. 같은 길이로
    # 가린 뒤 절을 나누고 원문 좌표를 재검산한다. 인용 부호 바깥은 보존한다.
    marker = '\ue010' * len(surface)
    if any(marker in x['raw_text'] for x in records):
        return ()
    mask = lambda raw: raw.replace(surface, marker)
    source = ClaimScopeSource(post_title=mask(titles[0]['raw_text']) if titles else '',
                              body_lines=tuple(mask(x['raw_text']) for x in bodies), comments=())
    units = []
    for origin, index, _, clauses, boundaries, cuts in _author_line_clauses(source):
        record = titles[0] if origin == 'post_title' else bodies[index]
        units.extend((origin, record, clause, boundary[0], cut)
                     for clause, boundary, cut in zip(clauses, boundaries, cuts))
    found = []
    for ui, (origin, record, clause, boundary, cut) in enumerate(units):
        start, _ = boundary
        if start < 0:
            continue
        kept, quotes, _, lead, stop, _, reason = _author_clause_cut(
            clause.text, *cut, header=origin == 'post_title')
        if reason:
            continue
        admitted = set(kept[lead:stop])
        # 발화 인용만 넘긴다. 「작품명」처럼 명명에 쓰인 괄호는 인용 발화가 아니다.
        scoped = Clause(clause.text, tuple(quotes), clause.terminal)
        nxt = units[ui + 1][2] if ui + 1 < len(units) and units[ui + 1][0] == origin else None
        for hit in re.finditer(re.escape(marker), clause.text):
            lo, hi = start + hit.start(), start + hit.end()
            raw = record['raw_text']
            left = raw[lo-1:lo] if lo else ''
            tail = re.match(r'[0-9A-Za-z가-힣]+', raw[hi:])
            # 한 content block 안의 여러 줄 발화도 원필드 전체에서 확인한다.
            # _author_line_clauses의 carried 범위는 별도 body record 간 인용을 담당한다.
            multiline_quoted = any(a <= lo < b for a, b in (
                m.span() for m in re.finditer(r'''“[^”]*\n[^”]*”|‘[^’]*\n[^’]*’|"[^"]*\n[^"]*"|'[^']*\n[^']*' ''', raw, re.X)))
            if (raw[lo:hi] != surface or (left and re.match(r'[0-9A-Za-z가-힣]', left))
                    or (tail and not _SURFACE_TAIL.fullmatch(tail.group(0)))
                    or multiline_quoted
                    or not set(range(hit.start(), hit.end())).issubset(admitted)):
                continue
            basis = 'author_occurrence'
            if require_work_role:
                # split_clauses는 보고된 질문을 한 절로 보존한다. 그러므로 표제 뒤
                # '? 라고 물었다'를 독서 관계 fallback이 직접 단언으로 읽지 못하게 한다.
                # 표제 내부 물음표는 marker로 가렸으므로 여기에는 포함되지 않는다.
                if re.search(r'[?？][ \t]*(?:이?라고|라며|냐고|하고)(?=\s|물|묻|질문|말|했|하)',
                             clause.text[hit.end():]):
                    continue
                naming = _explicit_work_object_name(scoped, hit.start(), hit.end(), marker, admitted, nxt)
                if naming is not None:
                    local_spans = naming.pop('clause_spans')
                    naming['raw_spans'] = {key: [start + a, start + b]
                                           for key, (a, b) in local_spans.items()}
                    naming['raw_evidence'] = {key: raw[a:b] for key, (a, b) in naming['raw_spans'].items()}
                    found.append({'origin': origin, 'original_index': record['original_index'],
                                  'raw_span': [lo, hi], 'raw_text': raw,
                                  'basis': 'explicit_work_object_name_without_reading_assertion',
                                  'role_evidence': naming,
                                  'source_sha256': hashlib.sha256(raw.encode()).hexdigest()})
                    continue
                if clause_assertion(scoped, hit.start(), hit.end(), nxt) != ASSERTED:
                    continue
                # 위의 좁은 명명 예외 밖에서는 가정/계획을 기존 독서 관계로 승격하지 않는다.
                outside = clause.text[:hit.start()] + clause.text[hit.end():]
                if re.search(r'만약|가령|가정|(?:이라|라|다)면|(?:을|를)\s*경우|'
                             r'추정|가능성|일\s*수|읽(?:으면|는다면|을\s*(?:예정|계획))', outside):
                    continue
                # 인용/부정 검사를 통과한 정확한 명명 표제의 괄호만 독서 대상에
                # 포함한다. '표제'을의 닫는 부호 때문에 을만 별도 목적어가 되지 않게
                # 기존 관계 검사에 한 표면으로 넘긴다. 원문 좌표와 인용 판정은 그대로다.
                role_start, role_end, role_surface = hit.start(), hit.end(), marker
                pairs = {"'": "'", '"': '"', '「': '」', '『': '』', '《': '》', '“': '”', '‘': '’'}
                opening = clause.text[hit.start()-1:hit.start()] if hit.start() else ''
                closing = clause.text[hit.end():hit.end()+1]
                if (opening in pairs and closing == pairs[opening]
                        and {hit.start()-1, hit.end()}.issubset(admitted)):
                    role_start, role_end = hit.start()-1, hit.end()+1
                    role_surface = clause.text[role_start:role_end]
                relation, cue, _ = _surface_relation([clause.text], 0, role_start, role_end, role_surface, [role_surface])
                q, z = r'''["'「『《“‘]?''', r'''["'」』》”’]?'''
                name = q + re.escape(marker) + z
                explicit_name = any(re.fullmatch(p, clause.text.strip().rstrip('.!。！').strip()) for p in (
                    rf'(?:이\s*|그\s*)?(?:웹소설|소설|작품)의\s*(?:정식\s*)?(?:제목|이름|표제)(?:은|는)\s*{name}(?:이다|다|임|입니다)',
                    rf'{name}(?:은|는)\s*(?:웹소설|소설|작품)(?:의\s*(?:제목|이름|표제))?(?:이다|다|임|입니다)',
                    rf'(?:웹소설|소설|작품)\s+{name}(?:이다|다|임|입니다)?',
                ))
                if not explicit_name and not (relation == 'current_work' and _cue_backed(cue)):
                    continue
                basis = 'explicit_work_name' if explicit_name else cue
            found.append({'origin': origin, 'original_index': record['original_index'],
                          'raw_span': [lo, hi], 'raw_text': raw, 'basis': basis,
                          'source_sha256': hashlib.sha256(raw.encode()).hexdigest()})
    return tuple(found)


def title_hypothesis_source_support(ctx, alias, title):
    """가설형 표제가 실제 이름인 예외 근거. 일반 제목에 강제하는 새 문법이 아니다.

    원문 명명/독서 대상과 한 외부 필드 전체의 명시 alias 선언을
    구분한다. 제목 metadata·query 조각을 이어 붙이거나 일부 인용 절만 꺼내지 않는다.
    후보 보존 근거이며 해당 글의 식별/공개/탐색 완전성 권한은 아니다.
    공식 표제 예외는 각 호출자의 기존 공식 제목 추출/검산 경로에서 별도로 처리한다.
    """
    if not isinstance(title, str) or not title.strip():
        return None
    title = title.strip()
    literal = _author_occurrences(ctx, title, require_work_role=True)
    common = {'title': title, 'publication_authority': False, 'supports_publish': False}
    if literal:
        return dict(literal[0], **common, kind='author_work_name')
    occurrences = _author_occurrences(ctx, alias, require_work_role=True)
    rows = list(getattr(ctx, 'search_results', None) or ()) + list(getattr(ctx, 'fetched_page_info', None) or ())
    for row in rows:
        if (not isinstance(row, dict) or row.get('_ocr_diagnostic_only') is True
                or row.get('_purpose') == 'image_ocr_diagnostic_probe'):
            continue
        provenance = ' '.join(str(row.get(key) or '') for key in
                              ('source', 'origin', 'provenance', 'generated_source', 'source_tier')).lower()
        if (any(row.get(key) is True for key in ('is_generated', 'generated', 'from_ocr', 'is_ocr'))
                or any(word in provenance for word in ('llm', 'model', 'generated', 'ocr', 'vlm'))):
            continue
        url = row.get('url')
        if not isinstance(url, str):
            continue
        try:
            parsed = urlsplit(url)
            host = (parsed.hostname or '').lower().rstrip('.')
            if parsed.scheme not in {'http', 'https'} or not host or parsed.username or parsed.password:
                continue
        except ValueError:
            continue
        official = _supported_official_work_url(url)
        domains = ('dcinside.com', 'fmkorea.com', 'arca.live', 'arcalive.com', 'namu.wiki',
                   'ruliweb.com', 'theqoo.net', 'clien.net')
        community = any(host == x or host.endswith('.' + x) for x in domains)
        if not official and not community:
            continue
        if not occurrences:
            continue
        q, z = r'''["'「『《“‘]?''', r'''["'」』》”’]?'''
        t, a = q + re.escape(title) + z, q + re.escape(alias.strip()) + z
        marker = r'(?:약칭|약자|줄임말|별칭|약어)'
        predicates = (
            rf'(?:웹소설\s+|소설\s+|작품\s+)?{t}\s*(?:의\s*)?{marker}(?:은|는|:|：)\s*{a}\s*(?:이다|다|임|라고\s*한다|이라고\s*한다)',
            rf'{a}(?:은|는)\s*(?:웹소설\s+|소설\s+|작품\s+)?{t}\s*(?:의\s*)?{marker}\s*(?:이다|다|임|으로\s*(?:쓰인다|불린다|사용된다))',
            rf'(?:웹소설\s+|소설\s+|작품\s+)?{t}(?:을|를)?\s*줄여서\s*{a}\s*(?:라고|이라고)\s*(?:한다|부른다)',
        )
        for field in ('content', 'snippet', 'description'):
            raw = row.get(field)
            if not isinstance(raw, str):
                continue
            # 필드 전체를 읽어 선언의 바깥 문맥도 보존한다. 제목 내부 부호는
            # escape한 제목의 일부이며 ?, 개행에서 문장을 임의로 쪼개지 않는다.
            if not any(re.fullmatch(r'\s*' + p + r'[.!。！]?\s*', raw) for p in predicates):
                continue
            return dict(common, kind='source_alias_declaration', alias=alias.strip(),
                        author_occurrence=occurrences[0], source_url=url, source_field=field,
                        raw_span=[0, len(raw)], assertion=raw,
                        source_sha256=hashlib.sha256(raw.encode()).hexdigest())
    return None


def title_hypothesis_observation_context(ctx):
    """기존 공식 검산에 원관측만 공급한다. ctx/원문/증거 dict는 수정하지 않는다.

    일반 제목 경로에는 사용하지 않는다. 생성/OCR/진단 전용 행의 provenance
    제외는 alias 예외와 같고, 삭제/목록/비작품 등 부정 관측은 지우지 않는다.
    """
    def observed(row):
        if (not isinstance(row, dict) or row.get('_ocr_diagnostic_only') is True
                or row.get('_purpose') == 'image_ocr_diagnostic_probe'):
            return False
        # 기존 공식 checker의 문자열 포함 판정을 그대로 신뢰하지 않는다.
        # 상세 경로·페이지 상태·매체 검산은 아래 원래 checker에 남긴다.
        try:
            parsed = urlsplit(str(row.get('url') or ''))
            host = str(parsed.hostname or '').lower()
            domains = ('novelpia.com', 'series.naver.com', 'page.kakao.com', 'kakao.page',
                       'munpia.com', 'ridibooks.com', 'joara.com')
            if (parsed.scheme.lower() not in {'http', 'https'} or parsed.username is not None
                    or parsed.password is not None
                    or not any(host == domain or host.endswith('.' + domain) for domain in domains)):
                return False
        except ValueError:
            return False
        provenance = ' '.join(str(row.get(key) or '') for key in
            ('source', 'origin', 'provenance', 'generated_source', 'source_tier')).lower()
        return not (any(row.get(key) is True for key in ('is_generated', 'generated', 'from_ocr', 'is_ocr'))
                    or any(word in provenance for word in ('llm', 'model', 'generated', 'ocr', 'vlm')))
    observed_ctx = copy(ctx)
    observed_ctx.search_results = [row for row in getattr(ctx, 'search_results', None) or () if observed(row)]
    observed_ctx.fetched_page_info = [row for row in getattr(ctx, 'fetched_page_info', None) or () if observed(row)]
    return observed_ctx


def unbound_decoder_title_hypothesis(ctx, title, decoded_terms, *, source_term=None):
    if not is_title_hypothesis_surface(title):
        return False
    aliases = [source_term]
    for term in decoded_terms or ():
        if not isinstance(term, dict):
            continue
        best = term.get('best_match')
        names = [str(best.get('title') or '').strip()] if isinstance(best, dict) else []
        names.extend(str(x.get('value') or '').strip() for x in term.get('interpretations') or () if isinstance(x, dict))
        names.extend(str(x.get('official_novel_title') or x.get('official_title') or '').strip()
                     for x in term.get('candidates') or () if isinstance(x, dict))
        if str(title or '').strip() in names:
            aliases.append(term.get('original'))
    return not any(title_hypothesis_source_support(ctx, alias, title) for alias in aliases)


def record_title_hypothesis_observation(ctx, title, alias, source):
    observation = {'text': title, 'alias_or_mention': alias, 'source': source,
                   'reason_code': 'unbound_title_hypothesis_not_candidate',
                   'publication_authority': False, 'supports_publish': False}
    observations = list(getattr(ctx, '_title_meta_explanation_observations', ()) or ())
    if observation not in observations and len(observations) < 24:
        observations.append(observation)
    ctx._title_meta_explanation_observations = tuple(observations)
