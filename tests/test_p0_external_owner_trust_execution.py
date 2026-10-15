from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import base64
import gc
import hashlib
import inspect
import json
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest import mock

from llm_batch.grounding import p0_actual_owner_root_preauthorization as preauth
from llm_batch.grounding import p0_external_owner_trust_execution as external
from tests.p0_actual_authority_supervisor_fixtures import (
    KEY,
    ROOT_FILE_ID,
    ROOT_FINAL_PATH,
    ROOT_VOLUME_SERIAL,
    RUN_ID,
    SESSION_ID,
    build_coordinated_actual_fixture,
)


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _rehash(value: dict[str, object]) -> dict[str, object]:
    material = deepcopy(value)
    material.pop("artifact_sha256", None)
    return {**material, "artifact_sha256": external.canonical_sha256(material)}


class ExternalOwnerTrustExecutionTests(unittest.TestCase):
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
        self.protected_root = base / "protected"
        for path in (
            self.store,
            self.run_root,
            self.packet_root,
            self.protected_root,
        ):
            path.mkdir()
        (self.store / external.NONCE_LEDGER_DIRECTORY).mkdir()
        nonce_ledger_info = os.stat(self.store / external.NONCE_LEDGER_DIRECTORY)

        now = datetime.now(timezone.utc).replace(microsecond=0)
        self.anchor = _rehash(
            {
                "schema_version": external.TRUST_ANCHOR_SCHEMA,
                "store_id": "test-external-owner-store-001",
                "key_id": self.fixture.preauthorization["key_id"],
                "algorithm": "HMAC-SHA256",
                "key_fingerprint_sha256": hashlib.sha256(KEY).hexdigest(),
                "key_material_base64": base64.b64encode(KEY).decode("ascii"),
                "owner_principal_sha256": self.fixture.preauthorization[
                    "owner_principal_sha256"
                ],
                "owner_anchor_sha256": self.fixture.preauthorization[
                    "owner_anchor_sha256"
                ],
                "nonce_ledger_device_decimal": str(nonce_ledger_info.st_dev),
                "nonce_ledger_inode_decimal": str(nonce_ledger_info.st_ino),
                "valid_from": _utc(now - timedelta(hours=1)),
                "valid_to": _utc(now + timedelta(days=1)),
            }
        )
        self.revocation = _rehash(
            {
                "schema_version": external.REVOCATION_SNAPSHOT_SCHEMA,
                "store_id": self.anchor["store_id"],
                "snapshot_id": "test-revocation-snapshot-001",
                "sequence": 1,
                "issued_at": _utc(now - timedelta(hours=2)),
                "valid_from": _utc(now - timedelta(hours=1)),
                "valid_to": _utc(now + timedelta(hours=12)),
                "revoked_key_ids": [],
                "revoked_owner_anchor_sha256": [],
            }
        )
        self.preauthorization = deepcopy(self.fixture.preauthorization)
        self.preauthorization.update(
            {
                "issued_at": _utc(now - timedelta(hours=2)),
                "not_before": _utc(now - timedelta(hours=1)),
                "expires_at": _utc(now + timedelta(hours=12)),
            }
        )
        self._resign_preauthorization()
        self._write_store_files()

    def _resign_preauthorization(self, key: bytes = KEY) -> None:
        self.preauthorization["preauthorization_signature_sha256"] = (
            preauth.sign_preauthorization(self.preauthorization, key)
        )
        self.preauthorization = preauth.with_artifact_hash(self.preauthorization)

    def _write_store_files(self) -> None:
        (self.store / external.TRUST_ANCHOR_FILENAME).write_bytes(
            external.json_file_bytes(self.anchor)
        )
        (self.store / external.REVOCATION_SNAPSHOT_FILENAME).write_bytes(
            external.json_file_bytes(self.revocation)
        )

    def _kwargs(self) -> dict[str, object]:
        return {
            "trust_store_dir": self.store,
            "run_root": self.run_root,
            "packet_root": self.packet_root,
            "protected_roots": [self.protected_root],
            "owner_root_preauthorization_bytes": external.json_file_bytes(
                self.preauthorization
            ),
            "session_id": SESSION_ID,
            "run_id": RUN_ID,
            "nonce_commitment_sha256": external.nonce_commitment_sha256(
                self.preauthorization["nonce"]
            ),
            "expected_packet_root_final_path": ROOT_FINAL_PATH,
            "expected_packet_root_volume_serial": ROOT_VOLUME_SERIAL,
            "expected_packet_root_file_id": ROOT_FILE_ID,
            "expected_parser_provenance": deepcopy(
                self.preauthorization["expected_provenance"]
            ),
        }

    def test_success_executes_store_signature_and_nonce_without_authority_overclaim(self) -> None:
        receipt = external.execute_external_owner_trust(**self._kwargs())
        self.assertEqual(receipt["schema_version"], external.EXECUTION_RECEIPT_SCHEMA)
        self.assertTrue(receipt["trust_store_filesystem_execution_observed"])
        self.assertTrue(receipt["signature_verified_with_store_key"])
        self.assertTrue(receipt["single_use_replay_consumed"])
        self.assertEqual(
            receipt["single_use_scope"],
            "CURRENT_PINNED_PRESENTED_STORE_FILESYSTEM_EXECUTION",
        )
        self.assertTrue(receipt["nonce_ledger_identity_pin_matched"])
        self.assertTrue(receipt["nonce_directory_namespace_guard_verified"])
        self.assertEqual(
            receipt["nonce_directory_rename_delete_guard_verified"], os.name == "nt"
        )
        self.assertFalse(receipt["cross_process_immutable_nonce_ledger_verified"])
        self.assertTrue(receipt["nonce_atomic_create_exclusive_verified"])
        self.assertTrue(receipt["nonce_record_file_flush_verified"])
        self.assertEqual(receipt["nonce_directory_entry_flush_verified"], os.name != "nt")
        self.assertFalse(receipt["power_loss_durable_replay_verified"])
        self.assertTrue(receipt["nonce_ledger_action_applied"])
        self.assertTrue(receipt["security_control_state_mutated"])
        self.assertFalse(receipt["protected_pipeline_action_applied"])
        self.assertTrue(receipt["revocation_snapshot_no_match_for_key_or_anchor"])
        self.assertFalse(receipt["filesystem_namespace_alias_resolution_verified"])
        for field in (
            "external_trust_store_verified",
            "revocation_current_verified",
            "trusted_time_verified",
            "external_owner_trust_verified",
            "external_root_identity_pin_verified",
            "filesystem_handle_trust_verified",
            "owner_authority_verified",
            "actual_authority_granted",
            "production_approval",
            "full_scan_approval",
            "p0_phase_exit",
            "action_applied",
        ):
            self.assertIs(receipt[field], False, field)
        material = dict(receipt)
        stored_hash = material.pop("receipt_sha256")
        self.assertEqual(stored_hash, external.canonical_sha256(material))
        self.assertEqual(receipt["credited_actual_source_claim_count"], 0)
        self.assertEqual(receipt["credited_actual_a_context_review_count"], 0)

    def test_public_api_and_receipt_do_not_expose_store_key(self) -> None:
        signature = inspect.signature(external.execute_external_owner_trust)
        self.assertNotIn("key", signature.parameters)
        self.assertNotIn("trusted_key", signature.parameters)
        issued_before = len(external._ISSUED_STATE_RECORDS)
        receipt = external.execute_external_owner_trust(**self._kwargs())
        self.assertEqual(len(external._ISSUED_STATE_RECORDS), issued_before)
        serialized = external.canonical_bytes(receipt)
        self.assertNotIn(KEY, serialized)
        self.assertNotIn(base64.b64encode(KEY), serialized)
        self.assertNotIn("key_material_base64", receipt)
        self.assertNotIn("_trusted_key", receipt)
        self.assertNotIn("trust_anchor_artifact_sha256", receipt)
        self.assertNotIn("trust_anchor_bytes_sha256", receipt)
        self.assertTrue(receipt["trust_anchor_full_hash_withheld_from_public_receipt"])
        self.assertNotIn("_ExternalOwnerTrustExecutionState", external.__all__)
        self.assertNotIn("_execute_external_owner_trust_state", external.__all__)

    def test_private_state_retains_store_key_for_same_process_only(self) -> None:
        state = external._execute_external_owner_trust_state(**self._kwargs())
        record = external._ISSUED_STATE_RECORDS[id(state)]
        self.assertTrue(state.public_receipt["signature_verified_with_store_key"])
        trusted_key = external._consume_external_owner_trust_state(
            state,
            expected_receipt_sha256=state.public_receipt["receipt_sha256"],
            expected_nonce_commitment_sha256=state.public_receipt[
                "nonce_commitment_sha256"
            ],
        )
        self.assertEqual(trusted_key, KEY)
        self.assertFalse(any(record.secret.key))
        self.assertFalse(any(record.secret.execution_seal))
        with self.assertRaisesRegex(
            external.P0ExternalOwnerTrustExecutionError, "already consumed"
        ):
            external._consume_external_owner_trust_state(
                state,
                expected_receipt_sha256=state.public_receipt["receipt_sha256"],
                expected_nonce_commitment_sha256=state.public_receipt[
                    "nonce_commitment_sha256"
                ],
            )

    def test_private_state_rejects_simplenamespace_forgery(self) -> None:
        state = external._execute_external_owner_trust_state(**self._kwargs())
        forged = SimpleNamespace(
            public_receipt=state.public_receipt,
            _execution_seal=state._execution_seal,
        )
        with self.assertRaisesRegex(
            external.P0ExternalOwnerTrustExecutionError, "exact module-issued type"
        ):
            external._consume_external_owner_trust_state(
                forged,
                expected_receipt_sha256=state.public_receipt["receipt_sha256"],
                expected_nonce_commitment_sha256=state.public_receipt[
                    "nonce_commitment_sha256"
                ],
            )
        self.assertEqual(
            external._consume_external_owner_trust_state(
                state,
                expected_receipt_sha256=state.public_receipt["receipt_sha256"],
                expected_nonce_commitment_sha256=state.public_receipt[
                    "nonce_commitment_sha256"
                ],
            ),
            KEY,
        )

    def test_private_state_receipt_tamper_burns_seal(self) -> None:
        state = external._execute_external_owner_trust_state(**self._kwargs())
        expected_receipt = state.public_receipt["receipt_sha256"]
        expected_nonce = state.public_receipt["nonce_commitment_sha256"]
        with self.assertRaises(TypeError):
            state.public_receipt["packet_root_tuple"]["file_id_128_hex"] = "f" * 32
        tampered = external._thaw_state_json(state.public_receipt)
        tampered["packet_root_tuple"]["file_id_128_hex"] = "f" * 32
        material = dict(tampered)
        material.pop("receipt_sha256")
        tampered["receipt_sha256"] = external.canonical_sha256(material)
        object.__setattr__(
            state,
            "public_receipt",
            external._freeze_state_json(tampered),
        )
        with self.assertRaisesRegex(
            external.P0ExternalOwnerTrustExecutionError, "seal binding mismatch"
        ):
            external._consume_external_owner_trust_state(
                state,
                expected_receipt_sha256=expected_receipt,
                expected_nonce_commitment_sha256=expected_nonce,
            )
        with self.assertRaisesRegex(
            external.P0ExternalOwnerTrustExecutionError, "already consumed"
        ):
            external._consume_external_owner_trust_state(
                state,
                expected_receipt_sha256=expected_receipt,
                expected_nonce_commitment_sha256=expected_nonce,
            )

    def test_private_state_wrong_nonce_binding_burns_seal(self) -> None:
        state = external._execute_external_owner_trust_state(**self._kwargs())
        with self.assertRaisesRegex(
            external.P0ExternalOwnerTrustExecutionError, "seal binding mismatch"
        ):
            external._consume_external_owner_trust_state(
                state,
                expected_receipt_sha256=state.public_receipt["receipt_sha256"],
                expected_nonce_commitment_sha256="f" * 64,
            )
        with self.assertRaisesRegex(
            external.P0ExternalOwnerTrustExecutionError, "already consumed"
        ):
            external._consume_external_owner_trust_state(
                state,
                expected_receipt_sha256=state.public_receipt["receipt_sha256"],
                expected_nonce_commitment_sha256=state.public_receipt[
                    "nonce_commitment_sha256"
                ],
            )

    def test_private_state_exact_clone_cannot_consume_or_discard_original(self) -> None:
        state = external._execute_external_owner_trust_state(**self._kwargs())
        clone = replace(state)
        self.assertIs(type(clone), type(state))
        self.assertIsNot(clone, state)
        self.assertEqual(clone._execution_seal, state._execution_seal)
        external._discard_external_owner_trust_state(clone)
        with self.assertRaisesRegex(
            external.P0ExternalOwnerTrustExecutionError,
            "copied",
        ):
            external._consume_external_owner_trust_state(
                clone,
                expected_receipt_sha256=state.public_receipt["receipt_sha256"],
                expected_nonce_commitment_sha256=state.public_receipt[
                    "nonce_commitment_sha256"
                ],
            )
        self.assertEqual(
            external._consume_external_owner_trust_state(
                state,
                expected_receipt_sha256=state.public_receipt["receipt_sha256"],
                expected_nonce_commitment_sha256=state.public_receipt[
                    "nonce_commitment_sha256"
                ],
            ),
            KEY,
        )

    def test_private_state_malformed_expected_value_burns_genuine_state(self) -> None:
        state = external._execute_external_owner_trust_state(**self._kwargs())
        with self.assertRaisesRegex(
            external.P0ExternalOwnerTrustExecutionError,
            "lowercase SHA-256",
        ):
            external._consume_external_owner_trust_state(
                state,
                expected_receipt_sha256=None,
                expected_nonce_commitment_sha256=state.public_receipt[
                    "nonce_commitment_sha256"
                ],
            )
        with self.assertRaisesRegex(
            external.P0ExternalOwnerTrustExecutionError,
            "already consumed",
        ):
            external._consume_external_owner_trust_state(
                state,
                expected_receipt_sha256=state.public_receipt["receipt_sha256"],
                expected_nonce_commitment_sha256=state.public_receipt[
                    "nonce_commitment_sha256"
                ],
            )

    def test_private_state_forced_seal_tamper_burns(self) -> None:
        state = external._execute_external_owner_trust_state(**self._kwargs())
        record = external._ISSUED_STATE_RECORDS[id(state)]
        object.__setattr__(state, "_execution_seal", b"z" * 32)
        with self.assertRaisesRegex(
            external.P0ExternalOwnerTrustExecutionError,
            "seal binding mismatch",
        ):
            external._consume_external_owner_trust_state(
                state,
                expected_receipt_sha256=state.public_receipt["receipt_sha256"],
                expected_nonce_commitment_sha256=state.public_receipt[
                    "nonce_commitment_sha256"
                ],
            )
        self.assertFalse(any(record.secret.key))
        self.assertFalse(any(record.secret.execution_seal))

    def test_private_state_pid_mismatch_burns(self) -> None:
        state = external._execute_external_owner_trust_state(**self._kwargs())
        record = external._ISSUED_STATE_RECORDS[id(state)]
        record.secret.issuer_pid += 1
        with self.assertRaisesRegex(
            external.P0ExternalOwnerTrustExecutionError,
            "seal binding mismatch",
        ):
            external._consume_external_owner_trust_state(
                state,
                expected_receipt_sha256=state.public_receipt["receipt_sha256"],
                expected_nonce_commitment_sha256=state.public_receipt[
                    "nonce_commitment_sha256"
                ],
            )
        self.assertFalse(any(record.secret.key))
        self.assertFalse(any(record.secret.execution_seal))

    def test_private_state_discard_is_identity_scoped_and_idempotent(self) -> None:
        baseline = len(external._ISSUED_STATE_RECORDS)
        state = external._execute_external_owner_trust_state(**self._kwargs())
        record = external._ISSUED_STATE_RECORDS[id(state)]
        clone = replace(state)
        external._discard_external_owner_trust_state(clone)
        self.assertEqual(len(external._ISSUED_STATE_RECORDS), baseline + 1)
        external._discard_external_owner_trust_state(state)
        external._discard_external_owner_trust_state(state)
        self.assertEqual(len(external._ISSUED_STATE_RECORDS), baseline)
        self.assertFalse(any(record.secret.key))
        self.assertFalse(any(record.secret.execution_seal))
        with self.assertRaisesRegex(
            external.P0ExternalOwnerTrustExecutionError,
            "already consumed",
        ):
            external._consume_external_owner_trust_state(
                state,
                expected_receipt_sha256=state.public_receipt["receipt_sha256"],
                expected_nonce_commitment_sha256=state.public_receipt[
                    "nonce_commitment_sha256"
                ],
            )

    def test_private_state_gc_finalizer_removes_registry_and_burns(self) -> None:
        baseline = len(external._ISSUED_STATE_RECORDS)
        state = external._execute_external_owner_trust_state(**self._kwargs())
        record = external._ISSUED_STATE_RECORDS[id(state)]
        del state
        gc.collect()
        self.assertEqual(len(external._ISSUED_STATE_RECORDS), baseline)
        self.assertFalse(any(record.secret.key))
        self.assertFalse(any(record.secret.execution_seal))

    def test_private_state_sixteen_way_race_has_one_consumer(self) -> None:
        state = external._execute_external_owner_trust_state(**self._kwargs())
        receipt_sha = state.public_receipt["receipt_sha256"]
        nonce_sha = state.public_receipt["nonce_commitment_sha256"]
        barrier = threading.Barrier(16)

        def consume() -> str:
            barrier.wait()
            try:
                key = external._consume_external_owner_trust_state(
                    state,
                    expected_receipt_sha256=receipt_sha,
                    expected_nonce_commitment_sha256=nonce_sha,
                )
            except external.P0ExternalOwnerTrustExecutionError as exc:
                return str(exc)
            return "success" if key == KEY else "wrong-key"

        with ThreadPoolExecutor(max_workers=16) as executor:
            results = list(executor.map(lambda _: consume(), range(16)))
        self.assertEqual(results.count("success"), 1)
        self.assertEqual(
            sum("already consumed" in result for result in results),
            15,
        )
        self.assertNotIn("wrong-key", results)

    def test_nonce_record_cross_binds_complete_execution_tuple(self) -> None:
        receipt = external.execute_external_owner_trust(**self._kwargs())
        path = (
            self.store
            / external.NONCE_LEDGER_DIRECTORY
            / f"{receipt['nonce_commitment_sha256']}.json"
        )
        raw = path.read_bytes()
        record = json.loads(raw)
        self.assertEqual(record["session_id"], SESSION_ID)
        self.assertEqual(record["run_id"], RUN_ID)
        self.assertEqual(
            record["preauthorization_bytes_sha256"],
            hashlib.sha256(external.json_file_bytes(self.preauthorization)).hexdigest(),
        )
        self.assertEqual(
            record["parser_provenance_sha256"],
            external.canonical_sha256(self.preauthorization["expected_provenance"]),
        )
        self.assertEqual(record["packet_root_tuple"], receipt["packet_root_tuple"])
        self.assertEqual(
            record["trust_anchor_artifact_sha256"], self.anchor["artifact_sha256"]
        )
        self.assertEqual(
            record["trust_anchor_bytes_sha256"],
            hashlib.sha256(external.json_file_bytes(self.anchor)).hexdigest(),
        )
        self.assertEqual(
            record["revocation_snapshot_artifact_sha256"],
            receipt["revocation_snapshot_artifact_sha256"],
        )
        self.assertEqual(record["wall_clock_observed_at"], receipt["wall_clock_observed_at"])
        material = dict(record)
        artifact = material.pop("artifact_sha256")
        self.assertEqual(artifact, external.canonical_sha256(material))
        self.assertEqual(hashlib.sha256(raw).hexdigest(), receipt["nonce_record_bytes_sha256"])

    def test_reopen_replay_and_crash_reservation_fail_closed(self) -> None:
        kwargs = self._kwargs()
        external.execute_external_owner_trust(**kwargs)
        with self.assertRaisesRegex(external.P0ExternalOwnerTrustExecutionError, "already consumed"):
            external.execute_external_owner_trust(**kwargs)

        self.preauthorization["nonce"] = "crash-reserved-nonce-002"
        self._resign_preauthorization()
        kwargs = self._kwargs()
        commitment = kwargs["nonce_commitment_sha256"]
        reserved = self.store / external.NONCE_LEDGER_DIRECTORY / f"{commitment}.json"
        reserved.write_bytes(b"")
        with self.assertRaisesRegex(external.P0ExternalOwnerTrustExecutionError, "already consumed"):
            external.execute_external_owner_trust(**kwargs)

    def test_nonce_ledger_directory_replacement_cannot_reset_replay_state(self) -> None:
        kwargs = self._kwargs()
        external.execute_external_owner_trust(**kwargs)
        nonce_dir = self.store / external.NONCE_LEDGER_DIRECTORY
        retired = self.store.parent / "retired-nonce-ledger"
        os.replace(nonce_dir, retired)
        nonce_dir.mkdir()
        with self.assertRaisesRegex(
            external.P0ExternalOwnerTrustExecutionError, "filesystem identity"
        ):
            external.execute_external_owner_trust(**kwargs)
        self.assertEqual(len(list(retired.iterdir())), 1)
        self.assertEqual(len(list(nonce_dir.iterdir())), 0)

    def test_sixteen_way_race_has_exactly_one_success(self) -> None:
        kwargs = self._kwargs()

        def attempt(_: int) -> str:
            try:
                external.execute_external_owner_trust(**kwargs)
            except external.P0ExternalOwnerTrustExecutionError:
                return "rejected"
            return "success"

        with ThreadPoolExecutor(max_workers=16) as executor:
            results = list(executor.map(attempt, range(16)))
        self.assertEqual(results.count("success"), 1)
        self.assertEqual(results.count("rejected"), 15)
        records = list((self.store / external.NONCE_LEDGER_DIRECTORY).iterdir())
        self.assertEqual(len(records), 1)

    def test_fsync_failure_burns_nonce_and_retry_is_replay(self) -> None:
        kwargs = self._kwargs()
        with mock.patch.object(external.os, "fsync", side_effect=OSError("fault")):
            with self.assertRaisesRegex(external.P0ExternalOwnerTrustExecutionError, "failed closed"):
                external.execute_external_owner_trust(**kwargs)
        with self.assertRaisesRegex(external.P0ExternalOwnerTrustExecutionError, "already consumed"):
            external.execute_external_owner_trust(**kwargs)

    def test_trust_store_must_be_outside_every_supplied_root(self) -> None:
        for label, overrides in (
            ("run", {"run_root": self.store}),
            ("packet", {"packet_root": self.store}),
            ("protected", {"protected_roots": [self.store]}),
            ("store-under-run", {"run_root": self.store.parent}),
        ):
            kwargs = self._kwargs()
            kwargs.update(overrides)
            with self.subTest(label=label):
                with self.assertRaisesRegex(
                    external.P0ExternalOwnerTrustExecutionError, "must be outside"
                ):
                    external.execute_external_owner_trust(**kwargs)

    def test_exact_store_inventory_and_nonce_names_are_enforced(self) -> None:
        extra = self.store / "unexpected.txt"
        extra.write_text("x", encoding="utf-8")
        with self.assertRaisesRegex(external.P0ExternalOwnerTrustExecutionError, "exact canonical inventory"):
            external.execute_external_owner_trust(**self._kwargs())
        extra.unlink()
        bad_nonce = self.store / external.NONCE_LEDGER_DIRECTORY / "not-canonical"
        bad_nonce.write_bytes(b"")
        with self.assertRaisesRegex(external.P0ExternalOwnerTrustExecutionError, "noncanonical entry"):
            external.execute_external_owner_trust(**self._kwargs())

    def test_store_files_reject_hardlink_and_symlink_aliases(self) -> None:
        anchor_path = self.store / external.TRUST_ANCHOR_FILENAME
        outside_link = self.store.parent / "anchor-hardlink.json"
        try:
            os.link(anchor_path, outside_link)
        except OSError as exc:
            self.skipTest(f"hardlink unavailable: {exc}")
        with self.assertRaisesRegex(external.P0ExternalOwnerTrustExecutionError, "single-link"):
            external.execute_external_owner_trust(**self._kwargs())

    def test_store_path_symlink_or_reparse_alias_is_rejected_when_available(self) -> None:
        alias = self.store.parent / "store-alias"
        try:
            alias.symlink_to(self.store, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"directory symlink unavailable: {exc}")
        kwargs = self._kwargs()
        kwargs["trust_store_dir"] = alias
        with self.assertRaisesRegex(external.P0ExternalOwnerTrustExecutionError, "symlink/reparse"):
            external.execute_external_owner_trust(**kwargs)

    def test_anchor_and_revocation_are_strict_canonical_json(self) -> None:
        anchor_path = self.store / external.TRUST_ANCHOR_FILENAME
        valid = anchor_path.read_bytes()
        cases = {
            "bom": b"\xef\xbb\xbf" + valid,
            "duplicate": valid.replace(b"{", b'{"store_id":"duplicate",', 1),
            "nonfinite": valid.replace(b'"schema_version":', b'"unexpected":NaN,"schema_version":', 1),
            "trailing": valid + b"\n",
        }
        for label, raw in cases.items():
            with self.subTest(label=label):
                anchor_path.write_bytes(raw)
                with self.assertRaises(external.P0ExternalOwnerTrustExecutionError):
                    external.execute_external_owner_trust(**self._kwargs())
                anchor_path.write_bytes(valid)

    def test_large_integer_and_deep_json_are_typed_fail_closed(self) -> None:
        anchor_path = self.store / external.TRUST_ANCHOR_FILENAME
        malformed_values = (
            b'{"x":' + b"1" * 5000 + b"}\n",
            b'{"x":' + b"[" * 2000 + b"0" + b"]" * 2000 + b"}\n",
        )
        for raw in malformed_values:
            anchor_path.write_bytes(raw)
            with self.subTest(prefix=raw[:12]):
                with self.assertRaises(external.P0ExternalOwnerTrustExecutionError):
                    external.execute_external_owner_trust(**self._kwargs())
            self._write_store_files()

    def test_schema_extra_field_and_self_hash_tamper_are_rejected(self) -> None:
        for label, mutation in (
            ("schema", lambda row: row.update(schema_version="wrong")),
            ("extra", lambda row: row.update(extra="forbidden")),
            ("self-hash", lambda row: row.update(key_id="changed-without-rehash")),
        ):
            row = deepcopy(self.anchor)
            mutation(row)
            if label != "self-hash":
                row = _rehash(row)
            (self.store / external.TRUST_ANCHOR_FILENAME).write_bytes(
                external.json_file_bytes(row)
            )
            with self.subTest(label=label):
                with self.assertRaises(external.P0ExternalOwnerTrustExecutionError):
                    external.execute_external_owner_trust(**self._kwargs())
            self._write_store_files()

    def test_key_fingerprint_and_store_key_signature_mismatch_are_rejected(self) -> None:
        other_key = b"other-owner-key-material-that-is-at-least-32-bytes"
        anchor = deepcopy(self.anchor)
        anchor["key_material_base64"] = base64.b64encode(other_key).decode("ascii")
        anchor = _rehash(anchor)
        (self.store / external.TRUST_ANCHOR_FILENAME).write_bytes(
            external.json_file_bytes(anchor)
        )
        with self.assertRaisesRegex(external.P0ExternalOwnerTrustExecutionError, "fingerprint mismatch"):
            external.execute_external_owner_trust(**self._kwargs())

        anchor["key_fingerprint_sha256"] = hashlib.sha256(other_key).hexdigest()
        anchor = _rehash(anchor)
        (self.store / external.TRUST_ANCHOR_FILENAME).write_bytes(
            external.json_file_bytes(anchor)
        )
        with self.assertRaisesRegex(external.P0ExternalOwnerTrustExecutionError, "signature mismatch"):
            external.execute_external_owner_trust(**self._kwargs())

    def test_anchor_key_principal_and_owner_anchor_cross_bindings_reject_swaps(self) -> None:
        for field, value in (
            ("key_id", "other-key-id"),
            ("owner_principal_sha256", "d" * 64),
            ("owner_anchor_sha256", "e" * 64),
        ):
            anchor = deepcopy(self.anchor)
            anchor[field] = value
            anchor = _rehash(anchor)
            (self.store / external.TRUST_ANCHOR_FILENAME).write_bytes(
                external.json_file_bytes(anchor)
            )
            with self.subTest(field=field):
                with self.assertRaisesRegex(
                    external.P0ExternalOwnerTrustExecutionError, "binding mismatch"
                ):
                    external.execute_external_owner_trust(**self._kwargs())
            self._write_store_files()

    def test_expired_anchor_and_stale_revocation_snapshot_are_rejected(self) -> None:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        anchor = deepcopy(self.anchor)
        anchor["valid_from"] = _utc(now - timedelta(days=2))
        anchor["valid_to"] = _utc(now - timedelta(days=1))
        anchor = _rehash(anchor)
        (self.store / external.TRUST_ANCHOR_FILENAME).write_bytes(
            external.json_file_bytes(anchor)
        )
        with self.assertRaisesRegex(external.P0ExternalOwnerTrustExecutionError, "anchor is outside"):
            external.execute_external_owner_trust(**self._kwargs())
        self._write_store_files()

        snapshot = deepcopy(self.revocation)
        snapshot["issued_at"] = _utc(now - timedelta(days=3))
        snapshot["valid_from"] = _utc(now - timedelta(days=2))
        snapshot["valid_to"] = _utc(now - timedelta(days=1))
        snapshot = _rehash(snapshot)
        (self.store / external.REVOCATION_SNAPSHOT_FILENAME).write_bytes(
            external.json_file_bytes(snapshot)
        )
        with self.assertRaisesRegex(external.P0ExternalOwnerTrustExecutionError, "snapshot is outside"):
            external.execute_external_owner_trust(**self._kwargs())

    def test_revoked_key_and_revoked_owner_anchor_are_rejected(self) -> None:
        for field, value in (
            ("revoked_key_ids", [self.anchor["key_id"]]),
            ("revoked_owner_anchor_sha256", [self.anchor["owner_anchor_sha256"]]),
        ):
            snapshot = deepcopy(self.revocation)
            snapshot[field] = value
            snapshot = _rehash(snapshot)
            (self.store / external.REVOCATION_SNAPSHOT_FILENAME).write_bytes(
                external.json_file_bytes(snapshot)
            )
            with self.subTest(field=field):
                with self.assertRaisesRegex(external.P0ExternalOwnerTrustExecutionError, "is revoked"):
                    external.execute_external_owner_trust(**self._kwargs())
            self._write_store_files()

    def test_revocation_lists_require_sorted_unique_values(self) -> None:
        for field, values in (
            ("revoked_key_ids", ["z-key", "a-key"]),
            ("revoked_key_ids", ["a-key", "a-key"]),
            ("revoked_owner_anchor_sha256", ["f" * 64, "a" * 64]),
        ):
            snapshot = deepcopy(self.revocation)
            snapshot[field] = values
            snapshot = _rehash(snapshot)
            (self.store / external.REVOCATION_SNAPSHOT_FILENAME).write_bytes(
                external.json_file_bytes(snapshot)
            )
            with self.subTest(field=field, values=values):
                with self.assertRaisesRegex(external.P0ExternalOwnerTrustExecutionError, "sorted and unique"):
                    external.execute_external_owner_trust(**self._kwargs())
            self._write_store_files()

    def test_preauthorization_raw_rejects_bom_duplicate_nonfinite_and_trailing(self) -> None:
        raw = external.json_file_bytes(self.preauthorization)
        cases = {
            "bom": b"\xef\xbb\xbf" + raw,
            "duplicate": raw.replace(b"{", b'{"run_id":"duplicate",', 1),
            "nonfinite": raw.replace(b'"schema_version":', b'"unexpected":NaN,"schema_version":', 1),
            "trailing": raw + b"\n",
        }
        for label, candidate in cases.items():
            kwargs = self._kwargs()
            kwargs["owner_root_preauthorization_bytes"] = candidate
            with self.subTest(label=label):
                with self.assertRaises(external.P0ExternalOwnerTrustExecutionError):
                    external.execute_external_owner_trust(**kwargs)

    def test_signed_run_nonce_root_and_parser_provenance_swaps_are_rejected(self) -> None:
        mutations = (
            ("run", lambda row: row.update(run_id="other-run"), "run_id mismatch"),
            ("nonce", lambda row: row.update(nonce="other-nonce"), "nonce commitment mismatch"),
            (
                "root",
                lambda row: row["allowed_packet_root"].update(file_id_128_hex="f" * 32),
                "root tuple mismatch",
            ),
            (
                "provenance",
                lambda row: row["expected_provenance"].update(parser_version="other-parser"),
                "parser provenance binding mismatch",
            ),
        )
        for label, mutate, message in mutations:
            original = deepcopy(self.preauthorization)
            mutate(self.preauthorization)
            self._resign_preauthorization()
            kwargs = self._kwargs()
            if label == "nonce":
                kwargs["nonce_commitment_sha256"] = external.nonce_commitment_sha256(
                    original["nonce"]
                )
            if label == "provenance":
                kwargs["expected_parser_provenance"] = original["expected_provenance"]
            with self.subTest(label=label):
                with self.assertRaisesRegex(external.P0ExternalOwnerTrustExecutionError, message):
                    external.execute_external_owner_trust(**kwargs)
            self.preauthorization = original

    def test_malformed_root_and_nonexact_parser_provenance_fail_as_contract_errors(self) -> None:
        original = deepcopy(self.preauthorization)
        self.preauthorization["allowed_packet_root"]["final_volume_guid_path"] = 7
        self._resign_preauthorization()
        with self.assertRaisesRegex(
            external.P0ExternalOwnerTrustExecutionError, "final path is invalid"
        ):
            external.execute_external_owner_trust(**self._kwargs())
        self.preauthorization = original

        kwargs = self._kwargs()
        provenance = deepcopy(kwargs["expected_parser_provenance"])
        provenance["unexpected"] = "forbidden"
        kwargs["expected_parser_provenance"] = provenance
        with self.assertRaisesRegex(
            external.P0ExternalOwnerTrustExecutionError, "fields mismatch"
        ):
            external.execute_external_owner_trust(**kwargs)

    def test_preauthorization_expiry_single_use_and_capability_overclaim_reject(self) -> None:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        cases = (
            (
                "expired",
                {
                    "issued_at": _utc(now - timedelta(days=3)),
                    "not_before": _utc(now - timedelta(days=2)),
                    "expires_at": _utc(now - timedelta(days=1)),
                },
            ),
            ("not-single-use", {"single_use": False}),
            ("production", {"production_approval": True}),
            ("apply", {"action_applied": True}),
        )
        for label, changes in cases:
            original = deepcopy(self.preauthorization)
            self.preauthorization.update(changes)
            self._resign_preauthorization()
            with self.subTest(label=label):
                with self.assertRaises(external.P0ExternalOwnerTrustExecutionError):
                    external.execute_external_owner_trust(**self._kwargs())
            self.preauthorization = original

    def test_signed_nested_requirements_scope_decision_and_effect_are_strict(self) -> None:
        cases = (
            ("protected", lambda row: row.update(protected_roots=[])),
            ("category", lambda row: row.update(category_root_map=[])),
            ("watch", lambda row: row.update(watch_requirements={})),
            ("write-deny", lambda row: row.update(write_deny_requirements={})),
            ("scope", lambda row: row.update(authority_scope="MALFORMED_SCOPE")),
            ("decision", lambda row: row.update(decision="DENY")),
            ("effect", lambda row: row.update(operational_effect="PIPELINE_WRITE")),
        )
        for label, mutate in cases:
            original = deepcopy(self.preauthorization)
            mutate(self.preauthorization)
            self._resign_preauthorization()
            with self.subTest(label=label):
                with self.assertRaises(external.P0ExternalOwnerTrustExecutionError):
                    external.execute_external_owner_trust(**self._kwargs())
            self.preauthorization = original

    @unittest.skipUnless(os.name == "nt", "Windows reparse/hardlink guard e2e")
    def test_windows_filesystem_execution_end_to_end(self) -> None:
        receipt = external.execute_external_owner_trust(**self._kwargs())
        self.assertTrue(receipt["trust_store_alias_guards_checked"])
        self.assertTrue(receipt["single_use_replay_consumed"])
        self.assertFalse(receipt["external_owner_trust_verified"])

    @unittest.skipUnless(os.name == "nt", "Windows held-directory rename denial")
    def test_windows_held_nonce_directory_blocks_in_call_replacement(self) -> None:
        nonce_dir = self.store / external.NONCE_LEDGER_DIRECTORY
        retired = self.store.parent / "in-call-retired-ledger"
        original_write = external._write_all
        rename_blocked: list[bool] = []

        def racing_write(descriptor: int, raw: bytes) -> None:
            try:
                os.replace(nonce_dir, retired)
            except OSError:
                rename_blocked.append(True)
            else:  # pragma: no cover - security regression
                rename_blocked.append(False)
            original_write(descriptor, raw)

        with mock.patch.object(external, "_write_all", new=racing_write):
            receipt = external.execute_external_owner_trust(**self._kwargs())
        self.assertEqual(rename_blocked, [True])
        self.assertTrue(receipt["nonce_ledger_identity_pin_matched"])
        self.assertEqual(len(list(nonce_dir.iterdir())), 1)
        self.assertFalse(retired.exists())


if __name__ == "__main__":
    unittest.main()
