"""합성 transport로 기존 검색 정책과 별칭 본문 검증을 함께 확인한다. ROOT 실행 대기."""
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.experts.orchestrator import ConversationContext, ExpertType


TITLE = '유리성의 항해자'
ALIAS = '유항자'
AUTHOR = '담청'
DETAIL = 'https://novelpia.com/novel/987654321'
SOURCE = 'https://reader.example.org/reviews/glass-voyager'
PURPOSE = 'candidate_alias_relation_source_probe'
QUERY = f'"{ALIAS}" "{TITLE}" "{AUTHOR}"'


class NoExternal:
    def __init__(self):
        self.attempts = []

    def _deny(self, *args, **kwargs):
        self.attempts.append((args, kwargs))
        raise AssertionError('실제 모델·검색·fetch 호출 금지')

    search = fetch = chat = _stream_chat_http = _deny


def _transport(url):
    return {'requested_url': url, 'final_url': url, 'method': 'httpx', 'status_code': 200}


def _case(tmp_path, monkeypatch, *, denied=False, body=None):
    external = NoExternal()
    pipeline = AgenticPipeline(llm=external, mcp=external, output_dir=tmp_path, max_iterations=2)
    # 실제 정책은 켜 둔다. 수치 환경은 이 시험의 허용 범위를 명시한다.
    monkeypatch.setenv('LLM_ENABLE_LATE_TOTAL_SEARCH_BUDGET', '1')
    monkeypatch.setenv('LLM_ENABLE_LATE_SEARCH_BUDGET', '1')
    monkeypatch.setenv('LLM_LATE_TOTAL_SEARCH_MIN_ITERATION', '3')
    monkeypatch.setenv('PIPELINE_SEARCH_CONCURRENCY', '1')
    for name in ('LLM_MAX_TOTAL_SEARCH_QUERIES_PER_POST', 'LLM_MAX_TOTAL_SEARCH_QUERIES_CORE_FAST',
                 'LLM_MAX_TOTAL_SEARCH_QUERIES_UNCERTAIN', 'LLM_MAX_TOTAL_SEARCH_QUERIES_ADJACENT',
                 'LLM_MAX_TOTAL_SEARCH_QUERIES_ADJACENT_CHEAP', 'LLM_MAX_TOTAL_SEARCH_QUERIES_QUARANTINE',
                 'LLM_MAX_TOTAL_SEARCH_QUERIES_SHORT_ALIAS_BRIDGE', 'LLM_MAX_TOTAL_SEARCH_QUERIES_DEEP_RESEARCH',
                 'LLM_MAX_TOTAL_SEARCH_QUERIES_MEMORY_QUERY'):
        monkeypatch.setenv(name, '18')
    post = {'post_id': 17, 'title': '점심 먹고 산책함' if denied else f'{ALIAS} 이번 화 읽었음',
            'content_blocks': [{'type': 'text', 'text': '그냥 날씨 이야기' if denied else '소설 전개가 재미있다.'}]}
    ctx = ConversationContext(post_id=17, post_data=deepcopy(post), comments=[])
    ctx.set_expert_output(ExpertType.GATEKEEPER, {'post_type': 'noise' if denied else 'work_discussion',
        'detected_entities': {'possible_titles': [] if denied else [TITLE]},
        'context_clues': {} if denied else {'has_episode_reference': True}})
    if denied:
        ctx.discourse_warning = 'semantic_seed_review(no_work_anchor)'
        ctx.set_expert_output(ExpertType.DISCOURSE, {'discourse_analysis': {
            'intent': 'community_banter', 'target_kind': 'none', 'title_novel_terms': [],
            'semantic_seed_review': {'is_specific_work_discussion': False},
            'warnings': ['semantic_seed_review_specific_work_denied']}})
    ctx.fetched_page_info = [{'url': DETAIL, 'fetch_transport_provenance': _transport(DETAIL),
        'structured_info': {'title': TITLE, 'author': AUTHOR, 'page_type': 'novel_page', 'content_status': 'active'}}]
    row = {'title': f'{TITLE} 별칭 소개', 'url': SOURCE,
           'content': f'{TITLE}의 약칭은 {ALIAS}. 작가 {AUTHOR}의 소설이다.'}
    source_body = body if body is not None else row['content']
    calls, fetches = [], []

    def search(query, purpose='', **kwargs):
        calls.append((query, purpose, kwargs))
        return [deepcopy(row)], {'raw_total': 1, 'total': 1, 'enumeration_finished': True,
                                'error_status': 'NONE', 'attempts': 1, 'degraded': False}

    def fetch(url):
        fetches.append(url)
        assert url == SOURCE
        return {'url': url, 'text': source_body, 'fetch_transport_provenance': _transport(url)}, {}

    monkeypatch.setattr(pipeline, '_search_with_meta', search)
    monkeypatch.setattr(pipeline, '_fetch_with_meta', fetch)
    record = Mock(wraps=ctx.record_search_outcome)
    monkeypatch.setattr(ctx, 'record_search_outcome', record)
    return pipeline, ctx, external, calls, fetches, record, post


