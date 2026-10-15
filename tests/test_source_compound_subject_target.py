"""ROOT 전용: 실제 Kiwi→native 대상→설명 소비. 저장 관측은 성공 stub로 쓰지 않는다."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_final_source_context_explanation import consume
from llm_batch.grounding.source_speech_structure import _nominal_kiwi, _verified_subject_target, _event_fragment
from llm_batch.grounding.source_context_explanation import _bound_units

FIXTURE = Path(__file__).parent/'fixtures/b9_baseline_subject_observations.json'
FIXTURE_SHA = '2b958ec2f1ff12973215d64ea527255cb7601a169f040fcb83f618a80a10c0ee'


@pytest.fixture(scope='module')
def baseline_observations():
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == FIXTURE_SHA
    records = json.loads(raw)
    assert len(records) == 4
    assert all(record['events'][0]['verified_subject_target'] == '' for record in records)
    yield records
    assert FIXTURE.read_bytes() == raw


def b9(comment):
    return consume('개돌 신작 초대남이 너무 좆같은데', '좀 사람새끼처럼 생겨야지',
                   comments=[{'comment_id':'c1','author':'ㅇㅇ','content':comment}])


@pytest.mark.parametrize('index,expected,forbidden', [
    (0, '필요·당위 의견', '초대남에 불만·부정적인 반응을 보인다'),
    (1, '초대남에 불만·부정적인 반응을 보인다', '필요·당위 의견'),
    (2, '평가를 질문한다', '필요·당위 의견'),
    (3, None, '필요·당위 의견'),
])
def test_observed_b9_compound_subject_reaches_real_explanation_without_changing_native_event(
        baseline_observations, index, expected, forbidden):
    observed = baseline_observations[index]
    _, ctx, identity, notes, verify = b9(observed['text'])
    ledger = ctx._final_source_projection_native.comment_ledgers[0]
    assert len(ledger.evaluations) == 1
    event = ledger.evaluations[0]
    source = next(source for source in ledger.sources if source.source_id == event.source_id)
    original = observed['events'][0]['event']
    assert (event.predicate, event.predicate_span, event.actor, event.polarity,
            event.evaluation_polarity, event.realization, event.final_support) == (
        original['predicate'], tuple(original['predicate_span']), original['actor'], original['polarity'],
        original['evaluation_polarity'], original['realization'], original['final_support'])
    assert source.text == observed['text']
    assert event.grammatical_subject.text == '초대남이'
    assert event.grammatical_subject.span == (0,4)
    assert _verified_subject_target(source.text, event.grammatical_subject) == '초대남'
    if expected is not None:
        assert expected in notes
    assert forbidden not in notes
    if index == 0:
        assert any(proof.rule == 'source_evaluation_obligation_structure'
                   for proof in ctx._final_source_context_explanation.proofs)
        assert '글쓴이는 초대남에 불만·부정적인 반응을 보인다' in identity.reason
    if index == 3:
        # 당위 부정의 원래 event polarity는 그대로지만 현재 호평/불평을 새로 만들지 않는다.
        assert '초대남에 긍정적인 반응을 보인다' not in notes
        assert '초대남에 불만·부정적인 반응을 보인다' not in notes
    assert observed['text'] in notes and verify()


@pytest.mark.parametrize('name,particle,nominal_count', [
    ('급식메뉴','가',2), ('학교급식메뉴','가',3), ('관리시스템','이',2), ('출판관리시스템','이',3),
])
def test_other_adjacent_nominal_subjects_keep_full_source_span_through_native_and_notes(name, particle, nominal_count):
    comment = name + particle + ' 좋다.'
    _, ctx, identity, notes, verify = consume('다른 대상은 어떤가?', comments=[
        {'comment_id':'c2','author':'독자','content':comment}])
    native = ctx._final_source_projection_native
    event = next(event for event in native.comment_ledgers[0].evaluations if event.evaluation_polarity == 'pos')
    source = next(source for source in native.comment_ledgers[0].sources if source.source_id == event.source_id)
    tokens = [token for token in _nominal_kiwi().tokenize(source.text) if token.start < len(name)]
    assert len(tokens) == nominal_count and all(token.tag in {'NNG','NNP','SL','SH'} for token in tokens)
    assert ''.join(token.form for token in tokens) == name
    assert _verified_subject_target(source.text, event.grammatical_subject) == name
    assert f'댓글 1의 화자는 {name}에 긍정적인 반응을 보인다' in notes
    assert identity.novel_identity is None and verify()


@pytest.mark.parametrize('subject_text,target', [
    ('급식 메뉴가','급식메뉴'),
    ('친구의급식메뉴가','친구의급식메뉴'),
    ('새로운급식메뉴가','새로운급식메뉴'),
    ('읽은책이','읽은책'),
    ('급식,메뉴가','급식메뉴'),
    ('급식메뉴','급식메뉴'),
])
def test_oversized_or_unmarked_subject_cannot_cross_space_owner_adnominal_or_punctuation(subject_text,target):
    # 후보 native 주어의 범위를 과대 지정한 음성 대조다. 실제 tokenizer를 우회하지 않는다.
    source = subject_text + ' 좋다.'
    subject = SimpleNamespace(text=subject_text, span=(0,len(subject_text)), actor='other:'+target, explicit=True)
    assert _verified_subject_target(source,subject) == ''


@pytest.mark.parametrize('mode', ['span', 'text', 'actor'])
def test_compound_subject_must_match_same_source_span_and_actor(mode):
    source = '초대남이 좋다.'
    subject = SimpleNamespace(text='초대남이',span=(0,4),actor='other:초대남',explicit=True)
    if mode == 'span': subject.span=(1,4)
    elif mode == 'text': subject.text='다른이'
    else: subject.actor='other:초대'
    assert _verified_subject_target(source,subject) == ''


@pytest.mark.parametrize('mode', ['body', 'comment', 'carrier'])
def test_b9_explanation_retains_native_source_tamper_rejection(mode):
    _, ctx, _, notes, verify = b9('초대남이 좆같아야하는거임')
    assert '필요·당위 의견' in notes and verify()
    native = ctx._final_source_projection_native
    if mode == 'body': ctx.post_data['content_blocks'][0]['text'] = '변조된 작성자 본문'
    elif mode == 'comment': ctx.comments[0]['content'] = '다른 댓글'
    else: ctx._final_source_original_inputs[1]['raw_text'] = '변조된 원 carrier'
    assert not verify()
    assert ctx._final_source_projection_native is native and ctx._final_source_projection_call_count == 1


def test_single_nominal_target_and_reported_obligation_keep_existing_semantics():
    source = '결말이 좋다.'
    subject = SimpleNamespace(text='결말이',span=(0,3),actor='other:결말',explicit=True)
    assert _verified_subject_target(source,subject) == '결말'
    _, ctx, _, notes, verify = consume('전언의 범위',comments=[
        {'comment_id':'c3','author':'독자','content':'친구가 초대남이 좆같아야한다고 함'}])
    assert 'source_evaluation_obligation_structure' not in {proof.rule for proof in ctx._final_source_context_explanation.proofs}
    assert '댓글 1의 화자는 초대남에 불만·부정적인 반응을 보인다' not in notes
    assert verify()


@pytest.mark.parametrize('name,particle', [
    ('급식메뉴','가'), ('학교급식메뉴','가'), ('관리시스템','이'), ('출판관리시스템','이'),
])
def test_neutral_author_title_preserves_internal_comment_fragment_without_enabling_document_display(name, particle):
    comment = name + particle + ' 좋다.'
    _, ctx, identity, notes, verify = consume('다른 대상의 의견', comments=[
        {'comment_id':'c2','author':'독자','content':comment}])
    native = ctx._final_source_projection_native
    observed = ctx._final_source_discussion_observations
    units, unresolved = _bound_units(native, observed['records'], observed['comments'])
    assert not unresolved
    unit = next(unit for unit in units if unit.role == 'comment' and unit.text == comment)
    event = next(event for event in unit.proof.event_objects if event.evaluation_polarity == 'pos')
    fragment = _event_fragment(unit, event, native.projection)
    expected = f'댓글 1의 화자는 {name}에 긍정적인 반응을 보인다'
    assert fragment is not None and fragment.destination == 'note' and expected in fragment.sentence
    explanation = ctx._final_source_context_explanation
    assert any(expected in sentence for sentence in explanation.note_sentences)
    assert explanation.supported is False and explanation.primary_subject == '' and not explanation.reason_sentences
    assert ctx._final_source_projection_consumption['source_explanation_used'] is False
    assert expected not in notes and comment in notes
    assert identity.novel_identity is None and verify()
    assert ctx._final_source_projection_call_count == 1
