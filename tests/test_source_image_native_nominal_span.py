"""원문 명사구와 native event 결속 회귀 초안. ROOT 실행 전이며 전체 런 재현이 아니다."""
import copy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import pytest

from llm_batch import promotion_gate
from test_source_role39_boundaries import pipeline, make_context, DetectedTitle


OBSERVATION = Path(__file__).parent/'fixtures/role39_image_native_observed_failure_v1.json'
OBSERVATION_SHA = '101bf76ae25aa2e203884117256b7a11291517b7ee19eb3a42ef7e4f5a0d050e'


def source(ctx):
    return copy.deepcopy({'original':ctx._final_source_original_inputs,
                          'title':ctx.post_data['title'], 'blocks':ctx.post_data['content_blocks'],
                          'comments':ctx.comments})


def image(title):
    return {'explicit_work_title':title,'evidence_type':'explicit_text',
            'title_role':'unknown','promotion_eligible':False}


def relation(pipe, ctx, title):
    return pipe._image_work_relation(ctx,DetectedTitle(official_title=title,confidence='Low',source_tier='llm_only'))


def mentions(pipe, body):
    return pipe._image_source_mentions(body,lambda _position:0)


def test_observed_original_role39_input_binds_complete_source_np_to_native_event(tmp_path):
    raw=OBSERVATION.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==OBSERVATION_SHA
    observed=json.loads(raw)
    assert observed['supports_primary'] is False  # 기존 실패 관측은 바꾸지 않는다.
    assert [m['fields']['title'] for m in observed['direct_source_mentions']]==['항로']
    inp=observed['input']
    assert inp['body']=='나는 달의 항로를 읽었다.'
    pipe=pipeline(tmp_path)
    ctx=make_context(pipe,inp['title'],inp['body'],images=[inp['image']])
    before=source(ctx)
    current=pipe._image_work_relation(ctx,DetectedTitle(**inp['candidate']))
    assert current.supports_primary is True
    assert current.supporting_event_ids
    assert pipe._source_image_title_recall_allowed(ctx,inp['image']) is True
    body=inp['body']
    found=[m for m in ctx._image_work_mentions['달의항로'] if m.title=='달의 항로']
    assert len(found)==1
    mention=found[0]
    assert (mention.start,mention.end)==(3,8)
    assert body[mention.start:mention.end]==mention.title
    events=ctx._image_post_event_graphs[body]
    assert any(e.target_mention_id==mention.mention_id and e.actor=='author'
               and e.assertion_mode in {'direct','corrected'} and e.polarity=='positive' for e in events)
    reducer=ctx._image_native_reducers['달의항로']
    assert reducer.authority is True and reducer.support_event_ids
    assert source(ctx)==before and OBSERVATION.read_bytes()==raw


@pytest.mark.parametrize('title', ['달의 항로','바다 항로','태양의 바다 항로','태양의 바다의 항로','은빛항로'])
def test_compound_and_genitive_nominal_name_keeps_exact_source_span(tmp_path,title):
    pipe=pipeline(tmp_path)
    body='나는 '+title+'를 읽었다.'
    ctx=make_context(pipe,'감상',body,images=[image(title)])
    before=source(ctx)
    found=[m for m in mentions(pipe,body) if m.title==title]
    assert len(found)==1
    assert (found[0].start,found[0].end)==(3,3+len(title))
    assert body[found[0].start:found[0].end]==title
    assert relation(pipe,ctx,title).supports_primary is True
    assert source(ctx)==before


@pytest.mark.parametrize('prefix', ['나는 ','내가 ','나는 나의 ','나는 내 ','나는 우리의 ','나는 친구의 '])
def test_subject_and_contextual_owner_are_outside_source_work_name(tmp_path,prefix):
    pipe=pipeline(tmp_path)
    title='달의 항로'
    body=prefix+title+'를 읽었다.'
    found=mentions(pipe,body)
    names=[m.title for m in found]
    assert title in names
    assert not any(name.startswith(('나는 ','내가 ','나의 ','내 ','우리의 ','친구의 ')) for name in names)
    target=next(m for m in found if m.title==title)
    assert target.start==len(prefix) and body[target.start:target.end]==title


