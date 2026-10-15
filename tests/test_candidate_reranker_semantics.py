"""원문 의미역할의 양성/음성·좌표·재생·별칭 경계. 실행은 root 묶음에서만."""
from copy import deepcopy
import hashlib
import json

import pytest

from llm_batch.grounding import candidate_reranker_semantics as semantics
from llm_batch.grounding import candidate_reranker_roles as roles
from llm_batch.grounding import candidate_reranker_shadow as shadow


def make_semantics_view(text="나는 달빛 기사를 리뷰한다.", titles=("달빛 기사", "별빛 기록"), *, fragments=None):
    return {"schema_version": shadow.VIEW_SCHEMA, "stage": "PRE_SELECTION", "post_id": 71,
        "candidate_namespace": "CORPUS_CANDIDATE", "generation_sha256": "a" * 64,
        "candidate_set_fingerprint": None, "generation_status": "COMPLETE",
        "source_view": {"schema_version": shadow.SOURCE_SCHEMA, "post_id": 71,
            "fragments": fragments if fragments is not None else [{"raw_path": "/content", "kind": "BODY", "text": text}]},
        "candidates": [{"candidate_id": f"corpus-{i}", "titles": [title], "urls": [], "aliases": [],
            "option_kind": "WORK_CANDIDATE", "event_eligible": True, "identity_conflict": False,
            "negative_evidence": [], "role_observations": []} for i, title in enumerate(titles)]}


def _sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _assert_spans(original, receipt):
    texts = {f["raw_path"]: f["text"] for f in original["source_view"]["fragments"]}
    for row in receipt["observations"]:
        for span in [row["mention"], *row["relation_cues"], *row["related_mentions"]]:
            text = texts[span["raw_path"]]
            assert text[span["start"]:span["end"]] == span["text"]
            raw = text.encode("utf-8")[span["byte_start"]:span["byte_end"]]
            assert raw.decode("utf-8") == span["text"]
            assert hashlib.sha256(raw).hexdigest() == span["text_sha256"]
        if row["role"] != "MENTIONED":
            assert row["relation_cues"] and row["speaker"] == "AUTHOR" and row["assertion"] == "ASSERTED"


@pytest.mark.parametrize(("text", "role", "surface"), [
    ("나는 달빛 기사를 리뷰한다.", "PRIMARY", "달빛 기사"),
    ("이 글에서는 달빛 기사를 평가했습니다.", "PRIMARY", "달빛 기사"),
    ("이 글의 논의 대상은 달빛 기사이다.", "PRIMARY", "달빛 기사"),
    ("달빛 기사는 김하늘 작가의 전작이다.", "PREVIOUS", "달빛 기사"),
    ("김하늘 작가의 이전 작품은 달빛 기사입니다.", "PREVIOUS", "달빛 기사"),
    ("별빛 기록을 쓴 작가의 전작은 달빛 기사이다.", "PREVIOUS", "달빛 기사"),
    ("달빛 기사는 별빛 기록을 쓴 작가의 전작이다.", "PREVIOUS", "달빛 기사"),
    ("달빛 기사보다 별빛 기록이 더 좋다.", "COMPARISON", "달빛 기사"),
    ("별빛 기록은 달빛 기사와 비슷하다.", "COMPARISON", "달빛 기사"),
])
def test_explicit_author_relation_has_exact_proof_and_replays(text, role, surface):
    original = make_semantics_view(text)
    saved = deepcopy(original)
    enriched, receipt = semantics.observe_preselection_semantics(original)
    rows = [r for r in receipt["observations"] if r["role"] == role]
    assert len(rows) == 1 and rows[0]["mention"]["text"] == surface
    assert original == saved
    assert receipt["score_consumption_status"] == "NOT_CONSUMED_MODEL_POLICY_UNBOUND"
    assert receipt["publication_authority"] is receipt["public_apply"] is receipt["central_db_write"] is False
    assert receipt["receipt_sha256"] == _sha({k: v for k, v in receipt.items() if k != "receipt_sha256"})
    assert semantics.validate_semantic_observation(original, enriched, receipt) == receipt
    _assert_spans(original, receipt)
    stripped = deepcopy(enriched)
    for candidate in stripped["candidates"]:
        candidate["role_observations"] = []
    assert stripped == original


