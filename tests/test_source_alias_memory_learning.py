"""공유 별칭 학습 후손 회귀. ROOT가 완료 런과 격리 tree를 확인한 뒤 실행한다.

기존 13개 characterization 기대값을 바꾸지 않는다. 원본 fixture/receipt와
새 봉투로 만든 후손 WAL을 구분하고, 실제 memory/main/producer 경계를 사용한다.
"""
from copy import deepcopy
from importlib import import_module
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


FIXTURES = Path(__file__).parent / 'fixtures/alias_memory_repair_v1'


def canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(value):
    return hashlib.sha256(value).hexdigest()


@pytest.fixture(scope='module')
def facts():
    manifest_raw = (FIXTURES / 'manifest.json').read_bytes()
    manifest = json.loads(manifest_raw)
    for name, digest in manifest['files_sha256'].items():
        assert sha((FIXTURES / name).read_bytes()) == digest
    rows = {int(p.stem.split('_')[1]): json.loads(p.read_text(encoding='utf-8')) for p in FIXTURES.glob('row_*.json')}
    before = canon(rows)
    for index, item in rows.items():
        p = item['packet']
        assert p['index1'] == index and type(p['post_id']) is int
        assert sha(canon({'post': p['source_post'], 'comments': p['source_comments']})) == p['source_canonical_sha256']
        assert sha(canon(p['checkpoint_result'])) == p['result_canonical_sha256']
        assert item['checkpoint']['result'] == p['checkpoint_result']
        assert item['experts']['post_id'] == p['post_id']
    yield rows
    assert canon(rows) == before
    assert (FIXTURES / 'manifest.json').read_bytes() == manifest_raw
    for name, digest in manifest['files_sha256'].items():
        assert sha((FIXTURES / name).read_bytes()) == digest


@pytest.fixture(scope='module')
def sut(facts):
    # 원형 계약에서는 원문 fixture 결속만 사용한다. 실행 위치/제품 SHA는 의미 기대값이 아니다.
    contract_path = FIXTURES / 'execution_contract.json'
    contract_raw = contract_path.read_bytes()
    control = json.loads(contract_raw)
    assert control['fixture_manifest_sha256'] == sha((FIXTURES / 'manifest.json').read_bytes())
    tree = Path(__file__).resolve().parents[1]
    assert (tree / 'expert_main.py').is_file(), 'CURRENT_CHECKOUT_REQUIRED'
    names = ['expert_main', 'llm_batch.agentic_pipeline', 'llm_batch.domain.batch_context',
             'llm_batch.domain.alias_learning', 'llm_batch.domain.models',
             'llm_batch.experts.orchestrator', 'llm_batch.ledger.publication_commit']
    paths = {name: tree / ('expert_main.py' if name == 'expert_main' else
                          'src/' + name.replace('.', '/') + '.py') for name in names}
    # 현재 바이트는 시험 전후 불변만 확인하며 제품 정답으로 사용하지 않는다.
    before = {name: path.read_bytes() for name, path in paths.items()}
    violations = []
    active = [True]
    def audit(event, args):
        if active[0] and (event.startswith(('socket.connect', 'socket.bind', 'socket.getaddrinfo', 'subprocess.', 'os.spawn')) or event in {'os.system', 'urllib.Request'}):
            violations.append(event)
            raise AssertionError('ALIAS_REPAIR_EXTERNAL_ATTEMPT:' + event)
    sys.addaudithook(audit)
    sys.dont_write_bytecode = True
    modules = {}
    try:
        for name in names:
            module = import_module(name)
            assert Path(module.__file__).resolve() == paths[name].resolve()
            modules[name.rsplit('.', 1)[-1]] = module
        yield SimpleNamespace(**modules)
    finally:
        active[0] = False
        assert not violations
        assert contract_path.read_bytes() == contract_raw
        assert all(path.read_bytes() == before[name] for name, path in paths.items())



