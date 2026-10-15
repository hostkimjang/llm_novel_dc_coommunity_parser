"""저자 추출→실제 힌트→envelope·main 소비 회귀. ROOT의 격리 오프라인 묶음 전용."""
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
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


@pytest.fixture(scope="module")
def sut():
    names = ["llm_batch.grounding.munpia_author_byline", "llm_batch.mcp_bridge.server",
             "llm_batch.agentic_pipeline", "llm_batch.experts.orchestrator", "llm_batch.domain.models",
             "llm_batch.domain.batch_context", "llm_batch.ledger.publication_commit", "expert_main"]
    return {name: importlib.import_module(name) for name in names}


@pytest.fixture(scope="module")
def facts():
    paths = [FIXTURES / "fixture.json", FIXTURES / "url_fetch_cache.json", FIXTURES / "munpia_publish_control.json"]
    original = {p: p.read_bytes() for p in paths}
    values = {p.name: json.loads(raw) for p, raw in original.items()}
    before = canonical(values)
    yield values
    assert canonical(values) == before
    assert all(p.read_bytes() == raw for p, raw in original.items())


def html(name, *, navigation=True):
    return ('<html><head><title>' + TITLE + ' - 문피아 웹소설</title></head><body><h1>'
            + TITLE + '</h1><div>글 ' + name + '</div>'
            + ('<aside>검미성 작가 작가의 서재 가기 작가의 다른 작품</aside>' if navigation else '')
            + '</body></html>')


def hint(sut, name, *, title=TITLE, url=URL):
    text = '# ' + title + '\n글\n' + name + '\n총12화\n작품소개\n밤바다 이야기'
    proof = sut['llm_batch.grounding.munpia_author_byline'].byline_evidence(url, title, text, kind='rendered_text')
    assert proof['status'] == 'VERIFIED'
    return {'name': name, 'source': 'url_fetch', 'url': url, 'author_byline': proof}


def envelope(sut, hints):
    o = sut['llm_batch.experts.orchestrator']
    ctx = o.ConversationContext(post_id=1, post_data={}, comments=[])
    ctx.snippet_hints = {'author_hints': deepcopy(hints)}
    before = canonical(ctx.snippet_hints)
    pipe = object.__new__(sut['llm_batch.agentic_pipeline'].AgenticPipeline)
    result = pipe._build_batch_context_learning_envelope(ctx)
    assert canonical(ctx.snippet_hints) == before
    return result


@pytest.mark.parametrize('name', ['별바다', '바람의', '작가의', 'J. R. River', '밤하늘_7'])
def test_explicit_byline_preserves_names_in_html_rendered_and_envelope(sut, name):
    parsed = sut['llm_batch.mcp_bridge.server']._extract_novel_platform_info(html(name), URL)
    assert parsed['author'] == name
    helper = sut['llm_batch.grounding.munpia_author_byline']
    assert helper.valid_byline_evidence(parsed['author_byline'])
    assert envelope(sut, [hint(sut, name)])['identified_author'] == name


@pytest.mark.parametrize('label', ['작가:', '저자：', '글'])
def test_first_adjacent_label_is_not_overwritten_by_navigation(sut, label):
    raw = html('바람의').replace('글 바람의', label + ' 바람의')
    parsed = sut['llm_batch.mcp_bridge.server']._extract_novel_platform_info(raw, URL)
    assert parsed['author'] == '바람의'


@pytest.mark.parametrize('body', [
    '<aside>별바다 작가 작가의 서재 가기</aside>',
    '<nav>작가의 서재 가기 작가의 다른 작품</nav>',
    '<div>작가의 서재 가기</div>',
    '<p>검미성 작가 작가의 다른 작품</p>',
    '<p>줄거리입니다.</p><div>글 잘못된저자</div>',
    '<script>글 잘못된저자</script>',
])
def test_navigation_or_later_nonbyline_does_not_become_author(sut, body):
    raw = '<html><head><title>' + TITLE + ' - 문피아 웹소설</title></head><body><h1>' + TITLE + '</h1>' + body + '</body></html>'
    parsed = sut['llm_batch.mcp_bridge.server']._extract_novel_platform_info(raw, URL)
    assert parsed.get('author') is None
    assert parsed['author_byline']['status'] == 'NO_EXPLICIT_BYLINE'


def test_two_explicit_conflicting_bylines_hold_and_do_not_fall_back_to_navigation(sut):
    raw = html('별바다', navigation=False).replace('</div>', '</div><div>작가: 다른이</div>', 1)
    parsed = sut['llm_batch.mcp_bridge.server']._extract_novel_platform_info(raw, URL)
    assert parsed.get('author') is None and parsed['author_byline']['status'] == 'CONFLICT'
    helper = sut['llm_batch.grounding.munpia_author_byline']
    fetched = {'url': URL, 'text': '', 'structured_info': parsed}
    got = helper.qualify_legacy_munpia_fetch(URL, fetched)
    assert got['structured_info'].get('author') is None
    assert got['structured_info']['author_byline_observation']['status'] == 'CONFLICT'


