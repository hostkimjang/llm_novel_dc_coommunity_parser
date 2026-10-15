from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import inspect
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from llm_batch.grounding import p0_external_owner_asymmetric_signature as asymmetric
from llm_batch.grounding import p0_windows_bootstrap_policy_signature_candidate as bootstrap
from llm_batch.grounding import p0_windows_owner_policy_contract as policy
from llm_batch.grounding import p0_windows_cng_ecdsa_p256 as cng_p256
from tests import test_p0_windows_fixed_owner_policy_store_candidate as store_fixture
from tests import test_p0_windows_owner_policy_contract as contract_fixture
from tests.test_p0_external_owner_asymmetric_signature import _TestOnlyCngSigner


def _compiled_key_for_signer(
    signer: _TestOnlyCngSigner,
) -> bootstrap._CompiledBootstrapKeyCandidate:
    x64 = base64.b64encode(signer.x).decode("ascii")
    y64 = base64.b64encode(signer.y).decode("ascii")
    fingerprint = asymmetric.public_key_fingerprint_sha256(
        public_key_x_base64=x64,
        public_key_y_base64=y64,
    )
    return bootstrap._CompiledBootstrapKeyCandidate(
        key_id="controlled-bootstrap-key-001",
        public_key_x=signer.x,
        public_key_y=signer.y,
        public_key_fingerprint_sha256=fingerprint,
    )


def _signed_policy(
    signer: _TestOnlyCngSigner,
    *,
    key: bootstrap._CompiledBootstrapKeyCandidate | None = None,
    material_transform=None,
) -> tuple[bytes, bytes, dict[str, object], dict[str, object]]:
    key = key or _compiled_key_for_signer(signer)
    body = contract_fixture._body()
    body["bootstrap_key_id"] = key.key_id
    body["bootstrap_public_key_fingerprint_sha256"] = (
        key.public_key_fingerprint_sha256
    )
    store_fixture._rederive_body(body)
    signature = contract_fixture._signature(body)
    material = bootstrap.canonical_bytes(
        bootstrap._signature_material(signature)
    )
    if material_transform is not None:
        material = material_transform(material, signature)
    signature["signature_rs_base64"] = base64.b64encode(
        signer.sign_low_s(material)
    ).decode("ascii")
    contract_fixture._rehash(signature)
    return (
        policy.json_file_bytes(body),
        policy.json_file_bytes(signature),
        body,
        signature,
    )


