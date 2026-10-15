"""ROOT 실행 전용: 저장 source→역할 producer/consumer, 완전 runtime 재현은 아님."""
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

FIXTURE = Path(__file__).parent / 'fixtures/nonwork_secondary_saved36_46.json'
FIXTURE_SHA = '0709d5086f7fa472c6fcfbb6a4fecc41a7828a4a1e41118bc25cc9fac22552ef'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


@pytest.fixture(scope='module')
def sut():
    names = ['llm_batch.agentic_pipeline', 'llm_batch.domain.models', 'llm_batch.experts.orchestrator',
             'llm_batch.grounding.degraded_reference_role', 'llm_batch.domain.batch_context',
             'llm_batch.ledger.publication_commit', 'expert_main']
    return SimpleNamespace(**{name.rsplit('.', 1)[-1]: importlib.import_module(name) for name in names})


@pytest.fixture(scope='module')
def facts():
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == FIXTURE_SHA
    data = json.loads(raw)
    for record in data['rows']:
        packet = record['packet']
        assert type(packet['post_id']) is int
        assert hashlib.sha256(canonical({'post':packet['source_post'], 'comments':packet['source_comments']})).hexdigest() == packet['source_canonical_sha256']
        assert hashlib.sha256(canonical(packet['checkpoint_result'])).hexdigest() == packet['result_canonical_sha256']
    before = canonical(data)
    yield data
    assert canonical(data) == before and FIXTURE.read_bytes() == raw


class ExternalAttempt(BaseException):
    pass


class NoExternal:
    def __init__(self):
        self.attempts = []

    def __getattr__(self, name):
        def denied(*args, **kwargs):
            self.attempts.append(name)
            raise ExternalAttempt('SECONDARY_ROLE_EXTERNAL_ATTEMPT:' + name)
        return denied


def context(sut, tmp_path, *, post=None, title='작품 참조 검토', body=(), comments=(), experts=()):
    raw = deepcopy(post) if post is not None else {'post_id':903646, 'title':title,
        'content_blocks':[{'type':'text', 'text':text} for text in body]}
    model = sut.models.PostInput(**raw, comments=deepcopy(list(comments)))
    external = NoExternal()
    pipe = sut.agentic_pipeline.AgenticPipeline(llm=external, mcp=external, output_dir=tmp_path,
        max_iterations=1, native_recovery=True, parallel_count=12, worker_id=0)
    pipe.enable_url_fetch_disk_cache = False
    pipe._use_session_knowledge = False
    ctx = sut.orchestrator.ConversationContext(post_id=model.post_id, post_data=pipe._post_to_dict(model),
        comments=pipe._extract_comments(model))
    ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(model)
    ctx._final_source_original_comment_refs = tuple(model.comments)
    for row in experts:
        ctx.set_expert_output(sut.orchestrator.ExpertType(row['expert']), deepcopy(row['value']))
    return pipe, ctx, external


def degraded(sut, title, **changes):
    values = dict(official_title=title, confidence='High', source_tier='llm_only',
        heretic_url=None, alias_or_mention=None, reference_role='mentioned', locked=False,
        negative_evidence=['url_title_mismatch:외부 검색의 다른 정식 표제', 'candidate_source_missing_url'])
    values.update(changes)
    return sut.models.DetectedTitle(**values)


def secondary(pipe, ctx, candidate):
    return pipe._collect_secondary_reference_works(ctx=ctx, official_title=None, primary_work=None,
        mentioned_works=[candidate], comparison_target=None, recommendation_candidates=[])


