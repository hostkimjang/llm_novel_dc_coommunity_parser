from __future__ import annotations

import base64
from copy import deepcopy
import ctypes
import hashlib
import inspect
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from llm_batch.grounding import p0_external_owner_asymmetric_signature as asymmetric
from llm_batch.grounding import p0_windows_bootstrap_policy_signature_candidate as bootstrap
from llm_batch.grounding import p0_windows_fixed_directory_identity as fixed
from llm_batch.grounding import p0_windows_fixed_owner_policy_store_candidate as candidate
from llm_batch.grounding import p0_windows_owner_policy_contract as policy
from tests import test_p0_windows_owner_policy_contract as contract_fixture
from tests.test_p0_external_owner_asymmetric_signature import _TestOnlyCngSigner


def _pin_rehash(value: dict[str, object]) -> dict[str, object]:
    material = {
        key: item for key, item in value.items() if key != "artifact_sha256"
    }
    value["artifact_sha256"] = asymmetric.canonical_sha256(material)
    return value


def _rederive_body(body: dict[str, object]) -> dict[str, object]:
    object_policies = body["object_policies"]
    operational_key = body["operational_key"]
    assert isinstance(object_policies, list)
    assert isinstance(operational_key, dict)
    owner_principal = policy.derive_owner_principal_sha256(body["owner_sid"])
    acl_hash = policy.canonical_sha256(
        {
            "domain": policy.ACL_TEMPLATE_DOMAIN,
            "objects": [
                {
                    "role": row["role"],
                    "object_kind": row["object_kind"],
                    "security_template": row["security_template"],
                }
                for row in object_policies
            ],
        }
    )
    key_hash = policy.derive_operational_key_projection_sha256(
        operational_key
    )
    object_identity_hash = policy.canonical_sha256(
        [
            {
                key: row[key]
                for key in (
                    "role",
                    "object_kind",
                    "final_volume_guid_path",
                    "volume_serial_decimal",
                    "file_id_128_hex",
                )
            }
            for row in object_policies
        ]
    )
    anchor = policy.canonical_sha256(
        {
            "domain": policy.OWNER_ANCHOR_DOMAIN,
            "policy_id": body["policy_id"],
            "policy_epoch": body["policy_epoch"],
            "predecessor_policy_bytes_sha256": body[
                "predecessor_policy_bytes_sha256"
            ],
            **{
                field: body[field]
                for field in (
                    "store_id",
                    "project_id",
                    "trust_domain",
                    "environment",
                    "purpose",
                    "bootstrap_key_id",
                )
            },
            "bootstrap_public_key_fingerprint_sha256": body[
                "bootstrap_public_key_fingerprint_sha256"
            ],
            "owner_principal_sha256": owner_principal,
            "verifier_sid": body["verifier_sid"],
            "object_identity_projection_sha256": object_identity_hash,
            "acl_template_sha256": acl_hash,
            "operational_key_projection_sha256": key_hash,
            "min_revocation_sequence": body["min_revocation_sequence"],
            "lifecycle_status": body["lifecycle_status"],
        }
    )
    body.update(
        {
            "owner_principal_sha256": owner_principal,
            "acl_template_sha256": acl_hash,
            "operational_key_projection_sha256": key_hash,
            "owner_anchor_sha256": anchor,
        }
    )
    return contract_fixture._rehash(body)


