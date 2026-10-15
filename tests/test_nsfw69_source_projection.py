"""현재69/33의 source/native 기능 대조. 미완료 main/WAL을 대신하지 않는다."""
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

FIXTURES = Path(__file__).parent / 'fixtures/nsfw_source_projection_v1'
FIXTURE_SHA = '961bec1140fe45123aa10f550409a9638869883eec725995dd02922ba7f94704'
CONTROL_SHA = '7ed330c10e661dd21d1bac754539ba870555ca66e2fec82c744f278e2b129770'
SCOPE = 'SOURCE_PROJECTION_FUNCTION_CONTROL_NOT_FULL_CONTEXT_MAIN_WAL'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def typed_hold_identity_input(saved):
    """writer의 정확한 두-null 공개 HOLD 쌍만 typed None으로 옮긴다."""
    if not isinstance(saved, dict) or 'novel_identity' not in saved:
        raise ValueError('EXACT_WRITER_NULL_PAIR_REQUIRED')
    pair = saved['novel_identity']
    if (type(pair) is not dict or set(pair) != {'official_title', 'heretic_url'}
            or pair['official_title'] is not None or pair['heretic_url'] is not None
            or saved.get('title_resolution_allowed') is not False):
        raise ValueError('EXACT_WRITER_NULL_PAIR_REQUIRED')
    copied = deepcopy(saved)
    copied['novel_identity'] = None
    return copied


class ExternalAttempt(BaseException):
    pass


class NoExternal:
    def __init__(self, attempts, kind):
        self.attempts, self.kind = attempts, kind

    def __getattr__(self, name):
        def reject(*args, **kwargs):
            self.attempts.append({'kind': self.kind, 'method': name})
            raise ExternalAttempt('NSFW_SOURCE_PROJECTION_EXTERNAL_ATTEMPT:' + self.kind + '.' + name)
        return reject





@pytest.fixture(scope='module')
def facts():
    raw = (FIXTURES / 'saved_context.json').read_bytes()
    assert sha(raw) == FIXTURE_SHA
    data = json.loads(raw)
    for name in ('current33', 'current69'):
        record = data['records'][name]; packet = record['packet']
        assert type(packet['post_id']) is int
        assert sha(canonical({'post': packet['source_post'], 'comments': packet['source_comments']})) == packet['source_canonical_sha256']
        assert sha(canonical(packet['checkpoint_result'])) == packet['result_canonical_sha256']
        assert record['experts']['arbiter']['metadata_synthesis']['is_nsfw'] is False
        saved = packet['checkpoint_result']['analysis_result']['identity']
        converted = typed_hold_identity_input(saved)
        assert converted['novel_identity'] is None
        assert {k: v for k, v in converted.items() if k != 'novel_identity'} == {
            k: v for k, v in saved.items() if k != 'novel_identity'}
        # 변환 범위의 음성 대조는 fixture 계약 검산이다. 원형 19개 nodeid는 그대로 둔다.
        invalid_pairs = [None, {}, {'official_title': None}, {'heretic_url': None},
            {'official_title': None, 'heretic_url': None, 'confidence': 'Low'},
            {'official_title': '', 'heretic_url': None},
            {'official_title': None, 'heretic_url': 'https://example.invalid/1'},
            {'official_title': False, 'heretic_url': None}]
        for pair in invalid_pairs:
            invalid = deepcopy(saved); invalid['novel_identity'] = pair
            with pytest.raises(ValueError, match='EXACT_WRITER_NULL_PAIR_REQUIRED'):
                typed_hold_identity_input(invalid)
        missing = deepcopy(saved); missing.pop('novel_identity')
        with pytest.raises(ValueError, match='EXACT_WRITER_NULL_PAIR_REQUIRED'):
            typed_hold_identity_input(missing)
        allowed = deepcopy(saved); allowed['title_resolution_allowed'] = True
        with pytest.raises(ValueError, match='EXACT_WRITER_NULL_PAIR_REQUIRED'):
            typed_hold_identity_input(allowed)
    before = canonical(data)
    yield data
    assert canonical(data) == before and (FIXTURES / 'saved_context.json').read_bytes() == raw


