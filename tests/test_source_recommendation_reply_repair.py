"""ROOT의 END 후 격리 단일 실행용. 원형26 진단/기대값은 수정하지 않는다."""
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import pytest

FIXTURES = Path(__file__).parent / 'fixtures'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture(scope='module')
def facts():
    contract = json.loads((FIXTURES / 'recommendation_reply_execution.json').read_bytes())
    rows = {}
    for filename, pin in contract['fixture_sha256'].items():
        assert sha(FIXTURES / filename) == pin
        rows[filename] = json.loads((FIXTURES / filename).read_bytes())
    d26 = rows['recommendation26_saved_source.json']; p71 = rows['recommendation71_source_packet.json']
    current = d26['current26']
    assert hashlib.sha256(canonical({'post': current['source_post'], 'comments': current['source_comments']})).hexdigest() == current['source_canonical_sha256']
    assert hashlib.sha256(canonical({'post': p71['source_post'], 'comments': p71['source_comments']})).hexdigest() == p71['source_canonical_sha256']
    assert hashlib.sha256(canonical(p71['checkpoint_result'])).hexdigest() == p71['result_canonical_sha256']
    before = canonical(rows)
    yield SimpleNamespace(d26=d26, p71=p71, contract=contract)
    assert canonical(rows) == before
    for filename, pin in contract['fixture_sha256'].items():
        assert sha(FIXTURES / filename) == pin


@pytest.fixture(scope='module')
def sut(facts):
    # 고정 원문·지원 시험의 계약은 유지하고 현재 checkout의 제품을 검사한다.
    tree = Path(__file__).resolve().parents[1]
    names = ['llm_batch.agentic_pipeline', 'llm_batch.domain.models', 'llm_batch.experts.orchestrator',
             'llm_batch.ledger.publication_commit', 'expert_main',
             'test_source_bound_propriety_question_state', 'test_comment_answer_original_recall']
    paths = {name: tree / ('expert_main.py' if name == 'expert_main' else
                          'tests/' + name + '.py' if name.startswith('test_') else
                          'src/' + name.replace('.', '/') + '.py') for name in names}
    before = {name: path.read_bytes() for name, path in paths.items()}
    modules = {}
    for name in names:
        module = importlib.import_module(name)
        assert Path(module.__file__).resolve() == paths[name].resolve()
        modules[name.rsplit('.', 1)[-1]] = module
    yield SimpleNamespace(**modules)
    assert all(path.read_bytes() == before[name] for name, path in paths.items())



class ExternalAttempt(BaseException):
    pass


class NoExternal:
    def __init__(self): self.attempts = []
    def __getattr__(self, name):
        def denied(*args, **kwargs):
            self.attempts.append(name)
            raise ExternalAttempt('NO_MODEL_SEARCH_FETCH:' + name)
        return denied


def context(sut, tmp_path, record=None, *, title='', body=(), comments=()):
    raw = deepcopy(record['source_post']) if record else {'post_id': 902671, 'title': title,
        'content_blocks': [{'type': 'text', 'text': x} for x in body]}
    comments = deepcopy(record['source_comments'] if record else comments)
    post = sut.models.PostInput(**raw, comments=comments)
    external = NoExternal()
    pipe = sut.agentic_pipeline.AgenticPipeline(llm=external, mcp=external, output_dir=tmp_path,
        max_iterations=1, parallel_count=12, worker_id=0, native_recovery=True)
    pipe.enable_url_fetch_disk_cache = False; pipe._use_session_knowledge = False
    ctx = sut.orchestrator.ConversationContext(post_id=post.post_id, post_data=pipe._post_to_dict(post),
                                              comments=pipe._extract_comments(post))
    ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs = tuple(post.comments)
    ctx._source_bound_nsfw_original_carrier = pipe._capture_source_bound_nsfw_carrier(post)
    return pipe, ctx, external


def collect(pipe, ctx):
    values = pipe._collect_comment_answer_preservation_candidates(ctx, discussion_type='recommendation')
    assert all(x.confidence == 'Low' and x.reference_role == 'candidate'
               and 'comment_answer_preservation_only' in x.negative_evidence for x in values)
    return values


