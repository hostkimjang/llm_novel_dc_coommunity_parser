"""명시 byline 인접 구간 끝의 충돌과 반복 정상 표기를 구분한다."""
from copy import deepcopy
import importlib

import pytest

URL = 'https://novel.munpia.com/999992'
TITLE = '달빛 항로'


@pytest.mark.parametrize('name,count', [('별바다', 5), ('바람의', 12), ('작가의', 64)])
def test_more_than_four_equal_bylines_preserve_the_explicit_name(name, count):
    helper = importlib.import_module('llm_batch.grounding.munpia_author_byline')
    raw = '<h1>' + TITLE + '</h1>' + ('<div>글 ' + name + '</div>') * count
    proof = helper.byline_evidence(URL, TITLE, raw, kind='html')
    assert proof['status'] == 'VERIFIED' and proof['name'] == name
    assert helper.valid_byline_evidence(proof)
    fetched = {'url': URL, 'text': '', 'structured_info': {'title': TITLE, 'author': name, 'author_byline': proof}}
    before = deepcopy(fetched)
    structured = helper.qualify_legacy_munpia_fetch(URL, fetched)['structured_info']
    got = helper.select_author_hint([], observations=[structured['author_byline_observation']],
        selected={'official_title': TITLE, 'heretic_url': URL})
    assert got == name and fetched == before


@pytest.mark.parametrize('same_count', [4, 5, 63])
def test_later_conflicting_byline_cannot_hide_behind_equal_prefix(same_count):
    helper = importlib.import_module('llm_batch.grounding.munpia_author_byline')
    raw = '<h1>' + TITLE + '</h1>' + '<div>글 별바다</div>' * same_count + '<div>작가: 다른이</div>'
    proof = helper.byline_evidence(URL, TITLE, raw, kind='html')
    assert proof['status'] == 'CONFLICT' and proof['name'] is None
    assert helper.valid_byline_evidence(proof)
    fetched = {'url': URL, 'text': '', 'structured_info': {'title': TITLE, 'author': '별바다', 'author_byline': proof}}
    before = deepcopy(fetched)
    structured = helper.qualify_legacy_munpia_fetch(URL, fetched)['structured_info']
    assert structured.get('author') is None and structured['author_byline_observation']['status'] == 'CONFLICT'
    assert helper.select_author_hint([{'name': '별바다', 'source': 'url_fetch'}],
        observations=[structured['author_byline_observation']],
        selected={'official_title': TITLE, 'heretic_url': URL}) is None
    assert fetched == before


def test_source_size_limit_remains_fail_closed():
    helper = importlib.import_module('llm_batch.grounding.munpia_author_byline')
    raw = '<h1>' + TITLE + '</h1><div>글 별바다</div>' + ' ' * helper.MAX_SOURCE_BYTES
    assert len(raw.encode()) > 262144
    assert helper.byline_evidence(URL, TITLE, raw, kind='html') is None
