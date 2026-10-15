#!/usr/bin/env python3
"""Build the deterministic, example-only actual-P0 schema-contract fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from llm_batch.grounding.p0_actual_registry_contract import (  # noqa: E402
    ANNOTATION_EVENT_SCHEMA,
    B_SENSE_SCHEMA,
    EXAMPLE_ORIGIN,
    OPERATIONAL_EFFECT,
    SOURCE_CLAIM_SCHEMA,
    SOURCE_SNAPSHOT_SCHEMA,
    _b_receipts,
    _annotation_subject_sha,
    _capture_receipt,
    _claim_set_sha,
    _claim_receipt,
    _decision_payload_sha,
    _event_sha,
    _record_sha,
    build_example_manifest,
    canonical_sha256,
    jsonl_bytes,
    validate_example_directory,
    with_row_hash,
)


DEFAULT_DIRECTORY = (
    REPO_ROOT / "tests" / "fixtures" / "p0_actual_contract_example_v1"
)

SNAPSHOT_BASENAME = "p0_source_snapshot_registry_example_v1.jsonl"
CLAIM_BASENAME = "p0_source_claim_example_v1.jsonl"
B_CONTEXT_BASENAME = "p0_b_sense_contract_example_v1.jsonl"
EVENT_BASENAME = "p0_annotation_events_example_v1.jsonl"
MANIFEST_BASENAME = "p0_actual_contract_example_manifest_v1.json"

PAYLOADS = (
    (
        "p0_payload_official_structured_example_01_v1.txt",
        "작품 《별빛 기록》은 커뮤니티에서 '별기'로 불린다. '회귀각'은 다시 시작할 기회가 보인다는 뜻이다.\n",
    ),
    (
        "p0_payload_community_structured_example_02_v1.txt",
        "작품 《별빛 기록》은 커뮤니티에서 '별기'로 불린다. '회귀각'은 다시 시작할 기회가 보인다는 뜻이다.\n",
    ),
    (
        "p0_payload_media_ocr_example_03_v1.txt",
        "여기서 '달잠'은 밤새 읽다가 해 뜰 무렵 잠드는 행동을 가리킨다.\n",
    ),
    (
        "p0_payload_community_structured_example_04_v1.txt",
        "'푸른문'은 이 문장에서는 단순한 장소 묘사일 뿐 은어가 아니다.\n",
    ),
    (
        "p0_payload_generic_fallback_example_05_v1.txt",
        "해석 후보가 불완전한 일반 게시물: '잔빛'의 뜻은 확인되지 않았다.\n",
    ),
)


def _sha_text(label: str) -> str:
    return canonical_sha256(label)


def _source_snapshot(
    *,
    index: int,
    payload_name: str,
    payload_text: str,
    source_profile: str,
    platform: str,
    community_scope: str,
    parent: Mapping[str, Any] | None = None,
    derivation_kind: str = "ORIGINAL",
) -> dict[str, Any]:
    registry_id = f"EXAMPLE:REGISTRY:{index:02d}"
    source_id = (
        str(parent["source_id"])
        if parent is not None and derivation_kind == "TEMPORAL_REVISION"
        else f"EXAMPLE:SOURCE:{index:02d}"
    )
    snapshot_id = f"EXAMPLE:SNAPSHOT:{index:02d}"
    payload_bytes = payload_text.encode("utf-8")
    parser_route = (
        "generic_queue" if source_profile == "GENERIC_FALLBACK" else "structured_profile"
    )
    row: dict[str, Any] = {
        "schema_version": SOURCE_SNAPSHOT_SCHEMA,
        "record_origin": EXAMPLE_ORIGIN,
        "registry_record_id": registry_id,
        "source_id": source_id,
        "snapshot_id": snapshot_id,
        "snapshot_regime": "FIXED_CONTRACT_EXAMPLE_V1",
        "platform": platform,
        "community_scope": community_scope,
        "canonical_url": f"https://source-{index:02d}.example/posts/{index:02d}",
        "locator": f"example-post-{index:02d}",
        "author_pseudonym_sha256": _sha_text(f"example-author-{index:02d}"),
        "published_at": f"2026-01-{index:02d}T00:00:00Z",
        "published_at_unknown_reason": None,
        "modified_at": f"2026-01-{index:02d}T01:00:00Z",
        "modified_at_unknown_reason": None,
        "collected_at": f"2026-01-{index:02d}T02:00:00Z",
        "http_status": 200,
        "content_type": "text/plain; charset=utf-8",
        "response_bytes": len(payload_bytes),
        "response_sha256": hashlib.sha256(payload_bytes).hexdigest(),
        "normalized_text_sha256": hashlib.sha256(payload_bytes).hexdigest(),
        "normalization_version": "utf8_identity_v1",
        "payload_ref": payload_name,
        "capture_profile": source_profile.lower(),
        "capture_version": "example_capture_v1",
        "capture_run_manifest_sha256": _sha_text(
            f"example-capture-manifest-{index:02d}"
        ),
        "capture_receipt_sha256": "",
        "lineage_root_id": (
            registry_id if parent is None else parent["lineage_root_id"]
        ),
        "parent_registry_record_id": (
            None if parent is None else parent["registry_record_id"]
        ),
        "derivation_kind": derivation_kind,
        "independence_group_id": (
            f"EXAMPLE:INDEPENDENCE:{index:02d}"
            if parent is None
            else parent["independence_group_id"]
        ),
        "independence_status": (
            "ELIGIBLE_ROOT" if parent is None else "COLLAPSED_DERIVATIVE"
        ),
        "lineage_review_status": "VERIFIED",
        "lineage_reason_codes": [
            "lineage_original_verified"
            if parent is None
            else "lineage_temporal_revision_collapsed"
            if derivation_kind == "TEMPORAL_REVISION"
            else "lineage_derivative_verified"
        ],
        "lineage_evidence_sha256": _sha_text(f"example-lineage-{index:02d}"),
        "source_profile": source_profile,
        "parser_route": parser_route,
        "collection_allowed": True,
        "content_retention_allowed": True,
        "derived_index_allowed": True,
        "quotation_allowed": True,
        "publication_evidence_eligible": parent is None,
        "rights_basis": "FIXED_EXAMPLE_POLICY_ONLY",
        "rights_policy_sha256": _sha_text("example-rights-policy-v1"),
        "rights_assessment_status": "ASSESSED",
        "rights_reason_codes": ["rights_policy_assessed"],
        "rights_reviewed_at": "2026-01-10T00:00:00Z",
        "retention_class": "CONTROLLED_RAW",
        "takedown_status": "ACTIVE",
        "payload_deletion_receipt_sha256": None,
        "derived_index_deletion_receipt_sha256": None,
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
        "registry_record_sha256": "",
    }
    row["capture_receipt_sha256"] = _capture_receipt(row)
    row["registry_record_sha256"] = _record_sha(row, "registry_record_sha256")
    return with_row_hash(row)


def _source_claim(
    *,
    index: int,
    snapshot: Mapping[str, Any],
    payload_text: str,
    surface_text: str,
    track: str,
    claim_kind: str,
    claim_direction: str,
    target_work_id: str | None = None,
    target_sense_id: str | None = None,
    definition: str | None = None,
    parse_disposition: str = "PARSED",
    repair_mode: str = "NONE",
) -> dict[str, Any]:
    surface_start = payload_text.index(surface_text)
    if definition is None:
        span_start = surface_start
        span_end = surface_start + len(surface_text)
    else:
        definition_start = payload_text.index(definition)
        span_start = min(surface_start, definition_start)
        span_end = max(
            surface_start + len(surface_text), definition_start + len(definition)
        )
    span_text = payload_text[span_start:span_end]
    row: dict[str, Any] = {
        "schema_version": SOURCE_CLAIM_SCHEMA,
        "record_origin": EXAMPLE_ORIGIN,
        "claim_id": f"EXAMPLE:CLAIM:{index:02d}",
        "registry_record_id": snapshot["registry_record_id"],
        "registry_record_sha256": snapshot["registry_record_sha256"],
        "snapshot_id": snapshot["snapshot_id"],
        "track": track,
        "span_start": span_start,
        "span_end": span_end,
        "span_text": span_text,
        "span_sha256": canonical_sha256(span_text),
        "surface_text": surface_text,
        "normalized_surface": surface_text,
        "claim_direction": claim_direction,
        "claim_kind": claim_kind,
        "target_work_id": target_work_id,
        "target_sense_id": target_sense_id,
        "definition": definition,
        "parse_disposition": parse_disposition,
        "parser_profile": str(snapshot["source_profile"]).lower(),
        "parser_version": "example_parser_v1",
        "parser_run_id": "EXAMPLE:PARSER:RUN:01",
        "parser_manifest_sha256": _sha_text("example-parser-manifest-v1"),
        "repair_mode": repair_mode,
        "repair_output_text": None,
        "repair_source_span_sha256": None,
        "claim_evidence_receipt_sha256": "",
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    row["claim_evidence_receipt_sha256"] = _claim_receipt(
        row, str(snapshot["response_sha256"])
    )
    return with_row_hash(row)


def _b_context(
    *,
    index: int,
    claim: Mapping[str, Any],
    content_text: str,
    surface_text: str,
    candidate_sense_ids: list[str],
    candidate_registry_status: str,
    truth_kind: str,
    truth_sense_id: str | None,
    new_sense_proposal_id: str | None,
    novelty_review_receipt_sha256: str | None,
    truth_reason_codes: list[str],
    annotation_status: str,
    annotation_reason_codes: list[str],
    inference_decision: str,
    inference_sense_id: str | None,
    inference_reason_codes: list[str],
    publication_action: str,
    public_sense_id: str | None,
    public_definition: str | None,
    publication_reason_codes: list[str],
    term_type: str,
    definition: str | None,
    discourse_function: str,
    temporal_status: str,
    sensitivity_class: str,
    sensitive_review_status: str,
    platform_scope: str,
    community_scope: str,
) -> dict[str, Any]:
    context_id = f"EXAMPLE:B_CONTEXT:{index:02d}"
    claim_ids = [str(claim["claim_id"])]
    row: dict[str, Any] = {
        "schema_version": B_SENSE_SCHEMA,
        "record_origin": EXAMPLE_ORIGIN,
        "context_id": context_id,
        "post_id": f"EXAMPLE:POST:{index:02d}",
        "content_text": content_text,
        "content_fingerprint": canonical_sha256(content_text),
        "context_observed_at": f"2026-02-{index:02d}T12:00:00Z",
        "surface_text": surface_text,
        "surface_start": content_text.index(surface_text),
        "surface_end": content_text.index(surface_text) + len(surface_text),
        "surface_sha256": canonical_sha256(surface_text),
        "normalized_surface": surface_text,
        "community_scope": community_scope,
        "platform_scope": platform_scope,
        "candidate_sense_ids": candidate_sense_ids,
        "candidate_set_fingerprint": canonical_sha256(candidate_sense_ids),
        "candidate_registry_snapshot_sha256": _sha_text(
            f"example-candidate-registry-{index:02d}"
        ),
        "candidate_registry_status": candidate_registry_status,
        "annotation_subject_sha256": "",
        "truth_source_claim_ids": claim_ids,
        "truth_claim_set_sha256": _claim_set_sha([claim]),
        "truth_evidence_cutoff": f"2026-01-{10 + index:02d}T00:00:00Z",
        "truth_evidence_receipt_sha256": None,
        "inference_source_claim_ids": claim_ids,
        "inference_claim_set_sha256": _claim_set_sha([claim]),
        "inference_evidence_cutoff": f"2026-01-{9 + index:02d}T00:00:00Z",
        "inference_input_receipt_sha256": "",
        "truth_kind": truth_kind,
        "truth_sense_id": truth_sense_id,
        "new_sense_proposal_id": new_sense_proposal_id,
        "novelty_review_receipt_sha256": novelty_review_receipt_sha256,
        "truth_reason_codes": truth_reason_codes,
        "annotation_status": annotation_status,
        "annotation_reason_codes": annotation_reason_codes,
        "annotation_event_id": f"EXAMPLE:ANNOTATION_EVENT:{index:02d}",
        "inference_decision": inference_decision,
        "inference_sense_id": inference_sense_id,
        "inference_reason_codes": inference_reason_codes,
        "publication_action": publication_action,
        "public_sense_id": public_sense_id,
        "public_definition": public_definition,
        "publication_reason_codes": publication_reason_codes,
        "term_type": term_type,
        "definition": definition,
        "discourse_function": discourse_function,
        "valid_from": None,
        "valid_to": None,
        "temporal_status": temporal_status,
        "sensitivity_class": sensitivity_class,
        "sensitive_review_status": sensitive_review_status,
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    truth_receipt, inference_receipt = _b_receipts(row)
    row["truth_evidence_receipt_sha256"] = truth_receipt
    row["inference_input_receipt_sha256"] = inference_receipt
    row["annotation_subject_sha256"] = _annotation_subject_sha(row)
    return with_row_hash(row)


def _annotation_event(
    *, index: int, context: Mapping[str, Any]
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "schema_version": ANNOTATION_EVENT_SCHEMA,
        "record_origin": EXAMPLE_ORIGIN,
        "journal_id": f"EXAMPLE:ANNOTATION_JOURNAL:{index:02d}",
        "journal_sequence": 1,
        "event_id": context["annotation_event_id"],
        "event_sha256": "",
        "previous_event_id": None,
        "previous_event_sha256": None,
        "target_record_type": "B_SENSE_CONTEXT",
        "target_id": context["context_id"],
        "target_subject_sha256": context["annotation_subject_sha256"],
        "reviewer_pseudonym_sha256": _sha_text(f"example-reviewer-{index:02d}"),
        "reviewer_principal_sha256": _sha_text(f"example-principal-{index:02d}"),
        "reviewer_role": "HUMAN_CURATOR",
        "independent_review": True,
        "reviewer_assignment_receipt_sha256": _sha_text(
            f"example-reviewer-assignment-{index:02d}"
        ),
        "guideline_path": "docs/example-only/p0_annotation_guideline_v1.md",
        "guideline_version": "example_guideline_v1",
        "guideline_sha256": _sha_text("example-annotation-guideline-v1"),
        "event_kind": "PRIMARY_REVIEW",
        "supersedes_event_ids": [],
        "occurred_at": f"2026-02-{index:02d}T13:00:00Z",
        "evidence_cutoff": context["truth_evidence_cutoff"],
        "evidence_claim_ids": context["truth_source_claim_ids"],
        "annotation_status": context["annotation_status"],
        "decision_kind": context["truth_kind"],
        "decision_sense_id": context["truth_sense_id"],
        "decision_payload_sha256": _decision_payload_sha(context),
        "reason_codes": (
            context["truth_reason_codes"]
            if context["annotation_status"] == "JUDGED"
            else context["annotation_reason_codes"]
        ),
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    row["event_sha256"] = _event_sha(row)
    return with_row_hash(row)


def _fixture_rows() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    root = _source_snapshot(
        index=1,
        payload_name=PAYLOADS[0][0],
        payload_text=PAYLOADS[0][1],
        source_profile="OFFICIAL_STRUCTURED",
        platform="official-example",
        community_scope="work-catalog",
    )
    mirror = _source_snapshot(
        index=2,
        payload_name=PAYLOADS[1][0],
        payload_text=PAYLOADS[1][1],
        source_profile="COMMUNITY_STRUCTURED",
        platform="community-example",
        community_scope="sense-board",
        parent=root,
        derivation_kind="MIRROR",
    )
    repost = _source_snapshot(
        index=3,
        payload_name=PAYLOADS[2][0],
        payload_text=PAYLOADS[2][1],
        source_profile="MEDIA_OCR",
        platform="media-example",
        community_scope="image-posts",
        parent=root,
        derivation_kind="REPOST",
    )
    temporal_revision = _source_snapshot(
        index=4,
        payload_name=PAYLOADS[3][0],
        payload_text=PAYLOADS[3][1],
        source_profile="COMMUNITY_STRUCTURED",
        platform="community-example",
        community_scope="sense-board",
        parent=root,
        derivation_kind="TEMPORAL_REVISION",
    )
    generic_root = _source_snapshot(
        index=5,
        payload_name=PAYLOADS[4][0],
        payload_text=PAYLOADS[4][1],
        source_profile="GENERIC_FALLBACK",
        platform="generic-example",
        community_scope="unclassified",
    )
    snapshots = [root, mirror, repost, temporal_revision, generic_root]
    claims = [
        _source_claim(
            index=1,
            snapshot=snapshots[0],
            payload_text=PAYLOADS[0][1],
            surface_text="별기",
            track="A",
            claim_kind="WORK_ALIAS",
            claim_direction="SURFACE_TO_WORK",
            target_work_id="EXAMPLE:WORK:STARLIGHT_RECORD",
        ),
        _source_claim(
            index=2,
            snapshot=snapshots[0],
            payload_text=PAYLOADS[0][1],
            surface_text="회귀각",
            track="B",
            claim_kind="COMMUNITY_SENSE",
            claim_direction="SURFACE_TO_SENSE",
            target_sense_id="EXAMPLE:SENSE:RETRY_OPPORTUNITY",
            definition="다시 시작할 기회가 보인다는 뜻",
        ),
        _source_claim(
            index=3,
            snapshot=snapshots[2],
            payload_text=PAYLOADS[2][1],
            surface_text="달잠",
            track="B",
            claim_kind="NEW_SENSE_CANDIDATE",
            claim_direction="SURFACE_TO_SENSE",
            definition="밤새 읽다가 해 뜰 무렵 잠드는 행동",
        ),
        _source_claim(
            index=4,
            snapshot=snapshots[3],
            payload_text=PAYLOADS[3][1],
            surface_text="푸른문",
            track="B",
            claim_kind="NON_TERM_EVIDENCE",
            claim_direction="SURFACE_TO_SENSE",
        ),
        _source_claim(
            index=5,
            snapshot=snapshots[4],
            payload_text=PAYLOADS[4][1],
            surface_text="잔빛",
            track="B",
            claim_kind="UNKNOWN",
            claim_direction="UNKNOWN_DIRECTION",
            parse_disposition="GENERIC_PENDING",
            repair_mode="ABSTAIN",
        ),
    ]
    existing_definition = "다시 시작할 기회가 보인다는 뜻"
    contexts = [
        _b_context(
            index=1,
            claim=claims[1],
            content_text="이번 전개는 회귀각이 분명해서 다시 도전할 만하다.",
            surface_text="회귀각",
            candidate_sense_ids=["EXAMPLE:SENSE:RETRY_OPPORTUNITY"],
            candidate_registry_status="COMPLETE",
            truth_kind="SENSE_ID",
            truth_sense_id="EXAMPLE:SENSE:RETRY_OPPORTUNITY",
            new_sense_proposal_id=None,
            novelty_review_receipt_sha256=None,
            truth_reason_codes=["truth_existing_sense_confirmed"],
            annotation_status="JUDGED",
            annotation_reason_codes=["annotation_human_review_completed"],
            inference_decision="ASSERT_SENSE",
            inference_sense_id="EXAMPLE:SENSE:RETRY_OPPORTUNITY",
            inference_reason_codes=["inference_existing_sense_selected"],
            publication_action="PUBLISH",
            public_sense_id="EXAMPLE:SENSE:RETRY_OPPORTUNITY",
            public_definition=existing_definition,
            publication_reason_codes=[
                "publication_evidence_verified",
                "publication_existing_wal_no_write",
            ],
            term_type="COMMUNITY_JARGON",
            definition=existing_definition,
            discourse_function="STANCE",
            temporal_status="CURRENT",
            sensitivity_class="NONE",
            sensitive_review_status="NOT_REQUIRED",
            platform_scope=snapshots[0]["platform"],
            community_scope=snapshots[0]["community_scope"],
        ),
        _b_context(
            index=2,
            claim=claims[2],
            content_text="어제도 달잠을 자서 오전 내내 졸렸다.",
            surface_text="달잠",
            candidate_sense_ids=[],
            candidate_registry_status="COMPLETE",
            truth_kind="NEW_SENSE",
            truth_sense_id=None,
            new_sense_proposal_id="EXAMPLE:NEW_SENSE_PROPOSAL:01",
            novelty_review_receipt_sha256=_sha_text("example-novelty-review-01"),
            truth_reason_codes=["truth_new_sense_confirmed"],
            annotation_status="JUDGED",
            annotation_reason_codes=["annotation_human_review_completed"],
            inference_decision="ASSERT_NEW_SENSE",
            inference_sense_id=None,
            inference_reason_codes=["inference_new_sense_candidate"],
            publication_action="HOLD",
            public_sense_id=None,
            public_definition=None,
            publication_reason_codes=[
                "publication_existing_wal_no_write",
                "publication_new_sense_review_hold",
            ],
            term_type="COMMUNITY_JARGON",
            definition="밤새 읽다가 해 뜰 무렵 잠드는 행동",
            discourse_function="OTHER",
            temporal_status="CURRENT",
            sensitivity_class="NONE",
            sensitive_review_status="NOT_REQUIRED",
            platform_scope=snapshots[2]["platform"],
            community_scope=snapshots[2]["community_scope"],
        ),
        _b_context(
            index=3,
            claim=claims[3],
            content_text="푸른문 옆에 가방을 두었다는 장소 설명이다.",
            surface_text="푸른문",
            candidate_sense_ids=[],
            candidate_registry_status="COMPLETE",
            truth_kind="NON_TERM",
            truth_sense_id=None,
            new_sense_proposal_id=None,
            novelty_review_receipt_sha256=None,
            truth_reason_codes=["truth_non_term_confirmed"],
            annotation_status="JUDGED",
            annotation_reason_codes=["annotation_human_review_completed"],
            inference_decision="ASSERT_NON_TERM",
            inference_sense_id=None,
            inference_reason_codes=["inference_non_term_selected"],
            publication_action="REJECT",
            public_sense_id=None,
            public_definition=None,
            publication_reason_codes=[
                "publication_existing_wal_no_write",
                "publication_non_term_reject",
            ],
            term_type="NON_TERM",
            definition=None,
            discourse_function="OTHER",
            temporal_status="CURRENT",
            sensitivity_class="NONE",
            sensitive_review_status="NOT_REQUIRED",
            platform_scope=snapshots[3]["platform"],
            community_scope=snapshots[3]["community_scope"],
        ),
        _b_context(
            index=4,
            claim=claims[4],
            content_text="잔빛이 무슨 뜻인지는 접근 가능한 근거만으로 확인할 수 없다.",
            surface_text="잔빛",
            candidate_sense_ids=[],
            candidate_registry_status="UNAVAILABLE",
            truth_kind="UNRESOLVED",
            truth_sense_id=None,
            new_sense_proposal_id=None,
            novelty_review_receipt_sha256=None,
            truth_reason_codes=[],
            annotation_status="UNAVAILABLE",
            annotation_reason_codes=["evidence_unavailable"],
            inference_decision="ABSTAIN",
            inference_sense_id=None,
            inference_reason_codes=["retrieval_unavailable_requires_abstain"],
            publication_action="HOLD",
            public_sense_id=None,
            public_definition=None,
            publication_reason_codes=[
                "publication_abstain_hold",
                "publication_existing_wal_no_write",
                "publication_unavailable_hold",
            ],
            term_type="UNRESOLVED",
            definition=None,
            discourse_function="UNRESOLVED",
            temporal_status="UNKNOWN",
            sensitivity_class="NOT_ASSESSED",
            sensitive_review_status="NOT_ASSESSED",
            platform_scope=snapshots[4]["platform"],
            community_scope=snapshots[4]["community_scope"],
        ),
    ]
    events = [
        _annotation_event(index=index, context=context)
        for index, context in enumerate(contexts, start=1)
    ]
    return snapshots, claims, contexts, events


def _write_new_or_identical(path: Path, payload: bytes) -> None:
    if path.exists():
        if not path.is_file() or path.is_symlink() or path.read_bytes() != payload:
            raise ValueError(f"refusing to overwrite non-identical fixture: {path}")
        return
    path.write_bytes(payload)


def build(directory: Path) -> dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=True)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError(f"fixture directory must be a regular directory: {directory}")

    snapshots, claims, contexts, events = _fixture_rows()
    for payload_name, payload_text in PAYLOADS:
        _write_new_or_identical(directory / payload_name, payload_text.encode("utf-8"))

    snapshot_path = directory / SNAPSHOT_BASENAME
    claim_path = directory / CLAIM_BASENAME
    context_path = directory / B_CONTEXT_BASENAME
    event_path = directory / EVENT_BASENAME
    manifest_path = directory / MANIFEST_BASENAME
    _write_new_or_identical(snapshot_path, jsonl_bytes(snapshots))
    _write_new_or_identical(claim_path, jsonl_bytes(claims))
    _write_new_or_identical(context_path, jsonl_bytes(contexts))
    _write_new_or_identical(event_path, jsonl_bytes(events))

    manifest = build_example_manifest(
        snapshot_path=snapshot_path,
        claim_path=claim_path,
        b_context_path=context_path,
        event_path=event_path,
        counts={
            "source_snapshots": len(snapshots),
            "source_claims": len(claims),
            "b_sense_contexts": len(contexts),
            "annotation_events": len(events),
        },
    )
    manifest_payload = (
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    _write_new_or_identical(manifest_path, manifest_payload)

    receipt = validate_example_directory(directory)
    return {
        "directory": str(directory),
        "record_origin": EXAMPLE_ORIGIN,
        "example_source_snapshot_count": len(snapshots),
        "example_source_claim_count": len(claims),
        "example_b_sense_context_count": len(contexts),
        "example_annotation_event_count": len(events),
        "manifest_sha256": manifest["manifest_sha256"],
        "validator_gate_status": receipt["gate_status"],
        "validator_schema_check_status": receipt["schema_check_status"],
        "validator_actual_gate_status": receipt["actual_gate_status"],
        "validator_artifact_binding_verified": receipt["artifact_binding_verified"],
        "validator_payload_binding_verified": receipt["payload_binding_verified"],
        "p0_phase_exit": receipt["p0_phase_exit"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    args = parser.parse_args()
    result = build(args.directory.resolve())
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
