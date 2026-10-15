"""A-event V2 result-free target/precommit의 회귀 및 집중 공격 테스트."""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from llm_batch.grounding import p0_actual_packet_contract as old_packet
from llm_batch.grounding import p0_presented_a_context_annotation_event_v2_target_precommit_contract as contract
from llm_batch.grounding import p0_presented_a_context_annotation_event_v2_target_precommit_parent_validator as parent
from tests import test_p0_presented_a_context_annotation_subject_v2_precommit as subject_fixture


TARGET_PRECOMMITTED = "2026-09-02T00:00:12Z"
RESPONSE_SCHEMA_COMMITMENT = contract.RESPONSE_SCHEMA_COMMITMENT_SHA256


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


def _bundle() -> dict[str, bytes]:
    predecessor = subject_fixture._bundle()
    raws = {key: predecessor[key] for key in contract.UPSTREAM_RAW_KEYS}
    targets = contract.build_target_rows_bytes(
        predecessor["subjects"], predecessor["precommit"], **raws)
    target_precommit = contract.build_precommit_bytes(
        targets, predecessor["subjects"], predecessor["precommit"],
        precommitted_at=TARGET_PRECOMMITTED, **raws,
    )
    return {**predecessor, "targets": targets, "target_precommit": target_precommit}


class AEventV2TargetPrecommitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = _bundle()

    def _raws(self, bundle: dict[str, bytes] | None = None) -> dict[str, bytes]:
        value = self.bundle if bundle is None else bundle
        return {key: value[key] for key in contract.UPSTREAM_RAW_KEYS}

    def _pins(self, bundle: dict[str, bytes] | None = None) -> dict[str, str]:
        value = self.bundle if bundle is None else bundle
        return {key: contract.raw_sha256(value[key]) for key in contract.UPSTREAM_RAW_KEYS} | {
            "subject_rows": contract.raw_sha256(value["subjects"]),
            "subject_precommit": contract.raw_sha256(value["precommit"]),
            "target_rows": contract.raw_sha256(value["targets"]),
            "target_precommit": contract.raw_sha256(value["target_precommit"]),
        }

    def _parent(self, bundle: dict[str, bytes] | None = None) -> dict[str, object]:
        value = self.bundle if bundle is None else bundle
        return parent.validate_target_precommit_against_raw_inputs(
            target_rows_raw=value["targets"],
            target_precommit_raw=value["target_precommit"],
            subject_rows_raw=value["subjects"],
            subject_precommit_raw=value["precommit"],
            expected_raw_sha256=self._pins(value),
            **self._raws(value),
        )

    def test_positive_exact_15_raw_composed_parent(self) -> None:
        targets = contract.validate_target_rows_bytes(
            self.bundle["targets"], self.bundle["subjects"], self.bundle["precommit"], **self._raws())
        precommit = contract.validate_precommit_bytes(
            self.bundle["target_precommit"], self.bundle["targets"], self.bundle["subjects"],
            self.bundle["precommit"], **self._raws())
        receipt = self._parent()
        self.assertEqual((len(targets), precommit["target_count"], receipt["total_bound_raw_artifact_count"]),
                         (20, 20, 15))
        self.assertEqual(receipt["validation_architecture"], "PRODUCER_FREE_COMPOSED_PARENT")
        self.assertTrue(receipt["producer_free_composed_parent_verified"])
        self.assertTrue(receipt["predecessor_subject_parent_executed"])
        self.assertTrue(receipt["predecessor_subject_replay_delegated"])
        self.assertFalse(receipt["predecessor_subject_replay_locally_verified"])
        self.assertFalse(receipt["predecessor_subject_replay_locally_duplicated"])

    def test_target_order_id_commitment_and_genesis_are_deterministic(self) -> None:
        again = contract.build_target_rows_bytes(
            self.bundle["subjects"], self.bundle["precommit"], **self._raws())
        self.assertEqual(again, self.bundle["targets"])
        rows = _rows(again)
        self.assertEqual([row["target_sequence"] for row in rows], list(range(1, 21)))
        self.assertEqual(len({row["target_id"] for row in rows}), 20)
        self.assertEqual(len({row["journal_genesis_sha256"] for row in rows}), 20)

    def test_generic_subjects_are_included_without_private_profile_copy(self) -> None:
        subjects = _rows(self.bundle["subjects"])
        targets = _rows(self.bundle["targets"])
        generic_ids = {row["subject_id"] for row in subjects if row["source_profile"] == "GENERIC_FALLBACK"}
        self.assertEqual(len(generic_ids), 5)
        self.assertTrue(generic_ids <= {row["subject_id"] for row in targets})
        self.assertTrue(all("source_profile" not in row and "evidence_disposition" not in row for row in targets))
        self.assertEqual(self._parent()["generic_fallback_target_count"], 5)

    def test_response_taxonomy_is_only_one_common_precommit_commitment(self) -> None:
        targets = _rows(self.bundle["targets"])
        precommit = _obj(self.bundle["target_precommit"])
        self.assertEqual(precommit["response_schema_commitment_sha256"], RESPONSE_SCHEMA_COMMITMENT)
        self.assertFalse(any("response_schema" in key or "taxonomy" in key for row in targets for key in row))
        again = contract.build_precommit_bytes(
            self.bundle["targets"], self.bundle["subjects"], self.bundle["precommit"],
            precommitted_at=TARGET_PRECOMMITTED, **self._raws())
        self.assertEqual(again, self.bundle["target_precommit"])
        parameters = inspect.signature(contract.build_precommit_bytes).parameters
        self.assertNotIn("target_precommit_id", parameters)
        self.assertNotIn("response_schema_commitment_sha256", parameters)
        with self.assertRaises(contract.P0PresentedAContextEventV2TargetPrecommitError):
            contract.build_precommit_bytes(
                self.bundle["targets"], self.bundle["subjects"], self.bundle["precommit"],
                target_precommit_id="forbidden-free-id", response_schema_commitment_sha256="1" * 64,
                precommitted_at=TARGET_PRECOMMITTED, **self._raws())
        self.assertEqual(contract.build_target_rows_bytes(
            self.bundle["subjects"], self.bundle["precommit"], **self._raws()), self.bundle["targets"])
        self.assertEqual(contract.RESPONSE_SCHEMA["status_decision_matrix"], {
            "JUDGED": ["WORK_ID", "NIL"],
            "UNJUDGED": ["UNRESOLVED"],
            "UNAVAILABLE": ["UNRESOLVED"],
        })
        self.assertEqual(
            contract.RESPONSE_SCHEMA["initial_state_payload_rule"], "NO_RESULT_OBJECT_EXISTS")
        self.assertIn("COMPLETE_FUTURE_CANDIDATE_ENUMERATION", contract.RESPONSE_SCHEMA["nil_rule"])
        self.assertIn("NOT_NIL_NOT_NEGATIVE_NOT_GOLD", contract.RESPONSE_SCHEMA["unresolved_rule"])

    def test_no_per_target_label_reviewer_result_or_event_fields(self) -> None:
        for row in _rows(self.bundle["targets"]):
            forbidden = {key for key in row if key != "schema_version" and any(
                fragment in key.lower() for fragment in contract.FORBIDDEN_PER_TARGET_FIELD_FRAGMENTS)}
            self.assertEqual(forbidden, set())
        for field in ("gold_label", "reviewer_id", "result_value", "annotation_event"):
            rows = _rows(self.bundle["targets"])
            rows[0][field] = "FORGED"
            rows[0] = contract.with_self_hash(rows[0], "row_sha256")
            attacked = _jsonl(rows)
            with self.subTest(field=field), self.assertRaises(contract.P0PresentedAContextEventV2TargetPrecommitError):
                contract.validate_target_rows_bytes(
                    attacked, self.bundle["subjects"], self.bundle["precommit"], **self._raws())

    def test_counts_denominator_authority_wiring_and_metrics_are_closed(self) -> None:
        row = _obj(self.bundle["target_precommit"])
        self.assertEqual((row["target_count"], row["annotation_opportunity_count"]), (20, 20))
        self.assertEqual((row["planned_primary_opportunity_count"], row["unstarted_target_count"]), (20, 20))
        self.assertEqual(row["source_profile_counts"], {profile: 5 for profile in (
            "OFFICIAL_STRUCTURED", "COMMUNITY_STRUCTURED", "MEDIA_OCR", "GENERIC_FALLBACK")})
        self.assertEqual(set(row["bound_input_raw_sha256"]), set(contract.INPUT_RAW_KEYS))
        self.assertTrue(all(row[field] == 0 and type(row[field]) is int for field in contract.ZERO_COUNT_FIELDS))
        self.assertTrue(all(row[field] is False for field in contract.FALSE_FIELDS))
        self.assertEqual(row["statistical_denominator_contribution"], "NONE")
        self.assertEqual(row["metric_status"], contract.METRIC_STATUS)
        self.assertIs(row["iid_independence_assumed"], False)
        self.assertIs(self._parent()["iid_independence_assumed"], False)
        self.assertIs(contract.COMPONENT_MANIFEST["iid_independence_assumed"], False)
        self.assertEqual(
            contract.COMPONENT_MANIFEST["future_inferential_cluster_unit"],
            "UPSTREAM_SOURCE_FRAME_CANDIDATE_ID",
        )
        self.assertEqual(
            row["future_inferential_cluster_unit"],
            contract.COMPONENT_MANIFEST["future_inferential_cluster_unit"],
        )
        self.assertEqual(
            self._parent()["future_inferential_cluster_unit"],
            row["future_inferential_cluster_unit"],
        )

    def test_subject_precommit_must_strictly_precede_target_precommit(self) -> None:
        predecessor_time = _obj(self.bundle["precommit"])["precommitted_at"]
        with self.assertRaisesRegex(contract.P0PresentedAContextEventV2TargetPrecommitError, "strictly follow"):
            contract.build_precommit_bytes(
                self.bundle["targets"], self.bundle["subjects"], self.bundle["precommit"],
                precommitted_at=predecessor_time, **self._raws())  # type: ignore[arg-type]
        attacked = _obj(self.bundle["target_precommit"])
        attacked["precommitted_at"] = predecessor_time
        attacked["target_precommit_id"] = (
            contract.TARGET_PRECOMMIT_ID_PREFIX
            + contract.canonical_sha256({
                "domain": contract.TARGET_PRECOMMIT_ID_DOMAIN,
                "bound_input_raw_sha256": attacked["bound_input_raw_sha256"],
                "target_rows_raw_sha256": attacked["target_rows_raw_sha256"],
                "response_schema_commitment_sha256": attacked[
                    "response_schema_commitment_sha256"
                ],
                "precommitted_at": predecessor_time,
            })
        )
        attacked_raw = _reseal(attacked, "artifact_sha256")
        with self.assertRaisesRegex(parent.P0PresentedAContextEventV2TargetParentError, "strictly precede"):
            parent.validate_target_precommit_against_raw_inputs(
                target_rows_raw=self.bundle["targets"],
                target_precommit_raw=attacked_raw,
                subject_rows_raw=self.bundle["subjects"],
                subject_precommit_raw=self.bundle["precommit"],
                expected_raw_sha256={**self._pins(), "target_precommit": contract.raw_sha256(attacked_raw)},
                **self._raws())

    def test_timestamp_is_strict_rfc3339_but_offset_fractional_has_parent_parity(self) -> None:
        with self.assertRaisesRegex(
            contract.P0PresentedAContextEventV2TargetPrecommitError, "strict RFC3339"
        ):
            contract.build_precommit_bytes(
                self.bundle["targets"], self.bundle["subjects"], self.bundle["precommit"],
                precommitted_at="2026-09-02 00:00:12+00:00", **self._raws())
        raw = contract.build_precommit_bytes(
            self.bundle["targets"], self.bundle["subjects"], self.bundle["precommit"],
            precommitted_at="2026-09-02T09:00:12.125+09:00", **self._raws())
        value = {**self.bundle, "target_precommit": raw}
        receipt = self._parent(value)
        self.assertEqual(receipt["validated_raw_sha256"]["target_precommit"], contract.raw_sha256(raw))

    def test_parent_receipt_binds_exact_15_raws_and_changes_across_valid_bundles(self) -> None:
        first = self._parent()
        later_raw = contract.build_precommit_bytes(
            self.bundle["targets"], self.bundle["subjects"], self.bundle["precommit"],
            precommitted_at="2026-09-02T00:00:13Z", **self._raws())
        later_bundle = {**self.bundle, "target_precommit": later_raw}
        second = self._parent(later_bundle)
        self.assertEqual(set(first["validated_raw_sha256"]), set(self._pins()))
        self.assertEqual(first["validated_raw_sha256"], self._pins())
        self.assertNotEqual(first["validated_raw_pin_set_sha256"],
                            second["validated_raw_pin_set_sha256"])
        self.assertNotEqual(first["receipt_sha256"], second["receipt_sha256"])
        self.assertNotEqual(
            _obj(self.bundle["target_precommit"])["target_precommit_id"],
            _obj(later_raw)["target_precommit_id"],
        )

    def test_target_tamper_order_id_and_genesis_fail(self) -> None:
        for field, value in (
            ("target_sequence", 2), ("subject_input_sequence", False),
            ("target_id", "P0:A:ANNOTATION:TARGET:V2:forged"),
            ("journal_genesis_sha256", "0" * 64),
        ):
            rows = _rows(self.bundle["targets"])
            rows[0][field] = value
            rows[0] = contract.with_self_hash(rows[0], "row_sha256")
            with self.subTest(field=field), self.assertRaises(contract.P0PresentedAContextEventV2TargetPrecommitError):
                contract.validate_target_rows_bytes(
                    _jsonl(rows), self.bundle["subjects"], self.bundle["precommit"], **self._raws())

    def test_precommit_bool_integer_confusion_and_open_flag_fail(self) -> None:
        for field, value in (("target_count", True), ("annotation_result_count", False),
                             ("actual_authority_granted", True)):
            row = _obj(self.bundle["target_precommit"])
            row[field] = value
            attacked = _reseal(row, "artifact_sha256")
            with self.subTest(field=field), self.assertRaises(contract.P0PresentedAContextEventV2TargetPrecommitError):
                contract.validate_precommit_bytes(
                    attacked, self.bundle["targets"], self.bundle["subjects"],
                    self.bundle["precommit"], **self._raws())

    def test_exact_schemas_reject_extra_and_missing_fields(self) -> None:
        rows = _rows(self.bundle["targets"])
        rows[0]["unknown"] = 1
        rows[0] = contract.with_self_hash(rows[0], "row_sha256")
        with self.assertRaises(contract.P0PresentedAContextEventV2TargetPrecommitError):
            contract.validate_target_rows_bytes(
                _jsonl(rows), self.bundle["subjects"], self.bundle["precommit"], **self._raws())
        row = _obj(self.bundle["target_precommit"])
        row.pop("journal_head_count")
        with self.assertRaises(contract.P0PresentedAContextEventV2TargetPrecommitError):
            contract.validate_precommit_bytes(
                _file(row), self.bundle["targets"], self.bundle["subjects"],
                self.bundle["precommit"], **self._raws())

    def test_caller_sha_pins_cover_both_predecessor_and_current_outputs(self) -> None:
        kwargs = {
            "target_rows_raw": self.bundle["targets"],
            "target_precommit_raw": self.bundle["target_precommit"],
            "subject_rows_raw": self.bundle["subjects"],
            "subject_precommit_raw": self.bundle["precommit"],
            "expected_raw_sha256": self._pins(),
            **self._raws(),
        }
        for field in (*contract.UPSTREAM_RAW_KEYS, "subject_rows", "subject_precommit",
                      "target_rows", "target_precommit"):
            pins = dict(self._pins())
            pins[field] = "0" * 64
            with self.subTest(field=field), self.assertRaises(parent.P0PresentedAContextEventV2TargetParentError):
                parent.validate_target_precommit_against_raw_inputs(**{**kwargs, "expected_raw_sha256": pins})

    def test_predecessor_parent_is_called_directly_and_failure_is_fatal(self) -> None:
        with patch.object(parent.subject_parent, "validate_subject_precommit_against_raw_inputs",
                          side_effect=RuntimeError("dependency failed")):
            with self.assertRaisesRegex(parent.P0PresentedAContextEventV2TargetParentError, "execution failed"):
                self._parent()

    def test_predecessor_receipt_manifest_authority_and_self_hash_are_strict(self) -> None:
        raw_receipt = parent.subject_parent.validate_subject_precommit_against_raw_inputs(
            subject_rows_raw=self.bundle["subjects"],
            expected_subject_rows_raw_sha256=contract.raw_sha256(self.bundle["subjects"]),
            precommit_raw=self.bundle["precommit"],
            expected_precommit_raw_sha256=contract.raw_sha256(self.bundle["precommit"]),
            **self._raws())
        for field, value, reseal in (
            ("actual_authority_granted", True, True),
            ("expected_component_manifest_sha256", "0" * 64, True),
            ("total_bound_raw_artifact_count", 14, True),
            ("receipt_sha256", "0" * 64, False),
        ):
            receipt = dict(raw_receipt)
            receipt[field] = value
            if reseal:
                material = dict(receipt)
                material.pop("receipt_sha256", None)
                receipt["receipt_sha256"] = hashlib.sha256(contract.canonical_bytes(material)).hexdigest()
            with self.subTest(field=field), patch.object(
                parent.subject_parent, "validate_subject_precommit_against_raw_inputs", return_value=receipt
            ), self.assertRaises(parent.P0PresentedAContextEventV2TargetParentError):
                self._parent()

    def test_noncanonical_duplicate_nan_deep_and_cap_inputs_normalize(self) -> None:
        malformed = (
            b"\xef\xbb\xbf{}\n", b"{}\r\n", b'{"x":NaN}\n', b'{"x":1,"x":2}\n',
            b'{"x":' + b"[" * 5000 + b"0" + b"]" * 5000 + b"}\n",
            b" " * (contract.MAX_OUTPUT_BYTES + 1),
        )
        for raw in malformed:
            with self.subTest(prefix=raw[:12]), self.assertRaises(contract.P0PresentedAContextEventV2TargetPrecommitError):
                contract.validate_target_rows_bytes(
                    raw, self.bundle["subjects"], self.bundle["precommit"], **self._raws())
        with self.assertRaises(parent.P0PresentedAContextEventV2TargetParentError):
            parent.validate_target_precommit_against_raw_inputs(
                target_rows_raw=b"[]\n",
                target_precommit_raw=self.bundle["target_precommit"],
                subject_rows_raw=self.bundle["subjects"],
                subject_precommit_raw=self.bundle["precommit"],
                expected_raw_sha256={**self._pins(), "target_rows": contract.raw_sha256(b"[]\n")},
                **self._raws())

    def test_input_inventory_missing_extra_and_wrong_type_fail_closed(self) -> None:
        for mutate in (
            lambda raws: raws.pop("a_seed"),
            lambda raws: raws.__setitem__("unexpected", b"{}\n"),
            lambda raws: raws.__setitem__("a_seed", None),
        ):
            raws = self._raws()
            mutate(raws)
            with self.assertRaises(contract.P0PresentedAContextEventV2TargetPrecommitError):
                contract.validate_target_rows_bytes(
                    self.bundle["targets"], self.bundle["subjects"], self.bundle["precommit"],
                    **raws)  # type: ignore[arg-type]

    def test_manifest_literal_dependency_pin_and_producer_free_parent(self) -> None:
        self.assertEqual(contract.COMPONENT_MANIFEST, parent.EXPECTED_COMPONENT_MANIFEST)
        self.assertEqual(contract.COMPONENT_MANIFEST_SHA256, parent.EXPECTED_COMPONENT_MANIFEST_SHA256)
        self.assertEqual(parent.PREDECESSOR_COMPONENT_MANIFEST_SHA256,
                         "4f8e70e08f153886576fad2dbaa2a35e298a1e7438e58a047bdf00105a8f01b6")
        source = Path(parent.__file__).read_text(encoding="utf-8")
        self.assertNotIn("import p0_presented_a_context_annotation_event_v2_target_precommit_contract", source)
        self.assertNotIn("from llm_batch.grounding import p0_presented_a_context_annotation_event_v2", source)
        self.assertIn("p0_presented_a_context_annotation_subject_v2_precommit_parent_validator", source)
        receipt = self._parent()
        self.assertFalse(receipt["upstream_code_identity_verified"])
        self.assertFalse(receipt["same_process_monkeypatch_resistance_verified"])
        self.assertEqual(
            contract.COMPONENT_MANIFEST["validation_architecture"],
            "PRODUCER_FREE_COMPOSED_PARENT_DELEGATION",
        )
        self.assertEqual(contract.COMPONENT_MANIFEST["effective_raw_caps"], parent.EFFECTIVE_RAW_CAPS)

    def test_archived_packet_v1_inventory_and_runtime_references_remain_unchanged(self) -> None:
        self.assertEqual(len(old_packet.CHILD_FILES), 13)
        packet_source = Path(old_packet.__file__).read_text(encoding="utf-8")
        self.assertNotIn(contract.TARGET_SCHEMA, packet_source)
        self.assertNotIn(contract.PRECOMMIT_SCHEMA, packet_source)


if __name__ == "__main__":
    unittest.main()
