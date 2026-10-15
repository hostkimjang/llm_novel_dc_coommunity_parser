"""55번 저장 관측의 부분 context 및 좁은 상태 동기화. 새 모델/검색·의미 gold 없음."""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

import pytest

from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import PostInput
from llm_batch.experts.orchestrator import ConversationContext, ExpertType
from llm_batch.ledger.publication_commit import (
    PublicationCommitRegistry, build_publication_scope_descriptor, commit_publication_result,
)
from llm_batch import promotion_gate
from llm_batch.grounding.candidate_audit import apply_candidate_audit_fields, has_authoritative_publish_contract

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).parent / 'fixtures/actual80_run191128_semantic55_saved_experts.json'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


class NoExternal:
    def __getattr__(self, name):
        def forbidden(*args, **kwargs):
            raise AssertionError('NEW_MODEL_SEARCH_FETCH_FORBIDDEN:' + name)
        return forbidden


def context(tmp_path, *, label='current', mutate=None, capture=True):
    fixture = json.loads(FIXTURE.read_bytes())
    assert fixture['scope'] == 'SAVED_EXPERTS_PARTIAL_CONTEXT_NOT_ORIGINAL_MEMORY_CONTEXT'
    packet = fixture['packet']
    assert digest({'post': packet['source_post'], 'comments': packet['source_comments']}) == fixture['source_canonical_sha256']
    assert digest(packet['checkpoint_result']) == fixture['result_canonical_sha256']
    stream = fixture['expert_stream'] if label == 'current' else fixture['prior_expert_stream']
    row = copy.deepcopy(fixture['records'][label])
    assert row['experts'] == {x['expert']: x['value'] for x in stream}
    if mutate:
        mutate(row)
    post = PostInput(**row['post'], comments=row['comments'])
    pipe = AgenticPipeline(llm=NoExternal(), mcp=NoExternal(), output_dir=tmp_path,
        max_iterations=1, native_recovery=True)
    pipe.enable_url_fetch_disk_cache = False
    pipe._use_session_knowledge = False
    ctx = ConversationContext(post_id=post.post_id, post_data=pipe._post_to_dict(post), comments=pipe._extract_comments(post))
    if capture:
        ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(post)
        ctx._final_source_original_comment_refs = tuple(post.comments)
        ctx._source_bound_nsfw_original_carrier = pipe._capture_source_bound_nsfw_carrier(post)
    for name, value in row['experts'].items():
        ctx.set_expert_output(ExpertType(name), copy.deepcopy(value))
    # 원래 메모리 context를 발명하지 않는다. 실제 보존된 producer 메타데이터만 복사한다.
    stored = packet['checkpoint_result'] if label == 'current' else fixture['prior_packet']['old_result']
    ledger = stored['analysis_result']['identity']['candidate_ledger']
    for attr, key in (('_candidate_producer_plans', 'candidate_producer_plans'),
            ('_candidate_producer_receipts', 'candidate_producer_receipts'),
            ('_candidate_generation_stage_receipts', 'candidate_stage_receipts')):
        setattr(ctx, attr, copy.deepcopy(ledger.get(key, [])))
    discourse = row['experts']['discourse']['discourse_analysis']
    ctx.primary_domain = discourse.get('primary_domain')
    ctx.discourse_intent = discourse.get('intent')
    return pipe, ctx, fixture


def inputs(ctx):
    return (ctx.get_expert_output(ExpertType.VERIFIER)['verification_result'],
        ctx.get_expert_output(ExpertType.ARBITER)['final_decision'])


def scope(pipe, ctx, *, flags=('unresolved_nonwork_overlap_demoted',)):
    vr, fd = inputs(ctx)
    return pipe._derive_resolution_scope_fields(ctx=ctx, is_relevant=False, official_title=None,
        discussion_type='noise', topicality='unrelated', subtype='other_quarantine', work_resolution='none',
        verification_result=vr, final_decision=fd, final_nonwork_flags=flags)


def serialize(pipe, ctx):
    source_before = canonical({'post': ctx.post_data, 'comments': ctx.comments})
    result = pipe._context_to_output(ctx)
    payload = result.model_dump(mode='json')
    pipe.verify_final_source_context_serialization(result, payload, stage='surface_title_saved_context')
    assert canonical({'post': ctx.post_data, 'comments': ctx.comments}) == source_before
    assert ctx._final_source_projection_call_count == 1
    return result, payload


