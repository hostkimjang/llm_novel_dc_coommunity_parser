"""Coordinated ACTUAL synthetic fixture for combined supervisor tests."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from llm_batch.grounding import p0_actual_a_context_contract as a_context
from llm_batch.grounding import p0_actual_a_event_bytes as a_event_bytes
from llm_batch.grounding import p0_actual_authority_bridge_contract as bridge
from llm_batch.grounding import p0_actual_authority_contract as authority
from llm_batch.grounding import p0_actual_authority_raw_execution as authority_raw
from llm_batch.grounding import p0_actual_owner_root_preauthorization as preauth
from llm_batch.grounding import p0_actual_packet_contract as packet
from llm_batch.grounding import p0_actual_registry_contract as registry
from llm_batch.grounding import p0_actual_route_contract as route
from llm_batch.grounding import p0_actual_supervisor_execution_contract as packet_supervisor
from llm_batch.grounding import p0_actual_authority_supervisor_execution as combined
from llm_batch.grounding import p0_windows_fixed_directory_identity as windows
from tests import test_p0_actual_authority_contract as authority_fixture
from tests import test_p0_actual_packet_contract as packet_fixture


REPO_ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_DIR = REPO_ROOT / "tests" / "fixtures" / "p0_actual_authority_contract_example_v2"
FOUNDATION_DIR = REPO_ROOT / "tests" / "fixtures" / "p0_actual_contract_example_v1"
EVENT_PATH = FOUNDATION_DIR / "p0_annotation_events_example_v1.jsonl"

KEY = b"combined-authority-supervisor-owner-key-material-32-bytes"
VOLUME_GUID = "00000000-0000-0000-0000-000000000000"
ROOT_FINAL_PATH = f"\\\\?\\Volume{{{VOLUME_GUID}}}\\packet"
ROOT_VOLUME_SERIAL = 123456789
ROOT_FILE_ID = "a" * 32
SESSION_ID = "SESSION:COMBINED:ACTUAL:01"
RUN_ID = "actual-p0-combined-run-001"


def _rehash(row: dict[str, Any]) -> dict[str, Any]:
    material = deepcopy(row)
    material.pop("artifact_sha256", None)
    return authority.with_artifact_hash(material)


def _json_bytes(value: Any) -> bytes:
    return combined.json_file_bytes(value)


def _head(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_record_type": event["target_record_type"],
        "target_id": event["target_id"],
        "target_subject_sha256": event["target_subject_sha256"],
        "journal_id": event["journal_id"],
        "head_sequence": event["journal_sequence"],
        "head_event_id": event["event_id"],
        "head_event_sha256": event["event_sha256"],
    }


def _actual_event_material(
    rows: dict[str, dict[str, Any]],
) -> tuple[bytes, dict[str, dict[str, Any]]]:
    events = [json.loads(line) for line in EVENT_PATH.read_bytes().splitlines()]
    actual_events: list[dict[str, Any]] = []
    for event in events:
        event["record_origin"] = registry.ACTUAL_ORIGIN
        event["event_sha256"] = registry._event_sha(event)
        actual_events.append(registry.with_row_hash(event))
    raw = packet.jsonl_bytes(actual_events)

    predecessor_heads = deepcopy(rows["predecessor_head_map"])
    predecessor_heads["record_origin"] = authority.ACTUAL_ORIGIN
    predecessor_heads["heads"] = sorted(
        [_head(event) for event in actual_events[:2]],
        key=lambda item: (item["target_record_type"], item["target_id"]),
    )
    predecessor_heads["head_count"] = len(predecessor_heads["heads"])
    predecessor_heads["head_map_sha256"] = authority.canonical_sha256(
        predecessor_heads["heads"]
    )
    rows["predecessor_head_map"] = _rehash(predecessor_heads)

    current_heads = deepcopy(rows["head_map"])
    current_heads["record_origin"] = authority.ACTUAL_ORIGIN
    current_heads["heads"] = sorted(
        [_head(event) for event in actual_events],
        key=lambda item: (item["target_record_type"], item["target_id"]),
    )
    current_heads["head_count"] = len(current_heads["heads"])
    current_heads["head_map_sha256"] = authority.canonical_sha256(
        current_heads["heads"]
    )
    rows["head_map"] = _rehash(current_heads)

    prefix = packet.jsonl_bytes(actual_events[:2])
    predecessor = deepcopy(rows["predecessor_checkpoint"])
    predecessor.update(
        {
            "record_origin": authority.ACTUAL_ORIGIN,
            "checkpoint_kind": "OWNER_SEALED_GENESIS",
            "event_file_sha256": hashlib.sha256(prefix).hexdigest(),
            "prefix_rows": 2,
            "prefix_bytes": len(prefix),
            "prefix_sha256": hashlib.sha256(prefix).hexdigest(),
            "prefix_head_set_sha256": rows["predecessor_head_map"]["head_map_sha256"],
            "head_map_artifact_sha256": rows["predecessor_head_map"]["artifact_sha256"],
            "owner_sealed": True,
            "durable_prior_observation": True,
            "historical_append_only_verified": False,
            "created_at": "2026-07-31T00:00:00Z",
        }
    )
    rows["predecessor_checkpoint"] = _rehash(predecessor)

    current = deepcopy(rows["current_checkpoint"])
    current.update(
        {
            "record_origin": authority.ACTUAL_ORIGIN,
            "checkpoint_kind": "OWNER_SEALED_APPEND",
            "previous_checkpoint_sha256": rows["predecessor_checkpoint"]["artifact_sha256"],
            "event_file_sha256": hashlib.sha256(raw).hexdigest(),
            "prefix_rows": len(actual_events),
            "prefix_bytes": len(raw),
            "prefix_sha256": hashlib.sha256(raw).hexdigest(),
            "prefix_head_set_sha256": rows["head_map"]["head_map_sha256"],
            "head_map_artifact_sha256": rows["head_map"]["artifact_sha256"],
            "owner_sealed": True,
            "durable_prior_observation": True,
            "historical_append_only_verified": False,
            "created_at": "2026-08-01T02:30:00Z",
        }
    )
    rows["current_checkpoint"] = _rehash(current)
    return raw, rows


def _authority_prefix() -> tuple[dict[str, dict[str, Any]], bytes, str, str]:
    rows = {
        role: json.loads((AUTHORITY_DIR / filename).read_text(encoding="utf-8"))
        for role, filename in authority.AUTHORITY_EXAMPLE_FILES_V2.items()
    }
    foundation_receipt = registry.validate_example_directory(FOUNDATION_DIR)
    foundation_manifest = json.loads(
        (FOUNDATION_DIR / "p0_actual_contract_example_manifest_v1.json").read_text(
            encoding="utf-8"
        )
    )
    event_raw, rows = _actual_event_material(rows)

    anchor = deepcopy(rows["owner_anchor"])
    anchor.update(
        {
            "record_origin": authority.ACTUAL_ORIGIN,
            "anchor_id": "ACTUAL:COMBINED:OWNER:ANCHOR",
            "key_id": "combined-owner-key-001",
            "key_fingerprint_sha256": hashlib.sha256(KEY).hexdigest(),
            "trust_root_location": "EXTERNAL_PREPROVISIONED",
            "revocation_status": "ACTIVE",
        }
    )
    rows["owner_anchor"] = _rehash(anchor)

    policies = deepcopy(rows["policy_refs"])
    policies["record_origin"] = authority.ACTUAL_ORIGIN
    for ref in policies["policy_refs"]:
        ref["status"] = "EXTERNAL_AUTHORITY_VERIFIED"
        if ref["sha256"] is None:
            ref["sha256"] = authority.canonical_sha256(ref["logical_name"])
    policies["policy_ref_set_sha256"] = authority.canonical_sha256(
        policies["policy_refs"]
    )
    policies["policy_authority_verified"] = True
    rows["policy_refs"] = _rehash(policies)

    watch_spec = deepcopy(rows["watch_spec"])
    watch_spec["record_origin"] = authority.ACTUAL_ORIGIN
    rows["watch_spec"] = _rehash(watch_spec)
    members = authority_fixture._complete_watch_members()
    for phase, collected in (
        ("pre", "2026-07-31T15:00:00Z"),
        ("post", "2026-08-01T03:00:00Z"),
    ):
        snapshot = deepcopy(rows[f"watch_{phase}"])
        snapshot.update(
            {
                "record_origin": authority.ACTUAL_ORIGIN,
                "watch_spec_sha256": rows["watch_spec"]["artifact_sha256"],
                "collection_status": "CAPTURED",
                "collected_at": collected,
                "members": deepcopy(members),
                "required_targets_present": True,
                "directory_membership_complete": True,
            }
        )
        snapshot["membership_sha256"] = authority.canonical_sha256(
            snapshot["members"]
        )
        rows[f"watch_{phase}"] = _rehash(snapshot)

    launch = deepcopy(rows["launch"])
    launch.update(
        {
            "record_origin": authority.ACTUAL_ORIGIN,
            "launch_id": "ACTUAL:COMBINED:LAUNCH:01",
            "launch_status": "SEALED_PRE_CAPTURE",
            "created_at": "2026-07-31T12:00:00Z",
            "capture_started_at": "2026-08-01T00:00:00Z",
            "owner_anchor_sha256": rows["owner_anchor"]["artifact_sha256"],
            "policy_refs_sha256": rows["policy_refs"]["artifact_sha256"],
            "watch_spec_sha256": rows["watch_spec"]["artifact_sha256"],
            "predecessor_checkpoint_sha256": rows["predecessor_checkpoint"]["artifact_sha256"],
            "observed_actual_source_claims": 40,
            "observed_actual_a_context_reviews": 20,
        }
    )
    rows["launch"] = _rehash(launch)
    return (
        rows,
        event_raw,
        foundation_manifest["manifest_sha256"],
        foundation_receipt["receipt_sha256"],
    )


def _packet_with_parser(
    launch_sha256: str,
) -> tuple[bytes, dict[str, bytes], dict[str, Any], dict[str, Any]]:
    sources, plan, seal, claims, terminals, parser_row = (
        packet_fixture._build_actual_route_rows()
    )
    parser_row = deepcopy(parser_row)
    parser_row.update(
        {
            "launch_sha256": launch_sha256,
            "started_at": "2026-08-01T01:00:00Z",
            "completed_at": "2026-08-01T02:00:00Z",
        }
    )
    parser_row = authority.with_artifact_hash(parser_row)
    candidate = packet_fixture._candidate_registry(packet.ACTUAL_ORIGIN)
    contexts, events = packet_fixture._a_rows(
        claims,
        seal,
        sources,
        candidate,
        20,
        origin=packet.ACTUAL_ORIGIN,
    )
    route_receipt = route.validate_route_bundle(
        source_snapshots=sources,
        input_plan=plan,
        selection_seal=seal,
        source_claims=claims,
        terminal_rows=terminals,
        parser_receipt=parser_row,
        expected_origin=packet.ACTUAL_ORIGIN,
    )
    selected_ids = {
        claim_id for context in contexts for claim_id in context["source_claim_ids"]
    }
    bound_claims = [claim for claim in claims if claim["claim_id"] in selected_ids]
    a_receipt = a_context.validate_actual_a_context_bundle(
        bound_claims, contexts, events
    )
    artifacts: dict[str, Any] = {
        "source_snapshots": sources,
        "controlled_payloads": packet_fixture._controlled_payloads(
            sources, origin=packet.ACTUAL_ORIGIN
        ),
        "source_input_plan": plan,
        "label_blind_selection_seal": seal,
        "source_claims": claims,
        "terminal_queue": terminals,
        "parser_receipt": parser_row,
        "candidate_registry": candidate,
        "a_contexts": contexts,
        "a_subject_selection_seal": packet_fixture._a_subject_seal(
            contexts, seal, origin=packet.ACTUAL_ORIGIN
        ),
        "a_annotation_events": events,
        "route_receipt": route_receipt,
        "a_context_receipt": a_receipt,
    }
    children = packet_fixture._child_bytes(artifacts)
    manifest = packet_fixture._manifest(
        artifacts,
        route_receipt,
        a_receipt,
        children,
        origin=packet.ACTUAL_ORIGIN,
    )
    manifest_bytes = packet.json_file_bytes(manifest)
    return manifest_bytes, children, artifacts, route_receipt


def _complete_authority_rows(
    rows: dict[str, dict[str, Any]],
    parser_row: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    rows["parser_receipt"] = deepcopy(parser_row)
    authorization = deepcopy(rows["owner_authorization"])
    authorization.update(
        {
            "record_origin": authority.ACTUAL_ORIGIN,
            "key_id": rows["owner_anchor"]["key_id"],
            "owner_anchor_sha256": rows["owner_anchor"]["artifact_sha256"],
            "launch_sha256": rows["launch"]["artifact_sha256"],
            "issued_at": "2026-07-31T13:00:00Z",
            "not_before": "2026-07-31T13:00:00Z",
            "expires_at": "2026-09-10T00:00:00Z",
            "nonce": "combined-owner-authorization-nonce-001",
            "verification_status": "DETACHED_SIGNATURE_PRESENT_UNVERIFIED",
        }
    )
    authorization["authorization_signature_sha256"] = (
        authority.sign_authorization_material(authorization, KEY)
    )
    rows["owner_authorization"] = _rehash(authorization)

    manifest = deepcopy(rows["manifest"])
    manifest.update(
        {
            "record_origin": authority.ACTUAL_ORIGIN,
            "manifest_id": "ACTUAL:COMBINED:AUTHORITY:MANIFEST:01",
            "owner_anchor_sha256": rows["owner_anchor"]["artifact_sha256"],
            "policy_refs_sha256": rows["policy_refs"]["artifact_sha256"],
            "watch_spec_sha256": rows["watch_spec"]["artifact_sha256"],
            "watch_pre_sha256": rows["watch_pre"]["artifact_sha256"],
            "watch_post_sha256": rows["watch_post"]["artifact_sha256"],
            "predecessor_checkpoint_sha256": rows["predecessor_checkpoint"]["artifact_sha256"],
            "predecessor_head_map_sha256": rows["predecessor_head_map"]["artifact_sha256"],
            "current_checkpoint_sha256": rows["current_checkpoint"]["artifact_sha256"],
            "head_map_sha256": rows["head_map"]["artifact_sha256"],
            "launch_sha256": rows["launch"]["artifact_sha256"],
            "parser_receipt_sha256": parser_row["artifact_sha256"],
            "owner_authorization_sha256": rows["owner_authorization"]["artifact_sha256"],
            "finalized_at": "2026-09-04T01:00:00Z",
            "actual_source_claim_count": 40,
            "actual_a_context_review_count": 20,
        }
    )
    rows["manifest"] = _rehash(manifest)

    final = deepcopy(rows["final_attestation"])
    final.update(
        {
            "record_origin": authority.ACTUAL_ORIGIN,
            "attestation_id": "ACTUAL:COMBINED:FINAL:01",
            "key_id": rows["owner_anchor"]["key_id"],
            "owner_anchor_sha256": rows["owner_anchor"]["artifact_sha256"],
            "owner_authorization_sha256": rows["owner_authorization"]["artifact_sha256"],
            "launch_sha256": rows["launch"]["artifact_sha256"],
            "parser_receipt_sha256": parser_row["artifact_sha256"],
            "predecessor_checkpoint_sha256": rows["predecessor_checkpoint"]["artifact_sha256"],
            "predecessor_head_map_sha256": rows["predecessor_head_map"]["artifact_sha256"],
            "current_checkpoint_sha256": rows["current_checkpoint"]["artifact_sha256"],
            "head_map_sha256": rows["head_map"]["artifact_sha256"],
            "watch_spec_sha256": rows["watch_spec"]["artifact_sha256"],
            "watch_pre_sha256": rows["watch_pre"]["artifact_sha256"],
            "watch_post_sha256": rows["watch_post"]["artifact_sha256"],
            "manifest_sha256": rows["manifest"]["artifact_sha256"],
            "event_file_sha256": rows["current_checkpoint"]["event_file_sha256"],
            "actual_source_claim_count": 40,
            "actual_a_context_review_count": 20,
            "issued_at": "2026-09-04T02:00:00Z",
            "nonce": "combined-final-attestation-nonce-001",
            "verification_status": "DETACHED_SIGNATURE_PRESENT_UNVERIFIED",
        }
    )
    final["attestation_signature_sha256"] = authority.sign_final_attestation_material(
        final, KEY
    )
    rows["final_attestation"] = _rehash(final)
    return rows


def _handle_observation(
    manifest_bytes: bytes, children: dict[str, bytes]
) -> windows.WindowsFixedDirectoryRead:
    raw = {packet.PACKET_MANIFEST_FILENAME: manifest_bytes, **children}
    members = [
        {"name": name, "bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
        for name, value in sorted(raw.items())
    ]
    material = {
        "schema_version": windows.WINDOWS_HANDLE_RECEIPT_SCHEMA,
        "platform": "win32",
        "root_final_path": ROOT_FINAL_PATH,
        "root_volume_serial": str(ROOT_VOLUME_SERIAL),
        "root_file_id": ROOT_FILE_ID,
        "members": members,
        "filesystem_handle_binding_verified": True,
        "filesystem_handle_trust_verified": False,
        "external_root_identity_pin_verified": False,
        "os_write_deny_verified": False,
        "runtime_noninterference_verified": False,
        "authority_journal_watch_bundle_verified": False,
        "external_owner_authority_verified": False,
        "actual_authority_granted": False,
        "production_approval": False,
        "full_scan_approval": False,
        "p0_phase_exit": False,
        "action_applied": False,
        "operational_effect": "NONE_SHADOW_ONLY",
    }
    receipt = {**material, "receipt_sha256": combined.canonical_sha256(material)}
    return windows.WindowsFixedDirectoryRead(raw, receipt)


def _provenance(rows: dict[str, dict[str, Any]], route_receipt: dict[str, Any]) -> dict[str, Any]:
    parser_row = rows["parser_receipt"]
    value = {
        "schema_version": bridge.PARSER_PROVENANCE_AUTHORIZATION_SCHEMA,
        "record_origin": authority.ACTUAL_ORIGIN,
        "provenance_authorization_id": "ACTUAL:COMBINED:PARSER:PROVENANCE:01",
        "domain": bridge.PARSER_PROVENANCE_DOMAIN,
        "algorithm": "HMAC-SHA256",
        "key_id": rows["owner_anchor"]["key_id"],
        "owner_anchor_sha256": rows["owner_anchor"]["artifact_sha256"],
        "owner_authorization_sha256": rows["owner_authorization"]["artifact_sha256"],
        "launch_sha256": rows["launch"]["artifact_sha256"],
        "expected_parser_receipt_schema": authority.PARSER_RECEIPT_SCHEMA,
        "expected_parser_manifest_sha256": route_receipt["parser_manifest_sha256"],
        "expected_parser_version": route_receipt["parser_version"],
        "expected_capture_manifest_sha256": parser_row["capture_manifest_sha256"],
        "expected_input_registry_sha256": parser_row["input_registry_sha256"],
        "authority_scope": bridge.AUTHORITY_SCOPE,
        "decision": bridge.PARSER_PROVENANCE_DECISION,
        "issued_at": "2026-07-31T14:00:00Z",
        "not_before": "2026-07-31T15:00:00Z",
        "expires_at": "2026-09-09T00:00:00Z",
        "nonce": "combined-provenance-nonce-001",
        "provenance_signature_sha256": None,
        "verification_status": "DETACHED_SIGNATURE_PRESENT_UNVERIFIED",
        "action_applied": False,
        "operational_effect": bridge.OPERATIONAL_EFFECT,
    }
    value["provenance_signature_sha256"] = bridge.sign_parser_provenance_authorization(
        value, KEY
    )
    return bridge.with_artifact_hash(value)


def _preauthorization(
    rows: dict[str, dict[str, Any]], route_receipt: dict[str, Any]
) -> dict[str, Any]:
    categories = [
        {
            "category": category,
            "root_id": "PROTECTED_ROOT",
            "relative_root": f"category-{index}",
            "required_min_count": 1,
        }
        for index, category in enumerate(preauth.REQUIRED_WATCH_CATEGORIES)
    ]
    parser_row = rows["parser_receipt"]
    value = {
        "schema_version": preauth.PREAUTHORIZATION_SCHEMA,
        "record_origin": authority.ACTUAL_ORIGIN,
        "preauthorization_id": "owner-root-preauth-combined-001",
        "project_id": "llm-novel-dc-community-parser",
        "run_id": RUN_ID,
        "parser_run_id": parser_row["parser_run_id"],
        "domain": preauth.PREAUTHORIZATION_DOMAIN,
        "algorithm": "HMAC-SHA256",
        "key_id": rows["owner_anchor"]["key_id"],
        "owner_principal_sha256": rows["owner_anchor"]["owner_principal_sha256"],
        "owner_anchor_sha256": rows["owner_anchor"]["artifact_sha256"],
        "foundation_manifest_sha256": rows["manifest"]["foundation_manifest_sha256"],
        "launch_sha256": rows["launch"]["artifact_sha256"],
        "owner_authorization_sha256": rows["owner_authorization"]["artifact_sha256"],
        "watch_spec_sha256": rows["watch_spec"]["artifact_sha256"],
        "expected_provenance": {
            "parser_receipt_schema": authority.PARSER_RECEIPT_SCHEMA,
            "parser_manifest_sha256": route_receipt["parser_manifest_sha256"],
            "parser_version": route_receipt["parser_version"],
            "capture_manifest_sha256": parser_row["capture_manifest_sha256"],
            "input_registry_sha256": parser_row["input_registry_sha256"],
            "source_input_plan_sha256": route_receipt["source_input_plan_sha256"],
            "sampling_frame_sha256": route_receipt["sampling_frame_sha256"],
            "packet_manifest_schema": packet.PACKET_MANIFEST_SCHEMA,
            "packet_fixed_member_contract_sha256": preauth.FIXED_MEMBER_CONTRACT_SHA256,
        },
        "allowed_packet_root": {
            "root_id": "PACKET_ROOT",
            "final_volume_guid_path": ROOT_FINAL_PATH,
            "volume_serial_decimal": str(ROOT_VOLUME_SERIAL),
            "file_id_128_hex": ROOT_FILE_ID,
            "access_intent": "WRITE_RUN_OUTPUT_ONLY",
        },
        "protected_roots": [
            {
                "root_id": "PROTECTED_ROOT",
                "final_volume_guid_path": f"\\\\?\\Volume{{{VOLUME_GUID}}}\\protected",
                "volume_serial_decimal": str(ROOT_VOLUME_SERIAL),
                "file_id_128_hex": "b" * 32,
                "access_intent": "READ_ONLY_PROTECTED",
            }
        ],
        "category_root_map": categories,
        "watch_requirements": {
            "pre_post_required": True,
            "recursive_exact_membership_required": True,
            "identity_per_member_required": True,
            "continuous_journal_or_equivalent_required": True,
            "overflow_or_gap_fail_closed": True,
            "independent_observer_required": True,
            "required_evidence_schema": "p0_watch_evidence_v1",
        },
        "write_deny_requirements": {
            "os_enforcement_required": True,
            "protected_root_ids": ["PROTECTED_ROOT"],
            "parser_principal_must_be_denied": True,
            "independent_verifier_required": True,
            "must_preexist_before_watch_pre": True,
            "must_remain_through_terminal_attestation": True,
            "required_evidence_schema": "p0_write_deny_evidence_v1",
        },
        "issued_at": "2026-07-31T13:00:00Z",
        "not_before": "2026-07-31T14:00:00Z",
        "expires_at": "2026-09-09T00:00:00Z",
        "nonce": "combined-preauthorization-nonce-001",
        "single_use": True,
        "authority_scope": preauth.AUTHORITY_SCOPE,
        "decision": preauth.PREAUTHORIZATION_DECISION,
        "public_apply": False,
        "central_slang_db_write": False,
        "publication_wal_write": False,
        "production_approval": False,
        "full_scan_approval": False,
        "preauthorization_signature_sha256": None,
        "verification_status": "DETACHED_SIGNATURE_PRESENT_UNVERIFIED",
        "action_applied": False,
        "operational_effect": preauth.OPERATIONAL_EFFECT,
    }
    value["preauthorization_signature_sha256"] = preauth.sign_preauthorization(
        value, KEY
    )
    return preauth.with_artifact_hash(value)


def _terminal(
    rows: dict[str, dict[str, Any]],
    provenance: dict[str, Any],
    packet_manifest: dict[str, Any],
    packet_receipt: dict[str, Any],
    route_receipt: dict[str, Any],
    foundation_result: dict[str, Any],
    event_result: dict[str, Any],
    a_result: dict[str, Any],
    windows_result: dict[str, Any],
) -> dict[str, Any]:
    value = {
        "schema_version": bridge.TERMINAL_BRIDGE_ATTESTATION_SCHEMA,
        "record_origin": authority.ACTUAL_ORIGIN,
        "bridge_attestation_id": "ACTUAL:COMBINED:TERMINAL:01",
        "domain": bridge.TERMINAL_BRIDGE_DOMAIN,
        "algorithm": "HMAC-SHA256",
        "key_id": rows["owner_anchor"]["key_id"],
        "owner_anchor_sha256": rows["owner_anchor"]["artifact_sha256"],
        "owner_authorization_sha256": rows["owner_authorization"]["artifact_sha256"],
        "parser_provenance_authorization_sha256": provenance["artifact_sha256"],
        "launch_sha256": rows["launch"]["artifact_sha256"],
        "keyless_manifest_file_sha256": packet_receipt["manifest_file_sha256"],
        "keyless_manifest_artifact_sha256": packet_manifest["artifact_sha256"],
        "packet_receipt_sha256": packet_receipt["receipt_sha256"],
        "route_receipt_sha256": bridge.canonical_sha256(route_receipt),
        "parser_receipt_sha256": rows["parser_receipt"]["artifact_sha256"],
        "authority_manifest_sha256": rows["manifest"]["artifact_sha256"],
        "authority_final_attestation_sha256": rows["final_attestation"]["artifact_sha256"],
        "authority_foundation_receipt_sha256": foundation_result["receipt_sha256"],
        "event_bytes_receipt_sha256": event_result["receipt_sha256"],
        "event_file_sha256": event_result["event_file_sha256"],
        "a_event_bytes_receipt_sha256": a_result["receipt_sha256"],
        "a_context_file_sha256": a_result["a_context_file_sha256"],
        "a_event_file_sha256": a_result["a_event_file_sha256"],
        "a_subject_selection_seal_sha256": a_result["a_subject_selection_seal_sha256"],
        "windows_packet_validation_receipt_sha256": windows_result["receipt_sha256"],
        "windows_expected_manifest_sha256": windows_result["expected_manifest_sha256"],
        "windows_root_final_path": ROOT_FINAL_PATH,
        "windows_root_volume_serial": str(ROOT_VOLUME_SERIAL),
        "windows_root_file_id": ROOT_FILE_ID,
        "actual_source_claim_count": 40,
        "actual_a_context_review_count": 20,
        "issued_at": "2026-09-04T03:00:00Z",
        "nonce": "combined-terminal-nonce-001",
        "decision": bridge.TERMINAL_BRIDGE_DECISION,
        "authority_scope": bridge.AUTHORITY_SCOPE,
        "bridge_signature_sha256": None,
        "verification_status": "DETACHED_SIGNATURE_PRESENT_UNVERIFIED",
        "action_applied": False,
        "operational_effect": bridge.OPERATIONAL_EFFECT,
    }
    value["bridge_signature_sha256"] = bridge.sign_terminal_bridge_attestation(
        value, KEY
    )
    return bridge.with_artifact_hash(value)


@dataclass
class CoordinatedActualFixture:
    manifest_bytes: bytes
    children: dict[str, bytes]
    observation: windows.WindowsFixedDirectoryRead
    authority_raw_by_filename: dict[str, bytes]
    annotation_event_bytes: bytes
    preauthorization: dict[str, Any]
    provenance: dict[str, Any]
    terminal: dict[str, Any]
    foundation_manifest_sha256: str
    foundation_receipt_sha256: str

    @property
    def manifest_sha256(self) -> str:
        return hashlib.sha256(self.manifest_bytes).hexdigest()

    @property
    def nonce_commitment_sha256(self) -> str:
        return combined.nonce_commitment_sha256(self.preauthorization["nonce"])

    def raw_kwargs(self) -> dict[str, Any]:
        return {
            "authority_raw_by_filename": dict(self.authority_raw_by_filename),
            "annotation_event_bytes": self.annotation_event_bytes,
            "owner_root_preauthorization_bytes": _json_bytes(self.preauthorization),
            "parser_provenance_authorization_bytes": _json_bytes(self.provenance),
            "terminal_bridge_attestation_bytes": _json_bytes(self.terminal),
        }


def build_coordinated_actual_fixture() -> CoordinatedActualFixture:
    rows, event_raw, foundation_manifest_sha, foundation_receipt_sha = _authority_prefix()
    manifest_bytes, children, artifacts, route_receipt = _packet_with_parser(
        rows["launch"]["artifact_sha256"]
    )
    rows = _complete_authority_rows(rows, artifacts["parser_receipt"])
    authority_raw_by_filename = {
        filename: _json_bytes(rows[role])
        for role, filename in authority.AUTHORITY_EXAMPLE_FILES_V2.items()
    }
    authority_state = authority_raw._execute_authority_raw_validation_state(
        authority_raw_by_filename=authority_raw_by_filename,
        annotation_event_bytes=event_raw,
        expected_authority_origin=authority.ACTUAL_ORIGIN,
        expected_event_origin=registry.ACTUAL_ORIGIN,
        foundation_manifest_sha256=foundation_manifest_sha,
        foundation_receipt_sha256=foundation_receipt_sha,
        key=KEY,
        expected_external_anchor_sha256=rows["owner_anchor"]["artifact_sha256"],
        observed_at=rows["launch"]["capture_started_at"],
    )
    observation = _handle_observation(manifest_bytes, children)
    packet_receipt = packet.validate_packet_bytes(
        manifest_bytes,
        children,
        expected_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        expected_origin=packet.ACTUAL_ORIGIN,
    )
    windows_result = windows.bind_windows_fixed_packet_observation(
        observation,
        expected_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        expected_origin=packet.ACTUAL_ORIGIN,
    )
    role_raw = {
        role: children[path] for role, path, _ in packet.CHILD_FILES
    }
    derived, _ = packet_supervisor._derive_a_source_claim_subset(
        role_raw["source_claims"], role_raw["a_contexts"]
    )
    a_result = a_event_bytes.verify_a_event_bytes(
        source_claim_bytes=derived,
        a_context_bytes=role_raw["a_contexts"],
        a_event_bytes=role_raw["a_annotation_events"],
        a_subject_selection_seal_bytes=role_raw["a_subject_selection_seal"],
        expected_origin=packet.ACTUAL_ORIGIN,
    )
    provenance = _provenance(rows, route_receipt)
    preauthorization = _preauthorization(rows, route_receipt)
    packet_manifest = json.loads(manifest_bytes)
    terminal = _terminal(
        rows,
        provenance,
        packet_manifest,
        packet_receipt,
        route_receipt,
        dict(authority_state.foundation_result),
        dict(authority_state.event_result),
        a_result,
        windows_result,
    )
    return CoordinatedActualFixture(
        manifest_bytes=manifest_bytes,
        children=children,
        observation=observation,
        authority_raw_by_filename=authority_raw_by_filename,
        annotation_event_bytes=event_raw,
        preauthorization=preauthorization,
        provenance=provenance,
        terminal=terminal,
        foundation_manifest_sha256=foundation_manifest_sha,
        foundation_receipt_sha256=foundation_receipt_sha,
    )
