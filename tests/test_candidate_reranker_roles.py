"""원문 exact-title MENTIONED 관측 계약. 외부 자원·모델 호출 없음."""
from copy import deepcopy
import hashlib
import json

import pytest

from llm_batch.grounding import candidate_reranker_roles as roles
from llm_batch.grounding import candidate_reranker_shadow as shadow


def _sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _view(titles=("달빛기사",), text="달빛기사는 어떤가요?", *, fragments=None):
    return {"schema_version": shadow.VIEW_SCHEMA, "stage": "PRE_SELECTION", "post_id": 7,
        "candidate_namespace": "CORPUS_CANDIDATE", "generation_sha256": "a" * 64,
        "candidate_set_fingerprint": None, "generation_status": "COMPLETE",
        "source_view": {"schema_version": shadow.SOURCE_SCHEMA, "post_id": 7,
            "fragments": fragments if fragments is not None else [
                {"raw_path": "/content", "kind": "BODY", "text": text}]},
        "candidates": [{"candidate_id": f"corpus-{i}", "titles": [title], "urls": [],
            "aliases": [], "option_kind": "WORK_CANDIDATE", "event_eligible": True,
            "identity_conflict": False, "negative_evidence": [], "role_observations": []}
            for i, title in enumerate(titles)]}


def test_unicode_source_spans_hashes_and_all_other_fields_are_preserved():
    fragments = [{"raw_path": "/title", "kind": "TITLE", "text": "📚 달빛기사는?"},
        {"raw_path": "/content", "kind": "BODY", "text": "달빛기사\n달빛기사"},
        {"raw_path": "/comments/0/content", "kind": "COMMENT", "text": "달빛기사도 좋아요"}]
    original = _view(fragments=fragments)
    saved = deepcopy(original)
    view, metadata = roles.observe_preselection_roles(original)
    assert original == saved and view is not original
    observed = view["candidates"][0]["role_observations"]
    assert len(observed) == 4 and observed[0]["start"] == 2
    for item in observed:
        text = next(f["text"] for f in fragments if f["raw_path"] == item["raw_path"])
        assert item["role"] == "MENTIONED"
        assert text[item["start"]:item["end"]] == "달빛기사"
        assert item["text_sha256"] == hashlib.sha256("달빛기사".encode("utf-8")).hexdigest()
    stripped = deepcopy(view)
    stripped["candidates"][0]["role_observations"] = []
    assert stripped == original
    assert metadata["frozen_view_sha256"] == _sha(view)
    assert roles.validate_metadata(metadata, frozen_view=view) == metadata


@pytest.mark.parametrize("text", ["달빛기사", "(달빛기사)", " 달빛기사 ",
    "\n달빛기사\n", "\t달빛기사\t", "\r달빛기사\r", "\r\n달빛기사\r\n",
    "달빛기사는", "달빛기사에서는 좋아요", "달빛기사도", "달빛기사은요", "달빛기사를?"])
def test_explicit_word_and_complete_particle_boundaries(text):
    view, meta = roles.observe_preselection_roles(_view(text=text))
    assert meta["status"] == "OBSERVED" and meta["counts"]["observations"] == 1
    assert len(view["candidates"][0]["role_observations"]) == 1


@pytest.mark.parametrize("text", ["신달빛기사", "달빛기사전", "달빛기사은행",
    "달빛기사이름", "_달빛기사", "달빛기사_", "x달빛기사", "달빛기사x",
    "달빛기사\u0301", "\u0301달빛기사", "달빛기사\u200d", "\u200d달빛기사"])
def test_partial_word_mark_and_format_boundaries_are_not_mentions(text):
    view, meta = roles.observe_preselection_roles(_view(text=text))
    assert meta["status"] == "NO_MATCH"
    assert meta["counts"]["boundary_rejected"] == 1
    assert view["candidates"][0]["role_observations"] == []


def test_case_unicode_normalization_and_regex_are_literal():
    view, meta = roles.observe_preselection_roles(_view(("DUNE", "가", "[A+B]"), "dune 가 [A+B]"))
    assert [len(c["role_observations"]) for c in view["candidates"]] == [0, 0, 1]
    assert meta["counts"]["observations"] == 1


def test_same_title_on_different_ids_is_not_arbitrarily_bound():
    view, meta = roles.observe_preselection_roles(_view(("달빛기사", "달빛기사")))
    assert meta["status"] == "AMBIGUOUS" and meta["counts"]["ambiguous_spans"] == 1
    assert all(not candidate["role_observations"] for candidate in view["candidates"])
    assert roles.validate_metadata(meta, frozen_view=view) == meta


@pytest.mark.parametrize("same_candidate", [False, True])
def test_overlapping_boundary_valid_titles_all_remain_unbound(same_candidate):
    original = _view(("별빛 기록", "기록"), "별빛 기록")
    if same_candidate:
        original["candidates"] = original["candidates"][:1]
        original["candidates"][0]["titles"].append("기록")
    view, meta = roles.observe_preselection_roles(original)
    assert meta["status"] == "AMBIGUOUS" and meta["counts"]["ambiguous_spans"] == 2
    assert all(not candidate["role_observations"] for candidate in view["candidates"])


