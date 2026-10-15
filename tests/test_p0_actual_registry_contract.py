from __future__ import annotations

import ast
from copy import deepcopy
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

import llm_batch.grounding.p0_actual_registry_contract as actual_contract  # noqa: E402
from llm_batch.grounding.p0_actual_registry_contract import (  # noqa: E402
    ACTUAL_ORIGIN,
    EXAMPLE_ORIGIN,
    P0ActualContractError,
    canonical_sha256,
    validate_actual_foundation_bundle,
    validate_actual_source_snapshot,
    validate_example_directory,
    with_row_hash,
)


FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "p0_actual_contract_example_v1"
SNAPSHOT_PATH = FIXTURE_DIR / "p0_source_snapshot_registry_example_v1.jsonl"
CLAIM_PATH = FIXTURE_DIR / "p0_source_claim_example_v1.jsonl"
B_CONTEXT_PATH = FIXTURE_DIR / "p0_b_sense_contract_example_v1.jsonl"
EVENT_PATH = FIXTURE_DIR / "p0_annotation_events_example_v1.jsonl"
MANIFEST_PATH = FIXTURE_DIR / "p0_actual_contract_example_manifest_v1.json"


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _rehash_snapshot(row: dict[str, object]) -> dict[str, object]:
    row = deepcopy(row)
    row["capture_receipt_sha256"] = actual_contract._capture_receipt(row)
    row["registry_record_sha256"] = actual_contract._record_sha(
        row, "registry_record_sha256"
    )
    return with_row_hash(row)


def _rehash_claim(
    row: dict[str, object], source: dict[str, object], *, rehash_span: bool = True
) -> dict[str, object]:
    row = deepcopy(row)
    row["registry_record_sha256"] = source["registry_record_sha256"]
    row["snapshot_id"] = source["snapshot_id"]
    if rehash_span:
        row["span_sha256"] = canonical_sha256(row["span_text"])
    row["claim_evidence_receipt_sha256"] = actual_contract._claim_receipt(
        row, source["response_sha256"]
    )
    return with_row_hash(row)


def _rehash_b_context(row: dict[str, object]) -> dict[str, object]:
    row = deepcopy(row)
    row["content_fingerprint"] = canonical_sha256(row["content_text"])
    row["surface_start"] = row["content_text"].index(row["surface_text"])
    row["surface_end"] = row["surface_start"] + len(row["surface_text"])
    row["surface_sha256"] = canonical_sha256(row["surface_text"])
    row["candidate_set_fingerprint"] = canonical_sha256(row["candidate_sense_ids"])
    truth_receipt, inference_receipt = actual_contract._b_receipts(row)
    row["truth_evidence_receipt_sha256"] = truth_receipt
    row["inference_input_receipt_sha256"] = inference_receipt
    row["annotation_subject_sha256"] = actual_contract._annotation_subject_sha(row)
    return with_row_hash(row)


def _rehash_event(row: dict[str, object]) -> dict[str, object]:
    row = deepcopy(row)
    row["event_sha256"] = actual_contract._event_sha(row)
    return with_row_hash(row)


def _rebind_context_claim_sets(
    contexts: list[dict[str, object]], claims: list[dict[str, object]]
) -> list[dict[str, object]]:
    by_claim = {row["claim_id"]: row for row in claims}
    rebound = []
    for context in deepcopy(contexts):
        context["truth_claim_set_sha256"] = actual_contract._claim_set_sha(
            [by_claim[claim_id] for claim_id in context["truth_source_claim_ids"]]
        )
        context["inference_claim_set_sha256"] = actual_contract._claim_set_sha(
            [by_claim[claim_id] for claim_id in context["inference_source_claim_ids"]]
        )
        rebound.append(_rehash_b_context(context))
    return rebound


def _rebind_events_to_contexts(
    events: list[dict[str, object]], contexts: list[dict[str, object]]
) -> list[dict[str, object]]:
    by_event_id = {row["annotation_event_id"]: row for row in contexts}
    rebound = []
    for event in deepcopy(events):
        context = by_event_id[event["event_id"]]
        event["target_subject_sha256"] = context["annotation_subject_sha256"]
        event["decision_payload_sha256"] = actual_contract._decision_payload_sha(
            context
        )
        rebound.append(_rehash_event(event))
    return rebound


