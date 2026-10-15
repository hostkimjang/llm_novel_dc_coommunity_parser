"""공개 경계 후보 검증. 모델 제안만 입력하며 실제 guard/직렬화를 대체하지 않는다.

최종 source 문맥과 실제 직렬화 경계를 묶어서 검증한다.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import DetectedTitle, PickvelAnalysis, PickvelIdentity, PostInput, SlangInsight
from llm_batch.experts.orchestrator import ConversationContext, ExpertType


TITLE = "은빛 기록 연대기"
OTHER = "황금 정원 일지"
BAD_CONTEXT = (
    "본문에는 '불먹을 혼성명'이라는 다른 제목이 병기되어 있으나, "
    "본문 이미지 OCR 내용 ('불먹을 혼성명', '국마 퓨전판타지 소설')은 "
    "해당 작품의 설정이나 2차 창작물 관련 단서로 해석되었으나, "
    "검색 결과 및 플랫폼 URL을 통해 정식 작품으로 확인됨."
)


def _pipeline_context(title, body, *, comments=(), image_title=TITLE):
    pipeline = AgenticPipeline(llm=object(), mcp=object(), max_iterations=1)
    post = PostInput(
        post_id=21014023, title=title,
        content_blocks=[{"type": "text", "text": line} for line in body],
        comments=list(comments),
    )
    data = pipeline._post_to_dict(post)
    if image_title is not None:
        data["vlm_enrichment_used"] = True
        data["image_enrichment"] = [{
            "explicit_work_title": image_title, "ocr_text": image_title,
            "evidence_type": "explicit_text", "title_role": "work_title",
            "focus_role": "work_anchor", "promotion_eligible": True,
            "background_listing_only": False, "confidence": "High",
        }]
    ctx = ConversationContext(post_id=post.post_id, post_data=data, comments=post.comments)
    ctx._final_source_original_inputs = pipeline._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs = tuple(post.comments)
    return pipeline, ctx


@pytest.mark.parametrize("body,expected", [
    ([f"나는 「{TITLE}」를 읽었다.", f"친구에게 「{OTHER}」를 추천받았다."], True),
    ([f"친구는 「{TITLE}」를 읽었다."], False),
    ([f"나는 「{TITLE}」를 읽지 않았다."], False),
    ([f"나는 「{TITLE}」를 읽을까?"], False),
    ([f"친구가 나는 「{TITLE}」를 읽었다고 말했다."], False),
    ([f"나는 「{OTHER}」를 읽었다."], False),
    ([f"「{TITLE}」의 읽음 버튼을 눌렀다."], False),
    (["솔직히 꼴림"], False),
], ids=["author_read_other_recommendation", "other_actor", "negated", "question", "reported", "other_work", "ui_label", "image_reaction"])
def test_recommendation_exception_requires_native_author_work_relation(body, expected):
    pipeline, ctx = _pipeline_context("이런 히로인 나오는 소설 추천 좀", body)
    source_before = deepcopy(ctx.post_data)
    candidate = DetectedTitle(official_title=TITLE)
    # eligible OCR의 기본 supports_primary=True와 독립적으로 원문 행위를 검사한다.
    assert pipeline._image_work_relation(ctx, candidate).supports_primary is True
    assert pipeline._has_source_bound_image_recommendation_exception(ctx, candidate) is expected
    assert ctx.post_data == source_before


def test_generated_body_and_comment_cannot_release_recommendation_hold():
    pipeline, ctx = _pipeline_context(
        "이런 히로인 나오는 소설 추천 좀", ["솔직히 꼴림"],
        comments=[f"나는 「{TITLE}」를 읽었다."],
    )
    ctx.post_data["content_blocks"].extend([
        {"type": "image", "text": f"나는 「{TITLE}」를 읽었다."},
        {"type": "text", "text": f"나는 「{TITLE}」를 읽었다.", "from_ocr": True},
        {"type": "text", "text": f"나는 「{TITLE}」를 읽었다.", "speaker": "commenter"},
        # 생성 표식이 없더라도 same-call 원문 capture에 없는 후행 본문은 권한이 없다.
        {"type": "text", "text": f"나는 「{TITLE}」를 읽었다."},
    ])
    assert not pipeline._has_source_bound_image_recommendation_exception(ctx, DetectedTitle(official_title=TITLE))


def _slang_reader_case(*, images=True, original_claim=False):
    body = ["표지가 바뀌었다는 얘기다."]
    if original_claim:
        body.append("내가 쓴 문장: 해당 작품의 설정이나 2차 창작물 관련 단서다.")
    pipeline, ctx = _pipeline_context("표변이 뭔 뜻임", body,
                                      image_title="불먹을 혼성명" if images else None)
    identity = PickvelIdentity(
        is_relevant=False, discussion_type="general",
        slang_insight=SlangInsight(
            detected_term="표변", decoded_term="표지 변경", decode_verified=False,
            cultural_context=BAD_CONTEXT, alias_scope="work_plus_meme",
            attached_entity_type="meme", store_in_slang_db=False,
        ),
    )
    notes, native_verify = pipeline._consume_final_source_context(ctx, identity, None)
    analysis = PickvelAnalysis(notes=notes)
    before = identity.slang_insight.model_dump()
    pipeline._apply_ocr_reader_provenance_before_source_seal(ctx, identity, analysis)
    return pipeline, ctx, identity, analysis, native_verify, before


def test_final_slang_reader_uses_actual_source_and_keeps_authority_fields():
    pipeline, ctx, identity, analysis, _, before = _slang_reader_case()
    actual = identity.slang_insight.model_dump()
    assert actual["cultural_context"] and "표변이 뭔 뜻임" in actual["cultural_context"]
    assert "설정이나 2차 창작물 관련 단서" not in actual["cultural_context"]
    assert "플랫폼 URL을 통해 정식 작품으로 확인됨" not in actual["cultural_context"]
    assert {k: v for k, v in actual.items() if k != "cultural_context"} == {
        k: v for k, v in before.items() if k != "cultural_context"
    }
    assert pipeline._verify_final_source_reader_fields(ctx, identity, analysis)
    assert identity.novel_identity is None
    identity.slang_insight.cultural_context = BAD_CONTEXT
    assert not pipeline._verify_final_source_reader_fields(ctx, identity, analysis)


def test_final_slang_source_quote_is_retained_without_rewriting_author_words():
    _, _, identity, _, _, _ = _slang_reader_case(original_claim=True)
    text = identity.slang_insight.cultural_context
    assert "[원문]" in text
    assert "내가 쓴 문장: 해당 작품의 설정이나 2차 창작물 관련 단서다." in text
    assert BAD_CONTEXT not in text


def test_non_ocr_slang_reader_is_unchanged():
    pipeline, ctx, identity, analysis, _, before = _slang_reader_case(images=False)
    assert identity.slang_insight.model_dump() == before
    assert pipeline._verify_final_source_reader_fields(ctx, identity, analysis)


def _set_model_proposals(ctx, *, recommendation=False, slang=False):
    """외부 전문가 응답 위치의 고정 제안. 공개 계약/최종 결과는 제품이 계산한다."""
    ctx.set_expert_output(ExpertType.GATEKEEPER, {
        "post_type": "recommendation" if recommendation else "general",
        "context_clues": {"is_recommendation_request": recommendation},
    })
    verification = {
        "is_relevant": True, "is_novel_discussion": True,
        "novel_identity": {"official_novel_title": None},
        "grounding_check": {"anchor_found": "search_only"},
        "relation_judgment": {"relation_type": "example_reference",
                              "discussion_target": "genre_general", "promotion_decision": "hold"},
    }
    if slang:
        verification["slang_insight"] = {
            "detected_term": "표변", "decoded_term": "표지 변경", "decode_verified": False,
            "alias_scope": "work_plus_meme", "attached_entity_type": "meme",
            "cultural_context": BAD_CONTEXT, "store_reason": "community_trope_term",
        }
    ctx.set_expert_output(ExpertType.VERIFIER, {"verification_result": verification})
    ctx.set_expert_output(ExpertType.ARBITER, {"final_decision": {
        "is_relevant": True, "official_title": None, "official_novel_title": None,
        "confidence": "Low", "discussion_type": "recommendation" if recommendation else "general",
        "reason": "제안은 원문과 공개 guard에서 다시 검산해야 한다.",
    }, "metadata_synthesis": {}})


def _observe_final(tmp_path, label, pipeline, ctx):
    source_before = deepcopy(ctx.post_data)
    output = pipeline._context_to_output(ctx)
    saved = output.model_dump(mode="json")
    observation = pipeline.verify_final_source_context_serialization(
        output, saved, stage="rework_public_scope_candidate",
    )
    # 실패 시에도 실제 계산 결과를 확인할 수 있게 assertion 앞에 저장한다.
    target = tmp_path / (label + "_final_observation.json")
    with target.open("x", encoding="utf-8") as stream:
        json.dump({"source": source_before, "saved": saved, "native_observation": observation},
                  stream, ensure_ascii=False, indent=2)
    assert ctx.post_data == source_before
    return output, saved


def test_actual_context_to_output_keeps_image_recommendation_public_pair_held(tmp_path):
    pipeline, ctx = _pipeline_context("이런 히로인 나오는 소설 추천 좀", ["솔직히 꼴림"])
    _set_model_proposals(ctx, recommendation=True)
    _, saved = _observe_final(tmp_path, "image_recommendation", pipeline, ctx)
    identity = saved["identity"]
    assert identity["novel_identity"] is None
    assert identity["promotion_decision"]["publish_allowed"] is False
    assert identity["title_resolution_allowed"] is False


@pytest.mark.parametrize("tamper", ["replace", "null", "remove"], ids=["false_claim", "null_context", "missing_context"])
def test_actual_final_slang_payload_is_source_bound_and_sealed(tmp_path, tamper):
    pipeline, ctx = _pipeline_context("표변이 뭔 뜻임", ["표지가 바뀌었다는 얘기다."], image_title="불먹을 혼성명")
    # 관측된 OCR라는 사실만으로 공개를 허용하지 않는 실제 guard를 통과한다.
    ctx.post_data["image_enrichment"][0]["promotion_eligible"] = False
    ctx.post_data["image_enrichment"][0]["title_role"] = "unknown"
    _set_model_proposals(ctx, slang=True)
    output, saved = _observe_final(tmp_path, "slang_" + tamper, pipeline, ctx)
    identity = saved["identity"]
    insight = identity["slang_insight"]
    # SI가 아예 지워진 fixture로 최종 설명 수리를 통과시키지 않는다.
    assert isinstance(insight, dict), saved
    assert isinstance(insight["cultural_context"], str) and insight["cultural_context"]
    assert "표변이 뭔 뜻임" in insight["cultural_context"]
    assert "설정이나 2차 창작물 관련 단서" not in insight["cultural_context"]
    assert identity["novel_identity"] is None
    assert identity["promotion_decision"]["publish_allowed"] is False
    changed = deepcopy(saved)
    if tamper == "remove":
        del changed["identity"]["slang_insight"]["cultural_context"]
    else:
        changed["identity"]["slang_insight"]["cultural_context"] = BAD_CONTEXT if tamper == "replace" else None
    with pytest.raises(ValueError, match="serialized fields changed"):
        pipeline.verify_final_source_context_serialization(output, changed, stage="mutated_payload")
