"""34·35 고정 부분 context와 실제 producer/typed 저장 경로. 새 추론·외부 호출 금지."""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

import pytest

from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import PostInput
from llm_batch.experts.decoder import DecoderExpert
from llm_batch.experts.orchestrator import ConversationContext, ExpertType
from llm_batch.grounding.candidate_audit import apply_candidate_audit_fields, has_authoritative_publish_contract
from llm_batch.ledger.publication_commit import (
    PublicationCommitRegistry, build_publication_scope_descriptor, commit_publication_result,
)
from llm_batch import promotion_gate

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).parent / 'fixtures/actual80_surface_hypothesis34_35_saved_experts.json'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


class NoExternal:
    def __getattr__(self, name):
        def forbidden(*args, **kwargs):
            raise AssertionError('NEW_MODEL_SEARCH_FETCH_FORBIDDEN:' + name)
        return forbidden


def context(tmp_path, index=None, variant='current', *, title='', body=()):
    if index is not None:
        fixture = json.loads(FIXTURE.read_bytes())
        assert fixture['scope'] == 'SAVED_EXPERTS_PARTIAL_CONTEXT_NOT_ORIGINAL_MEMORY_CONTEXT'
        record = fixture['records'][str(index)]
        assert digest(record['source']) == record['source_canonical_sha256']
        stored = record['variants'][variant]
        assert digest(stored['result']) == stored['result_canonical_sha256']
        assert stored['experts'] == {x['expert']: x['value'] for x in stored['expert_stream']}
        source = copy.deepcopy(record['source'])
    else:
        stored = None
        source = {'post': {'post_id': 934350, 'gallery_id': 'genrenovel', 'title': title,
                          'content_blocks': [{'type': 'text', 'text': x} for x in body]}, 'comments': []}
    post = PostInput(**source['post'], comments=source['comments'])
    pipe = AgenticPipeline(llm=NoExternal(), mcp=NoExternal(), output_dir=tmp_path,
                          max_iterations=1, native_recovery=True)
    pipe.enable_url_fetch_disk_cache = False
    pipe._use_session_knowledge = False
    ctx = ConversationContext(post_id=post.post_id, post_data=pipe._post_to_dict(post),
                              comments=pipe._extract_comments(post))
    ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs = tuple(post.comments)
    ctx._source_bound_nsfw_original_carrier = pipe._capture_source_bound_nsfw_carrier(post)
    if stored:
        for name, payload in stored['experts'].items():
            ctx.set_expert_output(ExpertType(name), copy.deepcopy(payload))
        discourse = stored['experts']['discourse']['discourse_analysis']
        ctx.primary_domain = discourse.get('primary_domain')
        ctx.discourse_intent = discourse.get('intent')
        ident = stored['result']['analysis_result']['identity']
        ctx.search_results = [dict(row, content=row.get('snippet', ''), _purpose=row.get('purpose'))
                              for row in (ident.get('search_evidence_catalog') or [])]
        # 원래 private ctx를 재현한다고 가정하지 않고 저장된 관측만 옮긴다.
        for attr, key in (('_candidate_producer_plans', 'candidate_producer_plans'),
                          ('_candidate_producer_receipts', 'candidate_producer_receipts'),
                          ('_candidate_generation_stage_receipts', 'candidate_stage_receipts')):
            setattr(ctx, attr, copy.deepcopy((ident.get('candidate_ledger') or {}).get(key, [])))
    return pipe, ctx, stored


def interpretation(alias, title):
    return {'decoded_terms': [{'original': alias, 'best_match': {'title': None, 'confidence': 'low'},
             'candidates': [], 'interpretations': [{'type': 'novel_title', 'value': title,
              'context_fit': 'medium', 'evidence': '모델 해독 가설이며 독립 표제 확인은 별도'}]}]}


def seed(ctx, value):
    ctx.set_expert_output(ExpertType.DECODER, copy.deepcopy(value))
    before = canonical(ctx.get_expert_output(ExpertType.DECODER))
    DecoderExpert(NoExternal())._init_suspected_titles(ctx.get_expert_output(ExpertType.DECODER), ctx)
    assert canonical(ctx.get_expert_output(ExpertType.DECODER)) == before


@pytest.mark.parametrize('variant', ['prior', 'current'])
def test_saved34_discourse_marker_is_not_inventory_but_authored_work_surface_survives(tmp_path, variant):
    pipe, ctx, stored = context(tmp_path, 34, variant)
    old = stored['result']['analysis_result']['identity']['candidate_preservation_sources']
    assert any(x['official_title'] == '아니' for x in old)
    assert pipe._collect_short_alias_hold_candidates(ctx) == []
    raw = pipe._unresolved_source_work_surface_holds(ctx)
    assert [x.official_title for x in raw] == ['재획']
    snapshot = pipe._build_candidate_preservation_snapshot(title_candidates=[], mentioned_works=[],
        comparison_target=None, recommendation_candidates=[], local_diagnostic_sources=raw)
    assert [x['official_title'] for x in snapshot.retained_sources] == ['재획']
    assert snapshot.status != 'COMPLETE'


