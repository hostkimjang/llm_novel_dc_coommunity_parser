import ast
from copy import deepcopy
import json
from pathlib import Path
import socket
import pytest
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.experts.orchestrator import ConversationContext

FOLDER=Path(__file__).parent / 'fixtures/r5_selected_guard'

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
 def forbidden(*args,**kwargs): raise AssertionError('offline replay only')
 monkeypatch.setattr(socket.socket,'connect',forbidden)

def setup():
 f=json.loads((FOLDER/'fixture.json').read_text('utf-8'))
 p=AgenticPipeline(llm=object(),mcp=object())
 ctx=ConversationContext(post_id=f['post']['post_id'],post_data=deepcopy(f['post']),comments=[])
 ctx.search_results=[deepcopy(f['fanfic_hit']),*deepcopy(f['official_hits'])]
 # Full fetched object was not exported; this is a synthetic shape of the logged exact active fetch.
 ctx.fetched_page_info=[{'url':f['selected_url'],'structured_info':{'title':f['selected_title'],'page_type':'novel_page','content_status':'active','media_type':'novel','author':'추공'},'content':'나 혼자만 레벨업 추공 공식 작품 상세'}]
 return f,p,ctx

def test_actual_hit_reproduces_current_cross_url_block_and_candidate_scopes_it():
 f,p,c=setup()
 assert p._is_unanchored_fanfic_derivative_resolution(c,f['selected_title'],selected_url=f['selected_url']) is False
 assert p._normalize_url_for_match(f['fanfic_hit']['url']) != p._normalize_url_for_match(f['selected_url'])

@pytest.mark.parametrize('change',['no_selected_url','same_selected_fanfic','explicit_authored_fanfic','no_fetch','wrong_title','webtoon_fetch','inactive_fetch','fanfic_fetch','text_preview_fanfic','entry_degraded','entry_blocked','entry_false_ok','entry_http_error','structured_error','structured_fallback','structured_degraded','structured_http_error','possible_throttle'])
def test_candidate_keeps_fanfic_and_missing_or_wrong_edition_blocks(change):
 f,p,c=setup();url=f['selected_url']
 if change=='no_selected_url':url=None
 elif change=='same_selected_fanfic':url=f['fanfic_hit']['url'];c.fetched_page_info=[]
 elif change=='explicit_authored_fanfic':c.post_data['content_blocks'].append({'type':'text','text':'나혼렙 팬픽 이야기임'})
 elif change=='no_fetch':c.fetched_page_info=[]
 elif change=='wrong_title':c.fetched_page_info[0]['structured_info']['title']='나 혼자만 레벨업 : 라그나로크'
 elif change=='webtoon_fetch':c.fetched_page_info[0]['structured_info']['media_type']='webtoon'
 elif change=='inactive_fetch':c.fetched_page_info[0]['structured_info']['content_status']='unavailable'
 elif change=='fanfic_fetch':c.fetched_page_info[0]['structured_info']['category']='패러디'
 elif change=='text_preview_fanfic':c.fetched_page_info[0]['text_preview']='팬픽 패러디 작품'
 elif change=='entry_degraded':c.fetched_page_info[0]['degraded']=True
 elif change=='entry_blocked':c.fetched_page_info[0]['blocked']=True
 elif change=='entry_false_ok':c.fetched_page_info[0]['ok']=False
 elif change=='entry_http_error':c.fetched_page_info[0]['http_status']=403
 elif change=='structured_error':c.fetched_page_info[0]['structured_info']['error']='blocked'
 elif change=='structured_fallback':c.fetched_page_info[0]['structured_info']['fallback_source']='cached'
 elif change=='structured_degraded':c.fetched_page_info[0]['structured_info']['degraded']=True
 elif change=='structured_http_error':c.fetched_page_info[0]['structured_info']['status_code']=404
 elif change=='possible_throttle':c.fetched_page_info[0]['possible_throttle']=True
 assert p._is_unanchored_fanfic_derivative_resolution(c,f['selected_title'],selected_url=url) is True


def saved_verifier():return json.loads((FOLDER/'verifier_saved.json').read_text('utf-8'))

def test_actual_positive_mixed_topic_is_not_mismatch_evidence():
 v=saved_verifier()
 assert AgenticPipeline._has_verifier_non_novel_mismatch(v) is False

@pytest.mark.parametrize('mutation',['explicit_webtoon','negative_novel','rejection','grounding','counterargument','topic_negative','cross_media_game','comic_adaptation'])
def test_actual_rejection_and_webtoon_only_remain_blocked(mutation):
 v=saved_verifier()
 if mutation=='explicit_webtoon':v['inference']['topic']='나 혼자만 레벨업 웹툰 감상';v['is_novel_discussion']=False
 elif mutation=='negative_novel':v['is_novel_discussion']=False
 elif mutation=='rejection':v['rejection_reason']='웹툰 매체 타입 불일치'
 elif mutation=='grounding':v['grounding_check']['grounding_issue']='만화 도메인 불일치'
 elif mutation=='counterargument':v['counter_arguments']=[{'issue':'웹툰 원작과 매체가 다름'}]
 elif mutation=='topic_negative':v['inference']['topic']='웹툰 및 소설판 비교지만 웹소설 토론으로 보기 어려움'
 elif mutation=='cross_media_game':v['rejection_reason']='도메인 불일치: 원작 소설이 아니라 게임과 웹툰'
 elif mutation=='comic_adaptation':v['inference']['topic']='comic adaptation 만화 각색 감상';v['is_novel_discussion']=False 
 assert AgenticPipeline._has_verifier_non_novel_mismatch(v) is True

def test_serializer_callsite_supplies_selected_url_without_publication_override():
 source=Path(__import__('inspect').getfile(AgenticPipeline)).read_text(encoding='utf-8')
 assert 'self._is_unanchored_fanfic_derivative_resolution(ctx, official_title, selected_url=heretic_url)' in source
 f,p,c=setup();before=deepcopy(c.search_results)
 assert p._is_unanchored_fanfic_derivative_resolution(c,f['selected_title'],selected_url=f['selected_url']) is False
 assert c.search_results == before
 assert not c.get_expert_output(__import__('llm_batch.experts.orchestrator',fromlist=['ExpertType']).ExpertType.ARBITER)
 assert not hasattr(c,'_publication_commit')
