from __future__ import annotations

import base64
from copy import deepcopy
import os
import unittest
from unittest.mock import patch

from llm_batch.grounding import (
    p0_windows_bootstrap_policy_signature_candidate as bootstrap,
)
from llm_batch.grounding import p0_windows_owner_deployment_projection as deployment
from llm_batch.grounding import p0_windows_owner_policy_contract as policy
from tests import test_p0_windows_owner_policy_contract as v1_fixture


_VOLUME = "\\\\?\\Volume{12345678-1234-1234-1234-1234567890ab}"


def _projection() -> dict[str, object]:
    return deployment.with_artifact_hash(
        {
            "projection_schema": deployment.DEPLOYMENT_PROJECTION_SCHEMA,
            "verifier_kind": deployment.VERIFIER_KIND,
            "service_name": deployment.SERVICE_NAME,
            "service_sid": deployment.SERVICE_SID,
            "service_start_account_sid": deployment.SERVICE_START_ACCOUNT_SID,
            "service_type": deployment.SERVICE_TYPE,
            "service_start_type": deployment.SERVICE_START_TYPE,
            "service_error_control": deployment.SERVICE_ERROR_CONTROL,
            "service_sid_type": deployment.SERVICE_SID_TYPE,
            "service_binary_path_argv_policy": (
                deployment.SERVICE_BINARY_PATH_ARGV_POLICY
            ),
            "image_final_volume_guid_path": (
                f"{_VOLUME}\\Program Files\\llm-novel-dc\\owner-verifier-v2\\"
                "llm-novel-dc-owner-verifier.exe"
            ),
            "image_volume_serial_decimal": "123456789",
            "image_file_id_128_hex": "1" * 32,
            "image_sha256": "2" * 64,
            "bootstrap_resource_sha256": "3" * 64,
            "bootstrap_resource_type": deployment.BOOTSTRAP_RESOURCE_TYPE,
            "bootstrap_resource_name": deployment.BOOTSTRAP_RESOURCE_NAME,
            "bootstrap_resource_language_id": (
                deployment.BOOTSTRAP_RESOURCE_LANGUAGE_ID
            ),
            "bootstrap_resource_exact_count": 1,
            "authenticode_signature_type": deployment.VERIFIER_SIGNATURE_TYPE,
            "signer_leaf_spki_sha256": "4" * 64,
            "signer_root_spki_sha256": "5" * 64,
            "wdac_policy_id": "11111111-1111-1111-1111-111111111111",
            "wdac_base_policy_id": "22222222-2222-2222-2222-222222222222",
            "wdac_policy_sha256": "6" * 64,
            "user_mode_code_integrity_required": True,
            "provider_modules": [
                {
                    "role": "BCRYPT",
                    "module_name": "bcrypt.dll",
                    "loaded_final_volume_guid_path": (
                        f"{_VOLUME}\\Windows\\System32\\bcrypt.dll"
                    ),
                    "volume_serial_decimal": "123456789",
                    "file_id_128_hex": "7" * 32,
                    "image_sha256": "8" * 64,
                    "authenticode_signature_type": (
                        deployment.PROVIDER_SIGNATURE_TYPE
                    ),
                    "signer_leaf_spki_sha256": "9" * 64,
                    "signer_root_spki_sha256": "a" * 64,
                },
                {
                    "role": "BCRYPT_PRIMITIVES",
                    "module_name": "bcryptprimitives.dll",
                    "loaded_final_volume_guid_path": (
                        f"{_VOLUME}\\Windows\\System32\\bcryptprimitives.dll"
                    ),
                    "volume_serial_decimal": "123456789",
                    "file_id_128_hex": "b" * 32,
                    "image_sha256": "c" * 64,
                    "authenticode_signature_type": (
                        deployment.PROVIDER_SIGNATURE_TYPE
                    ),
                    "signer_leaf_spki_sha256": "d" * 64,
                    "signer_root_spki_sha256": "e" * 64,
                },
            ],
        }
    )


def _derive_v2_anchor(body: dict[str, object]) -> str:
    objects = body["object_policies"]
    assert isinstance(objects, list)
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
    projection = body["deployment_projection"]
    assert isinstance(projection, dict)
    return policy.canonical_sha256(
        {
            "domain": policy.OWNER_ANCHOR_DOMAIN_V2,
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
        }
    )


