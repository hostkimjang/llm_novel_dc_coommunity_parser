"""실제 복수 검색 제안의 높은 형태 점수와 원문 작품 관계를 구별한다."""
from copy import deepcopy
import json,socket
from pathlib import Path
import pytest
import test_source_bound_completed_nonwork_comparison as completed
import test_source_bound_general_context_fetch_delta as delta
import test_source_bound_general_comparison_question as replay
from llm_batch.experts.orchestrator import ExpertType
HERE=Path(__file__).resolve().parent
FIXTURE=HERE/'fixtures/row55_final55_v3_lexical_proposals.json'

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('NETWORK_FORBIDDEN_IN_LEXICAL_PROPOSAL_REPLAY')
    monkeypatch.setattr(socket.socket,'connect',forbidden)

def context(tmp_path,mutate=None):
    previous=completed.FIXTURE
    try:
        completed.FIXTURE=FIXTURE
        pipe,ctx,row=completed.context(tmp_path,mutate)
        # Actual log lines 1122-1123 enumerate score 1.0 before 0.9.
        ctx.suspected_titles.sort(key=lambda item:item['confidence'],reverse=True)
        return pipe,ctx,row
    finally:completed.FIXTURE=previous

def matching_candidate(ctx):
    term=ctx.get_expert_output(ExpertType.DECODER)['decoded_terms'][0]
    item=next(c for c in term['candidates'] if c.get('morphological_score')==1.0)
    inventory=next(i for i in ctx.suspected_titles if i['confidence']==1.0)
    return term,item,inventory

def test_actual_multiple_candidates_full_native_main_wal_without_erasing_inventory(tmp_path,monkeypatch):
    pipe,ctx,row=context(tmp_path/'entry')
    assert sorted(i['confidence'] for i in ctx.suspected_titles)==[0.9,1.0]
    term,item,inventory=matching_candidate(ctx)
    assert term['best_match']['title']!=item['official_novel_title']
    proof=pipe._source_bound_general_context_state(ctx,'nonwork_comparison')
    assert proof is not None and proof['verify']() is True
    monkeypatch.setattr(delta,'context',context)
    delta.test_full_context_to_output_with_recorded_negative_fetch_shape_and_actual_proposal(tmp_path/'full',monkeypatch)
    path=tmp_path/'full/fullpath_receipt.json';receipt=json.loads(path.read_text('utf-8'))
    receipt.update(source_run_id='20261015_003412_146145',lexical_score_is_semantic_work_confidence=False,
        original_inventory_scores=[1.0,0.9],candidate_rows_preserved=True)
    path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')

@pytest.mark.parametrize('kind',['actual','different_catalog_host','genre_label_absent','genre_label_changed',
    'other_low_best','fd_exact_low','fd_omitted','ordinary_other_title','extra_nonselected_candidate'])
def test_weak_exact_lexical_proposal_does_not_become_source_work_relationship(tmp_path,kind):
    def mutate(row):
        term=row['experts']['decoder']['decoded_terms'][0]
        item=next(c for c in term['candidates'] if c.get('morphological_score')==1.0)
        if kind=='different_catalog_host':item['url']='https://catalog.fixture.invalid/item/123'
        elif kind=='genre_label_absent':item.pop('genre_match',None)
        elif kind=='genre_label_changed':item['genre_match']={'target_genre':'다른 분류','is_match':False}
        elif kind=='other_low_best':term['best_match']['title']=item['official_novel_title']
        elif kind=='fd_exact_low':row['experts']['arbiter']['final_decision']['suspected_titles'][0]['title']=row['post']['title']
        elif kind=='fd_omitted':row['experts']['arbiter']['final_decision'].pop('suspected_titles')
        elif kind=='ordinary_other_title':
            title='오렌지vs사과';row['post']['title']=title;row['post']['post_id']=12345678
            g=row['experts']['gatekeeper'];g['detected_entities']['possible_titles']=[title];g['context_clues']['short_post_title_surface']=title
            row['experts']['verifier']['verification_result']['grounding_check']['anchor_text']=title
            term['original']=title;term['interpretations'][1]['value']=title;item['official_novel_title']=title
            d=row['experts']['discourse']['discourse_analysis']
            if d.get('author_question_span'):
                d['author_question_span']=title;d['source_bound_question_receipt']['span']=title
            row['catalog']=[]
        elif kind=='extra_nonselected_candidate':term['candidates'].append({'official_novel_title':row['post']['title'],'morphological_score':0.75})
    pipe,ctx,row=context(tmp_path,mutate)
    before=replay.source_and_experts(ctx);inventory=deepcopy(ctx.suspected_titles)
    proof=pipe._source_bound_general_context_state(ctx,'nonwork_comparison')
    assert proof is not None and proof['verify']() is True
    assert proof['expected_state']==(False,'noise','other_quarantine','unrelated','off_topic','none','context_only')
    assert replay.source_and_experts(ctx)==before and ctx.suspected_titles==inventory
    assert proof['publication_authority'] is False and proof['candidate_completeness_claimed'] is False