@pytest.mark.parametrize('body', [
    '친구는 달의 항로를 읽었다.',
    '나는 달의 항로를 읽지 않았다.',
    '나는 달의 항로를 읽으면 좋겠다.',
    '나는 달의 항로를 읽을 예정이다.',
    '친구는 "나는 달의 항로를 읽었다."라고 말했다.',
    '나는 "달의 항로를 읽었다"라는 댓글을 읽었다.',
    '나는 달의 항로의 표지를 읽었다.',
    '나는 달의 항로의 댓글을 읽었다.',
    '나는 달의 항로라는 앱의 문구를 읽었다.',
    '나는 달의 항로를 읽었다고 썼지만 실제로 읽지 않았다.',
])
def test_full_name_does_not_override_native_actor_mood_quote_or_object_role(tmp_path,body):
    pipe=pipeline(tmp_path)
    ctx=make_context(pipe,'감상',body,images=[image('달의 항로')])
    before=source(ctx)
    assert relation(pipe,ctx,'달의 항로').supports_primary is False
    assert pipe._source_image_title_recall_allowed(ctx,image('달의 항로')) is False
    assert source(ctx)==before


@pytest.mark.parametrize('body', ['나는 「달의 항로」를 읽었다.','나는 달의 항로라는 소설을 읽었다.'])
def test_existing_delimited_and_explicit_naming_recall_stays_supported(tmp_path,body):
    pipe=pipeline(tmp_path)
    ctx=make_context(pipe,'감상',body,images=[image('달의 항로')])
    before=source(ctx)
    assert any(m.title=='달의 항로' for m in mentions(pipe,body))
    assert relation(pipe,ctx,'달의 항로').supports_primary is True
    assert source(ctx)==before


def test_source_graph_does_not_follow_candidate_inventory_or_order(tmp_path):
    pipe=pipeline(tmp_path)
    body='나는 달의 항로를 읽었다.'
    baseline_mentions=[asdict(m) for m in mentions(pipe,body)]
    baseline_events=[asdict(e) for e in pipe._image_build_native_source_graph(body,[(0,len(body),0)],mentions(pipe,body))]
    for titles in [[],['바다 항로'],['달의 항로','바다 항로'],['바다 항로','달의 항로']]:
        ctx=make_context(pipe,'감상',body,images=[image(title) for title in titles])
        before=source(ctx)
        for title in titles: relation(pipe,ctx,title)
        current_mentions=mentions(pipe,body)
        current_events=pipe._image_build_native_source_graph(body,[(0,len(body),0)],current_mentions)
        assert [asdict(m) for m in current_mentions]==baseline_mentions
        assert [asdict(e) for e in current_events]==baseline_events
        if body in getattr(ctx,'_image_post_event_graphs',{}):
            assert [asdict(e) for e in ctx._image_post_event_graphs[body]]==baseline_events
        assert source(ctx)==before


def test_no_morphology_does_not_invent_compound_np_from_candidate(tmp_path,monkeypatch):
    # 이용 불가를 만드는 음성 대조다. 성공 결과나 authority는 주입하지 않는다.
    monkeypatch.setattr(promotion_gate,'_edition_kiwi',lambda:None)
    pipe=pipeline(tmp_path)
    body='나는 달의 항로를 읽었다.'
    assert not any(m.title=='달의 항로' for m in mentions(pipe,body))
    ctx=make_context(pipe,'감상',body,images=[image('달의 항로')])
    assert relation(pipe,ctx,'달의 항로').supports_primary is False
    assert any(m.title=='달의 항로' for m in mentions(pipe,'나는 「달의 항로」를 읽었다.'))


