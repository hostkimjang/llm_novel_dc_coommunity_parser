"""빈 이웃 표준형의 실제 builder/직렬화/guard 대조. ROOT 격리 실행 전용."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import PostInput
from llm_batch.experts.orchestrator import ConversationContext, ExpertType
import test_source_bound_surface_title_state as surface
import test_source_general_context_state as general

FIXTURES = Path(__file__).parent / 'fixtures/empty_neighbor_v1'
ROOT = Path(__file__).resolve().parents[1]
EMPTY = {'repeated_terms': [], 'repeated_authors': [], 'nearby_titles': [], 'image_dense_neighbors': 0}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


@pytest.fixture(scope='module')
def fixed():
    manifest = json.loads((FIXTURES / 'manifest.json').read_bytes())
    for name, pin in manifest['files_sha256'].items():
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == pin
    for name, pin in manifest['support_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == pin
    data = json.loads((FIXTURES / 'source80.json').read_bytes())
    before = canonical(data)
    for row in data['rows']:
        assert type(row['post_id']) is int
        assert hashlib.sha256(canonical({'post': row['source_post'], 'comments': row['source_comments']})).hexdigest() == row['source_canonical_sha256']
    yield data
    assert canonical(data) == before
    for name, pin in manifest['files_sha256'].items():
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == pin


def original_posts(fixed):
    return [PostInput(**deepcopy(r['source_post']), comments=deepcopy(r['source_comments'])) for r in fixed['rows']]


def old_context(tmp_path, route):
    if route == 'surface':
        pipe, ctx, fixture = surface.context(tmp_path)
        record = fixture['records']['current']
    else:
        pipe, ctx, record = general.context(tmp_path, 55)
    post = PostInput(**deepcopy(record['post']), comments=deepcopy(record['comments']))
    return pipe, ctx, post


def guard(pipe, ctx, route):
    if route == 'surface':
        vr, fd = surface.inputs(ctx)
        return pipe._surface_title_anchor_inputs(ctx, vr, fd)
    return pipe._general_context_state_inputs(ctx, 'nonwork_comparison')


@pytest.mark.parametrize('route', ['surface', 'general'])
def test_actual_source80_index_and_post_conversion_preserve_old_qualified_boundary(fixed, tmp_path, route):
    posts = original_posts(fixed)
    raw_before = canonical([p.model_dump(mode='json') for p in posts])
    index = AgenticPipeline.build_recent_post_index(posts)
    assert len(index) == 80
    pipe, ctx, post = old_context(tmp_path, route)
    assert guard(pipe, ctx, route) is not None
    experts_before = canonical(ctx.expert_outputs)
    pipe.recent_post_index = index
    converted = pipe._post_to_dict(post)
    assert converted['neighbor_hints'] == EMPTY and bool(converted['neighbor_hints']) is True
    ctx.post_data = converted
    assert guard(pipe, ctx, route) is not None
    assert canonical(ctx.expert_outputs) == experts_before
    assert canonical([p.model_dump(mode='json') for p in posts]) == raw_before


@pytest.mark.parametrize('route', ['surface', 'general'])
@pytest.mark.parametrize('kind', ['unknown_key', 'missing_key', 'tuple_list', 'bool_count', 'float_count',
    'string_count', 'null', 'empty_list', 'string', 'real_term', 'real_author', 'real_title', 'image_count'])
def test_unknown_malformed_or_nonempty_neighbor_metadata_stays_blocked(tmp_path, route, kind):
    pipe, ctx, _ = old_context(tmp_path, route)
    hints = deepcopy(EMPTY)
    if kind == 'unknown_key': hints['other'] = []
    elif kind == 'missing_key': hints.pop('nearby_titles')
    elif kind == 'tuple_list': hints['nearby_titles'] = ()
    elif kind == 'bool_count': hints['image_dense_neighbors'] = False
    elif kind == 'float_count': hints['image_dense_neighbors'] = 0.0
    elif kind == 'string_count': hints['image_dense_neighbors'] = '0'
    elif kind == 'null': hints = None
    elif kind == 'empty_list': hints = []
    elif kind == 'string': hints = ''
    elif kind == 'real_term': hints['repeated_terms'] = ['항해']
    elif kind == 'real_author': hints['repeated_authors'] = ['별바다']
    elif kind == 'real_title': hints['nearby_titles'] = ['달빛 항로']
    elif kind == 'image_count': hints['image_dense_neighbors'] = 1
    before = canonical(ctx.expert_outputs)
    ctx.post_data['neighbor_hints'] = hints
    assert guard(pipe, ctx, route) is None
    assert canonical(ctx.expert_outputs) == before


@pytest.mark.parametrize('route', ['surface', 'general'])
def test_real_builder_neighbor_remains_additional_context(fixed, tmp_path, route):
    pipe, ctx, post = old_context(tmp_path, route)
    neighbor = post.model_dump(mode='json')
    neighbor['post_id'] = post.post_id + 100000000
    neighbor['content_blocks'] = [{'type': 'image', 'url': 'https://example.invalid/neighbor.png', 'text': None}]
    index = AgenticPipeline.build_recent_post_index([post, PostInput(**neighbor)])
    assert index[post.post_id]['image_dense_neighbors'] == 1
    pipe.recent_post_index = index
    ctx.post_data = pipe._post_to_dict(post)
    assert guard(pipe, ctx, route) is None


@pytest.mark.parametrize('index1', [55, 57])
def test_current_saved_pending_and_competition_are_not_rewritten(fixed, tmp_path, index1):
    evidence = json.loads((FIXTURES / 'scope55_57_evidence.json').read_bytes())
    record = next(row for row in evidence['rows'] if row['input_index1'] == index1)
    posts = original_posts(fixed)
    post = next(p for p in posts if p.post_id == record['post_id'])
    class ExternalAttempt(BaseException):
        pass
    class NoExternal:
        def __getattr__(self, name):
            def reject(*args, **kwargs): raise ExternalAttempt(name)
            return reject
    pipe = AgenticPipeline(llm=NoExternal(), mcp=NoExternal(), output_dir=tmp_path,
        max_iterations=1, parallel_count=12, native_recovery=True,
        recent_post_index=AgenticPipeline.build_recent_post_index(posts))
    ctx = ConversationContext(post_id=post.post_id, post_data=pipe._post_to_dict(post), comments=pipe._extract_comments(post))
    ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs = tuple(post.comments)
    ctx._source_bound_nsfw_original_carrier = pipe._capture_source_bound_nsfw_carrier(post)
    for block in record['expert_stream']:
        assert hashlib.sha256(canonical(block['value'])).hexdigest() == block['value_canonical_sha256']
        ctx.set_expert_output(ExpertType(block['expert']), deepcopy(block['value']))
    decoder = ctx.get_expert_output(ExpertType.DECODER)
    assert decoder['needs_verification'] is True
    before = canonical(ctx.expert_outputs)
    assert ctx.post_data['neighbor_hints'] == EMPTY
    assert pipe._has_additional_neighbor_context(ctx.post_data) is False
    if index1 == 55:
        vr, fd = surface.inputs(ctx)
        assert pipe._surface_title_anchor_inputs(ctx, vr, fd) is None
        assert pipe._general_context_state_inputs(ctx, 'nonwork_comparison') is None
    # 57 검증을 수행/완료했다고 주장하지 않는다. 이 후보는 pending 상태를 전혀 고치지 않는다.
    assert canonical(ctx.expert_outputs) == before
