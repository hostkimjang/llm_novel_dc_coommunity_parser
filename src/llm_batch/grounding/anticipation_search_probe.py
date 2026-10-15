"""서로 다른 원문 표면을 가진 기다림 글의 확인 검색 한 개를 구성한다."""
from __future__ import annotations

import re
from typing import Any

from ..experts.source_spans import author_text_spans


_AUTHOR_ANTICIPATION_RE = re.compile(
    r'(?:올\s*때\s*(?:됐|되)|올\s*때(?:까지)?\s*기다(?:리|린|림|려)|연재\s*(?:재개|복귀|기대)|'
    r'재연재|복귀|귀환|돌아오|돌아와|휴재\s*끝|기우제)'
)
_INLINE_QUOTE_RE = re.compile(r'["“][^"”]*["”]|[‘][^’]*[’]|\x27[^\x27]*\x27')
_REPORTED_ANTICIPATION_TAIL_RE = re.compile(
    r'^\s*(?:[가-힣]{0,8}\s*){0,3}?(?:다고|다며|다더라|다던데|다는데|다는|'
    r'라고|라며|라던데|라는|라니|'
    r'대(?=\s|$)|래(?=\s|$))'
)
_FIRST_PERSON_OPINION_RE = re.compile(r'(?:^|\s)(?:나는|난|내가|나도|내\s*생각엔|우리도)\s+')
_AUTHOR_OPINION_END_RE = re.compile(r'(?:본다|생각한다|기대한다|기다린다|기다림)\s*$')


def _external_subject_before_marker(clause: str, marker_start: int) -> bool:
    """A separate subject before the work surface owns this expectation clause."""
    prefix = clause[:marker_start]
    words = re.findall(r'[가-힣]+', prefix)
    if not words:
        return False
    last_word = words[-1]
    for match in re.finditer(r'(?<![가-힣])([가-힣]{1,12})(?:이|가)(?=\s)', prefix):
        subject = match.group(1)
        if subject in {'나', '내', '우리', '제가', '저'}:
            continue
        if match.group(0).strip() == last_word:
            continue
        return True
    return False


def authored_anticipation_title_span(post: Any) -> str:
    """Return a direct author expectation clause, excluding reported speech."""
    title = next((
        str(span.get('text') or '') for span in author_text_spans(post)
        if span.get('source') == 'author_title'
    ), '')
    for clause in re.split(r'(?:지만|[,;。.!?])\s*', title):
        authored = _INLINE_QUOTE_RE.sub(' ', clause).strip()
        marker = _AUTHOR_ANTICIPATION_RE.search(authored)
        if not marker:
            continue
        if _external_subject_before_marker(authored, marker.start()):
            continue
        if _REPORTED_ANTICIPATION_TAIL_RE.match(authored[marker.end():]) and not (
            _FIRST_PERSON_OPINION_RE.search(authored)
            and _AUTHOR_OPINION_END_RE.search(authored)
        ):
            continue
        return authored
    return ''


def anticipation_title_surface_present(post: Any) -> bool:
    """Detect an expectation surface before deciding who said it."""
    title = str(post.get('title') or '') if isinstance(post, dict) else ''
    return bool(_AUTHOR_ANTICIPATION_RE.search(title))


def anticipation_relation_marker_present(text: Any) -> bool:
    """Check a relation marker after the verified alias was removed."""
    return isinstance(text, str) and bool(_AUTHOR_ANTICIPATION_RE.search(text))


def _compact_source_title(value: Any) -> str:
    return re.sub(r'[^0-9a-z가-힣]', '', value.lower()) if isinstance(value, str) else ''


