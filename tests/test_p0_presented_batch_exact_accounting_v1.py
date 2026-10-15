from __future__ import annotations

import ast
from copy import deepcopy
import inspect
import json
from pathlib import Path
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_batch.grounding import (  # noqa: E402
    p0_actual_packet_contract as packet_contract,
)
from llm_batch.grounding import (  # noqa: E402
    p0_full_eligible_sampling_frame_v2_contract as frame,
)
from llm_batch.grounding import (  # noqa: E402
    p0_presented_batch_exact_accounting_v1_contract as contract,
)
from llm_batch.grounding import (  # noqa: E402
    p0_presented_batch_exact_accounting_v1_parent_validator as parent,
)


PLATFORM = "fixture-platform"
UTC_DAY = "2026-09-01"
CREATED_AT = "2026-08-31T00:00:00Z"
CUTOFF = "2026-09-02T00:00:00Z"
FRAME_SEALED_AT = "2026-09-02T00:00:01Z"
OWNER_PRECOMMITTED_AT = "2026-09-02T00:00:02Z"
SEED_REVEALED_AT = "2026-09-02T00:00:03Z"
SELECTION_SEALED_AT = "2026-09-02T00:00:04Z"
BATCH_PRECOMMITTED_AT = "2026-09-02T00:00:05Z"
BATCH_STARTED_AT = "2026-09-02T00:00:06Z"
BATCH_COMPLETED_AT = "2026-09-02T00:00:07Z"
RESULTS_SEALED_AT = "2026-09-02T00:00:08Z"
REVIEW_INVENTORY_SEALED_AT = "2026-09-02T00:00:09Z"

ADAPTER_BY_PROFILE = {
    "OFFICIAL_STRUCTURED": "adapter-official",
    "COMMUNITY_STRUCTURED": "adapter-community",
    "MEDIA_OCR": "adapter-media",
    "GENERIC_FALLBACK": "adapter-generic",
}


def _sha(value: object) -> str:
    return frame.canonical_sha256(value)


def _object(raw: bytes) -> dict[str, object]:
    return json.loads(raw.decode("utf-8"))


def _rows(raw: bytes) -> list[dict[str, object]]:
    return [json.loads(line) for line in raw.decode("utf-8").splitlines()]


def _file(value: object) -> bytes:
    return contract.canonical_file_bytes(value)


def _jsonl(values: list[dict[str, object]]) -> bytes:
    return b"".join(_file(value) for value in values)


def _reseal(value: dict[str, object], field: str) -> dict[str, object]:
    material = {key: item for key, item in value.items() if key != field}
    return {**material, field: contract.canonical_sha256(material)}