def test_partial_short_title_does_not_invalidate_exact_long_title():
    view, meta = roles.observe_preselection_roles(_view(("달빛기사", "달빛기사전"), "달빛기사전"))
    assert [len(c["role_observations"]) for c in view["candidates"]] == [0, 1]
    assert meta["counts"]["boundary_rejected"] == 1


def test_ambiguous_and_unique_mentions_preserve_both_outcomes():
    view, meta = roles.observe_preselection_roles(_view(("동명", "동명", "유일"), "동명 유일"))
    assert meta["status"] == "OBSERVED"
    assert [len(c["role_observations"]) for c in view["candidates"]] == [0, 0, 1]
    assert meta["counts"]["ambiguous_spans"] == 1
    assert "AMBIGUOUS_TITLE_SPANS_UNBOUND" in meta["reason_codes"]


def test_duplicate_title_same_candidate_is_one_observation_and_aliases_are_ignored():
    original = _view(text="달빛기사 달기사")
    original["candidates"][0]["titles"].append("달빛기사")
    original["candidates"][0]["aliases"] = ["달기사"]
    view, meta = roles.observe_preselection_roles(original)
    assert meta["counts"]["unique_titles"] == meta["counts"]["observations"] == 1
    assert view["candidates"][0]["aliases"] == ["달기사"]


def test_existing_supplied_roles_are_rejected_without_mutation():
    original, _ = roles.observe_preselection_roles(_view())
    saved = deepcopy(original)
    with pytest.raises(roles.RoleObservationError, match="ROLE_INPUT_NOT_EMPTY"):
        roles.observe_preselection_roles(original)
    assert original == saved


def test_repeated_source_text_keeps_fragment_identity_and_order():
    fragments = [{"raw_path": f"/comments/{i}/content", "kind": "COMMENT", "text": "달빛기사"}
                 for i in (1, 0)]
    view, meta = roles.observe_preselection_roles(_view(fragments=fragments))
    assert [r["raw_path"] for r in view["candidates"][0]["role_observations"]] == [f["raw_path"] for f in fragments]
    assert meta["counts"]["observations"] == 2


def test_per_candidate_limit_accepts_exact_bound_and_rejects_overflow_without_partial_result():
    view, meta = roles.observe_preselection_roles(_view(text="달빛기사 " * 32))
    assert len(view["candidates"][0]["role_observations"]) == meta["counts"]["observations"] == 32
    original = _view(text="달빛기사 " * 33)
    saved = deepcopy(original)
    with pytest.raises(roles.RoleObservationError, match="ROLE_OBSERVATION_LIMIT"):
        roles.observe_preselection_roles(original)
    assert original == saved


def test_total_limit_accepts_128_and_rejects_129_without_truncation():
    titles = ("Alpha", "Bravo", "Charlie", "Delta", "Echo")
    original = _view(titles, " ".join((title + " ") * 32 for title in titles[:4]))
    view, meta = roles.observe_preselection_roles(original)
    assert meta["counts"]["observations"] == 128
    assert roles.validate_metadata(meta, frozen_view=view) == meta
    original["source_view"]["fragments"][0]["text"] += " Echo"
    saved = deepcopy(original)
    with pytest.raises(roles.RoleObservationError, match="ROLE_OBSERVATION_LIMIT"):
        roles.observe_preselection_roles(original)
    assert original == saved


def test_raw_match_scan_cap_is_explicit_even_when_all_matches_ambiguous():
    original = _view(("X", "X"), "X " * 4097)
    with pytest.raises(roles.RoleObservationError, match="ROLE_MATCH_SCAN_LIMIT"):
        roles.observe_preselection_roles(original)
    assert all(not c["role_observations"] for c in original["candidates"])


@pytest.mark.parametrize("kind", ["empty_candidates", "urls_only", "empty_source"])
def test_no_match_and_empty_inputs_remain_honest(kind):
    original = _view()
    if kind == "empty_candidates": original["candidates"] = []
    if kind == "urls_only":
        original["candidates"][0].update(titles=[], urls=["https://example.invalid/work"])
    if kind == "empty_source": original["source_view"]["fragments"] = []
    view, meta = roles.observe_preselection_roles(original)
    assert meta["status"] == "NO_MATCH" and meta["counts"]["observations"] == 0
    assert roles.validate_metadata(meta, frozen_view=view) == meta


@pytest.mark.parametrize("generation", ["TRUNCATED", "UNKNOWN"])
def test_observer_does_not_upgrade_generation_or_scoring_eligibility(generation):
    original = _view()
    original["generation_status"] = generation
    view, meta = roles.observe_preselection_roles(original)
    assert view["generation_status"] == generation and meta["status"] == "OBSERVED"
    receipt = shadow.unavailable_scorer().score(view)
    assert receipt["status"] == "NOT_SCORED_GENERATION_" + generation
    assert receipt["ranked_candidates"] == []


