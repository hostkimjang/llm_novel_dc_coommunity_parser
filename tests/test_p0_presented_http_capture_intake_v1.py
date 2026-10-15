from __future__ import annotations

from copy import deepcopy
import ast
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from llm_batch.grounding import p0_presented_http_capture_intake_v1_contract as contract
from llm_batch.grounding import p0_presented_http_capture_intake_v1_parent_validator as parent
from llm_batch.grounding import p0_presented_source_seed_candidate_inventory_v1_contract as seed_contract


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "src" / "llm_batch" / "grounding" / "p0_presented_http_capture_intake_v1_contract.py"
PARENT_PATH = REPO_ROOT / "src" / "llm_batch" / "grounding" / "p0_presented_http_capture_intake_v1_parent_validator.py"


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _payloads() -> dict[str, bytes]:
    return {
        seed_id: f"presented response body {sequence}: {seed_id}\n".encode("utf-8")
        for sequence, (seed_id, *_rest) in enumerate(contract.SEED_SPECIFICATIONS, start=1)
    }


def _timestamp_evidence() -> dict[str, object]:
    material = {
        "date_header": None,
        "last_modified_header": None,
        "source_timestamp": None,
        "source_timestamp_basis": "NOT_EXPOSED",
    }
    return {**material, "evidence_sha256": contract.canonical_sha256(material)}


