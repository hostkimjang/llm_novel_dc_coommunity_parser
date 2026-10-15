from __future__ import annotations

from copy import deepcopy
import inspect
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_batch.grounding import p0_presented_a_context_full_frame_v1_contract as contract  # noqa: E402
from llm_batch.grounding import p0_presented_a_context_full_frame_v1_parent_validator as parent  # noqa: E402


PLATFORM = "fixture-platform"
DAY = "2026-09-01"
CREATED = "2026-08-31T00:00:00Z"
CUTOFF = "2026-09-02T00:00:00Z"
FRAME_SEALED = "2026-09-02T00:00:01Z"
PRECOMMITTED = "2026-09-02T00:00:02Z"
REVEALED = "2026-09-02T00:00:03Z"
SELECTED = "2026-09-02T00:00:04Z"
ADAPTERS = {
    profile: f"adapter-{index:02d}"
    for index, profile in enumerate(contract.SOURCE_PROFILES, start=1)
}


def _sha(value: object) -> str:
    return contract.canonical_sha256(value)


def _obj(raw: bytes) -> dict[str, object]:
    return json.loads(raw.decode("utf-8"))


def _file(value: object) -> bytes:
    return contract.canonical_file_bytes(value)


def _reseal(value: dict[str, object], field: str = "artifact_sha256") -> bytes:
    return _file(contract.with_self_hash(value, field))


def _scope_raw() -> bytes:
    return contract.build_scope_bytes({
        "schema_version": contract.SCOPE_SCHEMA,
        "record_origin": contract.EXAMPLE_ORIGIN,
        "scope_id": "fixture-a-context-frame-v1",
        "created_at": CREATED,
        "frame_cutoff": CUTOFF,
        "adapter_profile_map": sorted(
            ({"adapter_id": adapter, "source_profile": profile} for profile, adapter in ADAPTERS.items()),
            key=lambda row: row["adapter_id"],
        ),
        "strata": [
            {"source_profile": profile, "platform_scope": PLATFORM, "utc_day": DAY, "quota": 5}
            for profile in contract.SOURCE_PROFILES
        ],
        "upstream_source_sampling_plan_raw_sha256": _sha("source-plan"),
        "upstream_bridge_inventory_raw_sha256": _sha("bridge-inventory"),
        "context_enumeration_policy_sha256": _sha("context-enumeration-policy"),
        "eligibility_policy_sha256": _sha("eligibility-policy"),
        "rights_policy_sha256": _sha("rights-policy"),
        "strata_policy_sha256": _sha("strata-policy"),
        "future_seed_spec_sha256": _sha({"provider": "fixture", "round": 42}),
        "expected_per_profile_quota": 5,
        "expected_total_quota": 20,
        "selection_algorithm": contract.SELECTION_ALGORITHM,
        "labels_observed": False,
        "semantic_truth_fields_used": False,
        "annotation_started": False,
        "action_applied": False,
        "operational_effect": contract.OPERATIONAL_EFFECT,
    })


def _candidate(profile: str, index: int, *, eligible: bool = True) -> dict[str, object]:
    registry = f"REGISTRY:{profile}:{index:02d}"
    return {
        "upstream_frame_candidate_id": f"UPSTREAM:{profile}:{index:02d}",
        "registry_record_id": registry,
        "adapter_id": ADAPTERS[profile],
        "platform_scope": PLATFORM,
        "community_scope_commitment_sha256": _sha({"community": profile}),
        "content_fingerprint": _sha({"registry": registry, "content": "bytes"}),
        "payload_sha256": _sha({"registry": registry, "payload": "raw"}),
        "surface_start": index,
        "surface_end": index + 3,
        "surface_sha256": _sha({"registry": registry, "surface": "약어"}),
        "context_observed_at": "2026-09-01T12:00:00Z",
        "source_published_at": "2026-09-01T08:00:00Z",
        "capture_receipt_sha256": _sha({"registry": registry, "capture": 1}),
        "source_claim_set_sha256": _sha({"registry": registry, "claims": []}),
        "presented_rights_policy_assessed": eligible,
        "presented_collection_allowed": eligible,
        "presented_takedown_status": "ACTIVE" if eligible else "PENDING_REMOVAL",
        "presented_source_binding_verified": eligible,
    }