def wrapper_class():
    tree = ast.parse((ROOT / 'expert_main.py').read_text(encoding='utf8'))
    node = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == '_FinalSourceContextResult')
    namespace = {'Any': Any, 'Dict': Dict, 'Mapping': Mapping}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(ROOT / 'expert_main.py'), 'exec'), namespace)
    return namespace['_FinalSourceContextResult']



def synchronize_like_actual_main(payload, post):
    # CLI startup 자체를 실행하지 않고 정규 _process_one이 쓰는 진입점/typed 분기를 그대로 쓴다.
    # legacy guard를 대체하거나 성공을 반환하는 mock은 두지 않는다.
    tree = ast.parse((ROOT / 'expert_main.py').read_text(encoding='utf8'))
    names = {'_runtime_candidate_audit_seed', '_sync_final_publication_ledger_contract', '_reapply_authoritative_publish_contract',
        '_sync_analysis_notes_to_final_publication', '_sync_reader_explanation_to_publish_contract'}
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in selected} == names
    promotion_names = ('PUBLISH_CONTRACT_VERSION', 'candidate_inventory_evidence_from_sources',
        'candidate_inventory_pairs', 'candidate_inventory_records', 'EvidenceRecord', 'GroundingState',
        'ScopeState', 'apply_publish_contract', 'build_publish_ledger', 'evaluate_publish_contract',
        'evidence_records_from_payload', 'grounding_state_from_dict')
    namespace = {name: getattr(promotion_gate, name) for name in promotion_names}
    namespace.update(Any=Any, Dict=Dict, Callable=Callable, Optional=Optional, json=json, re=re)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(ROOT / 'expert_main.py'), 'exec'), namespace)
    identity = payload['identity']
    assert has_authoritative_publish_contract(identity) is True
    audit_seed = namespace['_runtime_candidate_audit_seed'](identity, None)
    assert audit_seed is None
    apply_candidate_audit_fields(identity, audit_seed)
    sync_payload = dict(payload)
    sync_payload.update(title=post['title'], content=[item['text'] for item in post['content_blocks']],
        comments=list(post.get('comments_raw') or []), comment_context_lines=[],
        comment_dialogue_context_lines=[], _loop_projection_followup=None)
    return namespace['_sync_final_publication_ledger_contract'](sync_payload, post_title=post['title'])


