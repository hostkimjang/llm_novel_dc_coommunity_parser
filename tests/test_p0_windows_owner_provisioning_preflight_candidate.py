from __future__ import annotations

from copy import deepcopy
from contextlib import nullcontext
import hashlib
import inspect
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from llm_batch.grounding import (
    p0_windows_fixed_owner_policy_store_candidate as fixed_store,
)
from llm_batch.grounding import (
    p0_windows_owner_provisioning_preflight_candidate as preflight,
)
from llm_batch.grounding import p0_windows_owner_policy_contract as policy
from tests import test_p0_windows_owner_deployment_projection as fixture
from tests import test_p0_windows_owner_policy_contract as v1_fixture


def _rehash(value: dict[str, object]) -> dict[str, object]:
    value.pop("receipt_sha256", None)
    value["receipt_sha256"] = fixture.deployment.canonical_sha256(value)
    return value


def _valid_fixed_outcome():
    body = fixture._v2_body()
    contract = fixture._validate_v2(body)
    body_hash = hashlib.sha256(policy.json_file_bytes(body)).hexdigest()
    signature_hash = "b" * 64
    signature_material_hash = "c" * 64
    bootstrap = _rehash(
        {
            "schema_version": fixed_store.bootstrap.RECEIPT_SCHEMA,
            "gate_status": fixed_store.bootstrap.GATE_STATUS,
            "candidate_only": True,
            "policy_body_bytes_sha256": body_hash,
            "policy_signature_bytes_sha256": signature_hash,
            "signature_material_contract": (
                fixed_store.bootstrap.SIGNATURE_MATERIAL_CONTRACT
            ),
            "signature_material_bytes_sha256": signature_material_hash,
            "compiled_bootstrap_key_id": body["bootstrap_key_id"],
            "compiled_bootstrap_public_key_fingerprint_sha256": body[
                "bootstrap_public_key_fingerprint_sha256"
            ],
            "compiled_bootstrap_key_candidate_provenance": (
                fixed_store.bootstrap.COMPILED_BOOTSTRAP_KEY_CANDIDATE_PROVENANCE
            ),
            "algorithm": policy.BOOTSTRAP_SIGNATURE_ALGORITHM,
            "curve": fixed_store.asymmetric.CURVE,
            "cng_provider_name": fixed_store.asymmetric.CNG_PROVIDER,
            "owner_policy_contract_receipt": contract,
            "owner_policy_contract_receipt_declared_sha256": contract[
                "receipt_sha256"
            ],
            **{
                field: True
                for field in fixed_store._BOOTSTRAP_RECEIPT_TRUE_FIELDS
            },
            **{
                field: False
                for field in fixed_store._BOOTSTRAP_RECEIPT_FALSE_FIELDS
            },
        }
    )
    receipt = _rehash(
        {
            "schema_version": fixed_store.CANDIDATE_RECEIPT_SCHEMA,
            "gate_status": fixed_store.GATE_STATUS,
            "candidate_only": True,
            "fixed_policy_store_discovery_candidate_observed": True,
            "policy_body_bytes_sha256": body_hash,
            "policy_signature_bytes_sha256": signature_hash,
            "owner_policy_contract_receipt": contract,
            "owner_policy_contract_receipt_declared_sha256": contract[
                "receipt_sha256"
            ],
            "owner_policy_contract_receipt_full_canonical_sha256": (
                fixture.deployment.canonical_sha256(contract)
            ),
            "bootstrap_policy_signature_candidate_receipt": bootstrap,
            "bootstrap_policy_signature_candidate_receipt_declared_sha256": (
                bootstrap["receipt_sha256"]
            ),
            "bootstrap_signature_input_sha256": signature_material_hash,
            "compiled_bootstrap_key_id": body["bootstrap_key_id"],
            "compiled_bootstrap_public_key_fingerprint_sha256": body[
                "bootstrap_public_key_fingerprint_sha256"
            ],
            "compiled_bootstrap_key_candidate_selected": True,
            "bootstrap_signature_mathematics_verified": True,
            **{
                field: True
                for field in preflight._FIXED_STORE_REQUIRED_TRUE_FIELDS
            },
            **{field: False for field in fixed_store._FALSE_FIELDS},
        }
    )
    return receipt, body


