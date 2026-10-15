"""새 외부 명시 관계의 회수·변조 대조. 원형54사례와 fixture는 수정하지 않는다.

데이터는 합성 외부 문서이며 실측 fetch/사람 정답이 아니다. 실제 Verifier 판독기,
producer, typed validator, 공개 계약, WAL, main, memory 함수를 ROOT가 실행한다.
"""
from copy import deepcopy
from importlib import import_module
import importlib.util
import json
from pathlib import Path
import sys
from urllib.parse import quote

import pytest

_path = Path(__file__).with_name('test_source_alias_memory_learning.py')
_spec = importlib.util.spec_from_file_location('_alias_memory_repair_v1_support', _path)
_base = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _base
_spec.loader.exec_module(_base)
facts, sut, canon, sha = _base.facts, _base.sut, _base.canon, _base.sha


@pytest.fixture(scope='module')
def external_case():
    path = Path(__file__).parent / 'fixtures/alias_memory_external_v2/positive.json'
    raw = path.read_bytes()
    assert sha(raw) == '027a3197719b93e81e2a5d5dcbcc529addc0199d1a3ee4ca9171294072b79082'
    case = json.loads(raw)
    assert case['human_gold'] is False and case['external_fetch_performed'] is False
    yield case
    assert path.read_bytes() == raw and canon(case) == canon(json.loads(raw))


def produce_external(sut, original):
    case = deepcopy(original)
    typed = sut.models.PostInput(**case['post'], comments=deepcopy(case['comments']))
    ctx = sut.orchestrator.ConversationContext(post_id=typed.post_id, post_data=deepcopy(case['post']), comments=deepcopy(case['comments']))
    ctx._batch_alias_original_source = sut.alias_learning.capture_alias_source(typed)
    ctx.search_results = deepcopy(case['search_rows'])
    ctx.expert_outputs = {'decoder': deepcopy(case['decoder']), 'verifier': {'verification_result': deepcopy(case['verification'])}}
    before = canon({'post': ctx.post_data, 'comments': ctx.comments, 'search': ctx.search_results, 'experts': ctx.expert_outputs, 'source': ctx._batch_alias_original_source})
    pipe = object.__new__(sut.agentic_pipeline.AgenticPipeline)
    envelope = pipe._build_batch_context_learning_envelope(ctx)
    serialized = sut.models.PickvelOutputItemV2(post_id=typed.post_id, identity={'is_relevant': True}, batch_context_learning_envelope=envelope).model_dump()['batch_context_learning_envelope']
    assert serialized == envelope
    assert before == canon({'post': ctx.post_data, 'comments': ctx.comments, 'search': ctx.search_results, 'experts': ctx.expert_outputs, 'source': ctx._batch_alias_original_source})
    return serialized


def typed_exact_hold_identity_input(saved):
    """시험 준비: 실제 writer의 정확한 HOLD 두-null pair만 typed None으로 변환한다."""
    if not isinstance(saved, dict) or 'novel_identity' not in saved:
        raise ValueError('EXACT_WRITER_NULL_PAIR_REQUIRED')
    pair = saved['novel_identity']
    if (type(pair) is not dict or set(pair) != {'official_title', 'heretic_url'}
        or pair['official_title'] is not None or pair['heretic_url'] is not None
        or saved.get('title_resolution_allowed') is not False):
        raise ValueError('EXACT_WRITER_NULL_PAIR_REQUIRED')
    copied = deepcopy(saved)
    copied['novel_identity'] = None
    return copied


def canonical_result(sut, case, envelope, *, publish=True):
    # 별칭 선언과 별도의 합성 공식 상세 전제다. 외부 alias proof가 공개 권한을 만들지 않는다.
    gate = import_module('llm_batch.promotion_gate')
    root = Path(sut.agentic_pipeline.__file__).resolve().parents[2]
    assert Path(gate.__file__).resolve() == root / 'src/llm_batch/promotion_gate.py'
    title, post_id = case['title'], case['post']['post_id']
    url = f'https://novelpia.com/novel/{post_id}'
    state = gate.GroundingState(post_id=post_id, candidate_title=title, candidate_url=url,
        source='synthetic_independent_official_detail', official_title_exists=publish,
        row_discusses_work_as_work=publish, title_resolution_state='resolved' if publish else 'unresolved_matchable',
        work_resolution='resolved' if publish else 'unresolved', discussion_type='specific_work' if publish else 'unknown',
        scope=gate.ScopeState(scope_kind='current_work' if publish else 'unknown', confidence='high' if publish else 'low',
            direct_bridge_sources=('body', 'official_detail') if publish else (),
            conflict_reason_codes=() if publish else ('synthetic_hold',)))
    evidence = [gate.EvidenceRecord(kind='official_detail' if publish else 'synthetic_hold', strength='strong',
        source_path_or_snippet=url, supports_publish=publish, reason_code='independent_detail' if publish else 'synthetic_hold',
        candidate_title=title, candidate_url=url, title_url_match=True if publish else None)]
    identity = {'is_relevant': publish, 'novel_identity': {'official_title': title, 'heretic_url': url, 'confidence': 'Max'} if publish else None,
                'slang_insight': deepcopy(case['verification']['slang_insight'])}
    gate.apply_publish_contract(identity, gate.evaluate_publish_contract(state, evidence))
    typed_identity = identity if publish else typed_exact_hold_identity_input(identity)
    payload = sut.models.PickvelOutputItemV2(post_id=post_id, identity=typed_identity, batch_context_learning_envelope=envelope).model_dump(mode='json')
    return {**deepcopy(case['post']), 'comments': deepcopy(case['comments']), 'analysis_result': payload, 'run_meta': {'local_synthetic_alias_regression': True}}


