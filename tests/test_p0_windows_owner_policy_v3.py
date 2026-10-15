from __future__ import annotations

import base64
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import inspect
import os
import unittest
from unittest.mock import patch

from llm_batch.grounding import (
    p0_windows_native_observer_profile_contract as native,
)
from llm_batch.grounding import (
    p0_windows_fixed_owner_policy_store_candidate as fixed_store,
)
from llm_batch.grounding import (
    p0_windows_owner_policy_v3_preflight_candidate as v3_preflight,
)
from llm_batch.grounding import p0_windows_owner_policy_contract as policy
from tests import test_p0_windows_owner_deployment_projection as v2_fixture
from tests import test_p0_windows_owner_policy_contract as v1_fixture
from tests import (
    test_p0_windows_owner_provisioning_preflight_candidate as preflight_fixture,
)
from tests.test_p0_external_owner_asymmetric_signature import _TestOnlyCngSigner
from tests.test_p0_windows_bootstrap_policy_signature_candidate import (
    _compiled_key_for_signer,
)


_P256_SPKI_PREFIX = bytes.fromhex(
    "3059301306072a8648ce3d020106082a8648ce3d03010703420004"
)
_V1_RECEIPT_SHA256 = (
    "6cbf89be4178d8c8376d154a6f1965fd8ed06cb3d0477b6f27852247fb2dc344"
)
_V2_RECEIPT_SHA256 = (
    "9e969eff694115058e171c4b038dd23a091c51e95543eb9bd2668d4f74e8e7a6"
)


def _spki(seed: int) -> bytes:
    return _P256_SPKI_PREFIX + bytes([seed]) * 64


def _profile(deployment_sha256: str) -> dict[str, object]:
    observer_spki = _spki(0x11)
    owner_state_spki = _spki(0x22)
    return native.with_artifact_hash(
        {
            "schema_version": native.PROFILE_SCHEMA,
            "record_origin": native.PROFILE_ORIGIN,
            "domain": native.PROFILE_DOMAIN,
            "deployment_projection_sha256": deployment_sha256,
            "service_name": v2_fixture.deployment.SERVICE_NAME,
            "service_sid": v2_fixture.deployment.SERVICE_SID,
            "fixed_pipe_name": native.FIXED_PIPE_NAME,
            "request_schema_version": native.REQUEST_SCHEMA,
            "request_domain": native.REQUEST_DOMAIN,
            "receipt_body_schema_version": native.RECEIPT_BODY_SCHEMA,
            "receipt_body_domain": native.RECEIPT_BODY_DOMAIN,
            "receipt_signature_schema_version": native.RECEIPT_SIGNATURE_SCHEMA,
            "receipt_signature_domain": native.RECEIPT_SIGNATURE_DOMAIN,
            "challenge_size_bytes": native.CHALLENGE_SIZE_BYTES,
            "max_request_bytes": native.MAX_REQUEST_BYTES,
            "max_response_bytes": native.MAX_RESPONSE_BYTES,
            "observer_key_id": "observer-tpm-key-001",
            "observer_key_epoch": 1,
            "observer_key_role": native.OBSERVER_KEY_ROLE,
            "observer_key_algorithm": native.OBSERVER_KEY_ALGORITHM,
            "observer_public_key_spki_der_base64": base64.b64encode(
                observer_spki
            ).decode("ascii"),
            "observer_public_key_fingerprint_sha256": hashlib.sha256(
                observer_spki
            ).hexdigest(),
            "observer_key_storage_provider": (
                native.OBSERVER_KEY_STORAGE_PROVIDER
            ),
            "observer_key_unique_name_sha256": "5" * 64,
            "observer_key_allowed_signature_domains": [
                native.RECEIPT_SIGNATURE_DOMAIN
            ],
            "observer_key_hardware_backed_required": True,
            "observer_key_non_exportable_required": True,
            "observer_key_attestation_format": (
                native.OBSERVER_KEY_ATTESTATION_FORMAT
            ),
            "observer_key_attestation_sha256": "6" * 64,
            "observer_key_security_template_sha256": "7" * 64,
            "owner_state_ticket_schema_version": (
                native.OWNER_STATE_TICKET_SCHEMA
            ),
            "owner_state_ticket_domain": native.OWNER_STATE_TICKET_DOMAIN,
            "owner_state_authority_key_id": "owner-state-key-001",
            "owner_state_authority_key_epoch": 1,
            "owner_state_authority_key_role": native.OWNER_STATE_KEY_ROLE,
            "owner_state_authority_algorithm": native.OWNER_STATE_KEY_ALGORITHM,
            "owner_state_authority_public_key_spki_der_base64": (
                base64.b64encode(owner_state_spki).decode("ascii")
            ),
            "owner_state_authority_spki_sha256": hashlib.sha256(
                owner_state_spki
            ).hexdigest(),
            "owner_state_authority_allowed_signature_domains": [
                native.OWNER_STATE_TICKET_DOMAIN
            ],
            "trusted_time_model": native.TRUSTED_TIME_MODEL,
            "nonce_state_model": native.NONCE_STATE_MODEL,
            "max_ticket_lifetime_seconds": 300,
            "min_revocation_sequence": 1,
            "min_observer_counter": 1,
        }
    )