def _derived_snapshot(
    root: dict[str, object],
    *,
    suffix: str,
    derivation_kind: str,
    parent_registry_record_id: str | None = None,
) -> dict[str, object]:
    row = deepcopy(root)
    row["registry_record_id"] = f"EXAMPLE:REGISTRY:{suffix}"
    row["snapshot_id"] = f"EXAMPLE:SNAPSHOT:{suffix}"
    if derivation_kind != "TEMPORAL_REVISION":
        row["source_id"] = f"EXAMPLE:SOURCE:{suffix}"
    row["parent_registry_record_id"] = (
        root["registry_record_id"]
        if parent_registry_record_id is None
        else parent_registry_record_id
    )
    row["lineage_root_id"] = root["registry_record_id"]
    row["derivation_kind"] = derivation_kind
    row["independence_status"] = "COLLAPSED_DERIVATIVE"
    row["lineage_reason_codes"] = [
        "lineage_temporal_revision_collapsed"
        if derivation_kind == "TEMPORAL_REVISION"
        else "lineage_derivative_verified"
    ]
    row["publication_evidence_eligible"] = False
    return _rehash_snapshot(row)


def _manifest_hash(manifest: dict[str, object]) -> dict[str, object]:
    material = deepcopy(manifest)
    material.pop("manifest_sha256", None)
    material["manifest_sha256"] = canonical_sha256(material)
    return material


