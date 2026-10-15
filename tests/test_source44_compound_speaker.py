"""44 내용절·바깥 주체·부정 cue를 실제 native/설명으로 대조한다. ROOT 실행용."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import subprocess
from types import SimpleNamespace

import pytest

from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import PickvelIdentity, PostInput
from llm_batch.experts.orchestrator import ConversationContext
from llm_batch.grounding.context_projection_contract import _speaker_ledger, _nominal_judgment_binding
from llm_batch.grounding.source_context_diagnostics import export_source_context_diagnostics

FIXTURE = Path(__file__).parent / 'fixtures/source44_compound_speaker_saved.json'
FIXTURE_SHA = 'a14e68aefde4a07a879a50fb8a6ec454d968f218af9078acd1f3c6259612af95'
ORIGINAL = '다 좋은 마무리는 아니라고 생각해요'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


class ExternalAttempt(BaseException):
    pass


class NoExternal:
    def __init__(self):
        self.attempts = []

    def __getattr__(self, name):
        def forbidden(*args, **kwargs):
            self.attempts.append(name)
            raise ExternalAttempt(name)
        return forbidden


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise ExternalAttempt('NETWORK_OR_CHILD')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(subprocess, 'run', forbidden)


@pytest.fixture(scope='module')
def packet():
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == FIXTURE_SHA
    value = json.loads(raw)['packet']
    assert type(value['post_id']) is int and value['index1'] == 44
    assert hashlib.sha256(canonical({'post':value['source_post'], 'comments':value['source_comments']})).hexdigest() == value['source_canonical_sha256']
    assert hashlib.sha256(canonical(value['checkpoint_result'])).hexdigest() == value['result_canonical_sha256']
    yield value
    assert FIXTURE.read_bytes() == raw and canonical(value) == canonical(json.loads(raw)['packet'])


def consume(tmp_path, *, post=None, body=(), comments=(), candidates=None):
    raw = deepcopy(post) if post is not None else {'post_id': 944001, 'title':'작품 평가 이야기',
        'content_blocks':[{'type':'text','text':text} for text in body]}
    raw['comments'] = deepcopy(list(comments))
    model = PostInput(**raw)
    source_before = canonical(model.model_dump())
    external = NoExternal()
    pipe = AgenticPipeline(llm=external, mcp=external, output_dir=tmp_path, max_iterations=1,
        native_recovery=True, parallel_count=12)
    pipe.enable_heretic_live_fetch = False
    pipe.enable_url_fetch_disk_cache = False
    ctx = ConversationContext(post_id=model.post_id, post_data=pipe._post_to_dict(model), comments=model.comments)
    ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(model)
    ctx._final_source_original_comment_refs = tuple(model.comments)
    # 저장 전체 identity를 초기 context라고 위장하지 않는다. 공개 null인 명시 기능 입력이다.
    identity = PickvelIdentity(is_relevant=False, discussion_type='general', title_candidates=deepcopy(candidates))
    candidate_before = deepcopy(identity.model_dump()['title_candidates'])
    notes, verify = pipe._consume_final_source_context(ctx, identity, None)
    assert verify() and not external.attempts
    native = ctx._final_source_projection_native
    output = SimpleNamespace(_final_source_context_native=native, _final_source_context_owner=ctx)
    output._final_source_context_receipt = {'native_object':native, 'context':ctx,
        'native_verification_status':'NATIVE_CALLBACK_TRUE'}
    before_export = canonical(identity.model_dump(mode='json'))
    diagnostic = export_source_context_diagnostics(output, enabled=True)
    assert diagnostic['native_verification_status'] == 'NATIVE_CALLBACK_TRUE'
    assert diagnostic['publication_authority'] is False
    assert canonical(identity.model_dump(mode='json')) == before_export
    assert identity.novel_identity is None and identity.model_dump()['title_candidates'] == candidate_before
    assert canonical(model.model_dump()) == source_before and verify() and not external.attempts
    return ctx, identity, notes, diagnostic, verify


def good_cues(ledger):
    return [event for event in ledger.evaluations if event.evidence_kind == 'cue' and '좋' in event.predicate]


def assert_lexical_preservation(event):
    assert event.evaluation_polarity == 'pos' and event.polarity == 'positive'
    assert event.evidence_text[slice(*event.predicate_span)] == event.predicate


def test_original44_source_native_export_and_final_explanation_share_scope(tmp_path, packet):
    candidates = packet['checkpoint_result']['analysis_result']['identity']['title_candidates']
    ctx, identity, notes, diagnostic, verify = consume(tmp_path, post=packet['source_post'],
        comments=packet['source_comments'], candidates=candidates)
    ledger = ctx._final_source_projection_native.author_ledger
    claim = next(c for c in ledger.claims if c.text == ORIGINAL)
    assert (claim.kind, claim.speaker, claim.final_support) == ('own', 'self', True)
    assert claim.grammatical_subject.actor == 'self'
    events = [e for e in good_cues(ledger) if e.evidence_text == ORIGINAL]
    assert len(events) == 1
    event = events[0]
    assert event.predicate == '좋은' and event.predicate_span == (2, 4)
    assert event.actor == event.speaker == 'self'
    assert (event.grammatical_subject.actor, event.grammatical_subject.text,
            event.grammatical_subject.span, event.grammatical_subject.explicit) == ('self', '', (-1, -1), False)
    assert event.realization == 'embedded' and event.realization_source == 'nominal_judgment_content'
    assert not event.final_support
    assert_lexical_preservation(event)
    stored = next(e for l in diagnostic['ledgers'] if l['source_role'] == 'author'
                  for e in l['evaluations'] if e['event_id'] == event.event_id)
    assert (stored['actor'], stored['speaker'], stored['final_support']) == ('self','self',False)
    assert stored['predicate_span'] == [2, 4] and stored['evidence_text'] == ORIGINAL
    assert ORIGINAL in identity.reason + notes
    assert any(p['rule'] == 'source_comparison_not_sufficient_structure'
               for p in diagnostic['explanation']['proofs'])
    assert '비교 우위와 최종 평가를 구분한다' in identity.reason
    assert '긍정적인 반응' not in identity.reason
    assert verify()


@pytest.mark.parametrize('text', [
    ORIGINAL,
    '좋은 선택은 아니라고 생각해요',
    '나는 좋은 선택은 아니라고 생각해요',
    '저는 좋은 결말이 아니라고 판단해요',
    '좋은 작품의 결말은 아니라고 생각해요',
])
def test_content_noun_is_not_a_speaker_and_positive_lexeme_is_not_adopted(text):
    binding = _nominal_judgment_binding(text)
    assert binding is not None and binding['content_negated']
    assert text[slice(*binding['modifier_span'])] == '좋은'
    assert binding['actor'] == 'self'
    ledger = _speaker_ledger((text,), source_id='author')
    assert len(ledger.claims) == 1 and ledger.claims[0].speaker == 'self'
    assert ledger.claims[0].kind == 'own'
    assert ledger.claims[0].grammatical_subject.actor == 'self'
    events = good_cues(ledger)
    assert events and all(not e.final_support for e in events)
    for event in events:
        assert_lexical_preservation(event)
        assert event.actor == event.grammatical_subject.actor == binding['actor']
        assert event.grammatical_subject.span == binding['actor_span']
        a, z = binding['actor_span']
        assert event.grammatical_subject.text == (text[a:z] if a >= 0 else '')
        assert event.grammatical_subject.explicit is (a >= 0)


@pytest.mark.parametrize('text,speaker', [
    ('친구는 좋은 마무리는 아니라고 생각한다', '친구'),
    ('유진은 좋은 선택이 아니라고 생각한다', '유진'),
    ('친구는 좋은 마무리가 아니냐고 물었다', '친구'),
])
def test_explicit_matrix_speaker_keeps_external_report(text, speaker):
    ledger = _speaker_ledger((text,), source_id='author')
    assert len(ledger.claims) == 1
    claim = ledger.claims[0]
    assert (claim.speaker, claim.kind, claim.final_support) == (speaker, 'reported', False)
    events = good_cues(ledger)
    assert events and all(e.actor == 'other:' + speaker and not e.final_support for e in events)
    for event in events:
        assert_lexical_preservation(event)
        subject = event.grammatical_subject
        assert subject.actor == event.actor and subject.explicit
        assert subject.span == (0, len(text.split()[0]))
        assert text[slice(*subject.span)] == subject.text == text.split()[0]


def test_same_word_used_as_a_named_quoted_speaker_is_preserved():
    text = '마무리는 "이 작품은 좋다."라고 말했다.'
    ledger = _speaker_ledger((text,), source_id='author')
    claim = next(c for c in ledger.claims if c.text == '이 작품은 좋다.')
    assert claim.kind == 'reported' and claim.speaker == '마무리' and not claim.final_support
    assert all(not e.final_support for e in ledger.evaluations)


@pytest.mark.parametrize('text,mode', [
    ('좋은 마무리가 아니냐고 물었다', 'question'),
    ('좋은 선택은 아니라고 생각하나요?', 'question'),
    ('좋은 선택은 아니라고 생각한다면 계속 고민하겠다.', 'conditional'),
    ('좋은 선택이라고 생각하지 않는다.', 'embedded'),
    ('좋은 마무리가 아니라고 생각하지 않는다', 'embedded'),
])
def test_question_condition_and_belief_negation_do_not_assert_content_praise(text, mode):
    ledger = _speaker_ledger((text,), source_id='author')
    assert ledger.claims and all(c.speaker == 'self' for c in ledger.claims)
    events = good_cues(ledger)
    assert events and all(e.realization == mode and not e.final_support for e in events)
    for event in events:
        assert_lexical_preservation(event)


@pytest.mark.parametrize('text', [
    '이 작품은 좋다.',
    '나는 좋은 선택이라고 생각한다.',
    '좋은 마무리라고 생각해요',
])
def test_independent_positive_evaluation_and_positive_nominal_judgment_survive(text):
    ledger = _speaker_ledger((text,), source_id='author')
    events = good_cues(ledger)
    assert events and any(e.final_support and e.realization == 'actual' for e in events)
    assert all(c.speaker == 'self' for c in ledger.claims)


@pytest.mark.parametrize('same_block', [False, True])
def test_actual_source_split_preserves_later_independent_praise(tmp_path, same_block):
    later = '하지만 이 작품은 좋다.'
    body = [ORIGINAL + '. ' + later] if same_block else [ORIGINAL + '.', later]
    ctx, identity, notes, diagnostic, verify = consume(tmp_path, body=body)
    ledger = ctx._final_source_projection_native.author_ledger
    # 실제 caller 분할 경로를 사용한다. 두 문장을 ledger의 단일 clause라고 전달하지 않는다.
    first = [e for e in good_cues(ledger) if e.predicate == '좋은']
    second = [e for e in good_cues(ledger) if e.predicate.startswith('좋다')]
    assert first and second and all(not e.final_support for e in first)
    assert any(e.final_support and e.actor == 'self' for e in second)
    assert {e.source_id for e in first}.isdisjoint({e.source_id for e in second})
    assert ORIGINAL in identity.reason + notes and later in identity.reason + notes
    assert verify()


@pytest.mark.parametrize('placement', ['body', 'comment'])
def test_consumer_keeps_source_role_and_rejects_uncaptured_mutation(tmp_path, placement):
    comments = [{'comment_id':'c44', 'author':'다른 독자', 'content':ORIGINAL}] if placement == 'comment' else []
    ctx, identity, notes, diagnostic, verify = consume(tmp_path,
        body=[ORIGINAL] if placement == 'body' else [], comments=comments)
    native = ctx._final_source_projection_native
    ledger = native.author_ledger if placement == 'body' else native.comment_ledgers[0]
    claim = next(c for c in ledger.claims if c.text == ORIGINAL)
    assert claim.kind == 'own' and claim.speaker == 'self'
    assert ledger.source_role == ('author' if placement == 'body' else 'comment')
    assert good_cues(ledger) and all(not e.final_support for e in good_cues(ledger))
    if placement == 'body':
        ctx.post_data['content_blocks'][0]['text'] += ' 변조'
    else:
        ctx.comments[0]['content'] += ' 변조'
    assert not verify()


def test_saved44_publication_and_learning_are_separate_from_new_native_trial(packet):
    from llm_batch.domain.batch_context import BatchContextMemory
    from llm_batch.ledger.publication_commit import compute_publication_decision_commit, validate_publication_result_commit
    from expert_main import _learn_batch_context_from_canonical_publication
    saved = deepcopy(packet['checkpoint_result'])
    before = canonical(saved)
    receipt = compute_publication_decision_commit(saved, publication_scope_id=packet['publication_scope_id'],
        attempt_run_id=packet['run_id'], input_index=44, post_id=packet['post_id'])
    validate_publication_result_commit(saved, receipt, expected_scope_id=packet['publication_scope_id'],
        expected_input_index=44, expected_post_id=packet['post_id'])
    memory = BatchContextMemory(enabled=True)
    assert receipt.outcome == 'HOLD' and receipt.publish_allowed is False
    assert _learn_batch_context_from_canonical_publication(memory, saved, receipt, created=True) is False
    assert memory.resolved_abbreviations == memory.resolved_authors == memory.resolved_characters == {}
    assert canonical(saved) == before