def produce(sut, item):
    p = item['packet']
    ctx = sut.orchestrator.ConversationContext(post_id=p['post_id'], post_data=deepcopy(p['source_post']), comments=deepcopy(p['source_comments']))
    input_model = sut.models.PostInput(**p['source_post'], comments=deepcopy(p['source_comments']))
    ctx._batch_alias_original_source = sut.alias_learning.capture_alias_source(input_model)
    for block in item['experts']['blocks']:
        ctx.expert_outputs[block['expert']] = deepcopy(block['value'])
    before = canon({'post': ctx.post_data, 'comments': ctx.comments, 'experts': ctx.expert_outputs, 'source': ctx._batch_alias_original_source})
    pipeline = object.__new__(sut.agentic_pipeline.AgenticPipeline)
    envelope = pipeline._build_batch_context_learning_envelope(ctx)
    assert before == canon({'post': ctx.post_data, 'comments': ctx.comments, 'experts': ctx.expert_outputs, 'source': ctx._batch_alias_original_source})
    model = sut.models.PickvelOutputItemV2(post_id=p['post_id'], identity={'is_relevant': True}, batch_context_learning_envelope=envelope)
    assert model.model_dump()['batch_context_learning_envelope'] == envelope
    return envelope, ctx, pipeline


@pytest.mark.parametrize('index', [8, 50, 55, 56, 64, 79])
def test_fixed_source_experts_producer_typed_envelope(sut, facts, index):
    envelope, _, _ = produce(sut, facts[index])
    terms = envelope['decoded_terms']
    if index == 64:
        assert [term['original'] for term in terms] == ['나혼렙']
        assert terms[0]['best_match'] == {'title': '나 혼자만 레벨업', 'confidence': 'high'}
        assert terms[0]['learning_evidence']['alias_confidence'] == 3
    else:
        assert terms == [], (index, terms)
    # 작가 14번은 별도 수리다. 이 후보가 작가/인물 채널을 재해석하지 않는다.
    old = facts[index]['packet']['checkpoint_result']['analysis_result']['batch_context_learning_envelope']
    assert envelope['identified_characters'] == old['identified_characters']


@pytest.mark.parametrize('index', [8, 56, 64, 50, 55, 79])
def test_actual_commit_then_descendant_wal_main_learning(sut, facts, tmp_path, index):
    item = facts[index]
    p = item['packet']
    commit = sut.publication_commit
    original = p['checkpoint_result']
    original_bytes = canon(original)
    receipt = commit.validate_publication_result_commit(original, item['checkpoint']['publication_commit'], expected_scope_id=p['publication_scope_id'], expected_input_index=index, expected_post_id=p['post_id'])
    # 기존 WAL의 원본 결과/commit을 새 봉투로 덮어쓰지 않는다.
    descendant = deepcopy(original)
    descendant['analysis_result']['batch_context_learning_envelope'] = produce(sut, item)[0]
    assert descendant['analysis_result']['identity'] == original['analysis_result']['identity']
    descriptor = commit.build_publication_scope_descriptor(input_file_sha256=sha(canon(p['source_post'])), post_ids=[p['post_id']], config_hash='alias-learning-repair-descendant-v1')
    wal_path = tmp_path / 'descendant_wal.jsonl'
    registry = commit.PublicationCommitRegistry(wal_path, scope_descriptor=descriptor, create_new=True)
    new_receipt, created = commit.commit_publication_result(descendant, registry=registry, attempt_run_id='alias-repair-descendant', input_index=1, post_id=p['post_id'])
    assert new_receipt.outcome == receipt.outcome
    wal_before = wal_path.read_bytes()
    reopened = commit.PublicationCommitRegistry(wal_path, scope_descriptor=descriptor, create_new=False)
    canonical_result = reopened.result(p['post_id'])
    commit.validate_publication_result_commit(canonical_result, new_receipt, expected_scope_id=descriptor.publication_scope_id, expected_input_index=1, expected_post_id=p['post_id'])
    memory = sut.batch_context.BatchContextMemory(enabled=True)
    learned = sut.expert_main._learn_batch_context_from_canonical_publication(memory, canonical_result, new_receipt, created=created)
    assert learned is (receipt.outcome == 'PUBLISH')
    if index == 64:
        assert memory.get_abbreviation('나혼렙') == '나 혼자만 레벨업'
    else:
        assert memory.resolved_abbreviations == memory.pending_abbreviations == {}
    assert wal_path.read_bytes() == wal_before and canon(original) == original_bytes
    assert not sut.expert_main._learn_batch_context_from_canonical_publication(memory, canonical_result, new_receipt, created=False)


