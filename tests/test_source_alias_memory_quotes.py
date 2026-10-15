"""통합 실패의 명명 따옴표와 HOLD typed 입력 대조. ROOT 실행 전용."""
from copy import deepcopy
from importlib import import_module
import importlib.util
from pathlib import Path
import sys

import pytest

_path = Path(__file__).with_name('test_source_alias_memory_external.py')
_spec = importlib.util.spec_from_file_location('_alias_external_v5_quote_support', _path)
_base = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _base
_spec.loader.exec_module(_base)
facts, sut, external_case = _base.facts, _base.sut, _base.external_case
canon = _base.canon


@pytest.mark.parametrize('opener,closer', [("'", "'"), ('"', '"'), ('‘', '’'), ('“', '”')])
@pytest.mark.parametrize('prefix', ['', "John's note and Jane's note describe the book.\n", "Don't confuse O'Neill's notes.\n"])
def test_quoted_name_keeps_existing_assertion_and_reaches_wal_main(sut, external_case, tmp_path, opener, closer, prefix):
    case = deepcopy(external_case)
    row = case['search_rows'][0]
    row['content'] = '한국의 판타지 웹소설이다.\n' + prefix + '약칭은 ' + opener + case['alias'] + closer + '이다.'
    probe = import_module('llm_batch.grounding.anticipation_search_probe')
    assertion = probe.source_bound_alias_assertion(case['title'], [case['alias']], case['search_rows'], source_text=case['post']['title'])
    assert assertion is not None  # 원래 명명 판독기가 관계를 만든다.
    assert sut.alias_learning._owned_external_assertion(row, assertion, case['alias'], case['title']) is True
    envelope = _base.produce_external(sut, case)
    assert len(envelope['decoded_terms']) == 1
    assert envelope['decoded_terms'][0]['learning_evidence']['external_evidence']['assertion'] == assertion
    result = _base.canonical_result(sut, case, envelope)
    stored, receipt, created, path, wal = _base.committed(sut, tmp_path, case, result)
    memory = sut.batch_context.BatchContextMemory(enabled=True)
    assert sut.expert_main._learn_batch_context_from_canonical_publication(memory, stored, receipt, created=created)
    assert memory.get_abbreviation(case['alias']) == case['title']
    assert path.read_bytes() == wal


@pytest.mark.parametrize('variant', ['outer_speech', 'speaker_label', 'unclosed_name', 'source_speech', 'escaped_closing'])
def test_name_quote_fix_does_not_erase_speech_or_unclosed_quote(sut, external_case, variant):
    case = deepcopy(external_case)
    claim = "약칭은 '" + case['alias'] + "'이다."
    intro = '한국의 판타지 웹소설이다.\n'
    if variant == 'outer_speech': case['search_rows'][0]['content'] = intro + '"인용 시작\n' + claim + '\n인용 끝"'
    elif variant == 'speaker_label': case['search_rows'][0]['content'] = intro + '친구:\n' + claim
    elif variant == 'unclosed_name': case['search_rows'][0]['content'] = intro + "약칭은 '" + case['alias'] + '이다.'
    elif variant == 'escaped_closing': case['search_rows'][0]['content'] = intro + '"인용 시작\n' + claim + '\n끝\\"'
    else:
        case['post']['title'] = ''
        case['post']['content_blocks'] = [{'type': 'text', 'text': "친구:\n'" + case['alias'] + " 40화 재미있네'"}]
    assert _base.produce_external(sut, case)['decoded_terms'] == []


def test_exact_hold_adapter_is_narrow_and_preserves_input_and_other_contract_fields():
    saved = {'novel_identity': {'official_title': None, 'heretic_url': None}, 'title_resolution_allowed': False,
             'promotion_decision': {'publish_allowed': False}, 'is_relevant': False}
    before = canon(saved)
    converted = _base.typed_exact_hold_identity_input(saved)
    assert converted['novel_identity'] is None and canon(saved) == before
    assert {k: v for k, v in converted.items() if k != 'novel_identity'} == {k: v for k, v in saved.items() if k != 'novel_identity'}
    for pair in [None, {}, {'official_title': None}, {'heretic_url': None},
                 {'official_title': None, 'heretic_url': None, 'confidence': 'Low'},
                 {'official_title': '', 'heretic_url': None}, {'official_title': False, 'heretic_url': None},
                 {'official_title': None, 'heretic_url': 'https://example.invalid/1'}]:
        changed = deepcopy(saved); changed['novel_identity'] = pair
        with pytest.raises(ValueError, match='EXACT_WRITER_NULL_PAIR_REQUIRED'):
            _base.typed_exact_hold_identity_input(changed)
    for value in [True, 0, None, 'false']:
        changed = deepcopy(saved); changed['title_resolution_allowed'] = value
        with pytest.raises(ValueError, match='EXACT_WRITER_NULL_PAIR_REQUIRED'):
            _base.typed_exact_hold_identity_input(changed)
    missing = deepcopy(saved); missing.pop('novel_identity')
    with pytest.raises(ValueError, match='EXACT_WRITER_NULL_PAIR_REQUIRED'):
        _base.typed_exact_hold_identity_input(missing)


@pytest.mark.parametrize('alias,title,stat', [('아카데미의 피해자', '아카데미의 피해자', 'abbreviation_exact_title_skipped'),
    ('시달소', '시간을 달리는 소녀', 'abbreviation_seed_quarantined')])
def test_unqualified_rejection_observation_never_calls_registration(sut, alias, title, stat):
    memory = sut.batch_context.BatchContextMemory(enabled=True)
    attempts = []
    def forbidden(*args, **kwargs):
        attempts.append((args, kwargs))
        raise AssertionError('REJECTED_OBSERVATION_MUST_NOT_REGISTER')
    memory.register_abbreviation = forbidden
    result = {'identity': {'is_relevant': True, 'novel_identity': {'official_title': title, 'confidence': 'Max'},
        'slang_insight': {'detected_term': alias, 'canonical_work_alias': alias, 'decoded_term': title, 'alias_scope': 'pure_work_alias'}}}
    before = canon(result)
    memory.learn_from_result(result, decoded_terms=[{'original': alias, 'best_match': {'title': title}}])
    assert memory.stats[stat] == 1 and attempts == []
    assert memory.resolved_abbreviations == memory.pending_abbreviations == {}
    assert canon(result) == before
