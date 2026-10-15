from __future__ import annotations

from copy import deepcopy
import hashlib
import sys
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from llm_batch.grounding import p0_actual_authority_bridge_contract as bridge  # noqa: E402
from llm_batch.grounding import p0_actual_a_event_bytes as a_event_bytes  # noqa: E402
from llm_batch.grounding import p0_actual_authority_contract as authority  # noqa: E402
from llm_batch.grounding import p0_actual_authority_event_bytes as event_bytes  # noqa: E402
from llm_batch.grounding import p0_actual_packet_contract as packet  # noqa: E402
from llm_batch.grounding import p0_actual_route_contract as route  # noqa: E402
from llm_batch.grounding import p0_windows_fixed_directory_identity as windows  # noqa: E402


KEY = b"authority-bridge-test-key-material-32-bytes-minimum"
SHA_A = hashlib.sha256(b"a").hexdigest()
SHA_B = hashlib.sha256(b"b").hexdigest()
SHA_C = hashlib.sha256(b"c").hexdigest()
SHA_D = hashlib.sha256(b"d").hexdigest()


def _artifact(**values):
    return bridge.with_artifact_hash(values)


def _receipt(**values):
    return {**values, "receipt_sha256": bridge.canonical_sha256(values)}


def _provenance(rows, *, actual: bool):
    value = {
        "schema_version": bridge.PARSER_PROVENANCE_AUTHORIZATION_SCHEMA,
        "record_origin": rows["authority_origin"],
        "provenance_authorization_id": "TEST:PARSER:PROVENANCE:01",
        "domain": bridge.PARSER_PROVENANCE_DOMAIN,
        "algorithm": "HMAC-SHA256",
        "key_id": rows["owner_anchor"]["key_id"],
        "owner_anchor_sha256": rows["owner_anchor"]["artifact_sha256"],
        "owner_authorization_sha256": rows["owner_authorization"]["artifact_sha256"],
        "launch_sha256": rows["launch"]["artifact_sha256"],
        "expected_parser_receipt_schema": authority.PARSER_RECEIPT_SCHEMA,
        "expected_parser_manifest_sha256": rows["route_receipt"]["parser_manifest_sha256"],
        "expected_parser_version": rows["route_receipt"]["parser_version"],
        "expected_capture_manifest_sha256": rows["parser_receipt"]["capture_manifest_sha256"],
        "expected_input_registry_sha256": rows["parser_receipt"]["input_registry_sha256"],
        "authority_scope": bridge.AUTHORITY_SCOPE,
        "decision": bridge.PARSER_PROVENANCE_DECISION,
        "issued_at": "2026-01-01T01:30:00Z",
        "not_before": "2026-01-01T02:00:00Z",
        "expires_at": "2026-01-09T00:00:00Z",
        "nonce": "TEST-PROVENANCE-NONCE",
        "provenance_signature_sha256": None,
        "verification_status": "EXTERNAL_KEY_ABSENT",
        "action_applied": False,
        "operational_effect": bridge.OPERATIONAL_EFFECT,
    }
    if actual:
        value["verification_status"] = "DETACHED_SIGNATURE_PRESENT_UNVERIFIED"
        value["provenance_signature_sha256"] = bridge.sign_parser_provenance_authorization(
            value, KEY
        )
    return bridge.with_artifact_hash(value)


