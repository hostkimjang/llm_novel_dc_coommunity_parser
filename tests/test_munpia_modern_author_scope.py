"""현대형 HTML의 작품 영역과 실제 저장 저자 소비 대조. ROOT 종료 후 실행용."""
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path

import pytest

URL = "https://www.munpia.com/novel/detail/999992"
TITLE = "달빛 항로"
FIXTURE = Path(__file__).parent / "fixtures/munpia_modern_author14/munpia_publish_control.json"
FIXTURE_SHA = "5ec03c4532a2528603b90e9c74b952d43a8997f4f2ebda09265eb77fec04d88c"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


@pytest.fixture(scope="module")
def sut():
    names = ["llm_batch.grounding.munpia_author_byline", "llm_batch.mcp_bridge.server",
             "llm_batch.agentic_pipeline", "llm_batch.experts.orchestrator", "llm_batch.domain.models",
             "llm_batch.domain.batch_context", "llm_batch.ledger.publication_commit", "expert_main"]
    modules = {name: importlib.import_module(name) for name in names}
    root = Path(__file__).resolve().parents[1]
    for name, module in modules.items():
        expected = root / "expert_main.py" if name == "expert_main" else root / "src" / (name.replace(".", "/") + ".py")
        assert Path(module.__file__).resolve() == expected.resolve()
    return modules


def document(body, *, head="", title=TITLE):
    return (f"<html><head><title>{title} - 문피아 웹소설</title>{head}</head><body>"
            + body + "<p>" + "현재 작품의 소개를 담은 충분한 길이의 문장입니다. " * 8 + "</p></body></html>")


def modern(sut, raw, *, title=TITLE, url=URL, text=""):
    helper = sut["llm_batch.grounding.munpia_author_byline"]
    info = sut["llm_batch.mcp_bridge.server"]._extract_novel_platform_info(raw, url)
    assert info["title"] == title and info["page_type"] == "novel_page"
    assert info["content_status"] == "active"
    assert helper.valid_byline_evidence(info["author_byline"])
    fetched = {"url": url, "text": text, "structured_info": info}
    before = canonical(fetched)
    qualified = helper.qualify_munpia_fetch(url, fetched)["structured_info"]
    assert canonical(fetched) == before
    selected = {"official_title": title, "heretic_url": url}
    name, binding = helper.select_author_evidence([], observations=[qualified["author_byline_observation"]], selected=selected)
    return info, qualified, name, binding


@pytest.mark.parametrize("region", ["aside", "nav", "template", "footer", "hidden", "hidden_false",
                                    "aria_hidden", "display_none", "visibility_hidden", "visibility_collapse"])
@pytest.mark.parametrize("placement", ["before", "after"])
@pytest.mark.parametrize("visible_byline", [False, True])
def test_excluded_region_neither_creates_author_nor_conflicts_with_visible_byline(sut, region, placement, visible_byline):
    attrs = {"hidden": "hidden", "hidden_false": "hidden='false'", "aria_hidden": "aria-hidden='true'",
             "display_none": "style='display: none'", "visibility_hidden": "style='visibility:hidden!important'",
             "visibility_collapse": "style='visibility:collapse'"}
    tag = region if region in {"aside", "nav", "template", "footer"} else "div"
    excluded = f"<{tag} {attrs.get(region, '')}><h1>{TITLE}</h1><h2>다른이</h2></{tag}>"
    main = f"<h1>{TITLE}</h1>" + ("<h2>별바다</h2>" if visible_byline else "<p>작품 소개</p>")
    body = excluded + main if placement == "before" else main + excluded
    info, qualified, name, binding = modern(sut, document(body))
    assert name == ("별바다" if visible_byline else None)
    assert qualified.get("author") == name
    assert info["author_byline"]["status"] == ("VERIFIED" if visible_byline else "NO_EXPLICIT_BYLINE")
    assert (binding is not None) is visible_byline


