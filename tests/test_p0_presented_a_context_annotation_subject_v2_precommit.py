"""Presented A-context annotation subject V2 precommit 회귀/공격 테스트."""

from __future__ import annotations

from copy import deepcopy
import base64
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from llm_batch.grounding import p0_full_eligible_sampling_frame_v2_contract as source_frame
from llm_batch.grounding import p0_actual_packet_contract as old_packet
from llm_batch.grounding import p0_presented_a_context_annotation_subject_v2_precommit_contract as contract
from llm_batch.grounding import p0_presented_a_context_annotation_subject_v2_precommit_parent_validator as parent
from llm_batch.grounding import p0_presented_a_context_full_frame_v1_contract as a_frame
from llm_batch.grounding import p0_presented_batch_exact_accounting_v1_contract as bridge_contract
from tests import test_p0_presented_batch_exact_accounting_v1 as source_fixture


A_CREATED = "2026-09-02T00:00:05Z"
A_CUTOFF = "2026-09-02T00:00:06Z"
A_FRAME_SEALED = "2026-09-02T00:00:07Z"
A_OWNER = "2026-09-02T00:00:08Z"
A_REVEAL = "2026-09-02T00:00:09Z"
A_SELECTED = "2026-09-02T00:00:10Z"
PRECOMMITTED = "2026-09-02T00:00:11Z"


def _sha(value: object) -> str:
    return contract.canonical_sha256(value)


def _obj(raw: bytes) -> dict[str, object]:
    return json.loads(raw)


def _rows(raw: bytes) -> list[dict[str, object]]:
    return [json.loads(line) for line in raw.splitlines()]


def _file(value: object) -> bytes:
    return contract.canonical_file_bytes(value)


def _jsonl(rows: list[dict[str, object]]) -> bytes:
    return b"".join(_file(row) for row in rows)


def _reseal(value: dict[str, object], field: str) -> bytes:
    return _file(contract.with_self_hash(value, field))


def _bridge_inputs(plan_raw: bytes) -> list[dict[str, object]]:
    result = []
    for selected in _obj(plan_raw)["selected_inputs"]:  # type: ignore[index]
        sequence = selected["input_sequence"]
        profile = selected["source_profile"]
        payload = f"{profile} 제시 문맥 {sequence}: 아생갤 표면은 아직 판정 전이다.".encode("utf-8")
        result.append({
            **{field: selected[field] for field in bridge_contract._SELECTED_IDENTITY_FIELDS},
            "registry_record_id": f"subject-v2-registry-{sequence}",
            "registry_record_commitment_sha256": _sha({"registry": sequence}),
            "content_type": "text/plain; charset=utf-8",
            "capture_version": "subject-v2-fixture-capture-v1",
            "normalization_version": "utf8_identity_v1",
            "payload": payload,
        })
    return result


def _a_scope(source_bundle: dict[str, bytes], bridge: bytes) -> bytes:
    adapters = _obj(source_bundle["scope"])["adapter_profile_map"]
    return a_frame.build_scope_bytes({
        "schema_version": a_frame.SCOPE_SCHEMA, "record_origin": a_frame.EXAMPLE_ORIGIN,
        "scope_id": "fixture-subject-v2-a-frame", "created_at": A_CREATED,
        "frame_cutoff": A_CUTOFF, "adapter_profile_map": adapters,
        "strata": [{"source_profile": profile, "platform_scope": source_fixture.PLATFORM,
                    "utc_day": source_fixture.UTC_DAY, "quota": 5}
                   for profile in a_frame.SOURCE_PROFILES],
        "upstream_source_sampling_plan_raw_sha256": contract.raw_sha256(source_bundle["plan"]),
        "upstream_bridge_inventory_raw_sha256": contract.raw_sha256(bridge),
        "context_enumeration_policy_sha256": _sha("subject-v2-enumeration"),
        "eligibility_policy_sha256": _sha("subject-v2-eligibility"),
        "rights_policy_sha256": _sha("subject-v2-rights"),
        "strata_policy_sha256": _sha("subject-v2-strata"),
        "future_seed_spec_sha256": _sha("subject-v2-future-seed"),
        "expected_per_profile_quota": 5, "expected_total_quota": 20,
        "selection_algorithm": a_frame.SELECTION_ALGORITHM, "labels_observed": False,
        "semantic_truth_fields_used": False, "annotation_started": False,
        "action_applied": False, "operational_effect": a_frame.OPERATIONAL_EFFECT,
    })