def committed(sut, tmp_path, case, result):
    ledger = sut.publication_commit
    descriptor = ledger.build_publication_scope_descriptor(input_file_sha256=sha(canon(case['post'])),
        post_ids=[case['post']['post_id']], config_hash='alias_external_repair_v2')
    path = tmp_path / 'alias_external_wal.jsonl'
    registry = ledger.PublicationCommitRegistry(path, scope_descriptor=descriptor, create_new=True)
    receipt, created = ledger.commit_publication_result(result, registry=registry, attempt_run_id='alias-external-synthetic',
        input_index=1, post_id=case['post']['post_id'])
    raw = path.read_bytes()
    stored = ledger.PublicationCommitRegistry(path, scope_descriptor=descriptor, create_new=False).result(case['post']['post_id'])
    ledger.validate_publication_result_commit(stored, receipt, expected_scope_id=descriptor.publication_scope_id,
        expected_input_index=1, expected_post_id=case['post']['post_id'])
    assert path.read_bytes() == raw and canon(stored) == canon(result)
    return stored, receipt, created, path, raw


@pytest.mark.parametrize('decoder_conf,relation_conf,rank', [('high', 'high', 3), ('medium', 'high', 2), ('high', 'medium', 2)])
@pytest.mark.parametrize('title', ['달이 두 번 뜨는 항해', '별빛 길에서 돌아오면?', '나는 돌아오지 않는다'])
def test_new_external_alias_real_producer_typed_wal_main_memory(sut, external_case, tmp_path, decoder_conf, relation_conf, rank, title):
    case = deepcopy(external_case)
    case['title'] = title
    case['search_rows'][0]['title'] = title + ' - 나무위키'
    case['search_rows'][0]['url'] = 'https://namu.wiki/w/' + quote(title, safe='')
    case['decoder']['decoded_terms'][0]['interpretations'][0]['value'] = title
    case['decoder']['decoded_terms'][0]['best_match']['title'] = title
    case['verification']['novel_identity']['official_title'] = title
    case['verification']['slang_insight']['decoded_term'] = title
    case['decoder']['decoded_terms'][0]['best_match']['confidence'] = decoder_conf
    case['verification']['relation_judgment']['confidence'] = relation_conf
    envelope = produce_external(sut, case)
    assert len(envelope['decoded_terms']) == 1
    proof = envelope['decoded_terms'][0]['learning_evidence']
    assert proof['schema_version'] == sut.alias_learning.EXTERNAL_SCHEMA
    assert proof['relation_kind'] == 'external_source_bound_alias_assertion'
    assert proof['discussion_target'] == 'specific_work' and proof['alias_confidence'] == rank
    assert '_query' not in canon(envelope).decode() and 'model_summary' not in canon(envelope).decode()
    verifier = import_module('llm_batch.experts.verifier')
    root = Path(sut.agentic_pipeline.__file__).resolve().parents[2]
    assert Path(verifier.__file__).resolve() == root / 'src/llm_batch/experts/verifier.py'
    actual = object.__new__(verifier.VerifierExpert)._source_bound_alias_assertion_for_relation(
        case['title'], [case['alias']], case['search_rows'], post=case['post'], comments=case['comments'])
    assert actual == proof['external_evidence']['assertion']
    result = canonical_result(sut, case, envelope)
    before = canon(result)
    stored, receipt, created, path, wal = committed(sut, tmp_path, case, result)
    memory = sut.batch_context.BatchContextMemory(enabled=True)
    assert sut.expert_main._learn_batch_context_from_canonical_publication(memory, stored, receipt, created=created)
    if rank == 3:
        assert memory.get_abbreviation(case['alias']) == case['title']
        assert memory.resolved_abbreviations[memory._normalize(case['alias'])]['confidence'] == rank
    else:
        assert memory.get_abbreviation(case['alias']) is None
        assert memory.pending_abbreviations[memory._normalize(case['alias'])]['confidence'] == rank
        assert memory.pending_abbreviations[memory._normalize(case['alias'])]['allow_pending_promotion'] is False
    assert canon(result) == before and path.read_bytes() == wal
    assert not sut.expert_main._learn_batch_context_from_canonical_publication(memory, stored, receipt, created=False)


