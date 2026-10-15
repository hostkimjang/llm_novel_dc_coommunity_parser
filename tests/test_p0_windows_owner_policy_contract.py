from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import inspect
import json
import os
from pathlib import Path
import tempfile
import unittest

from llm_batch.grounding import p0_windows_binary_acl_projection as binary_acl
from llm_batch.grounding import p0_windows_owner_policy_contract as policy


_VOLUME = "\\\\?\\Volume{12345678-1234-1234-1234-1234567890ab}"
_OWNER_SID = "S-1-5-18"
_VERIFIER_SID = "S-1-5-21-111-222-333-1001"
_GROUP_SID = "S-1-5-18"


def _rehash(value: dict[str, object]) -> dict[str, object]:
    value["artifact_sha256"] = policy.canonical_sha256(
        {key: item for key, item in value.items() if key != "artifact_sha256"}
    )
    return value


def _security(role: str) -> dict[str, object]:
    reader_mask = (
        policy.DIRECTORY_READER_MASK
        if role in policy.OBJECT_ROLES[:5]
        else policy.FILE_READER_MASK
    )
    return {
        "owner_sid": _OWNER_SID,
        "group_sid": _GROUP_SID,
        "dacl_present": True,
        "dacl_null": False,
        "dacl_protected": True,
        "dacl_defaulted": False,
        "dacl_auto_inherited": False,
        "dacl_auto_inherit_req": False,
        "ordered_aces": [
            {
                "ace_type": policy.ACCESS_ALLOWED_ACE_TYPE,
                "ace_flags": 0,
                "access_mask_decimal": str(policy.FILE_ALL_ACCESS),
                "sid": _OWNER_SID,
            },
            {
                "ace_type": policy.ACCESS_ALLOWED_ACE_TYPE,
                "ace_flags": 0,
                "access_mask_decimal": str(reader_mask),
                "sid": _VERIFIER_SID,
            },
        ],
    }


def _object_policies(epoch: int = 1) -> list[dict[str, object]]:
    store = f"{_VOLUME}\\ProgramData\\llm-novel-dc\\p0-owner-policy-v1"
    generation = f"{store}\\generations\\{epoch:020d}"
    paths = {
        "policy_store": store,
        "generations_directory": f"{store}\\generations",
        "generation_directory": generation,
        "policy_directory": f"{generation}\\policy",
        "pin_directory": f"{generation}\\pin",
        "policy_body_file": f"{generation}\\policy\\body.json",
        "policy_signature_file": f"{generation}\\policy\\signature.json",
        "public_key_pin_file": (
            f"{generation}\\pin\\p0_external_owner_public_key_pin_v1.json"
        ),
    }
    return [
        {
            "role": role,
            "object_kind": (
                "DIRECTORY" if role in policy.OBJECT_ROLES[:5] else "FILE"
            ),
            "final_volume_guid_path": paths[role],
            "volume_serial_decimal": "123456789",
            "file_id_128_hex": f"{index + 1:032x}",
            "security_template": _security(role),
        }
        for index, role in enumerate(policy.OBJECT_ROLES)
    ]


