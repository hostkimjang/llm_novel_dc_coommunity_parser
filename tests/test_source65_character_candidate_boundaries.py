"""65 v1의 F1/F2/F3 반례. 원형 42사례는 별도 파일 그대로 실행한다."""
from copy import deepcopy
import json
import math

import pytest

from test_source65_character_candidate_preservation import (
    pipeline, synthetic_context,
)
from llm_batch.domain.alias_learning import capture_alias_source
from llm_batch.domain.models import DetectedTitle
from llm_batch.grounding.character_work_candidate import (
    CHARACTER_WORK_CANDIDATE_HOLD, _digest, character_work_candidates,
)


def raw_snapshot(ctx):
    # 입력 불변 비교용이며 proof hash가 아니다. NaN 원형 자체를 보존했는지 확인한다.
    return json.dumps([ctx.post_data, ctx.comments, ctx.expert_outputs, ctx.search_results],
        ensure_ascii=False, sort_keys=True, allow_nan=True)


@pytest.mark.parametrize("where", ["term", "row"])
@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_metadata_isolated_without_relaxing_strict_digest_or_existing_candidates(pipeline, where, number):
    ctx = synthetic_context()
    target = ctx.expert_outputs["decoder"]["decoded_terms"][0] if where == "term" else ctx.search_results[0]
    target["debug_quality"] = number
    normal = "독립 항로의 기록"
    ctx.post_data["content_blocks"] = [{"type": "text", "text": f"소설 「{normal}」를 읽었다."}]
    before = raw_snapshot(ctx)
    with pytest.raises(ValueError):
        _digest(target)  # allow_nan=False 원형 규칙은 바꾸지 않는다.
    assert character_work_candidates(ctx) == []
    existing = [(7, False, {"title": normal, "confidence": "Medium", "url": None, "alias": None, "locked": False})]
    candidates, snapshot = pipeline._finalize_title_candidate_generation(
        scored=existing, final_norm="", max_items=6, ctx=ctx)
    assert len(candidates) == 1 and candidates[0].official_title == normal
    assert candidates[0].confidence == "Medium"
    assert CHARACTER_WORK_CANDIDATE_HOLD not in (candidates[0].negative_evidence or [])
    annotated, primary, _, _ = pipeline._annotate_work_references(ctx=ctx,
        title_candidates=[DetectedTitle(official_title=normal, confidence="High", reference_role="candidate")],
        official_title=normal, vf_result={})
    assert primary is not None and primary.official_title == normal
    assert any(c.official_title == normal for c in annotated)
    assert raw_snapshot(ctx) == before
    if math.isnan(number):
        assert math.isnan(target["debug_quality"])
    else:
        assert target["debug_quality"] == number


@pytest.mark.parametrize("where", ["term", "row"])
def test_bad_relation_does_not_remove_an_independent_valid_new_candidate(where):
    bad = synthetic_context()
    good = synthetic_context("별빛 문답", "백도윤")
    target = bad.expert_outputs["decoder"]["decoded_terms"][0] if where == "term" else bad.search_results[0]
    target["debug_quality"] = float("nan")
    bad.post_data["content_blocks"] = [{"type": "text", "text": good.post_data["title"]}]
    bad.expert_outputs["decoder"]["decoded_terms"].extend(deepcopy(good.expert_outputs["decoder"]["decoded_terms"]))
    bad.search_results.extend(deepcopy(good.search_results))
    before = raw_snapshot(bad)
    assert [p["title"] for p in character_work_candidates(bad)] == ["별빛 문답"]
    assert raw_snapshot(bad) == before


HEADER = "개요 웹소설 은월전의 등장인물을 정리한 문서. "
POSITIVE = "서하진과 마주쳤다. "


@pytest.mark.parametrize("negative", [
    "서하진은 이 작품의 등장인물이 아니다.",
    "서하진은 은월전의 등장인물이 아니다.",
    "서하진은 이 작품에 등장하지 않는다.",
    "서하진은 이 작품의 등장인물이라는 설명은 취소됐다.",
])
@pytest.mark.parametrize("where", ["same_field_after", "same_field_before", "content_against_snippet"])
def test_same_owner_person_contradiction_blocks_any_positive_occurrence(negative, where):
    ctx = synthetic_context()
    row = ctx.search_results[0]
    if where == "same_field_after": row["snippet"] = HEADER + POSITIVE + negative
    elif where == "same_field_before": row["snippet"] = HEADER + negative + POSITIVE
    else:
        row["content"] = negative  # 같은 row 소유 문서. 부정 field에 긍정 표제를 재요구하지 않는다.
        row["snippet"] = HEADER + POSITIVE
    before = raw_snapshot(ctx)
    assert character_work_candidates(ctx) == []
    assert raw_snapshot(ctx) == before


