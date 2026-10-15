"""인코딩이 다른 동일 Namu 문서의 반증. 과거65의 실제 입력 재현은 아니다."""
from copy import deepcopy
import json
from urllib.parse import unquote

import pytest

from test_source65_character_candidate_preservation import pipeline, synthetic_context
from llm_batch.grounding.character_work_candidate import CHARACTER_WORK_CANDIDATE_HOLD, character_work_candidates


DENIAL = "서하진은 이 작품의 등장인물이 아니다."


def other_encoding(ctx, *, field="content", text=DENIAL):
    original = ctx.search_results[0]
    return {"url": unquote(original["url"]), "title": original["title"], field: text}


def raw_snapshot(ctx):
    return json.dumps([ctx.post_data, ctx.comments, ctx.expert_outputs, ctx.search_results],
        ensure_ascii=False, sort_keys=True, allow_nan=False)


@pytest.mark.parametrize("field", ["content", "snippet", "description"])
@pytest.mark.parametrize("reverse", [False, True])
def test_real_search_ingestion_keeps_distinct_encodings_but_relation_checks_same_document(field, reverse):
    ctx = synthetic_context()
    positive = deepcopy(ctx.search_results[0])
    negative = other_encoding(ctx, field=field)
    ctx.search_results = []
    assert positive["url"] != negative["url"]
    assert ctx._normalize_url_for_dedup(positive["url"]) != ctx._normalize_url_for_dedup(negative["url"])
    assert ctx.add_search_results([negative, positive] if reverse else [positive, negative]) == 2
    assert len(ctx.search_results) == 2
    before = raw_snapshot(ctx)
    assert character_work_candidates(ctx) == []
    assert raw_snapshot(ctx) == before


@pytest.mark.parametrize("text", [
    "백도윤은 이 작품의 등장인물이 아니다.",
    "서하진은 다른 작품의 등장인물이 아니다.",
    "서하진은 이 작품의 등장인물이라는 설명은 잘못이 아니다.",
    "서하진은 이 작품의 등장인물이 아니라는 주장은 틀렸다.",
    "서하진은 이 작품의 등장인물이라는 설명은 취소하지 않았다.",
])
def test_same_document_unrelated_person_and_rebutted_counterclaim_preserve_positive(text):
    ctx = synthetic_context()
    assert ctx.add_search_results([other_encoding(ctx, text=text)]) == 1
    before = raw_snapshot(ctx)
    proofs = character_work_candidates(ctx)
    assert len(proofs) == 1 and proofs[0]["title"] == "은월전"
    assert proofs[0]["evidence_url"] == ctx.search_results[0]["url"]
    assert proofs[0]["publication_authority"] is False and proofs[0]["alias_authority"] is False
    assert raw_snapshot(ctx) == before


@pytest.mark.parametrize("url,title", [
    ("https://namu.wiki/w/다른작품/등장인물", "다른작품/등장인물 - 나무위키"),
    ("https://namu.wiki/w/은 월전/등장인물", "은 월전/등장인물 - 나무위키"),
    ("https://namu.wiki/w/은월전/줄거리", "은월전/줄거리 - 나무위키"),
    ("https://example.com/w/은월전/등장인물", "은월전/등장인물 - 나무위키"),
])
def test_other_document_is_not_a_global_veto_even_for_same_person(url, title):
    ctx = synthetic_context()
    assert ctx.add_search_results([{"url": url, "title": title, "content": DENIAL}]) == 1
    before = raw_snapshot(ctx)
    proofs = character_work_candidates(ctx)
    assert len(proofs) == 1 and proofs[0]["title"] == "은월전"
    assert raw_snapshot(ctx) == before


@pytest.mark.parametrize("marker", ["_ocr_diagnostic_only", "_purpose", "purpose", "media_type"])
def test_same_url_diagnostic_or_other_media_row_does_not_gain_document_authority(marker):
    ctx = synthetic_context()
    row = other_encoding(ctx)
    row[marker] = True if marker == "_ocr_diagnostic_only" else "webtoon" if marker == "media_type" else "image_ocr_diagnostic_probe"
    assert ctx.add_search_results([row]) == 1
    assert len(character_work_candidates(ctx)) == 1


def test_exact_url_ingestion_still_deduplicates_without_product_policy_changes():
    ctx = synthetic_context()
    same_url = {"url": ctx.search_results[0]["url"], "title": ctx.search_results[0]["title"], "content": DENIAL}
    assert ctx.add_search_results([same_url]) == 0
    assert len(ctx.search_results) == 1 and len(character_work_candidates(ctx)) == 1


def test_annotate_rechecks_new_same_document_counterevidence_without_public_promotion(pipeline):
    ctx = synthetic_context()
    candidates, _ = pipeline._finalize_title_candidate_generation(scored=[], final_norm="", max_items=6, ctx=ctx)
    assert len(candidates) == 1 and CHARACTER_WORK_CANDIDATE_HOLD in candidates[0].negative_evidence
    assert ctx.add_search_results([other_encoding(ctx)]) == 1
    before = raw_snapshot(ctx)
    annotated, primary, mentioned, future = pipeline._annotate_work_references(
        ctx=ctx, title_candidates=candidates, official_title=None, vf_result={})
    assert not any(CHARACTER_WORK_CANDIDATE_HOLD in (c.negative_evidence or []) for c in annotated)
    assert primary is None and mentioned == [] and future is None
    assert raw_snapshot(ctx) == before