@pytest.mark.parametrize('kind',['score','title','term','producer','best_high','fd_high','fd_medium',
    'positive_verifier','positive_arbiter','official_candidate','official_best','official_fd','official_search',
    'official_fetch','candidate_alias','inventory_alias','fd_alias','candidate_character','candidate_direct',
    'source_alias_row','known_alias','source_change','candidate_strong_confidence',
    'fd_author','fd_character','fd_author_info','best_author','inventory_character'])
def test_real_source_relationship_or_invalid_provenance_still_blocks(tmp_path,kind):
    pipe,ctx,row=context(tmp_path);term,item,inventory=matching_candidate(ctx)
    vr=ctx.get_expert_output(ExpertType.VERIFIER)['verification_result'];fd=ctx.get_expert_output(ExpertType.ARBITER)['final_decision']
    official='https://novelpia.com/novel/123'
    if kind=='score':inventory['confidence']=0.99
    elif kind=='title':inventory['title']='다른 제목'
    elif kind=='term':inventory['source_term']='다른 원문'
    elif kind=='producer':inventory['source_expert']='unknown'
    elif kind=='best_high':term['best_match']['confidence']='high'
    elif kind=='fd_high':fd['suspected_titles'][0]['confidence']='High'
    elif kind=='fd_medium':fd['suspected_titles'][0]['confidence']='Medium'
    elif kind=='positive_verifier':vr['is_novel_discussion']=True
    elif kind=='positive_arbiter':fd['is_relevant']=True
    elif kind=='official_candidate':item['url']=official
    elif kind=='official_best':term['best_match'].update(title=ctx.post_data['title'],url=official)
    elif kind=='official_fd':fd['suspected_titles'][0].update(title=ctx.post_data['title'],url=official)
    elif kind=='official_search':ctx.search_results.append({'title':ctx.post_data['title'],'url':official})
    elif kind=='official_fetch':ctx.fetched_page_info=[{'url':official,'structured_info':{'title':ctx.post_data['title']}}]
    elif kind=='candidate_alias':item['explicit_alias_bridge']=True
    elif kind=='inventory_alias':inventory['explicit_alias_bridge']=True
    elif kind=='fd_alias':fd['suspected_titles'][0]['explicit_alias_bridge']=True
    elif kind=='candidate_character':item['verified_character_work_link']=True
    elif kind=='candidate_direct':item['post_direct_grounding']=True
    elif kind=='source_alias_row':ctx.search_results.append({'title':'명시 관계','explicit_alias_bridge':True})
    elif kind=='known_alias':ctx.post_data['title']='아생갤vs회귀수선전'
    elif kind=='source_change':ctx.post_data['title']+='변경'
    elif kind=='candidate_strong_confidence':item['confidence']='High'
    elif kind=='fd_author':fd['suspected_titles'][0]['author']='명시 작가'
    elif kind=='fd_character':fd['suspected_titles'][0]['character']='명시 인물'
    elif kind=='fd_author_info':fd['suspected_titles'][0]['author_info']={'name':'명시 작가'}
    elif kind=='best_author':term['best_match']['author']='명시 작가'
    elif kind=='inventory_character':inventory['character']='명시 인물'
    assert pipe._source_bound_general_context_state(ctx,'nonwork_comparison') is None

@pytest.mark.parametrize('kind',['inventory','candidate','final','source','catalog','fetch'])
def test_weak_observations_remain_in_the_sealed_raw_facts(tmp_path,kind):
    pipe,ctx,row=context(tmp_path);term,item,inventory=matching_candidate(ctx)
    proof=pipe._source_bound_general_context_state(ctx,'nonwork_comparison')
    assert proof is not None and proof['verify']() is True
    if kind=='inventory':inventory['confidence']=0.99
    elif kind=='candidate':item['genre_match']={'target_genre':'변조'}
    elif kind=='final':ctx.get_expert_output(ExpertType.ARBITER)['final_decision']['suspected_titles']=[]
    elif kind=='source':ctx.post_data['title']+='변경'
    elif kind=='catalog':ctx.search_results.append({'title':'추가 검색'})
    else:ctx.fetched_page_info=[]
    assert proof['verify']() is False