def _terminal(rows, *, actual: bool):
    value = {
        "schema_version": bridge.TERMINAL_BRIDGE_ATTESTATION_SCHEMA,
        "record_origin": rows["authority_origin"],
        "bridge_attestation_id": "TEST:TERMINAL:BRIDGE:01",
        "domain": bridge.TERMINAL_BRIDGE_DOMAIN,
        "algorithm": "HMAC-SHA256",
        "key_id": rows["owner_anchor"]["key_id"],
        "owner_anchor_sha256": rows["owner_anchor"]["artifact_sha256"],
        "owner_authorization_sha256": rows["owner_authorization"]["artifact_sha256"],
        "parser_provenance_authorization_sha256": rows["provenance"]["artifact_sha256"],
        "launch_sha256": rows["launch"]["artifact_sha256"],
        "keyless_manifest_file_sha256": rows["packet_receipt"]["manifest_file_sha256"],
        "keyless_manifest_artifact_sha256": rows["keyless_manifest"]["artifact_sha256"],
        "packet_receipt_sha256": rows["packet_receipt"]["receipt_sha256"],
        "route_receipt_sha256": bridge.canonical_sha256(rows["route_receipt"]),
        "parser_receipt_sha256": rows["parser_receipt"]["artifact_sha256"],
        "authority_manifest_sha256": rows["authority_manifest"]["artifact_sha256"],
        "authority_final_attestation_sha256": rows["final_attestation"]["artifact_sha256"],
        "authority_foundation_receipt_sha256": rows["authority_receipt"]["receipt_sha256"],
        "event_bytes_receipt_sha256": rows["event_receipt"]["receipt_sha256"],
        "event_file_sha256": rows["event_receipt"]["event_file_sha256"],
        "a_event_bytes_receipt_sha256": rows["a_event_receipt"]["receipt_sha256"],
        "a_context_file_sha256": rows["a_event_receipt"]["a_context_file_sha256"],
        "a_event_file_sha256": rows["a_event_receipt"]["a_event_file_sha256"],
        "a_subject_selection_seal_sha256": rows["a_event_receipt"][
            "a_subject_selection_seal_sha256"
        ],
        "windows_packet_validation_receipt_sha256": rows["windows_receipt"][
            "receipt_sha256"
        ],
        "windows_expected_manifest_sha256": rows["windows_receipt"][
            "expected_manifest_sha256"
        ],
        "windows_root_final_path": rows["windows_receipt"][
            "windows_handle_receipt"
        ]["root_final_path"],
        "windows_root_volume_serial": rows["windows_receipt"][
            "windows_handle_receipt"
        ]["root_volume_serial"],
        "windows_root_file_id": rows["windows_receipt"]["windows_handle_receipt"][
            "root_file_id"
        ],
        "actual_source_claim_count": 40,
        "actual_a_context_review_count": 20,
        "issued_at": "2026-01-06T00:00:00Z",
        "nonce": "TEST-TERMINAL-BRIDGE-NONCE",
        "decision": bridge.TERMINAL_BRIDGE_DECISION,
        "authority_scope": bridge.AUTHORITY_SCOPE,
        "bridge_signature_sha256": None,
        "verification_status": "EXTERNAL_KEY_ABSENT",
        "action_applied": False,
        "operational_effect": bridge.OPERATIONAL_EFFECT,
    }
    if actual:
        value["verification_status"] = "DETACHED_SIGNATURE_PRESENT_UNVERIFIED"
        value["bridge_signature_sha256"] = bridge.sign_terminal_bridge_attestation(
            value, KEY
        )
    return bridge.with_artifact_hash(value)


