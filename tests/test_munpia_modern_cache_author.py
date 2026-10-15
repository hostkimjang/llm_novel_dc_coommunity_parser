"""현대형 문피아의 저장 byline→실제 producer→최종 저자 채널 회귀.

당시 전체 context 재현이 아니다. 캐시의 당시 바이트 동일성은 UNKNOWN이며,
원문/결과는 고정 snapshot, 캐시는 후속 관측본이다. ROOT가 종료 후 실행한다.
"""
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures/munpia_modern_author14"
MODERN = "https://www.munpia.com/novel/detail/999992"
LEGACY = "https://novel.munpia.com/999992"
TITLE = "달빛 항로"
FIXTURE_SHA256 = {
    "url_fetch_cache.json": "910412a3ab46cf479edd9325de9e6ed33cb38b83ee786c78dc9c0b91bb934dad",
    "packet14.json": "7d9fd38c6530be627585abc630f1cde2c04449b54f339054c476bb8c63fd9ee1",
    "provenance.json": "ea0afc584e9e0e18bf0f91b1fb39b304e905607e8ef9e3ad866203c8c1e22421",
}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


@pytest.fixture(scope="module")
def sut():
    names = ["llm_batch.grounding.munpia_author_byline", "llm_batch.mcp_bridge.server",
             "llm_batch.agentic_pipeline", "llm_batch.experts.orchestrator", "llm_batch.domain.models"]
    modules = {name: importlib.import_module(name) for name in names}
    root = Path(__file__).resolve().parents[1]
    for name, module in modules.items():
        assert Path(module.__file__).resolve() == (root / "src" / (name.replace(".", "/") + ".py")).resolve()
    return modules


@pytest.fixture(scope="module")
def facts():
    original = {p.name: p.read_bytes() for p in FIXTURES.iterdir() if p.is_file()}
    for name, expected in FIXTURE_SHA256.items():
        assert digest(original[name]) == expected
    provenance = json.loads(original["provenance.json"])
    assert provenance["cache_bytes_at_original_fetch"] == "UNKNOWN"
    for name, expected in provenance["fixtures_sha256"].items():
        assert digest(original[name]) == expected
    packet = json.loads(original["packet14.json"])
    assert type(packet["post_id"]) is int and packet["index1"] == 14
    assert digest(canonical({"post": packet["source_post"], "comments": packet["source_comments"]})) == provenance["source_canonical_sha256"]
    assert digest(canonical(packet["checkpoint_result"])) == provenance["result_canonical_sha256"]
    values = {"cache": json.loads(original["url_fetch_cache.json"]), "packet": packet, "original": original}
    before = canonical({k: v for k, v in values.items() if k != "original"})
    yield values
    assert canonical({k: v for k, v in values.items() if k != "original"}) == before
    assert {p.name: p.read_bytes() for p in FIXTURES.iterdir() if p.is_file()} == original


def rendered(name="별바다", title=TITLE):
    return f"# {title}\n글\n{name}\n총12화\n완결\n## 작품소개\n밤바다 이야기"


def fetched(name="별바다", *, url=MODERN, text=None):
    return {"url": url, "text": rendered(name) if text is None else text,
            "structured_info": {"page_type": "novel_page", "title": TITLE,
                                "content_status": "active", "author": "오래된 메타데이터"}}


def selected(url=MODERN, title=TITLE):
    return {"official_title": title, "heretic_url": url}


def helper(sut):
    return sut["llm_batch.grounding.munpia_author_byline"]


def qualify(sut, raw, url=MODERN):
    before = canonical(raw)
    got = helper(sut).qualify_munpia_fetch(url, raw)
    assert canonical(raw) == before
    return got["structured_info"]


def select(sut, structured, identity=None):
    proof = structured.get("author_byline")
    hints = [{"name": "잘못된 첫 힌트", "source": "llm_snippet"}]
    if proof:
        hints.append({"name": structured["author"], "source": "url_fetch", "url": proof["url"],
                      "title": proof["title"], "author_byline": helper(sut).compact_byline(proof)})
    return helper(sut).select_author_evidence(hints,
        observations=[structured["author_byline_observation"]], selected=selected() if identity is None else identity)


