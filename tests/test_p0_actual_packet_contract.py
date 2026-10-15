"""Key-less actual-P0 terminal packet의 file-bound 회귀 테스트."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from llm_batch.grounding import p0_actual_a_context_contract as a_contract
from llm_batch.grounding import p0_actual_authority_contract as authority_contract
from llm_batch.grounding import p0_actual_packet_contract as packet_contract
from llm_batch.grounding import p0_actual_route_contract as route_contract
from tests import test_p0_actual_a_context_contract as a_fixtures
from tests import test_p0_actual_route_contract as route_fixtures


def _build_route_rows() -> tuple[
    list[dict[str, object]],
    dict[str, object],
    dict[str, object],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    templates = route_fixtures._jsonl(route_fixtures.SNAPSHOT_PATH)
    claim_templates = route_fixtures._jsonl(route_fixtures.CLAIM_PATH)
    sources = [
        route_fixtures._snapshot(templates[0], profile, profile_index, sequence)
        for sequence, (profile, profile_index) in enumerate(
            (
                (profile, profile_index)
                for profile in route_contract.SOURCE_PROFILES
                for profile_index in range(1, 11)
            ),
            start=1,
        )
    ]
    plan = route_fixtures._plan(sources)
    structured = [
        row for row in sources if row["source_profile"] != "GENERIC_FALLBACK"
    ]
    claims = [
        route_fixtures._claim(
            claim_templates[0], source, f"EXAMPLE:PACKET:CLAIM:{index:02d}"
        )
        for index, source in enumerate(structured, start=1)
    ]
    # 1:N claim 회계가 input count와 claim row count를 혼동하지 않는지 보존한다.
    claims.append(
        route_fixtures._claim(
            claim_templates[1], structured[0], "EXAMPLE:PACKET:CLAIM:01:B"
        )
    )
    generic = [
        row for row in sources if row["source_profile"] == "GENERIC_FALLBACK"
    ]
    claims.extend(
        route_fixtures._claim(
            claim_templates[4],
            source,
            f"EXAMPLE:PACKET:CLAIM:GENERIC:{index:02d}",
        )
        for index, source in enumerate(generic, start=1)
    )
    seal = route_fixtures._seal(plan, sources, claims)
    terminals = [
        route_fixtures._terminal(
            source,
            plan,
            disposition="GENERIC_PENDING",
            index=index,
        )
        for index, source in enumerate(generic, start=1)
    ]
    return sources, plan, seal, claims, terminals


def _build_actual_route_rows() -> tuple[
    list[dict[str, object]],
    dict[str, object],
    dict[str, object],
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, object],
]:
    case_type = route_fixtures.P0ActualRouteContractTests
    case_type.setUpClass()
    case = case_type()
    materials = case._actual_materials()
    parser_receipt = case._actual_parser_receipt(materials)
    return (
        materials["source_snapshots"],
        materials["input_plan"],
        materials["selection_seal"],
        materials["source_claims"],
        materials["terminal_rows"],
        parser_receipt,
    )


def _a_rows(
    claims: list[dict[str, object]],
    seal: dict[str, object],
    sources: list[dict[str, object]],
    candidate_registry: dict[str, object],
    count: int = 20,
    *,
    origin: str = packet_contract.EXAMPLE_ORIGIN,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    contexts: list[dict[str, object]] = []
    events: list[dict[str, object]] = []
    selected_ids = {row["claim_id"] for row in seal["selected_claim_units"]}
    track_a_claims = [
        row for row in claims if row["track"] == "A" and row["claim_id"] in selected_ids
    ][:count]
    source_by_id = {row["registry_record_id"]: row for row in sources}
    for index, claim in enumerate(track_a_claims, start=1):
        _, base_contexts, base_events = a_fixtures._bundle(origin)
        context = deepcopy(base_contexts[0])
        event = deepcopy(base_events[0])
        context_id = f"EXAMPLE:PACKET:A:CONTEXT:{index:02d}"
        event_id = f"EXAMPLE:PACKET:A:EVENT:{index:02d}"
        source = source_by_id[claim["registry_record_id"]]
        sequence = int(str(source["locator"]).split(":")[-1])
        content = route_fixtures._payload_text(
            str(source["source_profile"]), sequence
        )
        context.update(
            {
                "context_id": context_id,
                "sampling_unit_id": f"EXAMPLE:PACKET:A:SAMPLE:{index:02d}",
                "post_id": f"EXAMPLE:PACKET:POST:{index:02d}",
                "content_text": content,
                "content_fingerprint": a_contract.canonical_sha256(content),
                "context_observed_at": "2026-09-01T00:00:00Z",
                "surface_text": claim["span_text"],
                "surface_start": claim["span_start"],
                "surface_end": claim["span_end"],
                "surface_sha256": a_contract.canonical_sha256(claim["span_text"]),
                "normalized_surface": claim["normalized_surface"],
                "community_scope": source["community_scope"],
                "platform_scope": source["platform"],
                "candidate_work_ids": [claim["target_work_id"]],
                "candidate_set_fingerprint": a_contract.canonical_sha256(
                    [claim["target_work_id"]]
                ),
                "candidate_registry_snapshot_sha256": candidate_registry[
                    "artifact_sha256"
                ],
                "source_claim_ids": [claim["claim_id"]],
                "source_claim_set_sha256": a_contract.source_claim_set_sha256(
                    [claim]
                ),
                "truth_work_id": claim["target_work_id"],
                "evidence_cutoff": "2026-08-31T00:00:00Z",
                "latest_annotation_event_id": event_id,
            }
        )
        context["sampling_unit_sha256"] = a_contract.sampling_unit_sha256(context)
        context["evidence_receipt_sha256"] = a_contract.evidence_receipt_sha256(
            context
        )
        context["annotation_subject_sha256"] = a_contract.annotation_subject_sha256(
            context
        )
        event.update(
            {
                "journal_id": f"EXAMPLE:PACKET:A:JOURNAL:{index:02d}",
                "event_id": event_id,
                "target_id": context_id,
                "target_subject_sha256": context["annotation_subject_sha256"],
                "evidence_claim_ids": context["source_claim_ids"],
                "evidence_cutoff": context["evidence_cutoff"],
                "decision_work_id": context["truth_work_id"],
                "decision_payload_sha256": a_contract.decision_payload_sha256(
                    context
                ),
                "occurred_at": "2026-09-03T00:00:00Z",
            }
        )
        event["event_sha256"] = a_contract.annotation_event_sha256(event)
        event = a_contract.with_row_hash(event)
        context["latest_annotation_event_sha256"] = event["event_sha256"]
        context = a_contract.with_row_hash(context)
        contexts.append(context)
        events.append(event)
    return contexts, events


def _candidate_registry(
    origin: str = packet_contract.EXAMPLE_ORIGIN,
) -> dict[str, object]:
    return route_contract.with_artifact_hash(
        {
            "schema_version": packet_contract.CANDIDATE_REGISTRY_SCHEMA,
            "record_origin": origin,
            "registry_id": "EXAMPLE:PACKET:CANDIDATES:01",
            "created_at": "2026-08-30T00:00:00Z",
            "enumeration_status": "COMPLETE",
            "work_ids": ["EXAMPLE:WORK:STARLIGHT_RECORD"],
            "action_applied": False,
            "operational_effect": packet_contract.OPERATIONAL_EFFECT,
        }
    )


def _controlled_payloads(
    sources: list[dict[str, object]],
    *,
    origin: str = packet_contract.EXAMPLE_ORIGIN,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for source in sources:
        sequence = int(str(source["locator"]).split(":")[-1])
        content = route_fixtures._payload_text(
            str(source["source_profile"]), sequence
        )
        raw = content.encode("utf-8")
        rows.append(
            a_contract.with_row_hash(
                {
                    "schema_version": packet_contract.CONTROLLED_PAYLOAD_ROW_SCHEMA,
                    "record_origin": origin,
                    "registry_record_id": source["registry_record_id"],
                    "payload_ref": source["payload_ref"],
                    "content_text": content,
                    "content_bytes": len(raw),
                    "content_sha256": hashlib.sha256(raw).hexdigest(),
                    "normalized_text_sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
        )
    return rows


def _example_parser_receipt() -> dict[str, object]:
    return authority_contract.with_artifact_hash(
        {
            "schema_version": authority_contract.PARSER_RECEIPT_SCHEMA,
            "record_origin": authority_contract.EXAMPLE_ORIGIN,
            "parser_run_id": "EXAMPLE:PACKET:PARSER:NOT_RUN",
            "launch_sha256": "a" * 64,
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
            "operational_effect": packet_contract.OPERATIONAL_EFFECT,
        }
    )


def _a_subject_seal(
    contexts: list[dict[str, object]],
    seal: dict[str, object],
    *,
    origin: str = packet_contract.EXAMPLE_ORIGIN,
) -> dict[str, object]:
    selected = [
        packet_contract.a_subject_projection(context)
        for context in sorted(contexts, key=lambda item: item["context_id"])
    ]
    return packet_contract.with_a_subject_seal_hash(
        {
            "schema_version": packet_contract.A_SUBJECT_SELECTION_SEAL_SCHEMA,
            "record_origin": origin,
            "seal_id": "EXAMPLE:PACKET:A:SUBJECT-SEAL:01",
            "claim_selection_seal_sha256": seal["artifact_sha256"],
            "sampling_frame_sha256": contexts[0]["sampling_frame_sha256"],
            "selected_subject_count": len(selected),
            "selected_subjects": selected,
            "selected_subjects_sha256": packet_contract.canonical_sha256(selected),
            "labels_observed": False,
            "sealed_at": "2026-09-02T01:00:00Z",
            "action_applied": False,
            "operational_effect": packet_contract.OPERATIONAL_EFFECT,
        }
    )


def _content_values(
    *,
    a_count: int = 20,
    origin: str = packet_contract.EXAMPLE_ORIGIN,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    if origin == packet_contract.ACTUAL_ORIGIN:
        sources, plan, seal, claims, terminals, parser_receipt = (
            _build_actual_route_rows()
        )
    else:
        sources, plan, seal, claims, terminals = _build_route_rows()
        parser_receipt = _example_parser_receipt()
    candidate_registry = _candidate_registry(origin)
    contexts, events = _a_rows(
        claims,
        seal,
        sources,
        candidate_registry,
        a_count,
        origin=origin,
    )
    route_receipt = route_contract.validate_route_bundle(
        source_snapshots=sources,
        input_plan=plan,
        selection_seal=seal,
        source_claims=claims,
        terminal_rows=terminals,
        parser_receipt=(
            parser_receipt if origin == packet_contract.ACTUAL_ORIGIN else None
        ),
        expected_origin=origin,
    )
    a_claim_ids = {
        claim_id for context in contexts for claim_id in context["source_claim_ids"]
    }
    bound_a_claims = [row for row in claims if row["claim_id"] in a_claim_ids]
    validate_a = (
        a_contract.validate_actual_a_context_bundle
        if origin == packet_contract.ACTUAL_ORIGIN
        else a_contract.validate_example_a_context_bundle
    )
    a_receipt = validate_a(bound_a_claims, contexts, events)
    artifacts: dict[str, object] = {
        "source_snapshots": sources,
        "controlled_payloads": _controlled_payloads(sources, origin=origin),
        "source_input_plan": plan,
        "label_blind_selection_seal": seal,
        "source_claims": claims,
        "terminal_queue": terminals,
        "parser_receipt": parser_receipt,
        "candidate_registry": candidate_registry,
        "a_contexts": contexts,
        "a_subject_selection_seal": _a_subject_seal(
            contexts, seal, origin=origin
        ),
        "a_annotation_events": events,
        "route_receipt": route_receipt,
        "a_context_receipt": a_receipt,
    }
    return artifacts, route_receipt, a_receipt


def _child_bytes(artifacts: dict[str, object]) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for role, path, media_type in packet_contract.CHILD_FILES:
        value = artifacts[role]
        result[path] = (
            packet_contract.json_file_bytes(value)
            if media_type == "application/json"
            else packet_contract.jsonl_bytes(value)  # type: ignore[arg-type]
        )
    return result


def _manifest(
    artifacts: dict[str, object],
    route_receipt: dict[str, object],
    a_receipt: dict[str, object],
    child_bytes: dict[str, bytes],
    *,
    origin: str = packet_contract.EXAMPLE_ORIGIN,
) -> dict[str, object]:
    sources = artifacts["source_snapshots"]
    claims = artifacts["source_claims"]
    terminals = artifacts["terminal_queue"]
    contexts = artifacts["a_contexts"]
    events = artifacts["a_annotation_events"]
    profile_counts = {
        profile: sum(row["source_profile"] == profile for row in sources)
        for profile in route_contract.SOURCE_PROFILES
    }
    status_counts = {
        status: sum(row["annotation_status"] == status for row in contexts)
        for status in a_contract.ANNOTATION_STATUSES
    }
    selected_subjects = [
        packet_contract.a_subject_projection(context)
        for context in sorted(contexts, key=lambda item: item["context_id"])
    ]
    refs = []
    for role, path, media_type in packet_contract.CHILD_FILES:
        value = artifacts[role]
        rows = 1 if media_type == "application/json" else len(value)
        refs.append(
            packet_contract.file_ref(role, path, media_type, child_bytes[path], rows)
        )
    return packet_contract.with_manifest_hash(
        {
            "schema_version": packet_contract.PACKET_MANIFEST_SCHEMA,
            "record_origin": origin,
            "packet_id": "EXAMPLE:KEYLESS:PACKET:01",
            "created_at": "2026-09-04T00:00:00Z",
            "files": refs,
            "source_profile_counts": profile_counts,
            "route_counts": {
                field: route_receipt[field]
                for field in (
                    "input_count",
                    "typed_input_count",
                    "claim_row_count",
                    "generic_count",
                    "error_count",
                )
            },
            "a_annotation_status_counts": status_counts,
            "observed_counts": {
                "source_snapshot_count": len(sources),
                "source_claim_row_count": len(claims),
                "selected_source_claim_count": route_receipt[
                    "selected_claim_count"
                ],
                "terminal_queue_count": len(terminals),
                "a_context_review_count": len(contexts),
                "a_annotation_event_count": len(events),
            },
            "credited_counts": {
                "actual_source_claim_count": 0,
                "actual_a_context_review_count": 0,
            },
            "route_receipt_sha256": packet_contract.canonical_sha256(route_receipt),
            "parser_receipt_sha256": artifacts["parser_receipt"][
                "artifact_sha256"
            ],
            "a_context_receipt_sha256": packet_contract.canonical_sha256(a_receipt),
            "a_subject_selection_seal_sha256": artifacts[
                "a_subject_selection_seal"
            ]["artifact_sha256"],
            "a_selected_subject_count": len(selected_subjects),
            "a_selected_subjects_sha256": packet_contract.canonical_sha256(
                selected_subjects
            ),
            "filesystem_handle_trust_verified": False,
            "authority_journal_watch_bundle_verified": False,
            "external_owner_authority_verified": False,
            "os_write_deny_verified": False,
            "runtime_noninterference_verified": False,
            "actual_authority_granted": False,
            "production_approval": False,
            "full_scan_approval": False,
            "p0_phase_exit": False,
            "action_applied": False,
            "operational_effect": packet_contract.OPERATIONAL_EFFECT,
            "gate_status": "NO_GO_ACTUAL_P0_AUTHORITY_NOT_VERIFIED",
            "blockers": list(packet_contract.BLOCKERS),
        }
    )


def _packet(
    *,
    a_count: int = 20,
    origin: str = packet_contract.EXAMPLE_ORIGIN,
) -> tuple[bytes, dict[str, bytes]]:
    artifacts, route_receipt, a_receipt = _content_values(
        a_count=a_count, origin=origin
    )
    children = _child_bytes(artifacts)
    manifest = _manifest(
        artifacts, route_receipt, a_receipt, children, origin=origin
    )
    return packet_contract.json_file_bytes(manifest), children


def _pinned(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class P0ActualPacketContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest_bytes, cls.children = _packet()

    def _validate(
        self,
        manifest_bytes: bytes | None = None,
        children: dict[str, bytes] | None = None,
        pinned: str | None = None,
    ) -> dict[str, object]:
        manifest_raw = self.manifest_bytes if manifest_bytes is None else manifest_bytes
        return packet_contract.validate_packet_bytes(
            manifest_raw,
            self.children if children is None else children,
            expected_manifest_sha256=_pinned(manifest_raw) if pinned is None else pinned,
            expected_origin=packet_contract.EXAMPLE_ORIGIN,
        )

    def test_positive_40_plus_20_packet_is_structural_no_go_only(self) -> None:
        receipt = self._validate()
        self.assertEqual(40, receipt["observed_counts"]["source_snapshot_count"])
        self.assertEqual(20, receipt["observed_counts"]["a_context_review_count"])
        self.assertEqual(
            {profile: 10 for profile in route_contract.SOURCE_PROFILES},
            receipt["source_profile_counts"],
        )
        self.assertEqual(30, receipt["route_counts"]["typed_input_count"])
        self.assertEqual(31, receipt["route_counts"]["claim_row_count"])
        self.assertEqual(
            {
                "actual_source_claim_count": 0,
                "actual_a_context_review_count": 0,
            },
            receipt["credited_counts"],
        )
        self.assertFalse(receipt["filesystem_handle_trust_verified"])
        self.assertTrue(receipt["byte_inventory_binding_verified"])
        self.assertFalse(receipt["portable_directory_binding_verified"])
        self.assertEqual(
            receipt["receipt_sha256"],
            packet_contract.canonical_sha256(
                {
                    key: value
                    for key, value in receipt.items()
                    if key != "receipt_sha256"
                }
            ),
        )
        self.assertEqual(
            receipt["route_receipt_sha256"],
            packet_contract.canonical_sha256(
                json.loads(self.children["route_receipt.json"])
            ),
        )
        self.assertEqual(
            receipt["route_parser_manifest_sha256"],
            json.loads(self.children["route_receipt.json"])[
                "parser_manifest_sha256"
            ],
        )
        self.assertFalse(receipt["actual_authority_granted"])
        self.assertEqual(
            "NO_GO_ACTUAL_P0_AUTHORITY_NOT_VERIFIED", receipt["gate_status"]
        )

    def test_actual_origin_40_plus_20_executes_but_keeps_credit_zero(self) -> None:
        manifest, children = _packet(origin=packet_contract.ACTUAL_ORIGIN)
        receipt = packet_contract.validate_packet_bytes(
            manifest,
            children,
            expected_manifest_sha256=_pinned(manifest),
            expected_origin=packet_contract.ACTUAL_ORIGIN,
        )
        self.assertTrue(receipt["route_accounting_packet_complete"])
        self.assertEqual(40, receipt["observed_counts"]["selected_source_claim_count"])
        self.assertEqual(20, receipt["observed_counts"]["a_context_review_count"])
        self.assertEqual(
            {
                "actual_source_claim_count": 0,
                "actual_a_context_review_count": 0,
            },
            receipt["credited_counts"],
        )
        self.assertFalse(receipt["authority_journal_watch_bundle_verified"])
        self.assertFalse(receipt["actual_authority_granted"])
        self.assertFalse(receipt["p0_phase_exit"])

    def test_directory_validator_requires_exact_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            (root / packet_contract.PACKET_MANIFEST_FILENAME).write_bytes(
                self.manifest_bytes
            )
            for name, raw in self.children.items():
                (root / name).write_bytes(raw)
            receipt = packet_contract.validate_packet_directory(
                root,
                expected_manifest_sha256=_pinned(self.manifest_bytes),
                expected_origin=packet_contract.EXAMPLE_ORIGIN,
            )
            self.assertTrue(receipt["portable_directory_binding_verified"])
            self.assertEqual(
                receipt["receipt_sha256"],
                packet_contract.canonical_sha256(
                    {
                        key: value
                        for key, value in receipt.items()
                        if key != "receipt_sha256"
                    }
                ),
            )
            (root / "unlisted.txt").write_text("forbidden", encoding="utf-8")
            with self.assertRaisesRegex(
                packet_contract.P0ActualPacketError, "directory inventory"
            ):
                packet_contract.validate_packet_directory(
                    root,
                    expected_manifest_sha256=_pinned(self.manifest_bytes),
                    expected_origin=packet_contract.EXAMPLE_ORIGIN,
                )

    def test_caller_pinned_manifest_sha_is_mandatory(self) -> None:
        with self.assertRaisesRegex(
            packet_contract.P0ActualPacketError, "caller-pinned"
        ):
            self._validate(pinned="0" * 64)

    def test_manifest_never_accepts_actual_credit_or_authority(self) -> None:
        for field, value in (
            ("credited_counts", {"actual_source_claim_count": 40, "actual_a_context_review_count": 20}),
            ("actual_authority_granted", True),
            ("filesystem_handle_trust_verified", True),
            ("gate_status", "GO"),
        ):
            manifest = json.loads(self.manifest_bytes)
            manifest[field] = value
            forged = packet_contract.json_file_bytes(
                packet_contract.with_manifest_hash(manifest)
            )
            with self.subTest(field=field), self.assertRaises(
                packet_contract.P0ActualPacketError
            ):
                self._validate(manifest_bytes=forged)

    def test_child_reference_and_canonical_bytes_are_both_required(self) -> None:
        artifacts, route_receipt, a_receipt = _content_values()
        children = _child_bytes(artifacts)
        plan = artifacts["source_input_plan"]
        children["source_input_plan.json"] = (
            json.dumps(plan, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
        )
        manifest = _manifest(artifacts, route_receipt, a_receipt, children)
        raw = packet_contract.json_file_bytes(manifest)
        with self.assertRaisesRegex(
            packet_contract.P0ActualPacketError, "not canonical JSON"
        ):
            self._validate(raw, children)

    def test_stored_route_receipt_must_equal_recomputation(self) -> None:
        artifacts, route_receipt, a_receipt = _content_values()
        stored = deepcopy(route_receipt)
        stored["gate_status"] = "NO_GO_FORGED"
        artifacts["route_receipt"] = stored
        children = _child_bytes(artifacts)
        manifest = _manifest(artifacts, route_receipt, a_receipt, children)
        raw = packet_contract.json_file_bytes(manifest)
        with self.assertRaisesRegex(
            packet_contract.P0ActualPacketError, "stored route receipt"
        ):
            self._validate(raw, children)

    def test_stored_a_receipt_must_equal_recomputation(self) -> None:
        artifacts, route_receipt, a_receipt = _content_values()
        stored = deepcopy(a_receipt)
        stored["actual_a_context_review_count"] = 20
        artifacts["a_context_receipt"] = stored
        children = _child_bytes(artifacts)
        manifest = _manifest(artifacts, route_receipt, a_receipt, children)
        raw = packet_contract.json_file_bytes(manifest)
        with self.assertRaisesRegex(
            packet_contract.P0ActualPacketError, "stored A-context receipt"
        ):
            self._validate(raw, children)

    def test_controlled_payload_exact_span_replay_rejects_forged_claim(self) -> None:
        artifacts, _, _ = _content_values()
        payloads = {
            row["registry_record_id"]: row["content_text"]
            for row in artifacts["controlled_payloads"]
        }
        claims = deepcopy(artifacts["source_claims"])
        claims[0]["span_text"] = "위조"
        with self.assertRaisesRegex(
            packet_contract.P0ActualPacketError, "does not match captured payload"
        ):
            packet_contract.validate_claim_payload_spans(claims, payloads)

    def test_a_subject_seal_must_be_prelabel_and_candidate_registry_is_bound(self) -> None:
        artifacts, route_receipt, a_receipt = _content_values()
        seal = deepcopy(artifacts["a_subject_selection_seal"])
        seal["labels_observed"] = True
        artifacts["a_subject_selection_seal"] = (
            packet_contract.with_a_subject_seal_hash(seal)
        )
        children = _child_bytes(artifacts)
        raw = packet_contract.json_file_bytes(
            _manifest(artifacts, route_receipt, a_receipt, children)
        )
        with self.assertRaisesRegex(
            packet_contract.P0ActualPacketError, "label blind"
        ):
            self._validate(raw, children)

        artifacts, route_receipt, a_receipt = _content_values()
        registry = deepcopy(artifacts["candidate_registry"])
        registry["work_ids"] = ["EXAMPLE:WORK:FORGED"]
        artifacts["candidate_registry"] = route_contract.with_artifact_hash(registry)
        children = _child_bytes(artifacts)
        raw = packet_contract.json_file_bytes(
            _manifest(artifacts, route_receipt, a_receipt, children)
        )
        with self.assertRaisesRegex(
            packet_contract.P0ActualPacketError, "candidate registry binding"
        ):
            self._validate(raw, children)

    def test_a_subject_seal_cannot_predate_context_observation(self) -> None:
        artifacts, _, _ = _content_values()
        contexts = deepcopy(artifacts["a_contexts"])
        for context in contexts:
            context["context_observed_at"] = "2026-09-02T12:00:00Z"
        seal = deepcopy(artifacts["a_subject_selection_seal"])
        seal = packet_contract.with_a_subject_seal_hash(seal)
        with self.assertRaisesRegex(
            packet_contract.P0ActualPacketError,
            "cannot predate any context observation",
        ):
            packet_contract.validate_a_subject_selection_seal(
                seal,
                contexts,
                claim_selection_seal=artifacts["label_blind_selection_seal"],
                expected_origin=packet_contract.EXAMPLE_ORIGIN,
            )

    def test_candidate_registry_cannot_postdate_evidence_cutoff(self) -> None:
        artifacts, route_receipt, a_receipt = _content_values()
        registry = deepcopy(artifacts["candidate_registry"])
        registry["created_at"] = "2026-08-31T12:00:00Z"
        registry = route_contract.with_artifact_hash(registry)
        artifacts["candidate_registry"] = registry
        for context in artifacts["a_contexts"]:
            context["candidate_registry_snapshot_sha256"] = registry[
                "artifact_sha256"
            ]
            context["evidence_receipt_sha256"] = a_contract.evidence_receipt_sha256(
                context
            )
            context["annotation_subject_sha256"] = a_contract.annotation_subject_sha256(
                context
            )
            context["row_sha256"] = a_contract.canonical_sha256(
                {key: value for key, value in context.items() if key != "row_sha256"}
            )
        children = _child_bytes(artifacts)
        raw = packet_contract.json_file_bytes(
            _manifest(artifacts, route_receipt, a_receipt, children)
        )
        with self.assertRaisesRegex(
            packet_contract.P0ActualPacketError,
            "candidate registry postdates A evidence cutoff",
        ):
            self._validate(raw, children)

    def test_parser_receipt_child_is_strictly_validated(self) -> None:
        artifacts, route_receipt, a_receipt = _content_values()
        artifacts["parser_receipt"]["parser_run_id"] = "EXAMPLE:FORGED"
        children = _child_bytes(artifacts)
        raw = packet_contract.json_file_bytes(
            _manifest(artifacts, route_receipt, a_receipt, children)
        )
        with self.assertRaisesRegex(
            packet_contract.P0ActualPacketError, "parser receipt invalid"
        ):
            self._validate(raw, children)

    def test_manifest_reported_counts_are_recomputed(self) -> None:
        for field in ("observed_counts", "a_selected_subjects_sha256"):
            manifest = json.loads(self.manifest_bytes)
            if field == "observed_counts":
                manifest[field]["source_claim_row_count"] += 1
            else:
                manifest[field] = "0" * 64
            raw = packet_contract.json_file_bytes(
                packet_contract.with_manifest_hash(manifest)
            )
            with self.subTest(field=field), self.assertRaisesRegex(
                packet_contract.P0ActualPacketError, "recomputed binding mismatch"
            ):
                self._validate(raw)

    def test_terminal_rejects_incomplete_selection_and_parser_error(self) -> None:
        artifacts, _, a_receipt = _content_values()
        sources = artifacts["source_snapshots"]
        plan = artifacts["source_input_plan"]
        error_source = sources[-1]
        claims = [
            row
            for row in artifacts["source_claims"]
            if row["registry_record_id"] != error_source["registry_record_id"]
        ]
        terminals = list(artifacts["terminal_queue"][:-1])
        terminals.append(
            route_fixtures._terminal(
                error_source,
                plan,
                disposition="PARSER_ERROR",
                index=10,
            )
        )
        seal = route_fixtures._seal(plan, sources, claims)
        route_receipt = route_contract.validate_route_bundle(
            source_snapshots=sources,
            input_plan=plan,
            selection_seal=seal,
            source_claims=claims,
            terminal_rows=terminals,
            expected_origin=route_contract.EXAMPLE_ORIGIN,
        )
        artifacts.update(
            {
                "label_blind_selection_seal": seal,
                "source_claims": claims,
                "terminal_queue": terminals,
                "route_receipt": route_receipt,
            }
        )
        children = _child_bytes(artifacts)
        manifest = _manifest(artifacts, route_receipt, a_receipt, children)
        raw = packet_contract.json_file_bytes(manifest)
        with self.assertRaisesRegex(
            packet_contract.P0ActualPacketError, "complete 40-claim selection"
        ):
            self._validate(raw, children)

    def test_latest_a_event_must_follow_selection_seal(self) -> None:
        artifacts, route_receipt, _ = _content_values()
        events = artifacts["a_annotation_events"]
        contexts = artifacts["a_contexts"]
        events[0]["occurred_at"] = artifacts["label_blind_selection_seal"][
            "sealed_at"
        ]
        a_fixtures._rehash_event(events[0])
        contexts[0]["latest_annotation_event_sha256"] = events[0]["event_sha256"]
        a_fixtures._rehash_context(contexts[0])
        claim_ids = {
            claim_id for context in contexts for claim_id in context["source_claim_ids"]
        }
        a_claims = [
            row for row in artifacts["source_claims"] if row["claim_id"] in claim_ids
        ]
        a_receipt = a_contract.validate_example_a_context_bundle(
            a_claims, contexts, events
        )
        artifacts["a_context_receipt"] = a_receipt
        children = _child_bytes(artifacts)
        manifest = _manifest(artifacts, route_receipt, a_receipt, children)
        raw = packet_contract.json_file_bytes(manifest)
        with self.assertRaisesRegex(
            packet_contract.P0ActualPacketError, "after subject selection seal"
        ):
            self._validate(raw, children)

    def test_terminal_packet_rejects_only_19_a_contexts(self) -> None:
        manifest, children = _packet(a_count=19)
        with self.assertRaisesRegex(
            packet_contract.P0ActualPacketError, "exactly 20"
        ):
            self._validate(manifest, children)

    def test_fixed_child_inventory_rejects_missing_file(self) -> None:
        children = dict(self.children)
        children.pop("a_annotation_events.jsonl")
        with self.assertRaisesRegex(
            packet_contract.P0ActualPacketError, "fixed inventory"
        ):
            self._validate(children=children)

    def test_manifest_extra_field_and_self_hash_fail_closed(self) -> None:
        manifest = json.loads(self.manifest_bytes)
        manifest["production_note"] = "untrusted"
        raw = packet_contract.json_file_bytes(
            packet_contract.with_manifest_hash(manifest)
        )
        with self.assertRaisesRegex(
            packet_contract.P0ActualPacketError, "fields mismatch"
        ):
            self._validate(raw)
        manifest = json.loads(self.manifest_bytes)
        manifest["packet_id"] = "EXAMPLE:FORGED"
        raw = packet_contract.json_file_bytes(manifest)
        with self.assertRaisesRegex(
            packet_contract.P0ActualPacketError, "self hash mismatch"
        ):
            self._validate(raw)


if __name__ == "__main__":
    unittest.main()