def _derive_v3_anchor(body: dict[str, object]) -> str:
    objects = body["object_policies"]
    assert isinstance(objects, list)
    projection = body["deployment_projection"]
    profile = body["native_observer_profile"]
    assert isinstance(projection, dict) and isinstance(profile, dict)
    object_identity_hash = policy.canonical_sha256(
        [
            {
                key: row[key]
                for key in (
                    "role",
                    "object_kind",
                    "final_volume_guid_path",
                    "volume_serial_decimal",
                    "file_id_128_hex",
                )
            }
            for row in objects
        ]
    )
    return policy.canonical_sha256(
        {
            "domain": policy.OWNER_ANCHOR_DOMAIN_V3,
            "policy_id": body["policy_id"],
            "policy_epoch": body["policy_epoch"],
            "predecessor_policy_bytes_sha256": body[
                "predecessor_policy_bytes_sha256"
            ],
            "store_id": body["store_id"],
            "project_id": body["project_id"],
            "trust_domain": body["trust_domain"],
            "environment": body["environment"],
            "purpose": body["purpose"],
            "bootstrap_key_id": body["bootstrap_key_id"],
            "bootstrap_public_key_fingerprint_sha256": body[
                "bootstrap_public_key_fingerprint_sha256"
            ],
            "owner_principal_sha256": body["owner_principal_sha256"],
            "verifier_sid": body["verifier_sid"],
            "object_identity_projection_sha256": object_identity_hash,
            "acl_template_sha256": body["acl_template_sha256"],
            "operational_key_projection_sha256": body[
                "operational_key_projection_sha256"
            ],
            "min_revocation_sequence": body["min_revocation_sequence"],
            "lifecycle_status": body["lifecycle_status"],
            "deployment_projection_sha256": projection["artifact_sha256"],
            "native_observer_profile_sha256": profile["artifact_sha256"],
        }
    )


def _v3_body() -> dict[str, object]:
    body = v2_fixture._v2_body()
    projection = body["deployment_projection"]
    assert isinstance(projection, dict)
    body["schema_version"] = policy.POLICY_BODY_SCHEMA_V3
    body["domain"] = policy.POLICY_DOMAIN_V3
    body["native_observer_profile"] = _profile(projection["artifact_sha256"])
    body["owner_anchor_sha256"] = _derive_v3_anchor(body)
    return v1_fixture._rehash(body)


def _v3_signature(body: dict[str, object]) -> dict[str, object]:
    signature = v1_fixture._signature(body)
    signature["schema_version"] = policy.POLICY_SIGNATURE_SCHEMA_V3
    signature["domain"] = policy.SIGNATURE_DOMAIN_V3
    return v1_fixture._rehash(signature)


def _validate_v3(
    body: dict[str, object] | None = None,
    signature: dict[str, object] | None = None,
) -> dict[str, object]:
    actual_body = body or _v3_body()
    actual_signature = signature or _v3_signature(actual_body)
    body_bytes, signature_bytes = v1_fixture._contract_bytes(
        actual_body, actual_signature
    )
    return policy.validate_presented_windows_owner_policy_contract(
        policy_body_bytes=body_bytes,
        policy_signature_bytes=signature_bytes,
    )


def _fixed_outcome_for_policy(
    body: dict[str, object], signature: dict[str, object]
) -> tuple[dict[str, object], dict[str, object], bytes]:
    body_bytes, signature_bytes = v1_fixture._contract_bytes(body, signature)
    contract = policy.validate_presented_windows_owner_policy_contract(
        policy_body_bytes=body_bytes,
        policy_signature_bytes=signature_bytes,
    )
    fixed_receipt, _old_body = preflight_fixture._valid_fixed_outcome()
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    signature_hash = hashlib.sha256(signature_bytes).hexdigest()
    fixed_receipt["policy_body_bytes_sha256"] = body_hash
    fixed_receipt["policy_signature_bytes_sha256"] = signature_hash
    fixed_receipt["owner_policy_contract_receipt"] = contract
    fixed_receipt["owner_policy_contract_receipt_declared_sha256"] = contract[
        "receipt_sha256"
    ]
    fixed_receipt["owner_policy_contract_receipt_full_canonical_sha256"] = (
        v2_fixture.deployment.canonical_sha256(contract)
    )
    bootstrap = fixed_receipt[
        "bootstrap_policy_signature_candidate_receipt"
    ]
    assert isinstance(bootstrap, dict)
    bootstrap["policy_body_bytes_sha256"] = body_hash
    bootstrap["policy_signature_bytes_sha256"] = signature_hash
    bootstrap["policy_signature_artifact_sha256"] = contract[
        "policy_signature_artifact_sha256"
    ]
    bootstrap["compiled_bootstrap_key_id"] = body["bootstrap_key_id"]
    bootstrap["compiled_bootstrap_public_key_fingerprint_sha256"] = body[
        "bootstrap_public_key_fingerprint_sha256"
    ]
    bootstrap["owner_policy_contract_receipt"] = contract
    bootstrap["owner_policy_contract_receipt_declared_sha256"] = contract[
        "receipt_sha256"
    ]
    bootstrap["signature_material_bytes_sha256"] = (
        fixed_store.bootstrap.canonical_sha256(
            {
                field: signature[field]
                for field in fixed_store.bootstrap._SIGNATURE_MATERIAL_FIELDS
            }
        )
    )
    bootstrap["signature_material_envelope_field_names"] = list(
        fixed_store.bootstrap._SIGNATURE_MATERIAL_FIELDS
    )
    bootstrap["public_api_key_parameter_absent"] = True
    bootstrap["public_api_provider_parameter_absent"] = True
    bootstrap["credited_actual_source_claim_count"] = 0
    bootstrap["credited_actual_a_context_review_count"] = 0
    bootstrap["operational_effect"] = "NONE_SHADOW_ONLY"
    for field in v3_preflight._BOOTSTRAP_RECEIPT_FIELDS:
        if field != "receipt_sha256":
            bootstrap.setdefault(field, None)
    preflight_fixture._rehash(bootstrap)
    fixed_receipt["bootstrap_signature_input_sha256"] = bootstrap[
        "signature_material_bytes_sha256"
    ]
    fixed_receipt["compiled_bootstrap_key_id"] = body["bootstrap_key_id"]
    fixed_receipt["compiled_bootstrap_public_key_fingerprint_sha256"] = body[
        "bootstrap_public_key_fingerprint_sha256"
    ]
    fixed_receipt[
        "bootstrap_policy_signature_candidate_receipt_declared_sha256"
    ] = bootstrap["receipt_sha256"]
    fixed_receipt["credited_actual_source_claim_count"] = 0
    fixed_receipt["credited_actual_a_context_review_count"] = 0
    fixed_receipt["operational_effect"] = "NONE_SHADOW_ONLY"
    operational = body["operational_key"]
    assert isinstance(operational, dict)
    fixed_receipt.update(
        {
            "known_folder_id": fixed_store.KNOWN_FOLDER_ID,
            "known_folder_flags": fixed_store.KNOWN_FOLDER_FLAGS,
            "known_folder_token_is_null": True,
            "fixed_relative_store_components": list(
                policy.FIXED_POLICY_STORE_SUFFIX
            ),
            "selected_generation_component": fixed_store.GENERATION_COMPONENT,
            "selected_policy_epoch": fixed_store.COMPILED_POLICY_EPOCH,
            "lexical_ancestor_handle_count": 1,
            "role_handle_count": len(policy.OBJECT_ROLES),
            "policy_body_bytes_length": len(body_bytes),
            "policy_signature_bytes_length": len(signature_bytes),
            "public_key_pin_bytes_length": 1,
            "public_key_pin_bytes_sha256": operational["pin_bytes_sha256"],
            "public_key_pin_artifact_sha256": operational[
                "pin_artifact_sha256"
            ],
            "public_key_fingerprint_sha256": operational[
                "public_key_fingerprint_sha256"
            ],
            "public_key_id": operational["key_id"],
            "public_key_epoch": operational["key_epoch"],
            "acl_projection_sha256_by_role": {
                role: "d" * 64 for role in policy.OBJECT_ROLES
            },
        }
    )
    identity = {
        "final_path": "\\\\?\\Volume{12345678-1234-1234-1234-1234567890ab}\\x",
        "volume_serial": "1",
        "file_id": "1" * 32,
    }
    watch = {
        "requested_path": "C:\\ProgramData\\llm-novel-dc",
        "identity": identity,
        "watch_subtree": True,
        "notify_filter": fixed_store._WATCH_FILTER,
        "completion_status": "CANCELLED_AT_INTERVAL_END",
        "pending_request_until_interval_end_observed": True,
        "completion_drained_observed": True,
        "watch_handles_non_inheritable_verified": True,
        "watch_handles_closed_observed": True,
        "directory_change_notification_delivered_observed": False,
        "overflow_observed": False,
        "observation_gap_observed": False,
        "bounded_watch_observation_verified": True,
    }
    fixed_receipt["directory_change_watches"] = [deepcopy(watch), deepcopy(watch)]
    for field in v3_preflight._FIXED_STORE_RECEIPT_FIELDS:
        if field != "receipt_sha256":
            fixed_receipt.setdefault(field, None)
    preflight_fixture._rehash(fixed_receipt)
    return fixed_receipt, body, signature_bytes


