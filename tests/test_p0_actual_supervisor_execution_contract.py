from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError
import hashlib
import inspect
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from llm_batch.grounding import p0_actual_packet_contract as packet_contract
from llm_batch.grounding import p0_actual_a_event_bytes as a_event_bytes
from llm_batch.grounding import p0_actual_supervisor_execution_contract as supervisor
from llm_batch.grounding import p0_windows_fixed_directory_identity as windows_identity
from tests.test_p0_actual_packet_contract import _packet


_ROOT_FINAL_PATH = (
    "\\\\?\\Volume{00000000-0000-0000-0000-000000000000}\\packet"
)
_ROOT_VOLUME_SERIAL = 1
_ROOT_FILE_ID = "1" * 32
_FAKE_OBSERVATION: windows_identity.WindowsFixedDirectoryRead | None = None
_FAKE_READ_CALLS = 0


def _canonical_sha256(value: object) -> str:
    return supervisor.canonical_sha256(value)


def _fake_read(
    packet_dir: Path | str,
    *,
    expected_root_final_path: str,
    expected_root_volume_serial: int,
    expected_root_file_id: str,
) -> windows_identity.WindowsFixedDirectoryRead:
    del packet_dir
    global _FAKE_READ_CALLS
    _FAKE_READ_CALLS += 1
    if (
        expected_root_final_path != _ROOT_FINAL_PATH
        or expected_root_volume_serial != _ROOT_VOLUME_SERIAL
        or expected_root_file_id != _ROOT_FILE_ID
    ):
        raise windows_identity.P0WindowsFixedDirectoryError(
            "caller-pinned root identity mismatch"
        )
    if _FAKE_OBSERVATION is None:
        raise AssertionError("test observation was not installed")
    return _FAKE_OBSERVATION


def _observation(
    manifest: bytes, children: dict[str, bytes]
) -> windows_identity.WindowsFixedDirectoryRead:
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
    material = {
        "schema_version": windows_identity.WINDOWS_HANDLE_RECEIPT_SCHEMA,
        "platform": "win32",
        "root_final_path": _ROOT_FINAL_PATH,
        "root_volume_serial": str(_ROOT_VOLUME_SERIAL),
        "root_file_id": _ROOT_FILE_ID,
        "members": members,
        "filesystem_handle_binding_verified": True,
        "filesystem_handle_trust_verified": False,
        "external_root_identity_pin_verified": False,
        "actual_authority_granted": False,
    }
    receipt = {**material, "receipt_sha256": _canonical_sha256(material)}
    return windows_identity.WindowsFixedDirectoryRead(raw_by_name, receipt)


def _rehash_receipt(value: dict[str, object]) -> dict[str, object]:
    material = {key: item for key, item in value.items() if key != "receipt_sha256"}
    return {**material, "receipt_sha256": _canonical_sha256(material)}