class P0ActualRegistryContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        required = (SNAPSHOT_PATH, CLAIM_PATH, B_CONTEXT_PATH, EVENT_PATH, MANIFEST_PATH)
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise AssertionError(f"actual contract example fixture is missing: {missing}")
        cls.snapshots = _load_jsonl(SNAPSHOT_PATH)
        cls.claims = _load_jsonl(CLAIM_PATH)
        cls.b_contexts = _load_jsonl(B_CONTEXT_PATH)
        cls.events = _load_jsonl(EVENT_PATH)

    def setUp(self) -> None:
        self.source_rows = deepcopy(self.snapshots)
        self.claim_rows = deepcopy(self.claims)
        self.context_rows = deepcopy(self.b_contexts)
        self.event_rows = deepcopy(self.events)

    def _source(self, *, derivation: str | None = None, profile: str | None = None):
        return next(
            row
            for row in self.source_rows
            if (derivation is None or row["derivation_kind"] == derivation)
            and (profile is None or row["source_profile"] == profile)
        )

    def _context(self, *, truth: str | None = None, publication: str | None = None):
        return next(
            row
            for row in self.context_rows
            if (truth is None or row["truth_kind"] == truth)
            and (publication is None or row["publication_action"] == publication)
        )

    def _validate_example_bundle(
        self,
        *,
        snapshots=None,
        claims=None,
        contexts=None,
        events=None,
    ):
        return actual_contract._validate_bundle(
            self.source_rows if snapshots is None else snapshots,
            self.claim_rows if claims is None else claims,
            self.context_rows if contexts is None else contexts,
            self.event_rows if events is None else events,
            expected_origin=EXAMPLE_ORIGIN,
        )

    def _sync_claim_bindings(self) -> None:
        by_registry = {row["registry_record_id"]: row for row in self.source_rows}
        self.claim_rows = [
            _rehash_claim(row, by_registry[row["registry_record_id"]])
            for row in self.claim_rows
        ]
        self.context_rows = _rebind_context_claim_sets(
            self.context_rows, self.claim_rows
        )
        self.event_rows = _rebind_events_to_contexts(
            self.event_rows, self.context_rows
        )

    def test_durable_directory_schema_pass_and_actual_gate_stays_closed(self) -> None:
        receipt = validate_example_directory(FIXTURE_DIR)
        self.assertEqual(receipt["record_origin"], EXAMPLE_ORIGIN)
        self.assertEqual(receipt["gate_status"], "NO_GO_ACTUAL_P0_NOT_STARTED")
        self.assertEqual(
            receipt["schema_check_status"],
            "PASS_ACTUAL_SCHEMA_CONTRACT_EXAMPLE_ONLY",
        )
        self.assertEqual(receipt["actual_gate_status"], "NO_GO_ACTUAL_P0_NOT_STARTED")
        self.assertEqual(receipt["metric_status"], "METRICS_NOT_ESTIMABLE")
        self.assertEqual(receipt["review_status"], "REVIEW_LOCKED")
        self.assertEqual(receipt["actual_source_claim_count"], 0)
        self.assertEqual(receipt["actual_a_context_review_count"], 0)
        self.assertFalse(receipt["p0_phase_exit"])
        self.assertFalse(receipt["full_scan_approval"])
        self.assertTrue(receipt["artifact_binding_verified"])
        self.assertTrue(receipt["payload_binding_verified"])

    def test_actual_in_memory_validation_can_never_grant_go(self) -> None:
        receipt = validate_actual_foundation_bundle([], [], [], [])
        self.assertEqual(receipt["record_origin"], ACTUAL_ORIGIN)
        self.assertEqual(receipt["gate_status"], "NO_GO_ACTUAL_P0_NOT_STARTED")
        self.assertEqual(
            receipt["schema_check_status"], "STRUCTURE_VALID_NO_DURABLE_AUTHORITY"
        )
        self.assertEqual(receipt["actual_gate_status"], "NO_GO_ACTUAL_P0_NOT_STARTED")
        self.assertEqual(receipt["source_snapshot_count"], 0)
        self.assertEqual(receipt["source_claim_count"], 0)
        self.assertEqual(receipt["actual_source_claim_count"], 0)
        self.assertEqual(receipt["actual_a_context_review_count"], 0)
        self.assertFalse(receipt["artifact_binding_verified"])
        self.assertFalse(receipt["payload_binding_verified"])
        self.assertFalse(receipt["p0_phase_exit"])

    def test_actual_and_example_origin_url_namespaces_are_disjoint(self) -> None:
        row = deepcopy(self.source_rows[0])
        row["record_origin"] = ACTUAL_ORIGIN
        row["canonical_url"] = "https://evidence.example.kr/community/post/1"
        row = _rehash_snapshot(row)
        self.assertEqual(validate_actual_source_snapshot(row)["record_origin"], ACTUAL_ORIGIN)

        reserved_actual = deepcopy(row)
        reserved_actual["canonical_url"] = "https://source.example/post/1"
        reserved_actual = _rehash_snapshot(reserved_actual)
        with self.assertRaisesRegex(P0ActualContractError, "non-reserved actual"):
            validate_actual_source_snapshot(reserved_actual)

        actual_url_in_example = deepcopy(self.source_rows[0])
        actual_url_in_example["canonical_url"] = "https://evidence.example.kr/post/1"
        actual_url_in_example = _rehash_snapshot(actual_url_in_example)
        with self.assertRaisesRegex(P0ActualContractError, "reserved example"):
            actual_contract._validate_source_snapshot(actual_url_in_example, EXAMPLE_ORIGIN)

    def test_registry_and_claim_hashes_snapshot_and_span_fail_closed(self) -> None:
        source = self.source_rows[0]
        claim = next(
            row for row in self.claim_rows if row["registry_record_id"] == source["registry_record_id"]
        )
        attacks = []
        registry_hash = deepcopy(source)
        registry_hash["registry_record_sha256"] = "0" * 64
        attacks.append(("registry_record_sha256", [registry_hash], self.claim_rows))

        claim_registry = deepcopy(claim)
        claim_registry["registry_record_sha256"] = "1" * 64
        claim_registry = with_row_hash(claim_registry)
        attacks.append(("claim/registry", self.source_rows, [claim_registry]))

        claim_snapshot = deepcopy(claim)
        claim_snapshot["snapshot_id"] = "snapshot-forged"
        claim_snapshot = with_row_hash(claim_snapshot)
        attacks.append(("snapshot", self.source_rows, [claim_snapshot]))

        for label, sources, claims in attacks:
            with self.subTest(label=label), self.assertRaises(P0ActualContractError):
                self._validate_example_bundle(
                    snapshots=sources, claims=claims, contexts=[], events=[]
                )

        span_hash = deepcopy(claim)
        span_hash["span_sha256"] = "2" * 64
        span_hash = with_row_hash(span_hash)
        with self.assertRaisesRegex(P0ActualContractError, "span_sha256"):
            actual_contract._validate_source_claim(span_hash, EXAMPLE_ORIGIN)

    def test_directory_payload_span_binding_rejects_validly_rehashed_wrong_offsets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            copied = Path(tmp_name) / "fixture"
            shutil.copytree(FIXTURE_DIR, copied)
            claim_path = copied / CLAIM_PATH.name
            claims = _load_jsonl(claim_path)
            source_rows = _load_jsonl(copied / SNAPSHOT_PATH.name)
            source = {row["registry_record_id"]: row for row in source_rows}[
                claims[0]["registry_record_id"]
            ]
            claims[0]["span_start"] = 1
            claims[0]["span_end"] = 1 + len(claims[0]["span_text"])
            claims[0] = _rehash_claim(claims[0], source)
            claim_path.write_bytes(actual_contract.jsonl_bytes(claims))
            manifest_path = copied / MANIFEST_PATH.name
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source_claims"] = actual_contract._file_ref(claim_path, len(claims))
            manifest_path.write_text(
                json.dumps(_manifest_hash(manifest), ensure_ascii=False, sort_keys=True, indent=2)
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(P0ActualContractError, "controlled payload"):
                validate_example_directory(copied)

    def test_lineage_missing_parent_and_cycle_fail_closed(self) -> None:
        root = deepcopy(self._source(derivation="ORIGINAL"))
        missing = _derived_snapshot(
            root,
            suffix="MISSING",
            derivation_kind="REPOST",
            parent_registry_record_id="registry-missing",
        )
        sources = self.source_rows + [missing]
        with self.assertRaisesRegex(P0ActualContractError, "parent is missing"):
            self._validate_example_bundle(snapshots=sources, claims=[], contexts=[], events=[])

        first = _derived_snapshot(
            root,
            suffix="CYCLE_A",
            derivation_kind="REPOST",
            parent_registry_record_id="EXAMPLE:REGISTRY:CYCLE_B",
        )
        second = _derived_snapshot(
            root,
            suffix="CYCLE_B",
            derivation_kind="REPOST",
            parent_registry_record_id="EXAMPLE:REGISTRY:CYCLE_A",
        )
        with self.assertRaisesRegex(P0ActualContractError, "cycle"):
            self._validate_example_bundle(
                snapshots=[root, first, second], claims=[], contexts=[], events=[]
            )

    def test_temporal_revision_preserves_source_and_cannot_vote_independently(self) -> None:
        root = deepcopy(self._source(derivation="ORIGINAL"))
        temporal = _derived_snapshot(
            root, suffix="TEMPORAL", derivation_kind="TEMPORAL_REVISION"
        )
        self.assertEqual(temporal["independence_status"], "COLLAPSED_DERIVATIVE")
        self._validate_example_bundle(
            snapshots=self.source_rows + [temporal], claims=[], contexts=[], events=[]
        )

        temporal["source_id"] = "different-logical-source"
        replacement = _rehash_snapshot(temporal)
        sources = self.source_rows + [replacement]
        with self.assertRaisesRegex(P0ActualContractError, "logical source_id"):
            self._validate_example_bundle(snapshots=sources, claims=[], contexts=[], events=[])

    def test_mirror_requires_equal_response_but_repost_may_differ(self) -> None:
        root = deepcopy(self._source(derivation="ORIGINAL"))
        mirror = _derived_snapshot(root, suffix="MIRROR", derivation_kind="MIRROR")
        mirror["response_sha256"] = canonical_sha256("changed mirror response")
        mirror = _rehash_snapshot(mirror)
        mirror_sources = self.source_rows + [mirror]
        with self.assertRaisesRegex(P0ActualContractError, "mirror must preserve"):
            self._validate_example_bundle(
                snapshots=mirror_sources, claims=[], contexts=[], events=[]
            )

        repost = _derived_snapshot(root, suffix="REPOST", derivation_kind="REPOST")
        repost["response_sha256"] = canonical_sha256("changed repost response")
        repost = _rehash_snapshot(repost)
        repost_sources = self.source_rows + [repost]
        receipt = self._validate_example_bundle(
            snapshots=repost_sources, claims=[], contexts=[], events=[]
        )
        self.assertEqual(receipt["gate_status"], "NO_GO_ACTUAL_P0_NOT_STARTED")

    def test_rights_unknown_revoked_retention_and_publication_fail_closed(self) -> None:
        base = deepcopy(self._source(derivation="ORIGINAL"))
        attacks = []

        unknown = deepcopy(base)
        unknown["rights_assessment_status"] = "UNKNOWN"
        unknown["rights_reason_codes"] = ["rights_unknown_fail_closed"]
        attacks.append(("unknown", _rehash_snapshot(unknown)))

        retention = deepcopy(base)
        retention["content_retention_allowed"] = False
        attacks.append(("retention", _rehash_snapshot(retention)))

        revoked = deepcopy(base)
        revoked["rights_assessment_status"] = "REVOKED"
        revoked["rights_reason_codes"] = ["rights_revoked_and_deleted"]
        for field in (
            "collection_allowed",
            "content_retention_allowed",
            "derived_index_allowed",
            "quotation_allowed",
            "publication_evidence_eligible",
        ):
            revoked[field] = False
        revoked["retention_class"] = "HASH_ONLY"
        revoked["payload_ref"] = None
        revoked["takedown_status"] = "REMOVED"
        revoked["payload_deletion_receipt_sha256"] = None
        revoked["derived_index_deletion_receipt_sha256"] = None
        attacks.append(("revoked", _rehash_snapshot(revoked)))

        collapsed_publish = _derived_snapshot(
            base, suffix="COLLAPSED", derivation_kind="REPOST"
        )
        collapsed_publish["publication_evidence_eligible"] = True
        attacks.append(("collapsed", _rehash_snapshot(collapsed_publish)))

        for label, row in attacks:
            with self.subTest(label=label), self.assertRaises(P0ActualContractError):
                actual_contract._validate_source_snapshot(row, EXAMPLE_ORIGIN)

    def test_generic_source_cannot_emit_a_typed_claim(self) -> None:
        source = self._source(profile="GENERIC_FALLBACK")
        claim = next(
            row for row in self.claim_rows if row["registry_record_id"] == source["registry_record_id"]
        )
        claim["track"] = "B"
        claim["claim_kind"] = "COMMUNITY_SENSE"
        claim["claim_direction"] = "SURFACE_TO_SENSE"
        claim["target_sense_id"] = "sense-forged"
        claim["definition"] = claim["surface_text"]
        claim["parse_disposition"] = "PARSED"
        claim["repair_mode"] = "NONE"
        claim = _rehash_claim(claim, source)
        with self.assertRaisesRegex(P0ActualContractError, "generic source"):
            self._validate_example_bundle(
                snapshots=self.source_rows, claims=[claim], contexts=[], events=[]
            )

    def test_b_candidate_integrity_and_cutoff_fail_closed(self) -> None:
        context = deepcopy(self._context(truth="SENSE_ID"))
        fingerprint = deepcopy(context)
        fingerprint["candidate_set_fingerprint"] = "0" * 64
        fingerprint = with_row_hash(fingerprint)
        with self.assertRaisesRegex(P0ActualContractError, "candidate_set_fingerprint"):
            actual_contract._validate_b_context(fingerprint, EXAMPLE_ORIGIN)

        bad_surface_span = deepcopy(context)
        bad_surface_span["surface_start"] += 1
        bad_surface_span["surface_end"] += 1
        bad_surface_span = with_row_hash(bad_surface_span)
        with self.assertRaisesRegex(P0ActualContractError, "surface span"):
            actual_contract._validate_b_context(bad_surface_span, EXAMPLE_ORIGIN)

        cutoff = deepcopy(context)
        cutoff["inference_evidence_cutoff"] = "2099-01-01T00:00:00+00:00"
        cutoff = _rehash_b_context(cutoff)
        with self.assertRaisesRegex(P0ActualContractError, "inference evidence cutoff"):
            actual_contract._validate_b_context(cutoff, EXAMPLE_ORIGIN)

        incomplete = deepcopy(context)
        incomplete["candidate_registry_status"] = "INCOMPLETE"
        incomplete = _rehash_b_context(incomplete)
        with self.assertRaisesRegex(P0ActualContractError, "requires ABSTAIN"):
            actual_contract._validate_b_context(incomplete, EXAMPLE_ORIGIN)

    def test_b_new_sense_requires_novelty_receipt(self) -> None:
        context = deepcopy(self._context(truth="NEW_SENSE"))
        context["novelty_review_receipt_sha256"] = None
        context = _rehash_b_context(context)
        with self.assertRaisesRegex(P0ActualContractError, "novelty review"):
            actual_contract._validate_b_context(context, EXAMPLE_ORIGIN)

    def test_b_temporal_and_sensitive_publication_fail_closed(self) -> None:
        context = deepcopy(self._context(publication="PUBLISH"))
        temporal = deepcopy(context)
        temporal["valid_from"] = None
        temporal["valid_to"] = "2026-01-15T00:00:00+00:00"
        temporal = _rehash_b_context(temporal)
        with self.assertRaisesRegex(P0ActualContractError, "CURRENT sense"):
            actual_contract._validate_b_context(temporal, EXAMPLE_ORIGIN)

        sensitive = deepcopy(context)
        sensitive["sensitivity_class"] = "SENSITIVE"
        sensitive["sensitive_review_status"] = "APPROVED"
        sensitive = _rehash_b_context(sensitive)
        with self.assertRaisesRegex(P0ActualContractError, "PUBLISH B sense"):
            actual_contract._validate_b_context(sensitive, EXAMPLE_ORIGIN)

        hold = deepcopy(self._context(publication="HOLD"))
        hold["public_sense_id"] = "sense-leak"
        hold["public_definition"] = "leaked definition"
        hold = _rehash_b_context(hold)
        with self.assertRaisesRegex(P0ActualContractError, "must not leak"):
            actual_contract._validate_b_context(hold, EXAMPLE_ORIGIN)

    def test_b_bundle_blocks_future_evidence_and_ineligible_publication_source(self) -> None:
        publish = self._context(publication="PUBLISH")
        claim_id = publish["truth_source_claim_ids"][0]
        claim = next(row for row in self.claim_rows if row["claim_id"] == claim_id)
        source = next(
            row
            for row in self.source_rows
            if row["registry_record_id"] == claim["registry_record_id"]
        )

        source["collected_at"] = "2099-01-01T00:00:00+00:00"
        source = _rehash_snapshot(source)
        self.source_rows = [
            source if row["registry_record_id"] == source["registry_record_id"] else row
            for row in self.source_rows
        ]
        self._sync_claim_bindings()
        with self.assertRaisesRegex(P0ActualContractError, "collected after cutoff"):
            self._validate_example_bundle()

        self.setUp()
        publish = self._context(publication="PUBLISH")
        supporting = set(publish["truth_source_claim_ids"])
        registry_ids = {
            row["registry_record_id"]
            for row in self.claim_rows
            if row["claim_id"] in supporting
        }
        self.source_rows = [
            _rehash_snapshot({**row, "publication_evidence_eligible": False})
            if row["registry_record_id"] in registry_ids
            else row
            for row in self.source_rows
        ]
        self._sync_claim_bindings()
        with self.assertRaisesRegex(P0ActualContractError, "eligible source rights"):
            self._validate_example_bundle()

    def test_annotation_event_hash_reviewer_and_guideline_are_bound(self) -> None:
        event = deepcopy(self.event_rows[0])
        bad_hash = deepcopy(event)
        bad_hash["event_sha256"] = "0" * 64
        bad_hash = with_row_hash(bad_hash)
        with self.assertRaisesRegex(P0ActualContractError, "event_sha256"):
            actual_contract._validate_annotation_event(bad_hash, EXAMPLE_ORIGIN)

        reviewer = deepcopy(event)
        reviewer["reviewer_role"] = "MODEL_JUDGE"
        reviewer = _rehash_event(reviewer)
        with self.assertRaisesRegex(P0ActualContractError, "reviewer contract"):
            actual_contract._validate_annotation_event(reviewer, EXAMPLE_ORIGIN)

        guideline = deepcopy(event)
        guideline["guideline_sha256"] = "1" * 64
        guideline = with_row_hash(guideline)
        with self.assertRaisesRegex(P0ActualContractError, "event_sha256"):
            actual_contract._validate_annotation_event(guideline, EXAMPLE_ORIGIN)

    def test_annotation_chain_and_supersedes_are_principal_bound(self) -> None:
        first = deepcopy(self.event_rows[0])
        second = deepcopy(first)
        second["journal_sequence"] = 2
        second["event_id"] = f"{first['event_id']}-recheck"
        second["previous_event_id"] = first["event_id"]
        second["previous_event_sha256"] = first["event_sha256"]
        second["event_kind"] = "INTRA_RATER_RECHECK"
        second["independent_review"] = False
        second["supersedes_event_ids"] = [first["event_id"]]
        second["occurred_at"] = "2098-01-01T00:00:00+00:00"
        second = _rehash_event(second)
        actual_contract._validate_annotation_event(second, EXAMPLE_ORIGIN)
        actual_contract._validate_event_chains([first, second])

        forged_reviewer = deepcopy(second)
        forged_reviewer["reviewer_principal_sha256"] = "2" * 64
        forged_reviewer = _rehash_event(forged_reviewer)
        with self.assertRaisesRegex(P0ActualContractError, "supersedes binding"):
            actual_contract._validate_event_chains([first, forged_reviewer])

        forged_previous = deepcopy(second)
        forged_previous["previous_event_sha256"] = "3" * 64
        forged_previous = _rehash_event(forged_previous)
        with self.assertRaisesRegex(P0ActualContractError, "previous-event chain"):
            actual_contract._validate_event_chains([first, forged_previous])

    def test_b_truth_and_public_definition_require_matching_claim_semantics(self) -> None:
        new_context = self._context(truth="NEW_SENSE")
        claim_id = new_context["truth_source_claim_ids"][0]
        source_by_id = {row["registry_record_id"]: row for row in self.source_rows}
        claims = deepcopy(self.claim_rows)
        for index, claim in enumerate(claims):
            if claim["claim_id"] != claim_id:
                continue
            claim["claim_kind"] = "NON_TERM_EVIDENCE"
            claim["definition"] = None
            claims[index] = _rehash_claim(
                claim, source_by_id[claim["registry_record_id"]]
            )
        contexts = _rebind_context_claim_sets(self.context_rows, claims)
        with self.assertRaisesRegex(P0ActualContractError, "B truth lacks"):
            self._validate_example_bundle(claims=claims, contexts=contexts)

        forged_definition = deepcopy(self._context(publication="PUBLISH"))
        forged_definition["definition"] = "근거와 무관한 위조 정의"
        forged_definition["public_definition"] = "근거와 무관한 위조 정의"
        forged_definition = _rehash_b_context(forged_definition)
        contexts = [
            forged_definition if row["context_id"] == forged_definition["context_id"] else row
            for row in self.context_rows
        ]
        with self.assertRaisesRegex(P0ActualContractError, "B truth lacks"):
            self._validate_example_bundle(contexts=contexts)

    def test_typed_definition_must_be_captured_in_the_exact_claim_span(self) -> None:
        context = self._context(publication="PUBLISH")
        claim_id = context["truth_source_claim_ids"][0]
        source_by_id = {row["registry_record_id"]: row for row in self.source_rows}
        claims = deepcopy(self.claim_rows)
        for index, claim in enumerate(claims):
            if claim["claim_id"] != claim_id:
                continue
            claim["definition"] = "근거 payload에 존재하지 않는 위조 정의"
            claims[index] = _rehash_claim(
                claim, source_by_id[claim["registry_record_id"]]
            )
        forged_context = deepcopy(context)
        forged_context["definition"] = "근거 payload에 존재하지 않는 위조 정의"
        forged_context["public_definition"] = forged_context["definition"]
        forged_context = _rehash_b_context(forged_context)
        contexts = [
            forged_context if row["context_id"] == forged_context["context_id"] else row
            for row in self.context_rows
        ]
        with self.assertRaisesRegex(P0ActualContractError, "definition must occur"):
            self._validate_example_bundle(claims=claims, contexts=contexts)

    def test_b_context_binds_the_complete_referenced_claim_rows(self) -> None:
        context = self._context(publication="PUBLISH")
        claim_id = context["truth_source_claim_ids"][0]
        source_by_id = {row["registry_record_id"]: row for row in self.source_rows}
        claims = deepcopy(self.claim_rows)
        for index, claim in enumerate(claims):
            if claim["claim_id"] != claim_id:
                continue
            claim["parser_version"] = "example_parser_v1_metadata_rewrite"
            claims[index] = _rehash_claim(
                claim, source_by_id[claim["registry_record_id"]]
            )
        with self.assertRaisesRegex(P0ActualContractError, "truth claim set binding"):
            self._validate_example_bundle(claims=claims)

    def test_inference_cutoff_cannot_follow_context_observation(self) -> None:
        context = deepcopy(self._context(truth="SENSE_ID"))
        context["truth_evidence_cutoff"] = "2100-01-01T00:00:00+00:00"
        context["inference_evidence_cutoff"] = "2099-01-01T00:00:00+00:00"
        context = _rehash_b_context(context)
        with self.assertRaisesRegex(P0ActualContractError, "context observation"):
            actual_contract._validate_b_context(context, EXAMPLE_ORIGIN)

    def test_claim_and_context_sampling_units_cannot_be_duplicated_by_new_ids(self) -> None:
        source_by_id = {row["registry_record_id"]: row for row in self.source_rows}
        duplicate_claim = deepcopy(self.claim_rows[0])
        duplicate_claim["claim_id"] = "EXAMPLE:CLAIM:DUPLICATE_ID"
        duplicate_claim = _rehash_claim(
            duplicate_claim, source_by_id[duplicate_claim["registry_record_id"]]
        )
        with self.assertRaisesRegex(P0ActualContractError, "claim sampling unit"):
            self._validate_example_bundle(claims=[*self.claim_rows, duplicate_claim])

        duplicate_context = deepcopy(self.context_rows[0])
        duplicate_context["context_id"] = "EXAMPLE:B_CONTEXT:DUPLICATE_ID"
        duplicate_context["annotation_event_id"] = "EXAMPLE:ANNOTATION_EVENT:DUPLICATE_ID"
        duplicate_context = _rehash_b_context(duplicate_context)
        duplicate_event = deepcopy(self.event_rows[0])
        duplicate_event["journal_id"] = "EXAMPLE:ANNOTATION_JOURNAL:DUPLICATE_ID"
        duplicate_event["event_id"] = duplicate_context["annotation_event_id"]
        duplicate_event["target_id"] = duplicate_context["context_id"]
        duplicate_event["target_subject_sha256"] = duplicate_context[
            "annotation_subject_sha256"
        ]
        duplicate_event = _rehash_event(duplicate_event)
        with self.assertRaisesRegex(P0ActualContractError, "context sampling unit"):
            self._validate_example_bundle(
                contexts=[*self.context_rows, duplicate_context],
                events=[*self.event_rows, duplicate_event],
            )

    def test_annotation_subject_has_one_journal_and_ignores_projection_changes(self) -> None:
        conflicting_head = deepcopy(self.event_rows[0])
        conflicting_head["journal_id"] = "EXAMPLE:ANNOTATION_JOURNAL:CONFLICT"
        conflicting_head["event_id"] = "EXAMPLE:ANNOTATION_EVENT:CONFLICT"
        conflicting_head = _rehash_event(conflicting_head)
        with self.assertRaisesRegex(P0ActualContractError, "one authoritative journal"):
            self._validate_example_bundle(events=[*self.event_rows, conflicting_head])

        held = deepcopy(self._context(publication="PUBLISH"))
        original_subject = held["annotation_subject_sha256"]
        held["publication_action"] = "HOLD"
        held["public_sense_id"] = None
        held["public_definition"] = None
        held["publication_reason_codes"] = [
            "publication_existing_wal_no_write",
            "publication_rights_hold",
        ]
        held = _rehash_b_context(held)
        self.assertEqual(held["annotation_subject_sha256"], original_subject)
        contexts = [
            held if row["context_id"] == held["context_id"] else row
            for row in self.context_rows
        ]
        receipt = self._validate_example_bundle(contexts=contexts)
        self.assertEqual(receipt["gate_status"], "NO_GO_ACTUAL_P0_NOT_STARTED")

    def test_annotation_event_binds_decision_payload_and_rejects_orphans(self) -> None:
        forged_decision = deepcopy(self.event_rows[0])
        forged_decision["decision_payload_sha256"] = "0" * 64
        forged_decision = _rehash_event(forged_decision)
        events = [forged_decision, *self.event_rows[1:]]
        with self.assertRaisesRegex(P0ActualContractError, "latest annotation event binding"):
            self._validate_example_bundle(events=events)

        changed_annotation = deepcopy(self._context(publication="PUBLISH"))
        changed_annotation["term_type"] = "MEME"
        changed_annotation["discourse_function"] = "OTHER"
        changed_annotation["valid_from"] = "2025-01-01T00:00:00Z"
        changed_annotation = _rehash_b_context(changed_annotation)
        contexts = [
            changed_annotation
            if row["context_id"] == changed_annotation["context_id"]
            else row
            for row in self.context_rows
        ]
        with self.assertRaisesRegex(P0ActualContractError, "latest annotation event binding"):
            self._validate_example_bundle(contexts=contexts)

        orphan = deepcopy(self.event_rows[0])
        orphan["journal_id"] = "EXAMPLE:ANNOTATION_JOURNAL:ORPHAN"
        orphan["event_id"] = "EXAMPLE:ANNOTATION_EVENT:ORPHAN"
        orphan["target_id"] = "EXAMPLE:B_CONTEXT:DOES_NOT_EXIST"
        orphan = _rehash_event(orphan)
        with self.assertRaisesRegex(P0ActualContractError, "orphan event"):
            self._validate_example_bundle(events=[*self.event_rows, orphan])

    def test_manifest_path_hash_and_duplicate_keys_fail_closed(self) -> None:
        def copied_fixture() -> tuple[tempfile.TemporaryDirectory[str], Path]:
            owner = tempfile.TemporaryDirectory()
            destination = Path(owner.name) / "fixture"
            shutil.copytree(FIXTURE_DIR, destination)
            return owner, destination

        owner, copied = copied_fixture()
        try:
            manifest_path = copied / MANIFEST_PATH.name
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source_claims"]["path"] = "../p0_source_claim_example_v1.jsonl"
            manifest_path.write_text(
                json.dumps(_manifest_hash(manifest), ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(P0ActualContractError, "fixed contract basename"):
                validate_example_directory(copied)
        finally:
            owner.cleanup()

        owner, copied = copied_fixture()
        try:
            manifest_path = copied / MANIFEST_PATH.name
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source_claims"]["sha256"] = "0" * 64
            manifest_path.write_text(
                json.dumps(_manifest_hash(manifest), ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(P0ActualContractError, "file binding"):
                validate_example_directory(copied)
        finally:
            owner.cleanup()

        owner, copied = copied_fixture()
        try:
            manifest_path = copied / MANIFEST_PATH.name
            text = manifest_path.read_text(encoding="utf-8")
            text = text.replace(
                '"schema_version":',
                '"schema_version":"duplicate", "schema_version":',
                1,
            )
            manifest_path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(P0ActualContractError, "duplicate JSON key"):
                validate_example_directory(copied)
        finally:
            owner.cleanup()

    def test_jsonl_duplicate_key_fails_closed_even_when_manifest_is_rebound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            copied = Path(tmp_name) / "fixture"
            shutil.copytree(FIXTURE_DIR, copied)
            snapshots_path = copied / SNAPSHOT_PATH.name
            lines = snapshots_path.read_text(encoding="utf-8").splitlines()
            lines[0] = lines[0].replace(
                '"schema_version":',
                '"schema_version":"duplicate", "schema_version":',
                1,
            )
            snapshots_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            manifest_path = copied / MANIFEST_PATH.name
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source_snapshots"] = actual_contract._file_ref(
                snapshots_path, len(lines)
            )
            manifest_path.write_text(
                json.dumps(_manifest_hash(manifest), ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(P0ActualContractError, "duplicate JSON key"):
                validate_example_directory(copied)

    def test_module_ast_has_no_runtime_writer_or_external_retriever_import(self) -> None:
        module_path = SRC_ROOT / "llm_batch" / "grounding" / "p0_actual_registry_contract.py"
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
        forbidden = (
            "llm_batch.ledger",
            "llm_batch.runtime",
            "llm_batch.slang",
            "llm_batch.grounding.p0_grounding_contract",
            "pyserini",
            "requests",
            "httpx",
            "subprocess",
        )
        self.assertFalse(
            sorted(name for name in imports if name.startswith(forbidden)),
            f"forbidden imports: {sorted(imports)}",
        )


if __name__ == "__main__":
    unittest.main()
