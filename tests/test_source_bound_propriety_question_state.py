"""57번 저장 전문가의 제한 재구성과 실제 serializer/검산/WAL 회귀. 모델 호출 없음."""
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
from llm_batch import promotion_gate
from llm_batch.promotion_gate import normalize_scope_reason_codes
from llm_batch.grounding.candidate_audit import apply_candidate_audit_fields, has_authoritative_publish_contract
from llm_batch.ledger.publication_commit import (
    PublicationCommitError, PublicationCommitRegistry, build_publication_scope_descriptor, commit_publication_result,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).parent / 'fixtures/actual80_run191128_semantic57_saved_experts.json'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


class NoExternal:
    def __getattr__(self, name):
        def forbidden(*args, **kwargs):
            raise AssertionError('NEW_MODEL_SEARCH_FETCH_FORBIDDEN:' + name)
        return forbidden


def record():
    fixture = json.loads(FIXTURE.read_bytes())
    assert fixture['scope'] == 'LOG_DERIVED_RECONSTRUCTED_CONTEXT_NOT_ORIGINAL_MEMORY_CONTEXT'
    assert digest({'post': fixture['packet']['source_post'], 'comments': fixture['packet']['source_comments']}) == fixture['source_canonical_sha256']
    assert digest(fixture['packet']['checkpoint_result']) == fixture['result_canonical_sha256']
    last = {x['expert']: x['value'] for x in fixture['completed_expert_stream']['outputs']}
    assert last == fixture['record']['experts']
    return copy.deepcopy(fixture['record']), fixture


def context(tmp_path, *, mutate=None, capture=True):
    row, fixture = record()
    if mutate:
        mutate(row)
    raw = copy.deepcopy(row['post'])
    raw['comments'] = copy.deepcopy(row['comments'])
    post = PostInput(**raw)
    pipe = AgenticPipeline(llm=NoExternal(), mcp=NoExternal(), output_dir=tmp_path,
        max_iterations=1, native_recovery=True)
    pipe.enable_url_fetch_disk_cache = False
    pipe._use_session_knowledge = False
    ctx = ConversationContext(post_id=post.post_id, post_data=pipe._post_to_dict(post),
        comments=pipe._extract_comments(post))
    if capture:
        ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(post)
        ctx._final_source_original_comment_refs = tuple(post.comments)
        ctx._source_bound_nsfw_original_carrier = pipe._capture_source_bound_nsfw_carrier(post)
    for name, value in row['experts'].items():
        ctx.set_expert_output(ExpertType(name), copy.deepcopy(value))
    # 고정 결과에 실제 보존된 producer 메타데이터만 복원한다. 새 COMPLETE proof를 만들지 않는다.
    stored_ledger = fixture['packet']['checkpoint_result']['analysis_result']['identity']['candidate_ledger']
    for attr, key in (('_candidate_producer_plans', 'candidate_producer_plans'),
            ('_candidate_producer_receipts', 'candidate_producer_receipts'),
            ('_candidate_generation_stage_receipts', 'candidate_stage_receipts')):
        setattr(ctx, attr, copy.deepcopy(stored_ledger.get(key, [])))
    discourse = (row['experts'].get('discourse') or {}).get('discourse_analysis') or {}
    ctx.primary_domain = discourse.get('primary_domain')
    ctx.discourse_intent = discourse.get('intent')
    return pipe, ctx, fixture


def serialize(pipe, ctx):
    original = canonical({'post': ctx.post_data, 'comments': ctx.comments})
    output = pipe._context_to_output(ctx)
    payload = output.model_dump(mode='json')
    observed = pipe.verify_final_source_context_serialization(output, payload, stage='propriety_question_saved_experts')
    assert isinstance(observed, dict)
    assert canonical({'post': ctx.post_data, 'comments': ctx.comments}) == original
    assert ctx._final_source_projection_call_count == 1
    return output, payload


