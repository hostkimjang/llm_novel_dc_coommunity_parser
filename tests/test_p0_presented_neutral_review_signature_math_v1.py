from __future__ import annotations

import ast
import base64
from copy import deepcopy
import inspect
import json
import os
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_batch.grounding import p0_presented_neutral_review_signature_math_v1_contract as contract  # noqa: E402
from llm_batch.grounding import p0_presented_neutral_review_signature_math_v1_parent_validator as parent  # noqa: E402
from llm_batch.grounding import p0_windows_cng_ecdsa_p256 as cng_p256  # noqa: E402
from tests.test_p0_external_owner_asymmetric_signature import _TestOnlyCngSigner  # noqa: E402


KINDS = (
    contract.CAMPAIGN_POLICY_PREAUTHORIZATION,
    contract.REVIEW_LEASE,
    contract.HUMAN_REVIEW_RESULT,
    contract.FINAL_REVIEW_ATTESTATION,
)


def _reseal(value: dict[str, object]) -> dict[str, object]:
    material = {key: item for key, item in value.items() if key != "artifact_sha256"}
    return {**material, "artifact_sha256": contract.canonical_sha256(material)}


def _payload(kind: str, marker: str = "original") -> bytes:
    material = {
        "schema_version": "p0_test_presented_review_payload_v1",
        "record_origin": contract.RECORD_ORIGIN,
        "signature_kind": kind,
        "content_commitment_sha256": contract.canonical_sha256(
            {"kind": kind, "marker": marker}
        ),
        "action_applied": False,
        "operational_effect": contract.OPERATIONAL_EFFECT,
    }
    return contract.canonical_file_bytes(
        {**material, "artifact_sha256": contract.canonical_sha256(material)}
    )


def _object(raw: bytes) -> dict[str, object]:
    return json.loads(raw.decode("utf-8"))


