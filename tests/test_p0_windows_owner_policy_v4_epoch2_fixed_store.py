from __future__ import annotations

from copy import deepcopy
import base64
import hashlib
import inspect
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from llm_batch.grounding import (
    p0_windows_owner_policy_v4_epoch2_fixed_store as store,
)
from llm_batch.grounding import (
    p0_windows_owner_policy_v4_epoch2_fixed_store_parent_validator as parent,
)
from llm_batch.grounding import (
    p0_windows_owner_policy_v4_packet_v2_profile_contract as v4,
)
from tests import test_p0_windows_owner_policy_v4_packet_v2_profile_contract as v4_fixture_module


def _fixture() -> tuple[object, dict[str, bytes], dict[str, object]]:
    fixture = v4_fixture_module.WindowsOwnerPolicyV4PacketV2ProfileContractTests(
        "test_valid_signed_v4_profile_is_component_only_no_go"
    )
    fixture.setUp()
    raws = {
        "predecessor_policy_v3_body": fixture.predecessor_body_raw,
        "predecessor_policy_v3_signature": fixture.predecessor_signature_raw,
        "packet_v2_public_key_pin": fixture.pin_raw,
        "policy_v4_body": fixture.body_raw,
        "policy_v4_signature": fixture.signature_raw,
        "bootstrap_public_key_spki": fixture.bootstrap_spki,
    }
    child = v4.validate_presented_windows_owner_policy_v4_packet_v2_profile(
        predecessor_policy_v3_body_bytes=fixture.predecessor_body_raw,
        predecessor_policy_v3_signature_bytes=fixture.predecessor_signature_raw,
        packet_v2_public_key_pin_bytes=fixture.pin_raw,
        policy_v4_body_bytes=fixture.body_raw,
        policy_v4_signature_bytes=fixture.signature_raw,
        bootstrap_public_key_spki_der=fixture.bootstrap_spki,
    )
    return fixture, raws, child


def _write_store(program_data: str, raws: dict[str, bytes]) -> dict[str, str]:
    paths = store._paths(program_data)
    for role in store.DIRECTORY_ROLES:
        Path(paths[role]).mkdir(parents=True, exist_ok=True)
    for role, raw in raws.items():
        Path(paths[role]).write_bytes(raw)
    return paths