@pytest.mark.parametrize("text", [
    "예전에 달빛 기사를 읽었다.", "달빛 기사는 이미 봤으니 빼 달라.",
    "달빛 기사는 작가의 전작이다.", "달빛 기사는 해당 작가의 전작이다.",
    "달빛 기사 작가의 신작이 나왔다.", "달빛 기사와 별빛 기록을 읽었다.",
    "달빛 기사 같은 성격이다.", "달빛 기사처럼 뛰었다.",
    "달빛 기사가 등장하는 제목이다.", "달빛 기사보다 장르가 더 좋다.",
    "별빛 기록은 달빛 기사와 비슷하지 않다.", "달빛 기사보다 별빛 기록이 더 좋지 않다.",
    "나는 달빛 기사를 리뷰하지 않는다.", "나는 달빛 기사를 리뷰한다고 들었다.",
    "나는 달빛 기사를 리뷰한다면 좋겠다.", "나는 달빛 기사를 리뷰한다?",
    "친구가 나는 달빛 기사를 리뷰한다고 말했다.", "철수가 달빛 기사를 리뷰한다.",
    "김하늘 작가의 전작은 달빛 기사이다라고 들었다.",
    "“김하늘 작가의 전작은 달빛 기사이다.",
    "나는 달빛 기사를 리뷰한다.\n아니다. 잘못 썼다.",
])
def test_reader_history_unknown_owner_nonwork_negation_report_question_do_not_promote(text):
    _, receipt = semantics.observe_preselection_semantics(make_semantics_view(text))
    assert receipt["observations"]
    assert {r["role"] for r in receipt["observations"]} == {"MENTIONED"}
    assert receipt["counts"]["semantic_observations"] == 0


def test_comment_and_multiline_report_remain_mentions_with_reasons():
    original = make_semantics_view(fragments=[
        {"raw_path": "/content", "kind": "BODY", "text": "친구: “\r\n나는 달빛 기사를 리뷰한다.\r\n”\r\n나는 별빛 기록을 평가한다."},
        {"raw_path": "/comments/0/content", "kind": "COMMENT", "text": "나는 달빛 기사를 리뷰한다."}])
    _, receipt = semantics.observe_preselection_semantics(original)
    assert [r["role"] for r in receipt["observations"]] == ["MENTIONED", "PRIMARY", "MENTIONED"]
    reasons = {reason for item in receipt["unresolved"] for reason in item["reason_codes"]}
    assert "COMMENT_SEMANTICS_DEFERRED" in reasons
    assert "QUOTED_OR_REMOVED_SOURCE" in reasons or "SOURCE_EMPTY_AFTER_REMOVAL" in reasons
    _assert_spans(original, receipt)


def test_unicode_crlf_repeated_clauses_are_distinct_and_do_not_promote_whole_post():
    text = "📚 기록\r\n나는 달빛 기사를 리뷰한다.\r\n달빛 기사를 읽었다.\r\n나는 달빛 기사를 리뷰한다."
    original = make_semantics_view(text)
    _, receipt = semantics.observe_preselection_semantics(original)
    assert [r["role"] for r in receipt["observations"]] == ["PRIMARY", "MENTIONED", "PRIMARY"]
    starts = [r["mention"]["start"] for r in receipt["observations"]]
    assert len(set(starts)) == 3 and starts == sorted(starts)
    _assert_spans(original, receipt)


def test_previous_and_current_are_occurrence_roles_not_selected_labels():
    original = make_semantics_view("김하늘 작가의 전작은 달빛 기사이다. 나는 별빛 기록을 리뷰한다. 달빛 기사를 읽었다.")
    _, receipt = semantics.observe_preselection_semantics(original)
    assert [(r["mention"]["text"], r["role"]) for r in receipt["observations"]] == [
        ("달빛 기사", "PREVIOUS"), ("별빛 기록", "PRIMARY"), ("달빛 기사", "MENTIONED")]