def test_actual55_partial_context_scope_native_wrapper_wal(tmp_path):
    fixture_before = FIXTURE.read_bytes()
    pipe, ctx, fixture = context(tmp_path)
    code = fixture['baseline_scope_function']['source']
    assert hashlib.sha256(code.encode()).hexdigest() == fixture['baseline_scope_function']['sha256']
    namespace = dict(AgenticPipeline._derive_resolution_scope_fields.__globals__)
    exec(compile(ast.parse(code), 'pinned_pre_fix_surface_title_scope', 'exec'), namespace)
    vr, fd = inputs(ctx)
    baseline = namespace['_derive_resolution_scope_fields'](pipe, ctx=ctx, is_relevant=False,
        official_title=None, discussion_type='noise', topicality='unrelated', subtype='other_quarantine',
        work_resolution='none', verification_result=vr, final_decision=fd)
    assert baseline['title_resolution_state'] == 'unresolved_matchable' and baseline['is_novel_related'] is True
    output, payload = serialize(pipe, ctx)
    identity = payload['identity']
    assert (identity['discussion_type'], identity['subtype'], identity['topicality'], identity['work_resolution']) == (
        'noise', 'other_quarantine', 'unrelated', 'none')
    assert identity['title_resolution_state'] == 'context_only'
    assert identity['is_novel_related'] is False and identity['is_relevant'] is False
    assert identity['novel_identity'] is None and identity['title_resolution_allowed'] is False
    assert payload['analysis']['is_nsfw'] is False and payload['analysis']['nsfw_assessment_status'] == 'MODEL_REPORTED'
    assert '장수풍뎅이vs사슴벌레' in payload['analysis']['notes']
    binding = ctx._surface_title_anchor_evidence
    assert binding['verify']() is True
    assert binding['publication_authority'] is False and binding['source_semantic_proof'] is False
    assert binding['candidate_completeness_claimed'] is False
    native = ctx._final_source_projection_native
    assert native.state.is_novel_related is False
    assert native.projection.fallback is True  # 기존 의미 미지원이 성공으로 승격되지 않는다.
    contract = ctx._last_publish_contract
    assert contract.state.title_resolution_state == 'context_only'
    assert contract.decision.publish_allowed is False and contract.decision.bypassed_gate is False
    assert identity['publish_contract_input_fingerprint'] == contract.input_fingerprint
    assert identity['candidate_ledger']['publish_contract_input_fingerprint'] == contract.input_fingerprint
    assert identity['candidate_ledger']['title_resolution_state'] == 'context_only'
    # 첫 typed writer의 bool을 모델과 원장이 동일하게 전달해야 한다. None/0을 정규화하지 않는다.
    for key in ('promotion_blocked', 'hold_without_candidates', 'safe_resolved'):
        expected = contract.trace.post_gate_identity.candidate_ledger_status == key
        assert type(identity[key]) is bool and identity[key] is expected
        assert identity[key] is identity['candidate_ledger'][key]
    old = fixture['packet']['checkpoint_result']['analysis_result']['identity']['candidate_ledger']
    for name in ('candidate_generation', 'candidate_generation_proof'):
        assert identity['candidate_ledger'][name]['status'] == old[name]['status']
    wrapper = wrapper_class()
    assert identity['publish_contract_version'] == promotion_gate.PUBLISH_CONTRACT_VERSION
    bound_before = pipe._surface_title_anchor_serialization_seal(payload)
    decision_before = copy.deepcopy(identity['promotion_decision'])
    trace_before = copy.deepcopy(identity['publish_contract_trace'])
    synchronize_like_actual_main(payload, ctx.post_data)
    assert identity['promotion_decision'] == decision_before == contract.decision.to_dict()
    assert identity['publish_contract_trace'] == trace_before == contract.trace.to_dict()
    assert 'publish_contract_integrity_error' not in identity
    assert identity['novel_identity'] == {'official_title': None, 'heretic_url': None}
    assert output.identity.novel_identity is None
    assert pipe._surface_title_anchor_serialization_seal(payload) == bound_before
    pipe.verify_final_source_context_serialization(output, payload, stage='surface_title_after_actual_main_typed_sync')
    row = dict(ctx.post_data, comments=list(ctx.comments), analysis_result=payload)
    wrapped = wrapper(row, output=output, verifier=pipe.verify_final_source_context_serialization)
    descriptor = build_publication_scope_descriptor(input_file_sha256=digest(ctx.post_data),
        post_ids=[ctx.post_id], config_hash='surface-anchor-partial-context', release_fingerprint='candidate-only')
    path = tmp_path / 'publication.jsonl'
    registry = PublicationCommitRegistry(path, scope_descriptor=descriptor, create_new=True)
    wrapped.verify_stored_payload(wrapped, stage='surface_title_precommit')
    commit, created = commit_publication_result(wrapped, registry=registry,
        attempt_run_id='surface-title-saved-context', input_index=1, post_id=ctx.post_id)
    assert created and commit.outcome == 'HOLD' and commit.publish_allowed is False
    reopened = PublicationCommitRegistry(path, scope_descriptor=descriptor, create_new=False)
    stored = reopened.result(ctx.post_id)
    assert stored['analysis_result'] == payload
    wrapped.verify_stored_payload(stored, stage='surface_title_wal_readback')
    changed = copy.deepcopy(stored)
    changed['analysis_result']['identity']['title_resolution_state'] = 'unresolved_matchable'
    wal_before = path.read_bytes()
    with pytest.raises(ValueError):
        wrapped.verify_stored_payload(changed, stage='surface_title_wal_tamper')
    assert path.read_bytes() == wal_before and FIXTURE.read_bytes() == fixture_before


