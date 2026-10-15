from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from llm_batch.grounding import p0_actual_authority_contract as authority_contract
from llm_batch.grounding import p0_actual_owner_root_preauthorization as contract
from llm_batch.grounding import p0_actual_packet_contract as packet_contract


KEY = b"external-owner-key-material-for-structural-hmac-math"
SHA_A = "1" * 64
SHA_B = "2" * 64
SHA_C = "3" * 64
SHA_D = "4" * 64
SHA_E = "5" * 64
SHA_F = "6" * 64
SHA_G = "7" * 64
SHA_H = "8" * 64
VOLUME = "11111111-2222-3333-4444-555555555555"


def _root(
    root_id: str,
    path: str,
    file_id: str,
    *,
    packet: bool,
) -> dict[str, object]:
    return {
        "root_id": root_id,
        "final_volume_guid_path": f"\\\\?\\Volume{{{VOLUME}}}\\{path}",
        "volume_serial_decimal": "123456789",
        "file_id_128_hex": file_id,
        "access_intent": (
            "WRITE_RUN_OUTPUT_ONLY" if packet else "READ_ONLY_PROTECTED"
        ),
    }


def _unsigned(origin: str = contract.ACTUAL_ORIGIN) -> dict[str, object]:
    categories = []
    for index, category in enumerate(contract.REQUIRED_WATCH_CATEGORIES):
        categories.append(
            {
                "category": category,
                "root_id": "PROTECTED_ROOT",
                "relative_root": f"category-{index}",
                "required_min_count": 1,
            }
        )
    return {
        "schema_version": contract.PREAUTHORIZATION_SCHEMA,
        "record_origin": origin,
        "preauthorization_id": "owner-root-preauth-001",
        "project_id": "llm-novel-dc-community-parser",
        "run_id": "actual-p0-run-001",
        "parser_run_id": "parser-run-001",
        "domain": contract.PREAUTHORIZATION_DOMAIN,
        "algorithm": "HMAC-SHA256",
        "key_id": "owner-key-001",
        "owner_principal_sha256": SHA_A,
        "owner_anchor_sha256": SHA_B,
        "foundation_manifest_sha256": SHA_C,
        "launch_sha256": SHA_D,
        "owner_authorization_sha256": SHA_E,
        "watch_spec_sha256": SHA_F,
        "expected_provenance": {
            "parser_receipt_schema": authority_contract.PARSER_RECEIPT_SCHEMA,
            "parser_manifest_sha256": SHA_A,
            "parser_version": "parser-v1.2.3",
            "capture_manifest_sha256": SHA_B,
            "input_registry_sha256": SHA_C,
            "source_input_plan_sha256": SHA_D,
            "sampling_frame_sha256": SHA_E,
            "packet_manifest_schema": packet_contract.PACKET_MANIFEST_SCHEMA,
            "packet_fixed_member_contract_sha256": (
                contract.FIXED_MEMBER_CONTRACT_SHA256
            ),
        },
        "allowed_packet_root": _root(
            "PACKET_ROOT", "runs\\packet-001", "a" * 32, packet=True
        ),
        "protected_roots": [
            _root(
                "PROTECTED_ROOT",
                "protected\\repository-state",
                "b" * 32,
                packet=False,
            )
        ],
        "category_root_map": categories,
        "watch_requirements": {
            "pre_post_required": True,
            "recursive_exact_membership_required": True,
            "identity_per_member_required": True,
            "continuous_journal_or_equivalent_required": True,
            "overflow_or_gap_fail_closed": True,
            "independent_observer_required": True,
            "required_evidence_schema": "p0_watch_evidence_v1",
        },
        "write_deny_requirements": {
            "os_enforcement_required": True,
            "protected_root_ids": ["PROTECTED_ROOT"],
            "parser_principal_must_be_denied": True,
            "independent_verifier_required": True,
            "must_preexist_before_watch_pre": True,
            "must_remain_through_terminal_attestation": True,
            "required_evidence_schema": "p0_write_deny_evidence_v1",
        },
        "issued_at": "2026-09-02T01:00:00Z",
        "not_before": "2026-09-02T01:01:00Z",
        "expires_at": "2026-09-02T02:00:00Z",
        "nonce": "nonce-actual-p0-001",
        "single_use": True,
        "authority_scope": contract.AUTHORITY_SCOPE,
        "decision": contract.PREAUTHORIZATION_DECISION,
        "public_apply": False,
        "central_slang_db_write": False,
        "publication_wal_write": False,
        "production_approval": False,
        "full_scan_approval": False,
        "preauthorization_signature_sha256": None,
        "verification_status": (
            "DETACHED_SIGNATURE_PRESENT_UNVERIFIED"
            if origin == contract.ACTUAL_ORIGIN
            else "EXTERNAL_KEY_ABSENT"
        ),
        "action_applied": False,
        "operational_effect": contract.OPERATIONAL_EFFECT,
    }


