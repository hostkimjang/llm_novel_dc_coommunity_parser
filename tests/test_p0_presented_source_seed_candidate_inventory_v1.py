from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path
import unittest

from src.llm_batch.grounding import (
    p0_presented_source_seed_candidate_inventory_v1_contract as contract,
)
from src.llm_batch.grounding import (
    p0_presented_source_seed_candidate_inventory_v1_parent_validator as parent,
)


ROOT = Path(__file__).resolve().parents[1]


def reseal(value: dict[str, object], field: str = "artifact_sha256") -> bytes:
    material = copy.deepcopy(value)
    material.pop(field, None)
    material[field] = contract.canonical_sha256(material)
    return contract.canonical_file_bytes(material)


class PresentedSourceSeedCandidateInventoryV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.legacy_artifacts = {
            path: (ROOT / path).read_bytes() for path in contract.LEGACY_ARTIFACT_PATHS
        }
        cls.registry_raw = contract.build_registry_bytes()
        cls.registry_inventory_raw = contract.build_registry_inventory_bytes(cls.registry_raw)
        cls.legacy_inventory_raw = contract.build_legacy_quality_inventory_bytes(
            cls.legacy_artifacts
        )
        cls.receipt_raw = contract.build_receipt_bytes(
            cls.registry_raw,
            cls.registry_inventory_raw,
            cls.legacy_inventory_raw,
            cls.legacy_artifacts,
        )

    def test_exact_eight_urls_a3_b5_and_four_lineage_families(self):
        rows = contract.validate_registry_bytes(self.registry_raw)
        self.assertEqual(8, len(rows))
        self.assertEqual({"A": 3, "B": 5}, dict(__import__("collections").Counter(row["track"] for row in rows)))
        self.assertEqual(4, len({row["source_lineage"] for row in rows}))
        self.assertEqual(
            [spec[2] for spec in contract.SEED_SPECIFICATIONS],
            [row["canonical_url"] for row in rows],
        )
        self.assertEqual(rows[0]["source_lineage"], rows[1]["source_lineage"])
        self.assertEqual(1, len({row["source_lineage"] for row in rows[4:]}))

    def test_all_candidates_are_unverified_unrun_rights_unknown_and_ineligible(self):
        rows = contract.validate_registry_bytes(self.registry_raw)
        for row in rows:
            self.assertEqual(
                "WORK_ALIAS_LIST" if row["track"] == "A" else "COMMUNITY_LEXICON_LIST",
                row["record_type"],
            )
            self.assertNotIn("source_profile", row)
            self.assertIn("format_hint", row)
            self.assertEqual("PENDING_CAPTURE_ADAPTER", row["source_profile_status"])
            self.assertEqual("PRESENTED_UNVERIFIED", row["status"])
            self.assertIsNone(row["attested_at"])
            self.assertEqual("NOT_ATTESTED", row["attestation_status"])
            self.assertEqual("NOT_RUN", row["capture_status"])
            self.assertEqual("NOT_RUN", row["parser_status"])
            self.assertEqual("UNKNOWN_FAIL_CLOSED", row["rights_status"])
            self.assertEqual("REFERENCE_CANDIDATE_ONLY", row["semantic_status"])
            self.assertFalse(row["independence_eligible"])
            self.assertTrue(all(row[field] is False for field in contract._CAPABILITY_FIELDS))

    def test_seed_rows_have_no_semantic_judgment_fields(self):
        rows = contract.validate_registry_bytes(self.registry_raw)
        forbidden_fragments = ("target", "truth", "definition", "judg")
        for row in rows:
            lowered = {key.lower() for key in row}
            self.assertFalse(any(fragment in key for key in lowered for fragment in forbidden_fragments))

    def test_registry_is_canonical_and_hash_bound(self):
        rows = contract.validate_registry_bytes(self.registry_raw)
        self.assertEqual(
            self.registry_raw,
            b"".join(contract.canonical_file_bytes(row) for row in rows),
        )
        for row in rows:
            material = dict(row)
            presented = material.pop("row_sha256")
            self.assertEqual(contract.canonical_sha256(material), presented)
        inventory = contract.validate_registry_inventory_bytes(
            self.registry_inventory_raw, self.registry_raw
        )
        self.assertEqual(hashlib.sha256(self.registry_raw).hexdigest(), inventory["registry_raw_sha256"])
        self.assertEqual(contract.COMPONENT_MANIFEST_SHA256, inventory["component_manifest_sha256"])

    def test_legacy_inventory_uses_current_bytes_and_surfaces_stale_binding(self):
        inventory = contract.validate_legacy_quality_inventory_bytes(
            self.legacy_inventory_raw, self.legacy_artifacts
        )
        rows = inventory["artifact_rows"]
        for row in rows:
            raw = self.legacy_artifacts[row["path"]]
            self.assertEqual(len(raw), row["actual_bytes"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row["actual_sha256"])
        self.assertEqual(7, len(rows))
        self.assertTrue(all(row["identity_pin_verified"] for row in rows))
        self.assertEqual("SHA_MATCH_BYTES_UNAVAILABLE", rows[0]["binding_status"])
        ledger = rows[2]
        self.assertEqual("STALE_PARENT_BINDING", ledger["binding_status"])
        self.assertEqual(
            "717c6e52b725f0953716b95412035c4bba96ff3ce2d2e3946bb4cb47cc3c1102",
            ledger["parent_expected_sha256"],
        )
        self.assertEqual(
            "b7e75467744a1cf769763d459e3ebcfbf613bbaff703a0b6dedd55d29d905998",
            ledger["actual_sha256"],
        )
        self.assertEqual(1, inventory["stale_parent_binding_count"])
        self.assertEqual(["LABEL_LEDGER"], inventory["stale_parent_binding_roles"])
        self.assertEqual(1, inventory["role_blocker_count"])
        self.assertEqual("LABEL_LEDGER", inventory["role_blockers"][0]["artifact_role"])
        self.assertEqual("LEGACY_LABEL_LEDGER_SHA256_BINDING_STALE", inventory["role_blockers"][0]["blocker_code"])
        self.assertEqual("NOT_ESTIMABLE", inventory["legacy_metric_status"])

    def test_pool_statistics_are_recomputed_at_distinct_grains(self):
        inventory = json.loads(self.legacy_inventory_raw)
        pools = {pool["pool_id"]: pool for pool in inventory["pool_summaries"]}
        self.assertEqual(5, len(pools))
        self.assertEqual(5, inventory["distinct_pool_grain_count"])
        self.assertEqual(5, len({pool["grain"] for pool in pools.values()}))
        golden = pools["golden18_label_pool"]
        self.assertEqual((18, 9, 6, 3), (golden["row_count"], golden["candidate_labeled_count"], golden["nil_labeled_count"], golden["unjudged_count"]))
        refresh = pools["source_refresh_pool"]
        self.assertEqual((39, 39, 87, 39), (refresh["row_count"], refresh["unique_post_id_count"], refresh["url_reference_count"], refresh["pending_count"]))
        judge = pools["judge3905_shadow_pool"]
        self.assertEqual((1505, 1505, 0, 198, 2, 649), (judge["row_count"], judge["unique_post_id_count"], judge["candidate_count_positive_count"], judge["public_title_present_count"], judge["evidence_catalog_present_count"], judge["web_unverified_count"]))
        self.assertEqual(0, pools["reserved_p01_pool"]["row_count"])
        self.assertEqual(0, pools["reserved_p02_pool"]["row_count"])
        self.assertTrue(pools["reserved_p01_pool"]["empty_bytes_verified"])
        self.assertTrue(pools["reserved_p02_pool"]["empty_bytes_verified"])
        self.assertTrue(inventory["must_not_sum_across_pools"])
        self.assertIsNone(inventory["combined_unique_denominator"])
        self.assertEqual(0, inventory["combined_metric_denominator"])

    def test_receipt_all_actual_credit_index_and_stat_fields_fail_closed(self):
        receipt = contract.validate_receipt_bytes(
            self.receipt_raw,
            self.registry_raw,
            self.registry_inventory_raw,
            self.legacy_inventory_raw,
            self.legacy_artifacts,
        )
        for field in (
            "eligible_independence_group_count",
            "actual_source_snapshot_count",
            "actual_source_claim_count",
            "actual_context_review_count",
            "actual_credit_count",
            "derived_index_row_count",
            "metric_denominator",
        ):
            self.assertEqual(0, receipt[field])
        self.assertIsNone(receipt["statistical_estimate"])
        self.assertEqual("NOT_ESTIMABLE", receipt["metric_status"])
        self.assertTrue(receipt["must_not_sum_across_pools"])
        self.assertIsNone(receipt["combined_unique_denominator"])
        self.assertFalse(receipt["action_applied"])
        self.assertEqual("NONE_SHADOW_ONLY", receipt["operational_effect"])
        self.assertIn("LEGACY_LABEL_LEDGER_SHA256_BINDING_STALE", receipt["blockers"])

    def test_parent_replays_without_producer(self):
        result = parent.validate_presented_source_seed_candidate_bundle(
            registry_raw=self.registry_raw,
            registry_inventory_raw=self.registry_inventory_raw,
            legacy_inventory_raw=self.legacy_inventory_raw,
            receipt_raw=self.receipt_raw,
            legacy_artifacts=self.legacy_artifacts,
        )
        self.assertEqual(8, result["seed_count"])
        self.assertEqual(0, result["actual_credit_count"])
        self.assertEqual(
            "NO_GO_INDEPENDENT_PRESENTED_SOURCE_SEED_REPLAY_ONLY",
            result["gate_status"],
        )
        self.assertEqual(
            contract.COMPONENT_MANIFEST_SHA256,
            parent.EXPECTED_COMPONENT_MANIFEST_SHA256,
        )
        self.assertRegex(result["receipt_sha256"], r"^[0-9a-f]{64}$")

    def test_registry_mutation_rejected_even_when_row_resealed(self):
        rows = contract.validate_registry_bytes(self.registry_raw)
        rows[0]["canonical_url"] += "/changed"
        material = dict(rows[0])
        material.pop("row_sha256")
        rows[0]["row_sha256"] = contract.canonical_sha256(material)
        forged = b"".join(contract.canonical_file_bytes(row) for row in rows)
        with self.assertRaisesRegex(contract.P0PresentedSourceSeedCandidateError, "exact specification"):
            contract.validate_registry_bytes(forged)

    def test_semantic_field_injection_rejected(self):
        first, *rest = self.registry_raw.splitlines()
        row = json.loads(first)
        row["definition"] = "forbidden"
        material = dict(row)
        material.pop("row_sha256")
        row["row_sha256"] = contract.canonical_sha256(material)
        forged = contract.canonical_file_bytes(row) + b"\n".join(rest) + b"\n"
        with self.assertRaises(contract.P0PresentedSourceSeedCandidateError):
            contract.validate_registry_bytes(forged)

    def test_registry_inventory_reseal_cannot_change_counts_or_raw_binding(self):
        value = json.loads(self.registry_inventory_raw)
        value["lineage_family_count"] = 8
        with self.assertRaisesRegex(contract.P0PresentedSourceSeedCandidateError, "replay mismatch"):
            contract.validate_registry_inventory_bytes(reseal(value), self.registry_raw)
        value = json.loads(self.registry_inventory_raw)
        value["registry_raw_sha256"] = "0" * 64
        with self.assertRaisesRegex(contract.P0PresentedSourceSeedCandidateError, "replay mismatch"):
            contract.validate_registry_inventory_bytes(reseal(value), self.registry_raw)

    def test_legacy_stale_blocker_cannot_be_resealed_away(self):
        value = json.loads(self.legacy_inventory_raw)
        value["role_blockers"] = []
        value["role_blocker_count"] = 0
        value["stale_parent_binding_count"] = 0
        with self.assertRaisesRegex(contract.P0PresentedSourceSeedCandidateError, "replay mismatch"):
            contract.validate_legacy_quality_inventory_bytes(reseal(value), self.legacy_artifacts)

    def test_legacy_artifact_allowlist_and_bytes_are_exact(self):
        reordered = dict(reversed(list(self.legacy_artifacts.items())))
        with self.assertRaisesRegex(contract.P0PresentedSourceSeedCandidateError, "ordered allowlist"):
            contract.build_legacy_quality_inventory_bytes(reordered)
        mutated = dict(self.legacy_artifacts)
        mutated[contract.LEGACY_LABEL_LEDGER_PATH] += b" "
        with self.assertRaisesRegex(contract.P0PresentedSourceSeedCandidateError, "identity pin mismatch: LABEL_LEDGER"):
            contract.build_legacy_quality_inventory_bytes(mutated)

    def test_coordinated_reseal_and_forged_counts_or_bool_are_rejected_by_identity(self):
        ledger = json.loads(self.legacy_artifacts[contract.LEGACY_LABEL_LEDGER_PATH])
        ledger["counts"]["rows"] = True
        mutated = dict(self.legacy_artifacts)
        mutated[contract.LEGACY_LABEL_LEDGER_PATH] = json.dumps(ledger, ensure_ascii=False).encode("utf-8")
        with self.assertRaisesRegex(contract.P0PresentedSourceSeedCandidateError, "identity pin mismatch: LABEL_LEDGER"):
            contract.build_legacy_quality_inventory_bytes(mutated)
        refresh = json.loads(self.legacy_artifacts[contract.SOURCE_REFRESH_QUEUE_PATH])
        refresh["coverage"]["rows"] = 40
        mutated = dict(self.legacy_artifacts)
        mutated[contract.SOURCE_REFRESH_QUEUE_PATH] = json.dumps(refresh, ensure_ascii=False).encode("utf-8")
        with self.assertRaisesRegex(contract.P0PresentedSourceSeedCandidateError, "identity pin mismatch: SOURCE_REFRESH_QUEUE"):
            contract.build_legacy_quality_inventory_bytes(mutated)

    def test_raw_stat_replayers_reject_bool_and_forged_partition_counts(self):
        ledger = json.loads(self.legacy_artifacts[contract.LEGACY_LABEL_LEDGER_PATH])
        comparison = json.loads(self.legacy_artifacts[contract.LEGACY_COMPARISON_PATH])
        forged = copy.deepcopy(ledger)
        forged["counts"]["rows"] = True
        with self.assertRaisesRegex(contract.P0PresentedSourceSeedCandidateError, "non-bool integer"):
            contract._validate_golden18(forged, comparison)
        forged = copy.deepcopy(ledger)
        forged["counts"]["candidate_truth"] = 8
        with self.assertRaisesRegex(contract.P0PresentedSourceSeedCandidateError, "counts replay mismatch"):
            contract._validate_golden18(forged, comparison)
        refresh = json.loads(self.legacy_artifacts[contract.SOURCE_REFRESH_QUEUE_PATH])
        refresh["coverage"]["rows"] = True
        with self.assertRaisesRegex(contract.P0PresentedSourceSeedCandidateError, "non-bool integer"):
            contract._validate_refresh_queue(refresh)

    def test_parent_also_rejects_coordinated_legacy_reseal(self):
        mutated = dict(self.legacy_artifacts)
        ledger = json.loads(mutated[contract.LEGACY_LABEL_LEDGER_PATH])
        ledger["counts"]["rows"] = 18
        mutated[contract.LEGACY_LABEL_LEDGER_PATH] = contract.canonical_file_bytes(ledger)
        with self.assertRaisesRegex(parent.P0PresentedSourceSeedParentError, "identity mismatch: LABEL_LEDGER"):
            parent.validate_presented_source_seed_candidate_bundle(
                registry_raw=self.registry_raw,
                registry_inventory_raw=self.registry_inventory_raw,
                legacy_inventory_raw=self.legacy_inventory_raw,
                receipt_raw=self.receipt_raw,
                legacy_artifacts=mutated,
            )

    def test_empty_reserved_file_becoming_nonempty_is_identity_failure(self):
        for path, role in ((contract.ROWS_P01_PATH, "ROWS_P01"), (contract.ROWS_P02_PATH, "ROWS_P02")):
            mutated = dict(self.legacy_artifacts)
            mutated[path] = b"not-empty\n"
            with self.assertRaisesRegex(contract.P0PresentedSourceSeedCandidateError, f"identity pin mismatch: {role}"):
                contract.build_legacy_quality_inventory_bytes(mutated)

    def test_extra_pool_or_overlap_summation_claim_is_rejected(self):
        value = json.loads(self.legacy_inventory_raw)
        value["pool_summaries"].append(copy.deepcopy(value["pool_summaries"][0]))
        value["pool_count"] = 6
        with self.assertRaisesRegex(contract.P0PresentedSourceSeedCandidateError, "replay mismatch"):
            contract.validate_legacy_quality_inventory_bytes(reseal(value), self.legacy_artifacts)
        value = json.loads(self.legacy_inventory_raw)
        value["must_not_sum_across_pools"] = False
        value["combined_unique_denominator"] = 1562
        value["combined_metric_denominator"] = 1562
        with self.assertRaisesRegex(contract.P0PresentedSourceSeedCandidateError, "replay mismatch"):
            contract.validate_legacy_quality_inventory_bytes(reseal(value), self.legacy_artifacts)

    def test_receipt_reseal_cannot_claim_actual_or_metrics(self):
        for field, value in (
            ("actual_credit_count", 1),
            ("derived_index_row_count", 1),
            ("metric_denominator", 8),
            ("statistical_estimate", 0.9),
            ("source_attestation_verified", True),
            ("production_approval", True),
        ):
            forged = json.loads(self.receipt_raw)
            forged[field] = value
            with self.assertRaisesRegex(contract.P0PresentedSourceSeedCandidateError, "replay mismatch"):
                contract.validate_receipt_bytes(
                    reseal(forged),
                    self.registry_raw,
                    self.registry_inventory_raw,
                    self.legacy_inventory_raw,
                    self.legacy_artifacts,
                )

    def test_raw_and_component_binding_swap_is_rejected(self):
        forged = json.loads(self.receipt_raw)
        forged["registry_inventory_artifact_sha256"] = forged["legacy_inventory_artifact_sha256"]
        with self.assertRaisesRegex(contract.P0PresentedSourceSeedCandidateError, "replay mismatch"):
            contract.validate_receipt_bytes(
                reseal(forged), self.registry_raw, self.registry_inventory_raw,
                self.legacy_inventory_raw, self.legacy_artifacts
            )

    def test_noncanonical_duplicate_key_and_bom_are_rejected(self):
        with self.assertRaises(contract.P0PresentedSourceSeedCandidateError):
            contract.validate_registry_bytes(b"\xef\xbb\xbf" + self.registry_raw)
        first = self.registry_raw.splitlines()[0]
        duplicate = first[:-1] + b',"seed_id":"duplicate"}'
        forged = duplicate + b"\n" + b"\n".join(self.registry_raw.splitlines()[1:]) + b"\n"
        with self.assertRaises(contract.P0PresentedSourceSeedCandidateError):
            contract.validate_registry_bytes(forged)

    def test_contract_has_no_forbidden_runtime_import_or_call(self):
        path = ROOT / "src/llm_batch/grounding/p0_presented_source_seed_candidate_inventory_v1_contract.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        forbidden_imports = {"os", "pathlib", "subprocess", "socket", "requests", "urllib", "time", "random"}
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertFalse(imports & forbidden_imports)
        called = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertFalse(called & {"open", "exec", "eval", "compile", "__import__"})

    def test_parent_is_independent_and_does_not_import_producer(self):
        path = ROOT / "src/llm_batch/grounding/p0_presented_source_seed_candidate_inventory_v1_parent_validator.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertFalse(any("p0_presented_source_seed_candidate" in name for name in imported))
        self.assertNotIn("import contract", source)

    def test_parent_rejects_resealed_registry_variant(self):
        rows = contract.validate_registry_bytes(self.registry_raw)
        rows[1]["source_lineage"] = "lineage-forged-independent-mirror"
        rows[1]["independence_group_id"] = "lineage-forged-independent-mirror"
        material = dict(rows[1])
        material.pop("row_sha256")
        rows[1]["row_sha256"] = contract.canonical_sha256(material)
        forged_registry = b"".join(contract.canonical_file_bytes(row) for row in rows)
        with self.assertRaisesRegex(
            parent.P0PresentedSourceSeedParentError,
            "independent specification",
        ):
            parent.validate_presented_source_seed_candidate_bundle(
                registry_raw=forged_registry,
                registry_inventory_raw=self.registry_inventory_raw,
                legacy_inventory_raw=self.legacy_inventory_raw,
                receipt_raw=self.receipt_raw,
                legacy_artifacts=self.legacy_artifacts,
            )


if __name__ == "__main__":
    unittest.main()
