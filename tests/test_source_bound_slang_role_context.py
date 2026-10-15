"""합성 HOLD의 실제 serializer 통합 초안. 실제 8번의 공식 공개 재현 시험은 아니다."""
from __future__ import annotations

from copy import deepcopy
import json
import hashlib
import os

import pytest

from test_source_bound_nsfw import wrapper_class
from llm_batch.ledger.publication_commit import PublicationCommitRegistry, build_publication_scope_descriptor, commit_publication_result
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import PostInput
from llm_batch.experts.orchestrator import ConversationContext, ExpertType


BAD = "작품명(은빛 기록)과 주인공 이름(서린)을 결합한 표현이다."
RETAINED = "서로 부를 때 쓰는 표현이다."


class NoExternalIO:
    def __init__(self):
        self.calls = []

    def fetch(self, *args, **kwargs):
        self.calls.append("fetch")
        raise AssertionError("EXTERNAL_FETCH_FORBIDDEN")

    def search(self, *args, **kwargs):
        self.calls.append("search")
        raise AssertionError("EXTERNAL_SEARCH_FORBIDDEN")


def _context(cultural_context):
    post = PostInput(post_id=8100801, title="은빛 기록서린이라는 표현",
        content_blocks=[{"type": "text", "text": "이 말이 무슨 뜻인지 궁금하다."}],
        comments=[])
    io = NoExternalIO()
    pipe = AgenticPipeline(llm=object(), mcp=io, max_iterations=1)
    pipe._use_session_knowledge = False
    pipe.enable_url_fetch_disk_cache = False
    ctx = ConversationContext(post_id=post.post_id,
        post_data=pipe._post_to_dict(post), comments=pipe._extract_comments(post))
    ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs = tuple(post.comments)
    ctx._source_bound_nsfw_original_carrier = pipe._capture_source_bound_nsfw_carrier(post)
    ctx.set_expert_output(ExpertType.GATEKEEPER, {
        "post_type": "general", "context_clues": {"is_recommendation_request": False},
    })
    ctx.set_expert_output(ExpertType.VERIFIER, {"verification_result": {
        "is_relevant": True, "is_novel_discussion": True,
        "novel_identity": {"official_novel_title": None},
        "grounding_check": {"anchor_found": "search_only"},
        "relation_judgment": {"relation_type": "example_reference",
            "discussion_target": "genre_general", "promotion_decision": "hold"},
        "slang_insight": {
            "detected_term": "은빛 기록서린", "decoded_term": "커뮤니티 별명",
            "decode_verified": False, "canonical_work_alias": "은빛 기록",
            "alias_scope": "work_plus_character", "attached_entity_text": "서린",
            "attached_entity_type": "other", "store_reason": "character_attached_composite",
            "cultural_context": cultural_context,
        },
    }})
    # 고정 전문가 제안만 제공한다. 최종 guard/native verifier/반환 모델은 제품이 만든다.
    ctx.set_expert_output(ExpertType.ARBITER, {"final_decision": {
        "is_relevant": True, "official_title": None, "official_novel_title": None,
        "confidence": "Low", "discussion_type": "general",
        "reason": "표현의 의미를 묻는 글이며 특정 작품의 공개 근거는 없다.",
    }, "metadata_synthesis": {"is_nsfw": False}})
    return pipe, ctx, io


def _serialize(cultural_context):
    pipe, ctx, io = _context(cultural_context)
    before = deepcopy(ctx.post_data)
    output = pipe._context_to_output(ctx)
    payload = output.model_dump(mode="json")
    assert ctx.post_data == before
    assert io.calls == []
    assert isinstance(payload["identity"]["slang_insight"], dict), payload
    assert payload["identity"]["novel_identity"] is None
    assert payload["identity"]["promotion_decision"]["publish_allowed"] is False
    assert payload["identity"]["title_resolution_allowed"] is False
    assert payload["identity"]["slang_insight"]["store_in_slang_db"] is False
    pipe.verify_final_source_context_serialization(output, payload, stage="slang_role_full_context")
    return pipe, ctx, output, payload


@pytest.mark.parametrize("description", [
    BAD,
    "작품명(은빛 기록)과 주인공의 성함('서린')을 결합한 표현이다.",
    "주인공의 성함은 '서린'이다.",
    "작품명과 '주인공 이름(서린)'을 결합한 표현이다.",
    "주인공 이름(서린)이라고 부르는 표현이며, 다른 리뷰를 친구가 썼다.",
    "주인공의 이름은 '김서린'이다.",
    '“주인공 이름(서린)\n”을 결합한 표현이다.',
    '작품명과 “\n주인공 이름(서린)\n”을 결합한 표현이다.',
], ids=["legacy", "quoted_honorific", "name_subject", "meta_quote", "separate_report_clause",
    "new_named_person", "multiline_quote_tail", "multiline_quote_both_ends"])
