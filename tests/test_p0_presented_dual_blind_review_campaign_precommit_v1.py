from __future__ import annotations

import ast
import base64
from copy import deepcopy
import inspect
import json
import os
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_batch.grounding import p0_presented_dual_blind_review_campaign_precommit_v1_contract as contract  # noqa: E402
from llm_batch.grounding import p0_presented_neutral_review_signature_math_v1_contract as signature_math  # noqa: E402
from tests.test_p0_external_owner_asymmetric_signature import _TestOnlyCngSigner  # noqa: E402
from tests.test_p0_presented_neutral_review_accounting_v1 import _review_bundle  # noqa: E402

try:  # The standalone parent is authored independently from this test fixture.
    from llm_batch.grounding import p0_presented_dual_blind_review_campaign_precommit_v1_parent_validator as parent  # type: ignore[no-redef]  # noqa: E402
except ImportError:  # pragma: no cover - temporary while the independent parent lands
    parent = None


CAMP = "campaign-dual-blind-candidate-001"
RUN = "run-dual-blind-candidate-001"
TRUST = "review-trust-candidate"
PROJECT = "llm-novel-dc-community-parser"
ENVIRONMENT = "p0-shadow"
ASSIGNMENT_SEALED_AT = "2026-09-03T00:00:20Z"
CAMPAIGN_PRECOMMITTED_AT = "2026-09-03T00:00:21Z"


def _object(raw: bytes) -> dict[str, object]:
    return json.loads(raw.decode("utf-8"))


def _rows(raw: bytes) -> list[dict[str, object]]:
    return [json.loads(line) for line in raw.decode("utf-8").splitlines()]


def _file(value: object) -> bytes:
    return contract.canonical_file_bytes(value)


def _jsonl(values: list[dict[str, object]]) -> bytes:
    return b"".join(_file(value) for value in values)


def _reseal(
    value: dict[str, object], field: str, *, domain: str | None = None
) -> dict[str, object]:
    material = {key: item for key, item in value.items() if key != field}
    digest_input: object = (
        material
        if domain is None
        else {"self_hash_domain": domain, "self_hash_material": material}
    )
    return {**material, field: contract.canonical_sha256(digest_input)}


