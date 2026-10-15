#!/usr/bin/env python3
"""Build the deterministic, no-authority actual-P0 authority schema example."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from llm_batch.grounding.p0_actual_authority_contract import (  # noqa: E402
    ANCHOR_SCHEMA,
    AUTHORITY_EXAMPLE_FILES_V2,
    AUTHORIZATION_DECISION,
    AUTHORIZATION_DOMAIN,
    AUTHORIZATION_SCHEMA,
    AUTHORITY_SCOPE,
    CHECKPOINT_SCHEMA,
    EXAMPLE_ORIGIN,
    FINAL_ATTESTATION_DECISION,
    FINAL_ATTESTATION_DOMAIN,
    FINAL_ATTESTATION_SCHEMA,
    HEAD_MAP_SCHEMA,
    LAUNCH_SCHEMA,
    MANIFEST_SCHEMA,
    OPERATIONAL_EFFECT,
    PARSER_RECEIPT_SCHEMA,
    POLICY_REFS_SCHEMA,
    REQUIRED_POLICY_NAMES,
    REQUIRED_WATCH_CATEGORIES,
    WATCH_SNAPSHOT_SCHEMA,
    WATCH_SPEC_SCHEMA,
    canonical_sha256,
    validate_authority_foundation_bundle,
    with_artifact_hash,
)
from llm_batch.grounding.p0_actual_registry_contract import (  # noqa: E402
    validate_example_directory as validate_foundation_directory,
)


DEFAULT_DIRECTORY = (
    REPO_ROOT / "tests" / "fixtures" / "p0_actual_authority_contract_example_v2"
)
DEFAULT_FOUNDATION_DIRECTORY = (
    REPO_ROOT / "tests" / "fixtures" / "p0_actual_contract_example_v1"
)

FILES = AUTHORITY_EXAMPLE_FILES_V2


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _write_new_or_identical(
    path: Path,
    payload: bytes,
    *,
    refresh_existing: bool = False,
) -> None:
    if path.exists():
        if path.read_bytes() != payload:
            if refresh_existing:
                path.write_bytes(payload)
                return
            raise RuntimeError(f"refusing to overwrite non-identical authority example: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _example_head(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_record_type": event["target_record_type"],
        "target_id": event["target_id"],
        "target_subject_sha256": event["target_subject_sha256"],
        "journal_id": event["journal_id"],
        "head_sequence": event["journal_sequence"],
        "head_event_id": event["event_id"],
        "head_event_sha256": event["event_sha256"],
    }


def build_example_rows(
    foundation_directory: Path,
) -> tuple[dict[str, dict[str, Any]], str, str]:
    foundation_receipt = validate_foundation_directory(foundation_directory)
    foundation_manifest_path = (
        foundation_directory / "p0_actual_contract_example_manifest_v1.json"
    )
    foundation_manifest = json.loads(
        foundation_manifest_path.read_text(encoding="utf-8")
    )
    foundation_manifest_sha = foundation_manifest["manifest_sha256"]
    foundation_receipt_sha = foundation_receipt["receipt_sha256"]

    owner_anchor = with_artifact_hash(
        {
            "schema_version": ANCHOR_SCHEMA,
            "record_origin": EXAMPLE_ORIGIN,
            "anchor_id": "EXAMPLE:OWNER_ANCHOR:ABSENT",
            "project_id": "llm-novel-dc-community-parser",
            "owner_principal_sha256": canonical_sha256("example-owner-principal"),
            "algorithm": "HMAC-SHA256",
            "key_id": "EXAMPLE-KEY-ABSENT",
            "key_fingerprint_sha256": None,
            "trust_root_location": "EXTERNAL_KEY_ABSENT_SCHEMA_EXAMPLE",
            "allowed_scope": AUTHORITY_SCOPE,
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_to": "2027-01-01T00:00:00Z",
            "revocation_status": "UNKNOWN",
            "action_applied": False,
            "operational_effect": OPERATIONAL_EFFECT,
        }
    )

    policy_ref_rows = [
        {
            "logical_name": name,
            "status": "MISSING" if name in {"CAPTURE_POLICY", "RIGHTS_POLICY"} else "EXAMPLE_HASH_ONLY",
            "sha256": (
                None
                if name in {"CAPTURE_POLICY", "RIGHTS_POLICY"}
                else canonical_sha256(f"authority-schema-example:{name}")
            ),
        }
        for name in REQUIRED_POLICY_NAMES
    ]
    policy_refs = with_artifact_hash(
        {
            "schema_version": POLICY_REFS_SCHEMA,
            "record_origin": EXAMPLE_ORIGIN,
            "policy_refs": policy_ref_rows,
            "policy_ref_set_sha256": canonical_sha256(policy_ref_rows),
            "policy_authority_verified": False,
            "action_applied": False,
            "operational_effect": OPERATIONAL_EFFECT,
        }
    )

    watch_rules = [
        {
            "category": category,
            "relative_root": {
                "CENTRAL_SLANG_DB": "slang_db",
                "PUBLICATION_JOURNAL": "out/publication_commit_journals",
                "CHECKPOINT": "out/checkpoints",
                "RESULT": "out/results",
                "RECOVERY": "out/recovery",
                "DECISION_LEDGER": "out/decision_ledgers",
            }[category],
            "glob": "**/*",
            "recursive": True,
            "required_min_count": 1,
        }
        for category in REQUIRED_WATCH_CATEGORIES
    ]
    watch_spec = with_artifact_hash(
        {
            "schema_version": WATCH_SPEC_SCHEMA,
            "record_origin": EXAMPLE_ORIGIN,
            "watch_spec_id": "EXAMPLE:WATCH_SPEC:01",
            "rules": watch_rules,
            "required_categories_sha256": canonical_sha256(
                list(REQUIRED_WATCH_CATEGORIES)
            ),
            "rules_sha256": canonical_sha256(watch_rules),
            "allowed_write_root": "out/p0_actual_authority_example_run",
            "created_at": "2026-01-02T00:00:00Z",
            "action_applied": False,
            "operational_effect": OPERATIONAL_EFFECT,
        }
    )

    def empty_snapshot(phase: str) -> dict[str, Any]:
        return with_artifact_hash(
            {
                "schema_version": WATCH_SNAPSHOT_SCHEMA,
                "record_origin": EXAMPLE_ORIGIN,
                "snapshot_id": f"EXAMPLE:WATCH:{phase}",
                "watch_spec_sha256": watch_spec["artifact_sha256"],
                "phase": phase,
                "collected_at": None,
                "collection_status": "NOT_CAPTURED",
                "members": [],
                "membership_sha256": canonical_sha256([]),
                "required_targets_present": False,
                "directory_membership_complete": False,
                "os_write_deny_verified": False,
                "action_applied": False,
                "operational_effect": OPERATIONAL_EFFECT,
            }
        )

    watch_pre = empty_snapshot("PRE")
    watch_post = empty_snapshot("POST")

    event_path = foundation_directory / "p0_annotation_events_example_v1.jsonl"
    event_raw = event_path.read_bytes()
    event_lines = event_raw.splitlines(keepends=True)
    if len(event_lines) != 4 or any(not line.endswith(b"\n") for line in event_lines):
        raise RuntimeError("foundation annotation example framing changed")
    events = [json.loads(line.decode("utf-8")) for line in event_lines]
    heads = sorted(
        [_example_head(event) for event in events],
        key=lambda row: (row["target_record_type"], row["target_id"]),
    )
    head_map = with_artifact_hash(
        {
            "schema_version": HEAD_MAP_SCHEMA,
            "record_origin": EXAMPLE_ORIGIN,
            "head_map_id": "EXAMPLE:HEAD_MAP:CURRENT",
            "heads": heads,
            "head_count": len(heads),
            "head_map_sha256": canonical_sha256(heads),
            "one_journal_per_target_structurally": True,
            "action_applied": False,
            "operational_effect": OPERATIONAL_EFFECT,
        }
    )
    predecessor_heads = sorted(
        [_example_head(event) for event in events[:2]],
        key=lambda row: (row["target_record_type"], row["target_id"]),
    )
    predecessor_head_map = with_artifact_hash(
        {
            "schema_version": HEAD_MAP_SCHEMA,
            "record_origin": EXAMPLE_ORIGIN,
            "head_map_id": "EXAMPLE:HEAD_MAP:PREDECESSOR",
            "heads": predecessor_heads,
            "head_count": len(predecessor_heads),
            "head_map_sha256": canonical_sha256(predecessor_heads),
            "one_journal_per_target_structurally": True,
            "action_applied": False,
            "operational_effect": OPERATIONAL_EFFECT,
        }
    )
    predecessor_prefix = b"".join(event_lines[:2])
    predecessor_prefix_sha = hashlib.sha256(predecessor_prefix).hexdigest()
    predecessor = with_artifact_hash(
        {
            "schema_version": CHECKPOINT_SCHEMA,
            "record_origin": EXAMPLE_ORIGIN,
            "checkpoint_id": "EXAMPLE:ANNOTATION_CHECKPOINT:PREDECESSOR",
            "checkpoint_kind": "SCHEMA_EXAMPLE_RECONSTRUCTED_PREFIX",
            "previous_checkpoint_sha256": None,
            "event_file_sha256": predecessor_prefix_sha,
            "prefix_rows": 2,
            "prefix_bytes": len(predecessor_prefix),
            "prefix_sha256": predecessor_prefix_sha,
            "prefix_head_set_sha256": predecessor_head_map["head_map_sha256"],
            "head_map_artifact_sha256": predecessor_head_map["artifact_sha256"],
            "owner_sealed": False,
            "durable_prior_observation": False,
            "historical_append_only_verified": False,
            "created_at": "2026-02-02T14:00:00Z",
            "action_applied": False,
            "operational_effect": OPERATIONAL_EFFECT,
        }
    )
    current = with_artifact_hash(
        {
            "schema_version": CHECKPOINT_SCHEMA,
            "record_origin": EXAMPLE_ORIGIN,
            "checkpoint_id": "EXAMPLE:ANNOTATION_CHECKPOINT:CURRENT",
            "checkpoint_kind": "SCHEMA_EXAMPLE_RECONSTRUCTED_PREFIX",
            "previous_checkpoint_sha256": predecessor["artifact_sha256"],
            "event_file_sha256": hashlib.sha256(event_raw).hexdigest(),
            "prefix_rows": len(event_lines),
            "prefix_bytes": len(event_raw),
            "prefix_sha256": hashlib.sha256(event_raw).hexdigest(),
            "prefix_head_set_sha256": head_map["head_map_sha256"],
            "head_map_artifact_sha256": head_map["artifact_sha256"],
            "owner_sealed": False,
            "durable_prior_observation": False,
            "historical_append_only_verified": False,
            "created_at": "2026-02-04T14:00:00Z",
            "action_applied": False,
            "operational_effect": OPERATIONAL_EFFECT,
        }
    )

    launch = with_artifact_hash(
        {
            "schema_version": LAUNCH_SCHEMA,
            "record_origin": EXAMPLE_ORIGIN,
            "launch_id": "EXAMPLE:ACTUAL_P0:LAUNCH:NOT_STARTED",
            "launch_status": "NOT_LAUNCHED",
            "created_at": "2026-02-02T15:00:00Z",
            "capture_started_at": None,
            "foundation_manifest_sha256": foundation_manifest_sha,
            "foundation_receipt_sha256": foundation_receipt_sha,
            "owner_anchor_sha256": owner_anchor["artifact_sha256"],
            "policy_refs_sha256": policy_refs["artifact_sha256"],
            "watch_spec_sha256": watch_spec["artifact_sha256"],
            "predecessor_checkpoint_sha256": predecessor["artifact_sha256"],
            "planned_source_claim_set_sha256": canonical_sha256([]),
            "planned_a_context_set_sha256": canonical_sha256([]),
            "expected_actual_source_claims": 40,
            "expected_actual_a_context_reviews": 20,
            "observed_actual_source_claims": 0,
            "observed_actual_a_context_reviews": 0,
            "authority_scope": AUTHORITY_SCOPE,
            "owner_authorization_required": True,
            "public_apply": False,
            "central_slang_db_write": False,
            "publication_wal_write": False,
            "production_approval": False,
            "full_scan_approval": False,
            "action_applied": False,
            "operational_effect": OPERATIONAL_EFFECT,
        }
    )
    parser_receipt = with_artifact_hash(
        {
            "schema_version": PARSER_RECEIPT_SCHEMA,
            "record_origin": EXAMPLE_ORIGIN,
            "parser_run_id": "EXAMPLE:PARSER:NOT_RUN",
            "launch_sha256": launch["artifact_sha256"],
            "runtime_status": "NOT_RUN",
            "started_at": None,
            "completed_at": None,
            "capture_manifest_sha256": None,
            "input_registry_sha256": None,
            "output_claims_sha256": None,
            "generic_queue_sha256": None,
            "input_count": 0,
            "processed_count": 0,
            "typed_input_count": 0,
            "claim_row_count": 0,
            "generic_count": 0,
            "error_count": 0,
            "network_deny_verified": False,
            "run_root_containment_verified": False,
            "exact_accounting_verified": False,
            "runtime_noninterference_verified": False,
            "action_applied": False,
            "operational_effect": OPERATIONAL_EFFECT,
        }
    )
    owner_authorization = with_artifact_hash(
        {
            "schema_version": AUTHORIZATION_SCHEMA,
            "record_origin": EXAMPLE_ORIGIN,
            "domain": AUTHORIZATION_DOMAIN,
            "algorithm": "HMAC-SHA256",
            "key_id": owner_anchor["key_id"],
            "owner_anchor_sha256": owner_anchor["artifact_sha256"],
            "launch_sha256": launch["artifact_sha256"],
            "decision": AUTHORIZATION_DECISION,
            "authority_scope": AUTHORITY_SCOPE,
            "issued_at": "2026-02-02T15:00:00Z",
            "not_before": "2026-02-02T15:00:00Z",
            "expires_at": "2026-03-05T00:00:00Z",
            "nonce": "EXAMPLE-NONCE-NO-KEY",
            "public_apply": False,
            "central_slang_db_write": False,
            "publication_wal_write": False,
            "production_approval": False,
            "full_scan_approval": False,
            "authorization_signature_sha256": None,
            "verification_status": "EXTERNAL_KEY_ABSENT",
            "action_applied": False,
            "operational_effect": OPERATIONAL_EFFECT,
        }
    )
    manifest = with_artifact_hash(
        {
            "schema_version": MANIFEST_SCHEMA,
            "record_origin": EXAMPLE_ORIGIN,
            "manifest_id": "EXAMPLE:ACTUAL_AUTHORITY:MANIFEST:01",
            "foundation_manifest_sha256": foundation_manifest_sha,
            "foundation_receipt_sha256": foundation_receipt_sha,
            "owner_anchor_sha256": owner_anchor["artifact_sha256"],
            "policy_refs_sha256": policy_refs["artifact_sha256"],
            "watch_spec_sha256": watch_spec["artifact_sha256"],
            "watch_pre_sha256": watch_pre["artifact_sha256"],
            "watch_post_sha256": watch_post["artifact_sha256"],
            "predecessor_checkpoint_sha256": predecessor["artifact_sha256"],
            "predecessor_head_map_sha256": predecessor_head_map["artifact_sha256"],
            "current_checkpoint_sha256": current["artifact_sha256"],
            "head_map_sha256": head_map["artifact_sha256"],
            "launch_sha256": launch["artifact_sha256"],
            "parser_receipt_sha256": parser_receipt["artifact_sha256"],
            "owner_authorization_sha256": owner_authorization["artifact_sha256"],
            "finalized_at": None,
            "actual_source_claim_count": 0,
            "actual_a_context_review_count": 0,
            "authority": "NONE_SCHEMA_FOUNDATION_ONLY",
            "public_apply": False,
            "central_slang_db_write": False,
            "publication_wal_write": False,
            "production_approval": False,
            "full_scan_approval": False,
            "p0_phase_exit": False,
            "action_applied": False,
            "operational_effect": OPERATIONAL_EFFECT,
        }
    )
    final_attestation = with_artifact_hash(
        {
            "schema_version": FINAL_ATTESTATION_SCHEMA,
            "record_origin": EXAMPLE_ORIGIN,
            "attestation_id": "EXAMPLE:POST_RUN_ATTESTATION:UNSIGNED",
            "domain": FINAL_ATTESTATION_DOMAIN,
            "algorithm": "HMAC-SHA256",
            "key_id": owner_anchor["key_id"],
            "owner_anchor_sha256": owner_anchor["artifact_sha256"],
            "owner_authorization_sha256": owner_authorization["artifact_sha256"],
            "foundation_manifest_sha256": foundation_manifest_sha,
            "foundation_receipt_sha256": foundation_receipt_sha,
            "launch_sha256": launch["artifact_sha256"],
            "parser_receipt_sha256": parser_receipt["artifact_sha256"],
            "predecessor_checkpoint_sha256": predecessor["artifact_sha256"],
            "predecessor_head_map_sha256": predecessor_head_map["artifact_sha256"],
            "current_checkpoint_sha256": current["artifact_sha256"],
            "head_map_sha256": head_map["artifact_sha256"],
            "watch_spec_sha256": watch_spec["artifact_sha256"],
            "watch_pre_sha256": watch_pre["artifact_sha256"],
            "watch_post_sha256": watch_post["artifact_sha256"],
            "manifest_sha256": manifest["artifact_sha256"],
            "event_file_sha256": current["event_file_sha256"],
            "actual_source_claim_count": 0,
            "actual_a_context_review_count": 0,
            "decision": FINAL_ATTESTATION_DECISION,
            "authority_scope": AUTHORITY_SCOPE,
            "issued_at": "2026-02-04T15:00:00Z",
            "nonce": "EXAMPLE-POST-RUN-NONCE-NO-KEY",
            "public_apply": False,
            "central_slang_db_write": False,
            "publication_wal_write": False,
            "production_approval": False,
            "full_scan_approval": False,
            "attestation_signature_sha256": None,
            "verification_status": "EXTERNAL_KEY_ABSENT",
            "action_applied": False,
            "operational_effect": OPERATIONAL_EFFECT,
        }
    )
    rows = {
        "owner_anchor": owner_anchor,
        "policy_refs": policy_refs,
        "watch_spec": watch_spec,
        "watch_pre": watch_pre,
        "watch_post": watch_post,
        "predecessor_checkpoint": predecessor,
        "predecessor_head_map": predecessor_head_map,
        "current_checkpoint": current,
        "head_map": head_map,
        "launch": launch,
        "parser_receipt": parser_receipt,
        "owner_authorization": owner_authorization,
        "manifest": manifest,
        "final_attestation": final_attestation,
    }
    return rows, foundation_manifest_sha, foundation_receipt_sha


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument(
        "--refresh-existing",
        action="store_true",
        help="replace only the selected authority fixture with deterministic builder output",
    )
    parser.add_argument(
        "--foundation-directory", type=Path, default=DEFAULT_FOUNDATION_DIRECTORY
    )
    args = parser.parse_args()
    rows, foundation_manifest_sha, foundation_receipt_sha = build_example_rows(
        args.foundation_directory
    )
    for logical_name, row in rows.items():
        _write_new_or_identical(
            args.directory / FILES[logical_name],
            _json_bytes(row),
            refresh_existing=args.refresh_existing,
        )
    receipt = validate_authority_foundation_bundle(
        **rows,
        expected_origin=EXAMPLE_ORIGIN,
        foundation_manifest_sha256=foundation_manifest_sha,
        foundation_receipt_sha256=foundation_receipt_sha,
    )
    print(
        json.dumps(
            {
                "directory": str(args.directory.resolve()),
                "schema_check_status": receipt["schema_check_status"],
                "gate_status": receipt["gate_status"],
                "actual_source_claim_count": receipt["actual_source_claim_count"],
                "actual_a_context_review_count": receipt[
                    "actual_a_context_review_count"
                ],
                "manifest_sha256": receipt["manifest_sha256"],
                "receipt_sha256": receipt["receipt_sha256"],
                "p0_phase_exit": receipt["p0_phase_exit"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