@pytest.mark.parametrize("remainder", [RETAINED, None], ids=["retain_other_sentence", "hold_only_sentence"])
def test_actual_hold_context_preserves_slang_and_seals_only_role_sentence(tmp_path, remainder, description):
    proposed = description + (" " + remainder if remainder else "")
    pipe, ctx, output, payload = _serialize(proposed)
    insight = payload["identity"]["slang_insight"]
    assert insight["cultural_context"] == remainder
    assert insight["alias_scope"] == "work_plus_character"
    assert insight["attached_entity_type"] == "other"
    held = ctx.__dict__.get("_slang_character_role_hold")
    assert held and held["status"] == "UNSUPPORTED_CHARACTER_ROLE_SENTENCES_HELD"
    assert held["publication_authority"] is False
    assert any(description in item["model_quote"] for item in held["held"])

    # 역할 문장이 애초에 없는 동일 제안과 공개 필드/설명/분석을 대조한다.
    # SI 삭제나 앞단의 무조건 설명 삭제로 우연히 통과하지 못하게 한다.
    _, control_ctx, _, control = _serialize(remainder)
    assert control_ctx.__dict__.get("_slang_character_role_hold") is None
    assert payload["identity"] == control["identity"]
    assert payload["analysis"] == control["analysis"]

    target = tmp_path / "typed_synthetic_hold_output.json"
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    readback = json.loads(target.read_text(encoding="utf-8"))
    assert readback == payload
    pipe.verify_final_source_context_serialization(output, readback, stage="slang_role_disk_readback")
    # 실제 main 운반 객체와 새 공개 WAL의 HOLD 저장/재개봉도 별도로 검산한다.
    row = dict(ctx.post_data, comments=list(ctx.comments), analysis_result=payload)
    wrapped = wrapper_class()(row, output=output, verifier=pipe.verify_final_source_context_serialization)
    input_sha = hashlib.sha256(json.dumps(ctx.post_data, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()
    scope = build_publication_scope_descriptor(input_file_sha256=input_sha,
        post_ids=[ctx.post_id], config_hash='synthetic-slang-role-context', release_fingerprint='candidate-only')
    wal_path = tmp_path / 'publication_commits.jsonl'
    registry = PublicationCommitRegistry(wal_path, scope_descriptor=scope, create_new=True)
    wrapped.verify_stored_payload(wrapped, stage='slang_role_before_commit')
    commit, created = commit_publication_result(wrapped, registry=registry,
        attempt_run_id='synthetic-slang-role', input_index=1, post_id=ctx.post_id)
    assert created and commit.outcome == 'HOLD' and commit.publish_allowed is False
    reopened = PublicationCommitRegistry(wal_path, scope_descriptor=scope, create_new=False)
    stored_row = reopened.result(ctx.post_id)
    assert stored_row['analysis_result'] == payload
    wrapped.verify_stored_payload(stored_row, stage='slang_role_wal_readback')
    wal_before = wal_path.read_bytes()
    forged_row = deepcopy(stored_row)
    forged_row['analysis_result']['identity']['slang_insight']['cultural_context'] = proposed
    with pytest.raises(ValueError, match='serialized fields changed'):
        wrapped.verify_stored_payload(forged_row, stage='slang_role_wal_tamper')
    assert wal_path.read_bytes() == wal_before
    # null/키 부재도 구별하며 최초 봉인을 재발급하지 않는다.
    for mutation in ("restore_unsupported", "remove_key", "null_or_insert"):
        changed = deepcopy(readback)
        changed_insight = changed["identity"]["slang_insight"]
        if mutation == "remove_key":
            del changed_insight["cultural_context"]
        else:
            changed_insight["cultural_context"] = proposed if mutation == "restore_unsupported" else (
                None if remainder is not None else RETAINED)
        with pytest.raises(ValueError, match="serialized fields changed"):
            pipe.verify_final_source_context_serialization(output, changed,
                stage="slang_role_tampered_" + mutation)



@pytest.mark.parametrize('description', [
    '주인공의 이름은 중요한 단서입니다.',
    "친구가 '주인공 이름(서린)'이라고 말했다.",
    '“주인공 이름(서린)\n”이 아니다.',
    '“\n주인공의 성함(서린)\n”이 맞는가?',
    '만약 “\n주인공 이름(서린)\n”이라면 가능한 설명이다.',
], ids=['general_description', 'reported_speech', 'multiline_negative',
    'multiline_question', 'multiline_condition'])
def test_nonclaim_or_reported_description_survives_actual_native_serialization(description):
    pipe, ctx, output, payload = _serialize(description)
    assert payload['identity']['slang_insight']['cultural_context'] == description
    assert '_slang_character_role_hold' not in ctx.__dict__
    assert payload['identity']['promotion_decision']['publish_allowed'] is False
    changed = deepcopy(payload)
    changed['identity']['slang_insight']['cultural_context'] = None
    with pytest.raises(ValueError, match='serialized fields changed'):
        pipe.verify_final_source_context_serialization(output, changed, stage='retained_role_description_tamper')
