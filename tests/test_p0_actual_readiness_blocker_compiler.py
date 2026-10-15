from __future__ import annotations

from copy import deepcopy
import hashlib
import inspect
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from llm_batch.grounding import p0_actual_authority_contract as authority
from llm_batch.grounding import p0_actual_packet_contract as packet
from llm_batch.grounding import p0_actual_readiness_blocker_compiler as compiler
from llm_batch.grounding import p0_actual_route_contract as route
from llm_batch.grounding import p0_windows_runtime_evidence as runtime


EXPECTED_CHILD_BLOCKERS = [
    "FIXED_OWNER_POLICY_STORE_NOT_VERIFIED",
    "OWNER_POLICY_V2_NOT_VERIFIED",
    "SERVICE_CONFIGURATION_NOT_VERIFIED",
    "SERVICE_IMAGE_IDENTITY_NOT_VERIFIED",
    "SERVICE_PROCESS_TOKEN_NOT_VERIFIED",
    "EMBEDDED_BOOTSTRAP_RESOURCE_NOT_VERIFIED",
    "AUTHENTICODE_NOT_VERIFIED",
    "WDAC_UMCI_NOT_VERIFIED",
    "LOADED_CNG_PROVIDER_NOT_VERIFIED",
    "TRUSTED_TIME_REVOCATION_NOT_VERIFIED",
    "SIGNED_NATIVE_OBSERVER_NOT_VERIFIED",
    "SINGLE_INTERVAL_STORE_HOST_BINDING_NOT_VERIFIED",
    "EXTERNAL_OWNER_PROVISIONING_NOT_VERIFIED",
]
EXPECTED_OUTER_BLOCKERS = [
    "OWNER_PROVISIONING_PREFLIGHT_NO_GO",
    "SIGNED_NATIVE_OBSERVER_NOT_VERIFIED",
    "EXTERNAL_OWNER_TRUST_NOT_VERIFIED",
    "TRUSTED_TIME_NOT_VERIFIED",
    "REVOCATION_CURRENT_NOT_VERIFIED",
    "DURABLE_CROSS_PROCESS_NONCE_NOT_VERIFIED",
    "PROTECTED_ROOT_OWNER_PINS_NOT_VERIFIED",
    "PROTECTED_WATCH_6_CATEGORY_COVERAGE_NOT_VERIFIED",
    "PROCESS_WIDE_WRITE_DENY_NOT_VERIFIED",
    "AUTHORITY_JOURNAL_WATCH_BUNDLE_NOT_VERIFIED",
    "RUNTIME_NONINTERFERENCE_NOT_VERIFIED",
    "PARSER_RUNTIME_NOT_RUN",
    "ACTUAL_POLICY_AUTHORITY_NOT_VERIFIED",
    "ACTUAL_CAPTURE_RIGHTS_POLICY_NOT_AUTHORIZED",
    "ACTUAL_SAMPLING_PLAN_NOT_AUTHORIZED",
    "ACTUAL_ANNOTATION_GUIDELINE_NOT_AUTHORIZED",
    "ACTUAL_REVIEWER_ASSIGNMENT_NOT_AUTHORIZED",
    "ACTUAL_ANNOTATION_DURABLE_PREDECESSOR_NOT_VERIFIED",
    "ACTUAL_ANNOTATION_APPEND_ONLY_NOT_VERIFIED",
    "ACTUAL_SOURCE_CLAIMS_CREDITED_0_OF_40",
    "ACTUAL_A_CONTEXT_REVIEWS_CREDITED_0_OF_20",
    "ACTUAL_SEMANTIC_EVIDENCE_NOT_VERIFIED",
    "P1_RETRIEVAL_RERANKER_NIL_SHADOW_BLOCKED_BY_P0",
    "BLOCKER_ONLY_COMPILER_NOT_AUTHORITY",
]
EXPECTED_FALSE_OUTPUT_FIELDS = {
    "capture_execution_authorized",
    "runtime_execution_entrypoint_invoked",
    "process_spawned",
    "service_started",
    "nonce_consumption_invoked",
    "publication_wal_write_invoked_by_compiler",
    "central_slang_db_write_invoked_by_compiler",
    "action_applied",
    "protected_pipeline_state_mutated",
    "host_preflight_freshness_verified",
    "signed_native_observer_receipt_verified",
    "external_owner_trust_verified",
    "trusted_time_verified",
    "revocation_current_verified",
    "durable_cross_process_nonce_verified",
    "protected_root_owner_pins_verified",
    "protected_watch_six_category_coverage_verified",
    "process_wide_write_deny_verified",
    "authority_journal_watch_bundle_verified",
    "continuous_runtime_noninterference_verified",
    "transient_write_absence_verified",
    "runtime_noninterference_verified",
    "parser_runtime_verified",
    "actual_policy_authority_verified",
    "actual_annotation_durable_predecessor_verified",
    "actual_annotation_append_only_verified",
    "actual_authority_granted",
    "actual_semantic_evidence_verified",
    "p0_phase_exit",
    "production_approval",
    "full_scan_approval",
    "serialized_receipt_authoritative",
}
EXPECTED_WATCH_CATEGORIES = [
    "CENTRAL_SLANG_DB",
    "CHECKPOINT",
    "DECISION_LEDGER",
    "PUBLICATION_JOURNAL",
    "RECOVERY",
    "RESULT",
]


