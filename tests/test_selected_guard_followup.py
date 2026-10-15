import ast
from functools import lru_cache
import json,re,sys
from pathlib import Path
import pytest
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.experts.orchestrator import ConversationContext
F=Path(__file__).parent / 'fixtures/r5_selected_guard'
def methods():
 return {'_has_verifier_non_novel_mismatch': AgenticPipeline._has_verifier_non_novel_mismatch,
         '_is_unanchored_fanfic_derivative_resolution': AgenticPipeline._is_unanchored_fanfic_derivative_resolution}
@pytest.mark.parametrize('topic',['웹툰 및 소설 판본 감상','웹 소설과 만화 비교','웹툰 감상','게임과 소설 반응'])
def test_positive_topic_description_is_not_rejection(topic):
 v={'is_relevant':True,'is_novel_discussion':True,'inference':{'topic':topic},'counter_arguments':[]}
 assert methods()['_has_verifier_non_novel_mismatch'](v) is False
@pytest.mark.parametrize('field,text',[('topic','웹툰만 다루며 소설 아님'),('topic','웹툰 및 소설 판본이지만 웹소설 토론으로 보기 어려움'),('reason','게임과 웹툰 도메인 불일치'),('rejection_reason','웹툰 매체 타입 불일치')])
def test_actual_negative_stays_blocked(field,text):
 v={'is_relevant':True,'is_novel_discussion':True,'inference':{'topic':'웹툰과 소설판 감상'},'counter_arguments':[]}
 if field=='topic':v['inference']['topic']=text
 else:v[field]=text
 assert methods()['_has_verifier_non_novel_mismatch'](v) is True
@pytest.mark.parametrize('novel',[False,None])
def test_webtoon_only_rejection_flags_remain(novel):
 assert methods()['_has_verifier_non_novel_mismatch']({'is_relevant':True,'is_novel_discussion':novel,'inference':{'topic':'웹툰 감상'}}) is True
@pytest.mark.parametrize('clean',[True,False])
def test_bounded_diagnostic_no_body_and_reason(capsys,clean):
 f=json.loads((F/'fixture.json').read_text('utf-8'));p=AgenticPipeline(llm=object(),mcp=object());c=ConversationContext(post_id=1,post_data=f['post'],comments=[]);c.search_results=[f['fanfic_hit']]
 c.fetched_page_info=[{'url':f['selected_url'],'text_preview':'SECRET_BODY_CONTENT','structured_info':{'title':f['selected_title'],'page_type':'novel_page','content_status':'active','media_type':'novel','degraded':not clean}}]
 result=methods()['_is_unanchored_fanfic_derivative_resolution'](p,c,f['selected_title'],selected_url=f['selected_url']);assert result is (not clean)
 msg=capsys.readouterr().err;assert 'SECRET_BODY_CONTENT' not in msg;d=json.loads(msg.split('[selected_fanfic_guard_observation] ')[1]);assert d['publication_authority'] is False;assert d['selected_fetch_count']==1;assert d['selected_verified']==clean;assert len(d['fanfic_hit_urls'])==1
 if not clean:assert 'NOT_CLEAN_ACTIVE_DETAIL' in d['fetch_predicate_failures']

@pytest.mark.parametrize('conflict',[False,True])
def test_page_title_only_and_conflicting_display(conflict,capsys):
 f=json.loads((F/'fixture.json').read_text('utf-8'));p=AgenticPipeline(llm=object(),mcp=object());c=ConversationContext(post_id=1,post_data=f['post'],comments=[]);c.search_results=[f['fanfic_hit']]
 structured={'page_title':f['selected_title'],'page_type':'novel_page','content_status':'active','media_type':'novel'}
 if conflict:structured['title']='다른 작품'
 c.fetched_page_info=[{'url':f['selected_url'],'structured_info':structured}]
 assert methods()['_is_unanchored_fanfic_derivative_resolution'](p,c,f['selected_title'],selected_url=f['selected_url']) is conflict

@pytest.mark.parametrize('selected_fanfic',[False,True])
def test_exact_original_fetch_set_does_not_clear_selected_fanfic(selected_fanfic,capsys):
 f=json.loads((F/'fixture.json').read_text('utf-8'));p=AgenticPipeline(llm=object(),mcp=object());c=ConversationContext(post_id=1,post_data=f['post'],comments=[]);c.search_results=[f['fanfic_hit']]
 c.fetched_page_info=[{'url':f['selected_url'],'structured_info':{'title':f['selected_title'],'page_type':'novel_page','content_status':'active'}}]
 selected=f['fanfic_hit']['url'] if selected_fanfic else 'https://www.munpia.com/novel/detail/191240'
 assert methods()['_is_unanchored_fanfic_derivative_resolution'](p,c,f['selected_title'],selected_url=selected) is selected_fanfic

@pytest.mark.parametrize('negative',[False,True])
def test_reason_uses_same_descriptive_negative_rule(negative):
 v={'is_relevant':True,'is_novel_discussion':True,'reason':'웹툰 및 소설 판본 감상','counter_arguments':[]}
 if negative:v['reason']='웹툰 매체 타입 불일치이며 소설 아님'
 assert methods()['_has_verifier_non_novel_mismatch'](v) is negative

def test_selected_fanfic_fetch_blocks_even_without_search_hit(capsys):
 f=json.loads((F/'fixture.json').read_text('utf-8'));p=AgenticPipeline(llm=object(),mcp=object());c=ConversationContext(post_id=1,post_data=f['post'],comments=[]);c.search_results=[]
 original={'url':f['selected_url'],'structured_info':{'title':f['selected_title'],'page_type':'novel_page','content_status':'active'}}
 selected='https://www.joara.com/book/1829469'
 c.fetched_page_info=[original,{'url':selected,'text_preview':'팬픽 패러디','structured_info':{'title':f['selected_title'],'page_type':'novel_page','content_status':'active'}}]
 assert methods()['_is_unanchored_fanfic_derivative_resolution'](p,c,f['selected_title'],selected_url=selected) is True