@pytest.mark.parametrize('owner', ['작가','집필자'])
def test_f1_person_owner_overlapping_work_head_keeps_original_single_title(tmp_path,owner):
    pipe=pipeline(tmp_path)
    title='은빛항로'
    body='나는 '+owner+'의 '+title+'를 읽었다.'
    found=mentions(pipe,body)
    assert title in [m.title for m in found]
    assert owner+'의 '+title not in [m.title for m in found]
    target=next(m for m in found if m.title==title)
    assert target.start==body.index(title) and body[target.start:target.end]==title
    ctx=make_context(pipe,'감상',body,images=[image(title)])
    before=source(ctx)
    current=relation(pipe,ctx,title)
    assert current.supports_primary is True and current.supporting_event_ids
    assert pipe._source_image_title_recall_allowed(ctx,image(title)) is True
    assert source(ctx)==before


@pytest.mark.parametrize('owner', ['작가','집필자'])
@pytest.mark.parametrize('template', [
    '친구는 {owner}의 은빛항로를 읽었다.',
    '나는 {owner}의 은빛항로를 읽지 않았다.',
    '나는 {owner}의 은빛항로를 읽으면 좋겠다.',
    '나는 {owner}의 은빛항로를 읽을 예정이다.',
    '친구는 "나는 {owner}의 은빛항로를 읽었다"고 말했다.',
])
def test_f1_owner_removal_does_not_override_negative_or_foreign_statement(tmp_path,owner,template):
    pipe=pipeline(tmp_path)
    body=template.format(owner=owner)
    ctx=make_context(pipe,'감상',body,images=[image('은빛항로')])
    before=source(ctx)
    assert relation(pipe,ctx,'은빛항로').supports_primary is False
    assert pipe._source_image_title_recall_allowed(ctx,image('은빛항로')) is False
    assert source(ctx)==before


@pytest.mark.parametrize('owner', ['작가','집필자'])
@pytest.mark.parametrize('template', ['나는 「{title}」를 읽었다.','나는 {title}라는 소설을 읽었다.'])
def test_f1_explicit_full_title_keeps_lexical_person_role_inside_name(tmp_path,owner,template):
    pipe=pipeline(tmp_path)
    title=owner+'의 은빛항로'
    body=template.format(title=title)
    found=mentions(pipe,body)
    assert title in [m.title for m in found]
    target=next(m for m in found if m.title==title)
    assert body[target.start:target.end]==title
    ctx=make_context(pipe,'감상',body,images=[image(title)])
    before=source(ctx)
    assert relation(pipe,ctx,title).supports_primary is True
    assert source(ctx)==before


@pytest.mark.parametrize('owner', ['작가','집필자'])
def test_f1_unmarked_owner_phrase_does_not_authorize_same_named_full_title(tmp_path,owner):
    # 같은 문자열이 실제 표제일 가능성만으로 문맥 소유자를 표제에 붙이지 않는다.
    # 위의 명시 따옴표/명명 양성과 대조하며 NIL이나 비관련으로 바꾸지 않는다.
    pipe=pipeline(tmp_path)
    plain='은빛항로'
    owner_prefixed=owner+'의 '+plain
    body='나는 '+owner_prefixed+'를 읽었다.'
    ctx=make_context(pipe,'감상',body,images=[image(owner_prefixed),image(plain)])
    before=source(ctx)
    assert relation(pipe,ctx,owner_prefixed).supports_primary is False
    assert pipe._source_image_title_recall_allowed(ctx,image(owner_prefixed)) is False
    assert relation(pipe,ctx,plain).supports_primary is True
    assert source(ctx)==before


@pytest.mark.parametrize('quotes', [('"','"'), ("'","'"), ('“','”'), ('‘','’'), ('「','」'), ('『','』')])
@pytest.mark.parametrize('break_text', ['. ', '.\n'])
def test_source_quote_keeps_native_attribution_across_sentence_boundaries(tmp_path, quotes, break_text):
    pipe = pipeline(tmp_path)
    title = '달의 항로'
    utterance = '나는 '+title+'를 읽었다'+break_text+'결말이 좋다.'
    body = '친구는 '+quotes[0]+utterance+quotes[1]+'라고 말했다.'
    ctx = make_context(pipe, '감상', body, images=[image(title)])
    before = source(ctx)
    assert relation(pipe, ctx, title).supports_primary is False
    assert pipe._source_image_title_recall_allowed(ctx, image(title)) is False
    events = ctx._image_post_event_graphs[body]
    scoped = [e for e in events if body[slice(*e.evidence_span)].startswith(('읽', '좋'))]
    assert scoped
    for event in scoped:
        assert event.assertion_mode == 'quoted'
        assert dict(event.native_trace.mood_flags)['quoted'] is True
        assert event.native_trace.attribution == 'quoted'
        evidence = event.native_trace.attribution_evidence
        assert evidence.text == quotes[0]+utterance+quotes[1]
        assert body[slice(*evidence.span)] == evidence.text
    assert source(ctx) == before