def _v2_body(
    projection: dict[str, object] | None = None,
) -> dict[str, object]:
    body = v1_fixture._body()
    body["schema_version"] = policy.POLICY_BODY_SCHEMA_V2
    body["domain"] = policy.POLICY_DOMAIN_V2
    body["verifier_sid"] = deployment.SERVICE_SID
    objects = body["object_policies"]
    assert isinstance(objects, list)
    for row in objects:
        security = row["security_template"]
        assert isinstance(security, dict)
        aces = security["ordered_aces"]
        assert isinstance(aces, list)
        aces[1]["sid"] = deployment.SERVICE_SID
    body["acl_template_sha256"] = policy.canonical_sha256(
        {
            "domain": policy.ACL_TEMPLATE_DOMAIN,
            "objects": [
                {
                    "role": row["role"],
                    "object_kind": row["object_kind"],
                    "security_template": row["security_template"],
                }
                for row in objects
            ],
        }
    )
    body["deployment_projection"] = deepcopy(projection or _projection())
    body["owner_anchor_sha256"] = _derive_v2_anchor(body)
    return v1_fixture._rehash(body)


def _v2_signature(body: dict[str, object]) -> dict[str, object]:
    signature = v1_fixture._signature(body)
    signature["schema_version"] = policy.POLICY_SIGNATURE_SCHEMA_V2
    signature["domain"] = policy.SIGNATURE_DOMAIN_V2
    return v1_fixture._rehash(signature)


def _validate_v2(
    body: dict[str, object] | None = None,
    signature: dict[str, object] | None = None,
) -> dict[str, object]:
    actual_body = body or _v2_body()
    actual_signature = signature or _v2_signature(actual_body)
    body_bytes, signature_bytes = v1_fixture._contract_bytes(
        actual_body, actual_signature
    )
    return policy.validate_presented_windows_owner_policy_contract(
        policy_body_bytes=body_bytes,
        policy_signature_bytes=signature_bytes,
    )


