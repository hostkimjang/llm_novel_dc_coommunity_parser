"""Packet V2 Windows fixed-directory 경계의 집중 회귀·공격 테스트."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import inspect
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from llm_batch.grounding import p0_presented_a_context_annotation_packet_v2_contract as packet_v2
from llm_batch.grounding import p0_presented_a_context_annotation_packet_v2_windows_fixed_directory as windows_v2
from tests.test_p0_presented_a_context_annotation_packet_v2 import (
    _children,
    _manifest,
    _pins,
)


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(windows_v2._canonical_bytes(value)).hexdigest()


def _reseal_receipt(value: dict[str, object]) -> dict[str, object]:
    value["receipt_sha256"] = _canonical_sha256(
        {key: item for key, item in value.items() if key != "receipt_sha256"}
    )
    return value


def _write_packet(root: Path, manifest: bytes, children: dict[str, bytes]) -> None:
    for role, path, _media, _cap in windows_v2.FIXED_MEMBER_CONTRACT:
        (root / path).write_bytes(manifest if role == "packet_manifest" else children[role])


def _synthetic_handle_receipt() -> tuple[dict[str, object], dict[str, object]]:
    root = "\\\\?\\Volume{00000000-0000-0000-0000-000000000000}\\packet"
    volume = "1"
    members = []
    for index, (role, path, media, cap) in enumerate(windows_v2.FIXED_MEMBER_CONTRACT, 1):
        projection_sha = _canonical_sha256({"member": index})
        members.append({
            "role": role,
            "path": path,
            "media_type": media,
            "max_bytes": cap,
            "final_path": root + "\\" + path,
            "volume_serial": volume,
            "file_id": f"{index:032x}",
            "bytes": 0,
            "sha256": hashlib.sha256(b"").hexdigest(),
            "number_of_links": 1,
            "unnamed_stream_only": True,
            "before_projection_sha256": projection_sha,
            "after_projection_sha256": projection_sha,
            "reopen_projection_sha256": projection_sha,
        })
    ancestor_sha = _canonical_sha256({"ancestor": 0})
    ancestors = [{
        "index": 0,
        "lexical_path": "C:\\",
        "before_projection_sha256": ancestor_sha,
        "after_projection_sha256": ancestor_sha,
        "reopen_projection_sha256": ancestor_sha,
    }]
    root_sha = _canonical_sha256({"root": 1})
    inventory_sha = _canonical_sha256({"inventory": 1})
    pins = {role: hashlib.sha256(role.encode()).hexdigest()
            for role in windows_v2.MEMBER_ROLES}
    evidence = {
        "windows_component_manifest_sha256":
            windows_v2.COMPONENT_MANIFEST_SHA256,
        "packet_component_manifest_sha256":
            windows_v2.PACKET_COMPONENT_MANIFEST_SHA256,
        "fixed_member_contract_sha256":
            windows_v2.FIXED_MEMBER_CONTRACT_SHA256,
        "member_raw_caps_sha256": windows_v2.MEMBER_RAW_CAPS_SHA256,
        "expected_member_raw_pin_set_sha256": _canonical_sha256(pins),
        "member_sequence": list(windows_v2.MEMBER_SEQUENCE),
        "member_sequence_sha256":
            _canonical_sha256(list(windows_v2.MEMBER_SEQUENCE)),
        "total_member_bytes": 0,
        "aggregate_member_cap_bytes": windows_v2.AGGREGATE_MEMBER_CAP_BYTES,
        "inventory_before_sha256": inventory_sha,
        "inventory_after_sha256": inventory_sha,
        "ancestor_chain_sha256": _canonical_sha256(ancestors),
        "root_before_projection_sha256": root_sha,
        "root_after_projection_sha256": root_sha,
        "root_reopen_projection_sha256": root_sha,
        "member_evidence_sha256": _canonical_sha256(members),
    }
    local_evidence = {
        "root_final_path": root,
        "root_volume_serial": volume,
        "root_file_id": "f" * 32,
        "ancestor_handle_count": 1,
        "member_handle_count": 16,
        **evidence,
        "members": members,
        "ancestor_chain": ancestors,
    }
    material = {
        "schema_version": windows_v2.WINDOWS_HANDLE_RECEIPT_SCHEMA,
        "platform": "win32",
        "root_final_path": root,
        "root_volume_serial": volume,
        "root_file_id": "f" * 32,
        "ancestor_handle_count": 1,
        "member_handle_count": 16,
        **evidence,
        "members": members,
        "ancestor_chain": ancestors,
        **{field: True for field in windows_v2._HANDLE_TRUE_FIELDS},
        **{field: False for field in windows_v2._DENIAL_FIELDS},
        "operational_effect": "NONE_SHADOW_ONLY",
        "gate_status": "NO_GO_PRESENTED_PACKET_V2_BOUNDED_WINDOWS_HANDLE_BINDING_ONLY",
        "receipt_hash_scope": "CANONICAL_MATERIAL_EXCLUDING_RECEIPT_SHA256",
    }
    return (
        {**material, "receipt_sha256": _canonical_sha256(material)},
        local_evidence,
    )

class PacketV2WindowsFixedDirectoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.children = _children()
        cls.manifest = _manifest(cls.children)
        cls.pins = _pins(cls.manifest, cls.children)

    def _memory(self, **overrides: object) -> dict[str, object]:
        values: dict[str, object] = {
            "manifest_raw": self.manifest,
            "expected_member_raw_sha256": self.pins,
            **self.children,
        }
        values.update(overrides)
        return windows_v2.bind_presented_a_context_annotation_packet_v2_memory(**values)

    def _direct(self, root: Path, **overrides: object) -> dict[str, object]:
        identity = windows_v2.observe_presented_a_context_annotation_packet_v2_windows_directory_identity(root)
        values: dict[str, object] = {
            "expected_root_final_path": identity.final_path,
            "expected_root_volume_serial": identity.volume_serial,
            "expected_root_file_id": identity.file_id,
            "expected_member_raw_sha256": self.pins,
        }
        values.update(overrides)
        return windows_v2.validate_presented_a_context_annotation_packet_v2_windows_directory(
            root, **values
        )

    def _parent_inputs(self) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        manifest = packet_v2.validate_manifest_bytes(self.manifest, self.children)
        target = windows_v2._validated_object(
            self.children["target_precommit"], "target precommit"
        )
        receipt = windows_v2.packet_v2_parent.validate_packet_manifest_against_raw_inputs(
            manifest_raw=self.manifest,
            expected_member_raw_sha256=self.pins,
            **self.children,
        )
        return manifest, target, receipt

    def test_fixed_literal_pins_exact_contract_and_aggregate(self) -> None:
        self.assertEqual(
            windows_v2.PACKET_COMPONENT_MANIFEST_SHA256,
            "2a4b63518b8d80522469753191c9879af6f85f55828f28318a149911e564d59f",
        )
        self.assertEqual(
            windows_v2.FIXED_MEMBER_CONTRACT_SHA256,
            "37f3a34ab17c219065b81d9f2eb3d9a8876c5e32e12e7051ec30f3e5038385fc",
        )
        self.assertEqual(windows_v2.FIXED_MEMBER_CONTRACT, packet_v2.FIXED_MEMBER_CONTRACT)
        self.assertEqual(len(windows_v2.FIXED_MEMBER_CONTRACT), 16)
        self.assertEqual(sum(windows_v2.MEMBER_RAW_CAPS.values()), 281_905_216)
        self.assertEqual(windows_v2.AGGREGATE_MEMBER_CAP_BYTES, 281_905_216)

    def test_memory_positive_exact_schema_self_hash_and_all_denials(self) -> None:
        receipt = self._memory()
        self.assertEqual(tuple(receipt), windows_v2.MEMORY_RECEIPT_FIELDS)
        self.assertEqual(receipt["validation_mode"], "MEMORY_RAW_BYTES")
        self.assertFalse(receipt["handles_held_across_packet_validation"])
        self.assertFalse(receipt["local_byte_handle_consistency_verified"])
        self.assertEqual(receipt["packet_parent_execution_count"], 1)
        self.assertEqual(receipt["independent_target_parent_execution_count"], 1)
        self.assertEqual(receipt["total_target_parent_execution_count"], 2)
        self.assertFalse(receipt["target_parent_single_execution_claimed"])
        self.assertTrue(all(receipt[field] is False for field in windows_v2._DENIAL_FIELDS))
        material = dict(receipt)
        declared = material.pop("receipt_sha256")
        self.assertEqual(declared, _canonical_sha256(material))

    def test_memory_pin_inventory_missing_extra_order_and_bad_scalar_fail(self) -> None:
        missing = dict(self.pins)
        missing.pop("a_plan")
        extra = dict(self.pins)
        extra["result_rows"] = "0" * 64
        reversed_pins = {key: self.pins[key] for key in reversed(tuple(self.pins))}
        bad_bool = dict(self.pins)
        bad_bool["source_seed"] = False  # type: ignore[assignment]
        for attacked in (missing, extra, reversed_pins, bad_bool):
            with self.subTest(keys=tuple(attacked)), self.assertRaises(
                windows_v2.P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError
            ):
                self._memory(expected_member_raw_sha256=attacked)

    def test_memory_child_exact_order_and_bool_bytes_confusion_fail(self) -> None:
        reversed_children = {key: self.children[key] for key in reversed(tuple(self.children))}
        values = {
            "manifest_raw": self.manifest,
            "expected_member_raw_sha256": self.pins,
            **reversed_children,
        }
        with self.assertRaisesRegex(
            windows_v2.P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError,
            "ordered 15-role",
        ):
            windows_v2.bind_presented_a_context_annotation_packet_v2_memory(**values)
        with self.assertRaisesRegex(
            windows_v2.P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError,
            "exact bytes",
        ):
            self._memory(source_seed=True)

    def test_memory_role_cap_plus_one_rejects_before_hash_and_decode(self) -> None:
        huge = b"x" * (windows_v2.MEMBER_RAW_CAPS["source_seed"] + 1)
        with mock.patch.object(
            windows_v2.hashlib, "sha256", side_effect=AssertionError("hash reached")
        ), mock.patch.object(
            windows_v2.packet_v2, "validate_manifest_bytes", side_effect=AssertionError("decode reached")
        ):
            with self.assertRaisesRegex(
                windows_v2.P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError,
                "before hash/decode",
            ):
                self._memory(source_seed=huge)

    def test_forged_resealed_parent_high_risk_true_is_rejected(self) -> None:
        genuine = windows_v2.packet_v2_parent.validate_packet_manifest_against_raw_inputs(
            manifest_raw=self.manifest,
            expected_member_raw_sha256=self.pins,
            **self.children,
        )
        forged = deepcopy(genuine)
        forged["actual_authority_granted"] = True
        forged["receipt_sha256"] = _canonical_sha256(
            {key: value for key, value in forged.items() if key != "receipt_sha256"}
        )
        with mock.patch.object(
            windows_v2.packet_v2_parent,
            "validate_packet_manifest_against_raw_inputs",
            return_value=forged,
        ), self.assertRaisesRegex(
            windows_v2.P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError,
            "semantics",
        ):
            self._memory()

    def test_forged_resealed_parent_extra_field_is_rejected(self) -> None:
        genuine = windows_v2.packet_v2_parent.validate_packet_manifest_against_raw_inputs(
            manifest_raw=self.manifest,
            expected_member_raw_sha256=self.pins,
            **self.children,
        )
        forged = deepcopy(genuine)
        forged["attacker_safe_looking_extra"] = False
        forged["receipt_sha256"] = _canonical_sha256(
            {key: value for key, value in forged.items() if key != "receipt_sha256"}
        )
        with mock.patch.object(
            windows_v2.packet_v2_parent,
            "validate_packet_manifest_against_raw_inputs",
            return_value=forged,
        ), self.assertRaisesRegex(
            windows_v2.P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError,
            "exact ordered fields",
        ):
            self._memory()

    def test_resealed_zero_target_parent_declared_sha_is_rejected(self) -> None:
        _manifest_value, _target, genuine = self._parent_inputs()
        forged = deepcopy(genuine)
        forged["target_parent_receipt_sha256"] = "0" * 64
        _reseal_receipt(forged)
        with mock.patch.object(
            windows_v2.packet_v2_parent,
            "validate_packet_manifest_against_raw_inputs",
            return_value=forged,
        ), self.assertRaisesRegex(
            windows_v2.P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError,
            "dynamic/fixed semantics",
        ):
            self._memory()

    def test_resealed_zero_target_parent_full_sha_is_rejected(self) -> None:
        _manifest_value, _target, genuine = self._parent_inputs()
        forged = deepcopy(genuine)
        forged["target_parent_receipt_full_sha256"] = "0" * 64
        _reseal_receipt(forged)
        with mock.patch.object(
            windows_v2.packet_v2_parent,
            "validate_packet_manifest_against_raw_inputs",
            return_value=forged,
        ), self.assertRaisesRegex(
            windows_v2.P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError,
            "dynamic/fixed semantics",
        ):
            self._memory()

    def test_parent_order_plain_types_bool_int_and_count_pocs_fail(self) -> None:
        manifest, target, genuine = self._parent_inputs()

        class StringSubclass(str):
            pass

        class IntegerSubclass(int):
            pass

        class DictSubclass(dict):
            pass

        variants: list[dict[str, object]] = []
        reversed_top = dict(reversed(tuple(genuine.items())))
        variants.append(_reseal_receipt(reversed_top))
        subclass_key = {
            StringSubclass(key) if key == "schema_version" else key: value
            for key, value in genuine.items()
        }
        variants.append(_reseal_receipt(subclass_key))
        variants.append(_reseal_receipt(DictSubclass(genuine)))
        for field, attacked in (
            ("schema_version", StringSubclass(genuine["schema_version"])),
            ("gold_count", IntegerSubclass(0)),
            ("validated_member_raw_sha256", DictSubclass(genuine["validated_member_raw_sha256"])),
            ("actual_authority_granted", 0),
            ("actual_authority_granted", 1),
            ("gold_count", False),
            ("gold_count", 99),
        ):
            value = deepcopy(genuine)
            value[field] = attacked
            variants.append(_reseal_receipt(value))
        for attacked in variants:
            with self.subTest(keys=tuple(attacked)):
                with self.assertRaises(
                    windows_v2.P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError
                ):
                    windows_v2._strict_parent_receipt(
                        attacked,
                        self.pins,
                        manifest=manifest,
                        target_precommit=target,
                        expected_target_parent_receipt_sha256=
                            genuine["target_parent_receipt_sha256"],
                        expected_target_parent_receipt_full_sha256=
                            genuine["target_parent_receipt_full_sha256"],
                    )

    def test_parent_nested_map_order_types_values_and_dynamic_fields_fail(self) -> None:
        manifest, target, genuine = self._parent_inputs()
        variants: list[dict[str, object]] = []
        for field in (
            "validated_member_raw_sha256",
            "source_profile_counts",
            "terminal_status_counts",
        ):
            value = deepcopy(genuine)
            value[field] = dict(reversed(tuple(value[field].items())))
            variants.append(_reseal_receipt(value))
        value = deepcopy(genuine)
        value["source_profile_counts"]["OFFICIAL_STRUCTURED"] = True
        variants.append(_reseal_receipt(value))
        value = deepcopy(genuine)
        value["terminal_status_counts"]["JUDGED"] = False
        variants.append(_reseal_receipt(value))
        for field, attacked in (
            ("packet_id", "P0:A:ANNOTATION:PACKET:V2:" + "0" * 64),
            ("packet_manifest_artifact_sha256", "0" * 64),
            ("target_precommitted_at", genuine["packet_created_at"]),
        ):
            value = deepcopy(genuine)
            value[field] = attacked
            variants.append(_reseal_receipt(value))
        for attacked in variants:
            with self.subTest(keys=tuple(attacked)):
                with self.assertRaises(
                    windows_v2.P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError
                ):
                    windows_v2._strict_parent_receipt(
                        attacked,
                        self.pins,
                        manifest=manifest,
                        target_precommit=target,
                        expected_target_parent_receipt_sha256=
                            genuine["target_parent_receipt_sha256"],
                        expected_target_parent_receipt_full_sha256=
                            genuine["target_parent_receipt_full_sha256"],
                    )

    def test_v1_poc_resealed_handle_false_to_true_is_rejected(self) -> None:
        genuine, evidence = _synthetic_handle_receipt()
        safe = windows_v2._validate_handle_receipt_projection(
            genuine, expected_evidence=evidence
        )
        self.assertNotIn("members", safe)
        forged = deepcopy(genuine)
        forged["external_owner_authority_verified"] = True
        forged["receipt_sha256"] = _canonical_sha256(
            {key: value for key, value in forged.items() if key != "receipt_sha256"}
        )
        with self.assertRaisesRegex(
            windows_v2.P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError,
            "fixed safe semantics",
        ):
            windows_v2._validate_handle_receipt_projection(
                forged, expected_evidence=evidence
            )

    def test_handle_order_plain_types_and_ascii_volume_pocs_fail(self) -> None:
        genuine, evidence = _synthetic_handle_receipt()
        variants: list[tuple[dict[str, object], dict[str, object]]] = []

        class StringSubclass(str):
            pass

        class DictSubclass(dict):
            pass

        reversed_top = _reseal_receipt(dict(reversed(tuple(genuine.items()))))
        variants.append((reversed_top, evidence))
        subclass_key = {
            StringSubclass(key) if key == "schema_version" else key: value
            for key, value in genuine.items()
        }
        variants.append((_reseal_receipt(subclass_key), evidence))
        variants.append((_reseal_receipt(DictSubclass(genuine)), evidence))

        reordered = deepcopy(genuine)
        reordered_evidence = deepcopy(evidence)
        first = reordered["members"][0]
        reordered["members"][0] = dict(reversed(tuple(first.items())))
        reordered_evidence["members"] = reordered["members"]
        reordered["member_evidence_sha256"] = _canonical_sha256(reordered["members"])
        reordered_evidence["member_evidence_sha256"] = reordered["member_evidence_sha256"]
        variants.append((_reseal_receipt(reordered), reordered_evidence))

        arabic = deepcopy(genuine)
        arabic_evidence = deepcopy(evidence)
        arabic["root_volume_serial"] = "١"
        arabic_evidence["root_volume_serial"] = "١"
        for member in arabic["members"]:
            member["volume_serial"] = "١"
        arabic_evidence["members"] = arabic["members"]
        arabic["member_evidence_sha256"] = _canonical_sha256(arabic["members"])
        arabic_evidence["member_evidence_sha256"] = arabic["member_evidence_sha256"]
        variants.append((_reseal_receipt(arabic), arabic_evidence))

        bool_count = deepcopy(genuine)
        bool_evidence = deepcopy(evidence)
        bool_count["total_member_bytes"] = False
        bool_evidence["total_member_bytes"] = False
        variants.append((_reseal_receipt(bool_count), bool_evidence))

        for attacked, local in variants:
            with self.subTest(keys=tuple(attacked)), self.assertRaises(
                windows_v2.P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError
            ):
                windows_v2._validate_handle_receipt_projection(
                    attacked, expected_evidence=local
                )

    def test_handle_evidence_tamper_reseal_rejects_local_mismatch(self) -> None:
        genuine, evidence = _synthetic_handle_receipt()
        safe = windows_v2._validate_handle_receipt_projection(
            genuine, expected_evidence=evidence
        )
        for field in windows_v2._HANDLE_EVIDENCE_FIELDS:
            self.assertEqual(safe[field], genuine[field])
        self.assertEqual(
            safe["member_evidence_sha256"],
            _canonical_sha256(genuine["members"]),
        )
        self.assertEqual(
            safe["ancestor_chain_sha256"],
            _canonical_sha256(genuine["ancestor_chain"]),
        )

        attacked = deepcopy(genuine)
        attacked["inventory_before_sha256"] = "0" * 64
        _reseal_receipt(attacked)
        with self.assertRaisesRegex(
            windows_v2.P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError,
            "locally computed evidence mismatch",
        ):
            windows_v2._validate_handle_receipt_projection(
                attacked, expected_evidence=evidence
            )

        attacked = deepcopy(genuine)
        local = deepcopy(evidence)
        attacked["root_after_projection_sha256"] = "0" * 64
        local["root_after_projection_sha256"] = "0" * 64
        _reseal_receipt(attacked)
        with self.assertRaisesRegex(
            windows_v2.P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError,
            "fixed safe semantics",
        ):
            windows_v2._validate_handle_receipt_projection(
                attacked, expected_evidence=local
            )

    @unittest.skipUnless(os.name == "nt", "Windows handle test")
    def test_positive_windows_exact16_and_safe_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_packet(root, self.manifest, self.children)
            receipt = self._direct(root)
        self.assertEqual(tuple(receipt), windows_v2.WINDOWS_DIRECTORY_RECEIPT_FIELDS)
        self.assertTrue(receipt["handles_held_across_packet_validation"])
        self.assertTrue(receipt["local_byte_handle_consistency_verified"])
        self.assertEqual(receipt["member_handle_count"], 16)
        self.assertNotIn("members", receipt["handle_safe_projection"])
        safe = receipt["handle_safe_projection"]
        self.assertEqual(tuple(safe), windows_v2._SAFE_HANDLE_PROJECTION_FIELDS)
        self.assertEqual(safe["member_sequence"], list(windows_v2.MEMBER_ROLES))
        self.assertEqual(
            safe["member_raw_caps_sha256"], windows_v2.MEMBER_RAW_CAPS_SHA256
        )
        self.assertEqual(
            safe["inventory_before_sha256"], safe["inventory_after_sha256"]
        )
        self.assertEqual(
            safe["root_before_projection_sha256"],
            safe["root_after_projection_sha256"],
        )
        self.assertEqual(
            safe["root_before_projection_sha256"],
            safe["root_reopen_projection_sha256"],
        )
        self.assertTrue(all(receipt[field] is False for field in windows_v2._DENIAL_FIELDS))
        material = dict(receipt)
        declared = material.pop("receipt_sha256")
        self.assertEqual(declared, _canonical_sha256(material))

    @unittest.skipUnless(os.name == "nt", "Windows handle test")
    def test_all_root_identity_pins_are_required_and_exact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_packet(root, self.manifest, self.children)
            identity = windows_v2.observe_presented_a_context_annotation_packet_v2_windows_directory_identity(root)
            cases = (
                {"expected_root_final_path": identity.final_path + "-other"},
                {"expected_root_volume_serial": identity.volume_serial ^ 1},
                {"expected_root_file_id": "0" * 32 if identity.file_id != "0" * 32 else "1" * 32},
            )
            for override in cases:
                with self.subTest(override=override), self.assertRaises(
                    windows_v2.P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError
                ):
                    self._direct(root, **override)

    @unittest.skipUnless(os.name == "nt", "Windows handle test")
    def test_missing_extra_and_renamed_members_fail_exact_inventory(self) -> None:
        for attack in ("missing", "extra", "rename"):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _write_packet(root, self.manifest, self.children)
                first = windows_v2.FIXED_MEMBER_CONTRACT[0][1]
                if attack == "missing":
                    (root / first).unlink()
                elif attack == "extra":
                    (root / "extra.json").write_bytes(b"{}\n")
                else:
                    (root / first).rename(root / "RENAMED.json")
                with self.assertRaisesRegex(
                    windows_v2.P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError,
                    "inventory",
                ):
                    self._direct(root)

    @unittest.skipUnless(os.name == "nt", "Windows handle test")
    def test_role_cap_and_aggregate_reject_before_first_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_packet(root, self.manifest, self.children)
            (root / windows_v2.FIXED_MEMBER_PATHS["source_seed"]).write_bytes(
                b"x" * (windows_v2.MEMBER_RAW_CAPS["source_seed"] + 1)
            )
            with mock.patch.object(windows_v2, "_read_handle_exact") as read_probe:
                with self.assertRaisesRegex(
                    windows_v2.P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError,
                    "role cap before first read",
                ):
                    self._direct(root)
            read_probe.assert_not_called()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_packet(root, self.manifest, self.children)
            with mock.patch.object(windows_v2, "AGGREGATE_MEMBER_CAP_BYTES", 0), mock.patch.object(
                windows_v2, "_read_handle_exact"
            ) as read_probe:
                with self.assertRaisesRegex(
                    windows_v2.P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError,
                    "aggregate cap before first read",
                ):
                    self._direct(root)
            read_probe.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Windows handle test")
    def test_all_16_member_handles_are_open_before_first_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_packet(root, self.manifest, self.children)
            original_open = windows_v2._open_handle
            original_read = windows_v2._read_handle_exact
            opened = 0
            first_read_seen = False

            def tracking_open(*args: object, **kwargs: object):
                nonlocal opened
                if kwargs.get("read_data") is True:
                    opened += 1
                return original_open(*args, **kwargs)

            def tracking_read(*args: object, **kwargs: object):
                nonlocal first_read_seen
                if not first_read_seen:
                    self.assertEqual(opened, 16)
                    first_read_seen = True
                return original_read(*args, **kwargs)

            with mock.patch.object(windows_v2, "_open_handle", side_effect=tracking_open), mock.patch.object(
                windows_v2, "_read_handle_exact", side_effect=tracking_read
            ):
                self._direct(root)
            self.assertTrue(first_read_seen)

    @unittest.skipUnless(os.name == "nt", "Windows handle test")
    def test_postread_member_snapshot_mutation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_packet(root, self.manifest, self.children)
            original = windows_v2._query_snapshot
            target = windows_v2.FIXED_MEMBER_CONTRACT[0][1].casefold()
            count = 0

            def drifting(api: object, handle: int, *, include_streams: bool):
                nonlocal count
                snapshot = original(api, handle, include_streams=include_streams)
                if include_streams and snapshot.final_path.casefold().endswith(target):
                    count += 1
                    if count == 2:
                        basic = list(snapshot.basic)
                        basic[3] += 1
                        return replace(snapshot, basic=tuple(basic))
                return snapshot

            with mock.patch.object(windows_v2, "_query_snapshot", side_effect=drifting), self.assertRaisesRegex(
                windows_v2.P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError,
                "identity/metadata changed",
            ):
                self._direct(root)

    @unittest.skipUnless(os.name == "nt", "Windows handle test")
    def test_hardlink_alias_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_packet(root, self.manifest, self.children)
            first = windows_v2.FIXED_MEMBER_CONTRACT[0][1]
            second = windows_v2.FIXED_MEMBER_CONTRACT[1][1]
            (root / second).unlink()
            os.link(root / first, root / second)
            with self.assertRaises(windows_v2.P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError):
                self._direct(root)

    @unittest.skipUnless(os.name == "nt", "Windows handle test")
    def test_ads_fails_closed_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_packet(root, self.manifest, self.children)
            first = windows_v2.FIXED_MEMBER_CONTRACT[0][1]
            try:
                with open(str(root / first) + ":hidden", "wb") as stream:
                    stream.write(b"forbidden")
            except OSError as exc:
                self.skipTest(f"ADS unavailable: {exc}")
            with self.assertRaisesRegex(
                windows_v2.P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError,
                "unnamed data stream",
            ):
                self._direct(root)

    @unittest.skipUnless(os.name == "nt", "Windows handle test")
    def test_child_reparse_fails_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_packet(root, self.manifest, self.children)
            first = windows_v2.FIXED_MEMBER_CONTRACT[0][1]
            second = windows_v2.FIXED_MEMBER_CONTRACT[1][1]
            (root / second).unlink()
            try:
                os.symlink(root / first, root / second)
            except OSError as exc:
                self.skipTest(f"symlink unavailable: {exc}")
            with self.assertRaises(windows_v2.P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError):
                self._direct(root)

    def test_non_windows_fails_before_filesystem_probe(self) -> None:
        with mock.patch.object(windows_v2, "_IS_WINDOWS", False), mock.patch.object(
            windows_v2, "_lexical_ancestor_paths"
        ) as fs_probe:
            with self.assertRaisesRegex(
                windows_v2.P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError,
                "unavailable",
            ):
                windows_v2.validate_presented_a_context_annotation_packet_v2_windows_directory(
                    "must-not-be-touched",
                    expected_root_final_path="\\\\?\\Volume{00000000-0000-0000-0000-000000000000}\\packet",
                    expected_root_volume_serial=1,
                    expected_root_file_id="0" * 32,
                    expected_member_raw_sha256=self.pins,
                )
        fs_probe.assert_not_called()

    def test_no_v1_runtime_preauth_or_supervisor_import_and_no_receipt_api(self) -> None:
        source = inspect.getsource(windows_v2)
        for forbidden in (
            "p0_actual_packet_contract",
            "p0_windows_fixed_directory_identity",
            "p0_actual_owner_root_preauthorization",
            "p0_actual_supervisor_execution_contract",
            "p0_windows_runtime_evidence",
        ):
            self.assertNotIn(forbidden, source)
        for public in (
            windows_v2.bind_presented_a_context_annotation_packet_v2_memory,
            windows_v2.validate_presented_a_context_annotation_packet_v2_windows_directory,
        ):
            parameters = inspect.signature(public).parameters
            self.assertNotIn("receipt", parameters)
            self.assertNotIn("handle_receipt", parameters)

    def test_component_manifest_hash_and_public_callable_exact_allowlist(self) -> None:
        self.assertEqual(
            windows_v2.COMPONENT_MANIFEST_SHA256,
            _canonical_sha256(windows_v2.COMPONENT_MANIFEST),
        )
        self.assertEqual(
            tuple(windows_v2.COMPONENT_MANIFEST["schemas"]),
            (
                "memory_receipt", "windows_handle_receipt",
                "windows_directory_receipt", "safe_handle_projection",
            ),
        )
        self.assertEqual(
            windows_v2.COMPONENT_MANIFEST["public_apis"], windows_v2.PUBLIC_APIS
        )
        self.assertFalse(
            windows_v2.COMPONENT_MANIFEST[
                "serialized_handle_receipt_public_input_allowed"
            ]
        )
        architecture = windows_v2.COMPONENT_MANIFEST["validation_call_architecture"]
        self.assertEqual(architecture["target_parent_total_execution_count"], 2)
        self.assertFalse(architecture["target_parent_single_execution_claimed"])
        self.assertFalse(
            architecture["same_process_monkeypatch_resistance_verified"]
        )
        public_functions = tuple(
            name for name, value in vars(windows_v2).items()
            if not name.startswith("_")
            and inspect.isfunction(value)
            and value.__module__ == windows_v2.__name__
        )
        self.assertEqual(public_functions, windows_v2.PUBLIC_APIS)


if __name__ == "__main__":
    unittest.main()
