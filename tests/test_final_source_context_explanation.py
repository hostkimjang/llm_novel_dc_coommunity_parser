"""최종 네 필드의 원문 설명·인용 경계·댓글 귀속 기능 검증."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import NovelIdentity, PickvelIdentity, PostInput
from llm_batch.experts.orchestrator import ConversationContext, ExpertType
from llm_batch.grounding.claim_scope_contract import split_clauses
from llm_batch.grounding.context_projection_contract import _is_question


def consume(title, *body, comments=(), identity=None, discourse=None, synthesizer=None):
    post = PostInput(post_id=123, title=title, author="동일표시명", ip="118.235",
        content_blocks=[{"type": "text", "text": line} for line in body], comments=list(comments))
    pipeline = AgenticPipeline(llm=object(), mcp=object(), max_iterations=2)
    ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
    ctx._final_source_original_inputs = pipeline._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs = tuple(post.comments)
    if discourse is not None:
        ctx.set_expert_output(ExpertType.DISCOURSE, discourse)
    if synthesizer is not None:
        ctx.set_expert_output(ExpertType.SYNTHESIZER, synthesizer)
    identity = identity or PickvelIdentity(is_relevant=False, discussion_type="general")
    notes, verify = pipeline._consume_final_source_context(ctx, identity, None)
    return pipeline, ctx, identity, notes, verify


def test_concrete_plot_reaction_survives_missing_expert_summary():
    _, ctx, identity, notes, verify = consume("전개 감상", "생각보다 적수를 빨리 죽이고",
        "무리를 일망타진한게 의외였음", "작가가 큰판을 보여줘서 좋구나")
    assert "일망타진" in identity.reason and "놀라움" in identity.reason
    assert "예상과 달랐" in identity.primary_subject_text
    assert identity.reason_lines and "큰판" in notes
    assert ctx._final_source_projection_consumption["source_explanation_used"]
    assert not ctx._final_source_projection_consumption["source_explanation_counts_as_core"]
    assert not ctx._final_source_projection_consumption["source_explanation_grants_publication_authority"]
    assert identity.novel_identity is None and verify()


def test_missing_summary_cost_claim_and_comment_exception_reach_public_fields():
    comments = [{"comment_id": "c1", "author": "ㅇㅇ", "content": "가챠겜 하면 10만원 공중분해"},
                {"comment_id": "c2", "author": "ㅇㅇ", "content": "단, 모바일겜은 제외."},
                {"comment_id": "c3", "author": "ㅇㅇ", "content": "단, 피방은 제외."},
                {"comment_id": "c4", "author": "ㅇㅇ", "content": "단, 피방은 오늘 문 닫음."},
                {"comment_id": "c5", "author": "ㅇㅇ", "content": "피방은 빼고 계산해야지"}]
    _, ctx, identity, notes, verify = consume(
        "게임이랑 소설이 취미인게 가성비임", "피방은 3만원, 노피아는 1만 5천원 정도 씀", comments=comments)
    assert ctx._final_source_projection_consumption["source_explanation_used"]
    assert "가성비" in identity.primary_subject_text
    assert "쓴 금액" in identity.reason
    assert all(f"댓글 {number}" in notes for number in (1, 2, 3, 5))
    assert "댓글 3의 화자는 비용 평가에 대해 예외를 제시한다" in notes
    assert "댓글 4의 화자는 비용 평가에 대해 예외를 제시한다" not in notes
    assert "댓글 5의 화자는 비용 평가에 대해 예외를 제시한다" in notes
    assert identity.novel_identity is None and verify()


def test_unsupported_summary_does_not_supply_new_plot_facts_to_public_explanation():
    summary = "현재 작품의 전개 속도나 특정 복선의 흐름을 보고 향후 전개될 내용을 예견한다."
    _, ctx, identity, notes, verify = consume(
        "즉사무림이유백 미래가 벌써 보이네", "벌써 시동걸 정도면 ㄷㄷ",
        synthesizer={"reinterpretation": {"post_intent": summary}, "synthesis_summary": summary})
    assert ctx._final_source_projection_consumption["source_explanation_used"]
    assert "앞으로의 전개" in identity.primary_subject_text
    assert "복선의 흐름" not in identity.reason
    assert "전개 속도" not in identity.reason
    assert identity.novel_identity is None and verify()


def test_skipped_friend_question_is_neutral_quote_with_exact_source_proof():
    pipeline, ctx, identity, notes, verify = consume("찐친 어떻게 만들지", "관심 분야가 맞아야 하잖아.",
        "친구는 없으면,, 사이가 멀어지지 않음?", "그 분야 이야기를 하고 싶은데 잘 안 맞는거지")
    quoted = pipeline._final_source_skipped_clause_observations(ctx._final_source_projection_native)
    assert len(quoted) == 1 and not quoted[0]["counts_as_core"]
    lo, hi = quoted[0]["raw_span"]
    assert quoted[0]["origin"].raw_text[lo:hi] == quoted[0]["raw_text"]
    assert "친구는 없으면,, 사이가 멀어지지 않음?" in identity.reason
    assert "관심" in identity.primary_subject_text and "친구" in notes
    assert "전해 들은 사실" not in identity.reason and verify()


def test_numeric_dots_preserve_full_online_surfaces_and_sentence_boundary():
    assert [clause.text for clause in split_clauses("118.235 친구. 39.7도 친구.")] == ["118.235 친구.", "39.7도 친구."]
    _, _, identity, _, verify = consume("친구가 많네", "118.235", "39.7", "ㅇㅇ", "가상쨩", "너희 내 친구쟈나")
    assert "118.235" in identity.reason and "39.7" in identity.reason
    assert "농담" in identity.primary_subject_text and verify()


def test_past_reported_question_and_independent_current_question_keep_scope():
    past = "난 기억나는데 예전 게시판에 이 기능 좋나요?라고 물어본게 첫글임"
    assert [clause.text for clause in split_clauses(past)] == [past] and not _is_question(past)
    assert _is_question(past + ". 지금은 어떤가요?")
    _, ctx, identity, _, verify = consume("첫글 뭐임?", past)
    records = ctx._final_source_discussion_observations["records"]
    recollection = next(r for r in records if r["text"] == past)
    assert recollection["kind"] == "past_recollection" and not recollection["question"]
    assert "과거 질문·경험 회상" in identity.reason and verify()


def test_same_name_and_ip_are_comment_candidates_and_mutation_is_rejected():
    comments = [{"comment_id": "c1", "author": "동일표시명", "ip": "118.235", "content": "추천후보"}]
    _, ctx, identity, notes, verify = consume("이런 소설 없냐", "거대로봇 나오는 소설 없냐", comments=comments)
    metadata = ctx.post_data["comment_metadata"][0]
    assert not metadata["is_post_author"] and metadata["post_author_match_unverified"]
    assert "댓글 작성자 동일표시명" in identity.reason and "- 작성자 동일표시명:" not in identity.reason
    assert verify()
    ctx.comments[0]["content"] = "바뀐 댓글"
    assert not verify()


def test_title_resolution_does_not_announce_unpublished_official_pair():
    identity = PickvelIdentity(is_relevant=False, discussion_type="general", title_resolution_state="resolved",
        novel_identity=NovelIdentity(official_title="내부후보", heretic_url=None, confidence="Low"))
    _, _, identity, _, verify = consume("작품 얘기", "아직 제목을 모르겠다", identity=identity)
    assert "공식 제목·URL 공개 검증은 미완료" in identity.reason
    assert "- 공식 제목: 미확정" in identity.reason
    assert "- 제목 판정: resolved" not in identity.reason and verify()


def test_reader_behavior_question_keeps_fiction_background_separate():
    _, _, identity, notes, verify = consume("악플쓰고 소설빙의하는거 궁금한게", "소설보고 댓글쓰고 그럼?", "난 아얘안써봐서")
    assert "실제 독자" in identity.primary_subject_text
    assert "배경" in notes and "댓글을 써 본 적이 없" in notes
    assert verify()


def test_current_work_evaluation_and_origin_questions_do_not_route_to_genre_or_community():
    for title, body, expected in [
        ("급한 질문", "새벽대장장이 볼만함?", "work_evaluation_question"),
        ("아니 재료작 게시판발 작품이었음?", "", "work_origin_question")]:
        identity = PickvelIdentity(is_relevant=False, discussion_type="trope_discussion",
            primary_subject_type="genre_question", subtype="genre_trope_discussion")
        _, _, identity, _, verify = consume(title, *([body] if body else []), identity=identity,
            discourse={"primary_domain": "novel_literature"})
        assert identity.primary_subject_type == expected
        assert identity.discussion_type == "general" and identity.novel_identity is None
        assert "질문" in identity.reason or "판단을 구한다" in identity.reason
        assert verify()


def test_recommendation_allowance_and_mood_are_not_work_praise():
    _, _, identity, notes, verify = consume("이런 소설 없냐", "거대로봇 비행선 나오는 소설", "해외소설이라도 좋아",
        "비슷한 느낌이라 최근 기분이 좋다")
    assert "해외소설이라도을 좋게 평가" not in identity.reason
    assert "기분이을 좋게 평가" not in identity.reason
    assert "허용" in notes and "기분" in notes and verify()


def test_sympathy_and_dissatisfaction_preserve_target_and_reading_limit():
    _, _, identity, _, verify = consume("인물B가 너무 불쌍해", "가족을 위해 죽는다니")
    assert "안타까움" in identity.primary_subject_text and "인물B" in identity.reason and verify()
    _, _, identity, _, verify = consume("작품A 초반 감상", "작품A 초반 보는데 대사가 오글거려")
    assert "불만" in identity.reason and "완독" in identity.reason and verify()


def test_narrative_feature_question_and_counterfactual_preference_are_not_facts():
    _, _, identity, _, verify = consume("작품A 이거 하렘임?")
    assert "확인하려는 질문" in identity.reason and "특성을 확정하지" in identity.reason and verify()
    _, _, identity, _, verify = consume("주인공은 빌런이었어야돼")
    assert "반사실" in identity.reason and "실제 작품이 그렇게" in identity.reason and verify()


def test_food_plan_and_limit_are_explained_as_personal_statements():
    _, _, identity, notes, verify = consume("저녁 대안 질문", "편의점에서 간식 사서 떼우려는데",
        "이보다 나은 대안 있으면 말해주오", "감기 걸려서 차가운건 못먹음")
    assert "식사 계획" in identity.reason and "대안" in identity.primary_subject_text
    assert "먹지 못한다고 말한다" in notes and verify()
    _, _, identity, _, verify = consume("소프트웨어 선택", "플러그인 사서 쓰려는데", "이보다 나은 대안 있으면 말해주오")
    assert "식사 계획" not in identity.reason and verify()


def test_serialisation_wish_and_conditional_return_keep_noncompleted_scope():
    _, _, identity, _, verify = consume("기다리는표면 연재 바라지도 않음", "그냥 일기나 써서 올리면 좋겠다")
    assert "바라지는 않으며" in identity.reason and "일기" in identity.primary_subject_text and verify()
    _, _, identity, _, verify = consume("나도 해지 해야겠다 기대작 완결 나면 돌아옴")
    assert "해지할 의사" in identity.reason and "복귀 조건" in identity.reason and verify()


def test_name_interpretation_revision_does_not_authenticate_person_or_role():
    _, _, identity, _, verify = consume("그 표시명이 작가 이름인줄 알았더니", "파딱 고로시였누..")
    assert "다시 이해" in identity.reason and "파딱" in identity.reason
    assert identity.novel_identity is None and verify()


def test_unbound_carrier_keeps_fallback_without_new_semantic_authority():
    post = PostInput(post_id=5, title="큰 판이 의외였음")
    pipeline = AgenticPipeline(llm=object(), mcp=object(), max_iterations=2)
    ctx = ConversationContext(post_id=5, post_data=pipeline._post_to_dict(post), comments=[])
    identity = PickvelIdentity(is_relevant=False, discussion_type="general")
    _, verify = pipeline._consume_final_source_context(ctx, identity, None)
    assert ctx._final_source_projection_consumption["status"] == "HOLD_UNBOUND"
    assert ctx._final_source_context_explanation is None and not verify()


def test_quoted_recommendation_phrase_is_a_question_about_meaning():
    _, _, identity, _, verify = consume("작품A 추천해줘는 무슨 뜻임?")
    assert "추천해 달라는 요청" not in identity.reason
    assert identity.novel_identity is None and verify()


def test_plan_and_reading_scope_keep_the_current_source_predicate():
    _, _, identity, _, verify = consume("점심 먹고 소프트웨어를 고르는중", "플러그인 사서 쓰려는데", "이보다 나은 대안 있으면 말해주오")
    assert "식사 계획" not in identity.reason and verify()
    _, _, identity, _, verify = consume("작품A 감상", "작품A 끝까지 다 읽었는데 대사가 오글거려")
    assert "끝까지 읽었다고 밝힌" in identity.reason
    assert "부분 독서 범위" not in identity.reason and verify()