def test_candidate_identity_order_and_flags_are_not_changed_or_used_as_roles():
    original = _view(("달빛기사", "다른기사"), "달빛기사 다른기사")
    original["candidates"].reverse()
    original["candidates"][0].update(event_eligible=False, identity_conflict=True,
        negative_evidence=["not a primary target"])
    view, _ = roles.observe_preselection_roles(original)
    for before, after in zip(original["candidates"], view["candidates"]):
        assert {k: v for k, v in after.items() if k != "role_observations"} == {k: v for k, v in before.items() if k != "role_observations"}
        assert [r["role"] for r in after["role_observations"]] == ["MENTIONED"]


@pytest.mark.parametrize("fault", ["post", "path", "extra", "stage", "duplicate_id"])
def test_existing_frozen_view_validation_is_not_bypassed(fault):
    original = _view(("달빛기사", "다른기사"))
    if fault == "post": original["source_view"]["post_id"] = "7"
    if fault == "path": original["source_view"]["fragments"][0]["raw_path"] = "/result/title"
    if fault == "extra": original["selected_candidate_id"] = "corpus-0"
    if fault == "stage": original["stage"] = "POST_SELECTION"
    if fault == "duplicate_id": original["candidates"][1]["candidate_id"] = "corpus-0"
    with pytest.raises(shadow.CandidateRerankerShadowError):
        roles.observe_preselection_roles(original)


@pytest.mark.parametrize("fault", ["policy", "status", "bool_count", "digest", "count", "extra", "reason"])
def test_metadata_tampering_is_rejected(fault):
    view, meta = roles.observe_preselection_roles(_view())
    if fault == "policy": meta["policy_sha256"] = "0" * 64
    if fault == "status": meta["status"] = "NO_MATCH"
    if fault == "bool_count": meta["counts"]["observations"] = True
    if fault == "digest": meta["frozen_view_sha256"] = "0" * 64
    if fault == "count": meta["counts"]["raw_matches"] += 1
    if fault == "extra": meta["gold"] = True
    if fault == "reason": meta["reason_codes"] = ["GOLD_CONFIRMED"]
    with pytest.raises(roles.RoleObservationError):
        roles.validate_metadata(meta, frozen_view=view)


@pytest.mark.parametrize("forgery", ["PRIMARY", "non_title_span"])
def test_resealed_metadata_does_not_approve_injected_role_or_non_title_span(forgery):
    view, meta = roles.observe_preselection_roles(_view(text="달빛기사 다른말"))
    observation = view["candidates"][0]["role_observations"][0]
    if forgery == "PRIMARY": observation["role"] = "PRIMARY"
    else:
        observation.update(start=5, end=8, text_sha256=hashlib.sha256("다른말".encode("utf-8")).hexdigest())
    meta["frozen_view_sha256"] = _sha(view)
    with pytest.raises(roles.RoleObservationError, match="ROLE_METADATA_REPLAY_MISMATCH"):
        roles.validate_metadata(meta, frozen_view=view)


def test_metadata_validation_returns_private_copy_and_observations_are_deterministic():
    first_view, first_meta = roles.observe_preselection_roles(_view())
    second_view, second_meta = roles.observe_preselection_roles(_view())
    assert (first_view, first_meta) == (second_view, second_meta)
    checked = roles.validate_metadata(first_meta, frozen_view=first_view)
    checked["counts"]["observations"] = 99
    assert first_meta["counts"]["observations"] == 1


@pytest.mark.parametrize("status", ["NOT_EXECUTED", "ERROR", "LIMIT_EXCEEDED", "INVALID_INPUT"])
def test_nonexecution_metadata_does_not_claim_source_binding(status):
    meta = roles.not_executed_metadata("UPSTREAM_UNAVAILABLE", status=status)
    assert meta["status"] == status and meta["frozen_view_sha256"] is None
    assert all(value is None for value in meta["counts"].values())
    assert roles.validate_metadata(meta) == meta
    with pytest.raises(roles.RoleObservationError):
        roles.validate_metadata(meta, frozen_view=_view())


def test_nonexecution_helper_rejects_executed_status_and_invalid_reason():
    with pytest.raises(roles.RoleObservationError):
        roles.not_executed_metadata(status="OBSERVED")
    with pytest.raises(roles.RoleObservationError):
        roles.not_executed_metadata("not a reason")


def test_policy_explicitly_limits_authority_and_semantic_scope():
    assert roles.POLICY_SHA256 == _sha(roles.POLICY)
    assert roles.POLICY["semantic_roles_supported"] == ["MENTIONED"]
    assert roles.POLICY["semantic_roles_not_implemented"] == ["PRIMARY", "PREVIOUS", "COMPARISON"]
    assert roles.POLICY["authority"] == "SOURCE_OBSERVATION_NOT_GOLD"
    assert roles.POLICY["publication_authority"] is roles.POLICY["public_apply"] is roles.POLICY["central_db_write"] is False
