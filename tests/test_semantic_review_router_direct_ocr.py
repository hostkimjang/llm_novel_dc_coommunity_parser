"""최종 OCR HOLD의 검토 연결과 기존 v1 보존. 실제 base closure는 별도 시험이다."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from src.llm_batch.measurement import semantic_review_router as router
from src.llm_batch.measurement.semantic_recovery_plan import build_semantic_recovery_plan_receipt
from src.llm_batch.ledger.publication_commit import (
    PUBLICATION_COMMIT_EVENT_SCHEMA, compute_publication_decision_commit,
)
from src.llm_batch.ledger.recovery_activation import _create_event, extract_direct_ocr_review_proposals
from src.llm_batch.promotion_gate import (
    EvidenceRecord, GroundingState, ScopeState, apply_publish_contract, evaluate_publish_contract,
)
from tests.recovery_execution_fixtures import _hold_result, json_bytes
from tests.test_semantic_review_router import _result, _commit


def _sha(value):
    return hashlib.sha256(json_bytes(value)).hexdigest()


def _direct_hold():
    # 실패한 실제 WAL처럼 선택된 제목 없는 inventory HOLD를 실제 공개 guard로 만든다.
    # 이 순수 router 단위 fixture를 실제 base/HTTP 통합 성공 근거로 사용하지 않는다.
    row = _hold_result(101, "candidate", ocr_review_required=False)
    identity = row["analysis_result"]["identity"]
    state = GroundingState(post_id=101, candidate_title="", candidate_url="",
        source="serializer_candidate_inventory_preserved", official_title_exists=False,
        row_discusses_work_as_work=False, title_resolution_state="unresolved_matchable",
        work_resolution="unresolved", discussion_type="review", candidate_inventory_count=1,
        scope=ScopeState(scope_kind="unknown", confidence="low",
            conflict_reason_codes=("serializer_candidate_inventory_hold", "candidate_inventory_unselected")))
    evidence = EvidenceRecord(kind="candidate_preservation", candidate_title="합성 달별갤 작품",
        source_path_or_snippet="합성 달별갤 작품", reason_code="candidate_inventory_preserved_without_selection")
    apply_publish_contract(identity, evaluate_publish_contract(state, [evidence]))
    identity["consistency_flags"] = ["direct_image_explicit_title_rescued", "direct_image_work_surface_lock"]
    identity["title_candidates"][0]["source_tier"] = "llm_only"
    return row


def _build(row, *, version=None):
    commit = _commit(row)
    receipt = router.build_semantic_review_router_receipt(row, commit,
        attempt_run_id=commit.attempt_run_id,
        **({"rule_version": version} if version is not None else {}))
    return commit, receipt


def _reseal(receipt):
    value = deepcopy(receipt)
    value["source_view_sha256"] = _sha(value["source_view"])
    value["router_decision_sha256"] = _sha(router._router_decision_material(value))
    value["receipt_sha256"] = _sha({key: item for key, item in value.items() if key != "receipt_sha256"})
    return value


def test_final_catalog_without_legacy_flag_routes_review_and_preserves_publication():
    row = _direct_hold()
    original = deepcopy(row)
    commit, receipt = _build(row)
    assert commit.outcome == "HOLD"
    assert receipt["rule_version"] == "strict_evidence_v2"
    assert receipt["state"] == router.REVIEW_REQUIRED
    assert receipt["trigger_codes"] == ["DIRECT_OCR_HOLD_CANDIDATE"]
    summary = receipt["source_view"]["direct_ocr_evidence"]
    proposals = extract_direct_ocr_review_proposals(row)
    assert len(proposals) == summary["proposal_count"] == 1
    assert summary["source_payload_sha256"] == [proposals[0].source_payload_sha256]
    assert summary["catalog_sha256"] == _sha(row["analysis_result"]["identity"]["image_evidence_catalog"])
    assert "합성 달별갤 작품" not in json.dumps(receipt, ensure_ascii=False)
    assert row == original
    assert router.validate_semantic_review_router_receipt(receipt, result=row,
        expected_publication_receipt=commit) == receipt
    assert router.validate_semantic_review_router_receipt(receipt) == receipt
    row["run_meta"]["semantic_review_router_receipt"] = receipt
    after = _commit(row)
    assert (after.decision_id, after.public_projection_sha256, after.stable_result_sha256) == (
        commit.decision_id, commit.public_projection_sha256, commit.stable_result_sha256)
    assert after.result_sha256 != commit.result_sha256
    assert router.validate_semantic_review_router_receipt(receipt, result=row,
        expected_publication_receipt=commit) == receipt
    # 실제 main처럼 router 첨부 후 현재 저장행의 receipt를 다시 계산해 전달한다.
    recovery = build_semantic_recovery_plan_receipt(row, after, attempt_run_id=after.attempt_run_id)
    assert recovery["plan"]["state"] == "HOLD"
    assert recovery["plan"]["raw_ocr_evidence_count"] == 1


@pytest.mark.parametrize("field,value", [
    ("suppressed_explicit_work_title", "합성 달별갤 작품"),
    ("background_listing_only", True), ("promotion_eligible", False),
    ("evidence_type", "inference"), ("title_role", "background"),
])
def test_ineligible_catalog_does_not_gain_review_from_rescued_flag(field, value):
    row = _direct_hold()
    row["analysis_result"]["identity"]["image_evidence_catalog"][0][field] = value
    commit, receipt = _build(row)
    assert not extract_direct_ocr_review_proposals(row)
    assert receipt["source_view"]["direct_ocr_evidence"]["proposal_count"] == 0
    assert receipt["state"] == router.NO_REVIEW
    router.validate_semantic_review_router_receipt(receipt, result=row, expected_publication_receipt=commit)


def test_multiple_titles_require_review_but_do_not_become_one_executable_proposal():
    row = _direct_hold()
    catalog = row["analysis_result"]["identity"]["image_evidence_catalog"]
    catalog.append({**deepcopy(catalog[0]), "eid": "IMG002", "explicit_work_title": "다른 합성 작품",
                    "ocr_text": "다른 합성 작품"})
    commit, receipt = _build(row)
    assert receipt["state"] == router.REVIEW_REQUIRED
    assert receipt["trigger_codes"] == ["MULTIPLE_DIRECT_OCR_HOLD_CANDIDATES"]
    assert receipt["source_view"]["direct_ocr_evidence"]["proposal_count"] == 2
    assert len(extract_direct_ocr_review_proposals(row)) == 2
    assert receipt["public_apply"] is False and commit.outcome == "HOLD"


def test_published_title_does_not_get_direct_ocr_hold_trigger():
    from tests.test_publication_decision_commit import _valid_result
    row = _valid_result(post_id=101)
    identity = row["analysis_result"]["identity"]
    identity["image_evidence_catalog"] = _direct_hold()["analysis_result"]["identity"]["image_evidence_catalog"]
    row.setdefault("comments", [])
    row["image_count"] = 1
    identity.setdefault("consistency_flags", [])
    identity.setdefault("output_consistency_lint", [])
    commit, receipt = _build(row)
    assert commit.outcome == "PUBLISH"
    assert receipt["source_view"]["direct_ocr_evidence"]["proposal_count"] == 0
    assert not any("DIRECT_OCR" in code for code in receipt["trigger_codes"])
    router.validate_semantic_review_router_receipt(receipt, result=row, expected_publication_receipt=commit)


@pytest.mark.parametrize("kind,state", [("review", router.REVIEW_REQUIRED), ("no_review", router.NO_REVIEW)])
def test_v1_schema_hash_source_route_and_result_revalidation_are_preserved(kind, state):
    row = _result(kind=kind)
    commit, receipt = _build(row, version="strict_evidence_v1")
    assert receipt["schema_version"] == "semantic_review_router_receipt_v1"
    assert receipt["rule_version"] == "strict_evidence_v1" and receipt["state"] == state
    assert "direct_ocr_evidence" not in receipt["source_view"]
    assert set(receipt["source_view"]) == router._COMPLETE_SOURCE_VIEW_FIELDS
    assert receipt["source_view_sha256"] == _sha(receipt["source_view"])
    assert receipt["router_decision_sha256"] == _sha(router._router_decision_material(receipt))
    assert receipt["receipt_sha256"] == _sha({k: v for k, v in receipt.items() if k != "receipt_sha256"})
    assert router.validate_semantic_review_router_receipt(receipt) == receipt
    assert router.validate_semantic_review_router_receipt(receipt, result=row,
        expected_publication_receipt=commit) == receipt
    changed = deepcopy(row)
    changed["comments"].append("다른 원문 댓글")
    with pytest.raises(router.SemanticReviewRouterError, match="source_view does not match result"):
        router.validate_semantic_review_router_receipt(receipt, result=changed, expected_publication_receipt=commit)


def test_v1_receipt_is_not_reinterpreted_using_v2_catalog():
    row = _direct_hold()
    commit, receipt = _build(row, version="strict_evidence_v1")
    assert receipt["state"] == router.NO_REVIEW
    assert router.validate_semantic_review_router_receipt(receipt, result=row,
        expected_publication_receipt=commit) == receipt
    _, current = _build(row)
    assert current["state"] == router.REVIEW_REQUIRED
    assert receipt["stable_result_sha256"] == current["stable_result_sha256"]
    for version in ("strict_evidence_v1", "strict_evidence_v2"):
        wrong = deepcopy(current if version.endswith("v1") else receipt)
        wrong["rule_version"] = version
        wrong = _reseal(wrong)
        with pytest.raises(router.SemanticReviewRouterError, match="source_view"):
            router.validate_semantic_review_router_receipt(wrong)


def test_changed_catalog_and_fully_resealed_receipt_cannot_keep_old_wal_binding():
    row = _direct_hold()
    commit, receipt = _build(row)
    changed = deepcopy(row)
    changed["analysis_result"]["identity"]["image_evidence_catalog"][0]["ocr_text"] += " 변조"
    with pytest.raises(router.SemanticReviewRouterError, match="source_view does not match result"):
        router.validate_semantic_review_router_receipt(receipt, result=changed, expected_publication_receipt=commit)
    forged = router.build_semantic_review_router_receipt(changed, commit, attempt_run_id=commit.attempt_run_id)
    assert forged["source_view_sha256"] != receipt["source_view_sha256"]
    with pytest.raises(router.SemanticReviewRouterError, match="v2 result publication binding mismatch"):
        router.validate_semantic_review_router_receipt(forged, result=changed, expected_publication_receipt=commit)


@pytest.mark.parametrize("change,expected_error", [
    ("count_bool", "direct OCR proposal count is invalid"),
    ("count_float", "direct OCR proposal count is invalid"),
    ("wrong_pin", "source_view does not match result"),
    ("extra_field", "direct OCR evidence fields mismatch"),
    ("empty_pin_list", "direct OCR source pins are invalid"),
    ("image_count_bool", "source_view image_count is invalid"),
    ("publish_allowed_int", "source_view publish_allowed is invalid"),
], ids=["count_bool", "count_float", "wrong_pin", "extra_field", "empty_pin_list",
        "image_count_bool", "publish_allowed_int"])
def test_resealed_summary_is_revalidated_against_current_result(change, expected_error):
    row = _direct_hold()
    commit, receipt = _build(row)
    forged = deepcopy(receipt)
    evidence = forged["source_view"]["direct_ocr_evidence"]
    if change == "count_bool": evidence["proposal_count"] = True
    elif change == "count_float": evidence["proposal_count"] = 1.0
    elif change == "wrong_pin": evidence["catalog_sha256"] = "0" * 64
    elif change == "extra_field": evidence["title"] = "주입 제목"
    elif change == "image_count_bool": forged["source_view"]["image_count"] = True
    elif change == "publish_allowed_int": forged["source_view"]["publish_allowed"] = 0
    else: evidence["source_payload_sha256"] = []
    sealed = _reseal(forged)
    with pytest.raises(router.SemanticReviewRouterError, match=expected_error):
        router.validate_semantic_review_router_receipt(sealed, result=row,
            expected_publication_receipt=commit)
    if change != "wrong_pin":
        with pytest.raises(router.SemanticReviewRouterError, match=expected_error):
            router.validate_semantic_review_router_receipt(sealed)


@pytest.mark.parametrize("catalog", [{}, [None], [{}] * 129])
def test_invalid_or_oversized_catalog_is_unknown(catalog):
    row = _direct_hold()
    row["analysis_result"]["identity"]["image_evidence_catalog"] = catalog
    commit, receipt = _build(row)
    assert receipt["state"] == router.UNKNOWN
    assert receipt["unknown_reason_codes"] == ["INVALID_DIRECT_OCR_EVIDENCE"]
    router.validate_semantic_review_router_receipt(receipt, result=row, expected_publication_receipt=commit)


def _new_ref(kwargs, role, value, directory, *, raw=False):
    payload = value if raw else json_bytes(value)
    path = directory / (role + ".json")
    with path.open("xb") as stream:
        stream.write(payload)
    kwargs["source_bytes"][role] = payload
    kwargs["source_refs"][role] = {"path": str(path), "bytes": len(payload),
                                  "sha256": hashlib.sha256(payload).hexdigest()}


@pytest.mark.parametrize("version", ["strict_evidence_v1", "strict_evidence_v2"])
def test_provider_plan_compatibility_and_no_existing_source_overwrite(tmp_path, version):
    from tests.recovery_provider_fixtures import build_recovery_provider_fixture
    from src.llm_batch.measurement.recovery_provider_contract import (
        build_recovery_provider_plan, bind_recovery_provider_plan,
    )
    bundle = build_recovery_provider_fixture(tmp_path / "original")
    old = {Path(ref["path"]): Path(ref["path"]).read_bytes() for ref in bundle["source_refs"].values()}
    kwargs = deepcopy(bundle["build_kwargs"])
    results = deepcopy(bundle["results"])
    row = results[0]
    if version == "strict_evidence_v2":
        row["analysis_result"]["identity"] = deepcopy(_direct_hold()["analysis_result"]["identity"])
    receipt = compute_publication_decision_commit(row,
        publication_scope_id=bundle["receipt"].publication_scope_id,
        attempt_run_id=bundle["receipt"].attempt_run_id, input_index=1, post_id=101)
    review = router.build_semantic_review_router_receipt(row, receipt,
        attempt_run_id=receipt.attempt_run_id, rule_version=version)
    assert review["state"] == router.REVIEW_REQUIRED
    recovery = build_semantic_recovery_plan_receipt(row, receipt, attempt_run_id=receipt.attempt_run_id)
    proposal, = extract_direct_ocr_review_proposals(row)
    event = _create_event(receipt=receipt, proposal=proposal, raw_capability="fixture-audit-token-only",
        hmac_key=bundle["hmac_key"], sequence=1, prev_event_sha256="GENESIS")
    kwargs.update(publication_decision_id=receipt.decision_id, activation_event_sha256=event.event_sha256)
    kwargs["source_binding"]["relation_role"] = proposal.relation_role
    kwargs["payload"]["purpose"] = recovery["plan"]["query_plan"]["purposes"][0]
    rewritten = tmp_path / "new_refs"
    rewritten.mkdir()
    _new_ref(kwargs, "result", results, rewritten)
    records = [json.loads(line) for line in kwargs["source_bytes"]["publication_wal"].splitlines()]
    records[0] = {"schema_version": PUBLICATION_COMMIT_EVENT_SCHEMA, "receipt": receipt.to_dict(), "result": row}
    _new_ref(kwargs, "publication_wal", b"".join(json_bytes(record) + b"\n" for record in records), rewritten, raw=True)
    _new_ref(kwargs, "router", review, rewritten)
    _new_ref(kwargs, "recovery_plan", recovery, rewritten)
    _new_ref(kwargs, "activation_journal", json_bytes(event.to_dict()) + b"\n", rewritten, raw=True)
    # manifest의 output_file도 새 immutable result 경로를 가리킨다.
    manifest = deepcopy(bundle["manifest"])
    manifest["output_file"] = kwargs["source_refs"]["result"]["path"]
    _new_ref(kwargs, "manifest", manifest, rewritten)
    plan = build_recovery_provider_plan(**kwargs)
    bound = bind_recovery_provider_plan(plan, hmac_key=bundle["hmac_key"])
    assert bound.verify_protected_sources() is True
    assert plan["guard_status"] == "GUARD_NOT_EVALUATED" and plan["public_apply"] is False
    assert all(path.read_bytes() == raw for path, raw in old.items())
    assert not bound.output_dir.exists()