def _rows(*, actual: bool = False):
    authority_origin = authority.ACTUAL_ORIGIN if actual else authority.EXAMPLE_ORIGIN
    packet_origin = packet.ACTUAL_ORIGIN if actual else packet.EXAMPLE_ORIGIN
    key_id = "TEST-OWNER-KEY" if actual else "EXAMPLE-KEY-ABSENT"
    owner_anchor = _artifact(
        record_origin=authority_origin,
        key_id=key_id,
    )
    launch = _artifact(
        record_origin=authority_origin,
        created_at="2026-01-01T00:00:00Z",
        capture_started_at="2026-01-01T03:00:00Z" if actual else None,
    )
    owner_authorization = _artifact(
        record_origin=authority_origin,
        key_id=key_id,
        owner_anchor_sha256=owner_anchor["artifact_sha256"],
        launch_sha256=launch["artifact_sha256"],
        issued_at="2026-01-01T01:00:00Z",
        not_before="2026-01-01T02:00:00Z",
        expires_at="2026-01-10T00:00:00Z",
    )
    parser_receipt = _artifact(
        schema_version=authority.PARSER_RECEIPT_SCHEMA,
        record_origin=authority_origin,
        launch_sha256=launch["artifact_sha256"],
        runtime_status="COMPLETE" if actual else "NOT_RUN",
        completed_at="2026-01-02T00:00:00Z" if actual else None,
        capture_manifest_sha256=SHA_A,
        input_registry_sha256=SHA_B,
        action_applied=False,
    )
    route_receipt = {
        "schema_version": route.ROUTE_RECEIPT_SCHEMA,
        "record_origin": packet_origin,
        "source_input_plan_sha256": hashlib.sha256(b"source-plan").hexdigest(),
        "sampling_frame_sha256": hashlib.sha256(b"sampling-frame").hexdigest(),
        "parser_manifest_sha256": SHA_C,
        "parser_version": "test-parser-v1",
        "parser_launch_sha256": launch["artifact_sha256"],
        "parser_capture_manifest_sha256": SHA_A,
        "captured_source_registry_sha256": SHA_B,
        "route_accounting_packet_complete": actual,
        "actual_authority_granted": False,
        "action_applied": False,
    }
    observed = {
        "source_snapshot_count": 40,
        "source_claim_row_count": 41,
        "selected_source_claim_count": 40,
        "terminal_queue_count": 10,
        "a_context_review_count": 20,
        "a_annotation_event_count": 20,
    }
    credited = {
        "actual_source_claim_count": 0,
        "actual_a_context_review_count": 0,
    }
    a_context_file_sha = hashlib.sha256(b"a-context-file").hexdigest()
    a_event_file_sha = hashlib.sha256(b"a-event-file").hexdigest()
    a_seal_file_sha = hashlib.sha256(b"a-seal-file").hexdigest()
    a_seal_artifact_sha = hashlib.sha256(b"a-seal-artifact").hexdigest()
    a_context_receipt = _receipt(
        schema_version="test_a_context_receipt_v1",
        record_origin=packet_origin,
        actual_authority_granted=False,
    )
    a_event_receipt = _receipt(
        schema_version=a_event_bytes.A_EVENT_BYTES_RECEIPT_SCHEMA,
        record_origin=packet_origin,
        source_claim_file_sha256=hashlib.sha256(b"source-claim-file").hexdigest(),
        source_claim_row_count=41,
        a_context_file_sha256=a_context_file_sha,
        a_context_row_count=20,
        a_event_file_sha256=a_event_file_sha,
        a_event_row_count=20,
        a_subject_selection_seal_file_sha256=a_seal_file_sha,
        a_subject_selection_seal_row_count=1,
        a_subject_selection_seal_sha256=a_seal_artifact_sha,
        a_context_receipt=a_context_receipt,
        a_context_receipt_sha256=a_context_receipt["receipt_sha256"],
        head_count=20,
        head_projection_sha256=hashlib.sha256(b"a-heads").hexdigest(),
        canonical_input_bytes_verified=True,
        a_event_hash_chains_verified=True,
        latest_event_projection_verified=True,
        a_subject_selection_seal_verified=True,
        filesystem_handle_trust_verified=False,
        durable_predecessor_verified=False,
        annotation_append_only_verified=False,
        owner_authority_verified=False,
        runtime_noninterference_verified=False,
        credited_actual_a_context_review_count=0,
        actual_authority_granted=False,
        production_approval=False,
        full_scan_approval=False,
        p0_phase_exit=False,
        action_applied=False,
        operational_effect=bridge.OPERATIONAL_EFFECT,
        gate_status="NO_GO_ACTUAL_A_EVENT_BYTES_STRUCTURE_ONLY",
    )
    child_shas = {
        role: hashlib.sha256(f"child:{role}".encode()).hexdigest()
        for role, _, _ in packet.CHILD_FILES
    }
    child_shas.update(
        {
            "a_contexts": a_context_file_sha,
            "a_annotation_events": a_event_file_sha,
            "a_subject_selection_seal": a_seal_file_sha,
        }
    )
    files = [
        {
            "role": role,
            "path": path,
            "media_type": media_type,
            "rows": 1,
            "bytes": 1,
            "sha256": child_shas[role],
        }
        for role, path, media_type in packet.CHILD_FILES
    ]
    keyless_manifest = _artifact(
        record_origin=packet_origin,
        created_at="2026-01-03T00:00:00Z",
        files=files,
        route_receipt_sha256=bridge.canonical_sha256(route_receipt),
        parser_receipt_sha256=parser_receipt["artifact_sha256"],
        a_context_receipt_sha256=bridge.canonical_sha256(a_context_receipt),
        a_subject_selection_seal_sha256=a_seal_artifact_sha,
        observed_counts=observed,
        credited_counts=credited,
        actual_authority_granted=False,
        production_approval=False,
        full_scan_approval=False,
        p0_phase_exit=False,
        action_applied=False,
    )
    manifest_file_sha = hashlib.sha256(
        bridge.canonical_bytes(keyless_manifest) + b"\n"
    ).hexdigest()
    packet_receipt = _receipt(
        schema_version=packet.PACKET_RECEIPT_SCHEMA,
        record_origin=packet_origin,
        manifest_file_sha256=manifest_file_sha,
        manifest_artifact_sha256=keyless_manifest["artifact_sha256"],
        route_receipt_sha256=bridge.canonical_sha256(route_receipt),
        parser_receipt_sha256=parser_receipt["artifact_sha256"],
        a_context_receipt_sha256=bridge.canonical_sha256(a_context_receipt),
        a_subject_selection_seal_sha256=a_seal_artifact_sha,
        source_input_plan_sha256=route_receipt["source_input_plan_sha256"],
        sampling_frame_sha256=route_receipt["sampling_frame_sha256"],
        route_parser_manifest_sha256=route_receipt["parser_manifest_sha256"],
        route_parser_version=route_receipt["parser_version"],
        route_parser_launch_sha256=route_receipt["parser_launch_sha256"],
        route_parser_capture_manifest_sha256=route_receipt[
            "parser_capture_manifest_sha256"
        ],
        route_accounting_packet_complete=actual,
        observed_counts=observed,
        credited_counts=credited,
        external_owner_authority_verified=False,
        actual_authority_granted=False,
        production_approval=False,
        full_scan_approval=False,
        p0_phase_exit=False,
        action_applied=False,
    )
    windows_handle_receipt = _receipt(
        schema_version=windows.WINDOWS_HANDLE_RECEIPT_SCHEMA,
        root_final_path=(
            "\\\\?\\Volume{12345678-1234-1234-1234-1234567890ab}\\packet"
        ),
        root_volume_serial="123456789",
        root_file_id="00112233445566778899aabbccddeeff",
        filesystem_handle_binding_verified=True,
        filesystem_handle_trust_verified=False,
        external_root_identity_pin_verified=False,
        os_write_deny_verified=False,
        runtime_noninterference_verified=False,
        authority_journal_watch_bundle_verified=False,
        external_owner_authority_verified=False,
        actual_authority_granted=False,
        production_approval=False,
        full_scan_approval=False,
        p0_phase_exit=False,
        action_applied=False,
        operational_effect=bridge.OPERATIONAL_EFFECT,
    )
    windows_projection = [
        {
            "role": child["role"],
            "path": child["path"],
            "bytes": child["bytes"],
            "sha256": child["sha256"],
        }
        for child in files
    ]
    windows_receipt = _receipt(
        schema_version=windows.WINDOWS_PACKET_VALIDATION_RECEIPT_SCHEMA,
        expected_manifest_sha256=manifest_file_sha,
        windows_handle_receipt=windows_handle_receipt,
        windows_handle_receipt_declared_receipt_sha256=windows_handle_receipt[
            "receipt_sha256"
        ],
        windows_handle_receipt_full_canonical_sha256=bridge.canonical_sha256(
            windows_handle_receipt
        ),
        packet_receipt=deepcopy(packet_receipt),
        packet_receipt_declared_receipt_sha256=packet_receipt["receipt_sha256"],
        packet_receipt_full_canonical_sha256=bridge.canonical_sha256(packet_receipt),
        handle_member_inventory_projection=windows_projection,
        handle_member_inventory_sha256=bridge.canonical_sha256(windows_projection),
        packet_manifest_fixed_file_inventory_projection=windows_projection,
        packet_manifest_fixed_file_inventory_sha256=bridge.canonical_sha256(
            windows_projection
        ),
        handle_manifest_fixed_file_inventory_exact_match=True,
        byte_inventory_binding_verified=True,
        filesystem_handle_binding_verified=True,
        filesystem_handle_trust_verified=False,
        external_root_identity_pin_verified=False,
        os_write_deny_verified=False,
        runtime_noninterference_verified=False,
        external_owner_authority_verified=False,
        actual_authority_granted=False,
        production_approval=False,
        full_scan_approval=False,
        p0_phase_exit=False,
        action_applied=False,
        operational_effect=bridge.OPERATIONAL_EFFECT,
        gate_status="NO_GO_ACTUAL_P0_AUTHORITY_NOT_VERIFIED",
        receipt_hash_scope="CANONICAL_MATERIAL_EXCLUDING_RECEIPT_SHA256",
    )
    authority_counts = (40, 20) if actual else (0, 0)
    authority_manifest = _artifact(
        record_origin=authority_origin,
        parser_receipt_sha256=parser_receipt["artifact_sha256"],
        finalized_at="2026-01-04T00:00:00Z" if actual else None,
        actual_source_claim_count=authority_counts[0],
        actual_a_context_review_count=authority_counts[1],
        production_approval=False,
        full_scan_approval=False,
        p0_phase_exit=False,
        action_applied=False,
    )
    event_file_sha = SHA_D
    final_attestation = _artifact(
        record_origin=authority_origin,
        owner_anchor_sha256=owner_anchor["artifact_sha256"],
        owner_authorization_sha256=owner_authorization["artifact_sha256"],
        launch_sha256=launch["artifact_sha256"],
        parser_receipt_sha256=parser_receipt["artifact_sha256"],
        manifest_sha256=authority_manifest["artifact_sha256"],
        event_file_sha256=event_file_sha,
        actual_source_claim_count=authority_counts[0],
        actual_a_context_review_count=authority_counts[1],
        issued_at="2026-01-05T00:00:00Z",
        action_applied=False,
    )
    authority_receipt = _receipt(
        schema_version=authority.RECEIPT_SCHEMA,
        record_origin=authority_origin,
        manifest_sha256=authority_manifest["artifact_sha256"],
        final_attestation_sha256=final_attestation["artifact_sha256"],
        owner_authority_verified=False,
        actual_source_claim_count=0,
        actual_a_context_review_count=0,
        production_approval=False,
        full_scan_approval=False,
        p0_phase_exit=False,
        action_applied=False,
    )
    event_receipt = _receipt(
        schema_version=event_bytes.EVENT_BYTES_RECEIPT_SCHEMA,
        event_file_sha256=event_file_sha,
        owner_authority_verified=False,
        action_applied=False,
    )
    rows = {
        "authority_origin": authority_origin,
        "packet_origin": packet_origin,
        "owner_anchor": owner_anchor,
        "owner_authorization": owner_authorization,
        "launch": launch,
        "parser_receipt": parser_receipt,
        "route_receipt": route_receipt,
        "keyless_manifest": keyless_manifest,
        "packet_receipt": packet_receipt,
        "authority_manifest": authority_manifest,
        "final_attestation": final_attestation,
        "authority_receipt": authority_receipt,
        "event_receipt": event_receipt,
        "a_event_receipt": a_event_receipt,
        "windows_receipt": windows_receipt,
    }
    rows["provenance"] = _provenance(rows, actual=actual)
    rows["terminal"] = _terminal(rows, actual=actual)
    return rows


