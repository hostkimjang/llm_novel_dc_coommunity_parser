"""공유 NSFW carrier의 URL schema를 surface/general guard에서도 그대로 검산한다.

ROOT의 종료·격리 tree·audit gate 아래에서만 실행한다. 빈 이웃 후보는 이 파일에서 수리하지 않는다.
"""
from copy import deepcopy
import hashlib
from importlib import import_module
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).parent / 'fixtures/nsfw_carrier_consumers_v2/manifest.json'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


@pytest.fixture(scope='module')
def support():
    raw = FIXTURE.read_bytes()
    manifest = json.loads(raw)
    support_before = {}
    for rel, digest in manifest['support_sha256'].items():
        support_before[rel] = (ROOT / rel).read_bytes()
        if rel.startswith('tests/fixtures/'):
            assert hashlib.sha256(support_before[rel]).hexdigest() == digest
        else:
            assert rel.startswith('tests/') and rel.endswith('.py')
    surface = import_module('test_source_bound_surface_title_state')
    general = import_module('test_source_general_context_state')
    for module in (surface, general):
        assert Path(module.__file__).resolve().parent == ROOT / 'tests'
    pipeline = import_module('llm_batch.agentic_pipeline')
    assert Path(pipeline.__file__).resolve() == ROOT / 'src/llm_batch/agentic_pipeline.py'
    yield SimpleNamespace(surface=surface, general=general)
    assert FIXTURE.read_bytes() == raw
    for rel, digest in manifest['support_sha256'].items():
        assert (ROOT / rel).read_bytes() == support_before[rel]
        if rel.startswith('tests/fixtures/'):
            assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == digest


def original_context(support, tmp_path, route, index):
    if route == 'surface':
        return support.surface.context(tmp_path)
    return support.general.context(tmp_path, index)


def inputs(support, pipe, ctx, route, index):
    if route == 'surface':
        return pipe._surface_title_anchor_inputs(ctx, *support.surface.inputs(ctx))
    return pipe._general_context_state_inputs(ctx, 'nonwork_comparison' if index == 55 else 'genre_context')


def binding(support, pipe, ctx, route, index):
    if route == 'surface':
        return pipe._source_bound_surface_title_anchor(ctx, *support.surface.inputs(ctx))
    return pipe._source_bound_general_context_state(ctx, 'nonwork_comparison' if index == 55 else 'genre_context')


def immutable(ctx):
    return canonical({'post': ctx.post_data, 'comments': ctx.comments, 'experts': ctx.expert_outputs,
        'carrier': ctx._source_bound_nsfw_original_carrier, 'originals': ctx._final_source_original_inputs,
        'comment_refs': ctx._final_source_original_comment_refs})


@pytest.mark.parametrize('route,index', [('surface', 55), ('general', 55), ('general', 70), ('general', 77)])
def test_original_positive_inputs_keep_complete_url_carrier_without_rewriting(support, tmp_path, route, index):
    pipe, ctx, _ = original_context(support, tmp_path, route, index)
    before = immutable(ctx)
    original = json.loads(ctx._source_bound_nsfw_original_carrier)
    assert original['content_blocks'] and all('url' in b and b['url'] is None for b in original['content_blocks'])
    evidence = inputs(support, pipe, ctx, route, index)
    assert evidence is not None
    source = json.loads(evidence['facts'])['source']
    assert source == original
    assert immutable(ctx) == before


@pytest.mark.parametrize('route,index', [('surface', 55), ('general', 55), ('general', 70), ('general', 77)])
@pytest.mark.parametrize('mutation', ['url_string', 'url_empty', 'url_missing', 'url_false'])
def test_captured_original_url_cannot_be_changed_or_removed(support, tmp_path, route, index, mutation):
    pipe, ctx, _ = original_context(support, tmp_path, route, index)
    assert inputs(support, pipe, ctx, route, index) is not None
    post_before = canonical(ctx.post_data)
    carrier = json.loads(ctx._source_bound_nsfw_original_carrier)
    if mutation == 'url_string': carrier['content_blocks'][0]['url'] = 'https://example.invalid/changed-source'
    elif mutation == 'url_empty': carrier['content_blocks'][0]['url'] = ''
    elif mutation == 'url_missing': carrier['content_blocks'][0].pop('url')
    elif mutation == 'url_false': carrier['content_blocks'][0]['url'] = False
    ctx._source_bound_nsfw_original_carrier = canonical(carrier).decode()
    changed = ctx._source_bound_nsfw_original_carrier
    assert inputs(support, pipe, ctx, route, index) is None
    assert canonical(ctx.post_data) == post_before and ctx._source_bound_nsfw_original_carrier == changed


@pytest.mark.parametrize('route,index', [('surface', 55), ('general', 55), ('general', 70), ('general', 77)])
@pytest.mark.parametrize('field', ['url', 'image_url', 'src'])
def test_live_source_url_and_alternate_url_fields_remain_disallowed(support, tmp_path, route, index, field):
    pipe, ctx, _ = original_context(support, tmp_path, route, index)
    assert inputs(support, pipe, ctx, route, index) is not None
    carrier_before = ctx._source_bound_nsfw_original_carrier
    ctx.post_data['content_blocks'][0][field] = 'https://example.invalid/added-source'
    source_before = canonical(ctx.post_data)
    assert inputs(support, pipe, ctx, route, index) is None
    assert ctx._source_bound_nsfw_original_carrier == carrier_before and canonical(ctx.post_data) == source_before


@pytest.mark.parametrize('route,index', [('surface', 55), ('general', 55), ('general', 70), ('general', 77)])
@pytest.mark.parametrize('location', ['carrier', 'live'])
def test_existing_binding_callback_revalidates_url_after_initial_admission(support, tmp_path, route, index, location):
    pipe, ctx, _ = original_context(support, tmp_path, route, index)
    evidence = binding(support, pipe, ctx, route, index)
    assert evidence is not None and evidence['verify']() is True
    assert evidence['publication_authority'] is False
    if location == 'carrier':
        carrier = json.loads(ctx._source_bound_nsfw_original_carrier)
        carrier['content_blocks'][0]['url'] = 'https://example.invalid/changed-after-binding'
        ctx._source_bound_nsfw_original_carrier = canonical(carrier).decode()
    else:
        ctx.post_data['content_blocks'][0]['url'] = 'https://example.invalid/changed-after-binding'
    before = immutable(ctx)
    assert evidence['verify']() is False
    assert immutable(ctx) == before
