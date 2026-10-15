"""저장39 관측과 일반 역할 반례의 초안. 전체 런 재현/사람 정답/품질 PASS가 아니다."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import DetectedTitle, PostInput
from llm_batch.experts.orchestrator import ConversationContext, ExpertType
from test_source_bound_propriety_question_state import NoExternal

FIXTURE = Path(__file__).parent/'fixtures/actual80_run233800_role39_saved_experts.json'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')


def pipeline(tmp_path):
    pipe = AgenticPipeline(llm=NoExternal(), mcp=NoExternal(), output_dir=tmp_path,
                           max_iterations=1, native_recovery=True)
    pipe.enable_url_fetch_disk_cache = False
    pipe._use_session_knowledge = False
    return pipe


def make_context(pipe, title, body='', comments=(), images=()):
    post = PostInput(post_id=80239, title=title, author='작성자',
                    content_blocks=[{'type':'text', 'text':body}], comments=list(comments))
    ctx = ConversationContext(post_id=post.post_id, post_data=pipe._post_to_dict(post), comments=pipe._extract_comments(post))
    ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs = tuple(post.comments)
    ctx.post_data['image_enrichment'] = copy.deepcopy(list(images))
    ctx.search_results = []
    ctx.fetched_page_info = []
    return ctx


def current(tmp_path):
    fixture = json.loads(FIXTURE.read_bytes())
    packet = fixture['packet']
    assert packet['run_id'] == '20261012_233800_447943'
    assert packet['publication_scope_id'] == 'b67420bb3207d177cfb521bbbcdd0742ed06e50a0a0009e4d7c63812cca3e06c'
    assert type(packet['index1']) is int and packet['index1'] == 39
    assert type(packet['post_id']) is int and packet['post_id'] == packet['source_post']['post_id']
    assert hashlib.sha256(canonical({'post':packet['source_post'], 'comments':packet['source_comments']})).hexdigest() == fixture['source_canonical_sha256']
    assert hashlib.sha256(canonical(packet['checkpoint_result'])).hexdigest() == fixture['result_canonical_sha256']
    pipe = pipeline(tmp_path)
    post = PostInput(**packet['source_post'], comments=packet['source_comments'])
    ctx = ConversationContext(post_id=post.post_id, post_data=pipe._post_to_dict(post), comments=pipe._extract_comments(post))
    ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs = tuple(post.comments)
    ctx.post_data['image_enrichment'] = copy.deepcopy(fixture['image_catalog'])
    for name, value in fixture['experts'].items():
        ctx.set_expert_output(ExpertType(name), copy.deepcopy(value))
    ctx.search_results = copy.deepcopy(fixture['search_catalog'])
    ctx.fetched_page_info = []  # 원래 fetch를 발명하지 않는다.
    return pipe, ctx, fixture


def character_term(name, evidence):
    return {'original':name, 'is_author_name':False, 'candidates':[],
            'interpretations':[{'type':'character_name','value':name,'context_fit':'high'}],
            'grounding':{'is_grounded':True,'anchor_type':'character_mention','anchor_evidence':evidence}}


def test_current39_character_source_binding_preserves_experts_and_alias(tmp_path):
    before = FIXTURE.read_bytes()
    pipe, ctx, record = current(tmp_path)
    roots = {name:ctx.get_expert_output(ExpertType(name)) for name in record['experts']}
    values = canonical(roots)
    for name in ('디오니소스', '리샤'):
        proof = pipe._source_character_work_conflict(ctx, name)
        assert proof['blocked'] is True
        assert proof['source_occurrences']
        assert proof['publication_authority'] is False
    assert pipe._source_character_work_conflict(ctx, '판타지 수학 대전')['blocked'] is False
    assert canonical(roots) == values
    assert all(ctx.get_expert_output(ExpertType(name)) is root for name,root in roots.items())
    assert FIXTURE.read_bytes() == before


def test_current39_weak_character_mention_not_comparison_work(tmp_path):
    pipe, ctx, record = current(tmp_path)
    identity = record['packet']['checkpoint_result']['analysis_result']['identity']
    mentioned = [DetectedTitle(**item) for item in identity['mentioned_works']]
    before = [item.model_dump() for item in mentioned]
    projected = pipe._project_unverified_mentioned_works(mentioned, ctx=ctx)
    assert projected[0].official_title is None
    assert projected[0].reference_role == 'candidate'
    assert projected[0].alias_or_mention == '디오니소스'
    assert 'source_character_surface_not_work' in projected[0].negative_evidence
    primary = DetectedTitle(official_title='판타지 수학 대전', confidence='Low')
    comparison, _ = pipe._derive_reference_targets(ctx=ctx, discussion_type='review',
        title_candidates=mentioned, primary_work=primary, mentioned_works=mentioned)
    assert comparison is None
    assert [item.model_dump() for item in mentioned] == before
    assert identity['mentioned_works'][0]['official_title'] == '디오니소스'


@pytest.mark.parametrize('change', ['ground_bool', 'anchor_kind', 'anchor_text', 'source', 'quoted_source'])
def test_character_rejection_cannot_reuse_unbound_or_mutated_proof(tmp_path, change):
    pipe = pipeline(tmp_path)
    raw = '루미가 성문을 지켰다'
    ctx = make_context(pipe, raw)
    term = character_term('루미', raw)
    ctx.set_expert_output(ExpertType.DECODER, {'decoded_terms':[term]})
    assert pipe._source_character_work_conflict(ctx, '루미')['blocked'] is True
    if change == 'ground_bool': term['grounding']['is_grounded'] = 'true'
    elif change == 'anchor_kind': term['grounding']['anchor_type'] = 'title_mention'
    elif change == 'anchor_text': term['grounding']['anchor_evidence'] = '다른 글의 루미'
    elif change == 'source': ctx.post_data['title'] = '원문이 교체됨'
    else:
        ctx = make_context(pipe, '인용: '+raw)
        ctx.set_expert_output(ExpertType.DECODER, {'decoded_terms':[term]})
    assert pipe._source_character_work_conflict(ctx, '루미')['blocked'] is False


def test_character_same_named_official_work_and_explicit_work_are_retained(tmp_path):
    pipe = pipeline(tmp_path)
    raw = '루미가 성문을 지켰다'
    term = character_term('루미', raw)
    ctx = make_context(pipe, raw, '소설 루미도 읽었다')
    ctx.set_expert_output(ExpertType.DECODER, {'decoded_terms':[term]})
    assert pipe._source_character_work_conflict(ctx, '루미')['reason'] == 'INDEPENDENT_SOURCE_WORK_NAMING'
    ctx = make_context(pipe, raw)
    ctx.set_expert_output(ExpertType.DECODER, {'decoded_terms':[term]})
    ctx.search_results = [{'title':'루미', 'url':'https://novelpia.com/novel/884002',
                           'snippet':'작품명 루미. 작가 별하.', 'source_tier':'official_detail'}]
    # 이 검사는 공식 상세 검색 항목의 recall 보존이다. fetch나 게시물↔작품 연결을 발명하지 않는다.
    assert pipe._source_character_work_conflict(ctx, '루미')['blocked'] is False


def test_normal_author_and_explicit_alias_roles_are_not_character_only(tmp_path):
    pipe = pipeline(tmp_path)
    ctx = make_context(pipe, '별하 작가의 달항로 신작 소식', '달항로는 달의 항로의 약칭이다')
    ctx.set_expert_output(ExpertType.DECODER, {'decoded_terms':[
        {'original':'별하','is_author_name':True, 'author_info':{'name':'별하'},
         'interpretations':[{'type':'author_name','value':'별하','context_fit':'high'}]},
        {'original':'달항로','is_author_name':False,
         'interpretations':[{'type':'work_alias','value':'달의 항로','context_fit':'high'}]}]})
    assert pipe._source_character_work_conflict(ctx, '별하')['blocked'] is False
    assert pipe._source_character_work_conflict(ctx, '달의 항로')['blocked'] is False
    assert pipe._get_identified_author(ctx) == '별하'


def test_canonical_rescue_does_not_promote_character_wiki_title(tmp_path):
    pipe = pipeline(tmp_path)
    raw = '루미가 성문을 지켰다'
    ctx = make_context(pipe, raw)
    ctx.set_expert_output(ExpertType.DECODER, {'decoded_terms':[character_term('루미', raw)]})
    ctx.search_results = [{'title':'루미', 'url':'https://namu.wiki/w/루미',
                           'snippet':'작중 인물 루미의 행적'}]
    result = pipe._select_best_canonical_rescue_candidate(ctx=ctx, vf_result={}, seed_titles=['루미'])
    assert result['title'] is None


@pytest.mark.parametrize('title,expected', [
    ('작품A랑 작품B 비교 리뷰', True), ('작품A와 작품B의 차이', True), ('작품A vs 작품B', True),
    ('작품A와 작품B 읽었다', False), ('작품A 읽었다. 작품B는 나중에. 다른 얘기를 비교함', False)])
def test_comparison_requires_author_pair_and_relation(tmp_path, title, expected):
    pipe = pipeline(tmp_path)
    ctx = make_context(pipe, title)
    a = DetectedTitle(official_title='작품A', confidence='High', source_tier='official_detail')
    b = DetectedTitle(official_title='작품B', confidence='Medium', source_tier='community')
    result, _ = pipe._derive_reference_targets(ctx=ctx, discussion_type='review',
        title_candidates=[a,b], primary_work=a, mentioned_works=[b])
    assert (result is not None) is expected
    if expected: assert result.official_title == '작품B'


def test_recommendation_list_and_comment_comparison_do_not_invent_author_comparison(tmp_path):
    pipe = pipeline(tmp_path)
    ctx = make_context(pipe, '작품 추천 부탁해요', comments=['작품A와 작품B 비교하면 좋겠다'])
    a, b = [DetectedTitle(official_title=t, confidence='Medium') for t in ('작품A', '작품B')]
    result, recommendations = pipe._derive_reference_targets(ctx=ctx, discussion_type='recommendation',
        title_candidates=[a,b], primary_work=None, mentioned_works=[a,b])
    assert result is None
    assert [x.official_title for x in recommendations] == ['작품A','작품B']


def test_current39_ineligible_ocr_cannot_set_state_or_recall_view(tmp_path):
    pipe, ctx, record = current(tmp_path)
    raw_images = canonical(ctx.post_data['image_enrichment'])
    assert pipe._source_image_title_recall_allowed(ctx, ctx.post_data['image_enrichment'][0]) is False
    view = pipe._build_official_url_recall_identity(ctx=ctx, extended_identity={
        'official_title':None,'work_resolution':'unresolved','title_resolution_state':'unresolved_matchable'})
    assert view['image_evidence_catalog'] == []
    fields = pipe._derive_resolution_scope_fields(ctx=ctx, is_relevant=True, official_title=None,
        discussion_type='author_talk', topicality='core_relevant', subtype='review_reaction',
        work_resolution='unresolved', verification_result=record['experts']['verifier']['verification_result'],
        final_decision=record['experts']['arbiter'].get('final_decision', {}))
    assert fields['title_resolution_state'] != 'ocr_explicit_title_unresolved'
    assert fields['title_resolution_allowed'] is False
    assert canonical(ctx.post_data['image_enrichment']) == raw_images


@pytest.mark.parametrize('flag', ['false', 0, 1])
def test_malformed_image_eligibility_is_not_a_bool(tmp_path, flag):
    pipe = pipeline(tmp_path)
    item = {'explicit_work_title':'달의 항로','evidence_type':'explicit_text',
            'title_role':'work_title','promotion_eligible':flag}
    ctx = make_context(pipe, '무관한 이야기', images=[item])
    assert pipe._source_image_title_recall_allowed(ctx, item) is False


def test_eligible_surface_and_existing_cover_exception_preserved(tmp_path):
    pipe = pipeline(tmp_path)
    item = {'explicit_work_title':'달의 항로','evidence_type':'explicit_text',
            'title_role':'work_title','promotion_eligible':True}
    ctx = make_context(pipe, '오늘 읽은 소설', images=[item])
    assert pipe._source_image_title_recall_allowed(ctx, item) is True
    cover = dict(item, promotion_eligible=False, evidence_type='cover_title',
                 title_role='unknown',focus_role='work_anchor',explicit_author_name='별하')
    assert pipe._source_image_title_recall_allowed(ctx, cover) is True


def test_ineligible_image_with_native_author_work_relation_preserved(tmp_path):
    pipe = pipeline(tmp_path)
    item = {'explicit_work_title':'달의 항로','evidence_type':'explicit_text',
            'title_role':'unknown','promotion_eligible':False}
    ctx = make_context(pipe, '감상', '나는 달의 항로를 읽었다.', images=[item])
    candidate = DetectedTitle(official_title='달의 항로',confidence='Low',source_tier='llm_only')
    native = pipe._image_work_relation(ctx, candidate)
    assert native.supports_primary is True
    assert pipe._source_image_title_recall_allowed(ctx, item) is True


def test_recall_rechecks_image_role_after_upstream_false_proposal(tmp_path, monkeypatch):
    pipe, ctx, _ = current(tmp_path)
    image = ctx.post_data['image_enrichment'][0]
    identity = {'official_title':None, 'title_resolution_state':'unresolved_matchable','work_resolution':'unresolved'}
    candidates = []
    # 성공을 만들기 위한 gate stub이 아니다. 잘못된 upstream 제안을 강제로 넣어 최종 거절을 검사한다.
    monkeypatch.setattr('llm_batch.agentic_pipeline.official_url_recoverable', lambda _identity: {
        'official_title':image['explicit_work_title'], 'heretic_url':'https://novelpia.com/novel/884003',
        'source':'search_evidence', 'source_tier':'official_detail','confidence':'High'})
    result, output_candidates, primary, promotion = pipe._apply_official_url_recall_promotion(
        ctx=ctx, extended_identity=identity, title_candidates=candidates, primary_work=None,
        verification_result={}, final_decision={})
    assert result is identity and output_candidates is candidates
    assert primary is None and promotion is None


@pytest.mark.parametrize('suffix', [
    '읽어보다', '물어보다', '살펴보다', '알아보다', '돌아보다',
    '읽어보다는 말만 했다', '읽어보다고 적었다', '한번 보다',
])
def test_v2_reading_verbs_do_not_create_comparison_roles(tmp_path, suffix):
    pipe=pipeline(tmp_path)
    title='봄날기록과 가을편지를 '+suffix
    ctx=make_context(pipe,title)
    before=canonical(ctx.post_data)
    a=DetectedTitle(official_title='봄날기록',confidence='High')
    b=DetectedTitle(official_title='가을편지',confidence='Medium')
    result,_=pipe._derive_reference_targets(ctx=ctx,discussion_type='review',
        title_candidates=[a,b],primary_work=a,mentioned_works=[b])
    assert result is None
    assert canonical(ctx.post_data)==before


@pytest.mark.parametrize('left,right,text', [
    ('봄날인가?','가을편지','봄날인가?와 가을편지의 전개를 비교하면'),
    ('봄날인가?','가을편지','봄날인가?와 가을편지의 차이'),
    ('봄날이다!','가을편지','봄날이다!와 가을편지는 비슷하다'),
    ('봄날.기록','가을편지','봄날.기록과 가을편지 비교 리뷰'),
    ('봄날。기록','가을편지','봄날。기록과 가을편지를 비교해보면'),
    ('봄날기록','가을인가?','봄날기록과 가을인가?의 차이'),
    ('봄날인가?','가을이다!','봄날인가?와 가을이다!의 전개를 비교하면'),
    ('봄날인가?','가을이다!','봄날인가?보다 가을이다!가 낫다'),
    ('봄날인가?','가을이다!','봄날인가?가 가을이다!보다 좋았다'),
    ('봄날기록','가을편지','봄날기록 vs. 가을편지'),
    ('봄날기록','가을편지','봄날기록은 재밌는 반면 가을편지는 지루했다'),
    ('봄날기록','가을편지','봄날기록만큼 가을편지도 재밌다'),
])
def test_v2_punctuation_inside_verified_title_spans_keeps_real_comparison(tmp_path,left,right,text):
    pipe=pipeline(tmp_path)
    ctx=make_context(pipe,text)
    before=canonical(ctx.post_data)
    a=DetectedTitle(official_title=left,confidence='High')
    b=DetectedTitle(official_title=right,confidence='Medium')
    result,_=pipe._derive_reference_targets(ctx=ctx,discussion_type='review',
        title_candidates=[a,b],primary_work=a,mentioned_works=[b])
    assert result is not None and result.official_title==right
    assert canonical(ctx.post_data)==before


@pytest.mark.parametrize('text', [
    '봄날인가?를 읽었다. 가을편지를 비교하면',
    '봄날인가?와 가을편지를 읽었다! 비교 리뷰는 내일 쓴다',
    '봄날인가?\n가을편지의 전개를 비교하면',
    '봄날인가?와 가을편지를 읽어보다',
    '봄날인가?와 가을편지를 읽었다 다른 인물을 비교했다',
    '봄날인가?보다가 가을편지를 읽었다',
    '봄날인가?와 가을편지 비교사 안내',
    '봄날인가? vs.\n가을편지',
])
def test_v2_title_punctuation_does_not_erase_external_boundaries_or_verb_roles(tmp_path,text):
    pipe=pipeline(tmp_path)
    ctx=make_context(pipe,text)
    a=DetectedTitle(official_title='봄날인가?',confidence='High')
    b=DetectedTitle(official_title='가을편지',confidence='Medium')
    result,_=pipe._derive_reference_targets(ctx=ctx,discussion_type='review',
        title_candidates=[a,b],primary_work=a,mentioned_works=[b])
    assert result is None


def test_v2_alias_surface_punctuation_and_captured_source_drift(tmp_path):
    pipe=pipeline(tmp_path)
    ctx=make_context(pipe,'봄날인가?와 가을편지의 전개를 비교하면')
    a=DetectedTitle(official_title='봄날의 긴 정식 이름',alias_or_mention='봄날인가?',confidence='High')
    b=DetectedTitle(official_title='가을편지',confidence='Medium')
    assert pipe._source_reference_comparison_supported(ctx,b,[a]) is True
    ctx.post_data['title']='봄날인가?와 가을편지를 읽어보다'
    assert pipe._source_reference_comparison_supported(ctx,b,[a]) is False