class V4Epoch2FixedStoreParentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture, self.raws, self.child = _fixture()

    def test_valid_six_member_parent_replay_is_pure_no_go(self) -> None:
        receipt = parent.validate_v4_epoch2_fixed_store_parent_replay(
            raw_bundle=self.raws, child_receipt=self.child
        )
        self.assertEqual(tuple(receipt), parent._RECEIPT_FIELDS)
        self.assertEqual(receipt["predecessor_policy_epoch"], 1)
        self.assertEqual(receipt["policy_v4_epoch"], 2)
        self.assertEqual(
            receipt["bootstrap_public_key_spki_bytes_sha256"],
            hashlib.sha256(self.fixture.bootstrap_spki).hexdigest(),
        )
        self.assertTrue(all(receipt[field] is True for field in parent._TRUE_FIELDS))
        self.assertTrue(all(receipt[field] is False for field in parent._FALSE_FIELDS))
        material = dict(receipt)
        declared = material.pop("receipt_sha256")
        self.assertEqual(declared, parent.canonical_sha256(material))

    def test_parent_does_not_import_or_call_v4_producer(self) -> None:
        source = inspect.getsource(parent)
        self.assertNotIn("p0_windows_owner_policy_v4_packet_v2_profile_contract", source)
        self.assertNotIn(
            "validate_presented_windows_owner_policy_v4_packet_v2_profile",
            source,
        )
        with mock.patch.object(
            v4, "validate_presented_windows_owner_policy_v4_packet_v2_profile"
        ) as producer:
            parent.validate_v4_epoch2_fixed_store_parent_replay(
                raw_bundle=self.raws, child_receipt=self.child
            )
        producer.assert_not_called()

    def test_raw_inventory_missing_extra_and_order_drift_fail(self) -> None:
        variants = []
        missing = dict(self.raws)
        missing.pop("policy_v4_signature")
        variants.append(missing)
        variants.append({**self.raws, "extra": b"x"})
        variants.append(dict(reversed(tuple(self.raws.items()))))
        for value in variants:
            with self.subTest(keys=tuple(value)):
                with self.assertRaises(
                    parent.P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError
                ):
                    parent.validate_v4_epoch2_fixed_store_parent_replay(
                        raw_bundle=value, child_receipt=self.child
                    )

    def test_raw_bitflip_and_epoch_substitution_fail(self) -> None:
        bitflip = dict(self.raws)
        bitflip["bootstrap_public_key_spki"] = self.raws[
            "bootstrap_public_key_spki"
        ][:-1] + bytes([self.raws["bootstrap_public_key_spki"][-1] ^ 1])
        with self.assertRaises(parent.P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError):
            parent.validate_v4_epoch2_fixed_store_parent_replay(
                raw_bundle=bitflip, child_receipt=self.child
            )

        body = json.loads(self.raws["policy_v4_body"].decode("utf-8"))
        body["policy_epoch"] = 3
        body.pop("artifact_sha256")
        body["artifact_sha256"] = parent.canonical_sha256(body)
        epoch = dict(self.raws)
        epoch["policy_v4_body"] = parent.canonical_bytes(body) + b"\n"
        with self.assertRaises(parent.P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError):
            parent.validate_v4_epoch2_fixed_store_parent_replay(
                raw_bundle=epoch, child_receipt=self.child
            )

    def test_forged_resealed_child_truth_hash_and_order_fail(self) -> None:
        truth = deepcopy(self.child)
        truth["trusted_time_verified"] = True
        material = dict(truth)
        material.pop("receipt_sha256")
        truth["receipt_sha256"] = parent.canonical_sha256(material)
        bad_hash = deepcopy(self.child)
        bad_hash["receipt_sha256"] = "aa" * 32
        reordered = dict(reversed(tuple(self.child.items())))
        for value in (truth, bad_hash, reordered):
            with self.assertRaises(parent.P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError):
                parent.validate_v4_epoch2_fixed_store_parent_replay(
                    raw_bundle=self.raws, child_receipt=value
                )

    def test_parent_private_helper_and_module_attribute_tamper_fail(self) -> None:
        with mock.patch.object(parent, "_strict_child", lambda value: value):
            with self.assertRaises(parent.P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError):
                parent.validate_v4_epoch2_fixed_store_parent_replay(
                    raw_bundle=self.raws, child_receipt=self.child
                )
        with mock.patch.object(parent.json, "loads", lambda *_a, **_k: {}):
            with self.assertRaises(parent.P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError):
                parent.validate_v4_epoch2_fixed_store_parent_replay(
                    raw_bundle=self.raws, child_receipt=self.child
                )

    def test_parent_component_manifest_is_literal_recomputed(self) -> None:
        self.assertEqual(
            parent.COMPONENT_MANIFEST_SHA256,
            parent.EXPECTED_COMPONENT_MANIFEST_SHA256,
        )
        self.assertEqual(
            parent.COMPONENT_MANIFEST_SHA256,
            parent.canonical_sha256(parent.COMPONENT_MANIFEST),
        )
        self.assertEqual(
            parent.SEMANTIC_CONTRACT_SHA256,
            parent.EXPECTED_SEMANTIC_CONTRACT_SHA256,
        )

    def test_parent_independently_rejects_forged_v4_signature_math(self) -> None:
        signature = json.loads(self.raws["policy_v4_signature"].decode("utf-8"))
        signature["signature_rs_base64"] = base64.b64encode(
            (1).to_bytes(32, "big") + (1).to_bytes(32, "big")
        ).decode("ascii")
        signature.pop("artifact_sha256")
        signature["artifact_sha256"] = parent.canonical_sha256(signature)
        raws = dict(self.raws)
        raws["policy_v4_signature"] = parent.canonical_bytes(signature) + b"\n"
        child = deepcopy(self.child)
        child["policy_v4_signature_bytes_sha256"] = hashlib.sha256(
            raws["policy_v4_signature"]
        ).hexdigest()
        child["policy_v4_signature_artifact_sha256"] = signature[
            "artifact_sha256"
        ]
        material = dict(child)
        material.pop("receipt_sha256")
        child["receipt_sha256"] = parent.canonical_sha256(material)
        with self.assertRaises(parent.P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError):
            parent.validate_v4_epoch2_fixed_store_parent_replay(
                raw_bundle=raws, child_receipt=child
            )

    def test_parent_rejects_effect_hash_and_numeric_type_confusion(self) -> None:
        variants = []
        for field, value in (
            ("operational_effect", "APPLY_NOW"),
            ("signature_input_sha256", "not-a-sha"),
            ("policy_epoch", 2.0),
            ("packet_v2_key_epoch", float(self.child["packet_v2_key_epoch"])),
            (
                "max_preauthorization_ttl_seconds",
                float(self.child["max_preauthorization_ttl_seconds"]),
            ),
            (
                "min_revocation_sequence",
                float(self.child["min_revocation_sequence"]),
            ),
        ):
            altered = deepcopy(self.child)
            altered[field] = value
            material = dict(altered)
            material.pop("receipt_sha256")
            altered["receipt_sha256"] = parent.canonical_sha256(material)
            variants.append((field, altered))
        for field, altered in variants:
            with self.subTest(field=field):
                with self.assertRaises(
                    parent.P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError
                ):
                    parent.validate_v4_epoch2_fixed_store_parent_replay(
                        raw_bundle=self.raws, child_receipt=altered
                    )

    def test_parent_epoch_constant_drift_fails_integrity(self) -> None:
        with mock.patch.object(parent, "EXPECTED_POLICY_EPOCH", 10):
            with self.assertRaises(parent.P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError):
                parent.validate_v4_epoch2_fixed_store_parent_replay(
                    raw_bundle=self.raws, child_receipt=self.child
                )

    def test_parent_base64_codec_attribute_tamper_fails_integrity(self) -> None:
        with mock.patch.object(parent.base64, "b64decode", lambda *_a, **_k: b"x"), \
                mock.patch.object(parent.base64, "b64encode", lambda *_a, **_k: b"x"):
            with self.assertRaises(parent.P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError):
                parent.validate_v4_epoch2_fixed_store_parent_replay(
                    raw_bundle=self.raws, child_receipt=self.child
                )

    def test_parent_rejects_malformed_v3_acl_and_v3_helper_tamper(self) -> None:
        malformed = deepcopy(self.fixture.predecessor_body)
        malformed["object_policies"][0]["security_template"]["ordered_aces"][
            0
        ]["access_mask_decimal"] = "0"
        malformed.pop("artifact_sha256")
        malformed["artifact_sha256"] = parent.canonical_sha256(malformed)
        raws = dict(self.raws)
        raws["predecessor_policy_v3_body"] = parent.canonical_bytes(malformed) + b"\n"
        with self.assertRaises(parent.P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError):
            parent.validate_v4_epoch2_fixed_store_parent_replay(
                raw_bundle=raws, child_receipt=self.child
            )
        with mock.patch.object(parent.owner_v3, "_validate_policy_body", lambda _raw: {}):
            with self.assertRaises(parent.P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError):
                parent.validate_v4_epoch2_fixed_store_parent_replay(
                    raw_bundle=self.raws, child_receipt=self.child
                )
        with mock.patch.object(
            parent.owner_v3,
            "_BODY_KEYS_V3",
            parent.owner_v3._BODY_KEYS_V3 | {"evil"},
        ):
            with self.assertRaises(parent.P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError):
                parent.validate_v4_epoch2_fixed_store_parent_replay(
                    raw_bundle=self.raws, child_receipt=self.child
                )
        with mock.patch.object(
            parent.owner_v3.deployment.uuid,
            "UUID",
            lambda value: type("FakeUUID", (), {"int": 1, "__str__": lambda self: value})(),
        ):
            with self.assertRaises(parent.P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError):
                parent.validate_v4_epoch2_fixed_store_parent_replay(
                    raw_bundle=self.raws, child_receipt=self.child
                )


