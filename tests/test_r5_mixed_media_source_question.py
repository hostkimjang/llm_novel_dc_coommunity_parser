"""실제64 저장 응답을 재생해 작품 질문/플랫폼 장애의 초기 분기를 검증한다."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket

import pytest

from llm_batch.experts.orchestrator import ConversationContext, ExpertType, Orchestrator


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("저장 응답 재생 중 외부 호출 금지")
    monkeypatch.setattr(socket.socket, "connect", forbidden)


def saved():
    path = Path(__file__).parent / "fixtures/r5_row64_mixed_media_boundary.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == "d2105a96ecf7f14892dad377231eb1b989ca361ac2609bfb5572d1e1e49ea4c4"
    return json.loads(path.read_text(encoding="utf-8"))


def context(observation):
    fixture = saved()
    ctx = ConversationContext(post_id=fixture["post"]["post_id"],
                              post_data=deepcopy(fixture["post"]), comments=[])
    ctx.set_expert_output(ExpertType.GATEKEEPER, deepcopy(observation["gatekeeper"]))
    ctx.set_expert_output(ExpertType.DISCOURSE, deepcopy(observation["discourse"]))
    return ctx


@pytest.mark.parametrize("arm", ["bootstrap", "before"])
def test_saved_row64_work_question_does_not_take_platform_early_return(arm):
    observation = next(row for row in saved()["observations"] if row["arm"] == arm)
    ctx = context(observation)
    orch = Orchestrator.__new__(Orchestrator)
    gate = ctx.get_expert_output(ExpertType.GATEKEEPER)
    assert gate["post_type"] == "meta_platform"  # 실제 잘못된 후처리도 그대로 재생
    assert gate["context_clues"]["meta_platform_issue_detected"] is True
    assert orch._has_source_bound_work_reading_question(ctx)
    assert not orch._is_meta_platform_issue_context(ctx, gate)
    # 제목 승인/최종 판정을 만들어내지 않는다. 후속 작품 검토만 허용한다.
    assert not ctx.get_expert_output(ExpertType.DECODER)
    assert not ctx.get_expert_output(ExpertType.ARBITER)


@pytest.mark.parametrize("mutation", ["no_novel_secondary", "malformed_secondary",
    "platform_primary", "missing_receipt", "wrong_receipt", "other_speaker",
    "not_work", "not_specific", "association", "inconsistent", "incoherent",
    "platform_body", "quoted_reading"])
def test_mixed_media_exception_retains_original_source_guards(mutation):
    ctx = context(saved()["observations"][1])
    da = ctx.get_expert_output(ExpertType.DISCOURSE)["discourse_analysis"]
    if mutation == "no_novel_secondary": da["secondary_domains"] = ["games"]
    elif mutation == "malformed_secondary": da["secondary_domains"] = "novel_literature"
    elif mutation == "platform_primary": da["primary_domain"] = "meta_platform"
    elif mutation == "missing_receipt": da.pop("source_bound_question_receipt")
    elif mutation == "wrong_receipt": da["source_bound_question_receipt"]["span"] = "다른 작품 재밌냐"
    elif mutation == "other_speaker": da["source_bound_question_receipt"]["speaker"] = "commenter"
    elif mutation == "not_work": da["target_kind"] = "platform"
    elif mutation == "not_specific": da["semantic_seed_review"]["is_specific_work_discussion"] = False
    elif mutation == "association": da["is_association_not_discussion"] = True
    elif mutation == "inconsistent": da["title_body_consistency"] = False
    elif mutation == "incoherent": da["is_coherent"] = False
    elif mutation == "platform_body":
        ctx.post_data["content_blocks"] = [{"type": "text", "text": "광고 쿠키 매칭이 안되어서 다운로드 오류가 남"}]
    elif mutation == "quoted_reading":
        ctx.post_data["content_blocks"] = [{"type": "text", "text": "소설판은 접었다고 들었음"}]
    orch = Orchestrator.__new__(Orchestrator)
    assert not orch._has_source_bound_work_reading_question(ctx)
    assert orch._is_meta_platform_issue_context(ctx, ctx.get_expert_output(ExpertType.GATEKEEPER))


def test_unrelated_platform_matching_failure_is_not_work_review():
    ctx = context(saved()["observations"][1])
    ctx.post_data["title"] = "광고 쿠키 매칭 안됨"
    ctx.post_data["content_blocks"] = [{"type": "text", "text": "시리즈 회차 다운로드가 안됨"}]
    orch = Orchestrator.__new__(Orchestrator)
    assert not orch._has_source_bound_work_reading_question(ctx)
    assert orch._is_meta_platform_issue_context(ctx, ctx.get_expert_output(ExpertType.GATEKEEPER))


def test_mixed_media_rule_is_not_tied_to_actual64_title_or_id():
    ctx = context(saved()["observations"][1])
    ctx.post_id = 123
    ctx.post_data.update(post_id=123, title="가상작품 재밌냐",
        content_blocks=[{"type": "text", "text": "소설판은 인물 묘사가 싫어서 하차했음"}])
    da = ctx.get_expert_output(ExpertType.DISCOURSE)["discourse_analysis"]
    da["title_novel_terms"] = ["가상작품"]
    da["source_bound_question_receipt"].update(span="가상작품 재밌냐",
        target_description="가상작품", target_candidates=["가상작품"])
    orch = Orchestrator.__new__(Orchestrator)
    assert orch._has_source_bound_work_reading_question(ctx)
    assert not orch._is_meta_platform_issue_context(ctx, ctx.get_expert_output(ExpertType.GATEKEEPER))
