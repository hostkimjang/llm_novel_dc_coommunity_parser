"""ROOT의 묶음 검증용. 같은 URL의 저장 투영이며 원래 VLM 인자/픽셀 정답이 아니다."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from llm_batch.experts.orchestrator import ExpertMessage, ExpertType
from llm_batch.ledger.publication_commit import (
    PublicationCommitRegistry, build_publication_scope_descriptor, commit_publication_result,
)
from test_source_bound_nsfw import context_for
from test_source_bound_nsfw_desire import actual_main_sync_and_wrapper
from test_nsfw_assessment_status import image_record, positive_image, serialize_record


FIXTURE = Path(__file__).parent / 'fixtures/nsfw_image_assessment_saved49_60.json'
FIXTURE_SHA = '3e5691f879b02ae890b2ba57c5eee458f80d6497f1b8dfd17b6a90a553c985b1'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


@pytest.fixture(scope='module')
def saved():
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == FIXTURE_SHA
    value = json.loads(raw)
    assert value['scope'] == 'SAVED_EXPERTS_PARTIAL_CONTEXT_NOT_RUNTIME_ARGUMENT_CAPTURE'
    for record in value['records'].values():
        packet = record['packet']
        assert type(packet['post_id']) is int
        assert digest({'post': packet['source_post'], 'comments': packet['source_comments']}) == packet['source_canonical_sha256']
        assert digest(packet['checkpoint_result']) == packet['result_canonical_sha256']
        assert set(record['experts']) == {'gatekeeper', 'discourse'}
        assert {name: digest(expert) for name, expert in record['experts'].items()} == record['expert_sha256']
    before = canonical(value)
    yield value
    assert canonical(value) == before and FIXTURE.read_bytes() == raw


def prepared(saved, index, *, inject=True):
    row = saved['records'][str(index)]
    packet = row['packet']
    record = {'post': deepcopy(packet['source_post']), 'comments': deepcopy(packet['source_comments']),
              'experts': deepcopy(row['experts'])}
    pipe, ctx, record = context_for(record_override=record)
    pipe.enable_ocr = True
    ctx.post_data['image_enrichment'] = deepcopy(row['image_projection'])
    if inject:
        pipe._inject_image_enrichment_blocks(ctx.post_data)
    return pipe, ctx, record


@pytest.mark.parametrize('index', [49, 60])
def test_saved_noise_images_use_bound_native_rule_and_actual_main_wal(saved, index, tmp_path):
    pipe, ctx, record = prepared(saved, index)
    before = canonical([ctx.post_data, ctx.comments, ctx.expert_outputs, record])
    capture = ctx._source_bound_nsfw_original_carrier
    assert ctx.get_expert_output(ExpertType.ARBITER) is None
    output = pipe._context_to_output(ctx)
    payload = output.model_dump(mode='json')
    observation = pipe.verify_final_source_context_serialization(output, payload, stage='image_native')
    proof = observation['nsfw_content_observation']
    assert payload['analysis']['is_nsfw'] is True
    assert payload['analysis']['nsfw_assessment_status'] == 'SOURCE_RULE_POSITIVE'
    assert payload['analysis']['nsfw_assessment_reason'] == 'SOURCE_IMAGE_RULE_POSITIVE'
    assert proof['model_assessment']['status'] == 'NOISE_OUTPUT_WITHOUT_MODEL_ASSESSMENT'
    assert proof['model_assessment']['noise_early_return_observed'] is False
    assert proof['image_assessment']['binding_status'] == 'BOUND'
    assert proof['image_assessment']['fallback_executed'] is True
    assert proof['image_assessment']['pixels_verified'] is False
    assert proof['evidence'][0]['block_index'] == 0
    assert proof['evidence'][0]['ocr_sha256'] == hashlib.sha256(recorded_ocr(saved, index).encode()).hexdigest()
    assert payload['identity']['novel_identity'] is None
    assert payload['identity']['promotion_decision']['publish_allowed'] is False
    wrapper = actual_main_sync_and_wrapper(payload, ctx.post_data)
    pipe.verify_final_source_context_serialization(output, payload, stage='image_actual_main')
    row = dict(record['post'], comments=deepcopy(record['comments']), analysis_result=payload)
    wrapped = wrapper(row, output=output, verifier=pipe.verify_final_source_context_serialization)
    scope = build_publication_scope_descriptor(input_file_sha256=digest(record['post']),
        post_ids=[ctx.post_id], config_hash='image-partial-source', release_fingerprint='candidate-only')
    path = tmp_path / 'commits.jsonl'
    registry = PublicationCommitRegistry(path, scope_descriptor=scope, create_new=True)
    commit, created = commit_publication_result(wrapped, registry=registry, attempt_run_id='image-partial',
        input_index=1, post_id=ctx.post_id)
    assert created and commit.outcome == 'HOLD' and commit.publish_allowed is False
    stored = PublicationCommitRegistry(path, scope_descriptor=scope, create_new=False).result(ctx.post_id)
    checked = wrapped.verify_stored_payload(stored, stage='image_wal_readback')
    assert checked['nsfw_content_observation'] == proof
    assert stored['analysis_result'] == payload
    assert before == canonical([ctx.post_data, ctx.comments, ctx.expert_outputs, record])
    assert ctx._source_bound_nsfw_original_carrier == capture
    wal_before = path.read_bytes()
    for reason in ('MODEL_BOOLEAN_REPORTED', None, False, 1, {}, 'UNKNOWN', 'DELETE'):
        changed = deepcopy(stored)
        if reason == 'DELETE':
            del changed['analysis_result']['analysis']['nsfw_assessment_reason']
        else:
            changed['analysis_result']['analysis']['nsfw_assessment_reason'] = reason
        with pytest.raises(ValueError, match='NSFW assessment reason'):
            wrapped.verify_stored_payload(changed, stage='image_reason_tampered')
    assert path.read_bytes() == wal_before


def recorded_ocr(saved, index):
    return saved['records'][str(index)]['image_projection'][0]['ocr_text']


@pytest.mark.parametrize('index', [49, 60])
@pytest.mark.parametrize('inject', [False, True])
def test_same_source_projection_before_and_after_actual_injection_is_read_only(saved, index, inject):
    pipe, ctx, _ = prepared(saved, index, inject=inject)
    before = canonical([ctx.post_data, ctx.comments, ctx.expert_outputs])
    result = pipe._source_bound_image_nsfw_assessment(ctx)
    assert result['status'] == 'SOURCE_IMAGE_RULE_POSITIVE'
    assert result['binding_status'] == 'BOUND'
    assert before == canonical([ctx.post_data, ctx.comments, ctx.expert_outputs])
    # This helper's positive cannot bypass the final native gate.
    decision = pipe._source_bound_nsfw_decision(ctx, {}, False, native_verified=False)
    assert decision['status'] == 'SOURCE_NOT_BOUND'
    assert decision['resolved_value'] is False
    assert decision['assessment_status'] == 'NOT_EVALUATED'


@pytest.mark.parametrize('mutation', [
    'missing_carrier', 'source_title', 'source_id_type', 'source_comment', 'raw_comment',
    'selected_comment', 'source_url', 'foreign_url', 'string_index', 'bool_index',
    'other_index', 'duplicate_index', 'wrong_ocr_type', 'wrong_summary_type', 'foreign_derived',
    'changed_injected_ocr', 'changed_injected_url', 'removed_source',
])
def test_image_source_and_derivation_mismatch_cannot_create_positive(saved, mutation):
    pipe, ctx, _ = prepared(saved, 49)
    post = ctx.post_data
    item = post['image_enrichment'][0]
    if mutation == 'missing_carrier': del ctx._source_bound_nsfw_original_carrier
    elif mutation == 'source_title': post['title'] += ' changed'
    elif mutation == 'source_id_type': post['post_id'] = str(post['post_id'])
    elif mutation == 'source_comment': ctx._final_source_original_comment_refs = ()
    elif mutation == 'raw_comment': post['comments_raw'] = []
    elif mutation == 'selected_comment': ctx.comments = []
    elif mutation == 'source_url': post['content_blocks'][0]['url'] += '?changed'
    elif mutation == 'foreign_url': item['source_url'] += '?other'
    elif mutation == 'string_index': item['block_index'] = '0'
    elif mutation == 'bool_index': item['block_index'] = False
    elif mutation == 'other_index': item['block_index'] = 1
    elif mutation == 'duplicate_index': post['image_enrichment'].append(deepcopy(item))
    elif mutation == 'wrong_ocr_type': item['ocr_text'] = ['text']
    elif mutation == 'wrong_summary_type': item['visual_summary'] = 1
    elif mutation == 'foreign_derived': post['content_blocks'].append({'type':'ocr_text','text':'external','url':'https://foreign.invalid'})
    elif mutation == 'changed_injected_ocr': post['content_blocks'][1]['text'] += ' changed'
    elif mutation == 'changed_injected_url': post['content_blocks'][1]['url'] += '?other'
    elif mutation == 'removed_source': post['content_blocks'].pop(0)
    else: raise AssertionError(mutation)
    before = canonical([post, ctx.comments])
    result = pipe._source_bound_image_nsfw_assessment(ctx)
    assert result['status'] != 'SOURCE_IMAGE_RULE_POSITIVE'
    assert result['evidence'] == []
    assert pipe._fallback_explicit_nsfw_from_image(ctx) is False
    assert before == canonical([post, ctx.comments])


@pytest.mark.parametrize('ocr,visual', [
    ('정자 잔뜩 마셔', ''), ('', '성인용 만화의 한 장면이다.'),
    ('SEXTOY', ''), ('', '성인용 기구의 제품 이미지다.'),
    ('성교', '성인용 만화의 한 장면이다.'),
    ('성교하는 사람은 소설 제목이다.', '소설 표지의 제목과 약어를 설명한다.'),
    ('정자 잔뜩 마셔', '의학 교재가 성적 장면의 오류를 설명한다.'),
    ('성교육 교재', '성인용 기구를 보여 주는 제품 이미지다.'),
    ('정자 잔뜩 마셔', '성인용 만화 장면이 아니다.'),
    ('일반제품', '성인용 기구가 아니라 운동용 제품 이미지다.'),
    ('중성제품', '성인용 기구는 없음. 일상 용품의 제품 이미지.'),
    ('일반제품', '의료용 인체 모형이 성기 모양인 제품 이미지다.'),
    ('일반제품', '성인용 운동 기구의 제품 이미지다.'),
    ('일반제품', '성인용 제품의 제품 이미지다.'),
    ('일반제품', '성인용 기구가 아닌 제품 이미지다.'),
    ('일반제품', '성적이지 않은 성인용 기구 제품 이미지다.'),
    ('PRODUCT', 'Not a dildo. 제품 이미지다.'),
    ('PRODUCT', 'Medical dildo 제품 이미지다.'),
    ('섹스', '도서 제목과 약칭의 표기다.'),
    ('정자에서 물을 마셔', '정원에 놓인 정자를 그린 풍경 이미지다.'),
])
def test_ocr_summary_context_controls_remain_unevaluated(saved, ocr, visual):
    pipe, ctx, _ = prepared(saved, 49, inject=False)
    ctx.post_data['image_enrichment'][0].update(ocr_text=ocr, visual_summary=visual)
    pipe._inject_image_enrichment_blocks(ctx.post_data)
    result = pipe._source_bound_image_nsfw_assessment(ctx)
    assert result['binding_status'] == 'BOUND'
    assert result['status'] == 'NO_POSITIVE_IMAGE_RULE'
    assert result['requires_image_review'] is True


@pytest.mark.parametrize('ocr,visual', [
    ('정자 잔뜩 마셔', '성인용 만화의 한 장면을 그린 일러스트다.'),
    ('성관계를 하자', '성적 장면을 묘사한 이미지다.'),
    ('새로운 표기', '성인용 기구의 제품 사진과 라벨이 보인다.'),
    ('', '성인용 기구이며 성기 모양인 제품 이미지다.'),
])
def test_general_content_and_product_relations_do_not_depend_on_actual_names(saved, ocr, visual):
    pipe, ctx, _ = prepared(saved, 49, inject=False)
    ctx.post_data['image_enrichment'][0].update(ocr_text=ocr, visual_summary=visual)
    result = pipe._source_bound_image_nsfw_assessment(ctx)
    assert result['status'] == 'SOURCE_IMAGE_RULE_POSITIVE'
    assert len(result['evidence']) == 1


def test_cross_image_or_external_search_text_cannot_complete_relation():
    first = positive_image()
    first['visual_summary'] = '일반 그림이다.'
    second = dict(first, block_index=1, source_url='https://fixture.invalid/two.png',
        ocr_text='', visual_summary='성인용 만화의 한 장면이다.')
    record = image_record()
    record['post']['content_blocks'].append({'type':'image','url':second['source_url']})
    pipe, ctx, _ = context_for(record_override=record)
    pipe.enable_ocr = True
    ctx.post_data['image_enrichment'] = [first, second]
    ctx.search_results = [{'title':'외부 성인 만화','content':'정자 잔뜩 마셔','url':first['source_url']}]
    result = pipe._source_bound_image_nsfw_assessment(ctx)
    assert result['binding_status'] == 'BOUND' and result['evidence'] == []


@pytest.mark.parametrize('value', [False, True])
def test_model_boolean_precedence_keeps_fallback_unexecuted(value):
    _, _, _, payload, observation = serialize_record(image_record(value), images=[positive_image()])
    proof = observation['nsfw_content_observation']
    assert payload['analysis']['is_nsfw'] is value
    assert payload['analysis']['nsfw_assessment_status'] == 'MODEL_REPORTED'
    assert payload['analysis']['nsfw_assessment_reason'] == 'MODEL_BOOLEAN_REPORTED'
    assert proof['image_assessment']['fallback_executed'] is False
    assert proof['image_assessment']['status'] == 'NOT_RUN_MODEL_BOOLEAN_PRESENT'


@pytest.mark.parametrize('fast_path', [False, True])
def test_actual_noise_final_message_and_fast_path_placeholder_preserve_unassessed_reason(saved, fast_path):
    pipe, ctx, _ = prepared(saved, 49, inject=False)
    ctx.post_data['image_enrichment'][0].update(ocr_text='', visual_summary='일반 풍경 사진이다.')
    pipe._inject_image_enrichment_blocks(ctx.post_data)
    content = {'decision':'noise','reason':'작품과 무관한 이미지'}
    if fast_path:
        content['fast_path'] = True
        ctx.set_expert_output(ExpertType.ARBITER, {'final_decision':{'is_relevant':False,
            'official_novel_title':None,'discussion_type':'noise','confidence':'High'},
            'final_reasoning':'Fast-Path 판정: 작품과 무관한 이미지','metadata_synthesis':{}})
    ctx.add_message(ExpertMessage(from_expert=ExpertType.GATEKEEPER, to_expert=None,
        message_type='final', content=content))
    output = pipe._context_to_output(ctx)
    payload = output.model_dump(mode='json')
    observation = pipe.verify_final_source_context_serialization(output, payload, stage='noise_reason')
    assert payload['analysis']['is_nsfw'] is False
    assert payload['analysis']['nsfw_assessment_status'] == 'NOT_EVALUATED'
    assert payload['analysis']['nsfw_assessment_reason'] == 'NOISE_EARLY_RETURN_NO_MODEL_ASSESSMENT'
    assert observation['nsfw_content_observation']['model_assessment']['noise_early_return_observed'] is True
    assert observation['nsfw_content_observation']['image_assessment']['requires_image_review'] is True
    if fast_path:
        assert ctx.get_expert_output(ExpertType.ARBITER)['metadata_synthesis'] == {}
    else:
        assert ctx.get_expert_output(ExpertType.ARBITER) is None


@pytest.mark.parametrize('field', ['ocr_text', 'visual_summary', 'source_url', 'block_index'])
def test_post_seal_image_evidence_changes_are_rejected(saved, field):
    pipe, ctx, _ = prepared(saved, 49)
    output = pipe._context_to_output(ctx)
    payload = output.model_dump(mode='json')
    pipe.verify_final_source_context_serialization(output, payload, stage='before_tamper')
    item = ctx.post_data['image_enrichment'][0]
    item[field] = item[field] + 1 if field == 'block_index' else item[field] + ' changed'
    with pytest.raises(ValueError):
        pipe.verify_final_source_context_serialization(output, payload, stage='after_image_tamper')