@pytest.mark.parametrize('index', [36, 46])
def test_saved_source_and_logged_experts_reject_recorded_secondary_at_real_consumer(sut, facts, tmp_path, index):
    record = next(row for row in facts['rows'] if row['index1'] == index)
    packet = record['packet']
    pipe, ctx, external = context(sut, tmp_path, post=packet['source_post'], comments=packet['source_comments'],
                                  experts=record['logged_experts']['records'])
    original = packet['checkpoint_result']['analysis_result']['identity']['secondary_reference_works'][0]
    candidate = sut.models.DetectedTitle(**deepcopy(original))
    before = canonical([ctx.post_data, ctx.comments, ctx.expert_outputs, candidate.model_dump(mode='json')])
    assert sut.degraded_reference_role.unbound_degraded_reference(ctx, candidate) is True
    assert secondary(pipe, ctx, candidate) == []
    assert canonical([ctx.post_data, ctx.comments, ctx.expert_outputs, candidate.model_dump(mode='json')]) == before
    assert not external.attempts


@pytest.mark.parametrize('index', [36, 46])
def test_saved_source_annotator_keeps_diagnostic_candidate_without_mentioned_or_secondary(sut, facts, tmp_path, index):
    record = next(row for row in facts['rows'] if row['index1'] == index)
    packet = record['packet']
    pipe, ctx, external = context(sut, tmp_path, post=packet['source_post'], comments=packet['source_comments'],
                                  experts=record['logged_experts']['records'])
    identity = packet['checkpoint_result']['analysis_result']['identity']
    candidate = sut.models.DetectedTitle(**deepcopy(identity['secondary_reference_works'][0]))
    before = canonical([ctx.post_data, ctx.comments, ctx.expert_outputs, candidate.model_dump(mode='json')])
    annotated, primary, mentioned, comparison = pipe._annotate_work_references(ctx=ctx,
        title_candidates=[candidate], official_title=None,
        vf_result=ctx.get_expert_output(sut.orchestrator.ExpertType.VERIFIER))
    target = candidate.official_title
    assert target in {item.official_title for item in annotated}
    assert all(item.reference_role == 'candidate' for item in annotated if item.official_title == target)
    assert target not in {item.official_title for item in mentioned}
    final_secondary = pipe._collect_secondary_reference_works(ctx=ctx, official_title=None, primary_work=primary,
        mentioned_works=mentioned, comparison_target=comparison, recommendation_candidates=[])
    assert target not in {item.official_title for item in final_secondary}
    assert canonical([ctx.post_data, ctx.comments, ctx.expert_outputs, candidate.model_dump(mode='json')]) == before
    assert not external.attempts
    (tmp_path / f'saved_{index}_local_boundary.json').write_text(json.dumps({
        'scope':'SAVED_SOURCE_RECORDED_TYPED_CANDIDATE_NOT_FULL_CONTEXT_REPLAY',
        'source_sha256':packet['source_canonical_sha256'], 'original_result_sha256':packet['result_canonical_sha256'],
        'annotated':[item.model_dump(mode='json') for item in annotated],
        'mentioned':[item.model_dump(mode='json') for item in mentioned],
        'secondary':[item.model_dump(mode='json') for item in final_secondary]}, ensure_ascii=False, indent=2), encoding='utf-8')


@pytest.mark.parametrize('index', [36, 46])
def test_saved_hold_publication_and_learning_boundary_remain_unchanged(sut, facts, index):
    packet = next(row['packet'] for row in facts['rows'] if row['index1'] == index)
    result = deepcopy(packet['checkpoint_result'])
    before = canonical(result)
    receipt = sut.publication_commit.compute_publication_decision_commit(result,
        publication_scope_id=packet['publication_scope_id'], attempt_run_id=packet['run_id'],
        input_index=index, post_id=packet['post_id'])
    sut.publication_commit.validate_publication_result_commit(result, receipt,
        expected_scope_id=packet['publication_scope_id'], expected_input_index=index, expected_post_id=packet['post_id'])
    memory = sut.batch_context.BatchContextMemory(enabled=True)
    assert receipt.outcome == 'HOLD' and receipt.publish_allowed is False
    assert sut.expert_main._learn_batch_context_from_canonical_publication(memory, result, receipt, created=True) is False
    assert memory.resolved_abbreviations == memory.resolved_authors == memory.resolved_characters == {}
    assert canonical(result) == before
    # 이것은 원형 저장 행의 계약 대조이며 새 결과의 WAL 성공을 주장하지 않는다.