def _valid_v3_fixed_outcome() -> tuple[dict[str, object], dict[str, object], bytes]:
    body = _v3_body()
    body["bootstrap_key_id"] = fixed_store.bootstrap.COMPILED_BOOTSTRAP_KEY_ID
    body["bootstrap_public_key_fingerprint_sha256"] = (
        fixed_store.bootstrap.COMPILED_BOOTSTRAP_PUBLIC_KEY_FINGERPRINT_SHA256
    )
    body["owner_anchor_sha256"] = _derive_v3_anchor(body)
    body = v1_fixture._rehash(body)
    return _fixed_outcome_for_policy(body, _v3_signature(body))


def _controlled_cng_signed_v3_fixed_outcome(
    signer: _TestOnlyCngSigner,
    key: fixed_store.bootstrap._CompiledBootstrapKeyCandidate,
) -> tuple[dict[str, object], dict[str, object], bytes]:
    body = _v3_body()
    body["bootstrap_key_id"] = key.key_id
    body["bootstrap_public_key_fingerprint_sha256"] = (
        key.public_key_fingerprint_sha256
    )
    body["owner_anchor_sha256"] = _derive_v3_anchor(body)
    body = v1_fixture._rehash(body)
    signature = _v3_signature(body)
    material = fixed_store.bootstrap.canonical_bytes(
        fixed_store.bootstrap._signature_material(signature)
    )
    signature["signature_rs_base64"] = base64.b64encode(
        signer.sign_low_s(material)
    ).decode("ascii")
    v1_fixture._rehash(signature)
    return _fixed_outcome_for_policy(body, signature)