def _candidates(*, reverse: bool = False, underfill: bool = False) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for profile_index, profile in enumerate(contract.SOURCE_PROFILES):
        count = 4 if underfill and profile_index == 0 else (5 if profile_index == 0 else 6)
        rows.extend(_candidate(profile, index) for index in range(count))
    if not underfill:
        rows.append(_candidate(contract.SOURCE_PROFILES[0], 99, eligible=False))
    return list(reversed(rows)) if reverse else rows


def _bundle(*, candidates: list[dict[str, object]] | None = None) -> dict[str, bytes]:
    scope = _scope_raw()
    census = contract.build_census_bytes(scope, _candidates() if candidates is None else candidates)
    frame = contract.build_frame_manifest_bytes(scope, census, frame_sealed_at=FRAME_SEALED)
    scope_value = contract.validate_scope_bytes(scope)
    frame_value = contract.validate_frame_manifest_bytes(frame, scope, census)
    seed = contract.build_seed_receipt_bytes({
        "schema_version": contract.SEED_RECEIPT_SCHEMA,
        "record_origin": contract.EXAMPLE_ORIGIN,
        "seed_receipt_id": "fixture-a-seed-v1",
        "scope_sha256": scope_value["artifact_sha256"],
        "frame_manifest_sha256": frame_value["artifact_sha256"],
        "census_raw_sha256": contract.raw_sha256(census),
        "future_seed_spec_sha256": scope_value["future_seed_spec_sha256"],
        "revealed_seed_sha256": _sha("revealed-seed"),
        "frame_owner_precommit_sha256": _sha("presented-owner-precommit"),
        "frame_owner_precommitted_at": PRECOMMITTED,
        "revealed_at": REVEALED,
        "owner_authority_verified": False,
        "seed_authority_verified": False,
        "action_applied": False,
        "operational_effect": contract.OPERATIONAL_EFFECT,
    }, scope, frame, census)
    plan = contract.build_sampling_plan_bytes(
        scope, census, frame, seed, selection_sealed_at=SELECTED
    )
    return {"scope": scope, "census": census, "frame": frame, "seed": seed, "plan": plan}