def wrapper_class():
    tree = ast.parse((ROOT / 'expert_main.py').read_text(encoding='utf8'))
    node = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == '_FinalSourceContextResult')
    namespace = {'Any': Any, 'Dict': Dict, 'Mapping': Mapping}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(ROOT / 'expert_main.py'), 'exec'), namespace)
    return namespace['_FinalSourceContextResult']


def legacy_converge_direct(payload):
    tree = ast.parse((ROOT / 'expert_main.py').read_text(encoding='utf8'))
    names = {'_publication_has_candidate_payload', '_promotion_gate_state_candidate_payload',
        '_enforce_publish_contract_trace_convergence'}
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    selected += [node for node in tree.body if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == '_NO_CANDIDATE_PUBLICATION_REASON_CODES' for t in node.targets)]
    assert len(selected) == 4
    namespace = {'Any': Any, 'Dict': Dict, 'normalize_scope_reason_codes': normalize_scope_reason_codes}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(ROOT / 'expert_main.py'), 'exec'), namespace)
    return namespace['_enforce_publish_contract_trace_convergence'](payload)


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


def test_saved57_baseline_scope_and_real_serializer_contract_wal(tmp_path):
    raw_before = FIXTURE.read_bytes()
    pipe, ctx, fixture = context(tmp_path)
    # 실제 동결 원본 함수의 scope 계산만 재생한다. 원래 메모리 context 전체 복원 주장은 아니다.
    baseline_source = fixture['baseline_scope_function']['source']
    assert hashlib.sha256(baseline_source.encode()).hexdigest() == fixture['baseline_scope_function']['sha256']
    namespace = dict(AgenticPipeline._derive_resolution_scope_fields.__globals__)
    exec(compile(ast.parse(baseline_source), 'frozen_pre_fix_resolution_scope', 'exec'), namespace)
    old_identity = fixture['packet']['checkpoint_result']['analysis_result']['identity']
    old_scope = namespace['_derive_resolution_scope_fields'](pipe, ctx=ctx,
        is_relevant=False, official_title=None, discussion_type='noise', topicality='unrelated',
        subtype='other_quarantine', work_resolution='none',
        verification_result=ctx.get_expert_output(ExpertType.VERIFIER)['verification_result'],
        final_decision=ctx.get_expert_output(ExpertType.ARBITER)['final_decision'])
    assert old_scope['title_resolution_state'] == old_identity['title_resolution_state'] == 'unresolved_matchable'
    assert old_scope['is_novel_related'] is True

    output, payload = serialize(pipe, ctx)
    identity = payload['identity']
    for key in ('discussion_type', 'subtype', 'topicality', 'relevance_scope', 'is_relevant',
                'is_novel_related', 'work_resolution', 'title_resolution_allowed'):
        assert identity[key] == old_identity[key], key
    assert identity['title_resolution_state'] == 'context_only'
    assert identity['novel_identity'] is None
    assert payload['analysis']['is_nsfw'] is True
    assert payload['analysis']['nsfw_assessment_status'] == 'MODEL_REPORTED'
    assert '성희롱' in identity['primary_subject_text'] and '질문' in identity['primary_subject_text']
    assert '- 제목 판정: context_only' in identity['reason']
    binding = ctx._propriety_question_scope_evidence
    assert binding['native'] is ctx._final_source_projection_native
    assert binding['verify']() is True and binding['publication_authority'] is False
    assert binding['prior_contract_fingerprint'] != binding['contract_fingerprint']
    contract = ctx._last_publish_contract
    assert contract.state.title_resolution_state == 'context_only'
    assert contract.decision.publish_allowed is False and contract.decision.bypassed_gate is False
    assert identity['publish_contract_input_fingerprint'] == binding['contract_fingerprint'] == contract.input_fingerprint
    assert identity['candidate_ledger']['publish_contract_input_fingerprint'] == contract.input_fingerprint
    assert identity['promotion_gate_state']['title_resolution_state'] == 'context_only'
    assert identity['candidate_ledger']['title_resolution_state'] == 'context_only'
    assert identity['candidate_ledger']['candidate_generation']['status'] == old_identity['candidate_ledger']['candidate_generation']['status'] == 'UNKNOWN'
    assert identity['candidate_ledger']['candidate_generation_proof']['status'] == old_identity['candidate_ledger']['candidate_generation_proof']['status'] == 'TRUNCATED'
    for proof in binding['proofs']:
        assert proof.manifest_object is binding['native'].manifest
        assert proof.ledger_object is binding['native'].author_ledger
        assert proof.comment_object is None and proof.claimant == 'self' and proof.claim_kind == 'own'

    # 실제 main의 v2 marker -> typed state/evidence 재계산 분기를 거친다.
    # legacy convergence 직접 호출은 정규 경로가 아니다(별도 음성 대조 아래).
    bound_before = pipe._propriety_question_serialization_seal(payload)
    decision_before = copy.deepcopy(identity['promotion_decision'])
    trace_before = copy.deepcopy(identity['publish_contract_trace'])
    assert identity['novel_identity'] is None
    synchronize_like_actual_main(payload, ctx.post_data)
    assert identity['promotion_decision'] == decision_before == contract.decision.to_dict()
    assert identity['publish_contract_trace'] == trace_before == contract.trace.to_dict()
    assert 'publish_contract_integrity_error' not in identity
    assert identity['novel_identity'] == {'official_title': None, 'heretic_url': None}
    assert output.identity.novel_identity is None
    assert pipe._propriety_question_serialization_seal(payload) == bound_before
    pipe.verify_final_source_context_serialization(output, payload, stage='after_actual_main_typed_sync')
    row = fixture['record']
    full = dict(row['post'], post_author=row['post'].get('author'), comments=row['comments'], analysis_result=payload,
        run_meta={'local_test': True})
    wrapped = wrapper_class()(full, output=output, verifier=pipe.verify_final_source_context_serialization)
    scope = build_publication_scope_descriptor(input_file_sha256=fixture['source_canonical_sha256'],
        post_ids=[ctx.post_id], config_hash='propriety-question-saved-experts', release_fingerprint='candidate-only')
    path = tmp_path / 'publication.jsonl'
    registry = PublicationCommitRegistry(path, scope_descriptor=scope, create_new=True)
    wrapped.verify_stored_payload(wrapped, stage='before_commit')
    commit, created = commit_publication_result(wrapped, registry=registry,
        attempt_run_id='saved57-local', input_index=1, post_id=ctx.post_id)
    assert created is True and commit.outcome == 'HOLD' and commit.publish_allowed is False
    stored = PublicationCommitRegistry(path, scope_descriptor=scope, create_new=False).result(ctx.post_id)
    assert stored['analysis_result'] == payload
    wrapped.verify_stored_payload(stored, stage='actual_wal_readback')
    damaged_stored = copy.deepcopy(stored)
    damaged_stored['analysis_result']['identity']['title_resolution_state'] = 'unresolved_matchable'
    with pytest.raises(ValueError, match='final source serialized fields changed'):
        wrapped.verify_stored_payload(damaged_stored, stage='tampered_wal_readback')
    assert FIXTURE.read_bytes() == raw_before