def synthetic(sut, *, alias='쌍달', title='달이 두 번 뜨는 날', decoder_conf='high', relation_conf='high', body=None, store=False):
    source = {'post_id': 501, 'title': '작품 별칭 정리', 'content_blocks': [{'type': 'text', 'text': body if body is not None else f'「{title}」의 약칭은 「{alias}」이다.'}]}
    decoder = {'needs_verification': False, 'decoded_terms': [{'original': alias, 'is_author_name': False, 'interpretations': [{'type': 'novel_title', 'value': title}], 'best_match': {'title': title, 'confidence': decoder_conf}}]}
    verification = {'is_relevant': True, 'novel_identity': {'official_title': title, 'confidence': 'Max'}, 'slang_insight': {'canonical_work_alias': alias, 'detected_term': alias, 'decoded_term': title, 'decode_verified': True, 'alias_scope': 'pure_work_alias', 'store_in_slang_db': store}, 'relation_judgment': {'relation_type': 'explicit_alias', 'discussion_target': 'specific_work', 'promotion_decision': 'allow', 'confidence': relation_conf}}
    terms = sut.alias_learning.build_alias_learning_terms(source, decoder, verification, registries=())
    result = {**deepcopy(source), 'identity': {'is_relevant': True, 'novel_identity': {'official_title': title, 'confidence': 'Max'}, 'slang_insight': deepcopy(verification['slang_insight'])}}
    return source, decoder, verification, terms, result


@pytest.mark.parametrize('title,alias', [('달이 두 번 뜨는 날', '쌍달'), ('내가 돌아오면 세계는?', '돌아온 날은 끝이 아니다'), ('나는 돌아오지 않는다', '나는 돌아오지 않는다')])
@pytest.mark.parametrize('store', [True, False])
def test_explicit_alias_sentence_title_and_store_policy_preserved(sut, title, alias, store):
    source, decoder, verification, terms, result = synthetic(sut, title=title, alias=alias, store=store)
    assert len(terms) == 1
    before = canon(result)
    memory = sut.batch_context.BatchContextMemory(enabled=True)
    memory.learn_from_result(result, decoded_terms=terms, identified_author='정상 필명', identified_characters=['주인공'])
    if alias == title:
        assert memory.resolved_abbreviations == memory.pending_abbreviations == {}
        assert memory.stats['abbreviation_exact_title_skipped'] == 1
    else:
        assert memory.get_abbreviation(alias) == title
    assert memory.get_author_works('정상 필명')['title'] == title
    assert memory.get_character_work('주인공') == title
    assert canon(result) == before


@pytest.mark.parametrize('decoder_conf,relation_conf,expected', [('medium', 'high', 2), ('high', 'medium', 2), ('low', 'high', 0), ('high', 'low', 0), ('', 'high', 0), ('high', '', 0)])
def test_individual_confidence_survives_normalization_and_is_not_work_confidence(sut, decoder_conf, relation_conf, expected):
    _, _, _, terms, result = synthetic(sut, decoder_conf=decoder_conf, relation_conf=relation_conf)
    envelope = sut.batch_context.normalize_batch_context_learning_envelope({'schema_version': sut.batch_context.BATCH_CONTEXT_LEARNING_ENVELOPE_SCHEMA, 'decoded_terms': terms})
    memory = sut.batch_context.BatchContextMemory(enabled=True)
    for _ in range(3):
        memory.learn_from_result(result, decoded_terms=envelope['decoded_terms'])
    assert memory.resolved_abbreviations == {}
    if expected:
        assert envelope['decoded_terms'][0]['learning_evidence']['alias_confidence'] == expected
        assert memory.pending_abbreviations[memory._normalize('쌍달')]['confidence'] == expected
    else:
        assert envelope['decoded_terms'] == [] and memory.pending_abbreviations == {}


