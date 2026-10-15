from __future__ import annotations

from copy import deepcopy
import ast
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from llm_batch.grounding import p0_presented_http_capture_intake_v1_contract as capture
from llm_batch.grounding import p0_presented_source_seed_candidate_inventory_v1_contract as seed_contract
from llm_batch.grounding import p0_presented_http_capture_temporal_evidence_v2_contract as contract
from llm_batch.grounding import p0_presented_http_capture_temporal_evidence_v2_parent_validator as parent


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "src" / "llm_batch" / "grounding" / "p0_presented_http_capture_temporal_evidence_v2_contract.py"
PARENT_PATH = REPO_ROOT / "src" / "llm_batch" / "grounding" / "p0_presented_http_capture_temporal_evidence_v2_parent_validator.py"


def _raw_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _text_hash(value: str) -> str:
    return _raw_hash(value.encode("utf-8"))


def _timestamp_evidence(
    *,
    date_header: str | None = None,
    last_modified_header: str | None = None,
    source_timestamp: str | None = None,
    basis: str = "NOT_EXPOSED",
) -> dict[str, object]:
    material = {
        "date_header": date_header,
        "last_modified_header": last_modified_header,
        "source_timestamp": source_timestamp,
        "source_timestamp_basis": basis,
    }
    return {**material, "evidence_sha256": capture.canonical_sha256(material)}


def _payloads() -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for sequence, (seed_id, *_rest) in enumerate(capture.SEED_SPECIFICATIONS, start=1):
        if sequence == 1:
            raw = (
                b'{"datePublished":"2026-09-01T01:00:00+09:00",'
                b'"dateModified":"2026-09-02T00:00:00Z"}\n'
            )
        elif sequence == 2:
            raw = b'<meta data-version="rev-42">\n'
        else:
            raw = f"presented response body {sequence}: {seed_id}\n".encode("utf-8")
        result[seed_id] = raw
    return result