@pytest.mark.parametrize('mutation', [
    'cooccurrence', 'query_only', 'model_summary_only', 'different_row', 'wrong_document_url',
    'wrong_document_title', 'negation', 'hypothesis', 'question', 'reported_speech',
    'multiline_quote', 'blockquote', 'competing_work', 'same_document_counterclaim',
    'split_same_document_rows', 'ocr_diagnostic', 'generated_row',
    'missing_source_alias', 'source_other_speaker', 'source_multiline_quote', 'source_negation',
    'source_span_in_compound', 'missing_relation', 'not_specific_work', 'not_verified',
    'low_alias_confidence', 'no_source_capture_equivalent',
])
def test_unqualified_external_relation_never_becomes_learning_authority(sut, external_case, mutation):
    case = deepcopy(external_case)
    row = case['search_rows'][0]
    intro = '한국의 판타지 웹소설이다.\n'
    claim = '약칭은 ' + case['alias'] + '이다.'
    if mutation == 'cooccurrence': row['content'] = intro + case['alias'] + '와 ' + case['title'] + '을 검색했다.'
    elif mutation == 'query_only': row['content'] = intro; row['_query'] = claim
    elif mutation == 'model_summary_only': row['content'] = intro; row['model_summary'] = claim
    elif mutation == 'different_row':
        row['content'] = intro
        case['search_rows'].append({'title': '검색 안내', 'url': 'https://example.com/results', 'content': claim})
    elif mutation == 'wrong_document_url': row['url'] = 'https://namu.wiki/w/' + quote('별개의 다른 소설', safe='')
    elif mutation == 'wrong_document_title': row['title'] = '별개의 다른 소설 - 나무위키'
    elif mutation == 'negation': row['content'] = intro + claim + '\n이 약칭은 잘못된 이름이다.'
    elif mutation == 'hypothesis': row['content'] = intro + '약칭은 ' + case['alias'] + '이라면 좋겠다.'
    elif mutation == 'question': row['content'] = intro + '약칭은 ' + case['alias'] + '인가?'
    elif mutation == 'reported_speech': row['content'] = intro + '친구가 약칭은 ' + case['alias'] + '이라고 말했다.'
    elif mutation == 'multiline_quote': row['content'] = intro + '"인용 시작\n' + claim + '\n인용 끝"'
    elif mutation == 'blockquote': row['content'] = intro + '> ' + claim
    elif mutation == 'competing_work':
        case['search_rows'].append({'title': '바람이 세 번 부는 항해 - 나무위키', 'url': 'https://namu.wiki/w/' + quote('바람이 세 번 부는 항해', safe=''), 'content': intro + claim})
    elif mutation == 'same_document_counterclaim':
        case['search_rows'].append({**row, 'content': intro + case['alias'] + '는 잘못된 약칭이다.'})
    elif mutation == 'split_same_document_rows':
        row['content'] = intro
        case['search_rows'].append({**row, 'content': claim})
    elif mutation == 'ocr_diagnostic': row['_ocr_diagnostic_only'] = True
    elif mutation == 'generated_row': row['source'] = 'llm_generated_summary'
    elif mutation == 'missing_source_alias': case['post']['title'] = '이 작품은 재미있네'
    elif mutation == 'source_other_speaker': case['post']['title'] = '친구가 ' + case['alias'] + ' 재밌다고 말했다'
    elif mutation == 'source_multiline_quote':
        case['post']['title'] = '다른 사람의 발언'
        case['post']['content_blocks'] = [{'type': 'text', 'text': '"인용 시작'}, {'type': 'text', 'text': case['alias'] + ' 재미있다'}, {'type': 'text', 'text': '인용 끝"'}]
    elif mutation == 'source_negation': case['post']['title'] = case['alias'] + '는 작품명이 아니다'
    elif mutation == 'source_span_in_compound': case['post']['title'] = case['alias'] + '주인공 재미있네'
    elif mutation == 'missing_relation': case['verification'].pop('relation_judgment')
    elif mutation == 'not_specific_work': case['verification']['relation_judgment']['discussion_target'] = 'genre_general'
    elif mutation == 'not_verified': case['verification']['slang_insight']['decode_verified'] = False
    elif mutation == 'low_alias_confidence': case['decoder']['decoded_terms'][0]['best_match']['confidence'] = 'low'
    elif mutation == 'no_source_capture_equivalent':
        case['post']['title'] = ''
        case['post']['content_blocks'] = []
    assert produce_external(sut, case)['decoded_terms'] == []


