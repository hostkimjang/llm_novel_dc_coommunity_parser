"""ROOT 격리 실행 전용. 19 전체 context 재현을 주장하지 않는 원문/로컬 producer 회귀."""
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

FIXTURE = Path(__file__).parent / 'fixtures/candidate19_saved_source_experts.json'
FIXTURE_SHA = '1fcbcda786dd20b0fafcc24942d5e66aed2b1b9751a952976ba8b32885385120'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


@pytest.fixture(scope='module')
def sut():
    names = ['llm_batch.agentic_pipeline', 'llm_batch.domain.models', 'llm_batch.experts.orchestrator',
             'llm_batch.grounding.decoder_title_role', 'llm_batch.domain.batch_context',
             'llm_batch.ledger.publication_commit', 'expert_main']
    return SimpleNamespace(**{name.rsplit('.', 1)[-1]: importlib.import_module(name) for name in names})


@pytest.fixture(scope='module')
def facts():
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == FIXTURE_SHA
    data = json.loads(raw)
    packet = data['current_full_packet']
    assert type(packet['post_id']) is int and packet['post_id'] == data['post_id']
    assert hashlib.sha256(canonical({'post': packet['source_post'], 'comments': packet['source_comments']})).hexdigest() == data['source_canonical_sha256']
    assert hashlib.sha256(canonical(packet['checkpoint_result'])).hexdigest() == data['result_canonical_sha256']
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
            raise ExternalAttempt('CANDIDATE19_NEW_EXTERNAL_ATTEMPT:' + name)
        return denied


def context(sut, tmp_path, *, post=None, comments=(), experts=None, title='', body=()):
    raw = deepcopy(post) if post else {'post_id': 903019, 'title': title,
        'content_blocks': [{'type': 'text', 'text': text} for text in body]}
    model = sut.models.PostInput(**raw, comments=deepcopy(comments))
    external = NoExternal()
    pipe = sut.agentic_pipeline.AgenticPipeline(llm=external, mcp=external, output_dir=tmp_path,
        max_iterations=1, native_recovery=True, parallel_count=12, worker_id=0)
    pipe.enable_url_fetch_disk_cache = False
    pipe._use_session_knowledge = False
    ctx = sut.orchestrator.ConversationContext(post_id=model.post_id, post_data=pipe._post_to_dict(model),
                                              comments=pipe._extract_comments(model))
    ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(model)
    ctx._final_source_original_comment_refs = tuple(model.comments)
    for name, payload in (experts or {}).items():
        ctx.set_expert_output(sut.orchestrator.ExpertType(name), deepcopy(payload))
    return pipe, ctx, external


def self_term(title, role='general_noun'):
    return {'original': title, 'best_match': {'title': title, 'confidence': 'high'},
        'interpretations': [{'type': role, 'value': title if role == 'novel_title' else '작성자 문장 해석'}],
        'grounding': {'is_grounded': True, 'anchor_type': 'title_mention'},
        'candidates': [{'official_novel_title': title, 'morphological_score': 0.9}]}


def correction(alias, title, interpreted='다른 작품의 정식 이름'):
    return {'original': alias, 'best_match': {'title': None, 'confidence': 'none'},
        'interpretations': [{'type': 'novel_title', 'value': interpreted}],
        'candidates': [{'official_novel_title': title, 'morphological_score': 0.99}],
        '_alias_bridge_pending': True}


def seed(sut, ctx, term):
    ctx.set_expert_output(sut.orchestrator.ExpertType.DECODER,
                         {'decoded_terms': [deepcopy(term)], 'needs_verification': False})


