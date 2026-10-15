from __future__ import annotations

import base64
import ast
from copy import deepcopy
import hashlib
import inspect
import json
import unittest

from llm_batch.grounding import p0_actual_registry_contract as registry_contract
from llm_batch.grounding import p0_actual_route_contract as route_contract
from llm_batch.grounding import p0_source_profile_parser_candidate as parser
from llm_batch.grounding import p0_source_profile_parser_parent_validator as parent
from tests import test_p0_actual_route_contract as route_fixture


def _structured_payload(profile: str, index: int) -> bytes:
    surface = f"신조어-{profile.lower()}-{index:02d}"
    if profile == "OFFICIAL_STRUCTURED" and index == 1:
        surface = "새말🙂"
    definition = f"정의-{profile.lower()}-{index:02d}"
    document = f"'{surface}'은 {definition}을 뜻한다"
    entry_kind = parser.ENTRY_EXPLICIT_DEFINITION_CANDIDATE
    envelope: dict[str, object] = {
        "schema_version": parser.ENVELOPE_SCHEMA,
        "source_profile": profile,
        "document": document,
        "entries": [
            {
                "entry_kind": entry_kind,
                "evidence_start": 0,
                "evidence_end": len(document),
                "surface": surface,
                "definition": definition,
            }
        ],
    }
    if profile == "MEDIA_OCR":
        envelope["ocr_source_media_sha256"] = parser.canonical_sha256(
            {"media": index}
        )
        envelope["ocr_engine_manifest_sha256"] = parser.canonical_sha256(
            {"engine": index}
        )
    return parser.canonical_file_bytes(envelope)


def _payload(profile: str, index: int) -> bytes:
    if profile == "GENERIC_FALLBACK":
        return f"일반 해석 보류 입력 {index:02d}: 잔빛-{index:02d}\n".encode("utf-8")
    return _structured_payload(profile, index)


