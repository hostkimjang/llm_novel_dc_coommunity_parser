from __future__ import annotations

import inspect
import unittest

from llm_batch.grounding import p0_actual_readiness_blocker_compiler_v2 as compiler
from llm_batch.grounding import p0_windows_owner_policy_v4_transition_fixed_store as transition


class ActualReadinessBlockerCompilerV2Tests(unittest.TestCase):
    @staticmethod
    def _rehash(receipt):
        material = dict(receipt)
        material.pop("receipt_sha256")
        return {**material, "receipt_sha256": compiler.canonical_sha256(material)}

    def test_public_api_is_zero_argument_and_current_receipt_is_no_go(self) -> None:
        self.assertEqual(
            list(inspect.signature(compiler.compile_fixed_p0_actual_readiness_blockers_v2).parameters),
            [],
        )
        receipt = compiler.compile_fixed_p0_actual_readiness_blockers_v2()
        self.assertEqual(tuple(receipt), compiler._RECEIPT_FIELDS)
        self.assertEqual(receipt["transition_status"], "VALID_COMPONENT_NO_GO")
        self.assertEqual(receipt["decision"], "NO_GO")
        self.assertEqual(receipt["credited_actual_selected_source_claim_unit_count"], 0)
        self.assertEqual(receipt["credited_actual_a_sampling_unit_count"], 0)
        self.assertTrue(all(receipt[field] is False for field in compiler._FALSE_FIELDS))

    def test_three_child_states_are_distinct(self) -> None:
        valid = compiler._execute_transition_once(
            transition.observe_fixed_windows_owner_policy_v4_transition_store
        )
        invalid = compiler._execute_transition_once(lambda: {})
        def fail():
            raise RuntimeError("boom")
        failed = compiler._execute_transition_once(fail)
        self.assertEqual(valid["status"], "VALID_COMPONENT_NO_GO")
        self.assertEqual(invalid["status"], "INVALID_TRANSITION_RECEIPT")
        self.assertEqual(failed["status"], "TRANSITION_EXECUTION_FAILED")
        self.assertEqual(
            [(row["executed"], row["validated"]) for row in (valid, invalid, failed)],
            [(True, True), (True, False), (False, False)],
        )

    def test_resealed_empty_success_child_is_rejected(self) -> None:
        forged = transition._failure_receipt("FIXED_STORE")
        forged["failure_stage"] = "EXTERNAL_STATE"
        forged["blocker_codes"] = list(transition._BLOCKERS[9:])
        for field in transition._TRUE_FIELDS:
            forged[field] = True
        material = dict(forged)
        material.pop("receipt_sha256")
        forged["receipt_sha256"] = transition.canonical_sha256(material)
        result = compiler._execute_transition_once(lambda: forged)
        self.assertEqual(result["status"], "INVALID_TRANSITION_RECEIPT")

    def test_output_helper_code_mutation_is_detected(self) -> None:
        original = compiler._validate_output.__code__
        def forged(receipt):
            return receipt
        try:
            compiler._validate_output.__code__ = forged.__code__
            with self.assertRaises(compiler.P0ActualReadinessBlockerCompilerV2Error):
                compiler.compile_fixed_p0_actual_readiness_blockers_v2()
        finally:
            compiler._validate_output.__code__ = original

    def test_endpoint_snapshot_and_compare_dependency_code_mutation_is_detected(self) -> None:
        original = compiler.compiler_v1._endpoint_comparison.__code__
        def forged(before, after):
            return True, True, True, True
        try:
            compiler.compiler_v1._endpoint_comparison.__code__ = forged.__code__
            with self.assertRaises(compiler.P0ActualReadinessBlockerCompilerV2Error):
                compiler._assert_integrity()
        finally:
            compiler.compiler_v1._endpoint_comparison.__code__ = original

    def test_transition_integrity_checker_mutation_is_detected(self) -> None:
        original = compiler.transition._assert_integrity.__code__
        def forged():
            return None
        try:
            compiler.transition._assert_integrity.__code__ = forged.__code__
            with self.assertRaises(compiler.P0ActualReadinessBlockerCompilerV2Error):
                compiler._assert_integrity()
        finally:
            compiler.transition._assert_integrity.__code__ = original

    def test_resealed_output_static_type_and_state_mutations_fail(self) -> None:
        baseline = compiler.compile_fixed_p0_actual_readiness_blockers_v2()
        mutations = (
            ("scope", "ATTACKER_SCOPE"),
            ("required_actual_selected_source_claim_unit_count", 40.0),
            ("transition_failure_stage", "ATTACKER_STAGE"),
            ("transition_component_manifest_sha256", "aa" * 32),
            ("local_endpoint_projection_before_sha256", "aa" * 32),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                forged = dict(baseline)
                forged[field] = value
                forged = self._rehash(forged)
                with self.assertRaises(compiler.P0ActualReadinessBlockerCompilerV2Error):
                    compiler._validate_output(forged)

    def test_coordinated_endpoint_projection_and_hash_reseal_fails(self) -> None:
        baseline = compiler.compile_fixed_p0_actual_readiness_blockers_v2()
        forged = dict(baseline)
        forged["local_endpoint_projection_after"] = [
            *forged["local_endpoint_projection_after"],
            {
                "kind": "PUBLICATION_JOURNAL",
                "path": "out/publication_commit_journals/attacker.jsonl",
                "bytes": 0,
                "mtime_ns": 0,
                "sha256": "00" * 32,
            },
        ]
        forged["local_endpoint_projection_after_sha256"] = compiler.canonical_sha256(
            forged["local_endpoint_projection_after"]
        )
        forged = self._rehash(forged)
        with self.assertRaises(compiler.P0ActualReadinessBlockerCompilerV2Error):
            compiler._validate_output(forged)

    def test_both_endpoint_projections_cannot_be_resealed_to_attacker_paths(self) -> None:
        baseline = compiler.compile_fixed_p0_actual_readiness_blockers_v2()
        forged = dict(baseline)
        attacker_projection = [
            {
                "kind": "CENTRAL_SLANG_DB", "path": "evil/db.json",
                "bytes": 1, "mtime_ns": 1, "sha256": "00" * 32,
            },
            {
                "kind": "PUBLICATION_JOURNAL", "path": "evil/j.jsonl",
                "bytes": 1, "mtime_ns": 1, "sha256": "11" * 32,
            },
        ]
        forged["local_endpoint_projection_before"] = attacker_projection
        forged["local_endpoint_projection_after"] = [dict(row) for row in attacker_projection]
        forged["local_endpoint_projection_before_sha256"] = compiler.canonical_sha256(
            forged["local_endpoint_projection_before"]
        )
        forged["local_endpoint_projection_after_sha256"] = compiler.canonical_sha256(
            forged["local_endpoint_projection_after"]
        )
        forged["local_endpoint_snapshot_before_succeeded"] = True
        forged["local_endpoint_snapshot_after_succeeded"] = True
        forged["required_local_endpoint_kinds_present_before"] = True
        forged["required_local_endpoint_kinds_present_after"] = True
        forged["local_endpoint_inventory_stable"] = True
        forged["local_endpoint_bytes_sha_stable"] = True
        forged["local_endpoint_mtime_stable"] = True
        forged["compiler_pre_post_endpoint_projection_match_observed"] = True
        forged["blocker_codes"] = list(compiler._BASE_BLOCKERS)
        forged = self._rehash(forged)
        with self.assertRaises(compiler.P0ActualReadinessBlockerCompilerV2Error):
            compiler._validate_output(forged)

    def test_publication_backslash_traversal_reseal_fails(self) -> None:
        baseline = compiler.compile_fixed_p0_actual_readiness_blockers_v2()
        forged = dict(baseline)
        malicious = [dict(row) for row in baseline["local_endpoint_projection_before"]]
        journal = next(row for row in malicious if row["kind"] == "PUBLICATION_JOURNAL")
        journal["path"] = "out/publication_commit_journals/..\\evil.jsonl"
        forged["local_endpoint_projection_before"] = malicious
        forged["local_endpoint_projection_after"] = [dict(row) for row in malicious]
        forged["local_endpoint_projection_before_sha256"] = compiler.canonical_sha256(malicious)
        forged["local_endpoint_projection_after_sha256"] = compiler.canonical_sha256(malicious)
        forged = self._rehash(forged)
        with self.assertRaises(compiler.P0ActualReadinessBlockerCompilerV2Error):
            compiler._validate_output(forged)

    def test_transition_success_counts_require_exact_int_types(self) -> None:
        source = inspect.getsource(compiler._validate_transition_receipt)
        self.assertIn('type(receipt["role_handle_count"]) is not int', source)
        self.assertIn('type(receipt["file_handle_count"]) is not int', source)

    def test_resealed_invalid_state_cannot_carry_valid_child_binding(self) -> None:
        baseline = compiler.compile_fixed_p0_actual_readiness_blockers_v2()
        forged = dict(baseline)
        forged["transition_status"] = "INVALID_TRANSITION_RECEIPT"
        forged["transition_observer_executed_once"] = True
        forged["transition_receipt_strictly_validated"] = False
        forged["transition_failure_stage"] = "FIXED_STORE"
        forged["blocker_codes"] = [
            *compiler._BASE_BLOCKERS[:-1],
            "V3_V4_TRANSITION_RECEIPT_NOT_VERIFIED",
            *(
                ["LOCAL_ENDPOINT_SNAPSHOT_NOT_VERIFIED"]
                if not (
                    forged["local_endpoint_snapshot_before_succeeded"]
                    and forged["local_endpoint_snapshot_after_succeeded"]
                    and forged["required_local_endpoint_kinds_present_before"]
                    and forged["required_local_endpoint_kinds_present_after"]
                )
                else []
            ),
            compiler._BASE_BLOCKERS[-1],
        ]
        forged = self._rehash(forged)
        with self.assertRaises(compiler.P0ActualReadinessBlockerCompilerV2Error):
            compiler._validate_output(forged)


if __name__ == "__main__":
    unittest.main()
