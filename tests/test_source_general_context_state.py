"""현재55/70/77 저장 입력의 일반 문맥 상태 수리. 외부 실행·사람 정답을 만들지 않는다."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import pytest
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import PostInput
from llm_batch.experts.orchestrator import ConversationContext, ExpertType
from llm_batch.ledger.publication_commit import PublicationCommitRegistry, build_publication_scope_descriptor, commit_publication_result
from test_source_bound_propriety_question_state import NoExternal, synchronize_like_actual_main, wrapper_class

FIXTURE=Path(__file__).parent/'fixtures/actual80_run233800_general_state_saved_experts.json'
def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()
def context(tmp_path,index,mutate=None):
    fixture=json.loads(FIXTURE.read_bytes())
    assert fixture['scope']=='SAVED_EXPERTS_AND_CATALOG_PARTIAL_CONTEXT_NOT_ORIGINAL_MEMORY'
    row=copy.deepcopy(fixture['rows'][str(index)])
    p=row['packet']
    assert digest({'post':p['source_post'],'comments':p['source_comments']})==row['source_canonical_sha256']
    assert digest(p['checkpoint_result'])==row['result_canonical_sha256']
    assert row['experts']=={entry['expert']:entry['value'] for entry in row['expert_stream']}
    if mutate: mutate(row)
    post=PostInput(**row['post'],comments=row['comments'])
    pipe=AgenticPipeline(llm=NoExternal(),mcp=NoExternal(),output_dir=tmp_path,max_iterations=1,native_recovery=True)
    pipe.enable_url_fetch_disk_cache=False
    pipe._use_session_knowledge=False
    ctx=ConversationContext(post_id=post.post_id,post_data=pipe._post_to_dict(post),comments=pipe._extract_comments(post))
    ctx._final_source_original_inputs=pipe._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs=tuple(post.comments)
    ctx._source_bound_nsfw_original_carrier=pipe._capture_source_bound_nsfw_carrier(post)
    for name,value in row['experts'].items(): ctx.set_expert_output(ExpertType(name),copy.deepcopy(value))
    ctx.search_results=copy.deepcopy(row['catalog'])
    ledger=p['checkpoint_result']['analysis_result']['identity']['candidate_ledger']
    for attr,key in (('_candidate_producer_plans','candidate_producer_plans'),
        ('_candidate_producer_receipts','candidate_producer_receipts'),('_candidate_generation_stage_receipts','candidate_stage_receipts')):
        setattr(ctx,attr,copy.deepcopy(ledger.get(key,[])))
    disc=row['experts']['discourse']['discourse_analysis']
    ctx.primary_domain=disc['primary_domain'];ctx.discourse_intent=disc['intent']
    return pipe,ctx,row

def serialize(pipe,ctx):
    before=canonical({'post':ctx.post_data,'comments':ctx.comments})
    output=pipe._context_to_output(ctx)
    payload=output.model_dump(mode='json')
    pipe.verify_final_source_context_serialization(output,payload,stage='general_state_candidate')
    assert canonical({'post':ctx.post_data,'comments':ctx.comments})==before
    assert ctx._final_source_projection_call_count==1
    return output,payload

@pytest.mark.parametrize('index',[55,70,77])
def test_current_general_context_states_real_main_wrapper_wal(tmp_path,index):
    fixture_bytes=FIXTURE.read_bytes()
    pipe,ctx,row=context(tmp_path,index)
    mode='nonwork_comparison' if index==55 else 'genre_context'
    experts_before=canonical({k.value:ctx.get_expert_output(k) for k in ExpertType})
    inputs=pipe._general_context_state_inputs(ctx,mode)
    assert inputs is not None
    assert canonical({k.value:ctx.get_expert_output(k) for k in ExpertType})==experts_before
    output,payload=serialize(pipe,ctx)
    ident=payload['identity'];old=row['packet']['checkpoint_result']['analysis_result']
    assert ident['is_relevant'] is False and ident['is_novel_related'] is (index!=55)
    assert ident['title_resolution_state']=='context_only' and ident['work_resolution']=='none'
    assert ident['title_resolution_allowed'] is False and ident['promotion_decision']['publish_allowed'] is False
    assert ident['novel_identity'] is None
    assert (ident['discussion_type'],ident['subtype'],ident['topicality'],ident['relevance_scope'])==(
        ('noise','other_quarantine','unrelated','off_topic') if index==55 else
        ('trope_discussion','genre_trope_discussion','adjacent_relevant','adjacent'))
    assert payload['analysis']['is_nsfw']==old['analysis']['is_nsfw']
    assert payload['analysis']['nsfw_assessment_status']==old['analysis']['nsfw_assessment_status']
    for key in ('candidate_generation','candidate_generation_proof'):
        assert ident['candidate_ledger'][key]['status']==old['identity']['candidate_ledger'][key]['status']
    binding=ctx._general_context_state_evidence
    assert binding['mode']==mode and binding['verify']() is True
    assert binding['publication_authority'] is False and binding['candidate_completeness_claimed'] is False
    assert output.__dict__['_final_source_context_receipt']['general_context_state_binding'] is binding
    before=copy.deepcopy(ident['promotion_decision'])
    synchronize_like_actual_main(payload,ctx.post_data)
    assert ident['promotion_decision']==before
    assert ident['novel_identity']=={'official_title':None,'heretic_url':None}
    pipe.verify_final_source_context_serialization(output,payload,stage='general_state_actual_main')
    full=dict(row['post'],comments=row['comments'],analysis_result=payload,run_meta={'local_test':True})
    wrapped=wrapper_class()(full,output=output,verifier=pipe.verify_final_source_context_serialization)
    descriptor=build_publication_scope_descriptor(input_file_sha256=row['source_canonical_sha256'],post_ids=[ctx.post_id],
        config_hash='general-context-saved-source',release_fingerprint='candidate-only')
    path=tmp_path/'publication.jsonl'
    registry=PublicationCommitRegistry(path,scope_descriptor=descriptor,create_new=True)
    commit,created=commit_publication_result(wrapped,registry=registry,attempt_run_id='general-current-local',input_index=1,post_id=ctx.post_id)
    assert created and commit.outcome=='HOLD' and commit.publish_allowed is False
    stored=PublicationCommitRegistry(path,scope_descriptor=descriptor,create_new=False).result(ctx.post_id)
    wrapped.verify_stored_payload(stored,stage='general_state_wal_readback')
    assert stored['analysis_result']==payload
    assert FIXTURE.read_bytes()==fixture_bytes

@pytest.mark.parametrize('kind',['known_alias','ordinary_noun_official','raw_link','title_declaration','strong_decoder','specific_relation','nonboolean','work_slang','foreign_carrier','quoted_source','comment','image'])
def test_nonwork_comparison_does_not_override_real_work_evidence(tmp_path,kind):
    def mutate(row):
        if kind in {'known_alias','ordinary_noun_official'}:
            title='아생갤vs회귀수선전' if kind=='known_alias' else '별의 길vs푸른 밤'
            row['post']['title']=title
            g=row['experts']['gatekeeper'];g['detected_entities']['possible_titles']=[title]
            g['context_clues']['short_post_title_surface']=title
            row['experts']['verifier']['verification_result']['grounding_check']['anchor_text']=title
            row['experts']['decoder']['decoded_terms'][0]['original']=title
            if kind=='ordinary_noun_official':
                row['catalog'].append({'title':'별의 길','url':'https://novelpia.com/novel/123'})
        elif kind=='raw_link':row['post']['content_blocks'][0]['text']='https://novelpia.com/novel/123'
        elif kind=='title_declaration':row['post']['content_blocks'][0]['text']='장수풍뎅이는 소설 작품 제목이다.'
        elif kind=='strong_decoder':row['experts']['decoder']['decoded_terms'][0]['best_match']['confidence']='high'
        elif kind=='specific_relation':row['experts']['verifier']['verification_result']['relation_judgment']={'discussion_target':'specific_work','post_direct_grounding':True}
        elif kind=='nonboolean':row['experts']['verifier']['verification_result']['is_relevant']=0
        elif kind=='work_slang':row['experts']['verifier']['verification_result']['slang_insight']={'alias_scope':'pure_work_alias','canonical_work_alias':'가상 작품'}
        elif kind=='quoted_source':row['post']['title']='「'+row['post']['title']+'」'
        elif kind=='comment':row['comments']=[{'content':'작품명은 별의 길','comment_id':'own-1','post_id':row['post']['post_id']}]
        elif kind=='image':row['post']['content_blocks'].append({'type':'image','url':'https://fixture.invalid/work.png'})
    pipe,ctx,_=context(tmp_path,55,mutate)
    if kind=='foreign_carrier':ctx._final_source_original_inputs=()
    assert pipe._general_context_state_inputs(ctx,'nonwork_comparison') is None

@pytest.mark.parametrize('index',[70,77])
@pytest.mark.parametrize('kind',['work_title','known_alias','title_query','recommendation','raw_link','specific_relation','decoder_work','source_mismatch','grounded_work'])
def test_genre_discussion_with_specific_work_cannot_use_general_state(tmp_path,index,kind):
    def mutate(row):
        if kind=='work_title':
            row['post']['content_blocks'][0]['text']+=' 별의 길'
            row['catalog'].append({'title':'별의 길','url':'https://novelpia.com/novel/123'})
        elif kind=='known_alias':row['post']['content_blocks'][0]['text']+=' 아생갤'
        elif kind=='title_query':row['post']['content_blocks'][0]['text']+=' 소설 제목이 뭐임?'
        elif kind=='recommendation':row['post']['content_blocks'][0]['text']+=' 비슷한 작품 추천 좀'
        elif kind=='raw_link':row['post']['content_blocks'][0]['text']+=' https://novelpia.com/novel/123'
        elif kind=='specific_relation':
            row['experts']['verifier']={'verification_result':{'is_relevant':False,'is_novel_discussion':False,
                'relation_judgment':{'discussion_target':'specific_work','post_direct_grounding':True}}}
        elif kind=='grounded_work':
            row['experts']['verifier']={'verification_result':{'is_relevant':False,'is_novel_discussion':False,'grounding_check':{'decoder_grounded':True,'anchor_found':'character_mention','anchor_text':'실제 인물'}}}
        elif kind=='decoder_work':
            row['experts']['decoder']={'needs_verification':False,'unresolved_terms':[],
                'decoded_terms':[{'original':'가상 작품','is_author_name':False,'best_match':{'title':'가상 작품','confidence':'high'},'interpretations':[{'type':'novel_title','value':'가상 작품','context_fit':'high'}],'candidates':[]}]}
    pipe,ctx,_=context(tmp_path,index,mutate)
    if kind=='source_mismatch':ctx.post_data['content_blocks'][0]['text']+=' 변경'
    assert pipe._general_context_state_inputs(ctx,'genre_context') is None

@pytest.mark.parametrize('index',[55,70,77])
@pytest.mark.parametrize('kind',['raw_source','catalog_value','catalog_owner','expert_value','native','title_state','broad_type','topicality','contract'])
def test_general_state_same_source_contract_and_wire_cannot_drift(tmp_path,index,kind):
    pipe,ctx,_=context(tmp_path,index)
    output,payload=serialize(pipe,ctx);altered=copy.deepcopy(payload)
    if kind=='raw_source':ctx.post_data['title']+=' 변경'
    elif kind=='catalog_value':ctx.search_results.append({'title':'추가','url':'https://fixture.invalid/new'})
    elif kind=='catalog_owner':ctx.search_results=copy.deepcopy(ctx.search_results)
    elif kind=='expert_value':ctx.get_expert_output(ExpertType.DISCOURSE)['discourse_analysis']['intent']='discuss_work'
    elif kind=='native':ctx.__dict__.pop('_final_source_projection_native')
    elif kind=='title_state':altered['identity']['title_resolution_state']='unresolved_matchable'
    elif kind=='broad_type':altered['identity']['is_novel_related']=int(index!=55)
    elif kind=='topicality':altered['identity']['topicality']='core_relevant'
    else:altered['identity']['publish_contract_input_fingerprint']='changed'
    with pytest.raises(ValueError):pipe.verify_final_source_context_serialization(output,altered,stage='general_state_tamper_'+kind)

@pytest.mark.parametrize('index',[55,70,77])
def test_unrelated_search_is_preserved_but_does_not_own_specific_work_state(tmp_path,index):
    pipe,ctx,_=context(tmp_path,index)
    ctx.search_results.append({'title':'아주 먼 바다의 마법사','url':'https://novelpia.com/novel/777','snippet':'원문의 표면 및 명명 관계가 없는 별도 작품 소개'})
    source_before=canonical(ctx.search_results)
    evidence=pipe._source_bound_general_context_state(ctx,'nonwork_comparison' if index==55 else 'genre_context')
    assert evidence is not None and evidence['verify']() is True
    assert canonical(ctx.search_results)==source_before
    assert evidence['publication_authority'] is False and evidence['candidate_completeness_claimed'] is False


@pytest.mark.parametrize('index',[55,70,77])
@pytest.mark.parametrize('field',['page_title','structured_title','structured_page_title','structured_llm_identified_title'])
@pytest.mark.parametrize('matching',[True,False])
def test_official_fetch_nested_title_preserves_competing_source_work(tmp_path,index,field,matching):
    # 대조 입력은 먼저 guard 양성임을 확인한다. 원문/carrier는 변경하지 않는다.
    pipe,ctx,row=context(tmp_path/'baseline',index)
    mode='nonwork_comparison' if index==55 else 'genre_context'
    assert pipe._general_context_state_inputs(ctx,mode) is not None
    title=row['post']['title'] if matching else '먼바다기록집'
    entry={'url':'https://novelpia.com/novel/934357','title':'웹소설로 꿈꾸는 세상!'}
    if field=='page_title':entry['page_title']=title
    else:entry['structured_info']={field.removeprefix('structured_'):title}
    ctx.fetched_page_info=[entry]
    before=canonical([ctx.post_data,ctx.comments,ctx.search_results,ctx.fetched_page_info])
    evidence=pipe._general_context_state_inputs(ctx,mode)
    assert (evidence is None) is matching
    assert canonical([ctx.post_data,ctx.comments,ctx.search_results,ctx.fetched_page_info])==before


@pytest.mark.parametrize('index', [55, 70, 77])
def test_general_entry_preserves_raw_arbiter_and_verifier_after_real_main(tmp_path, index):
    pipe, ctx, _ = context(tmp_path, index)
    owners = {kind: ctx.get_expert_output(kind) for kind in (ExpertType.ARBITER, ExpertType.VERIFIER)}
    before = canonical({kind.value: value for kind, value in owners.items()})
    output, payload = serialize(pipe, ctx)
    assert all(ctx.get_expert_output(kind) is value for kind, value in owners.items())
    assert canonical({kind.value: ctx.get_expert_output(kind) for kind in owners}) == before
    if index != 77:  # 77은 저장된 early-genre 경로로 두 전문가 출력 자체가 없다.
        for kind, key in ((ExpertType.ARBITER, 'final_decision'), (ExpertType.VERIFIER, 'verification_result')):
            verdict = ctx.get_expert_output(kind)[key]
            assert verdict['is_relevant'] is False and verdict['is_novel_discussion'] is False
    binding = output.__dict__['_final_source_context_receipt']['general_context_state_binding']
    assert binding is ctx._general_context_state_evidence and binding['verify']() is True
    assert payload['identity']['is_relevant'] is False
    assert payload['identity']['primary_work'] is None
    assert payload['identity']['promotion_decision']['publish_allowed'] is False


@pytest.mark.parametrize('index', [55, 70, 77])
@pytest.mark.parametrize('kind', ['catalog_value', 'catalog_owner', 'source_work', 'expert_value', 'raw_source'])
def test_general_entry_cannot_rebase_changed_inputs(tmp_path, index, kind):
    pipe, ctx, _ = context(tmp_path, index)
    mode = 'nonwork_comparison' if index == 55 else 'genre_context'
    bound = pipe._source_bound_general_context_state(ctx, mode)
    assert bound is not None and bound['verify']() is True
    old_sha = bound['input_sha256']
    if kind == 'catalog_value':
        ctx.search_results.append({'title': '추가 자료', 'url': 'https://fixture.invalid/extra'})
    elif kind == 'catalog_owner':
        ctx.search_results = copy.deepcopy(ctx.search_results)
    elif kind == 'source_work':
        ctx.fetched_page_info = [{'url': 'https://novelpia.com/novel/934357',
            'structured_info': {'title': ctx.post_data['title']}}]
        assert pipe._general_context_state_inputs(ctx, mode) is None
    elif kind == 'expert_value':
        ctx.get_expert_output(ExpertType.DISCOURSE)['discourse_analysis']['intent'] = 'discuss_work'
    else:
        ctx.post_data['title'] += ' 변경'
    assert bound['verify']() is False and bound['input_sha256'] == old_sha


@pytest.mark.parametrize('index', [55, 70, 77])
def test_scope_without_entry_cannot_capture_late_general_authority(tmp_path, index):
    pipe, ctx, _ = context(tmp_path, index)
    mode = 'nonwork_comparison' if index == 55 else 'genre_context'
    proof = pipe._source_bound_general_context_state(ctx, mode)
    assert proof is not None
    expected = proof['expected_state']
    pipe._derive_resolution_scope_fields(ctx=ctx, is_relevant=False, official_title=None,
        discussion_type=expected[1], topicality=expected[3], subtype=expected[2],
        work_resolution='none', verification_result=(ctx.get_expert_output(ExpertType.VERIFIER) or {}).get('verification_result'),
        final_decision=(ctx.get_expert_output(ExpertType.ARBITER) or {}).get('final_decision'))
    assert ctx.__dict__.get('_general_context_state_evidence') is None


@pytest.mark.parametrize('kind', ['source_work', 'alias_relation', 'raw_arbiter', 'catalog_owner'])
def test_real_main_rejects_new_evidence_between_entry_adoption_and_scope(tmp_path, monkeypatch, kind):
    # 결함 주입 뒤 실제 메서드를 그대로 호출한다. 성공 반환값/검증 결과를 대체하지 않는다.
    pipe, ctx, _ = context(tmp_path, 70)
    real_derive = pipe._derive_resolution_scope_fields
    seen = []
    def inject_then_derive(**kwargs):
        bound = kwargs['general_context_entry']
        assert bound is not None and bound['context'] is ctx and bound['verify']() is True
        seen.append(bound)
        if kind == 'source_work':
            ctx.fetched_page_info = [{'url': 'https://novelpia.com/novel/934357',
                'structured_info': {'title': ctx.post_data['title']}}]
        elif kind == 'alias_relation':
            ctx.get_expert_output(ExpertType.VERIFIER)['verification_result']['relation_judgment'] = {
                'discussion_target': 'specific_work', 'post_direct_grounding': True}
        elif kind == 'raw_arbiter':
            ctx.get_expert_output(ExpertType.ARBITER)['final_decision']['is_relevant'] = True
        else:
            ctx.search_results = copy.deepcopy(ctx.search_results)
        return real_derive(**kwargs)
    monkeypatch.setattr(pipe, '_derive_resolution_scope_fields', inject_then_derive)
    with pytest.raises(ValueError, match='general context entry changed before scope adoption'):
        pipe._context_to_output(ctx)
    assert len(seen) == 1 and seen[0]['verify']() is False
    assert ctx.__dict__.get('_general_context_state_evidence') is None


def test_general_entry_from_another_context_cannot_bind_scope(tmp_path):
    pipe, ctx, _ = context(tmp_path/'one', 70)
    _, other, _ = context(tmp_path/'two', 70)
    bound = pipe._source_bound_general_context_state(other, 'genre_context')
    assert bound is not None and bound['verify']() is True
    with pytest.raises(ValueError, match='general context entry changed before scope adoption'):
        pipe._derive_resolution_scope_fields(ctx=ctx, is_relevant=False, official_title=None,
            discussion_type='trope_discussion', topicality='adjacent_relevant', subtype='genre_trope_discussion',
            work_resolution='none', verification_result=ctx.get_expert_output(ExpertType.VERIFIER)['verification_result'],
            final_decision=ctx.get_expert_output(ExpertType.ARBITER)['final_decision'], general_context_entry=bound)


def test_existing_surface_binding_keeps_priority_and_original_identity(tmp_path):
    from test_source_bound_surface_title_state import context as surface_context
    pipe, ctx, _ = surface_context(tmp_path)
    vr = ctx.get_expert_output(ExpertType.VERIFIER)['verification_result']
    fd = ctx.get_expert_output(ExpertType.ARBITER)['final_decision']
    assert pipe._surface_title_anchor_inputs(ctx, vr, fd) is not None
    output, payload = serialize(pipe, ctx)
    assert ctx.__dict__.get('_general_context_state_evidence') is None
    assert ctx._surface_title_anchor_evidence['verify']() is True
    assert output.__dict__['_final_source_context_receipt']['surface_title_anchor_binding'] is ctx._surface_title_anchor_evidence
    assert payload['identity']['is_relevant'] is False
    assert payload['identity']['is_novel_related'] is False
    assert ctx.post_data['title'] in payload['analysis']['notes']
