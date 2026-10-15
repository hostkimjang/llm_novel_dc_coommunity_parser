"""선별 전 원래 인용 경계와 학습 표면의 분리. 기존156사례와 기대값은 보존한다."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

_path = Path(__file__).with_name('test_source_alias_memory_scope.py')
_spec = importlib.util.spec_from_file_location('_alias_scope_v3_boundary_support', _path)
_support = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _support
_spec.loader.exec_module(_support)
facts, sut, external_case = _support.facts, _support.sut, _support.external_case
canon, sha = _support.canon, _support.sha
produce_external, canonical_result, committed = _support.produce_external, _support.canonical_result, _support.committed
consume = _support._consume


def _case_with_blocks(original, blocks):
    case = deepcopy(original)
    case['post']['title'] = ''
    case['post']['content_blocks'] = deepcopy(blocks)
    return case


def _closed_prefix_case(original):
    return _case_with_blocks(original, [{'type': 'quote', 'text': '친구:\n"PRIVATE_QUOTE_OPEN'},
        {'type': 'quote', 'text': 'PRIVATE_QUOTE_CLOSE"'},
        {'type': 'text', 'text': original['alias'] + ' 40화 재미있네'}])


def test_independent_f3_exact_quote_block_counterexample_through_real_main_wal(sut, tmp_path):
    folder = Path(__file__).parent / 'fixtures/alias_memory_boundaries_v4'
    path = folder / 'review_counterexample.json'
    raw = path.read_bytes()
    assert sha(raw) == json.loads((folder / 'manifest.json').read_bytes())['files_sha256'][path.name]
    case = json.loads(raw)['case']
    before = canon(case)
    typed = sut.models.PostInput(**case['post'], comments=deepcopy(case['comments']))
    assert [block.type for block in typed.content_blocks] == ['quote', 'text', 'quote']
    envelope = produce_external(sut, case)
    assert envelope['decoded_terms'] == []
    memory, _ = consume(sut, case, envelope, tmp_path)
    assert memory.resolved_abbreviations == memory.pending_abbreviations == {}
    assert canon(case) == before and path.read_bytes() == raw


@pytest.mark.parametrize('variant,allowed', [
    ('quote_wrap', False), ('blockquote_wrap', False), ('corner_quote_wrap', False), ('quote_lexical_only', False),
    ('quote_label_wrap', False), ('ocr_cannot_close', False), ('generated_cannot_restore_owner', False),
    ('after_closed_quote', True), ('after_closed_quote_author_label', True), ('self_contained_quote', True),
    ('independent_image', True), ('independent_ocr', True), ('independent_generated_type', True),
    ('independent_vlm_prefix', True), ('plain_quote_block', True), ('author_before_open_quote', True),
])
def test_lexical_admission_and_original_quote_scope_remain_separate(sut, external_case, tmp_path, variant, allowed):
    alias = external_case['alias']
    authored = {'type': 'text', 'text': alias + ' 40화 재미있네'}
    opening = {'type': 'quote', 'text': '친구:\n"PRIVATE_QUOTE_OPEN'}
    closing = {'type': 'quote', 'text': 'PRIVATE_QUOTE_CLOSE"'}
    blocks = [opening, authored, closing]
    if variant == 'blockquote_wrap': opening['type'] = closing['type'] = 'blockquote'
    elif variant == 'corner_quote_wrap': opening['text'] = '『인용 시작'; closing['text'] = '인용 끝』'
    elif variant == 'quote_lexical_only': blocks = [{'type': 'quote', 'text': alias + ' 40화 재미있네'}]
    elif variant == 'quote_label_wrap': opening['text'] = '친구:'; closing['text'] = '인용 끝'
    elif variant == 'ocr_cannot_close': closing['type'] = 'ocr'
    elif variant == 'generated_cannot_restore_owner':
        blocks = [{'type': 'quote', 'text': '친구:'}, {'type': 'generated', 'text': '인용 끝\n작성자:'}, authored]
    elif variant == 'after_closed_quote': blocks = [opening, closing, authored]
    elif variant == 'after_closed_quote_author_label': blocks = [opening, closing, {'type': 'text', 'text': '작성자:'}, authored]
    elif variant == 'self_contained_quote': blocks = [{'type': 'quote', 'text': '친구:\n"닫힌 인용"'}, authored]
    elif variant == 'independent_image': blocks = [{'type': 'image', 'url': 'https://example.invalid/image.png', 'text': '친구:\n"'}, authored]
    elif variant == 'independent_ocr': blocks = [{'type': 'ocr', 'text': '친구:\n"'}, authored]
    elif variant == 'independent_generated_type': blocks = [{'type': 'generated', 'text': '친구:\n"'}, authored]
    elif variant == 'independent_vlm_prefix': blocks = [{'type': 'text', 'text': '[VLM]\n친구:\n"'}, authored]
    elif variant == 'plain_quote_block': blocks = [{'type': 'quote', 'text': '타인의 짧은 인용문이다.'}, authored]
    elif variant == 'author_before_open_quote': blocks = [authored, opening]
    case = _case_with_blocks(external_case, blocks)
    before = canon(case)
    envelope = produce_external(sut, case)
    assert bool(envelope['decoded_terms']) is allowed
    assert 'PRIVATE_QUOTE' not in canon(envelope).decode('utf8')
    memory, stored = consume(sut, case, envelope, tmp_path)
    assert memory.get_abbreviation(alias) == (case['title'] if allowed else None)
    assert memory.pending_abbreviations == {}
    assert stored['content_blocks'] == case['post']['content_blocks']
    assert canon(case) == before


def _change_boundary(post, mutation):
    block = post['content_blocks'][0]
    if mutation == 'text': block['text'] += ' 경계의 원문 변경'
    elif mutation == 'kind': block['type'] = 'blockquote'
    elif mutation == 'erased': post['content_blocks'][0] = {'type': 'image', 'url': 'https://example.invalid/placeholder.png'}
    elif mutation == 'speaker': block['speaker'] = '다른 화자'
    elif mutation == 'author_denied': block['is_post_author'] = False
    elif mutation == 'order': post['content_blocks'][:2] = list(reversed(post['content_blocks'][:2]))


@pytest.mark.parametrize('mutation', ['text', 'kind', 'erased', 'speaker', 'author_denied', 'order'])
def test_capture_boundary_changes_are_rejected_before_producer_qualification(sut, external_case, mutation):
    case = _closed_prefix_case(external_case)
    typed = sut.models.PostInput(**case['post'], comments=deepcopy(case['comments']))
    ctx = sut.orchestrator.ConversationContext(post_id=typed.post_id, post_data=deepcopy(case['post']), comments=deepcopy(case['comments']))
    ctx._batch_alias_original_source = sut.alias_learning.capture_alias_source(typed)
    ctx.search_results = deepcopy(case['search_rows'])
    ctx.expert_outputs = {'decoder': deepcopy(case['decoder']), 'verifier': {'verification_result': deepcopy(case['verification'])}}
    pipe = object.__new__(sut.agentic_pipeline.AgenticPipeline)
    good = pipe._build_batch_context_learning_envelope(ctx)
    assert good['decoded_terms']
    before_source = canon(case)
    before_experts = canon(ctx.expert_outputs)
    lexical_before = sut.alias_learning._fields(ctx._batch_alias_original_source)
    _change_boundary(ctx._batch_alias_original_source, mutation)
    assert sut.alias_learning._fields(ctx._batch_alias_original_source) == lexical_before
    assert sut.alias_learning.alias_source_from_context(ctx) == {}
    assert pipe._build_batch_context_learning_envelope(ctx)['decoded_terms'] == []
    assert canon(case) == before_source and canon(ctx.expert_outputs) == before_experts


@pytest.mark.parametrize('mutation', ['text', 'kind', 'erased', 'speaker', 'author_denied', 'order'])
def test_saved_proof_rechecks_boundaries_even_when_lexical_fields_do_not_change(sut, external_case, tmp_path, mutation):
    case = _closed_prefix_case(external_case)
    envelope = produce_external(sut, case)
    assert envelope['decoded_terms']
    original = canonical_result(sut, case, envelope)
    stored, receipt, _, path, wal = committed(sut, tmp_path, case, original)
    altered = deepcopy(stored)
    lexical_before = sut.alias_learning._fields(altered)
    _change_boundary(altered, mutation)
    assert sut.alias_learning._fields(altered) == lexical_before
    terms = altered['analysis_result']['batch_context_learning_envelope']['decoded_terms']
    memory = sut.batch_context.BatchContextMemory(enabled=True)
    memory.learn_from_result(altered, decoded_terms=terms)
    assert memory.resolved_abbreviations == memory.pending_abbreviations == {}
    with pytest.raises(sut.publication_commit.PublicationCommitError):
        sut.publication_commit.validate_publication_result_commit(altered, receipt)
    assert path.read_bytes() == wal and canon(stored) == canon(original)


@pytest.mark.parametrize('flag', ['from_ocr', 'is_generated', 'model_generated', 'provenance'])
def test_mapping_source_generated_metadata_has_no_boundary_authority(sut, external_case, flag):
    # Mapping 입력 helper의 대조다. PostInput이 extra 필드를 보존한다고 주장하지 않는다.
    case = deepcopy(external_case)
    block = {'type': 'quote', 'text': '친구:\n"', flag: 'generated_summary' if flag == 'provenance' else True}
    case['post']['title'] = ''
    case['post']['content_blocks'] = [block, {'type': 'text', 'text': case['alias'] + ' 40화 재미있네'}]
    captured = sut.alias_learning.capture_alias_source(case['post'])
    terms = sut.alias_learning.build_alias_learning_terms(captured, case['decoder'], case['verification'],
        registries=[], search_rows=case['search_rows'])
    assert len(terms) == 1
    assert sut.alias_learning.eligible_alias_confidence(case['post'], terms[0], case['title'], registries=[]) == 3


@pytest.mark.parametrize('route', ['external', 'curated', 'author'])
def test_original_quote_boundaries_apply_to_every_alias_qualification_route(sut, external_case, route):
    case = deepcopy(external_case)
    phrase = case['title'] + '의 약칭은 ' + case['alias'] + '이다.' if route == 'author' else case['alias'] + ' 40화 재미있네'
    case['post']['title'] = ''
    case['post']['content_blocks'] = [{'type': 'quote', 'text': '친구:\n"인용 시작'},
        {'type': 'text', 'text': phrase}, {'type': 'quote', 'text': '인용 끝"'}]
    terms = sut.alias_learning.build_alias_learning_terms(case['post'], case['decoder'], case['verification'],
        registries=[{case['alias']: case['title']}] if route == 'curated' else [],
        search_rows=case['search_rows'] if route == 'external' else [])
    assert terms == []
