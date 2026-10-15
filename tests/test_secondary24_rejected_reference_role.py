"""검토된 search-only 거절→원문 관계→역할 producer/consumer. ROOT 오프라인 실행용."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import subprocess

import pytest

from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.alias_learning import capture_alias_source
from llm_batch.domain.models import DetectedTitle, PostInput
from llm_batch.experts.orchestrator import ConversationContext, ExpertType
from llm_batch.grounding.rejected_reference_role import rejected_search_reference

FIXTURE = Path(__file__).parent / 'fixtures/secondary24_saved_context.json'
FIXTURE_SHA = '56b4760b633d9078b1af4c4a1ef834f454605febcbcf599d445204f807dbc97d'
TITLE = '은빛 항로의 탐험가'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


@pytest.fixture(autouse=True)
def no_external(monkeypatch):
    def forbidden(*args, **kwargs):
        raise ExternalAttempt('SECONDARY24_NO_NETWORK_OR_CHILD')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(subprocess, 'run', forbidden)


class ExternalAttempt(BaseException):
    pass


class NoExternal:
    def __getattr__(self, name):
        def forbidden(*args, **kwargs):
            raise ExternalAttempt('SECONDARY24_EXTERNAL:' + name)
        return forbidden


@pytest.fixture(scope='module')
def facts():
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == FIXTURE_SHA
    value = json.loads(raw)
    packet = value['packet']
    assert type(packet['post_id']) is int and packet['index1'] == 24
    assert hashlib.sha256(canonical({'post': packet['source_post'], 'comments': packet['source_comments']})).hexdigest() == packet['source_canonical_sha256']
    assert hashlib.sha256(canonical(packet['checkpoint_result'])).hexdigest() == packet['result_canonical_sha256']
    for expert in value['logged_experts']:
        assert hashlib.sha256(canonical(expert['value'])).hexdigest() == expert['canonical_sha256']
    yield value
    assert FIXTURE.read_bytes() == raw and canonical(value) == canonical(json.loads(raw))


def verification(title=TITLE):
    return {'grounding_check': {'decoder_grounded': False, 'anchor_found': 'search_only'},
        'counter_arguments': [{'issue': f"Decoder의 '{title}' 매칭 오류", 'severity': 'critical', 'action': 'reject'}]}


def context(tmp_path, *, post=None, body=(), comments=(), experts=(), search=()):
    raw = deepcopy(post) if post is not None else {'post_id': 902424, 'title': '전투 연출 취향',
        'content_blocks': [{'type': 'text', 'text': value} for value in body]}
    typed = PostInput(**raw, comments=deepcopy(list(comments)))
    pipe = AgenticPipeline(llm=NoExternal(), mcp=NoExternal(), output_dir=tmp_path,
        max_iterations=1, native_recovery=True, parallel_count=12, worker_id=0)
    pipe.enable_heretic_live_fetch = False
    pipe.enable_url_fetch_disk_cache = False
    pipe._use_session_knowledge = False
    ctx = ConversationContext(post_id=typed.post_id, post_data=pipe._post_to_dict(typed),
        comments=pipe._extract_comments(typed))
    ctx._batch_alias_original_source = capture_alias_source(typed)
    ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(typed)
    ctx._final_source_original_comment_refs = tuple(typed.comments)
    ctx.search_results = deepcopy(list(search))
    for item in experts:
        ctx.set_expert_output(ExpertType(item['expert']), deepcopy(item['value']))
    return pipe, ctx


def candidate(title=TITLE, **overrides):
    return DetectedTitle(**dict(dict(official_title=title, confidence='High', heretic_url=None,
        locked=False, reference_role='mentioned', source_tier='llm_only',
        negative_evidence=['candidate_source_missing_url']), **overrides))


def collect(pipe, ctx, cand, lane='mentioned'):
    return pipe._collect_secondary_reference_works(ctx=ctx, official_title=None, primary_work=None,
        mentioned_works=[cand] if lane == 'mentioned' else [],
        comparison_target=cand if lane == 'comparison' else None,
        recommendation_candidates=[cand] if lane == 'recommendation' else [])


def saved_context(tmp_path, facts):
    p = facts['packet']
    return context(tmp_path, post=p['source_post'], comments=p['source_comments'],
        experts=facts['logged_experts'], search=facts['search_evidence_catalog'])


@pytest.mark.parametrize('lane', ['mentioned', 'comparison', 'recommendation'])
def test_saved24_real_role_consumer_rejects_target_without_erasing_saved_evidence(tmp_path, facts, lane):
    pipe, ctx = saved_context(tmp_path, facts)
    cand = DetectedTitle(**deepcopy(facts['stored_candidate']))
    before = canonical([ctx.post_data, ctx.comments, ctx.expert_outputs, ctx.search_results, cand.model_dump()])
    assert rejected_search_reference(pipe, ctx, cand) is True
    assert collect(pipe, ctx, cand, lane) == []
    assert canonical([ctx.post_data, ctx.comments, ctx.expert_outputs, ctx.search_results, cand.model_dump()]) == before
    assert facts['packet']['checkpoint_result']['analysis_result']['identity']['novel_identity'] == {'official_title': None, 'heretic_url': None}


def test_saved24_annotator_preserves_raw_candidate_but_not_rejected_mentioned_role(tmp_path, facts):
    pipe, ctx = saved_context(tmp_path, facts)
    cand = DetectedTitle(**deepcopy(facts['stored_candidate']))
    raw = canonical(ctx.expert_outputs)
    annotated, primary, mentioned, future = pipe._annotate_work_references(ctx=ctx,
        title_candidates=[cand], official_title=None,
        vf_result=ctx.get_expert_output(ExpertType.VERIFIER)['verification_result'])
    found = [x for x in annotated if x.official_title == cand.official_title]
    assert len(found) == 1 and found[0].reference_role == 'candidate'
    assert cand.official_title not in {x.official_title for x in mentioned}
    assert primary is None or primary.official_title != cand.official_title
    assert collect(pipe, ctx, cand) == [] and canonical(ctx.expert_outputs) == raw


def test_saved24_adjacent_primary_move_cannot_bypass_the_same_rejection(tmp_path, facts):
    pipe, ctx = saved_context(tmp_path, facts)
    cand = DetectedTitle(**deepcopy(facts['stored_candidate']))
    result = pipe._derive_primary_subject_interpretation(ctx=ctx, topicality='adjacent_relevant',
        subtype='genre_trope_discussion', discussion_type='trope_discussion', official_title=None,
        primary_work=cand, mentioned_works=[], comparison_target=None, recommendation_candidates=[],
        metadata={}, verification_result=ctx.get_expert_output(ExpertType.VERIFIER)['verification_result'])
    assert result['secondary_reference_works'] == []


@pytest.mark.parametrize('lane', ['mentioned', 'comparison', 'recommendation'])
@pytest.mark.parametrize('source_kind', ['body', 'comment'])
def test_explicit_source_work_survives_same_target_rejection_in_all_reference_lanes(tmp_path, lane, source_kind):
    text = f'소설 「{TITLE}」를 추천한다.'
    pipe, ctx = context(tmp_path, body=[text] if source_kind == 'body' else [],
        comments=[{'comment_id': 24, 'content': text}] if source_kind == 'comment' else [],
        experts=[{'expert': 'verifier', 'value': {'verification_result': verification()}}])
    cand = candidate()
    assert rejected_search_reference(pipe, ctx, cand) is False
    kept = collect(pipe, ctx, cand, lane)
    assert len(kept) == 1 and kept[0].official_title == TITLE


@pytest.mark.parametrize('title,text', [
    ('나는 오늘도 살아간다.', '소설 「나는 오늘도 살아간다.」를 읽지 않았다.'),
    ('주무시기 전에 무엇을 하셨나요?', '친구가 소설 「주무시기 전에 무엇을 하셨나요?」를 읽었다고 말했다.'),
    ('아카데미 생존 갤러리', '소설 「아카데미 생존 갤러리」와 다른 소설을 비교했다.'),
    (TITLE, f'“나는 소설 「{TITLE}」를 읽었다.”'),
])
def test_sentence_gallery_and_quoted_names_are_references_without_own_reading_claim(tmp_path, title, text):
    pipe, ctx = context(tmp_path, body=[text],
        experts=[{'expert': 'verifier', 'value': verification(title)}])
    cand = candidate(title)
    assert rejected_search_reference(pipe, ctx, cand) is False
    assert len(collect(pipe, ctx, cand)) == 1


@pytest.mark.parametrize('relation', ['valid', 'other_title', 'query_only', 'withdrawn'])
def test_alias_relation_must_belong_to_source_and_this_candidate(tmp_path, relation):
    alias = '은항탐'
    text = f'{TITLE}의 약칭은 {alias}이다.'
    if relation == 'other_title': text = f'푸른 별의 기록자의 약칭은 {alias}이다.'
    if relation == 'withdrawn': text += ' 그 명명은 철회한다.'
    row = {'url': 'https://example.org/novel-review/24', 'title': '서평', 'snippet': text}
    if relation == 'query_only': row = {'url': row['url'], 'title': '서평', 'query': text}
    pipe, ctx = context(tmp_path, body=[alias + ' 같은 소설 추천해줘'], search=[row],
        experts=[{'expert': 'verifier', 'value': verification()}])
    cand = candidate(alias_or_mention=alias)
    assert rejected_search_reference(pipe, ctx, cand) is (relation != 'valid')
    assert bool(collect(pipe, ctx, cand)) is (relation == 'valid')


@pytest.mark.parametrize('source_character,weak', [
    ('루미엘', False), ('다른인물', False), ('루미엘', True),
    ('루미엘은', False), ('루미엘라', False),
])
def test_character_work_link_needs_current_source_character_and_strong_binding(tmp_path, source_character, weak):
    pipe, ctx = context(tmp_path, body=[source_character + ' 이야기'],
        experts=[{'expert': 'verifier', 'value': verification()}])
    ctx.verified_character_work_links = [{'character': '루미엘', 'title': TITLE,
        'url': 'https://novelpia.com/novel/902424', '_weak_match': weak}]
    expected = source_character in {'루미엘', '루미엘은'} and not weak
    assert rejected_search_reference(pipe, ctx, candidate()) is (not expected)


@pytest.mark.parametrize('in_source', [False, True])
def test_official_search_existence_does_not_replace_source_url_relationship(tmp_path, in_source):
    url = 'https://novelpia.com/novel/902424'
    pipe, ctx = context(tmp_path, body=[url] if in_source else ['줄을 쓰는 전투가 좋다'],
        search=[{'url': url, 'title': TITLE, 'page_type': 'novel_detail', 'content_status': 'active', 'snippet': TITLE + ' 작품 상세'}],
        experts=[{'expert': 'verifier', 'value': verification()}])
    assert pipe._find_title_matched_official_url(TITLE, ctx.search_results) == url
    assert rejected_search_reference(pipe, ctx, candidate(heretic_url=url, source_tier='official_detail')) is (not in_source)


@pytest.mark.parametrize('fault', ['other_title', 'prefix_neighbor', 'major', 'downgrade', 'true_grounded', 'not_search_only', 'missing'])
def test_no_candidate_specific_critical_search_only_rejection_keeps_existing_behavior(tmp_path, fault):
    vf = verification()
    if fault == 'other_title': vf = verification('다른 작품')
    elif fault == 'prefix_neighbor': vf = verification(TITLE + '의 귀환')
    elif fault == 'major': vf['counter_arguments'][0]['severity'] = 'major'
    elif fault == 'downgrade': vf['counter_arguments'][0]['action'] = 'downgrade_confidence'
    elif fault == 'true_grounded': vf['grounding_check']['decoder_grounded'] = True
    elif fault == 'not_search_only': vf['grounding_check']['anchor_found'] = 'body_mention'
    else: vf = {}
    pipe, ctx = context(tmp_path, experts=[{'expert': 'verifier', 'value': vf}])
    cand = candidate()
    assert rejected_search_reference(pipe, ctx, cand) is False
    assert len(collect(pipe, ctx, cand)) == 1


@pytest.mark.parametrize('mutation', ['live_body', 'captured_body', 'live_comment'])
def test_source_mutation_cannot_reuse_independent_role_support(tmp_path, mutation):
    pipe, ctx = context(tmp_path, body=[f'소설 「{TITLE}」를 읽었다.'],
        comments=[{'comment_id': 24, 'content': '좋은 작품이다.'}],
        experts=[{'expert': 'verifier', 'value': verification()}])
    assert rejected_search_reference(pipe, ctx, candidate()) is False
    if mutation == 'live_body': ctx.post_data['content_blocks'][0]['text'] += ' 변경'
    elif mutation == 'captured_body': ctx._batch_alias_original_source['content_blocks'][0]['text'] += ' 변경'
    else: ctx.comments[0] += ' 변경'
    assert rejected_search_reference(pipe, ctx, candidate()) is True


def test_saved24_actual_alias_candidate_is_not_globally_removed(tmp_path, facts):
    pipe, ctx = saved_context(tmp_path, facts)
    actual = next(row for row in facts['packet']['checkpoint_result']['analysis_result']['identity']['candidate_preservation_sources']
                  if row.get('alias_or_mention') == '약먹마')
    cand = candidate(actual['official_title'], alias_or_mention=actual['alias_or_mention'], confidence='Medium')
    assert rejected_search_reference(pipe, ctx, cand) is False
    assert len(collect(pipe, ctx, cand)) == 1


@pytest.mark.parametrize('placement', ['body', 'comment'])
def test_candidate_specific_name_withdrawal_is_not_positive_reference(tmp_path, placement):
    text = f'소설 「{TITLE}」이라고 썼지만 그건 실제 작품명이 아니다.'
    pipe, ctx = context(tmp_path, body=[text] if placement == 'body' else [],
        comments=[{'comment_id': 24, 'content': text}] if placement == 'comment' else [],
        experts=[{'expert': 'verifier', 'value': verification()}])
    assert rejected_search_reference(pipe, ctx, candidate()) is True
    assert collect(pipe, ctx, candidate()) == []


def test_saved24_original_hold_publication_and_learning_contract_stays_unchanged(facts):
    from llm_batch.domain.batch_context import BatchContextMemory
    from llm_batch.ledger.publication_commit import (
        compute_publication_decision_commit, validate_publication_result_commit)
    from expert_main import _learn_batch_context_from_canonical_publication

    packet = facts['packet']
    result = deepcopy(packet['checkpoint_result'])
    before = canonical(result)
    receipt = compute_publication_decision_commit(result,
        publication_scope_id=packet['publication_scope_id'], attempt_run_id=packet['run_id'],
        input_index=24, post_id=packet['post_id'])
    validate_publication_result_commit(result, receipt,
        expected_scope_id=packet['publication_scope_id'], expected_input_index=24,
        expected_post_id=packet['post_id'])
    memory = BatchContextMemory(enabled=True)
    assert receipt.outcome == 'HOLD' and receipt.publish_allowed is False
    assert _learn_batch_context_from_canonical_publication(memory, result, receipt, created=True) is False
    assert memory.resolved_abbreviations == memory.resolved_authors == memory.resolved_characters == {}
    assert canonical(result) == before
    # 원형 저장 행의 공개/학습 계약 대조다. 새 파생 행의 full context/main/WAL 성공이 아니다.


@pytest.mark.parametrize('item_fields,rejected', [
    ({'issue': f"Decoder의 '{TITLE}' 매칭 오류"}, True),
    ({'issue': f"Decoder의 '{TITLE} 외전' 매칭 오류"}, False),
    ({'issue': f"Decoder의 '{TITLE} 개정판' 매칭 오류"}, False),
    ({'issue': f"Decoder의 '새로운 {TITLE}' 매칭 오류"}, False),
    ({'issue': f'Decoder의 {TITLE} 매칭 오류'}, False),
    ({'issue': f'Decoder의 {TITLE} 외전 매칭 오류'}, False),
    ({'explanation': f'Decoder가 "{TITLE}"로 연결했으나 원문 근거가 없다.'}, True),
    ({'explanation': f'Decoder가 "{TITLE} 외전"으로 연결했으나 원문 근거가 없다.'}, False),
    ({'candidate_title': TITLE, 'issue': '원문 관계 없는 검색 후보의 매칭 오류'}, True),
    ({'candidate_title': TITLE + ' 외전', 'issue': f"'{TITLE}'와 비교되는 작품의 오류"}, False),
    ({'candidate_title': TITLE, 'official_title': TITLE + ' 외전', 'issue': f"'{TITLE}' 매칭 오류"}, False),
    ({'issue': f'Decoder의 「{TITLE}」 매칭 오류'}, True),
])
def test_rejection_target_is_the_whole_named_work_not_a_spaced_title_prefix(tmp_path, item_fields, rejected):
    # 명시 합성 표제 경계다. 원형24/Verifier를 고치거나 실행 당시 자료로 부르지 않는다.
    vf = verification()
    vf['counter_arguments'] = [dict(severity='critical', action='reject', **item_fields)]
    pipe, ctx = context(tmp_path, experts=[{'expert': 'verifier', 'value': vf}])
    before = canonical([ctx.post_data, ctx.comments, ctx.expert_outputs])
    cand = candidate()
    assert rejected_search_reference(pipe, ctx, cand) is rejected
    kept = collect(pipe, ctx, cand)
    assert len(kept) == (0 if rejected else 1)
    if not rejected:
        assert kept[0].official_title == TITLE and kept[0].reference_role == 'mentioned'
    assert canonical([ctx.post_data, ctx.comments, ctx.expert_outputs]) == before