@pytest.mark.parametrize('title,body,expected', [
    ('아니 재획 장갤발 작품이었음?', [], []),
    ('저기 재획 장갤발 작품이었음?', [], []),
    ('그런데 별책 이야기', ['다른 소설을 읽었다'], []),
    ('별책', ['소설 별책을 읽었다'], ['별책']),
    ('아니', ['소설 아니를 읽었다'], ['아니']),
])
def test_first_token_requires_its_own_work_relation_without_word_blacklist(tmp_path, title, body, expected):
    pipe, ctx, _ = context(tmp_path, title=title, body=body)
    assert [x.official_title for x in pipe._collect_short_alias_hold_candidates(ctx)] == expected


@pytest.mark.parametrize('variant', ['prior', 'current'])
def test_saved35_decoder_hypothesis_remains_diagnostic_through_title_inventory(tmp_path, variant):
    pipe, ctx, stored = context(tmp_path, 35, variant)
    decoded = ctx.get_expert_output(ExpertType.DECODER)
    hypotheses = [x['value'] for t in decoded['decoded_terms'] if t['original'] == '회모장'
                  for x in t.get('interpretations', []) if x.get('type') == 'novel_title']
    assert hypotheses
    seed(ctx, decoded)
    assert not set(hypotheses) & {x['title'] for x in ctx.suspected_titles}
    assert set(hypotheses) <= {x['text'] for x in ctx._title_meta_explanation_observations}
    # 저장된/다른 소비자가 다시 공급해도 title-stage 경계가 같은 source 판단을 한다.
    ctx.suspected_titles.extend({'title': x, 'confidence': 0.9, 'from': 'decoder_multi_interp'} for x in hypotheses)
    titles, snapshot = pipe._build_title_candidates_with_snapshot(ctx=ctx, is_relevant=True,
        official_title=None, heretic_url=None, confidence='Low', vf_result={})
    assert not set(hypotheses) & {x.official_title for x in titles}
    assert not set(hypotheses) & {x.get('official_title') for x in snapshot.retained_sources}
    assert snapshot.status != 'COMPLETE'
    assert [x.official_title for x in pipe._unresolved_source_work_surface_holds(ctx)] == ['회모장']


def candidate_titles(ctx):
    return {x['title'] for x in ctx.suspected_titles}


def outward_titles(payload):
    identity = payload['identity']
    rows = [x for field in ('title_candidates','recommendation_candidates','candidate_preservation_sources')
            for x in identity.get(field) or []]
    rows += payload['analysis'].get('detected_titles') or []
    return {x.get('official_title') for x in rows}


@pytest.mark.parametrize('full', [
    '전혀 다른 작품명', '주무시기 전에 무엇을 하셨나요?',
    '나는 오늘도 살아간다.', '아카데미 생존 갤러리',
])
@pytest.mark.parametrize('with_interpretation', [False, True])
def test_normal_best_match_with_official_anchor_keeps_existing_candidate_path(tmp_path, full, with_interpretation):
    pipe, ctx, _ = context(tmp_path, title='별책 읽었다')
    ctx.search_results = [{'url':'https://novelpia.com/novel/934350',
                           'title':full, 'snippet':f'{full} 작품 상세'}]
    value = interpretation('별책', full)
    term = value['decoded_terms'][0]
    term['best_match'] = {'title':full,'confidence':'medium'}
    term['candidates'] = [{'official_title':full,'morphological_score':0.9}]
    if not with_interpretation: term['interpretations'] = []
    seed(ctx, value)
    assert full in candidate_titles(ctx)
    assert pipe._is_unbound_title_meta_explanation(ctx,full) is False


@pytest.mark.parametrize('path', ['resolved_mapping','high_fit_interpretation'])
def test_original_known_official_positive_continues_through_producer_consumer(tmp_path, monkeypatch, path):
    import llm_batch.experts.decoder as module
    full = '전혀 다른 작품명'
    monkeypatch.setattr(module, 'KNOWN_ABBREVIATIONS', {'가가':full})
    pipe, ctx, _ = context(tmp_path, title='가가 읽었다')
    ctx.search_results = [{'url':'https://novelpia.com/novel/123',
                           'title':f'웹소설로 꿈꾸는 세상! - {full}', 'snippet':f'{full} 작품 상세'}]
    value = {'decoded_terms':[]}
    if path == 'resolved_mapping':
        ctx._resolved_mappings = [('가가',full)]
    else:
        value = interpretation('가가',full)
        value['decoded_terms'][0]['interpretations'][0]['context_fit'] = 'high'
        value = DecoderExpert(NoExternal())._auto_promote_high_fit_interpretation(value, ctx)
        assert value['decoded_terms'][0]['best_match']['title'] == full
        assert value['decoded_terms'][0]['best_match']['confidence'] == 'medium'
    seed(ctx,value)
    assert full in candidate_titles(ctx)
    assert pipe._is_unbound_title_meta_explanation(ctx,full) is False
    titles, snapshot = pipe._build_title_candidates_with_snapshot(ctx=ctx, is_relevant=True,
        official_title=None,heretic_url=None,confidence='Low',vf_result={})
    assert full in {x.official_title for x in titles} | {x.get('official_title') for x in snapshot.retained_sources}


