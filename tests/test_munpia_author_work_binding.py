"""문피아 저자·작품 관계와 실제 소비 경계. ROOT 격리 실행 대기."""
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures/munpia_author14_repair"
URL = "https://novel.munpia.com/999992"
TITLE = "달빛 항로"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


@pytest.fixture(scope="module")
def sut():
    names = ["llm_batch.grounding.munpia_author_byline", "llm_batch.mcp_bridge.server",
             "llm_batch.agentic_pipeline", "llm_batch.experts.orchestrator", "llm_batch.domain.models",
             "llm_batch.domain.batch_context", "llm_batch.ledger.publication_commit", "expert_main"]
    return {name: importlib.import_module(name) for name in names}


def proof_hint(sut, name="바람의", title=TITLE, url=URL):
    helper = sut["llm_batch.grounding.munpia_author_byline"]
    proof = helper.byline_evidence(url, title, f"# {title}\n글\n{name}\n총12화", kind="rendered_text")
    assert proof["status"] == "VERIFIED"
    return {"name": name, "source": "url_fetch", "url": url, "author_byline": proof}


def build(sut, hints, selected, observations=()):
    o = sut["llm_batch.experts.orchestrator"]
    ctx = o.ConversationContext(post_id=1, post_data={}, comments=[])
    ctx.snippet_hints = {"author_hints": deepcopy(hints)}
    ctx._munpia_author_byline_observations = deepcopy(observations)
    before = canonical([ctx.snippet_hints, ctx._munpia_author_byline_observations])
    pipe = object.__new__(sut["llm_batch.agentic_pipeline"].AgenticPipeline)
    env = pipe._build_final_batch_context_learning_envelope(ctx, {"novel_identity": selected})
    assert canonical([ctx.snippet_hints, ctx._munpia_author_byline_observations]) == before
    return env


@pytest.mark.parametrize("attrs", ["hidden", "hidden='false'", "aria-hidden='true'", "style='display: none'",
                                  "style='visibility: hidden !important'", "style='visibility:collapse'"])
def test_hidden_heading_cannot_win_over_visible_author(sut, attrs):
    raw = (f"<div {attrs}><h1>{TITLE}</h1><div>글 별바다</div></div>"
           f"<h1>{TITLE}</h1><div>글 바람의</div>")
    got = sut["llm_batch.grounding.munpia_author_byline"].byline_evidence(URL, TITLE, raw, kind="html")
    assert got["status"] == "VERIFIED" and got["name"] == "바람의"


@pytest.mark.parametrize("attrs", ["hidden", "aria-hidden='true'", "style='display:none'"])
def test_hidden_adjacent_byline_cannot_conflict_with_visible_name(sut, attrs):
    raw = f"<h1>{TITLE}</h1><div {attrs}>글 별바다</div><div>글 작가의</div>"
    got = sut["llm_batch.grounding.munpia_author_byline"].byline_evidence(URL, TITLE, raw, kind="html")
    assert got["status"] == "VERIFIED" and got["name"] == "작가의"


@pytest.mark.parametrize("mode", ["different_title", "same_title_other_edition", "both_different", "selected_missing"])
def test_valid_other_work_byline_never_becomes_selected_author(sut, mode):
    selected = {"official_title": TITLE, "heretic_url": URL}
    title = "다른 작품" if mode in {"different_title", "both_different"} else TITLE
    url = "https://novel.munpia.com/7777" if mode in {"same_title_other_edition", "both_different"} else URL
    if mode == "selected_missing": selected = {}
    env = build(sut, [proof_hint(sut, title=title, url=url), {"name": "작가의", "source": "url_fetch"}], selected)
    assert env["identified_author"] is None
    assert "identified_author_work" not in env


@pytest.mark.parametrize("reverse", [False, True])
def test_right_work_survives_other_book_author_order(sut, reverse):
    hints = [proof_hint(sut, name="다른이", title="다른 작품", url="https://novel.munpia.com/7777"), proof_hint(sut)]
    if reverse: hints.reverse()
    env = build(sut, hints, {"official_title": TITLE, "heretic_url": URL})
    assert env["identified_author"] == "바람의"
    assert env["identified_author_work"]["url"] == URL


