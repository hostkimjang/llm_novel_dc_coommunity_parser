"""65 v2 F4의 반증 극성. 원형 78사례는 별도 두 파일 그대로 실행한다."""
import json

import pytest

from test_source65_character_candidate_preservation import synthetic_context
from llm_batch.grounding.character_work_candidate import character_work_candidates


HEADER = "개요 웹소설 은월전의 등장인물을 정리한 문서. "
POSITIVE = "서하진과 마주쳤다. "


def source_with_statement(statement, where):
    ctx = synthetic_context()
    row = ctx.search_results[0]
    if where == "same_field_after":
        row["snippet"] = HEADER + POSITIVE + statement
    else:
        row["content"] = statement
        row["snippet"] = HEADER + POSITIVE
    return ctx


def raw_snapshot(ctx):
    return json.dumps([ctx.post_data, ctx.comments, ctx.expert_outputs, ctx.search_results],
        ensure_ascii=False, sort_keys=True, allow_nan=False)


@pytest.mark.parametrize("statement", [
    "서하진은 이 작품의 등장인물이라는 설명은 잘못이 아니다.",
    "서하진은 이 작품의 등장인물이 아니라는 주장은 틀렸다.",
    "서하진은 이 작품에 등장하지 않는다는 주장은 틀렸다.",
    "서하진은 이 작품과 무관하다는 주장은 틀렸다.",
    "서하진은 다른 작품의 등장인물이라는 주장은 틀렸다.",
    "서하진은 이 작품의 등장인물이라는 설명은 취소됐다는 주장은 틀렸다.",
    '"서하진은 이 작품의 등장인물이 아니다."라는 주장은 틀렸다.',
    "서하진은 이 작품의 등장인물이 아니다?",
])
@pytest.mark.parametrize("where", ["same_field_after", "cross_field"])
def test_denied_or_rebutted_counterclaim_does_not_erase_independent_positive(statement, where):
    ctx = source_with_statement(statement, where)
    before = raw_snapshot(ctx)
    proofs = character_work_candidates(ctx)
    assert len(proofs) == 1 and proofs[0]["title"] == "은월전"
    assert proofs[0]["character"] == "서하진"
    assert proofs[0]["publication_authority"] is False
    assert proofs[0]["alias_authority"] is False and proofs[0]["supports_publish"] is False
    assert raw_snapshot(ctx) == before


@pytest.mark.parametrize("statement", [
    "서하진은 이 작품의 등장인물이 아니다.",
    "서하진은 이 작품의 등장인물이라는 설명은 잘못이다.",
    "서하진은 이 작품의 등장인물이라는 정보는 오류입니다.",
    "서하진은 이 작품에 등장하지 않는다.",
    "서하진은 이 작품과 무관하다.",
    "서하진은 다른 작품의 등장인물이다.",
    "서하진은 이 작품의 등장인물이라는 설명은 취소됐다.",
    "서하진은 이 작품의 등장인물이라는 설명은 철회되었습니다.",
])
@pytest.mark.parametrize("where", ["same_field_after", "cross_field"])
def test_complete_asserted_counterevidence_still_rejects_relationship(statement, where):
    ctx = source_with_statement(statement, where)
    before = raw_snapshot(ctx)
    assert character_work_candidates(ctx) == []
    assert raw_snapshot(ctx) == before


@pytest.mark.parametrize("ending", ["", ".", "。", "!", "\n다른 인물의 설명이다."])
def test_complete_negative_predicate_uses_local_sentence_boundary(ending):
    ctx = source_with_statement("서하진은 이 작품의 등장인물이 아니다" + ending, "cross_field")
    assert character_work_candidates(ctx) == []
