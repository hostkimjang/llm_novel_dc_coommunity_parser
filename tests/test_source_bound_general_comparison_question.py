"""실제 A/A 일반 비교 질문의 상태·계약·WAL 회귀. 모델·네트워크 실행 없음."""
from __future__ import annotations
import copy,hashlib,json,socket
from pathlib import Path
from types import MethodType
import pytest
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import PostInput
from llm_batch.experts.orchestrator import ConversationContext,ExpertType
from llm_batch.ledger.publication_commit import PublicationCommitRegistry,build_publication_scope_descriptor,commit_publication_result
from test_source_bound_propriety_question_state import NoExternal,synchronize_like_actual_main,wrapper_class

FIXTURE=Path(__file__).parent/'fixtures/row55_aa_saved_general_question.json'

def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def baseline_helper():
    baseline=json.loads(FIXTURE.read_text('utf-8'))['baseline_helper']
    assert hashlib.sha256(baseline['source'].encode()).hexdigest()==baseline['sha256']
    namespace=dict(AgenticPipeline._general_context_state_inputs.__globals__)
    exec(compile('from __future__ import annotations\n'+baseline['source'],'pinned_row55_pre_fix_general_context','exec'),namespace)
    return namespace['_general_context_state_inputs']

BASELINE=baseline_helper()

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('NETWORK_FORBIDDEN_IN_ROW55_REPLAY')
    monkeypatch.setattr(socket.socket,'connect',forbidden)

def context(tmp_path,arm='after',post_id=9426461,mutate=None):
    fixture=json.loads(FIXTURE.read_text('utf-8'))
    assert fixture['scope']=='SAVED_EXPERTS_AND_CATALOG_PARTIAL_CONTEXT_NOT_ORIGINAL_MEMORY'
    row=copy.deepcopy(next(row for row in fixture['rows'] if row['arm']==arm and row['post_id']==post_id))
    assert hashlib.sha256(canonical({'post':row['post'],'comments':row['comments']})).hexdigest()==row['source_canonical_sha256']
    assert hashlib.sha256(canonical(row['experts'])).hexdigest()==row['experts_canonical_sha256']
    assert hashlib.sha256(canonical(row['catalog'])).hexdigest()==row['catalog_canonical_sha256']
    if mutate:mutate(row)
    raw=copy.deepcopy(row['post']);raw['comments']=copy.deepcopy(row['comments'])
    post=PostInput(**raw)
    pipe=AgenticPipeline(llm=NoExternal(),mcp=NoExternal(),output_dir=tmp_path,max_iterations=1,native_recovery=True)
    pipe.enable_url_fetch_disk_cache=False;pipe._use_session_knowledge=False
    ctx=ConversationContext(post_id=post.post_id,post_data=pipe._post_to_dict(post),comments=pipe._extract_comments(post))
    ctx._final_source_original_inputs=pipe._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs=tuple(post.comments)
    ctx._source_bound_nsfw_original_carrier=pipe._capture_source_bound_nsfw_carrier(post)
    for name,value in row['experts'].items():ctx.set_expert_output(ExpertType(name),copy.deepcopy(value))
    ctx.search_results=copy.deepcopy(row['catalog'])
    ledger=row['candidate_provenance']
    for attr,key in (('_candidate_producer_plans','candidate_producer_plans'),('_candidate_producer_receipts','candidate_producer_receipts'),('_candidate_generation_stage_receipts','candidate_stage_receipts')):
        setattr(ctx,attr,copy.deepcopy(ledger.get(key,[])))
    disc=row['experts']['discourse']['discourse_analysis'];ctx.primary_domain=disc['primary_domain'];ctx.discourse_intent=disc['intent']
    return pipe,ctx,row

def source_and_experts(ctx):
    return canonical({'post':ctx.post_data,'comments':ctx.comments,'experts':{k.value:ctx.get_expert_output(k) for k in ExpertType},'catalog':ctx.search_results})

def serialize(pipe,ctx):
    before=source_and_experts(ctx)
    output=pipe._context_to_output(ctx);payload=output.model_dump(mode='json')
    pipe.verify_final_source_context_serialization(output,payload,stage='row55_candidate')
    assert source_and_experts(ctx)==before
    return output,payload

def test_actual_after_baseline_failure_and_candidate_scope_without_input_mutation(tmp_path):
    pipe,ctx,row=context(tmp_path)
    before=source_and_experts(ctx)
    assert BASELINE(pipe,ctx,'nonwork_comparison') is None
    evidence=pipe._general_context_state_inputs(ctx,'nonwork_comparison')
    assert evidence is not None
    assert source_and_experts(ctx)==before
    assert ctx.get_expert_output(ExpertType.DECODER)['needs_verification'] is True

