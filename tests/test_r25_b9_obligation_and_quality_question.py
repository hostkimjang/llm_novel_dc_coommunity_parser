"""R25 댓글의 평가 당위와 작성자 질문을 현재 평가로 바꾸지 않는다."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_final_source_context_explanation import consume


def _rules(ctx):
    return {proof.rule for proof in ctx._final_source_context_explanation.proofs}


def test_b9_comment_obligation_does_not_become_current_dissatisfaction():
    comments = [{"comment_id": "40479771", "author": "ㅇㅇ",
                 "content": "초대남이 좆같아야하는거임"}]
    _, ctx, identity, notes, verify = consume(
        "개돌 신작 초대남이 너무 좆같은데", "좀 사람새끼처럼 생겨야지",
        comments=comments)
    assert "source_evaluation_obligation_structure" in _rules(ctx)
    assert "댓글 1의 화자는 원문의 「초대남이 좆같아야하는거임」에서 필요·당위 의견" in notes
    assert "댓글 1의 화자는 초대남에 불만·부정적인 반응을 보인다" not in notes
    assert "글쓴이는 초대남에 불만·부정적인 반응을 보인다" in identity.reason
    assert verify()


def test_actual_negative_comment_and_question_keep_their_distinct_scope():
    for comment, expected in (
        ("초대남이 좆같음", "불만·부정적인 반응을 보인다"),
        ("초대남이 좆같아야 하나?", "평가를 질문한다"),
    ):
        _, ctx, _, notes, verify = consume(
            "개돌 신작 초대남이 너무 좆같은데", "좀 사람새끼처럼 생겨야지",
            comments=[{"comment_id": "c1", "author": "ㅇㅇ", "content": comment}])
        assert expected in notes
        assert "필요·당위 의견" not in notes
        assert verify()
    _, ctx, _, notes, verify = consume(
        "신작 인물 감상", comments=[{"comment_id": "c1", "author": "ㅇㅇ",
        "content": "친구가 초대남이 좆같아야한다고 함"}])
    assert "source_evaluation_obligation_structure" not in _rules(ctx)
    assert "댓글 1의 화자는 초대남에 불만·부정적인 반응을 보인다" not in notes
    assert verify()
    _, ctx, _, notes, verify = consume(
        "개돌 신작 초대남이 너무 좆같은데", "좀 사람새끼처럼 생겨야지",
        comments=[{"comment_id": "c1", "author": "ㅇㅇ",
                   "content": "초대남이 좆같아야하는거임은 아님"}])
    assert "source_evaluation_obligation_structure" not in _rules(ctx)
    assert "필요·당위 의견" not in notes
    assert verify()


def test_later_quality_question_is_not_a_settled_negative_assessment():
    question = "초반에피의 재미를 넘을 수 없나?"
    later = "후반갈수록 재밌는 소년만화 << 본적이 없음"
    _, ctx, identity, notes, verify = consume("소년만화도 사실 4드론아닐까?", question, later)
    assert "source_later_quality_limit_structure" not in _rules(ctx)
    assert "후반 전개가 넘기 어렵다고 평가" not in identity.reason
    assert "후반 전개가 넘기 어렵다고 평가" not in notes
    assert verify()

    _, ctx, identity, _, verify = consume("소년만화도 사실 4드론아닐까?",
        "절대 초반에피의 재미를 넘을 수 없는것같네", later)
    assert "source_later_quality_limit_structure" in _rules(ctx)
    assert "후반 전개가 넘기 어렵다고 평가" in identity.reason
    assert verify()
