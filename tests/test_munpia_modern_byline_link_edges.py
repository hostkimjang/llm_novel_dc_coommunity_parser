"""byline의 문피아 숫자 작품 좌표와 가시 링크 경계. ROOT 실행 대기."""
import importlib
from pathlib import Path

import pytest

URL = "https://www.munpia.com/novel/detail/999992"
TITLE = "달빛 항로"


@pytest.fixture(scope="module")
def sut():
    names = ["llm_batch.grounding.munpia_author_byline", "llm_batch.mcp_bridge.server"]
    modules = [importlib.import_module(name) for name in names]
    root = Path(__file__).resolve().parents[1]
    for name, module in zip(names, modules):
        assert Path(module.__file__).resolve() == (root / "src" / (name.replace(".", "/") + ".py")).resolve()
    return modules


def read_byline(sut, inner):
    helper, bridge = sut
    html = (f"<html><head><title>{TITLE} - 문피아 웹소설</title></head><body>"
            f"<h1>{TITLE}</h1><h2>{inner}</h2><p>" + "현재 작품의 충분한 소개문입니다. " * 8 + "</p></body></html>")
    info = bridge._extract_novel_platform_info(html, URL)
    assert info["page_type"] == "novel_page" and info["content_status"] == "active"
    assert helper.valid_byline_evidence(info["author_byline"])
    result = helper.qualify_munpia_fetch(URL, {"url": URL, "text": "", "structured_info": info})["structured_info"]
    name, binding = helper.select_author_evidence([], observations=[result["author_byline_observation"]],
        selected={"official_title": TITLE, "heretic_url": URL})
    return info, result, name, binding


@pytest.mark.parametrize("href,expected", [
    ("/novel/detail/123?x=1", None),
    ("http://novel.munpia.com/123", None),
    ("http://www.munpia.com/novel/detail/123?x=1", None),
    ("https://novel.munpia.com/123?x=1", None),
    ("/novel/detail/999992?x=1", "바람의"),
    ("http://novel.munpia.com/999992", "바람의"),
    ("http://www.munpia.com/novel/detail/999992?x=1", "바람의"),
    ("https://novel.munpia.com/999992?x=1", "바람의"),
    ("/author/123?x=1", "바람의"),
    ("http://novel.munpia.com/author/123", "바람의"),
])
def test_byline_link_work_id_survives_transport_spelling_without_retyping_profiles(sut, href, expected):
    info, result, name, binding = read_byline(sut, f'<a href="{href}">바람의</a>')
    assert name == result.get("author") == expected
    assert info["author_byline"]["status"] == ("VERIFIED" if expected else "NO_EXPLICIT_BYLINE")
    assert (binding is not None) == (expected is not None)
    # 링크의 역할 검사 때문에 요청 URL 허용 범위를 넓히지 않는다.
    helper = sut[0]
    assert not helper.is_munpia_author_detail("http://novel.munpia.com/123")
    assert not helper.is_munpia_author_detail(URL + "?x=1")


@pytest.mark.parametrize("hidden", [
    '<a hidden href="https://novelpia.com/novel/123">다른 작품</a>',
    '<span hidden><a href="/novel/detail/123?x=1">다른 작품</a></span>',
    '<a href="http://novel.munpia.com/123"><span hidden>다른 작품</span></a>',
    '<span style="display:none"><a href="https://novelpia.com/novel/123">다른 작품</a></span>',
])
@pytest.mark.parametrize("visible_author", [False, True])
def test_hidden_work_links_do_not_create_an_author_or_remove_a_visible_byline(sut, hidden, visible_author):
    inner = ("바람의" if visible_author else "") + hidden
    info, result, name, binding = read_byline(sut, inner)
    expected = "바람의" if visible_author else None
    assert name == result.get("author") == expected
    assert info["author_byline"]["status"] == ("VERIFIED" if visible_author else "NO_EXPLICIT_BYLINE")
    assert (binding is not None) is visible_author