def _a_candidate(bridge: dict[str, object], source_candidate: dict[str, object]) -> dict[str, object]:
    payload = base64.b64decode(bridge["payload_base64"]).decode("utf-8")  # type: ignore[arg-type]
    return {
        "upstream_frame_candidate_id": bridge["candidate_id"],
        "registry_record_id": bridge["registry_record_id"], "adapter_id": bridge["adapter_id"],
        "platform_scope": bridge["platform"],
        "community_scope_commitment_sha256": _sha({"presented-community": bridge["registry_record_id"]}),
        "content_fingerprint": _sha(payload), "payload_sha256": bridge["payload_sha256"],
        "surface_start": 0, "surface_end": len(payload), "surface_sha256": _sha(payload),
        "context_observed_at": source_candidate["observed_at"],
        "source_published_at": source_candidate["published_at"],
        "capture_receipt_sha256": _sha({"presented-capture": bridge["bridge_row_sha256"]}),
        "source_claim_set_sha256": _sha({"presented-claim-commitment": bridge["bridge_row_sha256"]}),
        "presented_rights_policy_assessed": True, "presented_collection_allowed": True,
        "presented_takedown_status": "ACTIVE", "presented_source_binding_verified": True,
    }


def _bundle() -> dict[str, bytes]:
    source = source_fixture._frame_bundle()
    bridge = bridge_contract.build_bridge_inventory_bytes(
        scope_raw=source["scope"], census_raw=source["census"],
        frame_manifest_raw=source["frame"], seed_receipt_raw=source["seed"],
        sampling_plan_raw=source["plan"], batch_inputs=_bridge_inputs(source["plan"]),
    )
    a_scope = _a_scope(source, bridge)
    source_census = {row["candidate_id"]: row for row in _rows(source["census"])}
    a_census = a_frame.build_census_bytes(
        a_scope, [_a_candidate(row, source_census[row["candidate_id"]]) for row in _rows(bridge)])
    a_frame_raw = a_frame.build_frame_manifest_bytes(a_scope, a_census, frame_sealed_at=A_FRAME_SEALED)
    scope_value = a_frame.validate_scope_bytes(a_scope)
    frame_value = a_frame.validate_frame_manifest_bytes(a_frame_raw, a_scope, a_census)
    a_seed = a_frame.build_seed_receipt_bytes({
        "schema_version": a_frame.SEED_RECEIPT_SCHEMA, "record_origin": a_frame.EXAMPLE_ORIGIN,
        "seed_receipt_id": "fixture-subject-v2-seed", "scope_sha256": scope_value["artifact_sha256"],
        "frame_manifest_sha256": frame_value["artifact_sha256"],
        "census_raw_sha256": contract.raw_sha256(a_census),
        "future_seed_spec_sha256": scope_value["future_seed_spec_sha256"],
        "revealed_seed_sha256": _sha("subject-v2-revealed"),
        "frame_owner_precommit_sha256": _sha("subject-v2-owner"),
        "frame_owner_precommitted_at": A_OWNER, "revealed_at": A_REVEAL,
        "owner_authority_verified": False, "seed_authority_verified": False,
        "action_applied": False, "operational_effect": a_frame.OPERATIONAL_EFFECT,
    }, a_scope, a_frame_raw, a_census)
    a_plan = a_frame.build_sampling_plan_bytes(
        a_scope, a_census, a_frame_raw, a_seed, selection_sealed_at=A_SELECTED)
    raws = {
        "source_scope": source["scope"], "source_census": source["census"],
        "source_frame": source["frame"], "source_seed": source["seed"], "source_plan": source["plan"],
        "bridge_inventory": bridge, "a_scope": a_scope, "a_census": a_census,
        "a_frame": a_frame_raw, "a_seed": a_seed, "a_plan": a_plan,
    }
    subjects = contract.build_subject_rows_bytes(**raws)
    precommit = contract.build_precommit_bytes(subjects, precommit_id="fixture-subject-v2-precommit",
                                               precommitted_at=PRECOMMITTED, **raws)
    return {**raws, "subjects": subjects, "precommit": precommit}