@pytest.fixture(scope='module')
def sut(facts):
    # 원형 진단 계약 파일은 불변 자료로만 보존한다. 과거 런/제품 지문은 요구하지 않는다.
    contract_path = FIXTURES / 'execution_contract.json'
    contract_raw = contract_path.read_bytes()
    assert sha(contract_raw) == CONTROL_SHA
    tree = Path(__file__).resolve().parents[1]
    assert (tree / 'expert_main.py').is_file(), 'CURRENT_CHECKOUT_REQUIRED'
    names = ('llm_batch.agentic_pipeline', 'llm_batch.domain.models', 'llm_batch.experts.orchestrator')
    paths = {name: tree / ('src/' + name.replace('.', '/') + '.py') for name in names}
    before = {name: path.read_bytes() for name, path in paths.items()}
    active, violations = [True], []
    def audit(event, args):
        if active[0] and (event.startswith(('socket.connect', 'socket.getaddrinfo', 'subprocess.', 'os.spawn'))
                          or event in {'os.system', 'urllib.Request'}):
            violations.append(event)
            raise ExternalAttempt('NSFW_SOURCE_PROJECTION_NETWORK_PROCESS:' + event)
    sys.addaudithook(audit)
    sys.dont_write_bytecode = True
    modules = {}
    try:
        for name in names:
            module = importlib.import_module(name)
            assert Path(module.__file__).resolve() == paths[name].resolve()
            modules[name.rsplit('.', 1)[-1]] = module
        yield SimpleNamespace(**modules)
    finally:
        active[0] = False
        assert violations == []
        assert contract_path.read_bytes() == contract_raw
        assert all(path.read_bytes() == before[name] for name, path in paths.items())



