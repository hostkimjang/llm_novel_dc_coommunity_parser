"""233800 저장 전문가·카탈로그의 제한 재구성. 모델·외부 검색과 사람 정답을 만들지 않는다."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import PostInput
from llm_batch.experts.orchestrator import ConversationContext, ExpertType
from llm_batch.grounding.source_context_diagnostics import export_source_context_diagnostics, MAX_BYTES
from llm_batch.ledger.publication_commit import (
    PublicationCommitRegistry, build_publication_scope_descriptor, commit_publication_result,
)
from test_source_bound_propriety_question_state import (
    NoExternal, synchronize_like_actual_main, wrapper_class,
)

FIXTURE = Path(__file__).parent/'fixtures/actual80_run233800_scope_state_saved_experts.json'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def context(tmp_path, index=57):
    fixture = json.loads(FIXTURE.read_bytes())
    assert fixture['scope'] == 'SAVED_EXPERTS_AND_CATALOG_PARTIAL_CONTEXT_NOT_ORIGINAL_MEMORY'
    record = copy.deepcopy(fixture['rows'][str(index)])
    packet = record['packet']
    assert digest({'post':packet['source_post'], 'comments':packet['source_comments']}) == record['source_canonical_sha256']
    assert digest(packet['checkpoint_result']) == record['result_canonical_sha256']
    post = PostInput(**record['post'], comments=record['comments'])
    pipe = AgenticPipeline(llm=NoExternal(), mcp=NoExternal(), output_dir=tmp_path,
        max_iterations=1, native_recovery=True)
    pipe.enable_url_fetch_disk_cache = False
    pipe._use_session_knowledge = False
    ctx = ConversationContext(post_id=post.post_id, post_data=pipe._post_to_dict(post), comments=pipe._extract_comments(post))
    ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs = tuple(post.comments)
    ctx._source_bound_nsfw_original_carrier = pipe._capture_source_bound_nsfw_carrier(post)
    for name, value in record['experts'].items():
        ctx.set_expert_output(ExpertType(name), copy.deepcopy(value))
    # 저장된 카탈로그만 복원한다. 원래 full cache·batch memory·fetch 객체를 발명하지 않는다.
    ctx.search_results = copy.deepcopy(record['catalog'])
    ledger = packet['checkpoint_result']['analysis_result']['identity']['candidate_ledger']
    for attr, key in (('_candidate_producer_plans','candidate_producer_plans'),
            ('_candidate_producer_receipts','candidate_producer_receipts'),
            ('_candidate_generation_stage_receipts','candidate_stage_receipts')):
        setattr(ctx, attr, copy.deepcopy(ledger.get(key, [])))
    discourse = record['experts']['discourse']['discourse_analysis']
    ctx.primary_domain = discourse['primary_domain']
    ctx.discourse_intent = discourse['intent']
    return pipe, ctx, record


def serialize(pipe, ctx):
    before = canonical({'post':ctx.post_data, 'comments':ctx.comments})
    output = pipe._context_to_output(ctx)
    payload = output.model_dump(mode='json')
    pipe.verify_final_source_context_serialization(output, payload, stage='current_scope_state')
    assert canonical({'post':ctx.post_data, 'comments':ctx.comments}) == before
    assert ctx._final_source_projection_call_count == 1
    return output, payload


def call_scope_again(pipe, ctx, output):
    identity = output.identity.model_copy(deep=True)
    identity.title_resolution_state = 'unresolved_matchable'
    observations = ctx._final_source_discussion_observations
    return pipe._source_bound_propriety_question_scope(ctx, identity,
        ctx._final_source_projection_native, ctx._final_source_context_explanation,
        observations['records'], observations['comments'], publish_contract=ctx._last_publish_contract)


def test_current57_literal_anchor_same_native_real_main_wrapper_wal(tmp_path):
    fixture_before = FIXTURE.read_bytes()
    pipe, ctx, row = context(tmp_path)
    vr = ctx.get_expert_output(ExpertType.VERIFIER)['verification_result']
    original_ground = copy.deepcopy(vr['grounding_check'])
    assert original_ground['decoder_grounded'] is True
    assert original_ground['anchor_found'] == 'title_mention'
    assert original_ground['anchor_text'] == row['post']['title']
    output, payload = serialize(pipe, ctx)
    identity = payload['identity']
    assert vr['grounding_check'] == original_ground
    assert identity['is_novel_related'] is True and identity['is_relevant'] is False
    assert identity['discussion_type'] == 'noise' and identity['work_resolution'] == 'none'
    assert identity['title_resolution_state'] == 'context_only' and identity['title_resolution_allowed'] is False
    assert identity['novel_identity'] is None and identity['promotion_decision']['publish_allowed'] is False
    assert payload['analysis']['is_nsfw'] is True
    binding = ctx._propriety_question_scope_evidence
    assert binding['rule'] == 'current_author_propriety_question_literal_title_only_v1'
    assert binding['native'] is ctx._final_source_projection_native
    assert binding['verify']() is True and binding['publication_authority'] is False
    original_ledger = row['packet']['checkpoint_result']['analysis_result']['identity']['candidate_ledger']
    for field in ['candidate_generation','candidate_generation_proof']:
        assert identity['candidate_ledger'][field]['status'] == original_ledger[field]['status']
    diagnostics = export_source_context_diagnostics(output, enabled=True)
    by_gate = {x['gate']:x for x in diagnostics['scope_state_guards']}
    assert by_gate['propriety_question_scope']['status'] == 'ELIGIBLE'
    assert by_gate['propriety_callback']['status'] == 'APPLIED'
    assert by_gate['propriety_callback']['calls'] == 1
    assert all(x['publication_authority'] is False for x in by_gate.values())
    assert len(canonical(diagnostics)) <= MAX_BYTES
    before = copy.deepcopy(identity['promotion_decision'])
    synchronize_like_actual_main(payload, ctx.post_data)
    assert identity['promotion_decision'] == before
    assert identity['novel_identity'] == {'official_title':None, 'heretic_url':None}
    assert 'publish_contract_integrity_error' not in identity
    pipe.verify_final_source_context_serialization(output, payload, stage='current_after_main')
    full = dict(row['post'], comments=row['comments'], analysis_result=payload, run_meta={'local_test':True})
    wrapped = wrapper_class()(full, output=output, verifier=pipe.verify_final_source_context_serialization)
    descriptor = build_publication_scope_descriptor(input_file_sha256=row['source_canonical_sha256'],
        post_ids=[ctx.post_id], config_hash='literal-title-question-current', release_fingerprint='candidate-only')
    path = tmp_path/'publication.jsonl'
    registry = PublicationCommitRegistry(path, scope_descriptor=descriptor, create_new=True)
    commit, created = commit_publication_result(wrapped, registry=registry, attempt_run_id='current57-local',
        input_index=1, post_id=ctx.post_id)
    assert created and commit.outcome == 'HOLD' and commit.publish_allowed is False
    stored = PublicationCommitRegistry(path, scope_descriptor=descriptor, create_new=False).result(ctx.post_id)
    wrapped.verify_stored_payload(stored, stage='current_wal_readback')
    assert stored['analysis_result'] == payload
    assert FIXTURE.read_bytes() == fixture_before


def test_current55_old_surface_rejected_but_general_binding_applies_context_only(tmp_path):
    pipe, ctx, row = context(tmp_path, 55)
    vr = ctx.get_expert_output(ExpertType.VERIFIER)['verification_result']
    fd = ctx.get_expert_output(ExpertType.ARBITER)['final_decision']
    before = canonical({'vr':vr, 'fd':fd, 'decoder':ctx.get_expert_output(ExpertType.DECODER)})
    assert pipe._surface_title_anchor_inputs(ctx, vr, fd) is None
    observation = ctx._source_scope_state_diagnostics['surface_title_anchor']
    assert observation['code'] == 'DECODER_GENERAL_NOUN_HIGH_MISSING'
    assert observation['applied'] is False
    assert canonical({'vr':vr, 'fd':fd, 'decoder':ctx.get_expert_output(ExpertType.DECODER)}) == before
    # 옛 surface guard의 거절은 유지하고, 새 general 경로의 별도 근거를 요구한다.
    assert pipe._general_context_state_inputs(ctx, 'nonwork_comparison') is not None
    output, payload = serialize(pipe, ctx)
    assert ctx.__dict__.get('_surface_title_anchor_evidence') is None
    binding = ctx.__dict__.get('_general_context_state_evidence')
    assert binding is not None
    assert binding['rule'] == 'SOURCE_GENERAL_CONTEXT_STATE_V1'
    assert binding['mode'] == 'nonwork_comparison' and binding['verify']() is True
    assert binding['publication_authority'] is False and binding['candidate_completeness_claimed'] is False
    assert output.__dict__['_final_source_context_receipt']['general_context_state_binding'] is binding
    assert payload['identity']['is_relevant'] is False
    assert payload['identity']['is_novel_related'] is False
    assert payload['identity']['title_resolution_state'] == 'context_only'
    assert payload['identity']['title_resolution_allowed'] is False
    assert payload['identity']['work_resolution'] == 'none'
    assert payload['identity']['novel_identity'] is None
    assert (payload['identity']['discussion_type'], payload['identity']['subtype'],
        payload['identity']['topicality'], payload['identity']['relevance_scope']) == (
        'noise', 'other_quarantine', 'unrelated', 'off_topic')
    assert payload['identity']['promotion_decision']['publish_allowed'] is False
    assert payload['analysis']['is_nsfw'] is False
    assert payload['analysis']['nsfw_assessment_status'] == row['packet']['checkpoint_result']['analysis_result']['analysis']['nsfw_assessment_status']
    assert canonical({'vr':vr, 'fd':fd, 'decoder':ctx.get_expert_output(ExpertType.DECODER)}) == before
    diagnostics = export_source_context_diagnostics(output, enabled=True)
    record = next(x for x in diagnostics['scope_state_guards'] if x['gate']=='surface_title_anchor')
    assert record['first_rejection'] == 'DECODER_GENERAL_NOUN_HIGH_MISSING'
    assert record['applied'] is False


@pytest.mark.parametrize('kind', ['official_search','official_fetch','specific_relation','alias','work_candidate',
    'author','character','comment_work','image_work','raw_link','nonboolean','changed_literal','missing_decoder'])
def test_current57_competition_and_missing_inputs_cannot_borrow_question_proof(tmp_path, kind):
    pipe, ctx, _ = context(tmp_path)
    output, _ = serialize(pipe, ctx)
    vr = ctx.get_expert_output(ExpertType.VERIFIER)['verification_result']
    if kind == 'official_search':
        ctx.search_results.append({'title':'별도 작품','url':'https://novelpia.com/novel/123'})
    elif kind == 'official_fetch':
        ctx.fetched_page_info = [{'title':'별도 작품','url':'https://series.naver.com/novel/detail.series?productNo=123'}]
    elif kind == 'specific_relation':
        vr['relation_judgment'] = {'discussion_target':'specific_work','post_direct_grounding':True}
    elif kind == 'alias':
        vr['slang_insight'].update(alias_scope='pure_work_alias', canonical_work_alias='아카데미 생존 갤러리')
    elif kind == 'work_candidate':
        ctx.get_expert_output(ExpertType.DECODER)['decoded_terms'][0]['candidates'].append({'official_novel_title':'다른 작품'})
    elif kind in {'author','character'}:
        ctx.get_expert_output(ExpertType.GATEKEEPER)['detected_entities']['possible_'+('authors' if kind=='author' else 'characters')] = ['독립 인명']
    elif kind == 'comment_work':
        ctx.comments.append('아생갤 얘기임')
    elif kind == 'image_work':
        ctx.post_data['image_enrichment'] = [{'explicit_work_title':'별도 작품','promotion_eligible':True}]
    elif kind == 'raw_link':
        ctx.post_data['content_blocks'][0]['text'] += ' https://novelpia.com/novel/123'
    elif kind == 'nonboolean':
        vr['is_novel_discussion'] = 0
    elif kind == 'changed_literal':
        vr['grounding_check']['anchor_text'] = '다른 원문'
    else:
        ctx.get_expert_output(ExpertType.DECODER).clear()
    assert call_scope_again(pipe, ctx, output) is None
    assert ctx._source_scope_state_diagnostics['propriety_question_scope']['status'] == 'REJECTED'


@pytest.mark.parametrize('kind', ['catalog_value','catalog_owner','literal_anchor','state','raw_source','native_proof'])
def test_current57_seal_rejects_late_candidate_source_or_state_changes(tmp_path, kind):
    pipe, ctx, _ = context(tmp_path)
    output, payload = serialize(pipe, ctx)
    altered = copy.deepcopy(payload)
    if kind == 'catalog_value':
        ctx.search_results[0]['title'] += ' changed'
    elif kind == 'catalog_owner':
        ctx.search_results = copy.deepcopy(ctx.search_results)
    elif kind == 'literal_anchor':
        ctx.get_expert_output(ExpertType.VERIFIER)['verification_result']['grounding_check']['decoder_grounded'] = False
    elif kind == 'state':
        altered['identity']['title_resolution_state'] = 'unresolved_matchable'
    elif kind == 'raw_source':
        ctx.post_data['content_blocks'][1]['text'] = '다른 발화'
    else:
        ctx.__dict__.pop('_final_source_projection_native')
    with pytest.raises(ValueError):
        pipe.verify_final_source_context_serialization(output, altered, stage='current_scope_tamper_'+kind)


def test_scope_diagnostics_are_bounded_and_do_not_authorize_publication(tmp_path):
    pipe, ctx, _ = context(tmp_path)
    output, payload = serialize(pipe, ctx)
    sealed = pipe._propriety_question_serialization_seal(payload)
    output.__dict__['_source_scope_state_diagnostics']['propriety_callback']['code'] = 'x'*100000
    diagnostics = export_source_context_diagnostics(output, enabled=True)
    assert len(canonical(diagnostics)) <= MAX_BYTES and diagnostics['status']=='TRUNCATED'
    assert diagnostics['publication_authority'] is False
    assert pipe._propriety_question_serialization_seal(payload) == sealed
    assert payload['identity']['promotion_decision']['publish_allowed'] is False
    assert export_source_context_diagnostics(output, enabled=False)['scope_state_guards'] == []
