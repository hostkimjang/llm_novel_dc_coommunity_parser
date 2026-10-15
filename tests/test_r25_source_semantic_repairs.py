"""원문 결속 설명의 병렬 대상·비판·후반 비교를 최종 공개 필드까지 확인한다."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_final_source_context_explanation import consume


def _visible(identity, notes):
    return "\n".join((identity.reason, *identity.reason_lines,
                      identity.primary_subject_text, notes))


def test_coordinated_media_absence_keeps_both_targets_without_inventing_a_work():
    for title, media in (("웹툰도 소설도 빡오는게 없구나", "웹툰·소설"),
                         ("만화도 영화도 볼만한게 없네", "만화·영화")):
        _, ctx, identity, notes, verify = consume(title, "하...")
        explanation = ctx._final_source_context_explanation
        visible = _visible(identity, notes)
        assert ctx._final_source_projection_consumption["source_explanation_used"]
        assert any(p.rule == "source_coordinated_media_absence" for p in explanation.proofs)
        assert media in explanation.primary_subject and media in visible
        assert "한 매체만의 평가" in visible
        assert identity.novel_identity is None and verify()


def test_coordinated_media_absence_does_not_claim_question_report_or_single_medium():
    for title in ("웹툰도 소설도 볼만한게 없나?", "친구가 웹툰도 소설도 볼만한게 없다고 함",
                  "웹툰도 볼만한게 없구나"):
        _, ctx, identity, notes, verify = consume(title)
        assert not any(p.rule == "source_coordinated_media_absence"
                       for p in ctx._final_source_context_explanation.proofs)
        assert verify()


def test_underused_character_criticism_explains_title_and_author_body():
    _, ctx, identity, notes, verify = consume(
        "솔직히 판수대 리샤 타락도 비중 좆도 없는것도 웃겼음 ㅋㅋ",
        "어떻게 여신의 딸이라 불리던 성녀가 신을 저버리고 타락했는데 전적이 잡몹들 처리가 끝 ㅋㅋ",
    )
    explanation = ctx._final_source_context_explanation
    visible = _visible(identity, notes)
    assert ctx._final_source_projection_consumption["source_explanation_used"]
    assert {p.raw_path for p in explanation.proofs} == {"/title", "/content_blocks/0/text"}
    assert "비중이 적다는 점" in visible and "큰 설정에 견줘 전적·활약" in visible
    assert "외부 사실 여부는 확인하지 않는다" in visible
    assert identity.novel_identity is None and verify()


def test_quoted_or_questioned_underuse_does_not_become_authors_criticism():
    for title in ("리샤 비중이 없다는 말이 웃겼냐?", "친구가 리샤 비중 없어서 웃겼다고 함",
                  "리샤 비중 없는 것도 웃겼음"):
        _, ctx, identity, notes, verify = consume(title)
        assert "비중이 적다는 점을 웃겼다고 표현하며 비판" not in _visible(identity, notes)
        assert verify()


def test_later_quality_limit_and_exception_override_open_question_summary():
    _, ctx, identity, notes, verify = consume(
        "소년만화도 사실 4드론아닐까?",
        "원나블도 그렇고 그 이후의 소년만화들도 그렇고",
        "절대 초반에피의 재미를 넘을 수 없는것같네",
        "후반갈수록 재밌는 소년만화 << 본적이 없음",
        "본좌인 드래곤볼정도만 예외",
    )
    explanation = ctx._final_source_context_explanation
    visible = _visible(identity, notes)
    assert ctx._final_source_projection_consumption["source_explanation_used"]
    assert "후반 전개 평가와 예외" in identity.primary_subject_text
    assert "초반에피의 재미를 후반 전개가 넘기 어렵다" in visible
    assert "드래곤볼」은 예외" in visible
    assert "절대 초반에피의에 긍정적인 반응" not in visible
    assert any(p.rule == "source_later_quality_limit_structure" for p in explanation.proofs)
    assert identity.novel_identity is None and verify()


def test_later_quality_limit_needs_same_authors_later_reading_claim():
    _, ctx, identity, notes, verify = consume(
        "소년만화도 사실 4드론아닐까?", "절대 초반에피의 재미를 넘을 수 없는것같네",
        comments=[{"comment_id": "c1", "author": "다른화자", "content": "후반갈수록 재밌는 만화 본적이 없음"}],
    )
    assert not any(p.rule == "source_later_quality_limit_structure"
                   for p in ctx._final_source_context_explanation.proofs)
    assert verify()


def test_later_quality_limit_without_exception_does_not_invent_one():
    _, ctx, identity, notes, verify = consume(
        "소년만화도 사실 4드론아닐까?", "절대 초반에피의 재미를 넘을 수 없는것같네",
        "후반갈수록 재밌는 소년만화 << 본적이 없음",
    )
    assert any(p.rule == "source_later_quality_limit_structure"
               for p in ctx._final_source_context_explanation.proofs)
    assert "후반 전개 평가" in identity.primary_subject_text
    assert "예외" not in _visible(identity, notes)
    assert verify()


def test_single_comment_preserves_previous_judgment_and_later_emotion():
    comment = "사실 전화까지는 그래도 행복한 죽음이라 생각했는데 막화 보니까 살짝 울컥..."
    _, ctx, identity, notes, verify = consume(
        "즉사무림 은영이 너무 불쌍해", "어렵게 생긴 가족을 위해 죽는다니",
        comments=[{"comment_id": "c1", "author": "다른화자", "content": comment}],
    )
    explanation = ctx._final_source_context_explanation
    assert any(p.rule == "source_comment_temporal_evaluation_shift" for p in explanation.proofs)
    assert "행복한 죽음이라 생각했는데" in notes and "막화 보니까 살짝 울컥" in notes
    assert "앞부분의 평가 하나로 줄이지 않는다" in notes
    assert "사실 전화까지는·그래도에 긍정적인 반응" not in notes
    assert verify()


def test_new_work_critique_outranks_generic_author_relation_without_title_promotion():
    _, ctx, identity, notes, verify = consume(
        "개돌 신작 초대남이 너무 좆같은데",
        "좀 사람새끼처럼 생겨야지",
        "그리고 남주도 병신같음",
        "그래야 전개에 개연성이 생기지",
    )
    explanation = ctx._final_source_context_explanation
    assert any(p.rule == "source_new_work_critique" for p in explanation.proofs)
    assert "초대남의 묘사와 다른 주요 인물·개연성에 대한 비판" in identity.primary_subject_text
    assert "초대남의 외모·묘사를 비판" in identity.reason
    assert identity.novel_identity is None and verify()


def test_actual_new_work_full_author_body_keeps_critique_primary():
    _, ctx, identity, notes, verify = consume(
        "개돌 신작 초대남이 너무 좆같은데",
        "좀 사람새끼처럼 생겨야지",
        "좆돼지 청소부는 너무 불쾌하잖아",
        "이럴거면 그냥 도적단에 던져버리던지",
        "창녀촌에서 수련을 시키던지 하지",
        "남캐 둘만 나온다던데",
        "나머지 하나가 금태양이나 거근쇼타여도 이 새끼랑 번갈아서 나온다는 소리잖아",
        "좆같노",
        "마왕 모가지 딴 대마법사랑 용사 연인이면 좀 멀쩡한 놈들 초대남으로 부를 수 있잖아",
        "대마법사에게 음심을 품고 있었지만 차마 밝힐 수 없던 귀여운 거근쇼타 제자라던가",
        "산전수전 다 겪고 여자경험도 풍부한 금태양 동료 궁수라던가",
        "그리고 남주도 병신같음",
        "명색이 용사인데 실좆은 어쩔 수 없더라도 정력은 존나 쎄야 하는 거 아니냐",
        "그래야 거근들한테 쑤셔져도 남주가 2시간 3시간 쉬지 않고 박아대면 돌아온다 그런 개연성이 생기지",
        "작품 설명에 NTR 강조한 거 보니 결말부엔 마음도 뜨겠노",
        "아쉽기 그지없다 정말",
    )
    visible = _visible(identity, notes)
    assert any(p.rule == "source_new_work_critique"
               for p in ctx._final_source_context_explanation.proofs)
    assert {p.raw_path for p in ctx._final_source_context_explanation.proofs
            if p.rule == "source_new_work_critique"} == {
                "/title", "/content_blocks/0/text", "/content_blocks/10/text", "/content_blocks/12/text",
            }
    assert "초대남의 묘사와 다른 주요 인물·개연성에 대한 비판" in identity.primary_subject_text
    assert "초대남의 외모·묘사를 비판" in visible
    assert "다른 주요 인물의 묘사와 전개의 개연성" in visible
    assert identity.novel_identity is None and verify()


def test_new_work_relation_alone_does_not_invent_detailed_critique():
    for body in (("본문은 없음",),
                 ("초대남 얼굴은 좋다", "남주는 싫다", "개연성은 좋다"),
                 ("초대남 얼굴이 별로다", "남주는 싫다", "개연성은 좋다"),
                 ("남주 얼굴은 별로다", "남주는 싫다", "개연성은 부족하다"),
                 ("좀 남주가 사람처럼 생겨야지", "남주도 싫다", "그래야 개연성이 생기지")):
        _, ctx, identity, notes, verify = consume("개돌 신작 초대남이 너무 별로인데", *body)
        assert not any(p.rule == "source_new_work_critique"
                       for p in ctx._final_source_context_explanation.proofs)
        assert "다른 주요 인물·개연성에 대한 비판" not in identity.primary_subject_text
        assert verify()
    _, ctx, identity, _, verify = consume(
        "개돌 신작 남주가 너무 별로인데", "남주 얼굴은 별로다", "남주도 싫다", "개연성이 부족하다")
    assert not any(p.rule == "source_new_work_critique"
                   for p in ctx._final_source_context_explanation.proofs)
    assert "다른 주요 인물·개연성에 대한 비판" not in identity.primary_subject_text
    assert verify()
    _, ctx, identity, _, verify = consume(
        "개돌 신작 초대남이 너무 별로인데", "청소부는 불쾌하다",
        "다른 인물을 여주로 부르면 좋겠다", "남주도 싫다")
    assert not any(p.rule == "source_new_work_critique"
                   for p in ctx._final_source_context_explanation.proofs)
    assert verify()
