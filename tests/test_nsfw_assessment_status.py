"""NSFW bool과 평가 상태를 실제 serializer/main/WAL에서 검산한다. 픽셀 정답 시험이 아니다."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import PickvelAnalysis, PickvelOutputItemV2
from llm_batch.experts.orchestrator import ExpertType
from llm_batch.ledger.publication_commit import (
    PublicationCommitRegistry, build_publication_scope_descriptor, commit_publication_result,
)
from test_final_source_context_explanation import consume
from test_source_bound_nsfw import context_for, wrapper_class, FIXTURE as FIXTURE74


FIXTURE49 = Path(__file__).parent / 'fixtures/actual80_nsfw49_saved_experts.json'
MISSING = object()
STATUSES = ('MODEL_REPORTED', 'SOURCE_RULE_POSITIVE', 'NOT_EVALUATED')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def record_for(value=MISSING, *, title='내용을 묻는 글', body='이 표현의 의미가 궁금하다.'):
    record = deepcopy(json.loads(FIXTURE74.read_text(encoding='utf-8'))['records']['new'])
    record['post']['title'] = title
    record['post']['content_blocks'] = [{'type': 'text', 'text': body}]
    record['comments'] = []
    metadata = record['experts']['arbiter']['metadata_synthesis']
    metadata.pop('is_nsfw', None)
    if value is not MISSING:
        metadata['is_nsfw'] = value
    return record


def serialize_record(record, *, images=None):
    record_before = canonical(record)
    pipe, ctx, _ = context_for(record_override=record)
    if images is not None:
        ctx.post_data['image_enrichment'] = deepcopy(images)
    before = canonical({'post': ctx.post_data, 'comments': ctx.comments,
                        'original_inputs': ctx._final_source_original_inputs})
    output = pipe._context_to_output(ctx)
    payload = output.model_dump(mode='json')
    observation = pipe.verify_final_source_context_serialization(output, payload, stage='assessment_model_dump')
    assert canonical(record) == record_before
    assert canonical({'post': ctx.post_data, 'comments': ctx.comments,
                      'original_inputs': ctx._final_source_original_inputs}) == before
    assert payload['identity']['novel_identity'] is None
    assert payload['identity']['promotion_decision']['publish_allowed'] is False
    assert payload['analysis'] is not None
    return pipe, ctx, output, payload, observation


def assert_pair(payload, observation, value, status):
    assert payload['analysis']['is_nsfw'] is value
    assert payload['analysis']['nsfw_assessment_status'] == status
    proof = observation['nsfw_content_observation']
    assert proof['schema_version'] == 'source_bound_nsfw_v2'
    assert proof['resolved_value'] is value and proof['assessment_status'] == status
    assert proof['publication_authority'] is False and proof['human_gold'] is False


@pytest.mark.parametrize('value', [False, True], ids=['explicit_false', 'explicit_true'])
def test_explicit_model_boolean_preserves_value_and_reports_only_model_scope(value):
    _, _, _, payload, observation = serialize_record(record_for(value))
    assert_pair(payload, observation, value, 'MODEL_REPORTED')
    assert observation['nsfw_content_observation']['arbiter_status'] == 'BOOLEAN'


@pytest.mark.parametrize('value', [MISSING, None, 'false', 'true', '', 0, 1, [], {}],
                         ids=['missing', 'null', 'false_string', 'true_string', 'empty_string', 'zero', 'one', 'list', 'dict'])
def test_missing_or_invalid_model_value_is_not_evaluated_without_positive_rule(value):
    _, _, _, payload, observation = serialize_record(record_for(value))
    assert_pair(payload, observation, False, 'NOT_EVALUATED')
    assert observation['nsfw_content_observation']['arbiter_status'] == ('MISSING' if value is MISSING else 'INVALID_TYPE')
    assert observation['nsfw_content_observation']['arbiter_value'] is None


@pytest.mark.parametrize('value', [MISSING, None, 'false', 1], ids=['missing', 'null', 'string', 'integer'])
def test_existing_direct_post_positive_is_rule_reported_for_missing_or_invalid_model(value):
    record = record_for(value, title='섹스 장면 보고 꼴려', body='그 장면에 대한 감상이다.')
    pipe, ctx, output, payload, observation = serialize_record(record)
    assert pipe._fallback_explicit_nsfw_from_post(ctx) is True
    assert_pair(payload, observation, True, 'SOURCE_RULE_POSITIVE')
    assert observation['nsfw_content_observation']['arbiter_value'] is None
    # 원문은 그대로이고 fallback 관측을 바꾼 뒤 기존 봉인을 계속 쓰는 것은 거절한다.
    ctx.post_data['title'] = '다른 원문'
    with pytest.raises(ValueError, match='native verification failed'):
        pipe.verify_final_source_context_serialization(output, payload, stage='source_mutated')


def image_record(value=MISSING):
    record = record_for(value, title='이 그림이 무엇인지 궁금하다', body='')
    record['post']['content_blocks'] = [{'type': 'image', 'url': 'https://fixture.invalid/one-image.png'}]
    return record


def positive_image():
    return {'block_index': 0, 'source_url': 'https://fixture.invalid/one-image.png',
            'ocr_text': '정자 잔뜩 마셔', 'visual_summary': '성적 장면을 묘사한 이미지'}


@pytest.mark.parametrize('value,expected,status', [(MISSING, True, 'SOURCE_RULE_POSITIVE'),
    (False, False, 'MODEL_REPORTED'), (True, True, 'MODEL_REPORTED')],
    ids=['missing_rule_positive', 'explicit_false_preserved', 'explicit_true_preserved'])
def test_existing_same_image_fallback_and_model_boolean_precedence(value, expected, status):
    _, _, _, payload, observation = serialize_record(image_record(value), images=[positive_image()])
    assert_pair(payload, observation, expected, status)


def test_different_images_cannot_complete_existing_positive_rule():
    first = positive_image()
    first['visual_summary'] = '작품명을 묻는 그림'
    second = dict(positive_image(), block_index=1, source_url='https://fixture.invalid/second.png', ocr_text='')
    record = image_record()
    record['post']['content_blocks'].append({'type':'image', 'url':second['source_url']})
    _, _, _, payload, observation = serialize_record(record, images=[first, second])
    assert_pair(payload, observation, False, 'NOT_EVALUATED')


def test_actual74_source_override_remains_true_and_records_rule_scope():
    record = json.loads(FIXTURE74.read_text(encoding='utf-8'))['records']['new']
    assert record['experts']['arbiter']['metadata_synthesis']['is_nsfw'] is False
    _, _, _, payload, observation = serialize_record(record)
    assert_pair(payload, observation, True, 'SOURCE_RULE_POSITIVE')
    assert observation['nsfw_content_observation']['status'] == 'SOURCE_CONFLICT_RESOLVED_TRUE'
    assert observation['nsfw_content_observation']['evidence'][0]['raw_path'] == '/comments/4/content'


def test_actual49_saved_projection_without_arbiter_is_source_positive_with_bound_image(tmp_path):
    before = FIXTURE49.read_bytes()
    fixture = json.loads(before)
    record = fixture['records']['actual49']
    assert record['post']['post_id'] == 9788827
    assert 'arbiter' not in record['experts']
    images = fixture['stored_image_projection']['image_evidence_catalog']
    assert len(images) == 1
    image = images[0]
    block = record['post']['content_blocks'][image['block_index']]
    assert block['type'] == 'image' and block['url'] == image['source_url']
    assert '성인용 만화' in image['visual_summary']
    assert '정자' in image['ocr_text']
    # 공개 catalog에 남은 같은 이미지의 관측만 재주입한다. 전체 VLM context 복원이 아니다.
    pipe, ctx, output, payload, observation = serialize_record(record, images=images)
    assert_pair(payload, observation, True, 'SOURCE_RULE_POSITIVE')
    assert payload['analysis']['nsfw_assessment_reason'] == 'SOURCE_IMAGE_RULE_POSITIVE'
    assert observation['nsfw_content_observation']['arbiter_status'] == 'MISSING'
    row = dict(ctx.post_data, comments=deepcopy(record['comments']), analysis_result=payload)
    wrapped = wrapper_class()(row, output=output, verifier=pipe.verify_final_source_context_serialization)
    scope = build_publication_scope_descriptor(input_file_sha256=hashlib.sha256(canonical(record['post']).encode()).hexdigest(),
        post_ids=[ctx.post_id], config_hash='actual49-partial-context', release_fingerprint='local-candidate-only')
    path = tmp_path / 'actual49-local.jsonl'
    registry = PublicationCommitRegistry(path, scope_descriptor=scope, create_new=True)
    commit, created = commit_publication_result(wrapped, registry=registry,
        attempt_run_id='actual49-partial', input_index=1, post_id=ctx.post_id)
    assert created and commit.outcome == 'HOLD' and commit.publish_allowed is False
    stored = PublicationCommitRegistry(path, scope_descriptor=scope, create_new=False).result(ctx.post_id)
    assert stored['analysis_result'] == payload
    wrapped.verify_stored_payload(stored, stage='actual49_partial_context_wal')
    forged = deepcopy(stored)
    forged['analysis_result']['analysis']['nsfw_assessment_status'] = 'MODEL_REPORTED'
    with pytest.raises(ValueError, match='NSFW assessment serialization changed'):
        wrapped.verify_stored_payload(forged, stage='actual49_false_assessment_claim')
    assert FIXTURE49.read_bytes() == before


@pytest.mark.parametrize('value,status', [(False, 'MODEL_REPORTED'), (MISSING, 'NOT_EVALUATED')],
                         ids=['reported_false', 'missing_false'])
def test_status_and_boolean_survive_main_wrapper_wal_and_reject_mutations(tmp_path, value, status):
    pipe, ctx, output, payload, observation = serialize_record(record_for(value))
    assert_pair(payload, observation, False, status)
    row = dict(ctx.post_data, comments=list(ctx.comments), analysis_result=payload)
    wrapped = wrapper_class()(row, output=output, verifier=pipe.verify_final_source_context_serialization)
    scope = build_publication_scope_descriptor(input_file_sha256=hashlib.sha256(canonical(ctx.post_data).encode()).hexdigest(),
        post_ids=[ctx.post_id], config_hash='assessment-test', release_fingerprint='synthetic-local-only')
    path = tmp_path / 'assessment.jsonl'
    registry = PublicationCommitRegistry(path, scope_descriptor=scope, create_new=True)
    commit, created = commit_publication_result(wrapped, registry=registry,
        attempt_run_id='assessment', input_index=1, post_id=ctx.post_id)
    assert created and commit.outcome == 'HOLD' and commit.publish_allowed is False
    reopened = PublicationCommitRegistry(path, scope_descriptor=scope, create_new=False)
    stored = reopened.result(ctx.post_id)
    assert stored['analysis_result'] == payload
    wrapped.verify_stored_payload(stored, stage='assessment_wal_readback')
    wal_before = path.read_bytes()
    for marker in (None, 'false', '', 0, False, [], {}, *[s for s in STATUSES if s != status], 'DELETE'):
        changed = deepcopy(stored)
        if marker == 'DELETE':
            del changed['analysis_result']['analysis']['nsfw_assessment_status']
        else:
            changed['analysis_result']['analysis']['nsfw_assessment_status'] = marker
        with pytest.raises(ValueError, match='NSFW assessment'):
            wrapped.verify_stored_payload(changed, stage='assessment_field_tamper')
    changed = deepcopy(stored)
    changed['analysis_result']['analysis']['is_nsfw'] = True
    with pytest.raises(ValueError, match='NSFW source-bound serialization changed'):
        wrapped.verify_stored_payload(changed, stage='assessment_bool_tamper')
    assert path.read_bytes() == wal_before
    output.analysis.nsfw_assessment_status = None
    with pytest.raises(ValueError, match='NSFW assessment'):
        pipe.verify_final_source_context_serialization(output, payload, stage='assessment_model_tamper')


@pytest.mark.parametrize('legacy_nsfw_seal', [False, True], ids=['pre_nsfw_receipt', 'v1_nsfw_receipt'])
def test_legacy_receipt_and_field_seal_do_not_require_new_optional_status(legacy_nsfw_seal):
    # 실제 source 소비/검산으로 만든 context에 과거 구조의 output/receipt를 붙인다.
    # v1 결정문 fixture는 false 값의 과거 wire 구조만 검산하며 의미 판정을 대신하지 않는다.
    pipe, ctx, identity, notes, verify = consume('전개 감상', '생각보다 적수를 빨리 죽이고',
        '무리를 일망타진한게 의외였음', '작가가 큰판을 보여줘서 좋구나')
    assert verify() is True
    output = PickvelOutputItemV2(post_id=ctx.post_id, identity=identity,
        analysis=PickvelAnalysis(notes=notes, is_nsfw=False))
    for name, val in {
        '_final_source_context_owner': ctx,
        '_final_source_context_native': ctx._final_source_projection_native,
        '_final_source_context_original_entities': ctx._final_source_original_entities,
        '_final_source_context_consumption': ctx._final_source_projection_consumption,
    }.items():
        object.__setattr__(output, name, val)
    if legacy_nsfw_seal:
        old_decision = {'schema_version':'source_bound_nsfw_v1', 'post_id':ctx.post_id,
            'resolved_value':False, 'arbiter_status':'BOOLEAN', 'arbiter_value':False,
            'status':'NO_APPLICABLE_SOURCE_RULE', 'evidence':[], 'publication_authority':False}
        object.__setattr__(output, '_source_bound_nsfw_decision_seal', canonical(old_decision))
    pipe._attach_final_source_serialization_receipt(output, native_verifier=verify)
    assert 'nsfw_serialized_assessment' not in output.__dict__['_final_source_context_receipt']
    payload = output.model_dump(mode='json')
    assert payload['analysis']['nsfw_assessment_status'] is None
    old_payload = deepcopy(payload)
    del old_payload['analysis']['nsfw_assessment_status']
    assert pipe._final_source_serialization_seal(old_payload) == pipe._final_source_serialization_seal(payload)
    pipe.verify_final_source_context_serialization(output, old_payload, stage='legacy_missing_status')
    assert PickvelAnalysis.model_validate(old_payload['analysis']).nsfw_assessment_status is None


def test_optional_typed_status_and_analysis_none_boundary():
    assert PickvelAnalysis(is_nsfw=False).nsfw_assessment_status is None
    for value in ('UNKNOWN', 'false', True, 1, {}, []):
        with pytest.raises(ValidationError):
            PickvelAnalysis(nsfw_assessment_status=value)
    assert AgenticPipeline._source_bound_nsfw_serialized_assessment({'analysis':None}) is None
    assert AgenticPipeline._source_bound_nsfw_serialized_value({'analysis':None}) is None