class P0ActualSupervisorExecutionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        global _FAKE_OBSERVATION, _FAKE_READ_CALLS
        cls.manifest_bytes, cls.children = _packet(
            origin=packet_contract.EXAMPLE_ORIGIN
        )
        cls.manifest_sha256 = hashlib.sha256(cls.manifest_bytes).hexdigest()
        _FAKE_OBSERVATION = _observation(cls.manifest_bytes, cls.children)
        _FAKE_READ_CALLS = 0
        with mock.patch.object(
            windows_identity,
            "read_windows_fixed_p0_packet_directory",
            new=_fake_read,
        ):
            cls.measurement_manifest = (
                supervisor.build_local_packet_validator_measurement_manifest()
            )
            cls.execution_receipt = supervisor.execute_packet_supervisor_trace(
                packet_dir="ignored-test-packet",
                expected_root_final_path=_ROOT_FINAL_PATH,
                expected_root_volume_serial=_ROOT_VOLUME_SERIAL,
                expected_root_file_id=_ROOT_FILE_ID,
                expected_manifest_sha256=cls.manifest_sha256,
                expected_origin=packet_contract.EXAMPLE_ORIGIN,
                session_id="SESSION:SUPERVISOR:01",
                run_id="RUN:SUPERVISOR:01",
                nonce_commitment_sha256="2" * 64,
                expected_validator_measurement_manifest=cls.measurement_manifest,
            )

    def setUp(self) -> None:
        global _FAKE_OBSERVATION, _FAKE_READ_CALLS
        _FAKE_OBSERVATION = _observation(self.manifest_bytes, self.children)
        _FAKE_READ_CALLS = 0

    def _execute(
        self,
        *,
        measurement_manifest: dict[str, object] | None = None,
        manifest_sha256: str | None = None,
        root_final_path: str = _ROOT_FINAL_PATH,
    ) -> dict[str, object]:
        with mock.patch.object(
            windows_identity,
            "read_windows_fixed_p0_packet_directory",
            new=_fake_read,
        ):
            manifest = (
                supervisor.build_local_packet_validator_measurement_manifest()
                if measurement_manifest is None
                else measurement_manifest
            )
            return supervisor.execute_packet_supervisor_trace(
                packet_dir="ignored-test-packet",
                expected_root_final_path=root_final_path,
                expected_root_volume_serial=_ROOT_VOLUME_SERIAL,
                expected_root_file_id=_ROOT_FILE_ID,
                expected_manifest_sha256=(
                    self.manifest_sha256
                    if manifest_sha256 is None
                    else manifest_sha256
                ),
                expected_origin=packet_contract.EXAMPLE_ORIGIN,
                session_id="SESSION:SUPERVISOR:02",
                run_id="RUN:SUPERVISOR:02",
                nonce_commitment_sha256="3" * 64,
                expected_validator_measurement_manifest=manifest,
            )

    def test_direct_execution_trace_is_bounded_no_go(self) -> None:
        receipt = self.execution_receipt
        self.assertTrue(receipt["direct_packet_validator_invocations_completed"])
        self.assertTrue(receipt["packet_side_execution_trace_verified"])
        self.assertTrue(
            receipt[
                "same_handle_captured_packet_inputs_with_derived_a_claim_subset_verified"
            ]
        )
        self.assertFalse(receipt["presented_receipt_inputs_accepted"])
        self.assertTrue(receipt["untrusted_local_execution_observation"])
        self.assertTrue(receipt["caller_self_measurement_only"])
        self.assertFalse(
            receipt["windows_handle_capture_execution_provenance_verified"]
        )
        self.assertFalse(receipt["handles_held_across_validator_execution"])
        self.assertFalse(receipt["authority_side_execution_trace_verified"])
        self.assertFalse(receipt["external_code_authority_verified"])
        self.assertFalse(receipt["supervisor_runtime_trust_verified"])
        self.assertFalse(receipt["nonce_uniqueness_verified"])
        self.assertFalse(receipt["filesystem_handle_trust_verified"])
        self.assertFalse(receipt["actual_authority_granted"])
        self.assertFalse(receipt["production_approval"])
        self.assertFalse(receipt["full_scan_approval"])
        self.assertEqual(1 + len(packet_contract.CHILD_FILES), receipt["raw_member_count"])
        self.assertEqual(
            (41, 30, 20, 20),
            (
                receipt["a_claim_subset_derivation"][
                    "handle_captured_full_source_claim_row_count"
                ],
                receipt["a_claim_subset_derivation"][
                    "handle_captured_total_track_a_claim_count"
                ],
                receipt["a_claim_subset_derivation"][
                    "selected_source_claim_id_count"
                ],
                receipt["a_claim_subset_derivation"][
                    "derived_a_source_claim_row_count"
                ],
            ),
        )
        self.assertEqual(
            [
                "READ_WINDOWS_FIXED_PACKET_DIRECTORY",
                "VALIDATE_PACKET_BYTES",
                "BIND_WINDOWS_FIXED_PACKET_OBSERVATION",
                "VERIFY_A_EVENT_BYTES",
            ],
            receipt["fixed_step_order"],
        )
        self.assertEqual(
            "DIRECT_PACKET_EXECUTION_TRACE_PASS_EXTERNAL_TRUST_NO_GO",
            receipt["gate_status"],
        )

    def test_private_state_is_recursive_immutable_and_not_exported(self) -> None:
        with mock.patch.object(
            windows_identity,
            "read_windows_fixed_p0_packet_directory",
            new=_fake_read,
        ):
            state = supervisor._execute_packet_supervisor_state(
                packet_dir="ignored-test-packet",
                expected_root_final_path=_ROOT_FINAL_PATH,
                expected_root_volume_serial=_ROOT_VOLUME_SERIAL,
                expected_root_file_id=_ROOT_FILE_ID,
                expected_manifest_sha256=self.manifest_sha256,
                expected_origin=packet_contract.EXAMPLE_ORIGIN,
                session_id="SESSION:PRIVATE-STATE:01",
                run_id="RUN:PRIVATE-STATE:01",
                nonce_commitment_sha256="5" * 64,
                expected_validator_measurement_manifest=(
                    supervisor.build_local_packet_validator_measurement_manifest()
                ),
            )

        with self.assertRaises(FrozenInstanceError):
            state.public_receipt = {}  # type: ignore[misc]
        with self.assertRaises(TypeError):
            state.raw_by_name[packet_contract.PACKET_MANIFEST_FILENAME] = b"swap"  # type: ignore[index]
        with self.assertRaises(TypeError):
            state.public_receipt["gate_status"] = "GO"  # type: ignore[index]
        with self.assertRaises(TypeError):
            state.public_receipt["execution_genesis"]["run_id"] = "RUN:SWAP"  # type: ignore[index]
        with self.assertRaises(TypeError):
            state.handle_receipt["members"][0]["sha256"] = "f" * 64  # type: ignore[index]
        with self.assertRaises(TypeError):
            state.packet_receipt["credited_counts"][
                "actual_source_claim_count"
            ] = 40  # type: ignore[index]
        with self.assertRaises(TypeError):
            state.windows_packet_receipt["packet_receipt"][
                "actual_authority_granted"
            ] = True  # type: ignore[index]
        with self.assertRaises(TypeError):
            state.a_event_receipt["a_context_receipt"][
                "actual_authority_granted"
            ] = True  # type: ignore[index]
        self.assertIsInstance(state.raw_member_projection, tuple)
        self.assertEqual(
            self.manifest_bytes,
            state.raw_by_name[packet_contract.PACKET_MANIFEST_FILENAME],
        )
        self.assertNotIn("_PacketSupervisorState", supervisor.__all__)
        self.assertNotIn("_execute_packet_supervisor_state", supervisor.__all__)

    def test_public_wrapper_preserves_receipt_and_returns_detached_deep_copy(self) -> None:
        with mock.patch.object(
            windows_identity,
            "read_windows_fixed_p0_packet_directory",
            new=_fake_read,
        ):
            kwargs = {
                "packet_dir": "ignored-test-packet",
                "expected_root_final_path": _ROOT_FINAL_PATH,
                "expected_root_volume_serial": _ROOT_VOLUME_SERIAL,
                "expected_root_file_id": _ROOT_FILE_ID,
                "expected_manifest_sha256": self.manifest_sha256,
                "expected_origin": packet_contract.EXAMPLE_ORIGIN,
                "session_id": "SESSION:PRIVATE-STATE:02",
                "run_id": "RUN:PRIVATE-STATE:02",
                "nonce_commitment_sha256": "6" * 64,
                "expected_validator_measurement_manifest": (
                    supervisor.build_local_packet_validator_measurement_manifest()
                ),
            }
            state = supervisor._execute_packet_supervisor_state(**kwargs)
            first = supervisor.execute_packet_supervisor_trace(**kwargs)
            second = supervisor.execute_packet_supervisor_trace(**kwargs)

        expected = supervisor._thaw_snapshot(state.public_receipt)
        self.assertEqual(expected, first)
        self.assertEqual(first, second)
        self.assertIsInstance(first, dict)
        self.assertIsInstance(first["step_trace"], list)
        self.assertIsNot(first, second)
        self.assertIsNot(first["execution_genesis"], second["execution_genesis"])
        first["execution_genesis"]["run_id"] = "RUN:CALLER-MUTATION"
        first["step_trace"][0]["step_name"] = "CALLER-MUTATION"
        self.assertEqual("RUN:PRIVATE-STATE:02", second["execution_genesis"]["run_id"])
        self.assertEqual(
            "READ_WINDOWS_FIXED_PACKET_DIRECTORY",
            second["step_trace"][0]["step_name"],
        )

    def test_private_executor_accepts_no_state_or_child_receipt_injection(self) -> None:
        parameters = inspect.signature(
            supervisor._execute_packet_supervisor_state
        ).parameters
        forbidden = {
            "state",
            "observation",
            "handle_receipt",
            "packet_receipt",
            "windows_packet_receipt",
            "a_event_receipt",
            "public_receipt",
            "raw_by_name",
        }
        self.assertTrue(forbidden.isdisjoint(parameters))

    def test_naive_full_claim_input_fails_but_bound_derived_subset_passes(self) -> None:
        with self.assertRaises(a_event_bytes.P0ActualAEventBytesError):
            a_event_bytes.verify_a_event_bytes(
                source_claim_bytes=self.children["source_claims.jsonl"],
                a_context_bytes=self.children["a_contexts.jsonl"],
                a_event_bytes=self.children["a_annotation_events.jsonl"],
                a_subject_selection_seal_bytes=self.children[
                    "a_subject_selection_seal.json"
                ],
                expected_origin=packet_contract.EXAMPLE_ORIGIN,
            )
        derived, projection = supervisor._derive_a_source_claim_subset(
            self.children["source_claims.jsonl"], self.children["a_contexts.jsonl"]
        )
        receipt = a_event_bytes.verify_a_event_bytes(
            source_claim_bytes=derived,
            a_context_bytes=self.children["a_contexts.jsonl"],
            a_event_bytes=self.children["a_annotation_events.jsonl"],
            a_subject_selection_seal_bytes=self.children[
                "a_subject_selection_seal.json"
            ],
            expected_origin=packet_contract.EXAMPLE_ORIGIN,
        )
        self.assertEqual(20, projection["derived_a_source_claim_row_count"])
        self.assertEqual(
            projection["derived_a_source_claim_jsonl_sha256"],
            receipt["source_claim_file_sha256"],
        )

    def test_a_claim_subset_selection_tamper_is_rejected(self) -> None:
        contexts = [
            json.loads(line)
            for line in self.children["a_contexts.jsonl"].decode("utf-8").splitlines()
        ]
        claims = [
            json.loads(line)
            for line in self.children["source_claims.jsonl"].decode("utf-8").splitlines()
        ]
        track_b_id = next(row["claim_id"] for row in claims if row["track"] == "B")
        contexts[0]["source_claim_ids"] = [track_b_id]
        tampered_context_raw = packet_contract.jsonl_bytes(contexts)
        with self.assertRaisesRegex(
            supervisor.P0ActualSupervisorExecutionError,
            "TRACK-A",
        ):
            supervisor._derive_a_source_claim_subset(
                self.children["source_claims.jsonl"], tampered_context_raw
            )

    def test_a_claim_subset_duplicate_missing_and_noncanonical_inputs_fail(self) -> None:
        claims = [
            json.loads(line)
            for line in self.children["source_claims.jsonl"].decode("utf-8").splitlines()
        ]
        contexts = [
            json.loads(line)
            for line in self.children["a_contexts.jsonl"].decode("utf-8").splitlines()
        ]

        duplicate_claim_raw = packet_contract.jsonl_bytes([*claims, claims[0]])
        missing_contexts = copy.deepcopy(contexts)
        missing_contexts[0]["source_claim_ids"] = ["EXAMPLE:MISSING:CLAIM"]
        missing_context_raw = packet_contract.jsonl_bytes(missing_contexts)
        noncanonical_claim_raw = self.children["source_claims.jsonl"].replace(
            b'"action_applied":false', b'"action_applied": false', 1
        )

        variants = (
            ("duplicate", duplicate_claim_raw, self.children["a_contexts.jsonl"]),
            ("missing", self.children["source_claims.jsonl"], missing_context_raw),
            (
                "noncanonical",
                noncanonical_claim_raw,
                self.children["a_contexts.jsonl"],
            ),
        )
        for label, claim_raw, context_raw in variants:
            with self.subTest(label), self.assertRaises(
                supervisor.P0ActualSupervisorExecutionError
            ):
                supervisor._derive_a_source_claim_subset(claim_raw, context_raw)

    def test_presented_validator_never_promotes_execution_or_trust(self) -> None:
        validation = supervisor.validate_presented_packet_supervisor_receipt(
            self.execution_receipt
        )
        self.assertEqual(
            "PRESENTED_SUPERVISOR_RECEIPT_ONLY", validation["validation_scope"]
        )
        self.assertTrue(validation["presented_receipt_structurally_verified"])
        self.assertFalse(validation["direct_packet_validator_invocations_completed"])
        self.assertFalse(validation["packet_side_execution_trace_verified"])
        self.assertFalse(validation["underlying_validator_execution_verified"])
        self.assertTrue(validation["untrusted_local_execution_observation"])
        self.assertTrue(validation["caller_self_measurement_only"])
        self.assertFalse(
            validation["windows_handle_capture_execution_provenance_verified"]
        )
        self.assertFalse(validation["handles_held_across_validator_execution"])
        self.assertFalse(validation["external_code_authority_verified"])
        self.assertFalse(validation["actual_authority_granted"])

    def test_measurement_pin_mismatch_fails_before_directory_read(self) -> None:
        with mock.patch.object(
            windows_identity,
            "read_windows_fixed_p0_packet_directory",
            new=_fake_read,
        ):
            manifest = supervisor.build_local_packet_validator_measurement_manifest()
            manifest["measurements"][1]["callable_code_sha256"] = "f" * 64
            material = {
                key: item for key, item in manifest.items() if key != "artifact_sha256"
            }
            manifest["artifact_sha256"] = _canonical_sha256(material)
            with self.assertRaisesRegex(
                supervisor.P0ActualSupervisorExecutionError,
                "caller-pinned validator measurement mismatch",
            ):
                self._execute(measurement_manifest=manifest)
        self.assertEqual(0, _FAKE_READ_CALLS)

    def test_monkeypatched_callable_mismatch_fails_before_read(self) -> None:
        with mock.patch.object(
            windows_identity,
            "read_windows_fixed_p0_packet_directory",
            new=_fake_read,
        ):
            manifest = supervisor.build_local_packet_validator_measurement_manifest()
            original = packet_contract.validate_packet_bytes

            def replacement(*args: object, **kwargs: object) -> dict[str, object]:
                return original(*args, **kwargs)

            with mock.patch.object(
                packet_contract, "validate_packet_bytes", new=replacement
            ), self.assertRaisesRegex(
                supervisor.P0ActualSupervisorExecutionError,
                "caller-pinned validator measurement mismatch",
            ):
                self._execute(measurement_manifest=manifest)
        self.assertEqual(0, _FAKE_READ_CALLS)

    def test_manifest_root_and_raw_tamper_fail_without_terminal_receipt(self) -> None:
        wrong_manifest = "0" * 64
        if wrong_manifest == self.manifest_sha256:
            wrong_manifest = "1" * 64
        with self.subTest("manifest"):
            with self.assertRaises(ValueError):
                self._execute(manifest_sha256=wrong_manifest)

        with self.subTest("root"):
            with self.assertRaisesRegex(ValueError, "root identity mismatch"):
                self._execute(root_final_path=_ROOT_FINAL_PATH + "-other")

        with self.subTest("raw"):
            global _FAKE_OBSERVATION
            original = _FAKE_OBSERVATION
            raw_by_name = dict(original.raw_by_name)
            target = sorted(self.children)[0]
            raw_by_name[target] += b"tamper"
            _FAKE_OBSERVATION = windows_identity.WindowsFixedDirectoryRead(
                raw_by_name, original.receipt
            )
            with self.assertRaises(ValueError):
                self._execute()

    def test_presented_true_authority_injection_is_rejected_even_when_rehashed(self) -> None:
        tampered = copy.deepcopy(self.execution_receipt)
        tampered["actual_authority_granted"] = True
        tampered = _rehash_receipt(tampered)
        with self.assertRaisesRegex(
            supervisor.P0ActualSupervisorExecutionError,
            "authority boundary",
        ):
            supervisor.validate_presented_packet_supervisor_receipt(tampered)

    def test_self_hashed_nested_capability_injection_prevents_terminal_receipt(self) -> None:
        global _FAKE_OBSERVATION
        original = _FAKE_OBSERVATION
        for field in ("production_approval", "external_owner_authority_verified"):
            with self.subTest(field):
                nested_material = {
                    key: item
                    for key, item in original.receipt.items()
                    if key != "receipt_sha256"
                }
                nested_material[field] = True
                nested_receipt = {
                    **nested_material,
                    "receipt_sha256": _canonical_sha256(nested_material),
                }
                _FAKE_OBSERVATION = windows_identity.WindowsFixedDirectoryRead(
                    original.raw_by_name, nested_receipt
                )
                with self.assertRaisesRegex(
                    supervisor.P0ActualSupervisorExecutionError,
                    "overclaims forbidden capability",
                ):
                    self._execute()

    def test_deeply_nested_capability_injection_is_rejected(self) -> None:
        global _FAKE_OBSERVATION
        original = _FAKE_OBSERVATION
        nested_material = {
            key: item
            for key, item in copy.deepcopy(original.receipt).items()
            if key != "receipt_sha256"
        }
        nested_material["members"][0]["diagnostic"] = {
            "chain": [{"actual_authority_granted": True}]
        }
        nested_receipt = {
            **nested_material,
            "receipt_sha256": _canonical_sha256(nested_material),
        }
        _FAKE_OBSERVATION = windows_identity.WindowsFixedDirectoryRead(
            original.raw_by_name, nested_receipt
        )
        with self.assertRaisesRegex(
            supervisor.P0ActualSupervisorExecutionError,
            "overclaims forbidden capability",
        ):
            self._execute()

    def test_handle_receipt_root_and_member_cross_bindings_are_required(self) -> None:
        global _FAKE_OBSERVATION
        original = _FAKE_OBSERVATION
        variants: list[tuple[str, dict[str, object]]] = []

        wrong_root = copy.deepcopy(original.receipt)
        wrong_root["root_file_id"] = "f" * 32
        variants.append(("root", wrong_root))

        missing_member = copy.deepcopy(original.receipt)
        missing_member["members"].pop()
        variants.append(("member-count", missing_member))

        wrong_member_hash = copy.deepcopy(original.receipt)
        wrong_member_hash["members"][0]["sha256"] = "f" * 64
        variants.append(("member-hash", wrong_member_hash))

        for label, variant in variants:
            with self.subTest(label):
                material = {
                    key: item for key, item in variant.items() if key != "receipt_sha256"
                }
                variant = {
                    **material,
                    "receipt_sha256": _canonical_sha256(material),
                }
                _FAKE_OBSERVATION = windows_identity.WindowsFixedDirectoryRead(
                    original.raw_by_name, variant
                )
                with self.assertRaises(supervisor.P0ActualSupervisorExecutionError):
                    self._execute()

    def test_a_receipt_raw_cross_binding_rejects_self_hashed_swapped_result(self) -> None:
        original = a_event_bytes.verify_a_event_bytes

        def swapped_result(*args: object, **kwargs: object) -> dict[str, object]:
            result = original(*args, **kwargs)
            material = {
                key: item for key, item in result.items() if key != "receipt_sha256"
            }
            material["a_context_file_sha256"] = "f" * 64
            return {
                **material,
                "receipt_sha256": _canonical_sha256(material),
            }

        with mock.patch.object(
            a_event_bytes, "verify_a_event_bytes", new=swapped_result
        ), mock.patch.object(
            windows_identity,
            "read_windows_fixed_p0_packet_directory",
            new=_fake_read,
        ):
            manifest = supervisor.build_local_packet_validator_measurement_manifest()
            with self.assertRaisesRegex(
                supervisor.P0ActualSupervisorExecutionError,
                "A event receipt/raw input cross-binding mismatch",
            ):
                self._execute(measurement_manifest=manifest)

    def test_presented_projection_extra_and_truncated_members_are_rejected(self) -> None:
        extra = copy.deepcopy(self.execution_receipt)
        extra["raw_member_projection"].append(
            {
                "index": 14,
                "role": "unexpected",
                "path": "unexpected.bin",
                "bytes": 1,
                "sha256": "f" * 64,
            }
        )
        extra["raw_member_projection_sha256"] = _canonical_sha256(
            extra["raw_member_projection"]
        )

        truncated = copy.deepcopy(self.execution_receipt)
        truncated["raw_member_projection"].pop()
        truncated["raw_member_projection_sha256"] = _canonical_sha256(
            truncated["raw_member_projection"]
        )

        for label, value in (("extra", extra), ("truncated", truncated)):
            with self.subTest(label), self.assertRaisesRegex(
                supervisor.P0ActualSupervisorExecutionError,
                "raw member count mismatch",
            ):
                supervisor.validate_presented_packet_supervisor_receipt(
                    _rehash_receipt(value)
                )

    def test_presented_session_run_nonce_must_match_execution_genesis(self) -> None:
        variants = (
            ("session_id", "SESSION:SWAPPED"),
            ("run_id", "RUN:SWAPPED"),
            ("nonce_commitment_sha256", "f" * 64),
        )
        for field, value in variants:
            tampered = copy.deepcopy(self.execution_receipt)
            tampered[field] = value
            with self.subTest(field), self.assertRaisesRegex(
                supervisor.P0ActualSupervisorExecutionError,
                "execution genesis binding mismatch",
            ):
                supervisor.validate_presented_packet_supervisor_receipt(
                    _rehash_receipt(tampered)
                )

    def test_presented_step_omission_reorder_and_hash_break_are_rejected(self) -> None:
        variants: list[tuple[str, dict[str, object]]] = []

        omitted = copy.deepcopy(self.execution_receipt)
        omitted["step_trace"].pop()
        variants.append(("omission", _rehash_receipt(omitted)))

        reordered = copy.deepcopy(self.execution_receipt)
        reordered["step_trace"][0], reordered["step_trace"][1] = (
            reordered["step_trace"][1],
            reordered["step_trace"][0],
        )
        variants.append(("reorder", _rehash_receipt(reordered)))

        broken = copy.deepcopy(self.execution_receipt)
        broken["step_trace"][2]["input_binding_sha256"] = "e" * 64
        variants.append(("hash-break", _rehash_receipt(broken)))

        for label, variant in variants:
            with self.subTest(label), self.assertRaises(
                supervisor.P0ActualSupervisorExecutionError
            ):
                supervisor.validate_presented_packet_supervisor_receipt(variant)

    @unittest.skipUnless(os.name == "nt", "Windows handle integration requires Windows")
    def test_real_windows_handle_capture_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "packet"
            root.mkdir()
            (root / packet_contract.PACKET_MANIFEST_FILENAME).write_bytes(
                self.manifest_bytes
            )
            for name, raw in self.children.items():
                (root / name).write_bytes(raw)
            identity = windows_identity.observe_windows_directory_identity(root)
            measurements = (
                supervisor.build_local_packet_validator_measurement_manifest()
            )
            receipt = supervisor.execute_packet_supervisor_trace(
                packet_dir=root,
                expected_root_final_path=identity.final_path,
                expected_root_volume_serial=identity.volume_serial,
                expected_root_file_id=identity.file_id,
                expected_manifest_sha256=self.manifest_sha256,
                expected_origin=packet_contract.EXAMPLE_ORIGIN,
                session_id="SESSION:WINDOWS:01",
                run_id="RUN:WINDOWS:01",
                nonce_commitment_sha256="4" * 64,
                expected_validator_measurement_manifest=measurements,
            )
        self.assertTrue(receipt["packet_side_execution_trace_verified"])
        self.assertFalse(receipt["filesystem_handle_trust_verified"])
        self.assertFalse(receipt["actual_authority_granted"])


if __name__ == "__main__":
    unittest.main()