@pytest.fixture(scope='module')
def current_local(sut, facts, tmp_path_factory):
    tmp = tmp_path_factory.mktemp('candidate19_role_local')
    p = facts['current_full_packet']
    pipe, ctx, external = context(sut, tmp, post=p['source_post'], comments=p['source_comments'], experts=facts['experts'])
    before = canonical([ctx.post_data, ctx.comments, ctx.expert_outputs])
    own = pipe._pick_decoder_exact_post_title_surface(ctx)
    fd = facts['experts']['arbiter']['final_decision']
    vf = ctx.get_expert_output(sut.orchestrator.ExpertType.VERIFIER)
    candidates = pipe._build_title_candidates(ctx=ctx, is_relevant=fd['is_relevant'],
        official_title=fd['official_novel_title'], heretic_url=fd['heretic_url'], confidence=fd['confidence'], vf_result=vf)
    annotated, primary, mentioned, comparison = pipe._annotate_work_references(ctx=ctx,
        title_candidates=candidates, official_title=fd['official_novel_title'], vf_result=vf)
    secondary = pipe._collect_secondary_reference_works(ctx=ctx, official_title=fd['official_novel_title'],
        primary_work=primary, mentioned_works=mentioned, comparison_target=comparison, recommendation_candidates=[])
    assert canonical([ctx.post_data, ctx.comments, ctx.expert_outputs]) == before
    assert external.attempts == []
    observations = [row for row in getattr(ctx, '_title_meta_explanation_observations', ())
                    if row.get('source') == 'decoder_role_contract']
    report = {'scope': 'SAVED_SOURCE_LOCAL_PRODUCERS_NOT_FULL_CONTEXT_REPLAY', 'self_match': own,
        'source_canonical_sha256': facts['source_canonical_sha256'],
        'original_result_canonical_sha256': facts['result_canonical_sha256'],
        'observations': observations,
        **{name: [v.model_dump(mode='json') for v in values] for name, values in (
            ('candidates', candidates), ('annotated', annotated), ('mentioned', mentioned), ('secondary', secondary))}}
    (tmp / 'candidate19_role_observation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    return report


def test_current19_local_producers_reject_both_unqualified_work_roles_without_erasing_existing_primary_candidate(current_local, facts):
    report = current_local
    whole = facts['current_full_packet']['source_post']['title']
    wrong = facts['experts']['decoder']['decoded_terms'][0]['candidates'][0]['official_novel_title']
    existing = facts['experts']['arbiter']['final_decision']['official_novel_title']
    assert report['self_match'] is None
    assert existing in {row['official_title'] for row in report['candidates']}
    for stage in ['candidates', 'annotated', 'mentioned', 'secondary']:
        assert not {whole, wrong}.intersection(row['official_title'] for row in report[stage]), stage


def test_current19_raw_terms_remain_exact_non_authoritative_observations(current_local, facts):
    observations = current_local['observations']
    for index, term in enumerate(facts['experts']['decoder']['decoded_terms']):
        matches = [row for row in observations if row['term_index'] == index]
        assert matches and all(json.loads(row['raw_decoder_term_json']) == term for row in matches)
        assert all(hashlib.sha256(row['raw_decoder_term_json'].encode()).hexdigest()
                   == row['raw_decoder_term_sha256'] for row in matches)
        assert all(row['typed_work_role_allowed'] is False and row['publication_authority'] is False
                   and row['supports_publish'] is False for row in matches)


def test_original19_hold_commit_and_memory_boundary_remain_untouched(sut, facts):
    packet = facts['current_full_packet']; row = deepcopy(packet['checkpoint_result']); before = canonical(row)
    receipt = sut.publication_commit.PublicationDecisionCommit.from_dict(packet['publication_commit'])
    sut.publication_commit.validate_publication_result_commit(row, receipt,
        expected_scope_id=packet['publication_scope_id'], expected_input_index=19, expected_post_id=packet['post_id'])
    memory = sut.batch_context.BatchContextMemory(enabled=True)
    assert receipt.outcome == 'HOLD' and receipt.publish_allowed is False
    assert sut.expert_main._learn_batch_context_from_canonical_publication(memory, row, receipt, created=True) is False
    assert memory.resolved_abbreviations == memory.resolved_authors == memory.resolved_characters == {}
    assert canonical(row) == before


@pytest.mark.parametrize('surface', ['그 작품이 벌써 1위가 되었네', '나는 오늘도 살아간다.', '주무시기 전에 무엇을 하셨나요?'])
def test_nonwork_self_match_is_not_individual_title_verification(sut, tmp_path, surface):
    pipe, ctx, external = context(sut, tmp_path, title=surface)
    seed(sut, ctx, self_term(surface))
    before = canonical(ctx.expert_outputs)
    assert pipe._pick_decoder_exact_post_title_surface(ctx) is None
    assert pipe._decoder_title_role_rejected(ctx, surface) is True
    assert canonical(ctx.expert_outputs) == before and not external.attempts


@pytest.mark.parametrize('surface', ['나는 오늘도 살아간다.', '주무시기 전에 무엇을 하셨나요?', '아카데미 생존 갤러리'])
def test_same_sentence_or_gallery_surface_with_exact_official_evidence_is_preserved(sut, tmp_path, surface):
    pipe, ctx, external = context(sut, tmp_path, title=surface)
    seed(sut, ctx, self_term(surface))
    ctx.search_results = [{'url': 'https://novelpia.com/novel/934350', 'title': surface, 'snippet': '작품 상세'}]
    assert pipe._decoder_title_role_rejected(ctx, surface) is False
    assert pipe._pick_decoder_exact_post_title_surface(ctx) == surface
    assert not external.attempts


@pytest.mark.parametrize('body', ['나는 소설 「나는 오늘도 살아간다.」를 읽었다.',
    '소설 「나는 오늘도 살아간다.」를 읽지 않았다.', '소설 「나는 오늘도 살아간다.」를 읽었나?',
    '소설 「나는 오늘도 살아간다.」를 읽을 예정이다.'])
def test_existing_source_name_grammar_preserves_name_without_claiming_reading(sut, tmp_path, body):
    title = '나는 오늘도 살아간다.'
    pipe, ctx, external = context(sut, tmp_path, title='표제 확인', body=[body])
    seed(sut, ctx, self_term(title))
    assert pipe._decoder_title_role_rejected(ctx, title) is False
    assert not external.attempts


@pytest.mark.parametrize('body', ['친구가 소설 「나는 오늘도 살아간다.」를 읽었다고 말했다.',
    '“소설 「나는 오늘도 살아간다.」를 읽었다.”', '만약 소설 「나는 오늘도 살아간다.」를 읽었다면',
    '나는 오늘도 살아간다.라는 문장일 뿐 작품명이 아니다.'])
def test_report_quote_hypothesis_or_explanation_does_not_supply_missing_work_role(sut, tmp_path, body):
    title = '나는 오늘도 살아간다.'
    pipe, ctx, external = context(sut, tmp_path, title='문장 해석', body=[body])
    seed(sut, ctx, self_term(title))
    assert pipe._decoder_title_role_rejected(ctx, title) is True
    assert not external.attempts


@pytest.mark.parametrize('mode', ['valid', 'negated', 'wrong_title', 'generated', 'split_fields'])
def test_external_explicit_new_alias_relation_preserves_work_without_unbound_correction(sut, tmp_path, mode):
    # 등록 사전의 실제 여부에 기대지 않는 외부 새 alias 대조다.
    alias, title = '쌍달길', '달이 두 번 뜨는 항로'
    pipe, ctx, external = context(sut, tmp_path, title='별칭으로 읽은 작품', body=[f'소설 {alias}을 읽었다.'])
    seed(sut, ctx, correction(alias, title))
    statement = f'웹소설 {title}의 약칭은 {alias}이다.'
    row = {'url': 'https://gall.dcinside.com/mgallery/board/view/?id=genrenovel&no=999900', 'content': statement}
    if mode == 'negated': row['content'] = statement.replace('이다.', '이 아니다.')
    if mode == 'wrong_title': row['content'] = statement.replace(title, '다른 항로의 기록')
    if mode == 'generated': row['generated'] = True
    if mode == 'split_fields': row.update(title=title, content=f'약칭은 {alias}이다.')
    ctx.search_results = [row]
    assert pipe._decoder_title_role_rejected(ctx, title) is (mode != 'valid')
    assert not external.attempts


@pytest.mark.parametrize('title,alias', [('아카데미 생존 갤러리', '아생갤'), ('달이 두 번 뜨는 날', '쌍달')])
def test_consistent_specific_work_decoder_candidate_keeps_existing_recall(sut, tmp_path, title, alias):
    pipe, ctx, external = context(sut, tmp_path, title=f'{alias} 읽었다')
    term = correction(alias, title, interpreted=title)
    term['best_match'] = {'title': title, 'confidence': 'medium'}
    seed(sut, ctx, term)
    before = canonical(ctx.expert_outputs)
    assert pipe._decoder_title_role_rejected(ctx, title) is False
    candidates = pipe._build_title_candidates(ctx=ctx, is_relevant=True, official_title=None,
        heretic_url=None, confidence='Low', vf_result={})
    assert title in {row.official_title for row in candidates}
    assert canonical(ctx.expert_outputs) == before and not external.attempts


@pytest.mark.parametrize('score', [0, 0.5, 0.9, 1.0])
def test_morphological_score_cannot_select_null_best_unrelated_work(sut, tmp_path, score):
    pipe, ctx, external = context(sut, tmp_path, title='쌍달 읽었다')
    term = correction('쌍달', '관련 없는 교정 후보')
    term['candidates'][0]['morphological_score'] = score
    seed(sut, ctx, term)
    assert pipe._decoder_title_role_rejected(ctx, '관련 없는 교정 후보') is True
    candidate = sut.models.DetectedTitle(official_title='관련 없는 교정 후보', confidence='High', alias_or_mention='쌍달')
    assert pipe._collect_secondary_reference_works(ctx=ctx, official_title=None, primary_work=None,
        mentioned_works=[candidate], comparison_target=None, recommendation_candidates=[]) == []
    assert not external.attempts


def test_official_existence_for_a_different_surface_does_not_create_missing_alias_relation(sut, tmp_path):
    title = '관련 없는 교정 후보'
    pipe, ctx, external = context(sut, tmp_path, title='쌍달 읽었다')
    seed(sut, ctx, correction('쌍달', title))
    ctx.search_results = [{'url': 'https://novelpia.com/novel/934350', 'title': title, 'snippet': '작품 상세'}]
    assert pipe._decoder_title_role_rejected(ctx, title) is True
    assert not external.attempts


def test_matching_work_interpretation_with_unselected_best_remains_existing_provisional_path(sut, tmp_path):
    title = '달이 두 번 뜨는 항로'
    pipe, ctx, external = context(sut, tmp_path, title='쌍달길 읽었다')
    term = correction('쌍달길', title, interpreted=title)
    seed(sut, ctx, term)
    # 모든 null-best 후보를 삭제하는 정책이 아니다. 같은 후보의 작품 해석은 기존 경로에 남긴다.
    assert pipe._decoder_title_role_rejected(ctx, title) is False
    assert not external.attempts


@pytest.mark.parametrize('role', ['slang', 'community', 'genre'])
def test_ambiguous_gallery_alias_role_is_not_blanket_nonwork(sut, tmp_path, role):
    pipe, ctx, external = context(sut, tmp_path, title='아생갤 읽었다')
    seed(sut, ctx, self_term('아생갤', role=role))
    # 이 enum만으로 이번 문장 모순에 편입하지 않는다. 기존 별칭/작품 guard는 별도로 남는다.
    assert pipe._decoder_title_role_rejected(ctx, '아생갤') is False
    assert not external.attempts