@unittest.skipUnless(os.name == "nt", "Windows held-handle store tests")
class V4Epoch2FixedStoreWindowsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture, self.raws, self.child = _fixture()

    def _positive(self, root: str) -> dict[str, object]:
        # Fresh files can cause one delayed NTFS/AV metadata notification.  A
        # failed first interval is never accepted; a new full observation must
        # succeed from scratch.
        first_error: BaseException | None = None
        for _attempt in range(2):
            try:
                return store._observe_at_program_data(root)
            except store.P0WindowsOwnerPolicyV4Epoch2FixedStoreError as exc:
                first_error = exc
                if "directory watch completed before interval end: DELIVERED" not in str(exc):
                    raise
        assert first_error is not None
        raise first_error

    def test_layout_component_manifest_and_zero_arg_api(self) -> None:
        self.assertEqual(store.COMPILED_POLICY_EPOCH, 2)
        self.assertEqual(store.GENERATION_COMPONENT, "00000000000000000002")
        self.assertEqual(len(store.FILE_ROLES), 6)
        self.assertEqual(len(store.ALL_ROLES), 13)
        self.assertEqual(store.AGGREGATE_MEMBER_CAP_BYTES, 705_024)
        self.assertEqual(
            store.FIXED_MEMBER_CONTRACT_SHA256,
            store.EXPECTED_FIXED_MEMBER_CONTRACT_SHA256,
        )
        self.assertEqual(
            store.COMPONENT_MANIFEST_SHA256,
            store.EXPECTED_COMPONENT_MANIFEST_SHA256,
        )
        self.assertEqual(
            store.SEMANTIC_CONTRACT_SHA256,
            store.EXPECTED_SEMANTIC_CONTRACT_SHA256,
        )
        self.assertEqual(
            tuple(inspect.signature(
                store.observe_fixed_windows_owner_policy_v4_epoch2_store
            ).parameters),
            (),
        )

    def test_current_missing_store_is_structured_deterministic_no_go(self) -> None:
        root = Path(os.environ["ProgramData"]).joinpath(*store.FIXED_STORE_SUFFIX)
        if root.exists():
            self.skipTest("current host has an externally provisioned V4 store")
        first = store.observe_fixed_windows_owner_policy_v4_epoch2_store()
        second = store.observe_fixed_windows_owner_policy_v4_epoch2_store()
        self.assertEqual(first, second)
        self.assertEqual(first["failure_stage"], "FIXED_STORE")
        self.assertEqual(first["decision"], "NO_GO")
        self.assertEqual(tuple(first), store._RECEIPT_FIELDS)
        self.assertTrue(all(first[field] is False for field in store._AUTHORITY_FALSE_FIELDS))
        self.assertEqual(first["credited_actual_source_claim_count"], 0)
        self.assertEqual(first["credited_actual_a_context_review_count"], 0)

    def test_positive_temp_store_binds_handles_acl_watch_child_and_parent(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            _write_store(root, self.raws)
            receipt = self._positive(root)
        self.assertEqual(receipt["failure_stage"], "EXTERNAL_STATE")
        self.assertEqual(receipt["v4_parent_execution_count"], 1)
        self.assertEqual(receipt["role_handle_count"], len(store.ALL_ROLES))
        self.assertEqual(
            set(receipt["member_raw_sha256_by_role"]), set(store.FILE_ROLES)
        )
        self.assertTrue(
            all(receipt[field] is True for field in store._STRUCTURAL_TRUE_FIELDS)
        )
        self.assertTrue(
            all(receipt[field] is False for field in store._AUTHORITY_FALSE_FIELDS)
        )
        self.assertEqual(
            receipt["parent_replay_receipt"]["child_receipt_declared_sha256"],
            receipt["v4_contract_receipt_declared_sha256"],
        )

    def test_missing_extra_and_generation_substitution_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            paths = _write_store(root, self.raws)
            Path(paths["policy_v4_signature"]).unlink()
            with self.assertRaises(store.P0WindowsOwnerPolicyV4Epoch2FixedStoreError):
                store._observe_at_program_data(root)
        with tempfile.TemporaryDirectory() as root:
            paths = _write_store(root, self.raws)
            Path(paths["generation_directory"], "extra.bin").write_bytes(b"x")
            with self.assertRaises(store.P0WindowsOwnerPolicyV4Epoch2FixedStoreError):
                store._observe_at_program_data(root)
        with tempfile.TemporaryDirectory() as root:
            paths = _write_store(root, self.raws)
            generation = Path(paths["generation_directory"])
            generation.rename(generation.with_name("00000000000000000003"))
            with self.assertRaises(store.P0WindowsOwnerPolicyV4Epoch2FixedStoreError):
                store._observe_at_program_data(root)

    def test_parent_alias_helper_and_v4_callable_tamper_are_component_integrity_no_go(self) -> None:
        attacks = (
            mock.patch.object(store.fixed_win, "_read_handle_exact", lambda *_a: b""),
            mock.patch.object(store, "_paths", lambda _value: {}),
            mock.patch.object(store.fixed_win, "_Win32", object),
            mock.patch.object(parent, "_strict_child", lambda value: value),
            mock.patch.object(v4, "validate_presented_windows_owner_policy_v4_packet_v2_profile", lambda **_k: {}),
        )
        for attack in attacks:
            with self.subTest(attack=type(attack).__name__), attack:
                with self.assertRaises(
                    store.P0WindowsOwnerPolicyV4Epoch2FixedStoreError
                ):
                    store.observe_fixed_windows_owner_policy_v4_epoch2_store()

    def test_in_place_v4_code_semantic_and_failure_helper_tamper_raise(self) -> None:
        validator = v4.validate_presented_windows_owner_policy_v4_packet_v2_profile
        original_code = validator.__code__

        def forged(**_kwargs: object) -> dict[str, object]:
            return {}

        try:
            validator.__code__ = forged.__code__
            with self.assertRaises(store.P0WindowsOwnerPolicyV4Epoch2FixedStoreError):
                store.observe_fixed_windows_owner_policy_v4_epoch2_store()
        finally:
            validator.__code__ = original_code

        with mock.patch.object(store, "_DIRECTORY_INVENTORIES", {}):
            with self.assertRaises(store.P0WindowsOwnerPolicyV4Epoch2FixedStoreError):
                store.observe_fixed_windows_owner_policy_v4_epoch2_store()

        with mock.patch.object(
            store,
            "_failure_receipt",
            lambda *, stage: {
                "failure_stage": stage,
                "store_observation_succeeded": True,
                "owner_authority_verified": True,
            },
        ):
            with self.assertRaises(store.P0WindowsOwnerPolicyV4Epoch2FixedStoreError):
                store.observe_fixed_windows_owner_policy_v4_epoch2_store()

    def test_no_network_subprocess_write_or_clock_selector_in_public_component(self) -> None:
        source = inspect.getsource(store)
        for forbidden in (
            "subprocess",
            "requests",
            "urlopen",
            "socket",
            "time.time",
            "datetime.now",
            "write_bytes(",
            "write_text(",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
