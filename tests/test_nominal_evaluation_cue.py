"""명사구 내부 어휘 관측과 실제 평가 사건을 원문·native·진단·설명에서 구분한다."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import PickvelIdentity, PostInput
from llm_batch.experts.orchestrator import ConversationContext
from llm_batch.grounding.context_projection_contract import _speaker_ledger
from llm_batch.grounding.source_context_diagnostics import export_source_context_diagnostics


FIXTURE = Path(__file__).parent / "fixtures/nominal_cue13_74_saved.json"
FIXTURE_SHA = "a8598914e12514f2ba93988841f8fde63f48d3cbf10bb292ac623295cdbaf0af"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


class ForbiddenExternal(BaseException):
    pass


class NoExternal:
    def __init__(self):
        self.attempts = []

    def __getattr__(self, name):
        def forbidden(*args, **kwargs):
            self.attempts.append(name)
            raise ForbiddenExternal(name)
        return forbidden


def consume(post_data, comments, *, title_candidates=None):
    post = PostInput(**{**deepcopy(post_data), "comments": deepcopy(comments)})
    original = canonical(post.model_dump())
    external = NoExternal()
    pipe = AgenticPipeline(llm=external, mcp=external, max_iterations=2)
    ctx = ConversationContext(post_id=post.post_id, post_data=pipe._post_to_dict(post),
                              comments=post.comments)
    ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs = tuple(post.comments)
    identity = PickvelIdentity(is_relevant=False, discussion_type="general",
                              title_candidates=deepcopy(title_candidates))
    candidates_before = deepcopy(identity.model_dump()["title_candidates"])
    notes, verify = pipe._consume_final_source_context(ctx, identity, None)
    assert verify() and not external.attempts
    native = ctx._final_source_projection_native
    output = SimpleNamespace(_final_source_context_native=native, _final_source_context_owner=ctx)
    output._final_source_context_receipt = {
        "native_object": native, "context": ctx, "native_verification_status": "NATIVE_CALLBACK_TRUE",
    }
    public_before = deepcopy(identity.model_dump())
    diagnostic = export_source_context_diagnostics(output, enabled=True)
    assert diagnostic["publication_authority"] is False
    assert identity.model_dump() == public_before and identity.novel_identity is None
    assert identity.model_dump()["title_candidates"] == candidates_before
    assert canonical(post.model_dump()) == original and verify() and not external.attempts
    return ctx, identity, notes, diagnostic, verify


@pytest.mark.parametrize("index,phrase,predicate", [
    (13, "마좋좋좋 결말이 왜이러냐..", "마좋좋좋"),
    (74, "동창회나가서 학창시절첫사랑꼬시기", "학창시절첫사랑꼬시기"),
])
def test_saved_source_real_consumer_keeps_raw_cue_without_actual_support(index, phrase, predicate):
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == FIXTURE_SHA
    fixture = json.loads(raw)
    assert fixture["scope"] == "SAVED_SOURCE_FULL_RESULT_NOT_FULL_PRIVATE_CONTEXT"
    packet = next(r for r in fixture["rows"] if r["index1"] == index)
    assert type(packet["post_id"]) is int
    assert hashlib.sha256(canonical({"post": packet["source_post"], "comments": packet["source_comments"]})).hexdigest() == packet["source_canonical_sha256"]
    assert hashlib.sha256(canonical(packet["checkpoint_result"])).hexdigest() == packet["result_canonical_sha256"]
    # 저장된 실제 typed 후보만 전달한다. 새 공식 정답/전문가 성공값을 만들지 않는다.
    saved_candidates = packet["checkpoint_result"]["analysis_result"]["identity"]["title_candidates"]
    ctx, identity, notes, diagnostic, verify = consume(
        packet["source_post"], packet["source_comments"], title_candidates=saved_candidates)
    native = ctx._final_source_projection_native
    event = next(e for e in native.author_ledger.evaluations if e.predicate == predicate)
    assert event.evidence_text == phrase and phrase[slice(*event.predicate_span)] == predicate
    assert event.evaluation_polarity == "pos" and event.polarity == "positive"
    assert event.realization == "embedded" and event.realization_source == "nominal_cue_observation"
    assert not event.final_support and event.evidence_kind == "cue"
    stored = next(e for l in diagnostic["ledgers"] if l["source_role"] == "author"
                  for e in l["evaluations"] if e["predicate"] == predicate)
    assert stored["evidence_text"] == phrase and stored["predicate_span"] == list(event.predicate_span)
    assert stored["evaluation_polarity"] == "pos" and stored["realization"] == "embedded"
    assert stored["final_support"] is False
    assert phrase in identity.reason + notes
    assert not any("글쓴이" in line and "긍정적인 반응" in line for line in (identity.reason + notes).splitlines())
    assert verify() and FIXTURE.read_bytes() == raw


@pytest.mark.parametrize("text,needle,realization,realization_source", [
    ("동창회나가서 학창시절첫사랑꼬시기", "사랑", "embedded", "nominal_cue_observation"),
    ("첫사랑의 결말에 관한 이야기", "사랑", "embedded", "nominal_cue_observation"),
    ("사랑방에서 나눈 이야기", "사랑", "embedded", "nominal_cue_observation"),
    # 기존 reported 경계가 먼저 보호한 원문은 actual 전용 새 제한으로 재분류하지 않는다.
    ("사랑꾼이라는 별명", "사랑", "reported", "cue_token_construction"),
])
def test_compound_nominal_keeps_lexical_observation_without_affirmed_evaluation(
        text, needle, realization, realization_source):
    ledger = _speaker_ledger((text,), source_id="author")
    events = [e for e in ledger.evaluations if e.evidence_kind == "cue" and needle in e.predicate]
    assert events  # exporter 삭제나 cue 자체 제거로 통과시키지 않는다.
    for event in events:
        assert event.evaluation_polarity == "pos" and event.polarity == "positive"
        assert event.realization_source == realization_source
        assert event.realization == realization and not event.final_support
        assert event.evidence_text == text
        assert text[slice(*event.predicate_span)] == event.predicate
    assert any(c.text == text and c.final_support for c in ledger.claims)


@pytest.mark.parametrize("name", ["마좋좋좋", "좋은 날의 기록", "사랑의 항로"])
def test_source_named_surface_preserves_independent_later_praise(name):
    first, second = f"{name} 결말에 관한 이야기", "이 작품은 좋다."
    ledger = _speaker_ledger((first, second), works=(name,), source_id="author")
    first_events = [e for e in ledger.evaluations if e.source_id == "author:clause:0"]
    later = [e for e in ledger.evaluations if e.source_id == "author:clause:1"]
    assert first_events and all(not e.final_support for e in first_events)
    assert any(e.realization_source == "nominal_cue_observation" for e in first_events)
    assert any(e.final_support and e.realization == "actual" and e.evaluation_polarity == "pos" for e in later)


@pytest.mark.parametrize("text", [
    "이 작품은 좋다.",
    "나는 이 작품을 좋아한다.",
    "나는 그 인물을 사랑한다.",
    "나는 그 인물을 사랑해서 계속 읽었다.",
    "그 인물은 사랑스럽다.",
    "첫사랑을 했다.",
])
def test_actual_predicate_constructions_keep_positive_support(text):
    ledger = _speaker_ledger((text,), source_id="author")
    events = [e for e in ledger.evaluations if e.evaluation_polarity == "pos"]
    assert events and any(e.final_support and e.realization == "actual" for e in events)
    assert all(e.realization_source != "nominal_cue_observation" for e in events)


@pytest.mark.parametrize("text,mode", [
    ("이 작품은 좋나요?", "question"),
    ("이 작품이 좋다면 계속 읽겠다.", "conditional"),
    ('친구는 "이 작품은 좋다."라고 말했다.', "reported"),
])
def test_question_condition_and_report_do_not_become_own_actual_support(text, mode):
    ledger = _speaker_ledger((text,), source_id="author")
    events = [e for e in ledger.evaluations if e.evaluation_polarity == "pos"]
    assert events and not any(e.final_support for e in events)
    if mode == "reported":
        assert any(c.kind == "reported" and c.speaker == "친구" for c in ledger.claims)
    else:
        assert any(e.realization == mode for e in events)
    assert all(e.realization_source != "nominal_cue_observation" for e in events)


def test_real_comment_praise_keeps_its_speaker_and_exported_support():
    post = {"post_id": 93001, "title": "등장인물은 어떤가?", "content_blocks": []}
    comments = [{"comment_id": "c1", "author": "독자", "content": "그 인물은 좋다."}]
    ctx, identity, notes, diagnostic, verify = consume(post, comments)
    event = next(e for e in ctx._final_source_projection_native.comment_ledgers[0].evaluations
                 if e.evaluation_polarity == "pos")
    assert event.final_support and event.speaker == "self"
    assert any(l["source_role"] == "comment" and any(e["final_support"] for e in l["evaluations"])
               for l in diagnostic["ledgers"])
    assert "댓글" in notes and "그 인물은 좋다." in identity.reason + notes
    assert verify()


@pytest.mark.parametrize("field", ["title", "body"])
def test_original_carrier_mismatch_remains_rejected(field):
    post = {"post_id": 93002, "title": "첫사랑이라는 설정은 어떤가?",
            "content_blocks": [{"type": "text", "text": "첫사랑의 결말에 관한 이야기"}]}
    ctx, _, _, _, verify = consume(post, [])
    if field == "title":
        ctx.post_data["title"] += " 변경"
    else:
        ctx.post_data["content_blocks"][0]["text"] += " 변경"
    assert not verify()