@pytest.mark.parametrize("negative", [
    "백도윤은 이 작품의 등장인물이 아니다.",
    "서하진은 다른작품의 등장인물이 아니다.",
    "서하진은 이 작품의 등장인물이라는 설명은 취소하지 않았다.",
])
@pytest.mark.parametrize("where", ["same_field", "cross_field"])
def test_unrelated_person_or_other_work_denial_is_not_global_veto(negative, where):
    ctx = synthetic_context()
    if where == "same_field":
        ctx.search_results[0]["snippet"] = HEADER + POSITIVE + negative
    else:
        ctx.search_results[0]["content"] = negative
        ctx.search_results[0]["snippet"] = HEADER + POSITIVE
    proofs = character_work_candidates(ctx)
    assert len(proofs) == 1 and proofs[0]["character"] == "서하진"


def quoted_body(blocks):
    ctx = synthetic_context()
    anchor = ctx.post_data["title"]
    ctx.post_data["title"] = "인물 질문"
    ctx.post_data["content_blocks"] = [
        {"type": "text", "text": value.replace("ANCHOR", anchor)} if isinstance(value, str)
        else {**value, **({"text": value["text"].replace("ANCHOR", anchor)} if "text" in value else {})}
        for value in blocks
    ]
    ctx._batch_alias_original_source = capture_alias_source(ctx.post_data)
    return ctx


@pytest.mark.parametrize("blocks", [
    ['친구가 말했다: "', 'ANCHOR', '"'],
    ['친구가 말했다: “', 'ANCHOR', '”'],
    [{"type": "blockquote", "text": '친구가 말했다: "'}, 'ANCHOR', '"'],
    ['친구가 말했다: "', {"type": "image", "url": "https://example.com/x.png"}, 'ANCHOR', '"'],
])
def test_original_capture_matching_open_quote_crosses_body_fields(blocks):
    ctx = quoted_body(blocks)
    before = raw_snapshot(ctx)
    assert character_work_candidates(ctx) == []
    assert raw_snapshot(ctx) == before


@pytest.mark.parametrize("blocks,author_index", [
    (['친구가 말했다: "', 'ANCHOR', '"', '나는 궁금하다. ANCHOR'], 3),
    ([{"type": "blockquote", "text": '친구가 말했다: "'}, 'ANCHOR', '"', '나는 궁금하다. ANCHOR'], 3),
    (['친구가 말했다: "', 'ANCHOR', '"\n나는 궁금하다. ANCHOR'], 2),
])
def test_closed_quote_preserves_only_later_independent_author_occurrence(blocks, author_index):
    ctx = quoted_body(blocks)
    proofs = character_work_candidates(ctx)
    assert len(proofs) == 1
    occurrences = proofs[0]["source_occurrences"]
    assert occurrences and all(x["source"] == "author_body" and x["original_index"] == author_index for x in occurrences)
    for item in occurrences:
        assert item["raw_text"][slice(*item["raw_span"])] == "서하진"


@pytest.mark.parametrize("derived", [
    {"type": "image", "url": "https://example.com/x.png", "text": '"'},
    {"type": "text", "text": '[이미지 OCR] "', "from_ocr": True},
])
def test_independent_image_or_ocr_quote_cannot_open_author_speech_scope(derived):
    ctx = quoted_body([derived, "ANCHOR"])
    proofs = character_work_candidates(ctx)
    assert len(proofs) == 1 and proofs[0]["source_occurrences"][0]["original_index"] == 1


def test_quote_boundary_drift_is_not_hidden_by_unchanged_lexical_fields():
    ctx = quoted_body([{"type": "blockquote", "text": '친구가 말했다: "'}, 'ANCHOR', '"'])
    # lexical 작성자 필드는 동일하지만 원형 quote 시작 블록의 text가 바뀐다.
    ctx.post_data["content_blocks"][0]["text"] = "친구의 말은 끝났다."
    assert character_work_candidates(ctx) == []