@pytest.mark.parametrize('url', [
    'https://namu.wiki/w/별빛기사', 'https://bbs.ruliweb.com/community/board/1',
    'https://theqoo.net/novel/1', 'https://www.clien.net/service/board/1',
])
def test_normal_explicit_alias_wording_does_not_get_new_syntax_or_domain_veto(tmp_path, monkeypatch, url):
    import llm_batch.experts.decoder as module
    full='전혀 다른 작품명'
    monkeypatch.setattr(module,'KNOWN_ABBREVIATIONS',{'abc':full})
    pipe, ctx, _ = context(tmp_path,title='abc 읽었다')
    ctx.search_results = [{'url':url,'title':f'abc - {full}',
                           'snippet':f'abc는 {full}의 약칭으로 쓰인다.'}]
    value = interpretation('abc',full)
    term = value['decoded_terms'][0]
    term['best_match']={'title':full,'confidence':'medium'}
    term['candidates']=[{'official_title':full,'morphological_score':0.8}]
    term['grounding']={'anchor_type':'search_only'}
    guarded = DecoderExpert(NoExternal())._guard_weak_thematic_title_inference(value,ctx)
    assert guarded['decoded_terms'][0]['best_match'] == {'title':full,'confidence':'medium'}
    seed(ctx,guarded)
    assert full in candidate_titles(ctx)
    assert pipe._is_unbound_title_meta_explanation(ctx,full) is False


@pytest.mark.parametrize('body', [
    '회귀물 모험가 장르(추정) 읽었다', "소설 '회귀물 모험가 장르(추정)'을 읽었다",
    '나는 「회귀물 모험가 장르(추정)」를 읽었다',
    '이 소설의 제목은 회귀물 모험가 장르(추정)이다.',
])
def test_same_hypothesis_shaped_surface_has_positive_name_or_reading_role(tmp_path, body):
    from llm_batch.grounding.source_title_hypothesis import title_hypothesis_source_support
    full='회귀물 모험가 장르(추정)'
    pipe, ctx, _ = context(tmp_path,title='오늘 읽은 책',body=[body])
    value=interpretation('회모장',full)
    value['decoded_terms'][0]['best_match']={'title':full,'confidence':'medium'}
    value['decoded_terms'][0]['candidates']=[{'official_title':full,'morphological_score':0.7}]
    seed(ctx,value)
    assert full in candidate_titles(ctx)
    proof=title_hypothesis_source_support(ctx,'회모장',full)
    assert proof['kind']=='author_work_name' and proof['supports_publish'] is False
    assert proof['raw_text'][slice(*proof['raw_span'])] == full
    assert pipe._is_unbound_title_meta_explanation(ctx,full) is False


@pytest.mark.parametrize('body', [
    ['회귀물 모험가 장르(추정)라는 풀이일 뿐 작품명은 아니다'],
    ['회귀물 모험가 장르(추정)라는 설명을 읽었다'],
    ['만약 소설 회귀물 모험가 장르(추정)를 읽었다면'],
    ["친구가 '회귀물 모험가 장르(추정)'을 읽었다고 했다"],
    ['“', '소설 회귀물 모험가 장르(추정)를 읽었다.', '”라는 설명은 틀렸다.'],
    ['“\n소설 회귀물 모험가 장르(추정)를 읽었다.\n”라는 설명은 틀렸다.'],
    ['회귀물 모험가', '장르(추정) 읽었다'],
    ['회귀물 모험가 장르(추정)를 읽었다. 정정, 아니다.'],
])
def test_same_surface_non_naming_negated_hypothetical_or_reported_is_diagnostic(tmp_path,body):
    full='회귀물 모험가 장르(추정)'
    pipe,ctx,_=context(tmp_path,title='회모장 약자 풀이',body=body)
    seed(ctx,interpretation('회모장',full))
    assert full not in candidate_titles(ctx)
    assert pipe._is_unbound_title_meta_explanation(ctx,full) is True


def test_generic_noun_literal_is_not_work_naming_proof(tmp_path):
    from llm_batch.grounding.source_title_hypothesis import title_hypothesis_source_support
    _,ctx,_=context(tmp_path,title='기술 이야기',body=['인공지능은 기술 분야다'])
    assert title_hypothesis_source_support(ctx,'AI','인공지능') is None


@pytest.mark.parametrize('full,alias', [
    ('회귀물 모험가 장르(추정)','회모장'),
    ('주무시기 전에 무엇을 하셨나요?(추정)','주전무'),
    ('그가 말했다. 돌아오라(추정)','귀환'),
])
@pytest.mark.parametrize('style', ['copula','usage'])
def test_hypothesis_shaped_real_name_with_punctuation_and_alias_proof_is_preserved(tmp_path,full,alias,style):
    from llm_batch.grounding.source_title_hypothesis import title_hypothesis_source_support
    pipe,ctx,_=context(tmp_path,title=f'{alias} 읽었다')
    claim=f'소설 「{full}」의 약칭은 {alias}이다.' if style=='copula' else f'{alias}는 「{full}」의 약칭으로 쓰인다.'
    ctx.search_results=[{'url':'https://theqoo.net/novel/1','title':'약어 정리','snippet':claim}]
    value=interpretation(alias,full)
    value['decoded_terms'][0]['best_match']={'title':full,'confidence':'medium'}
    value['decoded_terms'][0]['candidates']=[{'official_title':full,'morphological_score':0.7}]
    seed(ctx,value)
    assert full in candidate_titles(ctx)
    proof=title_hypothesis_source_support(ctx,alias,full)
    assert proof['assertion']==claim and proof['source_field']=='snippet'
    assert proof['supports_publish'] is False
    assert pipe._is_unbound_title_meta_explanation(ctx,full) is False