def _sha(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _rehash(value: dict[str, object]) -> dict[str, object]:
    value.pop("receipt_sha256", None)
    value["receipt_sha256"] = _sha(value)
    return value


def _current_child() -> dict[str, object]:
    return compiler.preflight.observe_fixed_windows_owner_provisioning_preflight_candidate()


def _fixed_store_candidate() -> dict[str, object]:
    material: dict[str, object] = {
        "schema_version": (
            "p0_windows_owner_provisioning_preflight_candidate_receipt_v1"
        ),
        "gate_status": (
            "WINDOWS_OWNER_PROVISIONING_PREFLIGHT_CANDIDATE_EXECUTED_"
            "HOST_AND_EXTERNAL_PROVISIONING_NO_GO"
        ),
        "decision": "NO_GO",
        "failure_stage": "FIXED_STORE",
        "blocker_codes": list(EXPECTED_CHILD_BLOCKERS),
        "candidate_only": True,
        "zero_input_public_api_verified": True,
        "caller_supplied_selector_absent": True,
        "fixed_policy_store_candidate_observed": False,
        "owner_policy_v2_contract_verified": False,
        "v1_future_authority_hard_rejected": False,
        "bootstrap_signature_mathematics_verified": False,
        "deployment_projection_cross_binding_verified": False,
        "service_configuration_candidate_verified": False,
        "service_image_identity_candidate_verified": False,
        "service_configuration_projection": {},
        "service_image_identity_projection": {},
        "credited_actual_source_claim_count": 0,
        "credited_actual_a_context_review_count": 0,
        "operational_effect": "NONE_SHADOW_ONLY",
    }
    for field in (
        "service_process_token_verified",
        "embedded_bootstrap_resource_verified",
        "trusted_verifier_code_identity_verified",
        "wdac_umci_enforced_verified",
        "wdac_policy_identity_hash_verified",
        "loaded_cng_provider_identity_verified",
        "trusted_cng_provider_provenance_verified",
        "trusted_time_verified",
        "revocation_current_verified",
        "signed_native_observer_receipt_verified",
        "single_interval_store_host_cross_binding_verified",
        "serialized_receipt_authoritative",
        "external_owner_policy_provisioning_verified",
        "external_code_authority_verified",
        "owner_authority_verified",
        "actual_authority_granted",
        "actual_semantic_evidence_verified",
        "production_approval",
        "full_scan_approval",
        "p0_phase_exit",
        "action_applied",
        "protected_pipeline_state_mutated",
    ):
        material[field] = False
    return _rehash(material)


def _all_green_candidate() -> dict[str, object]:
    receipt = _fixed_store_candidate()
    for field in (
        "fixed_policy_store_candidate_observed",
        "owner_policy_v2_contract_verified",
        "v1_future_authority_hard_rejected",
        "bootstrap_signature_mathematics_verified",
        "deployment_projection_cross_binding_verified",
        "service_configuration_candidate_verified",
        "service_image_identity_candidate_verified",
    ):
        receipt[field] = True
    receipt["failure_stage"] = "NATIVE_EXTERNAL_EVIDENCE"
    receipt["blocker_codes"] = EXPECTED_CHILD_BLOCKERS[4:]
    image_path = (
        "\\\\?\\Volume{01234567-89ab-cdef-0123-456789abcdef}"
        "\\owner\\verifier.exe"
    )
    receipt["service_configuration_projection"] = {
        "service_name": "llm-novel-dc-p0-owner-verifier-v2",
        "service_type": "SERVICE_WIN32_OWN_PROCESS",
        "service_start_type": "SERVICE_DEMAND_START",
        "service_error_control": "SERVICE_ERROR_NORMAL",
        "service_sid_type": "SERVICE_SID_TYPE_RESTRICTED",
        "service_start_account_sid": "S-1-5-18",
        "service_binary_path_argv_policy": "EXACT_QUOTED_IMAGE_PATH_NO_ARGUMENTS",
        "raw_binary_path_sha256": hashlib.sha256(
            f'"{image_path}"'.encode("utf-16-le")
        ).hexdigest(),
    }
    receipt["service_image_identity_projection"] = {
        "final_volume_guid_path": image_path,
        "volume_serial_decimal": "123456789",
        "file_id_128_hex": "a" * 32,
        "image_sha256": "b" * 64,
        "held_handle_pre_post_stable": True,
        "single_link_non_reparse_unnamed_stream_verified": True,
        "handle_non_inheritable_verified": True,
    }
    return _rehash(receipt)


def _stable_snapshot(tag: str = "a") -> dict[str, object]:
    rows = [
        {
            "kind": "CENTRAL_SLANG_DB",
            "path": "slang_db/slang_db.json",
            "bytes": 10,
            "mtime_ns": 100,
            "sha256": tag * 64,
        },
        {
            "kind": "PUBLICATION_JOURNAL",
            "path": "out/publication_commit_journals/a.jsonl",
            "bytes": 20,
            "mtime_ns": 200,
            "sha256": "b" * 64,
        },
    ]
    return {
        "snapshot_succeeded": True,
        "required_local_endpoint_kinds_present": True,
        "projection": rows,
        "projection_sha256": _sha(rows),
    }


class ActualReadinessBlockerCompilerTests(unittest.TestCase):
    def test_public_api_is_zero_argument_and_static_boundary_is_read_only(self):
        self.assertEqual(
            tuple(
                inspect.signature(
                    compiler.compile_fixed_p0_actual_readiness_blockers
                ).parameters
            ),
            (),
        )
        source = inspect.getsource(compiler).casefold()
        for forbidden in (
            "os.environ",
            "os.getenv",
            "path.cwd",
            "path.home",
            "sys.argv",
            "subprocess",
            "powershell",
            "sc.exe",
            "sqlite",
            "requests",
            "urllib",
            "socket",
            "execute_external_owner_trust",
            "execute_windows_runtime_evidence",
            "execute_packet_supervisor_trace",
            "execute_authority_supervisor_trace",
            "parser_process_worker",
            "llm_batch.slang",
            ".write_text(",
            ".write_bytes(",
            ".mkdir(",
            ".replace(",
            ".unlink(",
        ):
            self.assertNotIn(forbidden, source)

    def test_current_host_is_exact_no_go_and_six_endpoints_are_stable(self):
        receipt = compiler.compile_fixed_p0_actual_readiness_blockers()
        self.assertEqual(receipt["decision"], "NO_GO")
        self.assertEqual(receipt["host_preflight_status"], "VALID_CANDIDATE_NO_GO")
        self.assertEqual(receipt["blocker_codes"], EXPECTED_OUTER_BLOCKERS)
        if receipt["host_preflight_failure_stage"] == "FIXED_STORE":
            self.assertEqual(
                receipt["host_preflight_blocker_codes"], EXPECTED_CHILD_BLOCKERS
            )
            self.assertEqual(
                receipt["host_preflight_receipt_binding"][
                    "declared_receipt_sha256"
                ],
                "bbed3cdd9d309f22db22fe9607b9000f31d924b8ed3c677b9dbbfadf2351a172",
            )
        self.assertTrue(
            receipt["compiler_pre_post_endpoint_projection_match_observed"]
        )
        self.assertGreaterEqual(
            len(receipt["local_endpoint_projection_before"]), 2
        )
        self.assertEqual(
            receipt["local_endpoint_projection_before"],
            receipt["local_endpoint_projection_after"],
        )

    def test_targets_watch_categories_and_false_fields_are_independent_oracles(self):
        receipt = compiler.compile_fixed_p0_actual_readiness_blockers()
        self.assertEqual(
            receipt["required_source_profiles"],
            [
                "OFFICIAL_STRUCTURED",
                "COMMUNITY_STRUCTURED",
                "MEDIA_OCR",
                "GENERIC_FALLBACK",
            ],
        )
        self.assertEqual(receipt["required_per_profile_quota"], 10)
        self.assertEqual(
            receipt["required_actual_selected_source_claim_unit_count"], 40
        )
        self.assertEqual(receipt["required_actual_a_sampling_unit_count"], 20)
        self.assertEqual(
            receipt["observed_actual_selected_source_claim_unit_count"], 0
        )
        self.assertEqual(receipt["observed_actual_source_claim_row_count"], 0)
        self.assertEqual(receipt["observed_actual_a_sampling_unit_count"], 0)
        self.assertEqual(receipt["observed_actual_a_annotation_event_count"], 0)
        self.assertEqual(
            receipt["credited_actual_selected_source_claim_unit_count"], 0
        )
        self.assertEqual(receipt["credited_actual_a_sampling_unit_count"], 0)
        self.assertEqual(list(route.SOURCE_PROFILES), receipt["required_source_profiles"])
        self.assertEqual(route.EXPECTED_PER_PROFILE_QUOTA, 10)
        self.assertEqual(route.EXPECTED_INPUT_COUNT, 40)
        self.assertEqual(packet.EXPECTED_A_CONTEXT_COUNT, 20)
        self.assertEqual(receipt["required_actual_watch_categories"], EXPECTED_WATCH_CATEGORIES)
        self.assertEqual(list(authority.REQUIRED_WATCH_CATEGORIES), EXPECTED_WATCH_CATEGORIES)
        self.assertEqual(list(runtime.REQUIRED_PROTECTED_CATEGORIES), EXPECTED_WATCH_CATEGORIES)
        self.assertEqual(
            receipt["source_credit_unit_definition"],
            "LABEL_BLIND_UNIQUE_SELECTED_CLAIM_UNIT_SOURCE_SNAPSHOT_PROFILE_10X4",
        )
        self.assertEqual(
            receipt["a_context_credit_unit_definition"],
            "UNIQUE_SAMPLING_UNIT_WITH_BOUND_PRIMARY_HUMAN_JOURNAL",
        )
        self.assertEqual(
            receipt["selected_a_context_denominator_includes_statuses"],
            ["JUDGED", "UNJUDGED", "UNAVAILABLE"],
        )
        self.assertEqual(
            receipt["observed_a_annotation_status_counts"],
            {"JUDGED": 0, "UNJUDGED": 0, "UNAVAILABLE": 0},
        )
        self.assertEqual(receipt["annotation_coverage_numerator_judged"], 0)
        self.assertEqual(
            receipt["annotation_coverage_denominator"],
            "ALL_SELECTED_20_INCLUDING_UNJUDGED_UNAVAILABLE",
        )
        self.assertEqual(receipt["terminal_accuracy_denominator"], "JUDGED_ONLY")
        self.assertEqual(receipt["worst_case_denominator"], "ALL_SELECTED_20")
        self.assertIs(
            receipt["one_to_many_claim_rows_increase_selected_unit_credit"],
            False,
        )
        self.assertIs(
            receipt["recheck_events_increase_a_sampling_unit_credit"], False
        )
        self.assertIs(receipt["synthetic_or_structural_evidence_creditable"], False)
        for field in EXPECTED_FALSE_OUTPUT_FIELDS:
            self.assertIn(field, receipt)
            self.assertIs(receipt[field], False)

    def test_all_green_self_hashed_candidate_remains_non_authoritative_no_go(self):
        child = _all_green_candidate()
        with patch.object(
            compiler.preflight,
            "observe_fixed_windows_owner_provisioning_preflight_candidate",
            return_value=child,
        ) as observe:
            receipt = compiler.compile_fixed_p0_actual_readiness_blockers()
        observe.assert_called_once_with()
        self.assertTrue(receipt["host_preflight_receipt_validated"])
        self.assertEqual(receipt["host_preflight_failure_stage"], "NATIVE_EXTERNAL_EVIDENCE")
        self.assertEqual(receipt["decision"], "NO_GO")
        self.assertEqual(receipt["blocker_codes"][-1], "BLOCKER_ONLY_COMPILER_NOT_AUTHORITY")
        self.assertEqual(
            receipt["credited_actual_selected_source_claim_unit_count"], 0
        )
        self.assertEqual(receipt["credited_actual_a_sampling_unit_count"], 0)
        for field in EXPECTED_FALSE_OUTPUT_FIELDS:
            self.assertIs(receipt[field], False)

    def test_resealed_forged_receipts_fail_closed_without_echoing_raw_input(self):
        base = _fixed_store_candidate()
        mutations = []
        for name, mutate in (
            ("decision", lambda row: row.__setitem__("decision", "GO")),
            ("authority", lambda row: row.__setitem__("actual_authority_granted", True)),
            ("production", lambda row: row.__setitem__("production_approval", True)),
            ("count", lambda row: row.__setitem__("credited_actual_source_claim_count", 40)),
            ("bool_count", lambda row: row.__setitem__("credited_actual_source_claim_count", False)),
            ("stage", lambda row: row.__setitem__("failure_stage", "NATIVE_EXTERNAL_EVIDENCE")),
            ("blocker_omission", lambda row: row["blocker_codes"].pop()),
            ("blocker_reorder", lambda row: row["blocker_codes"].reverse()),
            ("extra_field", lambda row: row.__setitem__("secret_marker", "DO_NOT_ECHO")),
        ):
            forged = deepcopy(base)
            mutate(forged)
            mutations.append((name, _rehash(forged)))
        missing = deepcopy(base)
        missing.pop("gate_status")
        mutations.append(("missing_field", _rehash(missing)))
        for name, forged in mutations:
            with self.subTest(name=name), patch.object(
                compiler.preflight,
                "observe_fixed_windows_owner_provisioning_preflight_candidate",
                return_value=forged,
            ):
                receipt = compiler.compile_fixed_p0_actual_readiness_blockers()
                self.assertFalse(receipt["host_preflight_receipt_validated"])
                self.assertEqual(receipt["host_preflight_status"], "INVALID_RECEIPT")
                self.assertEqual(
                    receipt["host_preflight_blocker_codes"],
                    ["HOST_PREFLIGHT_RECEIPT_NOT_VERIFIED"],
                )
                self.assertNotIn("DO_NOT_ECHO", json.dumps(receipt))
                self.assertEqual(receipt["decision"], "NO_GO")
                self.assertIn(
                    "HOST_PREFLIGHT_RECEIPT_NOT_VERIFIED",
                    receipt["blocker_codes"],
                )

    def test_non_dict_and_observer_exception_normalize_but_base_exceptions_propagate(self):
        for invalid in (None, [], SimpleNamespace(value="secret")):
            with self.subTest(value=type(invalid).__name__), patch.object(
                compiler.preflight,
                "observe_fixed_windows_owner_provisioning_preflight_candidate",
                return_value=invalid,
            ):
                receipt = compiler.compile_fixed_p0_actual_readiness_blockers()
                self.assertEqual(receipt["host_preflight_status"], "INVALID_RECEIPT")
        with patch.object(
            compiler.preflight,
            "observe_fixed_windows_owner_provisioning_preflight_candidate",
            side_effect=RuntimeError("secret raw exception"),
        ):
            receipt = compiler.compile_fixed_p0_actual_readiness_blockers()
        self.assertEqual(receipt["host_preflight_status"], "EXECUTION_FAILED")
        self.assertIn("HOST_PREFLIGHT_EXECUTION_FAILED", receipt["blocker_codes"])
        self.assertNotIn("secret raw exception", json.dumps(receipt))
        for exception in (KeyboardInterrupt(), SystemExit(2)):
            with self.subTest(exception=type(exception).__name__), patch.object(
                compiler.preflight,
                "observe_fixed_windows_owner_provisioning_preflight_candidate",
                side_effect=exception,
            ):
                with self.assertRaises(type(exception)):
                    compiler.compile_fixed_p0_actual_readiness_blockers()

    def test_endpoint_add_remove_or_content_change_adds_local_blocker(self):
        before = _stable_snapshot()
        changed = deepcopy(before)
        changed["projection"][0]["sha256"] = "c" * 64
        changed["projection_sha256"] = _sha(changed["projection"])
        with (
            patch.object(
                compiler,
                "_safe_snapshot_fixed_local_endpoints",
                side_effect=[before, changed],
            ),
            patch.object(
                compiler.preflight,
                "observe_fixed_windows_owner_provisioning_preflight_candidate",
                return_value=_fixed_store_candidate(),
            ),
        ):
            receipt = compiler.compile_fixed_p0_actual_readiness_blockers()
        self.assertFalse(receipt["local_endpoint_bytes_sha_stable"])
        self.assertFalse(
            receipt["compiler_pre_post_endpoint_projection_match_observed"]
        )
        self.assertIn("LOCAL_ENDPOINT_CHANGED_DURING_COMPILATION", receipt["blocker_codes"])
        self.assertEqual(receipt["blocker_codes"][-1], "BLOCKER_ONLY_COMPILER_NOT_AUTHORITY")

    def test_mtime_only_endpoint_change_is_not_reported_as_call_stable(self):
        before = _stable_snapshot()
        changed = deepcopy(before)
        changed["projection"][0]["mtime_ns"] = 101
        changed["projection_sha256"] = _sha(changed["projection"])
        with (
            patch.object(
                compiler,
                "_safe_snapshot_fixed_local_endpoints",
                side_effect=[before, changed],
            ),
            patch.object(
                compiler.preflight,
                "observe_fixed_windows_owner_provisioning_preflight_candidate",
                return_value=_fixed_store_candidate(),
            ),
        ):
            receipt = compiler.compile_fixed_p0_actual_readiness_blockers()
        self.assertTrue(receipt["local_endpoint_bytes_sha_stable"])
        self.assertFalse(receipt["local_endpoint_mtime_stable"])
        self.assertFalse(
            receipt["compiler_pre_post_endpoint_projection_match_observed"]
        )
        self.assertIn(
            "LOCAL_ENDPOINT_CHANGED_DURING_COMPILATION", receipt["blocker_codes"]
        )

    def test_missing_endpoint_snapshot_is_not_continuous_noninterference(self):
        failed = {
            "snapshot_succeeded": False,
            "required_local_endpoint_kinds_present": False,
            "projection": [],
            "projection_sha256": _sha([]),
        }
        with (
            patch.object(
                compiler,
                "_safe_snapshot_fixed_local_endpoints",
                side_effect=[failed, failed],
            ),
            patch.object(
                compiler.preflight,
                "observe_fixed_windows_owner_provisioning_preflight_candidate",
                return_value=_fixed_store_candidate(),
            ),
        ):
            receipt = compiler.compile_fixed_p0_actual_readiness_blockers()
        self.assertIn("LOCAL_ENDPOINT_SNAPSHOT_NOT_VERIFIED", receipt["blocker_codes"])
        self.assertNotIn(
            "LOCAL_ENDPOINT_CHANGED_DURING_COMPILATION",
            receipt["blocker_codes"],
        )
        self.assertFalse(receipt["local_endpoint_inventory_stable"])
        self.assertFalse(receipt["local_endpoint_bytes_sha_stable"])
        self.assertFalse(receipt["local_endpoint_mtime_stable"])
        self.assertFalse(
            receipt["compiler_pre_post_endpoint_projection_match_observed"]
        )
        self.assertFalse(receipt["continuous_runtime_noninterference_verified"])
        self.assertFalse(receipt["runtime_noninterference_verified"])

    def test_receipt_self_hash_is_exact_and_deterministic_with_stable_inputs(self):
        snapshot = _stable_snapshot()
        child = _fixed_store_candidate()
        with (
            patch.object(
                compiler,
                "_safe_snapshot_fixed_local_endpoints",
                side_effect=[snapshot, snapshot, snapshot, snapshot],
            ),
            patch.object(
                compiler.preflight,
                "observe_fixed_windows_owner_provisioning_preflight_candidate",
                return_value=child,
            ),
        ):
            first = compiler.compile_fixed_p0_actual_readiness_blockers()
            second = compiler.compile_fixed_p0_actual_readiness_blockers()
        self.assertEqual(first, second)
        material = dict(first)
        declared = material.pop("receipt_sha256")
        self.assertEqual(declared, _sha(material))


if __name__ == "__main__":
    unittest.main()