def comment(text, cid='a', parent=None, level=0):
    return {'comment_id': cid, 'content': text, 'author': '응답자',
            'reply_level': level, 'reply_to_comment_id': parent}


@pytest.fixture(scope='module')
def current26(sut, facts, tmp_path_factory):
    tmp = tmp_path_factory.mktemp('reply26')
    row = facts.d26['current26']
    pipe, ctx, external = context(sut, tmp, row)
    for name, payload in row['experts'].items():
        ctx.set_expert_output(sut.orchestrator.ExpertType(name), deepcopy(payload))
    assert set(row['experts']) == {'gatekeeper', 'discourse'}
    disc = row['experts']['discourse']['discourse_analysis']
    ctx.primary_domain, ctx.discourse_intent = disc['primary_domain'], disc['intent']
    ctx.discourse_warning = row['observed_context']['discourse_warning']
    for attr, key in (('_candidate_producer_plans', 'candidate_producer_plans'),
        ('_candidate_producer_receipts', 'candidate_producer_receipts'), ('_candidate_generation_stage_receipts', 'candidate_stage_receipts')):
        if key in row['stored_candidate_ledger']:
            setattr(ctx, attr, deepcopy(row['stored_candidate_ledger'][key]))
    source_before = canonical([ctx.post_data, ctx.comments, ctx._final_source_original_inputs, ctx._final_source_original_comment_refs])
    expert_before = canonical(ctx.expert_outputs)
    request = pipe._post_comment_answer_request_observation(ctx)
    initial = collect(pipe, ctx)
    output = pipe._context_to_output(ctx)
    payload = output.model_dump(mode='json')
    pipe.verify_final_source_context_serialization(output, payload, stage='reply26_context')
    stages = {'context': deepcopy(payload['identity'])}
    helper = sut.test_source_bound_propriety_question_state
    helper.synchronize_like_actual_main(payload, ctx.post_data)
    pipe.verify_final_source_context_serialization(output, payload, stage='reply26_main')
    stages['main'] = deepcopy(payload['identity'])
    full = dict(deepcopy(row['source_post']), comments=deepcopy(row['source_comments']), analysis_result=payload)
    wrapped = helper.wrapper_class()(full, output=output, verifier=pipe.verify_final_source_context_serialization)
    ledger = sut.publication_commit
    descriptor = ledger.build_publication_scope_descriptor(input_file_sha256=row['source_canonical_sha256'],
        post_ids=[ctx.post_id], config_hash='recommendation-reply-repair', release_fingerprint='isolated-partial-context')
    wal = tmp / 'publication.jsonl'; registry = ledger.PublicationCommitRegistry(wal, scope_descriptor=descriptor, create_new=True)
    receipt, created = ledger.commit_publication_result(wrapped, registry=registry,
        attempt_run_id='reply26-local', input_index=1, post_id=ctx.post_id)
    saved = ledger.PublicationCommitRegistry(wal, scope_descriptor=descriptor, create_new=False).result(ctx.post_id)
    wrapped.verify_stored_payload(saved, stage='reply26_wal')
    stages['wal'] = deepcopy(saved['analysis_result']['identity'])
    assert saved['analysis_result'] == payload
    assert source_before == canonical([ctx.post_data, ctx.comments, ctx._final_source_original_inputs, ctx._final_source_original_comment_refs])
    assert external.attempts == []
    report = {'scope': 'SAVED26_TWO_EXPERTS_PARTIAL_CONTEXT_NOT_FULL_RUNTIME', 'request': request,
        'initial': [v.model_dump(mode='json') for v in initial], 'stages': stages,
        'commit': {'created': created, 'outcome': receipt.outcome, 'publish_allowed': receipt.publish_allowed},
        'source_unchanged': True, 'working_experts_unchanged': canonical(ctx.expert_outputs) == expert_before,
        'external_attempts': external.attempts}
    (tmp / 'reply26_observation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    return report


def low_answer(rows, name):
    matches = [x for x in rows or () if x.get('official_title') == name]
    assert len(matches) == 1
    value = matches[0]
    assert value['confidence'] == 'Low' and value['reference_role'] == 'candidate'
    assert value.get('heretic_url') in (None, '')
    assert 'comment_answer_preservation_only' in value['negative_evidence']


def test_current26_initial_request_and_named_response_recovered(current26):
    assert current26['request']['kind'] == 'source_elliptic_narrative_recommendation_request'
    assert current26['request']['scope'] == 'low_reply_preservation_only'
    low_answer(current26['initial'], '라노토벌')


def test_current26_low_survives_context_main_wal_without_publication(current26):
    for value in current26['stages'].values():
        low_answer(value['recommendation_candidates'], '라노토벌')
        assert value['novel_identity'] in (None, {'official_title': None, 'heretic_url': None})
        assert value['title_resolution_allowed'] is False
        assert value['promotion_decision']['publish_allowed'] is False
    assert current26['commit'] == {'created': True, 'outcome': 'HOLD', 'publish_allowed': False}


def test_current71_source_only_named_replies_low_and_other_comments_not_titles(sut, facts, tmp_path):
    pipe, ctx, external = context(sut, tmp_path, facts.p71)
    before = canonical([ctx.post_data, ctx.comments])
    assert pipe._post_comment_answer_request_kind(ctx) == 'source_novel_existence_request'
    rows = collect(pipe, ctx)
    assert {x.official_title for x in rows} == {'우주괴물', '메카네크'}
    assert all(x.heretic_url is None and pipe._local_hold_has_work_role(ctx, x) for x in rows)
    preserved = pipe._build_candidate_preservation_sources(title_candidates=[], mentioned_works=[],
        comparison_target=None, recommendation_candidates=rows, secondary_reference_works=None)
    assert all(x['promotion_policy'] == 'hold_without_promotion' for x in preserved)
    assert before == canonical([ctx.post_data, ctx.comments]) and external.attempts == []


@pytest.mark.parametrize('index', ['18', '32', '49'])
def test_original_real_negative_sources_unchanged(sut, facts, tmp_path, index):
    pipe, ctx, external = context(sut, tmp_path, facts.d26['source_only_negative_controls'][index])
    assert collect(pipe, ctx) == [] and external.attempts == []


@pytest.mark.parametrize('name', ['food_comparison', 'daily_walk', 'explicit_movie', 'explicit_webtoon', 'explicit_game'])
def test_original_food_daily_other_media_expectations_unchanged(sut, facts, tmp_path, name):
    row = next(x for x in facts.d26['synthetic_negative_controls'] if x['name'] == name)
    pipe, ctx, external = context(sut, tmp_path, row)
    before = canonical([ctx.post_data, ctx.comments])
    assert collect(pipe, ctx) == []
    assert before == canonical([ctx.post_data, ctx.comments]) and external.attempts == []


@pytest.mark.parametrize('method', ['test_recommendation_comment_answers_are_preserved_as_candidates',
    'test_reply_chain_slash_title_answers_are_preserved_without_single_promotion',
    'test_local_hold_candidate_snapshot_keeps_preservation_type'])
def test_original_three_positive_methods_called_without_changing_expectations(sut, method):
    case = sut.test_comment_answer_original_recall.OriginalCommentRecallTests(method)
    result = unittest.TestResult(); case.run(result)
    assert result.testsRun == 1 and not result.skipped and result.wasSuccessful(), result.errors + result.failures


@pytest.mark.parametrize('text,expected', [('책 추천해줘', True), ('읽을 책을 추천해줘', True),
    ('소설같은거 추천해줘', True), ('해외소설이라도 추천해줘', True),
    ('산책할 곳 추천해줘', False), ('책장 추천해줘', False), ('정책 추천해줘', False),
    ('이런 장면이 나오는 판타지영화 추천해줘', False), ('판타지 웹툰 추천해줘', False),
    ('영화 같은 소설 추천해줘', True), ('소설 같은 영화 추천해줘', False)])
def test_request_nouns_and_particles_are_not_substrings(sut, tmp_path, text, expected):
    pipe, _, external = context(sut, tmp_path, title='요청')
    assert bool(pipe._comment_work_request_kind(text)) is expected
    assert not external.attempts


@pytest.mark.parametrize('text,expected', [('이런거 나오는 소설 없냐', True), ('웹소설이 있나요?', True),
    ('해외소설은 없을까?', True), ('이런 소설은 없다.', False),
    ('만약 이런 소설이 없다면', False), ('친구가 소설 없냐고 물었어', False),
    ('“이런 소설 없냐”라고 말했다.', False), ('게임 소설 같은 영화 없냐', False)])
def test_existence_request_vs_statement_quote_and_medium(sut, tmp_path, text, expected):
    pipe, _, external = context(sut, tmp_path, title='요청')
    assert (pipe._comment_work_request_kind(text) == 'source_novel_existence_request') is expected
    assert not external.attempts


@pytest.mark.parametrize('alias', ['은하의 끝', '아생갤', '새로 나온 긴 작품명'])
def test_unregistered_comparison_name_is_not_a_title_or_id_allowlist(sut, tmp_path, alias):
    pipe, ctx, external = context(sut, tmp_path, title='재회 장면이 보고싶다',
        body=[f'{alias}같은거 추천해줘', '진한 구원이 보고싶어'], comments=[comment('제목: 새로운 약속')])
    obs = pipe._post_comment_answer_request_observation(ctx)
    assert obs['comparison_observation']['surface'] == alias
    assert obs['supports_publish'] is False
    assert [v.official_title for v in collect(pipe, ctx)] == ['새로운 약속']
    assert not external.attempts


@pytest.mark.parametrize('mode', ['request_quote', 'request_other', 'scene_quote', 'taste_other', 'missing_scene',
    'missing_taste', 'film', 'webtoon', 'game', 'carried_quote', 'wrong_parent', 'typed_parent'])
def test_elliptic_request_requires_same_author_narrative_and_answer_relation(sut, tmp_path, mode):
    title = '재회 장면이 보고싶다'; body = ['은하항로같은거 추천해줘', '진한 구원이 보고싶어']
    comments = [comment('제목: 새로운 약속')]
    if mode == 'request_quote': body[0] = '“은하항로같은거 추천해줘”라고 말했다.'
    if mode == 'request_other': body[0] = '친구가 은하항로같은거 추천해줘'
    if mode == 'scene_quote': title = '“재회 장면이 보고싶다”라고 말했다.'
    if mode == 'taste_other': body[1] = '친구가 진한 구원이 보고싶어'
    if mode == 'missing_scene': title = '오늘 이야기'
    if mode == 'missing_taste': body = body[:1]
    if mode in {'film', 'webtoon', 'game'}: body[0] = {'film':'영화','webtoon':'웹툰','game':'게임'}[mode] + '같은거 추천해줘'
    if mode == 'carried_quote': body = ['“', *body, '”라고 말했다.']
    if mode == 'wrong_parent': comments = [comment('제목: 새로운 약속', parent='missing', level=1)]
    if mode == 'typed_parent': comments = [comment('소설 없냐', cid=5), comment('제목: 새로운 약속', parent='5', level=1)]
    pipe, ctx, external = context(sut, tmp_path, title=title, body=body, comments=comments)
    assert collect(pipe, ctx) == [] and not external.attempts


@pytest.mark.parametrize('answer', ['제목: 나는 오늘도 살아간다.', '제목: 산책', '제목: 게임',
    '[새로운 약속](https://novelpia.com/novel/998811)'])
def test_explicit_named_or_official_link_answer_keeps_low_candidate(sut, tmp_path, answer):
    pipe, ctx, external = context(sut, tmp_path, title='이런 소설 없냐', comments=[comment(answer)])
    rows = collect(pipe, ctx)
    assert len(rows) == 1 and pipe._local_hold_has_work_role(ctx, rows[0])
    assert not external.attempts


def test_same_name_inside_work_title_is_not_requested_other_medium(sut, tmp_path):
    pipe, ctx, external = context(sut, tmp_path, title='소설 「게임」 같은거 추천해줘', comments=[comment('제목: 새로운 약속')])
    assert [x.official_title for x in collect(pipe, ctx)] == ['새로운 약속']
    assert not external.attempts
