from __future__ import annotations

import unittest

from src.llm_batch.early_route_measurement import (
    ACCURACY_NOT_ESTIMABLE,
    ARM_AFTER,
    FROZEN_TRUTH_VERIFIED,
    LANE_CHEAP_NIL,
    LANE_FULL,
    NIL_LABEL,
    CheapNilProposal,
    EarlyRouteComparisonReceipt,
    EarlyRouteDecision,
    EarlyRoutePolicyV1,
    EarlyRouteSourceView,
    canonical_hash,
    compare_early_route,
    decide_early_route,
)


def _sha(label: str) -> str:
    return canonical_hash({"label": label})


def _source(**changes) -> EarlyRouteSourceView:
    payload = {
        "publication_scope_id": _sha("scope"),
        "pair_id": "pair-early-route-1",
        "arm": ARM_AFTER,
        "input_index": 1,
        "post_id": "9001",
        "source_input_sha256": _sha("source-input"),
        "title": "",
        "text_blocks": (),
        "comments": (),
        "block_kinds": (),
        "image_url_count": 0,
        "external_url_count": 0,
        "source_evidence_count": 0,
        "unknown_block_count": 0,
        "input_truncated": False,
        "parse_error_codes": (),
    }
    payload.update(changes)
    return EarlyRouteSourceView.create(**payload)


def _compare(decision: EarlyRouteDecision, **changes) -> EarlyRouteComparisonReceipt:
    payload = {
        "authoritative_wal_receipt_sha256": _sha("wal-receipt"),
        "authoritative_wal_outcome": "HOLD",
        "authoritative_publish_allowed": False,
        "authoritative_title": None,
        "authoritative_url": None,
        "public_projection_before_sha256": _sha("public-projection"),
        "public_projection_after_sha256": _sha("public-projection"),
    }
    payload.update(changes)
    return compare_early_route(decision, **payload)