@pytest.mark.parametrize('owner', ['', '작가의 ', '집필자의 '])
@pytest.mark.parametrize('ending', ['읽으면 좋겠다.', '읽으면 좋다.', '읽었다면 좋겠다.', '읽으면 좋겠다고 생각했다.'])
def test_conditional_evaluation_does_not_create_an_independent_actual_work_event(tmp_path, owner, ending):
    pipe = pipeline(tmp_path)
    title = '은빛항로'
    body = '나는 '+owner+title+'를 '+ending
    ctx = make_context(pipe, '감상', body, images=[image(title)])
    before = source(ctx)
    assert relation(pipe, ctx, title).supports_primary is False
    assert pipe._source_image_title_recall_allowed(ctx, image(title)) is False
    evaluations = [e for e in ctx._image_post_event_graphs[body]
        if body[slice(*e.evidence_span)].startswith('좋')]
    assert evaluations
    for event in evaluations:
        assert event.assertion_mode == 'hypothetical'
        assert event.native_trace.mood == 'conditional'
        assert dict(event.native_trace.mood_flags)['conditional'] is True
        evidence = event.native_trace.mood_evidence
        assert body[slice(*evidence.span)] == evidence.text
    assert source(ctx) == before


@pytest.mark.parametrize('body', [
    '나는 「은빛항로」를 읽었다.',
    '나는 「은빛항로」의 결말이 좋다고 평가한다.',
    '나는 「은빛항로」의 전개가 훌륭하다고 평가한다.',
    '친구는 "나는 은빛항로를 읽었다."라고 말했다. 나는 「은빛항로」를 읽었다.',
    '나는 작가의 은빛항로를 읽으면 좋겠다. 나는 「은빛항로」를 읽었다.',
    '나는 작가의 은빛항로를 읽었다. 결말이 좋겠다는 희망도 있다.',
])
def test_quote_and_modal_scope_preserves_independent_actual_reading_and_evaluation(tmp_path, body):
    pipe = pipeline(tmp_path)
    title = '은빛항로'
    ctx = make_context(pipe, '감상', body, images=[image(title)])
    before = source(ctx)
    current = relation(pipe, ctx, title)
    assert current.supports_primary is True and current.supporting_event_ids
    assert pipe._source_image_title_recall_allowed(ctx, image(title)) is True
    reducer = ctx._image_native_reducers[pipe._normalize_match_text(title)]
    assert reducer.authority is True
    assert source(ctx) == before


@pytest.mark.parametrize('body', [
    "John's 추천으로 나는 「은빛항로」를 읽었다. Jane's 글은 별개다.",
    "James' 추천으로 나는 「은빛항로」를 읽었다. Jones' 글은 별개다.",
    "John’s 추천으로 나는 「은빛항로」를 읽었다. Jane’s 글은 별개다.",
    "Don't worry. 나는 「은빛항로」를 읽었다. It's fine.",
    '표시는 \\"이고 나는 「은빛항로」를 읽었다. 다음 표시도 \\"이다.',
])
def test_v4_apostrophe_and_escaped_delimiter_do_not_quote_actual_reading(tmp_path,body):
    pipe=pipeline(tmp_path)
    title='은빛항로'
    ctx=make_context(pipe,'감상',body,images=[image(title)])
    before=source(ctx)
    current=relation(pipe,ctx,title)
    assert current.supports_primary is True and current.supporting_event_ids
    events=[e for e in ctx._image_post_event_graphs[body]
            if body[slice(*e.evidence_span)].startswith('읽었다')]
    assert events
    assert any(e.assertion_mode=='direct' and e.native_trace.attribution=='direct'
               and dict(e.native_trace.mood_flags)['quoted'] is False for e in events)
    assert source(ctx)==before


