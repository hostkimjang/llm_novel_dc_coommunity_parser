"""69 직접 댓글 소재와 source/main/WAL 결속의 기능 회귀 초안. 작성 시 실행하지 않는다."""
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
from llm_batch.experts.orchestrator import ExpertType
from llm_batch.grounding.candidate_audit import apply_candidate_audit_fields, has_authoritative_publish_contract
from llm_batch.ledger.publication_commit import (
    PublicationCommitRegistry, build_publication_scope_descriptor, commit_publication_result,
)
from llm_batch import promotion_gate
from test_source_bound_nsfw import context_for, FIXTURE as FIXTURE74

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=Path(__file__).parent/'fixtures/actual80_nsfw69_saved_experts.json'
RULE='DIRECT_COMMENT_SEXUAL_DESIRE_RESTRAINT_V1'


def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def record69():
    fixture=json.loads(FIXTURE.read_bytes())
    assert fixture['scope']=='SAVED_EXPERTS_PARTIAL_CONTEXT_NOT_ORIGINAL_MEMORY_CONTEXT'
    row=fixture['record']
    assert hashlib.sha256(canonical({'post':row['post'],'comments':row['comments']})).hexdigest()==row['source_canonical_sha256']
    assert hashlib.sha256(canonical(row['final_result'])).hexdigest()==row['result_canonical_sha256']
    assert row['experts']=={x['expert']:x['value'] for x in row['expert_stream']}
    assert type(row['post_id']) is int and row['post_id_type']=='int'
    return row


def serialize(record=None,*,mutate=None,capture=True):
    pipe,ctx,record=context_for(record_override=record or record69(),mutate_post=mutate,capture=capture)
    before=canonical([ctx.post_data,ctx.comments,ctx.expert_outputs])
    output=pipe._context_to_output(ctx)
    payload=output.model_dump(mode='json')
    observation=pipe.verify_final_source_context_serialization(output,payload,stage='nsfw69_native')
    assert before==canonical([ctx.post_data,ctx.comments,ctx.expert_outputs])
    assert ctx._final_source_projection_call_count==1
    return pipe,ctx,output,payload,observation


def actual_main_sync_and_wrapper(payload, post):
    # surface v3에서 검토한 실제 main typed 경로를 함수 소스 그대로 재사용한다.
    tree=ast.parse((ROOT/'expert_main.py').read_text(encoding='utf8'))
    names={'_runtime_candidate_audit_seed','_sync_final_publication_ledger_contract',
           '_reapply_authoritative_publish_contract','_sync_analysis_notes_to_final_publication',
           '_sync_reader_explanation_to_publish_contract'}
    selected=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in names]
    assert {x.name for x in selected}==names
    wrapper=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='_FinalSourceContextResult')
    exported=('PUBLISH_CONTRACT_VERSION','candidate_inventory_evidence_from_sources','candidate_inventory_pairs',
              'candidate_inventory_records','EvidenceRecord','GroundingState','ScopeState','apply_publish_contract',
              'build_publish_ledger','evaluate_publish_contract','evidence_records_from_payload','grounding_state_from_dict')
    ns={name:getattr(promotion_gate,name) for name in exported}
    ns.update(Any=Any,Dict=Dict,Mapping=Mapping,Callable=Callable,Optional=Optional,json=json,re=re)
    exec(compile(ast.Module(body=selected+[wrapper],type_ignores=[]),str(ROOT/'expert_main.py'),'exec'),ns)
    ident=payload['identity'];assert has_authoritative_publish_contract(ident)
    seed=ns['_runtime_candidate_audit_seed'](ident,None);assert seed is None
    apply_candidate_audit_fields(ident,seed)
    content=[b['text'] for b in post.get('content_blocks',[]) if isinstance(b,dict) and b.get('text')]
    comments=[x.get('content',x.get('text','')) if isinstance(x,dict) else str(x) for x in post.get('comments_raw',[])]
    sync=dict(payload,title=post['title'],content=content,comments=comments,
              comment_context_lines=[],comment_dialogue_context_lines=[],_loop_projection_followup=None)
    ns['_sync_final_publication_ledger_contract'](sync,post_title=post['title'])
    assert 'publish_contract_integrity_error' not in ident
    return ns['_FinalSourceContextResult']


