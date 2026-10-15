from __future__ import annotations

import base64
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import inspect
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from llm_batch.grounding import p0_external_owner_asymmetric_signature as asymmetric
from llm_batch.grounding import p0_windows_external_public_key_pin_candidate as candidate
from llm_batch.grounding import p0_windows_fixed_directory_identity as fixed
from llm_batch.grounding import p0_windows_runtime_evidence as runtime
from tests.p0_actual_authority_supervisor_fixtures import (
    build_coordinated_actual_fixture,
)
from tests.test_p0_external_owner_asymmetric_signature import (
    _TestOnlyCngSigner,
    _rehash,
)


@unittest.skipUnless(os.name == "nt", "Windows ACL/CNG APIs are required")
class WindowsExternalPublicKeyPinCandidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.signer = _TestOnlyCngSigner()
        self.addCleanup(self.signer.close)
        fixture = build_coordinated_actual_fixture()
        self.preauthorization = deepcopy(fixture.preauthorization)
        self.preauthorization_bytes = asymmetric.json_file_bytes(
            self.preauthorization
        )
        x64 = base64.b64encode(self.signer.x).decode("ascii")
        y64 = base64.b64encode(self.signer.y).decode("ascii")
        fingerprint = asymmetric.public_key_fingerprint_sha256(
            public_key_x_base64=x64,
            public_key_y_base64=y64,
        )
        self.pin = _rehash(
            {
                "schema_version": asymmetric.PUBLIC_KEY_PIN_SCHEMA,
                "record_origin": asymmetric.PRESENTED_PIN_ORIGIN,
                "trust_domain": "llm-novel-owner-trust-v1",
                "project_id": self.preauthorization["project_id"],
                "environment": "p0-shadow-test",
                "purpose": asymmetric.SIGNATURE_PURPOSE,
                "key_id": "test-only-owner-ecdsa-p256-001",
                "key_epoch": 1,
                "algorithm": asymmetric.ALGORITHM,
                "curve": asymmetric.CURVE,
                "coordinate_encoding": asymmetric.COORDINATE_ENCODING,
                "fingerprint_encoding": asymmetric.FINGERPRINT_ENCODING,
                "public_key_x_base64": x64,
                "public_key_y_base64": y64,
                "public_key_fingerprint_sha256": fingerprint,
                "owner_principal_sha256": self.preauthorization[
                    "owner_principal_sha256"
                ],
                "owner_anchor_sha256": self.preauthorization[
                    "owner_anchor_sha256"
                ],
                "allowed_signature_domains": [asymmetric.SIGNATURE_DOMAIN],
            }
        )
        self.pin_bytes = asymmetric.json_file_bytes(self.pin)
        self.envelope = self._signed_envelope(self.pin)
        self.envelope_bytes = asymmetric.json_file_bytes(self.envelope)
        validation = asymmetric.validate_presented_external_owner_asymmetric_signature(
            public_key_pin_bytes=self.pin_bytes,
            signature_envelope_bytes=self.envelope_bytes,
            owner_root_preauthorization_bytes=self.preauthorization_bytes,
        )
        self.expected_context = {
            field: validation[field]
            for field in asymmetric._OWNER_STATE_CONTEXT_FIELDS
        }

    def _signed_envelope(
        self,
        pin: dict[str, object],
        *,
        signer: _TestOnlyCngSigner | None = None,
        preauthorization: dict[str, object] | None = None,
    ) -> dict[str, object]:
        preauthorization = preauthorization or self.preauthorization
        preauthorization_bytes = asymmetric.json_file_bytes(preauthorization)
        envelope: dict[str, object] = {
            "schema_version": asymmetric.SIGNATURE_ENVELOPE_SCHEMA,
            "record_origin": asymmetric.PRESENTED_SIGNATURE_ORIGIN,
            "domain": asymmetric.SIGNATURE_DOMAIN,
            "trust_domain": pin["trust_domain"],
            "project_id": pin["project_id"],
            "environment": pin["environment"],
            "purpose": asymmetric.SIGNATURE_PURPOSE,
            "session_id": "external-owner-session-001",
            "run_id": preauthorization["run_id"],
            "preauthorization_id": preauthorization["preauthorization_id"],
            "parser_run_id": preauthorization["parser_run_id"],
            "nonce_commitment_sha256": asymmetric.canonical_sha256(
                {
                    "domain": asymmetric.NONCE_COMMITMENT_DOMAIN,
                    "nonce": preauthorization["nonce"],
                }
            ),
            "key_id": pin["key_id"],
            "key_epoch": pin["key_epoch"],
            "algorithm": asymmetric.ALGORITHM,
            "public_key_fingerprint_sha256": pin[
                "public_key_fingerprint_sha256"
            ],
            "owner_principal_sha256": pin["owner_principal_sha256"],
            "owner_anchor_sha256": pin["owner_anchor_sha256"],
            "preauthorization_schema": preauthorization["schema_version"],
            "preauthorization_bytes_sha256": hashlib.sha256(
                preauthorization_bytes
            ).hexdigest(),
            "preauthorization_artifact_sha256": preauthorization[
                "artifact_sha256"
            ],
            "signature_rs_base64": base64.b64encode(b"\0" * 64).decode("ascii"),
            "artifact_sha256": "0" * 64,
        }
        signature = (signer or self.signer).sign_low_s(
            asymmetric.canonical_bytes(
                asymmetric.external_owner_signature_material(envelope)
            )
        )
        envelope["signature_rs_base64"] = base64.b64encode(signature).decode(
            "ascii"
        )
        return _rehash(envelope)

    def _candidate_receipt(self, **changes: object) -> dict[str, object]:
        signed_roots = candidate._signed_root_expectation(
            self.preauthorization_bytes
        )
        clean_watch = {
            "bounded_watch_observation_verified": True,
            "directory_change_notification_delivered_observed": False,
            "overflow_observed": False,
            "observation_gap_observed": False,
            "pending_request_until_interval_end_observed": True,
            "completion_drained_observed": True,
            "watch_handles_closed_observed": True,
        }
        material: dict[str, object] = {
            "schema_version": candidate.CANDIDATE_RECEIPT_SCHEMA,
            "pin_filename": candidate.PUBLIC_KEY_PIN_FILENAME,
            "pin_bytes_length": len(self.pin_bytes),
            "pin_bytes_sha256": hashlib.sha256(self.pin_bytes).hexdigest(),
            "pin_artifact_sha256": self.pin["artifact_sha256"],
            "public_key_fingerprint_sha256": self.pin[
                "public_key_fingerprint_sha256"
            ],
            "key_id": self.pin["key_id"],
            "key_epoch": self.pin["key_epoch"],
            "owner_principal_sha256": self.pin["owner_principal_sha256"],
            "owner_anchor_sha256": self.pin["owner_anchor_sha256"],
            "presented_preauthorization_bytes_sha256": hashlib.sha256(
                self.preauthorization_bytes
            ).hexdigest(),
            "presented_root_expectation_sha256": candidate.canonical_sha256(
                signed_roots.projection()
            ),
            "presented_root_binding_projection_sha256": "4" * 64,
            "all_lexical_ancestor_handles_held": True,
            "file_handle_non_delete_shared_across_validation": True,
            "pin_store_handle_non_delete_shared_across_validation": True,
            "single_link_non_reparse_unnamed_stream_verified": True,
            "persistent_acls_filesystem_observed": True,
            "dedicated_fixed_filename_inventory_verified": True,
            "presented_packet_and_protected_parent_identities_bound_to_held_handles": True,
            "presented_protected_category_path_volumes_bound_to_held_handles": True,
            "held_run_packet_protected_parent_category_handles_identity_stable": True,
            "pin_store_overlap_with_held_run_packet_protected_parent_category_roots_rejected": True,
            "effective_verifier_token_source": "THREAD_IMPERSONATION_TOKEN",
            "effective_verifier_file_mutation_access_denied_observed": True,
            "effective_verifier_parent_mutation_access_denied_observed": True,
            "effective_verifier_owner_membership_rejected": True,
            "security_descriptor_pre_post_stable": True,
            "file_identity_pre_post_reopen_stable": True,
            "directory_change_watches": {
                "pin_store": dict(clean_watch),
                "pin_store_parent": dict(clean_watch),
            },
            "independent_owner_policy_state_verified": False,
            "external_public_key_pin_provisioning_verified": False,
            "independent_readonly_public_key_pin_verified": False,
            "public_key_pin_rollback_protection_verified": False,
        }
        material.update(changes)
        return {**material, "receipt_sha256": candidate.canonical_sha256(material)}

    @contextmanager
    def _fake_hold(
        self,
        *,
        raw: bytes | None = None,
        pin: dict[str, object] | None = None,
        receipt: dict[str, object] | None = None,
        observed_kwargs: dict[str, object] | None = None,
        **kwargs: object,
    ):
        if observed_kwargs is not None:
            observed_kwargs.update(kwargs)
        held = candidate._HeldPinCandidate(
            raw=raw or self.pin_bytes,
            pin=pin or self.pin,
            receipt=receipt or self._candidate_receipt(),
        )
        yield held

    def _execute(self, **changes: object) -> dict[str, object]:
        kwargs: dict[str, object] = {
            "pin_store_dir": Path("C:/external-pin-store"),
            "run_root": Path("C:/run-root"),
            "packet_root": Path("C:/packet-root"),
            "protected_category_roots": {
                category: Path(f"C:/protected/{index}-{category}")
                for index, category in enumerate(
                    runtime.REQUIRED_PROTECTED_CATEGORIES
                )
            },
            "signature_envelope_bytes": self.envelope_bytes,
            "owner_root_preauthorization_bytes": self.preauthorization_bytes,
            "expected_context": self.expected_context,
        }
        kwargs.update(changes)
        return candidate.execute_windows_external_public_key_pin_candidate_supervisor(
            **kwargs
        )

    def _actualized_root_material(
        self,
        *,
        packet_root: Path,
        protected_base: Path,
    ) -> tuple[bytes, bytes, dict[str, object]]:
        packet_identity = fixed.observe_windows_directory_identity(packet_root)
        protected_identity = fixed.observe_windows_directory_identity(
            protected_base
        )
        preauthorization = deepcopy(self.preauthorization)
        preauthorization["allowed_packet_root"] = {
            **preauthorization["allowed_packet_root"],
            "final_volume_guid_path": packet_identity.final_path,
            "volume_serial_decimal": str(packet_identity.volume_serial),
            "file_id_128_hex": packet_identity.file_id,
        }
        preauthorization["protected_roots"][0] = {
            **preauthorization["protected_roots"][0],
            "final_volume_guid_path": protected_identity.final_path,
            "volume_serial_decimal": str(protected_identity.volume_serial),
            "file_id_128_hex": protected_identity.file_id,
        }
        preauthorization = _rehash(preauthorization)
        preauthorization_bytes = asymmetric.json_file_bytes(preauthorization)
        envelope_bytes = asymmetric.json_file_bytes(
            self._signed_envelope(
                self.pin,
                preauthorization=preauthorization,
            )
        )
        validation = asymmetric.validate_presented_external_owner_asymmetric_signature(
            public_key_pin_bytes=self.pin_bytes,
            signature_envelope_bytes=envelope_bytes,
            owner_root_preauthorization_bytes=preauthorization_bytes,
        )
        expected_context = {
            field: validation[field]
            for field in asymmetric._OWNER_STATE_CONTEXT_FIELDS
        }
        return preauthorization_bytes, envelope_bytes, expected_context

    def test_public_api_has_no_raw_pin_expected_policy_or_receipt_injection(self) -> None:
        parameters = inspect.signature(
            candidate.execute_windows_external_public_key_pin_candidate_supervisor
        ).parameters
        self.assertEqual(
            list(parameters),
            [
                "pin_store_dir",
                "run_root",
                "packet_root",
                "protected_category_roots",
                "signature_envelope_bytes",
                "owner_root_preauthorization_bytes",
                "expected_context",
            ],
        )
        for forbidden in (
            "public_key_pin_bytes",
            "pin_receipt",
            "expected_owner_sid",
            "expected_pin_sha256",
            "expected_file_id",
            "expected_final_path",
            "trusted_policy",
            "callback",
            "state",
        ):
            self.assertNotIn(forbidden, parameters)
        self.assertFalse(any(name.startswith("_") for name in candidate.__all__))

    def test_controlled_candidate_uses_handle_bytes_in_same_call_and_stays_no_go(self) -> None:
        observed: dict[str, object] = {}

        @contextmanager
        def hold(**kwargs: object):
            with self._fake_hold(observed_kwargs=observed, **kwargs) as value:
                yield value

        baseline = len(asymmetric._ISSUED_OWNER_STATES)
        with patch.object(candidate, "_hold_windows_pin_candidate", hold):
            receipt = self._execute()
        self.assertEqual(len(asymmetric._ISSUED_OWNER_STATES), baseline)
        self.assertEqual(receipt["schema_version"], candidate.SUPERVISOR_RECEIPT_SCHEMA)
        self.assertEqual(receipt["gate_status"], candidate.GATE_STATUS)
        self.assertTrue(receipt["same_call_handle_read_pin_bytes_used_for_cng"])
        self.assertTrue(
            receipt[
                "pin_file_and_ancestor_handles_held_across_owner_state_validation"
            ]
        )
        self.assertTrue(receipt["caller_supplied_public_key_pin_bytes_absent"])
        self.assertEqual(observed["pin_store_dir"], Path("C:/external-pin-store"))
        for field in (
            "external_public_key_pin_provisioning_verified",
            "independent_readonly_public_key_pin_verified",
            "public_key_pin_rollback_protection_verified",
            "key_epoch_monotonicity_verified",
            "external_owner_signing_key_verified",
            "private_key_outside_verifier_verified",
            "trusted_time_verified",
            "revocation_current_verified",
            "durable_cross_process_nonce_verified",
            "power_loss_durable_replay_verified",
            "external_owner_trust_verified",
            "owner_authority_verified",
            "actual_authority_granted",
            "p0_phase_exit",
            "production_approval",
            "full_scan_approval",
        ):
            self.assertFalse(receipt[field], field)
        material = dict(receipt)
        declared = material.pop("receipt_sha256")
        self.assertEqual(declared, candidate.canonical_sha256(material))

    def test_complete_attacker_key_pin_signature_substitution_never_proves_authority(self) -> None:
        attacker = _TestOnlyCngSigner()
        self.addCleanup(attacker.close)
        pin = deepcopy(self.pin)
        pin["public_key_x_base64"] = base64.b64encode(attacker.x).decode("ascii")
        pin["public_key_y_base64"] = base64.b64encode(attacker.y).decode("ascii")
        pin["public_key_fingerprint_sha256"] = asymmetric.public_key_fingerprint_sha256(
            public_key_x_base64=pin["public_key_x_base64"],
            public_key_y_base64=pin["public_key_y_base64"],
        )
        pin["key_id"] = "attacker-self-consistent-key"
        pin = _rehash(pin)
        raw = asymmetric.json_file_bytes(pin)
        envelope = self._signed_envelope(pin, signer=attacker)
        validation = asymmetric.validate_presented_external_owner_asymmetric_signature(
            public_key_pin_bytes=raw,
            signature_envelope_bytes=asymmetric.json_file_bytes(envelope),
            owner_root_preauthorization_bytes=self.preauthorization_bytes,
        )
        context = {
            field: validation[field]
            for field in asymmetric._OWNER_STATE_CONTEXT_FIELDS
        }
        receipt = self._candidate_receipt(
            pin_bytes_length=len(raw),
            pin_bytes_sha256=hashlib.sha256(raw).hexdigest(),
            pin_artifact_sha256=pin["artifact_sha256"],
            public_key_fingerprint_sha256=pin[
                "public_key_fingerprint_sha256"
            ],
            key_id=pin["key_id"],
        )

        @contextmanager
        def hold(**_kwargs: object):
            yield candidate._HeldPinCandidate(raw=raw, pin=pin, receipt=receipt)

        with patch.object(candidate, "_hold_windows_pin_candidate", hold):
            result = self._execute(
                signature_envelope_bytes=asymmetric.json_file_bytes(envelope),
                expected_context=context,
            )
        self.assertTrue(result["same_call_handle_read_pin_bytes_used_for_cng"])
        self.assertFalse(result["external_public_key_pin_provisioning_verified"])
        self.assertFalse(result["owner_authority_verified"])

    def test_candidate_receipt_overclaim_and_tamper_are_rejected(self) -> None:
        overclaim = self._candidate_receipt(
            external_public_key_pin_provisioning_verified=True
        )
        tampered = self._candidate_receipt()
        tampered["pin_bytes_length"] = int(tampered["pin_bytes_length"]) + 1
        wrong_root = self._candidate_receipt(
            presented_root_expectation_sha256="f" * 64
        )
        wrong_token = self._candidate_receipt(
            effective_verifier_token_source="CALLER_ASSERTED_TOKEN"
        )
        for receipt in (overclaim, tampered, wrong_root, wrong_token):
            with self.subTest(receipt=receipt):
                @contextmanager
                def hold(**_kwargs: object):
                    yield candidate._HeldPinCandidate(
                        raw=self.pin_bytes,
                        pin=self.pin,
                        receipt=receipt,
                    )

                with patch.object(candidate, "_hold_windows_pin_candidate", hold):
                    with self.assertRaises(
                        candidate.P0WindowsExternalPublicKeyPinCandidateError
                    ):
                        self._execute()

    def test_pin_projection_mismatch_is_rejected_after_fresh_owner_state(self) -> None:
        wrong = deepcopy(self.pin)
        wrong["key_id"] = "projection-substitution"

        @contextmanager
        def hold(**_kwargs: object):
            yield candidate._HeldPinCandidate(
                raw=self.pin_bytes,
                pin=wrong,
                receipt=self._candidate_receipt(),
            )

        with patch.object(candidate, "_hold_windows_pin_candidate", hold):
            with self.assertRaises(
                candidate.P0WindowsExternalPublicKeyPinCandidateError
            ):
                self._execute()

    def test_invalid_signature_envelope_fails_without_owner_state_leak(self) -> None:
        malformed = self.envelope_bytes[:-2]

        @contextmanager
        def hold(**_kwargs: object):
            with self._fake_hold(**_kwargs) as value:
                yield value

        baseline = len(asymmetric._ISSUED_OWNER_STATES)
        with patch.object(candidate, "_hold_windows_pin_candidate", hold):
            with self.assertRaises(
                candidate.P0WindowsExternalPublicKeyPinCandidateError
            ):
                self._execute(signature_envelope_bytes=malformed)
        self.assertEqual(len(asymmetric._ISSUED_OWNER_STATES), baseline)

    def test_security_policy_rejects_null_unprotected_owner_and_each_mutation_right(self) -> None:
        safe = candidate._SecuritySnapshot(
            owner_sid="S-1-5-18",
            owner_sid_sha256="1" * 64,
            group_sid_sha256="2" * 64,
            sddl_sha256="3" * 64,
            dacl_present=True,
            dacl_null=False,
            dacl_protected=True,
            effective_token_owner_membership=False,
            mutation_access={name: False for name, _ in candidate._FILE_MUTATION_RIGHTS},
        )
        candidate._validate_security_snapshot(safe, "safe")
        for changes in (
            {"dacl_present": False},
            {"dacl_null": True},
            {"dacl_protected": False},
            {"effective_token_owner_membership": True},
        ):
            with self.subTest(changes=changes):
                value = candidate._SecuritySnapshot(
                    **{**safe.__dict__, **changes}
                )
                with self.assertRaises(
                    candidate.P0WindowsExternalPublicKeyPinCandidateError
                ):
                    candidate._validate_security_snapshot(value, "unsafe")
        for right in safe.mutation_access:
            with self.subTest(right=right):
                rights = dict(safe.mutation_access)
                rights[right] = True
                value = candidate._SecuritySnapshot(
                    **{**safe.__dict__, "mutation_access": rights}
                )
                with self.assertRaises(
                    candidate.P0WindowsExternalPublicKeyPinCandidateError
                ):
                    candidate._validate_security_snapshot(value, "unsafe")

    def test_effective_thread_token_selection_fallback_and_cleanup_are_fail_closed(self) -> None:
        class FakeTokenApi:
            def __init__(
                self,
                *,
                thread_token: bool,
                close_ok: bool = True,
                process_ok: bool = True,
                duplicate_ok: bool = True,
                process_failure_handle: bool = False,
            ) -> None:
                self.thread_token = thread_token
                self.close_ok = close_ok
                self.process_ok = process_ok
                self.duplicate_ok = duplicate_ok
                self.process_failure_handle = process_failure_handle
                self.calls: list[str] = []
                self.thread_args: tuple[int, bool] | None = None
                self.process_rights: int | None = None
                self.duplicate_level: int | None = None

            @staticmethod
            def _set_handle(target: object, value: int) -> None:
                pointer = candidate.ctypes.cast(
                    target,
                    candidate.ctypes.POINTER(candidate.wintypes.HANDLE),
                )
                pointer.contents.value = value

            def GetCurrentThread(self) -> int:
                return 11

            def GetCurrentProcess(self) -> int:
                return 22

            def OpenThreadToken(
                self, _thread: int, _rights: int, _open_as_self: bool, target: object
            ) -> bool:
                self.calls.append("OpenThreadToken")
                self.thread_args = (_rights, _open_as_self)
                if not self.thread_token:
                    return False
                self._set_handle(target, 101)
                return True

            def OpenProcessToken(
                self, _process: int, _rights: int, target: object
            ) -> bool:
                self.calls.append("OpenProcessToken")
                self.process_rights = _rights
                if self.process_ok:
                    self._set_handle(target, 202)
                    return True
                if self.process_failure_handle:
                    self._set_handle(target, 404)
                return False

            def DuplicateToken(
                self, _token: object, _level: int, target: object
            ) -> bool:
                self.calls.append("DuplicateToken")
                self.duplicate_level = _level
                if self.duplicate_ok:
                    self._set_handle(target, 303)
                    return True
                return False

            def CloseHandle(self, handle: object) -> bool:
                self.calls.append(f"CloseHandle:{int(handle.value)}")
                return self.close_ok

        thread_api = FakeTokenApi(thread_token=True)
        with candidate._impersonation_token(thread_api) as (token, source):
            self.assertEqual(token, 303)
            self.assertEqual(source, "THREAD_IMPERSONATION_TOKEN")
        self.assertNotIn("OpenProcessToken", thread_api.calls)
        self.assertEqual(
            thread_api.thread_args,
            (candidate._TOKEN_QUERY | candidate._TOKEN_DUPLICATE, True),
        )
        self.assertEqual(
            thread_api.duplicate_level, candidate._SECURITY_IMPERSONATION
        )

        process_api = FakeTokenApi(thread_token=False)
        with patch.object(
            candidate.ctypes, "get_last_error", return_value=candidate._ERROR_NO_TOKEN
        ):
            with candidate._impersonation_token(process_api) as (_token, source):
                self.assertEqual(source, "PROCESS_PRIMARY_TOKEN_NO_THREAD_TOKEN")
        self.assertIn("OpenProcessToken", process_api.calls)
        self.assertEqual(
            process_api.process_rights,
            candidate._TOKEN_QUERY | candidate._TOKEN_DUPLICATE,
        )

        denied_api = FakeTokenApi(thread_token=False)
        with patch.object(candidate.ctypes, "get_last_error", return_value=5):
            with self.assertRaises(
                candidate.P0WindowsExternalPublicKeyPinCandidateError
            ):
                with candidate._impersonation_token(denied_api):
                    self.fail("non-ERROR_NO_TOKEN must not fall back")
        self.assertNotIn("OpenProcessToken", denied_api.calls)

        duplicate_failure_api = FakeTokenApi(
            thread_token=True, duplicate_ok=False
        )
        with patch.object(candidate.ctypes, "get_last_error", return_value=6):
            with self.assertRaises(
                candidate.P0WindowsExternalPublicKeyPinCandidateError
            ):
                with candidate._impersonation_token(duplicate_failure_api):
                    self.fail("DuplicateToken failure must not yield")
        self.assertIn("CloseHandle:101", duplicate_failure_api.calls)

        process_failure_api = FakeTokenApi(
            thread_token=False,
            process_ok=False,
            process_failure_handle=True,
        )
        errors = iter((candidate._ERROR_NO_TOKEN, 5, 5))
        with patch.object(
            candidate.ctypes, "get_last_error", side_effect=lambda: next(errors)
        ):
            with self.assertRaises(
                candidate.P0WindowsExternalPublicKeyPinCandidateError
            ):
                with candidate._impersonation_token(process_failure_api):
                    self.fail("OpenProcessToken failure must not yield")
        self.assertIn("CloseHandle:404", process_failure_api.calls)

        cleanup_api = FakeTokenApi(thread_token=True, close_ok=False)
        sentinel = RuntimeError("primary")
        with patch.object(candidate.ctypes, "get_last_error", return_value=6):
            with self.assertRaisesRegex(RuntimeError, "primary"):
                with candidate._impersonation_token(cleanup_api):
                    raise sentinel
        self.assertEqual(
            [call for call in cleanup_api.calls if call.startswith("CloseHandle")],
            ["CloseHandle:303", "CloseHandle:101"],
        )

        cleanup_only_api = FakeTokenApi(thread_token=True, close_ok=False)
        with patch.object(candidate.ctypes, "get_last_error", return_value=6):
            with self.assertRaisesRegex(
                candidate.P0WindowsExternalPublicKeyPinCandidateError,
                "token cleanup failed",
            ):
                with candidate._impersonation_token(cleanup_only_api):
                    pass

    def test_localfree_cleanup_attempts_all_and_preserves_primary_error(self) -> None:
        class FakeLocalApi:
            def __init__(self, *, fail: bool, raises: bool = False) -> None:
                self.fail = fail
                self.raises = raises
                self.calls: list[int] = []

            def LocalFree(self, handle: object) -> object:
                self.calls.append(int(handle.value))
                if self.raises:
                    raise OSError("LocalFree exception")
                return handle.value if self.fail else None

        handles = [
            ("one", candidate.ctypes.c_void_p(101)),
            ("two", candidate.ctypes.c_void_p(202)),
        ]
        primary = RuntimeError("primary")
        failure = FakeLocalApi(fail=True)
        candidate._free_local_handles(failure, handles, primary)
        self.assertEqual(failure.calls, [101, 202])

        exceptional = FakeLocalApi(fail=False, raises=True)
        candidate._free_local_handles(exceptional, handles, primary)
        self.assertEqual(exceptional.calls, [101, 202])

        cleanup_only = FakeLocalApi(fail=True)
        with self.assertRaisesRegex(
            candidate.P0WindowsExternalPublicKeyPinCandidateError,
            "local-allocation cleanup failed",
        ):
            candidate._free_local_handles(cleanup_only, handles, None)

    def test_signed_packet_identity_and_protected_paths_reject_decoy_roots(self) -> None:
        expected = candidate._signed_root_expectation(self.preauthorization_bytes)
        packet = self.preauthorization["allowed_packet_root"]
        handles: list[tuple[str, object, object]] = [
            (
                "run_root",
                object(),
                SimpleNamespace(
                    final_path=(
                        "\\\\?\\Volume{00000000-0000-0000-0000-000000000000}"
                        "\\run"
                    ),
                    volume_serial=777,
                    file_id="c" * 32,
                ),
            ),
            (
                "packet_root",
                object(),
                SimpleNamespace(
                    final_path=packet["final_volume_guid_path"],
                    volume_serial=int(packet["volume_serial_decimal"]),
                    file_id=packet["file_id_128_hex"],
                ),
            ),
        ]
        for index, category in enumerate(runtime.REQUIRED_PROTECTED_CATEGORIES):
            handles.append(
                (
                    category,
                    object(),
                    SimpleNamespace(
                        final_path=expected.protected_final_paths[category],
                        volume_serial=123456789,
                        file_id=f"{index + 1:032x}",
                    ),
                )
            )
        parent_handles = [
            (
                parent.root_id,
                object(),
                SimpleNamespace(
                    final_path=parent.final_path,
                    volume_serial=parent.volume_serial,
                    file_id=parent.file_id,
                ),
            )
            for parent in expected.protected_parent_roots
        ]
        projection = candidate._signed_root_binding_projection(
            handles, parent_handles, expected
        )
        self.assertEqual(
            projection["signed_expectation_sha256"],
            candidate.canonical_sha256(expected.projection()),
        )
        for index, replacement in (
            (
                1,
                SimpleNamespace(
                    final_path=packet["final_volume_guid_path"],
                    volume_serial=int(packet["volume_serial_decimal"]),
                    file_id="f" * 32,
                ),
            ),
            (
                1,
                SimpleNamespace(
                    final_path=packet["final_volume_guid_path"],
                    volume_serial=int(packet["volume_serial_decimal"]) + 1,
                    file_id=packet["file_id_128_hex"],
                ),
            ),
            (
                1,
                SimpleNamespace(
                    final_path=(
                        "\\\\?\\Volume{00000000-0000-0000-0000-000000000000}"
                        "\\decoy-packet"
                    ),
                    volume_serial=int(packet["volume_serial_decimal"]),
                    file_id=packet["file_id_128_hex"],
                ),
            ),
            (
                2,
                SimpleNamespace(
                    final_path=(
                        "\\\\?\\Volume{00000000-0000-0000-0000-000000000000}"
                        "\\decoy"
                    ),
                    volume_serial=123456789,
                    file_id="1" * 32,
                ),
            ),
            (
                2,
                SimpleNamespace(
                    final_path=expected.protected_final_paths[
                        runtime.REQUIRED_PROTECTED_CATEGORIES[0]
                    ],
                    volume_serial=123456790,
                    file_id="1" * 32,
                ),
            ),
        ):
            tampered = list(handles)
            label, handle, _snapshot = tampered[index]
            tampered[index] = (label, handle, replacement)
            with self.subTest(label=label):
                with self.assertRaises(
                    candidate.P0WindowsExternalPublicKeyPinCandidateError
                ):
                    candidate._signed_root_binding_projection(
                        tampered, parent_handles, expected
                    )
        wrong_parent = list(parent_handles)
        root_id, handle, snapshot = wrong_parent[0]
        wrong_parent[0] = (
            root_id,
            handle,
            SimpleNamespace(
                final_path=snapshot.final_path,
                volume_serial=snapshot.volume_serial,
                file_id="e" * 32,
            ),
        )
        with self.assertRaises(
            candidate.P0WindowsExternalPublicKeyPinCandidateError
        ):
            candidate._signed_root_binding_projection(
                handles, wrong_parent, expected
            )
    def test_protected_root_map_is_exact_ordered_and_path_overlap_is_bidirectional(self) -> None:
        roots = {
            category: Path(f"C:/protected/{index}")
            for index, category in enumerate(runtime.REQUIRED_PROTECTED_CATEGORIES)
        }
        self.assertEqual(len(candidate._strict_protected_roots(roots)), 6)
        reversed_roots = dict(reversed(list(roots.items())))
        with self.assertRaises(candidate.P0WindowsExternalPublicKeyPinCandidateError):
            candidate._strict_protected_roots(reversed_roots)
        self.assertTrue(candidate._paths_overlap("X:\\a", "X:\\a\\b"))
        self.assertTrue(candidate._paths_overlap("X:\\a\\b", "X:\\a"))
        self.assertFalse(candidate._paths_overlap("X:\\ab", "X:\\a"))

    def test_relative_unc_ads_dot_and_trailing_components_fail_closed(self) -> None:
        for value in (
            "relative\\pin-store",
            "\\\\server\\share\\pin-store",
            "C:\\safe\\..\\pin-store",
            "C:\\safe\\pin-store:ads",
            "C:\\safe\\pin-store.",
            "C:\\safe\\pin-store ",
        ):
            with self.subTest(value=value):
                with self.assertRaises(
                    candidate.P0WindowsExternalPublicKeyPinCandidateError
                ):
                    candidate._normalise_path(value, "pin_store_dir")

    def test_current_user_owned_temp_pin_store_is_not_external_provisioning(self) -> None:
        with tempfile.TemporaryDirectory() as root_raw:
            root = Path(root_raw)
            store = root / "pin-store"
            run_root = root / "run"
            packet_root = root / "packet"
            protected_base = root / "protected"
            store.mkdir()
            run_root.mkdir()
            packet_root.mkdir()
            protected_base.mkdir()
            protected = {}
            for index, category_name in enumerate(
                runtime.REQUIRED_PROTECTED_CATEGORIES
            ):
                path = protected_base / f"category-{index}"
                path.mkdir()
                protected[category_name] = path
            (store / candidate.PUBLIC_KEY_PIN_FILENAME).write_bytes(self.pin_bytes)
            (
                preauthorization_bytes,
                envelope_bytes,
                expected_context,
            ) = self._actualized_root_material(
                packet_root=packet_root,
                protected_base=protected_base,
            )
            with self.assertRaises(
                candidate.P0WindowsExternalPublicKeyPinCandidateError
            ) as raised:
                candidate.execute_windows_external_public_key_pin_candidate_supervisor(
                    pin_store_dir=store,
                    run_root=run_root,
                    packet_root=packet_root,
                    protected_category_roots=protected,
                    signature_envelope_bytes=envelope_bytes,
                    owner_root_preauthorization_bytes=preauthorization_bytes,
                    expected_context=expected_context,
                )
            self.assertRegex(
                str(raised.exception),
                "present, non-NULL, protected DACL|must not own",
            )

    def test_pin_store_inside_signed_protected_parent_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as root_raw:
            root = Path(root_raw)
            run_root = root / "run"
            packet_root = root / "packet"
            protected_base = root / "protected"
            store = protected_base / "pin-store"
            for path in (run_root, packet_root, protected_base, store):
                path.mkdir()
            protected = {}
            for index, category_name in enumerate(
                runtime.REQUIRED_PROTECTED_CATEGORIES
            ):
                path = protected_base / f"category-{index}"
                path.mkdir()
                protected[category_name] = path
            (store / candidate.PUBLIC_KEY_PIN_FILENAME).write_bytes(self.pin_bytes)
            (
                preauthorization_bytes,
                envelope_bytes,
                expected_context,
            ) = self._actualized_root_material(
                packet_root=packet_root,
                protected_base=protected_base,
            )
            with self.assertRaisesRegex(
                candidate.P0WindowsExternalPublicKeyPinCandidateError,
                "pin store overlaps",
            ):
                candidate.execute_windows_external_public_key_pin_candidate_supervisor(
                    pin_store_dir=store,
                    run_root=run_root,
                    packet_root=packet_root,
                    protected_category_roots=protected,
                    signature_envelope_bytes=envelope_bytes,
                    owner_root_preauthorization_bytes=preauthorization_bytes,
                    expected_context=expected_context,
                )


if __name__ == "__main__":
    unittest.main()