@pytest.mark.parametrize(("titles", "text"), [
    (("달빛 기사", "달빛 기사"), "나는 달빛 기사를 리뷰한다."),
    (("달빛 기사", "기사"), "나는 달빛 기사를 리뷰한다."),
])
def test_shared_or_overlapping_mentions_are_not_arbitrarily_bound(titles, text):
    enriched, receipt = semantics.observe_preselection_semantics(make_semantics_view(text, titles))
    assert receipt["status"] == "AMBIGUOUS" and not receipt["observations"]
    assert all(not c["role_observations"] for c in enriched["candidates"])
    assert receipt["unresolved"]


def test_unbound_comparison_target_does_not_grant_other_candidate_a_relation():
    _, receipt = semantics.observe_preselection_semantics(make_semantics_view(
        "달빛 기사보다 별빛 기록이 더 좋다.", ("달빛 기사", "별빛 기록", "별빛 기록")))
    assert [(r["mention"]["text"], r["role"]) for r in receipt["observations"]] == [("달빛 기사", "MENTIONED")]


def test_ineligible_or_conflicted_work_does_not_get_semantic_role():
    for conflict in (False, True):
        original = make_semantics_view()
        original["candidates"][0].update(event_eligible=False, identity_conflict=conflict)
        _, receipt = semantics.observe_preselection_semantics(original)
        assert receipt["counts"]["primary"] == 0
        assert receipt["unresolved"]


def test_exact_boundaries_and_unverified_input_aliases_are_not_consumed():
    original = make_semantics_view("나는 신달빛 기사를 리뷰한다. 아생갤", ("달빛 기사",))
    original["candidates"][0]["aliases"] = ["아생갤"]
    enriched, receipt = semantics.observe_preselection_semantics(original)
    assert receipt["status"] == "NO_MATCH" and enriched == original
    assert receipt["counts"]["boundary_rejected"] == 1


def test_opaque_titles_are_not_read_as_negation_and_copula_suffix_is_complete():
    original = make_semantics_view("나는 아니 없는 소설을 리뷰한다.", ("아니 없는 소설",))
    assert semantics.observe_preselection_semantics(original)[1]["counts"]["primary"] == 1
    _, receipt = semantics.observe_preselection_semantics(make_semantics_view(
        "달빛 기사이다전", ("달빛 기사",)))
    assert receipt["status"] == "NO_MATCH"


@pytest.mark.parametrize("tamper", ["role", "cue", "span", "policy", "counts", "source", "ids", "authority"])
def test_resealing_does_not_hide_changed_role_proof_source_order_or_authority(tamper):
    original = make_semantics_view()
    enriched, receipt = semantics.observe_preselection_semantics(original)
    if tamper == "role":
        receipt["observations"][0]["role"] = "PREVIOUS"
    elif tamper == "cue":
        receipt["observations"][0]["relation_cues"] = []
    elif tamper == "span":
        receipt["observations"][0]["mention"]["byte_start"] += 1
    elif tamper == "policy":
        receipt["policy_sha256"] = "0" * 64
    elif tamper == "counts":
        receipt["counts"]["primary"] += 1
    elif tamper == "source":
        original["source_view"]["fragments"][0]["text"] += " 바뀜"
    elif tamper == "ids":
        enriched["candidates"].reverse()
    else:
        receipt["public_apply"] = True
    receipt["receipt_sha256"] = _sha({k: v for k, v in receipt.items() if k != "receipt_sha256"})
    with pytest.raises(semantics.SemanticObservationError):
        semantics.validate_semantic_observation(original, enriched, receipt)


def test_input_roles_must_be_empty_and_v1_is_unchanged():
    original = make_semantics_view()
    v1, metadata = roles.observe_preselection_roles(original)
    assert {r["role"] for c in v1["candidates"] for r in c["role_observations"]} == {"MENTIONED"}
    with pytest.raises(semantics.SemanticObservationError, match="SEMANTIC_INPUT_ROLES_NOT_EMPTY"):
        semantics.observe_preselection_semantics(v1)
    semantics.observe_preselection_semantics(original)
    assert roles.observe_preselection_roles(original) == (v1, metadata)