def test_saved69_false_is_source_positive_without_rewriting_arbiter_and_survives_actual_main_wal(tmp_path):
    fixture_before=FIXTURE.read_bytes()
    record=record69()
    assert record['final_result']['analysis_result']['analysis']['is_nsfw'] is False
    assert record['final_result']['analysis_result']['analysis']['nsfw_assessment_status']=='MODEL_REPORTED'
    assert record['experts']['arbiter']['metadata_synthesis']['is_nsfw'] is False
    pipe,ctx,output,payload,observation=serialize(record)
    assert payload['analysis']['is_nsfw'] is True
    assert payload['analysis']['nsfw_assessment_status']=='SOURCE_RULE_POSITIVE'
    proof=observation['nsfw_content_observation']
    assert proof['schema_version']=='source_bound_nsfw_v2' and proof['rule']==RULE
    assert proof['status']=='SOURCE_CONFLICT_RESOLVED_TRUE' and proof['arbiter_value'] is False
    assert proof['publication_authority'] is False and proof['human_gold'] is False
    assert proof['author_endorsement']=='NOT_ASSESSED' and proof['real_world_event']=='NOT_ASSERTED'
    assert len(proof['evidence'])==1
    ev=proof['evidence'][0];raw=record['comments'][0]['content']
    assert (ev['original_index'],ev['raw_path'],ev['comment_id'],ev['comment_id_type'])==(0,'/comments/0/content','29662459','str')
    assert raw[slice(*ev['raw_span'])]==ev['quote']==raw
    for part in ('participant','role','act','stance'):
        assert raw[slice(*ev[part+'_span'])]==ev[part+'_surface']
    assert ev['act_surface']=='겁탈' and ev['role_surface']=='마법사' and ev['stance_surface']=='참기'
    assert ev['counts_as_core'] is False and ev['event_occurrence']=='NOT_ASSERTED'
    assert ctx.get_expert_output(ExpertType.ARBITER)==record['experts']['arbiter']
    wrapper=actual_main_sync_and_wrapper(payload,ctx.post_data)
    after=pipe.verify_final_source_context_serialization(output,payload,stage='nsfw69_actual_main_typed_sync')
    assert after['nsfw_content_observation']==proof
    wrapped=wrapper(dict(ctx.post_data,comments=list(ctx.comments),analysis_result=payload),
                    output=output,verifier=pipe.verify_final_source_context_serialization)
    scope=build_publication_scope_descriptor(input_file_sha256=record['source_canonical_sha256'],post_ids=[ctx.post_id],
        config_hash='nsfw69-saved-partial-context',release_fingerprint='candidate-only')
    path=tmp_path/'publication.jsonl'
    registry=PublicationCommitRegistry(path,scope_descriptor=scope,create_new=True)
    commit,created=commit_publication_result(wrapped,registry=registry,attempt_run_id='nsfw69-partial',input_index=1,post_id=ctx.post_id)
    assert created and commit.publish_allowed is payload['identity']['promotion_decision']['publish_allowed']
    saved=PublicationCommitRegistry(path,scope_descriptor=scope,create_new=False).result(ctx.post_id)
    assert saved['analysis_result']==payload
    assert wrapped.verify_stored_payload(saved,stage='nsfw69_wal_readback')['nsfw_content_observation']==proof
    wal_before=path.read_bytes()
    for field,value in [('is_nsfw',False),('is_nsfw',None),('is_nsfw',1),('is_nsfw','true'),
                        ('nsfw_assessment_status','MODEL_REPORTED'),('nsfw_assessment_status',None)]:
        forged=copy.deepcopy(saved);forged['analysis_result']['analysis'][field]=value
        with pytest.raises(ValueError,match='NSFW'):
            wrapped.verify_stored_payload(forged,stage='nsfw69_mutated_assessment')
    assert path.read_bytes()==wal_before and FIXTURE.read_bytes()==fixture_before
    ctx.get_expert_output(ExpertType.ARBITER)['metadata_synthesis']['is_nsfw']=True
    with pytest.raises(ValueError):
        pipe.verify_final_source_context_serialization(output,payload,stage='nsfw69_raw_arbiter_changed')


@pytest.mark.parametrize('raw', [
    '핑발바이의 미친마법사 겁탈참기 lv.max',
    '  어떤 마법사를 겁탈 참기 LV.MAX  ',
    '주인공을 강간하고 싶다',
    '그 인물을 성폭행하려는 충동을 참았다',
    '그 남성은 성관계욕구참기',
    '그녀 섹스 참는 중',
    '여성 성적 자위 억제하기',
])
def test_direct_person_act_desire_or_restraint_forms_have_exact_spans(raw):
    proof=AgenticPipeline._direct_sexual_desire_comment_span(raw)
    assert proof is not None
    assert raw[slice(*proof['raw_span'])]==raw.strip()
    for field in ('participant','role','act','stance'):
        assert raw[slice(*proof[field+'_span'])]==proof[field+'_surface']
    assert proof['event_occurrence']=='NOT_ASSERTED'