@pytest.mark.parametrize('claim', [
    '소설 오늘부터 왕이 되는 방법의 약칭은 심해인가?',
    '소설 오늘부터 왕이 되는 방법의 약칭은 심해가 아니다.',
    '소설 오늘부터 왕이 되는 방법의 약칭은 심해일 것으로 추정된다.',
    '다른 소설의 약칭은 심해이다. 오늘부터 왕이 되는 방법도 있다.',
    '“\n소설 오늘부터 왕이 되는 방법의 약칭은 심해이다.\n”라는 설명은 틀렸다.',
    '소설 오늘부터 왕이 되는 방법의 약칭은 심해이다.\n위 설명은 틀렸다.',
    '만약 소설 오늘부터 왕이 되는 방법의 약칭은 심해이다라고 한다면',
    '친구가 소설 오늘부터 왕이 되는 방법의 약칭은 심해이다라고 말했다.',
])
def test_full_external_field_keeps_negative_quote_and_refutation_scope(tmp_path,claim):
    from llm_batch.grounding.source_title_hypothesis import title_hypothesis_source_support
    _,ctx,_=context(tmp_path,title='심해 읽었다')
    ctx.search_results=[{'url':'https://gall.dcinside.com/board/view/?id=genrenovel&no=1',
                         'title':'용어 해설','snippet':claim}]
    assert title_hypothesis_source_support(ctx,'심해','오늘부터 왕이 되는 방법') is None
    # 같은 반례를 실제 차단 대상 값으로 바꿔 producer/consumer까지 확인한다.
    full='오늘부터 왕이 되는 방법(추정)'
    ctx.search_results[0]['snippet']=claim.replace('오늘부터 왕이 되는 방법',full)
    value=interpretation('심해',full)
    value['decoded_terms'][0]['best_match']={'title':full,'confidence':'high'}
    value['decoded_terms'][0]['candidates']=[{'official_title':full,'morphological_score':0.99}]
    seed(ctx,value)
    assert full not in candidate_titles(ctx)


@pytest.mark.parametrize('mode', ['query_only','cross_fields','diagnostic','model_prose','spoofed_host','ocr','comment','missing_alias','known_only'])
def test_disconnected_evidence_does_not_authorize_hypothesis_role(tmp_path,monkeypatch,mode):
    import llm_batch.experts.decoder as module
    full='회귀물 모험가 장르(추정)'; alias='회모장'
    _,ctx,_=context(tmp_path,title=f'{alias} 읽었다')
    declaration=f'소설 {full}의 약칭은 {alias}이다.'
    row={'url':'https://novelpia.com/novel/934350','title':'검색 관측'}
    if mode=='query_only': row['query']=declaration
    if mode=='cross_fields': row.update(title=f'소설 {full}의 약칭은',snippet=f'{alias}이다.')
    if mode=='diagnostic': row.update(snippet=declaration,_ocr_diagnostic_only=True)
    if mode=='model_prose': row.update(snippet=declaration,source_tier='llm_only')
    if mode=='spoofed_host': row.update(snippet=declaration,url='https://novelpia.com.example.org/novel/934350')
    if mode=='ocr': ctx.post_data['content_blocks'].append({'type':'ocr_text','text':f'소설 {full}을 읽었다'})
    if mode=='comment': ctx.comments.append(f'소설 {full}을 읽었다')
    if mode=='missing_alias':
        _,ctx,_=context(tmp_path,title='다른 책을 읽었다'); row['snippet']=declaration
    if mode=='known_only': monkeypatch.setattr(module,'KNOWN_ABBREVIATIONS',{alias:full})
    ctx.search_results=[row]
    seed(ctx,interpretation(alias,full))
    assert full not in candidate_titles(ctx)


def test_exact_official_title_observation_is_candidate_existence_not_alias_or_publish_authority(tmp_path):
    from llm_batch.grounding.source_title_hypothesis import title_hypothesis_source_support
    full='회귀물 모험가 장르(추정)'
    pipe,ctx,_=context(tmp_path,title='회모장 읽었다')
    ctx.search_results=[{'url':'https://novelpia.com/novel/934350','title':full}]
    seed(ctx,interpretation('회모장',full))
    assert full in candidate_titles(ctx)
    proof=title_hypothesis_source_support(ctx,'회모장',full)
    # 단순 metadata 비교 예외는 제거했다. 공식 표제는 실제 기존 공식
    # producer/consumer 검산에서 보존하고 alias 증명으로 위조하지 않는다.
    assert proof is None
    assert pipe._is_unbound_title_meta_explanation(ctx,full) is False