class SubjectV2PrecommitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = _bundle()

    def _raws(self, bundle: dict[str, bytes] | None = None) -> dict[str, bytes]:
        value = self.bundle if bundle is None else bundle
        return {key: value[key] for key in contract.LINEAGE_KEYS}

    def _parent(self, bundle: dict[str, bytes] | None = None) -> dict[str, object]:
        value = self.bundle if bundle is None else bundle
        return parent.validate_subject_precommit_against_raw_inputs(
            subject_rows_raw=value["subjects"], expected_subject_rows_raw_sha256=contract.raw_sha256(value["subjects"]),
            precommit_raw=value["precommit"], expected_precommit_raw_sha256=contract.raw_sha256(value["precommit"]),
            **self._raws(value))

    def test_positive_13_raw_lineage_selected20_and_parent(self) -> None:
        rows = contract.validate_subject_rows_bytes(self.bundle["subjects"], **self._raws())
        precommit = contract.validate_precommit_bytes(self.bundle["precommit"], self.bundle["subjects"], **self._raws())
        receipt = self._parent()
        self.assertEqual((len(rows), precommit["subject_count"], receipt["total_bound_raw_artifact_count"]), (20, 20, 13))
        self.assertEqual(precommit["v2_annotation_event_count"], 0)
        self.assertTrue(receipt["bridge40_selected40_replayed"])
        self.assertTrue(receipt["subject20_selected20_replayed"])

    def test_parent_matches_producer_timezone_aware_precommit_time(self) -> None:
        precommit = _obj(self.bundle["precommit"])
        precommit["precommitted_at"] = "2026-09-02T09:00:11+09:00"
        attacked = _reseal(precommit, "artifact_sha256")
        contract.validate_precommit_bytes(attacked, self.bundle["subjects"], **self._raws())
        receipt = parent.validate_subject_precommit_against_raw_inputs(
            subject_rows_raw=self.bundle["subjects"], expected_subject_rows_raw_sha256=contract.raw_sha256(self.bundle["subjects"]),
            precommit_raw=attacked, expected_precommit_raw_sha256=contract.raw_sha256(attacked), **self._raws())
        self.assertEqual(receipt["gate_status"], parent.PARENT_GATE_STATUS)

    def test_parent_matches_a_predecessor_512_character_id_domain(self) -> None:
        seed = _obj(self.bundle["a_seed"])
        seed["seed_receipt_id"] = "A" * 300
        seed_raw = _reseal(seed, "artifact_sha256")
        plan_raw = a_frame.build_sampling_plan_bytes(
            self.bundle["a_scope"], self.bundle["a_census"], self.bundle["a_frame"], seed_raw,
            selection_sealed_at=A_SELECTED)
        raws = {**self._raws(), "a_seed": seed_raw, "a_plan": plan_raw}
        subjects = contract.build_subject_rows_bytes(**raws)
        precommit = contract.build_precommit_bytes(
            subjects, precommit_id="fixture-a-id-domain", precommitted_at=PRECOMMITTED, **raws)
        receipt = parent.validate_subject_precommit_against_raw_inputs(
            subject_rows_raw=subjects, expected_subject_rows_raw_sha256=contract.raw_sha256(subjects),
            precommit_raw=precommit, expected_precommit_raw_sha256=contract.raw_sha256(precommit), **raws)
        self.assertTrue(receipt["a_deterministic_selection_partition_replayed"])

    def test_parent_matches_a_predecessor_fractional_z_timestamp(self) -> None:
        seed = _obj(self.bundle["a_seed"])
        seed["revealed_at"] = "2026-09-02T00:00:09.500000Z"
        seed_raw = _reseal(seed, "artifact_sha256")
        plan_raw = a_frame.build_sampling_plan_bytes(
            self.bundle["a_scope"], self.bundle["a_census"], self.bundle["a_frame"], seed_raw,
            selection_sealed_at=A_SELECTED)
        raws = {**self._raws(), "a_seed": seed_raw, "a_plan": plan_raw}
        subjects = contract.build_subject_rows_bytes(**raws)
        precommit = contract.build_precommit_bytes(
            subjects, precommit_id="fixture-a-fractional-time", precommitted_at=PRECOMMITTED, **raws)
        receipt = parent.validate_subject_precommit_against_raw_inputs(
            subject_rows_raw=subjects, expected_subject_rows_raw_sha256=contract.raw_sha256(subjects),
            precommit_raw=precommit, expected_precommit_raw_sha256=contract.raw_sha256(precommit), **raws)
        self.assertTrue(receipt["a_deterministic_selection_partition_replayed"])

    def test_generic_is_unresolved_and_never_coerced_to_track_a(self) -> None:
        rows = _rows(self.bundle["subjects"])
        generic = [row for row in rows if row["source_profile"] == "GENERIC_FALLBACK"]
        self.assertEqual(len(generic), 5)
        self.assertTrue(all(row["evidence_disposition"] == "UNRESOLVED_PREANNOTATION_EVIDENCE" for row in generic))
        self.assertFalse(any(contract.FORBIDDEN_LABEL_FIELDS.intersection(row) for row in rows))

    def test_label_field_injection_and_generic_coercion_are_rejected(self) -> None:
        for mutate in (
            lambda rows: rows[0].__setitem__("truth_work_id", "WORK:1"),
            lambda rows: next(row for row in rows if row["source_profile"] == "GENERIC_FALLBACK").__setitem__("evidence_disposition", "PRESENTED_CONTEXT_UNJUDGED"),
        ):
            rows = _rows(self.bundle["subjects"])
            mutate(rows)
            rows[0] = contract.with_self_hash(rows[0], "row_sha256")
            with self.assertRaises(contract.P0PresentedAContextSubjectV2PrecommitError):
                contract.validate_subject_rows_bytes(_jsonl(rows), **self._raws())

    def test_subject_reorder_swap_duplicate_missing_and_surplus_backfill_rejected(self) -> None:
        mutations = []
        rows = _rows(self.bundle["subjects"])
        mutations.append([rows[1], rows[0], *rows[2:]])
        mutations.append([rows[0], rows[0], *rows[2:]])
        mutations.append(rows[:-1])
        mutations.append([*rows, rows[-1]])
        for attacked in mutations:
            with self.subTest(length=len(attacked)), self.assertRaises(contract.P0PresentedAContextSubjectV2PrecommitError):
                contract.validate_subject_rows_bytes(_jsonl(attacked), **self._raws())

    def test_profile_frame_payload_and_full_census_mapping_attacks_fail(self) -> None:
        census = _rows(self.bundle["a_census"])
        for field, value in (
            ("source_profile", "GENERIC_FALLBACK"), ("payload_sha256", "0" * 64),
            ("upstream_frame_candidate_id", "P0:FRAME:CANDIDATE:" + "0" * 64),
        ):
            attacked = deepcopy(census)
            attacked[-1][field] = value
            attacked[-1] = a_frame.with_self_hash(attacked[-1], "row_sha256")
            with self.subTest(field=field), self.assertRaises(contract.P0PresentedAContextSubjectV2PrecommitError):
                contract.validate_subject_rows_bytes(self.bundle["subjects"], **{**self._raws(), "a_census": _jsonl(attacked)})

    def test_character_span_and_surface_hash_are_replayed(self) -> None:
        census = _rows(self.bundle["a_census"])
        census[0]["surface_end"] = census[0]["surface_end"] - 1
        census[0] = a_frame.with_self_hash(census[0], "row_sha256")
        with self.assertRaises(contract.P0PresentedAContextSubjectV2PrecommitError):
            contract.validate_subject_rows_bytes(self.bundle["subjects"], **{**self._raws(), "a_census": _jsonl(census)})

    def test_scope_predecessor_swap_and_chronology_equality_fail(self) -> None:
        scope = _obj(self.bundle["a_scope"])
        scope["upstream_bridge_inventory_raw_sha256"] = "0" * 64
        with self.assertRaises(contract.P0PresentedAContextSubjectV2PrecommitError):
            contract.validate_subject_rows_bytes(self.bundle["subjects"], **{**self._raws(), "a_scope": _reseal(scope, "artifact_sha256")})
        precommit = _obj(self.bundle["precommit"])
        precommit["precommitted_at"] = A_SELECTED
        with self.assertRaisesRegex(contract.P0PresentedAContextSubjectV2PrecommitError, "chronology"):
            contract.validate_precommit_bytes(_reseal(precommit, "artifact_sha256"), self.bundle["subjects"], **self._raws())

    def test_promotion_flags_and_bool_integer_attacks_fail(self) -> None:
        for field, value in (("actual_authority_granted", True), ("actual_a_context_credit_count", True),
                             ("v2_annotation_event_count", 1), ("production_approval", True)):
            row = _obj(self.bundle["precommit"])
            row[field] = value
            with self.subTest(field=field), self.assertRaises(contract.P0PresentedAContextSubjectV2PrecommitError):
                contract.validate_precommit_bytes(_reseal(row, "artifact_sha256"), self.bundle["subjects"], **self._raws())

    def test_parent_rejects_coherently_resealed_a_selected_surplus_swap_and_promotion(self) -> None:
        plan = _obj(self.bundle["a_plan"])
        selected = plan["selected_contexts"]  # type: ignore[assignment]
        surplus = plan["eligible_surplus_contexts"]  # type: ignore[assignment]
        selected_index = len(selected) - 1
        profile = selected[selected_index]["source_profile"]
        surplus_index = next(index for index, row in enumerate(surplus) if row["source_profile"] == profile)
        outgoing, incoming = deepcopy(selected[selected_index]), deepcopy(surplus[surplus_index])
        incoming["input_sequence"] = outgoing["input_sequence"]
        outgoing["input_sequence"] = 0
        selected[selected_index], surplus[surplus_index] = incoming, outgoing
        plan["selected_context_set_sha256"] = _sha(selected)
        plan["eligible_surplus_set_sha256"] = _sha(surplus)
        attacked_plan = _reseal(plan, "artifact_sha256")
        with self.assertRaisesRegex(parent.P0PresentedAContextSubjectV2ParentError, "selection/partition"):
            parent.validate_subject_precommit_against_raw_inputs(
                subject_rows_raw=self.bundle["subjects"], expected_subject_rows_raw_sha256=contract.raw_sha256(self.bundle["subjects"]),
                precommit_raw=self.bundle["precommit"], expected_precommit_raw_sha256=contract.raw_sha256(self.bundle["precommit"]),
                **{**self._raws(), "a_plan": attacked_plan})

        promoted = _obj(self.bundle["a_plan"])
        promoted["actual_authority_granted"] = True
        promoted["production_approval"] = True
        promoted["actual_a_context_review_count"] = 20
        with self.assertRaisesRegex(parent.P0PresentedAContextSubjectV2ParentError, "authority/metric"):
            parent.validate_subject_precommit_against_raw_inputs(
                subject_rows_raw=self.bundle["subjects"], expected_subject_rows_raw_sha256=contract.raw_sha256(self.bundle["subjects"]),
                precommit_raw=self.bundle["precommit"], expected_precommit_raw_sha256=contract.raw_sha256(self.bundle["precommit"]),
                **{**self._raws(), "a_plan": _reseal(promoted, "artifact_sha256")})

        labeled = _obj(self.bundle["a_plan"])
        labeled["gold_label"] = "WORK:FORGED"
        with self.assertRaises(parent.P0PresentedAContextSubjectV2ParentError):
            parent.validate_subject_precommit_against_raw_inputs(
                subject_rows_raw=self.bundle["subjects"], expected_subject_rows_raw_sha256=contract.raw_sha256(self.bundle["subjects"]),
                precommit_raw=self.bundle["precommit"], expected_precommit_raw_sha256=contract.raw_sha256(self.bundle["precommit"]),
                **{**self._raws(), "a_plan": _reseal(labeled, "artifact_sha256")})
        for field, value in (("candidate_work_ids", ["WORK:FORGED"]),
                             ("predicted_work_id", "WORK:FORGED")):
            injected = _obj(self.bundle["a_plan"])
            injected[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(
                parent.P0PresentedAContextSubjectV2ParentError, "fields mismatch"
            ):
                parent.validate_subject_precommit_against_raw_inputs(
                    subject_rows_raw=self.bundle["subjects"], expected_subject_rows_raw_sha256=contract.raw_sha256(self.bundle["subjects"]),
                    precommit_raw=self.bundle["precommit"], expected_precommit_raw_sha256=contract.raw_sha256(self.bundle["precommit"]),
                    **{**self._raws(), "a_plan": _reseal(injected, "artifact_sha256")})

    def test_none_public_raw_boundaries_normalize_to_component_errors(self) -> None:
        with self.assertRaises(contract.P0PresentedAContextSubjectV2PrecommitError):
            contract.validate_subject_rows_bytes(None, **self._raws())  # type: ignore[arg-type]
        with self.assertRaises(contract.P0PresentedAContextSubjectV2PrecommitError):
            contract.validate_precommit_bytes(None, self.bundle["subjects"], **self._raws())  # type: ignore[arg-type]
        with self.assertRaises(parent.P0PresentedAContextSubjectV2ParentError):
            parent.validate_subject_precommit_against_raw_inputs(
                subject_rows_raw=None, expected_subject_rows_raw_sha256="0" * 64,  # type: ignore[arg-type]
                precommit_raw=self.bundle["precommit"], expected_precommit_raw_sha256=contract.raw_sha256(self.bundle["precommit"]),
                **self._raws())
        bridge_rows = _rows(self.bundle["bridge_inventory"])
        bridge_rows[0]["payload_base64"] = 7
        bridge_rows[0] = contract.with_self_hash(bridge_rows[0], "bridge_row_sha256")
        malformed_plan = _obj(self.bundle["source_plan"])
        malformed_plan["selected_inputs"][0] = 7  # type: ignore[index]
        malformed_plan["selected_input_set_sha256"] = _sha(malformed_plan["selected_inputs"])
        for key, raw in (("bridge_inventory", _jsonl(bridge_rows)),
                         ("source_plan", _reseal(malformed_plan, "artifact_sha256"))):
            with self.subTest(malformed=key), self.assertRaises(parent.P0PresentedAContextSubjectV2ParentError):
                parent.validate_subject_precommit_against_raw_inputs(
                    subject_rows_raw=self.bundle["subjects"], expected_subject_rows_raw_sha256=contract.raw_sha256(self.bundle["subjects"]),
                    precommit_raw=self.bundle["precommit"], expected_precommit_raw_sha256=contract.raw_sha256(self.bundle["precommit"]),
                    **{**self._raws(), key: raw})
        for mutate in (
            lambda raws: raws.pop("a_seed"),
            lambda raws: raws.__setitem__("unexpected", b"{}\n"),
            lambda raws: raws.__setitem__("a_seed", None),
        ):
            raws = self._raws()
            mutate(raws)
            with self.assertRaises(contract.P0PresentedAContextSubjectV2PrecommitError):
                contract.validate_subject_rows_bytes(self.bundle["subjects"], **raws)  # type: ignore[arg-type]
            with self.assertRaises(parent.P0PresentedAContextSubjectV2ParentError):
                parent.validate_subject_precommit_against_raw_inputs(
                    subject_rows_raw=self.bundle["subjects"], expected_subject_rows_raw_sha256=contract.raw_sha256(self.bundle["subjects"]),
                    precommit_raw=self.bundle["precommit"], expected_precommit_raw_sha256=contract.raw_sha256(self.bundle["precommit"]),
                    **raws)  # type: ignore[arg-type]
        surrogate = b'{"x":"\\ud800"}\n'
        with self.assertRaises(parent.P0PresentedAContextSubjectV2ParentError):
            parent.validate_subject_precommit_against_raw_inputs(
                subject_rows_raw=surrogate, expected_subject_rows_raw_sha256=hashlib.sha256(surrogate).hexdigest(),
                precommit_raw=self.bundle["precommit"], expected_precommit_raw_sha256=contract.raw_sha256(self.bundle["precommit"]),
                **self._raws())

    def test_parent_rejects_source_and_a_selection_reveal_equality(self) -> None:
        for key in ("a_plan", "source_plan"):
            plan = _obj(self.bundle[key])
            seed = _obj(self.bundle["a_seed" if key == "a_plan" else "source_seed"])
            plan["selection_sealed_at"] = seed["revealed_at"]
            with self.subTest(key=key), self.assertRaisesRegex(
                parent.P0PresentedAContextSubjectV2ParentError, "chronology"
            ):
                parent.validate_subject_precommit_against_raw_inputs(
                    subject_rows_raw=self.bundle["subjects"], expected_subject_rows_raw_sha256=contract.raw_sha256(self.bundle["subjects"]),
                    precommit_raw=self.bundle["precommit"], expected_precommit_raw_sha256=contract.raw_sha256(self.bundle["precommit"]),
                    **{**self._raws(), key: _reseal(plan, "artifact_sha256")})

    def test_parent_rejects_upstream_enum_and_numeric_bool_confusion(self) -> None:
        census = _rows(self.bundle["a_census"])
        census[0]["presented_takedown_status"] = "EVIL"
        census[0]["eligibility_status"] = "EXCLUDED"
        census[0]["exclusion_reason_codes"] = ["TAKEDOWN_NOT_ACTIVE"]
        census[0] = contract.with_self_hash(census[0], "row_sha256")
        with self.assertRaisesRegex(parent.P0PresentedAContextSubjectV2ParentError, "enum/type"):
            parent.validate_subject_precommit_against_raw_inputs(
                subject_rows_raw=self.bundle["subjects"], expected_subject_rows_raw_sha256=contract.raw_sha256(self.bundle["subjects"]),
                precommit_raw=self.bundle["precommit"], expected_precommit_raw_sha256=contract.raw_sha256(self.bundle["precommit"]),
                **{**self._raws(), "a_census": _jsonl(census)})

        frame = _obj(self.bundle["a_frame"])
        frame["excluded_candidate_count"] = False
        frame["actual_a_context_review_count"] = False
        frame["actual_surplus_review_count"] = False
        with self.assertRaisesRegex(parent.P0PresentedAContextSubjectV2ParentError, "integer"):
            parent.validate_subject_precommit_against_raw_inputs(
                subject_rows_raw=self.bundle["subjects"], expected_subject_rows_raw_sha256=contract.raw_sha256(self.bundle["subjects"]),
                precommit_raw=self.bundle["precommit"], expected_precommit_raw_sha256=contract.raw_sha256(self.bundle["precommit"]),
                **{**self._raws(), "a_frame": _reseal(frame, "artifact_sha256")})

    def test_parent_rejects_nested_scope_label_and_unknown_fields(self) -> None:
        for key, container, field in (
            ("a_scope", "adapter_profile_map", "predicted_work_id"),
            ("source_scope", "strata", "unknown_nested_field"),
            ("a_scope", "adapter_profile_map", "model_prediction_work_id"),
        ):
            value = _obj(self.bundle[key])
            value[container][0][field] = "WORK:FORGED"  # type: ignore[index]
            with self.subTest(key=key), self.assertRaises(parent.P0PresentedAContextSubjectV2ParentError):
                parent.validate_subject_precommit_against_raw_inputs(
                    subject_rows_raw=self.bundle["subjects"], expected_subject_rows_raw_sha256=contract.raw_sha256(self.bundle["subjects"]),
                    precommit_raw=self.bundle["precommit"], expected_precommit_raw_sha256=contract.raw_sha256(self.bundle["precommit"]),
                    **{**self._raws(), key: _reseal(value, "artifact_sha256")})

        scope = _obj(self.bundle["a_scope"])
        scope["strata"][0]["platform_scope"] = "absent-platform"  # type: ignore[index]
        scope["strata"][0]["quota"] = 0  # type: ignore[index]
        attacked_scope = contract.with_self_hash(scope, "artifact_sha256")
        frame = _obj(self.bundle["a_frame"])
        frame["scope_sha256"] = attacked_scope["artifact_sha256"]
        attacked_frame = contract.with_self_hash(frame, "artifact_sha256")
        seed = _obj(self.bundle["a_seed"])
        seed["scope_sha256"] = attacked_scope["artifact_sha256"]
        seed["frame_manifest_sha256"] = attacked_frame["artifact_sha256"]
        attacked_seed = contract.with_self_hash(seed, "artifact_sha256")
        plan = _obj(self.bundle["a_plan"])
        plan["scope_sha256"] = attacked_scope["artifact_sha256"]
        plan["frame_manifest_sha256"] = attacked_frame["artifact_sha256"]
        plan["seed_receipt_sha256"] = attacked_seed["artifact_sha256"]
        attacked_plan = contract.with_self_hash(plan, "artifact_sha256")
        with self.assertRaises(parent.P0PresentedAContextSubjectV2ParentError):
            parent.validate_subject_precommit_against_raw_inputs(
                subject_rows_raw=self.bundle["subjects"], expected_subject_rows_raw_sha256=contract.raw_sha256(self.bundle["subjects"]),
                precommit_raw=self.bundle["precommit"], expected_precommit_raw_sha256=contract.raw_sha256(self.bundle["precommit"]),
                **{**self._raws(), "a_scope": _file(attacked_scope), "a_frame": _file(attacked_frame),
                   "a_seed": _file(attacked_seed), "a_plan": _file(attacked_plan)})

        for key, expected in (("source_plan", 10), ("a_plan", 5)):
            plan = _obj(self.bundle[key])
            plan["per_profile_counts"] = {"HIDDEN": expected * 4}
            with self.subTest(counts=key), self.assertRaises(parent.P0PresentedAContextSubjectV2ParentError):
                parent.validate_subject_precommit_against_raw_inputs(
                    subject_rows_raw=self.bundle["subjects"], expected_subject_rows_raw_sha256=contract.raw_sha256(self.bundle["subjects"]),
                    precommit_raw=self.bundle["precommit"], expected_precommit_raw_sha256=contract.raw_sha256(self.bundle["precommit"]),
                    **{**self._raws(), key: _reseal(plan, "artifact_sha256")})

    def test_parent_pins_and_no_llm_batch_or_producer_import(self) -> None:
        source = Path(parent.__file__).read_text(encoding="utf-8")
        self.assertNotIn("from llm_batch", source)
        self.assertNotIn("import llm_batch", source)
        with patch.object(contract, "validate_subject_rows_bytes", side_effect=AssertionError("producer called")):
            receipt = self._parent()
        self.assertFalse(receipt["source_parent_full_frame_replay_verified"])
        self.assertTrue(receipt["source_deterministic_selection_partition_replayed"])
        with self.assertRaises(parent.P0PresentedAContextSubjectV2ParentError):
            parent.validate_subject_precommit_against_raw_inputs(
                subject_rows_raw=self.bundle["subjects"], expected_subject_rows_raw_sha256="0" * 64,
                precommit_raw=self.bundle["precommit"], expected_precommit_raw_sha256=contract.raw_sha256(self.bundle["precommit"]),
                **self._raws())
        with self.assertRaises(parent.P0PresentedAContextSubjectV2ParentError):
            parent.validate_subject_precommit_against_raw_inputs(
                subject_rows_raw=self.bundle["subjects"], expected_subject_rows_raw_sha256=contract.raw_sha256(self.bundle["subjects"]),
                precommit_raw=self.bundle["precommit"], expected_precommit_raw_sha256="0" * 64,
                **self._raws())

    def test_commitment_tamper_noncanonical_and_output_cap_fail(self) -> None:
        rows = _rows(self.bundle["subjects"])
        rows[0]["source_claim_set_sha256"] = "0" * 64
        rows[0] = contract.with_self_hash(rows[0], "row_sha256")
        with self.assertRaises(contract.P0PresentedAContextSubjectV2PrecommitError):
            contract.validate_subject_rows_bytes(_jsonl(rows), **self._raws())
        deep = b'{"x":' + b"[" * 5000 + b"0" + b"]" * 5000 + b"}\n"
        for raw in (b"\xef\xbb\xbf{}\n", b"{}\r\n", deep, b" " * 1_000_001):
            with self.subTest(prefix=raw[:8]), self.assertRaises(contract.P0PresentedAContextSubjectV2PrecommitError):
                contract.validate_subject_rows_bytes(raw, **self._raws())

    def test_archived_packet_v1_inventory_is_unchanged_and_has_no_runtime_reference(self) -> None:
        self.assertEqual(len(old_packet.CHILD_FILES), 13)
        packet_source = Path(old_packet.__file__).read_text(encoding="utf-8")
        self.assertNotIn(contract.PRECOMMIT_SCHEMA, packet_source)
        self.assertNotIn(contract.SUBJECT_SCHEMA, packet_source)
        self.assertEqual(contract.COMPONENT_MANIFEST, parent.EXPECTED_COMPONENT_MANIFEST)
        self.assertEqual(contract.COMPONENT_MANIFEST_SHA256, parent.EXPECTED_COMPONENT_MANIFEST_SHA256)


if __name__ == "__main__":
    unittest.main()
