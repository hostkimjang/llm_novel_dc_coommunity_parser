"""40·62 부정 경험의 평가 사건 범위. 원문 극성과 정확한 최종 설명을 보존한다."""
from __future__ import annotations
import copy
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import PickvelIdentity, PostInput
from llm_batch.experts.orchestrator import ConversationContext
from llm_batch.grounding.context_projection_contract import _speaker_ledger
from llm_batch.grounding.source_context_diagnostics import export_source_context_diagnostics

FIXTURE = Path(__file__).parent / "fixtures/source_negated_experience_saved40_62.jsonl"
FIXTURE_SHA = "bc550ecf294e845ef20da02aafdcbb6c6a6cb8135e84daba4491b33e363e4fb2"
def canonical(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
class ForbiddenExternal(BaseException): pass
class NoExternal:
    def __init__(self): self.attempts = []
    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.attempts.append(name)
            raise ForbiddenExternal(name)
        return call

def _events(text, source_id="author"):
    ledger = _speaker_ledger((text,), source_id=source_id)
    return ledger, [e for e in ledger.evaluations if e.evidence_kind == "cue"]

def _cue(events, word):
    return next(e for e in events if word in e.predicate)

@pytest.mark.parametrize("index1,word,phrase,role", [
    (40, "재밌게", "빙밍아웃하고 재밌게 풀어내는걸 본 적이 없음", "comment"),
    (62, "재밌는", "후반갈수록 재밌는 소년만화 << 본적이 없음", "author"),
])
def test_current_saved_source_native_and_export_without_false_actual_support(index1, word, phrase, role):
    raw = FIXTURE.read_bytes(); assert hashlib.sha256(raw).hexdigest() == FIXTURE_SHA
    packet = next(json.loads(l) for l in raw.splitlines() if json.loads(l)["index1"] == index1)
    assert hashlib.sha256(canonical({"post":packet["source_post"],"comments":packet["source_comments"]})).hexdigest() == packet["source_canonical_sha256"]
    assert hashlib.sha256(canonical(packet["checkpoint_result"])).hexdigest() == packet["result_canonical_sha256"]
    post = PostInput(**{**copy.deepcopy(packet["source_post"]), "comments":copy.deepcopy(packet["source_comments"])})
    before = canonical(post.model_dump()); forbidden = NoExternal()
    pipe = AgenticPipeline(llm=forbidden, mcp=forbidden, max_iterations=2)
    ctx = ConversationContext(post_id=post.post_id, post_data=pipe._post_to_dict(post), comments=post.comments)
    ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs = tuple(post.comments)
    identity = PickvelIdentity(is_relevant=False, discussion_type="general")
    notes, verify = pipe._consume_final_source_context(ctx, identity, None)
    native = ctx._final_source_projection_native
    ledgers = (native.author_ledger, *native.comment_ledgers)
    ledger = next(l for l in ledgers if any(c.text == phrase for c in l.claims))
    event = _cue(ledger.evaluations, word)
    assert ledger.source_role == role and event.speaker == "self"
    assert event.predicate == word and event.evaluation_polarity == "pos" and event.polarity == "positive"
    assert event.realization == "embedded" and event.realization_source == "negated_experience_scope"
    assert not event.final_support
    assert phrase[event.predicate_span[0]:event.predicate_span[1]] == event.predicate
    output = SimpleNamespace(_final_source_context_native=native, _final_source_context_owner=ctx)
    output._final_source_context_receipt = {"native_object":native,"context":ctx,"native_verification_status":"NATIVE_CALLBACK_TRUE"}
    diag = export_source_context_diagnostics(output, enabled=True)
    observed = next(e for l in diag["ledgers"] for e in l["evaluations"] if e["evidence_text"] == phrase and e["predicate"] == word)
    assert observed["evaluation_polarity"] == "pos" and observed["final_support"] is False
    assert not diag["publication_authority"] and phrase in identity.reason + notes
    if index1 == 62:
        assert "초반에피의 재미를 후반 전개가 넘기 어렵다" in identity.reason
        assert "드래곤볼」은 예외" in identity.reason
        assert "긍정적인 반응" not in identity.reason
    assert verify() and not forbidden.attempts and identity.novel_identity is None
    assert canonical(post.model_dump()) == before and FIXTURE.read_bytes() == raw

@pytest.mark.parametrize("text,word,polarity", [
    ("후반갈수록 재밌는 소년만화 << 본적이 없음", "재밌는", "pos"),
    ("빙밍아웃하고 재밌게 풀어내는걸 본 적이 없음", "재밌게", "pos"),
    ("좋은 작품을 본 적이 없다.", "좋은", "pos"),
    ("재미없는 작품을 읽은 적은 없다.", "재미없는", "neg"),
    ("재밌게 전개되는걸 본 적이 없음", "재밌게", "pos"),
    ("재밌는 작품을 접한 적도 없었다.", "재밌는", "pos"),
])
def test_same_nominalized_experience_scope_preserves_lexical_polarity(text, word, polarity):
    ledger, events = _events(text); event = _cue(events, word)
    assert event.evaluation_polarity == polarity and event.realization == "embedded"
    assert event.realization_source == "negated_experience_scope" and not event.final_support
    assert any(c.text == text and c.final_support for c in ledger.claims)
    assert text[event.predicate_span[0]:event.predicate_span[1]] == event.predicate

@pytest.mark.parametrize("text,word,polarity", [
    ("재밌는 작품을 본 적이 있다.", "재밌는", "pos"),
    ("좋은 작품을 읽은 적이 있다.", "좋은", "pos"),
    ("재밌는 작품은 봤고 다른 작품을 본 적이 없다.", "재밌는", "pos"),
    ("재밌는 작품을 본 적이 없지는 않다.", "재밌는", "pos"),
    ("이 작품은 재미없다.", "재미없다", "neg"),
])
def test_positive_experience_and_plain_negative_evaluation_keep_actual_support(text, word, polarity):
    _, events = _events(text); event = _cue(events, word)
    assert event.evaluation_polarity == polarity
    assert event.realization == "actual" and event.final_support
    assert event.realization_source != "negated_experience_scope"

@pytest.mark.parametrize("text", [
    '친구는 "재밌는 작품을 본 적이 없다."라고 말했다.',
    '친구는 "재밌는 작품을 본 적이 있다."라고 말했다.',
    '친구는 "재밌는 작품을 본 적이 있다."라고 말한 적이 없다.',
])
def test_external_quotes_do_not_become_author_support(text):
    _, events = _events(text); event = _cue(events, "재밌는")
    assert event.speaker == "친구" and not event.final_support
    assert event.evaluation_polarity == "pos"

@pytest.mark.parametrize("parts", [
    ("재밌는 작품을 본 적이 없다.", "하지만 유리성은 재밌다."),
    ("재밌는 작품을 본 적이 없다.", "그와 별개로 유리성은 좋다."),
])
def test_negated_experience_does_not_cross_into_independent_exception(parts):
    ledger = _speaker_ledger(parts, source_id="author")
    first = next(e for e in ledger.evaluations if e.source_id == "author:clause:0" and "재밌는" in e.predicate)
    later = [e for e in ledger.evaluations if e.source_id == "author:clause:1" and e.evaluation_polarity == "pos"]
    assert not first.final_support and later and any(e.final_support for e in later)

def test_explicit_condition_is_not_replaced_by_negative_experience_mode():
    _, events = _events("재밌다면 계속 읽겠다.")
    event = _cue(events, "재밌다면")
    assert event.realization == "conditional" and not event.final_support
    assert event.realization_source != "negated_experience_scope"