def test_positive_sentence_title_survives_actual_main_typed_sync_and_wal(tmp_path):
    full='주무시기 전에 무엇을 하셨나요?'
    pipe,ctx,_=context(tmp_path,title='주전무 읽었다',body=[f'나는 「{full}」를 읽었다'])
    value=interpretation('주전무',full)
    value['decoded_terms'][0]['best_match']={'title':full,'confidence':'medium'}
    value['decoded_terms'][0]['candidates']=[{'official_title':full,'morphological_score':0.8}]
    seed(ctx,value)
    assert full in candidate_titles(ctx)
    output=pipe._context_to_output(ctx)
    payload=output.model_dump(mode='json')
    assert full in outward_titles(payload)
    wrapper=actual_main_sync_and_wrapper(payload,ctx.post_data)
    pipe.verify_final_source_context_serialization(output,payload,stage='normal_title_actual_main_sync')
    wrapped=wrapper(dict(ctx.post_data,comments=list(ctx.comments),analysis_result=payload),
                    output=output,verifier=pipe.verify_final_source_context_serialization)
    descriptor=build_publication_scope_descriptor(input_file_sha256=digest(ctx.post_data),post_ids=[ctx.post_id],
        config_hash='normal-title-candidate-preservation',release_fingerprint='candidate-only')
    path=tmp_path/'normal_publication.jsonl'
    registry=PublicationCommitRegistry(path,scope_descriptor=descriptor,create_new=True)
    _,created=commit_publication_result(wrapped,registry=registry,attempt_run_id='normal-title-synthetic',
                                        input_index=1,post_id=ctx.post_id)
    assert created
    saved=PublicationCommitRegistry(path,scope_descriptor=descriptor,create_new=False).result(ctx.post_id)
    assert saved['analysis_result']==payload
    wrapped.verify_stored_payload(saved,stage='normal_title_wal_readback')
    assert full in outward_titles(saved['analysis_result'])



def test_existing_multi_interpretation_and_best_match_do_not_bypass_source_check(tmp_path):
    pipe, ctx, _ = context(tmp_path, title='회모장 읽었다')
    full = '회귀물 모험가 장르(추정)'
    value = interpretation('회모장', full)
    value['decoded_terms'][0]['best_match'] = {'title': full, 'confidence': 'high'}
    value['decoded_terms'][0]['candidates'] = [{'official_title': full, 'morphological_score': 0.99}]
    ctx.suspected_titles = [{'title': full, 'confidence': 0.99, 'source_term': '회모장',
                            'source_expert': 'decoder_multi_interp'}]
    seed(ctx, value)
    assert ctx.suspected_titles == []
    assert pipe._is_unbound_title_meta_explanation(ctx, full) is True


def actual_main_sync_and_wrapper(payload, post):
    # 실제 main의 typed audit/sync/wrapper 함수만 로드한다. CLI 시작·모델 호출 없음.
    tree = ast.parse((ROOT / 'expert_main.py').read_text(encoding='utf8'))
    names = {'_runtime_candidate_audit_seed', '_sync_final_publication_ledger_contract',
             '_reapply_authoritative_publish_contract', '_sync_analysis_notes_to_final_publication',
             '_sync_reader_explanation_to_publish_contract'}
    selected = [x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name in names]
    assert {x.name for x in selected} == names
    wrapper = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == '_FinalSourceContextResult')
    exported = ('PUBLISH_CONTRACT_VERSION','candidate_inventory_evidence_from_sources','candidate_inventory_pairs',
                'candidate_inventory_records','EvidenceRecord','GroundingState','ScopeState','apply_publish_contract',
                'build_publish_ledger','evaluate_publish_contract','evidence_records_from_payload','grounding_state_from_dict')
    ns = {name: getattr(promotion_gate, name) for name in exported}
    ns.update(Any=Any, Dict=Dict, Mapping=Mapping, Callable=Callable, Optional=Optional, json=json, re=re)
    exec(compile(ast.Module(body=selected+[wrapper], type_ignores=[]), str(ROOT/'expert_main.py'), 'exec'), ns)
    ident = payload['identity']; assert has_authoritative_publish_contract(ident)
    seed_value = ns['_runtime_candidate_audit_seed'](ident, None); assert seed_value is None
    apply_candidate_audit_fields(ident, seed_value)
    # main:13958~13973의 텍스트 투영. 이미지 블록에는 text가 없을 수 있다.
    content = [b['text'] for b in post.get('content_blocks', []) if isinstance(b, dict) and b.get('text')]
    comments = [x.get('content', x.get('text','')) if isinstance(x,dict) else str(x)
                for x in post.get('comments_raw', [])]
    sync = dict(payload, title=post['title'], content=content, comments=comments,
                comment_context_lines=[], comment_dialogue_context_lines=[], _loop_projection_followup=None)
    ns['_sync_final_publication_ledger_contract'](sync, post_title=post['title'])
    assert 'publish_contract_integrity_error' not in ident
    return ns['_FinalSourceContextResult']