def test_actual_after_full_scope_native_main_wrapper_wal(tmp_path):
    baseline,old_ctx,row=context(tmp_path/'baseline')
    baseline._general_context_state_inputs=MethodType(BASELINE,baseline)
    old_output,old=serialize(baseline,old_ctx)
    assert old['identity']['is_novel_related'] is True
    assert old['identity']['title_resolution_state']=='unresolved_matchable'
    pipe,ctx,row=context(tmp_path/'candidate')
    output,payload=serialize(pipe,ctx);ident=payload['identity']
    assert (ident['is_relevant'],ident['is_novel_related'],ident['work_resolution'],ident['title_resolution_state'])==(False,False,'none','context_only')
    assert (ident['discussion_type'],ident['topicality'],ident['relevance_scope'])==('noise','unrelated','off_topic')
    assert ident['promotion_decision']['publish_allowed'] is False and ident['title_resolution_allowed'] is False
    assert ident['novel_identity'] is None
    assert old['analysis']['is_nsfw']==payload['analysis']['is_nsfw']
    assert old['analysis']['nsfw_assessment_status']==payload['analysis']['nsfw_assessment_status']
    bound=ctx._general_context_state_evidence
    assert bound['verify']() is True and bound['publication_authority'] is False and bound['candidate_completeness_claimed'] is False
    assert ctx.__dict__.get('_surface_title_anchor_evidence') is None
    old_contract=copy.deepcopy(ident['promotion_decision'])
    synchronize_like_actual_main(payload,ctx.post_data)
    assert ident['novel_identity']=={'official_title':None,'heretic_url':None}
    assert ident['promotion_decision']==old_contract
    pipe.verify_final_source_context_serialization(output,payload,stage='row55_main_projection')
    input_hash=hashlib.sha256(canonical({'post':row['post'],'comments':row['comments']})).hexdigest()
    descriptor=build_publication_scope_descriptor(input_file_sha256=input_hash,post_ids=[ctx.post_id],config_hash='row55-candidate-local',release_fingerprint='offline-replay')
    path=tmp_path/'publication.jsonl';registry=PublicationCommitRegistry(path,scope_descriptor=descriptor,create_new=True)
    full=dict(row['post'],comments=row['comments'],analysis_result=payload,run_meta={'local_replay':True})
    wrapped=wrapper_class()(full,output=output,verifier=pipe.verify_final_source_context_serialization)
    commit,created=commit_publication_result(wrapped,registry=registry,attempt_run_id='row55-candidate',input_index=1,post_id=ctx.post_id)
    assert created and commit.outcome=='HOLD' and commit.publish_allowed is False
    stored=PublicationCommitRegistry(path,scope_descriptor=descriptor,create_new=False).result(ctx.post_id)
    wrapped.verify_stored_payload(stored,stage='row55_local_wal')
    assert stored['analysis_result']==payload
    fields=('is_relevant','is_novel_related','work_resolution','title_resolution_state','discussion_type','topicality','relevance_scope','novel_identity')
    receipt={'scope':'SAVED_EXPERTS_PARTIAL_CONTEXT_LOCAL_REPLAY_NOT_ACTUAL_NEW_RUN',
        'post_id':ctx.post_id,'replayed_input_canonical_sha256':input_hash,
        'baseline':{k:old['identity'].get(k) for k in fields},
        'candidate_after_main':{k:payload['identity'].get(k) for k in fields},
        'wal':{k:stored['analysis_result']['identity'].get(k) for k in fields},
        'commit':commit.to_dict(),'source_experts_unchanged':True,
        'general_binding_verified':bound['verify']() is True,'old_surface_binding_applied':False,
        'publication_authority':False,'candidate_completeness_claimed':False,'model_api_calls':0}
    (tmp_path/'stage_readback.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

@pytest.mark.parametrize('arm',['before','after'])
@pytest.mark.parametrize('post_id',[9727547,8981568])
def test_actual_work_questions_remain_outside_nonwork_repair(tmp_path,arm,post_id):
    pipe,ctx,row=context(tmp_path,arm,post_id)
    before=source_and_experts(ctx)
    assert BASELINE(pipe,ctx,'nonwork_comparison') is None
    assert pipe._general_context_state_inputs(ctx,'nonwork_comparison') is None
    assert source_and_experts(ctx)==before

def test_before55_keeps_context_only(tmp_path):
    pipe,ctx,row=context(tmp_path,'before')
    output,payload=serialize(pipe,ctx)
    assert payload['identity']['title_resolution_state']=='context_only'
    assert payload['identity']['is_novel_related'] is False

@pytest.mark.parametrize('kind',['missing_receipt','wrong_span','comment_source','foreign_speaker','wrong_position','bool_position','conflict','unverified','target_mismatch','multiple_targets','work_target','specific_relation','positive_verifier','positive_arbiter','nonboolean_verdict','unresolved_decoder','strong_decoder','not_high_general','strong_echo','decoder_request_not_boolean','official_matching','actual_title_url','author','character','comment','image','carrier_mismatch'])
def test_question_receipt_and_work_competition_remain_required(tmp_path,kind):
    def mutate(row):
        d=row['experts']['discourse']['discourse_analysis'];q=d['source_bound_question_receipt'];vr=row['experts']['verifier']['verification_result'];fd=row['experts']['arbiter']['final_decision'];dec=row['experts']['decoder']
        if kind=='missing_receipt':d.pop('source_bound_question_receipt')
        elif kind=='wrong_span':q['span']='다른 질문'
        elif kind=='comment_source':q['source']='comment'
        elif kind=='foreign_speaker':q['speaker']='quoted'
        elif kind=='wrong_position':q['position']=1
        elif kind=='bool_position':q['position']=False
        elif kind=='conflict':q['target_conflict']=True
        elif kind=='unverified':q['verification_level']='model_only'
        elif kind=='target_mismatch':q['target_description']='다른 대상'
        elif kind=='multiple_targets':q['target_candidates'].append('다른 대상')
        elif kind=='work_target':d['target_kind']='work'
        elif kind=='specific_relation':vr['relation_judgment']={'discussion_target':'specific_work','post_direct_grounding':True}
        elif kind=='positive_verifier':vr['is_novel_discussion']=True
        elif kind=='positive_arbiter':fd['is_relevant']=True
        elif kind=='nonboolean_verdict':vr['is_relevant']=0
        elif kind=='unresolved_decoder':dec['unresolved_terms']=['작품명?']
        elif kind=='strong_decoder':dec['decoded_terms'][0]['best_match']['confidence']='high'
        elif kind=='not_high_general':dec['decoded_terms'][0]['interpretations'][0]['context_fit']='low'
        elif kind=='strong_echo':dec['decoded_terms'][0]['interpretations'][1]['context_fit']='high'
        elif kind=='decoder_request_not_boolean':dec['needs_verification']=1
        elif kind=='official_matching':row['catalog'].append({'title':row['post']['title'],'url':'https://novelpia.com/novel/123'})
        elif kind=='actual_title_url':vr['novel_identity']={'official_title':row['post']['title'],'heretic_url':'https://novelpia.com/novel/123'}
        elif kind=='author':row['experts']['gatekeeper']['detected_entities']['possible_authors']=['실제 작가']
        elif kind=='character':row['experts']['gatekeeper']['detected_entities']['possible_characters']=['인물']
        elif kind=='comment':row['comments']=['작품 제목이다']
        elif kind=='image':row['post']['content_blocks'].append({'type':'image','url':'https://fixture.invalid/a.png'})
    pipe,ctx,row=context(tmp_path,mutate=mutate)
    if kind=='carrier_mismatch':ctx.post_data['title']+=' 변경'
    assert pipe._general_context_state_inputs(ctx,'nonwork_comparison') is None

@pytest.mark.parametrize('kind',['new_general_title','known_alias'])
def test_no_specific_post_or_title_hardcode_and_alias_is_preserved(tmp_path,kind):
    def mutate(row):
        title='오렌지vs사과' if kind=='new_general_title' else '아생갤vs회귀수선전'
        row['post']['title']=title;row['post']['post_id']=12345678
        d=row['experts']['discourse']['discourse_analysis'];d['author_question_span']=title
        d['source_bound_question_receipt']['span']=title
        g=row['experts']['gatekeeper'];g['detected_entities']['possible_titles']=[title];g['context_clues']['short_post_title_surface']=title
        vr=row['experts']['verifier']['verification_result'];vr['grounding_check']['anchor_text']=title
        dec=row['experts']['decoder']['decoded_terms'][0];dec['original']=title;dec['interpretations'][1]['value']=title
        row['catalog']=[]
    pipe,ctx,row=context(tmp_path,mutate=mutate)
    assert (pipe._general_context_state_inputs(ctx,'nonwork_comparison') is not None)==(kind=='new_general_title')

@pytest.mark.parametrize('kind',['receipt','source','candidate','state'])
def test_adopted_state_remains_bound_after_serialization(tmp_path,kind):
    pipe,ctx,row=context(tmp_path);output,payload=serialize(pipe,ctx)
    if kind=='receipt':ctx.get_expert_output(ExpertType.DISCOURSE)['discourse_analysis']['source_bound_question_receipt']['target_conflict']=True
    elif kind=='source':ctx.post_data['title']+=' 변경'
    elif kind=='candidate':ctx.search_results.append({'title':ctx.post_data['title'],'url':'https://novelpia.com/novel/321'})
    else:payload['identity']['title_resolution_state']='unresolved_matchable'
    with pytest.raises(ValueError):pipe.verify_final_source_context_serialization(output,payload,stage='row55_tamper_'+kind)
