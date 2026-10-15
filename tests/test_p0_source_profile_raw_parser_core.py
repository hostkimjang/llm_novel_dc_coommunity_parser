from __future__ import annotations

import ast
from copy import deepcopy
import inspect
from pathlib import Path
import unittest
from unittest import mock

from llm_batch.grounding import p0_actual_packet_contract as packet_contract
from llm_batch.grounding import p0_source_profile_raw_parser_core as core
from llm_batch.grounding import (
    p0_source_profile_raw_parser_core_parent_validator as parent,
)


ROOT = Path(__file__).resolve().parents[1]


def _parse(
    payload: bytes,
    *,
    source_profile: str = core.SUPPORTED_PROFILE,
    content_type: str = core.SUPPORTED_CONTENT_TYPE,
    capture_version: str = core.SUPPORTED_CAPTURE_VERSION,
    normalization_version: str = core.SUPPORTED_NORMALIZATION_VERSION,
) -> dict[str, object]:
    return core.parse_capture(
        source_profile=source_profile,
        content_type=content_type,
        capture_version=capture_version,
        normalization_version=normalization_version,
        payload=payload,
    )


def _validate(result: dict[str, object], payload: bytes) -> dict[str, object]:
    return parent.validate_result_against_capture(
        result,
        source_profile=core.SUPPORTED_PROFILE,
        content_type=core.SUPPORTED_CONTENT_TYPE,
        capture_version=core.SUPPORTED_CAPTURE_VERSION,
        normalization_version=core.SUPPORTED_NORMALIZATION_VERSION,
        payload=payload,
    )


def _reseal(result: dict[str, object]) -> dict[str, object]:
    material = {key: value for key, value in result.items() if key != "result_sha256"}
    result["result_sha256"] = core.canonical_sha256(material)
    return result