@pytest.mark.parametrize('index,variant', [(34,'current'),(35,'current')])
def test_saved_context_source_native_typed_writer_wal_without_hypothesis_roles(tmp_path, index, variant):
    fixture_before = FIXTURE.read_bytes()
    pipe, ctx, stored = context(tmp_path, index, variant)
    immutable_before = canonical({'post':ctx.post_data, 'comments':ctx.comments,
        'original_inputs':ctx._final_source_original_inputs,
        'original_comment_refs':ctx._final_source_original_comment_refs,
        'nsfw_carrier':ctx._source_bound_nsfw_original_carrier})
    stored_before = canonical(stored)
    decoded = copy.deepcopy(ctx.get_expert_output(ExpertType.DECODER))
    stored_ledger = stored['result']['analysis_result']['identity']['candidate_ledger']
    producer_fields = (('_candidate_producer_plans', 'candidate_producer_plans'),
                       ('_candidate_producer_receipts', 'candidate_producer_receipts'),
                       ('_candidate_generation_stage_receipts', 'candidate_stage_receipts'))
    # 이미 context()가 원본 관측을 복원한다. 누락을 허위 complete/False로 메우지 않는다.
    for attr, key in producer_fields:
        assert canonical(getattr(ctx, attr)) == canonical(stored_ledger[key])
    stored_stage_count = len(stored_ledger['candidate_stage_receipts'])
    seed(ctx, decoded)
    for attr, key in producer_fields[:2]:
        assert canonical(getattr(ctx, attr)) == canonical(stored_ledger[key])
    stages = ctx._candidate_generation_stage_receipts
    assert canonical(stages[:stored_stage_count]) == canonical(stored_ledger['candidate_stage_receipts'])
    assert len(stages) == stored_stage_count + 1
    assert stages[-1]['producer'] == 'decoder' and stages[-1]['stage'] == 'new_suspected_titles'
    # seed의 입력 설정이 끝난 뒤 working expert owner와 값을 관측한다.
    expert_owners = dict(ctx.expert_outputs)
    experts_before = copy.deepcopy(ctx.expert_outputs)
    output = pipe._context_to_output(ctx)
    payload = output.model_dump(mode='json')
    experts_after = copy.deepcopy(ctx.expert_outputs)
    observations = [{"expert": name, "before_sha256": digest(experts_before.get(name)),
        "after_sha256": digest(experts_after.get(name)),
        "changed": experts_before.get(name) != experts_after.get(name),
        "before": experts_before.get(name), "after": experts_after.get(name)}
        for name in sorted(set(experts_before) | set(experts_after))]
    # 실제 제품 후처리의 변경을 숨기거나 복원하지 않는다. 의미 수용은 아래 공개/role 검사가 담당한다.
    with (tmp_path/'working_expert_observation.json').open('x',encoding='utf8') as stream:
        json.dump({'observations': observations, 'working_mutation_accepted_as_semantic_repair': False},
                  stream, ensure_ascii=False, indent=2)
    assert set(ctx.expert_outputs) == set(expert_owners)
    assert all(ctx.expert_outputs[name] is owner for name, owner in expert_owners.items())
    assert canonical(stored) == stored_before
    assert canonical({'post':ctx.post_data, 'comments':ctx.comments,
        'original_inputs':ctx._final_source_original_inputs,
        'original_comment_refs':ctx._final_source_original_comment_refs,
        'nsfw_carrier':ctx._source_bound_nsfw_original_carrier}) == immutable_before
    assert ctx._final_source_projection_call_count == 1
    pipe.verify_final_source_context_serialization(output, payload, stage='surface_hypothesis_native')
    forbidden = {'아니'} if index == 34 else {
        x['value'] for t in decoded['decoded_terms'] if t['original'] == '회모장'
        for x in t.get('interpretations', []) if x.get('type') == 'novel_title'}
    ident = payload['identity']
    for field in ('title_candidates','recommendation_candidates','candidate_preservation_sources'):
        assert not forbidden & {x.get('official_title') for x in ident.get(field) or []}
    assert not forbidden & {x.get('candidate_title') for x in ident.get('promotion_gate_evidence') or []}
    assert not forbidden & {x.get('official_title') for x in payload['analysis'].get('detected_titles') or []}
    original_surface = '재획' if index == 34 else '회모장'
    assert original_surface in json.dumps(ident.get('candidate_preservation_sources'),ensure_ascii=False)
    stored_identity = stored['result']['analysis_result']['identity']
    # 모델 직렬화 직후에는 아직 실제 main의 observational audit가 실행되지 않았다.
    assert ident['candidate_generation_miss'] is None
    producer_before_main = canonical({key: ident['candidate_ledger'][key] for _, key in producer_fields})
    generation_before_main = canonical({key: ident['candidate_ledger'][key]
                                       for key in ('candidate_generation', 'candidate_generation_proof')})
    boundary_before = {'stage': 'MODEL_BEFORE_MAIN_AUDIT',
                      'candidate_generation_miss': ident['candidate_generation_miss'],
                      'candidate_ledger_status': ident['candidate_ledger_status']}
    for key in ('candidate_generation', 'candidate_generation_proof'):
        assert ident['candidate_ledger'][key]['status'] == stored_identity['candidate_ledger'][key]['status']
    assert ident['novel_identity'] is None
    assert ident['promotion_decision']['publish_allowed'] is False
    if index == 35:
        assert forbidden <= {x['text'] for x in ident['candidate_ledger']['title_meta_explanation_observations']}
    wrapper = actual_main_sync_and_wrapper(payload, ctx.post_data)
    # 동일한 최종 저장 경계끼리 비교한다. helper의 실제 audit/typed sync가 값을 산출한다.
    assert ident['candidate_generation_miss'] == stored_identity['candidate_generation_miss']
    assert type(ident['candidate_generation_miss']) is bool
    assert ident['candidate_generation_miss'] == (ident['candidate_ledger_status'] == 'candidate_generation_miss')
    assert canonical({key: ident['candidate_ledger'][key] for _, key in producer_fields}) == producer_before_main
    assert canonical({key: ident['candidate_ledger'][key]
                      for key in ('candidate_generation', 'candidate_generation_proof')}) == generation_before_main
    with (tmp_path/'candidate_audit_boundary_observation.json').open('x', encoding='utf8') as stream:
        json.dump({'index1':index, 'post_id':ctx.post_id, 'run_id':stored['run_id'], 'scope_id':stored['scope_id'],
            'stored_result_canonical_sha256':stored['result_canonical_sha256'],
            'before':boundary_before,
            'after':{'stage':'ACTUAL_MAIN_AUDIT_AND_TYPED_SYNC',
                     'candidate_generation_miss':ident['candidate_generation_miss'],
                     'candidate_ledger_status':ident['candidate_ledger_status']},
            'saved_candidate_generation_miss':stored_identity['candidate_generation_miss'],
            'producer_payload_sha256':hashlib.sha256(producer_before_main).hexdigest(),
            'generation_payload_sha256':hashlib.sha256(generation_before_main).hexdigest(),
            'candidate_completeness_claimed':False}, stream, ensure_ascii=False, indent=2)
    pipe.verify_final_source_context_serialization(output, payload, stage='surface_hypothesis_actual_main_sync')
    wrapped = wrapper(dict(ctx.post_data, comments=list(ctx.comments), analysis_result=payload),
                      output=output, verifier=pipe.verify_final_source_context_serialization)
    descriptor = build_publication_scope_descriptor(input_file_sha256=digest(ctx.post_data),
        post_ids=[ctx.post_id], config_hash='surface-hypothesis-partial-context', release_fingerprint='candidate-only')
    path = tmp_path/'publication.jsonl'
    registry = PublicationCommitRegistry(path, scope_descriptor=descriptor, create_new=True)
    commit, created = commit_publication_result(wrapped, registry=registry,
        attempt_run_id='surface-hypothesis-saved-context', input_index=1, post_id=ctx.post_id)
    assert created and commit.outcome == 'HOLD' and commit.publish_allowed is False
    readback = PublicationCommitRegistry(path, scope_descriptor=descriptor, create_new=False).result(ctx.post_id)
    assert readback['analysis_result'] == payload
    wrapped.verify_stored_payload(readback, stage='surface_hypothesis_wal_readback')
    assert FIXTURE.read_bytes() == fixture_before