def test_reuse_is_deterministic_and_has_no_cross_post_context():
    first = make_semantics_view()
    before = semantics.observe_preselection_semantics(first)
    second = make_semantics_view("김하늘 작가의 전작은 달빛 기사이다.")
    second["post_id"] = second["source_view"]["post_id"] = 72
    assert semantics.observe_preselection_semantics(second)[1]["counts"]["previous"] == 1
    assert semantics.observe_preselection_semantics(first) == before


def test_limit_has_no_partial_result_and_does_not_mutate_input():
    original = make_semantics_view("\n".join(["나는 달빛 기사를 리뷰한다."] * 33))
    saved = deepcopy(original)
    with pytest.raises(semantics.SemanticObservationError, match="SEMANTIC_PER_CANDIDATE_LIMIT"):
        semantics.observe_preselection_semantics(original)
    assert original == saved


def test_receipt_byte_limit_is_explicit(monkeypatch):
    monkeypatch.setattr(semantics, "MAX_RECEIPT_BYTES", 500)
    with pytest.raises(semantics.SemanticObservationError, match="SEMANTIC_RECEIPT_BYTE_LIMIT"):
        semantics.observe_preselection_semantics(make_semantics_view())


@pytest.mark.parametrize("status", ["NOT_EXECUTED", "ERROR", "LIMIT_EXCEEDED", "INVALID_INPUT"])
def test_nonexecution_receipt_is_explicit_and_has_no_fake_source_binding(status):
    receipt = semantics.not_executed_receipt("PIPELINE_NOT_EXECUTED", status=status)
    assert receipt["status"] == status
    assert receipt["observations"] == receipt["unresolved"] == []
    assert set(receipt["counts"].values()) == {None}
    assert receipt["source_view_sha256"] is receipt["frozen_view_sha256"] is None
    assert receipt["score_consumption_status"] == semantics.SCORE_CONSUMPTION_STATUS


def test_alias_requires_real_validator_and_preserves_evidence(tmp_path):
    from test_candidate_reranker_alias_evidence import build_alias_fixture
    fixture = build_alias_fixture(tmp_path)
    original = fixture["frozen_view"]
    saved = deepcopy(original)
    enriched, receipt = semantics.observe_preselection_semantics(original,
        alias_evidence=fixture["call_evidence"], evidence_payloads=fixture["evidence_payloads"])
    assert original == saved
    assert receipt["alias_validation"]["bindings"]
    assert receipt["counts"]["alias_observations"] > 0
    assert all(r["alias_evidence_ids"] for r in receipt["observations"] if r["mention_kind"] == "VERIFIED_ALIAS")
    assert semantics.validate_semantic_observation(original, enriched, receipt,
        alias_evidence=fixture["call_evidence"], evidence_payloads=fixture["evidence_payloads"]) == receipt
    _assert_spans(original, receipt)
    changed = dict(fixture["evidence_payloads"])
    digest = next(iter(changed))
    changed[digest] += b" "
    with pytest.raises(semantics.SemanticObservationError):
        semantics.validate_semantic_observation(original, enriched, receipt,
            alias_evidence=fixture["call_evidence"], evidence_payloads=changed)


def test_no_final_projection_or_io_used(monkeypatch):
    from llm_batch.grounding import context_projection_contract as context
    def forbidden(*args, **kwargs):
        raise AssertionError("Final projection and I/O are not source observation")
    monkeypatch.setattr(context, "project_context_native", forbidden)
    monkeypatch.setattr("builtins.open", forbidden)
    enriched, receipt = semantics.observe_preselection_semantics(make_semantics_view())
    assert receipt["counts"]["primary"] == 1
    assert enriched["candidates"][0]["role_observations"][0]["role"] == "PRIMARY"