def _probe(pipeline, ctx, alias=ALIAS):
    return pipeline._probe_fresh_candidate_alias_relation(ctx, title=TITLE, alias=alias, exact_urls=[DETAIL])


def test_alias_probe_uses_guarded_executor_and_preserves_bound_body_receipt(tmp_path, monkeypatch):
    pipeline, ctx, external, calls, fetches, record, post = _case(tmp_path, monkeypatch)
    expert_before = deepcopy(ctx.expert_outputs)
    assert _probe(pipeline, ctx) == 'fetched_source_alias_assertion'
    assert calls == [(QUERY, PURPOSE, {})]
    assert fetches == [SOURCE]
    assert record.call_count == 1  # executor만 기록하고 기존 ad-hoc 기록을 중복 호출하지 않는다.
    assert QUERY in ctx.executed_queries
    receipt = ctx._fresh_candidate_alias_relation_receipts[0]
    assert receipt['candidate_title'] == TITLE and receipt['candidate_url'] == DETAIL
    assert receipt['alias'] == ALIAS and receipt['source_url'] == SOURCE
    assert receipt['body_sha256'] == hashlib.sha256(receipt['source_body'].encode('utf8')).hexdigest()
    assert pipeline._trusted_non_llm_alias_official_detail_binding_source(
        ctx, title=TITLE, alias=ALIAS, exact_urls=[DETAIL]) == 'fetched_source_alias_assertion'
    assert ctx.post_data == post and ctx.expert_outputs == expert_before
    assert external.attempts == []


def test_semantic_no_work_denial_never_falls_back_to_raw_search(tmp_path, monkeypatch):
    pipeline, ctx, external, calls, fetches, record, post = _case(tmp_path, monkeypatch, denied=True)
    assert pipeline.orchestrator._title_search_intent_permit(ctx)[0] is False
    assert _probe(pipeline, ctx) == ''
    assert calls == [] and fetches == [] and record.call_count == 0
    assert not getattr(ctx, '_fresh_candidate_alias_relation_receipts', [])
    assert ctx.post_data == post and external.attempts == []


def test_alias_probe_obeys_late_budget_even_before_minimum_iteration(tmp_path, monkeypatch):
    pipeline, ctx, external, calls, fetches, record, _ = _case(tmp_path, monkeypatch)
    ctx.iteration = 0
    ctx.executed_queries = [f'prior query {i}' for i in range(18)]
    request = [{'query': QUERY, 'purpose': PURPOSE}]
    assert pipeline.orchestrator._is_late_search_expansion_batch(request) is True
    assert _probe(pipeline, ctx) == ''
    assert calls == [] and fetches == [] and record.call_count == 0
    assert ctx.search_stop_reason == 'late_total_search_budget_exhausted'
    assert external.attempts == []


def test_alias_probe_keeps_repeat_and_two_pair_bound(tmp_path, monkeypatch):
    pipeline, ctx, external, calls, fetches, _, _ = _case(tmp_path, monkeypatch, body='관계가 없는 본문이다.')
    assert _probe(pipeline, ctx) == ''
    assert _probe(pipeline, ctx) == ''
    assert len(calls) == 1
    assert _probe(pipeline, ctx, '유리항') == ''
    assert len(calls) == 2
    assert _probe(pipeline, ctx, '유성항') == ''
    assert len(calls) == 2 and len(fetches) == 2
    assert len(ctx._fresh_candidate_alias_relation_attempted) == 2
    assert external.attempts == []