@pytest.mark.parametrize("href,card_title", [
    ("https://www.munpia.com/novel/detail/123", TITLE),
    ("/novel/detail/123", TITLE),
    ("https://novel.munpia.com/123", "다른 책"),
    ("https://novelpia.com/novel/999992", TITLE),
])
@pytest.mark.parametrize("placement", ["before", "after"])
def test_other_work_link_cannot_claim_the_requested_coordinates(sut, href, card_title, placement):
    card = f'<a href="{href}"><h1>{card_title}</h1><h2>다른이</h2></a>'
    main = f"<h1>{TITLE}</h1><h2>별바다</h2>"
    body = card + main if placement == "before" else main + card
    _, qualified, name, binding = modern(sut, document(body))
    assert name == "별바다" and binding["url"] == URL
    assert qualified["author_byline_observation"]["status"] == "VERIFIED"


@pytest.mark.parametrize("href", [URL, "/novel/detail/999992", "https://novel.munpia.com/999992"])
def test_current_work_title_link_keeps_normal_author(sut, href):
    body = f'<a href="{href}"><h1>{TITLE}</h1><h2>작가의</h2></a>'
    _, _, name, binding = modern(sut, document(body))
    assert name == "작가의" and binding["url"] == URL


@pytest.mark.parametrize("href,expected", [("/author/123", "바람의"), ("/novel/detail/123", None)])
def test_inline_author_profile_and_other_work_link_are_distinct(sut, href, expected):
    body = f'<h1>{TITLE}</h1><h2><a href="{href}">바람의</a></h2>'
    _, _, name, binding = modern(sut, document(body))
    assert name == expected and (binding is not None) == (expected is not None)


@pytest.mark.parametrize("position", ["heading", "byline"])
def test_malformed_card_link_does_not_create_author_or_raise(sut, position):
    if position == "heading":
        body = f'<a href="https://[broken"><h1>{TITLE}</h1><h2>다른이</h2></a>'
    else:
        body = f'<h1>{TITLE}</h1><h2><a href="https://[broken">다른이</a></h2>'
    _, _, name, binding = modern(sut, document(body))
    assert name is None and binding is None


@pytest.mark.parametrize("shape", ["adjacent_h2", "repeated_header"])
@pytest.mark.parametrize("second", ["별바다", "다른이"])
def test_visible_same_work_repeated_bylines_keep_real_conflicts(sut, shape, second):
    body = f"<h1>{TITLE}</h1><h2>별바다</h2>"
    if shape == "repeated_header":
        body += f"<h1>{TITLE}</h1>"
    body += f"<h2>{second}</h2>"
    info, qualified, name, _ = modern(sut, document(body), text=f"# {TITLE}\n글\n별바다\n총12화")
    expected_status = "VERIFIED" if second == "별바다" else "CONFLICT"
    assert info["author_byline"]["status"] == qualified["author_byline_observation"]["status"] == expected_status
    assert name == ("별바다" if second == "별바다" else None)


def test_later_matching_heading_cannot_replace_different_first_visible_work(sut):
    body = f"<h1>다른 작품</h1><h2>다른이</h2><h1>{TITLE}</h1><h2>별바다</h2>"
    _, _, name, binding = modern(sut, document(body))
    assert name is None and binding is None


@pytest.mark.parametrize("placement", ["template", "body"])
def test_nested_fake_head_metadata_does_not_become_document_metadata(sut, placement):
    fake = f'<head><meta property="og:url" content="{URL}"><meta name="author" content="다른이"></head>'
    fake = f"<template>{fake}</template>" if placement == "template" else fake
    _, _, name, binding = modern(sut, document(f"<h1>{TITLE}</h1><p>소개</p>" + fake))
    assert name is None and binding is None