@pytest.mark.parametrize('full', [
    '여러 장르 등의 약자 추정',
    '주무시기 전에 무엇을 하셨나요?(추정)',
    '나는 오늘도 살아간다.(추정)',
])
@pytest.mark.parametrize('branding', ['', '웹소설로 꿈꾸는 세상! - '])
def test_f4_existing_official_extraction_preserves_real_hypothesis_shaped_title(tmp_path,full,branding):
    pipe,ctx,_=context(tmp_path,title='별책 읽었다')
    url='https://novelpia.com/novel/934350'
    ctx.search_results=[{'url':url,'title':branding+full,'snippet':'웹소설 작품 상세'}]
    decoder=DecoderExpert(NoExternal())
    # 기존 공식 extractor와 checker 자체가 기대 근거다. 판단 함수를 stub하지 않는다.
    exact=[x for x in decoder._extract_official_titles_from_search(ctx) if x['title']==full and x['url']==url]
    assert exact
    assert pipe._has_official_title_evidence(ctx,full,allow_ocr_catalog=False,allow_live_fetch=False) is True
    value=interpretation('별책',full)
    value['decoded_terms'][0]['best_match']={'title':full,'confidence':'medium'}
    value['decoded_terms'][0]['candidates']=[{'official_title':full,'morphological_score':0.8}]
    before=canonical([ctx.post_data,ctx.comments,ctx.search_results,getattr(ctx,'fetched_page_info',None)])
    seed(ctx,value)
    assert full in candidate_titles(ctx)
    assert pipe._is_unbound_title_meta_explanation(ctx,full) is False
    titles,snapshot=pipe._build_title_candidates_with_snapshot(ctx=ctx,is_relevant=True,
        official_title=None,heretic_url=None,confidence='Low',vf_result={})
    assert full in {x.official_title for x in titles} | {x.get('official_title') for x in snapshot.retained_sources}
    assert before==canonical([ctx.post_data,ctx.comments,ctx.search_results,getattr(ctx,'fetched_page_info',None)])
    # 후보 보존을 원글 alias 관계나 공식 공개 허가로 표시하지 않는다.
    assert not any(x.get('text')==full for x in getattr(ctx,'_title_meta_explanation_observations',()))


@pytest.mark.parametrize('mode', ['different_title','listing','spoofed_host','generated','diagnostic','ocr',
                                  'suffix_host','userinfo_host','non_http'])
