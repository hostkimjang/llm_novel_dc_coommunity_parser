from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
import unittest

from expert_main import (
    PublicationCommitError,
    _build_decision_call_measurement_gate,
    _decision_call_measurement_config,
    _measurement_execution_source,
    _preview_publication_decision,
    validate_publication_result_commit,
)
from src.llm_batch.measurement.publication_shadow_observation import (
    PublicationShadowObservationError,
    build_publication_shadow_observation,
    validate_publication_shadow_observation,
)


def _receipt(
    *,
    decision: str = "a",
    outcome: str = "HOLD",
    projection: str = "b",
    stable: str = "c",
    decision_payload: str = "d",
    input_index: int = 1,
    post_id: int = 101,
):
    return SimpleNamespace(
        publication_scope_id="e" * 64,
        input_index=input_index,
        post_id=post_id,
        decision_id=decision * 64,
        outcome=outcome,
        publish_allowed=outcome == "PUBLISH",
        decision_sha256=decision_payload * 64,
        public_projection_sha256=projection * 64,
        stable_result_sha256=stable * 64,
    )


class PublicationShadowObservationTest(unittest.TestCase):
    def test_equal_receipt_is_deterministic_and_public_apply_is_false(self) -> None:
        receipt = build_publication_shadow_observation(
            observed_receipt=_receipt(),
            authoritative_receipt=_receipt(),
        )
        self.assertEqual(validate_publication_shadow_observation(receipt), receipt)
        self.assertFalse(receipt["public_apply"])
        self.assertTrue(receipt["comparison"]["decision_equivalent"])
        self.assertEqual(receipt["comparison"]["drift_dimensions"], [])

    def test_semantic_drift_is_recorded_instead_of_rejected(self) -> None:
        receipt = build_publication_shadow_observation(
            observed_receipt=_receipt(
                decision="1",
                outcome="PUBLISH",
                projection="2",
                stable="3",
                decision_payload="4",
            ),
            authoritative_receipt=_receipt(),
        )
        validated = validate_publication_shadow_observation(receipt)
        self.assertFalse(validated["comparison"]["decision_equivalent"])
        self.assertEqual(
            validated["comparison"]["drift_dimensions"],
            [
                "DECISION_ID",
                "OUTCOME",
                "PUBLISH_ALLOWED",
                "DECISION_PAYLOAD",
                "PUBLIC_PROJECTION",
                "STABLE_RESULT",
            ],
        )

    def test_coordinate_mismatch_and_tamper_fail_closed(self) -> None:
        with self.assertRaisesRegex(
            PublicationShadowObservationError, "input_index mismatch"
        ):
            build_publication_shadow_observation(
                observed_receipt=_receipt(input_index=2),
                authoritative_receipt=_receipt(input_index=1),
            )
        receipt = build_publication_shadow_observation(
            observed_receipt=_receipt(),
            authoritative_receipt=_receipt(),
        )
        tampered = deepcopy(receipt)
        tampered["comparison"]["decision_equivalent"] = False
        with self.assertRaisesRegex(
            PublicationShadowObservationError, "comparison mismatch"
        ):
            validate_publication_shadow_observation(tampered)

    def test_required_shadow_config_is_fresh_no_public_write(self) -> None:
        config = _decision_call_measurement_config(
            {
                "PIPELINE_DECISION_CALL_LEDGER_MODE": "REQUIRED",
                "PIPELINE_MEASUREMENT_RUN_SPEC_SHA256": "f" * 64,
                "PIPELINE_MEASUREMENT_PAIR_ID": "shadow-r1",
                "PIPELINE_MEASUREMENT_ARM": "AFTER",
                "PIPELINE_MEASUREMENT_EXECUTION_MODE": (
                    "FRESH_SEMANTIC_OBSERVATION_REQUIRED"
                ),
                "PIPELINE_MEASUREMENT_MUTABLE_CONTEXT_MODE": "FROZEN_OFF",
                "PIPELINE_SLANG_DB": "0",
            }
        )
        self.assertTrue(config["fresh_execution_required"])
        self.assertTrue(config["semantic_drift_observation"])
        self.assertFalse(config["publication_decision_equivalence_required"])
        self.assertTrue(config["actual_kpi_eligible"])
        self.assertEqual(
            _measurement_execution_source(config),
            "FRESH_SHADOW_OBSERVATION_NO_PUBLIC_WRITE",
        )

    def test_shadow_config_rejects_early_route_and_strict_mode_is_unchanged(self) -> None:
        base = {
            "PIPELINE_DECISION_CALL_LEDGER_MODE": "REQUIRED",
            "PIPELINE_MEASUREMENT_RUN_SPEC_SHA256": "f" * 64,
            "PIPELINE_MEASUREMENT_PAIR_ID": "shadow-r1",
            "PIPELINE_MEASUREMENT_ARM": "AFTER",
            "PIPELINE_MEASUREMENT_MUTABLE_CONTEXT_MODE": "FROZEN_OFF",
            "PIPELINE_SLANG_DB": "0",
        }
        with self.assertRaisesRegex(ValueError, "forbids early-route"):
            _decision_call_measurement_config(
                {
                    **base,
                    "PIPELINE_MEASUREMENT_EXECUTION_MODE": (
                        "FRESH_SEMANTIC_OBSERVATION_REQUIRED"
                    ),
                    "PIPELINE_MEASUREMENT_EARLY_ROUTE_MODE": "SOURCE_ONLY_V1",
                }
            )
        strict = _decision_call_measurement_config(
            {
                **base,
                "PIPELINE_MEASUREMENT_EXECUTION_MODE": "FRESH_EXECUTION_REQUIRED",
                "PIPELINE_MEASUREMENT_EARLY_ROUTE_MODE": "OFF",
            }
        )
        self.assertTrue(strict["fresh_execution_required"])
        self.assertFalse(strict["semantic_drift_observation"])
        self.assertTrue(strict["publication_decision_equivalence_required"])
        self.assertEqual(
            _measurement_execution_source(strict),
            "FRESH_EXECUTION_NO_PUBLIC_WRITE",
        )

    def test_required_shadow_gate_binds_observed_preview_to_wal_authority(self) -> None:
        observation = build_publication_shadow_observation(
            observed_receipt=_receipt(decision="1", stable="2"),
            authoritative_receipt=_receipt(),
        )
        config = {
            "mode": "REQUIRED",
            "actual_kpi_eligible": True,
            "semantic_drift_observation": True,
        }
        summary = {
            "instrumentation_status": "ENABLED",
            "ledger_status": "COMPLETE",
            "actual_kpi_status": "PENDING_INDEPENDENT_READBACK",
            "reason_codes": [],
        }
        entry = {
            "ledger_ref": {
                "closure_kind": "ROW_SEAL",
                "row": {"input_index": 1, "post_id": 101},
            },
            "row_summary": {
                "writer_complete": True,
                "actual_kpi_status": "PENDING_INDEPENDENT_READBACK",
            },
            "attempt_receipt": {
                "publication_link_status": "LINKED_EXTERNAL_LEDGER",
                "publication_link_decision_id": (
                    observation["authoritative_decision"]["decision_id"]
                ),
                "publication_decision_id_preview": (
                    observation["observed_decision"]["decision_id"]
                ),
                "publication_shadow_observation": observation,
            },
        }
        gate = _build_decision_call_measurement_gate(
            measurement_config=config,
            ledger_summary=summary,
            row_attempts={1: entry},
            expected_input_count=1,
        )
        self.assertEqual(gate["status"], "GO")

        broken = deepcopy(entry)
        broken["attempt_receipt"]["publication_link_decision_id"] = "0" * 64
        gate = _build_decision_call_measurement_gate(
            measurement_config=config,
            ledger_summary=summary,
            row_attempts={1: broken},
            expected_input_count=1,
        )
        self.assertEqual(gate["status"], "NO_GO")
        self.assertIn(
            "ROW_SHADOW_OBSERVATION_AUTHORITY_LINK_MISMATCH",
            gate["reason_codes"],
        )

    def test_attempt_local_metadata_requires_final_exact_receipt_reseal(self) -> None:
        result = {
            "post_id": 101,
            "title": "",
            "error": "private test error",
            "analysis_result": {
                "identity": {
                    "is_relevant": False,
                    "novel_identity": None,
                }
            },
            "run_meta": {},
        }
        scope = "e" * 64
        initial = _preview_publication_decision(
            result,
            publication_scope_id=scope,
            attempt_run_id="attempt-shadow",
            input_index=1,
            post_id=101,
        )
        result.setdefault("run_meta", {})["publication_shadow_observation"] = {
            "attempt_local": True
        }
        with self.assertRaisesRegex(
            PublicationCommitError, "stored result no longer matches the receipt"
        ):
            validate_publication_result_commit(result, initial)

        final = _preview_publication_decision(
            result,
            publication_scope_id=scope,
            attempt_run_id="attempt-shadow",
            input_index=1,
            post_id=101,
        )
        self.assertEqual(initial.decision_id, final.decision_id)
        self.assertNotEqual(initial.result_sha256, final.result_sha256)
        validate_publication_result_commit(result, final)


if __name__ == "__main__":
    unittest.main()
