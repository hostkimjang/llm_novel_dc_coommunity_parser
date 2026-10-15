from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import ctypes
import gc
import hashlib
import inspect
import os
import struct
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from llm_batch.grounding import p0_external_owner_asymmetric_signature as asymmetric
from llm_batch.grounding import p0_external_owner_state_supervisor as owner_state
from tests.p0_actual_authority_supervisor_fixtures import (
    build_coordinated_actual_fixture,
)


_P256_ORDER = int(
    "ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551",
    16,
)


class _TestOnlyCngSigner:
    """Ephemeral test signer; production verification code has no signer API."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise unittest.SkipTest("Windows CNG is required")
        self._bcrypt = ctypes.WinDLL("bcrypt", use_last_error=True)
        self._handle = ctypes.c_void_p
        self._byte_pointer = ctypes.POINTER(ctypes.c_ubyte)
        self._ulong = ctypes.c_ulong
        self._ntstatus = ctypes.c_long
        self._provider = self._handle()
        self._key = self._handle()

        self._open = self._prototype(
            "BCryptOpenAlgorithmProvider",
            [
                ctypes.POINTER(self._handle),
                ctypes.c_wchar_p,
                ctypes.c_wchar_p,
                self._ulong,
            ],
        )
        self._generate = self._prototype(
            "BCryptGenerateKeyPair",
            [self._handle, ctypes.POINTER(self._handle), self._ulong, self._ulong],
        )
        self._finalize = self._prototype(
            "BCryptFinalizeKeyPair", [self._handle, self._ulong]
        )
        self._export = self._prototype(
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
        self._sign = self._prototype(
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
        self._destroy = self._prototype("BCryptDestroyKey", [self._handle])
        self._close = self._prototype(
            "BCryptCloseAlgorithmProvider", [self._handle, self._ulong]
        )
        self._ok(self._open(ctypes.byref(self._provider), "ECDSA_P256", None, 0))
        self._ok(self._generate(self._provider, ctypes.byref(self._key), 256, 0))
        self._ok(self._finalize(self._key, 0))
        self.public_blob = self._export_public_blob()
        self.x = self.public_blob[8:40]
        self.y = self.public_blob[40:72]

    def _prototype(self, name: str, args: list[object]):
        function = getattr(self._bcrypt, name)
        function.argtypes = args
        function.restype = self._ntstatus
        return function

    @staticmethod
    def _ok(status: int) -> None:
        if status != 0:
            raise RuntimeError(f"test-only CNG operation failed: 0x{status & 0xffffffff:08x}")

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

    def sign_low_s(self, material: bytes) -> bytes:
        digest = hashlib.sha256(material).digest()
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
        if len(signature) != 64:
            raise RuntimeError("unexpected CNG ECDSA signature length")
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


def _rehash(value: dict[str, object]) -> dict[str, object]:
    material = deepcopy(value)
    material.pop("artifact_sha256", None)
    return {**material, "artifact_sha256": asymmetric.canonical_sha256(material)}


@unittest.skipUnless(os.name == "nt", "Windows CNG is required")
class ExternalOwnerAsymmetricSignatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.signer = _TestOnlyCngSigner()
        self.addCleanup(self.signer.close)
        fixture = build_coordinated_actual_fixture()
        self.preauthorization = deepcopy(fixture.preauthorization)
        self.preauthorization_bytes = asymmetric.json_file_bytes(self.preauthorization)
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
        self.envelope = self._signed_envelope(self.pin)

    def _signed_envelope(
        self,
        pin: dict[str, object],
        *,
        signer: _TestOnlyCngSigner | None = None,
        preauthorization_bytes: bytes | None = None,
        changes: dict[str, object] | None = None,
    ) -> dict[str, object]:
        raw = preauthorization_bytes or self.preauthorization_bytes
        preauthorization = json_load(raw)
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
            "preauthorization_schema": self.preauthorization["schema_version"],
            "preauthorization_bytes_sha256": hashlib.sha256(raw).hexdigest(),
            "preauthorization_artifact_sha256": preauthorization[
                "artifact_sha256"
            ],
            "signature_rs_base64": base64.b64encode(b"\0" * 64).decode("ascii"),
            "artifact_sha256": "0" * 64,
        }
        if changes:
            envelope.update(changes)
        material = asymmetric.external_owner_signature_material(envelope)
        signature = (signer or self.signer).sign_low_s(
            asymmetric.canonical_bytes(material)
        )
        envelope["signature_rs_base64"] = base64.b64encode(signature).decode(
            "ascii"
        )
        return _rehash(envelope)

    def _validate(
        self,
        *,
        pin: dict[str, object] | None = None,
        envelope: dict[str, object] | None = None,
        preauthorization_bytes: bytes | None = None,
    ) -> dict[str, object]:
        return asymmetric.validate_presented_external_owner_asymmetric_signature(
            public_key_pin_bytes=asymmetric.json_file_bytes(pin or self.pin),
            signature_envelope_bytes=asymmetric.json_file_bytes(
                envelope or self.envelope
            ),
            owner_root_preauthorization_bytes=(
                preauthorization_bytes or self.preauthorization_bytes
            ),
        )

    def _raw_triplet(self) -> dict[str, bytes]:
        return {
            "public_key_pin_bytes": asymmetric.json_file_bytes(self.pin),
            "signature_envelope_bytes": asymmetric.json_file_bytes(self.envelope),
            "owner_root_preauthorization_bytes": self.preauthorization_bytes,
        }

    def _issue_owner_state(self):
        return (
            asymmetric._validate_presented_external_owner_asymmetric_signature_state(
                **self._raw_triplet()
            )
        )

    @staticmethod
    def _owner_state_context(receipt) -> dict[str, object]:
        return {
            field: receipt[field]
            for field in asymmetric._OWNER_STATE_CONTEXT_FIELDS
        }

    def _consume_owner_state(self, state, **changes):
        raw = self._raw_triplet()
        if "expected_context" in changes:
            expected_context = changes.pop("expected_context")
        else:
            expected_context = self._owner_state_context(state.public_receipt)
        raw.update(changes)
        return asymmetric._consume_external_owner_asymmetric_signature_state(
            state,
            **raw,
            expected_context=expected_context,
        )

    def test_valid_cng_signature_is_component_only(self) -> None:
        receipt = self._validate()
        for field in (
            "presented_public_key_pin_verified",
            "public_key_fingerprint_recomputed_verified",
            "cng_public_key_import_verified",
            "canonical_low_s_signature_verified",
            "asymmetric_signature_math_verified",
            "exact_preauthorization_bytes_bound_verified",
            "public_api_private_key_parameter_absent",
            "fresh_execution_result_observed",
        ):
            self.assertIs(receipt[field], True, field)
        for field in (
            "external_public_key_pin_provisioning_verified",
            "independent_readonly_public_key_pin_verified",
            "public_key_pin_rollback_protection_verified",
            "key_epoch_monotonicity_verified",
            "independent_context_policy_verified",
            "signature_freshness_verified",
            "external_owner_signing_key_verified",
            "private_key_outside_verifier_verified",
            "trusted_cng_provider_provenance_verified",
            "trusted_time_verified",
            "revocation_current_verified",
            "revocation_rollback_protection_verified",
            "durable_cross_process_nonce_verified",
            "power_loss_durable_replay_verified",
            "single_use_replay_consumed",
            "external_trust_store_verified",
            "external_owner_trust_verified",
            "external_root_identity_pin_verified",
            "filesystem_handle_trust_verified",
            "runtime_noninterference_verified",
            "os_write_deny_verified",
            "parser_runtime_execution_verified",
            "actual_semantic_evidence_verified",
            "serialized_receipt_authoritative",
            "execution_trace_transferable_by_receipt",
            "owner_authority_verified",
            "actual_authority_granted",
            "p0_phase_exit",
            "production_approval",
            "full_scan_approval",
            "action_applied",
            "protected_pipeline_state_mutated",
        ):
            self.assertIs(receipt[field], False, field)
        self.assertEqual(receipt["gate_status"], asymmetric.GATE_STATUS)
        self.assertEqual(receipt["cng_provider_name"], asymmetric.CNG_PROVIDER)
        self.assertEqual(receipt["credited_actual_source_claim_count"], 0)
        self.assertEqual(receipt["credited_actual_a_context_review_count"], 0)
        material = dict(receipt)
        declared = material.pop("receipt_sha256")
        self.assertEqual(declared, asymmetric.canonical_sha256(material))

    def test_public_api_has_no_private_key_signer_callback_or_provider(self) -> None:
        parameters = inspect.signature(
            asymmetric.validate_presented_external_owner_asymmetric_signature
        ).parameters
        self.assertEqual(
            set(parameters),
            {
                "public_key_pin_bytes",
                "signature_envelope_bytes",
                "owner_root_preauthorization_bytes",
            },
        )
        source = inspect.getsource(asymmetric)
        for forbidden in (
            "BCryptGenerateKeyPair",
            "BCryptSignHash",
            "NCryptOpenKey",
            "ECCPRIVATEBLOB",
        ):
            self.assertNotIn(forbidden, source)

    def test_signature_bit_tamper_is_rejected(self) -> None:
        envelope = deepcopy(self.envelope)
        signature = bytearray(base64.b64decode(envelope["signature_rs_base64"]))
        signature[0] ^= 1
        envelope["signature_rs_base64"] = base64.b64encode(signature).decode("ascii")
        envelope = _rehash(envelope)
        with self.assertRaisesRegex(
            asymmetric.P0ExternalOwnerAsymmetricSignatureError,
            "signature mismatch",
        ):
            self._validate(envelope=envelope)

    def test_high_s_and_zero_scalar_are_rejected_before_cng(self) -> None:
        for signature in (
            b"\0" * 32 + (1).to_bytes(32, "big"),
            (1).to_bytes(32, "big") + (_P256_ORDER - 1).to_bytes(32, "big"),
            _P256_ORDER.to_bytes(32, "big") + (1).to_bytes(32, "big"),
            (1).to_bytes(32, "big") + _P256_ORDER.to_bytes(32, "big"),
        ):
            with self.subTest(signature=signature.hex()[:8]):
                envelope = deepcopy(self.envelope)
                envelope["signature_rs_base64"] = base64.b64encode(signature).decode(
                    "ascii"
                )
                envelope = _rehash(envelope)
                with self.assertRaisesRegex(
                    asymmetric.P0ExternalOwnerAsymmetricSignatureError,
                    "canonical nonzero low-S",
                ):
                    self._validate(envelope=envelope)

    def test_exact_preauthorization_bytes_swap_is_rejected(self) -> None:
        changed = deepcopy(self.preauthorization)
        changed["nonce"] = "different-still-structural-nonce"
        changed = _rehash(changed)
        with self.assertRaisesRegex(
            asymmetric.P0ExternalOwnerAsymmetricSignatureError,
            "preauthorization (?:bytes|nonce commitment)",
        ):
            self._validate(
                preauthorization_bytes=asymmetric.json_file_bytes(changed)
            )

    def test_project_run_and_preauthorization_id_relabel_are_rejected(self) -> None:
        cases = (
            {"project_id": "attacker-project"},
            {"run_id": "attacker-run"},
            {"preauthorization_id": "attacker-preauth"},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                envelope = self._signed_envelope(self.pin, changes=changes)
                with self.assertRaisesRegex(
                    asymmetric.P0ExternalOwnerAsymmetricSignatureError,
                    "binding mismatch",
                ):
                    self._validate(envelope=envelope)

    def test_algorithm_domain_and_hmac_downgrade_are_rejected(self) -> None:
        for changes in (
            {"algorithm": "HMAC-SHA256"},
            {"domain": "p0-owner-generic-signature"},
            {"schema_version": "p0_external_owner_trust_anchor_v1"},
        ):
            with self.subTest(changes=changes):
                envelope = self._signed_envelope(self.pin, changes=changes)
                with self.assertRaisesRegex(
                    asymmetric.P0ExternalOwnerAsymmetricSignatureError,
                    "schema/domain/algorithm mismatch",
                ):
                    self._validate(envelope=envelope)

    def test_public_coordinate_substitution_fails_even_when_rehashed(self) -> None:
        pin = deepcopy(self.pin)
        x = bytearray(base64.b64decode(pin["public_key_x_base64"]))
        x[-1] ^= 1
        pin["public_key_x_base64"] = base64.b64encode(x).decode("ascii")
        pin["public_key_fingerprint_sha256"] = (
            asymmetric.public_key_fingerprint_sha256(
                public_key_x_base64=pin["public_key_x_base64"],
                public_key_y_base64=pin["public_key_y_base64"],
            )
        )
        pin = _rehash(pin)
        envelope = self._signed_envelope(pin)
        with self.assertRaises(asymmetric.P0ExternalOwnerAsymmetricSignatureError):
            self._validate(pin=pin, envelope=envelope)

    def test_complete_attacker_key_substitution_stays_presented_only(self) -> None:
        attacker = _TestOnlyCngSigner()
        self.addCleanup(attacker.close)
        attacker_preauthorization = deepcopy(self.preauthorization)
        attacker_preauthorization["project_id"] = "attacker-project"
        attacker_preauthorization["run_id"] = "attacker-run"
        attacker_preauthorization["parser_run_id"] = "attacker-parser-run"
        attacker_preauthorization["preauthorization_id"] = "attacker-preauth"
        attacker_preauthorization["owner_principal_sha256"] = "a" * 64
        attacker_preauthorization["owner_anchor_sha256"] = "b" * 64
        attacker_preauthorization["launch_sha256"] = "c" * 64
        attacker_preauthorization["owner_authorization_sha256"] = "d" * 64
        attacker_preauthorization["allowed_packet_root"][
            "file_id_128_hex"
        ] = "e" * 32
        attacker_preauthorization["nonce"] = "attacker-reissued-nonce"
        attacker_preauthorization = _rehash(attacker_preauthorization)
        attacker_raw = asymmetric.json_file_bytes(attacker_preauthorization)
        pin = deepcopy(self.pin)
        pin["project_id"] = "attacker-project"
        pin["key_id"] = "attacker-presented-key"
        pin["owner_principal_sha256"] = "a" * 64
        pin["owner_anchor_sha256"] = "b" * 64
        pin["public_key_x_base64"] = base64.b64encode(attacker.x).decode("ascii")
        pin["public_key_y_base64"] = base64.b64encode(attacker.y).decode("ascii")
        pin["public_key_fingerprint_sha256"] = (
            asymmetric.public_key_fingerprint_sha256(
                public_key_x_base64=pin["public_key_x_base64"],
                public_key_y_base64=pin["public_key_y_base64"],
            )
        )
        pin = _rehash(pin)
        envelope = self._signed_envelope(
            pin, signer=attacker, preauthorization_bytes=attacker_raw
        )
        receipt = self._validate(
            pin=pin,
            envelope=envelope,
            preauthorization_bytes=attacker_raw,
        )
        self.assertTrue(receipt["asymmetric_signature_math_verified"])
        self.assertFalse(receipt["external_public_key_pin_provisioning_verified"])
        self.assertFalse(receipt["external_owner_trust_verified"])
        self.assertFalse(receipt["actual_authority_granted"])

    def test_pin_envelope_context_substitution_is_rejected(self) -> None:
        cases = (
            ("trust_domain", "attacker-trust-domain"),
            ("environment", "attacker-environment"),
            ("purpose", "ATTACKER_PURPOSE"),
            ("key_id", "attacker-key-id"),
            ("owner_principal_sha256", "c" * 64),
            ("owner_anchor_sha256", "d" * 64),
        )
        for field, value in cases:
            with self.subTest(field=field):
                pin = deepcopy(self.pin)
                pin[field] = value
                pin = _rehash(pin)
                with self.assertRaises(
                    asymmetric.P0ExternalOwnerAsymmetricSignatureError
                ):
                    self._validate(pin=pin)

    def test_preauthorization_self_hash_and_exact_framing_are_rejected(self) -> None:
        changed = deepcopy(self.preauthorization)
        changed["artifact_sha256"] = "e" * 64
        with self.assertRaisesRegex(
            asymmetric.P0ExternalOwnerAsymmetricSignatureError,
            "structure is invalid",
        ):
            self._validate(
                preauthorization_bytes=asymmetric.json_file_bytes(changed)
            )

        duplicate = self.preauthorization_bytes.replace(
            b'"schema_version":',
            b'"schema_version":"duplicate","schema_version":',
            1,
        )
        with self.assertRaisesRegex(
            asymmetric.P0ExternalOwnerAsymmetricSignatureError,
            "duplicate JSON key",
        ):
            self._validate(preauthorization_bytes=duplicate)

    def test_fingerprint_self_hash_and_context_mismatch_are_rejected(self) -> None:
        pin = deepcopy(self.pin)
        pin["public_key_fingerprint_sha256"] = "f" * 64
        pin = _rehash(pin)
        with self.assertRaisesRegex(
            asymmetric.P0ExternalOwnerAsymmetricSignatureError,
            "fingerprint mismatch",
        ):
            self._validate(pin=pin)

        pin = deepcopy(self.pin)
        pin["key_epoch"] = 2
        pin = _rehash(pin)
        with self.assertRaisesRegex(
            asymmetric.P0ExternalOwnerAsymmetricSignatureError,
            "key_epoch",
        ):
            self._validate(pin=pin)

    def test_noncanonical_json_and_base64_are_rejected(self) -> None:
        canonical = asymmetric.json_file_bytes(self.pin)
        malformed = (
            b"\xef\xbb\xbf" + canonical,
            canonical.replace(b"\n", b"\r\n"),
            canonical[:-1],
            canonical.replace(b'"schema_version":', b'"schema_version":"duplicate","schema_version":', 1),
        )
        for raw in malformed:
            with self.subTest(raw=raw[:10]):
                with self.assertRaises(asymmetric.P0ExternalOwnerAsymmetricSignatureError):
                    asymmetric.validate_presented_external_owner_asymmetric_signature(
                        public_key_pin_bytes=raw,
                        signature_envelope_bytes=asymmetric.json_file_bytes(
                            self.envelope
                        ),
                        owner_root_preauthorization_bytes=self.preauthorization_bytes,
                    )

        pin = deepcopy(self.pin)
        pin["public_key_x_base64"] = pin["public_key_x_base64"] + "="
        pin = _rehash(pin)
        with self.assertRaisesRegex(
            asymmetric.P0ExternalOwnerAsymmetricSignatureError,
            "canonical base64|encode exactly",
        ):
            self._validate(pin=pin)

    def test_rfc5480_spki_fingerprint_has_independent_known_vector(self) -> None:
        x = bytes.fromhex(
            "6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296"
        )
        y = bytes.fromhex(
            "4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5"
        )
        self.assertEqual(
            asymmetric.public_key_fingerprint_sha256(
                public_key_x_base64=base64.b64encode(x).decode("ascii"),
                public_key_y_base64=base64.b64encode(y).decode("ascii"),
            ),
            "5cd252fb0ce8932436faf8ccd1040981b89ee4ad6b9fe9e2a2b7e71aacb27cd3",
        )

    def test_nonbytes_and_oversized_inputs_fail_with_contract_error(self) -> None:
        kwargs = {
            "public_key_pin_bytes": asymmetric.json_file_bytes(self.pin),
            "signature_envelope_bytes": asymmetric.json_file_bytes(self.envelope),
            "owner_root_preauthorization_bytes": self.preauthorization_bytes,
        }
        for field in tuple(kwargs):
            with self.subTest(field=field, kind="nonbytes"):
                changed = dict(kwargs)
                changed[field] = None
                with self.assertRaises(
                    asymmetric.P0ExternalOwnerAsymmetricSignatureError
                ):
                    asymmetric.validate_presented_external_owner_asymmetric_signature(
                        **changed
                    )
            with self.subTest(field=field, kind="oversized"):
                changed = dict(kwargs)
                changed[field] = b"{" + b"x" * (1024 * 1024) + b"}\n"
                with self.assertRaises(
                    asymmetric.P0ExternalOwnerAsymmetricSignatureError
                ):
                    asymmetric.validate_presented_external_owner_asymmetric_signature(
                        **changed
                    )

    def test_owner_state_is_minted_only_after_fresh_raw_validation(self) -> None:
        baseline = len(asymmetric._ISSUED_OWNER_STATES)
        raw = self._raw_triplet()
        self._validate()
        self.assertEqual(len(asymmetric._ISSUED_OWNER_STATES), baseline)
        with patch.object(
            asymmetric,
            "_validate_presented_external_owner_asymmetric_signature_core",
            wraps=(
                asymmetric._validate_presented_external_owner_asymmetric_signature_core
            ),
        ) as validator:
            state = (
                asymmetric._validate_presented_external_owner_asymmetric_signature_state(
                    **raw
                )
            )
        self.addCleanup(
            asymmetric._discard_external_owner_asymmetric_signature_state,
            state,
        )
        validator.assert_called_once_with(**raw)
        self.assertIs(type(state), asymmetric._ExternalOwnerAsymmetricSignatureState)
        self.assertEqual(len(asymmetric._ISSUED_OWNER_STATES), baseline + 1)

        asymmetric._discard_external_owner_asymmetric_signature_state(state)
        self.assertEqual(len(asymmetric._ISSUED_OWNER_STATES), baseline)
        changed = dict(raw)
        changed["signature_envelope_bytes"] = (
            changed["signature_envelope_bytes"][:-2] + b"x\n"
        )
        with self.assertRaises(
            asymmetric.P0ExternalOwnerAsymmetricSignatureError
        ):
            asymmetric._validate_presented_external_owner_asymmetric_signature_state(
                **changed
            )
        self.assertEqual(len(asymmetric._ISSUED_OWNER_STATES), baseline)

    def test_owner_state_cross_binds_raw_receipt_context_and_consumes_once(self) -> None:
        baseline = len(asymmetric._ISSUED_OWNER_STATES)
        state = self._issue_owner_state()
        consumed = self._consume_owner_state(state)
        raw = self._raw_triplet()
        self.assertEqual(consumed.public_key_pin_bytes, raw["public_key_pin_bytes"])
        self.assertEqual(
            consumed.signature_envelope_bytes,
            raw["signature_envelope_bytes"],
        )
        self.assertEqual(
            consumed.owner_root_preauthorization_bytes,
            raw["owner_root_preauthorization_bytes"],
        )
        self.assertEqual(
            dict(consumed.public_receipt),
            dict(state.public_receipt),
        )
        self.assertEqual(len(asymmetric._ISSUED_OWNER_STATES), baseline)
        with self.assertRaisesRegex(
            asymmetric.P0ExternalOwnerAsymmetricSignatureError,
            "already consumed",
        ):
            self._consume_owner_state(state)

    def test_owner_state_clone_namespace_and_public_receipt_do_not_burn_real(self) -> None:
        state = self._issue_owner_state()
        self.addCleanup(
            asymmetric._discard_external_owner_asymmetric_signature_state,
            state,
        )
        clone = asymmetric._ExternalOwnerAsymmetricSignatureState(
            state.public_receipt,
            state._execution_seal,
        )
        fakes = (
            clone,
            SimpleNamespace(
                public_receipt=state.public_receipt,
                _execution_seal=state._execution_seal,
            ),
            dict(state.public_receipt),
            asymmetric.canonical_bytes(dict(state.public_receipt)),
        )
        expected = self._owner_state_context(state.public_receipt)
        for fake in fakes:
            with self.subTest(fake=type(fake).__name__):
                with self.assertRaises(
                    asymmetric.P0ExternalOwnerAsymmetricSignatureError
                ):
                    self._consume_owner_state(fake, expected_context=expected)
        consumed = self._consume_owner_state(state)
        self.assertEqual(
            consumed.public_receipt["receipt_sha256"],
            state.public_receipt["receipt_sha256"],
        )

    def test_owner_state_raw_tamper_or_role_swap_burns_genuine_state(self) -> None:
        raw = self._raw_triplet()
        cases = (
            {
                "public_key_pin_bytes": raw["public_key_pin_bytes"][:-2]
                + b"x\n"
            },
            {
                "signature_envelope_bytes": raw[
                    "signature_envelope_bytes"
                ][:-2]
                + b"x\n"
            },
            {
                "owner_root_preauthorization_bytes": raw[
                    "owner_root_preauthorization_bytes"
                ][:-2]
                + b"x\n"
            },
            {
                "public_key_pin_bytes": raw["signature_envelope_bytes"],
                "signature_envelope_bytes": raw["public_key_pin_bytes"],
            },
        )
        for changes in cases:
            with self.subTest(changes=tuple(changes)):
                state = self._issue_owner_state()
                with self.assertRaisesRegex(
                    asymmetric.P0ExternalOwnerAsymmetricSignatureError,
                    "binding mismatch",
                ):
                    self._consume_owner_state(state, **changes)
                with self.assertRaisesRegex(
                    asymmetric.P0ExternalOwnerAsymmetricSignatureError,
                    "already consumed",
                ):
                    self._consume_owner_state(state)

    def test_owner_state_context_relabel_and_malformed_context_burn_state(self) -> None:
        changes = (
            ("project_id", "attacker-project"),
            ("session_id", "attacker-session"),
            ("run_id", "attacker-run"),
            ("parser_run_id", "attacker-parser-run"),
            ("nonce_commitment_sha256", "a" * 64),
            ("launch_sha256", "b" * 64),
            ("key_epoch", 2),
            ("public_key_fingerprint_sha256", "c" * 64),
            ("owner_anchor_sha256", "d" * 64),
            ("packet_root_projection_sha256", "e" * 64),
            ("expected_provenance_sha256", "f" * 64),
        )
        for field, value in changes:
            with self.subTest(field=field):
                state = self._issue_owner_state()
                expected = self._owner_state_context(state.public_receipt)
                expected[field] = value
                with self.assertRaisesRegex(
                    asymmetric.P0ExternalOwnerAsymmetricSignatureError,
                    "binding mismatch",
                ):
                    self._consume_owner_state(
                        state,
                        expected_context=expected,
                    )
                with self.assertRaisesRegex(
                    asymmetric.P0ExternalOwnerAsymmetricSignatureError,
                    "already consumed",
                ):
                    self._consume_owner_state(state)

        state = self._issue_owner_state()
        with self.assertRaisesRegex(
            asymmetric.P0ExternalOwnerAsymmetricSignatureError,
            "exact fixed fields",
        ):
            self._consume_owner_state(state, expected_context={})
        with self.assertRaisesRegex(
            asymmetric.P0ExternalOwnerAsymmetricSignatureError,
            "already consumed",
        ):
            self._consume_owner_state(state)

    def test_owner_state_is_frozen_and_forced_seal_tamper_burns(self) -> None:
        state = self._issue_owner_state()
        with self.assertRaises(AttributeError):
            state.public_receipt = {}  # type: ignore[misc]
        with self.assertRaises(TypeError):
            state.public_receipt["project_id"] = "attacker"  # type: ignore[index]
        object.__setattr__(state, "_execution_seal", b"z" * 32)
        with self.assertRaisesRegex(
            asymmetric.P0ExternalOwnerAsymmetricSignatureError,
            "binding mismatch",
        ):
            self._consume_owner_state(state)
        with self.assertRaisesRegex(
            asymmetric.P0ExternalOwnerAsymmetricSignatureError,
            "already consumed",
        ):
            self._consume_owner_state(state)

        state = self._issue_owner_state()
        expected = self._owner_state_context(state.public_receipt)
        tampered = dict(state.public_receipt)
        tampered["project_id"] = "attacker-project"
        material = dict(tampered)
        material.pop("receipt_sha256")
        tampered["receipt_sha256"] = asymmetric.canonical_sha256(material)
        object.__setattr__(state, "public_receipt", tampered)
        with self.assertRaisesRegex(
            asymmetric.P0ExternalOwnerAsymmetricSignatureError,
            "binding mismatch",
        ):
            self._consume_owner_state(state, expected_context=expected)
        with self.assertRaisesRegex(
            asymmetric.P0ExternalOwnerAsymmetricSignatureError,
            "already consumed",
        ):
            self._consume_owner_state(state, expected_context=expected)

    def test_owner_state_discard_is_identity_scoped_and_idempotent(self) -> None:
        baseline = len(asymmetric._ISSUED_OWNER_STATES)
        state = self._issue_owner_state()
        clone = asymmetric._ExternalOwnerAsymmetricSignatureState(
            state.public_receipt,
            state._execution_seal,
        )
        asymmetric._discard_external_owner_asymmetric_signature_state(clone)
        self._consume_owner_state(state)
        self.assertEqual(len(asymmetric._ISSUED_OWNER_STATES), baseline)

        state = self._issue_owner_state()
        asymmetric._discard_external_owner_asymmetric_signature_state(state)
        asymmetric._discard_external_owner_asymmetric_signature_state(state)
        with self.assertRaisesRegex(
            asymmetric.P0ExternalOwnerAsymmetricSignatureError,
            "already consumed",
        ):
            self._consume_owner_state(state)
        self.assertEqual(len(asymmetric._ISSUED_OWNER_STATES), baseline)

    def test_owner_state_sixteen_way_race_has_exactly_one_consumer(self) -> None:
        state = self._issue_owner_state()
        barrier = threading.Barrier(16)

        def consume() -> str:
            barrier.wait()
            try:
                self._consume_owner_state(state)
            except asymmetric.P0ExternalOwnerAsymmetricSignatureError as exc:
                return str(exc)
            return "success"

        with ThreadPoolExecutor(max_workers=16) as executor:
            results = list(executor.map(lambda _: consume(), range(16)))
        self.assertEqual(results.count("success"), 1)
        self.assertEqual(
            sum("already consumed" in result for result in results),
            15,
        )

    def test_owner_state_gc_finalizer_and_pid_mismatch_burn_buffers(self) -> None:
        baseline = len(asymmetric._ISSUED_OWNER_STATES)
        state = self._issue_owner_state()
        record = asymmetric._ISSUED_OWNER_STATES[id(state)]
        buffers = (
            record.secret.execution_seal,
            record.secret.public_key_pin_bytes,
            record.secret.signature_envelope_bytes,
            record.secret.owner_root_preauthorization_bytes,
        )
        del state
        gc.collect()
        self.assertEqual(len(asymmetric._ISSUED_OWNER_STATES), baseline)
        self.assertTrue(all(not any(buffer) for buffer in buffers))

        state = self._issue_owner_state()
        record = asymmetric._ISSUED_OWNER_STATES[id(state)]
        record.secret.issuer_pid += 1
        with self.assertRaisesRegex(
            asymmetric.P0ExternalOwnerAsymmetricSignatureError,
            "binding mismatch",
        ):
            self._consume_owner_state(state)
        self.assertTrue(
            all(
                not any(buffer)
                for buffer in (
                    record.secret.execution_seal,
                    record.secret.public_key_pin_bytes,
                    record.secret.signature_envelope_bytes,
                    record.secret.owner_root_preauthorization_bytes,
                )
            )
        )

    def test_public_owner_state_supervisor_consumes_raw3_without_receipt_input(self) -> None:
        raw = self._raw_triplet()
        diagnostic = self._validate()
        expected = self._owner_state_context(diagnostic)
        receipt = owner_state.execute_presented_external_owner_state_supervisor(
            **raw,
            expected_context=expected,
        )
        for field in (
            "asymmetric_signature_math_verified",
            "exact_preauthorization_bytes_bound_verified",
            "fresh_raw_triplet_validation_observed",
            "module_issued_owner_state_consumed_once",
            "same_call_raw_triplet_verified",
            "exact_object_identity_registry_verified",
            "public_receipt_input_absent",
            "process_local_cooperative_handoff_only",
        ):
            self.assertIs(receipt[field], True, field)
        for field in (
            "serialized_receipt_consumed",
            "serialized_receipt_authoritative",
            "execution_trace_transferable_by_receipt",
            "signature_artifact_replay_prevented",
            "arbitrary_in_process_code_resistance_verified",
            "secure_memory_erasure_verified",
            "external_public_key_pin_provisioning_verified",
            "independent_context_policy_verified",
            "signature_freshness_verified",
            "trusted_time_verified",
            "revocation_current_verified",
            "durable_cross_process_nonce_verified",
            "single_use_replay_consumed",
            "external_owner_trust_verified",
            "runtime_noninterference_verified",
            "owner_authority_verified",
            "actual_authority_granted",
            "p0_phase_exit",
            "production_approval",
            "full_scan_approval",
            "action_applied",
            "protected_pipeline_state_mutated",
        ):
            self.assertIs(receipt[field], False, field)
        material = dict(receipt)
        declared = material.pop("receipt_sha256")
        self.assertEqual(declared, asymmetric.canonical_sha256(material))
        self.assertEqual(receipt["gate_status"], owner_state.GATE_STATUS)
        self.assertEqual(receipt["credited_actual_source_claim_count"], 0)
        self.assertEqual(receipt["credited_actual_a_context_review_count"], 0)

        parameters = inspect.signature(
            owner_state.execute_presented_external_owner_state_supervisor
        ).parameters
        self.assertEqual(
            set(parameters),
            {
                "public_key_pin_bytes",
                "signature_envelope_bytes",
                "owner_root_preauthorization_bytes",
                "expected_context",
            },
        )
        for private_name in (
            "_ExternalOwnerAsymmetricSignatureState",
            "_validate_presented_external_owner_asymmetric_signature_state",
            "_consume_external_owner_asymmetric_signature_state",
            "_discard_external_owner_asymmetric_signature_state",
        ):
            self.assertNotIn(private_name, asymmetric.__all__)


def json_load(raw: bytes) -> dict[str, object]:
    import json

    value = json.loads(raw)
    assert isinstance(value, dict)
    return value


if __name__ == "__main__":
    unittest.main()
