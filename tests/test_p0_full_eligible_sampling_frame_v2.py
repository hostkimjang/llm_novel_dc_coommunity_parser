from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_batch.grounding import (  # noqa: E402
    p0_full_eligible_sampling_frame_v2_contract as contract,
)
from llm_batch.grounding import (  # noqa: E402
    p0_full_eligible_sampling_frame_v2_parent_validator as parent,
)


PLATFORM = "fixture-platform"
UTC_DAY = "2026-09-01"
CREATED_AT = "2026-08-31T00:00:00Z"
CUTOFF = "2026-09-02T00:00:00Z"
FRAME_SEALED_AT = "2026-09-02T00:00:01Z"
OWNER_PRECOMMITTED_AT = "2026-09-02T00:00:02Z"
SEED_REVEALED_AT = "2026-09-02T00:00:03Z"
SELECTION_SEALED_AT = "2026-09-02T00:00:04Z"

ADAPTER_BY_PROFILE = {
    "OFFICIAL_STRUCTURED": "adapter-official",
    "COMMUNITY_STRUCTURED": "adapter-community",
    "MEDIA_OCR": "adapter-media",
    "GENERIC_FALLBACK": "adapter-generic",
}


def _sha(value: object) -> str:
    return contract.canonical_sha256(value)


def _object(raw: bytes) -> dict[str, object]:
    return json.loads(raw.decode("utf-8"))


def _file(value: object) -> bytes:
    return contract.canonical_file_bytes(value)


def _scope_raw() -> bytes:
    adapter_map = sorted(
        (
            {"adapter_id": adapter, "source_profile": profile}
            for profile, adapter in ADAPTER_BY_PROFILE.items()
        ),
        key=lambda item: item["adapter_id"],
    )
    strata = [
        {
            "source_profile": profile,
            "platform": PLATFORM,
            "utc_day": UTC_DAY,
            "quota": 10,
        }
        for profile in contract.SOURCE_PROFILES
    ]
    return contract.build_scope_bytes(
        {
            "schema_version": contract.SCOPE_SCHEMA,
            "record_origin": contract.EXAMPLE_ORIGIN,
            "scope_id": "fixture-full-frame-v2",
            "created_at": CREATED_AT,
            "frame_cutoff": CUTOFF,
            "adapter_profile_map": adapter_map,
            "strata": strata,
            "enumeration_policy_sha256": _sha("enumeration-policy-v2"),
            "eligibility_policy_sha256": _sha("eligibility-policy-v2"),
            "rights_policy_sha256": _sha("rights-policy-v2"),
            "strata_policy_sha256": _sha("strata-policy-v2"),
            "future_seed_spec_sha256": _sha(
                {"provider": "fixture-beacon", "future_round": 42}
            ),
            "expected_per_profile_quota": 10,
            "expected_total_quota": 40,
            "selection_algorithm": contract.SELECTION_ALGORITHM,
            "lineage_policy": contract.LINEAGE_POLICY,
            "labels_observed": False,
            "semantic_fields_used": False,
            "action_applied": False,
            "operational_effect": contract.OPERATIONAL_EFFECT,
        }
    )


def _candidate(profile: str, index: int) -> dict[str, object]:
    locator = _sha({"profile": profile, "candidate": index})
    return {
        "locator_commitment_sha256": locator,
        "adapter_id": ADAPTER_BY_PROFILE[profile],
        "platform": PLATFORM,
        "observed_at": "2026-09-01T12:00:00Z",
        "published_at": "2026-09-01T08:00:00Z",
        "lineage_root_locator_commitment_sha256": locator,
        "lineage_role": "ROOT",
        "presented_rights_policy_assessed": True,
        "presented_collection_allowed": True,
        "presented_takedown_status": "ACTIVE",
        "presented_adapter_contract_verified": True,
    }


def _candidates(per_profile: int = 12) -> list[dict[str, object]]:
    return [
        _candidate(profile, index)
        for profile in contract.SOURCE_PROFILES
        for index in range(per_profile)
    ]