def test_f4_invalid_or_generated_official_metadata_does_not_rescue_gloss(tmp_path,mode):
    pipe,ctx,_=context(tmp_path,title='회모장 읽었다')
    full='회귀물 모험가 장르(추정)'
    row={'url':'https://novelpia.com/novel/934350','title':'웹소설로 꿈꾸는 세상! - '+full}
    if mode=='different_title':row['title']='웹소설로 꿈꾸는 세상! - 바닷가의 겨울 일기'
    if mode=='listing':row['url']='https://novelpia.com/search'
    if mode=='spoofed_host':row['url']='https://novelpia.com.example.org/novel/934350'
    if mode=='generated':row['source_tier']='llm_only'
    if mode=='diagnostic':row['_ocr_diagnostic_only']=True
    if mode=='ocr':row['from_ocr']=True
    if mode=='suffix_host':row['url']='https://notnovelpia.com/novel/934350'
    if mode=='userinfo_host':row['url']='https://novelpia.com@elsewhere.example/novel/934350'
    if mode=='non_http':row['url']='ftp://novelpia.com/novel/934350'
    ctx.search_results=[row]
    before=canonical([ctx.search_results,getattr(ctx,'fetched_page_info',None)])
    seed(ctx,interpretation('회모장',full))
    assert full not in candidate_titles(ctx)
    assert pipe._is_unbound_title_meta_explanation(ctx,full) is True
    assert before==canonical([ctx.search_results,getattr(ctx,'fetched_page_info',None)])


@pytest.mark.parametrize('page_type,content_status', [
    ('novel_page','deleted'),('listing','active'),('community_post','active'),
])
def test_f4_consumer_keeps_existing_negative_official_page_state(tmp_path,page_type,content_status):
    pipe,ctx,_=context(tmp_path,title='별책 읽었다')
    full='여러 장르 등의 약자 추정';url='https://novelpia.com/novel/934350'
    ctx.search_results=[{'url':url,'title':'웹소설로 꿈꾸는 세상! - '+full}]
    ctx.fetched_page_info=[{'url':url,'title':full,'structured_info':{
        'title':full,'page_type':page_type,'content_status':content_status}}]
    before=canonical([ctx.search_results,getattr(ctx,'fetched_page_info',None)])
    assert pipe._has_official_title_evidence(ctx,full,allow_ocr_catalog=False,allow_live_fetch=False) is False
    assert pipe._is_unbound_title_meta_explanation(ctx,full) is True
    assert before==canonical([ctx.search_results,getattr(ctx,'fetched_page_info',None)])


@pytest.mark.parametrize('mode', ['manga','derivative'])
def test_f4_consumer_does_not_replace_existing_media_and_derivative_guards(tmp_path,mode):
    pipe,ctx,_=context(tmp_path,title='별책 읽었다')
    full='여러 장르 등의 약자 추정'
    row={'url':'https://ridibooks.com/books/1019005884','title':full,'media_type':'manga'}
    if mode=='derivative':
        row={'url':'https://novelpia.com/novel/934350',
             'title':f'[{full}] 별개의 모험', 'snippet':'원작 소설 기반 패러디 팬픽'}
    ctx.search_results=[row]
    assert pipe._has_official_title_evidence(ctx,full,allow_ocr_catalog=False,allow_live_fetch=False) is False
    assert pipe._is_unbound_title_meta_explanation(ctx,full) is True


def test_f4_filtered_observation_view_retains_negative_rows_without_mutating_context(tmp_path):
    from llm_batch.grounding.source_title_hypothesis import title_hypothesis_observation_context
    _,ctx,_=context(tmp_path,title='별책 읽었다')
    ctx.search_results=[{'url':'https://novelpia.com/novel/1','title':'참조 표제'},
                        {'url':'https://novelpia.com/novel/2','title':'모형 표제','source_tier':'llm_only'}]
    ctx.fetched_page_info=[{'url':'https://novelpia.com/novel/1','structured_info':{'content_status':'deleted'}},
                           {'url':'https://novelpia.com/novel/3','from_ocr':True}]
    before=canonical([ctx.search_results,ctx.fetched_page_info,ctx.post_data,ctx.comments])
    view=title_hypothesis_observation_context(ctx)
    assert view is not ctx and len(view.search_results)==1 and len(view.fetched_page_info)==1
    assert view.fetched_page_info[0]['structured_info']['content_status']=='deleted'
    assert before==canonical([ctx.search_results,ctx.fetched_page_info,ctx.post_data,ctx.comments])


@pytest.mark.parametrize('title,body,expected', [
    ('판초 무서우..', ['척추를 데드스페이스 리퍼로 상상하고 읽으니까 몰입이 심해졌어'], '판초'),
    ('판초법사 경찰력 사용하면서도 1달 이상 정보통제가 가능함?',
     ['전국 경찰력 다 동원하는데 소문이 안날수가 있나?'], '판초법사'),
    ('아생갤 개 재밌네', ['소설 읽고 있다'], '아생갤'),
    ('저기', ['소설 저기를 읽었다'], '저기'),
])
def test_low_alias_hold_keeps_original_nominal_recall_without_registry_or_public_authority(tmp_path,title,body,expected):
    pipe,ctx,_=context(tmp_path,title=title,body=body)
    before=canonical([ctx.post_data,ctx.comments,ctx._final_source_original_inputs])
    candidates=pipe._collect_short_alias_hold_candidates(ctx)
    assert [item.official_title for item in candidates]==[expected]
    assert all(item.confidence=='Low' and item.reference_role=='candidate' for item in candidates)
    assert before==canonical([ctx.post_data,ctx.comments,ctx._final_source_original_inputs])