def test_prior_anchor_none_remains_existing_path_without_optional_receipt(tmp_path):
    pipe, ctx, _ = context(tmp_path, label='prior')
    assert scope(pipe, ctx)['title_resolution_state'] == 'context_only'
    assert ctx.__dict__.get('_surface_title_anchor_evidence') is None
    output, payload = serialize(pipe, ctx)
    assert payload['identity']['title_resolution_state'] == 'context_only'
    assert 'surface_title_anchor_binding' not in output._final_source_context_receipt
    # 비해당 기존 경로도 이미 적용한 typed writer의 세 상태 bool을 생성자에서 잃지 않는다.
    identity = payload['identity']
    contract = ctx._last_publish_contract
    flags_before = {}
    for key in ('promotion_blocked', 'hold_without_candidates', 'safe_resolved'):
        expected = contract.trace.post_gate_identity.candidate_ledger_status == key
        assert type(identity[key]) is bool and identity[key] is expected
        assert identity[key] is identity['candidate_ledger'][key]
        flags_before[key] = identity[key]
    synchronize_like_actual_main(payload, ctx.post_data)
    assert {key: identity[key] for key in flags_before} == flags_before
    pipe.verify_final_source_context_serialization(output, payload, stage='prior_no_optional_surface_main_sync')


@pytest.mark.parametrize('owner,field,value', [
    (owner, field, value) for owner in ('verifier', 'arbiter')
    for field in ('is_relevant', 'is_novel_discussion') for value in (None, 'false', 0, True)])
def test_four_negative_fields_require_actual_false(tmp_path, owner, field, value):
    pipe, ctx, _ = context(tmp_path)
    vr, fd = inputs(ctx)
    (vr if owner == 'verifier' else fd)[field] = value
    assert pipe._source_bound_surface_title_anchor(ctx, vr, fd) is None


@pytest.mark.parametrize('change', ['carrier_missing', 'carrier_title', 'source_title', 'body', 'comment',
    'image', 'content_alias', 'original_path', 'foreign_verifier', 'foreign_arbiter',
    'novel_secondary', 'gk_character', 'gk_extra_title', 'recommendation1', 'recommendation2',
    'decoder_high', 'candidate_url', 'verified_character', 'known_alias', 'official_detail', 'wrong_anchor'])
def test_source_and_competing_evidence_reject_new_exception(tmp_path, change):
    pipe, ctx, _ = context(tmp_path)
    vr, fd = inputs(ctx)
    gate = ctx.get_expert_output(ExpertType.GATEKEEPER)
    discourse = ctx.get_expert_output(ExpertType.DISCOURSE)['discourse_analysis']
    term = ctx.get_expert_output(ExpertType.DECODER)['decoded_terms'][0]
    if change == 'carrier_missing': del ctx._source_bound_nsfw_original_carrier
    elif change == 'carrier_title':
        carrier = json.loads(ctx._source_bound_nsfw_original_carrier); carrier['title'] += '다른 원문'
        ctx._source_bound_nsfw_original_carrier = canonical(carrier).decode()
    elif change == 'source_title': ctx.post_data['title'] += '다른 원문'
    elif change == 'body': ctx.post_data['content_blocks'][0]['text'] = '아생갤은 아카데미 생존 갤러리의 약칭이다.'
    elif change == 'comment': ctx.comments = ['이 소설 추천함']
    elif change == 'image': ctx.post_data['content_blocks'].append({'type':'image','url':'https://example.invalid/image.png'})
    elif change == 'content_alias': ctx.post_data['content'] = '김작가 신작 추천'
    elif change == 'original_path': ctx._final_source_original_inputs[0]['raw_path'] = '/foreign'
    elif change == 'foreign_verifier': vr = copy.deepcopy(vr)
    elif change == 'foreign_arbiter': fd = copy.deepcopy(fd)
    elif change == 'novel_secondary': discourse['secondary_domains'] = ['novel_literature']
    elif change == 'gk_character': gate['detected_entities']['possible_characters'] = ['인물']
    elif change == 'gk_extra_title': gate['detected_entities']['possible_titles'].append('경쟁 작품')
    elif change.startswith('recommendation'): gate['context_clues'][
        'is_recommendation_request' if change.endswith('1') else 'is_asking_recommendation'] = True
    elif change == 'decoder_high': term['interpretations'][1]['context_fit'] = 'high'
    elif change == 'candidate_url': term['candidates'][0]['url'] = 'https://novel.munpia.com/123'
    elif change == 'verified_character':
        # 기존 rework 시험에서 쓰는 구체적 인물 연결 형태다. 외부 사실의 새 검증을 뜻하지 않는다.
        # 이전 '특정인물' 가상 표면은 generic guard가 거절하므로 강한 근거 반례가 아니었다.
        ctx.verified_character_work_links = [{'character':'밤도깨비 에이브', 'title':'도깨비가 되었다.',
            'url':'https://novelpia.com/novel/175153'}]
        assert pipe._has_strong_verified_character_work_links(ctx) is True
    elif change == 'known_alias':
        def mutate(row):
            title = '아생갤vs사슴벌레'; row['post']['title'] = title
            row['experts']['gatekeeper']['detected_entities']['possible_titles'] = [title]
            row['experts']['gatekeeper']['context_clues']['short_post_title_surface'] = title
            row['experts']['verifier']['verification_result']['grounding_check']['anchor_text'] = title
            row['experts']['decoder']['decoded_terms'][0]['original'] = title
        pipe, ctx, _ = context(tmp_path, mutate=mutate); vr, fd = inputs(ctx)
    elif change == 'official_detail': ctx.search_results = [{'title':ctx.post_data['title'],
        'url':'https://novel.munpia.com/123', 'content':'독립 공식 상세 관측'}]
    elif change == 'wrong_anchor': vr['grounding_check']['anchor_text'] = '사슴벌레'
    assert pipe._source_bound_surface_title_anchor(ctx, vr, fd) is None