def _validate(rows, *, key=None):
    return bridge.validate_authority_bridge_bundle(
        parser_provenance_authorization=rows["provenance"],
        terminal_bridge_attestation=rows["terminal"],
        owner_anchor=rows["owner_anchor"],
        owner_authorization=rows["owner_authorization"],
        launch=rows["launch"],
        parser_receipt=rows["parser_receipt"],
        route_receipt=rows["route_receipt"],
        keyless_manifest=rows["keyless_manifest"],
        packet_receipt=deepcopy(rows["packet_receipt"]),
        authority_manifest=rows["authority_manifest"],
        authority_final_attestation=rows["final_attestation"],
        authority_foundation_receipt=rows["authority_receipt"],
        event_bytes_receipt=rows["event_receipt"],
        a_event_bytes_receipt=rows["a_event_receipt"],
        windows_packet_validation_receipt=rows["windows_receipt"],
        expected_authority_origin=rows["authority_origin"],
        expected_packet_origin=rows["packet_origin"],
        key=key,
        expected_external_anchor_sha256=(
            rows["owner_anchor"]["artifact_sha256"] if key is not None else None
        ),
    )


def _reseal_packet(rows):
    rows["keyless_manifest"] = bridge.with_artifact_hash(rows["keyless_manifest"])
    rows["packet_receipt"]["manifest_artifact_sha256"] = rows["keyless_manifest"][
        "artifact_sha256"
    ]
    rows["packet_receipt"]["manifest_file_sha256"] = hashlib.sha256(
        bridge.canonical_bytes(rows["keyless_manifest"]) + b"\n"
    ).hexdigest()
    rows["packet_receipt"].pop("receipt_sha256", None)
    rows["packet_receipt"] = _receipt(**rows["packet_receipt"])
    _reseal_windows(rows)