@pytest.mark.parametrize('order', ['unbound_first', 'byline_first'])
def test_verified_byline_wins_over_unbound_first_hint_without_name_blacklist(sut, order):
    bad = {'name': '작가의', 'source': 'url_fetch'}
    good = hint(sut, '바람의')
    values = [bad, good] if order == 'unbound_first' else [good, bad]
    assert envelope(sut, values)['identified_author'] == '바람의'
    assert envelope(sut, [hint(sut, '작가의'), {'name': '다른이', 'source': 'llm_snippet'}])['identified_author'] == '작가의'


@pytest.mark.parametrize('mode', ['source', 'digest', 'name', 'url', 'competing_byline'])
def test_corrupted_or_competing_byline_cannot_use_first_hint_fallback(sut, mode):
    value = hint(sut, '바람의')
    values = [value, {'name': '작가의', 'source': 'url_fetch'}]
    if mode == 'source': value['author_byline']['source_text'] += ' 변조'
    if mode == 'digest': value['author_byline']['source_sha256'] = '0' * 64
    if mode == 'name': value['name'] = '작가의'
    if mode == 'url': value['url'] = 'https://novel.munpia.com/7777'
    if mode == 'competing_byline': values.append(hint(sut, '별바다'))
    assert envelope(sut, values)['identified_author'] is None


@pytest.mark.parametrize('mode', ['wrong_title', 'wrong_result_url', 'redirect', 'deleted', 'no_byline'])
def test_cached_author_requires_exact_page_title_and_live_byline_evidence(sut, facts, mode):
    cache = deepcopy(facts['url_fetch_cache.json']);result = cache['result'];url = cache['url']
    if mode == 'wrong_title': result['structured_info']['title'] = '다른 작품'
    if mode == 'wrong_result_url': result['url'] = 'https://novel.munpia.com/7777'
    if mode == 'redirect': result['final_url'] = 'https://example.invalid/elsewhere'
    if mode == 'deleted': result['structured_info']['content_status'] = 'deleted'
    if mode == 'no_byline': result['text'] = '작가의 서재 가기'
    before = canonical(result)
    got = sut['llm_batch.grounding.munpia_author_byline'].qualify_legacy_munpia_fetch(url, result)
    assert got['structured_info'].get('author') is None
    assert got['structured_info']['author_byline_observation']['original_author'] == '작가의'
    assert canonical(result) == before


def test_actual14_cache_read_and_real_enrichment_emit_correct_author_without_cache_write(sut, facts, tmp_path):
    attempts = []
    class ExternalAttemptBlocked(BaseException):
        pass
    class NoExternal:
        def __getattr__(self, name):
            def denied(*args, **kwargs):
                attempts.append(name)
                raise ExternalAttemptBlocked('AUTHOR_REPAIR_EXTERNAL_ATTEMPT:' + name)
            return denied
    raw = (FIXTURES / 'url_fetch_cache.json').read_bytes()
    cache = facts['url_fetch_cache.json'];P = sut['llm_batch.agentic_pipeline'].AgenticPipeline
    pipe = P(llm=NoExternal(), mcp=NoExternal(), output_dir=tmp_path, max_iterations=1,
             parallel_count=12, worker_id=0, native_recovery=True)
    pipe.enable_url_fetch_disk_cache = True
    pipe.url_fetch_cache_dir = tmp_path / 'cache';pipe.url_fetch_cache_dir.mkdir()
    copy_path = pipe.url_fetch_cache_dir / (hashlib.sha1(cache['url'].encode()).hexdigest() + '.json')
    copy_path.write_bytes(raw)
    fetched, meta = pipe._fetch_with_meta(cache['url'])
    fetched_before = canonical(fetched)
    assert meta['from_cache'] is True and fetched['structured_info']['author'] == '작가의'
    packet = facts['fixture.json']['packet14'];o = sut['llm_batch.experts.orchestrator']
    post = sut['llm_batch.domain.models'].PostInput(**deepcopy(packet['source_post']), comments=deepcopy(packet['source_comments']))
    ctx = o.ConversationContext(post_id=post.post_id, post_data=pipe._post_to_dict(post), comments=pipe._extract_comments(post))
    original_source = canonical([ctx.post_data, ctx.comments])
    orchestrator = o.Orchestrator(experts={}, search_fn=None, fetch_fn=pipe._fetch, max_iterations=1,
        parallel_count=12, page_cache_dir=tmp_path / 'pages', page_cache_enabled=False,
        monitor_enabled=False, fetch_concurrency=1)
    orchestrator._deep_search_enrich(ctx, [], [deepcopy(facts['fixture.json']['cache_lead_control'])],
                                    post_data=deepcopy(ctx.post_data), gatekeeper_result=None)
    author_hints = ctx.snippet_hints['author_hints']
    correct = [h for h in author_hints if h.get('name') == '검미성' and h.get('author_byline')]
    assert correct and all(h.get('name') != '작가의' for h in author_hints)
    assert pipe._build_batch_context_learning_envelope(ctx)['identified_author'] == '검미성'
    assert canonical([ctx.post_data, ctx.comments]) == original_source
    assert canonical(fetched) == fetched_before and copy_path.read_bytes() == raw
    assert attempts == []


