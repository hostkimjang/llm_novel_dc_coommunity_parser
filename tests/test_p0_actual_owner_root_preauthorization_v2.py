from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import inspect
import json
import unittest
from unittest.mock import patch

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils

from llm_batch.grounding import p0_actual_owner_root_preauthorization as v1
from llm_batch.grounding import p0_actual_owner_root_preauthorization_v2 as candidate
from llm_batch.grounding import p0_windows_cng_ecdsa_p256 as cng


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def file_bytes(value: object) -> bytes:
    return canonical(value) + b"\n"


def reseal(value: dict[str, object]) -> dict[str, object]:
    result = dict(value)
    result.pop("artifact_sha256", None)
    result["artifact_sha256"] = digest(result)
    return result


def receipt_reseal(value: dict[str, object]) -> dict[str, object]:
    result = dict(value)
    result.pop("receipt_sha256", None)
    result["receipt_sha256"] = digest(result)
    return result


class OwnerRootPreauthorizationV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.private_key = ec.generate_private_key(ec.SECP256R1())
        self.packet_dir = r"C:\presented-packet-v2"
        self.observed_at = "2026-09-03T01:30:00Z"
        self.pin, self.body, self.envelope = self._bundle(self.private_key)
        self.windows_receipt = self._windows_receipt(self.body)

    def _bundle(
        self, private_key: ec.EllipticCurvePrivateKey,
        *, body_changes: dict[str, object] | None = None,
        member_change: tuple[int, str, object] | None = None,
        pin_changes: dict[str, object] | None = None,
        envelope_changes: dict[str, object] | None = None,
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        public = private_key.public_key().public_numbers()
        x = public.x.to_bytes(32, "big")
        y = public.y.to_bytes(32, "big")
        fingerprint = hashlib.sha256(candidate._P256_SPKI_PREFIX + x + y).hexdigest()
        owner_principal = "11" * 32
        pin: dict[str, object] = {
            "schema_version": candidate.PUBLIC_KEY_PIN_SCHEMA,
            "record_origin": candidate.PIN_ORIGIN,
            "trust_domain": "owner.example",
            "project_id": "project-v2",
            "environment": "test",
            "purpose": candidate.PURPOSE,
            "key_id": "owner-key-v2",
            "key_epoch": 7,
            "algorithm": candidate.ALGORITHM,
            "curve": candidate.CURVE,
            "coordinate_encoding": candidate.COORDINATE_ENCODING,
            "fingerprint_encoding": candidate.FINGERPRINT_ENCODING,
            "public_key_x_base64": base64.b64encode(x).decode("ascii"),
            "public_key_y_base64": base64.b64encode(y).decode("ascii"),
            "public_key_fingerprint_sha256": fingerprint,
            "owner_principal_sha256": owner_principal,
            "owner_anchor_sha256": "00" * 32,
            "allowed_signature_domains": [candidate.SIGNATURE_DOMAIN],
        }
        pin["owner_anchor_sha256"] = digest({
            "domain": candidate.OWNER_ANCHOR_DOMAIN,
            "trust_domain": pin["trust_domain"],
            "project_id": pin["project_id"],
            "environment": pin["environment"],
            "owner_principal_sha256": owner_principal,
        })
        if pin_changes:
            pin.update(pin_changes)
        pin = reseal(pin)

        members: list[dict[str, object]] = []
        for ordinal, (role, path, media, cap) in enumerate(candidate._FIXED_MEMBER_CONTRACT):
            members.append({
                "ordinal": ordinal, "role": role, "path": path,
                "media_type": media, "max_bytes": cap,
                "raw_sha256": hashlib.sha256(f"raw:{role}".encode()).hexdigest(),
            })
        if member_change:
            index, field, value = member_change
            members[index][field] = value
        body: dict[str, object] = {
            "schema_version": candidate.PREAUTHORIZATION_SCHEMA,
            "record_origin": candidate.PREAUTHORIZATION_ORIGIN,
            "domain": candidate.PREAUTHORIZATION_DOMAIN,
            "algorithm": candidate.ALGORITHM,
            "preauthorization_component_manifest_sha256": candidate.COMPONENT_MANIFEST_SHA256,
            "windows_component_manifest_sha256": candidate.WINDOWS_COMPONENT_MANIFEST_SHA256,
            "packet_component_manifest_sha256": candidate.PACKET_COMPONENT_MANIFEST_SHA256,
            "fixed_member_contract_sha256": candidate.FIXED_MEMBER_CONTRACT_SHA256,
            "member_commitment_domain": candidate.MEMBER_COMMITMENT_DOMAIN,
            "member_commitment_sha256": "00" * 32,
            "members": members,
            "packet_id": "P0:A:ANNOTATION:PACKET:V2:test-packet",
            "packet_manifest_raw_sha256": members[0]["raw_sha256"],
            "packet_manifest_artifact_sha256": "22" * 32,
            "trust_domain": pin["trust_domain"],
            "project_id": pin["project_id"],
            "environment": pin["environment"],
            "session_id": "session-v2",
            "run_id": "run-v2",
            "preauthorization_id": "preauthorization-v2",
            "owner_principal_sha256": pin["owner_principal_sha256"],
            "owner_anchor_sha256": pin["owner_anchor_sha256"],
            "key_id": pin["key_id"],
            "key_epoch": pin["key_epoch"],
            "public_key_fingerprint_sha256": pin["public_key_fingerprint_sha256"],
            "root_final_path": r"\\?\Volume{11111111-2222-3333-4444-555555555555}\packet-v2",
            "root_volume_serial": "123456789",
            "root_file_id": "33" * 16,
            "issued_at": "2026-09-03T01:00:00Z",
            "not_before": "2026-09-03T01:00:00Z",
            "expires_at": "2026-09-03T02:00:00Z",
            "nonce_base64": base64.b64encode(b"n" * 32).decode("ascii"),
            "nonce_context_domain": candidate.NONCE_CONTEXT_DOMAIN,
            "nonce_context_commitment_sha256": "00" * 32,
            "single_use": True,
            **{field: False for field in candidate._BODY_FALSE_FIELDS},
            "operational_effect": candidate.OPERATIONAL_EFFECT,
            "gate_status": candidate.GATE_STATUS,
        }
        body["member_commitment_sha256"] = digest({
            "domain": candidate.MEMBER_COMMITMENT_DOMAIN,
            "packet_component_manifest_sha256": candidate.PACKET_COMPONENT_MANIFEST_SHA256,
            "windows_component_manifest_sha256": candidate.WINDOWS_COMPONENT_MANIFEST_SHA256,
            "fixed_member_contract_sha256": candidate.FIXED_MEMBER_CONTRACT_SHA256,
            "members": members,
        })
        body["nonce_context_commitment_sha256"] = candidate._nonce_context(body)
        if body_changes:
            body.update(body_changes)
        body = reseal(body)
        pin_raw = file_bytes(pin)
        body_raw = file_bytes(body)
        envelope: dict[str, object] = {
            "schema_version": candidate.SIGNATURE_ENVELOPE_SCHEMA,
            "record_origin": candidate.SIGNATURE_ORIGIN,
            "domain": candidate.SIGNATURE_DOMAIN,
            "algorithm": candidate.ALGORITHM,
            "preauthorization_schema": candidate.PREAUTHORIZATION_SCHEMA,
            "preauthorization_component_manifest_sha256": candidate.COMPONENT_MANIFEST_SHA256,
            "public_key_pin_bytes_sha256": hashlib.sha256(pin_raw).hexdigest(),
            "public_key_pin_artifact_sha256": pin["artifact_sha256"],
            "preauthorization_bytes_sha256": hashlib.sha256(body_raw).hexdigest(),
            "preauthorization_artifact_sha256": body["artifact_sha256"],
            "member_commitment_sha256": body["member_commitment_sha256"],
            "nonce_context_commitment_sha256": body["nonce_context_commitment_sha256"],
            "trust_domain": body["trust_domain"],
            "project_id": body["project_id"],
            "environment": body["environment"],
            "session_id": body["session_id"],
            "run_id": body["run_id"],
            "preauthorization_id": body["preauthorization_id"],
            "key_id": body["key_id"],
            "key_epoch": body["key_epoch"],
            "public_key_fingerprint_sha256": body["public_key_fingerprint_sha256"],
            "owner_principal_sha256": body["owner_principal_sha256"],
            "owner_anchor_sha256": body["owner_anchor_sha256"],
            "signature_rs_base64": "",
        }
        if envelope_changes:
            envelope.update(envelope_changes)
        material = {
            key: envelope[key]
            for key in candidate._ENVELOPE_FIELDS
            if key not in {"signature_rs_base64", "artifact_sha256"}
        }
        der = private_key.sign(canonical(material), ec.ECDSA(hashes.SHA256()))
        r, s = utils.decode_dss_signature(der)
        if s > candidate._P256_ORDER // 2:
            s = candidate._P256_ORDER - s
        signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
        envelope["signature_rs_base64"] = base64.b64encode(signature).decode("ascii")
        envelope = reseal(envelope)
        return pin, body, envelope

    def _windows_receipt(self, body: dict[str, object]) -> dict[str, object]:
        pins = {member["role"]: member["raw_sha256"] for member in body["members"]}  # type: ignore[index]
        pin_set = digest(pins)
        sha_a = "44" * 32
        sha_b = "55" * 32
        safe: dict[str, object] = {
            "schema_version": candidate.windows_v2.SAFE_HANDLE_PROJECTION_SCHEMA,
            "handle_receipt_sha256": "66" * 32,
            "root_final_path": body["root_final_path"],
            "root_volume_serial": body["root_volume_serial"],
            "root_file_id": body["root_file_id"],
            "ancestor_handle_count": 2,
            "member_handle_count": 16,
            "windows_component_manifest_sha256": candidate.WINDOWS_COMPONENT_MANIFEST_SHA256,
            "packet_component_manifest_sha256": candidate.PACKET_COMPONENT_MANIFEST_SHA256,
            "fixed_member_contract_sha256": candidate.FIXED_MEMBER_CONTRACT_SHA256,
            "member_raw_caps_sha256": digest(candidate._MEMBER_RAW_CAPS),
            "expected_member_raw_pin_set_sha256": pin_set,
            "member_sequence": list(candidate._MEMBER_ROLES),
            "member_sequence_sha256": digest(list(candidate._MEMBER_ROLES)),
            "total_member_bytes": 12345,
            "aggregate_member_cap_bytes": candidate._AGGREGATE_MEMBER_CAP_BYTES,
            "inventory_before_sha256": sha_a,
            "inventory_after_sha256": sha_a,
            "ancestor_chain_sha256": sha_b,
            "root_before_projection_sha256": sha_b,
            "root_after_projection_sha256": sha_b,
            "root_reopen_projection_sha256": sha_b,
            "member_evidence_sha256": sha_a,
            "handles_held_across_packet_validation": True,
            "local_byte_handle_consistency_verified": True,
            **{field: False for field in candidate._WINDOWS_DENIAL_FIELDS},
        }
        safe = receipt_reseal(safe)
        receipt: dict[str, object] = {
            "schema_version": candidate.windows_v2.WINDOWS_DIRECTORY_RECEIPT_SCHEMA,
            "validation_mode": "WINDOWS_FIXED_DIRECTORY_DIRECT",
            "windows_component_manifest_sha256": candidate.WINDOWS_COMPONENT_MANIFEST_SHA256,
            "packet_component_manifest_sha256": candidate.PACKET_COMPONENT_MANIFEST_SHA256,
            "fixed_member_contract_sha256": candidate.FIXED_MEMBER_CONTRACT_SHA256,
            "fixed_member_count": 16,
            "aggregate_member_cap_bytes": candidate._AGGREGATE_MEMBER_CAP_BYTES,
            "expected_member_raw_sha256": pins,
            "validated_member_raw_sha256": dict(pins),
            "expected_member_raw_pin_set_sha256": pin_set,
            "producer_manifest_validated": True,
            "producer_parent_validated": True,
            "producer_parent_receipt_sha256": "77" * 32,
            "producer_parent_receipt_full_sha256": "78" * 32,
            "independent_target_parent_receipt_sha256": "79" * 32,
            "independent_target_parent_receipt_full_sha256": "7a" * 32,
            "packet_parent_execution_count": 1,
            "independent_target_parent_execution_count": 1,
            "total_target_parent_execution_count": 2,
            "target_parent_single_execution_claimed": False,
            "byte_inventory_binding_verified": True,
            "handles_held_across_packet_validation": True,
            "local_byte_handle_consistency_verified": True,
            **{field: False for field in candidate._WINDOWS_DENIAL_FIELDS},
            "operational_effect": "NONE_SHADOW_ONLY",
            "gate_status": "NO_GO_PRESENTED_PACKET_V2_BOUNDED_WINDOWS_HANDLE_BINDING_ONLY",
            "receipt_hash_scope": "CANONICAL_MATERIAL_EXCLUDING_RECEIPT_SHA256",
            "root_final_path": body["root_final_path"],
            "root_volume_serial": body["root_volume_serial"],
            "root_file_id": body["root_file_id"],
            "ancestor_handle_count": 2,
            "member_handle_count": 16,
            "handle_safe_projection": safe,
            "handle_safe_projection_sha256": safe["receipt_sha256"],
        }
        return receipt_reseal(receipt)

    def _crypto_verify(self, **kwargs: bytes) -> None:
        der = utils.encode_dss_signature(
            int.from_bytes(kwargs["signature"][:32], "big"),
            int.from_bytes(kwargs["signature"][32:], "big"),
        )
        key = ec.EllipticCurvePublicNumbers(
            int.from_bytes(kwargs["public_key_x"], "big"),
            int.from_bytes(kwargs["public_key_y"], "big"),
            ec.SECP256R1(),
        ).public_key()
        try:
            key.verify(
                der, kwargs["digest"],
                ec.ECDSA(utils.Prehashed(hashes.SHA256())),
            )
        except InvalidSignature as exc:
            raise cng.P0WindowsCngEcdsaP256Error("signature mismatch") from exc

    def _validate(
        self,
        *, pin: dict[str, object] | None = None,
        body: dict[str, object] | None = None,
        envelope: dict[str, object] | None = None,
        windows_receipt: dict[str, object] | None = None,
        observed_at: str | None = None,
    ) -> tuple[dict[str, object], object, object]:
        pin = pin or self.pin
        body = body or self.body
        envelope = envelope or self.envelope
        with (
            patch.object(candidate.os, "name", "nt"),
            patch.object(candidate.cng_p256, "verify_p256_sha256", side_effect=self._crypto_verify) as cng_call,
            patch.object(
                candidate.windows_v2,
                "validate_presented_a_context_annotation_packet_v2_windows_directory",
                return_value=windows_receipt or self.windows_receipt,
            ) as windows_call,
        ):
            receipt = candidate.validate_owner_root_preauthorization_v2_windows(
                self.packet_dir,
                public_key_pin_bytes=file_bytes(pin),
                preauthorization_bytes=file_bytes(body),
                signature_envelope_bytes=file_bytes(envelope),
                observed_at=observed_at or self.observed_at,
            )
        return receipt, cng_call, windows_call

    def test_controlled_signature_positive_and_exact_public_receipt(self) -> None:
        receipt, cng_call, windows_call = self._validate()
        cng_call.assert_called_once()
        windows_call.assert_called_once_with(
            self.packet_dir,
            expected_root_final_path=self.body["root_final_path"],
            expected_root_volume_serial=int(self.body["root_volume_serial"]),
            expected_root_file_id=self.body["root_file_id"],
            expected_member_raw_sha256={
                member["role"]: member["raw_sha256"] for member in self.body["members"]  # type: ignore[index]
            },
        )
        self.assertEqual(tuple(receipt), candidate._RECEIPT_FIELDS)
        material = dict(receipt)
        declared = material.pop("receipt_sha256")
        self.assertEqual(declared, digest(material))
        for field in candidate._RECEIPT_TRUE_FIELDS:
            self.assertIs(receipt[field], True, field)
        for field in candidate._RECEIPT_FALSE_FIELDS:
            self.assertIs(receipt[field], False, field)
        self.assertEqual(receipt["credited_actual_source_claim_count"], 0)
        self.assertEqual(receipt["credited_actual_a_context_review_count"], 0)
        self.assertNotIn("handle_safe_projection", receipt)
        self.assertNotIn("windows_receipt", receipt)

    def test_public_api_is_exact_and_component_hash_is_stable(self) -> None:
        self.assertEqual(candidate.__all__, ["validate_owner_root_preauthorization_v2_windows"])
        self.assertEqual(
            tuple(inspect.signature(candidate.validate_owner_root_preauthorization_v2_windows).parameters),
            ("packet_dir", "public_key_pin_bytes", "preauthorization_bytes", "signature_envelope_bytes", "observed_at"),
        )
        self.assertEqual(
            candidate.COMPONENT_MANIFEST_SHA256,
            digest(candidate.COMPONENT_MANIFEST),
        )
        self.assertEqual(
            candidate.COMPONENT_MANIFEST_SHA256,
            "07ae0af427112978ba3cb5f5a0ae8713a25837cbb9ae65ac0b7993da7d44876e",
        )
        self.assertEqual(
            candidate.WINDOWS_COMPONENT_MANIFEST_SHA256,
            "4e4e5c76fd3fd210a5e3c381243dccec623f2c0a48afbba6e52667d38afaae02",
        )

    def test_invalid_signature_domain_component_and_chronology_have_zero_windows_calls(self) -> None:
        cases: list[tuple[dict[str, object], dict[str, object], dict[str, object], str]] = []
        bad_signature = deepcopy(self.envelope)
        raw = bytearray(base64.b64decode(bad_signature["signature_rs_base64"]))
        raw[0] ^= 1
        bad_signature["signature_rs_base64"] = base64.b64encode(raw).decode("ascii")
        bad_signature = reseal(bad_signature)
        cases.append((self.pin, self.body, bad_signature, self.observed_at))
        bad_domain = deepcopy(self.envelope)
        bad_domain["domain"] = "wrong-domain"
        bad_domain = reseal(bad_domain)
        cases.append((self.pin, self.body, bad_domain, self.observed_at))
        _, bad_component_body, bad_component_env = self._bundle(
            self.private_key,
            body_changes={"windows_component_manifest_sha256": "aa" * 32},
        )
        cases.append((self.pin, bad_component_body, bad_component_env, self.observed_at))
        cases.append((self.pin, self.body, self.envelope, "2026-09-03T02:00:00Z"))
        for pin, body, envelope, observed in cases:
            with self.subTest(observed=observed, domain=envelope["domain"]):
                with (
                    patch.object(candidate.os, "name", "nt"),
                    patch.object(candidate.cng_p256, "verify_p256_sha256", side_effect=self._crypto_verify),
                    patch.object(candidate.windows_v2, "validate_presented_a_context_annotation_packet_v2_windows_directory") as windows_call,
                ):
                    with self.assertRaises(candidate.P0ActualOwnerRootPreauthorizationV2Error):
                        candidate.validate_owner_root_preauthorization_v2_windows(
                            self.packet_dir,
                            public_key_pin_bytes=file_bytes(pin),
                            preauthorization_bytes=file_bytes(body),
                            signature_envelope_bytes=file_bytes(envelope),
                            observed_at=observed,
                        )
                windows_call.assert_not_called()

    def test_signature_encoding_high_s_zero_range_der_and_base64_rejected(self) -> None:
        good = base64.b64decode(self.envelope["signature_rs_base64"])
        variants = (
            b"\x01" * 32 + (candidate._P256_ORDER - 1).to_bytes(32, "big"),
            b"\x00" * 32 + good[32:],
            candidate._P256_ORDER.to_bytes(32, "big") + good[32:],
            utils.encode_dss_signature(1, 1),
            b"not base64",
        )
        for signature in variants:
            envelope = deepcopy(self.envelope)
            if signature == b"not base64":
                envelope["signature_rs_base64"] = "@@not-base64@@"
            else:
                envelope["signature_rs_base64"] = base64.b64encode(signature).decode("ascii")
            envelope = reseal(envelope)
            with self.subTest(length=len(signature)):
                with patch.object(candidate.windows_v2, "validate_presented_a_context_annotation_packet_v2_windows_directory") as call:
                    with self.assertRaises(candidate.P0ActualOwnerRootPreauthorizationV2Error):
                        candidate.validate_owner_root_preauthorization_v2_windows(
                            self.packet_dir,
                            public_key_pin_bytes=file_bytes(self.pin),
                            preauthorization_bytes=file_bytes(self.body),
                            signature_envelope_bytes=file_bytes(envelope),
                            observed_at=self.observed_at,
                        )
                call.assert_not_called()

    def test_canonical_framing_duplicate_nan_bom_crlf_and_caps_rejected(self) -> None:
        pin_raw = file_bytes(self.pin)
        malformed = (
            b"\xef\xbb\xbf" + pin_raw,
            pin_raw.replace(b"\n", b"\r\n"),
            pin_raw[:-1],
            pin_raw.replace(b'"algorithm":', b'"algorithm":"duplicate","algorithm":', 1),
            pin_raw.replace(b'"key_epoch":7', b'"key_epoch":NaN'),
            b"{" + b"x" * candidate._MAX_PIN_BYTES + b"}\n",
        )
        for raw in malformed:
            with self.subTest(prefix=raw[:8]):
                with patch.object(candidate.windows_v2, "validate_presented_a_context_annotation_packet_v2_windows_directory") as call:
                    with self.assertRaises(candidate.P0ActualOwnerRootPreauthorizationV2Error):
                        candidate.validate_owner_root_preauthorization_v2_windows(
                            self.packet_dir,
                            public_key_pin_bytes=raw,
                            preauthorization_bytes=file_bytes(self.body),
                            signature_envelope_bytes=file_bytes(self.envelope),
                            observed_at=self.observed_at,
                        )
                call.assert_not_called()

    def test_pin_body_envelope_cross_swaps_are_rejected(self) -> None:
        other_key = ec.generate_private_key(ec.SECP256R1())
        other_pin, other_body, other_envelope = self._bundle(other_key)
        cases = (
            (other_pin, self.body, self.envelope),
            (self.pin, other_body, other_envelope),
            (self.pin, self.body, other_envelope),
        )
        for pin, body, envelope in cases:
            with self.subTest(case=envelope["public_key_fingerprint_sha256"]):
                with patch.object(candidate.windows_v2, "validate_presented_a_context_annotation_packet_v2_windows_directory") as call:
                    with self.assertRaises(candidate.P0ActualOwnerRootPreauthorizationV2Error):
                        candidate.validate_owner_root_preauthorization_v2_windows(
                            self.packet_dir,
                            public_key_pin_bytes=file_bytes(pin),
                            preauthorization_bytes=file_bytes(body),
                            signature_envelope_bytes=file_bytes(envelope),
                            observed_at=self.observed_at,
                        )
                call.assert_not_called()

    def test_member_order_role_path_media_cap_and_sha_are_rejected(self) -> None:
        mutations = (
            (1, "ordinal", 2), (1, "role", "wrong"), (1, "path", "wrong.json"),
            (1, "media_type", "text/plain"), (1, "max_bytes", 1),
            (1, "raw_sha256", "ABC"),
        )
        for mutation in mutations:
            pin, body, envelope = self._bundle(self.private_key, member_change=mutation)
            with self.subTest(mutation=mutation):
                with patch.object(candidate.windows_v2, "validate_presented_a_context_annotation_packet_v2_windows_directory") as call:
                    with self.assertRaises(candidate.P0ActualOwnerRootPreauthorizationV2Error):
                        candidate.validate_owner_root_preauthorization_v2_windows(
                            self.packet_dir,
                            public_key_pin_bytes=file_bytes(pin),
                            preauthorization_bytes=file_bytes(body),
                            signature_envelope_bytes=file_bytes(envelope),
                            observed_at=self.observed_at,
                        )
                call.assert_not_called()

    def test_packet_manifest_split_view_is_rejected_before_windows(self) -> None:
        pin, body, envelope = self._bundle(
            self.private_key,
            body_changes={"packet_manifest_raw_sha256": "ab" * 32},
        )
        with (
            patch.object(candidate.cng_p256, "verify_p256_sha256") as cng_call,
            patch.object(
                candidate.windows_v2,
                "validate_presented_a_context_annotation_packet_v2_windows_directory",
            ) as call,
        ):
            with self.assertRaisesRegex(
                candidate.P0ActualOwnerRootPreauthorizationV2Error,
                r"member\[0\]",
            ):
                candidate.validate_owner_root_preauthorization_v2_windows(
                    self.packet_dir,
                    public_key_pin_bytes=file_bytes(pin),
                    preauthorization_bytes=file_bytes(body),
                    signature_envelope_bytes=file_bytes(envelope),
                    observed_at=self.observed_at,
                )
        call.assert_not_called()
        cng_call.assert_not_called()

    def test_observation_window_is_closed_at_expiry_and_open_at_not_before(self) -> None:
        accepted, _, _ = self._validate(observed_at="2026-09-03T01:00:00Z")
        self.assertIs(accepted["preauthorization_chronology_window_matched"], True)
        with patch.object(
            candidate.windows_v2,
            "validate_presented_a_context_annotation_packet_v2_windows_directory",
        ) as call:
            with self.assertRaises(candidate.P0ActualOwnerRootPreauthorizationV2Error):
                candidate.validate_owner_root_preauthorization_v2_windows(
                    self.packet_dir,
                    public_key_pin_bytes=file_bytes(self.pin),
                    preauthorization_bytes=file_bytes(self.body),
                    signature_envelope_bytes=file_bytes(self.envelope),
                    observed_at="2026-09-03T02:00:00Z",
                )
        call.assert_not_called()

    def test_signed_root_mismatch_in_windows_receipt_is_rejected(self) -> None:
        forged = deepcopy(self.windows_receipt)
        forged["root_file_id"] = "99" * 16
        forged = receipt_reseal(forged)
        with self.assertRaises(candidate.P0ActualOwnerRootPreauthorizationV2Error):
            self._validate(windows_receipt=forged)

    def test_same_bundle_can_pass_twice_but_replay_claims_remain_false(self) -> None:
        first, _, _ = self._validate()
        second, _, _ = self._validate()
        self.assertEqual(first, second)
        self.assertIs(first["single_use_replay_consumed"], False)
        self.assertIs(first["same_bundle_replay_prevented"], False)
        self.assertIs(first["durable_cross_process_nonce_verified"], False)

    def test_complete_attacker_replacement_passes_math_without_authority(self) -> None:
        attacker_key = ec.generate_private_key(ec.SECP256R1())
        pin, body, envelope = self._bundle(
            attacker_key,
            pin_changes={"owner_principal_sha256": "aa" * 32},
        )
        # A coherent attacker derives a new anchor after choosing its principal.
        pin["owner_anchor_sha256"] = digest({
            "domain": candidate.OWNER_ANCHOR_DOMAIN,
            "trust_domain": pin["trust_domain"], "project_id": pin["project_id"],
            "environment": pin["environment"],
            "owner_principal_sha256": pin["owner_principal_sha256"],
        })
        pin = reseal(pin)
        # Rebuild fully so body/envelope bind the replaced pin.
        pin, body, envelope = self._bundle(attacker_key)
        receipt = self._windows_receipt(body)
        result, _, _ = self._validate(
            pin=pin, body=body, envelope=envelope, windows_receipt=receipt,
        )
        self.assertIs(result["asymmetric_signature_math_verified"], True)
        self.assertIs(result["external_public_key_pin_provisioning_verified"], False)
        self.assertIs(result["owner_authority_verified"], False)
        self.assertIs(result["actual_authority_granted"], False)

    def test_forged_resealed_windows_truth_root_and_hash_are_rejected(self) -> None:
        forged_truth = deepcopy(self.windows_receipt)
        forged_truth["actual_authority_granted"] = True
        forged_truth = receipt_reseal(forged_truth)
        forged_root = deepcopy(self.windows_receipt)
        forged_root["root_volume_serial"] = "123456788"
        forged_root = receipt_reseal(forged_root)
        forged_hash = deepcopy(self.windows_receipt)
        forged_hash["receipt_sha256"] = "00" * 32
        forged_safe = deepcopy(self.windows_receipt)
        safe = dict(forged_safe["handle_safe_projection"])
        safe["trusted_time_verified"] = True
        safe = receipt_reseal(safe)
        forged_safe["handle_safe_projection"] = safe
        forged_safe["handle_safe_projection_sha256"] = safe["receipt_sha256"]
        forged_safe = receipt_reseal(forged_safe)
        for forged in (forged_truth, forged_root, forged_hash, forged_safe):
            with self.subTest(value=forged["receipt_sha256"]):
                with self.assertRaises(candidate.P0ActualOwnerRootPreauthorizationV2Error):
                    self._validate(windows_receipt=forged)

    def test_coherent_monkeypatched_windows_result_never_grants_authority(self) -> None:
        receipt, _, windows_call = self._validate()
        windows_call.assert_called_once()
        self.assertIs(receipt["windows_receipt_strictly_validated"], True)
        self.assertIs(receipt["same_process_monkeypatch_resistance_verified"], False)
        self.assertIs(receipt["filesystem_handle_trust_verified"], False)
        self.assertIs(receipt["actual_authority_granted"], False)

    def test_non_windows_fails_after_crypto_preflight_without_filesystem_call(self) -> None:
        with (
            patch.object(candidate.os, "name", "posix"),
            patch.object(candidate.cng_p256, "verify_p256_sha256", side_effect=self._crypto_verify) as crypto,
            patch.object(candidate.windows_v2, "validate_presented_a_context_annotation_packet_v2_windows_directory") as windows_call,
        ):
            with self.assertRaisesRegex(
                candidate.P0ActualOwnerRootPreauthorizationV2Error,
                "Windows direct fixed-directory",
            ):
                candidate.validate_owner_root_preauthorization_v2_windows(
                    self.packet_dir,
                    public_key_pin_bytes=file_bytes(self.pin),
                    preauthorization_bytes=file_bytes(self.body),
                    signature_envelope_bytes=file_bytes(self.envelope),
                    observed_at=self.observed_at,
                )
        crypto.assert_called_once()
        windows_call.assert_not_called()

    def test_v1_fixed_14_hash_schema_domain_and_ref0_are_unchanged(self) -> None:
        self.assertEqual(len(v1.FIXED_MEMBER_CONTRACT), 14)
        self.assertEqual(
            v1.FIXED_MEMBER_CONTRACT_SHA256,
            "72189ac02f34f100c5d07e62f1acccb3a86f79756f3381e57dba637341012256",
        )
        self.assertEqual(v1.PREAUTHORIZATION_SCHEMA, "p0_actual_owner_capture_root_preauthorization_v1")
        self.assertEqual(
            v1.PREAUTHORIZATION_DOMAIN,
            "llm-novel-dc-community-parser/p0-actual-owner-capture-root-preauthorization/v1",
        )
        self.assertEqual(v1.FIXED_MEMBER_CONTRACT[0], {
            "role": "packet_manifest",
            "path": "p0_actual_keyless_pilot_manifest_v1.json",
            "media_type": "application/json",
        })


if __name__ == "__main__":
    unittest.main()
