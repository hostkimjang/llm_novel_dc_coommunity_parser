from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import inspect
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

from llm_batch.grounding import p0_actual_owner_root_preauthorization_v2 as preauth_v2
from llm_batch.grounding import p0_windows_owner_policy_contract as owner_policy
from llm_batch.grounding import (
    p0_windows_owner_policy_v4_packet_v2_profile_contract as candidate,
)
from tests import test_p0_windows_owner_policy_v3 as v3_fixture
from tests import test_p0_windows_owner_policy_contract as v1_fixture


def _low_s_sign(private_key: ec.EllipticCurvePrivateKey, material: bytes) -> bytes:
    der = private_key.sign(material, ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der)
    if s > candidate._P256_ORDER // 2:
        s = candidate._P256_ORDER - s
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


class WindowsOwnerPolicyV4PacketV2ProfileContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bootstrap_private = ec.generate_private_key(ec.SECP256R1())
        self.packet_private = ec.generate_private_key(ec.SECP256R1())
        self.bootstrap_spki = self.bootstrap_private.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self.predecessor_body = v3_fixture._v3_body()
        self.predecessor_body["bootstrap_public_key_fingerprint_sha256"] = (
            hashlib.sha256(self.bootstrap_spki).hexdigest()
        )
        self.predecessor_body["owner_anchor_sha256"] = (
            v3_fixture._derive_v3_anchor(self.predecessor_body)
        )
        self.predecessor_body = v1_fixture._rehash(self.predecessor_body)
        self.predecessor_signature = v3_fixture._v3_signature(
            self.predecessor_body
        )
        self.predecessor_body_raw, self.predecessor_signature_raw = (
            v1_fixture._contract_bytes(
                self.predecessor_body, self.predecessor_signature
            )
        )
        self.predecessor_receipt = (
            owner_policy.validate_presented_windows_owner_policy_contract(
                policy_body_bytes=self.predecessor_body_raw,
                policy_signature_bytes=self.predecessor_signature_raw,
            )
        )
        self.pin = self._pin()
        self.pin_raw = candidate.json_file_bytes(self.pin)
        self.body = self._body()
        self.body_raw = candidate.json_file_bytes(self.body)
        self.signature = self._signature(self.body, self.body_raw)
        self.signature_raw = candidate.json_file_bytes(self.signature)

    def _pin(self) -> dict[str, object]:
        numbers = self.packet_private.public_key().public_numbers()
        x = numbers.x.to_bytes(32, "big")
        y = numbers.y.to_bytes(32, "big")
        owner_principal = self.predecessor_body["owner_principal_sha256"]
        row: dict[str, object] = {
            "schema_version": candidate.PACKET_PUBLIC_KEY_PIN_SCHEMA,
            "record_origin": preauth_v2.PIN_ORIGIN,
            "trust_domain": self.predecessor_body["trust_domain"],
            "project_id": self.predecessor_body["project_id"],
            "environment": self.predecessor_body["environment"],
            "purpose": candidate.PACKET_PREAUTHORIZATION_PURPOSE,
            "key_id": "packet-v2-owner-key-001",
            "key_epoch": 3,
            "algorithm": candidate.PACKET_PREAUTHORIZATION_ALGORITHM,
            "curve": preauth_v2.CURVE,
            "coordinate_encoding": preauth_v2.COORDINATE_ENCODING,
            "fingerprint_encoding": preauth_v2.FINGERPRINT_ENCODING,
            "public_key_x_base64": base64.b64encode(x).decode("ascii"),
            "public_key_y_base64": base64.b64encode(y).decode("ascii"),
            "public_key_fingerprint_sha256": hashlib.sha256(
                preauth_v2._P256_SPKI_PREFIX + x + y
            ).hexdigest(),
            "owner_principal_sha256": owner_principal,
            "owner_anchor_sha256": "00" * 32,
            "allowed_signature_domains": [
                candidate.PACKET_PREAUTHORIZATION_SIGNATURE_DOMAIN
            ],
        }
        row["owner_anchor_sha256"] = candidate.canonical_sha256({
            "domain": preauth_v2.OWNER_ANCHOR_DOMAIN,
            "trust_domain": row["trust_domain"],
            "project_id": row["project_id"],
            "environment": row["environment"],
            "owner_principal_sha256": owner_principal,
        })
        return candidate.with_artifact_hash(row)

    def _install_pin(self, pin: dict[str, object]) -> None:
        self.pin = pin
        self.pin_raw = candidate.json_file_bytes(pin)

    def _install_predecessor(self, body: dict[str, object]) -> None:
        body["owner_anchor_sha256"] = v3_fixture._derive_v3_anchor(body)
        self.predecessor_body = v1_fixture._rehash(body)
        self.predecessor_signature = v3_fixture._v3_signature(
            self.predecessor_body
        )
        self.predecessor_body_raw, self.predecessor_signature_raw = (
            v1_fixture._contract_bytes(
                self.predecessor_body, self.predecessor_signature
            )
        )
        self.predecessor_receipt = (
            owner_policy.validate_presented_windows_owner_policy_contract(
                policy_body_bytes=self.predecessor_body_raw,
                policy_signature_bytes=self.predecessor_signature_raw,
            )
        )

    def _invalid_wdac_uuid_predecessor_raw(self) -> bytes:
        predecessor = deepcopy(self.predecessor_body)
        projection = predecessor["deployment_projection"]
        projection["wdac_policy_id"] = "not-a-canonical-uuid"
        projection = candidate.owner_policy.deployment.with_artifact_hash(
            projection
        )
        profile = predecessor["native_observer_profile"]
        profile["deployment_projection_sha256"] = projection["artifact_sha256"]
        profile = candidate.owner_policy.observer_profile.with_artifact_hash(
            profile
        )
        predecessor["deployment_projection"] = projection
        predecessor["native_observer_profile"] = profile
        predecessor["owner_anchor_sha256"] = v3_fixture._derive_v3_anchor(
            predecessor
        )
        predecessor = v1_fixture._rehash(predecessor)
        return owner_policy.json_file_bytes(predecessor)

    def _profile(self) -> dict[str, object]:
        row: dict[str, object] = {
            "schema_version": candidate.PROFILE_SCHEMA,
            "domain": candidate.PROFILE_DOMAIN,
            "public_key_pin_schema": candidate.PACKET_PUBLIC_KEY_PIN_SCHEMA,
            "public_key_pin_bytes_sha256": hashlib.sha256(self.pin_raw).hexdigest(),
            "public_key_pin_artifact_sha256": self.pin["artifact_sha256"],
            "public_key_fingerprint_sha256": self.pin["public_key_fingerprint_sha256"],
            "key_id": self.pin["key_id"],
            "key_epoch": self.pin["key_epoch"],
            "preauthorization_algorithm": candidate.PACKET_PREAUTHORIZATION_ALGORITHM,
            "preauthorization_signature_domain": candidate.PACKET_PREAUTHORIZATION_SIGNATURE_DOMAIN,
            "packet_component_manifest_sha256": candidate.PACKET_COMPONENT_MANIFEST_SHA256,
            "windows_component_manifest_sha256": candidate.WINDOWS_COMPONENT_MANIFEST_SHA256,
            "preauthorization_component_manifest_sha256": candidate.PREAUTHORIZATION_COMPONENT_MANIFEST_SHA256,
            "supervisor_component_manifest_sha256": candidate.SUPERVISOR_COMPONENT_MANIFEST_SHA256,
            "fixed_member_contract_sha256": candidate.FIXED_MEMBER_CONTRACT_SHA256,
            "max_preauthorization_ttl_seconds": candidate.MAX_PREAUTHORIZATION_TTL_SECONDS,
            "min_revocation_sequence": self.predecessor_body["min_revocation_sequence"],
            "packet_v2_purpose": candidate.PACKET_PREAUTHORIZATION_PURPOSE,
            "owner_principal_sha256": self.pin["owner_principal_sha256"],
            "public_key_pin_owner_anchor_sha256": self.pin["owner_anchor_sha256"],
            **{field: True for field in candidate._REQUIRED_CAPABILITY_FIELDS},
            **{field: False for field in candidate._PROFILE_FALSE_FIELDS},
        }
        row["profile_artifact_sha256"] = candidate.canonical_sha256(row)
        return row

    def _body(
        self, *, profile_changes: dict[str, object] | None = None,
        body_changes: dict[str, object] | None = None,
    ) -> dict[str, object]:
        profile = self._profile()
        if profile_changes:
            profile.update(profile_changes)
            profile.pop("profile_artifact_sha256", None)
            profile["profile_artifact_sha256"] = candidate.canonical_sha256(profile)
        row: dict[str, object] = {
            "schema_version": candidate.POLICY_BODY_SCHEMA,
            "record_origin": owner_policy.POLICY_ORIGIN,
            "domain": candidate.POLICY_DOMAIN,
            "policy_id": self.predecessor_body["policy_id"],
            "policy_epoch": self.predecessor_body["policy_epoch"] + 1,
            "predecessor_policy_v3_bytes_sha256": hashlib.sha256(
                self.predecessor_body_raw
            ).hexdigest(),
            "predecessor_policy_v3_epoch": self.predecessor_body["policy_epoch"],
            "predecessor_policy_v3_artifact_sha256": self.predecessor_body["artifact_sha256"],
            "predecessor_policy_v3_signature_bytes_sha256": hashlib.sha256(
                self.predecessor_signature_raw
            ).hexdigest(),
            "predecessor_policy_v3_signature_artifact_sha256": self.predecessor_signature[
                "artifact_sha256"
            ],
            "predecessor_contract_receipt_sha256": self.predecessor_receipt[
                "receipt_sha256"
            ],
            "project_id": self.predecessor_body["project_id"],
            "trust_domain": self.predecessor_body["trust_domain"],
            "environment": self.predecessor_body["environment"],
            "policy_purpose": self.predecessor_body["purpose"],
            "bootstrap_key_id": self.predecessor_body["bootstrap_key_id"],
            "bootstrap_public_key_fingerprint_sha256": self.predecessor_body[
                "bootstrap_public_key_fingerprint_sha256"
            ],
            "owner_principal_sha256": self.predecessor_body["owner_principal_sha256"],
            "packet_v2_owner_anchor_sha256": self.pin["owner_anchor_sha256"],
            "owner_anchor_sha256": "00" * 32,
            "packet_v2_preauthorization_profile": profile,
            "operational_effect": candidate.OPERATIONAL_EFFECT,
            "gate_status": candidate.GATE_STATUS,
        }
        if body_changes:
            row.update(body_changes)
        if not body_changes or "owner_anchor_sha256" not in body_changes:
            row["owner_anchor_sha256"] = candidate._derive_owner_anchor(row, profile)
        return candidate.with_artifact_hash(row)

    def _signature(
        self, body: dict[str, object], body_raw: bytes,
        *, changes: dict[str, object] | None = None,
        key: ec.EllipticCurvePrivateKey | None = None,
    ) -> dict[str, object]:
        row: dict[str, object] = {
            "schema_version": candidate.POLICY_SIGNATURE_SCHEMA,
            "record_origin": owner_policy.SIGNATURE_ORIGIN,
            "domain": candidate.SIGNATURE_DOMAIN,
            "algorithm": candidate.SIGNATURE_ALGORITHM,
            "policy_body_schema": candidate.POLICY_BODY_SCHEMA,
            "policy_body_bytes_sha256": hashlib.sha256(body_raw).hexdigest(),
            "policy_body_artifact_sha256": body["artifact_sha256"],
            "policy_id": body["policy_id"],
            "policy_epoch": body["policy_epoch"],
            "predecessor_policy_v3_bytes_sha256": body[
                "predecessor_policy_v3_bytes_sha256"
            ],
            "predecessor_policy_v3_epoch": body["predecessor_policy_v3_epoch"],
            "predecessor_policy_v3_artifact_sha256": body[
                "predecessor_policy_v3_artifact_sha256"
            ],
            "predecessor_policy_v3_signature_bytes_sha256": body[
                "predecessor_policy_v3_signature_bytes_sha256"
            ],
            "predecessor_policy_v3_signature_artifact_sha256": body[
                "predecessor_policy_v3_signature_artifact_sha256"
            ],
            "predecessor_contract_receipt_sha256": body[
                "predecessor_contract_receipt_sha256"
            ],
            "bootstrap_key_id": body["bootstrap_key_id"],
            "bootstrap_public_key_fingerprint_sha256": body[
                "bootstrap_public_key_fingerprint_sha256"
            ],
            "profile_artifact_sha256": body[
                "packet_v2_preauthorization_profile"
            ]["profile_artifact_sha256"],
            "owner_anchor_sha256": body["owner_anchor_sha256"],
            "signature_rs_base64": "",
        }
        if changes:
            row.update(changes)
        material = {
            field: row[field]
            for field in candidate._SIGNATURE_FIELDS
            if field not in {"signature_rs_base64", "artifact_sha256"}
        }
        row["signature_rs_base64"] = base64.b64encode(
            _low_s_sign(key or self.bootstrap_private, candidate.canonical_bytes(material))
        ).decode("ascii")
        return candidate.with_artifact_hash(row)

    def _validate(
        self, *, predecessor_body_raw: bytes | None = None,
        predecessor_signature_raw: bytes | None = None,
        pin_raw: bytes | None = None,
        body: dict[str, object] | None = None,
        signature: dict[str, object] | None = None,
        bootstrap_spki: bytes | None = None,
    ) -> dict[str, object]:
        actual_body = body or self.body
        body_raw = candidate.json_file_bytes(actual_body)
        actual_signature = signature or (
            self.signature if actual_body is self.body else self._signature(actual_body, body_raw)
        )
        return candidate.validate_presented_windows_owner_policy_v4_packet_v2_profile(
            predecessor_policy_v3_body_bytes=predecessor_body_raw or self.predecessor_body_raw,
            predecessor_policy_v3_signature_bytes=predecessor_signature_raw or self.predecessor_signature_raw,
            packet_v2_public_key_pin_bytes=pin_raw or self.pin_raw,
            policy_v4_body_bytes=body_raw,
            policy_v4_signature_bytes=candidate.json_file_bytes(actual_signature),
            bootstrap_public_key_spki_der=bootstrap_spki or self.bootstrap_spki,
        )

    def test_valid_signed_v4_profile_is_component_only_no_go(self) -> None:
        receipt = self._validate()
        self.assertEqual(receipt["gate_status"], candidate.GATE_STATUS)
        self.assertTrue(receipt["successor_bootstrap_signature_mathematics_verified"])
        self.assertTrue(receipt["predecessor_v3_parent_contract_validated"])
        self.assertTrue(receipt["exact_v2_algorithm_and_signature_domain_bound"])
        self.assertTrue(receipt["exact_component_pin_set_bound"])
        self.assertTrue(receipt["packet_v2_public_key_curve_point_verified"])
        self.assertTrue(receipt["packet_v2_owner_principal_cross_binding_verified"])
        self.assertTrue(receipt["packet_v2_owner_anchor_cross_binding_verified"])
        self.assertTrue(receipt["packet_key_four_role_separation_verified"])
        self.assertTrue(receipt["bounded_monotonic_epoch_profile_verified"])
        self.assertTrue(receipt["profile_artifact_self_hash_verified"])
        self.assertTrue(receipt["owner_anchor_v4_recomputed_verified"])
        self.assertTrue(receipt["predecessor_body_signature_receipt_bound"])
        self.assertEqual(
            receipt["packet_v2_owner_principal_sha256"],
            self.predecessor_body["owner_principal_sha256"],
        )
        self.assertEqual(
            receipt["packet_v2_owner_anchor_sha256"],
            self.pin["owner_anchor_sha256"],
        )
        self.assertEqual(
            receipt["profile_artifact_sha256"],
            self.body["packet_v2_preauthorization_profile"][
                "profile_artifact_sha256"
            ],
        )
        self.assertEqual(receipt["owner_anchor_sha256"], self.body["owner_anchor_sha256"])
        self.assertEqual(receipt["credited_actual_source_claim_count"], 0)
        self.assertEqual(receipt["credited_actual_a_context_review_count"], 0)
        for field in candidate._RECEIPT_FALSE_FIELDS:
            self.assertIs(receipt[field], False, field)
        material = dict(receipt)
        declared = material.pop("receipt_sha256")
        self.assertEqual(declared, candidate.canonical_sha256(material))

    def test_component_manifest_is_literal_pinned_and_recomputed(self) -> None:
        self.assertEqual(
            candidate.COMPONENT_MANIFEST_SHA256,
            candidate.canonical_sha256(candidate.COMPONENT_MANIFEST),
        )
        self.assertEqual(candidate.PACKET_COMPONENT_MANIFEST_SHA256, "2a4b63518b8d80522469753191c9879af6f85f55828f28318a149911e564d59f")
        self.assertEqual(candidate.WINDOWS_COMPONENT_MANIFEST_SHA256, "4e4e5c76fd3fd210a5e3c381243dccec623f2c0a48afbba6e52667d38afaae02")
        self.assertEqual(candidate.PREAUTHORIZATION_COMPONENT_MANIFEST_SHA256, "07ae0af427112978ba3cb5f5a0ae8713a25837cbb9ae65ac0b7993da7d44876e")
        self.assertEqual(candidate.SUPERVISOR_COMPONENT_MANIFEST_SHA256, "239b595763bf1bef0d5ab925d51f864f1c1c3090123f6ca540a225e4f9c4fddf")
        self.assertEqual(candidate.FIXED_MEMBER_CONTRACT_SHA256, "37f3a34ab17c219065b81d9f2eb3d9a8876c5e32e12e7051ec30f3e5038385fc")
        self.assertEqual(
            candidate.EXPECTED_COMPONENT_MANIFEST_SHA256,
            "9224e3c69c2748a882b81d5ccd29d02f3a9ad689e29a20ea6de6f100edbb9fc7",
        )

    def test_public_api_is_presented_only_and_parent_called_once(self) -> None:
        signature = inspect.signature(
            candidate.validate_presented_windows_owner_policy_v4_packet_v2_profile
        )
        self.assertEqual(
            tuple(signature.parameters),
            (
                "predecessor_policy_v3_body_bytes",
                "predecessor_policy_v3_signature_bytes",
                "packet_v2_public_key_pin_bytes",
                "policy_v4_body_bytes",
                "policy_v4_signature_bytes",
                "bootstrap_public_key_spki_der",
            ),
        )
        self._validate()
        self.assertIs(
            candidate._OWNER_POLICY_PARENT_VALIDATOR,
            owner_policy.validate_presented_windows_owner_policy_contract,
        )
        source = inspect.getsource(candidate)
        self.assertEqual(source.count("receipt = _OWNER_POLICY_PARENT_VALIDATOR("), 1)
        for forbidden in ("open(", "Path(", "subprocess", "requests", "urlopen"):
            self.assertNotIn(forbidden, source)

    def test_profile_algorithm_domain_and_component_substitution_fail_closed(self) -> None:
        mutations = {
            "preauthorization_algorithm": owner_policy.OPERATIONAL_KEY_ALGORITHM,
            "preauthorization_signature_domain": owner_policy.OPERATIONAL_SIGNATURE_DOMAIN,
            "packet_component_manifest_sha256": "aa" * 32,
            "windows_component_manifest_sha256": "aa" * 32,
            "preauthorization_component_manifest_sha256": "aa" * 32,
            "supervisor_component_manifest_sha256": "aa" * 32,
            "fixed_member_contract_sha256": "aa" * 32,
            "public_key_pin_schema": "wrong-schema",
            "public_key_pin_bytes_sha256": "aa" * 32,
            "public_key_pin_artifact_sha256": "aa" * 32,
            "public_key_fingerprint_sha256": "aa" * 32,
            "key_id": "substituted-key",
            "key_epoch": 4,
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
                    self._validate(body=self._body(profile_changes={field: value}))

    def test_downstream_requirements_and_mutation_denials_are_exact(self) -> None:
        for field in candidate._REQUIRED_CAPABILITY_FIELDS:
            with self.subTest(required=field):
                with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
                    self._validate(body=self._body(profile_changes={field: False}))
        for field in candidate._PROFILE_FALSE_FIELDS:
            with self.subTest(denial=field):
                with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
                    self._validate(body=self._body(profile_changes={field: True}))

    def test_predecessor_hash_epoch_scope_and_successor_epoch_are_bound(self) -> None:
        mutations = {
            "predecessor_policy_v3_bytes_sha256": "aa" * 32,
            "predecessor_policy_v3_epoch": 999,
            "predecessor_policy_v3_artifact_sha256": "aa" * 32,
            "policy_epoch": self.predecessor_body["policy_epoch"],
            "project_id": "other-project",
            "trust_domain": "other.example",
            "environment": "other",
            "policy_purpose": "other-purpose",
            "bootstrap_key_id": "other-key",
            "bootstrap_public_key_fingerprint_sha256": "aa" * 32,
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
                    self._validate(body=self._body(body_changes={field: value}))

    def test_non_v3_predecessor_is_rejected(self) -> None:
        v1_body = v1_fixture._body()
        v1_body_raw, v1_signature_raw = v1_fixture._contract_bytes(v1_body)
        with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
            self._validate(
                predecessor_body_raw=v1_body_raw,
                predecessor_signature_raw=v1_signature_raw,
            )

    def test_pin_substitution_scope_and_self_hash_fail_closed(self) -> None:
        pin = deepcopy(self.pin)
        pin["project_id"] = "other-project"
        pin = candidate.with_artifact_hash(pin)
        with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
            self._validate(pin_raw=candidate.json_file_bytes(pin))

    def test_pin_owner_principal_must_equal_predecessor_and_anchor_is_explicit(self) -> None:
        pin = deepcopy(self.pin)
        pin["owner_principal_sha256"] = "ab" * 32
        pin["owner_anchor_sha256"] = candidate.canonical_sha256({
            "domain": preauth_v2.OWNER_ANCHOR_DOMAIN,
            "trust_domain": pin["trust_domain"],
            "project_id": pin["project_id"],
            "environment": pin["environment"],
            "owner_principal_sha256": pin["owner_principal_sha256"],
        })
        self._install_pin(candidate.with_artifact_hash(pin))
        body = self._body()
        with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
            self._validate(body=body)

    def test_invalid_p256_coordinate_pair_is_rejected_after_shape_and_hash(self) -> None:
        pin = deepcopy(self.pin)
        zero = b"\x00" * 32
        pin["public_key_x_base64"] = base64.b64encode(zero).decode("ascii")
        pin["public_key_y_base64"] = base64.b64encode(zero).decode("ascii")
        pin["public_key_fingerprint_sha256"] = hashlib.sha256(
            preauth_v2._P256_SPKI_PREFIX + zero + zero
        ).hexdigest()
        pin = candidate.with_artifact_hash(pin)
        with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
            self._validate(pin_raw=candidate.json_file_bytes(pin))

    def test_packet_key_id_and_fingerprint_are_distinct_from_all_v3_roles(self) -> None:
        for predecessor_key_id in (
            self.predecessor_body["bootstrap_key_id"],
            self.predecessor_body["operational_key"]["key_id"],
            self.predecessor_body["native_observer_profile"]["observer_key_id"],
            self.predecessor_body["native_observer_profile"]["owner_state_authority_key_id"],
        ):
            pin = deepcopy(self.pin)
            pin["key_id"] = predecessor_key_id
            self._install_pin(candidate.with_artifact_hash(pin))
            with self.subTest(key_id=predecessor_key_id):
                with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
                    self._validate(body=self._body())
            self.pin = self._pin()
            self.pin_raw = candidate.json_file_bytes(self.pin)

        predecessor = deepcopy(self.predecessor_body)
        operational = predecessor["operational_key"]
        operational["public_key_fingerprint_sha256"] = self.pin[
            "public_key_fingerprint_sha256"
        ]
        predecessor["operational_key_projection_sha256"] = (
            owner_policy.derive_operational_key_projection_sha256(operational)
        )
        self._install_predecessor(predecessor)
        with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
            self._validate(body=self._body())

    def test_packet_key_epoch_is_bounded_and_strictly_newer_than_all_v3_epochs(self) -> None:
        for epoch in (True, 0, 1, 2**63):
            pin = deepcopy(self.pin)
            pin["key_epoch"] = epoch
            self._install_pin(candidate.with_artifact_hash(pin))
            with self.subTest(epoch=epoch):
                with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
                    self._validate(body=self._body())
            self.pin = self._pin()
            self.pin_raw = candidate.json_file_bytes(self.pin)

    def test_predecessor_max_epoch_has_no_bounded_successor(self) -> None:
        predecessor = deepcopy(self.predecessor_body)
        old_component = f"{1:020d}"
        new_component = f"{2**63 - 1:020d}"
        predecessor["policy_epoch"] = 2**63 - 1
        predecessor["predecessor_policy_bytes_sha256"] = "ef" * 32
        for row in predecessor["object_policies"]:
            row["final_volume_guid_path"] = row[
                "final_volume_guid_path"
            ].replace(old_component, new_component)
        self._install_predecessor(predecessor)
        with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
            self._validate(body=self.body)

    def test_predecessor_signature_and_parent_receipt_are_explicitly_bound(self) -> None:
        changed_signature = deepcopy(self.predecessor_signature)
        changed_signature["signature_rs_base64"] = base64.b64encode(
            (3).to_bytes(32, "big") + (4).to_bytes(32, "big")
        ).decode("ascii")
        changed_signature = v1_fixture._rehash(changed_signature)
        with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
            self._validate(
                predecessor_signature_raw=owner_policy.json_file_bytes(
                    changed_signature
                )
            )

        bad_receipt = deepcopy(self.predecessor_receipt)
        bad_receipt["policy_signature_artifact_sha256"] = "aa" * 32
        material = dict(bad_receipt)
        material.pop("receipt_sha256")
        bad_receipt["receipt_sha256"] = owner_policy.canonical_sha256(material)
        with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
            candidate._validate_predecessor_receipt(
                bad_receipt,
                body=self.predecessor_body,
                body_raw=self.predecessor_body_raw,
                signature=self.predecessor_signature,
                signature_raw=self.predecessor_signature_raw,
            )

    def test_parent_receipt_missing_reordered_and_bad_hash_errors_are_converted(self) -> None:
        missing = deepcopy(self.predecessor_receipt)
        missing.pop("store_id")
        reordered = dict(reversed(tuple(self.predecessor_receipt.items())))
        bad_hash = deepcopy(self.predecessor_receipt)
        bad_hash["receipt_sha256"] = "aa" * 32
        for receipt in (missing, reordered, bad_hash):
            with self.subTest(keys=len(receipt)):
                with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
                    candidate._validate_predecessor_receipt(
                        receipt,
                        body=self.predecessor_body,
                        body_raw=self.predecessor_body_raw,
                        signature=self.predecessor_signature,
                        signature_raw=self.predecessor_signature_raw,
                    )

    def test_profile_artifact_and_v4_owner_anchor_reseal_attacks_fail_closed(self) -> None:
        stale_profile = deepcopy(self.body)
        stale_profile["packet_v2_preauthorization_profile"][
            "trusted_time_required"
        ] = False
        stale_profile = candidate.with_artifact_hash(stale_profile)
        stale_raw = candidate.json_file_bytes(stale_profile)
        stale_signature = self._signature(stale_profile, stale_raw)
        with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
            self._validate(body=stale_profile, signature=stale_signature)

        bad_anchor = self._body(body_changes={"owner_anchor_sha256": "aa" * 32})
        with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
            self._validate(body=bad_anchor)

    def test_coordinated_dependency_manifest_substitution_is_rejected(self) -> None:
        evil = {"component": "substituted"}
        evil_sha = candidate.canonical_sha256(evil)
        with (
            patch.object(candidate.packet_v2, "COMPONENT_MANIFEST", evil),
            patch.object(candidate.packet_v2, "COMPONENT_MANIFEST_SHA256", evil_sha),
            patch.object(candidate.owner_policy, "validate_presented_windows_owner_policy_contract") as parent,
        ):
            with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
                self._validate()
        parent.assert_not_called()

    def test_coordinated_imported_packet_semantic_constants_cannot_redefine_v4(self) -> None:
        pin = deepcopy(self.pin)
        pin.update({
            "schema_version": "attacker-pin-schema",
            "purpose": "ATTACKER_PURPOSE",
            "algorithm": "ATTACKER_ALGORITHM",
            "allowed_signature_domains": ["attacker/signature/domain"],
        })
        pin = candidate.with_artifact_hash(pin)
        with (
            patch.object(candidate.preauth_v2, "PUBLIC_KEY_PIN_SCHEMA", pin["schema_version"]),
            patch.object(candidate.preauth_v2, "PURPOSE", pin["purpose"]),
            patch.object(candidate.preauth_v2, "ALGORITHM", pin["algorithm"]),
            patch.object(candidate.preauth_v2, "SIGNATURE_DOMAIN", pin["allowed_signature_domains"][0]),
        ):
            with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
                self._validate(pin_raw=candidate.json_file_bytes(pin))

    def test_coordinated_local_and_upstream_semantic_patch_cannot_redefine_sealed_manifest(self) -> None:
        with (
            patch.object(candidate, "SIGNATURE_ALGORITHM", "ATTACKER_SIG_ALG"),
            patch.object(candidate, "SIGNATURE_DOMAIN", "attacker/v4/signature"),
            patch.object(candidate, "PACKET_PREAUTHORIZATION_ALGORITHM", "ATTACKER_PACKET_ALG"),
            patch.object(candidate, "PACKET_PREAUTHORIZATION_SIGNATURE_DOMAIN", "attacker/packet/signature"),
            patch.object(candidate.preauth_v2, "ALGORITHM", "ATTACKER_PACKET_ALG"),
            patch.object(candidate.preauth_v2, "SIGNATURE_DOMAIN", "attacker/packet/signature"),
            patch.object(candidate.owner_policy, "BOOTSTRAP_SIGNATURE_ALGORITHM", "ATTACKER_SIG_ALG"),
            patch.object(candidate.owner_policy, "validate_presented_windows_owner_policy_contract") as parent,
        ):
            with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
                self._validate()
        parent.assert_not_called()

    def test_patched_parent_shaped_receipt_cannot_accept_invalid_v3_body(self) -> None:
        invalid = deepcopy(self.predecessor_body)
        invalid["owner_principal_sha256"] = "NOT_A_SHA"
        invalid = v1_fixture._rehash(invalid)
        invalid_raw = owner_policy.json_file_bytes(invalid)
        shaped = deepcopy(self.predecessor_receipt)
        with patch.object(
            candidate.owner_policy,
            "validate_presented_windows_owner_policy_contract",
            return_value=shaped,
        ) as parent:
            with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
                self._validate(predecessor_body_raw=invalid_raw)
        parent.assert_not_called()

    def test_parent_receipt_store_anchor_and_full_identity_reseal_are_rejected(self) -> None:
        attacks = {
            "store_id": "attacker-store",
            "owner_anchor_sha256": "aa" * 32,
            "full_policy_identity_sha256": "bb" * 32,
        }
        for field, value in attacks.items():
            receipt = deepcopy(self.predecessor_receipt)
            receipt[field] = value
            material = dict(receipt)
            material.pop("receipt_sha256")
            receipt["receipt_sha256"] = owner_policy.canonical_sha256(material)
            with self.subTest(field=field):
                with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
                    candidate._validate_predecessor_receipt(
                        receipt,
                        body=self.predecessor_body,
                        body_raw=self.predecessor_body_raw,
                        signature=self.predecessor_signature,
                        signature_raw=self.predecessor_signature_raw,
                    )

    def test_side_effectful_public_parent_patch_is_rejected_before_invocation(self) -> None:
        touched = {"value": False}

        def side_effectful_parent(**_kwargs: object) -> dict[str, object]:
            touched["value"] = True
            candidate.packet_v2.COMPONENT_MANIFEST_SHA256 = "aa" * 32
            return deepcopy(self.predecessor_receipt)

        with patch.object(
            candidate.owner_policy,
            "validate_presented_windows_owner_policy_contract",
            side_effect=side_effectful_parent,
        ) as parent:
            with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
                self._validate()
        parent.assert_not_called()
        self.assertFalse(touched["value"])

    def test_transitive_v3_artifact_hash_helper_patch_is_rejected_before_parent(self) -> None:
        invalid = deepcopy(self.predecessor_body)
        invalid["artifact_sha256"] = "aa" * 32
        invalid_raw = owner_policy.json_file_bytes(invalid)
        with patch.object(
            candidate.owner_policy,
            "_artifact_hash",
            return_value="aa" * 32,
        ) as helper:
            with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
                self._validate(predecessor_body_raw=invalid_raw)
        helper.assert_not_called()

    def test_owner_module_alias_drift_is_rejected_before_parent(self) -> None:
        with patch.object(candidate.owner_policy, "deployment", object()):
            with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
                self._validate()

    def test_deployment_uuid_module_alias_rebind_cannot_accept_invalid_uuid_chain(self) -> None:
        invalid_raw = self._invalid_wdac_uuid_predecessor_raw()

        class FakeUUID:
            called = False

            def __init__(self, value: str) -> None:
                type(self).called = True
                self.int = 1
                self.value = value

            def __str__(self) -> str:
                return self.value

        fake_module = SimpleNamespace(UUID=FakeUUID)
        with patch.object(
            candidate._OWNER_DEPLOYMENT_MODULE, "uuid", fake_module
        ):
            with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
                self._validate(predecessor_body_raw=invalid_raw)
        self.assertFalse(FakeUUID.called)

    def test_uuid_uuid_attribute_patch_cannot_accept_invalid_uuid_chain(self) -> None:
        invalid_raw = self._invalid_wdac_uuid_predecessor_raw()

        class FakeUUID:
            called = False

            def __init__(self, value: str) -> None:
                type(self).called = True
                self.int = 1
                self.value = value

            def __str__(self) -> str:
                return self.value

        uuid_module = candidate._OWNER_DEPLOYMENT_MODULE.uuid
        with patch.object(uuid_module, "UUID", FakeUUID):
            with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
                self._validate(predecessor_body_raw=invalid_raw)
        self.assertFalse(FakeUUID.called)

    def test_upstream_pin_validator_patch_cannot_bypass_local_pin_self_hash(self) -> None:
        bad_pin = deepcopy(self.pin)
        bad_pin["artifact_sha256"] = "aa" * 32
        with patch.object(
            candidate.preauth_v2,
            "_validate_pin",
            return_value=(bad_pin, b"x" * 32, b"y" * 32),
        ) as upstream:
            with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
                self._validate(pin_raw=candidate.json_file_bytes(bad_pin))
        upstream.assert_not_called()
        pin = deepcopy(self.pin)
        pin["artifact_sha256"] = "aa" * 32
        with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
            self._validate(pin_raw=candidate.json_file_bytes(pin))

    def test_signature_wrong_key_bitflip_high_s_and_domain_fail_closed(self) -> None:
        wrong_key = ec.generate_private_key(ec.SECP256R1())
        wrong_signature = self._signature(self.body, self.body_raw, key=wrong_key)
        high_s = deepcopy(self.signature)
        raw = base64.b64decode(high_s["signature_rs_base64"])
        s = int.from_bytes(raw[32:], "big")
        high_s["signature_rs_base64"] = base64.b64encode(
            raw[:32] + (candidate._P256_ORDER - s).to_bytes(32, "big")
        ).decode("ascii")
        high_s = candidate.with_artifact_hash(high_s)
        wrong_domain = deepcopy(self.signature)
        wrong_domain["domain"] = "wrong-domain"
        wrong_domain = candidate.with_artifact_hash(wrong_domain)
        bitflip = deepcopy(self.signature)
        bitflip_raw = bytearray(base64.b64decode(bitflip["signature_rs_base64"]))
        bitflip_raw[0] ^= 1
        bitflip["signature_rs_base64"] = base64.b64encode(bitflip_raw).decode("ascii")
        bitflip = candidate.with_artifact_hash(bitflip)
        for row in (wrong_signature, high_s, wrong_domain, bitflip):
            with self.subTest(domain=row["domain"]):
                with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
                    self._validate(signature=row)

    def test_bootstrap_spki_fingerprint_curve_and_encoding_are_strict(self) -> None:
        wrong = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        p384 = ec.generate_private_key(ec.SECP384R1()).public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        for raw in (wrong, p384, b"not-der"):
            with self.subTest(length=len(raw)):
                with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
                    self._validate(bootstrap_spki=raw)

    def test_ttl_and_revocation_floor_fail_closed(self) -> None:
        for changes in (
            {"max_preauthorization_ttl_seconds": 301},
            {"max_preauthorization_ttl_seconds": True},
            {"min_revocation_sequence": 0},
            {"min_revocation_sequence": True},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
                    self._validate(body=self._body(profile_changes=changes))

    def test_noncanonical_duplicate_bom_and_trailing_bytes_are_rejected(self) -> None:
        duplicate_body = self.body_raw.replace(
            b'{"artifact_sha256":', b'{"artifact_sha256":"' + b"0" * 64 + b'","artifact_sha256":', 1
        )
        variants = (
            {"policy_v4_body_bytes": self.body_raw[:-1]},
            {"policy_v4_body_bytes": b"\xef\xbb\xbf" + self.body_raw},
            {"policy_v4_body_bytes": duplicate_body},
            {"policy_v4_signature_bytes": self.signature_raw + b"\n"},
            {"packet_v2_public_key_pin_bytes": self.pin_raw + b" "},
        )
        base = {
            "predecessor_policy_v3_body_bytes": self.predecessor_body_raw,
            "predecessor_policy_v3_signature_bytes": self.predecessor_signature_raw,
            "packet_v2_public_key_pin_bytes": self.pin_raw,
            "policy_v4_body_bytes": self.body_raw,
            "policy_v4_signature_bytes": self.signature_raw,
            "bootstrap_public_key_spki_der": self.bootstrap_spki,
        }
        for override in variants:
            with self.subTest(field=tuple(override)):
                args = {**base, **override}
                with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
                    candidate.validate_presented_windows_owner_policy_v4_packet_v2_profile(**args)

    def test_dependency_drift_fails_before_parent_validation(self) -> None:
        with (
            patch.object(candidate.preauth_v2, "COMPONENT_MANIFEST_SHA256", "aa" * 32),
            patch.object(candidate.owner_policy, "validate_presented_windows_owner_policy_contract") as parent,
        ):
            with self.assertRaises(candidate.P0WindowsOwnerPolicyV4PacketV2ProfileError):
                self._validate()
        parent.assert_not_called()


if __name__ == "__main__":
    unittest.main()