def _exact_service(projection: dict[str, object]):
    return preflight._ServiceConfiguration(
        service_type=preflight._SERVICE_WIN32_OWN_PROCESS,
        start_type=preflight._SERVICE_DEMAND_START,
        error_control=preflight._SERVICE_ERROR_NORMAL,
        binary_path=f'"{projection["image_final_volume_guid_path"]}"',
        start_account="LocalSystem",
        service_sid_type=preflight._SERVICE_SID_TYPE_RESTRICTED,
    )


class WindowsOwnerProvisioningPreflightCandidateTests(unittest.TestCase):
    def test_public_api_is_zero_argument_and_has_no_shell_or_environment_selector(self):
        signature = inspect.signature(
            preflight.observe_fixed_windows_owner_provisioning_preflight_candidate
        )
        self.assertEqual(tuple(signature.parameters), ())
        source = inspect.getsource(preflight)
        for forbidden in (
            "os.environ",
            "os.getenv",
            "subprocess",
            "sc.exe",
            "powershell",
            "shutil.which",
        ):
            self.assertNotIn(forbidden, source.casefold())

    def test_missing_fixed_store_is_deterministic_no_go_and_stops_before_scm(self):
        with (
            patch.object(
                fixed_store,
                "_observe_fixed_windows_owner_policy_store_candidate_with_body",
                side_effect=fixed_store.P0WindowsFixedOwnerPolicyStoreCandidateError(
                    "absent"
                ),
            ),
            patch.object(
                preflight, "_observe_fixed_service_configuration_candidate"
            ) as service,
        ):
            first = preflight._observe_preflight_candidate()
            second = preflight._observe_preflight_candidate()
        self.assertEqual(first, second)
        self.assertEqual(first["decision"], "NO_GO")
        self.assertEqual(first["failure_stage"], "FIXED_STORE")
        self.assertIn(
            "FIXED_OWNER_POLICY_STORE_NOT_VERIFIED", first["blocker_codes"]
        )
        service.assert_not_called()
        material = dict(first)
        declared = material.pop("receipt_sha256")
        self.assertEqual(declared, fixture.deployment.canonical_sha256(material))

    def test_valid_v2_store_service_absence_is_structured_no_go(self):
        outcome = _valid_fixed_outcome()
        with (
            patch.object(
                fixed_store,
                "_observe_fixed_windows_owner_policy_store_candidate_with_body",
                return_value=outcome,
            ),
            patch.object(
                preflight,
                "_observe_fixed_service_configuration_candidate",
                return_value=None,
            ),
            patch.object(
                preflight, "_observe_service_image_identity_candidate"
            ) as image,
        ):
            receipt = preflight._observe_preflight_candidate()
        self.assertTrue(receipt["fixed_policy_store_candidate_observed"])
        self.assertTrue(receipt["owner_policy_v2_contract_verified"])
        self.assertTrue(receipt["deployment_projection_cross_binding_verified"])
        self.assertFalse(receipt["service_configuration_candidate_verified"])
        self.assertEqual(receipt["failure_stage"], "SERVICE_CONFIGURATION")
        image.assert_not_called()

    def test_service_projection_is_preserved_when_image_observation_fails(self):
        outcome = _valid_fixed_outcome()
        projection = outcome[1]["deployment_projection"]
        service = _exact_service(projection)
        with (
            patch.object(
                fixed_store,
                "_observe_fixed_windows_owner_policy_store_candidate_with_body",
                return_value=outcome,
            ),
            patch.object(
                preflight,
                "_observe_fixed_service_configuration_candidate",
                return_value=service,
            ),
            patch.object(
                preflight,
                "_observe_service_image_identity_candidate",
                side_effect=preflight._StageNoGo(
                    "SERVICE_IMAGE",
                    ("SERVICE_IMAGE_IDENTITY_NOT_VERIFIED",),
                ),
            ),
        ):
            receipt = preflight._observe_preflight_candidate()
        self.assertEqual(receipt["failure_stage"], "SERVICE_IMAGE")
        self.assertTrue(receipt["service_configuration_candidate_verified"])
        self.assertEqual(
            receipt["service_configuration_projection"],
            preflight._validate_service_configuration_candidate(
                projection, service
            ),
        )
        self.assertEqual(receipt["service_image_identity_projection"], {})

    def test_v1_is_hard_rejected_before_scm(self):
        body = v1_fixture._body()
        body_bytes, signature_bytes = v1_fixture._contract_bytes(body)
        contract = policy.validate_presented_windows_owner_policy_contract(
            policy_body_bytes=body_bytes,
            policy_signature_bytes=signature_bytes,
        )
        fixed_receipt, _v2_body = _valid_fixed_outcome()
        body_hash = hashlib.sha256(body_bytes).hexdigest()
        fixed_receipt["policy_body_bytes_sha256"] = body_hash
        fixed_receipt["owner_policy_contract_receipt"] = contract
        fixed_receipt["owner_policy_contract_receipt_declared_sha256"] = contract[
            "receipt_sha256"
        ]
        fixed_receipt["owner_policy_contract_receipt_full_canonical_sha256"] = (
            fixture.deployment.canonical_sha256(contract)
        )
        bootstrap = fixed_receipt[
            "bootstrap_policy_signature_candidate_receipt"
        ]
        assert isinstance(bootstrap, dict)
        bootstrap["policy_body_bytes_sha256"] = body_hash
        bootstrap["owner_policy_contract_receipt"] = contract
        bootstrap["owner_policy_contract_receipt_declared_sha256"] = contract[
            "receipt_sha256"
        ]
        _rehash(bootstrap)
        fixed_receipt[
            "bootstrap_policy_signature_candidate_receipt_declared_sha256"
        ] = bootstrap["receipt_sha256"]
        _rehash(fixed_receipt)
        with (
            patch.object(
                fixed_store,
                "_observe_fixed_windows_owner_policy_store_candidate_with_body",
                return_value=(fixed_receipt, body),
            ),
            patch.object(
                preflight, "_observe_fixed_service_configuration_candidate"
            ) as service,
        ):
            receipt = preflight._observe_preflight_candidate()
        self.assertEqual(receipt["failure_stage"], "OWNER_POLICY_V2")
        self.assertTrue(receipt["v1_future_authority_hard_rejected"])
        self.assertFalse(receipt["owner_policy_v2_contract_verified"])
        service.assert_not_called()

    def test_forged_nested_contract_is_rejected_even_if_outer_receipt_is_resealed(self):
        invalid_outer, invalid_body = _valid_fixed_outcome()
        invalid_outer.pop("gate_status")
        _rehash(invalid_outer)
        with patch.object(
            fixed_store,
            "_observe_fixed_windows_owner_policy_store_candidate_with_body",
            return_value=(invalid_outer, invalid_body),
        ):
            invalid_receipt = preflight._observe_preflight_candidate()
        self.assertEqual(invalid_receipt["failure_stage"], "FIXED_STORE")
        self.assertFalse(
            invalid_receipt["fixed_policy_store_candidate_observed"]
        )
        self.assertFalse(invalid_receipt["v1_future_authority_hard_rejected"])

        fixed_receipt, body = _valid_fixed_outcome()
        forged = deepcopy(fixed_receipt)
        contract = forged["owner_policy_contract_receipt"]
        assert isinstance(contract, dict)
        contract["future_authority_policy_version_eligible"] = False
        _rehash(contract)
        bootstrap = forged["bootstrap_policy_signature_candidate_receipt"]
        assert isinstance(bootstrap, dict)
        bootstrap["owner_policy_contract_receipt"] = contract
        bootstrap["owner_policy_contract_receipt_declared_sha256"] = contract[
            "receipt_sha256"
        ]
        _rehash(bootstrap)
        forged["owner_policy_contract_receipt_declared_sha256"] = contract[
            "receipt_sha256"
        ]
        forged["owner_policy_contract_receipt_full_canonical_sha256"] = (
            fixture.deployment.canonical_sha256(contract)
        )
        forged[
            "bootstrap_policy_signature_candidate_receipt_declared_sha256"
        ] = bootstrap["receipt_sha256"]
        _rehash(forged)
        with patch.object(
            preflight, "_observe_fixed_service_configuration_candidate"
        ) as service:
            with self.assertRaises(preflight._StageNoGo):
                preflight._validated_projection_from_fixed_outcome(forged, body)
        service.assert_not_called()
        with (
            patch.object(
                fixed_store,
                "_observe_fixed_windows_owner_policy_store_candidate_with_body",
                return_value=(forged, body),
            ),
            patch.object(
                preflight, "_observe_fixed_service_configuration_candidate"
            ) as service,
        ):
            generic_v2_failure = preflight._observe_preflight_candidate()
        self.assertEqual(
            generic_v2_failure["failure_stage"], "OWNER_POLICY_V2"
        )
        self.assertFalse(
            generic_v2_failure["v1_future_authority_hard_rejected"]
        )
        service.assert_not_called()

        fixed_receipt, body = _valid_fixed_outcome()
        bootstrap = fixed_receipt[
            "bootstrap_policy_signature_candidate_receipt"
        ]
        assert isinstance(bootstrap, dict)
        bootstrap["owner_authority_verified"] = True
        _rehash(bootstrap)
        fixed_receipt[
            "bootstrap_policy_signature_candidate_receipt_declared_sha256"
        ] = bootstrap["receipt_sha256"]
        _rehash(fixed_receipt)
        with self.assertRaises(preflight._StageNoGo):
            preflight._validated_projection_from_fixed_outcome(
                fixed_receipt, body
            )

        fixed_receipt, _body_a = _valid_fixed_outcome()
        body_b = fixture._v2_body()
        projection_b = body_b["deployment_projection"]
        assert isinstance(projection_b, dict)
        projection_b["image_sha256"] = "f" * 64
        body_b["deployment_projection"] = fixture.deployment.with_artifact_hash(
            projection_b
        )
        body_b["owner_anchor_sha256"] = fixture._derive_v2_anchor(body_b)
        v1_fixture._rehash(body_b)
        body_b_hash = hashlib.sha256(policy.json_file_bytes(body_b)).hexdigest()
        fixed_receipt["policy_body_bytes_sha256"] = body_b_hash
        bootstrap = fixed_receipt[
            "bootstrap_policy_signature_candidate_receipt"
        ]
        assert isinstance(bootstrap, dict)
        bootstrap["policy_body_bytes_sha256"] = body_b_hash
        _rehash(bootstrap)
        fixed_receipt[
            "bootstrap_policy_signature_candidate_receipt_declared_sha256"
        ] = bootstrap["receipt_sha256"]
        _rehash(fixed_receipt)
        with self.assertRaises(preflight._StageNoGo):
            preflight._validated_projection_from_fixed_outcome(
                fixed_receipt, body_b
            )

    def test_service_configuration_attack_matrix_is_exact(self):
        projection = fixture._projection()
        exact = _exact_service(projection)
        observed = preflight._validate_service_configuration_candidate(
            projection, exact
        )
        self.assertEqual(
            observed["service_sid_type"], fixture.deployment.SERVICE_SID_TYPE
        )
        mutations = {
            "service_type": exact.service_type | 0x20,
            "start_type": 2,
            "error_control": 0,
            "binary_path": exact.binary_path + " --attacker",
            "start_account": "NetworkService",
            "service_sid_type": 1,
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                values = dict(exact.__dict__)
                values[field] = value
                with self.assertRaises(preflight._StageNoGo):
                    preflight._validate_service_configuration_candidate(
                        projection, preflight._ServiceConfiguration(**values)
                    )

    def test_image_failure_is_normalized_after_exact_service_candidate(self):
        fixed_receipt, body = _valid_fixed_outcome()
        projection = body["deployment_projection"]
        assert isinstance(projection, dict)
        with (
            patch.object(
                fixed_store,
                "_observe_fixed_windows_owner_policy_store_candidate_with_body",
                return_value=(fixed_receipt, body),
            ),
            patch.object(
                preflight,
                "_observe_fixed_service_configuration_candidate",
                return_value=_exact_service(projection),
            ),
            patch.object(
                preflight,
                "_observe_service_image_identity_candidate",
                side_effect=preflight._StageNoGo(
                    "SERVICE_IMAGE",
                    ("SERVICE_IMAGE_IDENTITY_NOT_VERIFIED",),
                ),
            ),
        ):
            receipt = preflight._observe_preflight_candidate()
        self.assertTrue(receipt["service_configuration_candidate_verified"])
        self.assertFalse(receipt["service_image_identity_candidate_verified"])
        self.assertEqual(receipt["failure_stage"], "SERVICE_IMAGE")

    def test_held_image_composition_checks_identity_hash_and_pre_post_stability(self):
        raw = b"native-verifier-image"
        projection = fixture._projection()
        projection["image_sha256"] = hashlib.sha256(raw).hexdigest()
        projection = fixture.deployment.with_artifact_hash(projection)
        snapshot = preflight.fixed._ObjectSnapshot(
            final_path=projection["image_final_volume_guid_path"],
            volume_serial=int(projection["image_volume_serial_decimal"]),
            file_id=projection["image_file_id_128_hex"],
            basic=(1, 2, 3, 4, 0),
            standard=(len(raw), len(raw), 1, False, False),
            reparse_tag=0,
            streams=(("::$DATA", len(raw), len(raw)),),
        )
        with (
            patch.object(preflight.fixed, "_Win32", return_value=object()),
            patch.object(preflight, "_HandleFlagsApi", return_value=object()),
            patch.object(preflight, "_assert_non_inheritable"),
            patch.object(
                preflight.fixed,
                "_open_handle",
                return_value=nullcontext(SimpleNamespace(value=7)),
            ),
            patch.object(preflight.fixed, "_assert_regular_single_link"),
            patch.object(preflight.fixed, "_read_handle_exact", return_value=raw),
            patch.object(
                preflight.fixed,
                "_query_snapshot",
                side_effect=[snapshot, snapshot],
            ),
        ):
            observed = preflight._observe_service_image_identity_candidate(
                projection
            )
        self.assertTrue(observed["held_handle_pre_post_stable"])

        drifted = preflight.fixed._ObjectSnapshot(
            final_path=snapshot.final_path,
            volume_serial=snapshot.volume_serial,
            file_id="f" * 32,
            basic=snapshot.basic,
            standard=snapshot.standard,
            reparse_tag=snapshot.reparse_tag,
            streams=snapshot.streams,
        )
        with (
            patch.object(preflight.fixed, "_Win32", return_value=object()),
            patch.object(preflight, "_HandleFlagsApi", return_value=object()),
            patch.object(preflight, "_assert_non_inheritable"),
            patch.object(
                preflight.fixed,
                "_open_handle",
                return_value=nullcontext(SimpleNamespace(value=7)),
            ),
            patch.object(preflight.fixed, "_assert_regular_single_link"),
            patch.object(preflight.fixed, "_read_handle_exact", return_value=raw),
            patch.object(
                preflight.fixed,
                "_query_snapshot",
                side_effect=[snapshot, drifted],
            ),
        ):
            with self.assertRaises(preflight._StageNoGo):
                preflight._observe_service_image_identity_candidate(projection)

    def test_all_green_python_mocks_remain_non_authoritative_no_go(self):
        fixed_receipt, body = _valid_fixed_outcome()
        projection = body["deployment_projection"]
        assert isinstance(projection, dict)
        image_projection = {
            "final_volume_guid_path": projection["image_final_volume_guid_path"],
            "held_handle_pre_post_stable": True,
        }
        with (
            patch.object(
                fixed_store,
                "_observe_fixed_windows_owner_policy_store_candidate_with_body",
                return_value=(fixed_receipt, body),
            ),
            patch.object(
                preflight,
                "_observe_fixed_service_configuration_candidate",
                return_value=_exact_service(projection),
            ),
            patch.object(
                preflight,
                "_observe_service_image_identity_candidate",
                return_value=image_projection,
            ),
        ):
            receipt = preflight._observe_preflight_candidate()
        self.assertTrue(receipt["service_configuration_candidate_verified"])
        self.assertTrue(receipt["service_image_identity_candidate_verified"])
        self.assertEqual(receipt["failure_stage"], "NATIVE_EXTERNAL_EVIDENCE")
        for field in preflight._ALWAYS_FALSE_FIELDS:
            self.assertFalse(receipt[field], field)
        self.assertIn("SIGNED_NATIVE_OBSERVER_NOT_VERIFIED", receipt["blocker_codes"])
        self.assertEqual(receipt["decision"], "NO_GO")

    def test_non_windows_gate_precedes_any_observer(self):
        with (
            patch.object(preflight, "_IS_WINDOWS", False),
            patch.object(preflight, "_observe_preflight_candidate") as observer,
        ):
            with self.assertRaisesRegex(
                preflight.P0WindowsOwnerProvisioningPreflightCandidateError,
                "Windows-only",
            ):
                preflight.observe_fixed_windows_owner_provisioning_preflight_candidate()
        observer.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Windows host preflight smoke")
    def test_current_windows_host_never_grants_authority(self):
        receipt = (
            preflight.observe_fixed_windows_owner_provisioning_preflight_candidate()
        )
        self.assertEqual(receipt["decision"], "NO_GO")
        self.assertEqual(receipt["credited_actual_source_claim_count"], 0)
        self.assertEqual(receipt["credited_actual_a_context_review_count"], 0)
        for field in preflight._ALWAYS_FALSE_FIELDS:
            self.assertFalse(receipt[field], field)


if __name__ == "__main__":
    unittest.main()