class WindowsOwnerDeploymentProjectionTests(unittest.TestCase):
    def test_valid_projection_is_structural_evidence_only(self) -> None:
        projection = _projection()
        receipt = deployment.validate_windows_owner_deployment_projection_contract(
            projection=projection
        )
        self.assertTrue(receipt["deployment_projection_contract_verified"])
        self.assertTrue(receipt["service_name_sid_binding_contract_verified"])
        self.assertTrue(receipt["exact_service_configuration_contract_verified"])
        self.assertTrue(
            receipt["embedded_bootstrap_resource_selector_contract_verified"]
        )
        self.assertEqual(
            receipt["deployment_projection_sha256"],
            projection["artifact_sha256"],
        )
        for field in (
            "live_host_observation_verified",
            "bootstrap_public_key_independently_pinned",
            "trusted_verifier_code_identity_verified",
            "trusted_cng_provider_provenance_verified",
            "external_owner_policy_provisioning_verified",
            "owner_authority_verified",
            "actual_authority_granted",
            "production_approval",
            "full_scan_approval",
            "p0_phase_exit",
            "action_applied",
        ):
            self.assertFalse(receipt[field], field)
        material = dict(receipt)
        declared = material.pop("receipt_sha256")
        self.assertEqual(declared, deployment.canonical_sha256(material))

    def test_v1_contract_remains_valid_but_is_future_authority_ineligible(self) -> None:
        body = v1_fixture._body()
        body_bytes, signature_bytes = v1_fixture._contract_bytes(body)
        receipt = policy.validate_presented_windows_owner_policy_contract(
            policy_body_bytes=body_bytes,
            policy_signature_bytes=signature_bytes,
        )
        self.assertEqual(receipt["schema_version"], policy.CONTRACT_RECEIPT_SCHEMA)
        for v2_only_field in (
            "policy_schema_version",
            "deployment_projection_sha256",
            "deployment_projection_contract_verified",
            "policy_verifier_sid_deployment_service_sid_cross_binding_verified",
            "future_authority_policy_requires_v2",
            "future_authority_policy_version_eligible",
        ):
            self.assertNotIn(v2_only_field, receipt)

    def test_v2_policy_binds_projection_and_still_never_grants_authority(self) -> None:
        body = _v2_body()
        receipt = _validate_v2(body)
        projection = body["deployment_projection"]
        assert isinstance(projection, dict)
        self.assertEqual(
            receipt["schema_version"], policy.CONTRACT_RECEIPT_SCHEMA_V2
        )
        self.assertEqual(receipt["policy_schema_version"], policy.POLICY_BODY_SCHEMA_V2)
        self.assertEqual(
            receipt["signature_schema_version"],
            policy.POLICY_SIGNATURE_SCHEMA_V2,
        )
        self.assertEqual(receipt["policy_domain"], policy.POLICY_DOMAIN_V2)
        self.assertEqual(receipt["signature_domain"], policy.SIGNATURE_DOMAIN_V2)
        self.assertEqual(
            receipt["deployment_projection_sha256"],
            projection["artifact_sha256"],
        )
        self.assertTrue(receipt["deployment_projection_contract_verified"])
        self.assertTrue(
            receipt[
                "policy_verifier_sid_deployment_service_sid_cross_binding_verified"
            ]
        )
        self.assertTrue(receipt["future_authority_policy_version_eligible"])
        for field in policy._ALWAYS_FALSE_FIELDS:
            self.assertFalse(receipt[field], field)

    def test_v1_v2_downgrades_and_signature_domain_cross_pairing_fail(self) -> None:
        body = _v2_body()
        v1_signature = v1_fixture._signature(body)
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError,
            "policy_signature.schema_version mismatch",
        ):
            _validate_v2(body, v1_signature)

        downgraded = deepcopy(body)
        downgraded["schema_version"] = policy.POLICY_BODY_SCHEMA
        downgraded["domain"] = policy.POLICY_DOMAIN
        v1_fixture._rehash(downgraded)
        with self.assertRaises(policy.P0WindowsOwnerPolicyContractError):
            _validate_v2(downgraded, v1_fixture._signature(downgraded))

        missing = deepcopy(body)
        missing.pop("deployment_projection")
        v1_fixture._rehash(missing)
        with self.assertRaises(policy.P0WindowsOwnerPolicyContractError):
            _validate_v2(missing, _v2_signature(missing))

        wrong_domain = _v2_signature(body)
        wrong_domain["domain"] = policy.SIGNATURE_DOMAIN
        v1_fixture._rehash(wrong_domain)
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError,
            "policy_signature.domain mismatch",
        ):
            _validate_v2(body, wrong_domain)

    def test_projection_self_hash_and_exact_fields_fail_closed(self) -> None:
        projection = _projection()
        projection["image_sha256"] = "f" * 64
        with self.assertRaisesRegex(
            deployment.P0WindowsOwnerDeploymentProjectionError,
            "artifact hash mismatch",
        ):
            deployment.validate_windows_owner_deployment_projection_contract(
                projection=projection
            )

        projection = _projection()
        projection["unexpected"] = True
        with self.assertRaises(deployment.P0WindowsOwnerDeploymentProjectionError):
            deployment.validate_windows_owner_deployment_projection_contract(
                projection=projection
            )

        projection = _projection()
        providers = projection["provider_modules"]
        assert isinstance(providers, list)
        providers[0]["unexpected"] = True
        deployment.with_artifact_hash(projection)
        with self.assertRaises(deployment.P0WindowsOwnerDeploymentProjectionError):
            deployment.validate_windows_owner_deployment_projection_contract(
                projection=deployment.with_artifact_hash(projection)
            )

    def test_service_identity_and_fixed_image_path_tampering_fail_closed(self) -> None:
        mutations = (
            ("verifier_kind", "PYTHON_SCRIPT"),
            ("service_name", "attacker-service"),
            ("service_sid", "S-1-5-18"),
            ("service_start_account_sid", "S-1-5-19"),
            ("service_type", "SERVICE_WIN32_SHARE_PROCESS"),
            ("service_start_type", "SERVICE_AUTO_START"),
            ("service_error_control", "SERVICE_ERROR_IGNORE"),
            ("service_sid_type", "SERVICE_SID_TYPE_UNRESTRICTED"),
            ("service_binary_path_argv_policy", "WINDOWS_COMMAND_LINE"),
            ("image_final_volume_guid_path", "C:\\attacker\\verifier.exe"),
            (
                "image_final_volume_guid_path",
                f"{_VOLUME}\\Program Files\\llm-novel-dc\\owner-verifier-v2\\evil.exe",
            ),
            (
                "image_final_volume_guid_path",
                "\\\\?\\Volume{00000000-0000-0000-0000-000000000000}"
                "\\Program Files\\llm-novel-dc\\owner-verifier-v2\\"
                "llm-novel-dc-owner-verifier.exe",
            ),
            ("image_volume_serial_decimal", "0123456789"),
            ("image_file_id_128_hex", "F" * 32),
            ("bootstrap_resource_type", "RT_RCDATA"),
            ("bootstrap_resource_name", "DECOY"),
            ("bootstrap_resource_language_id", 1033),
            ("bootstrap_resource_language_id", False),
            ("bootstrap_resource_exact_count", 2),
            ("bootstrap_resource_exact_count", True),
        )
        for field, value in mutations:
            with self.subTest(field=field, value=value):
                projection = _projection()
                projection[field] = value
                projection = deployment.with_artifact_hash(projection)
                with self.assertRaises(
                    deployment.P0WindowsOwnerDeploymentProjectionError
                ):
                    deployment.validate_windows_owner_deployment_projection_contract(
                        projection=projection
                    )

    def test_wdac_authenticode_and_spki_tampering_fail_closed(self) -> None:
        mutations = (
            ("wdac_policy_id", "22222222-2222-2222-2222-222222222222"),
            ("wdac_policy_id", "00000000-0000-0000-0000-000000000000"),
            ("wdac_base_policy_id", "NOT-A-UUID"),
            ("wdac_policy_sha256", "F" * 64),
            ("user_mode_code_integrity_required", False),
            ("authenticode_signature_type", deployment.PROVIDER_SIGNATURE_TYPE),
            ("signer_leaf_spki_sha256", "5" * 64),
            ("signer_root_spki_sha256", "not-a-sha256"),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                projection = _projection()
                projection[field] = value
                projection = deployment.with_artifact_hash(projection)
                with self.assertRaises(
                    deployment.P0WindowsOwnerDeploymentProjectionError
                ):
                    deployment.validate_windows_owner_deployment_projection_contract(
                        projection=projection
                    )

    def test_loaded_provider_order_path_signature_spki_and_identity_are_exact(self) -> None:
        def mutate_order(providers: list[dict[str, object]]) -> None:
            providers.reverse()

        def mutate_path(providers: list[dict[str, object]]) -> None:
            providers[0]["loaded_final_volume_guid_path"] = (
                f"{_VOLUME}\\Windows\\System32x\\bcrypt.dll"
            )

        def mutate_signature(providers: list[dict[str, object]]) -> None:
            providers[0]["authenticode_signature_type"] = (
                deployment.VERIFIER_SIGNATURE_TYPE
            )

        def mutate_spki(providers: list[dict[str, object]]) -> None:
            providers[0]["signer_leaf_spki_sha256"] = providers[0][
                "signer_root_spki_sha256"
            ]

        def mutate_identity(providers: list[dict[str, object]]) -> None:
            providers[1]["volume_serial_decimal"] = providers[0][
                "volume_serial_decimal"
            ]
            providers[1]["file_id_128_hex"] = providers[0]["file_id_128_hex"]

        for mutate in (
            mutate_order,
            mutate_path,
            mutate_signature,
            mutate_spki,
            mutate_identity,
        ):
            with self.subTest(mutate=mutate.__name__):
                projection = _projection()
                providers = projection["provider_modules"]
                assert isinstance(providers, list)
                mutate(providers)
                projection = deployment.with_artifact_hash(projection)
                with self.assertRaises(
                    deployment.P0WindowsOwnerDeploymentProjectionError
                ):
                    deployment.validate_windows_owner_deployment_projection_contract(
                        projection=projection
                    )

    def test_owner_anchor_binds_projection_even_after_projection_rehash(self) -> None:
        body = _v2_body()
        original_anchor = body["owner_anchor_sha256"]
        projection = body["deployment_projection"]
        assert isinstance(projection, dict)
        projection["image_sha256"] = "f" * 64
        body["deployment_projection"] = deployment.with_artifact_hash(projection)
        v1_fixture._rehash(body)
        self.assertEqual(body["owner_anchor_sha256"], original_anchor)
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError,
            "owner_anchor_sha256 mismatch",
        ):
            _validate_v2(body, _v2_signature(body))

    def test_v2_policy_rejects_acl_principal_service_sid_split(self) -> None:
        body = _v2_body()
        body["verifier_sid"] = v1_fixture._VERIFIER_SID
        objects = body["object_policies"]
        assert isinstance(objects, list)
        for row in objects:
            security = row["security_template"]
            assert isinstance(security, dict)
            aces = security["ordered_aces"]
            assert isinstance(aces, list)
            aces[1]["sid"] = v1_fixture._VERIFIER_SID
        body["acl_template_sha256"] = policy.canonical_sha256(
            {
                "domain": policy.ACL_TEMPLATE_DOMAIN,
                "objects": [
                    {
                        "role": row["role"],
                        "object_kind": row["object_kind"],
                        "security_template": row["security_template"],
                    }
                    for row in objects
                ],
            }
        )
        body["owner_anchor_sha256"] = _derive_v2_anchor(body)
        v1_fixture._rehash(body)
        with self.assertRaisesRegex(
            policy.P0WindowsOwnerPolicyContractError,
            "verifier_sid must match the fixed deployment service SID",
        ):
            _validate_v2(body, _v2_signature(body))

    def test_self_consistent_attacker_material_remains_zero_authority(self) -> None:
        projection = _projection()
        projection["image_sha256"] = "f" * 64
        projection["bootstrap_resource_sha256"] = "0" * 64
        projection["signer_leaf_spki_sha256"] = "1" * 64
        projection = deployment.with_artifact_hash(projection)
        body = _v2_body(projection)
        receipt = _validate_v2(body, _v2_signature(body))
        self.assertTrue(receipt["deployment_projection_contract_verified"])
        self.assertTrue(receipt["future_authority_policy_version_eligible"])
        for field in policy._ALWAYS_FALSE_FIELDS:
            self.assertFalse(receipt[field], field)

    @unittest.skipUnless(os.name == "nt", "Windows CNG bootstrap test")
    def test_v2_exact_transcript_passes_bootstrap_math_without_authority(self) -> None:
        from tests.test_p0_external_owner_asymmetric_signature import (
            _TestOnlyCngSigner,
        )
        from tests.test_p0_windows_bootstrap_policy_signature_candidate import (
            _compiled_key_for_signer,
        )

        signer = _TestOnlyCngSigner()
        self.addCleanup(signer.close)
        key = _compiled_key_for_signer(signer)
        body = _v2_body()
        body["bootstrap_key_id"] = key.key_id
        body["bootstrap_public_key_fingerprint_sha256"] = (
            key.public_key_fingerprint_sha256
        )
        body["owner_anchor_sha256"] = _derive_v2_anchor(body)
        v1_fixture._rehash(body)
        signature = _v2_signature(body)
        transcript = bootstrap.canonical_bytes(
            bootstrap._signature_material(signature)
        )
        signature["signature_rs_base64"] = base64.b64encode(
            signer.sign_low_s(transcript)
        ).decode("ascii")
        v1_fixture._rehash(signature)

        with patch.object(
            bootstrap,
            "_compiled_bootstrap_key_candidate",
            return_value=key,
        ):
            receipt = (
                bootstrap.verify_presented_windows_owner_policy_bootstrap_signature_candidate(
                    policy_body_bytes=policy.json_file_bytes(body),
                    policy_signature_bytes=policy.json_file_bytes(signature),
                )
            )
        self.assertTrue(receipt["bootstrap_signature_mathematics_verified"])
        self.assertFalse(receipt["external_code_authority_verified"])
        self.assertFalse(receipt["owner_authority_verified"])
        self.assertFalse(receipt["actual_authority_granted"])


if __name__ == "__main__":
    unittest.main()
