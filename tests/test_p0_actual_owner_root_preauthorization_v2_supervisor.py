from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import inspect
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from llm_batch.grounding import p0_actual_owner_root_preauthorization_v2_supervisor as candidate


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def reseal(row: dict[str, object]) -> dict[str, object]:
    material = dict(row)
    material.pop("receipt_sha256", None)
    return {**material, "receipt_sha256": digest(material)}


class IntSubclass(int):
    pass


class DictSubclass(dict):
    pass


class SupervisorV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.packet_dir = Path("presented-packet-v2")
        self.pin_bytes = b'{"pin":"presented"}\n'
        self.body_bytes = b'{"preauthorization":"presented"}\n'
        self.envelope_bytes = b'{"signature":"presented"}\n'
        self.observed_at = "2026-09-03T01:30:00Z"
        self.child = self._child_receipt()

    def _child_receipt(self) -> dict[str, object]:
        string_fields = (
            set(candidate._CHILD_RECEIPT_FIELDS)
            - set(candidate._CHILD_TRUE_FIELDS)
            - set(candidate._CHILD_FALSE_FIELDS)
            - {
                "key_epoch",
                "credited_actual_source_claim_count",
                "credited_actual_a_context_review_count",
                "receipt_sha256",
            }
        )
        values: dict[str, object] = {}
        for field in candidate._CHILD_RECEIPT_FIELDS:
            if field in string_fields:
                values[field] = "fixture-value"
        for field in tuple(values):
            if field.endswith("_sha256"):
                values[field] = "ab" * 32
        values.update(
            {
                "schema_version": candidate.PREAUTHORIZATION_RECEIPT_SCHEMA,
                "preauthorization_component_manifest_sha256": (
                    candidate.PREAUTHORIZATION_COMPONENT_MANIFEST_SHA256
                ),
                "windows_component_manifest_sha256": (
                    candidate.WINDOWS_COMPONENT_MANIFEST_SHA256
                ),
                "packet_component_manifest_sha256": (
                    candidate.PACKET_COMPONENT_MANIFEST_SHA256
                ),
                "fixed_member_contract_sha256": (
                    candidate.FIXED_MEMBER_CONTRACT_SHA256
                ),
                "public_key_pin_bytes_sha256": hashlib.sha256(
                    self.pin_bytes
                ).hexdigest(),
                "preauthorization_bytes_sha256": hashlib.sha256(
                    self.body_bytes
                ).hexdigest(),
                "signature_envelope_bytes_sha256": hashlib.sha256(
                    self.envelope_bytes
                ).hexdigest(),
                "observed_at": self.observed_at,
                "key_epoch": 7,
                **{field: True for field in candidate._CHILD_TRUE_FIELDS},
                **{field: False for field in candidate._CHILD_FALSE_FIELDS},
                "credited_actual_source_claim_count": 0,
                "credited_actual_a_context_review_count": 0,
                "operational_effect": candidate.PREAUTHORIZATION_OPERATIONAL_EFFECT,
                "gate_status": candidate.PREAUTHORIZATION_GATE_STATUS,
            }
        )
        material = {field: values[field] for field in candidate._CHILD_RECEIPT_FIELDS[:-1]}
        return {**material, "receipt_sha256": digest(material)}

    @contextmanager
    def _patched_child(
        self,
        *,
        result: object | None = None,
        error: Exception | None = None,
    ):
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        original = getattr(candidate.preauth_v2, candidate.PREAUTHORIZATION_PUBLIC_API)

        def fake(*args: object, **kwargs: object) -> object:
            calls.append((args, kwargs))
            if error is not None:
                raise error
            return self.child if result is None else result

        fake.__name__ = original.__name__
        fake.__module__ = original.__module__
        fake.__wrapped__ = original  # type: ignore[attr-defined]
        with patch.object(
            candidate.preauth_v2,
            candidate.PREAUTHORIZATION_PUBLIC_API,
            new=fake,
        ):
            yield calls

    def _execute(self, child: object | None = None) -> tuple[dict[str, object], list]:
        with self._patched_child(result=child) as calls:
            receipt = candidate.execute_owner_root_preauthorization_v2_supervisor_windows(
                self.packet_dir,
                public_key_pin_bytes=self.pin_bytes,
                preauthorization_bytes=self.body_bytes,
                signature_envelope_bytes=self.envelope_bytes,
                observed_at=self.observed_at,
            )
        return receipt, calls

    @staticmethod
    def _step_kwargs(step: dict[str, object]) -> dict[str, str]:
        return {
            "raw_input_binding_sha256": step["raw_input_binding_sha256"],
            "child_receipt_declared_sha256": step[
                "child_receipt_declared_sha256"
            ],
            "child_receipt_full_sha256": step["child_receipt_full_sha256"],
            "child_safe_projection_sha256": step[
                "child_safe_projection_sha256"
            ],
            "child_truth_table_projection_sha256": step[
                "child_truth_table_projection_sha256"
            ],
        }  # type: ignore[return-value]

    def test_positive_exact_one_call_and_bounded_receipt(self) -> None:
        receipt, calls = self._execute()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], (self.packet_dir,))
        self.assertEqual(
            calls[0][1],
            {
                "public_key_pin_bytes": self.pin_bytes,
                "preauthorization_bytes": self.body_bytes,
                "signature_envelope_bytes": self.envelope_bytes,
                "observed_at": self.observed_at,
            },
        )
        self.assertEqual(tuple(receipt), candidate._RECEIPT_FIELDS)
        material = dict(receipt)
        declared = material.pop("receipt_sha256")
        self.assertEqual(declared, digest(material))
        for field in candidate._SUPERVISOR_TRUE_FIELDS:
            self.assertIs(receipt[field], True, field)
        for field in candidate._SUPERVISOR_FALSE_FIELDS:
            self.assertIs(receipt[field], False, field)
        self.assertEqual(receipt["execution_step_count"], 1)
        self.assertEqual(receipt["preauthorization_execution_count"], 1)
        self.assertEqual(receipt["direct_windows_execution_count"], 0)
        self.assertEqual(receipt["packet_dir_input_kind"], "PATH")
        self.assertEqual(
            receipt["packet_dir_lexical_utf8_sha256"],
            hashlib.sha256(str(self.packet_dir).encode("utf-8")).hexdigest(),
        )
        self.assertEqual(receipt["credited_actual_source_claim_count"], 0)
        self.assertEqual(receipt["credited_actual_a_context_review_count"], 0)
        self.assertNotIn("public_key_pin_artifact_sha256", receipt)
        self.assertNotEqual(receipt["child_safe_projection"], self.child)
        safe = receipt["child_safe_projection"]
        self.assertIs(type(safe), dict)
        self.assertEqual(tuple(safe), candidate._CHILD_SAFE_FIELDS)
        self.assertEqual(receipt["child_safe_projection_sha256"], safe["receipt_sha256"])
        step = receipt["execution_step_receipt"]
        self.assertIs(type(step), dict)
        self.assertEqual(tuple(step), candidate._STEP_RECEIPT_FIELDS)
        self.assertEqual(step["ordinal"], 0)
        self.assertEqual(step["operation"], candidate.EXECUTION_STEP)
        self.assertEqual(step["preauthorization_execution_count"], 1)
        self.assertEqual(step["direct_windows_execution_count"], 0)
        self.assertEqual(
            receipt["execution_step_receipt_declared_sha256"],
            step["receipt_sha256"],
        )
        self.assertEqual(
            receipt["execution_step_receipt_full_sha256"], digest(step)
        )

    def test_public_api_dependency_identity_and_manifest_hash_are_fixed(self) -> None:
        self.assertEqual(
            candidate.__all__,
            ["execute_owner_root_preauthorization_v2_supervisor_windows"],
        )
        self.assertEqual(
            tuple(
                inspect.signature(
                    candidate.execute_owner_root_preauthorization_v2_supervisor_windows
                ).parameters
            ),
            (
                "packet_dir",
                "public_key_pin_bytes",
                "preauthorization_bytes",
                "signature_envelope_bytes",
                "observed_at",
            ),
        )
        self.assertEqual(len(candidate._CHILD_RECEIPT_FIELDS), 88)
        self.assertEqual(
            candidate.COMPONENT_MANIFEST_SHA256,
            digest(candidate.COMPONENT_MANIFEST),
        )
        self.assertEqual(
            candidate.COMPONENT_MANIFEST_SHA256,
            "239b595763bf1bef0d5ab925d51f864f1c1c3090123f6ca540a225e4f9c4fddf",
        )
        self.assertEqual(
            candidate.PREAUTHORIZATION_COMPONENT_MANIFEST_SHA256,
            "07ae0af427112978ba3cb5f5a0ae8713a25837cbb9ae65ac0b7993da7d44876e",
        )

    def test_exact_input_type_cap_and_observed_at_precheck_have_zero_calls(self) -> None:
        class BytesSubclass(bytes):
            pass

        cases = (
            {"public_key_pin_bytes": b""},
            {"public_key_pin_bytes": BytesSubclass(self.pin_bytes)},
            {"public_key_pin_bytes": b"x" * (candidate._MAX_PIN_BYTES + 1)},
            {"preauthorization_bytes": b"x" * (candidate._MAX_PREAUTHORIZATION_BYTES + 1)},
            {"signature_envelope_bytes": b"x" * (candidate._MAX_SIGNATURE_ENVELOPE_BYTES + 1)},
            {"observed_at": "2026-09-03T01:30:00+00:00"},
            {"observed_at": 1},
        )
        for changes in cases:
            kwargs: dict[str, object] = {
                "public_key_pin_bytes": self.pin_bytes,
                "preauthorization_bytes": self.body_bytes,
                "signature_envelope_bytes": self.envelope_bytes,
                "observed_at": self.observed_at,
                **changes,
            }
            with self.subTest(changes=tuple(changes)):
                with patch.object(
                    candidate.preauth_v2,
                    candidate.PREAUTHORIZATION_PUBLIC_API,
                ) as child_call:
                    with self.assertRaises(
                        candidate.P0ActualOwnerRootPreauthorizationV2SupervisorError
                    ):
                        candidate.execute_owner_root_preauthorization_v2_supervisor_windows(
                            self.packet_dir, **kwargs  # type: ignore[arg-type]
                        )
                child_call.assert_not_called()

    def test_child_exception_is_closed_and_called_once(self) -> None:
        with self._patched_child(error=RuntimeError("child failed")) as calls:
            with self.assertRaisesRegex(
                candidate.P0ActualOwnerRootPreauthorizationV2SupervisorError,
                "child validation failed",
            ):
                candidate.execute_owner_root_preauthorization_v2_supervisor_windows(
                    self.packet_dir,
                    public_key_pin_bytes=self.pin_bytes,
                    preauthorization_bytes=self.body_bytes,
                    signature_envelope_bytes=self.envelope_bytes,
                    observed_at=self.observed_at,
                )
        self.assertEqual(len(calls), 1)

    def test_missing_extra_order_and_mapping_subclass_are_rejected(self) -> None:
        missing = dict(self.child)
        missing.pop("run_id")
        extra = dict(self.child)
        extra["extra"] = False
        reordered = {
            "preauthorization_component_manifest_sha256": self.child[
                "preauthorization_component_manifest_sha256"
            ],
            "schema_version": self.child["schema_version"],
            **{
                key: value
                for key, value in self.child.items()
                if key
                not in {"schema_version", "preauthorization_component_manifest_sha256"}
            },
        }
        subclass = DictSubclass(self.child)
        for forged in (missing, extra, reordered, subclass):
            with self.subTest(kind=type(forged).__name__, length=len(forged)):
                with self.assertRaises(
                    candidate.P0ActualOwnerRootPreauthorizationV2SupervisorError
                ):
                    self._execute(forged)

    def test_string_boolean_integer_and_subclass_types_are_rejected(self) -> None:
        mutations = (
            ("run_id", ["not", "str"]),
            (candidate._CHILD_TRUE_FIELDS[0], 1),
            (candidate._CHILD_FALSE_FIELDS[0], 0),
            ("key_epoch", True),
            ("key_epoch", IntSubclass(7)),
            ("credited_actual_source_claim_count", False),
        )
        for field, value in mutations:
            forged = deepcopy(self.child)
            forged[field] = value
            forged = reseal(forged)
            with self.subTest(field=field, value_type=type(value).__name__):
                with self.assertRaises(
                    candidate.P0ActualOwnerRootPreauthorizationV2SupervisorError
                ):
                    self._execute(forged)

    def test_hash_format_and_self_hash_are_rejected(self) -> None:
        bad_format = deepcopy(self.child)
        bad_format["signature_input_sha256"] = "AB" * 32
        bad_format = reseal(bad_format)
        bad_self_hash = deepcopy(self.child)
        bad_self_hash["receipt_sha256"] = "00" * 32
        for forged in (bad_format, bad_self_hash):
            with self.assertRaises(
                candidate.P0ActualOwnerRootPreauthorizationV2SupervisorError
            ):
                self._execute(forged)

    def test_component_pin_input_hash_and_observed_at_forgeries_are_rejected(self) -> None:
        mutations = (
            ("preauthorization_component_manifest_sha256", "11" * 32),
            ("windows_component_manifest_sha256", "11" * 32),
            ("packet_component_manifest_sha256", "11" * 32),
            ("fixed_member_contract_sha256", "11" * 32),
            ("public_key_pin_bytes_sha256", "11" * 32),
            ("preauthorization_bytes_sha256", "11" * 32),
            ("signature_envelope_bytes_sha256", "11" * 32),
            ("observed_at", "2026-09-03T01:31:00Z"),
        )
        for field, value in mutations:
            forged = deepcopy(self.child)
            forged[field] = value
            forged = reseal(forged)
            with self.subTest(field=field):
                with self.assertRaises(
                    candidate.P0ActualOwnerRootPreauthorizationV2SupervisorError
                ):
                    self._execute(forged)

    def test_truth_gate_and_credit_forgeries_are_rejected(self) -> None:
        mutations = (
            (candidate._CHILD_TRUE_FIELDS[0], False),
            (candidate._CHILD_FALSE_FIELDS[0], True),
            ("credited_actual_source_claim_count", 1),
            ("credited_actual_a_context_review_count", 1),
            ("operational_effect", "WRITE"),
            ("gate_status", "GO"),
        )
        for field, value in mutations:
            forged = deepcopy(self.child)
            forged[field] = value
            forged = reseal(forged)
            with self.subTest(field=field):
                with self.assertRaises(
                    candidate.P0ActualOwnerRootPreauthorizationV2SupervisorError
                ):
                    self._execute(forged)

    def test_raw_input_aggregate_and_safe_projection_are_recomputable(self) -> None:
        receipt, _ = self._execute()
        expected_binding = {
            "domain": candidate.RAW_INPUT_BINDING_DOMAIN,
            "packet_dir_input_kind": "PATH",
            "packet_dir_lexical_utf8_length": len(
                str(self.packet_dir).encode("utf-8")
            ),
            "packet_dir_lexical_utf8_sha256": hashlib.sha256(
                str(self.packet_dir).encode("utf-8")
            ).hexdigest(),
            "public_key_pin_bytes_length": len(self.pin_bytes),
            "public_key_pin_bytes_sha256": hashlib.sha256(self.pin_bytes).hexdigest(),
            "preauthorization_bytes_length": len(self.body_bytes),
            "preauthorization_bytes_sha256": hashlib.sha256(self.body_bytes).hexdigest(),
            "signature_envelope_bytes_length": len(self.envelope_bytes),
            "signature_envelope_bytes_sha256": hashlib.sha256(
                self.envelope_bytes
            ).hexdigest(),
            "observed_at": self.observed_at,
        }
        self.assertEqual(receipt["raw_input_binding_sha256"], digest(expected_binding))
        safe = receipt["child_safe_projection"]
        safe_material = dict(safe)
        safe_declared = safe_material.pop("receipt_sha256")
        self.assertEqual(safe_declared, digest(safe_material))
        self.assertEqual(
            receipt["child_truth_table_projection_sha256"],
            safe["child_truth_table_projection_sha256"],
        )

    def test_path_kind_and_lexical_bytes_are_bound_without_normalization(self) -> None:
        path_receipt, _ = self._execute()
        with self._patched_child() as str_calls:
            str_receipt = candidate.execute_owner_root_preauthorization_v2_supervisor_windows(
                str(self.packet_dir),
                public_key_pin_bytes=self.pin_bytes,
                preauthorization_bytes=self.body_bytes,
                signature_envelope_bytes=self.envelope_bytes,
                observed_at=self.observed_at,
            )
        self.assertEqual(len(str_calls), 1)
        self.assertEqual(path_receipt["packet_dir_input_kind"], "PATH")
        self.assertEqual(str_receipt["packet_dir_input_kind"], "STR")
        self.assertEqual(
            path_receipt["packet_dir_lexical_utf8_sha256"],
            str_receipt["packet_dir_lexical_utf8_sha256"],
        )
        self.assertNotEqual(
            path_receipt["raw_input_binding_sha256"],
            str_receipt["raw_input_binding_sha256"],
        )
        lexical = "segment/../presented-packet-v2"
        with self._patched_child() as lexical_calls:
            lexical_receipt = (
                candidate.execute_owner_root_preauthorization_v2_supervisor_windows(
                    lexical,
                    public_key_pin_bytes=self.pin_bytes,
                    preauthorization_bytes=self.body_bytes,
                    signature_envelope_bytes=self.envelope_bytes,
                    observed_at=self.observed_at,
                )
            )
        self.assertEqual(len(lexical_calls), 1)
        self.assertEqual(
            lexical_receipt["packet_dir_lexical_utf8_sha256"],
            hashlib.sha256(lexical.encode("utf-8")).hexdigest(),
        )
        self.assertIs(
            lexical_receipt["external_root_identity_pin_verified"], False
        )
        self.assertIs(lexical_receipt["root_identity_authority_verified"], False)

    def test_invalid_path_lexical_inputs_fail_before_child(self) -> None:
        invalid = ("", "bad\x00path", b"path", object(), "bad\ud800path")
        for packet_dir in invalid:
            with self.subTest(value_type=type(packet_dir).__name__):
                with patch.object(
                    candidate.preauth_v2,
                    candidate.PREAUTHORIZATION_PUBLIC_API,
                ) as child_call:
                    with self.assertRaises(
                        candidate.P0ActualOwnerRootPreauthorizationV2SupervisorError
                    ):
                        candidate.execute_owner_root_preauthorization_v2_supervisor_windows(
                            packet_dir,  # type: ignore[arg-type]
                            public_key_pin_bytes=self.pin_bytes,
                            preauthorization_bytes=self.body_bytes,
                            signature_envelope_bytes=self.envelope_bytes,
                            observed_at=self.observed_at,
                        )
                child_call.assert_not_called()

    def test_step_receipt_missing_extra_order_mapping_and_scalar_types_rejected(self) -> None:
        receipt, _ = self._execute()
        step = receipt["execution_step_receipt"]
        self.assertIs(type(step), dict)
        kwargs = self._step_kwargs(step)
        missing = dict(step)
        missing.pop("operation")
        extra = dict(step)
        extra["extra"] = False
        reordered = {
            "domain": step["domain"],
            "schema_version": step["schema_version"],
            **{
                key: value
                for key, value in step.items()
                if key not in {"schema_version", "domain"}
            },
        }
        subclass = DictSubclass(step)
        wrong_int = deepcopy(step)
        wrong_int["ordinal"] = False
        wrong_int = reseal(wrong_int)
        wrong_str = deepcopy(step)
        wrong_str["operation"] = [candidate.EXECUTION_STEP]
        wrong_str = reseal(wrong_str)
        for forged in (missing, extra, reordered, subclass, wrong_int, wrong_str):
            with self.subTest(kind=type(forged).__name__, length=len(forged)):
                with self.assertRaises(
                    candidate.P0ActualOwnerRootPreauthorizationV2SupervisorError
                ):
                    candidate._strict_step_receipt(forged, **kwargs)

    def test_step_receipt_input_output_count_and_self_hash_forgeries_rejected(self) -> None:
        receipt, _ = self._execute()
        step = receipt["execution_step_receipt"]
        self.assertIs(type(step), dict)
        kwargs = self._step_kwargs(step)
        mutations = (
            ("schema_version", "wrong"),
            ("domain", "wrong"),
            ("ordinal", 1),
            ("operation", "wrong"),
            ("raw_input_binding_sha256", "11" * 32),
            ("child_receipt_declared_sha256", "11" * 32),
            ("child_receipt_full_sha256", "11" * 32),
            ("child_safe_projection_sha256", "11" * 32),
            ("child_truth_table_projection_sha256", "11" * 32),
            ("preauthorization_execution_count", 2),
            ("direct_windows_execution_count", 1),
        )
        for field, value in mutations:
            forged = deepcopy(step)
            forged[field] = value
            forged = reseal(forged)
            with self.subTest(field=field):
                with self.assertRaises(
                    candidate.P0ActualOwnerRootPreauthorizationV2SupervisorError
                ):
                    candidate._strict_step_receipt(forged, **kwargs)
        bad_hash = deepcopy(step)
        bad_hash["receipt_sha256"] = "00" * 32
        with self.assertRaises(
            candidate.P0ActualOwnerRootPreauthorizationV2SupervisorError
        ):
            candidate._strict_step_receipt(bad_hash, **kwargs)

    def test_checked_callable_object_is_the_exact_object_called_once(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def checked(*args: object, **kwargs: object) -> object:
            calls.append((args, kwargs))
            return self.child

        with (
            patch.object(candidate, "_assert_dependency_contract", return_value=checked),
            patch.object(
                candidate.preauth_v2,
                candidate.PREAUTHORIZATION_PUBLIC_API,
            ) as swapped_after_check,
        ):
            receipt = candidate.execute_owner_root_preauthorization_v2_supervisor_windows(
                self.packet_dir,
                public_key_pin_bytes=self.pin_bytes,
                preauthorization_bytes=self.body_bytes,
                signature_envelope_bytes=self.envelope_bytes,
                observed_at=self.observed_at,
            )
        self.assertEqual(len(calls), 1)
        swapped_after_check.assert_not_called()
        self.assertIs(receipt["preauthorization_public_api_identity_pinned"], True)

    def test_same_bundle_can_pass_twice_but_replay_and_authority_stay_false(self) -> None:
        first, _ = self._execute()
        second, _ = self._execute()
        self.assertEqual(first, second)
        for field in (
            "single_use_replay_consumed",
            "same_bundle_replay_prevented",
            "durable_cross_process_nonce_verified",
            "external_owner_trust_verified",
            "actual_authority_granted",
            "production_approval",
            "full_scan_approval",
            "p0_phase_exit",
            "action_applied",
        ):
            self.assertIs(first[field], False, field)

    def test_no_direct_windows_runtime_v1_or_side_effect_imports(self) -> None:
        source = inspect.getsource(candidate)
        self.assertNotIn("p0_presented_a_context_annotation_packet_v2_windows", source)
        self.assertNotIn("preauthorization_v1", source)
        import_lines = tuple(
            line.strip()
            for line in source.splitlines()
            if line.startswith("import ") or line.startswith("from ")
        )
        self.assertFalse(
            any(
                forbidden in line
                for line in import_lines
                for forbidden in (
                    "runtime",
                    "subprocess",
                    "socket",
                    "urllib",
                    "requests",
                )
            )
        )
        self.assertNotIn("open(", source)
        self.assertNotIn(".write(", source)
        self.assertNotIn(".write_text(", source)
        self.assertNotIn(".write_bytes(", source)
        self.assertEqual(receipt_imports(source), {"p0_actual_owner_root_preauthorization_v2"})

    def test_coherent_monkeypatch_receipt_never_claims_code_or_authority(self) -> None:
        receipt, calls = self._execute()
        self.assertEqual(len(calls), 1)
        self.assertIs(receipt["child_receipt_exactly_validated"], True)
        self.assertIs(receipt["same_process_monkeypatch_resistance_verified"], False)
        self.assertIs(receipt["upstream_code_identity_verified"], False)
        self.assertIs(receipt["supervisor_independent_windows_observation_verified"], False)
        self.assertIs(receipt["direct_windows_validator_called_by_supervisor"], False)
        self.assertIs(receipt["actual_authority_granted"], False)


def receipt_imports(source: str) -> set[str]:
    prefix = "from llm_batch.grounding import "
    result: set[str] = set()
    for line in source.splitlines():
        if line.startswith(prefix):
            result.add(line[len(prefix) :].split(" as ", 1)[0].strip())
    return result


if __name__ == "__main__":
    unittest.main()