def _body(epoch: int = 1) -> dict[str, object]:
    operational_key = {
        "key_id": "owner-operational-key-001",
        "key_epoch": 1,
        "algorithm": policy.OPERATIONAL_KEY_ALGORITHM,
        "public_key_fingerprint_sha256": "1" * 64,
        "pin_bytes_sha256": "2" * 64,
        "pin_artifact_sha256": "3" * 64,
        "allowed_signature_domains": [
            policy.OPERATIONAL_SIGNATURE_DOMAIN
        ],
    }
    object_policies = _object_policies(epoch)
    owner_principal = policy.derive_owner_principal_sha256(_OWNER_SID)
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
    predecessor = None if epoch == 1 else "a" * 64
    bootstrap_fingerprint = "4" * 64
    scope = {
        "store_id": "machine-owner-policy-store-001",
        "project_id": "llm-novel-dc-community-parser",
        "trust_domain": "local-windows-owner",
        "environment": "controlled-fixture",
        "purpose": "p0-external-owner-policy",
        "bootstrap_key_id": "offline-bootstrap-key-001",
    }
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
            "policy_id": "owner-policy-001",
            "policy_epoch": epoch,
            "predecessor_policy_bytes_sha256": predecessor,
            **scope,
            "bootstrap_public_key_fingerprint_sha256": bootstrap_fingerprint,
            "owner_principal_sha256": owner_principal,
            "verifier_sid": _VERIFIER_SID,
            "object_identity_projection_sha256": object_identity_hash,
            "acl_template_sha256": acl_hash,
            "operational_key_projection_sha256": key_hash,
            "min_revocation_sequence": 1,
            "lifecycle_status": "ACTIVE",
        }
    )
    return _rehash(
        {
            "schema_version": policy.POLICY_BODY_SCHEMA,
            "record_origin": policy.POLICY_ORIGIN,
            "domain": policy.POLICY_DOMAIN,
            "policy_id": "owner-policy-001",
            "policy_epoch": epoch,
            "predecessor_policy_bytes_sha256": predecessor,
            **scope,
            "bootstrap_public_key_fingerprint_sha256": bootstrap_fingerprint,
            "owner_sid": _OWNER_SID,
            "verifier_sid": _VERIFIER_SID,
            "object_policies": object_policies,
            "operational_key": operational_key,
            "min_revocation_sequence": 1,
            "lifecycle_status": "ACTIVE",
            "owner_principal_sha256": owner_principal,
            "acl_template_sha256": acl_hash,
            "operational_key_projection_sha256": key_hash,
            "owner_anchor_sha256": anchor,
            "artifact_sha256": "0" * 64,
        }
    )


def _signature(body: dict[str, object]) -> dict[str, object]:
    body_bytes = policy.json_file_bytes(body)
    raw_signature = (1).to_bytes(32, "big") + (2).to_bytes(32, "big")
    return _rehash(
        {
            "schema_version": policy.POLICY_SIGNATURE_SCHEMA,
            "record_origin": policy.SIGNATURE_ORIGIN,
            "domain": policy.SIGNATURE_DOMAIN,
            "policy_id": body["policy_id"],
            "policy_epoch": body["policy_epoch"],
            "bootstrap_key_id": body["bootstrap_key_id"],
            "bootstrap_public_key_fingerprint_sha256": body[
                "bootstrap_public_key_fingerprint_sha256"
            ],
            "policy_body_bytes_sha256": hashlib.sha256(body_bytes).hexdigest(),
            "algorithm": policy.BOOTSTRAP_SIGNATURE_ALGORITHM,
            "signature_rs_base64": base64.b64encode(raw_signature).decode(
                "ascii"
            ),
            "artifact_sha256": "0" * 64,
        }
    )


def _contract_bytes(
    body: dict[str, object], signature: dict[str, object] | None = None
) -> tuple[bytes, bytes]:
    _rehash(body)
    body_bytes = policy.json_file_bytes(body)
    signature = deepcopy(signature) if signature is not None else _signature(body)
    signature["policy_body_bytes_sha256"] = hashlib.sha256(body_bytes).hexdigest()
    signature["policy_id"] = body["policy_id"]
    signature["policy_epoch"] = body["policy_epoch"]
    signature["bootstrap_key_id"] = body["bootstrap_key_id"]
    signature["bootstrap_public_key_fingerprint_sha256"] = body[
        "bootstrap_public_key_fingerprint_sha256"
    ]
    _rehash(signature)
    return body_bytes, policy.json_file_bytes(signature)


