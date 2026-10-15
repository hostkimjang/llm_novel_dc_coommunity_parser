"""A-context 전용 byte-exact event verifier 회귀 테스트."""

from __future__ import annotations

from copy import deepcopy
import json
import unittest

from llm_batch.grounding import p0_actual_a_context_contract as a_contract
from llm_batch.grounding import p0_actual_a_event_bytes as event_bytes
from llm_batch.grounding import p0_actual_packet_contract as packet_contract
from tests import test_p0_actual_packet_contract as packet_fixtures


def _jsonl(rows: list[dict[str, object]]) -> bytes:
    return b"".join(event_bytes.canonical_bytes(row) + b"\n" for row in rows)


def _json(value: dict[str, object]) -> bytes:
    return event_bytes.canonical_bytes(value) + b"\n"


def _materials() -> dict[str, object]:
    artifacts, _, _ = packet_fixtures._content_values()
    contexts = deepcopy(artifacts["a_contexts"])
    events = deepcopy(artifacts["a_annotation_events"])
    claim_ids = {
        claim_id for context in contexts for claim_id in context["source_claim_ids"]
    }
    claims = sorted(
        [
            deepcopy(claim)
            for claim in artifacts["source_claims"]
            if claim["claim_id"] in claim_ids
        ],
        key=lambda item: item["claim_id"],
    )
    return {
        "claims": claims,
        "contexts": contexts,
        "events": events,
        "seal": deepcopy(artifacts["a_subject_selection_seal"]),
    }


def _bytes(values: dict[str, object]) -> dict[str, bytes]:
    return {
        "source_claim_bytes": _jsonl(values["claims"]),
        "a_context_bytes": _jsonl(values["contexts"]),
        "a_event_bytes": _jsonl(values["events"]),
        "a_subject_selection_seal_bytes": _json(values["seal"]),
    }


def _rehash_context(context: dict[str, object]) -> None:
    context["row_sha256"] = a_contract.canonical_sha256(
        {key: value for key, value in context.items() if key != "row_sha256"}
    )


def _rehash_event(event: dict[str, object]) -> None:
    event["event_sha256"] = a_contract.annotation_event_sha256(event)
    event["row_sha256"] = a_contract.canonical_sha256(
        {key: value for key, value in event.items() if key != "row_sha256"}
    )