@pytest.mark.parametrize("name", ["별바다", "바람의", "작가의", "공지", "J. R. River", "밤하늘_7"])
@pytest.mark.parametrize("url", [MODERN, LEGACY])
def test_explicit_names_survive_without_blacklist(sut, name, url):
    result = qualify(sut, fetched(name, url=url), url)
    assert result["author"] == name
    assert helper(sut).valid_byline_evidence(result["author_byline"])
    assert result["author_byline_observation"]["original_author"] == "오래된 메타데이터"
    got, binding = select(sut, result, selected(url))
    assert got == name and binding["url"] == url
    assert helper(sut).normalize_author_work_binding(binding) == binding
    assert helper(sut).author_for_identity({"identified_author": name, "identified_author_work": binding},
                                         {"novel_identity": selected(url)}) == name


@pytest.mark.parametrize("body", [
    "작가의 서재 가기", "# 다른 작품\n글\n별바다\n총12화",
    "# 달빛 항로\n줄거리입니다\n글\n별바다\n총12화",
    "# 달빛 항로\n글\n별바다", "# 달빛 항로\n## 추천\n글\n별바다\n총12화",
])
def test_missing_or_wrong_heading_cannot_keep_old_author(sut, body):
    result = qualify(sut, fetched(text=body))
    assert result.get("author") is None
    assert select(sut, result) == (None, None)


@pytest.mark.parametrize("mode", ["wrong_result_url", "redirect", "deleted", "unavailable", "community_page",
                                  "foreign_previous_url", "foreign_previous_title", "tampered_proof"])
def test_fetch_coordinates_and_prior_proof_are_exact(sut, mode):
    raw = fetched()
    if mode == "wrong_result_url": raw["url"] = "https://www.munpia.com/novel/detail/123"
    if mode == "redirect": raw["final_url"] = "https://www.munpia.com/novel/detail/123"
    if mode in {"deleted", "unavailable"}: raw["structured_info"]["content_status"] = mode
    if mode == "community_page": raw["structured_info"]["page_type"] = "community_post"
    if mode.startswith("foreign_previous") or mode == "tampered_proof":
        title = "다른 작품" if mode == "foreign_previous_title" else TITLE
        url = "https://www.munpia.com/novel/detail/123" if mode == "foreign_previous_url" else MODERN
        proof = helper(sut).byline_evidence(url, title, rendered(title=title), kind="rendered_text")
        if mode == "tampered_proof": proof["source_sha256"] = "0" * 64
        raw["structured_info"]["author_byline"] = proof
    result = qualify(sut, raw)
    assert result.get("author") is None
    assert select(sut, result) == (None, None)


@pytest.mark.parametrize("url", ["http://www.munpia.com/novel/detail/999992",
    MODERN + "?x=1", MODERN + "#card", "https://www.munpia.com.evil.test/novel/detail/999992",
    "https://www.munpia.com/communities/novels-fanart/posts/999992", "https://novelpia.com/novel/999992"])
def test_nonexact_modern_url_does_not_gain_munpia_proof(sut, url):
    assert helper(sut).byline_evidence(url, TITLE, rendered(), kind="rendered_text") is None
    raw = fetched(url=url)
    assert helper(sut).qualify_munpia_fetch(url, raw) is raw


@pytest.mark.parametrize("second", ["별바다", "다른이"])
@pytest.mark.parametrize("placement", ["before_metadata", "after_metadata"])
def test_adjacent_rendered_conflict_does_not_disappear(sut, second, placement):
    text = f"# {TITLE}\n글\n별바다\n"
    if placement == "after_metadata": text += "총12화\n"
    text += f"글\n{second}\n총12화\n## 작품소개\n내용"
    result = qualify(sut, fetched(text=text))
    if second == "별바다":
        assert result["author"] == "별바다" and select(sut, result)[0] == "별바다"
    else:
        assert result.get("author") is None
        assert result["author_byline_observation"]["status"] == "CONFLICT"
        assert select(sut, result) == (None, None)


