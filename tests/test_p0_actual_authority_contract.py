from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import llm_batch.grounding.p0_actual_authority_contract as authority  # noqa: E402
from llm_batch.grounding.p0_actual_authority_contract import (  # noqa: E402
    ACTUAL_ORIGIN,
    EXAMPLE_ORIGIN,
    P0ActualAuthorityError,
    canonical_sha256,
    sign_authorization_material,
    sign_final_attestation_material,
    validate_authority_foundation_bundle,
    with_artifact_hash,
)
from llm_batch.grounding.p0_actual_registry_contract import (  # noqa: E402
    validate_example_directory as validate_foundation_directory,
)
from tools.build_p0_actual_authority_contract_examples import (  # noqa: E402
    FILES,
    build_example_rows,
)
from tools.validate_p0_actual_authority_contract_examples import (  # noqa: E402
    validate_example_directory,
)


FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "p0_actual_authority_contract_example_v2"
FOUNDATION_DIR = REPO_ROOT / "tests" / "fixtures" / "p0_actual_contract_example_v1"


def _load_rows(directory: Path = FIXTURE_DIR) -> dict[str, dict[str, object]]:
    return {
        name: json.loads((directory / basename).read_text(encoding="utf-8"))
        for name, basename in FILES.items()
    }


def _rehash(row: dict[str, object]) -> dict[str, object]:
    return with_artifact_hash(deepcopy(row))