def test_current_modern_munpia_author_extractor_contract_is_unchanged(sut):
    bridge = sut['llm_batch.mcp_bridge.server']
    modern = 'https://www.munpia.com/novel/detail/999992'
    assert bridge._MUNPIA_OFFICIAL_DETAIL_URL.fullmatch(modern)
    assert bridge._MUNPIA_OFFICIAL_DETAIL_URL.fullmatch(URL) is None
    raw = '<title>달빛 항로 - 문피아 웹소설</title><h1>달빛 항로</h1><h2>작가의</h2>'
    assert bridge._extract_novel_platform_info(raw, modern)['author'] == '작가의'


def test_other_author_hint_sources_keep_existing_order_without_munpia_proof(sut):
    assert envelope(sut, [{'name': '바람의', 'source': 'llm_term_role'}, {'name': '별바다', 'source': 'url_fetch'}])['identified_author'] == '바람의'


def test_original14_hold_receipt_remains_unchanged_and_does_not_learn(sut, facts):
    packet = facts['fixture.json']['packet14'];row = deepcopy(packet['checkpoint_result']);before = canonical(row)
    ledger = sut['llm_batch.ledger.publication_commit']
    receipt = ledger.PublicationDecisionCommit.from_dict(packet['publication_commit'])
    ledger.validate_publication_result_commit(row, receipt, expected_scope_id=packet['publication_scope_id'],
                                             expected_input_index=14, expected_post_id=packet['post_id'])
    memory = sut['llm_batch.domain.batch_context'].BatchContextMemory(enabled=True)
    assert sut['expert_main']._learn_batch_context_from_canonical_publication(memory, row, receipt, created=True) is False
    assert not memory.resolved_authors and canonical(row) == before


@pytest.mark.parametrize('name', ['별바다', '바람의', '작가의'])
def test_explicit_author_envelope_survives_typed_and_real_main_consumer_control(sut, facts, tmp_path, name):
    # 공개 identity는 실제 기존 양성, 저자 채널은 독립 합성 대조다.
    # 해당 실제 작품의 작가가 이 합성 필명이라는 의미 판정이 아니다.
    # v1의 무관 네이버 작품 대조는 보존된 v1에 남긴다. v2는 동일 문피아 작품 쌍으로 바로잡는다.
    row = deepcopy(facts['munpia_publish_control.json']['packet']['checkpoint_result'])
    selected_title = row['analysis_result']['identity']['novel_identity']['official_title']
    env = envelope(sut, [hint(sut, name, title=selected_title, url='https://novel.munpia.com/222360')])
    row['analysis_result']['batch_context_learning_envelope'] = env
    typed = sut['llm_batch.domain.models'].PickvelOutputItemV2.model_validate(row['analysis_result'])
    assert typed.model_dump(mode='json')['batch_context_learning_envelope'] == env
    ledger = sut['llm_batch.ledger.publication_commit'];before = canonical(row)
    scope = ledger.build_publication_scope_descriptor(input_file_sha256=hashlib.sha256(before).hexdigest(),
        post_ids=[row['post_id']], config_hash='author-byline-consumer-control', release_fingerprint='synthetic-channel-not-model')
    registry = ledger.PublicationCommitRegistry(tmp_path / 'control.jsonl', scope_descriptor=scope, create_new=True)
    receipt, created = ledger.commit_publication_result(row, registry=registry, attempt_run_id='author-control', input_index=1, post_id=row['post_id'])
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
    memory = sut['llm_batch.domain.batch_context'].BatchContextMemory(enabled=True)
    assert sut['expert_main']._learn_batch_context_from_canonical_publication(memory, stored, receipt, created=created) is True
    assert set(memory.resolved_authors) == {memory._normalize(name)}
    assert canonical(row) == before
    assert canonical(stored) == before and wal_path.read_bytes() == wal_before