@pytest.mark.parametrize('surface,body', [
    ('여름', '여름요정 작가의 신작 제목은 아직 모른다.'),
    ('은빛', '은빛바다 작가가 신작을 냈다.'),
    ('북쪽', '북쪽을 멸망시키고 시작하는 소설이 있다.'),
    ('왕국', '왕국 멸망 소재를 다루는 소설이 있다.'),
    ('봄', '소설 봄 멸망 소재를 이야기한다.'),
    ('행운', '소설 「행운」은 작품명이 아니다.'),
    ('중국', '작품명은 중국이 아니라 아직 모르는 이름이다.'),
    ('봄', '소설 「봄」이라는 말은 제목이 아닌 계절 설명이다.'),
])
def test_unbound_nonwork_or_name_denial_keeps_only_diagnostic_role(sut, tmp_path, surface, body):
    pipe, ctx, external = context(sut, tmp_path, body=[body])
    candidate = degraded(sut, surface)
    assert sut.degraded_reference_role.unbound_degraded_reference(ctx, candidate) is True
    assert secondary(pipe, ctx, candidate) == []
    assert not external.attempts


@pytest.mark.parametrize('surface,body', [
    ('행운', '나는 소설 「행운」을 비교해 읽었다.'),
    ('중국', '소설 『중국』을 읽었다.'),
    ('봄', '소설 봄을 읽었다.'),
    ('여름', '작품명은 여름이다.'),
    ('나는 오늘도 살아간다.', '소설 「나는 오늘도 살아간다.」를 읽었다.'),
    ('주무시기 전에 무엇을 하셨나요?', '소설 「주무시기 전에 무엇을 하셨나요?」를 읽었다.'),
    ('아카데미 생존 갤러리', '소설 「아카데미 생존 갤러리」를 읽었다.'),
    ('행운', '행운요정의 신작 제목은 모른다. 나는 소설 「행운」을 비교해 읽었다.'),
    ('봄', '작가는 소설 「봄」 같은 작품도 써 보라.'),
    ('봄', '나는 소설 「봄」을 읽지 않았다.'),
    ('봄', '친구가 소설 「봄」을 읽었다고 말했다.'),
    ('봄', '“나는 소설 「봄」을 읽었다.”'),
])
def test_independently_named_work_reference_survives_without_claiming_own_reading(sut, tmp_path, surface, body):
    pipe, ctx, external = context(sut, tmp_path, body=[body])
    candidate = degraded(sut, surface)
    assert sut.degraded_reference_role.unbound_degraded_reference(ctx, candidate) is False
    kept = secondary(pipe, ctx, candidate)
    assert len(kept) == 1 and kept[0].official_title == surface and kept[0].reference_role == 'mentioned'
    assert not external.attempts


@pytest.mark.parametrize('comment', ['나는 소설 「봄」을 읽었다.', '“소설 「봄」을 읽었다.”', '작품명은 봄이다.'])
def test_comment_named_work_is_reference_without_post_author_attribution(sut, tmp_path, comment):
    pipe, ctx, external = context(sut, tmp_path, title='봄요정 신작 제목은 모름',
        comments=[{'comment_id':735, 'author':'다른 독자', 'content':comment}])
    before = canonical([ctx.post_data, ctx.comments, ctx._final_source_original_inputs])
    candidate = degraded(sut, '봄')
    assert len(secondary(pipe, ctx, candidate)) == 1
    assert canonical([ctx.post_data, ctx.comments, ctx._final_source_original_inputs]) == before
    assert not external.attempts