@pytest.mark.parametrize('expert,field,value', [
    ('verifier', 'is_relevant', None), ('verifier', 'is_relevant', 'false'),
    ('verifier', 'is_novel_discussion', True), ('arbiter', 'is_relevant', None),
    ('arbiter', 'is_novel_discussion', 'false'), ('arbiter', 'is_novel_discussion', True),
])
def test_missing_or_nonboolean_expert_negative_never_owns_new_rule(tmp_path, expert, field, value):
    def mutate(row):
        key = 'verification_result' if expert == 'verifier' else 'final_decision'
        row['experts'][expert][key][field] = value
    pipe, ctx, _ = context(tmp_path, mutate=mutate)
    # 전체 serializer의 다른 기존 fallback 결과를 새 규칙 성공으로 오인하지 않는다.
    serialize(pipe, ctx)
    assert ctx.__dict__.get('_propriety_question_scope_evidence') is None


@pytest.mark.parametrize('kind', ['missing_decoder', 'pending_decoder', 'unresolved_decoder', 'work_interpretation',
    'real_candidate', 'author', 'character', 'alias', 'work_relation'])
def test_missing_and_competing_work_observations_keep_rule_unavailable(tmp_path, kind):
    def mutate(row):
        decoder = row['experts']['decoder']
        verifier = row['experts']['verifier']['verification_result']
        if kind == 'missing_decoder':
            del row['experts']['decoder']
        elif kind == 'pending_decoder':
            decoder['needs_verification'] = True
        elif kind == 'unresolved_decoder':
            decoder['unresolved_terms'] = ['작품 약칭 미확인']
        elif kind == 'work_interpretation':
            decoder['decoded_terms'][0]['interpretations'].append({'type': 'work_alias', 'value': '아생갤'})
        elif kind == 'real_candidate':
            decoder['decoded_terms'][0]['candidates'].append({'official_novel_title': '가상 작품', 'url': None})
        elif kind in {'author', 'character'}:
            row['experts']['gatekeeper']['detected_entities']['possible_' + ('authors' if kind == 'author' else 'characters')] = ['가상 인명']
        elif kind == 'alias':
            verifier['slang_insight'].update(canonical_work_alias='아카데미 생존 갤러리', alias_scope='pure_work_alias')
        elif kind == 'work_relation':
            verifier['relation_judgment'] = {'discussion_target': 'specific_work', 'post_direct_grounding': True}
    pipe, ctx, _ = context(tmp_path, mutate=mutate)
    serialize(pipe, ctx)
    assert ctx.__dict__.get('_propriety_question_scope_evidence') is None