def _reseal_windows(rows):
    old = rows["windows_receipt"]
    handle = old["windows_handle_receipt"]
    projection = [
        {
            "role": child["role"],
            "path": child["path"],
            "bytes": child["bytes"],
            "sha256": child["sha256"],
        }
        for child in rows["keyless_manifest"]["files"]
    ]
    rows["windows_receipt"] = _receipt(
        schema_version=windows.WINDOWS_PACKET_VALIDATION_RECEIPT_SCHEMA,
        expected_manifest_sha256=rows["packet_receipt"]["manifest_file_sha256"],
        windows_handle_receipt=handle,
        windows_handle_receipt_declared_receipt_sha256=handle["receipt_sha256"],
        windows_handle_receipt_full_canonical_sha256=bridge.canonical_sha256(handle),
        packet_receipt=rows["packet_receipt"],
        packet_receipt_declared_receipt_sha256=rows["packet_receipt"]["receipt_sha256"],
        packet_receipt_full_canonical_sha256=bridge.canonical_sha256(
            rows["packet_receipt"]
        ),
        handle_member_inventory_projection=projection,
        handle_member_inventory_sha256=bridge.canonical_sha256(projection),
        packet_manifest_fixed_file_inventory_projection=projection,
        packet_manifest_fixed_file_inventory_sha256=bridge.canonical_sha256(
            projection
        ),
        handle_manifest_fixed_file_inventory_exact_match=True,
        byte_inventory_binding_verified=True,
        filesystem_handle_binding_verified=True,
        filesystem_handle_trust_verified=False,
        external_root_identity_pin_verified=False,
        os_write_deny_verified=False,
        runtime_noninterference_verified=False,
        external_owner_authority_verified=False,
        actual_authority_granted=False,
        production_approval=False,
        full_scan_approval=False,
        p0_phase_exit=False,
        action_applied=False,
        operational_effect=bridge.OPERATIONAL_EFFECT,
        gate_status="NO_GO_ACTUAL_P0_AUTHORITY_NOT_VERIFIED",
        receipt_hash_scope="CANONICAL_MATERIAL_EXCLUDING_RECEIPT_SHA256",
    )


def _reseal_terminal(rows, *, actual=False):
    rows["terminal"] = _terminal(rows, actual=actual)


