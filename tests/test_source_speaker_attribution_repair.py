"""친구 언급과 전언 화자를 구분하는 원문→native→최종 설명 기능 회귀. ROOT만 실행한다."""
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
from llm_batch.grounding.context_projection_contract import _speaker_ledger, _author_clause_cut
from llm_batch.grounding.source_context_diagnostics import export_source_context_diagnostics

FIXTURE = Path(__file__).parent / "fixtures/source_speaker7_saved_packet.json"
FIXTURE_SHA = "8d2d9832fbca9ce17b35cfac212a21f262f5d3a2179c2b47f9eebc63ec5ab12c"
def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

class UnexpectedExternal(BaseException):
    pass
class NoExternal:
    def __init__(self): self.attempts = []
    def __getattr__(self, name):
        def forbidden(*args, **kwargs):
            self.attempts.append(name)
            raise UnexpectedExternal(name)
        return forbidden

def consume(post, comments):
    post = copy.deepcopy(post); post["comments"] = copy.deepcopy(comments)
    model = PostInput(**post); before = canonical(model.model_dump())
    forbidden = NoExternal()
    pipe = AgenticPipeline(llm=forbidden, mcp=forbidden, max_iterations=2)
    ctx = ConversationContext(post_id=model.post_id, post_data=pipe._post_to_dict(model), comments=model.comments)
    ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(model)
    ctx._final_source_original_comment_refs = tuple(model.comments)
    identity = PickvelIdentity(is_relevant=False, discussion_type="general")
    notes, verify = pipe._consume_final_source_context(ctx, identity, None)
    assert verify() and not forbidden.attempts
    assert canonical(model.model_dump()) == before
    native = ctx._final_source_projection_native
    output = SimpleNamespace(_final_source_context_native=native, _final_source_context_owner=ctx)
    output._final_source_context_receipt = {"native_object":native, "context":ctx,
        "native_verification_status":"NATIVE_CALLBACK_TRUE"}
    diagnostics = export_source_context_diagnostics(output, enabled=True)
    assert diagnostics["publication_authority"] is False
    assert identity.novel_identity is None
    return pipe, ctx, identity, notes, verify, diagnostics

def test_saved7_author_question_and_comment_beneficiary_have_own_speakers_without_promoting_question():
    before = FIXTURE.read_bytes(); assert hashlib.sha256(before).hexdigest() == FIXTURE_SHA
    saved = json.loads(before)
    assert hashlib.sha256(canonical({"post":saved["source_post"],"comments":saved["source_comments"]})).hexdigest() == saved["source_canonical_sha256"]
    assert hashlib.sha256(canonical(saved["checkpoint_result"])).hexdigest() == saved["result_canonical_sha256"]
    pipe, ctx, identity, notes, verify, diag = consume(saved["source_post"], saved["source_comments"])
    native = ctx._final_source_projection_native
    question = "친구는 없으면,, 사이가 멀어지지 않음?"
    statement = "친구를 위해 내 이상성욕을 참는게 바로 우정임"
    claim = next(c for c in native.author_ledger.claims if c.text == question)
    assert (claim.speaker, claim.kind, claim.initial_support, claim.final_support) == ("self", "uncertain", False, False)
    assert claim.speaker_source == "unit_speaker" and claim.attribution == "direct_clause"
    comment_ledger = native.comment_ledgers[2]
    comment_claim = next(c for c in comment_ledger.claims if c.text == statement)
    assert comment_claim.speaker == "self" and comment_claim.kind == "own"
    assert comment_claim.speaker_source == "unit_speaker"
    assert question in identity.reason and statement in notes
    skipped = pipe._final_source_skipped_clause_observations(native)
    assert any(x["raw_text"] == question and x["skip"].reason == "unasserted_author_clause" and not x["counts_as_core"] for x in skipped)
    observed = [c for ledger in diag["ledgers"] for c in ledger["claims"] if c["text"] in (question, statement)]
    assert len(observed) == 2 and all(c["speaker"] == "self" for c in observed)
    assert verify() and FIXTURE.read_bytes() == before

