from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import llm_batch.grounding.p0_grounding_contract as p0_contract  # noqa: E402
from llm_batch.grounding.p0_grounding_contract import (  # noqa: E402
    FIXTURE_ORIGIN,
    P0GroundingContractError,
    SOURCE_PROFILES,
    build_fixture_manifest,
    build_synthetic_contract_fixture,
    canonical_sha256,
    file_sha256,
    load_jsonl,
    jsonl_bytes,
    source_record_sha256,
    validate_context_decision,
    validate_contract_bundle,
    validate_fixture_manifest,
    validate_fixture_directory,
    validate_source_claim,
    with_row_hash,
)


FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "p0_grounding_contract_v1"
SOURCE_PATH = FIXTURE_DIR / "p0_source_claim_contract_v1.jsonl"
CONTEXT_PATH = FIXTURE_DIR / "p0_context_decision_contract_v1.jsonl"
MANIFEST_PATH = FIXTURE_DIR / "p0_grounding_contract_fixture_manifest_v1.json"


class P0GroundingContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sources = load_jsonl(SOURCE_PATH)
        cls.contexts = load_jsonl(CONTEXT_PATH)

    def test_exact_p0_quotas_and_contract_only_gate(self) -> None:
        receipt = validate_fixture_directory(FIXTURE_DIR)
        self.assertEqual(receipt["fixture_origin"], FIXTURE_ORIGIN)
        self.assertEqual(receipt["gate_status"], "GO_P0_CONTRACT_FIXTURE_ONLY")
        self.assertEqual(receipt["metric_status"], "METRICS_NOT_ESTIMABLE")
        self.assertEqual(receipt["review_status"], "REVIEW_LOCKED")
        self.assertFalse(receipt["full_scan_approval"])
        self.assertEqual(receipt["source_claim_count"], 40)
        self.assertEqual(receipt["context_count"], 20)
        self.assertEqual(receipt["profile_counts"], {profile: 10 for profile in SOURCE_PROFILES})
        self.assertEqual(receipt["track_counts"], {"A": 20, "B": 20})
        self.assertEqual(receipt["eligible_independence_group_count"], 30)
        self.assertEqual(receipt["lineage_root_count"], 30)
        self.assertEqual(receipt["lineage_derivative_count"], 10)
        self.assertEqual(receipt["generic_queue_count"], 10)
        self.assertEqual(receipt["truth_counts"], {"WORK_ID": 10, "NIL": 4, "UNRESOLVED": 6})
        self.assertEqual(
            receipt["inference_counts"], {"ASSERT_WORK": 10, "ASSERT_NIL": 4, "ABSTAIN": 6}
        )
        self.assertEqual(
            receipt["publication_counts"], {"PUBLISH": 6, "HOLD": 10, "REJECT": 4}
        )
        self.assertTrue(receipt["artifact_binding_verified"])

    def test_builder_is_deterministic(self) -> None:
        sources, contexts = build_synthetic_contract_fixture()
        self.assertEqual(sources, self.sources)
        self.assertEqual(contexts, self.contexts)

    def test_identical_builder_run_is_a_filesystem_no_op(self) -> None:
        paths = (SOURCE_PATH, CONTEXT_PATH, MANIFEST_PATH)
        before = {path: (file_sha256(path), path.stat().st_mtime_ns) for path in paths}
        completed = subprocess.run(
            [sys.executable, str(REPO_ROOT / "tools" / "build_p0_grounding_contract_fixture.py")],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertEqual(before, {path: (file_sha256(path), path.stat().st_mtime_ns) for path in paths})

    def test_manifest_binds_exact_files_and_hashes(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        validated = validate_fixture_manifest(manifest, directory=FIXTURE_DIR)
        self.assertEqual(validated["source_claims"]["sha256"], file_sha256(SOURCE_PATH))
        self.assertEqual(validated["context_decisions"]["sha256"], file_sha256(CONTEXT_PATH))
        self.assertEqual(
            validated["manifest_sha256"],
            canonical_sha256({key: value for key, value in validated.items() if key != "manifest_sha256"}),
        )

    def test_validator_cli_is_read_only_for_fixture_files(self) -> None:
        before = {path: file_sha256(path) for path in (SOURCE_PATH, CONTEXT_PATH, MANIFEST_PATH)}
        completed = subprocess.run(
            [sys.executable, str(REPO_ROOT / "tools" / "validate_p0_grounding_contract.py")],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        receipt = json.loads(completed.stdout)
        self.assertEqual(receipt["gate_status"], "GO_P0_CONTRACT_FIXTURE_ONLY")
        self.assertEqual(before, {path: file_sha256(path) for path in before})

    def test_unknown_author_and_time_require_allowlisted_reason(self) -> None:
        row = deepcopy(self.sources[8])
        row["author_unknown_reason"] = None
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "author requires"):
            validate_source_claim(row)
        row = deepcopy(self.sources[8])
        row["published_at_unknown_reason"] = "made_up_reason"
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "published_at requires"):
            validate_source_claim(row)

    def test_source_content_span_and_self_hash_tamper_fail_closed(self) -> None:
        row = deepcopy(self.sources[0])
        row["span_text"] = "invented title"
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "span offsets/text mismatch"):
            validate_source_claim(row)
        row = deepcopy(self.sources[0])
        row["row_sha256"] = "0" * 64
        with self.assertRaisesRegex(P0GroundingContractError, "hash mismatch"):
            validate_source_claim(row)

    def test_source_snapshot_is_bound_to_response_bytes(self) -> None:
        row = deepcopy(self.sources[0])
        row["response_text"] += " mutated"
        row["response_bytes"] = len(row["response_text"].encode("utf-8"))
        import hashlib

        row["response_sha256"] = hashlib.sha256(row["response_text"].encode("utf-8")).hexdigest()
        row["content_sha256"] = canonical_sha256(row["response_text"])
        row["source_record_sha256"] = source_record_sha256(row)
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "snapshot_sha256 response binding"):
            validate_source_claim(row)

    def test_source_record_and_claim_direction_are_separately_bound(self) -> None:
        row = deepcopy(self.sources[0])
        row["platform"] = "MUTATED_PLATFORM"
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "source_record_sha256 mismatch"):
            validate_source_claim(row)
        row = deepcopy(self.sources[0])
        row["target_text"] = "invented-target"
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "existing claim span"):
            validate_source_claim(row)

    def test_source_identifiers_require_canonical_text(self) -> None:
        row = deepcopy(self.sources[0])
        row["source_id"] = f" {row['source_id']}"
        row["source_record_sha256"] = source_record_sha256(row)
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "canonical text"):
            validate_source_claim(row)

    def test_source_canonical_url_requires_nonempty_hostname(self) -> None:
        row = deepcopy(self.sources[0])
        row["canonical_url"] = "https://"
        row["source_record_sha256"] = source_record_sha256(row)
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "valid https URL with a hostname"):
            validate_source_claim(row)

    def test_canonical_url_rejects_invalid_port_and_credentials(self) -> None:
        for invalid_url in (
            "https://example.invalid:notaport/path",
            "https://example.invalid:99999/path",
            "https://user:pass@example.invalid/path",
        ):
            row = deepcopy(self.sources[0])
            row["canonical_url"] = invalid_url
            row["source_record_sha256"] = source_record_sha256(row)
            row = with_row_hash(row)
            with self.subTest(url=invalid_url):
                with self.assertRaisesRegex(
                    P0GroundingContractError, "valid https URL with a hostname"
                ):
                    validate_source_claim(row)

    def test_source_profile_is_bound_to_parser_family(self) -> None:
        row = deepcopy(next(row for row in self.sources if row["source_profile"] == "OFFICIAL_STRUCTURED"))
        row["parser_profile"] = "community_structured"
        row["source_record_sha256"] = source_record_sha256(row)
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "profile/parser/content-type"):
            validate_source_claim(row)

    def test_claim_kind_is_bound_to_direction_in_bundle_and_directory_paths(self) -> None:
        for claim_kind, invalid_direction in (
            ("WORK_ALIAS", "SURFACE_TO_SENSE"),
            ("COMMUNITY_SENSE", "SURFACE_TO_WORK"),
        ):
            sources = deepcopy(self.sources)
            row = next(source for source in sources if source["claim_kind"] == claim_kind)
            row["claim_direction"] = invalid_direction
            row.update(with_row_hash(row))
            with self.subTest(claim_kind=claim_kind):
                with self.assertRaisesRegex(P0GroundingContractError, "kind/direction"):
                    validate_contract_bundle(sources, self.contexts)
                with tempfile.TemporaryDirectory() as temp_directory:
                    directory = Path(temp_directory)
                    source_path = directory / "p0_source_claim_contract_v1.jsonl"
                    context_path = directory / "p0_context_decision_contract_v1.jsonl"
                    manifest_path = directory / "p0_grounding_contract_fixture_manifest_v1.json"
                    source_path.write_bytes(jsonl_bytes(sources))
                    context_path.write_bytes(jsonl_bytes(self.contexts))
                    manifest = build_fixture_manifest(
                        source_path=source_path,
                        context_path=context_path,
                        source_count=len(sources),
                        context_count=len(self.contexts),
                    )
                    manifest_path.write_text(
                        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(P0GroundingContractError, "kind/direction"):
                        validate_fixture_directory(directory)

    def test_one_source_can_emit_multiple_claim_rows_without_becoming_two_sources(self) -> None:
        rows = deepcopy(self.sources)
        second_claim = deepcopy(rows[0])
        second_claim["claim_id"] = "claim-extra-same-source"
        second_claim["item_locator"] = f"{second_claim['locator']}#claim-2"
        second_claim = with_row_hash(second_claim)
        rows.append(second_claim)
        receipt = validate_contract_bundle(rows, self.contexts)
        self.assertIn("SOURCE_CLAIM_COUNT_NOT_40", receipt["blockers"])
        self.assertEqual(receipt["lineage_root_count"], 30)

    def test_missing_lineage_ancestor_uses_contract_error(self) -> None:
        rows = deepcopy(self.sources)
        row = next(row for row in rows if row["parent_source_id"] is not None)
        row["parent_source_id"] = "missing-parent"
        row["source_record_sha256"] = source_record_sha256(row)
        row.update(with_row_hash(row))
        with self.assertRaisesRegex(P0GroundingContractError, "lineage parent is missing"):
            validate_contract_bundle(rows, self.contexts)

    def test_lineage_derivative_cannot_vote_as_independent(self) -> None:
        rows = deepcopy(self.sources)
        derived = next(row for row in rows if row["parent_source_id"] is not None)
        derived["independence_group_id"] = "invented-independent-group"
        derived["independence_status"] = "ELIGIBLE_ROOT"
        derived.update(with_row_hash(derived))
        with self.assertRaises(P0GroundingContractError):
            validate_contract_bundle(rows, self.contexts)

    def test_mirror_and_repost_preserve_parent_response_hash(self) -> None:
        by_source = {row["source_id"]: row for row in self.sources}
        derived = [
            row for row in self.sources if row["derivation_kind"] in {"MIRROR", "REPOST"}
        ]
        self.assertTrue(derived)
        self.assertTrue(
            all(
                row["response_sha256"] == by_source[row["parent_source_id"]]["response_sha256"]
                for row in derived
            )
        )

    def test_unknown_lineage_is_representable_but_never_an_independent_vote(self) -> None:
        rows = deepcopy(self.sources)
        row = rows[0]
        row["derivation_kind"] = "UNKNOWN_LINEAGE"
        row["independence_status"] = "COLLAPSED_UNKNOWN_LINEAGE"
        row["source_record_sha256"] = source_record_sha256(row)
        row.update(with_row_hash(row))
        receipt = validate_contract_bundle(rows, self.contexts)
        self.assertEqual(receipt["eligible_independence_group_count"], 29)
        self.assertIn("INDEPENDENCE_GROUP_COUNT_NOT_30", receipt["blockers"])

    def test_generic_profile_routes_to_generic_queue_without_drop(self) -> None:
        generic = [row for row in self.sources if row["source_profile"] == "GENERIC_FALLBACK"]
        self.assertEqual(len(generic), 10)
        self.assertTrue(all(row["parser_route"] == "generic_queue" for row in generic))
        row = deepcopy(generic[0])
        row["parser_route"] = "structured_profile"
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "profile/parser|generic fallback"):
            validate_source_claim(row)

    def test_all_source_profiles_are_linked_to_track_a_contexts(self) -> None:
        by_claim = {row["claim_id"]: row for row in self.sources}
        linked_profiles = {
            by_claim[claim_id]["source_profile"]
            for context in self.contexts
            for claim_id in context["source_claim_ids"]
        }
        self.assertEqual(linked_profiles, set(SOURCE_PROFILES))
        self.assertTrue(
            all(
                by_claim[claim_id]["track"] == context["track"]
                for context in self.contexts
                for claim_id in context["source_claim_ids"]
            )
        )

    def test_repair_existing_cannot_introduce_new_text(self) -> None:
        row = deepcopy(next(row for row in self.sources if row["repair_mode"] == "REPAIR_EXISTING"))
        row["repair_output_text"] = "new model-generated title"
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "existing source span"):
            validate_source_claim(row)

    def test_unavailable_cannot_become_nil(self) -> None:
        row = deepcopy(next(row for row in self.contexts if row["annotation_status"] == "UNAVAILABLE"))
        row["truth_kind"] = "NIL"
        row["truth_nil_reason"] = "NIL_NO_VALID_CANDIDATE"
        row["truth_reason_codes"] = ["truth_nil_no_canonical_target_after_complete_enumeration"]
        row["nil_receipt_sha256"] = canonical_sha256({"mutated": True})
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "must keep truth null"):
            validate_context_decision(row)

    def test_incomplete_candidate_universe_cannot_assert_nil(self) -> None:
        row = deepcopy(next(row for row in self.contexts if row["inference_decision"] == "ASSERT_NIL"))
        row["producer_status"] = "INCOMPLETE"
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "ASSERT_NIL requires"):
            validate_context_decision(row)

    def test_truth_receipts_bind_post_work_and_nil_reason(self) -> None:
        work_row = deepcopy(next(row for row in self.contexts if row["truth_kind"] == "WORK_ID"))
        work_row["post_relation_receipt_sha256"] = "0" * 64
        work_row = with_row_hash(work_row)
        with self.assertRaisesRegex(P0GroundingContractError, "post relation receipt binding"):
            validate_context_decision(work_row)
        nil_row = deepcopy(next(row for row in self.contexts if row["truth_kind"] == "NIL"))
        nil_row["nil_receipt_sha256"] = "0" * 64
        nil_row = with_row_hash(nil_row)
        with self.assertRaisesRegex(P0GroundingContractError, "NIL receipt binding"):
            validate_context_decision(nil_row)

    def test_publish_requires_healthy_complete_retrieval(self) -> None:
        row = deepcopy(next(row for row in self.contexts if row["publication_action"] == "PUBLISH"))
        row["retrieval_status"] = "UNRECOVERED"
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "ASSERT_WORK requires"):
            validate_context_decision(row)
        row = deepcopy(
            next(
                row
                for row in self.contexts
                if row["publication_action"] == "HOLD"
                and row["inference_decision"] == "ASSERT_WORK"
            )
        )
        row["producer_status"] = "UNAVAILABLE"
        row["retrieval_status"] = "UNAVAILABLE"
        row["candidate_integrity_status"] = "NO-GO"
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "ASSERT_WORK requires"):
            validate_context_decision(row)

    def test_unresolved_truth_reason_codes_must_still_be_a_list(self) -> None:
        row = deepcopy(next(row for row in self.contexts if row["annotation_status"] == "UNJUDGED"))
        row["truth_reason_codes"] = None
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "truth_reason_codes must be a list"):
            validate_context_decision(row)

    def test_annotation_operational_and_hold_reason_families_are_bound(self) -> None:
        row = deepcopy(next(row for row in self.contexts if row["annotation_status"] == "UNJUDGED"))
        row["annotation_reason_codes"] = ["evidence_retrieval_unavailable"]
        row["publication_reason_codes"] = [
            "publication_abstain_hold",
            "publication_existing_wal_no_write",
            "publication_unavailable_hold",
        ]
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "annotation status/reason"):
            validate_context_decision(row)

        row = deepcopy(next(row for row in self.contexts if row["annotation_status"] == "UNAVAILABLE"))
        row["producer_status"] = "COMPLETE"
        row["retrieval_status"] = "GO"
        row["candidate_integrity_status"] = "GO"
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "unavailable operational state"):
            validate_context_decision(row)

    def test_hold_cannot_leak_public_fields(self) -> None:
        row = deepcopy(next(row for row in self.contexts if row["publication_action"] == "HOLD"))
        row["public_work_id"] = row["candidate_work_ids"][0]
        row["public_url"] = "https://example.invalid/works/leaked"
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "must not leak"):
            validate_context_decision(row)

    def test_context_and_candidate_fingerprints_fail_closed(self) -> None:
        row = deepcopy(self.contexts[0])
        row["content_text"] += " changed"
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "content_fingerprint mismatch"):
            validate_context_decision(row)
        row = deepcopy(self.contexts[0])
        row["candidate_work_ids"].append("work-020")
        row["candidate_work_ids"] = sorted(set(row["candidate_work_ids"]))
        row["candidate_canonical_urls"]["work-020"] = "https://example.invalid/works/work-020"
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "candidate_set_fingerprint mismatch"):
            validate_context_decision(row)
        row = deepcopy(self.contexts[0])
        row["canonical_universe_sha256"] = "0" * 64
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "canonical_universe_sha256 mismatch"):
            validate_context_decision(row)

    def test_publish_url_and_success_reasons_are_bound(self) -> None:
        row = deepcopy(next(row for row in self.contexts if row["publication_action"] == "PUBLISH"))
        row["public_url"] = "https://example.invalid/unrelated"
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "URL must match"):
            validate_context_decision(row)
        row = deepcopy(next(row for row in self.contexts if row["publication_action"] == "PUBLISH"))
        row["inference_reason_codes"] = sorted(
            [*row["inference_reason_codes"], "retrieval_failclose_requires_abstain"]
        )
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "must not carry"):
            validate_context_decision(row)
        row = deepcopy(next(row for row in self.contexts if row["inference_decision"] == "ABSTAIN"))
        row["inference_reason_codes"] = sorted(
            [*row["inference_reason_codes"], "inference_candidate_selected"]
        )
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "only registered blocker"):
            validate_context_decision(row)
        row = deepcopy(next(row for row in self.contexts if row["inference_decision"] == "ABSTAIN"))
        row["publication_reason_codes"] = sorted(
            [*row["publication_reason_codes"], "publication_evidence_verified"]
        )
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "reason family|must not carry publish"):
            validate_context_decision(row)

    def test_truth_reason_family_mismatch_fails_closed(self) -> None:
        row = deepcopy(next(row for row in self.contexts if row["truth_kind"] == "WORK_ID"))
        row["truth_reason_codes"] = ["truth_nil_non_work"]
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "WORK_ID truth reason mismatch"):
            validate_context_decision(row)

    def test_duplicate_context_denominator_fails_closed(self) -> None:
        rows = deepcopy(self.contexts)
        rows[1]["post_id"] = rows[0]["post_id"]
        rows[1]["post_relation_receipt_sha256"] = canonical_sha256(
            {
                "post_id": rows[1]["post_id"],
                "work_id": rows[1]["truth_work_id"],
                "content_fingerprint": rows[1]["content_fingerprint"],
                "source_claim_ids": rows[1]["source_claim_ids"],
                "kind": "relation",
            }
        )
        rows[1].update(with_row_hash(rows[1]))
        with self.assertRaisesRegex(P0GroundingContractError, "post_id must be unique"):
            validate_contract_bundle(self.sources, rows)

    def test_global_canonical_universe_and_urls_are_consistent(self) -> None:
        rows = deepcopy(self.contexts)
        rows[-1]["canonical_universe_work_ids"].append("work-999")
        rows[-1]["canonical_universe_sha256"] = canonical_sha256(
            rows[-1]["canonical_universe_work_ids"]
        )
        rows[-1].update(with_row_hash(rows[-1]))
        validate_context_decision(rows[-1])
        with self.assertRaisesRegex(P0GroundingContractError, "one canonical universe"):
            validate_contract_bundle(self.sources, rows)

    def test_publish_requires_eligible_official_source(self) -> None:
        rows = deepcopy(self.contexts)
        row = next(row for row in rows if row["publication_action"] == "PUBLISH")
        row["source_claim_ids"] = ["claim-031"]
        row["snapshot_id"] = "snapshot-p0-t0-src-031"
        row["post_relation_receipt_sha256"] = canonical_sha256(
            {
                "post_id": row["post_id"],
                "work_id": row["truth_work_id"],
                "content_fingerprint": row["content_fingerprint"],
                "source_claim_ids": row["source_claim_ids"],
                "kind": "relation",
            }
        )
        row.update(with_row_hash(row))
        validate_context_decision(row)
        with self.assertRaisesRegex(P0GroundingContractError, "selected work|eligible official"):
            validate_contract_bundle(self.sources, rows)

    def test_publish_official_claim_must_support_selected_work(self) -> None:
        rows = deepcopy(self.contexts)
        row = next(
            row
            for row in rows
            if row["publication_action"] == "PUBLISH" and row["public_work_id"] != "work-001"
        )
        row["source_claim_ids"] = ["claim-001"]
        row["snapshot_id"] = "snapshot-p0-t0-src-001"
        row["post_relation_receipt_sha256"] = canonical_sha256(
            {
                "post_id": row["post_id"],
                "work_id": row["truth_work_id"],
                "content_fingerprint": row["content_fingerprint"],
                "source_claim_ids": row["source_claim_ids"],
                "kind": "relation",
            }
        )
        row.update(with_row_hash(row))
        validate_context_decision(row)
        with self.assertRaisesRegex(P0GroundingContractError, "selected work"):
            validate_contract_bundle(self.sources, rows)

    def test_restricted_or_failed_official_source_cannot_support_publish(self) -> None:
        for field, value in (("rights_status", "RESTRICTED_REVIEW"), ("http_status", 404)):
            sources = deepcopy(self.sources)
            row = next(source for source in sources if source["claim_id"] == "claim-001")
            row[field] = value
            row["source_record_sha256"] = source_record_sha256(row)
            row.update(with_row_hash(row))
            with self.assertRaisesRegex(P0GroundingContractError, "eligible official"):
                validate_contract_bundle(sources, self.contexts)

    def test_quote_lineage_requires_parent_span(self) -> None:
        import hashlib

        sources = deepcopy(self.sources)
        row = next(source for source in sources if source["derivation_kind"] == "QUOTE")
        row["response_text"] = f"unrelated derived body {row['span_text']}"
        row["response_bytes"] = len(row["response_text"].encode("utf-8"))
        row["response_sha256"] = hashlib.sha256(row["response_text"].encode("utf-8")).hexdigest()
        row["content_sha256"] = canonical_sha256(row["response_text"])
        row["span_start"] = row["response_text"].index(row["span_text"])
        row["span_end"] = row["span_start"] + len(row["span_text"])
        row["snapshot_sha256"] = canonical_sha256(
            {
                "snapshot_id": row["snapshot_id"],
                "regime": row["snapshot_regime"],
                "origin": row["fixture_origin"],
                "response_sha256": row["response_sha256"],
            }
        )
        row["source_record_sha256"] = source_record_sha256(row)
        row.update(with_row_hash(row))
        validate_source_claim(row)
        with self.assertRaisesRegex(P0GroundingContractError, "quoted parent span"):
            validate_contract_bundle(sources, self.contexts)

    def test_in_memory_bundle_cannot_emit_durable_go(self) -> None:
        receipt = validate_contract_bundle(self.sources, self.contexts)
        self.assertNotEqual(receipt["gate_status"], "GO_P0_CONTRACT_FIXTURE_ONLY")
        self.assertIn("ARTIFACT_BINDING_NOT_VERIFIED", receipt["blockers"])
        self.assertIn("MANIFEST_BINDING_MISSING", receipt["blockers"])
        self.assertFalse(hasattr(p0_contract, "_ARTIFACT_BINDING_TOKEN"))
        with self.assertRaises(TypeError):
            validate_contract_bundle(
                self.sources,
                self.contexts,
                source_file_sha256="1" * 64,
                context_file_sha256="2" * 64,
                manifest_sha256="3" * 64,
            )

    def test_candidate_and_public_urls_require_nonempty_hostname(self) -> None:
        row = deepcopy(next(row for row in self.contexts if row["publication_action"] == "PUBLISH"))
        selected = row["public_work_id"]
        row["candidate_canonical_urls"][selected] = "https://"
        row["candidate_set_fingerprint"] = canonical_sha256(
            [
                {"work_id": work_id, "canonical_url": row["candidate_canonical_urls"][work_id]}
                for work_id in row["candidate_work_ids"]
            ]
        )
        row["canonical_work_receipt_sha256"] = canonical_sha256(
            {"work_id": selected, "canonical_url": "https://", "kind": "canonical"}
        )
        row["public_url"] = "https://"
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "valid https URL with a hostname"):
            validate_context_decision(row)

    def test_wrong_work_publish_is_structural_but_semantic_no_go(self) -> None:
        rows = deepcopy(self.contexts)
        sources = deepcopy(self.sources)
        row = next(row for row in rows if row["publication_action"] == "PUBLISH")
        wrong_id = next(candidate for candidate in row["candidate_work_ids"] if candidate != row["truth_work_id"])
        supporting_claim = deepcopy(
            next(source for source in sources if source["claim_id"] == row["source_claim_ids"][0])
        )
        supporting_claim["claim_id"] = "claim-extra-wrong-public-work"
        supporting_claim["item_locator"] = f"{supporting_claim['locator']}#wrong-public-work"
        supporting_claim["target_work_id"] = wrong_id
        supporting_claim = with_row_hash(supporting_claim)
        sources.append(supporting_claim)
        row["source_claim_ids"] = sorted(
            [*row["source_claim_ids"], supporting_claim["claim_id"]]
        )
        row["inference_work_id"] = wrong_id
        row["public_work_id"] = wrong_id
        row["public_url"] = row["candidate_canonical_urls"][wrong_id]
        row["post_relation_receipt_sha256"] = canonical_sha256(
            {
                "post_id": row["post_id"],
                "work_id": row["truth_work_id"],
                "content_fingerprint": row["content_fingerprint"],
                "source_claim_ids": row["source_claim_ids"],
                "kind": "relation",
            }
        )
        row.update(with_row_hash(row))
        validate_context_decision(row)
        receipt = validate_contract_bundle(sources, rows)
        self.assertEqual(receipt["gate_status"], "NO_GO_P0_CONTRACT_OR_SEMANTIC_SAFETY")
        self.assertIn("WRONG_WORK_PUBLISH", receipt["blockers"])
        self.assertIn("WRONG_WORK_INFERENCE", receipt["blockers"])
        self.assertFalse(receipt["full_scan_approval"])

    def test_wrong_work_hold_is_semantic_no_go(self) -> None:
        rows = deepcopy(self.contexts)
        row = next(
            row
            for row in rows
            if row["publication_action"] == "HOLD" and row["inference_decision"] == "ASSERT_WORK"
        )
        row["inference_work_id"] = next(
            candidate for candidate in row["candidate_work_ids"] if candidate != row["truth_work_id"]
        )
        row.update(with_row_hash(row))
        validate_context_decision(row)
        receipt = validate_contract_bundle(self.sources, rows)
        self.assertIn("WRONG_WORK_INFERENCE", receipt["blockers"])

    def test_shadow_action_can_never_be_applied(self) -> None:
        row = deepcopy(self.sources[0])
        row["action_applied"] = True
        row = with_row_hash(row)
        with self.assertRaisesRegex(P0GroundingContractError, "no-write"):
            validate_source_claim(row)
        context = deepcopy(self.contexts[0])
        context["action_applied"] = True
        context = with_row_hash(context)
        with self.assertRaisesRegex(P0GroundingContractError, "no-write"):
            validate_context_decision(context)

    def test_p0_module_has_no_runtime_writer_or_external_retriever_import(self) -> None:
        module_path = SRC_ROOT / "llm_batch" / "grounding" / "p0_grounding_contract.py"
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
        forbidden_fragments = {
            "pyserini",
            "promotion_gate",
            "slang",
            "ledger",
            "expert_main",
            "agentic_pipeline",
        }
        self.assertFalse(
            {name for name in imports if any(fragment in name for fragment in forbidden_fragments)}
        )
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
        self.assertNotIn("pyserini", pyproject)


if __name__ == "__main__":
    unittest.main()
