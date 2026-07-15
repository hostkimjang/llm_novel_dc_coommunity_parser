from __future__ import annotations

import copy
from dataclasses import replace
import unittest

from src.llm_batch.grounding.candidate_generation import (
    build_candidate_generation_proof,
    build_candidate_generation_snapshot,
    build_candidate_producer_plan,
    build_candidate_producer_receipt,
    build_candidate_stage_receipt,
    build_title_candidate_generation_snapshot,
)
from src.llm_batch.grounding.candidate_set_shadow import (
    NIL_LABEL,
    PROBABILITY_STATUS,
    CandidateSet,
    LabelProbability,
    SelectiveShadowDecision,
    build_candidate_set,
    build_uncalibrated_selective_shadow,
    candidate_set_from_dict,
    selective_shadow_from_dict,
    selective_shadow_from_identity,
    unavailable_shadow_payload,
)
from src.llm_batch.grounding.candidate_audit import apply_candidate_audit_fields
from src.llm_batch.promotion_gate import (
    EvidenceRecord,
    GroundingState,
    RetrievalState,
    ScopeState,
    can_publish_title,
    publish_input_fingerprint,
)


def current_state(*, title: str = "작품 A", url: str = "https://example.test/work/1") -> GroundingState:
    return GroundingState(
        post_id=100,
        candidate_title=title,
        candidate_url=url,
        official_title_exists=bool(title),
        row_discusses_work_as_work=bool(title),
        title_resolution_state="resolved" if title else "unresolved_matchable",
        work_resolution="resolved" if title else "unresolved",
        scope=ScopeState(scope_kind="current_work" if title else "unknown", confidence="high"),
    )


def supporting_evidence(title: str, url: str, *, kind: str = "official_detail") -> EvidenceRecord:
    return EvidenceRecord(
        kind=kind,
        strength="strong",
        source_path_or_snippet=url or title,
        supports_publish=True,
        reason_code="official_detail_display_title_exact",
        candidate_title=title,
        candidate_url=url,
        title_url_match=True,
    )


def identity_fixture() -> dict:
    state = current_state()
    evidence = [supporting_evidence(state.candidate_title, state.candidate_url)]
    decision = can_publish_title(state, evidence)
    return {
        "novel_identity": {
            "official_title": decision.official_title,
            "official_url": decision.official_url,
        },
        "title_candidates": [
            {
                "official_title": "작품 A",
                "heretic_url": "https://example.test/work/1?utm_source=test",
                "source_tier": "official_detail",
                "reference_role": "primary",
            },
            {
                "official_title": "작품 B",
                "heretic_url": "https://example.test/work/2",
                "source_tier": "official_detail",
                "reference_role": "candidate",
            },
        ],
        "promotion_gate_state": state.to_dict(),
        "promotion_gate_evidence": [item.to_dict() for item in evidence],
        "promotion_decision": decision.to_dict(),
    }


