"""72의 저장 근거와 명시 합성 context로 URL 소유권 경계를 확인한다. 전체 런 재생이 아니다."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import subprocess

import pytest

import llm_batch.agentic_pipeline as pipeline_module
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.experts.orchestrator import ConversationContext


FIXTURE = Path(__file__).parent / 'fixtures/current72_url_ownership.json'
TITLE = '은빛 항로의 탐험가'
URL = 'https://novelpia.com/novel/812345'


class ExternalCallForbidden(BaseException):
    pass


def forbidden(*args, **kwargs):
    raise ExternalCallForbidden('외부 호출은 이 국소 시험의 입력이 아니다.')


class NoExternal:
    def __getattr__(self, name):
        return forbidden


def canonical(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(subprocess, 'run', forbidden)
    monkeypatch.setattr(AgenticPipeline, '_fetch_and_attach_page_info', forbidden)


def make_context(tmp_path, *, source_title=TITLE, selected=TITLE, status='unavailable',
                 fetched_title='403 Forbidden', rows=None, post=None):
    # source/result 및 E001은 별도 fixture에서 검산한다. 이 fetched entry는 명시 합성 입력이다.
    pipeline = AgenticPipeline(llm=NoExternal(), mcp=NoExternal(), output_dir=tmp_path,
        max_iterations=1, native_recovery=True)
    pipeline.enable_heretic_live_fetch = False
    pipeline.enable_url_fetch_disk_cache = False
    pipeline._use_session_knowledge = False
    assert Path(pipeline_module.__file__).resolve() == (
        Path(__file__).resolve().parents[1] / 'src/llm_batch/agentic_pipeline.py').resolve()
    source = deepcopy(post or {'post_id': 720072, 'title': '연재 소식을 기다린다', 'content_blocks': []})
    ctx = ConversationContext(post_id=source['post_id'], post_data=source, comments=[])
    ctx.search_results = deepcopy(rows if rows is not None else [
        {'title': source_title, 'url': URL, 'content': '공식 작품 소개', 'rank': 1}])
    ctx.fetched_page_info = [{'url': URL, 'structured_info': {'title': fetched_title,
        'page_title': fetched_title, 'page_type': 'novel_page', 'content_status': status},
        'text_preview': fetched_title}]
    return pipeline, ctx


def evaluate(pipeline, ctx, title, url=URL):
    before = deepcopy((ctx.post_data, ctx.comments, ctx.search_results, ctx.fetched_page_info))
    result = pipeline._evaluate_heretic_url_candidate(url, ctx=ctx,
        search_results=ctx.search_results, identified_title=title, identified_author=None)
    assert (ctx.post_data, ctx.comments, ctx.search_results, ctx.fetched_page_info) == before
    return result


@pytest.mark.parametrize('selected_is_if', [False, True])
def test_current72_saved_e001_through_real_url_functions(tmp_path, selected_is_if):
    raw_fixture = FIXTURE.read_bytes()
    assert hashlib.sha256(raw_fixture).hexdigest() == 'b40c0fe034a2aaa33af3f683a4c7aca8f6dd83d67047b2c3f7b4c5fb2a7c3696'
    fixture = json.loads(raw_fixture)
    assert fixture['scope'] == 'SAVED_PACKET_AND_E001_WITH_EXPLICIT_SYNTHETIC_403_CONTEXT'
    packet = fixture['packet']
    assert packet['source_canonical_sha256'] == '0fbc7fd27c1ce744670c4ce116817a5796a3bba4756c8d01b45df03980d21fd1'
    assert packet['result_canonical_sha256'] == '188dbf6c6d37172137a89706b4ad0c5b955489c7abab61851d35314e995d78cd'
    assert type(packet['post_id']) is int and packet['index1'] == 72
    assert canonical({'post': packet['source_post'], 'comments': packet['source_comments']}) == packet['source_canonical_sha256']
    assert canonical(packet['checkpoint_result']) == packet['result_canonical_sha256']
    e001 = fixture['e001']
    assert e001 == packet['checkpoint_result']['analysis_result']['identity']['search_evidence_catalog'][0]
    selected = e001['title'] if selected_is_if else '괴담 동아리'
    pipeline, ctx = make_context(tmp_path, rows=[e001], post=packet['source_post'])
    ctx.comments = [item['content'] for item in packet['source_comments']]
    ctx.fetched_page_info[0]['url'] = e001['url']
    # 기존 recall 부분일치는 양쪽 모두 남아야 한다. URL 자격과 구분한다.
    assert pipeline._source_title_match_quality(e001['title'], selected) is not None
    quality = pipeline._title_matched_official_url_quality(selected, e001['url'], ctx.search_results, require_exact_identity=True)
    assert (quality == 0) if selected_is_if else (quality is None)
    kept = pipeline._can_keep_unavailable_fetch_with_exact_search_title(ctx=ctx,
        url=e001['url'], identified_title=selected, search_results=ctx.search_results,
        fetched_entries=ctx.fetched_page_info)
    assert kept is selected_is_if
    chosen = pipeline._find_title_matched_official_url(selected, ctx.search_results)
    assert chosen == (e001['url'] if selected_is_if else None)
    result = evaluate(pipeline, ctx, selected, e001['url'])
    assert result['valid'] is selected_is_if
    if selected_is_if:
        assert result['fetch_unavailable_search_exact_fallback'] is True
    else:
        assert result['invalid_reason'] == 'url_title_mismatch'
        assert result['title_evidence'] is False
    assert packet['checkpoint_result']['analysis_result']['identity']['novel_identity'] == {
        'official_title': None, 'heretic_url': None}


@pytest.mark.parametrize('source_title,selected', [
    (TITLE, TITLE),
    ('은빛항로의탐험가', TITLE),
    ('노벨피아 - 웹소설로 꿈꾸는 세상! - ' + TITLE, TITLE),
    (TITLE + ' - 네이버 시리즈', TITLE),
    ('웹소설로 꿈꾸는 세상! - ' + TITLE + ' - 노벨피아', TITLE),
    ('[독점] ' + TITLE, TITLE),
    ('[림월드] ' + TITLE, '[림월드] ' + TITLE),
    (TITLE + ' if', TITLE + ' if'),
    ('IF 은빛 항로의 탐험가', 'IF 은빛 항로의 탐험가'),
    (TITLE + ' - if', TITLE + ' - if'),
])
def test_same_work_title_spacing_chrome_and_real_identity_preserved(tmp_path, source_title, selected):
    pipeline, ctx = make_context(tmp_path, source_title=source_title, selected=selected)
    assert pipeline._official_url_title_identity_matches(source_title, selected)
    assert pipeline._title_matched_official_url_quality(selected, URL, ctx.search_results, require_exact_identity=True) == 0
    assert pipeline._find_title_matched_official_url(selected, ctx.search_results) == URL
    result = evaluate(pipeline, ctx, selected)
    assert result['valid'] and result['title_evidence'] and result['fetch_unavailable_search_exact_fallback']


@pytest.mark.parametrize('other_title', [
    TITLE + ' if', TITLE + ' 외전', TITLE + ' 2', TITLE + ' 이후',
    '[다른세계] ' + TITLE, '또 다른 ' + TITLE,
    '은빛 항로의 탐험가들', '은빛 항로의 탐험자', TITLE + ' - if',
])
def test_other_identity_is_not_assigned_original_url_despite_recall(tmp_path, other_title):
    pipeline, ctx = make_context(tmp_path, source_title=other_title)
    assert not pipeline._official_url_title_identity_matches(other_title, TITLE)
    assert pipeline._title_matched_official_url_quality(TITLE, URL, ctx.search_results, require_exact_identity=True) is None
    assert pipeline._find_title_matched_official_url(TITLE, ctx.search_results) is None
    assert not pipeline._can_keep_unavailable_fetch_with_exact_search_title(ctx=ctx, url=URL,
        identified_title=TITLE, search_results=ctx.search_results, fetched_entries=ctx.fetched_page_info)
    assert evaluate(pipeline, ctx, TITLE)['valid'] is False


@pytest.mark.parametrize('status,fetched_title', [
    ('active', TITLE), ('active', '노벨피아 - 웹소설로 꿈꾸는 세상! - ' + TITLE),
    ('active', '403 Forbidden'), ('unavailable', '403 Forbidden'),
])
def test_exact_search_owner_preserves_existing_active_and_blocked_paths(tmp_path, status, fetched_title):
    pipeline, ctx = make_context(tmp_path, status=status, fetched_title=fetched_title)
    result = evaluate(pipeline, ctx, TITLE)
    assert result['valid'] and result['title_evidence']
    assert result['fetch_unavailable_search_exact_fallback'] is (status == 'unavailable')


@pytest.mark.parametrize('status', ['active', 'unavailable'])
def test_other_fetched_title_cannot_lend_original_mention_in_description(tmp_path, status):
    pipeline, ctx = make_context(tmp_path, source_title=TITLE + ' if', status=status,
        fetched_title=TITLE + ' if')
    ctx.fetched_page_info[0]['text_preview'] = TITLE + '의 세계관에서 이어지는 별개의 이야기'
    assert evaluate(pipeline, ctx, TITLE)['valid'] is False
    assert evaluate(pipeline, ctx, TITLE + ' if')['valid'] is True


def test_exact_owner_search_is_not_replaced_by_stale_longer_same_url_title(tmp_path):
    rows = [{'title': TITLE, 'url': URL, 'content': '정확 공식 제목'},
            {'title': '오래된 검색 캐시의 전혀 다른 길고 긴 작품 제목', 'url': URL, 'content': ''}]
    pipeline, ctx = make_context(tmp_path, rows=rows)
    assert pipeline._title_matched_official_url_quality(TITLE, URL, rows, require_exact_identity=True) == 0
    assert pipeline._find_title_matched_official_url(TITLE, rows) == URL
    assert evaluate(pipeline, ctx, TITLE)['valid'] is True


def test_deleted_page_stays_rejected_even_with_exact_search_title(tmp_path):
    pipeline, ctx = make_context(tmp_path, status='deleted', fetched_title=TITLE)
    assert not pipeline._can_keep_unavailable_fetch_with_exact_search_title(ctx=ctx, url=URL,
        identified_title=TITLE, search_results=ctx.search_results, fetched_entries=ctx.fetched_page_info)
    result = evaluate(pipeline, ctx, TITLE)
    assert not result['valid'] and result['invalid_reason'] == 'content_deleted_or_unavailable'


def test_exact_title_at_another_url_cannot_rescue_the_selected_if_url(tmp_path):
    rows = [{'title': TITLE + ' if', 'url': URL, 'content': ''},
            {'title': TITLE, 'url': 'https://novelpia.com/novel/812346', 'content': ''}]
    pipeline, ctx = make_context(tmp_path, rows=rows)
    assert pipeline._title_matched_official_url_quality(TITLE, URL, rows, require_exact_identity=True) is None
    assert pipeline._find_title_matched_official_url(TITLE, rows) == rows[1]['url']
    assert not evaluate(pipeline, ctx, TITLE)['valid']


@pytest.mark.parametrize('field,value', [('_ocr_diagnostic_only', True), ('_purpose', 'image_ocr_diagnostic_probe')])
def test_diagnostic_exact_title_row_cannot_supply_owner_proof(tmp_path, field, value):
    rows = [{'title': TITLE + ' if', 'url': URL, 'content': ''},
            {'title': TITLE, 'url': URL, 'content': '', field: value}]
    pipeline, ctx = make_context(tmp_path, rows=rows)
    assert pipeline._title_matched_official_url_quality(TITLE, URL, rows, require_exact_identity=True) is None
    assert pipeline._find_title_matched_official_url(TITLE, rows) is None
    assert not evaluate(pipeline, ctx, TITLE)['valid']


def test_explicit_packet_title_and_same_url_still_support_branding_only_search(tmp_path):
    post = {'post_id': 720073, 'title': '신작 안내', 'content_blocks': [
        {'type': 'text', 'text': URL}, {'type': 'text', 'text': TITLE}]}
    pipeline, ctx = make_context(tmp_path, source_title='작품 소개 글', post=post)
    assert pipeline._has_post_direct_official_url_title_support(ctx, url=URL, title=TITLE)
    result = evaluate(pipeline, ctx, TITLE)
    assert result['valid'] and result['fetch_unavailable_search_exact_fallback']


def test_legacy_search_ranking_quality_is_preserved_without_url_authority(tmp_path):
    selected = '빌어먹을 환생'
    rows = [{'title': '25화무 빌어먹을 환생 목마 - 앤드북스',
             'url': 'https://book.novelpia.com/novel/19205',
             'content': '뒤로가기. 빌어먹을 환생. 선호. 연재본 > 판타지.', 'rank': 1},
            {'title': '빌어먹을 환생',
             'url': 'https://series.naver.com/novel/detail.series?productNo=5935188',
             'content': '7화 시엘. 8화 시엘. 빌어먹을 환생 프로젝트J.', 'rank': 2}]
    pipeline, _ = make_context(tmp_path)
    assert pipeline._title_matched_official_url_quality(selected, rows[1]['url'], rows) == 0
    assert pipeline._title_matched_official_url_quality(selected, rows[0]['url'], rows) == 1
    assert pipeline._find_title_matched_official_url(selected, rows) == rows[1]['url']
    assert pipeline._title_matched_official_url_quality(selected, rows[0]['url'], rows,
        require_exact_identity=True) is None


@pytest.mark.parametrize('is_same_title', [True, False])
def test_existing_same_work_kakao_tab_canonicalization_keeps_exact_owner(tmp_path, is_same_title):
    pipeline, _ = make_context(tmp_path)
    detail = 'https://page.kakao.com/content/54701995'
    rows = [{'title': TITLE if is_same_title else TITLE + ' if',
             'url': detail + '?tab_type=comment', 'content': ''}]
    expected = detail if is_same_title else None
    assert pipeline._find_title_matched_official_url(TITLE, rows) == expected


def test_original_generic_platform_title_with_explicit_work_header_contract(tmp_path):
    # 기존 rework:4099의 입력/반환 기대 그대로. 별도 원문 작품명·packet URL을 주입하지 않는다.
    pipeline, _ = make_context(tmp_path)
    rows = [
        {'title': '네이버 시리즈',
         'url': 'https://series.naver.com/novel/detail.series?productNo=14041321',
         'content': '즉사기 들고 무림에 떨어지다 125화 연재중 #NOVEL #무협 작가: 오늘도요'},
        {'title': 'novel.munpia.com', 'url': 'https://novel.munpia.com/528383',
         'content': '즉사기 들고 무림에 떨어지다 - 웹소설 문피아'},
    ]
    before = deepcopy(rows)
    assert pipeline._find_title_matched_official_url('즉사기 들고 무림에 떨어지다', rows) == (
        'https://series.naver.com/novel/detail.series?productNo=14041321')
    assert rows == before


@pytest.mark.parametrize('content', [
    TITLE + ' 125화 연재중 #NOVEL #무협 작가: 오늘도요',
    TITLE + ' - 웹소설 문피아',
])
def test_branding_row_header_runs_through_real_evaluator(tmp_path, content):
    rows = [{'title': '노벨피아', 'url': URL, 'content': content}]
    pipeline, ctx = make_context(tmp_path, rows=rows)
    assert pipeline._find_title_matched_official_url(TITLE, rows) == URL
    result = evaluate(pipeline, ctx, TITLE)
    assert result['valid'] and result['fetch_unavailable_search_exact_fallback']


@pytest.mark.parametrize('content', [
    '원작 ' + TITLE + '의 주인공이 등장하는 이야기',
    TITLE + '의 팬픽이다. 125화 연재중',
    TITLE + ' if 125화 연재중 #NOVEL #무협 작가: 오늘도요',
    '소개: ' + TITLE + '을 좋아하는 주인공의 다른 이야기',
])
def test_original_mention_or_different_title_in_branding_snippet_is_not_ownership(tmp_path, content):
    rows = [{'title': '노벨피아', 'url': URL, 'content': content}]
    pipeline, ctx = make_context(tmp_path, rows=rows)
    assert pipeline._title_matched_official_url_quality(TITLE, URL, rows,
        require_exact_identity=True) is None
    assert pipeline._find_title_matched_official_url(TITLE, rows) is None
    assert evaluate(pipeline, ctx, TITLE)['valid'] is False


def test_explicit_header_does_not_override_different_concrete_page_title(tmp_path):
    rows = [{'title': TITLE + ' if', 'url': URL,
             'content': TITLE + ' 125화 연재중 #NOVEL #무협 작가: 오늘도요'}]
    pipeline, ctx = make_context(tmp_path, rows=rows)
    assert pipeline._find_title_matched_official_url(TITLE, rows) is None
    assert not evaluate(pipeline, ctx, TITLE)['valid']