def _seed_raw(scope_raw: bytes, census_raw: bytes, frame_raw: bytes) -> bytes:
    scope = contract.validate_scope_bytes(scope_raw)
    frame = contract.validate_frame_manifest_bytes(frame_raw, scope_raw, census_raw)
    return contract.build_seed_receipt_bytes(
        {
            "schema_version": contract.SEED_RECEIPT_SCHEMA,
            "record_origin": contract.EXAMPLE_ORIGIN,
            "seed_receipt_id": "fixture-seed-receipt-v2",
            "scope_sha256": scope["artifact_sha256"],
            "frame_manifest_sha256": frame["artifact_sha256"],
            "future_seed_spec_sha256": scope["future_seed_spec_sha256"],
            "revealed_seed_sha256": _sha("fixture-revealed-seed"),
            "frame_owner_precommit_sha256": _sha("presented-owner-precommit"),
            "frame_owner_precommitted_at": OWNER_PRECOMMITTED_AT,
            "revealed_at": SEED_REVEALED_AT,
            "owner_authority_verified": False,
            "seed_authority_verified": False,
            "action_applied": False,
            "operational_effect": contract.OPERATIONAL_EFFECT,
        },
        scope_raw,
        frame_raw,
        census_raw,
    )


def _bundle(
    *,
    candidates: list[dict[str, object]] | None = None,
    per_profile: int = 12,
) -> dict[str, bytes]:
    scope_raw = _scope_raw()
    census_raw = contract.build_census_bytes(
        scope_raw,
        _candidates(per_profile) if candidates is None else candidates,
    )
    frame_raw = contract.build_frame_manifest_bytes(
        scope_raw, census_raw, frame_sealed_at=FRAME_SEALED_AT
    )
    seed_raw = _seed_raw(scope_raw, census_raw, frame_raw)
    plan_raw = contract.build_sampling_plan_bytes(
        scope_raw,
        census_raw,
        frame_raw,
        seed_raw,
        selection_sealed_at=SELECTION_SEALED_AT,
    )
    return {
        "scope": scope_raw,
        "census": census_raw,
        "frame": frame_raw,
        "seed": seed_raw,
        "plan": plan_raw,
    }


def _census_objects(raw: bytes) -> list[dict[str, object]]:
    return [json.loads(line) for line in raw.decode("utf-8").splitlines()]


def _census_file(rows: list[dict[str, object]]) -> bytes:
    return b"".join(_file(row) for row in rows)


def _reseal(value: dict[str, object], field: str = "artifact_sha256") -> bytes:
    return _file(contract.with_self_hash(value, field))