@pytest.mark.parametrize(("opening", "closing"), [("“", "”"), ('"', '"'), ("‘", "’"), ("'", "'"), ("「", "」"), ("『", "』")])
@pytest.mark.parametrize("closed", [True, False])
def test_multiline_quote_context_never_promotes_quoted_first_person(opening, closing, closed):
    text = "친구: " + opening + "\n나는 달빛 기사를 리뷰한다."
    if closed:
        text += "\n" + closing + "\n나는 별빛 기록을 리뷰한다."
    original = make_semantics_view(text)
    enriched, receipt = semantics.observe_preselection_semantics(original)
    first = [row for row in receipt["observations"] if row["mention"]["text"] == "달빛 기사"]
    assert len(first) == 1 and first[0]["role"] == "MENTIONED"
    assert first[0]["assertion"] == "MENTION_ONLY"
    assert any(set(item["reason_codes"]) & {"QUOTED_OR_REMOVED_SOURCE", "UNBALANCED_QUOTATION"} for item in receipt["unresolved"])
    if closed:
        assert [row["role"] for row in receipt["observations"] if row["mention"]["text"] == "별빛 기록"] == ["PRIMARY"]
    assert semantics.validate_semantic_observation(original, enriched, receipt) == receipt
    _assert_spans(original, receipt)


def test_nested_quote_and_crossed_delimiters_do_not_restore_author_prematurely():
    text = '친구: “「\n나는 달빛 기사를 리뷰한다.\n」\n나는 별빛 기록을 리뷰한다.\n”'
    original = make_semantics_view(text)
    _, receipt = semantics.observe_preselection_semantics(original)
    assert [row["role"] for row in receipt["observations"]] == ["MENTIONED", "MENTIONED"]
    crossed = make_semantics_view('친구: “「\n나는 달빛 기사를 리뷰한다.\n”\n나는 별빛 기록을 리뷰한다.')
    _, receipt = semantics.observe_preselection_semantics(crossed)
    assert receipt["counts"]["semantic_observations"] == 0
    _assert_spans(crossed, receipt)


def test_quote_carries_across_body_fragments_but_not_title_or_comment():
    original = make_semantics_view(fragments=[
        {"raw_path": "/title", "kind": "TITLE", "text": "나는 별빛 기록을 리뷰한다."},
        {"raw_path": "/content_blocks/0/text", "kind": "BODY", "text": '친구: "'},
        {"raw_path": "/content_blocks/1/text", "kind": "BODY", "text": "나는 달빛 기사를 리뷰한다."},
        {"raw_path": "/comments/0/content", "kind": "COMMENT", "text": "나는 달빛 기사를 리뷰한다."}])
    _, receipt = semantics.observe_preselection_semantics(original)
    assert [(row["mention"]["raw_path"], row["role"]) for row in receipt["observations"]] == [
        ("/title", "PRIMARY"), ("/content_blocks/1/text", "MENTIONED"), ("/comments/0/content", "MENTIONED")]
    _assert_spans(original, receipt)


@pytest.mark.parametrize("label", ["김철수:", "user_27:", "김철수 작가：", "- 독자17:", "John Smith:", "김 철수：",
    "John Michael David Charles William Smith:", "Élodie Martin:", "山田 太郎：", "박 연구원 (검토자):"])
def test_named_colon_speaker_is_not_author_assertion(label):
    original = make_semantics_view(label + " 달빛 기사는 김하늘 작가의 전작이다. 나는 별빛 기록을 리뷰한다.")
    _, receipt = semantics.observe_preselection_semantics(original)
    assert receipt["counts"]["semantic_observations"] == 0
    assert all(row["role"] == "MENTIONED" for row in receipt["observations"])
    assert any("SOURCE_SPEAKER_LABEL_UNRESOLVED" in item["reason_codes"] for item in receipt["unresolved"])
    _assert_spans(original, receipt)