def source_bound_search_row_fingerprint(row: Any) -> str:
    """Bind an assertion to one exact search row without query/model fields."""
    import hashlib
    import json

    if not isinstance(row, dict):
        return ''
    payload = {
        key: row.get(key)
        for key in ('title', 'page_title', 'url', 'content', 'snippet', 'description')
        if isinstance(row.get(key), str)
    }
    if not payload.get('url') or not (payload.get('title') or payload.get('page_title')):
        return ''
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _source_bound_wiki_rows(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Return exact Namu document-title/path bindings with novel-shaped text."""
    from urllib.parse import unquote, urlsplit

    bound: list[dict[str, str]] = []
    if not isinstance(rows, list):
        return bound
    for row in rows[:120]:
        if not isinstance(row, dict):
            continue
        if row.get('_ocr_diagnostic_only') is True or row.get('_purpose') == 'image_ocr_diagnostic_probe':
            continue
        url = row.get('url')
        raw_title = row.get('title') or row.get('page_title')
        if not isinstance(url, str) or not isinstance(raw_title, str):
            continue
        try:
            parsed = urlsplit(url)
            path = unquote(parsed.path)
            if (
                parsed.scheme != 'https'
                or parsed.hostname not in {'namu.wiki', 'www.namu.wiki'}
                or parsed.username
                or parsed.password
                or parsed.port not in (None, 443)
                or not path.startswith('/w/')
            ):
                continue
        except ValueError:
            continue
        url_title = path[3:].strip('/')
        source_title = re.sub(r'\s*[-–]\s*나무위키(?::대문)?\s*$', '', raw_title).strip()
        source_key = _compact_source_title(source_title)
        if '/' in url_title or not 6 <= len(source_key) <= 80 or _compact_source_title(url_title) != source_key:
            continue
        body = '\n'.join(
            row[key]
            for key in ('content', 'snippet', 'description')
            if isinstance(row.get(key), str)
        )[:6000]
        if '소설' not in body:
            continue
        if re.search(
            r'(?:^|[.!?\n])\s*(?:한국|일본|중국|미국)의?[^.!?\n]{0,20}?'
            r'(?:만화|웹툰|애니메이션|게임)\s*(?:이다)?[.!?\n]',
            body,
        ):
            continue
        bound.append({
            'source_key': source_key,
            'source_title': source_title,
            'source_url': url,
            'body': body,
            'source_row_sha256': source_bound_search_row_fingerprint(row),
        })
    return bound


def _source_bound_sentence_parts(body: str) -> list[tuple[str, str]]:
    parts: list[tuple[str, str]] = []
    for match in re.finditer(r'([^.!?。！？\n\r]+)([.!?。！？]?)', body):
        sentence = match.group(1).strip()
        if sentence:
            parts.append((sentence, match.group(2)))
    return parts


def _source_bound_novel_document(source_title: str, body: str) -> bool:
    """Require the bound document itself, rather than its origin, to be a novel."""
    sentences = [sentence for sentence, _ in _source_bound_sentence_parts(body)]
    if not sentences:
        return False

    non_novel_type = r'(?:웹툰|만화|애니메이션|보드게임|게임|영화|드라마)'
    non_novel_identity = re.compile(
        rf'^(?:개요\s*)?(?:이|본|해당)?\s*(?:작품|문서)?(?:은|는|이|가)?\s*'
        rf'[^.!?\n]{{0,56}}?{non_novel_type}\s*(?:작품)?(?:이다|임)\s*$'
    )
    unrelated_non_novel = re.compile(
        rf'(?:동명(?:의)?\s*)?(?:웹\s*)?소설[^.!?\n]{{0,28}}?'
        rf'(?:무관|별개|아니)[^.!?\n]{{0,28}}?{non_novel_type}'
    )
    if any(
        non_novel_identity.search(sentence) or unrelated_non_novel.search(sentence)
        for sentence in sentences
    ):
        return False

    source_subject = re.escape(source_title)
    explicit_subject = re.compile(
        rf'^(?:개요\s*)?(?:{source_subject}|(?:이|본|해당)\s*(?:작품|소설|문서))'
        rf'(?:은|는|이|가)?\s*[^.!?\n]{{0,48}}?(?:웹\s*)?소설\s*(?:작품)?(?:이다|임)?\s*$'
    )
    country_intro = re.compile(
        r'^(?:개요\s*)?(?:한국|대한민국|일본|중국|대만|미국)(?:의)?\s*'
        r'[^.!?\n]{0,48}?(?:웹\s*)?소설\s*(?:작품)?(?:이다|임)?\s*$'
    )
    bare_novel_identity = re.compile(
        r'^(?:개요\s*)?[^.!?\n]{0,36}?(?:웹\s*)?소설\s*(?:작품)?(?:이다|임)?\s*$'
    )
    unbound_subject = re.compile(r'^(?:개요\s*)?[^\s]{1,24}(?:은|는|이|가)\s+')
    non_subject_prefix = re.compile(
        r'^(?:개요\s*)?(?:원작|원작품|각색작|미디어믹스|동명작)(?:은|는|이|가|의)?(?:\s|$)'
    )
    for sentence in sentences:
        if (
            non_subject_prefix.search(sentence)
            or re.search(r'(?:소설|작품)\s*(?:이|가|은|는)?\s*(?:아니|무관|별개)', sentence)
        ):
            continue
        if explicit_subject.search(sentence) or country_intro.search(sentence):
            return True
        if not unbound_subject.search(sentence) and bare_novel_identity.search(sentence):
            return True
    return False


def source_bound_alias_assertion(
    title: str,
    alias_terms: list[str],
    rows: list[dict[str, Any]],
    *,
    source_text: str,
    support_surface: str = '',
) -> dict[str, str] | None:
    """Read an explicit alias declaration only from an exact source-bound row.

    The query, a different row, OCR/model prose, or an unrelated trailing mention
    cannot supply a missing part of the title/alias relation.
    """
    import hashlib

    if (
        not isinstance(title, str)
        or not isinstance(alias_terms, list)
        or not isinstance(rows, list)
        or not isinstance(source_text, str)
        or not isinstance(support_surface, str)
    ):
        return None
    target = _compact_source_title(title)
    if not 6 <= len(target) <= 80:
        return None

    word = r'0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ_'

    def visible(text: str, token: str) -> bool:
        return bool(re.search(
            rf'(?<![{word}]){re.escape(token)}'
            rf'(?:으로|라고|이라|이다|은|는|이|가|을|를|의|도|만|다)?(?![{word}])',
            text,
        ))

    aliases: list[str] = []
    for value in alias_terms:
        alias = value.strip() if isinstance(value, str) else ''
        if (
            alias
            and alias not in aliases
            and re.fullmatch(r'[0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ_]{2,32}', alias)
            and visible(source_text, alias)
        ):
            aliases.append(alias)
    if not aliases:
        return None

    negative = re.compile(
        r'아니|않|잘못|오해|착각|거짓|오류|다른\s*(?:작품|소설|제목|문서)|'
        r'별개\s*(?:작품|소설|제목|문서)|(?:후보|가칭|임시명|추정)'
    )
    non_declaration = re.compile(
        r'(?:약칭|줄임말|통칭|별칭|약어)(?:을|를)\s*'
        r'(?:검색|찾|확인|조사|질문|언급|설명|소개)'
    )
    marker = r'(?:약칭|줄임말|통칭|별칭|약어)'
    derivation = (
        r'(?:(?:제목|작품명|정식명)(?:에서|의)?\s*'
        r'(?:(?:각|한|첫|앞)\s*)?(?:글자|음절)(?:씩)?\s*'
        r'(?:따온|딴|따서|조합한|줄인)\s*)?'
    )

    declarations: dict[str, dict[str, dict[str, str]]] = {}

    alias_item_pattern = r'''['"“”‘’]?[0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ_]{2,32}['"“”‘’]?'''

    def parse_alias_list_claim(claim: str) -> set[str]:
        value = claim.strip()
        list_text = ''
        for predicate in (
            r'(?P<items>.+?)\s*(?:이라고|라고)\s*(?:한다|부른다|불린다|통한다)\s*$',
            r'(?P<items>.+?)\s*(?:이라|라|으로|로)\s*(?:불린다|부른다|통한다)\s*$',
            r'(?P<items>.+?)\s*(?:이다|임)\s*$',
        ):
            matched = re.fullmatch(predicate, value)
            if matched:
                list_text = matched.group('items').strip()
                break
        if not list_text and value.endswith('다'):
            possible = value[:-1].strip()
            possible_items = re.split(r'\s*(?:,|·|/|또는|혹은|및)\s*', possible)
            final_item = possible_items[-1].strip(' \t\r\n\'"“”‘’') if possible_items else ''
            if final_item in aliases:
                list_text = possible
        if not list_text:
            return set()
        raw_items = re.split(r'\s*(?:,|·|/|또는|혹은|및)\s*', list_text)
        if not 1 <= len(raw_items) <= 7:
            return set()
        items: set[str] = set()
        for raw_item in raw_items:
            if not re.fullmatch(alias_item_pattern, raw_item.strip()):
                return set()
            item = raw_item.strip().strip('\'"“”‘’')
            if not item:
                return set()
            items.add(item)
        return items

    for row in _source_bound_wiki_rows(rows):
        source_key = row['source_key']
        source_title = row['source_title']
        body = row['body']
        sentence_parts = _source_bound_sentence_parts(body)
        sentences = [sentence for sentence, _ in sentence_parts]
        if not _source_bound_novel_document(source_title, body):
            continue
        author_sentences: list[str] = []
        if support_surface:
            author = re.escape(support_surface)
            author_re = re.compile(
                rf'''(?<![{word}]){author}['"“”‘’]?\s*(?:작가|저자)(?:의|가|는)?(?![{word}])'''
                rf'''|(?:작가|저자)(?:는|은|:)?\s*['"“”‘’]?{author}['"“”‘’]?(?:이다|다)?(?![{word}])'''
            )
            author_sentences = [sentence for sentence in sentences if author_re.search(sentence)]
            if not author_sentences or any(negative.search(sentence) for sentence in author_sentences):
                continue

        for alias in aliases:
            title_value = re.escape(source_title)
            subject = (
                rf'(?:(?:이|본|해당)\s*(?:작품|소설)(?:의)?\s*|'
                rf'{title_value}\s*(?:의)?\s*)?'
            )
            declaration_prefixes = (
                re.compile(rf'^\s*{subject}{marker}\s*(?:은|는|이|가|:|=)\s*{derivation}(?P<claim>.+?)\s*$'),
                re.compile(rf'^\s*{subject}{marker}\s*(?:으로|로)\s*(?P<claim>.+?)\s*$'),
                re.compile(
                    rf'^\s*{subject}(?:제목|작품명|정식명)(?:을|를)?\s*'
                    rf'(?:줄여서|줄여|줄인\s*말로)\s*(?P<claim>.+?)\s*$'
                ),
            )
            non_assertive_ending = re.compile(
                r'(?:인가|일까|겠나|이라면|라면|이면)\s*$|'
                r'(?:보다|보다는)[^.!?\n]{0,32}(?:가깝|비슷|낫)'
            )
            contradictory = any(
                negative.search(sentence)
                and (visible(sentence, alias) or re.search(marker, sentence))
                for sentence in sentences
            )
            if contradictory:
                continue
            declared_sentence = ''
            for sentence, terminal in sentence_parts:
                if (
                    terminal in {'?', '？'}
                    or negative.search(sentence)
                    or non_declaration.search(sentence)
                    or non_assertive_ending.search(sentence)
                ):
                    continue
                for prefix in declaration_prefixes:
                    matched = prefix.fullmatch(sentence)
                    if matched and alias in parse_alias_list_claim(matched.group('claim')):
                        declared_sentence = sentence + terminal
                        break
                if declared_sentence:
                    break
                reverse = re.fullmatch(
                    rf'''\s*['"“”‘’]?{re.escape(alias)}['"“”‘’]?\s*'''
                    rf'''(?:은|는|이|가)\s*{title_value}\s*(?:의)?\s*{marker}\s*'''
                    rf'''(?:이다|임|(?:이라고|라고)\s*한다|(?:이라|라|로)\s*불린다)\s*''',
                    sentence,
                )
                if reverse:
                    declared_sentence = sentence + terminal
                    break
            if not declared_sentence:
                continue
            declarations.setdefault(alias, {})[source_key] = {
                'title': source_title,
                'alias_surface': alias,
                'support_surface': support_surface,
                'source_url': row['source_url'],
                'source_title': source_title,
                'source_row_sha256': row['source_row_sha256'],
                'source_text_sha256': hashlib.sha256(body.encode('utf-8')).hexdigest(),
                'assertion_sentence_sha256': hashlib.sha256(declared_sentence.encode('utf-8')).hexdigest(),
            }

    for alias in aliases:
        by_title = declarations.get(alias) or {}
        if set(by_title) == {target}:
            return by_title[target]
    return None


def source_bound_review_section_alias_assertion(
    title: str,
    alias_terms: list[str],
    rows: list[dict[str, Any]],
    *,
    source_text: str,
    support_surface: str = '',
) -> dict[str, str | int] | None:
    """Candidate-only alias evidence from one numbered section of a DC review.

    A paragraph in the exact work section must use the alias as its subject.
    Lists, comparisons, and mentions outside that section remain ambiguous.
    This parser is deliberately separate from the Verifier's wiki assertion.
    """
    import hashlib
    from urllib.parse import parse_qs, urlsplit

    if (
        not isinstance(title, str) or not isinstance(alias_terms, list)
        or not isinstance(rows, list) or not isinstance(source_text, str)
        or not isinstance(support_surface, str)
    ):
        return None
    target = _compact_source_title(title)
    if not 4 <= len(target) <= 80:
        return None

    word = r'0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ_'
    aliases = [
        alias for alias in dict.fromkeys(
            value.strip() for value in alias_terms if isinstance(value, str)
        )
        if re.fullmatch(r'[0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ_]{2,32}', alias)
        and re.search(rf'(?<![{word}]){re.escape(alias)}(?![{word}])', source_text)
    ]
    if not aliases:
        return None

    heading_re = re.compile(r'^\s*(?P<number>[1-9][0-9]?)\.\s+(?P<name>[^\r\n]{4,100}?)\s*$')
    unsafe = re.compile(
        r'아니|않|잘못|오해|착각|거짓|오류|별개|무관|다른\s*(?:작품|소설)|'
        r'만약|가정|이라면|라면|다면|으면|일\s*경우|인가|일까|'
        r'보다|추천|비교|순위|랭킹'
    )
    media_identity = re.compile(
        r'(?:이|본|해당)?\s*(?:작품|제목)?(?:은|는|이|가)?\s*'
        r'[^.!?\n]{0,32}?(?:웹툰|만화|애니메이션|게임|영화|드라마)\s*'
        r'(?:작품)?(?:이다|임|라고\s*한다)'
    )
    for row in rows[:120]:
        if not isinstance(row, dict):
            continue
        url, page_title, body = row.get('url'), row.get('title'), row.get('content')
        if not all(isinstance(value, str) for value in (url, page_title, body)):
            continue
        if not re.search(r'리뷰|감상', page_title) or not body or len(body) > 30000:
            continue
        try:
            parsed = urlsplit(url)
            query = parse_qs(parsed.query, strict_parsing=True)
            if (
                parsed.scheme != 'https' or parsed.hostname != 'gall.dcinside.com'
                or parsed.username or parsed.password or parsed.port not in (None, 443)
                or parsed.path != '/mgallery/board/view/'
                or not re.fullmatch(r'[a-z][a-z0-9_]{1,31}', query.get('id', [''])[0])
                or not re.fullmatch(r'[0-9]{1,12}', query.get('no', [''])[0])
                or set(query) != {'id', 'no'}
                or any(len(values) != 1 for values in query.values())
                or parsed.fragment
            ):
                continue
        except ValueError:
            continue

        lines = []
        offset = 0
        for raw_line in body.splitlines(keepends=True):
            text = raw_line.rstrip('\r\n')
            lines.append((text, offset, offset + len(text)))
            offset += len(raw_line)
        headings = []
        for index, (line, start, _) in enumerate(lines):
            match = heading_re.fullmatch(line)
            if match:
                name = re.sub(r'\s*\([^()]{1,40}\)\s*$', '', match.group('name')).strip()
                headings.append((index, start, name, int(match.group('number'))))
        numbers = [number for _, _, _, number in headings]
        if len(headings) < 2 or numbers != list(range(1, len(headings) + 1)):
            continue
        targets = [i for i, (_, _, name, _) in enumerate(headings) if name == title]
        if len(targets) != 1:
            continue
        index = targets[0]
        line_start = headings[index][0]
        line_end = headings[index + 1][0] if index + 1 < len(headings) else len(lines)
        section = lines[line_start + 1:line_end]
        section_text = '\n'.join(line for line, _, _ in section)
        if (
            any(re.match(r'^\s*(?:#{1,6}\s+|\+\s+)', line) for line, _, _ in section)
            or not re.search(r'(?:웹\s*)?소설|연재|회차|작가|저자|\(문(?:/|\))',
                          page_title + '\n' + section_text)
            or media_identity.search(section_text)
        ):
            continue
        if support_surface:
            author = re.escape(support_surface)
            if not re.search(
                rf'(?<![{word}]){author}\s*(?:작가|저자)'
                rf'|(?:작가|저자)(?:는|은|:)?\s*{author}(?![{word}])',
                section_text,
            ):
                continue

        for alias in aliases:
            alias_re = re.compile(
                rf'(?<![{word}]){re.escape(alias)}'
                rf'(?=(?:은|는|이|가|도|을|를|에서|의)?(?![{word}]))'
            )
            occurrences = [
                (i, line, start, match)
                for i, (line, start, _) in enumerate(lines)
                for match in alias_re.finditer(line)
            ]
            if not occurrences or any(not line_start < i < line_end for i, _, _, _ in occurrences):
                continue
            # One ambiguous use makes the whole row insufficient evidence.
            accepted = []
            for i, line, start, match in occurrences:
                clause = line.strip()
                if (
                    unsafe.search(line) or '?' in line or '？' in line
                    or any(name in line for heading_i, _, name, _ in headings if heading_i != line_start)
                    or re.search(r'[<>≷=]|\d+\s*/\s*\d+|\b\d+\s*위\b', line)
                    or re.match(r'^\s*(?:[+\-*•]|\d+[.)])\s+', line)
                    or re.search(r'(?:웹툰|만화|애니메이션|게임|영화|드라마)', line)
                    or len(clause) < len(alias) + 12
                    or not re.match(
                        rf'^\s*{re.escape(alias)}(?:은|는|이|가|도|을|를|에서|의)\s+',
                        line,
                    )
                    or not re.search(r'(?:다|음|요|죠|됨|했다|한다)[.!。]?\s*$', clause)
                ):
                    accepted = []
                    break
                accepted.append((line, start, match))
            if not accepted:
                continue
            line, start, match = accepted[0]
            return {
                'title': title,
                'alias_surface': alias,
                'support_surface': support_surface,
                'source_url': url,
                'source_title': page_title,
                'source_row_sha256': source_bound_search_row_fingerprint(row),
                'source_text_sha256': hashlib.sha256(body.encode('utf-8')).hexdigest(),
                'assertion_sentence_sha256': hashlib.sha256(line.encode('utf-8')).hexdigest(),
                'section_span_start': headings[index][1],
                'section_span_end': lines[line_end][1] if line_end < len(lines) else len(body),
                'assertion_span_start': start,
                'assertion_span_end': start + len(line),
                'alias_span_start': start + match.start(),
                'alias_span_end': start + match.end(),
            }
    return None


def source_anticipation_probe(
    post: dict[str, Any], comments: list[Any], discourse: dict[str, Any]
) -> dict[str, str] | None:
    """작품 여부는 미확정으로 두고 원문 두 표면만 질의에 사용한다."""
    if not isinstance(post, dict) or not isinstance(discourse, dict):
        return None
    review = discourse.get('semantic_seed_review')
    if (not isinstance(review, dict)
        or review.get('is_specific_work_discussion') is not False
        or discourse.get('primary_domain') != 'novel_literature'
        or discourse.get('domain_confidence') not in {'high', 'medium'}):
        return None
    direct_title = authored_anticipation_title_span(post)
    if not direct_title and not anticipation_title_surface_present(post):
        return None
    title = direct_title or str(post.get('title') or '')
    body = [
        _INLINE_QUOTE_RE.sub(' ', str(span.get('text') or ''))
        for span in author_text_spans(post)
        if span.get('source') == 'author_body'
    ]
    comment_texts = [x for x in comments if isinstance(x, str)][:16] if isinstance(comments, list) else []
    source_text = ' '.join([title, *body, *comment_texts])
    if re.search(r'(?:만화|웹툰|애니메이션|축구|야구|농구|선수|날씨|주식|코인|추천\s*해|소설\s*아니|작품\s*아니)', source_text):
        return None
    generic = {'친구','사람','작가','작가님','작품','소설','웹소설','연재','복귀','기우제','주인공','캐릭터','날씨','이제','이제는','이번','우리','여러분','가자','화이팅'}
    word = r'0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ_'
    def visible(text: str, token: str) -> bool:
        return bool(re.search(rf'(?<![{word}]){re.escape(token)}(?:은|는|이|가|을|를|의|도|만)?(?![{word}])', text))
    terms = discourse.get('semantic_seed_review_context_terms')
    if not isinstance(terms, list):
        return None
    aliases = list(dict.fromkeys(
        term.strip() for term in terms if isinstance(term, str)
        and re.fullmatch(r'[가-힣]{2,8}', term.strip())
        and term.strip() not in generic and visible(title, term.strip())
    ))
    if len(aliases) != 1:
        return None
    alias = aliases[0]
    names = set()
    for text in body:
        for match in re.finditer(r'(?<![가-힣])(?:가자|가즈아|힘내)\s+([가-힣]{2,12})(?![가-힣])|(?<![가-힣])([가-힣]{2,12})\s+(?:화이팅|힘내)(?![가-힣])', text):
            name = match.group(1) or match.group(2)
            if name == alias or name in generic:
                continue
            if any(visible(comment, name) and re.search(r'(?:기우제|연재|복귀|기다리|기다림|존버)', comment) for comment in comment_texts):
                names.add(name)
    if len(names) != 1:
        return None
    name = next(iter(names))
    return {'alias_surface': alias, 'support_surface': name, 'query': f'{alias} {name} 웹소설'}

def source_anticipation_official_search_evidence(
    post: dict[str, Any], comments: list[Any], discourse: dict[str, Any],
    title: str, rows: list[dict[str, Any]],
) -> dict[str, str] | None:
    """원문 기다림 대상과 위키 원문의 명시 약칭/작가 관계만 검색 허용에 쓴다."""
    import hashlib
    if not isinstance(discourse, dict) or not isinstance(title, str) or not isinstance(rows, list):
        return None
    target = _compact_source_title(title)
    if not 6 <= len(target) <= 80:
        return None
    terms = []
    for key in ('title_novel_terms', 'semantic_seed_review_context_terms'):
        values = discourse.get(key)
        if isinstance(values, list):
            terms.extend(value for value in values if isinstance(value, str))
    probe = source_anticipation_probe(
        post, comments, dict(discourse, semantic_seed_review_context_terms=terms)
    )
    if not probe:
        return None
    alias, author = probe['alias_surface'], probe['support_surface']
    word = r'0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ_'
    alias_re = re.compile(rf'(?<![{word}]){re.escape(alias)}(?:으로|라고|이라|이다|은|는|이|가|을|를|의|도|만|다)?(?![{word}])')
    author_re = re.compile(
        rf'''(?<![{word}]){re.escape(author)}['"“”‘’]?\s*(?:작가|저자)(?:의|가|는)?(?![{word}])'''
        rf'''|(?:작가|저자)(?:는|은|:)?\s*['"“”‘’]?{re.escape(author)}['"“”‘’]?(?:이다|다)?(?![{word}])'''
    )
    negative = re.compile(r'아니|않|잘못|오해|착각|다른\s*(?:작품|소설)|별개\s*(?:작품|소설)')
    evidence_by_title: dict[str, dict[str, str]] = {}
    for row in _source_bound_wiki_rows(rows):
        source_key = row['source_key']
        source_title = row['source_title']
        url = row['source_url']
        body = row['body']
        sentences = re.split(r'[.!?。\n]', body)
        author_sentences = [sentence for sentence in sentences if author_re.search(sentence)]
        if not author_sentences or any(negative.search(sentence) for sentence in author_sentences):
            continue
        alias_sentences = []
        for sentence in sentences:
            marker = re.search(r'약칭|줄임말|줄여서|약자로', sentence)
            if marker and alias_re.search(sentence[marker.start():marker.start() + 160]):
                alias_sentences.append(sentence)
        if not alias_sentences or any(negative.search(sentence) for sentence in alias_sentences):
            continue
        evidence_by_title.setdefault(source_key, {
            'title': source_title, 'alias_surface': alias, 'support_surface': author,
            'source_url': url, 'source_title': source_title,
            'source_text_sha256': hashlib.sha256(body.encode('utf-8')).hexdigest(),
        })
    if set(evidence_by_title) != {target}:
        return None
    return evidence_by_title[target]


def source_anticipation_coverage_query(
    post: dict[str, Any], comments: list[Any], discourse: dict[str, Any],
    requests: list[dict[str, Any]],
) -> dict[str, str] | None:
    """원문 자격을 갖춘 단독 제안 두 개에 결합 질의가 빠진 경우만 반환한다."""
    if not isinstance(discourse, dict) or not isinstance(requests, list) or not requests:
        return None
    terms = []
    for key in ('title_novel_terms', 'semantic_seed_review_context_terms'):
        values = discourse.get(key)
        if isinstance(values, list):
            terms.extend(value for value in values if isinstance(value, str))
    probe = source_anticipation_probe(
        post, comments, dict(discourse, semantic_seed_review_context_terms=terms)
    )
    if not probe:
        return None
    alias, support = probe['alias_surface'], probe['support_surface']
    expected = {frozenset((alias, '웹소설')), frozenset((support, '웹소설'))}
    suggestions = discourse.get('search_suggestions')
    if not isinstance(suggestions, list) or not suggestions:
        return None
    proposed = set()
    for suggestion in suggestions:
        if not isinstance(suggestion, dict) or not isinstance(suggestion.get('query'), str):
            return None
        tokens = suggestion['query'].split()
        if len(tokens) != 2 or frozenset(tokens) not in expected:
            return None
        proposed.add(frozenset(tokens))
    if proposed != expected:
        return None
    requested = set()
    for request in requests:
        if not isinstance(request, dict) or not isinstance(request.get('query'), str):
            continue
        tokens = request['query'].split()
        if alias in tokens and support in tokens:
            return None
        if len(tokens) == 2:
            requested.add(frozenset(tokens))
    return probe if expected.issubset(requested) else None


def source_anticipation_priority_query(
    post: dict[str, Any], comments: list[Any], discourse: dict[str, Any],
    requests: list[dict[str, Any]],
) -> dict[str, str] | None:
    """Choose an existing source-bound suggestion; do not create a request."""
    if not isinstance(discourse, dict) or not isinstance(requests, list):
        return None
    terms = []
    for key in ('title_novel_terms', 'semantic_seed_review_context_terms'):
        values = discourse.get(key)
        if isinstance(values, list):
            terms.extend(value for value in values if isinstance(value, str))
    # Reuse the original-text eligibility rules without changing expert output.
    eligibility_input = dict(discourse, semantic_seed_review_context_terms=terms)
    probe = source_anticipation_probe(post, comments, eligibility_input)
    if not probe:
        return None
    expected_tokens = {probe['alias_surface'], probe['support_surface'], '웹소설'}

    def key(query: Any) -> str:
        return ' '.join(query.split()) if isinstance(query, str) else ''

    suggestions = discourse.get('search_suggestions')
    if not isinstance(suggestions, list):
        return None
    proposed = {key(item.get('query')) for item in suggestions if isinstance(item, dict)}
    matches = []
    for request in requests:
        if not isinstance(request, dict):
            continue
        query = key(request.get('query'))
        purpose = str(request.get('purpose') or '').split(':', 1)[0].strip()
        if (purpose != 'discourse_suggestion' or query not in proposed
            or len(query.split()) != 3 or set(query.split()) != expected_tokens):
            continue
        if query not in matches:
            matches.append(query)
    if len(matches) != 1:
        return None
    return {**probe, 'query': matches[0]}
