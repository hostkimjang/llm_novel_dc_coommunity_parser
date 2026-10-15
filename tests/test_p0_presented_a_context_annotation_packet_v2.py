"""Presented A-context annotation packet V2 envelope의 집중 회귀/공격 테스트."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import inspect
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from llm_batch.grounding import p0_actual_supervisor_execution_contract as old_supervisor
from llm_batch.grounding import p0_actual_owner_root_preauthorization as old_preauth
from llm_batch.grounding import p0_actual_packet_contract as old_packet
from llm_batch.grounding import p0_presented_a_context_annotation_packet_v2_contract as contract
from llm_batch.grounding import p0_presented_a_context_annotation_packet_v2_parent_validator as parent
from llm_batch.grounding import p0_presented_a_context_annotation_event_v2_target_precommit_parent_validator as target_parent
from tests import test_p0_presented_a_context_annotation_event_v2_target_precommit as target_fixture


CREATED_AT = "2026-09-02T00:00:13Z"


def _children() -> dict[str, bytes]:
    source = target_fixture._bundle()
    aliases = {"subject_rows": "subjects", "subject_precommit": "precommit", "target_rows": "targets"}
    return {role: source[role] if role in source else source[aliases[role]] for role in contract.CHILD_ROLES}


def _manifest(children: dict[str, bytes]) -> bytes:
    return contract.build_manifest_bytes(children, created_at=CREATED_AT)


def _pins(manifest: bytes, children: dict[str, bytes]) -> dict[str, str]:
    return {"packet_manifest": hashlib.sha256(manifest).hexdigest(),
            **{role: hashlib.sha256(raw).hexdigest() for role, raw in children.items()}}


def _obj(raw: bytes) -> dict[str, object]:
    return json.loads(raw)


def _reseal(row: dict[str, object]) -> bytes:
    return contract.canonical_file_bytes(contract.with_self_hash(row))


class PresentedAContextAnnotationPacketV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.children = _children()
        cls.manifest = _manifest(cls.children)
        cls.pins = _pins(cls.manifest, cls.children)

    def _parent(self, *, manifest: bytes | None = None,
                children: dict[str, bytes] | None = None,
                pins: dict[str, str] | None = None) -> dict[str, object]:
        use_manifest = self.manifest if manifest is None else manifest
        use_children = self.children if children is None else children
        return parent.validate_packet_manifest_against_raw_inputs(
            manifest_raw=use_manifest,
            expected_member_raw_sha256=self.pins if pins is None else pins,
            **use_children,
        )

    def test_positive_memory_only_15_child_16_member_envelope(self) -> None:
        manifest = contract.validate_manifest_bytes(self.manifest, self.children)
        receipt = self._parent()
        self.assertEqual(len(manifest["files"]), 15)
        self.assertEqual(len(contract.FIXED_MEMBER_CONTRACT), 16)
        self.assertEqual((manifest["input_raw_artifact_count"], manifest["output_raw_artifact_count"],
                          manifest["total_bound_raw_artifact_count"]), (13, 2, 15))
        self.assertEqual((manifest["fixed_child_count"], manifest["fixed_member_count"]), (15, 16))
        self.assertEqual((receipt["input_raw_artifact_count"], receipt["output_raw_artifact_count"],
                          receipt["total_bound_raw_artifact_count"]), (13, 2, 15))
        self.assertEqual((receipt["fixed_child_count"], receipt["fixed_member_count"]), (15, 16))
        self.assertTrue(receipt["target_parent_executed"])
        self.assertTrue(receipt["packet_envelope_independently_replayed"])
        self.assertFalse(receipt["target_replay_locally_verified"])
        self.assertEqual(receipt["receipt_sha256"], parent._digest(
            {key: value for key, value in receipt.items() if key != "receipt_sha256"}))

    def test_member_contract_binds_role_path_media_and_cap(self) -> None:
        self.assertEqual(contract.FIXED_MEMBER_CONTRACT, parent.FIXED_MEMBER_CONTRACT)
        self.assertEqual(contract.FIXED_MEMBER_CONTRACT_SHA256, parent.FIXED_MEMBER_CONTRACT_SHA256)
        self.assertEqual(contract.COMPONENT_MANIFEST_SHA256, parent.EXPECTED_COMPONENT_MANIFEST_SHA256)
        manifest = _obj(self.manifest)
        expected = [list(item) for item in contract.CHILD_FILES]
        actual = [[ref["role"], ref["path"], ref["media_type"], ref["max_bytes"]]
                  for ref in manifest["files"]]  # type: ignore[index]
        self.assertEqual(actual, expected)
        self.assertNotIn("packet_manifest", {ref["role"] for ref in manifest["files"]})  # type: ignore[index]
        for ref in manifest["files"]:  # type: ignore[index]
            self.assertEqual(set(ref), {"role", "path", "media_type", "max_bytes", "rows", "bytes", "sha256"})
            self.assertNotIn("/", ref["path"])
            self.assertNotIn("\\", ref["path"])
            self.assertNotIn("..", ref["path"])

    def test_producer_dependency_manifest_pin_drift_is_fatal(self) -> None:
        with patch.object(contract.target_contract, "COMPONENT_MANIFEST_SHA256", "0" * 64):
            with self.assertRaisesRegex(contract.P0PresentedAContextAnnotationPacketV2Error,
                                        "dependency component manifest pin"):
                contract.validate_manifest_bytes(self.manifest, self.children)

    def test_counts_status_taxonomy_and_all_authority_are_closed(self) -> None:
        row = _obj(self.manifest)
        receipt = self._parent()
        self.assertEqual(row["source_profile_counts"], {profile: 5 for profile in contract.SOURCE_PROFILES})
        self.assertEqual((row["generic_subject_count"], row["generic_target_count"]), (5, 5))
        self.assertEqual(row["terminal_status_counts"], {"JUDGED": 0, "UNJUDGED": 0, "UNAVAILABLE": 0})
        self.assertTrue(all(type(row[field]) is int and row[field] == 0 for field in contract.ZERO_COUNT_FIELDS))
        self.assertTrue(all(row[field] is False for field in contract.FALSE_FIELDS))
        self.assertEqual(row["response_schema_commitment_sha256"],
                         "3728334be85d5b53fd1b8f403c8471bad78817735271a301bab07590c063dd41")
        self.assertIs(row["iid_independence_assumed"], False)
        self.assertEqual(row["future_inferential_cluster_unit"], "UPSTREAM_SOURCE_FRAME_CANDIDATE_ID")
        self.assertEqual(row["statistical_denominator_contribution"], "NONE")
        self.assertEqual(row["operational_effect"], "NONE_SHADOW_ONLY")
        for field in contract.ZERO_COUNT_FIELDS:
            self.assertIs(type(receipt[field]), int)
            self.assertEqual(receipt[field], row[field])
        for field in contract.FALSE_FIELDS:
            self.assertIs(receipt[field], False)
            self.assertEqual(receipt[field], row[field])
        for field in (
            "source_profile_counts", "generic_subject_count", "generic_target_count",
            "terminal_status_counts", "response_schema_commitment_sha256",
            "statistical_denominator_contribution", "metric_status",
            "iid_independence_assumed", "future_inferential_cluster_unit",
        ):
            self.assertEqual(receipt[field], row[field])
        self.assertEqual(receipt["target_precommitted_at"],
                         _obj(self.children["target_precommit"])["precommitted_at"])
        self.assertEqual(receipt["packet_created_at"], row["created_at"])
        self.assertIs(receipt["target_precommit_strictly_precedes_packet_manifest_verified"], True)
        self.assertIs(receipt["event_or_result_child_allowed"], False)
        self.assertIs(receipt["predecessor_subject_parent_receipt_value_independently_verified"], False)

        target_rows = [json.loads(line) for line in self.children["target_rows"].splitlines()]
        self.assertEqual(len(target_rows), 20)
        self.assertTrue(all(item["initial_state"] == "NO_EVENT_RECORDED" for item in target_rows))
        for item in target_rows:
            self.assertTrue({"annotation_event", "annotation_result", "reviewer_id"}.isdisjoint(item))

    def test_external_16_pin_inventory_missing_extra_order_and_swapped_fail(self) -> None:
        variants: list[dict[str, str]] = []
        missing = dict(self.pins); missing.pop("a_plan"); variants.append(missing)
        extra = dict(self.pins); extra["result_rows"] = "0" * 64; variants.append(extra)
        reordered = {key: self.pins[key] for key in reversed(tuple(self.pins))}; variants.append(reordered)
        swapped = dict(self.pins)
        swapped["source_scope"], swapped["source_frame"] = swapped["source_frame"], swapped["source_scope"]
        variants.append(swapped)
        for attacked in variants:
            with self.subTest(keys=tuple(attacked)), self.assertRaises(
                    parent.P0PresentedAContextAnnotationPacketV2ParentError):
                self._parent(pins=attacked)

    def test_resealed_manifest_and_child_do_not_self_authorize(self) -> None:
        row = _obj(self.manifest)
        row["production_approval"] = True
        attacked_manifest = _reseal(row)
        attacked_pins = {**self.pins, "packet_manifest": hashlib.sha256(attacked_manifest).hexdigest()}
        with self.assertRaises(parent.P0PresentedAContextAnnotationPacketV2ParentError):
            self._parent(manifest=attacked_manifest, pins=attacked_pins)
        children = dict(self.children)
        children["target_rows"] += b"{}\n"
        attacked_pins = dict(self.pins)
        attacked_pins["target_rows"] = hashlib.sha256(children["target_rows"]).hexdigest()
        with self.assertRaises(parent.P0PresentedAContextAnnotationPacketV2ParentError):
            self._parent(children=children, pins=attacked_pins)

    def test_resealed_ref_path_role_media_cap_order_and_unknown_field_fail(self) -> None:
        mutations = (
            lambda files: files[0].__setitem__("path", "../escape.json"),
            lambda files: files[0].__setitem__("role", "source_frame"),
            lambda files: files[0].__setitem__("media_type", "text/plain"),
            lambda files: files[0].__setitem__("max_bytes", files[0]["max_bytes"] + 1),
            lambda files: files.reverse(),
            lambda files: files[0].__setitem__("optional", True),
        )
        for mutate in mutations:
            row = _obj(self.manifest)
            mutate(row["files"])  # type: ignore[arg-type]
            attacked = _reseal(row)
            with self.subTest(mutation=mutate), self.assertRaises(
                    contract.P0PresentedAContextAnnotationPacketV2Error):
                contract.validate_manifest_bytes(attacked, self.children)

    def test_resealed_bool_integer_confusion_fails_closed(self) -> None:
        for field, value in (("production_approval", 0), ("reviewer_count", False),
                             ("fixed_member_count", True)):
            row = _obj(self.manifest)
            row[field] = value
            attacked = _reseal(row)
            with self.subTest(field=field), self.assertRaises(
                    contract.P0PresentedAContextAnnotationPacketV2Error):
                contract.validate_manifest_bytes(attacked, self.children)
        for field, key, value in (
            ("terminal_status_counts", "JUDGED", False),
            ("source_profile_counts", "GENERIC_FALLBACK", True),
        ):
            row = _obj(self.manifest)
            row[field][key] = value
            attacked = _reseal(row)
            with self.subTest(field=field, key=key), self.assertRaises(
                    contract.P0PresentedAContextAnnotationPacketV2Error):
                contract.validate_manifest_bytes(attacked, self.children)

    def test_manifest_and_child_cap_reject_before_hash_or_decode(self) -> None:
        huge_manifest = b"x" * (contract.MAX_MANIFEST_BYTES + 1)
        with patch.object(contract.hashlib, "sha256", side_effect=AssertionError("hash reached")):
            with self.assertRaisesRegex(contract.P0PresentedAContextAnnotationPacketV2Error, "cap"):
                contract.validate_manifest_bytes(huge_manifest, self.children)
        with patch.object(parent.hashlib, "sha256", side_effect=AssertionError("hash reached")):
            with self.assertRaisesRegex(parent.P0PresentedAContextAnnotationPacketV2ParentError, "cap"):
                self._parent(manifest=huge_manifest)
        children = dict(self.children)
        children["source_seed"] = b"x" * (contract.EFFECTIVE_RAW_CAPS["source_seed"] + 1)
        with patch.object(contract.hashlib, "sha256", side_effect=AssertionError("hash reached")):
            with self.assertRaisesRegex(contract.P0PresentedAContextAnnotationPacketV2Error, "cap"):
                contract.build_manifest_bytes(children, created_at=CREATED_AT)

    def test_strict_timestamp_and_chronology(self) -> None:
        for timestamp in ("2026-09-02 00:00:13+00:00", "2026-09-02T00:00:13"):
            with self.subTest(timestamp=timestamp), self.assertRaisesRegex(
                    contract.P0PresentedAContextAnnotationPacketV2Error, "strict RFC3339|timezone"):
                contract.build_manifest_bytes(self.children, created_at=timestamp)
        target_time = _obj(self.children["target_precommit"])["precommitted_at"]
        with self.assertRaisesRegex(contract.P0PresentedAContextAnnotationPacketV2Error, "strictly precede"):
            contract.build_manifest_bytes(self.children, created_at=target_time)  # type: ignore[arg-type]
        pins = {role: hashlib.sha256(raw).hexdigest() for role, raw in self.children.items()}
        precommit = contract._validated_target(self.children)
        attacked_manifest = contract.canonical_file_bytes(contract._manifest_value(
            self.children, pins, created_at=target_time, target_precommit=precommit,
        ))
        attacked_pins = _pins(attacked_manifest, self.children)
        with self.assertRaisesRegex(contract.P0PresentedAContextAnnotationPacketV2Error,
                                    "strictly precede"):
            contract.validate_manifest_bytes(attacked_manifest, self.children)
        with self.assertRaisesRegex(parent.P0PresentedAContextAnnotationPacketV2ParentError,
                                    "strictly precede"):
            self._parent(manifest=attacked_manifest, pins=attacked_pins)

    def test_forged_target_parent_receipt_is_rejected_after_single_call(self) -> None:
        child_pins = {role: self.pins[role] for role in contract.CHILD_ROLES}
        genuine = target_parent.validate_target_precommit_against_raw_inputs(
            target_rows_raw=self.children["target_rows"], target_precommit_raw=self.children["target_precommit"],
            subject_rows_raw=self.children["subject_rows"], subject_precommit_raw=self.children["subject_precommit"],
            expected_raw_sha256=child_pins,
            **{role: self.children[role] for role in contract.CHILD_ROLES[:11]},
        )
        for field, value in (("actual_authority_granted", True), ("target_count", True),
                             ("actual_a_context_review_count", False),
                             ("iid_independence_assumed", 0),
                             ("statistical_denominator_contribution", False),
                             ("target_wiring_applied", 0),
                             ("predecessor_parent_module", "forged.module")):
            forged = deepcopy(genuine)
            forged[field] = value
            forged["receipt_sha256"] = parent._digest(
                {key: item for key, item in forged.items() if key != "receipt_sha256"})
            with patch.object(parent.target_parent, "validate_target_precommit_against_raw_inputs",
                              return_value=forged) as mocked:
                with self.subTest(field=field), self.assertRaisesRegex(
                        parent.P0PresentedAContextAnnotationPacketV2ParentError, "semantic"):
                    self._parent()
                mocked.assert_called_once()

    def test_forged_target_parent_nested_raw_map_type_and_order_are_rejected(self) -> None:
        class EvilDict(dict[str, str]):
            def __ne__(self, other: object) -> bool:
                return False

        child_pins = {role: self.pins[role] for role in contract.CHILD_ROLES}
        genuine = target_parent.validate_target_precommit_against_raw_inputs(
            target_rows_raw=self.children["target_rows"], target_precommit_raw=self.children["target_precommit"],
            subject_rows_raw=self.children["subject_rows"], subject_precommit_raw=self.children["subject_precommit"],
            expected_raw_sha256=child_pins,
            **{role: self.children[role] for role in contract.CHILD_ROLES[:11]},
        )
        nested_variants = (
            EvilDict({"forged": "0" * 64}),
            {role: child_pins[role] for role in reversed(contract.CHILD_ROLES)},
        )
        for nested in nested_variants:
            forged = dict(genuine)
            forged["validated_raw_sha256"] = nested
            forged["receipt_sha256"] = parent._digest(
                {key: value for key, value in forged.items() if key != "receipt_sha256"}
            )
            with patch.object(parent.target_parent, "validate_target_precommit_against_raw_inputs",
                              return_value=forged):
                with self.subTest(kind=type(nested).__name__), self.assertRaisesRegex(
                        parent.P0PresentedAContextAnnotationPacketV2ParentError,
                        "raw map exact ordered inventory"):
                    self._parent()

    def test_opaque_predecessor_receipt_value_is_not_overclaimed(self) -> None:
        child_pins = {role: self.pins[role] for role in contract.CHILD_ROLES}
        genuine = target_parent.validate_target_precommit_against_raw_inputs(
            target_rows_raw=self.children["target_rows"], target_precommit_raw=self.children["target_precommit"],
            subject_rows_raw=self.children["subject_rows"], subject_precommit_raw=self.children["subject_precommit"],
            expected_raw_sha256=child_pins,
            **{role: self.children[role] for role in contract.CHILD_ROLES[:11]},
        )
        forged = dict(genuine)
        forged["predecessor_subject_parent_receipt_sha256"] = "0" * 64
        forged["receipt_sha256"] = parent._digest(
            {key: value for key, value in forged.items() if key != "receipt_sha256"}
        )
        with patch.object(parent.target_parent, "validate_target_precommit_against_raw_inputs",
                          return_value=forged):
            receipt = self._parent()
        self.assertIs(receipt["predecessor_subject_parent_receipt_value_independently_verified"], False)
        self.assertIs(receipt["same_process_monkeypatch_resistance_verified"], False)

    def test_layers_do_not_import_wrong_code_or_add_io(self) -> None:
        producer_source = inspect.getsource(contract)
        parent_source = inspect.getsource(parent)
        self.assertIn("target_precommit_contract as target_contract", producer_source)
        self.assertNotIn("target_precommit_parent_validator", producer_source)
        self.assertIn("target_precommit_parent_validator as target_parent", parent_source)
        self.assertNotIn("import p0_presented_a_context_annotation_packet_v2_contract", parent_source)
        for source in (producer_source, parent_source):
            self.assertNotIn("from pathlib", source)
            self.assertNotIn("open(", source)
            self.assertNotIn("write_bytes", source)

    def test_v1_fixed_point_is_unchanged_and_has_no_v2_reference(self) -> None:
        self.assertEqual(len(old_packet.CHILD_FILES), 13)
        self.assertEqual(old_packet.PACKET_MANIFEST_FILENAME, "p0_actual_keyless_pilot_manifest_v1.json")
        self.assertEqual(len(old_preauth.FIXED_MEMBER_CONTRACT), 14)
        self.assertEqual(old_preauth.FIXED_MEMBER_CONTRACT_SHA256,
                         "72189ac02f34f100c5d07e62f1acccb3a86f79756f3381e57dba637341012256")
        self.assertEqual(len(old_supervisor._STEP_SPECS), 4)
        roots = (Path(old_packet.__file__), Path(old_preauth.__file__), Path(old_supervisor.__file__))
        self.assertFalse(any("annotation_packet_v2" in path.read_text(encoding="utf-8") for path in roots))


if __name__ == "__main__":
    unittest.main()