@pytest.mark.parametrize('kind', ['working_insert', 'ocr_block', 'split_name'])
def test_generated_or_cross_field_name_cannot_supply_missing_original_role(sut, tmp_path, kind):
    post = {'post_id':903646, 'title':'봄요정 신작', 'content_blocks':[]}
    if kind == 'ocr_block': post['content_blocks'] = [{'type':'image', 'text':'소설 「봄」을 읽었다.', 'url':'https://example.invalid/image.png'}]
    if kind == 'split_name': post['content_blocks'] = [{'type':'text','text':'소설 「'}, {'type':'text','text':'봄」을 읽었다.'}]
    pipe, ctx, external = context(sut, tmp_path, post=post)
    if kind == 'working_insert': ctx.post_data['content_blocks'].append({'type':'text','text':'소설 「봄」을 읽었다.'})
    assert secondary(pipe, ctx, degraded(sut, '봄')) == []
    assert not external.attempts


@pytest.mark.parametrize('changes', [
    {'heretic_url':'https://novelpia.com/novel/934350', 'source_tier':'official_detail'},
    {'alias_or_mention':'아생갤'},
    {'negative_evidence':['candidate_source_missing_url']},
    {'negative_evidence':[]},
])
def test_qualified_url_alias_and_other_unresolved_paths_keep_existing_scope(sut, tmp_path, changes):
    pipe, ctx, external = context(sut, tmp_path)
    candidate = degraded(sut, '아카데미 생존 갤러리', **changes)
    assert sut.degraded_reference_role.unbound_degraded_reference(ctx, candidate) is False
    kept = secondary(pipe, ctx, candidate)
    assert len(kept) == 1 and kept[0].official_title == candidate.official_title
    assert not external.attempts


def reference_context(sut, tmp_path, raw, placement):
    # 명시 합성 문법 대조다. 저장36/46의 원문을 바꾸거나 과거 재생이라고 부르지 않는다.
    return context(sut, tmp_path, title='독서 이야기',
        body=[raw] if placement == 'body' else [],
        comments=[{'comment_id':735, 'author':'다른 독자', 'content':raw}] if placement == 'comment' else [])


@pytest.mark.parametrize('surface,raw,placement', [
    ('중국', '『중국』이라는 소설을 읽었다.', 'comment'),
    ('봄', '봄이라는 소설을 읽었다.', 'comment'),
    ('여름', '「여름」이란 작품을 비교했다.', 'comment'),
    ('중국', '친구가 『중국』이라는 소설을 읽었다고 말했다.', 'body'),
    ('봄', '“『봄』이라는 소설을 읽었다.”', 'comment'),
    ('봄', '『봄』이라는 소설을 읽지 않았다.', 'comment'),
    ('나는 오늘도 살아간다.', '『나는 오늘도 살아간다.』라는 소설을 읽었다.', 'comment'),
    ('아카데미 생존 갤러리', '「아카데미 생존 갤러리」라는 웹소설을 읽었다.', 'body'),
])
def test_postfix_named_work_reference_preserves_source_and_mentioned_role(sut, tmp_path, surface, raw, placement):
    pipe, ctx, external = reference_context(sut, tmp_path, raw, placement)
    candidate = degraded(sut, surface)
    before = canonical([ctx.post_data, ctx.comments, ctx._final_source_original_inputs, candidate.model_dump(mode='json')])
    assert sut.degraded_reference_role.unbound_degraded_reference(ctx, candidate) is False
    kept = secondary(pipe, ctx, candidate)
    assert len(kept) == 1 and kept[0].official_title == surface and kept[0].reference_role == 'mentioned'
    assert canonical([ctx.post_data, ctx.comments, ctx._final_source_original_inputs, candidate.model_dump(mode='json')]) == before
    assert not external.attempts


