"""작가 품평의 작성자 근거 결속. 현재39는 저장 부분 입력이며 완전 런 재현이 아니다."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import pytest
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import PostInput
from llm_batch.experts.orchestrator import ConversationContext, ExpertType

FIXTURE=Path(__file__).parent/'fixtures/actual80_run233800_role39_saved_experts.json'
EXTRA=Path(__file__).parent/'fixtures/actual80_run233800_role39_author_trace_inputs.json'

def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')

class NoExternal:
    def __init__(self,attempts):self.attempts=attempts
    def __getattr__(self,name):
        def forbidden(*args,**kwargs):
            self.attempts.append(name)
            raise AssertionError('EXTERNAL_CALL_FORBIDDEN:'+name)
        return forbidden

def pipeline(tmp_path):
    attempts=[]
    pipe=AgenticPipeline(llm=NoExternal(attempts),mcp=NoExternal(attempts),output_dir=tmp_path/'output',max_iterations=1)
    pipe._use_session_knowledge=False
    pipe.enable_url_fetch_disk_cache=False
    return pipe,attempts

def context(title,body='',comments=(),*,character=False):
    raw={'post_id':1,'title':title,'content_blocks':copy.deepcopy(body) if isinstance(body,list)
         else [{'type':'text','text':body}]}
    ctx=ConversationContext(post_id=1,post_data=raw,comments=list(comments))
    ctx.search_results=[];ctx.fetched_page_info=[]
    ctx.set_expert_output(ExpertType.DECODER,{'decoded_terms':[
        {'original':'리샤','is_author_name':False,
         'grounding':{'is_grounded':True,'anchor_type':'character_mention'},
         'interpretations':[{'type':'character_name','value':'리샤','context_fit':'high'},
                            {'type':'author_name','value':'리샤','context_fit':'medium'}]}] if character else []})
    return ctx

def test_current39_does_not_join_external_author_gloss_with_comment_spell_use(tmp_path):
    raw=FIXTURE.read_bytes();extra_raw=EXTRA.read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='a5eff4d2943391d22bdf2bbfeb5bbb179f77728bc7d3699919b5d90036ee6456'
    assert hashlib.sha256(extra_raw).hexdigest()=='7a40f41e43b4ca310c2a00a0ad7937330d0ca73054ce4bf3126ab2cf8b122694'
    fixture=json.loads(raw);extra=json.loads(extra_raw);packet=fixture['packet']
    assert type(packet['post_id']) is int and packet['post_id']==10388511 and packet['index1']==39
    assert packet['run_id']==extra['run_id']=='20261012_233800_447943'
    assert packet['publication_scope_id']==extra['publication_scope_id']=='b67420bb3207d177cfb521bbbcdd0742ed06e50a0a0009e4d7c63812cca3e06c'
    assert hashlib.sha256(canonical({'post':packet['source_post'],'comments':packet['source_comments']})).hexdigest()==fixture['source_canonical_sha256']
    assert hashlib.sha256(canonical(packet['checkpoint_result'])).hexdigest()==fixture['result_canonical_sha256']
    pipe,attempts=pipeline(tmp_path)
    post=PostInput(**copy.deepcopy(packet['source_post']),comments=copy.deepcopy(packet['source_comments']))
    ctx=ConversationContext(post_id=post.post_id,post_data=pipe._post_to_dict(post),comments=pipe._extract_comments(post))
    ctx._final_source_original_inputs=pipe._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs=tuple(post.comments)
    ctx.post_data['image_enrichment']=copy.deepcopy(fixture['image_catalog'])
    for name,value in fixture['experts'].items():ctx.set_expert_output(ExpertType(name),copy.deepcopy(value))
    ctx.set_expert_output(ExpertType.SYNTHESIZER,copy.deepcopy(extra['logged_synthesizer_missing_in_role_fixture']['value']))
    ctx.llm_snippet_analysis=copy.deepcopy(extra['logged_snippet_analyzer']['value'])
    ctx.search_results=copy.deepcopy(fixture['search_catalog']);ctx.fetched_page_info=[]
    source_before=canonical({'post':ctx.post_data,'comments':ctx.comments,'experts':ctx.expert_outputs,'search':ctx.search_results})
    owners=dict(ctx.expert_outputs)
    metadata=ctx.get_expert_output(ExpertType.ARBITER)['metadata_synthesis']
    verifier=ctx.get_expert_output(ExpertType.VERIFIER)['verification_result']
    assert pipe._has_author_benchmark_or_advice_signal(ctx=ctx,metadata=metadata,verification_result=verifier,official_title=None) is False
    taxonomy=pipe._derive_output_taxonomy(ctx=ctx,is_relevant=True,discussion_type='general',official_title=None,
        title_candidates=[],primary_work=None,mentioned_works=[],comparison_target=None,recommendation_candidates=[],
        metadata=metadata,verification_result=verifier)
    assert taxonomy['subtype'] not in {'author_meta','release_serialization_meta'}
    assert pipe._derive_legacy_discussion_type(topicality=taxonomy['topicality'],subtype=taxonomy['subtype'],discussion_type='general')!='author_talk'
    assert canonical({'post':ctx.post_data,'comments':ctx.comments,'experts':ctx.expert_outputs,'search':ctx.search_results})==source_before
    assert all(ctx.expert_outputs[name] is owner for name,owner in owners.items())
    assert not attempts and FIXTURE.read_bytes()==raw and EXTRA.read_bytes()==extra_raw

@pytest.mark.parametrize('kind',['comment','ocr','generated','quoted_block','foreign_speaker','inline_quote','multiline_quote','quote_prefix','search'])
def test_foreign_or_quoted_benchmark_does_not_become_author_statement(tmp_path,kind):
    pipe,attempts=pipeline(tmp_path)
    cue='검미성 작가의 필력이 좋다'
    body=[];comments=[]
    if kind=='comment':comments=[cue]
    elif kind=='search':pass
    elif kind=='inline_quote':body=[{'type':'text','text':'댓글에 "'+cue+'"라고 했다'}]
    elif kind=='multiline_quote':body=[{'type':'text','text':'"인용 시작'}, {'type':'text','text':cue+'"'}]
    elif kind=='quote_prefix':body=[{'type':'text','text':'> '+cue}]
    else:
        flags={'ocr':{'type':'ocr_text'},'generated':{'is_generated':True},'quoted_block':{'is_quote':True},
               'foreign_speaker':{'speaker':'commenter'}}[kind]
        body=[{'type':'text','text':cue,**flags}]
    ctx=context('검미성 이야기',body,comments)
    if kind=='search':ctx.search_results=[{'title':cue,'content':cue}]
    before=canonical(ctx.post_data)
    assert pipe._has_author_benchmark_or_advice_signal(ctx=ctx,metadata={'detected_author':'검미성'}) is False
    assert canonical(ctx.post_data)==before and not attempts

@pytest.mark.parametrize('body',['리샤가 힐도 못쓰면 곤란하다','리샤가 마법을 못 쓰면 어떡함',
    '리샤의 전투 스타일이 바뀌었다','리샤의 커리어하이는 이번 전투다'])
def test_explicit_character_with_only_external_author_interpretation_is_not_author_benchmark(tmp_path,body):
    pipe,attempts=pipeline(tmp_path);ctx=context('리샤 이야기',body,character=True)
    before=canonical(ctx.expert_outputs)
    assert pipe._has_author_benchmark_or_advice_signal(ctx=ctx,metadata={}) is False
    assert canonical(ctx.expert_outputs)==before and not attempts

@pytest.mark.parametrize('title,body,author',[
    ('목마는 그냥 현판이나 써야댐','개돌도 후반 말아먹긴했지만 애호뉴비로 커리어하이 찍긴 했자나','목마'),
    ('잘생인방 뭔일 터짐?','민트초코주먹밥 작가 필력 얘기하다가 노피아 표지 때문에 터졌네','민트초코주먹밥'),
    ('검미성은 무협이나 써라','','검미성'),
    ('검미성 문체가 좋다','','검미성'),
    ('검미성은 글 쓰면 잘 쓰더라','','검미성'),
    ('검미성은 같은거 하나 써라','','검미성'),
])
def test_authored_writing_advice_and_existing_benchmark_recall_are_kept(tmp_path,title,body,author):
    pipe,attempts=pipeline(tmp_path);ctx=context(title,body)
    ctx.set_expert_output(ExpertType.GATEKEEPER,{'detected_entities':{'possible_authors':['목마','개돌']}})
    assert pipe._has_author_benchmark_or_advice_signal(ctx=ctx,metadata={'detected_author':author}) is True
    assert not attempts

@pytest.mark.parametrize('title,expected',[
    ('리샤 작가 문체가 좋다',True),('작가 리샤 문체가 좋다',True),
    ('리샤 작가가 아니라 인물이고 스타일만 바뀌었다',False),
    ('작가 리샤가 아니라 인물 리샤의 스타일이다',False),
])
def test_same_named_author_needs_explicit_undenied_authored_role(tmp_path,title,expected):
    pipe,attempts=pipeline(tmp_path);ctx=context(title,character=True)
    before=canonical(ctx.expert_outputs)
    assert pipe._has_author_benchmark_or_advice_signal(ctx=ctx,metadata={}) is expected
    assert canonical(ctx.expert_outputs)==before and not attempts

def test_source_mutation_and_exact_work_title_do_not_borrow_benchmark(tmp_path):
    pipe,attempts=pipeline(tmp_path)
    post=PostInput(post_id=1,title='검미성 이야기',content_blocks=[{'type':'text','text':'아직 의견이 없다'}],comments=[])
    ctx=ConversationContext(post_id=1,post_data=pipe._post_to_dict(post),comments=[])
    ctx._final_source_original_inputs=pipe._capture_final_source_original_inputs(post)
    ctx.post_data['content_blocks']=[{'type':'text','text':'검미성 작가의 필력이 좋다'}]
    assert pipe._has_author_benchmark_or_advice_signal(ctx=ctx,metadata={'detected_author':'검미성'}) is False
    fresh=context('검미성 문체가 좋다')
    assert pipe._has_author_benchmark_or_advice_signal(ctx=fresh,metadata={'detected_author':'검미성'},
        official_title='검미성 문체가 좋다') is False
    assert not attempts


@pytest.mark.parametrize('opening,closing', [('"','"'),('“','”'),("'","'"),('‘','’'),('「','」'),('『','』')])
@pytest.mark.parametrize('layout', ['blocks','one_field_lines','delimiter_fields','unclosed'])
def test_v2_multiline_quote_scope_is_bound_before_author_name_and_cue(tmp_path,opening,closing,layout):
    pipe,attempts=pipeline(tmp_path)
    cue='검미성 작가의 필력이 좋다'
    lines=[opening+'인용 시작',cue+closing]
    if layout=='one_field_lines':body=[{'type':'text','text':'\n'.join(lines)}]
    elif layout=='delimiter_fields':body=[{'type':'text','text':opening},{'type':'text','text':cue},{'type':'text','text':closing}]
    elif layout=='unclosed':body=[{'type':'text','text':opening+'인용 시작'},{'type':'text','text':cue}]
    else:body=[{'type':'text','text':line} for line in lines]
    ctx=context('검미성 이야기',body)
    before=canonical({'post':ctx.post_data,'experts':ctx.expert_outputs})
    assert pipe._has_author_benchmark_or_advice_signal(ctx=ctx,metadata={'detected_author':'검미성'}) is False
    assert canonical({'post':ctx.post_data,'experts':ctx.expert_outputs})==before and not attempts


@pytest.mark.parametrize('body', [
    [{'type':'text','text':'"인용 시작'},{'type':'text','text':'검미성 작가의 필력이 좋다"'},{'type':'text','text':'나는 검미성 작가 문체가 좋다'}],
    [{'type':'text','text':'"인용 시작'},{'type':'text','text':'검미성 작가의 필력이 좋다" 나는 검미성 작가 문체가 좋다'}],
    [{'type':'text','text':'"인용 시작'},{'type':'text','text':'검미성 작가의 필력이 좋다"'},{'type':'text','text':'검미성 작가의 필력이 좋다'}],
    [{'type':'text','text':'"검미성" 작가 문체가 좋다'}],
])
def test_v2_closed_quote_keeps_independent_authored_evaluation_at_its_own_offset(tmp_path,body):
    pipe,attempts=pipeline(tmp_path)
    ctx=context('검미성 이야기',body)
    before=canonical(ctx.post_data)
    assert pipe._has_author_benchmark_or_advice_signal(ctx=ctx,metadata={'detected_author':'검미성'}) is True
    assert canonical(ctx.post_data)==before and not attempts


@pytest.mark.parametrize('mode',['title_quote','ocr_quote','comment_quote','generated_quote'])
def test_v2_other_source_quote_does_not_mask_independent_author_body(tmp_path,mode):
    pipe,attempts=pipeline(tmp_path)
    title='검미성 "인용 시작' if mode=='title_quote' else '검미성 이야기'
    body=[];comments=['"인용 시작'] if mode=='comment_quote' else []
    if mode=='ocr_quote':body.append({'type':'ocr_text','text':'"인용 시작'})
    if mode=='generated_quote':body.append({'type':'text','text':'"인용 시작','is_generated':True})
    body.append({'type':'text','text':'검미성 작가 문체가 좋다'})
    ctx=context(title,body,comments)
    before=canonical({'post':ctx.post_data,'comments':ctx.comments})
    assert pipe._has_author_benchmark_or_advice_signal(ctx=ctx,metadata={'detected_author':'검미성'}) is True
    assert canonical({'post':ctx.post_data,'comments':ctx.comments})==before and not attempts


def test_v2_quote_and_occurrence_remain_bound_to_captured_original_fields(tmp_path):
    pipe,attempts=pipeline(tmp_path)
    post=PostInput(post_id=1,title='검미성 이야기',content_blocks=[
        {'type':'text','text':'"인용 시작'}, {'type':'text','text':'검미성 작가의 필력이 좋다"'}],comments=[])
    ctx=ConversationContext(post_id=1,post_data=pipe._post_to_dict(post),comments=[])
    ctx._final_source_original_inputs=pipe._capture_final_source_original_inputs(post)
    before=canonical(ctx._final_source_original_inputs)
    assert pipe._has_author_benchmark_or_advice_signal(ctx=ctx,metadata={'detected_author':'검미성'}) is False
    # 닫는 인용문과 같은 문장을 새 위치에 넣어도 원래 필드의 출현이 아니다.
    ctx.post_data['content_blocks'].append({'type':'text','text':'검미성 작가의 필력이 좋다'})
    assert pipe._has_author_benchmark_or_advice_signal(ctx=ctx,metadata={'detected_author':'검미성'}) is False
    ctx.post_data['content_blocks'][0]['text']='이제 인용이 아님'
    assert pipe._has_author_benchmark_or_advice_signal(ctx=ctx,metadata={'detected_author':'검미성'}) is False
    assert canonical(ctx._final_source_original_inputs)==before and not attempts


@pytest.mark.parametrize('opening,closing', [('"','"'),('“','”'),("'","'")])
@pytest.mark.parametrize('one_field', [False,True])
@pytest.mark.parametrize('captured', [False,True])
def test_v3_explicit_multiline_pen_name_is_a_name_not_a_report(tmp_path, opening, closing, one_field, captured):
    pipe, attempts = pipeline(tmp_path)
    lines = ['필명은 '+opening+'검미성', closing+'이다. 이 작가의 문체가 좋다.']
    body = [{'type':'text','text':'\n'.join(lines)}] if one_field else [{'type':'text','text':x} for x in lines]
    ctx = context('작가 품평', body)
    if captured:
        post = PostInput(post_id=1,title='작가 품평',content_blocks=body,comments=[])
        ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(post)
    before = canonical({'post':ctx.post_data,'experts':ctx.expert_outputs,
        'capture':ctx.__dict__.get('_final_source_original_inputs')})
    assert pipe._has_author_benchmark_or_advice_signal(ctx=ctx,metadata={'detected_author':'검미성'}) is True
    assert canonical({'post':ctx.post_data,'experts':ctx.expert_outputs,
        'capture':ctx.__dict__.get('_final_source_original_inputs')}) == before
    assert not attempts


@pytest.mark.parametrize('text', [
    '인용: 필명은 "검미성\n"이다. 이 작가의 문체가 좋다.',
    '친구가 “필명은 \'검미성\n\'이다. 이 작가의 문체가 좋다.”라고 말했다.',
    '필명은 "검미성은 글을 써라\n"이다. 이 작가의 문체가 좋다.',
    '필명은 "검미성\n"이 아니다. 이 작가의 문체가 좋다.',
    '필명은 "검미성\n"이라고 친구가 말했다. 이 작가의 문체가 좋다.',
    '필명은 "검미성\n"이라면 이 작가의 문체가 좋다.',
])
def test_v3_pen_name_exception_does_not_adopt_speech_denial_or_condition(tmp_path, text):
    pipe, attempts = pipeline(tmp_path)
    ctx = context('작가 품평', text)
    before = canonical(ctx.post_data)
    assert pipe._has_author_benchmark_or_advice_signal(ctx=ctx,metadata={'detected_author':'검미성'}) is False
    assert canonical(ctx.post_data) == before and not attempts


@pytest.mark.parametrize('flag,value', [('is_quoted',True),('is_post_author',False),('is_generated',True),('speaker','commenter'),('type','ocr_text')])
@pytest.mark.parametrize('call_before_change', [False,True])
def test_v3_captured_quote_opening_survives_later_lexical_exclusion(tmp_path, flag, value, call_before_change):
    pipe, attempts = pipeline(tmp_path)
    post = PostInput(post_id=1,title='검미성 이야기',content_blocks=[
        {'type':'text','text':'"인용 시작'}, {'type':'text','text':'검미성 작가의 필력이 좋다"'}],comments=[])
    ctx = ConversationContext(post_id=1,post_data=pipe._post_to_dict(post),comments=[])
    ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(post)
    captured = canonical(ctx._final_source_original_inputs)
    if call_before_change:
        assert pipe._has_author_benchmark_or_advice_signal(ctx=ctx,metadata={'detected_author':'검미성'}) is False
    ctx.post_data['content_blocks'][0][flag] = value
    before = canonical(ctx.post_data)
    assert pipe._has_author_benchmark_or_advice_signal(ctx=ctx,metadata={'detected_author':'검미성'}) is False
    assert canonical(ctx.post_data) == before
    assert canonical(ctx._final_source_original_inputs) == captured and not attempts


@pytest.mark.parametrize('flags', [{'is_quoted':True},{'is_generated':True},{'speaker':'commenter'},
    {'type':'ocr_text'},{'is_post_author':False}])
@pytest.mark.parametrize('captured', [False,True])
def test_v3_initial_external_open_quote_does_not_hide_independent_author_statement(tmp_path, flags, captured):
    pipe, attempts = pipeline(tmp_path)
    body = [{'type':'text','text':'"다른 자료의 끝나지 않은 인용',**flags},
        {'type':'text','text':'검미성 작가의 문체가 좋다'}]
    ctx = context('검미성 이야기', body)
    if captured:
        # 원래 PostInput capture가 보존하는 값과 위치를 사용한다. 출처 flag를 새로 발명하지 않는다.
        post = PostInput(post_id=1,title='검미성 이야기',content_blocks=body,comments=[])
        ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(post)
    before = canonical({'post':ctx.post_data,'capture':ctx.__dict__.get('_final_source_original_inputs')})
    assert pipe._has_author_benchmark_or_advice_signal(ctx=ctx,metadata={'detected_author':'검미성'}) is True
    assert canonical({'post':ctx.post_data,'capture':ctx.__dict__.get('_final_source_original_inputs')}) == before
    assert not attempts


def test_v3_nominal_name_is_not_itself_an_evaluation_cue(tmp_path):
    pipe, attempts = pipeline(tmp_path)
    ctx = context('작가 소개', '필명은 "필력\n"이다.')
    assert pipe._has_author_benchmark_or_advice_signal(ctx=ctx,metadata={'detected_author':'필력'}) is False
    assert not attempts


def test_v3_captured_field_path_cannot_be_replaced_with_equal_text(tmp_path):
    pipe, attempts = pipeline(tmp_path)
    post = PostInput(post_id=1,title='검미성 이야기',content_blocks=[
        {'type':'text','text':'검미성 작가의 문체가 좋다'}],comments=[])
    ctx = ConversationContext(post_id=1,post_data=pipe._post_to_dict(post),comments=[])
    ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(post)
    assert pipe._has_author_benchmark_or_advice_signal(ctx=ctx,metadata={'detected_author':'검미성'}) is True
    ctx.post_data['content'] = copy.deepcopy(ctx.post_data['content_blocks'])
    ctx.post_data['content_blocks'] = []
    assert pipe._has_author_benchmark_or_advice_signal(ctx=ctx,metadata={'detected_author':'검미성'}) is False
    assert not attempts