class WindowsOwnerPolicyContractTests(unittest.TestCase):
    def _validate(
        self,
        body: dict[str, object] | None = None,
        signature: dict[str, object] | None = None,
    ) -> dict[str, object]:
        body_bytes, signature_bytes = _contract_bytes(body or _body(), signature)
        return policy.validate_presented_windows_owner_policy_contract(
            policy_body_bytes=body_bytes,
            policy_signature_bytes=signature_bytes,
        )

    def test_valid_contract_is_component_only_and_zero_authority(self) -> None:
        receipt = self._validate()
        self.assertEqual(receipt["schema_version"], policy.CONTRACT_RECEIPT_SCHEMA)
        self.assertEqual(receipt["gate_status"], policy.GATE_STATUS)
        self.assertTrue(receipt["exact_standard_explicit_ace_profile_contract_verified"])
        self.assertTrue(receipt["detached_signature_body_hash_cross_binding_verified"])
        for field in policy._ALWAYS_FALSE_FIELDS:
            self.assertFalse(receipt[field], field)
        material = {
            key: value for key, value in receipt.items() if key != "receipt_sha256"
        }
        self.assertEqual(receipt["receipt_sha256"], policy.canonical_sha256(material))

    def test_public_api_has_no_path_key_sid_expected_context_or_callback(self) -> None:
        signature = inspect.signature(
            policy.validate_presented_windows_owner_policy_contract
        )
        self.assertEqual(
            list(signature.parameters),
            ["policy_body_bytes", "policy_signature_bytes"],
        )
        forbidden = {
            "path",
            "store",
            "key",
            "sid",
            "expected",
            "context",
            "callback",
            "receipt",
            "state",
        }
        for name in signature.parameters:
            self.assertFalse(any(token in name for token in forbidden))

    def test_noncanonical_duplicate_and_unknown_keys_fail_closed(self) -> None:
        body = _body()
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8") + b"\n"
        _, signature_bytes = _contract_bytes(body)
        with self.assertRaises(policy.P0WindowsOwnerPolicyContractError):
            policy.validate_presented_windows_owner_policy_contract(
                policy_body_bytes=raw,
                policy_signature_bytes=signature_bytes,
            )
        duplicate = policy.json_file_bytes(body).replace(
            b'{"acl_template_sha256":',
            b'{"schema_version":"duplicate","acl_template_sha256":',
            1,
        )
        with self.assertRaises(policy.P0WindowsOwnerPolicyContractError):
            policy.validate_presented_windows_owner_policy_contract(
                policy_body_bytes=duplicate,
                policy_signature_bytes=signature_bytes,
            )
        body["unexpected"] = True
        with self.assertRaises(policy.P0WindowsOwnerPolicyContractError):
            self._validate(body)

    def test_owner_and_verifier_profiles_must_be_permitted_and_distinct(self) -> None:
        body = _body()
        body["verifier_sid"] = _OWNER_SID
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError, "distinct"
        ):
            self._validate(body)
        body = _body()
        body["owner_sid"] = "S-1-5-32-544"
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError, "structural owner profile"
        ):
            self._validate(body)

    def test_genesis_and_successor_predecessor_rules(self) -> None:
        body = _body()
        body["predecessor_policy_bytes_sha256"] = "a" * 64
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError, "genesis"
        ):
            self._validate(body)
        receipt = self._validate(_body(epoch=2))
        self.assertEqual(receipt["policy_epoch"], 2)

    def test_object_role_order_and_fixed_generation_layout_are_exact(self) -> None:
        body = _body()
        objects = body["object_policies"]
        assert isinstance(objects, list)
        objects[0], objects[1] = objects[1], objects[0]
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError, "ordered role"
        ):
            self._validate(body)
        body = _body()
        objects = body["object_policies"]
        assert isinstance(objects, list)
        objects[2]["final_volume_guid_path"] += ".attacker"
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError, "fixed generation layout"
        ):
            self._validate(body)

    def test_object_identity_and_volume_guid_paths_are_strict(self) -> None:
        body = _body()
        objects = body["object_policies"]
        assert isinstance(objects, list)
        objects[1]["file_id_128_hex"] = objects[0]["file_id_128_hex"]
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError, "identities"
        ):
            self._validate(body)
        body = _body()
        objects = body["object_policies"]
        assert isinstance(objects, list)
        objects[0]["final_volume_guid_path"] = "C:\\ProgramData\\owner-policy"
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError, "volume-GUID"
        ):
            self._validate(body)

    def test_exact_ace_profile_rejects_callback_inherited_and_generic(self) -> None:
        for field, value, message in (
            ("ace_type", 9, "standard ACCESS_ALLOWED"),
            ("ace_flags", 16, "explicit and non-inheriting"),
            ("access_mask_decimal", str(0x80000000), "generic/MAXIMUM_ALLOWED"),
        ):
            with self.subTest(field=field):
                body = _body()
                objects = body["object_policies"]
                assert isinstance(objects, list)
                objects[0]["security_template"]["ordered_aces"][1][field] = value
                with self.assertRaisesRegex(
                    policy.P0WindowsOwnerPolicyContractError, message
                ):
                    self._validate(body)

    def test_exact_ace_order_mask_and_no_extra_principal(self) -> None:
        body = _body()
        objects = body["object_policies"]
        assert isinstance(objects, list)
        aces = objects[0]["security_template"]["ordered_aces"]
        aces[0], aces[1] = aces[1], aces[0]
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError, "exact policy profile"
        ):
            self._validate(body)
        body = _body()
        objects = body["object_policies"]
        assert isinstance(objects, list)
        objects[0]["security_template"]["ordered_aces"].append(
            {
                "ace_type": 0,
                "ace_flags": 0,
                "access_mask_decimal": str(policy.FILE_READER_MASK),
                "sid": "S-1-5-21-1-2-3-1002",
            }
        )
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError, "exactly owner and verifier"
        ):
            self._validate(body)

    def test_security_control_and_owner_must_match_exactly(self) -> None:
        body = _body()
        objects = body["object_policies"]
        assert isinstance(objects, list)
        objects[0]["security_template"]["dacl_protected"] = False
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError, "dacl_protected"
        ):
            self._validate(body)
        body = _body()
        objects = body["object_policies"]
        assert isinstance(objects, list)
        objects[0]["security_template"]["owner_sid"] = _VERIFIER_SID
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError, "owner SID mismatch"
        ):
            self._validate(body)

    def test_derived_owner_anchor_and_key_projection_tamper_fail(self) -> None:
        for field in (
            "owner_principal_sha256",
            "acl_template_sha256",
            "operational_key_projection_sha256",
            "owner_anchor_sha256",
        ):
            with self.subTest(field=field):
                body = _body()
                body[field] = "f" * 64
                with self.assertRaisesRegex(
                    policy.P0WindowsOwnerPolicyContractError, "mismatch"
                ):
                    self._validate(body)

    def test_signature_cross_binding_and_low_s_are_strict(self) -> None:
        body = _body()
        signature = _signature(body)
        signature["policy_id"] = "attacker-policy"
        body_bytes = policy.json_file_bytes(body)
        _rehash(signature)
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError, "policy_id mismatch"
        ):
            policy.validate_presented_windows_owner_policy_contract(
                policy_body_bytes=body_bytes,
                policy_signature_bytes=policy.json_file_bytes(signature),
            )
        signature = _signature(body)
        high_s = (1).to_bytes(32, "big") + (policy._P256_ORDER - 1).to_bytes(
            32, "big"
        )
        signature["signature_rs_base64"] = base64.b64encode(high_s).decode(
            "ascii"
        )
        _rehash(signature)
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError, "low-S"
        ):
            policy.validate_presented_windows_owner_policy_contract(
                policy_body_bytes=body_bytes,
                policy_signature_bytes=policy.json_file_bytes(signature),
            )

    def test_numeric_types_and_canonical_base64_are_not_malleable(self) -> None:
        body = _body()
        objects = body["object_policies"]
        assert isinstance(objects, list)
        objects[0]["security_template"]["ordered_aces"][0]["ace_type"] = False
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError, "standard ACCESS_ALLOWED"
        ):
            self._validate(body)

        body = _body()
        body_bytes = policy.json_file_bytes(body)
        signature = _signature(body)
        signature["policy_epoch"] = True
        _rehash(signature)
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError, "must be an integer"
        ):
            policy.validate_presented_windows_owner_policy_contract(
                policy_body_bytes=body_bytes,
                policy_signature_bytes=policy.json_file_bytes(signature),
            )

        signature = _signature(body)
        encoded = signature["signature_rs_base64"]
        assert isinstance(encoded, str) and encoded.endswith("Ag==")
        signature["signature_rs_base64"] = encoded[:-4] + "Ah=="
        _rehash(signature)
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError, "canonical pad bits"
        ):
            policy.validate_presented_windows_owner_policy_contract(
                policy_body_bytes=body_bytes,
                policy_signature_bytes=policy.json_file_bytes(signature),
            )

    def test_path_normalization_aliases_and_cross_volume_rows_fail_closed(self) -> None:
        body = _body()
        objects = body["object_policies"]
        assert isinstance(objects, list)
        objects[1]["volume_serial_decimal"] = "987654321"
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError, "one volume serial"
        ):
            self._validate(body)

        body = _body()
        objects = body["object_policies"]
        assert isinstance(objects, list)
        objects[0]["final_volume_guid_path"] += "."
        with self.assertRaises(policy.P0WindowsOwnerPolicyContractError):
            self._validate(body)

        for replacement in (
            "12345678-1234-1234-1234-1234567890AB",
            "12345678-1234-1234-1234-1234567890aB",
        ):
            with self.subTest(replacement=replacement):
                body = _body()
                objects = body["object_policies"]
                assert isinstance(objects, list)
                for row in objects:
                    row["final_volume_guid_path"] = row[
                        "final_volume_guid_path"
                    ].replace(
                        "12345678-1234-1234-1234-1234567890ab", replacement
                    )
                with self.assertRaisesRegex(
                    policy.P0WindowsOwnerPolicyContractError, "lowercase canonical"
                ):
                    self._validate(body)

        # Windows preserves the filesystem casing of the OS-owned known-folder
        # prefix.  The compiled application-owned suffix remains exact.
        self._validate(_body())
        body = _body()
        objects = body["object_policies"]
        assert isinstance(objects, list)
        for row in objects:
            row["final_volume_guid_path"] = row[
                "final_volume_guid_path"
            ].replace("\\llm-novel-dc\\", "\\LLM-NOVEL-DC\\")
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError, "fixed lowercase suffix"
        ):
            self._validate(body)

        body = _body()
        objects = body["object_policies"]
        assert isinstance(objects, list)
        for row in objects:
            row["final_volume_guid_path"] = row[
                "final_volume_guid_path"
            ].replace("p0-owner-policy-v1", "Straße")
        with self.assertRaises(policy.P0WindowsOwnerPolicyContractError):
            self._validate(body)

    def test_builtin_alias_and_invalid_sid_revision_fail_closed(self) -> None:
        for owner_sid in (
            "S-1-5-32-551",
            "S-0-5-21-1",
            "S-1-5-19",
            "S-1-5-20",
            "S-1-5-9",
            "S-1-5-21-111-222-333-512",
            "S-1-5-21-1",
        ):
            with self.subTest(owner_sid=owner_sid):
                body = _body()
                body["owner_sid"] = owner_sid
                with self.assertRaises(policy.P0WindowsOwnerPolicyContractError):
                    self._validate(body)
        body = _body()
        body["verifier_sid"] = "S-1-5-19"
        with self.assertRaises(policy.P0WindowsOwnerPolicyContractError):
            self._validate(body)
        for verifier_sid in (
            "S-1-5-21-111-222-333-512",
            "S-1-15-2-1",
            "S-1-15-2-2",
            "S-1-5-21-1",
        ):
            with self.subTest(verifier_sid=verifier_sid):
                body = _body()
                body["verifier_sid"] = verifier_sid
                with self.assertRaises(
                    policy.P0WindowsOwnerPolicyContractError
                ):
                    self._validate(body)

    def test_reserved_device_and_noncanonical_case_paths_fail_closed(self) -> None:
        for replacement in ("con", "con.txt", "nul", "com1", "lpt9"):
            with self.subTest(replacement=replacement):
                body = _body()
                objects = body["object_policies"]
                assert isinstance(objects, list)
                for row in objects:
                    row["final_volume_guid_path"] = row[
                        "final_volume_guid_path"
                    ].replace("p0-owner-policy-v1", replacement)
                with self.assertRaises(policy.P0WindowsOwnerPolicyContractError):
                    self._validate(body)
        body = _body()
        objects = body["object_policies"]
        assert isinstance(objects, list)
        for row in objects:
            row["final_volume_guid_path"] = row[
                "final_volume_guid_path"
            ].replace("\\policy", "\\POLICY")
        with self.assertRaises(policy.P0WindowsOwnerPolicyContractError):
            self._validate(body)

    def test_owner_anchor_binds_scope_identity_and_revocation_floor(self) -> None:
        for field, value in (
            ("project_id", "other-project"),
            ("store_id", "other-store"),
            ("min_revocation_sequence", 2),
        ):
            with self.subTest(field=field):
                body = _body()
                original_anchor = body["owner_anchor_sha256"]
                body[field] = value
                with self.assertRaisesRegex(
                    policy.P0WindowsOwnerPolicyContractError,
                    "owner_anchor_sha256 mismatch",
                ):
                    self._validate(body)
                self.assertEqual(body["owner_anchor_sha256"], original_anchor)

        body = _body()
        objects = body["object_policies"]
        assert isinstance(objects, list)
        objects[0]["file_id_128_hex"] = "f" * 32
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError,
            "owner_anchor_sha256 mismatch",
        ):
            self._validate(body)

    def test_parser_resource_and_unicode_failures_are_contract_errors(self) -> None:
        _, signature_bytes = _contract_bytes(_body())
        hostile_inputs = (
            b'{"x":"\\ud800"}\n',
            b'{"x":' + b"1" * 5000 + b"}\n",
            b'{"x":' + b"[" * 1500 + b"0" + b"]" * 1500 + b"}\n",
        )
        for raw in hostile_inputs:
            with self.subTest(length=len(raw)):
                with self.assertRaises(
                    policy.P0WindowsOwnerPolicyContractError
                ):
                    policy.validate_presented_windows_owner_policy_contract(
                        policy_body_bytes=raw,
                        policy_signature_bytes=signature_bytes,
                    )

    def test_policy_and_signature_artifact_hashes_are_verified(self) -> None:
        body = _body()
        signature = _signature(body)
        body["artifact_sha256"] = "f" * 64
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError, "artifact_sha256 mismatch"
        ):
            policy.validate_presented_windows_owner_policy_contract(
                policy_body_bytes=policy.json_file_bytes(body),
                policy_signature_bytes=policy.json_file_bytes(signature),
            )
        body = _body()
        signature = _signature(body)
        signature["artifact_sha256"] = "f" * 64
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError, "artifact_sha256 mismatch"
        ):
            policy.validate_presented_windows_owner_policy_contract(
                policy_body_bytes=policy.json_file_bytes(body),
                policy_signature_bytes=policy.json_file_bytes(signature),
            )

    def test_exact_security_projection_comparator_is_presented_only(self) -> None:
        body = _body()
        body_bytes = policy.json_file_bytes(body)
        observed = deepcopy(body["object_policies"][0]["security_template"])
        receipt = policy.compare_exact_security_projection(
            validated_policy_body_bytes=body_bytes,
            role="policy_store",
            observed_security_projection=observed,
        )
        self.assertTrue(receipt["presented_projection_exact_match_verified"])
        self.assertFalse(receipt["live_windows_binary_acl_verified"])
        self.assertFalse(receipt["independent_owner_policy_state_verified"])
        observed["group_sid"] = "S-1-5-19"
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError, "exactly match"
        ):
            policy.compare_exact_security_projection(
                validated_policy_body_bytes=body_bytes,
                role="policy_store",
                observed_security_projection=observed,
            )

    @unittest.skipUnless(os.name == "nt", "Windows binary ACL test")
    def test_live_binary_acl_reader_projects_held_file_and_policy_rejects_it(self) -> None:
        import msvcrt

        with tempfile.TemporaryDirectory() as raw_temp:
            path = Path(raw_temp) / "current-user-owned-policy.json"
            with path.open("w+b") as stream:
                handle = int(msvcrt.get_osfhandle(stream.fileno()))
                projection = binary_acl.observe_windows_binary_acl_projection(
                    handle=handle
                )
                self.assertTrue(projection["dacl_present"])
                self.assertFalse(projection["dacl_null"])
                self.assertTrue(projection["owner_sid"].startswith("S-"))
                self.assertTrue(projection["group_sid"].startswith("S-"))
                self.assertGreaterEqual(len(projection["ordered_aces"]), 1)
                with self.assertRaises(
                    policy.P0WindowsOwnerPolicyContractError
                ):
                    policy.compare_exact_security_projection(
                        validated_policy_body_bytes=policy.json_file_bytes(_body()),
                        role="policy_body_file",
                        observed_security_projection=projection,
                    )
                with self.assertRaises(
                    binary_acl.P0WindowsBinaryAclProjectionError
                ):
                    binary_acl.observe_windows_binary_acl_projection(
                        handle=handle + 2**64
                    )

    @unittest.skipUnless(os.name == "nt", "Windows binary ACL test")
    def test_live_binary_acl_reader_rejects_invalid_handle(self) -> None:
        for handle in (2**31 - 1, 2**64 - 1, 2**64 - 2):
            with self.subTest(handle=handle):
                with self.assertRaises(
                    binary_acl.P0WindowsBinaryAclProjectionError
                ):
                    binary_acl.observe_windows_binary_acl_projection(handle=handle)


if __name__ == "__main__":
    unittest.main()
