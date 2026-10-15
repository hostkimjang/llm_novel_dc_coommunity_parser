"""기존 동명이작/작가 URL 회귀 입력과 플랫폼·매체 표기 순서 대조. 실제80 재생은 아니다."""
from copy import deepcopy
import socket
import subprocess

import pytest

from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.experts.orchestrator import ConversationContext, ExpertType


TITLE = '세상에 나쁜 영애는 없다'
AUTHOR_URL = 'https://m.munpia.com/novel/detail/405699'
OTHER_URL = 'https://novelpia.com/novel/233647'
RELATED_URL = 'https://series.naver.com/novel/detail.series?productNo=11651797'


class ForbiddenExternal(BaseException):
    pass


def forbidden(*args, **kwargs):
    raise ForbiddenExternal('외부 실행 없이 원형 URL 회귀 입력만 소비한다.')


class NoExternal:
    def __getattr__(self, name):
        return forbidden


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(subprocess, 'run', forbidden)
    monkeypatch.setattr(AgenticPipeline, '_fetch_and_attach_page_info', forbidden)


def original_case(tmp_path):
    # test_agentic_pipeline_rework.py:4121의 입력/작가 근거/기대는 그대로다.
    pipeline = AgenticPipeline(llm=NoExternal(), mcp=NoExternal(), output_dir=tmp_path,
        max_iterations=2)
    pipeline.enable_heretic_live_fetch = False
    pipeline.enable_url_fetch_disk_cache = False
    pipeline._use_session_knowledge = False
    ctx = ConversationContext(post_id=11703669, post_data={
        'post_id': 11703669, 'title': '세나영 하렘 엔딩 아님?',
        'content_blocks': [{'type': 'text', 'text': '하렘엔딩 아닌 코리타에게 무슨 가치가 있음?'}]},
        comments=['세나영 웹툰화 됐고 코리타 외전 기다림'])
    ctx.set_expert_output(ExpertType.GATEKEEPER,
        {'detected_entities': {'possible_authors': ['코리타']}})
    rows = [
        {'rank': 1, 'title': TITLE, 'url': OTHER_URL,
         'content': '빙의한 소설이 자꾸 멸망한다. 그래서 이번에는 마왕을 어릴 때부터 관리하기로 했다.'},
        {'rank': 2, 'title': TITLE + ' - 문피아 웹소설', 'url': AUTHOR_URL,
         'content': '코리타 - 귀족 영애라는 족속들은 싸가지가 없거나, 머리에 꽃밭밖에 없다.'},
        {'rank': 3, 'title': TITLE, 'url': RELATED_URL,
         'content': '귀족 영애라는 족속들은 싸가지가 없거나, 머리에 꽃밭밖에 없다.'},
    ]
    return pipeline, ctx, rows


def test_original_author_context_homonym_expectation_and_exact_owner_both_hold(tmp_path):
    pipeline, ctx, rows = original_case(tmp_path)
    before = deepcopy((ctx.post_data, ctx.comments, rows))
    assert pipeline._get_identified_author(ctx) == '코리타'
    for exact in (False, True):
        owner_rank = pipeline._title_matched_official_url_quality(TITLE, AUTHOR_URL, rows,
            ctx=ctx, require_exact_identity=exact)
        other_rank = pipeline._title_matched_official_url_quality(TITLE, OTHER_URL, rows,
            ctx=ctx, require_exact_identity=exact)
        assert owner_rank is not None and other_rank is not None
        assert owner_rank < other_rank
    assert pipeline._find_title_matched_official_url(TITLE, rows, ctx=ctx) == AUTHOR_URL
    assert (ctx.post_data, ctx.comments, rows) == before


@pytest.mark.parametrize('chrome', ['문피아 웹소설', '웹소설 문피아', '문피아 소설', '소설 문피아'])
def test_platform_media_order_preserves_exact_title_and_independent_author_rank(tmp_path, chrome):
    pipeline, ctx, rows = original_case(tmp_path)
    rows[1]['title'] = TITLE + ' - ' + chrome
    before = deepcopy(rows)
    assert pipeline._official_url_title_identity_matches(rows[1]['title'], TITLE)
    assert pipeline._find_title_matched_official_url(TITLE, rows, ctx=ctx) == AUTHOR_URL
    assert rows == before


@pytest.mark.parametrize('other_title', [TITLE + ' if', TITLE + ' - if', '다른 영애의 일상'])
def test_same_author_does_not_lend_different_work_url(tmp_path, other_title):
    pipeline, ctx, rows = original_case(tmp_path)
    rows[1]['title'] = other_title + ' - 문피아 웹소설'
    before = deepcopy(rows)
    assert pipeline._get_identified_author(ctx) == '코리타'
    assert not pipeline._official_url_title_identity_matches(rows[1]['title'], TITLE)
    assert pipeline._title_matched_official_url_quality(TITLE, AUTHOR_URL, rows,
        ctx=ctx, require_exact_identity=True) is None
    assert pipeline._find_title_matched_official_url(TITLE, rows, ctx=ctx) != AUTHOR_URL
    assert rows == before


@pytest.mark.parametrize('substantive_component', ['가짜플랫폼 웹소설', '문피아 if 웹소설'])
def test_media_word_does_not_erase_nonbranding_title_component(tmp_path, substantive_component):
    pipeline, ctx, rows = original_case(tmp_path)
    rows[1]['title'] = TITLE + ' - ' + substantive_component
    assert not pipeline._official_url_title_identity_matches(rows[1]['title'], TITLE)
    assert pipeline._title_matched_official_url_quality(TITLE, AUTHOR_URL, rows,
        ctx=ctx, require_exact_identity=True) is None
    assert pipeline._find_title_matched_official_url(TITLE, rows, ctx=ctx) != AUTHOR_URL
