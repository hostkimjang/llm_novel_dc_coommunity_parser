from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from types import MappingProxyType
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from llm_batch.grounding import p0_actual_authority_contract as authority  # noqa: E402
from llm_batch.grounding import p0_actual_authority_event_bytes as event_bytes  # noqa: E402
from llm_batch.grounding import p0_actual_authority_raw_execution as execution  # noqa: E402
from llm_batch.grounding import p0_actual_registry_contract as registry  # noqa: E402


AUTHORITY_DIR = (
    REPO_ROOT / "tests" / "fixtures" / "p0_actual_authority_contract_example_v2"
)
FOUNDATION_DIR = (
    REPO_ROOT / "tests" / "fixtures" / "p0_actual_contract_example_v1"
)
EVENT_PATH = FOUNDATION_DIR / "p0_annotation_events_example_v1.jsonl"

EXPECTED_AUTHORITY_MANIFEST_SHA256 = (
    "1a6e4af406dc687e5335773a443987703be0669478e4c4671bfe705f827985ed"
)
EXPECTED_FINAL_ATTESTATION_SHA256 = (
    "b21e0e6ee2c180568d78bbda3602fccfad838c0ae873b67bdc4343e0146f9a5b"
)
EXPECTED_FOUNDATION_RECEIPT_SHA256 = (
    "3f692bc338dfecf9f7f721c4872c6240e2b6817a88d42e7957e84f4855df2d35"
)
EXPECTED_EVENT_RECEIPT_SHA256 = (
    "d62553a2042902b65403543e265fff3b65604dedc73615ff9306598971082dbe"
)
EXPECTED_RAW_EXECUTION_RECEIPT_SHA256 = (
    "fc1240559c2cbb639c12e248ecf8dd7e5c2a6bd5fd88bb2780f420bd7e6fc882"
)


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _rehash(value: dict[str, object]) -> dict[str, object]:
    material = {key: item for key, item in value.items() if key != "receipt_sha256"}
    return {**material, "receipt_sha256": _canonical_sha256(material)}


class P0ActualAuthorityRawExecutionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw_by_filename = {
            basename: (AUTHORITY_DIR / basename).read_bytes()
            for basename in authority.AUTHORITY_EXAMPLE_FILES_V2.values()
        }
        cls.event_raw = EVENT_PATH.read_bytes()
        manifest = json.loads(
            (FOUNDATION_DIR / "p0_actual_contract_example_manifest_v1.json").read_text(
                encoding="utf-8"
            )
        )
        cls.foundation_manifest_sha256 = manifest["manifest_sha256"]
        cls.foundation_receipt_sha256 = registry.validate_example_directory(
            FOUNDATION_DIR
        )["receipt_sha256"]

    def setUp(self) -> None:
        self.raw = dict(self.raw_by_filename)

    def _execute(self, **kwargs: object) -> dict[str, object]:
        arguments: dict[str, object] = {
            "authority_raw_by_filename": self.raw,
            "annotation_event_bytes": self.event_raw,
            "expected_authority_origin": authority.EXAMPLE_ORIGIN,
            "expected_event_origin": registry.EXAMPLE_ORIGIN,
            "foundation_manifest_sha256": self.foundation_manifest_sha256,
            "foundation_receipt_sha256": self.foundation_receipt_sha256,
        }
        arguments.update(kwargs)
        return execution.execute_authority_raw_validation(**arguments)

    def _execute_state(self, **kwargs: object):
        arguments: dict[str, object] = {
            "authority_raw_by_filename": self.raw,
            "annotation_event_bytes": self.event_raw,
            "expected_authority_origin": authority.EXAMPLE_ORIGIN,
            "expected_event_origin": registry.EXAMPLE_ORIGIN,
            "foundation_manifest_sha256": self.foundation_manifest_sha256,
            "foundation_receipt_sha256": self.foundation_receipt_sha256,
        }
        arguments.update(kwargs)
        return execution._execute_authority_raw_validation_state(**arguments)

    def test_direct_execution_binds_exact_raw_inventory_and_remains_no_go(self) -> None:
        receipt = self._execute()
        self.assertEqual(14, receipt["authority_raw_member_count"])
        self.assertEqual(
            list(execution.AUTHORITY_FILE_ROLES),
            [
                (row["role"], row["path"])
                for row in receipt["authority_raw_member_projection"]
            ],
        )
        for row in receipt["authority_raw_member_projection"]:
            raw = self.raw[row["path"]]
            self.assertEqual(len(raw), row["bytes"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row["sha256"])
        self.assertTrue(receipt["foundation_validator_invoked_directly"])
        self.assertTrue(receipt["annotation_event_bytes_validator_invoked_directly"])
        self.assertTrue(receipt["local_direct_validator_invocations_observed"])
        self.assertTrue(receipt["untrusted_local_execution_observation"])
        self.assertFalse(receipt["caller_self_code_measurement_verified"])
        self.assertFalse(receipt["external_owner_trust_verified"])
        self.assertFalse(receipt["runtime_noninterference_verified"])
        self.assertFalse(receipt["owner_authority_verified"])
        self.assertFalse(receipt["actual_authority_granted"])
        self.assertEqual(0, receipt["credited_actual_source_claim_count"])
        self.assertEqual(0, receipt["credited_actual_a_context_review_count"])
        self.assertFalse(receipt["p0_phase_exit"])
        self.assertFalse(receipt["production_approval"])
        self.assertFalse(receipt["full_scan_approval"])
        self.assertFalse(receipt["action_applied"])
        self.assertEqual(execution.GATE_STATUS, receipt["gate_status"])

    def test_frozen_authority_and_event_receipt_hashes_regress(self) -> None:
        receipt = self._execute()
        foundation = receipt["foundation_result_projection"]
        event = receipt["event_result_projection"]
        self.assertEqual(
            EXPECTED_AUTHORITY_MANIFEST_SHA256, foundation["manifest_sha256"]
        )
        self.assertEqual(
            EXPECTED_FINAL_ATTESTATION_SHA256,
            foundation["final_attestation_sha256"],
        )
        self.assertEqual(
            EXPECTED_FOUNDATION_RECEIPT_SHA256, foundation["receipt_sha256"]
        )
        self.assertEqual(EXPECTED_EVENT_RECEIPT_SHA256, event["receipt_sha256"])
        self.assertEqual(EXPECTED_RAW_EXECUTION_RECEIPT_SHA256, receipt["receipt_sha256"])

    def test_noncanonical_fixture_json_is_not_rewritten_or_rejected(self) -> None:
        target = authority.AUTHORITY_EXAMPLE_FILES_V2["manifest"]
        raw = self.raw[target]
        parsed = json.loads(raw.decode("utf-8"))
        canonical = json.dumps(
            parsed,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.assertNotEqual(raw, canonical)
        receipt = self._execute()
        projection = next(
            row
            for row in receipt["authority_raw_member_projection"]
            if row["role"] == "manifest"
        )
        self.assertEqual(hashlib.sha256(raw).hexdigest(), projection["sha256"])

    def test_invalid_utf8_duplicate_key_and_nonfinite_json_fail_closed(self) -> None:
        target = authority.AUTHORITY_EXAMPLE_FILES_V2["owner_anchor"]
        variants = {
            "strict UTF-8": self.raw[target] + b"\xff",
            "duplicate JSON key": self.raw[target].replace(
                b'"schema_version"',
                b'"schema_version":"duplicate","schema_version"',
                1,
            ),
            "non-finite constant": self.raw[target].replace(
                b'"action_applied":false', b'"action_applied":NaN', 1
            ),
        }
        for message, raw in variants.items():
            with self.subTest(message=message):
                self.raw[target] = raw
                with self.assertRaisesRegex(
                    execution.P0ActualAuthorityRawExecutionError, message
                ):
                    self._execute()
                self.raw[target] = self.raw_by_filename[target]

    def test_bom_trailing_json_and_non_object_fail_closed(self) -> None:
        target = authority.AUTHORITY_EXAMPLE_FILES_V2["owner_anchor"]
        variants = (
            b"\xef\xbb\xbf" + self.raw[target],
            self.raw[target] + b"{}",
            b"[]",
        )
        for raw in variants:
            with self.subTest(raw=raw[:8]):
                self.raw[target] = raw
                with self.assertRaises(execution.P0ActualAuthorityRawExecutionError):
                    self._execute()
                self.raw[target] = self.raw_by_filename[target]

    def test_missing_extra_and_serialized_result_member_are_rejected(self) -> None:
        missing = dict(self.raw)
        missing.pop(next(iter(missing)))
        extra = {**self.raw, "unexpected.json": b"{}"}
        injected = {**self.raw, "authority_foundation_receipt.json": b"{}"}
        non_string = {**self.raw, 7: b"{}"}
        for label, value in (
            ("missing", missing),
            ("extra", extra),
            ("serialized-result", injected),
            ("non-string-filename", non_string),
        ):
            with self.subTest(label=label), self.assertRaises(
                execution.P0ActualAuthorityRawExecutionError
            ):
                self._execute(authority_raw_by_filename=value)

    def test_executor_metadata_cannot_carry_nested_result_injection(self) -> None:
        attacks = (
            {"observed_at": {"actual_authority_granted": True}},
            {"key": {"owner_authority_verified": True}},
            {"expected_external_anchor_sha256": {"p0_phase_exit": True}},
        )
        for attack in attacks:
            with self.subTest(attack=attack), self.assertRaises(
                execution.P0ActualAuthorityRawExecutionError
            ):
                self._execute(**attack)

    def test_role_filename_swap_is_rejected_by_direct_foundation_validator(self) -> None:
        anchor = authority.AUTHORITY_EXAMPLE_FILES_V2["owner_anchor"]
        policies = authority.AUTHORITY_EXAMPLE_FILES_V2["policy_refs"]
        self.raw[anchor], self.raw[policies] = self.raw[policies], self.raw[anchor]
        with self.assertRaises(authority.P0ActualAuthorityError):
            self._execute()

    def test_checkpoint_and_head_map_role_swaps_fail_closed(self) -> None:
        swaps = (
            ("predecessor_checkpoint", "current_checkpoint"),
            ("predecessor_head_map", "head_map"),
        )
        for left_role, right_role in swaps:
            left = authority.AUTHORITY_EXAMPLE_FILES_V2[left_role]
            right = authority.AUTHORITY_EXAMPLE_FILES_V2[right_role]
            self.raw[left], self.raw[right] = self.raw[right], self.raw[left]
            with self.subTest(left=left_role, right=right_role), self.assertRaises(
                authority.P0ActualAuthorityError
            ):
                self._execute()
            self.raw = dict(self.raw_by_filename)

    def test_foundation_result_authority_injection_is_rejected(self) -> None:
        original = authority.validate_authority_foundation_bundle

        def injected(**kwargs: object) -> dict[str, object]:
            result = original(**kwargs)
            result["owner_authority_verified"] = True
            return _rehash(result)

        with mock.patch.object(
            authority, "validate_authority_foundation_bundle", new=injected
        ), self.assertRaisesRegex(
            execution.P0ActualAuthorityRawExecutionError,
            "overclaims owner_authority_verified",
        ):
            self._execute()

    def test_foundation_result_extra_field_injection_is_rejected(self) -> None:
        original = authority.validate_authority_foundation_bundle

        def injected(**kwargs: object) -> dict[str, object]:
            result = original(**kwargs)
            result["execution_verified"] = True
            return _rehash(result)

        with mock.patch.object(
            authority, "validate_authority_foundation_bundle", new=injected
        ), self.assertRaisesRegex(
            execution.P0ActualAuthorityRawExecutionError,
            "foundation validator result fields mismatch",
        ):
            self._execute()

    def test_foundation_result_schema_origin_and_gate_injections_are_rejected(self) -> None:
        original = authority.validate_authority_foundation_bundle
        variants = (
            ("schema_version", "p0_actual_authority_foundation_receipt_v999"),
            ("record_origin", authority.ACTUAL_ORIGIN),
            ("gate_status", "GO_ACTUAL_P0"),
            ("actual_gate_status", "GO_ACTUAL_P0"),
            ("authority", "OWNER_VERIFIED"),
        )
        for field, value in variants:
            def injected(**kwargs: object) -> dict[str, object]:
                result = original(**kwargs)
                result[field] = value
                return _rehash(result)

            with self.subTest(field=field), mock.patch.object(
                authority, "validate_authority_foundation_bundle", new=injected
            ), self.assertRaises(execution.P0ActualAuthorityRawExecutionError):
                self._execute()

    def test_event_result_swap_is_rejected_even_when_self_rehashed(self) -> None:
        original = event_bytes.verify_annotation_event_bytes_from_bytes

        def swapped(**kwargs: object) -> dict[str, object]:
            result = original(**kwargs)
            result["event_file_sha256"] = "f" * 64
            return _rehash(result)

        with mock.patch.object(
            event_bytes, "verify_annotation_event_bytes_from_bytes", new=swapped
        ), self.assertRaisesRegex(
            execution.P0ActualAuthorityRawExecutionError,
            "event validator result/raw input cross-binding mismatch",
        ):
            self._execute()

    def test_event_result_schema_gate_effect_and_bool_count_injections_fail(self) -> None:
        original = event_bytes.verify_annotation_event_bytes_from_bytes
        variants = (
            ("schema_version", "p0_actual_annotation_event_bytes_receipt_v999"),
            ("gate_status", "GO_ACTUAL_P0"),
            ("operational_effect", "PRODUCTION_WRITE"),
            ("event_row_count", True),
            ("predecessor_prefix_rows", True),
        )
        for field, value in variants:
            def injected(**kwargs: object) -> dict[str, object]:
                result = original(**kwargs)
                result[field] = value
                return _rehash(result)

            with self.subTest(field=field), mock.patch.object(
                event_bytes,
                "verify_annotation_event_bytes_from_bytes",
                new=injected,
            ), self.assertRaises(execution.P0ActualAuthorityRawExecutionError):
                self._execute()

    def test_raw_event_tamper_is_rejected_by_direct_event_validator(self) -> None:
        with self.assertRaises(authority.P0ActualAuthorityError):
            self._execute(annotation_event_bytes=self.event_raw + b"\n")

    def test_presented_receipt_is_structure_only_and_drops_execution(self) -> None:
        receipt = self._execute()
        validation = execution.validate_presented_authority_raw_execution_receipt(
            receipt
        )
        self.assertTrue(validation["presented_receipt_structurally_verified"])
        self.assertFalse(validation["local_direct_validator_invocations_observed"])
        self.assertFalse(validation["underlying_validator_execution_verified"])
        self.assertFalse(validation["external_owner_trust_verified"])
        self.assertFalse(validation["actual_authority_granted"])
        self.assertFalse(validation["p0_phase_exit"])
        self.assertEqual(execution.GATE_STATUS, validation["gate_status"])

    def test_presented_receipt_capability_and_projection_injections_fail(self) -> None:
        base = self._execute()
        capability = deepcopy(base)
        capability["actual_authority_granted"] = True
        capability = _rehash(capability)
        projection = deepcopy(base)
        projection["authority_raw_member_projection"][0]["role"] = "manifest"
        projection["authority_raw_member_projection_sha256"] = _canonical_sha256(
            projection["authority_raw_member_projection"]
        )
        projection = _rehash(projection)
        event_swap = deepcopy(base)
        event_swap["event_result_projection"]["event_file_sha256"] = "f" * 64
        event_swap = _rehash(event_swap)
        for label, receipt in (
            ("capability", capability),
            ("projection", projection),
            ("event-swap", event_swap),
        ):
            with self.subTest(label=label), self.assertRaises(
                execution.P0ActualAuthorityRawExecutionError
            ):
                execution.validate_presented_authority_raw_execution_receipt(receipt)

    def test_private_state_is_recursively_immutable_and_not_exported(self) -> None:
        state = self._execute_state()
        self.assertIsInstance(state.raw_by_filename, MappingProxyType)
        self.assertIsInstance(state.parsed_rows, MappingProxyType)
        self.assertIsInstance(state.parsed_rows["manifest"], MappingProxyType)
        self.assertIsInstance(state.foundation_result, MappingProxyType)
        self.assertIsInstance(state.foundation_result["blockers"], tuple)
        self.assertIsInstance(state.event_result, MappingProxyType)
        self.assertIsInstance(state.public_receipt, MappingProxyType)
        self.assertIsInstance(
            state.public_receipt["authority_raw_member_projection"], tuple
        )
        mutations = (
            lambda: state.raw_by_filename.__setitem__("injected", b"{}"),
            lambda: state.parsed_rows["manifest"].__setitem__(
                "p0_phase_exit", True
            ),
            lambda: state.foundation_result.__setitem__(
                "owner_authority_verified", True
            ),
            lambda: state.event_result.__setitem__("gate_status", "GO"),
            lambda: state.public_receipt.__setitem__("production_approval", True),
        )
        for mutate in mutations:
            with self.assertRaises((AttributeError, TypeError)):
                mutate()
        self.assertNotIn("_AuthorityRawExecutionState", execution.__all__)
        self.assertNotIn("_execute_authority_raw_validation_state", execution.__all__)

    def test_public_receipt_is_detached_and_private_executor_rejects_injection_args(self) -> None:
        first = self._execute()
        self.assertIs(type(first), dict)
        self.assertIs(type(first["authority_raw_member_projection"]), list)
        self.assertIs(type(first["authority_raw_member_projection"][0]), dict)
        frozen_sha = first["receipt_sha256"]
        first["actual_authority_granted"] = True
        first["foundation_result_projection"]["gate_status"] = "GO"
        first["authority_raw_member_projection"][0]["role"] = "injected"
        second = self._execute()
        self.assertEqual(frozen_sha, second["receipt_sha256"])
        self.assertFalse(second["actual_authority_granted"])
        self.assertEqual(
            "NO_GO_ACTUAL_P0_NOT_STARTED",
            second["foundation_result_projection"]["gate_status"],
        )
        self.assertEqual("owner_anchor", second["authority_raw_member_projection"][0]["role"])

        state = self._execute_state()
        target = authority.AUTHORITY_EXAMPLE_FILES_V2["manifest"]
        original_raw = state.raw_by_filename[target]
        self.raw[target] = b"{}"
        self.assertEqual(original_raw, state.raw_by_filename[target])
        for field in ("foundation_result", "event_result", "parsed_rows", "state"):
            with self.subTest(field=field), self.assertRaises(TypeError):
                self._execute_state(**{field: {"actual_authority_granted": True}})


if __name__ == "__main__":
    unittest.main()