@pytest.mark.parametrize('body,comments', [
    (['남근은 있는듯', '민수: <- 이러면 성희롱임?'], None),
    (['"남근은 있는듯', '<- 이러면 성희롱임?"'], None),
    (['남근은 있는듯', '<- 이러면 성희롱임? 라고 물었다.'], None),
    (['그때 남근은 있는듯 했음', '예전에 <- 이러면 성희롱임? 하고 물었다.'], None),
    (['남근은 있는듯', '만약 이렇게 말하면 성희롱임?'], None),
    (['남근은 있는듯', '오늘은 그냥 쉬었음'], [{'content': '<- 이러면 성희롱임?', 'author': '타인'}]),
    (['남근은 있는듯', '<- 이러면 성희롱임?', '아생갤은 아카데미 생존 갤러리의 약칭이다.'], None),
    (['남근은 있는듯', '<- 이러면 성희롱임?', '가상 작가의 신작 제목이 뭐임?'], None),
    (['남근은 있는듯', '<- 이러면 성희롱임?', '예전에 읽은 소설 제목 좀 찾아줘'], None),
    (['남근은 있는듯', '<- 이러면 성희롱임?', '비슷한 소설 추천 좀'], None),
    (['남근은 있는듯', '<- 이러면 성희롱임?'], [{'content': '아생갤 얘기임', 'author': '타인'}]),
])
def test_author_attribution_and_extra_work_question_cannot_borrow_pointed_proof(tmp_path, body, comments):
    def mutate(row):
        row['post']['content_blocks'] = [{'type': 'text', 'text': value} for value in body]
        if comments is not None:
            row['comments'] = comments
    pipe, ctx, _ = context(tmp_path, mutate=mutate)
    serialize(pipe, ctx)
    assert ctx.__dict__.get('_propriety_question_scope_evidence') is None


