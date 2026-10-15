"""공식 제목 보류와 분리된 저자 원문 작품 담론의 국소 경계."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import PostInput
from llm_batch.experts.orchestrator import ConversationContext, ExpertType, Orchestrator
from llm_batch.promotion_gate import GroundingState, ScopeState, evaluate_publish_contract


def _context(title, body, *, target_kind="work", terms=(), receipt=None):
    post = {"post_id": 1, "title": title,
            "content_blocks": [{"type": "text", "text": part}
                               for part in (body if isinstance(body, (tuple, list)) else (body,))]}
    ctx = ConversationContext(post_id=1, post_data=post, comments=[])
    da = {"primary_domain": "novel_literature", "target_kind": target_kind,
          "is_coherent": True, "title_body_consistency": True,
          "is_association_not_discussion": False,
          "title_novel_terms": list(terms),
          "semantic_seed_review": {"is_specific_work_discussion": True}}
    if receipt is not None:
        da["source_bound_question_receipt"] = {
            "span": title, "source": "author_title", "speaker": "author",
            "modality": "text", "position": 0,
            "target_description": receipt, "target_conflict": False,
        }
    ctx.set_expert_output(ExpertType.DISCOURSE, {"discourse_analysis": da})
    return ctx


def test_edition_reading_question_overrides_wrong_platform_issue_only_with_source_receipt():
    title = "나혼렙 재밌냐"
    ctx = _context(title, "소설판은 주인공 유형을 싫어해서 접었음.",
                   terms=("나혼렙",), receipt="작품 '나 혼자만 레벨업'")
    orch = Orchestrator.__new__(Orchestrator)
    wrong_gate = {"post_type": "meta_platform", "context_clues": {"meta_platform_issue_detected": True}}
    assert orch._has_source_bound_work_reading_question(ctx)
    assert not orch._is_meta_platform_issue_context(ctx, wrong_gate)
    ctx.post_data["content_blocks"] = [{"type": "text", "text": "플랫폼 결제가 안 됨"}]
    assert not orch._has_source_bound_work_reading_question(ctx)
    assert orch._is_meta_platform_issue_context(ctx, wrong_gate)
    ctx.post_data["content_blocks"] = [{"type": "text", "text": "소설판은 접었음"}]
    ctx.get_expert_output(ExpertType.DISCOURSE)["discourse_analysis"]["semantic_seed_review"]["is_specific_work_discussion"] = False
    assert orch._is_meta_platform_issue_context(ctx, wrong_gate)


def test_unresolved_work_question_keeps_reading_scope_without_title_authority():
    pipeline = AgenticPipeline(llm=object(), mcp=object())
    ctx = _context("그런의미로 마왕의게임<< 보지픽 가능함?", "난 이거 중도하차함")
    assert pipeline._has_source_bound_unresolved_work_question_reading_context(ctx)
    ctx.post_data["content_blocks"] = [{"type": "text", "text": "댓글에서 중도하차함이라고 들음"}]
    assert not pipeline._has_source_bound_unresolved_work_question_reading_context(ctx)
    ctx.post_data["content_blocks"] = [{"type": "text", "text": "다른작품은 중도하차함"}]
    assert not pipeline._has_source_bound_unresolved_work_question_reading_context(ctx)
    ctx.post_data["content_blocks"] = [{"type": "text", "text": "마왕의게임은 중도하차함"}]
    assert pipeline._has_source_bound_unresolved_work_question_reading_context(ctx)
    ctx.post_data["content_blocks"] = [{"type": "text", "text": "이거는 중도하차함"}]
    assert pipeline._has_source_bound_unresolved_work_question_reading_context(ctx)
    ctx.post_data["title"] = "빙의, 회귀물에선 보통 숨길 수 있나?"
    ctx.post_data["content_blocks"] = [{"type": "text", "text": "난 중도하차함"}]
    assert not pipeline._has_source_bound_unresolved_work_question_reading_context(ctx)


def test_anticipation_alias_needs_independent_nonfanfic_relation():
    pipeline = AgenticPipeline(llm=object(), mcp=object())
    ctx = _context("무친년 연재 바라지도 않음", "그냥 일기나 써서 올리면 좋겠다",
                   target_kind="author")
    ctx.search_results = [{"title": "이 무림의 미친년은 나야",
                           "snippet": "한국 웹소설. 약칭은 무친년, 연재 현황이 있다."}]
    assert pipeline._has_source_bound_unresolved_work_anticipation_context(ctx)
    ctx.search_results = [{"title": "무친년 단편 팬픽",
                           "snippet": "노벨피아 웹소설 무친년 팬픽 작품"}]
    assert not pipeline._has_source_bound_unresolved_work_anticipation_context(ctx)
    ctx.search_results = [{"title": "이 무림의 미친년은 나야",
                           "snippet": "한국 웹소설. 약칭은 무친년, 연재 현황이 있다."}]
    ctx.post_data["content_blocks"] = [{"type": "text", "text": "그냥 일기까지 바라지는 않음"}]
    assert not pipeline._has_source_bound_unresolved_work_anticipation_context(ctx)


def test_source_bound_a_cases_survive_final_storage_with_official_identity_held():
    pipeline = AgenticPipeline(llm=object(), mcp=object(), max_iterations=1)
    cases = (
        _context("나혼렙 재밌냐", (
                 "웹툰판은 처음의 그 어리버리랑 광고에 뜨는 쿨가이 캐릭이 매칭이 안되어서 손 떼고",
                 "소설판은 내가 소환물 부려서 웃기지도 않는 티티카타하면서 잘난 척하는 주인공 유형(박제후 꺼 같은)을 싫어해서 접었음.",
                 "끝까지 읽으면 읽을만했다고 느낌?",
                 ),
                 terms=("나혼렙",), receipt="작품 '나 혼자만 레벨업'"),
        _context("그런의미로 마왕의게임<< 보지픽 가능함?", "난 이거 중도하차함"),
        _context("무친년 연재 바라지도 않음", ("그냥 일기나 써서 올리면 좋겠다", "- dc official App"),
                 target_kind="author"),
    )
    cases[2].search_results = [{"title": "이 무림의 미친년은 나야",
                                "snippet": "한국 웹소설. 약칭은 무친년, 연재 현황이 있다."}]
    for ctx in cases:
        ctx.set_expert_output(ExpertType.GATEKEEPER, {"post_type": "work_discussion"})
        ctx.set_expert_output(ExpertType.VERIFIER, {"verification_result": {
            "is_relevant": True, "is_novel_discussion": True,
            "novel_identity": {"official_novel_title": None},
            "grounding_check": {"anchor_found": "title_mention"},
            "inference": {"type": "work_discussion"},
        }})
        ctx.set_expert_output(ExpertType.ARBITER, {"final_decision": {
            "is_relevant": True, "official_title": None, "official_novel_title": None,
            "confidence": "Low", "discussion_type": "work_discussion",
            "_title_deliberately_null": True,
            "reason": "작성자 원문에 묶인 작품 담론", "final_reasoning": "작성자 원문에 묶인 작품 담론",
        }, "metadata_synthesis": {}})
        output = pipeline._context_to_output(ctx)
        saved = output.model_dump(mode="json")
        identity = saved["identity"]
        assert identity["is_relevant"] is True, identity.get("consistency_flags")
        assert identity["novel_identity"] is None
        assert ctx.post_data["title"] in identity["reason"]
        assert saved["analysis"] is None or isinstance(saved["analysis"], dict)
        assert "official_title" not in (saved["analysis"] or {})


def test_other_work_drop_does_not_gain_final_relevance_from_question_title():
    pipeline = AgenticPipeline(llm=object(), mcp=object(), max_iterations=1)
    ctx = _context("그런의미로 마왕의게임<< 보지픽 가능함?", "다른작품은 중도하차함")
    ctx.set_expert_output(ExpertType.GATEKEEPER, {"post_type": "work_discussion"})
    ctx.set_expert_output(ExpertType.VERIFIER, {"verification_result": {
        "is_relevant": True, "is_novel_discussion": True,
        "novel_identity": {"official_novel_title": None},
        "grounding_check": {"anchor_found": "title_mention"},
    }})
    ctx.set_expert_output(ExpertType.ARBITER, {"final_decision": {
        "is_relevant": True, "official_title": None, "official_novel_title": None,
        "confidence": "Low", "discussion_type": "work_discussion",
        "_title_deliberately_null": True,
    }, "metadata_synthesis": {}})
    assert not pipeline._has_source_bound_unresolved_work_question_reading_context(ctx)
    saved = pipeline._context_to_output(ctx).model_dump(mode="json")
    assert saved["identity"]["is_relevant"] is False
    assert saved["identity"]["novel_identity"] is None


@pytest.mark.parametrize("late_eids,body_override,expected_relevant", [
    ({"SR001", "SR003"}, None, True),
    ({"SR003"}, None, False),
    ({"SR001"}, "그냥 일기까지 바라지는 않음", False),
])
def test_a58_late_alias_recall_restores_relevance_but_keeps_publication_held(
    monkeypatch, late_eids, body_override, expected_relevant,
):
    record = json.loads(
        (Path(__file__).resolve().parent / "fixtures"
         / "fourth80_rows_26_58_63_integration_evidence.json").read_text(encoding="utf-8")
    )["records"]["58"]
    post = dict(record["original_post_full"])
    if body_override is not None:
        post["content_blocks"] = [{"type": "text", "text": body_override}]
    comments = record["original_comments_full"]
    pipeline = AgenticPipeline(llm=object(), mcp=object(), max_iterations=1)
    post_input = PostInput(
        post_id=post["post_id"], title=post["title"], author=post["author"],
        content_blocks=post["content_blocks"], comments=comments,
    )
    ctx = ConversationContext(
        post_id=post["post_id"], post_data=pipeline._post_to_dict(post_input),
        comments=comments,
    )
    ctx._final_source_original_inputs = pipeline._capture_final_source_original_inputs(post_input)
    ctx._final_source_original_comment_refs = tuple(comments)
    ctx._last_publish_contract = evaluate_publish_contract(
        GroundingState(
            post_id=post["post_id"], candidate_title="", candidate_url="",
            source="early_no_search", official_title_exists=False,
            row_discusses_work_as_work=False, title_resolution_state="context_only",
            work_resolution="none", discussion_type="noise",
            scope=ScopeState(scope_kind="unknown", confidence="low"),
        ),
        [], post_gate_context={"work_resolution": "none", "discussion_type": "noise"},
    )
    for name in ("gatekeeper", "discourse", "decoder", "verifier", "arbiter"):
        ctx.set_expert_output(
            getattr(ExpertType, name.upper()),
            record["sealed_expert_outputs"][name][-1]["data"],
        )
    assert ctx.search_results == []
    early_validator = pipeline._apply_output_consistency_validator
    delivered = []

    def deliver_after_early_validator(*args, **kwargs):
        result = early_validator(*args, **kwargs)
        assert not ctx.search_results
        assert "source_bound_unresolved_work_anticipation" not in set(
            result.get("consistency_flags") or ()
        )
        ctx.search_results = [
            item for item in record["stored_search_evidence_catalog"]
            if item["eid"] in late_eids
        ]
        delivered.append(True)
        return result

    monkeypatch.setattr(
        pipeline, "_apply_output_consistency_validator", deliver_after_early_validator
    )
    saved = pipeline._context_to_output(ctx).model_dump(mode="json")
    identity = saved["identity"]
    assert delivered == [True]
    assert identity["is_relevant"] is expected_relevant
    assert identity["novel_identity"] is None
    assert identity["title_resolution_allowed"] is False
    assert identity["is_resolved_work_discussion"] is False
    assert identity["promotion_decision"]["publish_allowed"] is False
    if not expected_relevant:
        assert "source_bound_unresolved_work_anticipation" not in (
            identity["consistency_flags"] or []
        )
        return
    assert identity["is_relevant"] is True
    assert identity["is_novel_related"] is True
    assert identity["topicality"] == "core_relevant"
    assert identity["relevance_scope"] == "core"
    assert identity["discussion_type"] == "anticipation"
    assert identity["subtype"] == "unresolved_work"
    assert identity["work_resolution"] == "unresolved"
    assert "source_bound_unresolved_work_anticipation" in identity["consistency_flags"]
    assert identity["publish_contract_trace"]["post_gate_identity"]["work_resolution"] == "unresolved"
    assert any(item["eid"] == "SR001" for item in identity["search_evidence_catalog"])
    assert "무친년 연재 바라지도 않음" in identity["reason"]
    assert "일기나 써서 올리면 좋겠다" in identity["reason"]
    assert "특정 작품에 대한 토론이 아닌" not in identity["reason"]
