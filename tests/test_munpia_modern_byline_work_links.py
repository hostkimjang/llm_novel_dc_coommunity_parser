"""현대 문피아 byline의 명시 외부 작품 링크와 프로필 링크 대조. ROOT 실행 대기."""
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


def linked_author(sut, href):
    helper, bridge = sut
    html = (f"<html><head><title>{TITLE} - 문피아 웹소설</title></head><body>"
            f'<h1>{TITLE}</h1><h2><a href="{href}">바람의</a></h2>'
            + "<p>" + "현재 작품의 충분한 길이의 소개문입니다. " * 8 + "</p></body></html>")
    info = bridge._extract_novel_platform_info(html, URL)
    proof = info["author_byline"]
    assert info["page_type"] == "novel_page" and info["content_status"] == "active"
    assert helper.valid_byline_evidence(proof)
    qualified = helper.qualify_munpia_fetch(URL, {"url": URL, "text": "", "structured_info": info})["structured_info"]
    name, binding = helper.select_author_evidence([], observations=[qualified["author_byline_observation"]],
        selected={"official_title": TITLE, "heretic_url": URL})
    return proof, qualified, name, binding


@pytest.mark.parametrize("href", [
    "https://novelpia.com/novel/123",
    "http://novelpia.com/novel/123",
    "https://www.novelpia.com/novel/123",
    "https://book.novelpia.com/novel/123",
    "https://series.naver.com/novel/detail.series?productNo=123",
    "https://series.naver.com/comic/detail.series?productNo=123",
    "https://series.naver.com/ebook/detail.series?productNo=123",
    "https://m.series.naver.com/novel/detail.series?productNo=123",
    "https://page.kakao.com/content/123",
    "https://page.kakao.com/home/다른-작품/123",
    "https://ridibooks.com/books/123",
    "https://www.ridibooks.com/books/123",
])
def test_explicit_foreign_official_work_link_is_not_an_author_profile(sut, href):
    proof, qualified, name, binding = linked_author(sut, href)
    assert proof["status"] == "NO_EXPLICIT_BYLINE" and proof["name"] is None
    assert qualified.get("author") is None and name is None and binding is None


@pytest.mark.parametrize("href", [
    "/author/123",
    "https://novelpia.com/member/123",
    "https://writer.example/profile/123",
    "https://writer.example/novel/123",
    "https://series.naver.com/author/detail.series?authorNo=123",
    URL,
    "https://novel.munpia.com/999992",
])
def test_nonwork_profiles_and_current_work_coordinate_keep_explicit_name(sut, href):
    # 링크 역할의 합성 대조이며 외부 프로필 URL의 실제 존재를 주장하지 않는다.
    proof, qualified, name, binding = linked_author(sut, href)
    assert proof["status"] == "VERIFIED" and proof["name"] == "바람의"
    assert qualified["author"] == name == "바람의" and binding["url"] == URL