@pytest.mark.parametrize('body', ['「달이 두 번 뜨는 날」의 약칭은 「쌍달」이 아니다.', '「달이 두 번 뜨는 날」의 약칭은 「쌍달」이라면 좋겠다.', '> 「달이 두 번 뜨는 날」의 약칭은 「쌍달」이다.', '다른 사람이 「달이 두 번 뜨는 날」의 약칭은 「쌍달」이라고 말했다.'])
def test_negated_hypothetical_external_speech_is_not_an_alias_declaration(sut, body):
    assert synthetic(sut, body=body)[3] == []


@pytest.mark.parametrize('change', ['missing', 'post_id', 'span', 'text_hash', 'corpus_hash', 'term_title', 'official_title', 'confidence', 'body', 'extra_field'])
def test_consumer_revalidates_persisted_proof_and_source(sut, change):
    _, _, _, terms, result = synthetic(sut)
    assert terms
    term = terms[0]
    proof = term['learning_evidence']
    if change == 'missing': term.pop('learning_evidence')
    elif change == 'post_id': proof['post_id'] += 1
    elif change == 'span': proof['source_span'][0] += 1
    elif change == 'text_hash': proof['source_text_sha256'] = '0' * 64
    elif change == 'corpus_hash': proof['source_corpus_sha256'] = '0' * 64
    elif change == 'term_title': term['best_match']['title'] = '경쟁 작품'
    elif change == 'official_title': result['identity']['novel_identity']['official_title'] = '경쟁 작품'
    elif change == 'confidence': proof['alias_confidence'] = 4
    elif change == 'body': result['content_blocks'][0]['text'] += ' 추가 원문'
    elif change == 'extra_field': proof['unvalidated'] = True
    memory = sut.batch_context.BatchContextMemory(enabled=True)
    memory.learn_from_result(result, decoded_terms=terms)
    assert memory.resolved_abbreviations == memory.pending_abbreviations == {}


def test_multiline_quote_derived_text_comments_and_missing_original_capture(sut, facts):
    source, decoder, vf, _, _ = synthetic(sut)
    statement = source['content_blocks'][0]['text']
    variants = [
        [{'type': 'text', 'text': '"타인의 설명 시작'}, {'type': 'text', 'text': statement}, {'type': 'text', 'text': '인용 끝"'}],
        [{'type': 'text', 'text': statement, 'speaker': 'commenter'}],
        [{'type': 'text', 'text': statement, 'from_ocr': True}],
        [{'type': 'text', 'text': statement, 'quoted': True}],
    ]
    for blocks in variants:
        altered = {**source, 'content_blocks': blocks}
        assert sut.alias_learning.build_alias_learning_terms(altered, decoder, vf, registries=()) == []
    assert sut.alias_learning.build_alias_learning_terms({**source, 'content_blocks': [], 'comments': [statement]}, decoder, vf, registries=()) == []
    _, ctx, pipeline = produce(sut, facts[64])
    del ctx._batch_alias_original_source
    assert pipeline._build_batch_context_learning_envelope(ctx)['decoded_terms'] == []


def test_original_legacy_row_does_not_relearn_unqualified_aliases(sut, facts):
    item = facts[8]
    memory = sut.batch_context.BatchContextMemory(enabled=True)
    receipt = sut.publication_commit.PublicationDecisionCommit.from_dict(item['checkpoint']['publication_commit'])
    original = deepcopy(item['packet']['checkpoint_result'])
    before = canon(original)
    assert sut.expert_main._learn_batch_context_from_canonical_publication(memory, original, receipt, created=True)
    assert memory.resolved_abbreviations == memory.pending_abbreviations == {}
    assert canon(original) == before


def test_inline_consumer_uses_same_proof_with_actual64_source(sut, facts):
    envelope, ctx, pipeline = produce(sut, facts[64])
    identity = deepcopy(facts[64]['packet']['checkpoint_result']['analysis_result']['identity'])
    output = sut.models.PickvelOutputItemV2(post_id=ctx.post_id, identity=identity, batch_context_learning_envelope=envelope)
    pipeline.batch_context = sut.batch_context.BatchContextMemory(enabled=True)
    ctx.fetched_page_info = []
    before = canon(output.model_dump())
    pipeline._learn_batch_context(ctx, output)
    assert pipeline.batch_context.get_abbreviation('나혼렙') == '나 혼자만 레벨업'
    assert canon(output.model_dump()) == before


