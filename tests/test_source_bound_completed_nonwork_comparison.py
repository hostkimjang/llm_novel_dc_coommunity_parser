"""발화가 질문으로 표시되지 않은 실제 비교 글도 완료된 비작품 판정에 결속한다."""
from copy import deepcopy
import json,socket
from pathlib import Path
import pytest
import test_source_bound_general_comparison_question as replay
import test_source_bound_general_context_fetch_delta as delta
from llm_batch.experts.orchestrator import ExpertType
HERE=Path(__file__).resolve().parent
FIXTURE=HERE/'fixtures/row55_final55_nonquestion.json'

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('NETWORK_FORBIDDEN_IN_COMPLETED_NONWORK_REPLAY')
    monkeypatch.setattr(socket.socket,'connect',forbidden)

def context(tmp_path,mutate=None):
    previous=replay.FIXTURE
    try:
        replay.FIXTURE=FIXTURE
        pipe,ctx,row=replay.context(tmp_path,'final55',9426461,mutate)
    finally:replay.FIXTURE=previous
    decoder=ctx.get_expert_output(ExpertType.DECODER)
    ctx.suspected_titles=[{'title':candidate['official_novel_title'],'confidence':candidate.get('morphological_score',0.5),
        'source_term':term['original'],'source_expert':'arbiter'}
        for term in decoder['decoded_terms'] for candidate in term['candidates'] if candidate.get('official_novel_title')]
    return pipe,ctx,row

def test_actual_no_question_span_full_native_main_wal_and_sealed_delta(tmp_path,monkeypatch):
    # Reuse the actual output/native/main/WAL assertions with latest stored
    # source/experts and log-scalar transport shapes. No model replay is claimed.
    monkeypatch.setattr(delta,'context',context)
    monkeypatch.setattr(delta,'PAGES',[(url,title,'deleted') for url,title,_ in delta.PAGES])
    delta.test_full_context_to_output_with_recorded_negative_fetch_shape_and_actual_proposal(tmp_path,monkeypatch)
    receipt=json.loads((tmp_path/'fullpath_receipt.json').read_text('utf-8'))
    assert receipt['state']['is_novel_related'] is False
    assert receipt['state']['title_resolution_state']=='context_only'

@pytest.mark.parametrize('intent',['make_joke','other'])
@pytest.mark.parametrize('title_kind',['actual_book_observation','literal_comparison_echo','different_general_comparison'])
def test_nonquestion_utterance_does_not_reopen_completed_negative_work_verdict(tmp_path,intent,title_kind):
    def mutate(row):
        disc=row['experts']['discourse']['discourse_analysis'];disc['intent']=intent
        disc['author_question_span']=None;disc['author_question_target']=None
        disc.pop('source_bound_question_receipt',None)
        term=row['experts']['decoder']['decoded_terms'][0]
        if title_kind=='different_general_comparison':
            title='오렌지vs사과';row['post']['title']=title;row['post']['post_id']=12345678
            g=row['experts']['gatekeeper'];g['detected_entities']['possible_titles']=[title]
            g['context_clues']['short_post_title_surface']=title
            row['experts']['verifier']['verification_result']['grounding_check']['anchor_text']=title
            term['original']=title;row['catalog']=[]
        if title_kind!='actual_book_observation':term['interpretations'][1]['value']=row['post']['title']
    pipe,ctx,row=context(tmp_path,mutate)
    before=replay.source_and_experts(ctx)
    proof=pipe._source_bound_general_context_state(ctx,'nonwork_comparison')
    assert proof is not None and proof['verify']() is True
    assert proof['expected_state']==(False,'noise','other_quarantine','unrelated','off_topic','none','context_only')
    assert replay.source_and_experts(ctx)==before
    assert proof['publication_authority'] is False and proof['candidate_completeness_claimed'] is False

@pytest.mark.parametrize('kind',['positive_verifier','positive_arbiter','nonboolean_verdict','decoder_unknown',
    'unresolved_terms','high_work','specific_work','official_work','known_alias','broken_asserted_question',
    'author','character','comment','image','search_source_relation','low_general_exact_echo',
    'numeric_proposal_without_provenance','literal_high_candidate'])
def test_nonquestion_completed_verdict_keeps_work_and_original_guards(tmp_path,kind):
    def mutate(row):
        e=row['experts'];vr=e['verifier']['verification_result'];fd=e['arbiter']['final_decision'];dec=e['decoder']
        if kind=='positive_verifier':vr['is_novel_discussion']=True
        elif kind=='positive_arbiter':fd['is_relevant']=True
        elif kind=='nonboolean_verdict':vr['is_relevant']=0
        elif kind=='decoder_unknown':dec['needs_verification']=None
        elif kind=='unresolved_terms':dec['unresolved_terms']=['미확정 작품']
        elif kind=='high_work':dec['decoded_terms'][0]['best_match']['confidence']='high'
        elif kind=='specific_work':vr['relation_judgment']={'discussion_target':'specific_work','post_direct_grounding':True}
        elif kind=='official_work':row['catalog'].append({'title':row['post']['title'],'url':'https://novelpia.com/novel/123'})
        elif kind=='known_alias':
            title='아생갤vs회귀수선전';row['post']['title']=title
            e['gatekeeper']['detected_entities']['possible_titles']=[title]
            e['gatekeeper']['context_clues']['short_post_title_surface']=title
            vr['grounding_check']['anchor_text']=title;dec['decoded_terms'][0]['original']=title
        elif kind=='broken_asserted_question':e['discourse']['discourse_analysis']['author_question_span']=row['post']['title']
        elif kind=='author':e['gatekeeper']['detected_entities']['possible_authors']=['작가']
        elif kind=='character':e['gatekeeper']['detected_entities']['possible_characters']=['작품 인물']
        elif kind=='comment':row['comments']=['작품 질문임']
        elif kind=='image':row['post']['content_blocks'].append({'type':'image','url':'https://fixture.invalid/work.png'})
        elif kind=='search_source_relation':row['catalog'].append({'title':'관계','explicit_alias_bridge':True})
        elif kind=='low_general_exact_echo':
            dec['decoded_terms'][0]['interpretations'][0]['context_fit']='low'
            dec['decoded_terms'][0]['interpretations'][1]['value']=row['post']['title']
    pipe,ctx,row=context(tmp_path,mutate)
    if kind=='numeric_proposal_without_provenance':ctx.suspected_titles[0].pop('source_term')
    elif kind=='literal_high_candidate':ctx.suspected_titles[0]['confidence']='High'
    assert pipe._source_bound_general_context_state(ctx,'nonwork_comparison') is None

@pytest.mark.parametrize('kind',['source','expert','evidence','state'])
def test_nonquestion_final_binding_rejects_changes_after_acceptance(tmp_path,kind):
    pipe,ctx,row=context(tmp_path)
    proof=pipe._source_bound_general_context_state(ctx,'nonwork_comparison')
    assert proof is not None and proof['verify']() is True
    if kind=='source':ctx.post_data['title']+='변경'
    elif kind=='expert':ctx.get_expert_output(ExpertType.ARBITER)['final_decision']['is_relevant']=True
    elif kind=='evidence':ctx.search_results.append({'title':'새 근거'})
    else:ctx.get_expert_output(ExpertType.DISCOURSE)['discourse_analysis']['target_kind']='work'
    assert proof['verify']() is False