@pytest.mark.parametrize('raw', [
    '마법사 공격참기 lv.max','마법사 졸음참기 lv.max','마법사 식욕참기 lv.max',
    '마법사 자위참기','도시 겁탈참기','내 지갑 강간참기','여주 겁탈참기','기사 겁탈참기',
    '마법사 겁탈','마법사 겁탈참기라는 말의 뜻','마법사 강간하고 싶지 않다',
    '마법사 겁탈참기인가?','마법사 겁탈참기는 아니다',
    '"마법사 겁탈참기"','「마법사 겁탈참기」','인용: 마법사 겁탈참기',
    '제목 마법사 겁탈참기','단어 설명의 마법사 겁탈참기','신문기사의 남성 강간충동참기',
    '예방 교육의 인물 강간충동참기','치료 대상 남성 성폭행충동참기',
    '친구가 말한 마법사 겁탈참기','<p>마법사 겁탈참기</p>',
    'https://example.invalid/마법사겁탈참기','마법사\n겁탈참기',
])
def test_homonyms_meta_quotes_nonsexual_or_incomplete_forms_stay_outside_rule(raw):
    assert AgenticPipeline._direct_sexual_desire_comment_span(raw) is None


@pytest.mark.parametrize('mode', ['missing_carrier','html','competing_text','typed_parent','duplicate_id','over_cap'])
def test_source69_rule_requires_original_native_comment_binding(mode):
    record=copy.deepcopy(record69())
    def mutate(post):
        c=post['comments'][0]
        if mode=='html':c['content_html']='<p>'+c['content']+'</p>'
        if mode=='competing_text':c['text']='전혀 다른 원문'
        if mode=='typed_parent':c['post_id']=str(post['post_id'])
        if mode=='duplicate_id':post['comments'].append(dict(c,content='일반 댓글',content_html='일반 댓글'))
        if mode=='over_cap':post['comments']=[{'comment_id':str(500+i),'post_id':post['post_id'],'content':'일반 반응'} for i in range(15)]+[c]
    _,_,_,payload,observation=serialize(record,mutate=mutate,capture=mode!='missing_carrier')
    assert payload['analysis']['is_nsfw'] is False
    assert payload['analysis']['nsfw_assessment_status']=='MODEL_REPORTED'
    assert observation['nsfw_content_observation']['evidence']==[]


@pytest.mark.parametrize('value,expected,status', [(False,True,'SOURCE_RULE_POSITIVE'),
    (True,True,'SOURCE_RULE_POSITIVE'),('MISSING',True,'SOURCE_RULE_POSITIVE'),
    (None,False,'NOT_EVALUATED'),('false',False,'NOT_EVALUATED'),(1,False,'NOT_EVALUATED')])
def test_source69_respects_existing_metadata_types_and_boolean_assessment_pair(value,expected,status):
    record=copy.deepcopy(record69());meta=record['experts']['arbiter']['metadata_synthesis']
    if value=='MISSING':meta.pop('is_nsfw')
    else:meta['is_nsfw']=value
    _,_,_,payload,observation=serialize(record)
    assert payload['analysis']['is_nsfw'] is expected
    assert payload['analysis']['nsfw_assessment_status']==status
    if expected:assert observation['nsfw_content_observation']['rule']==RULE


def test_existing74_rule_keeps_precedence_even_with_an_additional_desire_comment():
    record=copy.deepcopy(json.loads(FIXTURE74.read_bytes())['records']['new'])
    record['comments'].append({'comment_id':'additional','post_id':record['post']['post_id'],
                              'content':'마법사 겁탈참기 lv.max'})
    _,_,_,payload,observation=serialize(record)
    proof=observation['nsfw_content_observation']
    assert payload['analysis']['is_nsfw'] is True
    assert proof['rule']=='TROPE_REPLY_EXPLICIT_SEXUAL_VIOLENCE_V1'
    assert len(proof['evidence'])==1
    assert proof['evidence'][0]['raw_path']=='/comments/4/content'
    assert proof['evidence'][0]['quote']=='히로인 강간'


def test_source_drift_after_capture_cannot_add_a_desire_proof():
    record=copy.deepcopy(record69())
    record['comments'][0]['content']=record['comments'][0]['content_html']='일반 반응'
    pipe,ctx,_=context_for(record_override=record)
    c=ctx._final_source_original_comment_refs[0]
    c['content']=c['content_html']='마법사 겁탈참기 lv.max';ctx.comments[0]=c['content']
    output=pipe._context_to_output(ctx);payload=output.model_dump(mode='json')
    observation=pipe.verify_final_source_context_serialization(output,payload,stage='nsfw69_source_drift')
    assert payload['analysis']['is_nsfw'] is False
    assert observation['nsfw_content_observation']['status'] in ('SOURCE_NOT_BOUND','SOURCE_DRIFT')
    assert observation['nsfw_content_observation']['evidence']==[]