@unittest.skipUnless(os.name == "nt", "Windows CNG is required")
class PresentedDualBlindReviewCampaignPrecommitV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.signers = [_TestOnlyCngSigner() for _ in range(6)]
        cls.bundle = cls._build_honest_bundle()

    @classmethod
    def tearDownClass(cls) -> None:
        for signer in cls.signers:
            signer.close()

    @classmethod
    def _pin(
        cls,
        index: int,
        kind: str,
        *,
        key_id: str | None = None,
        principal: str | None = None,
        authority_anchor: str | None = None,
        signer_index: int | None = None,
    ) -> bytes:
        signer = cls.signers[index if signer_index is None else signer_index]
        return signature_math.build_presented_review_key_pin_bytes(
            signature_kind=kind,
            trust_domain=TRUST,
            project_id=PROJECT,
            environment=ENVIRONMENT,
            key_id=key_id or f"review-campaign-key-{index + 1}",
            key_epoch=1,
            public_key_x_base64=base64.b64encode(signer.x).decode("ascii"),
            public_key_y_base64=base64.b64encode(signer.y).decode("ascii"),
            signer_principal_commitment_sha256=principal
            or contract.canonical_sha256({"principal": index + 1}),
            authority_anchor_sha256=authority_anchor
            or contract.canonical_sha256("shared-review-authority-anchor"),
            presented_revocation_snapshot_raw_sha256=contract.canonical_sha256(
                "shared-review-revocation-snapshot"
            ),
        )

    @classmethod
    def _build_honest_bundle(cls) -> dict[str, object]:
        old = _review_bundle()
        guideline = contract.build_review_guideline_bytes(
            campaign_id=CAMP,
            guideline_id="neutral-full-payload-guideline-v1",
            guideline_version=1,
        )
        response = contract.build_review_response_schema_bytes(
            campaign_id=CAMP,
            response_schema_id="neutral-full-payload-response-v1",
        )
        policy_pin = cls._pin(0, signature_math.CAMPAIGN_POLICY_PREAUTHORIZATION)
        lease_pin = cls._pin(1, signature_math.REVIEW_LEASE)
        final_pin = cls._pin(2, signature_math.FINAL_REVIEW_ATTESTATION)
        reviewer_pins = [
            cls._pin(index, signature_math.HUMAN_REVIEW_RESULT)
            for index in range(3, 6)
        ]
        reviewers = [
            {
                "reviewer_id": f"reviewer-opaque-{index + 1}",
                "identity_commitment_sha256": _object(pin)[
                    "signer_principal_commitment_sha256"
                ],
                "independence_group_id": f"human-group-{index + 1}",
                "public_key_pin_raw": pin,
            }
            for index, pin in enumerate(reviewer_pins)
        ]
        pin_inventory, actors = (
            contract.build_key_pin_inventory_and_actor_roster_bytes(
                campaign_policy_pin_raw=policy_pin,
                campaign_policy_independence_group_id="policy-group",
                review_lease_pin_raw=lease_pin,
                review_lease_independence_group_id="lease-group",
                final_attestation_pin_raw=final_pin,
                final_attestation_independence_group_id="final-group",
                reviewers=reviewers,
            )
        )
        reviewer_ids = [
            ["reviewer-opaque-1", "reviewer-opaque-2", "reviewer-opaque-3"]
            for _ in range(contract.EXPECTED_INPUT_COUNT)
        ]
        opaque_ids = [
            [
                contract.canonical_sha256(
                    {"opaque-candidate": input_sequence, "slot": slot}
                )
                for slot in contract.ASSIGNMENT_SLOTS
            ]
            for input_sequence in range(1, contract.EXPECTED_INPUT_COUNT + 1)
        ]
        assignments = contract.build_assignment_inventory_bytes(
            campaign_id=CAMP,
            run_id=RUN,
            actor_roster_raw=actors,
            reviewer_ids_by_input=reviewer_ids,
            opaque_task_ids_by_input=opaque_ids,
        )
        private_map = contract.build_evaluator_private_map_bytes(
            campaign_id=CAMP,
            run_id=RUN,
            review_unit_inventory_raw=old["units"],
            assignment_inventory_raw=assignments,
            actor_roster_raw=actors,
        )
        tasks = contract.build_reviewer_facing_task_inventory_bytes(
            campaign_id=CAMP,
            run_id=RUN,
            evaluator_private_map_raw=private_map,
            review_guideline_raw=guideline,
            response_schema_raw=response,
        )
        precommit = contract.build_campaign_precommit_bytes(
            campaign_id=CAMP,
            run_id=RUN,
            trust_domain=TRUST,
            project_id=PROJECT,
            environment=ENVIRONMENT,
            sampling_plan_raw=old["plan"],
            expected_sampling_plan_raw_sha256=contract.raw_sha256(old["plan"]),
            bridge_inventory_raw=old["bridge"],
            batch_precommit_raw=old["precommit"],
            expected_batch_precommit_raw_sha256=contract.raw_sha256(old["precommit"]),
            parser_results_raw=old["results"],
            batch_receipt_raw=old["receipt"],
            unreviewed_inventory_raw=old["unreviewed"],
            review_unit_inventory_raw=old["units"],
            review_guideline_raw=guideline,
            response_schema_raw=response,
            key_pin_inventory_raw=pin_inventory,
            actor_roster_raw=actors,
            assignment_inventory_raw=assignments,
            evaluator_private_map_raw=private_map,
            reviewer_facing_task_inventory_raw=tasks,
            presented_assignment_sealed_at=ASSIGNMENT_SEALED_AT,
            presented_campaign_precommitted_at=CAMPAIGN_PRECOMMITTED_AT,
        )
        subject = signature_math.build_presented_review_subject_bytes(
            signature_kind=signature_math.CAMPAIGN_POLICY_PREAUTHORIZATION,
            trust_domain=TRUST,
            project_id=PROJECT,
            environment=ENVIRONMENT,
            campaign_id=CAMP,
            run_id=RUN,
            subject_id="dual-blind-campaign-policy-precommit-001",
            presented_issued_at=CAMPAIGN_PRECOMMITTED_AT,
            nonce_commitment_sha256=contract.canonical_sha256(
                "presented-campaign-policy-nonce"
            ),
            payload_raw=precommit,
            predecessor_subject_raw_sha256=None,
        )
        unsigned = signature_math.build_presented_review_signature_envelope_material(
            public_key_pin_raw=policy_pin,
            subject_raw=subject,
            payload_raw=precommit,
        )
        signature = cls.signers[0].sign_low_s(signature_math.canonical_bytes(unsigned))
        envelope = signature_math.seal_presented_review_signature_envelope_bytes(
            unsigned_material=unsigned,
            signature_rs_base64=base64.b64encode(signature).decode("ascii"),
        )
        bundle: dict[str, object] = {
            **old,
            "guideline": guideline,
            "response": response,
            "policy_pin": policy_pin,
            "lease_pin": lease_pin,
            "final_pin": final_pin,
            "reviewer_pins": reviewer_pins,
            "pin_inventory": pin_inventory,
            "actors": actors,
            "assignments": assignments,
            "private_map": private_map,
            "tasks": tasks,
            "campaign_precommit": precommit,
            "policy_subject": subject,
            "policy_envelope": envelope,
        }
        bundle["campaign_receipt"] = cls._producer(bundle)
        return bundle

    @staticmethod
    def _producer(bundle: dict[str, object], **overrides: object) -> dict[str, object]:
        args: dict[str, object] = {
            "sampling_plan_raw": bundle["plan"],
            "expected_sampling_plan_raw_sha256": contract.raw_sha256(bundle["plan"]),
            "bridge_inventory_raw": bundle["bridge"],
            "batch_precommit_raw": bundle["precommit"],
            "expected_batch_precommit_raw_sha256": contract.raw_sha256(bundle["precommit"]),
            "parser_results_raw": bundle["results"],
            "batch_receipt_raw": bundle["receipt"],
            "unreviewed_inventory_raw": bundle["unreviewed"],
            "review_unit_inventory_raw": bundle["units"],
            "review_guideline_raw": bundle["guideline"],
            "response_schema_raw": bundle["response"],
            "key_pin_inventory_raw": bundle["pin_inventory"],
            "actor_roster_raw": bundle["actors"],
            "assignment_inventory_raw": bundle["assignments"],
            "evaluator_private_map_raw": bundle["private_map"],
            "reviewer_facing_task_inventory_raw": bundle["tasks"],
            "campaign_precommit_raw": bundle["campaign_precommit"],
            "policy_signature_subject_raw": bundle["policy_subject"],
            "policy_signature_envelope_raw": bundle["policy_envelope"],
        }
        args.update(overrides)
        return contract.validate_presented_dual_blind_review_campaign_precommit_bundle(
            **args
        )

    @staticmethod
    def _build_precommit(bundle: dict[str, object], **overrides: object) -> bytes:
        args: dict[str, object] = {
            "campaign_id": CAMP,
            "run_id": RUN,
            "trust_domain": TRUST,
            "project_id": PROJECT,
            "environment": ENVIRONMENT,
            "sampling_plan_raw": bundle["plan"],
            "expected_sampling_plan_raw_sha256": contract.raw_sha256(bundle["plan"]),
            "bridge_inventory_raw": bundle["bridge"],
            "batch_precommit_raw": bundle["precommit"],
            "expected_batch_precommit_raw_sha256": contract.raw_sha256(bundle["precommit"]),
            "parser_results_raw": bundle["results"],
            "batch_receipt_raw": bundle["receipt"],
            "unreviewed_inventory_raw": bundle["unreviewed"],
            "review_unit_inventory_raw": bundle["units"],
            "review_guideline_raw": bundle["guideline"],
            "response_schema_raw": bundle["response"],
            "key_pin_inventory_raw": bundle["pin_inventory"],
            "actor_roster_raw": bundle["actors"],
            "assignment_inventory_raw": bundle["assignments"],
            "evaluator_private_map_raw": bundle["private_map"],
            "reviewer_facing_task_inventory_raw": bundle["tasks"],
            "presented_assignment_sealed_at": ASSIGNMENT_SEALED_AT,
            "presented_campaign_precommitted_at": CAMPAIGN_PRECOMMITTED_AT,
        }
        args.update(overrides)
        return contract.build_campaign_precommit_bytes(**args)

    @staticmethod
    def _parent(bundle: dict[str, object], **overrides: object) -> dict[str, object]:
        if parent is None:  # pragma: no cover - only during independent authoring race
            raise unittest.SkipTest("independent parent validator has not landed yet")
        args: dict[str, object] = {
            "sampling_plan_raw": bundle["plan"],
            "expected_sampling_plan_raw_sha256": contract.raw_sha256(bundle["plan"]),
            "bridge_inventory_raw": bundle["bridge"],
            "batch_precommit_raw": bundle["precommit"],
            "expected_batch_precommit_raw_sha256": contract.raw_sha256(bundle["precommit"]),
            "parser_results_raw": bundle["results"],
            "batch_receipt_raw": bundle["receipt"],
            "unreviewed_inventory_raw": bundle["unreviewed"],
            "review_unit_inventory_raw": bundle["units"],
            "review_guideline_raw": bundle["guideline"],
            "response_schema_raw": bundle["response"],
            "key_pin_inventory_raw": bundle["pin_inventory"],
            "actor_roster_raw": bundle["actors"],
            "assignment_inventory_raw": bundle["assignments"],
            "evaluator_private_map_raw": bundle["private_map"],
            "reviewer_facing_task_inventory_raw": bundle["tasks"],
            "campaign_precommit_raw": bundle["campaign_precommit"],
            "policy_signature_subject_raw": bundle["policy_subject"],
            "policy_signature_envelope_raw": bundle["policy_envelope"],
            "component_receipt_raw": _file(bundle["campaign_receipt"]),
        }
        args.update(overrides)
        return parent.validate_presented_dual_blind_review_campaign_precommit_against_raw_inputs(
            **args
        )

    def test_honest_40_by_3_bundle_signature_math_and_parent_replay(self) -> None:
        receipt = self._producer(self.bundle)
        self.assertEqual(receipt["selected_input_count"], 40)
        self.assertEqual(receipt["primary_assignment_count"], 80)
        self.assertEqual(receipt["reserve_assignment_count"], 40)
        self.assertEqual(receipt["total_assignment_count"], 120)
        self.assertEqual(receipt["opaque_task_id_count"], 120)
        self.assertEqual(receipt["selected_input_itt_denominator"], 40)
        self.assertEqual(receipt["planned_primary_review_opportunity_denominator"], 80)
        self.assertEqual(receipt["primary_pair_input_denominator"], 40)
        self.assertEqual(receipt["maximum_reserve_adjudication_opportunity_denominator"], 40)
        self.assertEqual(receipt["planned_final_judged_input_denominator"], 40)
        self.assertIsNone(receipt["required_adjudication_denominator"])
        self.assertEqual(
            receipt["required_adjudication_denominator_derivation"],
            "AFTER_ALL_80_PRIMARY_TERMINALS_FROZEN_COUNT_BOTH_AUTHORITY_QUALIFIED_JUDGED_PAIRS_WITH_DIFFERENT_CANONICAL_FULL_GOLD_SETS",
        )
        self.assertTrue(receipt["campaign_policy_signature_math_verified"])
        self.assertTrue(receipt["dual_primary_and_reserve_preassignment_structure_verified"])
        parent_receipt = self._parent(self.bundle, component_receipt_raw=_file(receipt))
        self.assertTrue(parent_receipt["parent_separate_implementation_raw_replay_verified"])

    def test_result_import_surface_is_absent_and_legacy_results_are_ineligible(self) -> None:
        expected_build = {
            "campaign_id", "run_id", "trust_domain", "project_id", "environment",
            "sampling_plan_raw", "expected_sampling_plan_raw_sha256",
            "bridge_inventory_raw", "batch_precommit_raw",
            "expected_batch_precommit_raw_sha256", "parser_results_raw",
            "batch_receipt_raw", "unreviewed_inventory_raw",
            "review_unit_inventory_raw", "review_guideline_raw",
            "response_schema_raw", "key_pin_inventory_raw", "actor_roster_raw",
            "assignment_inventory_raw", "evaluator_private_map_raw",
            "reviewer_facing_task_inventory_raw", "presented_assignment_sealed_at",
            "presented_campaign_precommitted_at",
        }
        expected_validate = expected_build.difference(
            {
                "campaign_id", "run_id", "trust_domain", "project_id", "environment",
                "presented_assignment_sealed_at", "presented_campaign_precommitted_at",
            }
        ).union(
            {
                "campaign_precommit_raw", "policy_signature_subject_raw",
                "policy_signature_envelope_raw",
            }
        )
        self.assertEqual(
            set(inspect.signature(contract.build_campaign_precommit_bytes).parameters),
            expected_build,
        )
        self.assertEqual(
            set(
                inspect.signature(
                    contract.validate_presented_dual_blind_review_campaign_precommit_bundle
                ).parameters
            ),
            expected_validate,
        )
        self.assertFalse(any("result" in name.lower() for name in contract.__all__))
        self.assertEqual(contract.COMPONENT_MANIFEST["result_input_count"], 0)
        self.assertEqual(
            contract.COMPONENT_MANIFEST["old_review_roster_assignment_result_receipt_inputs"],
            [],
        )
        precommit = _object(self.bundle["campaign_precommit"])
        self.assertEqual(precommit["component_manifest_sha256"], contract.COMPONENT_MANIFEST_SHA256)
        receipt = self.bundle["campaign_receipt"]
        self.assertEqual(
            precommit["prior_presented_result_import_policy"],
            "FORBIDDEN_NEW_CAMPAIGN_ONLY",
        )
        self.assertFalse(receipt["prior_presented_result_imported"])
        self.assertEqual(receipt["review_result_input_count"], 0)

    def test_guideline_is_exact_fixed_policy_and_has_no_instruction_override_api(self) -> None:
        self.assertEqual(
            set(inspect.signature(contract.build_review_guideline_bytes).parameters),
            {"campaign_id", "guideline_id", "guideline_version"},
        )
        with self.assertRaises(TypeError):
            contract.build_review_guideline_bytes(
                campaign_id=CAMP,
                guideline_id="malicious-guideline",
                guideline_version=1,
                instructions=["Infer target_work_id and peer results."],
            )
        guideline = _object(self.bundle["guideline"])
        self.assertEqual(
            guideline["instructions"], list(contract.REVIEW_GUIDELINE_INSTRUCTIONS)
        )
        self.assertTrue(any("아생갤" in item for item in guideline["instructions"]))
        changed = deepcopy(guideline)
        changed["instructions"][0] = "Infer a target work from every surface."
        changed = _reseal(changed, "artifact_sha256")
        with self.assertRaises(contract.P0PresentedDualBlindReviewCampaignPrecommitV1Error):
            self._build_precommit(self.bundle, review_guideline_raw=_file(changed))

    def test_response_canonical_gold_comparison_and_terminal_semantics_are_exact(self) -> None:
        response = _object(self.bundle["response"])
        profile = response["canonical_gold_set_comparison_profile"]
        self.assertEqual(
            profile["comparison_eligibility"],
            "BOTH_AUTHORITY_QUALIFIED_PRIMARIES_JUDGED_AND_FROZEN",
        )
        self.assertEqual(profile["duplicate_policy"], "REJECT")
        self.assertEqual(profile["empty_set_policy"], "VALID_JUDGED_COMPLETE_SET")
        self.assertEqual(profile["parser_observation_input_policy"], "FORBIDDEN")
        semantics = response["terminal_field_semantics"]
        self.assertEqual(semantics["UNAVAILABLE"]["presented_gold_spans"], "NULL")
        self.assertEqual(semantics["UNAVAILABLE"]["quality_arithmetic"], "NULL")
        self.assertEqual(semantics["UNJUDGED"]["presented_gold_spans"], "NULL")
        self.assertEqual(semantics["UNJUDGED"]["reviewed_at"], "NULL")
        attacks = []
        for path, value in (
            (("canonical_gold_set_comparison_profile", "ordering"), "INPUT_ORDER_SENSITIVE"),
            (("canonical_gold_set_comparison_profile", "duplicate_policy"), "ALLOW"),
            (("canonical_gold_set_comparison_profile", "parser_observation_input_policy"), "ALLOWED"),
            (("terminal_field_semantics", "UNAVAILABLE", "presented_gold_spans"), "EMPTY_LIST"),
            (("terminal_field_semantics", "UNJUDGED", "quality_arithmetic"), "ZERO"),
        ):
            changed = deepcopy(response)
            cursor = changed
            for key in path[:-1]:
                cursor = cursor[key]
            cursor[path[-1]] = value
            attacks.append(_file(_reseal(changed, "artifact_sha256")))
        for index, changed in enumerate(attacks):
            with self.subTest(attack=index), self.assertRaises(
                contract.P0PresentedDualBlindReviewCampaignPrecommitV1Error
            ):
                self._build_precommit(self.bundle, response_schema_raw=changed)

    def test_blind_tasks_are_minimal_sorted_projection_and_keep_asenggal_raw_only(self) -> None:
        tasks = _rows(self.bundle["tasks"])
        self.assertEqual(len(tasks), 120)
        self.assertEqual(
            [row["opaque_task_id"] for row in tasks],
            sorted(row["opaque_task_id"] for row in tasks),
        )
        allowed = set(contract.ARTIFACT_FIELDS["blind_task_row"])
        forbidden = {
            "input_sequence", "assignment_slot", "reviewer_id", "co_reviewer_id",
            "peer_opaque_task_id", "frame_candidate_id", "registry_record_id",
            "selected_input_sha256", "bridge_row_sha256", "parser_result_row_sha256",
            "parser_terminal_disposition", "emitted_observation_subjects_sha256",
            "emitted_observation_count", "target_work_id", "target_sense_id",
            "alias_relation", "nil_status",
        }
        self.assertTrue(all(set(row) == allowed for row in tasks))
        self.assertTrue(all(not forbidden.intersection(row) for row in tasks))
        payloads = [base64.b64decode(row["payload_base64"]) for row in tasks]
        self.assertTrue(any("아생갤" in raw.decode("utf-8", errors="ignore") for raw in payloads))
        serialized = self.bundle["tasks"].decode("utf-8")
        self.assertNotIn("target_work_id", serialized)
        self.assertNotIn("alias_relation", serialized)

    def test_blind_task_forbidden_field_peer_slot_and_input_leaks_fail(self) -> None:
        for field, value in (
            ("input_sequence", 1),
            ("assignment_slot", contract.PRIMARY_A),
            ("reviewer_id", "reviewer-opaque-1"),
            ("peer_opaque_task_id", "0" * 64),
            ("target_work_id", "work-attacker"),
        ):
            changed = _rows(self.bundle["tasks"])
            changed[0][field] = value
            with self.subTest(field=field), self.assertRaises(
                contract.P0PresentedDualBlindReviewCampaignPrecommitV1Error
            ):
                self._producer(
                    self.bundle,
                    reviewer_facing_task_inventory_raw=_jsonl(changed),
                )

    def test_opaque_id_duplicate_input_major_order_and_projection_tamper_fail(self) -> None:
        attacks: list[list[dict[str, object]]] = []
        duplicate = _rows(self.bundle["tasks"])
        duplicate[1]["opaque_task_id"] = duplicate[0]["opaque_task_id"]
        duplicate[1] = _reseal(
            duplicate[1], "blind_task_row_sha256", domain="P0_DUAL_BLIND_REVIEW_TASK_ROW_V1"
        )
        attacks.append(duplicate)
        input_major = sorted(
            _rows(self.bundle["tasks"]),
            key=lambda row: next(
                item["assignment_sequence"]
                for item in _rows(self.bundle["assignments"])
                if item["opaque_task_id"] == row["opaque_task_id"]
            ),
        )
        for index, row in enumerate(input_major, start=1):
            row["task_sequence"] = index
            input_major[index - 1] = _reseal(
                row, "blind_task_row_sha256", domain="P0_DUAL_BLIND_REVIEW_TASK_ROW_V1"
            )
        attacks.append(input_major)
        projection = _rows(self.bundle["tasks"])
        projection[0]["payload_sha256"] = "f" * 64
        projection[0] = _reseal(
            projection[0], "blind_task_row_sha256", domain="P0_DUAL_BLIND_REVIEW_TASK_ROW_V1"
        )
        attacks.append(projection)
        reordered = _rows(self.bundle["tasks"])
        reordered[0], reordered[1] = reordered[1], reordered[0]
        attacks.append(reordered)
        for index, changed in enumerate(attacks):
            with self.subTest(attack=index), self.assertRaises(
                contract.P0PresentedDualBlindReviewCampaignPrecommitV1Error
            ):
                self._producer(
                    self.bundle,
                    reviewer_facing_task_inventory_raw=_jsonl(changed),
                )

    def test_39_or_41_inputs_and_79_or_81_primaries_or_39_or_41_reserves_fail(self) -> None:
        unit_rows = _rows(self.bundle["units"])
        for changed in (unit_rows[:-1], [*unit_rows, deepcopy(unit_rows[-1])]):
            with self.subTest(kind="input", count=len(changed)), self.assertRaises(
                contract.P0PresentedDualBlindReviewCampaignPrecommitV1Error
            ):
                self._build_precommit(self.bundle, review_unit_inventory_raw=_jsonl(changed))
        assignments = _rows(self.bundle["assignments"])
        primary_indices = [
            index for index, row in enumerate(assignments)
            if row["assignment_slot"] in (contract.PRIMARY_A, contract.PRIMARY_B)
        ]
        reserve_indices = [
            index for index, row in enumerate(assignments)
            if row["assignment_slot"] == contract.DISAGREEMENT_ADJUDICATOR_RESERVE
        ]
        attacks = []
        for remove_at in (primary_indices[-1], reserve_indices[-1]):
            attacks.append(assignments[:remove_at] + assignments[remove_at + 1 :])
        for source_at in (primary_indices[-1], reserve_indices[-1]):
            attacks.append([*assignments, deepcopy(assignments[source_at])])
        for index, changed in enumerate(attacks):
            with self.subTest(kind="assignment-cardinality", attack=index), self.assertRaises(
                contract.P0PresentedDualBlindReviewCampaignPrecommitV1Error
            ):
                self._build_precommit(
                    self.bundle, assignment_inventory_raw=_jsonl(changed)
                )

    def test_total_120_slot_laundering_81_primary_39_reserve_and_inverse_fail(self) -> None:
        assignments = _rows(self.bundle["assignments"])
        for source_slot, replacement_slot, expected_primary, expected_reserve in (
            (
                contract.DISAGREEMENT_ADJUDICATOR_RESERVE,
                contract.PRIMARY_A,
                81,
                39,
            ),
            (contract.PRIMARY_B, contract.DISAGREEMENT_ADJUDICATOR_RESERVE, 79, 41),
        ):
            changed = deepcopy(assignments)
            target = next(
                index
                for index, row in enumerate(changed)
                if row["assignment_slot"] == source_slot
            )
            changed[target]["assignment_slot"] = replacement_slot
            changed[target] = _reseal(
                changed[target], "assignment_row_sha256",
                domain="P0_DUAL_BLIND_REVIEW_ASSIGNMENT_ROW_V1",
            )
            primary_count = sum(
                row["assignment_slot"] in (contract.PRIMARY_A, contract.PRIMARY_B)
                for row in changed
            )
            reserve_count = sum(
                row["assignment_slot"] == contract.DISAGREEMENT_ADJUDICATOR_RESERVE
                for row in changed
            )
            self.assertEqual((len(changed), primary_count, reserve_count), (120, expected_primary, expected_reserve))
            with self.subTest(primary=primary_count, reserve=reserve_count), self.assertRaises(
                contract.P0PresentedDualBlindReviewCampaignPrecommitV1Error
            ):
                self._build_precommit(
                    self.bundle, assignment_inventory_raw=_jsonl(changed)
                )

    def test_per_input_reviewer_key_fingerprint_principal_and_group_duplicates_fail(self) -> None:
        assignments = _rows(self.bundle["assignments"])
        for field in (
            "reviewer_id", "reviewer_pin_raw_sha256", "reviewer_key_id",
            "reviewer_public_key_fingerprint_sha256",
            "reviewer_principal_commitment_sha256", "reviewer_independence_group_id",
        ):
            changed = deepcopy(assignments)
            changed[1][field] = changed[0][field]
            changed[1] = _reseal(
                changed[1], "assignment_row_sha256",
                domain="P0_DUAL_BLIND_REVIEW_ASSIGNMENT_ROW_V1",
            )
            with self.subTest(field=field), self.assertRaises(
                contract.P0PresentedDualBlindReviewCampaignPrecommitV1Error
            ):
                self._build_precommit(
                    self.bundle, assignment_inventory_raw=_jsonl(changed)
                )

    def test_unhashable_actor_assignment_and_private_task_ids_use_contract_errors(self) -> None:
        assignment_rows = _rows(self.bundle["assignments"])
        reviewer_matrix = [
            [row["reviewer_id"] for row in assignment_rows[start : start + 3]]
            for start in range(0, 120, 3)
        ]
        opaque_matrix = [
            [row["opaque_task_id"] for row in assignment_rows[start : start + 3]]
            for start in range(0, 120, 3)
        ]
        actors = _rows(self.bundle["actors"])
        actors[3]["actor_id"] = []
        actors[3] = _reseal(
            actors[3], "actor_row_sha256", domain="P0_DUAL_BLIND_REVIEW_ACTOR_ROW_V1"
        )
        with self.assertRaises(contract.P0PresentedDualBlindReviewCampaignPrecommitV1Error):
            contract.build_assignment_inventory_bytes(
                campaign_id=CAMP,
                run_id=RUN,
                actor_roster_raw=_jsonl(actors),
                reviewer_ids_by_input=reviewer_matrix,
                opaque_task_ids_by_input=opaque_matrix,
            )
        assignments = deepcopy(assignment_rows)
        assignments[0]["reviewer_id"] = []
        assignments[0] = _reseal(
            assignments[0], "assignment_row_sha256",
            domain="P0_DUAL_BLIND_REVIEW_ASSIGNMENT_ROW_V1",
        )
        malformed_assignments = _jsonl(assignments)
        with self.assertRaises(contract.P0PresentedDualBlindReviewCampaignPrecommitV1Error):
            self._build_precommit(
                self.bundle, assignment_inventory_raw=malformed_assignments
            )
        with self.assertRaises(parent.P0PresentedDualBlindReviewCampaignPrecommitV1ParentError):
            self._parent(
                self.bundle, assignment_inventory_raw=malformed_assignments
            )
        private_rows = _rows(self.bundle["private_map"])
        private_rows[0]["opaque_task_id"] = []
        private_rows[0] = _reseal(
            private_rows[0], "private_map_row_sha256",
            domain="P0_DUAL_BLIND_REVIEW_PRIVATE_MAP_ROW_V1",
        )
        malformed_private = _jsonl(private_rows)
        with self.assertRaises(contract.P0PresentedDualBlindReviewCampaignPrecommitV1Error):
            self._build_precommit(
                self.bundle, evaluator_private_map_raw=malformed_private
            )
        with self.assertRaises(parent.P0PresentedDualBlindReviewCampaignPrecommitV1ParentError):
            self._parent(
                self.bundle, evaluator_private_map_raw=malformed_private
            )

    def test_global_key_principal_fingerprint_and_actor_id_duplicates_fail(self) -> None:
        base_pins = list(self.bundle["reviewer_pins"])
        duplicate_cases = (
            ("key", self._pin(4, signature_math.HUMAN_REVIEW_RESULT, key_id=_object(base_pins[0])["key_id"])),
            ("principal", self._pin(4, signature_math.HUMAN_REVIEW_RESULT, principal=_object(base_pins[0])["signer_principal_commitment_sha256"])),
            ("fingerprint", self._pin(4, signature_math.HUMAN_REVIEW_RESULT, signer_index=3)),
        )
        for label, duplicate_pin in duplicate_cases:
            reviewers = [
                {
                    "reviewer_id": f"fresh-reviewer-{index + 1}",
                    "identity_commitment_sha256": _object(pin)["signer_principal_commitment_sha256"],
                    "independence_group_id": f"fresh-group-{index + 1}",
                    "public_key_pin_raw": pin,
                }
                for index, pin in enumerate([base_pins[0], duplicate_pin, base_pins[2]])
            ]
            with self.subTest(label=label), self.assertRaises(
                contract.P0PresentedDualBlindReviewCampaignPrecommitV1Error
            ):
                contract.build_key_pin_inventory_and_actor_roster_bytes(
                    campaign_policy_pin_raw=self.bundle["policy_pin"],
                    campaign_policy_independence_group_id="policy-group",
                    review_lease_pin_raw=self.bundle["lease_pin"],
                    review_lease_independence_group_id="lease-group",
                    final_attestation_pin_raw=self.bundle["final_pin"],
                    final_attestation_independence_group_id="final-group",
                    reviewers=reviewers,
                )
        duplicated_id = _rows(self.bundle["actors"])
        duplicated_id[3]["actor_id"] = duplicated_id[0]["actor_id"]
        duplicated_id[3] = _reseal(
            duplicated_id[3], "actor_row_sha256", domain="P0_DUAL_BLIND_REVIEW_ACTOR_ROW_V1"
        )
        with self.assertRaises(contract.P0PresentedDualBlindReviewCampaignPrecommitV1Error):
            self._build_precommit(self.bundle, actor_roster_raw=_jsonl(duplicated_id))

    def test_singleton_kind_group_and_shared_authority_anchor_mismatches_fail(self) -> None:
        valid_reviewers = [
            {
                "reviewer_id": f"role-reviewer-{index}",
                "identity_commitment_sha256": _object(pin)["signer_principal_commitment_sha256"],
                "independence_group_id": f"role-human-group-{index}",
                "public_key_pin_raw": pin,
            }
            for index, pin in enumerate(self.bundle["reviewer_pins"])
        ]
        with self.assertRaises(contract.P0PresentedDualBlindReviewCampaignPrecommitV1Error):
            contract.build_key_pin_inventory_and_actor_roster_bytes(
                campaign_policy_pin_raw=self.bundle["lease_pin"],
                campaign_policy_independence_group_id="policy-group",
                review_lease_pin_raw=self.bundle["lease_pin"],
                review_lease_independence_group_id="lease-group",
                final_attestation_pin_raw=self.bundle["final_pin"],
                final_attestation_independence_group_id="final-group",
                reviewers=valid_reviewers,
            )
        for lease_group in ("policy-group", "human-group-1"):
            with self.subTest(group=lease_group), self.assertRaises(
                contract.P0PresentedDualBlindReviewCampaignPrecommitV1Error
            ):
                contract.build_key_pin_inventory_and_actor_roster_bytes(
                    campaign_policy_pin_raw=self.bundle["policy_pin"],
                    campaign_policy_independence_group_id="policy-group",
                    review_lease_pin_raw=self.bundle["lease_pin"],
                    review_lease_independence_group_id=lease_group,
                    final_attestation_pin_raw=self.bundle["final_pin"],
                    final_attestation_independence_group_id="final-group",
                    reviewers=[
                        {
                            "reviewer_id": f"reviewer-new-{index}",
                            "identity_commitment_sha256": _object(pin)["signer_principal_commitment_sha256"],
                            "independence_group_id": f"human-group-{index + 1}",
                            "public_key_pin_raw": pin,
                        }
                        for index, pin in enumerate(self.bundle["reviewer_pins"])
                    ],
                )
        bad_anchor_pin = self._pin(
            5, signature_math.HUMAN_REVIEW_RESULT,
            key_id="bad-anchor-reviewer-key",
            principal=contract.canonical_sha256("bad-anchor-reviewer-principal"),
            authority_anchor=contract.canonical_sha256("attacker-anchor"),
        )
        reviewers = [
            {
                "reviewer_id": f"anchor-reviewer-{index}",
                "identity_commitment_sha256": _object(pin)["signer_principal_commitment_sha256"],
                "independence_group_id": f"anchor-human-group-{index}",
                "public_key_pin_raw": pin,
            }
            for index, pin in enumerate(
                [self.bundle["reviewer_pins"][0], self.bundle["reviewer_pins"][1], bad_anchor_pin]
            )
        ]
        with self.assertRaises(contract.P0PresentedDualBlindReviewCampaignPrecommitV1Error):
            contract.build_key_pin_inventory_and_actor_roster_bytes(
                campaign_policy_pin_raw=self.bundle["policy_pin"],
                campaign_policy_independence_group_id="policy-group",
                review_lease_pin_raw=self.bundle["lease_pin"],
                review_lease_independence_group_id="lease-group",
                final_attestation_pin_raw=self.bundle["final_pin"],
                final_attestation_independence_group_id="final-group",
                reviewers=reviewers,
            )

    def test_pin_raw_and_actor_projection_tampering_fail(self) -> None:
        pin_lines = self.bundle["pin_inventory"].splitlines(keepends=True)
        pin = _object(pin_lines[3])
        pin["key_epoch"] = 2
        pin = _reseal(pin, "artifact_sha256")
        tampered_pins = b"".join([*pin_lines[:3], _file(pin), *pin_lines[4:]])
        with self.assertRaises(contract.P0PresentedDualBlindReviewCampaignPrecommitV1Error):
            self._build_precommit(self.bundle, key_pin_inventory_raw=tampered_pins)
        for field, value in (
            ("pin_raw_sha256", "e" * 64),
            ("key_id", "attacker-key"),
            ("declared_independence_group_id", "policy-group"),
        ):
            changed = _rows(self.bundle["actors"])
            changed[3][field] = value
            changed[3] = _reseal(
                changed[3], "actor_row_sha256", domain="P0_DUAL_BLIND_REVIEW_ACTOR_ROW_V1"
            )
            with self.subTest(field=field), self.assertRaises(
                contract.P0PresentedDualBlindReviewCampaignPrecommitV1Error
            ):
                self._build_precommit(self.bundle, actor_roster_raw=_jsonl(changed))

    def test_precommit_subject_signature_and_chronology_tampering_fail(self) -> None:
        for field, value in (
            ("primary_assignment_count", 79),
            ("component_manifest_sha256", "b" * 64),
            ("required_adjudication_denominator", 0),
            ("required_adjudication_denominator_derivation", "POST_HOC_OWNER_CHOICE"),
        ):
            precommit = _object(self.bundle["campaign_precommit"])
            precommit[field] = value
            precommit = _reseal(precommit, "artifact_sha256")
            with self.subTest(field=field), self.assertRaises(
                contract.P0PresentedDualBlindReviewCampaignPrecommitV1Error
            ):
                self._producer(self.bundle, campaign_precommit_raw=_file(precommit))
        subject = _object(self.bundle["policy_subject"])
        subject["payload_raw_sha256"] = "e" * 64
        subject = _reseal(subject, "artifact_sha256")
        with self.assertRaises(contract.P0PresentedDualBlindReviewCampaignPrecommitV1Error):
            self._producer(self.bundle, policy_signature_subject_raw=_file(subject))
        envelope = _object(self.bundle["policy_envelope"])
        signature = bytearray(base64.b64decode(envelope["signature_rs_base64"]))
        signature[0] ^= 1
        envelope["signature_rs_base64"] = base64.b64encode(signature).decode("ascii")
        envelope = _reseal(envelope, "artifact_sha256")
        with self.assertRaises(contract.P0PresentedDualBlindReviewCampaignPrecommitV1Error):
            self._producer(self.bundle, policy_signature_envelope_raw=_file(envelope))
        for assigned, precommitted in (
            ("2026-09-02T00:00:05Z", CAMPAIGN_PRECOMMITTED_AT),
            (ASSIGNMENT_SEALED_AT, ASSIGNMENT_SEALED_AT),
            (CAMPAIGN_PRECOMMITTED_AT, ASSIGNMENT_SEALED_AT),
        ):
            with self.subTest(assigned=assigned, precommitted=precommitted), self.assertRaises(
                contract.P0PresentedDualBlindReviewCampaignPrecommitV1Error
            ):
                self._build_precommit(
                    self.bundle,
                    presented_assignment_sealed_at=assigned,
                    presented_campaign_precommitted_at=precommitted,
                )

    def test_duplicate_nonfinite_trailing_and_oversize_artifacts_fail_closed(self) -> None:
        guideline = self.bundle["guideline"]
        duplicate = guideline.replace(
            b'{"', b'{"schema_version":"duplicate",', 1
        )
        nonfinite = guideline.replace(b'"guideline_version":1', b'"guideline_version":NaN')
        trailing = guideline + b"trailing"
        oversized = b'{' + b'"padding":"' + b"x" * (128 * 1024) + b'"}\n'
        for label, changed in (
            ("duplicate", duplicate), ("nonfinite", nonfinite),
            ("trailing", trailing), ("oversize", oversized),
        ):
            with self.subTest(label=label), self.assertRaises(
                contract.P0PresentedDualBlindReviewCampaignPrecommitV1Error
            ):
                self._build_precommit(self.bundle, review_guideline_raw=changed)
        precommit = self.bundle["campaign_precommit"]
        precommit_attacks = (
            precommit.replace(b'{"', b'{"schema_version":"duplicate",', 1),
            precommit.replace(b'"primary_assignment_count":80', b'"primary_assignment_count":NaN'),
            precommit + b"trailing",
            b'{"padding":"' + b"x" * (1024 * 1024) + b'"}\n',
        )
        for index, changed in enumerate(precommit_attacks):
            with self.subTest(precommit_attack=index), self.assertRaises(
                contract.P0PresentedDualBlindReviewCampaignPrecommitV1Error
            ):
                self._producer(self.bundle, campaign_precommit_raw=changed)

    def test_authority_actual_metric_and_nonjudged_reserve_invariants_stay_closed(self) -> None:
        receipt = self.bundle["campaign_receipt"]
        for field in (
            "external_key_provisioning_verified", "external_authority_anchor_verified",
            "reviewer_identity_verified", "reviewer_independence_factuality_verified",
            "reviewer_blinding_verified", "reviewer_dispatch_isolation_verified",
            "mapping_confidentiality_verified", "opaque_identifier_unpredictability_verified",
            "trusted_time_verified", "revocation_state_verified",
            "durable_replay_prevention_verified", "lease_signature_verified",
            "final_attestation_signature_verified", "actual_human_review_verified",
            "primary_result_inventory_verified", "all_80_primary_terminals_verified",
            "all_40_pairs_complete_verified", "disagreement_inventory_verified",
            "required_adjudication_complete_verified", "final_40_judged_verified",
            "metric_eligibility_verified", "descriptive_quality_metrics_allowed",
            "inferential_metrics_allowed", "complete_case_metrics_allowed",
            "semantic_metrics_allowed", "actual_authority_granted", "p0_phase_exit",
            "production_approval", "full_scan_approval",
        ):
            self.assertFalse(receipt[field], field)
        for field in (
            "actual_human_review_count", "actual_primary_review_event_count",
            "actual_pair_complete_input_count", "actual_adjudicated_input_count",
            "actual_judged_input_count", "actual_source_credit_count",
            "actual_context_credit_count",
        ):
            self.assertEqual(receipt[field], 0, field)
        precommit = _object(self.bundle["campaign_precommit"])
        protocol = precommit["review_protocol"]
        self.assertEqual(precommit["selected_input_itt_denominator"], 40)
        self.assertEqual(precommit["planned_primary_review_opportunity_denominator"], 80)
        self.assertEqual(precommit["primary_pair_input_denominator"], 40)
        self.assertEqual(precommit["maximum_reserve_adjudication_opportunity_denominator"], 40)
        self.assertEqual(precommit["planned_final_judged_input_denominator"], 40)
        self.assertIsNone(precommit["required_adjudication_denominator"])
        self.assertEqual(
            precommit["required_adjudication_denominator_derivation"],
            "AFTER_ALL_80_PRIMARY_TERMINALS_FROZEN_COUNT_BOTH_AUTHORITY_QUALIFIED_JUDGED_PAIRS_WITH_DIFFERENT_CANONICAL_FULL_GOLD_SETS",
        )
        self.assertEqual(
            protocol["reserve_activation_rule"],
            "BOTH_AUTHORITY_QUALIFIED_PRIMARIES_JUDGED_AND_CANONICAL_FULL_GOLD_SETS_DIFFER",
        )
        self.assertEqual(protocol["primary_nonjudged_substitution_policy"], "FORBIDDEN")
        self.assertEqual(
            protocol["pair_incomplete_disposition"],
            "INCOMPLETE_NO_FINAL_JUDGED_RESULT_PRIMARY_TERMINALS_RETAINED",
        )
        self.assertEqual(
            protocol["whole_inventory_reviewer_release_policy"],
            "FORBIDDEN_DISPATCH_ONE_TASK_AT_A_TIME",
        )
        self.assertEqual(receipt["statistical_denominator_contribution"], "NONE")
        self.assertEqual(receipt["metric_status"], contract.METRIC_STATUS)
        self.assertEqual(receipt["gate_status"], contract.GATE_STATUS)

    def test_parent_rejects_forged_authority_count_metric_and_stale_receipt(self) -> None:
        if parent is None:
            self.skipTest("independent parent validator has not landed yet")
        for field, value in (
            ("reviewer_identity_verified", True),
            ("actual_human_review_count", 40),
            ("actual_primary_review_event_count", 80),
            ("statistical_denominator_contribution", "PRIMARY_REVIEW_EVENT"),
            ("metric_status", "ESTIMABLE"),
        ):
            changed = deepcopy(self.bundle["campaign_receipt"])
            changed[field] = value
            changed = _reseal(changed, "receipt_sha256")
            with self.subTest(field=field), self.assertRaises(
                parent.P0PresentedDualBlindReviewCampaignPrecommitV1ParentError
            ):
                self._parent(self.bundle, component_receipt_raw=_file(changed))
        stale = deepcopy(self.bundle["campaign_receipt"])
        stale["campaign_precommit_raw_sha256"] = "d" * 64
        stale = _reseal(stale, "receipt_sha256")
        with self.assertRaises(parent.P0PresentedDualBlindReviewCampaignPrecommitV1ParentError):
            self._parent(self.bundle, component_receipt_raw=_file(stale))

    def test_parent_directly_rejects_assignment_task_and_precommit_policy_tampering(self) -> None:
        if parent is None:
            self.skipTest("independent parent validator has not landed yet")
        assignments = _rows(self.bundle["assignments"])
        assignments[2]["assignment_slot"] = contract.PRIMARY_A
        assignments[2] = _reseal(
            assignments[2], "assignment_row_sha256",
            domain="P0_DUAL_BLIND_REVIEW_ASSIGNMENT_ROW_V1",
        )
        with self.assertRaises(parent.P0PresentedDualBlindReviewCampaignPrecommitV1ParentError):
            self._parent(self.bundle, assignment_inventory_raw=_jsonl(assignments))
        tasks = _rows(self.bundle["tasks"])
        tasks[0]["payload_sha256"] = "c" * 64
        tasks[0] = _reseal(
            tasks[0], "blind_task_row_sha256",
            domain="P0_DUAL_BLIND_REVIEW_TASK_ROW_V1",
        )
        with self.assertRaises(parent.P0PresentedDualBlindReviewCampaignPrecommitV1ParentError):
            self._parent(self.bundle, reviewer_facing_task_inventory_raw=_jsonl(tasks))
        precommit = _object(self.bundle["campaign_precommit"])
        precommit["required_adjudication_denominator"] = 0
        precommit = _reseal(precommit, "artifact_sha256")
        with self.assertRaises(parent.P0PresentedDualBlindReviewCampaignPrecommitV1ParentError):
            self._parent(self.bundle, campaign_precommit_raw=_file(precommit))

    def test_production_module_has_no_private_signer_io_or_runtime_import(self) -> None:
        source = inspect.getsource(contract)
        tree = ast.parse(source)
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
        self.assertTrue(
            imported.isdisjoint(
                {"os", "pathlib", "subprocess", "socket", "requests", "httpx", "llm_runtime"}
            )
        )
        for forbidden in (
            "BCryptGenerateKeyPair", "BCryptSignHash", "private_key", "def sign",
            "open(", "Path(", "subprocess.", "socket.", "requests.", "httpx.",
        ):
            self.assertNotIn(forbidden, source)
        if parent is not None:
            parent_source = inspect.getsource(parent)
            parent_tree = ast.parse(parent_source)
            imports = {
                node.module or ""
                for node in ast.walk(parent_tree)
                if isinstance(node, ast.ImportFrom)
            }
            imports.update(
                alias.name
                for node in ast.walk(parent_tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            )
            self.assertFalse(
                any(
                    "p0_presented_dual_blind_review_campaign_precommit_v1_contract"
                    in name
                    for name in imports
                )
            )

    def test_manifest_effective_upstream_and_local_bounds_are_complete_and_match_parent(self) -> None:
        expected = {
            "max_object_bytes": 1024 * 1024,
            "max_guideline_bytes": 128 * 1024,
            "max_pin_line_bytes": 16 * 1024,
            "max_pin_inventory_bytes": 512 * 1024,
            "max_roster_bytes": 512 * 1024,
            "max_review_unit_bytes": 32 * 1024 * 1024,
            "max_upstream_bridge_bytes": 16 * 1024 * 1024,
            "max_upstream_result_bytes": 32 * 1024 * 1024,
            "max_upstream_unreviewed_bytes": 32 * 1024 * 1024,
            "max_assignment_bytes": 4 * 1024 * 1024,
            "max_private_map_bytes": 4 * 1024 * 1024,
            "max_blind_task_bytes": 4 * 1024 * 1024,
            "max_jsonl_line_bytes": 1024 * 1024,
            "max_instructions": 64,
            "max_instruction_chars": 2048,
            "max_text_chars": 4096,
        }
        self.assertEqual(contract.COMPONENT_MANIFEST["limits"], expected)
        self.assertEqual(
            contract.COMPONENT_MANIFEST_SHA256,
            parent.EXPECTED_COMPONENT_MANIFEST_SHA256,
        )
        parent_values = {
            "max_object_bytes": parent._MAX_OBJECT_BYTES,
            "max_guideline_bytes": parent._MAX_GUIDELINE_BYTES,
            "max_pin_line_bytes": parent._MAX_PIN_LINE_BYTES,
            "max_pin_inventory_bytes": parent._MAX_PIN_INVENTORY_BYTES,
            "max_roster_bytes": parent._MAX_ROSTER_BYTES,
            "max_review_unit_bytes": parent._MAX_REVIEW_UNIT_BYTES,
            "max_upstream_bridge_bytes": parent._MAX_UPSTREAM_BRIDGE_BYTES,
            "max_upstream_result_bytes": parent._MAX_UPSTREAM_RESULT_BYTES,
            "max_upstream_unreviewed_bytes": parent._MAX_UPSTREAM_UNREVIEWED_BYTES,
            "max_assignment_bytes": parent._MAX_ASSIGNMENT_BYTES,
            "max_private_map_bytes": parent._MAX_PRIVATE_MAP_BYTES,
            "max_blind_task_bytes": parent._MAX_BLIND_TASK_BYTES,
            "max_jsonl_line_bytes": parent._MAX_JSONL_LINE_BYTES,
            "max_instructions": parent._MAX_INSTRUCTIONS,
            "max_instruction_chars": parent._MAX_INSTRUCTION_CHARS,
            "max_text_chars": parent._MAX_TEXT_CHARS,
        }
        self.assertEqual(parent_values, expected)


if __name__ == "__main__":
    unittest.main()