def test_unrelated_munpia_conflict_does_not_suppress_bound_other_platform(sut):
    selected = {"official_title": "다른 책", "heretic_url": "https://novelpia.com/novel/12"}
    observation = {"status": "CONFLICT", "url": URL, "title": TITLE, "evidence": []}
    env = build(sut, [{"name": "별바다", "source": "url_fetch_platform", "title": selected["official_title"],
                       "url": selected["heretic_url"]}], selected, [observation])
    assert env["identified_author"] == "별바다"


@pytest.mark.parametrize("mode", ["html_conflict", "html_rendered_conflict", "invalid_previous"])
def test_real_enrichment_carries_conflict_past_generic_hint_and_keeps_raw_private(sut, tmp_path, mode):
    fixture_bytes = (FIXTURES / "fixture.json").read_bytes()
    cache_bytes = (FIXTURES / "url_fetch_cache.json").read_bytes()
    facts, cache = json.loads(fixture_bytes), json.loads(cache_bytes)
    raw = deepcopy(cache["result"]); url = cache["url"]; title = raw["structured_info"]["title"]
    helper = sut["llm_batch.grounding.munpia_author_byline"]
    html = f"<h1>{title}</h1><div>글 별바다</div>"
    if mode == "html_conflict": html += "<div>작가: 다른이</div>"
    proof = helper.byline_evidence(url, title, html, kind="html")
    if mode == "invalid_previous": proof["source_sha256"] = "0" * 64
    raw["structured_info"]["author_byline"] = proof
    if mode != "html_rendered_conflict": raw["text"] = ""
    before = canonical(raw); attempts = []
    class ExternalAttemptBlocked(BaseException):
        pass
    def fetch(requested):
        attempts.append(requested)
        if requested != url: raise ExternalAttemptBlocked(requested)
        return raw
    o = sut["llm_batch.experts.orchestrator"]; p = sut["llm_batch.agentic_pipeline"].AgenticPipeline
    class NoExternal:
        def __getattr__(self, name):
            def denied(*args, **kwargs):
                attempts.append('EXTERNAL:' + name)
                raise ExternalAttemptBlocked('AUTHOR_REPAIR_EXTERNAL_ATTEMPT:' + name)
            return denied
    pipe = p(llm=NoExternal(), mcp=NoExternal(), output_dir=tmp_path / 'pipeline',
             max_iterations=1, parallel_count=12, worker_id=0, native_recovery=True)
    pipe.enable_url_fetch_disk_cache = False
    pipe._use_session_knowledge = False
    packet = facts["packet14"]
    post = sut["llm_batch.domain.models"].PostInput(**deepcopy(packet["source_post"]), comments=deepcopy(packet["source_comments"]))
    ctx = o.ConversationContext(post_id=post.post_id, post_data=pipe._post_to_dict(post), comments=pipe._extract_comments(post))
    ctx.snippet_hints = {"author_hints": [{"name": "검미성", "source": "llm_term_role"}],
                         "title_hints": [], "abbreviation_hints": []}
    orchestrator = o.Orchestrator(experts={}, search_fn=None, fetch_fn=fetch, max_iterations=1,
        parallel_count=12, page_cache_dir=tmp_path / "pages", page_cache_enabled=False,
        monitor_enabled=False, fetch_concurrency=1)
    orchestrator._deep_search_enrich(ctx, [], [deepcopy(facts["cache_lead_control"])],
                                    post_data=deepcopy(ctx.post_data), gatekeeper_result=None)
    assert attempts and all(value == url for value in attempts)
    assert ctx._munpia_author_byline_observations
    assert any(h.get("name") == "검미성" for h in ctx.snippet_hints["author_hints"])
    assert pipe._build_final_batch_context_learning_envelope(ctx, {"novel_identity": {
        "official_title": title, "heretic_url": url}})["identified_author"] is None
    assert '"source_text"' not in canonical([ctx.fetched_page_info, ctx.snippet_hints])
    assert canonical(raw) == before
    assert (FIXTURES / "fixture.json").read_bytes() == fixture_bytes
    assert (FIXTURES / "url_fetch_cache.json").read_bytes() == cache_bytes