@pytest.mark.parametrize("text,kind,support", [
    ("친구는 없으면,, 사이가 멀어지지 않음?", "uncertain", False),
    ("지인이 없으면, 혼자 지내야 하나?", "uncertain", False),
    ("친구를 위해 내가 먼저 연락했다.", "own", True),
    ("지인을 위해 내 시간을 쓰는 게 배려다.", "own", True),
    ("친구가 없으면 나는 혼자 지낼 것이다.", "uncertain", False),
    ("댓글은 없으면 내가 적겠다.", "uncertain", False),
    ("친구가 화면을 정리했다.", "own", True),
    ("친구는 라면을 샀다.", "own", True),
    ("친구는 말하기 연습을 했다.", "own", True),
])
def test_mentioned_person_is_not_the_speaker_and_uncertain_content_stays_unasserted(text, kind, support):
    ledger = _speaker_ledger((text,), source_id="author")
    assert len(ledger.claims) == 1
    claim = ledger.claims[0]
    assert (claim.speaker, claim.kind, claim.final_support) == ("self", kind, support)
    assert claim.speaker_source == "unit_speaker"
    cut = _author_clause_cut(text)
    assert cut[-1] == ("unasserted_author_clause" if not support else "")

@pytest.mark.parametrize("text", [
    "친구가 그러는데 내일 모이자.",
    "지인은 결말이 좋다고 하더라.",
    "친구 말로는 내일 모인다고 한다.",
    "댓글에서는 분량이 짧다고 한다.",
    "친구: 내일 모이자.",
    "댓글: 다음 편을 기다린다.",
    "결말이 좋다더라.",
])
def test_actual_report_or_speaker_marker_keeps_other_voice(text):
    claims = _speaker_ledger((text,), source_id="author").claims
    assert claims and all(c.speaker != "self" and c.kind == "reported" and not c.final_support for c in claims)
    assert _author_clause_cut(text)[-1] in {"reported_speaker_lead", "reported_tail"}

@pytest.mark.parametrize("text", [
    '친구는 "나는 이 작품을 읽었다."라고 말했다.',
    '친구는 "나는 이 작품을 읽었다."라고 말한 적이 없다.',
    '친구는 "나는 이 작품을 읽었다."라고 했나?',
    '친구는 "나는 이 작품을 읽었다."라고 한다면 어떨까?',
])
def test_quoted_friend_report_remains_external_and_unasserted(text):
    claims = _speaker_ledger((text,), source_id="author").claims
    quote = next(c for c in claims if c.text == "나는 이 작품을 읽었다.")
    assert quote.speaker == "친구" and not quote.final_support
    assert quote.kind in {"reported", "denied", "uncertain"}

@pytest.mark.parametrize("as_comment", [False, True])
def test_same_clause_keeps_its_source_unit_and_carrier_tamper_is_rejected(as_comment):
    text = "친구를 위해 내가 먼저 연락했다."
    comments = [{"comment_id":"c1", "author":"다른 화자", "content":text}] if as_comment else []
    post = {"post_id":901, "title":"관계 이야기", "content_blocks":[] if as_comment else [{"type":"text","text":text}]}
    pipe, ctx, identity, notes, verify, diag = consume(post, comments)
    native = ctx._final_source_projection_native
    ledger = native.comment_ledgers[0] if as_comment else native.author_ledger
    claim = next(c for c in ledger.claims if c.text == text)
    assert claim.speaker == "self" and claim.kind == "own"
    assert ledger.source_role == ("comment" if as_comment else "author")
    assert ("댓글 작성자 다른 화자" if as_comment else "작성자 발화") in notes
    if as_comment:
        ctx.comments[0]["content"] = "변경된 댓글"
    else:
        ctx.post_data["content_blocks"][0]["text"] = "변경된 본문"
    assert not verify()