class P0ActualAuthorityBridgeContractTest(unittest.TestCase):
    def test_example_bridge_is_structurally_bound_but_never_credited(self):
        receipt = _validate(_rows())
        self.assertEqual(
            receipt["binding_scope"],
            "STRUCTURAL_PRESENTED_RECEIPT_BINDINGS_ONLY",
        )
        self.assertTrue(receipt["presented_receipt_cross_bindings_verified"])
        self.assertFalse(receipt["underlying_validator_execution_verified"])
        self.assertTrue(receipt["untrusted_observation"])
        self.assertFalse(receipt["filesystem_handle_binding_verified"])
        self.assertTrue(receipt["presented_filesystem_handle_binding_consistent"])
        self.assertFalse(receipt["parser_provenance_signature_math_valid"])
        self.assertFalse(receipt["terminal_bridge_signature_math_valid"])
        self.assertEqual(
            receipt["credited_counts"],
            {"actual_source_claim_count": 0, "actual_a_context_review_count": 0},
        )
        for field in (
            "external_anchor_trust_verified",
            "external_root_identity_pin_verified",
            "filesystem_handle_trust_verified",
            "os_write_deny_verified",
            "runtime_noninterference_verified",
            "owner_authority_verified",
            "actual_authority_granted",
            "production_approval",
            "full_scan_approval",
            "p0_phase_exit",
            "action_applied",
        ):
            self.assertFalse(receipt[field], field)

    def test_caller_presented_fake_receipts_cannot_prove_execution_or_authority(self):
        # `_rows`는 실제 하위 validator 실행 산출물이 아니라 이 테스트가 만든
        # self-consistent serialized mapping이다. bridge 성공은 실행 provenance가 아니다.
        receipt = _validate(_rows(actual=True), key=KEY)
        self.assertTrue(receipt["presented_receipt_cross_bindings_verified"])
        self.assertEqual(
            receipt["binding_scope"],
            "STRUCTURAL_PRESENTED_RECEIPT_BINDINGS_ONLY",
        )
        self.assertFalse(receipt["underlying_validator_execution_verified"])
        self.assertTrue(receipt["untrusted_observation"])
        self.assertFalse(receipt["filesystem_handle_binding_verified"])
        self.assertFalse(receipt["owner_authority_verified"])
        self.assertFalse(receipt["actual_authority_granted"])
        self.assertFalse(receipt["p0_phase_exit"])
        self.assertEqual(
            receipt["credited_counts"],
            {"actual_source_claim_count": 0, "actual_a_context_review_count": 0},
        )

    def test_actual_signed_bridge_math_can_pass_but_authority_stays_false(self):
        receipt = _validate(_rows(actual=True), key=KEY)
        self.assertTrue(receipt["parser_provenance_signature_math_valid"])
        self.assertTrue(receipt["terminal_bridge_signature_math_valid"])
        self.assertFalse(receipt["actual_authority_granted"])
        self.assertEqual(receipt["credited_counts"]["actual_source_claim_count"], 0)

    def test_actual_missing_key_is_unverified_not_authorized(self):
        receipt = _validate(_rows(actual=True))
        self.assertFalse(receipt["parser_provenance_signature_math_valid"])
        self.assertFalse(receipt["terminal_bridge_signature_math_valid"])
        self.assertFalse(receipt["owner_authority_verified"])

    def test_example_rejects_injected_signature(self):
        rows = _rows()
        provenance = dict(rows["provenance"])
        provenance["verification_status"] = "DETACHED_SIGNATURE_PRESENT_UNVERIFIED"
        provenance["provenance_signature_sha256"] = SHA_A
        rows["provenance"] = bridge.with_artifact_hash(provenance)
        with self.assertRaisesRegex(bridge.P0ActualAuthorityBridgeError, "example.*unsigned"):
            _validate(rows)

    def test_actual_requires_signature_artifacts(self):
        rows = _rows(actual=True)
        provenance = dict(rows["provenance"])
        provenance["verification_status"] = "EXTERNAL_KEY_ABSENT"
        provenance["provenance_signature_sha256"] = None
        rows["provenance"] = bridge.with_artifact_hash(provenance)
        with self.assertRaisesRegex(bridge.P0ActualAuthorityBridgeError, "actual.*requires signature"):
            _validate(rows)

    def test_bad_provenance_and_terminal_signatures_fail(self):
        for name, field in (
            ("provenance", "provenance_signature_sha256"),
            ("terminal", "bridge_signature_sha256"),
        ):
            rows = _rows(actual=True)
            value = dict(rows[name])
            value[field] = SHA_A
            rows[name] = bridge.with_artifact_hash(value)
            with self.subTest(name=name), self.assertRaisesRegex(
                bridge.P0ActualAuthorityBridgeError, "signature mismatch"
            ):
                _validate(rows, key=KEY)

    def test_uniform_parser_rebind_cannot_escape_owner_provenance(self):
        rows = _rows()
        rows["route_receipt"]["parser_manifest_sha256"] = SHA_D
        rows["route_receipt"]["parser_version"] = "attacker-parser-v9"
        rows["keyless_manifest"]["route_receipt_sha256"] = bridge.canonical_sha256(
            rows["route_receipt"]
        )
        _reseal_packet(rows)
        _reseal_terminal(rows)
        with self.assertRaisesRegex(bridge.P0ActualAuthorityBridgeError, "parser manifest|parser version"):
            _validate(rows)

    def test_packet_and_route_swaps_fail(self):
        rows = _rows()
        rows["keyless_manifest"]["route_receipt_sha256"] = SHA_A
        _reseal_packet(rows)
        with self.assertRaisesRegex(bridge.P0ActualAuthorityBridgeError, "packet route"):
            _validate(rows)
        rows = _rows()
        rows["packet_receipt"]["manifest_artifact_sha256"] = SHA_B
        with self.assertRaisesRegex(bridge.P0ActualAuthorityBridgeError, "packet receipt"):
            _validate(rows)

    def test_parser_swap_fails_across_packet_and_authority(self):
        rows = _rows()
        parser_row = dict(rows["parser_receipt"])
        parser_row["input_registry_sha256"] = SHA_D
        rows["parser_receipt"] = bridge.with_artifact_hash(parser_row)
        with self.assertRaisesRegex(bridge.P0ActualAuthorityBridgeError, "parser receipt|expected input"):
            _validate(rows)

    def test_event_receipt_and_event_file_swaps_fail(self):
        rows = _rows()
        event = dict(rows["event_receipt"])
        event["event_file_sha256"] = SHA_A
        event.pop("receipt_sha256")
        rows["event_receipt"] = _receipt(**event)
        with self.assertRaisesRegex(bridge.P0ActualAuthorityBridgeError, "event file"):
            _validate(rows)
        rows = _rows()
        rows["terminal"]["event_bytes_receipt_sha256"] = SHA_B
        rows["terminal"] = bridge.with_artifact_hash(rows["terminal"])
        with self.assertRaisesRegex(bridge.P0ActualAuthorityBridgeError, "event receipt"):
            _validate(rows)

    def test_authority_manifest_and_receipt_swaps_fail(self):
        rows = _rows()
        manifest = dict(rows["authority_manifest"])
        manifest["parser_receipt_sha256"] = SHA_D
        rows["authority_manifest"] = bridge.with_artifact_hash(manifest)
        with self.assertRaisesRegex(bridge.P0ActualAuthorityBridgeError, "parser receipt|authority manifest"):
            _validate(rows)
        rows = _rows()
        authority_receipt = dict(rows["authority_receipt"])
        authority_receipt.pop("receipt_sha256")
        authority_receipt["manifest_sha256"] = SHA_A
        rows["authority_receipt"] = _receipt(**authority_receipt)
        with self.assertRaisesRegex(bridge.P0ActualAuthorityBridgeError, "authority manifest"):
            _validate(rows)

    def test_terminal_attestation_covers_post_run_packet(self):
        rows = _rows()
        rows["keyless_manifest"]["created_at"] = "2026-01-03T00:00:01Z"
        _reseal_packet(rows)
        with self.assertRaisesRegex(bridge.P0ActualAuthorityBridgeError, "packet terminal"):
            _validate(rows)

    def test_packet_receipt_projection_swap_fails_after_valid_rehash(self):
        rows = _rows()
        rows["packet_receipt"]["route_parser_version"] = "swapped-parser-v9"
        rows["packet_receipt"].pop("receipt_sha256")
        rows["packet_receipt"] = _receipt(**rows["packet_receipt"])
        _reseal_windows(rows)
        _reseal_terminal(rows)
        with self.assertRaisesRegex(
            bridge.P0ActualAuthorityBridgeError, "packet provenance"
        ):
            _validate(rows)

    def test_a_event_receipt_swap_fails_terminal_binding(self):
        rows = _rows()
        value = dict(rows["a_event_receipt"])
        value.pop("receipt_sha256")
        value["head_projection_sha256"] = SHA_A
        rows["a_event_receipt"] = _receipt(**value)
        with self.assertRaisesRegex(
            bridge.P0ActualAuthorityBridgeError, "A event receipt"
        ):
            _validate(rows)

    def test_a_context_file_child_swap_fails_even_when_packet_is_resealed(self):
        rows = _rows()
        for child in rows["keyless_manifest"]["files"]:
            if child["role"] == "a_contexts":
                child["sha256"] = SHA_A
        _reseal_packet(rows)
        _reseal_terminal(rows)
        with self.assertRaisesRegex(
            bridge.P0ActualAuthorityBridgeError, "A fixed child bytes"
        ):
            _validate(rows)

    def test_a_subject_seal_artifact_swap_fails_cross_binding(self):
        rows = _rows()
        value = dict(rows["a_event_receipt"])
        value.pop("receipt_sha256")
        value["a_subject_selection_seal_sha256"] = SHA_A
        rows["a_event_receipt"] = _receipt(**value)
        _reseal_terminal(rows)
        with self.assertRaisesRegex(
            bridge.P0ActualAuthorityBridgeError, "A subject seal"
        ):
            _validate(rows)

    def test_bridge_receipt_exposes_packet_and_a_byte_projections(self):
        rows = _rows()
        receipt = _validate(rows)
        self.assertEqual(
            receipt["packet_receipt_sha256"], rows["packet_receipt"]["receipt_sha256"]
        )
        self.assertEqual(
            receipt["a_event_bytes_receipt_sha256"],
            rows["a_event_receipt"]["receipt_sha256"],
        )
        self.assertEqual(
            receipt["a_subject_selection_seal_sha256"],
            rows["a_event_receipt"]["a_subject_selection_seal_sha256"],
        )

    def test_windows_composite_nested_packet_swap_fails(self):
        rows = _rows()
        composite = deepcopy(rows["windows_receipt"])
        composite.pop("receipt_sha256")
        composite["packet_receipt"]["route_parser_version"] = "swapped-v9"
        composite["packet_receipt"].pop("receipt_sha256")
        composite["packet_receipt"] = _receipt(**composite["packet_receipt"])
        composite["packet_receipt_declared_receipt_sha256"] = composite[
            "packet_receipt"
        ]["receipt_sha256"]
        composite["packet_receipt_full_canonical_sha256"] = bridge.canonical_sha256(
            composite["packet_receipt"]
        )
        rows["windows_receipt"] = _receipt(**composite)
        _reseal_terminal(rows)
        with self.assertRaisesRegex(
            bridge.P0ActualAuthorityBridgeError, "Windows nested packet"
        ):
            _validate(rows)

    def test_windows_root_tuple_swap_fails_terminal_signature_scope(self):
        rows = _rows()
        handle = dict(rows["windows_receipt"]["windows_handle_receipt"])
        handle.pop("receipt_sha256")
        handle["root_file_id"] = "ffeeddccbbaa99887766554433221100"
        rows["windows_receipt"]["windows_handle_receipt"] = _receipt(**handle)
        _reseal_windows(rows)
        with self.assertRaisesRegex(
            bridge.P0ActualAuthorityBridgeError, "Windows composite"
        ):
            _validate(rows)

    def test_windows_trust_self_assertion_is_rejected(self):
        rows = _rows()
        composite = dict(rows["windows_receipt"])
        composite.pop("receipt_sha256")
        composite["filesystem_handle_trust_verified"] = True
        rows["windows_receipt"] = _receipt(**composite)
        _reseal_terminal(rows)
        with self.assertRaisesRegex(
            bridge.P0ActualAuthorityBridgeError, "external trust.*remain false"
        ):
            _validate(rows)

    def test_chronology_and_expiry_fail_closed(self):
        rows = _rows(actual=True)
        terminal = dict(rows["terminal"])
        terminal["issued_at"] = "2026-01-04T00:00:00Z"
        terminal["bridge_signature_sha256"] = bridge.sign_terminal_bridge_attestation(
            terminal, KEY
        )
        rows["terminal"] = bridge.with_artifact_hash(terminal)
        with self.assertRaisesRegex(bridge.P0ActualAuthorityBridgeError, "chronology"):
            _validate(rows, key=KEY)
        rows = _rows(actual=True)
        terminal = dict(rows["terminal"])
        terminal["issued_at"] = "2026-01-09T00:00:00Z"
        terminal["bridge_signature_sha256"] = bridge.sign_terminal_bridge_attestation(
            terminal, KEY
        )
        rows["terminal"] = bridge.with_artifact_hash(terminal)
        with self.assertRaisesRegex(bridge.P0ActualAuthorityBridgeError, "chronology/expiry"):
            _validate(rows, key=KEY)

    def test_caller_true_authority_flag_is_rejected(self):
        rows = _rows()
        rows["packet_receipt"]["actual_authority_granted"] = True
        rows["packet_receipt"].pop("receipt_sha256")
        rows["packet_receipt"] = _receipt(**rows["packet_receipt"])
        _reseal_windows(rows)
        _reseal_terminal(rows)
        with self.assertRaisesRegex(bridge.P0ActualAuthorityBridgeError, "must remain false"):
            _validate(rows)

    def test_receipt_self_hashes_are_recomputed(self):
        rows = _rows()
        rows["event_receipt"]["receipt_sha256"] = SHA_A
        with self.assertRaisesRegex(bridge.P0ActualAuthorityBridgeError, "receipt hash mismatch"):
            _validate(rows)


if __name__ == "__main__":
    unittest.main()