def _foundation_hashes() -> tuple[str, str]:
    manifest = json.loads(
        (FOUNDATION_DIR / "p0_actual_contract_example_manifest_v1.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = validate_foundation_directory(FOUNDATION_DIR)
    return manifest["manifest_sha256"], receipt["receipt_sha256"]


def _rebind_manifest(rows: dict[str, dict[str, object]]) -> None:
    mapping = {
        "owner_anchor_sha256": "owner_anchor",
        "policy_refs_sha256": "policy_refs",
        "watch_spec_sha256": "watch_spec",
        "watch_pre_sha256": "watch_pre",
        "watch_post_sha256": "watch_post",
        "predecessor_checkpoint_sha256": "predecessor_checkpoint",
        "predecessor_head_map_sha256": "predecessor_head_map",
        "current_checkpoint_sha256": "current_checkpoint",
        "head_map_sha256": "head_map",
        "launch_sha256": "launch",
        "parser_receipt_sha256": "parser_receipt",
        "owner_authorization_sha256": "owner_authorization",
    }
    manifest = deepcopy(rows["manifest"])
    for field, logical_name in mapping.items():
        manifest[field] = rows[logical_name]["artifact_sha256"]
    rows["manifest"] = _rehash(manifest)
    attestation_mapping = {
        "owner_anchor_sha256": "owner_anchor",
        "owner_authorization_sha256": "owner_authorization",
        "launch_sha256": "launch",
        "parser_receipt_sha256": "parser_receipt",
        "predecessor_checkpoint_sha256": "predecessor_checkpoint",
        "predecessor_head_map_sha256": "predecessor_head_map",
        "current_checkpoint_sha256": "current_checkpoint",
        "head_map_sha256": "head_map",
        "watch_spec_sha256": "watch_spec",
        "watch_pre_sha256": "watch_pre",
        "watch_post_sha256": "watch_post",
        "manifest_sha256": "manifest",
    }
    attestation = deepcopy(rows["final_attestation"])
    for field, logical_name in attestation_mapping.items():
        attestation[field] = rows[logical_name]["artifact_sha256"]
    attestation["event_file_sha256"] = rows["current_checkpoint"][
        "event_file_sha256"
    ]
    attestation["actual_source_claim_count"] = rows["manifest"][
        "actual_source_claim_count"
    ]
    attestation["actual_a_context_review_count"] = rows["manifest"][
        "actual_a_context_review_count"
    ]
    rows["final_attestation"] = _rehash(attestation)


def _complete_watch_members() -> list[dict[str, object]]:
    roots = {
        "CENTRAL_SLANG_DB": "slang_db",
        "PUBLICATION_JOURNAL": "out/publication_commit_journals",
        "CHECKPOINT": "out/checkpoints",
        "RESULT": "out/results",
        "RECOVERY": "out/recovery",
        "DECISION_LEDGER": "out/decision_ledgers",
    }
    return [
        {
            "category": category,
            "relative_path": f"{roots[category]}/anchor.dat",
            "entry_type": "FILE",
            "bytes": 10,
            "sha256": canonical_sha256(f"bytes:{category}"),
            "identity_sha256": canonical_sha256(f"identity:{category}"),
        }
        for category in authority.REQUIRED_WATCH_CATEGORIES
    ]


class P0ActualAuthorityContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.foundation_manifest_sha, cls.foundation_receipt_sha = _foundation_hashes()
        cls.rows = _load_rows()

    def setUp(self) -> None:
        self.bundle = deepcopy(self.rows)

    def _validate(self, rows=None, **kwargs):
        return validate_authority_foundation_bundle(
            **(self.bundle if rows is None else rows),
            expected_origin=EXAMPLE_ORIGIN,
            foundation_manifest_sha256=self.foundation_manifest_sha,
            foundation_receipt_sha256=self.foundation_receipt_sha,
            **kwargs,
        )

    def test_directory_schema_pass_never_grants_actual_authority(self) -> None:
        receipt = validate_example_directory(FIXTURE_DIR, FOUNDATION_DIR)
        self.assertEqual(
            receipt["schema_check_status"],
            "PASS_ACTUAL_AUTHORITY_SCHEMA_EXAMPLE_ONLY",
        )
        self.assertEqual(receipt["gate_status"], "NO_GO_ACTUAL_P0_NOT_STARTED")
        self.assertEqual(receipt["actual_source_claim_count"], 0)
        self.assertEqual(receipt["actual_a_context_review_count"], 0)
        self.assertFalse(receipt["owner_authority_verified"])
        self.assertFalse(receipt["final_attestation_math_valid"])
        self.assertFalse(receipt["annotation_append_only_verified"])
        self.assertFalse(receipt["runtime_noninterference_verified"])
        self.assertFalse(receipt["p0_phase_exit"])
        self.assertFalse(receipt["production_approval"])
        self.assertFalse(receipt["full_scan_approval"])
        self.assertIn(
            "ACTUAL_EVENT_BYTES_RECEIPT_NOT_BOUND", receipt["blockers"]
        )
        self.assertIn(
            "ACTUAL_KEYLESS_PILOT_PACKET_NOT_IMPLEMENTED", receipt["blockers"]
        )

    def test_builder_is_deterministic_and_matches_fixture(self) -> None:
        rows, foundation_manifest, foundation_receipt = build_example_rows(
            FOUNDATION_DIR
        )
        self.assertEqual(rows, self.rows)
        self.assertEqual(foundation_manifest, self.foundation_manifest_sha)
        self.assertEqual(foundation_receipt, self.foundation_receipt_sha)

    def test_manifest_cannot_self_declare_authority_or_counts(self) -> None:
        for field, value, message in (
            ("authority", "OWNER_VERIFIED", "self-declare authority"),
            ("p0_phase_exit", True, "cannot exit actual P0"),
            ("actual_source_claim_count", 40, "counts zero"),
            ("actual_a_context_review_count", 20, "counts zero"),
            ("public_apply", True, "public_apply=false"),
        ):
            with self.subTest(field=field):
                row = deepcopy(self.rows["manifest"])
                row[field] = value
                row = _rehash(row)
                with self.assertRaisesRegex(P0ActualAuthorityError, message):
                    authority.validate_manifest(row, EXAMPLE_ORIGIN)

        extra = deepcopy(self.rows["manifest"])
        extra["owner_authority_verified"] = True
        with self.assertRaisesRegex(P0ActualAuthorityError, "extra"):
            authority.validate_manifest(extra, EXAMPLE_ORIGIN)

        cyclic = deepcopy(self.rows["manifest"])
        cyclic["final_attestation_sha256"] = self.rows["final_attestation"][
            "artifact_sha256"
        ]
        with self.assertRaisesRegex(P0ActualAuthorityError, "extra"):
            authority.validate_manifest(cyclic, EXAMPLE_ORIGIN)

    def test_example_origin_and_run_local_anchor_cannot_become_trusted(self) -> None:
        example = deepcopy(self.rows["owner_anchor"])
        example["key_fingerprint_sha256"] = canonical_sha256("test key")
        example["trust_root_location"] = "EXTERNAL_PREPROVISIONED"
        example["revocation_status"] = "ACTIVE"
        example = _rehash(example)
        with self.assertRaisesRegex(P0ActualAuthorityError, "must remain untrusted"):
            authority.validate_owner_anchor(example, EXAMPLE_ORIGIN)

        actual = deepcopy(self.rows["owner_anchor"])
        actual["record_origin"] = ACTUAL_ORIGIN
        actual["trust_root_location"] = "RUN_LOCAL_GENERATED"
        actual["key_fingerprint_sha256"] = canonical_sha256("test key")
        actual["revocation_status"] = "ACTIVE"
        actual = _rehash(actual)
        with self.assertRaisesRegex(P0ActualAuthorityError, "externally provisioned"):
            authority.validate_owner_anchor(actual, ACTUAL_ORIGIN)

    def test_external_owner_key_must_match_the_pinned_anchor_fingerprint(self) -> None:
        key = b"externally-provisioned-owner-key-32-bytes!!"
        anchor = deepcopy(self.rows["owner_anchor"])
        anchor["record_origin"] = ACTUAL_ORIGIN
        anchor["trust_root_location"] = "EXTERNAL_PREPROVISIONED"
        anchor["key_fingerprint_sha256"] = hashlib.sha256(key).hexdigest()
        anchor["revocation_status"] = "ACTIVE"
        anchor = _rehash(anchor)
        self.assertTrue(
            authority.check_supplied_owner_key_binding(
                anchor,
                key=key,
                expected_external_anchor_sha256=anchor["artifact_sha256"],
                observed_at="2026-02-03T00:00:00Z",
            )
        )
        with self.assertRaisesRegex(P0ActualAuthorityError, "fingerprint mismatch"):
            authority.check_supplied_owner_key_binding(
                anchor,
                key=b"different-external-owner-key-32-bytes!",
                expected_external_anchor_sha256=anchor["artifact_sha256"],
                observed_at="2026-02-03T00:00:00Z",
            )
        revoked = deepcopy(anchor)
        revoked["revocation_status"] = "REVOKED"
        revoked = _rehash(revoked)
        with self.assertRaisesRegex(P0ActualAuthorityError, "active"):
            authority.validate_owner_anchor(revoked, ACTUAL_ORIGIN)

    def test_test_key_signature_on_example_remains_non_authoritative(self) -> None:
        key = b"schema-example-test-key-material-32-bytes!!"
        row = deepcopy(self.bundle["owner_authorization"])
        row["verification_status"] = "DETACHED_SIGNATURE_PRESENT_UNVERIFIED"
        row["authorization_signature_sha256"] = sign_authorization_material(row, key)
        self.bundle["owner_authorization"] = _rehash(row)
        _rebind_manifest(self.bundle)
        receipt = self._validate(
            key=key,
            expected_external_anchor_sha256=self.bundle["owner_anchor"][
                "artifact_sha256"
            ],
            observed_at="2026-02-03T00:00:00Z",
        )
        self.assertFalse(receipt["detached_hmac_math_valid"])
        self.assertFalse(receipt["supplied_anchor_key_match"])
        self.assertFalse(receipt["owner_authority_verified"])
        self.assertEqual(receipt["actual_source_claim_count"], 0)
        self.assertFalse(receipt["p0_phase_exit"])

    def test_actual_detached_hmac_binds_key_anchor_time_domain_and_launch(self) -> None:
        key = b"actual-owner-test-key-material-32-bytes!!!"
        base = deepcopy(self.rows["owner_authorization"])
        base["record_origin"] = ACTUAL_ORIGIN
        base["verification_status"] = "DETACHED_SIGNATURE_PRESENT_UNVERIFIED"
        base["authorization_signature_sha256"] = sign_authorization_material(base, key)
        base = _rehash(base)
        _, verified = authority.validate_authorization(
            base,
            ACTUAL_ORIGIN,
            key=key,
            expected_external_anchor_sha256=base["owner_anchor_sha256"],
            observed_at="2026-02-03T00:00:00Z",
        )
        self.assertTrue(verified)

        attacks = []
        wrong_signature = deepcopy(base)
        wrong_signature["authorization_signature_sha256"] = "0" * 64
        attacks.append(("signature mismatch", _rehash(wrong_signature), key, "2026-02-03T00:00:00Z"))
        wrong_domain = deepcopy(base)
        wrong_domain["domain"] = "other-domain"
        wrong_domain["authorization_signature_sha256"] = sign_authorization_material(
            wrong_domain, key
        )
        attacks.append(("domain/algorithm", _rehash(wrong_domain), key, "2026-02-03T00:00:00Z"))
        attacks.append(("not currently valid", base, key, "2027-01-06T00:00:00Z"))
        attacks.append(("signature mismatch", base, b"wrong-owner-key-material-32-bytes!!", "2026-02-03T00:00:00Z"))
        for message, row, attack_key, observed_at in attacks:
            with self.subTest(message=message), self.assertRaisesRegex(
                P0ActualAuthorityError, message
            ):
                authority.validate_authorization(
                    row,
                    ACTUAL_ORIGIN,
                    key=attack_key,
                    expected_external_anchor_sha256=row["owner_anchor_sha256"],
                    observed_at=observed_at,
                )

    def test_actual_final_attestation_binds_full_envelope_and_domain(self) -> None:
        key = b"actual-owner-final-key-material-32-bytes!!!"
        base = deepcopy(self.rows["final_attestation"])
        base["record_origin"] = ACTUAL_ORIGIN
        base["verification_status"] = "DETACHED_SIGNATURE_PRESENT_UNVERIFIED"
        base["attestation_signature_sha256"] = sign_final_attestation_material(
            base, key
        )
        base = _rehash(base)
        _, verified = authority.validate_final_attestation(
            base,
            ACTUAL_ORIGIN,
            key=key,
            expected_external_anchor_sha256=base["owner_anchor_sha256"],
        )
        self.assertTrue(verified)

        tampered = deepcopy(base)
        tampered["verification_status"] = "EXTERNAL_KEY_ABSENT"
        tampered["attestation_signature_sha256"] = None
        tampered = _rehash(tampered)
        with self.assertRaisesRegex(P0ActualAuthorityError, "requires signature"):
            authority.validate_final_attestation(tampered, ACTUAL_ORIGIN)

        wrong_domain = deepcopy(base)
        wrong_domain["domain"] = authority.AUTHORIZATION_DOMAIN
        wrong_domain["attestation_signature_sha256"] = sign_final_attestation_material(
            wrong_domain, key
        )
        wrong_domain = _rehash(wrong_domain)
        with self.assertRaisesRegex(P0ActualAuthorityError, "domain/algorithm"):
            authority.validate_final_attestation(wrong_domain, ACTUAL_ORIGIN)

    def test_actual_origin_full_bundle_validates_math_but_never_grants_authority(self) -> None:
        key = b"actual-full-bundle-owner-key-material-32-bytes"
        rows = deepcopy(self.rows)

        anchor = deepcopy(rows["owner_anchor"])
        anchor["record_origin"] = ACTUAL_ORIGIN
        anchor["trust_root_location"] = "EXTERNAL_PREPROVISIONED"
        anchor["key_fingerprint_sha256"] = hashlib.sha256(key).hexdigest()
        anchor["revocation_status"] = "ACTIVE"
        rows["owner_anchor"] = _rehash(anchor)

        policies = deepcopy(rows["policy_refs"])
        policies["record_origin"] = ACTUAL_ORIGIN
        for ref in policies["policy_refs"]:
            ref["status"] = "EXTERNAL_AUTHORITY_VERIFIED"
            if ref["sha256"] is None:
                ref["sha256"] = canonical_sha256(ref["logical_name"])
        policies["policy_ref_set_sha256"] = canonical_sha256(
            policies["policy_refs"]
        )
        policies["policy_authority_verified"] = True
        rows["policy_refs"] = _rehash(policies)

        watch_spec = deepcopy(rows["watch_spec"])
        watch_spec["record_origin"] = ACTUAL_ORIGIN
        rows["watch_spec"] = _rehash(watch_spec)
        members = _complete_watch_members()
        for phase, collected_at in (
            ("pre", "2026-02-02T16:00:00Z"),
            ("post", "2026-02-04T14:30:00Z"),
        ):
            snapshot = deepcopy(rows[f"watch_{phase}"])
            snapshot["record_origin"] = ACTUAL_ORIGIN
            snapshot["watch_spec_sha256"] = rows["watch_spec"]["artifact_sha256"]
            snapshot["collection_status"] = "CAPTURED"
            snapshot["collected_at"] = collected_at
            snapshot["members"] = deepcopy(members)
            snapshot["membership_sha256"] = canonical_sha256(snapshot["members"])
            snapshot["required_targets_present"] = True
            snapshot["directory_membership_complete"] = True
            rows[f"watch_{phase}"] = _rehash(snapshot)

        predecessor_heads = deepcopy(rows["predecessor_head_map"])
        predecessor_heads["record_origin"] = ACTUAL_ORIGIN
        rows["predecessor_head_map"] = _rehash(predecessor_heads)
        predecessor = deepcopy(rows["predecessor_checkpoint"])
        predecessor["record_origin"] = ACTUAL_ORIGIN
        predecessor["checkpoint_kind"] = "OWNER_SEALED_GENESIS"
        predecessor["head_map_artifact_sha256"] = rows[
            "predecessor_head_map"
        ]["artifact_sha256"]
        predecessor["owner_sealed"] = True
        predecessor["durable_prior_observation"] = True
        rows["predecessor_checkpoint"] = _rehash(predecessor)

        current_heads = deepcopy(rows["head_map"])
        current_heads["record_origin"] = ACTUAL_ORIGIN
        rows["head_map"] = _rehash(current_heads)
        current = deepcopy(rows["current_checkpoint"])
        current["record_origin"] = ACTUAL_ORIGIN
        current["checkpoint_kind"] = "OWNER_SEALED_APPEND"
        current["previous_checkpoint_sha256"] = rows["predecessor_checkpoint"][
            "artifact_sha256"
        ]
        current["head_map_artifact_sha256"] = rows["head_map"]["artifact_sha256"]
        current["owner_sealed"] = True
        current["durable_prior_observation"] = True
        rows["current_checkpoint"] = _rehash(current)

        launch = deepcopy(rows["launch"])
        launch["record_origin"] = ACTUAL_ORIGIN
        launch["launch_status"] = "SEALED_PRE_CAPTURE"
        launch["capture_started_at"] = "2026-02-03T00:00:00Z"
        launch["owner_anchor_sha256"] = rows["owner_anchor"]["artifact_sha256"]
        launch["policy_refs_sha256"] = rows["policy_refs"]["artifact_sha256"]
        launch["watch_spec_sha256"] = rows["watch_spec"]["artifact_sha256"]
        launch["predecessor_checkpoint_sha256"] = rows[
            "predecessor_checkpoint"
        ]["artifact_sha256"]
        launch["observed_actual_source_claims"] = 40
        launch["observed_actual_a_context_reviews"] = 20
        rows["launch"] = _rehash(launch)

        parser = deepcopy(rows["parser_receipt"])
        parser["record_origin"] = ACTUAL_ORIGIN
        parser["launch_sha256"] = rows["launch"]["artifact_sha256"]
        parser["runtime_status"] = "COMPLETE"
        parser["started_at"] = "2026-02-03T01:00:00Z"
        parser["completed_at"] = "2026-02-04T12:00:00Z"
        for field in (
            "capture_manifest_sha256",
            "input_registry_sha256",
            "output_claims_sha256",
            "generic_queue_sha256",
        ):
            parser[field] = canonical_sha256(f"actual:{field}")
        parser["input_count"] = 40
        parser["processed_count"] = 40
        parser["typed_input_count"] = 30
        parser["claim_row_count"] = 40
        parser["generic_count"] = 10
        parser["network_deny_verified"] = True
        parser["run_root_containment_verified"] = True
        parser["exact_accounting_verified"] = True
        rows["parser_receipt"] = _rehash(parser)

        authorization = deepcopy(rows["owner_authorization"])
        authorization["record_origin"] = ACTUAL_ORIGIN
        authorization["owner_anchor_sha256"] = rows["owner_anchor"][
            "artifact_sha256"
        ]
        authorization["launch_sha256"] = rows["launch"]["artifact_sha256"]
        authorization["verification_status"] = (
            "DETACHED_SIGNATURE_PRESENT_UNVERIFIED"
        )
        authorization["authorization_signature_sha256"] = (
            sign_authorization_material(authorization, key)
        )
        rows["owner_authorization"] = _rehash(authorization)

        manifest = deepcopy(rows["manifest"])
        manifest["record_origin"] = ACTUAL_ORIGIN
        manifest["owner_anchor_sha256"] = rows["owner_anchor"]["artifact_sha256"]
        manifest["policy_refs_sha256"] = rows["policy_refs"]["artifact_sha256"]
        manifest["watch_spec_sha256"] = rows["watch_spec"]["artifact_sha256"]
        manifest["watch_pre_sha256"] = rows["watch_pre"]["artifact_sha256"]
        manifest["watch_post_sha256"] = rows["watch_post"]["artifact_sha256"]
        manifest["predecessor_checkpoint_sha256"] = rows[
            "predecessor_checkpoint"
        ]["artifact_sha256"]
        manifest["predecessor_head_map_sha256"] = rows[
            "predecessor_head_map"
        ]["artifact_sha256"]
        manifest["current_checkpoint_sha256"] = rows["current_checkpoint"][
            "artifact_sha256"
        ]
        manifest["head_map_sha256"] = rows["head_map"]["artifact_sha256"]
        manifest["launch_sha256"] = rows["launch"]["artifact_sha256"]
        manifest["parser_receipt_sha256"] = rows["parser_receipt"][
            "artifact_sha256"
        ]
        manifest["owner_authorization_sha256"] = rows[
            "owner_authorization"
        ]["artifact_sha256"]
        manifest["finalized_at"] = "2026-02-04T14:45:00Z"
        manifest["actual_source_claim_count"] = 40
        manifest["actual_a_context_review_count"] = 20
        rows["manifest"] = _rehash(manifest)

        attestation = deepcopy(rows["final_attestation"])
        attestation["record_origin"] = ACTUAL_ORIGIN
        attestation["owner_anchor_sha256"] = rows["owner_anchor"][
            "artifact_sha256"
        ]
        attestation["owner_authorization_sha256"] = rows[
            "owner_authorization"
        ]["artifact_sha256"]
        attestation["launch_sha256"] = rows["launch"]["artifact_sha256"]
        attestation["parser_receipt_sha256"] = rows["parser_receipt"][
            "artifact_sha256"
        ]
        attestation["predecessor_checkpoint_sha256"] = rows[
            "predecessor_checkpoint"
        ]["artifact_sha256"]
        attestation["predecessor_head_map_sha256"] = rows[
            "predecessor_head_map"
        ]["artifact_sha256"]
        attestation["current_checkpoint_sha256"] = rows[
            "current_checkpoint"
        ]["artifact_sha256"]
        attestation["head_map_sha256"] = rows["head_map"]["artifact_sha256"]
        attestation["watch_spec_sha256"] = rows["watch_spec"]["artifact_sha256"]
        attestation["watch_pre_sha256"] = rows["watch_pre"]["artifact_sha256"]
        attestation["watch_post_sha256"] = rows["watch_post"]["artifact_sha256"]
        attestation["manifest_sha256"] = rows["manifest"]["artifact_sha256"]
        attestation["actual_source_claim_count"] = 40
        attestation["actual_a_context_review_count"] = 20
        attestation["verification_status"] = (
            "DETACHED_SIGNATURE_PRESENT_UNVERIFIED"
        )
        attestation["attestation_signature_sha256"] = (
            sign_final_attestation_material(attestation, key)
        )
        rows["final_attestation"] = _rehash(attestation)

        receipt = validate_authority_foundation_bundle(
            **rows,
            expected_origin=ACTUAL_ORIGIN,
            foundation_manifest_sha256=self.foundation_manifest_sha,
            foundation_receipt_sha256=self.foundation_receipt_sha,
            key=key,
            expected_external_anchor_sha256=rows["owner_anchor"][
                "artifact_sha256"
            ],
            observed_at="2026-02-03T00:00:00Z",
        )
        self.assertTrue(receipt["detached_hmac_math_valid"])
        self.assertTrue(receipt["final_attestation_math_valid"])
        self.assertTrue(receipt["supplied_anchor_key_match"])
        self.assertFalse(receipt["owner_authority_verified"])
        self.assertFalse(receipt["runtime_noninterference_verified"])
        self.assertEqual(receipt["actual_source_claim_count"], 0)
        self.assertFalse(receipt["p0_phase_exit"])

    def test_final_attestation_child_binding_cannot_be_rehashed_away(self) -> None:
        attestation = deepcopy(self.bundle["final_attestation"])
        attestation["parser_receipt_sha256"] = canonical_sha256("other-parser")
        self.bundle["final_attestation"] = _rehash(attestation)
        with self.assertRaisesRegex(P0ActualAuthorityError, "final attestation parser"):
            self._validate()

    def test_policy_child_mutation_cannot_keep_stale_launch_binding(self) -> None:
        policies = deepcopy(self.bundle["policy_refs"])
        policies["policy_refs"][0]["sha256"] = canonical_sha256("rewritten policy")
        policies["policy_ref_set_sha256"] = canonical_sha256(policies["policy_refs"])
        self.bundle["policy_refs"] = _rehash(policies)
        _rebind_manifest(self.bundle)
        with self.assertRaisesRegex(P0ActualAuthorityError, "policy refs"):
            self._validate()

    def test_launch_must_precede_capture_and_preserve_fixed_target(self) -> None:
        launch = deepcopy(self.rows["launch"])
        launch["record_origin"] = ACTUAL_ORIGIN
        launch["launch_status"] = "SEALED_PRE_CAPTURE"
        launch["capture_started_at"] = "2025-12-31T23:59:59Z"
        launch = _rehash(launch)
        with self.assertRaisesRegex(P0ActualAuthorityError, "cannot precede"):
            authority.validate_launch(launch, ACTUAL_ORIGIN)

        for claims, contexts in ((39, 20), (40, 19), (41, 20), (40, 21)):
            with self.subTest(claims=claims, contexts=contexts):
                row = deepcopy(self.rows["launch"])
                row["expected_actual_source_claims"] = claims
                row["expected_actual_a_context_reviews"] = contexts
                row = _rehash(row)
                with self.assertRaisesRegex(P0ActualAuthorityError, r"fixed 40\+20"):
                    authority.validate_launch(row, EXAMPLE_ORIGIN)

    def test_checkpoint_rollback_is_rejected_after_complete_rebinding(self) -> None:
        current = deepcopy(self.bundle["current_checkpoint"])
        current["prefix_rows"] = 1
        current["prefix_bytes"] = 1
        current["prefix_sha256"] = canonical_sha256("shortened-prefix")
        current["event_file_sha256"] = current["prefix_sha256"]
        self.bundle["current_checkpoint"] = _rehash(current)
        _rebind_manifest(self.bundle)
        with self.assertRaisesRegex(P0ActualAuthorityError, "prefix rollback"):
            self._validate()

    def test_checkpoint_cannot_claim_append_only_without_external_predecessor(self) -> None:
        checkpoint = deepcopy(self.rows["predecessor_checkpoint"])
        checkpoint["historical_append_only_verified"] = True
        checkpoint = _rehash(checkpoint)
        with self.assertRaisesRegex(P0ActualAuthorityError, "cannot assert history"):
            authority.validate_checkpoint(checkpoint, EXAMPLE_ORIGIN)

    def test_head_map_rejects_forked_target_and_stale_count(self) -> None:
        row = deepcopy(self.rows["head_map"])
        duplicate = deepcopy(row["heads"][0])
        duplicate["journal_id"] = "EXAMPLE:SECOND:JOURNAL"
        duplicate["head_event_id"] = "EXAMPLE:SECOND:EVENT"
        row["heads"].insert(1, duplicate)
        row["head_count"] = len(row["heads"])
        row["head_map_sha256"] = canonical_sha256(row["heads"])
        row = _rehash(row)
        with self.assertRaisesRegex(P0ActualAuthorityError, "one head"):
            authority.validate_head_map(row, EXAMPLE_ORIGIN)

        stale = deepcopy(self.rows["head_map"])
        stale["head_count"] += 1
        stale = _rehash(stale)
        with self.assertRaisesRegex(P0ActualAuthorityError, "count mismatch"):
            authority.validate_head_map(stale, EXAMPLE_ORIGIN)

    def test_watch_spec_requires_every_fixed_category(self) -> None:
        row = deepcopy(self.rows["watch_spec"])
        row["rules"] = row["rules"][:-1]
        row["rules_sha256"] = canonical_sha256(row["rules"])
        row = _rehash(row)
        with self.assertRaisesRegex(P0ActualAuthorityError, "fixed ordered categories"):
            authority.validate_watch_spec(row, EXAMPLE_ORIGIN)

        zero = deepcopy(self.rows["watch_spec"])
        zero["rules"][0]["required_min_count"] = 0
        zero["rules_sha256"] = canonical_sha256(zero["rules"])
        zero = _rehash(zero)
        with self.assertRaisesRegex(P0ActualAuthorityError, "must be positive"):
            authority.validate_watch_spec(zero, EXAMPLE_ORIGIN)

        unsafe_glob = deepcopy(self.rows["watch_spec"])
        unsafe_glob["rules"][0]["glob"] = "../*"
        unsafe_glob["rules_sha256"] = canonical_sha256(unsafe_glob["rules"])
        unsafe_glob = _rehash(unsafe_glob)
        with self.assertRaisesRegex(P0ActualAuthorityError, "fixed recursive"):
            authority.validate_watch_spec(unsafe_glob, EXAMPLE_ORIGIN)

        nonrecursive = deepcopy(self.rows["watch_spec"])
        nonrecursive["rules"][0]["recursive"] = False
        nonrecursive["rules_sha256"] = canonical_sha256(nonrecursive["rules"])
        nonrecursive = _rehash(nonrecursive)
        with self.assertRaisesRegex(P0ActualAuthorityError, "must be recursive"):
            authority.validate_watch_spec(nonrecursive, EXAMPLE_ORIGIN)

    def test_watch_member_must_belong_to_its_category_root(self) -> None:
        members = _complete_watch_members()
        members[0]["relative_path"] = "out/results/not-a-slang-db.dat"
        for phase in ("pre", "post"):
            snapshot = deepcopy(self.bundle[f"watch_{phase}"])
            snapshot["collection_status"] = "CAPTURED"
            snapshot["collected_at"] = (
                "2026-02-03T01:00:00Z" if phase == "pre" else "2026-02-03T02:00:00Z"
            )
            snapshot["members"] = deepcopy(members)
            snapshot["membership_sha256"] = canonical_sha256(snapshot["members"])
            snapshot["required_targets_present"] = True
            snapshot["directory_membership_complete"] = True
            self.bundle[f"watch_{phase}"] = _rehash(snapshot)
        _rebind_manifest(self.bundle)
        with self.assertRaisesRegex(P0ActualAuthorityError, "category rule root"):
            self._validate()

    def test_watch_and_capture_chronology_fail_closed(self) -> None:
        members = _complete_watch_members()
        for phase, collected_at in (
            ("pre", "2026-02-03T03:00:00Z"),
            ("post", "2026-02-03T02:00:00Z"),
        ):
            snapshot = deepcopy(self.bundle[f"watch_{phase}"])
            snapshot["collection_status"] = "CAPTURED"
            snapshot["collected_at"] = collected_at
            snapshot["members"] = deepcopy(members)
            snapshot["membership_sha256"] = canonical_sha256(snapshot["members"])
            snapshot["required_targets_present"] = True
            snapshot["directory_membership_complete"] = True
            self.bundle[f"watch_{phase}"] = _rehash(snapshot)
        _rebind_manifest(self.bundle)
        with self.assertRaisesRegex(P0ActualAuthorityError, "PRE must not follow"):
            self._validate()

    def test_verified_anchor_must_be_valid_at_observation(self) -> None:
        key = b"actual-owner-test-key-material-32-bytes!!!"
        anchor = deepcopy(self.rows["owner_anchor"])
        anchor["record_origin"] = ACTUAL_ORIGIN
        anchor["trust_root_location"] = "EXTERNAL_PREPROVISIONED"
        anchor["key_fingerprint_sha256"] = hashlib.sha256(key).hexdigest()
        anchor["revocation_status"] = "ACTIVE"
        anchor = _rehash(anchor)
        with self.assertRaisesRegex(P0ActualAuthorityError, "anchor is not valid"):
            authority.check_supplied_owner_key_binding(
                anchor,
                key=key,
                expected_external_anchor_sha256=anchor["artifact_sha256"],
                observed_at="2028-01-01T00:00:00Z",
            )

    def test_watch_paths_must_be_contained(self) -> None:
        for path in (
            "../slang_db",
            "C:/slang_db",
            "/absolute/slang_db",
            "x//y",
            "x/./y",
            "CON",
        ):
            with self.subTest(path=path):
                row = deepcopy(self.rows["watch_spec"])
                row["rules"][0]["relative_root"] = path
                row["rules_sha256"] = canonical_sha256(row["rules"])
                row = _rehash(row)
                with self.assertRaisesRegex(P0ActualAuthorityError, "canonical relative"):
                    authority.validate_watch_spec(row, EXAMPLE_ORIGIN)

    def test_snapshot_cannot_self_declare_os_write_deny(self) -> None:
        row = deepcopy(self.rows["watch_pre"])
        row["os_write_deny_verified"] = True
        row = _rehash(row)
        with self.assertRaisesRegex(P0ActualAuthorityError, "self-declared OS write-deny"):
            authority.validate_watch_snapshot(row, EXAMPLE_ORIGIN)

        captured_without_time = deepcopy(self.rows["watch_pre"])
        captured_without_time["collection_status"] = "CAPTURED"
        captured_without_time = _rehash(captured_without_time)
        with self.assertRaisesRegex(P0ActualAuthorityError, "requires collected_at"):
            authority.validate_watch_snapshot(captured_without_time, EXAMPLE_ORIGIN)

    def test_terminal_equality_is_not_runtime_noninterference_without_write_deny(self) -> None:
        members = _complete_watch_members()
        for phase in ("PRE", "POST"):
            snapshot = deepcopy(self.bundle[f"watch_{phase.lower()}"])
            snapshot["collection_status"] = "CAPTURED"
            snapshot["collected_at"] = (
                "2026-02-03T01:00:00Z" if phase == "PRE" else "2026-02-03T02:00:00Z"
            )
            snapshot["members"] = deepcopy(members)
            snapshot["membership_sha256"] = canonical_sha256(snapshot["members"])
            snapshot["required_targets_present"] = True
            snapshot["directory_membership_complete"] = True
            self.bundle[f"watch_{phase.lower()}"] = _rehash(snapshot)
        _rebind_manifest(self.bundle)
        receipt = self._validate()
        self.assertTrue(receipt["terminal_membership_projection_equal"])
        self.assertFalse(receipt["runtime_write_deny_claim_present"])
        self.assertFalse(receipt["runtime_noninterference_verified"])

    def test_watch_membership_add_delete_or_replace_breaks_terminal_equality(self) -> None:
        common_members = _complete_watch_members()
        for mutation in ("add", "delete", "replace"):
            with self.subTest(mutation=mutation):
                rows = deepcopy(self.rows)
                pre_members = deepcopy(common_members)
                post_members = deepcopy(common_members)
                if mutation == "add":
                    post_members.append(
                        {
                            **deepcopy(common_members[0]),
                            "relative_path": "slang_db/added.dat",
                        }
                    )
                    post_members.sort(
                        key=lambda item: (item["category"], item["relative_path"])
                    )
                elif mutation == "delete":
                    post_members = post_members[1:]
                if mutation == "replace":
                    post_members[0]["identity_sha256"] = canonical_sha256(
                        "file-identity-after"
                    )
                for phase, members in (("pre", pre_members), ("post", post_members)):
                    snapshot = deepcopy(rows[f"watch_{phase}"])
                    snapshot["collection_status"] = "CAPTURED"
                    snapshot["collected_at"] = (
                        "2026-02-03T01:00:00Z"
                        if phase == "pre"
                        else "2026-02-03T02:00:00Z"
                    )
                    snapshot["members"] = members
                    snapshot["membership_sha256"] = canonical_sha256(members)
                    snapshot["required_targets_present"] = not (
                        mutation == "delete" and phase == "post"
                    )
                    snapshot["directory_membership_complete"] = True
                    rows[f"watch_{phase}"] = _rehash(snapshot)
                _rebind_manifest(rows)
                receipt = self._validate(rows=rows)
                self.assertFalse(receipt["terminal_membership_projection_equal"])
                self.assertFalse(receipt["runtime_noninterference_verified"])

    def test_parser_not_run_and_complete_accounting_fail_closed(self) -> None:
        not_run = deepcopy(self.rows["parser_receipt"])
        not_run["network_deny_verified"] = True
        not_run = _rehash(not_run)
        with self.assertRaisesRegex(P0ActualAuthorityError, "must remain empty"):
            authority.validate_parser_receipt(not_run, EXAMPLE_ORIGIN)

        complete = deepcopy(self.rows["parser_receipt"])
        complete["record_origin"] = ACTUAL_ORIGIN
        complete["runtime_status"] = "COMPLETE"
        complete["started_at"] = "2026-02-03T01:00:00Z"
        complete["completed_at"] = "2026-02-03T02:00:00Z"
        for field in (
            "capture_manifest_sha256",
            "input_registry_sha256",
            "output_claims_sha256",
            "generic_queue_sha256",
        ):
            complete[field] = canonical_sha256(field)
        complete["input_count"] = 2
        complete["processed_count"] = 2
        complete["typed_input_count"] = 1
        complete["claim_row_count"] = 1
        complete["generic_count"] = 0
        complete["error_count"] = 0
        complete = _rehash(complete)
        with self.assertRaisesRegex(P0ActualAuthorityError, "accounting mismatch"):
            authority.validate_parser_receipt(complete, ACTUAL_ORIGIN)

        missing_artifact = deepcopy(complete)
        missing_artifact["input_count"] = 1
        missing_artifact["processed_count"] = 1
        missing_artifact["typed_input_count"] = 1
        missing_artifact["claim_row_count"] = 1
        missing_artifact["network_deny_verified"] = True
        missing_artifact["run_root_containment_verified"] = True
        missing_artifact["exact_accounting_verified"] = True
        missing_artifact["capture_manifest_sha256"] = None
        missing_artifact = _rehash(missing_artifact)
        with self.assertRaisesRegex(P0ActualAuthorityError, "all artifact hashes"):
            authority.validate_parser_receipt(missing_artifact, ACTUAL_ORIGIN)

    def test_failed_parser_receipt_preserves_terminal_accounting(self) -> None:
        failed = deepcopy(self.rows["parser_receipt"])
        failed["record_origin"] = ACTUAL_ORIGIN
        failed["runtime_status"] = "FAILED"
        failed["started_at"] = "2026-02-03T01:00:00Z"
        failed["completed_at"] = "2026-02-03T02:00:00Z"
        for field in (
            "capture_manifest_sha256",
            "input_registry_sha256",
            "output_claims_sha256",
            "generic_queue_sha256",
        ):
            failed[field] = canonical_sha256(field)
        failed["input_count"] = 2
        failed["processed_count"] = 1
        failed["error_count"] = 1
        failed["network_deny_verified"] = True
        failed["run_root_containment_verified"] = True
        failed["exact_accounting_verified"] = True
        failed = _rehash(failed)
        self.assertEqual(
            authority.validate_parser_receipt(failed, ACTUAL_ORIGIN)[
                "runtime_status"
            ],
            "FAILED",
        )

        false_failure = deepcopy(failed)
        false_failure["input_count"] = 1
        false_failure["processed_count"] = 1
        false_failure["typed_input_count"] = 1
        false_failure["claim_row_count"] = 1
        false_failure["error_count"] = 0
        false_failure = _rehash(false_failure)
        with self.assertRaisesRegex(P0ActualAuthorityError, "failure witness"):
            authority.validate_parser_receipt(false_failure, ACTUAL_ORIGIN)

    def test_origin_mixing_fails_before_any_gate(self) -> None:
        row = deepcopy(self.bundle["policy_refs"])
        row["record_origin"] = ACTUAL_ORIGIN
        self.bundle["policy_refs"] = _rehash(row)
        _rebind_manifest(self.bundle)
        with self.assertRaisesRegex(P0ActualAuthorityError, "origin mismatch"):
            self._validate()

    def test_directory_rejects_duplicate_keys_missing_and_extra_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            copied = Path(tmp_name) / "fixture"
            shutil.copytree(FIXTURE_DIR, copied)
            manifest_path = copied / FILES["manifest"]
            text = manifest_path.read_text(encoding="utf-8")
            text = text.replace(
                '"schema_version":',
                '"schema_version":"duplicate","schema_version":',
                1,
            )
            manifest_path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(P0ActualAuthorityError, "duplicate JSON key"):
                validate_example_directory(copied, FOUNDATION_DIR)

        with tempfile.TemporaryDirectory() as tmp_name:
            copied = Path(tmp_name) / "fixture"
            shutil.copytree(FIXTURE_DIR, copied)
            (copied / "unexpected.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(P0ActualAuthorityError, "file set mismatch"):
                validate_example_directory(copied, FOUNDATION_DIR)

        with tempfile.TemporaryDirectory() as tmp_name:
            copied = Path(tmp_name) / "fixture"
            shutil.copytree(FIXTURE_DIR, copied)
            manifest_path = copied / FILES["manifest"]
            value = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_path.write_text(
                json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(P0ActualAuthorityError, "canonical JSON bytes"):
                validate_example_directory(copied, FOUNDATION_DIR)

    def test_module_has_no_writer_runtime_retriever_or_key_creation_import(self) -> None:
        module_path = (
            SRC_ROOT / "llm_batch" / "grounding" / "p0_actual_authority_contract.py"
        )
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
        forbidden = (
            "llm_batch.ledger",
            "llm_batch.runtime",
            "llm_batch.slang",
            "llm_batch.grounding.p0_actual_registry_contract",
            "pyserini",
            "requests",
            "httpx",
            "subprocess",
            "secrets",
        )
        self.assertFalse(
            sorted(name for name in imports if name.startswith(forbidden)),
            f"forbidden imports: {sorted(imports)}",
        )


if __name__ == "__main__":
    unittest.main()
