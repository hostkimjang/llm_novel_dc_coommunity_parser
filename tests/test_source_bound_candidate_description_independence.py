"""후보 재서술과 완료된 원문의 비작품 판정을 분리한 실제 응답 회귀."""
from copy import deepcopy
import json,socket
from pathlib import Path
import pytest
import test_source_bound_completed_nonwork_comparison as completed
import test_source_bound_general_context_fetch_delta as delta
import test_source_bound_general_comparison_question as replay
from llm_batch.experts.orchestrator import ExpertType
HERE=Path(__file__).resolve().parent
FIXTURE=HERE/'fixtures/row55_final55_v2_candidate_description.json'

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('NETWORK_FORBIDDEN_IN_CANDIDATE_DESCRIPTION_REPLAY')
    monkeypatch.setattr(socket.socket,'connect',forbidden)

def context(tmp_path,mutate=None):
    previous=completed.FIXTURE
    try:
        completed.FIXTURE=FIXTURE
        return completed.context(tmp_path,mutate)
    finally:completed.FIXTURE=previous

def test_latest_actual_short_final_candidate_full_native_main_wal(tmp_path,monkeypatch):
    monkeypatch.setattr(delta,'context',context)
    delta.test_full_context_to_output_with_recorded_negative_fetch_shape_and_actual_proposal(tmp_path,monkeypatch)
    path=tmp_path/'fullpath_receipt.json';receipt=json.loads(path.read_text('utf-8'))
    receipt['source_run_id']='20261015_002004_324886'
    receipt['final_candidate_wording_is_work_identity_claim']=False
    path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')

@pytest.mark.parametrize('variant',['actual_short','inventory_long','other_low_description','empty_list','omitted_list','null_list'])
def test_final_candidate_wording_is_not_negative_verdict_authority(tmp_path,variant):
    def mutate(row):
        fd=row['experts']['arbiter']['final_decision']
        if variant=='inventory_long':fd['suspected_titles'][0]['title']=row['experts']['decoder']['decoded_terms'][0]['best_match']['title']
        elif variant=='other_low_description':fd['suspected_titles'][0]['title']='근거가 부족한 검색 제안'
        elif variant=='empty_list':fd['suspected_titles']=[]
        elif variant=='omitted_list':fd.pop('suspected_titles')
        elif variant=='null_list':fd['suspected_titles']=None
    pipe,ctx,row=context(tmp_path,mutate)
    before=replay.source_and_experts(ctx);inventory=deepcopy(ctx.suspected_titles)
    proof=pipe._source_bound_general_context_state(ctx,'nonwork_comparison')
    assert proof is not None and proof['verify']() is True
    assert proof['expected_state']==(False,'noise','other_quarantine','unrelated','off_topic','none','context_only')
    assert replay.source_and_experts(ctx)==before and ctx.suspected_titles==inventory
    assert proof['publication_authority'] is False and proof['candidate_completeness_claimed'] is False

@pytest.mark.parametrize('kind',['fd_high','fd_numeric','fd_source_exact_official','official_source_exact','explicit_alias',
    'decoder_best_high','decoder_best_medium','decoder_term_other','decoder_score_other','decoder_candidate_other',
    'inventory_owner_unknown','inventory_string_high','positive_verifier','positive_arbiter','nonboolean_verdict',
    'specific_relation','source_change'])
def test_independent_negative_verdict_preserves_candidate_provenance_and_competition(tmp_path,kind):
    pipe,ctx,row=context(tmp_path)
    fd=ctx.get_expert_output(ExpertType.ARBITER)['final_decision']
    vr=ctx.get_expert_output(ExpertType.VERIFIER)['verification_result']
    term=ctx.get_expert_output(ExpertType.DECODER)['decoded_terms'][0]
    if kind=='fd_high':fd['suspected_titles'][0]['confidence']='High'
    elif kind=='fd_numeric':fd['suspected_titles'][0]['confidence']=0.9
    elif kind=='fd_source_exact_official':fd['suspected_titles'][0].update(title=ctx.post_data['title'],url='https://novelpia.com/novel/123')
    elif kind=='official_source_exact':ctx.search_results.append({'title':ctx.post_data['title'],'url':'https://novelpia.com/novel/123'})
    elif kind=='explicit_alias':ctx.search_results.append({'title':'명시 관계','explicit_alias_bridge':True})
    elif kind=='decoder_best_high':term['best_match']['confidence']='high'
    elif kind=='decoder_best_medium':term['best_match']['confidence']='medium'
    elif kind=='decoder_term_other':term['original']='다른 원문'
    elif kind=='decoder_score_other':term['candidates'][0]['morphological_score']=0.8
    elif kind=='decoder_candidate_other':term['candidates'][0]['official_novel_title']='다른 후보'
    elif kind=='inventory_owner_unknown':ctx.suspected_titles[0]['source_expert']='unknown'
    elif kind=='inventory_string_high':ctx.suspected_titles[0]['confidence']='High'
    elif kind=='positive_verifier':vr['is_novel_discussion']=True
    elif kind=='positive_arbiter':fd['is_relevant']=True
    elif kind=='nonboolean_verdict':fd['is_relevant']=0
    elif kind=='specific_relation':vr['relation_judgment']={'discussion_target':'specific_work','post_direct_grounding':True}
    elif kind=='source_change':ctx.post_data['title']+=' 변경'
    assert pipe._source_bound_general_context_state(ctx,'nonwork_comparison') is None

@pytest.mark.parametrize('kind',['final_wording','inventory','source','catalog'])
def test_captured_facts_cannot_change_after_acceptance(tmp_path,kind):
    pipe,ctx,row=context(tmp_path)
    proof=pipe._source_bound_general_context_state(ctx,'nonwork_comparison')
    assert proof is not None and proof['verify']() is True
    if kind=='final_wording':ctx.get_expert_output(ExpertType.ARBITER)['final_decision']['suspected_titles'][0]['title']='다른 요약'
    elif kind=='inventory':ctx.suspected_titles[0]['title']='변조'
    elif kind=='source':ctx.post_data['title']+=' 변경'
    else:ctx.search_results.append({'title':'추가 검색'})
    assert proof['verify']() is False