def _capture_records(payloads: dict[str, bytes]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for sequence, (seed_id, _track, url, _hint, _lineage, _relation) in enumerate(
        capture.SEED_SPECIFICATIONS, start=1
    ):
        timestamp = _timestamp_evidence()
        if sequence == 1:
            timestamp = _timestamp_evidence(
                date_header="Wed, 02 Sep 2026 16:00:00 GMT",
                last_modified_header="Wed, 02 Sep 2026 00:00:00 GMT",
                source_timestamp="2026-09-02T16:00:00Z",
                basis="PRESENTED_HTTP_DATE",
            )
        payload = payloads[seed_id]
        result.append({
            "seed_sequence": sequence, "seed_id": seed_id,
            "source_id": seed_id, "requested_url": url, "final_url": url,
            "redirect_hops": [], "terminal_http_status": 200,
            "response_content_type": "text/html; charset=utf-8",
            "source_timestamp_evidence": timestamp,
            "capture_timing_provenance": {
                "presented_capture_id": f"presented-http-capture:{seed_id}",
                "presented_collected_at": f"2026-09-03T0{sequence}:00:00+09:00",
                "clock_source": "CALLER_PRESENTED_UNVERIFIED",
                "clock_attestation_ref_sha256": _text_hash(f"clock:{seed_id}"),
                "capture_tool_id": "presented-http-client-v1",
                "capture_tool_manifest_sha256": _text_hash("capture-tool-v1"),
                "request_config_sha256": _text_hash(f"request:{seed_id}"),
                "response_representation": "HTTP_CONTENT_DECODED_ENTITY_BYTES_V1",
                "content_encoding": "identity",
            },
            "rights_attestation_ref": {
                "artifact_role": "RIGHTS_ATTESTATION_CANDIDATE",
                "artifact_id": f"presented-rights-attestation:{seed_id}",
                "artifact_sha256": _text_hash(f"rights:{seed_id}"),
                "attestation_status": "NOT_ATTESTED",
            },
            "retention_attestation_ref": {
                "artifact_role": "RETENTION_ATTESTATION_CANDIDATE",
                "artifact_id": f"presented-retention-attestation:{seed_id}",
                "artifact_sha256": _text_hash(f"retention:{seed_id}"),
                "attestation_status": "NOT_ATTESTED",
            },
            "byte_locator": {
                "payload_role": "RAW_HTTP_RESPONSE_BODY",
                "payload_id": f"presented-http-body:{seed_id}",
                "coordinate_system": "ZERO_BASED_BYTE_OFFSETS_IN_RESPONSE_BODY",
                "start": 0, "end": len(payload),
                "payload_sha256": _raw_hash(payload),
            },
        })
    return result


def _capture_bundle(
    payloads: dict[str, bytes] | None = None,
) -> tuple[bytes, dict[str, bytes], list[dict[str, object]], bytes, bytes]:
    payloads = _payloads() if payloads is None else payloads
    seed_raw = seed_contract.build_registry_bytes()
    records = _capture_records(payloads)
    intake = capture.build_intake_bytes(
        seed_registry_raw=seed_raw, presented_records=records,
        raw_payloads_by_seed=payloads,
    )
    receipt = capture.build_receipt_bytes(
        intake, seed_registry_raw=seed_raw, presented_records=records,
        raw_payloads_by_seed=payloads,
    )
    return seed_raw, payloads, records, intake, receipt


def _signal(
    payload: bytes,
    *,
    kind: str,
    syntax: str,
    value: str,
    normalized: str,
) -> dict[str, object]:
    encoded = value.encode("utf-8")
    value_start = payload.index(encoded)
    value_end = value_start + len(encoded)
    return {
        "kind": kind, "syntax": syntax,
        "context_start": 0, "context_end": len(payload),
        "value_start": value_start, "value_end": value_end,
        "context_sha256": _raw_hash(payload),
        "value_sha256": _raw_hash(encoded),
        "presented_value": value, "normalized_value": normalized,
    }


def _page_record(
    *,
    sequence: int,
    seed_id: str,
    capture_row_sha256: str,
    status: str,
    signals: list[dict[str, object]],
) -> dict[str, object]:
    material = {
        "seed_sequence": sequence, "seed_id": seed_id,
        "capture_row_sha256": capture_row_sha256,
        "native_revision_status": status,
        "signals": sorted(signals, key=lambda item: str(item["kind"])),
    }
    return {**material, "record_sha256": contract.canonical_sha256(material)}


def _reseal_page_record(record: dict[str, object]) -> None:
    material = dict(record)
    material.pop("record_sha256", None)
    material["signals"] = sorted(
        material["signals"], key=lambda item: str(item["kind"])
    )
    record["record_sha256"] = contract.canonical_sha256(material)


def _page_records(
    intake_raw: bytes, payloads: dict[str, bytes]
) -> list[dict[str, object]]:
    rows = json.loads(intake_raw)["rows"]
    output: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        signals: list[dict[str, object]] = []
        status = "NOT_EXPOSED"
        if index == 0:
            payload = payloads[row["seed_id"]]
            signals = [
                _signal(
                    payload, kind="PUBLISHED_AT", syntax="JSON_LD_DATE_PUBLISHED",
                    value="2026-09-01T01:00:00+09:00",
                    normalized="2026-08-31T16:00:00Z",
                ),
                _signal(
                    payload, kind="MODIFIED_AT", syntax="JSON_LD_DATE_MODIFIED",
                    value="2026-09-02T00:00:00Z",
                    normalized="2026-09-02T00:00:00Z",
                ),
            ]
            status = "PRESENTED_LOCATED"
        elif index == 1:
            payload = payloads[row["seed_id"]]
            signals = [
                _signal(
                    payload, kind="VERSION_ID", syntax="SITE_NATIVE_VERSION_TOKEN",
                    value="rev-42", normalized="rev-42",
                )
            ]
            status = "PRESENTED_LOCATED"
        output.append(_page_record(
            sequence=index + 1, seed_id=row["seed_id"],
            capture_row_sha256=row["row_sha256"], status=status,
            signals=signals,
        ))
    return output


def _bundle():
    seed_raw, payloads, records, intake, intake_receipt = _capture_bundle()
    page_records = _page_records(intake, payloads)
    kwargs = {
        "seed_registry_raw": seed_raw,
        "presented_records": records,
        "raw_payloads_by_seed": payloads,
        "intake_raw": intake,
        "intake_receipt_raw": intake_receipt,
        "page_revision_records": page_records,
    }
    artifact = contract.build_artifact_bytes(**kwargs)
    child_receipt = contract.build_receipt_bytes(artifact, **kwargs)
    return kwargs, artifact, child_receipt


def _kwargs_with_first_signals(
    payloads: dict[str, bytes], signals: list[dict[str, object]]
) -> dict[str, object]:
    seed_raw, payloads, records, intake, receipt = _capture_bundle(payloads)
    rows = json.loads(intake)["rows"]
    pages = [
        _page_record(
            sequence=index + 1, seed_id=row["seed_id"],
            capture_row_sha256=row["row_sha256"],
            status="PRESENTED_LOCATED" if index == 0 else "NOT_EXPOSED",
            signals=signals if index == 0 else [],
        )
        for index, row in enumerate(rows)
    ]
    return {
        "seed_registry_raw": seed_raw,
        "presented_records": records,
        "raw_payloads_by_seed": payloads,
        "intake_raw": intake,
        "intake_receipt_raw": receipt,
        "page_revision_records": pages,
    }


def _canonical_file(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8") + b"\n"


def _reseal(value: dict[str, object], field: str) -> bytes:
    material = deepcopy(value)
    material.pop(field, None)
    material[field] = contract.canonical_sha256(material)
    return _canonical_file(material)


class PresentedHttpCaptureTemporalEvidenceV2Tests(unittest.TestCase):
    def test_three_signal_types_are_separate_from_transport_and_parent_replay(self) -> None:
        kwargs, artifact_raw, receipt_raw = _bundle()
        artifact = contract.validate_artifact_bytes(artifact_raw, **kwargs)
        receipt = contract.validate_receipt_bytes(
            receipt_raw, artifact_raw=artifact_raw, **kwargs
        )
        parent_receipt = parent.validate_parent_replay(
            **kwargs, temporal_artifact_raw=artifact_raw,
            child_receipt_raw=receipt_raw,
        )
        self.assertEqual(artifact["row_count"], 8)
        self.assertEqual(artifact["track_counts"], {"A": 3, "B": 5})
        self.assertEqual(artifact["page_revision_presented_count"], 2)
        self.assertEqual(artifact["page_revision_not_exposed_count"], 6)
        self.assertEqual(artifact["page_revision_signal_count"], 3)
        self.assertEqual(artifact["http_date_present_count"], 1)
        self.assertEqual(artifact["http_last_modified_present_count"], 1)
        self.assertEqual(artifact["http_header_page_revision_promotion_count"], 0)
        self.assertTrue(receipt["transport_page_revision_separation_verified"])
        self.assertTrue(parent_receipt["predecessor_parent_replay_verified"])

    def test_http_headers_are_never_page_native_revision(self) -> None:
        kwargs, artifact_raw, _receipt_raw = _bundle()
        first = json.loads(artifact_raw)["rows"][0]
        transport = first["transport_observation"]
        self.assertEqual(
            transport["http_date_role"],
            "HTTP_RESPONSE_ORIGIN_DATE_NOT_PAGE_REVISION",
        )
        self.assertEqual(
            transport["http_last_modified_role"],
            "HTTP_REPRESENTATION_METADATA_NOT_PAGE_NATIVE_REVISION",
        )
        self.assertFalse(first["http_headers_accepted_as_page_revision"])
        self.assertEqual(
            transport["http_last_modified_instant"],
            first["page_native_revision_evidence"]["signals"][1]["normalized_value"],
        )
        self.assertEqual(json.loads(artifact_raw)["http_header_page_revision_promotion_count"], 0)
        contract.validate_artifact_bytes(artifact_raw, **kwargs)

    def test_signal_permutation_builds_identical_bytes(self) -> None:
        kwargs, artifact_raw, _receipt_raw = _bundle()
        permuted = deepcopy(kwargs["page_revision_records"])
        permuted[0]["signals"].reverse()
        material = dict(permuted[0])
        material.pop("record_sha256")
        material["signals"] = sorted(material["signals"], key=lambda item: item["kind"])
        permuted[0]["record_sha256"] = contract.canonical_sha256(material)
        self.assertEqual(
            contract.build_artifact_bytes(
                **{**kwargs, "page_revision_records": permuted}
            ),
            artifact_raw,
        )

    def test_not_exposed_and_located_cardinality_fail_closed(self) -> None:
        kwargs, _artifact, _receipt = _bundle()
        variants = []
        bad = deepcopy(kwargs["page_revision_records"])
        bad[0]["native_revision_status"] = "NOT_EXPOSED"
        variants.append(bad)
        bad = deepcopy(kwargs["page_revision_records"])
        bad[2]["native_revision_status"] = "PRESENTED_LOCATED"
        variants.append(bad)
        for records in variants:
            material = dict(records[0] if records[0] != kwargs["page_revision_records"][0] else records[2])
            target = 0 if records[0] != kwargs["page_revision_records"][0] else 2
            material.pop("record_sha256")
            material["signals"] = sorted(material["signals"], key=lambda item: item["kind"])
            records[target]["record_sha256"] = contract.canonical_sha256(material)
            with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
                contract.build_artifact_bytes(
                    **{**kwargs, "page_revision_records": records}
                )

    def test_locator_span_hash_payload_and_capture_row_swaps_are_rejected(self) -> None:
        kwargs, artifact_raw, receipt_raw = _bundle()
        mutations = (
            ("value_end", lambda value: value - 1),
            ("context_sha256", lambda _value: "f" * 64),
            ("value_sha256", lambda _value: "f" * 64),
        )
        for field, mutate in mutations:
            bad = deepcopy(kwargs["page_revision_records"])
            bad[0]["signals"][0][field] = mutate(bad[0]["signals"][0][field])
            material = dict(bad[0])
            material.pop("record_sha256")
            material["signals"] = sorted(material["signals"], key=lambda item: item["kind"])
            bad[0]["record_sha256"] = contract.canonical_sha256(material)
            with self.subTest(field=field), self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
                contract.build_artifact_bytes(
                    **{**kwargs, "page_revision_records": bad}
                )
        bad = deepcopy(kwargs["page_revision_records"])
        bad[0]["capture_row_sha256"] = bad[1]["capture_row_sha256"]
        material = dict(bad[0]); material.pop("record_sha256")
        material["signals"] = sorted(material["signals"], key=lambda item: item["kind"])
        bad[0]["record_sha256"] = contract.canonical_sha256(material)
        with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
            contract.build_artifact_bytes(**{**kwargs, "page_revision_records": bad})
        changed_payloads = dict(kwargs["raw_payloads_by_seed"])
        first_id = next(iter(changed_payloads))
        changed_payloads[first_id] += b"tamper"
        with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
            contract.validate_artifact_bytes(
                artifact_raw, **{**kwargs, "raw_payloads_by_seed": changed_payloads}
            )
        changed_receipt = receipt_raw[:-2] + b" \n"
        with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
            contract.build_artifact_bytes(
                **{**kwargs, "intake_receipt_raw": changed_receipt}
            )

    def test_duplicate_kind_and_header_origin_syntax_are_rejected(self) -> None:
        kwargs, _artifact, _receipt = _bundle()
        variants = []
        bad = deepcopy(kwargs["page_revision_records"])
        bad[0]["signals"].append(deepcopy(bad[0]["signals"][0]))
        variants.append(bad)
        bad = deepcopy(kwargs["page_revision_records"])
        bad[0]["signals"][0]["syntax"] = "HTTP_LAST_MODIFIED"
        variants.append(bad)
        bad = deepcopy(kwargs["page_revision_records"])
        published = next(
            item for item in bad[0]["signals"] if item["kind"] == "PUBLISHED_AT"
        )
        published["syntax"] = "JSON_LD_DATE_MODIFIED"
        variants.append(bad)
        for records in variants:
            material = dict(records[0]); material.pop("record_sha256")
            material["signals"] = sorted(material["signals"], key=lambda item: item["kind"])
            records[0]["record_sha256"] = contract.canonical_sha256(material)
            with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
                contract.build_artifact_bytes(
                    **{**kwargs, "page_revision_records": records}
                )

    def test_timestamp_normalization_and_chronology_are_recomputed(self) -> None:
        kwargs, _artifact, _receipt = _bundle()
        for normalized in ("2026-09-01T01:00:00Z", "2026-08-31T16:00:00+00:00"):
            bad = deepcopy(kwargs["page_revision_records"])
            bad[0]["signals"][0]["normalized_value"] = normalized
            material = dict(bad[0]); material.pop("record_sha256")
            material["signals"] = sorted(material["signals"], key=lambda item: item["kind"])
            bad[0]["record_sha256"] = contract.canonical_sha256(material)
            with self.subTest(normalized=normalized), self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
                contract.build_artifact_bytes(**{**kwargs, "page_revision_records": bad})
        bad_payloads = dict(kwargs["raw_payloads_by_seed"])
        first_id = next(iter(bad_payloads))
        bad_payloads[first_id] = (
            b'{"datePublished":"2026-09-03T00:00:00Z",'
            b'"dateModified":"2026-09-02T00:00:00Z"}\n'
        )
        seed_raw, bad_payloads, records, intake, receipt = _capture_bundle(bad_payloads)
        rows = json.loads(intake)["rows"]
        first_payload = bad_payloads[first_id]
        first_signals = [
            _signal(
                first_payload, kind="PUBLISHED_AT",
                syntax="JSON_LD_DATE_PUBLISHED",
                value="2026-09-03T00:00:00Z",
                normalized="2026-09-03T00:00:00Z",
            ),
            _signal(
                first_payload, kind="MODIFIED_AT",
                syntax="JSON_LD_DATE_MODIFIED",
                value="2026-09-02T00:00:00Z",
                normalized="2026-09-02T00:00:00Z",
            ),
        ]
        pages = [
            _page_record(
                sequence=index + 1, seed_id=row["seed_id"],
                capture_row_sha256=row["row_sha256"],
                status="PRESENTED_LOCATED" if index == 0 else "NOT_EXPOSED",
                signals=first_signals if index == 0 else [],
            )
            for index, row in enumerate(rows)
        ]
        with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
            contract.build_artifact_bytes(
                seed_registry_raw=seed_raw, presented_records=records,
                raw_payloads_by_seed=bad_payloads, intake_raw=intake,
                intake_receipt_raw=receipt, page_revision_records=pages,
            )

    def test_future_page_timestamp_and_unknown_offset_are_rejected(self) -> None:
        for value in ("2099-01-01T00:00:00Z", "2026-09-01T00:00:00-00:00"):
            payloads = _payloads()
            first_id = next(iter(payloads))
            payloads[first_id] = (
                '{"datePublished":"' + value + '"}\n'
            ).encode("utf-8")
            signal = _signal(
                payloads[first_id], kind="PUBLISHED_AT",
                syntax="JSON_LD_DATE_PUBLISHED", value=value,
                normalized=value if value.endswith("Z") else "2026-09-01T00:00:00Z",
            )
            kwargs = _kwargs_with_first_signals(payloads, [signal])
            with self.subTest(value=value), self.assertRaises(
                contract.P0PresentedHttpCaptureTemporalEvidenceV2Error
            ):
                contract.build_artifact_bytes(**kwargs)

    def test_page_native_marker_binding_and_unique_value_role_are_enforced(self) -> None:
        payloads = _payloads()
        first_id = next(iter(payloads))
        value = "2026-09-01T00:00:00Z"
        payloads[first_id] = f"unrelated comment {value}\n".encode("utf-8")
        signal = _signal(
            payloads[first_id], kind="PUBLISHED_AT",
            syntax="JSON_LD_DATE_PUBLISHED", value=value, normalized=value,
        )
        with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
            contract.build_artifact_bytes(
                **_kwargs_with_first_signals(payloads, [signal])
            )

        payloads = _payloads()
        first_id = next(iter(payloads))
        payloads[first_id] = (
            f'{{"datePublished":"{value}","dateModified":"{value}"}}\n'
        ).encode("utf-8")
        overlapping = [
            _signal(
                payloads[first_id], kind="PUBLISHED_AT",
                syntax="JSON_LD_DATE_PUBLISHED", value=value, normalized=value,
            ),
            _signal(
                payloads[first_id], kind="MODIFIED_AT",
                syntax="JSON_LD_DATE_MODIFIED", value=value, normalized=value,
            ),
        ]
        with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
            contract.build_artifact_bytes(
                **_kwargs_with_first_signals(payloads, overlapping)
            )

    def test_locator_must_point_to_its_exact_marker_value_occurrence(self) -> None:
        value = "2026-09-01T00:00:00Z"
        payloads = _payloads()
        first_id = next(iter(payloads))
        payload = (
            f'{{"datePublished":"{value}","dateModified":"{value}"}}\n'
        ).encode("utf-8")
        payloads[first_id] = payload
        first_start = payload.index(value.encode("utf-8"))
        second_start = payload.index(value.encode("utf-8"), first_start + 1)
        published = _signal(
            payload, kind="PUBLISHED_AT", syntax="JSON_LD_DATE_PUBLISHED",
            value=value, normalized=value,
        )
        modified = _signal(
            payload, kind="MODIFIED_AT", syntax="JSON_LD_DATE_MODIFIED",
            value=value, normalized=value,
        )
        published["value_start"] = second_start
        published["value_end"] = second_start + len(value)
        modified["value_start"] = first_start
        modified["value_end"] = first_start + len(value)
        with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
            contract.build_artifact_bytes(
                **_kwargs_with_first_signals(payloads, [published, modified])
            )

        payloads = _payloads()
        first_id = next(iter(payloads))
        payload = b'<div data-version="rev-42">rev-42</div>\n'
        payloads[first_id] = payload
        version = _signal(
            payload, kind="VERSION_ID", syntax="SITE_NATIVE_VERSION_TOKEN",
            value="rev-42", normalized="rev-42",
        )
        decoy_start = payload.rindex(b"rev-42")
        version["value_start"] = decoy_start
        version["value_end"] = decoy_start + len(b"rev-42")
        with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
            contract.build_artifact_bytes(
                **_kwargs_with_first_signals(payloads, [version])
            )

    def test_json_ld_top_level_and_native_attribute_boundaries_are_enforced(self) -> None:
        value = "2026-09-01T00:00:00Z"
        payloads = _payloads()
        first_id = next(iter(payloads))
        payload = (
            f'{{"nested":{{"datePublished":"{value}"}},'
            f'"datePublished":"{value}"}}\n'
        ).encode("utf-8")
        payloads[first_id] = payload
        nested = _signal(
            payload, kind="PUBLISHED_AT", syntax="JSON_LD_DATE_PUBLISHED",
            value=value, normalized=value,
        )
        with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
            contract.build_artifact_bytes(
                **_kwargs_with_first_signals(payloads, [nested])
            )

        payloads = _payloads()
        first_id = next(iter(payloads))
        payload = b'<div not-data-version="rev-42"></div>\n'
        payloads[first_id] = payload
        suffix = _signal(
            payload, kind="VERSION_ID", syntax="SITE_NATIVE_VERSION_TOKEN",
            value="rev-42", normalized="rev-42",
        )
        with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
            contract.build_artifact_bytes(
                **_kwargs_with_first_signals(payloads, [suffix])
            )
        cropped_kwargs = _kwargs_with_first_signals(payloads, [suffix])
        cropped_signal = cropped_kwargs["page_revision_records"][0]["signals"][0]
        cropped_signal["context_start"] = payload.index(b"data-version")
        cropped_signal["context_end"] = cropped_signal["value_end"] + 1
        cropped_signal["context_sha256"] = _raw_hash(
            payload[
                cropped_signal["context_start"]:cropped_signal["context_end"]
            ]
        )
        _reseal_page_record(cropped_kwargs["page_revision_records"][0])
        with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
            contract.build_artifact_bytes(**cropped_kwargs)
        _valid_kwargs, valid_artifact_raw, valid_receipt_raw = _bundle()
        with self.assertRaises(parent.P0PresentedHttpCaptureTemporalEvidenceV2ParentError):
            parent.validate_parent_replay(
                **cropped_kwargs, temporal_artifact_raw=valid_artifact_raw,
                child_receipt_raw=valid_receipt_raw,
            )

    def test_http_last_modified_after_date_is_rejected(self) -> None:
        payloads = _payloads()
        seed_raw = seed_contract.build_registry_bytes()
        records = _capture_records(payloads)
        records[0]["source_timestamp_evidence"] = _timestamp_evidence(
            date_header="Wed, 02 Sep 2026 00:00:00 GMT",
            last_modified_header="Thu, 03 Sep 2026 00:00:00 GMT",
            source_timestamp="2026-09-02T00:00:00Z",
            basis="PRESENTED_HTTP_DATE",
        )
        intake = capture.build_intake_bytes(
            seed_registry_raw=seed_raw, presented_records=records,
            raw_payloads_by_seed=payloads,
        )
        receipt = capture.build_receipt_bytes(
            intake, seed_registry_raw=seed_raw, presented_records=records,
            raw_payloads_by_seed=payloads,
        )
        with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
            contract.build_artifact_bytes(
                seed_registry_raw=seed_raw, presented_records=records,
                raw_payloads_by_seed=payloads, intake_raw=intake,
                intake_receipt_raw=receipt,
                page_revision_records=_page_records(intake, payloads),
            )

    def test_http_metadata_after_capture_observation_is_rejected(self) -> None:
        payloads = _payloads()
        seed_raw = seed_contract.build_registry_bytes()
        records = _capture_records(payloads)
        records[0]["source_timestamp_evidence"] = _timestamp_evidence(
            date_header="Thu, 01 Jan 2099 00:00:00 GMT",
            source_timestamp="2099-01-01T00:00:00Z",
            basis="PRESENTED_HTTP_DATE",
        )
        intake = capture.build_intake_bytes(
            seed_registry_raw=seed_raw, presented_records=records,
            raw_payloads_by_seed=payloads,
        )
        receipt = capture.build_receipt_bytes(
            intake, seed_registry_raw=seed_raw, presented_records=records,
            raw_payloads_by_seed=payloads,
        )
        with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
            contract.build_artifact_bytes(
                seed_registry_raw=seed_raw, presented_records=records,
                raw_payloads_by_seed=payloads, intake_raw=intake,
                intake_receipt_raw=receipt,
                page_revision_records=_page_records(intake, payloads),
            )

    def test_version_token_and_exact_signal_limit_are_enforced(self) -> None:
        kwargs, _artifact, _receipt = _bundle()
        bad = deepcopy(kwargs["page_revision_records"])
        signal = bad[1]["signals"][0]
        signal["presented_value"] = "rev 42"
        signal["normalized_value"] = "rev 42"
        material = dict(bad[1]); material.pop("record_sha256")
        material["signals"] = sorted(material["signals"], key=lambda item: item["kind"])
        bad[1]["record_sha256"] = contract.canonical_sha256(material)
        with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
            contract.build_artifact_bytes(**{**kwargs, "page_revision_records": bad})
        bad = deepcopy(kwargs["page_revision_records"])
        extra = deepcopy(bad[0]["signals"][0])
        for kind in ("VERSION_ID", "VERSION_ID"):
            item = deepcopy(extra)
            item["kind"] = kind
            item["syntax"] = "SITE_NATIVE_VERSION_TOKEN"
            bad[0]["signals"].append(item)
        material = dict(bad[0]); material.pop("record_sha256")
        material["signals"] = sorted(material["signals"], key=lambda item: item["kind"])
        bad[0]["record_sha256"] = contract.canonical_sha256(material)
        with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
            contract.build_artifact_bytes(**{**kwargs, "page_revision_records": bad})

    def test_bool_offsets_and_context_over_limit_are_rejected(self) -> None:
        kwargs, _artifact, _receipt = _bundle()
        bad = deepcopy(kwargs["page_revision_records"])
        bad[0]["signals"][0]["value_start"] = False
        material = dict(bad[0]); material.pop("record_sha256")
        material["signals"] = sorted(material["signals"], key=lambda item: item["kind"])
        bad[0]["record_sha256"] = contract.canonical_sha256(material)
        with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
            contract.build_artifact_bytes(**{**kwargs, "page_revision_records": bad})
        payloads = _payloads()
        first_id = next(iter(payloads))
        payloads[first_id] = b"x" * 513 + b"2026-09-01T00:00:00Z"
        seed_raw, payloads, records, intake, receipt = _capture_bundle(payloads)
        rows = json.loads(intake)["rows"]
        signal = _signal(
            payloads[first_id], kind="PUBLISHED_AT",
            syntax="JSON_LD_DATE_PUBLISHED", value="2026-09-01T00:00:00Z",
            normalized="2026-09-01T00:00:00Z",
        )
        pages = [
            _page_record(
                sequence=i + 1, seed_id=row["seed_id"],
                capture_row_sha256=row["row_sha256"],
                status="PRESENTED_LOCATED" if i == 0 else "NOT_EXPOSED",
                signals=[signal] if i == 0 else [],
            ) for i, row in enumerate(rows)
        ]
        with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
            contract.build_artifact_bytes(
                seed_registry_raw=seed_raw, presented_records=records,
                raw_payloads_by_seed=payloads, intake_raw=intake,
                intake_receipt_raw=receipt, page_revision_records=pages,
            )

    def test_page_record_resource_preflight_runs_before_record_hashing(self) -> None:
        kwargs, _artifact, _receipt = _bundle()
        bad = deepcopy(kwargs["page_revision_records"])
        bad[0]["signals"][0]["presented_value"] = "x" * 129
        with self.assertRaisesRegex(
            contract.P0PresentedHttpCaptureTemporalEvidenceV2Error,
            "presented_value text invalid",
        ):
            contract.build_artifact_bytes(
                **{**kwargs, "page_revision_records": bad}
            )
        bad = deepcopy(kwargs["page_revision_records"])
        bad[0]["signals"][0]["context_start"] = 10 ** 10_000
        with self.assertRaisesRegex(
            contract.P0PresentedHttpCaptureTemporalEvidenceV2Error,
            "locator preflight invalid",
        ):
            contract.build_artifact_bytes(
                **{**kwargs, "page_revision_records": bad}
            )

    def test_artifacts_omit_raw_context_but_disclose_normalized_scalars(self) -> None:
        kwargs, artifact_raw, receipt_raw = _bundle()
        parent_receipt = parent.validate_parent_replay(
            **kwargs, temporal_artifact_raw=artifact_raw,
            child_receipt_raw=receipt_raw,
        )
        parent_raw = contract.canonical_file_bytes(parent_receipt)
        for forbidden in (
            b'"datePublished"', b'"dateModified"',
            b"2026-09-01T01:00:00+09:00", b'<meta data-version="rev-42">',
        ):
            self.assertNotIn(forbidden, artifact_raw)
            self.assertNotIn(forbidden, receipt_raw)
            self.assertNotIn(forbidden, parent_raw)
        self.assertIn(b"rev-42", artifact_raw)
        self.assertTrue(
            contract.COMPONENT_MANIFEST[
                "page_revision_normalized_scalar_exposed_in_artifact"
            ]
        )
        self.assertFalse(
            contract.COMPONENT_MANIFEST[
                "page_revision_raw_context_or_unnormalized_span_exposed_in_artifact"
            ]
        )

    def test_zero_signal_receipt_and_replay_idempotency_are_truthful(self) -> None:
        kwargs, artifact_raw, receipt_raw = _bundle()
        artifact = json.loads(artifact_raw)
        receipt = json.loads(receipt_raw)
        self.assertEqual(
            artifact["replay_idempotency_key_sha256"],
            receipt["replay_idempotency_key_sha256"],
        )
        self.assertTrue(receipt["all_presented_page_revision_spans_verified"])

        pages = deepcopy(kwargs["page_revision_records"])
        for page in pages:
            page["native_revision_status"] = "NOT_EXPOSED"
            page["signals"] = []
            _reseal_page_record(page)
        zero_kwargs = {**kwargs, "page_revision_records": pages}
        zero_artifact_raw = contract.build_artifact_bytes(**zero_kwargs)
        zero_receipt_raw = contract.build_receipt_bytes(
            zero_artifact_raw, **zero_kwargs
        )
        zero_receipt = json.loads(zero_receipt_raw)
        self.assertEqual(zero_receipt["page_revision_signal_count"], 0)
        self.assertTrue(
            zero_receipt["all_presented_page_revision_spans_verified"]
        )
        self.assertEqual(
            json.loads(zero_artifact_raw)["replay_idempotency_key_sha256"],
            zero_receipt["replay_idempotency_key_sha256"],
        )

    def test_all_authority_credit_metric_and_action_fields_remain_false(self) -> None:
        _kwargs, artifact_raw, receipt_raw = _bundle()
        artifact = json.loads(artifact_raw)
        receipt = json.loads(receipt_raw)
        for value in (artifact, receipt, *artifact["rows"]):
            for field in contract._FALSE_CAPABILITIES:
                self.assertIs(value[field], False)
        self.assertEqual(artifact["credited_actual_source_snapshot_count"], 0)
        self.assertEqual(receipt["actual_credit_count"], 0)
        self.assertEqual(artifact["metric_denominator"], 0)
        self.assertEqual(artifact["gate_status"], "NO_GO_PRESENTED_TEMPORAL_EVIDENCE_ONLY")

    def test_fully_resealed_authority_and_receipt_forgery_are_rejected(self) -> None:
        kwargs, artifact_raw, receipt_raw = _bundle()
        forged_artifact = json.loads(artifact_raw)
        forged_artifact["actual_authority_granted"] = True
        forged_artifact_raw = _reseal(forged_artifact, "artifact_sha256")
        with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
            contract.validate_artifact_bytes(forged_artifact_raw, **kwargs)
        with self.assertRaises(parent.P0PresentedHttpCaptureTemporalEvidenceV2ParentError):
            parent.validate_parent_replay(
                **kwargs, temporal_artifact_raw=forged_artifact_raw,
                child_receipt_raw=receipt_raw,
            )
        forged_receipt = json.loads(receipt_raw)
        forged_receipt["actual_credit_count"] = 1
        forged_receipt_raw = _reseal(forged_receipt, "receipt_sha256")
        with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
            contract.validate_receipt_bytes(
                forged_receipt_raw, artifact_raw=artifact_raw, **kwargs
            )

    def test_noncanonical_duplicate_key_bom_and_crlf_are_rejected(self) -> None:
        kwargs, artifact_raw, _receipt_raw = _bundle()
        variants = (
            artifact_raw.replace(b'{', b'{"schema_version":"duplicate",', 1),
            b"\xef\xbb\xbf" + artifact_raw,
            artifact_raw.replace(b"\n", b"\r\n"),
            artifact_raw[:-1] + b" \n",
        )
        for raw in variants:
            with self.subTest(prefix=raw[:20]), self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
                contract.validate_artifact_bytes(raw, **kwargs)

    def test_invalid_unselected_http_header_is_rejected_by_temporal_successor(self) -> None:
        seed_raw, payloads, records, _intake, _receipt = _capture_bundle()
        records[2]["source_timestamp_evidence"] = _timestamp_evidence(
            date_header="not-a-date", basis="NOT_EXPOSED"
        )
        intake = capture.build_intake_bytes(
            seed_registry_raw=seed_raw, presented_records=records,
            raw_payloads_by_seed=payloads,
        )
        intake_receipt = capture.build_receipt_bytes(
            intake, seed_registry_raw=seed_raw, presented_records=records,
            raw_payloads_by_seed=payloads,
        )
        pages = _page_records(intake, payloads)
        with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
            contract.build_artifact_bytes(
                seed_registry_raw=seed_raw, presented_records=records,
                raw_payloads_by_seed=payloads, intake_raw=intake,
                intake_receipt_raw=intake_receipt,
                page_revision_records=pages,
            )

    def test_component_and_parent_helper_or_literal_tamper_fail_closed(self) -> None:
        kwargs, artifact_raw, receipt_raw = _bundle()
        with patch.object(contract, "GATE_STATUS", "GO"):
            with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
                contract.build_artifact_bytes(**kwargs)
        with patch.object(contract, "_page_projection", lambda *args, **kwargs: {}):
            with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
                contract.build_artifact_bytes(**kwargs)
        with patch.object(parent, "_page", lambda *args, **kwargs: {}):
            with self.assertRaises(parent.P0PresentedHttpCaptureTemporalEvidenceV2ParentError):
                parent.validate_parent_replay(
                    **kwargs, temporal_artifact_raw=artifact_raw,
                    child_receipt_raw=receipt_raw,
                )
        with patch.object(contract._integer, "__defaults__", (-999,)):
            with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
                contract.build_artifact_bytes(**kwargs)
        with patch.object(parent._int, "__defaults__", (-999,)):
            with self.assertRaises(parent.P0PresentedHttpCaptureTemporalEvidenceV2ParentError):
                parent.validate_parent_replay(
                    **kwargs, temporal_artifact_raw=artifact_raw,
                    child_receipt_raw=receipt_raw,
                )
        with patch.object(contract.re, "fullmatch", lambda *_args, **_kwargs: True):
            with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
                contract.build_artifact_bytes(**kwargs)
        with patch.object(capture.validate_intake_bytes, "__defaults__", (None,)):
            with self.assertRaises(contract.P0PresentedHttpCaptureTemporalEvidenceV2Error):
                contract.build_artifact_bytes(**kwargs)
        with patch.object(
            parent.capture_parent.validate_parent_replay, "__defaults__", (None,)
        ):
            with self.assertRaises(parent.P0PresentedHttpCaptureTemporalEvidenceV2ParentError):
                parent.validate_parent_replay(
                    **kwargs, temporal_artifact_raw=artifact_raw,
                    child_receipt_raw=receipt_raw,
                )

    def test_parent_source_has_no_temporal_or_capture_producer_import(self) -> None:
        tree = ast.parse(PARENT_PATH.read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imports.append((node.module or "") + "." + ".".join(alias.name for alias in node.names))
            elif isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
        text = "\n".join(imports)
        self.assertNotIn("temporal_evidence_v2_contract", text)
        self.assertNotIn("http_capture_intake_v1_contract", text)
        self.assertIn("http_capture_intake_v1_parent_validator", text)

    def test_manifest_hash_is_stable_and_parent_pinned(self) -> None:
        self.assertEqual(
            contract.COMPONENT_MANIFEST_SHA256,
            "8961fb8c5cc798d04eef08370563d7407344a70da4b43ea685406024f4f2cb8b",
        )
        self.assertEqual(
            parent.EXPECTED_COMPONENT_MANIFEST_SHA256,
            contract.COMPONENT_MANIFEST_SHA256,
        )
        self.assertEqual(
            contract.PREDECESSOR_COMPONENT_MANIFEST_SHA256,
            capture.COMPONENT_MANIFEST_SHA256,
        )


if __name__ == "__main__":
    unittest.main()