def _records(payloads: dict[str, bytes]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for sequence, (seed_id, _track, url, _hint, _lineage, _relation) in enumerate(
        contract.SEED_SPECIFICATIONS, start=1
    ):
        final_url = url
        hops: list[dict[str, object]] = []
        if sequence == 1:
            final_url = "https://arca.live/redirected/novel-abbreviation"
            hops = [{
                "hop_sequence": 1,
                "from_url": url,
                "status_code": 302,
                "location": "/redirected/novel-abbreviation",
                "to_url": final_url,
            }]
        payload = payloads[seed_id]
        rows.append({
            "seed_sequence": sequence,
            "seed_id": seed_id,
            "source_id": seed_id,
            "requested_url": url,
            "final_url": final_url,
            "redirect_hops": hops,
            "terminal_http_status": 200,
            "response_content_type": "text/html; charset=utf-8",
            "source_timestamp_evidence": _timestamp_evidence(),
            "capture_timing_provenance": {
                "presented_capture_id": f"presented-http-capture:{seed_id}",
                "presented_collected_at": f"2026-09-03T0{sequence}:00:00+09:00",
                "clock_source": "CALLER_PRESENTED_UNVERIFIED",
                "clock_attestation_ref_sha256": _sha_text(f"clock:{seed_id}"),
                "capture_tool_id": "presented-http-client-v1",
                "capture_tool_manifest_sha256": _sha_text("capture-tool-v1"),
                "request_config_sha256": _sha_text(f"request:{seed_id}"),
                "response_representation": "HTTP_CONTENT_DECODED_ENTITY_BYTES_V1",
                "content_encoding": "identity",
            },
            "rights_attestation_ref": {
                "artifact_role": "RIGHTS_ATTESTATION_CANDIDATE",
                "artifact_id": f"presented-rights-attestation:{seed_id}",
                "artifact_sha256": _sha_text(f"rights:{seed_id}"),
                "attestation_status": "NOT_ATTESTED",
            },
            "retention_attestation_ref": {
                "artifact_role": "RETENTION_ATTESTATION_CANDIDATE",
                "artifact_id": f"presented-retention-attestation:{seed_id}",
                "artifact_sha256": _sha_text(f"retention:{seed_id}"),
                "attestation_status": "NOT_ATTESTED",
            },
            "byte_locator": {
                "payload_role": "RAW_HTTP_RESPONSE_BODY",
                "payload_id": f"presented-http-body:{seed_id}",
                "coordinate_system": "ZERO_BASED_BYTE_OFFSETS_IN_RESPONSE_BODY",
                "start": 0,
                "end": len(payload),
                "payload_sha256": hashlib.sha256(payload).hexdigest(),
            },
        })
    return rows


def _build():
    seed_raw = seed_contract.build_registry_bytes()
    payloads = _payloads()
    records = _records(payloads)
    intake = contract.build_intake_bytes(
        seed_registry_raw=seed_raw,
        presented_records=records,
        raw_payloads_by_seed=payloads,
    )
    receipt = contract.build_receipt_bytes(
        intake,
        seed_registry_raw=seed_raw,
        presented_records=records,
        raw_payloads_by_seed=payloads,
    )
    return seed_raw, payloads, records, intake, receipt


def _canonical_file(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8") + b"\n"


def _reseal(value: dict[str, object], field: str) -> bytes:
    material = deepcopy(value)
    material.pop(field, None)
    material[field] = contract.canonical_sha256(material)
    return _canonical_file(material)


class PresentedHttpCaptureIntakeV1Tests(unittest.TestCase):
    def test_exact_eight_seed_capture_bindings_and_parent_replay(self) -> None:
        seed_raw, payloads, records, intake_raw, receipt_raw = _build()
        intake = contract.validate_intake_bytes(
            intake_raw, seed_registry_raw=seed_raw, presented_records=records,
            raw_payloads_by_seed=payloads,
        )
        receipt = contract.validate_receipt_bytes(
            receipt_raw, intake_raw=intake_raw, seed_registry_raw=seed_raw,
            presented_records=records, raw_payloads_by_seed=payloads,
        )
        parent_receipt = parent.validate_parent_replay(
            seed_registry_raw=seed_raw, presented_records=records,
            raw_payloads_by_seed=payloads, intake_raw=intake_raw,
            child_receipt_raw=receipt_raw,
        )
        self.assertEqual(intake["row_count"], 8)
        self.assertEqual(intake["track_counts"], {"A": 3, "B": 5})
        self.assertEqual(intake["lineage_family_count"], 4)
        self.assertTrue(receipt["seed_binding_verified"])
        self.assertTrue(parent_receipt["original_input_replayed"])

    def test_all_authority_semantic_index_publication_and_metric_fields_fail_closed(self) -> None:
        seed_raw, payloads, records, intake_raw, receipt_raw = _build()
        intake = json.loads(intake_raw)
        receipt = json.loads(receipt_raw)
        for row in intake["rows"]:
            self.assertEqual(row["record_origin"], "PRESENTED_UNVERIFIED")
            self.assertEqual(row["capture_runtime_status"], "NOT_RUN")
            self.assertEqual(row["parser_status"], "NOT_RUN")
            self.assertEqual(row["attestation_status"], "NOT_ATTESTED")
            self.assertEqual(row["rights_status"], "UNKNOWN_FAIL_CLOSED")
            self.assertEqual(row["retention_status"], "UNKNOWN_FAIL_CLOSED")
            self.assertEqual(row["semantic_status"], "NOT_EVALUATED")
            for field in contract._FALSE_CAPABILITIES:
                self.assertIs(row[field], False)
        self.assertEqual(intake["metric_denominator"], 0)
        self.assertEqual(receipt["actual_credit_count"], 0)
        self.assertEqual(receipt["metric_status"], "NOT_ESTIMABLE")
        parent.validate_parent_replay(
            seed_registry_raw=seed_raw, presented_records=records,
            raw_payloads_by_seed=payloads, intake_raw=intake_raw,
            child_receipt_raw=receipt_raw,
        )

    def test_raw_payload_never_appears_in_intake_receipt_or_parent_receipt(self) -> None:
        seed_raw, payloads, records, intake_raw, receipt_raw = _build()
        parent_receipt = parent.validate_parent_replay(
            seed_registry_raw=seed_raw, presented_records=records,
            raw_payloads_by_seed=payloads, intake_raw=intake_raw,
            child_receipt_raw=receipt_raw,
        )
        combined = intake_raw + receipt_raw + _canonical_file(parent_receipt)
        for payload in payloads.values():
            self.assertNotIn(payload, combined)
        self.assertNotIn(b"payload_base64", combined)
        self.assertNotIn(b"content_text", combined)

    def test_same_inputs_are_byte_deterministic(self) -> None:
        first = _build()
        second = _build()
        self.assertEqual(first[3], second[3])
        self.assertEqual(first[4], second[4])

    def test_seed_registry_identity_tamper_is_rejected(self) -> None:
        seed_raw, payloads, records, intake_raw, receipt_raw = _build()
        bad = seed_raw.replace(b"seed-arca", b"seed-xrca", 1)
        with self.assertRaises(contract.P0PresentedHttpCaptureIntakeError):
            contract.build_intake_bytes(
                seed_registry_raw=bad, presented_records=records,
                raw_payloads_by_seed=payloads,
            )
        with self.assertRaises(parent.P0PresentedHttpCaptureIntakeParentError):
            parent.validate_parent_replay(
                seed_registry_raw=bad, presented_records=records,
                raw_payloads_by_seed=payloads, intake_raw=b"{}\n",
                child_receipt_raw=b"{}\n",
            )

    def test_seed_or_source_swap_is_rejected(self) -> None:
        seed_raw, payloads, records, _intake, _receipt = _build()
        for mutate in ("seed_id", "source_id", "requested_url", "seed_sequence"):
            bad = deepcopy(records)
            bad[0][mutate] = bad[1][mutate]
            with self.subTest(field=mutate), self.assertRaises(contract.P0PresentedHttpCaptureIntakeError):
                contract.build_intake_bytes(
                    seed_registry_raw=seed_raw, presented_records=bad,
                    raw_payloads_by_seed=payloads,
                )

    def test_extra_duplicate_missing_or_reordered_records_are_rejected(self) -> None:
        seed_raw, payloads, records, _intake, _receipt = _build()
        variants = [records[:-1], records + [deepcopy(records[-1])], [records[1], records[0], *records[2:]], [records[0], records[0], *records[2:]]]
        for bad in variants:
            with self.subTest(length=len(bad)), self.assertRaises(contract.P0PresentedHttpCaptureIntakeError):
                contract.build_intake_bytes(
                    seed_registry_raw=seed_raw, presented_records=bad,
                    raw_payloads_by_seed=payloads,
                )

    def test_payload_mapping_extra_missing_and_order_swap_are_rejected(self) -> None:
        seed_raw, payloads, records, _intake, _receipt = _build()
        missing = dict(payloads)
        missing.pop(next(iter(missing)))
        extra = dict(payloads)
        extra["seed-extra"] = b"extra"
        reversed_mapping = dict(reversed(list(payloads.items())))
        for bad in (missing, extra, reversed_mapping):
            with self.assertRaises(contract.P0PresentedHttpCaptureIntakeError):
                contract.build_intake_bytes(
                    seed_registry_raw=seed_raw, presented_records=records,
                    raw_payloads_by_seed=bad,
                )

    def test_redirect_location_resolution_laundering_is_rejected(self) -> None:
        seed_raw, payloads, records, _intake, _receipt = _build()
        bad = deepcopy(records)
        bad[0]["redirect_hops"][0]["location"] = "/different-target"
        with self.assertRaises(contract.P0PresentedHttpCaptureIntakeError):
            contract.build_intake_bytes(
                seed_registry_raw=seed_raw, presented_records=bad,
                raw_payloads_by_seed=payloads,
            )

    def test_redirect_order_final_url_cycle_and_status_are_rejected(self) -> None:
        seed_raw, payloads, records, _intake, _receipt = _build()
        variants = []
        for field, value in (
            ("hop_sequence", 2), ("from_url", records[1]["requested_url"]),
            ("status_code", 200), ("to_url", records[0]["requested_url"]),
        ):
            bad = deepcopy(records)
            bad[0]["redirect_hops"][0][field] = value
            variants.append(bad)
        bad = deepcopy(records)
        bad[0]["final_url"] = bad[0]["requested_url"]
        variants.append(bad)
        for bad in variants:
            with self.assertRaises(contract.P0PresentedHttpCaptureIntakeError):
                contract.build_intake_bytes(
                    seed_registry_raw=seed_raw, presented_records=bad,
                    raw_payloads_by_seed=payloads,
                )

    def test_redirect_control_fragment_userinfo_and_excess_hops_fail_closed(self) -> None:
        seed_raw, payloads, records, intake_raw, receipt_raw = _build()
        variants = []
        for location, target in (
            ("/bad\u200b", "https://arca.live/bad"),
            ("/bad#fragment", "https://arca.live/bad#fragment"),
            ("https://user@arca.live/bad", "https://user@arca.live/bad"),
        ):
            bad = deepcopy(records)
            bad[0]["redirect_hops"][0]["location"] = location
            bad[0]["redirect_hops"][0]["to_url"] = target
            bad[0]["final_url"] = target
            variants.append(bad)
        bad = deepcopy(records)
        base = bad[0]["requested_url"]
        hops = []
        for i in range(11):
            target = f"https://arca.live/r{i}"
            hops.append({"hop_sequence": i + 1, "from_url": base, "status_code": 302, "location": f"/r{i}", "to_url": target})
            base = target
        bad[0]["redirect_hops"] = hops
        bad[0]["final_url"] = base
        variants.append(bad)
        for bad in variants:
            with self.assertRaises(contract.P0PresentedHttpCaptureIntakeError):
                contract.build_intake_bytes(seed_registry_raw=seed_raw, presented_records=bad, raw_payloads_by_seed=payloads)
            with self.assertRaises(parent.P0PresentedHttpCaptureIntakeParentError):
                parent.validate_parent_replay(
                    seed_registry_raw=seed_raw, presented_records=bad,
                    raw_payloads_by_seed=payloads, intake_raw=intake_raw,
                    child_receipt_raw=receipt_raw,
                )

    def test_terminal_1xx_and_entity_body_status_mismatch_are_rejected(self) -> None:
        seed_raw, payloads, records, _intake, _receipt = _build()
        for status in (100, 199, 204, 205, 304):
            bad = deepcopy(records)
            bad[0]["terminal_http_status"] = status
            with self.subTest(status=status), self.assertRaises(contract.P0PresentedHttpCaptureIntakeError):
                contract.build_intake_bytes(seed_registry_raw=seed_raw, presented_records=bad, raw_payloads_by_seed=payloads)

    def test_zero_body_is_allowed_for_other_status_and_required_for_entityless_status(self) -> None:
        seed_raw, payloads, records, _intake, _receipt = _build()
        empty_payloads = dict(payloads)
        first = records[0]["seed_id"]
        empty_payloads[first] = b""
        empty_records = _records(empty_payloads)
        ordinary = contract.build_intake_bytes(seed_registry_raw=seed_raw, presented_records=empty_records, raw_payloads_by_seed=empty_payloads)
        self.assertEqual(json.loads(ordinary)["rows"][0]["raw_response_bytes"], 0)
        empty_records[0]["terminal_http_status"] = 204
        raw = contract.build_intake_bytes(seed_registry_raw=seed_raw, presented_records=empty_records, raw_payloads_by_seed=empty_payloads)
        self.assertEqual(json.loads(raw)["rows"][0]["raw_response_bytes"], 0)

    def test_byte_locator_length_or_hash_mismatch_is_rejected(self) -> None:
        seed_raw, payloads, records, _intake, _receipt = _build()
        for field, value in (("end", 1), ("payload_sha256", "f" * 64), ("start", 1)):
            bad = deepcopy(records)
            bad[0]["byte_locator"][field] = value
            with self.assertRaises(contract.P0PresentedHttpCaptureIntakeError):
                contract.build_intake_bytes(seed_registry_raw=seed_raw, presented_records=bad, raw_payloads_by_seed=payloads)

    def test_payload_change_after_build_is_rejected_by_contract_and_parent(self) -> None:
        seed_raw, payloads, records, intake_raw, receipt_raw = _build()
        changed = dict(payloads)
        first = next(iter(changed))
        changed[first] += b"tamper"
        with self.assertRaises(contract.P0PresentedHttpCaptureIntakeError):
            contract.validate_intake_bytes(intake_raw, seed_registry_raw=seed_raw, presented_records=records, raw_payloads_by_seed=changed)
        with self.assertRaises(parent.P0PresentedHttpCaptureIntakeParentError):
            parent.validate_parent_replay(seed_registry_raw=seed_raw, presented_records=records, raw_payloads_by_seed=changed, intake_raw=intake_raw, child_receipt_raw=receipt_raw)

    def test_rights_retention_authority_forgery_and_seed_ref_swap_are_rejected(self) -> None:
        seed_raw, payloads, records, _intake, _receipt = _build()
        variants = []
        bad = deepcopy(records)
        bad[0]["rights_attestation_ref"]["attestation_status"] = "ATTESTED"
        variants.append(bad)
        bad = deepcopy(records)
        bad[0]["retention_attestation_ref"] = deepcopy(bad[1]["retention_attestation_ref"])
        variants.append(bad)
        for bad in variants:
            with self.assertRaises(contract.P0PresentedHttpCaptureIntakeError):
                contract.build_intake_bytes(seed_registry_raw=seed_raw, presented_records=bad, raw_payloads_by_seed=payloads)

    def test_source_timestamp_basis_and_evidence_hash_are_bound(self) -> None:
        seed_raw, payloads, records, _intake, _receipt = _build()
        variants = []
        bad = deepcopy(records)
        bad[0]["source_timestamp_evidence"]["source_timestamp_basis"] = "PRESENTED_HTTP_DATE"
        variants.append(bad)
        bad = deepcopy(records)
        bad[0]["source_timestamp_evidence"]["evidence_sha256"] = "f" * 64
        variants.append(bad)
        for bad in variants:
            with self.assertRaises(contract.P0PresentedHttpCaptureIntakeError):
                contract.build_intake_bytes(seed_registry_raw=seed_raw, presented_records=bad, raw_payloads_by_seed=payloads)

    def test_http_timestamp_header_presence_parse_and_instant_equality_are_required(self) -> None:
        seed_raw, payloads, records, _intake, _receipt = _build()
        good = deepcopy(records)
        material = {
            "date_header": "Wed, 03 Sep 2026 00:00:00 GMT",
            "last_modified_header": None,
            "source_timestamp": "2026-09-03T00:00:00Z",
            "source_timestamp_basis": "PRESENTED_HTTP_DATE",
        }
        good[0]["source_timestamp_evidence"] = {**material, "evidence_sha256": contract.canonical_sha256(material)}
        contract.build_intake_bytes(seed_registry_raw=seed_raw, presented_records=good, raw_payloads_by_seed=payloads)
        for header, timestamp, basis in (
            (None, "2026-09-03T00:00:00Z", "PRESENTED_HTTP_DATE"),
            ("not-an-http-date", "2026-09-03T00:00:00Z", "PRESENTED_HTTP_DATE"),
            ("Wed, 03 Sep 2026 00:00:00 GMT", "2026-09-03T00:00:01Z", "PRESENTED_HTTP_DATE"),
            ("Wed, 03 Sep 2026 00:00:00 GMT", "2026-09-03T00:00:00Z", "PRESENTED_PAGE_METADATA"),
        ):
            bad = deepcopy(records)
            bad_material = {
                "date_header": header, "last_modified_header": None,
                "source_timestamp": timestamp, "source_timestamp_basis": basis,
            }
            bad[0]["source_timestamp_evidence"] = {**bad_material, "evidence_sha256": contract.canonical_sha256(bad_material)}
            with self.subTest(header=header, timestamp=timestamp, basis=basis), self.assertRaises(contract.P0PresentedHttpCaptureIntakeError):
                contract.build_intake_bytes(seed_registry_raw=seed_raw, presented_records=bad, raw_payloads_by_seed=payloads)

    def test_clock_or_capture_provenance_cannot_claim_authority(self) -> None:
        seed_raw, payloads, records, _intake, _receipt = _build()
        for field, value in (
            ("clock_source", "TRUSTED_TIME"),
            ("response_representation", "WIRE_BYTES"),
            ("presented_capture_id", records[1]["capture_timing_provenance"]["presented_capture_id"]),
        ):
            bad = deepcopy(records)
            bad[0]["capture_timing_provenance"][field] = value
            with self.assertRaises(contract.P0PresentedHttpCaptureIntakeError):
                contract.build_intake_bytes(seed_registry_raw=seed_raw, presented_records=bad, raw_payloads_by_seed=payloads)

    def test_url_content_type_and_encoding_must_already_be_canonical(self) -> None:
        seed_raw, payloads, records, intake_raw, receipt_raw = _build()
        variants = []
        bad = deepcopy(records)
        bad[0]["final_url"] = "https://ARCA.LIVE/redirected/novel-abbreviation"
        bad[0]["redirect_hops"][0]["to_url"] = bad[0]["final_url"]
        bad[0]["redirect_hops"][0]["location"] = bad[0]["final_url"]
        variants.append(bad)
        bad = deepcopy(records)
        bad[0]["response_content_type"] = "Text/HTML; Charset=UTF-8"
        variants.append(bad)
        bad = deepcopy(records)
        bad[0]["capture_timing_provenance"]["content_encoding"] = "Identity"
        variants.append(bad)
        bad = deepcopy(records)
        bad[0]["response_content_type"] = "💣/💣"
        variants.append(bad)
        bad = deepcopy(records)
        bad[0]["response_content_type"] = "text/html; charset=utf-8; charset=ascii"
        variants.append(bad)
        bad = deepcopy(records)
        bad[0]["capture_timing_provenance"]["content_encoding"] = "폭탄"
        variants.append(bad)
        bad = deepcopy(records)
        bad[0]["capture_timing_provenance"]["content_encoding"] = "compress"
        variants.append(bad)
        bad = deepcopy(records)
        bad[0]["final_url"] = "https://arca.live/a/../redirected/novel-abbreviation"
        bad[0]["redirect_hops"][0]["to_url"] = bad[0]["final_url"]
        bad[0]["redirect_hops"][0]["location"] = "/a/../redirected/novel-abbreviation"
        variants.append(bad)
        for bad in variants:
            with self.assertRaises(contract.P0PresentedHttpCaptureIntakeError):
                contract.build_intake_bytes(seed_registry_raw=seed_raw, presented_records=bad, raw_payloads_by_seed=payloads)
            with self.assertRaises(parent.P0PresentedHttpCaptureIntakeParentError):
                parent.validate_parent_replay(
                    seed_registry_raw=seed_raw, presented_records=bad,
                    raw_payloads_by_seed=payloads, intake_raw=intake_raw,
                    child_receipt_raw=receipt_raw,
                )

    def test_semantic_or_raw_content_field_injection_is_rejected(self) -> None:
        seed_raw, payloads, records, _intake, _receipt = _build()
        for field in ("target_work_id", "definition", "payload_base64", "content_text"):
            bad = deepcopy(records)
            bad[0][field] = "forged"
            with self.assertRaises(contract.P0PresentedHttpCaptureIntakeError):
                contract.build_intake_bytes(seed_registry_raw=seed_raw, presented_records=bad, raw_payloads_by_seed=payloads)

    def test_fully_resealed_output_rights_or_credit_forgery_is_rejected(self) -> None:
        seed_raw, payloads, records, intake_raw, _receipt_raw = _build()
        for mutate in ("row", "bundle"):
            value = json.loads(intake_raw)
            if mutate == "row":
                value["rows"][0]["derived_index_allowed"] = True
                row = value["rows"][0]
                material = dict(row)
                material.pop("row_sha256")
                row["row_sha256"] = contract.canonical_sha256(material)
                value["rows_sha256"] = contract.canonical_sha256(value["rows"])
            else:
                value["credited_actual_source_claim_count"] = 1
            forged = _reseal(value, "artifact_sha256")
            with self.assertRaises(contract.P0PresentedHttpCaptureIntakeError):
                contract.validate_intake_bytes(forged, seed_registry_raw=seed_raw, presented_records=records, raw_payloads_by_seed=payloads)

    def test_child_receipt_forgery_is_rejected_even_when_resealed(self) -> None:
        seed_raw, payloads, records, intake_raw, receipt_raw = _build()
        value = json.loads(receipt_raw)
        value["actual_credit_count"] = 1
        forged = _reseal(value, "receipt_sha256")
        with self.assertRaises(contract.P0PresentedHttpCaptureIntakeError):
            contract.validate_receipt_bytes(forged, intake_raw=intake_raw, seed_registry_raw=seed_raw, presented_records=records, raw_payloads_by_seed=payloads)
        with self.assertRaises(parent.P0PresentedHttpCaptureIntakeParentError):
            parent.validate_parent_replay(seed_registry_raw=seed_raw, presented_records=records, raw_payloads_by_seed=payloads, intake_raw=intake_raw, child_receipt_raw=forged)

    def test_producer_component_constant_tamper_fails_at_child_entry(self) -> None:
        seed_raw = seed_contract.build_registry_bytes()
        payloads = _payloads()
        records = _records(payloads)
        with patch.object(contract, "COMPONENT_MANIFEST_SHA256", "f" * 64), self.assertRaises(contract.P0PresentedHttpCaptureIntakeError):
            contract.build_intake_bytes(seed_registry_raw=seed_raw, presented_records=records, raw_payloads_by_seed=payloads)

    def test_producer_helper_tamper_fails_at_child_entry(self) -> None:
        seed_raw = seed_contract.build_registry_bytes()
        payloads = _payloads()
        records = _records(payloads)
        original = contract._normalize_presented_record

        def forged(*args, **kwargs):
            row = original(*args, **kwargs)
            row["semantic_status"] = "FORGED"
            material = dict(row)
            material.pop("row_sha256")
            row["row_sha256"] = contract.canonical_sha256(material)
            return row

        with patch.object(contract, "_normalize_presented_record", forged), self.assertRaises(contract.P0PresentedHttpCaptureIntakeError):
            contract.build_intake_bytes(seed_registry_raw=seed_raw, presented_records=records, raw_payloads_by_seed=payloads)

    def test_coordinated_child_parent_helper_tamper_fails_closed(self) -> None:
        seed_raw = seed_contract.build_registry_bytes()
        payloads = _payloads()
        records = _records(payloads)
        child_original = contract._normalize_presented_record
        parent_original = parent._normalize_record

        def forge(original):
            def forged(*args, **kwargs):
                row = original(*args, **kwargs)
                row["semantic_status"] = "FORGED"
                material = dict(row)
                material.pop("row_sha256")
                row["row_sha256"] = contract.canonical_sha256(material)
                return row
            return forged

        with (
            patch.object(contract, "_normalize_presented_record", forge(child_original)),
            patch.object(parent, "_normalize_record", forge(parent_original)),
            self.assertRaises(contract.P0PresentedHttpCaptureIntakeError),
        ):
            contract.build_intake_bytes(
                seed_registry_raw=seed_raw,
                presented_records=records,
                raw_payloads_by_seed=payloads,
            )

    def test_runtime_module_attribute_and_mime_regex_tamper_fail_closed(self) -> None:
        seed_raw, payloads, records, intake_raw, receipt_raw = _build()
        with patch.object(contract.json, "loads", lambda *_args, **_kwargs: {}), self.assertRaises(contract.P0PresentedHttpCaptureIntakeError):
            contract.validate_intake_bytes(
                intake_raw, seed_registry_raw=seed_raw,
                presented_records=records, raw_payloads_by_seed=payloads,
            )
        with patch.object(parent.unicodedata, "normalize", lambda *_args: ""), self.assertRaises(parent.P0PresentedHttpCaptureIntakeParentError):
            parent.validate_parent_replay(
                seed_registry_raw=seed_raw, presented_records=records,
                raw_payloads_by_seed=payloads, intake_raw=intake_raw,
                child_receipt_raw=receipt_raw,
            )
        permissive = contract.re.compile(r".+")
        with patch.object(contract, "_CONTENT_TYPE_RE", permissive), self.assertRaises(contract.P0PresentedHttpCaptureIntakeError):
            contract.build_intake_bytes(
                seed_registry_raw=seed_raw, presented_records=records,
                raw_payloads_by_seed=payloads,
            )
        with patch.object(parent, "_CONTENT_TYPE_RE", permissive), self.assertRaises(parent.P0PresentedHttpCaptureIntakeParentError):
            parent.validate_parent_replay(
                seed_registry_raw=seed_raw, presented_records=records,
                raw_payloads_by_seed=payloads, intake_raw=intake_raw,
                child_receipt_raw=receipt_raw,
            )

    def test_parent_constant_or_helper_tamper_fails_closed(self) -> None:
        seed_raw, payloads, records, intake_raw, receipt_raw = _build()
        with patch.object(parent, "EXPECTED_COMPONENT_MANIFEST_SHA256", "f" * 64), self.assertRaises(parent.P0PresentedHttpCaptureIntakeParentError):
            parent.validate_parent_replay(seed_registry_raw=seed_raw, presented_records=records, raw_payloads_by_seed=payloads, intake_raw=intake_raw, child_receipt_raw=receipt_raw)
        original = parent._normalize_record

        def forged(*args, **kwargs):
            row = original(*args, **kwargs)
            row["semantic_status"] = "FORGED"
            return row

        with patch.object(parent, "_normalize_record", forged), self.assertRaises(parent.P0PresentedHttpCaptureIntakeParentError):
            parent.validate_parent_replay(seed_registry_raw=seed_raw, presented_records=records, raw_payloads_by_seed=payloads, intake_raw=intake_raw, child_receipt_raw=receipt_raw)

    def test_noncanonical_bom_duplicate_key_and_unknown_field_are_rejected(self) -> None:
        seed_raw, payloads, records, intake_raw, _receipt = _build()
        variants = [b"\xef\xbb\xbf" + intake_raw, intake_raw.replace(b'"schema_version":', b'"schema_version":"duplicate","schema_version":', 1)]
        value = json.loads(intake_raw)
        value["unknown"] = False
        variants.append(_canonical_file(value))
        for bad in variants:
            with self.assertRaises(contract.P0PresentedHttpCaptureIntakeError):
                contract.validate_intake_bytes(bad, seed_registry_raw=seed_raw, presented_records=records, raw_payloads_by_seed=payloads)

    def test_contract_and_parent_have_no_io_process_or_seed_producer_dependency(self) -> None:
        forbidden_imports = {"os", "pathlib", "socket", "subprocess", "requests", "httpx", "urllib.request", "time", "random"}
        for path in (CONTRACT_PATH, PARENT_PATH):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imported.add(node.module or "")
            self.assertFalse(any(name in forbidden_imports or any(name.startswith(x + ".") for x in forbidden_imports) for name in imported), imported)
        parent_text = PARENT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("p0_presented_http_capture_intake_v1_contract", parent_text)
        self.assertNotIn("p0_presented_source_seed_candidate_inventory_v1_contract", parent_text)

    def test_component_and_seed_lineage_pins_are_exact(self) -> None:
        self.assertEqual(contract.SEED_COMPONENT_MANIFEST_SHA256, seed_contract.COMPONENT_MANIFEST_SHA256)
        self.assertEqual(contract.SEED_REGISTRY_RAW_SHA256, hashlib.sha256(seed_contract.build_registry_bytes()).hexdigest())
        self.assertEqual(parent.SEED_COMPONENT_SHA, seed_contract.COMPONENT_MANIFEST_SHA256)
        self.assertEqual(parent.SEED_RAW_SHA, contract.SEED_REGISTRY_RAW_SHA256)
        self.assertEqual(parent.EXPECTED_COMPONENT_MANIFEST_SHA256, contract.COMPONENT_MANIFEST_SHA256)


if __name__ == "__main__":
    unittest.main()