class P0ActualAEventBytesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.values = _materials()
        cls.raw = _bytes(cls.values)

    def _verify(self, raw: dict[str, bytes] | None = None) -> dict[str, object]:
        return event_bytes.verify_a_event_bytes(
            **(self.raw if raw is None else raw),
            expected_origin=packet_contract.EXAMPLE_ORIGIN,
        )

    def test_positive_receipt_binds_all_bytes_and_remains_no_go(self) -> None:
        receipt = self._verify()
        self.assertEqual(20, receipt["a_context_row_count"])
        self.assertEqual(20, receipt["a_event_row_count"])
        self.assertEqual(20, receipt["head_count"])
        self.assertTrue(receipt["canonical_input_bytes_verified"])
        self.assertTrue(receipt["a_event_hash_chains_verified"])
        self.assertTrue(receipt["latest_event_projection_verified"])
        self.assertEqual(0, receipt["credited_actual_a_context_review_count"])
        for field in (
            "filesystem_handle_trust_verified",
            "durable_predecessor_verified",
            "annotation_append_only_verified",
            "owner_authority_verified",
            "runtime_noninterference_verified",
            "actual_authority_granted",
            "production_approval",
            "full_scan_approval",
            "p0_phase_exit",
        ):
            self.assertFalse(receipt[field], field)

    def test_actual_origin_is_validated_separately_and_still_receives_zero_credit(self) -> None:
        artifacts, _, _ = packet_fixtures._content_values(
            origin=packet_contract.ACTUAL_ORIGIN
        )
        contexts = deepcopy(artifacts["a_contexts"])
        claim_ids = {
            claim_id
            for context in contexts
            for claim_id in context["source_claim_ids"]
        }
        values = {
            "claims": sorted(
                [
                    deepcopy(claim)
                    for claim in artifacts["source_claims"]
                    if claim["claim_id"] in claim_ids
                ],
                key=lambda item: item["claim_id"],
            ),
            "contexts": contexts,
            "events": deepcopy(artifacts["a_annotation_events"]),
            "seal": deepcopy(artifacts["a_subject_selection_seal"]),
        }
        receipt = event_bytes.verify_a_event_bytes(
            **_bytes(values),
            expected_origin=packet_contract.ACTUAL_ORIGIN,
        )
        self.assertEqual(packet_contract.ACTUAL_ORIGIN, receipt["record_origin"])
        self.assertEqual(0, receipt["credited_actual_a_context_review_count"])
        self.assertFalse(receipt["actual_authority_granted"])

    def test_twenty_contexts_allow_a_valid_twenty_first_recheck_event(self) -> None:
        values = _materials()
        first = values["events"][0]
        recheck = deepcopy(first)
        recheck.update(
            {
                "journal_sequence": 2,
                "event_id": "EXAMPLE:PACKET:A:EVENT:01:RECHECK",
                "previous_event_id": first["event_id"],
                "previous_event_sha256": first["event_sha256"],
                "event_kind": "INTRA_RATER_RECHECK",
                "supersedes_event_ids": [first["event_id"]],
                "occurred_at": "2026-09-03T01:00:00Z",
                "independent_review": False,
            }
        )
        _rehash_event(recheck)
        values["events"].insert(1, recheck)
        context = values["contexts"][0]
        context["latest_annotation_event_id"] = recheck["event_id"]
        context["latest_annotation_event_sha256"] = recheck["event_sha256"]
        _rehash_context(context)

        receipt = self._verify(_bytes(values))
        self.assertEqual(20, receipt["a_context_row_count"])
        self.assertEqual(21, receipt["a_event_row_count"])
        self.assertEqual(20, receipt["head_count"])
        self.assertTrue(receipt["a_event_hash_chains_verified"])

    def test_event_jsonl_rejects_duplicate_key_bom_crlf_missing_lf_and_noncanonical(self) -> None:
        original = self.raw["a_event_bytes"]
        mutations = {
            "duplicate JSON key": original.replace(
                b'"action_applied":false,',
                b'"action_applied":false,"action_applied":false,',
                1,
            ),
            "UTF-8 BOM": b"\xef\xbb\xbf" + original,
            "LF framing": original.replace(b"\n", b"\r\n", 1),
            "final LF": original[:-1],
            "not canonical JSON": b"{ " + original[1:],
        }
        for expected, value in mutations.items():
            raw = dict(self.raw)
            raw["a_event_bytes"] = value
            with self.subTest(expected=expected), self.assertRaisesRegex(
                event_bytes.P0ActualAEventBytesError, expected
            ):
                self._verify(raw)

    def test_every_input_requires_canonical_byte_framing(self) -> None:
        for name in (
            "source_claim_bytes",
            "a_context_bytes",
            "a_subject_selection_seal_bytes",
        ):
            raw = dict(self.raw)
            raw[name] = raw[name][:-1]
            with self.subTest(name=name), self.assertRaisesRegex(
                event_bytes.P0ActualAEventBytesError, "final LF"
            ):
                self._verify(raw)

    def test_orphan_event_is_rejected_after_valid_rehash(self) -> None:
        values = _materials()
        values["events"][0]["target_id"] = "EXAMPLE:ORPHAN:A:CONTEXT"
        _rehash_event(values["events"][0])
        with self.assertRaisesRegex(event_bytes.P0ActualAEventBytesError, "orphan"):
            self._verify(_bytes(values))

    def test_broken_chain_predecessor_binding_is_rejected(self) -> None:
        values = _materials()
        event = values["events"][0]
        event["journal_sequence"] = 2
        event["previous_event_id"] = "EXAMPLE:MISSING:PREDECESSOR"
        event["previous_event_sha256"] = "f" * 64
        event["event_kind"] = "INTRA_RATER_RECHECK"
        event["independent_review"] = False
        event["supersedes_event_ids"] = ["EXAMPLE:MISSING:PREDECESSOR"]
        _rehash_event(event)
        with self.assertRaisesRegex(
            event_bytes.P0ActualAEventBytesError,
            "sequence|journal|chain|supersession",
        ):
            self._verify(_bytes(values))

    def test_latest_event_mismatch_is_rejected(self) -> None:
        values = _materials()
        context = values["contexts"][0]
        context["latest_annotation_event_id"] = "EXAMPLE:FORGED:LATEST"
        _rehash_context(context)
        with self.assertRaisesRegex(
            event_bytes.P0ActualAEventBytesError, "latest human A event binding"
        ):
            self._verify(_bytes(values))

    def test_context_and_event_row_swaps_are_rejected(self) -> None:
        for field, expected in (
            ("contexts", "context JSONL row order"),
            ("events", "event JSONL row order"),
        ):
            values = _materials()
            values[field][0], values[field][1] = values[field][1], values[field][0]
            with self.subTest(field=field), self.assertRaisesRegex(
                event_bytes.P0ActualAEventBytesError, expected
            ):
                self._verify(_bytes(values))

    def test_semantic_context_event_swap_is_rejected(self) -> None:
        values = _materials()
        first, second = values["events"][:2]
        first["target_id"], second["target_id"] = second["target_id"], first["target_id"]
        first["target_subject_sha256"], second["target_subject_sha256"] = (
            second["target_subject_sha256"],
            first["target_subject_sha256"],
        )
        _rehash_event(first)
        _rehash_event(second)
        with self.assertRaisesRegex(
            event_bytes.P0ActualAEventBytesError,
            "latest human A event binding|journal|reviewer|evidence",
        ):
            self._verify(_bytes(values))

    def test_subject_seal_and_context_swap_cannot_be_rehashed_away(self) -> None:
        values = _materials()
        seal = values["seal"]
        seal["selected_subjects"][0], seal["selected_subjects"][1] = (
            seal["selected_subjects"][1],
            seal["selected_subjects"][0],
        )
        seal["selected_subjects_sha256"] = event_bytes.canonical_sha256(
            seal["selected_subjects"]
        )
        material = {key: value for key, value in seal.items() if key != "artifact_sha256"}
        seal["artifact_sha256"] = event_bytes.canonical_sha256(material)
        with self.assertRaisesRegex(
            event_bytes.P0ActualAEventBytesError, "selected subject projection"
        ):
            self._verify(_bytes(values))

    def test_exact_20_contexts_and_at_least_20_events_are_required(self) -> None:
        values = _materials()
        values["contexts"] = values["contexts"][:-1]
        values["events"] = values["events"][:-1]
        with self.assertRaisesRegex(
            event_bytes.P0ActualAEventBytesError, "exactly 20 contexts"
        ):
            self._verify(_bytes(values))

    def test_receipt_cannot_claim_authority_through_nested_context_receipt(self) -> None:
        receipt = self._verify()
        nested = receipt["a_context_receipt"]
        self.assertEqual(0, nested["actual_a_context_review_count"])
        self.assertFalse(nested["owner_key_verified"])
        self.assertEqual("SHADOW_ONLY", nested["authority"])


if __name__ == "__main__":
    unittest.main()