class P0SourceProfileRawParserCoreTests(unittest.TestCase):
    def test_two_whole_line_grammars_emit_ordered_neutral_observations(self) -> None:
        first = "'새말🙂'은 새 뜻을 뜻한다."
        second = "'줄임말'는 두 번째 뜻를 뜻한다."
        payload = f"{first}\n{second}\n".encode("utf-8")
        result = _parse(payload)

        self.assertEqual(result["disposition"], "MATCHED")
        self.assertEqual(result["observation_count"], 2)
        self.assertEqual(result["line_count"], 2)
        observations = result["observations"]
        self.assertIsInstance(observations, list)
        first_row, second_row = observations
        self.assertEqual(first_row["surface_text"], "새말🙂")
        self.assertEqual(first_row["presented_definition_text"], "새 뜻")
        self.assertEqual(second_row["surface_text"], "줄임말")
        self.assertEqual(second_row["presented_definition_text"], "두 번째 뜻")
        self.assertEqual(second_row["character_span_start"], len(first) + 1)
        self.assertGreater(
            second_row["utf8_byte_span_start"], second_row["character_span_start"]
        )
        for row in observations:
            self.assertEqual(
                set(row),
                {
                    "schema_version",
                    "observation_sequence",
                    "line_number",
                    "relation_kind",
                    "character_span_start",
                    "character_span_end",
                    "utf8_byte_span_start",
                    "utf8_byte_span_end",
                    "evidence_text",
                    "evidence_utf8_sha256",
                    "surface_text",
                    "surface_utf8_sha256",
                    "presented_definition_text",
                    "presented_definition_utf8_sha256",
                    "observation_sha256",
                },
            )
            self.assertFalse(
                {"track", "claim_kind", "target_work_id", "target_sense_id", "credit"}
                & set(row)
            )

        receipt = _validate(result, payload)
        self.assertTrue(
            receipt["parent_separate_implementation_capture_replay_verified"]
        )
        self.assertFalse(receipt["same_process_isolation_verified"])
        self.assertFalse(receipt["core_code_identity_verified"])
        self.assertFalse(receipt["parent_code_identity_verified"])
        self.assertFalse(receipt["claim_rows_emitted"])
        self.assertFalse(receipt["target_ids_emitted"])
        self.assertFalse(receipt["actual_semantic_evidence_verified"])
        self.assertFalse(receipt["p0_phase_exit"])

    def test_mentions_alias_language_questions_and_suffixes_are_no_match(self) -> None:
        cases = (
            "아생갤 재밌다",
            "아생갤은 현실 갤러리다",
            "아생갤은 아카데미 생존 갤러리의 약칭이다",
            "'아생갤'은 어떤 뜻을 뜻한다?",
            "누군가는 '아생갤'은 어떤 뜻을 뜻한다는 주장은 거짓이라고 말했다",
            "'아생갤'은 어떤 뜻을 뜻한다. 라고 비꼬았다",
            "'아생갤'은 실제 뜻이 아니다. 사실 작품 별칭을 뜻한다.",
            "'표면'은 정의\u202e를 뜻한다.",
            "'표면'은 첫 정의。둘째 정의를 뜻한다.",
        )
        for text in cases:
            with self.subTest(text=text):
                result = _parse(text.encode("utf-8"))
                self.assertEqual(result["disposition"], "NO_MATCH")
                self.assertEqual(result["observations"], [])
                self.assertNotIn("target_work_id", str(result))
                _validate(result, text.encode("utf-8"))

    def test_preceding_negation_line_closes_all_partial_matches(self) -> None:
        payload = (
            "아래 내용은 사실이 아니다:\n"
            "'아생갤'은 아카데미 생존 갤러리를 뜻한다."
        ).encode("utf-8")
        result = _parse(payload)
        self.assertEqual(result["disposition"], "NO_MATCH")
        self.assertEqual(
            result["reason_code"], "mixed_or_nonmatching_context_fail_closed"
        )
        self.assertEqual(result["observation_count"], 0)
        _validate(result, payload)

    def test_exact_asaenggal_definition_is_neutral_text_not_work_alias(self) -> None:
        payload = "'아생갤'은 아카데미 생존 갤러리를 뜻한다.".encode("utf-8")
        result = _parse(payload)
        self.assertEqual(result["disposition"], "MATCHED")
        row = result["observations"][0]
        self.assertEqual(row["surface_text"], "아생갤")
        self.assertEqual(
            row["presented_definition_text"], "아카데미 생존 갤러리"
        )
        rendered = str(result)
        for forbidden in (
            "WORK_ALIAS",
            "NEW_SENSE_CANDIDATE",
            "COMMUNITY_SENSE",
            "NON_TERM_EVIDENCE",
            "target_work_id",
            "target_sense_id",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_unpinned_profiles_and_capture_contracts_remain_unsupported(self) -> None:
        payload = "'표면'은 제시 정의를 뜻한다.".encode("utf-8")
        expected = {
            "OFFICIAL_STRUCTURED": "official_capture_adapter_not_bound",
            "MEDIA_OCR": "ocr_media_engine_transcript_provenance_not_bound",
            "GENERIC_FALLBACK": "generic_profile_requires_manual_lane",
            "ATTACKER_PROFILE": "unknown_source_profile",
        }
        for profile, reason in expected.items():
            with self.subTest(profile=profile):
                result = _parse(payload, source_profile=profile)
                self.assertEqual(result["disposition"], "UNSUPPORTED_PROFILE")
                self.assertEqual(result["reason_code"], reason)
                self.assertEqual(result["observations"], [])
                receipt = parent.validate_result_against_capture(
                    result,
                    source_profile=profile,
                    content_type=core.SUPPORTED_CONTENT_TYPE,
                    capture_version=core.SUPPORTED_CAPTURE_VERSION,
                    normalization_version=core.SUPPORTED_NORMALIZATION_VERSION,
                    payload=payload,
                )
                self.assertEqual(receipt["disposition"], "UNSUPPORTED_PROFILE")
        for field, value in (
            ("content_type", "application/json"),
            ("capture_version", "attacker-adapter-v1"),
            ("normalization_version", "nfkc-v1"),
        ):
            kwargs = {field: value}
            result = _parse(payload, **kwargs)
            self.assertEqual(result["disposition"], "UNSUPPORTED_PROFILE")
            self.assertEqual(result["reason_code"], "community_capture_contract_mismatch")

    def test_invalid_capture_classes_are_separate_from_no_match(self) -> None:
        cases = {
            "empty": b"",
            "oversized": b"x" * (core.MAX_PAYLOAD_BYTES + 1),
            "invalid utf8": b"\xff",
            "BOM": b"\xef\xbb\xbftext",
            "NUL": b"a\x00b",
            "CRLF": b"a\r\n",
            "NFD": "'e\u0301'은 정의를 뜻한다.".encode("utf-8"),
            "zero width": "'아\u200b생갤'은 정의를 뜻한다.".encode("utf-8"),
        }
        for label, payload in cases.items():
            with self.subTest(label=label):
                result = _parse(payload)
                self.assertEqual(result["disposition"], "INVALID_CAPTURE")
                self.assertEqual(result["observations"], [])
                _validate(result, payload)

    def test_metadata_is_bounded_and_rejects_unicode_controls(self) -> None:
        payload = "'표면'은 제시 정의를 뜻한다.".encode("utf-8")
        for kwargs in (
            {"capture_version": "bad\u202e-version"},
            {"content_type": "x" * 513},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(
                core.P0RawCaptureParserCoreError
            ):
                _parse(payload, **kwargs)

    def test_observation_limit_fails_closed_without_partial_output(self) -> None:
        boundary = "\n".join(
            f"'경계-{index:02d}'은 정의-{index:02d}을 뜻한다."
            for index in range(core.MAX_OBSERVATIONS)
        ).encode("utf-8")
        boundary_result = _parse(boundary)
        self.assertEqual(boundary_result["disposition"], "MATCHED")
        self.assertEqual(
            boundary_result["observation_count"], core.MAX_OBSERVATIONS
        )
        _validate(boundary_result, boundary)

        payload = "\n".join(
            f"'표면-{index:02d}'은 정의-{index:02d}을 뜻한다."
            for index in range(core.MAX_OBSERVATIONS + 1)
        ).encode("utf-8")
        result = _parse(payload)
        self.assertEqual(result["disposition"], "INVALID_CAPTURE")
        self.assertEqual(result["reason_code"], "observation_limit_exceeded")
        self.assertEqual(result["observations"], [])
        _validate(result, payload)

    def test_same_capture_is_byte_canonically_deterministic(self) -> None:
        payload = "'표면'은 제시 정의를 뜻한다.\n".encode("utf-8")
        first = _parse(payload)
        second = _parse(payload)
        self.assertEqual(first, second)
        self.assertEqual(core.canonical_bytes(first), core.canonical_bytes(second))
        self.assertEqual(first["core_manifest_sha256"], core.CORE_MANIFEST_SHA256)

    def test_parent_rejects_fully_resealed_observation_and_field_injection(self) -> None:
        payload = "'표면'은 제시 정의를 뜻한다.".encode("utf-8")
        original = _parse(payload)

        changed = deepcopy(original)
        row = changed["observations"][0]
        row["surface_text"] = "공격표면"
        observation_material = {
            key: value for key, value in row.items() if key != "observation_sha256"
        }
        row["observation_sha256"] = core.canonical_sha256(observation_material)
        changed["observations_sha256"] = core.canonical_sha256(changed["observations"])
        _reseal(changed)
        with self.assertRaisesRegex(
            parent.P0RawCaptureCoreParentValidationError, "independent capture replay"
        ):
            _validate(changed, payload)

        injected = deepcopy(original)
        injected["observations"][0]["target_work_id"] = "ATTACKER:WORK"
        injected["observations_sha256"] = core.canonical_sha256(
            injected["observations"]
        )
        _reseal(injected)
        with self.assertRaisesRegex(
            parent.P0RawCaptureCoreParentValidationError,
            "observation field set mismatch",
        ):
            _validate(injected, payload)

    def test_parent_rejects_resealed_observation_delete_duplicate_and_reorder(self) -> None:
        payload = "\n".join(
            (
                "'첫말'은 첫 정의를 뜻한다.",
                "'둘말'은 둘 정의를 뜻한다.",
                "'셋말'은 셋 정의를 뜻한다.",
            )
        ).encode("utf-8")
        original = _parse(payload)
        variants = {
            "delete": deepcopy(original["observations"][:-1]),
            "duplicate": deepcopy(
                [*original["observations"], original["observations"][0]]
            ),
            "reorder": deepcopy(list(reversed(original["observations"]))),
        }
        for label, observations in variants.items():
            with self.subTest(label=label):
                changed = deepcopy(original)
                changed["observations"] = observations
                changed["observation_count"] = len(observations)
                changed["observations_sha256"] = core.canonical_sha256(observations)
                _reseal(changed)
                with self.assertRaisesRegex(
                    parent.P0RawCaptureCoreParentValidationError,
                    "independent capture replay",
                ):
                    _validate(changed, payload)

    def test_parent_rejects_bool_int_float_scalar_equivalence(self) -> None:
        payload = "'표면'은 제시 정의를 뜻한다.".encode("utf-8")
        original = _parse(payload)
        mutations = (
            ("observation_count bool", lambda row: row.__setitem__("observation_count", True)),
            ("line_count float", lambda row: row.__setitem__("line_count", 1.0)),
            (
                "sequence bool",
                lambda row: row["observations"][0].__setitem__(
                    "observation_sequence", True
                ),
            ),
            (
                "span bool",
                lambda row: row["observations"][0].__setitem__(
                    "character_span_start", False
                ),
            ),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                changed = deepcopy(original)
                mutate(changed)
                with self.assertRaisesRegex(
                    parent.P0RawCaptureCoreParentValidationError,
                    "independent capture replay",
                ):
                    _validate(changed, payload)

    def test_parent_pins_contract_independently_from_core_module_monkeypatch(self) -> None:
        payload = "'표면'은 제시 정의를 뜻한다.".encode("utf-8")
        self.assertEqual(
            core.CORE_MANIFEST_SHA256, parent.EXPECTED_CORE_MANIFEST_SHA256
        )
        with mock.patch.object(core, "CORE_VERSION", "attacker-core-v999"), mock.patch.object(
            core, "CORE_MANIFEST_SHA256", "f" * 64
        ):
            attacked = _parse(payload)
            with self.assertRaisesRegex(
                parent.P0RawCaptureCoreParentValidationError,
                "independent capture replay",
            ):
                _validate(attacked, payload)

    def test_core_and_parent_have_narrow_static_capability_surface(self) -> None:
        core_tree = ast.parse(inspect.getsource(core))
        parent_tree = ast.parse(inspect.getsource(parent))
        core_import_roots: set[str] = set()
        for node in ast.walk(core_tree):
            if isinstance(node, ast.Import):
                core_import_roots.update(
                    alias.name.split(".")[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                core_import_roots.add(node.module.split(".")[0])
        self.assertEqual(
            core_import_roots,
            {"__future__", "hashlib", "json", "re", "unicodedata", "typing"},
        )
        forbidden_calls = {
            "open",
            "exec",
            "eval",
            "compile",
            "__import__",
            "system",
            "popen",
            "connect",
            "spawn",
        }
        for label, tree in (("core", core_tree), ("parent", parent_tree)):
            calls = {
                node.func.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            }
            self.assertFalse(forbidden_calls & calls, label)
        parent_calls = {
            node.func.attr
            for node in ast.walk(parent_tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertNotIn("parse_capture", parent_calls)
        parent_import_roots: set[str] = set()
        for node in ast.walk(parent_tree):
            if isinstance(node, ast.Import):
                parent_import_roots.update(
                    alias.name.split(".")[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                parent_import_roots.add(node.module.split(".")[0])
        self.assertEqual(
            parent_import_roots,
            {"__future__", "hashlib", "json", "re", "unicodedata", "typing"},
        )
        source = inspect.getsource(core) + inspect.getsource(parent)
        for forbidden in (
            "DecisionLedger",
            "PublicationCommit",
            "slang_db",
            "target_work_id",
            "target_sense_id",
        ):
            self.assertNotIn(forbidden, source)

    def test_existing_probe_worker_sandbox_and_packet_inventory_are_unchanged(self) -> None:
        self.assertEqual(len(packet_contract.CHILD_FILES), 13)
        token = "p0_source_profile_raw_parser_core"
        for relative in (
            "src/llm_batch/grounding/p0_parser_process_protocol.py",
            "src/llm_batch/grounding/p0_parser_process_worker.py",
            "src/llm_batch/grounding/p0_windows_parser_process_sandbox.py",
            "src/llm_batch/grounding/p0_actual_packet_contract.py",
        ):
            self.assertNotIn(token, (ROOT / relative).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
