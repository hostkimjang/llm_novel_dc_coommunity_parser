from __future__ import annotations

from copy import deepcopy
from contextlib import ExitStack
from dataclasses import replace
import inspect
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from llm_batch.grounding import p0_actual_authority_bridge_contract as bridge
from llm_batch.grounding import p0_actual_authority_contract as authority
from llm_batch.grounding import p0_actual_authority_supervisor_execution as combined
from llm_batch.grounding import p0_actual_owner_root_preauthorization as preauth
from llm_batch.grounding import p0_actual_packet_contract as packet
from llm_batch.grounding import p0_actual_registry_contract as registry
from llm_batch.grounding import p0_actual_supervisor_execution_contract as packet_supervisor
from llm_batch.grounding import p0_windows_fixed_directory_identity as windows
from tests.p0_actual_authority_supervisor_fixtures import (
    KEY,
    ROOT_FILE_ID,
    ROOT_FINAL_PATH,
    ROOT_VOLUME_SERIAL,
    RUN_ID,
    SESSION_ID,
    _complete_authority_rows,
    _json_bytes,
    _rehash,
    build_coordinated_actual_fixture,
)


class ActualAuthoritySupervisorExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = build_coordinated_actual_fixture()

    def _execute(
        self,
        *,
        raw_overrides: dict[str, object] | None = None,
        bridge_replacement: object | None = None,
        packet_replacement: object | None = None,
    ) -> dict[str, object]:
        values: dict[str, object] = self.fixture.raw_kwargs()
        if raw_overrides:
            values.update(raw_overrides)
        with ExitStack() as stack:
            stack.enter_context(
                mock.patch.object(
                    windows,
                    "read_windows_fixed_p0_packet_directory",
                    new=lambda *args, **kwargs: self.fixture.observation,
                )
            )
            if bridge_replacement is not None:
                stack.enter_context(
                    mock.patch.object(
                        bridge,
                        "validate_authority_bridge_bundle",
                        new=bridge_replacement,
                    )
                )
            if packet_replacement is not None:
                stack.enter_context(
                    mock.patch.object(
                        packet_supervisor,
                        "_execute_packet_supervisor_state",
                        new=packet_replacement,
                    )
                )
            packet_measurement = (
                packet_supervisor.build_local_packet_validator_measurement_manifest()
            )
            combined_measurement = (
                combined.build_local_authority_supervisor_measurement_manifest()
            )
            return combined.execute_authority_supervisor_trace(
                packet_dir="unused-by-controlled-observation",
                expected_packet_root_final_path=ROOT_FINAL_PATH,
                expected_packet_root_volume_serial=ROOT_VOLUME_SERIAL,
                expected_packet_root_file_id=ROOT_FILE_ID,
                expected_packet_manifest_sha256=self.fixture.manifest_sha256,
                **values,
                expected_authority_origin=authority.ACTUAL_ORIGIN,
                expected_packet_origin=packet.ACTUAL_ORIGIN,
                expected_event_origin=registry.ACTUAL_ORIGIN,
                foundation_manifest_sha256=self.fixture.foundation_manifest_sha256,
                foundation_receipt_sha256=self.fixture.foundation_receipt_sha256,
                session_id=SESSION_ID,
                run_id=RUN_ID,
                nonce_commitment_sha256=self.fixture.nonce_commitment_sha256,
                expected_packet_validator_measurement_manifest=packet_measurement,
                expected_combined_validator_measurement_manifest=combined_measurement,
                key=KEY,
            )

    @staticmethod
    def _reseal_presented(row: dict[str, object]) -> dict[str, object]:
        material = deepcopy(row)
        material.pop("receipt_sha256", None)
        material["receipt_sha256"] = combined.canonical_sha256(material)
        return material

    def test_direct_controlled_40_plus_20_bridge_is_zero_credit_no_go(self) -> None:
        receipt = self._execute()
        self.assertEqual(len(receipt["step_trace"]), 7)
        self.assertEqual(
            receipt["gate_status"],
            "DIRECT_LOCAL_AUTHORITY_BRIDGE_PASS_EXTERNAL_TRUST_NO_GO",
        )
        self.assertEqual(
            receipt["credited_counts"],
            {"actual_source_claim_count": 0, "actual_a_context_review_count": 0},
        )
        self.assertTrue(receipt["parser_binding"]["parser_receipt_byte_exact_cross_binding_verified"])
        self.assertTrue(receipt["parser_binding"]["parser_receipt_semantic_cross_binding_verified"])
        self.assertFalse(receipt["runtime_noninterference_verified"])
        self.assertFalse(receipt["parser_runtime_execution_verified"])
        for field in combined._FALSE_FIELDS:
            self.assertIs(receipt[field], False, field)
        parser_raw = self.fixture.children["parser_receipt.json"]
        authority_parser_raw = self.fixture.authority_raw_by_filename[
            authority.AUTHORITY_EXAMPLE_FILES_V2["parser_receipt"]
        ]
        self.assertEqual(parser_raw, authority_parser_raw)
        # This parser-owned self-claim is needed by the structural route contract;
        # it is not an OS/runtime witness and the combined boundary stays false.
        self.assertTrue(json.loads(parser_raw)["runtime_noninterference_verified"])

    def test_public_signature_accepts_no_receipt_or_state_injection(self) -> None:
        signature = inspect.signature(combined.execute_authority_supervisor_trace)
        forbidden = {
            "packet_receipt",
            "packet_state",
            "authority_receipt",
            "authority_state",
            "foundation_result",
            "event_result",
            "bridge_receipt",
            "serialized_receipt",
        }
        self.assertTrue(forbidden.isdisjoint(signature.parameters))
        self.assertNotIn("kwargs", signature.parameters)
        self.assertIn("authority_raw_by_filename", signature.parameters)
        self.assertIn("owner_root_preauthorization_bytes", signature.parameters)

    def test_supplemental_raw_rejects_bom_duplicate_and_nonfinite(self) -> None:
        base = self.fixture.raw_kwargs()
        duplicate = base["parser_provenance_authorization_bytes"].replace(
            b"{", b'{"schema_version":"duplicate",', 1
        )
        nonfinite = base["terminal_bridge_attestation_bytes"].replace(
            b'"actual_source_claim_count":40',
            b'"actual_source_claim_count":NaN',
            1,
        )
        cases = (
            {"owner_root_preauthorization_bytes": b"\xef\xbb\xbf" + base["owner_root_preauthorization_bytes"]},
            {"parser_provenance_authorization_bytes": duplicate},
            {"terminal_bridge_attestation_bytes": nonfinite},
        )
        for override in cases:
            with self.subTest(override=next(iter(override))):
                with self.assertRaises(ValueError):
                    self._execute(raw_overrides=override)

    def test_parser_receipt_swap_is_rejected_before_bridge(self) -> None:
        rows = {
            role: json.loads(self.fixture.authority_raw_by_filename[path])
            for role, path in authority.AUTHORITY_EXAMPLE_FILES_V2.items()
        }
        swapped = deepcopy(rows["parser_receipt"])
        swapped["parser_run_id"] = "actual-parser-run-swapped"
        swapped = _rehash(swapped)
        rows = _complete_authority_rows(rows, swapped)
        authority_raw = {
            path: _json_bytes(rows[role])
            for role, path in authority.AUTHORITY_EXAMPLE_FILES_V2.items()
        }
        with self.assertRaisesRegex(ValueError, "byte-exact binding mismatch"):
            self._execute(raw_overrides={"authority_raw_by_filename": authority_raw})

    def test_preauthorization_run_and_nonce_replay_mismatch_are_rejected(self) -> None:
        for field, value in (("run_id", "other-run"), ("nonce", "other-nonce")):
            row = deepcopy(self.fixture.preauthorization)
            row[field] = value
            row["preauthorization_signature_sha256"] = preauth.sign_preauthorization(
                row, KEY
            )
            row = preauth.with_artifact_hash(row)
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "run/nonce/parser"):
                    self._execute(
                        raw_overrides={
                            "owner_root_preauthorization_bytes": _json_bytes(row)
                        }
                    )

    def test_provenance_swap_is_rejected(self) -> None:
        row = deepcopy(self.fixture.provenance)
        row["expected_parser_version"] = "swapped-parser-version"
        row["provenance_signature_sha256"] = (
            bridge.sign_parser_provenance_authorization(row, KEY)
        )
        row = bridge.with_artifact_hash(row)
        with self.assertRaisesRegex(ValueError, "preauthorization/provenance mismatch"):
            self._execute(
                raw_overrides={"parser_provenance_authorization_bytes": _json_bytes(row)}
            )

    def test_terminal_replay_swap_is_rejected(self) -> None:
        row = deepcopy(self.fixture.terminal)
        row["packet_receipt_sha256"] = "f" * 64
        row["bridge_signature_sha256"] = bridge.sign_terminal_bridge_attestation(
            row, KEY
        )
        row = bridge.with_artifact_hash(row)
        with self.assertRaises(ValueError):
            self._execute(
                raw_overrides={"terminal_bridge_attestation_bytes": _json_bytes(row)}
            )

    def test_fake_bridge_go_is_rejected_even_when_self_hashed(self) -> None:
        original = bridge.validate_authority_bridge_bundle

        def fake_go(*args: object, **kwargs: object) -> dict[str, object]:
            row = original(*args, **kwargs)
            row["actual_authority_granted"] = True
            row["gate_status"] = "GO_FAKE"
            material = {key: value for key, value in row.items() if key != "receipt_sha256"}
            return {**material, "receipt_sha256": bridge.canonical_sha256(material)}

        with self.assertRaisesRegex(ValueError, "authority overclaim"):
            self._execute(bridge_replacement=fake_go)

    def test_fake_packet_child_go_and_nested_true_are_rejected(self) -> None:
        original = packet_supervisor._execute_packet_supervisor_state

        def fake_child(*args: object, **kwargs: object) -> object:
            state = original(*args, **kwargs)
            row = combined._json_plain(state.public_receipt)
            row["actual_authority_granted"] = True
            row["gate_status"] = "GO_FAKE_CHILD"
            material = {key: value for key, value in row.items() if key != "receipt_sha256"}
            row = {**material, "receipt_sha256": combined.canonical_sha256(material)}
            return replace(state, public_receipt=row)

        with self.assertRaisesRegex(ValueError, "nested authority overclaim"):
            self._execute(packet_replacement=fake_child)

    def test_presented_receipt_is_strictly_structural_and_downgraded(self) -> None:
        receipt = self._execute()
        result = combined.validate_presented_authority_supervisor_receipt(receipt)
        self.assertTrue(result["presented_receipt_structurally_verified"])
        self.assertFalse(result["direct_local_validator_invocations_observed"])
        self.assertFalse(result["underlying_validator_execution_verified"])
        self.assertEqual(result["credited_counts"], {"actual_source_claim_count": 0, "actual_a_context_review_count": 0})

    def test_presented_rejects_truncation_genesis_swap_and_nested_true(self) -> None:
        original = self._execute()

        truncated = deepcopy(original)
        truncated["step_trace"].pop()
        truncated = self._reseal_presented(truncated)

        reordered = deepcopy(original)
        reordered["step_trace"][0], reordered["step_trace"][1] = (
            reordered["step_trace"][1],
            reordered["step_trace"][0],
        )
        reordered = self._reseal_presented(reordered)

        genesis_swap = deepcopy(original)
        genesis_swap["execution_genesis"]["run_id"] = "replayed-other-run"
        genesis_swap["execution_genesis_sha256"] = combined.canonical_sha256(
            genesis_swap["execution_genesis"]
        )
        genesis_swap = self._reseal_presented(genesis_swap)

        nested_true = deepcopy(original)
        nested_true["step_trace"][6]["output_binding"]["nested"] = {
            "actual_authority_granted": True
        }
        nested_true["step_trace"][6]["output_binding_sha256"] = combined.canonical_sha256(
            nested_true["step_trace"][6]["output_binding"]
        )
        step_material = {
            key: value
            for key, value in nested_true["step_trace"][6].items()
            if key != "step_sha256"
        }
        nested_true["step_trace"][6]["step_sha256"] = combined.canonical_sha256(
            step_material
        )
        nested_true["trace_head_sha256"] = nested_true["step_trace"][6]["step_sha256"]
        nested_true["result_bindings"][6] = {
            "step_index": 6,
            **nested_true["step_trace"][6]["output_binding"],
        }
        nested_true["result_bindings_sha256"] = combined.canonical_sha256(
            nested_true["result_bindings"]
        )
        nested_true = self._reseal_presented(nested_true)

        extra = deepcopy(original)
        extra["unexpected"] = True
        extra = self._reseal_presented(extra)

        projection = deepcopy(original)
        projection["authority_raw_projection"][0]["sha256"] = "e" * 64
        projection = self._reseal_presented(projection)

        for label, value in (
            ("truncated", truncated),
            ("reordered", reordered),
            ("genesis", genesis_swap),
            ("nested", nested_true),
            ("extra", extra),
            ("projection", projection),
        ):
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    combined.validate_presented_authority_supervisor_receipt(value)

    @unittest.skipUnless(os.name == "nt", "Windows handle integration requires Windows")
    def test_real_windows_handle_capture_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "packet"
            root.mkdir()
            (root / packet.PACKET_MANIFEST_FILENAME).write_bytes(
                self.fixture.manifest_bytes
            )
            for name, raw in self.fixture.children.items():
                (root / name).write_bytes(raw)
            identity = windows.observe_windows_directory_identity(root)
            packet_measurement = (
                packet_supervisor.build_local_packet_validator_measurement_manifest()
            )
            packet_state = packet_supervisor._execute_packet_supervisor_state(
                packet_dir=root,
                expected_root_final_path=identity.final_path,
                expected_root_volume_serial=identity.volume_serial,
                expected_root_file_id=identity.file_id,
                expected_manifest_sha256=self.fixture.manifest_sha256,
                expected_origin=packet.ACTUAL_ORIGIN,
                session_id=SESSION_ID,
                run_id=RUN_ID,
                nonce_commitment_sha256=self.fixture.nonce_commitment_sha256,
                expected_validator_measurement_manifest=packet_measurement,
            )

            preauthorization = deepcopy(self.fixture.preauthorization)
            preauthorization["allowed_packet_root"].update(
                {
                    "final_volume_guid_path": identity.final_path,
                    "volume_serial_decimal": str(identity.volume_serial),
                    "file_id_128_hex": identity.file_id,
                }
            )
            preauthorization["preauthorization_signature_sha256"] = (
                preauth.sign_preauthorization(preauthorization, KEY)
            )
            preauthorization = preauth.with_artifact_hash(preauthorization)

            terminal = deepcopy(self.fixture.terminal)
            terminal.update(
                {
                    "windows_packet_validation_receipt_sha256": (
                        packet_state.windows_packet_receipt["receipt_sha256"]
                    ),
                    "windows_root_final_path": identity.final_path,
                    "windows_root_volume_serial": str(identity.volume_serial),
                    "windows_root_file_id": identity.file_id,
                }
            )
            terminal["bridge_signature_sha256"] = (
                bridge.sign_terminal_bridge_attestation(terminal, KEY)
            )
            terminal = bridge.with_artifact_hash(terminal)

            combined_measurement = (
                combined.build_local_authority_supervisor_measurement_manifest()
            )
            receipt = combined.execute_authority_supervisor_trace(
                packet_dir=root,
                expected_packet_root_final_path=identity.final_path,
                expected_packet_root_volume_serial=identity.volume_serial,
                expected_packet_root_file_id=identity.file_id,
                expected_packet_manifest_sha256=self.fixture.manifest_sha256,
                authority_raw_by_filename=self.fixture.authority_raw_by_filename,
                annotation_event_bytes=self.fixture.annotation_event_bytes,
                owner_root_preauthorization_bytes=_json_bytes(preauthorization),
                parser_provenance_authorization_bytes=_json_bytes(
                    self.fixture.provenance
                ),
                terminal_bridge_attestation_bytes=_json_bytes(terminal),
                expected_authority_origin=authority.ACTUAL_ORIGIN,
                expected_packet_origin=packet.ACTUAL_ORIGIN,
                expected_event_origin=registry.ACTUAL_ORIGIN,
                foundation_manifest_sha256=self.fixture.foundation_manifest_sha256,
                foundation_receipt_sha256=self.fixture.foundation_receipt_sha256,
                session_id=SESSION_ID,
                run_id=RUN_ID,
                nonce_commitment_sha256=self.fixture.nonce_commitment_sha256,
                expected_packet_validator_measurement_manifest=packet_measurement,
                expected_combined_validator_measurement_manifest=combined_measurement,
                key=KEY,
            )
        self.assertTrue(receipt["direct_local_validator_invocations_observed"])
        self.assertFalse(receipt["filesystem_handle_binding_verified"])
        self.assertFalse(receipt["actual_authority_granted"])


if __name__ == "__main__":
    unittest.main()
