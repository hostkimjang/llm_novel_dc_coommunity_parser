"""A-context lineage-capped full frame V2의 표본·계보 회귀 테스트."""

from __future__ import annotations

import base64
from copy import deepcopy
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch

from llm_batch.grounding import p0_presented_a_context_full_frame_v1_contract as a_frame_v1
from llm_batch.grounding import (
    p0_presented_a_context_lineage_capped_full_frame_v2_contract as contract,
)
from llm_batch.grounding import (
    p0_presented_a_context_lineage_capped_full_frame_v2_parent_validator as parent,
)
from tests import test_p0_presented_a_context_annotation_subject_v2_precommit as subject_fixture


LINEAGE_FRAME_SEALED_AT = "2026-09-02T00:00:11Z"
LINEAGE_OWNER_PRECOMMITTED_AT = "2026-09-02T00:00:12Z"
LINEAGE_SEED_REVEALED_AT = "2026-09-02T00:00:13Z"
SELECTION_SEALED_AT = "2026-09-02T00:00:14Z"


def _obj(raw: bytes) -> dict[str, object]:
    return json.loads(raw.decode("utf-8"))


def _rows(raw: bytes) -> list[dict[str, object]]:
    return [json.loads(line) for line in raw.decode("utf-8").splitlines()]


def _file(value: object) -> bytes:
    return contract.canonical_file_bytes(value)


def _reseal(value: dict[str, object], field: str = "artifact_sha256") -> bytes:
    material = {key: item for key, item in value.items() if key != field}
    return _file({**material, field: contract.canonical_sha256(material)})


def _all_raw_kwargs(bundle: dict[str, bytes]) -> dict[str, bytes]:
    """V2가 독립 재생해야 하는 source/bridge/A predecessor 원문을 모은다."""

    return {
        "source_scope_raw": bundle["source_scope"],
        "source_census_raw": bundle["source_census"],
        "source_frame_raw": bundle["source_frame"],
        "source_seed_raw": bundle["source_seed"],
        "source_plan_raw": bundle["source_plan"],
        "bridge_inventory_raw": bundle["bridge_inventory"],
        "a_scope_raw": bundle["a_scope"],
        "a_census_raw": bundle["a_census"],
        "a_frame_raw": bundle["a_frame"],
        "a_seed_raw": bundle["a_seed"],
        "a_plan_raw": bundle["a_plan"],
    }


def _preseed_raw_kwargs(bundle: dict[str, bytes]) -> dict[str, bytes]:
    """seed reveal 전에 허용되는 source 5개·bridge·A 3개 원문만 돌려준다."""

    all_raw = _all_raw_kwargs(bundle)
    return {key: all_raw[key] for key in contract.PRESEED_RAW_KEYS}


def _variant(
    candidate: dict[str, object], bridge_row: dict[str, object], offset: int
) -> dict[str, object]:
    """같은 source lineage에 속하면서 span만 다른 A-context를 만든다."""

    payload = base64.b64decode(bridge_row["payload_base64"]).decode("utf-8")  # type: ignore[arg-type]
    if offset < 0 or offset >= len(payload):
        raise AssertionError("fixture span offset must leave a nonempty context")
    result = deepcopy(candidate)
    result["surface_start"] = offset
    result["surface_end"] = len(payload)
    result["surface_sha256"] = a_frame_v1.canonical_sha256(payload[offset:])
    return result


def _rebuild_a_predecessor(
    base: dict[str, bytes], candidates: list[dict[str, object]]
) -> dict[str, bytes]:
    """subject-v2 source/bridge를 보존하고 A-frame V1 다섯 원문만 다시 봉인한다."""

    a_scope = base["a_scope"]
    a_census = a_frame_v1.build_census_bytes(a_scope, candidates)
    a_frame = a_frame_v1.build_frame_manifest_bytes(
        a_scope,
        a_census,
        frame_sealed_at=subject_fixture.A_FRAME_SEALED,
    )
    scope_value = a_frame_v1.validate_scope_bytes(a_scope)
    frame_value = a_frame_v1.validate_frame_manifest_bytes(a_frame, a_scope, a_census)
    seed_material = _obj(base["a_seed"])
    seed_material.pop("artifact_sha256")
    seed_material.update(
        {
            "scope_sha256": scope_value["artifact_sha256"],
            "frame_manifest_sha256": frame_value["artifact_sha256"],
            "census_raw_sha256": a_frame_v1.raw_sha256(a_census),
        }
    )
    a_seed = a_frame_v1.build_seed_receipt_bytes(
        seed_material,
        a_scope,
        a_frame,
        a_census,
    )
    a_plan = a_frame_v1.build_sampling_plan_bytes(
        a_scope,
        a_census,
        a_frame,
        a_seed,
        selection_sealed_at=subject_fixture.A_SELECTED,
    )
    return {
        **base,
        "a_census": a_census,
        "a_frame": a_frame,
        "a_seed": a_seed,
        "a_plan": a_plan,
    }


