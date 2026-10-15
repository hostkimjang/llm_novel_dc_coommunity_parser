"""ROOT의 격리 단일 회귀용. 원형 33/현재69 부분 context와 파생 배열 검산을 구분한다."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import PostInput
from llm_batch.experts.orchestrator import ConversationContext, ExpertType
from llm_batch.ledger.publication_commit import (
    PublicationCommitRegistry, build_publication_scope_descriptor, commit_publication_result,
)
import test_source_bound_nsfw as prior74
import test_source_bound_nsfw_desire as prior69


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).parent / 'fixtures/nsfw_enrichment_saved_context.json'
FIXTURE_SHA = '961bec1140fe45123aa10f550409a9638869883eec725995dd02922ba7f94704'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


@pytest.fixture(scope='module')
def fixed():
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == FIXTURE_SHA
    data = json.loads(raw)
    assert data['scope'] == 'SAVED_EXPERTS_PARTIAL_CONTEXT_SAME_SOURCE_URL_DERIVATION_NOT_FULL_RUN_REPLAY'
    support_before = {}
    for rel, pin in data['original_test_support_sha256'].items():
        support_before[rel] = (ROOT / rel).read_bytes()
        if rel.startswith('tests/fixtures/'):
            assert hashlib.sha256(support_before[rel]).hexdigest() == pin
        else:
            assert rel.startswith('tests/') and rel.endswith('.py')
    assert Path(prior74.__file__).resolve() == ROOT / 'tests/test_source_bound_nsfw.py'
    assert Path(prior69.__file__).resolve() == ROOT / 'tests/test_source_bound_nsfw_desire.py'
    for record in data['records'].values():
        packet = record['packet']
        assert type(packet['post_id']) is int
        assert digest({'post': packet['source_post'], 'comments': packet['source_comments']}) == packet['source_canonical_sha256']
        assert digest(packet['checkpoint_result']) == packet['result_canonical_sha256']
        assert record['experts']['arbiter']['metadata_synthesis']['is_nsfw'] is False
    before = canonical(data)
    yield data
    assert canonical(data) == before and FIXTURE.read_bytes() == raw
    assert all((ROOT / rel).read_bytes() == saved for rel, saved in support_before.items())


class ExternalAttempt(BaseException):
    pass


class NoExternal:
    def __init__(self, attempts, kind):
        self.attempts, self.kind = attempts, kind

    def __getattr__(self, name):
        def reject(*args, **kwargs):
            self.attempts.append({'kind': self.kind, 'method': name})
            raise ExternalAttempt('NO_MODEL_SEARCH_API:' + self.kind + '.' + name)
        return reject


def bare_projection(kind='both', *, ocr_enabled=True):
    """합성 배열 대조만 사용한다. native 검산 또는 모델 출력을 stub하지 않는다."""
    pipe = object.__new__(AgenticPipeline)
    pipe.enable_ocr = ocr_enabled
    source = [
        {'type': 'image', 'text': None, 'url': 'https://example.invalid/source-image.png'},
        {'type': 'text', 'text': '원래 작성자의 질문', 'url': None},
    ]
    item = {'block_index': 0, 'source_url': source[0]['url'], 'evidence_type': 'explicit_text',
            'title_role': 'unknown', 'promotion_eligible': False, 'ocr_text': '그림 속 안내 문구',
            'visual_summary': '글자가 있는 일반 안내 화면'}
    if kind == 'ocr_only':
        item['visual_summary'] = ''
    elif kind == 'summary_only':
        item['ocr_text'] = ''
    elif kind == 'weak_ocr':
        item['evidence_type'] = 'character_visual_only'
    post = {'content_blocks': copy.deepcopy(source), 'image_enrichment': [item]}
    pipe._inject_image_enrichment_blocks(post)
    return pipe, source, post


@pytest.mark.parametrize('kind,ocr_enabled,expected_types', [
    ('both', True, ['image', 'ocr_text', 'image_summary', 'text']),
    ('ocr_only', True, ['image', 'ocr_text', 'text']),
    ('summary_only', True, ['image', 'image_summary', 'text']),
    ('both', False, ['image', 'image_summary', 'text']),
    ('weak_ocr', True, ['image', 'ocr_text', 'text']),
])
def test_same_source_url_actual_injection_array_is_accepted_without_mutation(kind, ocr_enabled, expected_types):
    pipe, source, post = bare_projection(kind, ocr_enabled=ocr_enabled)
    assert [x['type'] for x in post['content_blocks']] == expected_types
    before = canonical([source, post])
    assert pipe._source_bound_nsfw_blocks_match(source, post) is True
    assert canonical([source, post]) == before


@pytest.mark.parametrize('mutation', [
    'drop_source', 'append_raw_text', 'append_unbound_ocr', 'body_text', 'ocr_text', 'summary_text',
    'reverse_order', 'move_derived', 'duplicate_derived', 'original_image_url', 'derived_url',
    'derived_type', 'original_type', 'tuple_blocks', 'non_dict_block', 'missing_enrichment',
    'foreign_enrichment_url', 'string_index', 'bool_index', 'out_of_range_index', 'text_block_index',
    'tuple_enrichment', 'non_dict_enrichment', 'changed_enrichment_ocr', 'changed_enrichment_summary',
])
def test_source_or_derivation_mismatch_is_rejected(mutation):
    pipe, source, post = bare_projection()
    blocks, item = post['content_blocks'], post['image_enrichment'][0]
    if mutation == 'drop_source': blocks.pop()
    elif mutation == 'append_raw_text': blocks.append({'type': 'text', 'text': '외부 문장', 'url': None})
    elif mutation == 'append_unbound_ocr': blocks.append({'type': 'ocr_text', 'text': '외부 문장', 'url': source[0]['url']})
    elif mutation == 'body_text': blocks[-1]['text'] += ' 변조'
    elif mutation == 'ocr_text': blocks[1]['text'] += ' 변조'
    elif mutation == 'summary_text': blocks[2]['text'] += ' 변조'
    elif mutation == 'reverse_order': blocks.reverse()
    elif mutation == 'move_derived': blocks.append(blocks.pop(1))
    elif mutation == 'duplicate_derived': blocks.insert(2, copy.deepcopy(blocks[1]))
    elif mutation == 'original_image_url': blocks[0]['url'] += '?other'
    elif mutation == 'derived_url': blocks[1]['url'] += '?other'
    elif mutation == 'derived_type': blocks[1]['type'] = 'text'
    elif mutation == 'original_type': blocks[-1]['type'] = 'ocr_text'
    elif mutation == 'tuple_blocks': post['content_blocks'] = tuple(blocks)
    elif mutation == 'non_dict_block': blocks.append('외부 문장')
    elif mutation == 'missing_enrichment': post.pop('image_enrichment')
    elif mutation == 'foreign_enrichment_url': item['source_url'] += '?other'
    elif mutation == 'string_index': item['block_index'] = '0'
    elif mutation == 'bool_index': item['block_index'] = False
    elif mutation == 'out_of_range_index': item['block_index'] = len(source)
    elif mutation == 'text_block_index': item['block_index'] = 1
    elif mutation == 'tuple_enrichment': post['image_enrichment'] = tuple(post['image_enrichment'])
    elif mutation == 'non_dict_enrichment': post['image_enrichment'].append('외부 항목')
    elif mutation == 'changed_enrichment_ocr': item['ocr_text'] += ' 변조'
    elif mutation == 'changed_enrichment_summary': item['visual_summary'] += ' 변조'
    else: raise AssertionError(mutation)
    assert pipe._source_bound_nsfw_blocks_match(source, post) is False


def test_original_ocr_typed_block_is_not_discarded_as_if_derived():
    pipe = object.__new__(AgenticPipeline)
    pipe.enable_ocr = True
    original = [{'type': 'ocr_text', 'text': '원래 입력의 고정 블록', 'url': None}]
    post = {'content_blocks': copy.deepcopy(original)}
    assert pipe._source_bound_nsfw_blocks_match(original, post) is True
    post['content_blocks'][0]['text'] = '바뀐 값'
    assert pipe._source_bound_nsfw_blocks_match(original, post) is False


def replay(fixed, name, dest, *, external_derived=False):
    record = fixed['records'][name]
    packet = record['packet']
    attempts = []
    post = PostInput(**copy.deepcopy(packet['source_post']), comments=copy.deepcopy(packet['source_comments']))
    pipe = AgenticPipeline(llm=NoExternal(attempts, 'llm'), mcp=NoExternal(attempts, 'mcp'),
                           output_dir=dest / 'pipeline', max_iterations=1, parallel_count=12, native_recovery=True)
    pipe.enable_url_fetch_disk_cache = False
    pipe._use_session_knowledge = False
    ctx = ConversationContext(post_id=post.post_id, post_data=pipe._post_to_dict(post), comments=pipe._extract_comments(post))
    ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs = tuple(post.comments)
    ctx._source_bound_nsfw_original_carrier = pipe._capture_source_bound_nsfw_carrier(post)
    captured = ctx._source_bound_nsfw_original_carrier
    for expert, value in record['experts'].items():
        ctx.set_expert_output(ExpertType(expert), copy.deepcopy(value))
    for key, value in record['observed_context_fields'].items():
        setattr(ctx, key, copy.deepcopy(value))
    # catalog는 손실 투영이다. 동일 URL 파생 함수 인자로만 쓰고 raw 검색으로 바꾸지 않는다.
    ident = packet['checkpoint_result']['analysis_result']['identity']
    ctx.post_data['image_enrichment'] = copy.deepcopy(ident['image_evidence_catalog'])
    for attr, key in (('_candidate_producer_plans', 'candidate_producer_plans'),
                      ('_candidate_producer_receipts', 'candidate_producer_receipts'),
                      ('_candidate_generation_stage_receipts', 'candidate_stage_receipts')):
        if key in ident['candidate_ledger']:
            setattr(ctx, attr, copy.deepcopy(ident['candidate_ledger'][key]))
    ocr = packet['checkpoint_result']['run_meta']['execution_config']['settings']['ocr']['value']
    assert type(ocr) is bool and ocr is True and ident['ocr_enabled'] is True
    pipe.enable_ocr = ocr  # 실제 저장 설정 복원. 전역 환경이나 모델 응답을 고치지 않는다.
    if external_derived:
        assert name == 'current33'
        # 별도 합성 대조: 실제69의 직접 댓글을 33의 같은 URL 파생 OCR/요약으로만 옮긴다.
        text = fixed['records']['current69']['packet']['source_comments'][0]['content']
        item = ctx.post_data['image_enrichment'][0]
        item.update(ocr_text=text, visual_summary=text, evidence_type='explicit_text')
    enrichment_before = canonical(ctx.post_data['image_enrichment'])
    source_blocks = json.loads(captured)['content_blocks']
    assert pipe._source_bound_nsfw_blocks_match(source_blocks, ctx.post_data) is True
    pipe._inject_image_enrichment_blocks(ctx.post_data)
    assert len(ctx.post_data['content_blocks']) > len(source_blocks)
    assert any(x['type'] == 'ocr_text' for x in ctx.post_data['content_blocks'])
    assert pipe._source_bound_nsfw_blocks_match(source_blocks, ctx.post_data) is True
    assert ctx._source_bound_nsfw_original_carrier == captured
    assert canonical(ctx.post_data['image_enrichment']) == enrichment_before
    assert not ctx.search_results, 'SAVED_CATALOG_NOT_INJECTED_AS_RAW_SEARCH'
    report = {'status': 'STARTED', 'case': name, 'scope': fixed['scope'], 'external_derived_control': external_derived,
              'source_canonical_sha256': packet['source_canonical_sha256'],
              'original_result_canonical_sha256': packet['result_canonical_sha256'],
              'captured_carrier_sha256': hashlib.sha256(captured.encode()).hexdigest(),
              'image_catalog_is_full_runtime_enrichment': False, 'actual_run_causality_proven': False}
    try:
        output = pipe._context_to_output(ctx)
        payload = output.model_dump(mode='json')
        observation = pipe.verify_final_source_context_serialization(output, payload, stage='enrichment_context')
        wrapper = prior69.actual_main_sync_and_wrapper(payload, ctx.post_data)
        pipe.verify_final_source_context_serialization(output, payload, stage='enrichment_actual_main')
        wrapped = wrapper(dict(copy.deepcopy(packet['source_post']), comments=copy.deepcopy(packet['source_comments']),
                               analysis_result=payload), output=output, verifier=pipe.verify_final_source_context_serialization)
        descriptor = build_publication_scope_descriptor(input_file_sha256=packet['source_canonical_sha256'],
                    post_ids=[ctx.post_id], config_hash='nsfw-enrichment-regression', release_fingerprint='candidate-only')
        wal = dest / 'publication.jsonl'
        registry = PublicationCommitRegistry(wal, scope_descriptor=descriptor, create_new=True)
        commit, created = commit_publication_result(wrapped, registry=registry, attempt_run_id='nsfw-enrichment-local',
                                                  input_index=1, post_id=ctx.post_id)
        stored = PublicationCommitRegistry(wal, scope_descriptor=descriptor, create_new=False).result(ctx.post_id)
        stored_observation = wrapped.verify_stored_payload(stored, stage='enrichment_wal_readback')
        proof = stored_observation['nsfw_content_observation']
        assert created and commit.outcome == 'HOLD' and commit.publish_allowed is False
        assert proof == observation['nsfw_content_observation']
        assert payload['analysis']['is_nsfw'] is record['expected_nsfw']
        assert payload['analysis']['nsfw_assessment_status'] == record['expected_assessment']
        assert proof['status'] == record['expected_source_status']
        assert proof['arbiter_value'] is False and ctx.expert_outputs['arbiter']['metadata_synthesis']['is_nsfw'] is False
        assert proof['source_carrier_sha256'] == hashlib.sha256(captured.encode()).hexdigest()
        assert stored['analysis_result']['analysis']['is_nsfw'] is record['expected_nsfw']
        assert stored['analysis_result']['identity']['novel_identity']['official_title'] is None
        assert stored['analysis_result']['identity']['novel_identity']['heretic_url'] is None
        if name == 'current69':
            assert proof['rule'] == 'DIRECT_COMMENT_SEXUAL_DESIRE_RESTRAINT_V1'
            assert all(x['source_origin'] == 'comment' for x in proof['evidence']) and proof['evidence']
            assert proof['evidence'][0]['comment_id'] == packet['source_comments'][0]['comment_id']
            assert proof['evidence'][0]['raw_text_sha256'] == hashlib.sha256(packet['source_comments'][0]['content'].encode()).hexdigest()
        else:
            assert proof['evidence'] == []
        assert attempts == []
        report.update(status='OBSERVED_PARTIAL_CONTEXT_MAIN_WAL', nsfw_observation=proof,
                      source_after_sha256=hashlib.sha256(ctx._source_bound_nsfw_original_carrier.encode()).hexdigest())
        return pipe, ctx, output, payload, wrapped, stored, wal
    except BaseException as error:
        report.update(status='INCOMPLETE_REPLAY_OR_ASSERTION_FAILURE', exception_type=type(error).__name__, message=str(error))
        raise
    finally:
        report['external_attempts'] = attempts
        (dest / 'enrichment_observation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


@pytest.fixture(scope='module', params=['current33'])
def sealed_case(fixed, request, tmp_path_factory):
    dest = tmp_path_factory.mktemp(request.param + '_enrichment')
    return request.param, replay(fixed, request.param, dest)


def test_current33_false_and_current69_source_positive_survive_real_main_wal(sealed_case):
    name, (_, _, _, _, wrapped, stored, _) = sealed_case
    wrapped.verify_stored_payload(stored, stage=name + '_final_check')


@pytest.mark.parametrize('mutation', ['title', 'body', 'image_url', 'raw_comment', 'selected_comment', 'post_id_type'])
def test_post_seal_source_and_comment_tamper_still_rejected(sealed_case, mutation, monkeypatch):
    _, (_, ctx, _, _, wrapped, stored, wal) = sealed_case
    before = wal.read_bytes()
    if mutation == 'title': monkeypatch.setitem(ctx.post_data, 'title', ctx.post_data['title'] + ' 변조')
    elif mutation == 'body':
        blocks = copy.deepcopy(ctx.post_data['content_blocks'])
        next(x for x in blocks if x['type'] == 'text')['text'] += ' 변조'
        monkeypatch.setitem(ctx.post_data, 'content_blocks', blocks)
    elif mutation == 'image_url':
        blocks = copy.deepcopy(ctx.post_data['content_blocks'])
        next(x for x in blocks if x['type'] == 'image')['url'] += '?other'
        monkeypatch.setitem(ctx.post_data, 'content_blocks', blocks)
    elif mutation == 'raw_comment':
        comments = copy.deepcopy(ctx.post_data['comments_raw'])
        comments[0]['content'] += ' 변조'
        monkeypatch.setitem(ctx.post_data, 'comments_raw', comments)
    elif mutation == 'selected_comment':
        comments = list(ctx.comments)
        comments[0] = comments[0] + ' 변조'
        monkeypatch.setattr(ctx, 'comments', comments)
    elif mutation == 'post_id_type': monkeypatch.setitem(ctx.post_data, 'post_id', str(ctx.post_id))
    else: raise AssertionError(mutation)
    with pytest.raises(ValueError):
        wrapped.verify_stored_payload(stored, stage='enrichment_source_tamper')
    assert wal.read_bytes() == before


@pytest.mark.parametrize('field,value', [('is_nsfw', 'false'), ('is_nsfw', 0), ('nsfw_assessment_status', 'NOT_EVALUATED')])
def test_post_seal_serialized_bool_and_assessment_tamper_rejected(sealed_case, field, value):
    _, (_, _, _, _, wrapped, stored, wal) = sealed_case
    before = wal.read_bytes()
    changed = copy.deepcopy(stored)
    changed['analysis_result']['analysis'][field] = value
    with pytest.raises(ValueError):
        wrapped.verify_stored_payload(changed, stage='enrichment_wire_tamper')
    assert wal.read_bytes() == before


def test_external_derived_text_does_not_become_original_comment_rule_evidence(fixed, tmp_path):
    _, _, _, _, _, stored, _ = replay(fixed, 'current33', tmp_path, external_derived=True)
    assert stored['analysis_result']['analysis']['is_nsfw'] is False


# 원형 69의 기대값 목록과 원형 함수 자체를 그대로 사용한다. 기대값을 새로 낮추지 않는다.
ORIGINAL69_MATRIX = next(mark.args[1] for mark in prior69.test_source69_respects_existing_metadata_types_and_boolean_assessment_pair.pytestmark if mark.name == 'parametrize')


@pytest.mark.parametrize('value,expected,status', ORIGINAL69_MATRIX)
def test_existing69_metadata_contract_unchanged(fixed, value, expected, status):
    prior69.test_source69_respects_existing_metadata_types_and_boolean_assessment_pair(value, expected, status)


def test_existing74_precedence_unchanged(fixed):
    prior69.test_existing74_rule_keeps_precedence_even_with_an_additional_desire_comment()


def test_existing74_source_and_real_wal_readback_unchanged(fixed):
    case = prior74.SourceBoundNSFWTests(methodName='test_actual74_false_conflict_uses_exact_source_and_real_wal_readback')
    case.test_actual74_false_conflict_uses_exact_source_and_real_wal_readback()
