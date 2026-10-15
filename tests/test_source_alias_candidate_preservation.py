"""명시 별칭의 후보 보존 기능. 저장 13은 부분 자료이며 전체 런 재생이 아니다."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.alias_learning import capture_alias_source, eligible_alias_confidence
from llm_batch.domain.models import PostInput
from llm_batch.experts.decoder import DecoderExpert, abbreviation_match_score
from llm_batch.experts.orchestrator import ConversationContext, ExpertType
from llm_batch.grounding.candidate_alias_relation import candidate_alias_relation
from llm_batch.grounding.anticipation_search_probe import source_bound_alias_assertion


FIXTURE = Path(__file__).parent / 'fixtures/alias_candidate13_saved_evidence.json'
TITLE, ALIAS = '은빛 항로의 탐험가', '은항탐'
URL = 'https://example.org/reviews/one'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def context(text=None, *, title=TITLE, alias=ALIAS, **row_fields):
    post = {'post_id': 130013, 'title': alias + ' 결말 이야기', 'content_blocks': []}
    row = {'url': URL, 'title': '서평', 'snippet': text or f'{title}, 줄여서 {alias}이 완결났다.'}
    row.update(row_fields)
    return SimpleNamespace(post_id=post['post_id'], post_data=post, search_results=[row],
        _batch_alias_original_source=capture_alias_source(post))


def saved():
    fixture = json.loads(FIXTURE.read_bytes())
    assert fixture['scope'] == 'SAVED_SOURCE_RESULT_AND_E007_ONLY_NOT_ORIGINAL_PRIVATE_CONTEXT'
    packet = fixture['packet']
    assert type(packet['post_id']) is int
    assert digest({'post': packet['source_post'], 'comments': packet['source_comments']}) == packet['source_canonical_sha256']
    assert digest(packet['checkpoint_result']) == packet['result_canonical_sha256']
    return fixture, packet


def test_saved13_exact_relation_recovered_without_lending_it_to_other_title():
    fixture, packet = saved()
    post = deepcopy(packet['source_post'])
    ctx = SimpleNamespace(post_id=packet['post_id'], post_data=post,
        search_results=[deepcopy(fixture['e007'])], _batch_alias_original_source=capture_alias_source(post))
    before = deepcopy(vars(ctx))
    actual_title, actual_alias = '마법 좋아좋아좋아', '마좋좋좋'
    witness = candidate_alias_relation(ctx, actual_title, actual_alias)
    assert witness and witness['field'] == 'snippet'
    assert witness['relation_kind'] == 'same_field_explicit_declaration'
    raw = fixture['e007']['snippet']
    assert raw[slice(*witness['title_span'])] == actual_title
    assert raw[slice(*witness['alias_span'])] == actual_alias
    assert witness['publication_authority'] is witness['learning_authority'] is False
    assert candidate_alias_relation(ctx, '마법 좋아, 마법과 좋아', actual_alias) is None
    # Arca 후보 근거를 기존 Namu 학습 proof로 승격하지 않는다.
    assert source_bound_alias_assertion(actual_title, [actual_alias], ctx.search_results,
        source_text=post['title']) is None
    original = packet['checkpoint_result']['analysis_result']['identity']
    assert original['novel_identity'] == {'official_title': None, 'heretic_url': None}
    assert actual_title not in {x['official_title'] for x in original['title_candidates']}
    assert vars(ctx) == before


@pytest.mark.parametrize('title,alias,text', [
    (TITLE, ALIAS, f'{TITLE}, 줄여서 {ALIAS}이 완결났다.'),
    (TITLE, ALIAS, f'{TITLE}의 약칭은 {ALIAS}이다.'),
    (TITLE, ALIAS, f'{ALIAS}는 {TITLE}의 약칭으로 쓰인다.'),
    (TITLE, ALIAS, f'소설 「{TITLE}」의 별칭은 「{ALIAS}」이다.'),
    ('반짝 반짝 반짝', '반반반', '반짝 반짝 반짝, 줄여서 반반반이 완결됐다.'),
    ('내가 내일도 살아갈까?', '내내살', '소설 「내가 내일도 살아갈까?」의 약칭은 내내살이다.'),
    ('이것은 소설이 아니다', '이소아', '「이것은 소설이 아니다」를 줄여서 이소아라고 부른다.'),
    (TITLE, ALIAS, f'{TITLE}의 약칭은 {ALIAS}이다. 나는 아직 읽지 않았다.'),
    (TITLE, ALIAS, f'{TITLE}, 줄여서 {ALIAS}이 완결났지만 결말이 잘못됐다.'),
])
def test_literal_naming_keeps_repetition_sentence_titles_and_reading_negation(title, alias, text):
    ctx = context(text, title=title, alias=alias)
    witness = candidate_alias_relation(ctx, title, alias)
    assert witness and witness['title'] == title and witness['alias'] == alias
    assert witness['publication_authority'] is witness['learning_authority'] is False


@pytest.mark.parametrize('text', [
    f'{TITLE}의 약칭은 {ALIAS}가 아니다.',
    f'{TITLE}의 약칭은 {ALIAS}라는 말은 잘못이다.',
    f'{TITLE}, 줄여서 {ALIAS}라고 불렀지만 그 명명을 철회한다.',
    f'{TITLE}의 약칭은 {ALIAS}이다. 그 약칭은 취소한다.',
    f'{TITLE}의 약칭은 {ALIAS}이다. {ALIAS}는 잘못된 약칭이다.',
    f'"{TITLE}, 줄여서 {ALIAS}이다."라고 친구가 말했다.',
    f'친구는 {TITLE}의 약칭은 {ALIAS}이라고 말했다.',
    f'만약 {TITLE}의 약칭은 {ALIAS}이라고 가정하면 어떨까.',
    f'{TITLE}의 약칭은 {ALIAS}인가?',
    f'웹툰 「{TITLE}」의 약칭은 {ALIAS}이다.',
])
def test_unasserted_or_non_novel_relation_does_not_protect_candidate(text):
    assert candidate_alias_relation(context(text), TITLE, ALIAS) is None


@pytest.mark.parametrize('variant', ['cross_field', 'cross_row', 'query_only', 'alias_absent', 'other_title', 'ocr', 'webtoon', 'invalid_url'])
def test_both_relation_members_must_belong_to_same_usable_field(variant):
    ctx = context()
    if variant == 'cross_field':
        ctx.search_results = [{'url': URL, 'title': TITLE, 'snippet': f'약칭은 {ALIAS}이다.'}]
    elif variant == 'cross_row':
        ctx.search_results = [{'url': URL, 'title': TITLE}, {'url': URL + '/2', 'snippet': f'약칭은 {ALIAS}이다.'}]
    elif variant == 'query_only':
        ctx.search_results = [{'url': URL, 'query': f'{TITLE}의 약칭은 {ALIAS}이다.', 'snippet': '검색 결과 없음'}]
    elif variant == 'alias_absent':
        ctx.post_data['title'] = '다른 이야기'
        ctx._batch_alias_original_source = capture_alias_source(ctx.post_data)
    elif variant == 'other_title':
        ctx.search_results[0]['snippet'] = f'다른 세계의 항해의 약칭은 {ALIAS}이다.'
    elif variant == 'ocr':
        ctx.search_results[0]['_ocr_diagnostic_only'] = True
    elif variant == 'webtoon':
        ctx.search_results[0]['media_type'] = 'webtoon'
    else:
        ctx.search_results[0]['url'] = 'javascript:alert(1)'
    assert candidate_alias_relation(ctx, TITLE, ALIAS) is None


@pytest.mark.parametrize('change', ['post_id', 'post_text', 'capture_text', 'row_text', 'row_url', 'field_move'])
def test_recompute_binds_current_source_and_external_row_without_cached_success(change):
    ctx = context()
    before = candidate_alias_relation(ctx, TITLE, ALIAS)
    assert before
    if change == 'post_id': ctx.post_id += 1
    elif change == 'post_text': ctx.post_data['title'] += ' 원문 변경'
    elif change == 'capture_text': ctx._batch_alias_original_source['title'] += ' 변조'
    elif change == 'row_text': ctx.search_results[0]['snippet'] = f'{TITLE}의 약칭은 {ALIAS}가 아니다.'
    elif change == 'row_url': ctx.search_results[0]['url'] = URL + '/other'
    else: ctx.search_results[0]['content'] = ctx.search_results[0].pop('snippet')
    after = candidate_alias_relation(ctx, TITLE, ALIAS)
    if change in {'row_url', 'field_move'}:
        assert after and after != before and after['row_relation_fields_sha256'] != before['row_relation_fields_sha256']
        assert after['publication_authority'] is after['learning_authority'] is False
    else:
        assert after is None


def test_competing_same_alias_and_same_name_media_do_not_select_official_identity():
    ctx = context()
    other = '은빛 항로의 귀환자'
    ctx.search_results += [
        {'url': URL + '/2', 'snippet': f'{other}의 약칭은 {ALIAS}이다.'},
        {'url': 'https://comic.naver.com/webtoon/list?titleId=123', 'media_type': 'webtoon',
         'snippet': f'{TITLE}의 약칭은 {ALIAS}이다.'},
    ]
    a, b = [candidate_alias_relation(ctx, title, ALIAS) for title in (TITLE, other)]
    assert a and b and a['row_index'] == 0 and b['row_index'] == 1
    assert all(w['publication_authority'] is w['learning_authority'] is False for w in (a, b))
    assert candidate_alias_relation(ctx, TITLE, ALIAS, rows=ctx.search_results[2:]) is None


def test_candidate_witness_is_not_an_alias_learning_proof():
    ctx = context()
    witness = candidate_alias_relation(ctx, TITLE, ALIAS)
    term = {'original': ALIAS, 'source_role': 'work_alias', 'best_match': {'title': TITLE, 'confidence': 'high'},
            'learning_evidence': witness}
    assert eligible_alias_confidence(ctx.post_data, term, TITLE, registries={}) == 0


def test_existing_exact_wiki_document_contract_is_reused_without_broadening_it():
    ctx = context()
    ctx.search_results = [{'url': 'https://namu.wiki/w/' + TITLE, 'title': TITLE,
                           'content': f'한국의 웹소설이다. 약칭은 {ALIAS}이다.'}]
    strict = source_bound_alias_assertion(TITLE, [ALIAS], ctx.search_results, source_text=ctx.post_data['title'])
    assert strict
    witness = candidate_alias_relation(ctx, TITLE, ALIAS)
    assert witness and witness['strict_document_assertion'] == strict
    assert witness['learning_authority'] is False


class NoExternal:
    def __getattr__(self, name):
        def forbidden(*args, **kwargs):
            raise AssertionError('NO_NEW_MODEL_SEARCH_FETCH:' + name)
        return forbidden


def pipeline_context(tmp_path, post, rows):
    model = PostInput(**post, comments=[])
    pipe = AgenticPipeline(llm=NoExternal(), mcp=NoExternal(), output_dir=tmp_path,
                          max_iterations=1, native_recovery=True)
    pipe.enable_heretic_live_fetch = False
    pipe.enable_url_fetch_disk_cache = False
    pipe._use_session_knowledge = False
    ctx = ConversationContext(post_id=model.post_id, post_data=pipe._post_to_dict(model), comments=[])
    ctx._batch_alias_original_source = capture_alias_source(model)
    ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(model)
    ctx.search_results = deepcopy(rows)
    return pipe, ctx


@pytest.mark.parametrize('method', ['_validate_morpheme_in_title', '_guard_no_body_evidence'])
@pytest.mark.parametrize('exact', [True, False])
def test_actual_decoder_guards_do_not_borrow_saved13_declaration(tmp_path, capsys, method, exact):
    fixture, packet = saved()
    _, ctx = pipeline_context(tmp_path, deepcopy(packet['source_post']), [fixture['e007']])
    title = '마법 좋아좋아좋아' if exact else '마법 좋아, 마법과 좋아'
    raw = {'decoded_terms': [{'original': '마좋좋좋', 'morphemes': ['완결'],
           'best_match': {'title': title, 'confidence': 'high'}, 'candidates': [], 'interpretations': []}]}
    decoder = DecoderExpert(NoExternal())
    if method == '_guard_no_body_evidence':
        result = decoder._guard_no_body_evidence(deepcopy(raw), {}, ctx)
        marker = '검색 결과에 명시적 약칭 증거 있음'
    else:
        result = decoder._validate_morpheme_in_title(deepcopy(raw), ctx)
        marker = '명시적 약칭 증거 발견'
    output = capsys.readouterr().err
    if exact:
        if method == '_validate_morpheme_in_title':
            # 저장 원문/E007은 그대로다. 반복음절 약칭은 실제 점수의 정상 조기 보호를 탄다.
            score = abbreviation_match_score('마좋좋좋', title)
            assert score >= 0.8
            assert f'score={score:.2f}, morpheme_ok=True' in output
            assert marker not in output
        else:
            assert marker in output
        assert result['decoded_terms'][0]['best_match']['title'] == title
        assert result['decoded_terms'][0]['best_match']['confidence'].lower() == 'high'
        assert not result['decoded_terms'][0]['best_match'].get('url')
    else:
        assert marker not in output
    # 정확한 과거 Decoder payload를 복원했다는 주장이 아니라 실제 두 guard의 기능 대조다.
    assert ctx.search_results == [fixture['e007']]


@pytest.mark.parametrize('method', ['_validate_morpheme_in_title', '_guard_no_body_evidence'])
@pytest.mark.parametrize('exact', [True, False])
def test_irregular_alias_reaches_actual_decoder_relation_branch(tmp_path, capsys, method, exact):
    # 저장 13과 구분한 합성 불규칙 별칭: 실제 점수/형태소 불일치 뒤 명명 관계를 판독한다.
    alias = '달콩별'
    declared_title = TITLE if exact else '푸른 별의 기록자'
    post = {'post_id': 130114, 'title': alias + ' 결말 이야기', 'content_blocks': []}
    rows = [{'url': URL, 'title': '서평',
             'snippet': f'{declared_title}의 약칭은 {alias}이다.'}]
    _, ctx = pipeline_context(tmp_path, post, rows)
    raw = {'decoded_terms': [{'original': alias, 'morphemes': ['완결', '후기'],
        'best_match': {'title': TITLE, 'confidence': 'high'}, 'candidates': [], 'interpretations': []}]}
    raw_before, source_before = deepcopy(raw), (deepcopy(ctx.post_data), deepcopy(ctx.search_results))
    assert abbreviation_match_score(alias, TITLE) < 0.5
    assert all(part not in TITLE.replace(' ', '') for part in raw['decoded_terms'][0]['morphemes'])
    decoder = DecoderExpert(NoExternal())
    if method == '_guard_no_body_evidence':
        result = decoder._guard_no_body_evidence(deepcopy(raw), {}, ctx)
        marker = '검색 결과에 명시적 약칭 증거 있음'
    else:
        result = decoder._validate_morpheme_in_title(deepcopy(raw), ctx)
        marker = '명시적 약칭 증거 발견'
    output = capsys.readouterr().err
    assert (marker in output) is exact
    if method == '_validate_morpheme_in_title':
        assert 'morpheme_ok=False' in output
    if exact:
        best = result['decoded_terms'][0]['best_match']
        assert best['title'] == TITLE and best['confidence'].lower() == 'high'
        assert not best.get('url')
    assert raw == raw_before and (ctx.post_data, ctx.search_results) == source_before


@pytest.mark.parametrize('declared', [True, False])
def test_real_ranked_inventory_preserves_declared_loser_without_score_or_authority_promotion(tmp_path, capsys, declared):
    # 명시 합성 context: 실제 점수/수집/typed 후보를 사용하고 함수 성공값을 주입하지 않는다.
    # 2음절 은항은 generic seed여서 alias가 전달되지 않았다. 양쪽의 실제 3음절 약칭을 쓴다.
    low_title, high_title, alias = '은하 항해의 기록', '은빛 항로의 기사', '은항기'
    post = {'post_id': 130099, 'title': alias + ' 이야기',
        'content_blocks': [{'type': 'text', 'text': f'소설 「{low_title}」와 소설 「{high_title}」를 읽었다.'}]}
    relation = f'{low_title}의 약칭은 {alias}이다.' if declared else f'{low_title}의 약칭은 {alias}가 아니다.'
    rows = [{'url': URL, 'title': '서평', 'snippet': relation},
        {'url': 'https://novelpia.com/novel/130099', 'title': high_title,
         'snippet': high_title + ' 작품 상세', 'page_type': 'novel_detail', 'content_status': 'active'}]
    pipe, ctx = pipeline_context(tmp_path, post, rows)
    ctx.set_expert_output(ExpertType.DECODER, {'decoded_terms': [
        {'original': alias, 'best_match': {'title': high_title, 'confidence': 'high'}, 'candidates': []},
        {'original': alias, 'best_match': {'title': low_title, 'confidence': 'low'}, 'candidates': []}]})
    before = deepcopy(ctx.get_expert_output(ExpertType.DECODER))
    for term in before['decoded_terms']:
        title = term['best_match']['title']
        assert not pipe._is_generic_alias_seed(alias, full_title=title)
        assert abbreviation_match_score(alias, title) >= 0.55
        assert pipe._decoder_term_title_bridge_score(term, title) >= 0.55
    assert (candidate_alias_relation(ctx, low_title, alias) is not None) is declared
    best = pipe._select_best_canonical_rescue_candidate(ctx=ctx, vf_result={}, seed_titles=[low_title, high_title])
    low = pipe._canonical_work_rescue_strength(ctx=ctx, title=low_title, vf_result={})
    assert best['title'] == high_title and best['rescue']['strong']
    assert best['score'] >= low['score'] + 2 or (best['rescue']['official_ev'] and not low['official_ev'])
    titles, snapshot = pipe._build_title_candidates_with_snapshot(ctx=ctx, is_relevant=True,
        official_title=None, heretic_url=None, confidence='Low', vf_result={})
    by_title = {x.official_title: x for x in titles}
    output = capsys.readouterr().err
    if declared:
        assert low_title in by_title and '명시 별칭 후보 보존' in output
        value = by_title[low_title]
        assert value.confidence == 'Low' and value.heretic_url is None and value.locked is False
        assert value.reference_role == 'candidate'
        assert value.alias_or_mention == alias
    else:
        assert low_title not in by_title and 'alias 충돌 후보 정리' in output
    assert high_title in by_title
    assert ctx.get_expert_output(ExpertType.DECODER) == before
    assert snapshot.status != 'COMPLETE'