def test_image_and_ocr_competition_do_not_enter_text_only_rule(tmp_path):
    def mutate(row):
        row['post']['content_blocks'].append({'type': 'image', 'url': 'https://fixture.invalid/scene.png'})
    pipe, ctx, _ = context(tmp_path, mutate=mutate)
    ctx.post_data['image_enrichment'] = [{'block_index': 2, 'source_url': 'https://fixture.invalid/scene.png',
        'ocr_text': '아카데미 생존 갤러리', 'explicit_work_title': '아카데미 생존 갤러리',
        'evidence_type': 'explicit_text', 'title_role': 'work_title', 'promotion_eligible': False}]
    serialize(pipe, ctx)
    assert ctx.__dict__.get('_propriety_question_scope_evidence') is None


@pytest.mark.parametrize('change', ['hash', 'span', 'foreign_ledger', 'foreign_native', 'missing_carrier'])
def test_same_native_question_proof_rejects_resealed_or_foreign_objects(tmp_path, change):
    pipe, ctx, _ = context(tmp_path)
    output, _ = serialize(pipe, ctx)
    owned = ctx._propriety_question_scope_evidence
    native = owned['native']
    explanation = owned['explanation']
    proof_index = next(i for i, p in enumerate(explanation.proofs) if p.rule == 'current_pointed_harassment_question')
    proof = explanation.proofs[proof_index]
    changes = {'hash': {'source_sha256': '0' * 64}, 'span': {'raw_span': (1, 2)},
        'foreign_ledger': {'ledger_object': copy.deepcopy(native.author_ledger)}}
    if change == 'foreign_native':
        native = replace(native)
    elif change == 'missing_carrier':
        ctx.__dict__.pop('_final_source_original_inputs')
    else:
        proofs = list(explanation.proofs)
        proofs[proof_index] = replace(proof, **changes[change])
        explanation = replace(explanation, proofs=tuple(proofs))
    identity = output.identity.model_copy(deep=True)
    identity.title_resolution_state = 'unresolved_matchable'
    assert pipe._source_bound_propriety_question_scope(ctx, identity, native, explanation,
        ctx._final_source_discussion_observations['records'], ctx._final_source_discussion_observations['comments'],
        publish_contract=ctx._last_publish_contract) is None


@pytest.mark.parametrize('field', ['title_state', 'contract', 'nsfw', 'source', 'expert_negative'])
def test_final_seal_rejects_state_contract_nsfw_and_consumed_source_tamper(tmp_path, field):
    pipe, ctx, _ = context(tmp_path)
    output, payload = serialize(pipe, ctx)
    changed = copy.deepcopy(payload)
    if field == 'title_state':
        changed['identity']['title_resolution_state'] = 'unresolved_matchable'
    elif field == 'contract':
        changed['identity']['candidate_ledger']['publish_contract_input_fingerprint'] = '0' * 64
    elif field == 'nsfw':
        changed['analysis']['is_nsfw'] = False
    elif field == 'source':
        ctx.post_data['content_blocks'][1]['text'] = '다른 질문'
    else:
        ctx.get_expert_output(ExpertType.VERIFIER)['verification_result']['is_novel_discussion'] = True
    expected = ('NSFW source-bound serialization changed' if field == 'nsfw' else
        'final source native verification failed' if field in {'source', 'expert_negative'} else
        'final source serialized fields changed')
    with pytest.raises(ValueError, match=expected):
        pipe.verify_final_source_context_serialization(output, changed, stage='propriety_scope_tamper_' + field)