@unittest.skipUnless(os.name == "nt", "Windows CNG bootstrap test")
class WindowsBootstrapPolicySignatureCandidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.signer = _TestOnlyCngSigner()
        self.addCleanup(self.signer.close)
        self.key = _compiled_key_for_signer(self.signer)

    def _verify(self, body_raw: bytes, signature_raw: bytes):
        with patch.object(
            bootstrap,
            "_compiled_bootstrap_key_candidate",
            return_value=self.key,
        ):
            return bootstrap.verify_presented_windows_owner_policy_bootstrap_signature_candidate(
                policy_body_bytes=body_raw,
                policy_signature_bytes=signature_raw,
            )

    def test_public_api_accepts_only_two_exact_byte_inputs_and_no_key_selector(self) -> None:
        signature = inspect.signature(
            bootstrap.verify_presented_windows_owner_policy_bootstrap_signature_candidate
        )
        self.assertEqual(
            list(signature.parameters),
            ["policy_body_bytes", "policy_signature_bytes"],
        )
        self.assertTrue(
            all(
                parameter.kind is inspect.Parameter.KEYWORD_ONLY
                for parameter in signature.parameters.values()
            )
        )
        forbidden = {"key", "path", "provider", "callback", "receipt", "state"}
        self.assertFalse(forbidden & set(signature.parameters))
        body_raw, signature_raw, _body, _signature = _signed_policy(
            self.signer, key=self.key
        )
        with self.assertRaises(TypeError):
            bootstrap.verify_presented_windows_owner_policy_bootstrap_signature_candidate(
                body_raw, signature_raw
            )

    def test_valid_exact_transcript_passes_math_but_never_authority(self) -> None:
        body_raw, signature_raw, _body, _signature = _signed_policy(
            self.signer, key=self.key
        )
        receipt = self._verify(body_raw, signature_raw)
        self.assertTrue(receipt["bootstrap_signature_mathematics_verified"])
        self.assertTrue(receipt["compiled_bootstrap_key_candidate_selected"])
        self.assertTrue(receipt["exact_policy_body_bytes_hash_bound_verified"])
        self.assertEqual(receipt["compiled_bootstrap_key_id"], self.key.key_id)
        self.assertEqual(
            receipt["compiled_bootstrap_key_candidate_provenance"],
            bootstrap.COMPILED_BOOTSTRAP_KEY_CANDIDATE_PROVENANCE,
        )
        self.assertNotEqual(
            self.key.public_key_fingerprint_sha256,
            bootstrap.COMPILED_BOOTSTRAP_PUBLIC_KEY_FINGERPRINT_SHA256,
        )
        for field in bootstrap._FALSE_FIELDS:
            self.assertFalse(receipt[field], field)
        material = dict(receipt)
        declared = material.pop("receipt_sha256")
        self.assertEqual(declared, bootstrap.canonical_sha256(material))

    def test_transcript_lf_and_double_sha_signatures_fail(self) -> None:
        transforms = (
            lambda material, _signature: material + b"\n",
            lambda material, _signature: hashlib.sha256(material).digest(),
        )
        for transform in transforms:
            with self.subTest(transform=transform):
                body_raw, signature_raw, _body, _signature = _signed_policy(
                    self.signer,
                    key=self.key,
                    material_transform=transform,
                )
                with self.assertRaisesRegex(
                    bootstrap.P0WindowsBootstrapPolicySignatureCandidateError,
                    "mathematics failed",
                ):
                    self._verify(body_raw, signature_raw)

    def test_exact_body_byte_change_with_valid_structure_breaks_signature(self) -> None:
        body_raw, _signature_raw, body, signature = _signed_policy(
            self.signer, key=self.key
        )
        body = deepcopy(body)
        operational = body["operational_key"]
        assert isinstance(operational, dict)
        operational["pin_bytes_sha256"] = "e" * 64
        store_fixture._rederive_body(body)
        body_raw = policy.json_file_bytes(body)
        signature["policy_body_bytes_sha256"] = hashlib.sha256(
            body_raw
        ).hexdigest()
        contract_fixture._rehash(signature)
        with self.assertRaisesRegex(
            bootstrap.P0WindowsBootstrapPolicySignatureCandidateError,
            "mathematics failed",
        ):
            self._verify(body_raw, policy.json_file_bytes(signature))

    def test_self_consistent_attacker_key_substitution_is_rejected(self) -> None:
        attacker = _TestOnlyCngSigner()
        self.addCleanup(attacker.close)
        attacker_key = _compiled_key_for_signer(attacker)
        body_raw, signature_raw, _body, _signature = _signed_policy(
            attacker, key=attacker_key
        )
        with self.assertRaisesRegex(
            bootstrap.P0WindowsBootstrapPolicySignatureCandidateError,
            "does not match compiled candidate",
        ):
            self._verify(body_raw, signature_raw)

    def test_compiled_coordinate_fingerprint_mismatch_fails_before_cng(self) -> None:
        with patch.object(
            bootstrap,
            "COMPILED_BOOTSTRAP_PUBLIC_KEY_FINGERPRINT_SHA256",
            "f" * 64,
        ):
            with self.assertRaisesRegex(
                bootstrap.P0WindowsBootstrapPolicySignatureCandidateError,
                "fingerprint constant mismatch",
            ):
                bootstrap._compiled_bootstrap_key_candidate()

    def test_structural_high_s_and_zero_scalar_never_reach_cng(self) -> None:
        body_raw, _signature_raw, _body, signature = _signed_policy(
            self.signer, key=self.key
        )
        for raw in (
            b"\0" * 64,
            (1).to_bytes(32, "big")
            + (policy._P256_ORDER - 1).to_bytes(32, "big"),
        ):
            with self.subTest(raw=raw[-2:]):
                changed = deepcopy(signature)
                changed["signature_rs_base64"] = base64.b64encode(raw).decode(
                    "ascii"
                )
                contract_fixture._rehash(changed)
                with self.assertRaisesRegex(
                    bootstrap.P0WindowsBootstrapPolicySignatureCandidateError,
                    "strict owner-policy contract",
                ):
                    self._verify(body_raw, policy.json_file_bytes(changed))

    def test_common_cng_cleanup_attempts_both_and_preserves_primary(self) -> None:
        calls: list[str] = []

        def destroy(_key):
            calls.append("destroy")
            raise OSError("destroy failure")

        def close(_provider, _flags):
            calls.append("close")
            return -1

        handle = SimpleNamespace(value=1)
        with self.assertRaises(cng_p256.P0WindowsCngEcdsaP256Error):
            cng_p256._cleanup_cng_handles(
                destroy_key=destroy,
                close_provider=close,
                key=handle,
                provider=handle,
                primary_error=None,
            )
        self.assertEqual(calls, ["destroy", "close"])
        calls.clear()
        cng_p256._cleanup_cng_handles(
            destroy_key=destroy,
            close_provider=close,
            key=handle,
            provider=handle,
            primary_error=RuntimeError("primary verification failure"),
        )
        self.assertEqual(calls, ["destroy", "close"])

    def test_cng_call_exception_is_normalized_and_bootstrap_never_leaks_it(self) -> None:
        class FakeFunction:
            def __init__(self, *, error: Exception | None = None):
                self.error = error

            def __call__(self, *_args):
                if self.error is not None:
                    raise self.error
                return 0

        fake_bcrypt = SimpleNamespace(
            BCryptOpenAlgorithmProvider=FakeFunction(
                error=OSError("simulated bcrypt call exception")
            ),
            BCryptImportKeyPair=FakeFunction(),
            BCryptVerifySignature=FakeFunction(),
            BCryptDestroyKey=FakeFunction(),
            BCryptCloseAlgorithmProvider=FakeFunction(),
        )
        with patch.object(cng_p256.ctypes, "WinDLL", return_value=fake_bcrypt):
            with self.assertRaisesRegex(
                cng_p256.P0WindowsCngEcdsaP256Error,
                "failed closed",
            ):
                cng_p256.verify_p256_sha256(
                    public_key_x=b"\x01" * 32,
                    public_key_y=b"\x02" * 32,
                    digest=b"\x03" * 32,
                    signature=b"\x04" * 64,
                )

        body_raw, signature_raw, _body, _signature = _signed_policy(
            self.signer, key=self.key
        )
        with patch.object(
            bootstrap.cng_p256,
            "verify_p256_sha256",
            side_effect=OSError("unexpected primitive leak"),
        ):
            with self.assertRaisesRegex(
                bootstrap.P0WindowsBootstrapPolicySignatureCandidateError,
                "failed closed",
            ):
                self._verify(body_raw, signature_raw)

    def test_production_compiled_public_key_imports_before_expected_mismatch(self) -> None:
        key = bootstrap._compiled_bootstrap_key_candidate()
        with self.assertRaisesRegex(
            cng_p256.P0WindowsCngEcdsaP256Error,
            "signature mismatch",
        ):
            cng_p256.verify_p256_sha256(
                public_key_x=key.public_key_x,
                public_key_y=key.public_key_y,
                digest=b"\x05" * 32,
                signature=b"\x01" * 64,
            )


class WindowsBootstrapPolicySignatureCandidatePlatformTests(unittest.TestCase):
    def test_non_windows_gate_precedes_policy_parsing_and_cng(self) -> None:
        with (
            patch.object(bootstrap.os, "name", "posix"),
            patch.object(
                bootstrap.policy,
                "validate_presented_windows_owner_policy_contract",
            ) as contract,
        ):
            with self.assertRaisesRegex(
                bootstrap.P0WindowsBootstrapPolicySignatureCandidateError,
                "Windows CNG",
            ):
                bootstrap.verify_presented_windows_owner_policy_bootstrap_signature_candidate(
                    policy_body_bytes=b"{}",
                    policy_signature_bytes=b"{}",
                )
            contract.assert_not_called()


if __name__ == "__main__":
    unittest.main()