@pytest.mark.parametrize("mode", ["heading", "jsonld", "meta", "conflict", "no_html_byline"])
def test_existing_modern_html_and_rendered_sources_are_reconciled(sut, mode):
    h1 = f"<h1>{TITLE}</h1>"
    if mode == "heading": html = f"{h1}<h2>별바다</h2>"
    elif mode == "jsonld": html = '<head><script type="application/ld+json">' + json.dumps(
        {"name": TITLE, "url": MODERN, "author": {"name": "별바다"}}, ensure_ascii=False) + '</script></head>' + h1
    elif mode == "meta": html = f'<head><meta property="og:url" content="{MODERN}"><meta name="author" content="별바다"></head>{h1}'
    elif mode == "conflict": html = f'{h1}<h2>다른이</h2>'
    else: html = h1 + '<nav>작가의 서재 가기</nav>'
    # HTML 플랫폼 producer의 제목·본문 길이 계약을 갖춘 합성 대조다.
    html = f"<title>{TITLE} - 문피아 웹소설</title>" + html + "<p>" + "먼 바다를 항해하는 사람들의 이야기입니다. " * 8 + "</p>"
    structured = sut["llm_batch.mcp_bridge.server"]._extract_novel_platform_info(html, MODERN)
    assert structured["title"] == TITLE and structured["page_type"] == "novel_page"
    assert helper(sut).valid_byline_evidence(structured["author_byline"])
    if mode == "heading":
        only_html = qualify(sut, {"url": MODERN, "text": "", "structured_info": deepcopy(structured)})
        assert select(sut, only_html)[0] == "별바다"
    got = qualify(sut, {"url": MODERN, "text": rendered(), "structured_info": structured})
    if mode == "conflict":
        assert got["author_byline_observation"]["status"] == "CONFLICT"
        assert select(sut, got) == (None, None)
    else:
        assert got["author"] == "별바다" and select(sut, got)[0] == "별바다"


@pytest.mark.parametrize("mode", ["modern", "legacy_same_id", "same_title_other_id", "wrong_title", "other_platform", "missing"])
def test_final_selection_binds_both_title_and_numeric_work_id(sut, mode):
    result = qualify(sut, fetched())
    targets = {"modern": selected(), "legacy_same_id": selected(LEGACY),
               "same_title_other_id": selected("https://www.munpia.com/novel/detail/123"),
               "wrong_title": selected(title="다른 작품"),
               "other_platform": selected("https://novelpia.com/novel/999992"), "missing": {}}
    name, binding = select(sut, result, targets[mode])
    assert name == ("별바다" if mode in {"modern", "legacy_same_id"} else None)
    assert (binding is not None) == (name is not None)


def test_unrelated_modern_observation_keeps_bound_other_platform_hint(sut):
    bad = qualify(sut, fetched(text="작가의 서재 가기"))["author_byline_observation"]
    target = selected("https://novelpia.com/novel/12", "다른 책")
    hints = [{"name": "바람의", "source": "url_fetch_platform", "title": target["official_title"], "url": target["heretic_url"]}]
    assert helper(sut).select_author_evidence(hints, observations=[bad], selected=target) == ("바람의", None)


@pytest.mark.parametrize("same_id", [False, True])
def test_modern_selection_keeps_legacy_competition_within_same_work(sut, same_id):
    good = qualify(sut, fetched())["author_byline_observation"]
    other_url = LEGACY if same_id else "https://novel.munpia.com/123"
    other = qualify(sut, fetched("다른이", url=other_url), other_url)["author_byline_observation"]
    for observations in ([good, other], [other, good]):
        got = helper(sut).select_author_evidence([], observations=observations, selected=selected())
        assert got[0] == (None if same_id else "별바다")


def test_modern_source_size_limit_stays_fail_closed(sut):
    assert helper(sut).byline_evidence(MODERN, TITLE, rendered() + " " * helper(sut).MAX_SOURCE_BYTES,
                                      kind="rendered_text") is None


def test_legacy_entrypoint_remains_legacy_only(sut):
    raw = fetched()
    assert helper(sut).qualify_legacy_munpia_fetch(MODERN, raw) is raw
    old = fetched(url=LEGACY)
    assert helper(sut).qualify_legacy_munpia_fetch(LEGACY, old) == helper(sut).qualify_munpia_fetch(LEGACY, old)