# v2: 기존 23사례는 위 원형 그대로 두고 F1/F2 및 동의·철회 기능 대조를 잇는다.
@pytest.mark.parametrize("text,speaker,kind,support", [
    ("친구는 쉬고 나는 내일 오겠다고 말했다.", "self", "own", True),
    ("친구는 쉬었지만 저는 내일 오겠다고 말했다.", "self", "own", True),
    ("친구는 내가 내일 온다고 말했다.", "친구", "reported", False),
    ("친구는 우리가 내일 온다고 말했다.", "친구", "reported", False),
])
def test_report_predicate_binds_matrix_subject_after_join_not_quoted_content_subject(text, speaker, kind, support):
    ledger = _speaker_ledger((text,), source_id="author")
    assert len(ledger.claims) == 1
    claim = ledger.claims[0]
    assert (claim.speaker, claim.kind, claim.final_support) == (speaker, kind, support)
    assert _author_clause_cut(text)[-1] == ("" if speaker == "self" else "reported_speaker_lead")

@pytest.mark.parametrize("text,speaker", [
    ("친구:내일모이자.", "친구"),
    ("댓글：다음편기다린다.", "댓글"),
    ("친구가 말했어,내일모이자고.", "친구"),
    ("지인이 이야기했어요,내일모이자고.", "지인"),
])
def test_explicit_label_and_finite_speech_prefix_do_not_require_following_space(text, speaker):
    claims = _speaker_ledger((text,), source_id="author").claims
    assert claims and all((c.speaker, c.kind, c.final_support) == (speaker, "reported", False) for c in claims)
    assert _author_clause_cut(text)[-1] == "reported_speaker_lead"

@pytest.mark.parametrize("as_comment", [False, True])
@pytest.mark.parametrize("text,speaker", [
    ("친구는 쉬고 나는 내일 오겠다고 말했다.", "self"),
    ("친구:내일모이자.", "친구"),
])
def test_bound_source_to_native_export_keeps_correct_unit_and_speaker(text, speaker, as_comment):
    comments = [{"comment_id":"c1", "author":"댓글 작성자", "content":text}] if as_comment else []
    post = {"post_id":902, "title":"관계 이야기", "content_blocks":[] if as_comment else [{"type":"text", "text":text}]}
    _, ctx, _, _, verify, diagnostics = consume(post, comments)
    native = ctx._final_source_projection_native
    ledger = native.comment_ledgers[0] if as_comment else native.author_ledger
    claim = next(c for c in ledger.claims if c.text == text)
    assert claim.speaker == speaker and claim.final_support is (speaker == "self")
    exported = next(l for l in diagnostics["ledgers"] if l["source_role"] == ("comment" if as_comment else "author"))
    assert any(c["text"] == text and c["speaker"] == speaker for c in exported["claims"])
    assert verify()

@pytest.mark.parametrize("text,speaker", [
    ('친구는 쉬고 나는 "내일 온다."라고 말했다.', "self"),
    ('친구는 "내가 내일 온다."라고 말했다.', "친구"),
])
def test_explicit_quote_uses_its_own_frame_subject_without_changing_quote_scanner(text, speaker):
    claims = _speaker_ledger((text,), source_id="author").claims
    quote = next(c for c in claims if c.text in ("내일 온다.", "내가 내일 온다."))
    assert quote.speaker == speaker
    assert quote.kind == ("own" if speaker == "self" else "reported")
    assert quote.final_support is (speaker == "self")

@pytest.mark.parametrize("reported", ["친구:내일모이자.", "친구가 말했어,내일모이자고."])
def test_external_report_agreement_withdrawal_then_independent_self_statement(reported):
    own = "친구는 쉬고 나는 내일 오겠다고 말했다."
    parts = (reported, "나는 그 말에 동의한다.", "나는 내 동의를 철회한다.", own)
    ledger = _speaker_ledger(parts, source_id="author")
    external = next(c for c in ledger.claims if c.text == reported)
    assert external.speaker == "친구" and external.kind == "reported"
    assert not external.initial_support and not external.final_support and not external.active_adoption_event_ids
    effects = [a.applied_effect for a in ledger.applications if external.claim_id in a.target_claim_ids and a.applied_effect]
    assert effects == ["adopt", "withdraw"]
    own_claim = next(c for c in ledger.claims if c.text == own)
    assert own_claim.speaker == "self" and own_claim.kind == "own" and own_claim.final_support