class WindowsOwnerPolicyV3Tests(unittest.TestCase):
    def test_successor_public_api_is_zero_input_and_separate_from_v2(self) -> None:
        signature = inspect.signature(
            v3_preflight.observe_fixed_windows_owner_policy_v3_preflight_candidate
        )
        self.assertEqual(tuple(signature.parameters), ())
        source = inspect.getsource(v3_preflight)
        self.assertNotIn("owner_provisioning_preflight_candidate", source)
        self.assertNotIn("OpenSCManager", source)
        self.assertNotIn("CreateFile", source)

    @unittest.skipUnless(os.name == "nt", "Windows CNG v3 successor test")
    def test_valid_v3_store_stops_at_positive_profile_before_scm_or_ipc(self) -> None:
        signer = _TestOnlyCngSigner()
        self.addCleanup(signer.close)
        key = _compiled_key_for_signer(signer)
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    fixed_store.bootstrap,
                    "COMPILED_BOOTSTRAP_KEY_ID",
                    key.key_id,
                )
            )
            stack.enter_context(
                patch.object(
                    fixed_store.bootstrap,
                    "COMPILED_BOOTSTRAP_PUBLIC_KEY_FINGERPRINT_SHA256",
                    key.public_key_fingerprint_sha256,
                )
            )
            stack.enter_context(
                patch.object(
                    fixed_store.bootstrap,
                    "_compiled_bootstrap_key_candidate",
                    return_value=key,
                )
            )
            outcome = _controlled_cng_signed_v3_fixed_outcome(signer, key)
            fixed_receipt, body, signature_bytes = outcome
            producer_receipt = (
                fixed_store.bootstrap.verify_presented_windows_owner_policy_bootstrap_signature_candidate(
                    policy_body_bytes=policy.json_file_bytes(body),
                    policy_signature_bytes=signature_bytes,
                )
            )
            self.assertEqual(
                producer_receipt,
                fixed_receipt["bootstrap_policy_signature_candidate_receipt"],
            )
            observe = stack.enter_context(
                patch.object(
                    fixed_store,
                    "_observe_fixed_windows_owner_policy_store_candidate_with_body_and_signature_bytes",
                    return_value=outcome,
                )
            )
            real_verifier = (
                fixed_store.bootstrap.verify_presented_windows_owner_policy_bootstrap_signature_candidate
            )
            reexecute = stack.enter_context(
                patch.object(
                    fixed_store.bootstrap,
                    "verify_presented_windows_owner_policy_bootstrap_signature_candidate",
                    wraps=real_verifier,
                )
            )
            receipt = v3_preflight._observe_v3_preflight_candidate()
        observe.assert_called_once_with()
        reexecute.assert_called_once_with(
            policy_body_bytes=policy.json_file_bytes(body),
            policy_signature_bytes=signature_bytes,
        )
        self.assertEqual(receipt["decision"], "NO_GO")
        self.assertEqual(receipt["failure_stage"], "POSITIVE_PROFILE")
        self.assertIn(
            "POSITIVE_NATIVE_OBSERVER_POLICY_PROFILE_INCOMPLETE",
            receipt["blocker_codes"],
        )
        for field in (
            "fixed_policy_store_candidate_observed",
            "owner_policy_v3_contract_verified",
            "non_v3_policy_versions_ineligible_by_contract",
            "producer_bootstrap_receipt_exact_validated",
            "producer_bootstrap_signature_math_result_observed",
            "successor_bootstrap_cng_same_process_reexecution_attempted",
            "successor_bootstrap_cng_same_process_reexecution_succeeded",
            "successor_reexecution_receipt_contract_validated",
            "successor_reexecution_receipt_exact_match_verified",
            "same_snapshot_policy_bytes_used_for_cng_reexecution",
            "bootstrap_signature_math_two_execution_consistency_verified",
            "bootstrap_signature_mathematics_verified",
            "deployment_projection_cross_binding_verified",
            "native_observer_profile_component_contract_verified",
            "policy_deployment_native_profile_cross_binding_verified",
            "four_key_role_separation_contract_verified",
            "current_v3_positive_profile_incomplete_verified",
            "current_transcript_schema_positive_path_closed_by_contract",
            "positive_native_observer_hard_rejected",
        ):
            self.assertIs(receipt[field], True, field)
        for field in v3_preflight._ALWAYS_FALSE_FIELDS:
            self.assertIs(receipt[field], False, field)
        self.assertEqual(receipt["credited_actual_source_claim_count"], 0)
        self.assertEqual(receipt["credited_actual_a_context_review_count"], 0)

    def test_cng_reexecution_failure_is_separate_no_go_without_message_echo(self) -> None:
        outcome = _valid_v3_fixed_outcome()
        for error in (
            fixed_store.bootstrap.P0WindowsBootstrapPolicySignatureCandidateError(
                "secret bootstrap detail"
            ),
            RuntimeError("secret provider detail"),
        ):
            with self.subTest(error=type(error).__name__), patch.object(
                fixed_store,
                "_observe_fixed_windows_owner_policy_store_candidate_with_body_and_signature_bytes",
                return_value=outcome,
            ), patch.object(
                fixed_store.bootstrap,
                "verify_presented_windows_owner_policy_bootstrap_signature_candidate",
                side_effect=error,
            ) as reexecute:
                receipt = v3_preflight._observe_v3_preflight_candidate()
            reexecute.assert_called_once_with(
                policy_body_bytes=policy.json_file_bytes(outcome[1]),
                policy_signature_bytes=outcome[2],
            )
            self.assertEqual(
                receipt["failure_stage"], "BOOTSTRAP_CNG_REEXECUTION"
            )
            self.assertIn(
                "BOOTSTRAP_CNG_REEXECUTION_NOT_VERIFIED",
                receipt["blocker_codes"],
            )
            self.assertTrue(receipt["owner_policy_v3_contract_verified"])
            self.assertTrue(
                receipt[
                    "successor_bootstrap_cng_same_process_reexecution_attempted"
                ]
            )
            self.assertFalse(
                receipt[
                    "successor_bootstrap_cng_same_process_reexecution_succeeded"
                ]
            )
            self.assertFalse(receipt["bootstrap_signature_mathematics_verified"])
            self.assertNotIn("secret", str(receipt))

    def test_reexecution_receipt_must_exactly_match_producer(self) -> None:
        outcome = _valid_v3_fixed_outcome()
        direct = deepcopy(
            outcome[0]["bootstrap_policy_signature_candidate_receipt"]
        )
        assert isinstance(direct, dict)
        direct["policy_signature_bytes_sha256"] = "f" * 64
        preflight_fixture._rehash(direct)
        with patch.object(
            fixed_store,
            "_observe_fixed_windows_owner_policy_store_candidate_with_body_and_signature_bytes",
            return_value=outcome,
        ), patch.object(
            fixed_store.bootstrap,
            "verify_presented_windows_owner_policy_bootstrap_signature_candidate",
            return_value=direct,
        ):
            receipt = v3_preflight._observe_v3_preflight_candidate()
        self.assertEqual(receipt["failure_stage"], "BOOTSTRAP_CNG_REEXECUTION")
        self.assertIn(
            "BOOTSTRAP_CNG_REEXECUTION_RECEIPT_MISMATCH",
            receipt["blocker_codes"],
        )
        self.assertFalse(
            receipt[
                "successor_bootstrap_cng_same_process_reexecution_succeeded"
            ]
        )
        self.assertTrue(
            receipt["successor_reexecution_receipt_contract_validated"]
        )
        self.assertFalse(
            receipt["successor_reexecution_receipt_exact_match_verified"]
        )
        self.assertFalse(receipt["bootstrap_signature_mathematics_verified"])

    def test_invalid_reexecution_receipt_shapes_fail_closed(self) -> None:
        outcome = _valid_v3_fixed_outcome()
        valid = outcome[0]["bootstrap_policy_signature_candidate_receipt"]
        assert isinstance(valid, dict)
        invalids: list[object] = [None, {}, {**valid, "attacker": True}]
        credit = deepcopy(valid)
        credit["credited_actual_source_claim_count"] = 40
        preflight_fixture._rehash(credit)
        invalids.append(credit)
        bool_integer = deepcopy(valid)
        bool_integer["candidate_only"] = 1
        preflight_fixture._rehash(bool_integer)
        invalids.append(bool_integer)
        for direct in invalids:
            with self.subTest(kind=type(direct).__name__), patch.object(
                fixed_store,
                "_observe_fixed_windows_owner_policy_store_candidate_with_body_and_signature_bytes",
                return_value=outcome,
            ), patch.object(
                fixed_store.bootstrap,
                "verify_presented_windows_owner_policy_bootstrap_signature_candidate",
                return_value=direct,
            ):
                receipt = v3_preflight._observe_v3_preflight_candidate()
            self.assertEqual(
                receipt["failure_stage"], "BOOTSTRAP_CNG_REEXECUTION"
            )
            self.assertIn(
                "BOOTSTRAP_CNG_REEXECUTION_NOT_VERIFIED",
                receipt["blocker_codes"],
            )
            self.assertFalse(
                receipt[
                    "successor_bootstrap_cng_same_process_reexecution_succeeded"
                ]
            )
            self.assertFalse(
                receipt["successor_reexecution_receipt_contract_validated"]
            )

    @unittest.skipUnless(os.name == "nt", "Windows CNG v3 attack test")
    def test_coordinated_low_s_signature_reseal_fails_at_successor_cng(self) -> None:
        body = _v3_body()
        body["bootstrap_key_id"] = fixed_store.bootstrap.COMPILED_BOOTSTRAP_KEY_ID
        body["bootstrap_public_key_fingerprint_sha256"] = (
            fixed_store.bootstrap.COMPILED_BOOTSTRAP_PUBLIC_KEY_FINGERPRINT_SHA256
        )
        body["owner_anchor_sha256"] = _derive_v3_anchor(body)
        body = v1_fixture._rehash(body)
        signature = _v3_signature(body)
        signature["signature_rs_base64"] = base64.b64encode(
            (3).to_bytes(32, "big") + (4).to_bytes(32, "big")
        ).decode("ascii")
        v1_fixture._rehash(signature)
        outcome = _fixed_outcome_for_policy(body, signature)
        with patch.object(
            fixed_store,
            "_observe_fixed_windows_owner_policy_store_candidate_with_body_and_signature_bytes",
            return_value=outcome,
        ):
            receipt = v3_preflight._observe_v3_preflight_candidate()
        self.assertEqual(receipt["failure_stage"], "BOOTSTRAP_CNG_REEXECUTION")
        self.assertIn(
            "BOOTSTRAP_CNG_REEXECUTION_NOT_VERIFIED",
            receipt["blocker_codes"],
        )
        self.assertTrue(receipt["owner_policy_v3_contract_verified"])
        self.assertFalse(receipt["bootstrap_signature_mathematics_verified"])
        self.assertFalse(receipt["p0_phase_exit"])
        self.assertFalse(receipt["protected_pipeline_state_mutated"])

    def test_v1_and_v2_are_hard_rejected_by_v3_successor(self) -> None:
        v1_body = v1_fixture._body()
        outcomes = (
            _fixed_outcome_for_policy(
                v1_body, v1_fixture._signature(v1_body)
            ),
            _fixed_outcome_for_policy(
                v2_fixture._v2_body(),
                v2_fixture._v2_signature(v2_fixture._v2_body()),
            ),
        )
        for outcome in outcomes:
            with self.subTest(schema=outcome[1]["schema_version"]), patch.object(
                fixed_store,
                "_observe_fixed_windows_owner_policy_store_candidate_with_body_and_signature_bytes",
                return_value=outcome,
            ), patch.object(
                fixed_store.bootstrap,
                "verify_presented_windows_owner_policy_bootstrap_signature_candidate",
            ) as reexecute:
                receipt = v3_preflight._observe_v3_preflight_candidate()
            reexecute.assert_not_called()
            self.assertEqual(receipt["failure_stage"], "OWNER_POLICY_V3")
            self.assertTrue(receipt["fixed_policy_store_candidate_observed"])
            self.assertTrue(
                receipt["non_v3_policy_version_input_hard_rejected"]
            )
            self.assertFalse(receipt["owner_policy_v3_contract_verified"])
            self.assertFalse(receipt["service_configuration_observation_attempted"])
            self.assertFalse(receipt["native_observer_ipc_attempted"])

    def test_resealed_positive_truth_flips_are_rejected(self) -> None:
        for field in (
            "future_authority_policy_version_eligible",
            "positive_native_observer_policy_profile_complete",
        ):
            fixed_receipt, body, signature_bytes = _valid_v3_fixed_outcome()
            contract = fixed_receipt["owner_policy_contract_receipt"]
            assert isinstance(contract, dict)
            contract[field] = True
            preflight_fixture._rehash(contract)
            bootstrap = fixed_receipt[
                "bootstrap_policy_signature_candidate_receipt"
            ]
            assert isinstance(bootstrap, dict)
            bootstrap["owner_policy_contract_receipt"] = contract
            bootstrap["owner_policy_contract_receipt_declared_sha256"] = contract[
                "receipt_sha256"
            ]
            preflight_fixture._rehash(bootstrap)
            fixed_receipt["owner_policy_contract_receipt_declared_sha256"] = (
                contract["receipt_sha256"]
            )
            fixed_receipt[
                "owner_policy_contract_receipt_full_canonical_sha256"
            ] = v2_fixture.deployment.canonical_sha256(contract)
            fixed_receipt[
                "bootstrap_policy_signature_candidate_receipt_declared_sha256"
            ] = bootstrap["receipt_sha256"]
            preflight_fixture._rehash(fixed_receipt)
            with self.subTest(field=field), patch.object(
                fixed_store,
                "_observe_fixed_windows_owner_policy_store_candidate_with_body_and_signature_bytes",
                return_value=(fixed_receipt, body, signature_bytes),
            ):
                receipt = v3_preflight._observe_v3_preflight_candidate()
            self.assertEqual(receipt["failure_stage"], "OWNER_POLICY_V3")
            self.assertFalse(receipt["owner_policy_v3_contract_verified"])

    def test_signature_hash_and_nested_bootstrap_mix_are_rejected(self) -> None:
        fixed_receipt, body, signature_bytes = _valid_v3_fixed_outcome()
        contract = fixed_receipt["owner_policy_contract_receipt"]
        assert isinstance(contract, dict)
        contract["policy_signature_bytes_sha256"] = "f" * 64
        preflight_fixture._rehash(contract)
        bootstrap = fixed_receipt[
            "bootstrap_policy_signature_candidate_receipt"
        ]
        assert isinstance(bootstrap, dict)
        bootstrap["owner_policy_contract_receipt"] = contract
        bootstrap["owner_policy_contract_receipt_declared_sha256"] = contract[
            "receipt_sha256"
        ]
        preflight_fixture._rehash(bootstrap)
        fixed_receipt["owner_policy_contract_receipt_declared_sha256"] = contract[
            "receipt_sha256"
        ]
        fixed_receipt[
            "owner_policy_contract_receipt_full_canonical_sha256"
        ] = v2_fixture.deployment.canonical_sha256(contract)
        fixed_receipt[
            "bootstrap_policy_signature_candidate_receipt_declared_sha256"
        ] = bootstrap["receipt_sha256"]
        preflight_fixture._rehash(fixed_receipt)
        with patch.object(
            fixed_store,
            "_observe_fixed_windows_owner_policy_store_candidate_with_body_and_signature_bytes",
            return_value=(fixed_receipt, body, signature_bytes),
        ):
            receipt = v3_preflight._observe_v3_preflight_candidate()
        self.assertEqual(receipt["failure_stage"], "OWNER_POLICY_V3")

        fixed_receipt, body, signature_bytes = _valid_v3_fixed_outcome()
        contract = fixed_receipt["owner_policy_contract_receipt"]
        bootstrap = fixed_receipt[
            "bootstrap_policy_signature_candidate_receipt"
        ]
        assert isinstance(contract, dict) and isinstance(bootstrap, dict)
        fixed_receipt["policy_signature_bytes_sha256"] = "e" * 64
        contract["policy_signature_bytes_sha256"] = "e" * 64
        contract["policy_signature_artifact_sha256"] = "f" * 64
        preflight_fixture._rehash(contract)
        bootstrap["policy_signature_bytes_sha256"] = "e" * 64
        bootstrap["policy_signature_artifact_sha256"] = "f" * 64
        bootstrap["owner_policy_contract_receipt"] = contract
        bootstrap["owner_policy_contract_receipt_declared_sha256"] = contract[
            "receipt_sha256"
        ]
        preflight_fixture._rehash(bootstrap)
        fixed_receipt["owner_policy_contract_receipt_declared_sha256"] = contract[
            "receipt_sha256"
        ]
        fixed_receipt[
            "owner_policy_contract_receipt_full_canonical_sha256"
        ] = v2_fixture.deployment.canonical_sha256(contract)
        fixed_receipt[
            "bootstrap_policy_signature_candidate_receipt_declared_sha256"
        ] = bootstrap["receipt_sha256"]
        preflight_fixture._rehash(fixed_receipt)
        with patch.object(
            fixed_store,
            "_observe_fixed_windows_owner_policy_store_candidate_with_body_and_signature_bytes",
            return_value=(fixed_receipt, body, signature_bytes),
        ):
            receipt = v3_preflight._observe_v3_preflight_candidate()
        self.assertEqual(receipt["failure_stage"], "OWNER_POLICY_V3")

        fixed_receipt, body, signature_bytes = _valid_v3_fixed_outcome()
        bootstrap = fixed_receipt[
            "bootstrap_policy_signature_candidate_receipt"
        ]
        assert isinstance(bootstrap, dict)
        bootstrap["owner_policy_contract_receipt"] = (
            preflight_fixture._valid_fixed_outcome()[0][
                "owner_policy_contract_receipt"
            ]
        )
        bootstrap["owner_policy_contract_receipt_declared_sha256"] = bootstrap[
            "owner_policy_contract_receipt"
        ]["receipt_sha256"]
        preflight_fixture._rehash(bootstrap)
        fixed_receipt[
            "bootstrap_policy_signature_candidate_receipt_declared_sha256"
        ] = bootstrap["receipt_sha256"]
        preflight_fixture._rehash(fixed_receipt)
        with patch.object(
            fixed_store,
            "_observe_fixed_windows_owner_policy_store_candidate_with_body_and_signature_bytes",
            return_value=(fixed_receipt, body, signature_bytes),
        ):
            receipt = v3_preflight._observe_v3_preflight_candidate()
        self.assertEqual(receipt["failure_stage"], "OWNER_POLICY_V3")

    def test_bool_integer_outer_receipt_flip_is_fixed_store_reject(self) -> None:
        fixed_receipt, body, signature_bytes = _valid_v3_fixed_outcome()
        fixed_receipt["known_folder_api_succeeded"] = 1
        preflight_fixture._rehash(fixed_receipt)
        with patch.object(
            fixed_store,
            "_observe_fixed_windows_owner_policy_store_candidate_with_body_and_signature_bytes",
            return_value=(fixed_receipt, body, signature_bytes),
        ):
            receipt = v3_preflight._observe_v3_preflight_candidate()
        self.assertEqual(receipt["failure_stage"], "FIXED_STORE")
        self.assertFalse(receipt["fixed_policy_store_candidate_observed"])
        self.assertIn("OWNER_POLICY_V3_NOT_VERIFIED", receipt["blocker_codes"])

    def test_exact_receipt_and_outer_semantics_attack_matrix(self) -> None:
        fixed_mutations = {
            "extra": lambda row: row.__setitem__("attacker", True),
            "credit": lambda row: row.__setitem__(
                "credited_actual_source_claim_count", 40
            ),
            "known_folder": lambda row: row.__setitem__(
                "known_folder_id", "attacker"
            ),
            "selected_epoch_bool": lambda row: row.__setitem__(
                "selected_policy_epoch", True
            ),
            "empty_watch": lambda row: row.__setitem__(
                "directory_change_watches", []
            ),
        }
        for label, mutate in fixed_mutations.items():
            fixed_receipt, body, signature_bytes = _valid_v3_fixed_outcome()
            mutate(fixed_receipt)
            preflight_fixture._rehash(fixed_receipt)
            with self.subTest(layer="fixed", attack=label), patch.object(
                fixed_store,
                "_observe_fixed_windows_owner_policy_store_candidate_with_body_and_signature_bytes",
                return_value=(fixed_receipt, body, signature_bytes),
            ):
                receipt = v3_preflight._observe_v3_preflight_candidate()
            self.assertEqual(receipt["failure_stage"], "FIXED_STORE")

        bootstrap_mutations = {
            "extra": lambda row: row.__setitem__("attacker", True),
            "credit": lambda row: row.__setitem__(
                "credited_actual_source_claim_count", 40
            ),
            "envelope": lambda row: row.__setitem__(
                "signature_material_envelope_field_names", ["attacker"]
            ),
            "key_parameter": lambda row: row.__setitem__(
                "public_api_key_parameter_absent", False
            ),
        }
        for label, mutate in bootstrap_mutations.items():
            fixed_receipt, body, signature_bytes = _valid_v3_fixed_outcome()
            bootstrap = fixed_receipt[
                "bootstrap_policy_signature_candidate_receipt"
            ]
            assert isinstance(bootstrap, dict)
            mutate(bootstrap)
            preflight_fixture._rehash(bootstrap)
            fixed_receipt[
                "bootstrap_policy_signature_candidate_receipt_declared_sha256"
            ] = bootstrap["receipt_sha256"]
            preflight_fixture._rehash(fixed_receipt)
            with self.subTest(layer="bootstrap", attack=label), patch.object(
                fixed_store,
                "_observe_fixed_windows_owner_policy_store_candidate_with_body_and_signature_bytes",
                return_value=(fixed_receipt, body, signature_bytes),
            ):
                receipt = v3_preflight._observe_v3_preflight_candidate()
            self.assertEqual(receipt["failure_stage"], "OWNER_POLICY_V3")

        contract_mutations = {
            "extra": lambda row: row.__setitem__("attacker", True),
            "epoch_bool": lambda row: row.__setitem__("policy_epoch", True),
            "owner_anchor": lambda row: row.__setitem__(
                "owner_anchor_sha256", "f" * 64
            ),
            "security_map": lambda row: row.__setitem__(
                "security_template_sha256_by_role", {}
            ),
        }
        for label, mutate in contract_mutations.items():
            fixed_receipt, body, signature_bytes = _valid_v3_fixed_outcome()
            contract = fixed_receipt["owner_policy_contract_receipt"]
            bootstrap = fixed_receipt[
                "bootstrap_policy_signature_candidate_receipt"
            ]
            assert isinstance(contract, dict) and isinstance(bootstrap, dict)
            mutate(contract)
            preflight_fixture._rehash(contract)
            bootstrap["owner_policy_contract_receipt"] = contract
            bootstrap["owner_policy_contract_receipt_declared_sha256"] = contract[
                "receipt_sha256"
            ]
            preflight_fixture._rehash(bootstrap)
            fixed_receipt["owner_policy_contract_receipt_declared_sha256"] = (
                contract["receipt_sha256"]
            )
            fixed_receipt[
                "owner_policy_contract_receipt_full_canonical_sha256"
            ] = v2_fixture.deployment.canonical_sha256(contract)
            fixed_receipt[
                "bootstrap_policy_signature_candidate_receipt_declared_sha256"
            ] = bootstrap["receipt_sha256"]
            preflight_fixture._rehash(fixed_receipt)
            with self.subTest(layer="contract", attack=label), patch.object(
                fixed_store,
                "_observe_fixed_windows_owner_policy_store_candidate_with_body_and_signature_bytes",
                return_value=(fixed_receipt, body, signature_bytes),
            ):
                receipt = v3_preflight._observe_v3_preflight_candidate()
            self.assertEqual(receipt["failure_stage"], "OWNER_POLICY_V3")

    def test_missing_fixed_store_is_deterministic_no_go(self) -> None:
        with patch.object(
            fixed_store,
            "_observe_fixed_windows_owner_policy_store_candidate_with_body_and_signature_bytes",
            side_effect=fixed_store.P0WindowsFixedOwnerPolicyStoreCandidateError(
                "absent"
            ),
        ) as observe, patch.object(
            fixed_store.bootstrap,
            "verify_presented_windows_owner_policy_bootstrap_signature_candidate",
        ) as reexecute:
            first = v3_preflight._observe_v3_preflight_candidate()
            second = v3_preflight._observe_v3_preflight_candidate()
        self.assertEqual(first, second)
        self.assertEqual(observe.call_count, 2)
        reexecute.assert_not_called()
        self.assertEqual(first["failure_stage"], "FIXED_STORE")
        self.assertEqual(
            first["gate_status"],
            "WINDOWS_OWNER_POLICY_V3_PREFLIGHT_EXECUTED_POSITIVE_NO_GO",
        )
        self.assertIn("OWNER_POLICY_V3_NOT_VERIFIED", first["blocker_codes"])
        self.assertFalse(first["fixed_policy_store_candidate_observed"])
        self.assertFalse(first["service_configuration_observation_attempted"])
        self.assertFalse(first["actual_launch_attempted"])

    @unittest.skipUnless(os.name == "nt", "Windows fixed-store observation required")
    def test_current_host_is_explicit_no_go_without_action(self) -> None:
        with patch.object(
            fixed_store.bootstrap,
            "verify_presented_windows_owner_policy_bootstrap_signature_candidate",
            wraps=fixed_store.bootstrap.verify_presented_windows_owner_policy_bootstrap_signature_candidate,
        ) as reexecute:
            receipt = (
                v3_preflight.observe_fixed_windows_owner_policy_v3_preflight_candidate()
            )
        reexecute.assert_not_called()
        self.assertEqual(receipt["decision"], "NO_GO")
        self.assertEqual(receipt["failure_stage"], "FIXED_STORE")
        self.assertFalse(receipt["action_applied"])
        self.assertFalse(receipt["protected_pipeline_state_mutated"])

    def test_v1_v2_receipt_hashes_remain_exact(self) -> None:
        body_bytes, signature_bytes = v1_fixture._contract_bytes(
            v1_fixture._body()
        )
        v1_receipt = policy.validate_presented_windows_owner_policy_contract(
            policy_body_bytes=body_bytes,
            policy_signature_bytes=signature_bytes,
        )
        self.assertEqual(v1_receipt["receipt_sha256"], _V1_RECEIPT_SHA256)
        self.assertEqual(
            v2_fixture._validate_v2()["receipt_sha256"], _V2_RECEIPT_SHA256
        )

    def test_v3_binds_profile_and_is_component_only(self) -> None:
        body = _v3_body()
        receipt = _validate_v3(body)
        profile = body["native_observer_profile"]
        assert isinstance(profile, dict)
        self.assertEqual(receipt["schema_version"], policy.CONTRACT_RECEIPT_SCHEMA_V3)
        self.assertEqual(receipt["policy_domain"], policy.POLICY_DOMAIN_V3)
        self.assertEqual(receipt["signature_domain"], policy.SIGNATURE_DOMAIN_V3)
        self.assertEqual(
            receipt["native_observer_profile_sha256"],
            profile["artifact_sha256"],
        )
        self.assertTrue(receipt["native_observer_profile_contract_verified"])
        self.assertTrue(
            receipt[
                "operational_and_observer_key_role_separation_contract_verified"
            ]
        )
        self.assertFalse(receipt["future_authority_policy_version_eligible"])
        self.assertFalse(
            receipt["positive_native_observer_policy_profile_complete"]
        )
        for field in policy._ALWAYS_FALSE_FIELDS:
            self.assertFalse(receipt[field], field)

    def test_v2_v3_body_signature_cross_pair_is_rejected(self) -> None:
        v3_body = _v3_body()
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError,
            "policy_signature.schema_version mismatch",
        ):
            _validate_v3(v3_body, v2_fixture._v2_signature(v3_body))

        v2_body = v2_fixture._v2_body()
        v3_signature = _v3_signature(v2_body)
        body_bytes, signature_bytes = v1_fixture._contract_bytes(
            v2_body, v3_signature
        )
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError,
            "policy_signature.schema_version mismatch",
        ):
            policy.validate_presented_windows_owner_policy_contract(
                policy_body_bytes=body_bytes,
                policy_signature_bytes=signature_bytes,
            )

    def test_profile_deployment_cross_binding_is_hard_fail(self) -> None:
        body = _v3_body()
        profile = body["native_observer_profile"]
        assert isinstance(profile, dict)
        profile["deployment_projection_sha256"] = "f" * 64
        body["native_observer_profile"] = native.with_artifact_hash(profile)
        body["owner_anchor_sha256"] = _derive_v3_anchor(body)
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError,
            "deployment_projection_sha256 cross-binding mismatch",
        ):
            _validate_v3(v1_fixture._rehash(body))

    def test_profile_service_binding_and_unknown_fields_fail(self) -> None:
        body = _v3_body()
        profile = body["native_observer_profile"]
        assert isinstance(profile, dict)
        profile["service_name"] = "attacker-service"
        body["native_observer_profile"] = native.with_artifact_hash(profile)
        body["owner_anchor_sha256"] = _derive_v3_anchor(body)
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError,
            "native observer profile v1 is invalid",
        ):
            _validate_v3(v1_fixture._rehash(body))

        body = _v3_body()
        body["unexpected"] = True
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError, "keys mismatch"
        ):
            _validate_v3(body)

    def test_all_four_key_roles_must_be_distinct(self) -> None:
        body = _v3_body()
        profile = body["native_observer_profile"]
        operational = body["operational_key"]
        assert isinstance(profile, dict) and isinstance(operational, dict)
        operational["key_id"] = profile["observer_key_id"]
        body["operational_key_projection_sha256"] = (
            policy.derive_operational_key_projection_sha256(operational)
        )
        body["owner_anchor_sha256"] = _derive_v3_anchor(body)
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError,
            "key IDs must be distinct",
        ):
            _validate_v3(v1_fixture._rehash(body))

        body = _v3_body()
        profile = body["native_observer_profile"]
        operational = body["operational_key"]
        assert isinstance(profile, dict) and isinstance(operational, dict)
        operational["public_key_fingerprint_sha256"] = profile[
            "observer_public_key_fingerprint_sha256"
        ]
        body["operational_key_projection_sha256"] = (
            policy.derive_operational_key_projection_sha256(operational)
        )
        body["owner_anchor_sha256"] = _derive_v3_anchor(body)
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError,
            "key fingerprints must be distinct",
        ):
            _validate_v3(v1_fixture._rehash(body))

    def test_operational_key_cannot_sign_observer_domain(self) -> None:
        body = _v3_body()
        operational = body["operational_key"]
        assert isinstance(operational, dict)
        operational["allowed_signature_domains"] = [
            policy.OPERATIONAL_SIGNATURE_DOMAIN,
            native.RECEIPT_SIGNATURE_DOMAIN,
        ]
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError,
            "operational_key.allowed_signature_domains mismatch",
        ):
            _validate_v3(body)

    def test_self_consistent_presented_reseal_never_becomes_authority(self) -> None:
        body = _v3_body()
        profile = deepcopy(body["native_observer_profile"])
        assert isinstance(profile, dict)
        replacement_spki = _spki(0x33)
        profile["observer_public_key_spki_der_base64"] = base64.b64encode(
            replacement_spki
        ).decode("ascii")
        profile["observer_public_key_fingerprint_sha256"] = hashlib.sha256(
            replacement_spki
        ).hexdigest()
        body["native_observer_profile"] = native.with_artifact_hash(profile)
        body["owner_anchor_sha256"] = _derive_v3_anchor(body)
        receipt = _validate_v3(v1_fixture._rehash(body))
        self.assertTrue(receipt["native_observer_profile_contract_verified"])
        self.assertFalse(receipt["bootstrap_signature_mathematics_verified"])
        self.assertFalse(receipt["owner_authority_verified"])
        self.assertFalse(receipt["actual_authority_granted"])
        self.assertFalse(receipt["p0_phase_exit"])


if __name__ == "__main__":
    unittest.main()