@unittest.skipUnless(os.name == "nt", "Windows fixed-store test")
class WindowsFixedOwnerPolicyStoreCandidateTests(unittest.TestCase):
    def _snapshot(self, path: Path, *, directory: bool):
        api = fixed._Win32()
        with fixed._open_handle(
            api, str(path), directory=directory, read_data=False
        ) as handle:
            return fixed._query_snapshot(
                api, handle.value, include_streams=not directory
            )

    def _build_store(self, program_data: Path):
        paths = {
            role: Path(path)
            for role, path in candidate._role_paths(str(program_data)).items()
        }
        for role in policy.OBJECT_ROLES[:5]:
            paths[role].mkdir(parents=True, exist_ok=True)
        for role in policy.OBJECT_ROLES[5:]:
            paths[role].write_bytes(b"")

        object_policies: list[dict[str, object]] = []
        templates_by_final_path: dict[str, dict[str, object]] = {}
        for role in policy.OBJECT_ROLES:
            is_directory = role in policy.OBJECT_ROLES[:5]
            snapshot = self._snapshot(paths[role], directory=is_directory)
            security = contract_fixture._security(role)
            templates_by_final_path[snapshot.final_path] = security
            object_policies.append(
                {
                    "role": role,
                    "object_kind": "DIRECTORY" if is_directory else "FILE",
                    "final_volume_guid_path": snapshot.final_path,
                    "volume_serial_decimal": str(snapshot.volume_serial),
                    "file_id_128_hex": snapshot.file_id,
                    "security_template": security,
                }
            )

        x64 = base64.b64encode(b"\x01" * 32).decode("ascii")
        y64 = base64.b64encode(b"\x02" * 32).decode("ascii")
        fingerprint = asymmetric.public_key_fingerprint_sha256(
            public_key_x_base64=x64,
            public_key_y_base64=y64,
        )
        body = contract_fixture._body()
        bootstrap_signer = _TestOnlyCngSigner()
        self.addCleanup(bootstrap_signer.close)
        bootstrap_x64 = base64.b64encode(bootstrap_signer.x).decode("ascii")
        bootstrap_y64 = base64.b64encode(bootstrap_signer.y).decode("ascii")
        bootstrap_fingerprint = asymmetric.public_key_fingerprint_sha256(
            public_key_x_base64=bootstrap_x64,
            public_key_y_base64=bootstrap_y64,
        )
        bootstrap_key = bootstrap._CompiledBootstrapKeyCandidate(
            key_id="controlled-fixed-store-bootstrap-key-001",
            public_key_x=bootstrap_signer.x,
            public_key_y=bootstrap_signer.y,
            public_key_fingerprint_sha256=bootstrap_fingerprint,
        )
        body.update(
            {
                "object_policies": object_policies,
                "trust_domain": "fixed-owner-policy-test",
                "environment": "controlled-fixed-store-fixture",
                "bootstrap_key_id": bootstrap_key.key_id,
                "bootstrap_public_key_fingerprint_sha256": (
                    bootstrap_key.public_key_fingerprint_sha256
                ),
            }
        )
        body["operational_key"] = {
            "key_id": "fixed-owner-operational-key-001",
            "key_epoch": 1,
            "algorithm": asymmetric.ALGORITHM,
            "public_key_fingerprint_sha256": fingerprint,
            "pin_bytes_sha256": "0" * 64,
            "pin_artifact_sha256": "0" * 64,
            "allowed_signature_domains": [asymmetric.SIGNATURE_DOMAIN],
        }
        _rederive_body(body)
        anchor_before_pin = body["owner_anchor_sha256"]
        pin = _pin_rehash(
            {
                "schema_version": asymmetric.PUBLIC_KEY_PIN_SCHEMA,
                "record_origin": asymmetric.PRESENTED_PIN_ORIGIN,
                "trust_domain": body["trust_domain"],
                "project_id": body["project_id"],
                "environment": body["environment"],
                "purpose": asymmetric.SIGNATURE_PURPOSE,
                "key_id": body["operational_key"]["key_id"],
                "key_epoch": body["operational_key"]["key_epoch"],
                "algorithm": body["operational_key"]["algorithm"],
                "curve": asymmetric.CURVE,
                "coordinate_encoding": asymmetric.COORDINATE_ENCODING,
                "fingerprint_encoding": asymmetric.FINGERPRINT_ENCODING,
                "public_key_x_base64": x64,
                "public_key_y_base64": y64,
                "public_key_fingerprint_sha256": fingerprint,
                "owner_principal_sha256": body["owner_principal_sha256"],
                "owner_anchor_sha256": body["owner_anchor_sha256"],
                "allowed_signature_domains": [asymmetric.SIGNATURE_DOMAIN],
            }
        )
        pin_raw = asymmetric.json_file_bytes(pin)
        body["operational_key"]["pin_bytes_sha256"] = hashlib.sha256(
            pin_raw
        ).hexdigest()
        body["operational_key"]["pin_artifact_sha256"] = pin[
            "artifact_sha256"
        ]
        _rederive_body(body)
        self.assertEqual(body["owner_anchor_sha256"], anchor_before_pin)
        signature = contract_fixture._signature(body)
        signature_material = bootstrap.canonical_bytes(
            bootstrap._signature_material(signature)
        )
        signature["signature_rs_base64"] = base64.b64encode(
            bootstrap_signer.sign_low_s(signature_material)
        ).decode("ascii")
        contract_fixture._rehash(signature)
        paths["policy_body_file"].write_bytes(policy.json_file_bytes(body))
        paths["policy_signature_file"].write_bytes(
            policy.json_file_bytes(signature)
        )
        paths["public_key_pin_file"].write_bytes(pin_raw)
        return (
            paths,
            body,
            pin,
            pin_raw,
            templates_by_final_path,
            bootstrap_key,
        )

    def test_public_api_is_zero_argument_and_has_no_external_selectors(self) -> None:
        signature = inspect.signature(
            candidate.observe_fixed_windows_owner_policy_store_candidate
        )
        self.assertEqual(list(signature.parameters), [])
        source = inspect.getsource(candidate)
        for forbidden in (
            "os.environ",
            "os.getenv",
            "expandvars",
            "winreg",
        ):
            self.assertNotIn(forbidden, source)
        with self.assertRaises(TypeError):
            candidate.observe_fixed_windows_owner_policy_store_candidate(
                "C:\\attacker"
            )
        with self.assertRaises(TypeError):
            candidate.observe_fixed_windows_owner_policy_store_candidate(
                path="C:\\attacker"
            )

    def test_known_folder_call_uses_exact_guid_flags_null_token_and_frees(self) -> None:
        class FakeApi:
            def __init__(self):
                self.buffer = ctypes.create_unicode_buffer("C:\\ProgramData")
                self.calls = []
                self.freed = 0

            def SHGetKnownFolderPath(self, guid, flags, token, output):
                self.calls.append(
                    (
                        ctypes.string_at(
                            guid, ctypes.sizeof(candidate._GUID)
                        ),
                        flags,
                        token,
                    )
                )
                ctypes.cast(
                    output, ctypes.POINTER(ctypes.c_wchar_p)
                )[0] = ctypes.cast(self.buffer, ctypes.c_wchar_p)
                return 0

            def CoTaskMemFree(self, pointer):
                self.freed += 1

        api = FakeApi()
        self.assertEqual(candidate._program_data_path(api), "C:\\ProgramData")
        self.assertEqual(len(api.calls), 1)
        self.assertEqual(
            api.calls[0][0].hex(),
            "825dab62c1fdc34da9dd070d1d495d97",
        )
        self.assertEqual(api.calls[0][1:], (0, None))
        self.assertEqual(api.freed, 1)

    def test_known_folder_failure_still_frees_nonnull_allocation(self) -> None:
        class FailingApi:
            def __init__(self):
                self.buffer = ctypes.create_unicode_buffer("C:\\decoy")
                self.freed = 0

            def SHGetKnownFolderPath(self, _guid, _flags, _token, output):
                ctypes.cast(
                    output, ctypes.POINTER(ctypes.c_wchar_p)
                )[0] = ctypes.cast(self.buffer, ctypes.c_wchar_p)
                return -2147467259

            def CoTaskMemFree(self, _pointer):
                self.freed += 1

        api = FailingApi()
        with self.assertRaisesRegex(
            candidate.P0WindowsFixedOwnerPolicyStoreCandidateError,
            "HRESULT",
        ):
            candidate._program_data_path(api)
        self.assertEqual(api.freed, 1)

    def test_held_handle_close_failure_prevents_success(self) -> None:
        class CloseFailApi:
            def CloseHandle(self, _handle):
                return False

        with self.assertRaises(fixed.P0WindowsFixedDirectoryError):
            with fixed._OwnedHandle(CloseFailApi(), 1234, "controlled-close"):
                pass

    def test_controlled_fixed_store_observation_is_candidate_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            program_data = Path(raw_temp)
            _paths, body, pin, pin_raw, templates, bootstrap_key = self._build_store(
                program_data
            )
            query_api = fixed._Win32()

            def fake_acl(*, handle: int):
                snapshot = fixed._query_snapshot(
                    query_api, handle, include_streams=False
                )
                return deepcopy(templates[snapshot.final_path])

            with (
                patch.object(
                    candidate,
                    "_program_data_path",
                    return_value=str(program_data),
                ),
                patch.object(
                    candidate.binary_acl,
                    "observe_windows_binary_acl_projection",
                    side_effect=fake_acl,
                ) as acl_observer,
                patch.object(
                    candidate.bootstrap,
                    "_compiled_bootstrap_key_candidate",
                    return_value=bootstrap_key,
                ),
            ):
                receipt, observed_body, observed_signature_bytes = (
                    candidate._observe_fixed_windows_owner_policy_store_candidate_with_body_and_signature_bytes()
                )

            self.assertEqual(
                receipt["schema_version"], candidate.CANDIDATE_RECEIPT_SCHEMA
            )
            self.assertTrue(receipt["candidate_only"])
            self.assertTrue(
                receipt["fixed_policy_store_discovery_candidate_observed"]
            )
            self.assertTrue(
                receipt[
                    "policy_object_identity_live_handle_exact_match_observed"
                ]
            )
            self.assertTrue(
                receipt[
                    "held_role_acl_projection_matches_presented_template_observed"
                ]
            )
            self.assertTrue(receipt["bootstrap_signature_mathematics_verified"])
            self.assertEqual(observed_body, body)
            self.assertEqual(
                hashlib.sha256(observed_signature_bytes).hexdigest(),
                receipt["policy_signature_bytes_sha256"],
            )
            for critical_false in (
                "bootstrap_public_key_independently_pinned",
                "trusted_verifier_code_identity_verified",
                "trusted_cng_provider_provenance_verified",
                "external_owner_policy_provisioning_verified",
                "owner_authority_verified",
                "actual_authority_granted",
                "actual_semantic_evidence_verified",
                "production_approval",
                "full_scan_approval",
                "p0_phase_exit",
                "action_applied",
                "protected_pipeline_state_mutated",
            ):
                self.assertIn(critical_false, receipt)
                self.assertFalse(receipt[critical_false], critical_false)
            self.assertEqual(receipt["role_handle_count"], 8)
            self.assertEqual(acl_observer.call_count, 16)
            self.assertEqual(
                receipt["public_key_pin_bytes_sha256"],
                hashlib.sha256(pin_raw).hexdigest(),
            )
            self.assertEqual(
                receipt["owner_policy_contract_receipt"]["owner_anchor_sha256"],
                body["owner_anchor_sha256"],
            )
            self.assertEqual(
                receipt["public_key_pin_artifact_sha256"],
                pin["artifact_sha256"],
            )
            for field in candidate._FALSE_FIELDS:
                self.assertFalse(receipt[field], field)
            material = dict(receipt)
            declared = material.pop("receipt_sha256")
            self.assertEqual(declared, candidate.canonical_sha256(material))

    def test_forged_bootstrap_receipt_matrix_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            program_data = Path(raw_temp)
            paths, body, _pin, _pin_raw, _templates, bootstrap_key = (
                self._build_store(program_data)
            )
            body_raw = paths["policy_body_file"].read_bytes()
            signature_raw = paths["policy_signature_file"].read_bytes()
            contract_receipt = (
                policy.validate_presented_windows_owner_policy_contract(
                    policy_body_bytes=body_raw,
                    policy_signature_bytes=signature_raw,
                )
            )
            with patch.object(
                bootstrap,
                "_compiled_bootstrap_key_candidate",
                return_value=bootstrap_key,
            ):
                valid = (
                    bootstrap.verify_presented_windows_owner_policy_bootstrap_signature_candidate(
                        policy_body_bytes=body_raw,
                        policy_signature_bytes=signature_raw,
                    )
                )

            def with_valid_self_hash(receipt):
                material = dict(receipt)
                material.pop("receipt_sha256", None)
                return {
                    **material,
                    "receipt_sha256": candidate.canonical_sha256(material),
                }

            forged_receipts = []
            changed = deepcopy(valid)
            changed["receipt_sha256"] = "0" * 64
            forged_receipts.append(("self-hash", changed))
            for label, field, value in (
                (
                    "math false",
                    "bootstrap_signature_mathematics_verified",
                    False,
                ),
                ("schema", "schema_version", "forged-schema"),
                ("key", "compiled_bootstrap_key_id", "attacker-key"),
                ("authority", "owner_authority_verified", True),
                (
                    "receipt authority",
                    "serialized_receipt_authoritative",
                    True,
                ),
            ):
                changed = deepcopy(valid)
                changed[field] = value
                forged_receipts.append((label, with_valid_self_hash(changed)))

            for label, forged in forged_receipts:
                with self.subTest(label=label):
                    with self.assertRaises(
                        candidate.P0WindowsFixedOwnerPolicyStoreCandidateError
                    ):
                        candidate._validate_same_call_bootstrap_receipt(
                            receipt=forged,
                            policy_body_bytes=body_raw,
                            policy_signature_bytes=signature_raw,
                            contract_receipt=contract_receipt,
                            body=body,
                        )

    def test_binary_acl_drift_between_pre_and_post_observation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            program_data = Path(raw_temp)
            _paths, _body, _pin, _pin_raw, templates, bootstrap_key = self._build_store(
                program_data
            )
            query_api = fixed._Win32()
            calls = 0

            def drifting_acl(*, handle: int):
                nonlocal calls
                calls += 1
                snapshot = fixed._query_snapshot(
                    query_api, handle, include_streams=False
                )
                projection = deepcopy(templates[snapshot.final_path])
                if calls == 9:
                    projection["group_sid"] = "S-1-5-19"
                return projection

            with (
                patch.object(
                    candidate,
                    "_program_data_path",
                    return_value=str(program_data),
                ),
                patch.object(
                    candidate.binary_acl,
                    "observe_windows_binary_acl_projection",
                    side_effect=drifting_acl,
                ),
                patch.object(
                    candidate.bootstrap,
                    "_compiled_bootstrap_key_candidate",
                    return_value=bootstrap_key,
                ),
            ):
                with self.assertRaisesRegex(
                    candidate.P0WindowsFixedOwnerPolicyStoreCandidateError,
                    "binary ACL changed",
                ):
                    candidate.observe_fixed_windows_owner_policy_store_candidate()
            self.assertEqual(calls, 9)

    def test_first_watch_is_finalized_if_second_watch_start_fails(self) -> None:
        class FirstWatch:
            finalized = False

            def finalize(self):
                self.finalized = True
                return object()

        first = FirstWatch()
        with patch.object(
            candidate.directory_watch.WindowsDirectoryChangeWatch,
            "start",
            side_effect=[first, RuntimeError("second watch start failed")],
        ):
            with self.assertRaises(
                candidate.P0WindowsFixedOwnerPolicyStoreCandidateError
            ):
                candidate._observe_at_program_data("C:\\ProgramData")
        self.assertTrue(first.finalized)

    def test_pin_byte_hash_and_owner_anchor_tamper_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            _paths, body, pin, pin_raw, _templates, _bootstrap_key = self._build_store(
                Path(raw_temp)
            )
            changed = deepcopy(pin)
            changed["owner_anchor_sha256"] = "f" * 64
            changed_raw = asymmetric.json_file_bytes(_pin_rehash(changed))
            with self.assertRaisesRegex(
                candidate.P0WindowsFixedOwnerPolicyStoreCandidateError,
                "owner_anchor_sha256",
            ):
                candidate._pin_cross_binding(body, changed, changed_raw)
            with self.assertRaisesRegex(
                candidate.P0WindowsFixedOwnerPolicyStoreCandidateError,
                "byte/artifact",
            ):
                candidate._pin_cross_binding(body, pin, pin_raw + b"x")

    def test_current_machine_missing_fixed_suffix_fails_closed(self) -> None:
        fixed_root = Path("C:\\ProgramData") / Path(
            *policy.FIXED_POLICY_STORE_SUFFIX
        )
        if fixed_root.exists():
            self.skipTest("a fixed owner-policy store is provisioned")
        with self.assertRaises(
            candidate.P0WindowsFixedOwnerPolicyStoreCandidateError
        ):
            candidate.observe_fixed_windows_owner_policy_store_candidate()


class WindowsFixedOwnerPolicyStoreCandidatePlatformTests(unittest.TestCase):
    def test_non_windows_gate_precedes_known_folder_probe(self) -> None:
        with (
            patch.object(candidate, "_IS_WINDOWS", False),
            patch.object(candidate, "_KnownFolderApi") as known_folder,
        ):
            with self.assertRaisesRegex(
                candidate.P0WindowsFixedOwnerPolicyStoreCandidateError,
                "Windows-only",
            ):
                candidate.observe_fixed_windows_owner_policy_store_candidate()
            known_folder.assert_not_called()


if __name__ == "__main__":
    unittest.main()