def test_patch_reuses_native_once_and_callback_precedes_display_consumption():
    tree = ast.parse((ROOT / 'src/llm_batch/agentic_pipeline.py').read_text(encoding='utf8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'AgenticPipeline')
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    helper = methods['_source_bound_propriety_question_scope']
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == 'project_context_native' for n in ast.walk(helper))
    consume = methods['_consume_final_source_context']
    calls = [n for n in ast.walk(consume) if isinstance(n, ast.Call)]
    project = [n for n in calls if isinstance(n.func, ast.Attribute) and n.func.attr == '_project_final_source_context']
    callbacks = [n for n in calls if isinstance(n.func, ast.Name) and n.func.id == 'preseal_contract_update']
    classification = [n for n in calls if isinstance(n.func, ast.Attribute) and n.func.attr == '_final_source_discussion_classification']
    assert len(project) == len(callbacks) == len(classification) == 1
    assert project[0].lineno < callbacks[0].lineno < classification[0].lineno


@pytest.mark.parametrize('change', [
    'title_state_missing', 'title_state_null', 'allowed_int', 'relevance_int',
    'ledger_state', 'ledger_fingerprint_missing', 'identity_fingerprint',
    'trace_fingerprint', 'trace_decision_fingerprint', 'public_allowed_int', 'public_title',
])
def test_propriety_scope_wrapper_rejects_missing_type_and_contract_mirror_changes(tmp_path, change):
    pipe, ctx, fixture = context(tmp_path)
    output, payload = serialize(pipe, ctx)
    full = dict(fixture['record']['post'], analysis_result=payload)
    wrapped = wrapper_class()(full, output=output, verifier=pipe.verify_final_source_context_serialization)
    changed = copy.deepcopy(full)
    identity = changed['analysis_result']['identity']
    if change == 'title_state_missing':
        del identity['title_resolution_state']
    elif change == 'title_state_null':
        identity['title_resolution_state'] = None
    elif change == 'allowed_int':
        identity['title_resolution_allowed'] = 0
    elif change == 'relevance_int':
        identity['is_novel_related'] = 1
    elif change == 'ledger_state':
        identity['candidate_ledger']['title_resolution_state'] = 'unresolved_matchable'
    elif change == 'ledger_fingerprint_missing':
        del identity['candidate_ledger']['publish_contract_input_fingerprint']
    elif change == 'identity_fingerprint':
        identity['publish_contract_input_fingerprint'] = '0' * 64
    elif change == 'trace_fingerprint':
        identity['publish_contract_trace']['input_fingerprint'] = '0' * 64
    elif change == 'trace_decision_fingerprint':
        identity['candidate_ledger']['publish_contract_trace']['gate_decision']['input_fingerprint'] = '0' * 64
    elif change == 'public_allowed_int':
        identity['publish_ledger']['gate_decision']['publish_allowed'] = 0
    else:
        identity['publish_ledger']['public_publish']['official_title'] = '근거 없는 작품'
    with pytest.raises(ValueError, match='final source serialized fields changed'):
        wrapped.verify_stored_payload(changed, stage='scope_wrapper_tamper_' + change)
    with pytest.raises(ValueError, match='final source serialized fields changed'):
        wrapper_class()(changed, output=output, verifier=pipe.verify_final_source_context_serialization)
    assert ctx._propriety_question_scope_evidence['verify']() is True


@pytest.mark.parametrize('change', ['model_ledger', 'model_state', 'optional_seal', 'context_contract'])
def test_propriety_scope_native_model_cannot_drift_with_unchanged_wire_payload(tmp_path, change):
    pipe, ctx, _ = context(tmp_path)
    output, payload = serialize(pipe, ctx)
    if change == 'model_ledger':
        output.identity.candidate_ledger['publish_contract_input_fingerprint'] = '0' * 64
    elif change == 'model_state':
        output.identity.title_resolution_state = 'unresolved_matchable'
    elif change == 'optional_seal':
        output.__dict__.pop('_source_bound_propriety_scope_seal')
    else:
        ctx._last_publish_contract = replace(ctx._last_publish_contract)
    with pytest.raises(ValueError, match='final source native verification failed'):
        pipe.verify_final_source_context_serialization(output, payload, stage='native_scope_tamper_' + change)


def test_nonquestion_path_keeps_legacy_final4_receipt_without_optional_scope(tmp_path):
    def mutate(row):
        row['experts']['verifier']['verification_result']['is_novel_discussion'] = True
    pipe, ctx, _ = context(tmp_path, mutate=mutate)
    output, payload = serialize(pipe, ctx)
    assert ctx.__dict__.get('_propriety_question_scope_evidence') is None
    receipt = output.__dict__['_final_source_context_receipt']
    assert 'propriety_scope_seal' not in receipt and 'propriety_serialized_seal' not in receipt
    assert '_source_bound_propriety_scope_seal' not in output.__dict__
    assert receipt['seal'] == pipe._final_source_serialization_seal(payload)


def test_legacy_direct_convergence_is_not_the_actual_typed_main_path(tmp_path):
    pipe, ctx, fixture = context(tmp_path)
    output, payload = serialize(pipe, ctx)
    original_decision = copy.deepcopy(payload['identity']['promotion_decision'])
    wrong_route = copy.deepcopy(payload)
    legacy_converge_direct(wrong_route)
    assert 'serialized_public_identity_scrubbed' not in original_decision['reason_codes']
    assert wrong_route['identity']['promotion_decision']['reason_codes'] == [
        *original_decision['reason_codes'], 'serialized_public_identity_scrubbed']
    # 같은 잘못된 경로는 이번에도 실제 WAL 검산이 거절해야 한다. guard를 완화하지 않는다.
    scope = build_publication_scope_descriptor(input_file_sha256=fixture['source_canonical_sha256'],
        post_ids=[ctx.post_id], config_hash='wrong-legacy-route', release_fingerprint='candidate-only')
    registry = PublicationCommitRegistry(tmp_path / 'wrong-route.jsonl', scope_descriptor=scope, create_new=True)
    with pytest.raises(PublicationCommitError, match='typed state/evidence recompute does not match decision'):
        commit_publication_result(dict(fixture['record']['post'], analysis_result=wrong_route), registry=registry,
            attempt_run_id='wrong-route-local', input_index=1, post_id=ctx.post_id)
    synchronize_like_actual_main(payload, ctx.post_data)
    assert payload['identity']['promotion_decision'] == original_decision
    pipe.verify_final_source_context_serialization(output, payload, stage='actual_typed_route_control')


def test_actual_main_null_pair_is_the_only_permitted_public_shape_change(tmp_path):
    pipe, ctx, fixture = context(tmp_path)
    output, payload = serialize(pipe, ctx)
    synchronize_like_actual_main(payload, ctx.post_data)
    full = dict(fixture['record']['post'], analysis_result=payload)
    wrapped = wrapper_class()(full, output=output, verifier=pipe.verify_final_source_context_serialization)
    # 기존 typed writer의 정확한 null 두 키만 허용한다. 다른 빈 값은 None으로 강제 변환하지 않는다.
    invalid = ({}, {'official_title': None}, {'official_title': None, 'heretic_url': None, 'author': None},
        {'official_title': '', 'heretic_url': None}, {'official_title': False, 'heretic_url': None},
        {'official_title': None, 'heretic_url': False},
        {'official_title': '근거 없는 작품', 'heretic_url': None},
        {'official_title': None, 'heretic_url': 'https://novelpia.com/novel/1'})
    for value in invalid:
        changed = copy.deepcopy(full)
        changed['analysis_result']['identity']['novel_identity'] = value
        with pytest.raises(ValueError, match='final source serialized fields changed'):
            wrapped.verify_stored_payload(changed, stage='invalid_public_null_pair')
    changed = copy.deepcopy(full)
    del changed['analysis_result']['identity']['novel_identity']
    with pytest.raises(ValueError, match='final source serialized fields changed'):
        wrapped.verify_stored_payload(changed, stage='missing_public_identity')
    wrapped.verify_stored_payload(full, stage='unchanged_exact_null_pair')
