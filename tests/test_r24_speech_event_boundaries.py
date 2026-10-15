"""R24 인과절 평가의 주체·질문·추측 경계를 원문 사건으로 검증한다."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_batch.grounding.context_projection_contract import _source_evaluation_events
from tests.test_final_source_context_explanation import consume


def _cue(text: str):
    events = [e for e in _source_evaluation_events(text, (), "clause:0") if e.evidence_kind == "cue"]
    assert len(events) == 1
    return events[0]


@pytest.mark.parametrize("text, actor, realization", [
    ("근데 ts녀를 너무 사랑해서 괴롭힐 수 없기 때문에 족장님도 참으면서 선 안넘고 박태양도 비중 사라짐", "unknown", "actual"),
    ("검미성은 ts녀를 사랑해서 괴롭힐 수 없었다", "other:검미성", "actual"),
    ("나는 ts녀를 사랑해서 계속 읽었다", "self", "actual"),
    ("ts물을 좋아하다보니 암타를 한걸지도", "unknown", "modal"),
    ("ts물을 좋아하다보니 암타를 한걸지도?", "unknown", "question"),
    ("ts물을 좋아하다보니 암타를 했다", "self", "actual"),
])
def test_causal_cue_keeps_actor_and_realization_boundary(text, actor, realization):
    event = _cue(text)
    assert (event.actor, event.realization) == (actor, realization)
    assert text[event.predicate_span[0]:event.predicate_span[1]] == event.predicate


def test_plot_cause_does_not_become_author_or_commenter_praise():
    line = "근데 ts녀를 너무 사랑해서 괴롭힐 수 없기 때문에 족장님도 참으면서 선 안넘고 박태양도 비중 사라짐"
    _, ctx, identity, notes, verify = consume("전개 해석", line, comments=[
        {"comment_id": "c1", "author": "다른화자", "content": line},
    ])
    explanation = ctx._final_source_context_explanation
    assert not any(p.rule == "source_event_structure" for p in explanation.proofs)
    assert "비중 사라짐" in identity.reason or "비중 사라짐" in notes
    assert verify()


def test_comment_conjecture_is_not_question_or_commenter_praise():
    _, ctx, identity, notes, verify = consume("TS 서사 추측", comments=[
        {"comment_id": "c1", "author": "다른화자", "content": "ts물을 좋아하다보니 암타를 한걸지도"},
    ])
    explanation = ctx._final_source_context_explanation
    assert not any(p.rule == "source_event_structure" for p in explanation.proofs)
    assert verify()


@pytest.mark.parametrize("text, expected", [
    ("나는 ts녀를 사랑해서 계속 읽었다", "긍정적인 반응"),
    ("ts녀를 사랑하나요?", "평가를 질문"),
    ("ts녀를 사랑한다면 계속 읽겠다", "조건·가능성"),
])
def test_true_own_reaction_question_and_condition_survive(text, expected):
    _, ctx, identity, notes, verify = consume(text)
    explanation = ctx._final_source_context_explanation
    assert any(p.rule == "source_event_structure" for p in explanation.proofs)
    assert expected in "\n".join((*explanation.reason_sentences, *explanation.note_sentences))
    assert verify()


def test_reported_and_other_actor_do_not_become_own_evaluation():
    for line in ("검미성은 ts녀를 사랑해서 괴롭힐 수 없었다", "친구가 ts녀를 사랑한다고 말했다"):
        _, ctx, identity, notes, verify = consume("서사 해석", line)
        explanation = ctx._final_source_context_explanation
        assert "ts녀에 대한 긍정적인 반응" not in explanation.primary_subject
        assert "글쓴이는 ts녀에 긍정적인 반응" not in "\n".join(explanation.reason_sentences)
        assert verify()


@pytest.mark.parametrize("comment", [
    "핑발바이의 미친마법사 겁탈참기 lv.max",
    "미친 마법사 등장",
])
def test_nominal_michin_work_phrase_does_not_become_comment_surprise(comment):
    _, ctx, identity, notes, verify = consume(
        "작품 표현", comments=[
            {"comment_id": "29662459", "author": "ㅇㅇ", "content": comment},
        ],
    )
    explanation = ctx._final_source_context_explanation
    assert not any(
        event.evidence_kind == "cue" and event.evaluation_polarity == "surprise"
        for event in _source_evaluation_events(comment, (), "comment:29662459")
    )
    assert not any(
        proof.rule == "source_event_structure"
        and any(event.evaluation_polarity == "surprise" for event in proof.event_objects)
        for proof in explanation.proofs
    )
    assert "놀라움" not in notes
    assert "놀라움" not in identity.reason
    assert comment in str(ctx._final_source_original_comment_refs)
    assert verify()


@pytest.mark.parametrize("comment", [
    "미친! 이 전개 뭐야",
    "미친, 이번 화 전개 뭐야",
    "미친 ㅋㅋ 이번 화 전개",
    "헐 이번 화 보고 놀랐음",
])
def test_independent_comment_surprise_still_survives_native_consumer(comment):
    _, ctx, _, notes, verify = consume(
        "전개 반응", comments=[
            {"comment_id": "c1", "author": "ㅇㅇ", "content": comment},
        ],
    )
    assert any(
        event.evidence_kind == "cue" and event.evaluation_polarity == "surprise"
        for event in _source_evaluation_events(comment, (), "comment:c1")
    )
    assert comment in notes
    assert verify()


def test_unique_guild_name_and_first_body_impression_have_bounded_relation_proof():
    _, ctx, identity, notes, verify = consume(
        '저것봐! 한국 최강의 S급 길드 "7인입구막기"다!',
        '단 한 번도 게이트 공략에 실패하지않은 길드 느낌임',
    )
    explanation = ctx._final_source_context_explanation
    proofs = [p for p in explanation.proofs if p.rule == "source_guild_name_impression_relation"]
    assert len(proofs) == 2
    assert {p.raw_path for p in proofs} == {"/title", "/content_blocks/0/text"}
    assert "'7인입구막기'를 길드 이름으로 소개" in explanation.reason_sentences[0]
    assert "본문 첫 줄에서 그 길드에 대해 '단 한 번도 게이트 공략에 실패하지않은 길드'라는 인상을 이어 적는다" in explanation.reason_sentences[0]
    assert "글 안의 화제 연결" in explanation.reason_sentences[0]
    assert "실제 집단의 정체나 공략 기록" in explanation.reason_sentences[0]
    assert explanation.primary_subject == "제목의 길드 이름 소개와 첫 본문의 길드 인상."
    assert "그에 대한 인상" not in explanation.primary_subject
    assert not explanation.counts_as_core and not explanation.publication_authority
    assert identity.novel_identity is None and verify()


@pytest.mark.parametrize("title, body, comments", [
    ('S급 길드 "첫째"다! B급 길드 "둘째"다!', ('공략에 실패하지않은 길드 느낌임',), ()),
    ('S급 길드 "별빛단"이다!', ('공략에 실패하지않은 조직 느낌임',), ()),
    ('S급 길드 "별빛단"이다!', ('친구가 공략에 실패하지않은 길드 느낌이라고 했다',), ()),
    ('S급 길드 "별빛단"이다!', (), ('공략에 실패하지않은 길드 느낌임',)),
    ('S급 길드 "별빛단"이다!', ('공략에 실패하지않은 길드 느낌임?',), ()),
])
def test_guild_relation_holds_without_unique_current_author_title_body_pair(title, body, comments):
    comment_rows = [{"comment_id": f"c{i}", "author": "다른화자", "content": text}
                    for i, text in enumerate(comments)]
    _, ctx, identity, notes, verify = consume(title, *body, comments=comment_rows)
    explanation = ctx._final_source_context_explanation
    assert not any(p.rule == "source_guild_name_impression_relation" for p in explanation.proofs)
    assert verify()


@pytest.mark.parametrize("body", [
    "단 한 번도 게이트 공략에 실패하지않은 다른 길드 느낌임",
    "단 한 번도 게이트 공략에 실패하지않은 다른 S급 길드 느낌임",
    "공략에 실패하지않은 라이벌 길드 느낌임",
    "공략에 실패하지않은 라이벌인 길드 느낌임",
    "공략에 실패하지않은 경쟁 길드 느낌임",
    "검은달이라는 길드 느낌임",
    "검은달 길드 느낌임",
    "별빛단 아닌 길드 느낌임",
    "별빛단이 아닌 길드 느낌임",
    "별빛단 아니었던 길드 느낌임",
    "별빛단 말고 길드 느낌임",
    "별빛단 외의 길드 느낌임",
    "별빛단 제외한 길드 느낌임",
])
def test_guild_relation_holds_for_explicit_other_guild_target(body):
    _, ctx, identity, notes, verify = consume('S급 길드 "별빛단"이다!', body)
    explanation = ctx._final_source_context_explanation
    assert not any(p.rule == "source_guild_name_impression_relation" for p in explanation.proofs)
    assert verify()


@pytest.mark.parametrize("line", [
    "아침먹고 앉아있다가 집이 흔들렸다함 ㅋㅋㅋ",
    "그때부터 덜덜덜덜덜 했다함 ㅋㅋㅋㅋ",
])
def test_reported_clause_keeps_original_predicate_in_quoted_explanation(line):
    _, ctx, identity, notes, verify = consume("지진 이야기", line)
    explanation = ctx._final_source_context_explanation
    proofs = [p for p in explanation.proofs if p.rule == "source_report_structure"]
    assert proofs and all(p.raw_path == "/content_blocks/0/text" for p in proofs)
    visible = "\n".join((*explanation.reason_sentences, explanation.primary_subject, identity.reason, notes))
    assert f"「{line}」라는 전언 표현" in visible
    assert "흔들렸에" not in visible and "했에" not in visible
    assert verify()


def test_reported_other_modal_negative_question_is_inscription_only():
    _, ctx, identity, notes, verify = consume(
        "무랑캐 마카롱...",
        "설마 단군신화의 웅녀가 매운걸 너무 먹어서 단걸 좋아하는 건 아니겠지",
    )
    explanation = ctx._final_source_context_explanation
    proofs = [p for p in explanation.proofs if p.rule == "source_reported_modal_doubt_inscription"]
    assert len(proofs) == 1 and proofs[0].raw_path == "/content_blocks/0/text"
    assert proofs[0].claim_kind == "reported" and not proofs[0].final_support
    event = proofs[0].event_objects[0]
    assert event.actor == "other:웅녀" and event.realization == "modal" and not event.final_support
    sentence = explanation.reason_sentences[0]
    assert "추측성 부정 의문이 적혀 있다" in sentence
    assert "실제 선호나 앞 절 행동을 확인한 사실로 확정하지 않는다" in sentence
    assert not explanation.counts_as_core and not explanation.publication_authority
    assert identity.novel_identity is None and verify()


@pytest.mark.parametrize("body, comments", [
    (("웅녀가 단걸 좋아한다",), ()),
    (("설마 내가 단걸 좋아하는 건 아니겠지",), ()),
    (("만약 웅녀가 단걸 좋아하면 어떻게 될까",), ()),
    ((), ("설마 단군신화의 웅녀가 매운걸 너무 먹어서 단걸 좋아하는 건 아니겠지",)),
])
def test_inscription_does_not_promote_assertion_self_question_condition_or_comment(body, comments):
    comment_rows = [{"comment_id": f"c{i}", "author": "다른화자", "content": text}
                    for i, text in enumerate(comments)]
    _, ctx, identity, notes, verify = consume("서사에 관한 생각", *body, comments=comment_rows)
    explanation = ctx._final_source_context_explanation
    assert not any(p.rule == "source_reported_modal_doubt_inscription" for p in explanation.proofs)
    assert verify()


def test_native_origin_tamper_invalidates_new_relation_proof():
    _, ctx, identity, notes, verify = consume('S급 길드 "별빛단"이다!', '공략에 실패하지않은 길드 느낌임')
    proof = next(p for p in ctx._final_source_context_explanation.proofs
                 if p.rule == "source_guild_name_impression_relation")
    assert verify()
    object.__setattr__(proof.origin_object, "raw_text", "바뀐 원문")
    assert not verify()


def test_unverified_subject_surface_does_not_form_broken_evaluation_target():
    for title, body, malformed in (
        ("창작물에 나오는 신들 다 좆밥아님?", (), "나오에"),
        ("가을입니다 하니까 그거 생각나네",
         ("나의 일러레 웹툰에서 울집매 히로인 ntr한 거", "걔가 저지른 일은 아니긴 한데 너무 충격적이었음"),
         "일은에"),
    ):
        _, ctx, identity, notes, verify = consume(title, *body)
        explanation = ctx._final_source_context_explanation
        visible = "\n".join((*explanation.reason_sentences, *explanation.note_sentences,
                             explanation.primary_subject, identity.reason, notes))
        assert malformed not in visible
        assert verify()

    _, ctx, identity, notes, verify = consume("주인공이 싫지 않다")
    assert "주인공에 긍정적인 반응" in identity.reason
    assert verify()