def _positive_candidates(base: dict[str, bytes]) -> list[dict[str, object]]:
    """source selected lineage마다 기본 context와 span variant 하나를 둔다."""

    source_by_candidate = {
        row["candidate_id"]: row for row in _rows(base["source_census"])
    }
    candidates: list[dict[str, object]] = []
    for bridge_row in _rows(base["bridge_inventory"]):
        candidate = subject_fixture._a_candidate(
            bridge_row,
            source_by_candidate[bridge_row["candidate_id"]],
        )
        candidates.extend((candidate, _variant(candidate, bridge_row, 1)))
    return candidates


def _positive_bundle(*, reverse: bool = False) -> dict[str, bytes]:
    base = subject_fixture._bundle()
    candidates = _positive_candidates(base)
    if reverse:
        candidates.reverse()
    return _rebuild_a_predecessor(base, candidates)


def _lineage_bundle(bundle: dict[str, bytes]) -> dict[str, bytes]:
    preseed_raws = _preseed_raw_kwargs(bundle)
    lineage_frame = contract.build_lineage_frame_bytes(
        lineage_frame_sealed_at=LINEAGE_FRAME_SEALED_AT,
        **preseed_raws,
    )
    lineage_seed = contract.build_seed_receipt_bytes(
        {
            "seed_receipt_id": "fixture-a-lineage-capped-seed-v2",
            "revealed_seed_sha256": contract.canonical_sha256(
                "fixture-a-lineage-capped-revealed-seed"
            ),
            "frame_owner_precommit_sha256": contract.canonical_sha256(
                "fixture-a-lineage-capped-owner-precommit"
            ),
            "frame_owner_precommitted_at": LINEAGE_OWNER_PRECOMMITTED_AT,
            "revealed_at": LINEAGE_SEED_REVEALED_AT,
        },
        lineage_frame,
        **preseed_raws,
    )
    plan = contract.build_sampling_plan_bytes(
        lineage_frame_raw=lineage_frame,
        lineage_seed_raw=lineage_seed,
        selection_sealed_at=SELECTION_SEALED_AT,
        **_all_raw_kwargs(bundle),
    )
    return {
        **bundle,
        "lineage_frame": lineage_frame,
        "lineage_seed": lineage_seed,
        "lineage_plan": plan,
    }


