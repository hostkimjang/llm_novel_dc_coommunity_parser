"""최종 원문 설명과 문맥 메모의 중복 및 미지원 설명 fallback 검증."""
from __future__ import annotations

import sys
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import PickvelIdentity, PostInput
from llm_batch.experts.orchestrator import ConversationContext
from llm_batch.grounding.source_context_explanation import SourceExplanation


def _consume(*, title="전개 감상", force_hold=False, unsupported=False):
    post = PostInput(
        post_id=24,
        title=title,
        author="작성자",
        content_blocks=[{"type": "text", "text": "생각보다 적수를 빨리 죽이고 무리를 일망타진한게 의외였음"}],
        comments=[{"comment_id": "c1", "author": "독자", "content": "그 장면은 놀랐음"}],
    )
    pipeline = AgenticPipeline(llm=object(), mcp=object(), max_iterations=2)
    ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
    ctx._final_source_original_inputs = pipeline._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs = tuple(post.comments)
    identity = PickvelIdentity(is_relevant=False, discussion_type="general")
    hold_patch = (patch.object(pipeline, "_final_source_original_projection_channels", return_value=(False, "test hold"))
                  if force_hold else nullcontext())
    explanation_patch = (patch("llm_batch.agentic_pipeline.reduce_source_context", return_value=SourceExplanation())
                         if unsupported else nullcontext())
    with hold_patch:
        with explanation_patch:
            notes, verify = pipeline._consume_final_source_context(ctx, identity, None)
    return ctx, identity, notes, verify


def test_supported_reason_is_not_copied_into_notes():
    ctx, identity, notes, verify = _consume()
    explanation = ctx._final_source_context_explanation
    assert ctx._final_source_projection_consumption["source_explanation_used"]
    assert explanation.reason_sentences
    assert "[원문에 근거한 설명]" in identity.reason
    assert "[원문에 근거한 설명]" not in notes
    assert "[문맥과 댓글 역할]" in notes
    assert "[원문]" in identity.reason and "일망타진" in identity.reason
    assert verify()


def test_held_reason_and_notes_keep_distinct_roles():
    ctx, identity, notes, _ = _consume(title="큰 판이 의외였음", force_hold=True)
    assert ctx._final_source_projection_consumption["status"] == "HOLD_UNBOUND"
    assert not ctx._final_source_projection_consumption["source_explanation_used"]
    assert "[원문에 근거한 설명]" not in notes
    assert "[원문]" in notes
    assert identity.primary_subject_text.startswith("[원문] 큰 판이 의외였음")
    assert "[작성자 발화·원문 귀속]" not in identity.primary_subject_text


def test_unsupported_explanation_uses_raw_quote_as_primary():
    ctx, identity, notes, verify = _consume(unsupported=True)
    assert not ctx._final_source_projection_consumption["source_explanation_used"]
    assert identity.primary_subject_text.startswith("[원문] 전개 감상")
    assert "[작성자 발화·원문 귀속]" not in identity.primary_subject_text
    assert "[원문에 근거한 설명]" not in identity.reason
    assert "일망타진" in identity.reason and "일망타진" in notes
    assert verify()
