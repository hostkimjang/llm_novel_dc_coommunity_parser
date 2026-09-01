import copy
import hashlib
import unittest

from src.llm_batch.measurement.observation_envelope import (
    OBSERVATION_ENVELOPE_SCHEMA,
    SIDECAR_RECEIPT_SCHEMA,
    ObservationEnvelopeError,
    build_observation_envelope,
    build_sidecar_receipt,
    canonical_sha256,
    reference_legacy_receipt,
    validate_observation_envelope,
    validate_sidecar_receipt,
)


def _sha(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


class ObservationEnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.scope = _sha("scope")
        self.binding = {
            "publication_scope_id": self.scope,
            "input_index": 3,
            "post_id": "post-3",
            "decision_id": _sha("decision"),
            "commit_sha256": _sha("commit"),
            "input_sha256": _sha("input"),
            "result_sha256": _sha("result"),
            "public_projection_sha256": _sha("projection"),
            "stable_result_sha256": _sha("stable"),
            "contract_input_fingerprint": _sha("fingerprint"),
        }
        self.coordinate = {
            "publication_scope_id": self.scope,
            "input_index": 3,
            "post_id": "post-3",
            "attempt_run_id": "attempt-3",
        }

    def envelope(self):
        return build_observation_envelope(
            observation_kind="PUBLICATION_DRIFT",
            producer="test.producer",
            producer_schema_version="producer_v1",
            rule_version="rule_v1",
            mode="AUDIT_ONLY",
            authority_class="OBSERVATIONAL_ONLY",
            coordinate=self.coordinate,
            publication_binding=self.binding,
            source_lineage={
                "source_kind": "FRESH_RESULT",
                "source_snapshot_sha256": _sha("snapshot"),
                "source_result_sha256": _sha("source-result"),
                "source_stable_result_sha256": _sha("source-stable"),
                "source_view_schema": "source_view_v1",
                "source_view_sha256": _sha("source-view"),
                "extractor_rule_version": "extractor_v1",
                "parent_lineage_root_sha256": _sha("lineage-root"),
            },
            payload_ref={"legacy_schema": "legacy_v1", "legacy_receipt_sha256": _sha("payload")},
            parent_refs=sorted([_sha("parent-a"), _sha("parent-b")]),
        )

    def test_build_validate_is_deterministic_and_non_public(self):
        envelope = self.envelope()
        self.assertEqual(envelope["schema_version"], OBSERVATION_ENVELOPE_SCHEMA)
        self.assertIs(envelope["public_apply"], False)
        self.assertEqual(validate_observation_envelope(envelope), envelope)
        self.assertEqual(envelope["envelope_sha256"], canonical_sha256({k: v for k, v in envelope.items() if k != "envelope_sha256"}))

    def test_envelope_rejects_extra_hash_and_parent_order(self):
        envelope = self.envelope()
        envelope["unexpected"] = True
        with self.assertRaises(ObservationEnvelopeError):
            validate_observation_envelope(envelope)
        envelope = self.envelope()
        envelope["parent_refs"] = list(reversed(envelope["parent_refs"]))
        with self.assertRaises(ObservationEnvelopeError):
            validate_observation_envelope(envelope)
        envelope = self.envelope()
        envelope["parent_refs"] = [envelope["parent_refs"][0]] * 2
        with self.assertRaises(ObservationEnvelopeError):
            validate_observation_envelope(envelope)

    def test_envelope_rejects_public_apply_and_hash_mismatch(self):
        envelope = self.envelope()
        envelope["public_apply"] = True
        with self.assertRaises(ObservationEnvelopeError):
            validate_observation_envelope(envelope)

    def test_envelope_nested_families_fail_closed(self):
        for family, key, replacement in (
            ("coordinate", "attempt_run_id", ""),
            ("publication_binding", "commit_sha256", "bad"),
            ("source_lineage", "source_view_sha256", "bad"),
            ("payload_ref", "legacy_schema", ""),
        ):
            envelope = self.envelope()
            envelope[family][key] = replacement
            with self.subTest(family=family):
                with self.assertRaises(ObservationEnvelopeError):
                    validate_observation_envelope(envelope)
        envelope = self.envelope()
        envelope["envelope_sha256"] = _sha("tampered")
        with self.assertRaises(ObservationEnvelopeError):
            validate_observation_envelope(envelope)

    def test_sidecar_receipt_roundtrip_and_strict_fields(self):
        envelope = self.envelope()
        receipt = build_sidecar_receipt(
            operation="APPEND",
            storage_kind="ATTEMPT_LOCAL_RUN_META",
            status="RECORDED",
            envelope_sha256=envelope["envelope_sha256"],
            publication_binding=self.binding,
            storage_binding={"ledger_schema": "ledger_v1", "scope_id": self.scope, "sequence": 1, "prev_frame_sha256": None, "frame_sha256": _sha("frame"), "readback_sha256": _sha("readback")},
            relationship="OBSERVED_FROM",
        )
        self.assertEqual(receipt["schema_version"], SIDECAR_RECEIPT_SCHEMA)
        self.assertIs(receipt["public_apply"], False)
        self.assertEqual(validate_sidecar_receipt(receipt), receipt)
        extra = dict(receipt, extra=True)
        with self.assertRaises(ObservationEnvelopeError):
            validate_sidecar_receipt(extra)
        missing = dict(receipt)
        missing.pop("relationship")
        with self.assertRaises(ObservationEnvelopeError):
            validate_sidecar_receipt(missing)

    def test_sidecar_rejects_public_apply_and_bad_parent(self):
        envelope = self.envelope()
        receipt = build_sidecar_receipt(
            operation="TRACE_LINK",
            storage_kind="RECOVERY_APPEND_ONLY_LEDGER",
            status="VALIDATED",
            envelope_sha256=envelope["envelope_sha256"],
            publication_binding=self.binding,
            storage_binding={"ledger_schema": "ledger_v1", "scope_id": self.scope, "sequence": 2, "prev_frame_sha256": _sha("previous"), "frame_sha256": _sha("frame"), "readback_sha256": _sha("readback")},
            relationship="MEASURED_AGAINST",
        )
        receipt["public_apply"] = True
        with self.assertRaises(ObservationEnvelopeError):
            validate_sidecar_receipt(receipt)

    def test_sidecar_nested_families_fail_closed(self):
        envelope = self.envelope()
        receipt = build_sidecar_receipt(
            operation="APPEND", storage_kind="ATTEMPT_LOCAL_RUN_META", status="RECORDED",
            envelope_sha256=envelope["envelope_sha256"], publication_binding=self.binding,
            storage_binding={"ledger_schema": "ledger_v1", "scope_id": self.scope, "sequence": 1,
                             "prev_frame_sha256": None, "frame_sha256": _sha("frame"),
                             "readback_sha256": _sha("readback")},
            relationship="OBSERVED_FROM",
        )
        for family, key, replacement in (
            ("publication_binding", "input_sha256", "bad"),
            ("storage_binding", "frame_sha256", "bad"),
        ):
            tampered = copy.deepcopy(receipt)
            tampered[family][key] = replacement
            with self.subTest(family=family):
                with self.assertRaises(ObservationEnvelopeError):
                    validate_sidecar_receipt(tampered)
        receipt = build_sidecar_receipt(
            operation="TRACE_LINK", storage_kind="DECISION_CALL_LEDGER", status="VALIDATED",
            envelope_sha256=envelope["envelope_sha256"], publication_binding=self.binding,
            storage_binding={"ledger_schema": "ledger_v1", "scope_id": self.scope, "sequence": 2, "prev_frame_sha256": _sha("previous"), "frame_sha256": _sha("frame"), "readback_sha256": _sha("readback")},
            relationship="TRACE_LINKED_TO",
        )
        receipt["relationship"] = "BAD_RELATIONSHIP"
        with self.assertRaises(ObservationEnvelopeError):
            validate_sidecar_receipt(receipt)

    def test_legacy_reference_does_not_mutate_input(self):
        legacy = {"schema_version": "legacy_v2", "receipt": {"ok": True}}
        before = copy.deepcopy(legacy)
        reference = reference_legacy_receipt(legacy, legacy_schema="legacy_v2")
        self.assertEqual(legacy, before)
        self.assertEqual(reference["legacy_schema"], "legacy_v2")
        self.assertEqual(reference["legacy_receipt_sha256"], canonical_sha256(legacy))


if __name__ == "__main__":
    unittest.main()
