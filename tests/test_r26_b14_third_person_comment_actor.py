"""실제 B14 댓글의 제3자 행위자와 자기 평가·부정·질문 경계를 묶어 검증한다."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_batch.grounding.context_projection_contract import _source_evaluation_events
from tests.test_final_source_context_explanation import consume


ACTUAL_COMMENT = "검미성은 이쪽이 익숙한맛인데 검미성이 ts녀를 사랑해서..."


def _love_event(text: str):
    events = [e for e in _source_evaluation_events(text, (), "comment:40480057")
              if "사랑" in e.predicate]
    assert len(events) == 1
    return events[0]


@pytest.mark.parametrize("text, polarity, realization", [
    (ACTUAL_COMMENT, "pos", "actual"),
    ("검미성이 ts녀를 사랑하지 않아서...", "neg", "actual"),
    ("검미성이 ts녀를 사랑해서...?", "pos", "question"),
])
def test_explicit_third_person_subject_survives_terminal_punctuation(text, polarity, realization):
    event = _love_event(text)
    assert event.actor == "other:검미성"
    assert event.grammatical_subject.explicit
    assert event.grammatical_subject.text == "검미성이"
    assert event.attribution == "causal_explicit_subject_token"
    assert event.attribution_evidence_span != (-1, -1)
    assert event.evaluation_polarity == polarity
    assert event.realization == realization
    assert text[event.predicate_span[0]:event.predicate_span[1]] == event.predicate


def test_actual_comment_does_not_become_commenter_positive_reaction():
    _, ctx, identity, notes, verify = consume(
        "망겜힐은 오행복 박태양이 빌런이였어야돼",
        comments=[{"comment_id": "40480057", "author": "ㅇㅇ", "content": ACTUAL_COMMENT}],
    )
    explanation = ctx._final_source_context_explanation
    assert not any(
        proof.rule == "source_event_structure"
        and any(event.actor == "other:검미성" for event in proof.event_objects)
        for proof in explanation.proofs
    )
    assert ACTUAL_COMMENT in notes
    assert "댓글 1의 화자는 ts녀" not in notes
    assert "긍정적인 반응을 보인다" not in notes
    assert identity.novel_identity is None and verify()


def test_genuine_first_person_evaluation_still_survives():
    text = "나는 ts녀를 사랑해서 계속 읽었다"
    event = _love_event(text)
    assert event.actor == "self" and event.evaluation_polarity == "pos"
    _, ctx, identity, notes, verify = consume("작품 감상", text)
    assert any(proof.rule == "source_event_structure" for proof in ctx._final_source_context_explanation.proofs)
    assert "긍정적인 반응" in identity.reason + notes
    assert verify()


def test_negated_first_person_and_third_person_stay_distinct():
    own = _love_event("나는 ts녀를 사랑하지 않아서...")
    other = _love_event("검미성이 ts녀를 사랑하지 않아서...")
    assert (own.actor, own.evaluation_polarity) == ("self", "neg")
    assert (other.actor, other.evaluation_polarity) == ("other:검미성", "neg")
    assert own.polarity == other.polarity == "positive"


@pytest.mark.parametrize("comment", [
    "검미성이 ts녀를 사랑해서...?",
    "「검미성이 ts녀를 사랑해서...?」라고 물었다",
])
def test_question_or_quoted_question_does_not_turn_into_current_praise(comment):
    _, ctx, _, notes, verify = consume(
        "질문", comments=[{"comment_id": "q1", "author": "ㅇㅇ", "content": comment}],
    )
    assert "긍정적인 반응을 보인다" not in notes
    assert "댓글 1의 화자는 ts녀" not in notes
    assert comment in notes
    assert verify()