@pytest.mark.parametrize("label", ["김철수:", "John Smith:", "김 철수："])
def test_inline_speaker_label_holds_following_clauses_without_rewriting_prior_author(label):
    text = "나는 별빛 기록을 리뷰한다. 안내. " + label + " 달빛 기사는 김하늘 작가의 전작이다. 나는 별빛 기록을 리뷰한다."
    original = make_semantics_view(text)
    enriched, receipt = semantics.observe_preselection_semantics(original)
    assert [row["role"] for row in receipt["observations"]] == ["PRIMARY", "MENTIONED", "MENTIONED"]
    assert receipt["counts"]["semantic_observations"] == 1
    assert semantics.validate_semantic_observation(original, enriched, receipt) == receipt
    _assert_spans(original, receipt)


def test_closed_inline_quoted_speaker_does_not_capture_later_author_clause():
    original = make_semantics_view('안내. John Smith: “달빛 기사는 김하늘 작가의 전작이다”. 나는 별빛 기록을 리뷰한다.')
    _, receipt = semantics.observe_preselection_semantics(original)
    assert [row["role"] for row in receipt["observations"]] == ["MENTIONED", "PRIMARY"]
    _assert_spans(original, receipt)


@pytest.mark.parametrize("prefix", ["https://example.invalid 안내.", "12:30 안내."])
def test_url_and_numeric_time_colons_do_not_create_speaker_scope(prefix):
    original = make_semantics_view(prefix + " 나는 별빛 기록을 리뷰한다.")
    _, receipt = semantics.observe_preselection_semantics(original)
    assert [row["role"] for row in receipt["observations"]] == ["PRIMARY"]
    _assert_spans(original, receipt)


def test_speaker_label_without_closure_is_carried_to_next_body_line():
    original = make_semantics_view("김철수:\n달빛 기사는 김하늘 작가의 전작이다.\n나는 별빛 기록을 리뷰한다.")
    _, receipt = semantics.observe_preselection_semantics(original)
    assert receipt["counts"]["semantic_observations"] == 0
    assert len(receipt["observations"]) == 2


@pytest.mark.parametrize("text", [
    "나는 달빛 기사를 리뷰한다면 사겠다.",
    "나는 달빛 기사를 리뷰했다면 달랐을 것이다.",
    "이 글의 논의 대상은 달빛 기사이었다면 좋겠다.",
    "달빛 기사는 김하늘 작가의 전작이었다면 좋겠다.",
    "달빛 기사보다 별빛 기록이 더 좋다면 사겠다.",
    "별빛 기록은 달빛 기사와 비슷하다면 사겠다.",
])
def test_primary_previous_and_comparison_conditional_suffixes_are_not_assertions(text):
    original = make_semantics_view(text)
    enriched, receipt = semantics.observe_preselection_semantics(original)
    assert receipt["observations"] and receipt["counts"]["semantic_observations"] == 0
    assert all(row["role"] == "MENTIONED" for row in receipt["observations"])
    assert any("CONDITIONAL_RELATION" in item["reason_codes"] for item in receipt["unresolved"])
    assert semantics.validate_semantic_observation(original, enriched, receipt) == receipt
    _assert_spans(original, receipt)


def test_conditional_and_speaker_cues_inside_opaque_title_do_not_change_positive_rule():
    original = make_semantics_view("나는 가면: 기록을 리뷰한다.", ("가면: 기록",))
    assert semantics.observe_preselection_semantics(original)[1]["counts"]["primary"] == 1
    original = make_semantics_view("가면: 기록은 김하늘 작가의 전작이다.", ("가면: 기록",))
    assert semantics.observe_preselection_semantics(original)[1]["counts"]["previous"] == 1
    original = make_semantics_view("안내. John Smith: 기록은 김하늘 작가의 전작이다. 나는 별빛 기록을 리뷰한다.", ("John Smith: 기록", "별빛 기록"))
    enriched, receipt = semantics.observe_preselection_semantics(original)
    assert [row["role"] for row in receipt["observations"]] == ["PREVIOUS", "PRIMARY"]
    assert semantics.validate_semantic_observation(original, enriched, receipt) == receipt
    _assert_spans(original, receipt)