def source_control(sut, facts, name, dest, *, external_derived=False):
    record = facts['records'][name]; packet = record['packet']; attempts = []
    post = sut.models.PostInput(**deepcopy(packet['source_post']), comments=deepcopy(packet['source_comments']))
    pipe = sut.agentic_pipeline.AgenticPipeline(llm=NoExternal(attempts, 'llm'), mcp=NoExternal(attempts, 'mcp'),
        output_dir=dest / 'pipeline', max_iterations=1, parallel_count=12, native_recovery=True)
    pipe.enable_url_fetch_disk_cache = False
    pipe._use_session_knowledge = False
    ctx = sut.orchestrator.ConversationContext(post_id=post.post_id, post_data=pipe._post_to_dict(post), comments=pipe._extract_comments(post))
    ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs = tuple(post.comments)
    ctx._source_bound_nsfw_original_carrier = pipe._capture_source_bound_nsfw_carrier(post)
    carrier = ctx._source_bound_nsfw_original_carrier
    for expert, value in record['experts'].items():
        ctx.set_expert_output(sut.orchestrator.ExpertType(expert), deepcopy(value))
    for key, value in record['observed_context_fields'].items():
        setattr(ctx, key, deepcopy(value))
    expert_before = canonical(ctx.expert_outputs)
    saved_identity = packet['checkpoint_result']['analysis_result']['identity']
    # 최종 저장 identity를 source 기능에 넣는 명시 대조다. 초기 runtime ctx였다고 주장하지 않는다.
    typed_input = typed_hold_identity_input(saved_identity)
    identity = sut.models.PickvelIdentity.model_validate(typed_input)
    before_pair = canonical(identity.model_dump(mode='json').get('novel_identity'))
    ctx.post_data['image_enrichment'] = deepcopy(saved_identity['image_evidence_catalog'])
    pipe.enable_ocr = packet['checkpoint_result']['run_meta']['execution_config']['settings']['ocr']['value']
    assert pipe.enable_ocr is True and saved_identity['ocr_enabled'] is True
    if external_derived:
        assert name == 'current33'
        item = ctx.post_data['image_enrichment'][0]
        text = facts['records']['current69']['packet']['source_comments'][0]['content']
        item.update(ocr_text=text, visual_summary=text, evidence_type='explicit_text')
    blocks_before = deepcopy(ctx.post_data['content_blocks'])
    pipe._inject_image_enrichment_blocks(ctx.post_data)
    assert len(ctx.post_data['content_blocks']) > len(blocks_before)
    assert any(b.get('type') == 'ocr_text' for b in ctx.post_data['content_blocks'])
    assert pipe._source_bound_nsfw_blocks_match(json.loads(carrier)['content_blocks'], ctx.post_data) is True
    source_before = canonical({'post': ctx.post_data, 'comments': ctx.comments, 'carrier': carrier})
    notes = (packet['checkpoint_result']['analysis_result'].get('analysis') or {}).get('notes')
    report = {'status': 'STARTED', 'scope': SCOPE, 'case': name,
        'source_canonical_sha256': packet['source_canonical_sha256'],
        'full_result_canonical_sha256': packet['result_canonical_sha256'],
        'identity_input_origin': 'EXACT_SAVED_FINAL_IDENTITY_EXPLICIT_FUNCTION_CONTROL_NOT_INITIAL_CONTEXT',
        'identity_representation_adapter': 'EXACT_TWO_NULL_WRITER_HOLD_PAIR_TO_TYPED_NONE_ONLY',
        'original_saved_public_pair': deepcopy(saved_identity['novel_identity']),
        'typed_public_pair': identity.model_dump(mode='json').get('novel_identity'),
        'confidence_or_publication_authority_injected': False,
        'image_argument_origin': 'SAVED_CATALOG_SAME_URL_DERIVATION_NOT_FULL_RUNTIME_ENRICHMENT',
        'external_derived_control': external_derived, 'source_carrier_sha256': sha(carrier.encode()),
        'full_context_main_wal_executed': False, 'prior_ten_incomplete_replaced': False,
        'human_gold': False, 'actual_run_causality_proven': False}
    try:
        _, verify_native = pipe._consume_final_source_context(ctx, identity, notes)
        assert callable(verify_native)
        native_verified = verify_native()  # 실제 반환 함수. true 상수/대역 함수를 넣지 않는다.
        assert type(native_verified) is bool
        report['native_callback_result'] = native_verified
        report['projection_call_count'] = ctx._final_source_projection_call_count
        report['projection_consumption'] = deepcopy(ctx._final_source_projection_consumption)
        assert native_verified is True, 'SOURCE_FUNCTION_CONTROL_NATIVE_NOT_VERIFIED'
        assert ctx._final_source_projection_call_count == 1
        assert ctx._final_source_projection_native.manifest.alignment == 'exact_enumeration'
        metadata = ctx.get_expert_output(sut.orchestrator.ExpertType.ARBITER)['metadata_synthesis']
        assert metadata['is_nsfw'] is False
        decision = pipe._source_bound_nsfw_decision(ctx, metadata, metadata['is_nsfw'], native_verified=native_verified)
        report['decision'] = decision
        assert decision['resolved_value'] is record['expected_nsfw']
        assert decision['assessment_status'] == record['expected_assessment']
        assert decision['status'] == record['expected_source_status']
        assert decision['arbiter_value'] is False and decision['publication_authority'] is False
        assert decision['source_carrier_sha256'] == sha(carrier.encode())
        assert canonical(ctx.expert_outputs) == expert_before
        assert canonical({'post': ctx.post_data, 'comments': ctx.comments, 'carrier': ctx._source_bound_nsfw_original_carrier}) == source_before
        assert canonical(identity.model_dump(mode='json').get('novel_identity')) == before_pair
        assert attempts == []
        report['status'] = 'PASS_SOURCE_PROJECTION_FUNCTION_CONTROL_ONLY'
        return SimpleNamespace(pipe=pipe, ctx=ctx, callback=verify_native, metadata=metadata, decision=decision,
                               carrier=carrier, expert_before=expert_before, attempts=attempts, report=report)
    except BaseException as error:
        report.update(status='INCOMPLETE_OR_FAILED_SOURCE_FUNCTION_CONTROL', exception_type=type(error).__name__, message=str(error))
        raise
    finally:
        report['external_attempts'] = attempts
        (dest / 'source_projection_observation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf8')