class CandidateSetShadowContractTests(unittest.TestCase):
    def test_same_url_aliases_form_one_canonical_candidate(self):
        state = current_state(title="정식 제목", url="https://example.test/work/1?utm_source=x")
        evidence = [supporting_evidence("이전 제목", "https://example.test/work/1/")]
        candidate_set = build_candidate_set(
            state,
            evidence,
            additional_sources=[
                (
                    "title_candidates",
                    [{"official_title": "정식 제목", "heretic_url": "https://example.test/work/1"}],
                )
            ],
        )
        self.assertEqual(1, len(candidate_set.candidates))
        self.assertEqual(("이전 제목", "정식 제목"), candidate_set.candidates[0].titles)
        self.assertEqual(("https://example.test/work/1",), candidate_set.candidates[0].urls)
        self.assertTrue(candidate_set.candidates[0].baseline_selected)
        self.assertEqual("GO", candidate_set.integrity_status)

    def test_candidate_set_is_order_independent(self):
        state = GroundingState(post_id=1, candidate_title="", candidate_inventory_count=2)
        first = EvidenceRecord(
            kind="candidate_preservation",
            candidate_title="작품 A",
            candidate_url="https://example.test/a",
        )
        second = EvidenceRecord(
            kind="candidate_preservation",
            candidate_title="작품 B",
            candidate_url="https://example.test/b",
        )
        left = build_candidate_set(
            state,
            [first, second],
            additional_sources=[("mentioned_works", ["작품 B", "작품 A"])],
        )
        right = build_candidate_set(
            state,
            [second, first],
            additional_sources=[("mentioned_works", ["작품 A", "작품 B"])],
        )
        self.assertEqual(left.to_dict(), right.to_dict())
        self.assertEqual(2, len(left.candidates))

    def test_nil_is_a_class_and_abstain_is_a_separate_unapplied_action(self):
        state = GroundingState(post_id=1, candidate_title="", candidate_inventory_count=2)
        evidence = [
            EvidenceRecord(kind="candidate_preservation", candidate_title="작품 A"),
            EvidenceRecord(kind="candidate_preservation", candidate_title="작품 B"),
        ]
        baseline = can_publish_title(state, evidence)
        shadow = build_uncalibrated_selective_shadow(state, evidence, baseline)
        labels = [item.label for item in shadow.event_probabilities]
        self.assertEqual(NIL_LABEL, labels[-1])
        self.assertEqual(3, len(labels))
        self.assertTrue(all(item.probability is None for item in shadow.event_probabilities))
        self.assertEqual(PROBABILITY_STATUS, shadow.probability_status)
        self.assertEqual("NOT_EVALUATED", shadow.action)
        self.assertFalse(shadow.action_applied)
        self.assertIsNone(shadow.selected_label)

    def test_inventory_hint_mismatch_is_no_go(self):
        state = GroundingState(post_id=1, candidate_title="", candidate_inventory_count=2)
        evidence = [EvidenceRecord(kind="candidate_preservation", candidate_title="작품 A")]
        candidate_set = build_candidate_set(state, evidence)
        self.assertEqual("NO-GO", candidate_set.integrity_status)
        self.assertIn("candidate_inventory_count_mismatch", candidate_set.reason_codes)

    def test_same_title_with_multiple_urls_remains_two_work_events(self):
        state = GroundingState(post_id=1, candidate_title="", candidate_inventory_count=2)
        evidence = [
            EvidenceRecord(
                kind="candidate_preservation",
                candidate_title="같은 제목",
                candidate_url="https://example.test/a",
            ),
            EvidenceRecord(
                kind="candidate_preservation",
                candidate_title="같은 제목",
                candidate_url="https://example.test/b",
            ),
        ]
        candidate_set = build_candidate_set(state, evidence)
        self.assertEqual(2, len(candidate_set.candidates))
        self.assertTrue(all(item.event_eligible for item in candidate_set.candidates))
        self.assertEqual(2, candidate_set.event_candidate_count)
        self.assertEqual("GO", candidate_set.integrity_status)
        self.assertIn("multiple_work_candidates_present", candidate_set.reason_codes)

    def test_url_less_hold_alias_stays_outside_probability_event_space(self):
        state = GroundingState(post_id=1, candidate_title="", candidate_inventory_count=1)
        evidence = [
            EvidenceRecord(
                kind="candidate_preservation",
                candidate_title="정식 작품명",
                candidate_url="https://example.test/a",
            )
        ]
        candidate_set = build_candidate_set(
            state,
            evidence,
            additional_sources=[
                (
                    "candidate_preservation_sources",
                    [
                        {
                            "official_title": "작품 약칭",
                            "source_tier": "community",
                            "preservation_role": "recommendation_candidate",
                            "promotion_policy": "hold_without_promotion",
                        }
                    ],
                )
            ],
        )
        self.assertEqual(2, len(candidate_set.candidates))
        self.assertEqual(1, candidate_set.event_candidate_count)
        self.assertEqual(1, candidate_set.unlinked_surface_count)
        self.assertIn("unlinked_surfaces_preserved_outside_event_space", candidate_set.reason_codes)
        self.assertEqual("GO", candidate_set.integrity_status)

    def test_shadow_does_not_change_publication_fingerprint_or_decision(self):
        state = current_state()
        evidence = [supporting_evidence(state.candidate_title, state.candidate_url)]
        before_fingerprint = publish_input_fingerprint(state, evidence)
        before_decision = can_publish_title(state, evidence).to_dict()
        shadow = build_uncalibrated_selective_shadow(
            state,
            evidence,
            can_publish_title(state, evidence),
            additional_sources=[("title_candidates", [{"official_title": "작품 B"}])],
        )
        self.assertEqual(before_fingerprint, publish_input_fingerprint(state, evidence))
        self.assertEqual(before_decision, can_publish_title(state, evidence).to_dict())
        self.assertEqual("NONE_SHADOW_ONLY", shadow.operational_effect)

    def test_identity_replay_is_exact_and_additional_candidates_are_observed(self):
        identity = identity_fixture()
        before = copy.deepcopy(identity)
        shadow = selective_shadow_from_identity(identity)
        self.assertEqual(2, len(shadow.candidate_set.candidates))
        self.assertIsNotNone(shadow.baseline_selected_candidate_id)
        self.assertEqual(before, identity)
        self.assertEqual(
            before["promotion_decision"],
            can_publish_title(
                current_state(),
                [supporting_evidence("작품 A", "https://example.test/work/1")],
            ).to_dict(),
        )

    def test_candidate_audit_attaches_shadow_only_inside_ledger(self):
        identity = identity_fixture()
        public_before = copy.deepcopy(identity["novel_identity"])
        decision_before = copy.deepcopy(identity["promotion_decision"])
        state_before = copy.deepcopy(identity["promotion_gate_state"])
        fields = apply_candidate_audit_fields(identity)
        shadow = fields["candidate_ledger"]["candidate_set_shadow"]
        self.assertEqual("candidate_set_nil_shadow_v1", shadow["schema_version"])
        self.assertNotIn("candidate_set_shadow", {key: value for key, value in identity.items() if key != "candidate_ledger"})
        self.assertEqual(public_before, identity["novel_identity"])
        self.assertEqual(decision_before, identity["promotion_decision"])
        self.assertEqual(state_before, identity["promotion_gate_state"])

    def test_candidate_audit_contract_mismatch_attaches_separate_unavailable_envelope(self):
        identity = identity_fixture()
        identity["promotion_decision"]["status"] = "tampered"
        public_before = copy.deepcopy(identity["novel_identity"])
        fields = apply_candidate_audit_fields(identity)
        shadow = fields["candidate_ledger"]["candidate_set_shadow"]
        self.assertEqual("candidate_set_nil_shadow_unavailable_v1", shadow["schema_version"])
        self.assertIn("candidate_set_shadow_contract_invalid", fields["candidate_audit_lint"])
        self.assertEqual(public_before, identity["novel_identity"])

    def test_stored_decision_mismatch_fails_closed(self):
        identity = identity_fixture()
        identity["promotion_decision"]["status"] = "tampered_status"
        with self.assertRaisesRegex(ValueError, "does not replay exactly"):
            selective_shadow_from_identity(identity)

    def test_candidate_set_and_shadow_roundtrip(self):
        shadow = selective_shadow_from_identity(identity_fixture())
        restored_set = candidate_set_from_dict(shadow.candidate_set.to_dict())
        restored_shadow = selective_shadow_from_dict(shadow.to_dict())
        self.assertEqual(shadow.candidate_set, restored_set)
        self.assertEqual(shadow, restored_shadow)

    def test_candidate_set_fingerprint_tamper_is_rejected(self):
        shadow = selective_shadow_from_identity(identity_fixture())
        payload = shadow.candidate_set.to_dict()
        payload["source_record_count"] += 1
        with self.assertRaisesRegex(
            ValueError, "fingerprint mismatch|source_record_count/observation_signatures mismatch"
        ):
            candidate_set_from_dict(payload)

    def test_shadow_fingerprint_tamper_is_rejected(self):
        shadow = selective_shadow_from_identity(identity_fixture())
        payload = shadow.to_dict()
        payload["reason_codes"].append("tampered")
        with self.assertRaisesRegex(ValueError, "shadow_fingerprint mismatch"):
            selective_shadow_from_dict(payload)

    def test_malformed_boolean_is_rejected(self):
        shadow = selective_shadow_from_identity(identity_fixture())
        payload = shadow.to_dict()
        payload["action_applied"] = "false"
        with self.assertRaisesRegex(ValueError, "action_applied must be a bool"):
            selective_shadow_from_dict(payload)

    def test_partial_or_non_normalized_probability_vector_is_rejected(self):
        shadow = selective_shadow_from_identity(identity_fixture())
        labels = [item.label for item in shadow.event_probabilities]
        partial = tuple(
            LabelProbability(label=label, probability=0.5 if index == 0 else None)
            for index, label in enumerate(labels)
        )
        with self.assertRaisesRegex(ValueError, "all available or all null"):
            replace(shadow, event_probabilities=partial)
        bad_sum = tuple(
            LabelProbability(label=label, probability=0.2)
            for label in labels
        )
        with self.assertRaisesRegex(ValueError, "sum to 1"):
            replace(shadow, event_probabilities=bad_sum, probability_status="CALIBRATED")

    def test_available_probability_vector_cannot_claim_uncalibrated_status(self):
        shadow = selective_shadow_from_identity(identity_fixture())
        count = len(shadow.event_probabilities)
        available = tuple(
            LabelProbability(label=item.label, probability=1.0 / count)
            for item in shadow.event_probabilities
        )
        with self.assertRaisesRegex(ValueError, "CALIBRATED_SHADOW status"):
            replace(shadow, event_probabilities=available, selected_label=available[0].label)

    def test_direct_builder_rejects_arbitrary_baseline_decision(self):
        state = current_state()
        evidence = [supporting_evidence(state.candidate_title, state.candidate_url)]
        wrong = replace(can_publish_title(state, evidence), status="tampered")
        with self.assertRaisesRegex(ValueError, "baseline promotion decision does not replay"):
            build_uncalibrated_selective_shadow(state, evidence, wrong)

    def test_root_and_ledger_contract_namespaces_must_not_be_mixed(self):
        identity = identity_fixture()
        identity["candidate_ledger"] = {
            "promotion_gate_evidence": identity.pop("promotion_gate_evidence")
        }
        with self.assertRaisesRegex(ValueError, "incomplete root promotion contract namespace"):
            selective_shadow_from_identity(identity)

    def test_complete_root_and_ledger_contract_namespaces_must_match(self):
        identity = identity_fixture()
        identity["candidate_ledger"] = {
            "promotion_gate_state": copy.deepcopy(identity["promotion_gate_state"]),
            "promotion_gate_evidence": copy.deepcopy(identity["promotion_gate_evidence"]),
            "promotion_decision": copy.deepcopy(identity["promotion_decision"]),
        }
        identity["candidate_ledger"]["promotion_decision"]["status"] = "tampered"
        with self.assertRaisesRegex(ValueError, "root/ledger promotion decision mismatch"):
            selective_shadow_from_identity(identity)

    def test_malformed_root_namespace_cannot_fall_back_to_complete_ledger(self):
        identity = identity_fixture()
        identity["candidate_ledger"] = {
            "promotion_gate_state": copy.deepcopy(identity["promotion_gate_state"]),
            "promotion_gate_evidence": copy.deepcopy(identity["promotion_gate_evidence"]),
            "promotion_decision": copy.deepcopy(identity["promotion_decision"]),
        }
        identity["promotion_gate_state"] = None
        identity["promotion_gate_evidence"] = None
        identity["promotion_decision"] = "tampered"
        with self.assertRaisesRegex(ValueError, "incomplete root promotion contract namespace"):
            selective_shadow_from_identity(identity)

    def test_direct_builder_rejects_non_typed_evidence(self):
        with self.assertRaisesRegex(ValueError, "only EvidenceRecord"):
            build_candidate_set(current_state(), [{"kind": "candidate_preservation"}])

    def test_unavailable_payload_uses_a_distinct_non_roundtrip_schema(self):
        payload = unavailable_shadow_payload("typed_publish_contract_replay_failed")
        self.assertEqual("candidate_set_nil_shadow_unavailable_v1", payload["schema_version"])
        with self.assertRaises(ValueError):
            selective_shadow_from_dict(payload)

    def test_retrieval_block_is_a_reason_for_abstain_not_a_probability_class(self):
        state = replace(
            current_state(),
            retrieval=RetrievalState(required=True, attempted=True, recovered=False),
        )
        evidence = [supporting_evidence(state.candidate_title, state.candidate_url)]
        decision = can_publish_title(state, evidence)
        shadow = build_uncalibrated_selective_shadow(state, evidence, decision)
        self.assertIn("retrieval_failclose_requires_abstain", shadow.reason_codes)
        self.assertEqual("ABSTAIN", shadow.action)
        self.assertEqual(NIL_LABEL, shadow.event_probabilities[-1].label)
        self.assertFalse(any(item.label == "ABSTAIN" for item in shadow.event_probabilities))

    def test_empty_candidate_set_still_exposes_only_nil_event_without_asserting_nil(self):
        state = GroundingState(post_id=1, candidate_title="")
        decision = can_publish_title(state, [])
        shadow = build_uncalibrated_selective_shadow(state, [], decision)
        self.assertEqual((), shadow.candidate_set.candidates)
        self.assertEqual([NIL_LABEL], [item.label for item in shadow.event_probabilities])
        self.assertIsNone(shadow.selected_label)
        self.assertEqual("NOT_EVALUATED", shadow.action)

    def test_candidate_identity_fingerprint_ignores_duplicate_observation_multiplicity(self):
        state = GroundingState(post_id=1, candidate_title="")
        evidence = [EvidenceRecord(kind="candidate_preservation", candidate_title="작품 A")]
        left = build_candidate_set(state, evidence)
        right = build_candidate_set(
            state,
            evidence,
            additional_sources=[("mentioned_works", ["작품 A"])],
        )
        self.assertEqual(left.candidate_set_fingerprint, right.candidate_set_fingerprint)
        self.assertNotEqual(left.observation_fingerprint, right.observation_fingerprint)

    def test_alias_is_provenance_not_a_separate_probability_event(self):
        shadow = selective_shadow_from_identity(identity_fixture())
        work_a = next(
            option for option in shadow.candidate_set.candidates if "작품 A" in option.titles
        )
        self.assertEqual((), work_a.aliases)
        identity = identity_fixture()
        identity["title_candidates"][0]["alias_or_mention"] = "작A"
        with_alias = selective_shadow_from_identity(identity)
        work_a = next(
            option for option in with_alias.candidate_set.candidates if "작품 A" in option.titles
        )
        self.assertEqual(("작A",), work_a.aliases)
        labels = [item.label for item in with_alias.event_probabilities]
        self.assertEqual(with_alias.candidate_set.event_candidate_count + 1, len(labels))

    def test_alias_only_observation_is_preserved_as_non_event_surface(self):
        state = GroundingState(post_id=1, candidate_title="")
        candidate_set = build_candidate_set(
            state,
            [],
            additional_sources=[
                (
                    "candidate_preservation_sources",
                    [
                        {
                            "alias_or_mention": "작품 약칭",
                            "source_tier": "community",
                            "promotion_policy": "hold_without_promotion",
                        }
                    ],
                )
            ],
        )
        self.assertEqual(1, len(candidate_set.candidates))
        self.assertEqual(0, candidate_set.event_candidate_count)
        self.assertEqual("UNLINKED_SURFACE", candidate_set.candidates[0].option_kind)

    def test_typed_inventory_alias_link_does_not_create_probability_event(self):
        state = GroundingState(post_id=1, candidate_title="")
        evidence = [
            EvidenceRecord(kind="candidate_preservation", candidate_title="아카데미 생존 갤러리"),
            EvidenceRecord(kind="candidate_preservation", candidate_title="아생갤"),
        ]
        candidate_set = build_candidate_set(
            state,
            evidence,
            additional_sources=[
                (
                    "candidate_preservation_sources",
                    [
                        {
                            "official_title": "아카데미 생존 갤러리",
                            "alias_or_mention": "아생갤",
                            "preservation_role": "title_candidate",
                        },
                        {
                            "official_title": "아생갤",
                            "alias_or_mention": "아생갤",
                            "preservation_role": "recommendation_candidate",
                            "promotion_policy": "hold_without_promotion",
                        },
                    ],
                )
            ],
        )
        work = [item for item in candidate_set.candidates if item.option_kind == "WORK_CANDIDATE"]
        unlinked = [item for item in candidate_set.candidates if item.option_kind == "UNLINKED_SURFACE"]
        self.assertEqual(1, len(work))
        self.assertEqual(("아생갤",), work[0].aliases)
        self.assertEqual(1, len(unlinked))
        self.assertEqual(("아생갤",), unlinked[0].titles)
        self.assertEqual(1, candidate_set.event_candidate_count)

    def test_generation_at_cap_cannot_claim_complete(self):
        state = GroundingState(post_id=1, candidate_title="")
        evidence = [EvidenceRecord(kind="candidate_preservation", candidate_title="작품 A")]
        with self.assertRaisesRegex(ValueError, "at cap cannot be declared COMPLETE"):
            build_candidate_set(
                state,
                evidence,
                generation_status="COMPLETE",
                generation_cap=1,
            )
        with self.assertRaisesRegex(ValueError, "TRUNCATED generation requires"):
            build_candidate_set(state, evidence, generation_status="TRUNCATED")

    def test_duplicate_observations_at_cap_cannot_claim_complete(self):
        state = GroundingState(post_id=1, candidate_title="")
        evidence = [
            EvidenceRecord(kind="candidate_preservation", candidate_title="중복 작품")
            for _index in range(24)
        ]

        with self.assertRaisesRegex(ValueError, "at cap cannot be declared COMPLETE"):
            build_candidate_set(
                state,
                evidence,
                generation_status="COMPLETE",
                generation_cap=24,
            )

    def test_nested_ledger_generation_metadata_is_strict_and_root_fields_are_rejected(self):
        identity = identity_fixture()
        snapshot = build_candidate_generation_snapshot(
            identity["title_candidates"],
            cap=24,
        )
        identity["candidate_preservation_sources"] = copy.deepcopy(
            identity["title_candidates"]
        )
        identity["candidate_ledger"] = {
            "candidate_generation": snapshot.to_ledger_dict(),
        }

        shadow = selective_shadow_from_identity(identity)
        self.assertEqual("UNKNOWN", shadow.candidate_set.generation_status)
        self.assertEqual(24, shadow.candidate_set.generation_cap)
        self.assertEqual(
            "NOT_EVALUABLE_GENERATION_UNKNOWN",
            shadow.candidate_set.candidate_set_recall_status,
        )

        malformed = copy.deepcopy(identity)
        malformed["candidate_ledger"]["candidate_generation"]["cap"] = "24"
        with self.assertRaisesRegex(ValueError, "cap must be a positive int"):
            selective_shadow_from_identity(malformed)

        mixed = copy.deepcopy(identity)
        mixed["candidate_generation_status"] = "COMPLETE"
        with self.assertRaisesRegex(ValueError, "root candidate generation metadata is forbidden"):
            selective_shadow_from_identity(mixed)

    def test_nested_generation_metadata_must_match_retained_sources(self):
        identity = identity_fixture()
        snapshot = build_candidate_generation_snapshot(identity["title_candidates"], cap=24)
        identity["candidate_preservation_sources"] = copy.deepcopy(
            identity["title_candidates"]
        )
        identity["candidate_ledger"] = {
            "candidate_generation": snapshot.to_ledger_dict(),
        }
        identity["candidate_preservation_sources"][0]["official_title"] = "변조된 작품"

        with self.assertRaisesRegex(ValueError, "retained sources fingerprint mismatch"):
            selective_shadow_from_identity(identity)

    def test_title_stage_truncation_dominates_serializer_unknown(self):
        identity = identity_fixture()
        identity["candidate_preservation_sources"] = copy.deepcopy(
            identity["title_candidates"]
        )
        local = build_candidate_generation_snapshot(
            identity["candidate_preservation_sources"],
            cap=24,
        )
        title_sources = [
            {
                "official_title": f"상류 작품 {index}",
                "heretic_url": f"https://example.test/upstream/{index}",
                "preservation_role": "ranked_title_candidate",
            }
            for index in range(7)
        ]
        title_stage = build_title_candidate_generation_snapshot(title_sources, cap=6)
        identity["candidate_ledger"] = {
            "candidate_generation": local.to_ledger_dict(),
            "title_candidate_generation": title_stage.to_ledger_dict(),
            "title_candidate_generation_retained_sources": list(
                title_stage.retained_sources or ()
            ),
        }

        shadow = selective_shadow_from_identity(identity)

        self.assertEqual("TRUNCATED", shadow.candidate_set.generation_status)
        self.assertEqual(6, shadow.candidate_set.generation_cap)
        self.assertEqual(
            "NOT_EVALUABLE_GENERATION_TRUNCATED",
            shadow.candidate_set.candidate_set_recall_status,
        )

        tampered = copy.deepcopy(identity)
        tampered["candidate_ledger"]["title_candidate_generation_retained_sources"][0][
            "official_title"
        ] = "변조된 상류 작품"
        with self.assertRaisesRegex(ValueError, "retained sources fingerprint mismatch"):
            selective_shadow_from_identity(tampered)

    def test_stage_local_receipt_is_diagnostic_and_does_not_compose_candidate_set(self):
        identity = identity_fixture()
        baseline = selective_shadow_from_identity(identity)
        receipt = build_candidate_stage_receipt(
            [{"title": f"내부 후보 {index:02d}"} for index in range(6)],
            producer="verifier",
            stage="ranked_update",
        )
        with_receipt = copy.deepcopy(identity)
        with_receipt["candidate_ledger"] = {
            "candidate_stage_receipts": [receipt.to_ledger_dict()]
        }

        replay = selective_shadow_from_identity(with_receipt)

        self.assertEqual("TRUNCATED", receipt.status)
        self.assertEqual(baseline.to_dict(), replay.to_dict())
        self.assertEqual(
            identity["novel_identity"],
            with_receipt["novel_identity"],
        )

    def test_bound_search_fetch_proof_unlocks_recall_evaluation_only(self):
        identity = identity_fixture()
        public_before = copy.deepcopy(identity["novel_identity"])
        decision_before = copy.deepcopy(identity["promotion_decision"])
        identity["candidate_preservation_sources"] = copy.deepcopy(
            identity["title_candidates"]
        )
        local = build_candidate_generation_snapshot(
            identity["candidate_preservation_sources"],
            cap=24,
        )
        title_stage = build_title_candidate_generation_snapshot(
            identity["title_candidates"],
            cap=6,
        )
        search_input = {
            "query": 'site:example.test "작품 A"',
            "purpose": "official_title_verify",
        }
        fetch_input = {
            "url": "https://example.test/work/1",
            "purpose": "official_detail_fetch",
        }
        search_plan = build_candidate_producer_plan(
            [search_input],
            producer="search",
            occurrence=1,
            enumeration_finished=True,
        )
        fetch_plan = build_candidate_producer_plan(
            [fetch_input],
            producer="fetch",
            occurrence=1,
            enumeration_finished=True,
        )
        search_receipt = build_candidate_producer_receipt(
            [{"title": "작품 A", "url": "https://example.test/work/1"}],
            {"attempts": 1, "raw_total": 1, "enumeration_finished": True},
            producer="search",
            operation_input=search_input,
            purpose="official_title_verify",
            plan_fingerprint=search_plan.plan_fingerprint,
            occurrence=1,
        )
        fetch_receipt = build_candidate_producer_receipt(
            [
                {
                    "url": "https://example.test/work/1",
                    "structured_info": {"page_title": "작품 A"},
                }
            ],
            {"attempted_count": 1, "raw_count": 1, "enumeration_finished": True},
            producer="fetch",
            operation_input=fetch_input,
            purpose="official_detail_fetch",
            plan_fingerprint=fetch_plan.plan_fingerprint,
            occurrence=2,
        )
        proof = build_candidate_generation_proof(
            [search_plan, fetch_plan],
            [search_receipt, fetch_receipt],
            local_snapshots=[local, title_stage],
        )
        identity["candidate_ledger"] = {
            "candidate_generation": local.to_ledger_dict(),
            "title_candidate_generation": title_stage.to_ledger_dict(),
            "title_candidate_generation_retained_sources": list(
                title_stage.retained_sources or ()
            ),
            "candidate_producer_plans": [
                search_plan.to_ledger_dict(),
                fetch_plan.to_ledger_dict(),
            ],
            "candidate_producer_receipts": [
                search_receipt.to_ledger_dict(),
                fetch_receipt.to_ledger_dict(),
            ],
            "candidate_generation_proof": proof.to_ledger_dict(),
        }

        shadow = selective_shadow_from_identity(identity)

        self.assertEqual("COMPLETE", shadow.candidate_set.generation_status)
        self.assertEqual(
            "READY_FOR_GOLD_EVALUATION",
            shadow.candidate_set.candidate_set_recall_status,
        )
        self.assertEqual(PROBABILITY_STATUS, shadow.probability_status)
        self.assertTrue(
            all(item.probability is None for item in shadow.event_probabilities)
        )
        self.assertEqual(public_before, identity["novel_identity"])
        self.assertEqual(decision_before, identity["promotion_decision"])

        tampered = copy.deepcopy(identity)
        tampered["candidate_ledger"]["candidate_producer_receipts"][0][
            "accepted_count"
        ] = 0
        with self.assertRaises(ValueError):
            selective_shadow_from_identity(tampered)

    def test_forged_candidate_id_is_rejected_even_with_outer_payload(self):
        shadow = selective_shadow_from_identity(identity_fixture())
        payload = shadow.candidate_set.to_dict()
        payload["candidates"][0]["candidate_id"] = "cand_" + "0" * 64
        with self.assertRaisesRegex(ValueError, "candidate_id does not match"):
            candidate_set_from_dict(payload)


if __name__ == "__main__":
    unittest.main()
