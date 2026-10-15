"""ACTUAL P0 Track-A 문맥 계약의 fail-close 회귀 테스트."""

from __future__ import annotations

from copy import deepcopy
import unittest

from src.llm_batch.grounding.p0_actual_a_context_contract import (
    A_ANNOTATION_EVENT_SCHEMA,
    A_CONTEXT_SCHEMA,
    P0ActualAContextContractError,
    annotation_event_sha256,
    annotation_subject_sha256,
    canonical_sha256,
    decision_payload_sha256,
    evidence_receipt_sha256,
    sampling_unit_sha256,
    source_claim_set_sha256,
    validate_actual_a_context_bundle,
    validate_example_a_context_bundle,
    with_row_hash,
)
from src.llm_batch.grounding.p0_actual_registry_contract import (
    ACTUAL_ORIGIN,
    EXAMPLE_ORIGIN,
    OPERATIONAL_EFFECT,
    SOURCE_CLAIM_SCHEMA,
    with_row_hash as with_registry_row_hash,
)


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
WORK_ID = "WORK:STARLIGHT_RECORD"


def _claim(origin: str = EXAMPLE_ORIGIN, *, track: str = "A") -> dict:
    """registry validator를 통과하는 최소 deterministic Track-A claim."""
    row = {
        "schema_version": SOURCE_CLAIM_SCHEMA,
        "record_origin": origin,
        "claim_id": f"{origin}:CLAIM:01",
        "registry_record_id": f"{origin}:REGISTRY:01",
        "registry_record_sha256": SHA_A,
        "snapshot_id": f"{origin}:SNAPSHOT:01",
        "track": track,
        "span_start": 0,
        "span_end": 2,
        "span_text": "별기",
        "span_sha256": canonical_sha256("별기"),
        "surface_text": "별기",
        "normalized_surface": "별기",
        "claim_direction": "SURFACE_TO_WORK" if track == "A" else "SURFACE_TO_SENSE",
        "claim_kind": "WORK_ALIAS" if track == "A" else "COMMUNITY_SENSE",
        "target_work_id": WORK_ID if track == "A" else None,
        "target_sense_id": None if track == "A" else "SENSE:01",
        "definition": None if track == "A" else "별기",
        "parse_disposition": "PARSED",
        "parser_profile": "official_structured",
        "parser_version": "test-parser-v1",
        "parser_run_id": f"{origin}:PARSER:01",
        "parser_manifest_sha256": SHA_B,
        "repair_mode": "NONE",
        "repair_output_text": None,
        "repair_source_span_sha256": None,
        "claim_evidence_receipt_sha256": SHA_C,
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    return with_registry_row_hash(row)


def _decision(kind: str) -> dict:
    if kind == "WORK_ID":
        return {
            "annotation_status": "JUDGED",
            "truth_kind": kind,
            "truth_work_id": WORK_ID,
            "truth_nil_reason": None,
            "truth_reason_codes": ["truth_explicit_alias_relation"],
            "annotation_reason_codes": ["annotation_human_review_completed"],
        }
    if kind == "NIL":
        return {
            "annotation_status": "JUDGED",
            "truth_kind": kind,
            "truth_work_id": None,
            "truth_nil_reason": "NIL_NO_VALID_CANDIDATE",
            "truth_reason_codes": [
                "truth_nil_no_canonical_target_after_complete_enumeration"
            ],
            "annotation_reason_codes": ["annotation_human_review_completed"],
        }
    return {
        "annotation_status": "UNAVAILABLE",
        "truth_kind": "UNRESOLVED",
        "truth_work_id": None,
        "truth_nil_reason": None,
        "truth_reason_codes": [],
        "annotation_reason_codes": ["evidence_unavailable"],
    }


def _bundle(
    origin: str = EXAMPLE_ORIGIN,
    *,
    kind: str = "WORK_ID",
) -> tuple[list[dict], list[dict], list[dict]]:
    claim = _claim(origin)
    decision = _decision(kind)
    content = "별기는 별빛기록의 공식 약어다."
    start = content.index("별기")
    candidates = [WORK_ID] if kind == "WORK_ID" else []
    candidate_status = "UNAVAILABLE" if kind == "UNRESOLVED" else "COMPLETE"
    context = {
        "schema_version": A_CONTEXT_SCHEMA,
        "record_origin": origin,
        "context_id": f"{origin}:A:CONTEXT:01",
        "sampling_frame_sha256": SHA_A,
        "sampling_unit_id": f"{origin}:A:SAMPLE:01",
        "sampling_unit_sha256": "",
        "post_id": f"{origin}:POST:01",
        "content_text": content,
        "content_fingerprint": canonical_sha256(content),
        "context_observed_at": "2026-01-02T00:00:00Z",
        "surface_text": "별기",
        "surface_start": start,
        "surface_end": start + 2,
        "surface_sha256": canonical_sha256("별기"),
        "normalized_surface": "별기",
        "community_scope": "novel-community",
        "platform_scope": "test-platform",
        "candidate_work_ids": candidates,
        "candidate_set_fingerprint": canonical_sha256(candidates),
        "candidate_registry_snapshot_sha256": SHA_B,
        "candidate_registry_status": candidate_status,
        "source_claim_ids": [claim["claim_id"]],
        "source_claim_set_sha256": source_claim_set_sha256([claim]),
        "evidence_cutoff": "2026-01-01T00:00:00Z",
        "evidence_receipt_sha256": "",
        "annotation_subject_sha256": "",
        **decision,
        "latest_annotation_event_id": f"{origin}:A:EVENT:01",
        "latest_annotation_event_sha256": SHA_D,
        "reviewer_principal_sha256": SHA_A,
        "reviewer_assignment_receipt_sha256": SHA_B,
        "guideline_path": "docs/devs/P0_ACTUAL_A_GUIDELINE.md",
        "guideline_version": "p0-a-v1",
        "guideline_sha256": SHA_C,
        "action_applied": False,
        "public_apply": False,
        "central_slang_db_write": False,
        "publication_wal_write": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    context["sampling_unit_sha256"] = sampling_unit_sha256(context)
    context["evidence_receipt_sha256"] = evidence_receipt_sha256(context)
    context["annotation_subject_sha256"] = annotation_subject_sha256(context)
    event = {
        "schema_version": A_ANNOTATION_EVENT_SCHEMA,
        "record_origin": origin,
        "journal_id": f"{origin}:A:JOURNAL:01",
        "journal_sequence": 1,
        "event_id": context["latest_annotation_event_id"],
        "event_sha256": "",
        "previous_event_id": None,
        "previous_event_sha256": None,
        "target_record_type": "A_CONTEXT",
        "target_id": context["context_id"],
        "target_subject_sha256": context["annotation_subject_sha256"],
        "reviewer_pseudonym_sha256": SHA_D,
        "reviewer_principal_sha256": context["reviewer_principal_sha256"],
        "reviewer_role": "HUMAN_CURATOR",
        "independent_review": True,
        "reviewer_assignment_receipt_sha256": context[
            "reviewer_assignment_receipt_sha256"
        ],
        "guideline_path": context["guideline_path"],
        "guideline_version": context["guideline_version"],
        "guideline_sha256": context["guideline_sha256"],
        "event_kind": "PRIMARY_REVIEW",
        "supersedes_event_ids": [],
        "occurred_at": "2026-01-03T00:00:00Z",
        "evidence_cutoff": context["evidence_cutoff"],
        "evidence_claim_ids": context["source_claim_ids"],
        "annotation_status": context["annotation_status"],
        "decision_kind": context["truth_kind"],
        "decision_work_id": context["truth_work_id"],
        "decision_nil_reason": context["truth_nil_reason"],
        "decision_payload_sha256": decision_payload_sha256(context),
        "truth_reason_codes": context["truth_reason_codes"],
        "annotation_reason_codes": context["annotation_reason_codes"],
        "action_applied": False,
        "public_apply": False,
        "central_slang_db_write": False,
        "publication_wal_write": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    event["event_sha256"] = annotation_event_sha256(event)
    event = with_row_hash(event)
    context["latest_annotation_event_sha256"] = event["event_sha256"]
    context = with_row_hash(context)
    return [claim], [context], [event]


def _rehash_context(context: dict) -> None:
    context["row_sha256"] = canonical_sha256(
        {key: value for key, value in context.items() if key != "row_sha256"}
    )


def _rehash_event(event: dict) -> None:
    event["event_sha256"] = annotation_event_sha256(event)
    event["row_sha256"] = canonical_sha256(
        {key: value for key, value in event.items() if key != "row_sha256"}
    )


class P0ActualAContextContractTests(unittest.TestCase):
    def test_example_bundle_is_valid_but_never_receives_actual_credit(self) -> None:
        receipt = validate_example_a_context_bundle(*_bundle())
        self.assertTrue(receipt["structural_validation_verified"])
        self.assertEqual(0, receipt["actual_a_context_review_count"])
        self.assertEqual("SHADOW_ONLY", receipt["authority"])
        self.assertFalse(receipt["owner_key_verified"])
        self.assertFalse(receipt["public_apply"])

    def test_actual_origin_is_separate_and_remains_keyless_shadow_only(self) -> None:
        receipt = validate_actual_a_context_bundle(*_bundle(ACTUAL_ORIGIN))
        self.assertEqual(ACTUAL_ORIGIN, receipt["record_origin"])
        self.assertEqual(0, receipt["actual_a_context_review_count"])
        with self.assertRaisesRegex(
            P0ActualAContextContractError, "origin namespace mismatch"
        ):
            validate_actual_a_context_bundle(*_bundle(EXAMPLE_ORIGIN))

    def test_track_b_claim_is_rejected(self) -> None:
        claims, contexts, events = _bundle()
        claims[0] = _claim(EXAMPLE_ORIGIN, track="B")
        contexts[0]["source_claim_ids"] = [claims[0]["claim_id"]]
        contexts[0]["source_claim_set_sha256"] = source_claim_set_sha256(claims)
        contexts[0]["evidence_receipt_sha256"] = evidence_receipt_sha256(contexts[0])
        contexts[0]["annotation_subject_sha256"] = annotation_subject_sha256(contexts[0])
        events[0]["evidence_claim_ids"] = contexts[0]["source_claim_ids"]
        events[0]["target_subject_sha256"] = contexts[0]["annotation_subject_sha256"]
        _rehash_event(events[0])
        contexts[0]["latest_annotation_event_sha256"] = events[0]["event_sha256"]
        _rehash_context(contexts[0])
        with self.assertRaisesRegex(P0ActualAContextContractError, "TRACK A claims only"):
            validate_example_a_context_bundle(claims, contexts, events)

    def test_sampling_units_must_be_unique(self) -> None:
        claims, contexts, events = _bundle()
        duplicate = deepcopy(contexts[0])
        duplicate["context_id"] += ":DUP"
        duplicate["annotation_subject_sha256"] = annotation_subject_sha256(duplicate)
        _rehash_context(duplicate)
        with self.assertRaisesRegex(P0ActualAContextContractError, "sampling_unit_id must be unique"):
            validate_example_a_context_bundle(claims, [contexts[0], duplicate], events)

    def test_id_reissue_cannot_launder_duplicate_content_span(self) -> None:
        claims, contexts, events = _bundle()
        duplicate = deepcopy(contexts[0])
        duplicate.update(
            {
                "context_id": f"{EXAMPLE_ORIGIN}:A:CONTEXT:02",
                "sampling_unit_id": f"{EXAMPLE_ORIGIN}:A:SAMPLE:02",
                "post_id": f"{EXAMPLE_ORIGIN}:POST:02",
                "latest_annotation_event_id": f"{EXAMPLE_ORIGIN}:A:EVENT:02",
            }
        )
        duplicate["sampling_unit_sha256"] = sampling_unit_sha256(duplicate)
        duplicate["annotation_subject_sha256"] = annotation_subject_sha256(duplicate)
        duplicate_event = deepcopy(events[0])
        duplicate_event.update(
            {
                "journal_id": f"{EXAMPLE_ORIGIN}:A:JOURNAL:02",
                "event_id": duplicate["latest_annotation_event_id"],
                "target_id": duplicate["context_id"],
                "target_subject_sha256": duplicate["annotation_subject_sha256"],
            }
        )
        _rehash_event(duplicate_event)
        duplicate["latest_annotation_event_sha256"] = duplicate_event["event_sha256"]
        _rehash_context(duplicate)
        with self.assertRaisesRegex(P0ActualAContextContractError, "sampling_unit_sha256"):
            validate_example_a_context_bundle(
                claims, [contexts[0], duplicate], [events[0], duplicate_event]
            )

    def test_sampling_frame_reissue_cannot_launder_duplicate_context(self) -> None:
        claims, contexts, events = _bundle()
        duplicate = deepcopy(contexts[0])
        duplicate.update(
            {
                "context_id": f"{EXAMPLE_ORIGIN}:A:CONTEXT:02",
                "sampling_unit_id": f"{EXAMPLE_ORIGIN}:A:SAMPLE:02",
                "post_id": f"{EXAMPLE_ORIGIN}:POST:02",
                "sampling_frame_sha256": SHA_D,
                "latest_annotation_event_id": f"{EXAMPLE_ORIGIN}:A:EVENT:02",
            }
        )
        duplicate["sampling_unit_sha256"] = sampling_unit_sha256(duplicate)
        duplicate["annotation_subject_sha256"] = annotation_subject_sha256(duplicate)
        duplicate_event = deepcopy(events[0])
        duplicate_event.update(
            {
                "journal_id": f"{EXAMPLE_ORIGIN}:A:JOURNAL:02",
                "event_id": duplicate["latest_annotation_event_id"],
                "target_id": duplicate["context_id"],
                "target_subject_sha256": duplicate["annotation_subject_sha256"],
            }
        )
        _rehash_event(duplicate_event)
        duplicate["latest_annotation_event_sha256"] = duplicate_event["event_sha256"]
        _rehash_context(duplicate)
        with self.assertRaisesRegex(P0ActualAContextContractError, "sampling_unit_sha256"):
            validate_example_a_context_bundle(
                claims, [contexts[0], duplicate], [events[0], duplicate_event]
            )

    def test_work_id_requires_matching_candidate_and_source_claim(self) -> None:
        claims, contexts, events = _bundle()
        contexts[0]["truth_work_id"] = "WORK:FORGED"
        contexts[0]["truth_reason_codes"] = ["truth_context_work_relation"]
        _rehash_context(contexts[0])
        with self.assertRaisesRegex(P0ActualAContextContractError, "complete bound candidate"):
            validate_example_a_context_bundle(claims, contexts, events)

    def test_nil_requires_complete_candidate_enumeration(self) -> None:
        claims, contexts, events = _bundle(kind="NIL")
        contexts[0]["candidate_registry_status"] = "INCOMPLETE"
        contexts[0]["evidence_receipt_sha256"] = evidence_receipt_sha256(contexts[0])
        contexts[0]["annotation_subject_sha256"] = annotation_subject_sha256(contexts[0])
        _rehash_context(contexts[0])
        with self.assertRaisesRegex(P0ActualAContextContractError, "NIL requires complete"):
            validate_example_a_context_bundle(claims, contexts, events)

    def test_unavailable_stays_unresolved_and_candidate_unavailable(self) -> None:
        receipt = validate_example_a_context_bundle(*_bundle(kind="UNRESOLVED"))
        self.assertEqual(1, receipt["validated_a_context_count"])
        claims, contexts, events = _bundle(kind="UNRESOLVED")
        contexts[0]["truth_kind"] = "NIL"
        contexts[0]["truth_nil_reason"] = "NIL_NON_WORK"
        contexts[0]["truth_reason_codes"] = ["truth_nil_non_work"]
        _rehash_context(contexts[0])
        with self.assertRaisesRegex(P0ActualAContextContractError, "must remain UNRESOLVED"):
            validate_example_a_context_bundle(claims, contexts, events)

    def test_latest_event_binds_subject_reviewer_guideline_and_decision(self) -> None:
        for field, forged in (
            ("reviewer_principal_sha256", SHA_D),
            ("guideline_sha256", SHA_D),
            ("latest_annotation_event_sha256", SHA_A),
        ):
            claims, contexts, events = _bundle()
            contexts[0][field] = forged
            _rehash_context(contexts[0])
            with self.subTest(field=field), self.assertRaisesRegex(
                P0ActualAContextContractError, "latest human A event binding"
            ):
                validate_example_a_context_bundle(claims, contexts, events)

    def test_event_hash_chain_and_latest_recheck_are_bound(self) -> None:
        claims, contexts, events = _bundle()
        first = events[0]
        second = deepcopy(first)
        second.update(
            {
                "journal_sequence": 2,
                "event_id": f"{EXAMPLE_ORIGIN}:A:EVENT:02",
                "previous_event_id": first["event_id"],
                "previous_event_sha256": first["event_sha256"],
                "event_kind": "INTRA_RATER_RECHECK",
                "supersedes_event_ids": [first["event_id"]],
                "occurred_at": "2026-01-04T00:00:00Z",
                "independent_review": False,
            }
        )
        _rehash_event(second)
        contexts[0]["latest_annotation_event_id"] = second["event_id"]
        contexts[0]["latest_annotation_event_sha256"] = second["event_sha256"]
        _rehash_context(contexts[0])
        validate_example_a_context_bundle(claims, contexts, [first, second])
        second["previous_event_sha256"] = SHA_D
        _rehash_event(second)
        with self.assertRaisesRegex(P0ActualAContextContractError, "hash chain mismatch"):
            validate_example_a_context_bundle(claims, contexts, [first, second])

    def test_journal_requires_primary_first_and_every_event_after_observation(self) -> None:
        claims, contexts, events = _bundle()
        events[0]["event_kind"] = "INTRA_RATER_RECHECK"
        events[0]["supersedes_event_ids"] = ["FORGED:EVENT"]
        events[0]["independent_review"] = False
        _rehash_event(events[0])
        contexts[0]["latest_annotation_event_sha256"] = events[0]["event_sha256"]
        _rehash_context(contexts[0])
        with self.assertRaisesRegex(P0ActualAContextContractError, "start with one primary"):
            validate_example_a_context_bundle(claims, contexts, events)

        claims, contexts, events = _bundle()
        first = events[0]
        first["occurred_at"] = "2026-01-01T12:00:00Z"
        _rehash_event(first)
        second = deepcopy(first)
        second.update(
            {
                "journal_sequence": 2,
                "event_id": f"{EXAMPLE_ORIGIN}:A:EVENT:02",
                "previous_event_id": first["event_id"],
                "previous_event_sha256": first["event_sha256"],
                "event_kind": "INTRA_RATER_RECHECK",
                "supersedes_event_ids": [first["event_id"]],
                "occurred_at": "2026-01-04T00:00:00Z",
                "independent_review": False,
            }
        )
        _rehash_event(second)
        contexts[0]["latest_annotation_event_id"] = second["event_id"]
        contexts[0]["latest_annotation_event_sha256"] = second["event_sha256"]
        _rehash_context(contexts[0])
        with self.assertRaisesRegex(P0ActualAContextContractError, "must not precede"):
            validate_example_a_context_bundle(claims, contexts, [first, second])

    def test_context_surface_must_match_every_referenced_claim(self) -> None:
        claims, contexts, events = _bundle()
        contexts[0]["normalized_surface"] = "공식"
        contexts[0]["annotation_subject_sha256"] = annotation_subject_sha256(contexts[0])
        events[0]["target_subject_sha256"] = contexts[0]["annotation_subject_sha256"]
        _rehash_event(events[0])
        contexts[0]["latest_annotation_event_sha256"] = events[0]["event_sha256"]
        _rehash_context(contexts[0])
        with self.assertRaisesRegex(P0ActualAContextContractError, "normalized surface"):
            validate_example_a_context_bundle(claims, contexts, events)

    def test_context_cannot_recut_a_claim_span_around_the_same_surface(self) -> None:
        claims, contexts, events = _bundle()
        context = contexts[0]
        context["content_text"] = "X별기는 별빛기록의 공식 약어다."
        context["content_fingerprint"] = canonical_sha256(context["content_text"])
        context["surface_start"] = 1
        context["surface_end"] = 3
        context["sampling_unit_sha256"] = sampling_unit_sha256(context)
        context["evidence_receipt_sha256"] = evidence_receipt_sha256(context)
        context["annotation_subject_sha256"] = annotation_subject_sha256(context)
        events[0]["target_subject_sha256"] = context["annotation_subject_sha256"]
        _rehash_event(events[0])
        context["latest_annotation_event_sha256"] = events[0]["event_sha256"]
        _rehash_context(context)
        with self.assertRaisesRegex(
            P0ActualAContextContractError, "claim span and surface binding"
        ):
            validate_example_a_context_bundle(claims, contexts, events)

    def test_recheck_cannot_change_reviewer_or_subject_evidence_cutoff(self) -> None:
        claims, contexts, events = _bundle()
        first = events[0]
        second = deepcopy(first)
        second.update(
            {
                "journal_sequence": 2,
                "event_id": f"{EXAMPLE_ORIGIN}:A:EVENT:02",
                "previous_event_id": first["event_id"],
                "previous_event_sha256": first["event_sha256"],
                "event_kind": "INTRA_RATER_RECHECK",
                "supersedes_event_ids": [first["event_id"]],
                "occurred_at": "2026-01-04T00:00:00Z",
                "independent_review": False,
                "reviewer_principal_sha256": SHA_D,
            }
        )
        _rehash_event(second)
        contexts[0]["latest_annotation_event_id"] = second["event_id"]
        contexts[0]["latest_annotation_event_sha256"] = second["event_sha256"]
        contexts[0]["reviewer_principal_sha256"] = SHA_D
        _rehash_context(contexts[0])
        with self.assertRaisesRegex(
            P0ActualAContextContractError, "reviewer/assignment drift"
        ):
            validate_example_a_context_bundle(claims, contexts, [first, second])

        claims, contexts, events = _bundle()
        first = events[0]
        second = deepcopy(first)
        first["evidence_cutoff"] = "2025-12-31T00:00:00Z"
        _rehash_event(first)
        second.update(
            {
                "journal_sequence": 2,
                "event_id": f"{EXAMPLE_ORIGIN}:A:EVENT:02",
                "previous_event_id": first["event_id"],
                "previous_event_sha256": first["event_sha256"],
                "event_kind": "INTRA_RATER_RECHECK",
                "supersedes_event_ids": [first["event_id"]],
                "occurred_at": "2026-01-04T00:00:00Z",
                "independent_review": False,
            }
        )
        _rehash_event(second)
        contexts[0]["latest_annotation_event_id"] = second["event_id"]
        contexts[0]["latest_annotation_event_sha256"] = second["event_sha256"]
        _rehash_context(contexts[0])
        with self.assertRaisesRegex(
            P0ActualAContextContractError, "evidence claim/cutoff drift"
        ):
            validate_example_a_context_bundle(claims, contexts, [first, second])

    def test_action_and_all_write_flags_are_false(self) -> None:
        for target_index, field in (
            (1, "public_apply"),
            (1, "central_slang_db_write"),
            (1, "publication_wal_write"),
            (2, "action_applied"),
        ):
            claims, contexts, events = _bundle()
            target = (claims, contexts, events)[target_index][0]
            target[field] = True
            if target_index == 1:
                _rehash_context(target)
            else:
                _rehash_event(target)
            with self.subTest(field=field), self.assertRaisesRegex(
                P0ActualAContextContractError, "no-write shadow only"
            ):
                validate_example_a_context_bundle(claims, contexts, events)

    def test_unreferenced_claim_and_orphan_event_fail_closed(self) -> None:
        claims, contexts, events = _bundle()
        orphan_claim = deepcopy(claims[0])
        orphan_claim["claim_id"] += ":ORPHAN"
        orphan_claim = with_registry_row_hash(orphan_claim)
        with self.assertRaisesRegex(P0ActualAContextContractError, "unreferenced"):
            validate_example_a_context_bundle(
                [claims[0], orphan_claim], contexts, events
            )
        events[0]["target_id"] = "MISSING:A:CONTEXT"
        _rehash_event(events[0])
        with self.assertRaisesRegex(P0ActualAContextContractError, "orphan"):
            validate_example_a_context_bundle(claims, contexts, events)

    def test_row_hash_and_decision_payload_tampering_are_rejected(self) -> None:
        claims, contexts, events = _bundle()
        contexts[0]["content_text"] += " 변조"
        with self.assertRaises(P0ActualAContextContractError):
            validate_example_a_context_bundle(claims, contexts, events)
        claims, contexts, events = _bundle()
        events[0]["decision_payload_sha256"] = SHA_A
        _rehash_event(events[0])
        with self.assertRaisesRegex(P0ActualAContextContractError, "decision payload"):
            validate_example_a_context_bundle(claims, contexts, events)


if __name__ == "__main__":
    unittest.main()
