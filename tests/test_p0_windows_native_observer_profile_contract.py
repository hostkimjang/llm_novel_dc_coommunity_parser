from __future__ import annotations

import base64
from copy import deepcopy
import ctypes
from datetime import datetime, timedelta, timezone
import hashlib
import inspect
import os
import struct
import unittest
from unittest.mock import patch

from llm_batch.grounding import p0_windows_native_observer_profile_contract as native
from llm_batch.grounding import (
    p0_windows_native_observer_positive_predicate_candidate as positive,
)
from llm_batch.grounding import p0_windows_owner_deployment_projection as deployment
from llm_batch.grounding import p0_windows_owner_policy_contract as owner_policy


_P256_ORDER = int(
    "ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551",
    16,
)
_P256_SPKI_PREFIX = bytes.fromhex(
    "3059301306072a8648ce3d020106082a8648ce3d03010703420004"
)


class _TestOnlyCngSigner:
    """Ephemeral test signer; the production contract exposes no signer API."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise unittest.SkipTest("Windows CNG is required")
        bcrypt = ctypes.WinDLL("bcrypt", use_last_error=True)
        self._handle = ctypes.c_void_p
        self._byte_pointer = ctypes.POINTER(ctypes.c_ubyte)
        self._ulong = ctypes.c_ulong
        self._ntstatus = ctypes.c_long
        self._provider = self._handle()
        self._key = self._handle()

        def prototype(name: str, args: list[object]):
            function = getattr(bcrypt, name)
            function.argtypes = args
            function.restype = self._ntstatus
            return function

        self._open = prototype(
            "BCryptOpenAlgorithmProvider",
            [
                ctypes.POINTER(self._handle),
                ctypes.c_wchar_p,
                ctypes.c_wchar_p,
                self._ulong,
            ],
        )
        self._generate = prototype(
            "BCryptGenerateKeyPair",
            [self._handle, ctypes.POINTER(self._handle), self._ulong, self._ulong],
        )
        self._finalize = prototype(
            "BCryptFinalizeKeyPair", [self._handle, self._ulong]
        )
        self._export = prototype(
            "BCryptExportKey",
            [
                self._handle,
                self._handle,
                ctypes.c_wchar_p,
                self._byte_pointer,
                self._ulong,
                ctypes.POINTER(self._ulong),
                self._ulong,
            ],
        )
        self._sign = prototype(
            "BCryptSignHash",
            [
                self._handle,
                ctypes.c_void_p,
                self._byte_pointer,
                self._ulong,
                self._byte_pointer,
                self._ulong,
                ctypes.POINTER(self._ulong),
                self._ulong,
            ],
        )
        self._destroy = prototype("BCryptDestroyKey", [self._handle])
        self._close = prototype(
            "BCryptCloseAlgorithmProvider", [self._handle, self._ulong]
        )
        self._ok(self._open(ctypes.byref(self._provider), "ECDSA_P256", None, 0))
        self._ok(self._generate(self._provider, ctypes.byref(self._key), 256, 0))
        self._ok(self._finalize(self._key, 0))
        blob = self._export_public_blob()
        self.x = blob[8:40]
        self.y = blob[40:72]

    @staticmethod
    def _ok(status: int) -> None:
        if status != 0:
            raise RuntimeError(
                f"test-only CNG operation failed: 0x{status & 0xffffffff:08x}"
            )

    def _export_public_blob(self) -> bytes:
        size = self._ulong()
        self._ok(
            self._export(
                self._key,
                None,
                "ECCPUBLICBLOB",
                None,
                0,
                ctypes.byref(size),
                0,
            )
        )
        output = (ctypes.c_ubyte * size.value)()
        self._ok(
            self._export(
                self._key,
                None,
                "ECCPUBLICBLOB",
                output,
                size.value,
                ctypes.byref(size),
                0,
            )
        )
        result = bytes(output)
        if len(result) != 72 or struct.unpack("<II", result[:8]) != (0x31534345, 32):
            raise RuntimeError("unexpected test-only CNG public blob")
        return result

    @property
    def spki(self) -> bytes:
        return _P256_SPKI_PREFIX + self.x + self.y

    def sign_low_s(self, material: dict[str, object]) -> bytes:
        digest = hashlib.sha256(native.canonical_bytes(material)).digest()
        digest_buffer = (ctypes.c_ubyte * len(digest)).from_buffer_copy(digest)
        size = self._ulong()
        self._ok(
            self._sign(
                self._key,
                None,
                digest_buffer,
                len(digest),
                None,
                0,
                ctypes.byref(size),
                0,
            )
        )
        output = (ctypes.c_ubyte * size.value)()
        self._ok(
            self._sign(
                self._key,
                None,
                digest_buffer,
                len(digest),
                output,
                size.value,
                ctypes.byref(size),
                0,
            )
        )
        signature = bytes(output)
        r = int.from_bytes(signature[:32], "big")
        s = int.from_bytes(signature[32:], "big")
        if s > _P256_ORDER // 2:
            s = _P256_ORDER - s
        return r.to_bytes(32, "big") + s.to_bytes(32, "big")

    def close(self) -> None:
        if self._key.value:
            self._ok(self._destroy(self._key))
            self._key = self._handle()
        if self._provider.value:
            self._ok(self._close(self._provider, 0))
            self._provider = self._handle()


def _project(value: dict[str, object]) -> dict[str, object]:
    return native.with_projection_hash(value)


def _artifact(value: dict[str, object]) -> dict[str, object]:
    return native.with_artifact_hash(value)


class NativeObserverProfileContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.observer = _TestOnlyCngSigner()
        cls.owner_state = _TestOnlyCngSigner()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.observer.close()
        cls.owner_state.close()

    def _profile(self) -> dict[str, object]:
        observer_spki = self.observer.spki
        state_spki = self.owner_state.spki
        return _artifact(
            {
                "schema_version": native.PROFILE_SCHEMA,
                "record_origin": native.PROFILE_ORIGIN,
                "domain": native.PROFILE_DOMAIN,
                "deployment_projection_sha256": "1" * 64,
                "service_name": deployment.SERVICE_NAME,
                "service_sid": deployment.SERVICE_SID,
                "fixed_pipe_name": native.FIXED_PIPE_NAME,
                "request_schema_version": native.REQUEST_SCHEMA,
                "request_domain": native.REQUEST_DOMAIN,
                "receipt_body_schema_version": native.RECEIPT_BODY_SCHEMA,
                "receipt_body_domain": native.RECEIPT_BODY_DOMAIN,
                "receipt_signature_schema_version": native.RECEIPT_SIGNATURE_SCHEMA,
                "receipt_signature_domain": native.RECEIPT_SIGNATURE_DOMAIN,
                "challenge_size_bytes": native.CHALLENGE_SIZE_BYTES,
                "max_request_bytes": native.MAX_REQUEST_BYTES,
                "max_response_bytes": native.MAX_RESPONSE_BYTES,
                "observer_key_id": "observer-tpm-key-001",
                "observer_key_epoch": 3,
                "observer_key_role": native.OBSERVER_KEY_ROLE,
                "observer_key_algorithm": native.OBSERVER_KEY_ALGORITHM,
                "observer_public_key_spki_der_base64": base64.b64encode(
                    observer_spki
                ).decode("ascii"),
                "observer_public_key_fingerprint_sha256": hashlib.sha256(
                    observer_spki
                ).hexdigest(),
                "observer_key_storage_provider": native.OBSERVER_KEY_STORAGE_PROVIDER,
                "observer_key_unique_name_sha256": "2" * 64,
                "observer_key_allowed_signature_domains": [
                    native.RECEIPT_SIGNATURE_DOMAIN
                ],
                "observer_key_hardware_backed_required": True,
                "observer_key_non_exportable_required": True,
                "observer_key_attestation_format": native.OBSERVER_KEY_ATTESTATION_FORMAT,
                "observer_key_attestation_sha256": "3" * 64,
                "observer_key_security_template_sha256": "4" * 64,
                "owner_state_ticket_schema_version": native.OWNER_STATE_TICKET_SCHEMA,
                "owner_state_ticket_domain": native.OWNER_STATE_TICKET_DOMAIN,
                "owner_state_authority_key_id": "owner-state-key-001",
                "owner_state_authority_key_epoch": 7,
                "owner_state_authority_key_role": native.OWNER_STATE_KEY_ROLE,
                "owner_state_authority_algorithm": native.OWNER_STATE_KEY_ALGORITHM,
                "owner_state_authority_public_key_spki_der_base64": base64.b64encode(
                    state_spki
                ).decode("ascii"),
                "owner_state_authority_spki_sha256": hashlib.sha256(
                    state_spki
                ).hexdigest(),
                "owner_state_authority_allowed_signature_domains": [
                    native.OWNER_STATE_TICKET_DOMAIN
                ],
                "trusted_time_model": native.TRUSTED_TIME_MODEL,
                "nonce_state_model": native.NONCE_STATE_MODEL,
                "max_ticket_lifetime_seconds": 300,
                "min_revocation_sequence": 11,
                "min_observer_counter": 19,
            }
        )

    def _request(self, profile: dict[str, object]) -> dict[str, object]:
        challenge = bytes(range(native.CHALLENGE_SIZE_BYTES))
        return _artifact(
            {
                "schema_version": native.REQUEST_SCHEMA,
                "record_origin": native.REQUEST_ORIGIN,
                "domain": native.REQUEST_DOMAIN,
                "request_id": "11111111-1111-4111-8111-111111111111",
                "challenge_base64": base64.b64encode(challenge).decode("ascii"),
                "challenge_sha256": hashlib.sha256(challenge).hexdigest(),
                "policy_id": "owner-policy-001",
                "policy_epoch": 1,
                "policy_body_bytes_sha256": "5" * 64,
                "deployment_projection_sha256": profile[
                    "deployment_projection_sha256"
                ],
                "native_observer_profile_sha256": profile["artifact_sha256"],
            }
        )

    def _sign_ticket(self, ticket: dict[str, object]) -> dict[str, object]:
        material = {
            key: value
            for key, value in ticket.items()
            if key not in {"signature_rs_base64", "artifact_sha256"}
        }
        ticket["signature_rs_base64"] = base64.b64encode(
            self.owner_state.sign_low_s(material)
        ).decode("ascii")
        return _artifact(ticket)

    def _ticket(
        self, profile: dict[str, object], request: dict[str, object]
    ) -> dict[str, object]:
        return self._sign_ticket(
            {
                "schema_version": native.OWNER_STATE_TICKET_SCHEMA,
                "record_origin": native.OWNER_STATE_TICKET_ORIGIN,
                "domain": native.OWNER_STATE_TICKET_DOMAIN,
                "ticket_id": "22222222-2222-4222-8222-222222222222",
                "decision": native.TICKET_DECISION,
                "request_id": request["request_id"],
                "request_artifact_sha256": request["artifact_sha256"],
                "challenge_sha256": request["challenge_sha256"],
                "policy_id": request["policy_id"],
                "policy_epoch": request["policy_epoch"],
                "policy_body_bytes_sha256": request["policy_body_bytes_sha256"],
                "deployment_projection_sha256": request[
                    "deployment_projection_sha256"
                ],
                "native_observer_profile_sha256": profile["artifact_sha256"],
                "observer_key_id": profile["observer_key_id"],
                "observer_key_epoch": profile["observer_key_epoch"],
                "revocation_sequence": 11,
                "observer_counter": 19,
                "issued_at_utc": "2026-09-03T00:00:00Z",
                "not_before_utc": "2026-09-03T00:00:01Z",
                "expires_at_utc": "2026-09-03T00:04:01Z",
                "owner_state_authority_key_id": profile[
                    "owner_state_authority_key_id"
                ],
                "owner_state_authority_key_epoch": profile[
                    "owner_state_authority_key_epoch"
                ],
                "owner_state_authority_key_role": native.OWNER_STATE_KEY_ROLE,
                "algorithm": native.OWNER_STATE_KEY_ALGORITHM,
                "signature_rs_base64": "",
            }
        )

    def _providers(self) -> dict[str, object]:
        modules: list[dict[str, object]] = []
        for index, (role, name) in enumerate(deployment.PROVIDER_MODULES):
            modules.append(
                _project(
                    {
                        "role": role,
                        "module_name": name,
                        "final_volume_guid_path": (
                            "\\\\?\\Volume{12345678-1234-1234-1234-1234567890ab}"
                            f"\\Windows\\System32\\{name}"
                        ),
                        "volume_serial_decimal": "123456789",
                        "file_id_128_hex": f"{index + 4:032x}",
                        "image_sha256": f"{index + 6:x}" * 64,
                        "signature_type": deployment.PROVIDER_SIGNATURE_TYPE,
                        "signer_leaf_spki_sha256": "8" * 64,
                        "signer_root_spki_sha256": "9" * 64,
                        "catalog_status": "VERIFIED",
                        "handle_held": True,
                    }
                )
            )
        return {
            "modules": modules,
            "projection_sha256": native.canonical_sha256(modules),
        }

    def _body(
        self,
        profile: dict[str, object],
        request: dict[str, object],
        ticket: dict[str, object],
    ) -> dict[str, object]:
        policy_signature_sha = "a" * 64
        owner_anchor = "b" * 64
        return _artifact(
            {
                "schema_version": native.RECEIPT_BODY_SCHEMA,
                "record_origin": native.RECEIPT_BODY_ORIGIN,
                "domain": native.RECEIPT_BODY_DOMAIN,
                "receipt_id": "33333333-3333-4333-8333-333333333333",
                "request_id": request["request_id"],
                "request_artifact_sha256": request["artifact_sha256"],
                "challenge_sha256": request["challenge_sha256"],
                "owner_state_ticket_artifact_sha256": ticket["artifact_sha256"],
                "policy_id": request["policy_id"],
                "policy_epoch": request["policy_epoch"],
                "policy_body_bytes_sha256": request["policy_body_bytes_sha256"],
                "policy_signature_bytes_sha256": policy_signature_sha,
                "owner_anchor_sha256": owner_anchor,
                "deployment_projection_sha256": profile[
                    "deployment_projection_sha256"
                ],
                "native_observer_profile_sha256": profile["artifact_sha256"],
                "observer_key_id": profile["observer_key_id"],
                "observer_key_epoch": profile["observer_key_epoch"],
                "qpc_frequency": 10_000_000,
                "observation_started_qpc": 100_000_000,
                "observation_finished_qpc": 110_000_000,
                "system_boot_id_sha256": "c" * 64,
                "policy_store_evidence": _project(
                    {
                        "policy_body_bytes_sha256": request[
                            "policy_body_bytes_sha256"
                        ],
                        "policy_signature_bytes_sha256": policy_signature_sha,
                        "owner_anchor_sha256": owner_anchor,
                        "all_required_handles_held": True,
                        "pre_post_stable": True,
                    }
                ),
                "service_evidence": _project(
                    {
                        "service_name": deployment.SERVICE_NAME,
                        "service_sid": deployment.SERVICE_SID,
                        "service_status": "RUNNING",
                        "service_pid": 4242,
                        "process_creation_time_100ns": 999_999,
                        "token_user_sid": deployment.SERVICE_START_ACCOUNT_SID,
                        "service_sid_enabled": True,
                        "service_sid_restricted": True,
                        "token_is_restricted": True,
                        "linked_token_absent": True,
                    }
                ),
                "image_evidence": _project(
                    {
                        "final_volume_guid_path": (
                            "\\\\?\\Volume{12345678-1234-1234-1234-1234567890ab}"
                            "\\Program Files\\llm-novel-dc\\owner-verifier-v2"
                            "\\llm-novel-dc-owner-verifier.exe"
                        ),
                        "volume_serial_decimal": "123456789",
                        "file_id_128_hex": "1" * 32,
                        "image_sha256": "d" * 64,
                        "handle_held": True,
                    }
                ),
                "bootstrap_resource_evidence": _project(
                    {
                        "resource_type": deployment.BOOTSTRAP_RESOURCE_TYPE,
                        "resource_name": deployment.BOOTSTRAP_RESOURCE_NAME,
                        "language_id": deployment.BOOTSTRAP_RESOURCE_LANGUAGE_ID,
                        "exact_count": 1,
                        "resource_sha256": "e" * 64,
                    }
                ),
                "authenticode_evidence": _project(
                    {
                        "signature_type": deployment.VERIFIER_SIGNATURE_TYPE,
                        "signer_leaf_spki_sha256": "1" * 64,
                        "signer_root_spki_sha256": "2" * 64,
                        "winverifytrust_status": "VERIFIED",
                        "chain_status": "VERIFIED",
                        "revocation_status": "CURRENT",
                    }
                ),
                "wdac_evidence": _project(
                    {
                        "policy_id": "44444444-4444-4444-8444-444444444444",
                        "base_policy_id": "55555555-5555-4555-8555-555555555555",
                        "policy_sha256": "3" * 64,
                        "umci_enforcement_status": "ENFORCED",
                    }
                ),
                "provider_evidence": self._providers(),
                "observer_key_evidence": _project(
                    {
                        "key_id": profile["observer_key_id"],
                        "key_epoch": profile["observer_key_epoch"],
                        "storage_provider": profile["observer_key_storage_provider"],
                        "key_unique_name_sha256": profile[
                            "observer_key_unique_name_sha256"
                        ],
                        "public_key_fingerprint_sha256": profile[
                            "observer_public_key_fingerprint_sha256"
                        ],
                        "hardware_backed_observed": True,
                        "non_exportable_observed": True,
                        "attestation_sha256": profile[
                            "observer_key_attestation_sha256"
                        ],
                        "security_template_sha256": profile[
                            "observer_key_security_template_sha256"
                        ],
                    }
                ),
                "owner_state_evidence": _project(
                    {
                        "ticket_id": ticket["ticket_id"],
                        "ticket_artifact_sha256": ticket["artifact_sha256"],
                        "revocation_sequence": ticket["revocation_sequence"],
                        "observer_counter": ticket["observer_counter"],
                        "ticket_window_structure_observed": True,
                        "nonce_consumption_observed": True,
                        "trusted_time_ticket_observed": True,
                    }
                ),
                "diagnostics": [],
            }
        )

    def _sign_receipt(
        self, profile: dict[str, object], body_bytes: bytes
    ) -> dict[str, object]:
        signature: dict[str, object] = {
            "schema_version": native.RECEIPT_SIGNATURE_SCHEMA,
            "record_origin": native.RECEIPT_SIGNATURE_ORIGIN,
            "domain": native.RECEIPT_SIGNATURE_DOMAIN,
            "receipt_body_bytes_sha256": hashlib.sha256(body_bytes).hexdigest(),
            "observer_key_id": profile["observer_key_id"],
            "observer_key_epoch": profile["observer_key_epoch"],
            "observer_key_role": native.OBSERVER_KEY_ROLE,
            "public_key_fingerprint_sha256": profile[
                "observer_public_key_fingerprint_sha256"
            ],
            "algorithm": native.OBSERVER_KEY_ALGORITHM,
            "signature_rs_base64": "",
        }
        material = {
            key: value
            for key, value in signature.items()
            if key not in {"signature_rs_base64", "artifact_sha256"}
        }
        signature["signature_rs_base64"] = base64.b64encode(
            self.observer.sign_low_s(material)
        ).decode("ascii")
        return _artifact(signature)

    def _bundle(self) -> dict[str, object]:
        profile = self._profile()
        request = self._request(profile)
        ticket = self._ticket(profile, request)
        body = self._body(profile, request, ticket)
        body_bytes = native.json_file_bytes(body)
        signature = self._sign_receipt(profile, body_bytes)
        return {
            "native_observer_profile": profile,
            "request_bytes": native.json_file_bytes(request),
            "owner_state_ticket_bytes": native.json_file_bytes(ticket),
            "raw_receipt_body_bytes": body_bytes,
            "detached_observer_signature_bytes": native.json_file_bytes(signature),
        }

    def _validate(self, bundle: dict[str, object] | None = None) -> dict[str, object]:
        return native.validate_presented_windows_native_observer_profile_component(
            **(bundle or self._bundle())
        )

    def test_valid_transcript_is_component_only_and_zero_authority(self) -> None:
        receipt = self._validate()
        self.assertEqual(receipt["schema_version"], native.VALIDATION_RECEIPT_SCHEMA)
        self.assertEqual(receipt["gate_status"], native.GATE_STATUS)
        self.assertEqual(receipt["decision"], "NO_GO")
        for field in (
            "strict_profile_contract_verified",
            "strict_canonical_transcript_verified",
            "request_ticket_receipt_cross_binding_verified",
            "observer_and_owner_state_key_roles_disjoint_verified",
            "owner_state_ticket_signature_math_verified",
            "observer_receipt_signature_math_verified",
            "owner_state_ticket_time_window_structure_verified",
            "signed_revocation_and_counter_floor_structure_verified",
            "presented_profile_only",
        ):
            self.assertIs(receipt[field], True, field)
        for field in native._ALWAYS_FALSE_FIELDS:
            self.assertIs(receipt[field], False, field)
        self.assertIs(receipt["serialized_receipt_authoritative"], False)
        self.assertEqual(receipt["credited_actual_source_claim_count"], 0)
        self.assertEqual(receipt["credited_actual_a_context_review_count"], 0)
        material = dict(receipt)
        declared = material.pop("receipt_sha256")
        self.assertEqual(declared, native.canonical_sha256(material))

    def test_all_green_presented_transcript_is_still_positive_rejected(self) -> None:
        bundle = self._bundle()
        receipt = positive.reject_presented_windows_native_observer_component_candidate(
            **bundle
        )
        self.assertEqual(receipt["decision"], "POSITIVE_REJECTED")
        self.assertEqual(receipt["failure_stage"], "PRESENTED_COMPONENT_ONLY")
        self.assertTrue(
            receipt[
                "selected_presented_runtime_flags_no_explicit_negative_but_rejected"
            ]
        )
        self.assertFalse(
            receipt["presented_negative_runtime_projection_detected"]
        )
        self.assertTrue(receipt["positive_candidate_hard_rejected"])
        self.assertFalse(receipt["positive_native_observer_evidence_verified"])
        self.assertEqual(receipt["credited_actual_source_claim_count"], 0)
        self.assertEqual(receipt["credited_actual_a_context_review_count"], 0)

    def test_signed_negative_runtime_transcript_passes_component_but_is_hard_rejected(self) -> None:
        bundle = self._bundle()
        profile = bundle["native_observer_profile"]
        body = __import__("json").loads(bundle["raw_receipt_body_bytes"])
        service = body["service_evidence"]
        service.update(
            {
                "service_status": "NOT_RUNNING",
                "service_pid": 0,
                "process_creation_time_100ns": 0,
                "service_sid_enabled": False,
                "service_sid_restricted": False,
                "token_is_restricted": False,
                "linked_token_absent": False,
            }
        )
        body["service_evidence"] = _project(service)
        body["authenticode_evidence"]["winverifytrust_status"] = "FAILED"
        body["authenticode_evidence"] = _project(
            body["authenticode_evidence"]
        )
        body["wdac_evidence"]["umci_enforcement_status"] = "NOT_ENFORCED"
        body["wdac_evidence"] = _project(body["wdac_evidence"])
        body["observer_key_evidence"]["hardware_backed_observed"] = False
        body["observer_key_evidence"] = _project(
            body["observer_key_evidence"]
        )
        body["owner_state_evidence"]["nonce_consumption_observed"] = False
        body["owner_state_evidence"]["trusted_time_ticket_observed"] = False
        body["owner_state_evidence"] = _project(body["owner_state_evidence"])
        body["diagnostics"] = ["signed negative observation"]
        body = _artifact(body)
        body_bytes = native.json_file_bytes(body)
        bundle["raw_receipt_body_bytes"] = body_bytes
        bundle["detached_observer_signature_bytes"] = native.json_file_bytes(
            self._sign_receipt(profile, body_bytes)
        )

        component_receipt = self._validate(bundle)
        self.assertEqual(component_receipt["decision"], "NO_GO")
        receipt = positive.reject_presented_windows_native_observer_component_candidate(
            **bundle
        )
        self.assertEqual(
            receipt["failure_stage"], "PRESENTED_NEGATIVE_RUNTIME_EVIDENCE"
        )
        self.assertTrue(
            receipt["presented_negative_runtime_projection_detected"]
        )
        self.assertTrue(
            receipt["presented_negative_runtime_projection_hard_rejected"]
        )
        self.assertIn(
            "PRESENTED_NEGATIVE_RUNTIME_PROJECTION_DETECTED",
            receipt["blocker_codes"],
        )
        self.assertFalse(receipt["actual_authority_granted"])

    def test_resealed_component_receipt_cannot_become_positive_input(self) -> None:
        bundle = self._bundle()
        forged = self._validate(bundle)
        forged["decision"] = "GO"
        forged["receipt_sha256"] = native.canonical_sha256(
            {key: value for key, value in forged.items() if key != "receipt_sha256"}
        )
        with (
            patch.object(
                native,
                "validate_presented_windows_native_observer_profile_component",
                return_value=forged,
            ),
            self.assertRaises(
                positive.P0WindowsNativeObserverPositivePredicateCandidateError
            ),
        ):
            positive.reject_presented_windows_native_observer_component_candidate(
                **bundle
            )

    def test_nested_profile_validator_preserves_required_v3_cross_bindings(self) -> None:
        profile = self._profile()
        validated = native._validate_native_observer_profile(profile)
        for field in (
            "artifact_sha256",
            "deployment_projection_sha256",
            "service_name",
            "service_sid",
        ):
            self.assertEqual(validated[field], profile[field])

    def test_operational_preauthorization_domain_cannot_sign_observer_or_ticket(self) -> None:
        for field in (
            "observer_key_allowed_signature_domains",
            "owner_state_authority_allowed_signature_domains",
        ):
            profile = self._profile()
            profile[field] = [owner_policy.OPERATIONAL_SIGNATURE_DOMAIN]
            profile = _artifact(profile)
            with self.subTest(field=field), self.assertRaises(
                native.P0WindowsNativeObserverProfileContractError
            ):
                native._validate_native_observer_profile(profile)

    def test_observer_and_owner_state_keys_must_be_distinct(self) -> None:
        profile = self._profile()
        profile["owner_state_authority_key_id"] = profile["observer_key_id"]
        profile["owner_state_authority_public_key_spki_der_base64"] = profile[
            "observer_public_key_spki_der_base64"
        ]
        profile["owner_state_authority_spki_sha256"] = profile[
            "observer_public_key_fingerprint_sha256"
        ]
        profile = _artifact(profile)
        with self.assertRaises(native.P0WindowsNativeObserverProfileContractError):
            native._validate_native_observer_profile(profile)

    def test_high_s_ticket_and_observer_signatures_are_rejected(self) -> None:
        for artifact_key in (
            "owner_state_ticket_bytes",
            "detached_observer_signature_bytes",
        ):
            bundle = self._bundle()
            row = deepcopy(
                __import__("json").loads(bundle[artifact_key])
            )
            raw = base64.b64decode(row["signature_rs_base64"])
            row["signature_rs_base64"] = base64.b64encode(
                raw[:32] + (_P256_ORDER - 1).to_bytes(32, "big")
            ).decode("ascii")
            row = _artifact(row)
            bundle[artifact_key] = native.json_file_bytes(row)
            with self.subTest(artifact=artifact_key), self.assertRaises(
                native.P0WindowsNativeObserverProfileContractError
            ):
                self._validate(bundle)

    def test_wrong_ticket_and_receipt_domains_fail_even_when_resigned(self) -> None:
        bundle = self._bundle()
        ticket = __import__("json").loads(bundle["owner_state_ticket_bytes"])
        ticket["domain"] = native.RECEIPT_SIGNATURE_DOMAIN
        ticket = self._sign_ticket(ticket)
        bundle["owner_state_ticket_bytes"] = native.json_file_bytes(ticket)
        with self.assertRaises(native.P0WindowsNativeObserverProfileContractError):
            self._validate(bundle)

        bundle = self._bundle()
        signature = __import__("json").loads(
            bundle["detached_observer_signature_bytes"]
        )
        signature["domain"] = native.OWNER_STATE_TICKET_DOMAIN
        material = {
            key: value
            for key, value in signature.items()
            if key not in {"signature_rs_base64", "artifact_sha256"}
        }
        signature["signature_rs_base64"] = base64.b64encode(
            self.observer.sign_low_s(material)
        ).decode("ascii")
        signature = _artifact(signature)
        bundle["detached_observer_signature_bytes"] = native.json_file_bytes(
            signature
        )
        with self.assertRaises(native.P0WindowsNativeObserverProfileContractError):
            self._validate(bundle)

    def test_cross_request_replay_is_structurally_rejected(self) -> None:
        bundle = self._bundle()
        request = __import__("json").loads(bundle["request_bytes"])
        challenge = bytes(reversed(range(native.CHALLENGE_SIZE_BYTES)))
        request["request_id"] = "66666666-6666-4666-8666-666666666666"
        request["challenge_base64"] = base64.b64encode(challenge).decode("ascii")
        request["challenge_sha256"] = hashlib.sha256(challenge).hexdigest()
        request = _artifact(request)
        bundle["request_bytes"] = native.json_file_bytes(request)
        with self.assertRaises(native.P0WindowsNativeObserverProfileContractError):
            self._validate(bundle)

    def test_stateless_revalidation_never_claims_replay_consumption(self) -> None:
        bundle = self._bundle()
        first = self._validate(bundle)
        second = self._validate(bundle)
        self.assertEqual(first, second)
        self.assertIs(first["single_use_replay_consumed"], False)
        self.assertIs(first["durable_cross_process_nonce_verified"], False)
        self.assertIs(first["signature_freshness_verified"], False)

    def test_counter_revocation_floor_and_ticket_lifetime_fail_closed(self) -> None:
        for field, value in (
            ("revocation_sequence", 10),
            ("observer_counter", 18),
            ("expires_at_utc", "2026-09-03T00:30:01Z"),
        ):
            bundle = self._bundle()
            ticket = __import__("json").loads(bundle["owner_state_ticket_bytes"])
            ticket[field] = value
            ticket = self._sign_ticket(ticket)
            bundle["owner_state_ticket_bytes"] = native.json_file_bytes(ticket)
            with self.subTest(field=field), self.assertRaises(
                native.P0WindowsNativeObserverProfileContractError
            ):
                self._validate(bundle)

    def test_bool_integer_and_missing_evidence_field_are_rejected(self) -> None:
        profile = self._profile()
        profile["observer_key_epoch"] = True
        profile = _artifact(profile)
        with self.assertRaises(native.P0WindowsNativeObserverProfileContractError):
            native._validate_native_observer_profile(profile)

        bundle = self._bundle()
        body = __import__("json").loads(bundle["raw_receipt_body_bytes"])
        body["service_evidence"].pop("linked_token_absent")
        body["service_evidence"] = _project(body["service_evidence"])
        body = _artifact(body)
        bundle["raw_receipt_body_bytes"] = native.json_file_bytes(body)
        bundle["detached_observer_signature_bytes"] = native.json_file_bytes(
            self._sign_receipt(
                bundle["native_observer_profile"],
                bundle["raw_receipt_body_bytes"],
            )
        )
        with self.assertRaises(native.P0WindowsNativeObserverProfileContractError):
            self._validate(bundle)

    def test_noncanonical_and_duplicate_json_are_rejected(self) -> None:
        bundle = self._bundle()
        bundle["request_bytes"] = bundle["request_bytes"].replace(b"\n", b"\r\n")
        with self.assertRaises(native.P0WindowsNativeObserverProfileContractError):
            self._validate(bundle)

        bundle = self._bundle()
        request = bundle["request_bytes"]
        bundle["request_bytes"] = request.replace(
            b'{"artifact_sha256":',
            b'{"artifact_sha256":"' + b"0" * 64 + b'","artifact_sha256":',
            1,
        )
        with self.assertRaises(native.P0WindowsNativeObserverProfileContractError):
            self._validate(bundle)

    def test_signature_bit_tamper_and_key_role_swap_are_rejected(self) -> None:
        bundle = self._bundle()
        signature = __import__("json").loads(
            bundle["detached_observer_signature_bytes"]
        )
        raw = bytearray(base64.b64decode(signature["signature_rs_base64"]))
        raw[0] ^= 1
        signature["signature_rs_base64"] = base64.b64encode(raw).decode("ascii")
        signature = _artifact(signature)
        bundle["detached_observer_signature_bytes"] = native.json_file_bytes(
            signature
        )
        with self.assertRaises(native.P0WindowsNativeObserverProfileContractError):
            self._validate(bundle)

        bundle = self._bundle()
        signature = __import__("json").loads(
            bundle["detached_observer_signature_bytes"]
        )
        signature["observer_key_role"] = native.OWNER_STATE_KEY_ROLE
        material = {
            key: value
            for key, value in signature.items()
            if key not in {"signature_rs_base64", "artifact_sha256"}
        }
        signature["signature_rs_base64"] = base64.b64encode(
            self.observer.sign_low_s(material)
        ).decode("ascii")
        signature = _artifact(signature)
        bundle["detached_observer_signature_bytes"] = native.json_file_bytes(
            signature
        )
        with self.assertRaises(native.P0WindowsNativeObserverProfileContractError):
            self._validate(bundle)

    def test_public_api_has_no_path_private_key_signer_callback_or_authority_input(self) -> None:
        parameters = inspect.signature(
            native.validate_presented_windows_native_observer_profile_component
        ).parameters
        self.assertEqual(
            list(parameters),
            [
                "native_observer_profile",
                "request_bytes",
                "owner_state_ticket_bytes",
                "raw_receipt_body_bytes",
                "detached_observer_signature_bytes",
            ],
        )
        source = inspect.getsource(
            native.validate_presented_windows_native_observer_profile_component
        )
        for forbidden in ("private_key", "signer_callback", "expected_authority"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
