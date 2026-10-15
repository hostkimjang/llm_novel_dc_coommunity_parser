from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from llm_batch.grounding import p0_actual_packet_contract as packet_contract
from llm_batch.grounding import p0_windows_fixed_directory_identity as windows_identity


def _canonical_sha256(value: object) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _fixed_names() -> list[str]:
    return [
        packet_contract.PACKET_MANIFEST_FILENAME,
        *(filename for _, filename, _ in packet_contract.CHILD_FILES),
    ]


def _write_fixed_directory(root: Path) -> dict[str, bytes]:
    raw_by_name: dict[str, bytes] = {}
    for index, name in enumerate(_fixed_names()):
        raw = f"fixed-member-{index}:{name}\n".encode("utf-8")
        (root / name).write_bytes(raw)
        raw_by_name[name] = raw
    return raw_by_name


@unittest.skipUnless(os.name == "nt", "Windows handle integration")
class WindowsFixedDirectoryIdentityIntegrationTests(unittest.TestCase):
    def _identity(
        self, root: Path
    ) -> windows_identity.WindowsDirectoryIdentity:
        return windows_identity.observe_windows_directory_identity(root)

    def _read(
        self,
        root: Path,
        identity: windows_identity.WindowsDirectoryIdentity | None = None,
        **overrides: object,
    ) -> windows_identity.WindowsFixedDirectoryRead:
        identity = identity or self._identity(root)
        arguments = {
            "expected_root_final_path": identity.final_path,
            "expected_root_volume_serial": identity.volume_serial,
            "expected_root_file_id": identity.file_id,
        }
        arguments.update(overrides)
        return windows_identity.read_windows_fixed_p0_packet_directory(
            root, **arguments
        )

    def test_positive_handle_bound_read_is_self_hashed_but_no_go(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            expected = _write_fixed_directory(root)
            result = self._read(root)

        self.assertEqual(expected, result.raw_by_name)
        self.assertEqual(14, result.receipt["member_handle_count"])
        self.assertTrue(result.receipt["filesystem_handle_binding_verified"])
        self.assertFalse(result.receipt["filesystem_handle_trust_verified"])
        self.assertFalse(result.receipt["external_root_identity_pin_verified"])
        self.assertTrue(result.receipt["member_unnamed_stream_only_verified"])
        self.assertTrue(
            result.receipt["root_direct_parent_component_boundary_verified"]
        )
        self.assertEqual(
            result.receipt["ancestor_handle_count"],
            len(result.receipt["ancestor_chain"]),
        )
        self.assertEqual(
            _canonical_sha256(result.receipt["ancestor_chain"]),
            result.receipt["ancestor_chain_sha256"],
        )
        for index, member in enumerate(result.receipt["ancestor_chain"]):
            self.assertEqual(index, member["index"])
            self.assertEqual(
                member["before_projection_sha256"],
                member["after_projection_sha256"],
            )
            self.assertEqual(
                member["stable_projection_sha256"],
                member["before_projection_sha256"],
            )
        self.assertFalse(result.receipt["os_write_deny_verified"])
        self.assertFalse(result.receipt["runtime_noninterference_verified"])
        self.assertFalse(result.receipt["external_owner_authority_verified"])
        self.assertFalse(result.receipt["actual_authority_granted"])
        material = dict(result.receipt)
        receipt_sha = material.pop("receipt_sha256")
        self.assertEqual(_canonical_sha256(material), receipt_sha)

    def test_all_three_external_root_pins_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            _write_fixed_directory(root)
            identity = self._identity(root)
            cases = (
                {
                    "expected_root_final_path": identity.final_path + "-other",
                },
                {
                    "expected_root_volume_serial": identity.volume_serial ^ 1,
                },
                {
                    "expected_root_file_id": (
                        "0" * 32 if identity.file_id != "0" * 32 else "1" * 32
                    ),
                },
            )
            for override in cases:
                with self.subTest(override=override), self.assertRaises(
                    windows_identity.P0WindowsFixedDirectoryError
                ):
                    self._read(root, identity, **override)

    def test_extra_member_fails_exact_handle_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            _write_fixed_directory(root)
            identity = self._identity(root)
            (root / "unlisted.txt").write_bytes(b"forbidden")
            with self.assertRaisesRegex(
                windows_identity.P0WindowsFixedDirectoryError,
                "fixed directory inventory",
            ):
                self._read(root, identity)

    def test_hardlink_alias_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            _write_fixed_directory(root)
            first, second = _fixed_names()[:2]
            (root / second).unlink()
            os.link(root / first, root / second)
            identity = self._identity(root)
            with self.assertRaises(
                windows_identity.P0WindowsFixedDirectoryError
            ):
                self._read(root, identity)

    def test_child_symlink_or_reparse_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            _write_fixed_directory(root)
            first, second = _fixed_names()[:2]
            (root / second).unlink()
            try:
                os.symlink(root / first, root / second)
            except OSError as exc:
                self.skipTest(f"symlink creation is unavailable: {exc}")
            identity = self._identity(root)
            with self.assertRaises(
                windows_identity.P0WindowsFixedDirectoryError
            ):
                self._read(root, identity)

    def test_root_or_ancestor_reparse_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            base = Path(tmp_name)
            parent = base / "real-parent"
            root = parent / "packet"
            root.mkdir(parents=True)
            _write_fixed_directory(root)
            identity = self._identity(root)

            root_alias = base / "packet-alias"
            parent_alias = base / "parent-alias"
            try:
                os.symlink(root, root_alias, target_is_directory=True)
                os.symlink(parent, parent_alias, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlink creation is unavailable: {exc}")

            for path in (root_alias, parent_alias / "packet"):
                with self.subTest(path=path), self.assertRaises(
                    windows_identity.P0WindowsFixedDirectoryError
                ):
                    self._read(path, identity)

    def test_named_alternate_data_stream_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            _write_fixed_directory(root)
            stream_path = str(root / _fixed_names()[0]) + ":hidden"
            try:
                with open(stream_path, "wb") as stream:
                    stream.write(b"not-part-of-the-packet")
            except OSError as exc:
                self.skipTest(f"alternate data streams are unavailable: {exc}")
            identity = self._identity(root)
            with self.assertRaisesRegex(
                windows_identity.P0WindowsFixedDirectoryError,
                "unnamed data stream",
            ):
                self._read(root, identity)

    def test_before_after_metadata_drift_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            _write_fixed_directory(root)
            identity = self._identity(root)
            target = _fixed_names()[0].casefold()
            original = windows_identity._query_snapshot
            counts: dict[str, int] = {}

            def drifting_snapshot(api: object, handle: int, *, include_streams: bool):
                snapshot = original(api, handle, include_streams=include_streams)
                if include_streams and snapshot.final_path.casefold().endswith(target):
                    counts[target] = counts.get(target, 0) + 1
                    if counts[target] == 2:
                        basic = list(snapshot.basic)
                        basic[3] += 1
                        return replace(snapshot, basic=tuple(basic))
                return snapshot

            with mock.patch.object(
                windows_identity, "_query_snapshot", side_effect=drifting_snapshot
            ), self.assertRaisesRegex(
                windows_identity.P0WindowsFixedDirectoryError,
                "identity/metadata changed",
            ):
                self._read(root, identity)

    def test_directory_entry_and_open_handle_metadata_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            _write_fixed_directory(root)
            identity = self._identity(root)
            original = windows_identity._enumerate_directory
            calls = 0

            def mismatched_inventory(api: object, handle: int):
                nonlocal calls
                calls += 1
                values = original(api, handle)
                if calls == 1:
                    name = sorted(values)[0]
                    values[name] = replace(
                        values[name], allocation_size=values[name].allocation_size + 1
                    )
                return values

            with mock.patch.object(
                windows_identity,
                "_enumerate_directory",
                side_effect=mismatched_inventory,
            ), self.assertRaisesRegex(
                windows_identity.P0WindowsFixedDirectoryError,
                "metadata mismatch",
            ):
                self._read(root, identity)

    def test_directory_entry_and_open_handle_file_id_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            _write_fixed_directory(root)
            identity = self._identity(root)
            original = windows_identity._enumerate_directory
            calls = 0

            def mismatched_inventory(api: object, handle: int):
                nonlocal calls
                calls += 1
                values = original(api, handle)
                if calls == 1:
                    name = sorted(values)[0]
                    replacement = (
                        "0" * 32
                        if values[name].file_id != "0" * 32
                        else "1" * 32
                    )
                    values[name] = replace(values[name], file_id=replacement)
                return values

            with mock.patch.object(
                windows_identity,
                "_enumerate_directory",
                side_effect=mismatched_inventory,
            ), self.assertRaisesRegex(
                windows_identity.P0WindowsFixedDirectoryError,
                "metadata mismatch",
            ):
                self._read(root, identity)

    def test_second_handle_inventory_drift_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            _write_fixed_directory(root)
            identity = self._identity(root)
            original = windows_identity._enumerate_directory
            calls = 0

            def drifting_inventory(api: object, handle: int):
                nonlocal calls
                calls += 1
                values = original(api, handle)
                if calls == 2:
                    name = sorted(values)[0]
                    values[name] = replace(
                        values[name], change_time=values[name].change_time + 1
                    )
                return values

            with mock.patch.object(
                windows_identity,
                "_enumerate_directory",
                side_effect=drifting_inventory,
            ), self.assertRaisesRegex(
                windows_identity.P0WindowsFixedDirectoryError,
                "inventory changed",
            ):
                self._read(root, identity)

    def test_existing_packet_byte_validator_can_consume_handle_read_map(self) -> None:
        # Reuse the deterministic packet builder already covered by the packet
        # contract tests; this test covers only the new handle-to-bytes bridge.
        from tests.test_p0_actual_packet_contract import _packet, _pinned

        manifest, children = _packet(origin=packet_contract.EXAMPLE_ORIGIN)
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            (root / packet_contract.PACKET_MANIFEST_FILENAME).write_bytes(manifest)
            for name, raw in children.items():
                (root / name).write_bytes(raw)
            identity = self._identity(root)
            receipt = windows_identity.validate_windows_fixed_p0_packet_directory(
                root,
                expected_root_final_path=identity.final_path,
                expected_root_volume_serial=identity.volume_serial,
                expected_root_file_id=identity.file_id,
                expected_manifest_sha256=_pinned(manifest),
                expected_origin=packet_contract.EXAMPLE_ORIGIN,
            )

        self.assertTrue(receipt["byte_inventory_binding_verified"])
        self.assertTrue(receipt["filesystem_handle_binding_verified"])
        self.assertFalse(receipt["filesystem_handle_trust_verified"])
        self.assertFalse(receipt["external_root_identity_pin_verified"])
        self.assertTrue(
            receipt["packet_receipt"]["byte_inventory_binding_verified"]
        )
        self.assertEqual(_pinned(manifest), receipt["expected_manifest_sha256"])
        self.assertEqual(
            receipt["handle_member_inventory_projection"],
            receipt["packet_manifest_fixed_file_inventory_projection"],
        )
        self.assertEqual(
            receipt["handle_member_inventory_sha256"],
            receipt["packet_manifest_fixed_file_inventory_sha256"],
        )
        self.assertTrue(receipt["handle_manifest_fixed_file_inventory_exact_match"])
        self.assertEqual(
            receipt["windows_handle_receipt"]["receipt_sha256"],
            receipt["windows_handle_receipt_declared_receipt_sha256"],
        )
        self.assertEqual(
            receipt["packet_receipt"]["receipt_sha256"],
            receipt["packet_receipt_declared_receipt_sha256"],
        )
        self.assertEqual(
            _canonical_sha256(receipt["packet_receipt"]),
            receipt["packet_receipt_full_canonical_sha256"],
        )
        self.assertFalse(receipt["os_write_deny_verified"])
        self.assertFalse(receipt["runtime_noninterference_verified"])
        self.assertFalse(receipt["actual_authority_granted"])
        material = dict(receipt)
        receipt_sha = material.pop("receipt_sha256")
        self.assertEqual(_canonical_sha256(material), receipt_sha)

    def test_composite_rejects_nested_handle_member_hash_mismatch(self) -> None:
        from tests.test_p0_actual_packet_contract import _packet, _pinned

        manifest, children = _packet(origin=packet_contract.EXAMPLE_ORIGIN)
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            (root / packet_contract.PACKET_MANIFEST_FILENAME).write_bytes(manifest)
            for name, raw in children.items():
                (root / name).write_bytes(raw)
            identity = self._identity(root)
            observation = self._read(root, identity)
            tampered_receipt = dict(observation.receipt)
            tampered_members = [dict(value) for value in tampered_receipt["members"]]
            tampered_members[0]["sha256"] = "0" * 64
            tampered_receipt["members"] = tampered_members
            tampered = windows_identity.WindowsFixedDirectoryRead(
                observation.raw_by_name, tampered_receipt
            )
            with mock.patch.object(
                windows_identity,
                "read_windows_fixed_p0_packet_directory",
                return_value=tampered,
            ), self.assertRaisesRegex(
                windows_identity.P0WindowsFixedDirectoryError,
                "member bytes/hash mismatch",
            ):
                windows_identity.validate_windows_fixed_p0_packet_directory(
                    root,
                    expected_root_final_path=identity.final_path,
                    expected_root_volume_serial=identity.volume_serial,
                    expected_root_file_id=identity.file_id,
                    expected_manifest_sha256=_pinned(manifest),
                    expected_origin=packet_contract.EXAMPLE_ORIGIN,
                )


class WindowsFixedDirectoryIdentityPlatformTests(unittest.TestCase):
    @staticmethod
    def _pure_observation() -> tuple[
        windows_identity.WindowsFixedDirectoryRead, bytes, dict[str, bytes]
    ]:
        from tests.test_p0_actual_packet_contract import _packet

        manifest, children = _packet(origin=packet_contract.EXAMPLE_ORIGIN)
        raw_by_name = {
            packet_contract.PACKET_MANIFEST_FILENAME: manifest,
            **children,
        }
        members = [
            {
                "name": name,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
            for name, raw in sorted(raw_by_name.items())
        ]
        receipt_material = {
            "schema_version": windows_identity.WINDOWS_HANDLE_RECEIPT_SCHEMA,
            "platform": "win32",
            "members": members,
            "filesystem_handle_binding_verified": True,
            "filesystem_handle_trust_verified": False,
            "external_root_identity_pin_verified": False,
            "actual_authority_granted": False,
        }
        receipt = {
            **receipt_material,
            "receipt_sha256": _canonical_sha256(receipt_material),
        }
        return (
            windows_identity.WindowsFixedDirectoryRead(raw_by_name, receipt),
            manifest,
            children,
        )

    def test_non_windows_fails_before_filesystem_access(self) -> None:
        with mock.patch.object(windows_identity, "_IS_WINDOWS", False), mock.patch.object(
            windows_identity, "_lexical_ancestor_paths"
        ) as path_probe:
            with self.assertRaisesRegex(
                windows_identity.P0WindowsFixedDirectoryError, "unavailable"
            ):
                windows_identity.read_windows_fixed_p0_packet_directory(
                    "must-not-be-observed",
                    expected_root_final_path=(
                        "\\\\?\\Volume{00000000-0000-0000-0000-000000000000}\\packet"
                    ),
                    expected_root_volume_serial=1,
                    expected_root_file_id="0" * 32,
                )
        path_probe.assert_not_called()

    def test_pure_bind_reuses_observation_without_filesystem_access(self) -> None:
        observation, manifest, _ = self._pure_observation()
        with mock.patch.object(
            windows_identity, "read_windows_fixed_p0_packet_directory"
        ) as read_probe:
            receipt = windows_identity.bind_windows_fixed_packet_observation(
                observation,
                expected_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
                expected_origin=packet_contract.EXAMPLE_ORIGIN,
            )

        read_probe.assert_not_called()
        self.assertTrue(receipt["byte_inventory_binding_verified"])
        self.assertTrue(receipt["filesystem_handle_binding_verified"])
        self.assertFalse(receipt["filesystem_handle_trust_verified"])
        self.assertFalse(receipt["actual_authority_granted"])

    def test_pure_bind_rejects_raw_member_tamper(self) -> None:
        observation, manifest, children = self._pure_observation()
        raw_by_name = dict(observation.raw_by_name)
        target = sorted(children)[0]
        raw_by_name[target] += b"tamper"
        tampered = windows_identity.WindowsFixedDirectoryRead(
            raw_by_name, observation.receipt
        )

        with self.assertRaises(ValueError):
            windows_identity.bind_windows_fixed_packet_observation(
                tampered,
                expected_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
                expected_origin=packet_contract.EXAMPLE_ORIGIN,
            )

    def test_pure_bind_rejects_manifest_pin_mismatch(self) -> None:
        observation, manifest, _ = self._pure_observation()
        wrong_pin = "0" * 64
        if wrong_pin == hashlib.sha256(manifest).hexdigest():  # pragma: no cover
            wrong_pin = "1" * 64

        with self.assertRaises(ValueError):
            windows_identity.bind_windows_fixed_packet_observation(
                observation,
                expected_manifest_sha256=wrong_pin,
                expected_origin=packet_contract.EXAMPLE_ORIGIN,
            )

    def test_pure_bind_rejects_presented_handle_receipt_tamper(self) -> None:
        observation, manifest, _ = self._pure_observation()
        receipt = dict(observation.receipt)
        receipt["external_root_identity_pin_verified"] = True
        tampered = windows_identity.WindowsFixedDirectoryRead(
            observation.raw_by_name, receipt
        )

        with self.assertRaisesRegex(
            windows_identity.P0WindowsFixedDirectoryError,
            "self-hash mismatch",
        ):
            windows_identity.bind_windows_fixed_packet_observation(
                tampered,
                expected_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
                expected_origin=packet_contract.EXAMPLE_ORIGIN,
            )


if __name__ == "__main__":
    unittest.main()