@pytest.mark.parametrize('case', ['pending_decoder', 'mixed_character', 'author_role', 'genre_relation', 'unverified_alias', 'different_decoded_title', 'low_work_confidence', 'final_alias_denied'])
def test_individual_role_and_final_work_gates_remain_independent(sut, case):
    source, decoder, vf, _, result = synthetic(sut)
    if case == 'pending_decoder': decoder['needs_verification'] = True
    elif case == 'mixed_character': decoder['decoded_terms'][0]['interpretations'].append({'type': 'character_name', 'value': '인물 이름'})
    elif case == 'author_role': decoder['decoded_terms'][0]['is_author_name'] = True
    elif case == 'genre_relation': vf['relation_judgment']['relation_type'] = 'genre_or_trope_label'
    elif case == 'unverified_alias': vf['slang_insight']['decode_verified'] = False
    elif case == 'different_decoded_title': vf['slang_insight']['decoded_term'] = '다른 작품'
    elif case == 'low_work_confidence': result['identity']['novel_identity']['confidence'] = 'Low'
    elif case == 'final_alias_denied': result['identity']['slang_insight']['decode_verified'] = False
    terms = sut.alias_learning.build_alias_learning_terms(source, decoder, vf, registries=())
    if case in {'low_work_confidence', 'final_alias_denied'}:
        assert terms, '개별 관계와 공개/최종 단계의 차단을 구분한다'
    else:
        assert terms == []
    memory = sut.batch_context.BatchContextMemory(enabled=True)
    memory.learn_from_result(result, decoded_terms=terms)
    assert memory.resolved_abbreviations == memory.pending_abbreviations == {}


def test_normalizer_is_bounded_idempotent_and_does_not_publish_raw_experts(sut):
    _, _, _, terms, _ = synthetic(sut)
    raw = {'schema_version': sut.batch_context.BATCH_CONTEXT_LEARNING_ENVELOPE_SCHEMA, 'decoded_terms': deepcopy(terms), 'identified_author': '정상 필명', 'identified_characters': ['인물', '인물'], 'raw_prompt': 'PRIVATE'}
    raw['decoded_terms'][0]['raw_snippet'] = 'PRIVATE'
    before = canon(raw)
    normalized = sut.batch_context.normalize_batch_context_learning_envelope(raw)
    assert normalized == sut.batch_context.normalize_batch_context_learning_envelope(normalized)
    assert b'PRIVATE' not in canon(normalized)
    assert normalized['identified_characters'] == ['인물'] and canon(raw) == before


def test_scope_conflict_and_disabled_memory_do_not_learn(sut):
    _, _, _, terms, result = synthetic(sut)
    for identity_patch in ({'is_relevant': False}, {'title_resolution_allowed': False}, {'title_resolution_state': 'context_only'}):
        altered = deepcopy(result)
        altered['identity'].update(identity_patch)
        memory = sut.batch_context.BatchContextMemory(enabled=True)
        memory.learn_from_result(altered, decoded_terms=terms)
        assert memory.resolved_abbreviations == memory.pending_abbreviations == {}
    memory = sut.batch_context.BatchContextMemory(enabled=False)
    memory.learn_from_result(result, decoded_terms=terms)
    assert memory.resolved_abbreviations == memory.pending_abbreviations == {}


@pytest.mark.parametrize('body', ['달이 두 번 뜨는 날의 약칭은 쌍달이다.', '쌍달은 달이 두 번 뜨는 날의 별칭이다.', '「쌍달」은 「달이 두 번 뜨는 날」의 줄임말입니다.'])
def test_unquoted_and_inverse_explicit_alias_declaration_preserved(sut, body):
    _, _, _, terms, result = synthetic(sut, body=body)
    assert len(terms) == 1
    memory = sut.batch_context.BatchContextMemory(enabled=True)
    memory.learn_from_result(result, decoded_terms=terms)
    assert memory.get_abbreviation('쌍달') == '달이 두 번 뜨는 날'