def test_existing_adopted_nonwork_flag_is_required(tmp_path):
    pipe, ctx, _ = context(tmp_path)
    assert scope(pipe, ctx, flags=())['title_resolution_state'] == 'unresolved_matchable'
    assert ctx.__dict__.get('_surface_title_anchor_evidence') is None


def test_plain_comparison_scope_is_not_hardcoded_to_actual55_title(tmp_path):
    def mutate(row):
        title = '사과vs배'
        row['post']['title'] = title
        row['experts']['gatekeeper']['detected_entities']['possible_titles'] = [title]
        row['experts']['gatekeeper']['context_clues']['short_post_title_surface'] = title
        row['experts']['verifier']['verification_result']['grounding_check']['anchor_text'] = title
        row['experts']['decoder']['decoded_terms'][0]['original'] = title
    pipe, ctx, _ = context(tmp_path, mutate=mutate)
    # 명시 합성 입력의 국소 결속 시험. 저장55의 모델 자유문을 새 과일 의미 정답으로 쓰지 않는다.
    assert scope(pipe, ctx)['title_resolution_state'] == 'context_only'
    assert ctx._surface_title_anchor_evidence['source_semantic_proof'] is False


@pytest.mark.parametrize('body,comments,extra_block', [
    ('김작가 신작을 기다린다.', [], None),
    ('이런 소설을 추천해 주세요.', [], None),
    ('예전에 읽은 작품 제목을 찾습니다.', [], None),
    ('아생갤은 아카데미 생존 갤러리의 약칭이다.', [], None),
    ('- dc official App', ['이 작품의 인물이다.'], None),
    ('- dc official App', [], {'type':'image', 'url':'https://example.invalid/ocr.png'}),
])
def test_legitimately_captured_competing_originals_cannot_use_surface_only_scope(tmp_path, body, comments, extra_block):
    def mutate(row):
        row['post']['content_blocks'] = [{'type':'text', 'text':body}]
        if extra_block:
            row['post']['content_blocks'].append(extra_block)
        row['comments'] = comments
    pipe, ctx, _ = context(tmp_path, mutate=mutate)
    # 원래 carrier부터 함께 바뀐 합성 반례다. 단순 ctx drift 검출만으로 통과한 시험이 아니다.
    assert pipe._source_bound_surface_title_anchor(ctx, *inputs(ctx)) is None
    scope(pipe, ctx)
    assert ctx.__dict__.get('_surface_title_anchor_evidence') is None


@pytest.fixture
def serialized(tmp_path):
    pipe, ctx, _ = context(tmp_path)
    output, payload = serialize(pipe, ctx)
    return pipe, ctx, output, payload