def _sealed(
    origin: str = contract.ACTUAL_ORIGIN,
    *,
    key: bytes = KEY,
) -> dict[str, object]:
    row = _unsigned(origin)
    if origin == contract.ACTUAL_ORIGIN:
        row["preauthorization_signature_sha256"] = contract.sign_preauthorization(
            row, key
        )
    return contract.with_artifact_hash(row)


def _resign_and_reseal(row: dict[str, object], *, key: bytes = KEY) -> dict[str, object]:
    material = copy.deepcopy(row)
    material.pop("artifact_sha256", None)
    material["preauthorization_signature_sha256"] = contract.sign_preauthorization(
        material, key
    )
    return contract.with_artifact_hash(material)


class OwnerRootPreauthorizationTests(unittest.TestCase):
    def test_actual_signature_math_still_returns_zero_credit_no_go(self) -> None:
        receipt = contract.validate_owner_root_preauthorization(
            _sealed(),
            contract.ACTUAL_ORIGIN,
            key=KEY,
            expected_owner_anchor_sha256=SHA_B,
            observed_at="2026-09-02T01:30:00Z",
        )

        self.assertTrue(receipt["signature_math_valid"])
        self.assertTrue(receipt["presented_owner_anchor_match"])
        self.assertTrue(receipt["presented_internal_structure_verified"])
        self.assertTrue(receipt["presented_observation_window_checked"])
        self.assertTrue(receipt["presented_observation_window_match"])
        self.assertFalse(receipt["filesystem_namespace_alias_resolution_verified"])
        self.assertTrue(receipt["category_effective_root_overlap_rejected"])
        for field in (
            "external_trust_store_verified",
            "revocation_current_verified",
            "single_use_replay_consumed",
            "external_root_identity_pin_verified",
            "filesystem_handle_trust_verified",
            "continuous_watch_verified",
            "os_write_deny_verified",
            "runtime_noninterference_verified",
            "owner_authority_verified",
            "actual_authority_granted",
            "production_approval",
            "full_scan_approval",
            "p0_phase_exit",
            "action_applied",
        ):
            self.assertFalse(receipt[field], field)
        self.assertEqual(0, receipt["credited_actual_source_claim_count"])
        self.assertEqual(0, receipt["credited_actual_a_context_review_count"])
        self.assertEqual(
            "NO_GO_ACTUAL_P0_AUTHORITY_NOT_VERIFIED", receipt["gate_status"]
        )
        material = dict(receipt)
        stored = material.pop("receipt_sha256")
        self.assertEqual(contract.canonical_sha256(material), stored)

    def test_actual_detached_signature_can_be_structurally_unverified(self) -> None:
        receipt = contract.validate_owner_root_preauthorization(
            _sealed(), contract.ACTUAL_ORIGIN
        )
        self.assertFalse(receipt["signature_math_valid"])
        self.assertFalse(receipt["external_trust_store_verified"])
        self.assertTrue(receipt["presented_internal_structure_verified"])
        self.assertFalse(receipt["presented_observation_window_checked"])
        self.assertFalse(receipt["presented_observation_window_match"])

    def test_example_is_unsigned_and_permanently_no_go(self) -> None:
        receipt = contract.validate_owner_root_preauthorization(
            _sealed(contract.EXAMPLE_ORIGIN), contract.EXAMPLE_ORIGIN
        )
        self.assertFalse(receipt["signature_math_valid"])
        self.assertFalse(receipt["actual_authority_granted"])

    def test_actual_requires_signature_and_example_rejects_signature(self) -> None:
        actual = _unsigned(contract.ACTUAL_ORIGIN)
        with self.assertRaisesRegex(
            contract.P0ActualOwnerRootPreauthorizationError,
            "requires a detached",
        ):
            contract.validate_owner_root_preauthorization(
                contract.with_artifact_hash(actual), contract.ACTUAL_ORIGIN
            )

        example = _unsigned(contract.EXAMPLE_ORIGIN)
        example["preauthorization_signature_sha256"] = SHA_A
        with self.assertRaisesRegex(
            contract.P0ActualOwnerRootPreauthorizationError, "must remain unsigned"
        ):
            contract.validate_owner_root_preauthorization(
                contract.with_artifact_hash(example), contract.EXAMPLE_ORIGIN
            )

    def test_strict_schema_rejects_external_trust_claim_injection(self) -> None:
        row = _sealed()
        row["external_trust_store_verified"] = True
        row = _resign_and_reseal(row)
        with self.assertRaisesRegex(
            contract.P0ActualOwnerRootPreauthorizationError, "fields mismatch"
        ):
            contract.validate_owner_root_preauthorization(
                row, contract.ACTUAL_ORIGIN, key=KEY
            )

    def test_true_capability_injection_is_rejected_even_when_resigned(self) -> None:
        for field in (
            "public_apply",
            "central_slang_db_write",
            "publication_wal_write",
            "production_approval",
            "full_scan_approval",
            "action_applied",
        ):
            with self.subTest(field=field):
                row = _sealed()
                row[field] = True
                row = _resign_and_reseal(row)
                with self.assertRaisesRegex(
                    contract.P0ActualOwnerRootPreauthorizationError,
                    "must remain false",
                ):
                    contract.validate_owner_root_preauthorization(
                        row, contract.ACTUAL_ORIGIN, key=KEY
                    )

    def test_root_tuple_fields_are_strictly_validated(self) -> None:
        mutations = (
            ("final_volume_guid_path", "C:\\runs\\packet"),
            ("volume_serial_decimal", "0123"),
            ("file_id_128_hex", "A" * 32),
            ("access_intent", "READ_ONLY_PROTECTED"),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                row = _sealed()
                row["allowed_packet_root"][field] = value
                row = _resign_and_reseal(row)
                with self.assertRaises(contract.P0ActualOwnerRootPreauthorizationError):
                    contract.validate_owner_root_preauthorization(
                        row, contract.ACTUAL_ORIGIN, key=KEY
                    )

    def test_unicode_decimal_volume_serial_is_rejected(self) -> None:
        row = _sealed()
        row["protected_roots"][0]["volume_serial_decimal"] = "１２３４５"
        row = _resign_and_reseal(row)
        with self.assertRaisesRegex(
            contract.P0ActualOwnerRootPreauthorizationError,
            "volume_serial_decimal is invalid",
        ):
            contract.validate_owner_root_preauthorization(
                row, contract.ACTUAL_ORIGIN, key=KEY
            )

    def test_packet_and_protected_path_overlap_is_rejected(self) -> None:
        row = _sealed()
        row["protected_roots"][0]["final_volume_guid_path"] = (
            f"\\\\?\\Volume{{{VOLUME}}}\\runs\\packet-001\\protected"
        )
        row = _resign_and_reseal(row)
        with self.assertRaisesRegex(
            contract.P0ActualOwnerRootPreauthorizationError, "must not overlap"
        ):
            contract.validate_owner_root_preauthorization(
                row, contract.ACTUAL_ORIGIN, key=KEY
            )

    def test_packet_and_protected_identity_alias_is_rejected(self) -> None:
        row = _sealed()
        row["protected_roots"][0]["file_id_128_hex"] = "a" * 32
        row = _resign_and_reseal(row)
        with self.assertRaisesRegex(
            contract.P0ActualOwnerRootPreauthorizationError, "identities"
        ):
            contract.validate_owner_root_preauthorization(
                row, contract.ACTUAL_ORIGIN, key=KEY
            )

    def test_protected_roots_require_unique_canonical_order(self) -> None:
        row = _sealed()
        second = _root(
            "AAA_ROOT", "protected\\other", "c" * 32, packet=False
        )
        row["protected_roots"].append(second)
        row = _resign_and_reseal(row)
        with self.assertRaisesRegex(
            contract.P0ActualOwnerRootPreauthorizationError, "canonically ordered"
        ):
            contract.validate_owner_root_preauthorization(
                row, contract.ACTUAL_ORIGIN, key=KEY
            )

    def test_category_map_requires_exact_fixed_order(self) -> None:
        for mutation in ("missing", "swapped", "duplicate"):
            with self.subTest(mutation=mutation):
                row = _sealed()
                categories = row["category_root_map"]
                if mutation == "missing":
                    categories.pop()
                elif mutation == "swapped":
                    categories[0], categories[1] = categories[1], categories[0]
                else:
                    categories[1]["category"] = categories[0]["category"]
                row = _resign_and_reseal(row)
                with self.assertRaisesRegex(
                    contract.P0ActualOwnerRootPreauthorizationError,
                    "exact ordered",
                ):
                    contract.validate_owner_root_preauthorization(
                        row, contract.ACTUAL_ORIGIN, key=KEY
                    )

    def test_category_unknown_root_and_duplicate_effective_root_fail(self) -> None:
        row = _sealed()
        row["category_root_map"][0]["root_id"] = "UNKNOWN_ROOT"
        row = _resign_and_reseal(row)
        with self.assertRaisesRegex(
            contract.P0ActualOwnerRootPreauthorizationError, "unknown protected"
        ):
            contract.validate_owner_root_preauthorization(
                row, contract.ACTUAL_ORIGIN, key=KEY
            )

        row = _sealed()
        row["category_root_map"][1]["relative_root"] = (
            row["category_root_map"][0]["relative_root"] + "/nested"
        )
        row = _resign_and_reseal(row)
        with self.assertRaisesRegex(
            contract.P0ActualOwnerRootPreauthorizationError,
            "non-overlapping",
        ):
            contract.validate_owner_root_preauthorization(
                row, contract.ACTUAL_ORIGIN, key=KEY
            )

        row = _sealed()
        row["category_root_map"][1]["relative_root"] = row["category_root_map"][0][
            "relative_root"
        ]
        row = _resign_and_reseal(row)
        with self.assertRaisesRegex(
            contract.P0ActualOwnerRootPreauthorizationError, "effective roots"
        ):
            contract.validate_owner_root_preauthorization(
                row, contract.ACTUAL_ORIGIN, key=KEY
            )

    def test_provenance_schema_and_fixed_member_contract_are_pinned(self) -> None:
        self.assertEqual(14, len(contract.FIXED_MEMBER_CONTRACT))
        self.assertEqual(13, len(packet_contract.CHILD_FILES))
        mutations = (
            ("parser_receipt_schema", "p0_actual_parser_runtime_receipt_v1"),
            ("packet_manifest_schema", "p0_actual_keyless_pilot_manifest_v0"),
            ("packet_fixed_member_contract_sha256", SHA_G),
            ("capture_manifest_sha256", "bad"),
            ("input_registry_sha256", "bad"),
            ("source_input_plan_sha256", "bad"),
            ("sampling_frame_sha256", "bad"),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                row = _sealed()
                row["expected_provenance"][field] = value
                row = _resign_and_reseal(row)
                with self.assertRaises(contract.P0ActualOwnerRootPreauthorizationError):
                    contract.validate_owner_root_preauthorization(
                        row, contract.ACTUAL_ORIGIN, key=KEY
                    )

    def test_watch_and_write_deny_requirements_cannot_be_relaxed(self) -> None:
        for section, field in (
            ("watch_requirements", "continuous_journal_or_equivalent_required"),
            ("watch_requirements", "independent_observer_required"),
            ("write_deny_requirements", "os_enforcement_required"),
            ("write_deny_requirements", "parser_principal_must_be_denied"),
            (
                "write_deny_requirements",
                "must_remain_through_terminal_attestation",
            ),
        ):
            with self.subTest(section=section, field=field):
                row = _sealed()
                row[section][field] = False
                row = _resign_and_reseal(row)
                with self.assertRaisesRegex(
                    contract.P0ActualOwnerRootPreauthorizationError, "must be true"
                ):
                    contract.validate_owner_root_preauthorization(
                        row, contract.ACTUAL_ORIGIN, key=KEY
                    )

    def test_write_deny_root_set_must_exactly_match_protected_roots(self) -> None:
        row = _sealed()
        row["write_deny_requirements"]["protected_root_ids"] = []
        row = _resign_and_reseal(row)
        with self.assertRaisesRegex(
            contract.P0ActualOwnerRootPreauthorizationError, "exactly match"
        ):
            contract.validate_owner_root_preauthorization(
                row, contract.ACTUAL_ORIGIN, key=KEY
            )

    def test_validity_chronology_and_observation_window_fail_closed(self) -> None:
        cases = (
            ("issued_at", "2026-09-02T01:02:00Z"),
            ("expires_at", "2026-09-02T01:01:00Z"),
            ("not_before", "2026-09-02 01:01:00+00:00"),
        )
        for field, value in cases:
            with self.subTest(field=field):
                row = _sealed()
                row[field] = value
                row = _resign_and_reseal(row)
                with self.assertRaises(contract.P0ActualOwnerRootPreauthorizationError):
                    contract.validate_owner_root_preauthorization(
                        row, contract.ACTUAL_ORIGIN, key=KEY
                    )
        for observed in ("2026-09-02T01:00:59Z", "2026-09-02T02:00:00Z"):
            with self.subTest(observed=observed), self.assertRaisesRegex(
                contract.P0ActualOwnerRootPreauthorizationError,
                "observation window",
            ):
                contract.validate_owner_root_preauthorization(
                    _sealed(),
                    contract.ACTUAL_ORIGIN,
                    key=KEY,
                    observed_at=observed,
                )

    def test_single_use_is_mandatory_but_not_self_claimed_consumed(self) -> None:
        row = _sealed()
        row["single_use"] = False
        row = _resign_and_reseal(row)
        with self.assertRaisesRegex(
            contract.P0ActualOwnerRootPreauthorizationError, "single-use"
        ):
            contract.validate_owner_root_preauthorization(
                row, contract.ACTUAL_ORIGIN, key=KEY
            )

        receipt = contract.validate_owner_root_preauthorization(
            _sealed(), contract.ACTUAL_ORIGIN, key=KEY
        )
        self.assertFalse(receipt["single_use_replay_consumed"])

    def test_reseal_without_owner_resign_cannot_change_root_or_run(self) -> None:
        for field, value in (
            ("run_id", "actual-p0-run-swapped"),
            ("launch_sha256", SHA_H),
        ):
            with self.subTest(field=field):
                row = _sealed()
                row[field] = value
                row = contract.with_artifact_hash(row)
                with self.assertRaisesRegex(
                    contract.P0ActualOwnerRootPreauthorizationError,
                    "signature mismatch",
                ):
                    contract.validate_owner_root_preauthorization(
                        row, contract.ACTUAL_ORIGIN, key=KEY
                    )
        row = _sealed()
        row["allowed_packet_root"]["file_id_128_hex"] = "c" * 32
        row = contract.with_artifact_hash(row)
        with self.assertRaisesRegex(
            contract.P0ActualOwnerRootPreauthorizationError, "signature mismatch"
        ):
            contract.validate_owner_root_preauthorization(
                row, contract.ACTUAL_ORIGIN, key=KEY
            )

    def test_signature_and_artifact_hash_tampering_are_independent(self) -> None:
        row = _sealed()
        row["nonce"] = "tampered-without-reseal"
        with self.assertRaisesRegex(
            contract.P0ActualOwnerRootPreauthorizationError, "artifact hash mismatch"
        ):
            contract.validate_owner_root_preauthorization(
                row, contract.ACTUAL_ORIGIN, key=KEY
            )

        row = _sealed()
        row["preauthorization_signature_sha256"] = SHA_A
        row = contract.with_artifact_hash(row)
        with self.assertRaisesRegex(
            contract.P0ActualOwnerRootPreauthorizationError, "signature mismatch"
        ):
            contract.validate_owner_root_preauthorization(
                row, contract.ACTUAL_ORIGIN, key=KEY
            )

    def test_caller_key_never_becomes_external_trust(self) -> None:
        local_key = b"run-local-generated-key-that-is-long-enough-for-hmac"
        row = _sealed(key=local_key)
        receipt = contract.validate_owner_root_preauthorization(
            row,
            contract.ACTUAL_ORIGIN,
            key=local_key,
            expected_owner_anchor_sha256=SHA_B,
        )
        self.assertTrue(receipt["signature_math_valid"])
        self.assertFalse(receipt["external_trust_store_verified"])
        self.assertFalse(receipt["revocation_current_verified"])
        self.assertFalse(receipt["owner_authority_verified"])

    def test_presented_anchor_mismatch_and_short_key_fail(self) -> None:
        with self.assertRaisesRegex(
            contract.P0ActualOwnerRootPreauthorizationError, "anchor mismatch"
        ):
            contract.validate_owner_root_preauthorization(
                _sealed(),
                contract.ACTUAL_ORIGIN,
                expected_owner_anchor_sha256=SHA_C,
            )
        with self.assertRaisesRegex(
            contract.P0ActualOwnerRootPreauthorizationError, "at least 32 bytes"
        ):
            contract.validate_owner_root_preauthorization(
                _sealed(), contract.ACTUAL_ORIGIN, key=b"short"
            )


if __name__ == "__main__":
    unittest.main()
