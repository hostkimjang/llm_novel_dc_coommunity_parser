from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.build_promotion_contract_n5_blind_judge import (
    BUILDER_VERSION,
    EXPECTED_POST_IDS,
    _outcomes_for_policy,
    _scan_runtime_literals,
    _validate_adjudication,
    _validate_golden_manifest,
    _validate_independent_identity_evidence,
    _validate_r6,
    _validate_source_manifest,
    build_judge,
    file_sha256,
    write_outputs,
)
from tools.safe_loss_flip_rate_probe import (
    ACCEPTABLE_OUTCOME_LEGACY_FIELDS,
    ACCEPTABLE_OUTCOME_REQUIRED_FIELDS,
    OUTCOME_CONTRACT_FIELDS,
    _match_acceptable_outcome,
    analyze_flip_rate,
    load_blind_judge,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_MANIFEST = ROOT / "docs/devs/loop642_promotion_contract_n5_source_input_manifest.json"
GOLDEN_MANIFEST = (
    ROOT
    / "out/regression_safe_grounding_20260626_000008_928006_loop01/golden/golden_manifest.json"
)
ADJUDICATION = ROOT / "docs/devs/loop641_merged375_adjusted_collateral_adjudication.json"
R6_AUDIT = ROOT / "docs/devs/loop642_promotion_contract_golden18_r6_i5_expected_audit.json"
R6_RESULT = (
    ROOT
    / "out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop642_promotion_contract_golden18_r6_i5_result.json"
)
INDEPENDENT_IDENTITY_EVIDENCE = (
    ROOT
    / "docs/devs/loop642_promotion_contract_n5_independent_identity_evidence_20260710.json"
)


class PromotionContractN5BlindJudgeBuilderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = build_judge(
            source_manifest_path=SOURCE_MANIFEST,
            golden_manifest_path=GOLDEN_MANIFEST,
            blind_adjudication_path=ADJUDICATION,
            independent_identity_evidence_path=INDEPENDENT_IDENTITY_EVIDENCE,
            r6_golden_audit_path=R6_AUDIT,
            r6_result_path=R6_RESULT,
            generated_at="2026-07-10T00:00:00+09:00",
        )

    @staticmethod
    def _write_json(path: Path, payload: object) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def _analyze_r6_row(self, post_id: str) -> dict:
        result_rows = json.loads(R6_RESULT.read_text(encoding="utf-8"))
        base = next(row for row in result_rows if str(row.get("post_id")) == post_id)
        repeats: list[dict] = []
        for index in range(5):
            row = copy.deepcopy(base)
            row["run_meta"]["run_id"] = f"builder-test-{post_id}-{index}"
            row["_flip_probe_result_binding"] = {"repeat_index": index}
            repeats.append(row)
        judge = next(
            row for row in self.report["rows"] if str(row.get("post_id")) == post_id
        )
        return analyze_flip_rate(
            result_rows=repeats,
            post_ids=[post_id],
            repeats=5,
            blind_judge={post_id: judge},
        )

    @staticmethod
    def _policy_pair() -> dict[str, str]:
        return {
            "title": "정책 기반 검증용 작품",
            "url": "https://example.invalid/novel/42",
        }

    @staticmethod
    def _observed_outcome(expected: dict) -> dict:
        observed = {
            field: expected[field]
            for field in (
                "public_title",
                "public_url",
                "candidate_title",
                "candidate_url",
                "decision_status",
                "publish_allowed",
                "candidate_preserved",
                "bypassed_gate",
                "scope_kind",
            )
        }
        observed.update(
            {
                "reason_codes": list(expected["required_reason_codes"]),
                "direct_bridge_sources": list(
                    expected["required_direct_bridge_sources"]
                ),
                "evidence_kinds": list(expected["required_evidence_kinds"]),
                "evidence_reason_codes": list(
                    expected["required_evidence_reason_codes"]
                ),
                "publish_supporting_evidence_kinds": list(
                    expected["required_publish_supporting_evidence_kinds"]
                ),
                "publish_supporting_evidence_reason_codes": list(
                    expected[
                        "required_publish_supporting_evidence_reason_codes"
                    ]
                ),
                "candidate_inventory_pairs": list(
                    expected.get("required_candidate_inventory_pairs") or []
                ),
                "input_fingerprint": "a" * 64,
                "contract_version": "promotion_contract_v2",
                "contract_consistency_issues": [],
                "canonical_publication_contract_gate": "GO",
                "canonical_publication_contract_violation_codes": [],
            }
        )
        return observed

    def test_builds_exact_modern_schema_and_loader_roundtrip(self):
        self.assertEqual(self.report["gate"], "GO")
        self.assertEqual(
            BUILDER_VERSION, "promotion-contract-n5-source-backed-blind-judge-v2"
        )
        self.assertEqual(
            self.report["matcher_contract"]["evidence_requirement_derivation"],
            "stratum_policy_plus_authoritative_source_identity",
        )
        self.assertIs(
            self.report["matcher_contract"][
                "observed_r6_trace_requirement_copy_allowed"
            ],
            False,
        )
        self.assertEqual(
            [str(row["post_id"]) for row in self.report["rows"]],
            list(EXPECTED_POST_IDS),
        )
        ocr_row = next(
            row for row in self.report["rows"] if str(row["post_id"]) == "11663540"
        )
        self.assertEqual(
            ocr_row["authoritative_identity"],
            {
                "title": "전 버튜버가 하고 싶은데요",
                "url": "https://novelpia.com/novel/275975",
            },
        )
        self.assertTrue(
            any(
                item.get("artifact") == "independent_identity_evidence"
                for item in ocr_row["source_evidence"]
            )
        )
        self.assertEqual(self.report["scope"]["expected_independent_result_count"], 25)
        self.assertEqual(
            [len(row["acceptable_outcomes"]) for row in self.report["rows"]],
            [4, 4, 1, 1, 1],
        )
        for row in self.report["rows"]:
            for outcome in row["acceptable_outcomes"]:
                self.assertFalse(set(outcome) & ACCEPTABLE_OUTCOME_LEGACY_FIELDS)
                self.assertFalse(set(outcome) - OUTCOME_CONTRACT_FIELDS)
                self.assertFalse(ACCEPTABLE_OUTCOME_REQUIRED_FIELDS - set(outcome))
                self.assertIs(outcome["bypassed_gate"], False)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "judge.json"
            self._write_json(path, self.report)
            loaded = load_blind_judge(path)
        self.assertEqual(set(loaded), set(EXPECTED_POST_IDS))

    def test_url_canonical_policy_requires_source_native_identity_provenance(self):
        pair = self._policy_pair()
        outcomes = _outcomes_for_policy(pair, stratum="URL_canonical")
        self.assertEqual(len(outcomes), 1)
        publish = outcomes[0]
        self.assertEqual(
            (publish["public_title"], publish["public_url"]),
            (pair["title"], pair["url"]),
        )
        self.assertEqual(
            publish["required_direct_bridge_sources"],
            ["source_native_non_image_work_relation_bridge"],
        )
        self.assertIn(
            "source_native_official_detail_identity",
            publish["required_evidence_reason_codes"],
        )
        self.assertIn(
            "source_native_non_image_work_relation_bridge",
            publish["required_publish_supporting_evidence_reason_codes"],
        )

    def test_independent_identity_evidence_rejects_title_or_url_drift(self):
        golden = _validate_golden_manifest(GOLDEN_MANIFEST)
        payload = json.loads(INDEPENDENT_IDENTITY_EVIDENCE.read_text(encoding="utf-8"))
        for field, value in (
            ("title", "runtime이 선택한 다른 제목"),
            ("url", "https://novelpia.com/novel/999999"),
        ):
            with self.subTest(field=field):
                mutated = copy.deepcopy(payload)
                mutated["rows"][0][field] = value
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / "identity.json"
                    self._write_json(path, mutated)
                    with self.assertRaises(ValueError):
                        _validate_independent_identity_evidence(path, golden=golden)

    def test_alias_policy_requires_alias_relation_and_preserves_safe_holds(self):
        pair = self._policy_pair()
        outcomes = _outcomes_for_policy(pair, stratum="aliases_including_아생갤")
        self.assertEqual(len(outcomes), 4)
        publish, current_candidate_only, current_hold, context_hold = outcomes
        self.assertIn("alias_bridge", publish["required_reason_codes"])
        self.assertEqual(
            publish["required_publish_supporting_evidence_kinds"], ["alias_bridge"]
        )
        self.assertEqual(current_candidate_only["decision_status"], "candidate_only")
        self.assertEqual(current_hold["decision_status"], "hold")
        self.assertEqual(
            [current_candidate_only["scope_kind"], current_hold["scope_kind"], context_hold["scope_kind"]],
            ["current_work", "current_work", "context_only"],
        )
        for hold in (current_candidate_only, current_hold, context_hold):
            self.assertEqual(
                hold["required_candidate_inventory_pairs"],
                [{"title": pair["title"], "url": pair["url"]}],
            )

    def test_ocr_policy_accepts_direct_image_exact_pair_without_incidental_trace(self):
        pair = self._policy_pair()
        outcomes = _outcomes_for_policy(pair, stratum="OCR")
        self.assertEqual(len(outcomes), 4)
        publish = outcomes[0]
        all_requirements = {
            value
            for field, values in publish.items()
            if field.startswith("required_") and isinstance(values, list)
            for value in values
            if isinstance(value, str)
        }
        self.assertNotIn("work_consumption_marker", all_requirements)
        self.assertNotIn("alias_bridge", all_requirements)
        self.assertIn("direct_image_work_surface_bridge", all_requirements)
        self.assertIn("ocr_catalog_official_title", all_requirements)
        self.assertNotIn("verified_image_ocr_work_title_publication", all_requirements)
        matched, reasons, malformed = _match_acceptable_outcome(
            self._observed_outcome(publish), publish, index=0
        )
        self.assertTrue(matched, reasons)
        self.assertFalse(malformed)

    def test_context_only_policy_allows_only_candidate_preserved_hold(self):
        pair = self._policy_pair()
        outcomes = _outcomes_for_policy(pair, stratum="context_only_HOLD")
        self.assertEqual(len(outcomes), 1)
        hold = outcomes[0]
        self.assertIs(hold["publish_allowed"], False)
        self.assertIs(hold["candidate_preserved"], True)
        self.assertEqual(hold["scope_kind"], "context_only")
        self.assertEqual(
            hold["required_candidate_inventory_pairs"],
            [{"title": pair["title"], "url": pair["url"]}],
        )

    def test_golden_stable_policy_excludes_incidental_release_context(self):
        pair = self._policy_pair()
        outcomes = _outcomes_for_policy(pair, stratum="golden_stable")
        self.assertEqual(len(outcomes), 1)
        publish = outcomes[0]
        self.assertEqual(
            publish["required_reason_codes"],
            [
                "official_title_exists",
                "row_discusses_work_as_work",
                "scope_current_work",
                "title_led_consumption_bridge",
                "official_detail_url",
                "title_url_pair_verified",
            ],
        )
        all_requirements = json.dumps(publish, ensure_ascii=False)
        self.assertNotIn(
            "official_detail_bracket_visual_release_context", all_requirements
        )
        self.assertNotIn("alias_bridge", all_requirements)
        self.assertNotIn("title_acceptance_accept", all_requirements)
        analysis = self._analyze_r6_row("11660237")
        self.assertEqual(
            analysis["gate"], "GO", analysis["rows"][0]["mismatch_reasons"]
        )
        matched, reasons, malformed = _match_acceptable_outcome(
            self._observed_outcome(publish), publish, index=0
        )
        self.assertTrue(matched, reasons)
        self.assertFalse(malformed)

    def test_wrong_selected_alias_candidate_is_not_accepted_as_preserved_expected_pair(self):
        analysis = self._analyze_r6_row("11694035")
        self.assertNotEqual(analysis["gate"], "GO")
        row = analysis["rows"][0]
        self.assertFalse(row["blind_judge_expected_match"])
        self.assertTrue(
            any(
                "candidate_title" in reason
                or "required_candidate_inventory_pairs_missing" in reason
                for reason in row["mismatch_reasons"]
            )
        )

    def test_source_manifest_hash_selection_and_coverage_mutations_fail_closed(self):
        original = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
        mutations = {}
        bad_hash = copy.deepcopy(original)
        bad_hash["artifact"]["byte_sha256"] = "0" * 64
        mutations["hash"] = bad_hash
        duplicate = copy.deepcopy(original)
        duplicate["selection"]["requested_strata_order"][1]["post_id"] = duplicate[
            "selection"
        ]["requested_strata_order"][0]["post_id"]
        mutations["duplicate"] = duplicate
        missing = copy.deepcopy(original)
        missing["selection"]["requested_strata_order"].pop()
        mutations["missing"] = missing
        extra = copy.deepcopy(original)
        extra["selection"]["requested_strata_order"].append(
            copy.deepcopy(extra["selection"]["requested_strata_order"][0])
        )
        mutations["extra"] = extra
        row_hash = copy.deepcopy(original)
        row_hash["selection"]["requested_strata_order"][0][
            "source_row_canonical_sha256"
        ] = "0" * 64
        mutations["source_row_hash"] = row_hash
        with tempfile.TemporaryDirectory() as tmp:
            for name, payload in mutations.items():
                with self.subTest(name=name):
                    path = Path(tmp) / f"{name}.json"
                    self._write_json(path, payload)
                    with self.assertRaises(ValueError):
                        _validate_source_manifest(path)

    def test_materialized_input_byte_mutation_fails_closed(self):
        manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
        source_input = (
            ROOT
            / "out/regression_safe_grounding_20260626_000008_928006_loop01/probe/loop642_promotion_contract_n5_source_input.jsonl"
        )
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            mutated_input = folder / "mutated.jsonl"
            mutated_input.write_bytes(source_input.read_bytes() + b"\n")
            manifest["artifact"]["path"] = mutated_input.as_posix()
            manifest_path = folder / "manifest.json"
            self._write_json(manifest_path, manifest)
            with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
                _validate_source_manifest(manifest_path)

    def test_golden_adjudication_r6_audit_and_result_mutations_fail_closed(self):
        source = _validate_source_manifest(SOURCE_MANIFEST)
        golden = _validate_golden_manifest(GOLDEN_MANIFEST)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)

            mutated_golden = json.loads(GOLDEN_MANIFEST.read_text(encoding="utf-8"))
            target = next(row for row in mutated_golden["rows"] if row["post_id"] == 11660237)
            target["expected_title_or_hypothesis"] += " 변조"
            golden_path = folder / "golden.json"
            self._write_json(golden_path, mutated_golden)
            changed_golden = _validate_golden_manifest(golden_path)
            with self.assertRaises(ValueError):
                _validate_r6(R6_AUDIT, R6_RESULT, golden=changed_golden)

            mutated_adjudication = json.loads(ADJUDICATION.read_text(encoding="utf-8"))
            target = next(
                row
                for row in mutated_adjudication["reviewed_rows"]
                if row["post_id"] == 11663514
            )
            target["blind_verdict"]["preferred_option"] = "B"
            adjudication_path = folder / "adjudication.json"
            self._write_json(adjudication_path, mutated_adjudication)
            with self.assertRaisesRegex(ValueError, "derivation digest mismatch"):
                _validate_adjudication(adjudication_path, source=source, golden=golden)

            mutated_audit = json.loads(R6_AUDIT.read_text(encoding="utf-8"))
            mutated_audit["rows"][0]["passed"] = False
            audit_path = folder / "r6-audit.json"
            self._write_json(audit_path, mutated_audit)
            with self.assertRaisesRegex(ValueError, "recomputation mismatch"):
                _validate_r6(audit_path, R6_RESULT, golden=golden)

            result = json.loads(R6_RESULT.read_text(encoding="utf-8"))
            result[0]["post_id"] = 99999999
            result_path = folder / "r6-result.json"
            self._write_json(result_path, result)
            mutated_audit = json.loads(R6_AUDIT.read_text(encoding="utf-8"))
            mutated_audit["after_result_path"] = result_path.as_posix()
            audit_path = folder / "r6-result-audit.json"
            self._write_json(audit_path, mutated_audit)
            with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
                _validate_r6(audit_path, result_path, golden=golden)

    def test_runtime_target_literal_addition_fails_closed(self):
        pairs = {
            str(row["post_id"]): row["authoritative_identity"]
            for row in self.report["rows"]
        }
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            clean = folder / "clean.py"
            clean.write_text("def generic_gate():\n    return False\n", encoding="utf-8")
            scan = _scan_runtime_literals(pairs=pairs, runtime_source_paths=[clean])
            self.assertEqual(scan["gate"], "GO")
            hardcoded = folder / "hardcoded.py"
            hardcoded.write_text(
                f"TARGET = {pairs['11663514']['title']!r}\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "forbidden N5 literal"):
                _scan_runtime_literals(pairs=pairs, runtime_source_paths=[hardcoded])

    def test_output_is_exclusive_create_and_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            output_json = folder / "judge.json"
            output_md = folder / "judge.md"
            write_outputs(self.report, output_json=output_json, output_md=output_md)
            json_hash = file_sha256(output_json)
            md_hash = file_sha256(output_md)
            with self.assertRaises(FileExistsError):
                write_outputs(self.report, output_json=output_json, output_md=output_md)
            self.assertEqual(file_sha256(output_json), json_hash)
            self.assertEqual(file_sha256(output_md), md_hash)
            self.assertIn("승인 경계", output_md.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