@pytest.mark.parametrize('location,value', [('state','unresolved_matchable'), ('broad',True), ('broad',0),
    ('allowed',0), ('fingerprint','foreign'), ('ledger_fingerprint','foreign'), ('trace_fingerprint','foreign'),
    ('decision_publish',True), ('novel',{'official_title':'가짜 작품','heretic_url':None}), ('missing',None),
    ('promotion_blocked',None), ('hold_without_candidates',None), ('safe_resolved',None),
    ('promotion_blocked',0), ('hold_without_candidates',0), ('safe_resolved',0)])
def test_serialized_scope_and_contract_tampering_rejected(serialized, location, value):
    pipe, ctx, output, payload = serialized
    forged = copy.deepcopy(payload); identity = forged['identity']
    if location == 'state': identity['title_resolution_state'] = value
    elif location == 'broad': identity['is_novel_related'] = value
    elif location == 'allowed': identity['title_resolution_allowed'] = value
    elif location == 'fingerprint': identity['publish_contract_input_fingerprint'] = value
    elif location == 'ledger_fingerprint': identity['candidate_ledger']['publish_contract_input_fingerprint'] = value
    elif location == 'trace_fingerprint': identity['publish_contract_trace']['input_fingerprint'] = value
    elif location == 'decision_publish': identity['promotion_decision']['publish_allowed'] = value
    elif location == 'novel': identity['novel_identity'] = value
    elif location == 'missing': del identity['title_resolution_state']
    elif location in ('promotion_blocked', 'hold_without_candidates', 'safe_resolved'): identity[location] = value
    with pytest.raises(ValueError):
        pipe.verify_final_source_context_serialization(output, forged, stage='surface_title_payload_tamper')
    pipe.verify_final_source_context_serialization(output, payload, stage='surface_title_original_still_valid')


@pytest.mark.parametrize('change', ['model_broad','model_state','expert_object','expert_value','source',
    'native','contract_object','evidence_object'])
def test_same_call_objects_and_used_values_are_immutable(serialized, change):
    pipe, ctx, output, payload = serialized
    if change == 'model_broad': output.identity.is_novel_related = True
    elif change == 'model_state': output.identity.title_resolution_state = 'unresolved_matchable'
    elif change == 'expert_object': ctx.expert_outputs['verifier'] = copy.deepcopy(ctx.expert_outputs['verifier'])
    elif change == 'expert_value': inputs(ctx)[0]['grounding_check']['anchor_text'] = 'foreign'
    elif change == 'source': ctx.post_data['title'] = 'foreign'
    elif change == 'native': object.__setattr__(output, '_final_source_context_native', replace(ctx._final_source_projection_native))
    elif change == 'contract_object': ctx._last_publish_contract = replace(ctx._last_publish_contract)
    elif change == 'evidence_object': ctx._surface_title_anchor_evidence = dict(ctx._surface_title_anchor_evidence)
    with pytest.raises(ValueError):
        pipe.verify_final_source_context_serialization(output, payload, stage='surface_title_actual_object_tamper')


def test_actual_main_exact_null_pair_and_invalid_shapes_at_wrapper(serialized):
    pipe, ctx, output, payload = serialized
    synchronize_like_actual_main(payload, ctx.post_data)
    full = dict(ctx.post_data, analysis_result=payload)
    wrapped = wrapper_class()(full, output=output, verifier=pipe.verify_final_source_context_serialization)
    invalid = ({}, {'official_title': None}, {'official_title': None, 'heretic_url': None, 'author': None},
        {'official_title': '', 'heretic_url': None}, {'official_title': False, 'heretic_url': None},
        {'official_title': None, 'heretic_url': False},
        {'official_title': '근거 없는 작품', 'heretic_url': None},
        {'official_title': None, 'heretic_url': 'https://novelpia.com/novel/1'})
    for value in invalid:
        changed = copy.deepcopy(full)
        changed['analysis_result']['identity']['novel_identity'] = value
        with pytest.raises(ValueError, match='final source serialized fields changed'):
            wrapped.verify_stored_payload(changed, stage='surface_title_invalid_public_null_pair')
    changed = copy.deepcopy(full)
    del changed['analysis_result']['identity']['novel_identity']
    with pytest.raises(ValueError, match='final source serialized fields changed'):
        wrapped.verify_stored_payload(changed, stage='surface_title_missing_public_identity')
    wrapped.verify_stored_payload(full, stage='surface_title_unchanged_exact_null_pair')