def test_actual_cache_real_enrichment_final_envelope_without_success_stub(sut, facts, tmp_path):
    attempts = []
    class ExternalAttemptBlocked(BaseException):
        pass
    class NoExternal:
        def __getattr__(self, name):
            def denied(*args, **kwargs):
                attempts.append(name)
                raise ExternalAttemptBlocked("MODERN_AUTHOR_EXTERNAL_ATTEMPT:" + name)
            return denied
    cache = deepcopy(facts["cache"]); packet = facts["packet"]
    P = sut["llm_batch.agentic_pipeline"].AgenticPipeline
    pipe = P(llm=NoExternal(), mcp=NoExternal(), output_dir=tmp_path / "pipeline",
             max_iterations=1, parallel_count=12, worker_id=0, native_recovery=True)
    pipe._use_session_knowledge = False
    pipe.enable_url_fetch_disk_cache = True
    pipe.url_fetch_cache_dir = tmp_path / "cache"
    pipe.url_fetch_cache_dir.mkdir()
    cached_file = pipe.url_fetch_cache_dir / (hashlib.sha1(cache["url"].encode()).hexdigest() + ".json")
    cached_file.write_bytes(facts["original"]["url_fetch_cache.json"])
    raw, meta = pipe._fetch_with_meta(cache["url"])
    raw_before = canonical(raw)
    assert meta["from_cache"] is True and raw["structured_info"]["author"] == "공지"
    models = sut["llm_batch.domain.models"]; o = sut["llm_batch.experts.orchestrator"]
    post = models.PostInput(**deepcopy(packet["source_post"]), comments=deepcopy(packet["source_comments"]))
    ctx = o.ConversationContext(post_id=post.post_id, post_data=pipe._post_to_dict(post), comments=pipe._extract_comments(post))
    source_before = canonical([ctx.post_data, ctx.comments])
    identity = deepcopy(packet["checkpoint_result"]["analysis_result"]["identity"])
    e007 = next(v for v in identity["search_evidence_catalog"] if v["eid"] == "E007")
    # 저장 catalog의 내용/URL만 얇은 search-row 형식으로 전달한다. 당시 전체 검색 시퀀스는 아니다.
    lead = {"title": e007["title"], "url": e007["url"], "content": e007["snippet"],
            "source": "SAVED_E007_PARTIAL_REPLAY"}
    orchestrator = o.Orchestrator(experts={}, search_fn=None, fetch_fn=pipe._fetch,
        max_iterations=1, parallel_count=12, page_cache_dir=tmp_path / "pages", page_cache_enabled=False,
        monitor_enabled=False, fetch_concurrency=1)
    orchestrator._deep_search_enrich(ctx, [], [lead], post_data=deepcopy(ctx.post_data), gatekeeper_result=None)
    hints = ctx.snippet_hints["author_hints"]
    bound = [h for h in hints if h.get("author_byline")]
    assert bound and any(h["name"] == "검미성" and h["url"] == cache["url"] and h["title"] == e007["title"] for h in bound)
    assert all(h.get("name") != "공지" for h in hints)
    assert any(v["status"] == "VERIFIED" and v["url"] == cache["url"] for v in ctx._munpia_author_byline_observations)
    envelope = pipe._build_final_batch_context_learning_envelope(ctx, identity)
    assert envelope["identified_author"] == "검미성"
    assert envelope["identified_author_work"]["url"] == cache["url"]
    assert envelope["identified_author_work"]["title"] == e007["title"]
    assert helper(sut).author_for_identity(envelope, identity) == "검미성"
    control = deepcopy(packet["checkpoint_result"]["analysis_result"])
    control["batch_context_learning_envelope"] = envelope
    typed = models.PickvelOutputItemV2.model_validate(control)
    assert typed.model_dump(mode="json")["batch_context_learning_envelope"] == envelope
    wrong = deepcopy(identity); wrong["novel_identity"]["heretic_url"] = "https://www.munpia.com/novel/detail/380282"
    assert helper(sut).author_for_identity(envelope, wrong) is None
    assert '"source_text"' not in canonical([ctx.fetched_page_info, ctx.snippet_hints]).decode()
    assert canonical([ctx.post_data, ctx.comments]) == source_before
    assert canonical(raw) == raw_before and cached_file.read_bytes() == facts["original"]["url_fetch_cache.json"]
    assert attempts == []