class FullEligibleSamplingFrameV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.bundle = _bundle()

    def test_positive_exact_accounting_nominal_probability_and_parent_replay(self) -> None:
        frame = contract.validate_frame_manifest_bytes(
            self.bundle["frame"], self.bundle["scope"], self.bundle["census"]
        )
        plan = contract.validate_sampling_plan_bytes(
            self.bundle["plan"],
            self.bundle["scope"],
            self.bundle["census"],
            self.bundle["seed"],
            self.bundle["frame"],
        )
        self.assertEqual(frame["census_row_count"], 48)
        self.assertEqual(frame["eligible_candidate_count"], 48)
        self.assertEqual(plan["input_count"], 40)
        self.assertEqual(plan["eligible_surplus_count"], 8)
        self.assertEqual(
            plan["per_profile_counts"],
            {profile: 10 for profile in contract.SOURCE_PROFILES},
        )
        self.assertTrue(
            all(
                row["inclusion_probability_numerator"] == 5
                and row["inclusion_probability_denominator"] == 6
                for row in plan["selected_inputs"]
            )
        )
        receipt = parent.validate_frame_and_plan_against_raw_inputs(
            self.bundle["frame"],
            self.bundle["plan"],
            scope_raw=self.bundle["scope"],
            census_raw=self.bundle["census"],
            seed_receipt_raw=self.bundle["seed"],
        )
        self.assertTrue(receipt["parent_separate_implementation_frame_replay_verified"])
        self.assertEqual(receipt["selected_input_count"], 40)
        for field in (
            "same_process_isolation_verified",
            "core_code_identity_verified",
            "parent_code_identity_verified",
            "external_population_completeness_verified",
            "owner_authority_verified",
            "external_seed_provenance_verified",
            "runtime_execution_verified",
            "actual_source_evidence_verified",
            "actual_authority_granted",
            "p0_phase_exit",
            "production_approval",
            "full_scan_approval",
        ):
            self.assertIs(receipt[field], False, field)

    def test_candidate_input_order_does_not_change_canonical_census_or_plan(self) -> None:
        first = _bundle(candidates=_candidates())
        second = _bundle(candidates=list(reversed(_candidates())))
        self.assertEqual(first["census"], second["census"])
        self.assertEqual(first["frame"], second["frame"])
        self.assertEqual(first["plan"], second["plan"])

    def test_excluded_unknown_junk_does_not_rerandomize_eligible_selection(self) -> None:
        baseline = self.bundle
        unknown_locator = _sha("excluded-unknown-lineage")
        unknown = {
            **_candidate("COMMUNITY_STRUCTURED", 999),
            "locator_commitment_sha256": unknown_locator,
            "lineage_root_locator_commitment_sha256": unknown_locator,
            "lineage_role": "UNKNOWN",
            "presented_rights_policy_assessed": False,
            "presented_collection_allowed": False,
            "presented_adapter_contract_verified": False,
        }
        changed = _bundle(candidates=[*_candidates(), unknown])
        base_plan = _object(baseline["plan"])
        changed_plan = _object(changed["plan"])
        self.assertNotEqual(baseline["census"], changed["census"])
        self.assertNotEqual(baseline["frame"], changed["frame"])
        self.assertEqual(
            base_plan["selected_inputs"], changed_plan["selected_inputs"]
        )
        self.assertEqual(
            base_plan["selected_input_set_sha256"],
            changed_plan["selected_input_set_sha256"],
        )

    def test_scope_and_census_reject_noncanonical_raw_bytes(self) -> None:
        with self.assertRaises(contract.P0FullEligibleFrameV2Error):
            contract.validate_scope_bytes(self.bundle["scope"].rstrip(b"\n"))
        with self.assertRaises(contract.P0FullEligibleFrameV2Error):
            contract.validate_scope_bytes(b"\xef\xbb\xbf" + self.bundle["scope"])
        with self.assertRaises(contract.P0FullEligibleFrameV2Error):
            contract.validate_scope_bytes(self.bundle["scope"].replace(b"\n", b"\r\n"))
        duplicate = self.bundle["scope"].replace(
            b'"scope_id":"fixture-full-frame-v2"',
            b'"scope_id":"fixture-full-frame-v2","scope_id":"duplicate"',
        )
        with self.assertRaises(contract.P0FullEligibleFrameV2Error):
            contract.validate_scope_bytes(duplicate)
        with self.assertRaises(contract.P0FullEligibleFrameV2Error):
            contract.validate_census_bytes(
                self.bundle["census"] + b"\n", self.bundle["scope"]
            )

        escaped_surrogate = b'{"x":"\\ud800"}\n'
        with self.assertRaises(contract.P0FullEligibleFrameV2Error):
            contract.validate_scope_bytes(escaped_surrogate)
        with self.assertRaises(
            parent.P0FullEligibleSamplingFrameV2ParentValidationError
        ):
            parent.validate_frame_and_plan_against_raw_inputs(
                escaped_surrogate,
                escaped_surrogate,
                scope_raw=escaped_surrogate,
                census_raw=escaped_surrogate,
                seed_receipt_raw=escaped_surrogate,
            )

    def test_semantic_label_parser_and_asaenggal_fields_are_not_in_schema(self) -> None:
        forbidden = (
            "surface_text",
            "title",
            "alias",
            "아생갤",
            "gold_label",
            "target_work_id",
            "parser_disposition",
        )
        for field in forbidden:
            with self.subTest(field=field):
                candidate = _candidate("COMMUNITY_STRUCTURED", 500)
                candidate[field] = "injected"
                with self.assertRaises(contract.P0FullEligibleFrameV2Error):
                    contract.build_census_bytes(_scope_raw(), [candidate])

    def test_duplicate_locator_and_cross_profile_lineage_are_rejected(self) -> None:
        duplicate = _candidates()
        duplicate.append(deepcopy(duplicate[0]))
        with self.assertRaisesRegex(
            contract.P0FullEligibleFrameV2Error, "duplicate candidate"
        ):
            contract.build_census_bytes(_scope_raw(), duplicate)

        root = _candidate("OFFICIAL_STRUCTURED", 700)
        derivative = _candidate("COMMUNITY_STRUCTURED", 701)
        derivative["lineage_root_locator_commitment_sha256"] = root[
            "locator_commitment_sha256"
        ]
        derivative["lineage_role"] = "DERIVATIVE"
        with self.assertRaisesRegex(
            contract.P0FullEligibleFrameV2Error, "crosses derived profiles"
        ):
            contract.build_census_bytes(_scope_raw(), [root, derivative])

    def test_root_must_be_canonical_min_across_all_lineage_members(self) -> None:
        root = _candidate("OFFICIAL_STRUCTURED", 800)
        root["locator_commitment_sha256"] = "f" * 64
        root["lineage_root_locator_commitment_sha256"] = "f" * 64
        derivative = _candidate("OFFICIAL_STRUCTURED", 801)
        derivative["locator_commitment_sha256"] = "0" * 64
        derivative["lineage_root_locator_commitment_sha256"] = "f" * 64
        derivative["lineage_role"] = "DERIVATIVE"
        with self.assertRaisesRegex(
            contract.P0FullEligibleFrameV2Error, "canonical-min"
        ):
            contract.build_census_bytes(_scope_raw(), [root, derivative])

    def test_parent_rejects_fully_resealed_cross_stratum_lineage(self) -> None:
        scope_material = _object(_scope_raw())
        scope_material.pop("artifact_sha256")
        scope_material["strata"] = [
            {
                "source_profile": "OFFICIAL_STRUCTURED",
                "platform": PLATFORM,
                "utc_day": UTC_DAY,
                "quota": 5,
            },
            {
                "source_profile": "OFFICIAL_STRUCTURED",
                "platform": "fixture-platform-two",
                "utc_day": UTC_DAY,
                "quota": 5,
            },
            *[
                {
                    "source_profile": profile,
                    "platform": PLATFORM,
                    "utc_day": UTC_DAY,
                    "quota": 10,
                }
                for profile in contract.SOURCE_PROFILES[1:]
            ],
        ]
        scope = contract.build_scope_bytes(scope_material)
        first = _candidate("OFFICIAL_STRUCTURED", 910)
        second = _candidate("OFFICIAL_STRUCTURED", 911)
        second["platform"] = "fixture-platform-two"
        valid = contract.build_census_bytes(scope, [first, second])
        rows = _census_objects(valid)
        by_locator = {row["locator_commitment_sha256"]: row for row in rows}
        root = by_locator[first["locator_commitment_sha256"]]
        derivative = by_locator[second["locator_commitment_sha256"]]
        derivative["lineage_root_locator_commitment_sha256"] = root[
            "locator_commitment_sha256"
        ]
        derivative["lineage_group_id"] = contract.lineage_group_id_from_root(
            root["locator_commitment_sha256"]
        )
        derivative["lineage_role"] = "DERIVATIVE"
        derivative["eligibility_status"] = "EXCLUDED"
        derivative["exclusion_reason_codes"] = ["LINEAGE_DERIVATIVE"]
        for index, row in enumerate(sorted(rows, key=lambda item: item["candidate_id"]), 1):
            row["enumeration_sequence"] = index
            rows[index - 1] = contract.with_self_hash(row, "row_sha256")
        forged = _census_file(rows)
        with self.assertRaisesRegex(
            contract.P0FullEligibleFrameV2Error,
            "crosses fixed platform/UTC-day strata",
        ):
            contract.validate_census_bytes(forged, scope)
        with self.assertRaisesRegex(
            parent.P0FullEligibleSamplingFrameV2ParentValidationError,
            "crosses fixed platform/UTC-day strata",
        ):
            parent.validate_frame_and_plan_against_raw_inputs(
                self.bundle["frame"],
                self.bundle["plan"],
                scope_raw=scope,
                census_raw=forged,
                seed_receipt_raw=self.bundle["seed"],
            )

    def test_eligibility_flip_is_rejected_even_after_row_reseal(self) -> None:
        rows = _census_objects(self.bundle["census"])
        rows[0]["eligibility_status"] = "EXCLUDED"
        rows[0]["exclusion_reason_codes"] = ["COLLECTION_NOT_ALLOWED"]
        rows[0] = contract.with_self_hash(rows[0], "row_sha256")
        with self.assertRaisesRegex(
            contract.P0FullEligibleFrameV2Error, "recomputed"
        ):
            contract.validate_census_bytes(
                _census_file(rows), self.bundle["scope"]
            )

    def test_underfilled_fixed_stratum_cannot_spill_or_backfill(self) -> None:
        scope = _scope_raw()
        census = contract.build_census_bytes(scope, _candidates(per_profile=9))
        with self.assertRaisesRegex(contract.P0FullEligibleFrameV2Error, "underfill"):
            contract.build_frame_manifest_bytes(
                scope, census, frame_sealed_at=FRAME_SEALED_AT
            )

    def test_seed_and_selection_chronology_is_fail_closed(self) -> None:
        scope = self.bundle["scope"]
        census = self.bundle["census"]
        frame = self.bundle["frame"]
        material = _object(self.bundle["seed"])
        material.pop("artifact_sha256")
        material["frame_owner_precommitted_at"] = FRAME_SEALED_AT
        with self.assertRaisesRegex(contract.P0FullEligibleFrameV2Error, "chronology"):
            contract.build_seed_receipt_bytes(material, scope, frame, census)

        with self.assertRaisesRegex(
            contract.P0FullEligibleFrameV2Error, "strictly follow seed reveal"
        ):
            contract.build_sampling_plan_bytes(
                scope,
                census,
                frame,
                self.bundle["seed"],
                selection_sealed_at=SEED_REVEALED_AT,
            )

    def test_seed_scope_frame_and_future_event_spec_are_cross_bound(self) -> None:
        seed = _object(self.bundle["seed"])
        for field in (
            "scope_sha256",
            "frame_manifest_sha256",
            "future_seed_spec_sha256",
        ):
            with self.subTest(field=field):
                changed = deepcopy(seed)
                changed.pop("artifact_sha256")
                changed[field] = _sha({"tampered": field})
                with self.assertRaises(contract.P0FullEligibleFrameV2Error):
                    contract.build_seed_receipt_bytes(
                        changed,
                        self.bundle["scope"],
                        self.bundle["frame"],
                        self.bundle["census"],
                    )

    def test_omitted_eligible_row_cannot_reuse_sealed_frame_seed_or_plan(self) -> None:
        rows = _census_objects(self.bundle["census"])
        omitted = rows[1:]
        for sequence, row in enumerate(omitted, start=1):
            row["enumeration_sequence"] = sequence
            omitted[sequence - 1] = contract.with_self_hash(row, "row_sha256")
        census = _census_file(omitted)
        with self.assertRaises(
            parent.P0FullEligibleSamplingFrameV2ParentValidationError
        ):
            parent.validate_frame_and_plan_against_raw_inputs(
                self.bundle["frame"],
                self.bundle["plan"],
                scope_raw=self.bundle["scope"],
                census_raw=census,
                seed_receipt_raw=self.bundle["seed"],
            )

    def test_resealed_plan_reorder_replacement_and_scalar_type_attacks_fail(self) -> None:
        original = _object(self.bundle["plan"])
        mutations: list[dict[str, object]] = []

        reordered = deepcopy(original)
        reordered["selected_inputs"][0], reordered["selected_inputs"][1] = (
            reordered["selected_inputs"][1],
            reordered["selected_inputs"][0],
        )
        reordered["selected_input_set_sha256"] = _sha(reordered["selected_inputs"])
        mutations.append(reordered)

        duplicated = deepcopy(original)
        duplicated["selected_inputs"][1] = deepcopy(duplicated["selected_inputs"][0])
        duplicated["selected_inputs"][1]["input_sequence"] = 2
        duplicated["selected_input_set_sha256"] = _sha(duplicated["selected_inputs"])
        mutations.append(duplicated)

        bool_count = deepcopy(original)
        bool_count["selected_inputs"][0]["N_h"] = True
        bool_count["selected_input_set_sha256"] = _sha(bool_count["selected_inputs"])
        mutations.append(bool_count)

        float_count = deepcopy(original)
        float_count["selected_inputs"][0]["N_h"] = 12.0
        float_count["selected_input_set_sha256"] = _sha(float_count["selected_inputs"])
        mutations.append(float_count)

        for mutation in mutations:
            with self.subTest(kind=mutations.index(mutation)):
                raw = _reseal(mutation)
                with self.assertRaises(contract.P0FullEligibleFrameV2Error):
                    contract.validate_sampling_plan_bytes(
                        raw,
                        self.bundle["scope"],
                        self.bundle["census"],
                        self.bundle["seed"],
                        self.bundle["frame"],
                    )
                with self.assertRaises(
                    parent.P0FullEligibleSamplingFrameV2ParentValidationError
                ):
                    parent.validate_frame_and_plan_against_raw_inputs(
                        self.bundle["frame"],
                        raw,
                        scope_raw=self.bundle["scope"],
                        census_raw=self.bundle["census"],
                        seed_receipt_raw=self.bundle["seed"],
                    )

    def test_v1_schema_and_algorithm_cross_replay_are_rejected(self) -> None:
        scope = _object(self.bundle["scope"])
        scope["schema_version"] = "p0_actual_source_input_plan_v1"
        with self.assertRaises(contract.P0FullEligibleFrameV2Error):
            contract.validate_scope_bytes(_reseal(scope))

        scope = _object(self.bundle["scope"])
        scope["selection_algorithm"] = "SHA256_RANK_WITHIN_PROFILE_V1"
        with self.assertRaises(contract.P0FullEligibleFrameV2Error):
            contract.validate_scope_bytes(_reseal(scope))

    def test_parent_is_independent_from_producer_constants_and_helpers(self) -> None:
        with patch.object(contract, "RANK_DOMAIN", "tampered-rank-domain"), patch.object(
            contract, "COMPONENT_MANIFEST_SHA256", "0" * 64
        ):
            receipt = parent.validate_frame_and_plan_against_raw_inputs(
                self.bundle["frame"],
                self.bundle["plan"],
                scope_raw=self.bundle["scope"],
                census_raw=self.bundle["census"],
                seed_receipt_raw=self.bundle["seed"],
            )
        self.assertTrue(receipt["parent_separate_implementation_frame_replay_verified"])
        self.assertEqual(
            parent.EXPECTED_COMPONENT_MANIFEST_SHA256,
            "efed07649c14cc2af0b0916ef6e6a04b39ad0c9147b97daec74428521287111b",
        )

    def test_parent_source_does_not_import_producer_or_llm_batch(self) -> None:
        source = (
            ROOT
            / "src"
            / "llm_batch"
            / "grounding"
            / "p0_full_eligible_sampling_frame_v2_parent_validator.py"
        ).read_text(encoding="utf-8")
        executable = "\n".join(
            line for line in source.splitlines() if not line.lstrip().startswith('"""')
        )
        self.assertNotIn("from llm_batch", executable)
        self.assertNotIn("import llm_batch", executable)
        self.assertNotIn("import p0_full_eligible_sampling_frame_v2_contract", executable)

    def test_component_manifest_binds_behavior_and_keeps_authority_false(self) -> None:
        self.assertEqual(
            contract.COMPONENT_MANIFEST_SHA256,
            parent.EXPECTED_COMPONENT_MANIFEST_SHA256,
        )
        self.assertEqual(
            contract.COMPONENT_MANIFEST["selection_rank_input_fields"],
            [
                "domain",
                "derived_seed_sha256",
                "eligible_sampling_units_sha256",
                "stratum_id",
                "lineage_unit_sha256",
            ],
        )
        for field in contract.FALSE_AUTHORITY_FIELDS:
            self.assertIs(contract.COMPONENT_MANIFEST[field], False, field)


if __name__ == "__main__":
    unittest.main()
