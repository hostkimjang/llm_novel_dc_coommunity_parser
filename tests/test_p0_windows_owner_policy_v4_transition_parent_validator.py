from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import inspect
import unittest

from cryptography.hazmat.primitives.asymmetric import ec

from llm_batch.grounding import p0_external_owner_asymmetric_signature as asymmetric
from llm_batch.grounding import p0_windows_bootstrap_policy_signature_candidate as bootstrap
from llm_batch.grounding import p0_windows_owner_policy_contract as owner
from llm_batch.grounding import p0_windows_owner_policy_v4_epoch2_fixed_store_parent_validator as v4_parent
from llm_batch.grounding import p0_windows_owner_policy_v4_packet_v2_profile_contract as v4
from llm_batch.grounding import p0_windows_owner_policy_v4_transition_parent_validator as parent
from tests import test_p0_windows_owner_policy_contract as v1_fixture
from tests import test_p0_windows_owner_policy_v3 as v3_fixture
from tests import test_p0_windows_owner_policy_v4_packet_v2_profile_contract as v4_fixture


def _rehash(value: dict[str, object]) -> dict[str, object]:
    return v1_fixture._rehash(value)


def _fixture() -> tuple[object, dict[str, bytes], dict[str, object], dict[str, object]]:
    fixture = v4_fixture.WindowsOwnerPolicyV4PacketV2ProfileContractTests(
        "test_valid_signed_v4_profile_is_component_only_no_go"
    )
    fixture.setUp()
    operational_private = ec.generate_private_key(ec.SECP256R1())
    numbers = operational_private.public_key().public_numbers()
    x = numbers.x.to_bytes(32, "big")
    y = numbers.y.to_bytes(32, "big")
    x64, y64 = base64.b64encode(x).decode(), base64.b64encode(y).decode()
    fingerprint = asymmetric.public_key_fingerprint_sha256(
        public_key_x_base64=x64, public_key_y_base64=y64
    )
    body = deepcopy(fixture.predecessor_body)
    body["operational_key"] = {
        "key_id": "transition-operational-key-001", "key_epoch": 1,
        "algorithm": asymmetric.ALGORITHM,
        "public_key_fingerprint_sha256": fingerprint,
        "pin_bytes_sha256": "0" * 64, "pin_artifact_sha256": "0" * 64,
        "allowed_signature_domains": [asymmetric.SIGNATURE_DOMAIN],
    }
    body["operational_key_projection_sha256"] = owner.derive_operational_key_projection_sha256(body["operational_key"])
    body["owner_anchor_sha256"] = v3_fixture._derive_v3_anchor(body)
    pin = {
        "schema_version": asymmetric.PUBLIC_KEY_PIN_SCHEMA,
        "record_origin": asymmetric.PRESENTED_PIN_ORIGIN,
        "trust_domain": body["trust_domain"], "project_id": body["project_id"],
        "environment": body["environment"], "purpose": asymmetric.SIGNATURE_PURPOSE,
        "key_id": body["operational_key"]["key_id"],
        "key_epoch": body["operational_key"]["key_epoch"],
        "algorithm": asymmetric.ALGORITHM, "curve": asymmetric.CURVE,
        "coordinate_encoding": asymmetric.COORDINATE_ENCODING,
        "fingerprint_encoding": asymmetric.FINGERPRINT_ENCODING,
        "public_key_x_base64": x64, "public_key_y_base64": y64,
        "public_key_fingerprint_sha256": fingerprint,
        "owner_principal_sha256": body["owner_principal_sha256"],
        "owner_anchor_sha256": body["owner_anchor_sha256"],
        "allowed_signature_domains": [asymmetric.SIGNATURE_DOMAIN],
    }
    pin = _rehash(pin)
    pin_raw = asymmetric.json_file_bytes(pin)
    body["operational_key"]["pin_bytes_sha256"] = hashlib.sha256(pin_raw).hexdigest()
    body["operational_key"]["pin_artifact_sha256"] = pin["artifact_sha256"]
    body["operational_key_projection_sha256"] = owner.derive_operational_key_projection_sha256(body["operational_key"])
    body["owner_anchor_sha256"] = v3_fixture._derive_v3_anchor(body)
    body = _rehash(body)
    body_raw = owner.json_file_bytes(body)
    signature = v3_fixture._v3_signature(body)
    material = bootstrap.canonical_bytes(bootstrap._signature_material(signature))
    signature["signature_rs_base64"] = base64.b64encode(
        v4_fixture._low_s_sign(fixture.bootstrap_private, material)
    ).decode()
    signature = _rehash(signature)
    signature_raw = owner.json_file_bytes(signature)
    fixture.predecessor_body = body
    fixture.predecessor_body_raw = body_raw
    fixture.predecessor_signature = signature
    fixture.predecessor_signature_raw = signature_raw
    fixture.predecessor_receipt = owner.validate_presented_windows_owner_policy_contract(
        policy_body_bytes=body_raw, policy_signature_bytes=signature_raw
    )
    fixture.body = fixture._body()
    fixture.body_raw = v4.json_file_bytes(fixture.body)
    fixture.signature = fixture._signature(fixture.body, fixture.body_raw)
    fixture.signature_raw = v4.json_file_bytes(fixture.signature)
    v4_raws = {
        "predecessor_policy_v3_body": body_raw,
        "predecessor_policy_v3_signature": signature_raw,
        "packet_v2_public_key_pin": fixture.pin_raw,
        "policy_v4_body": fixture.body_raw,
        "policy_v4_signature": fixture.signature_raw,
        "bootstrap_public_key_spki": fixture.bootstrap_spki,
    }
    child = v4.validate_presented_windows_owner_policy_v4_packet_v2_profile(
        predecessor_policy_v3_body_bytes=body_raw,
        predecessor_policy_v3_signature_bytes=signature_raw,
        packet_v2_public_key_pin_bytes=fixture.pin_raw,
        policy_v4_body_bytes=fixture.body_raw,
        policy_v4_signature_bytes=fixture.signature_raw,
        bootstrap_public_key_spki_der=fixture.bootstrap_spki,
    )
    replay = v4_parent.validate_v4_epoch2_fixed_store_parent_replay(
        raw_bundle=v4_raws, child_receipt=child
    )
    raws = {
        "live_v3_policy_body": body_raw,
        "live_v3_policy_signature": signature_raw,
        "live_v3_operational_pin": pin_raw,
        **v4_raws,
    }
    return fixture, raws, child, replay


class TransitionParentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture, self.raws, self.child, self.replay = _fixture()

    def validate(self, raws=None, child=None, replay=None):
        return parent.validate_windows_owner_policy_v4_transition_parent(
            raw_bundle=raws or self.raws,
            v4_child_receipt=child or self.child,
            v4_parent_receipt=replay or self.replay,
        )

    def test_valid_nine_member_transition_is_component_only(self) -> None:
        receipt = self.validate()
        self.assertEqual(receipt["predecessor_policy_epoch"], 1)
        self.assertEqual(receipt["policy_v4_epoch"], 2)
        self.assertTrue(all(receipt[field] is True for field in parent._TRUE_FIELDS))
        self.assertTrue(all(receipt[field] is False for field in parent._FALSE_FIELDS))

    def test_public_api_has_three_keyword_only_inputs(self) -> None:
        signature = inspect.signature(parent.validate_windows_owner_policy_v4_transition_parent)
        self.assertEqual(list(signature.parameters), [
            "raw_bundle", "v4_child_receipt", "v4_parent_receipt"
        ])

    def test_live_embedded_mismatch_fails(self) -> None:
        raws = dict(self.raws)
        raws["live_v3_policy_body"] += b"x"
        with self.assertRaises(parent.P0WindowsOwnerPolicyV4TransitionParentError):
            self.validate(raws=raws)

    def test_reversed_parent_receipt_fails(self) -> None:
        reversed_receipt = dict(reversed(tuple(self.replay.items())))
        with self.assertRaises(parent.P0WindowsOwnerPolicyV4TransitionParentError):
            self.validate(replay=reversed_receipt)

    def test_resealed_v4_parent_static_or_child_binding_mutation_fails(self) -> None:
        mutations = (
            ("gate_status", "GO"),
            ("operational_effect", "APPLY"),
            ("component_manifest_sha256", "aa" * 32),
            ("policy_id", "attacker-policy"),
            ("packet_v2_key_epoch", 2.0),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                forged = dict(self.replay)
                forged[field] = value
                forged = _rehash(forged)
                with self.assertRaises(parent.P0WindowsOwnerPolicyV4TransitionParentError):
                    self.validate(replay=forged)

    def test_resealed_parent_hashes_cannot_bless_tampered_v4_raw(self) -> None:
        raws = dict(self.raws)
        raws["policy_v4_body"] += b"x"
        forged = dict(self.replay)
        hashes = {
            role: hashlib.sha256(raws[role]).hexdigest()
            for role in v4_parent.RAW_ROLES
        }
        forged["raw_sha256_by_role"] = hashes
        forged["raw_bundle_projection_sha256"] = parent.canonical_sha256(hashes)
        forged = _rehash(forged)
        with self.assertRaises(parent.P0WindowsOwnerPolicyV4TransitionParentError):
            self.validate(raws=raws, replay=forged)

    def test_operational_pin_extra_resealed_fails(self) -> None:
        pin = parent._parse(self.raws["live_v3_operational_pin"], "pin")
        pin["attacker"] = True
        pin = _rehash(pin)
        raws = dict(self.raws)
        raws["live_v3_operational_pin"] = asymmetric.json_file_bytes(pin)
        with self.assertRaises(parent.P0WindowsOwnerPolicyV4TransitionParentError):
            self.validate(raws=raws)

    def test_operational_pin_scope_mismatch_fails_even_when_body_hash_is_updated(self) -> None:
        pin = parent._parse(self.raws["live_v3_operational_pin"], "pin")
        pin["trust_domain"] = "attacker.example"
        pin = _rehash(pin)
        pin_raw = asymmetric.json_file_bytes(pin)
        body = deepcopy(self.fixture.predecessor_body)
        body["operational_key"]["pin_bytes_sha256"] = hashlib.sha256(pin_raw).hexdigest()
        body["operational_key"]["pin_artifact_sha256"] = pin["artifact_sha256"]
        body = _rehash(body)
        body_raw = owner.json_file_bytes(body)
        signature = v3_fixture._v3_signature(body)
        material = bootstrap.canonical_bytes(bootstrap._signature_material(signature))
        signature["signature_rs_base64"] = base64.b64encode(
            v4_fixture._low_s_sign(self.fixture.bootstrap_private, material)
        ).decode()
        signature = _rehash(signature)
        signature_raw = owner.json_file_bytes(signature)
        with self.assertRaises(parent.P0WindowsOwnerPolicyV4TransitionParentError):
            parent._verify_v3_math(
                body_raw=body_raw,
                signature_raw=signature_raw,
                pin_raw=pin_raw,
                spki=self.raws["bootstrap_public_key_spki"],
            )

    def test_high_s_v3_signature_fails(self) -> None:
        signature = parent._parse(self.raws["live_v3_policy_signature"], "sig")
        raw = base64.b64decode(signature["signature_rs_base64"])
        s = int.from_bytes(raw[32:], "big")
        signature["signature_rs_base64"] = base64.b64encode(
            raw[:32] + (parent.P256_ORDER - s).to_bytes(32, "big")
        ).decode()
        signature = _rehash(signature)
        changed = owner.json_file_bytes(signature)
        raws = dict(self.raws)
        raws["live_v3_policy_signature"] = changed
        raws["predecessor_policy_v3_signature"] = changed
        with self.assertRaises(parent.P0WindowsOwnerPolicyV4TransitionParentError):
            self.validate(raws=raws)

    def test_private_v3_math_helper_code_mutation_fails_closed(self) -> None:
        original = parent._verify_v3_math.__code__
        def forged(*, body_raw, signature_raw, pin_raw, spki):
            return "aa" * 32, "owner-policy-001", "bb" * 32
        try:
            parent._verify_v3_math.__code__ = forged.__code__
            with self.assertRaises(parent.P0WindowsOwnerPolicyV4TransitionParentError):
                self.validate()
        finally:
            parent._verify_v3_math.__code__ = original

    def test_v4_parent_replay_dependency_code_mutation_fails_closed(self) -> None:
        original = v4_parent.validate_v4_epoch2_fixed_store_parent_replay.__code__
        def forged(*, raw_bundle, child_receipt):
            return child_receipt
        try:
            v4_parent.validate_v4_epoch2_fixed_store_parent_replay.__code__ = forged.__code__
            with self.assertRaises(parent.P0WindowsOwnerPolicyV4TransitionParentError):
                self.validate()
        finally:
            v4_parent.validate_v4_epoch2_fixed_store_parent_replay.__code__ = original


if __name__ == "__main__":
    unittest.main()
