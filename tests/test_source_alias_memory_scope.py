"""v2 독립 F1/F2의 후손 기능 대조. ROOT만 실행하며 기존107사례는 그대로다."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
from urllib.parse import quote

import pytest

_path = Path(__file__).with_name('test_source_alias_memory_external.py')
_spec = importlib.util.spec_from_file_location('_alias_external_v2_scope_support', _path)
_support = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _support
_spec.loader.exec_module(_support)
facts, sut, external_case = _support.facts, _support.sut, _support.external_case
canon, sha = _support.canon, _support.sha
produce_external, canonical_result, committed = _support.produce_external, _support.canonical_result, _support.committed


def _supplement(case, text, field='content'):
    first = case['search_rows'][0]
    return {'title': first['title'], 'url': first['url'], field: text}


def _consume(sut, case, envelope, tmp_path):
    result = canonical_result(sut, case, envelope)
    before = canon(result)
    stored, receipt, created, path, raw = committed(sut, tmp_path, case, result)
    memory = sut.batch_context.BatchContextMemory(enabled=True)
    sut.expert_main._learn_batch_context_from_canonical_publication(memory, stored, receipt, created=created)
    assert canon(result) == before and path.read_bytes() == raw
    assert receipt.outcome == 'PUBLISH'
    return memory, stored


@pytest.mark.parametrize('case_index', [0, 1])
def test_independent_review_exact_counterexamples_reach_typed_wal_main(sut, tmp_path, case_index):
    path = Path(__file__).parent / 'fixtures/alias_memory_scope_v3/review_counterexamples.json'
    raw = path.read_bytes()
    expected = json.loads((path.parent / 'manifest.json').read_bytes())['files_sha256'][path.name]
    assert sha(raw) == expected
    case = json.loads(raw)['cases'][case_index]['case']
    before = canon(case)
    envelope = produce_external(sut, case)
    assert envelope['decoded_terms'] == []
    memory, _ = _consume(sut, case, envelope, tmp_path)
    assert memory.resolved_abbreviations == memory.pending_abbreviations == {}
    assert canon(case) == before and path.read_bytes() == raw


@pytest.mark.parametrize('variant', ['content', 'snippet', 'description', 'fragment', 'www', 'default_port', 'first', 'duplicate_positive'])
def test_same_document_counterclaim_needs_no_repeated_novel_introduction(sut, external_case, variant):
    case = deepcopy(external_case)
    row = _supplement(case, case['alias'] + '은 이 작품의 약칭이 아니다.', variant if variant in {'snippet', 'description'} else 'content')
    if variant == 'fragment': row['url'] += '#반박'
    elif variant == 'www': row['url'] = row['url'].replace('namu.wiki/', 'www.namu.wiki/')
    elif variant == 'default_port': row['url'] = row['url'].replace('namu.wiki/', 'namu.wiki:443/')
    if variant == 'first': case['search_rows'].insert(0, row)
    else: case['search_rows'].append(row)
    if variant == 'duplicate_positive': case['search_rows'].append(deepcopy(case['search_rows'][0]))
    before = canon(case)
    assert produce_external(sut, case)['decoded_terms'] == []
    assert canon(case) == before


@pytest.mark.parametrize('variant', ['friend', 'blank_line', 'intervening_line', 'comment', 'named_role', 'reported_label',
    'content_snippet', 'snippet_description', 'quote_across_fields', 'quoted_own_label', 'body_own_label_in_quote', 'reopened_speech',
    'named_speaker', 'unknown_heading_ambiguous'])
def test_document_speaker_and_quote_scope_crosses_lines_and_fields(sut, external_case, variant):
    case = deepcopy(external_case)
    row = case['search_rows'][0]
    intro, claim = '한국의 판타지 웹소설이다.\n', '약칭은 ' + case['alias'] + '이다.'
    prefix = {'friend': '친구:\n', 'blank_line': '친구:\n\n', 'intervening_line': '친구:\n이어서 설명하겠다.\n',
        'comment': '댓글:\n', 'named_role': '독자 A:\n', 'reported_label': '동행의 말:\n',
        'named_speaker': '여행자:\n', 'unknown_heading_ambiguous': '중간 표제:\n',
        'quoted_own_label': '친구:\n"작성자:"\n', 'body_own_label_in_quote': '친구:\n"작성자:\n',
        'reopened_speech': '친구:\n인용 끝\n작성자:\n친구:\n'}.get(variant, '친구:\n')
    row['content'] = intro + prefix + claim
    if variant == 'content_snippet': row['content'] = intro + '친구:'; row['snippet'] = claim
    elif variant == 'snippet_description': row['content'] = intro; row['snippet'] = '친구:'; row['description'] = claim
    elif variant == 'quote_across_fields':
        row['content'] = intro + '"인용 시작'; row['snippet'] = claim; row['description'] = '"'
    elif variant == 'body_own_label_in_quote': row['content'] += '"'
    assert produce_external(sut, case)['decoded_terms'] == []


@pytest.mark.parametrize('variant', ['neutral_same_document', 'duplicate_same_document', 'unrelated_counterclaim',
    'bound_other_document_counterclaim', 'author_return', 'explicit_quote_end', 'alias_heading', 'name_quotes', 'overview_heading', 'work_info_heading'])
def test_complete_witness_and_independent_author_positive_survive_wal_readback(sut, external_case, tmp_path, variant):
    case = deepcopy(external_case)
    row = case['search_rows'][0]
    intro, claim = '한국의 판타지 웹소설이다.\n', '약칭은 ' + case['alias'] + '이다.'
    if variant == 'neutral_same_document': case['search_rows'].append(_supplement(case, '연재 주기는 주간이다.'))
    elif variant == 'duplicate_same_document': case['search_rows'].append(deepcopy(row))
    elif variant in {'unrelated_counterclaim', 'bound_other_document_counterclaim'}:
        other = '별개의 먼 우주 항해'
        case['search_rows'].append({'title': other + ' - 나무위키', 'url': 'https://namu.wiki/w/' + quote(other, safe=''),
            'content': (intro if variant == 'bound_other_document_counterclaim' else '') + case['alias'] + '은 이 작품의 약칭이 아니다.'})
    elif variant == 'author_return': row['content'] = intro + '친구:\n잘 모르겠다.\n\n작성자:\n' + claim
    elif variant == 'explicit_quote_end': row['content'] = intro + '친구:\n잘 모르겠다.\n[인용 끝]\n' + claim
    elif variant == 'alias_heading': row['content'] = intro + '약칭:\n' + claim
    elif variant == 'overview_heading': row['content'] = intro + '개요:\n' + claim
    elif variant == 'work_info_heading': row['content'] = intro + '작품 정보:\n' + claim
    elif variant == 'name_quotes': row['content'] = intro + "약칭은 '" + case['alias'] + "'이다."
    envelope = produce_external(sut, case)
    assert len(envelope['decoded_terms']) == 1
    witness = envelope['decoded_terms'][0]['learning_evidence']['external_evidence']
    assert witness['schema_version'] == 'alias_external_assertion_witness_v2'
    assert witness['row_scope'] == 'complete_bound_document_rows_within_bounded_search_input'
    if variant == 'neutral_same_document':
        assert witness['rows'][1] == case['search_rows'][1]
        assert len(witness['rows']) == 2
    if variant == 'duplicate_same_document': assert len(witness['rows']) == 1
    memory, stored = _consume(sut, case, envelope, tmp_path)
    assert memory.get_abbreviation(case['alias']) == case['title']
    assert stored['analysis_result']['batch_context_learning_envelope'] == envelope


@pytest.mark.parametrize('variant,allowed', [('one_field', False), ('split_fields', False), ('blank_paragraph', False),
    ('quoted_own_label', False), ('author_return', True), ('quote_end', True)])
def test_original_source_speaker_scope_is_rechecked_at_producer_and_consumer(sut, external_case, tmp_path, variant, allowed):
    case = deepcopy(external_case)
    case['post']['title'] = ''
    text = case['alias'] + ' 40화 재미있네'
    bodies = ['친구:\n' + text]
    if variant == 'split_fields': bodies = ['친구:', text]
    elif variant == 'blank_paragraph': bodies = ['친구:', '', text]
    elif variant == 'quoted_own_label': bodies = ['친구:', '"작성자:"', text]
    elif variant == 'author_return': bodies = ['친구:', '잘 모르겠다.', '', '작성자:', text]
    elif variant == 'quote_end': bodies = ['친구:', '잘 모르겠다.', '[인용 끝]', text]
    case['post']['content_blocks'] = [{'type': 'text', 'text': value} for value in bodies]
    envelope = produce_external(sut, case)
    assert bool(envelope['decoded_terms']) is allowed
    memory, _ = _consume(sut, case, envelope, tmp_path)
    assert memory.get_abbreviation(case['alias']) == (case['title'] if allowed else None)
    assert memory.pending_abbreviations == {}


@pytest.mark.parametrize('variant', ['added_counterclaim', 'changed_supplement', 'old_incomplete_scope'])
def test_recomputed_witness_catalog_hash_does_not_hide_missing_or_changed_scope(sut, external_case, variant):
    case = deepcopy(external_case)
    case['search_rows'].append(_supplement(case, '연재 주기는 주간이다.'))
    envelope = produce_external(sut, case)
    assert envelope['decoded_terms']
    witness = envelope['decoded_terms'][0]['learning_evidence']['external_evidence']
    denial = case['alias'] + '은 이 작품의 약칭이 아니다.'
    if variant == 'added_counterclaim': witness['rows'].append(_supplement(case, denial))
    elif variant == 'changed_supplement': witness['rows'][1]['content'] = denial
    elif variant == 'old_incomplete_scope':
        witness['schema_version'] = 'alias_external_assertion_witness_v1'
        witness['row_scope'] = 'complete_eligible_wiki_rows_within_bounded_search_input'
    witness['rows_sha256'] = sut.alias_learning._corpus_sha(witness['rows'])
    normalized = sut.batch_context.normalize_batch_context_learning_envelope(envelope)
    memory = sut.batch_context.BatchContextMemory(enabled=True)
    memory.learn_from_result(canonical_result(sut, case, normalized), decoded_terms=normalized['decoded_terms'])
    assert memory.resolved_abbreviations == memory.pending_abbreviations == {}


@pytest.mark.parametrize('variant', ['long_supplement', 'many_supplements'])
def test_complete_same_document_input_is_not_truncated_to_fit_witness_caps(sut, external_case, variant):
    case = deepcopy(external_case)
    if variant == 'long_supplement': case['search_rows'].append(_supplement(case, '가' * 6001))
    else: case['search_rows'].extend(_supplement(case, f'연재 기록 {index}') for index in range(24))
    assert produce_external(sut, case)['decoded_terms'] == []


@pytest.mark.parametrize('route,author_return', [('curated', False), ('curated', True), ('author', False), ('author', True)])
def test_speaker_boundary_is_not_bypassed_by_curated_or_authored_relation(sut, external_case, tmp_path, route, author_return):
    case = deepcopy(external_case)
    case['post']['title'] = ''
    text = case['alias'] + ' 40화 재미있네' if route == 'curated' else case['title'] + '의 약칭은 ' + case['alias'] + '이다.'
    bodies = ['친구:', '잘 모르겠다.'] + (['작성자:'] if author_return else []) + [text]
    case['post']['content_blocks'] = [{'type': 'text', 'text': value} for value in bodies]
    # 사전은 합성 매핑이며 외부 검색 fallback은 사용하지 않는다. 실제 producer 자격 함수를 호출한다.
    terms = sut.alias_learning.build_alias_learning_terms(case['post'], case['decoder'], case['verification'],
        registries=[{case['alias']: case['title']}] if route == 'curated' else [], search_rows=[])
    assert bool(terms) is author_return
    if terms:
        assert terms[0]['learning_evidence']['relation_kind'] == ('curated_alias_relation' if route == 'curated' else 'author_alias_declaration')
    envelope = produce_external(sut, case)
    envelope['decoded_terms'] = terms
    envelope = sut.batch_context.normalize_batch_context_learning_envelope(envelope)
    # 합성 registry를 가진 소비 경계 자체의 검산을 먼저 확인한다. 전역 사전은 수정하지 않는다.
    if terms:
        assert sut.alias_learning.eligible_alias_confidence(case['post'], terms[0], case['title'],
            registries=[{case['alias']: case['title']}] if route == 'curated' else []) == 3
    if route == 'author' or not terms:
        memory, _ = _consume(sut, case, envelope, tmp_path)
        assert memory.get_abbreviation(case['alias']) == (case['title'] if author_return else None)