def _materials() -> tuple[
    list[dict[str, object]],
    dict[str, object],
    dict[str, bytes],
]:
    templates = route_fixture._jsonl(route_fixture.SNAPSHOT_PATH)
    sources: list[dict[str, object]] = []
    payloads: dict[str, bytes] = {}
    sequence = 0
    for profile in route_contract.SOURCE_PROFILES:
        for profile_index in range(1, 11):
            sequence += 1
            source = route_fixture._snapshot(
                templates[0], profile, profile_index, sequence
            )
            raw = _payload(profile, profile_index)
            source.update(
                {
                    "capture_profile": profile.lower(),
                    "payload_ref": f"pure_parser_{sequence:02d}.txt",
                    "response_bytes": len(raw),
                    "response_sha256": hashlib.sha256(raw).hexdigest(),
                    "normalized_text_sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
            source = route_fixture._rehash_snapshot(source)
            sources.append(source)
            payloads[str(source["registry_record_id"])] = raw
    plan = route_fixture._plan(sources)
    return sources, plan, payloads


def _request(
    sources: list[dict[str, object]],
    plan: dict[str, object],
    payloads: dict[str, bytes],
) -> bytes:
    return parser.build_request_bytes(
        request_id="EXAMPLE:PURE:PARSER:REQUEST:01",
        parser_run_id="EXAMPLE:PURE:PARSER:RUN:01",
        source_snapshots=sources,
        input_plan=plan,
        payloads_by_registry=payloads,
    )


def _replace_payload(
    sources: list[dict[str, object]],
    payloads: dict[str, bytes],
    registry_id: str,
    raw: bytes,
) -> tuple[list[dict[str, object]], dict[str, object], dict[str, bytes]]:
    changed_sources = deepcopy(sources)
    changed_payloads = dict(payloads)
    changed_payloads[registry_id] = raw
    for index, source in enumerate(changed_sources):
        if source["registry_record_id"] == registry_id:
            source["response_bytes"] = len(raw)
            source["response_sha256"] = hashlib.sha256(raw).hexdigest()
            source["normalized_text_sha256"] = hashlib.sha256(raw).hexdigest()
            changed_sources[index] = route_fixture._rehash_snapshot(source)
            break
    return changed_sources, route_fixture._plan(changed_sources), changed_payloads


def _response_object(raw: bytes) -> dict[str, object]:
    return json.loads(raw.decode("utf-8"))


def _reseal_response(response: dict[str, object]) -> bytes:
    material = {key: value for key, value in response.items() if key != "response_sha256"}
    response["response_sha256"] = parser.canonical_sha256(material)
    return parser.canonical_file_bytes(response)


class P0SourceProfileParserCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sources, cls.plan, cls.payloads = _materials()
        cls.request_raw = _request(cls.sources, cls.plan, cls.payloads)
        cls.response_raw = parser.execute_request_bytes(cls.request_raw)
        cls.validated = parent.validated_artifacts(
            cls.response_raw, cls.request_raw
        )

    def test_controlled_10x4_produces_existing_claim_and_terminal_artifacts(self) -> None:
        claims = self.validated["source_claims"]
        terminals = self.validated["terminal_rows"]
        receipt = self.validated["receipt"]
        self.assertEqual(len(claims), 40)
        self.assertEqual(len(terminals), 10)
        self.assertEqual(receipt["input_count"], 40)
        self.assertEqual(receipt["typed_input_count"], 30)
        self.assertEqual(receipt["typed_claim_row_count"], 30)
        self.assertEqual(receipt["generic_count"], 10)
        self.assertEqual(receipt["error_count"], 0)
        self.assertTrue(receipt["presented_envelope_projection_contract_verified"])
        self.assertTrue(
            receipt[
                "parent_independent_presented_payload_projection_replay_verified"
            ]
        )
        for field in parser.FALSE_AUTHORITY_FIELDS:
            self.assertIs(receipt[field], False, field)
        self.assertEqual(
            receipt["credited_counts"],
            {"actual_source_claim_count": 0, "actual_a_context_review_count": 0},
        )

        seal = route_fixture._seal(self.plan, self.sources, claims)
        route_receipt = route_contract.validate_route_bundle(
            source_snapshots=self.sources,
            input_plan=self.plan,
            selection_seal=seal,
            source_claims=claims,
            terminal_rows=terminals,
            expected_origin=route_contract.EXAMPLE_ORIGIN,
        )
        self.assertTrue(route_receipt["selection_complete"])
        self.assertTrue(route_receipt["exact_accounting_verified"])
        self.assertFalse(route_receipt["parser_receipt_verified"])
        self.assertFalse(route_receipt["route_accounting_packet_complete"])

    def test_same_request_is_byte_deterministic(self) -> None:
        second = parser.execute_request_bytes(self.request_raw)
        self.assertEqual(self.response_raw, second)
        self.assertEqual(
            parent.validate_response_against_request(second, self.request_raw),
            self.validated["receipt"],
        )

    def test_asaenggal_mention_is_not_typed_or_promoted(self) -> None:
        target = next(
            row
            for row in self.sources
            if row["source_profile"] == "OFFICIAL_STRUCTURED"
        )
        envelope = {
            "schema_version": parser.ENVELOPE_SCHEMA,
            "source_profile": "OFFICIAL_STRUCTURED",
            "document": "아생갤🙂 재밌다",
            "entries": [
                {
                    "entry_kind": "SURFACE_MENTION",
                    "evidence_start": 0,
                    "evidence_end": 3,
                    "surface": "아생갤",
                    "definition": None,
                }
            ],
        }
        changed = _replace_payload(
            self.sources,
            self.payloads,
            str(target["registry_record_id"]),
            parser.canonical_file_bytes(envelope),
        )
        request_raw = _request(*changed)
        response_raw = parser.execute_request_bytes(request_raw)
        artifacts = parent.validated_artifacts(response_raw, request_raw)
        matching_claims = [
            row
            for row in artifacts["source_claims"]
            if row["registry_record_id"] == target["registry_record_id"]
        ]
        self.assertEqual(matching_claims, [])
        terminal = next(
            row
            for row in artifacts["terminal_rows"]
            if row["registry_record_id"] == target["registry_record_id"]
        )
        self.assertEqual(terminal["terminal_disposition"], "PARSER_ERROR")
        rendered = response_raw.decode("utf-8")
        self.assertNotIn("아카데미 생존 갤러리", rendered)
        self.assertNotIn("NON_TERM_EVIDENCE", rendered)
        self.assertNotIn("WORK_ALIAS", rendered)

    def test_surrounding_negation_cannot_launder_a_selected_subspan(self) -> None:
        target = next(
            row
            for row in self.sources
            if row["source_profile"] == "OFFICIAL_STRUCTURED"
        )
        statement = "'은어'은 새 뜻을 뜻한다"
        document = f"누군가는 {statement}는 주장은 거짓이라고 말했다"
        start = document.index(statement)
        envelope = {
            "schema_version": parser.ENVELOPE_SCHEMA,
            "source_profile": "OFFICIAL_STRUCTURED",
            "document": document,
            "entries": [
                {
                    "entry_kind": parser.ENTRY_EXPLICIT_DEFINITION_CANDIDATE,
                    "evidence_start": start,
                    "evidence_end": start + len(statement),
                    "surface": "은어",
                    "definition": "새 뜻",
                }
            ],
        }
        changed = _replace_payload(
            self.sources,
            self.payloads,
            str(target["registry_record_id"]),
            parser.canonical_file_bytes(envelope),
        )
        request_raw = _request(*changed)
        response_raw = parser.execute_request_bytes(request_raw)
        artifacts = parent.validated_artifacts(response_raw, request_raw)
        self.assertFalse(
            any(
                row["registry_record_id"] == target["registry_record_id"]
                for row in artifacts["source_claims"]
            )
        )
        terminal = next(
            row
            for row in artifacts["terminal_rows"]
            if row["registry_record_id"] == target["registry_record_id"]
        )
        self.assertEqual(terminal["terminal_disposition"], "PARSER_ERROR")

    def test_multiple_structured_statements_are_rejected_not_projected_one_to_many(self) -> None:
        target = next(
            row
            for row in self.sources
            if row["source_profile"] == "COMMUNITY_STRUCTURED"
        )
        first = "'첫말'은 첫 정의를 뜻한다"
        second = "'둘말'은 둘 정의를 뜻한다"
        document = f"{first}\n{second}"
        envelope = {
            "schema_version": parser.ENVELOPE_SCHEMA,
            "source_profile": "COMMUNITY_STRUCTURED",
            "document": document,
            "entries": [
                {
                    "entry_kind": parser.ENTRY_EXPLICIT_DEFINITION_CANDIDATE,
                    "evidence_start": 0,
                    "evidence_end": len(first),
                    "surface": "첫말",
                    "definition": "첫 정의",
                },
                {
                    "entry_kind": parser.ENTRY_EXPLICIT_DEFINITION_CANDIDATE,
                    "evidence_start": len(first) + 1,
                    "evidence_end": len(document),
                    "surface": "둘말",
                    "definition": "둘 정의",
                },
            ],
        }
        changed = _replace_payload(
            self.sources,
            self.payloads,
            str(target["registry_record_id"]),
            parser.canonical_file_bytes(envelope),
        )
        request_raw = _request(*changed)
        response_raw = parser.execute_request_bytes(request_raw)
        artifacts = parent.validated_artifacts(response_raw, request_raw)
        self.assertFalse(
            any(
                row["registry_record_id"] == target["registry_record_id"]
                for row in artifacts["source_claims"]
            )
        )
        terminal = next(
            row
            for row in artifacts["terminal_rows"]
            if row["registry_record_id"] == target["registry_record_id"]
        )
        self.assertEqual(terminal["terminal_disposition"], "PARSER_ERROR")

    def test_multibyte_surface_has_distinct_character_and_utf8_byte_witness(self) -> None:
        claim = next(
            row
            for row in self.validated["source_claims"]
            if row["surface_text"] == "새말🙂"
        )
        self.assertEqual(claim["claim_kind"], "NEW_SENSE_CANDIDATE")
        self.assertIsNone(claim["target_work_id"])
        self.assertIsNone(claim["target_sense_id"])
        response = _response_object(self.response_raw)
        witness = next(
            row
            for row in response["claim_byte_span_witnesses"]
            if row["claim_id"] == claim["claim_id"]
        )
        self.assertGreater(
            witness["utf8_byte_span_end"] - witness["utf8_byte_span_start"],
            witness["character_span_end"] - witness["character_span_start"],
        )

    def test_request_label_or_output_field_is_rejected_before_transform(self) -> None:
        request = json.loads(self.request_raw.decode("utf-8"))
        for field in (
            "gold_label",
            "truth_kind",
            "target_work_id",
            "annotation_artifact_sha256",
            "candidate_registry",
            "expected_title",
        ):
            forged = deepcopy(request)
            forged[field] = "forbidden"
            with self.subTest(field=field), self.assertRaisesRegex(
                parser.P0SourceProfileParserCandidateError, "fields mismatch"
            ):
                parser.execute_request_bytes(parser.canonical_file_bytes(forged))

    def test_capture_profile_must_match_source_profile(self) -> None:
        sources = deepcopy(self.sources)
        sources[0]["capture_profile"] = "attacker_profile"
        sources[0] = route_fixture._rehash_snapshot(sources[0])
        plan = route_fixture._plan(sources)
        with self.assertRaisesRegex(
            parser.P0SourceProfileParserCandidateError,
            "capture/input-plan registry binding mismatch",
        ):
            _request(sources, plan, self.payloads)

    def test_target_injection_in_structured_envelope_becomes_parser_error(self) -> None:
        target = next(
            row
            for row in self.sources
            if row["source_profile"] == "OFFICIAL_STRUCTURED"
        )
        raw = self.payloads[str(target["registry_record_id"])]
        envelope = json.loads(raw.decode("utf-8"))
        envelope["target_work_id"] = "ATTACKER:ARBITRARY"
        changed = _replace_payload(
            self.sources,
            self.payloads,
            str(target["registry_record_id"]),
            parser.canonical_file_bytes(envelope),
        )
        request_raw = _request(*changed)
        response_raw = parser.execute_request_bytes(request_raw)
        validated = parent.validated_artifacts(response_raw, request_raw)
        self.assertEqual(validated["receipt"]["typed_input_count"], 29)
        self.assertEqual(validated["receipt"]["error_count"], 1)
        terminal = next(
            row
            for row in validated["terminal_rows"]
            if row["registry_record_id"] == target["registry_record_id"]
        )
        self.assertEqual(terminal["terminal_disposition"], "PARSER_ERROR")
        self.assertNotIn("ATTACKER", json.dumps(terminal))

    def test_noncanonical_or_duplicate_structured_bytes_are_terminal_errors(self) -> None:
        target = next(
            row
            for row in self.sources
            if row["source_profile"] == "COMMUNITY_STRUCTURED"
        )
        original = self.payloads[str(target["registry_record_id"])].decode("utf-8")
        envelope = json.loads(original)
        noncanonical = json.dumps(envelope, ensure_ascii=False, indent=2).encode("utf-8")
        duplicate = original.replace(
            '"document":', '"document":"duplicate","document":', 1
        ).encode("utf-8")
        for label, raw in (("noncanonical", noncanonical), ("duplicate", duplicate)):
            with self.subTest(label=label):
                changed = _replace_payload(
                    self.sources,
                    self.payloads,
                    str(target["registry_record_id"]),
                    raw,
                )
                request_raw = _request(*changed)
                response_raw = parser.execute_request_bytes(request_raw)
                receipt = parent.validate_response_against_request(
                    response_raw, request_raw
                )
                self.assertEqual(receipt["error_count"], 1)

    def test_generic_profile_cannot_become_typed(self) -> None:
        generic_source = next(
            row
            for row in self.sources
            if row["source_profile"] == "GENERIC_FALLBACK"
        )
        structured_bytes = _structured_payload("OFFICIAL_STRUCTURED", 99)
        changed = _replace_payload(
            self.sources,
            self.payloads,
            str(generic_source["registry_record_id"]),
            structured_bytes,
        )
        request_raw = _request(*changed)
        response_raw = parser.execute_request_bytes(request_raw)
        artifacts = parent.validated_artifacts(response_raw, request_raw)
        claim = next(
            row
            for row in artifacts["source_claims"]
            if row["registry_record_id"] == generic_source["registry_record_id"]
        )
        self.assertEqual(claim["claim_kind"], "UNKNOWN")
        self.assertEqual(claim["parse_disposition"], "GENERIC_PENDING")
        self.assertIsNone(claim["target_work_id"])
        self.assertIsNone(claim["target_sense_id"])

    def test_fully_resealed_arbitrary_work_target_is_rejected_by_parent_replay(self) -> None:
        response = _response_object(self.response_raw)
        claim_raw = base64.b64decode(response["source_claims_jsonl_base64"])
        claims = [json.loads(line) for line in claim_raw.decode("utf-8").splitlines()]
        attacked = claims[0]
        attacked.update(
            {
                "track": "A",
                "claim_kind": "WORK_ALIAS",
                "claim_direction": "SURFACE_TO_WORK",
                "target_work_id": "ATTACKER:ARBITRARY",
                "definition": None,
            }
        )
        attacked["claim_id"] = "P0:CLAIM:" + parser.canonical_sha256(
            parser._claim_id_material(
                attacked,
                str(
                    next(
                        source["response_sha256"]
                        for source in self.sources
                        if source["registry_record_id"]
                        == attacked["registry_record_id"]
                    )
                ),
            )
        )
        source = next(
            row
            for row in self.sources
            if row["registry_record_id"] == attacked["registry_record_id"]
        )
        attacked["claim_evidence_receipt_sha256"] = registry_contract._claim_receipt(
            attacked, str(source["response_sha256"])
        )
        claims[0] = registry_contract.with_row_hash(attacked)
        new_claim_raw = b"".join(parser.canonical_file_bytes(row) for row in claims)
        response["source_claims_jsonl_base64"] = base64.b64encode(new_claim_raw).decode(
            "ascii"
        )
        response["source_claims_file_bytes"] = len(new_claim_raw)
        response["source_claims_file_sha256"] = hashlib.sha256(new_claim_raw).hexdigest()
        response["source_claim_inventory_sha256"] = route_contract.canonical_sha256(
            claims
        )
        typed = [row for row in claims if row["claim_kind"] != "UNKNOWN"]
        response["typed_output_claims_sha256"] = route_contract.canonical_sha256(
            typed
        )
        witnesses = response["claim_byte_span_witnesses"]
        witnesses[0]["claim_id"] = claims[0]["claim_id"]
        response["claim_byte_span_witnesses_sha256"] = parser.canonical_sha256(
            witnesses
        )
        forged_raw = _reseal_response(response)
        with self.assertRaisesRegex(
            parent.P0SourceProfileParserParentValidationError,
            "independent capture replay",
        ):
            parent.validate_response_against_request(forged_raw, self.request_raw)

    def test_claim_reorder_with_resealed_hashes_is_rejected(self) -> None:
        response = _response_object(self.response_raw)
        claims = [
            json.loads(line)
            for line in base64.b64decode(
                response["source_claims_jsonl_base64"]
            ).decode("utf-8").splitlines()
        ]
        claims[0], claims[1] = claims[1], claims[0]
        raw = b"".join(parser.canonical_file_bytes(row) for row in claims)
        response["source_claims_jsonl_base64"] = base64.b64encode(raw).decode("ascii")
        response["source_claims_file_bytes"] = len(raw)
        response["source_claims_file_sha256"] = hashlib.sha256(raw).hexdigest()
        response["source_claim_inventory_sha256"] = route_contract.canonical_sha256(
            claims
        )
        response["typed_output_claims_sha256"] = route_contract.canonical_sha256(
            [row for row in claims if row["claim_kind"] != "UNKNOWN"]
        )
        forged_raw = _reseal_response(response)
        with self.assertRaisesRegex(
            parent.P0SourceProfileParserParentValidationError,
            "independent capture replay",
        ):
            parent.validate_response_against_request(forged_raw, self.request_raw)

    def test_component_has_no_direct_io_or_process_imports(self) -> None:
        allowed_roots = {
            "__future__",
            "ast",
            "base64",
            "binascii",
            "hashlib",
            "json",
            "re",
            "typing",
            "unicodedata",
            "llm_batch",
        }
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
        for module in (parser, parent):
            source = inspect.getsource(module)
            tree = ast.parse(source)
            imports: set[str] = set()
            project_imports: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name.split(".", 1)[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.add((node.module or "").split(".", 1)[0])
                    if node.module == "llm_batch.grounding":
                        project_imports.update(alias.name for alias in node.names)
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        self.assertNotIn(node.func.id, forbidden_calls)
                    elif isinstance(node.func, ast.Attribute):
                        rendered = ast.unparse(node.func)
                        if rendered != "re.compile":
                            self.assertNotIn(node.func.attr, forbidden_calls)
            self.assertLessEqual(imports, allowed_roots)
            expected_project_imports = (
                {
                    "p0_actual_registry_contract",
                    "p0_actual_route_contract",
                }
                if module is parser
                else {
                    "p0_actual_registry_contract",
                    "p0_actual_route_contract",
                    "p0_source_profile_parser_candidate",
                }
            )
            self.assertEqual(project_imports, expected_project_imports)
            self.assertNotIn("DecisionLedger", source)
            self.assertNotIn("PublicationCommit", source)


if __name__ == "__main__":
    unittest.main()