@pytest.mark.parametrize('name', ['current33', 'current69'])
def test_saved_source_normal_ocr_real_native_decision(sut, facts, tmp_path, name):
    control = source_control(sut, facts, name, tmp_path)
    if name == 'current69':
        assert control.decision['rule'] == 'DIRECT_COMMENT_SEXUAL_DESIRE_RESTRAINT_V1'
        evidence = control.decision['evidence']
        assert evidence and all(e['source_origin'] == 'comment' for e in evidence)
        raw_comment = facts['records'][name]['packet']['source_comments'][0]
        assert evidence[0]['comment_id'] == raw_comment['comment_id']
        assert evidence[0]['raw_text_sha256'] == sha(raw_comment['content'].encode())
    else:
        assert control.decision['evidence'] == [] and control.decision['resolved_value'] is False


@pytest.mark.parametrize('name', ['current33', 'current69'])
@pytest.mark.parametrize('mutation', ['title', 'body', 'image_url', 'raw_comment', 'selected_comment', 'post_id_type', 'derived_type', 'block_order'])
def test_bound_source_mutation_cannot_keep_positive_proof(sut, facts, tmp_path, name, mutation):
    c = source_control(sut, facts, name, tmp_path)
    if mutation == 'title': c.ctx.post_data['title'] += ' 변조'
    elif mutation == 'body': next(b for b in c.ctx.post_data['content_blocks'] if b['type'] == 'text')['text'] += ' 변조'
    elif mutation == 'image_url': next(b for b in c.ctx.post_data['content_blocks'] if b['type'] == 'image')['url'] += '?foreign'
    elif mutation == 'raw_comment': c.ctx.post_data['comments_raw'][0]['content'] += ' 변조'
    elif mutation == 'selected_comment': c.ctx.comments[0] += ' 변조'
    elif mutation == 'post_id_type': c.ctx.post_data['post_id'] = str(c.ctx.post_id)
    elif mutation == 'derived_type': next(b for b in c.ctx.post_data['content_blocks'] if b['type'] == 'ocr_text')['type'] = 'text'
    elif mutation == 'block_order': c.ctx.post_data['content_blocks'].reverse()
    native_verified = c.callback()
    assert type(native_verified) is bool
    decision = c.pipe._source_bound_nsfw_decision(c.ctx, c.metadata, c.metadata['is_nsfw'], native_verified=native_verified)
    assert decision['status'] in {'SOURCE_NOT_BOUND', 'SOURCE_DRIFT'}
    assert decision['resolved_value'] is False and decision['evidence'] == []
    assert decision['source_carrier_sha256'] is None
    assert c.ctx._source_bound_nsfw_original_carrier == c.carrier
    assert canonical(c.ctx.expert_outputs) == c.expert_before and c.attempts == []
    (tmp_path / 'mutation_observation.json').write_text(json.dumps({
        'scope': SCOPE, 'case': name, 'mutation': mutation, 'native_callback_result': native_verified,
        'decision': decision, 'prior_ten_incomplete_replaced': False}, ensure_ascii=False, indent=2), encoding='utf8')


def test_derived_external_phrase_does_not_replace_current33_original(sut, facts, tmp_path):
    c = source_control(sut, facts, 'current33', tmp_path, external_derived=True)
    assert c.decision['resolved_value'] is False and c.decision['evidence'] == []