@pytest.mark.parametrize('body', [
    "친구는 '나는 「은빛항로」를 읽었다. 결말이 좋다.'라고 말했다.",
    "친구는'나는 「은빛항로」를 읽었다. 결말이 좋다.'라고 말했다.",
    "친구는 'John's 추천으로 나는 「은빛항로」를 읽었다. 결말이 좋다.'라고 말했다.",
])
def test_v4_real_single_quote_keeps_reading_quoted_with_word_apostrophe_inside(tmp_path,body):
    pipe=pipeline(tmp_path)
    title='은빛항로'
    ctx=make_context(pipe,'감상',body,images=[image(title)])
    before=source(ctx)
    assert relation(pipe,ctx,title).supports_primary is False
    events=[e for e in ctx._image_post_event_graphs[body]
            if body[slice(*e.evidence_span)].startswith('읽었다')]
    assert events and all(e.assertion_mode=='quoted' and e.native_trace.attribution=='quoted' for e in events)
    assert all(body[slice(*e.native_trace.attribution_evidence.span)]==e.native_trace.attribution_evidence.text for e in events)
    assert source(ctx)==before


@pytest.mark.parametrize('owner',['작가의 ','집필자의 '])
@pytest.mark.parametrize('bridge',[' 정말 ',' 매우 ', ', ', '， ', ', 정말 ', ' 아주 '])
def test_v4_same_clause_conditional_evaluation_survives_adverb_and_comma(tmp_path,owner,bridge):
    pipe=pipeline(tmp_path)
    title='은빛항로'
    body='나는 '+owner+title+'를 읽으면'+bridge+'좋다.'
    ctx=make_context(pipe,'감상',body,images=[image(title)])
    before=source(ctx)
    assert relation(pipe,ctx,title).supports_primary is False
    assert pipe._source_image_title_recall_allowed(ctx,image(title)) is False
    events=[e for e in ctx._image_post_event_graphs[body] if body[slice(*e.evidence_span)].startswith('좋다')]
    assert events
    for event in events:
        assert event.assertion_mode=='hypothetical'
        assert event.native_trace.mood=='conditional'
        assert dict(event.native_trace.mood_flags)['conditional'] is True
        evidence=event.native_trace.mood_evidence
        assert body[slice(*evidence.span)]==evidence.text and '읽으면' in evidence.text
    assert source(ctx)==before


@pytest.mark.parametrize('body', [
    '나는 작가의 은빛항로를 읽으면 정말 좋다. 나는 「은빛항로」를 읽었다.',
    '나는 작가의 은빛항로를 읽으면, 좋다. 나는 「은빛항로」의 문체가 좋다고 평가한다.',
    '나는 작가의 은빛항로를 읽으면 좋겠지만 나는 「은빛항로」를 읽었다.',
    '나는 작가의 은빛항로를 읽으면 좋겠지만 지금은 「은빛항로」의 문체가 좋다.',
    '나는 작가의 은빛항로를 읽으면 좋겠다고 생각했다. 하지만 지금은 「은빛항로」를 읽었다.',
    '나는 작가의 은빛항로를 읽으면 정말 좋다; 나는 「은빛항로」의 문체가 좋다고 평가한다.',
])
def test_v4_independent_actual_reading_or_evaluation_does_not_inherit_old_conditional(tmp_path,body):
    pipe=pipeline(tmp_path)
    title='은빛항로'
    ctx=make_context(pipe,'감상',body,images=[image(title)])
    before=source(ctx)
    current=relation(pipe,ctx,title)
    assert current.supports_primary is True and current.supporting_event_ids
    assert pipe._source_image_title_recall_allowed(ctx,image(title)) is True
    assert source(ctx)==before