def _scope_raw() -> bytes:
    return frame.build_scope_bytes(
        {
            "schema_version": frame.SCOPE_SCHEMA,
            "record_origin": frame.EXAMPLE_ORIGIN,
            "scope_id": "fixture-presented-batch-v1",
            "created_at": CREATED_AT,
            "frame_cutoff": CUTOFF,
            "adapter_profile_map": sorted(
                (
                    {"adapter_id": adapter, "source_profile": profile}
                    for profile, adapter in ADAPTER_BY_PROFILE.items()
                ),
                key=lambda item: item["adapter_id"],
            ),
            "strata": [
                {
                    "source_profile": profile,
                    "platform": PLATFORM,
                    "utc_day": UTC_DAY,
                    "quota": 10,
                }
                for profile in frame.SOURCE_PROFILES
            ],
            "enumeration_policy_sha256": _sha("enumeration-policy"),
            "eligibility_policy_sha256": _sha("eligibility-policy"),
            "rights_policy_sha256": _sha("rights-policy"),
            "strata_policy_sha256": _sha("strata-policy"),
            "future_seed_spec_sha256": _sha("future-seed-spec"),
            "expected_per_profile_quota": 10,
            "expected_total_quota": 40,
            "selection_algorithm": frame.SELECTION_ALGORITHM,
            "lineage_policy": frame.LINEAGE_POLICY,
            "labels_observed": False,
            "semantic_fields_used": False,
            "action_applied": False,
            "operational_effect": frame.OPERATIONAL_EFFECT,
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


def _frame_bundle() -> dict[str, bytes]:
    scope = _scope_raw()
    census = frame.build_census_bytes(
        scope,
        [
            _candidate(profile, index)
            for profile in frame.SOURCE_PROFILES
            for index in range(10)
        ],
    )
    frame_raw = frame.build_frame_manifest_bytes(
        scope, census, frame_sealed_at=FRAME_SEALED_AT
    )
    scope_value = frame.validate_scope_bytes(scope)
    frame_value = frame.validate_frame_manifest_bytes(frame_raw, scope, census)
    seed = frame.build_seed_receipt_bytes(
        {
            "schema_version": frame.SEED_RECEIPT_SCHEMA,
            "record_origin": frame.EXAMPLE_ORIGIN,
            "seed_receipt_id": "fixture-presented-batch-seed-v1",
            "scope_sha256": scope_value["artifact_sha256"],
            "frame_manifest_sha256": frame_value["artifact_sha256"],
            "future_seed_spec_sha256": scope_value["future_seed_spec_sha256"],
            "revealed_seed_sha256": _sha("revealed-seed"),
            "frame_owner_precommit_sha256": _sha("presented-owner-precommit"),
            "frame_owner_precommitted_at": OWNER_PRECOMMITTED_AT,
            "revealed_at": SEED_REVEALED_AT,
            "owner_authority_verified": False,
            "seed_authority_verified": False,
            "action_applied": False,
            "operational_effect": frame.OPERATIONAL_EFFECT,
        },
        scope,
        frame_raw,
        census,
    )
    plan = frame.build_sampling_plan_bytes(
        scope,
        census,
        frame_raw,
        seed,
        selection_sealed_at=SELECTION_SEALED_AT,
    )
    return {"scope": scope, "census": census, "frame": frame_raw, "seed": seed, "plan": plan}


def _payload(sequence: int, profile: str) -> bytes:
    if profile != "COMMUNITY_STRUCTURED":
        return b"presented unsupported profile bytes"
    if sequence == 11:
        return "'첫말'은 첫 정의를 뜻한다.\n'둘말'은 둘 정의를 뜻한다.".encode("utf-8")
    if sequence == 12:
        return "정의문이 아닌 제시 문맥".encode("utf-8")
    if sequence == 13:
        return b"\xff"
    if sequence == 14:
        return "'아생갤'은 caller가 제시한 정의를 뜻한다.".encode("utf-8")
    return f"'표면{sequence}'은 제시 정의 {sequence}를 뜻한다.".encode("utf-8")


def _batch_inputs(plan_raw: bytes) -> list[dict[str, object]]:
    plan = _object(plan_raw)
    inputs: list[dict[str, object]] = []
    for selected in plan["selected_inputs"]:  # type: ignore[index]
        sequence = selected["input_sequence"]
        profile = selected["source_profile"]
        inputs.append(
            {
                **{
                    field: selected[field]
                    for field in contract._SELECTED_IDENTITY_FIELDS
                },
                "registry_record_id": f"registry-record-{sequence}",
                "registry_record_commitment_sha256": _sha(
                    {"registry": sequence, "candidate": selected["candidate_id"]}
                ),
                "content_type": "text/plain; charset=utf-8",
                "capture_version": "normalized-community-explicit-statement-lines-v1",
                "normalization_version": "utf8_identity_v1",
                "payload": _payload(sequence, profile),
            }
        )
    return inputs


def _base_bundle() -> dict[str, bytes]:
    bundle = _frame_bundle()
    bridge = contract.build_bridge_inventory_bytes(
        scope_raw=bundle["scope"],
        census_raw=bundle["census"],
        frame_manifest_raw=bundle["frame"],
        seed_receipt_raw=bundle["seed"],
        sampling_plan_raw=bundle["plan"],
        batch_inputs=_batch_inputs(bundle["plan"]),
    )
    precommit = contract.build_batch_precommit_bytes(
        scope_raw=bundle["scope"],
        census_raw=bundle["census"],
        frame_manifest_raw=bundle["frame"],
        seed_receipt_raw=bundle["seed"],
        sampling_plan_raw=bundle["plan"],
        bridge_inventory_raw=bridge,
        precommitted_at=BATCH_PRECOMMITTED_AT,
    )
    results, receipt = contract.execute_presented_batch(
        scope_raw=bundle["scope"],
        census_raw=bundle["census"],
        frame_manifest_raw=bundle["frame"],
        seed_receipt_raw=bundle["seed"],
        sampling_plan_raw=bundle["plan"],
        bridge_inventory_raw=bridge,
        batch_precommit_raw=precommit,
        batch_started_at=BATCH_STARTED_AT,
        batch_completed_at=BATCH_COMPLETED_AT,
        results_sealed_at=RESULTS_SEALED_AT,
    )
    unreviewed = contract.build_unreviewed_inventory_bytes(
        receipt,
        scope_raw=bundle["scope"],
        census_raw=bundle["census"],
        frame_manifest_raw=bundle["frame"],
        seed_receipt_raw=bundle["seed"],
        sampling_plan_raw=bundle["plan"],
        bridge_inventory_raw=bridge,
        batch_precommit_raw=precommit,
        results_raw=results,
        review_inventory_sealed_at=REVIEW_INVENTORY_SEALED_AT,
    )
    return {**bundle, "bridge": bridge, "precommit": precommit, "results": results, "receipt": receipt, "unreviewed": unreviewed}


def _parent_validate(bundle: dict[str, bytes]) -> dict[str, object]:
    return parent.validate_batch_bundle_against_raw_inputs(
        sampling_plan_raw=bundle["plan"],
        expected_sampling_plan_raw_sha256=contract.raw_sha256(bundle["plan"]),
        bridge_inventory_raw=bundle["bridge"],
        batch_precommit_raw=bundle["precommit"],
        expected_precommit_raw_sha256=contract.raw_sha256(bundle["precommit"]),
        results_raw=bundle["results"],
        batch_receipt_raw=bundle["receipt"],
        unreviewed_inventory_raw=bundle["unreviewed"],
    )


def _receipt_for_results(bundle: dict[str, bytes], results_raw: bytes) -> bytes:
    plan = contract._validated_plan(
        scope_raw=bundle["scope"],
        census_raw=bundle["census"],
        frame_manifest_raw=bundle["frame"],
        seed_receipt_raw=bundle["seed"],
        sampling_plan_raw=bundle["plan"],
    )
    bridges, _, _ = contract._validate_bridge_rows(bundle["bridge"], plan)
    results = contract._validate_result_rows(results_raw, bridges)
    precommit = contract.validate_batch_precommit_bytes(
        bundle["precommit"],
        scope_raw=bundle["scope"],
        census_raw=bundle["census"],
        frame_manifest_raw=bundle["frame"],
        seed_receipt_raw=bundle["seed"],
        sampling_plan_raw=bundle["plan"],
        bridge_inventory_raw=bundle["bridge"],
    )
    value = contract._build_receipt_value(
        precommit=precommit,
        bridge_inventory_raw=bundle["bridge"],
        batch_precommit_raw=bundle["precommit"],
        results_raw=results_raw,
        result_rows=results,
        batch_started_at=BATCH_STARTED_AT,
        batch_completed_at=BATCH_COMPLETED_AT,
        results_sealed_at=RESULTS_SEALED_AT,
    )
    return _file(value)


def _unreviewed_for(bundle: dict[str, bytes], results: bytes, receipt: bytes) -> bytes:
    return contract.build_unreviewed_inventory_bytes(
        receipt,
        scope_raw=bundle["scope"],
        census_raw=bundle["census"],
        frame_manifest_raw=bundle["frame"],
        seed_receipt_raw=bundle["seed"],
        sampling_plan_raw=bundle["plan"],
        bridge_inventory_raw=bundle["bridge"],
        batch_precommit_raw=bundle["precommit"],
        results_raw=results,
        review_inventory_sealed_at=REVIEW_INVENTORY_SEALED_AT,
    )


class PresentedBatchExactAccountingV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = _base_bundle()

    def test_positive_exact_itt_accounting_and_parent_replay(self) -> None:
        receipt = _object(self.bundle["receipt"])
        inventory = _object(self.bundle["unreviewed"])
        self.assertEqual(receipt["itt_denominator"], 40)
        self.assertEqual(receipt["itt_accounted_input_count"], 40)
        self.assertEqual(
            receipt["terminal_disposition_counts"],
            {
                "MATCHED": 8,
                "NO_MATCH": 1,
                "UNSUPPORTED_PROFILE": 30,
                "INVALID_CAPTURE": 1,
                "CORE_ERROR": 0,
            },
        )
        self.assertEqual(receipt["total_observation_count"], 9)
        self.assertEqual(receipt["metric_status"], contract.METRIC_STATUS)
        self.assertFalse(receipt["inferential_metrics_allowed"])
        self.assertFalse(receipt["complete_case_metrics_allowed"])
        self.assertFalse(receipt["observation_rows_are_sampling_units"])
        self.assertEqual(receipt["sampling_unit"], "SELECTED_INPUT_LINEAGE")
        self.assertEqual(inventory["contextual_observation_count"], 9)
        self.assertEqual(inventory["full_payload_missed_span_input_count"], 40)
        self.assertEqual(inventory["unreviewed_full_payload_input_count"], 40)
        parent_receipt = _parent_validate(self.bundle)
        self.assertTrue(parent_receipt["parent_separate_implementation_batch_accounting_verified"])
        self.assertEqual(parent_receipt["independent_non_error_core_replay_count"], 40)
        self.assertEqual(parent_receipt["itt_denominator"], 40)
        self.assertEqual(parent_receipt["metric_status"], contract.METRIC_STATUS)
        self.assertFalse(parent_receipt["inferential_metrics_allowed"])
        self.assertFalse(parent_receipt["complete_case_metrics_allowed"])
        for field in (
            "upstream_full_frame_replay_verified",
            "same_process_isolation_verified",
            "core_error_factuality_verified",
            "runtime_execution_authority_verified",
            "actual_source_evidence_verified",
            "exhaustive_human_review_verified",
            "actual_authority_granted",
            "p0_phase_exit",
            "production_approval",
            "full_scan_approval",
        ):
            self.assertIs(parent_receipt[field], False, field)

    def test_core_error_is_terminal_itt_and_execution_continues_all_40(self) -> None:
        base = _frame_bundle()
        inputs = _batch_inputs(base["plan"])
        bridge = contract.build_bridge_inventory_bytes(
            scope_raw=base["scope"], census_raw=base["census"], frame_manifest_raw=base["frame"],
            seed_receipt_raw=base["seed"], sampling_plan_raw=base["plan"], batch_inputs=inputs,
        )
        precommit = contract.build_batch_precommit_bytes(
            scope_raw=base["scope"], census_raw=base["census"], frame_manifest_raw=base["frame"],
            seed_receipt_raw=base["seed"], sampling_plan_raw=base["plan"], bridge_inventory_raw=bridge,
            precommitted_at=BATCH_PRECOMMITTED_AT,
        )
        original = contract.neutral_core.parse_capture
        target = _payload(14, "COMMUNITY_STRUCTURED")
        calls = 0

        def controlled(**kwargs: object) -> dict[str, object]:
            nonlocal calls
            calls += 1
            if kwargs["payload"] == target:
                raise RuntimeError("controlled core failure")
            return original(**kwargs)  # type: ignore[arg-type]

        with mock.patch.object(contract.neutral_core, "parse_capture", side_effect=controlled):
            results, receipt = contract.execute_presented_batch(
                scope_raw=base["scope"], census_raw=base["census"], frame_manifest_raw=base["frame"],
                seed_receipt_raw=base["seed"], sampling_plan_raw=base["plan"], bridge_inventory_raw=bridge,
                batch_precommit_raw=precommit, batch_started_at=BATCH_STARTED_AT,
                batch_completed_at=BATCH_COMPLETED_AT, results_sealed_at=RESULTS_SEALED_AT,
            )
        self.assertEqual(calls, 40)
        receipt_value = _object(receipt)
        self.assertEqual(receipt_value["core_error_count"], 1)
        self.assertEqual(receipt_value["itt_accounted_input_count"], 40)
        error = _rows(results)[13]
        self.assertEqual(error["terminal_disposition"], "CORE_ERROR")
        self.assertIsNone(error["core_result"])
        self.assertEqual(error["observation_count"], 0)
        bundle = {**base, "bridge": bridge, "precommit": precommit, "results": results, "receipt": receipt}
        bundle["unreviewed"] = _unreviewed_for(bundle, results, receipt)
        parent_receipt = _parent_validate(bundle)
        self.assertEqual(parent_receipt["presented_core_error_accounting_count"], 1)
        self.assertEqual(parent_receipt["independent_non_error_core_replay_count"], 39)
        self.assertIs(parent_receipt["core_error_factuality_verified"], False)

    def test_empty_payload_precedes_unsupported_profile_in_parent_replay(self) -> None:
        base = _frame_bundle()
        inputs = _batch_inputs(base["plan"])
        self.assertEqual(inputs[0]["source_profile"], "OFFICIAL_STRUCTURED")
        inputs[0]["payload"] = b""
        bridge = contract.build_bridge_inventory_bytes(
            scope_raw=base["scope"], census_raw=base["census"], frame_manifest_raw=base["frame"],
            seed_receipt_raw=base["seed"], sampling_plan_raw=base["plan"], batch_inputs=inputs,
        )
        precommit = contract.build_batch_precommit_bytes(
            scope_raw=base["scope"], census_raw=base["census"], frame_manifest_raw=base["frame"],
            seed_receipt_raw=base["seed"], sampling_plan_raw=base["plan"], bridge_inventory_raw=bridge,
            precommitted_at=BATCH_PRECOMMITTED_AT,
        )
        results, receipt = contract.execute_presented_batch(
            scope_raw=base["scope"], census_raw=base["census"], frame_manifest_raw=base["frame"],
            seed_receipt_raw=base["seed"], sampling_plan_raw=base["plan"], bridge_inventory_raw=bridge,
            batch_precommit_raw=precommit, batch_started_at=BATCH_STARTED_AT,
            batch_completed_at=BATCH_COMPLETED_AT, results_sealed_at=RESULTS_SEALED_AT,
        )
        first = _rows(results)[0]
        self.assertEqual(first["terminal_disposition"], "INVALID_CAPTURE")
        self.assertEqual(first["core_result"]["reason_code"], "empty_payload")
        bundle = {**base, "bridge": bridge, "precommit": precommit, "results": results, "receipt": receipt}
        bundle["unreviewed"] = _unreviewed_for(bundle, results, receipt)
        parent_receipt = _parent_validate(bundle)
        self.assertEqual(parent_receipt["independent_non_error_core_replay_count"], 40)

    def test_fully_resealed_reported_core_error_is_accounted_but_never_factual(self) -> None:
        rows = deepcopy(_rows(self.bundle["results"]))
        target = rows[13]
        target.update(
            {
                "terminal_disposition": "CORE_ERROR",
                "core_result": None,
                "core_result_sha256": None,
                "core_observations_sha256": None,
                "observation_count": 0,
                "core_error_stage": contract.CORE_ERROR_STAGE,
                "core_error_code": contract.CORE_ERROR_CODE,
                "core_error_presented_only": True,
            }
        )
        rows[13] = _reseal(target, "result_row_sha256")
        results = _jsonl(rows)
        receipt = _receipt_for_results(self.bundle, results)
        unreviewed = _unreviewed_for(self.bundle, results, receipt)
        parent_receipt = _parent_validate(
            {**self.bundle, "results": results, "receipt": receipt, "unreviewed": unreviewed}
        )
        self.assertEqual(parent_receipt["presented_core_error_accounting_count"], 1)
        self.assertIs(parent_receipt["core_error_factuality_verified"], False)
        self.assertIs(parent_receipt["runtime_execution_authority_verified"], False)

    def test_bridge_drop_duplicate_extra_and_physical_reorder_fail(self) -> None:
        rows = _rows(self.bundle["bridge"])
        variants = (
            rows[:-1],
            [*rows[:-1], deepcopy(rows[0])],
            [*rows, deepcopy(rows[0])],
            [rows[1], rows[0], *rows[2:]],
        )
        for variant in variants:
            with self.subTest(rows=len(variant)):
                with self.assertRaises((contract.P0PresentedBatchAccountingError, parent.P0PresentedBatchParentValidationError)):
                    parent.validate_batch_bundle_against_raw_inputs(
                        sampling_plan_raw=self.bundle["plan"],
                        expected_sampling_plan_raw_sha256=contract.raw_sha256(self.bundle["plan"]),
                        bridge_inventory_raw=_jsonl(variant),
                        batch_precommit_raw=self.bundle["precommit"],
                        expected_precommit_raw_sha256=contract.raw_sha256(self.bundle["precommit"]),
                        results_raw=self.bundle["results"],
                        batch_receipt_raw=self.bundle["receipt"],
                        unreviewed_inventory_raw=self.bundle["unreviewed"],
                    )

    def test_input_profile_candidate_registry_and_payload_swaps_fail(self) -> None:
        base = _frame_bundle()
        inputs = _batch_inputs(base["plan"])
        for field in ("source_profile", "candidate_id"):
            changed = deepcopy(inputs)
            changed[0][field], changed[10][field] = changed[10][field], changed[0][field]
            with self.subTest(field=field), self.assertRaises(contract.P0PresentedBatchAccountingError):
                contract.build_bridge_inventory_bytes(
                    scope_raw=base["scope"], census_raw=base["census"], frame_manifest_raw=base["frame"],
                    seed_receipt_raw=base["seed"], sampling_plan_raw=base["plan"], batch_inputs=changed,
                )
        bridge_rows = _rows(self.bundle["bridge"])
        for field in ("registry_record_id", "payload_base64", "payload_sha256"):
            changed = deepcopy(bridge_rows)
            changed[0][field], changed[10][field] = changed[10][field], changed[0][field]
            changed[0] = _reseal(changed[0], "bridge_row_sha256")
            changed[10] = _reseal(changed[10], "bridge_row_sha256")
            with self.subTest(sealed_field=field), self.assertRaises(parent.P0PresentedBatchParentValidationError):
                _parent_validate({**self.bundle, "bridge": _jsonl(changed)})

    def test_precommit_plan_and_presented_pin_chronology_fail_closed(self) -> None:
        with self.assertRaisesRegex(contract.P0PresentedBatchAccountingError, "follow selection"):
            contract.build_batch_precommit_bytes(
                scope_raw=self.bundle["scope"], census_raw=self.bundle["census"],
                frame_manifest_raw=self.bundle["frame"], seed_receipt_raw=self.bundle["seed"],
                sampling_plan_raw=self.bundle["plan"], bridge_inventory_raw=self.bundle["bridge"],
                precommitted_at=SELECTION_SEALED_AT,
            )
        for plan_pin, precommit_pin in (("0" * 64, contract.raw_sha256(self.bundle["precommit"])), (contract.raw_sha256(self.bundle["plan"]), "0" * 64)):
            with self.assertRaises(parent.P0PresentedBatchParentValidationError):
                parent.validate_batch_bundle_against_raw_inputs(
                    sampling_plan_raw=self.bundle["plan"], expected_sampling_plan_raw_sha256=plan_pin,
                    bridge_inventory_raw=self.bundle["bridge"], batch_precommit_raw=self.bundle["precommit"],
                    expected_precommit_raw_sha256=precommit_pin, results_raw=self.bundle["results"],
                    batch_receipt_raw=self.bundle["receipt"], unreviewed_inventory_raw=self.bundle["unreviewed"],
                )

    def test_result_drop_duplicate_extra_reorder_and_resequence_fail(self) -> None:
        rows = _rows(self.bundle["results"])
        variants = [rows[:-1], [*rows[:-1], deepcopy(rows[0])], [*rows, deepcopy(rows[0])]]
        swapped = deepcopy(rows)
        swapped[0], swapped[1] = swapped[1], swapped[0]
        variants.append(swapped)
        resequenced = deepcopy(swapped)
        for index, row in enumerate(resequenced, start=1):
            row["input_sequence"] = index
            resequenced[index - 1] = _reseal(row, "result_row_sha256")
        variants.append(resequenced)
        for variant in variants:
            with self.subTest(rows=len(variant)), self.assertRaises(parent.P0PresentedBatchParentValidationError):
                forged = {**self.bundle, "results": _jsonl(variant)}
                _parent_validate(forged)

    def test_fully_resealed_observation_delete_duplicate_reorder_and_move_fail_parent(self) -> None:
        baseline = _rows(self.bundle["results"])
        source = baseline[10]
        observations = source["core_result"]["observations"]
        variants: list[list[dict[str, object]]] = []
        for changed_observations in (
            observations[:-1],
            [*observations, deepcopy(observations[0])],
            list(reversed(observations)),
        ):
            rows = deepcopy(baseline)
            core_result = rows[10]["core_result"]
            normalized = []
            for sequence, observation in enumerate(changed_observations, start=1):
                changed_observation = deepcopy(observation)
                changed_observation["observation_sequence"] = sequence
                normalized.append(_reseal(changed_observation, "observation_sha256"))
            core_result["observations"] = normalized
            core_result["observation_count"] = len(normalized)
            core_result["observations_sha256"] = contract.canonical_sha256(normalized)
            rows[10]["core_result"] = _reseal(core_result, "result_sha256")
            rows[10]["core_result_sha256"] = rows[10]["core_result"]["result_sha256"]
            rows[10]["core_observations_sha256"] = rows[10]["core_result"]["observations_sha256"]
            rows[10]["observation_count"] = len(normalized)
            rows[10] = _reseal(rows[10], "result_row_sha256")
            variants.append(rows)
        for rows in variants:
            with self.subTest(observations=rows[10]["observation_count"]):
                forged_results = _jsonl(rows)
                forged_receipt = _receipt_for_results(self.bundle, forged_results)
                forged_inventory = _unreviewed_for(self.bundle, forged_results, forged_receipt)
                forged = {**self.bundle, "results": forged_results, "receipt": forged_receipt, "unreviewed": forged_inventory}
                with self.assertRaisesRegex(parent.P0PresentedBatchParentValidationError, "independent replay"):
                    _parent_validate(forged)

    def test_fully_resealed_core_error_to_no_match_laundering_fails_parent(self) -> None:
        rows = deepcopy(_rows(self.bundle["results"]))
        target = rows[13]
        bridge = _rows(self.bundle["bridge"])[13]
        fake_core = {
            **target["core_result"],
            "disposition": "NO_MATCH",
            "reason_code": "mixed_or_nonmatching_context_fail_closed",
            "line_count": 1,
            "nonempty_line_count": 1,
            "observation_count": 0,
            "observations": [],
            "observations_sha256": contract.canonical_sha256([]),
        }
        fake_core = _reseal(fake_core, "result_sha256")
        target.update(
            {
                "terminal_disposition": "NO_MATCH",
                "core_result": fake_core,
                "core_result_sha256": fake_core["result_sha256"],
                "core_observations_sha256": fake_core["observations_sha256"],
                "observation_count": 0,
                "core_error_stage": None,
                "core_error_code": None,
                "core_error_presented_only": False,
                "payload_sha256": bridge["payload_sha256"],
            }
        )
        rows[13] = _reseal(target, "result_row_sha256")
        forged_results = _jsonl(rows)
        forged_receipt = _receipt_for_results(self.bundle, forged_results)
        forged_inventory = _unreviewed_for(self.bundle, forged_results, forged_receipt)
        with self.assertRaisesRegex(parent.P0PresentedBatchParentValidationError, "independent replay"):
            _parent_validate({**self.bundle, "results": forged_results, "receipt": forged_receipt, "unreviewed": forged_inventory})

    def test_success_only_itt_denominator_and_credit_inflation_reseal_fail(self) -> None:
        value = _object(self.bundle["receipt"])
        for field, replacement in (("itt_denominator", 10), ("actual_source_credit_count", 40), ("missing_input_count", 1), ("retry_result_count", True), ("inferential_metrics_allowed", True), ("complete_case_metrics_allowed", True), ("observation_rows_are_sampling_units", True)):
            forged = deepcopy(value)
            forged[field] = replacement
            forged_raw = _file(_reseal(forged, "artifact_sha256"))
            with self.subTest(field=field), self.assertRaises(parent.P0PresentedBatchParentValidationError):
                _parent_validate({**self.bundle, "receipt": forged_raw})
        result_rows = _rows(self.bundle["results"])
        for field, value in (("attempt_count", True), ("observation_count", False)):
            forged_rows = deepcopy(result_rows)
            forged_rows[0][field] = value
            forged_rows[0] = _reseal(forged_rows[0], "result_row_sha256")
            with self.subTest(result_field=field), self.assertRaises(parent.P0PresentedBatchParentValidationError):
                _parent_validate({**self.bundle, "results": _jsonl(forged_rows)})

    def test_noncanonical_duplicate_key_bom_cr_surrogate_and_scalar_attacks_fail(self) -> None:
        attacks = (
            self.bundle["precommit"].replace(b'{', b'{"schema_version":"duplicate",', 1),
            b"\xef\xbb\xbf" + self.bundle["precommit"],
            self.bundle["precommit"].replace(b"\n", b"\r\n"),
            b'{"x":"\\ud800"}\n',
        )
        for raw in attacks:
            with self.subTest(prefix=raw[:20]), self.assertRaises((contract.P0PresentedBatchAccountingError, parent.P0PresentedBatchParentValidationError)):
                contract.validate_batch_precommit_bytes(
                    raw,
                    scope_raw=self.bundle["scope"], census_raw=self.bundle["census"],
                    frame_manifest_raw=self.bundle["frame"], seed_receipt_raw=self.bundle["seed"],
                    sampling_plan_raw=self.bundle["plan"], bridge_inventory_raw=self.bundle["bridge"],
                )
        receipt = _object(self.bundle["receipt"])
        for field, value in (("itt_denominator", True), ("core_error_count", 0.0)):
            forged = deepcopy(receipt)
            forged[field] = value
            forged_raw = _file(_reseal(forged, "artifact_sha256"))
            with self.subTest(field=field), self.assertRaises(parent.P0PresentedBatchParentValidationError):
                _parent_validate({**self.bundle, "receipt": forged_raw})

        huge_integer = b'{"x":' + (b"9" * 5000) + b'}\n'
        excessive_nesting = b'{"x":' + (b"[" * 5000) + b"0" + (b"]" * 5000) + b'}\n'
        for malformed in (huge_integer, excessive_nesting):
            for parser_call, error_type in (
                (lambda raw=malformed: contract._decode_object(raw, "malformed"), contract.P0PresentedBatchAccountingError),
                (lambda raw=malformed: parent._object(raw, "malformed"), parent.P0PresentedBatchParentValidationError),
            ):
                with self.subTest(malformed_length=len(malformed), parser=error_type.__name__), self.assertRaises(error_type):
                    parser_call()

        for public_call, error_type in (
            (
                lambda: contract.validate_batch_precommit_bytes(
                    excessive_nesting,
                    scope_raw=self.bundle["scope"], census_raw=self.bundle["census"],
                    frame_manifest_raw=self.bundle["frame"], seed_receipt_raw=self.bundle["seed"],
                    sampling_plan_raw=self.bundle["plan"], bridge_inventory_raw=self.bundle["bridge"],
                ),
                contract.P0PresentedBatchAccountingError,
            ),
            (
                lambda: _parent_validate({**self.bundle, "precommit": excessive_nesting}),
                parent.P0PresentedBatchParentValidationError,
            ),
        ):
            with self.subTest(public_validator=error_type.__name__), self.assertRaises(error_type):
                public_call()
        for timestamp_call, error_type in (
            (lambda: contract._timestamp("2026-02-31T00:00:00Z", "bad_time"), contract.P0PresentedBatchAccountingError),
            (lambda: parent._time("2026-02-31T00:00:00Z", "bad_time"), parent.P0PresentedBatchParentValidationError),
        ):
            with self.assertRaises(error_type):
                timestamp_call()

    def test_oversize_payload_rejects_whole_bridge_before_partial_accounting(self) -> None:
        base = _frame_bundle()
        inputs = _batch_inputs(base["plan"])
        inputs[0]["payload"] = b"x" * (contract.MAX_PAYLOAD_BYTES_PER_INPUT + 1)
        with self.assertRaisesRegex(contract.P0PresentedBatchAccountingError, "per-input bound"):
            contract.build_bridge_inventory_bytes(
                scope_raw=base["scope"], census_raw=base["census"], frame_manifest_raw=base["frame"],
                seed_receipt_raw=base["seed"], sampling_plan_raw=base["plan"], batch_inputs=inputs,
            )

    def test_v1_plan_and_semantic_field_injection_are_rejected(self) -> None:
        plan = _object(self.bundle["plan"])
        plan["schema_version"] = "p0_actual_source_input_plan_v1"
        plan["selection_algorithm"] = "CALLER_PRECOMMITTED_PROFILE_10X4_V1"
        plan = frame.with_self_hash(plan)
        raw = frame.canonical_file_bytes(plan)
        with self.assertRaises(parent.P0PresentedBatchParentValidationError):
            parent.validate_batch_bundle_against_raw_inputs(
                sampling_plan_raw=raw, expected_sampling_plan_raw_sha256=contract.raw_sha256(raw),
                bridge_inventory_raw=self.bundle["bridge"], batch_precommit_raw=self.bundle["precommit"],
                expected_precommit_raw_sha256=contract.raw_sha256(self.bundle["precommit"]),
                results_raw=self.bundle["results"], batch_receipt_raw=self.bundle["receipt"],
                unreviewed_inventory_raw=self.bundle["unreviewed"],
            )
        rows = _rows(self.bundle["bridge"])
        rows[0]["target_work_id"] = "ATTACKER:WORK"
        with self.assertRaises(parent.P0PresentedBatchParentValidationError):
            _parent_validate({**self.bundle, "bridge": _jsonl(rows)})

    def test_contextual_observation_ids_bind_candidate_and_do_not_inflate_credit(self) -> None:
        inventory = _object(self.bundle["unreviewed"])
        units = inventory["contextual_observation_review_units"]
        self.assertEqual(len(units), 9)
        self.assertEqual(len({row["contextual_observation_unit_sha256"] for row in units}), 9)
        receipt = _object(self.bundle["receipt"])
        self.assertEqual(receipt["actual_source_credit_count"], 0)
        self.assertEqual(receipt["itt_denominator"], 40)

    def test_asaenggal_remains_presented_neutral_surface_without_target_or_route(self) -> None:
        row = _rows(self.bundle["results"])[13]
        self.assertEqual(row["terminal_disposition"], "MATCHED")
        observation = row["core_result"]["observations"][0]
        self.assertEqual(observation["surface_text"], "아생갤")
        serialized = json.dumps(row, ensure_ascii=False, sort_keys=True)
        for forbidden in (
            "target_work_id",
            "target_sense_id",
            "alias_relation",
            "retrieval_query",
            "route_class",
            "credit_count",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_unreviewed_inventory_delete_duplicate_reorder_and_false_completion_fail(self) -> None:
        value = _object(self.bundle["unreviewed"])
        variants = []
        for mutate in (
            lambda row: row["contextual_observation_review_units"].pop(),
            lambda row: row["contextual_observation_review_units"].append(deepcopy(row["contextual_observation_review_units"][0])),
            lambda row: row["contextual_observation_review_units"].reverse(),
            lambda row: row.__setitem__("exhaustive_human_review_verified", True),
        ):
            changed = deepcopy(value)
            mutate(changed)
            changed["contextual_observation_review_units_sha256"] = contract.canonical_sha256(changed["contextual_observation_review_units"])
            changed["contextual_observation_count"] = len(changed["contextual_observation_review_units"])
            variants.append(_file(_reseal(changed, "artifact_sha256")))
        for raw in variants:
            with self.assertRaises(parent.P0PresentedBatchParentValidationError):
                _parent_validate({**self.bundle, "unreviewed": raw})

    def test_frame_candidate_and_registry_identity_remain_distinct(self) -> None:
        for row in _rows(self.bundle["bridge"]):
            self.assertNotEqual(row["candidate_id"], row["registry_record_id"])
        self.assertTrue(contract.COMPONENT_MANIFEST["frame_candidate_and_registry_id_distinct"])
        base = _frame_bundle()
        inputs = _batch_inputs(base["plan"])
        inputs[0]["registry_record_id"] = inputs[0]["candidate_id"]
        with self.assertRaisesRegex(contract.P0PresentedBatchAccountingError, "must remain distinct"):
            contract.build_bridge_inventory_bytes(
                scope_raw=base["scope"], census_raw=base["census"], frame_manifest_raw=base["frame"],
                seed_receipt_raw=base["seed"], sampling_plan_raw=base["plan"], batch_inputs=inputs,
            )
        rows = _rows(self.bundle["bridge"])
        rows[0]["registry_record_id"] = rows[0]["candidate_id"]
        rows[0] = _reseal(rows[0], "bridge_row_sha256")
        with self.assertRaisesRegex(parent.P0PresentedBatchParentValidationError, "must remain distinct"):
            _parent_validate({**self.bundle, "bridge": _jsonl(rows)})

    def test_parent_manifest_is_exact_and_producer_monkeypatch_does_not_change_it(self) -> None:
        self.assertEqual(contract.COMPONENT_MANIFEST_SHA256, parent.EXPECTED_COMPONENT_MANIFEST_SHA256)
        original = parent.EXPECTED_COMPONENT_MANIFEST_SHA256
        with mock.patch.object(contract, "EXPECTED_INPUT_COUNT", 39), mock.patch.object(
            contract, "COMPONENT_MANIFEST_SHA256", "f" * 64
        ):
            self.assertEqual(parent.EXPECTED_COMPONENT_MANIFEST_SHA256, original)
            _parent_validate(self.bundle)

    def test_parent_has_no_batch_core_or_project_import_and_narrow_capabilities(self) -> None:
        tree = ast.parse(inspect.getsource(parent))
        roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])
        self.assertEqual(
            roots,
            {"__future__", "base64", "collections", "datetime", "hashlib", "json", "math", "re", "unicodedata", "typing"},
        )
        forbidden_calls = {"open", "exec", "eval", "compile", "__import__", "system", "popen", "connect", "spawn"}
        calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertFalse(forbidden_calls & calls)

    def test_existing_route_protocol_worker_sandbox_packet_and_child_count_are_unchanged(self) -> None:
        self.assertEqual(len(packet_contract.CHILD_FILES), 13)
        token = "p0_presented_batch_exact_accounting_v1"
        for relative in (
            "src/llm_batch/grounding/p0_actual_route_contract.py",
            "src/llm_batch/grounding/p0_parser_process_protocol.py",
            "src/llm_batch/grounding/p0_parser_process_worker.py",
            "src/llm_batch/grounding/p0_windows_parser_process_sandbox.py",
            "src/llm_batch/grounding/p0_actual_packet_contract.py",
        ):
            self.assertNotIn(token, (ROOT / relative).read_text(encoding="utf-8"))

    def test_manifest_keeps_all_authority_credit_review_and_operational_truth_false(self) -> None:
        manifest = contract.COMPONENT_MANIFEST
        self.assertEqual(manifest["actual_source_credit_count"], 0)
        self.assertEqual(manifest["actual_context_credit_count"], 0)
        self.assertEqual(manifest["metric_status"], contract.METRIC_STATUS)
        self.assertFalse(manifest["inferential_metrics_allowed"])
        self.assertFalse(manifest["complete_case_metrics_allowed"])
        self.assertFalse(manifest["observation_rows_are_sampling_units"])
        self.assertEqual(manifest["sampling_unit"], "SELECTED_INPUT_LINEAGE")
        self.assertFalse(manifest["exhaustive_human_review_verified"])
        self.assertEqual(manifest["direct_io_capabilities"], [])
        for field in contract._FALSE_AUTHORITY_FIELDS:
            self.assertIs(manifest[field], False, field)


if __name__ == "__main__":
    unittest.main()