@pytest.mark.parametrize("mode", ["jsonld_exact", "jsonld_og", "meta_exact", "meta_unbound_title",
                                   "other_og", "other_canonical", "foreign_jsonld", "hidden_meta",
                                   "body_jsonld", "mixed_jsonld", "missing_jsonld_url"])
def test_structured_metadata_is_bound_to_actual_document_and_work(sut, mode):
    helper = sut["llm_batch.grounding.munpia_author_byline"]
    item = {"name": TITLE, "url": URL, "author": {"name": "별바다"}}
    head = f"<title>{TITLE} - 문피아 웹소설</title>"
    body = ""
    if mode in {"jsonld_og", "missing_jsonld_url"}:
        item.pop("url")
    if mode == "foreign_jsonld":
        item["url"] = "https://www.munpia.com/novel/detail/123"
    payload = [dict(item, url="https://www.munpia.com/novel/detail/123", author={"name": "다른이"}), item] if mode == "mixed_jsonld" else item
    script = '<script type="application/ld+json">' + json.dumps(payload, ensure_ascii=False) + '</script>'
    if mode in {"meta_exact", "meta_unbound_title", "hidden_meta"}:
        head += f'<meta content="{URL}" property="og:url"><meta content="별바다" name="author"' + (' hidden' if mode == "hidden_meta" else '') + '>'
        if mode == "meta_unbound_title":
            head = head.replace(f"<title>{TITLE} - 문피아 웹소설</title>", "")
    elif mode == "body_jsonld":
        body = script
    else:
        head += script
    if mode == "jsonld_og":
        head += f'<meta property="og:url" content="{URL}">'
    if mode == "other_og":
        head += '<meta property="og:url" content="https://www.munpia.com/novel/detail/123">'
    if mode == "other_canonical":
        head += '<link rel="canonical" href="https://www.munpia.com/novel/detail/123">'
    html = f"<html><head>{head}</head><body>{body}</body></html>"
    proof = helper.byline_evidence(URL, TITLE, html, kind="html")
    assert helper.valid_byline_evidence(proof)
    expected = "별바다" if mode in {"jsonld_exact", "jsonld_og", "meta_exact", "mixed_jsonld"} else None
    assert proof["name"] == expected
    assert proof["status"] == ("VERIFIED" if expected else "NO_EXPLICIT_BYLINE")


