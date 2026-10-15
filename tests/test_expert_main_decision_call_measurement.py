from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from expert_main import (
    _build_decision_call_measurement_gate,
    _build_runtime_completion_gate,
    _decision_affecting_publication_config,
    _decision_call_measurement_config,
    _fresh_execution_authoritative_reference_for_row,
    _large_run_complete_from_gates,
    _preview_publication_decision,
    _publication_decision_environment,
    _require_fresh_execution_authoritative_references,
)
from src.llm_batch.ledger.publication_commit import (
    PublicationCommitRegistry,
    commit_publication_result,
)
from tests.test_publication_decision_commit import _scope_descriptor, _valid_result


class DecisionCallMeasurementConfigTest(unittest.TestCase):
    def test_default_is_disabled_and_unbound(self) -> None:
        config = _decision_call_measurement_config({})
        self.assertEqual(config["mode"], "OFF")
        self.assertEqual(config["binding_status"], "UNBOUND")
        self.assertFalse(config["actual_kpi_eligible"])

    def test_shadow_partial_binding_stays_ineligible(self) -> None:
        config = _decision_call_measurement_config(
            {
                "PIPELINE_DECISION_CALL_LEDGER_MODE": "shadow",
                "PIPELINE_MEASUREMENT_PAIR_ID": "pair-a",
            }
        )
        self.assertEqual(config["binding_status"], "PARTIAL_UNBOUND")
        self.assertFalse(config["actual_kpi_eligible"])

    def test_off_mode_rejects_measurement_binding(self) -> None:
        with self.assertRaisesRegex(ValueError, "measurement bindings require"):
            _decision_call_measurement_config(
                {"PIPELINE_MEASUREMENT_PAIR_ID": "pair-a"}
            )

    def test_required_mode_rejects_incomplete_or_nonfresh_binding(self) -> None:
        with self.assertRaisesRegex(ValueError, "REQUIRED decision call measurement"):
            _decision_call_measurement_config(
                {"PIPELINE_DECISION_CALL_LEDGER_MODE": "REQUIRED"}
            )
        with self.assertRaisesRegex(ValueError, "REQUIRED decision call measurement"):
            _decision_call_measurement_config(
                {
                    "PIPELINE_DECISION_CALL_LEDGER_MODE": "REQUIRED",
                    "PIPELINE_MEASUREMENT_RUN_SPEC_SHA256": "a" * 64,
                    "PIPELINE_MEASUREMENT_PAIR_ID": "pair-a",
                    "PIPELINE_MEASUREMENT_ARM": "BEFORE",
                    "PIPELINE_MEASUREMENT_EXECUTION_MODE": "NORMAL",
                }
            )

    def test_required_complete_fresh_binding_is_eligible(self) -> None:
        config = _decision_call_measurement_config(
            {
                "PIPELINE_DECISION_CALL_LEDGER_MODE": "REQUIRED",
                "PIPELINE_MEASUREMENT_RUN_SPEC_SHA256": "a" * 64,
                "PIPELINE_MEASUREMENT_PAIR_ID": "pair-a",
                "PIPELINE_MEASUREMENT_ARM": "AFTER",
                "PIPELINE_MEASUREMENT_EXECUTION_MODE": "FRESH_EXECUTION_REQUIRED",
                "PIPELINE_MEASUREMENT_MUTABLE_CONTEXT_MODE": "FROZEN_OFF",
            }
        )
        self.assertEqual(config["binding_status"], "BOUND")
        self.assertTrue(config["fresh_execution_required"])
        self.assertTrue(config["actual_kpi_eligible"])
        self.assertTrue(config["mutable_context_frozen"])

    def test_invalid_hash_arm_and_execution_mode_fail(self) -> None:
        with self.assertRaisesRegex(ValueError, "lowercase sha256"):
            _decision_call_measurement_config(
                {
                    "PIPELINE_DECISION_CALL_LEDGER_MODE": "SHADOW",
                    "PIPELINE_MEASUREMENT_RUN_SPEC_SHA256": "not-a-hash",
                }
            )

    def test_measurement_binding_does_not_change_publication_decision_config(self) -> None:
        before = {
            "llm_model": "model-a",
            "prompt_version": "prompt-v1",
            "decision_call_measurement": {
                "mode": "REQUIRED",
                "pair_id": "pair-1",
                "arm": "BEFORE",
            },
        }
        after = {
            **before,
            "decision_call_measurement": {
                "mode": "REQUIRED",
                "pair_id": "pair-1",
                "arm": "AFTER",
            },
        }
        self.assertEqual(
            _decision_affecting_publication_config(before),
            _decision_affecting_publication_config(after),
        )
        self.assertNotIn(
            "decision_call_measurement",
            _decision_affecting_publication_config(before),
        )

    def test_actual_environment_path_excludes_all_measurement_keys_but_keeps_decision_keys(self) -> None:
        base = {
            "LLM_MODEL": "decision-model-a",
            "PIPELINE_REASON_FULL_MODE": "1",
            "PIPELINE_DECISION_CALL_LEDGER_MODE": "REQUIRED",
            "PIPELINE_DECISION_CALL_PAIR_ID": "pair-before",
            "PIPELINE_DECISION_CALL_ARM": "BEFORE",
            "PIPELINE_DECISION_CALL_RUN_SPEC_SHA256": "a" * 64,
            "PIPELINE_DECISION_CALL_EXECUTION_SOURCE": "FRESH_EXECUTION_NO_PUBLIC_WRITE",
            "PIPELINE_MEASUREMENT_RUN_SPEC_SHA256": "a" * 64,
            "PIPELINE_MEASUREMENT_PAIR_ID": "pair-before",
            "PIPELINE_MEASUREMENT_ARM": "BEFORE",
            "PIPELINE_MEASUREMENT_EXECUTION_MODE": "FRESH_EXECUTION_REQUIRED",
        }
        changed_measurement = {
            **base,
            "PIPELINE_DECISION_CALL_PAIR_ID": "pair-after",
            "PIPELINE_DECISION_CALL_ARM": "AFTER",
            "PIPELINE_DECISION_CALL_RUN_SPEC_SHA256": "b" * 64,
            "PIPELINE_MEASUREMENT_RUN_SPEC_SHA256": "b" * 64,
            "PIPELINE_MEASUREMENT_PAIR_ID": "pair-after",
            "PIPELINE_MEASUREMENT_ARM": "AFTER",
        }
        with patch.dict(os.environ, base, clear=True):
            before = _publication_decision_environment()
        with patch.dict(os.environ, changed_measurement, clear=True):
            after = _publication_decision_environment()

        digest = lambda value: hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        self.assertEqual(before, after)
        self.assertEqual(digest(before), digest(after))
        self.assertEqual(before["LLM_MODEL"], "decision-model-a")
        self.assertEqual(before["PIPELINE_REASON_FULL_MODE"], "1")
        self.assertFalse(
            any(key.startswith("PIPELINE_DECISION_CALL_") for key in before)
        )
        self.assertFalse(any(key.startswith("PIPELINE_MEASUREMENT_") for key in before))

        with patch.dict(
            os.environ,
            {**changed_measurement, "LLM_MODEL": "decision-model-b"},
            clear=True,
        ):
            changed_decision = _publication_decision_environment()
        self.assertNotEqual(digest(before), digest(changed_decision))

    def test_fresh_execution_rejects_empty_and_partial_authoritative_wal(self) -> None:
        scope = _scope_descriptor((101, 102))
        with tempfile.TemporaryDirectory() as tmp:
            registry = PublicationCommitRegistry(
                Path(tmp) / "publication.jsonl",
                scope_descriptor=scope,
                create_new=True,
            )
            with self.assertRaisesRegex(
                Exception,
                "FRESH_EXECUTION_NO_PUBLIC_WRITE requires an authoritative WAL",
            ):
                _require_fresh_execution_authoritative_references(
                    {},
                    post_ids=[101, 102],
                )

            receipt, created = commit_publication_result(
                _valid_result(post_id=101),
                registry=registry,
                attempt_run_id="authoritative-before",
                input_index=1,
                post_id=101,
            )
            self.assertTrue(created)
            references = {1: (registry.result(101), receipt)}
            self.assertEqual(
                _fresh_execution_authoritative_reference_for_row(
                    references,
                    input_index=1,
                    post_id=101,
                )[1].decision_id,
                receipt.decision_id,
            )
            with self.assertRaisesRegex(
                Exception,
                "missing=2:102",
            ):
                _require_fresh_execution_authoritative_references(
                    references,
                    post_ids=[101, 102],
                )

    def test_required_measurement_failures_block_large_run_completion(self) -> None:
        required = {
            "mode": "REQUIRED",
            "actual_kpi_eligible": True,
        }
        complete_summary = {
            "instrumentation_status": "ENABLED",
            "ledger_status": "COMPLETE",
            "actual_kpi_status": "PENDING_INDEPENDENT_READBACK",
            "reason_codes": [],
        }
        linked_entry = {
            "ledger_ref": {"closure_kind": "ROW_SEAL"},
            "row_summary": {
                "writer_complete": True,
                "actual_kpi_status": "PENDING_INDEPENDENT_READBACK",
            },
            "attempt_receipt": {
                "publication_link_status": "LINKED_EXTERNAL_LEDGER",
            },
        }
        runtime_complete = _build_runtime_completion_gate(
            input_post_count=1,
            completed_count=1,
            pending_count=0,
            failed_count=0,
            terminal_artifacts_finalized=True,
        )
        self.assertEqual(runtime_complete["status"], "GO")
        self.assertTrue(
            _large_run_complete_from_gates(
                runtime_complete,
                _build_decision_call_measurement_gate(
                    measurement_config=required,
                    ledger_summary=complete_summary,
                    row_attempts={1: linked_entry},
                    expected_input_count=1,
                ),
            )
        )

        cases = {
            "external_link_failed": (
                complete_summary,
                {
                    **linked_entry,
                    "attempt_receipt": {
                        "publication_link_status": "LINK_FAILED_NOT_ESTIMABLE",
                    },
                },
                "ROW_EXTERNAL_LEDGER_UNLINKED",
            ),
            "row_not_estimable": (
                complete_summary,
                {
                    **linked_entry,
                    "row_summary": {
                        "writer_complete": False,
                        "actual_kpi_status": "NOT_ESTIMABLE",
                    },
                },
                "ROW_NOT_ESTIMABLE",
            ),
            "ambiguous_or_unlinked_ledger": (
                {
                    **complete_summary,
                    "ledger_status": "PARTIAL",
                    "actual_kpi_status": "NOT_ESTIMABLE",
                    "reason_codes": [
                        "AMBIGUOUS_MULTIPLE_ATTEMPT_RUNS",
                        "UNLINKED_ROW_ATTEMPT",
                    ],
                },
                linked_entry,
                "LEDGER_AMBIGUOUS_MULTIPLE_ATTEMPT_RUNS",
            ),
        }
        for name, (summary, row_entry, expected_reason) in cases.items():
            with self.subTest(name=name):
                gate = _build_decision_call_measurement_gate(
                    measurement_config=required,
                    ledger_summary=summary,
                    row_attempts={1: row_entry},
                    expected_input_count=1,
                )
                self.assertEqual(gate["status"], "NO_GO")
                self.assertTrue(gate["blocks_large_run_complete"])
                self.assertIn(expected_reason, gate["reason_codes"])
                self.assertFalse(_large_run_complete_from_gates(runtime_complete, gate))

    def test_measurement_preview_is_state_free_and_checks_reference_decision(self) -> None:
        scope = _scope_descriptor((101,)).publication_scope_id
        baseline = _valid_result(post_id=101)
        reference = _preview_publication_decision(
            baseline,
            publication_scope_id=scope,
            attempt_run_id="before-run",
            input_index=1,
            post_id=101,
        )
        after = _valid_result(post_id=101)
        after["run_meta"] = {
            "decision_call_measurement": {"pair_id": "pair-1", "arm": "AFTER"},
            "measurement_execution_source": "FRESH_EXECUTION_NO_PUBLIC_WRITE",
        }
        replay = _preview_publication_decision(
            after,
            publication_scope_id=scope,
            attempt_run_id="after-run",
            input_index=1,
            post_id=101,
            reference_receipt=reference,
        )
        self.assertEqual(reference.decision_id, replay.decision_id)

    def test_expert_main_wires_full_row_lifecycle_and_no_public_write_mode(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "expert_main.py").read_text(
            encoding="utf-8"
        )
        for token in (
            "DecisionTracingLLMClient(",
            ".begin_row_attempt(",
            ".seal_row_attempt()",
            ".abort_row_attempt(",
            "decision_call_ledger_registry.link_publication(",
            '"FRESH_EXECUTION_NO_PUBLIC_WRITE"',
            '"decision_call_ledger_production_enable_allowed": False',
        ):
            self.assertIn(token, source)
        with self.assertRaisesRegex(ValueError, "BEFORE or AFTER"):
            _decision_call_measurement_config(
                {
                    "PIPELINE_DECISION_CALL_LEDGER_MODE": "SHADOW",
                    "PIPELINE_MEASUREMENT_ARM": "CONTROL",
                }
            )
        with self.assertRaisesRegex(ValueError, "NORMAL, FRESH_EXECUTION_REQUIRED, or FRESH_SEMANTIC_OBSERVATION_REQUIRED"):
            _decision_call_measurement_config(
                {
                    "PIPELINE_DECISION_CALL_LEDGER_MODE": "SHADOW",
                    "PIPELINE_MEASUREMENT_EXECUTION_MODE": "REPLAY",
                }
            )
        for execution_mode in ("NORMAL", "FRESH_EXECUTION_REQUIRED", "FRESH_SEMANTIC_OBSERVATION_REQUIRED"):
            with self.subTest(execution_mode=execution_mode):
                config = _decision_call_measurement_config({
                    "PIPELINE_DECISION_CALL_LEDGER_MODE": "SHADOW",
                    "PIPELINE_MEASUREMENT_EXECUTION_MODE": execution_mode,
                })
                self.assertEqual(config["execution_mode"], execution_mode)


if __name__ == "__main__":
    unittest.main()