class EarlyRouteMeasurementContractTests(unittest.TestCase):
    def test_all_schemas_are_strict_self_hashed_and_round_trip(self) -> None:
        policy = EarlyRoutePolicyV1.create()
        source = _source(title="ㅋㅋㅋ!!!")
        decision = decide_early_route(source, policy)
        comparison = _compare(decision)

        self.assertEqual(EarlyRoutePolicyV1.from_dict(policy.to_dict()), policy)
        self.assertEqual(EarlyRouteSourceView.from_dict(source.to_dict()), source)
        self.assertEqual(
            CheapNilProposal.from_dict(decision.cheap_proposal.to_dict()),
            decision.cheap_proposal,
        )
        self.assertEqual(EarlyRouteDecision.from_dict(decision.to_dict()), decision)
        self.assertEqual(
            EarlyRouteComparisonReceipt.from_dict(comparison.to_dict()),
            comparison,
        )

        for value, parser, fingerprint_key in (
            (policy.to_dict(), EarlyRoutePolicyV1.from_dict, "policy_sha256"),
            (source.to_dict(), EarlyRouteSourceView.from_dict, "source_view_sha256"),
            (decision.to_dict(), EarlyRouteDecision.from_dict, "decision_sha256"),
            (comparison.to_dict(), EarlyRouteComparisonReceipt.from_dict, "receipt_sha256"),
        ):
            forged = dict(value)
            forged[fingerprint_key] = _sha(f"forged-{fingerprint_key}")
            with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
                parser(forged)

    def test_mapping_key_collision_is_rejected_before_hashing(self) -> None:
        with self.assertRaisesRegex(ValueError, "mapping key collision"):
            canonical_hash({1: "first", "1": "second"})

    def test_source_view_rejects_forbidden_posthoc_fields_and_unknown_extras(self) -> None:
        base = _source().to_dict()
        for key in (
            "wal_decision",
            "frozen_truth",
            "judge_seed",
            "slang_db",
            "session_memory",
            "search_results",
            "vlm_output",
            "ocr_text",
            "expert_output",
        ):
            forged = {**base, key: {"leak": True}}
            with self.subTest(key=key), self.assertRaisesRegex(
                ValueError, "forbidden source-view fields"
            ):
                EarlyRouteSourceView.from_dict(forged)
        with self.assertRaisesRegex(ValueError, "shape mismatch"):
            EarlyRouteSourceView.from_dict({**base, "unrelated_extra": True})

    def test_source_view_and_policy_are_after_only(self) -> None:
        with self.assertRaisesRegex(ValueError, "AFTER-only"):
            _source(arm="BEFORE")
        policy = EarlyRoutePolicyV1.create()
        forged = policy.to_dict()
        forged["allowed_arm"] = "BEFORE"
        forged["policy_sha256"] = canonical_hash(
            {key: value for key, value in forged.items() if key != "policy_sha256"}
        )
        with self.assertRaisesRegex(ValueError, "AFTER-only"):
            EarlyRoutePolicyV1.from_dict(forged)

    def test_zero_call_eligibility_is_narrow_and_fixed_nil(self) -> None:
        for title in ("", "   ... !!! ", "ㅋㅋㅋ", "ㅎㅎㅠㅠ!!"):
            with self.subTest(title=title):
                decision = decide_early_route(_source(title=title))
                self.assertEqual(decision.selected_lane, LANE_CHEAP_NIL)
                self.assertEqual(decision.hard_risk_codes, ())
                self.assertFalse(decision.provider_dispatch_allowed)
                self.assertTrue(decision.compute_route_executed)
                self.assertFalse(decision.public_action_applied)
                proposal = decision.cheap_proposal
                self.assertIsNotNone(proposal)
                self.assertEqual(proposal.selected_label, NIL_LABEL)
                self.assertFalse(proposal.publish_allowed)
                self.assertIsNone(proposal.official_title)
                self.assertIsNone(proposal.official_url)
                self.assertEqual(proposal.candidate_ids, ())
                self.assertFalse(proposal.public_action_applied)

    def test_single_emotive_jamo_fails_closed_because_repetition_is_unproven(self) -> None:
        decision = decide_early_route(_source(title="ㅋ"))
        self.assertEqual(decision.selected_lane, LANE_FULL)
        self.assertIn("EMOTIVE_JAMO_NOT_REPEATED", decision.hard_risk_codes)

    def test_meaningful_text_attacks_always_route_full(self) -> None:
        attacks = {
            "domain_alias": {"title": "아생갤"},
            "comment_title": {"comments": ("아카데미 생존 갤러리",)},
            "latin": {"title": "novel"},
            "digit": {"title": "123"},
            "episode": {"title": "123화"},
            "platform": {"title": "노벨피아"},
            "url": {"title": "https://novelpia.com/novel/1"},
            "domain_url": {"comments": ("novelpia.com/novel/1",)},
            "masking_jamo": {"title": "ㅁㅁ세계"},
            "masking_symbol": {"title": "■■"},
            "quote": {"title": "“ㅋㅋㅋ”"},
            "multiwork": {"title": "///"},
            "other_jamo": {"title": "ㄹㅇ"},
            "other_letter": {"title": "作品"},
            "unicode_symbol": {"title": "～～～"},
            "emoji": {"title": "😂😂"},
        }
        for name, change in attacks.items():
            with self.subTest(name=name):
                decision = decide_early_route(_source(**change))
                self.assertEqual(decision.selected_lane, LANE_FULL)
                self.assertTrue(decision.hard_risk_codes)
                self.assertTrue(decision.provider_dispatch_allowed)
                self.assertIsNone(decision.cheap_proposal)

    def test_inventory_and_block_alias_attacks_route_full(self) -> None:
        attacks = {
            "image_count": {"image_url_count": 1},
            "external_url_count": {"external_url_count": 1},
            "source_evidence_count": {"source_evidence_count": 1},
            "unknown_count": {"unknown_block_count": 1},
            "image_kind": {"block_kinds": ("image",)},
            "image_url_alias": {"block_kinds": ("image_url",)},
            "src_alias": {"block_kinds": ("src",)},
            "attachment": {"block_kinds": ("attachment",)},
            "search_block": {"block_kinds": ("search_result",)},
            "vlm_block": {"block_kinds": ("vlm_enrichment",)},
            "unknown_kind": {"block_kinds": ("mystery",)},
            "truncated": {"input_truncated": True},
            "parse_error": {"parse_error_codes": ("INVALID_BLOCK",)},
        }
        for name, change in attacks.items():
            with self.subTest(name=name):
                decision = decide_early_route(_source(**change))
                self.assertEqual(decision.selected_lane, LANE_FULL)
                self.assertTrue(decision.hard_risk_codes)

    def test_known_text_block_with_only_noise_stays_cheap(self) -> None:
        decision = decide_early_route(
            _source(
                title="!!!",
                text_blocks=("ㅋㅋㅋ",),
                comments=("ㅎㅎ",),
                block_kinds=("text",),
            )
        )
        self.assertEqual(decision.selected_lane, LANE_CHEAP_NIL)

    def test_risk_codes_are_deterministic_sorted_and_unique(self) -> None:
        source = _source(
            title="아생갤 123화 https://example.com \"A/B\"",
            comments=("문피아",),
            block_kinds=("image_url", "mystery"),
            image_url_count=1,
            external_url_count=1,
            source_evidence_count=1,
            input_truncated=True,
            parse_error_codes=("B", "A"),
        )
        first = decide_early_route(source)
        second = decide_early_route(source)
        self.assertEqual(first, second)
        self.assertEqual(first.hard_risk_codes, tuple(sorted(set(first.hard_risk_codes))))

    def test_source_only_route_is_invariant_when_wal_or_truth_changes(self) -> None:
        source = _source(title="ㅋㅋㅋ")
        decision_before = decide_early_route(source)
        missing_truth = _compare(decision_before)
        candidate_truth = _compare(
            decision_before,
            authoritative_wal_receipt_sha256=_sha("different-wal"),
            frozen_truth_status=FROZEN_TRUTH_VERIFIED,
            frozen_truth_receipt_sha256=_sha("truth-receipt"),
            frozen_truth_label="candidate-123",
        )
        self.assertEqual(decision_before, decide_early_route(source))
        self.assertEqual(
            missing_truth.route_decision_sha256,
            candidate_truth.route_decision_sha256,
        )
        self.assertNotEqual(missing_truth.receipt_sha256, candidate_truth.receipt_sha256)

    def test_wal_parity_is_baseline_equivalence_not_truth(self) -> None:
        comparison = _compare(decide_early_route(_source(title="ㅋㅋ")))
        self.assertEqual(comparison.baseline_equivalence_status, "BASELINE_EQUIVALENT")
        self.assertFalse(comparison.baseline_equivalence_is_truth)
        self.assertTrue(comparison.public_projection_match)
        self.assertEqual(comparison.accuracy_status, ACCURACY_NOT_ESTIMABLE)
        self.assertIsNone(comparison.accuracy_match)
        self.assertEqual(comparison.gate, "NO_GO_ACCURACY_NOT_ESTIMABLE")
        self.assertFalse(comparison.production_enable_allowed)

    def test_verified_frozen_nil_can_only_open_measurement_comparison_gate(self) -> None:
        comparison = _compare(
            decide_early_route(_source(title="ㅋㅋ")),
            frozen_truth_status=FROZEN_TRUTH_VERIFIED,
            frozen_truth_receipt_sha256=_sha("truth-receipt"),
            frozen_truth_label=NIL_LABEL,
        )
        self.assertEqual(comparison.accuracy_status, "MATCH_FROZEN_ACTUAL")
        self.assertTrue(comparison.accuracy_match)
        self.assertEqual(comparison.gate, "GO_MEASUREMENT_COMPARISON_ONLY")
        self.assertFalse(comparison.public_action_applied)
        self.assertFalse(comparison.production_enable_allowed)

    def test_candidate_truth_is_false_cheap_and_blocks_gate(self) -> None:
        comparison = _compare(
            decide_early_route(_source(title="ㅋㅋ")),
            frozen_truth_status=FROZEN_TRUTH_VERIFIED,
            frozen_truth_receipt_sha256=_sha("truth-receipt"),
            frozen_truth_label="candidate-work-1",
        )
        self.assertEqual(comparison.accuracy_status, "MISMATCH_FROZEN_ACTUAL")
        self.assertFalse(comparison.accuracy_match)
        self.assertEqual(comparison.gate, "NO_GO_FROZEN_ACTUAL_MISMATCH")

    def test_wal_publish_mismatch_and_public_interference_each_block(self) -> None:
        decision = decide_early_route(_source(title="ㅋㅋ"))
        mismatch = _compare(
            decision,
            authoritative_wal_outcome="PUBLISH",
            authoritative_publish_allowed=True,
            authoritative_title="작품명",
            frozen_truth_status=FROZEN_TRUTH_VERIFIED,
            frozen_truth_receipt_sha256=_sha("truth"),
            frozen_truth_label=NIL_LABEL,
        )
        self.assertEqual(mismatch.baseline_equivalence_status, "BASELINE_MISMATCH")
        self.assertEqual(mismatch.gate, "NO_GO_BASELINE_MISMATCH")

        interference = _compare(
            decision,
            public_projection_after_sha256=_sha("mutated-public"),
            frozen_truth_status=FROZEN_TRUTH_VERIFIED,
            frozen_truth_receipt_sha256=_sha("truth"),
            frozen_truth_label=NIL_LABEL,
        )
        self.assertEqual(interference.public_noninterference_status, "VIOLATION")
        self.assertEqual(interference.gate, "NO_GO_PUBLIC_INTERFERENCE")

    def test_missing_truth_cannot_be_laundered_with_unbound_fields(self) -> None:
        decision = decide_early_route(_source(title="ㅋㅋ"))
        with self.assertRaisesRegex(ValueError, "must not carry evidence"):
            _compare(
                decision,
                frozen_truth_receipt_sha256=_sha("truth"),
                frozen_truth_label=NIL_LABEL,
            )
        with self.assertRaisesRegex(ValueError, "requires a receipt and label"):
            _compare(decision, frozen_truth_status=FROZEN_TRUTH_VERIFIED)

    def test_full_route_comparison_never_claims_cheap_accuracy(self) -> None:
        decision = decide_early_route(_source(title="아생갤"))
        comparison = _compare(
            decision,
            frozen_truth_status=FROZEN_TRUTH_VERIFIED,
            frozen_truth_receipt_sha256=_sha("truth"),
            frozen_truth_label="candidate-work",
        )
        self.assertEqual(comparison.selected_lane, LANE_FULL)
        self.assertEqual(
            comparison.baseline_equivalence_status,
            "NOT_APPLICABLE_FULL_EXPERT",
        )
        self.assertIsNone(comparison.public_projection_match)
        self.assertEqual(comparison.accuracy_status, "NOT_APPLICABLE_FULL_EXPERT")
        self.assertEqual(comparison.gate, "NO_GO_FULL_EXPERT_REQUIRED")

    def test_forged_public_action_and_proposal_are_rejected(self) -> None:
        proposal = CheapNilProposal.create()
        forged_proposal = proposal.to_dict()
        forged_proposal["publish_allowed"] = True
        forged_proposal["proposal_sha256"] = canonical_hash(
            {key: value for key, value in forged_proposal.items() if key != "proposal_sha256"}
        )
        with self.assertRaisesRegex(ValueError, "cannot publish"):
            CheapNilProposal.from_dict(forged_proposal)

        decision = decide_early_route(_source(title="ㅋㅋ"))
        forged_decision = decision.to_dict()
        forged_decision["public_action_applied"] = True
        forged_decision["decision_sha256"] = canonical_hash(
            {key: value for key, value in forged_decision.items() if key != "decision_sha256"}
        )
        with self.assertRaisesRegex(ValueError, "must not apply a public action"):
            EarlyRouteDecision.from_dict(forged_decision)

    def test_self_rehashed_comparison_cannot_forge_gate_or_status_relations(self) -> None:
        comparison = _compare(decide_early_route(_source(title="ㅋㅋ")))
        attacks = {
            "gate": ("GO_MEASUREMENT_COMPARISON_ONLY", "missing P3 truth"),
            "baseline_equivalence_status": (
                "BASELINE_MISMATCH",
                "baseline equivalence status",
            ),
            "public_noninterference_status": (
                "VIOLATION",
                "public noninterference status",
            ),
            "accuracy_status": (
                "MATCH_FROZEN_ACTUAL",
                "missing P3 truth",
            ),
        }
        for field_name, (forged_value, message) in attacks.items():
            with self.subTest(field_name=field_name):
                forged = comparison.to_dict()
                forged[field_name] = forged_value
                forged["receipt_sha256"] = canonical_hash(
                    {
                        key: value
                        for key, value in forged.items()
                        if key != "receipt_sha256"
                    }
                )
                with self.assertRaisesRegex(ValueError, message):
                    EarlyRouteComparisonReceipt.from_dict(forged)

    def test_constructor_rejects_mapping_payloads_in_raw_source_text(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be a string"):
            _source(text_blocks=({"expert_output": "leak"},))
        with self.assertRaisesRegex(ValueError, "must be a string"):
            _source(comments=({"judge_seed": "leak"},))


if __name__ == "__main__":
    unittest.main()