@pytest.mark.parametrize('raw,placement', [
    ('소설 「봄」이라고 썼지만 그건 실제 작품명이 아니다.', 'comment'),
    ('소설 「봄」이라고 썼지만 그건 실제 작품명이 아니다.', 'body'),
    ('작품 「봄」이라고 적었는데 그 이름은 정식 제목이 아니다.', 'comment'),
    ('소설 『봄』이라고 불렀으나 『봄』은 작품명이 아니다.', 'body'),
    ('소설 「봄」이라고 쓴 것은 작품명이 아니다.', 'comment'),
    ('소설 「봄」이라고 표현했다. 그것은 소설의 제목이 아니다.', 'body'),
    ('나는 소설 「봄」을 읽지 않았다. 그건 작품명이 아니다.', 'body'),
    ('나는 소설 「봄」을 읽었다. 「봄」은 작품명이 아니다.', 'body'),
])
def test_same_field_name_withdrawal_precedes_author_occurrence_and_comment_fallback(sut, tmp_path, raw, placement):
    pipe, ctx, external = reference_context(sut, tmp_path, raw, placement)
    candidate = degraded(sut, '봄')
    before = canonical([ctx.post_data, ctx.comments, ctx._final_source_original_inputs, candidate.model_dump(mode='json')])
    assert sut.degraded_reference_role.unbound_degraded_reference(ctx, candidate) is True
    assert secondary(pipe, ctx, candidate) == []
    assert canonical([ctx.post_data, ctx.comments, ctx._final_source_original_inputs, candidate.model_dump(mode='json')]) == before
    assert not external.attempts


@pytest.mark.parametrize('raw', [
    '『봄』이라는 소설가는 유명하다.',
    '『봄』이라는 소재를 다루는 글이다.',
    '『봄』이라는 단어를 골랐다.',
    '『봄』이라는 소설은 아니다.',
])
def test_postfix_naming_does_not_turn_person_material_word_or_denial_into_work(sut, tmp_path, raw):
    pipe, ctx, external = reference_context(sut, tmp_path, raw, 'comment')
    assert sut.degraded_reference_role.unbound_degraded_reference(ctx, degraded(sut, '봄')) is True
    assert secondary(pipe, ctx, degraded(sut, '봄')) == []
    assert not external.attempts


@pytest.mark.parametrize('placement,positive_first', [('body',False), ('body',True), ('comment',False), ('comment',True)])
def test_independent_positive_occurrence_survives_another_name_withdrawal_in_same_field(sut, tmp_path, placement, positive_first):
    positive = '나는 소설 「봄」을 읽었다.'
    withdrawn = '메모에는 소설 「봄」이라고 썼지만 그건 실제 작품명이 아니다.'
    raw = ' '.join([positive, withdrawn] if positive_first else [withdrawn, positive])
    pipe, ctx, external = reference_context(sut, tmp_path, raw, placement)
    candidate = degraded(sut, '봄')
    assert sut.degraded_reference_role.unbound_degraded_reference(ctx, candidate) is False
    kept = secondary(pipe, ctx, candidate)
    assert len(kept) == 1 and kept[0].official_title == '봄' and kept[0].reference_role == 'mentioned'
    assert not external.attempts


@pytest.mark.parametrize('mutation', ['working_body', 'working_comment'])
def test_uncaptured_working_positive_cannot_undo_original_name_withdrawal(sut, tmp_path, mutation):
    raw = '소설 「봄」이라고 썼지만 그건 실제 작품명이 아니다.'
    pipe, ctx, external = reference_context(sut, tmp_path, raw, 'body')
    original_capture = canonical(ctx._final_source_original_inputs)
    if mutation == 'working_body':
        ctx.post_data['content_blocks'].append({'type':'text','text':'나는 소설 「봄」을 읽었다.'})
    else:
        ctx.comments.append('나는 소설 「봄」을 읽었다.')
    assert sut.degraded_reference_role.unbound_degraded_reference(ctx, degraded(sut, '봄')) is True
    assert secondary(pipe, ctx, degraded(sut, '봄')) == []
    assert canonical(ctx._final_source_original_inputs) == original_capture
    assert not external.attempts