@pytest.mark.parametrize("mode", ["modern_html", "modern_rendered", "other_id", "other_title", "binding_name"])
def test_modern_proof_survives_real_main_wal_reopen_and_author_consumer(sut, tmp_path, mode):
    fixture_bytes = FIXTURE.read_bytes()
    assert hashlib.sha256(fixture_bytes).hexdigest() == FIXTURE_SHA
    row = deepcopy(json.loads(fixture_bytes)["packet"]["checkpoint_result"])
    identity = row["analysis_result"]["identity"]
    selected = identity["novel_identity"]
    title, url = selected["official_title"], selected["heretic_url"]
    helper = sut["llm_batch.grounding.munpia_author_byline"]
    # 공개 작품 쌍은 원형이다. 별바다는 저자 전달 채널만 검증하는 합성 필명이다.
    raw = document(f"<h1>{title}</h1><h2>별바다</h2>", title=title)
    info = sut["llm_batch.mcp_bridge.server"]._extract_novel_platform_info(raw, url)
    text = f"# {title}\n글\n별바다\n총12화" if mode == "modern_rendered" else ""
    if mode == "modern_rendered":
        info.pop("author_byline", None)
    qualified = helper.qualify_munpia_fetch(url, {"url": url, "text": text, "structured_info": info})["structured_info"]
    proof = qualified["author_byline"]
    assert proof["status"] == "VERIFIED" and proof["source_kind"] == ("rendered_text" if mode == "modern_rendered" else "html")
    orchestrator = sut["llm_batch.experts.orchestrator"]
    ctx = orchestrator.ConversationContext(post_id=row["post_id"], post_data={}, comments=[])
    ctx.snippet_hints = {"author_hints": [{"name": "별바다", "source": "url_fetch", "url": url,
                                         "title": title, "author_byline": helper.compact_byline(proof)}]}
    ctx._munpia_author_byline_observations = [qualified["author_byline_observation"]]
    before_context = canonical([ctx.snippet_hints, ctx._munpia_author_byline_observations])
    pipe = object.__new__(sut["llm_batch.agentic_pipeline"].AgenticPipeline)
    envelope = pipe._build_final_batch_context_learning_envelope(ctx, identity)
    assert envelope["identified_author"] == "별바다" and envelope["identified_author_work"]["url"] == url
    assert canonical([ctx.snippet_hints, ctx._munpia_author_byline_observations]) == before_context
    if mode == "other_id":
        envelope["identified_author_work"]["url"] = "https://www.munpia.com/novel/detail/7777"
    if mode == "other_title":
        envelope["identified_author_work"]["title"] = "다른 작품"
    if mode == "binding_name":
        envelope["identified_author_work"]["name"] = "다른이"
    input_envelope_before = canonical(envelope)
    expected_typed_envelope = deepcopy(envelope)
    if mode == "binding_name":
        # 이름이 다른 결속은 typed 정규화가 저자 채널을 거절한다.
        # 원래 입력의 변조 관측과 다른 필드는 그대로 보존해야 한다.
        expected_typed_envelope["identified_author"] = None
    row["analysis_result"]["batch_context_learning_envelope"] = envelope
    typed = sut["llm_batch.domain.models"].PickvelOutputItemV2.model_validate(row["analysis_result"])
    row["analysis_result"]["batch_context_learning_envelope"] = typed.model_dump(mode="json")["batch_context_learning_envelope"]
    assert canonical(envelope) == input_envelope_before
    assert row["analysis_result"]["batch_context_learning_envelope"] == expected_typed_envelope
    ledger = sut["llm_batch.ledger.publication_commit"]
    before = canonical(row)
    scope = ledger.build_publication_scope_descriptor(input_file_sha256=hashlib.sha256(before.encode()).hexdigest(),
        post_ids=[row["post_id"]], config_hash="modern-author-consumer-control", release_fingerprint="synthetic-modern-author-channel")
    wal = tmp_path / "modern_author.jsonl"
    registry = ledger.PublicationCommitRegistry(wal, scope_descriptor=scope, create_new=True)
    receipt, created = ledger.commit_publication_result(row, registry=registry, attempt_run_id="modern-author-control",
        input_index=1, post_id=row["post_id"])
    assert created and receipt.publish_allowed is True
    wal_bytes = wal.read_bytes()
    reopened = ledger.PublicationCommitRegistry(wal, scope_descriptor=scope, create_new=False)
    stored = reopened.result(row["post_id"])
    receipts = [value for value in reopened.receipts() if value.post_id == row["post_id"]]
    assert len(receipts) == 1 and receipts[0].to_dict() == receipt.to_dict()
    receipt = receipts[0]
    ledger.validate_publication_result_commit(stored, receipt, expected_scope_id=scope.publication_scope_id,
        expected_input_index=1, expected_post_id=row["post_id"])
    assert stored["analysis_result"]["batch_context_learning_envelope"] == expected_typed_envelope
    if mode == "binding_name":
        assert stored["analysis_result"]["batch_context_learning_envelope"]["identified_author"] is None
    memory = sut["llm_batch.domain.batch_context"].BatchContextMemory(enabled=True)
    assert sut["expert_main"]._learn_batch_context_from_canonical_publication(memory, stored, receipt, created=created) is True
    expected = {memory._normalize("별바다")} if mode in {"modern_html", "modern_rendered"} else set()
    assert set(memory.resolved_authors) == expected
    assert canonical(stored) == canonical(row) == before and wal.read_bytes() == wal_bytes
    assert FIXTURE.read_bytes() == fixture_bytes