@pytest.mark.parametrize('fault', ['snippet_only', 'official_redirect', 'source_redirect', 'official_mismatch'])
def test_alias_probe_keeps_transport_and_source_assertion_rejection(tmp_path, monkeypatch, fault):
    body = '본문에는 별칭 관계가 없다.' if fault == 'snippet_only' else None
    pipeline, ctx, external, calls, fetches, _, _ = _case(tmp_path, monkeypatch, body=body)
    if fault == 'official_redirect':
        ctx.fetched_page_info[0]['fetch_transport_provenance']['final_url'] = DETAIL + '?redirect=1'
    elif fault == 'official_mismatch':
        ctx.fetched_page_info[0]['structured_info']['title'] = '서리 탑의 기록자'
    elif fault == 'source_redirect':
        original = pipeline._fetch_with_meta
        def redirected(url):
            result, meta = original(url)
            result['fetch_transport_provenance']['final_url'] = SOURCE + '/other'
            return result, meta
        monkeypatch.setattr(pipeline, '_fetch_with_meta', redirected)
    assert _probe(pipeline, ctx) == ''
    assert not getattr(ctx, '_fresh_candidate_alias_relation_receipts', [])
    if fault.startswith('official_'):
        assert calls == [] and fetches == []
    else:
        assert calls == [(QUERY, PURPOSE, {})] and fetches == [SOURCE]
    assert external.attempts == []


def test_bounded_executor_drops_injected_queries_without_disabling_existing_filters(tmp_path, monkeypatch):
    pipeline, ctx, external, calls, _, _, _ = _case(tmp_path, monkeypatch)
    orch = pipeline.orchestrator
    original = orch._inject_title_led_official_detail_search_requests
    def injected(context, requests, **kwargs):
        return [*original(context, requests, **kwargs), {'query': '추가 작품 탐색', 'purpose': 'official_title_verify'}]
    monkeypatch.setattr(orch, '_inject_title_led_official_detail_search_requests', injected)
    intent_filter = Mock(wraps=orch._prune_title_search_requests_for_intent_permit)
    monkeypatch.setattr(orch, '_prune_title_search_requests_for_intent_permit', intent_filter)
    assert _probe(pipeline, ctx) == 'fetched_source_alias_assertion'
    assert intent_filter.call_count == 1
    assert calls == [(QUERY, PURPOSE, {})]
    assert external.attempts == []


def test_bounded_executor_does_not_replace_denied_query_with_source_probe(tmp_path, monkeypatch):
    pipeline, ctx, external, calls, fetches, _, _ = _case(tmp_path, monkeypatch, denied=True)
    fallback = Mock(side_effect=AssertionError('거절된 bounded 요청의 대체 질의 생성 금지'))
    monkeypatch.setattr('llm_batch.experts.orchestrator.source_anticipation_probe', fallback)
    assert _probe(pipeline, ctx) == ''
    assert fallback.call_count == 0
    assert calls == [] and fetches == [] and external.attempts == []


def test_default_executor_still_allows_normal_request_expansion(tmp_path, monkeypatch):
    pipeline, ctx, external, calls, _, _, _ = _case(tmp_path, monkeypatch)
    orch = pipeline.orchestrator
    extra_query = '"별빛 숲의 기록자" "별숲기"'
    # 생성기 경계만 고정한다. 실제 intent·예산·중복·실행 loop는 그대로 사용한다.
    def injected(_context, requests, **_kwargs):
        return [*requests, {'query': extra_query, 'purpose': PURPOSE, 'priority': 2}]
    monkeypatch.setattr(orch, '_inject_title_led_official_detail_search_requests', injected)
    orch._execute_searches([{'query': QUERY, 'purpose': PURPOSE, 'priority': 1}], ctx.post_id, ctx=ctx)
    assert [query for query, _purpose, _kwargs in calls] == [QUERY, extra_query]
    assert external.attempts == []