class PresentedAContextFullFrameV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.bundle = _bundle()

    def _parent(self, bundle: dict[str, bytes] | None = None) -> dict[str, object]:
        b = self.bundle if bundle is None else bundle
        return parent.validate_a_context_frame_and_plan_against_raw_inputs(
            b["frame"], b["plan"], scope_raw=b["scope"],
            census_raw=b["census"], seed_receipt_raw=b["seed"],
        )

    def test_positive_selected20_surplus3_excluded1_and_independent_parent(self) -> None:
        frame = contract.validate_frame_manifest_bytes(
            self.bundle["frame"], self.bundle["scope"], self.bundle["census"]
        )
        plan = contract.validate_sampling_plan_bytes(
            self.bundle["plan"], self.bundle["scope"], self.bundle["census"],
            self.bundle["seed"], self.bundle["frame"],
        )
        receipt = self._parent()
        self.assertEqual((frame["eligible_candidate_count"], frame["excluded_candidate_count"]), (23, 1))
        self.assertEqual((plan["input_count"], plan["eligible_surplus_count"]), (20, 3))
        self.assertEqual({row["source_profile"]: 5 for row in plan["selected_contexts"]}, {profile: 5 for profile in contract.SOURCE_PROFILES})
        self.assertTrue(receipt["selected_surplus_exact_partition_verified"])
        self.assertTrue(receipt["parent_separate_implementation_frame_replay_verified"])

    def test_selected_opportunity_is_never_actual_review_or_metric_denominator(self) -> None:
        plan = contract.validate_sampling_plan_bytes(
            self.bundle["plan"], self.bundle["scope"], self.bundle["census"], self.bundle["seed"], self.bundle["frame"]
        )
        receipt = self._parent()
        for row in (plan, receipt):
            self.assertEqual(row["actual_a_context_review_count"], 0)
            self.assertEqual(row["actual_surplus_review_count"], 0)
            self.assertEqual(row["statistical_denominator_contribution"], "NONE")
            self.assertEqual(row["metric_status"], contract.METRIC_STATUS)
            self.assertFalse(row["inferential_metrics_allowed"])
            self.assertFalse(row["complete_case_metrics_allowed"])
        for field in contract.FALSE_AUTHORITY_FIELDS:
            self.assertIs(plan[field], False, field)

    def test_candidate_input_order_is_irrelevant(self) -> None:
        first = _bundle(candidates=_candidates())
        second = _bundle(candidates=_candidates(reverse=True))
        self.assertEqual(first["census"], second["census"])
        self.assertEqual(first["frame"], second["frame"])
        self.assertEqual(first["plan"], second["plan"])

    def test_duplicate_logical_unit_is_rejected(self) -> None:
        rows = _candidates()
        rows.append(deepcopy(rows[0]))
        with self.assertRaisesRegex(contract.P0PresentedAContextFrameError, "duplicate logical"):
            contract.build_census_bytes(_scope_raw(), rows)

    def test_registry_record_is_part_of_immutable_context_unit(self) -> None:
        left = _candidate(contract.SOURCE_PROFILES[0], 0)
        right = deepcopy(left)
        right["registry_record_id"] = "REGISTRY:OTHER:00"
        self.assertNotEqual(contract.context_unit_sha256(left), contract.context_unit_sha256(right))

    def test_truth_label_and_result_fields_are_forbidden_prelabel(self) -> None:
        for field, value in (
            ("truth_kind", "WORK_ID"), ("truth_work_id", "WORK:1"),
            ("annotation_status", "JUDGED"), ("candidate_work_ids", ["WORK:1"]),
        ):
            row = _candidate(contract.SOURCE_PROFILES[0], 0)
            row[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(contract.P0PresentedAContextFrameError, "fields mismatch"):
                contract.build_census_bytes(_scope_raw(), [row])

    def test_underfill_never_spills_from_another_profile(self) -> None:
        scope = _scope_raw()
        census = contract.build_census_bytes(scope, _candidates(underfill=True))
        frame = contract.build_frame_manifest_bytes(scope, census, frame_sealed_at=FRAME_SEALED)
        frame_value = contract.validate_frame_manifest_bytes(frame, scope, census)
        scope_value = contract.validate_scope_bytes(scope)
        seed = contract.build_seed_receipt_bytes({
            "schema_version": contract.SEED_RECEIPT_SCHEMA, "record_origin": contract.EXAMPLE_ORIGIN,
            "seed_receipt_id": "underfill-seed", "scope_sha256": scope_value["artifact_sha256"],
            "frame_manifest_sha256": frame_value["artifact_sha256"], "census_raw_sha256": contract.raw_sha256(census),
            "future_seed_spec_sha256": scope_value["future_seed_spec_sha256"], "revealed_seed_sha256": _sha("seed"),
            "frame_owner_precommit_sha256": _sha("precommit"), "frame_owner_precommitted_at": PRECOMMITTED,
            "revealed_at": REVEALED, "owner_authority_verified": False, "seed_authority_verified": False,
            "action_applied": False, "operational_effect": contract.OPERATIONAL_EFFECT,
        }, scope, frame, census)
        with self.assertRaisesRegex(contract.P0PresentedAContextFrameError, "underfill"):
            contract.build_sampling_plan_bytes(scope, census, frame, seed, selection_sealed_at=SELECTED)

    def test_frame_count_bool_reseal_is_rejected_by_both_implementations(self) -> None:
        frame = _obj(self.bundle["frame"])
        frame["excluded_candidate_count"] = True
        attacked = _reseal(frame)
        with self.assertRaises(contract.P0PresentedAContextFrameError):
            contract.validate_frame_manifest_bytes(attacked, self.bundle["scope"], self.bundle["census"])
        attacked_bundle = {**self.bundle, "frame": attacked}
        with self.assertRaises(parent.P0PresentedAContextFrameParentError):
            self._parent(attacked_bundle)

    def test_census_sequence_bool_reseal_is_rejected_by_both_implementations(self) -> None:
        rows = [json.loads(line) for line in self.bundle["census"].decode("utf-8").splitlines()]
        rows[0]["enumeration_sequence"] = True
        rows[0] = contract.with_self_hash(rows[0], "row_sha256")
        attacked = b"".join(_file(row) for row in rows)
        with self.assertRaises(contract.P0PresentedAContextFrameError):
            contract.validate_census_bytes(attacked, self.bundle["scope"])
        with self.assertRaises(parent.P0PresentedAContextFrameParentError):
            self._parent({**self.bundle, "census": attacked})

    def test_plan_item_bool_int_reseal_attacks_are_rejected(self) -> None:
        for field in ("input_sequence", "inclusion_probability_numerator", "inclusion_probability_denominator"):
            plan = _obj(self.bundle["plan"])
            plan["selected_contexts"][0][field] = True
            plan["selected_context_set_sha256"] = _sha(plan["selected_contexts"])
            attacked = _reseal(plan)
            with self.subTest(field=field), self.assertRaises(contract.P0PresentedAContextFrameError):
                contract.validate_sampling_plan_bytes(attacked, self.bundle["scope"], self.bundle["census"], self.bundle["seed"], self.bundle["frame"])
            with self.subTest(parent_field=field), self.assertRaises(parent.P0PresentedAContextFrameParentError):
                self._parent({**self.bundle, "plan": attacked})

    def test_plan_top_level_bool_int_reseal_attacks_are_rejected(self) -> None:
        attacks = (
            ("without_replacement", 1),
            ("spill_allowed", 0),
            ("replacement_allowed", 0),
            ("input_count", True),
            ("eligible_surplus_count", True),
        )
        for field, value in attacks:
            plan = _obj(self.bundle["plan"])
            plan[field] = value
            attacked = _reseal(plan)
            with self.subTest(field=field), self.assertRaises(contract.P0PresentedAContextFrameError):
                contract.validate_sampling_plan_bytes(attacked, self.bundle["scope"], self.bundle["census"], self.bundle["seed"], self.bundle["frame"])
            with self.subTest(parent_field=field), self.assertRaises(parent.P0PresentedAContextFrameParentError):
                self._parent({**self.bundle, "plan": attacked})

    def test_scope_quota_float_reseal_attacks_are_rejected_by_both_implementations(self) -> None:
        for field, value in (
            ("expected_per_profile_quota", 5.0),
            ("expected_total_quota", 20.0),
        ):
            scope = _obj(self.bundle["scope"])
            scope[field] = value
            attacked = _reseal(scope)
            with self.subTest(field=field), self.assertRaises(contract.P0PresentedAContextFrameError):
                contract.validate_scope_bytes(attacked)
            with self.subTest(parent_field=field), self.assertRaises(parent.P0PresentedAContextFrameParentError):
                self._parent({**self.bundle, "scope": attacked})

    def test_partition_and_metric_promotion_tamper_fail_closed(self) -> None:
        for mutate in (
            lambda row: row["eligible_surplus_contexts"].pop(),
            lambda row: row.__setitem__("actual_a_context_review_count", 20),
            lambda row: row.__setitem__("inferential_metrics_allowed", True),
        ):
            plan = _obj(self.bundle["plan"])
            mutate(plan)
            if "eligible_surplus_contexts" in plan:
                plan["eligible_surplus_set_sha256"] = _sha(plan["eligible_surplus_contexts"])
                plan["eligible_surplus_count"] = len(plan["eligible_surplus_contexts"])
            attacked = _reseal(plan)
            with self.assertRaises(contract.P0PresentedAContextFrameError):
                contract.validate_sampling_plan_bytes(attacked, self.bundle["scope"], self.bundle["census"], self.bundle["seed"], self.bundle["frame"])

    def test_raw_predecessor_cross_bindings_reject_delete_seed_swap_and_registry_change(self) -> None:
        # (a) A fully resealed/resequenced census deletion cannot reuse old frame/seed/plan.
        census_rows = [json.loads(line) for line in self.bundle["census"].decode("utf-8").splitlines()]
        removed_index = next(index for index, row in enumerate(census_rows) if row["eligibility_status"] == "ELIGIBLE")
        census_rows.pop(removed_index)
        deleted = b"".join(
            _file(contract.with_self_hash({**row, "enumeration_sequence": index}, "row_sha256"))
            for index, row in enumerate(census_rows, start=1)
        )
        with self.assertRaises(contract.P0PresentedAContextFrameError):
            contract.validate_frame_manifest_bytes(self.bundle["frame"], self.bundle["scope"], deleted)
        with self.assertRaises(parent.P0PresentedAContextFrameParentError):
            self._parent({**self.bundle, "census": deleted})

        # (b) A plan generated from a different revealed seed cannot be swapped in.
        seed_value = _obj(self.bundle["seed"])
        seed_value["revealed_seed_sha256"] = _sha("different-seed")
        other_seed = _reseal(seed_value)
        other_plan = contract.build_sampling_plan_bytes(
            self.bundle["scope"], self.bundle["census"], self.bundle["frame"],
            other_seed, selection_sealed_at=SELECTED,
        )
        with self.assertRaises(contract.P0PresentedAContextFrameError):
            contract.validate_sampling_plan_bytes(
                other_plan, self.bundle["scope"], self.bundle["census"],
                self.bundle["seed"], self.bundle["frame"],
            )
        with self.assertRaises(parent.P0PresentedAContextFrameParentError):
            self._parent({**self.bundle, "plan": other_plan})

        # (c) A changed immutable registry binding creates a new unit and invalidates old frame.
        candidates = _candidates()
        candidates[0] = {**candidates[0], "registry_record_id": "REGISTRY:REBOUND:00"}
        rebound = contract.build_census_bytes(self.bundle["scope"], candidates)
        with self.assertRaises(contract.P0PresentedAContextFrameError):
            contract.validate_frame_manifest_bytes(self.bundle["frame"], self.bundle["scope"], rebound)
        with self.assertRaises(parent.P0PresentedAContextFrameParentError):
            self._parent({**self.bundle, "census": rebound})

    def test_seed_and_selection_chronology_are_strict(self) -> None:
        seed = _obj(self.bundle["seed"])
        seed["revealed_at"] = seed["frame_owner_precommitted_at"]
        with self.assertRaisesRegex(contract.P0PresentedAContextFrameError, "chronology"):
            contract.validate_seed_receipt_bytes(_reseal(seed), self.bundle["scope"], self.bundle["frame"], self.bundle["census"])
        plan = _obj(self.bundle["plan"])
        plan["selection_sealed_at"] = REVEALED
        with self.assertRaisesRegex(contract.P0PresentedAContextFrameError, "chronology"):
            contract.validate_sampling_plan_bytes(_reseal(plan), self.bundle["scope"], self.bundle["census"], self.bundle["seed"], self.bundle["frame"])

    def test_deep_json_and_noncanonical_framing_normalize_to_component_error(self) -> None:
        deep = b'{"x":' + (b"[" * 5000) + b"0" + (b"]" * 5000) + b"}\n"
        huge_int = b'{"x":' + (b"9" * 10000) + b"}\n"
        oversized = b"{" + (b" " * 1_000_000) + b"}\n"
        for bad in (
            deep, huge_int, oversized, b"\xef\xbb\xbf{}\n", b"{}\r\n", b'{"x":NaN}\n'
        ):
            with self.subTest(prefix=bad[:12]), self.assertRaises(contract.P0PresentedAContextFrameError):
                contract.validate_scope_bytes(bad)
            with self.subTest(parent_prefix=bad[:12]), self.assertRaises(parent.P0PresentedAContextFrameParentError):
                parent.validate_a_context_frame_and_plan_against_raw_inputs(
                    self.bundle["frame"], self.bundle["plan"], scope_raw=bad,
                    census_raw=self.bundle["census"], seed_receipt_raw=self.bundle["seed"],
                )

    def test_oversized_frame_is_rejected_by_both_implementations(self) -> None:
        oversized_frame = b"{" + (b" " * 1_000_000) + b"}\n"
        with self.assertRaises(contract.P0PresentedAContextFrameError):
            contract.validate_frame_manifest_bytes(
                oversized_frame, self.bundle["scope"], self.bundle["census"]
            )
        with self.assertRaises(parent.P0PresentedAContextFrameParentError):
            self._parent({**self.bundle, "frame": oversized_frame})

    def test_census_builder_enforces_cumulative_budget_before_late_validation(self) -> None:
        expected = self.bundle["census"]
        with patch.object(contract, "MAX_CENSUS_BYTES", len(expected)):
            self.assertEqual(
                contract.build_census_bytes(self.bundle["scope"], _candidates()),
                expected,
            )
        with (
            patch.object(contract, "MAX_CENSUS_BYTES", len(expected) - 1),
            patch.object(
                contract,
                "validate_census_bytes",
                side_effect=AssertionError("late validator must not run"),
            ) as late_validator,
        ):
            with self.assertRaisesRegex(
                contract.P0PresentedAContextFrameError,
                "cumulative byte budget",
            ):
                contract.build_census_bytes(self.bundle["scope"], _candidates())
        late_validator.assert_not_called()

    def test_census_parsers_stop_at_row_budget_and_do_not_call_splitlines(self) -> None:
        row = _file(_obj(self.bundle["census"].splitlines(keepends=True)[0]))
        two_rows = row + row
        for module, error_type in (
            (contract, contract.P0PresentedAContextFrameError),
            (parent, parent.P0PresentedAContextFrameParentError),
        ):
            original = module._object
            with (
                self.subTest(module=module.__name__),
                patch.object(module, "MAX_CENSUS_ROWS", 1),
                patch.object(module, "_object", wraps=original) as parser,
            ):
                with self.assertRaises(error_type):
                    module._jsonl(two_rows)
                self.assertEqual(parser.call_count, 1)
            self.assertNotIn("splitlines", inspect.getsource(module._jsonl))

    def test_census_parsers_reject_first_bad_shape_and_oversized_row_immediately(self) -> None:
        malformed_many = b"{}\n" * 1_000
        oversized_row = b"{" + (b" " * contract.MAX_CENSUS_ROW_BYTES) + b"}\n"
        for module, error_type in (
            (contract, contract.P0PresentedAContextFrameError),
            (parent, parent.P0PresentedAContextFrameParentError),
        ):
            original = module._object
            with (
                self.subTest(module=module.__name__, case="shape"),
                patch.object(module, "_object", wraps=original) as parser,
            ):
                with self.assertRaisesRegex(error_type, "fields mismatch"):
                    module._jsonl(malformed_many)
                self.assertEqual(parser.call_count, 1)
            with (
                self.subTest(module=module.__name__, case="row-size"),
                patch.object(module, "_object", wraps=original) as parser,
            ):
                with self.assertRaises(error_type):
                    module._jsonl(oversized_row)
                parser.assert_not_called()

    def test_census_builder_checks_row_budget_inside_candidate_iteration(self) -> None:
        class MisreportingSequence(list):
            def __len__(self) -> int:
                return 1

        with patch.object(contract, "MAX_CENSUS_ROWS", 1):
            with self.assertRaisesRegex(
                contract.P0PresentedAContextFrameError,
                "row budget",
            ):
                contract.build_census_bytes(
                    self.bundle["scope"],
                    MisreportingSequence(
                        [
                            _candidate(contract.SOURCE_PROFILES[0], 0),
                            _candidate(contract.SOURCE_PROFILES[1], 1),
                        ]
                    ),
                )

    def test_census_builder_conservative_budget_stops_candidate_preparation(self) -> None:
        candidates = _candidates()
        with (
            patch.object(contract, "MAX_CENSUS_BYTES", 1),
            patch.object(contract, "_base_candidate", wraps=contract._base_candidate) as prepare,
        ):
            with self.assertRaisesRegex(
                contract.P0PresentedAContextFrameError,
                "conservative cumulative byte budget",
            ):
                contract.build_census_bytes(self.bundle["scope"], candidates)
        self.assertEqual(prepare.call_count, 1)

    def test_parent_census_byte_budget_is_exact_and_fail_closed(self) -> None:
        census = self.bundle["census"]
        with patch.object(parent, "MAX_CENSUS_BYTES", len(census)):
            self.assertEqual(self._parent()["census_row_count"], 24)
        with patch.object(parent, "MAX_CENSUS_BYTES", len(census) - 1):
            with self.assertRaisesRegex(
                parent.P0PresentedAContextFrameParentError,
                "census framing",
            ):
                self._parent()

    def test_parent_replay_does_not_call_monkeypatched_producer(self) -> None:
        with patch.object(contract, "canonical_sha256", return_value="0" * 64), patch.object(
            contract, "validate_sampling_plan_bytes", side_effect=AssertionError("producer called")
        ):
            receipt = self._parent()
        self.assertTrue(receipt["parent_separate_implementation_frame_replay_verified"])


if __name__ == "__main__":
    unittest.main()