class PresentedAContextLineageCappedFullFrameV2Tests(unittest.TestCase):
    """동일 source lineage가 표본석과 통계 분모를 부풀리지 못하게 한다."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = _lineage_bundle(_positive_bundle())

    def _parent(self, bundle: dict[str, bytes] | None = None) -> dict[str, object]:
        value = self.bundle if bundle is None else bundle
        return parent.validate_lineage_frame_seed_and_plan_against_raw_inputs(
            lineage_frame_raw=value["lineage_frame"],
            lineage_seed_raw=value["lineage_seed"],
            sampling_plan_raw=value["lineage_plan"],
            **_all_raw_kwargs(value),
        )

    def test_positive_eighty_contexts_collapse_to_forty_lineages_and_twenty_seats(
        self,
    ) -> None:
        frame = contract.validate_lineage_frame_bytes(
            self.bundle["lineage_frame"], **_preseed_raw_kwargs(self.bundle)
        )
        plan = contract.validate_sampling_plan_bytes(
            self.bundle["lineage_plan"],
            lineage_frame_raw=self.bundle["lineage_frame"],
            lineage_seed_raw=self.bundle["lineage_seed"],
            **_all_raw_kwargs(self.bundle),
        )
        self.assertEqual(frame["eligible_context_count"], 80)
        self.assertEqual(frame["eligible_source_lineage_count"], 40)
        self.assertEqual(plan["selected_input_count"], 20)
        self.assertEqual(plan["eligible_context_surplus_count"], 60)
        self.assertEqual(plan["eligible_lineage_surplus_count"], 20)
        self.assertEqual(
            plan["per_profile_counts"],
            {profile: 5 for profile in a_frame_v1.SOURCE_PROFILES},
        )

    def test_candidate_input_order_does_not_change_any_canonical_v2_bytes(self) -> None:
        reversed_bundle = _lineage_bundle(_positive_bundle(reverse=True))
        for field in (
            "a_census",
            "a_frame",
            "a_seed",
            "a_plan",
            "lineage_frame",
            "lineage_seed",
            "lineage_plan",
        ):
            with self.subTest(field=field):
                self.assertEqual(self.bundle[field], reversed_bundle[field])

    def test_one_prolific_lineage_cannot_fill_a_profile_quota(self) -> None:
        base = subject_fixture._bundle()
        source_by_candidate = {
            row["candidate_id"]: row for row in _rows(base["source_census"])
        }
        bridge_rows = _rows(base["bridge_inventory"])
        official = next(
            row for row in bridge_rows if row["source_profile"] == "OFFICIAL_STRUCTURED"
        )
        official_candidate = subject_fixture._a_candidate(
            official, source_by_candidate[official["candidate_id"]]
        )
        candidates = [
            _variant(official_candidate, official, offset) for offset in range(5)
        ]
        for bridge_row in bridge_rows:
            if bridge_row["source_profile"] == "OFFICIAL_STRUCTURED":
                continue
            candidates.append(
                subject_fixture._a_candidate(
                    bridge_row,
                    source_by_candidate[bridge_row["candidate_id"]],
                )
            )
        attacked = _rebuild_a_predecessor(base, candidates)
        with self.assertRaisesRegex(ValueError, "underfill|lineage"):
            contract.build_lineage_frame_bytes(
                lineage_frame_sealed_at=LINEAGE_FRAME_SEALED_AT,
                **_preseed_raw_kwargs(attacked),
            )

    def test_selected_and_surplus_partition_distinct_lineages_exactly_once(self) -> None:
        plan = _obj(self.bundle["lineage_plan"])
        selected = plan["selected_inputs"]  # type: ignore[assignment]
        context_surplus = plan["eligible_context_surplus"]  # type: ignore[assignment]
        selected_lineages = plan["selected_lineages"]  # type: ignore[assignment]
        lineage_surplus = plan["eligible_lineage_surplus"]  # type: ignore[assignment]
        selected_units = [row["source_lineage_unit_sha256"] for row in selected]
        selected_lineage_units = [
            row["source_lineage_unit_sha256"] for row in selected_lineages
        ]
        surplus_lineage_units = [
            row["source_lineage_unit_sha256"] for row in lineage_surplus
        ]
        self.assertEqual(len(selected_units), 20)
        self.assertEqual(len(selected_units), len(set(selected_units)))
        self.assertEqual(set(selected_units), set(selected_lineage_units))
        self.assertEqual(len(context_surplus), 60)
        self.assertEqual(len(surplus_lineage_units), 20)
        self.assertEqual(len(surplus_lineage_units), len(set(surplus_lineage_units)))
        self.assertFalse(set(selected_lineage_units) & set(surplus_lineage_units))
        self.assertEqual(
            len(set(selected_lineage_units + surplus_lineage_units)), 40
        )
        selected_contexts = {row["context_unit_sha256"] for row in selected}
        surplus_contexts = {
            row["context_unit_sha256"] for row in context_surplus
        }
        self.assertFalse(selected_contexts & surplus_contexts)
        self.assertEqual(len(selected_contexts | surplus_contexts), 80)

    def test_nominal_probability_uses_lineage_population_and_is_reduced(self) -> None:
        plan = _obj(self.bundle["lineage_plan"])
        for row in plan["selected_inputs"]:  # type: ignore[union-attr]
            with self.subTest(candidate_id=row["candidate_id"]):
                self.assertEqual((row["G_h"], row["n_h"], row["K_g"]), (10, 5, 2))
                self.assertEqual(
                    (
                        row["lineage_inclusion_probability_numerator"],
                        row["lineage_inclusion_probability_denominator"],
                    ),
                    (1, 2),
                )
                self.assertEqual(
                    (
                        row["within_lineage_probability_numerator"],
                        row["within_lineage_probability_denominator"],
                    ),
                    (1, 2),
                )
                self.assertEqual(
                    (
                        row["marginal_inclusion_probability_numerator"],
                        row["marginal_inclusion_probability_denominator"],
                    ),
                    (1, 4),
                )
                for prefix in (
                    "lineage_inclusion_probability",
                    "lineage_weight",
                    "within_lineage_probability",
                    "within_lineage_weight",
                    "marginal_inclusion_probability",
                    "marginal_weight",
                ):
                    self.assertEqual(
                        math.gcd(
                            row[f"{prefix}_numerator"],
                            row[f"{prefix}_denominator"],
                        ),
                        1,
                    )

    def test_resealed_duplicate_selected_lineage_is_rejected_by_both_validators(self) -> None:
        plan = _obj(self.bundle["lineage_plan"])
        selected = plan["selected_inputs"]  # type: ignore[assignment]
        selected[1]["source_lineage_unit_sha256"] = selected[0][
            "source_lineage_unit_sha256"
        ]
        plan["selected_input_set_sha256"] = contract.canonical_sha256(selected)
        attacked = _reseal(plan)
        with self.assertRaises(ValueError):
            contract.validate_sampling_plan_bytes(
                attacked,
                lineage_frame_raw=self.bundle["lineage_frame"],
                lineage_seed_raw=self.bundle["lineage_seed"],
                **_all_raw_kwargs(self.bundle),
            )
        with self.assertRaises(ValueError):
            parent.validate_lineage_frame_seed_and_plan_against_raw_inputs(
                lineage_frame_raw=self.bundle["lineage_frame"],
                lineage_seed_raw=self.bundle["lineage_seed"],
                sampling_plan_raw=attacked,
                **_all_raw_kwargs(self.bundle),
            )

    def test_parent_replays_lineage_cap_and_all_authority_stays_false(self) -> None:
        plan = _obj(self.bundle["lineage_plan"])
        receipt = self._parent()
        self.assertTrue(receipt["parent_separate_implementation_frame_replay_verified"])
        self.assertEqual(receipt["selected_input_count"], 20)
        self.assertEqual(plan["actual_a_context_review_count"], 0)
        self.assertEqual(plan["actual_surplus_review_count"], 0)
        self.assertEqual(plan["statistical_denominator"], "NONE")
        self.assertFalse(plan["inferential_metrics_allowed"])
        self.assertFalse(plan["complete_case_metrics_allowed"])
        for field in contract.FALSE_AUTHORITY_FIELDS:
            with self.subTest(field=field):
                self.assertIs(plan[field], False)
                self.assertIs(receipt[field], False)

    def test_component_manifest_pins_predecessors_and_v1_stays_immutable(self) -> None:
        self.assertEqual(
            a_frame_v1.COMPONENT_MANIFEST_SHA256,
            "5b38f560cbe6c2af9294e79ad6298b798e7256426c2e1ca353162e7531c47aa9",
        )
        self.assertEqual(
            contract.COMPONENT_MANIFEST_SHA256,
            "c1080b53622b1b1bb93b127361e333cadeddf664c44a94d329257a6a918d250b",
        )
        manifest = contract.COMPONENT_MANIFEST
        self.assertEqual(
            manifest["source_component_manifest_sha256"],
            "efed07649c14cc2af0b0916ef6e6a04b39ad0c9147b97daec74428521287111b",
        )
        self.assertEqual(
            manifest["bridge_component_manifest_sha256"],
            "c7beb367d62a4af025643d42caddf20caccb4938cd5a68dac8b649ee49b165c1",
        )
        self.assertEqual(manifest["downstream_wiring_count"], 0)

    def test_excluded_context_does_not_rerandomize_either_stage(self) -> None:
        base = _positive_bundle()
        candidates = _positive_candidates(subject_fixture._bundle())
        bridge_row = _rows(base["bridge_inventory"])[0]
        source_by_id = {row["candidate_id"]: row for row in _rows(base["source_census"])}
        excluded = _variant(
            subject_fixture._a_candidate(
                bridge_row, source_by_id[bridge_row["candidate_id"]]
            ),
            bridge_row,
            2,
        )
        excluded["presented_collection_allowed"] = False
        candidates.append(excluded)
        changed = _lineage_bundle(_rebuild_a_predecessor(base, candidates))
        before = _obj(self.bundle["lineage_plan"])
        after = _obj(changed["lineage_plan"])
        self.assertEqual(before["selected_lineages"], after["selected_lineages"])
        self.assertEqual(before["selected_inputs"], after["selected_inputs"])

    def test_extra_eligible_member_changes_only_its_context_stage(self) -> None:
        base = _positive_bundle()
        before = _obj(_lineage_bundle(base)["lineage_plan"])
        selected_source_id = before["selected_inputs"][0]["source_frame_candidate_id"]  # type: ignore[index]
        bridge_row = next(
            row
            for row in _rows(base["bridge_inventory"])
            if row["candidate_id"] == selected_source_id
        )
        source_by_id = {row["candidate_id"]: row for row in _rows(base["source_census"])}
        candidates = _positive_candidates(subject_fixture._bundle())
        candidates.append(
            _variant(
                subject_fixture._a_candidate(
                    bridge_row, source_by_id[bridge_row["candidate_id"]]
                ),
                bridge_row,
                2,
            )
        )
        after = _obj(
            _lineage_bundle(_rebuild_a_predecessor(base, candidates))["lineage_plan"]
        )
        self.assertEqual(
            [row["source_lineage_unit_sha256"] for row in before["selected_lineages"]],  # type: ignore[union-attr]
            [row["source_lineage_unit_sha256"] for row in after["selected_lineages"]],  # type: ignore[union-attr]
        )
        target_unit = before["selected_inputs"][0]["source_lineage_unit_sha256"]  # type: ignore[index]
        before_other = {
            row["source_lineage_unit_sha256"]: row["context_unit_sha256"]
            for row in before["selected_inputs"]  # type: ignore[union-attr]
            if row["source_lineage_unit_sha256"] != target_unit
        }
        after_other = {
            row["source_lineage_unit_sha256"]: row["context_unit_sha256"]
            for row in after["selected_inputs"]  # type: ignore[union-attr]
            if row["source_lineage_unit_sha256"] != target_unit
        }
        self.assertEqual(before_other, after_other)

    def test_new_seed_chronology_is_fail_closed(self) -> None:
        preseed = _preseed_raw_kwargs(self.bundle)
        frame = self.bundle["lineage_frame"]
        common = {
            "seed_receipt_id": "bad-chronology-seed",
            "revealed_seed_sha256": contract.canonical_sha256("revealed"),
            "frame_owner_precommit_sha256": contract.canonical_sha256("owner"),
        }
        for precommitted_at, revealed_at in (
            (LINEAGE_FRAME_SEALED_AT, LINEAGE_SEED_REVEALED_AT),
            (LINEAGE_OWNER_PRECOMMITTED_AT, LINEAGE_OWNER_PRECOMMITTED_AT),
        ):
            with self.subTest(precommitted_at=precommitted_at, revealed_at=revealed_at):
                with self.assertRaisesRegex(ValueError, "chronology"):
                    contract.build_seed_receipt_bytes(
                        {
                            **common,
                            "frame_owner_precommitted_at": precommitted_at,
                            "revealed_at": revealed_at,
                        },
                        frame,
                        **preseed,
                    )

    def test_source_bridge_a_cross_binding_rejects_registry_relabel(self) -> None:
        base = subject_fixture._bundle()
        candidates = _positive_candidates(base)
        candidates[0]["registry_record_id"] = "coordinated-but-unbridged-registry"
        attacked = _rebuild_a_predecessor(base, candidates)
        with self.assertRaisesRegex(ValueError, "cross binding"):
            contract.build_lineage_frame_bytes(
                lineage_frame_sealed_at=LINEAGE_FRAME_SEALED_AT,
                **_preseed_raw_kwargs(attacked),
            )

    def test_authority_reseal_is_rejected_at_frame_seed_and_plan(self) -> None:
        frame = _obj(self.bundle["lineage_frame"])
        frame["lineage_factual_authority_verified"] = True
        with self.assertRaises(ValueError):
            contract.validate_lineage_frame_bytes(
                _reseal(frame), **_preseed_raw_kwargs(self.bundle)
            )
        seed = _obj(self.bundle["lineage_seed"])
        seed["seed_authority_verified"] = True
        with self.assertRaises(ValueError):
            contract.validate_seed_receipt_bytes(
                _reseal(seed),
                self.bundle["lineage_frame"],
                **_preseed_raw_kwargs(self.bundle),
            )
        plan = _obj(self.bundle["lineage_plan"])
        plan["production_approval"] = True
        attacked_plan = _reseal(plan)
        with self.assertRaises(ValueError):
            contract.validate_sampling_plan_bytes(
                attacked_plan,
                lineage_frame_raw=self.bundle["lineage_frame"],
                lineage_seed_raw=self.bundle["lineage_seed"],
                **_all_raw_kwargs(self.bundle),
            )
        with self.assertRaises(ValueError):
            parent.validate_lineage_frame_seed_and_plan_against_raw_inputs(
                lineage_frame_raw=self.bundle["lineage_frame"],
                lineage_seed_raw=self.bundle["lineage_seed"],
                sampling_plan_raw=attacked_plan,
                **_all_raw_kwargs(self.bundle),
            )

    def test_raw_role_and_exact_bytes_preflight(self) -> None:
        class BytesSubclass(bytes):
            pass

        preseed = _preseed_raw_kwargs(self.bundle)
        missing = dict(preseed)
        missing.pop("a_frame_raw")
        with self.assertRaisesRegex(ValueError, "role order|membership"):
            contract.build_lineage_frame_bytes(
                lineage_frame_sealed_at=LINEAGE_FRAME_SEALED_AT, **missing
            )
        reordered = {key: preseed[key] for key in reversed(tuple(preseed))}
        with self.assertRaisesRegex(ValueError, "role order|membership"):
            contract.build_lineage_frame_bytes(
                lineage_frame_sealed_at=LINEAGE_FRAME_SEALED_AT, **reordered
            )
        subclassed = dict(preseed)
        subclassed["a_frame_raw"] = BytesSubclass(subclassed["a_frame_raw"])
        with self.assertRaisesRegex(ValueError, "type"):
            contract.build_lineage_frame_bytes(
                lineage_frame_sealed_at=LINEAGE_FRAME_SEALED_AT, **subclassed
            )

    def test_parent_is_producer_free_and_temporal_observation_is_not_lineage_key(self) -> None:
        root = Path(__file__).resolve().parents[1]
        producer_name = "p0_presented_a_context_lineage_capped_full_frame_v2_contract"
        parent_source = (
            root
            / "src/llm_batch/grounding/p0_presented_a_context_lineage_capped_full_frame_v2_parent_validator.py"
        ).read_text(encoding="utf-8")
        producer_source = (
            root
            / "src/llm_batch/grounding/p0_presented_a_context_lineage_capped_full_frame_v2_contract.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(f"import {producer_name}", parent_source)
        self.assertNotIn("revision_observation_identity_sha256", producer_source)
        self.assertIn("source_lineage_unit_sha256", producer_source)

    def test_parent_runtime_guard_rejects_predecessor_callable_substitution(self) -> None:
        with patch.object(
            parent.source_parent,
            "validate_frame_and_plan_against_raw_inputs",
            return_value={
                "expected_component_manifest_sha256": contract.SOURCE_COMPONENT_MANIFEST_SHA256
            },
        ):
            with self.assertRaisesRegex(ValueError, "callable integrity"):
                self._parent()
        with patch.object(
            parent.a_parent,
            "validate_a_context_frame_and_plan_against_raw_inputs",
            return_value={"parent_separate_implementation_frame_replay_verified": True},
        ):
            with self.assertRaisesRegex(ValueError, "callable integrity"):
                self._parent()

    def test_parent_bridge_parity_rejects_metadata_and_commitment_types(self) -> None:
        source_plan = _obj(self.bundle["source_plan"])
        selected = source_plan["selected_inputs"]  # type: ignore[assignment]
        bridge_rows = _rows(self.bundle["bridge_inventory"])
        for field, value in (
            ("content_type", True),
            ("content_type", "text/plain\x00"),
            ("registry_record_commitment_sha256", "not-a-sha"),
        ):
            attacked_rows = deepcopy(bridge_rows)
            attacked_rows[0][field] = value
            material = {
                key: item
                for key, item in attacked_rows[0].items()
                if key != "bridge_row_sha256"
            }
            attacked_rows[0]["bridge_row_sha256"] = contract.canonical_sha256(material)
            attacked = b"".join(_file(row) for row in attacked_rows)
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    parent._bridge(attacked, selected)

    def test_parent_rejects_bool_seed_id_even_when_self_hash_is_resealed(self) -> None:
        seed = _obj(self.bundle["lineage_seed"])
        seed["seed_receipt_id"] = True
        attacked = _reseal(seed)
        with self.assertRaisesRegex(ValueError, "seed_receipt_id"):
            parent.validate_lineage_frame_seed_and_plan_against_raw_inputs(
                lineage_frame_raw=self.bundle["lineage_frame"],
                lineage_seed_raw=attacked,
                sampling_plan_raw=self.bundle["lineage_plan"],
                **_all_raw_kwargs(self.bundle),
            )

    def test_payload_fingerprint_and_surface_are_recomputed_from_bridge_bytes(self) -> None:
        base = subject_fixture._bundle()
        for field, value in (
            ("content_fingerprint", contract.canonical_sha256("forged payload")),
            ("surface_sha256", contract.canonical_sha256("forged surface")),
        ):
            candidates = _positive_candidates(base)
            candidates[0][field] = value
            attacked = _rebuild_a_predecessor(base, candidates)
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "cross binding"):
                    contract.build_lineage_frame_bytes(
                        lineage_frame_sealed_at=LINEAGE_FRAME_SEALED_AT,
                        **_preseed_raw_kwargs(attacked),
                    )

    def test_runtime_guard_rejects_helper_and_constant_drift(self) -> None:
        old_parent_object = parent._object
        try:
            parent._object = lambda raw, label: old_parent_object(raw, label)
            with self.assertRaisesRegex(ValueError, "integrity drift"):
                self._parent()
        finally:
            parent._object = old_parent_object
        old_parent_cap = parent.MAX_OBJECT_BYTES
        try:
            parent.MAX_OBJECT_BYTES += 1
            with self.assertRaisesRegex(ValueError, "integrity drift"):
                self._parent()
        finally:
            parent.MAX_OBJECT_BYTES = old_parent_cap
        old_child_state = contract._bound_state
        try:
            contract._bound_state = lambda raws, require_a_plan: old_child_state(
                raws, require_a_plan=require_a_plan
            )
            with self.assertRaisesRegex(ValueError, "integrity drift"):
                contract.validate_lineage_frame_bytes(
                    self.bundle["lineage_frame"], **_preseed_raw_kwargs(self.bundle)
                )
        finally:
            contract._bound_state = old_child_state

    def test_huge_integer_json_error_is_normalized_by_child_and_parent(self) -> None:
        attacked = b'{"x":' + b"1" * 5000 + b"}\n"
        with self.assertRaises(contract.P0PresentedAContextLineageCappedV2Error):
            contract._object(attacked, "huge integer")
        with self.assertRaises(parent.P0PresentedAContextLineageCappedV2ParentError):
            parent._object(attacked, "huge integer")

    def test_mutable_exported_manifest_drift_is_detected(self) -> None:
        original = dict(contract.COMPONENT_MANIFEST)
        try:
            contract.COMPONENT_MANIFEST["authority"] = "ALL"
            with self.assertRaisesRegex(ValueError, "integrity drift"):
                contract._runtime_guard()
        finally:
            contract.COMPONENT_MANIFEST.clear()
            contract.COMPONENT_MANIFEST.update(original)

    def test_child_preflights_seed_before_any_predecessor_replay(self) -> None:
        oversized = b"x" * (contract.MAX_OBJECT_BYTES + 1)
        with patch.object(
            contract.source_v2,
            "validate_scope_bytes",
            wraps=contract.source_v2.validate_scope_bytes,
        ) as source_scope_call:
            with self.assertRaisesRegex(ValueError, "byte bound"):
                contract.validate_seed_receipt_bytes(
                    oversized,
                    self.bundle["lineage_frame"],
                    **_preseed_raw_kwargs(self.bundle),
                )
            self.assertEqual(source_scope_call.call_count, 0)

    def test_parent_preflights_new_artifact_bytes_before_predecessor_calls(self) -> None:
        oversized = b"{" + b" " * contract.MAX_OBJECT_BYTES + b"}\n"
        with patch.object(
            parent.source_parent,
            "_scope",
            wraps=parent.source_parent._scope,
        ) as source_call, patch.object(
            parent.a_parent,
            "_scope",
            wraps=parent.a_parent._scope,
        ) as a_call:
            with self.assertRaises(ValueError):
                parent.validate_lineage_frame_seed_and_plan_against_raw_inputs(
                    lineage_frame_raw=oversized,
                    lineage_seed_raw=self.bundle["lineage_seed"],
                    sampling_plan_raw=self.bundle["lineage_plan"],
                    **_all_raw_kwargs(self.bundle),
                )
            self.assertEqual(source_call.call_count, 0)
            self.assertEqual(a_call.call_count, 0)


if __name__ == "__main__":
    unittest.main()