@pytest.mark.parametrize('mutation', ['url', 'row_text', 'row_sha', 'catalog_sha', 'assertion_sha', 'alias', 'title', 'span', 'source_sha',
    'specific_work', 'verified_bool', 'confidence', 'unknown_field', 'removed_witness', 'competing_row'])
def test_serialized_external_witness_is_revalidated_before_consumption(sut, external_case, mutation):
    case = deepcopy(external_case)
    envelope = produce_external(sut, case)
    assert envelope['decoded_terms']
    term = envelope['decoded_terms'][0]
    proof = term['learning_evidence']
    witness = proof['external_evidence']
    if mutation == 'url': witness['rows'][0]['url'] = 'https://namu.wiki/w/' + quote('다른 작품', safe='')
    elif mutation == 'row_text': witness['rows'][0]['content'] += '\n약칭은 잘못된 것이다.'
    elif mutation == 'row_sha': witness['assertion']['source_row_sha256'] = '0' * 64
    elif mutation == 'catalog_sha': witness['rows_sha256'] = '0' * 64
    elif mutation == 'assertion_sha': witness['assertion']['assertion_sentence_sha256'] = '0' * 64
    elif mutation == 'alias': witness['assertion']['alias_surface'] = '경쟁약어'
    elif mutation == 'title': witness['assertion']['title'] = '다른 작품'
    elif mutation == 'span': proof['source_span'][0] += 1
    elif mutation == 'source_sha': proof['source_text_sha256'] = '0' * 64
    elif mutation == 'specific_work': proof['discussion_target'] = 'genre_general'
    elif mutation == 'verified_bool': proof['decode_verified'] = 1
    elif mutation == 'confidence': proof['alias_confidence'] = 4
    elif mutation == 'unknown_field': witness['model_verdict'] = True
    elif mutation == 'removed_witness': proof.pop('external_evidence')
    elif mutation == 'competing_row':
        witness['rows'].append({'title': '별개의 소설 항해 - 나무위키', 'url': 'https://namu.wiki/w/' + quote('별개의 소설 항해', safe=''),
                                'content': '한국의 웹소설이다.\n약칭은 ' + case['alias'] + '이다.'})
        witness['rows_sha256'] = sut.alias_learning._corpus_sha(witness['rows'])
    normalized = sut.batch_context.normalize_batch_context_learning_envelope(envelope)
    result = canonical_result(sut, case, normalized)
    memory = sut.batch_context.BatchContextMemory(enabled=True)
    memory.learn_from_result(result, decoded_terms=normalized['decoded_terms'])
    assert memory.resolved_abbreviations == memory.pending_abbreviations == {}


def test_hold_does_not_consume_valid_alias_and_old_commit_rejects_changed_witness(sut, external_case, tmp_path):
    case = deepcopy(external_case)
    envelope = produce_external(sut, case)
    assert envelope['decoded_terms']
    result = canonical_result(sut, case, envelope, publish=False)
    stored, receipt, created, _, _ = committed(sut, tmp_path, case, result)
    assert receipt.outcome == 'HOLD'
    memory = sut.batch_context.BatchContextMemory(enabled=True)
    assert not sut.expert_main._learn_batch_context_from_canonical_publication(memory, stored, receipt, created=created)
    altered = deepcopy(stored)
    altered['analysis_result']['batch_context_learning_envelope']['decoded_terms'][0]['learning_evidence']['external_evidence']['rows'][0]['content'] += '\n추가 문장'
    with pytest.raises(sut.publication_commit.PublicationCommitError):
        sut.publication_commit.validate_publication_result_commit(altered, receipt)


def test_wal_canonical_key_order_and_size_caps_are_not_bypassed(sut, external_case):
    case = deepcopy(external_case)
    envelope = produce_external(sut, case)
    reordered = json.loads(canon(envelope))
    assert sut.batch_context.normalize_batch_context_learning_envelope(reordered) == envelope
    result = canonical_result(sut, case, reordered)
    memory = sut.batch_context.BatchContextMemory(enabled=True)
    memory.learn_from_result(result, decoded_terms=reordered['decoded_terms'])
    assert memory.get_abbreviation(case['alias']) == case['title']
    for rows in ([case['search_rows'][0]] * 121,
                 [{**case['search_rows'][0], 'content': case['search_rows'][0]['content'] + ' ' * 6001}]):
        changed = deepcopy(case)
        changed['search_rows'] = rows
        assert produce_external(sut, changed)['decoded_terms'] == []