@unittest.skipUnless(os.name == "nt", "Windows CNG is required")
class PresentedNeutralReviewSignatureMathV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.signers: list[_TestOnlyCngSigner] = []

    def tearDown(self) -> None:
        for signer in self.signers:
            signer.close()

    def _new_signer(self) -> _TestOnlyCngSigner:
        signer = _TestOnlyCngSigner()
        self.signers.append(signer)
        return signer

    def _bundle(
        self,
        kind: str = contract.HUMAN_REVIEW_RESULT,
        *,
        signer: _TestOnlyCngSigner | None = None,
        marker: str = "original",
        presented_issued_at: str = "2026-09-03T00:00:00Z",
        revocation_marker: str = "presented-revocation",
    ) -> dict[str, object]:
        signer = self._new_signer() if signer is None else signer
        payload = _payload(kind, marker)
        pin = contract.build_presented_review_key_pin_bytes(
            signature_kind=kind,
            trust_domain="review-trust-candidate",
            project_id="llm-novel-dc-community-parser",
            environment="p0-shadow",
            key_id=f"key-{kind.lower()}",
            key_epoch=1,
            public_key_x_base64=base64.b64encode(signer.x).decode("ascii"),
            public_key_y_base64=base64.b64encode(signer.y).decode("ascii"),
            signer_principal_commitment_sha256=contract.canonical_sha256(
                {"presented-principal": kind}
            ),
            authority_anchor_sha256=contract.canonical_sha256(
                {"presented-anchor": kind}
            ),
            presented_revocation_snapshot_raw_sha256=contract.canonical_sha256(
                {revocation_marker: kind, "epoch": 1}
            ),
        )
        subject = contract.build_presented_review_subject_bytes(
            signature_kind=kind,
            trust_domain="review-trust-candidate",
            project_id="llm-novel-dc-community-parser",
            environment="p0-shadow",
            campaign_id="campaign-candidate-001",
            run_id="run-candidate-001",
            subject_id=f"subject-{kind.lower()}",
            presented_issued_at=presented_issued_at,
            nonce_commitment_sha256=contract.canonical_sha256(
                {"nonce": kind, "marker": marker}
            ),
            payload_raw=payload,
            predecessor_subject_raw_sha256=None,
        )
        material = contract.build_presented_review_signature_envelope_material(
            public_key_pin_raw=pin, subject_raw=subject, payload_raw=payload
        )
        signature = signer.sign_low_s(contract.canonical_bytes(material))
        envelope = contract.seal_presented_review_signature_envelope_bytes(
            unsigned_material=material,
            signature_rs_base64=base64.b64encode(signature).decode("ascii"),
        )
        receipt = contract.validate_presented_neutral_review_signature_math(
            public_key_pin_raw=pin,
            subject_raw=subject,
            payload_raw=payload,
            signature_envelope_raw=envelope,
            expected_signature_kind=kind,
            expected_public_key_pin_raw_sha256=contract.raw_sha256(pin),
            expected_subject_raw_sha256=contract.raw_sha256(subject),
        )
        return {
            "signer": signer,
            "kind": kind,
            "payload": payload,
            "pin": pin,
            "subject": subject,
            "material": material,
            "envelope": envelope,
            "receipt": receipt,
            "receipt_raw": contract.canonical_file_bytes(receipt),
        }

    def _validate(self, bundle: dict[str, object], **overrides: object) -> dict[str, object]:
        args: dict[str, object] = {
            "public_key_pin_raw": bundle["pin"],
            "subject_raw": bundle["subject"],
            "payload_raw": bundle["payload"],
            "signature_envelope_raw": bundle["envelope"],
            "expected_signature_kind": bundle["kind"],
            "expected_public_key_pin_raw_sha256": contract.raw_sha256(bundle["pin"]),
            "expected_subject_raw_sha256": contract.raw_sha256(bundle["subject"]),
        }
        args.update(overrides)
        return contract.validate_presented_neutral_review_signature_math(**args)

    def _parent(self, bundle: dict[str, object], **overrides: object) -> dict[str, object]:
        args: dict[str, object] = {
            "public_key_pin_raw": bundle["pin"],
            "subject_raw": bundle["subject"],
            "payload_raw": bundle["payload"],
            "signature_envelope_raw": bundle["envelope"],
            "component_receipt_raw": bundle["receipt_raw"],
            "expected_signature_kind": bundle["kind"],
            "expected_public_key_pin_raw_sha256": contract.raw_sha256(bundle["pin"]),
            "expected_subject_raw_sha256": contract.raw_sha256(bundle["subject"]),
        }
        args.update(overrides)
        return parent.validate_presented_neutral_review_signature_math_against_raw_inputs(
            **args
        )

    def test_all_four_role_domain_profiles_pass_math_and_parent_replay(self) -> None:
        for kind in KINDS:
            with self.subTest(kind=kind):
                bundle = self._bundle(kind)
                receipt = bundle["receipt"]
                expected_role, expected_purpose, expected_domain = contract.SIGNATURE_PROFILE[kind]
                self.assertEqual(receipt["key_role"], expected_role)
                self.assertEqual(receipt["purpose"], expected_purpose)
                self.assertEqual(receipt["domain"], expected_domain)
                self.assertTrue(receipt["asymmetric_signature_math_verified"])
                replay = self._parent(bundle)
                self.assertTrue(replay["parent_separate_implementation_raw_replay_verified"])
                self.assertTrue(replay["parent_reexecuted_windows_cng_signature_math"])

    def test_receipt_truth_boundary_stays_false_and_zero(self) -> None:
        receipt = self._bundle()["receipt"]
        for field in (
            "external_key_provisioning_verified",
            "external_authority_anchor_verified",
            "signer_identity_verified",
            "reviewer_identity_verified",
            "reviewer_independence_verified",
            "reviewer_blinding_verified",
            "human_judgment_factuality_verified",
            "payload_semantics_verified",
            "trusted_time_verified",
            "revocation_state_verified",
            "durable_replay_prevention_verified",
            "code_identity_verified",
            "dependency_closure_verified",
            "trusted_cng_provider_provenance_verified",
            "process_isolation_verified",
            "runtime_execution_authority_verified",
            "serialized_receipt_authoritative",
            "execution_trace_transferable_by_receipt",
            "actual_human_review_verified",
            "actual_source_evidence_verified",
            "metric_eligibility_verified",
            "single_signature_is_review_evidence",
            "cross_role_cryptographic_key_separation_verified",
            "cross_role_key_separation_verified",
            "review_chain_verified",
            "workflow_lineage_verified",
            "review_accounting_binding_verified",
            "dual_blind_primary_pair_verified",
            "dual_blind_quorum_verified",
            "adjudication_verified",
            "disagreement_adjudication_verified",
            "retrospective_actualization_allowed",
            "presented_accounting_receipt_upgrade_permitted",
            "descriptive_metrics_allowed",
            "descriptive_quality_metrics_allowed",
            "inferential_metrics_allowed",
            "complete_case_metrics_allowed",
            "semantic_metrics_allowed",
            "actual_authority_granted",
            "p0_phase_exit",
            "production_approval",
            "full_scan_approval",
            "action_applied",
        ):
            self.assertIs(receipt[field], False, field)
        self.assertEqual(receipt["actual_human_review_count"], 0)
        self.assertEqual(receipt["actual_context_credit_count"], 0)
        self.assertEqual(receipt["actual_human_unreviewed_input_count"], 40)
        self.assertEqual(receipt["actual_primary_review_event_count"], 0)
        self.assertEqual(receipt["actual_pair_complete_input_count"], 0)
        self.assertEqual(receipt["actual_adjudicated_input_count"], 0)
        self.assertEqual(receipt["actual_judged_input_count"], 0)
        self.assertEqual(receipt["actual_source_credit_count"], 0)
        self.assertEqual(receipt["statistical_denominator_contribution"], "NONE")
        self.assertTrue(receipt["successor_campaign_new_precommit_required"])
        self.assertEqual(receipt["operational_effect"], "NONE_SHADOW_ONLY")

    def test_same_physical_key_can_be_repacked_for_four_roles_but_separation_stays_false(self) -> None:
        signer = self._new_signer()
        receipts = [self._bundle(kind, signer=signer)["receipt"] for kind in KINDS]
        self.assertEqual(len({receipt["public_key_fingerprint_sha256"] for receipt in receipts}), 1)
        for receipt in receipts:
            self.assertTrue(receipt["asymmetric_signature_math_verified"])
            self.assertFalse(receipt["cross_role_cryptographic_key_separation_verified"])
            self.assertFalse(receipt["cross_role_key_separation_verified"])
            self.assertFalse(receipt["actual_authority_granted"])
            self.assertEqual(receipt["statistical_denominator_contribution"], "NONE")

    def test_single_human_result_with_no_predecessor_is_math_not_review_evidence(self) -> None:
        bundle = self._bundle(contract.HUMAN_REVIEW_RESULT)
        subject = _object(bundle["subject"])
        receipt = bundle["receipt"]
        self.assertIsNone(subject["predecessor_subject_raw_sha256"])
        self.assertFalse(receipt["single_signature_is_review_evidence"])
        self.assertFalse(receipt["workflow_lineage_verified"])
        self.assertFalse(receipt["review_accounting_binding_verified"])
        self.assertFalse(receipt["dual_blind_quorum_verified"])
        self.assertFalse(receipt["disagreement_adjudication_verified"])
        self.assertFalse(receipt["retrospective_actualization_allowed"])
        self.assertTrue(receipt["successor_campaign_new_precommit_required"])

    def test_role_domain_or_purpose_swap_is_rejected_even_when_resealed(self) -> None:
        bundle = self._bundle()
        for field, bad in (
            ("key_role", "REVIEW_LEASE_SIGNING_ONLY"),
            ("domain", contract.SIGNATURE_PROFILE[contract.REVIEW_LEASE][2]),
            ("purpose", contract.SIGNATURE_PROFILE[contract.REVIEW_LEASE][1]),
        ):
            row = _object(bundle["envelope"])
            row[field] = bad
            material = {
                key: value
                for key, value in row.items()
                if key not in {"signature_rs_base64", "artifact_sha256"}
            }
            row["signature_rs_base64"] = base64.b64encode(
                bundle["signer"].sign_low_s(contract.canonical_bytes(material))
            ).decode("ascii")
            tampered = contract.canonical_file_bytes(_reseal(row))
            with self.subTest(field=field), self.assertRaises(
                contract.P0PresentedNeutralReviewSignatureMathV1Error
            ):
                self._validate(bundle, signature_envelope_raw=tampered)

    def test_cross_kind_replay_is_rejected(self) -> None:
        bundle = self._bundle(contract.HUMAN_REVIEW_RESULT)
        with self.assertRaises(contract.P0PresentedNeutralReviewSignatureMathV1Error):
            self._validate(
                bundle,
                expected_signature_kind=contract.REVIEW_LEASE,
            )

    def test_exact_payload_bytes_and_artifact_are_bound(self) -> None:
        bundle = self._bundle()
        changed_payload = _payload(contract.HUMAN_REVIEW_RESULT, "changed")
        with self.assertRaises(contract.P0PresentedNeutralReviewSignatureMathV1Error):
            self._validate(bundle, payload_raw=changed_payload)
        malformed = bytearray(bundle["payload"])
        malformed[-2] ^= 1
        with self.assertRaises(contract.P0PresentedNeutralReviewSignatureMathV1Error):
            self._validate(bundle, payload_raw=bytes(malformed))

    def test_semantic_or_operational_promotion_fields_are_rejected_recursively(self) -> None:
        for forbidden_key, forbidden_value in (
            ("target_work_id", "아카데미-생존-갤러리"),
            ("alias_relation", "아생갤"),
            ("production_approval", True),
            ("semantic_metrics_allowed", True),
            ("review_accounting_binding_verified", True),
            ("actual_context_credit_count", 20),
            ("gate_status", "GO"),
            ("action_applied", True),
            ("operational_effect", "WRITE_PRODUCTION"),
        ):
            payload_material = {
                "schema_version": "p0_test_presented_review_payload_v1",
                "record_origin": contract.RECORD_ORIGIN,
                "nested": {forbidden_key: forbidden_value},
                "action_applied": False,
                "operational_effect": contract.OPERATIONAL_EFFECT,
            }
            payload = contract.canonical_file_bytes(
                {
                    **payload_material,
                    "artifact_sha256": contract.canonical_sha256(payload_material),
                }
            )
            with self.subTest(key=forbidden_key), self.assertRaises(
                contract.P0PresentedNeutralReviewSignatureMathV1Error
            ):
                contract.build_presented_review_subject_bytes(
                    signature_kind=contract.HUMAN_REVIEW_RESULT,
                    trust_domain="review-trust-candidate",
                    project_id="llm-novel-dc-community-parser",
                    environment="p0-shadow",
                    campaign_id="campaign-candidate-001",
                    run_id="run-candidate-001",
                    subject_id="subject-malicious",
                    presented_issued_at="2026-09-03T00:00:00Z",
                    nonce_commitment_sha256=contract.canonical_sha256("nonce"),
                    payload_raw=payload,
                    predecessor_subject_raw_sha256=None,
                )

    def test_impossible_calendar_time_rejects_but_stale_presented_time_proves_no_freshness(self) -> None:
        bundle = self._bundle()
        row = _object(bundle["subject"])
        row["presented_issued_at"] = "2026-02-31T00:00:00Z"
        tampered = contract.canonical_file_bytes(_reseal(row))
        with self.assertRaises(contract.P0PresentedNeutralReviewSignatureMathV1Error):
            self._validate(
                bundle,
                subject_raw=tampered,
                expected_subject_raw_sha256=contract.raw_sha256(tampered),
            )
        stale = self._bundle(
            presented_issued_at="2000-01-01T00:00:00Z",
            revocation_marker="attacker-chosen-revocation",
        )
        self.assertFalse(stale["receipt"]["trusted_time_verified"])
        self.assertFalse(stale["receipt"]["revocation_state_verified"])

    def test_malformed_subject_sha_types_fail_with_contract_errors(self) -> None:
        bundle = self._bundle()
        for bad in (7, ["0" * 64], None):
            row = _object(bundle["subject"])
            row["payload_raw_sha256"] = bad
            tampered = contract.canonical_file_bytes(_reseal(row))
            expected = contract.raw_sha256(tampered)
            with self.subTest(bad=bad), self.assertRaises(
                contract.P0PresentedNeutralReviewSignatureMathV1Error
            ):
                self._validate(
                    bundle,
                    subject_raw=tampered,
                    expected_subject_raw_sha256=expected,
                )
            with self.subTest(parent_bad=bad), self.assertRaises(
                parent.P0PresentedNeutralReviewSignatureMathV1ParentError
            ):
                self._parent(
                    bundle,
                    subject_raw=tampered,
                    expected_subject_raw_sha256=expected,
                )

    def test_repeat_validation_is_allowed_but_durable_replay_prevention_is_false(self) -> None:
        bundle = self._bundle()
        first = self._validate(bundle)
        second = self._validate(bundle)
        self.assertEqual(first["receipt_sha256"], second["receipt_sha256"])
        self.assertFalse(first["durable_replay_prevention_verified"])
        self.assertFalse(second["durable_replay_prevention_verified"])

    def test_pin_subject_and_envelope_substitution_without_matching_signature_reject(self) -> None:
        bundle = self._bundle()
        replacement = self._bundle(marker="replacement")
        for overrides in (
            {
                "public_key_pin_raw": replacement["pin"],
                "expected_public_key_pin_raw_sha256": contract.raw_sha256(replacement["pin"]),
            },
            {
                "subject_raw": replacement["subject"],
                "payload_raw": replacement["payload"],
                "expected_subject_raw_sha256": contract.raw_sha256(replacement["subject"]),
            },
            {"signature_envelope_raw": replacement["envelope"]},
        ):
            with self.subTest(overrides=tuple(overrides)), self.assertRaises(
                contract.P0PresentedNeutralReviewSignatureMathV1Error
            ):
                self._validate(bundle, **overrides)

    def test_coordinated_attacker_pin_subject_key_and_signature_can_only_pass_math(self) -> None:
        replacement = self._bundle(marker="coordinated-attacker")
        receipt = self._validate(replacement)
        self.assertTrue(receipt["asymmetric_signature_math_verified"])
        self.assertTrue(receipt["caller_presented_pin_only"])
        self.assertFalse(receipt["external_key_provisioning_verified"])
        self.assertFalse(receipt["signer_identity_verified"])
        self.assertFalse(receipt["actual_authority_granted"])

    def test_signature_bit_flip_zero_scalar_and_high_s_reject(self) -> None:
        bundle = self._bundle()
        original = base64.b64decode(_object(bundle["envelope"])["signature_rs_base64"])
        order = int(
            "ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551",
            16,
        )
        candidates = [
            bytes([original[0] ^ 1]) + original[1:],
            bytes(64),
            original[:32] + (order - int.from_bytes(original[32:], "big")).to_bytes(32, "big"),
        ]
        for signature in candidates:
            row = _object(bundle["envelope"])
            row["signature_rs_base64"] = base64.b64encode(signature).decode("ascii")
            tampered = contract.canonical_file_bytes(_reseal(row))
            with self.subTest(signature=signature[:2].hex()), self.assertRaises(
                contract.P0PresentedNeutralReviewSignatureMathV1Error
            ):
                self._validate(bundle, signature_envelope_raw=tampered)

    def test_wrong_expected_hashes_reject(self) -> None:
        bundle = self._bundle()
        bad = "0" * 64
        with self.assertRaises(contract.P0PresentedNeutralReviewSignatureMathV1Error):
            self._validate(bundle, expected_public_key_pin_raw_sha256=bad)
        with self.assertRaises(contract.P0PresentedNeutralReviewSignatureMathV1Error):
            self._validate(bundle, expected_subject_raw_sha256=bad)

    def test_noncanonical_bom_crlf_duplicate_and_trailing_data_reject(self) -> None:
        bundle = self._bundle()
        pin = bundle["pin"]
        variants = (
            b"\xef\xbb\xbf" + pin,
            pin.replace(b"\n", b"\r\n"),
            pin[:-1] + b" \n",
            pin[:-2] + b',"schema_version":"duplicate"}\n',
        )
        for variant in variants:
            with self.subTest(prefix=variant[:4]), self.assertRaises(
                contract.P0PresentedNeutralReviewSignatureMathV1Error
            ):
                self._validate(
                    bundle,
                    public_key_pin_raw=variant,
                    expected_public_key_pin_raw_sha256=contract.raw_sha256(variant),
                )

    def test_parent_rejects_forged_or_stale_child_receipt(self) -> None:
        bundle = self._bundle()
        for field, forged_value in (
            ("actual_human_review_verified", True),
            ("actual_human_review_count", 1),
            ("retrospective_actualization_allowed", True),
            ("statistical_denominator_contribution", "PRIMARY_REVIEW_EVENT"),
        ):
            row = deepcopy(bundle["receipt"])
            row[field] = forged_value
            material = {key: value for key, value in row.items() if key != "receipt_sha256"}
            forged = contract.canonical_file_bytes(
                {**material, "receipt_sha256": contract.canonical_sha256(material)}
            )
            with self.subTest(field=field), self.assertRaises(
                parent.P0PresentedNeutralReviewSignatureMathV1ParentError
            ):
                self._parent(bundle, component_receipt_raw=forged)
        stale = self._bundle(marker="stale-other")
        with self.assertRaises(parent.P0PresentedNeutralReviewSignatureMathV1ParentError):
            self._parent(bundle, component_receipt_raw=stale["receipt_raw"])

    def test_payload_size_bound_fingerprint_known_answer_and_provider_constants(self) -> None:
        oversized = b'{"schema_version":"x","padding":"' + b"a" * (1024 * 1024) + b'"}\n'
        with self.assertRaises(contract.P0PresentedNeutralReviewSignatureMathV1Error):
            contract.build_presented_review_subject_bytes(
                signature_kind=contract.HUMAN_REVIEW_RESULT,
                trust_domain="review-trust-candidate",
                project_id="llm-novel-dc-community-parser",
                environment="p0-shadow",
                campaign_id="campaign-candidate-001",
                run_id="run-candidate-001",
                subject_id="subject-oversized",
                presented_issued_at="2026-09-03T00:00:00Z",
                nonce_commitment_sha256=contract.canonical_sha256("nonce"),
                payload_raw=oversized,
                predecessor_subject_raw_sha256=None,
            )
        gx = bytes.fromhex("6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296")
        gy = bytes.fromhex("4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5")
        self.assertEqual(
            contract.public_key_fingerprint_sha256(
                public_key_x_base64=base64.b64encode(gx).decode("ascii"),
                public_key_y_base64=base64.b64encode(gy).decode("ascii"),
            ),
            "5cd252fb0ce8932436faf8ccd1040981b89ee4ad6b9fe9e2a2b7e71aacb27cd3",
        )
        self.assertEqual(contract.CNG_PROVIDER, cng_p256.CNG_PROVIDER)
        self.assertEqual(contract.CURVE, cng_p256.CURVE)

    def test_parent_is_structurally_independent_and_production_has_no_signer(self) -> None:
        parent_source = inspect.getsource(parent)
        tree = ast.parse(parent_source)
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
        self.assertFalse(
            any("p0_presented_neutral_review_signature_math_v1_contract" in name for name in imported)
        )
        contract_source = inspect.getsource(contract)
        self.assertNotIn("BCryptGenerateKeyPair", contract_source)
        self.assertNotIn("BCryptSignHash", contract_source)
        self.assertNotIn("p0_external_owner_asymmetric_signature", contract_source)


if __name__ == "__main__":
    unittest.main()
