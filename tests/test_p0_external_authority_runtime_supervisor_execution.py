from __future__ import annotations

import base64
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import inspect
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

from llm_batch.grounding import p0_actual_authority_contract as authority
from llm_batch.grounding import p0_actual_authority_supervisor_execution as combined
from llm_batch.grounding import p0_actual_owner_root_preauthorization as preauth
from llm_batch.grounding import p0_actual_packet_contract as packet
from llm_batch.grounding import p0_actual_registry_contract as registry
from llm_batch.grounding import p0_actual_supervisor_execution_contract as packet_supervisor
from llm_batch.grounding import p0_external_authority_runtime_supervisor_execution as external_runtime
from llm_batch.grounding import p0_external_owner_trust_execution as external
from llm_batch.grounding import p0_windows_fixed_directory_identity as windows
from llm_batch.grounding import p0_windows_runtime_evidence as runtime
from tests.p0_actual_authority_supervisor_fixtures import (
    KEY,
    ROOT_FILE_ID,
    ROOT_FINAL_PATH,
    ROOT_VOLUME_SERIAL,
    RUN_ID,
    SESSION_ID,
    _json_bytes,
    build_coordinated_actual_fixture,
)


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _rehash_external(value: dict[str, object]) -> dict[str, object]:
    material = deepcopy(value)
    material.pop("artifact_sha256", None)
    return {**material, "artifact_sha256": external.canonical_sha256(material)}


class ExternalAuthorityRuntimeSupervisorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = build_coordinated_actual_fixture()

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name)
        self.store = base / "external-trust"
        self.run_root = base / "run"
        self.packet_root = base / "packet"
        for path in (self.store, self.run_root, self.packet_root):
            path.mkdir()
        self.category_roots: dict[str, Path] = {}
        for index, category in enumerate(runtime.REQUIRED_PROTECTED_CATEGORIES):
            path = base / f"protected-{index}"
            path.mkdir()
            self.category_roots[category] = path
        (self.store / external.NONCE_LEDGER_DIRECTORY).mkdir()
        nonce_ledger_info = os.stat(self.store / external.NONCE_LEDGER_DIRECTORY)

        now = datetime.now(timezone.utc).replace(microsecond=0)
        self.preauthorization = deepcopy(self.fixture.preauthorization)
        self.preauthorization.update(
            {
                "issued_at": _utc(now - timedelta(hours=2)),
                "not_before": _utc(now - timedelta(hours=1)),
                "expires_at": _utc(now + timedelta(hours=12)),
            }
        )
        self.preauthorization["preauthorization_signature_sha256"] = (
            preauth.sign_preauthorization(self.preauthorization, KEY)
        )
        self.preauthorization = preauth.with_artifact_hash(self.preauthorization)

        anchor = _rehash_external(
            {
                "schema_version": external.TRUST_ANCHOR_SCHEMA,
                "store_id": "integration-external-owner-store-001",
                "key_id": self.preauthorization["key_id"],
                "algorithm": "HMAC-SHA256",
                "key_fingerprint_sha256": hashlib.sha256(KEY).hexdigest(),
                "key_material_base64": base64.b64encode(KEY).decode("ascii"),
                "owner_principal_sha256": self.preauthorization[
                    "owner_principal_sha256"
                ],
                "owner_anchor_sha256": self.preauthorization["owner_anchor_sha256"],
                "nonce_ledger_device_decimal": str(nonce_ledger_info.st_dev),
                "nonce_ledger_inode_decimal": str(nonce_ledger_info.st_ino),
                "valid_from": _utc(now - timedelta(hours=1)),
                "valid_to": _utc(now + timedelta(days=1)),
            }
        )
        revocation = _rehash_external(
            {
                "schema_version": external.REVOCATION_SNAPSHOT_SCHEMA,
                "store_id": anchor["store_id"],
                "snapshot_id": "integration-revocation-snapshot-001",
                "sequence": 1,
                "issued_at": _utc(now - timedelta(hours=2)),
                "valid_from": _utc(now - timedelta(hours=1)),
                "valid_to": _utc(now + timedelta(hours=12)),
                "revoked_key_ids": [],
                "revoked_owner_anchor_sha256": [],
            }
        )
        (self.store / external.TRUST_ANCHOR_FILENAME).write_bytes(
            external.json_file_bytes(anchor)
        )
        (self.store / external.REVOCATION_SNAPSHOT_FILENAME).write_bytes(
            external.json_file_bytes(revocation)
        )

    def _expected_effective_paths(self) -> list[str]:
        parent = self.preauthorization["protected_roots"][0][
            "final_volume_guid_path"
        ]
        return [
            f"{parent}\\{row['relative_root']}"
            for row in self.preauthorization["category_root_map"]
        ]

    def _runtime_raw_evidence(
        self, *, path_mismatch: bool = False
    ) -> runtime._RuntimeRawEvidence:
        paths = self._expected_effective_paths()
        categories: list[runtime._CategoryEvidence] = []
        for index, category in enumerate(runtime.REQUIRED_PROTECTED_CATEGORIES):
            observed = paths[index]
            if path_mismatch and index == 0:
                observed += "-swapped"
            identity = runtime._Identity(
                observed,
                1000 + index,
                f"{index + 1:032x}",
                False,
            )
            unavailable_usn = runtime._Usn(
                False, None, None, None, None, None, 5
            )
            inventory = runtime._Inventory(
                True,
                hashlib.sha256(category.encode("ascii")).hexdigest(),
                0,
                False,
                None,
            )
            categories.append(
                runtime._CategoryEvidence(
                    category,
                    str(self.category_roots[category]),
                    identity,
                    identity,
                    None,
                    unavailable_usn,
                    unavailable_usn,
                    inventory,
                    inventory,
                    runtime._WatchOutcome(
                        False, False, None, None, False, False, True, (), None
                    ),
                    runtime._WatchOutcome(
                        False, False, None, None, False, False, True, (), None
                    ),
                    runtime._WriteProbe(
                        False,
                        None,
                        runtime._FILE_ADD_FILE | runtime._FILE_ADD_SUBDIRECTORY,
                        False,
                        False,
                        None,
                    ),
                )
            )
        return runtime._RuntimeRawEvidence(
            True,
            10_000_000,
            tuple(
                (phase, index + 1)
                for index, phase in enumerate(runtime._PHASES)
            ),
            False,
            False,
            False,
            tuple(categories),
            ("controlled integration observer is intentionally incomplete",),
        )

    def _mint_runtime_state(
        self, operation: object, *, path_mismatch: bool = False
    ) -> runtime._RuntimeExecutionState:
        self.assertTrue(callable(operation))
        result: object = None
        error: BaseException | None = None
        traceback: object = None
        try:
            result = operation()  # type: ignore[operator]
        except BaseException as exc:
            error = exc
            traceback = exc.__traceback__
        return runtime._issue_execution_state(
            self._runtime_raw_evidence(path_mismatch=path_mismatch),
            result,
            error,
            traceback,
            False,
        )

    def _kwargs(self) -> dict[str, object]:
        packet_measurement = (
            packet_supervisor.build_local_packet_validator_measurement_manifest()
        )
        combined_measurement = (
            combined.build_local_authority_supervisor_measurement_manifest()
        )
        return {
            "trust_store_dir": self.store,
            "run_root": self.run_root,
            "protected_category_roots": self.category_roots,
            "packet_dir": self.packet_root,
            "expected_packet_root_final_path": ROOT_FINAL_PATH,
            "expected_packet_root_volume_serial": ROOT_VOLUME_SERIAL,
            "expected_packet_root_file_id": ROOT_FILE_ID,
            "expected_packet_manifest_sha256": self.fixture.manifest_sha256,
            "authority_raw_by_filename": self.fixture.authority_raw_by_filename,
            "annotation_event_bytes": self.fixture.annotation_event_bytes,
            "owner_root_preauthorization_bytes": _json_bytes(self.preauthorization),
            "parser_provenance_authorization_bytes": _json_bytes(
                self.fixture.provenance
            ),
            "terminal_bridge_attestation_bytes": _json_bytes(self.fixture.terminal),
            "expected_authority_origin": authority.ACTUAL_ORIGIN,
            "expected_packet_origin": packet.ACTUAL_ORIGIN,
            "expected_event_origin": registry.ACTUAL_ORIGIN,
            "foundation_manifest_sha256": self.fixture.foundation_manifest_sha256,
            "foundation_receipt_sha256": self.fixture.foundation_receipt_sha256,
            "session_id": SESSION_ID,
            "run_id": RUN_ID,
            "nonce_commitment_sha256": external.nonce_commitment_sha256(
                self.preauthorization["nonce"]
            ),
            "expected_packet_validator_measurement_manifest": packet_measurement,
            "expected_combined_validator_measurement_manifest": combined_measurement,
        }

    def _execute(self, *, path_mismatch: bool = False) -> dict[str, object]:
        def execute_runtime(
            _roots: object,
            operation: object,
            *,
            impersonate_operation: bool,
        ) -> runtime._RuntimeExecutionState:
            self.assertFalse(impersonate_operation)
            return self._mint_runtime_state(
                operation,
                path_mismatch=path_mismatch,
            )

        with ExitStack() as stack:
            stack.enter_context(
                mock.patch.object(
                    windows,
                    "read_windows_fixed_p0_packet_directory",
                    new=lambda *args, **kwargs: self.fixture.observation,
                )
            )
            stack.enter_context(
                mock.patch.object(
                    runtime,
                    "_execute_windows_runtime_evidence_state",
                    new=execute_runtime,
                )
            )
            return external_runtime.execute_external_authority_runtime_supervisor_trace(
                **self._kwargs()
            )

    def test_store_key_nonce_and_combined_execution_are_cross_bound_no_go(self) -> None:
        receipt = self._execute()
        self.assertEqual(receipt["gate_status"], external_runtime.GATE_STATUS)
        self.assertTrue(receipt["signature_verified_with_store_key"])
        self.assertTrue(receipt["single_use_replay_consumed"])
        self.assertTrue(receipt["nonce_ledger_action_applied"])
        self.assertTrue(receipt["combined_direct_local_execution_observed"])
        self.assertTrue(
            receipt["protected_category_final_path_projection_match"]
        )
        self.assertFalse(receipt["runtime_noninterference_verified"])
        self.assertFalse(receipt["external_owner_trust_verified"])
        self.assertFalse(receipt["actual_authority_granted"])
        self.assertEqual(
            receipt["credited_counts"],
            {"actual_source_claim_count": 0, "actual_a_context_review_count": 0},
        )
        material = dict(receipt)
        stored = material.pop("receipt_sha256")
        self.assertEqual(stored, external_runtime.canonical_sha256(material))

    def test_replay_is_burned_before_second_combined_execution(self) -> None:
        self._execute()
        with self.assertRaisesRegex(ValueError, "already consumed"):
            self._execute()

    def test_combined_failure_burns_nonce_and_retry_never_reenters_operation(self) -> None:
        class MarkerError(RuntimeError):
            pass

        operation_calls = 0

        def failed_runtime(
            _roots: object,
            operation: object,
            *,
            impersonate_operation: bool,
        ) -> runtime._RuntimeExecutionState:
            nonlocal operation_calls
            self.assertFalse(impersonate_operation)
            operation_calls += 1
            return self._mint_runtime_state(operation)

        with mock.patch.object(
            runtime,
            "_execute_windows_runtime_evidence_state",
            new=failed_runtime,
        ), mock.patch.object(
            combined,
            "execute_authority_supervisor_trace",
            side_effect=MarkerError("combined failed after nonce consumption"),
        ):
            with self.assertRaisesRegex(MarkerError, "combined failed"):
                external_runtime.execute_external_authority_runtime_supervisor_trace(
                    **self._kwargs()
                )
            with self.assertRaisesRegex(ValueError, "already consumed"):
                external_runtime.execute_external_authority_runtime_supervisor_trace(
                    **self._kwargs()
                )
        self.assertEqual(operation_calls, 1)

    def test_simple_namespace_runtime_state_is_rejected_after_operation(self) -> None:
        operation_calls = 0

        def forged_runtime(
            _roots: object,
            operation: object,
            *,
            impersonate_operation: bool,
        ) -> SimpleNamespace:
            nonlocal operation_calls
            self.assertFalse(impersonate_operation)
            operation_calls += 1
            result = operation()
            return SimpleNamespace(
                operation_result=result,
                operation_exception=None,
                operation_traceback=None,
                detached_receipt={},
            )

        with mock.patch.object(
            windows,
            "read_windows_fixed_p0_packet_directory",
            new=lambda *args, **kwargs: self.fixture.observation,
        ), mock.patch.object(
            runtime,
            "_execute_windows_runtime_evidence_state",
            new=forged_runtime,
        ):
            with self.assertRaisesRegex(ValueError, "was not minted"):
                external_runtime.execute_external_authority_runtime_supervisor_trace(
                    **self._kwargs()
                )
        self.assertEqual(operation_calls, 1)

    @unittest.skipUnless(os.name == "nt", "requires the real Windows runtime witness")
    def test_real_windows_runtime_witness_wraps_combined_and_stays_no_go(self) -> None:
        with mock.patch.object(
            windows,
            "read_windows_fixed_p0_packet_directory",
            new=lambda *args, **kwargs: self.fixture.observation,
        ):
            receipt = (
                external_runtime.execute_external_authority_runtime_supervisor_trace(
                    **self._kwargs()
                )
            )
        self.assertTrue(receipt["runtime_witness_same_process_execution_observed"])
        self.assertTrue(receipt["qpc_monotonic_timeline_verified"])
        self.assertFalse(receipt["runtime_noninterference_verified"])
        self.assertFalse(receipt["parser_runtime_execution_verified"])
        self.assertFalse(receipt["external_owner_trust_verified"])
        self.assertFalse(receipt["actual_authority_granted"])
        self.assertEqual(receipt["gate_status"], external_runtime.GATE_STATUS)

    def test_runtime_root_swap_cannot_create_external_root_trust(self) -> None:
        receipt = self._execute(path_mismatch=True)
        self.assertFalse(
            receipt["protected_category_final_path_projection_match"]
        )
        self.assertFalse(receipt["external_root_identity_pin_verified"])

    def test_combined_child_receipt_self_hash_is_recomputed(self) -> None:
        original = combined.execute_authority_supervisor_trace

        def tampered_combined(**kwargs: object) -> dict[str, object]:
            receipt = original(**kwargs)
            receipt["unhashed_injected_field"] = "forged"
            return receipt

        with mock.patch.object(
            combined,
            "execute_authority_supervisor_trace",
            side_effect=tampered_combined,
        ):
            with self.assertRaisesRegex(ValueError, "self-hash mismatch"):
                self._execute()

    def test_public_api_has_no_key_or_child_receipt_state_injection(self) -> None:
        signature = inspect.signature(
            external_runtime.execute_external_authority_runtime_supervisor_trace
        )
        forbidden = {
            "key",
            "trusted_key",
            "trust_state",
            "runtime_state",
            "combined_receipt",
            "runtime_receipt",
            "external_trust_receipt",
        }
        self.assertTrue(forbidden.isdisjoint(signature.parameters))
        self.assertNotIn("kwargs", signature.parameters)

    def test_post_mint_trust_invariant_failure_discards_key_state(self) -> None:
        before = len(external._ISSUED_STATE_RECORDS)
        with mock.patch.object(
            external_runtime,
            "_reject_trust_overclaim",
            side_effect=external_runtime.P0ExternalAuthorityRuntimeSupervisorError(
                "forced post-mint invariant failure"
            ),
        ):
            with self.assertRaisesRegex(ValueError, "post-mint invariant"):
                external_runtime.execute_external_authority_runtime_supervisor_trace(
                    **self._kwargs()
                )
        self.assertEqual(len(external._ISSUED_STATE_RECORDS), before)

    def test_presented_receipt_is_downgraded_and_fake_go_is_rejected(self) -> None:
        receipt = self._execute()
        presented = external_runtime.validate_presented_external_authority_runtime_receipt(
            receipt
        )
        self.assertTrue(presented["presented_structure_verified"])
        self.assertFalse(presented["underlying_execution_verified"])
        self.assertFalse(presented["single_use_replay_consumed"])
        self.assertFalse(presented["runtime_noninterference_verified"])

        fake = deepcopy(receipt)
        fake["actual_authority_granted"] = True
        material = dict(fake)
        material.pop("receipt_sha256", None)
        fake["receipt_sha256"] = external_runtime.canonical_sha256(material)
        with self.assertRaisesRegex(ValueError, "fixed invariant mismatch"):
            external_runtime.validate_presented_external_authority_runtime_receipt(fake)

        missing_binding = deepcopy(receipt)
        missing_binding.pop("runtime_witness_binding")
        missing_binding.pop("receipt_sha256")
        missing_binding["receipt_sha256"] = external_runtime.canonical_sha256(
            missing_binding
        )
        with self.assertRaisesRegex(ValueError, "field inventory mismatch"):
            external_runtime.validate_presented_external_authority_runtime_receipt(
                missing_binding
            )

        unknown_schema = deepcopy(receipt)
        unknown_schema["external_trust_binding"]["schema"] = "attacker_schema_v1"
        unknown_schema["child_bindings_sha256"] = external_runtime.canonical_sha256(
            [
                unknown_schema["external_trust_binding"],
                unknown_schema["runtime_witness_binding"],
                unknown_schema["combined_supervisor_binding"],
            ]
        )
        unknown_schema.pop("receipt_sha256")
        unknown_schema["receipt_sha256"] = external_runtime.canonical_sha256(
            unknown_schema
        )
        with self.assertRaisesRegex(ValueError, "external_trust_binding is invalid"):
            external_runtime.validate_presented_external_authority_runtime_receipt(
                unknown_schema
            )

        contradictory = deepcopy(receipt)
        contradictory["bounded_runtime_noninterference_verified"] = True
        contradictory.pop("receipt_sha256")
        contradictory["receipt_sha256"] = external_runtime.canonical_sha256(
            contradictory
        )
        with self.assertRaisesRegex(ValueError, "fixed invariant mismatch"):
            external_runtime.validate_presented_external_authority_runtime_receipt(
                contradictory
            )

    def test_bom_duplicate_nonfinite_and_category_omission_fail_before_nonce(self) -> None:
        base = _json_bytes(self.preauthorization)
        variants = (
            b"\xef\xbb\xbf" + base,
            base.replace(b"{", b'{"schema_version":"duplicate",', 1),
            base.replace(b"{", b'{"poison":NaN,', 1),
        )
        for raw in variants:
            with self.subTest(raw=raw[:20]):
                kwargs = self._kwargs()
                kwargs["owner_root_preauthorization_bytes"] = raw
                with self.assertRaises(ValueError):
                    external_runtime.execute_external_authority_runtime_supervisor_trace(
                        **kwargs
                    )
        missing = dict(self.category_roots)
        missing.pop(runtime.REQUIRED_PROTECTED_CATEGORIES[-1])
        kwargs = self._kwargs()
        kwargs["protected_category_roots"] = missing
        with self.assertRaisesRegex(ValueError, "exact ordered category"):
            external_runtime.execute_external_authority_runtime_supervisor_trace(**kwargs)
        nonce_dir = self.store / external.NONCE_LEDGER_DIRECTORY
        self.assertEqual(list(nonce_dir.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