@pytest.mark.parametrize("mode", ["same_pair", "same_munpia_id_modern_url", "other_title", "other_edition",
                                  "other_platform", "binding_name", "binding_missing_field", "binding_digest_shape"])
def test_typed_main_wal_rechecks_author_pair_after_envelope_creation(sut, tmp_path, mode):
    row = deepcopy(json.loads((FIXTURES / "munpia_publish_control.json").read_text(encoding="utf8"))["packet"]["checkpoint_result"])
    selected = row["analysis_result"]["identity"]["novel_identity"]
    title = selected["official_title"]; legacy_url = "https://novel.munpia.com/222360"
    env = build(sut, [proof_hint(sut, title=title, url=legacy_url)], {
        "official_title": title, "heretic_url": legacy_url if mode == "same_pair" else selected["heretic_url"]})
    assert env["identified_author"] == "바람의"
    # 공개 identity/ledger는 원형 유지. 잘못 결속된 전달 채널만 바꿔 실제 소비자의 대조를 확인한다.
    if mode == "other_title": env["identified_author_work"]["title"] = "다른 작품"
    if mode == "other_edition": env["identified_author_work"]["url"] = "https://novel.munpia.com/7777"
    if mode == "other_platform": env["identified_author_work"]["url"] = "https://novelpia.com/novel/222360"
    if mode == "binding_name": env["identified_author_work"]["name"] = "다른이"
    if mode == "binding_missing_field": env["identified_author_work"].pop("title")
    if mode == "binding_digest_shape": env["identified_author_work"]["source_sha256"] = "invalid"
    row["analysis_result"]["batch_context_learning_envelope"] = env
    typed = sut["llm_batch.domain.models"].PickvelOutputItemV2.model_validate(row["analysis_result"])
    row["analysis_result"]["batch_context_learning_envelope"] = typed.model_dump(mode="json")["batch_context_learning_envelope"]
    ledger = sut["llm_batch.ledger.publication_commit"]
    before = canonical(row)
    scope = ledger.build_publication_scope_descriptor(input_file_sha256=hashlib.sha256(before.encode()).hexdigest(),
        post_ids=[row["post_id"]], config_hash="author-work-consumer-control", release_fingerprint="synthetic-author-channel")
    registry = ledger.PublicationCommitRegistry(tmp_path / "control.jsonl", scope_descriptor=scope, create_new=True)
    receipt, created = ledger.commit_publication_result(row, registry=registry, attempt_run_id="author-work-control", input_index=1, post_id=row["post_id"])
    assert created and receipt.publish_allowed is True
    wal_path = tmp_path / 'control.jsonl'
    wal_before = wal_path.read_bytes()
    reopened = ledger.PublicationCommitRegistry(wal_path, scope_descriptor=scope, create_new=False)
    stored = reopened.result(row['post_id'])
    receipts = [item for item in reopened.receipts() if item.post_id == row['post_id']]
    assert len(receipts) == 1 and receipts[0].to_dict() == receipt.to_dict()
    receipt = receipts[0]
    ledger.validate_publication_result_commit(stored, receipt, expected_scope_id=scope.publication_scope_id,
        expected_input_index=1, expected_post_id=row['post_id'])
    assert canonical(stored) == before and wal_path.read_bytes() == wal_before
    memory = sut["llm_batch.domain.batch_context"].BatchContextMemory(enabled=True)
    assert sut["expert_main"]._learn_batch_context_from_canonical_publication(memory, stored, receipt, created=created) is True
    expected = {memory._normalize("바람의")} if mode in {"same_pair", "same_munpia_id_modern_url"} else set()
    assert set(memory.resolved_authors) == expected
    assert canonical(row) == before
    assert canonical(stored) == before and wal_path.read_bytes() == wal_before
